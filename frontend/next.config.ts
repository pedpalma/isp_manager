import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // React Strict Mode: ajuda a pegar efeitos colaterais cedo (dev).
  reactStrictMode: true,
  // Em prod, gerar imagem enxuta com output "standalone" (entra no marco de deploy):
  // output: "standalone",
};

export default nextConfig;
