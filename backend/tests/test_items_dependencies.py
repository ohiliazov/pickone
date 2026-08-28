from __future__ import annotations

from typing import Annotated
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth.models import User
from pickone.auth.service import create_guest, register, verify
from pickone.core.errors import install_error_handlers
from pickone.core.models import OutboxJob
from pickone.db.session import get_session as real_get_session
from pickone.items.dependencies import item_author


async def _latest_email_token(db_session: AsyncSession, to: str) -> str:
    jobs = (
        (await db_session.execute(select(OutboxJob).order_by(OutboxJob.created_at.desc())))
        .scalars()
        .all()
    )
    job = next(j for j in jobs if j.payload.get("to") == to)
    url = job.payload["body"].split("\n\n")[1].strip()
    return str(parse_qs(urlparse(url).query)["token"][0])


@pytest.fixture
async def dep_app(db_session: AsyncSession) -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)
    app.dependency_overrides[real_get_session] = lambda: db_session

    @app.get("/add")
    async def add(actor: Annotated[User, Depends(item_author)]) -> dict[str, str]:
        return {"id": str(actor.id)}

    return app


@pytest.fixture
async def dep_client(dep_app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=dep_app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_no_session_at_all_gets_401_with_the_item_specific_copy(
    dep_client: AsyncClient,
) -> None:
    resp = await dep_client.get("/add")
    assert resp.status_code == 401
    body = resp.json()["error"]
    assert body["code"] == "account_required"
    assert body["message"] == "Make an account to add one."


async def test_guest_gets_401_with_the_item_specific_copy(
    dep_client: AsyncClient, db_session: AsyncSession
) -> None:
    _user, _session_row, raw_token = await create_guest(
        db_session, ip="1.1.1.1", user_agent="pytest"
    )
    dep_client.cookies.set("po_session", raw_token)

    resp = await dep_client.get("/add")
    assert resp.status_code == 401
    body = resp.json()["error"]
    assert body["code"] == "account_required"
    assert body["message"] == "Make an account to add one."


async def test_unverified_member_gets_403(
    dep_client: AsyncClient, db_session: AsyncSession
) -> None:
    reg = await register(
        db_session, email="itemdep1@b.com", password="correcthorse1", guest_token=None
    )
    dep_client.cookies.set("po_session", reg.raw_token)

    resp = await dep_client.get("/add")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "verification_required"


async def test_verified_member_passes_through(
    dep_client: AsyncClient, db_session: AsyncSession
) -> None:
    reg = await register(
        db_session, email="itemdep2@b.com", password="correcthorse1", guest_token=None
    )
    token = await _latest_email_token(db_session, "itemdep2@b.com")
    await verify(db_session, token=token)
    dep_client.cookies.set("po_session", reg.raw_token)

    resp = await dep_client.get("/add")
    assert resp.status_code == 200
    assert resp.json()["id"] == str(reg.user.id)
