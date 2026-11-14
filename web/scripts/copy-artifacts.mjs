// Copy the build artifacts (../artifacts/**/*.json|md and ../ledger/predictions.jsonl) into
// web/public/artifacts/ so every page can fall back to static data when the API is down (plan R4/R13).
// Missing sources are tolerated: the script reports what it skipped and always exits 0.
import { copyFileSync, existsSync, mkdirSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(here, "..");
const repoRoot = path.resolve(webRoot, "..");
const srcArtifacts = path.join(repoRoot, "artifacts");
const srcLedger = path.join(repoRoot, "ledger", "predictions.jsonl");
const dest = path.join(webRoot, "public", "artifacts");

const EXTENSIONS = new Set([".json", ".md"]);
const copied = [];

function walk(dir, rel = "") {
  for (const name of readdirSync(dir)) {
    const abs = path.join(dir, name);
    const relPath = rel ? `${rel}/${name}` : name;
    const st = statSync(abs);
    if (st.isDirectory()) walk(abs, relPath);
    else if (EXTENSIONS.has(path.extname(name).toLowerCase())) {
      const out = path.join(dest, ...relPath.split("/"));
      mkdirSync(path.dirname(out), { recursive: true });
      copyFileSync(abs, out);
      copied.push(relPath);
    }
  }
}

rmSync(dest, { recursive: true, force: true });
mkdirSync(dest, { recursive: true });

if (existsSync(srcArtifacts)) walk(srcArtifacts);
else console.warn(`[copy-artifacts] ${srcArtifacts} not found; offline fallback will have no data.`);

if (existsSync(srcLedger)) {
  mkdirSync(path.join(dest, "ledger"), { recursive: true });
  copyFileSync(srcLedger, path.join(dest, "ledger", "predictions.jsonl"));
  copied.push("ledger/predictions.jsonl");
} else {
  console.warn("[copy-artifacts] ledger/predictions.jsonl not found; the ledger page needs the API.");
}

// An index of what is available offline, so the data layer can avoid 404 probes.
writeFileSync(
  path.join(dest, "index.json"),
  JSON.stringify({ generated_at: new Date().toISOString(), files: copied.sort() }, null, 1),
);
console.log(`[copy-artifacts] copied ${copied.length} file(s) to public/artifacts/`);
