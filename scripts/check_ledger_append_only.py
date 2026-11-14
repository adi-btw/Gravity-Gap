"""T9 part 2: fail if ledger/predictions.jsonl lost or changed any line that exists at a base revision.

The ledger is append-only (plan/08-testing-qa.md T9): new predictions may be added at the end, but a frozen
prediction must never be edited, reordered or removed. This compares the working-tree file with
`git show <base>:ledger/predictions.jsonl`.

Usage:
    python scripts/check_ledger_append_only.py                 # base = $LEDGER_BASE_REF or HEAD
    python scripts/check_ledger_append_only.py --base origin/main
    python scripts/check_ledger_append_only.py --base <sha>

A missing base (first commit, shallow clone, all-zero SHA of a new branch) or a ledger that did not exist at
the base is not an error: there is nothing to protect yet, so the check passes with a notice.
Exit codes: 0 = append-only (or nothing to compare), 1 = violation, 2 = usage / git error.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER_REL = "ledger/predictions.jsonl"
ZERO_SHA = "0" * 40


def _lines(text: str) -> list[str]:
    """Split into records: tolerate CRLF and a trailing newline / trailing blank lines, nothing else."""
    lines = [ln.rstrip("\r") for ln in text.split("\n")]
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def compare_ledgers(old_text: str, new_text: str) -> list[str]:
    """Return human-readable violations; empty list means `new` only appends to `old`."""
    old, new = _lines(old_text), _lines(new_text)
    problems: list[str] = []
    for i, old_line in enumerate(old, start=1):
        if i > len(new):
            problems.append(f"line {i} was removed (base has {len(old)} lines, now {len(new)})")
            break
        if new[i - 1] != old_line:
            problems.append(f"line {i} was changed")
    return problems


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")


def base_ledger(base: str) -> str | None:
    """Ledger text at `base`, or None when the base or the file does not exist there."""
    if not base or base == ZERO_SHA:
        return None
    if _git("rev-parse", "--verify", "--quiet", f"{base}^{{commit}}").returncode != 0:
        return None
    shown = _git("show", f"{base}:{LEDGER_REL}")
    return shown.stdout if shown.returncode == 0 else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default=os.environ.get("LEDGER_BASE_REF") or "HEAD",
                        help="git revision to compare against (default: $LEDGER_BASE_REF or HEAD)")
    parser.add_argument("--file", default=str(ROOT / LEDGER_REL), help="ledger file to check")
    args = parser.parse_args(argv)

    if _git("rev-parse", "--git-dir").returncode != 0:
        print("check_ledger_append_only: not a git repository", file=sys.stderr)
        return 2
    old = base_ledger(args.base)
    if old is None:
        print(f"check_ledger_append_only: no {LEDGER_REL} at base '{args.base}' (first commit or missing base); "
              "nothing to compare.")
        return 0
    path = Path(args.file)
    new = path.read_text(encoding="utf-8") if path.exists() else ""
    problems = compare_ledgers(old, new)
    if problems:
        print(f"check_ledger_append_only: {LEDGER_REL} is append-only, but compared with '{args.base}':")
        for p in problems:
            print(f"  - {p}")
        return 1
    added = len(_lines(new)) - len(_lines(old))
    print(f"check_ledger_append_only: OK vs '{args.base}' ({len(_lines(old))} frozen lines kept, {added} appended)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
