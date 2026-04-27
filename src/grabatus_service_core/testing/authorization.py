"""AllowAllPolicy / RejectAllPolicy: test fakes for UriAuthorizationPort."""

from __future__ import annotations

from typing import TYPE_CHECKING

from grabatus_service_core.errors import UnauthorizedUriError

if TYPE_CHECKING:
    from grabatus_service_core.contract.identity import Identity


class AllowAllPolicy:
    """No-op UriAuthorizationPort that authorizes any URI for any identity."""

    def authorize(self, *, uri: str, identity: Identity) -> None:
        del uri, identity


class RejectAllPolicy:
    """UriAuthorizationPort that denies every URI; for testing the error branch."""

    def authorize(self, *, uri: str, identity: Identity) -> None:
        del identity
        raise UnauthorizedUriError(f"RejectAllPolicy denies uri={uri!r}")
