import { expect, test } from "@playwright/test";

/**
 * Lo stile è l'unica parte dell'app che i test in jsdom non possono vedere: Tailwind
 * genera il CSS al momento della costruzione, e jsdom non lo calcola. Questi controlli
 * girano nel browser vero, sull'app costruita e servita da Nginx — cioè su quella che
 * finisce in produzione.
 *
 * Esistono perché è già successo: la prima stesura della regola di base scriveva
 * `input[type="text"]`, che non seleziona un `<input>` senza attributo `type`. Metà
 * dei campi di quest'app sono scritti così, e sono rimasti trasparenti e senza bordo
 * su uno sfondo grigio — invisibili, senza che un solo test fallisse. Il campo provato
 * qui è di proposito uno senza `type`: provarne uno tipizzato non avrebbe visto niente.
 *
 * I controlli sul colore e sui campi non scrivono niente e non leggono lo stato:
 * girano anche su uno stack già usato. Il controllo sul cursore della dispensa fa
 * eccezione — aggiunge una voce con l'ingresso diretto (spec §8.3) perché il seme
 * non popola la dispensa, e senza una voce non c'è nessun cursore da provare.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  // l'app parte presumendo una sessione valida: è il primo 401 a far comparire
  // l'accesso, quindi il campo si aspetta invece di darlo per già presente
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
});

test("i token del colore arrivano davvero alla pagina", async ({ page }) => {
  // --color-page: #eef1ee. Se il blocco @theme non venisse compilato, questo
  // resterebbe il bianco di default e tutto il resto sarebbe da rifare
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(238, 241, 238)");
});

test("un campo di testo si vede: ha fondo e bordo", async ({ page }) => {
  const field = page.getByLabel("Aggiungi alla lista");
  await expect(field).toBeVisible();

  // bianco sul fondo grigio della pagina, non trasparente
  await expect(field).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await expect(field).toHaveCSS("border-top-width", "1px");
  // sotto i 16px iOS ingrandisce la pagina da solo quando il campo prende fuoco
  await expect(field).toHaveCSS("font-size", "16px");
});

// Decisione mia (non del brief del Task 9): il Task 1 ha reso l'intestazione
// sticky con un'altezza fissa (`h-12`) e ha sottratto la stessa misura al `main`
// (`min-h-[calc(100dvh-3rem)]`). Nessun test in jsdom calcola quell'aritmetica —
// se le due misure divergessero l'app avrebbe una barra di scorrimento verticale
// che non serve, o l'intestazione coprirebbe la prima riga. Questo è l'unico task
// che apre un browser vero: è il posto giusto per un controllo che nessun altro
// può fare.
//
// Rilievo di revisione: le prime due asserzioni (banner visibile a freddo,
// nessun scorrimento *orizzontale*) non provano quell'aritmetica — se le due
// misure divergessero lo scorrimento in più sarebbe verticale, e nessuna delle
// due lo vedrebbe. Ora il test controlla anche `scrollHeight`/`clientHeight`, e
// prova lo `sticky` per davvero: ridotto il viewport e aperte le ricette del
// seme (26, più che sufficienti a far scorrere anche una pagina bassa), scorre e
// controlla che il banner sia ancora lì — prima di scorrere non c'è nessuna prova
// che sia "sempre" visibile, solo che lo sia a pagina appena caricata.
test("l'intestazione è sempre visibile, anche scorrendo, e la pagina non scorre di suo in nessuna direzione", async ({
  page,
}) => {
  await expect(page.getByRole("banner")).toBeVisible();
  // stringa e non funzione: questo file lo compila tsconfig.node.json, che non
  // include la libreria DOM (page.evaluate gira nel browser, non in node), e
  // `document` come identificatore tipato non esisterebbe in questo progetto
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
  expect(scrollWidth).toBeLessThanOrEqual(clientWidth);

  const scrollHeight = await page.evaluate<number>("document.documentElement.scrollHeight");
  const clientHeight = await page.evaluate<number>("document.documentElement.clientHeight");
  expect(scrollHeight).toBeLessThanOrEqual(clientHeight);

  // la prova dello `sticky`: senza uno scroll vero, "sempre visibile" è solo "visibile
  // a pagina appena caricata". Un viewport basso e le 26 ricette del seme bastano a
  // garantire contenuto più alto della finestra.
  await page.setViewportSize({ width: 390, height: 400 });
  await page.getByRole("link", { name: "Ricette" }).click();
  await page.mouse.wheel(0, 2000);
  await expect(page.getByRole("banner")).toBeVisible();
});

test("il cursore della dispensa è un bersaglio da pollice, e le zone si vedono", async ({
  page,
}) => {
  // jsdom non calcola il CSS: che il pallino esista, si veda e si possa toccare
  // non lo può dire nessun test in memoria (quarta lezione di CLAUDE.md)
  await page.getByRole("link", { name: "Dispensa" }).click();

  // il seme non popola la dispensa: senza una voce non c'è nessun cursore da
  // provare. L'ingresso diretto (spec §8.3) evita di passare dalla lista.
  //
  // Dipendenza dall'ordine non scritta altrove: questa voce resta in dispensa ad
  // ogni esecuzione (non viene mai archiviata), e `cooking.spec.ts` cerca un `li`
  // con testo «pomodoro» prendendo il primo. Non si rompe solo perché Playwright
  // ordina i file alfabeticamente e `cooking` gira prima di `style` — non risolto
  // qui, la pulizia resta per la revisione finale.
  await page.getByLabel("Aggiungi in dispensa").fill("pomodo");
  await page.getByRole("option", { name: /Pomodoro/ }).click();

  const cursore = page.getByRole("slider").first();
  await expect(cursore).toBeVisible();

  const box = await cursore.boundingBox();
  expect(box!.height).toBeGreaterThanOrEqual(40);

  // le tre zone stanno su un elemento dietro al cursore: se il gradiente non
  // arrivasse, resterebbe un binario invisibile e il cursore non direbbe più nulla
  const zone = page.locator("input[type='range']").first().locator("xpath=preceding-sibling::div[1]");
  await expect(zone).toHaveCSS("background-image", /linear-gradient/);
});
