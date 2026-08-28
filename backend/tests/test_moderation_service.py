from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.core.idgen import new_uuid
from pickone.items.models import Item
from pickone.moderation.circuit_breaker import get_circuit_breaker
from pickone.moderation.models import ModerationResult
from pickone.moderation.provider import ProviderResult
from pickone.moderation.service import moderate


async def _make_item(session: AsyncSession, *, slug: str = "test-item") -> Item:
    item = Item(
        id=new_uuid(),
        text="Test Item",
        normalized_text="test item",
        slug=slug,
        status="PENDING_MODERATION",
    )
    session.add(item)
    await session.flush()
    return item


class _StubProvider:
    def __init__(
        self, result: ProviderResult | None = None, error: Exception | None = None
    ) -> None:
        self._result = result
        self._error = error
        self.calls = 0

    async def check(self, text: str) -> ProviderResult:
        self.calls += 1
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


async def test_clean_text_is_approved(db_session: AsyncSession) -> None:
    item = await _make_item(db_session)
    stub = _StubProvider(ProviderResult(scores={}, model="stub", raw={"ok": True}))
    outcome = await moderate(db_session, item_id=item.id, text="hello", provider=stub)
    assert outcome.decision == "APPROVED"
    assert outcome.model == "stub"


async def test_high_scores_are_rejected(db_session: AsyncSession) -> None:
    item = await _make_item(db_session)
    stub = _StubProvider(ProviderResult(scores={"hate": 0.9}, model="stub", raw={}))
    outcome = await moderate(db_session, item_id=item.id, text="hello", provider=stub)
    assert outcome.decision == "REJECTED"


async def test_provider_exception_yields_error_and_records_failure(
    db_session: AsyncSession,
) -> None:
    item = await _make_item(db_session)
    stub = _StubProvider(error=RuntimeError("boom"))
    breaker = get_circuit_breaker()
    outcome = await moderate(db_session, item_id=item.id, text="hello", provider=stub)
    assert outcome.decision == "ERROR"
    assert breaker._consecutive_failures == 1


class _SlowProvider:
    async def check(self, text: str) -> ProviderResult:
        import asyncio

        await asyncio.sleep(1.0)
        return ProviderResult(scores={}, model="slow", raw={})


async def test_provider_timeout_yields_error(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pickone.core.config import get_settings

    monkeypatch.setenv("PICKONE_MODERATION_TIMEOUT_MS", "10")
    get_settings.cache_clear()
    try:
        item = await _make_item(db_session)
        breaker = get_circuit_breaker()
        outcome = await moderate(
            db_session, item_id=item.id, text="hello", provider=_SlowProvider()
        )
        assert outcome.decision == "ERROR"
        assert breaker._consecutive_failures == 1
    finally:
        get_settings.cache_clear()


async def test_circuit_breaker_open_skips_the_provider_call(db_session: AsyncSession) -> None:
    item = await _make_item(db_session)
    breaker = get_circuit_breaker()
    for _ in range(10):
        breaker.record_failure()
    assert breaker.is_open()
    stub = _StubProvider(ProviderResult(scores={}, model="stub", raw={}))
    outcome = await moderate(db_session, item_id=item.id, text="hello", provider=stub)
    assert outcome.decision == "ERROR"
    assert stub.calls == 0


async def test_moderation_result_is_persisted_with_all_fields(db_session: AsyncSession) -> None:
    item = await _make_item(db_session)
    stub = _StubProvider(ProviderResult(scores={"hate": 0.01}, model="stub-model", raw={"a": 1}))
    await moderate(db_session, item_id=item.id, text="hello", provider=stub)

    row = (
        await db_session.execute(
            select(ModerationResult).where(ModerationResult.item_id == item.id)
        )
    ).scalar_one()
    assert row.provider == "_StubProvider"
    assert row.model == "stub-model"
    assert row.decision == "APPROVED"
    assert row.scores == {"hate": 0.01}
    assert row.raw_response == {"a": 1}
    assert row.policy_version == "v1"
    assert row.latency_ms is not None


async def test_moderation_results_are_append_only(db_session: AsyncSession) -> None:
    item = await _make_item(db_session)
    stub = _StubProvider(ProviderResult(scores={}, model="stub", raw={}))
    await moderate(db_session, item_id=item.id, text="hello", provider=stub)
    await moderate(db_session, item_id=item.id, text="hello", provider=stub)

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
