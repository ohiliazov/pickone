from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth.service import create_guest, register
from pickone.core.config import get_settings
from pickone.core.errors import install_error_handlers
from pickone.db.session import get_session as real_get_session


@pytest.fixture
async def csrf_app(db_session: AsyncSession) -> FastAPI:
    from collections.abc import AsyncIterator
    from contextlib import asynccontextmanager

    from pickone.api.csrf import CSRFMiddleware

    @asynccontextmanager
    async def session_scope() -> AsyncIterator[AsyncSession]:
        yield db_session

    app = FastAPI()
    install_error_handlers(app)
    app.add_middleware(CSRFMiddleware, session_scope=session_scope)
    app.dependency_overrides[real_get_session] = lambda: db_session

    @app.post("/api/auth/login")
    async def login_route() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/api/newly-added-unsafe-route")
    async def unlisted_route() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/api/safe")
    async def safe_route() -> dict[str, bool]:
        return {"ok": True}

    return app


@pytest.fixture
async def csrf_client(csrf_app: FastAPI) -> AsyncClient:
    origin = get_settings().base_url
    transport = ASGITransport(app=csrf_app)
    return AsyncClient(transport=transport, base_url="http://test", headers={"Origin": origin})


async def test_get_needs_no_csrf_header(csrf_client: AsyncClient) -> None:
    resp = await csrf_client.get("/api/safe")
    assert resp.status_code == 200


async def test_allowlisted_login_route_needs_no_csrf_header(csrf_client: AsyncClient) -> None:
    resp = await csrf_client.post("/api/auth/login")
    assert resp.status_code == 200


async def test_new_unsafe_route_is_denied_by_default(csrf_client: AsyncClient) -> None:
    resp = await csrf_client.post("/api/newly-added-unsafe-route")
    assert resp.status_code == 403


async def test_missing_origin_is_rejected_even_for_allowlisted_route() -> None:
    from pickone.api.csrf import CSRFMiddleware

    app = FastAPI()
    install_error_handlers(app)
    app.add_middleware(CSRFMiddleware)

    @app.post("/api/auth/login")
    async def login_route() -> dict[str, bool]:
        return {"ok": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/auth/login")

    assert resp.status_code == 403


async def test_foreign_origin_is_rejected(csrf_client: AsyncClient) -> None:
    resp = await csrf_client.post(
        "/api/newly-added-unsafe-route", headers={"Origin": "https://evil.example.com"}
    )
    assert resp.status_code == 403


async def test_valid_session_without_csrf_header_is_rejected(
    csrf_client: AsyncClient, db_session: AsyncSession
) -> None:
    _user, _session_row, raw_token = await create_guest(
        db_session, ip="8.8.8.1", user_agent="pytest"
    )
    csrf_client.cookies.set("po_session", raw_token)

    resp = await csrf_client.post("/api/newly-added-unsafe-route")
    assert resp.status_code == 403


async def test_valid_session_with_correct_csrf_header_is_accepted(
    csrf_client: AsyncClient, db_session: AsyncSession
) -> None:
    from pickone.core.security import derive_csrf_token

    reg = await register(
        db_session, email="csrf1@b.com", password="correcthorse1", guest_token=None
    )
    csrf_client.cookies.set("po_session", reg.raw_token)
    token = derive_csrf_token(reg.session_row.csrf_secret, str(reg.session_row.id))

    resp = await csrf_client.post(
        "/api/newly-added-unsafe-route", headers={"X-PickOne-CSRF": token}
    )
    assert resp.status_code == 200


async def test_valid_session_with_wrong_csrf_header_is_rejected(
    csrf_client: AsyncClient, db_session: AsyncSession
) -> None:
    reg = await register(
        db_session, email="csrf2@b.com", password="correcthorse1", guest_token=None
    )
    csrf_client.cookies.set("po_session", reg.raw_token)

    resp = await csrf_client.post(
        "/api/newly-added-unsafe-route", headers={"X-PickOne-CSRF": "not-the-right-token"}
    )
    assert resp.status_code == 403
