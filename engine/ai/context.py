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
* ``suppression`` R2 curves ``{diluent: trimmed engine.suppression.curve(...)}`` for questions about putting
  a flame out with CO2 / helium (or ``context_ids`` with ``eng:suppression:co2``) -> cite ``[eng:suppression:co2]``
  (+ ``[PSI-69]``, the FLEX tests behind M1/M2); ``suppression_reference`` holds the empirical FLEX rows of
  ``artifacts/suppression_reference.json`` in the habitat's O2 band     -> cite ``[eng:suppression_reference]``
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
SUPPRESSION_DIR = ARTIFACTS / "suppression"
SUPPRESSION_REFERENCE_PATH = ARTIFACTS / "suppression_reference.json"

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


# --------------------------------------------------------------------------- suppression (R2)

SUPPRESSION_DILUENTS = ("co2", "he")
SUPPRESSION_WORDS = ("suppress", "extinguish", "put out", "put it out", "putting out", "snuff", "diluent",
                     "dilution", "dilute", "inert gas", "carbon dioxide", "co2", "co₂", "helium")
SUPPRESSION_POINT_FIELDS = ("applicable", "estimate", "band90", "reason")
SUPPRESSION_REFERENCE_ROWS = 12


def wants_suppression(question: str, context_ids: Iterable[str] = ()) -> bool:
    """True for questions about putting a flame out with CO2 / helium dilution (R2)."""
    if any(str(c).startswith("eng:suppression") or str(c) == "suppression" for c in context_ids or ()):
        return True
    q = (question or "").lower()
    return any(w in q for w in SUPPRESSION_WORDS)


def suppression_diluents(question: str, context_ids: Iterable[str] = ()) -> list[str]:
    """Diluents a suppression question is about: both when it compares them, CO2 by default."""
    q = (question or "").lower()
    ids = {str(c) for c in context_ids or ()}
    out = [d for d in SUPPRESSION_DILUENTS if f"eng:suppression:{d}" in ids]
    if any(w in q for w in ("co2", "co₂", "carbon dioxide")) and "co2" not in out:
        out.append("co2")
    if "helium" in q and "he" not in out:
        out.append("he")
    if any(w in q for w in ("better", "compare", "versus", " vs", "which diluent", "which gas")):
        out = list(dict.fromkeys(out + list(SUPPRESSION_DILUENTS)))
    return out or ["co2"]


def _suppression_artifact(preset_id: str, diluent: str) -> dict | None:
    f = SUPPRESSION_DIR / f"{preset_id}_{diluent}.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return None


def suppression_curve(h: dict, diluent: str) -> dict | None:
    """engine.suppression.curve output (preset artifact first); None when the engine is not available."""
    if h.get("preset_id"):
        art = _suppression_artifact(h["preset_id"], diluent)
        if art is not None:
            return art
    mod = _engine("suppression")
    if mod is None or not hasattr(mod, "curve"):
        return None
    return mod.curve(diluent, **_inputs(h))


def trim_suppression(curve: dict, diluent: str) -> dict:
    pts = []
    for p in curve.get("points") or []:
        item = {"fraction": p.get("fraction")}
        for m in ("M1", "M2"):
            if isinstance(p.get(m), dict):
                item[m] = {k: p[m].get(k) for k in SUPPRESSION_POINT_FIELDS}
        pts.append(item)
    out = {k: curve.get(k) for k in ("diluent", "label", "dose_for_p90", "tested_o2_range", "gate_note",
                                     "safety_note", "model_version") if k in curve}
    out["diluent"] = out.get("diluent") or diluent
    out["points"] = pts
    tested = [t for t in curve.get("tested") or [] if isinstance(t, dict)]
    out["n_tested"] = int(sum(float(t.get("n") or 0) for t in tested))
    out["id"] = f"eng:suppression:{diluent}"
    return jsonable(out)


def load_suppression_reference(path: Path | None = None) -> Any:
    f = path or SUPPRESSION_REFERENCE_PATH
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return None


_REF_CELL = ("bin", "fraction_lo", "fraction_hi", "n", "extinctions", "completions", "disruptions",
             "extinction_rate", "interval90")
_O2_BAND_IDS = {"le_0.17": (None, 0.17), "0.17_0.22": (0.17, 0.22), "gt_0.22": (0.22, None)}


def _band_bounds(band_id: str, label: str = "") -> tuple[float | None, float | None]:
    if band_id in _O2_BAND_IDS:
        return _O2_BAND_IDS[band_id]
    nums = [float(x) for x in re.findall(r"\d+\.\d+|\d+(?=\s*%)", f"{band_id} {label}")]
    nums = [x / 100 if x > 1 else x for x in nums]
    text = f"{band_id} {label}".lower()
    if len(nums) >= 2:
        return nums[0], nums[1]
    if nums and ("le" in text or "<" in text):
        return None, nums[0]
    if nums and ("gt" in text or ">" in text):
        return nums[0], None
    return None, None


def reference_rows(data: Any, diluent: str) -> list[dict]:
    """Rows ``{fuel, o2_band, o2_lo, o2_hi, bin, fraction_lo, fraction_hi, n, extinctions, ..., trend}``
    for one diluent from ``artifacts/suppression_reference.json``
    (layout ``tables[diluent][fuel][o2_band_id] = {o2_band, n, bins[]}``, engine/suppression_reference.py).
    """
    if not isinstance(data, dict) or not isinstance(data.get("tables"), dict):
        return []
    fuels = data["tables"].get(diluent) or {}
    trends = (data.get("trend") or {}).get(diluent) or {}
    rows: list[dict] = []
    for fuel, bands in fuels.items():
        if not isinstance(bands, dict):
            continue
        for band_id, cell in bands.items():
            if not isinstance(cell, dict):
                continue
            lo, hi = _band_bounds(str(band_id), str(cell.get("o2_band") or ""))
            direction = ((trends.get(fuel) or {}).get(band_id) or {}).get("direction")
            for b in cell.get("bins") or []:
                if not isinstance(b, dict):
                    continue
                row = {"fuel": str(fuel), "o2_band": cell.get("o2_band") or str(band_id), "o2_lo": lo, "o2_hi": hi,
                       **{k: b.get(k) for k in _REF_CELL if k in b}}
                if direction:
                    row["trend"] = direction
                rows.append(row)
    return rows


def _o2_band_match(row: dict, o2: float) -> bool:
    lo, hi = row.get("o2_lo"), row.get("o2_hi")
    return (lo is None or o2 > lo + 1e-9) and (hi is None or o2 <= hi + 1e-9)


def suppression_reference_block(h: dict, diluent: str, path: Path | None = None) -> dict | None:
    """Empirical FLEX rows for ``diluent`` in the habitat's O2 band; None when the artifact is not built."""
    data = load_suppression_reference(path)
    if data is None:
        return None
    rows = [r for r in reference_rows(data, diluent) if _o2_band_match(r, h["o2"])
            and isinstance(r.get("n"), (int, float)) and r["n"] > 0]
    out: dict[str, Any] = {"diluent": diluent, "rows": rows[:SUPPRESSION_REFERENCE_ROWS],
                           "id": "eng:suppression_reference"}
    max_o2 = (data.get("max_diluted_o2_by_diluent") or {}).get(diluent) if isinstance(data, dict) else None
    if isinstance(max_o2, (int, float)):
        out["max_diluted_o2"] = max_o2
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

    # ---- suppression curves (R2)
    supp: dict[str, Any] = {}
    supp_ref: dict[str, Any] = {}
    if wants_suppression(question, ctx_ids):
        for dil in suppression_diluents(question, ctx_ids):
            try:
                cur = suppression_curve(h, dil)
            except Exception as exc:  # noqa: BLE001 - engine errors must not break the pack
                missing.append(f"suppression.curve({dil}): {type(exc).__name__}")
                continue
            if cur is None:
                continue
            supp[dil] = trim_suppression(cur, dil)
            citable.add(supp[dil]["id"])
            ref = suppression_reference_block(h, dil)
            if ref is None:
                if "artifacts/suppression_reference.json" not in missing:
                    missing.append("artifacts/suppression_reference.json")
            elif ref["rows"]:
                supp_ref[dil] = ref
                citable.add(ref["id"])
        if not supp:
            missing.append("engine.suppression")
        else:
            citable.add("PSI-69")  # FLEX: the M1/M2 models behind every suppression curve
    pack["suppression"] = supp
    pack["suppression_reference"] = supp_ref

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
