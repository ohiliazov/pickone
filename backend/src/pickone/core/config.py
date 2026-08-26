"""The configuration register.  [SPEC §21.3]

Every ``[CONFIG]`` value in the specification lives here as a single named
setting with the documented default, loaded from the environment and validated
at boot. A magic number in a function body is a review failure.

M0 creates the register with the core keys. Each subsequent milestone adds only
its own keys, in its own section below.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET_KEY = "dev-only-not-a-secret-change-me-in-production"


class Env(StrEnum):
    LOCAL = "local"
    TEST = "test"
    PREVIEW = "preview"
    PRODUCTION = "production"

    @property
    def is_production(self) -> bool:
        return self is Env.PRODUCTION

    @property
    def is_indexable(self) -> bool:
        """Only production may be crawled. Everything else serves Disallow: /.

        [SPEC §14.8] A preview deploy that gets indexed is the classic own-goal.
        """
        return self is Env.PRODUCTION


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PICKONE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    # ---------------------------------------------------------------- M0: core
    env: Env = Env.LOCAL
    database_url: str = "postgresql+asyncpg://pickone:pickone@localhost:5100/pickone"
    secret_key: str = DEV_SECRET_KEY
    base_url: str = "http://localhost:3100"
    log_level: str = "INFO"

    db_pool_size: int = Field(default=4, ge=1, le=32)
    db_pool_max_overflow: int = Field(default=2, ge=0, le=32)
    db_echo: bool = False

    # How long a starting worker waits for the singleton lock before giving up.
    # Non-zero because a redeploy can leave the departing worker's connection
    # alive for a few seconds after its container is gone.
    worker_lock_wait_seconds: float = Field(default=30.0, ge=0, le=300)
    worker_lock_poll_seconds: float = Field(default=2.0, gt=0, le=30)

    # Later milestones add their keys here — and nowhere else.
    #   M1 auth      session TTLs, Argon2 params, rate limits, guest janitor TTLs
    #   M2 items     item_max_length=64, moderation provider + policy thresholds
    #   M3 rating    rating_system, initial_rating=0, initial_rd=350, ranked_rd
    #   M4 battles   battle_ttl_seconds=60, matchmaking weights, cooldowns
    #   M6 seo       indexing thresholds, sitemap caps, revalidation windows

    @model_validator(mode="after")
    def _production_requires_real_values(self) -> Settings:
        """Fail at boot, not on first request.  [M0 acceptance #4]

        This is the mechanism M2 reuses to refuse ``NullProvider`` in production.
        Add production-only requirements here; never at a call site.
        """
        if not self.env.is_production:
            return self

        problems: list[str] = []
        if self.secret_key == DEV_SECRET_KEY:
            problems.append("PICKONE_SECRET_KEY is still the development default")
        if len(self.secret_key) < 32:
            problems.append("PICKONE_SECRET_KEY must be at least 32 characters")
        if "localhost" in self.database_url:
            problems.append("PICKONE_DATABASE_URL points at localhost")
        if not self.base_url.startswith("https://"):
            problems.append("PICKONE_BASE_URL must be https in production")

        if problems:
            raise ValueError("Refusing to start in production:\n  - " + "\n  - ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    """The process-wide settings singleton. Cached, so the register is read once."""
    return Settings()
