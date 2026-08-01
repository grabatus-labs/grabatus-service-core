"""Tests for protocol version compatibility helpers."""

from __future__ import annotations

import pytest

from grabatus_service_core.contract.version import (
    SUPPORTED_PROTOCOL_VERSIONS,
    is_protocol_version_supported,
)


def test_supported_versions_contains_v1_0() -> None:
    assert "1.0" in SUPPORTED_PROTOCOL_VERSIONS


@pytest.mark.parametrize("version", ["1.0", "1.1"])
def test_is_protocol_version_supported_accepts_known(version: str) -> None:
    assert is_protocol_version_supported(version) is True


@pytest.mark.parametrize("version", ["0.9", "2.0", "1.2", "abc", ""])
def test_is_protocol_version_supported_rejects_unknown(version: str) -> None:
    assert is_protocol_version_supported(version) is False
