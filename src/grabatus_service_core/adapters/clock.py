"""SystemClock: real wall-clock + monotonic time backed by stdlib."""

from __future__ import annotations

import time
from datetime import UTC, datetime


class SystemClock:
    """Production ClockPort: returns real UTC time and process-wide monotonic seconds."""

    def now(self) -> datetime:
        return datetime.now(tz=UTC)

    def monotonic(self) -> float:
        return time.monotonic()
