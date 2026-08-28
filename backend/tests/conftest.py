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
    provided = os.environ.get("PICKONE_TEST_DATABASE_URL")
    if provided:
        yield provided
        return

    try:
        from testcontainers.community.postgres import PostgresContainer
    except ImportError:
        from testcontainers.postgres import PostgresContainer

    with PostgresContainer("postgres:16-alpine", driver="asyncpg") as pg:
        yield pg.get_connection_url()


@pytest.fixture(scope="session", autouse=True)
def _settings_env(database_url: str) -> Iterator[None]:
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
    command.upgrade(alembic_config, "head")


@pytest.fixture
async def engine(database_url: str, _migrated: None) -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(database_url, pool_pre_ping=True)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest.fixture
async def db_connection(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            yield conn
        finally:
            await trans.rollback()


@pytest.fixture
async def db_session(db_connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(
        bind=db_connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    ) as session:
        yield session


@pytest.fixture(autouse=True)
def _reset_circuit_breaker() -> Iterator[None]:
    from pickone.moderation.circuit_breaker import reset_circuit_breaker

    reset_circuit_breaker()
    yield
    reset_circuit_breaker()


@pytest.fixture(autouse=True)
async def _reset_app_engine_cache() -> AsyncIterator[None]:
    from pickone.db.engine import get_engine, get_sessionmaker

    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    yield
    get_sessionmaker.cache_clear()
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
    get_engine.cache_clear()


@pytest.fixture
async def client(
    db_session: AsyncSession, _reset_app_engine_cache: None
) -> AsyncIterator[AsyncClient]:
    from contextlib import asynccontextmanager

    from pickone.api.app import create_app
    from pickone.db.session import get_session

    @asynccontextmanager
    async def session_scope() -> AsyncIterator[AsyncSession]:
        yield db_session

    async def session_override() -> AsyncIterator[AsyncSession]:
        yield db_session

    app = create_app(session_scope=session_scope)
    app.dependency_overrides[get_session] = session_override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def frozen_clock() -> Iterator[object]:
    from pickone.core.clock import FrozenClock, SystemClock, set_clock

    clock = FrozenClock()
    set_clock(clock)
    yield clock
    set_clock(SystemClock())
