from __future__ import annotations

from typing import Any

import httpx
import pytest

from pickone.moderation.provider import (
    HeuristicProvider,
    NullProvider,
    OpenAIModerationProvider,
    ProviderResult,
    build_provider,
)


async def test_null_provider_approves_everything() -> None:
    result = await NullProvider().check("anything at all")
    assert result.scores == {}
    assert result.model == "null"


async def test_heuristic_provider_flags_blocked_terms() -> None:
    result = await HeuristicProvider().check("kill yourself now")
    assert result.scores.get("hate", 0.0) > 0.0


async def test_heuristic_provider_is_clean_for_ordinary_text() -> None:
    result = await HeuristicProvider().check("Fitting bed sheets")
    assert result.scores == {}


async def test_heuristic_provider_flags_exclamation_spam() -> None:
    result = await HeuristicProvider().check("!!!!!!!!!!")
    assert result.scores.get("harassment/threatening", 0.0) > 0.0


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeAsyncClient:
    captured_json: dict[str, Any] | None = None
    captured_headers: dict[str, str] | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def post(
        self, url: str, *, headers: dict[str, str], json: dict[str, Any]
    ) -> _FakeResponse:
        _FakeAsyncClient.captured_json = json
        _FakeAsyncClient.captured_headers = headers
        return _FakeResponse({"results": [{"category_scores": {"hate": 0.9, "sexual": 0.01}}]})


async def test_openai_provider_maps_category_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    provider = OpenAIModerationProvider(api_key="sk-test", model="omni-moderation-latest")
    result = await provider.check("some text")
    assert result.scores == {"hate": 0.9, "sexual": 0.01}
    assert result.model == "omni-moderation-latest"
    assert _FakeAsyncClient.captured_headers == {"Authorization": "Bearer sk-test"}
    assert _FakeAsyncClient.captured_json == {
        "model": "omni-moderation-latest",
        "input": "some text",
    }


def test_provider_result_is_a_plain_value() -> None:
    result = ProviderResult(scores={"hate": 0.1}, model="x", raw={})
    assert result.scores == {"hate": 0.1}


def test_build_provider_reads_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    from pickone.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("PICKONE_MODERATION_PROVIDER", "heuristic")
    try:
        assert isinstance(build_provider(), HeuristicProvider)
    finally:
        get_settings.cache_clear()
