import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Mobile-first PWA. Deployed statically to GitHub Pages under /vibe-economics/,
// so `base` is set for production builds; dev stays at the root path.
// Widgets compute client-side from committed JSON snapshots (public/data/*),
// but VITE_API_BASE + the /api proxy remain available for local backend dev.
export default defineConfig(({ command }) => ({
  // Subpath only for the production build (Pages); root "/" for the dev server.
  base: command === "build" ? process.env.VITE_BASE || "/vibe-economics/" : "/",
  plugins: [react()],
  server: {
    host: true, // expose on LAN so you can open it on your Android phone
    port: 5173,
    proxy: {
      "/api": {
        target: process.env.VITE_API_BASE || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
}));
