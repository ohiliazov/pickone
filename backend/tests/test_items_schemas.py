from __future__ import annotations

from datetime import UTC, datetime

from pickone.core.idgen import new_uuid
from pickone.items.models import Item
from pickone.items.schemas import (
    CreateItemRequest,
    CreateItemResponse,
    ItemDetail,
    ItemSummary,
    ReportRequest,
)


def _item(**overrides: object) -> Item:
    defaults: dict[str, object] = {
        "id": new_uuid(),
        "text": "Carbonara",
        "normalized_text": "carbonara",
        "slug": "carbonara",
        "status": "APPROVED",
        "rating": 100,
        "rating_deviation": 300,
        "battle_count": 0,
        "win_count": 0,
        "loss_count": 0,
        "skip_count": 0,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Item(**defaults)


def test_create_item_request_parses_text() -> None:
    request = CreateItemRequest(text="Fitting bed sheets")
    assert request.text == "Fitting bed sheets"


def test_item_summary_from_item() -> None:
    item = _item()
    summary = ItemSummary.from_item(item)
    assert summary.id == str(item.id)
    assert summary.text == "Carbonara"
    assert summary.slug == "carbonara"
    assert summary.status == "APPROVED"
    assert summary.rating == 100


def test_item_detail_from_item_with_no_battles() -> None:
    item = _item()
    detail = ItemDetail.from_item(item)
    assert detail.win_rate == 0.0
    assert detail.rank is None
    assert detail.ranked is False
    assert detail.battle_count == 0


def test_item_detail_from_item_computes_win_rate() -> None:
    item = _item(battle_count=10, win_count=6, loss_count=4)
    detail = ItemDetail.from_item(item)
    assert detail.win_rate == 0.6


def test_create_item_response_shape() -> None:
    item = _item()
    response = CreateItemResponse(item=ItemSummary.from_item(item), message="Added.")
    assert response.message == "Added."


def test_report_request_parses_reason() -> None:
    request = ReportRequest(reason="spam")
    assert request.reason == "spam"
