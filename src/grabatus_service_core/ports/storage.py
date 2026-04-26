"""StoragePort: abstract reads and writes against any URI scheme."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from grabatus_service_core.contract.io_spec import InputSpec, OutputSpec
    from grabatus_service_core.ports.values import Credentials, WriteReceipt


@runtime_checkable
class StoragePort(Protocol):
    """Read input artifacts, write output artifacts.

    A single Port covers all schemes; concrete adapters (GCS, S3, BigQuery,
    LocalFs, Inline, HttpFetch) dispatch internally based on the URI.
    Adapters that don't support a scheme raise ``UnsupportedSchemeError``.
    """

    def read(self, *, spec: InputSpec, credentials: Credentials) -> bytes:
        """Return raw bytes from ``spec.source_uri``."""
        ...

    def write(
        self,
        *,
        spec: OutputSpec,
        payload: bytes,
        credentials: Credentials,
    ) -> WriteReceipt:
        """Persist ``payload`` to ``spec.destination_uri``; return receipt."""
        ...
