"""Value objects passed between Ports and the runner."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass(frozen=True, slots=True)
class RawMessage:
    """Raw bytes received from the message broker."""

    payload: bytes


@dataclass(frozen=True, slots=True)
class Credentials:
    """Resolved credential bytes plus its token type (bearer, hmac, etc.)."""

    token: bytes
    token_type: str


@dataclass(frozen=True, slots=True)
class WriteReceipt:
    """Outcome of writing a single output."""

    uri: str
    bytes_written: int
    request_id_tag: str


@dataclass(frozen=True, slots=True)
class LoadedInputs:
    """Bytes loaded for each input role."""

    by_role: Mapping[str, bytes]

    def __post_init__(self) -> None:
        # Freeze the mapping so it cannot be mutated after construction.
        object.__setattr__(self, "by_role", MappingProxyType(dict(self.by_role)))


@dataclass(frozen=True, slots=True)
class ComputeResult:
    """Bytes produced for each output role plus optional metadata."""

    by_role: Mapping[str, bytes]
    metadata: Mapping[str, object]

    def __post_init__(self) -> None:
        object.__setattr__(self, "by_role", MappingProxyType(dict(self.by_role)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class WebhookAck:
    """Result of notifying the webhook."""

    http_status: int
    response_body: str
