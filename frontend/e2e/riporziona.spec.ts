import { expect, test, type Page } from "@playwright/test";

/**
 * R2, secondo modo, nel browser vero: si tocca una dose, si scrive quanto se ne fa, e il
 * server riscala il resto. A 375×812, il telefono.
 *
 * Le due ricette si creano con `page.request`, che condivide i cookie della pagina — il
 * seme non ha una ricetta senza porzioni — e si eliminano nel `finally`. La cottura della
 * prima scrive solo uno storico: nessuna confezione di questi ingredienti è in dispensa,
 * quindi niente cambia in dispensa né in lista.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

async function entra(page: Page) {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();
}

async function ingrediente(page: Page, nome: string): Promise<string> {
  const risposta = await page.request.get(`/api/v1/ingredients/search?q=${encodeURIComponent(nome)}`);
  expect(risposta.ok()).toBe(true);
  const trovati = (await risposta.json()) as { id: string; name: string }[];
  const voce = trovati.find((trovato) => trovato.name === nome);
  expect(voce, `«${nome}» non è nel seme`).toBeDefined();
  return voce!.id;
}

/** Farro «160 g», porro «1», sale «q.b.»: una dose piena, un numero nudo, una che non si
 * riscala. */
async function ricetta(page: Page, servings: number | null) {
  const farro = await ingrediente(page, "farro");
  const porro = await ingrediente(page, "porro");
  const sale = await ingrediente(page, "sale");
  const creata = await page.request.post("/api/v1/recipes", {
    data: {
      title: `Farro e2e ${servings === null ? "senza porzioni" : `per ${servings}`} ${Date.now()}`,
      instructions: "Cuoci il farro, poi unisci il porro.",
      servings,
      source: "manual",
      ingredients: [
        { ingredient_id: farro, role: "primary", quantity_text: "160 g" },
        { ingredient_id: porro, role: "primary", quantity_text: "1" },
        { ingredient_id: sale, role: "secondary", quantity_text: "q.b." },
      ],
    },
  });
  expect(creata.ok()).toBe(true);
  const id = ((await creata.json()) as { id: string }).id;
  return {
    id,
    farro,
    elimina: async () => {
      const risposta = await page.request.patch(`/api/v1/recipes/${id}`, { data: { archived: true } });
      expect.soft(risposta.ok(), `pulizia: la ricetta ${id} non si è eliminata`).toBe(true);
    },
  };
}

function riga(page: Page, nome: string) {
  return page.getByRole("listitem").filter({ hasText: nome });
}

/** La dose che si tocca: dal merge di R5 ogni riga ha anche «Sostituisci …». */
const RISCALA = /: riscala da /;

// stringhe e non funzioni: questo file lo compila tsconfig.node.json, senza la libreria DOM
async function nonScorreDiLato(page: Page, schermata: string) {
  await page.waitForLoadState("networkidle");
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
  expect(scrollWidth, `${schermata} scorre di lato`).toBeLessThanOrEqual(clientWidth);
}

test("da una dose le altre seguono, lo stepper dice le porzioni che fa, e la cottura registra la dose", async ({
  page,
}) => {
  await entra(page);
  const r = await ricetta(page, 2);
  try {
    await page.goto(`/ricette/${r.id}`);
    const dose = page.getByRole("button", { name: "160 g: riscala da farro" });
    await expect(dose).toBeVisible();
    expect((await dose.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    // «q.b.» non è una dose da cui partire: resta testo
    await expect(riga(page, "sale").getByRole("button", { name: RISCALA })).toHaveCount(0);

    await dose.click();
    const campo = page.getByRole("textbox", { name: "Quanto ne fai?" });
    await expect(campo).toBeFocused();
    await expect(campo).toHaveAccessibleDescription("g");
    const riscala = page.getByRole("button", { name: "Riscala", exact: true });
    await expect(riscala).toHaveAttribute("aria-disabled", "true");
    await expect(riscala).toHaveAccessibleDescription("Scrivi quanto ne fai.");

    // oltre 50 volte: la frase del server sotto il campo, la ricetta com'era
    await campo.fill("10000");
    await riscala.click();
    await expect(page.getByRole("alert").filter({ hasText: "50 volte" })).toHaveText(
      "Così la ricetta cambierebbe più di 50 volte: scrivi un numero fra 3,2 g e 8000 g."
    );
    await expect(riga(page, "farro")).toContainText("160 g");
    await expect(campo).toBeVisible();
    await nonScorreDiLato(page, "il dettaglio col campo aperto e il rifiuto");

    await campo.fill("120");
    await riscala.click();
    await expect(page.getByText("≈ 1,5", { exact: true })).toBeVisible();
    await expect(riga(page, "farro").getByRole("button", { name: RISCALA })).toHaveText("120 g");
    await expect(riga(page, "porro").getByRole("button", { name: RISCALA })).toHaveText("0,75");
    await expect(riga(page, "sale")).toContainText("q.b.");
    await expect(page.getByText("1 dose su 3 non si riscala: resta com'è.")).toBeVisible();
    await expect(page.getByText("Riscalata da farro: 120 g.")).toBeVisible();
    await expect(campo).toHaveCount(0);
    await expect(page.getByRole("button", { name: "120 g: riscala da farro" })).toBeFocused();

    // la cottura manda la dose, non le porzioni
    await page.getByRole("button", { name: "Cucina", exact: true }).click();
    const cottura = page.waitForRequest(
      (richiesta) =>
        richiesta.method() === "POST" && richiesta.url().endsWith(`/api/v1/recipes/${r.id}/cook`)
    );
    await page.getByRole("button", { name: "Ho cucinato", exact: true }).click();
    const corpo = (await cottura).postDataJSON() as Record<string, unknown>;
    expect(corpo.anchor).toBe(r.farro);
    expect(corpo.amount).toBe("120");
    expect("servings" in corpo).toBe(false);
    await expect(page.getByRole("status").filter({ hasText: /^Segnato\./ })).toBeVisible();

    // + torna alle porzioni intere: da ≈ 1,5 a 2, cioè la ricetta com'è
    await page.getByRole("button", { name: "Una porzione in più" }).click();
    await expect(riga(page, "farro").getByRole("button", { name: RISCALA })).toHaveText("160 g");
    await expect(page.getByText(/^Riscalata da/)).toHaveCount(0);
  } finally {
    await r.elimina();
  }
});

test("senza porzioni si riscala lo stesso, lo stepper resta fermo, e si torna alle dosi della ricetta", async ({
  page,
}) => {
  await entra(page);
  const r = await ricetta(page, null);
  try {
    await page.goto(`/ricette/${r.id}`);
    await page.getByRole("button", { name: "160 g: riscala da farro" }).click();
    const campo = page.getByRole("textbox", { name: "Quanto ne fai?" });
    await campo.fill("80");
    // l'Invio basta, come al telefono il tasto «fatto» della tastiera
    await campo.press("Enter");

    // prima la risposta: finché il campo è aperto, nella riga ci sono tre pulsanti
    await expect(page.getByText("Riscalata da farro: 80 g.")).toBeVisible();
    await expect(riga(page, "farro").getByRole("button", { name: RISCALA })).toHaveText("80 g");
    await expect(riga(page, "porro").getByRole("button", { name: RISCALA })).toHaveText("0,5");
    const piu = page.getByRole("button", { name: "Una porzione in più" });
    await expect(piu).toHaveAttribute("aria-disabled", "true");
    await expect(piu).toHaveAccessibleDescription("Porzioni non indicate: si cambiano da «Modifica».");
    await expect(page.getByText("—", { exact: true })).toBeVisible();

    const torna = page.getByRole("button", { name: "Torna alle dosi della ricetta" });
    expect((await torna.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await torna.click();
    await expect(riga(page, "farro").getByRole("button", { name: RISCALA })).toHaveText("160 g");
    await expect(riga(page, "porro").getByRole("button", { name: RISCALA })).toHaveText("1");
    await expect(torna).toHaveCount(0);
  } finally {
    await r.elimina();
  }
});
