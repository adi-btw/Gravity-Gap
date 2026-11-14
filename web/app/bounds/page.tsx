import type { Metadata } from "next";
import { BoundsPanel } from "@/components/BoundsPanel";

export const metadata: Metadata = { title: "Bounds Panel · Gravity Gap" };

export default function BoundsPage() {
  return <BoundsPanel />;
}
