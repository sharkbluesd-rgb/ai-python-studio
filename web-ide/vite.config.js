import { defineConfig } from "vite";

export default defineConfig({
  base: process.env.GITHUB_PAGES === "true" ? "/ai-python-studio/" : "/",
  publicDir: "public",
  build: { outDir: "dist", emptyOutDir: true, sourcemap: false, target: "es2022" },
  worker: { format: "es" },
});