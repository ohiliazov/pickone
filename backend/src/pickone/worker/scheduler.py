"""The job scheduler.

M0 registers no jobs. Later milestones add theirs here and nowhere else:

    M1  outbox runner, guest janitor
    M4  battle sweeper (every 30s), nightly reconciliation
    M6  rankings materialised-view refresh, sitemap rebuild
    M7  daily metric rollup, analytics pruning
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from pickone.core.logging import get_logger

logger = get_logger(__name__)


def build_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    # No jobs in M0. This is intentional and is asserted by a test, so that
    # adding a job is a deliberate act rather than an accident of a merge.
    logger.info("scheduler_built", jobs=len(scheduler.get_jobs()))
    return scheduler
