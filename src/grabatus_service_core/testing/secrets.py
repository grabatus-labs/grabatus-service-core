"""InMemorySecretsAdapter: dict-backed SecretsPort for tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from grabatus_service_core.errors import CredentialResolutionError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from grabatus_service_core.contract.secret_ref import SecretRef
    from grabatus_service_core.ports.values import Credentials


class InMemorySecretsAdapter:
    """Resolves SecretRef → Credentials by URI lookup in a private dict."""

    def __init__(self, seed: Mapping[str, Credentials] | None = None) -> None:
        self._secrets: dict[str, Credentials] = dict(seed or {})

    def resolve(self, *, secret_ref: SecretRef) -> Credentials:
        uri = secret_ref.to_uri()
        if uri not in self._secrets:
            raise CredentialResolutionError(
                f"in-memory secrets adapter has no entry for secret_ref={uri!r}",
            )
        return self._secrets[uri]
