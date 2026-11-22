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

test("«Abbina» di una voce lunga suggerisce l'ingrediente: l'elenco intero", async ({ page }) => {
  // «pasta barilla integrale» somiglia a «pasta» per circa 0,250, sotto la soglia del
  // taglio (0,30): con l'elenco tagliato «Abbina» non offriva la pasta. Chiede l'elenco
  // intero, e «Pasta» c'è, con «Aggiungi «…»» accanto. Non si sceglie niente: la voce
  // si archivia e basta.
  // il `beforeEach` non aspetta la risposta di «Entra»: l'attesa del link «Dispensa»
  // evita una prima `page.request` senza cookie
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  const testo = "pasta barilla integrale";
  const creata = await page.request.post("/api/v1/shopping-list", {
    data: { raw_text: testo, ingredient_id: null },
  });
  expect(creata.status()).toBe(201);
  const id = ((await creata.json()) as { id: string }).id;
  try {
    const spunta = await page.request.patch(`/api/v1/shopping-list/${id}`, {
      data: { status: "checked" },
    });
    expect(spunta.ok()).toBe(true);
    await page.goto("/sistema");
    await page.getByRole("button", { name: `Abbina: ${testo}`, exact: true }).click();
    const campo = page.getByRole("textbox", { name: `Abbina un ingrediente per ${testo}` });
    await expect(campo).toHaveValue(testo);
    await expect(page.getByRole("option", { name: "Pasta", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: `Aggiungi «${testo}»` })).toBeVisible();
  } finally {
    try {
      const risposta = await page.request.patch(`/api/v1/shopping-list/${id}`, {
        data: { status: "archived" },
      });
      expect.soft(risposta.ok(), `pulizia: la voce ${id} non si è archiviata`).toBe(true);
    } catch (guasto) {
      expect.soft(false, `pulizia: non sono riuscito ad archiviare la voce ${id} (${guasto})`).toBe(true);
    }
  }
});

test("l'Anagrafica con «zucchina» mostra anche i vicini, la Lista no", async ({ page }) => {
  // «zucca» somiglia a «zucchina» per circa 0,364 e «zucchero» per circa 0,385: sotto
  // la soglia del taglio, quindi in Lista restano fuori; l'Anagrafica chiede l'elenco
  // intero e li mostra, per correggere un ingrediente registrato male
  await page.goto("/anagrafica");
  await page.getByLabel("Cerca un ingrediente o un prodotto").fill("zucchina");
  await expect(page.getByRole("link", { name: /^Zucchina\b/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /^Zucca\b/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /^Zucchero\b/ }).first()).toBeVisible();
  // lo stesso testo, nella stessa sessione, in Lista resta tagliato
  const elenco = await suggerimentiInLista(page, "zucchina");
  await expect(elenco.getByRole("option", { name: /^Zucchina\b/ })).toBeVisible();
  await expect(elenco.getByRole("option", { name: /^Zucca\b/ })).toHaveCount(0);
});
