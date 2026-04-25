# CLAUDE.md

Guidance for Claude Code agents working in this repository.

## Code style

- Functions: max 20 lines. Split if longer.
- Files: under 500 lines. Split by responsibility.
- One thing per function, one responsibility per module (SRP).
- Names: specific enough that every grep hit is relevant. Avoid `data`, `handler`, `Manager`.
- Types: explicit everywhere. No `Any`, no untyped functions. `mypy --strict` is the gate.
- No code duplication. Extract shared logic before it needs to change.
- Early returns over nested ifs. Max 3 levels of indentation.
- Exception messages must include the offending value: `f"expected X, got {repr(v)!r}"`.
- No magic numbers or strings — use named constants.
- No positional boolean parameters — keyword-only or enums.
- Functions return one consistent type or raise — never `T | None` as control flow.

## Errors & failures

- No silent failures: every `except` must log+reraise or handle explicitly. Never `pass`.
- Catch the most specific exception type available.
- Domain code never catches `Exception` — only the FastAPI boundary handler does.

## Tests

- Run: `uv run pytest`
- Single file: `uv run pytest tests/unit/path/test_x.py -v`
- Coverage 100% line + branch is enforced. `# pragma: no cover` requires inline justification.
- Mock only at system boundaries (cloud SDKs). Never mock our own services.
- Tests must be FIRST: Fast, Independent, Repeatable, Self-validating, Timely.

## Dependencies

- Inject through constructor/parameter, not global/import.
- Wrap third-party libs behind a Protocol owned by this project (see `ports/`).

## Structure

- `src/grabatus_service_core/contract/` — Pydantic schemas (the protocol)
- `src/grabatus_service_core/ports/` — Protocols (interfaces)
- `src/grabatus_service_core/adapters/` — concrete implementations of ports
- `src/grabatus_service_core/runner/` — orchestrator (`ServiceRunner`)
- `src/grabatus_service_core/errors/` — exception hierarchy
- `src/grabatus_service_core/api/` — FastAPI integration
- `src/grabatus_service_core/security/` — security primitives
- `src/grabatus_service_core/observability/` — logging/tracing/metrics
- `src/grabatus_service_core/testing/` — public test fakes (consumed by services)

## Formatting

- `uv run ruff format` — automated, no debate.
- `uv run ruff check --fix` — lints and autofixes.

## Logging

- Structured JSON via `structlog`. Always use `extra={...}` with named fields.
- Bind `request_id`, `tenant_id`, `service_name` via `contextvars` at request boundary.

## Commits

- Conventional commits: `type: describe the WHY, not the WHAT`.
- Reference issue numbers when relevant.
- Never amend commits unless explicitly asked.

## Defensive requirements

- All external HTTP calls: timeout 30s, retry 3x with exponential backoff via `tenacity`.
- Webhook publish: circuit breaker after 5 consecutive failures via `pybreaker`.
- All URIs validated by `UriAuthorizationPort` before any I/O.
