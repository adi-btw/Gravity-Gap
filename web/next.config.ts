import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // web/ is its own npm project; pin the tracing root so a parent lockfile is not picked up.
  outputFileTracingRoot: path.resolve(__dirname),
  // Optional separate build dir (e.g. NEXT_DIST_DIR=.next-e2e) so an e2e build does not clobber a running `next dev`.
  ...(process.env.NEXT_DIST_DIR ? { distDir: process.env.NEXT_DIST_DIR } : {}),
};

export default nextConfig;
