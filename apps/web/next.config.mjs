/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Emit a self-contained server bundle (.next/standalone) for a small Docker
  // runtime image — used by the App Runner deploy.
  output: "standalone",
};

export default nextConfig;
