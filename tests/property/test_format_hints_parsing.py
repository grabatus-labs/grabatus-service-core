"""Property tests: FormatHints parsing never crashes uncaught.

The discriminated union in ``contract.format_hints`` is the entry
point for arbitrary, possibly attacker-controlled JSON. The invariant
is that parsing either succeeds (round-trip equality holds) or raises
a ``ValidationError`` — never an unexpected exception.
"""

from __future__ import annotations

from typing import Any

from hypothesis import given
from hypothesis import strategies as st
from pydantic import TypeAdapter, ValidationError

from grabatus_service_core.contract.format_hints import FormatHints

_FormatHintsAdapter: TypeAdapter[FormatHints] = TypeAdapter(FormatHints)


def _payload_strategy(
    fmt: str,
    optional: dict[str, st.SearchStrategy[Any]] | None = None,
) -> st.SearchStrategy[dict[str, Any]]:
    return st.fixed_dictionaries(
        {"format": st.just(fmt)},
        optional=optional or {},
    )


_xlsx_payload = _payload_strategy(
    "xlsx",
    optional={
        "sheet": st.text(min_size=1, max_size=64),
        "header": st.integers(min_value=0, max_value=128),
    },
)
_csv_payload = _payload_strategy(
    "csv",
    optional={
        "delimiter": st.text(min_size=1, max_size=4),
        "encoding": st.text(min_size=1, max_size=32),
    },
)
_json_payload = _payload_strategy("json")
_parquet_payload = _payload_strategy(
    "parquet",
    optional={"partition": st.text(min_size=0, max_size=256)},
)
_bigquery_payload = _payload_strategy(
    "bigquery",
    optional={
        "query": st.text(min_size=0, max_size=8192),
        "location": st.text(min_size=1, max_size=32),
    },
)
_inline_payload = _payload_strategy("inline")

_valid_payloads = st.one_of(
    _xlsx_payload,
    _csv_payload,
    _json_payload,
    _parquet_payload,
    _bigquery_payload,
    _inline_payload,
)


@given(payload=_valid_payloads)
def test_valid_format_payload_round_trips(payload: dict[str, Any]) -> None:
    parsed = _FormatHintsAdapter.validate_python(payload)
    redumped = _FormatHintsAdapter.dump_python(parsed)

    reparsed = _FormatHintsAdapter.validate_python(redumped)
    assert reparsed == parsed


@given(
    payload=st.dictionaries(
        keys=st.text(min_size=1, max_size=16),
        values=st.one_of(
            st.text(min_size=0, max_size=32),
            st.integers(),
            st.booleans(),
            st.none(),
        ),
        max_size=8,
    ),
)
def test_arbitrary_payloads_either_validate_or_raise_validation_error(
    payload: dict[str, Any],
) -> None:
    try:
        _FormatHintsAdapter.validate_python(payload)
    except ValidationError:
        return
