"""Grounded Q&A for Gravity Gap (plan/05-ai-layer.md, contracts.md "AI layer").

    ask(question, habitat=None, context_ids=()) ->
        {answer_markdown, citations[], numbers_used[], validated, mode, intent, habitat, validation}

Modes, in order of preference:

* ``claude``   only when ``ANTHROPIC_API_KEY`` is set **and** ``import anthropic`` works. Model from env
  ``GRAVITY_GAP_MODEL`` (default ``claude-sonnet-5-5``); the static system prompt is sent with
  ``cache_control`` (prompt caching). The answer is validated; on failure one retry with the errors, then
  the template answer.
* ``cached``   a pre-generated answer from ``artifacts/ai_cache.json`` whose fingerprint (question,
  habitat, artifact + engine source hashes) still matches.
* ``template`` a deterministic answer assembled from engine outputs in the context pack.

Intents: incident (R1), refusal, suppression (R2: CO2 / helium dilution, answered only from
``engine.suppression.curve`` and ``artifacts/suppression_reference.json`` in the pack, always with
``SAFETY_NOTE``), fans_off, planner, experiments, band, regime, explain.

Every answer is run through ``engine.ai.validator.validate`` against the context pack.

CLI: ``python -m engine.ai.answer --build-cache`` regenerates ``artifacts/ai_cache.json``;
``python -m engine.ai.answer "question" --habitat lunar_base`` prints one answer.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from engine.ai import context as ctx
from engine.ai.validator import validate
from engine.ledger import canonical_json

ROOT = Path(__file__).resolve().parents[2]
PROMPTS = Path(__file__).resolve().parent / "prompts"
CACHE_PATH = ROOT / "artifacts" / "ai_cache.json"
PROMPT_VERSION = "v1"
DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_CLAUDE_CALLS = int(os.environ.get("GRAVITY_GAP_MAX_CLAUDE_CALLS", "200"))
_claude_calls = 0

DEMO_QUESTIONS: list[tuple[str, str | None]] = [
    ("Why is the lunar base in the mixed regime?", "lunar_base"),
    ("Why is the M1 band wide for the lunar base?", "lunar_base"),
    ("Which experiments matter most for a Mars base?", "mars_base"),
    ("What should LUCI test first?", "lunar_base"),
    ("Is the lunar rover safer with the fans off?", "lunar_rover"),
    ("Can you predict rocket engine fires?", "lunar_base"),
    # R1 real-fire replay: habitat None -> the incident's own conditions (cache key "incident:<id>")
    ("What does Gravity Gap say about the Mir fire?", None),
    ("What would Gravity Gap say about Apollo 1's cabin air?", None),
    ("Is Apollo 13 in scope?", None),
    # R2 suppression calculator (intent "suppression"; engine.suppression.curve in the context pack)
    ("How much CO₂ would it take to put out a flame in ISS air?", "iss"),
    ("Why can't Gravity Gap answer suppression for the lunar base?", "lunar_base"),
    ("Does helium work better than CO₂?", "iss"),
]

OUT_OF_SCOPE = ("rocket", "propellant", "propulsion", "thruster", "launch vehicle", "booster",
                "combustion chamber", "explosive", "bomb", "weapon", "missile", "warhead")
HABITAT_WORDS = (("lunar rover", "lunar_rover"), ("rover", "lunar_rover"), ("lunar base", "lunar_base"),
                 ("moon", "lunar_base"), ("lunar", "lunar_base"), ("luci", "lunar_base"),
                 ("mars", "mars_base"), ("iss", "iss"), ("space station", "iss"),
                 ("exploration", "exploration"), ("earth", "earth"))
REGIME_DEF = "forced Ri < 0.1, buoyant Ri > 10"


# --------------------------------------------------------------------------- formatting


def fmt(x: Any) -> str:
    """3 significant figures, plain decimal (no exponent), so the validator's 0.5% tolerance holds."""
    if x is None:
        return "n/a"
    if isinstance(x, str):
        return x
    x = float(x)
    if not math.isfinite(x):
        return "unbounded"
    if x == 0:
        return "0"
    if abs(x) >= 100:
        return str(int(round(x)))
    d = max(0, 2 - int(math.floor(math.log10(abs(x)))))
    s = f"{x:.{d}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def pct(x: Any) -> str:
    return "n/a" if x is None else f"{fmt(float(x) * 100)}%"


def val(pred: dict, x: Any) -> str:
    """Value in the metric's natural unit (probabilities as %)."""
    if x is None:
        return "n/a"
    if isinstance(x, str):
        return x.replace("_", " ")
    if pred.get("kind") == "probability":
        return pct(x)
    unit = pred.get("unit") or ""
    return f"{fmt(x)} {unit}".strip() if unit not in ("category", "probability") else fmt(x)


def band(pred: dict, b: Any) -> str:
    if not b:
        return "n/a"
    lo, hi = b[0], b[1]
    if isinstance(lo, str) or isinstance(hi, str):
        return f"{val(pred, lo)} to {val(pred, hi)}"
    return f"{val(pred, lo)} to {val(pred, hi)}"


def _norm(q: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", q.lower())).strip()


# --------------------------------------------------------------------------- intent


def classify(question: str, context_ids: Iterable[str] = ()) -> str:
    q = question.lower()
    if ctx.find_incidents(question, context_ids):
        return "incident"
    if any(w in q for w in OUT_OF_SCOPE):
        return "refusal"
    if ctx.wants_suppression(question, context_ids):
        return "suppression"
    if ctx._wants_fans_off(q) or ("fan" in q and ("off" in q or "without" in q)) or "ventilation" in q:
        return "fans_off"
    if any(w in q for w in ("test first", "luci", "fm2", "next test", "which test", "what should", "plan")):
        return "planner"
    if any(w in q for w in ("experiment", "investigation", "matter most", "which data", "evidence")):
        return "experiments"
    if any(w in q for w in ("band", "wide", "uncertain", "confidence", "error bar", "interval")):
        return "band"
    if any(w in q for w in ("regime", "mixed", "buoyant", "forced", "richardson")):
        return "regime"
    return "explain"


def infer_habitat(question: str) -> str:
    q = question.lower()
    for word, pid in HABITAT_WORDS:
        if re.search(rf"\b{re.escape(word)}\b", q):
            return pid
    return "lunar_base"


def _metric_in(question: str, context_ids: Iterable[str]) -> str | None:
    m = re.search(r"\bM([1-5])\b", question, re.IGNORECASE)
    if m:
        return f"M{m.group(1)}"
    for c in context_ids or ():
        if re.fullmatch(r"M[1-5]", str(c)):
            return str(c)
    return None


# --------------------------------------------------------------------------- template pieces


def _regime_par(pack: dict, phys: dict | None = None, cite: str = "eng:physics", who: str | None = None,
                hab: dict | None = None) -> str:
    h = hab or pack["habitat"]
    phys = phys if phys is not None else pack.get("physics")
    who = who or h.get("label") or pack["habitat"]["label"]
    if not phys:
        return f"The physics engine is not available in this build, so the regime for {who} cannot be computed."
    ri = phys.get("ri")
    ri_txt = "unbounded (no forced flow)" if ri is None else fmt(ri)
    fr = (phys.get("mc") or {}).get("regime_fractions") or {}
    s = (f"**Regime: {phys.get('regime')}.** For {who} the buoyant velocity is {fmt(phys.get('u_b_cm_s'))} cm/s "
         f"against a vent flow of {fmt(h['u_cm_s'])} cm/s, so the Richardson number "
         f"Ri = u_b²/u_f² is {ri_txt} ({REGIME_DEF}) [{cite}].")
    if fr:
        s += (f" Sampling the uncertain constants gives {pct(fr.get('forced'))} forced, {pct(fr.get('mixed'))} "
              f"mixed and {pct(fr.get('buoyant'))} buoyant flames [{cite}].")
    return s


def _habitat_line(pack: dict) -> str:
    h = pack["habitat"]
    return (f"{h['label']}: {fmt(h['g_m_s2'])} m/s² ({fmt(h['g_over_g0'])} g), {fmt(h['p_psia'])} psia, "
            f"{pct(h['o2'])} O₂, vent {fmt(h['u_cm_s'])} cm/s, flame size {fmt(h['L_mm'])} mm.")


def _pred_par(pred: dict, cite: str | None = None) -> str:
    cite = cite or pred.get("id") or f"eng:{pred.get('metric')}"
    name = f"**{pred.get('metric')} – {pred.get('label')}**"
    if not pred.get("applicable"):
        return f"{name}: no estimate – {pred.get('reason') or 'outside the tested conditions'} [{cite}]."
    s = f"{name}: estimate {val(pred, pred.get('estimate'))}, 90% band {band(pred, pred.get('band90'))} [{cite}]."
    ref0 = pred.get("ref_0g") or {}
    if ref0.get("band90") and ref0.get("band90") != pred.get("band90"):
        s += f" The microgravity-only band is {band(pred, ref0['band90'])}."
    tr = pred.get("transfer") or {}
    if tr.get("confidence"):
        s += f" Transfer confidence: **{tr['confidence']}**."
    return s


def _top_sens(pred: dict, quantity: str) -> dict | None:
    best, spread = None, -1.0
    for s in pred.get("sensitivity") or []:
        if s.get("quantity", "estimate") != quantity:
            continue
        lo, hi = s.get("low"), s.get("high")
        if not isinstance(lo, (int, float)) or not isinstance(hi, (int, float)):
            continue
        if abs(hi - lo) > spread:
            best, spread = s, abs(hi - lo)
    return best


PARAM_NAMES = {"o2": "O₂ fraction", "pressure": "pressure (atm)", "C_b": "buoyancy coefficient C_b",
               "k": "buoyancy-coupling factor k", "dT_over_T": "flame temperature ratio ΔT/T",
               "L_factor": "flame-size factor", "L_mm": "flame size (mm)", "u_cm_s": "vent speed (cm/s)"}


def _why_wide(pred: dict) -> str:
    if not pred.get("applicable"):
        return ""
    parts = []
    widen = (pred.get("inputs") or {}).get("widen_factor")
    fr = pred.get("regime_fractions") or {}
    if widen is not None:
        parts.append(f"The training tests had no buoyancy, so the band is widened ×{fmt(widen)} for the "
                     f"{pct(fr.get('mixed'))} mixed and {pct(fr.get('buoyant'))} buoyant share of flames.")
    s_est = _top_sens(pred, "estimate")
    if s_est:
        parts.append(f"The largest atmosphere sensitivity is {PARAM_NAMES.get(s_est['param'], s_est['param'])}: "
                     f"moving it from {fmt(s_est.get('input_low'))} to {fmt(s_est.get('input_high'))} moves the "
                     f"estimate from {val(pred, s_est['low'])} to {val(pred, s_est['high'])}.")
    s_w = _top_sens(pred, "band_width")
    if s_w:
        parts.append(f"Among the physics constants, {PARAM_NAMES.get(s_w['param'], s_w['param'])} matters most: over "
                     f"{fmt(s_w.get('input_low'))} to {fmt(s_w.get('input_high'))} the band width goes from "
                     f"{val(pred, s_w['low'])} to {val(pred, s_w['high'])}.")
    if not parts:
        return ""
    return " ".join(parts) + f" [{pred.get('id')}]"


def _evidence_par(pack: dict, pred: dict, k: int = 3) -> str:
    rows = {r["id"]: r for r in pack.get("evidence") or []}
    picks = [rows[f"rec:{rid}"] for rid in (pred.get("evidence_ids") or []) if f"rec:{rid}" in rows][:k]
    if not picks:
        return ""
    bits = []
    for r in picks:
        desc = [r.get("fuel") or r.get("investigation") or ""]
        if r.get("o2_mole_fraction") is not None:
            desc.append(f"{pct(r['o2_mole_fraction'])} O₂")
        if r.get("pressure_atm") is not None:
            desc.append(f"{fmt(r['pressure_atm'])} atm")
        if r.get("outcome"):
            desc.append(str(r["outcome"]))
        bits.append(f"{', '.join(d for d in desc if d)} [{r['id']}]")
    invs = " ".join(f"[{i}]" for i in pred.get("evidence_investigations") or [])
    return f"Nearest evidence {invs}: " + "; ".join(bits) + "."


def _planner_items(pack: dict, metric: str | None = None, g: float | None = None) -> list[dict]:
    items = list(pack.get("planner") or [])
    if metric:
        m_items = [i for i in items if i.get("metric") == metric]
        items = m_items or items
    if g is not None:
        g_items = [i for i in items if i.get("g_m_s2") is not None and abs(float(i["g_m_s2"]) - g) < 1e-6]
        items = g_items or items
    return items


def _planner_par(pack: dict, item: dict) -> str:
    ext = " ".join(f"[{e}]" for e in item.get("extends") or [])
    s = (f"Planner rank {item.get('rank')}: {item.get('metric')} at {fmt(item.get('g_m_s2'))} m/s², "
         f"{fmt(item.get('p_psia'))} psia, {pct(item.get('o2'))} O₂, vent {fmt(item.get('u_cm_s'))} cm/s "
         f"(score {fmt(item.get('score'))}) [{item['id']}]. {item.get('rationale') or ''}")
    if ext:
        s += f" It extends {ext}."
    return s


def _design_id(pack: dict, text: str) -> str:
    return f"eng:design:{(pack.get('design_implications') or []).index(text) + 1}"


def _narrow_par(pack: dict, metric: str) -> str:
    items = _planner_items(pack, metric, pack["habitat"]["g_m_s2"])
    if items:
        return "**What would narrow it:** " + _planner_par(pack, items[0])
    h = pack["habitat"]
    return ("**What would narrow it:** the test planner artifact is not available in this build; the gap is a "
            f"partial-gravity test at {fmt(h['p_psia'])} psia / {pct(h['o2'])} O₂ in the mixed regime.")


def _pick_metric(pack: dict, metric: str | None) -> dict | None:
    preds = pack.get("predictions") or {}
    if metric and metric in preds:
        return preds[metric]
    for m in ("M1", "M3", "M2", "M5", "M4"):
        if m in preds and preds[m].get("applicable"):
            return preds[m]
    return next(iter(preds.values()), None)


def _missing_note(pack: dict) -> str:
    miss = [m for m in pack.get("missing") or [] if not m.startswith("artifacts/planner")]
    return f"_Not available in this build: {', '.join(miss)}._" if miss else ""


# --------------------------------------------------------------------------- templates per intent


def t_refusal(pack: dict, question: str) -> str:
    return ("This is outside Gravity Gap's scope. Gravity Gap predicts **cabin fires** in spacecraft and "
            "habitats (burning materials, fuel droplets, small gas flames, ventilation and cabin atmosphere) from "
            "NASA PSI microgravity combustion experiments. Rocket engines, propellants and propulsion combustion "
            "are a different problem and are not covered by this data or model; please consult propulsion-"
            "specific resources for that. Within scope you can ask, for example, *Why is the lunar base in the "
            "mixed regime?* or *What should LUCI test first?*")


def t_regime(pack: dict, question: str, metric: str | None) -> str:
    out = [_habitat_line(pack), _regime_par(pack)]
    phys = pack.get("physics") or {}
    if phys.get("regime") == "mixed":
        out.append("In the mixed regime neither the 0 g (ISS, forced-flow) data nor 1 g (buoyant) data apply "
                   "directly: buoyancy and the vent flow are comparable, which is exactly the condition PSI never tested.")
    impl = [d for d in pack.get("design_implications") or []
            if ("lunar" in d.lower() if pack["habitat"]["g_m_s2"] < 2 else "mars" in d.lower())]
    if impl and pack["habitat"]["g_m_s2"] > 0:
        out.append(f"Design implication: {impl[0]} [{_design_id(pack, impl[0])}]")
    pred = _pick_metric(pack, metric)
    if pred:
        out.append("Consequence for the predictions: " + _pred_par(pred))
    return "\n\n".join(o for o in out if o)


def t_band(pack: dict, question: str, metric: str | None) -> str:
    pred = _pick_metric(pack, metric or "M1")
    if pred is None:
        return f"No bounds prediction is available for {pack['habitat']['label']} in this build. {_missing_note(pack)}"
    out = [_habitat_line(pack), _pred_par(pred)]
    if pred.get("applicable"):
        out.append("**Why the band is wide:** " + _why_wide(pred))
    out += [_regime_par(pack), _narrow_par(pack, pred["metric"]), _evidence_par(pack, pred)]
    return "\n\n".join(o for o in out if o)


def t_experiments(pack: dict, question: str, metric: str | None) -> str:
    h = pack["habitat"]
    out = [_habitat_line(pack)]
    ranked = pack.get("rank") or []
    if ranked:
        lines = ["**Most relevant PSI investigations** (relevance score: atmosphere match, fire-safety pillars, "
                 "fuel realism, outcome data, test count):"]
        for i, r in enumerate(ranked[:5], start=1):
            p = r.get("parts") or {}
            lines.append(f"{i}. {r.get('acronym') or r['id']} [{r['id']}] score {fmt(r.get('score'))} "
                         f"(atmosphere {fmt(p.get('atmosphere'))}, fuel realism {fmt(p.get('fuel_realism'))})")
        out.append("\n".join(lines))
    preds = pack.get("predictions") or {}
    feeds = []
    for m, p in preds.items():
        invs = " ".join(f"[{i}]" for i in p.get("evidence_investigations") or [])
        state = "estimate" if p.get("applicable") else "no estimate (outside tested atmosphere)"
        if invs:
            feeds.append(f"{m} uses {invs} ({p.get('n_train')} training tests, {state}) [{p['id']}]")
    if feeds:
        out.append("**Data behind the predictions here:** " + "; ".join(feeds) + ".")
    items = _planner_items(pack, None, h["g_m_s2"])
    if items:
        out.append("**Where new experiments matter most:** " + _planner_par(pack, items[0]))
    out.append(_regime_par(pack))
    return "\n\n".join(o for o in out if o)


def t_planner(pack: dict, question: str, metric: str | None) -> str:
    h = pack["habitat"]
    items = _planner_items(pack, metric, None)
    out = []
    if items:
        out.append("**First test:** " + _planner_par(pack, items[0]))
        if len(items) > 1:
            nxt = "; ".join(f"rank {i.get('rank')}: {i.get('metric')} at {fmt(i.get('g_m_s2'))} m/s², "
                            f"{fmt(i.get('p_psia'))} psia, {pct(i.get('o2'))} O₂, vent {fmt(i.get('u_cm_s'))} cm/s "
                            f"[{i['id']}]" for i in items[1:3])
            out.append(f"**Then:** {nxt}.")
        out.append("Ranking = current band width × habitat weight × mixed-regime fraction, so tests sit where the "
                   "predictions are least certain and the habitat atmosphere matters most.")
    else:
        out.append("The test planner artifact is not available in this build. " + _narrow_par(pack, metric or "M1"))
    pred = _pick_metric(pack, metric)
    if pred:
        out.append(f"Today, for {h['label']}: " + _pred_par(pred))
    return "\n\n".join(o for o in out if o)


def t_fans_off(pack: dict, question: str, metric: str | None) -> str:
    h = pack["habitat"]
    sc = (pack.get("scenarios") or {}).get("fans_off")
    out = [_habitat_line(pack), "**With the fans on:** " + _regime_par(pack)]
    if not sc:
        out.append("A fans-off scenario was not computed (the vent flow is already zero or the engine is missing).")
        return "\n\n".join(out)
    out.append("**With the fans off:** " + _regime_par(pack, sc.get("physics"), "eng:fans_off:physics",
                                                         sc.get("label"), sc.get("habitat")))
    preds, preds0 = pack.get("predictions") or {}, sc.get("predictions") or {}
    wider = None
    for m in ([metric] if metric else []) + ["M1", "M3", "M4", "M5", "M2"]:
        if m in preds and m in preds0:
            p, p0 = preds[m], preds0[m]
            if not (p.get("applicable") or p0.get("applicable")):
                continue
            out.append(f"Fans on: {_pred_par(p)}\n\nFans off: {_pred_par(p0)}")
            b, b0 = p.get("band90"), p0.get("band90")
            if b and b0 and all(isinstance(x, (int, float)) for x in (*b, *b0)):
                wider = (b0[1] - b0[0]) > (b[1] - b[0])
            break
    trend = {True: "the 90% band gets wider", False: "the band does not narrow in a way the data support",
             None: "the PSI microgravity data transfer less well"}[wider]
    out.append("**Not safer by this evidence.** Without ventilation the flame is not microgravity-like: buoyancy "
               f"takes over and {trend}. For M1–M3 the "
               "engine never shifts the estimate with gravity or flow (gravity honesty rule), it only widens the "
               "band, so 'safer' cannot be claimed from these data.")
    impl = [d for d in pack.get("design_implications") or [] if "turning ventilation off" in d.lower()
            and (("lunar" in d.lower()) == (h["g_m_s2"] < 2))]
    if impl:
        out.append(f"Design implication: {impl[0]} [{_design_id(pack, impl[0])}]")
    return "\n\n".join(o for o in out if o)


def t_explain(pack: dict, question: str, metric: str | None) -> str:
    pred = _pick_metric(pack, metric)
    out = [_habitat_line(pack), _regime_par(pack)]
    if pred:
        out.append(_pred_par(pred))
        if pred.get("applicable"):
            out.append("**Why the band is wide:** " + _why_wide(pred))
        out.append(_narrow_par(pack, pred["metric"]))
        out.append(_evidence_par(pack, pred))
    else:
        out.append(_missing_note(pack))
    return "\n\n".join(o for o in out if o)


# --------------------------------------------------------------------------- incidents (R1)

# Hindsight wording the incident answers must never contain (plan/13-round-2-features.md, writing rules).
HINDSIGHT = re.compile(r"\b(would|could|might) have\b|\bprevent(ed|able)?\b", re.IGNORECASE)
INCIDENT_FIELD_LABELS = (("g_m_s2", "gravity"), ("p_psia", "pressure"), ("o2", "O₂"), ("u_cm_s", "vent flow"),
                         ("L_mm", "flame size"))
INCIDENT_CLOSING = ("This is what today's PSI data can and cannot say about these conditions. It is not a "
                    "reconstruction of the event and not a judgement of the crew or of the people who worked on it.")
INCIDENT_CLOSING_OUT_OF_SCOPE = ("Gravity Gap makes no prediction about this event. This is not a judgement of the "
                                 "crew or of the people who worked on it.")


def _clean(text: Any) -> str:
    """Artifact sentence, or '' when it uses hindsight wording (never shown in an incident answer)."""
    t = str(text or "").strip()
    return "" if not t or HINDSIGHT.search(t) else t


def _source_urls(inc: dict, field: str | None = None) -> list[str]:
    urls: list[str] = []
    for s in inc.get("sources") or []:
        if not isinstance(s, dict) or not s.get("url"):
            continue
        if field is None or s.get("field") == field:
            u = str(s["url"]).strip()
            if u not in urls:
                urls.append(u)
    return urls


def _cites(ids: Iterable[str]) -> str:
    return " ".join(f"[{i}]" for i in ids)


def _incident_value(field: str, v: Any) -> str:
    if field == "o2":
        return pct(v)
    unit = {"g_m_s2": "m/s²", "p_psia": "psia", "u_cm_s": "cm/s", "L_mm": "mm"}[field]
    return f"{fmt(v)} {unit}"


def _incident_title(inc: dict) -> str:
    year = f" ({inc['year']})" if inc.get("year") else ""
    phase = f": {inc['phase']}" if inc.get("phase") else ""
    return f"**{inc.get('name') or inc['incident_id']}{year}**{phase} [{inc['id']}]."


def _incident_conditions(inc: dict) -> str:
    assumed = set(inc.get("assumed") or [])
    bits = []
    for field, label in INCIDENT_FIELD_LABELS:
        v = inc.get(field)
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            continue
        cite = _source_urls(inc, field)
        tag = " (assumed; not stated in the sources)" if field in assumed else ""
        bits.append(f"{label} {_incident_value(field, v)}{tag}" + (f" {_cites(cite)}" if cite else ""))
    if not bits:
        return ""
    note = _clean(inc.get("assumed_note"))
    return f"**Conditions used** [{inc['id']}]: " + "; ".join(bits) + "." + (f" {note}" if note else "")


def _incident_quotes(inc: dict) -> str:
    lines = []
    for s in inc.get("sources") or []:
        if not isinstance(s, dict) or not s.get("url") or not _clean(s.get("quote")):
            continue
        q = " ".join(str(s["quote"]).split())
        lines.append(f"- {s.get('field') or 'source'}: “{q}” [{str(s['url']).strip()}]")
    return ("**What the sources say:**\n" + "\n".join(lines)) if lines else ""


def _incident_regime(inc: dict) -> str:
    phys = inc.get("physics")
    if not phys:
        return ""
    ri = phys.get("ri")
    ri_txt = "unbounded (no forced flow)" if ri is None else fmt(ri)
    s = (f"**Regime: {phys.get('regime')}.** Buoyant velocity {fmt(phys.get('u_b_cm_s'))} cm/s against a vent flow "
         f"of {fmt(inc.get('u_cm_s'))} cm/s gives Ri = {ri_txt} ({REGIME_DEF}) [{inc['id']}].")
    fr = inc.get("regime_fractions") or {}
    if fr:
        s += (f" Sampling the uncertain constants gives {pct(fr.get('forced'))} forced, {pct(fr.get('mixed'))} "
              f"mixed and {pct(fr.get('buoyant'))} buoyant flames [{inc['id']}].")
    return s


def _incident_metrics(pack: dict, inc: dict) -> str:
    metrics = inc.get("metrics") or {}
    if not metrics:
        return ""
    cov = inc.get("coverage") or {}
    meta = pack.get("metrics") or {}
    lines = []
    for m in sorted(metrics):
        r = metrics[m] or {}
        info = {**(meta.get(m) or {}), "metric": m}
        name = f"{m} – {info['label']}" if info.get("label") else m
        c = cov.get(m) or {}
        if r.get("applicable"):
            line = f"- **{name}**: estimate {val(info, r.get('estimate'))}, 90% band {band(info, r.get('band90'))}"
            if r.get("transfer_confidence"):
                line += f", transfer confidence **{r['transfer_confidence']}**"
        else:
            reason = _clean(r.get("reason")) or "outside the tested conditions"
            line = f"- **{name}**: **no evidence** – {reason}"
        if isinstance(c.get("nearest_distance"), (int, float)):
            line += f" (nearest tested condition at distance {fmt(c['nearest_distance'])})"
        lines.append(line + f" [{inc['id']}]")
    return "**What today's data can and cannot say:**\n" + "\n".join(lines)


_METRIC_FINDING = re.compile(r"^M[1-5]\b")


def _incident_findings(inc: dict, skip: Iterable[str] = ()) -> str:
    """Engine findings, minus the per-metric ones already listed by ``_incident_metrics`` and ``skip``."""
    finds = [f for f in (_clean(x) for x in inc.get("findings") or [])
             if f and not _METRIC_FINDING.match(f) and f not in skip]
    return ("**Findings:** " + " ".join(finds) + f" [{inc['id']}]") if finds else ""


def _incident_par(pack: dict, inc: dict) -> str:
    summary = _clean(inc.get("summary"))
    src = _source_urls(inc, "summary")
    out = [_incident_title(inc)]
    if summary:
        out.append(f"{summary} [{inc['id']}]" + (f" {_cites(src)}" if src else ""))
    if not inc.get("in_scope"):
        raw_note = _clean(inc.get("scope_note"))
        note = re.sub(r"^outside (this tool's|gravity gap's) scope\s*[:.-]\s*", "", raw_note, flags=re.IGNORECASE)
        note = note[:1].upper() + note[1:]
        out.insert(1, f"**Outside Gravity Gap's scope.** {note + ' ' if note else ''}Gravity Gap studies cabin "
                      f"fires (burning materials, fuel droplets and small gas flames in a cabin atmosphere with "
                      f"ventilation) using NASA PSI combustion experiments, so it gives no regime, estimate or band "
                      f"for this event [{inc['id']}].")
        out += [_incident_findings(inc, skip=(raw_note,)), _incident_quotes(inc)]
        return "\n\n".join(o for o in out if o)
    out.append(f"**Scope:** inside Gravity Gap's scope (a fire in a crew-cabin atmosphere) [{inc['id']}].")
    out += [_incident_conditions(inc), _incident_regime(inc), _incident_metrics(pack, inc),
            _incident_findings(inc), _incident_quotes(inc)]
    return "\n\n".join(o for o in out if o)


def t_incident(pack: dict, question: str, metric: str | None) -> str:
    incs = pack.get("incidents") or []
    if not incs:
        return ("The real-fire replay artifact (artifacts/incidents.json) is not available in this build, so "
                "Gravity Gap cannot describe this incident yet.")
    parts = [_incident_par(pack, inc) for inc in incs]
    closing = INCIDENT_CLOSING if any(i.get("in_scope") for i in incs) else INCIDENT_CLOSING_OUT_OF_SCOPE
    return "\n\n---\n\n".join(parts) + "\n\n" + closing


# --------------------------------------------------------------------------- suppression (R2)

# Shown with every suppression answer (plan/13-round-2-features.md R2, "Safety note (always visible)").
# The curve's own ``safety_note`` (engine.suppression.SAFETY_NOTE) is used when present; this fallback is kept
# word-for-word equal to it so the web page and the answers say the same thing.
SAFETY_NOTE = ("CO₂ at these concentrations is dangerous to breathe. Spacecraft use portable CO₂ or "
               "water-mist extinguishers aimed at the fire, not cabin flooding. This shows how dilution affected "
               "flames in NASA's tests; it is not an operating procedure.")
DILUENT_SHORT = {"co2": "CO₂", "he": "helium"}
SUPPRESSION_SAMPLE_POINTS = 4


def _supp_name(block: dict) -> str:
    return DILUENT_SHORT.get(block.get("diluent"), str(block.get("label") or block.get("diluent")))


def _supp_points(block: dict) -> tuple[list[dict], list[dict]]:
    """(applicable points with fraction > 0, gated points with fraction > 0) on M1."""
    ok, gated = [], []
    for p in block.get("points") or []:
        f, m1 = p.get("fraction"), p.get("M1") or {}
        if not isinstance(f, (int, float)) or f <= 0:
            continue
        good = m1.get("applicable") and isinstance(m1.get("estimate"), (int, float))
        (ok if good else gated).append(p)
    return ok, gated


def _supp_sample(ok: list[dict], dose: float | None) -> list[dict]:
    if len(ok) <= SUPPRESSION_SAMPLE_POINTS:
        return ok
    n = len(ok) - 1
    idx = {0, n // 3, (2 * n) // 3, n}
    if dose is not None:
        idx |= {i for i, p in enumerate(ok) if math.isclose(float(p["fraction"]), dose, abs_tol=1e-9)}
    return [ok[i] for i in sorted(idx)]


def _supp_point_line(pack: dict, block: dict, p: dict) -> str:
    meta = pack.get("metrics") or {}
    m1 = p["M1"]
    s = f"- {pct(p['fraction'])} {_supp_name(block)}: M1 estimate {pct(m1['estimate'])}"
    if m1.get("band90"):
        s += f", 90% band {band({'kind': 'probability'}, m1['band90'])}"
    m2 = p.get("M2") or {}
    if m2.get("applicable") and isinstance(m2.get("estimate"), (int, float)):
        info = {**(meta.get("M2") or {"unit": "mm"}), "metric": "M2"}
        s += f"; M2 extinction diameter {val(info, m2['estimate'])}"
        if m2.get("band90"):
            s += f" (90% band {band(info, m2['band90'])})"
    return s


def _supp_tested_range(block: dict) -> str:
    rng = block.get("tested_o2_range")
    if not rng or len(rng) != 2 or rng[0] is None or rng[1] is None:
        return f"FLEX has no {_supp_name(block)}-diluted tests the gate can use"
    return f"FLEX tested {_supp_name(block)} dilution only between {pct(rng[0])} and {pct(rng[1])} O₂"


def _supp_par(pack: dict, block: dict) -> str:
    h, cite, name = pack["habitat"], f"[{block['id']}]", _supp_name(block)
    ok, gated = _supp_points(block)
    dose = block.get("dose_for_p90") or None
    dose_f = dose.get("fraction") if isinstance(dose, dict) else None
    out = [f"**{block.get('label') or name}** replacing nitrogen at the habitat's {pct(h['o2'])} O₂ and "
           f"{fmt(h['p_psia'])} psia {cite}. The curve is the M1 chance that a droplet flame self-extinguishes "
           f"before burnout, from the FLEX droplet tests [PSI-69]."]
    if not ok:
        rng = block.get("tested_o2_range")
        where = ""
        if rng and len(rng) == 2 and rng[1] is not None and h["o2"] > rng[1]:
            where = f", and {pct(h['o2'])} O₂ is above that ceiling"
        elif rng and len(rng) == 2 and rng[0] is not None and h["o2"] < rng[0]:
            where = f", and {pct(h['o2'])} O₂ is below that range"
        out.append(f"**No evidence at any {name} fraction above 0.** {_supp_tested_range(block)}{where} {cite}. "
                   f"Every diluted point is outside tested conditions, so Gravity Gap gives no estimate, band or "
                   f"dose here (the chart shows gaps, never interpolated values).")
        note = (block.get("gate_note") or "").strip()
        if note:
            out.append(f"**Tested conditions:** {note} {cite}")
        out.append(f"**Dilution for 90% self-extinction:** not reached inside tested conditions {cite}.")
        return "\n\n".join(out)
    if isinstance(dose_f, (int, float)) and dose_f <= 0:
        out.append(f"**Dilution for 90% self-extinction:** none needed in the model {cite}. "
                   + (str(dose["note"]) if dose.get("note") else
                      f"The M1 estimate is already at or above 90% with no {name}."))
    elif isinstance(dose_f, (int, float)):
        out.append(f"**Dilution for 90% self-extinction:** about {pct(dose_f)} {name}, the smallest tested-"
                   f"condition fraction whose M1 estimate reaches 90% {cite}.")
    else:
        out.append(f"**Dilution for 90% self-extinction:** not reached inside tested conditions {cite}.")
    lines = [_supp_point_line(pack, block, p) for p in _supp_sample(ok, dose_f)]
    out.append(f"**Estimates along the curve** {cite}:\n" + "\n".join(lines))
    note = (block.get("gate_note") or "").strip()
    if note:
        out.append(f"**Tested conditions:** {note} {cite}")
    else:
        extra = ""
        if gated:
            extra = f"Above {pct(max(float(p['fraction']) for p in ok))} {name} there is no estimate. "
        out.append(f"{extra}{_supp_tested_range(block)} {cite}.")
    return "\n\n".join(out)


def _supp_ref_label(block: dict, r: dict) -> str:
    lo, hi, name = r.get("fraction_lo"), r.get("fraction_hi"), _supp_name(block)
    if isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
        return f"no {name}" if hi <= 0 else f"{pct(lo)} to {pct(hi)} {name}"
    if isinstance(lo, (int, float)):
        return f"above {pct(lo)} {name}"
    return f"bin {r.get('bin')}"


def _supp_ref_par(pack: dict, block: dict) -> str:
    ref = (pack.get("suppression_reference") or {}).get(block.get("diluent")) or {}
    rows = [r for r in ref.get("rows") or [] if isinstance(r.get("extinction_rate"), (int, float))]
    if not rows:
        return ""
    lines = [f"- {r.get('fuel') or 'FLEX'}, {_supp_ref_label(block, r)}: {fmt(r.get('extinctions'))} self-extinguished, "
             f"{fmt(r.get('completions'))} burned out ({pct(r['extinction_rate'])} self-extinction)"
             for r in rows[:8]]
    band_txt = rows[0].get("o2_band")
    head = f"**Raw FLEX outcomes, {band_txt}**" if band_txt else "**Raw FLEX outcomes**"
    return (f"{head} (counted from the test records, no model; bins mix pressures and droplet sizes, so they show "
            f"direction, not magnitude) [{ref['id']}]:\n" + "\n".join(lines))


def _dose_text(v: float) -> str:
    return "with no dilution" if v <= 0 else f"at about {pct(v)}"


def _supp_compare(pack: dict) -> str:
    blocks = pack.get("suppression") or {}
    if not ("co2" in blocks and "he" in blocks):
        return ""
    doses = {}
    for d, b in blocks.items():
        dose = b.get("dose_for_p90")
        doses[d] = dose.get("fraction") if isinstance(dose, dict) else None
    c, he = doses.get("co2"), doses.get("he")
    cites = "[eng:suppression:co2] [eng:suppression:he]"
    if isinstance(c, (int, float)) and isinstance(he, (int, float)):
        if math.isclose(c, he, abs_tol=1e-9):
            verdict = (f"both reach a 90% M1 estimate {_dose_text(c)}, so the dose cannot tell them apart; compare "
                       f"the estimates along the two curves above instead")
        else:
            lo_d, hi_d = ("co2", "he") if c < he else ("he", "co2")
            verdict = (f"{DILUENT_SHORT[lo_d]} reaches a 90% M1 estimate {_dose_text(doses[lo_d])}, "
                       f"{DILUENT_SHORT[hi_d]} {_dose_text(doses[hi_d])}")
        return (f"**CO₂ versus helium:** in these models {verdict} {cites}. This compares model curves inside "
                f"tested conditions only; it is not a ranking of extinguishing agents.")
    have = [DILUENT_SHORT[d] for d, v in doses.items() if isinstance(v, (int, float))]
    if have:
        other = [DILUENT_SHORT[d] for d in ("co2", "he") if DILUENT_SHORT[d] not in have]
        return (f"**CO₂ versus helium:** only {have[0]} reaches a 90% M1 estimate inside tested conditions; "
                f"{other[0]} does not, so the data cannot say which works better here {cites}.")
    return (f"**CO₂ versus helium:** neither reaches a 90% M1 estimate inside tested conditions here, so the "
            f"data cannot say which works better {cites}.")


def t_suppression(pack: dict, question: str, metric: str | None) -> str:
    blocks = pack.get("suppression") or {}
    out = [_habitat_line(pack)]
    if not blocks:
        out.append("The suppression calculator (engine.suppression) is not available in this build, so Gravity "
                   "Gap cannot give a dilution curve for these conditions yet.")
    else:
        for d in ("co2", "he"):
            if d in blocks:
                out += [_supp_par(pack, blocks[d]), _supp_ref_par(pack, blocks[d])]
        out.append(_supp_compare(pack))
    note = next((b.get("safety_note") for b in blocks.values() if b.get("safety_note")), None) or SAFETY_NOTE
    out.append(f"**Safety note:** {note}")
    return "\n\n".join(o for o in out if o)


TEMPLATES = {"suppression": t_suppression, "incident": t_incident, "regime": t_regime, "band": t_band, "experiments": t_experiments, "planner": t_planner,
             "fans_off": t_fans_off, "explain": t_explain}


def template_answer(question: str, pack: dict, intent: str, metric: str | None) -> str:
    if intent == "refusal":
        return t_refusal(pack, question)
    text = TEMPLATES.get(intent, t_explain)(pack, question, metric)
    if intent == "incident":
        return text  # self-contained: built only from the incident artifact, not the habitat predictions
    note = _missing_note(pack)
    return text + ("\n\n" + note if note else "")


# --------------------------------------------------------------------------- Claude path


def claude_available() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    return importlib.util.find_spec("anthropic") is not None


def load_prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def _system_prompt() -> str:
    return "\n\n".join(load_prompt(n) for n in ("system.v1", "explain_bounds.v1", "summarize_investigation.v1"))


def _parse_json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except ValueError:
        return None
    return obj if isinstance(obj, dict) and isinstance(obj.get("answer_markdown"), str) else None


def claude_answer(question: str, pack: dict) -> dict | None:  # pragma: no cover - needs network + key
    """One Claude call (+1 retry on validation failure). Returns None to fall back to the template."""
    global _claude_calls
    if _claude_calls >= MAX_CLAUDE_CALLS:
        return None
    import anthropic  # noqa: PLC0415 - optional dependency

    client = anthropic.Anthropic()
    model = os.environ.get("GRAVITY_GAP_MODEL", DEFAULT_MODEL)
    system = [{"type": "text", "text": _system_prompt(), "cache_control": {"type": "ephemeral"}}]
    messages: list[dict] = [{"role": "user", "content":
                             f"<context_pack>\n{canonical_json(pack)}\n</context_pack>\n\n<question>{question}</question>"}]
    for _attempt in range(2):
        _claude_calls += 1
        try:
            resp = client.messages.create(model=model, max_tokens=4000, system=system, messages=messages)
        except anthropic.APIError:
            return None
        if getattr(resp, "stop_reason", None) == "refusal":
            return None
        text = "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")
        parsed = _parse_json(text)
        if parsed is None:
            errors = ["response was not the required JSON object"]
        else:
            report = validate(parsed["answer_markdown"], pack, parsed.get("numbers_used") or [],
                              parsed.get("citations") or [])
            if report["ok"]:
                return {**parsed, "validation": report}
            errors = report["errors"]
        messages += [{"role": "assistant", "content": text or "(empty)"},
                     {"role": "user", "content": "Validation failed: " + "; ".join(errors[:10]) +
                      ". Fix these using only the context pack and return the JSON object only."}]
    return None


# --------------------------------------------------------------------------- cache


def _source_hashes() -> dict[str, str]:
    out = {}
    adir = ROOT / "artifacts"
    if adir.exists():
        for f in sorted(adir.rglob("*")):
            if f.is_file() and f.name not in ("ai_cache.json", "MANIFEST.json"):
                out[f"artifacts/{f.relative_to(adir).as_posix()}"] = hashlib.sha256(f.read_bytes()).hexdigest()
    edir = ROOT / "engine"
    for f in sorted(edir.rglob("*")):
        if f.is_file() and f.suffix in (".py", ".md") and "__pycache__" not in f.parts:
            out[f"engine/{f.relative_to(edir).as_posix()}"] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def fingerprint(question: str, habitat_key: str, context_ids: Iterable[str] = ()) -> str:
    body = {"q": _norm(question), "h": habitat_key, "ids": sorted(context_ids or []),
            "src": _source_hashes(), "prompt": PROMPT_VERSION}
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def _habitat_key(habitat: str | dict | None) -> str:
    if habitat is None or isinstance(habitat, str):
        return str(habitat)
    h = ctx.resolve_habitat(habitat)
    return h["preset_id"] or canonical_json({k: h[k] for k in ctx.HABITAT_FIELDS})


def load_cache(path: Path | None = None) -> dict:
    p = path or CACHE_PATH
    if not p.exists():
        return {"entries": []}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return {"entries": []}


def _default_habitat(question: str, context_ids: Iterable[str] = ()) -> tuple[str | dict, str]:
    """(habitat, cache key) used when the caller gives no habitat.

    Incident questions use the first named incident: its own conditions when in scope, else the habitat
    inferred from the question; the cache key is ``incident:<id>`` either way.
    """
    for inc in ctx.find_incidents(question, context_ids):
        hab = ctx.incident_habitat(inc)
        return (hab if hab is not None else infer_habitat(question)), f"incident:{inc['id']}"
    pid = infer_habitat(question)
    return pid, pid


def _cache_habitat_key(question: str, habitat: Any, context_ids: Iterable[str] = ()) -> str:
    return _default_habitat(question, context_ids)[1] if habitat is None else _habitat_key(habitat)


def _from_cache(question: str, habitat: Any, context_ids: Iterable[str]) -> dict | None:
    entries = load_cache().get("entries") or []
    hk = _cache_habitat_key(question, habitat, context_ids)
    cands = [e for e in entries if e.get("question_key") == _norm(question) and e.get("habitat") == hk]
    if not cands:
        return None
    fp = fingerprint(question, hk, context_ids)
    for e in cands:
        if e.get("fingerprint") == fp:
            return e
    return None


# --------------------------------------------------------------------------- main entry


def ask(question: str, habitat: str | dict | None = None, context_ids: Iterable[str] | None = None,
        *, use_cache: bool = True, allow_claude: bool = True) -> dict:
    question = (question or "").strip()
    if not question:
        raise ValueError("question is required")
    context_ids = [str(c) for c in (context_ids or [])]
    intent = classify(question, context_ids)
    metric = _metric_in(question, context_ids)

    if use_cache:
        hit = _from_cache(question, habitat, context_ids)
        if hit is not None:
            return {"answer_markdown": hit["answer_markdown"], "citations": hit["citations"],
                    "numbers_used": hit["numbers_used"], "validated": hit["validated"], "mode": "cached",
                    "intent": hit.get("intent", intent), "habitat": hit["habitat"],
                    "validation": hit.get("validation"), "prompt_version": PROMPT_VERSION}

    if habitat is None:
        habitat = _default_habitat(question, context_ids)[0]
    pack = ctx.build_context(habitat, question=question, context_ids=context_ids,
                             metrics=None)
    hab_out = pack["habitat"].get("preset_id") or pack["habitat"].get("label")

    if intent != "refusal" and allow_claude and claude_available():
        res = claude_answer(question, pack)
        if res is not None:
            return {"answer_markdown": res["answer_markdown"], "citations": res["validation"]["citations"] and
                    [c["id"] for c in res["validation"]["citations"]], "numbers_used": res.get("numbers_used") or [],
                    "validated": True, "mode": "claude", "intent": intent, "habitat": hab_out,
                    "validation": res["validation"], "prompt_version": PROMPT_VERSION}

    text = template_answer(question, pack, intent, metric)
    report = validate(text, pack)
    return {"answer_markdown": text, "citations": [c["id"] for c in report["citations"]],
            "numbers_used": [n["value"] for n in report["numbers"]], "validated": report["ok"],
            "mode": "template", "intent": intent, "habitat": hab_out, "validation": report,
            "prompt_version": PROMPT_VERSION}


def build_cache(path: Path | None = None, questions: list[tuple[str, str | None]] | None = None) -> dict:
    entries = []
    for q, hab in questions or DEMO_QUESTIONS:
        res = ask(q, hab, use_cache=False)
        hk = _cache_habitat_key(q, hab)
        entries.append({"question": q, "question_key": _norm(q), "habitat": hk,
                        "fingerprint": fingerprint(q, hk), "intent": res["intent"],
                        "mode_generated": res["mode"], "answer_markdown": res["answer_markdown"],
                        "citations": res["citations"], "numbers_used": res["numbers_used"],
                        "validated": res["validated"], "validation": res["validation"]})
    data = {"version": PROMPT_VERSION, "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "generated_by": "python -m engine.ai.answer --build-cache", "entries": entries}
    p = path or CACHE_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return data


def main(argv: list[str] | None = None) -> None:  # pragma: no cover - CLI
    ap = argparse.ArgumentParser(description="Gravity Gap grounded Q&A")
    ap.add_argument("question", nargs="?")
    ap.add_argument("--habitat", default=None)
    ap.add_argument("--build-cache", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    a = ap.parse_args(argv)
    # Windows consoles (cp1252) can't print "CO₂"; never let logging crash the cache build.
    reconfigure = getattr(__import__("sys").stdout, "reconfigure", None)
    if reconfigure:
        reconfigure(errors="replace")
    if a.build_cache:
        data = build_cache()
        for e in data["entries"]:
            print(f"{'OK ' if e['validated'] else 'BAD'} [{e['mode_generated']}] {e['question']}")
            if not e["validated"]:
                print("    " + "; ".join(e["validation"]["errors"]))
        return
    if not a.question:
        ap.error("question or --build-cache required")
    res = ask(a.question, a.habitat, use_cache=not a.no_cache)
    print(res["answer_markdown"])
    print(json.dumps({k: res[k] for k in ("mode", "validated", "citations")}, ensure_ascii=False))
    if not res["validated"]:
        print("errors:", res["validation"]["errors"])


if __name__ == "__main__":  # pragma: no cover
    main()
