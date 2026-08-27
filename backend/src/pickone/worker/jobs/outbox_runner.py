from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth.email_provider import EmailProvider, build_provider
from pickone.core.clock import get_clock
from pickone.core.config import get_settings
from pickone.core.models import OutboxJob


async def run_once(session: AsyncSession, *, provider: EmailProvider | None = None) -> int:
    provider = provider or build_provider()
    settings = get_settings()
    clock = get_clock()
    now = clock.now()

    result = await session.execute(
        select(OutboxJob)
        .where(
            OutboxJob.completed_at.is_(None),
            OutboxJob.locked_at.is_(None),
            OutboxJob.run_after <= now,
        )
        .order_by(OutboxJob.run_after)
        .with_for_update(skip_locked=True)
    )
    jobs = result.scalars().all()

    processed = 0
    for job in jobs:
        job.locked_at = now
        await session.flush()

        try:
            await provider.send(**job.payload)
        except Exception as exc:
            job.attempts += 1
            job.last_error = str(exc)
            job.locked_at = None
            if job.attempts >= settings.outbox_max_attempts:
                job.completed_at = now
                job.last_error = f"dead-lettered after {job.attempts} attempts: {exc}"
            else:
                delay = min(
                    settings.outbox_backoff_base_seconds * (2 ** (job.attempts - 1)),
                    settings.outbox_backoff_max_seconds,
                )
                job.run_after = now + timedelta(seconds=delay)
            await session.flush()
            continue

        job.attempts += 1
        job.completed_at = now
        job.locked_at = None
        await session.flush()
        processed += 1

    return processed
