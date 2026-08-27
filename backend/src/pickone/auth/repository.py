from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth.models import EmailToken, Session, User
from pickone.core.clock import get_clock
from pickone.core.idgen import new_uuid


async def get_user_by_id(session: AsyncSession, user_id: str) -> User | None:
    return await session.get(User, user_id)


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_registered_user(session: AsyncSession, *, email: str, password_hash: str) -> User:
    now = get_clock().now()
    user = User(
        id=new_uuid(),
        email=email,
        password_hash=password_hash,
        is_guest=False,
        created_at=now,
        last_seen_at=now,
    )
    session.add(user)
    await session.flush()
    return user


async def create_guest_user(session: AsyncSession) -> User:
    now = get_clock().now()
    user = User(
        id=new_uuid(),
        email=None,
        password_hash=None,
        is_guest=True,
        created_at=now,
        last_seen_at=now,
    )
    session.add(user)
    await session.flush()
    return user


async def convert_guest_to_registered(
    session: AsyncSession, user: User, *, email: str, password_hash: str
) -> User:
    user.email = email
    user.password_hash = password_hash
    user.is_guest = False
    await session.flush()
    return user


async def create_session(
    session: AsyncSession,
    *,
    user_id: str,
    token_hash: bytes,
    csrf_secret: bytes,
    expires_at: datetime,
    user_agent_hash: bytes | None = None,
    ip_hash: bytes | None = None,
) -> Session:
    now = get_clock().now()
    row = Session(
        id=new_uuid(),
        user_id=user_id,
        token_hash=token_hash,
        csrf_secret=csrf_secret,
        expires_at=expires_at,
        created_at=now,
        last_seen_at=now,
        user_agent_hash=user_agent_hash,
        ip_hash=ip_hash,
    )
    session.add(row)
    await session.flush()
    return row


async def get_active_session_by_token_hash(
    session: AsyncSession, token_hash: bytes
) -> Session | None:
    result = await session.execute(
        select(Session).where(Session.token_hash == token_hash, Session.revoked_at.is_(None))
    )
    return result.scalar_one_or_none()


async def touch_session(
    session: AsyncSession, row: Session, *, now: datetime, new_expires_at: datetime
) -> None:
    row.last_seen_at = now
    row.expires_at = new_expires_at
    await session.flush()


async def revoke_session(session: AsyncSession, row: Session, *, now: datetime) -> None:
    row.revoked_at = now
    await session.flush()


async def revoke_all_sessions_for_user(
    session: AsyncSession, user_id: str, *, now: datetime
) -> None:
    await session.execute(
        update(Session)
        .where(Session.user_id == user_id, Session.revoked_at.is_(None))
        .values(revoked_at=now)
    )


async def create_email_token(
    session: AsyncSession,
    *,
    user_id: str,
    purpose: str,
    token_hash: bytes,
    expires_at: datetime,
) -> EmailToken:
    row = EmailToken(
        id=new_uuid(),
        user_id=user_id,
        purpose=purpose,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    session.add(row)
    await session.flush()
    return row


async def get_email_token_by_hash(session: AsyncSession, token_hash: bytes) -> EmailToken | None:
    result = await session.execute(select(EmailToken).where(EmailToken.token_hash == token_hash))
    return result.scalar_one_or_none()


async def mark_email_token_used(session: AsyncSession, row: EmailToken, *, now: datetime) -> None:
    row.used_at = now
    await session.flush()


async def delete_all_email_tokens_for_user(session: AsyncSession, user_id: str) -> None:
    await session.execute(delete(EmailToken).where(EmailToken.user_id == user_id))


async def touch_user_last_seen(session: AsyncSession, user: User, *, now: datetime) -> None:
    user.last_seen_at = now
    await session.flush()


async def delete_user(session: AsyncSession, user_id: str) -> None:
    await session.execute(delete(User).where(User.id == user_id))
