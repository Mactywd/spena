import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

/**
 * La revisione della coda dell'import («Ingredienti da abbinare», `/ricette/importa`),
 * nel browser vero e **senza stub di rete**: il browser chiama le rotte vere, e le
 * decisioni che rivede le ha scritte il codice vero.
 *
 * Il seme dello stack non porta termini dell'import, e nessuna rotta ne crea: nascono
 * scaricando GialloZafferano, che qui non si tocca. Li semina
 * `backend/tests/e2e_import_review.py` dentro il container del backend, passando da
 * `decide_terms` — la funzione del bottone «Riprova con l'AI» — con il modello finto
 * della suite al posto di OpenRouter: alias, `decided_by = "ai"` e ingrediente creato
 * sono quelli che scrive la produzione. Per questo il file ha bisogno di
 * `docker compose exec` sullo stack e2e, oltre che del browser: se il progetto Compose
 * non si chiama `spena-e2e`, il nome si passa in `E2E_PROJECT`. L'aiutante che gira è
 * quello montato nel container, cioè quello della copia da cui lo stack è partito.
 *
 * Il termine lungo nasce collegato a un ingrediente che l'aiutante crea e poi toglie (non
 * a uno del seme: la pulizia non deve contare su un ingrediente che sopravvive per caso)
 * e porta un nome da 88 caratteri: è il caso
 * di un nome in `truncate` dentro una riga `justify-between`, a 375px. Quello corto
 * nasce come ingrediente nuovo, e si annulla qui: l'esito deve dire che l'ingrediente
 * creato è stato eliminato. In fondo la pulizia rimette tutto com'era, anche a prova
 * interrotta, passando dall'annulla vero.
 *
 * Rispetto a `docs/prossimi-passi.md` (Parte IX, b), due parole sono cambiate nel
 * codice dopo che la voce era stata scritta: la sezione non si chiama più «Deciso
 * dall'AI» ma «Decisioni recenti» (R11 ci ha messo anche le decisioni a mano, e chi ha
 * deciso lo dice un'etichetta per riga), e il riquadro di conferma dell'annullamento non
 * c'è più (S9: le cotture delle ricette rifatte non si perdono, quindi non c'è niente da
 * confermare). Si prova quel che c'è: l'etichetta «AI» della riga e la frase con l'esito
 * dell'annullamento.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

const ROOT = fileURLToPath(new URL("../..", import.meta.url));
// Gli argomenti come elenco, non come una frase da spezzare sugli spazi: un percorso o un
// nome di progetto con uno spazio dentro non cambia il comando
const COMPOSE = [
  "compose",
  "-p",
  process.env.E2E_PROJECT ?? "spena-e2e",
  "-f",
  "docker-compose.yml",
  "-f",
  "docker-compose.e2e.yml",
];

/** Lancia l'aiutante di semina nel container del backend e torna la sua ultima riga. */
function aiutante(...args: string[]): string {
  const uscita = execFileSync(
    "docker",
    [...COMPOSE, "exec", "-T", "backend", "python", "tests/e2e_import_review.py", ...args],
    { cwd: ROOT, encoding: "utf8" }
  );
  return uscita.trim().split("\n").pop() ?? "";
}

type Seminati = {
  long: { id: string; name: string; target: string };
  created: { id: string; name: string };
};

test.use({ viewport: { width: 375, height: 812 } });

test("le decisioni dell'AI si rivedono a 375px, e annullarne una dice cosa ha disfatto", async ({
  page,
}) => {
  // due `docker compose exec` che avviano Python e aprono una sessione sul database, oltre
  // al browser: i 30 secondi di default non bastano su una macchina carica
  test.setTimeout(120_000);
  try {
    // prima di seminare, gli avanzi di un giro interrotto se ne vanno: `clean` è
    // idempotente, e su uno stack pulito non fa niente
    aiutante("clean");
    const { long, created } = JSON.parse(aiutante("seed", String(Date.now()))) as Seminati;

    await page.goto("/");
    await page.getByLabel("Password").fill(PASSWORD);
    await page.getByRole("button", { name: "Entra", exact: true }).click();
    await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();
    await page.goto("/ricette/importa");
    await expect(page.getByRole("heading", { name: "Ingredienti da abbinare" })).toBeVisible();

    // la sezione delle decisioni già prese, e la riga del termine lungo: la si trova dal
    // suo tasto, che porta il nome del termine nel nome accessibile
    const sezione = page
      .locator("section")
      .filter({ has: page.getByRole("heading", { name: "Decisioni recenti" }) });
    // il `has` di un filtro si cerca dentro la riga: parte da `page`, non da `sezione`
    const annullaLungo = page.getByRole("button", {
      name: `Annulla la decisione su «${long.name}»`,
    });
    const rigaLunga = sezione.getByRole("listitem").filter({ has: annullaLungo });
    await expect(rigaLunga).toBeVisible();

    // chi ha deciso: la parola corta a video, la frase intera per chi ascolta
    await expect(rigaLunga.getByTestId("decided-by")).toHaveText("AI");
    await expect(rigaLunga.getByText("deciso dall'AI", { exact: true })).toBeAttached();
    await expect(rigaLunga.getByText(`collegato a ${long.target}`, { exact: true })).toBeVisible();

    // A 375px la pagina non scorre di lato: `scrollWidth` lo calcola il browser dal CSS
    // che Tailwind ha costruito, jsdom non lo vede.
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: test.info().outputPath("revisione-375.png"), fullPage: true });
    const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
    const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
    expect(scrollWidth, "la revisione scorre di lato").toBeLessThanOrEqual(clientWidth);

    // Il nome è davvero troncato — il testo è più largo della sua scatola — e non ha
    // invece spinto la riga oltre lo schermo o mandato a capo il tasto. `el` qui è
    // `any`: questo file lo compila tsconfig.node.json, senza la libreria DOM, ma dentro
    // `evaluate` si leggono solo proprietà dell'elemento, nessun globale del browser.
    const nome = rigaLunga.getByText(long.name, { exact: true });
    const misura = await nome.evaluate((el) => ({
      scrollWidth: el.scrollWidth as number,
      clientWidth: el.clientWidth as number,
    }));
    expect(misura.scrollWidth, "il nome lungo non è troncato").toBeGreaterThan(
      misura.clientWidth
    );

    // il tasto e l'etichetta restano interi dentro lo schermo, e a destra del nome
    await expect(annullaLungo).toBeInViewport({ ratio: 1 });
    await expect(rigaLunga.getByTestId("decided-by")).toBeInViewport({ ratio: 1 });
    const boxNome = (await nome.boundingBox())!;
    const boxTasto = (await annullaLungo.boundingBox())!;
    expect(boxNome.x + boxNome.width).toBeLessThanOrEqual(boxTasto.x);
    // un bersaglio da pollice, come ogni tasto dell'app
    expect(boxTasto.height).toBeGreaterThanOrEqual(40);

    // l'ingrediente che la decisione dell'AI ha creato esiste, prima dell'annullamento:
    // senza questo, l'assenza provata in fondo passerebbe anche con una ricerca muta
    const cerca = async () =>
      (
        (await (
          await page.request.get(
            `/api/v1/ingredients/search?q=${encodeURIComponent(created.name.toLowerCase())}`
          )
        ).json()) as { name: string }[]
      ).map((voce) => voce.name);
    expect(await cerca()).toContain(created.name.toLowerCase());

    // L'annullamento: non chiede conferma (S9), e l'esito dice quel che ha disfatto —
    // è l'unico gesto distruttivo della schermata, e l'ingrediente eliminato non si
    // vedrebbe altrimenti che tornando nell'anagrafica.
    await sezione
      .getByRole("button", { name: `Annulla la decisione su «${created.name}»` })
      .click();
    await expect(
      page.getByText(
        "Nessuna ricetta è tornata in coda. L'ingrediente che questa decisione aveva " +
          "creato è stato eliminato, perché nessun'altra cosa lo usava.",
        { exact: true }
      )
    ).toBeVisible();
    await expect(
      sezione.getByRole("button", { name: `Annulla la decisione su «${created.name}»` })
    ).toHaveCount(0);
    // il termine è tornato in coda, dove si decide a mano con la scheda di sempre
    const scheda = page.getByRole("listitem").filter({
      has: page.getByText(created.name, { exact: true }),
    });
    await expect(scheda).toBeVisible();
    await expect(scheda.getByText("1 ricetta in attesa", { exact: true })).toBeVisible();

    // e l'ingrediente è sparito davvero, non solo dalla frase
    expect(await cerca()).not.toContain(created.name.toLowerCase());
  } finally {
    // Best-effort e senza asserzioni, come in `anagrafica.spec.ts`: un `finally` che
    // solleva sostituisce l'errore vero del `try` con il proprio. La pulizia annulla
    // ogni decisione ancora in piedi (alias e ingrediente creato se ne vanno con
    // l'annulla vero), cancella i termini di questo file — anche quelli di un giro
    // interrotto — e le righe di spesa finte che la semina ha scritto.
    try {
      aiutante("clean");
    } catch (guasto) {
      console.warn("pulizia: non sono riuscito a togliere i termini seminati", guasto);
    }
  }
});
