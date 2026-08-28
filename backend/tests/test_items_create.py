from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth.models import User
from pickone.core.clock import get_clock
from pickone.core.errors import RateLimitedError
from pickone.core.idgen import new_uuid
from pickone.items import repository, service
from pickone.items.errors import (
    AlreadyExistsError,
    AlreadyReportedError,
    InvalidTextError,
    RejectedError,
)
from pickone.moderation.models import ModerationResult
from pickone.moderation.provider import ProviderResult


async def _make_user(session: AsyncSession, *, created_at: object = None) -> User:
    now = get_clock().now()
    user = User(
        id=new_uuid(),
        email=f"{new_uuid()}@example.com",
        password_hash="x",
        is_guest=False,
        email_verified_at=now,
        created_at=created_at or (now - timedelta(days=2)),
        last_seen_at=now,
    )
    session.add(user)
    await session.flush()
    return user


class _StubProvider:
    def __init__(self, result: ProviderResult) -> None:
        self._result = result

    async def check(self, text: str) -> ProviderResult:
        return self._result


async def test_approved_text_is_published(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    provider = _StubProvider(ProviderResult(scores={}, model="stub", raw={}))
    item = await service.create_item(db_session, user=user, text="Carbonara", provider=provider)
    assert item.status == "APPROVED"
    assert item.published_at is not None
    assert item.slug == "carbonara"


async def test_review_score_holds_the_item_unpublished(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    provider = _StubProvider(ProviderResult(scores={"hate": 0.3}, model="stub", raw={}))
    item = await service.create_item(db_session, user=user, text="Iffy item", provider=provider)
    assert item.status == "REVIEW"
    assert item.published_at is None


async def test_rejected_score_raises_and_marks_the_item_rejected(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    provider = _StubProvider(ProviderResult(scores={"hate": 0.9}, model="stub", raw={}))
    with pytest.raises(RejectedError):
        await service.create_item(db_session, user=user, text="Bad item text", provider=provider)


async def test_blocklisted_text_is_rejected_without_calling_the_provider(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)

    class _ExplodingProvider:
        async def check(self, text: str) -> ProviderResult:
            raise AssertionError("provider should never be called for blocklisted text")

    with pytest.raises(RejectedError):
        await service.create_item(
            db_session, user=user, text="kill yourself now", provider=_ExplodingProvider()
        )

    rows = (await db_session.execute(select(ModerationResult))).scalars().all()
    blocklist_rows = [r for r in rows if r.provider == "blocklist"]
    assert len(blocklist_rows) == 1
    assert blocklist_rows[0].decision == "REJECTED"


async def test_duplicate_text_returns_already_exists_with_the_existing_slug(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    provider = _StubProvider(ProviderResult(scores={}, model="stub", raw={}))
    first = await service.create_item(db_session, user=user, text="Carbonara", provider=provider)

    with pytest.raises(AlreadyExistsError) as exc:
        await service.create_item(db_session, user=user, text="CARBONARA!!", provider=provider)
    assert exc.value.details["slug"] == first.slug


async def test_invalid_text_is_rejected_before_any_db_write(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    provider = _StubProvider(ProviderResult(scores={}, model="stub", raw={}))
    with pytest.raises(InvalidTextError):
        await service.create_item(db_session, user=user, text="a", provider=provider)
    assert await repository.get_item_by_normalized_text(db_session, "a") is None


async def test_hourly_rate_limit_is_enforced(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    provider = _StubProvider(ProviderResult(scores={}, model="stub", raw={}))
    from pickone.core.config import get_settings

    limit = get_settings().rl_items_per_hour_user
    for n in range(limit):
        await service.create_item(db_session, user=user, text=f"Item number {n}", provider=provider)
    with pytest.raises(RateLimitedError):
        await service.create_item(db_session, user=user, text="One too many", provider=provider)


async def test_new_account_gets_the_tighter_daily_cap(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pickone.core.config import get_settings

    monkeypatch.setenv("PICKONE_RL_ITEMS_PER_HOUR_USER", "1000")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        user = await _make_user(db_session, created_at=get_clock().now())
        provider = _StubProvider(ProviderResult(scores={}, model="stub", raw={}))

        for n in range(settings.rl_items_per_day_new_account):
            await service.create_item(
                db_session, user=user, text=f"New item {n}", provider=provider
            )
        with pytest.raises(RateLimitedError):
            await service.create_item(
                db_session, user=user, text="Overflow item", provider=provider
            )
    finally:
        get_settings.cache_clear()


async def test_established_account_gets_the_normal_daily_cap(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pickone.core.config import get_settings

    monkeypatch.setenv("PICKONE_RL_ITEMS_PER_HOUR_USER", "1000")
    monkeypatch.setenv("PICKONE_RL_ITEMS_PER_DAY_USER", "6")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        user = await _make_user(db_session, created_at=get_clock().now() - timedelta(days=30))
        provider = _StubProvider(ProviderResult(scores={}, model="stub", raw={}))

        for n in range(settings.rl_items_per_day_user):
            await service.create_item(
                db_session, user=user, text=f"Old item {n}", provider=provider
            )
        with pytest.raises(RateLimitedError):
            await service.create_item(
                db_session, user=user, text="Overflow item", provider=provider
            )
    finally:
        get_settings.cache_clear()


async def test_report_item_then_duplicate_report_conflicts(db_session: AsyncSession) -> None:
    user = await _make_user(db_session)
    reporter = await _make_user(db_session)
    provider = _StubProvider(ProviderResult(scores={}, model="stub", raw={}))
    item = await service.create_item(db_session, user=user, text="Reportable", provider=provider)

    await service.report_item(db_session, item=item, reporter_user_id=reporter.id, reason="spam")
    with pytest.raises(AlreadyReportedError):
        await service.report_item(
            db_session, item=item, reporter_user_id=reporter.id, reason="spam again"
        )


async def test_nth_report_auto_hides_the_item(db_session: AsyncSession) -> None:
    from pickone.core.config import get_settings

    settings = get_settings()
    user = await _make_user(db_session)
    provider = _StubProvider(ProviderResult(scores={}, model="stub", raw={}))
    item = await service.create_item(db_session, user=user, text="Reported item", provider=provider)

    for _ in range(settings.auto_hide_report_count):
        reporter = await _make_user(db_session)
        await service.report_item(
            db_session, item=item, reporter_user_id=reporter.id, reason="spam"
        )
    assert item.status == "HIDDEN"


async def test_apply_moderation_decision_writes_a_new_row_and_updates_the_item(
    db_session: AsyncSession,
) -> None:
    user = await _make_user(db_session)
    reviewer = await _make_user(db_session)
    provider = _StubProvider(ProviderResult(scores={"hate": 0.3}, model="stub", raw={}))
    item = await service.create_item(db_session, user=user, text="Needs review", provider=provider)
    assert item.status == "REVIEW"

    await service.apply_moderation_decision(
        db_session, item=item, decision="APPROVED", reviewed_by_user_id=reviewer.id
    )
    assert item.status == "APPROVED"
    assert item.published_at is not None

    rows = (
        (
            await db_session.execute(
                select(ModerationResult).where(ModerationResult.item_id == item.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2
    admin_rows = [r for r in rows if r.reviewed_by_user_id == reviewer.id]
    assert len(admin_rows) == 1
    assert admin_rows[0].decision == "APPROVED"
