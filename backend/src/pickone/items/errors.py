from __future__ import annotations

from pickone.core.errors import ConflictError, InvalidInputError


class InvalidTextError(InvalidInputError):
    code = "invalid_text"


class RejectedError(InvalidInputError):
    code = "rejected"
    message = "We can't add that one."

    def __init__(self) -> None:
        super().__init__()


class AlreadyExistsError(ConflictError):
    code = "already_exists"


class AlreadyReportedError(ConflictError):
    code = "already_reported"
