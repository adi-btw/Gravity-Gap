"""C4: precomputed regime grid artifact (artifacts/regime_grid.json).

For each gravity in {0, 1.62, 3.71, 9.81} m/s^2, a grid over vent speed
u in 0..40 cm/s (step 1) x flame size L in {1, 2, 5, 10, 20, 50, 100} mm with
u_b, Ri (None when infinite, ADR-0003) and regime, at nominal coefficients
dT/T = 4, C_b = 1.

Run: ``python -m engine.regime_grid``
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

from engine import __version__
from engine.physics import (
    RI_BUOYANT_MIN,
    RI_FORCED_MAX,
    buoyant_velocity_cm_s,
    regime,
    richardson,
)

GRAVITIES = [
    {"id": "orbit", "label": "Orbit (0 g)", "g_m_s2": 0.0},
    {"id": "moon", "label": "Moon (0.165 g)", "g_m_s2": 1.62},
    {"id": "mars", "label": "Mars (0.38 g)", "g_m_s2": 3.71},
    {"id": "earth", "label": "Earth (1 g)", "g_m_s2": 9.81},
]
U_VALUES = list(range(0, 41))
L_VALUES = [1, 2, 5, 10, 20, 50, 100]
DT_OVER_T = 4.0
C_B = 1.0

ARTIFACT_PATH = Path(__file__).resolve().parent.parent / "artifacts" / "regime_grid.json"


def build_grid() -> dict:
    grids = []
    for grav in GRAVITIES:
        g = grav["g_m_s2"]
        cells = []
        boundaries = []
        for L in L_VALUES:
            u_b = buoyant_velocity_cm_s(g, L, DT_OVER_T, C_B)
            # Vent speeds where Ri crosses the thresholds: u = u_b / sqrt(Ri).
            boundaries.append(
                {
                    "L_mm": L,
                    "u_b_cm_s": u_b,
                    "u_mixed_from_cm_s": u_b / math.sqrt(RI_BUOYANT_MIN),
                    "u_forced_above_cm_s": u_b / math.sqrt(RI_FORCED_MAX),
                }
            )
            for u in U_VALUES:
                ri = richardson(u_b, float(u))
                cells.append(
                    {
                        "u_cm_s": u,
                        "L_mm": L,
                        "u_b_cm_s": u_b,
                        "ri": None if math.isinf(ri) else ri,
                        "regime": regime(ri),
                    }
                )
        grids.append({**grav, "boundaries": boundaries, "cells": cells})

    return {
        "metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "engine_version": __version__,
            "dT_over_T": DT_OVER_T,
            "C_b": C_B,
            "u_cm_s": {"min": U_VALUES[0], "max": U_VALUES[-1], "step": 1},
            "L_mm": L_VALUES,
            "thresholds": {"RI_FORCED_MAX": RI_FORCED_MAX, "RI_BUOYANT_MIN": RI_BUOYANT_MIN},
            "formula_notes": [
                "u_b = C_b * sqrt(g * L[m] * dT/T) * 100  [cm/s]",
                "Ri = u_b^2 / u^2; u_b = 0 -> 0; u = 0 and u_b > 0 -> inf (serialized as null)",
                "regime: forced Ri < 0.1, mixed 0.1 <= Ri <= 10, buoyant Ri > 10 (inf -> buoyant)",
                "boundaries: mixed regime for u in [u_mixed_from, u_forced_above]; forced above it",
                "Scaling-law estimate only; no chemistry or radiation.",
            ],
        },
        "grids": grids,
    }


def main(path: Path = ARTIFACT_PATH) -> Path:
    data = build_grid()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, allow_nan=False) + "\n", encoding="utf-8")
    n = sum(len(g["cells"]) for g in data["grids"])
    print(f"wrote {path} ({n} cells)")
    return path


if __name__ == "__main__":
    main()
