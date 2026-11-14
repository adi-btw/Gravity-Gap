import type { Metadata } from "next";
import { Placeholder } from "@/components/Placeholder";

export const metadata: Metadata = { title: "Gravity Spectrum Map · Gravity Gap" };

export default function ExplorePage() {
  return (
    <Placeholder
      feature="F1"
      title="Gravity Spectrum Map"
      purpose="Summarize and rank the PSI fire-safety evidence along the gravity axis, so you can see which investigations are most relevant to your habitat."
      bullets={[
    "A 0 to 1 g axis with investigations at 0 g (ISS, Cygnus) and 1 g references, with the Moon and Mars inside the no-data zone",
    "A ranked list scored on atmosphere distance, hazard pillar, fuel realism, outcome data and test count, with editable weights",
    "Non-combustion records (PSI-181 solder, PSI-108 fluids) excluded with a visible note",
      ]}
    />
  );
}
