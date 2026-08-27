from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth.errors import TokenExpiredError, TokenInvalidError
from pickone.auth.service import register, verify, verify_resend
from pickone.core.clock import FrozenClock
from pickone.core.models import OutboxJob


async def _latest_email_token(db_session: AsyncSession, to: str) -> str:
    jobs = (
        (await db_session.execute(select(OutboxJob).order_by(OutboxJob.created_at.desc())))
        .scalars()
        .all()
    )
    job = next(j for j in jobs if j.payload.get("to") == to)
    url = job.payload["body"].split("\n\n")[1].strip()
    return str(parse_qs(urlparse(url).query)["token"][0])


async def test_verify_marks_the_user_verified(db_session: AsyncSession) -> None:
    reg = await register(db_session, email="v1@b.com", password="correcthorse1", guest_token=None)
    token = await _latest_email_token(db_session, "v1@b.com")

    user = await verify(db_session, token=token)

    assert user.id == reg.user.id
    assert user.email_verified_at is not None


async def test_verify_rejects_an_unknown_token(db_session: AsyncSession) -> None:
    with pytest.raises(TokenInvalidError):
        await verify(db_session, token="not-a-real-token")


async def test_verify_rejects_a_reused_token(db_session: AsyncSession) -> None:
    await register(db_session, email="v2@b.com", password="correcthorse1", guest_token=None)
    token = await _latest_email_token(db_session, "v2@b.com")

    await verify(db_session, token=token)

    with pytest.raises(TokenInvalidError):
        await verify(db_session, token=token)


async def test_verify_rejects_an_expired_token(
    db_session: AsyncSession, frozen_clock: FrozenClock
) -> None:
    await register(db_session, email="v3@b.com", password="correcthorse1", guest_token=None)
    token = await _latest_email_token(db_session, "v3@b.com")

    frozen_clock.advance(seconds=25 * 3600)

    with pytest.raises(TokenExpiredError):
        await verify(db_session, token=token)


async def test_verify_resend_enqueues_a_new_email(db_session: AsyncSession) -> None:
    reg = await register(db_session, email="v4@b.com", password="correcthorse1", guest_token=None)

    await verify_resend(db_session, user_id=reg.user.id)

    jobs = (await db_session.execute(select(OutboxJob))).scalars().all()
    assert sum(1 for j in jobs if j.payload.get("to") == "v4@b.com") == 2
