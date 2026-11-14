import type { Metadata } from "next";
import { SuppressionView } from "@/components/SuppressionView";

export const metadata: Metadata = { title: "Put it out · Gravity Gap" };

export default function SuppressionPage() {
  return <SuppressionView />;
}
