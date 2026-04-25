"""Errors raised by storage adapters during input read or output write."""

from __future__ import annotations

from grabatus_service_core.errors.base import GrabatusServiceError


class StorageError(GrabatusServiceError):
    """Base for storage I/O failures."""

    error_code = "storage_error"
    http_status = 200
    retriable = True


class InputNotFoundError(StorageError):
    """The requested input URI does not exist."""

    error_code = "input_not_found"
    retriable = False


class InputReadError(StorageError):
    """Reading the input failed (network, permissions, transient I/O)."""

    error_code = "input_read_failed"


class OutputWriteError(StorageError):
    """Writing the output failed."""

    error_code = "output_write_failed"


class FormatParsingError(StorageError):
    """The bytes could not be parsed in the declared format."""

    error_code = "format_parsing_failed"
    retriable = False
