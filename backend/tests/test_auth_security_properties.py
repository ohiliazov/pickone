from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth.models import EmailToken, Session, User
from pickone.auth.service import register


async def test_session_token_hash_is_not_the_plaintext_token(db_session: AsyncSession) -> None:
    reg = await register(db_session, email="tok1@b.com", password="correcthorse1", guest_token=None)

    row = await db_session.get(Session, reg.session_row.id)
    assert row is not None
    assert row.token_hash != reg.raw_token.encode("utf-8")
    assert row.token_hash == hashlib.sha256(reg.raw_token.encode("utf-8")).digest()
    assert len(row.token_hash) == 32
    assert reg.raw_token.encode("utf-8") not in row.token_hash


async def test_email_token_hash_is_not_the_plaintext_token(db_session: AsyncSession) -> None:
    from urllib.parse import parse_qs, urlparse

    from pickone.core.models import OutboxJob

    await register(db_session, email="tok2@b.com", password="correcthorse1", guest_token=None)

    job = (await db_session.execute(select(OutboxJob))).scalars().one()
    url = job.payload["body"].split("\n\n")[1].strip()
    raw_verify_token = parse_qs(urlparse(url).query)["token"][0]

    row = (await db_session.execute(select(EmailToken))).scalars().one()
    assert len(row.token_hash) == 32
    assert row.token_hash == hashlib.sha256(raw_verify_token.encode("utf-8")).digest()
    assert raw_verify_token.encode("utf-8") not in row.token_hash


async def test_credentials_check_constraint_rejects_a_non_guest_null_email(
    db_session: AsyncSession,
) -> None:
    from pickone.core.idgen import new_uuid

    bad = User(id=new_uuid(), is_guest=False, email=None, password_hash="x")
    db_session.add(bad)
    with pytest.raises(Exception, match="credentials"):
        await db_session.flush()


async def test_credentials_check_constraint_rejects_a_guest_with_an_email(
    db_session: AsyncSession,
) -> None:
    from pickone.core.idgen import new_uuid

    bad = User(id=new_uuid(), is_guest=True, email="shouldnt@have.email", password_hash=None)
    db_session.add(bad)
    with pytest.raises(Exception, match="credentials"):
        await db_session.flush()


async def test_credentials_check_constraint_permits_a_guest_with_both_null(
    db_session: AsyncSession,
) -> None:
    from pickone.core.idgen import new_uuid

    uid = new_uuid()
    ok = User(id=uid, is_guest=True, email=None, password_hash=None)
    db_session.add(ok)
    await db_session.flush()

    row = await db_session.get(User, uid)
    assert row is not None
    assert row.is_guest is True


async def test_password_is_rehashed_when_argon2_params_change(db_session: AsyncSession) -> None:
    from pickone.auth.service import login
    from pickone.core.config import get_settings

    reg = await register(
        db_session, email="rehash1@b.com", password="correcthorse1", guest_token=None
    )
    original_hash = reg.user.password_hash

    settings = get_settings()
    object.__setattr__(settings, "argon2_time_cost", settings.argon2_time_cost + 1)
    try:
        result = await login(
            db_session, email="rehash1@b.com", password="correcthorse1", ip="9.1.1.1"
        )
    finally:
        object.__setattr__(settings, "argon2_time_cost", settings.argon2_time_cost - 1)

    assert result.user.password_hash != original_hash


def test_argon2_parameters_match_the_spec_defaults() -> None:
    from pickone.core.config import get_settings

    settings = get_settings()
    assert settings.argon2_time_cost == 3
    assert settings.argon2_memory_cost_kib == 65536
    assert settings.argon2_parallelism == 4


def test_argon2_hashing_is_not_instant() -> None:
    import time

    from pickone.core.security import hash_password

    started = time.perf_counter()
    hash_password("correcthorsebatterystaple")
    elapsed_ms = (time.perf_counter() - started) * 1000

    if not (5 <= elapsed_ms <= 3000):
        pytest.skip(f"Argon2 timing {elapsed_ms:.0f}ms is atypical for this runner")
    assert elapsed_ms >= 5
