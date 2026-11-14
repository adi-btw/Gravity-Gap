"""R1 Real-fire replay: run the engine on historical incident conditions.

Reads ``data/incidents.json`` (DE) and writes ``artifacts/incidents.json`` (contract: plan/contracts.md,
"Round 2 · R1 Real-fire replay addendum"). For each in-scope incident it stores the deterministic physics
(``physics.evaluate``), Monte Carlo regime fractions (``sample_physics``, seed 0, n 2000), the M1-M5
predictions through the existing honesty gate (``bounds.predict``) and the coverage status
(``coverage.coverage_for``), plus plain-language findings built only from those numbers.

Findings describe what today's data can and cannot say about the conditions. They never claim causes or
hindsight ("would have ...").

Run: ``python -m engine.incidents``
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

from engine import __version__, bounds, coverage, physics
from engine.montecarlo import sample_physics

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "incidents.json"
OUT_PATH = ROOT / "artifacts" / "incidents.json"

MC_N = 2000
MC_SEED = 0
METRIC_IDS = tuple(bounds.METRICS)  # M1..M5
OUT_OF_RANGE_REASON = "outside the model's input range"
SEA_LEVEL_PO2_PSIA = 0.2095 * physics.PSIA_PER_ATM  # ~3.1 psia, for scale in findings


# ------------------------------------------------------------------ formatting
def _num(x: float, digits: int = 2) -> str:
    """Compact human number: 3 significant figures, no trailing zeros, thousands as integers."""
    if x is None:
        return "n/a"
    x = float(x)
    if x == 0:
        return "0"
    if x == int(x) and abs(x) < 1e6:
        return f"{int(x):,}"
    if abs(x) >= 100:
        return f"{x:,.0f}"
    if abs(x) < 1:
        return f"{x:.{max(digits, 1)}g}"
    return f"{x:.2f}" if abs(x) < 10 else f"{x:.1f}"


def _pct(frac: float) -> str:
    return f"{frac * 100:.0f}%"


def _value(v) -> str:
    if isinstance(v, str):
        return v.replace("_", " ")
    if isinstance(v, (int, float)):
        return _num(v, 3)
    return str(v)


def _gravity_phrase(g: float) -> str:
    if abs(g - physics.G0) < 0.05:
        return f"At Earth gravity ({_num(g)} m/s²)"
    if g == 0:
        return "In orbit (0 g)"
    return f"At {_num(g)} m/s² ({_num(g / physics.G0)} g)"


# --------------------------------------------------------------------- engine
def _metric_entry(metric: str, inc: dict) -> dict:
    try:
        r = bounds.predict(metric, inc["g_m_s2"], inc["p_psia"], inc["o2"], inc["u_cm_s"], inc["L_mm"],
                           n=MC_N, seed=MC_SEED)
    except (ValueError, KeyError, FloatingPointError, OverflowError, ZeroDivisionError):
        return {"applicable": False, "estimate": None, "band90": None,
                "reason": OUT_OF_RANGE_REASON, "transfer_confidence": None, "crashed": True}
    return {
        "applicable": bool(r["applicable"]),
        "estimate": r.get("estimate"),
        "band90": r.get("band90"),
        "reason": r.get("reason"),
        "transfer_confidence": (r.get("transfer") or {}).get("confidence"),
    }


def _coverage_entry(metric: str, inc: dict) -> dict:
    hab = coverage.coverage_for(metric, inc["p_psia"], inc["o2"]).get("habitat") or {}
    return {"covered": bool(hab.get("covered", False)), "nearest_distance": hab.get("nearest_distance")}


def _findings(inc: dict, phys: dict, fr: dict, metrics: dict, cov: dict) -> list[str]:
    out: list[str] = []
    assumed = set(inc.get("assumed") or [])
    g, p, o2, u = inc["g_m_s2"], inc["p_psia"], inc["o2"], inc["u_cm_s"]
    flow = f"the assumed {_num(u)} cm/s ventilation" if "u_cm_s" in assumed else f"{_num(u)} cm/s ventilation"

    # Regime.
    reg = phys["regime"]
    ri_txt = "Ri infinite" if phys["ri"] is None else f"Ri {_num(phys['ri'])}"
    mc_txt = (f"Monte Carlo: {_pct(fr['forced'])} forced, {_pct(fr['mixed'])} mixed, "
              f"{_pct(fr['buoyant'])} buoyant")
    if reg == "buoyant":
        out.append(f"{_gravity_phrase(g)} with {flow} the flame is buoyancy-dominated ({ri_txt}; {mc_txt}).")
    elif reg == "forced":
        out.append(f"{_gravity_phrase(g)} with {flow} the flame is forced-flow ({ri_txt}; {mc_txt}): "
                   f"the regime ISS data covers best.")
    else:
        out.append(f"{_gravity_phrase(g)} with {flow} the flame is in the mixed regime ({ri_txt}; {mc_txt}): "
                   f"neither buoyancy nor forced flow dominates.")

    # Oxygen partial pressure, for scale.
    atm_src = ("With the assumed atmosphere (" if assumed & {"p_psia", "o2"} else "At the sourced atmosphere (")
    out.append(f"{atm_src}O2 {_num(o2 * 100, 3)}% at {_num(p)} psia) the oxygen partial pressure is "
               f"{_num(phys['p_o2_psia'])} psia (sea-level air is about {_num(SEA_LEVEL_PO2_PSIA)} psia).")

    # Evidence / honesty gate.
    applicable = [m for m in METRIC_IDS if metrics[m]["applicable"]]
    gated = [m for m in METRIC_IDS if not metrics[m]["applicable"]]
    dists = [cov[m]["nearest_distance"] for m in gated if cov[m]["nearest_distance"] is not None]
    atm = f"O2 {_num(o2 * 100, 3)}% at {_num(p)} psia"
    if not applicable:
        near = f" (nearest tested atmosphere distance {min(dists):.1f}; the evidence gate is {bounds.GATE_DISTANCE:.1f})" \
            if dists else ""
        out.append(f"{atm} is outside every tested atmosphere: no evidence for M1–M5{near}.")
    else:
        for m in applicable:
            e = metrics[m]
            label = bounds.METRICS[m]["label"]
            band = e["band90"]
            unit = " mm" if bounds.METRICS[m]["unit"] == "mm" else ""
            band_txt = (f" (90% band {_value(band[0])} to {_value(band[1])}{unit})"
                        if band and band[0] != band[1] else "")
            conf = f"; transfer confidence {e['transfer_confidence']}" if e["transfer_confidence"] else ""
            out.append(f"{m} applies here ({label}): estimate {_value(e['estimate'])}{unit}{band_txt}{conf}.")
        if gated:
            near = f" (nearest tested atmosphere distance {min(dists):.1f})" if dists else ""
            out.append(f"No evidence for {', '.join(gated)} at {atm}{near}.")
    crashed = [m for m in METRIC_IDS if metrics[m].get("crashed")]
    if crashed:
        out.append(f"{', '.join(crashed)}: {OUT_OF_RANGE_REASON}.")
    return out


def _in_scope_ready(inc: dict) -> bool:
    keys = ("g_m_s2", "p_psia", "o2", "u_cm_s", "L_mm")
    return bool(inc.get("in_scope")) and all(
        isinstance(inc.get(k), (int, float)) and not math.isnan(inc[k]) for k in keys)


def replay(inc: dict) -> dict:
    """Engine results for one incident (contract shape)."""
    rec = dict(inc)
    if not _in_scope_ready(inc):
        if inc.get("in_scope"):
            note = "Gravity, pressure, O2, flow or size is missing, so the engine was not run."
        else:
            note = inc.get("scope_note") or "Outside the tool's scope: this was not a cabin fire."
            note = f"Outside the tool's scope: {note}" if not note.lower().startswith("outside") else note
        rec.update(physics=None, regime_fractions=None, metrics=None, coverage=None, findings=[note])
        return rec

    args = (inc["g_m_s2"], inc["p_psia"], inc["o2"], inc["u_cm_s"], inc["L_mm"])
    phys = physics.evaluate(*args)
    fr = sample_physics(*args, n=MC_N, seed=MC_SEED)["regime_fractions"]
    metrics = {m: _metric_entry(m, inc) for m in METRIC_IDS}
    cov = {m: _coverage_entry(m, inc) for m in METRIC_IDS}
    findings = _findings(inc, phys, fr, metrics, cov)
    for e in metrics.values():
        e.pop("crashed", None)
    rec.update(physics=phys, regime_fractions=fr, metrics=metrics, coverage=cov, findings=findings)
    return rec


def build_incidents(path: Path | str = DATA_PATH) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return bounds.json_safe({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "engine_version": __version__,
        "incidents": [replay(inc) for inc in data["incidents"]],
    })


def main(path: Path | str = DATA_PATH, out: Path | str = OUT_PATH) -> int:
    result = build_incidents(path)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, allow_nan=False, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out} ({len(result['incidents'])} incidents)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
