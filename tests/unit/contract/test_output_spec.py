"""Tests for the OutputSpec schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.io_spec import OutputSpec


def _valid_output() -> dict[str, object]:
    return {
        "role": "forecast_json",
        "destination_uri": "gs://bucket/path/result.json.gz",
        "format": "json",
        "format_hints": {"format": "json"},
    }


def test_output_spec_accepts_minimal_payload_uses_defaults() -> None:
    spec = OutputSpec.model_validate(_valid_output())

    assert spec.compression == "none"
    assert spec.write_mode == "overwrite"


@pytest.mark.parametrize("compression", ["none", "gzip", "zstd"])
def test_output_spec_accepts_known_compressions(compression: str) -> None:
    payload = _valid_output() | {"compression": compression}

    spec = OutputSpec.model_validate(payload)

    assert spec.compression == compression


def test_output_spec_rejects_unknown_compression() -> None:
    payload = _valid_output() | {"compression": "lz4"}

    with pytest.raises(ValidationError, match="compression"):
        OutputSpec.model_validate(payload)


@pytest.mark.parametrize("mode", ["overwrite", "append", "fail_if_exists"])
def test_output_spec_accepts_known_write_modes(mode: str) -> None:
    payload = _valid_output() | {"write_mode": mode}

    spec = OutputSpec.model_validate(payload)

    assert spec.write_mode == mode


def test_output_spec_rejects_unknown_write_mode() -> None:
    payload = _valid_output() | {"write_mode": "upsert"}

    with pytest.raises(ValidationError, match="write_mode"):
        OutputSpec.model_validate(payload)


def test_output_spec_format_must_match_hints() -> None:
    payload = _valid_output() | {
        "format": "csv",
        "format_hints": {"format": "json"},
    }

    with pytest.raises(ValidationError, match="format"):
        OutputSpec.model_validate(payload)


def test_output_spec_is_frozen() -> None:
    spec = OutputSpec.model_validate(_valid_output())

    with pytest.raises(ValidationError, match="frozen"):
        spec.compression = "gzip"  # type: ignore[misc]
