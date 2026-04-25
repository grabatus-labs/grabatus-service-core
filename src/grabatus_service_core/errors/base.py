"""Base exception class for all grabatus_service_core errors."""

from __future__ import annotations

from typing import ClassVar


class GrabatusServiceError(Exception):
    """Abstract base for all errors raised by grabatus_service_core.

    Subclasses MUST declare the three ``ClassVar`` attributes ``error_code``,
    ``http_status``, and ``retriable``. Direct instantiation of this base
    class is not permitted.

    Example::

        class InputReadError(StorageError):
            error_code = "input_read_failed"
            http_status = 200
            retriable = True
    """

    error_code: ClassVar[str]
    http_status: ClassVar[int]
    retriable: ClassVar[bool]

    def __init__(
        self,
        message: str,
        *,
        context: dict[str, object] | None = None,
    ) -> None:
        if "error_code" not in type(self).__dict__ and not hasattr(type(self), "error_code"):
            raise NotImplementedError(
                f"{type(self).__name__} must declare a class-level " f"'error_code' attribute"
            )
        if type(self) is GrabatusServiceError:
            raise NotImplementedError(
                "GrabatusServiceError is abstract; subclass must declare "
                "'error_code', 'http_status', and 'retriable'"
            )
        super().__init__(message)
        self.context: dict[str, object] = context or {}
