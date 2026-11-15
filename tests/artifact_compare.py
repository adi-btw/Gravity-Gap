"""Compare a committed artifact with a fresh engine build across platforms.

Artifacts are built on Windows and checked on Linux CI. Model fits there differ in the last float digits, so exact
equality fails on numbers and on the model hashes derived from the fitted parameters (``model_version``). This helper
compares numbers with a relative tolerance of 1e-9, strings, booleans, keys and list lengths exactly, and skips the
model-hash keys. Formatted text fields (3 significant figures) must still match exactly.
"""
from __future__ import annotations

import math
from typing import Any

REL = 1e-9
ABS = 1e-12
HASH_KEYS = frozenset({"model_version", "model_versions"})


def diffs(a: Any, b: Any, path: str = "", rel: float = REL, skip: frozenset[str] = HASH_KEYS) -> list[str]:
    """Paths where ``a`` and ``b`` differ (numbers within ``rel`` count as equal)."""
    if isinstance(a, bool) or isinstance(b, bool):
        return [] if a is b else [f"{path}: {a!r} != {b!r}"]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        ok = math.isclose(a, b, rel_tol=rel, abs_tol=ABS)
        return [] if ok else [f"{path}: {a!r} != {b!r}"]
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return [f"{path}: keys {sorted(set(a) ^ set(b))} differ"]
        out: list[str] = []
        for k in a:
            if k not in skip:
                out += diffs(a[k], b[k], f"{path}.{k}", rel, skip)
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: length {len(a)} != {len(b)}"]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += diffs(x, y, f"{path}[{i}]", rel, skip)
        return out
    return [] if a == b else [f"{path}: {a!r} != {b!r}"]


def assert_same_build(a: Any, b: Any, rel: float = REL) -> None:
    found = diffs(a, b, rel=rel)
    assert not found, "artifact differs from the engine build:\n" + "\n".join(found[:20])
