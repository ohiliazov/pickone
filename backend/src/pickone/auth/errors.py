from __future__ import annotations

from pickone.core.errors import (
    ConflictError,
    GoneError,
    InvalidInputError,
    PickOneError,
    RateLimitedError,
)


class EmailTakenError(ConflictError):
    code = "email_taken"
    message = "That email's already in use."


class WeakPasswordError(InvalidInputError):
    code = "weak_password"
    message = "Needs a few more characters."


class InvalidCredentialsError(PickOneError):
    code = "invalid_credentials"
    message = "That didn't match."
    status_code = 401


class TooManyAttemptsError(RateLimitedError):
    code = "too_many_attempts"
    message = "Too many tries. Wait a moment."


class TokenExpiredError(GoneError):
    code = "token_expired"
    message = "That link's expired."


class TokenInvalidError(PickOneError):
    code = "token_invalid"
    message = "That link isn't right."
    status_code = 400


class VerificationRequiredError(PickOneError):
    code = "verification_required"
    message = "Verify your email first."
    status_code = 403
