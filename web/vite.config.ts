import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const API_PROXY = {
  "/api": "http://127.0.0.1:8790",
  "/mcp": "http://127.0.0.1:8790",
  "/healthz": "http://127.0.0.1:8790",
};

export default defineConfig({
  plugins: [react()],
  server: { proxy: API_PROXY },
  preview: { proxy: API_PROXY },
  build: {
    target: "es2022",
    cssCodeSplit: true,
    reportCompressedSize: false,
  },
});
