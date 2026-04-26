"""Tests for LocalFsStorage."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from grabatus_service_core.adapters.storage_localfs import LocalFsStorage
from grabatus_service_core.contract.io_spec import InputSpec, OutputSpec
from grabatus_service_core.errors import (
    InputNotFoundError,
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


def test_local_fs_satisfies_port() -> None:
    assert isinstance(LocalFsStorage(), StoragePort)


def test_local_fs_round_trips_bytes(tmp_path: Path) -> None:
    storage = LocalFsStorage()
    target = tmp_path / "sub" / "file.bin"

    receipt = storage.write(
        spec=_output(f"file:///{target.as_posix().lstrip('/')}"),
        payload=b"hello",
        credentials=_CREDS,
    )

    data = storage.read(
        spec=_input(f"file:///{target.as_posix().lstrip('/')}"),
        credentials=_CREDS,
    )

    assert receipt.bytes_written == 5
    assert data == b"hello"


def test_local_fs_read_raises_when_file_missing(tmp_path: Path) -> None:
    target = tmp_path / "missing.bin"

    with pytest.raises(InputNotFoundError):
        LocalFsStorage().read(
            spec=_input(f"file:///{target.as_posix().lstrip('/')}"),
            credentials=_CREDS,
        )


def test_local_fs_rejects_non_file_scheme() -> None:
    with pytest.raises(UnsupportedSchemeError):
        LocalFsStorage().read(spec=_input("gs://bucket/key"), credentials=_CREDS)


def test_local_fs_root_blocks_paths_outside(tmp_path: Path) -> None:
    inside_root = tmp_path / "scoped"
    inside_root.mkdir()
    storage = LocalFsStorage(root=inside_root)

    with pytest.raises(UnsupportedSchemeError, match="escapes"):
        storage.read(spec=_input("file:///etc/passwd"), credentials=_CREDS)


def test_local_fs_write_translates_oserror_to_output_write_error(
    tmp_path: Path,
) -> None:
    target = tmp_path / "out.bin"

    with (
        patch("pathlib.Path.write_bytes", side_effect=OSError("disk full")),
        pytest.raises(OutputWriteError, match="disk full"),
    ):
        LocalFsStorage().write(
            spec=_output(f"file:///{target.as_posix().lstrip('/')}"),
            payload=b"x",
            credentials=_CREDS,
        )


def test_local_fs_read_translates_oserror_to_input_read_error(
    tmp_path: Path,
) -> None:
    target = tmp_path / "f.bin"
    target.write_bytes(b"x")

    with (
        patch("pathlib.Path.read_bytes", side_effect=OSError("perm denied")),
        pytest.raises(InputReadError, match="perm denied"),
    ):
        LocalFsStorage().read(
            spec=_input(f"file:///{target.as_posix().lstrip('/')}"),
            credentials=_CREDS,
        )
