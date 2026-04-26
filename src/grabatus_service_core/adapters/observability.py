"""StructlogObservability: production ObservabilityPort backed by structlog.

This adapter intentionally implements only logs and metrics-as-logs. Real
OpenTelemetry tracing is configured separately by the application; here
the ``span`` context manager is a no-op that returns ``None`` so the
runner can use it uniformly across modes.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Iterator


_METRIC_LOG_KEY = "metric"


class StructlogObservability:
    """Routes log/span/metric calls to structlog (JSON in production)."""

    def __init__(self, *, logger: structlog.stdlib.BoundLogger | None = None) -> None:
        self._logger = logger or structlog.get_logger()

    def log(self, event: str, **fields: Any) -> None:  # noqa: ANN401
        self._logger.info(event, **fields)

    @contextmanager
    def span(self, name: str, **attrs: Any) -> Iterator[None]:  # noqa: ANN401
        # OpenTelemetry tracing is wired by the application factory; this
        # adapter only records that the span was entered/exited so that
        # logs around span boundaries carry the same fields.
        self._logger.debug("span_start", span=name, **attrs)
        try:
            yield None
        finally:
            self._logger.debug("span_end", span=name)

    def metric(self, name: str, value: float, **tags: Any) -> None:  # noqa: ANN401
        self._logger.info(_METRIC_LOG_KEY, metric_name=name, metric_value=value, **tags)
