from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth import repository
from pickone.auth.errors import EmailTakenError, WeakPasswordError
from pickone.auth.service import create_guest, register, resolve_session
from pickone.core.models import OutboxJob


async def test_register_creates_a_fresh_user(db_session: AsyncSession) -> None:
    result = await register(db_session, email="a@b.com", password="correcthorse1", guest_token=None)

    assert result.user.email == "a@b.com"
    assert result.user.is_guest is False
    assert result.converted_from_guest is False
    assert len(result.raw_token) > 20

    stored = await repository.get_user_by_email(db_session, "a@b.com")
    assert stored is not None
    assert stored.password_hash != "correcthorse1"


async def test_register_enqueues_a_verification_email(db_session: AsyncSession) -> None:
    await register(db_session, email="verify-me@b.com", password="correcthorse1", guest_token=None)

    jobs = (await db_session.execute(select(OutboxJob))).scalars().all()
    assert any(j.payload.get("to") == "verify-me@b.com" for j in jobs)


async def test_register_rejects_a_taken_email(db_session: AsyncSession) -> None:
    await register(db_session, email="dup@b.com", password="correcthorse1", guest_token=None)

    with pytest.raises(EmailTakenError):
        await register(db_session, email="dup@b.com", password="anotherpass1", guest_token=None)


async def test_register_rejects_a_short_password(db_session: AsyncSession) -> None:
    with pytest.raises(WeakPasswordError):
        await register(db_session, email="short@b.com", password="short1", guest_token=None)


async def test_register_rejects_a_common_password(db_session: AsyncSession) -> None:
    with pytest.raises(WeakPasswordError):
        await register(db_session, email="common@b.com", password="password123", guest_token=None)


async def test_register_converts_a_guest_in_place(db_session: AsyncSession) -> None:
    guest, _guest_session, guest_raw_token = await create_guest(
        db_session, ip="9.9.9.9", user_agent="pytest"
    )
    guest_id = guest.id

    result = await register(
        db_session, email="was-guest@b.com", password="correcthorse1", guest_token=guest_raw_token
    )

    assert result.converted_from_guest is True
    assert result.user.id == guest_id
    assert result.user.is_guest is False
    assert result.user.email == "was-guest@b.com"

    resolved = await resolve_session(db_session, guest_raw_token)
    assert resolved is None


async def test_register_with_taken_email_leaves_guest_row_untouched(
    db_session: AsyncSession,
) -> None:
    await register(db_session, email="taken@b.com", password="correcthorse1", guest_token=None)

    guest, _guest_session, guest_raw_token = await create_guest(
        db_session, ip="9.9.9.8", user_agent="pytest"
    )
    guest_id = guest.id

    with pytest.raises(EmailTakenError):
        await register(
            db_session, email="taken@b.com", password="anotherpass1", guest_token=guest_raw_token
        )

    still_guest = await repository.get_user_by_id(db_session, guest_id)
    assert still_guest is not None
    assert still_guest.is_guest is True
    assert still_guest.email is None
