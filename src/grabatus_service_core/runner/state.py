"""Frozen dataclasses propagated between runner steps.

Each step produces a state dataclass; the next step consumes it. Generic
states (``ValidatedContract``, ``AuthorizedContract``, ``ExecutionResult``)
preserve the contract's ``ParamsT`` so downstream callers keep static
typing on ``contract.parameters``.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Generic, Literal

from grabatus_service_core.contract.base import BaseServiceContract, ParamsT

if TYPE_CHECKING:
    from collections.abc import Mapping
    from uuid import UUID

    from grabatus_service_core.errors import GrabatusServiceError
    from grabatus_service_core.ports.values import (
        Credentials,
        WebhookAck,
        WriteReceipt,
    )


@dataclass(frozen=True, slots=True)
class ParsedEnvelope:
    """Step 1 output: contract dict pulled from the broker envelope."""

    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


@dataclass(frozen=True)
class ValidatedContract(Generic[ParamsT]):  # noqa: UP046 — TypeVar form needed for runtime use
    """Step 2 output: contract validated against its Pydantic schema."""

    contract: BaseServiceContract[ParamsT]


@dataclass(frozen=True)
class AuthorizedContract(Generic[ParamsT]):  # noqa: UP046 — TypeVar form needed for runtime use
    """Step 3 output: contract whose URIs and schemes were authorized."""

    contract: BaseServiceContract[ParamsT]


@dataclass(frozen=True, slots=True)
class CredentialBundle:
    """Step 4 output: credentials resolved per input and output role."""

    inputs: Mapping[str, Credentials]
    outputs: Mapping[str, Credentials]

    def __post_init__(self) -> None:
        object.__setattr__(self, "inputs", MappingProxyType(dict(self.inputs)))
        object.__setattr__(self, "outputs", MappingProxyType(dict(self.outputs)))


@dataclass(frozen=True, slots=True)
class WriteReceipts:
    """Step 7 output: receipts indexed by output role."""

    by_role: Mapping[str, WriteReceipt]

    def __post_init__(self) -> None:
        object.__setattr__(self, "by_role", MappingProxyType(dict(self.by_role)))


@dataclass(frozen=True)
class ExecutionResult(Generic[ParamsT]):  # noqa: UP046 — TypeVar form needed for runtime use
    """Final pipeline outcome — success or failure plus metadata."""

    request_id: UUID
    status: Literal["ok", "error"]
    contract: BaseServiceContract[ParamsT] | None
    receipts: WriteReceipts | None
    error: GrabatusServiceError | None
    metadata: Mapping[str, object]
    webhook_ack: WebhookAck | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
