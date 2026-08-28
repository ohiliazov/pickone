from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth.service import create_guest
from pickone.core.config import get_settings
from pickone.core.models import OutboxJob
from pickone.core.security import derive_csrf_token

ORIGIN = "http://localhost:3100"


async def _latest_token(session: AsyncSession, to: str, marker: str) -> str:
    result = await session.execute(select(OutboxJob).order_by(OutboxJob.created_at.desc()))
    jobs = result.scalars().all()
    job = next(j for j in jobs if j.payload.get("to") == to and marker in j.payload["body"])
    url = job.payload["body"].split("\n\n")[1].strip()
    return str(parse_qs(urlparse(url).query)["token"][0])


async def _verified_member(client: AsyncClient, db_session: AsyncSession, email: str) -> str:
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
    return str(csrf_token)


async def test_approved_item_returns_201_with_added_copy(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    csrf_token = await _verified_member(client, db_session, "creator1@b.com")
    resp = await client.post(
        "/api/items",
        json={"text": "Carbonara"},
        headers={"Origin": ORIGIN, "X-PickOne-CSRF": csrf_token},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["message"] == "Added."
    assert body["item"]["status"] == "APPROVED"
    assert body["item"]["slug"] == "carbonara"


async def test_duplicate_item_returns_409(client: AsyncClient, db_session: AsyncSession) -> None:
    csrf_token = await _verified_member(client, db_session, "creator2@b.com")
    await client.post(
        "/api/items",
        json={"text": "Pizza"},
        headers={"Origin": ORIGIN, "X-PickOne-CSRF": csrf_token},
    )
    resp = await client.post(
        "/api/items",
        json={"text": "PIZZA!!"},
        headers={"Origin": ORIGIN, "X-PickOne-CSRF": csrf_token},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "already_exists"
    assert resp.json()["error"]["details"]["slug"] == "pizza"


async def test_too_long_text_returns_422_invalid_text(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    csrf_token = await _verified_member(client, db_session, "creator3@b.com")
    resp = await client.post(
        "/api/items",
        json={"text": "a" * 65},
        headers={"Origin": ORIGIN, "X-PickOne-CSRF": csrf_token},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "invalid_text"
    assert resp.json()["error"]["details"]["reason"] == "too_long"


async def test_blocklisted_text_returns_422_rejected_with_no_details(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    csrf_token = await _verified_member(client, db_session, "creator4@b.com")
    resp = await client.post(
        "/api/items",
        json={"text": "kill yourself now"},
        headers={"Origin": ORIGIN, "X-PickOne-CSRF": csrf_token},
    )
    assert resp.status_code == 422
    body = resp.json()["error"]
    assert body["code"] == "rejected"
    assert body["message"] == "We can't add that one."
    assert body["details"] == {}


async def test_no_session_gets_403_from_csrf_before_any_route_logic(
    client: AsyncClient,
) -> None:
    resp = await client.post("/api/items", json={"text": "Anything"}, headers={"Origin": ORIGIN})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "csrf_failed"


async def test_guest_with_a_real_session_gets_401_account_required(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    _user, session_row, raw_token = await create_guest(
        db_session, ip="1.1.1.1", user_agent="pytest"
    )
    client.cookies.set("po_session", raw_token)
    csrf_token = derive_csrf_token(session_row.csrf_secret, str(session_row.id))

    resp = await client.post(
        "/api/items",
        json={"text": "Anything"},
        headers={"Origin": ORIGIN, "X-PickOne-CSRF": csrf_token},
    )
    assert resp.status_code == 401
    body = resp.json()["error"]
    assert body["code"] == "account_required"
    assert body["message"] == "Make an account to add one."


async def test_unverified_member_gets_403(client: AsyncClient, db_session: AsyncSession) -> None:
    reg_resp = await client.post(
        "/api/auth/register",
        json={"email": "unverified@b.com", "password": "correcthorse1"},
        headers={"Origin": ORIGIN},
    )
    csrf_token = reg_resp.json()["csrf_token"]
    resp = await client.post(
        "/api/items",
        json={"text": "Anything"},
        headers={"Origin": ORIGIN, "X-PickOne-CSRF": csrf_token},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "verification_required"


async def test_get_approved_item_by_slug(client: AsyncClient, db_session: AsyncSession) -> None:
    csrf_token = await _verified_member(client, db_session, "creator5@b.com")
    await client.post(
        "/api/items",
        json={"text": "Spaghetti alla Carbonara"},
        headers={"Origin": ORIGIN, "X-PickOne-CSRF": csrf_token},
    )
    resp = await client.get("/api/items/spaghetti-alla-carbonara")
    assert resp.status_code == 200
    body = resp.json()
    assert body["text"] == "Spaghetti alla Carbonara"
    assert body["rank"] is None
    assert body["ranked"] is False
    assert "rivals" not in body


async def test_get_unknown_slug_returns_404(client: AsyncClient) -> None:
    resp = await client.get("/api/items/does-not-exist")
    assert resp.status_code == 404


async def test_script_tag_and_quotes_round_trip_safely(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    csrf_token = await _verified_member(client, db_session, "creator6@b.com")
    text = "<script>alert(1)</script> \"quoted\" 'stuff'"
    create_resp = await client.post(
        "/api/items",
        json={"text": text},
        headers={"Origin": ORIGIN, "X-PickOne-CSRF": csrf_token},
    )
    assert create_resp.status_code in (201, 202)
    slug = create_resp.json()["item"]["slug"]

    get_resp = await client.get(f"/api/items/{slug}")
    if get_resp.status_code == 200:
        assert get_resp.json()["text"] == text


async def test_report_an_item_then_duplicate_report_conflicts(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    creator_csrf = await _verified_member(client, db_session, "creator7@b.com")
    await client.post(
        "/api/items",
        json={"text": "Reportable item"},
        headers={"Origin": ORIGIN, "X-PickOne-CSRF": creator_csrf},
    )

    reporter_csrf = await _verified_member(client, db_session, "reporter1@b.com")
    resp = await client.post(
        "/api/items/reportable-item/report",
        json={"reason": "spam"},
        headers={"Origin": ORIGIN, "X-PickOne-CSRF": reporter_csrf},
    )
    assert resp.status_code == 202

    dup_resp = await client.post(
        "/api/items/reportable-item/report",
        json={"reason": "spam again"},
        headers={"Origin": ORIGIN, "X-PickOne-CSRF": reporter_csrf},
    )
    assert dup_resp.status_code == 409
    assert dup_resp.json()["error"]["code"] == "already_reported"


async def test_report_without_a_session_gets_403_from_csrf(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/items/whatever/report",
        json={"reason": "spam"},
        headers={"Origin": ORIGIN},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "csrf_failed"


async def test_rate_limited_creation_returns_429(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    csrf_token = await _verified_member(client, db_session, "creator8@b.com")
    limit = get_settings().rl_items_per_hour_user
    for n in range(limit):
        resp = await client.post(
            "/api/items",
            json={"text": f"Rate limit item {n}"},
            headers={"Origin": ORIGIN, "X-PickOne-CSRF": csrf_token},
        )
        assert resp.status_code in (201, 202)
    over_resp = await client.post(
        "/api/items",
        json={"text": "One too many item"},
        headers={"Origin": ORIGIN, "X-PickOne-CSRF": csrf_token},
    )
    assert over_resp.status_code == 429
    assert over_resp.json()["error"]["code"] == "rate_limited"
