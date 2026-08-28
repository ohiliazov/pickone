from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth.dependencies import admin_user
from pickone.auth.models import User
from pickone.core.errors import NotFoundError
from pickone.db.session import get_session
from pickone.items import repository, service
from pickone.items.schemas import ItemSummary
from pickone.moderation import repository as moderation_repository

router = APIRouter(prefix="/api/admin", tags=["admin"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
AdminDep = Annotated[User, Depends(admin_user)]


class ModerationQueueItem(BaseModel):
    id: str
    text: str
    slug: str
    status: str
    created_at: datetime
    created_by_user_id: str | None
    latest_scores: dict[str, float]
    latest_provider: str | None


class ModerationQueueResponse(BaseModel):
    items: list[ModerationQueueItem]


class DecisionRequest(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]


class DecisionResponse(BaseModel):
    item: ItemSummary


class ReportEntry(BaseModel):
    id: str
    reporter_user_id: str | None
    reason: str
    created_at: datetime


class ReportedItemGroup(BaseModel):
    item: ItemSummary
    reports: list[ReportEntry]


class ReportsResponse(BaseModel):
    reports: list[ReportedItemGroup]


@router.get("/moderation/queue")
async def moderation_queue_route(session: SessionDep, _actor: AdminDep) -> ModerationQueueResponse:
    queue = await repository.list_moderation_queue(
        session, statuses=["PENDING_MODERATION", "REVIEW"]
    )
    items = []
    for item in queue:
        latest = await moderation_repository.get_latest_result_for_item(session, item.id)
        items.append(
            ModerationQueueItem(
                id=str(item.id),
                text=item.text,
                slug=item.slug,
                status=item.status,
                created_at=item.created_at,
                created_by_user_id=str(item.created_by_user_id)
                if item.created_by_user_id
                else None,
                latest_scores=latest.scores if latest else {},
                latest_provider=latest.provider if latest else None,
            )
        )
    return ModerationQueueResponse(items=items)


@router.get("/reports")
async def reports_route(session: SessionDep, _actor: AdminDep) -> ReportsResponse:
    groups = await repository.list_unresolved_reports_grouped(session)
    return ReportsResponse(
        reports=[
            ReportedItemGroup(
                item=ItemSummary.from_item(group.item),
                reports=[
                    ReportEntry(
                        id=str(r.id),
                        reporter_user_id=str(r.reporter_user_id) if r.reporter_user_id else None,
                        reason=r.reason,
                        created_at=r.created_at,
                    )
                    for r in group.reports
                ],
            )
            for group in groups
        ]
    )


@router.post("/items/{item_id}/decision")
async def decision_route(
    item_id: str, body: DecisionRequest, session: SessionDep, actor: AdminDep
) -> DecisionResponse:
    item = await repository.get_item_by_id(session, item_id)
    if item is None:
        raise NotFoundError()
    await service.apply_moderation_decision(
        session, item=item, decision=body.decision, reviewed_by_user_id=actor.id
    )
    await session.commit()
    return DecisionResponse(item=ItemSummary.from_item(item))
