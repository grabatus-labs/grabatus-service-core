"""tenacity-backed retry decorator for transient adapter failures."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")

_DEFAULT_MAX_ATTEMPTS = 3
_DEFAULT_INITIAL_BACKOFF = 0.5
_DEFAULT_MAX_BACKOFF = 8.0


def with_retry(
    *,
    retry_on: tuple[type[BaseException], ...],
    max_attempts: int = _DEFAULT_MAX_ATTEMPTS,
    initial_backoff: float = _DEFAULT_INITIAL_BACKOFF,
    max_backoff: float = _DEFAULT_MAX_BACKOFF,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator that retries a callable on the configured exception types.

    Uses exponential backoff (``initial_backoff`` doubling up to ``max_backoff``).
    Adapters wrap their I/O entry points with this decorator; domain code
    never retries directly so the policy stays in one place.
    """
    return retry(  # type: ignore[no-any-return,unused-ignore]
        retry=retry_if_exception_type(retry_on),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=initial_backoff, max=max_backoff),
        reraise=True,
    )
