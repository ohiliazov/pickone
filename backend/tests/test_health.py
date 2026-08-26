"""Liveness and readiness. [M0 acceptance #1]"""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient


async def test_healthz_is_ok(client: AsyncClient) -> None:
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_healthz_does_not_touch_the_database() -> None:
    """A database blip must not restart healthy API containers."""
    from pickone.api.app import create_app
    from pickone.api.routers.health import engine_dependency
    from pickone.db.session import get_session

    app = create_app()

    def _explode() -> None:
        raise AssertionError("/healthz must not touch the database")

    app.dependency_overrides[get_session] = _explode
    app.dependency_overrides[engine_dependency] = _explode
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        assert (await ac.get("/healthz")).status_code == 200


async def test_readyz_is_ready(client: AsyncClient) -> None:
    resp = await client.get("/readyz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready", "database": "ok"}


async def test_readyz_reports_not_ready_when_the_database_is_unreachable() -> None:
    """503, never 500.

    A readiness probe that returns "server error" when the database is down
    makes a load balancer page someone instead of draining the pod.
    """
    from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

    from pickone.api.app import create_app
    from pickone.api.routers.health import engine_dependency

    app = create_app()
    dead = create_async_engine("postgresql+asyncpg://nobody@127.0.0.1:1/none")

    def _dead_engine() -> AsyncEngine:
        return dead

    app.dependency_overrides[engine_dependency] = _dead_engine
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        resp = await ac.get("/readyz")
    await dead.dispose()

    assert resp.status_code == 503, "an unreachable database must not surface as 500"
    assert resp.json() == {"status": "not_ready", "database": "unreachable"}


async def test_request_id_is_echoed(client: AsyncClient) -> None:
    resp = await client.get("/healthz", headers={"X-Request-ID": "abc123"})
    assert resp.headers["X-Request-ID"] == "abc123"


async def test_request_id_is_minted_when_absent(client: AsyncClient) -> None:
    resp = await client.get("/healthz")
    assert len(resp.headers["X-Request-ID"]) == 32
