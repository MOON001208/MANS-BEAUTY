import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  basePath: "/MANS-BEAUTY",
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
