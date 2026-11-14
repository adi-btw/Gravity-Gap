"""V3: SAFFIRE-II hindcast (03 §5).

For each of the 9 SAFFIRE-II samples, "predict" the normal-gravity (1 g) burn
outcome using ONLY the microgravity (ug) result plus the physics bridge, then
score the prediction against the measured 1 g columns of
``data/clean/psi_saffire_ug_vs_1g.csv``.

Bridge rule (documented in artifacts/validation_saffire.md):
    1. Run ``engine.montecarlo.sample_physics`` at g = 9.81 m/s^2, 1 atm,
       the sample's O2, the tested forced flow (20 cm/s) and a characteristic
       length L. Primary L = sample thickness (the fuel dimension that sets the
       thermal/buoyant boundary layer of a thin sheet). Sensitivity runs use
       L = 10 mm and L = sample width (50 mm).
    2. Dominant regime: forced if forced fraction >= 0.5, buoyant if buoyant
       fraction >= 0.5, otherwise mixed.
    3. forced  -> ug outcome transfers           -> predict "same".
       buoyant -> ug outcome does NOT transfer   -> predict "more_at_1g"
                  (buoyancy adds oxidizer supply/heat feedback; thin fuels burn
                  more under gravity).
       mixed   -> primary ("conservative") rule treats buoyancy as
                  non-negligible -> "more_at_1g"; the "strict" variant
                  treats mixed as transfer -> "same". Both are reported.
    4. Ceiling: if the ug sample already burned completely, it cannot burn
       more at 1 g, so "more_at_1g" becomes "same". This uses ug data only.

Actual classes from ``which_burned_more``: normal_gravity -> more_at_1g,
similar -> same, microgravity -> more_at_ug.

Baselines: naive "1 g = ug outcome always" (predict "same"), and the constant
"1 g always burns more (with the same ceiling)", which shows how much of the
bridge's score is just a constant verdict.

Run: ``python -m engine.hindcast`` -> artifacts/hindcast_saffire.json and
artifacts/validation_saffire.md.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

from engine.montecarlo import sample_physics
from engine.physics import PSIA_PER_ATM

ROOT = Path(__file__).resolve().parents[1]
SAFFIRE_CSV = ROOT / "data" / "clean" / "psi_saffire_ug_vs_1g.csv"
OUT_JSON = ROOT / "artifacts" / "hindcast_saffire.json"
OUT_MD = ROOT / "artifacts" / "validation_saffire.md"

G_EARTH = 9.81
G_MOON = 1.62
P_PSIA = PSIA_PER_ATM  # SAFFIRE-II: ~1 atm Cygnus cabin (pressure not in table)
SAMPLE_WIDTH_MM = 50.0  # "Sample Width (cm)" = 5 cm for all 9 samples in the source
L_FIXED_MM = 10.0
# Sample 2-8 thickness is "See Fig. 5" in the source (not in the table). It is the
# PMMA sample next to 2-9 (1 cm PMMA); the 10 mm fallback is flagged, not hidden.
FALLBACK_THICKNESS_MM = 10.0
N_DRAWS = 2000
CLASSES = ("same", "more_at_1g", "more_at_ug")
ACTUAL_MAP = {"similar": "same", "normal_gravity": "more_at_1g", "microgravity": "more_at_ug"}
L_CHOICES = ("thickness", "10mm", "width_50mm")


def _f(x) -> float | None:
    """JSON-safe float (NaN/inf -> None)."""
    if x is None:
        return None
    x = float(x)
    return x if math.isfinite(x) else None


def load_samples(path: Path = SAFFIRE_CSV) -> list[dict]:
    df = pd.read_csv(path)
    out = []
    for _, r in df.iterrows():
        thick = r["thickness_mm"]
        thick_known = not pd.isna(thick)
        out.append({
            "sample": str(r["sample"]),
            "material": str(r["material"]),
            "thickness_mm": _f(thick) if thick_known else None,
            "thickness_assumed": not thick_known,
            "flow_cm_s": float(r["flow_speed_cm_s"]),
            "flow_direction": str(r["flow_direction"]),
            "o2": float(r["o2_mole_fraction"]),
            "ug_burned_fraction": float(r["ug_burned_fraction"]),
            "1g_burned_fraction": float(r["1g_burned_fraction"]),
            "ug_burn_length_raw": str(r["ug_burn_length_raw"]),
            "1g_burn_length_raw": str(r["1g_burn_length_raw"]),
            "actual": ACTUAL_MAP[str(r["which_burned_more"])],
            "flagged": bool(r["needs_manual_review"]) or not thick_known,
        })
    return out


def length_mm(s: dict, choice: str) -> float:
    if choice == "thickness":
        return s["thickness_mm"] if s["thickness_mm"] is not None else FALLBACK_THICKNESS_MM
    if choice == "10mm":
        return L_FIXED_MM
    if choice == "width_50mm":
        return SAMPLE_WIDTH_MM
    raise ValueError(f"unknown L choice {choice!r}")


def dominant_regime(fr: dict) -> str:
    if fr["forced"] >= 0.5:
        return "forced"
    if fr["buoyant"] >= 0.5:
        return "buoyant"
    return "mixed"


def bridge_predict(regime: str, ug_fraction: float, variant: str = "conservative") -> str:
    """Bridge rule: regime at 1 g + ug outcome -> predicted 1 g class."""
    if regime == "forced":
        pred = "same"
    elif regime == "buoyant":
        pred = "more_at_1g"
    elif regime == "mixed":
        pred = "more_at_1g" if variant == "conservative" else "same"
    else:
        raise ValueError(regime)
    if pred == "more_at_1g" and ug_fraction >= 1.0:
        pred = "same"  # ceiling: a fully burned ug sample cannot burn more at 1 g
    return pred


def physics_at(s: dict, g: float, L: float, seed: int) -> dict:
    r = sample_physics(g, P_PSIA, s["o2"], s["flow_cm_s"], L, n=N_DRAWS, seed=seed)
    fr = {k: float(v) for k, v in r["regime_fractions"].items()}
    return {
        "g_m_s2": g,
        "L_mm": L,
        "u_b_cm_s": {k: _f(v) for k, v in r["summary"]["u_b"].items()},
        "ri": {k: _f(v) for k, v in r["summary"]["ri"].items()},
        "regime_fractions": fr,
        "dominant_regime": dominant_regime(fr),
    }


def score(preds: list[str], actual: list[str]) -> dict:
    n = len(actual)
    hits = sum(p == a for p, a in zip(preds, actual))
    # binary view: does the outcome transfer ("same") or not?
    bin_hits = sum((p == "same") == (a == "same") for p, a in zip(preds, actual))
    confusion = {a: {p: 0 for p in CLASSES} for a in CLASSES}
    for p, a in zip(preds, actual):
        confusion[a][p] += 1
    return {
        "n": n,
        "hits": hits,
        "accuracy": hits / n if n else None,
        "binary_hits": bin_hits,
        "binary_accuracy": bin_hits / n if n else None,
        "confusion_actual_by_predicted": confusion,
    }


def run(seed: int = 0) -> dict:
    samples = load_samples()
    rows = []
    for s in samples:
        row = {k: s[k] for k in ("sample", "material", "thickness_mm", "thickness_assumed",
                                 "flow_direction", "o2", "ug_burned_fraction",
                                 "1g_burned_fraction", "ug_burn_length_raw",
                                 "1g_burn_length_raw", "actual", "flagged")}
        row["earth"] = {}
        row["moon"] = {}
        row["pred"] = {}
        for choice in L_CHOICES:
            L = length_mm(s, choice)
            e = physics_at(s, G_EARTH, L, seed)
            m = physics_at(s, G_MOON, L, seed)
            row["earth"][choice] = e
            row["moon"][choice] = m
            row["pred"][choice] = {
                "conservative": bridge_predict(e["dominant_regime"], s["ug_burned_fraction"]),
                "strict": bridge_predict(e["dominant_regime"], s["ug_burned_fraction"], "strict"),
                "moon_conservative": bridge_predict(m["dominant_regime"], s["ug_burned_fraction"]),
            }
        rows.append(row)

    def subset_scores(sel):
        actual = [r["actual"] for r in sel]
        out = {
            "baseline_same_as_ug": score(["same"] * len(sel), actual),
            "baseline_always_more_at_1g_capped": score(
                [bridge_predict("buoyant", r["ug_burned_fraction"]) for r in sel], actual),
        }
        for choice in L_CHOICES:
            for variant in ("conservative", "strict"):
                out[f"bridge_{variant}_L_{choice}"] = score(
                    [r["pred"][choice][variant] for r in sel], actual)
        return out

    clean = [r for r in rows if not r["flagged"]]
    primary = subset_scores(rows)["bridge_conservative_L_thickness"]
    return {
        "artifact": "hindcast_saffire",
        "validation": "V3 SAFFIRE-II hindcast (plan/03-physics-engine.md §5)",
        "source": "data/clean/psi_saffire_ug_vs_1g.csv (PSI-99 SAFFIRE-II)",
        "seed": seed,
        "n_draws": N_DRAWS,
        "conditions": {"p_psia": P_PSIA, "flow_cm_s": 20.0, "g_earth": G_EARTH, "g_moon": G_MOON,
                       "pressure_note": "not in source table; ~1 atm assumed"},
        "L_choices_mm": {"thickness": "sample thickness (primary)", "10mm": L_FIXED_MM,
                         "width_50mm": SAMPLE_WIDTH_MM},
        "fallback_thickness_mm": FALLBACK_THICKNESS_MM,
        "bridge_rule": [
            "dominant regime at 1 g: forced if forced fraction >= 0.5, buoyant if buoyant >= 0.5, else mixed",
            "forced -> ug outcome transfers (predict same)",
            "buoyant -> ug outcome does not transfer (predict more burn at 1 g)",
            "mixed -> conservative: more burn at 1 g; strict: same",
            "ceiling: if ug burned completely, 'more at 1 g' becomes 'same'",
        ],
        "classes": list(CLASSES),
        "samples": rows,
        "scores_all": subset_scores(rows),
        "scores_unflagged": subset_scores(clean),
        "unflagged_samples": [r["sample"] for r in clean],
        "headline": {
            "primary": "bridge_conservative_L_thickness",
            "accuracy": primary["accuracy"],
            "hits": primary["hits"],
            "n": primary["n"],
            "baseline_accuracy": subset_scores(rows)["baseline_same_as_ug"]["accuracy"],
        },
    }


# --------------------------------------------------------------------------- report

def _pct(x):
    return "n/a" if x is None else f"{100 * x:.0f}%"


def _num(x, nd=2):
    return "n/a" if x is None else f"{x:.{nd}g}" if abs(x) < 1e-2 else f"{x:.{nd}f}"


def _score_table(sc: dict) -> list[str]:
    names = [("baseline_same_as_ug", "Baseline: 1 g = ug outcome"),
             ("baseline_always_more_at_1g_capped", "Constant: 1 g burns more (capped)")]
    for choice in L_CHOICES:
        for variant in ("conservative", "strict"):
            names.append((f"bridge_{variant}_L_{choice}", f"Bridge ({variant}), L = {choice}"))
    lines = ["| Predictor | Hits | Accuracy (3-class) | Accuracy (transfer yes/no) |",
             "|---|---|---|---|"]
    for key, label in names:
        s = sc[key]
        lines.append(f"| {label} | {s['hits']}/{s['n']} | {_pct(s['accuracy'])} | "
                     f"{s['binary_hits']}/{s['n']} ({_pct(s['binary_accuracy'])}) |")
    return lines


def _confusion(s: dict) -> list[str]:
    lines = ["| actual \\ predicted | " + " | ".join(CLASSES) + " |",
             "|---|" + "---|" * len(CLASSES)]
    for a in CLASSES:
        lines.append(f"| {a} | " + " | ".join(str(s["confusion_actual_by_predicted"][a][p])
                                               for p in CLASSES) + " |")
    return lines


def render_markdown(res: dict) -> str:
    sa, su = res["scores_all"], res["scores_unflagged"]
    prim = sa["bridge_conservative_L_thickness"]
    base = sa["baseline_same_as_ug"]
    const = sa["baseline_always_more_at_1g_capped"]
    regimes_t = sorted({r["earth"]["thickness"]["dominant_regime"] for r in res["samples"]})
    L = []
    L.append("# V3 SAFFIRE-II hindcast (microgravity -> 1 g)")
    L.append("")
    L.append("Generated by `python -m engine.hindcast` (seed "
             f"{res['seed']}, {res['n_draws']} Monte Carlo draws). Data: `{res['source']}`. "
             "Machine-readable results: `artifacts/hindcast_saffire.json`.")
    L.append("")
    L.append("## Plain-language summary")
    L.append("")
    L.append("SAFFIRE-II burned 9 material samples in orbit (on Cygnus) and the same materials on the "
             "ground, all at about 22% O2 and a 20 cm/s airflow. We asked: knowing only the orbit "
             "result, can the physics bridge tell whether the ground (1 g) result would be the same "
             "or different?")
    L.append("")
    L.append(f"- **Bridge (primary, L = sample thickness): {prim['hits']}/{prim['n']} correct "
             f"({_pct(prim['accuracy'])}).** Naive baseline \"1 g = orbit outcome\": "
             f"{base['hits']}/{base['n']} ({_pct(base['accuracy'])}).")
    L.append(f"- **Caveat that matters:** with L = thickness every sample lands in the same 1 g regime "
             f"({', '.join(regimes_t)}), so the bridge gives the same verdict (\"buoyancy matters, expect "
             f"more burning at 1 g\") for all 9. Its score equals a constant guess \"1 g burns more, "
             f"unless the orbit sample already burned fully\" ({const['hits']}/{const['n']}). The bridge "
             "gets the direction right for these samples, but this test cannot show that it tells "
             "samples apart.")
    strict = sa["bridge_strict_L_thickness"]
    L.append(f"- The score depends on how the **mixed** regime is read. If mixed counts as \"transfers\" "
             f"(strict variant), the bridge falls to the baseline: {strict['hits']}/{strict['n']}. "
             "With L = sample width (50 mm) every sample is buoyant-dominated and both variants give "
             f"{sa['bridge_strict_L_width_50mm']['hits']}/{sa['bridge_strict_L_width_50mm']['n']}.")
    L.append("- The bridge's main point holds: at 1 g with 20 cm/s flow, buoyancy is **not** negligible "
             "(Ri is around 0.1 to 10 for thin sheets and above 10 at the 50 mm sample width), so orbit "
             "results should not be copied to Earth. The data agree: only 3 of 9 samples behaved the same.")
    L.append("- Misses: 2-3 (1.03 mm silicone, did not burn either way) and 2-7 (PMMA+Nomex, burned "
             "more in orbit). The bridge cannot predict extinction limits or mixed-material effects.")
    L.append("- At lunar gravity (1.62 m/s2) the thinnest samples move toward forced-flow, so the bridge "
             "would let the orbit result transfer for them on the Moon. That is a prediction with no "
             "test to check it against.")
    L.append("")
    L.append("## Bridge rule")
    L.append("")
    for b in res["bridge_rule"]:
        L.append(f"- {b}")
    L.append("- Characteristic length: **sample thickness** is the primary L (it sets the thermal "
             "boundary layer of a thin sheet). Sensitivity: L = 10 mm and L = sample width (50 mm). "
             f"Sample 2-8 has no thickness in the source (\"See Fig. 5\"); it uses a flagged "
             f"{res['fallback_thickness_mm']:g} mm fallback (as for the 1 cm PMMA sample 2-9).")
    L.append("- Conditions: g = 9.81 (Earth) and 1.62 (Moon) m/s2, ~1 atm (not in the table), "
             "20 cm/s forced flow, sample O2.")
    L.append("- Classes: `same`, `more_at_1g`, `more_at_ug` (from `which_burned_more`). "
             "\"Transfer yes/no\" scoring only asks whether the outcome changed, not the direction.")
    L.append("")
    L.append("## Scores, all 9 samples")
    L.append("")
    L.extend(_score_table(sa))
    L.append("")
    L.append("Confusion table, primary bridge (conservative, L = thickness):")
    L.append("")
    L.extend(_confusion(prim))
    L.append("")
    L.append("Confusion table, naive baseline:")
    L.append("")
    L.extend(_confusion(base))
    L.append("")
    L.append(f"## Scores, unflagged samples only ({', '.join(res['unflagged_samples'])})")
    L.append("")
    L.append("Excluded: 2-7 (PMMA & Nomex mixed sample), 2-8 (thickness not in table, damage-length "
             "footnote), 2-9 (footnoted burn length).")
    L.append("")
    L.extend(_score_table(su))
    L.append("")
    L.append("## Per-sample results")
    L.append("")
    L.append("Primary L = thickness. u_b and Ri are Monte Carlo medians (p05 to p95 in the JSON). "
             "Regime fractions are forced / mixed / buoyant.")
    L.append("")
    L.append("| Sample | Material | t (mm) | ug -> 1 g burned | Actual | u_b 1 g (cm/s) | Ri 1 g | "
             "Regime 1 g (F/M/B) | Prediction | Hit | Ri Moon | Regime Moon (F/M/B) | Moon verdict |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in res["samples"]:
        e, m = r["earth"]["thickness"], r["moon"]["thickness"]
        pred = r["pred"]["thickness"]["conservative"]
        fe, fm = e["regime_fractions"], m["regime_fractions"]
        t = "n/a (10 assumed)" if r["thickness_assumed"] else f"{r['thickness_mm']:g}"
        flag = " *" if r["flagged"] else ""
        moon_v = "transfers" if m["dominant_regime"] == "forced" else "does not transfer"
        L.append(
            f"| {r['sample']}{flag} | {r['material']} | {t} | "
            f"{_pct(r['ug_burned_fraction'])} -> {_pct(r['1g_burned_fraction'])} | {r['actual']} | "
            f"{_num(e['u_b_cm_s']['p50'], 3)} | {_num(e['ri']['p50'], 3)} | "
            f"{fe['forced']:.2f}/{fe['mixed']:.2f}/{fe['buoyant']:.2f} | {pred} | "
            f"{'yes' if pred == r['actual'] else 'no'} | {_num(m['ri']['p50'], 3)} | "
            f"{fm['forced']:.2f}/{fm['mixed']:.2f}/{fm['buoyant']:.2f} | {moon_v} |")
    L.append("")
    L.append("`*` = flagged (mixed material, footnote or missing thickness).")
    L.append("")
    L.append("### Sensitivity to L (dominant 1 g regime and prediction, conservative rule)")
    L.append("")
    L.append("| Sample | L = thickness | L = 10 mm | L = 50 mm (width) | Actual |")
    L.append("|---|---|---|---|---|")
    for r in res["samples"]:
        cells = [f"{r['earth'][c]['dominant_regime']} -> {r['pred'][c]['conservative']}"
                 for c in L_CHOICES]
        L.append(f"| {r['sample']} | " + " | ".join(cells) + f" | {r['actual']} |")
    L.append("")
    L.append("## Limitations")
    L.append("")
    L.append("- **n = 9** (6 unflagged). One hit more or less moves accuracy by 11 points. "
             "No result here is statistically significant.")
    L.append("- **No discrimination.** The 1 g regime is the same for every sample at a given L, "
             "because all samples share the same flow and similar thickness. The test checks the "
             "direction of the gravity effect, not the bridge's ability to rank materials.")
    L.append("- The ceiling rule (a fully burned orbit sample cannot burn more) carries part of the score "
             "(2-5, 2-6). It uses only orbit data, but it is logic, not physics.")
    L.append("- The bridge has no extinction or flammability-limit physics: it cannot say that 1.03 mm "
             "silicone (2-3) stays non-flammable at 1 g while 0.61 mm (2-2) partly burns.")
    L.append("- Mixed-material sample 2-7 (PMMA burned out, Nomex never ignited) is outside the model.")
    L.append("- Pressure is not in the SAFFIRE-II table; ~1 atm is assumed. O2 is derived from CO2 "
             "production (source note 1).")
    L.append("- Ground tests may differ from orbit tests in igniter, chamber and sample holder, "
             "not only gravity.")
    L.append("- The Moon column is a prediction only. No partial-gravity SAFFIRE data exist.")
    L.append("")
    return "\n".join(L)


def write_outputs(res: dict, json_path: Path = OUT_JSON, md_path: Path = OUT_MD) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(res, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(res), encoding="utf-8")


def main() -> None:
    res = run(seed=0)
    write_outputs(res)
    h = res["headline"]
    print(f"V3 SAFFIRE hindcast: bridge {h['hits']}/{h['n']} ({h['accuracy']:.0%}), "
          f"baseline {h['baseline_accuracy']:.0%}")
    for key, s in res["scores_all"].items():
        print(f"  {key:45s} {s['hits']}/{s['n']}  binary {s['binary_hits']}/{s['n']}")
    print(f"wrote {OUT_JSON.relative_to(ROOT)} and {OUT_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
