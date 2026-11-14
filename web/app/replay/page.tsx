import type { Metadata } from "next";
import { ReplayView } from "@/components/ReplayView";

export const metadata: Metadata = { title: "Real-fire replay · Gravity Gap" };

export default function ReplayPage() {
  return <ReplayView />;
}
