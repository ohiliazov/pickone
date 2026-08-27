from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from pickone.core.config import get_settings
from pickone.core.logging import get_logger
from pickone.db.engine import get_sessionmaker

logger = get_logger(__name__)


async def _run_outbox_once() -> None:
    from pickone.worker.jobs.outbox_runner import run_once

    async with get_sessionmaker()() as session:
        processed = await run_once(session)
        await session.commit()
        if processed:
            logger.info("outbox_processed", count=processed)


async def _run_guest_janitor_once() -> None:
    from pickone.worker.jobs.guest_janitor import run_once

    async with get_sessionmaker()() as session:
        reaped = await run_once(session)
        await session.commit()
        if reaped:
            logger.info("guests_reaped", count=reaped)


def build_scheduler() -> AsyncIOScheduler:
    settings = get_settings()
    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        _run_outbox_once,
        trigger=IntervalTrigger(seconds=settings.outbox_poll_seconds),
        id="outbox_runner",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        _run_guest_janitor_once,
        trigger=IntervalTrigger(minutes=settings.guest_janitor_interval_minutes),
        id="guest_janitor",
        max_instances=1,
        coalesce=True,
    )

    logger.info("scheduler_built", jobs=len(scheduler.get_jobs()))
    return scheduler
