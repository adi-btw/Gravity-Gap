import type { Metadata } from "next";

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
  return (
    <article className="max-w-3xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Method and limitations</h1>
        <p className="mt-1 text-sm text-muted">
          Gravity Gap bridges NASA&apos;s microgravity fire-safety data (PSI) and Earth data to estimate fire behavior
          at lunar and Martian gravity, where no direct fire data exist. Full citations and DOIs arrive with the
          catalog in phase 2.
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
    </article>
  );
}
