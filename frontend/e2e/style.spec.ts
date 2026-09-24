import { expect, test, type Locator } from "@playwright/test";

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
 * non popola la dispensa, e senza una voce non c'è nessun cursore da provare — ma
 * la archivia prima di finire: questo file non lascia niente dietro di sé, e
 * nessun altro file dipende dal proprio posto nell'ordine alfabetico.
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
  // La dispensa è stato condiviso fra i file e il database vive quanto lo stack,
  // quindi questo test rimette le cose com'erano: sceglie una voce che nessun
  // altro file nomina (`cooking.spec.ts` lavora su «pomodoro») e la archivia in
  // fondo, con la X. Prima non lo faceva, e reggeva solo perché Playwright ordina
  // i file alfabeticamente e `cooking` gira prima di `style`: un `--grep`, un file
  // nuovo con un nome che viene prima, o più worker, e il `.first()` di
  // `cooking.spec.ts` avrebbe trovato la voce lasciata qui.
  await page.getByLabel("Aggiungi in dispensa").fill("cipoll");
  await page.getByRole("option", { name: /^Cipolla\b/ }).click();

  // il cursore di QUESTA voce, non il primo dello schermo: la dispensa può
  // contenere anche quel che ha lasciato il resto della suite
  const riga = page.locator("li", { hasText: "cipolla" });
  const cursore = riga.getByRole("slider");
  await expect(cursore).toBeVisible();

  const box = await cursore.boundingBox();
  expect(box!.height).toBeGreaterThanOrEqual(40);

  // le tre zone stanno su un elemento dietro al cursore: se il gradiente non
  // arrivasse, resterebbe un binario invisibile e il cursore non direbbe più nulla
  const zone = riga.locator("input[type='range']").locator("xpath=preceding-sibling::div[1]");
  await expect(zone).toHaveCSS("background-image", /linear-gradient/);

  // la pulizia: la X archivia davvero la voce sul server (la lapide che resta è
  // solo l'annulla, a video). Senza questo la dispensa cresce di una riga a ogni
  // esecuzione su uno stack riusato.
  await riga.getByRole("button", { name: "Togli cipolla dalla dispensa" }).click();
  await expect(page.getByText("Tolta dalla dispensa")).toBeVisible();
});

test("la X di una pastiglia del filtro è un bersaglio da pollice, e la pastiglia si vede", async ({
  page,
}) => {
  // Stesso motivo del cursore: una pastiglia troppo piccola o senza fondo la vede
  // solo un browser. Questo filtro si usa in piedi in corsia, con il pollice, e
  // togliere un ingrediente è il gesto con cui si esce da un elenco vuoto — se la
  // X si manca, l'unica via d'uscita dal filtro è ricaricare la pagina.
  //
  // Non scrive niente: il filtro vive nello schermo, non sul server.
  await page.getByRole("link", { name: "Ricette" }).click();
  await page.getByLabel("Contiene ingredienti").fill("pomodo");
  await page.getByRole("option", { name: /^Pomodoro\b/ }).click();

  const togli = page.getByRole("button", { name: "Togli il filtro su Pomodoro" });
  const box = await togli.boundingBox();
  expect(box!.height).toBeGreaterThanOrEqual(40);
  expect(box!.width).toBeGreaterThanOrEqual(40);

  // il fondo della pastiglia è un token del tema: senza, resterebbe una scritta
  // appoggiata sulla pagina, indistinguibile da un'etichetta qualsiasi
  // la pastiglia è quella che contiene la SUA X, non «un li che dice Pomodoro»:
  // anche le schede delle ricette sono `li` e una di loro si chiama «Pasta al
  // pomodoro», quindi il filtro per testo pescava una scheda e la trovava
  // trasparente — un test verde per il motivo sbagliato sarebbe stato peggio
  const pastiglia = page.locator("li").filter({ has: togli });
  // --color-brand-tint: #e4efe8
  await expect(pastiglia).toHaveCSS("background-color", "rgb(228, 239, 232)");
});

test("i tasti delle porzioni sono bersagli da pollice, e il riporziona arriva a video", async ({
  page,
}) => {
  // jsdom non calcola il CSS: che due tasti da toccare in cucina siano davvero
  // grandi abbastanza non lo può dire nessun test in memoria (quarta lezione di
  // CLAUDE.md). E il giro completo prova anche che il server sta rispondendo
  // davvero al parametro, non che un nostro stub lo finge.
  await page.getByRole("link", { name: "Ricette", exact: true }).click();
  await page.getByRole("link", { name: /Pasta al pomodoro/ }).first().click();

  const meno = page.getByRole("button", { name: "Una porzione in meno" });
  const box = await meno.boundingBox();
  expect(box!.height).toBeGreaterThanOrEqual(40);
  expect(box!.width).toBeGreaterThanOrEqual(40);

  // «Pasta al pomodoro» nel seme è per 2 porzioni e ha dosi di tutti i tipi:
  // «180 g», «400 g», «1 spicchio», «2 cucchiai», «q.b.». Un tocco porta a 1, cioè
  // dimezza: «180 g» deve diventare «90 g», e «q.b.» deve restare «q.b.».
  const riga = page.locator("li", { hasText: "pasta" }).first();
  await expect(riga).toContainText("180 g");
  await meno.click();
  await expect(riga).toContainText("90 g");
  await expect(page.getByText("q.b.").first()).toBeVisible();
  // a 1 non si scende: il tasto si spegne invece di proporre zero porzioni
  await expect(meno).toBeDisabled();
});

test("i € del costo si distinguono accesi e spenti, e arrivano sulla scheda", async ({
  page,
}) => {
  // R9: `€€€··` si legge «tre su cinque» solo se il nero e il grigio chiaro sono
  // davvero due colori diversi a video, e quello lo dice Tailwind, non jsdom. Il
  // costo scelto qui si toglie prima di finire: il file non lascia niente dietro.
  await page.getByRole("link", { name: "Ricette", exact: true }).click();
  await page.getByRole("link", { name: /Pasta al pomodoro/ }).first().click();

  // per indirizzo e non per titolo: le altre prove e2e ne salvano una seconda con
  // lo stesso nome, e `.first()` sceglierebbe ricette diverse qui e nell'elenco
  const indirizzo = new URL(page.url()).pathname;

  const tre = page.getByRole("button", { name: "Costo 3 su 5" });
  const quattro = page.getByRole("button", { name: "Costo 4 su 5" });
  await tre.click();
  await expect(tre).toHaveAttribute("aria-pressed", "true");
  // --color-ink #16281f acceso, --color-ink-ghost #b3bcb5 spento
  await expect(tre).toHaveCSS("color", "rgb(22, 40, 31)");
  await expect(quattro).toHaveCSS("color", "rgb(179, 188, 181)");
  const box = await tre.boundingBox();
  expect(box!.height).toBeGreaterThanOrEqual(40);
  expect(box!.width).toBeGreaterThanOrEqual(40);

  // dal dettaglio «Ricette» è due link, il tasto indietro e la scheda in basso: la
  // barra delle schede li distingue
  await page.getByRole("navigation").getByRole("link", { name: "Ricette", exact: true }).click();
  const scheda = page.locator(`a[href="${indirizzo}"]`);
  const segno = scheda.getByRole("img", { name: "Costo 3 su 5" });
  await expect(segno).toBeVisible();
  await expect(segno.locator("[data-cost-step='3']")).toHaveCSS("color", "rgb(22, 40, 31)");
  await expect(segno.locator("[data-cost-step='4']")).toHaveCSS("color", "rgb(179, 188, 181)");

  await scheda.click();
  await page.getByRole("button", { name: "Costo 3 su 5" }).click();
  await expect(page.getByText("non indicato")).toBeVisible();
});

test("il gradino scelto della scala si distingue, e si legge", async ({ page }) => {
  await page.getByRole("link", { name: "Ricette", exact: true }).click();

  const tutte = page.getByRole("radio", { name: "Tutto il ricettario." });
  const uno = page.getByRole("radio", { name: "Al massimo 1 ingrediente da comprare." });
  await expect(tutte).toBeChecked();

  // il radio è `sr-only`: la pastiglia che si vede è lo `span` dentro la sua label,
  // come per la X del filtro qui sopra si parte dal controllo e si sale
  const pastigliaDi = (radio: Locator) => page.locator("label").filter({ has: radio }).locator("span");

  // --color-card: #ffffff. «+1» non è scelto: ha il fondo bianco del `secondary`
  await expect(pastigliaDi(uno)).toHaveCSS("background-color", "rgb(255, 255, 255)");

  // si tocca la pastiglia, non il radio: `sr-only` lo riduce a un quadratino di un
  // pixel sotto la sua label, e un click diretto lo intercetta la label (o, dopo lo
  // scorrimento, l'intestazione sticky). È anche il gesto vero — in corsia si tocca
  // quel che si vede — e che il radio risulti scelto prova pure che la label è legata
  await pastigliaDi(uno).click();
  await expect(uno).toBeChecked();

  // --color-brand: #14804f. Se il gradino scelto non cambiasse fondo, la scala
  // direbbe cinque volte la stessa cosa e nessun test in jsdom se ne accorgerebbe:
  // questa asserzione e quella sotto, insieme, dicono che i due gradini differiscono
  await expect(pastigliaDi(uno)).toHaveCSS("background-color", "rgb(20, 128, 79)");
  await expect(pastigliaDi(tutte)).toHaveCSS("background-color", "rgb(255, 255, 255)");

  // Il contrasto lo misura il browser: i due colori della pastiglia scelta si leggono
  // da `getComputedStyle`, il rapporto è la formula WCAG qui in chiaro. Le due letture
  // passano da `page.evaluate` con un'espressione — e non da `locator.evaluate` con
  // una funzione — per il motivo detto sull'intestazione qui sopra: questo file lo
  // compila tsconfig.node.json, che non include la libreria DOM, e `getComputedStyle`
  // scritto in una funzione non compilerebbe. Nella forma a stringa Playwright valuta
  // l'espressione e basta (non la chiama, quindi non c'è elemento da ricevere): lo
  // span si ritrova in CSS, partendo sempre dal controllo — `input[aria-label=…] + span`
  // è la stessa risalita del `filter({ has })`, scritta in un selettore.
  const ARIA = "Al massimo 1 ingrediente da comprare.";
  const coloreDella = (proprieta: string) =>
    page.evaluate<string>(
      `getComputedStyle(document.querySelector('input[aria-label="${ARIA}"] + span')).${proprieta}`
    );
  const luminanza = (colore: string) => {
    const [r, g, b] = colore.match(/\d+(\.\d+)?/g)!.slice(0, 3).map(Number);
    const canale = (v: number) => {
      const s = v / 255;
      return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
    };
    return 0.2126 * canale(r) + 0.7152 * canale(g) + 0.0722 * canale(b);
  };

  // questa app si legge in corsia alla luce del giorno: bianco su verde sta sopra 4.5:1
  const a = luminanza(await coloreDella("color"));
  const b = luminanza(await coloreDella("backgroundColor"));
  const rapporto = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  expect(rapporto).toBeGreaterThanOrEqual(4.5);
});

test("il campo data si vede, e la pastiglia della scadenza porta il suo colore", async ({
  page,
}) => {
  // La regola di base che veste i campi è una lista di esclusioni per selettore, e
  // `date` in quella lista non compare — quindi il campo *dovrebbe* essere vestito
  // come gli altri. È già successo il contrario con `input[type="text"]`: campi
  // trasparenti su fondo grigio mentre 157 test in jsdom passavano. Tailwind genera
  // il CSS alla costruzione e jsdom non lo calcola: questo è l'unico posto da cui
  // si vede.
  await page.getByRole("link", { name: "Dispensa" }).click();

  // stessa cautela del test sul cursore: una voce che nessun altro file nomina
  // («cipolla» è già di quel test, «pomodoro» di cooking.spec.ts), e archiviata in
  // fondo, perché la dispensa è stato condiviso e il database vive quanto lo stack
  await page.getByLabel("Aggiungi in dispensa").fill("carot");
  await page.getByRole("option", { name: /^Carota\b/ }).click();

  const riga = page.locator("li", { hasText: "carota" });

  // Il «+ scadenza» è scritto in piccolo di proposito, ma è un pulsante come gli
  // altri e si tocca col pollice in corsia: 12px di testo fanno un riquadro alto
  // 16px, e un bersaglio così si manca o si prende il vicino. Il padding lo porta
  // a 44px senza toccare il disegno, e questa è l'unica misura che lo verifica —
  // jsdom non calcola il CSS, quindi nessun test in memoria vede la differenza fra
  // prima e dopo. Misurato prima di aprire il campo: è l'unico momento in cui il
  // pulsante è a video.
  const aggiungiScadenza = riga.getByRole("button", { name: /scadenza/i });
  const boxTasto = await aggiungiScadenza.boundingBox();
  expect(boxTasto!.height).toBeGreaterThanOrEqual(40);

  await aggiungiScadenza.click();

  const campo = riga.getByLabel(/scadenza/i);
  await expect(campo).toBeVisible();
  // bianco sul fondo grigio, non trasparente: è il difetto che questo file esiste
  // per prendere
  await expect(campo).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await expect(campo).toHaveCSS("border-top-width", "1px");
  // sotto i 16px iOS ingrandisce la pagina da solo quando il campo prende fuoco
  await expect(campo).toHaveCSS("font-size", "16px");

  // fra tre giorni: dentro la soglia, quindi il server deve rispondere «soon» e la
  // pastiglia prendere il token nuovo. La data si calcola qui e non si scrive a
  // mano, o il test scadrebbe da solo.
  const fraTreGiorni = new Date(Date.now() + 3 * 24 * 60 * 60 * 1000)
    .toISOString()
    .slice(0, 10);
  //
  // Il `blur()` dopo il `fill()` non è cerimonia: la riga scrive all'uscita dal
  // campo, non a ogni battuta, perché un `input[type="date"]` fa scattare `change`
  // a ogni segmento toccato e legarci la scrittura salvava l'anno 0002 mentre si
  // batteva il 2027. Il `fill()` di Playwright scrive il valore in un colpo solo:
  // è esattamente il gesto che quel difetto non toccava, ed è la ragione per cui
  // questo file non l'aveva visto. Che la data arrivi al server lo prova la
  // pastiglia qui sotto, che esiste solo se `item.expires_on` è tornato valorizzato
  // dalla GET successiva — cioè prova anche che il `blur` scrive davvero.
  await campo.fill(fraTreGiorni);
  await campo.blur();

  // --color-expiry: #5b45a8. Se il token non arrivasse, la pastiglia resterebbe
  // del colore ereditato e direbbe quanto una scritta qualsiasi. Questo valore e
  // quello in index.css sono gli unici due posti dove il colore compare: se
  // l'occhio allo Step 3 lo fa cambiare, cambiano insieme.
  const pastiglia = riga.getByText(/^Scade il /);
  await expect(pastiglia).toHaveCSS("color", "rgb(91, 69, 168)");

  // La pastiglia è anche un pulsante: toccarla riapre il campo, ed è l'unica strada
  // per correggere una data battuta male (spec §6). Il disegno è la pastiglia, alta
  // 24px; il bersaglio dev'essere quello di tutti gli altri, come il «+ scadenza»
  // che stava qui un momento fa — due controlli affiancati, uno da 44px e uno da 24,
  // sarebbero mezza correzione. Anche questa misura la può fare solo un browser.
  const correggi = riga.getByRole("button", { name: /^Scade il / });
  const boxPastiglia = await correggi.boundingBox();
  expect(boxPastiglia!.height).toBeGreaterThanOrEqual(40);

  // la pulizia, come fa il test del cursore: senza, la dispensa cresce di una riga
  // a ogni esecuzione su uno stack riusato
  await riga.getByRole("button", { name: "Togli carota dalla dispensa" }).click();
  await expect(page.getByText("Tolta dalla dispensa")).toBeVisible();
});
