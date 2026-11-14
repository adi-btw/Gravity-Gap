import type { Metadata } from "next";
import { Placeholder } from "@/components/Placeholder";

export const metadata: Metadata = { title: "Data Explorer and Export · Gravity Gap" };

export default function DataPage() {
  return (
    <Placeholder
      feature="F8"
      title="Data Explorer and Export"
      purpose="Filter the cleaned PSI test table and download it with DOIs, to support predictive modeling."
      bullets={[
    "A filterable table of psi_tests.csv (investigation, O2, pressure, outcome, flags)",
    "A scatter builder",
    "CSV or JSON download with an auto-included citation block and cleaning-report version",
      ]}
    />
  );
}
