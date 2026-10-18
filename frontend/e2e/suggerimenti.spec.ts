import { expect, test, type Page } from "@playwright/test";

/**
 * I suggerimenti tagliati (spec docs/superpowers/specs/2026-10-06-suggerimenti-soglia-bozza.md),
 * provati sull'anagrafica del seme attraverso l'app vera: chi contiene il testo all'inizio
 * di una parola, nel nome o in un alias, e gli altri solo se nessuno lo contiene. Queste
 * prove leggono e basta: non scrivono niente nello stack.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
});

async function suggerimentiInLista(page: Page, testo: string) {
  await page.goto("/lista");
  await page.getByLabel("Aggiungi alla lista", { exact: true }).fill(testo);
  return page.getByRole("listbox", { name: "Suggerimenti: Aggiungi alla lista" });
}

test("«zucch» in lista: lo zucchero e la zucchina sì, la zucca no", async ({ page }) => {
  const elenco = await suggerimentiInLista(page, "zucch");
  await expect(elenco.getByRole("option", { name: /^Zucchina\b/ })).toBeVisible();
  await expect(elenco.getByRole("option", { name: /^Zucchero\b/ }).first()).toBeVisible();
  await expect(elenco.getByRole("option", { name: /^Zucca\b/ })).toHaveCount(0);
  await expect(elenco.getByRole("option", { name: /^Semi misti\b/ })).toHaveCount(0);
});

test("«olio» in lista: il tonno sott'olio sì, per il suo alias; le olive no", async ({ page }) => {
  const elenco = await suggerimentiInLista(page, "olio");
  await expect(elenco.getByRole("option", { name: /^Olio di oliva\b/ })).toBeVisible();
  await expect(elenco.getByRole("option", { name: /^Tonno in scatola\b/ })).toBeVisible();
  await expect(elenco.getByRole("option", { name: /^Olive\b/ })).toHaveCount(0);
  await expect(elenco.getByRole("option", { name: /^Aglio\b/ })).toHaveCount(0);
});

test("«pollo» in lista: petto e coscia di pollo a metà nome, il pisello no", async ({ page }) => {
  const elenco = await suggerimentiInLista(page, "pollo");
  await expect(elenco.getByRole("option", { name: /^Petto di pollo\b/ })).toBeVisible();
  await expect(elenco.getByRole("option", { name: /^Coscia di pollo\b/ })).toBeVisible();
  await expect(elenco.getByRole("option", { name: /^Pisello\b/ })).toHaveCount(0);
  await expect(elenco.getByRole("option", { name: /^Polenta\b/ })).toHaveCount(0);
});

test("un ingrediente che non c'è: nei filtri del ricettario niente righe, e la nota lo dice", async ({
  page,
}) => {
  await page.goto("/ricette");
  await page.getByRole("button", { name: /^Filtri/ }).click();
  await page.getByLabel("Contiene ingredienti").fill("tamarindo");
  await expect(
    page.getByText("Nessun ingrediente somiglia a «tamarindo». Prova con un'altra parola.")
  ).toBeVisible();
  // l'elenco dei suggerimenti, non `option` in tutta la pagina: il «Categoria» del
  // pannello è un <select>, e le sue voci sono `option` anche loro
  await expect(
    page.getByRole("listbox", { name: "Suggerimenti: Contiene ingredienti" })
  ).toHaveCount(0);
});
