import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // "standalone" output is for the self-hosted Docker image (apps/web/Dockerfile)
  // — it conflicts with Vercel's own build/bundling pipeline, which sets
  // the VERCEL env var during its builds, so skip it there.
  ...(process.env.VERCEL ? {} : { output: "standalone" }),
};

export default nextConfig;
