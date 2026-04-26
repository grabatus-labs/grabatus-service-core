"""Tests for the safe URI parser."""

from __future__ import annotations

import pytest

from grabatus_service_core.errors import UnsupportedSchemeError
from grabatus_service_core.security.uri_parser import ParsedUri, parse_uri


def test_parse_uri_extracts_scheme_host_path() -> None:
    parsed = parse_uri("gs://my-bucket/path/to/file.xlsx")

    assert parsed.scheme == "gs"
    assert parsed.host == "my-bucket"
    assert parsed.path == "/path/to/file.xlsx"


def test_parse_uri_lowercases_scheme() -> None:
    parsed = parse_uri("GS://Bucket/Path")

    assert parsed.scheme == "gs"


def test_parse_uri_preserves_path_case() -> None:
    parsed = parse_uri("gs://bucket/Path/To/File")

    assert parsed.path == "/Path/To/File"


def test_parse_uri_rejects_empty_string() -> None:
    with pytest.raises(UnsupportedSchemeError, match="empty"):
        parse_uri("")


def test_parse_uri_rejects_missing_scheme() -> None:
    with pytest.raises(UnsupportedSchemeError, match="scheme"):
        parse_uri("//bucket/path")


def test_parse_uri_rejects_path_traversal_in_path() -> None:
    with pytest.raises(UnsupportedSchemeError, match="traversal"):
        parse_uri("gs://bucket/safe/../../escape")


def test_parse_uri_rejects_double_slash_after_path() -> None:
    with pytest.raises(UnsupportedSchemeError, match="path"):
        parse_uri("gs://bucket//path")


def test_parsed_uri_is_frozen() -> None:
    parsed = parse_uri("gs://bucket/path")

    with pytest.raises((AttributeError, TypeError)):
        parsed.scheme = "s3"  # type: ignore[misc]


def test_parse_uri_handles_inline_scheme() -> None:
    parsed = parse_uri("inline://base64,SGVsbG8=")

    assert parsed.scheme == "inline"


def test_parsed_uri_carries_required_fields() -> None:
    p = ParsedUri(scheme="gs", host="b", path="/p")

    assert (p.scheme, p.host, p.path) == ("gs", "b", "/p")
