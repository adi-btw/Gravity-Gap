"""Deterministic post-validator for AI answers (plan/05-ai-layer.md section 3.4).

``validate(answer_markdown, pack, numbers_used=None, citations=None) -> report``

An answer is valid when

1. every number in ``answer_markdown`` matches a number in the context pack within a
   relative tolerance of 0.5% (``REL_TOL``); when ``numbers_used`` is given, every
   answer number must also be listed there and every listed value must be in the pack;
2. every citation id resolves to an id in the context pack (``pack["citable_ids"]``).

Number extraction rules (what counts as "a number"):

* Plain decimals ``\\d+(\\.\\d+)?`` (optional exponent). Thousand separators are not
  supported: write 1710, not 1,710. Signs are ignored (absolute values are compared), so
  ``0.2-0.7`` reads as 0.2 and 0.7.
* A number followed by ``%`` also matches a pack value of number/100 (``34%`` ~ 0.34).
* Numbers that are part of an identifier are not numbers: a digit run that follows a
  letter or underscore (``O2``, ``CO2``, ``M1``, ``v1``) or a ``-``/``:`` that itself
  follows a letter (``PSI-69``, ``FLEX-2``, ``FLEX:12``). Exception: a standalone multiplier
  ``x1.64`` / ``×1.64`` is a number.
* Ignored before scanning: citation brackets (``[PSI-69]``, ``[rec:PSI-69:FLEX:12]``,
  ``[doi:10.60555/mbq8-0451]``, ``[eng:M1]``, comma/semicolon lists of those), bare DOIs
  ``10.NNNN/...``, markdown list numbering at the start of a line (``1.``, ``2)``),
  ISO dates ``YYYY-MM-DD``, and years written as ``(YYYY)`` or ``et al. YYYY`` in citations.
* ``CONSTANTS`` (gravity of Earth/Moon/Mars, 0 g / 1 g, the Richardson thresholds 0.1 and
  10, sea-level pressure, the 90% band, 21% air) are always allowed; context packs
  also list them under ``constants`` so they are "in the pack".

Citation rules: a citation is any bracketed token, or bare ``PSI-NN`` / ``rec:...`` /
``doi:...`` token, with prefix ``PSI-``, ``rec:``, ``doi:`` or ``eng:`` (engine outputs:
``eng:physics``, ``eng:M1``, ``eng:planner:1``, ``eng:fans_off:M1``, ``eng:incident:mir1997``...),
or an ``http(s)://`` source URL (bracketed or bare; R1 incident sources are cited by their URL exactly
as written in the incident's ``sources``). Each must be in ``pack["citable_ids"]``. URLs are never
scanned for numbers. Bracketed text without a citation prefix is scanned for numbers like normal text.
"""
from __future__ import annotations

import math
import re
from typing import Any, Iterable

REL_TOL = 0.005
ABS_TOL = 1e-9

CONSTANTS: dict[str, float] = {
    "g_earth_m_s2": 9.81, "g_moon_m_s2": 1.62, "g_mars_m_s2": 3.71,
    "zero_g": 0.0, "one_g": 1.0, "ri_forced_max": 0.1, "ri_buoyant_min": 10.0,
    "p_sea_level_psia": 14.7, "band_percent": 90.0, "air_o2_fraction": 0.21,
}

CITE_PREFIX = r"(?:PSI-\d+|rec:[^\s,;\]]+|doi:[^\s,;\]]+|eng:[^\s,;\]]+|https?://[^\s,;\]]+)"
_BRACKET = re.compile(r"\[([^\[\]]+)\]")
_CITE_TOKEN = re.compile(rf"^\s*({CITE_PREFIX})\s*$")
_BARE_CITE = re.compile(r"(?<![\w:/\[-])(PSI-\d+|rec:[^\s,;\])]+|doi:[^\s,;\])]+|eng:[^\s,;\])]+)")
_URL = re.compile(r"https?://[^\s\]\)>]+")
_DOI = re.compile(r"\b10\.\d{4,9}/[^\s\])>,;]+")
_LIST_NUM = re.compile(r"(?m)^\s*(?:[-*+]\s+)?\d+[.)]\s+")
_DATE = re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}(?:T[\d:.+Z-]+)?\b")
_YEAR_CITE = re.compile(r"\((?:19|20)\d{2}[a-z]?\)|et al\.?,?\s+(?:19|20)\d{2}")
_NUMBER = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)(\s?%)?", re.ASCII)


# --------------------------------------------------------------------------- pack indexing


def _numbers_in_text(text: str) -> list[tuple[float, bool, str]]:
    """(value, is_percent, raw) for every number in ``text`` that is not part of an identifier."""
    out = []
    for m in _NUMBER.finditer(text):
        start = m.start(1)
        prev = text[start - 1] if start > 0 else ""
        prev2 = text[start - 2] if start > 1 else ""
        if prev in "xX" and not (prev2.isalnum() or prev2 == "_"):
            pass  # multiplier "x1.64" is a number, not an identifier
        elif prev.isalpha() or prev == "_":
            continue
        if prev in "-:" and (prev2.isalpha() or prev2 == "_"):
            continue
        raw = m.group(1)
        # a number glued to letters on the right that look like an id (e.g. 3D, 2x) is still a number
        try:
            val = float(raw)
        except ValueError:
            continue
        out.append((val, bool(m.group(2)), raw))
    return out


def _strip_ignored(text: str) -> str:
    text = _URL.sub(" ", text)
    text = _DOI.sub(" ", text)
    text = _DATE.sub(" ", text)
    text = _YEAR_CITE.sub(" ", text)
    return text


_SKIP_KEYS = {"id", "record_id", "investigation_id", "doi", "citable_ids", "catalog_index",
              "created_at", "generated_at", "model_version", "version", "sha256", "question",
              "evidence_ids", "evidence_investigations", "extends", "missing", "url", "incident_id"}


def pack_numbers(pack: dict) -> list[tuple[float, str]]:
    """Flatten every number in the pack (numeric leaves, and numbers inside string leaves)."""
    out: list[tuple[float, str]] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, bool) or node is None:
            return
        if isinstance(node, dict):
            for k, v in node.items():
                if str(k) in _SKIP_KEYS:
                    continue
                walk(v, f"{path}.{k}" if path else str(k))
        elif isinstance(node, (list, tuple)):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")
        elif isinstance(node, (int, float)):
            if math.isfinite(float(node)):
                out.append((float(node), path))
        elif isinstance(node, str):
            cleaned = _strip_ignored(_BRACKET.sub(lambda m: " " if _is_cite_group(m.group(1)) else m.group(0), node))
            cleaned = _BARE_CITE.sub(" ", cleaned)
            for val, _pct, _raw in _numbers_in_text(cleaned):
                out.append((val, f"{path}~text"))

    walk(pack, "")
    for k, v in CONSTANTS.items():
        out.append((float(v), f"constants.{k}"))
    return out


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= max(REL_TOL * max(abs(a), abs(b)), ABS_TOL)


def _match(value: float, is_percent: bool, candidates: Iterable[tuple[float, str]]) -> str | None:
    targets = [value]
    if is_percent:
        targets.append(value / 100.0)
    for t in targets:
        for c, path in candidates:
            if _close(abs(t), abs(c)):
                return path
    return None


# --------------------------------------------------------------------------- citations


def _is_cite_group(inner: str) -> bool:
    toks = [t for t in re.split(r"[,;]", inner) if t.strip()]
    return bool(toks) and all(_CITE_TOKEN.match(t) for t in toks)


def extract_citations(text: str) -> tuple[list[str], str]:
    """Return (citation ids in order of appearance, text with citation brackets removed)."""
    ids: list[str] = []

    def repl(m: re.Match) -> str:
        inner = m.group(1)
        toks = [t.strip() for t in re.split(r"[,;]", inner) if t.strip()]
        cites = [t for t in toks if _CITE_TOKEN.match(t)]
        if cites and len(cites) == len(toks):
            ids.extend(cites)
            return " "
        if cites:  # mixed bracket: citations count, the rest is scanned as text
            ids.extend(cites)
            return " " + " ".join(t for t in toks if not _CITE_TOKEN.match(t)) + " "
        return m.group(0)

    stripped = _BRACKET.sub(repl, text)
    # bare source URLs (e.g. markdown links "[NASA](https://...)") must resolve too
    for m in _URL.finditer(stripped):
        ids.append(m.group(0).rstrip(".,;:"))
    stripped = _URL.sub(" ", stripped)
    # bare mentions (PSI-69 in prose) must also resolve
    for m in _BARE_CITE.finditer(stripped):
        ids.append(m.group(1).rstrip(".:"))
    stripped = _BARE_CITE.sub(" ", stripped)
    seen: dict[str, None] = {}
    for i in ids:
        seen.setdefault(i, None)
    return list(seen), stripped


# --------------------------------------------------------------------------- main entry


def validate(
    answer_markdown: str,
    pack: dict,
    numbers_used: list | None = None,
    citations: list | None = None,
) -> dict:
    """Check numbers and citations of an answer against a context pack. Never raises."""
    errors: list[str] = []
    text = answer_markdown or ""
    cite_ids, body = extract_citations(text)
    if citations:
        for c in citations:
            c = str(c).strip().strip("[]")
            if c and c not in cite_ids:
                cite_ids.append(c)
    citable = set(pack.get("citable_ids") or [])
    cite_report = []
    for cid in cite_ids:
        ok = cid in citable
        cite_report.append({"id": cid, "resolved": ok})
        if not ok:
            errors.append(f"unresolved citation: {cid}")

    body = _LIST_NUM.sub(" ", body)
    body = _strip_ignored(body)
    candidates = pack_numbers(pack)
    used: list[tuple[float, str]] | None = None
    if numbers_used is not None:
        used = []
        for v in numbers_used:
            try:
                fv = float(v["value"] if isinstance(v, dict) else v)
            except (TypeError, ValueError, KeyError):
                errors.append(f"numbers_used entry is not a number: {v!r}")
                continue
            used.append((fv, "numbers_used"))
            if _match(fv, False, candidates) is None and _match(fv, True, candidates) is None:
                errors.append(f"numbers_used value {fv:g} is not in the context pack")

    num_report = []
    for val, pct, raw in _numbers_in_text(body):
        src = _match(val, pct, candidates)
        item = {"text": raw + ("%" if pct else ""), "value": val, "source": src}
        num_report.append(item)
        if src is None:
            errors.append(f"number not in context pack: {raw}{'%' if pct else ''}")
        elif used is not None and _match(val, pct, used) is None:
            errors.append(f"number {raw} is not declared in numbers_used")

    return {"ok": not errors, "errors": errors, "numbers": num_report, "citations": cite_report}
