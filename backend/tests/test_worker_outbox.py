from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.core.clock import FrozenClock
from pickone.core.models import OutboxJob
from pickone.core.outbox import enqueue


class _FailingProvider:
    def __init__(self, fail_times: int) -> None:
        self.fail_times = fail_times
        self.calls = 0

    async def send(self, *, to: str, subject: str, body: str) -> None:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("provider down")


class _WorkingProvider:
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send(self, *, to: str, subject: str, body: str) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body})


async def test_outbox_runner_sends_a_ready_job(db_session: AsyncSession) -> None:
    from pickone.worker.jobs.outbox_runner import run_once

    await enqueue(
        db_session, kind="send_email", payload={"to": "a@b.com", "subject": "s", "body": "b"}
    )

    provider = _WorkingProvider()
    processed = await run_once(db_session, provider=provider)

    assert processed == 1
    assert provider.sent == [{"to": "a@b.com", "subject": "s", "body": "b"}]

    job = (await db_session.execute(select(OutboxJob))).scalars().one()
    assert job.completed_at is not None
    assert job.attempts == 1


async def test_outbox_runner_does_not_resend_a_completed_job(db_session: AsyncSession) -> None:
    from pickone.worker.jobs.outbox_runner import run_once

    await enqueue(
        db_session, kind="send_email", payload={"to": "a@b.com", "subject": "s", "body": "b"}
    )

    provider = _WorkingProvider()
    await run_once(db_session, provider=provider)
    processed_again = await run_once(db_session, provider=provider)

    assert processed_again == 0
    assert len(provider.sent) == 1


async def test_outbox_runner_retries_on_failure_with_backoff(
    db_session: AsyncSession, frozen_clock: FrozenClock
) -> None:
    from pickone.worker.jobs.outbox_runner import run_once

    await enqueue(
        db_session, kind="send_email", payload={"to": "a@b.com", "subject": "s", "body": "b"}
    )

    provider = _FailingProvider(fail_times=1)
    processed = await run_once(db_session, provider=provider)
    assert processed == 0

    job = (await db_session.execute(select(OutboxJob))).scalars().one()
    assert job.attempts == 1
    assert job.completed_at is None
    assert job.last_error == "provider down"
    assert job.run_after > frozen_clock.now()

    not_yet_ready = await run_once(db_session, provider=provider)
    assert not_yet_ready == 0

    frozen_clock.set(job.run_after)
    processed_second = await run_once(db_session, provider=provider)
    assert processed_second == 1
    assert provider.calls == 2


async def test_outbox_runner_dead_letters_after_max_attempts(
    db_session: AsyncSession, frozen_clock: FrozenClock
) -> None:
    from pickone.worker.jobs.outbox_runner import run_once

    await enqueue(
        db_session, kind="send_email", payload={"to": "a@b.com", "subject": "s", "body": "b"}
    )

    provider = _FailingProvider(fail_times=100)
    for _ in range(8):
        await run_once(db_session, provider=provider)
        job = (await db_session.execute(select(OutboxJob))).scalars().one()
        if job.completed_at is not None:
            break
        frozen_clock.set(job.run_after)

    job = (await db_session.execute(select(OutboxJob))).scalars().one()
    assert job.attempts == 8
    assert job.completed_at is not None
    assert "dead" in (job.last_error or "").lower()
