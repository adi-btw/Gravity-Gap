"""Seed the F5 Prediction Ledger with the team's pre-demo predictions (run ONCE).

    python scripts/seed_ledger.py

Appends >= 5 predictions from engine.bounds.predict to ledger/predictions.jsonl. Rationales are
generated only from the prediction's own fields (no invented numbers). Refuses to run when the
ledger already has entries: the ledger is append-only and seeding twice would duplicate predictions.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import bounds, ledger  # noqa: E402
from engine.presets import PRESETS_BY_ID  # noqa: E402

AUTHOR = "Gravity Gap team (seeded)"
# (preset, metric) wanted, with fallbacks used when the wanted metric is not applicable.
PLAN = [
    ("lunar_base", ["M1"]),
    ("lunar_base", ["M3"]),
    ("mars_base", ["M1"]),
    ("lunar_rover", ["M2", "M3", "M1"]),
    ("exploration", ["M3", "M1"]),
]
FIELDS = ("g_m_s2", "p_psia", "o2", "u_cm_s", "L_mm")


def _f(x) -> str:
    return f"{x:.3g}" if isinstance(x, (int, float)) else str(x)


def rationale(pred: dict, preset: dict) -> str:
    fr = pred.get("regime_fractions") or {}
    tr = pred.get("transfer") or {}
    lo, hi = (pred.get("band90") or [None, None])[:2]
    invs = sorted({e["investigation_id"] for e in pred.get("evidence") or []})
    return (
        f"{preset['label']} ({_f(preset['g_m_s2'])} m/s^2, {_f(preset['p_psia'])} psia, O2 {_f(preset['o2'])}, "
        f"vent {_f(preset['u_cm_s'])} cm/s): {pred['metric']} '{pred['label']}' estimate {_f(pred['estimate'])} "
        f"with 90% band [{_f(lo)}, {_f(hi)}]. Monte Carlo regime mix forced {_f(fr.get('forced'))} / mixed "
        f"{_f(fr.get('mixed'))} / buoyant {_f(fr.get('buoyant'))}; transfer confidence {tr.get('confidence')}. "
        f"Trained on {pred.get('n_train')} microgravity tests from {', '.join(invs) or 'n/a'} "
        f"(model {pred.get('model_version')}). Check: a partial-gravity (LUCI/FM2-type) test at these conditions "
        f"confirms this prediction if the measured value falls inside the band."
    )


def main() -> int:
    existing = ledger.load()
    if existing:
        print(f"refusing to re-seed: {ledger.LEDGER_PATH} already has {len(existing)} entries")
        return 1
    written = []
    for pid, metrics in PLAN:
        preset = PRESETS_BY_ID[pid]
        hab = {k: preset[k] for k in FIELDS}
        for m in metrics:
            pred = bounds.predict(m, **hab)
            if not pred.get("applicable"):
                print(f"skip {pid} {m}: not applicable ({pred.get('reason')})")
                continue
            rec = ledger.append(pred, rationale(pred, preset), AUTHOR,
                                habitat={"preset_id": pid, "label": preset["label"], **hab})
            written.append(rec)
            print(f"{rec['id']} {pid} {m} estimate={_f(rec['estimate'])} sha256={rec['sha256'][:12]}")
            break
    print(f"wrote {len(written)} predictions to {ledger.LEDGER_PATH}")
    return 0 if len(written) >= 5 else 2


if __name__ == "__main__":
    raise SystemExit(main())
