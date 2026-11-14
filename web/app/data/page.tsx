import type { Metadata } from "next";
import { DataExplorer } from "@/components/DataExplorer";

export const metadata: Metadata = { title: "Data Explorer · Gravity Gap" };

export default function DataPage() {
  return <DataExplorer />;
}
