from __future__ import annotations

import pytest

from pickone.items.errors import InvalidTextError
from pickone.items.validation import RESERVED_SLUGS, validate_structure


@pytest.mark.parametrize(
    "text",
    [
        "Carbonara",
        "Fitting bed sheets",
        "300 W FTP",
        "Spaghetti alla Carbonara",
        "co-op",
    ],
)
def test_validate_structure_accepts_valid_text(text: str) -> None:
    validate_structure(text)


def test_rejects_too_short() -> None:
    with pytest.raises(InvalidTextError) as exc:
        validate_structure("a")
    assert exc.value.details["reason"] == "too_short"


def test_rejects_too_long() -> None:
    with pytest.raises(InvalidTextError) as exc:
        validate_structure("a" * 65)
    assert exc.value.details["reason"] == "too_long"
    assert exc.value.details["max"] == 64


def test_accepts_exactly_64_characters() -> None:
    validate_structure("a b" + "c" * 61)


def test_rejects_multiline() -> None:
    with pytest.raises(InvalidTextError) as exc:
        validate_structure("first line\nsecond line")
    assert exc.value.details["reason"] == "multiline"


@pytest.mark.parametrize(
    "text",
    [
        "Visit https://example.com now",
        "Visit www.example.com now",
        "Email me at person@example.com",
        "Call 555-123-4567 today",
        "Follow @handle please",
    ],
)
def test_rejects_urls_emails_phones_and_handles(text: str) -> None:
    with pytest.raises(InvalidTextError) as exc:
        validate_structure(text)
    assert exc.value.details["reason"] == "url_or_handle"


@pytest.mark.parametrize("text", ["12, 34", "!!!!!!!!", "1, 2, 3, 4"])
def test_rejects_majority_digits_or_punctuation(text: str) -> None:
    with pytest.raises(InvalidTextError) as exc:
        validate_structure(text)
    assert exc.value.details["reason"] == "mostly_non_letters"


def test_rejects_a_single_repeated_character() -> None:
    with pytest.raises(InvalidTextError) as exc:
        validate_structure("aaaaaaaa")
    assert exc.value.details["reason"] == "repeated_character"


@pytest.mark.parametrize("text", ["日本語のテキスト", "текст на русском", "\U0001f600\U0001f601"])
def test_rejects_disallowed_scripts(text: str) -> None:
    with pytest.raises(InvalidTextError) as exc:
        validate_structure(text)
    assert exc.value.details["reason"] == "disallowed_script"


def test_reserved_slugs_are_rejected() -> None:
    for reserved in RESERVED_SLUGS:
        with pytest.raises(InvalidTextError) as exc:
            validate_structure(reserved)
        assert exc.value.details["reason"] == "reserved_slug"


def test_reserved_slugs_contains_the_documented_set() -> None:
    assert {
        "api",
        "admin",
        "play",
        "add",
        "rankings",
        "item",
        "compare",
        "login",
        "register",
        "about",
        "terms",
        "privacy",
        "sitemap",
        "robots",
        "og",
        "_next",
        "static",
    } == RESERVED_SLUGS
