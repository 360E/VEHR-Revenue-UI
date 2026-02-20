/** @type {import('next').NextConfig} */
const nextConfig = {
  async redirects() {
    const apiBaseUrl =
      process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
    const normalized = apiBaseUrl.replace(/\/$/, "");
    return [
      {
        source: "/docs",
        destination: `${normalized}/docs`,
        permanent: false,
      },
      {
        source: "/redoc",
        destination: `${normalized}/redoc`,
        permanent: false,
      },
    ];
  },
  async rewrites() {
    const apiBaseUrl =
      process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
    const normalized = apiBaseUrl.replace(/\/$/, "");
    return [
      {
        source: "/api/v1/:path*",
        destination: `${normalized}/api/v1/:path*`,
      },
      {
        source: "/api",
        destination: `${normalized}/api/v1`,
      },
      {
        source: "/api/:path*",
        destination: `${normalized}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
