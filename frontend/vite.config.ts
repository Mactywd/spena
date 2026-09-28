// defineConfig viene da vitest/config: quello di Vite non conosce la chiave `test`
import { configDefaults, defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import basicSsl from "@vitejs/plugin-basic-ssl";
import { VitePWA } from "vite-plugin-pwa";

// Cosa il service worker mette da parte alla prima visita. I primi sono gli schemi di
// default di Workbox, che assegnare `globPatterns` sostituisce: senza, la pagina e il
// codice non si precaricherebbero più. Poi Inter, che l'app serve da sé proprio per
// funzionare offline (spec T3 §2): solo latino e latino esteso, le lettere
// dell'italiano (~133 KB). Gli altri alfabeti li chiede il browser per `unicode-range`
// solo se una pagina li contiene, e precaricarli sarebbe peso scaricato per niente.
// Icone e manifesto li aggiunge il plugin da sé. Lo prova vite.config.test.ts.
export const PRECACHE_GLOB_PATTERNS = [
  "**/*.{js,css,html}",
  "assets/inter-latin-wght-normal-*.woff2",
  "assets/inter-latin-ext-wght-normal-*.woff2",
];

export default defineConfig({
  // HTTPS serve anche in sviluppo: la fotocamera non parte su http da telefono
  plugins: [
    react(),
    tailwindcss(),
    basicSsl(),
    VitePWA({
      registerType: "autoUpdate",
      workbox: { globPatterns: PRECACHE_GLOB_PATTERNS },
      manifest: {
        name: "Spena",
        short_name: "Spena",
        start_url: "/",
        display: "standalone",
        background_color: "#f1f4f2",
        theme_color: "#f1f4f2",
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
