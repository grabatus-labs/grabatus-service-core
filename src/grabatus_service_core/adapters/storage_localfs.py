"""LocalFsStorage: file:// URIs for tests and local development."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from grabatus_service_core.errors import (
    InputNotFoundError,
    InputReadError,
    OutputWriteError,
    UnsupportedSchemeError,
)
from grabatus_service_core.ports.values import WriteReceipt

if TYPE_CHECKING:
    from grabatus_service_core.contract.io_spec import InputSpec, OutputSpec
    from grabatus_service_core.ports.values import Credentials


_FILE_SCHEME = "file"


class LocalFsStorage:
    """Read/write bytes against the local filesystem.

    Only meant for tests, sample services, and developer machines. Production
    services use :class:`GcsStorage` (or a partner-specific adapter) and never
    touch the local disk.
    """

    def __init__(self, *, root: Path | None = None) -> None:
        self._root = root

    def read(self, *, spec: InputSpec, credentials: Credentials) -> bytes:
        del credentials
        uri = str(spec.source_uri)
        path = self._resolve_path(uri)
        if not path.exists():
            raise InputNotFoundError(
                f"LocalFsStorage has no file at path={path!s}; uri={uri!r}",
            )
        try:
            return path.read_bytes()
        except OSError as exc:
            raise InputReadError(
                f"LocalFsStorage failed to read uri={uri!r}: {exc}",
            ) from exc

    def write(
        self,
        *,
        spec: OutputSpec,
        payload: bytes,
        credentials: Credentials,
    ) -> WriteReceipt:
        del credentials
        uri = str(spec.destination_uri)
        path = self._resolve_path(uri)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        except OSError as exc:
            raise OutputWriteError(
                f"LocalFsStorage failed to write uri={uri!r}: {exc}",
            ) from exc
        return WriteReceipt(uri=uri, bytes_written=len(payload), request_id_tag="local")

    def _resolve_path(self, uri: str) -> Path:
        scheme, _, rest = uri.partition("://")
        if scheme != _FILE_SCHEME:
            raise UnsupportedSchemeError(
                f"LocalFsStorage requires scheme={_FILE_SCHEME!r}, got uri={uri!r}",
            )
        # rest is "host/path"; for file:// we ignore host (always empty).
        _, _, path_str = rest.partition("/")
        path = Path("/" + path_str)
        if self._root is not None:
            try:
                path.relative_to(self._root)
            except ValueError as exc:
                raise UnsupportedSchemeError(
                    f"LocalFsStorage path={path!s} escapes configured root={self._root!s}",
                ) from exc
        return path
