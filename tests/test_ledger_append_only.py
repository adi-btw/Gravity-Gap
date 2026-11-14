"""T9 part 2: scripts/check_ledger_append_only.py comparison logic."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("check_ledger_append_only",
                                               ROOT / "scripts" / "check_ledger_append_only.py")
chk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chk)

A, B, C = '{"id":"a"}', '{"id":"b"}', '{"id":"c"}'


def test_identical_ok():
    assert chk.compare_ledgers(f"{A}\n{B}\n", f"{A}\n{B}\n") == []


def test_append_ok():
    assert chk.compare_ledgers(f"{A}\n", f"{A}\n{B}\n{C}\n") == []


def test_empty_base_ok():
    assert chk.compare_ledgers("", f"{A}\n") == []


def test_crlf_and_trailing_newline_tolerated():
    assert chk.compare_ledgers(f"{A}\n{B}\n", f"{A}\r\n{B}") == []


def test_changed_line_fails():
    problems = chk.compare_ledgers(f"{A}\n{B}\n", f'{A}\n{{"id":"B"}}\n')
    assert problems == ["line 2 was changed"]


def test_removed_line_fails():
    problems = chk.compare_ledgers(f"{A}\n{B}\n", f"{A}\n")
    assert len(problems) == 1 and "removed" in problems[0]


def test_reorder_fails():
    assert chk.compare_ledgers(f"{A}\n{B}\n", f"{B}\n{A}\n") == ["line 1 was changed", "line 2 was changed"]


def test_insert_in_middle_fails():
    assert chk.compare_ledgers(f"{A}\n{B}\n", f"{A}\n{C}\n{B}\n") == ["line 2 was changed"]


def test_missing_base_passes():
    assert chk.base_ledger(chk.ZERO_SHA) is None
    assert chk.base_ledger("") is None
    assert chk.base_ledger("no-such-ref-xyz") is None


def test_real_ledger_vs_head_is_append_only():
    # Working copy vs the last commit: passes unless someone edited a frozen prediction locally.
    try:
        in_git = chk._git("rev-parse", "--git-dir").returncode == 0
    except FileNotFoundError:
        in_git = False
    if not in_git:
        pytest.skip("not a git checkout")
    assert chk.main(["--base", "HEAD"]) == 0
