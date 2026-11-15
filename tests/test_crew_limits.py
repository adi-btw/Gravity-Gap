"""S5 crew-limit overlay: schema and sourcing gates on data/crew_limits.json (plan/15-round-3-features.md S5).

No limit line may be drawn without a citation, so every value must carry a source with a URL and a short
verbatim quote (<= 15 words).
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from urllib.parse import urlparse

import pytest

ROOT = Path(__file__).resolve().parents[1]
CREW_LIMITS_JSON = ROOT / "data" / "crew_limits.json"

ALLOWED_QUANTITIES = {
    "o2_partial_pressure_min",
    "o2_fraction_max",
    "total_pressure_min",
    "reference_atmosphere",
}
ALLOWED_CONFIDENCE = {"stated", "derived"}
REQUIRED_LIMIT_KEYS = {"id", "label", "quantity", "value", "unit", "applies_to", "source", "quote", "confidence"}
REQUIRED_SOURCE_KEYS = {"title", "org", "id_or_number", "url", "page_or_section"}
MAX_QUOTE_WORDS = 15
TRUSTED_HOSTS = ("nasa.gov",)  # ntrs.nasa.gov, www.nasa.gov, standards.nasa.gov


@pytest.fixture(scope="module")
def doc() -> dict:
    return json.loads(CREW_LIMITS_JSON.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def limits(doc: dict) -> list[dict]:
    return doc["limits"]


def test_top_level_shape(doc: dict) -> None:
    assert doc["schema_version"] == 1
    assert isinstance(doc["retrieved"], str) and len(doc["retrieved"]) == 10
    assert isinstance(doc["limits"], list) and doc["limits"]
    assert isinstance(doc["not_found"], list)


def test_ids_unique(limits: list[dict]) -> None:
    ids = [lim["id"] for lim in limits]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("key", sorted(REQUIRED_LIMIT_KEYS))
def test_every_limit_has_required_keys(limits: list[dict], key: str) -> None:
    for lim in limits:
        assert key in lim, f"{lim.get('id')} missing {key}"


def test_quantities_allowed(limits: list[dict]) -> None:
    for lim in limits:
        assert lim["quantity"] in ALLOWED_QUANTITIES, lim["id"]


def test_confidence_allowed(limits: list[dict]) -> None:
    for lim in limits:
        assert lim["confidence"] in ALLOWED_CONFIDENCE, lim["id"]


def test_values_numeric_positive(limits: list[dict]) -> None:
    for lim in limits:
        v = lim["value"]
        assert isinstance(v, (int, float)) and not isinstance(v, bool), lim["id"]
        assert math.isfinite(v) and v > 0, lim["id"]
        conv = lim.get("converted")
        if conv is not None:
            assert isinstance(conv["value"], (int, float)) and conv["value"] > 0, lim["id"]
            assert conv.get("conversion"), f"{lim['id']}: converted value must state its conversion"


def test_every_limit_cites_a_source_with_url(limits: list[dict]) -> None:
    for lim in limits:
        src = lim["source"]
        missing = REQUIRED_SOURCE_KEYS - set(src)
        assert not missing, f"{lim['id']} source missing {missing}"
        for k in REQUIRED_SOURCE_KEYS:
            assert isinstance(src[k], str) and src[k].strip(), f"{lim['id']} empty source.{k}"
        url = urlparse(src["url"])
        assert url.scheme == "https" and url.netloc, lim["id"]
        assert any(url.netloc == h or url.netloc.endswith("." + h) for h in TRUSTED_HOSTS), (
            f"{lim['id']}: source must be a NASA host, got {url.netloc}"
        )


def test_quotes_short_and_nonempty(limits: list[dict]) -> None:
    for lim in limits:
        q = lim["quote"].strip()
        assert q, lim["id"]
        assert len(q.split()) <= MAX_QUOTE_WORDS, f"{lim['id']}: quote has {len(q.split())} words"


def test_fraction_limits_in_range(limits: list[dict]) -> None:
    for lim in limits:
        if lim["quantity"] == "o2_fraction_max":
            assert lim["unit"].startswith("%"), lim["id"]
            assert 0 < lim["value"] <= 100, lim["id"]
        if lim["quantity"] == "reference_atmosphere":
            assert 0 < lim["o2_percent"] <= 100, lim["id"]
            assert lim["unit"] == "psia", lim["id"]


def test_derived_values_say_why(limits: list[dict]) -> None:
    for lim in limits:
        if lim["confidence"] == "derived":
            assert lim.get("caveat"), f"{lim['id']}: derived value needs a caveat"


def test_not_found_entries_explain_attempts(doc: dict) -> None:
    for item in doc["not_found"]:
        assert item.get("item") and item.get("tried")


def test_each_overlay_line_has_at_least_one_value(limits: list[dict]) -> None:
    present = {lim["quantity"] for lim in limits}
    assert {"o2_partial_pressure_min", "o2_fraction_max", "reference_atmosphere"} <= present


def test_exploration_atmosphere_on_pio2_curve(limits: list[dict]) -> None:
    """8.2 psia / 34% O2 should give PIO2 ~128 mmHg with PIO2 = (PB - 47) * FIO2 (source states 128)."""
    ref = next(lim for lim in limits if lim["id"] == "ref_exploration_atmosphere_8p2_34")
    pio2 = (ref["value"] * 51.715 - 47.0) * ref["o2_percent"] / 100.0
    assert abs(pio2 - ref["pio2_mmHg_stated"]) < 1.0
