"""Errors related to message decoding and contract validation."""

from __future__ import annotations

from grabatus_service_core.errors.base import GrabatusServiceError


class ContractError(GrabatusServiceError):
    """Base for any contract-related failure."""

    error_code = "contract_error"
    http_status = 200
    retriable = False


class MalformedMessageError(ContractError):
    """Raised when the Pub/Sub message envelope cannot be decoded."""

    error_code = "malformed_message"


class InvalidContractError(ContractError):
    """Raised when the decoded payload fails Pydantic validation."""

    error_code = "invalid_contract"


class UnsupportedProtocolVersionError(ContractError):
    """Raised when the envelope's protocol_version is not supported."""

    error_code = "unsupported_protocol_version"
