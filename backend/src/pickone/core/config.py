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
        return self is Env.PRODUCTION


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PICKONE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    env: Env = Env.LOCAL
    database_url: str = "postgresql+asyncpg://pickone:pickone@localhost:5100/pickone"
    secret_key: str = DEV_SECRET_KEY
    base_url: str = "http://localhost:3100"
    log_level: str = "INFO"

    db_pool_size: int = Field(default=4, ge=1, le=32)
    db_pool_max_overflow: int = Field(default=2, ge=0, le=32)
    db_echo: bool = False

    worker_lock_wait_seconds: float = Field(default=30.0, ge=0, le=300)
    worker_lock_poll_seconds: float = Field(default=2.0, gt=0, le=30)

    argon2_time_cost: int = Field(default=3, ge=1, le=10)
    argon2_memory_cost_kib: int = Field(default=65536, ge=8192)
    argon2_parallelism: int = Field(default=4, ge=1, le=16)

    password_min_length: int = Field(default=10, ge=8, le=128)

    session_ttl_days: int = Field(default=30, ge=1)
    session_absolute_ttl_days: int = Field(default=180, ge=1)

    verify_token_ttl_hours: int = Field(default=24, ge=1)
    verify_resend_limit_per_hour: int = Field(default=3, ge=1)
    reset_token_ttl_minutes: int = Field(default=60, ge=1)

    guest_empty_ttl_days: int = Field(default=7, ge=1)
    guest_max_age_days: int = Field(default=180, ge=1)
    guest_prompt_after_picks: int = Field(default=25, ge=1)

    rl_register_per_hour_ip: int = Field(default=5, ge=1)
    rl_register_per_day_ip: int = Field(default=20, ge=1)
    rl_login_per_15min_ip: int = Field(default=10, ge=1)
    rl_login_per_15min_account: int = Field(default=5, ge=1)
    rl_login_backoff_base_seconds: float = Field(default=15.0, gt=0)
    rl_login_backoff_max_minutes: int = Field(default=15, ge=1)
    rl_reset_request_per_hour_email: int = Field(default=3, ge=1)
    rl_reset_request_per_hour_ip: int = Field(default=10, ge=1)
    rl_verify_resend_per_hour_user: int = Field(default=3, ge=1)
    rl_guest_create_per_hour_ip: int = Field(default=300, ge=1)

    email_provider: str = "console"
    resend_api_key: str = ""
    mail_from: str = "noreply@pickone.app"
    mail_from_name: str = "PickOne"

    outbox_poll_seconds: float = Field(default=2.0, gt=0, le=60)
    outbox_max_attempts: int = Field(default=8, ge=1, le=50)
    outbox_backoff_base_seconds: float = Field(default=10.0, gt=0)
    outbox_backoff_max_seconds: float = Field(default=3600.0, gt=0)

    guest_janitor_interval_minutes: float = Field(default=60.0, gt=0)

    rl_items_per_day_user: int = Field(default=20, ge=1)

    @model_validator(mode="after")
    def _resend_requires_a_key_in_production(self) -> Settings:
        if self.env.is_production and self.email_provider == "resend" and not self.resend_api_key:
            raise ValueError(
                "PICKONE_RESEND_API_KEY is required when PICKONE_EMAIL_PROVIDER=resend"
            )
        return self

    @model_validator(mode="after")
    def _production_requires_real_values(self) -> Settings:
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
    return Settings()
