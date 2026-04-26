"""EnvVarSecretsAdapter: resolves SecretRef from process environment.

Maps ``secret://env/<name>`` and ``secret://env/<name>/<version>`` to the
value of an environment variable. Used for local development; the version
component is ignored (env vars don't have versions).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from grabatus_service_core.errors import CredentialResolutionError
from grabatus_service_core.ports.values import Credentials

if TYPE_CHECKING:
    from grabatus_service_core.contract.secret_ref import SecretRef


_ENV_PROVIDER = "env"
_DEFAULT_TOKEN_TYPE = "env"  # noqa: S105  # nosec B105 — token_type tag, not a credential


class EnvVarSecretsAdapter:
    """Read secrets from environment variables (development only)."""

    def __init__(self, *, environ: dict[str, str] | None = None) -> None:
        # Snapshot at construction so tests are deterministic without monkey-patching.
        self._environ = dict(environ) if environ is not None else dict(os.environ)

    def resolve(self, *, secret_ref: SecretRef) -> Credentials:
        if secret_ref.provider != _ENV_PROVIDER:
            raise CredentialResolutionError(
                f"EnvVarSecretsAdapter only resolves provider={_ENV_PROVIDER!r}, "
                f"got secret_ref={secret_ref.to_uri()!r}",
            )
        value = self._environ.get(secret_ref.name)
        if value is None:
            raise CredentialResolutionError(
                f"environment variable {secret_ref.name!r} is not set; "
                f"secret_ref={secret_ref.to_uri()!r}",
            )
        return Credentials(token=value.encode("utf-8"), token_type=_DEFAULT_TOKEN_TYPE)
