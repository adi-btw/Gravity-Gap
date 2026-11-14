"""E2 data-driven models M1-M3 (TL). Fitted on microgravity PSI data only.

Training sets (ADR-0004, plan/decisions.md):
    M1  FLEX (PSI-69) droplets, outcome "extinction" (1) vs "completion" (0).
        "disruption" rows are EXCLUDED: the droplet broke apart, so we do not
        know whether the flame would have self-extinguished before burnout.
    M2  FLEX droplets with outcome "extinction" and a recorded
        extinction_diameter_mm (disruption rows with a diameter are excluded
        for the same reason).
    M3  ACME CFI-G (PSI-159) NORMAL flames only (o2_context == "ambient"),
        outcome "self_extinguished" (1) vs "flow_terminated" (0). Inverse
        flames are excluded because their O2 is the burner stream, not the
        cabin atmosphere; no_ignition / flash_only are excluded (not a burn).

Rows with a missing feature (1 FLEX pressure, 12 FLEX droplet sizes) are
dropped, never imputed (data/clean/README.md "no invented values").

Public API:
    get_model(metric, n_boot=500, seed=0) -> FittedModel   (cached)
    MODEL_SPECS                                           (feature metadata)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, QuantileRegressor
from sklearn.preprocessing import StandardScaler

CODE_VERSION = "m1m3-1"
DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "clean" / "psi_tests.csv"

FLEX_ID = "PSI-69"
CFIG_ID = "PSI-159"

M1_FEATURES = ["o2", "log_p", "he", "co2", "is_methanol", "droplet_mm"]
M2_FEATURES = M1_FEATURES
M3_FEATURES = ["o2", "log_p", "is_ethane", "is_propane", "fuel_fraction"]
M3_FUELS = ("ethane", "propane", "butane")  # butane is the one-hot baseline
FLEX_FUELS = ("Heptane", "Methanol")
QUANTILES = (0.05, 0.5, 0.95)

_DF_CACHE: dict[str, pd.DataFrame] = {}
_MODEL_CACHE: dict[tuple, "FittedModel"] = {}


# --------------------------------------------------------------------------- data
def load_tests() -> pd.DataFrame:
    if "tests" not in _DF_CACHE:
        _DF_CACHE["tests"] = pd.read_csv(DATA_PATH, encoding="utf-8")
    return _DF_CACHE["tests"]


def _flex_features(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "o2": df["o2_mole_fraction"].astype(float),
            "log_p": np.log(df["pressure_atm"].astype(float)),
            "he": df["he_mole_fraction"].astype(float),
            "co2": df["co2_mole_fraction"].astype(float),
            "is_methanol": (df["fuel"].str.lower() == "methanol").astype(float),
            "droplet_mm": df["size_mm"].astype(float),
        },
        index=df.index,
    )


def _split_cfig_fuel(fuel: str) -> str:
    """'30% butane' -> 'butane' (the percentage is already in fuel_mole_fraction)."""
    return str(fuel).split()[-1].lower()


def _cfig_features(df: pd.DataFrame) -> pd.DataFrame:
    base = df["fuel"].map(_split_cfig_fuel)
    return pd.DataFrame(
        {
            "o2": df["o2_mole_fraction"].astype(float),
            "log_p": np.log(df["pressure_atm"].astype(float)),
            "is_ethane": (base == "ethane").astype(float),
            "is_propane": (base == "propane").astype(float),
            "fuel_fraction": df["fuel_mole_fraction"].astype(float),
        },
        index=df.index,
    )


@dataclass
class TrainingSet:
    metric: str
    X: pd.DataFrame  # feature columns, in spec order
    y: np.ndarray
    record_id: np.ndarray
    investigation_id: np.ndarray
    o2: np.ndarray
    p_atm: np.ndarray
    excluded: dict = field(default_factory=dict)

    def data_hash(self) -> str:
        h = hashlib.sha256()
        h.update(np.ascontiguousarray(self.X.to_numpy(dtype=float)).tobytes())
        h.update(np.ascontiguousarray(self.y.astype(float)).tobytes())
        h.update("|".join(self.record_id).encode())
        return h.hexdigest()


def _finish(metric, sub, X, y, excluded) -> TrainingSet:
    ok = X.notna().all(axis=1) & np.isfinite(y)
    excluded = {**excluded, "missing_feature": int((~ok).sum())}
    sub, X, y = sub[ok], X[ok], y[ok.to_numpy()]
    return TrainingSet(
        metric=metric,
        X=X.reset_index(drop=True),
        y=np.asarray(y, dtype=float),
        record_id=sub["record_id"].to_numpy(dtype=str),
        investigation_id=sub["investigation_id"].to_numpy(dtype=str),
        o2=sub["o2_mole_fraction"].to_numpy(dtype=float),
        p_atm=sub["pressure_atm"].to_numpy(dtype=float),
        excluded=excluded,
    )


def training_set(metric: str) -> TrainingSet:
    df = load_tests()
    if metric == "M1":
        flex = df[df["investigation_id"] == FLEX_ID]
        keep = flex["outcome"].isin(["extinction", "completion"])
        excluded = {
            "disruption": int((flex["outcome"] == "disruption").sum()),
            "no_outcome": int(flex["outcome"].isna().sum()),
        }
        sub = flex[keep]
        y = (sub["outcome"] == "extinction").to_numpy(dtype=float)
        return _finish("M1", sub, _flex_features(sub), y, excluded)
    if metric == "M2":
        flex = df[df["investigation_id"] == FLEX_ID]
        has_d = flex["extinction_diameter_mm"].notna()
        keep = has_d & (flex["outcome"] == "extinction")
        excluded = {"diameter_but_not_extinction": int((has_d & ~keep).sum())}
        sub = flex[keep]
        y = sub["extinction_diameter_mm"].to_numpy(dtype=float)
        return _finish("M2", sub, _flex_features(sub), y, excluded)
    if metric == "M3":
        cfig = df[df["investigation_id"] == CFIG_ID]
        normal = cfig["o2_context"] == "ambient"
        outcome_ok = cfig["outcome"].isin(["self_extinguished", "flow_terminated"])
        excluded = {
            "inverse_flame": int((~normal).sum()),
            "normal_no_ignition_or_flash": int((normal & ~outcome_ok).sum()),
        }
        sub = cfig[normal & outcome_ok]
        y = (sub["outcome"] == "self_extinguished").to_numpy(dtype=float)
        return _finish("M3", sub, _cfig_features(sub), y, excluded)
    raise KeyError(f"no fitted model for metric {metric!r}")


# ------------------------------------------------------------------------ models
def _fit_logistic(X: np.ndarray, y: np.ndarray):
    scaler = StandardScaler().fit(X)
    sd = np.where(scaler.scale_ > 0, scaler.scale_, 1.0)
    clf = LogisticRegression(C=1.0, max_iter=2000).fit((X - scaler.mean_) / sd, y)
    return scaler.mean_.copy(), sd, clf.coef_[0].copy(), float(clf.intercept_[0])


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


@dataclass
class FittedModel:
    metric: str
    kind: str  # "probability" | "quantity"
    features: list
    train: TrainingSet
    n_boot: int
    seed: int
    model_version: str
    # logistic: point params + bootstrap params
    mu: np.ndarray | None = None
    sd: np.ndarray | None = None
    w: np.ndarray | None = None
    b: float | None = None
    boot_mu: np.ndarray | None = None
    boot_sd: np.ndarray | None = None
    boot_w: np.ndarray | None = None
    boot_b: np.ndarray | None = None
    # quantile: one linear model per quantile on standardized X
    q_models: dict | None = None

    def feature_ranges(self) -> dict:
        return {c: (float(self.train.X[c].min()), float(self.train.X[c].max())) for c in self.features}

    def predict(self, X: np.ndarray) -> dict:
        """X: (m, d). Returns {"estimate": (m,), "lo": (m,), "hi": (m,)} (90% band)."""
        X = np.atleast_2d(np.asarray(X, dtype=float))
        if self.kind == "probability":
            est = _sigmoid(((X - self.mu) / self.sd) @ self.w + self.b)
            # boot: (B, m)
            Z = ((X[None, :, :] - self.boot_mu[:, None, :]) / self.boot_sd[:, None, :])
            pb = _sigmoid(np.einsum("bmd,bd->bm", Z, self.boot_w) + self.boot_b[:, None])
            lo, hi = np.quantile(pb, [0.05, 0.95], axis=0)
        else:
            qs = {q: m.predict(X) for q, m in self.q_models.items()}
            stack = np.sort(np.vstack([qs[q] for q in QUANTILES]), axis=0)  # no crossing
            stack = np.clip(stack, 0.0, None)  # a diameter cannot be negative
            lo, est, hi = stack
        lo = np.minimum(lo, est)
        hi = np.maximum(hi, est)
        return {"estimate": est, "lo": lo, "hi": hi}


class _ScaledQuantile:
    def __init__(self, q: float, X: np.ndarray, y: np.ndarray):
        self.mu = X.mean(axis=0)
        sd = X.std(axis=0)
        self.sd = np.where(sd > 0, sd, 1.0)
        self.m = QuantileRegressor(quantile=q, alpha=0.0, solver="highs").fit((X - self.mu) / self.sd, y)

    def predict(self, X: np.ndarray) -> np.ndarray:
        return self.m.predict((np.atleast_2d(X) - self.mu) / self.sd)


def fit_point(metric: str, X: np.ndarray, y: np.ndarray):
    """Unbootstrapped fit, used by cross-validation (engine/validation.py)."""
    if metric in ("M1", "M3"):
        mu, sd, w, b = _fit_logistic(X, y)
        return lambda Xq: _sigmoid(((np.atleast_2d(Xq) - mu) / sd) @ w + b)
    models = {q: _ScaledQuantile(q, X, y) for q in QUANTILES}
    def _pred(Xq):
        s = np.sort(np.vstack([models[q].predict(Xq) for q in QUANTILES]), axis=0)
        return np.clip(s, 0.0, None)  # rows: q05, q50, q95
    return _pred


def _fit(metric: str, n_boot: int, seed: int) -> FittedModel:
    ts = training_set(metric)
    feats = {"M1": M1_FEATURES, "M2": M2_FEATURES, "M3": M3_FEATURES}[metric]
    X = ts.X[feats].to_numpy(dtype=float)
    y = ts.y
    version = hashlib.sha256(f"{CODE_VERSION}|{ts.data_hash()}|{n_boot}|{seed}".encode()).hexdigest()[:12]
    if metric == "M2":
        q_models = {q: _ScaledQuantile(q, X, y) for q in QUANTILES}
        return FittedModel(metric, "quantity", feats, ts, n_boot, seed, version, q_models=q_models)

    mu, sd, w, b = _fit_logistic(X, y)
    rng = np.random.default_rng(seed)
    B, n = int(n_boot), len(y)
    d = X.shape[1]
    bm, bs, bw, bb = np.empty((B, d)), np.empty((B, d)), np.empty((B, d)), np.empty(B)
    i = 0
    while i < B:
        idx = rng.integers(0, n, size=n)
        yb = y[idx]
        if yb.min() == yb.max():  # need both classes; redraw
            continue
        bm[i], bs[i], bw[i], bb[i] = _fit_logistic(X[idx], yb)
        i += 1
    return FittedModel(
        metric, "probability", feats, ts, B, seed, version,
        mu=mu, sd=sd, w=w, b=b, boot_mu=bm, boot_sd=bs, boot_w=bw, boot_b=bb,
    )


def get_model(metric: str, n_boot: int = 500, seed: int = 0) -> FittedModel:
    """Fit once per (metric, n_boot, seed) and cache at module level."""
    key = (metric, int(n_boot), int(seed))
    if key not in _MODEL_CACHE:
        _MODEL_CACHE[key] = _fit(metric, n_boot, seed)
    return _MODEL_CACHE[key]


def query_row(metric: str, o2: float, p_atm: float, options: dict, model: FittedModel) -> tuple[np.ndarray, dict]:
    """Build one feature row for a habitat query; returns (row, inputs_used)."""
    ranges = model.feature_ranges()
    if metric in ("M1", "M2"):
        fuel = str(options.get("fuel", "Heptane"))
        if fuel.lower() not in {f.lower() for f in FLEX_FUELS}:
            raise ValueError(f"fuel for {metric} must be one of {FLEX_FUELS}, got {fuel!r}")
        L_mm = float(options.get("L_mm", 10.0))
        d_req = float(options.get("droplet_mm", L_mm))
        lo, hi = ranges["droplet_mm"]
        d = float(min(max(d_req, lo), hi))
        he = float(options.get("he", 0.0))
        co2 = float(options.get("co2", 0.0))
        row = np.array([o2, np.log(p_atm), he, co2, float(fuel.lower() == "methanol"), d])
        inputs = {"fuel": fuel.capitalize(), "droplet_mm": d, "droplet_mm_requested": d_req,
                  "droplet_clipped": d != d_req, "he": he, "co2": co2}
        return row, inputs
    fuel = str(options.get("fuel", "propane")).lower()
    fuel = _split_cfig_fuel(fuel)
    if fuel not in M3_FUELS:
        raise ValueError(f"fuel for M3 must be one of {M3_FUELS}, got {fuel!r}")
    ff = float(options.get("fuel_fraction", 0.3))
    row = np.array([o2, np.log(p_atm), float(fuel == "ethane"), float(fuel == "propane"), ff])
    return row, {"fuel": fuel, "fuel_fraction": ff}
