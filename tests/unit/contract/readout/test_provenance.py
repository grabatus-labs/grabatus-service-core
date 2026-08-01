"""Reproducibility pins what would be needed to rerun the fit."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.readout.provenance import InputDigest, Reproducibility

_DIGEST = "a" * 64


def _complete_payload() -> dict[str, object]:
    return {
        "random_seed": 42,
        "compute_duration_seconds": 84.2,
        "input_digests": (InputDigest(role="transactions", sha256=_DIGEST),),
        "library_versions": {"mlxtend": "0.23.1", "pandas": "2.2.0"},
    }


def _reproducibility(**overrides: object) -> Reproducibility:
    payload = _complete_payload()
    payload.update(overrides)
    return Reproducibility(**payload)  # type: ignore[arg-type]


def _reproducibility_missing(field: str) -> Reproducibility:
    payload = _complete_payload()
    del payload[field]
    return Reproducibility(**payload)  # type: ignore[arg-type]


def test_complete_reproducibility_validates() -> None:
    reproducibility = _reproducibility()
    assert reproducibility.random_seed == 42
    assert reproducibility.compute_duration_seconds == 84.2
    assert reproducibility.input_digests[0].sha256 == _DIGEST
    assert reproducibility.library_versions == {"mlxtend": "0.23.1", "pandas": "2.2.0"}


def test_random_seed_is_optional_for_deterministic_methods() -> None:
    assert _reproducibility(random_seed=None).random_seed is None


def test_sha256_must_be_64_hex_characters() -> None:
    with pytest.raises(ValidationError):
        InputDigest(role="transactions", sha256="abc")


def test_sha256_rejects_non_hex_characters() -> None:
    with pytest.raises(ValidationError):
        InputDigest(role="transactions", sha256="z" * 64)


def test_sha256_rejects_uppercase_hex() -> None:
    """Uppercase hex is the most likely integrator mistake for this field."""
    with pytest.raises(ValidationError):
        InputDigest(role="transactions", sha256="A" * 64)


def test_role_must_match_the_shared_role_pattern() -> None:
    with pytest.raises(ValidationError):
        InputDigest(role="Transactions", sha256=_DIGEST)


def test_duration_must_not_be_negative() -> None:
    with pytest.raises(ValidationError):
        _reproducibility(compute_duration_seconds=-1.0)


def test_compute_duration_cannot_be_omitted() -> None:
    """Pydantic v2 does not revalidate a default on omission, so the field
    must be declared without one — otherwise a negative-duration guard could
    be bypassed entirely by dropping the key, unnoticed by the test above.
    """
    with pytest.raises(ValidationError):
        _reproducibility_missing("compute_duration_seconds")


def test_library_versions_are_mandatory() -> None:
    with pytest.raises(ValidationError):
        _reproducibility(library_versions={})


def test_library_versions_cannot_be_omitted() -> None:
    with pytest.raises(ValidationError):
        _reproducibility_missing("library_versions")


def test_input_digests_cannot_exceed_max_digests() -> None:
    too_many = tuple(InputDigest(role=f"role_{index}", sha256=_DIGEST) for index in range(21))
    with pytest.raises(ValidationError):
        _reproducibility(input_digests=too_many)


def test_input_digests_cannot_be_empty() -> None:
    with pytest.raises(ValidationError):
        _reproducibility(input_digests=())


def test_input_digests_cannot_be_omitted() -> None:
    with pytest.raises(ValidationError):
        _reproducibility_missing("input_digests")


def test_library_versions_reject_an_oversized_value() -> None:
    """dict[str, str] has no inherent length bound -- a megabyte-scale
    "version" string would otherwise validate as one dict entry."""
    with pytest.raises(ValidationError):
        _reproducibility(library_versions={"mlxtend": "x" * 2_000_000})


def test_library_versions_reject_an_oversized_key() -> None:
    with pytest.raises(ValidationError):
        _reproducibility(library_versions={"x" * 2_000_000: "0.23.1"})
