from __future__ import annotations

from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth.models import User
from pickone.core import ratelimit
from pickone.core.clock import get_clock
from pickone.core.config import get_settings
from pickone.core.security import hash_ip
from pickone.items import normalize, repository, validation
from pickone.items.errors import AlreadyExistsError, AlreadyReportedError, RejectedError
from pickone.items.models import Item
from pickone.items.slugs import slugify
from pickone.moderation import repository as moderation_repository
from pickone.moderation import service as moderation_service
from pickone.moderation.provider import ModerationProvider
from pickone.moderation.starter_blocklist import contains_blocked_term


async def _insert_or_raise_already_exists(
    session: AsyncSession, *, text: str, normalized: str, base_slug: str, user_id: str
) -> Item:
    try:
        return await repository.insert_item_with_unique_slug(
            session,
            text=text,
            normalized_text=normalized,
            base_slug=base_slug,
            created_by_user_id=user_id,
        )
    except repository.NormalizedTextCollisionError as exc:
        existing = await repository.get_item_by_normalized_text(session, normalized)
        if existing is None:
            raise
        raise AlreadyExistsError(details={"slug": existing.slug}) from exc


def effective_daily_item_limit(user: User, *, now: datetime) -> int:
    settings = get_settings()
    account_age_hours = (now - user.created_at).total_seconds() / 3600
    if account_age_hours < settings.new_account_age_hours:
        return settings.rl_items_per_day_new_account
    return settings.rl_items_per_day_user


def daily_rate_limit_key(user: User) -> str:
    return f"items:day:{user.id}"


async def create_item(
    session: AsyncSession,
    *,
    user: User,
    text: str,
    ip: str | None = None,
    provider: ModerationProvider | None = None,
) -> Item:
    settings = get_settings()
    clock = get_clock()
    now = clock.now()

    await ratelimit.enforce(
        session,
        f"items:hour:{user.id}",
        limit=settings.rl_items_per_hour_user,
        window_seconds=3600,
    )

    daily_limit = effective_daily_item_limit(user, now=now)
    await ratelimit.enforce(
        session, daily_rate_limit_key(user), limit=daily_limit, window_seconds=86400
    )

    if ip is not None:
        await ratelimit.enforce(
            session,
            f"items:day_ip:{hash_ip(ip).hex()}",
            limit=settings.rl_items_per_day_ip,
            window_seconds=86400,
        )

    display = normalize.display_text(text)
    validation.validate_structure(display)
    normalized = normalize.normalized_text(display)

    existing = await repository.get_item_by_normalized_text(session, normalized)
    if existing is not None:
        raise AlreadyExistsError(details={"slug": existing.slug})

    base_slug = slugify(display)

    if contains_blocked_term(display):
        item = await _insert_or_raise_already_exists(
            session, text=display, normalized=normalized, base_slug=base_slug, user_id=user.id
        )
        await moderation_repository.create_moderation_result(
            session,
            item_id=item.id,
            provider="blocklist",
            model=None,
            decision="REJECTED",
            scores={},
            raw_response=None,
            policy_version=settings.moderation_policy_version,
            latency_ms=None,
        )
        await repository.set_item_status(session, item, status="REJECTED")
        raise RejectedError()

    item = await _insert_or_raise_already_exists(
        session, text=display, normalized=normalized, base_slug=base_slug, user_id=user.id
    )

    outcome = await moderation_service.moderate(
        session, item_id=item.id, text=display, provider=provider
    )

    if outcome.decision == "APPROVED":
        await repository.set_item_status(session, item, status="APPROVED", published_at=now)
    elif outcome.decision == "REJECTED":
        await repository.set_item_status(session, item, status="REJECTED")
        raise RejectedError()
    else:
        await repository.set_item_status(session, item, status="REVIEW")

    return item


async def report_item(
    session: AsyncSession, *, item: Item, reporter_user_id: str, reason: str
) -> None:
    settings = get_settings()
    try:
        async with session.begin_nested():
            await repository.create_report(
                session, item_id=item.id, reporter_user_id=reporter_user_id, reason=reason
            )
    except IntegrityError as exc:
        raise AlreadyReportedError() from exc

    count = await repository.count_distinct_reporters(session, item.id)
    if count >= settings.auto_hide_report_count:
        await repository.set_item_status(session, item, status="HIDDEN")


async def apply_moderation_decision(
    session: AsyncSession, *, item: Item, decision: str, reviewed_by_user_id: str
) -> None:
    settings = get_settings()
    now = get_clock().now()

    await moderation_repository.create_moderation_result(
        session,
        item_id=item.id,
        provider="admin",
        model=None,
        decision=decision,
        scores={},
        raw_response=None,
        policy_version=settings.moderation_policy_version,
        latency_ms=None,
        reviewed_by_user_id=reviewed_by_user_id,
    )
    published_at = now if decision == "APPROVED" else None
    await repository.set_item_status(session, item, status=decision, published_at=published_at)
