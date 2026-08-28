from __future__ import annotations

import pytest

from pickone.moderation.policy import POLICY_V1, decide
from pickone.moderation.starter_blocklist import STARTER_BLOCKLIST, contains_blocked_term


def test_approves_clean_scores() -> None:
    assert decide({"sexual": 0.01, "hate": 0.01}, POLICY_V1) == "APPROVED"


def test_approves_when_scores_are_missing_entirely() -> None:
    assert decide({}, POLICY_V1) == "APPROVED"


@pytest.mark.parametrize(
    "category",
    [
        "sexual/minors",
        "hate/threatening",
        "violence/graphic",
        "harassment/threatening",
        "self-harm",
        "sexual",
        "hate",
    ],
)
def test_review_at_threshold_triggers_review(category: str) -> None:
    threshold = POLICY_V1["review_at"][category]
    assert decide({category: threshold}, POLICY_V1) == "REVIEW"


@pytest.mark.parametrize(
    "category",
    [
        "sexual/minors",
        "hate/threatening",
        "violence/graphic",
        "harassment/threatening",
        "self-harm",
        "sexual",
        "hate",
    ],
)
def test_just_below_review_at_is_approved(category: str) -> None:
    threshold = POLICY_V1["review_at"][category]
    assert decide({category: threshold - 0.001}, POLICY_V1) == "APPROVED"


@pytest.mark.parametrize(
    "category",
    [
        "sexual/minors",
        "hate/threatening",
        "violence/graphic",
        "harassment/threatening",
        "self-harm",
        "sexual",
        "hate",
    ],
)
def test_reject_at_threshold_triggers_rejection(category: str) -> None:
    threshold = POLICY_V1["reject_at"][category]
    assert decide({category: threshold}, POLICY_V1) == "REJECTED"


@pytest.mark.parametrize(
    "category",
    [
        "sexual/minors",
        "hate/threatening",
        "violence/graphic",
        "harassment/threatening",
        "self-harm",
        "sexual",
        "hate",
    ],
)
def test_just_below_reject_at_is_review(category: str) -> None:
    threshold = POLICY_V1["reject_at"][category]
    assert decide({category: threshold - 0.001}, POLICY_V1) == "REVIEW"


def test_rejection_wins_over_review_when_both_apply() -> None:
    scores = {"hate": POLICY_V1["reject_at"]["hate"], "sexual": POLICY_V1["review_at"]["sexual"]}
    assert decide(scores, POLICY_V1) == "REJECTED"


def test_starter_blocklist_is_non_empty() -> None:
    assert len(STARTER_BLOCKLIST) > 0


def test_contains_blocked_term_is_case_insensitive() -> None:
    term = next(iter(STARTER_BLOCKLIST))
    assert contains_blocked_term(term.upper())
    assert contains_blocked_term(f"prefix {term} suffix")


def test_contains_blocked_term_is_false_for_clean_text() -> None:
    assert not contains_blocked_term("Carbonara")
    assert not contains_blocked_term("Fitting bed sheets")
