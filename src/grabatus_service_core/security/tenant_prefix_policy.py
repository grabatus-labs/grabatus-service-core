"""TenantPrefixPolicy: default URI authorization based on bucket+user prefix."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from grabatus_service_core.errors import UnauthorizedUriError
from grabatus_service_core.security.uri_parser import parse_uri

if TYPE_CHECKING:
    from grabatus_service_core.contract.identity import Identity


_TENANT_AGNOSTIC_SCHEMES = frozenset({"secret", "inline"})
_BUCKET_SCHEMES = frozenset({"gs", "s3"})
_BIGQUERY_SCHEMES = frozenset({"bigquery"})


@dataclass(frozen=True, slots=True)
class TenantPrefixPolicy:
    """Default UriAuthorizationPort enforcing tenant + user prefixing.

    Bucket-style URIs (``gs://``, ``s3://``) must use a bucket whose name
    starts with ``<bucket_prefix>-<tenant_id>``. When ``require_user_path_segment``
    is True, the first path segment must equal ``user_<user_id>``.

    BigQuery URIs (``bigquery://project.dataset.table``) require the
    project segment to start with ``<bucket_prefix>-<tenant_id>``.

    ``secret://`` and ``inline://`` URIs are tenant-agnostic and pass.
    All other schemes are denied (HTTP allowed schemes are configured
    separately via ``HostBlocklist``).
    """

    bucket_prefix: str
    require_user_path_segment: bool = True

    def authorize(self, *, uri: str, identity: Identity) -> None:
        parsed = parse_uri(uri)
        scheme = parsed.scheme
        if scheme in _TENANT_AGNOSTIC_SCHEMES:
            return
        if scheme in _BUCKET_SCHEMES:
            self._check_bucket_uri(
                uri=uri,
                parsed_host=parsed.host,
                parsed_path=parsed.path,
                identity=identity,
            )
            return
        if scheme in _BIGQUERY_SCHEMES:
            self._check_bigquery_uri(
                uri=uri,
                parsed_host=parsed.host,
                identity=identity,
            )
            return
        raise UnauthorizedUriError(
            f"scheme={scheme!r} not authorized by TenantPrefixPolicy; uri={uri!r}",
        )

    def _check_bucket_uri(
        self,
        *,
        uri: str,
        parsed_host: str,
        parsed_path: str,
        identity: Identity,
    ) -> None:
        expected_prefix = f"{self.bucket_prefix}-{identity.tenant_id}"
        if not parsed_host.startswith(expected_prefix):
            raise UnauthorizedUriError(
                f"bucket={parsed_host!r} does not start with "
                f"expected_prefix={expected_prefix!r} for tenant="
                f"{identity.tenant_id!r}; uri={uri!r}",
            )
        if self.require_user_path_segment:
            self._check_user_segment(
                path=parsed_path,
                user_id=identity.user_id,
                uri=uri,
            )

    def _check_bigquery_uri(
        self,
        *,
        uri: str,
        parsed_host: str,
        identity: Identity,
    ) -> None:
        expected_prefix = f"{self.bucket_prefix}-{identity.tenant_id}"
        project = parsed_host.split(".", 1)[0]
        if not project.startswith(expected_prefix):
            raise UnauthorizedUriError(
                f"bigquery project={project!r} does not start with "
                f"expected_prefix={expected_prefix!r}; uri={uri!r}",
            )

    @staticmethod
    def _check_user_segment(*, path: str, user_id: str, uri: str) -> None:
        segments = [seg for seg in path.split("/") if seg]
        expected_segment = f"user_{user_id}"
        if not segments or segments[0] != expected_segment:
            first_segment = segments[0] if segments else None
            raise UnauthorizedUriError(
                f"path must start with user segment={expected_segment!r}, "
                f"got first_segment={first_segment!r}; uri={uri!r}",
            )
