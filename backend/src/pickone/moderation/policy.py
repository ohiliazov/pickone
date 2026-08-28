from __future__ import annotations

from typing import Literal, TypedDict

Decision = Literal["APPROVED", "REVIEW", "REJECTED"]


class Policy(TypedDict):
    reject_at: dict[str, float]
    review_at: dict[str, float]
    default: Decision


POLICY_V1: Policy = {
    "reject_at": {
        "sexual/minors": 0.10,
        "hate/threatening": 0.20,
        "violence/graphic": 0.60,
        "harassment/threatening": 0.30,
        "self-harm": 0.30,
        "sexual": 0.70,
        "hate": 0.50,
    },
    "review_at": {
        "sexual/minors": 0.02,
        "hate/threatening": 0.05,
        "violence/graphic": 0.30,
        "harassment/threatening": 0.10,
        "self-harm": 0.10,
        "sexual": 0.40,
        "hate": 0.25,
    },
    "default": "APPROVED",
}


def decide(scores: dict[str, float], policy: Policy) -> Decision:
    if any(
        scores.get(category, 0.0) >= threshold
        for category, threshold in policy["reject_at"].items()
    ):
        return "REJECTED"
    if any(
        scores.get(category, 0.0) >= threshold
        for category, threshold in policy["review_at"].items()
    ):
        return "REVIEW"
    return policy["default"]
