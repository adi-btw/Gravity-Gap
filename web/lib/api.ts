/** Backend base URL (FastAPI, plan/contracts.md). Phase 1 physics runs client-side; later panels fetch from here. */
export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");
