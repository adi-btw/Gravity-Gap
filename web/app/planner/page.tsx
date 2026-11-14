import type { Metadata } from "next";
import { PlannerView } from "@/components/PlannerView";

export const metadata: Metadata = { title: "Test Planner · Gravity Gap" };

export default function PlannerPage() {
  return <PlannerView />;
}
