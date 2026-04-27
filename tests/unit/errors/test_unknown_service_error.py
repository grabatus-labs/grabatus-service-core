"""Verify UnknownServiceError carries the right ClassVar metadata."""

from grabatus_service_core.errors import UnknownServiceError
from grabatus_service_core.errors.contract import ContractError


def test_unknown_service_error_is_a_contract_error() -> None:
    assert issubclass(UnknownServiceError, ContractError)


def test_unknown_service_error_metadata() -> None:
    assert UnknownServiceError.error_code == "unknown_service"
    assert UnknownServiceError.http_status == 200
    assert UnknownServiceError.retriable is False


def test_unknown_service_error_message_round_trip() -> None:
    err = UnknownServiceError("service.name='ghost' not in registry")
    assert "ghost" in str(err)
