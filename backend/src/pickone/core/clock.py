"""An injectable clock.

Every timestamp in the system goes through this. It is what makes battle
expiry testable without ``sleep`` — M4's expiry tests depend on it entirely,
so it exists from the first commit rather than being retrofitted.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Timezone-aware UTC. Never a naive datetime."""
        ...


class SystemClock:
    """The real clock. The default everywhere outside tests."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class FrozenClock:
    """A clock tests can move by hand.

    Battle expiry is a 60-second window; asserting on it with real time would
    make the suite slow and flaky. Tests advance this instead.
    """

    def __init__(self, at: datetime | None = None) -> None:
        self._now = at or datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float = 0, **kwargs: float) -> datetime:
        self._now += timedelta(seconds=seconds, **kwargs)
        return self._now

    def set(self, at: datetime) -> datetime:
        self._now = at
        return self._now


_clock: Clock = SystemClock()


def get_clock() -> Clock:
    """FastAPI dependency and general accessor."""
    return _clock


def set_clock(clock: Clock) -> None:
    """Test seam. Production code must never call this."""
    global _clock
    _clock = clock
