"""R3 detection spike: download a small, fixed selection of PSI smoke / dust files.

Usage:
    python scripts/fetch_detection.py             # download what is missing or changed
    python scripts/fetch_detection.py --dry-run   # list the selection and sizes, download nothing

Only the files named in SELECTED are fetched (never a whole investigation: PSI-101 alone is ~6 GB).
Each name must exist in data/psi_metadata/{id}.json, which also gives the version and the expected
size. A file larger than MAX_FILE_BYTES is refused. Files land in data/detection/raw/{id}/ (spaces ->
underscores) and are recorded in data/detection/manifest.json (sha256, size, version, fetched_at).

Same rules as scripts/fetch_psi.py: signed URL from
/geode-py/ws/studies/{id}/download?file=...&version=...&redirect=false, generic User-Agent, idempotent
(a file whose version and sha256 match the manifest is not downloaded again), and downloaded content
is data only: it is never executed.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from pathlib import Path

import httpx
from fetch_psi import (
    API,
    TIMEOUT,
    get_with_retries,
    now_iso,
    sha256_bytes,
    table_local_name,
)

ROOT = Path(__file__).resolve().parents[1]
META_DIR = ROOT / "data" / "psi_metadata"
RAW_DIR = ROOT / "data" / "detection" / "raw"
MANIFEST = ROOT / "data" / "detection" / "manifest.json"

MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_TOTAL_BYTES = 200 * 1024 * 1024

# investigation id -> exact PSI file names (as listed in the metadata)
SELECTED: dict[str, list[str]] = {
    "PSI-101": [  # SAME-R (Smoke Aerosol Measurement Experiment - Reflight)
        "PSI-101_Experimental table_SAME-R.csv",
        "PSI-101_Analyzed Data_Sample descriptions tables.docx",
        "PSI-101_Analyzed Data_thermal precipitator map updated.xlsx",
        "PSI-101_Analyzed Data_54 lampwick binneddatacorr from GWM.xlsx",
        "PSI-101_Analyzed Data_60 silicone.xlsx",
        "PSI-101_Analyzed Data_62 Kapton unaged.xlsx",
        "PSI-101_Analyzed Data_SAME, SAME-R_Results.xlsx",
    ],
    "PSI-102": [  # SAME
        "PSI-102_Experimental table_SAME.csv",
    ],
    "PSI-47": [  # DAFT / DAFT-2
        "PSI-47_Experimental table_DAFT.csv",
        "PSI-47_Analyzed Data_DAFT Retrieved Data Summary.xls",
        "PSI-47_Analyzed Data_flight data 063_PTrk0002.xls",
        "PSI-47_Analyzed Data_flight data 063_DTrk0002.xls",
        "PSI-47_Raw Data_PTrk0002.txt",
        "PSI-47_Raw Data_DTrk0002.txt",
        "PSI-47_Reports_DAFT_FinalReport.doc",  # says what the dust bags held and how D was derived
    ],
    "PSI-115": [  # smoke simulation built on SAME data
        "PSI-115_Science Documents_DataOrganizationDocument.pdf",
        "PSI-115_Reports_NNX17AF08A_FinalReport.pdf",  # only source for the PSD units / sampling point
        "PSI-115_Analyzed Data_nodeDiameters.dat",
        "PSI-115_Analyzed Data_8cmGravityPSD.dat",
        "PSI-115_Analyzed Data_8cmNoGravityPSD.dat",
        "PSI-115_Analyzed Data_8cmGravityNS_PSD.dat",
        "PSI-115_Analyzed Data_8cmNoGravityNoTF_PSD.dat",
        "PSI-115_Analyzed Data_10cmGravityPSD.dat",
        "PSI-115_Analyzed Data_10cmNoGravityPSD.dat",
    ],
}


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {"generated_by": "scripts/fetch_detection.py", "files": {}}


def save_manifest(m: dict) -> None:
    m["updated_at"] = now_iso()
    m["files"] = dict(sorted(m["files"].items()))
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def metadata_files(inv_id: str) -> dict[str, dict]:
    """{file_name: metadata entry} from the stored investigation metadata."""
    meta = json.loads((META_DIR / f"{inv_id}.json").read_text(encoding="utf-8"))
    out: dict[str, dict] = {}
    for key in ("added", "experimentalTable"):
        for e in meta.get(key) or []:
            if e.get("file_name"):
                out[e["file_name"]] = e
    return out


def plan() -> list[dict]:
    """Resolve SELECTED against the metadata. Raises if a name is unknown or too large."""
    items = []
    for inv_id, names in SELECTED.items():
        known = metadata_files(inv_id)
        for name in names:
            if name not in known:
                raise SystemExit(f"{inv_id}: {name!r} is not in data/psi_metadata/{inv_id}.json")
            e = known[name]
            size = int(e.get("file_size") or 0)
            if size > MAX_FILE_BYTES:
                raise SystemExit(f"{inv_id}: {name!r} is {size} bytes, over the per-file limit")
            items.append({
                "investigation_id": inv_id, "file_name": name, "version": e.get("version", 1),
                "expected_size": size, "subcategory": e.get("subcategory") or "",
                "local": RAW_DIR / inv_id / table_local_name(name),
            })
    total = sum(i["expected_size"] for i in items)
    if total > MAX_TOTAL_BYTES:
        raise SystemExit(f"selection is {total} bytes, over the total limit")
    return items


def fetch_one(client: httpx.Client, item: dict, manifest: dict) -> bool:
    local: Path = item["local"]
    rel = local.relative_to(ROOT).as_posix()
    inv_id, fname, version = item["investigation_id"], item["file_name"], item["version"]
    prev = manifest["files"].get(rel)
    if (prev and local.exists() and str(prev.get("version")) == str(version)
            and prev.get("sha256") == sha256_bytes(local.read_bytes())):
        prev["checked_at"] = now_iso()
        print(f"  {inv_id}: {local.name} unchanged (v{version})")
        return True
    q = urllib.parse.quote(fname, safe="")
    try:
        r = get_with_retries(
            client, f"{API}/studies/{inv_id}/download?file={q}&version={version}&redirect=false")
        signed = r.text.strip().strip('"').strip()
        if not signed.startswith("https://"):
            raise ValueError(f"unexpected signed-URL body: {signed[:80]!r}")
        body = get_with_retries(client, signed).content
        if len(body) > MAX_FILE_BYTES:
            raise ValueError(f"body is {len(body)} bytes, over the per-file limit")
    except Exception as e:  # noqa: BLE001 - report and continue with the next file
        print(f"  [warn] {inv_id}: download of {fname} failed: {e}", file=sys.stderr)
        return False
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_bytes(body)
    manifest["files"][rel] = {
        "investigation_id": inv_id, "kind": "detection_raw", "source": "psi-api",
        "source_file_name": fname, "subcategory": item["subcategory"], "version": version,
        "sha256": sha256_bytes(body), "size": len(body), "expected_size": item["expected_size"],
        "fetched_at": now_iso(), "checked_at": now_iso(),
    }
    print(f"  {inv_id}: {local.name} downloaded ({len(body)} bytes, v{version})")
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="list the selection, download nothing")
    args = ap.parse_args(argv)

    items = plan()
    total = sum(i["expected_size"] for i in items)
    if args.dry_run:
        for i in items:
            state = "present" if i["local"].exists() else "missing"
            print(f"{i['expected_size']:>10}  {state:7}  {i['local'].relative_to(ROOT).as_posix()}")
        print(f"{len(items)} files, {total / 1e6:.1f} MB expected (dry run, nothing downloaded)")
        return 0

    manifest = load_manifest()
    ok = 0
    with httpx.Client(timeout=TIMEOUT, follow_redirects=True,
                      headers={"Accept": "application/json", "User-Agent": "gravity-gap-fetch/1.0"}) as client:
        for item in items:
            ok += fetch_one(client, item, manifest)
            save_manifest(manifest)  # save progress after each file
    print(f"{ok}/{len(items)} files present; manifest: {MANIFEST.relative_to(ROOT).as_posix()}")
    return 0 if ok == len(items) else 1


if __name__ == "__main__":
    raise SystemExit(main())
