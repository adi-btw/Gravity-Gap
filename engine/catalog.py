"""P3 Evidence Catalog: one record per PSI investigation -> artifacts/catalog.json.

Run:  python -m engine.catalog

Sources
- Text fields (title, objective, hypothesis, impacts, DOI, platform, hardware,
  research area, publications, related ids) come from
  ``data/psi_metadata/{id}.json`` written by ``scripts/fetch_psi.py`` (PSI API, or
  the PSI ISA-Tab export when the API is unavailable). Nothing is typed in here.
- Computed fields (n_tests, condition ranges, outcomes_available, fuel_phase,
  ground_reference) come from ``data/clean/*.csv`` only.

Rules (all transparent, documented per field in the record's ``*_basis`` keys)
- ``conditions``: min/max of o2_mole_fraction, pressure_atm, flow_speed_cm_s in
  psi_tests.csv. ``conditions.o2`` uses only ``o2_context == "ambient"`` rows (the
  surrounding atmosphere a habitat would be compared against); inverse-flame rows
  report the O2 of the *burner oxidizer stream*, which is not an atmosphere, so
  those go to ``conditions.o2_burner_stream`` instead (null when none). Pressure
  and flow use all rows. For day-summary-only investigations
  the ranges are parsed from ``o2_levels_percent`` (percent -> fraction),
  ``pressure_levels_atm`` and ``flow_speed_range_cm_s``. Null when no data.
- ``n_tests``: row count in psi_tests.csv; for day-summary-only investigations the
  sum of ``flames_ignited`` (ignitions, not distinct test points; 0 when the table
  gives no counts, e.g. SLICE free-text days and FLEX-2 condition ranges).
- ``outcomes_available``: any non-null ``outcome`` in psi_tests.csv.
- ``is_combustion``: metadata researchArea == "Combustion Science"; when no
  metadata is available, True if the investigation appears in the clean
  combustion tables (all of which are PSI combustion experiments).
- ``hazard_pillars``: keyword rule over title + objective + impacts + design
  keywords (``PILLAR_PATTERNS``); the matched words are kept in ``pillar_evidence``.
- ``pillar_data``: curated pointer to the data actually parsed for a pillar
  (``DETECTION_DATA``, R3 / ADR-0007): what it holds, the files (only those in
  data/detection/manifest.json) and the artifact; {} when none.
- ``ground_reference``: True only when the investigation has normal-gravity
  (1-g) columns in the clean data, i.e. psi_saffire_ug_vs_1g.csv (SAFFIRE-II).
- ``gravity_levels``: ["normal_gravity"] for PSI "Ground Investigation" studies,
  ["microgravity"] for flight platforms (ISS, Cygnus, Space Shuttle); a ground
  reference adds "normal_gravity".
- ``fuel_phase``: psi_tests.csv mode, else inferred from fuel names / metadata;
  ``FUEL_PHASE_OVERRIDES`` sets curated phases (with the metadata evidence word
  checked and quoted in ``fuel_phase_basis``) for investigations whose tables are
  not in data/clean: SAME / SAME-R / SAME modeling (pyrolysed solid samples ->
  "solid") and DAFT ("aerosol": test dust, no fuel burned, fuel_realism 0).
- ``lineage`` / ``reanalyzed_by``: ground re-analysis studies and the flight
  investigation whose data they reuse (``LINEAGE``, each link checked against
  the study's title / design keywords and the evidence word recorded).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
META_DIR = ROOT / "data" / "psi_metadata"
CLEAN_DIR = ROOT / "data" / "clean"
OUT = ROOT / "artifacts" / "catalog.json"
CATALOG_VERSION = "1.2.0"

# investigation -> (fuel_phase, evidence regex over metadata JSON text, basis note)
FUEL_PHASE_OVERRIDES: dict[str, tuple[str, str, str]] = {
    "PSI-47": ("aerosol", r"Arizona Red Dust|aerosoli[sz]ed",
               "DAFT aerosolised a test dust (Arizona Road Dust, ARD Fine, per the DAFT experimental "
               "table; the metadata writes 'Arizona Red Dust') to check smoke/particle "
               "instruments; nothing was burned, so this is not a fuel (fuel_realism 0)"),
    "PSI-101": ("solid", r"pyrolyzing|Teflon|Kapton|Pyrell",
                "SAME-R smoke came from heated (pyrolysing/smouldering) solid spacecraft "
                "material samples (Teflon, Kapton, silicone, Pyrell, cotton lamp wick)"),
    "PSI-102": ("solid", r"overheated\s+spacecraft materials|pyrolyzing",
                "SAME smoke came from overheated solid spacecraft material samples "
                "(Teflon, Kapton, silicone, cotton lamp wick)"),
    "PSI-115": ("solid", r"pyrolysis vapor expelled from a heated sample",
                "numerical modeling of SAME: smoke from pyrolysis vapour of a heated solid sample"),
}

PILLAR_PATTERNS: dict[str, str] = {
    "prevention": r"flammab|material|flame spread|ignit",
    "detection": r"smoke|soot|aerosol|particle|detect",
    "suppression": r"extingu|suppress|dilut|helium|co2",
}

# R3 (ADR-0007): detection-pillar data actually parsed into artifacts/detection.json, per investigation.
# Files are listed only if data/detection/manifest.json has them (see _pillar_data).
DETECTION_MANIFEST = ROOT / "data" / "detection" / "manifest.json"
DETECTION_DATA: dict[str, tuple[str | None, str, list[str]]] = {
    # investigation -> (artifact or None, what the data holds, files under data/detection/raw/)
    "PSI-101": ("artifacts/detection.json",
                ("Smoke particle sizes counted on microscope images (cotton lamp wick run 54, silicone run 60, "
                 "Kapton run 62) and per-run smoke sizes from instrument totals (100 runs, 5 materials)."),
                ["PSI-101/PSI-101_Analyzed_Data_54_lampwick_binneddatacorr_from_GWM.xlsx",
                 "PSI-101/PSI-101_Analyzed_Data_60_silicone.xlsx",
                 "PSI-101/PSI-101_Analyzed_Data_62_Kapton_unaged.xlsx",
                 "PSI-101/PSI-101_Analyzed_Data_SAME,_SAME-R_Results.xlsx"]),
    "PSI-102": (None,
                ("Sample list only (8 rows: material, air flow, weight loss rate, aging time). "
                 "No SAME measurement files are in this repository."),
                ["PSI-102/PSI-102_Experimental_table_SAME.csv"]),
    "PSI-47": ("artifacts/detection.json",
               ("Arizona Road Dust, total particle number and total mass only (no sizes). One derived "
                "diameter of average mass per dust bag, assuming a density of 1.0 g/cm3."),
               ["PSI-47/PSI-47_Analyzed_Data_DAFT_Retrieved_Data_Summary.xls",
                "PSI-47/PSI-47_Experimental_table_DAFT.csv"]),
    "PSI-115": ("artifacts/detection.json",
                ("Simulated smoke size distributions, Earth gravity vs microgravity "
                 "(dibutyl phthalate surrogate, t = 7 s; value unit [verify], shapes only)."),
                ["PSI-115/PSI-115_Analyzed_Data_nodeDiameters.dat",
                 "PSI-115/PSI-115_Analyzed_Data_8cmGravityPSD.dat",
                 "PSI-115/PSI-115_Analyzed_Data_8cmNoGravityPSD.dat",
                 "PSI-115/PSI-115_Analyzed_Data_8cmGravityNS_PSD.dat",
                 "PSI-115/PSI-115_Analyzed_Data_8cmNoGravityNoTF_PSD.dat",
                 "PSI-115/PSI-115_Analyzed_Data_10cmGravityPSD.dat",
                 "PSI-115/PSI-115_Analyzed_Data_10cmNoGravityPSD.dat"]),
}

# ground re-analysis study -> (flight investigations reused, evidence regex)
LINEAGE: dict[str, tuple[list[str], str]] = {
    "PSI-117": (["PSI-69"], r"\bFLEX\b"),
    "PSI-142": (["PSI-69"], r"\bFLEX\b"),
    "PSI-60": (["PSI-107"], r"\bSPICE\b"),
    "PSI-62": (["PSI-26", "PSI-25"], r"\bBASS\b"),
    "PSI-115": (["PSI-102"], r"Smoke Aerosol Measurement Experiment|\bSAME\b"),
}

_GAS_FUEL = re.compile(r"\b(CH4|C2H4|C2H6|C3H8|C4H10|H2|methane|ethylene|ethane|propane|butane|gaseous|gas)\b", re.I)
_LIQUID_FUEL = re.compile(r"(octane|heptane|decane|dodecane|alkane|ethanol|methanol|droplet)", re.I)
_SOLID_FUEL = re.compile(r"(flame spread|solid|fabric|sample|PMMA|cotton)", re.I)

# fields read from metadata JSON: canonical name -> accepted key aliases
_META_KEYS: dict[str, list[str]] = {
    "title": ["title", "studyTitle", "Study Title"],
    "acronym": ["acronym", "investigationAcronym"],
    "objective": ["objective"],
    "hypothesis": ["hypothesis"],
    "impacts": ["researchImpacts", "research_impacts", "impacts"],
    "doi": ["doi", "DOI"],
    "platform": ["flightProgram", "flightPlatform", "flight_platform"],
    "hardware": ["experimentHardware", "experiment_hardware", "hardware"],
    "research_area": ["researchArea", "research_area"],
    "sub_research_area": ["subResearchArea", "sub_research_area"],
    "project_type": ["projectType", "project_type"],
}


# ----------------------------------------------------------------- helpers
def _clean_text(v):
    if v is None:
        return None
    if isinstance(v, list):
        v = "; ".join(str(x) for x in v if x)
    s = str(v).replace("�", "'").strip().strip('"').strip()
    return s or None


def _meta_get(meta: dict, field: str):
    lower = {k.lower(): k for k in meta}
    for alias in _META_KEYS[field]:
        k = lower.get(alias.lower())
        if k is not None and meta[k] not in (None, "", []):
            return _clean_text(meta[k])
    return None


def _publications(meta: dict) -> list[dict]:
    out = []
    for p in meta.get("publications") or []:
        if isinstance(p, dict):
            doi = _clean_text(p.get("doi") or p.get("DOI"))
            title = _clean_text(p.get("title") or p.get("Title"))
        else:
            doi, title = None, _clean_text(p)
        if doi or title:
            out.append({"doi": doi, "title": title})
    return out


def _design_keywords(meta: dict) -> list[str]:
    for k in ("studyDesignTypes", "studyDesignDescriptors", "designTypes", "keywords"):
        v = meta.get(k)
        if v:
            return [_clean_text(x if not isinstance(x, dict) else x.get("name") or x.get("term")) or ""
                    for x in v]
    return []


def _related_ids(meta: dict) -> list[str]:
    raw = meta.get("related_glds") or meta.get("relatedGlds") or []
    if isinstance(raw, str):  # the PSI API returns a comma-separated string, e.g. "PSI-69,PSI-142"
        raw = [raw]
    ids = []
    for x in raw:
        s = x if isinstance(x, str) else (x.get("id") or x.get("accession") or "") if isinstance(x, dict) else ""
        ids += re.findall(r"PSI-\d+", str(s))
    return ids


def _rng(series: pd.Series):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if s.empty:
        return None
    return [round(float(s.min()), 6), round(float(s.max()), 6)]


def _parse_numbers(values) -> list[float]:
    nums: list[float] = []
    for v in values:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        nums += [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", str(v))]
    return nums


def _span(nums: list[float]):
    return [round(min(nums), 6), round(max(nums), 6)] if nums else None


def _short_platform(text: str | None, project_type: str | None) -> str | None:
    if project_type and "ground" in project_type.lower():
        return "ground"
    if not text:
        return None
    t = text.lower()
    if "cygnus" in t:
        return "Cygnus"
    if "international space station" in t or re.search(r"\biss\b", t):
        return "ISS"
    if "shuttle" in t:
        return "Space Shuttle"
    if "not applicable" in t:
        return "ground"
    return text


def _pillars(text: str) -> tuple[list[str], dict[str, list[str]]]:
    pillars, evidence = [], {}
    for name, pat in PILLAR_PATTERNS.items():
        words = sorted({m.group(0).lower() for m in re.finditer(rf"\w*(?:{pat})\w*", text, re.I)})
        if words:
            pillars.append(name)
            evidence[name] = words
    return pillars, evidence


def _pillar_data(inv: str, manifest_files: set[str]) -> dict:
    """{"detection": {...}} for investigations whose detection data is parsed (R3), else {}."""
    if inv not in DETECTION_DATA:
        return {}
    artifact, holds, files = DETECTION_DATA[inv]
    listed = [f"data/detection/raw/{f}" for f in files if f"data/detection/raw/{f}" in manifest_files]
    if not listed:
        return {}
    return {"detection": {"holds": holds, "files": listed, "artifact": artifact}}


def _infer_phase(text: str) -> str | None:
    for phase, rx in (("liquid", _LIQUID_FUEL), ("gas", _GAS_FUEL), ("solid", _SOLID_FUEL)):
        if rx.search(text):
            return phase
    return None


def _id_key(i: str) -> tuple:
    m = re.match(r"PSI-(\d+)", i)
    return (int(m.group(1)) if m else 10**9, i)


# ----------------------------------------------------------------- build
def load_metadata() -> dict[str, dict]:
    out = {}
    if META_DIR.is_dir():
        for p in sorted(META_DIR.glob("PSI-*.json")):
            out[p.stem] = json.loads(p.read_text(encoding="utf-8"))
    return out


def _inputs_hash(meta: dict[str, dict]) -> str:
    h = hashlib.sha256()
    for name in ("psi_tests.csv", "psi_test_day_summaries.csv", "psi_saffire_ug_vs_1g.csv"):
        h.update((CLEAN_DIR / name).read_bytes())
    for k in sorted(meta):
        h.update(json.dumps(meta[k], sort_keys=True).encode())
    return h.hexdigest()[:12]


def build_catalog() -> dict:
    tests = pd.read_csv(CLEAN_DIR / "psi_tests.csv", low_memory=False)
    days = pd.read_csv(CLEAN_DIR / "psi_test_day_summaries.csv")
    saffire = pd.read_csv(CLEAN_DIR / "psi_saffire_ug_vs_1g.csv")
    meta_all = load_metadata()
    detection_files = (set(json.loads(DETECTION_MANIFEST.read_text(encoding="utf-8"))["files"])
                       if DETECTION_MANIFEST.exists() else set())

    ground_ref_ids = {f.split("_", 1)[0] for f in saffire["source_file"].dropna()}
    test_ids = set(tests["investigation_id"].dropna())
    day_ids = set(days["investigation_id"].dropna()) - test_ids
    ids = sorted(test_ids | day_ids | set(meta_all), key=_id_key)

    records: dict[str, dict] = {}
    for inv in ids:
        meta = meta_all.get(inv, {})
        t = tests[tests["investigation_id"] == inv]
        d = days[days["investigation_id"] == inv]
        f = {k: _meta_get(meta, k) for k in _META_KEYS} if meta else dict.fromkeys(_META_KEYS)
        design = _design_keywords(meta) if meta else []

        # --- computed from clean data
        if not t.empty:
            ctx = t["o2_context"]
            conditions = {
                "o2": _rng(t.loc[ctx == "ambient", "o2_mole_fraction"]),
                "pressure_atm": _rng(t["pressure_atm"]),
                "flow_cm_s": _rng(t["flow_speed_cm_s"]),
                "o2_burner_stream": _rng(t.loc[ctx == "burner_oxidizer_stream", "o2_mole_fraction"]),
            }
            n_tests = int(len(t))
            n_basis = "rows in data/clean/psi_tests.csv"
            outcomes = bool(t["outcome"].notna().any())
            phase = t["fuel_phase"].mode().iat[0] if t["fuel_phase"].notna().any() else None
            phase_basis = "psi_tests.csv fuel_phase" if phase else None
            cond_source = "psi_tests.csv"
            data_acronym = t["investigation"].dropna().iat[0] if t["investigation"].notna().any() else None
            data_hw = t["hardware"].dropna().iat[0] if t["hardware"].notna().any() else None
            data_platform = t["platform"].dropna().iat[0] if t["platform"].notna().any() else None
        elif not d.empty:
            o2 = [x / 100.0 for x in _parse_numbers(d["o2_levels_percent"])]
            conditions = {
                "o2": _span(o2),
                "pressure_atm": _span(_parse_numbers(d["pressure_levels_atm"])),
                "flow_cm_s": _span(_parse_numbers(d["flow_speed_range_cm_s"])),
                "o2_burner_stream": None,
            }
            fl = pd.to_numeric(d["flames_ignited"], errors="coerce")
            n_tests = int(fl.sum()) if fl.notna().any() else 0
            n_basis = ("sum of flames_ignited in psi_test_day_summaries.csv (ignitions, not distinct test points)"
                       if fl.notna().any() else "day summaries give no test counts")
            outcomes = False
            phase = _infer_phase(" ".join(d["fuel"].dropna().astype(str)))
            phase_basis = "inferred from day-summary fuel names" if phase else None
            cond_source = "psi_test_day_summaries.csv"
            data_acronym = d["investigation"].dropna().iat[0] if d["investigation"].notna().any() else None
            data_hw = data_platform = None
        else:
            conditions = {"o2": None, "pressure_atm": None, "flow_cm_s": None, "o2_burner_stream": None}
            n_tests, n_basis, outcomes = 0, "no experimental table in data/clean", False
            phase, phase_basis, cond_source = None, None, None
            data_acronym = data_hw = data_platform = None

        # --- platform / gravity
        platform = (_short_platform(data_platform, None) if data_platform else None) \
            or _short_platform(f["platform"], f["project_type"])
        is_ground = bool(f["project_type"] and "ground" in f["project_type"].lower())
        ground_reference = inv in ground_ref_ids
        if is_ground:
            gravity = ["normal_gravity"]
        elif platform in ("ISS", "Cygnus", "Space Shuttle") or not t.empty or not d.empty:
            gravity = ["microgravity"]
        else:
            gravity = []
        if ground_reference and "normal_gravity" not in gravity:
            gravity.append("normal_gravity")

        # --- combustion flag
        if f["research_area"]:
            is_comb = f["research_area"].strip().lower() == "combustion science"
            comb_basis = f"metadata researchArea = {f['research_area']!r}"
        else:
            is_comb = inv in test_ids or inv in day_ids
            comb_basis = "no metadata; present in clean PSI combustion tables" if is_comb else "unknown"

        text = " ".join(x for x in (f["title"], f["objective"], f["impacts"], *design) if x)
        pillars, evidence = _pillars(text)

        if inv in FUEL_PHASE_OVERRIDES and meta:
            o_phase, o_rx, o_note = FUEL_PHASE_OVERRIDES[inv]
            m = re.search(o_rx, json.dumps(meta, ensure_ascii=False), re.I)
            if m:
                phase = o_phase
                phase_basis = f"curated: {o_note} (metadata evidence {m.group(0)!r})"

        if not phase and is_comb:
            phase = _infer_phase(" ".join(x for x in (f["sub_research_area"], *design) if x))
            phase_basis = "inferred from metadata subResearchArea / design keywords" if phase else None

        records[inv] = {
            "id": inv,
            "acronym": f["acronym"] or data_acronym,
            "title": f["title"],
            "doi": f["doi"],
            "platform": platform,
            "platform_source_text": f["platform"] or data_platform,
            "hardware": f["hardware"] or data_hw,
            "research_area": f["research_area"],
            "sub_research_area": f["sub_research_area"],
            "project_type": f["project_type"],
            "fuel_phase": phase,
            "fuel_phase_basis": phase_basis,
            "gravity_levels": gravity,
            "ground_reference": ground_reference,
            "ground_reference_note": (
                "has normal-gravity (1-g) burn-length columns for the same samples in "
                "data/clean/psi_saffire_ug_vs_1g.csv" if ground_reference else None),
            "conditions": conditions,
            "conditions_source": cond_source,
            "n_tests": n_tests,
            "n_tests_basis": n_basis,
            "outcomes_available": outcomes,
            "hazard_pillars": pillars,
            "pillar_evidence": evidence,
            "pillar_data": _pillar_data(inv, detection_files),
            "objective": f["objective"],
            "hypothesis": f["hypothesis"],
            "impacts": f["impacts"],
            "publications": _publications(meta) if meta else [],
            "related": sorted(set(_related_ids(meta)) - {inv}, key=_id_key) if meta else [],
            "lineage": None,
            "reanalyzed_by": [],
            "is_combustion": bool(is_comb),
            "is_combustion_basis": comb_basis,
            "metadata_source": meta.get("_source") if meta else None,
        }

    # --- lineage (B4), both directions
    for child, (parents, rx) in LINEAGE.items():
        rec = records.get(child)
        if rec is None:
            continue
        meta = meta_all.get(child, {})
        text = " ".join(x for x in (rec["title"], rec["sub_research_area"], *_design_keywords(meta)) if x)
        m = re.search(rx, text)
        listed = [p for p in parents if p in _related_ids(meta)]
        ev = []
        if listed:
            ev.append(f"metadata related_glds lists {', '.join(listed)}")
        if m:
            ev.append(f"title/design keyword {m.group(0)!r}")
        rec["lineage"] = {
            "reuses": parents,
            "evidence": "; ".join(ev) or "curated link (not confirmed by metadata)",
            "missing_from_catalog": [p for p in parents if p not in records],
        }
        rec["related"] = sorted(set(rec["related"]) | set(parents), key=_id_key)
        for p in parents:
            if p in records:
                records[p]["reanalyzed_by"] = sorted(set(records[p]["reanalyzed_by"]) | {child}, key=_id_key)
                records[p]["related"] = sorted(set(records[p]["related"]) | {child}, key=_id_key)
        if not rec["fuel_phase"]:
            phases = {records[p]["fuel_phase"] for p in parents if p in records and records[p]["fuel_phase"]}
            if len(phases) == 1:
                rec["fuel_phase"] = phases.pop()
                rec["fuel_phase_basis"] = "inherited from the reused flight investigation"

    return {
        "version": f"{CATALOG_VERSION}+{_inputs_hash(meta_all)}",
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "generated_by": "engine/catalog.py",
        "rules": {
            "hazard_pillars": PILLAR_PATTERNS,
            "n_tests": "psi_tests.csv rows; day-summary-only investigations: sum of flames_ignited",
            "conditions": "min/max over clean data; null when the source has no value; "
                          "o2 = ambient rows only, burner-stream O2 in o2_burner_stream",
            "fuel_phase_overrides": {k: v[0] for k, v in FUEL_PHASE_OVERRIDES.items()},
            "ground_reference": "true only when 1-g columns exist in the clean data (SAFFIRE-II)",
            "pillar_data": "curated DETECTION_DATA, files checked against data/detection/manifest.json",
        },
        "investigations": [records[i] for i in ids],
    }


def main() -> int:
    cat = build_catalog()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(cat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    recs = cat["investigations"]
    print(f"wrote {OUT.relative_to(ROOT)}: {len(recs)} records, "
          f"{sum(r['is_combustion'] for r in recs)} combustion, version {cat['version']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
