import type { Metadata } from "next";
import { TrustView } from "@/components/TrustView";

export const metadata: Metadata = { title: "Can I trust it? · Gravity Gap" };

export default function TrustPage() {
  return <TrustView />;
}
