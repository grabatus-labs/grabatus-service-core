"""A caveat pairs a limitation with the conclusion it forbids."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grabatus_service_core.contract.readout.caveats import Caveat


def test_caveat_pairs_statement_with_forbidden_conclusion() -> None:
    caveat = Caveat(
        severity="high",
        statement="A análise não separa período promocional de período orgânico.",
        do_not_conclude="Não atribua a afinidade observada a preferência do cliente.",
    )
    assert caveat.severity == "high"
    assert caveat.do_not_conclude == ("Não atribua a afinidade observada a preferência do cliente.")


def test_do_not_conclude_cannot_be_empty() -> None:
    """A caveat without it is a disclaimer nobody acts on."""
    with pytest.raises(ValidationError):
        Caveat(severity="low", statement="Alguma limitação.", do_not_conclude="")


def test_do_not_conclude_cannot_be_omitted() -> None:
    """Pydantic v2 does not revalidate a default on omission, so the field
    must have no default — otherwise the mandatory conclusion becomes
    silently optional without breaking the empty-string test above.
    """
    with pytest.raises(ValidationError):
        Caveat(severity="low", statement="Alguma limitação.")  # type: ignore[call-arg]


def test_unknown_severity_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Caveat(severity="critical", statement="s", do_not_conclude="d")  # type: ignore[arg-type]
