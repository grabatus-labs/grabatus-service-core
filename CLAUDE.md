# CLAUDE.md

Guidance for Claude Code agents working in this repository.

## Task and roadmap management (mandatory rule since 2026-05-09)

**All work items for this repository are tracked as GitHub Issues.**

- Repo (public): https://github.com/grabatus-labs/grabatus-service-core/issues
- Before starting any work: check for an open Issue. Create one if it does not exist.
- Commits must reference the Issue: `closes #N` or `refs #N` (conventional commits).
- **Security vulnerabilities must NEVER be opened as regular Issues on this public repo.**
  Use GitHub Security Advisories (private, maintainer-only):
  https://github.com/grabatus-labs/grabatus-service-core/security/advisories
  All 10 findings from the 2026-05-07 audit are already filed there as drafts.

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

## Protocol contract

`docs/integration_contract.md` is the **canonical specification** of the
protocol — the source of truth for every consumer of this library,
including the `grabatus` platform. It must stay byte-for-byte consistent
with the Pydantic models in `src/grabatus_service_core/contract/`.

Rules:
- Any change to a model in `contract/` must update `integration_contract.md`
  **in the same commit**. Fields added, renamed, or removed; constraints
  changed; new optional sections added — all of them.
- Any new error code added to `errors/` must appear in the taxonomy table
  in §3, with its stage, code string, and a one-line meaning.
- Any change to versioning policy (§4) must be reflected in the document.
- The `grabatus` platform regenerates its integration code from this document.
  A stale document means the platform ships broken integration code.
- When in doubt: the Pydantic models are ground truth; the document is the
  human-readable projection of those models.

## Defensive requirements

- All external HTTP calls: timeout 30s, retry 3x with exponential backoff via `tenacity`.
- Webhook publish: circuit breaker after 5 consecutive failures via `pybreaker`.
- All URIs validated by `UriAuthorizationPort` before any I/O.
