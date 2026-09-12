// defineConfig viene da vitest/config: quello di Vite non conosce la chiave `test`
import { configDefaults, defineConfig } from "vitest/config";
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
        background_color: "#eef1ee",
        theme_color: "#eef1ee",
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
    // e2e/ è di Playwright: i suoi file finiscono in `*.spec.ts` e rientrerebbero
    // nel pattern di default di Vitest, che li caricherebbe fuori dal loro runner.
    // Si parte dalle esclusioni di default perché assegnare `exclude` le sostituisce
    // tutte, node_modules compreso.
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
});
