from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth.models import User
from pickone.core.config import get_settings
from pickone.core.idgen import new_uuid
from pickone.items import repository
from pickone.items.models import Item


async def _make_guest(session: AsyncSession) -> User:
    user = User(id=new_uuid(), is_guest=True)
    session.add(user)
    await session.flush()
    return user


async def _insert(session: AsyncSession, *, base_slug: str = "carbonara") -> Item:
    return await repository.insert_item_with_unique_slug(
        session,
        text="Carbonara",
        normalized_text=base_slug.replace("-", " "),
        base_slug=base_slug,
        created_by_user_id=None,
    )


async def test_insert_item_uses_config_driven_rating_defaults(db_session: AsyncSession) -> None:
    settings = get_settings()
    item = await _insert(db_session)
    assert item.rating == settings.item_default_rating
    assert item.rating_deviation == settings.item_default_rating_deviation
    assert item.status == "PENDING_MODERATION"


async def test_get_item_by_normalized_text(db_session: AsyncSession) -> None:
    item = await _insert(db_session)
    found = await repository.get_item_by_normalized_text(db_session, "carbonara")
    assert found is not None
    assert found.id == item.id


async def test_get_item_by_normalized_text_returns_none_when_missing(
    db_session: AsyncSession,
) -> None:
    assert await repository.get_item_by_normalized_text(db_session, "nonexistent") is None


async def test_get_item_by_slug(db_session: AsyncSession) -> None:
    item = await _insert(db_session)
    found = await repository.get_item_by_slug(db_session, item.slug)
    assert found is not None
    assert found.id == item.id


async def test_get_item_by_id(db_session: AsyncSession) -> None:
    item = await _insert(db_session)
    found = await repository.get_item_by_id(db_session, item.id)
    assert found is not None
    assert found.slug == item.slug


async def test_slug_collision_appends_numeric_suffix(db_session: AsyncSession) -> None:
    first = await repository.insert_item_with_unique_slug(
        db_session,
        text="Pizza",
        normalized_text="pizza",
        base_slug="pizza",
        created_by_user_id=None,
    )
    second = await repository.insert_item_with_unique_slug(
        db_session,
        text="Pizza again",
        normalized_text="pizza again",
        base_slug="pizza",
        created_by_user_id=None,
    )
    third = await repository.insert_item_with_unique_slug(
        db_session,
        text="Pizza thrice",
        normalized_text="pizza thrice",
        base_slug="pizza",
        created_by_user_id=None,
    )
    assert first.slug == "pizza"
    assert second.slug == "pizza-2"
    assert third.slug == "pizza-3"


async def test_slug_falls_back_to_a_hash_suffix_after_exhausting_numeric_suffixes(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(repository, "MAX_NUMERIC_SUFFIX_ATTEMPTS", 2)
    for base in ("taco", "taco-2"):
        await repository.insert_item_with_unique_slug(
            db_session,
            text="Taco",
            normalized_text=f"taco-{base}",
            base_slug=base,
            created_by_user_id=None,
        )
    overflow = await repository.insert_item_with_unique_slug(
        db_session,
        text="Taco",
        normalized_text="taco-overflow",
        base_slug="taco",
        created_by_user_id=None,
    )
    assert overflow.slug not in {"taco", "taco-2"}
    assert overflow.slug.startswith("taco-")
    assert len(overflow.slug) == len("taco-") + 6


async def test_set_item_status_updates_status_and_published_at(db_session: AsyncSession) -> None:
    item = await _insert(db_session)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    await repository.set_item_status(db_session, item, status="APPROVED", published_at=now)
    assert item.status == "APPROVED"
    assert item.published_at == now


async def test_create_report_and_count_distinct_reporters(db_session: AsyncSession) -> None:
    item = await _insert(db_session)
    reporter_a = await _make_guest(db_session)
    reporter_b = await _make_guest(db_session)
    await repository.create_report(
        db_session, item_id=item.id, reporter_user_id=reporter_a.id, reason="spam"
    )
    await repository.create_report(
        db_session, item_id=item.id, reporter_user_id=reporter_b.id, reason="spam"
    )
    assert await repository.count_distinct_reporters(db_session, item.id) == 2


async def test_list_moderation_queue_returns_only_pending_and_review_oldest_first(
    db_session: AsyncSession,
) -> None:
    approved = await _insert(db_session, base_slug="approved-item")
    await repository.set_item_status(db_session, approved, status="APPROVED")

    pending = await _insert(db_session, base_slug="pending-item")
    review = await _insert(db_session, base_slug="review-item")
    await repository.set_item_status(db_session, review, status="REVIEW")

    queue = await repository.list_moderation_queue(
        db_session, statuses=["PENDING_MODERATION", "REVIEW"]
    )
    queue_ids = [i.id for i in queue]
    assert approved.id not in queue_ids
    assert queue_ids == [pending.id, review.id]


async def test_list_unresolved_reports_grouped_by_item(db_session: AsyncSession) -> None:
    item_a = await _insert(db_session, base_slug="item-a")
    item_b = await _insert(db_session, base_slug="item-b")
    reporter_1 = await _make_guest(db_session)
    reporter_2 = await _make_guest(db_session)
    reporter_3 = await _make_guest(db_session)
    await repository.create_report(
        db_session, item_id=item_a.id, reporter_user_id=reporter_1.id, reason="spam"
    )
    await repository.create_report(
        db_session, item_id=item_a.id, reporter_user_id=reporter_2.id, reason="offensive"
    )
    await repository.create_report(
        db_session, item_id=item_b.id, reporter_user_id=reporter_3.id, reason="spam"
    )

    groups = await repository.list_unresolved_reports_grouped(db_session)
    by_item_id = {g.item.id: g.reports for g in groups}
    assert len(by_item_id[item_a.id]) == 2
    assert len(by_item_id[item_b.id]) == 1
