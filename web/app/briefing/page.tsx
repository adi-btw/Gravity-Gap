import type { Metadata } from "next";
import { BriefingView } from "@/components/BriefingView";

export const metadata: Metadata = { title: "Fire-safety briefing · Gravity Gap" };

export default function BriefingPage() {
  return <BriefingView />;
}
