from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from pickone.auth.dependencies import current_actor
from pickone.auth.errors import VerificationRequiredError
from pickone.auth.models import User
from pickone.core.errors import NotAuthenticatedError


async def item_author(actor: Annotated[User | None, Depends(current_actor)]) -> User:
    if actor is None or actor.is_guest:
        raise NotAuthenticatedError("Make an account to add one.")
    if actor.email_verified_at is None:
        raise VerificationRequiredError()
    return actor
