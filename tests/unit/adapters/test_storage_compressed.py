"""CompressedStorage: gzip/zstd round-trip on top of any inner StoragePort."""

import gzip

import pytest

from grabatus_service_core.adapters.storage_compressed import CompressedStorage
from grabatus_service_core.errors import InputReadError
from grabatus_service_core.ports.values import Credentials
from grabatus_service_core.testing.factories import (
    make_input_spec,
    make_output_spec,
)
from grabatus_service_core.testing.storage import InMemoryStorage

_NO_CREDS = Credentials(token=b"", token_type="none")


def test_no_compression_writes_payload_verbatim() -> None:
    inner = InMemoryStorage()
    decorator = CompressedStorage(inner=inner)
    out_spec = make_output_spec(compression="none")
    decorator.write(spec=out_spec, payload=b"hello", credentials=_NO_CREDS)
    in_spec = make_input_spec(
        source_uri=str(out_spec.destination_uri),
        compression="none",
    )
    assert decorator.read(spec=in_spec, credentials=_NO_CREDS) == b"hello"


def test_gzip_write_stores_compressed_bytes() -> None:
    inner = InMemoryStorage()
    decorator = CompressedStorage(inner=inner)
    out_spec = make_output_spec(compression="gzip")
    plaintext = b"the quick brown fox jumps over the lazy dog"
    decorator.write(spec=out_spec, payload=plaintext, credentials=_NO_CREDS)
    # Read raw via inner storage with a no-compression InputSpec to confirm gzipped on disk.
    raw_in_spec = make_input_spec(
        source_uri=str(out_spec.destination_uri),
        compression="none",
    )
    raw = inner.read(spec=raw_in_spec, credentials=_NO_CREDS)
    assert raw != plaintext
    assert gzip.decompress(raw) == plaintext


def test_gzip_round_trips_via_decorator() -> None:
    inner = InMemoryStorage()
    decorator = CompressedStorage(inner=inner)
    out_spec = make_output_spec(compression="gzip")
    decorator.write(spec=out_spec, payload=b"payload", credentials=_NO_CREDS)
    in_spec = make_input_spec(
        source_uri=str(out_spec.destination_uri),
        compression="gzip",
    )
    assert decorator.read(spec=in_spec, credentials=_NO_CREDS) == b"payload"


def test_gzip_read_raises_on_corrupt_input() -> None:
    inner = InMemoryStorage(seed={"gs://bucket/garbage": b"not gzip data"})
    decorator = CompressedStorage(inner=inner)
    in_spec = make_input_spec(
        source_uri="gs://bucket/garbage",
        compression="gzip",
    )
    with pytest.raises(InputReadError, match=r"gzip"):
        decorator.read(spec=in_spec, credentials=_NO_CREDS)


def test_zstd_round_trips_via_decorator() -> None:
    inner = InMemoryStorage()
    decorator = CompressedStorage(inner=inner)
    out_spec = make_output_spec(compression="zstd")
    decorator.write(spec=out_spec, payload=b"zstandard test", credentials=_NO_CREDS)
    in_spec = make_input_spec(
        source_uri=str(out_spec.destination_uri),
        compression="zstd",
    )
    assert decorator.read(spec=in_spec, credentials=_NO_CREDS) == b"zstandard test"


def test_zstd_read_raises_on_corrupt_input() -> None:
    inner = InMemoryStorage(seed={"gs://bucket/garbage": b"not zstd data"})
    decorator = CompressedStorage(inner=inner)
    in_spec = make_input_spec(
        source_uri="gs://bucket/garbage",
        compression="zstd",
    )
    with pytest.raises(InputReadError, match=r"zstd"):
        decorator.read(spec=in_spec, credentials=_NO_CREDS)


def test_receipt_bytes_written_reflects_compressed_size() -> None:
    inner = InMemoryStorage()
    decorator = CompressedStorage(inner=inner)
    out_spec = make_output_spec(compression="gzip")
    payload = b"x" * 10_000  # very compressible
    receipt = decorator.write(spec=out_spec, payload=payload, credentials=_NO_CREDS)
    assert receipt.bytes_written < len(payload)
