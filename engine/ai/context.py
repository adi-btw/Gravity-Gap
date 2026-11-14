"""Context pack builder for the grounded AI layer (plan/05-ai-layer.md section 3.1).

``build_context(habitat, question="", context_ids=(), metrics=None) -> pack``

The pack is the *only* source of facts an answer may use. It contains:

* ``habitat``   resolved inputs (+ ``preset_id``/``label`` when they match a preset, ``g_over_g0``)
* ``physics``   ``engine.physics.evaluate`` + Monte Carlo summary         -> cite ``[eng:physics]``
* ``predictions`` ``{metric: trimmed engine.bounds.predict output}``       -> cite ``[eng:M1]``
* ``scenarios`` what-if variants (e.g. ``fans_off``: same habitat, u = 0)  -> cite ``[eng:fans_off:M1]``
* ``planner``   top planner items + ``design_implications``  -> cite ``[eng:planner:1]``, ``[eng:design:1]``
* ``rank``      top-k ranked investigations (``engine.rank``)
* ``records``   trimmed catalog records for the ranked + requested ids    -> cite ``[PSI-69]``, ``[doi:...]``
* ``evidence``  psi_tests.csv rows for the predictions' nearest evidence   -> cite ``[rec:PSI-69:FLEX:12]``
* ``catalog_index`` every catalog id / acronym / DOI (so any real investigation resolves)
* ``incidents`` real-fire replay incidents named in the question / ``context_ids`` (R1), trimmed from
  ``artifacts/incidents.json``                                          -> cite ``[eng:incident:mir1997]``
  and, for sourced facts, the source URL exactly as written in the incident's ``sources``
* ``constants`` physical constants and thresholds the answers may quote
* ``citable_ids`` every id a citation may use
* ``missing``   engine pieces that were unavailable (answers must say so, not guess)

Every engine module is optional: a missing module is recorded in ``missing``.
Precomputed ``artifacts/bounds/{preset}_{metric}.json`` are used when the habitat is a preset.
"""
from __future__ import annotations

import csv
import importlib
import json
import math
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from engine.ledger import jsonable
from engine.ai.validator import CONSTANTS

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts"
CATALOG_PATH = ARTIFACTS / "catalog.json"
PLANNER_PATH = ARTIFACTS / "planner.json"
BOUNDS_DIR = ARTIFACTS / "bounds"
TESTS_CSV = ROOT / "data" / "clean" / "psi_tests.csv"
INCIDENTS_PATH = ARTIFACTS / "incidents.json"

PACK_VERSION = "context.v1"
HABITAT_FIELDS = ("g_m_s2", "p_psia", "o2", "u_cm_s", "L_mm")
TOP_K_RECORDS = 6
EVIDENCE_PER_METRIC = 5
PLANNER_TOP = 5
EVIDENCE_FIELDS = ("record_id", "investigation_id", "investigation", "fuel", "fuel_phase", "gravity",
                   "o2_mole_fraction", "pressure_atm", "flow_speed_cm_s", "size_mm", "outcome",
                   "extinction_diameter_mm")
PRED_FIELDS = ("metric", "label", "unit", "kind", "applicable", "reason", "estimate", "band90",
               "ref_0g", "ref_1g", "regime_fractions", "u_eff_summary", "nonmonotonic_flag",
               "nonmonotonic_note", "transfer", "sensitivity", "n_train", "model_version", "inputs")


# --------------------------------------------------------------------------- loaders


def _engine(name: str):
    try:
        return importlib.import_module(f"engine.{name}")
    except Exception:  # noqa: BLE001 - any import failure means "not available"
        return None


@lru_cache(maxsize=1)
def load_catalog() -> list[dict]:
    if not CATALOG_PATH.exists():
        return []
    return list(json.loads(CATALOG_PATH.read_text(encoding="utf-8")).get("investigations", []))


@lru_cache(maxsize=1)
def load_planner() -> dict | None:
    if not PLANNER_PATH.exists():
        return None
    data = json.loads(PLANNER_PATH.read_text(encoding="utf-8"))
    if isinstance(data, list):
        data = {"tests": data, "design_implications": []}
    return data


@lru_cache(maxsize=1)
def _tests_index() -> dict[str, dict]:
    if not TESTS_CSV.exists():
        return {}
    out: dict[str, dict] = {}
    with TESTS_CSV.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out[row["record_id"]] = {k: row.get(k) for k in EVIDENCE_FIELDS}
    return out


def _num(v: Any) -> Any:
    if v in (None, ""):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return f if math.isfinite(f) else None


def evidence_row(record_id: str) -> dict | None:
    row = _tests_index().get(record_id)
    if row is None:
        return None
    out = {}
    for k, v in row.items():
        if v in (None, ""):
            continue
        out[k] = _num(v) if k in ("o2_mole_fraction", "pressure_atm", "flow_speed_cm_s", "size_mm",
                                  "extinction_diameter_mm") else v
    return out


# --------------------------------------------------------------------------- incidents (R1)

INCIDENT_FIELDS = ("id", "name", "date", "phase", "in_scope", "scope_note", "g_m_s2", "p_psia", "o2", "u_cm_s",
                   "L_mm", "assumed", "assumed_note", "summary", "sources", "physics", "regime_fractions", "metrics", "coverage",
                   "findings")
# Extra names people use for the incidents (matched as whole words, case-insensitive).
INCIDENT_ALIASES: dict[str, tuple[str, ...]] = {
    "apollo1": ("apollo 1", "apollo-1", "apollo i", "as-204", "as 204"),
    "mir1997": ("mir",),
    "artemis2": ("artemis ii", "artemis 2", "artemis-2"),
    "apollo13": ("apollo 13", "apollo-13", "apollo xiii"),
}


def load_incidents(path: Path | None = None) -> list[dict]:
    """Incidents from ``artifacts/incidents.json`` (empty list when not built). Read each call: the file is small."""
    f = path or INCIDENTS_PATH
    if not f.exists():
        return []
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return []
    items = data.get("incidents") if isinstance(data, dict) else data
    return [i for i in (items or []) if isinstance(i, dict) and i.get("id")]


def _alias_patterns(inc: dict) -> list[str]:
    names = {str(inc["id"]).lower()}
    name = str(inc.get("name") or "").strip().lower()
    if name:
        names.add(name)
        names.add(re.sub(r"\s*\(.*?\)\s*", " ", name).strip())
    names.update(INCIDENT_ALIASES.get(str(inc["id"]), ()))
    pats = []
    for n in sorted((n for n in names if n), key=len, reverse=True):
        words = [re.escape(w) for w in re.split(r"[\s-]+", n) if w]
        pats.append(r"(?<![\w-])" + r"[\s-]*".join(words) + r"(?![\w-])")
    return pats


def find_incidents(question: str, context_ids: Iterable[str] = (), incidents: list[dict] | None = None) -> list[dict]:
    """Incidents named in the question (by id, name or alias) or listed in ``context_ids``.

    ``context_ids`` may hold ``"mir1997"``, ``"incident:mir1997"`` or ``"eng:incident:mir1997"``.
    """
    incs = load_incidents() if incidents is None else incidents
    q = (question or "").lower()
    ids = {str(c).split(":")[-1] for c in context_ids or ()}
    out = []
    for inc in incs:
        if str(inc["id"]) in ids or any(re.search(p, q) for p in _alias_patterns(inc)):
            out.append(inc)
    return out


def incident_habitat(inc: dict) -> dict | None:
    """The incident's conditions as a habitat dict, or None (out of scope / values missing)."""
    if not inc.get("in_scope"):
        return None
    vals = {k: inc.get(k) for k in HABITAT_FIELDS}
    if any(not isinstance(vals[k], (int, float)) or isinstance(vals[k], bool) for k in HABITAT_FIELDS[:4]):
        return None
    if not isinstance(vals["L_mm"], (int, float)):
        vals["L_mm"] = 10.0
    return {**{k: float(v) for k, v in vals.items()}, "label": str(inc.get("name") or inc["id"])}


def trim_incident(inc: dict) -> dict:
    out = {k: inc.get(k) for k in INCIDENT_FIELDS if k in inc}
    out["incident_id"] = out.pop("id")
    date = str(inc.get("date") or "")
    if re.match(r"^\d{4}", date):
        out["year"] = int(date[:4])
    out["id"] = f"eng:incident:{inc['id']}"
    return jsonable(out)


def presets() -> list[dict]:
    mod = _engine("presets")
    return list(getattr(mod, "PRESETS", [])) if mod else []


def metrics_catalog() -> dict[str, dict]:
    mod = _engine("bounds")
    return dict(getattr(mod, "METRICS", {}) or {}) if mod else {}


# --------------------------------------------------------------------------- habitat


def resolve_habitat(habitat: str | dict | None) -> dict:
    """Preset id or dict of inputs -> full habitat dict (preset_id when it matches a preset)."""
    plist = presets()
    by_id = {p["id"]: p for p in plist}
    if habitat is None:
        habitat = "lunar_base"
    if isinstance(habitat, str):
        if habitat not in by_id:
            raise ValueError(f"unknown habitat preset '{habitat}'")
        p = by_id[habitat]
        return {"preset_id": p["id"], "label": p["label"], **{k: float(p[k]) for k in HABITAT_FIELDS}}
    hab = dict(habitat)
    pid = hab.get("preset_id") or hab.get("id")
    if pid in by_id:
        base = by_id[pid]
        for k in HABITAT_FIELDS:
            hab.setdefault(k, base[k])
    missing = [k for k in HABITAT_FIELDS[:4] if k not in hab]
    if missing:
        raise ValueError(f"habitat is missing {missing}")
    hab.setdefault("L_mm", 10.0)
    out = {k: float(hab[k]) for k in HABITAT_FIELDS}
    for p in plist:
        if all(math.isclose(out[k], float(p[k]), rel_tol=1e-9, abs_tol=1e-12) for k in HABITAT_FIELDS):
            return {"preset_id": p["id"], "label": p["label"], **out}
    return {"preset_id": None, "label": str(hab.get("label") or "Custom habitat"), **out}


def _inputs(h: dict) -> dict:
    return {k: h[k] for k in HABITAT_FIELDS}


# --------------------------------------------------------------------------- engine calls


def physics_block(h: dict) -> dict | None:
    phys, mc = _engine("physics"), _engine("montecarlo")
    if phys is None:
        return None
    out = dict(phys.evaluate(**_inputs(h)))
    if mc is not None:
        raw = mc.sample_physics(**_inputs(h), n=2000, seed=0)
        out["mc"] = {**{k: v for k, v in (raw.get("summary") or {}).items() if k != "regime_fractions"},
                     "regime_fractions": raw.get("regime_fractions")}
    out["id"] = "eng:physics"
    return jsonable(out)


def _bounds_artifact(preset_id: str, metric: str) -> dict | None:
    f = BOUNDS_DIR / f"{preset_id}_{metric}.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            return None
    return None


@lru_cache(maxsize=256)
def _predict_cached(metric: str, inputs: tuple) -> dict | None:
    mod = _engine("bounds")
    if mod is None or not hasattr(mod, "predict"):
        return None
    return jsonable(mod.predict(metric, **dict(inputs)))


def prediction(h: dict, metric: str) -> dict | None:
    """Full bounds.predict output (artifact for presets, live otherwise); None when unavailable."""
    if h.get("preset_id"):
        art = _bounds_artifact(h["preset_id"], metric)
        if art is not None:
            return art
    return _predict_cached(metric, tuple(sorted(_inputs(h).items())))


def trim_prediction(pred: dict, cite_id: str) -> dict:
    out = {k: pred.get(k) for k in PRED_FIELDS if k in pred}
    out["evidence_ids"] = [e.get("record_id") for e in (pred.get("evidence") or [])][:EVIDENCE_PER_METRIC]
    out["evidence_investigations"] = sorted({e.get("investigation_id") for e in (pred.get("evidence") or [])
                                             if e.get("investigation_id")})
    out["id"] = cite_id
    return out


def _trim_record(rec: dict) -> dict:
    keep = ("id", "acronym", "title", "doi", "platform", "fuel_phase", "gravity_levels", "ground_reference",
            "conditions", "n_tests", "outcomes_available", "hazard_pillars", "is_combustion")
    out = {k: rec.get(k) for k in keep}
    out["publications"] = [{"doi": p.get("doi"), "title": p.get("title")}
                           for p in (rec.get("publications") or []) if p.get("doi")][:3]
    return out


# --------------------------------------------------------------------------- pack


def _wants_fans_off(question: str) -> bool:
    q = question.lower()
    return any(s in q for s in ("fans off", "fan off", "fans are off", "no ventilation", "vent off",
                                "ventilation off", "without ventilation", "still air", "fans turned off"))


def build_context(
    habitat: str | dict | None,
    question: str = "",
    context_ids: Iterable[str] = (),
    metrics: Iterable[str] | None = None,
) -> dict:
    h = resolve_habitat(habitat)
    h["g_over_g0"] = h["g_m_s2"] / CONSTANTS["g_earth_m_s2"]
    h["o2_percent"] = h["o2"] * 100.0
    ctx_ids = [str(c) for c in (context_ids or [])]
    missing: list[str] = []
    citable: set[str] = set()

    pack: dict[str, Any] = {"version": PACK_VERSION, "habitat": h, "question": question}

    phys = physics_block(h)
    if phys is None:
        missing.append("engine.physics")
    else:
        citable.add("eng:physics")
    pack["physics"] = phys

    # ---- predictions
    known = metrics_catalog()
    if not known:
        missing.append("engine.bounds")
    wanted = list(metrics) if metrics is not None else list(known)
    for c in ctx_ids:
        if c in known and c not in wanted:
            wanted.append(c)
    preds: dict[str, dict] = {}
    raw_preds: dict[str, dict] = {}
    for m in wanted:
        if m not in known:
            continue
        try:
            p = prediction(h, m)
        except Exception as exc:  # noqa: BLE001 - engine errors must not break the pack
            missing.append(f"bounds.predict({m}): {type(exc).__name__}")
            continue
        if p is None:
            continue
        raw_preds[m] = p
        preds[m] = trim_prediction(p, f"eng:{m}")
        citable.add(f"eng:{m}")
    pack["metrics"] = {k: {"label": v.get("label"), "unit": v.get("unit"), "kind": v.get("kind"),
                           "flow_dependent": v.get("flow_dependent")} for k, v in known.items()}
    pack["predictions"] = preds

    # ---- what-if scenarios
    scenarios: dict[str, Any] = {}
    if _wants_fans_off(question) and h["u_cm_s"] > 0:
        h0 = {**h, "u_cm_s": 0.0, "preset_id": None, "label": f"{h['label']} with fans off"}
        sc: dict[str, Any] = {"habitat": {k: h0[k] for k in HABITAT_FIELDS}, "label": h0["label"]}
        ph0 = physics_block(h0)
        if ph0 is not None:
            ph0["id"] = "eng:fans_off:physics"
            citable.add("eng:fans_off:physics")
        sc["physics"] = ph0
        sc["predictions"] = {}
        for m in preds:
            try:
                p0 = _predict_cached(m, tuple(sorted(_inputs(h0).items())))
            except Exception:  # noqa: BLE001
                p0 = None
            if p0 is not None:
                sc["predictions"][m] = trim_prediction(p0, f"eng:fans_off:{m}")
                citable.add(f"eng:fans_off:{m}")
        scenarios["fans_off"] = sc
    pack["scenarios"] = scenarios

    # ---- planner
    plan = load_planner()
    if plan is None:
        missing.append("artifacts/planner.json")
        pack["planner"] = []
        pack["design_implications"] = []
    else:
        tests = list(plan.get("tests") or plan.get("items") or [])[:PLANNER_TOP]
        items = []
        for i, t in enumerate(tests, start=1):
            rank_no = t.get("rank", i)
            item = {k: t.get(k) for k in ("rank", "g_m_s2", "p_psia", "o2", "u_cm_s", "metric", "score",
                                          "parts", "rationale", "extends") if k in t}
            item["id"] = f"eng:planner:{rank_no}"
            citable.add(item["id"])
            items.append(item)
        pack["planner"] = items
        pack["design_implications"] = list(plan.get("design_implications") or [])
        for i in range(len(pack["design_implications"])):
            citable.add(f"eng:design:{i + 1}")

    # ---- catalog, rank, records
    catalog = load_catalog()
    if not catalog:
        missing.append("artifacts/catalog.json")
    pack["catalog_index"] = [{"id": r.get("id"), "acronym": r.get("acronym"), "doi": r.get("doi")}
                             for r in catalog]
    for r in catalog:
        citable.add(str(r.get("id")))
        if r.get("doi"):
            citable.add(f"doi:{r['doi']}")
    rank_mod = _engine("rank")
    ranked: list[dict] = []
    if rank_mod is not None and catalog:
        try:
            ranked = rank_mod.rank(catalog, h["g_m_s2"], h["p_psia"], h["o2"], h["u_cm_s"])
        except Exception:  # noqa: BLE001
            missing.append("engine.rank")
    pack["rank"] = [jsonable({"id": r["id"], "acronym": r.get("acronym"), "score": r.get("score"),
                              "parts": r.get("parts")}) for r in ranked[:TOP_K_RECORDS]]
    want_ids: list[str] = [r["id"] for r in pack["rank"]]
    for p in preds.values():
        want_ids.extend(p.get("evidence_investigations") or [])
    want_ids.extend(c for c in ctx_ids if c.startswith("PSI-"))
    by_id = {r.get("id"): r for r in catalog}
    records = []
    for rid in dict.fromkeys(want_ids):
        if rid in by_id:
            tr = _trim_record(by_id[rid])
            records.append(tr)
            for pub in tr["publications"]:
                citable.add(f"doi:{pub['doi']}")
    pack["records"] = jsonable(records)

    # ---- evidence rows
    ev_ids: list[str] = []
    for p in preds.values():
        ev_ids.extend(e for e in (p.get("evidence_ids") or []) if e)
    ev_ids.extend(c[4:] if c.startswith("rec:") else c for c in ctx_ids
                  if c.startswith("rec:") or c.count(":") >= 2)
    evidence = []
    for rid in dict.fromkeys(ev_ids):
        row = evidence_row(rid)
        if row is not None:
            row["id"] = f"rec:{rid}"
            citable.add(row["id"])
            evidence.append(row)
    pack["evidence"] = evidence

    # ---- real-fire replay incidents (R1)
    incs = [trim_incident(i) for i in find_incidents(question, ctx_ids)]
    for inc in incs:
        citable.add(inc["id"])
        for src in inc.get("sources") or []:
            if isinstance(src, dict) and src.get("url"):
                citable.add(str(src["url"]).strip())
    pack["incidents"] = incs

    pack["constants"] = dict(CONSTANTS)
    pack["missing"] = missing
    pack["citable_ids"] = sorted(citable)
    return jsonable(pack)


def record_by_id(pack: dict, rid: str) -> dict | None:
    for r in pack.get("records") or []:
        if r.get("id") == rid:
            return r
    for r in pack.get("catalog_index") or []:
        if r.get("id") == rid:
            return r
    return None
