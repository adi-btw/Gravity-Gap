import Link from "next/link";

interface Props {
  feature: string;
  title: string;
  purpose: string;
  bullets: string[];
}

/** Phase 2 placeholder that states the page's purpose so the IA is reviewable now. */
export function Placeholder({ feature, title, purpose, bullets }: Props) {
  return (
    <div className="max-w-3xl space-y-4">
      <p className="text-xs uppercase tracking-wider text-partial">{feature} · coming in phase 2</p>
      <h1 className="text-2xl font-semibold">{title}</h1>
      <p className="text-muted">{purpose}</p>
      <div className="hatch rounded-md border border-dashed border-line p-4">
        <h2 className="mb-2 text-sm font-medium">What this page will show</h2>
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {bullets.map((b) => (
            <li key={b}>{b}</li>
          ))}
        </ul>
      </div>
      <p className="text-sm">
        Available now:{" "}
        <Link href="/regime" className="text-micro underline">
          Regime calculator and pressure × gravity explorer
        </Link>
        .
      </p>
    </div>
  );
}
