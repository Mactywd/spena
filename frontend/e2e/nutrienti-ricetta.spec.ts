import { expect, test, type Page } from "@playwright/test";

/**
 * S4, fetta 2, nel browser vero: i nutrienti della «Pasta al pomodoro» del seme a porzione,
 * con la riga «q.b.» fuori dal conto e detta, e i pesi in Anagrafica. Gli alimenti e i pesi
 * si scrivono con `page.request` (la tabella CIQUAL di prova la carica lo stack: piano
 * `2026-10-13-s4-grammi.md`, Global Constraints), e si tolgono alla fine, anche se la prova
 * fallisce a metà: nessun altro file di `e2e/` dipende da loro.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

test.use({ viewport: { width: 375, height: 812 } });

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByRole("link", { name: "Ricette", exact: true })).toBeVisible();
});

async function ingrediente(page: Page, nome: string): Promise<{ id: string; name: string }> {
  const risposta = await page.request.get(`/api/v1/ingredients/search?q=${encodeURIComponent(nome)}`);
  expect(risposta.ok()).toBe(true);
  const trovati = (await risposta.json()) as { id: string; name: string }[];
  const voce = trovati.find((trovato) => trovato.name === nome);
  expect(voce, `«${nome}» non è nel seme`).toBeDefined();
  return voce!;
}

async function coppia(page: Page, ingredienteId: string, unita: string): Promise<string> {
  const valori = (await (await page.request.get(`/api/v1/ingredients/${ingredienteId}/nutrition`)).json()) as {
    weights: { unit: string; unit_label: string }[];
  };
  const trovata = valori.weights.find((peso) => peso.unit_label === unita);
  expect(trovata, `nessuna coppia «${unita}» per ${ingredienteId}`).toBeDefined();
  return `/api/v1/ingredients/${ingredienteId}/unit-grams/${encodeURIComponent(trovata!.unit)}`;
}

// stringhe e non funzioni: questo file lo compila tsconfig.node.json, senza la libreria DOM
async function nonScorreDiLato(page: Page, schermata: string) {
  await page.waitForLoadState("networkidle");
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
  expect(scrollWidth, `${schermata} scorre di lato`).toBeLessThanOrEqual(clientWidth);
}

test("nel dettaglio della ricetta i valori a porzione, e il «q.b.» fuori dal conto con la strada, a 375px", async ({
  page,
}) => {
  const scelte: [string, string][] = [
    ["pasta", "90003"], ["pomodoro", "90001"], ["aglio", "90005"], ["olio di oliva", "90006"],
  ];
  const voci: Record<string, { id: string }> = {};
  for (const nome of ["pasta", "pomodoro", "aglio", "olio di oliva", "basilico"]) {
    voci[nome] = await ingrediente(page, nome);
  }
  const pesi: string[] = [];
  try {
    for (const [nome, codice] of scelte) {
      const scelta = await page.request.put(`/api/v1/ingredients/${voci[nome].id}/nutrition`, {
        data: { ciqual_code: codice },
      });
      expect(scelta.ok()).toBe(true);
    }
    for (const [nome, unita, grammi] of [["aglio", "spicchio", 5], ["olio di oliva", "cucchiai", 12]] as const) {
      const percorso = await coppia(page, voci[nome].id, unita);
      expect((await page.request.put(percorso, { data: { grams: grammi } })).ok()).toBe(true);
      pesi.push(percorso);
    }

    await page.goto("/ricette");
    await page.getByRole("link", { name: /Pasta al pomodoro/ }).first().click();
    await expect(page.getByRole("button", { name: "Cucina", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Mostra i valori nutrizionali", exact: true }).click();

    // pasta 642,6 + pomodoro 72 + aglio 6,55 + olio 216 = 937,15 kcal, su due porzioni
    await expect(page.getByRole("table", { name: "A porzione, su 2 porzioni" })).toBeVisible();
    await expect(page.getByRole("cell", { name: "469 kcal", exact: true })).toBeVisible();
    await expect(page.getByText("Contate 4 righe su 5.", { exact: true })).toBeVisible();
    await expect(
      page.getByRole("listitem").filter({ hasText: "Basilico (q.b.): senza una dose da pesare" })
    ).toBeVisible();
    await nonScorreDiLato(page, "il dettaglio coi valori aperti");

    // la strada: il nome porta alla scheda, dove si rimedia
    await page.getByRole("link", { name: "Basilico", exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`/anagrafica/ingrediente/${voci.basilico.id}$`));
  } finally {
    for (const percorso of pesi) {
      expect.soft((await page.request.delete(percorso)).ok(), `pulizia: ${percorso}`).toBe(true);
    }
    for (const [nome] of scelte) {
      const via = await page.request.delete(`/api/v1/ingredients/${voci[nome].id}/nutrition`);
      expect.soft(via.ok(), `pulizia: la scelta di ${nome}`).toBe(true);
    }
  }
});

test("in Anagrafica il peso di una coppia si corregge e si annulla, a 375px", async ({ page }) => {
  const aglio = await ingrediente(page, "aglio");
  const percorso = await coppia(page, aglio.id, "spicchio");
  expect((await page.request.delete(percorso)).ok()).toBe(true);
  try {
    await page.goto(`/anagrafica/ingrediente/${aglio.id}`);
    await expect(page.getByRole("heading", { name: "Pesi per unità" })).toBeVisible();
    const riga = page.getByRole("listitem").filter({ hasText: "1 spicchio" });
    await expect(riga.getByText("da decidere", { exact: true })).toBeVisible();

    const correggi = page.getByRole("button", { name: "Correggi il peso di 1 spicchio", exact: true });
    expect((await correggi.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await correggi.click();
    await page.getByLabel("Grammi in 1 spicchio", { exact: true }).fill("6");
    await nonScorreDiLato(page, "il campo dei grammi aperto");
    await page.getByRole("button", { name: "Salva il peso", exact: true }).click();
    await expect(riga.getByText("6 g · a mano", { exact: true })).toBeVisible();

    await correggi.click();
    await page.getByRole("button", { name: "Annulla il peso", exact: true }).click();
    await expect(riga.getByText("da decidere", { exact: true })).toBeVisible();
  } finally {
    expect.soft((await page.request.delete(percorso)).ok(), "pulizia").toBe(true);
  }
});
