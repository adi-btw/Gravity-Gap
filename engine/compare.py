"""S4 side-by-side habitat compare (plan/15-round-3-features.md §S4).

Contract: plan/contracts.md "Round 3 · S4 Compare addendum".

``compare(a, b)`` runs ``engine.bounds.predict`` for M1-M5 at two habitats and adds a ``diff`` per metric plus a
one-line plain-language ``summary`` built by rule (no LLM). An estimate change is only reported when BOTH sides
are covered: a number is never subtracted from "no evidence".
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from engine import bounds
from engine.presets import PRESETS, PRESETS_BY_ID

HABITAT_FIELDS = ("g_m_s2", "p_psia", "o2", "u_cm_s", "L_mm")
FIELD_INFO = {
    "g_m_s2": ("gravity", "m/s²"),
    "p_psia": ("pressure", "psia"),
    "o2": ("O₂", "%"),
    "u_cm_s": ("vent speed", "cm/s"),
    "L_mm": ("flame size", "mm"),
}
REGIMES = ("forced", "mixed", "buoyant")
REGIME_WORDS = {"forced": "forced flow", "mixed": "mixed", "buoyant": "buoyancy-dominated"}
SIDE_FIELDS = ("applicable", "reason", "estimate", "band90", "regime_fractions", "transfer", "n_train",
               "model_version")

PredictFn = Callable[[dict, str], dict]


# ------------------------------------------------------------------- helpers
def fmt(x: Any) -> str:
    """3 significant figures, plain decimal (same rule as engine.ai.answer.fmt)."""
    if isinstance(x, str):
        return x.replace("_", " ")
    x = float(x)
    if x == 0:
        return "0"
    if abs(x) >= 100:
        return str(round(x))
    d = max(0, 2 - math.floor(math.log10(abs(x))))
    s = f"{x:.{d}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def fmt_value(kind: str | None, unit: str | None, x: Any) -> str:
    """Probabilities (and M5 fractions) as %, quantities with their unit, categories as words."""
    if isinstance(x, str):
        return fmt(x)
    if kind == "probability" or unit in ("probability", "fraction"):
        return f"{fmt(float(x) * 100)}%"
    return f"{fmt(x)} {unit}" if unit and unit != "category" else fmt(x)


def fmt_input(field: str, v: float) -> str:
    return f"{fmt(v * 100)}%" if field == "o2" else f"{fmt(v)} {FIELD_INFO[field][1]}"


def resolve(h: str | dict) -> dict:
    """Preset id or habitat dict -> {preset_id, label, g_m_s2, p_psia, o2, u_cm_s, L_mm}."""
    if isinstance(h, str):
        if h not in PRESETS_BY_ID:
            raise ValueError(f"unknown habitat preset {h!r}; known: {sorted(PRESETS_BY_ID)}")
        p = PRESETS_BY_ID[h]
        return {"preset_id": p["id"], "label": p["label"], **{k: float(p[k]) for k in HABITAT_FIELDS}}
    hab = dict(h)
    pid = hab.get("preset_id")
    if pid in PRESETS_BY_ID:
        for k in HABITAT_FIELDS:
            hab.setdefault(k, PRESETS_BY_ID[pid][k])
    hab.setdefault("L_mm", 10.0)
    missing = [k for k in HABITAT_FIELDS if hab.get(k) is None]
    if missing:
        raise ValueError(f"habitat is missing {missing}")
    out = {k: float(hab[k]) for k in HABITAT_FIELDS}
    for p in PRESETS:
        if all(math.isclose(out[k], float(p[k]), rel_tol=1e-9, abs_tol=1e-12) for k in HABITAT_FIELDS):
            return {"preset_id": p["id"], "label": str(hab.get("label") or p["label"]), **out}
    return {"preset_id": None, "label": str(hab.get("label") or "Custom habitat"), **out}


def dominant_regime(fr: dict | None) -> str | None:
    if not fr:
        return None
    vals = [(fr.get(r) if isinstance(fr.get(r), (int, float)) else -1.0) for r in REGIMES]
    if max(vals) < 0:
        return None
    return REGIMES[vals.index(max(vals))]


def _side(pred: dict) -> dict:
    out = {k: pred.get(k) for k in SIDE_FIELDS}
    out["applicable"] = bool(pred.get("applicable"))
    out["regime"] = dominant_regime(pred.get("regime_fractions"))
    return out


def _same(a: Any, b: Any) -> bool:
    return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-12)


def metric_diff(metric: str, label_a: str, label_b: str, sa: dict, sb: dict) -> dict:
    cov_a, cov_b = sa["applicable"], sb["applicable"]
    change = {(True, True): "both", (False, False): "neither", (True, False): "lost", (False, True): "gained"}
    diff = {
        "regime": {"a": sa["regime"], "b": sb["regime"], "changed": sa["regime"] != sb["regime"]},
        "coverage": {"a": cov_a, "b": cov_b, "change": change[(cov_a, cov_b)]},
        "estimate": None,
        "estimate_note": None,
        "band_width": None,
    }
    if not (cov_a and cov_b) or sa["estimate"] is None or sb["estimate"] is None:
        if not (cov_a or cov_b):
            diff["estimate_note"] = f"No difference shown: neither habitat has evidence for {metric}."
        else:
            diff["estimate_note"] = f"No difference shown: {label_b if cov_a else label_a} has no evidence for {metric}."
        return diff
    ea, eb = sa["estimate"], sb["estimate"]
    if isinstance(ea, str) or isinstance(eb, str):
        diff["estimate"] = {"a": ea, "b": eb, "delta": None, "direction": "same" if ea == eb else "changed"}
    else:
        same = _same(ea, eb)
        diff["estimate"] = {"a": ea, "b": eb, "delta": 0.0 if same else float(eb) - float(ea),
                            "direction": "same" if same else ("higher" if eb > ea else "lower")}
        ba, bb = sa["band90"], sb["band90"]
        if ba and bb and all(isinstance(v, (int, float)) for v in (*ba, *bb)):
            wa, wb = float(ba[1]) - float(ba[0]), float(bb[1]) - float(bb[0])
            diff["band_width"] = {"a": wa, "b": wb,
                                  "direction": "same" if _same(wa, wb) else ("wider" if wb > wa else "narrower")}
    return diff


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _plural(metrics: list[str], one: str, many: str) -> str:
    return f"{_join(metrics)} {one if len(metrics) == 1 else many}"


def build_summary(a: dict, b: dict, inputs_diff: list[dict], rows: list[dict]) -> str:
    la, lb = a["label"], b["label"]
    parts = []
    if inputs_diff:
        changes = [f"{d['label']} {fmt_input(d['field'], d['a'])} → {fmt_input(d['field'], d['b'])}"
                   for d in inputs_diff]
        parts.append(f"Moving from {la} to {lb} changes {_join(changes)}.")
    else:
        parts.append(f"{la} and {lb} have the same inputs.")

    flips: dict[tuple, list[str]] = {}
    for r in rows:
        rg = r["diff"]["regime"]
        if rg["changed"] and rg["a"] and rg["b"]:
            flips.setdefault((rg["a"], rg["b"]), []).append(r["metric"])
    for (ra, rb), ms in flips.items():
        who = "for every metric" if len(ms) == len(rows) else f"for {_join(ms)}"
        parts.append(f"The flame regime changes from {REGIME_WORDS[ra]} to {REGIME_WORDS[rb]} {who}.")

    by_change: dict[str, list[str]] = {}
    for r in rows:
        by_change.setdefault(r["diff"]["coverage"]["change"], []).append(r["metric"])
    if by_change.get("lost"):
        parts.append(f"{_plural(by_change['lost'], 'loses its', 'lose their')} evidence at {lb} (no estimate there).")
    if by_change.get("gained"):
        parts.append(f"{_plural(by_change['gained'], 'gains', 'gain')} evidence at {lb}.")
    if by_change.get("neither"):
        parts.append(f"{_plural(by_change['neither'], 'has', 'have')} no evidence on either side.")

    moves, cats = [], []
    for r in rows:
        est = r["diff"]["estimate"]
        if est is None:
            continue
        va, vb = fmt_value(r["kind"], r["unit"], est["a"]), fmt_value(r["kind"], r["unit"], est["b"])
        if est["delta"] is None:
            cats.append(f"{r['metric']} changes from {va} to {vb}" if est["direction"] == "changed"
                        else f"{r['metric']} stays at {va}")
        elif est["direction"] == "same":
            moves.append(f"{r['metric']} stays at {va}")
        else:
            moves.append(f"{r['metric']} goes from {va} to {vb}")
    if moves:
        parts.append(f"Where both sides have evidence, {_join(moves)}.")
    if cats:
        parts.append(f"{_join(cats)}.")
    for word in ("wider", "narrower"):
        ms = [r["metric"] for r in rows if (r["diff"]["band_width"] or {}).get("direction") == word]
        if ms:
            parts.append(f"The 90% band is {word} at {lb} for {_join(ms)}.")
    return " ".join(parts)


def _default_predict(n: int, seed: int) -> PredictFn:
    def fn(h: dict, metric: str) -> dict:
        return bounds.predict(metric, **{k: h[k] for k in HABITAT_FIELDS}, n=n, seed=seed)
    return fn


# ------------------------------------------------------------------- main entry
def compare(a: str | dict, b: str | dict, n: int = 2000, seed: int = 0,
            predict_fn: PredictFn | None = None) -> dict:
    """Compare two habitats metric by metric (contract shape, JSON-safe)."""
    ha, hb = resolve(a), resolve(b)
    predict = predict_fn or _default_predict(n, seed)
    inputs_diff = [
        {"field": k, "label": FIELD_INFO[k][0], "unit": FIELD_INFO[k][1], "a": ha[k], "b": hb[k]}
        for k in HABITAT_FIELDS if not _same(ha[k], hb[k])
    ]
    if ha["label"] == hb["label"] and inputs_diff:  # two different habitats must not read the same
        ha, hb = {**ha, "label": f"{ha['label']} (A)"}, {**hb, "label": f"{hb['label']} (B)"}
    rows = []
    versions = {}
    for metric, meta in bounds.METRICS.items():
        pa, pb = predict(ha, metric), predict(hb, metric)
        sa, sb = _side(pa), _side(pb)
        rows.append({
            "metric": metric,
            "label": pa.get("label") or meta["label"],
            "unit": pa.get("unit") or meta["unit"],
            "kind": pa.get("kind") or meta["kind"],
            "a": sa,
            "b": sb,
            "diff": metric_diff(metric, ha["label"], hb["label"], sa, sb),
        })
        versions[metric] = pa.get("model_version")
    return bounds.json_safe({
        "a": ha,
        "b": hb,
        "inputs_diff": inputs_diff,
        "metrics": rows,
        "summary": build_summary(ha, hb, inputs_diff, rows),
        "model_versions": versions,
    })
