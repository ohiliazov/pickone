"""Worker singleton enforcement via a Postgres advisory lock.

Exactly one worker instance may run ([SPEC §17.4]). A second instance would
double-run the sweeper harmlessly and double-send emails harmfully, so it must
exit cleanly rather than silently duplicating work.

This uses a *session-level* lock, held for the process lifetime, which is why
the worker holds its own dedicated connection outside the pool. Note that the
battle-creation path deliberately uses ``pg_advisory_xact_lock`` instead, so it
stays compatible with transaction-mode PgBouncer.
"""

from __future__ import annotations

import asyncio
from time import monotonic
from types import TracebackType

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from pickone.core.config import get_settings
from pickone.core.logging import get_logger

logger = get_logger(__name__)

# Arbitrary but fixed. Any other advisory lock in the system must not reuse it.
WORKER_LOCK_KEY = 0x5049434B  # "PICK"


class WorkerSingletonError(RuntimeError):
    """Raised when another worker already holds the lock."""


class WorkerSingleton:
    """Async context manager that acquires the lock or refuses to start."""

    def __init__(
        self,
        engine: AsyncEngine,
        key: int = WORKER_LOCK_KEY,
        *,
        wait_seconds: float | None = None,
        poll_seconds: float | None = None,
    ) -> None:
        settings = get_settings()
        self._engine = engine
        self._key = key
        self._wait = settings.worker_lock_wait_seconds if wait_seconds is None else wait_seconds
        self._poll = settings.worker_lock_poll_seconds if poll_seconds is None else poll_seconds
        self._conn: AsyncConnection | None = None

    async def __aenter__(self) -> WorkerSingleton:
        """Acquire the lock, waiting a bounded time for a predecessor to let go.

        The wait exists for redeploys. When the old worker's container is
        replaced, its Postgres connection — and therefore its lock — can outlive
        it by a few seconds. Failing instantly would turn every deploy into a
        restart loop that only resolves by luck, so a starting worker retries
        for `worker_lock_wait_seconds` before giving up. Giving up is still a
        hard exit: two workers running is worse than none.
        """
        deadline = monotonic() + self._wait
        attempt = 0
        while True:
            attempt += 1
            conn = await self._engine.connect()
            acquired = await conn.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": self._key})
            if acquired:
                self._conn = conn
                logger.info("worker_lock_acquired", key=self._key, attempts=attempt)
                return self

            await conn.close()
            if monotonic() >= deadline:
                raise WorkerSingletonError(
                    f"Another PickOne worker still holds the singleton lock after "
                    f"{self._wait:g}s ({attempt} attempts). Exiting."
                )
            logger.info("worker_lock_busy", key=self._key, attempt=attempt, retry_in=self._poll)
            await asyncio.sleep(self._poll)

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._conn is not None:
            await self._conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": self._key})
            await self._conn.close()
            self._conn = None
            logger.info("worker_lock_released", key=self._key)
