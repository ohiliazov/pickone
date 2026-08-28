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
        ({"moderation_provider": "null"}, "NullProvider"),
    ],
)
def test_production_refuses_to_start_when_misconfigured(
    override: dict[str, str], fragment: str
) -> None:
    with pytest.raises(ValidationError) as exc:
        Settings(**{**PROD, **override})  # type: ignore[arg-type]
    assert fragment in str(exc.value)


def test_the_same_misconfiguration_is_fine_outside_production() -> None:
    Settings(env=Env.LOCAL, secret_key=DEV_SECRET_KEY)
    Settings(env=Env.LOCAL, moderation_provider="null")


def test_default_moderation_provider_is_heuristic() -> None:
    assert Settings(env=Env.LOCAL).moderation_provider == "heuristic"


def test_openai_moderation_requires_a_key_in_production() -> None:
    with pytest.raises(ValidationError) as exc:
        Settings(**{**PROD, "moderation_provider": "openai"})  # type: ignore[arg-type]
    assert "PICKONE_OPENAI_API_KEY" in str(exc.value)


def test_openai_moderation_with_a_key_is_fine_in_production() -> None:
    settings = Settings(
        **{**PROD, "moderation_provider": "openai", "openai_api_key": "sk-test"}  # type: ignore[arg-type]
    )
    assert settings.moderation_provider == "openai"


def test_only_production_is_indexable() -> None:
    assert Env.PRODUCTION.is_indexable
    assert not Env.PREVIEW.is_indexable
    assert not Env.LOCAL.is_indexable
    assert not Env.TEST.is_indexable


def test_settings_are_frozen() -> None:
    s = Settings()
    with pytest.raises(ValidationError):
        s.log_level = "DEBUG"


def test_production_validator_is_the_seam_m2_will_reuse() -> None:
    validators = Settings.__pydantic_decorators__.model_validators
    assert "_production_requires_real_values" in validators
