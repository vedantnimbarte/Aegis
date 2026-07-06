/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Emit a self-contained server bundle for the Docker image (see Dockerfile).
  output: "standalone",
};

export default nextConfig;
