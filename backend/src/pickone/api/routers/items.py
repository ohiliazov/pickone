from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth.dependencies import registered_user
from pickone.auth.models import User
from pickone.core.errors import GoneError, NotFoundError
from pickone.db.session import get_session
from pickone.items import repository, service
from pickone.items.dependencies import item_author
from pickone.items.schemas import (
    CreateItemRequest,
    CreateItemResponse,
    ItemDetail,
    ItemSummary,
    ReportRequest,
)

router = APIRouter(prefix="/api", tags=["items"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_MESSAGES = {
    "APPROVED": "Added.",
    "REVIEW": "Added. We'll take a quick look before it joins.",
}


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "0.0.0.0"


@router.post("/items")
async def create_item_route(
    body: CreateItemRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    actor: Annotated[User, Depends(item_author)],
) -> CreateItemResponse:
    item = await service.create_item(session, user=actor, text=body.text, ip=_client_ip(request))
    await session.commit()

    response.status_code = (
        status.HTTP_201_CREATED if item.status == "APPROVED" else status.HTTP_202_ACCEPTED
    )
    return CreateItemResponse(item=ItemSummary.from_item(item), message=_MESSAGES[item.status])


@router.get("/items/{slug}")
async def get_item_route(slug: str, session: SessionDep) -> ItemDetail:
    item = await repository.get_item_by_slug(session, slug)
    if item is None:
        raise NotFoundError()
    if item.status in ("HIDDEN", "REJECTED"):
        raise GoneError()
    if item.status != "APPROVED":
        raise NotFoundError()
    return ItemDetail.from_item(item)


@router.post("/items/{slug}/report", status_code=status.HTTP_202_ACCEPTED)
async def report_item_route(
    slug: str,
    body: ReportRequest,
    session: SessionDep,
    actor: Annotated[User, Depends(registered_user)],
) -> None:
    item = await repository.get_item_by_slug(session, slug)
    if item is None:
        raise NotFoundError()
    await service.report_item(session, item=item, reporter_user_id=actor.id, reason=body.reason)
    await session.commit()
