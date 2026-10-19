import { expect, test, type Page } from "@playwright/test";

/**
 * S4, fetta 1, nel browser vero: in Anagrafica si sceglie l'alimento CIQUAL di un
 * ingrediente, si leggono i valori, si annulla. Lo stack carica la tabella di prova dopo il
 * seme (`backend/tests/ciqual_fixture.py`, valori inventati: piano
 * `2026-10-13-s4-ciqual.md`, Global Constraints). La prova parte e finisce con «pomodoro»
 * da decidere, e rimette a posto anche se fallisce a metà: nessun altro file di `e2e/`
 * dipende dalla sua scelta.
 *
 * `scrollWidth` lo calcola il browser dal CSS che Tailwind ha costruito: jsdom non lo vede.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

test.use({ viewport: { width: 375, height: 812 } });

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByRole("link", { name: "Ricette", exact: true })).toBeVisible();
});

async function ingrediente(page: Page, nome: string): Promise<{ id: string; name: string; kind: string }> {
  const risposta = await page.request.get(`/api/v1/ingredients/search?q=${encodeURIComponent(nome)}`);
  expect(risposta.ok()).toBe(true);
  const trovati = (await risposta.json()) as { id: string; name: string; kind: string }[];
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

test("in Anagrafica si sceglie l'alimento CIQUAL, si leggono i valori e si annulla, a 375px", async ({
  page,
}) => {
  const pomodoro = await ingrediente(page, "pomodoro");
  const percorso = `/api/v1/ingredients/${pomodoro.id}/nutrition`;
  // la partenza: da decidere, qualunque cosa abbia lasciato una prova interrotta
  expect((await page.request.delete(percorso)).ok()).toBe(true);
  try {
    await page.goto(`/anagrafica/ingrediente/${pomodoro.id}`);
    await expect(page.getByRole("heading", { name: "Valori nutrizionali" })).toBeVisible();
    await expect(page.getByText(/^Non ancora abbinato a un alimento della tabella CIQUAL/)).toBeVisible();

    await page.getByRole("button", { name: "Scegli l'alimento", exact: true }).click();
    await page.getByLabel("Cerca nella tabella CIQUAL", { exact: true }).fill("tomate");
    await page.getByRole("radio", { name: "Tomate, crue", exact: true }).check();
    const rigaScelta = page.locator("label", { has: page.getByRole("radio", { name: "Tomate, crue", exact: true }) });
    expect((await rigaScelta.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await nonScorreDiLato(page, "la ricerca aperta");
    await page.getByRole("button", { name: "Salva l'alimento", exact: true }).click();

    await expect(page.getByText("CIQUAL 2025 · 90001 · scelto a mano", { exact: true })).toBeVisible();
    await expect(page.getByRole("cell", { name: "18 kcal", exact: true })).toBeVisible();
    await page.getByText("Vitamine e minerali (3)", { exact: true }).click();
    await expect(page.getByRole("rowheader", { name: "Vitamina C", exact: true })).toBeVisible();
    await nonScorreDiLato(page, "la scheda con i valori");
    expect(((await (await page.request.get(percorso)).json()) as { state: string }).state).toBe("food");

    await page.getByRole("button", { name: "Annulla la scelta", exact: true }).click();
    await expect(page.getByText("Scelta annullata: l'AI lo abbinerà al prossimo giro.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Scegli l'alimento", exact: true })).toBeVisible();
  } finally {
    const risposta = await page.request.delete(percorso);
    expect.soft(risposta.ok(), `pulizia: la scelta di ${pomodoro.id} non si è annullata`).toBe(true);
  }
});

test("una voce non alimentare non ha «Valori nutrizionali»", async ({ page }) => {
  const detersivo = await ingrediente(page, "detersivo per i piatti");
  expect(detersivo.kind).toBe("non_food");

  await page.goto(`/anagrafica/ingrediente/${detersivo.id}`);
  await expect(page.getByRole("heading", { name: "Prodotti" })).toBeVisible();
  await page.waitForLoadState("networkidle");
  await expect(page.getByRole("heading", { name: "Valori nutrizionali" })).toHaveCount(0);
});
