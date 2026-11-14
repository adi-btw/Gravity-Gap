"""Gravity Gap API: a thin FastAPI wrapper around the engine and the build artifacts.

Contract: plan/contracts.md (API table). Run with:
    uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

import hashlib
import importlib
import json
import logging
import math
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.schemas import Health, HabitatIn, PhysicsOut, RankItem, TestsPage

log = logging.getLogger("gravity_gap.api")

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "artifacts" / "catalog.json"
TESTS_CSV_PATH = ROOT / "data" / "clean" / "psi_tests.csv"

MC_N = 2000
MC_SEED = 0
PROBLEM_JSON = "application/problem+json"
ALLOWED_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]


# --------------------------------------------------------------------------- helpers


def to_jsonable(value: Any) -> Any:
    """Recursively convert numpy / pandas values to plain Python and inf/NaN to None."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(v) for v in value]
    # numpy arrays and scalars
    if hasattr(value, "tolist") and not isinstance(value, (int, float)):
        return to_jsonable(value.tolist())
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, int):
        return value
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f if math.isfinite(f) else None


def engine_module(name: str):
    """Import an engine module lazily; 503 problem if the engine is not available."""
    try:
        return importlib.import_module(f"engine.{name}")
    except ImportError as exc:  # pragma: no cover - only when engine is missing
        raise HTTPException(status_code=503, detail=f"engine.{name} unavailable: {exc}") from exc


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any] | None:
    """Load artifacts/catalog.json once. Returns None when the artifact is missing."""
    if not CATALOG_PATH.exists():
        log.warning("catalog artifact missing: %s", CATALOG_PATH)
        return None
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def artifact_version() -> str:
    """Short sha256 of catalog.json bytes (MANIFEST.json integrity is phase 2)."""
    if not CATALOG_PATH.exists():
        return "missing"
    return hashlib.sha256(CATALOG_PATH.read_bytes()).hexdigest()[:12]


@lru_cache(maxsize=1)
def load_tests() -> pd.DataFrame | None:
    """Load data/clean/psi_tests.csv once. Returns None when missing."""
    if not TESTS_CSV_PATH.exists():
        log.warning("tests table missing: %s", TESTS_CSV_PATH)
        return None
    return pd.read_csv(TESTS_CSV_PATH, low_memory=False)


def investigations() -> list[dict[str, Any]]:
    catalog = load_catalog()
    if catalog is None:
        raise HTTPException(status_code=503, detail="artifacts/catalog.json is not built yet")
    return list(catalog.get("investigations", []))


def engine_version() -> str:
    try:
        engine = importlib.import_module("engine")
    except ImportError:
        return "missing"
    return str(getattr(engine, "__version__", "unknown"))


def problem(status: int, title: str, detail: Any, request: Request, **extra: Any) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
    }
    body.update(extra)
    return JSONResponse(status_code=status, content=to_jsonable(body), media_type=PROBLEM_JSON)


# --------------------------------------------------------------------------- app


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_catalog()
    load_tests()
    log.info("artifact_version=%s engine_version=%s", artifact_version(), engine_version())
    yield


app = FastAPI(
    title="Gravity Gap API",
    version="0.1.0",
    description="Partial-gravity fire prediction engine (NASA Space Apps 2026).",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


_TITLES = {400: "Bad Request", 404: "Not Found", 405: "Method Not Allowed", 422: "Unprocessable Entity",
           500: "Internal Server Error", 503: "Service Unavailable"}


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    title = _TITLES.get(exc.status_code, "HTTP Error")
    return problem(exc.status_code, title, exc.detail, request)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"loc": list(e.get("loc", ())), "msg": e.get("msg"), "type": e.get("type")}
        for e in exc.errors()
    ]
    detail = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in errors)
    return problem(422, "Unprocessable Entity", detail or "Request validation failed", request, errors=errors)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error on %s", request.url.path)
    return problem(500, "Internal Server Error", "Unexpected server error", request)


# --------------------------------------------------------------------------- endpoints


@app.get("/health", response_model=Health)
def health() -> dict[str, str]:
    return {"status": "ok", "artifact_version": artifact_version(), "engine_version": engine_version()}


@app.get("/presets")
def presets() -> list[dict[str, Any]]:
    return to_jsonable(engine_module("presets").PRESETS)


@app.get("/catalog")
def catalog() -> list[dict[str, Any]]:
    return to_jsonable(investigations())


@app.get("/catalog/{investigation_id}")
def catalog_record(investigation_id: str) -> dict[str, Any]:
    for record in investigations():
        if str(record.get("id")) == investigation_id:
            return to_jsonable(record)
    raise HTTPException(status_code=404, detail=f"Investigation '{investigation_id}' not found")


def _mc_block(mc_raw: dict[str, Any]) -> dict[str, Any]:
    summary = dict(mc_raw.get("summary") or {})
    fractions = mc_raw.get("regime_fractions", summary.pop("regime_fractions", None))
    summary.pop("regime_fractions", None)
    block = {"n": MC_N, "seed": MC_SEED, **summary, "regime_fractions": fractions}
    if "ri_inf_fraction" in mc_raw:
        block["ri_inf_fraction"] = mc_raw["ri_inf_fraction"]
    return block


@app.post("/physics", response_model=PhysicsOut)
def physics(body: HabitatIn) -> dict[str, Any]:
    phys = engine_module("physics")
    mc = engine_module("montecarlo")
    args = dict(g_m_s2=body.g_m_s2, p_psia=body.p_psia, o2=body.o2, u_cm_s=body.u_cm_s, L_mm=body.L_mm)
    result = dict(phys.evaluate(**args))
    mc_raw = mc.sample_physics(**args, n=MC_N, seed=MC_SEED)
    result["mc"] = _mc_block(mc_raw)
    return to_jsonable(result)


@app.post("/rank", response_model=list[RankItem])
def rank(body: HabitatIn) -> list[dict[str, Any]]:
    rank_mod = engine_module("rank")
    ranked = rank_mod.rank(
        investigations(), body.g_m_s2, body.p_psia, body.o2, body.u_cm_s, weights=body.weights
    )
    return to_jsonable(ranked)


@app.get("/data/tests", response_model=TestsPage)
def data_tests(
    investigation_id: str | None = Query(None, description="e.g. PSI-98"),
    o2_min: float | None = Query(None, ge=0, le=1),
    o2_max: float | None = Query(None, ge=0, le=1),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    df = load_tests()
    if df is None:
        raise HTTPException(status_code=503, detail="data/clean/psi_tests.csv is missing")
    mask = pd.Series(True, index=df.index)
    if investigation_id:
        mask &= df["investigation_id"].astype(str) == investigation_id
    if o2_min is not None:
        mask &= df["o2_mole_fraction"] >= o2_min
    if o2_max is not None:
        mask &= df["o2_mole_fraction"] <= o2_max
    filtered = df[mask]
    page = filtered.iloc[offset : offset + limit]
    # to_json turns NaN into null and numpy scalars into JSON numbers.
    rows = json.loads(page.to_json(orient="records"))
    return {"total": int(len(filtered)), "limit": limit, "offset": offset, "rows": rows}
