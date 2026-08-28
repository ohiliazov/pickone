from __future__ import annotations

import re
import unicodedata


def _char_range(low: int, high: int) -> str:
    return f"{chr(low)}-{chr(high)}"


_ZERO_WIDTH_AND_BIDI = re.compile(
    "["
    + _char_range(0x200B, 0x200D)
    + chr(0xFEFF)
    + _char_range(0x202A, 0x202E)
    + _char_range(0x2066, 0x2069)
    + "]"
)
_WHITESPACE_RUN = re.compile(r"\s+")
_CONTROL_CHAR = re.compile(r"[\x00-\x1f\x7f-\x9f]")


class ControlCharacterError(ValueError):
    pass


def display_text(raw: str) -> str:
    text = unicodedata.normalize("NFC", raw)
    text = _ZERO_WIDTH_AND_BIDI.sub("", text)
    text = _WHITESPACE_RUN.sub(" ", text).strip()
    if _CONTROL_CHAR.search(text):
        raise ControlCharacterError("control characters are not allowed")
    return text


def normalized_text(display: str) -> str:
    text = display.casefold()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] not in "PS")
    return _WHITESPACE_RUN.sub(" ", text).strip()
