from __future__ import annotations

from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth.dependencies import (
    admin_user,
    current_actor,
    registered_user,
    required_actor,
    required_session,
    verified_user,
)
from pickone.auth.models import Session, User
from pickone.auth.service import create_guest, register
from pickone.core.errors import install_error_handlers
from pickone.db.session import get_session as real_get_session


@pytest.fixture
async def dep_app(db_session: AsyncSession) -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)
    app.dependency_overrides[real_get_session] = lambda: db_session

    @app.get("/tier1")
    async def tier1(actor: Annotated[User | None, Depends(current_actor)]) -> dict[str, bool]:
        return {"is_none": actor is None}

    @app.get("/tier2")
    async def tier2(actor: Annotated[User, Depends(required_actor)]) -> dict[str, str]:
        return {"id": str(actor.id)}

    @app.get("/tier3")
    async def tier3(actor: Annotated[User, Depends(registered_user)]) -> dict[str, str]:
        return {"id": str(actor.id)}

    @app.get("/tier4")
    async def tier4(actor: Annotated[User, Depends(verified_user)]) -> dict[str, str]:
        return {"id": str(actor.id)}

    @app.get("/tier5")
    async def tier5(actor: Annotated[User, Depends(admin_user)]) -> dict[str, str]:
        return {"id": str(actor.id)}

    @app.get("/session")
    async def session_route(
        row: Annotated[Session, Depends(required_session)],
    ) -> dict[str, str]:
        return {"id": str(row.id)}

    return app


@pytest.fixture
async def dep_client(dep_app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=dep_app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_tier1_allows_no_cookie(dep_client: AsyncClient) -> None:
    resp = await dep_client.get("/tier1")
    assert resp.status_code == 200
    assert resp.json() == {"is_none": True}


async def test_tier2_rejects_no_cookie(dep_client: AsyncClient) -> None:
    resp = await dep_client.get("/tier2")
    assert resp.status_code == 401


async def test_tier2_accepts_a_guest(dep_client: AsyncClient, db_session: AsyncSession) -> None:
    _user, _session_row, raw_token = await create_guest(
        db_session, ip="1.1.1.1", user_agent="pytest"
    )
    dep_client.cookies.set("po_session", raw_token)

    resp = await dep_client.get("/tier2")
    assert resp.status_code == 200


async def test_tier3_rejects_a_guest(dep_client: AsyncClient, db_session: AsyncSession) -> None:
    _user, _session_row, raw_token = await create_guest(
        db_session, ip="1.1.1.2", user_agent="pytest"
    )
    dep_client.cookies.set("po_session", raw_token)

    resp = await dep_client.get("/tier3")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "account_required"


async def test_tier3_accepts_an_unverified_member(
    dep_client: AsyncClient, db_session: AsyncSession
) -> None:
    reg = await register(db_session, email="dep1@b.com", password="correcthorse1", guest_token=None)
    dep_client.cookies.set("po_session", reg.raw_token)

    resp = await dep_client.get("/tier3")
    assert resp.status_code == 200


async def test_tier4_rejects_an_unverified_member(
    dep_client: AsyncClient, db_session: AsyncSession
) -> None:
    reg = await register(db_session, email="dep2@b.com", password="correcthorse1", guest_token=None)
    dep_client.cookies.set("po_session", reg.raw_token)

    resp = await dep_client.get("/tier4")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "verification_required"


async def test_tier5_rejects_a_non_admin_with_404(
    dep_client: AsyncClient, db_session: AsyncSession
) -> None:
    reg = await register(db_session, email="dep3@b.com", password="correcthorse1", guest_token=None)
    dep_client.cookies.set("po_session", reg.raw_token)

    resp = await dep_client.get("/tier5")
    assert resp.status_code == 404


async def test_required_session_exposes_the_session_row(
    dep_client: AsyncClient, db_session: AsyncSession
) -> None:
    reg = await register(db_session, email="dep4@b.com", password="correcthorse1", guest_token=None)
    dep_client.cookies.set("po_session", reg.raw_token)

    resp = await dep_client.get("/session")

    assert resp.status_code == 200
    assert resp.json()["id"] == str(reg.session_row.id)


async def test_required_session_rejects_no_cookie(dep_client: AsyncClient) -> None:
    resp = await dep_client.get("/session")
    assert resp.status_code == 401
