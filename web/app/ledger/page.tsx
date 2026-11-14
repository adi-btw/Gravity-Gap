import type { Metadata } from "next";
import { LedgerView } from "@/components/LedgerView";

export const metadata: Metadata = { title: "Prediction Ledger · Gravity Gap" };

export default function LedgerPage() {
  return <LedgerView />;
}
