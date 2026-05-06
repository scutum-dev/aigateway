import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Streaming AI responses can run long; allow up to 5 min on Vercel functions
  // (Vercel default is 10s on hobby; 300s on pro). Adjust if you hit limits.
  experimental: {
    serverActions: { bodySizeLimit: "2mb" },
  },
};

export default nextConfig;
