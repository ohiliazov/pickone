from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from pickone import __version__
from pickone.api.csrf import CSRFMiddleware, SessionScope
from pickone.api.middleware import RequestIdMiddleware
from pickone.api.routers import auth, health
from pickone.core.config import Env, Settings, get_settings
from pickone.core.errors import install_error_handlers
from pickone.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = get_settings()
    logger.info("api_starting", env=settings.env.value, version=__version__)
    yield
    logger.info("api_stopping")


def create_app(
    settings: Settings | None = None, *, session_scope: SessionScope | None = None
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(
        level=settings.log_level,
        json_output=settings.env is not Env.LOCAL,
    )

    app = FastAPI(
        title="PickOne",
        version=__version__,
        lifespan=lifespan,
        docs_url=None if settings.env.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.env.is_production else "/openapi.json",
    )
    if session_scope is not None:
        app.add_middleware(CSRFMiddleware, session_scope=session_scope)
    else:
        app.add_middleware(CSRFMiddleware)
    app.add_middleware(RequestIdMiddleware)
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    return app


app = create_app()
