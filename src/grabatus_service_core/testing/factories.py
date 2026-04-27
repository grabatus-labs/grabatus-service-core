"""Factories for valid contract instances; reduce boilerplate in service tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, TypeVar, cast
from uuid import UUID

from pydantic import BaseModel

from grabatus_service_core.contract import (
    BaseServiceContract,
    Callback,
    Envelope,
    Identity,
    InputSpec,
    OutputSpec,
    References,
    ServiceDescriptor,
)
from grabatus_service_core.contract.opaque import (
    OpaqueServiceContract,
)

if TYPE_CHECKING:
    from grabatus_service_core.contract.io_spec import Compression

_DEFAULT_REQUEST_ID = UUID("a3f9c21e-bf38-4e75-9a2f-c89b6c3f2d12")
_DEFAULT_CREATED_AT = datetime(2026, 4, 25, 12, 0, 0, tzinfo=UTC)

ParamsT = TypeVar("ParamsT", bound=BaseModel)


def make_envelope(
    *,
    request_id: UUID | None = None,
    created_at: datetime | None = None,
    origin: str = "web",
    protocol_version: str = "1.0",
) -> Envelope:
    return Envelope.model_validate(
        {
            "protocol_version": protocol_version,
            "request_id": str(request_id or _DEFAULT_REQUEST_ID),
            "created_at": (created_at or _DEFAULT_CREATED_AT).isoformat(),
            "origin": origin,
        },
    )


def make_identity(*, user_id: str = "999", tenant_id: str = "grabatus") -> Identity:
    return Identity.model_validate({"user_id": user_id, "tenant_id": tenant_id})


def make_references(
    *,
    parameter_id: str = "p-1",
    result_id: str = "r-1",
) -> References:
    return References.model_validate(
        {"parameter_id": parameter_id, "result_id": result_id},
    )


def make_service_descriptor(
    *,
    name: str = "sample",
    version: str = "1.0.0",
) -> ServiceDescriptor:
    return ServiceDescriptor.model_validate({"name": name, "version": version})


def make_input_spec(
    *,
    role: str = "timeseries",
    source_uri: str = "gs://gbt-storage-grabatus/user_999/in.xlsx",
    fmt: str = "xlsx",
    hints: dict[str, Any] | None = None,
    compression: Compression = "none",
) -> InputSpec:
    payload: dict[str, Any] = {
        "role": role,
        "source_uri": source_uri,
        "format": fmt,
        "format_hints": hints or {"format": fmt, "sheet": "Dados"},
        "compression": compression,
    }
    return InputSpec.model_validate(payload)


def make_output_spec(
    *,
    role: str = "result_json",
    destination_uri: str = "gs://gbt-storage-grabatus/user_999/out.json",
    fmt: str = "json",
    hints: dict[str, Any] | None = None,
    compression: Compression = "none",
) -> OutputSpec:
    payload: dict[str, Any] = {
        "role": role,
        "destination_uri": destination_uri,
        "format": fmt,
        "format_hints": hints or {"format": fmt},
        "compression": compression,
    }
    return OutputSpec.model_validate(payload)


def make_callback(
    *,
    url: str = "https://grabatus.com/webhook",
    auth_scheme: str = "jwt_hs256",
) -> Callback:
    return Callback.model_validate({"url": url, "auth_scheme": auth_scheme})


def make_opaque_contract(
    *,
    parameters: dict[str, Any] | None = None,
    service_name: str = "sample",
    envelope: Envelope | None = None,
    identity: Identity | None = None,
    references: References | None = None,
    inputs: list[InputSpec] | None = None,
    outputs: list[OutputSpec] | None = None,
    callback: Callback | None = None,
) -> OpaqueServiceContract:
    """Build an OpaqueServiceContract for receiver-side tests.

    Example:
        >>> contract = make_opaque_contract(parameters={"foo": "bar"}, service_name="forecast")
        >>> contract.service.name
        'forecast'
    """
    return OpaqueServiceContract.model_validate(
        {
            "envelope": (envelope or make_envelope()).model_dump(mode="json"),
            "identity": (identity or make_identity()).model_dump(mode="json"),
            "references": (references or make_references()).model_dump(mode="json"),
            "service": make_service_descriptor(name=service_name).model_dump(mode="json"),
            "inputs": [spec.model_dump(mode="json") for spec in (inputs or [make_input_spec()])],
            "outputs": [spec.model_dump(mode="json") for spec in (outputs or [make_output_spec()])],
            "callback": (callback or make_callback()).model_dump(mode="json"),
            "parameters": parameters or {},
        },
    )


def make_contract(  # noqa: UP047 — TypeVar form needed for runtime BaseServiceContract[type(parameters)]
    *,
    parameters: ParamsT,
    envelope: Envelope | None = None,
    identity: Identity | None = None,
    references: References | None = None,
    service: ServiceDescriptor | None = None,
    inputs: list[InputSpec] | None = None,
    outputs: list[OutputSpec] | None = None,
    callback: Callback | None = None,
) -> BaseServiceContract[ParamsT]:
    # `BaseServiceContract[type(parameters)]` is a runtime parameterization that
    # mypy cannot type-check (the index expression isn't a static type), so we
    # build it dynamically and cast the result back to BaseServiceContract[ParamsT].
    parameterized = BaseServiceContract[type(parameters)]  # type: ignore[misc,valid-type]
    contract = parameterized.model_validate(
        {
            "envelope": (envelope or make_envelope()).model_dump(mode="json"),
            "identity": (identity or make_identity()).model_dump(mode="json"),
            "references": (references or make_references()).model_dump(mode="json"),
            "service": (service or make_service_descriptor()).model_dump(mode="json"),
            "inputs": [spec.model_dump(mode="json") for spec in (inputs or [make_input_spec()])],
            "outputs": [spec.model_dump(mode="json") for spec in (outputs or [make_output_spec()])],
            "callback": (callback or make_callback()).model_dump(mode="json"),
            "parameters": parameters.model_dump(mode="json"),
        },
    )
    return cast("BaseServiceContract[ParamsT]", contract)
