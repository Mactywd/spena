import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

/**
 * Le pagine scartate della coda d'import (spec docs/superpowers/specs/2026-10-09-scartate-in-coda-design.md),
 * nel browser vero e **senza stub di rete**: il browser chiama le rotte vere, e le pagine
 * le ha scartate il codice vero.
 *
 * Il seme dello stack non porta pagine dell'import, e nessuna rotta ne scarica. Le semina
 * `backend/tests/e2e_skipped_pages.py` dentro il container del backend: una pagina
 * illeggibile con `store_unparsable`, e una ricetta con la panna finita fra i prodotti per
 * la casa, scartata da `materialize_ready` col motivo che scrive la produzione. La
 * correzione passa dal servizio vero dell'anagrafica (`recategorize_ingredient`), che è
 * quel che fa chi cambia il reparto dalla scheda dell'ingrediente. Per questo il file ha
 * bisogno di `docker compose exec` sullo stack e2e, oltre che del browser: se il progetto
 * Compose non si chiama `spena-e2e`, il nome si passa in `E2E_PROJECT`. In fondo la pulizia
 * toglie tutto, anche a prova interrotta.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

const ROOT = fileURLToPath(new URL("../..", import.meta.url));
// Gli argomenti come elenco, non come una frase da spezzare sugli spazi
const COMPOSE = [
  "compose",
  "-p",
  process.env.E2E_PROJECT ?? "spena-e2e",
  "-f",
  "docker-compose.yml",
  "-f",
  "docker-compose.e2e.yml",
];

/** Lancia l'aiutante nel container del backend e torna la sua ultima riga. */
function aiutante(...args: string[]): string {
  const uscita = execFileSync(
    "docker",
    [...COMPOSE, "exec", "-T", "backend", "python", "tests/e2e_skipped_pages.py", ...args],
    { cwd: ROOT, encoding: "utf8" }
  );
  return uscita.trim().split("\n").pop() ?? "";
}

type Seminate = { title: string; nonFood: string; nonFoodId: string; unreadableUrl: string };

test.use({ viewport: { width: 375, height: 812 } });

test("le pagine scartate si leggono col perché, e una rimessa in coda dopo la correzione entra nel ricettario", async ({
  page,
}) => {
  // tre `docker compose exec` che avviano Python e aprono una sessione sul database, oltre
  // al browser: i 30 secondi di default non bastano su una macchina carica
  test.setTimeout(120_000);
  try {
    aiutante("clean");
    const seminate = JSON.parse(aiutante("seed", String(Date.now()))) as Seminate;

    await page.goto("/");
    await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
    await page.getByRole("button", { name: "Entra", exact: true }).click();
    await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();
    await page.goto("/ricette/importa");

    // chiusa di partenza, col numero
    const titolo = page.getByRole("button", { name: /^Scartate \(\d+\)$/ });
    await expect(titolo).toHaveAttribute("aria-expanded", "false");
    const prima = Number(/\((\d+)\)/.exec((await titolo.textContent()) ?? "")?.[1]);
    expect(prima).toBeGreaterThanOrEqual(2);
    await titolo.click();
    await expect(titolo).toHaveAttribute("aria-expanded", "true");

    // la pagina illeggibile: l'indirizzo, il perché, la pagina da aprire, nessuna rimessa
    const illeggibile = page.getByRole("listitem").filter({ hasText: seminate.unreadableUrl });
    await expect(illeggibile).toContainText(
      "Sul sito la pagina non aveva una ricetta leggibile: rimetterla in coda non cambierebbe niente."
    );
    await expect(illeggibile.getByRole("button", { name: /^Rimetti in coda/ })).toHaveCount(0);
    await expect(illeggibile.getByRole("link", { name: /^Apri la pagina/ })).toHaveAttribute(
      "href",
      seminate.unreadableUrl
    );

    // la ricetta col non alimentare: il perché in parole, con la strada
    const torta = page.getByRole("listitem").filter({ hasText: seminate.title });
    await expect(torta).toContainText(
      `Fra gli ingredienti c'è «${seminate.nonFood}», che non è un alimento.`
    );
    const rimetti = torta.getByRole("button", { name: `Rimetti in coda «${seminate.title}»` });

    // A 375px niente scorre di lato, e il tasto resta intero accanto al titolo troncato:
    // `scrollWidth` lo calcola il browser dal CSS che Tailwind ha costruito, jsdom no
    await page.waitForLoadState("networkidle");
    const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
    const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
    expect(scrollWidth, "la coda con le scartate scorre di lato").toBeLessThanOrEqual(clientWidth);
    await rimetti.scrollIntoViewIfNeeded();
    await expect(rimetti).toBeInViewport({ ratio: 1 });
    expect((await rimetti.boundingBox())!.height).toBeGreaterThanOrEqual(44);

    // rimessa senza correggere: torna scartata, l'avviso lo dice, la riga e il numero restano
    await rimetti.click();
    await expect(
      page.getByText(
        `«${seminate.title}» è ancora scartata: «${seminate.nonFood}» non è un alimento.`,
        { exact: true }
      )
    ).toBeVisible();
    await expect(torta).toBeVisible();
    await expect(page.getByRole("button", { name: `Scartate (${prima})`, exact: true })).toBeVisible();

    // la correzione, col servizio vero dell'anagrafica: la panna torna fra i latticini
    aiutante("fix", seminate.nonFoodId);
    await rimetti.click();
    await expect(
      page.getByText(`«${seminate.title}» è entrata nel ricettario.`, { exact: true })
    ).toBeVisible();
    await expect(torta).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: `Scartate (${prima - 1})`, exact: true })
    ).toBeVisible();

    // e «Apri» dell'avviso porta alla ricetta nata adesso
    await page.getByRole("button", { name: "Apri", exact: true }).click();
    await expect(page.getByRole("heading", { level: 1, name: seminate.title })).toBeVisible();
  } finally {
    // la pulizia, anche a prova interrotta: `expect.soft` non lancia — un `finally` che
    // lancia nasconderebbe l'errore vero — ma segna la prova fallita
    try {
      aiutante("clean");
    } catch (guasto) {
      expect.soft(false, `pulizia: non sono riuscito a togliere le pagine seminate (${guasto})`).toBe(true);
    }
  }
});
