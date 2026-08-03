"""Duplicate detection shared by every contract collection keyed by a string.

Input roles, output roles, finding ids, artifact roles and digest roles all
enforce the same invariant and all report it the same way. Written once so
the message stays identical wherever it fires.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


def duplicated(values: Iterable[str]) -> list[str]:
    """Return the values appearing more than once, sorted for a stable message."""
    seen: set[str] = set()
    repeated: set[str] = set()
    for value in values:
        if value in seen:
            repeated.add(value)
        seen.add(value)
    return sorted(repeated)
