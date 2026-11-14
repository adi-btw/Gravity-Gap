import { readFileSync } from "node:fs";
import path from "node:path";
import { normalizeCatalog } from "./api";
import type { CatalogRecord } from "./types";

/**
 * Build-time read of the catalog copied by scripts/copy-artifacts.mjs. Returns [] when it is missing so pages
 * fall back to a client fetch.
 */
export function readBundledCatalog(): CatalogRecord[] {
  try {
    const p = path.join(process.cwd(), "public", "artifacts", "catalog.json");
    return normalizeCatalog(JSON.parse(readFileSync(p, "utf-8")));
  } catch {
    return [];
  }
}
