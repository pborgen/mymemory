/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Static HTML/CSS/JS for S3 + CloudFront (no Node server).
  output: "export",
  // /chat/ → out/chat/index.html so S3/CloudFront can serve directories.
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
