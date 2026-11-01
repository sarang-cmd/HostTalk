import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Relative asset URLs, so the built page works from any folder,
  // including a subpath on GitHub Pages and a plain file open.
  base: "./",
  build: {
    // The build is committed, so the page can be served by any static host:
    // GitHub Pages on /site, an S3 bucket, or a plain web server.
    outDir: "../site",
    emptyOutDir: true,
    assetsInlineLimit: 2048,
    // The screenshots are the heavy part. Keep them as files with a hash.
    assetsDir: "assets",
  },
  server: {
    // The sandbox preview reaches the dev server through a proxied host,
    // so the host check is off for this local tool.
    host: true,
    port: 5174,
    strictPort: true,
    allowedHosts: true,
    fs: {
      // Fonts live in the app's static folder, one level up. The dev server
      // needs to read that folder as well as this project.
      allow: [".."],
    },
  },
  preview: {
    host: true,
    port: 4173,
    allowedHosts: true,
  },
});
