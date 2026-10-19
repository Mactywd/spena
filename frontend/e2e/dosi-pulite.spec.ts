import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

/**
 * La pulizia delle dosi dell'import nel browser vero, col comando vero nel container del
 * backend dello stack e2e (come `import-review.spec.ts` lancia i suoi aiutanti). Una
 * ricetta con le dosi nella forma di GialloZafferano — gli a capo e le tabulazioni —, la
 * prova che non salva niente, la scrittura, e il dettaglio che mostra la nota sotto il nome
 * e riscala la dose pulita. A 375×812, il telefono.
 *
 * Il comando passa su tutte le righe della base dello stack: quelle del seme non hanno la
 * forma dell'import, e non cambiano. La ricetta si crea con `page.request`, che condivide i
 * cookie della pagina, e si elimina nel `finally`.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";
const RADICE = fileURLToPath(new URL("../..", import.meta.url));
// gli argomenti come elenco: un percorso o un nome di progetto con uno spazio non cambiano
// il comando
const COMPOSE_E2E = [
  "compose",
  "-p",
  process.env.E2E_PROJECT ?? "spena-e2e",
  "-f",
  "docker-compose.yml",
  "-f",
  "docker-compose.e2e.yml",
];

function pulisciDosi(...args: string[]): string {
  return execFileSync(
    "docker",
    [...COMPOSE_E2E, "exec", "-T", "backend", "python", "-m", "app.cli.clean_doses", ...args],
    { cwd: RADICE, encoding: "utf8" }
  );
}

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

function riga(page: Page, nome: string) {
  return page.getByRole("listitem").filter({ hasText: nome });
}

// stringhe e non funzioni: questo file lo compila tsconfig.node.json, senza la libreria DOM
async function nonScorreDiLato(page: Page, schermata: string) {
  await page.waitForLoadState("networkidle");
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
  expect(scrollWidth, `${schermata} scorre di lato`).toBeLessThanOrEqual(clientWidth);
}

test("le dosi dell'import si puliscono: la prova non salva, la scrittura sì, la nota sotto il nome e la dose che si riscala", async ({
  page,
}) => {
  await entra(page);
  const parmigiano = await ingrediente(page, "parmigiano");
  const farro = await ingrediente(page, "farro");
  const sale = await ingrediente(page, "sale");
  const burro = await ingrediente(page, "burro");
  const creata = await page.request.post("/api/v1/recipes", {
    data: {
      title: `Dosi dell'import e2e ${Date.now()}`,
      instructions: "Cuoci il farro, poi condisci.",
      servings: 2,
      source: "manual",
      ingredients: [
        { ingredient_id: parmigiano, role: "primary", quantity_text: "36 mesi\n\t\t\t50\n\t\t\tg" },
        { ingredient_id: farro, role: "primary", quantity_text: "(da sciacquare)\n\t\t\t160\n\t\t\tg" },
        { ingredient_id: sale, role: "secondary", quantity_text: "fino\n\n\t\t\tq.b." },
        { ingredient_id: burro, role: "primary", quantity_text: "10\n\t\t\tg + q.b." },
      ],
    },
  });
  expect(creata.ok()).toBe(true);
  const id = ((await creata.json()) as { id: string }).id;
  try {
    // la prova fa tutto il lavoro, lo racconta, e non salva niente
    const prova = pulisciDosi("--dry-run");
    expect(prova).toContain("«36 mesi⏎50⏎g» → «50 g», nota «36 mesi»");
    expect(prova).toContain("Era una prova, niente salvato");
    await page.goto(`/ricette/${id}`);
    await expect(riga(page, "parmigiano")).toContainText("50");
    await expect(page.getByText("36 mesi", { exact: true })).toHaveCount(0);

    // la scrittura vera: «mesi» non è più usata da nessuna riga, e se ne va
    const scritta = pulisciDosi();
    expect(scritta).toContain("Salvato.");
    expect(scritta).toMatch(/Unità tolte, nessuna riga le usa più: [^\n]*\bmesi\b/);

    await page.reload();
    await expect(riga(page, "parmigiano").getByText("36 mesi", { exact: true })).toBeVisible();
    await expect(riga(page, "parmigiano")).toContainText("50 g");
    await expect(riga(page, "farro").getByText("da sciacquare", { exact: true })).toBeVisible();
    await expect(riga(page, "farro")).toContainText("160 g");
    await expect(riga(page, "sale").getByText("fino", { exact: true })).toBeVisible();
    await expect(riga(page, "burro")).toContainText("10 g + q.b.");
    await nonScorreDiLato(page, "il dettaglio con le note");

    // da 2 a 3 porzioni: la dose pulita si riscala, «+ q.b.» resta accanto, «q.b.» com'è
    await page.getByRole("button", { name: "Una porzione in più" }).click();
    await expect(riga(page, "parmigiano")).toContainText("75 g");
    await expect(riga(page, "farro")).toContainText("240 g");
    await expect(riga(page, "burro")).toContainText("15 g + q.b.");
    await expect(riga(page, "sale")).toContainText("q.b.");

    // rilanciato, il comando non trova più niente da pulire
    expect(pulisciDosi("--dry-run")).toContain("Ripulite: 0.");
  } finally {
    const tolta = await page.request.patch(`/api/v1/recipes/${id}`, { data: { archived: true } });
    expect.soft(tolta.ok(), `pulizia: la ricetta ${id} non si è eliminata`).toBe(true);
  }
});
