import type { Metadata } from "next";
import { RegimeTabs } from "@/components/RegimeTabs";

export const metadata: Metadata = { title: "Regime · Gravity Gap" };

export default function RegimePage() {
  return (
    <div className="space-y-4">
      <header>
        <h1 className="page-title">Which data family applies to your fire?</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">
          The Richardson number compares buoyancy-driven flow with ventilation. It tells you whether microgravity
          tests (forced flow), Earth tests (buoyant) or neither (mixed) describe a flame in your habitat. Everything
          here is computed in your browser from scaling laws and updates as you edit the habitat bar.
        </p>
      </header>
      <RegimeTabs />
    </div>
  );
}
