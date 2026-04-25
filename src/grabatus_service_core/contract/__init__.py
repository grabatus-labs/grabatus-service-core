"""Pydantic v2 schemas defining the platform-service protocol."""

from grabatus_service_core.contract.envelope import Envelope
from grabatus_service_core.contract.format_hints import (
    BigQueryHints,
    CsvHints,
    FormatHints,
    InlineHints,
    JsonHints,
    ParquetHints,
    XlsxHints,
)
from grabatus_service_core.contract.identity import Identity
from grabatus_service_core.contract.io_spec import InputSpec
from grabatus_service_core.contract.references import References
from grabatus_service_core.contract.secret_ref import SecretRef
from grabatus_service_core.contract.service_descriptor import ServiceDescriptor

__all__ = [
    "BigQueryHints",
    "CsvHints",
    "Envelope",
    "FormatHints",
    "Identity",
    "InlineHints",
    "InputSpec",
    "JsonHints",
    "ParquetHints",
    "References",
    "SecretRef",
    "ServiceDescriptor",
    "XlsxHints",
]
