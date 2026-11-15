// Reads the committed Gravity Gap artifacts and writes src/facts.json.
// Every number the video prints comes from this file; nothing is typed in by hand.
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, "..", "..");
const read = (rel) => JSON.parse(readFileSync(path.join(repo, "artifacts", rel), "utf-8"));

const catalog = read("catalog.json");
const comb = catalog.investigations.filter((r) => r.is_combustion);
const cleaned = comb.filter((r) => (r.n_tests_basis ?? "").startsWith("rows in data/clean/psi_tests.csv"));
const M = (m) => read(`bounds/lunar_base_${m}.json`);
const m1 = M("M1");
const m2 = M("M2");
const metrics = ["M1", "M2", "M3", "M4", "M5"].map((m) => {
  const b = M(m);
  return { metric: m, label: b.label, applicable: b.applicable, estimate: b.estimate, band90: b.band90 };
});
const r2 = m2.reason ?? "";
const holdout = read("holdout.json");
const planner = read("planner.json");
const briefing = read("briefing/lunar_base.json");

// Mars gravity: the mars_base preset in web/lib/presets.ts (not an artifact), read from source text.
const presets = readFileSync(path.join(repo, "web", "lib", "presets.ts"), "utf-8");
const marsBlock = presets.slice(presets.indexOf('id: "mars_base"'));
const marsG = Number(marsBlock.match(/g_m_s2:\s*([\d.]+)/)[1]);
const G0 = Number(readFileSync(path.join(repo, "web", "lib", "physics.ts"), "utf-8").match(/G0 = ([\d.]+)/)[1]);

const facts = {
  cleanedTests: cleaned.reduce((s, r) => s + (r.n_tests ?? 0), 0),
  combustionInvestigations: comb.length,
  orbitInvestigations: comb.filter((r) => r.gravity_levels.includes("microgravity")).length,
  earthInvestigations: comb.filter((r) => r.gravity_levels.includes("normal_gravity")).length,
  g: { moon: m1.habitat.g_m_s2, mars: marsG, earth: G0 },
  habitat: { p_psia: m1.habitat.p_psia, o2: m1.habitat.o2 },
  m1: {
    estimate: m1.estimate,
    band90: m1.band90,
    band0g: m1.ref_0g.band90,
    widen: Number(m1.transfer.basis.match(/widened x(\d+(?:\.\d+)?)/)[1]),
    confidence: m1.transfer.confidence,
    nTrain: m1.n_train,
  },
  m2: {
    distance: Number(r2.match(/distance (\d+\.\d+)\)/)[1]),
    gate: Number(r2.match(/more than (\d+(?:\.\d+)?) atmosphere/)[1]),
  },
  metrics,
  noEvidence: metrics.filter((m) => !m.applicable).length,
  trust: { held: holdout.overall.band_coverage.k, of: holdout.overall.band_coverage.n },
  planner1: planner.items[0],
  verdicts: briefing.verdicts.map((v) => ({ label: v.label, value: v.value })),
};
writeFileSync(path.join(here, "..", "src", "facts.json"), JSON.stringify(facts, null, 2) + "\n");
console.log(JSON.stringify(facts, null, 1));
