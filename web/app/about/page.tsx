import type { Metadata } from "next";
import Link from "next/link";
import { allDois } from "@/lib/catalog";
import { readBundledCatalog } from "@/lib/catalogServer";

export const metadata: Metadata = { title: "About · Gravity Gap" };

const FORMULAS = [
  ["Buoyant velocity", "u_b = C_b · √(g · L · ΔT/T∞)", "C_b ≈ 1, bracketed over [0.5, 1.5]"],
  ["Richardson number", "Ri = u_b² / u_f²", "forced < 0.1 ≤ mixed ≤ 10 < buoyant"],
  ["Grashof ratio", "G* = (g/g₀) · (P/P₀)²", "laminar buoyant flow structure only"],
  ["Effective flow", "u_eff = √(u_f² + (k · u_b)²)", "k bracketed over [0.3, 1.0]"],
  ["O₂ partial pressure", "p_O₂ = X_O₂ · P", "psia"],
  ["Atmosphere distance", "d = √(((X−X_t)/0.05)² + ((ln P − ln P_t)/0.3)²)", "d > 2 means extrapolation"],
];

export default function AboutPage() {
  const catalog = readBundledCatalog();
  const datasets = catalog.filter((r) => r.doi);
  const dois = allDois(catalog);
  return (
    <article className="max-w-3xl space-y-6">
      <header>
        <h1 className="page-title">Method and limitations</h1>
        <p className="mt-1 text-sm text-muted">
          Gravity Gap bridges NASA&apos;s microgravity fire-safety data (PSI) and Earth data to estimate fire behavior
          at lunar and Martian gravity, where no direct fire data exist. Every number traces to a PSI test record or a
          documented scaling law.
        </p>
      </header>
      <section>
        <h2 className="mb-2 text-lg font-medium">Core scaling laws (E1)</h2>
        <table className="w-full text-left text-sm">
          <thead className="text-xs text-muted">
            <tr>
              <th scope="col" className="py-1 pr-3">Quantity</th>
              <th scope="col" className="py-1 pr-3">Formula</th>
              <th scope="col" className="py-1">Notes</th>
            </tr>
          </thead>
          <tbody>
            {FORMULAS.map(([q, f, n]) => (
              <tr key={q} className="border-t border-line">
                <th scope="row" className="py-1.5 pr-3 font-normal">{q}</th>
                <td className="num py-1.5 pr-3">{f}</td>
                <td className="py-1.5 text-muted">{n}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 text-xs text-muted">
          Constants: g₀ = 9.81 m/s², P₀ = 14.7 psia, Moon 1.62 m/s², Mars 3.71 m/s². The browser and the Python
          engine share one set of reference cases so both give the same numbers.
        </p>
      </section>
      <section>
        <h2 className="mb-2 text-lg font-medium">Prediction method (E2 to E5)</h2>
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>
            <strong>Bounds (M1 to M5):</strong> M1 to M3 are fitted to FLEX and ACME CFI-G tests with bootstrap 90% bands;
            M4 and M5 are rule tables built from SAFFIRE-II and SPICE. An honesty gate refuses to give a number when the
            habitat atmosphere is more than 2 distance units from every training test.
          </li>
          <li>
            <strong>Gravity transfer:</strong> droplet and spherical-burner tests have no flow variable, so gravity never
            silently changes their estimate. The Monte Carlo regime fractions widen the band and lower the transfer
            confidence when buoyancy matters. Flow-dependent metrics map partial gravity through the effective flow.
          </li>
          <li>
            <strong>Ranking:</strong> relevance is a weighted sum of atmosphere match, fire-safety pillar, fuel realism,
            outcome availability and test count; the weights are editable on the{" "}
            <Link href="/explore" className="text-micro underline">spectrum page</Link>.
          </li>
          <li>
            <strong>Honesty test:</strong> each tested atmosphere is hidden from the model in turn, the model is refitted,
            and we check whether its 90% band catches the hidden tests. Results, including the misses, are on the{" "}
            <Link href="/trust" className="text-micro underline">Can I trust it? page</Link>.
          </li>
          <li>
            <strong>AI:</strong> the assistant writes explanations only from engine outputs and the catalog; a validator
            checks every number and citation. Without an API key it falls back to template or cached answers.
          </li>
          <li>
            <strong>Ledger:</strong> predictions are frozen with a SHA-256 of their canonical JSON, recomputed in your
            browser on the <Link href="/ledger" className="text-micro underline">ledger page</Link>.
          </li>
        </ul>
      </section>
      <section>
        <h2 className="mb-2 text-lg font-medium">Known limitations</h2>
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>Scaling laws give orders of magnitude. They do not resolve chemistry or radiation.</li>
          <li>
            PSI microgravity data mostly sit near 1 atm; low-pressure evidence is thinner (CFI 0.75 atm, CFI-G about
            0.5 bar, Flame Design about 0.5 atm).
          </li>
          <li>Solid materials, the real cabin hazard, have the fewest tests (SAFFIRE, BASS); results there are mostly qualitative.</li>
          <li>
            Partial gravity is not guaranteed to sit between 0 g and 1 g: flammability can peak at low-to-moderate flow.
          </li>
          <li>Vent speed and flame size presets are engineering assumptions and are editable.</li>
        </ul>
      </section>
      <section>
        <h2 className="mb-2 text-lg font-medium">Data sources</h2>
        <p className="text-sm text-muted">
          NASA Physical Sciences Informatics (PSI) system, combustion science investigations. Dataset DOIs
          ({datasets.length}) and publication DOIs ({dois.length - datasets.length}) from the catalog:
        </p>
        {catalog.length ? (
          <>
            <h3 className="mt-3 text-sm font-medium">PSI datasets</h3>
            <ul className="mt-1 space-y-1 text-sm">
              {datasets.map((r) => (
                <li key={r.id}>
                  <Link href={`/investigations/${r.id}`} className="num text-micro underline">{r.id}</Link>{" "}
                  {r.acronym ?? r.title}:{" "}
                  <a href={`https://doi.org/${r.doi}`} target="_blank" rel="noreferrer" className="num text-xs underline">
                    doi:{r.doi}
                  </a>
                </li>
              ))}
            </ul>
            <details className="mt-3 text-sm">
              <summary className="cursor-pointer">All {dois.length - datasets.length} publication DOIs</summary>
              <ul className="mt-2 space-y-1 text-xs">
                {dois
                  .filter((d) => !datasets.some((r) => r.doi === d.doi))
                  .map((d) => (
                    <li key={d.doi}>
                      <span className="num text-muted">{d.investigation}</span> {d.label}{" "}
                      <a href={`https://doi.org/${d.doi}`} target="_blank" rel="noreferrer" className="num underline">
                        doi:{d.doi}
                      </a>
                    </li>
                  ))}
              </ul>
            </details>
          </>
        ) : (
          <p className="mt-2 text-sm text-muted">The catalog artifact was not bundled with this build.</p>
        )}
      </section>
    </article>
  );
}
