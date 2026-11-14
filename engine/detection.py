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
"""
from __future__ import annotations

import itertools
import math
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
