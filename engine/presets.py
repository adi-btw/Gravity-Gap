"""F0 habitat presets (plan/04-features.md). Mirrored by web/lib/presets.ts.

Gravity values: Moon 1.62 and Mars 3.71 m/s^2 (0.165 g and 0.38 g).
Vent speeds and flame size are engineering assumptions, listed in ``assumed``
so the UI can mark them "assumed, editable".
"""

from __future__ import annotations

_BRIEF = "NASA Space Apps 2026 challenge brief"
_EXPLORATION_ATM = (
    "NASA exploration atmosphere 8.2 psia / 34% O2 (BRE PSI-20 objectives)"
)
_ASSUMED = ["u_cm_s", "L_mm"]

PRESETS: list[dict] = [
    {
        "id": "iss",
        "label": "ISS",
        "g_m_s2": 0.0,
        "p_psia": 14.7,
        "o2": 0.21,
        "u_cm_s": 10.0,
        "L_mm": 10.0,
        "source": f"{_BRIEF}; ISS sea-level cabin atmosphere 14.7 psia / 21% O2",
        "assumed": list(_ASSUMED),
    },
    {
        "id": "exploration",
        "label": "Exploration vehicle",
        "g_m_s2": 0.0,
        "p_psia": 10.2,
        "o2": 0.265,
        "u_cm_s": 10.0,
        "L_mm": 10.0,
        "source": f"{_BRIEF}; NASA exploration vehicle atmosphere 10.2 psia / 26.5% O2",
        "assumed": list(_ASSUMED),
    },
    {
        "id": "lunar_base",
        "label": "Lunar base",
        "g_m_s2": 1.62,
        "p_psia": 8.2,
        "o2": 0.34,
        "u_cm_s": 10.0,
        "L_mm": 10.0,
        "source": f"{_BRIEF}; {_EXPLORATION_ATM}",
        "assumed": list(_ASSUMED),
    },
    {
        "id": "lunar_rover",
        "label": "Lunar rover",
        "g_m_s2": 1.62,
        "p_psia": 8.2,
        "o2": 0.34,
        "u_cm_s": 5.0,
        "L_mm": 10.0,
        "source": f"{_BRIEF}; {_EXPLORATION_ATM}",
        "assumed": list(_ASSUMED),
    },
    {
        "id": "mars_base",
        "label": "Mars base",
        "g_m_s2": 3.71,
        "p_psia": 8.2,
        "o2": 0.34,
        "u_cm_s": 10.0,
        "L_mm": 10.0,
        "source": f"{_BRIEF}; {_EXPLORATION_ATM}",
        "assumed": list(_ASSUMED),
    },
    {
        "id": "earth",
        "label": "Earth reference",
        "g_m_s2": 9.81,
        "p_psia": 14.7,
        "o2": 0.21,
        "u_cm_s": 0.0,
        "L_mm": 10.0,
        "source": f"{_BRIEF}; Earth sea-level air 14.7 psia / 21% O2 (quiescent)",
        "assumed": list(_ASSUMED),
    },
]

PRESETS_BY_ID: dict[str, dict] = {p["id"]: p for p in PRESETS}


def get_preset(preset_id: str) -> dict:
    """Return a copy of a preset by id; raises KeyError if unknown."""
    p = PRESETS_BY_ID[preset_id]
    return {**p, "assumed": list(p["assumed"])}
