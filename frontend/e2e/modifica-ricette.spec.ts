import { expect, test, type Page } from "@playwright/test";

/**
 * R10 nel browser vero (spec §8.6): una ricetta si modifica togliendo l'unico
 * ingrediente che manca, e diventa cucinabile; si elimina, si annulla, torna. E il
 * modulo di modifica a 375 px non scorre di lato: `scrollWidth` lo calcola il browser
 * dal CSS che Tailwind ha costruito, jsdom non lo vede.
 *
 * La ricetta e la voce di dispensa si creano con `page.request`, che condivide i
 * cookie della pagina; il titolo porta l'ora, perché il ricettario vive quanto lo
 * stack. In fondo la voce si toglie e la ricetta si elimina — non esiste una
 * cancellazione vera, ed è il punto di R10 — dentro un `finally`, così un'asserzione
 * fallita a metà non lascia la dispensa sporca per le prove dopo.
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

test("una ricetta si modifica e diventa cucinabile, si elimina e torna; a 375px il modulo non scorre di lato", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();

  const cetriolo = await ingrediente(page, "cetriolo");
  const anguria = await ingrediente(page, "anguria");
  const titolo = `Insalata e2e ${Date.now()}`;
  const creata = await page.request.post("/api/v1/recipes", {
    data: {
      title: titolo, instructions: "Taglia e condisci.", servings: 2, source: "manual",
      ingredients: [
        { ingredient_id: cetriolo.id, role: "primary", quantity_text: "1" },
        { ingredient_id: anguria.id, role: "primary", quantity_text: "1 fetta" },
      ],
    },
  });
  expect(creata.ok()).toBe(true);
  const { id: ricettaId } = (await creata.json()) as { id: string };
  let voceId: string | undefined;

  try {
    const inDispensa = await page.request.post("/api/v1/pantry", {
      data: { ingredient_id: cetriolo.id, status: "available" },
    });
    expect(inDispensa.ok()).toBe(true);
    voceId = (await inDispensa.json()).id as string;

    // manca l'anguria, e solo lei
    await page.goto(`/ricette/${ricettaId}`);
    await expect(page.getByRole("heading", { name: titolo })).toBeVisible();
    await expect(page.getByText("manca", { exact: true })).toHaveCount(1);

    // la modifica: via l'anguria, e la ricetta diventa cucinabile
    await page.getByRole("link", { name: "Modifica" }).click();
    await expect(page).toHaveURL(new RegExp(`/ricette/${ricettaId}/modifica$`));
    await page.getByRole("button", { name: "Togli anguria" }).click();
    await page.getByRole("button", { name: "Salva le modifiche" }).click();

    await expect(page).toHaveURL(new RegExp(`/ricette/${ricettaId}$`));
    await expect(page.getByRole("status").filter({ hasText: "Salvata." })).toBeVisible();
    await expect(page.getByText("manca", { exact: true })).toHaveCount(0);
    const dettaglio = (await (await page.request.get(`/api/v1/recipes/${ricettaId}`)).json()) as {
      cookable: boolean;
    };
    expect(dettaglio.cookable).toBe(true);

    // eliminare, annullare, tornare
    await page.getByRole("button", { name: "Elimina" }).click();
    await expect(page).toHaveURL(/\/ricette$/);
    const lapide = page.getByRole("status").filter({ hasText: `${titolo} eliminata` });
    await expect(lapide).toBeVisible();
    await lapide.getByRole("button", { name: "Annulla" }).click();
    await expect(lapide).toHaveCount(0);
    await page.getByLabel("Cerca nel ricettario").fill(titolo);
    await expect(page.getByRole("link", { name: new RegExp(titolo) })).toBeVisible();

    // a 375px, il modulo di modifica
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(`/ricette/${ricettaId}/modifica`);
    await expect(page.getByRole("button", { name: "Salva le modifiche" })).toBeVisible();
    await page.screenshot({ path: test.info().outputPath("modifica-375.png"), fullPage: true });
    await nonScorreDiLato(page, "il modulo di modifica");
  } finally {
    if (voceId) await page.request.patch(`/api/v1/pantry/${voceId}`, { data: { archived: true } });
    await page.request.patch(`/api/v1/recipes/${ricettaId}`, { data: { archived: true } });
  }
});
