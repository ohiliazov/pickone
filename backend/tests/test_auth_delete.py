from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth import repository
from pickone.auth.models import EmailToken, Session
from pickone.auth.service import delete_account, login, register


async def test_delete_account_removes_the_user_row(db_session: AsyncSession) -> None:
    reg = await register(db_session, email="del1@b.com", password="correcthorse1", guest_token=None)

    await delete_account(db_session, user_id=reg.user.id)

    assert await repository.get_user_by_id(db_session, reg.user.id) is None


async def test_delete_account_removes_all_sessions(db_session: AsyncSession) -> None:
    reg = await register(db_session, email="del2@b.com", password="correcthorse1", guest_token=None)
    await login(db_session, email="del2@b.com", password="correcthorse1", ip="7.7.7.7")

    await delete_account(db_session, user_id=reg.user.id)

    remaining = (
        (await db_session.execute(select(Session).where(Session.user_id == reg.user.id)))
        .scalars()
        .all()
    )
    assert remaining == []


async def test_delete_account_removes_all_email_tokens(db_session: AsyncSession) -> None:
    reg = await register(db_session, email="del3@b.com", password="correcthorse1", guest_token=None)

    await delete_account(db_session, user_id=reg.user.id)

    remaining = (
        (await db_session.execute(select(EmailToken).where(EmailToken.user_id == reg.user.id)))
        .scalars()
        .all()
    )
    assert remaining == []
