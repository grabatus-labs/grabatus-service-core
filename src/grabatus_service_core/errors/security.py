"""Errors raised by the security layer (URI auth, schemes, hosts, secrets)."""

from __future__ import annotations

from grabatus_service_core.errors.base import GrabatusServiceError


class SecurityError(GrabatusServiceError):
    """Base for security-related failures."""

    error_code = "security_error"
    http_status = 200
    retriable = False


class UnsupportedSchemeError(SecurityError):
    """URI uses a scheme that is not in GBT_ALLOWED_SCHEMES."""

    error_code = "unsupported_scheme"


class UnauthorizedUriError(SecurityError):
    """URI does not match the tenant/user prefix policy."""

    error_code = "unauthorized_uri"


class BlockedHostError(SecurityError):
    """HTTP URI targets a blocked host (metadata, internal, etc.)."""

    error_code = "blocked_host"


class CredentialResolutionError(SecurityError):
    """Secret manager could not resolve a credential reference."""

    error_code = "credential_resolution_failed"
    retriable = True
