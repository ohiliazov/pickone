from __future__ import annotations

import re
import unicodedata

MAX_SLUG_LENGTH = 64

_NON_ALNUM_RUN = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in ascii_text if not unicodedata.combining(ch))
    ascii_text = ascii_text.encode("ascii", "ignore").decode("ascii")
    hyphenated = _NON_ALNUM_RUN.sub("-", ascii_text.lower()).strip("-")
    reserved_fixed = hyphenated.replace("-vs-", "-versus-")
    return _truncate_at_word_boundary(reserved_fixed, MAX_SLUG_LENGTH)


def _truncate_at_word_boundary(slug: str, max_length: int) -> str:
    if len(slug) <= max_length:
        return slug
    truncated = slug[:max_length]
    if slug[max_length] != "-" and "-" in truncated:
        truncated = truncated.rsplit("-", 1)[0]
    return truncated
