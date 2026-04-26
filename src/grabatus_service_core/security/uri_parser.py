"""Safe URI parser used by every security primitive.

Rejects empty input, missing scheme, double-slash path components, and
any path containing ``..`` segments. All checks happen here so that the
allowlist, blocklist, and tenant policy can trust the parsed result.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from grabatus_service_core.errors import UnsupportedSchemeError

_TRAVERSAL_SEGMENT = ".."


@dataclass(frozen=True, slots=True)
class ParsedUri:
    """Normalized parts of a URI used by security primitives."""

    scheme: str
    host: str
    path: str


def parse_uri(uri: str) -> ParsedUri:
    """Parse and validate ``uri``; raise ``UnsupportedSchemeError`` on bad input."""
    if not uri:
        raise UnsupportedSchemeError(
            f"URI is empty, expected scheme://host/path, got uri={uri!r}",
        )
    parsed = urlparse(uri)
    if not parsed.scheme:
        raise UnsupportedSchemeError(
            f"URI is missing a scheme, got uri={uri!r}",
        )
    path = parsed.path
    if "//" in path:
        raise UnsupportedSchemeError(
            f"URI path contains '//', got uri={uri!r}",
        )
    segments = [seg for seg in path.split("/") if seg]
    if _TRAVERSAL_SEGMENT in segments:
        raise UnsupportedSchemeError(
            f"URI path contains '..' traversal segment, got uri={uri!r}",
        )
    return ParsedUri(
        scheme=parsed.scheme.lower(),
        host=parsed.netloc,
        path=path,
    )
