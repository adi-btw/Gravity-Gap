"""P1 Ingest: download PSI investigation metadata and experimental tables.

Usage:
    python scripts/fetch_psi.py                       # metadata + tables for the default ids
    python scripts/fetch_psi.py --metadata-only
    python scripts/fetch_psi.py --ids PSI-69,PSI-99
    python scripts/fetch_psi.py --metadata-only --isa-dir ~/Downloads

For each investigation id:
  1. GET https://psi.nasa.gov/geode-py/ws/repo/investigations/{id} (public JSON)
     -> data/psi_metadata/{id}.json
  2. For each entry in the metadata's `experimentalTable`, ask
     /geode-py/ws/studies/{id}/download?file=...&version=...&redirect=false for a
     signed URL (the body is the URL, possibly quoted) and download the file to
     data/psi_experimental_tables/ (spaces -> underscores, same naming as the
     existing files).

Everything is recorded in data/raw_manifest.json (sha256, size, version,
fetched_at, source). The script is idempotent: a table whose version and sha256
are unchanged is not downloaded again, and an unchanged metadata file is not
rewritten.

Fallback (--isa-dir): when the API fails for an id (it has been returning HTTP
500 after a 30 s gateway timeout), the script looks in DIR for a PSI ISA-Tab
export named "{id}_metadata_*.zip", parses its i_Investigation.txt and writes
the same JSON keys the catalog reads, with "_source": "isa-tab:<zip name>".
An existing metadata file is never replaced by a failed fetch.

Downloaded content is treated as data only: it is parsed as JSON / CSV text and
never executed.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import sys
import time
import urllib.parse
import zipfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
META_DIR = ROOT / "data" / "psi_metadata"
TABLE_DIR = ROOT / "data" / "psi_experimental_tables"
MANIFEST = ROOT / "data" / "raw_manifest.json"

API = "https://psi.nasa.gov/geode-py/ws"
DEFAULT_IDS = [
    "PSI-10", "PSI-20", "PSI-21", "PSI-22", "PSI-23", "PSI-25", "PSI-26", "PSI-39",
    "PSI-47", "PSI-60", "PSI-62", "PSI-68", "PSI-69", "PSI-98", "PSI-99", "PSI-100",
    "PSI-101", "PSI-102", "PSI-106", "PSI-107", "PSI-115", "PSI-117", "PSI-142",
    "PSI-159", "PSI-181",
]
TIMEOUT = httpx.Timeout(60.0, connect=15.0)
RETRIES = 2  # extra attempts after the first


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"generated_by": "scripts/fetch_psi.py", "files": {}}


def save_manifest(m: dict) -> None:
    m["updated_at"] = now_iso()
    m["files"] = dict(sorted(m["files"].items()))
    MANIFEST.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def get_with_retries(client: httpx.Client, url: str) -> httpx.Response:
    last: Exception | None = None
    for attempt in range(RETRIES + 1):
        try:
            r = client.get(url)
            r.raise_for_status()
            return r
        except (httpx.HTTPError,) as e:  # timeouts, connection errors, 4xx/5xx
            last = e
            if attempt < RETRIES:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"GET failed after {RETRIES + 1} attempts: {url}: {last}")


def table_local_name(file_name: str) -> str:
    return Path(file_name).name.replace(" ", "_")


# ---------------------------------------------------------------- ISA fallback
def _read_isa_text(raw: bytes) -> str:
    for enc in ("utf-8", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def parse_isa_investigation(text: str) -> dict[str, list[str]]:
    """Parse an ISA-Tab i_Investigation.txt into {row key: [values...]}.

    The csv module handles the quoted multi-line values (e.g. Objective).
    Only rows in the STUDY sections are kept (the INVESTIGATION block is empty in
    PSI exports and shares key names like 'Study ...' only under STUDY).
    """
    rows: dict[str, list[str]] = {}
    for rec in csv.reader(io.StringIO(text), delimiter="\t"):
        if not rec or not rec[0].strip():
            continue
        key = rec[0].strip()
        vals = [v.strip() for v in rec[1:]]
        if key not in rows:
            rows[key] = vals
    return rows


def isa_to_metadata(inv_id: str, zip_path: Path) -> dict:
    with zipfile.ZipFile(zip_path) as zf:
        name = next(n for n in zf.namelist() if n.lower().startswith("i_") and n.endswith(".txt"))
        rows = parse_isa_investigation(_read_isa_text(zf.read(name)))

    def one(key: str) -> str | None:
        vals = [v for v in rows.get(key, []) if v]
        if not vals:
            return None
        v = vals[0]
        return v.strip().strip('"').strip() or None

    dois = rows.get("Study Publication DOI", [])
    titles = rows.get("Study Publication Title", [])
    pubs = []
    for i in range(max(len(dois), len(titles))):
        d = dois[i] if i < len(dois) else ""
        t = titles[i] if i < len(titles) else ""
        if d or t:
            pubs.append({"doi": d or None, "title": t or None})
    study_id = one("Study Identifier")
    if study_id and study_id != inv_id:
        raise ValueError(f"{zip_path.name}: Study Identifier {study_id} != {inv_id}")
    return {
        "_source": f"isa-tab:{zip_path.name}",
        "id": inv_id,
        "title": one("Study Title"),
        "acronym": one("Comment[Investigation Acronym]"),
        "objective": one("Comment[Objective]"),
        "hypothesis": one("Comment[Hypothesis]"),
        "approach": one("Comment[Approach]"),
        "researchImpacts": one("Comment[Research Impacts]"),
        "doi": one("Comment[DOI]"),
        "flightProgram": one("Comment[Flight Platform]"),
        "experimentHardware": one("Comment[Experiment Hardware]"),
        "researchArea": one("Comment[Research Area]"),
        "subResearchArea": one("Comment[SubResearch Area]"),
        "projectType": one("Comment[Project Type]"),
        "studyDesignTypes": [v for v in rows.get("Study Design Type", []) if v],
        "publications": pubs,
        "related_glds": [],
        "experimentalTable": [],
    }


def find_isa_zip(isa_dir: Path | None, inv_id: str) -> Path | None:
    if not isa_dir or not isa_dir.is_dir():
        return None
    hits = sorted(isa_dir.glob(f"{inv_id}_metadata_*.zip"))
    return hits[0] if hits else None


# ---------------------------------------------------------------- main steps
def write_if_changed(path: Path, data: bytes) -> bool:
    if path.exists() and sha256_bytes(path.read_bytes()) == sha256_bytes(data):
        return False
    path.write_bytes(data)
    return True


def fetch_metadata(client, inv_id, manifest, isa_dir) -> dict | None:
    META_DIR.mkdir(parents=True, exist_ok=True)
    out = META_DIR / f"{inv_id}.json"
    rel = out.relative_to(ROOT).as_posix()
    meta: dict | None = None
    source = None
    try:
        r = get_with_retries(client, f"{API}/repo/investigations/{inv_id}")
        meta = r.json()
        if not isinstance(meta, dict):
            raise ValueError("metadata response is not a JSON object")
        meta.setdefault("_source", "psi-api")
        source = "psi-api"
    except Exception as e:  # noqa: BLE001 - report and fall back
        print(f"  [warn] {inv_id}: API metadata failed: {e}", file=sys.stderr)
        z = find_isa_zip(isa_dir, inv_id)
        if z is not None:
            try:
                meta = isa_to_metadata(inv_id, z)
                source = meta["_source"]
            except Exception as e2:  # noqa: BLE001
                print(f"  [warn] {inv_id}: ISA fallback failed: {e2}", file=sys.stderr)
    if meta is None:
        if out.exists():
            print(f"  {inv_id}: keeping existing {rel}")
            return json.loads(out.read_text(encoding="utf-8"))
        print(f"  {inv_id}: no metadata available")
        return None
    data = (json.dumps(meta, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    changed = write_if_changed(out, data)
    entry = manifest["files"].get(rel, {})
    if changed or not entry:
        entry = {
            "investigation_id": inv_id, "kind": "metadata", "source": source,
            "version": None, "sha256": sha256_bytes(data), "size": len(data),
            "fetched_at": now_iso(),
        }
    entry["checked_at"] = now_iso()
    manifest["files"][rel] = entry
    print(f"  {inv_id}: metadata {'written' if changed else 'unchanged'} ({source})")
    return meta


def fetch_tables(client, inv_id, meta, manifest) -> None:
    TABLE_DIR.mkdir(parents=True, exist_ok=True)
    for t in meta.get("experimentalTable") or []:
        fname = t.get("file_name") or t.get("fileName") or t.get("name")
        version = t.get("version", 1)
        if not fname:
            continue
        local = TABLE_DIR / table_local_name(fname)
        rel = local.relative_to(ROOT).as_posix()
        prev = manifest["files"].get(rel)
        if (prev and local.exists() and str(prev.get("version")) == str(version)
                and prev.get("sha256") == sha256_bytes(local.read_bytes())):
            prev["checked_at"] = now_iso()
            print(f"  {inv_id}: {local.name} unchanged (v{version})")
            continue
        q = urllib.parse.quote(fname, safe="")
        try:
            r = get_with_retries(
                client, f"{API}/studies/{inv_id}/download?file={q}&version={version}&redirect=false")
            signed = r.text.strip().strip('"').strip()
            if not signed.startswith("https://"):
                raise ValueError(f"unexpected signed-URL body: {signed[:80]!r}")
            body = get_with_retries(client, signed).content
        except Exception as e:  # noqa: BLE001
            print(f"  [warn] {inv_id}: download of {fname} failed: {e}", file=sys.stderr)
            continue
        changed = write_if_changed(local, body)
        manifest["files"][rel] = {
            "investigation_id": inv_id, "kind": "experimental_table", "source": "psi-api",
            "source_file_name": fname, "version": version, "sha256": sha256_bytes(body),
            "size": len(body), "fetched_at": now_iso(), "checked_at": now_iso(),
        }
        print(f"  {inv_id}: {local.name} {'downloaded' if changed else 'same bytes'} (v{version})")


def record_existing_tables(manifest: dict) -> None:
    """Hash tables already on disk that the manifest does not know yet (provenance)."""
    for p in sorted(TABLE_DIR.glob("*.csv")):
        rel = p.relative_to(ROOT).as_posix()
        if rel in manifest["files"]:
            continue
        b = p.read_bytes()
        manifest["files"][rel] = {
            "investigation_id": p.name.split("_", 1)[0], "kind": "experimental_table",
            "source": "pre-existing (downloaded manually from psi.nasa.gov)", "version": None,
            "sha256": sha256_bytes(b), "size": len(b), "fetched_at": None,
            "checked_at": now_iso(),
        }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ids", help="comma-separated PSI ids (default: built-in list)")
    ap.add_argument("--metadata-only", action="store_true", help="skip table downloads")
    ap.add_argument("--isa-dir", type=Path, default=None,
                    help="folder with PSI ISA-Tab zips used when the API fails")
    args = ap.parse_args(argv)
    ids = [s.strip() for s in args.ids.split(",")] if args.ids else DEFAULT_IDS
    isa_dir = args.isa_dir.expanduser() if args.isa_dir else None

    manifest = load_manifest()
    ok = 0
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True,
                      headers={"Accept": "application/json", "User-Agent": "gravity-gap-fetch/1.0"}) as client:
        for inv_id in ids:
            print(inv_id)
            meta = fetch_metadata(client, inv_id, manifest, isa_dir)
            if meta is not None:
                ok += 1
                if not args.metadata_only:
                    fetch_tables(client, inv_id, meta, manifest)
            save_manifest(manifest)  # save progress after each id
    record_existing_tables(manifest)
    save_manifest(manifest)
    print(f"metadata available for {ok}/{len(ids)} ids; manifest: {MANIFEST.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
