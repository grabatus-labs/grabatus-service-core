"""Pydantic v2 schemas defining the platform-service protocol.

The canonical import path for the readout is
``grabatus_service_core.contract.readout`` — reexported here so the
subpackage is discoverable from the same facade as everything else.
Its private modules (``readout.enums``, ``readout.root``, …) are
implementation detail; import from the subpackage, not from them.
"""

from grabatus_service_core.contract import readout
from grabatus_service_core.contract.base import BaseServiceContract
from grabatus_service_core.contract.callback import Callback
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
from grabatus_service_core.contract.io_spec import InputSpec, OutputSpec
from grabatus_service_core.contract.references import References
from grabatus_service_core.contract.secret_ref import SecretRef
from grabatus_service_core.contract.service_descriptor import ServiceDescriptor
from grabatus_service_core.contract.version import (
    SUPPORTED_PROTOCOL_VERSIONS,
    is_protocol_version_supported,
)

__all__ = [
    "SUPPORTED_PROTOCOL_VERSIONS",
    "BaseServiceContract",
    "BigQueryHints",
    "Callback",
    "CsvHints",
    "Envelope",
    "FormatHints",
    "Identity",
    "InlineHints",
    "InputSpec",
    "JsonHints",
    "OutputSpec",
    "ParquetHints",
    "References",
    "SecretRef",
    "ServiceDescriptor",
    "XlsxHints",
    "is_protocol_version_supported",
    "readout",
]
