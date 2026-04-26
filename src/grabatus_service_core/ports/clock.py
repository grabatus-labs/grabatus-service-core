"""ClockPort: abstract over wall-clock time for testability."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime


@runtime_checkable
class ClockPort(Protocol):
    """Abstract clock; tests inject FrozenClock for determinism."""

    def now(self) -> datetime:
        """Return the current timezone-aware UTC datetime."""
        ...

    def monotonic(self) -> float:
        """Return a monotonic counter in seconds for duration measurement."""
        ...
