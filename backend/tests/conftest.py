"""The test harness.

The single most important thing in M0: every correctness property that matters
in this system is enforced by Postgres, so a suite that mocks the database
tests nothing ([SPEC §16.1]). These fixtures make a real database cheap enough
that nobody is ever tempted.

Two modes:
  * ``PICKONE_TEST_DATABASE_URL`` set  -> use that database (CI service container)
  * otherwise                          -> start one with testcontainers (local)
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, create_async_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    """A live Postgres, however we can get one."""
    provided = os.environ.get("PICKONE_TEST_DATABASE_URL")
    if provided:
        yield provided
        return

    try:  # testcontainers >= 4.14 moved the module
        from testcontainers.community.postgres import PostgresContainer
    except ImportError:  # pragma: no cover - older testcontainers
        from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine", driver="asyncpg") as pg:
        yield pg.get_connection_url()


@pytest.fixture(scope="session", autouse=True)
def _settings_env(database_url: str) -> Iterator[None]:
    """Point the config register at the test database before anything imports it."""
    os.environ["PICKONE_ENV"] = "test"
    os.environ["PICKONE_DATABASE_URL"] = database_url
    from pickone.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def alembic_config(database_url: str) -> Config:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "src/pickone/db/migrations"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


@pytest.fixture(scope="session", autouse=True)
def _migrated(alembic_config: Config, _settings_env: None) -> None:
    """Run migrations from empty, once per session.

    Migrating rather than ``create_all`` is deliberate: it means every test run
    exercises the same path production does.
    """
    command.upgrade(alembic_config, "head")


@pytest.fixture
async def engine(database_url: str, _migrated: None) -> AsyncIterator[AsyncEngine]:
    """Function-scoped on purpose.

    A session-scoped engine binds its connections to the event loop that created
    them, and pytest-asyncio gives each test its own loop — which surfaces as
    "attached to a different loop" the moment a second test touches the pool.
    Creating an engine is cheap (the pool connects lazily), so scoping it per
    test buys determinism for almost nothing. The expensive things — the
    container and the migrations — stay session-scoped.
    """
    eng = create_async_engine(database_url, pool_pre_ping=True)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest.fixture
async def db_connection(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """An outer transaction that is always rolled back.

    Tests get a real database with real constraints and leave no trace.
    """
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            yield conn
        finally:
            await trans.rollback()


@pytest.fixture
async def db_session(db_connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(bind=db_connection, expire_on_commit=False) as session:
        yield session


@pytest.fixture
async def client(_migrated: None) -> AsyncIterator[AsyncClient]:
    """An HTTP client bound to the app in-process. No network, no ports."""
    from pickone.api.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def frozen_clock() -> Iterator[object]:
    """Install a clock the test controls, and restore the real one after."""
    from pickone.core.clock import FrozenClock, SystemClock, set_clock

    clock = FrozenClock()
    set_clock(clock)
    yield clock
    set_clock(SystemClock())
