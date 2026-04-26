"""Tests for CompositeStorage."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from grabatus_service_core.adapters.storage_composite import CompositeStorage
from grabatus_service_core.contract.io_spec import InputSpec, OutputSpec
from grabatus_service_core.errors import UnsupportedSchemeError
from grabatus_service_core.ports.storage import StoragePort
from grabatus_service_core.ports.values import Credentials, WriteReceipt


def _input(uri: str) -> InputSpec:
    return InputSpec.model_validate(
        {
            "role": "timeseries",
            "source_uri": uri,
            "format": "json",
            "format_hints": {"format": "json"},
        },
    )


def _output(uri: str) -> OutputSpec:
    return OutputSpec.model_validate(
        {
            "role": "result",
            "destination_uri": uri,
            "format": "json",
            "format_hints": {"format": "json"},
        },
    )


_CREDS = Credentials(token=b"", token_type="bearer")


def test_composite_satisfies_port() -> None:
    composite = CompositeStorage(by_scheme={"gs": MagicMock()})
    assert isinstance(composite, StoragePort)


def test_composite_routes_read_to_matching_scheme() -> None:
    gs_adapter = MagicMock()
    gs_adapter.read.return_value = b"from-gs"
    file_adapter = MagicMock()
    composite = CompositeStorage(by_scheme={"gs": gs_adapter, "file": file_adapter})

    data = composite.read(spec=_input("gs://b/k"), credentials=_CREDS)

    assert data == b"from-gs"
    gs_adapter.read.assert_called_once()
    file_adapter.read.assert_not_called()


def test_composite_routes_write_to_matching_scheme() -> None:
    gs_adapter = MagicMock()
    receipt = WriteReceipt(uri="gs://b/k", bytes_written=1, request_id_tag="x")
    gs_adapter.write.return_value = receipt
    composite = CompositeStorage(by_scheme={"gs": gs_adapter})

    out = composite.write(spec=_output("gs://b/k"), payload=b"x", credentials=_CREDS)

    assert out is receipt


def test_composite_normalizes_scheme_case() -> None:
    gs_adapter = MagicMock()
    gs_adapter.read.return_value = b"x"
    composite = CompositeStorage(by_scheme={"GS": gs_adapter})

    composite.read(spec=_input("gs://b/k"), credentials=_CREDS)

    gs_adapter.read.assert_called_once()


def test_composite_raises_when_scheme_unmapped() -> None:
    composite = CompositeStorage(by_scheme={"gs": MagicMock()})

    with pytest.raises(UnsupportedSchemeError):
        composite.read(spec=_input("ftp://b/k"), credentials=_CREDS)


def test_composite_raises_on_unmapped_scheme_for_write() -> None:
    composite = CompositeStorage(by_scheme={"gs": MagicMock()})

    with pytest.raises(UnsupportedSchemeError):
        composite.write(spec=_output("ftp://b/k"), payload=b"x", credentials=_CREDS)
