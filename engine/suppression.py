"""R2 suppression calculator: how CO2 or helium dilution changed droplet flames in FLEX (TL).

Contract: plan/contracts.md "Round 2 · R2 Suppression calculator addendum".
Decision: ADR-0006 (dilution-aware honesty gate) in plan/decisions.md.

Composition rule: the habitat O2 mole fraction and total pressure are held fixed and the
diluent replaces nitrogen, so ``n2 = 1 - o2 - fraction``. FLEX compositions sum to 1 the same
way (O2 + N2 + CO2 or He). A point with n2 < 0 is ``applicable: false`` ("composition over
100%").

Each point is a plain ``engine.bounds.predict("M1"/"M2", ..., co2=..., he=...)`` call, so the
same gravity honesty rule (ADR-0005) and the same gate (ADR-0006) apply as on the Bounds panel.
No new model is fitted. M1 = P(droplet flame self-extinguishes before burnout), M2 = extinction
diameter in mm.

Runtime: the M1 bootstrap (500 refits) is fitted once per process and cached by engine.models,
and the Monte Carlo physics does not depend on the diluent, so a 15-point curve costs about the
same as two Bounds calls per point (well under a second after the first fit). ``n_boot`` and
``n`` are exposed for tests.

Run ``python -m engine.suppression`` to write artifacts/suppression/{preset}_{co2|he}.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from engine import bounds
from engine.bounds import GATE_DISTANCE, N_BOOT_DEFAULT, json_safe
from engine.models import get_model, training_set
from engine.physics import PSIA_PER_ATM
from engine.presets import PRESETS

ARTIFACT_DIR = Path(__file__).resolve().parent.parent / "artifacts" / "suppression"

DILUENTS = {
    "co2": {"label": "Carbon dioxide (CO2)", "max": 0.70},
    "he": {"label": "Helium", "max": 0.45},
}
_SYMBOL = {"co2": "CO₂", "he": "helium"}
P90 = 0.9
SAFETY_NOTE = (
    "CO₂ at these concentrations is dangerous to breathe. Spacecraft use portable CO₂ or "
    "water-mist extinguishers aimed at the fire, not cabin flooding. This shows how dilution affected "
    "flames in NASA's tests; it is not an operating procedure."
)
COMPOSITION_REASON = "composition over 100%"


def _pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def tested_conditions(diluent: str) -> list[dict]:
    """FLEX M1 training tests with this diluent > 0, aggregated by (O2, pressure, fraction)."""
    ts = training_set("M1")
    frac = ts.X[diluent].to_numpy(dtype=float)
    mask = frac > 0
    df = pd.DataFrame({
        "o2": np.round(ts.o2[mask], 3),
        "p_atm": np.round(ts.p_atm[mask], 2),
        "fraction": np.round(frac[mask], 3),
        "ext": ts.y[mask],
    })
    g = (df.groupby(["o2", "p_atm", "fraction"])["ext"].agg(n="size", extinctions="sum")
         .reset_index())
    return [
        {"o2": float(r.o2), "p_atm": float(r.p_atm), "fraction": float(r.fraction),
         "n": int(r.n), "extinctions": int(r.extinctions)}
        for r in g.itertuples(index=False)
    ]


def _metric_point(res: dict) -> dict:
    return {"applicable": bool(res["applicable"]), "estimate": res["estimate"],
            "band90": res["band90"], "reason": res["reason"]}


def _invalid_point() -> dict:
    return {"applicable": False, "estimate": None, "band90": None, "reason": COMPOSITION_REASON}


def _gate_note(diluent: str, o2: float, p_atm: float, o2_range, p_range, points: list[dict]) -> str:
    sym = _SYMBOL[diluent]
    if o2_range is None:
        return f"FLEX has no {sym}-diluted tests, so no dilution estimate is shown."
    lo, hi = o2_range
    tested = (f"FLEX tested {sym} dilution only between {_pct(lo)} and {_pct(hi)} O₂ "
              f"({p_range[0]:.2f}-{p_range[1]:.2f} atm)")
    diluted = [p for p in points if p["fraction"] > 0 and p["n2"] >= 0]
    ok = [p for p in diluted if p["M1"]["applicable"]]
    if not ok:
        where = f"at {_pct(o2)} O₂ and {p_atm:.2f} atm"
        return (f"{tested}; {where} there is no evidence, so no number is shown for any {sym} fraction. "
                f"An answer here needs new dilution tests at this oxygen level.")
    fmax = max(p["fraction"] for p in ok)
    gated = [p for p in diluted if not p["M1"]["applicable"]]
    txt = (f"{tested}. This habitat ({_pct(o2)} O₂, {p_atm:.2f} atm) is close enough to those tests "
           f"(distance <= {GATE_DISTANCE:g}, ADR-0006) for {sym} fractions up to {_pct(fmax)}")
    if gated:
        txt += "; beyond that there is no evidence and the curve has a gap"
    return txt + ". Gravity does not change these numbers; it only widens the band (ADR-0005)."


def curve(diluent: str, g_m_s2: float, p_psia: float, o2: float, u_cm_s: float, L_mm: float,
          steps: int = 15, seed: int = 0, n: int = 2000, n_boot: int = N_BOOT_DEFAULT) -> dict:
    """M1 and M2 versus diluent fraction (0..DILUENTS[d]["max"], ``steps`` points), contract shape."""
    if diluent not in DILUENTS:
        raise ValueError(f"diluent must be one of {sorted(DILUENTS)}, got {diluent!r}")
    steps = int(steps)
    if steps < 2:
        raise ValueError("steps must be >= 2")
    if p_psia <= 0:
        raise ValueError("p_psia must be > 0")
    if not 0 <= o2 <= 1:
        raise ValueError("o2 must be a mole fraction in [0, 1]")

    fractions = np.round(np.linspace(0.0, DILUENTS[diluent]["max"], steps), 6)
    points = []
    for f in fractions:
        f = float(f)
        n2 = 1.0 - o2 - f
        pt = {"fraction": f, "n2": round(n2, 6)}
        if n2 < -1e-9:
            pt.update(M1=_invalid_point(), M2=_invalid_point())
        else:
            dil = {"co2": f if diluent == "co2" else 0.0, "he": f if diluent == "he" else 0.0}
            for m in ("M1", "M2"):
                res = bounds.predict(m, g_m_s2, p_psia, o2, u_cm_s, L_mm, n=n, seed=seed,
                                     n_boot=n_boot, **dil)
                pt[m] = _metric_point(res)
        points.append(pt)

    dose = None
    for pt in points:
        e = pt["M1"]["estimate"]
        if pt["M1"]["applicable"] and e is not None and e >= P90:
            dose = {"fraction": pt["fraction"], "metric": "M1"}
            if pt["fraction"] == 0:
                dose["note"] = ("The M1 estimate is already at or above 90% with no dilution: in FLEX most "
                                "droplet flames in this atmosphere went out on their own before burnout.")
            break

    tested = tested_conditions(diluent)
    o2_range = [min(t["o2"] for t in tested), max(t["o2"] for t in tested)] if tested else None
    p_range = [min(t["p_atm"] for t in tested), max(t["p_atm"] for t in tested)] if tested else None
    p_atm = p_psia / PSIA_PER_ATM
    out = {
        "diluent": diluent,
        "label": DILUENTS[diluent]["label"],
        "habitat": {"g_m_s2": g_m_s2, "p_psia": p_psia, "o2": o2, "u_cm_s": u_cm_s, "L_mm": L_mm},
        "composition_rule": ("O2 and total pressure are held at the habitat values; the diluent replaces "
                             "nitrogen (n2 = 1 - o2 - fraction)."),
        "points": points,
        "dose_for_p90": dose,
        "tested": tested,
        "tested_o2_range": o2_range,
        "gate_note": _gate_note(diluent, o2, p_atm, o2_range, p_range, points),
        "safety_note": SAFETY_NOTE,
        "model_version": (f"M1 {get_model('M1', n_boot=n_boot).model_version}, "
                          f"M2 {get_model('M2', n_boot=n_boot).model_version}"),
    }
    return json_safe(out)


def build_artifacts(out_dir: Path = ARTIFACT_DIR, steps: int = 15, n: int = 2000,
                    n_boot: int = N_BOOT_DEFAULT) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for preset in PRESETS:
        hab = {k: preset[k] for k in ("g_m_s2", "p_psia", "o2", "u_cm_s", "L_mm")}
        for d in DILUENTS:
            res = {"preset_id": preset["id"], **curve(d, **hab, steps=steps, n=n, n_boot=n_boot)}
            path = out_dir / f"{preset['id']}_{d}.json"
            path.write_text(json.dumps(res, indent=1, allow_nan=False, ensure_ascii=False), encoding="utf-8")
            written.append(path)
    return written


def main() -> None:
    paths = build_artifacts()
    print(f"wrote {len(paths)} files to {ARTIFACT_DIR}")
    for p in paths:
        r = json.loads(p.read_text(encoding="utf-8"))
        ok = [pt for pt in r["points"] if pt["M1"]["applicable"]]
        ests = ", ".join(f"{pt['fraction']:.2f}:{pt['M1']['estimate']:.3f}" for pt in ok[::3])
        print(f"  {p.name}: {len(ok)}/{len(r['points'])} M1 points applicable; dose_for_p90={r['dose_for_p90']}; "
              f"M1 [{ests}]")


if __name__ == "__main__":
    main()
