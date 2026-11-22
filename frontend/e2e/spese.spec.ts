import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

/**
 * H1, «Spese dell'AI», nel browser vero, a 375×812.
 *
 * Lo stack e2e non ha spese: la chiave API è vuota, e nessuna chiamata costa
 * (al più qualche prova lascia una riga fallita, col costo NULL). Le righe col costo le
 * scrive `backend/tests/e2e_spese.py` nel container del backend — nessuna rete — e le
 * toglie nel `finally`. Le cifre attese sono le sue: negli ultimi 30 giorni 0,025 $. Le
 * chiamate fallite di altre prove cambiano il numero delle chiamate e delle senza costo,
 * non le cifre: per questo qui non si contano.
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

function aiutanteSpese(comando: "seed" | "clean"): string {
  const uscita = execFileSync(
    "docker",
    [...COMPOSE_E2E, "exec", "-T", "backend", "python", "tests/e2e_spese.py", comando],
    { cwd: RADICE, encoding: "utf8" }
  );
  return uscita.trim().split("\n").pop() ?? "";
}

test.use({ viewport: { width: 375, height: 812 } });

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();
});

test("dal ☰ si arriva a «Spese dell'AI», che parte da «Questo mese»", async ({ page }) => {
  await page.getByRole("button", { name: "Apri il menu" }).click();
  await page.getByRole("dialog", { name: "Menu" }).getByRole("link", { name: "Spese dell'AI" }).click();

  await expect(page).toHaveURL(/\/spese-ai$/);
  await expect(page.getByRole("heading", { name: "Spese dell'AI" })).toBeVisible();
  const periodo = page.getByRole("group", { name: "Periodo" });
  await expect(periodo.getByRole("button", { name: "Questo mese" })).toHaveAttribute("aria-pressed", "true");
  await expect(periodo.getByRole("button", { name: "Ultimi 30 giorni" })).toHaveAttribute("aria-pressed", "false");
  // vuoto o no, a seconda di cosa hanno lasciato le altre prove: una delle due cose c'è
  await expect(page.getByText(/^(Nessuna chiamata all'AI questo mese\.|Totale, .+)$/)).toBeVisible();
});

test("le spese seminate: il totale, le sezioni (una sconosciuta col suo nome), il giorno più caro, e niente scorre di lato", async ({
  page,
}) => {
  aiutanteSpese("clean");
  aiutanteSpese("seed");
  try {
    await page.goto("/spese-ai");
    const periodo = page.getByRole("group", { name: "Periodo" });
    for (const pulsante of await periodo.getByRole("button").all()) {
      expect((await pulsante.boundingBox())!.height, "un pulsante del periodo").toBeGreaterThanOrEqual(44);
    }

    await periodo.getByRole("button", { name: "Ultimi 30 giorni" }).click();
    await expect(periodo.getByRole("button", { name: "Ultimi 30 giorni" })).toHaveAttribute("aria-pressed", "true");
    await expect(page.getByText(/^0,025\s\$$/)).toBeVisible();
    await expect(page.getByText(/senza un costo/)).toBeVisible();

    const sezioni = page.getByRole("list", { name: "Spesa per sezione" });
    for (const [nome, cifre] of [
      ["Ricette scritte con l'AI", /0,02\s\$ · 80%/],
      ["Abbinare gli ingredienti dell'import", /0,004\s\$ · 16%/],
      ["e2e_sconosciuta", /0,001\s\$ · 4%/],
    ] as const) {
      await expect(sezioni.getByRole("listitem").filter({ hasText: nome }), nome).toContainText(cifre);
    }

    const grafico = page.getByRole("img", { name: /^Costo per giorno/ });
    await expect(grafico.locator("rect[data-day]")).toHaveCount(2);
    await expect(page.getByText(/^Il giorno più caro: .+, 0,021\s\$$/)).toBeVisible();

    await page.waitForLoadState("networkidle");
    const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
    const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
    expect(scrollWidth, "le spese scorrono di lato").toBeLessThanOrEqual(clientWidth);

    // «Da sempre» comprende le stesse righe, e nessun'altra col costo
    await periodo.getByRole("button", { name: "Da sempre" }).click();
    await expect(page.getByText(/^0,025\s\$$/)).toBeVisible();
  } finally {
    // `expect.soft` e non un'asserzione: un `finally` che lancia nasconderebbe l'errore vero
    try {
      aiutanteSpese("clean");
    } catch (guasto) {
      expect.soft(false, `pulizia: non sono riuscito a togliere le spese seminate (${guasto})`).toBe(true);
    }
  }
});
