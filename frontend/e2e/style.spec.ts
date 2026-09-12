import { expect, test } from "@playwright/test";

/**
 * Lo stile è l'unica parte dell'app che i test in jsdom non possono vedere: Tailwind
 * genera il CSS al momento della costruzione, e jsdom non lo calcola. Questi controlli
 * girano nel browser vero, sull'app costruita e servita da Nginx — cioè su quella che
 * finisce in produzione.
 *
 * Esistono perché è già successo: la prima stesura della regola di base scriveva
 * `input[type="text"]`, che non seleziona un `<input>` senza attributo `type`. Metà
 * dei campi di quest'app sono scritti così, e sono rimasti trasparenti e senza bordo
 * su uno sfondo grigio — invisibili, senza che un solo test fallisse. Il campo provato
 * qui è di proposito uno senza `type`: provarne uno tipizzato non avrebbe visto niente.
 *
 * Non scrive niente e non legge lo stato: gira anche su uno stack già usato.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  // l'app parte presumendo una sessione valida: è il primo 401 a far comparire
  // l'accesso, quindi il campo si aspetta invece di darlo per già presente
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
});

test("i token del colore arrivano davvero alla pagina", async ({ page }) => {
  // --color-page: #eef1ee. Se il blocco @theme non venisse compilato, questo
  // resterebbe il bianco di default e tutto il resto sarebbe da rifare
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(238, 241, 238)");
});

test("un campo di testo si vede: ha fondo e bordo", async ({ page }) => {
  const field = page.getByLabel("Aggiungi alla lista");
  await expect(field).toBeVisible();

  // bianco sul fondo grigio della pagina, non trasparente
  await expect(field).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await expect(field).toHaveCSS("border-top-width", "1px");
  // sotto i 16px iOS ingrandisce la pagina da solo quando il campo prende fuoco
  await expect(field).toHaveCSS("font-size", "16px");
});
