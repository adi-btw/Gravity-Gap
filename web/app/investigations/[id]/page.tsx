import type { Metadata } from "next";
import { InvestigationCard } from "@/components/InvestigationCard";
import { readBundledCatalog } from "@/lib/catalogServer";

/** Pre-render one card per catalog record at build time; unknown ids still render and fetch on the client. */
export function generateStaticParams() {
  return readBundledCatalog().map((r) => ({ id: r.id }));
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  const rec = readBundledCatalog().find((r) => r.id === id);
  return { title: `${rec?.acronym ?? id} · Gravity Gap` };
}

export default async function InvestigationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const rid = decodeURIComponent(id);
  const catalog = readBundledCatalog();
  const names = Object.fromEntries(catalog.map((r) => [r.id, r.acronym]));
  return <InvestigationCard id={rid} initialRecord={catalog.find((r) => r.id === rid) ?? null} names={names} />;
}
