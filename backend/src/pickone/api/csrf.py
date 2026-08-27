from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from pickone.auth import repository
from pickone.auth.dependencies import SESSION_COOKIE_NAME
from pickone.core.config import get_settings
from pickone.core.errors import CSRFFailedError
from pickone.core.security import csrf_token_matches, hash_token
from pickone.db.session import get_session

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
ALLOWLIST = {
    "/api/auth/login",
    "/api/auth/register",
    "/api/auth/verify",
    "/api/auth/password-reset/request",
    "/api/auth/password-reset/confirm",
}
CSRF_HEADER = "X-PickOne-CSRF"

SessionScope = Callable[[], AbstractAsyncContextManager[AsyncSession]]


@asynccontextmanager
async def _default_session_scope() -> AsyncIterator[AsyncSession]:
    gen = get_session()
    session = await anext(gen)
    try:
        yield session
    finally:
        with contextlib.suppress(StopAsyncIteration):
            await anext(gen)


def _origin_matches_base_url(origin: str, base_url: str) -> bool:
    a = urlparse(origin)
    b = urlparse(base_url)
    return (a.scheme, a.netloc) == (b.scheme, b.netloc)


class CSRFMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, session_scope: SessionScope = _default_session_scope) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._session_scope = session_scope

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method not in UNSAFE_METHODS:
            return await call_next(request)

        settings = get_settings()
        origin = request.headers.get("origin") or request.headers.get("referer")
        if not origin or not _origin_matches_base_url(origin, settings.base_url):
            return _forbidden()

        if request.url.path in ALLOWLIST:
            return await call_next(request)

        raw_token = request.cookies.get(SESSION_COOKIE_NAME)
        if not raw_token:
            return _forbidden()

        csrf_header = request.headers.get(CSRF_HEADER)
        if not csrf_header:
            return _forbidden()

        async with self._session_scope() as session:
            row = await repository.get_active_session_by_token_hash(session, hash_token(raw_token))
            if row is None:
                return _forbidden()
            if not csrf_token_matches(row.csrf_secret, str(row.id), csrf_header):
                return _forbidden()

        return await call_next(request)


def _forbidden() -> JSONResponse:
    err = CSRFFailedError()
    return JSONResponse(status_code=err.status_code, content=err.envelope())
