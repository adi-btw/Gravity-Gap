import type { Metadata } from "next";
import { Placeholder } from "@/components/Placeholder";

export const metadata: Metadata = { title: "Bounds Panel · Gravity Gap" };

export default function BoundsPage() {
  return (
    <Placeholder
      feature="F4"
      title="Bounds Panel"
      purpose="The prediction itself: a partial-gravity estimate with a 90% band between the 0 g and 1 g references, traceable to evidence."
      bullets={[
    "Metric selector (M1 to M5) with the 0 g reference, 1 g reference and partial-g band",
    "Evidence list grouped by investigation and a sensitivity tornado chart",
    "An extrapolation state when no evidence applies, and a warning when partial g may be more flammable than both bounds",
      ]}
    />
  );
}
