import type { Metadata } from "next";
import { DetectionView } from "@/components/DetectionView";

export const metadata: Metadata = { title: "Detection evidence · Gravity Gap" };

export default function DetectionPage() {
  return <DetectionView />;
}
