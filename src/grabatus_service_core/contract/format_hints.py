"""FormatHints: per-format parsing/serialization options.

Implemented as a discriminated union keyed on ``format``. Each format
declares its own model with ``extra='forbid'`` so that typos (e.g.
``sheetname`` instead of ``sheet``) fail validation immediately rather
than silently falling through to a default value at runtime.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class _BaseHints(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class XlsxHints(_BaseHints):
    """Hints for reading or writing Excel spreadsheets."""

    format: Literal["xlsx"]
    sheet: str = Field(default="Sheet1", min_length=1, max_length=64)
    header: int = Field(default=0, ge=0, le=128)


class CsvHints(_BaseHints):
    """Hints for reading or writing CSV files."""

    format: Literal["csv"]
    delimiter: str = Field(default=",", min_length=1, max_length=4)
    encoding: str = Field(default="utf-8", min_length=1, max_length=32)


class JsonHints(_BaseHints):
    """Hints for reading or writing JSON files."""

    format: Literal["json"]


class ParquetHints(_BaseHints):
    """Hints for reading or writing Parquet files."""

    format: Literal["parquet"]
    partition: str | None = Field(default=None, max_length=256)


class BigQueryHints(_BaseHints):
    """Hints for BigQuery sources or destinations."""

    format: Literal["bigquery"]
    query: str | None = Field(default=None, max_length=8192)
    location: str = Field(default="US", min_length=1, max_length=32)


class InlineHints(_BaseHints):
    """Hints for inline payloads (small data embedded in the URI)."""

    format: Literal["inline"]


FormatHints = Annotated[
    XlsxHints | CsvHints | JsonHints | ParquetHints | BigQueryHints | InlineHints,
    Field(discriminator="format"),
]
