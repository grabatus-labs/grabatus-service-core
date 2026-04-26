"""InMemoryStorage: dict-backed storage for tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from grabatus_service_core.errors import (
    InputNotFoundError,
    UnsupportedSchemeError,
)
from grabatus_service_core.ports.values import WriteReceipt

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from grabatus_service_core.contract.io_spec import InputSpec, OutputSpec
    from grabatus_service_core.ports.values import Credentials


_DEFAULT_SUPPORTED_SCHEMES = frozenset({"gs", "s3", "file", "inline", "http", "https"})


class InMemoryStorage:
    """Round-trips bytes by URI in a private dict.

    Optionally constrained to a set of supported URI schemes; rejects
    others with ``UnsupportedSchemeError`` to mimic real adapter behavior.
    """

    def __init__(
        self,
        seed: Mapping[str, bytes] | None = None,
        *,
        supported_schemes: Iterable[str] | None = None,
    ) -> None:
        self._objects: dict[str, bytes] = dict(seed or {})
        self._supported_schemes = frozenset(
            supported_schemes if supported_schemes is not None else _DEFAULT_SUPPORTED_SCHEMES,
        )

    def read(self, *, spec: InputSpec, credentials: Credentials) -> bytes:
        del credentials  # accepted but ignored in fake
        uri = str(spec.source_uri)
        self._check_scheme(uri)
        if uri not in self._objects:
            raise InputNotFoundError(
                f"in-memory storage has no object at uri={uri!r}",
            )
        return self._objects[uri]

    def write(
        self,
        *,
        spec: OutputSpec,
        payload: bytes,
        credentials: Credentials,
    ) -> WriteReceipt:
        del credentials
        uri = str(spec.destination_uri)
        self._check_scheme(uri)
        self._objects[uri] = payload
        return WriteReceipt(
            uri=uri,
            bytes_written=len(payload),
            request_id_tag="in-memory",
        )

    def _check_scheme(self, uri: str) -> None:
        scheme = uri.split("://", 1)[0].lower()
        if scheme not in self._supported_schemes:
            raise UnsupportedSchemeError(
                f"InMemoryStorage does not support scheme={scheme!r}; "
                f"supported={sorted(self._supported_schemes)!r}; uri={uri!r}",
            )
