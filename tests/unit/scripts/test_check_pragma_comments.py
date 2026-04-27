"""Tests for ``scripts/check_pragma_comments.py``."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest  # noqa: TC002  # CaptureFixture used at runtime via parametrised type alias

if TYPE_CHECKING:
    from collections.abc import Iterable

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import check_pragma_comments  # noqa: E402


def _write_tree(tmp_path: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def _capture_stdout(capsys: pytest.CaptureFixture[str]) -> Iterable[str]:
    return capsys.readouterr().out.splitlines()


def test_clean_tree_returns_zero(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_tree(
        tmp_path,
        {
            "src/foo.py": "x = 1\n",
            "tests/test_foo.py": "y = 2  # pragma: no cover  # justification\n",
        },
    )

    rc = check_pragma_comments.find_violations(tmp_path)

    assert rc == []
    monkey_main_rc = _run_main(tmp_path)
    out = _capture_stdout(capsys)
    assert monkey_main_rc == 0
    assert any("OK" in line for line in out)


def test_unjustified_pragma_in_src_is_reported(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_tree(
        tmp_path,
        {
            "src/foo.py": "x = 1  # pragma: no cover\n",
            "tests/test_foo.py": "",
        },
    )

    rc = _run_main(tmp_path)
    out = _capture_stdout(capsys)

    assert rc == 1
    assert any("src/foo.py:1" in line for line in out)


def test_whitespace_only_suffix_is_unjustified(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_tree(
        tmp_path,
        {
            "src/foo.py": "x = 1  # pragma: no cover     \n",
            "tests/test_foo.py": "",
        },
    )

    rc = _run_main(tmp_path)
    out = _capture_stdout(capsys)

    assert rc == 1
    assert any("src/foo.py:1" in line for line in out)


def test_excluded_paths_are_not_scanned(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    excluded = Path("tests") / "unit" / "fake_excluded.py"
    monkeypatch.setattr(check_pragma_comments, "_EXCLUDE_PATHS", (excluded,))
    _write_tree(
        tmp_path,
        {
            str(excluded): "x = 1  # pragma: no cover\n",
            "src/clean.py": "y = 2\n",
        },
    )

    rc = _run_main(tmp_path)
    out = _capture_stdout(capsys)

    assert rc == 0
    assert any("OK" in line for line in out)


def test_justified_pragma_passes(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _write_tree(
        tmp_path,
        {
            "src/foo.py": "x = 1  # pragma: no cover  # version guard\n",
            "tests/test_foo.py": "",
        },
    )

    rc = _run_main(tmp_path)
    out = _capture_stdout(capsys)

    assert rc == 0
    assert any("OK" in line for line in out)


def _run_main(repo_root: Path) -> int:
    """Re-route the script's repo root to a temp directory."""
    original = check_pragma_comments._REPO_ROOT
    check_pragma_comments._REPO_ROOT = repo_root
    try:
        return check_pragma_comments.main()
    finally:
        check_pragma_comments._REPO_ROOT = original
