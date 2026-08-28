from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from pickone.core.config import get_settings
from pickone.moderation.circuit_breaker import get_circuit_breaker
from pickone.moderation.policy import POLICY_V1, decide
from pickone.moderation.provider import ModerationProvider, build_provider
from pickone.moderation.repository import create_moderation_result


@dataclass(frozen=True)
class ModerationOutcome:
    decision: str
    provider: str
    model: str | None
    scores: dict[str, float]
    raw: dict[str, Any] | None
    latency_ms: int


async def moderate(
    session: AsyncSession,
    *,
    item_id: str,
    text: str,
    provider: ModerationProvider | None = None,
) -> ModerationOutcome:
    settings = get_settings()
    active_provider = provider or build_provider()
    breaker = get_circuit_breaker()
    provider_name = type(active_provider).__name__

    started = time.monotonic()
    decision = "ERROR"
    model: str | None = None
    scores: dict[str, float] = {}
    raw: dict[str, Any] | None = None

    if breaker.is_open():
        provider_name = "circuit_breaker"
    else:
        try:
            result = await asyncio.wait_for(
                active_provider.check(text), timeout=settings.moderation_timeout_ms / 1000
            )
        except Exception:
            breaker.record_failure()
        else:
            breaker.record_success()
            decision = decide(result.scores, POLICY_V1)
            model = result.model
            scores = result.scores
            raw = result.raw

    latency_ms = int((time.monotonic() - started) * 1000)

    await create_moderation_result(
        session,
        item_id=item_id,
        provider=provider_name,
        model=model,
        decision=decision,
        scores=scores,
        raw_response=raw,
        policy_version=settings.moderation_policy_version,
        latency_ms=latency_ms,
    )

    return ModerationOutcome(
        decision=decision,
        provider=provider_name,
        model=model,
        scores=scores,
        raw=raw,
        latency_ms=latency_ms,
    )
