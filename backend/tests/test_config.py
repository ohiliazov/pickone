"""The configuration register fails at boot, not on first request. [M0 #4]"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pickone.core.config import DEV_SECRET_KEY, Env, Settings

PROD = {
    "env": "production",
    "secret_key": "x" * 48,
    "database_url": "postgresql+asyncpg://u:p@db.internal:5432/pickone",
    "base_url": "https://pickone.app",
}


def test_local_defaults_are_usable() -> None:
    s = Settings(env=Env.LOCAL)
    assert s.env is Env.LOCAL
    assert not s.env.is_production


def test_production_accepts_a_real_configuration() -> None:
    assert Settings(**PROD).env.is_production  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("override", "fragment"),
    [
        ({"secret_key": DEV_SECRET_KEY}, "development default"),
        ({"secret_key": "short"}, "at least 32"),
        ({"database_url": "postgresql+asyncpg://u:p@localhost:5432/x"}, "localhost"),
        ({"base_url": "http://pickone.app"}, "https"),
    ],
)
def test_production_refuses_to_start_when_misconfigured(
    override: dict[str, str], fragment: str
) -> None:
    with pytest.raises(ValidationError) as exc:
        Settings(**{**PROD, **override})  # type: ignore[arg-type]
    assert fragment in str(exc.value)


def test_the_same_misconfiguration_is_fine_outside_production() -> None:
    """Local development must not be hostage to production rules."""
    Settings(env=Env.LOCAL, secret_key=DEV_SECRET_KEY)


def test_only_production_is_indexable() -> None:
    """[SPEC §14.8] Staging and preview must never be crawled."""
    assert Env.PRODUCTION.is_indexable
    assert not Env.PREVIEW.is_indexable
    assert not Env.LOCAL.is_indexable
    assert not Env.TEST.is_indexable


def test_settings_are_frozen() -> None:
    """Configuration is read once at boot; nothing mutates it at runtime."""
    s = Settings()
    with pytest.raises(ValidationError):
        s.log_level = "DEBUG"


def test_production_validator_is_the_seam_m2_will_reuse() -> None:
    """M2 refuses NullProvider in production through this same validator.

    The mechanism is built here so that milestone adds a rule, not a pattern.
    """
    validators = Settings.__pydantic_decorators__.model_validators
    assert "_production_requires_real_values" in validators
