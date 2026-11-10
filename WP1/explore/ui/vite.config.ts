import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: "0.0.0.0",
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/mcp": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      // Same-origin Typesense for Try Live / remote browsers (InstantSearch).
      "/typesense": {
        target: "http://127.0.0.1:8108",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/typesense/, ""),
      },
    },
  },
});
