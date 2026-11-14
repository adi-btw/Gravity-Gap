"""Pydantic request/response models for the Gravity Gap API (contract: plan/contracts.md)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HabitatIn(BaseModel):
    """Habitat state shared by POST /physics and POST /rank."""

    model_config = ConfigDict(extra="ignore")

    g_m_s2: float = Field(..., ge=0, le=30, description="Gravity, m/s^2 (Earth 9.81, Moon 1.62, Mars 3.71)")
    p_psia: float = Field(..., ge=0.5, le=20, description="Cabin pressure, psia")
    o2: float = Field(..., ge=0.05, le=1, description="O2 mole fraction (0.21 = 21%)")
    u_cm_s: float = Field(..., ge=0, le=200, description="Forced (vent) flow speed, cm/s")
    L_mm: float = Field(10.0, gt=0, le=1000, description="Flame / fuel length scale, mm")
    weights: dict[str, float] | None = Field(None, description="Optional rank weights (POST /rank only)")


class Percentiles(BaseModel):
    model_config = ConfigDict(extra="allow")

    p05: float | None = None
    p50: float | None = None
    p95: float | None = None


class RegimeFractions(BaseModel):
    model_config = ConfigDict(extra="allow")

    forced: float | None = None
    mixed: float | None = None
    buoyant: float | None = None


class MonteCarloOut(BaseModel):
    """Monte Carlo summary: p05/p50/p95 per quantity plus regime fractions."""

    model_config = ConfigDict(extra="allow")

    n: int
    seed: int
    u_b: Percentiles | None = None
    ri: Percentiles | None = None
    u_eff: Percentiles | None = None
    regime_fractions: RegimeFractions | None = None


class PhysicsOut(BaseModel):
    """engine.physics.evaluate(...) output plus the Monte Carlo block. inf/NaN are serialized as null."""

    model_config = ConfigDict(extra="allow")

    u_b_cm_s: float | None
    ri: float | None
    regime: str
    g_star: float | None
    p_o2_psia: float | None
    u_eff_cm_s: float | None
    mc: MonteCarloOut


class RankParts(BaseModel):
    model_config = ConfigDict(extra="allow")

    atmosphere: float | None = None
    pillar: float | None = None
    fuel_realism: float | None = None
    outcomes: float | None = None
    n_tests: float | None = None


class RankItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    acronym: str | None = None
    score: float | None
    parts: RankParts


class TestsPage(BaseModel):
    total: int
    limit: int
    offset: int
    rows: list[dict[str, Any]]


class Health(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str = Field(..., description='"ok", or "degraded" when artifacts differ from MANIFEST.json')
    artifact_version: str
    engine_version: str
    manifest_ok: bool | None = Field(None, description="None when artifacts/MANIFEST.json is missing")
    manifest: dict[str, Any] | None = None


# --------------------------------------------------------------------------- phase 2


class BoundsIn(HabitatIn):
    """POST /bounds: habitat state + metric id (see GET /metrics)."""

    metric: str = Field(..., description="Metric id, e.g. M1")


class LedgerIn(BaseModel):
    """POST /ledger: freeze a prediction for a habitat (preset id or explicit inputs)."""

    model_config = ConfigDict(extra="forbid")

    metric: str
    habitat: str | dict[str, Any] = Field(..., description='Preset id (e.g. "lunar_base") or habitat fields')
    rationale: str = Field(..., min_length=10, max_length=4000)
    author: str = Field(..., min_length=2, max_length=200)


class AskIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    question: str = Field(..., min_length=3, max_length=1000)
    habitat: str | dict[str, Any] | None = Field(None, description="Preset id or habitat fields; inferred if omitted")
    context_ids: list[str] = Field(default_factory=list, max_length=50,
                                   description="Ids to include: PSI-xx, rec:..., M1..M5, incident ids "
                                               "(mir1997 or eng:incident:mir1997)")


class AskOut(BaseModel):
    model_config = ConfigDict(extra="allow")

    answer_markdown: str
    citations: list[str]
    numbers_used: list[float]
    validated: bool
    mode: str = Field(..., description='"claude" | "cached" | "template"')


class Problem(BaseModel):
    """RFC 7807 problem details."""

    model_config = ConfigDict(extra="allow")

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
