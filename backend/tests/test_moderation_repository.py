from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from pickone.core.idgen import new_uuid
from pickone.items.models import Item
from pickone.moderation import repository


async def _make_item(session: AsyncSession) -> Item:
    item = Item(
        id=new_uuid(),
        text="Test Item",
        normalized_text="test item repo",
        slug="test-item-repo",
        status="PENDING_MODERATION",
    )
    session.add(item)
    await session.flush()
    return item


async def test_get_latest_result_for_item_returns_none_when_no_results(
    db_session: AsyncSession,
) -> None:
    item = await _make_item(db_session)
    assert await repository.get_latest_result_for_item(db_session, item.id) is None


async def test_get_latest_result_for_item_returns_the_most_recent(
    db_session: AsyncSession,
) -> None:
    item = await _make_item(db_session)
    await repository.create_moderation_result(
        db_session,
        item_id=item.id,
        provider="first",
        model=None,
        decision="REVIEW",
        scores={"hate": 0.1},
        raw_response=None,
        policy_version="v1",
        latency_ms=10,
    )
    second = await repository.create_moderation_result(
        db_session,
        item_id=item.id,
        provider="second",
        model=None,
        decision="APPROVED",
        scores={"hate": 0.0},
        raw_response=None,
        policy_version="v1",
        latency_ms=5,
    )

    latest = await repository.get_latest_result_for_item(db_session, item.id)
    assert latest is not None
    assert latest.id == second.id
    assert latest.provider == "second"
