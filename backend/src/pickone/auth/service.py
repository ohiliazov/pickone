from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth import repository
from pickone.auth.email_provider import (
    OutboxProvider,
    reset_password_template,
    verify_email_template,
)
from pickone.auth.errors import (
    EmailTakenError,
    InvalidCredentialsError,
    TokenExpiredError,
    TokenInvalidError,
    TooManyAttemptsError,
    WeakPasswordError,
)
from pickone.auth.models import Session, User
from pickone.core import ratelimit
from pickone.core.clock import get_clock
from pickone.core.config import get_settings
from pickone.core.security import (
    hash_ip,
    hash_password,
    hash_token,
    hash_user_agent,
    needs_rehash,
    new_csrf_secret,
    new_token,
    verify_password,
    verify_password_constant_time_dummy,
)
from pickone.core.starter_common_passwords import is_in_starter_common_passwords


def _validate_password(password: str) -> None:
    settings = get_settings()
    if len(password) < settings.password_min_length:
        raise WeakPasswordError(details={"min_length": settings.password_min_length})
    if is_in_starter_common_passwords(password):
        raise WeakPasswordError()


async def _issue_session(
    session: AsyncSession, user_id: str, *, ip: str | None, user_agent: str | None
) -> tuple[Session, str]:
    settings = get_settings()
    clock = get_clock()
    raw_token = new_token()
    row = await repository.create_session(
        session,
        user_id=user_id,
        token_hash=hash_token(raw_token),
        csrf_secret=new_csrf_secret(),
        expires_at=clock.now() + timedelta(days=settings.session_ttl_days),
        user_agent_hash=hash_user_agent(user_agent) if user_agent else None,
        ip_hash=hash_ip(ip) if ip else None,
    )
    return row, raw_token


async def resolve_session(
    session: AsyncSession, raw_token: str | None
) -> tuple[Session, User] | None:
    if not raw_token:
        return None
    row = await repository.get_active_session_by_token_hash(session, hash_token(raw_token))
    if row is None:
        return None
    clock = get_clock()
    now = clock.now()
    if row.expires_at <= now:
        return None
    user = await repository.get_user_by_id(session, row.user_id)
    if user is None or not user.is_active:
        return None
    settings = get_settings()
    new_expires_at = min(
        now + timedelta(days=settings.session_ttl_days),
        row.created_at + timedelta(days=settings.session_absolute_ttl_days),
    )
    await repository.touch_session(session, row, now=now, new_expires_at=new_expires_at)
    await repository.touch_user_last_seen(session, user, now=now)
    return row, user


async def create_guest(
    session: AsyncSession, *, ip: str, user_agent: str | None
) -> tuple[User, Session, str]:
    settings = get_settings()
    await ratelimit.enforce(
        session,
        f"guest_create:ip:{hash_ip(ip).hex()}",
        limit=settings.rl_guest_create_per_hour_ip,
        window_seconds=3600,
    )
    user = await repository.create_guest_user(session)
    session_row, raw_token = await _issue_session(session, user.id, ip=ip, user_agent=user_agent)
    return user, session_row, raw_token


@dataclass(frozen=True)
class RegisterResult:
    user: User
    session_row: Session
    raw_token: str
    converted_from_guest: bool
    picks_kept: int


async def register(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    guest_token: str | None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> RegisterResult:
    settings = get_settings()
    if ip is not None:
        await ratelimit.enforce(
            session,
            f"register:ip:{hash_ip(ip).hex()}",
            limit=settings.rl_register_per_hour_ip,
            window_seconds=3600,
        )
        await ratelimit.enforce(
            session,
            f"register:ip_day:{hash_ip(ip).hex()}",
            limit=settings.rl_register_per_day_ip,
            window_seconds=86400,
        )

    _validate_password(password)

    resolved = await resolve_session(session, guest_token)
    guest_session, guest_user = resolved if resolved is not None else (None, None)
    converting_guest = guest_user is not None and guest_user.is_guest

    existing = await repository.get_user_by_email(session, email)
    if existing is not None:
        raise EmailTakenError()

    password_hash = hash_password(password)

    if converting_guest and guest_session is not None and guest_user is not None:
        user = await repository.convert_guest_to_registered(
            session, guest_user, email=email, password_hash=password_hash
        )
        await repository.revoke_session(session, guest_session, now=get_clock().now())
        picks_kept = 0
    else:
        user = await repository.create_registered_user(
            session, email=email, password_hash=password_hash
        )
        picks_kept = 0

    session_row, raw_token = await _issue_session(session, user.id, ip=ip, user_agent=user_agent)

    verify_raw_token = new_token()
    await repository.create_email_token(
        session,
        user_id=user.id,
        purpose="VERIFY_EMAIL",
        token_hash=hash_token(verify_raw_token),
        expires_at=get_clock().now() + timedelta(hours=settings.verify_token_ttl_hours),
    )
    verify_url = f"{settings.base_url}/verify?token={verify_raw_token}"
    subject, body = verify_email_template(verify_url=verify_url)
    await OutboxProvider().send(session, to=email, subject=subject, body=body)

    return RegisterResult(
        user=user,
        session_row=session_row,
        raw_token=raw_token,
        converted_from_guest=converting_guest,
        picks_kept=picks_kept,
    )


@dataclass(frozen=True)
class LoginResult:
    user: User
    session_row: Session
    raw_token: str


async def login(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    ip: str,
    user_agent: str | None = None,
) -> LoginResult:
    settings = get_settings()
    clock = get_clock()

    account_key = f"login:acct:{email.lower()}"
    account_failures = await ratelimit.peek(session, account_key, window_seconds=900, clock=clock)
    if account_failures >= settings.rl_login_per_15min_account:
        excess = account_failures - settings.rl_login_per_15min_account
        delay = min(
            settings.rl_login_backoff_base_seconds * (2**excess),
            settings.rl_login_backoff_max_minutes * 60,
        )
        raise TooManyAttemptsError(
            details={"retry_after": int(delay)},
            headers={"Retry-After": str(int(delay))},
        )

    await ratelimit.enforce(
        session,
        f"login:ip:{hash_ip(ip).hex()}",
        limit=settings.rl_login_per_15min_ip,
        window_seconds=900,
        clock=clock,
    )

    user = await repository.get_user_by_email(session, email)
    if user is None or user.password_hash is None:
        verify_password_constant_time_dummy()
        await ratelimit.increment(session, account_key, window_seconds=900, clock=clock)
        raise InvalidCredentialsError()

    if not verify_password(password, user.password_hash):
        await ratelimit.increment(session, account_key, window_seconds=900, clock=clock)
        raise InvalidCredentialsError()

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        await session.flush()

    await repository.touch_user_last_seen(session, user, now=clock.now())

    session_row, raw_token = await _issue_session(session, user.id, ip=ip, user_agent=user_agent)
    return LoginResult(user=user, session_row=session_row, raw_token=raw_token)


async def verify(session: AsyncSession, *, token: str) -> User:
    row = await repository.get_email_token_by_hash(session, hash_token(token))
    if row is None or row.purpose != "VERIFY_EMAIL":
        raise TokenInvalidError()
    if row.used_at is not None:
        raise TokenInvalidError()

    clock = get_clock()
    now = clock.now()
    if row.expires_at <= now:
        raise TokenExpiredError()

    user = await repository.get_user_by_id(session, row.user_id)
    if user is None:
        raise TokenInvalidError()

    await repository.mark_email_token_used(session, row, now=now)
    user.email_verified_at = now
    await session.flush()
    return user


async def verify_resend(session: AsyncSession, *, user_id: str) -> None:
    settings = get_settings()
    clock = get_clock()

    await ratelimit.enforce(
        session,
        f"verify_resend:user:{user_id}",
        limit=settings.rl_verify_resend_per_hour_user,
        window_seconds=3600,
        clock=clock,
    )

    user = await repository.get_user_by_id(session, user_id)
    if user is None or user.email is None:
        return

    raw_token = new_token()
    await repository.create_email_token(
        session,
        user_id=user.id,
        purpose="VERIFY_EMAIL",
        token_hash=hash_token(raw_token),
        expires_at=clock.now() + timedelta(hours=settings.verify_token_ttl_hours),
    )
    verify_url = f"{settings.base_url}/verify?token={raw_token}"
    subject, body = verify_email_template(verify_url=verify_url)
    await OutboxProvider().send(session, to=user.email, subject=subject, body=body)


async def password_reset_request(
    session: AsyncSession, *, email: str, ip: str | None = None
) -> None:
    settings = get_settings()
    clock = get_clock()

    await ratelimit.enforce(
        session,
        f"reset_request:email:{email.lower()}",
        limit=settings.rl_reset_request_per_hour_email,
        window_seconds=3600,
        clock=clock,
    )
    if ip is not None:
        await ratelimit.enforce(
            session,
            f"reset_request:ip:{hash_ip(ip).hex()}",
            limit=settings.rl_reset_request_per_hour_ip,
            window_seconds=3600,
            clock=clock,
        )

    user = await repository.get_user_by_email(session, email)
    if user is None or user.is_guest:
        return

    raw_token = new_token()
    await repository.create_email_token(
        session,
        user_id=user.id,
        purpose="RESET_PASSWORD",
        token_hash=hash_token(raw_token),
        expires_at=clock.now() + timedelta(minutes=settings.reset_token_ttl_minutes),
    )
    reset_url = f"{settings.base_url}/reset?token={raw_token}"
    subject, body = reset_password_template(reset_url=reset_url)
    await OutboxProvider().send(session, to=email, subject=subject, body=body)


@dataclass(frozen=True)
class PasswordResetResult:
    user: User
    session_row: Session
    raw_token: str


async def password_reset_confirm(
    session: AsyncSession, *, token: str, new_password: str
) -> PasswordResetResult:
    row = await repository.get_email_token_by_hash(session, hash_token(token))
    if row is None or row.purpose != "RESET_PASSWORD":
        raise TokenInvalidError()
    if row.used_at is not None:
        raise TokenInvalidError()

    clock = get_clock()
    now = clock.now()
    if row.expires_at <= now:
        raise TokenExpiredError()

    user = await repository.get_user_by_id(session, row.user_id)
    if user is None:
        raise TokenInvalidError()

    _validate_password(new_password)

    user.password_hash = hash_password(new_password)
    await session.flush()

    await repository.revoke_all_sessions_for_user(session, user.id, now=now)
    await repository.mark_email_token_used(session, row, now=now)

    session_row, raw_token = await _issue_session(session, user.id, ip=None, user_agent=None)
    return PasswordResetResult(user=user, session_row=session_row, raw_token=raw_token)


async def delete_account(session: AsyncSession, *, user_id: str) -> None:
    now = get_clock().now()
    await repository.revoke_all_sessions_for_user(session, user_id, now=now)
    await repository.delete_all_email_tokens_for_user(session, user_id)
    await repository.delete_user(session, user_id)
