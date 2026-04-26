"""FrozenClock: deterministic clock for tests."""

from __future__ import annotations

from datetime import datetime, timedelta


class FrozenClock:
    """Clock fixed at a configurable instant; ``advance`` mutates state."""

    def __init__(self, iso_string: str) -> None:
        self._now = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        self._monotonic = 0.0

    def now(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._monotonic

    def advance(self, *, seconds: float) -> None:
        self._now = self._now + timedelta(seconds=seconds)
        self._monotonic = self._monotonic + seconds
