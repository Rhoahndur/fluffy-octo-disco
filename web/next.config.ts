import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow importing JSON files
  experimental: {
    serverActions: {
      bodySizeLimit: '10mb',
    },
  },
  // Increase API route timeout for LLM calls
  serverExternalPackages: ['@anthropic-ai/sdk'],
};

export default nextConfig;
