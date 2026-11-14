/** Catalog helpers shared by the investigation card, /about and /explore. */
import type { CatalogRecord } from "./types";

/**
 * First n sentences of PSI metadata text (no AI). Line breaks count as sentence ends; list markers such as
 * "A." at the start of a line are not treated as sentences on their own.
 */
export function firstSentences(text: string | null | undefined, n = 2): string {
  if (!text) return "";
  const parts = text
    .replace(/\r/g, "")
    .split(/\n+/)
    .flatMap((line) => line.trim().split(/(?<=[.!?])\s+(?=[A-Z0-9(“"])/))
    .map((s) => s.trim())
    .filter((s) => s && !/^[A-Z0-9][.)]$/.test(s));
  const out = parts.slice(0, n).map((s) => s.replace(/^(?:[A-Z]|\d+)[.)]\s+/, ""));
  return out.map((s) => (/[.!?:]$/.test(s) ? s : `${s}.`)).join(" ").replace(/:\.$/, ".");
}

const COND_LABEL: Record<string, { label: string; fmt: (v: number) => string }> = {
  o2: { label: "O₂ (mole fraction)", fmt: (v) => `${(v * 100).toFixed(1)}%` },
  o2_burner_stream: { label: "O₂ in burner stream", fmt: (v) => `${(v * 100).toFixed(1)}%` },
  pressure_atm: { label: "Pressure", fmt: (v) => `${v.toFixed(2)} atm` },
  flow_cm_s: { label: "Flow speed", fmt: (v) => `${v.toFixed(1)} cm/s` },
};

/** Conditions as display rows; unknown keys are shown with their raw name. */
export function conditionRows(c: CatalogRecord["conditions"]): { key: string; label: string; value: string }[] {
  if (!c) return [];
  return Object.entries(c as Record<string, unknown>).map(([k, v]) => {
    const spec = COND_LABEL[k] ?? { label: k.replace(/_/g, " "), fmt: (x: number) => String(Number(x.toPrecision(3))) };
    let value = "not recorded";
    if (Array.isArray(v) && v.length === 2 && v.every((x) => typeof x === "number")) {
      value = v[0] === v[1] ? spec.fmt(v[0]) : `${spec.fmt(v[0])} – ${spec.fmt(v[1])}`;
    } else if (typeof v === "number") value = spec.fmt(v);
    else if (typeof v === "string") value = v;
    return { key: k, label: spec.label, value };
  });
}

/** Every DOI in the catalog: investigation DOIs and publication DOIs, de-duplicated. */
export function allDois(records: CatalogRecord[]): { doi: string; label: string; investigation: string }[] {
  const seen = new Set<string>();
  const out: { doi: string; label: string; investigation: string }[] = [];
  records.forEach((r) => {
    const push = (doi: string | null | undefined, label: string) => {
      if (!doi) return;
      const d = doi.trim();
      if (seen.has(d.toLowerCase())) return;
      seen.add(d.toLowerCase());
      out.push({ doi: d, label, investigation: r.id });
    };
    push(r.doi, `${r.acronym ?? r.id}: ${r.title ?? "dataset"}`);
    (r.publications ?? []).forEach((p) => push(p.doi, p.title ?? "publication"));
  });
  return out;
}
