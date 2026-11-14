import type { Metadata } from "next";
import { Placeholder } from "@/components/Placeholder";

export const metadata: Metadata = { title: "Prediction Ledger · Gravity Gap" };

export default function LedgerPage() {
  return (
    <Placeholder
      feature="F5"
      title="Prediction Ledger"
      purpose="Frozen, hash-stamped predictions that LUCI or FM2 results can later confirm or refute."
      bullets={[
    "A table of predictions with status open, confirmed, refuted or inconclusive",
    "In-app SHA-256 verification of each record",
    "A note on how to check each prediction when partial-gravity data arrives",
      ]}
    />
  );
}
