"""GoogleSecretManagerAdapter: resolves SecretRef via Google Secret Manager."""

from __future__ import annotations

from typing import TYPE_CHECKING

from google.api_core import exceptions as gcp_exceptions
from google.cloud import secretmanager

from grabatus_service_core.adapters.retry import with_retry
from grabatus_service_core.errors import CredentialResolutionError
from grabatus_service_core.ports.values import Credentials

if TYPE_CHECKING:
    from grabatus_service_core.contract.secret_ref import SecretRef


_DEFAULT_TOKEN_TYPE = "secret"  # noqa: S105  # nosec B105 — token_type tag, not a credential
_RETRIABLE_GSM_ERRORS: tuple[type[BaseException], ...] = (
    gcp_exceptions.ServiceUnavailable,
    gcp_exceptions.InternalServerError,
    gcp_exceptions.GatewayTimeout,
    gcp_exceptions.DeadlineExceeded,
    gcp_exceptions.TooManyRequests,
    ConnectionError,
)


class GoogleSecretManagerAdapter:
    """Production SecretsPort backed by Google Cloud Secret Manager.

    The ``project_id`` is supplied at construction time; ``secret_ref.name``
    is the secret short name; ``secret_ref.version`` is either ``latest``
    or a numeric version string.
    """

    def __init__(
        self,
        *,
        project_id: str,
        client: secretmanager.SecretManagerServiceClient | None = None,
    ) -> None:
        self._project_id = project_id
        self._client = client or secretmanager.SecretManagerServiceClient()

    @with_retry(retry_on=_RETRIABLE_GSM_ERRORS)
    def resolve(self, *, secret_ref: SecretRef) -> Credentials:
        name = (
            f"projects/{self._project_id}/secrets/{secret_ref.name}/versions/{secret_ref.version}"
        )
        try:
            response = self._client.access_secret_version(name=name)
        except _RETRIABLE_GSM_ERRORS:
            raise
        except gcp_exceptions.NotFound as exc:
            raise CredentialResolutionError(
                f"Secret Manager has no version for secret_ref={secret_ref.to_uri()!r}",
            ) from exc
        except gcp_exceptions.GoogleAPIError as exc:
            raise CredentialResolutionError(
                f"Secret Manager access failed for secret_ref={secret_ref.to_uri()!r}: {exc}",
            ) from exc
        return Credentials(
            token=response.payload.data,
            token_type=_DEFAULT_TOKEN_TYPE,
        )
