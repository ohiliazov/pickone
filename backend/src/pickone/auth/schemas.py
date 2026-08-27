from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, EmailStr, Field

if TYPE_CHECKING:
    from pickone.auth.models import User


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class VerifyRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)


class PasswordResetRequestRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    password: str = Field(min_length=1, max_length=256)


class UserOut(BaseModel):
    id: str
    email: str | None
    email_verified: bool
    is_guest: bool

    @classmethod
    def from_user(cls, user: User) -> UserOut:
        return cls(
            id=str(user.id),
            email=user.email,
            email_verified=user.email_verified_at is not None,
            is_guest=user.is_guest,
        )


class RegisterResponse(BaseModel):
    user: UserOut
    csrf_token: str
    converted_from_guest: bool = False
    picks_kept: int = 0


class LoginResponse(BaseModel):
    user: UserOut
    csrf_token: str


class MeLimits(BaseModel):
    items_remaining_today: int


class MeResponse(BaseModel):
    user: UserOut
    csrf_token: str
    limits: MeLimits


class VerifyResponse(BaseModel):
    user: UserOut
