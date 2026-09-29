import { expect, test, type Page } from "@playwright/test";

/**
 * Il caso che ha fatto nascere S9, per intero e nel browser vero: un parmigiano
 * registrato sotto «burro» si sposta dalla dispensa in due tocchi e una scelta.
 *
 * Il prodotto e l'elemento di dispensa si creano con `page.request`, che condivide i
 * cookie della pagina: il seme non ha prodotti, e costruirli dalla sistemazione della
 * spesa allungherebbe la prova senza provare niente di S9. Il nome porta l'ora, perché
 * il catalogo vive quanto lo stack; in fondo la voce si toglie e il prodotto si
 * elimina, così il file non lascia niente dietro di sé. Nessun altro file di `e2e/`
 * nomina il burro o il parmigiano.
 *
 * `scrollWidth` lo calcola il browser dal CSS che Tailwind ha costruito: jsdom non lo
 * vede, quindi il controllo dei 375 px sta qui (come in `style.spec.ts`).
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

test("il parmigiano sotto «burro» si sposta dalla dispensa, e a 375px niente scorre di lato", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();

  // lo stato di partenza: un prodotto sotto l'ingrediente sbagliato, in dispensa
  const burro = await ingrediente(page, "burro");
  const nome = `Parmigiano Reggiano e2e ${Date.now()}`;
  const creato = await page.request.post("/api/v1/products", {
    data: { ingredient_id: burro.id, name: nome },
  });
  expect(creato.ok()).toBe(true);
  const { id: prodottoId } = (await creato.json()) as { id: string };
  // fuori dal `try`: la pulizia in `finally` la legge anche se la creazione della
  // voce di dispensa qui sotto non arrivasse mai a scriverla
  let voceId: string | undefined;

  // rilievo di revisione: la pulizia in fondo girava solo se ogni asserzione fra la
  // creazione e qui sotto passava. Un'asserzione fallita a metà lasciava il prodotto
  // e la voce di dispensa (col nome timestampato) nel database condiviso dello
  // stack e2e, a inquinare le prove che girano dopo. Da qui in poi sta tutto in un
  // `try`/`finally`: la pulizia gira comunque, anche a test interrotto a metà.
  try {
    const inDispensa = await page.request.post("/api/v1/pantry", {
      data: { ingredient_id: burro.id, product_id: prodottoId },
    });
    expect(inDispensa.ok()).toBe(true);
    voceId = (await inDispensa.json()).id as string;

    // tocco 1: il nome nella riga della dispensa, un bersaglio da pollice — il link
    // porta ora il nome dell'ingrediente («burro», prima dello spostamento) e non
    // più quello del prodotto (dal giro): si risale dal testo del prodotto, che in
    // dispensa resta unico, all'`li` che lo contiene e al link dentro
    await page.getByRole("link", { name: "Dispensa", exact: true }).click();
    const rigaProdotto = page.locator("li", { hasText: nome });
    const link = rigaProdotto.getByRole("link");
    await expect(link).toBeVisible();
    const box = await link.boundingBox();
    expect(box!.height).toBeGreaterThanOrEqual(44);
    await link.click();
    await expect(page).toHaveURL(
      new RegExp(`/anagrafica/prodotto/${prodottoId}\\?da=dispensa$`)
    );
    await expect(page.getByRole("link", { name: "Burro", exact: true })).toBeVisible();

    // tocco 2 e la scelta
    await page.getByRole("button", { name: "Spostalo" }).click();
    await page.getByLabel("Sposta sotto").fill("parmig");
    await page.getByRole("option", { name: /^Parmigiano\b/ }).click();
    await expect(
      page.getByText("Spostato sotto «Parmigiano», con 1 elemento di dispensa.")
    ).toBeVisible();
    await expect(page.getByRole("link", { name: "Parmigiano", exact: true })).toBeVisible();

    // la riga della dispensa mostra ora il nome dell'ingrediente e non più quello
    // del prodotto (dal giro): che stia sotto «parmigiano» lo dice il link stesso,
    // e la risposta che la dispensa legge lo conferma
    await page.getByRole("main").getByRole("link", { name: "Dispensa" }).click();
    const rigaSpostata = page.locator("li", { hasText: nome });
    await expect(rigaSpostata.getByRole("link", { name: "parmigiano" })).toBeVisible();
    const dispensa = (await (await page.request.get("/api/v1/pantry")).json()) as {
      id: string;
      ingredient_name: string;
    }[];
    expect(dispensa.find((voce) => voce.id === voceId)?.ingredient_name).toBe("parmigiano");

    // a 375px: le tre pagine nuove e il pannello dell'hamburger
    await page.setViewportSize({ width: 375, height: 812 });
    const parmigiano = await ingrediente(page, "parmigiano");

    await page.goto(`/anagrafica/prodotto/${prodottoId}?da=dispensa`);
    await expect(page.getByRole("heading", { name: nome })).toBeVisible();
    await page.screenshot({ path: test.info().outputPath("prodotto-375.png"), fullPage: true });
    await nonScorreDiLato(page, "la scheda del prodotto");

    await page.goto(`/anagrafica/ingrediente/${parmigiano.id}`);
    await expect(page.getByRole("heading", { name: "Parmigiano" })).toBeVisible();
    // il prodotto dal nome lungo sta nell'elenco della scheda: è il caso che allarga
    await expect(page.getByRole("link", { name: new RegExp(nome) })).toBeVisible();
    await page.screenshot({
      path: test.info().outputPath("ingrediente-375.png"),
      fullPage: true,
    });
    await nonScorreDiLato(page, "la scheda dell'ingrediente");

    await page.goto("/anagrafica");
    await page.getByLabel("Cerca un ingrediente o un prodotto", { exact: true }).fill("parmigiano");
    await expect(page.getByRole("heading", { name: "Prodotti" })).toBeVisible();
    await expect(page.getByRole("link", { name: new RegExp(nome) })).toBeVisible();
    await page.screenshot({ path: test.info().outputPath("anagrafica-375.png"), fullPage: true });
    await nonScorreDiLato(page, "l'anagrafica");

    await page.getByRole("button", { name: "Apri il menu" }).click();
    await expect(page.getByRole("dialog", { name: "Menu" })).toBeVisible();
    await page.screenshot({ path: test.info().outputPath("menu-375.png") });
    await nonScorreDiLato(page, "il pannello dell'hamburger");
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog", { name: "Menu" })).toHaveCount(0);

    // la pulizia del percorso felice: la voce esce dalla dispensa dal gesto vero
    // (il tocco sulla X), il prodotto dal catalogo. Resta qui, dentro il `try`: è
    // anche l'unica prova di questo file sul tasto che archivia una voce dalla sua
    // riga. Il `finally` qui sotto è la rete di sicurezza per quando non ci si arriva.
    await page.goto("/dispensa");
    await page.getByRole("button", { name: `Togli ${nome} dalla dispensa` }).click();
    await expect(page.getByText(`Tolto dalla dispensa: ${nome}`)).toBeVisible();
    expect((await page.request.delete(`/api/v1/products/${prodottoId}`)).ok()).toBe(true);
  } finally {
    // la rete di sicurezza: gira sempre, che il `try` sia arrivato in fondo o si sia
    // interrotto a metà con un'asserzione fallita. Best-effort e senza asserzioni:
    // un `finally` che solleva sostituisce l'errore vero del `try` con il proprio, e
    // qui l'errore vero è quello che conta. Ogni richiesta nel proprio try/catch, con
    // un avviso in console e basta — non un'asserzione — se fallisce.
    //
    // Archiviare è idempotente (spec: l'annulla della X rossa riporta indietro
    // `archived_at`, e archiviare due volte lo stesso `id` non fallisce mai — vedi
    // `archive_item` nel backend): richiamarla su una voce già tolta la lascia
    // semplicemente archiviata. Resta comunque nel proprio try/catch: un guasto di
    // rete o del server non deve nascondere l'asserzione fallita nel `try`.
    if (voceId) {
      try {
        await page.request.patch(`/api/v1/pantry/${voceId}`, { data: { archived: true } });
      } catch (guasto) {
        console.warn(`pulizia: non sono riuscito ad archiviare la voce ${voceId}`, guasto);
      }
    }
    // il prodotto può essere già sparito (il `try` l'ha eliminato per primo): un 404
    // qui è l'esito atteso quanto un 200, non un guasto della pulizia — ma non è
    // un'asserzione: anche un esito imprevisto resta un avviso, non un secondo errore
    try {
      await page.request.delete(`/api/v1/products/${prodottoId}`);
    } catch (guasto) {
      console.warn(`pulizia: non sono riuscito a eliminare il prodotto ${prodottoId}`, guasto);
    }
  }
});
