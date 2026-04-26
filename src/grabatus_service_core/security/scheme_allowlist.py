"""SchemeAllowlist: enforces GBT_ALLOWED_SCHEMES at request boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from grabatus_service_core.errors import UnsupportedSchemeError
from grabatus_service_core.security.uri_parser import parse_uri

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True, slots=True)
class SchemeAllowlist:
    """Reject URIs whose scheme is not in ``allowed``.

    The allowlist is a closed set: the library default is narrow
    (gs, bigquery, secret) and configuration may only narrow it further.
    """

    allowed: frozenset[str]

    def __init__(self, allowed: Iterable[str]) -> None:
        object.__setattr__(self, "allowed", frozenset(s.lower() for s in allowed))

    def check(self, uri: str) -> None:
        parsed = parse_uri(uri)
        if parsed.scheme not in self.allowed:
            raise UnsupportedSchemeError(
                f"scheme={parsed.scheme!r} not in allowed schemes "
                f"{sorted(self.allowed)!r}, uri={uri!r}",
            )

    @classmethod
    def from_env_csv(cls, csv: str) -> Self:
        """Build an allowlist from a comma-separated env var value."""
        items = [piece.strip() for piece in csv.split(",") if piece.strip()]
        return cls(allowed=items)
