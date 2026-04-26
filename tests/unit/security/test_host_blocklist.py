"""Tests for HostBlocklist."""

from __future__ import annotations

import pytest

from grabatus_service_core.errors import BlockedHostError
from grabatus_service_core.security.host_blocklist import HostBlocklist


def test_blocklist_allows_public_https_host() -> None:
    blocklist = HostBlocklist.production()

    blocklist.check("https://api.grabatus.com/webhook")  # no raise


@pytest.mark.parametrize(
    "uri",
    [
        "http://169.254.169.254/computeMetadata/v1/",
        "https://169.254.169.254/foo",
        "http://127.0.0.1:8080/x",
        "http://localhost/x",
        "http://10.0.0.5/x",
        "http://10.255.255.255/x",
        "http://example.internal/x",
        "http://services.local/x",
    ],
)
def test_blocklist_rejects_metadata_and_internal_hosts(uri: str) -> None:
    blocklist = HostBlocklist.production()

    with pytest.raises(BlockedHostError):
        blocklist.check(uri)


def test_blocklist_only_applies_to_http_schemes() -> None:
    blocklist = HostBlocklist.production()

    blocklist.check("gs://internal-bucket/path")  # no raise — not HTTP


def test_blocklist_allows_explicit_allowed_host() -> None:
    blocklist = HostBlocklist(
        allowed_hosts={"api.partner.com"},
    )

    blocklist.check("https://api.partner.com/x")


def test_blocklist_with_explicit_allowlist_rejects_others() -> None:
    blocklist = HostBlocklist(allowed_hosts={"api.partner.com"})

    with pytest.raises(BlockedHostError, match=r"api\.other\.com"):
        blocklist.check("https://api.other.com/x")


def test_blocklist_from_env_csv_parses_allowed_hosts() -> None:
    blocklist = HostBlocklist.from_env_csv("api.partner.com, api.grabatus.com")

    assert blocklist.allowed_hosts == frozenset(
        {"api.partner.com", "api.grabatus.com"},
    )


def test_blocklist_from_empty_env_uses_no_allowlist() -> None:
    blocklist = HostBlocklist.from_env_csv("")

    assert blocklist.allowed_hosts == frozenset()


def test_blocklist_passes_when_no_match() -> None:
    blocklist = HostBlocklist.production()

    blocklist.check("https://example.com/x")  # public DNS, no raise


def test_blocklist_passes_for_public_ip() -> None:
    """Branch coverage: valid IP that does not fall in any blocked network."""
    blocklist = HostBlocklist.production()

    blocklist.check("https://8.8.8.8/dns")  # public DNS IP, no raise
