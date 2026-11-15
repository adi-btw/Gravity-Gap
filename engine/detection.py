"""R3 detection spike: prototype parsers for smoke (SAME-R), dust (DAFT) and simulated smoke (PSI-115).

Formats are documented in ``data/detection/FORMATS.md``; the spike result is in
``plan/14-detection-spike.md``. Files are fetched by ``scripts/fetch_detection.py``.

Every parser returns records in one common shape::

    {"source": {"investigation_id", "file", "sheet", "rows"},
     "diameter_nm": [...], "value": [...], "value_kind": "...", "units": "..."}

plus a few extra keys where the file gives more (bin width, workbook-reported statistics, ...).

What each source really holds (do not blur these on a chart):
  * SAME-R TEM workbooks: binned particle counts by diameter (a real size distribution, small samples).
  * SAME-R results workbook: one row per run with integrated moments only (number, mean diameter,
    diameter of average mass, Hatch-Choate geometric standard deviation). No bins.
  * DAFT: time series of total number (P-Trak) and total mass (DustTrak). No sizes at all. The only
    size is a diameter of average mass derived from the two totals, with an assumed density.
  * PSI-115: a simulation. One number density per particle-size node.

Downloaded files are data only: they are parsed, never executed.

R3 build (reduced scope, ADR-0007): ``build()`` assembles ``artifacts/detection.json`` in the shape of
plan/contracts.md "Round 2 · R3 Detection evidence addendum"; run ``python -m engine.detection``.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import itertools
import json
import math
import statistics
import sys
from pathlib import Path

import openpyxl
import xlrd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "detection" / "raw"

UM_TO_NM = 1000.0
M_TO_NM = 1.0e9


def _is_num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _source(investigation_id: str, path: Path, sheet: str | None, rows: str) -> dict:
    return {"investigation_id": investigation_id, "file": Path(path).name, "sheet": sheet, "rows": rows}


# ------------------------------------------------------------------ statistics
def size_stats(diameter_nm: list[float], count: list[float]) -> dict | None:
    """Count statistics of a binned distribution on log-spaced diameters.

    ``geometric_mean_diameter_nm`` and ``geometric_std`` are the count-weighted mean and standard
    deviation of ln(d). ``count_median_diameter_nm`` is read off the cumulative count, taking each bin
    to span the geometric midpoints to its neighbours. For a lognormal distribution the two diameters
    agree; a large difference means the distribution is not lognormal (e.g. bimodal).
    Returns None when there are fewer than two bins or no counts.
    """
    pairs = [(d, c) for d, c in zip(diameter_nm, count) if _is_num(d) and _is_num(c) and d > 0 and c >= 0]
    total = sum(c for _, c in pairs)
    if len(pairs) < 2 or total <= 0:
        return None
    ln_d = [math.log(d) for d, _ in pairs]
    mean = sum(x * c for x, (_, c) in zip(ln_d, pairs)) / total
    var = sum((x - mean) ** 2 * c for x, (_, c) in zip(ln_d, pairs)) / total
    # bin edges in ln space: midpoints between neighbours, end bins mirrored
    edges = [ln_d[0] - (ln_d[1] - ln_d[0]) / 2]
    edges += [(a + b) / 2 for a, b in itertools.pairwise(ln_d)]
    edges.append(ln_d[-1] + (ln_d[-1] - ln_d[-2]) / 2)
    cum, median = 0.0, None
    for i, (_, c) in enumerate(pairs):
        if c > 0 and cum + c >= total / 2:
            median = math.exp(edges[i] + (total / 2 - cum) / c * (edges[i + 1] - edges[i]))
            break
        cum += c
    return {
        "count_median_diameter_nm": median,
        "geometric_mean_diameter_nm": math.exp(mean),
        "geometric_std": math.exp(math.sqrt(var)),
        "total": total,
    }


def diameter_of_average_mass_nm(number_per_cm3: float, mass_mg_per_m3: float, density_g_per_cm3: float) -> float:
    """Diameter of the sphere whose mass is (total mass) / (total number). Needs an assumed density."""
    mass_g_per_cm3 = mass_mg_per_m3 * 1.0e-3 / 1.0e6
    volume_cm3 = mass_g_per_cm3 / number_per_cm3 / density_g_per_cm3
    return (6.0 * volume_cm3 / math.pi) ** (1.0 / 3.0) * 1.0e7  # cm -> nm


# ------------------------------------------------------------------ SAME-R (PSI-101)
def _binned_sheet_name(sheetnames: list[str], big_only: bool) -> str:
    for name in sheetnames:
        low = name.lower()
        if low.startswith("binned data") and (("big only" in low) == big_only):
            return name
    raise ValueError(f"no 'Binned data' sheet (big_only={big_only}) in {sheetnames}")


def parse_same_r_tem(path: Path, big_only: bool = False, sheet: str | None = None) -> dict:
    """Binned TEM particle counts from a SAME-R per-run workbook (e.g. '60 silicone.xlsx').

    Sheet 'Binned data*': data from row 15 down; column D = dN (particles counted in the bin),
    G = D (bin lower edge, micrometres), H = Dmid (geometric bin centre, micrometres), C8 = dLnD.
    ``big_only=True`` reads the 'Binned data big only' variant, in which the workbook authors dropped
    the smallest particles. Workbook-reported Dg / sigma-g (cells I9 / J9) are returned for comparison.
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        name = sheet or _binned_sheet_name(wb.sheetnames, big_only)
        rows = list(wb[name].iter_rows(min_row=1, max_col=10, values_only=True))
    finally:
        wb.close()
    header = [str(v).strip() if v is not None else "" for v in rows[13]]
    if header[3] != "dN" or header[7] != "Dmid":
        raise ValueError(f"{Path(path).name}/{name}: unexpected header row 14: {header}")
    diam, lower, count, used = [], [], [], []
    for r in range(14, len(rows)):  # sheet row 15 onward
        dn, d_low, d_mid = rows[r][3], rows[r][6], rows[r][7]
        if _is_num(dn) and _is_num(d_mid):
            if diam and d_mid * UM_TO_NM <= diam[-1]:
                # '60 silicone.xlsx' pads the table by repeating its last bin with zero counts
                if dn != 0:
                    raise ValueError(f"{Path(path).name}/{name}: row {r + 1} repeats a bin with counts")
                continue
            diam.append(d_mid * UM_TO_NM)
            lower.append(d_low * UM_TO_NM if _is_num(d_low) else None)
            count.append(float(dn))
            used.append(r + 1)
    if not diam:
        raise ValueError(f"{Path(path).name}/{name}: no binned rows found")
    reported_dg, reported_sg = rows[8][8], rows[8][9]
    return {
        "source": _source("PSI-101", path, name, f"{used[0]}-{used[-1]}"),
        "instrument": "TEM image sizing of thermal-precipitator samples",
        "diameter_nm": diam,
        "bin_lower_nm": lower,
        "dlnD": rows[7][2] if _is_num(rows[7][2]) else None,
        "value": count,
        "value_kind": "particle_count_per_bin",
        "units": "particles",
        "stats": size_stats(diam, count),
        "workbook_reported": {
            "geometric_mean_diameter_nm": reported_dg * UM_TO_NM if _is_num(reported_dg) else None,
            "geometric_std": reported_sg if _is_num(reported_sg) else None,
        },
    }


_MOMENT_COLUMNS = {
    "Sample Type": "material",
    "SAME #": "run",
    "Description": "description",
    "M0 best Diameter (#/cm3)": "number_per_cm3",
    "M1/M0 (micro-m)--AMD": "count_mean_diameter_um",
    "Diameter of Average mass (micro-m)": "diameter_of_average_mass_um",
    "Hatch Choate Sigma g": "geometric_std",
    "Hatch Choate Dg": "geometric_mean_diameter_um",
}


def parse_same_r_moments(path: Path, sheet: str = "SAME R Results") -> list[dict]:
    """Per-run integrated moments from 'SAME, SAME-R_Results.xlsx' (no size bins).

    Header row 2, data from row 3. The diameters are derived by the experiment team from three
    integrated signals (number, ionization-chamber length moment, mass), not from a measured
    distribution. A run id ending in 'a' is the aged repeat of the same smoke.
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = list(wb[sheet].iter_rows(min_row=1, max_col=70, values_only=True))
    finally:
        wb.close()
    header = [str(v).strip() if v is not None else "" for v in rows[1]]
    col = {}
    for name, key in _MOMENT_COLUMNS.items():
        if name not in header:
            raise ValueError(f"{Path(path).name}/{sheet}: column {name!r} not found in row 2")
        col[key] = header.index(name)
    out = []
    for r in range(2, len(rows)):
        row = rows[r]
        material = row[col["material"]]
        numbers = {k: row[col[k]] for k in ("number_per_cm3", "count_mean_diameter_um",
                                            "diameter_of_average_mass_um", "geometric_std",
                                            "geometric_mean_diameter_um")}
        if not isinstance(material, str) or not all(_is_num(v) and v > 0 for v in numbers.values()):
            continue
        run = str(row[col["run"]]).strip()
        out.append({
            "source": _source("PSI-101", path, sheet, str(r + 1)),
            "material": material.strip(),
            "run": run,
            "aged": run.endswith("a"),
            "description": row[col["description"]],
            "diameter_nm": [numbers["geometric_mean_diameter_um"] * UM_TO_NM],
            "value": [numbers["number_per_cm3"]],
            "value_kind": "number_concentration_at_geometric_mean_diameter",
            "units": "particles/cm3",
            "count_mean_diameter_nm": numbers["count_mean_diameter_um"] * UM_TO_NM,
            "diameter_of_average_mass_nm": numbers["diameter_of_average_mass_um"] * UM_TO_NM,
            "geometric_std": numbers["geometric_std"],
        })
    return out


# ------------------------------------------------------------------ DAFT (PSI-47)
_DAFT_KIND = {
    "P-Trak": ("number_concentration", "particles/cm3"),
    "DustTrak": ("mass_concentration", "mg/m3"),
}


def parse_daft_txt(path: Path) -> dict:
    """Raw DAFT instrument log (PTrk*.txt / DTrk*.txt): 'Key: value' header lines, then one reading
    per line (1 s apart per the timestamps in the summary workbook). No particle sizes.

    Lines end in CR CR LF. Readings beyond the header's 'Number of points' are dropped (DTrk0002.txt
    carries one extra, unterminated value at the end).
    """
    raw = Path(path).read_bytes().decode("utf-8", errors="replace")
    lines = raw.replace(chr(13), "").split(chr(10))
    meta, values, first = {}, [], None
    for i, line in enumerate(lines, start=1):
        text = line.strip()
        if not text:
            continue
        if ":" in text and not values:
            key, _, val = text.partition(":")
            meta[key.strip()] = val.strip()
            continue
        values.append(float(text))
        first = first or i
    instrument = meta.get("Instrument", "")
    if instrument not in _DAFT_KIND or first is None:
        raise ValueError(f"{Path(path).name}: not a DAFT P-Trak / DustTrak log")
    declared = int(meta.get("Number of points", len(values)))
    values = values[:declared]
    kind, units = _DAFT_KIND[instrument]
    return {
        "source": _source("PSI-47", path, None, f"{first}-{first + len(values) - 1}"),
        "instrument": instrument,
        "header": meta,
        "diameter_nm": [],  # the instrument reports one total per second, not sizes
        "time_s": [float(i) for i in range(1, len(values) + 1)],
        "value": values,
        "value_kind": kind,
        "units": units,
    }


def parse_daft_xls(path: Path, sheet: str) -> dict:
    """One instrument sheet (e.g. 'PTrk0002') of a DAFT 'flight data 063_*.xls' workbook.

    Column A repeats the raw log; the columns headed 'Time (sec)' and 'pt/cc' or 'mg/m3' (row 1)
    hold the series from row 2. No particle sizes.
    """
    sh = xlrd.open_workbook(str(path)).sheet_by_name(sheet)
    head = [str(v).strip() for v in sh.row_values(0)]
    if "Time (sec)" not in head:
        raise ValueError(f"{Path(path).name}/{sheet}: no 'Time (sec)' column in row 1")
    t_col = head.index("Time (sec)")
    instrument = str(sh.cell_value(0, 0)).partition(":")[2].strip()
    if instrument not in _DAFT_KIND:
        raise ValueError(f"{Path(path).name}/{sheet}: unknown instrument {instrument!r}")
    kind, units = _DAFT_KIND[instrument]
    time_s, values = [], []
    for r in range(1, sh.nrows):
        t, v = sh.cell_value(r, t_col), sh.cell_value(r, t_col + 1)
        if _is_num(t) and _is_num(v):
            time_s.append(float(t))
            values.append(float(v))
    return {
        "source": _source("PSI-47", path, sheet, f"2-{len(values) + 1}"),
        "instrument": instrument,
        "diameter_nm": [],
        "time_s": time_s,
        "value": values,
        "value_kind": kind,
        "units": units,
    }


def parse_daft_summary(path: Path, sheet: str = "Logged Data Summary") -> list[dict]:
    """Per-bag averages from 'DAFT Retrieved Data Summary.xls' and the one size they allow.

    Row 5 holds the average P-Trak number (n/cm3) and DustTrak mass (mg/m3) for three dust bags
    (column pairs B/C, E/F, H/I); row 9 the workbook's 'D (micon)'; cell D20 the density it assumed.
    The diameter is a diameter of average mass (one number per bag), not a size distribution.
    """
    sh = xlrd.open_workbook(str(path)).sheet_by_name(sheet)
    if str(sh.cell_value(4, 0)).strip() != "average**" or not str(sh.cell_value(8, 0)).startswith("D ("):
        raise ValueError(f"{Path(path).name}/{sheet}: unexpected layout")
    density = sh.cell_value(19, 3)
    out = []
    for bag, c in enumerate((1, 4, 7), start=1):
        number, mass, reported_um = sh.cell_value(4, c), sh.cell_value(4, c + 1), sh.cell_value(8, c)
        d_nm = diameter_of_average_mass_nm(number, mass, density)
        out.append({
            "source": _source("PSI-47", path, sheet, "5, 9, 20"),
            "bag": bag,
            "diameter_nm": [d_nm],
            "value": [number],
            "value_kind": "number_concentration_at_diameter_of_average_mass",
            "units": "particles/cm3",
            "mass_concentration_mg_per_m3": mass,
            "assumed_density_g_per_cm3": density,
            "workbook_reported_diameter_nm": reported_um * UM_TO_NM,
        })
    return out


# ------------------------------------------------------------------ PSI-115 (simulation)
def parse_psi115_node_diameters(path: Path) -> list[float]:
    """nodeDiameters.dat: one header line, then 44 diameters in metres for nodes 2..45
    (node 1 is the vapour molecule and has no entry). Returned in nanometres."""
    out = []
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines()[1:]:
        if line.strip():
            out.append(float(line) * M_TO_NM)
    return out


def parse_psi115_psd(path: Path, node_diameters_path: Path) -> dict:
    """A PSI-115 '*PSD.dat' file: 'node  value' per line, nodes numbered from 1.

    Node 1 (vapour) appears in some files and is dropped. Node k (k >= 2) uses line k-1 of
    nodeDiameters.dat. The value is the simulated collected number density of that size node.
    """
    node_d = parse_psi115_node_diameters(node_diameters_path)
    diam, values, used = [], [], []
    for i, line in enumerate(Path(path).read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        parts = line.split()
        if len(parts) != 2:
            continue
        node, value = int(parts[0]), float(parts[1])
        if node < 2:
            continue
        diam.append(node_d[node - 2])
        values.append(value)
        used.append(i)
    if not diam:
        raise ValueError(f"{Path(path).name}: no size nodes found")
    return {
        "source": _source("PSI-115", path, None, f"{used[0]}-{used[-1]}"),
        "instrument": "simulation (dibutyl phthalate surrogate smoke), t = 7 s",
        "diameter_nm": diam,
        "value": values,
        "value_kind": "simulated_number_density_per_size_node",
        "units": "m^-3 [verify]",
        "stats": size_stats(diam, values),
    }


# ------------------------------------------------------------------ artifact (R3 build, reduced scope)
# Contract: plan/contracts.md "Round 2 · R3 Detection evidence addendum". Decision: ADR-0007.
# Only the committed data files are read (never the git-ignored reference documents).
OUT = ROOT / "artifacts" / "detection.json"
MANIFEST = ROOT / "data" / "detection" / "manifest.json"
SCHEMA_VERSION = 1

TEM_RUNS = [  # (material key as in the results workbook, run, file under raw/PSI-101)
    ("Lampwick", "54", "PSI-101_Analyzed_Data_54_lampwick_binneddatacorr_from_GWM.xlsx"),
    ("Silicone", "60", "PSI-101_Analyzed_Data_60_silicone.xlsx"),
    ("Kapton", "62", "PSI-101_Analyzed_Data_62_Kapton_unaged.xlsx"),
]
RESULTS_FILE = "PSI-101_Analyzed_Data_SAME,_SAME-R_Results.xlsx"
DAFT_SUMMARY_FILE = "PSI-47_Analyzed_Data_DAFT_Retrieved_Data_Summary.xls"
DAFT_TABLE_FILE = "PSI-47_Experimental_table_DAFT.csv"
NODE_FILE = "PSI-115_Analyzed_Data_nodeDiameters.dat"
SIM_RUNS = [  # (file, case, case label, gravity, variant)
    ("PSI-115_Analyzed_Data_8cmGravityPSD.dat", "1", "8cm", "earth", "base"),
    ("PSI-115_Analyzed_Data_8cmNoGravityPSD.dat", "1", "8cm", "micro", "base"),
    ("PSI-115_Analyzed_Data_8cmGravityNS_PSD.dat", "1", "8cm", "earth", "no_settling"),
    ("PSI-115_Analyzed_Data_8cmNoGravityNoTF_PSD.dat", "1", "8cm", "micro", "no_thermophoresis"),
    ("PSI-115_Analyzed_Data_10cmGravityPSD.dat", "2", "10cm", "earth", "base"),
    ("PSI-115_Analyzed_Data_10cmNoGravityPSD.dat", "2", "10cm", "micro", "base"),
]
MATERIAL_LABELS = {"Kapton": "Kapton", "Lampwick": "Cotton lamp wick", "Pyrell": "Pyrell",
                   "Silicone": "Silicone", "Teflon": "Teflon"}
DUST_LABEL = "Arizona Road Dust (DAFT)"
SIM_SUFFIX = "(simulation, dibutyl phthalate surrogate, t = 7 s)"
LARGE_UM = 20.0

SIZE_DEFINITIONS = {
    "tem_image_diameter": {
        "label": "Size on microscope images",
        "note": ("Smoke was collected on small grids and photographed with an electron microscope (TEM). "
                 "Each particle was measured on the images and counted into size bins."),
    },
    "moment_geometric_mean": {
        "label": "Middle size from instrument totals",
        "note": ("Worked out by the SAME-R team from three instrument totals (particle number, an ionization "
                 "chamber signal and particle mass), assuming a lognormal size spread. No particles were sized "
                 "one by one."),
    },
    "diameter_of_average_mass": {
        "label": "Diameter of average mass",
        "note": ("The size of a ball that has the average particle mass: total mass divided by total number. "
                 "It needs a material density."),
    },
    "simulation_node_diameter": {
        "label": "Size class in the simulation",
        "note": "The PSI-115 computer model sorts particles into 44 size classes; this is the size of each class.",
    },
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _raw(investigation_id: str, name: str) -> Path:
    return RAW_DIR / investigation_id / name


def _generated_from(paths: list[Path]) -> list[dict]:
    """Manifest hashes of the files used; fails if a file differs from data/detection/manifest.json."""
    listed = json.loads(MANIFEST.read_text(encoding="utf-8"))["files"]
    out = []
    for p in paths:
        key = p.relative_to(ROOT).as_posix()
        if key not in listed:
            raise ValueError(f"{key} is not in {MANIFEST.name}")
        actual = _sha256(p)
        if actual != listed[key]["sha256"]:
            raise ValueError(f"{key}: sha256 {actual[:12]} differs from manifest {listed[key]['sha256'][:12]}")
        out.append({"file": key, "sha256": actual, "bytes": p.stat().st_size})
    return out


def _span(values: list[float]) -> dict:
    return {"min": min(values), "max": max(values)}


def _rows_span(rows: list[int]) -> str:
    return f"{min(rows)}-{max(rows)}"


def _smoke_bins() -> list[dict]:
    out = []
    for material, run, name in TEM_RUNS:
        for big_only in (False, True):
            rec = parse_same_r_tem(_raw("PSI-101", name), big_only=big_only)
            total = sum(rec["value"])
            variant = "big_only" if big_only else "all"
            variant_label = "Larger particles only (cut made by the authors)" if big_only else "All particles counted"
            st = rec["stats"]
            out.append({
                "id": f"tem_{material.lower()}_{run}_{variant}",
                "label": f"{MATERIAL_LABELS[material]} smoke, run {run}: {variant_label.lower()}",
                "material": material,
                "material_label": MATERIAL_LABELS[material],
                "run": run,
                "variant": variant,
                "variant_label": variant_label,
                "size_definition": "tem_image_diameter",
                "note": ("Share of counted particles in each size bin, from microscope images of one test run. "
                         + ("The workbook authors left out the smallest particles in this version."
                            if big_only else
                            "This version keeps every particle, including a group of very small ones.")),
                "source": rec["source"],
                "diameter_nm": rec["diameter_nm"],
                "count": rec["value"],
                "fraction": [c / total for c in rec["value"]],
                "dlnD": rec["dlnD"],
                "stats": {
                    "count_median_diameter_nm": st["count_median_diameter_nm"],
                    "geometric_mean_diameter_nm": st["geometric_mean_diameter_nm"],
                    "geometric_std": st["geometric_std"],
                    "particle_count": st["total"],
                },
                "workbook_reported": {**rec["workbook_reported"], "cells": "I9, J9"},
            })
    return out


def _smoke_runs(moments: list[dict]) -> dict:
    rows = [int(m["source"]["rows"]) for m in moments]
    materials = sorted({m["material"] for m in moments})
    points = [{
        "material": m["material"], "aged": m["aged"], "run": m["run"], "row": int(m["source"]["rows"]),
        "description": m["description"], "value_nm": m["diameter_nm"][0], "geometric_std": m["geometric_std"],
    } for m in moments]
    by_material = []
    for mat in materials:
        for aged in (False, True):
            grp = [m for m in moments if m["material"] == mat and m["aged"] == aged]
            if not grp:
                continue
            dg = [m["diameter_nm"][0] for m in grp]
            by_material.append({
                "material": mat, "material_label": MATERIAL_LABELS.get(mat, mat), "aged": aged, "n_runs": len(grp),
                "dg_nm": {"median": statistics.median(dg), "min": min(dg), "max": max(dg)},
                "geometric_std_median": statistics.median(m["geometric_std"] for m in grp),
                "diameter_of_average_mass_nm_median": statistics.median(m["diameter_of_average_mass_nm"] for m in grp),
            })
    return {
        "id": "same_r_runs_dg",
        "label": "Smoke middle size per test run (SAME-R)",
        "size_definition": "moment_geometric_mean",
        "note": ("One dot per test run. Test conditions (heating, air flow, aging time) differ between runs. "
                 "Aged runs measured the same smoke again after it had been held for a while."),
        "source": {**moments[0]["source"], "rows": _rows_span(rows)},
        "materials": materials,
        "material_labels": {m: MATERIAL_LABELS.get(m, m) for m in materials},
        "points": points,
        "by_material": by_material,
    }


def _daft_material_text() -> tuple[str, dict]:
    path = _raw("PSI-47", DAFT_TABLE_FILE)
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        rows = list(csv.DictReader(fh))
    texts = {r["Sample Material"].strip() for r in rows if r.get("Sample Material")}
    if len(texts) != 1 or "Arizona Road Dust" not in next(iter(texts)):
        raise ValueError(f"{path.name}: unexpected 'Sample Material' values {texts}")
    return next(iter(texts)), _source("PSI-47", path, None, f"2-{len(rows) + 1}")


def _average_mass_comparison(moments: list[dict]) -> dict:
    rows = [int(m["source"]["rows"]) for m in moments]
    smoke_pts = [{"material": m["material"], "aged": m["aged"], "run": m["run"], "row": int(m["source"]["rows"]),
                  "value_nm": m["diameter_of_average_mass_nm"]} for m in moments]
    bags = parse_daft_summary(_raw("PSI-47", DAFT_SUMMARY_FILE))
    densities = {b["assumed_density_g_per_cm3"] for b in bags}
    if len(densities) != 1:
        raise ValueError(f"DAFT summary: more than one assumed density {densities}")
    density = densities.pop()
    dust_pts = [{"bag": b["bag"], "value_nm": b["diameter_nm"][0],
                 "workbook_reported_nm": b["workbook_reported_diameter_nm"],
                 "number_per_cm3": b["value"][0], "mass_mg_per_m3": b["mass_concentration_mg_per_m3"]} for b in bags]
    material_text, material_source = _daft_material_text()
    return {
        "size_definition": "diameter_of_average_mass",
        "note": ("Both groups use the same size measure: total particle mass divided by total particle number, "
                 "turned into the size of one ball. It is one number per test, not a size distribution, so it "
                 "cannot show how much smoke and dust sizes overlap."),
        "smoke": {
            "id": "same_r_runs_dam",
            "label": "Smoke from heated spacecraft materials (SAME-R)",
            "source": {**moments[0]["source"], "rows": _rows_span(rows)},
            "points": smoke_pts,
            "range_nm": _span([p["value_nm"] for p in smoke_pts]),
        },
        "dust": {
            "id": "daft_ard_dam",
            "label": DUST_LABEL,
            "material_text": material_text,
            "source": bags[0]["source"],
            "material_source": material_source,
            "assumed_density_g_per_cm3": density,
            "density_note": (f"The dust size assumes a density of {density:g} g/cm3 (water), as the DAFT "
                             "workbook does (cell D20). Mineral dust is denser, so its real size is smaller "
                             "than shown. The density of this dust is not in these files [verify]."),
            "points": dust_pts,
            "range_nm": _span([p["value_nm"] for p in dust_pts]),
        },
    }


def _simulation() -> list[dict]:
    nodes = _raw("PSI-115", NODE_FILE)
    gravity_label = {"earth": "Earth gravity", "micro": "microgravity"}
    variant_label = {"base": "", "no_settling": ", settling switched off",
                     "no_thermophoresis": ", thermophoresis switched off"}
    variant_note = {"base": "",
                    "no_settling": " Settling was switched off in this run.",
                    "no_thermophoresis": " Thermophoresis (particles pushed away from hot gas) was switched off "
                                         "in this run."}
    out = []
    for name, case, case_label, gravity, variant in SIM_RUNS:
        rec = parse_psi115_psd(_raw("PSI-115", name), nodes)
        total = sum(rec["value"])
        frac = [v / total for v in rec["value"]]
        st = size_stats(rec["diameter_nm"], frac)
        peak = rec["diameter_nm"][max(range(len(frac)), key=frac.__getitem__)]
        suffix = "" if variant == "base" else f"_{variant}"
        out.append({
            "id": f"psi115_case{case}_{gravity}{suffix}",
            "label": f"Case {case} ({case_label}), {gravity_label[gravity]}{variant_label[variant]} {SIM_SUFFIX}",
            "case": case,
            "case_label": case_label,
            "gravity": gravity,
            "variant": variant,
            "surrogate": "dibutyl phthalate",
            "time_s": 7,
            "is_simulation": True,
            "size_definition": "simulation_node_diameter",
            "note": ("A computer model, not a measurement. It uses dibutyl phthalate as a stand-in smoke, not the "
                     "SAME-R materials. Each curve is the share of its own particle count per size class, so only "
                     "shapes can be compared; the raw unit is [verify]." + variant_note[variant]),
            "source": rec["source"],
            "diameter_nm": rec["diameter_nm"],
            "fraction": frac,
            "stats": {
                "count_median_diameter_nm": st["count_median_diameter_nm"],
                "geometric_mean_diameter_nm": st["geometric_mean_diameter_nm"],
                "geometric_std": st["geometric_std"],
                "peak_diameter_nm": peak,
                "share_of_count_above_20um": sum(f for d, f in zip(rec["diameter_nm"], frac)
                                                 if d > LARGE_UM * UM_TO_NM),
            },
        })
    return out


def _gaps(smoke_bins: list[dict], moments: list[dict]) -> list[dict]:
    tem = next(s for s in smoke_bins if s["material"] == "Lampwick" and s["variant"] == "all")
    mom = next((m for m in moments if m["material"] == "Lampwick" and m["run"] == tem["run"]), None)
    disagree = "Different methods give different sizes for the same smoke, so they are never mixed in one series."
    if mom is not None:
        disagree += (f" Example: cotton lamp wick run {tem['run']} is "
                     f"{tem['stats']['geometric_mean_diameter_nm']:.0f} nm on microscope images and "
                     f"{mom['diameter_nm'][0]:.0f} nm from instrument totals. The cause was not investigated.")
    def in_text(names: set[str]) -> str:  # "cotton lamp wick, Kapton and silicone" (trade names keep capitals)
        words = sorted(MATERIAL_LABELS.get(n, n) if n in ("Kapton", "Pyrell", "Teflon")
                       else MATERIAL_LABELS.get(n, n).lower() for n in names)
        return words[0] if len(words) == 1 else f"{', '.join(words[:-1])} and {words[-1]}"

    tem_set = {s["material"] for s in smoke_bins}
    no_tem_set = {m["material"] for m in moments} - tem_set
    return [
        {"id": "lunar_dust", "text": (
            "No lunar dust or lunar dust simulant data exists in these PSI files. The only dust measured (DAFT) is "
            "Arizona Road Dust. So \"could lunar dust fool a smoke detector?\" is an open question here, not an "
            "answered one.")},
        {"id": "dust_sizes", "text": (
            "DAFT measured the total number and the total mass of dust particles, not their sizes. With no dust "
            "size distribution, smoke and dust sizes cannot be compared bin by bin, so no overlap is computed.")},
        {"id": "detector_sensitivity", "text": (
            "We have no cited source for which particle sizes ionization and light-scattering smoke detectors "
            "respond to, so the page does not show detector size ranges.")},
        {"id": "detector_signals", "text": (
            "The SAME-R results workbook lists smoke detector and ionization chamber voltages per run. One column "
            "is empty, one is all zero, and the offsets and baselines are not explained, so these signals are "
            "not shown.")},
        {"id": "size_definitions_disagree", "text": disagree},
        {"id": "tem_coverage", "text": (
            f"Microscope size distributions are available here for one run each of {in_text(tem_set)}. "
            f"{in_text(no_tem_set)} have per-run instrument totals only.")},
        {"id": "simulation_units", "text": (
            "The unit of the PSI-115 values could not be confirmed. Each simulated curve is shown as a share of "
            "its own count; totals are not compared.")},
        {"id": "simulation_vs_experiment", "text": (
            "The PSI-115 model uses a stand-in smoke (dibutyl phthalate), not the SAME-R materials, and its "
            "particles are several micrometres across, much larger than most SAME-R smoke. It is shown on its "
            "own chart.")},
        {"id": "daft_bag_mapping", "text": (
            "Which DAFT instrument log belongs to which dust bag is not confirmed. Only the per-bag averages "
            "from the DAFT summary workbook are used.")},
        {"id": "same_files", "text": (
            "No SAME (PSI-102) measurement files are in this repository; only its 8-row sample list is used, "
            "in the catalog.")},
    ]


def _stable(x):
    """Round floats to 10 significant digits so Windows and Linux builds give the same JSON."""
    if isinstance(x, float):
        return float(f"{x:.10g}")
    if isinstance(x, dict):
        return {k: _stable(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_stable(v) for v in x]
    return x


def build() -> dict:
    """Assemble artifacts/detection.json in the contract shape from the committed raw files."""
    from engine import __version__

    moments = parse_same_r_moments(_raw("PSI-101", RESULTS_FILE))
    smoke_bins = _smoke_bins()
    used = ([_raw("PSI-101", f) for _, _, f in TEM_RUNS] + [_raw("PSI-101", RESULTS_FILE)]
            + [_raw("PSI-47", DAFT_SUMMARY_FILE), _raw("PSI-47", DAFT_TABLE_FILE), _raw("PSI-115", NODE_FILE)]
            + [_raw("PSI-115", f) for f, *_ in SIM_RUNS])
    return _stable({
        "schema_version": SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        "engine_version": __version__,
        "generated_by": "engine/detection.py",
        "title": "Detection evidence",
        "verdict": "partial",
        "scope_note": (
            "Reduced scope. The planned chart of smoke sizes against dust sizes cannot be built: the dust "
            "experiment (DAFT) recorded only total dust number and mass, not sizes, and its dust is Arizona "
            "Road Dust. This page shows what the files do support: smoke size distributions, smoke sizes per "
            "test run, one like-for-like size comparison of smoke and dust, and a simulation of what gravity "
            "does to smoke. See ADR-0007."),
        "generated_from": _generated_from(used),
        "gaps": _gaps(smoke_bins, moments),
        "size_definitions": SIZE_DEFINITIONS,
        "smoke_bins": smoke_bins,
        "smoke_runs": _smoke_runs(moments),
        "average_mass_comparison": _average_mass_comparison(moments),
        "simulation": _simulation(),
    })


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    art = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(art, indent=1, allow_nan=False, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT).as_posix()} ({len(art['generated_from'])} source files, "
          f"{len(art['gaps'])} gaps)")
    for s in art["smoke_bins"]:
        st = s["stats"]
        print(f"  {s['id']}: n={st['particle_count']:.0f} median={st['count_median_diameter_nm']:.0f} nm "
              f"gm={st['geometric_mean_diameter_nm']:.0f} nm gsd={st['geometric_std']:.2f} "
              f"[{s['source']['sheet']} rows {s['source']['rows']}]")
    for b in art["smoke_runs"]["by_material"]:
        print(f"  {b['material']:<8} aged={b['aged']!s:<5} n={b['n_runs']:>2} Dg median={b['dg_nm']['median']:.0f} "
              f"({b['dg_nm']['min']:.0f}-{b['dg_nm']['max']:.0f}) nm gsd={b['geometric_std_median']:.2f} "
              f"DAM median={b['diameter_of_average_mass_nm_median']:.0f} nm")
    cmp_ = art["average_mass_comparison"]
    print(f"  smoke DAM {cmp_['smoke']['range_nm']['min']:.0f}-{cmp_['smoke']['range_nm']['max']:.0f} nm "
          f"({len(cmp_['smoke']['points'])} runs); {cmp_['dust']['label']} DAM "
          + ", ".join(f"bag {p['bag']} {p['value_nm']:.0f} nm" for p in cmp_["dust"]["points"]))
    for s in art["simulation"]:
        st = s["stats"]
        print(f"  {s['id']}: median={st['count_median_diameter_nm'] / 1000:.2f} um "
              f"peak={st['peak_diameter_nm'] / 1000:.1f} um above20um={st['share_of_count_above_20um']:.4f}")


if __name__ == "__main__":
    main()
