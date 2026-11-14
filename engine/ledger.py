"""F5 Prediction Ledger: append-only, hash-chained-by-content JSONL of frozen predictions.

Contract (plan/contracts.md, Phase 2 "Ledger"):

    append(prediction, rationale, author) -> record
    load() -> list[record]
    verify() -> list[{id, ok}]

Each line of ``ledger/predictions.jsonl`` is one JSON object

    {id, created_at, habitat, metric, estimate, band90, model_version,
     artifact_hashes, rationale, author, status: "open", sha256}

``sha256`` is the hex digest of the *canonical JSON* of every other field:
``json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`` encoded
as UTF-8, with floats normalised to finite Python floats (inf/NaN -> null). Anyone can
recompute it with a few lines of code, and git history of the file is the timestamp proof.

Append-only: the file is only ever opened in append mode. Existing lines are never
rewritten. ``verify()`` re-hashes every line, so an edit to an old line is detected.

Paths: every function takes an optional ``path``; the module-level ``LEDGER_PATH``
(default ``ledger/predictions.jsonl``) can also be overridden (tests use a tmp path).
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LEDGER_PATH: Path = ROOT / "ledger" / "predictions.jsonl"
ARTIFACTS_DIR: Path = ROOT / "artifacts"
MANIFEST_PATH: Path = ARTIFACTS_DIR / "MANIFEST.json"

STATUSES = ("open", "confirmed", "refuted", "inconclusive")
HABITAT_KEYS = ("preset_id", "label", "g_m_s2", "p_psia", "o2", "u_cm_s", "L_mm")
ID_PREFIX = "GG-P"


# --------------------------------------------------------------------------- helpers


def jsonable(value: Any) -> Any:
    """Plain-Python, finite-only copy of ``value`` (numpy scalars/arrays, tuples, inf/NaN -> None)."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(v) for v in value]
    if hasattr(value, "tolist") and not isinstance(value, (int, float)):
        return jsonable(value.tolist())
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f if math.isfinite(f) else None


def canonical_json(obj: Any) -> str:
    return json.dumps(jsonable(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def record_hash(record: dict) -> str:
    """sha256 over the canonical JSON of every field except ``sha256``."""
    body = {k: v for k, v in record.items() if k != "sha256"}
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def _path(path: str | Path | None) -> Path:
    return Path(path) if path is not None else Path(LEDGER_PATH)


def artifact_hashes(artifacts_dir: str | Path | None = None) -> dict[str, str]:
    """sha256 of the artifacts the prediction depends on.

    Uses ``artifacts/MANIFEST.json`` when present (it already lists every artifact file);
    otherwise hashes the files directly. ``ai_cache.json`` and ``MANIFEST.json`` are
    excluded because they do not affect predictions.
    """
    adir = Path(artifacts_dir) if artifacts_dir is not None else ARTIFACTS_DIR
    manifest = adir / "MANIFEST.json"
    if manifest.exists():
        try:
            files = json.loads(manifest.read_text(encoding="utf-8")).get("files", {})
            return {k: (v["sha256"] if isinstance(v, dict) else str(v))
                    for k, v in sorted(files.items()) if not k.endswith("ai_cache.json")}
        except (ValueError, KeyError, TypeError):
            pass
    out: dict[str, str] = {}
    if adir.exists():
        for f in sorted(adir.rglob("*")):
            if f.is_file() and f.name not in ("MANIFEST.json", "ai_cache.json"):
                out[f.relative_to(adir).as_posix()] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def _habitat_from(prediction: dict, habitat: dict | None) -> dict:
    src = habitat if habitat is not None else (prediction.get("habitat") or {})
    return {k: src[k] for k in HABITAT_KEYS if k in src}


# --------------------------------------------------------------------------- API


def load(path: str | Path | None = None) -> list[dict]:
    """All ledger records in file order ([] when the file does not exist)."""
    p = _path(path)
    if not p.exists():
        return []
    out = []
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                out.append(json.loads(line))
    return out


def _next_id(records: list[dict]) -> str:
    n = 0
    for r in records:
        rid = str(r.get("id", ""))
        if rid.startswith(ID_PREFIX):
            try:
                n = max(n, int(rid[len(ID_PREFIX):]))
            except ValueError:
                continue
    return f"{ID_PREFIX}{n + 1:04d}"


def append(
    prediction: dict,
    rationale: str,
    author: str,
    *,
    habitat: dict | None = None,
    path: str | Path | None = None,
    created_at: str | None = None,
    artifacts_dir: str | Path | None = None,
) -> dict:
    """Freeze one ``bounds.predict`` output as a new ledger line and return the record.

    ``habitat`` defaults to ``prediction["habitat"]``; it should carry the inputs
    (``g_m_s2, p_psia, o2, u_cm_s, L_mm``) and ideally ``preset_id``/``label``.
    """
    if not isinstance(prediction, dict) or not prediction.get("metric"):
        raise ValueError("prediction must be a bounds.predict dict with a 'metric'")
    if not str(rationale or "").strip():
        raise ValueError("rationale is required")
    if not str(author or "").strip():
        raise ValueError("author is required")
    hab = _habitat_from(prediction, habitat)
    if not all(k in hab for k in ("g_m_s2", "p_psia", "o2", "u_cm_s")):
        raise ValueError("habitat must include g_m_s2, p_psia, o2, u_cm_s")

    p = _path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = load(p)
    record: dict[str, Any] = {
        "id": _next_id(existing),
        "created_at": created_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "habitat": hab,
        "metric": prediction["metric"],
        "estimate": prediction.get("estimate"),
        "band90": prediction.get("band90"),
        "applicable": prediction.get("applicable"),
        "transfer": prediction.get("transfer"),
        "model_version": prediction.get("model_version"),
        "artifact_hashes": artifact_hashes(artifacts_dir),
        "rationale": str(rationale).strip(),
        "author": str(author).strip(),
        "status": "open",
    }
    record = jsonable(record)
    record["sha256"] = record_hash(record)
    line = canonical_json(record) + "\n"
    # Append mode only: existing bytes are never touched.
    with p.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(line)
    return record


def verify(path: str | Path | None = None) -> list[dict]:
    """Recompute every line's hash. Returns ``[{id, ok, line}]`` (``error`` on bad lines)."""
    p = _path(path)
    if not p.exists():
        return []
    out = []
    seen: set[str] = set()
    with p.open("r", encoding="utf-8") as fh:
        for n, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except ValueError as exc:
                out.append({"id": None, "ok": False, "line": n, "error": f"invalid JSON: {exc}"})
                continue
            rid = rec.get("id")
            ok = isinstance(rec.get("sha256"), str) and record_hash(rec) == rec["sha256"]
            item = {"id": rid, "ok": ok, "line": n}
            if not ok:
                item["error"] = "sha256 mismatch"
            elif rid in seen:
                item.update(ok=False, error="duplicate id")
            seen.add(rid)
            out.append(item)
    return out


def main() -> None:  # pragma: no cover - CLI convenience
    results = verify()
    bad = [r for r in results if not r["ok"]]
    print(json.dumps({"path": str(LEDGER_PATH), "n": len(results), "bad": bad}, indent=2))
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":  # pragma: no cover
    main()
