from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth import repository, service
from pickone.auth.dependencies import (
    SESSION_COOKIE_NAME,
    registered_user,
    required_actor,
    required_session,
)
from pickone.auth.models import Session, User
from pickone.auth.schemas import (
    LoginRequest,
    LoginResponse,
    MeLimits,
    MeResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequestRequest,
    RegisterRequest,
    RegisterResponse,
    UserOut,
    VerifyRequest,
    VerifyResponse,
)
from pickone.core import ratelimit
from pickone.core.clock import get_clock
from pickone.core.config import get_settings
from pickone.core.security import derive_csrf_token
from pickone.db.session import get_session
from pickone.items.service import daily_rate_limit_key, effective_daily_item_limit

router = APIRouter(prefix="/api", tags=["auth"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "0.0.0.0"


def _set_session_cookie(response: Response, raw_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=settings.env.is_production,
        samesite="lax",
        path="/",
        max_age=settings.session_ttl_days * 86400,
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register_route(
    body: RegisterRequest,
    request: Request,
    response: Response,
    session: SessionDep,
) -> RegisterResponse:
    guest_token = request.cookies.get(SESSION_COOKIE_NAME)
    result = await service.register(
        session,
        email=body.email,
        password=body.password,
        guest_token=guest_token,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()

    _set_session_cookie(response, result.raw_token)
    csrf_token = derive_csrf_token(result.session_row.csrf_secret, str(result.session_row.id))
    return RegisterResponse(
        user=UserOut.from_user(result.user),
        csrf_token=csrf_token,
        converted_from_guest=result.converted_from_guest,
        picks_kept=result.picks_kept,
    )


@router.post("/auth/login")
async def login_route(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
) -> LoginResponse:
    result = await service.login(
        session,
        email=body.email,
        password=body.password,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )
    await session.commit()

    _set_session_cookie(response, result.raw_token)
    csrf_token = derive_csrf_token(result.session_row.csrf_secret, str(result.session_row.id))
    return LoginResponse(user=UserOut.from_user(result.user), csrf_token=csrf_token)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_route(
    request: Request,
    response: Response,
    session: SessionDep,
) -> None:
    raw_token = request.cookies.get(SESSION_COOKIE_NAME)
    if raw_token:
        resolved = await service.resolve_session(session, raw_token)
        if resolved is not None:
            await repository.revoke_session(session, resolved[0], now=get_clock().now())
            await session.commit()
    _clear_session_cookie(response)


@router.post("/auth/verify")
async def verify_route(body: VerifyRequest, session: SessionDep) -> VerifyResponse:
    user = await service.verify(session, token=body.token)
    await session.commit()
    return VerifyResponse(user=UserOut.from_user(user))


@router.post("/auth/verify/resend", status_code=status.HTTP_202_ACCEPTED)
async def verify_resend_route(
    session: SessionDep,
    actor: Annotated[User, Depends(registered_user)],
) -> None:
    await service.verify_resend(session, user_id=actor.id)
    await session.commit()


@router.post("/auth/password-reset/request", status_code=status.HTTP_202_ACCEPTED)
async def password_reset_request_route(
    body: PasswordResetRequestRequest, request: Request, session: SessionDep
) -> None:
    await service.password_reset_request(session, email=body.email, ip=_client_ip(request))
    await session.commit()


@router.post("/auth/password-reset/confirm")
async def password_reset_confirm_route(
    body: PasswordResetConfirmRequest,
    response: Response,
    session: SessionDep,
) -> UserOut:
    result = await service.password_reset_confirm(
        session, token=body.token, new_password=body.password
    )
    await session.commit()
    _set_session_cookie(response, result.raw_token)
    return UserOut.from_user(result.user)


@router.get("/me")
async def me_route(
    actor: Annotated[User, Depends(required_actor)],
    session_row: Annotated[Session, Depends(required_session)],
    session: SessionDep,
) -> MeResponse:
    csrf_token = derive_csrf_token(session_row.csrf_secret, str(session_row.id))
    now = get_clock().now()
    daily_limit = effective_daily_item_limit(actor, now=now)
    used = await ratelimit.peek(session, daily_rate_limit_key(actor), window_seconds=86400)
    return MeResponse(
        user=UserOut.from_user(actor),
        csrf_token=csrf_token,
        limits=MeLimits(items_remaining_today=max(daily_limit - used, 0)),
    )


@router.post("/me/delete", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account_route(
    response: Response,
    session: SessionDep,
    actor: Annotated[User, Depends(registered_user)],
) -> None:
    await service.delete_account(session, user_id=actor.id)
    await session.commit()
    _clear_session_cookie(response)
