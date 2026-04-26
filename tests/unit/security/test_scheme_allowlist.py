"""Tests for SchemeAllowlist."""

from __future__ import annotations

import pytest

from grabatus_service_core.errors import UnsupportedSchemeError
from grabatus_service_core.security.scheme_allowlist import SchemeAllowlist


def test_allowlist_accepts_listed_scheme() -> None:
    allowlist = SchemeAllowlist(allowed={"gs", "bigquery"})

    allowlist.check("gs://bucket/path")  # no raise


def test_allowlist_rejects_unlisted_scheme() -> None:
    allowlist = SchemeAllowlist(allowed={"gs"})

    with pytest.raises(UnsupportedSchemeError, match="s3"):
        allowlist.check("s3://bucket/key")


def test_allowlist_normalizes_case() -> None:
    allowlist = SchemeAllowlist(allowed={"gs"})

    allowlist.check("GS://BUCKET/Path")


def test_allowlist_rejects_empty_uri() -> None:
    allowlist = SchemeAllowlist(allowed={"gs"})

    with pytest.raises(UnsupportedSchemeError):
        allowlist.check("")


def test_allowlist_from_env_string_parses_csv() -> None:
    allowlist = SchemeAllowlist.from_env_csv("gs,bigquery,secret")

    assert allowlist.allowed == frozenset({"gs", "bigquery", "secret"})


def test_allowlist_from_env_string_strips_whitespace() -> None:
    allowlist = SchemeAllowlist.from_env_csv("gs , bigquery , secret")

    assert allowlist.allowed == frozenset({"gs", "bigquery", "secret"})


def test_allowlist_from_env_string_lowercases() -> None:
    allowlist = SchemeAllowlist.from_env_csv("GS,BigQuery")

    assert allowlist.allowed == frozenset({"gs", "bigquery"})


def test_allowlist_from_env_empty_string_yields_empty_set() -> None:
    allowlist = SchemeAllowlist.from_env_csv("")

    assert allowlist.allowed == frozenset()
