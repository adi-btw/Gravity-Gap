import type { Metadata } from "next";
import { Placeholder } from "@/components/Placeholder";

export const metadata: Metadata = { title: "Test Planner · Gravity Gap" };

export default function PlannerPage() {
  return (
    <Placeholder
      feature="F6"
      title="Test Planner"
      purpose="If a lunar fire experiment can only run 10 tests, which ones shrink the uncertainty most?"
      bullets={[
    "Ranked candidate tests (g, P, O2, vent, metric) with expected band shrink",
    "A plain-language rationale and the investigations each test extends",
    "Design implications, such as the vent speed that keeps flames in the forced regime",
      ]}
    />
  );
}
