"""HttpFetchStorage: read bytes from https:// URIs (read-only)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx

from grabatus_service_core.adapters.retry import with_retry
from grabatus_service_core.errors import (
    InputNotFoundError,
    InputReadError,
    OutputWriteError,
    UnsupportedSchemeError,
)

if TYPE_CHECKING:
    from grabatus_service_core.contract.io_spec import InputSpec, OutputSpec
    from grabatus_service_core.ports.values import Credentials, WriteReceipt
    from grabatus_service_core.security.host_blocklist import HostBlocklist


_HTTP_SCHEMES = frozenset({"http", "https"})
_HTTP_NOT_FOUND = 404
_HTTP_OK_LOWER_BOUND = 200
_HTTP_OK_UPPER_BOUND = 300
_DEFAULT_TIMEOUT_SECONDS = 30.0
_RETRIABLE_HTTP_ERRORS: tuple[type[BaseException], ...] = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
)


class HttpFetchStorage:
    """Fetch bytes via httpx; refuses any scheme other than http/https.

    A :class:`HostBlocklist` is required and applied before every request,
    blocking metadata, RFC1918, and ``.internal`` hosts.
    """

    def __init__(
        self,
        *,
        host_blocklist: HostBlocklist,
        client: httpx.Client | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._blocklist = host_blocklist
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._timeout = timeout_seconds

    @with_retry(retry_on=_RETRIABLE_HTTP_ERRORS)
    def read(self, *, spec: InputSpec, credentials: Credentials) -> bytes:
        uri = str(spec.source_uri)
        scheme = uri.split("://", 1)[0].lower()
        if scheme not in _HTTP_SCHEMES:
            raise UnsupportedSchemeError(
                f"HttpFetchStorage requires http(s) scheme, got uri={uri!r}",
            )
        self._blocklist.check(uri)
        headers = self._build_auth_headers(credentials)
        try:
            response = self._client.get(uri, headers=headers, timeout=self._timeout)
        except _RETRIABLE_HTTP_ERRORS:
            raise
        except httpx.HTTPError as exc:
            raise InputReadError(
                f"HttpFetchStorage failed to GET uri={uri!r}: {exc}",
            ) from exc
        if response.status_code == _HTTP_NOT_FOUND:
            raise InputNotFoundError(f"HttpFetchStorage 404 for uri={uri!r}")
        if not (_HTTP_OK_LOWER_BOUND <= response.status_code < _HTTP_OK_UPPER_BOUND):
            raise InputReadError(
                f"HttpFetchStorage non-2xx={response.status_code} for uri={uri!r}",
            )
        return response.content

    def write(
        self,
        *,
        spec: OutputSpec,
        payload: bytes,
        credentials: Credentials,
    ) -> WriteReceipt:
        del payload, credentials
        raise OutputWriteError(
            f"HttpFetchStorage is read-only; refused write to uri={spec.destination_uri!s}",
        )

    @staticmethod
    def _build_auth_headers(credentials: Credentials) -> dict[str, str]:
        if not credentials.token:
            return {}
        token = credentials.token.decode("utf-8")
        return {"Authorization": f"{credentials.token_type.title()} {token}"}
