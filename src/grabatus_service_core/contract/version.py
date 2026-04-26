"""Protocol version constants and compatibility helpers."""

from __future__ import annotations

from typing import Final

SUPPORTED_PROTOCOL_VERSIONS: Final[frozenset[str]] = frozenset({"1.0"})


def is_protocol_version_supported(version: str) -> bool:
    """Return True iff this library supports the given protocol_version.

    Used by the runner to fail fast with
    ``UnsupportedProtocolVersionError`` before deeper validation runs.
    """
    return version in SUPPORTED_PROTOCOL_VERSIONS
