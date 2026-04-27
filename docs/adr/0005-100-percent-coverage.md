# ADR-0005 — 100% line + branch coverage with justified pragmas

- **Status:** Accepted
- **Date:** 2026-04-26

## Context

The library is a **shared dependency** of every Grabatus computational service. A regression here propagates to all services. We need confidence that every code path is exercised by tests, not just the happy path.

Standard 80% coverage targets are too lenient: they leave the specific branches (error handling, retry paths, rare edge cases) untested precisely because those are the lines hardest to exercise. These are also the lines most likely to break in production.

We additionally need protection against shallow tests that achieve coverage with weak asserts (e.g., `assert isinstance(x, dict)` when the contract guarantees a specific shape).

## Decision

The library enforces **100% line + branch coverage**, measured by `coverage.py` with `branch=True` in `pyproject.toml`. The coverage gate (`--cov-fail-under=100`) blocks any pull request that drops below 100%.

Where a line is genuinely impossible to cover (Protocol stubs, version guards, lazy imports inside try/except, defensive guards for impossible states), `# pragma: no cover` is allowed **only with an inline comment** explaining why. The CI script `scripts/check_pragma_comments.py` enforces that every `pragma: no cover` carries a justification.

A **mutation score floor of 95%** (`mutmut`) protects against shallow tests. Mutation runs only pre-merge to `main` (~30 minutes) so it does not slow every push.

## Alternatives Considered

- **80% coverage:** Too lenient — error paths typically fall in the unmeasured 20%.
- **No coverage gate, mutation only:** Mutation testing is too slow (30+ min) for every push, and developers want fast feedback.
- **100% line, no branch:** Misses untested branches in `if`/`elif` chains.
- **Per-file coverage thresholds:** Rejected as administrative overhead with no clear benefit over a single project-wide gate.

## Consequences

- Every new feature ships with comprehensive tests, including error paths.
- Refactoring is safer because the test suite catches regressions in branches that 80% gates would miss.
- The discipline shapes design: code that is hard to test gets refactored before being merged.
- The cost is that writing the last 5% of coverage takes disproportionate effort. We pay this cost once per feature.
- `# pragma: no cover` accumulates over time; the comment-required rule prevents anonymous pragmas from sneaking in. The CI script fails the build if a bare pragma is committed.
