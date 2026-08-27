from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth.errors import InvalidCredentialsError, TooManyAttemptsError
from pickone.auth.service import login, register
from pickone.core.clock import FrozenClock


async def test_login_succeeds_with_correct_credentials(db_session: AsyncSession) -> None:
    await register(db_session, email="a@b.com", password="correcthorse1", guest_token=None)

    result = await login(db_session, email="a@b.com", password="correcthorse1", ip="1.1.1.1")

    assert result.user.email == "a@b.com"
    assert len(result.raw_token) > 20


async def test_login_issues_a_new_session_not_reusing_register_session(
    db_session: AsyncSession,
) -> None:
    reg = await register(db_session, email="a2@b.com", password="correcthorse1", guest_token=None)
    result = await login(db_session, email="a2@b.com", password="correcthorse1", ip="1.1.1.1")

    assert result.raw_token != reg.raw_token
    assert result.session_row.id != reg.session_row.id


async def test_login_rejects_unknown_email(db_session: AsyncSession) -> None:
    with pytest.raises(InvalidCredentialsError):
        await login(db_session, email="nobody@b.com", password="whatever12", ip="2.2.2.2")


async def test_login_rejects_wrong_password(db_session: AsyncSession) -> None:
    await register(db_session, email="b@b.com", password="correcthorse1", guest_token=None)

    with pytest.raises(InvalidCredentialsError):
        await login(db_session, email="b@b.com", password="wrongpassword", ip="3.3.3.3")


async def test_unknown_email_and_wrong_password_raise_the_same_error(
    db_session: AsyncSession,
) -> None:
    await register(db_session, email="c@b.com", password="correcthorse1", guest_token=None)

    unknown_exc = None
    wrong_exc = None
    try:
        await login(db_session, email="doesnotexist@b.com", password="whatever12", ip="4.4.4.1")
    except InvalidCredentialsError as e:
        unknown_exc = e
    try:
        await login(db_session, email="c@b.com", password="wrongpassword", ip="4.4.4.2")
    except InvalidCredentialsError as e:
        wrong_exc = e

    assert unknown_exc is not None and wrong_exc is not None
    assert unknown_exc.envelope() == wrong_exc.envelope()
    assert unknown_exc.status_code == wrong_exc.status_code == 401


async def test_login_backoff_locks_out_after_repeated_failures(
    db_session: AsyncSession, frozen_clock: FrozenClock
) -> None:
    await register(db_session, email="d@b.com", password="correcthorse1", guest_token=None)

    for i in range(5):
        with pytest.raises(InvalidCredentialsError):
            await login(db_session, email="d@b.com", password="wrong", ip=f"5.5.5.{i}")

    with pytest.raises(TooManyAttemptsError) as exc_info:
        await login(db_session, email="d@b.com", password="wrong", ip="5.5.5.99")

    assert exc_info.value.details["retry_after"] > 0

    with pytest.raises(TooManyAttemptsError):
        await login(db_session, email="d@b.com", password="correcthorse1", ip="5.5.5.100")
