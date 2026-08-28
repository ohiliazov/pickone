from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.core.clock import get_clock
from pickone.core.idgen import new_uuid
from pickone.moderation.models import ModerationResult


async def create_moderation_result(
    session: AsyncSession,
    *,
    item_id: str,
    provider: str,
    model: str | None,
    decision: str,
    scores: dict[str, float],
    raw_response: dict[str, Any] | None,
    policy_version: str,
    latency_ms: int | None,
    reviewed_by_user_id: str | None = None,
) -> ModerationResult:
    row = ModerationResult(
        id=new_uuid(),
        item_id=item_id,
        provider=provider,
        model=model,
        decision=decision,
        scores=scores,
        raw_response=raw_response,
        policy_version=policy_version,
        latency_ms=latency_ms,
        reviewed_by_user_id=reviewed_by_user_id,
        created_at=get_clock().now(),
    )
    session.add(row)
    await session.flush()
    return row


async def get_latest_result_for_item(
    session: AsyncSession, item_id: str
) -> ModerationResult | None:
    result = await session.execute(
        select(ModerationResult)
        .where(ModerationResult.item_id == item_id)
        .order_by(ModerationResult.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
