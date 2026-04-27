"""InputSpec mirrors OutputSpec's compression field."""

from __future__ import annotations

from typing import TYPE_CHECKING

from grabatus_service_core.testing.factories import make_input_spec

if TYPE_CHECKING:
    from grabatus_service_core.contract.io_spec import InputSpec


def test_input_spec_default_compression_is_none() -> None:
    spec: InputSpec = make_input_spec()
    assert spec.compression == "none"


def test_input_spec_accepts_gzip_compression() -> None:
    spec: InputSpec = make_input_spec(compression="gzip")
    assert spec.compression == "gzip"


def test_input_spec_accepts_zstd_compression() -> None:
    spec: InputSpec = make_input_spec(compression="zstd")
    assert spec.compression == "zstd"
