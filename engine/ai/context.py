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
* ``detection`` R3 detection evidence (``artifacts/detection.json``, reduced scope, ADR-0007) for questions about
  smoke, dust, particles or smoke alarms (or ``context_ids`` starting with ``eng:detection``): scope note, gaps,
  size definitions and per-series stats (no raw bins) -> cite ``[eng:detection]``, a series
  ``[eng:detection:psi115_case1_micro]`` or a gap ``[eng:detection:lunar_dust]``; only ids in the artifact resolve
* ``compare`` S4 side-by-side compare of two habitats (``engine.compare.compare``) when the question names two
  presets with a compare cue ("What changes between ISS and the lunar base?") or ``context_ids`` has ``eng:compare``
  -> cite ``[eng:compare]`` (summary) and ``[eng:compare:M1]`` .. ``[eng:compare:M5]`` (only metrics present)
* ``drivers`` S3 band-width budget per covered metric (``engine.uncertainty.drivers``; preset artifacts
  ``artifacts/uncertainty/{preset}.json``, ADR-0008) for questions about why a band is wide (or ``context_ids``
  starting with ``eng:drivers``) -> cite ``[eng:drivers:M1]``; each source carries its share rounded to 5%
  (``share_pct``) and its basis in words
* ``holdout`` S2 honesty test (``artifacts/holdout.json``, ADR-0009) for "how do you know it works / can I trust
  it" questions (or ``context_ids`` starting with ``eng:holdout``): per-metric summaries, the wide check, the worst
  misses (with their PSI rows in ``evidence``) and the SAFFIRE hindcast -> cite ``[eng:holdout]``,
  ``[eng:holdout:<group id>]`` (only the groups in the pack) and ``[eng:holdout:saffire]``
* ``briefing`` S1 habitat fire-safety briefing (``artifacts/briefing/{preset}.json``, else
  ``engine.briefing.briefing``; ADR-0010) for "what should a designer know about fire" / briefing questions (or
  ``context_ids`` with ``eng:briefing``): habitat line, the four pillar chips, key numbers, levers, gaps, next tests,
  history, trust line, disclaimer -> cite ``[eng:briefing]`` and every id in the briefing's own ``citations``
  (``eng:M1``, ``PSI-69``, ``eng:drivers:M1``, ``eng:planner:6``, ``eng:incident:artemis2`` ...)
* ``atmosphere_map`` S5 O2 x pressure evidence map summaries (``artifacts/atmosphere_map/{metric}_{gravity}.json``,
  ADR-0011) for questions about which cabin air the evidence supports (or ``context_ids`` starting with
  ``eng:atmosphere_map`` / ``eng:crew_limit``): per metric the evidence share, the no-evidence share, the reading and
  the preset markers; the cited crew limits -> cite ``[eng:atmosphere_map:M1]`` (metrics present) and
  ``[eng:crew_limit:<id>]`` (ids in the artifact). No cells: the map never ranks atmospheres
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
DETECTION_PATH = ARTIFACTS / "detection.json"
UNCERTAINTY_DIR = ARTIFACTS / "uncertainty"
HOLDOUT_PATH = ARTIFACTS / "holdout.json"
BRIEFING_DIR = ARTIFACTS / "briefing"
ATMOSPHERE_MAP_DIR = ARTIFACTS / "atmosphere_map"

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


# --------------------------------------------------------------------------- habitat compare (S4)

# Preset names in questions (also used by engine.ai.answer.infer_habitat). Longest phrase wins at a position.
HABITAT_WORDS = (("lunar rover", "lunar_rover"), ("rover", "lunar_rover"), ("lunar base", "lunar_base"),
                 ("moon", "lunar_base"), ("lunar", "lunar_base"), ("luci", "lunar_base"),
                 ("mars", "mars_base"), ("iss", "iss"), ("space station", "iss"),
                 ("exploration", "exploration"), ("earth", "earth"))
_HABITAT_RE = re.compile(r"\b(" + "|".join(re.escape(w) for w, _ in sorted(HABITAT_WORDS, key=lambda x: -len(x[0])))
                         + r")\b")
COMPARE_CUES = ("compare", "comparison", "change", "differ", "between", " vs", "versus")


def preset_mentions(question: str) -> list[str]:
    """Distinct preset ids named in the question, in order of appearance."""
    words = dict(HABITAT_WORDS)
    return list(dict.fromkeys(words[m.group(1)] for m in _HABITAT_RE.finditer((question or "").lower())))


def wants_compare(question: str, context_ids: Iterable[str] = ()) -> bool:
    """True when the question compares two named presets, or ``context_ids`` asks for ``eng:compare``."""
    if any(str(c).startswith("eng:compare") for c in context_ids or ()):
        return True
    q = (question or "").lower()
    return len(preset_mentions(q)) >= 2 and any(c in q for c in COMPARE_CUES)


def compare_pair(question: str, h: dict) -> tuple[str | dict, str | dict] | None:
    """(A, B): the first two presets named; with one named preset, A = it and B = the habitat (if different)."""
    names = preset_mentions(question)
    if len(names) >= 2:
        return names[0], names[1]
    if len(names) == 1 and h.get("preset_id") != names[0]:
        return names[0], {k: h[k] for k in (*HABITAT_FIELDS, "preset_id", "label") if k in h}
    return None


def compare_block(a: str | dict, b: str | dict) -> dict | None:
    """``engine.compare.compare`` with the same predictions as ``eng:M1`` (preset artifacts), cite ids attached."""
    mod = _engine("compare")
    if mod is None or not hasattr(mod, "compare"):
        return None
    res = mod.compare(a, b, predict_fn=lambda hab, m: prediction(hab, m))
    out = {"id": "eng:compare", "a": res["a"], "b": res["b"], "inputs_diff": res["inputs_diff"],
           "summary": res["summary"], "metrics": {}}
    for row in res["metrics"]:
        out["metrics"][row["metric"]] = {**row, "id": f"eng:compare:{row['metric']}"}
    return jsonable(out)


# --------------------------------------------------------------------------- detection evidence (R3)

DETECTION_WORDS = ("smoke", "dust", "regolith", "particle", "aerosol", "soot", "alarm", "detector", "detect")
_THRESHOLD_KEY = re.compile(r"^share_of_count_above_(\d+(?:\.\d+)?)um$")


def wants_detection(question: str, context_ids: Iterable[str] = ()) -> bool:
    """True for questions about smoke, dust, particles or smoke alarms (R3 detection evidence)."""
    if any(str(c).startswith("eng:detection") for c in context_ids or ()):
        return True
    q = (question or "").lower()
    return any(re.search(rf"\b{w}", q) for w in DETECTION_WORDS)


def load_detection(path: Path | None = None) -> dict | None:
    f = path or DETECTION_PATH
    if not f.exists():
        return None
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _det_series(s: dict, keep: tuple[str, ...]) -> dict:
    out = {k: s.get(k) for k in keep if k in s}
    out["series_id"] = s.get("id")
    out["id"] = f"eng:detection:{s.get('id')}"
    return out


def detection_block(path: Path | None = None) -> dict | None:
    """Trimmed ``artifacts/detection.json`` (no raw bin arrays); None when the artifact is not built.

    Every cite id is ``eng:detection:<id>`` for a series or gap id that is in the artifact, plus ``eng:detection``.
    """
    data = load_detection(path)
    if data is None:
        return None
    out: dict[str, Any] = {"id": "eng:detection", "title": data.get("title"), "verdict": data.get("verdict"),
                           "scope_note": data.get("scope_note"), "size_definitions": data.get("size_definitions")}
    out["gaps"] = [{"gap_id": g["id"], "text": g.get("text"), "id": f"eng:detection:{g['id']}"}
                   for g in data.get("gaps") or [] if isinstance(g, dict) and g.get("id")]
    common = ("label", "size_definition", "note", "source")
    out["smoke_bins"] = [_det_series(s, common + ("material_label", "run", "variant", "stats"))
                         for s in data.get("smoke_bins") or [] if isinstance(s, dict) and s.get("id")]
    runs = data.get("smoke_runs")
    if isinstance(runs, dict) and runs.get("id"):
        out["smoke_runs"] = _det_series(runs, common + ("by_material",))
    amc = data.get("average_mass_comparison")
    if isinstance(amc, dict):
        comp: dict[str, Any] = {"size_definition": amc.get("size_definition"), "note": amc.get("note")}
        for side, keep in (("smoke", ("label", "source", "range_nm")),
                           ("dust", ("label", "material_text", "source", "assumed_density_g_per_cm3",
                                     "density_note", "points", "range_nm"))):
            if isinstance(amc.get(side), dict) and amc[side].get("id"):
                comp[side] = _det_series(amc[side], keep)
        out["average_mass_comparison"] = comp
    sims = []
    for s in data.get("simulation") or []:
        if not isinstance(s, dict) or not s.get("id"):
            continue
        item = _det_series(s, common + ("case", "case_label", "gravity", "variant", "surrogate", "time_s",
                                        "is_simulation", "stats"))
        for k in (s.get("stats") or {}):
            m = _THRESHOLD_KEY.match(str(k))
            if m:  # the size threshold is part of the stat's name ("share_of_count_above_20um")
                item["share_threshold_um"] = float(m.group(1))
        sims.append(item)
    out["simulation"] = sims
    return jsonable(out)


def detection_cite_ids(block: dict) -> list[str]:
    ids = [block["id"]] + [g["id"] for g in block.get("gaps") or []]
    ids += [s["id"] for s in block.get("smoke_bins") or []] + [s["id"] for s in block.get("simulation") or []]
    if block.get("smoke_runs"):
        ids.append(block["smoke_runs"]["id"])
    for side in ("smoke", "dust"):
        if (block.get("average_mass_comparison") or {}).get(side):
            ids.append(block["average_mass_comparison"][side]["id"])
    return ids


# --------------------------------------------------------------------------- uncertainty drivers (S3)

DRIVER_WORDS = ("band", "wide", "uncertain", "drives", "driver", "lever", "shrink", "narrow")
BASIS_TEXT = {"psi_data": "from limited NASA tests", "honesty_rule": "honesty rule for gravity",
              "engineering_assumption": "engineering assumption, not PSI data"}
DRIVER_METRICS = ("M1", "M2", "M3")


def wants_drivers(question: str, context_ids: Iterable[str] = ()) -> bool:
    """True for questions about why a band is wide / what would shrink it (or ``eng:drivers`` context ids)."""
    if any(str(c).startswith("eng:drivers") for c in context_ids or ()):
        return True
    q = (question or "").lower()
    return any(re.search(rf"\b{w}", q) for w in DRIVER_WORDS)


def share5(x: Any) -> int:
    """Share rounded to 5% (same rounding as the ``engine.uncertainty`` lever text)."""
    return int(5 * round(20 * float(x)))


def _drivers_raw(h: dict, metric: str) -> dict | None:
    if h.get("preset_id"):
        f = UNCERTAINTY_DIR / f"{h['preset_id']}.json"
        if f.exists():
            try:
                d = (json.loads(f.read_text(encoding="utf-8")).get("metrics") or {}).get(metric)
            except ValueError:
                d = None
            if isinstance(d, dict):
                return d
    mod = _engine("uncertainty")
    if mod is None or not hasattr(mod, "drivers"):
        return None
    return mod.drivers(metric, **_inputs(h))


def trim_drivers(d: dict) -> dict:
    cite = d.get("citation") or f"eng:drivers:{d.get('metric')}"
    out: dict[str, Any] = {"id": cite, "metric": d.get("metric"), "label": d.get("label"),
                           "applicable": bool(d.get("applicable")), "rounded_to_pct": 5}
    if not out["applicable"]:
        out["reason"] = d.get("reason")
        return out
    out.update({k: d.get(k) for k in ("kind", "unit", "estimate", "band90", "band_width", "model_band90",
                                       "widen_factor")})
    out["sources"] = [{"source": s.get("id"), "label": s.get("label"), "share": s.get("share"),
                       "share_pct": share5(s.get("share") or 0.0), "basis": s.get("basis"),
                       "basis_text": BASIS_TEXT.get(str(s.get("basis")), str(s.get("basis"))),
                       "reaches_band": s.get("reaches_band")} for s in d.get("sources") or []]
    md = d.get("model_detail") or {}
    out["model_detail"] = {k: md.get(k) for k in ("tests_within_gate", "n_train", "investigation_id", "source")}
    lev = d.get("lever") or {}
    out["lever"] = {"source": lev.get("source"), "share_pct": share5(lev.get("share") or 0.0),
                    "basis_text": BASIS_TEXT.get(str(lev.get("basis")), ""), "text": lev.get("text"),
                    "planner_candidate": lev.get("planner_candidate")}
    return out


def drivers_block(h: dict, metrics: Iterable[str]) -> tuple[dict, list[str]]:
    """``{metric: trimmed drivers}`` for the fitted metrics asked for, plus what failed."""
    out: dict[str, Any] = {}
    missing: list[str] = []
    for m in metrics:
        if m not in DRIVER_METRICS:
            continue
        try:
            d = _drivers_raw(h, m)
        except Exception as exc:  # noqa: BLE001 - engine errors must not break the pack
            missing.append(f"uncertainty.drivers({m}): {type(exc).__name__}")
            continue
        if d is None:
            missing.append("engine.uncertainty")
            break
        out[m] = trim_drivers(jsonable(d))
    return out, missing


# --------------------------------------------------------------------------- holdout honesty test (S2)

HOLDOUT_PATTERNS = (r"how do (?:you|we|i) know", r"\btrust\b", r"\bheld[- ]?out\b", r"\bhold(?:ing)? out\b",
                    r"\bholdout\b", r"\bhonesty test\b", r"\bcalibrat", r"does (?:it|this|the app) work",
                    r"how often .*\b(?:right|correct|hold|inside)\b", r"\bhow (?:accurate|reliable)\b")
HOLDOUT_WORST = 3  # worst misses per metric in the pack (the artifact keeps up to 5)


def wants_holdout(question: str, context_ids: Iterable[str] = ()) -> bool:
    """True for "how do you know it works / can I trust it" questions (or ``eng:holdout`` context ids)."""
    if any(str(c).startswith("eng:holdout") for c in context_ids or ()):
        return True
    q = (question or "").lower()
    return any(re.search(p, q) for p in HOLDOUT_PATTERNS)


def load_holdout(path: Path | None = None) -> dict | None:
    f = path or HOLDOUT_PATH
    if not f.exists():
        return None
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return data if isinstance(data, dict) and isinstance(data.get("metrics"), dict) else None


def _holdout_misses(res: dict, k: int) -> list[dict]:
    by_id = {g.get("id"): g for g in res.get("groups") or [] if isinstance(g, dict)}
    out = []
    for w in ((res.get("summary") or {}).get("worst_misses") or [])[:k]:
        g = by_id.get(w.get("id")) or {}
        out.append({"id": f"eng:holdout:{w.get('id')}", "metric": res.get("metric"),
                    "atmosphere": w.get("atmosphere"), "n_tests": w.get("n_tests"), "band90": w.get("band90"),
                    "observed": w.get("observed"), "gap": w.get("gap"),
                    "psi_rows": [r.get("record_id") for r in g.get("psi_rows") or [] if r.get("record_id")]})
    return out


def _holdout_metric(res: dict, k: int) -> dict:
    s = res.get("summary") or {}
    keep = ("n_groups", "n_tests", "n_skipped", "n_covered", "n_not_covered", "band_coverage", "strict_coverage",
            "no_evidence_justified", "weak_test", "brier_covered", "brier_baseline_covered",
            "tests_inside_band_covered")
    out = {"metric": res.get("metric"), "label": res.get("label"), "kind": res.get("kind"),
           "investigation_id": res.get("investigation_id"), "hit_rule": res.get("hit_rule"),
           **{key: s.get(key) for key in keep if key in s}}
    reasons = sorted({g.get("skip_reason") for g in res.get("groups") or []
                      if isinstance(g, dict) and g.get("status") == "skipped" and g.get("skip_reason")})
    if reasons:
        out["skip_reasons"] = reasons
    out["worst_misses"] = _holdout_misses(res, k)
    return out


def holdout_block(path: Path | None = None) -> dict | None:
    """Summaries of ``artifacts/holdout.json`` (no per-group list except the worst misses); None when not built."""
    data = load_holdout(path)
    if data is None:
        return None
    settings = data.get("settings") or {}
    out: dict[str, Any] = {"id": data.get("citation") or "eng:holdout", "adr": data.get("adr"),
                           "method": data.get("method"), "overall": data.get("overall"),
                           "interval": settings.get("interval"), "weak_below_groups": settings.get("weak_below_groups"),
                           "metrics": {m: _holdout_metric(r, HOLDOUT_WORST)
                                       for m, r in (data.get("metrics") or {}).items() if isinstance(r, dict)}}
    wide = data.get("wide_check")
    if isinstance(wide, dict):
        out["wide_check"] = {"what": wide.get("what"), "overall": wide.get("overall"),
                             "metrics": {m: _holdout_metric(r, 1) for m, r in (wide.get("metrics") or {}).items()
                                         if isinstance(r, dict)}}
    sf = data.get("saffire_hindcast")
    if isinstance(sf, dict) and sf.get("available"):
        base = (sf.get("scores") or {}).get("baseline_always_more_at_1g_capped") or {}
        out["saffire"] = {"id": sf.get("citation") or "eng:holdout:saffire", "metric": sf.get("metric"),
                          "headline": sf.get("headline"), "constant_rule": base, "caveat": sf.get("caveat")}
    return jsonable(out)


def holdout_cite_ids(block: dict) -> list[str]:
    ids = [block["id"]]
    for part in (block, block.get("wide_check") or {}):
        for m in (part.get("metrics") or {}).values():
            ids += [w["id"] for w in m.get("worst_misses") or []]
    if block.get("saffire"):
        ids.append(block["saffire"]["id"])
    return ids


def holdout_psi_rows(block: dict) -> list[str]:
    rows: list[str] = []
    for part in (block, block.get("wide_check") or {}):
        for m in (part.get("metrics") or {}).values():
            for w in m.get("worst_misses") or []:
                rows += w.get("psi_rows") or []
    return list(dict.fromkeys(rows))


# --------------------------------------------------------------------------- habitat briefing (S1)

BRIEFING_PATTERNS = (r"\bbriefing\b", r"\bdesigners?\b", r"\bknow about (?:a )?fires?\b", r"\bone[- ]page\b",
                     r"\bfire[- ]safety summary\b")


def wants_briefing(question: str, context_ids: Iterable[str] = ()) -> bool:
    """True for "what should a habitat designer know about fire" / briefing questions (or ``eng:briefing``)."""
    if any(str(c) == "eng:briefing" for c in context_ids or ()):
        return True
    q = (question or "").lower()
    return any(re.search(p, q) for p in BRIEFING_PATTERNS)


def _briefing_raw(h: dict) -> dict | None:
    if h.get("preset_id"):
        f = BRIEFING_DIR / f"{h['preset_id']}.json"
        if f.exists():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except ValueError:
                pass
    mod = _engine("briefing")
    if mod is None or not hasattr(mod, "briefing"):
        return None
    hab = {k: h[k] for k in HABITAT_FIELDS}
    if h.get("label"):
        hab["label"] = h["label"]
    return mod.briefing(hab)


def briefing_block(h: dict) -> dict | None:
    """The habitat's briefing without build metadata (model hashes, manifest hash); None when unavailable."""
    raw = _briefing_raw(h)
    if not isinstance(raw, dict) or not isinstance(raw.get("verdicts"), list):
        return None
    out = {k: raw.get(k) for k in ("habitat", "verdicts", "key_numbers", "drivers", "gaps", "next_tests", "history",
                                   "trust", "citations")}
    foot = raw.get("footer") or {}
    out["footer"] = {"disclaimer": foot.get("disclaimer"), "date": foot.get("date")}
    out["id"] = raw.get("citation") or "eng:briefing"
    return jsonable(out)


def briefing_cite_ids(block: dict) -> list[str]:
    return list(dict.fromkeys([block["id"], *(block.get("citations") or [])]))


# --------------------------------------------------------------------------- atmosphere evidence map (S5)

MAP_PATTERNS = (r"\bcabin air\b", r"\bair map\b", r"\batmosphere map\b", r"\bevidence map\b",
                r"\bwhich (?:cabin )?atmospheres?\b", r"\bwhat (?:cabin )?(?:air|atmospheres?) does the evidence\b",
                r"\bcrew (?:breathing )?limits?\b")
MAP_METRICS = ("M1", "M2", "M3")
MAP_GRAVITY_IDS = (("orbit", 0.0), ("lunar", 1.62), ("mars", 3.71), ("earth", 9.81))


def wants_atmosphere_map(question: str, context_ids: Iterable[str] = ()) -> bool:
    """True for "which cabin air does the evidence support" questions (or atmosphere-map / crew-limit ids)."""
    if any(str(c).startswith(("eng:atmosphere_map", "eng:crew_limit")) for c in context_ids or ()):
        return True
    q = (question or "").lower()
    return any(re.search(p, q) for p in MAP_PATTERNS)


def map_gravity_id(g_m_s2: float) -> str:
    """The map gravity preset for a habitat gravity; lunar when it matches none (estimates are the same anyway)."""
    for gid, g in MAP_GRAVITY_IDS:
        if math.isclose(float(g_m_s2), g, abs_tol=1e-9):
            return gid
    return "lunar"


def load_atmosphere_map(metric: str, gravity: str, directory: Path | None = None) -> dict | None:
    f = (directory or ATMOSPHERE_MAP_DIR) / f"{metric}_{gravity}.json"
    if not f.exists():
        return None
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return data if isinstance(data, dict) and isinstance(data.get("summary"), dict) else None


def _crew_limit(c: dict) -> dict:
    src = c.get("source") or {}
    out = {"id": c.get("citation"), "label": c.get("label"), "role": c.get("role"), "shape": c.get("shape"),
           "quantity": c.get("quantity"), "caveat": c.get("caveat"), "quote": c.get("quote"),
           "source": {"title": src.get("title"), "id_or_number": src.get("id_or_number")}}
    if c.get("reason"):
        out["reason"] = c["reason"]
    return out


def atmosphere_map_block(h: dict, directory: Path | None = None) -> dict | None:
    """Per-metric summaries of the evidence map at the habitat's gravity (no cells) + the cited crew limits."""
    gid = map_gravity_id(h["g_m_s2"])
    metrics: dict[str, Any] = {}
    crew: dict | None = None
    rule = what_varies = None
    for m in MAP_METRICS:
        d = load_atmosphere_map(m, gid, directory)
        if d is None:
            continue
        g = d.get("gravity") or {}
        overlays = d.get("overlays") or {}
        metrics[m] = {"id": d.get("citation") or f"eng:atmosphere_map:{m}", "metric": m, "label": d.get("label"),
                      "unit": d.get("unit"), "kind": d.get("kind"), "investigation_id": d.get("investigation_id"),
                      "gravity": {k: g.get(k) for k in ("id", "label", "g_m_s2", "widen_factor")},
                      "summary": d.get("summary"), "reading": d.get("reading"),
                      "presets": [{k: p.get(k) for k in ("id", "label", "o2", "p_psia", "on_map", "covered",
                                                         "nearest_distance")}
                                  for p in overlays.get("presets") or []]}
        if crew is None:
            crew = overlays.get("crew_limits")
        rule, what_varies = d.get("rule"), d.get("what_varies")
    if not metrics:
        return None
    out: dict[str, Any] = {"gravity_id": gid, "rule": rule, "what_varies": what_varies, "metrics": metrics,
                           "crew_limits": None}
    if isinstance(crew, dict):
        out["crew_limits"] = {"note": crew.get("note"), "source_file": crew.get("source_file"),
                              "drawn": [_crew_limit(c) for c in crew.get("drawn") or [] if c.get("citation")],
                              "not_drawn": [_crew_limit(c) for c in crew.get("not_drawn") or [] if c.get("citation")]}
    return jsonable(out)


def atmosphere_map_cite_ids(block: dict) -> list[str]:
    ids = [m["id"] for m in block["metrics"].values()]
    crew = block.get("crew_limits") or {}
    ids += [c["id"] for part in ("drawn", "not_drawn") for c in crew.get(part) or []]
    return ids


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

    # ---- holdout honesty test (S2): before the evidence rows so its PSI rows resolve as rec: ids
    hold = None
    if wants_holdout(question, ctx_ids):
        hold = holdout_block()
        if hold is None:
            missing.append("artifacts/holdout.json")
        else:
            citable.update(holdout_cite_ids(hold))

    # ---- evidence rows
    ev_ids: list[str] = []
    for p in preds.values():
        ev_ids.extend(e for e in (p.get("evidence_ids") or []) if e)
    if hold is not None:
        ev_ids.extend(holdout_psi_rows(hold))
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

    # ---- detection evidence (R3)
    det = None
    if wants_detection(question, ctx_ids):
        det = detection_block()
        if det is None:
            missing.append("artifacts/detection.json")
        else:
            citable.update(detection_cite_ids(det))
            for inv in ("PSI-47", "PSI-101", "PSI-115"):  # the investigations behind the detection series
                if any(r.get("id") == inv for r in catalog):
                    citable.add(inv)
    pack["detection"] = det

    # ---- habitat compare (S4)
    cmp_block = None
    if wants_compare(question, ctx_ids):
        pair = compare_pair(question, h)
        if pair is not None:
            try:
                cmp_block = compare_block(*pair)
            except Exception as exc:  # noqa: BLE001 - engine errors must not break the pack
                missing.append(f"compare.compare: {type(exc).__name__}")
            else:
                if cmp_block is None:
                    missing.append("engine.compare")
                else:
                    citable.add(cmp_block["id"])
                    citable.update(m["id"] for m in cmp_block["metrics"].values())
    pack["compare"] = cmp_block

    pack["holdout"] = hold

    # ---- habitat briefing (S1)
    brf = None
    if wants_briefing(question, ctx_ids):
        try:
            brf = briefing_block(h)
        except Exception as exc:  # noqa: BLE001 - engine errors must not break the pack
            missing.append(f"briefing.briefing: {type(exc).__name__}")
        else:
            if brf is None:
                missing.append("artifacts/briefing")
            else:
                citable.update(briefing_cite_ids(brf))
    pack["briefing"] = brf

    # ---- atmosphere evidence map (S5)
    amap = None
    if wants_atmosphere_map(question, ctx_ids):
        amap = atmosphere_map_block(h)
        if amap is None:
            missing.append("artifacts/atmosphere_map")
        else:
            citable.update(atmosphere_map_cite_ids(amap))
    pack["atmosphere_map"] = amap

    # ---- uncertainty drivers (S3)
    drv: dict[str, Any] = {}
    if wants_drivers(question, ctx_ids):
        asked = [c.split(":")[-1] for c in ctx_ids if c.startswith("eng:drivers:")]
        drv, drv_missing = drivers_block(h, [m for m in preds if not asked or m in asked])
        missing.extend(drv_missing)
        citable.update(d["id"] for d in drv.values())
    pack["drivers"] = drv

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
