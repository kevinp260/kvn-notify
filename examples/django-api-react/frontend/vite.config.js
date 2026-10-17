import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    // The browser talks to one origin; Vite forwards /api to Django.
    proxy: { "/api": process.env.API_URL || "http://127.0.0.1:8000" },
    // In development the worker is served from /src/, so allow it to cover the whole site.
    headers: { "Service-Worker-Allowed": "/" },
  },
  build: {
    rollupOptions: {
      // Build the service worker as its own file at the site root: /sw.js
      input: { main: "index.html", sw: "src/sw.js" },
      output: {
        entryFileNames: (chunk) => (chunk.name === "sw" ? "sw.js" : "assets/[name]-[hash].js"),
      },
    },
  },
});
