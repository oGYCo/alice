import type { NextConfig } from "next";

const apiOrigin =
  process.env.NEXT_PUBLIC_API_URL?.trim() ||
  process.env.API_URL?.trim() ||
  "http://localhost:8000";
const normalizedApiOrigin = apiOrigin.replace(/\/$/, "");

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${normalizedApiOrigin}/api/v1/:path*`,
      },
      {
        source: "/health",
        destination: `${normalizedApiOrigin}/health`,
      },
    ];
  },
};

export default nextConfig;
