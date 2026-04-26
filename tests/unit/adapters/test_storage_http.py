"""Tests for HttpFetchStorage (mock httpx)."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from grabatus_service_core.adapters.storage_http import HttpFetchStorage
from grabatus_service_core.contract.io_spec import InputSpec, OutputSpec
from grabatus_service_core.errors import (
    BlockedHostError,
    InputNotFoundError,
    InputReadError,
    OutputWriteError,
    UnsupportedSchemeError,
)
from grabatus_service_core.ports.storage import StoragePort
from grabatus_service_core.ports.values import Credentials
from grabatus_service_core.security.host_blocklist import HostBlocklist


def _input(uri: str = "https://api.partner.com/data.json") -> InputSpec:
    return InputSpec.model_validate(
        {
            "role": "timeseries",
            "source_uri": uri,
            "format": "json",
            "format_hints": {"format": "json"},
        },
    )


def _output(uri: str = "https://api.partner.com/x") -> OutputSpec:
    return OutputSpec.model_validate(
        {
            "role": "result",
            "destination_uri": uri,
            "format": "json",
            "format_hints": {"format": "json"},
        },
    )


def _allowlist() -> HostBlocklist:
    return HostBlocklist(allowed_hosts={"api.partner.com"})


def _client_returning(status: int, body: bytes = b"") -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.content = body
    client = MagicMock()
    client.get.return_value = response
    return client


def test_http_storage_satisfies_port() -> None:
    assert isinstance(
        HttpFetchStorage(host_blocklist=_allowlist(), client=MagicMock()),
        StoragePort,
    )


def test_http_storage_returns_body_on_2xx() -> None:
    storage = HttpFetchStorage(
        host_blocklist=_allowlist(),
        client=_client_returning(200, b"hello"),
    )

    data = storage.read(
        spec=_input(),
        credentials=Credentials(token=b"", token_type="bearer"),
    )

    assert data == b"hello"


def test_http_storage_raises_input_not_found_on_404() -> None:
    storage = HttpFetchStorage(
        host_blocklist=_allowlist(),
        client=_client_returning(404),
    )

    with pytest.raises(InputNotFoundError):
        storage.read(
            spec=_input(),
            credentials=Credentials(token=b"", token_type="bearer"),
        )


def test_http_storage_raises_read_error_on_other_non_2xx() -> None:
    storage = HttpFetchStorage(
        host_blocklist=_allowlist(),
        client=_client_returning(500),
    )

    with pytest.raises(InputReadError, match="500"):
        storage.read(
            spec=_input(),
            credentials=Credentials(token=b"", token_type="bearer"),
        )


def test_http_storage_rejects_non_http_scheme() -> None:
    storage = HttpFetchStorage(host_blocklist=_allowlist(), client=MagicMock())

    with pytest.raises(UnsupportedSchemeError):
        storage.read(
            spec=_input("gs://bucket/key"),
            credentials=Credentials(token=b"", token_type="bearer"),
        )


def test_http_storage_blocks_metadata_host() -> None:
    storage = HttpFetchStorage(
        host_blocklist=HostBlocklist.production(),
        client=MagicMock(),
    )

    with pytest.raises(BlockedHostError):
        storage.read(
            spec=_input("http://169.254.169.254/computeMetadata/v1/"),
            credentials=Credentials(token=b"", token_type="bearer"),
        )


def test_http_storage_passes_authorization_header_when_token_provided() -> None:
    client = _client_returning(200, b"x")
    storage = HttpFetchStorage(host_blocklist=_allowlist(), client=client)

    storage.read(
        spec=_input(),
        credentials=Credentials(token=b"abc", token_type="bearer"),
    )

    _, kwargs = client.get.call_args
    assert kwargs["headers"]["Authorization"] == "Bearer abc"


def test_http_storage_translates_httpx_error_to_input_read_error() -> None:
    client = MagicMock()
    client.get.side_effect = httpx.HTTPError("boom")
    storage = HttpFetchStorage(host_blocklist=_allowlist(), client=client)

    with pytest.raises(InputReadError, match="boom"):
        storage.read(
            spec=_input(),
            credentials=Credentials(token=b"", token_type="bearer"),
        )


def test_http_storage_retries_on_timeout_then_succeeds() -> None:
    client = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.content = b"ok"
    client.get.side_effect = [httpx.TimeoutException("slow"), response]
    storage = HttpFetchStorage(host_blocklist=_allowlist(), client=client)

    data = storage.read(
        spec=_input(),
        credentials=Credentials(token=b"", token_type="bearer"),
    )

    assert data == b"ok"
    assert client.get.call_count == 2


def test_http_storage_write_is_not_supported() -> None:
    storage = HttpFetchStorage(host_blocklist=_allowlist(), client=MagicMock())

    with pytest.raises(OutputWriteError):
        storage.write(
            spec=_output(),
            payload=b"x",
            credentials=Credentials(token=b"", token_type="bearer"),
        )
