import { expect, test, type Page } from "@playwright/test";
import { giornoDiRoma } from "./giornoDiRoma.ts";

/**
 * «Pasti» nel browser vero, a 375×812: la settimana scritta a mano, la ricetta di un pasto
 * fuori dal ricettario, la copia da «Scegli dal ricettario» e il rinvio da /ricette al pasto.
 * Tutto quel che si crea si toglie nel `finally` con `page.request` (che condivide i cookie
 * della pagina): un pasto con `DELETE /meals/<id>`, che archivia la ricetta fuori dal
 * ricettario. `workers: 1`: le prove non si pestano, e usano posti diversi.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

type Ricetta = { id: string; title: string; archived_at?: string | null };
type Pasto = { id: string; day: string; slot: string; recipe: { id: string; in_book: boolean } | null };

async function entra(page: Page) {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();
}

async function cercaNelRicettario(page: Page, titolo: string): Promise<Ricetta[]> {
  const risposta = await page.request.get(`/api/v1/recipes/search?q=${encodeURIComponent(titolo)}`);
  expect(risposta.ok()).toBe(true);
  return ((await risposta.json()) as Ricetta[]).filter((r) => r.title === titolo);
}

async function creaPasto(page: Page, giorno: string, slot: "lunch" | "dinner", piatto: string) {
  const risposta = await page.request.post("/api/v1/meals", { data: { day: giorno, slot, dish: piatto } });
  expect(risposta.ok()).toBe(true);
  return ((await risposta.json()) as Pasto).id;
}

async function togliPasto(page: Page, id: string) {
  const tolto = await page.request.delete(`/api/v1/meals/${id}`);
  expect.soft([200, 204, 404], `pulizia: il pasto ${id} non si è tolto`).toContain(tolto.status());
}

test("la settimana a mano: scrivere, ricetta fuori dal ricettario, salvarla, spostare, eliminare", async ({
  page,
}) => {
  await entra(page);
  const piatto = "Frittata di prova e2e";
  let pastoId: string | undefined;
  let ricettaId: string | undefined;
  try {
    await page.getByRole("link", { name: "Pasti", exact: true }).click();
    await expect(page).toHaveURL(/\/pasti$/);
    const oggi = page.locator('[aria-current="date"]');
    await expect(oggi).toHaveCount(1);
    // «Pranzo» poi «Cena»: il «+ da pianificare» della cena è l'ultimo
    await oggi.getByRole("link", { name: "+ da pianificare" }).last().click();
    await page.getByLabel("Piatto", { exact: true }).fill(piatto);
    await page.getByLabel("Accompagnamenti").fill("piadina · banana");
    await page.getByRole("button", { name: "Salva", exact: true }).click();
    await expect(page).toHaveURL(/\/pasti\?settimana=/);
    await expect(page.getByText(piatto)).toBeVisible();
    await expect(page.getByText("piadina · banana")).toBeVisible();

    await page.getByRole("link", { name: new RegExp(piatto) }).click();
    await expect(page).toHaveURL(/\/pasti\/[0-9a-f-]{36}$/);
    pastoId = page.url().split("/").pop()!;

    // la ricetta scritta per il pasto
    await page.getByRole("link", { name: "Scrivi la ricetta" }).click();
    await expect(page.getByLabel("Titolo")).toHaveValue(piatto);
    await page.getByLabel("Aggiungi un ingrediente").fill("uova");
    await page.getByRole("option", { name: /^uova/i }).first().click();
    await page.getByLabel("Procedimento").fill("Sbatti le uova, cuoci in padella.");
    await page.getByRole("button", { name: "Salva la ricetta" }).click();
    await expect(page).toHaveURL(new RegExp(`/pasti/${pastoId}$`));
    await expect(page.getByRole("heading", { name: piatto, level: 2 })).toBeVisible();
    await expect(page.getByRole("button", { name: /Cucina/ })).toHaveCount(0);
    await expect(page.getByRole("link", { name: /Cucina/ })).toHaveCount(0);

    const pasto = (await (await page.request.get(`/api/v1/meals/${pastoId}`)).json()) as Pasto;
    ricettaId = pasto.recipe!.id;
    expect(pasto.recipe!.in_book).toBe(false);
    expect(await cercaNelRicettario(page, piatto)).toEqual([]);

    await page.getByRole("button", { name: "Salva nel ricettario" }).click();
    await expect(page.getByRole("button", { name: "Togli dal ricettario" })).toBeVisible();
    expect((await cercaNelRicettario(page, piatto)).map((r) => r.id)).toEqual([ricettaId]);
    await page.getByRole("button", { name: "Togli dal ricettario" }).click();
    await expect(page.getByRole("button", { name: "Salva nel ricettario" })).toBeVisible();
    expect(await cercaNelRicettario(page, piatto)).toEqual([]);

    // spostare: domani a pranzo
    const domani = giornoDiRoma(1);
    await page.getByRole("button", { name: "Correggi" }).click();
    await page.getByLabel("Giorno", { exact: true }).fill(domani);
    await page.getByLabel("Pasto", { exact: true }).selectOption({ label: "Pranzo" });
    await page.getByRole("button", { name: "Salva le modifiche" }).click();
    await expect
      .poll(async () => {
        const p = (await (await page.request.get(`/api/v1/meals/${pastoId}`)).json()) as Pasto;
        return `${p.day} ${p.slot}`;
      })
      .toBe(`${domani} lunch`);
    await page.goto(`/pasti?settimana=${domani}`);
    await expect(page.getByText(piatto)).toBeVisible();

    // eliminare
    await page.getByRole("link", { name: new RegExp(piatto) }).click();
    await page.getByRole("button", { name: "Elimina" }).click();
    await page.getByRole("button", { name: "Sì, elimina" }).click();
    await expect(page).toHaveURL(/\/pasti\?settimana=/);
    await expect(page.getByText(piatto)).toHaveCount(0);
    // il posto torna vuoto: nella card di domani, il pranzo offre di nuovo «+ da pianificare»
    const giornoDomani = new Intl.DateTimeFormat("it-IT", { timeZone: "UTC", weekday: "long", day: "numeric" })
      .format(new Date(`${domani}T00:00:00Z`));
    const cardDomani = page
      .locator("li")
      .filter({ has: page.getByRole("heading", { name: new RegExp(`^${giornoDomani}`, "i") }) });
    await expect(cardDomani).toHaveCount(1);
    await expect(cardDomani.getByRole("link", { name: "+ da pianificare" })).toHaveCount(2);
    expect((await page.request.get(`/api/v1/meals/${pastoId}`)).status()).toBe(404);
    pastoId = undefined;
    const ricetta = (await (await page.request.get(`/api/v1/recipes/${ricettaId}`)).json()) as Ricetta;
    expect(ricetta.archived_at).toBeTruthy();
  } finally {
    if (pastoId) await togliPasto(page, pastoId);
  }
});

test("«Scegli dal ricettario» fa una copia", async ({ page }) => {
  await entra(page);
  const prima = (await (await page.request.get("/api/v1/recipes/search?limit=1")).json()) as Ricetta[];
  expect(prima.length).toBe(1);
  const { id: origineId, title } = prima[0];
  const pastoId = await creaPasto(page, giornoDiRoma(2), "lunch", "Pasto di prova e2e (copia)");
  try {
    const quante = (await cercaNelRicettario(page, title)).length;
    await page.goto(`/pasti/${pastoId}`);
    await page.getByRole("link", { name: "Scegli dal ricettario" }).click();
    await page.getByLabel("Cerca nel ricettario").fill(title);
    await page.getByRole("button", { name: new RegExp(title.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")) }).first().click();
    await expect(page).toHaveURL(new RegExp(`/pasti/${pastoId}$`));
    await expect(page.getByRole("heading", { name: title, level: 2 })).toBeVisible();

    // la ricetta del ricettario è ancora una sola, la stessa; il pasto ne ha una sua
    const dopo = await cercaNelRicettario(page, title);
    expect(dopo.length).toBe(quante);
    expect(dopo.map((r) => r.id)).toContain(origineId);
    const pasto = (await (await page.request.get(`/api/v1/meals/${pastoId}`)).json()) as Pasto;
    expect(pasto.recipe).not.toBeNull();
    expect(pasto.recipe!.id).not.toBe(origineId);
  } finally {
    await togliPasto(page, pastoId);
  }
});

test("la ricetta di un pasto aperta da /ricette porta al pasto", async ({ page }) => {
  await entra(page);
  const prima = (await (await page.request.get("/api/v1/recipes/search?limit=1")).json()) as Ricetta[];
  const pastoId = await creaPasto(page, giornoDiRoma(3), "lunch", "Pasto di prova e2e (rinvio)");
  try {
    const copia = await page.request.post(`/api/v1/meals/${pastoId}/recipe/copy`, {
      data: { recipe_id: prima[0].id },
    });
    expect(copia.ok()).toBe(true);
    const copiaId = ((await copia.json()) as Pasto).recipe!.id;
    await page.goto(`/ricette/${copiaId}`);
    await expect(page).toHaveURL(new RegExp(`/pasti/${pastoId}$`));
  } finally {
    await togliPasto(page, pastoId);
  }
});
