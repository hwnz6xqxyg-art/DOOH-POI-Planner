import { defineConfig } from "vite";

// Dev server proxies /api to the FastAPI backend (SPEC §12). In production the
// nginx `web` service serves the build and proxies /api to the api service.
export default defineConfig({
  server: {
    host: true,
    proxy: {
      "/api": {
        target: process.env.API_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
