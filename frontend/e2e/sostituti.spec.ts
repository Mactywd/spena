import { expect, test, type Page } from "@playwright/test";

// R5 nel browser vero: «Sostituisci» senza l'AI (lo stack e2e non ha la chiave), la
// strada a mano per una ricetta, la voce generale scritta in Anagrafica, il ritorno. La
// prova lascia dietro di sé la voce generale della lonza (non c'è una rotta per toglierla,
// e non serve): su uno stack riusato la guardia in cima lo dice. Toglie il resto.
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  // senza quest'attesa la prima `page.request` può partire prima del cookie di sessione
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
});

async function ingrediente(page: Page, nome: string): Promise<string> {
  const trovati = (await (
    await page.request.get(`/api/v1/ingredients/search?q=${encodeURIComponent(nome)}`)
  ).json()) as { id: string; name: string }[];
  const voce = trovati.find((trovato) => trovato.name === nome);
  expect(voce, `«${nome}» non è nel seme`).toBeDefined();
  return voce!.id;
}

async function senzaScorrimentoLaterale(page: Page, luogo: string) {
  await page.waitForLoadState("networkidle");
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
  expect(scrollWidth, `${luogo} scorre di lato`).toBeLessThanOrEqual(clientWidth);
}

test("«Sostituisci» senza l'AI: la strada a mano per la ricetta, la voce generale in Anagrafica, il ritorno", async ({ page }) => {
  const lonza = await ingrediente(page, "lonza di maiale");
  const fettina = await ingrediente(page, "fettina di manzo");
  const tacchino = await ingrediente(page, "tacchino");
  const prima = (await (await page.request.get(`/api/v1/ingredients/${lonza}/substitutes`)).json()) as {
    contexts: { verdict: string | null }[];
  };
  expect(
    prima.contexts.every((contesto) => contesto.verdict === null),
    "lo stack e2e non è pulito: ricrealo con `down -v` e riesegui"
  ).toBe(true);

  const creata = await page.request.post("/api/v1/recipes", {
    data: {
      title: `Sostituti e2e ${Date.now()}`,
      instructions: "Cuoci.",
      servings: 2,
      source: "manual",
      // niente categoria: una ricetta salata
      ingredients: [
        { ingredient_id: lonza, role: "primary", quantity_text: "300 g" },
        { ingredient_id: fettina, role: "secondary", quantity_text: "1" },
      ],
    },
  });
  expect(creata.ok()).toBe(true);
  const ricetta = ((await creata.json()) as { id: string }).id;
  const inDispensa = await page.request.post("/api/v1/pantry", {
    data: { ingredient_id: tacchino, status: "available" },
  });
  expect(inDispensa.ok()).toBe(true);
  const confezione = ((await inDispensa.json()) as { id: string }).id;

  try {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(`/ricette/${ricetta}`);
    const apri = page.getByRole("button", { name: "Sostituisci lonza di maiale" });
    const riga = page.getByRole("listitem").filter({ has: apri });
    const scatola = (await apri.boundingBox())!;
    expect(scatola.width).toBeGreaterThanOrEqual(44);
    expect(scatola.height).toBeGreaterThanOrEqual(44);

    await apri.click();
    await expect(apri).toHaveAttribute("aria-expanded", "true");
    // senza chiave il server non chiama nessuno: resta la strada a mano
    await expect(riga.getByText("Nessun suggerimento ancora.")).toBeVisible();
    await riga.getByRole("button", { name: "Scrivi tu" }).click();
    await riga.getByLabel("Cosa usare al suo posto").fill("tacchin");
    await riga.getByRole("option", { name: "Tacchino" }).click();
    await riga.getByLabel("Nota per tacchino").fill("a fette sottili");
    await riga.getByRole("button", { name: "Salva per questa ricetta" }).click();

    await expect(riga.getByText("Al posto di lonza di maiale:")).toBeVisible();
    await expect(riga.getByText("Tacchino", { exact: true })).toBeVisible();
    await expect(riga.getByText("· a fette sottili")).toBeVisible();
    await expect(riga.getByText("ce l'hai")).toBeVisible();
    await expect(riga.getByText("Scelto a mano per questa ricetta.")).toBeVisible();
    await senzaScorrimentoLaterale(page, "il pannello dei sostituti");

    // è salvata: si ritrova dopo un ricaricamento
    await page.reload();
    await page.getByRole("button", { name: "Sostituisci lonza di maiale" }).click();
    await expect(riga.getByText("Scelto a mano per questa ricetta.")).toBeVisible();

    // in Anagrafica la voce generale non c'è ancora, la correzione della ricetta sì
    await page.goto(`/anagrafica/ingrediente/${lonza}`);
    await expect(page.getByRole("heading", { name: "Sostituti" })).toBeVisible();
    await expect(page.getByText("Corretto a mano in 1 ricetta.")).toBeVisible();
    await page.getByRole("button", { name: "Scrivi tu: nei piatti salati" }).click();
    await page.getByText("Si può omettere", { exact: true }).click();
    await page.getByRole("button", { name: "Salva", exact: true }).click();
    await expect(page.getByText("Si può omettere: il piatto riesce anche senza lonza di maiale.")).toBeVisible();
    await expect(page.getByText("Scelto a mano.", { exact: true })).toBeVisible();
    await senzaScorrimentoLaterale(page, "la sezione dei sostituti");

    // nella ricetta la correzione vince; tolta, vale la voce generale
    await page.goto(`/ricette/${ricetta}`);
    await page.getByRole("button", { name: "Sostituisci lonza di maiale" }).click();
    await expect(riga.getByText("Scelto a mano per questa ricetta.")).toBeVisible();
    await riga.getByRole("button", { name: "Torna al suggerimento generale" }).click();
    await expect(riga.getByText("Si può omettere: il piatto riesce anche senza lonza di maiale.")).toBeVisible();
    await expect(riga.getByText("Scelto a mano per i piatti salati.")).toBeVisible();
  } finally {
    try {
      const via = await page.request.delete(`/api/v1/recipes/${ricetta}/substitutes/${lonza}`);
      expect.soft(via.status(), "pulizia: la correzione non si è tolta").toBe(204);
      const archiviata = await page.request.patch(`/api/v1/pantry/${confezione}`, { data: { archived: true } });
      expect.soft(archiviata.ok(), "pulizia: il tacchino non si è archiviato").toBe(true);
      const eliminata = await page.request.patch(`/api/v1/recipes/${ricetta}`, { data: { archived: true } });
      expect.soft(eliminata.ok(), "pulizia: la ricetta non si è eliminata").toBe(true);
    } catch (guasto) {
      expect.soft(false, `pulizia dei sostituti: ${guasto}`).toBe(true);
    }
  }
});
