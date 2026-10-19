import { expect, test, type Page } from "@playwright/test";

/**
 * Il piano 20 nel browser vero, a 375×812: la nota di una riga si corregge, si toglie e si
 * aggiunge dal modulo di modifica, e arriva al server; e nel passo del nome un non
 * alimentare del seme («detersivo per i piatti») lo dice subito, col collegamento che apre
 * l'anagrafica in un'altra scheda lasciando il modulo com'era.
 *
 * La ricetta si crea con `page.request` e si elimina nel `finally`; il passo del nome si
 * chiude con «Annulla», così nessun ingrediente nasce. Niente resta dietro.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

async function entra(page: Page) {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();
}

async function ingrediente(page: Page, nome: string): Promise<{ id: string; name: string }> {
  const risposta = await page.request.get(`/api/v1/ingredients/search?q=${encodeURIComponent(nome)}`);
  expect(risposta.ok()).toBe(true);
  const trovati = (await risposta.json()) as { id: string; name: string }[];
  const voce = trovati.find((trovato) => trovato.name === nome);
  expect(voce, `«${nome}» non è nel seme`).toBeDefined();
  return voce!;
}

// stringhe e non funzioni: questo file lo compila tsconfig.node.json, senza la libreria DOM
async function nonScorreDiLato(page: Page, schermata: string) {
  await page.waitForLoadState("networkidle");
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
  expect(scrollWidth, `${schermata} scorre di lato`).toBeLessThanOrEqual(clientWidth);
}

test("la nota di una riga si corregge, si toglie e si aggiunge dal modulo di modifica", async ({ page }) => {
  await entra(page);
  const cetriolo = await ingrediente(page, "cetriolo");
  const anguria = await ingrediente(page, "anguria");
  const titolo = `Insalata con le note e2e ${Date.now()}`;
  const creata = await page.request.post("/api/v1/recipes", {
    data: {
      title: titolo, instructions: "Taglia e condisci.", servings: 2, source: "manual",
      ingredients: [
        { ingredient_id: cetriolo.id, role: "primary", quantity_text: "1", note: "a rondelle" },
        { ingredient_id: anguria.id, role: "primary", quantity_text: "1 fetta" },
      ],
    },
  });
  expect(creata.ok()).toBe(true);
  const { id: ricettaId } = (await creata.json()) as { id: string };

  try {
    await page.goto(`/ricette/${ricettaId}/modifica`);
    const notaCetriolo = page.getByLabel("Nota per cetriolo");
    await expect(notaCetriolo).toHaveValue("a rondelle");

    const aggiungiNota = page.getByRole("button", { name: "Aggiungi una nota: anguria" });
    await expect(aggiungiNota).toBeVisible();
    expect((await aggiungiNota.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await aggiungiNota.click();
    const notaAnguria = page.getByLabel("Nota per anguria");
    await expect(notaAnguria).toBeFocused();
    await notaAnguria.fill("senza semi");
    await notaCetriolo.fill("");
    await nonScorreDiLato(page, "il modulo con le note aperte");

    await page.getByRole("button", { name: "Salva le modifiche" }).click();
    await expect(page).toHaveURL(new RegExp(`/ricette/${ricettaId}$`));

    const salvata = (await (await page.request.get(`/api/v1/recipes/${ricettaId}`)).json()) as {
      ingredients: { ingredient_name: string; note: string | null }[];
    };
    const note = Object.fromEntries(salvata.ingredients.map((riga) => [riga.ingredient_name, riga.note]));
    expect(note).toEqual({ cetriolo: null, anguria: "senza semi" });
  } finally {
    await page.request.patch(`/api/v1/recipes/${ricettaId}`, { data: { archived: true } });
  }
});

test("nel passo del nome un non alimentare lo dice subito, e l'anagrafica si apre a parte", async ({ page }) => {
  await entra(page);
  const detersivo = await ingrediente(page, "detersivo per i piatti");

  await page.goto("/ricette/nuova-ai");
  await page.getByLabel("Aggiungi un ingrediente").fill("detersivo per i piatti");
  await page.getByRole("button", { name: "Aggiungi «detersivo per i piatti»" }).click();

  const avviso = page.getByText(
    "In anagrafica questo nome è «Detersivo per i piatti», un non alimentare: una ricetta non può averlo. Scrivi un altro nome; se invece è l'anagrafica a sbagliare, correggila."
  );
  await expect(avviso).toBeVisible();
  const aggiungi = page.getByRole("button", { name: "Aggiungi alla ricetta", exact: true });
  await expect(aggiungi).toHaveAttribute("aria-disabled", "true");
  await expect(page.getByText("Cambia il nome: questo è un non alimentare.")).toBeVisible();

  const collegamento = page.getByRole("link", { name: "Correggi «Detersivo per i piatti» in Anagrafica" });
  await expect(collegamento).toHaveAttribute("href", `/anagrafica/ingrediente/${detersivo.id}`);
  expect((await collegamento.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await nonScorreDiLato(page, "il passo del nome con l'avviso");

  // l'anagrafica si apre in un'altra scheda, e il modulo resta com'era
  const [scheda] = await Promise.all([page.context().waitForEvent("page"), collegamento.click()]);
  await expect(scheda.getByRole("heading", { name: "Detersivo per i piatti" })).toBeVisible();
  await scheda.close();
  await expect(page.getByLabel("Come si chiama in generale?")).toHaveValue("detersivo per i piatti");

  // un altro nome, e l'avviso se ne va
  await page.getByLabel("Come si chiama in generale?").fill("zz prova nome e2e");
  await expect(avviso).toHaveCount(0);
  await expect(aggiungi).not.toHaveAttribute("aria-disabled", "true");
  await page.getByRole("button", { name: "Annulla", exact: true }).click();
  await expect(page.getByLabel("Come si chiama in generale?")).toHaveCount(0);
});
