"""CompressedStorage: a StoragePort decorator that honors compression on inputs and outputs.

Codecs supported:
- ``"none"`` — pass through (no transformation)
- ``"gzip"`` — Python stdlib gzip (compresslevel=9)
- ``"zstd"`` — zstandard library (level=10)

Example:
    >>> from grabatus_service_core.adapters.storage_gcs import GcsStorage
    >>> raw = GcsStorage(...)
    >>> storage = CompressedStorage(inner=raw)
"""

from __future__ import annotations

import gzip
from typing import TYPE_CHECKING

import zstandard as zstd

from grabatus_service_core.errors import (
    InputReadError,
    OutputWriteError,
)

if TYPE_CHECKING:
    from grabatus_service_core.contract.io_spec import InputSpec, OutputSpec
    from grabatus_service_core.ports.storage import StoragePort
    from grabatus_service_core.ports.values import Credentials, WriteReceipt


_GZIP_LEVEL = 9
_ZSTD_LEVEL = 10


class CompressedStorage:
    """Decorator that adds gzip/zstd codec support to any inner StoragePort."""

    def __init__(self, *, inner: StoragePort) -> None:
        self._inner = inner

    def read(self, *, spec: InputSpec, credentials: Credentials) -> bytes:
        raw = self._inner.read(spec=spec, credentials=credentials)
        if spec.compression == "none":
            return raw
        if spec.compression == "gzip":
            try:
                return gzip.decompress(raw)
            except OSError as exc:
                raise InputReadError(
                    f"failed to gzip-decompress payload from uri={spec.source_uri!s}: {exc}",
                ) from exc
        if spec.compression == "zstd":
            try:
                return zstd.ZstdDecompressor().decompress(raw)
            except zstd.ZstdError as exc:
                raise InputReadError(
                    f"failed to zstd-decompress payload from uri={spec.source_uri!s}: {exc}",
                ) from exc
        raise InputReadError(  # pragma: no cover  # unreachable; Pydantic narrows the type
            f"unknown compression={spec.compression!r}",
        )

    def write(
        self,
        *,
        spec: OutputSpec,
        payload: bytes,
        credentials: Credentials,
    ) -> WriteReceipt:
        if spec.compression == "none":
            transformed = payload
        elif spec.compression == "gzip":
            transformed = gzip.compress(payload, compresslevel=_GZIP_LEVEL)
        elif spec.compression == "zstd":
            transformed = zstd.ZstdCompressor(level=_ZSTD_LEVEL).compress(payload)
        else:
            raise OutputWriteError(  # pragma: no cover  # unreachable; Pydantic narrows the type
                f"unknown compression={spec.compression!r}",
            )
        return self._inner.write(
            spec=spec,
            payload=transformed,
            credentials=credentials,
        )
