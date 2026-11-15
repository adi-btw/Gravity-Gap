import type { Metadata } from "next";
import { CompareView } from "@/components/CompareView";

export const metadata: Metadata = { title: "Compare · Gravity Gap" };

export default function ComparePage() {
  return <CompareView />;
}
