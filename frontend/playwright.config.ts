import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  use: {
    // La porta di default è quella che docker-compose.e2e.yml pubblica, non quella
    // del server di sviluppo: `npm run dev` serve in HTTPS (la fotocamera non parte
    // altrimenti) e un default http://localhost:5173 non risponderebbe. Il percorso
    // va provato sull'app costruita e servita da Nginx, che è quella che finisce in
    // produzione. Vedi il README per la sequenza completa.
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5174",
    ignoreHTTPSErrors: true,
  },
  // Un backend solo e un database solo: due file che scrivono insieme sulla stessa
  // dispensa si darebbero fastidio e il fallimento sembrerebbe un difetto dell'app.
  workers: 1,
});
