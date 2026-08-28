from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from pickone.items.models import Item


class CreateItemRequest(BaseModel):
    text: str = Field(max_length=1000)


class ItemSummary(BaseModel):
    id: str
    text: str
    slug: str
    status: str
    rating: float

    @classmethod
    def from_item(cls, item: Item) -> ItemSummary:
        return cls(
            id=str(item.id),
            text=item.text,
            slug=item.slug,
            status=item.status,
            rating=float(item.rating),
        )


class ItemDetail(BaseModel):
    id: str
    text: str
    slug: str
    rating: float
    rating_deviation: float
    battle_count: int
    win_count: int
    loss_count: int
    win_rate: float
    rank: int | None
    ranked: bool
    created_at: datetime

    @classmethod
    def from_item(cls, item: Item) -> ItemDetail:
        win_rate = item.win_count / item.battle_count if item.battle_count else 0.0
        return cls(
            id=str(item.id),
            text=item.text,
            slug=item.slug,
            rating=float(item.rating),
            rating_deviation=float(item.rating_deviation),
            battle_count=item.battle_count,
            win_count=item.win_count,
            loss_count=item.loss_count,
            win_rate=win_rate,
            rank=None,
            ranked=False,
            created_at=item.created_at,
        )


class CreateItemResponse(BaseModel):
    item: ItemSummary
    message: str


class ReportRequest(BaseModel):
    reason: str = Field(max_length=500)
