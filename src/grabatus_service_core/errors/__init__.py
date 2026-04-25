"""Exception hierarchy for grabatus_service_core."""

from grabatus_service_core.errors.base import GrabatusServiceError
from grabatus_service_core.errors.compute import (
    ComputeError,
    ComputeTimeoutError,
)
from grabatus_service_core.errors.contract import (
    ContractError,
    InvalidContractError,
    MalformedMessageError,
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
    "MalformedMessageError",
    "OutputWriteError",
    "SecurityError",
    "StorageError",
    "UnauthorizedUriError",
    "UnsupportedProtocolVersionError",
    "UnsupportedSchemeError",
    "WebhookAuthError",
    "WebhookError",
]
