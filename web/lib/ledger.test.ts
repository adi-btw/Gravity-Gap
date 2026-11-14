import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { canonical, parseLedger, parseRaw, sha256Hex, verifyRecord, withoutField } from "./ledger";

/**
 * Generated with engine/ledger.py (canonical_json + record_hash) on 2026-11-14:
 *   rec = {..., "tiny": 1e-05, "big": 1e16, "neg": -0.0, "transfer": {"basis": "O₂ 34% — “quoted” \\ tab\there"}, ...}
 *   rec["sha256"] = record_hash(rec); print(canonical_json(rec))
 * It exercises Python-only number spellings (5.0, 10.0, 1e-05, 1e+16, -0.0), non-ASCII text (ensure_ascii=False),
 * escapes and key sorting.
 */
const PY_LINE = String.raw`{"applicable":true,"artifact_hashes":{"bounds/x.json":"ab"},"author":"team","band90":[0.007271608683920468,0.7620381902167531],"big":1e+16,"created_at":"2026-11-14T18:00:00+00:00","estimate":0.20064279335457827,"habitat":{"L_mm":10.0,"g_m_s2":1.62,"label":"Lunar rover","o2":0.34,"p_psia":8.2,"preset_id":"lunar_rover","u_cm_s":5.0},"id":"GG-P0001","metric":"M1","model_version":"2a8ccd37105c","neg":-0.0,"none":null,"rationale":"tiny and big","sha256":"d5d34eb6edf387d91ee92249bbe6163fd0105aab2144f11a0b621cad425c4c64","status":"open","tiny":1e-05,"transfer":{"basis":"O₂ 34% — “quoted” \\ tab\there","confidence":"low"}}`;
const PY_HASH = "d5d34eb6edf387d91ee92249bbe6163fd0105aab2144f11a0b621cad425c4c64";

describe("ledger canonical hash (mirrors engine/ledger.py)", () => {
  it("sha256Hex matches a known vector", async () => {
    expect(await sha256Hex("abc")).toBe("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  });

  it("reproduces the Python hash for a record with tricky numbers and unicode", async () => {
    const v = await verifyRecord(parseRaw(PY_LINE));
    expect(v.computed).toBe(PY_HASH);
    expect(v.ok).toBe(true);
  });

  it("canonical form round-trips the Python line exactly (minus sha256 ordering)", () => {
    const raw = parseRaw(PY_LINE);
    expect(canonical(raw)).toBe(PY_LINE);
    expect(canonical(withoutField(raw, "sha256"))).not.toContain("sha256");
  });

  it("re-sorts keys written in any order", async () => {
    const shuffled = String.raw`{"status":"open","a":{"z":1,"b":2.0}}`;
    expect(canonical(parseRaw(shuffled))).toBe(String.raw`{"a":{"b":2.0,"z":1},"status":"open"}`);
  });

  it("flags a tampered record as a mismatch", async () => {
    const tampered = PY_LINE.replace('"estimate":0.20064279335457827', '"estimate":0.25');
    const v = await verifyRecord(parseRaw(tampered));
    expect(v.ok).toBe(false);
    expect(v.expected).toBe(PY_HASH);
  });

  it("JSON.parse/stringify would NOT reproduce the hash (why the raw parser exists)", async () => {
    const naive = JSON.parse(PY_LINE);
    delete naive.sha256;
    const sorted = (o: unknown): unknown =>
      Array.isArray(o) ? o.map(sorted) : o && typeof o === "object" ? Object.fromEntries(Object.keys(o).sort().map((k) => [k, sorted((o as Record<string, unknown>)[k])])) : o;
    expect(await sha256Hex(JSON.stringify(sorted(naive)))).not.toBe(PY_HASH);
  });

  it("parses the API response shape {predictions[], verification[]}", () => {
    const body = `{"predictions":[${PY_LINE}],"verification":[{"id":"GG-P0001","ok":true}]}`;
    const recs = parseLedger("ledger-json", body);
    expect(recs).toHaveLength(1);
    expect(recs[0].record.id).toBe("GG-P0001");
  });

  const ledgerFile = path.resolve(__dirname, "..", "..", "ledger", "predictions.jsonl");
  it.skipIf(!existsSync(ledgerFile))("verifies every line of the real ledger/predictions.jsonl", async () => {
    const recs = parseLedger("jsonl", readFileSync(ledgerFile, "utf-8"));
    expect(recs.length).toBeGreaterThan(0);
    for (const r of recs) {
      const v = await verifyRecord(r.raw);
      expect(v.ok, `record ${String(r.record.id)}`).toBe(true);
    }
  });
});
