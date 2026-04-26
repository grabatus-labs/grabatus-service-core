"""Tests for InlineStorage."""

from __future__ import annotations

import pytest

from grabatus_service_core.adapters.storage_inline import InlineStorage
from grabatus_service_core.contract.io_spec import InputSpec, OutputSpec
from grabatus_service_core.errors import (
    FormatParsingError,
    InputReadError,
    OutputWriteError,
    UnsupportedSchemeError,
)
from grabatus_service_core.ports.storage import StoragePort
from grabatus_service_core.ports.values import Credentials


def _input(uri: str) -> InputSpec:
    return InputSpec.model_validate(
        {
            "role": "timeseries",
            "source_uri": uri,
            "format": "inline",
            "format_hints": {"format": "inline"},
        },
    )


def _output(uri: str) -> OutputSpec:
    return OutputSpec.model_validate(
        {
            "role": "result",
            "destination_uri": uri,
            "format": "inline",
            "format_hints": {"format": "inline"},
        },
    )


_CREDS = Credentials(token=b"", token_type="bearer")


def test_inline_storage_satisfies_port() -> None:
    assert isinstance(InlineStorage(), StoragePort)


def test_inline_storage_decodes_base64() -> None:
    # base64("hello") = "aGVsbG8="
    data = InlineStorage().read(
        spec=_input("inline://base64,aGVsbG8="),
        credentials=_CREDS,
    )

    assert data == b"hello"


def test_inline_storage_decodes_utf8() -> None:
    data = InlineStorage().read(
        spec=_input("inline://utf8,hello%20world"),
        credentials=_CREDS,
    )

    assert data == b"hello%20world"


def test_inline_storage_rejects_non_inline_scheme() -> None:
    with pytest.raises(UnsupportedSchemeError):
        InlineStorage().read(spec=_input("gs://bucket/key"), credentials=_CREDS)


def test_inline_storage_rejects_missing_data() -> None:
    with pytest.raises(InputReadError, match="missing data"):
        InlineStorage().read(spec=_input("inline://base64,"), credentials=_CREDS)


def test_inline_storage_rejects_unknown_encoding() -> None:
    with pytest.raises(UnsupportedSchemeError, match="encoding"):
        InlineStorage().read(spec=_input("inline://hex,deadbeef"), credentials=_CREDS)


def test_inline_storage_reports_invalid_base64() -> None:
    with pytest.raises(FormatParsingError):
        InlineStorage().read(
            spec=_input("inline://base64,not-valid-base64!!!"),
            credentials=_CREDS,
        )


def test_inline_storage_write_is_not_supported() -> None:
    with pytest.raises(OutputWriteError):
        InlineStorage().write(
            spec=_output("inline://utf8,x"),
            payload=b"data",
            credentials=_CREDS,
        )
