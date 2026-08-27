from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth import repository
from pickone.auth.service import create_guest, register
from pickone.core.clock import FrozenClock


async def test_janitor_reaps_an_old_empty_guest(
    db_session: AsyncSession, frozen_clock: FrozenClock
) -> None:
    from pickone.worker.jobs.guest_janitor import run_once

    guest, _s, _t = await create_guest(db_session, ip="1.1.1.1", user_agent="pytest")
    guest_id = guest.id

    frozen_clock.advance(seconds=8 * 86400)

    reaped = await run_once(db_session)

    assert reaped >= 1
    assert await repository.get_user_by_id(db_session, guest_id) is None


async def test_janitor_leaves_a_recent_guest_alone(
    db_session: AsyncSession, frozen_clock: FrozenClock
) -> None:
    from pickone.worker.jobs.guest_janitor import run_once

    guest, _s, _t = await create_guest(db_session, ip="1.1.1.2", user_agent="pytest")
    guest_id = guest.id

    frozen_clock.advance(seconds=3600)

    await run_once(db_session)

    assert await repository.get_user_by_id(db_session, guest_id) is not None


async def test_janitor_never_touches_a_registered_user(
    db_session: AsyncSession, frozen_clock: FrozenClock
) -> None:
    from pickone.worker.jobs.guest_janitor import run_once

    reg = await register(
        db_session, email="janitor1@b.com", password="correcthorse1", guest_token=None
    )
    user_id = reg.user.id

    frozen_clock.advance(seconds=200 * 86400)

    await run_once(db_session)

    assert await repository.get_user_by_id(db_session, user_id) is not None
