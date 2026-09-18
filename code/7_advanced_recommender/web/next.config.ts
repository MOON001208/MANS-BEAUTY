import type { NextConfig } from "next";
import path from "node:path";

const isGithubPages = process.env.DEPLOY_TARGET === "github-pages";

const nextConfig: NextConfig = {
  // Vercel 배포 시에는 basePath를 비우고, Github Pages 배포 시에만 /MANS-BEAUTY를 적용합니다.
  basePath: isGithubPages ? "/MANS-BEAUTY" : "",
  outputFileTracingRoot: path.resolve(process.cwd()),
  turbopack: { root: path.resolve(process.cwd()) },
  // 아래 설정들은 Vercel(정적배포 환경)과 Github Pages 둘 다 호환되도록 유지
  output: "export",
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
