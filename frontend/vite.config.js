import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Mobile-first PWA. The backend base URL is configurable via VITE_API_BASE
// (defaults to the local FastAPI dev server). During dev we also proxy /api.
export default defineConfig({
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
});
