"""Tests for the FormatHints discriminated union."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from grabatus_service_core.contract.format_hints import (
    BigQueryHints,
    CsvHints,
    FormatHints,
    InlineHints,
    JsonHints,
    ParquetHints,
    XlsxHints,
)


class _Holder(BaseModel):
    """Lightweight model exercising the discriminated union."""

    hints: FormatHints


def test_xlsx_hints_accepts_full_payload() -> None:
    holder = _Holder.model_validate(
        {"hints": {"format": "xlsx", "sheet": "Dados", "header": 0}},
    )

    assert isinstance(holder.hints, XlsxHints)
    assert holder.hints.sheet == "Dados"
    assert holder.hints.header == 0


def test_xlsx_hints_uses_defaults_when_omitted() -> None:
    holder = _Holder.model_validate({"hints": {"format": "xlsx"}})

    assert isinstance(holder.hints, XlsxHints)
    assert holder.hints.sheet == "Sheet1"
    assert holder.hints.header == 0


def test_xlsx_hints_rejects_typos() -> None:
    with pytest.raises(ValidationError, match="extra"):
        _Holder.model_validate({"hints": {"format": "xlsx", "sheetname": "Dados"}})


def test_csv_hints_round_trips() -> None:
    holder = _Holder.model_validate(
        {"hints": {"format": "csv", "delimiter": ";", "encoding": "latin-1"}},
    )

    assert isinstance(holder.hints, CsvHints)
    assert holder.hints.delimiter == ";"
    assert holder.hints.encoding == "latin-1"


def test_bigquery_hints_optional_query() -> None:
    holder = _Holder.model_validate(
        {"hints": {"format": "bigquery", "location": "US"}},
    )

    assert isinstance(holder.hints, BigQueryHints)
    assert holder.hints.query is None
    assert holder.hints.location == "US"


def test_parquet_hints_partition() -> None:
    holder = _Holder.model_validate(
        {"hints": {"format": "parquet", "partition": "year=2026"}},
    )

    assert isinstance(holder.hints, ParquetHints)
    assert holder.hints.partition == "year=2026"


def test_json_hints_default() -> None:
    holder = _Holder.model_validate({"hints": {"format": "json"}})

    assert isinstance(holder.hints, JsonHints)


def test_inline_hints_default() -> None:
    holder = _Holder.model_validate({"hints": {"format": "inline"}})

    assert isinstance(holder.hints, InlineHints)


def test_unknown_format_is_rejected() -> None:
    with pytest.raises(ValidationError, match="format"):
        _Holder.model_validate({"hints": {"format": "yaml"}})


def test_discriminator_routes_to_correct_class() -> None:
    holder = _Holder.model_validate(
        {"hints": {"format": "csv", "delimiter": "\t"}},
    )

    assert type(holder.hints).__name__ == "CsvHints"


def test_xlsx_header_must_be_non_negative() -> None:
    with pytest.raises(ValidationError, match="header"):
        _Holder.model_validate({"hints": {"format": "xlsx", "header": -1}})


def test_each_hint_class_is_frozen() -> None:
    holder = _Holder.model_validate({"hints": {"format": "xlsx"}})

    with pytest.raises(ValidationError, match="frozen"):
        holder.hints.sheet = "Other"  # type: ignore[misc]
