"""Property: any payload survives a write/read round-trip via any codec."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from grabatus_service_core.adapters.storage_compressed import CompressedStorage
from grabatus_service_core.ports.values import Credentials
from grabatus_service_core.testing.factories import make_input_spec, make_output_spec
from grabatus_service_core.testing.storage import InMemoryStorage

_NO_CREDS = Credentials(token=b"", token_type="none")


@given(payload=st.binary(min_size=0, max_size=4096))
def test_gzip_round_trips_arbitrary_bytes(payload: bytes) -> None:
    inner = InMemoryStorage()
    decorator = CompressedStorage(inner=inner)
    out_spec = make_output_spec(compression="gzip")
    decorator.write(spec=out_spec, payload=payload, credentials=_NO_CREDS)
    in_spec = make_input_spec(
        source_uri=str(out_spec.destination_uri),
        compression="gzip",
    )
    assert decorator.read(spec=in_spec, credentials=_NO_CREDS) == payload


@given(payload=st.binary(min_size=0, max_size=4096))
def test_zstd_round_trips_arbitrary_bytes(payload: bytes) -> None:
    inner = InMemoryStorage()
    decorator = CompressedStorage(inner=inner)
    out_spec = make_output_spec(compression="zstd")
    decorator.write(spec=out_spec, payload=payload, credentials=_NO_CREDS)
    in_spec = make_input_spec(
        source_uri=str(out_spec.destination_uri),
        compression="zstd",
    )
    assert decorator.read(spec=in_spec, credentials=_NO_CREDS) == payload


@given(payload=st.binary(min_size=0, max_size=4096))
def test_no_compression_round_trips_arbitrary_bytes(payload: bytes) -> None:
    inner = InMemoryStorage()
    decorator = CompressedStorage(inner=inner)
    out_spec = make_output_spec(compression="none")
    decorator.write(spec=out_spec, payload=payload, credentials=_NO_CREDS)
    in_spec = make_input_spec(
        source_uri=str(out_spec.destination_uri),
        compression="none",
    )
    assert decorator.read(spec=in_spec, credentials=_NO_CREDS) == payload
