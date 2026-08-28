from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from pickone.moderation.starter_blocklist import contains_blocked_term

_EXCLAMATION_SPAM_RATIO = 0.3


@dataclass(frozen=True)
class ProviderResult:
    scores: dict[str, float]
    model: str
    raw: dict[str, Any]


class ModerationProvider(Protocol):
    async def check(self, text: str) -> ProviderResult: ...


class NullProvider:
    async def check(self, text: str) -> ProviderResult:
        return ProviderResult(scores={}, model="null", raw={})


class HeuristicProvider:
    async def check(self, text: str) -> ProviderResult:
        scores = _heuristic_scores(text)
        return ProviderResult(scores=scores, model="heuristic", raw={"scores": scores})


def _heuristic_scores(text: str) -> dict[str, float]:
    scores: dict[str, float] = {}
    if contains_blocked_term(text):
        scores["hate"] = 1.0
    if text and text.count("!") / len(text) > _EXCLAMATION_SPAM_RATIO:
        scores["harassment/threatening"] = 0.5
    return scores


class OpenAIModerationProvider:
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    async def check(self, text: str) -> ProviderResult:
        import httpx

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/moderations",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"model": self._model, "input": text},
            )
            response.raise_for_status()
            data = response.json()

        scores: dict[str, float] = data["results"][0]["category_scores"]
        return ProviderResult(scores=scores, model=self._model, raw=data)


def build_provider() -> ModerationProvider:
    from pickone.core.config import get_settings

    settings = get_settings()
    if settings.moderation_provider == "openai":
        return OpenAIModerationProvider(settings.openai_api_key, settings.moderation_model)
    if settings.moderation_provider == "null":
        return NullProvider()
    return HeuristicProvider()
