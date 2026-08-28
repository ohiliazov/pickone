from __future__ import annotations

STARTER_BLOCKLIST = frozenset({"kill yourself", "kys"})


def contains_blocked_term(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in STARTER_BLOCKLIST)
