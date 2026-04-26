"""Grabatus Service Core: hexagonal library for Grabatus computational services.

Top-level imports here are deliberately limited to pure-Python domain
classes. Any module that requires a cloud SDK lives under ``adapters/``
(introduced in Sub-Plan 1B) and is imported only by services that wire
those adapters explicitly.
"""

from grabatus_service_core.contract import (
    BaseServiceContract,
    Callback,
    Envelope,
    FormatHints,
    Identity,
    InputSpec,
    OutputSpec,
    References,
    SecretRef,
    ServiceDescriptor,
)
from grabatus_service_core.errors import (
    BlockedHostError,
    ComputeError,
    ComputeTimeoutError,
    ContractError,
    CredentialResolutionError,
    FormatParsingError,
    GrabatusServiceError,
    InputNotFoundError,
    InputReadError,
    InvalidContractError,
    MalformedMessageError,
    OutputWriteError,
    SecurityError,
    StorageError,
    UnauthorizedUriError,
    UnsupportedProtocolVersionError,
    UnsupportedSchemeError,
    WebhookAuthError,
    WebhookError,
)

__version__ = "0.1.0"

__all__ = [
    "BaseServiceContract",
    "BlockedHostError",
    "Callback",
    "ComputeError",
    "ComputeTimeoutError",
    "ContractError",
    "CredentialResolutionError",
    "Envelope",
    "FormatHints",
    "FormatParsingError",
    "GrabatusServiceError",
    "Identity",
    "InputNotFoundError",
    "InputReadError",
    "InputSpec",
    "InvalidContractError",
    "MalformedMessageError",
    "OutputSpec",
    "OutputWriteError",
    "References",
    "SecretRef",
    "SecurityError",
    "ServiceDescriptor",
    "StorageError",
    "UnauthorizedUriError",
    "UnsupportedProtocolVersionError",
    "UnsupportedSchemeError",
    "WebhookAuthError",
    "WebhookError",
    "__version__",
]
