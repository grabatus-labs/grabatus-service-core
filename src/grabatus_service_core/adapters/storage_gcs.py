"""GcsStorage: gs:// adapter backed by google-cloud-storage."""

from __future__ import annotations

from typing import TYPE_CHECKING

from google.api_core import exceptions as gcp_exceptions
from google.cloud import storage as gcs

from grabatus_service_core.adapters.retry import with_retry
from grabatus_service_core.errors import (
    InputNotFoundError,
    InputReadError,
    OutputWriteError,
    UnsupportedSchemeError,
)
from grabatus_service_core.ports.values import WriteReceipt

if TYPE_CHECKING:
    from grabatus_service_core.contract.io_spec import InputSpec, OutputSpec
    from grabatus_service_core.ports.values import Credentials


_GCS_SCHEME = "gs"
_RETRIABLE_GCS_ERRORS: tuple[type[BaseException], ...] = (
    gcp_exceptions.ServiceUnavailable,
    gcp_exceptions.InternalServerError,
    gcp_exceptions.GatewayTimeout,
    gcp_exceptions.DeadlineExceeded,
    gcp_exceptions.TooManyRequests,
    ConnectionError,
)


def _parse_gs_uri(uri: str) -> tuple[str, str]:
    scheme, _, rest = uri.partition("://")
    if scheme != _GCS_SCHEME:
        raise UnsupportedSchemeError(
            f"GcsStorage requires scheme={_GCS_SCHEME!r}, got uri={uri!r}",
        )
    bucket, _, blob = rest.partition("/")
    if not bucket or not blob:
        raise UnsupportedSchemeError(
            f"GcsStorage URI must be gs://<bucket>/<blob>, got uri={uri!r}",
        )
    return bucket, blob


class GcsStorage:
    """Reads/writes Google Cloud Storage objects via google-cloud-storage."""

    def __init__(self, *, client: gcs.Client | None = None) -> None:
        self._client = client or gcs.Client()

    @with_retry(retry_on=_RETRIABLE_GCS_ERRORS)
    def read(self, *, spec: InputSpec, credentials: Credentials) -> bytes:
        del credentials
        uri = str(spec.source_uri)
        bucket_name, blob_name = _parse_gs_uri(uri)
        bucket = self._client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        try:
            data: bytes = blob.download_as_bytes()
        except _RETRIABLE_GCS_ERRORS:
            # Let tenacity see the retriable exception and decide whether to retry.
            raise
        except gcp_exceptions.NotFound as exc:
            raise InputNotFoundError(
                f"GcsStorage: object not found at uri={uri!r}",
            ) from exc
        except gcp_exceptions.GoogleAPIError as exc:
            raise InputReadError(
                f"GcsStorage: download failed for uri={uri!r}: {exc}",
            ) from exc
        else:
            return data

    @with_retry(retry_on=_RETRIABLE_GCS_ERRORS)
    def write(
        self,
        *,
        spec: OutputSpec,
        payload: bytes,
        credentials: Credentials,
    ) -> WriteReceipt:
        del credentials
        uri = str(spec.destination_uri)
        bucket_name, blob_name = _parse_gs_uri(uri)
        bucket = self._client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        try:
            blob.upload_from_string(payload)
        except _RETRIABLE_GCS_ERRORS:
            raise
        except gcp_exceptions.GoogleAPIError as exc:
            raise OutputWriteError(
                f"GcsStorage: upload failed for uri={uri!r}: {exc}",
            ) from exc
        return WriteReceipt(uri=uri, bytes_written=len(payload), request_id_tag="gcs")
