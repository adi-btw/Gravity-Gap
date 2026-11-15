"""Gravity Gap API: a thin FastAPI wrapper around the engine and the build artifacts.

Contract: plan/contracts.md (API table). Run with:
    uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

import hashlib
import hmac
import importlib
import io
import json
import logging
import math
import os
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.schemas import (AskIn, AskOut, BoundsIn, BriefingIn, CompareIn, Health, HabitatIn, LedgerIn, PhysicsOut,
                         RankItem, SuppressionIn, TestsPage)

log = logging.getLogger("gravity_gap.api")

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "artifacts" / "catalog.json"
TESTS_CSV_PATH = ROOT / "data" / "clean" / "psi_tests.csv"
CLEANING_REPORT_PATH = ROOT / "data" / "clean" / "CLEANING_REPORT.md"
ARTIFACTS_DIR = ROOT / "artifacts"
MANIFEST_PATH = ARTIFACTS_DIR / "MANIFEST.json"
PLANNER_PATH = ARTIFACTS_DIR / "planner.json"
INCIDENTS_PATH = ARTIFACTS_DIR / "incidents.json"
SUPPRESSION_REFERENCE_PATH = ARTIFACTS_DIR / "suppression_reference.json"
DETECTION_PATH = ARTIFACTS_DIR / "detection.json"
HOLDOUT_PATH = ARTIFACTS_DIR / "holdout.json"
ATMOSPHERE_MAP_DIR = ARTIFACTS_DIR / "atmosphere_map"
MAP_METRICS = ("M1", "M2", "M3")  # M4/M5 are rule tables with a box gate; not mapped (ADR-0011)
MAP_GRAVITIES = ("orbit", "lunar", "mars", "earth")

ASK_RATE_PER_MIN = int(os.environ.get("GRAVITY_GAP_ASK_RATE", "20"))
LEDGER_RATE_PER_MIN = int(os.environ.get("GRAVITY_GAP_LEDGER_RATE", "10"))
EXPORT_MAX_ROWS = 100_000

MC_N = 2000
MC_SEED = 0
PROBLEM_JSON = "application/problem+json"
DEFAULT_CORS_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")


def parse_cors_origins(raw: str | None) -> list[str]:
    """Comma-separated origins from env CORS_ORIGINS; blank/unset gives the localhost defaults."""
    origins = [o.strip().rstrip("/") for o in (raw or "").split(",") if o.strip()]
    return origins or list(DEFAULT_CORS_ORIGINS)


ALLOWED_ORIGINS = parse_cors_origins(os.environ.get("CORS_ORIGINS"))


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


_TITLES = {400: "Bad Request", 401: "Unauthorized", 403: "Forbidden", 404: "Not Found",
           429: "Too Many Requests", 405: "Method Not Allowed", 422: "Unprocessable Entity",
           500: "Internal Server Error", 503: "Service Unavailable"}


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    title = _TITLES.get(exc.status_code, "HTTP Error")
    resp = problem(exc.status_code, title, exc.detail, request)
    for k, v in (getattr(exc, "headers", None) or {}).items():
        resp.headers[k] = v
    return resp


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


def manifest_status() -> dict[str, Any]:
    """Compare current artifact hashes with artifacts/MANIFEST.json (never raises)."""
    if not MANIFEST_PATH.exists():
        return {"ok": None, "detail": "artifacts/MANIFEST.json missing (run scripts/build_manifest.py)"}
    try:
        listed = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")).get("files") or {}
        current = {}
        for f in sorted(ARTIFACTS_DIR.rglob("*")):
            if f.is_file() and f.name != "MANIFEST.json":
                current[f.relative_to(ARTIFACTS_DIR).as_posix()] = hashlib.sha256(f.read_bytes()).hexdigest()
        changed = sorted(k for k, v in listed.items() if k in current and current[k] != (v or {}).get("sha256"))
        missing = sorted(k for k in listed if k not in current)
        unlisted = sorted(k for k in current if k not in listed)
        return {"ok": not (changed or missing or unlisted), "changed": changed, "missing": missing,
                "unlisted": unlisted}
    except Exception as exc:  # noqa: BLE001 - health must not crash
        return {"ok": False, "detail": f"manifest unreadable: {type(exc).__name__}"}


@app.get("/health", response_model=Health)
def health() -> dict[str, Any]:
    m = manifest_status()
    return {"status": "degraded" if m["ok"] is False else "ok", "artifact_version": artifact_version(),
            "engine_version": engine_version(), "manifest_ok": m["ok"], "manifest": m}


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


OUTCOME_DESCRIPTION = ("Exact match on the outcome column, e.g. extinction; repeat the parameter or "
                       "comma-separate values to match any of them")


def parse_outcomes(values: list[str] | None) -> list[str]:
    """Flatten repeated and comma-separated `outcome=` values; drop blanks, keep order, dedupe."""
    out: list[str] = []
    for value in values or []:
        for part in str(value).split(","):
            part = part.strip()
            if part and part not in out:
                out.append(part)
    return out


@app.get("/data/tests", response_model=TestsPage)
def data_tests(
    investigation_id: str | None = Query(None, description="e.g. PSI-98"),
    o2_min: float | None = Query(None, ge=0, le=1),
    o2_max: float | None = Query(None, ge=0, le=1),
    outcome: list[str] | None = Query(None, description=OUTCOME_DESCRIPTION),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    filtered = _filtered_tests(investigation_id, o2_min, o2_max, outcome)
    page = filtered.iloc[offset : offset + limit]
    # to_json turns NaN into null and numpy scalars into JSON numbers.
    rows = json.loads(page.to_json(orient="records"))
    return {"total": int(len(filtered)), "limit": limit, "offset": offset, "rows": rows}


# --------------------------------------------------------------------------- phase 2 helpers


class RateLimiter:
    """Sliding-window, in-memory, per-client limiter (single process; good enough for the demo)."""

    def __init__(self, per_minute: int, window_s: float = 60.0) -> None:
        self.per_minute = per_minute
        self.window_s = window_s
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def check(self, client: str) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._hits.setdefault(client, deque())
            while q and now - q[0] > self.window_s:
                q.popleft()
            if len(q) >= self.per_minute:
                retry = max(1, int(self.window_s - (now - q[0])) + 1)
                raise HTTPException(status_code=429, detail=f"Rate limit: {self.per_minute} requests per minute",
                                    headers={"Retry-After": str(retry)})
            q.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


ask_limiter = RateLimiter(ASK_RATE_PER_MIN)
ledger_limiter = RateLimiter(LEDGER_RATE_PER_MIN)


def _client_id(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def bounds_module():
    mod = engine_module("bounds")
    if not hasattr(mod, "predict") or not hasattr(mod, "METRICS"):
        raise HTTPException(status_code=503, detail="engine.bounds has no predict/METRICS yet")
    return mod


HABITAT_KEYS = ("g_m_s2", "p_psia", "o2", "u_cm_s", "L_mm")


def _predict(metric: str, hab: dict[str, Any]) -> dict[str, Any]:
    mod = bounds_module()
    if metric not in mod.METRICS:
        raise HTTPException(status_code=422, detail=f"Unknown metric '{metric}'; known: {sorted(mod.METRICS)}")
    try:
        out = mod.predict(metric, **{k: hab[k] for k in HABITAT_KEYS})
    except NotImplementedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return to_jsonable(out)


def _resolve_habitat(habitat: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(habitat, str):
        by_id = {p["id"]: p for p in engine_module("presets").PRESETS}
        if habitat not in by_id:
            raise HTTPException(status_code=422, detail=f"Unknown habitat preset '{habitat}'")
        p = by_id[habitat]
        return {"preset_id": p["id"], "label": p["label"], **{k: float(p[k]) for k in HABITAT_KEYS}}
    try:
        hab = HabitatIn(**habitat)
    except Exception as exc:  # noqa: BLE001 - pydantic ValidationError
        raise HTTPException(status_code=422, detail=f"Invalid habitat: {exc}") from exc
    out = hab.model_dump(exclude={"weights"})
    for k in ("preset_id", "label"):
        if habitat.get(k):
            out[k] = str(habitat[k])
    return out


# --------------------------------------------------------------------------- phase 2 endpoints


@app.get("/metrics")
def metrics() -> dict[str, Any]:
    return to_jsonable(bounds_module().METRICS)


def _drivers(metric: str, hab: dict[str, Any]) -> dict[str, Any] | None:
    """S3 band-width breakdown (engine.uncertainty.drivers, ADR-0008) for the same habitat; None on any error."""
    try:
        mod = importlib.import_module("engine.uncertainty")
        return to_jsonable(mod.drivers(metric, **{k: hab[k] for k in HABITAT_KEYS}))
    except Exception:  # noqa: BLE001 - optional field: never blocks the bounds answer
        log.exception("drivers failed for %s", metric)
        return None


@app.post("/bounds")
def bounds(body: BoundsIn) -> dict[str, Any]:
    hab = body.model_dump(exclude={"weights", "metric"})
    out = _predict(body.metric, hab)
    out["drivers"] = _drivers(body.metric, hab)
    return out


@app.post("/compare")
def compare(body: CompareIn) -> dict[str, Any]:
    """S4: M1-M5 for two habitats side by side + rule-based diff and summary (engine.compare.compare)."""
    mod = engine_module("compare")
    if not hasattr(mod, "compare"):
        raise HTTPException(status_code=503, detail="engine.compare has no compare() yet")
    a, b = _resolve_habitat(body.a), _resolve_habitat(body.b)
    try:
        out = mod.compare(a, b)
    except NotImplementedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return to_jsonable(out)


@app.get("/coverage/{metric}")
def coverage(metric: str, p_psia: float | None = Query(None, gt=0, le=20), o2: float | None = Query(None, ge=0, le=1),
             co2: float | None = Query(None, ge=0, le=1, description="CO2 diluent fraction (M1/M2 4-D gate)"),
             he: float | None = Query(None, ge=0, le=1, description="He diluent fraction (M1/M2 4-D gate)"),
             ) -> dict[str, Any]:
    """Tested O2 x pressure (x CO2 x He for M1/M2) points for a metric plus the engine's applicability rule.

    The Bounds Panel draws this when a habitat is outside the tested range (no estimate); the suppression page
    passes `co2`/`he` so "covered" matches the dilution-aware gate (ADR-0006).
    """
    if (o2 or 0.0) + (co2 or 0.0) + (he or 0.0) > 1 + 1e-9:
        raise HTTPException(status_code=422, detail="o2 + co2 + he must be <= 1")
    try:
        from engine import coverage as coverage_module
    except ImportError as exc:  # pragma: no cover - engine missing
        raise HTTPException(status_code=503, detail=f"engine.coverage unavailable: {exc}") from exc
    try:
        if co2 is None and he is None:
            return to_jsonable(coverage_module.coverage_for(metric.upper(), p_psia, o2))
        return to_jsonable(coverage_module.coverage_for(metric.upper(), p_psia, o2, co2=co2, he=he))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown metric {metric!r}") from exc


@app.get("/planner")
def planner() -> dict[str, Any]:
    if not PLANNER_PATH.exists():
        raise HTTPException(status_code=503, detail="artifacts/planner.json is not built yet")
    return json.loads(PLANNER_PATH.read_text(encoding="utf-8"))


def load_incidents_artifact() -> dict[str, Any]:
    """artifacts/incidents.json (R1 real-fire replay); read per request (small, rebuilt by engine.incidents)."""
    if not INCIDENTS_PATH.exists():
        raise HTTPException(status_code=503,
                            detail="artifacts/incidents.json is not built yet (python -m engine.incidents)")
    try:
        data = json.loads(INCIDENTS_PATH.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="artifacts/incidents.json is not valid JSON") from exc
    if not isinstance(data, dict) or not isinstance(data.get("incidents"), list):
        raise HTTPException(status_code=503, detail="artifacts/incidents.json has no incidents list")
    return to_jsonable(data)


@app.get("/incidents")
def incidents() -> dict[str, Any]:
    """Real-fire replay: every incident with its engine results (`{generated_at, engine_version, incidents[]}`)."""
    return load_incidents_artifact()


@app.get("/incidents/{incident_id}")
def incident_record(incident_id: str) -> dict[str, Any]:
    for inc in load_incidents_artifact()["incidents"]:
        if isinstance(inc, dict) and str(inc.get("id")) == incident_id:
            return inc
    raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")


# --------------------------------------------------------------------------- R2 suppression calculator


def suppression_module():
    mod = engine_module("suppression")
    if not hasattr(mod, "curve") or not hasattr(mod, "DILUENTS"):
        raise HTTPException(status_code=503, detail="engine.suppression has no curve/DILUENTS yet")
    return mod


@app.get("/suppression/diluents")
def suppression_diluents() -> dict[str, Any]:
    """`engine.suppression.DILUENTS`: `{co2: {label, max}, he: {label, max}}`."""
    return to_jsonable(suppression_module().DILUENTS)


@app.post("/suppression")
def suppression(body: SuppressionIn) -> dict[str, Any]:
    """Dilution curve: M1/M2 with 90% bands vs diluent fraction (diluent replaces N2 at fixed O2 and pressure)."""
    mod = suppression_module()
    if body.diluent not in mod.DILUENTS:
        raise HTTPException(status_code=422, detail=f"Unknown diluent '{body.diluent}'; known: {sorted(mod.DILUENTS)}")
    try:
        out = mod.curve(body.diluent, body.g_m_s2, body.p_psia, body.o2, body.u_cm_s, body.L_mm, steps=body.steps)
    except NotImplementedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return to_jsonable(out)


@app.get("/suppression/reference")
def suppression_reference() -> Any:
    """`artifacts/suppression_reference.json`: empirical FLEX outcome rates by diluent bin (no model)."""
    if not SUPPRESSION_REFERENCE_PATH.exists():
        raise HTTPException(status_code=503, detail="artifacts/suppression_reference.json is not built yet "
                                                    "(python -m engine.suppression_reference)")
    try:
        data = json.loads(SUPPRESSION_REFERENCE_PATH.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="artifacts/suppression_reference.json is not valid JSON") from exc
    return to_jsonable(data)



# --------------------------------------------------------------------------- R3 detection evidence


@app.get("/detection")
def detection() -> Any:
    """`artifacts/detection.json` (R3 detection evidence, reduced scope per ADR-0007), served unchanged."""
    if not DETECTION_PATH.exists():
        raise HTTPException(status_code=503, detail="artifacts/detection.json is not built yet "
                                                    "(python -m engine.detection)")
    try:
        data = json.loads(DETECTION_PATH.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="artifacts/detection.json is not valid JSON") from exc
    return to_jsonable(data)


# --------------------------------------------------------------------------- S2 honesty test


@app.get("/holdout")
def holdout() -> Any:
    """`artifacts/holdout.json` (S2 honesty test: held-out tested atmospheres, ADR-0009), served unchanged."""
    if not HOLDOUT_PATH.exists():
        raise HTTPException(status_code=503, detail="artifacts/holdout.json is not built yet "
                                                    "(python -m engine.holdout)")
    try:
        data = json.loads(HOLDOUT_PATH.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise HTTPException(status_code=503, detail="artifacts/holdout.json is not valid JSON") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=503, detail="artifacts/holdout.json is not a JSON object")
    return data


# --------------------------------------------------------------------------- S1 briefing, S5 atmosphere map


@app.post("/briefing")
def briefing(body: BriefingIn) -> dict[str, Any]:
    """S1: one-page fire-safety briefing for a preset id or habitat fields (engine.briefing.briefing, ADR-0010)."""
    mod = engine_module("briefing")
    if not hasattr(mod, "briefing"):
        raise HTTPException(status_code=503, detail="engine.briefing has no briefing() yet")
    raw: str | dict[str, Any]
    if isinstance(body.habitat, str):
        if body.habitat not in {p["id"] for p in engine_module("presets").PRESETS}:
            raise HTTPException(status_code=422, detail=f"Unknown habitat preset '{body.habitat}'")
        raw = body.habitat
    else:
        try:
            hab = HabitatIn(**body.habitat)
        except Exception as exc:  # noqa: BLE001 - pydantic ValidationError
            raise HTTPException(status_code=422, detail=f"Invalid habitat: {exc}") from exc
        # exclude_unset keeps "L_mm omitted" visible to the engine, which then marks it as assumed
        raw = hab.model_dump(exclude={"weights"}, exclude_unset=True)
        if body.habitat.get("label"):
            raw["label"] = str(body.habitat["label"])
        assumed = body.habitat.get("assumed")
        if isinstance(assumed, list):
            raw["assumed"] = [str(a) for a in assumed if str(a) in HABITAT_KEYS]
    try:
        out = mod.briefing(raw)
    except NotImplementedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return to_jsonable(out)


@app.get("/atmosphere-map/{metric}")
def atmosphere_map(metric: str, g: str = Query("lunar", description="Gravity preset: orbit, lunar, mars or earth")
                   ) -> Any:
    """S5: `artifacts/atmosphere_map/{metric}_{g}.json` unchanged (O2 x pressure evidence map, ADR-0011)."""
    m = metric.upper()
    if m not in MAP_METRICS:
        raise HTTPException(status_code=404, detail=f"unknown metric {metric!r}; mapped: {list(MAP_METRICS)}")
    if g not in MAP_GRAVITIES:
        raise HTTPException(status_code=404, detail=f"unknown gravity {g!r}; known: {list(MAP_GRAVITIES)}")
    path = ATMOSPHERE_MAP_DIR / f"{m}_{g}.json"
    if not path.exists():
        raise HTTPException(status_code=503, detail=f"artifacts/atmosphere_map/{m}_{g}.json is not built yet "
                                                    "(python -m engine.atmosphere_map)")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=f"artifacts/atmosphere_map/{m}_{g}.json is not valid JSON") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=503, detail=f"artifacts/atmosphere_map/{m}_{g}.json is not a JSON object")
    return data


@app.get("/ledger")
def ledger_list() -> dict[str, Any]:
    led = engine_module("ledger")
    return {"predictions": led.load(), "verification": led.verify()}


@app.post("/ledger", status_code=201)
def ledger_append(body: LedgerIn, request: Request,
                  x_team_token: str | None = Header(None, alias="X-Team-Token")) -> dict[str, Any]:
    expected = os.environ.get("LEDGER_TEAM_TOKEN")
    if not expected:
        raise HTTPException(status_code=403, detail="Ledger writes are disabled (LEDGER_TEAM_TOKEN is not set)")
    if not x_team_token or not hmac.compare_digest(x_team_token.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Missing or invalid X-Team-Token")
    ledger_limiter.check(_client_id(request))
    hab = _resolve_habitat(body.habitat)
    pred = _predict(body.metric, hab)
    if not pred.get("applicable"):
        raise HTTPException(status_code=422,
                            detail=f"Prediction is not applicable, nothing to freeze: {pred.get('reason')}")
    try:
        return engine_module("ledger").append(pred, body.rationale, body.author, habitat=hab)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/ask", response_model=AskOut)
def ask(body: AskIn, request: Request) -> dict[str, Any]:
    ask_limiter.check(_client_id(request))
    answer_mod = engine_module("ai.answer")
    try:
        res = answer_mod.ask(body.question, body.habitat, body.context_ids)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return to_jsonable(res)


def _filtered_tests(investigation_id: str | None, o2_min: float | None, o2_max: float | None,
                    outcome: list[str] | None = None) -> pd.DataFrame:
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
    outcomes = parse_outcomes(outcome)
    if outcomes:
        mask &= df["outcome"].astype("string").isin(outcomes).fillna(False).astype(bool)
    return df[mask]


def cleaning_report_version() -> str:
    if not CLEANING_REPORT_PATH.exists():
        return "missing"
    data = CLEANING_REPORT_PATH.read_bytes()
    short = f"sha256:{hashlib.sha256(data).hexdigest()[:12]}"
    generated = next((ln.strip() for ln in data.decode("utf-8", "replace").splitlines()
                      if ln.lower().startswith("generated")), "")
    return f"{short} ({generated})" if generated else short


@app.get("/data/export")
def data_export(
    investigation_id: str | None = Query(None, description="e.g. PSI-98"),
    o2_min: float | None = Query(None, ge=0, le=1),
    o2_max: float | None = Query(None, ge=0, le=1),
    outcome: list[str] | None = Query(None, description=OUTCOME_DESCRIPTION),
    format: str = Query("csv", pattern="^(csv|json)$"),
) -> Response:
    filtered = _filtered_tests(investigation_id, o2_min, o2_max, outcome).iloc[:EXPORT_MAX_ROWS]
    catalog = {r.get("id"): r for r in (load_catalog() or {}).get("investigations", [])}
    inv_ids = sorted(set(filtered["investigation_id"].astype(str)), key=lambda i: (len(i), i))
    citations = [{"investigation_id": i, "acronym": (catalog.get(i) or {}).get("acronym"),
                  "title": (catalog.get(i) or {}).get("title"), "doi": (catalog.get(i) or {}).get("doi")}
                 for i in inv_ids]
    report = cleaning_report_version()
    if format == "json":
        body = {"source": "NASA Physical Sciences Informatics (PSI), cleaned by Gravity Gap",
                "cleaning_report": report, "citations": citations, "total": int(len(filtered)),
                "rows": json.loads(filtered.to_json(orient="records"))}
        return JSONResponse(content=to_jsonable(body),
                            headers={"Content-Disposition": 'attachment; filename="gravity_gap_tests.json"'})
    buf = io.StringIO()
    buf.write("# Gravity Gap export of data/clean/psi_tests.csv (NASA Physical Sciences Informatics)\n")
    buf.write(f"# Cleaning report: data/clean/CLEANING_REPORT.md {report}\n")
    buf.write(f"# Rows: {len(filtered)}. Cite every investigation below when using these data:\n")
    for c in citations:
        doi = f"https://doi.org/{c['doi']}" if c["doi"] else "DOI not available"
        buf.write(f"# {c['investigation_id']} {c['acronym'] or ''} - {c['title'] or ''} - {doi}\n")
    filtered.to_csv(buf, index=False, lineterminator="\n")
    return Response(content=buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="gravity_gap_tests.csv"'})
