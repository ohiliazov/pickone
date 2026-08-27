from __future__ import annotations

import asyncio
import time

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from pickone.worker.scheduler import build_scheduler
from pickone.worker.singleton import WorkerSingleton, WorkerSingletonError


async def test_first_worker_acquires_the_lock(engine: AsyncEngine) -> None:
    async with WorkerSingleton(engine):
        pass


async def test_second_worker_refuses_to_start(engine: AsyncEngine) -> None:
    async with WorkerSingleton(engine, wait_seconds=0):
        with pytest.raises(WorkerSingletonError):
            async with WorkerSingleton(engine, wait_seconds=0):
                pass


async def test_lock_is_released_on_exit(engine: AsyncEngine) -> None:
    async with WorkerSingleton(engine):
        pass
    async with WorkerSingleton(engine):
        pass


async def test_lock_is_released_when_the_worker_crashes(engine: AsyncEngine) -> None:
    with pytest.raises(RuntimeError):
        async with WorkerSingleton(engine):
            raise RuntimeError("crash")
    async with WorkerSingleton(engine):
        pass


async def test_worker_waits_for_a_departing_predecessor(engine: AsyncEngine) -> None:
    holder = WorkerSingleton(engine, wait_seconds=0)
    await holder.__aenter__()

    async def _release_shortly() -> None:
        await asyncio.sleep(0.3)
        await holder.__aexit__(None, None, None)

    releaser = asyncio.create_task(_release_shortly())
    async with WorkerSingleton(engine, wait_seconds=5, poll_seconds=0.1):
        pass
    await releaser


async def test_waiting_still_gives_up_eventually(engine: AsyncEngine) -> None:
    async with WorkerSingleton(engine, wait_seconds=0):
        started = time.monotonic()
        with pytest.raises(WorkerSingletonError, match="still holds"):
            async with WorkerSingleton(engine, wait_seconds=0.3, poll_seconds=0.1):
                pass
        assert time.monotonic() - started < 3.0


def test_scheduler_registers_exactly_the_expected_jobs() -> None:
    job_ids = {job.id for job in build_scheduler().get_jobs()}
    assert job_ids == {"outbox_runner", "guest_janitor"}
