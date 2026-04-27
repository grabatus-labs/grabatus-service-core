"""Tests for structlog JSON configuration."""

from __future__ import annotations

import io
import json
import logging

import structlog

from grabatus_service_core.observability.logging import configure_structlog


def test_configure_structlog_emits_json_with_event_field() -> None:
    buf = io.StringIO()
    configure_structlog(stream=buf, level=logging.INFO)

    structlog.get_logger().info("upload_received", user_id="999", file_id="abc")

    line = buf.getvalue().strip()
    record = json.loads(line)
    assert record["event"] == "upload_received"
    assert record["user_id"] == "999"
    assert record["file_id"] == "abc"


def test_configure_structlog_includes_contextvars() -> None:
    buf = io.StringIO()
    configure_structlog(stream=buf, level=logging.INFO)
    structlog.contextvars.bind_contextvars(request_id="r-1")
    try:
        structlog.get_logger().info("processing")
    finally:
        structlog.contextvars.clear_contextvars()

    line = buf.getvalue().strip()
    record = json.loads(line)
    assert record["request_id"] == "r-1"


def test_configure_structlog_respects_level() -> None:
    buf = io.StringIO()
    configure_structlog(stream=buf, level=logging.WARNING)

    structlog.get_logger().info("hidden")
    structlog.get_logger().warning("shown")

    lines = [json.loads(line) for line in buf.getvalue().splitlines()]
    events = [record["event"] for record in lines]
    assert events == ["shown"]
