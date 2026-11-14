"""Write artifacts/MANIFEST.json: sha256 + size of every file under artifacts/ (except the manifest).

    python scripts/build_manifest.py          # write
    python scripts/build_manifest.py --check  # exit 1 if any artifact differs from the manifest

The API's /health compares current hashes against this manifest (mismatch -> status "degraded").
Run it last in the artifact build, after every artifact (bounds, planner, rules, ai_cache) is final.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "artifacts"
MANIFEST = ARTIFACTS / "MANIFEST.json"


def current_files(adir: Path = ARTIFACTS) -> dict[str, dict]:
    out = {}
    for f in sorted(adir.rglob("*")):
        if f.is_file() and f.name != "MANIFEST.json":
            data = f.read_bytes()
            out[f.relative_to(adir).as_posix()] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    return out


def compare(manifest: dict, files: dict[str, dict]) -> dict:
    listed = manifest.get("files") or {}
    changed = sorted(k for k in listed if k in files and files[k]["sha256"] != listed[k].get("sha256"))
    missing = sorted(k for k in listed if k not in files)
    unlisted = sorted(k for k in files if k not in listed)
    return {"ok": not (changed or missing or unlisted), "changed": changed, "missing": missing, "unlisted": unlisted}


def build(adir: Path = ARTIFACTS) -> dict:
    files = current_files(adir)
    combined = hashlib.sha256("".join(f"{k}:{v['sha256']}\n" for k, v in files.items()).encode()).hexdigest()
    return {"version": 1, "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "generated_by": "scripts/build_manifest.py", "artifact_set_sha256": combined, "files": files}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if a.check:
        if not MANIFEST.exists():
            print("MANIFEST.json missing")
            return 1
        res = compare(json.loads(MANIFEST.read_text(encoding="utf-8")), current_files())
        print(json.dumps(res, indent=2))
        return 0 if res["ok"] else 1
    data = build()
    MANIFEST.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {MANIFEST} ({len(data['files'])} files, set {data['artifact_set_sha256'][:12]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
