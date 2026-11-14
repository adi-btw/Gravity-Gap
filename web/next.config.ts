import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // web/ is its own npm project; pin the tracing root so a parent lockfile is not picked up.
  outputFileTracingRoot: path.resolve(__dirname),
};

export default nextConfig;
