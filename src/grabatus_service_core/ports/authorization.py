"""UriAuthorizationPort: enforce tenant-scoped URI access."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from grabatus_service_core.contract.identity import Identity


@runtime_checkable
class UriAuthorizationPort(Protocol):
    """Authorize that ``uri`` is allowed for ``identity``.

    Default implementation (`TenantPrefixPolicy`) requires bucket+prefix
    to match ``identity.tenant_id``. Implementations raise
    ``UnauthorizedUriError`` on denial; success returns ``None``.
    """

    def authorize(self, *, uri: str, identity: Identity) -> None:
        """Raise ``UnauthorizedUriError`` if ``identity`` may not access ``uri``."""
        ...
