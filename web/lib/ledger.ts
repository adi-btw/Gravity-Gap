/**
 * In-browser re-verification of ledger hashes (F5). Mirrors engine/ledger.py:
 *   sha256 = SHA-256 hex of json.dumps(record_without_sha256, sort_keys=True, separators=(",", ":"))
 * engine/ledger.py passes ensure_ascii=False and hashes the UTF-8 bytes, so non-ASCII text is hashed as-is.
 *
 * JSON.parse would lose number spellings (Python writes 10.0, JavaScript would re-serialize 10), so records are
 * parsed with a small lexeme-preserving parser and numbers are re-emitted exactly as they appear in the source.
 */

export type RawJson =
  | { t: "null" }
  | { t: "bool"; v: boolean }
  | { t: "num"; raw: string }
  | { t: "str"; v: string }
  | { t: "arr"; v: RawJson[] }
  | { t: "obj"; v: [string, RawJson][] };

export function parseRaw(text: string): RawJson {
  let i = 0;
  const ws = () => {
    while (i < text.length && " \t\n\r".includes(text[i])) i++;
  };
  const fail = (msg: string): never => {
    throw new SyntaxError(`${msg} at offset ${i}`);
  };
  const str = (): string => {
    i++; // opening quote
    let out = "";
    while (i < text.length) {
      const c = text[i];
      if (c === '"') {
        i++;
        return out;
      }
      if (c === "\\") {
        const n = text[i + 1];
        const map: Record<string, string> = { '"': '"', "\\": "\\", "/": "/", b: "\b", f: "\f", n: "\n", r: "\r", t: "\t" };
        if (n === "u") {
          const hex = text.slice(i + 2, i + 6);
          if (!/^[0-9a-fA-F]{4}$/.test(hex)) fail("bad unicode escape");
          out += String.fromCharCode(parseInt(hex, 16));
          i += 6;
        } else if (n in map) {
          out += map[n];
          i += 2;
        } else fail("bad escape");
      } else {
        out += c;
        i++;
      }
    }
    return fail("unterminated string");
  };
  const value = (): RawJson => {
    ws();
    const c = text[i];
    if (c === "{") {
      i++;
      const v: [string, RawJson][] = [];
      ws();
      if (text[i] === "}") {
        i++;
        return { t: "obj", v };
      }
      for (;;) {
        ws();
        if (text[i] !== '"') fail("expected key");
        const k = str();
        ws();
        if (text[i] !== ":") fail("expected ':'");
        i++;
        v.push([k, value()]);
        ws();
        if (text[i] === ",") {
          i++;
          continue;
        }
        if (text[i] === "}") {
          i++;
          return { t: "obj", v };
        }
        fail("expected ',' or '}'");
      }
    }
    if (c === "[") {
      i++;
      const v: RawJson[] = [];
      ws();
      if (text[i] === "]") {
        i++;
        return { t: "arr", v };
      }
      for (;;) {
        v.push(value());
        ws();
        if (text[i] === ",") {
          i++;
          continue;
        }
        if (text[i] === "]") {
          i++;
          return { t: "arr", v };
        }
        fail("expected ',' or ']'");
      }
    }
    if (c === '"') return { t: "str", v: str() };
    if (text.startsWith("true", i)) {
      i += 4;
      return { t: "bool", v: true };
    }
    if (text.startsWith("false", i)) {
      i += 5;
      return { t: "bool", v: false };
    }
    if (text.startsWith("null", i)) {
      i += 4;
      return { t: "null" };
    }
    // Python may also emit NaN / Infinity / -Infinity (allow_nan=True default).
    const m = /^(-?(?:\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|Infinity)|NaN)/.exec(text.slice(i));
    if (m) {
      i += m[0].length;
      return { t: "num", raw: m[0] };
    }
    return fail("unexpected token");
  };
  const out = value();
  ws();
  if (i !== text.length) fail("trailing characters");
  return out;
}

/** Python json.dumps string encoding (ensure_ascii=True): lowercase \uXXXX for control and non-ASCII. */
export function pyString(s: string, ensureAscii = false): string {
  let out = '"';
  for (let k = 0; k < s.length; k++) {
    const ch = s[k];
    const code = s.charCodeAt(k);
    if (ch === '"') out += '\\"';
    else if (ch === "\\") out += "\\\\";
    else if (ch === "\n") out += "\\n";
    else if (ch === "\r") out += "\\r";
    else if (ch === "\t") out += "\\t";
    else if (ch === "\b") out += "\\b";
    else if (ch === "\f") out += "\\f";
    else if (code < 0x20 || (ensureAscii && code > 0x7e)) out += "\\u" + code.toString(16).padStart(4, "0");
    else out += ch;
  }
  return out + '"';
}

/** Python key order: sort_keys sorts by code point (equal to UTF-16 order for BMP keys). */
function cmpKeys(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

export function canonical(v: RawJson, ensureAscii = false): string {
  switch (v.t) {
    case "null":
      return "null";
    case "bool":
      return v.v ? "true" : "false";
    case "num":
      return v.raw;
    case "str":
      return pyString(v.v, ensureAscii);
    case "arr":
      return "[" + v.v.map((x) => canonical(x, ensureAscii)).join(",") + "]";
    case "obj":
      return (
        "{" +
        [...v.v]
          .sort((a, b) => cmpKeys(a[0], b[0]))
          .map(([k, x]) => pyString(k, ensureAscii) + ":" + canonical(x, ensureAscii))
          .join(",") +
        "}"
      );
  }
}

/** Convert to plain JS values for display. */
export function toPlain(v: RawJson): unknown {
  switch (v.t) {
    case "null":
      return null;
    case "bool":
      return v.v;
    case "num":
      return Number(v.raw === "NaN" ? NaN : v.raw);
    case "str":
      return v.v;
    case "arr":
      return v.v.map(toPlain);
    case "obj":
      return Object.fromEntries(v.v.map(([k, x]) => [k, toPlain(x)]));
  }
}

export function getField(v: RawJson, key: string): RawJson | undefined {
  return v.t === "obj" ? v.v.find(([k]) => k === key)?.[1] : undefined;
}

export function withoutField(v: RawJson, key: string): RawJson {
  return v.t === "obj" ? { t: "obj", v: v.v.filter(([k]) => k !== key) } : v;
}

export async function sha256Hex(text: string): Promise<string> {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) throw new Error("Web Crypto is unavailable (needs a secure context: https or localhost).");
  const digest = await subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

export interface LedgerRecord {
  raw: RawJson;
  record: Record<string, unknown>;
}

/** Split the API response or a JSONL file into records (raw + plain). Blank lines are skipped. */
export function parseLedger(kind: "jsonl" | "ledger-json", text: string): LedgerRecord[] {
  let raws: RawJson[];
  if (kind === "jsonl") {
    raws = text
      .split(/\r?\n/)
      .filter((l) => l.trim() !== "")
      .map((l) => parseRaw(l));
  } else {
    const root = parseRaw(text);
    const preds = root.t === "arr" ? root : getField(root, "predictions");
    raws = preds && preds.t === "arr" ? preds.v : [];
  }
  return raws.map((raw) => ({ raw, record: toPlain(raw) as Record<string, unknown> }));
}

export interface Verification {
  ok: boolean;
  expected: string | null;
  computed: string;
}

export async function verifyRecord(raw: RawJson, ensureAscii = false): Promise<Verification> {
  const stored = getField(raw, "sha256");
  const expected = stored && stored.t === "str" ? stored.v.toLowerCase() : null;
  const computed = await sha256Hex(canonical(withoutField(raw, "sha256"), ensureAscii));
  return { ok: expected !== null && expected === computed, expected, computed };
}
