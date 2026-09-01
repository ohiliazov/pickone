from __future__ import annotations

import pytest
import sentry_sdk

from pickone.api.app import create_app
from pickone.core.config import Env, Settings


def test_create_app_initializes_sentry_when_dsn_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))
    settings = Settings(env=Env.LOCAL, glitchtip_dsn="https://key@glitchtip.example/1")
    create_app(settings=settings)
    assert calls == [{"dsn": "https://key@glitchtip.example/1", "environment": "local"}]


def test_create_app_does_not_initialize_sentry_when_dsn_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: calls.append(kwargs))
    settings = Settings(env=Env.LOCAL, glitchtip_dsn="")
    create_app(settings=settings)
    assert calls == []
