"""SecretsPort: resolve ``secret://`` URIs to credential bytes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from grabatus_service_core.contract.secret_ref import SecretRef
    from grabatus_service_core.ports.values import Credentials


@runtime_checkable
class SecretsPort(Protocol):
    """Look up a secret in the configured secret manager."""

    def resolve(self, *, secret_ref: SecretRef) -> Credentials:
        """Return the credential bytes referenced by ``secret_ref``."""
        ...
