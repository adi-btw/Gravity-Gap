"""S1 habitat fire-safety briefing: one JSON that composes existing engine outputs (ADR-0010).

Contract: plan/contracts.md "Round 3 · S1 Briefing addendum". Plan: plan/15-round-3-features.md §S1.

``briefing(habitat)`` takes a preset id or habitat fields (+ optional ``label``) and returns, in page order:
habitat line, verdict strip (one chip per pillar, rules in ``PILLAR_RULES``), key numbers, uncertainty levers,
known gaps, recommended next tests, history check, trust line and footer. There is no new modelling: every
number is copied from ``engine.bounds.predict``, ``engine.coverage.coverage_for``, ``engine.uncertainty.drivers``,
``engine.suppression.curve`` or a built artifact (planner, incidents, detection, holdout, MANIFEST). Each item
carries citation ids (``eng:...``, ``PSI-xx``) and the top-level ``citations`` lists them all.

Deterministic for a given habitat and artifact set, except ``footer.generated_at`` / ``footer.date``.

Run ``python -m engine.briefing`` to write artifacts/briefing/{preset}.json for the six presets.
"""

from __future__ import annotations

import json
import math
import time
from datetime import UTC, datetime
from pathlib import Path

from engine import __version__, bounds, coverage, physics, suppression, uncertainty
from engine.compare import HABITAT_FIELDS, fmt, fmt_value, resolve
from engine.planner import _kernel
from engine.presets import PRESETS, PRESETS_BY_ID

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "artifacts"
OUT_DIR = ARTIFACTS / "briefing"
PLANNER_PATH = ARTIFACTS / "planner.json"
INCIDENTS_PATH = ARTIFACTS / "incidents.json"
DETECTION_PATH = ARTIFACTS / "detection.json"
HOLDOUT_PATH = ARTIFACTS / "holdout.json"
MANIFEST_PATH = ARTIFACTS / "MANIFEST.json"

METRIC_IDS = tuple(bounds.METRICS)  # M1..M5
INVESTIGATION = {"M1": "PSI-69", "M2": "PSI-69", "M3": "PSI-159", "M4": "PSI-99", "M5": "PSI-107"}
SHORT = {
    "M1": "droplet flame self-extinction",
    "M2": "droplet extinction diameter",
    "M3": "gas flame self-extinction",
    "M4": "SAFFIRE solid-material burn extent",
    "M5": "SPICE coflow flame window",
}
DETECTION_GAPS = ("lunar_dust", "detector_sensitivity")
HISTORY_MAX_DISTANCE = bounds.GATE_DISTANCE  # same reach as the honesty gate
PLANNER_CLOSE = 2.0  # planner-kernel distance; same as engine.uncertainty.PLANNER_MAX_DISTANCE
N_NEXT_TESTS = 3
DISCLAIMER = ("Not an operating procedure. This briefing summarises what NASA's PSI test data can and cannot say "
              "about fires in this habitat; it is not a design certification or crew guidance.")

PILLARS = {
    "prevention": {"label": "Prevention", "metrics": ("M3", "M4")},
    "behaviour": {"label": "Flame behaviour", "metrics": ("M1", "M2", "M5")},
    "detection": {"label": "Detection", "metrics": ()},
    "suppression": {"label": "Suppression", "metrics": ()},
}
PILLAR_RULES = {
    "prevention": ("evidence if M3 (gas flames) and M4 (SAFFIRE solids) are both covered at this habitat; partial "
                   "if exactly one is; no evidence if neither is."),
    "behaviour": ("evidence if M1, M2 and M5 are all covered at this habitat; partial if one or two are; "
                  "no evidence if none is."),
    "detection": ("always partial: smoke sizes were measured (SAME-R) and a simulation compares Earth gravity with "
                  "microgravity (PSI-115), but there are no lunar dust data and no cited detector size "
                  "sensitivity, and none of this evidence depends on the habitat's pressure or O2 (ADR-0007)."),
    "suppression": ("evidence if the R2 dilution curves have covered points (fraction > 0, M1 applicable) for both "
                    "CO2 and helium; partial if for one of them; no evidence if for neither."),
}
VALUES = ("evidence", "partial", "no evidence")


# ------------------------------------------------------------------ helpers
def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _pct(x: float) -> str:
    return f"{fmt(100 * float(x))}%"


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _count_rule(covered: list[bool]) -> str:
    if all(covered):
        return "evidence"
    return "partial" if any(covered) else "no evidence"


def _value_text(pred: dict, x) -> str:
    return fmt_value(pred.get("kind"), pred.get("unit"), x)


# ------------------------------------------------------------------ sections
def _habitat_section(h: dict, raw) -> dict:
    pid = h["preset_id"]
    if pid in PRESETS_BY_ID:
        p = PRESETS_BY_ID[pid]
        assumed, source = list(p["assumed"]), p["source"]
    else:
        given = raw if isinstance(raw, dict) else {}
        assumed = list(given.get("assumed") or ([] if given.get("L_mm") is not None else ["L_mm"]))
        source = "custom habitat: values as entered"
    parts = []
    for k, name in (("g_m_s2", "gravity"), ("p_psia", "pressure"), ("o2", "O₂"), ("u_cm_s", "vent speed"),
                    ("L_mm", "flame size")):
        unit = {"g_m_s2": " m/s²", "p_psia": " psia", "o2": "", "u_cm_s": " cm/s", "L_mm": " mm"}[k]
        val = _pct(h[k]) if k == "o2" else f"{fmt(h[k])}{unit}"
        parts.append(f"{name} {val}" + (" (assumed)" if k in assumed else ""))
    return {**h, "assumed": assumed, "source": source, "line": f"{h['label']}: " + ", ".join(parts) + "."}


def _pillar_chip(pillar: str, value: str, because: str, citations: list[str], metrics: dict | None = None) -> dict:
    assert value in VALUES
    return {"pillar": pillar, "label": PILLARS[pillar]["label"], "value": value, "rule": PILLAR_RULES[pillar],
            "because": because, "metrics": metrics or {}, "citations": citations}


def _metric_chip(pillar: str, preds: dict) -> dict:
    ms = PILLARS[pillar]["metrics"]
    cov = {m: bool(preds[m]["applicable"]) for m in ms}
    value = _count_rule(list(cov.values()))
    yes = [f"{m} ({SHORT[m]})" for m in ms if cov[m]]
    no = [f"{m} ({SHORT[m]})" for m in ms if not cov[m]]
    bits = []
    if yes:
        bits.append(f"{_join(yes)} {'is' if len(yes) == 1 else 'are'} covered at this habitat")
    if no:
        bits.append(f"{_join(no)} {'has' if len(no) == 1 else 'have'} no evidence here")
    because = "; ".join(bits) + "."
    low = [m for m in ms if cov[m] and (preds[m].get("transfer") or {}).get("confidence") == "low"]
    if low:
        because += (f" Transfer confidence is low for {_join(low)} (the engine's own rating of how well the tests "
                    f"carry over to this habitat; see each metric's transfer note).")
    cites = [f"eng:{m}" for m in ms] + sorted({INVESTIGATION[m] for m in ms})
    return _pillar_chip(pillar, value, because, cites, cov)


def _detection_chip(h: dict) -> dict:
    g = h["g_m_s2"]
    because = ("Smoke particle sizes from heated spacecraft materials were measured (SAME-R, PSI-101) and one "
               "smoke-versus-dust size comparison exists (Arizona Road Dust, DAFT, PSI-47), but there are no lunar "
               "dust data and no cited source for which particle sizes detectors respond to. This evidence does "
               "not depend on the habitat's pressure or O₂. Only the PSI-115 simulation is about gravity")
    if g == 0:
        because += ", and its microgravity case matches this habitat."
    elif abs(g - physics.G0) < 0.05:
        because += ", and its Earth-gravity case matches this habitat."
    else:
        because += (f", and it covers only Earth gravity and microgravity; {fmt(g)} m/s² lies between them and "
                    f"was not simulated.")
    return _pillar_chip("detection", "partial", because,
                        ["eng:detection", "eng:detection:lunar_dust", "eng:detection:detector_sensitivity",
                         "PSI-101", "PSI-47", "PSI-115"])


def _suppression(h: dict, n: int, seed: int) -> dict:
    curves = {d: suppression.curve(d, *(h[k] for k in HABITAT_FIELDS), n=n, seed=seed)
              for d in suppression.DILUENTS}
    summary = {}
    for d, c in curves.items():
        diluted = [p for p in c["points"] if p["fraction"] > 0 and p["n2"] >= 0]
        ok = [p for p in diluted if p["M1"]["applicable"]]
        summary[d] = {"covered_points": len(ok), "diluted_points": len(diluted),
                      "max_covered_fraction": max((p["fraction"] for p in ok), default=None),
                      "gate_note": c["gate_note"], "safety_note": c["safety_note"]}
    with_ev = [d for d in curves if summary[d]["covered_points"] > 0]
    value = "evidence" if len(with_ev) == len(curves) else ("partial" if with_ev else "no evidence")
    names = {"co2": "CO₂", "he": "helium"}
    if with_ev:
        bits = [f"{names[d]} up to {_pct(summary[d]['max_covered_fraction'])} "
                f"({summary[d]['covered_points']} of {summary[d]['diluted_points']} diluted points)" for d in with_ev]
        because = (f"FLEX dilution tests cover this atmosphere for {_join(bits)}; these show how dilution changed "
                   f"droplet flames in tests, not how an extinguisher performs.")
        missing = [names[d] for d in curves if d not in with_ev]
        if missing:
            because += f" No {_join(missing)} point has evidence here."
    else:
        because = ("No CO₂ or helium dilution point has evidence at this atmosphere: FLEX tested dilution only at "
                   "lower O₂ levels.")
    chip = _pillar_chip("suppression", value, because,
                        ["eng:suppression:co2", "eng:suppression:he", "PSI-69"],
                        {d: summary[d]["covered_points"] > 0 for d in curves})
    return {"chip": chip, "summary": summary}


def _key_numbers(preds: dict) -> list[dict]:
    out = []
    for m in METRIC_IDS:
        p = preds[m]
        if not p["applicable"]:
            continue
        est, band = p["estimate"], p["band90"]
        conf = (p.get("transfer") or {}).get("confidence")
        txt = f"{m} {p['label']}: {_value_text(p, est)}"
        if band and band[0] != band[1]:
            txt += f" (90% band {_value_text(p, band[0])} to {_value_text(p, band[1])})"
        txt += f"; transfer confidence {conf}." if conf else "."
        out.append({"metric": m, "label": p["label"], "unit": p["unit"], "kind": p["kind"], "estimate": est,
                    "band90": band, "transfer_confidence": conf, "n_train": p.get("n_train"), "text": txt,
                    "citations": [f"eng:{m}", INVESTIGATION[m]]})
    return out


def _drivers(h: dict, preds: dict, n: int, seed: int) -> list[dict]:
    out = []
    for m in bounds.FITTED:
        if not preds[m]["applicable"]:
            continue
        d = uncertainty.drivers(m, *(h[k] for k in HABITAT_FIELDS), n=n, seed=seed)
        if not d.get("applicable"):
            continue
        lev = d["lever"]
        cites = [d["citation"]]
        if lev.get("planner_candidate"):
            cites.append(f"eng:planner:{lev['planner_candidate']['rank']}")
        out.append({"metric": m, "source": lev["source"], "share": lev["share"], "basis": lev["basis"],
                    "text": lev["text"], "planner_candidate": lev.get("planner_candidate"), "citations": cites})
    return out


def _metric_gaps(h: dict, preds: dict) -> list[dict]:
    out = []
    for m in METRIC_IDS:
        p = preds[m]
        if p["applicable"]:
            continue
        cov = coverage.coverage_for(m, h["p_psia"], h["o2"])
        st = cov.get("habitat") or {}
        near = st.get("nearest_point")
        dist = st.get("nearest_distance")
        if m in bounds.FITTED and p.get("evidence"):
            dist = round(p["evidence"][0]["distance"], 4)  # the gate's own distance (unrounded test points)
        nearest = None
        txt = f"{m} {p['label']}: no evidence at this habitat."
        if near:
            p_psia = near["p_atm"] * physics.PSIA_PER_ATM
            nearest = {"o2": near["o2"], "p_atm": near["p_atm"], "p_psia": round(p_psia, 2),
                       "investigation_id": near["investigation_id"], "n": near["n"], "assumed": near.get("assumed")}
            for k in ("co2", "he"):
                if k in near:
                    nearest[k] = near[k]
            txt += (f" Nearest tested atmosphere: {_pct(near['o2'])} O₂ at {fmt(p_psia)} psia "
                    f"({near['investigation_id']}, {near['n']} tests), atmosphere distance {fmt(dist)}.")
            if near.get("assumed"):
                txt += f" That point is partly assumed: {near['assumed']}."
        txt += f" Rule: {cov['rule']['text']}"
        out.append({"kind": "metric", "id": m, "metric": m, "label": p["label"], "reason": p["reason"],
                    "nearest_distance": dist, "nearest_point": nearest, "rule_type": cov["rule"]["type"],
                    "text": txt, "citations": [f"eng:{m}", INVESTIGATION[m]]})
    return out


def _detection_gaps(det: dict | None) -> list[dict]:
    gaps = {g["id"]: g for g in (det or {}).get("gaps") or []}
    out = []
    for gid in DETECTION_GAPS:
        if gid in gaps:
            out.append({"kind": "detection", "id": gid, "text": gaps[gid]["text"],
                        "citations": [f"eng:detection:{gid}"]})
    return out


def _suppression_gaps(sup: dict) -> list[dict]:
    return [{"kind": "suppression", "id": f"suppression_{d}", "diluent": d, "text": s["gate_note"],
             "safety_note": s["safety_note"], "citations": [f"eng:suppression:{d}", "PSI-69"]}
            for d, s in sup.items()]


def _next_tests(h: dict, planner: dict | None) -> dict:
    rule = ("Relevance = the planner's own score x its re-scoring kernel between this habitat and the candidate "
            "(atmosphere distance, gravity scale 2 m/s², vent scale 10 cm/s), in place of its three fixed target "
            "weights. A dilution candidate is a test at that cabin atmosphere with CO₂ added, so the CO₂ term is "
            "left out. Top 3 of the planner's ranked list.")
    items = (planner or {}).get("items") or []
    if not items:
        return {"rule": rule, "items": [], "note": "The planner artifact is not built, so no tests are listed.",
                "citations": []}
    hab = {k: h[k] for k in ("g_m_s2", "p_psia", "o2", "u_cm_s")}
    scored = []
    for it in items:
        k = _kernel({**hab, "co2": it.get("co2", 0.0)}, it)
        dist = math.sqrt(max(-2.0 * math.log(max(k, 1e-300)), 0.0))
        scored.append((-(it["score"] * k), it["rank"], it, k, dist))
    scored.sort(key=lambda t: (t[0], t[1]))
    out = []
    for _, _, it, k, dist in scored[:N_NEXT_TESTS]:
        keys = ("rank", "metric", "type", "g_m_s2", "p_psia", "o2", "u_cm_s", "co2", "score", "rationale", "extends")
        out.append({**{key: it.get(key) for key in keys}, "kernel": round(k, 4) + 0.0,
                    "distance": round(dist, 4) + 0.0, "close": dist <= PLANNER_CLOSE,
                    "citations": [f"eng:planner:{it['rank']}"]})
    note = None
    if not any(o["close"] for o in out):
        note = (f"None of the planner's {len(items)} candidates is close to this habitat (kernel distance over "
                f"{fmt(PLANNER_CLOSE)}); these are the closest. The planner targets lunar, Mars, exploration and "
                f"ISS atmospheres in partial gravity.")
    return {"rule": rule, "items": out, "note": note, "citations": [c for o in out for c in o["citations"]]}


def _history(h: dict, inc_doc: dict | None) -> dict:
    p_atm = h["p_psia"] / physics.PSIA_PER_ATM
    rows = []
    for inc in (inc_doc or {}).get("incidents") or []:
        if not inc.get("in_scope") or not all(isinstance(inc.get(k), (int, float)) for k in ("o2", "p_psia")):
            continue
        d = physics.atmosphere_distance(h["o2"], p_atm, inc["o2"], inc["p_psia"] / physics.PSIA_PER_ATM)
        assumed = [k for k in ("p_psia", "o2") if k in (inc.get("assumed") or [])]
        rows.append({"id": inc["id"], "name": inc["name"], "date": inc.get("date"), "o2": inc["o2"],
                     "p_psia": inc["p_psia"], "g_m_s2": inc.get("g_m_s2"), "atmosphere_assumed": bool(assumed),
                     "distance": round(d, 4) + 0.0, "citations": [f"eng:incident:{inc['id']}"]})
    rows.sort(key=lambda r: (r["distance"], r["id"]))
    close = [r for r in rows if r["distance"] <= HISTORY_MAX_DISTANCE]
    base = {"max_distance": HISTORY_MAX_DISTANCE, "incidents_checked": len(rows),
            "rule": (f"Closest R1 incident atmosphere by atmosphere distance (O₂ and pressure); shown only within "
                     f"distance {fmt(HISTORY_MAX_DISTANCE)}, the same reach as the honesty gate.")}
    if not close:
        near = rows[0] if rows else None
        txt = "No replayed incident atmosphere is close to this habitat"
        if near:
            txt += (f" (the closest, {near['name']}, is {_pct(near['o2'])} O₂ at {fmt(near['p_psia'])} psia, "
                    f"distance {fmt(near['distance'])})")
        return {**base, "status": "none_close", "nearest": near, "close": [], "text": txt + ".",
                "citations": near["citations"] if near else []}
    first = close[0]
    same = [r for r in close if r["distance"] == first["distance"]]
    names = _join([f"{r['name']} ({r['date'][:4]})" if r.get("date") else r["name"] for r in same])
    how = "the same atmosphere as" if first["distance"] == 0 else f"atmosphere distance {fmt(first['distance'])} from"
    txt = (f"{names} happened at {_pct(first['o2'])} O₂ and {fmt(first['p_psia'])} psia, {how} this habitat")
    if any(r["atmosphere_assumed"] for r in same):
        txt += " (the incident's atmosphere is an assumed value, not a recorded one)"
    gs = sorted({r["g_m_s2"] for r in same if r.get("g_m_s2") is not None})
    if gs:
        g_txt = _join([f"{fmt(g)} m/s²" for g in gs])
        txt += (f". Gravity there was {g_txt}" + (" as here" if gs == [h["g_m_s2"]] else
                                                  f", here it is {fmt(h['g_m_s2'])} m/s²"))
    txt += ". The replay shows what today's data say about those conditions; it does not judge what happened."
    return {**base, "status": "close", "nearest": first, "close": close, "text": txt,
            "citations": [c for r in same for c in r["citations"]]}


def _trust(preds: dict, hold: dict | None) -> dict:
    if not hold:
        return {"text": "The honesty test artifact is not built.", "metrics": {}, "citations": []}
    covered = [m for m in bounds.FITTED if preds[m]["applicable"]]
    per = {}
    for m in covered:
        s = hold["metrics"][m]["summary"]
        w = hold["wide_check"]["metrics"][m]["summary"]
        per[m] = {"band_held": s["band_coverage"]["k"], "n_groups": s["band_coverage"]["n"],
                  "interval90": s["band_coverage"]["interval90"],
                  "strict_held": s["strict_coverage"]["k"], "strict_n": s["strict_coverage"]["n"],
                  "weak_test": s["weak_test"], "wide_check_band_held": w["band_coverage"]["k"],
                  "wide_check_n": w["band_coverage"]["n"], "wide_check_weak_test": w["weak_test"]}
    cites = ["eng:holdout"]
    if not covered:
        txt = ("No fitted metric (M1-M3) has evidence here, so the honesty test (ADR-0009) has no numbers of this "
               "habitat to check.")
    else:
        held = _join([f"{per[m]['band_held']} of {per[m]['n_groups']} {m} atmospheres" for m in covered])
        txt = (f"Honesty test (ADR-0009): hiding one tested atmosphere at a time and refitting, the 90% band held "
               f"for {held} under the overlap rule, which is lenient for groups of 1-3 tests.")
        strict = [m for m in covered if hold["metrics"][m]["kind"] == "probability"]
        if strict:
            txt += (" Under the strict rule (observed share inside the band) it held for "
                    + _join([f"{per[m]['strict_held']} of {per[m]['strict_n']} ({m})" for m in strict]) + ".")
        weak = [m for m in covered if per[m]["weak_test"]]
        if weak:
            txt += f" Weak test for {_join(weak)}: fewer than 10 covered groups."
        wide_weak = [m for m in covered if per[m]["wide_check_weak_test"] and m not in weak]
        if wide_weak:
            txt += (" In the wide check (a whole 0.10 O₂ band hidden at once) "
                    + _join([f"{m} had only {per[m]['wide_check_n']} covered groups" for m in wide_weak])
                    + ", a weak test.")
        txt += (" The test ran in microgravity (0 g), so the gravity widening of partial-gravity bands is not "
                "tested by it.")
    if preds["M4"]["applicable"]:
        sh = hold.get("saffire_hindcast") or {}
        if sh.get("available"):
            hd = sh["headline"]
            txt += (f" M4: the SAFFIRE hindcast scored {hd['hits']} of {hd['n']}, the same as a constant rule, so "
                    f"it is not discriminative.")
            cites.append("eng:holdout:saffire")
    return {"text": txt, "metrics": per, "citations": cites}


def _footer(preds: dict, manifest: dict | None, stamp: str) -> dict:
    return {
        "model_versions": {m: preds[m].get("model_version") for m in METRIC_IDS},
        "engine_version": __version__,
        "manifest": {"artifact_set_sha256": (manifest or {}).get("artifact_set_sha256"),
                     "generated_at": (manifest or {}).get("generated_at"),
                     "note": ("Hash of the artifact set this briefing was built with; it changes at the next "
                              "manifest rebuild.")},
        "generated_at": stamp,
        "date": stamp[:10],
        "disclaimer": DISCLAIMER,
    }


# ------------------------------------------------------------------ main entry
def briefing(habitat: str | dict, n: int = 2000, seed: int = 0, generated_at: str | None = None) -> dict:
    """Fire-safety briefing for a preset id or habitat dict (contract shape, JSON-safe)."""
    h = resolve(habitat)
    preds = {m: bounds.predict(m, *(h[k] for k in HABITAT_FIELDS), n=n, seed=seed) for m in METRIC_IDS}
    det, hold = _read_json(DETECTION_PATH), _read_json(HOLDOUT_PATH)
    sup = _suppression(h, n, seed)
    verdicts = [_metric_chip("prevention", preds), _metric_chip("behaviour", preds), _detection_chip(h), sup["chip"]]
    stamp = generated_at or datetime.now(UTC).isoformat(timespec="seconds")
    doc = {
        "artifact": "briefing",
        "adr": "ADR-0010",
        "citation": "eng:briefing",
        "habitat": _habitat_section(h, habitat),
        "verdicts": verdicts,
        "key_numbers": _key_numbers(preds),
        "drivers": _drivers(h, preds, n, seed),
        "gaps": _metric_gaps(h, preds) + _detection_gaps(det) + _suppression_gaps(sup["summary"]),
        "next_tests": _next_tests(h, _read_json(PLANNER_PATH)),
        "history": _history(h, _read_json(INCIDENTS_PATH)),
        "trust": _trust(preds, hold),
        "footer": _footer(preds, _read_json(MANIFEST_PATH), stamp),
    }
    cites = ["eng:briefing"]
    for sec in ("verdicts", "key_numbers", "drivers", "gaps"):
        for it in doc[sec]:
            cites.extend(it["citations"])
    for sec in ("next_tests", "history", "trust"):
        cites.extend(doc[sec]["citations"])
    doc["citations"] = sorted(set(cites))
    return bounds.json_safe(doc)


def build_artifacts(out_dir: Path = OUT_DIR) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    written = []
    for p in PRESETS:
        doc = {"preset_id": p["id"], **briefing(p["id"], generated_at=stamp)}
        path = out_dir / f"{p['id']}.json"
        path.write_text(json.dumps(doc, indent=1, allow_nan=False, ensure_ascii=False), encoding="utf-8")
        written.append(path)
    return written


def main() -> None:
    t0 = time.perf_counter()
    paths = build_artifacts()
    print(f"wrote {len(paths)} files to {OUT_DIR} in {time.perf_counter() - t0:.1f} s")
    for path in paths:
        d = json.loads(path.read_text(encoding="utf-8"))
        chips = ", ".join(f"{v['label']}={v['value']}" for v in d["verdicts"])
        gaps = [g["id"] for g in d["gaps"]]
        print(f"  {d['preset_id']}: {chips}; numbers {[k['metric'] for k in d['key_numbers']]}; gaps {gaps}; "
              f"next {[t['rank'] for t in d['next_tests']['items']]}; history {d['history']['status']}")


if __name__ == "__main__":
    main()
