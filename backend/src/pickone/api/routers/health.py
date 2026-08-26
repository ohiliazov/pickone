"""Liveness and readiness.

``/healthz`` answers "is this process alive" and must not touch the database —
otherwise a database blip restarts healthy API containers.

``/readyz`` answers "can this process serve traffic" and therefore must. It
deliberately does *not* use the request-session dependency: a dependency that
raises fails during resolution, which produces a 500 before the handler runs.
A readiness probe reporting "server error" instead of "not ready" is the
difference between a load balancer draining a pod and a pager going off, so
the connection is acquired inside the handler where it can be caught.
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from pickone import __version__
from pickone.core.config import get_settings
from pickone.core.logging import get_logger
from pickone.db.engine import get_engine

router = APIRouter(tags=["health"])
logger = get_logger(__name__)

READY_TIMEOUT_SECONDS = 2.0


def engine_dependency() -> AsyncEngine:
    """Indirection so tests can point readiness at a database that is down."""
    return get_engine()


@router.get("/healthz")
async def healthz() -> dict[str, Any]:
    return {"status": "ok", "version": __version__, "env": get_settings().env.value}


@router.get("/readyz")
async def readyz(engine: Annotated[AsyncEngine, Depends(engine_dependency)]) -> JSONResponse:
    try:
        async with asyncio.timeout(READY_TIMEOUT_SECONDS):
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
    except (Exception, asyncio.CancelledError) as exc:
        logger.warning("readyz_failed", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "database": "unreachable"},
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK, content={"status": "ready", "database": "ok"}
    )
