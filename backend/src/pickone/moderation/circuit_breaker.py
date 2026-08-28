from __future__ import annotations

from datetime import datetime

from pickone.core.clock import Clock, get_clock


class CircuitBreaker:
    def __init__(
        self, *, threshold: int, cooldown_seconds: float, clock: Clock | None = None
    ) -> None:
        self._threshold = threshold
        self._cooldown_seconds = cooldown_seconds
        self._clock = clock or get_clock()
        self._consecutive_failures = 0
        self._opened_at: datetime | None = None

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._threshold:
            self._opened_at = self._clock.now()

    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        elapsed = (self._clock.now() - self._opened_at).total_seconds()
        if elapsed >= self._cooldown_seconds:
            self._opened_at = None
            self._consecutive_failures = 0
            return False
        return True


_breaker: CircuitBreaker | None = None


def get_circuit_breaker() -> CircuitBreaker:
    global _breaker
    if _breaker is None:
        from pickone.core.config import get_settings

        settings = get_settings()
        _breaker = CircuitBreaker(
            threshold=settings.moderation_circuit_breaker_threshold,
            cooldown_seconds=settings.moderation_circuit_breaker_cooldown_seconds,
        )
    return _breaker


def reset_circuit_breaker() -> None:
    global _breaker
    _breaker = None
