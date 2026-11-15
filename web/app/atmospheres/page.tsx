import type { Metadata } from "next";
import { AtmosphereMapView } from "@/components/AtmosphereMapView";

export const metadata: Metadata = { title: "Atmosphere evidence map · Gravity Gap" };

export default function AtmospheresPage() {
  return <AtmosphereMapView />;
}
