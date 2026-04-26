"""AllowAllPolicy: authorizes every URI; only for tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grabatus_service_core.contract.identity import Identity


class AllowAllPolicy:
    """No-op UriAuthorizationPort that authorizes any URI for any identity."""

    def authorize(self, *, uri: str, identity: Identity) -> None:
        del uri, identity
