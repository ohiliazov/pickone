from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth import repository
from pickone.auth.service import create_guest


async def test_create_guest_returns_a_real_user_row(db_session: AsyncSession) -> None:
    user, session_row, raw_token = await create_guest(db_session, ip="1.2.3.4", user_agent="pytest")

    assert user.is_guest is True
    assert user.email is None
    assert user.password_hash is None
    assert session_row.user_id == user.id
    assert len(raw_token) > 20

    fetched = await repository.get_user_by_id(db_session, user.id)
    assert fetched is not None
    assert fetched.is_guest is True
