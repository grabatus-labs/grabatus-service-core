"""NullObservability: no-op implementation for tests."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator


class NullObservability:
    """Records nothing; satisfies ObservabilityPort for tests."""

    def log(self, event: str, **fields: Any) -> None:  # noqa: ANN401
        return None

    @contextmanager
    def span(self, name: str, **attrs: Any) -> Iterator[None]:  # noqa: ANN401
        yield None

    def metric(self, name: str, value: float, **tags: Any) -> None:  # noqa: ANN401
        return None
