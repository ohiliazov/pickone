"""The clock is injectable, so expiry is testable without sleeping."""

from __future__ import annotations

from datetime import UTC, datetime

from pickone.core.clock import FrozenClock, SystemClock, get_clock, set_clock


def test_system_clock_is_timezone_aware() -> None:
    now = SystemClock().now()
    assert now.tzinfo is not None
    assert now.utcoffset() == UTC.utcoffset(None)


def test_frozen_clock_does_not_move_on_its_own() -> None:
    clock = FrozenClock()
    assert clock.now() == clock.now()


def test_frozen_clock_advances_by_hand() -> None:
    clock = FrozenClock(datetime(2026, 1, 1, tzinfo=UTC))
    clock.advance(seconds=61)
    assert clock.now() == datetime(2026, 1, 1, 0, 1, 1, tzinfo=UTC)


def test_clock_is_swappable(frozen_clock: FrozenClock) -> None:
    assert get_clock() is frozen_clock


def test_clock_is_restored_after_the_fixture() -> None:
    set_clock(SystemClock())
    assert isinstance(get_clock(), SystemClock)
