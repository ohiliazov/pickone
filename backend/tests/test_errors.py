"""The error envelope is one shape, always. [SPEC §8.1]"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response

from pickone.core.errors import (
    ConflictError,
    GoneError,
    NotFoundError,
    PickOneError,
    install_error_handlers,
)


@pytest.fixture
def error_app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/gone")
    async def _gone() -> None:
        raise GoneError()

    @app.get("/conflict")
    async def _conflict() -> None:
        raise ConflictError("Already decided.", details={"battle_id": "x"})

    @app.get("/boom")
    async def _boom() -> None:
        raise RuntimeError("internal detail that must not leak")

    return app


async def _get(app: FastAPI, path: str) -> Response:
    # raise_app_exceptions=False because Starlette's ServerErrorMiddleware always
    # re-raises after building the 500 response, so the server can log it.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        return await ac.get(path)


@pytest.mark.parametrize(
    ("path", "status", "code"),
    [("/gone", 410, "gone"), ("/conflict", 409, "conflict")],
)
async def test_envelope_shape(error_app: FastAPI, path: str, status: int, code: str) -> None:
    resp = await _get(error_app, path)
    assert resp.status_code == status
    body = resp.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == code


async def test_details_are_carried(error_app: FastAPI) -> None:
    body = (await _get(error_app, "/conflict")).json()
    assert body["error"]["details"] == {"battle_id": "x"}
    assert body["error"]["message"] == "Already decided."


async def test_unhandled_exception_leaks_nothing(error_app: FastAPI) -> None:
    resp = await _get(error_app, "/boom")
    assert resp.status_code == 500
    assert "internal detail" not in resp.text
    assert resp.json()["error"]["code"] == "internal_error"


def test_messages_are_user_safe() -> None:
    """Copy is shown verbatim to users, so it lives in the product lexicon."""
    banned = {"error", "exception", "invalid request", "failed"}
    for cls in PickOneError.__subclasses__():
        msg = cls.message.lower()
        assert not any(b in msg for b in banned), f"{cls.__name__}: {cls.message!r}"
        assert msg.endswith("."), f"{cls.__name__} message should be a sentence"


def test_not_found_is_the_wrong_owner_answer() -> None:
    """[SPEC §8.4] Wrong-owner returns 404, not 403, so ids are not an oracle."""
    assert NotFoundError.status_code == 404
