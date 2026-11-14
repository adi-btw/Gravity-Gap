"""T1 data-quality gates on data/clean/psi_tests.csv (plan/02 §4)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
TESTS_CSV = ROOT / "data" / "clean" / "psi_tests.csv"

EXPECTED_COUNTS = {
    "PSI-10": 327, "PSI-100": 2, "PSI-107": 434, "PSI-159": 333, "PSI-25": 129,
    "PSI-26": 121, "PSI-39": 79, "PSI-69": 274, "PSI-98": 2, "PSI-99": 9,
}


@pytest.fixture(scope="module")
def tests_df() -> pd.DataFrame:
    return pd.read_csv(TESTS_CSV, low_memory=False)


def _num(df, col):
    return pd.to_numeric(df[col], errors="coerce").dropna()


def test_total_rows(tests_df):
    assert len(tests_df) == sum(EXPECTED_COUNTS.values()) == 1710


def test_per_investigation_counts(tests_df):
    got = tests_df["investigation_id"].value_counts().to_dict()
    assert got == EXPECTED_COUNTS


def test_o2_range(tests_df):
    for col in ("o2_mole_fraction", "o2_mole_fraction_final"):
        s = _num(tests_df, col)
        assert ((s >= 0) & (s <= 1)).all(), f"{col} outside [0, 1]"


def test_pressure_range(tests_df):
    s = _num(tests_df, "pressure_atm")
    assert ((s >= 0.05) & (s <= 10)).all()


def test_flow_range(tests_df):
    s = _num(tests_df, "flow_speed_cm_s")
    assert ((s >= -1) & (s <= 200)).all()


def test_ambient_gas_fractions_sum_to_one(tests_df):
    cols = ["o2_mole_fraction", "n2_mole_fraction", "co2_mole_fraction", "he_mole_fraction"]
    amb = tests_df[tests_df["o2_context"] == "ambient"]
    frac = amb[cols].apply(pd.to_numeric, errors="coerce")
    # Only rows that give the full ambient breakdown (O2 and N2 present: FLEX, CFI).
    # Flame Design / CFI-G / SAFFIRE give O2 only and BASS-II gives O2 + CO2 only,
    # so their fractions cannot be summed.
    full = frac[frac["o2_mole_fraction"].notna() & frac["n2_mole_fraction"].notna()]
    assert len(full) >= 300
    total = full.fillna(0).sum(axis=1)
    bad = full[(total - 1).abs() > 0.03 + 1e-9]  # inclusive tolerance (CFI rows sum to 0.97)
    assert bad.empty, f"{len(bad)} rows with gas fractions not summing to 1 +- 0.03"


def test_record_id_unique_and_present(tests_df):
    assert tests_df["record_id"].notna().all()
    assert tests_df["record_id"].is_unique


def test_every_row_traces_to_source(tests_df):
    assert tests_df["source_file"].notna().all()
    assert (tests_df["source_file"].astype(str).str.len() > 0).all()
    rows = pd.to_numeric(tests_df["source_row"], errors="coerce")
    assert rows.notna().all() and (rows >= 1).all()


def test_source_files_exist(tests_df):
    raw = ROOT / "data" / "psi_experimental_tables"
    missing = [f for f in tests_df["source_file"].unique() if not (raw / f).exists()]
    assert not missing, missing


def test_all_tests_microgravity(tests_df):
    assert set(tests_df["gravity"].dropna()) == {"microgravity"}


def test_fuel_phase_vocabulary(tests_df):
    assert set(tests_df["fuel_phase"].dropna()) <= {"gas", "liquid", "solid"}
