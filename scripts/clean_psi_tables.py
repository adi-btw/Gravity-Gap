"""Clean and merge PSI combustion experimental tables into tidy datasets.

Input : data/psi_experimental_tables/*.csv  (downloaded from psi.nasa.gov)
Output: data/clean/
    psi_tests.csv              one row per individual test (ISS microgravity runs)
    psi_saffire_ug_vs_1g.csv   SAFFIRE-II microgravity vs normal-gravity comparison
    psi_test_day_summaries.csv one row per test day / condition range (ACME summaries, FLEX-2, SLICE)
    CLEANING_REPORT.md         what was dropped, fixed and flagged

Rules:
  * Never invent values. Anything missing or unparseable becomes empty, and a flag says why.
  * Every row keeps source_file + source_row (1 = first data row of the original CSV).
  * Every fix to a source value is recorded in quality_flags.

Run:  python scripts/clean_psi_tables.py
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "psi_experimental_tables"
OUT = ROOT / "data" / "clean"

ATM_PER_BAR = 1 / 1.01325
ATM_PER_MMHG = 1 / 760.0

UNIFIED_COLUMNS = [
    "record_id", "investigation_id", "investigation", "hardware", "platform",
    "fuel_phase", "configuration", "test_id", "test_date", "fuel", "fuel_mole_fraction",
    "gravity",
    "o2_mole_fraction", "o2_mole_fraction_final", "o2_context",
    "pressure_atm", "n2_mole_fraction", "co2_mole_fraction", "he_mole_fraction",
    "flow_speed_cm_s", "flow_direction",
    "size_mm", "size_kind",
    "ignited", "outcome", "burn_time_s", "extinction_diameter_mm", "burning_rate_source_units",
    "cool_flame", "adiabatic_flame_temp_k", "stoich_mixture_fraction",
    "notes", "quality_flags", "source_file", "source_row",
]

REPORT: list[str] = []


# ----------------------------------------------------------------------------- helpers
def read(name: str) -> pd.DataFrame:
    df = pd.read_csv(SRC / name, encoding="utf-8-sig", dtype=str, encoding_errors="replace")
    df.columns = [c.strip() for c in df.columns]
    for c in df.columns:
        df[c] = df[c].str.strip().replace("", np.nan)
    df["source_row"] = np.arange(1, len(df) + 1)
    df["source_file"] = name
    return df


NON_NUMERIC_MARKERS = ("RAMP", "LOW O2", "#DIV/0!", "#VALUE!", "#N/A")


def num(value) -> float:
    """Leading number in a string ('~ 21.5' -> 21.5, '20 cm/s' -> 20, '0.27 mm' -> 0.27).

    The value must START with a number (after an optional ~ < > sign), so text such as
    'LOW O2' or '#DIV/0!' becomes NaN instead of being misread as 2 or 0.
    """
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    m = re.match(r"\s*[~<>]?\s*(-?\d+(?:\.\d+)?|-?\.\d+)", str(value))
    return float(m.group(1)) if m else np.nan


def marker_rows(d: pd.DataFrame) -> pd.Series:
    """Rows where a numeric column holds a text marker like RAMP / LOW O2 / #DIV/0!."""
    return d.apply(lambda s: s.astype(str).str.upper().str.startswith(NON_NUMERIC_MARKERS)).any(axis=1)


def range_mean(value) -> float:
    """'21.5 - 21.7' or '22.1 to 22.0' -> mean of the numbers found."""
    nums = re.findall(r"\d+(?:\.\d+)?", str(value)) if pd.notna(value) else []
    return float(np.mean([float(n) for n in nums])) if nums else np.nan


def yyddd_date(code) -> str | float:
    """ACME/CIR test codes start with YYDDD (two-digit year, day of year)."""
    m = re.match(r"\s*(\d{2})(\d{3})", str(code)) if pd.notna(code) else None
    if not m:
        return np.nan
    year, doy = 2000 + int(m.group(1)), int(m.group(2))
    if not 1 <= doy <= 366:
        return np.nan
    return (dt.date(year, 1, 1) + dt.timedelta(days=doy - 1)).isoformat()


def iso_date(value, fmt: str) -> str | float:
    try:
        return dt.datetime.strptime(str(value).strip(), fmt).date().isoformat()
    except (ValueError, TypeError):
        return np.nan


def yes_no(value):
    if pd.isna(value):
        return np.nan
    v = str(value).strip().lower()
    if v.startswith("yes") or v == "flash":
        return True
    if v.startswith("no"):
        return False
    return np.nan


def add_flag(df: pd.DataFrame, mask, flag: str) -> None:
    mask = pd.Series(mask, index=df.index).fillna(False).astype(bool)
    cur = df["quality_flags"].fillna("").astype(str)
    df.loc[mask, "quality_flags"] = (cur[mask] + ";" + flag).str.strip(";")


def finish(df: pd.DataFrame, inv_id: str, inv: str, hardware: str, platform: str, phase: str) -> pd.DataFrame:
    df = df.copy()
    df["investigation_id"], df["investigation"] = inv_id, inv
    df["hardware"], df["platform"], df["fuel_phase"] = hardware, platform, phase
    df["gravity"] = "microgravity"
    for c in UNIFIED_COLUMNS:
        if c not in df.columns:
            df[c] = np.nan
    df["quality_flags"] = df["quality_flags"].replace("", np.nan)
    table = df["source_file"].str.extract(r"table_(.+)\.csv", expand=False)
    df["record_id"] = inv_id + ":" + table + ":" + df["source_row"].astype(str)
    return df[UNIFIED_COLUMNS]


def drop_blank_and_dupes(df: pd.DataFrame, name: str, key_cols: list[str]) -> pd.DataFrame:
    data_cols = [c for c in df.columns if c not in ("source_row", "source_file")]
    blank = df[data_cols].isna().all(axis=1)
    dupes = df[data_cols].duplicated() & ~blank
    if blank.any() or dupes.any():
        REPORT.append(f"- `{name}`: dropped {int(blank.sum())} blank rows and {int(dupes.sum())} exact duplicate rows")
    df = df[~blank & ~dupes]
    missing_key = df[key_cols].isna().all(axis=1)
    if missing_key.any():
        REPORT.append(f"- `{name}`: dropped {int(missing_key.sum())} rows with no test identifier (notes/footnotes)")
    return df[~missing_key].copy()


def new_frame(d: pd.DataFrame) -> pd.DataFrame:
    o = pd.DataFrame(index=d.index)
    o["source_file"], o["source_row"] = d["source_file"], d["source_row"]
    o["quality_flags"] = ""
    return o


# ----------------------------------------------------------------------------- per-test loaders
def flex() -> pd.DataFrame:
    name = "PSI-69_Experimental_table_FLEX.csv"
    d = drop_blank_and_dupes(read(name), name, ["FLEX Identifier"])
    o = new_frame(d)
    o["test_id"] = d["FLEX Identifier"] + " (#" + d["FLEX Test #"] + ")"
    o["test_date"] = d["Test Date"].map(lambda v: iso_date(v, "%m/%d/%Y"))
    o["fuel"] = d["Fuel"]
    o["configuration"] = "droplet"
    p_mmhg = d["Ambient pressure; mmHg"].map(num)
    o["pressure_atm"] = p_mmhg.where(p_mmhg > 0) * ATM_PER_MMHG
    add_flag(o, p_mmhg.eq(0), "pressure_zero_in_source_treated_as_missing")
    o["o2_mole_fraction"] = d["O initial ambient composition; mole fraction"].map(num)
    o["o2_context"] = "ambient"
    o["n2_mole_fraction"] = d["N initial ambient composition; mole fraction"].map(num)
    o["co2_mole_fraction"] = d["CO initial ambient composition; mole fraction"].map(num)
    o["he_mole_fraction"] = d["He initial ambient composition; mole fraction"].map(num)
    o["size_mm"], o["size_kind"] = d["Droplet initial diameter; mm"].map(num), "droplet_initial_diameter"
    o["extinction_diameter_mm"] = d["Visible flame extinction diameter; mm"].map(num)
    o["burning_rate_source_units"] = d["Burning rate; mm"].map(num)
    o["burn_time_s"] = d["Burn time; s"].map(num)
    o["ignited"] = True
    o["outcome"] = d["Test end"].str.lower()
    add_flag(o, d["FLEX Identifier"].duplicated(keep=False), "duplicate_flex_identifier_in_source")
    add_flag(o, True, "burning_rate_units_listed_as_mm_in_source")
    return finish(o, "PSI-69", "FLEX", "CIR / MDCA", "ISS", "liquid")


def cfi() -> pd.DataFrame:
    name = "PSI-39_Experimental_table_CFI.csv"
    d = drop_blank_and_dupes(read(name), name, ["Flex Number"])
    o = new_frame(d)
    o["test_id"] = d["Flex Number"] + " / " + d["CIR"]
    o["test_date"] = d["Test Date"].map(lambda v: iso_date(v, "%d-%b-%y"))
    o["fuel"] = d["Fuel"]
    o["configuration"] = np.where(d["Fiber"].str.lower() == "yes", "droplet (fiber-supported)", "droplet")
    o["pressure_atm"] = d["Pressure"].map(num)
    o["o2_mole_fraction"], o["o2_context"] = d["Oxygen"].map(num), "ambient"
    o["n2_mole_fraction"] = d["Nitrogen"].map(num)
    o["he_mole_fraction"] = d["Helium"].map(num)
    add_flag(o, True, "no_outcome_in_table")
    return finish(o, "PSI-39", "CFI", "CIR / MDCA", "ISS", "liquid")


def cfig() -> pd.DataFrame:
    frames = []
    for name, kind in [("PSI-159_Experimental_table_CFI-G_Normal_Flames.csv", "normal"),
                       ("PSI-159_Experimental_table_CFI-G_Inverse_Flames.csv", "inverse")]:
        d = drop_blank_and_dupes(read(name), name, ["Test"])
        d.columns = [re.sub(r"\s+", " ", c) for c in d.columns]
        o = new_frame(d)
        o["test_id"] = d["Test"].str.replace(" ", "", regex=False)
        o["test_date"] = o["test_id"].map(yyddd_date)
        o["fuel"] = d["Fuel"]
        o["configuration"] = f"spherical porous burner ({kind} flame)"
        o["pressure_atm"] = d["approx p (bar)"].map(num) * ATM_PER_BAR
        if kind == "normal":
            o["o2_mole_fraction"] = d["XO2 before test"].map(num)
            o["o2_mole_fraction_final"] = d["XO2 after test"].map(num)
            o["o2_context"] = "ambient"
            o["fuel_mole_fraction"] = d["Xf"].map(num)
            o["cool_flame"] = d["Cool flame?"].map(yes_no)
            burner_t_k = d["Peak burner T (C )"].map(num) + 273.15
            outcome_col = "Self-ext or flow term"
        else:
            o["o2_mole_fraction"] = d["XO2"].map(num)
            o["o2_context"] = "burner_oxidizer_stream"
            o["fuel_mole_fraction"] = d["Xf before test"].map(num)
            burner_t_k = d["Peak burner temp (K)"].map(num)
            outcome_col = "Self -ext or flow term"
        if "cool_flame" not in o:
            o["cool_flame"] = np.nan
        hot = d["Hot ignition"].str.lower()
        o["burn_time_s"] = d["burn time (sec)"].map(num)
        o["adiabatic_flame_temp_k"] = d["Tad (K)"].map(num)
        o["stoich_mixture_fraction"] = d["Zst"].map(num)
        ignited = hot.isin(["yes", "flash"]) | o["cool_flame"].eq(True) | (o["burn_time_s"] > 0)
        o["ignited"] = ignited
        se = d[outcome_col].map({"SE": "self_extinguished", "FT": "flow_terminated"})
        o["outcome"] = np.select([~ignited, hot.eq("flash"), se.notna()],
                                 ["no_ignition", "flash_only", se.fillna("")], default="")
        o["outcome"] = o["outcome"].replace("", np.nan)
        parts = [d["Comments"]]
        if "Color" in d:
            parts.append(("color=" + d["Color"]).where(d["Color"].notna() & (d["Color"] != "-")))
        parts.append(("peak_burner_temp_K=" + burner_t_k.round(1).astype(str)).where(burner_t_k.notna()))
        o["notes"] = pd.concat(parts, axis=1).apply(lambda r: "; ".join(str(x) for x in r if pd.notna(x)), axis=1)
        add_flag(o, True, "pressure_approximate_in_source")
        add_flag(o, ignited & o["outcome"].isna(), "ignited_but_end_reason_not_recorded")
        add_flag(o, marker_rows(d), "text_marker_in_numeric_column_set_to_missing")
        frames.append(finish(o, "PSI-159", "ACME CFI-G", "CIR / ACME", "ISS", "gas"))
    return pd.concat(frames)


def flame_design() -> pd.DataFrame:
    frames = []
    for name, kind in [("PSI-10_Experimental_table_Flame_Design_Normal_Flame.csv", "normal"),
                       ("PSI-10_Experimental_table_Flame_Design_Inverse_Flame.csv", "inverse")]:
        d = drop_blank_and_dupes(read(name), name, ["Test"])
        o = new_frame(d)
        o["test_id"] = d["Test"]
        o["test_date"] = o["test_id"].map(yyddd_date)
        o["configuration"] = f"spherical porous burner ({kind} flame)"
        o["pressure_atm"] = d["pmean (atm)"].map(num)
        o["adiabatic_flame_temp_k"] = d["Tad (K)"].map(num)
        o["stoich_mixture_fraction"] = d["mean Zst"].map(num)
        if kind == "normal":
            o["fuel"] = d["Fuel"]
            o["fuel_mole_fraction"] = d["Xfuel"].map(num)
            o["o2_mole_fraction"] = d["XO2 (init)"].map(num)
            o["o2_mole_fraction_final"] = d["XO2 (final)"].map(num)
            o["o2_context"] = "ambient"
        else:
            o["fuel"] = "C2H4"
            o["fuel_mole_fraction"] = d["XC2H4 initial"].map(num)
            o["o2_mole_fraction"] = d["XO2"].map(num)
            o["o2_context"] = "burner_oxidizer_stream"
        add_flag(o, True, "no_outcome_in_table")
        add_flag(o, marker_rows(d), "text_marker_in_numeric_column_set_to_missing")
        frames.append(finish(o, "PSI-10", "ACME Flame Design", "CIR / ACME", "ISS", "gas"))
    return pd.concat(frames)


def spice() -> pd.DataFrame:
    name = "PSI-107_Experimental_table_Spice.csv"
    d = drop_blank_and_dupes(read(name), name, ["GMT ignition"])
    d.columns = [re.sub(r"\s+", " ", c) for c in d.columns]
    o = new_frame(d)
    o["test_id"] = "doy" + d["GMT date"] + "_" + d["GMT ignition"].str.replace(":", "", regex=False)
    o["fuel"] = d["Fuel"].str.replace(r"\s*%\s*", "% ", regex=True)
    o["configuration"] = "coflow jet flame"
    o["size_mm"], o["size_kind"] = d["Nozzle (mm)"].map(num), "nozzle_diameter"
    o["flow_speed_cm_s"], o["flow_direction"] = d["Air Rate (cm/s)"].map(num), "coflow"
    o["quality_flags"] = ("year_not_in_table;burn_time_derived_from_gmt_times;"
                          "o2_and_pressure_not_in_table;several_rows_can_share_one_flame")
    add_flag(o, o["flow_speed_cm_s"] < 0, "negative_air_rate_in_source_near_zero_coflow")
    times = {}
    for col in ("GMT ignition", "GMT Flame Off"):
        dotted = d[col].str.fullmatch(r"\d{1,2}\.\d{2}\.\d{2}", na=False)
        add_flag(o, dotted, f"{col.lower().replace(' ', '_')}_dots_read_as_colons")
        times[col] = pd.to_timedelta(d[col].str.replace(".", ":", regex=False), errors="coerce")
    dur = (times["GMT Flame Off"] - times["GMT ignition"]).dt.total_seconds()
    o["burn_time_s"] = dur.where(dur >= 0)
    add_flag(o, dur < 0, "flame_off_before_ignition_in_source_burn_time_missing")
    add_flag(o, dur.isna(), "flame_off_time_missing")
    los = d["GMT ignition"].str.upper().eq("LOS")  # loss of signal: no telemetry for this flame
    o["ignited"] = pd.Series(True, index=d.index, dtype=object).where(~los, np.nan)
    o["flow_speed_cm_s"] = o["flow_speed_cm_s"].where(~los)
    add_flag(o, los, "loss_of_signal_in_source_flow_and_ignition_unknown")
    o["notes"] = "GMT day-of-year " + d["GMT date"] + "; fuel rate " + d["Fuel Rate (mg/s)"].fillna("?") + " mg/s"
    return finish(o, "PSI-107", "SPICE", "MSG / SPICE flow duct", "ISS", "gas")


def bass() -> pd.DataFrame:
    name = "PSI-26_Experimental_table_BASS.csv"
    d = drop_blank_and_dupes(read(name), name, ["Test #"])
    o = new_frame(d)
    o["test_id"] = "run " + d["As Run Test #"].fillna("?") + " / test " + d["Test #"]
    o["test_date"] = d["Date"].map(lambda v: iso_date(v, "%m/%d/%Y"))
    o["fuel"] = d["Fuel Sample Material"]
    o["configuration"] = np.where(d["Fuel Sample Material"].str.contains("sphere", case=False, na=False), "sphere", "sample")
    size_cm = d["Fuel Sample Material"].str.extract(r"(\d+(?:\.\d+)?)\s*cm", expand=False).astype(float)
    o["size_mm"], o["size_kind"] = size_cm * 10, "sample_dimension"
    o["quality_flags"] = "conditions_not_in_table;no_outcome_in_table"
    return finish(o, "PSI-26", "BASS", "MSG / SPICE flow duct", "ISS", "solid")


def bass2() -> pd.DataFrame:
    name = "PSI-25_Experimental_table_BASS-II.csv"
    d = drop_blank_and_dupes(read(name), name, ["Test #"])
    d.columns = [re.sub(r"\s+", " ", c).strip() for c in d.columns]
    o = new_frame(d)
    o["test_id"] = d["Test #"]
    o["test_date"] = d["Date"].map(lambda v: iso_date(v, "%m/%d/%Y"))
    o["fuel"] = d["Fuel Sample Material"].str.replace(r"\s+", " ", regex=True)
    o["configuration"] = "sample in flow duct"
    o["o2_mole_fraction"] = d["Calibrated initial O2 % by vol"].map(num) / 100
    o["o2_mole_fraction_final"] = d["Calibrated final O2 % by vol"].map(num) / 100
    o["o2_context"] = "ambient"
    o["co2_mole_fraction"] = d["Initial CO2 % by vol"].map(num) / 100
    mat = d["Fuel Sample Material"].fillna("")
    micron = mat.str.extract(r"(\d+(?:\.\d+)?)\s*micron", expand=False).astype(float) / 1000
    mm = mat.str.extract(r"(\d*\.\d+|\d+)\s*mm", expand=False).astype(float)
    o["size_mm"] = micron.fillna(mm)
    o["size_kind"] = np.where(o["size_mm"].notna(), "sample_thickness", None)
    o["notes"] = ("PI=" + d["PI"].fillna("?") + "; fan_display=" + d["Fan display"].fillna("?")
                  + "; air_display=" + d["Air display"].fillna("?")
                  + "; CO_ppm " + d["Initial CO (ppm)"].fillna("?") + "->" + d["Final CO (ppm)"].fillna("?"))
    o["quality_flags"] = "flow_settings_kept_raw_units_unknown;no_outcome_in_table"
    return finish(o, "PSI-25", "BASS-II", "MSG / SPICE flow duct", "ISS", "solid")


def saffire() -> tuple[pd.DataFrame, pd.DataFrame]:
    frames, comparison = [], None
    specs = [("PSI-98", "SAFFIRE-I", "PSI-98_Experimental_table_SAFFIRE-1.csv"),
             ("PSI-99", "SAFFIRE-II", "PSI-99_Experimental_table_SAFFIRE-2.csv"),
             ("PSI-100", "SAFFIRE-III", "PSI-100_Experimental_table_SAFFIRE-3.csv")]
    for inv_id, inv, name in specs:
        d = read(name)
        d.columns = [re.sub(r"\s+", " ", c).strip() for c in d.columns]
        sample_col = d.columns[0]
        footnotes = d[sample_col].fillna("").str.match(r"(?i)note\s*\d")
        notes_text = " | ".join(d.loc[footnotes, sample_col])
        is_test = d[sample_col].fillna("").str.match(r"^(S\d+|\d+-\d+)$")
        REPORT.append(f"- `{name}`: kept {int(is_test.sum())} test rows; dropped {int((~is_test).sum())} "
                      f"rows (flow-visualisation entries and footnotes; footnotes copied into notes)")
        d = d[is_test].copy()
        o = new_frame(d)
        o["test_id"] = d[sample_col]
        mat = d["Material"]
        add_flag(o, mat.isna(), "material_blank_in_source_filled_from_row_above")
        o["fuel"] = mat.ffill()
        o["configuration"] = "large flat sample (Cygnus)"
        thick_col = next(c for c in d.columns if "thick" in c.lower())
        raw = d[thick_col].fillna("")
        typo = raw.str.match(r"^0\d+\s*mm$")
        add_flag(o, typo, "thickness_typo_037mm_read_as_0.37mm")
        fixed = raw.where(~typo, raw.str.replace(r"^0(\d+)", r"0.\1", regex=True))
        val = fixed.map(num)
        in_cm = (fixed.str.contains("cm") & ~fixed.str.contains("mm")) | (
            thick_col.lower().endswith("(cm)") & ~fixed.str.contains("mm"))
        o["size_mm"] = np.where(in_cm, val * 10, val)
        o["size_kind"] = "sample_thickness"
        add_flag(o, pd.isna(o["size_mm"]) & raw.ne(""), "thickness_not_numeric_in_source")
        flow_col = next(c for c in d.columns if "air flow" in c.lower())
        o["flow_speed_cm_s"] = d[flow_col].map(num)
        dir_col = next(c for c in d.columns if "direction" in c.lower())
        o["flow_direction"] = d[dir_col].str.lower()
        o2_col = next((c for c in d.columns if "o2" in c.lower()), None)
        if o2_col:
            o["o2_mole_fraction"] = d[o2_col].map(range_mean) / 100
            o["o2_context"] = "ambient"
            add_flag(o, d[o2_col].str.contains("~|-|to", na=False), "o2_approximate_or_range_mean")
        else:
            add_flag(o, True, "o2_not_in_table")
        bt_col = next((c for c in d.columns if "burn time" in c.lower()), None)
        if bt_col:
            insignificant = d[bt_col].str.lower().eq("insignificant")
            o["burn_time_s"] = np.where(insignificant, 0.0, d[bt_col].map(num))
            add_flag(o, insignificant, "burn_time_insignificant_set_to_0")
        o["notes"] = notes_text or np.nan
        if inv == "SAFFIRE-II":
            ug_len = d["?-g Burn Length"]
            o["ignited"] = True
            o["outcome"] = np.select(
                [ug_len.str.startswith("~ 0", na=False), ug_len.eq("29 cm")],
                ["no_sustained_burn", "complete_burn"], default="partial_burn")
            comparison = saffire_comparison(d, o)
        else:
            add_flag(o, True, "no_outcome_in_table")
        frames.append(finish(o, inv_id, inv, "Saffire flow unit on Cygnus", "Cygnus (after leaving ISS)", "solid"))
    return pd.concat(frames), comparison


def saffire_comparison(d: pd.DataFrame, o: pd.DataFrame) -> pd.DataFrame:
    sample_len_cm = d["Sample Length"].map(num)

    def length_cm(raw: pd.Series) -> np.ndarray:
        return np.where(raw.str.lower().str.startswith("complete", na=False), sample_len_cm, raw.map(num))

    def rate(raw: pd.Series) -> pd.Series:
        return raw.where(raw.str.contains("mm/s", na=False)).map(num)

    c = pd.DataFrame({
        "sample": d["Sample Number"],
        "material": o["fuel"],
        "thickness_mm": o["size_mm"],
        "sample_length_cm": sample_len_cm,
        "flow_speed_cm_s": o["flow_speed_cm_s"],
        "flow_direction": o["flow_direction"],
        "o2_mole_fraction": o["o2_mole_fraction"],
        "ug_burn_length_raw": d["?-g Burn Length"],
        "ug_burn_length_cm": d["?-g Burn Length"].map(num),
        "ug_spread_rate_raw": d["?-g Spread Length"],
        "ug_spread_rate_mm_s": rate(d["?-g Spread Length"]),
        "1g_burn_length_raw": d["1-g Burn Length"],
        "1g_burn_length_cm": length_cm(d["1-g Burn Length"]),
        "1g_spread_rate_raw": d["1-g Spread Rate"],
        "1g_spread_rate_mm_s": rate(d["1-g Spread Rate"]),
        "1g_spread_accelerating": d["1-g Spread Rate"].str.lower().eq("acceleratory"),
    })
    c["ug_burned_fraction"] = (c["ug_burn_length_cm"] / c["sample_length_cm"]).clip(upper=1)
    c["1g_burned_fraction"] = (c["1g_burn_length_cm"] / c["sample_length_cm"]).clip(upper=1)
    diff = c["1g_burned_fraction"] - c["ug_burned_fraction"]
    c["which_burned_more"] = np.select([diff > 0.05, diff < -0.05, diff.notna()],
                                       ["normal_gravity", "microgravity", "similar"], default="unknown")
    c["needs_manual_review"] = c["material"].str.contains("&", na=False) | c["ug_burn_length_raw"].str.contains("note", case=False, na=False)
    c["note"] = ("1-g 'Complete' converted to the full sample length; '~ 0' read as 0. "
                 "Multi-material and footnoted samples need the source notes.")
    c["source_file"], c["source_row"] = d["source_file"].values, d["source_row"].values
    return c


# ----------------------------------------------------------------------------- day summaries
def fmt_num(x: float) -> str:
    return f"{x:g}"


def day_summaries() -> pd.DataFrame:
    rows = []

    def base(r, inv_id, inv):
        return {"investigation_id": inv_id, "investigation": inv,
                "source_file": r["source_file"], "source_row": r["source_row"]}

    # BRE
    name = "PSI-20_Experimental_table_ACME_BRE.csv"
    for _, r in read(name).iterrows():
        raw = str(r["Oxygen Conc (percent)"])
        flags = []
        if re.fullmatch(r"\d{3,4}%", raw):
            raw = str(int(raw.rstrip("%")) // 100)
            flags.append("excel_percent_artifact_fixed")
        levels = "; ".join(fmt_num(num(x)) for x in raw.split(";") if not np.isnan(num(x)))
        date = iso_date(f'{r["Year"]} {r["Month"][:3]} {r["Date"]}', "%Y %b %d")
        rows.append({**base(r, "PSI-20", "ACME BRE"), "test_date": date,
                     "fuel": str(r["Fuel Bottle"]).replace("100%C2H4", "100% C2H4"),
                     "burner_size_mm": num(r["Burner Size (mm)"]), "o2_levels_percent": levels,
                     "flames_ignited": num(r["Flames Ignited"]),
                     "quality_flags": ";".join(flags + ["pressure_not_in_table", "ignitions_not_split_by_o2_level"])})
    REPORT.append(f"- `{name}`: fixed Excel '%' artifacts ('3400%' -> 34, '2100%' -> 21); kept as day summaries")

    # CLD Flame
    name = "PSI-21_Experimental_table_CLD_Flame.csv"
    for _, r in read(name).iterrows():
        src = str(r["Fuel Bottle"])
        fuel = re.sub(r"CH\d+$", "CH4", src) if re.search(r"CH\d+$", src) else src
        rows.append({**base(r, "PSI-21", "ACME CLD Flame"), "test_date": yyddd_date(r["Test Day"]),
                     "test_type": r["Test Type"], "fuel": fuel, "fuel_concentration": r["Fuel conc. Range"],
                     "flames_ignited": num(r["Flames ignited"]),
                     "quality_flags": "fuel_label_autofill_fixed" if fuel != src else np.nan})
    REPORT.append(f"- `{name}`: fixed spreadsheet auto-fill in fuel labels ('40% CH5', 'CH6', ... -> '40% CH4')")

    # E-FIELD
    for _, r in read("PSI-22_Experimental_table_ACME_E-FIELD_Flames.csv").iterrows():
        rows.append({**base(r, "PSI-22", "ACME E-FIELD Flames"), "test_date": yyddd_date(r["Test Day"]),
                     "test_type": r["Test Type"], "fuel": r["Fuel Bottle"], "fuel_concentration": r["Fuel Conc"],
                     "mesh_polarity": r["Mesh Polarity"], "flames_ignited": num(r["Flames Ignited"]),
                     "quality_flags": "voltage_and_ion_current_not_in_table"})

    # s-Flame
    name = "PSI-23_Experimental_table_ACME_s-Flame.csv"
    d = read(name)
    d.columns = [c.rstrip("*") for c in d.columns]
    for _, r in d.iterrows():
        atm = re.sub(r"with N\d+", "with N2", str(r["Atmosphere"]))
        fuel = re.sub(r"with N\d+", "with N2", str(r["Fuel Bottle"]))
        fixed = atm != r["Atmosphere"] or fuel != r["Fuel Bottle"]
        rows.append({**base(r, "PSI-23", "ACME s-Flame"), "test_date": yyddd_date(r["Test Day"]),
                     "test_type": r["Test Type"], "fuel": fuel, "atmosphere": atm,
                     "o2_levels_percent": fmt_num(num(atm)),
                     "flames_ignited": num(r["Flames Ignited"]),
                     "quality_flags": ";".join((["diluent_label_autofill_fixed"] if fixed else []) + ["o2_approximate"])})
    REPORT.append(f"- `{name}`: fixed auto-fill in diluent labels ('N3', 'N4', ... -> 'N2')")

    # SLICE
    for _, r in read("PSI-106_Experimental_table_Slice.csv").iterrows():
        date_raw = str(r["Test Date"])
        m = re.match(r"(\d{4}-[A-Z]{3}-\d{2})", date_raw)
        rows.append({**base(r, "PSI-106", "SLICE"),
                     "test_date": iso_date(m.group(1).title(), "%Y-%b-%d") if m else np.nan,
                     "fuel": r["Fuel Type"], "test_type": (date_raw[m.end():].strip() if m else date_raw) or np.nan,
                     "quality_flags": "free_text_row"})

    # FLEX-2 condition ranges
    for _, r in read("PSI-68_Experimental_table_Flex2.csv").iterrows():
        o2 = re.findall(r"\d*\.\d+", str(r["Oxygen Mole Fraction"]))
        rows.append({**base(r, "PSI-68", "FLEX-2"), "test_type": "condition range (not individual tests)",
                     "fuel": r["Sample (Fuel Type)"], "atmosphere": r["Ambient Gas Mixture"],
                     "o2_levels_percent": "; ".join(fmt_num(round(float(x) * 100, 1)) for x in o2),
                     "pressure_levels_atm": str(r["Ambient Pressure (atm)"]).replace("or", "").strip(),
                     "flow_speed_range_cm_s": r["Flow Velocity (cm/s)"],
                     "droplet_diameter_range_mm": r["Initial Droplet Diameter (mm)"],
                     "quality_flags": "ranges_only"})

    cols = ["investigation_id", "investigation", "test_date", "test_type", "fuel", "fuel_concentration",
            "atmosphere", "o2_levels_percent", "pressure_levels_atm", "burner_size_mm", "mesh_polarity",
            "flow_speed_range_cm_s", "droplet_diameter_range_mm", "flames_ignited",
            "quality_flags", "source_file", "source_row"]
    return pd.DataFrame(rows).reindex(columns=cols)


# ----------------------------------------------------------------------------- validation + main
def validate(tests: pd.DataFrame) -> list[str]:
    issues = []
    checks = {
        "o2_mole_fraction": (0, 1), "o2_mole_fraction_final": (0, 1), "n2_mole_fraction": (0, 1),
        "co2_mole_fraction": (0, 1), "he_mole_fraction": (0, 1), "pressure_atm": (0.05, 10),
        # flow lower bound -1: SPICE logs small negative readings at zero coflow (flagged per row)
        "burn_time_s": (0, 7200), "size_mm": (0, 1000), "flow_speed_cm_s": (-1, 200),
        "adiabatic_flame_temp_k": (300, 3500),
    }
    for col, (lo, hi) in checks.items():
        v = pd.to_numeric(tests[col], errors="coerce")
        bad = v.notna() & ((v < lo) | (v > hi))
        if bad.any():
            issues.append(f"- {col}: {int(bad.sum())} values outside [{lo}, {hi}] "
                          f"(e.g. {tests.loc[bad, 'record_id'].head(3).tolist()})")
    gas = tests[["o2_mole_fraction", "n2_mole_fraction", "co2_mole_fraction", "he_mole_fraction"]].apply(pd.to_numeric, errors="coerce")
    full = gas.notna().all(axis=1)
    off = full & ((gas.sum(axis=1) - 1).abs() > 0.03)
    if off.any():
        issues.append(f"- ambient gas fractions do not sum to 1 (+/-0.03) for {int(off.sum())} tests "
                      f"(e.g. {tests.loc[off, 'record_id'].head(3).tolist()})")
    if tests["record_id"].duplicated().any():
        issues.append(f"- duplicate record_id: {int(tests['record_id'].duplicated().sum())}")
    return issues


def md_table(df: pd.DataFrame) -> str:
    head = "| " + " | ".join(df.columns) + " |\n|" + "---|" * len(df.columns)
    body = "\n".join("| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False))
    return head + "\n" + body


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    saff, comparison = saffire()
    tests = pd.concat([flex(), cfi(), cfig(), flame_design(), spice(), bass(), bass2(), saff], ignore_index=True)
    days = day_summaries()
    for col in ("ignited", "cool_flame"):  # keep booleans as True/False/empty after concat
        tests[col] = tests[col].map(lambda v: np.nan if pd.isna(v) else bool(v)).astype(object)

    tests.to_csv(OUT / "psi_tests.csv", index=False)
    comparison.to_csv(OUT / "psi_saffire_ug_vs_1g.csv", index=False)
    days.to_csv(OUT / "psi_test_day_summaries.csv", index=False)

    issues = validate(tests)
    per_inv = tests.groupby(["investigation_id", "investigation"]).size().rename("tests").reset_index()
    key = ["o2_mole_fraction", "pressure_atm", "flow_speed_cm_s", "ignited", "outcome", "burn_time_s"]
    coverage = tests[key].notna().sum()
    flags = tests["quality_flags"].dropna().str.split(";").explode().value_counts()

    lines = ["# PSI cleaning report", "",
             f"Generated by `scripts/clean_psi_tables.py` on {dt.date.today().isoformat()}.", "",
             "## Outputs",
             f"- `psi_tests.csv`: {len(tests)} individual tests from {tests['investigation_id'].nunique()} investigations",
             f"- `psi_saffire_ug_vs_1g.csv`: {len(comparison)} SAFFIRE-II samples, microgravity vs normal gravity",
             f"- `psi_test_day_summaries.csv`: {len(days)} test-day / condition-range rows", "",
             "## Tests per investigation", md_table(per_inv), "",
             "## How many tests have each key field",
             *(f"- {k}: {int(v)} of {len(tests)}" for k, v in coverage.items()), "",
             "## Rows dropped and values fixed", *REPORT, "",
             "## Quality flags (count of tests)", *(f"- `{k}`: {int(v)}" for k, v in flags.items()), "",
             "## Validation (range checks)", *(issues or ["- All checked values are inside physical ranges."]), ""]
    (OUT / "CLEANING_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
