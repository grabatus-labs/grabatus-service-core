"""Shared test fixtures and Hypothesis profiles for grabatus_service_core."""

from __future__ import annotations

import os

from hypothesis import HealthCheck, settings

# Under mutation testing the suite runs inside mutmut's `mutants/` copy, on
# a cold import cache and with every core busy. Hypothesis' 200 ms
# per-example deadline fires there on tests that are comfortably fast
# otherwise, and mutmut aborts before evaluating a single mutant. Wall-clock
# is not the property these tests assert.
settings.register_profile(
    "mutation",
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "default"))
