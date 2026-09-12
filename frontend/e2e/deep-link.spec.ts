import { test, expect } from "@playwright/test";

/**
 * A cosa serve questo file: provare il fallback per single page application di
 * Nginx, cioè `try_files $uri $uri/ /index.html` in frontend/nginx.conf.
 *
 * È un pezzo di configurazione di deploy, non di codice dell'app: nessun test in
 * jsdom può vederlo, e senza di esso aprire un indirizzo interno — un segnalibro su
 * /dispensa, l'app installata come PWA che riparte, un ricaricamento della pagina —
 * risponde 404 da Nginx al primo colpo.
 *
 * Va qui, in un file suo, e deve essere la prima navigazione di un contesto nuovo:
 * dopo una visita alla radice il service worker della PWA serve index.html da sé e
 * maschera il fallback mancante. Misurato: rompendo `try_files` il test di
 * error-branch.spec.ts (che ricarica /lista a service worker già installato) resta
 * verde, questo no.
 */

const PASSWORD = process.env.E2E_PASSWORD ?? "test";

test("un indirizzo interno aperto di colpo carica l'app, non un 404 di Nginx", async ({
  page,
}) => {
  const response = await page.goto("/dispensa");
  expect(response?.status(), "Nginx deve servire index.html per un percorso interno").toBe(200);

  // da qui in poi è l'app a lavorare: il primo 401 porta all'accesso, e dopo
  // l'accesso il percorso chiesto è ancora quello
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Dispensa" })).toBeVisible();
});
