const path = require("path");

const withPWA = require("next-pwa")({
  dest: "public",
  disable: process.env.NODE_ENV === "development",
  register: true,
  skipWaiting: true,
});

// Backend interne (réseau docker). Le navigateur passe par les rewrites ci-dessous.
const BACKEND = process.env.BACKEND_INTERNAL_URL || "http://backend:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: "/mini-app/:path*", destination: `${BACKEND}/mini-app/:path*` },
      { source: "/v1/:path*", destination: `${BACKEND}/v1/:path*` },
      { source: "/result/:path*", destination: `${BACKEND}/result/:path*` },
      { source: "/ws", destination: `${BACKEND}/ws` },
      { source: "/health", destination: `${BACKEND}/health` },
    ];
  },
  webpack(config) {
    // Bypass Clerk : aliase le package vers nos mocks (dev only)
    config.resolve.alias["@clerk/nextjs/server$"] = path.resolve(__dirname, "src/lib/clerk-mock-server.ts");
    config.resolve.alias["@clerk/nextjs$"] = path.resolve(__dirname, "src/lib/clerk-mock.tsx");
    return config;
  },
};

module.exports = withPWA(nextConfig);
