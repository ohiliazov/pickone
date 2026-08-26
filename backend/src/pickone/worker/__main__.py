"""Worker entrypoint: ``pickone-worker``."""

from __future__ import annotations

import asyncio
import signal
import sys

from pickone.core.config import Env, get_settings
from pickone.core.logging import configure_logging, get_logger
from pickone.db.engine import get_engine
from pickone.worker.scheduler import build_scheduler
from pickone.worker.singleton import WorkerSingleton, WorkerSingletonError

logger = get_logger("pickone.worker")


async def run() -> int:
    settings = get_settings()
    configure_logging(level=settings.log_level, json_output=settings.env is not Env.LOCAL)

    engine = get_engine()
    try:
        async with WorkerSingleton(engine):
            scheduler = build_scheduler()
            scheduler.start()
            logger.info("worker_started", env=settings.env.value)

            stop = asyncio.Event()
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, stop.set)
            await stop.wait()

            logger.info("worker_stopping")
            scheduler.shutdown(wait=True)
    except WorkerSingletonError as exc:
        logger.warning("worker_not_singleton", reason=str(exc))
        return 1
    finally:
        await engine.dispose()
    return 0


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
