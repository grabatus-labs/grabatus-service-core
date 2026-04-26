"""HostBlocklist: prevents SSRF and access to internal-only hosts."""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Self

from grabatus_service_core.errors import BlockedHostError
from grabatus_service_core.security.uri_parser import parse_uri

if TYPE_CHECKING:
    from collections.abc import Iterable


_HTTP_SCHEMES = frozenset({"http", "https"})
_BLOCKED_LITERAL_HOSTS = frozenset({"localhost"})
_BLOCKED_DOMAIN_SUFFIXES = (".internal", ".local")
_BLOCKED_NETWORKS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)


@dataclass(frozen=True, slots=True)
class HostBlocklist:
    """Reject HTTP URIs that point at metadata, loopback, RFC1918, or .internal hosts.

    When ``allowed_hosts`` is non-empty, it acts as an additional positive
    allowlist: only those hosts are accepted, regardless of blocklist
    matching. Non-HTTP schemes are not checked here — they go through
    other primitives.
    """

    allowed_hosts: frozenset[str]

    def __init__(self, allowed_hosts: Iterable[str] | None = None) -> None:
        items = frozenset(h.lower() for h in (allowed_hosts or ()))
        object.__setattr__(self, "allowed_hosts", items)

    @classmethod
    def production(cls) -> Self:
        """Default: blocklist active, no positive allowlist."""
        return cls()

    @classmethod
    def from_env_csv(cls, csv: str) -> Self:
        items = [piece.strip() for piece in csv.split(",") if piece.strip()]
        return cls(allowed_hosts=items)

    def check(self, uri: str) -> None:
        parsed = parse_uri(uri)
        if parsed.scheme not in _HTTP_SCHEMES:
            return
        host = self._extract_host(parsed.host)
        if self.allowed_hosts:
            if host not in self.allowed_hosts:
                raise BlockedHostError(
                    f"host={host!r} not in allowed_hosts "
                    f"{sorted(self.allowed_hosts)!r}, uri={uri!r}",
                )
            return
        self._raise_if_blocked(host=host, uri=uri)

    @staticmethod
    def _extract_host(netloc: str) -> str:
        return netloc.split(":", 1)[0].lower()

    @staticmethod
    def _raise_if_blocked(*, host: str, uri: str) -> None:
        if host in _BLOCKED_LITERAL_HOSTS:
            raise BlockedHostError(
                f"host={host!r} is in literal blocklist, uri={uri!r}",
            )
        if any(host.endswith(suffix) for suffix in _BLOCKED_DOMAIN_SUFFIXES):
            raise BlockedHostError(
                f"host={host!r} matches blocked suffix {_BLOCKED_DOMAIN_SUFFIXES!r}, uri={uri!r}",
            )
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return
        for network in _BLOCKED_NETWORKS:
            if address in network:
                raise BlockedHostError(
                    f"host={host!r} resolves to blocked network {network!r}, uri={uri!r}",
                )
