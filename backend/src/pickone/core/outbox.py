from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from pickone.core.clock import get_clock
from pickone.core.idgen import new_uuid
from pickone.core.models import OutboxJob


async def enqueue(
    session: AsyncSession,
    *,
    kind: str,
    payload: dict[str, Any],
    run_after: datetime | None = None,
) -> OutboxJob:
    job = OutboxJob(
        id=new_uuid(),
        kind=kind,
        payload=payload,
        run_after=run_after or get_clock().now(),
    )
    session.add(job)
    await session.flush()
    return job
