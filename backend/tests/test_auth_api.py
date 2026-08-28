from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth.models import User
from pickone.core.config import get_settings
from pickone.core.models import OutboxJob


async def _latest_token(session: AsyncSession, to: str, marker: str) -> str:
    result = await session.execute(select(OutboxJob).order_by(OutboxJob.created_at.desc()))
    jobs = result.scalars().all()
    job = next(j for j in jobs if j.payload.get("to") == to and marker in j.payload["body"])
    url = job.payload["body"].split("\n\n")[1].strip()
    return str(parse_qs(urlparse(url).query)["token"][0])


async def test_me_exposes_is_admin(client: AsyncClient, db_session: AsyncSession) -> None:
    reg_resp = await client.post(
        "/api/auth/register",
        json={"email": "isadmin@b.com", "password": "correcthorse1"},
        headers={"Origin": get_settings().base_url},
    )
    assert reg_resp.json()["user"]["is_admin"] is False

    result = await db_session.execute(select(User).where(User.email == "isadmin@b.com"))
    user = result.scalar_one()
    user.is_admin = True
    await db_session.flush()

    me_resp = await client.get("/api/me")
    assert me_resp.json()["user"]["is_admin"] is True


async def test_me_items_remaining_today_reflects_real_usage(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    from datetime import timedelta

    from pickone.core.clock import get_clock

    origin = get_settings().base_url
    email = "itemsleft@b.com"
    reg_resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "correcthorse1"},
        headers={"Origin": origin},
    )
    csrf_token = reg_resp.json()["csrf_token"]

    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    user.created_at = get_clock().now() - timedelta(days=30)
    user.email_verified_at = get_clock().now()
    await db_session.flush()

    settings = get_settings()
    me_resp = await client.get("/api/me")
    assert me_resp.json()["limits"]["items_remaining_today"] == settings.rl_items_per_day_user

    await client.post(
        "/api/items",
        json={"text": "Something to add"},
        headers={"Origin": origin, "X-PickOne-CSRF": csrf_token},
    )

    me_resp_after = await client.get("/api/me")
    assert (
        me_resp_after.json()["limits"]["items_remaining_today"]
        == settings.rl_items_per_day_user - 1
    )


async def test_full_register_verify_login_logout_reset_login_delete_cycle(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    origin = get_settings().base_url

    reg_resp = await client.post(
        "/api/auth/register",
        json={"email": "e2e@b.com", "password": "correcthorse1"},
        headers={"Origin": origin},
    )
    assert reg_resp.status_code == 201
    reg_body = reg_resp.json()
    csrf_token = reg_body["csrf_token"]
    assert reg_body["user"]["email"] == "e2e@b.com"
    assert reg_body["user"]["email_verified"] is False
    assert "po_session" in client.cookies

    verify_token = await _latest_token(db_session, "e2e@b.com", "/verify?")
    verify_resp = await client.post(
        "/api/auth/verify",
        json={"token": verify_token},
        headers={"Origin": origin, "X-PickOne-CSRF": csrf_token},
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["user"]["email_verified"] is True

    logout_resp = await client.post(
        "/api/auth/logout", headers={"Origin": origin, "X-PickOne-CSRF": csrf_token}
    )
    assert logout_resp.status_code == 204

    me_after_logout = await client.get("/api/me")
    assert me_after_logout.status_code == 401

    login_resp = await client.post(
        "/api/auth/login",
        json={"email": "e2e@b.com", "password": "correcthorse1"},
        headers={"Origin": origin},
    )
    assert login_resp.status_code == 200
    me_resp = await client.get("/api/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["user"]["email"] == "e2e@b.com"
    assert me_resp.json()["csrf_token"]

    reset_req_resp = await client.post(
        "/api/auth/password-reset/request",
        json={"email": "e2e@b.com"},
        headers={"Origin": origin},
    )
    assert reset_req_resp.status_code == 202

    stale_cookie = client.cookies.get("po_session")

    reset_token = await _latest_token(db_session, "e2e@b.com", "/reset?")
    reset_confirm_resp = await client.post(
        "/api/auth/password-reset/confirm",
        json={"token": reset_token, "password": "brandnewpass1"},
        headers={"Origin": origin},
    )
    assert reset_confirm_resp.status_code == 200
    assert client.cookies.get("po_session") != stale_cookie

    old_session_me = await client.get("/api/me", headers={"Cookie": f"po_session={stale_cookie}"})
    assert old_session_me.status_code == 401

    relogin_resp = await client.post(
        "/api/auth/login",
        json={"email": "e2e@b.com", "password": "brandnewpass1"},
        headers={"Origin": origin},
    )
    assert relogin_resp.status_code == 200
    final_csrf = relogin_resp.json()["csrf_token"]

    delete_resp = await client.post(
        "/api/me/delete", headers={"Origin": origin, "X-PickOne-CSRF": final_csrf}
    )
    assert delete_resp.status_code == 204

    me_after_delete = await client.get("/api/me")
    assert me_after_delete.status_code == 401


async def test_register_without_csrf_allowlist_needs_no_header(client: AsyncClient) -> None:
    origin = get_settings().base_url
    resp = await client.post(
        "/api/auth/register",
        json={"email": "noheader@b.com", "password": "correcthorse1"},
        headers={"Origin": origin},
    )
    assert resp.status_code == 201


async def test_mutating_route_without_csrf_header_is_rejected(client: AsyncClient) -> None:
    origin = get_settings().base_url
    await client.post(
        "/api/auth/register",
        json={"email": "nohdr2@b.com", "password": "correcthorse1"},
        headers={"Origin": origin},
    )
    resp = await client.post("/api/auth/logout", headers={"Origin": origin})
    assert resp.status_code == 403


async def test_duplicate_registration_returns_409(client: AsyncClient) -> None:
    origin = get_settings().base_url
    await client.post(
        "/api/auth/register",
        json={"email": "dupe@b.com", "password": "correcthorse1"},
        headers={"Origin": origin},
    )
    client.cookies.clear()
    resp = await client.post(
        "/api/auth/register",
        json={"email": "dupe@b.com", "password": "anotherpass1"},
        headers={"Origin": origin},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "email_taken"


async def test_login_with_wrong_password_returns_401(client: AsyncClient) -> None:
    origin = get_settings().base_url
    await client.post(
        "/api/auth/register",
        json={"email": "wrongpw@b.com", "password": "correcthorse1"},
        headers={"Origin": origin},
    )
    client.cookies.clear()
    resp = await client.post(
        "/api/auth/login",
        json={"email": "wrongpw@b.com", "password": "wrongwrong"},
        headers={"Origin": origin},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "invalid_credentials"


async def test_verify_link_works_with_no_csrf_token_in_hand(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    origin = get_settings().base_url
    await client.post(
        "/api/auth/register",
        json={"email": "freshlink@b.com", "password": "correcthorse1"},
        headers={"Origin": origin},
    )

    token = await _latest_token(db_session, "freshlink@b.com", "/verify?")
    resp = await client.post(
        "/api/auth/verify",
        json={"token": token},
        headers={"Origin": origin},
    )
    assert resp.status_code == 200
