from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from pickone.core.config import get_settings


def _hasher() -> PasswordHasher:
    s = get_settings()
    return PasswordHasher(
        time_cost=s.argon2_time_cost,
        memory_cost=s.argon2_memory_cost_kib,
        parallelism=s.argon2_parallelism,
    )


def hash_password(password: str) -> str:
    return _hasher().hash(password)


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        _hasher().verify(encoded_hash, password)
    except VerifyMismatchError:
        return False
    return True


def needs_rehash(encoded_hash: str) -> bool:
    return _hasher().check_needs_rehash(encoded_hash)


_DUMMY_HASH = hash_password("this-is-not-a-real-password-const-time-decoy")


def verify_password_constant_time_dummy() -> None:
    verify_password("irrelevant", _DUMMY_HASH)


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def new_csrf_secret() -> bytes:
    return secrets.token_bytes(32)


def derive_csrf_token(csrf_secret: bytes, session_id: str) -> str:
    return hmac.new(csrf_secret, session_id.encode("utf-8"), hashlib.sha256).hexdigest()


def csrf_token_matches(csrf_secret: bytes, session_id: str, candidate: str) -> bool:
    expected = derive_csrf_token(csrf_secret, session_id)
    return hmac.compare_digest(expected, candidate)


def hash_ip(ip: str) -> bytes:
    key = get_settings().secret_key.encode("utf-8")
    return hmac.new(key, ip.encode("utf-8"), hashlib.sha256).digest()


def hash_user_agent(user_agent: str) -> bytes:
    key = get_settings().secret_key.encode("utf-8")
    return hmac.new(key, user_agent.encode("utf-8"), hashlib.sha256).digest()
