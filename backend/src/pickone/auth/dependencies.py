from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth.errors import VerificationRequiredError
from pickone.auth.models import Session, User
from pickone.auth.service import resolve_session
from pickone.core.errors import NotAuthenticatedError, NotFoundError
from pickone.db.session import get_session

SESSION_COOKIE_NAME = "po_session"


async def current_session_and_actor(
    session: Annotated[AsyncSession, Depends(get_session)],
    po_session: Annotated[str | None, Cookie()] = None,
) -> tuple[Session, User] | None:
    return await resolve_session(session, po_session)


async def current_actor(
    resolved: Annotated[tuple[Session, User] | None, Depends(current_session_and_actor)],
) -> User | None:
    if resolved is None:
        return None
    return resolved[1]


async def required_actor(
    actor: Annotated[User | None, Depends(current_actor)],
) -> User:
    if actor is None:
        raise NotAuthenticatedError()
    return actor


async def required_session(
    resolved: Annotated[tuple[Session, User] | None, Depends(current_session_and_actor)],
) -> Session:
    if resolved is None:
        raise NotAuthenticatedError()
    return resolved[0]


async def registered_user(
    actor: Annotated[User, Depends(required_actor)],
) -> User:
    if actor.is_guest:
        raise NotAuthenticatedError()
    return actor


async def verified_user(
    actor: Annotated[User, Depends(registered_user)],
) -> User:
    if actor.email_verified_at is None:
        raise VerificationRequiredError()
    return actor


async def admin_user(
    actor: Annotated[User, Depends(registered_user)],
) -> User:
    if not actor.is_admin:
        raise NotFoundError()
    return actor
