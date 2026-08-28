from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth.models import User
from pickone.core.models import OutboxJob
from pickone.moderation.circuit_breaker import get_circuit_breaker
from pickone.moderation.models import ModerationResult

ORIGIN = "http://localhost:3100"


async def _latest_token(session: AsyncSession, to: str, marker: str) -> str:
    result = await session.execute(select(OutboxJob).order_by(OutboxJob.created_at.desc()))
    jobs = result.scalars().all()
    job = next(j for j in jobs if j.payload.get("to") == to and marker in j.payload["body"])
    url = job.payload["body"].split("\n\n")[1].strip()
    return str(parse_qs(urlparse(url).query)["token"][0])


async def _verified_member(
    client: AsyncClient, db_session: AsyncSession, email: str
) -> tuple[str, str]:
    reg_resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "correcthorse1"},
        headers={"Origin": ORIGIN},
    )
    csrf_token = reg_resp.json()["csrf_token"]
    verify_token = await _latest_token(db_session, email, "/verify?")
    await client.post(
        "/api/auth/verify",
        json={"token": verify_token},
        headers={"Origin": ORIGIN, "X-PickOne-CSRF": csrf_token},
    )
    raw_token = client.cookies.get("po_session")
    assert raw_token is not None
    return str(csrf_token), str(raw_token)


def _switch_to(client: AsyncClient, raw_token: str) -> None:
    client.cookies.set("po_session", raw_token)


async def _make_admin(db_session: AsyncSession, email: str) -> None:
    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    user.is_admin = True
    await db_session.flush()


def _open_circuit_breaker() -> None:
    breaker = get_circuit_breaker()
    for _ in range(20):
        breaker.record_failure()


async def test_non_admin_gets_404_on_queue(client: AsyncClient, db_session: AsyncSession) -> None:
    csrf_token, _ = await _verified_member(client, db_session, "notadmin1@b.com")
    resp = await client.get(
        "/api/admin/moderation/queue", headers={"Origin": ORIGIN, "X-PickOne-CSRF": csrf_token}
    )
    assert resp.status_code == 404


async def test_non_admin_gets_404_on_reports(client: AsyncClient, db_session: AsyncSession) -> None:
    csrf_token, _ = await _verified_member(client, db_session, "notadmin2@b.com")
    resp = await client.get(
        "/api/admin/reports", headers={"Origin": ORIGIN, "X-PickOne-CSRF": csrf_token}
    )
    assert resp.status_code == 404


async def test_non_admin_gets_404_on_decision(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    csrf_token, _ = await _verified_member(client, db_session, "notadmin3@b.com")
    resp = await client.post(
        "/api/admin/items/00000000-0000-0000-0000-000000000000/decision",
        json={"decision": "APPROVED"},
        headers={"Origin": ORIGIN, "X-PickOne-CSRF": csrf_token},
    )
    assert resp.status_code == 404


async def test_admin_queue_lists_review_items_oldest_first(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    creator_csrf, creator_token = await _verified_member(client, db_session, "creator-admin1@b.com")
    admin_csrf, admin_token = await _verified_member(client, db_session, "admin1@b.com")
    await _make_admin(db_session, "admin1@b.com")
    _open_circuit_breaker()

    _switch_to(client, creator_token)
    await client.post(
        "/api/items",
        json={"text": "First item forced to review"},
        headers={"Origin": ORIGIN, "X-PickOne-CSRF": creator_csrf},
    )
    await client.post(
        "/api/items",
        json={"text": "Second item forced to review"},
        headers={"Origin": ORIGIN, "X-PickOne-CSRF": creator_csrf},
    )

    _switch_to(client, admin_token)
    resp = await client.get(
        "/api/admin/moderation/queue", headers={"Origin": ORIGIN, "X-PickOne-CSRF": admin_csrf}
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 2
    assert all(i["status"] == "REVIEW" for i in items)
    assert items[0]["text"] == "First item forced to review"
    assert items[1]["text"] == "Second item forced to review"


async def test_admin_approves_an_item_in_review(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    creator_csrf, creator_token = await _verified_member(client, db_session, "creator-admin2@b.com")
    admin_csrf, admin_token = await _verified_member(client, db_session, "admin2@b.com")
    await _make_admin(db_session, "admin2@b.com")
    _open_circuit_breaker()

    _switch_to(client, creator_token)
    create_resp = await client.post(
        "/api/items",
        json={"text": "Some item forced to review"},
        headers={"Origin": ORIGIN, "X-PickOne-CSRF": creator_csrf},
    )
    item_id = create_resp.json()["item"]["id"]

    _switch_to(client, admin_token)
    resp = await client.post(
        f"/api/admin/items/{item_id}/decision",
        json={"decision": "APPROVED"},
        headers={"Origin": ORIGIN, "X-PickOne-CSRF": admin_csrf},
    )
    assert resp.status_code == 200
    assert resp.json()["item"]["status"] == "APPROVED"

    rows = (
        (
            await db_session.execute(
                select(ModerationResult).where(ModerationResult.item_id == item_id)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2
    admin_rows = [r for r in rows if r.provider == "admin"]
    assert len(admin_rows) == 1
    assert admin_rows[0].decision == "APPROVED"


async def test_reports_endpoint_groups_by_item(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    creator_csrf, creator_token = await _verified_member(client, db_session, "creator-admin3@b.com")
    reporter_csrf, reporter_token = await _verified_member(
        client, db_session, "reporter-admin3@b.com"
    )
    admin_csrf, admin_token = await _verified_member(client, db_session, "admin3@b.com")
    await _make_admin(db_session, "admin3@b.com")

    _switch_to(client, creator_token)
    await client.post(
        "/api/items",
        json={"text": "Reported via admin test"},
        headers={"Origin": ORIGIN, "X-PickOne-CSRF": creator_csrf},
    )

    _switch_to(client, reporter_token)
    await client.post(
        "/api/items/reported-via-admin-test/report",
        json={"reason": "spam"},
        headers={"Origin": ORIGIN, "X-PickOne-CSRF": reporter_csrf},
    )

    _switch_to(client, admin_token)
    resp = await client.get(
        "/api/admin/reports", headers={"Origin": ORIGIN, "X-PickOne-CSRF": admin_csrf}
    )
    assert resp.status_code == 200
    groups = resp.json()["reports"]
    assert len(groups) == 1
    assert groups[0]["item"]["slug"] == "reported-via-admin-test"
    assert len(groups[0]["reports"]) == 1
    assert groups[0]["reports"][0]["reason"] == "spam"
