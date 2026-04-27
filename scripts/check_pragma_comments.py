"""Fail if any ``# pragma: no cover`` line lacks an inline justification.

ADR-0005 mandates that every coverage exclusion carry an inline
comment explaining why the line is genuinely uncoverable. This script
walks ``src/`` and ``tests/`` and exits non-zero on any bare pragma.

Usage::

    uv run python scripts/check_pragma_comments.py

Examples accepted::

    if sys.platform != "linux":  # pragma: no cover  # atheris is Linux-only
    def stub(self) -> None: ...  # pragma: no cover  # Protocol stub

Examples rejected::

    if False:  # pragma: no cover
    def f() -> None: ...  # pragma: no cover

The accepted pattern requires text after the pragma marker, separated
by ``#``. Whitespace-only suffixes are rejected.
"""

from __future__ import annotations

import re
from pathlib import Path

_PRAGMA_RE = re.compile(r"#\s*pragma:\s*no\s*cover\b(?P<rest>.*)$", re.IGNORECASE)
_JUSTIFICATION_RE = re.compile(r"^\s*#\s*\S")
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCAN_DIRS = ("src", "tests")
# Paths whose pragma comments are intentionally fixture strings, not real
# coverage exclusions. Excluding the file is safer than parsing strings
# out of every source file.
_EXCLUDE_PATHS = (Path("tests") / "unit" / "scripts" / "test_check_pragma_comments.py",)


def _is_unjustified(rest: str) -> bool:
    return _JUSTIFICATION_RE.match(rest) is None


def _is_excluded(path: Path, repo_root: Path) -> bool:
    relative = path.relative_to(repo_root)
    return any(relative == excluded for excluded in _EXCLUDE_PATHS)


def find_violations(repo_root: Path) -> list[tuple[Path, int, str]]:
    violations: list[tuple[Path, int, str]] = []
    for directory in _SCAN_DIRS:
        for path in (repo_root / directory).rglob("*.py"):
            if _is_excluded(path, repo_root):
                continue
            with path.open("r", encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, start=1):
                    match = _PRAGMA_RE.search(line)
                    if match is None:
                        continue
                    if _is_unjustified(match.group("rest")):
                        violations.append((path, lineno, line.rstrip("\n")))
    return violations


def main() -> int:
    violations = find_violations(_REPO_ROOT)
    if not violations:
        print("OK: every # pragma: no cover has an inline justification.")
        return 0

    print("ERROR: the following # pragma: no cover lines lack a justification:")
    for path, lineno, line in violations:
        rel = path.relative_to(_REPO_ROOT)
        print(f"  {rel}:{lineno}: {line}")
    print(
        "\nAdd an inline comment after the pragma explaining why the line "
        "is genuinely uncoverable, e.g.:",
    )
    print("  ...  # pragma: no cover  # Protocol stub")
    return 1


if __name__ == "__main__":  # pragma: no cover  # CLI entry only
    raise SystemExit(main())
