from __future__ import annotations

import re
import unicodedata

from pickone.core.config import get_settings
from pickone.items.errors import InvalidTextError
from pickone.items.slugs import slugify

RESERVED_SLUGS = frozenset(
    {
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
    }
)

_MIN_LENGTH = 2

_URL_PATTERN = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_EMAIL_PATTERN = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
_PHONE_PATTERN = re.compile(r"\d[\d\-.\s()]{6,}\d")
_HANDLE_PATTERN = re.compile(r"@\w+")

_ALLOWED_ACCENTED_RANGE = (0x00C0, 0x024F)
_ALLOWED_PUNCTUATION_CODEPOINTS = frozenset(
    {0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2026}
)


def _is_allowed_char(ch: str) -> bool:
    codepoint = ord(ch)
    if codepoint < 128:
        return True
    if _ALLOWED_ACCENTED_RANGE[0] <= codepoint <= _ALLOWED_ACCENTED_RANGE[1]:
        return True
    return codepoint in _ALLOWED_PUNCTUATION_CODEPOINTS


def _looks_like_a_reserved_slug(display: str) -> bool:
    return display.strip().lower() in RESERVED_SLUGS or slugify(display) in RESERVED_SLUGS


def validate_structure(display: str) -> None:
    max_length = get_settings().item_max_length

    if len(display) < _MIN_LENGTH:
        raise InvalidTextError(details={"reason": "too_short", "min": _MIN_LENGTH})
    if len(display) > max_length:
        raise InvalidTextError(details={"reason": "too_long", "max": max_length})
    if "\n" in display or "\r" in display:
        raise InvalidTextError(details={"reason": "multiline"})
    if (
        _URL_PATTERN.search(display)
        or _EMAIL_PATTERN.search(display)
        or _PHONE_PATTERN.search(display)
        or _HANDLE_PATTERN.search(display)
    ):
        raise InvalidTextError(details={"reason": "url_or_handle"})

    digit_or_punct = sum(1 for ch in display if unicodedata.category(ch)[0] in ("N", "P"))
    if digit_or_punct > len(display) / 2:
        raise InvalidTextError(details={"reason": "mostly_non_letters"})

    stripped = display.replace(" ", "")
    if stripped and len(set(stripped)) == 1:
        raise InvalidTextError(details={"reason": "repeated_character"})

    if any(not _is_allowed_char(ch) for ch in display):
        raise InvalidTextError(details={"reason": "disallowed_script"})

    if _looks_like_a_reserved_slug(display):
        raise InvalidTextError(details={"reason": "reserved_slug"})
