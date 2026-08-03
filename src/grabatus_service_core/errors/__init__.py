"""Exception hierarchy for grabatus_service_core."""

from grabatus_service_core.errors.base import GrabatusServiceError
from grabatus_service_core.errors.compute import (
    ComputeError,
    ComputeTimeoutError,
    InvalidReadoutError,
    MissingReadoutError,
    ReadoutMismatchError,
    UnknownOutputRoleError,
)
from grabatus_service_core.errors.contract import (
    ContractError,
    InvalidContractError,
    MalformedMessageError,
    UnknownServiceError,
    UnsupportedProtocolVersionError,
)
from grabatus_service_core.errors.io import (
    FormatParsingError,
    InputNotFoundError,
    InputReadError,
    OutputWriteError,
    StorageError,
)
from grabatus_service_core.errors.security import (
    BlockedHostError,
    CredentialResolutionError,
    SecurityError,
    UnauthorizedUriError,
    UnsupportedSchemeError,
)
from grabatus_service_core.errors.webhook import (
    WebhookAuthError,
    WebhookError,
)

__all__ = [
    "BlockedHostError",
    "ComputeError",
    "ComputeTimeoutError",
    "ContractError",
    "CredentialResolutionError",
    "FormatParsingError",
    "GrabatusServiceError",
    "InputNotFoundError",
    "InputReadError",
    "InvalidContractError",
    "InvalidReadoutError",
    "MalformedMessageError",
    "MissingReadoutError",
    "OutputWriteError",
    "ReadoutMismatchError",
    "SecurityError",
    "StorageError",
    "UnauthorizedUriError",
    "UnknownOutputRoleError",
    "UnknownServiceError",
    "UnsupportedProtocolVersionError",
    "UnsupportedSchemeError",
    "WebhookAuthError",
    "WebhookError",
]
