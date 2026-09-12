// defineConfig viene da vitest/config: quello di Vite non conosce la chiave `test`
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import basicSsl from "@vitejs/plugin-basic-ssl";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  // HTTPS serve anche in sviluppo: la fotocamera non parte su http da telefono
  plugins: [
    react(),
    tailwindcss(),
    basicSsl(),
    VitePWA({
      registerType: "autoUpdate",
      manifest: {
        name: "Spena",
        short_name: "Spena",
        start_url: "/",
        display: "standalone",
        background_color: "#ffffff",
        theme_color: "#1f7a4d",
        icons: [
          { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
        ],
      },
    }),
  ],
  server: {
    host: true,
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    globals: true,
  },
});
