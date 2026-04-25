"""Pydantic v2 schemas defining the platform-service protocol."""

from grabatus_service_core.contract.envelope import Envelope
from grabatus_service_core.contract.identity import Identity
from grabatus_service_core.contract.references import References
from grabatus_service_core.contract.service_descriptor import ServiceDescriptor

__all__ = ["Envelope", "Identity", "References", "ServiceDescriptor"]
