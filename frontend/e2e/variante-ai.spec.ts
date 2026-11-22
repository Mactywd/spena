import { expect, test, type Page } from "@playwright/test";
import type { RecipeDraft } from "../src/domain/types.ts";

/**
 * R8 nel browser vero, a 375×812: dal dettaglio di una ricetta, «Modifica con AI»; l'AI
 * dello stack e2e non ha la chiave, e il server risponde 503 da sé — il guasto vero, che
 * lascia sull'originale; poi una proposta, il modulo, il salvataggio vero, il legame sotto
 * il titolo, l'originale intatta, e la lapide quando l'originale è eliminata.
 *
 * IL LIMITE, detto chiaro: la proposta riuscita la costruisce il test con `page.route`,
 * perché il modello qui non si chiama (la prima lezione di CLAUDE.md: è un oggetto fatto
 * dal test). Non prova cosa l'AI risponde — lo provano i finti di `test_ai_recipes.py` —
 * ma il resto è vero: lo schermo, il salvataggio con `derived_from_id`, la risposta del
 * server col legame. La ricetta si crea con `page.request`; in fondo le due ricette si
 * eliminano (non esiste una cancellazione vera, R10) dentro un `finally`.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

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

test("R8: la variante nasce dal dettaglio col legame all'originale, che resta com'è", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();

  const cetriolo = await ingrediente(page, "cetriolo");
  const anguria = await ingrediente(page, "anguria");
  const titolo = `Insalata e2e ${Date.now()}`;
  const creata = await page.request.post("/api/v1/recipes", {
    data: {
      title: titolo, instructions: "1. Taglia.\n2. Condisci.", servings: 2, source: "manual",
      source_ref: null, cost: 1,
      ingredients: [
        { ingredient_id: cetriolo.id, role: "primary", quantity_text: "1" },
        { ingredient_id: anguria.id, role: "primary", quantity_text: "300 g" },
      ],
    },
  });
  expect(creata.ok()).toBe(true);
  const originaleId = ((await creata.json()) as { id: string }).id;
  let varianteId: string | null = null;

  try {
    await page.goto(`/ricette/${originaleId}`);
    await page
      .getByRole("toolbar", { name: "Azioni della ricetta" })
      .getByRole("button", { name: "Modifica con AI", exact: true })
      .click();
    await page.getByLabel("Cosa vuoi cambiare?").fill("senza anguria, con più cetriolo");

    // 1. il guasto vero: lo stack non ha la chiave dell'AI, e si resta sull'originale
    await page.getByRole("button", { name: "Proponi la variante", exact: true }).click();
    await expect(
      page.getByText("L'AI non ha risposto: questa ricetta resta com'è. Riprova fra poco.", { exact: true })
    ).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`/ricette/${originaleId}$`));
    await expect(page.getByRole("heading", { level: 1, name: titolo })).toBeVisible();
    await nonScorreDiLato(page, "il dettaglio col pannello della variante");

    // 2. la proposta, costruita qui: solo ingredienti del seme, così non nasce niente in anagrafica
    const titoloVariante = `${titolo} senza anguria`;
    await page.route(`**/api/v1/recipes/${originaleId}/ai-variant`, (route) =>
      route.fulfill({
        json: {
          title: titoloVariante, description: null,
          instructions: "1. Taglia i cetrioli.\n2. Condisci.", servings: 2, cost: 1,
          ingredients: [
            {
              raw_name: "cetriolo", role: "primary", quantity_text: "2", ingredient_id: cetriolo.id,
              matched_name: "cetriolo", confident: true, proposed_category: null,
            },
          ],
        } satisfies RecipeDraft,
      })
    );
    await page.getByRole("button", { name: "Proponi la variante", exact: true }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Nuova variante" })).toBeVisible();
    await expect(page.getByText(`Variante di «${titolo}»`, { exact: true })).toBeVisible();
    await expect(page.getByLabel("Titolo", { exact: true })).toHaveValue(titoloVariante);
    await nonScorreDiLato(page, "il modulo della variante");

    // 3. il salvataggio vero: la variante, col legame sotto il titolo
    await page.getByRole("button", { name: "Salva la variante", exact: true }).click();
    await expect(page.getByRole("heading", { level: 1, name: titoloVariante })).toBeVisible();
    await expect(page).toHaveURL(/\/ricette\/[0-9a-f-]{36}$/);
    varianteId = new URL(page.url()).pathname.split("/").pop()!;
    expect(varianteId).not.toBe(originaleId);
    const legame = page.getByRole("link", { name: `Variante di «${titolo}»`, exact: true });
    await expect(legame).toBeVisible();
    expect((await legame.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await nonScorreDiLato(page, "il dettaglio della variante");

    // 4. il legame porta all'originale, che è com'era e non ne ha uno suo
    await legame.click();
    await expect(page).toHaveURL(new RegExp(`/ricette/${originaleId}$`));
    await expect(page.getByRole("heading", { level: 1, name: titolo })).toBeVisible();
    await expect(page.getByRole("link", { name: /^Variante di/ })).toHaveCount(0);
    const letta = (await (await page.request.get(`/api/v1/recipes/${originaleId}`)).json()) as {
      title: string;
      derived_from: unknown;
      ingredients: { ingredient_name: string; quantity_text: string | null }[];
    };
    expect(letta.title).toBe(titolo);
    expect(letta.derived_from).toBeNull();
    expect(letta.ingredients.map((r) => [r.ingredient_name, r.quantity_text]).sort()).toEqual([
      ["anguria", "300 g"],
      ["cetriolo", "1"],
    ]);

    // 5. l'originale eliminata: il legame lo dice, e porta alla lapide
    const via = await page.request.patch(`/api/v1/recipes/${originaleId}`, { data: { archived: true } });
    expect(via.ok()).toBe(true);
    await page.goto(`/ricette/${varianteId}`);
    await page.getByRole("link", { name: `Variante di «${titolo}» (eliminata)`, exact: true }).click();
    await expect(page.getByText("Questa ricetta è stata eliminata.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Ripristina" })).toBeVisible();
  } finally {
    for (const id of [varianteId, originaleId]) {
      if (!id) continue;
      const risposta = await page.request.patch(`/api/v1/recipes/${id}`, { data: { archived: true } });
      expect.soft(risposta.ok(), `pulizia: la ricetta ${id} non si è eliminata`).toBe(true);
    }
  }
});
