"""CompositeStorage: scheme-routed StoragePort that delegates to per-scheme adapters."""

from __future__ import annotations

from typing import TYPE_CHECKING

from grabatus_service_core.errors import UnsupportedSchemeError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from grabatus_service_core.contract.io_spec import InputSpec, OutputSpec
    from grabatus_service_core.ports.storage import StoragePort
    from grabatus_service_core.ports.values import Credentials, WriteReceipt


def _scheme_of(uri: str) -> str:
    return uri.split("://", 1)[0].lower()


class CompositeStorage:
    """Delegates each call to a per-scheme adapter chosen by URI scheme.

    Schemes the runner plans to use (gs, file, inline, https, …) must each
    map to an adapter at construction time. URIs whose scheme is not in the
    mapping raise ``UnsupportedSchemeError``.
    """

    def __init__(self, *, by_scheme: Mapping[str, StoragePort]) -> None:
        self._by_scheme = {scheme.lower(): adapter for scheme, adapter in by_scheme.items()}

    def read(self, *, spec: InputSpec, credentials: Credentials) -> bytes:
        adapter = self._select(str(spec.source_uri))
        return adapter.read(spec=spec, credentials=credentials)

    def write(
        self,
        *,
        spec: OutputSpec,
        payload: bytes,
        credentials: Credentials,
    ) -> WriteReceipt:
        adapter = self._select(str(spec.destination_uri))
        return adapter.write(spec=spec, payload=payload, credentials=credentials)

    def _select(self, uri: str) -> StoragePort:
        scheme = _scheme_of(uri)
        adapter = self._by_scheme.get(scheme)
        if adapter is None:
            raise UnsupportedSchemeError(
                f"CompositeStorage has no adapter for scheme={scheme!r}; "
                f"configured={sorted(self._by_scheme)!r}; uri={uri!r}",
            )
        return adapter
