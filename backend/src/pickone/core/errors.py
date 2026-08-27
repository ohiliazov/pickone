from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from pickone.core.logging import get_logger

logger = get_logger(__name__)


class PickOneError(Exception):
    code: str = "internal_error"
    message: str = "Something went wrong."
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.__class__.message
        self.details = details or {}
        self.headers = headers or {}
        super().__init__(self.message)

    def envelope(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


class NotFoundError(PickOneError):
    code = "not_found"
    message = "Not here."
    status_code = status.HTTP_404_NOT_FOUND


class NotAuthenticatedError(PickOneError):
    code = "account_required"
    message = "Make an account first."
    status_code = status.HTTP_401_UNAUTHORIZED


class ForbiddenError(PickOneError):
    code = "forbidden"
    message = "Not allowed."
    status_code = status.HTTP_403_FORBIDDEN


class CSRFFailedError(PickOneError):
    code = "csrf_failed"
    message = "Request blocked."
    status_code = status.HTTP_403_FORBIDDEN


class ConflictError(PickOneError):
    code = "conflict"
    message = "Already done."
    status_code = status.HTTP_409_CONFLICT


class GoneError(PickOneError):
    code = "gone"
    message = "That one timed out."
    status_code = status.HTTP_410_GONE


class InvalidInputError(PickOneError):
    code = "invalid_input"
    message = "We can't use that."
    status_code = 422


class RateLimitedError(PickOneError):
    code = "rate_limited"
    message = "Slow down a moment."
    status_code = status.HTTP_429_TOO_MANY_REQUESTS


class ServiceUnavailableError(PickOneError):
    code = "service_unavailable"
    message = "Back in a moment."
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(PickOneError)
    async def _pickone_error(_: Request, exc: PickOneError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content=exc.envelope(), headers=exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = sorted({str(e["loc"][-1]) for e in exc.errors() if e.get("loc")})
        err = InvalidInputError(details={"fields": fields})
        return JSONResponse(status_code=err.status_code, content=err.envelope())

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", error=str(exc))
        err = PickOneError()
        return JSONResponse(status_code=err.status_code, content=err.envelope())
