"""Tests for GcsStorage (mock the google-cloud-storage client)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from google.api_core import exceptions as gcp_exceptions

from grabatus_service_core.adapters.storage_gcs import GcsStorage
from grabatus_service_core.contract.io_spec import InputSpec, OutputSpec
from grabatus_service_core.errors import (
    InputNotFoundError,
    InputReadError,
    OutputWriteError,
    UnsupportedSchemeError,
)
from grabatus_service_core.ports.storage import StoragePort
from grabatus_service_core.ports.values import Credentials


def _input(uri: str = "gs://bucket/key") -> InputSpec:
    return InputSpec.model_validate(
        {
            "role": "timeseries",
            "source_uri": uri,
            "format": "json",
            "format_hints": {"format": "json"},
        },
    )


def _output(uri: str = "gs://bucket/out") -> OutputSpec:
    return OutputSpec.model_validate(
        {
            "role": "result",
            "destination_uri": uri,
            "format": "json",
            "format_hints": {"format": "json"},
        },
    )


_CREDS = Credentials(token=b"", token_type="bearer")


def _client_with_blob(blob_mock: MagicMock) -> MagicMock:
    bucket_mock = MagicMock()
    bucket_mock.blob.return_value = blob_mock
    client_mock = MagicMock()
    client_mock.bucket.return_value = bucket_mock
    return client_mock


def test_gcs_storage_satisfies_port() -> None:
    assert isinstance(GcsStorage(client=MagicMock()), StoragePort)


def test_gcs_storage_reads_bytes_from_blob() -> None:
    blob = MagicMock()
    blob.download_as_bytes.return_value = b"hello"
    storage = GcsStorage(client=_client_with_blob(blob))

    data = storage.read(spec=_input(), credentials=_CREDS)

    assert data == b"hello"
    blob.download_as_bytes.assert_called_once()


def test_gcs_storage_translates_not_found() -> None:
    blob = MagicMock()
    blob.download_as_bytes.side_effect = gcp_exceptions.NotFound("missing")
    storage = GcsStorage(client=_client_with_blob(blob))

    with pytest.raises(InputNotFoundError):
        storage.read(spec=_input("gs://bucket/missing"), credentials=_CREDS)


def test_gcs_storage_translates_generic_api_error_to_read_error() -> None:
    blob = MagicMock()
    blob.download_as_bytes.side_effect = gcp_exceptions.Forbidden("denied")
    storage = GcsStorage(client=_client_with_blob(blob))

    with pytest.raises(InputReadError):
        storage.read(spec=_input(), credentials=_CREDS)


def test_gcs_storage_writes_bytes_and_returns_receipt() -> None:
    blob = MagicMock()
    storage = GcsStorage(client=_client_with_blob(blob))

    receipt = storage.write(
        spec=_output("gs://bucket/path/result.json"),
        payload=b"abcde",
        credentials=_CREDS,
    )

    blob.upload_from_string.assert_called_once_with(b"abcde")
    assert receipt.bytes_written == 5
    assert receipt.uri == "gs://bucket/path/result.json"


def test_gcs_storage_translates_write_failure() -> None:
    blob = MagicMock()
    blob.upload_from_string.side_effect = gcp_exceptions.Forbidden("denied")
    storage = GcsStorage(client=_client_with_blob(blob))

    with pytest.raises(OutputWriteError):
        storage.write(spec=_output(), payload=b"x", credentials=_CREDS)


def test_gcs_storage_rejects_non_gs_scheme() -> None:
    storage = GcsStorage(client=MagicMock())

    with pytest.raises(UnsupportedSchemeError):
        storage.read(spec=_input("s3://bucket/key"), credentials=_CREDS)


def test_gcs_storage_rejects_uri_without_blob() -> None:
    storage = GcsStorage(client=MagicMock())

    with pytest.raises(UnsupportedSchemeError, match="bucket"):
        storage.read(spec=_input("gs://bucket"), credentials=_CREDS)


def test_gcs_storage_retries_transient_errors() -> None:
    blob = MagicMock()
    blob.download_as_bytes.side_effect = [
        gcp_exceptions.ServiceUnavailable("503"),
        b"recovered",
    ]
    storage = GcsStorage(client=_client_with_blob(blob))

    data = storage.read(spec=_input(), credentials=_CREDS)

    assert data == b"recovered"
    assert blob.download_as_bytes.call_count == 2


def test_gcs_storage_retries_write_on_transient_errors() -> None:
    blob = MagicMock()
    blob.upload_from_string.side_effect = [
        gcp_exceptions.ServiceUnavailable("503"),
        None,
    ]
    storage = GcsStorage(client=_client_with_blob(blob))

    receipt = storage.write(spec=_output(), payload=b"x", credentials=_CREDS)

    assert receipt.bytes_written == 1
    assert blob.upload_from_string.call_count == 2
