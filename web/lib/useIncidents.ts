"use client";

import { api, type Sourced } from "./api";
import type { IncidentsArtifact } from "./types";
import { useAsync } from "./useAsync";

// One request per page load, shared by the habitat bar and the replay page. Failures are not cached.
let pending: Promise<Sourced<IncidentsArtifact>> | null = null;

function loadIncidents(): Promise<Sourced<IncidentsArtifact>> {
  if (!pending) {
    pending = api.incidents().catch((e: unknown) => {
      pending = null;
      throw e;
    });
  }
  return pending;
}

export function useIncidents() {
  return useAsync(loadIncidents, "incidents");
}
