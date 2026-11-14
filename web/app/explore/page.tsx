import type { Metadata } from "next";
import { ExploreView } from "@/components/ExploreView";

export const metadata: Metadata = { title: "Gravity Spectrum · Gravity Gap" };

export default function ExplorePage() {
  return <ExploreView />;
}
