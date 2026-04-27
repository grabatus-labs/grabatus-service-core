"""Configure structlog to emit JSON via the stdlib logging foundation.

We deliberately route through ``logging`` (instead of structlog's native
PrintLogger) so external libraries that use the standard logging API are
funneled through the same JSON renderer. The Cloud Logging agent indexes
every top-level field, so we keep the renderer flat (no nested objects
besides explicit ``error`` blocks).
"""

from __future__ import annotations

import logging
import sys
from typing import IO, TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from collections.abc import Iterable


def configure_structlog(
    *,
    stream: IO[str] | None = None,
    level: int = logging.INFO,
) -> None:
    """Configure structlog + stdlib logging for JSON output to ``stream``.

    Calling this more than once replaces the previous configuration; it is
    safe to call from tests with a fresh ``io.StringIO`` per test.
    """
    target = stream or sys.stdout

    handler = logging.StreamHandler(target)
    handler.setFormatter(_PassthroughFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    processors: Iterable[structlog.types.Processor] = (
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    )
    structlog.configure(
        processors=list(processors),
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )


class _PassthroughFormatter(logging.Formatter):
    """Pass through the already-rendered JSON message produced by structlog."""

    def format(self, record: logging.LogRecord) -> str:
        return record.getMessage()
