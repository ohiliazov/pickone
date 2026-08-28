from __future__ import annotations

from pickone.core.clock import FrozenClock
from pickone.core.config import get_settings
from pickone.moderation.circuit_breaker import (
    CircuitBreaker,
    get_circuit_breaker,
    reset_circuit_breaker,
)


def test_starts_closed() -> None:
    breaker = CircuitBreaker(threshold=3, cooldown_seconds=60, clock=FrozenClock())
    assert not breaker.is_open()


def test_stays_closed_below_the_threshold() -> None:
    breaker = CircuitBreaker(threshold=3, cooldown_seconds=60, clock=FrozenClock())
    breaker.record_failure()
    breaker.record_failure()
    assert not breaker.is_open()


def test_opens_at_the_threshold() -> None:
    breaker = CircuitBreaker(threshold=3, cooldown_seconds=60, clock=FrozenClock())
    for _ in range(3):
        breaker.record_failure()
    assert breaker.is_open()


def test_success_resets_the_failure_count() -> None:
    breaker = CircuitBreaker(threshold=3, cooldown_seconds=60, clock=FrozenClock())
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()
    breaker.record_failure()
    breaker.record_failure()
    assert not breaker.is_open()


def test_closes_again_after_the_cooldown_elapses() -> None:
    clock = FrozenClock()
    breaker = CircuitBreaker(threshold=3, cooldown_seconds=60, clock=clock)
    for _ in range(3):
        breaker.record_failure()
    assert breaker.is_open()
    clock.advance(seconds=59)
    assert breaker.is_open()
    clock.advance(seconds=2)
    assert not breaker.is_open()


def test_get_circuit_breaker_returns_the_same_instance() -> None:
    reset_circuit_breaker()
    try:
        assert get_circuit_breaker() is get_circuit_breaker()
    finally:
        reset_circuit_breaker()


def test_reset_circuit_breaker_clears_state() -> None:
    reset_circuit_breaker()
    try:
        breaker = get_circuit_breaker()
        for _ in range(get_settings().moderation_circuit_breaker_threshold):
            breaker.record_failure()
        assert breaker.is_open()
        reset_circuit_breaker()
        assert not get_circuit_breaker().is_open()
    finally:
        reset_circuit_breaker()
