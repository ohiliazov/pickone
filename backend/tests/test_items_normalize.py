from __future__ import annotations

import pytest

from pickone.items.normalize import ControlCharacterError, display_text, normalized_text

ZERO_WIDTH_SPACE = "​"
ZERO_WIDTH_NON_JOINER = "‌"
ZERO_WIDTH_JOINER = "‍"
BOM = "﻿"
LEFT_TO_RIGHT_EMBEDDING = "‪"
POP_DIRECTIONAL_FORMATTING = "‬"
FIRST_STRONG_ISOLATE = "⁦"
POP_DIRECTIONAL_ISOLATE = "⁩"
EMOJI = "\U0001f600"
CAFE_PRECOMPOSED = "café"[:3] + "é"
CAFE_DECOMPOSED = "café"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Carbonara", "Carbonara"),
        ("  Carbonara  ", "Carbonara"),
        ("Fitting   bed\t\tsheets", "Fitting bed sheets"),
        (CAFE_DECOMPOSED, CAFE_PRECOMPOSED),
        (f"a{ZERO_WIDTH_SPACE}b{ZERO_WIDTH_NON_JOINER}c{ZERO_WIDTH_JOINER}d{BOM}e", "abcde"),
        (
            f"a{LEFT_TO_RIGHT_EMBEDDING}b{POP_DIRECTIONAL_FORMATTING}c"
            f"{FIRST_STRONG_ISOLATE}d{POP_DIRECTIONAL_ISOLATE}e",
            "abcde",
        ),
        (f"{EMOJI} hello", f"{EMOJI} hello"),
        ("héllo мир", "héllo мир"),
    ],
)
def test_display_text(raw: str, expected: str) -> None:
    assert display_text(raw) == expected


def test_display_text_rejects_remaining_control_characters() -> None:
    with pytest.raises(ControlCharacterError):
        display_text("a\x01b")


def test_display_text_is_idempotent() -> None:
    for raw in ["  Carbonara  ", CAFE_DECOMPOSED, "Fitting   bed\t\tsheets"]:
        once = display_text(raw)
        assert display_text(once) == once


@pytest.mark.parametrize(
    ("display", "expected"),
    [
        ("Carbonara", "carbonara"),
        ("CAFÉ", "cafe"),
        (CAFE_PRECOMPOSED, "cafe"),
        (CAFE_DECOMPOSED, "cafe"),
        ("Fitting bed sheets", "fitting bed sheets"),
        ("Hello, World!", "hello world"),
        ("hello - world", "hello world"),
        (f"{EMOJI} hello", "hello"),
        ("héllo мир", "hello мир"),
    ],
)
def test_normalized_text(display: str, expected: str) -> None:
    assert normalized_text(display) == expected


def test_normalized_text_is_idempotent() -> None:
    for display in ["CAFÉ", "Hello, World!", "hello - world"]:
        once = normalized_text(display)
        assert normalized_text(once) == once
