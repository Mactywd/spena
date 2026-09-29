import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { expect, test, type Locator, type Page } from "@playwright/test";
import type { Ingredient, RecipeDraft } from "../src/domain/types.ts";
import { buttonClasses } from "../src/components/ui/buttonClasses.ts";

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
 * girano anche su uno stack già usato. Fanno eccezione i controlli che toccano la
 * dispensa — aggiungono una voce con l'ingresso diretto (spec §8.3) perché il seme
 * non la popola, e senza una voce non c'è niente da provare, né una tacca né un
 * riepilogo — e i giri dei due temi, che creano un prodotto e una sua confezione
 * (`perOgniLuogo`); tutti tolgono quel che hanno messo prima di finire: questo file
 * non lascia niente dietro di sé, e nessun altro file dipende dal proprio posto
 * nell'ordine alfabetico.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  // l'app parte presumendo una sessione valida: è il primo 401 a far comparire
  // l'accesso, quindi il campo si aspetta invece di darlo per già presente
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
});

test("i token del colore arrivano davvero alla pagina", async ({ page }) => {
  // se il blocco @theme non venisse compilato, il fondo resterebbe il bianco di
  // default e tutto il resto sarebbe da rifare
  await expect(page.locator("body")).toHaveCSS("background-color", tokenDelTema("page"));
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

test("le tacche della dispensa sono bersagli da pollice", async ({ page }) => {
  // jsdom non calcola il CSS: che le tacche esistano, si vedano e si possano
  // toccare non lo può dire nessun test in memoria (quarta lezione di CLAUDE.md).
  // A 375px, la larghezza del telefono: al viewport di default (1280) la colonna del
  // testo era larga abbastanza da non mostrare mai che a 375 ne restavano 135px.
  await page.setViewportSize({ width: 375, height: 812 });
  await page.getByRole("link", { name: "Dispensa" }).click();

  // il seme non popola la dispensa: senza una voce non c'è niente da provare.
  // L'aggiunta passa dalla barra in cima (spec T3 §2): si scrive nel campo, si
  // tocca il +, e si sceglie nel selettore che si apre già riempito di quel testo.
  //
  // La dispensa è stato condiviso fra i file e il database vive quanto lo stack,
  // quindi questo test rimette le cose com'erano: sceglie una voce che nessun
  // altro file nomina (`cooking.spec.ts` lavora su «pomodoro») e la archivia in
  // fondo, con la X. Prima non lo faceva, e reggeva solo perché Playwright ordina
  // i file alfabeticamente e `cooking` gira prima di `style`: un `--grep`, un file
  // nuovo con un nome che viene prima, o più worker, e il `.first()` di
  // `cooking.spec.ts` avrebbe trovato la voce lasciata qui.
  await page.getByLabel("Cerca o aggiungi in dispensa").fill("cipoll");
  await page.getByRole("button", { name: "Aggiungi in dispensa" }).click();
  await page.getByRole("option", { name: /^Cipolla\b/ }).click();

  // la riga di QUESTA voce, non la prima dello schermo: la dispensa può contenere
  // anche quel che ha lasciato il resto della suite
  const riga = page.locator("li", { hasText: "cipolla" });

  // le tre tacche: ognuna è un bersaglio da 44px (spec T3 §4.4), non solo quella
  // scelta — un tocco un po' storto su una tacca spenta deve prendere comunque lei
  const tacche = riga.getByRole("radio");
  await expect(tacche).toHaveCount(3);
  for (const tacca of await tacche.all()) {
    const box = await tacca.boundingBox();
    expect(box!.width).toBeGreaterThanOrEqual(44);
    expect(box!.height).toBeGreaterThanOrEqual(44);
  }

  // la ✕ che archivia la voce
  const togli = riga.getByRole("button", { name: "Togli cipolla dalla dispensa" });
  const boxTogli = await togli.boundingBox();
  expect(boxTogli!.width).toBeGreaterThanOrEqual(44);
  expect(boxTogli!.height).toBeGreaterThanOrEqual(44);

  // la scadenza: nessuna data ancora, quindi il pulsante dice «+ scadenza per
  // cipolla» — il testo è piccolo di proposito, ma il bersaglio dev'essere quello
  // di tutti gli altri
  const scadenza = riga.getByRole("button", { name: "+ scadenza per cipolla" });
  const boxScadenza = await scadenza.boundingBox();
  expect(boxScadenza!.height).toBeGreaterThanOrEqual(44);

  // il nome e la scadenza non si sovrappongono: due bersagli vicini che si
  // toccassero sarebbero mezzo bersaglio ciascuno
  const nome = riga.getByRole("link", { name: "cipolla" });
  const boxNome = await nome.boundingBox();
  expect(boxNome!.y + boxNome!.height, "il nome e la scadenza si sovrappongono").toBeLessThanOrEqual(
    boxScadenza!.y
  );

  // la scadenza sta sulla riga sua, subito sotto il prodotto: non accanto, dove un
  // nome di prodotto vero la spingeva a capo e lasciava il «·» da solo, e non
  // centrata nel bersaglio da 44px del pulsante — un <button> nativo centra il
  // contenuto in verticale, quindi il TOP del suo box parte più in alto del testo.
  // Qui si misura il TOP del TESTO con un Range, non del box: la distanza fra le due
  // cime è una riga di testo piccolo (16px) più il respiro (2px), non di più. «sfuso»
  // perché l'ingresso diretto non lega un prodotto.
  const prodotto = riga.getByText("sfuso", { exact: true });
  const cimaProdotto = await cimaDelTesto(prodotto);
  const cimaScadenza = await cimaDelTesto(scadenza);
  expect(cimaScadenza - cimaProdotto, "la scadenza non sta sulla riga sotto il prodotto").toBeGreaterThanOrEqual(14);
  expect(cimaScadenza - cimaProdotto, "la scadenza è staccata dal prodotto").toBeLessThanOrEqual(22);
  await expect(riga).not.toContainText("·");

  // un nome di prodotto vero e lungo resta su una riga, tagliato coi puntini, e la
  // riga non cresce. Il seme non mette prodotti in dispensa, quindi il testo si
  // sostituisce nella pagina: quel che si misura è il CSS della riga, non i dati. Il
  // nome è uno della dispensa vera che a 375px andava su tre righe.
  const altezzaRiga = (await riga.boundingBox())!.height;
  const nodoProdotto = (await prodotto.elementHandle())!;
  const altezzaUnaRiga = (await nodoProdotto.boundingBox())!.height;
  await nodoProdotto.evaluate((el) => {
    el.textContent = "Deodorante per Ambienti Vaniglia e Gelsomino";
  });
  expect((await nodoProdotto.boundingBox())!.height, "il nome lungo va a capo").toBe(altezzaUnaRiga);
  expect(
    await nodoProdotto.evaluate((el) => el.scrollWidth > el.clientWidth),
    "il nome lungo non è tagliato: la prova non ha misurato niente"
  ).toBe(true);
  expect((await riga.boundingBox())!.height, "la riga è cresciuta col nome lungo").toBe(altezzaRiga);
  await nodoProdotto.evaluate((el) => {
    el.textContent = "sfuso";
  });

  // la tacca accesa (l'ingresso diretto entra sempre «Disponibile») è un segno, non
  // un testo: la soglia WCAG 1.4.11 è 3:1 e non 4,5:1, misurata sul fondo `card`
  // della riga, in chiaro e in scuro — i colori sono quelli calcolati a video, gli
  // stessi helper (`tokenDelTema`/`tokenDelTemaScuro`) del resto del file
  const barretta = riga.locator('[role="radio"][aria-checked="true"] span');
  await page.emulateMedia({ colorScheme: "light" });
  const chiaro = await contrastoSegno(barretta);
  expect(chiaro.fondo).toBe(tokenDelTema("card"));
  expect(chiaro.rapporto, "tacca accesa su --color-card, chiaro").toBeGreaterThanOrEqual(3);

  await page.emulateMedia({ colorScheme: "dark" });
  const scuro = await contrastoSegno(barretta);
  expect(scuro.fondo).toBe(tokenDelTemaScuro("card"));
  expect(scuro.rapporto, "tacca accesa su --color-card, scuro").toBeGreaterThanOrEqual(3);
  await page.emulateMedia({ colorScheme: "light" });

  // la tacca spenta, che è quella che deve dire «si tocca anche qui» (spec §7): con
  // «Disponibile» sono accese tutte e tre, quindi si scende a «Finito» e si misura
  // quella di «Disponibile». Si aspetta che la scrittura sia finita — mentre è in
  // volo le tacche sono attenuate, e il numero sarebbe di un altro stato
  const finito = riga.getByRole("radio", { name: "Finito", exact: true });
  await finito.click();
  await expect(finito).toHaveAttribute("aria-checked", "true");
  await expect(finito).not.toHaveAttribute("aria-disabled", "true");
  const spenta = riga.locator('[role="radio"][aria-label="Disponibile"] span');
  await expect(spenta.locator("..")).toHaveAttribute("data-lit", "false");

  const spentaChiaro = await contrastoSegno(spenta);
  expect(spentaChiaro.colore).toBe(tokenDelTema("notch-off"));
  expect(spentaChiaro.fondo).toBe(tokenDelTema("card"));
  test.info().annotations.push({
    type: "contrasto",
    description: `tacca spenta su card, chiaro: ${spentaChiaro.rapporto.toFixed(2)}:1`,
  });
  expect(spentaChiaro.rapporto, "tacca spenta su --color-card, chiaro").toBeGreaterThanOrEqual(3);

  await page.emulateMedia({ colorScheme: "dark" });
  const spentaScuro = await contrastoSegno(spenta);
  expect(spentaScuro.colore).toBe(tokenDelTemaScuro("notch-off"));
  expect(spentaScuro.fondo).toBe(tokenDelTemaScuro("card"));
  test.info().annotations.push({
    type: "contrasto",
    description: `tacca spenta su card, scuro: ${spentaScuro.rapporto.toFixed(2)}:1`,
  });
  expect(spentaScuro.rapporto, "tacca spenta su --color-card, scuro").toBeGreaterThanOrEqual(3);
  await page.emulateMedia({ colorScheme: "light" });

  // la pulizia: la X archivia davvero la voce sul server. Senza questo la dispensa
  // cresce di una riga a ogni esecuzione su uno stack riusato.
  await togli.click();
  await expect(page.getByText("Tolto dalla dispensa: cipolla")).toBeVisible();
});

test("il riepilogo delle scadenze conta chi sta per scadere, ed è un bersaglio da pollice", async ({
  page,
}) => {
  // il `beforeEach` tocca «Entra» ma non aspetta la risposta: senza un'attesa qui,
  // la prima `page.request` qui sotto può partire prima che il cookie di sessione
  // sia scritto, e tornare 401. Le altre prove di questo file non se ne accorgono
  // perché cominciano con un tocco sulla UI (aspetta da sé finché il login non è
  // fatto); qui la prima cosa è una `page.request`, quindi l'attesa va messa a mano.
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();

  // il seme non popola la dispensa: senza una voce con `expires_on` vicino non c'è
  // nessun riepilogo da provare. Si crea con `page.request`, che condivide i
  // cookie della pagina — la POST di dispensa non prende la scadenza (schema
  // `PantryItemCreate`), che si scrive con una PATCH separata, come fa il campo
  // della riga.
  //
  // «zucchina» è un ingrediente che nessun altro file della suite nomina, e si
  // archivia nella pulizia con la X, come le altre voci di questo file: questo
  // file non lascia niente dietro di sé.
  const trovati = (await (
    await page.request.get("/api/v1/ingredients/search?q=zucchina")
  ).json()) as { id: string; name: string }[];
  const zucchina = trovati.find((voce) => voce.name === "zucchina");
  expect(zucchina, "«zucchina» non è nel seme").toBeDefined();

  const creata = await page.request.post("/api/v1/pantry", {
    data: { ingredient_id: zucchina!.id },
  });
  expect(creata.ok()).toBe(true);
  const voceId = ((await creata.json()) as { id: string }).id;

  const fraDueGiorni = new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
  const scritta = await page.request.patch(`/api/v1/pantry/${voceId}`, {
    data: { expires_on: fraDueGiorni },
  });
  expect(scritta.ok()).toBe(true);

  await page.getByRole("link", { name: "Dispensa" }).click();

  const riepilogo = page.getByRole("button", { name: /in scadenza questa settimana/ });
  await expect(riepilogo).toBeVisible();
  const box = await riepilogo.boundingBox();
  expect(box!.height).toBeGreaterThanOrEqual(44);

  // premuto, mostra la voce: `aria-pressed` e non solo il filtro applicato, perché
  // è un controllo scelto e non un'azione
  await riepilogo.click();
  await expect(riepilogo).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("li", { hasText: "zucchina" })).toBeVisible();

  // la pulizia: la X archivia davvero la voce sul server
  await page.getByRole("button", { name: "Togli zucchina dalla dispensa" }).click();
  await expect(page.getByText("Tolto dalla dispensa: zucchina")).toBeVisible();
});

test("la X di una pastiglia del filtro è un bersaglio da pollice, e la pastiglia si vede", async ({
  page,
}) => {
  // Stesso motivo del test sulle tacche della dispensa, qui sopra: una pastiglia
  // troppo piccola o senza fondo la vede
  // solo un browser. Questo filtro si usa in piedi in corsia, con il pollice, e
  // togliere un ingrediente è il gesto con cui si esce da un elenco vuoto — se la
  // X si manca, l'unica via d'uscita dal filtro è ricaricare la pagina.
  //
  // Non scrive niente: il filtro vive nello schermo, non sul server.
  await page.getByRole("link", { name: "Ricette" }).click();
  // categoria e ingredienti stanno nel pannello «Filtri» (T3 Consegna 4)
  await page.getByRole("button", { name: /^Filtri/ }).click();
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

  // Se il gradino scelto non cambiasse fondo, la scala direbbe cinque volte la
  // stessa cosa e nessun test in jsdom se ne accorgerebbe: questa asserzione e
  // quella sotto, insieme, dicono che i due gradini differiscono. Letto dal token e
  // non ricopiato qui, per lo stesso motivo di `tokenDelTema` più sotto: se il verde
  // cambia in index.css, questo controllo segue senza restare indietro.
  await expect(pastigliaDi(uno)).toHaveCSS("background-color", tokenDelTema("brand"));
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

/** Un token del blocco `@theme` di `src/index.css`, come `rgb(r, g, b)`.
 *
 * Letto dal file e non ricopiato qui: se il colore cambia in `index.css`, il controllo
 * del contrasto qui sotto misura il colore nuovo e lo confronta con il nuovo valore del
 * token — non con un esadecimale rimasto indietro in un test. */
function tokenDelTema(nome: string): string {
  const css = readFileSync(fileURLToPath(new URL("../src/index.css", import.meta.url)), "utf8");
  const tema = css.match(/@theme\s*\{([\s\S]*?)\n\}/)?.[1] ?? "";
  const esadecimale = tema.match(new RegExp(`--color-${nome}:\\s*#([0-9a-fA-F]{6})\\s*;`))?.[1];
  expect(esadecimale, `--color-${nome} non è nel blocco @theme di index.css`).toBeDefined();
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(esadecimale!.slice(i, i + 2), 16));
  return `rgb(${r}, ${g}, ${b})`;
}

/** Lo stesso token, dal blocco `@media (prefers-color-scheme: dark)` di `index.css`. */
function tokenDelTemaScuro(nome: string): string {
  const css = readFileSync(fileURLToPath(new URL("../src/index.css", import.meta.url)), "utf8");
  const scuro = css.match(/@media \(prefers-color-scheme: dark\)\s*\{\s*:root\s*\{([\s\S]*?)\}\s*\}/)?.[1] ?? "";
  const esadecimale = scuro.match(new RegExp(`--color-${nome}:\\s*#([0-9a-fA-F]{6})\\s*;`))?.[1];
  expect(esadecimale, `--color-${nome} non è nel blocco scuro di index.css`).toBeDefined();
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(esadecimale!.slice(i, i + 2), 16));
  return `rgb(${r}, ${g}, ${b})`;
}

/** Ogni testo visibile della pagina, col suo contrasto contro il primo fondo dipinto
 * dietro di lui. Salta ciò che è nascosto, i controlli spenti (WCAG li esenta) e il
 * testo dentro un `aria-hidden`. Torna solo i casi sotto 4,5:1, descritti.
 *
 * Gira da `body` e non da `page.evaluate`, per il motivo di `contrastoAVideo` più
 * sotto: questo file non ha la libreria DOM, e `document` o `getComputedStyle` come
 * globali non compilerebbero. Passando dal documento dell'elemento sì. */
async function testiIlleggibili(page: Page): Promise<string[]> {
  return page.locator("body").evaluate((body) => {
    const doc = body.ownerDocument;
    const view = doc.defaultView;
    const canali = (c: string) => (c.match(/[\d.]+/g) ?? []).map(Number);
    const lum = (c: string) => {
      const [r, g, b] = canali(c).map((v) => {
        const s = v / 255;
        return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const cattivi: string[] = [];
    // 4 è NodeFilter.SHOW_TEXT: la costante sta nella libreria DOM, che qui non c'è
    const walker = doc.createTreeWalker(body, 4);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const testo = n.textContent?.trim();
      const el = n.parentElement;
      if (!testo || !el) continue;
      if (el.closest("[aria-hidden=true], [disabled], [aria-disabled=true], .sr-only")) continue;
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      let fondo: string | null = null;
      let opacita = 1;
      for (let nodo = el; nodo; nodo = nodo.parentElement) {
        const s = view.getComputedStyle(nodo);
        opacita *= Number(s.opacity);
        if (fondo === null && (canali(s.backgroundColor)[3] ?? 1) > 0) fondo = s.backgroundColor;
      }
      if (opacita < 1) continue;
      const colore = view.getComputedStyle(el).color;
      // i numeri si estraggono come canali rgb: un `oklab(… / 0.6)` o un `color-mix()`
      // darebbe un rapporto inventato, quindi si dice che non si sa misurare
      if (!/^rgba?\(/.test(colore) || (fondo !== null && !/^rgba?\(/.test(fondo))) {
        cattivi.push(`«${testo.slice(0, 40)}» colore che lo scanner non sa leggere: ${colore} su ${fondo}`);
        continue;
      }
      const a = lum(colore);
      const b = lum(fondo ?? "rgb(255, 255, 255)");
      const rapporto = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
      if (rapporto < 4.5) cattivi.push(`«${testo.slice(0, 40)}» ${rapporto.toFixed(2)}:1 su ${fondo}`);
    }
    return cattivi;
  });
}

/** Il contrasto di un testo com'è a video, misurato dal browser.
 *
 * Colore del testo e fondo si leggono da `getComputedStyle`; il fondo è quello del primo
 * antenato che ne dipinge uno — un `<p>` sulla pagina è trasparente, e dietro di lui c'è
 * il `body` — e il rapporto WCAG si calcola dentro la pagina. Torna anche la dimensione
 * del carattere e l'opacità composta degli antenati: un'opacità sotto 1 schiarirebbe il
 * testo a video senza che il colore calcolato lo dica, e il rapporto mentirebbe.
 *
 * `el` è `any`: questo file lo compila tsconfig.node.json, senza la libreria DOM, quindi
 * `getComputedStyle` come globale non compilerebbe. Passando dalla finestra
 * dell'elemento sì — e la funzione si serializza e gira nel browser comunque. */
async function contrastoAVideo(testo: Locator) {
  return testo.evaluate((el) => {
    const view = el.ownerDocument.defaultView;
    const canali = (colore: string) => (colore.match(/[\d.]+/g) ?? []).map(Number);
    const luminanza = (colore: string) => {
      const [r, g, b] = canali(colore).map((v) => {
        const s = v / 255;
        return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };

    let fondo: string | null = null;
    let opacita = 1;
    for (let nodo = el; nodo; nodo = nodo.parentElement) {
      const stile = view.getComputedStyle(nodo);
      opacita *= Number(stile.opacity);
      const alfa = canali(stile.backgroundColor)[3] ?? 1;
      if (fondo === null && alfa > 0) fondo = stile.backgroundColor;
    }

    const stile = view.getComputedStyle(el);
    const a = luminanza(stile.color);
    const b = luminanza(fondo ?? "rgb(255, 255, 255)");
    return {
      colore: stile.color as string,
      fondo: fondo as string | null,
      dimensione: stile.fontSize as string,
      opacita,
      rapporto: (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05),
    };
  });
}

async function controllaContrasto(testo: Locator, token: string) {
  await expect(testo).toBeVisible();
  const misura = await contrastoAVideo(testo);
  test.info().annotations.push({
    type: "contrasto",
    description: `--color-${token} su ${misura.fondo}: ${misura.rapporto.toFixed(2)}:1`,
  });
  // è davvero il token, sul fondo della pagina, in `text-xs`, senza veli: altrimenti il
  // numero qui sotto sarebbe vero di un altro testo, non di quello che si voleva provare
  expect(misura.colore).toBe(tokenDelTema(token));
  expect(misura.fondo).toBe(tokenDelTema("page"));
  expect(misura.dimensione).toBe("12px");
  expect(misura.opacita).toBe(1);
  // AA per il testo piccolo: 12px non è «testo grande», quindi la soglia è 4.5 e non 3
  expect(misura.rapporto, `--color-${token} su --color-page`).toBeGreaterThanOrEqual(4.5);
}

/** Il contrasto WCAG 1.4.11 di un segno non testuale — qui, la barretta di una tacca
 * della dispensa — contro il fondo del primo antenato non trasparente: la stessa
 * risalita di `contrastoAVideo`, letta sul `backgroundColor` del segno invece che sul
 * `color` di un testo. La soglia per un segno è 3:1, non 4,5:1: non c'è niente da
 * leggere, solo da distinguere dal fondo. */
async function contrastoSegno(segno: Locator) {
  return segno.evaluate((el) => {
    const view = el.ownerDocument.defaultView;
    const canali = (colore: string) => (colore.match(/[\d.]+/g) ?? []).map(Number);
    const luminanza = (colore: string) => {
      const [r, g, b] = canali(colore).map((v) => {
        const s = v / 255;
        return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };

    const proprio = view.getComputedStyle(el).backgroundColor;
    let fondo: string | null = null;
    for (let nodo = el.parentElement; nodo; nodo = nodo.parentElement) {
      const stile = view.getComputedStyle(nodo);
      const alfa = canali(stile.backgroundColor)[3] ?? 1;
      if (alfa > 0) {
        fondo = stile.backgroundColor;
        break;
      }
    }

    const a = luminanza(proprio);
    const b = luminanza(fondo ?? "rgb(255, 255, 255)");
    return {
      colore: proprio as string,
      fondo: fondo as string | null,
      rapporto: (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05),
    };
  });
}

/** Il TOP del TESTO dentro un elemento, non del suo box: un `<button>` nativo centra
 * il contenuto in verticale, quindi il bounding box del pulsante parte più in alto
 * del testo che contiene — misurarlo direbbe che due righe sono allineate quando non
 * lo sono. Un `Range` sul primo nodo di testo prende il rettangolo del testo stesso,
 * indipendente dal centraggio o dal padding del contenitore. */
async function cimaDelTesto(elemento: Locator): Promise<number> {
  const cima = await elemento.evaluate((el) => {
    const nodo = [...el.childNodes].find(
      (figlio) => figlio.nodeType === 3 && figlio.textContent?.trim()
    );
    if (!nodo) return null;
    const range = el.ownerDocument.createRange();
    range.selectNodeContents(nodo);
    const rects = range.getClientRects();
    return rects.length ? rects[0].top : null;
  });
  expect(cima, "nessun nodo di testo diretto nell'elemento").not.toBeNull();
  return cima!;
}

// Parte IX, a. `index.css` *afferma* che `ink-faint` è il più chiaro che regge 4.5:1 sul
// fondo della pagina, e `low` ci sta sopra di un soffio: misurati qui il 2026-09-28,
// 4.67:1 e 4.59:1, cioè un 4% e un 2% di margine (la stima a mano di `ink-faint` diceva
// 4.58:1, ed era sbagliata). Qui lo misura il browser, sui testi veri che li usano
// in `text-xs` direttamente sul grigio della pagina — il caso peggiore, perché su una
// scheda bianca lo stesso colore rende di più.
test("il testo più chiaro dell'app regge 4.5:1 sul fondo della pagina, misurato a video", async ({
  page,
}) => {
  // `ink-faint`: la didascalia sotto la scala «quanto posso comprare» del ricettario, che
  // c'è sempre, anche a ricettario vuoto
  await page.getByRole("link", { name: "Ricette", exact: true }).click();
  await controllaContrasto(page.getByText("Tutto il ricettario.", { exact: true }), "ink-faint");

  // `low` in `text-xs` sul fondo della pagina sta in un posto solo: la bozza AI, sotto
  // un aggancio da confermare. La bozza la scrive il modello, che qui non si chiama:
  // la risposta di `POST /recipes/ai-draft` la dà `page.route`, e lo schermo, il
  // componente e il CSS sono quelli veri. L'ingrediente agganciato è uno vero del seme.
  const pomodoro = (
    (await (await page.request.get("/api/v1/ingredients/search?q=pomodoro")).json()) as {
      id: string;
      name: string;
    }[]
  ).find((voce) => voce.name === "pomodoro");
  expect(pomodoro, "«pomodoro» non è nel seme").toBeDefined();
  let bozzeServite = 0;
  await page.route("**/api/v1/recipes/ai-draft", (route) => {
    bozzeServite += 1;
    return route.fulfill({
      // `satisfies`: se la forma della bozza cambia nel frontend, lo stub non compila più
      // invece di restare indietro in silenzio
      json: {
        title: "Sugo di prova",
        description: null,
        instructions: "Scalda e servi.",
        servings: 2,
        cost: null,
        ingredients: [
          {
            raw_name: "Pomodori pelati",
            role: "primary",
            quantity_text: "400 g",
            ingredient_id: pomodoro!.id,
            matched_name: "pomodoro",
            confident: false,
            proposed_category: null,
          },
        ],
      } satisfies RecipeDraft,
    });
  });
  await page.goto("/ricette/nuova-ai");
  await page.getByLabel("Cosa vuoi cucinare").fill("un sugo");
  await page.getByRole("button", { name: "Proponi", exact: true }).click();
  await controllaContrasto(page.getByText(/^Parte escluso, perché l'aggancio/), "low");
  // la risposta l'ha data lo stub, non il modello: nessuna chiamata a OpenRouter
  expect(bozzeServite).toBe(1);
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

  // stessa cautela del test sulle tacche: una voce che nessun altro file nomina
  // («cipolla» è già di quel test, «pomodoro» di cooking.spec.ts), e archiviata in
  // fondo, perché la dispensa è stato condiviso e il database vive quanto lo stack.
  // L'aggiunta passa dalla barra in cima, come nel test sulle tacche.
  await page.getByLabel("Cerca o aggiungi in dispensa").fill("carot");
  await page.getByRole("button", { name: "Aggiungi in dispensa" }).click();
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
  //
  // Rilievo di revisione: fra tre giorni `expiryText` scrive «scade tra 3 gg», non
  // «Scade il …» (quella forma è per una data «soon» a un giorno o meno, o per una
  // già passata) — misurato qui il 2026-09-28. Il testo minuscolo copre tutti i rami
  // «soon» (oggi, domani, fra N giorni): è quello che questo controllo vuole, il
  // colore del token, non la parola esatta.
  const pastiglia = riga.getByText(/^scade /);
  await expect(pastiglia).toHaveCSS("color", "rgb(91, 69, 168)");

  // La pastiglia è anche un pulsante: toccarla riapre il campo, ed è l'unica strada
  // per correggere una data battuta male (spec §6). Il disegno è la pastiglia, alta
  // 24px; il bersaglio dev'essere quello di tutti gli altri, come il «+ scadenza»
  // che stava qui un momento fa — due controlli affiancati, uno da 44px e uno da 24,
  // sarebbero mezza correzione. Anche questa misura la può fare solo un browser.
  // Il nome accessibile porta il prefisso «Scadenza di <label>: », non la sola
  // parola della pastiglia (stesso rilievo di revisione qui sopra).
  const correggi = riga.getByRole("button", { name: /^Scadenza di carota: scade/ });
  const boxPastiglia = await correggi.boundingBox();
  expect(boxPastiglia!.height).toBeGreaterThanOrEqual(40);

  // Dalla tastiera il fuoco torna al pulsante, e resta lì anche dopo il salvataggio.
  // Invio con una data cambiata manda la PATCH, la riga si spegne finché la risposta
  // non torna, e un pulsante `disabled` perde il fuoco senza nemmeno un blur: finiva
  // sul `body`. jsdom non toglie il fuoco a un pulsante disabilitato, quindi lo vede
  // solo un browser, e solo con una scrittura vera.
  const fraCinqueGiorni = new Date(Date.now() + 5 * 24 * 60 * 60 * 1000)
    .toISOString()
    .slice(0, 10);
  await correggi.click();
  const salvata = page.waitForResponse(
    (risposta) => risposta.request().method() === "PATCH" && risposta.url().includes("/pantry/")
  );
  await campo.fill(fraCinqueGiorni);
  await campo.press("Enter");
  await salvata;
  const scadenzaNuova = riga.getByRole("button", { name: /^Scadenza di carota: scade tra 5 gg/ });
  await expect(scadenzaNuova).toBeVisible();
  await expect(scadenzaNuova).toBeFocused();

  // Esc chiude senza scrivere: la data resta quella di prima e il fuoco torna lì
  await scadenzaNuova.click();
  await campo.fill(fraTreGiorni);
  await campo.press("Escape");
  // l'`input` e non `campo`: `getByLabel` prende anche l'`aria-label` del pulsante,
  // che comincia con «Scadenza di carota», e il conto sarebbe 1 a campo chiuso
  await expect(riga.locator('input[type="date"]')).toHaveCount(0);
  await expect(scadenzaNuova).toBeFocused();

  // la pulizia, come fa il test sulle tacche: senza, la dispensa cresce di una
  // riga a ogni esecuzione su uno stack riusato
  await riga.getByRole("button", { name: "Togli carota dalla dispensa" }).click();
  await expect(page.getByText("Tolto dalla dispensa: carota")).toBeVisible();
});

test("a 375px nessuna schermata scorre di lato, e in lista si spunta toccando il nome", async ({
  page,
}) => {
  // S16: a 375px una voce con la nota del rientro allargava la pagina a 394px, e
  // la X di quella voce restava mezza fuori dallo schermo. `scrollWidth` lo calcola
  // il browser dal CSS che Tailwind ha costruito: jsdom non lo vede, quindi questo
  // è l'unico posto da cui si misura. Il controllo gira su ogni schermata
  // principale, non solo sulla lista: una riga che non si stringe è un difetto che
  // si può riscrivere ovunque.
  //
  // La nota esiste solo su una voce rientrata dalla cottura, quindi il test la
  // produce col gesto vero, come `cooking.spec.ts`: il mascarpone entra in
  // dispensa con l'ingresso diretto, il tiramisù lo finisce, e torna in lista.
  // Ingrediente e ricetta non li nomina nessun altro file, e in fondo si tolgono
  // voce di lista e voce di dispensa: questo file non lascia niente dietro di sé.
  await page.getByRole("link", { name: "Dispensa" }).click();
  await page.getByLabel("Cerca o aggiungi in dispensa").fill("mascarp");
  await page.getByRole("button", { name: "Aggiungi in dispensa" }).click();
  await page.getByRole("option", { name: /^Mascarpone\b/ }).click();
  await expect(page.locator("li", { hasText: "mascarpone" })).toBeVisible();

  await page.getByRole("link", { name: "Ricette", exact: true }).click();
  await page.getByRole("link", { name: /Tiramisù/ }).first().click();
  const ricetta = new URL(page.url()).pathname;
  await page.getByRole("button", { name: "Cucina", exact: true }).click();
  await page
    .getByRole("group", { name: /mascarpone/i })
    .getByRole("button", { name: "Finito", exact: true })
    .click();
  await expect(page.getByRole("checkbox", { name: /Rimetti in lista/ })).toBeChecked();
  await page.getByRole("button", { name: "Ho cucinato", exact: true }).click();
  // per il testo, come in `cooking.spec.ts`: l'avviso unico tiene sempre la sua regione
  await expect(page.getByRole("status").filter({ hasText: /^Segnato\./ })).toHaveText(
    "Segnato. Una cosa è tornata in lista della spesa."
  );

  await page.setViewportSize({ width: 375, height: 812 });

  // stringhe e non funzioni, per il motivo detto sul test dell'intestazione
  const nonScorreDiLato = async (schermata: string) => {
    await page.waitForLoadState("networkidle");
    const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
    const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
    expect(scrollWidth, `${schermata} scorre di lato`).toBeLessThanOrEqual(clientWidth);
  };

  await page.goto("/lista");
  const voce = page.getByRole("checkbox", { name: "mascarpone" });
  await expect(voce).toBeVisible();
  // la nota di QUESTA voce: `cooking.spec.ts` lascia in lista il suo pomodoro,
  // rientrato con la stessa nota
  const etichetta = page.locator("label").filter({ has: voce });
  await expect(etichetta.getByText("rientrata perché finita cucinando")).toBeVisible();
  // una prova a occhio per chi rivede: la cartella è quella dei risultati di
  // Playwright, che git ignora
  await page.screenshot({ path: test.info().outputPath("lista-375.png"), fullPage: true });
  await nonScorreDiLato("/lista");

  // S17: il bersaglio della spunta è la label intorno a casella, nome e nota, e il
  // pollice la prende solo se è alta almeno 44px. La X resta fuori: dentro, un
  // tocco per togliere una voce la spunterebbe anche
  await expect(etichetta).toContainText("mascarpone");
  await expect(etichetta.getByRole("button")).toHaveCount(0);
  const box = await etichetta.boundingBox();
  expect(box!.height).toBeGreaterThanOrEqual(44);

  await page.goto("/sistema");
  await nonScorreDiLato("/sistema");
  await page.goto("/dispensa");
  await expect(page.getByRole("heading", { name: "Dispensa" })).toBeVisible();
  await nonScorreDiLato("/dispensa");
  await page.goto("/ricette");
  await expect(page.getByRole("link", { name: /Tiramisù/ }).first()).toBeVisible();
  await nonScorreDiLato("/ricette");
  await page.goto(ricetta);
  await expect(page.getByRole("button", { name: "Cucina", exact: true })).toBeVisible();
  await nonScorreDiLato("il dettaglio di una ricetta");

  // la pulizia: la voce rientrata esce dalla lista, e quella finita dalla dispensa
  await page.goto("/lista");
  await page.getByRole("button", { name: "Togli mascarpone dalla lista" }).click();
  await expect(page.getByRole("checkbox", { name: "mascarpone" })).toHaveCount(0);
  await page.goto("/dispensa");
  await page.getByRole("button", { name: "Togli mascarpone dalla dispensa" }).click();
  await expect(page.getByText("Tolto dalla dispensa: mascarpone")).toBeVisible();
});

// T3, Consegna 0: il tema scuro. `theme.test.ts` fa l'aritmetica sui valori scritti in
// `index.css`; qui si misura quel che arriva a video, su ogni testo di ogni luogo che il
// seme `--con-ricette` raggiunge. Una coppia che nessuno ha messo in PAIRS — un
// `text-brand` finito su `bg-low-tint` — l'aritmetica non la vede; il browser sì.
//
// Cosa lo scanner (`testiIlleggibili`) misura e cosa no, detto esatto: prende il colore
// calcolato del testo e quello del primo antenato con un fondo non trasparente, e ne fa
// il rapporto WCAG. Salta il testo sotto un antenato con `opacity` minore di 1 (i
// controlli spenti, gli elementi velati), dentro `aria-hidden`, `disabled` o `.sr-only`.
// Non misura segnaposto e valori dei campi (non sono nodi di testo), né il testo sopra
// un'immagine o un gradiente, che confronta col primo fondo pieno. Legge i colori come
// `rgb()`/`rgba()`: un colore con l'alfa di Tailwind 4 (`text-ink/60`) si calcola in
// `oklab(… / 0.6)`, che non saprebbe leggere, e per questo lo segnala invece di
// misurarlo male. Oggi in `src/` nessun testo porta un'opacità.
const SCHERMATE = [
  "/lista",
  "/sistema",
  "/dispensa",
  "/ricette",
  "/ricette/nuova-ai",
  "/ricette/importa",
  "/anagrafica",
  "/non-esiste",
];

// scritto a mano: questo file non ha la libreria DOM (vedi `testiIlleggibili`)
type Animazione = { effect: { getTiming: () => { iterations?: number } } | null; finished: Promise<unknown> };

/** Aspetta che le transizioni in corso finiscano, prima di una misura del contrasto.
 * `transition-colors` sposta il colore in 150 ms: misurato appena dopo un tocco, o
 * appena cambiato il tema, un pulsante sta a metà fra il fondo di prima e quello di
 * dopo, e il rapporto è di un colore che nessuno vede fermo (è successo: «Finito» a
 * 3,15:1 su un rosso a metà strada). Le animazioni infinite (una rotella che gira) non
 * finirebbero mai, e restano fuori. Una sola, per `perOgniLuogo` e per le prove che
 * misurano uno stato che solo loro aprono. */
async function fermo(page: Page) {
  await page.locator("body").evaluate((body) =>
    Promise.all(
      body.ownerDocument
        .getAnimations()
        .filter((a: Animazione) => a.effect?.getTiming().iterations !== Infinity)
        .map((a: Animazione) => a.finished.catch(() => undefined))
    )
  );
}

/** Passa da ogni luogo misurato e chiama `misura` su ciascuno, già caricato.
 *
 * Prima le schermate che si aprono da un indirizzo fisso. Poi quelle che hanno bisogno
 * di un id, raggiunte toccando come fa chi usa l'app: il dettaglio della prima ricetta,
 * il foglio della cottura aperto, la modifica della ricetta, la scheda di un ingrediente
 * e quella di un prodotto dall'anagrafica. Il seme non ha prodotti e non popola la
 * dispensa, e senza una confezione il foglio della cottura non mostra i tre stati (né il
 * rosso pieno di «Finito», `STATUS_TONE.finished.fill`), né l'ingrediente elenca un
 * prodotto da aprire: così prodotto e confezione si creano con `page.request`, sotto il
 * primo ingrediente della ricetta, e si tolgono nel `finally`. Nella cottura si sceglie
 * «Finito» e poi «Annulla»: niente si registra. Per ultimi il ☰ aperto e l'accesso, che
 * butta via i cookie e quindi viene dopo la pulizia. */
async function perOgniLuogo(page: Page, misura: (luogo: string) => Promise<void>) {
  // prima di ogni misura, le transizioni in corso finiscono: vedi `fermo`
  const misuraFermo = async (luogo: string) => {
    await fermo(page);
    await misura(luogo);
  };

  // «/dispensa» è fra le SCHERMATE, e il seme non la popola: misurata vuota non
  // mostra né una tacca né la ✕ né il pulsante «+ scadenza», e lo scanner del
  // contrasto e quello dei nomi dei pulsanti non li vedrebbero mai. Una voce
  // feriale, creata e tolta qui perché serve solo a questo giro e non a un test
  // suo. «Farina» la usa anche il passo 7 della prova di «Sistema la spesa a 375px»,
  // ma solo per abbinarci una voce della lista: non crea righe in dispensa, e le due
  // prove non si pestano i piedi.
  const trovate = (await (
    await page.request.get("/api/v1/ingredients/search?q=farina")
  ).json()) as { id: string; name: string }[];
  const farina = trovate.find((voce) => voce.name === "farina");
  expect(farina, "«farina» non è nel seme").toBeDefined();
  const riempimento = await page.request.post("/api/v1/pantry", {
    data: { ingredient_id: farina!.id },
  });
  expect(riempimento.ok()).toBe(true);
  const riempimentoId = ((await riempimento.json()) as { id: string }).id;

  try {
    for (const indirizzo of SCHERMATE) {
      await page.goto(indirizzo);
      await page.waitForLoadState("networkidle");
      // la schermata vera, non l'accesso: vedi il `beforeEach` del tema qui sotto
      await expect(page.getByLabel("Password", { exact: true })).toHaveCount(0);
      await misuraFermo(indirizzo);
    }
  } finally {
    // prima che i cookie spariscano (in fondo a questa funzione, per la schermata
    // d'accesso): dopo, una PATCH autenticata non arriverebbe da nessuna parte e la
    // voce resterebbe, crescendo la dispensa a ogni esecuzione su uno stack riusato.
    // `expect.soft` e non un'asserzione: un `finally` che lancia nasconderebbe l'errore
    // vero del `try`, ma la prova risulta comunque fallita, così una voce rimasta non
    // passa per un successo silenzioso (come la pulizia della barra della lista, in
    // fondo al file)
    try {
      const risposta = await page.request.patch(`/api/v1/pantry/${riempimentoId}`, {
        data: { archived: true },
      });
      expect.soft(risposta.ok(), `pulizia: la voce ${riempimentoId} non si è archiviata`).toBe(true);
    } catch (guasto) {
      expect
        .soft(false, `pulizia: non sono riuscito ad archiviare la voce ${riempimentoId} (${guasto})`)
        .toBe(true);
    }
  }

  // il dettaglio: la prima scheda del ricettario. Una scheda è un link dentro una voce
  // della lista (RecipeRow), senza titoli `h2`/`h3`
  await page.goto("/ricette");
  await page.getByRole("listitem").getByRole("link").first().click();
  await expect(page.getByRole("button", { name: "Cucina", exact: true })).toBeVisible();
  const ricettaId = new URL(page.url()).pathname.split("/").pop()!;
  const ricetta = (await (await page.request.get(`/api/v1/recipes/${ricettaId}`)).json()) as {
    ingredients: { ingredient_id: string }[];
  };
  const ingredienteId = ricetta.ingredients[0].ingredient_id;

  const nome = `Prodotto e2e ${Date.now()}`;
  const creato = await page.request.post("/api/v1/products", {
    // marca e codice a barre anche, per misurare le righe che li mostrano; il codice è
    // unico nel catalogo e qui cambia a ogni esecuzione
    data: { ingredient_id: ingredienteId, name: nome, brand: "Marca e2e", barcode: String(Date.now()) },
  });
  expect(creato.ok()).toBe(true);
  const prodottoId = ((await creato.json()) as { id: string }).id;
  let voceId: string | undefined;
  try {
    const inDispensa = await page.request.post("/api/v1/pantry", {
      data: { ingredient_id: ingredienteId, product_id: prodottoId, note: "nota e2e" },
    });
    expect(inDispensa.ok()).toBe(true);
    voceId = ((await inDispensa.json()) as { id: string }).id;

    // di nuovo il dettaglio, ora che la dispensa ha qualcosa per questa ricetta
    await page.reload();
    await expect(page.getByRole("button", { name: "Cucina", exact: true })).toBeVisible();
    await page.waitForLoadState("networkidle");
    await misuraFermo("dettaglio");

    await page.getByRole("button", { name: "Cucina", exact: true }).click();
    const finito = page.getByRole("button", { name: "Finito", exact: true }).first();
    await finito.click();
    await expect(finito).toHaveAttribute("aria-pressed", "true");
    await misuraFermo("cottura, con «Finito» scelto");
    await page.getByRole("button", { name: "Annulla", exact: true }).click();

    await page.getByRole("link", { name: "Modifica", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Modifica la ricetta" })).toBeVisible();
    await page.waitForLoadState("networkidle");
    await misuraFermo("modifica della ricetta");

    // dall'anagrafica, cercando il prodotto; dalla sua scheda, il suo ingrediente
    await page.goto("/anagrafica");
    await page.getByLabel("Cerca un ingrediente o un prodotto", { exact: true }).fill(nome);
    await page.getByRole("link", { name: new RegExp(nome) }).click();
    await expect(page.getByRole("heading", { name: nome })).toBeVisible();
    await page.waitForLoadState("networkidle");
    await misuraFermo("scheda del prodotto");

    await page.getByRole("main").locator(`a[href^="/anagrafica/ingrediente/${ingredienteId}"]`).click();
    await expect(page.getByRole("link", { name: new RegExp(nome) })).toBeVisible();
    await page.waitForLoadState("networkidle");
    await misuraFermo("scheda dell'ingrediente");
  } finally {
    // Un `finally` che lancia nasconderebbe l'errore vero del `try`: ogni passo resta un
    // `expect.soft`, che non lancia e non salta il passo dopo, ma segna la prova fallita
    // — una voce o un prodotto rimasti non passano per un successo silenzioso. Prima la
    // voce, poi il prodotto
    if (voceId) {
      try {
        const risposta = await page.request.patch(`/api/v1/pantry/${voceId}`, {
          data: { archived: true },
        });
        expect.soft(risposta.ok(), `pulizia: la voce ${voceId} non si è archiviata`).toBe(true);
      } catch (guasto) {
        expect
          .soft(false, `pulizia: non sono riuscito ad archiviare la voce ${voceId} (${guasto})`)
          .toBe(true);
      }
    }
    try {
      const risposta = await page.request.delete(`/api/v1/products/${prodottoId}`);
      expect.soft(risposta.ok(), `pulizia: il prodotto ${prodottoId} non si è eliminato`).toBe(true);
    } catch (guasto) {
      expect
        .soft(false, `pulizia: non sono riuscito a eliminare il prodotto ${prodottoId} (${guasto})`)
        .toBe(true);
    }
  }

  // il ☰ aperto: il pannello sta in un portale suo, con un fondo suo
  await page.goto("/lista");
  await page.getByRole("button", { name: "Apri il menu" }).click();
  await expect(page.getByRole("dialog", { name: "Menu" })).toBeVisible();
  await misuraFermo("☰");
  // e l'accesso, l'unica schermata che si vede da fuori: senza il cookie, il primo 401
  // la fa comparire
  await page.context().clearCookies();
  await page.goto("/");
  await expect(page.getByLabel("Password", { exact: true })).toBeVisible();
  await misuraFermo("accesso");
}

for (const tema of ["light", "dark"] as const) {
  test.describe(`tema ${tema === "light" ? "chiaro" : "scuro"}`, () => {
    test.use({ colorScheme: tema });

    // Il `beforeEach` in cima al file preme «Entra» e non aspetta la risposta: un
    // `page.goto` subito dopo interrompe l'accesso, e ogni schermata qui sotto diventa
    // la schermata d'accesso — misurata a ogni giro, con un verde che non dice niente
    // delle altre. Si aspetta la barra delle schede, che c'è solo da dentro.
    test.beforeEach(async ({ page }) => {
      await expect(page.getByRole("link", { name: "Ricette", exact: true })).toBeVisible();
    });

    test("il fondo della pagina è il token del tema", async ({ page }) => {
      const atteso = tema === "light" ? tokenDelTema("page") : tokenDelTemaScuro("page");
      await expect(page.locator("body")).toHaveCSS("background-color", atteso);
    });

    test("in ogni luogo ogni testo sta sopra 4,5:1", async ({ page }) => {
      const tutti: string[] = [];
      await perOgniLuogo(page, async (luogo) => {
        tutti.push(...(await testiIlleggibili(page)).map((t) => `${luogo}: ${t}`));
      });
      expect(tutti).toEqual([]);
    });

    test("ogni pulsante ha un nome, anche quelli di sola icona", async ({ page }) => {
      const muti: string[] = [];
      await perOgniLuogo(page, async (luogo) => {
        // da `body`, per il motivo di `testiIlleggibili`
        const qui = await page.locator("body").evaluate((body) =>
          [...body.querySelectorAll("button")]
            .filter(
              (b) =>
                !(b.getAttribute("aria-label") || b.textContent?.trim() || b.getAttribute("aria-labelledby"))
            )
            .map((b) => b.outerHTML.slice(0, 80) as string)
        );
        muti.push(...qui.map((b) => `${luogo}: ${b}`));
      });
      expect(muti).toEqual([]);
    });
  });
}

test("il carattere è Inter, servito dall'app", async ({ page }) => {
  await page.waitForLoadState("networkidle");
  // `fonts.check` da solo non basta: torna vero anche per una famiglia che nessun
  // `@font-face` dichiara, perché «non c'è niente da caricare». Quindi prima si chiede
  // che la faccia di Inter esista nel documento e sia caricata davvero.
  const inter = await page.locator("body").evaluate((body) =>
    [...body.ownerDocument.fonts]
      .filter((f) => f.family.replace(/["']/g, "") === "Inter Variable")
      .map((f) => f.status as string)
  );
  expect(inter).toContain("loaded");
  expect(
    await page.locator("body").evaluate((body) => body.ownerDocument.fonts.check('16px "Inter Variable"') as boolean)
  ).toBe(true);
  await expect(page.locator("body")).toHaveCSS("font-family", /Inter Variable/);
});

// Inter è servito dall'app perché la PWA funzioni senza rete (spec T3 §2), e il test qui
// sopra non lo prova: con la rete il carattere arriva comunque. La prima stesura non lo
// metteva nel precaricamento, e nessun test lo vedeva. Qui si legge il `sw.js` che Nginx
// serve davvero; `vite.config.test.ts` prova gli schemi, questo il file costruito.
test("il service worker mette da parte Inter latino, e non gli altri alfabeti", async ({ page }) => {
  const risposta = await page.request.get("/sw.js");
  expect(risposta.ok()).toBe(true);
  const sw = await risposta.text();
  // il service worker vero, non l'index.html che Nginx dà per un indirizzo che non c'è
  expect(sw).toContain("precacheAndRoute");
  expect(sw).toMatch(/assets\/inter-latin-wght-normal-[\w-]+\.woff2/);
  expect(sw).toMatch(/assets\/inter-latin-ext-wght-normal-[\w-]+\.woff2/);
  expect(sw).not.toMatch(/inter-(cyrillic|greek|vietnamese)/);
});

// Il + di ActionBar (forma `square`). jsdom legge le classi ma non le calcola, e il
// difetto che questo prova stava proprio nel calcolo: `rounded-[10px]` accodato a un
// `rounded-full`, e nel CSS compilato vinceva il cerchio. ActionBar non sta ancora in
// nessuna schermata (le Consegne 1–6 la adottano), quindi il pulsante si mette nella
// pagina a mano, con le classi che `Button` gli darebbe e il CSS che Nginx serve.
test("il pulsante quadrato ha gli angoli dei pulsanti, non il cerchio", async ({ page }) => {
  await expect(page.getByRole("link", { name: "Ricette", exact: true })).toBeVisible();
  const misura = await page.locator("body").evaluate((body, classi) => {
    const doc = body.ownerDocument;
    const bottone = doc.createElement("button");
    bottone.className = classi;
    bottone.textContent = "+";
    body.appendChild(bottone);
    const stile = doc.defaultView.getComputedStyle(bottone);
    const esito = { raggio: stile.borderTopLeftRadius as string, lato: stile.width as string };
    bottone.remove();
    return esito;
  }, buttonClasses("primary", "square"));
  expect(misura).toEqual({ raggio: "10px", lato: "44px" });
});

test("la barra della lista resta sotto l'intestazione scorrendo, e la ✕ offre «Annulla»", async ({
  page,
}) => {
  // Dal giro: la barra e l'intestazione erano tutte e due `sticky top-0 z-10`, e
  // scorrendo la barra copriva l'intestazione. Ora la barra si ferma sotto. Serve una
  // lista più alta della finestra: otto voci a testo libero, create con l'API e tolte
  // in fondo, perché la lista è stato condiviso e il database vive quanto lo stack.
  //
  // il `beforeEach` tocca «Entra» ma non aspetta la risposta: senza un'attesa qui,
  // la prima `page.request` qui sotto può partire prima che il cookie di sessione
  // sia scritto, e tornare 401 (vedi lo stesso appunto sopra, al riepilogo scadenze).
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 500 });
  const voci = Array.from({ length: 8 }, (_, i) => `prova scorrimento ${i + 1}`);
  const create: string[] = [];
  try {
    for (const raw_text of voci) {
      const risposta = await page.request.post("/api/v1/shopping-list", {
        data: { raw_text, ingredient_id: null },
      });
      expect(risposta.ok()).toBe(true);
      create.push(((await risposta.json()) as { id: string }).id);
    }

    await page.goto("/lista");
    await expect(page.getByRole("checkbox", { name: "prova scorrimento 8" })).toBeVisible();
    await page.mouse.wheel(0, 1500);
    // aspetta che lo scorrimento sia arrivato davvero, o le misure qui sotto
    // guarderebbero la pagina ferma in cima
    await expect.poll(() => page.evaluate<number>("window.scrollY")).toBeGreaterThan(100);

    const intestazione = await page.getByRole("banner").boundingBox();
    const campo = page.getByLabel("Aggiungi alla lista");
    await expect(campo).toBeInViewport();
    const barra = await campo.boundingBox();
    expect(
      barra!.y,
      "la barra della lista copre l'intestazione"
    ).toBeGreaterThanOrEqual(intestazione!.y + intestazione!.height);
    // e l'intestazione è davvero quella che si vede lì sopra, non qualcosa che le
    // passa sopra: il punto al centro del marchio appartiene all'intestazione
    const sopra = await page.evaluate<boolean>(
      `(() => { const h = document.querySelector("header"); const r = h.getBoundingClientRect();
         const el = document.elementFromPoint(r.left + 40, r.top + r.height / 2);
         return !!el && h.contains(el); })()`
    );
    expect(sopra, "qualcosa copre l'intestazione").toBe(true);

    // la ✕ è un bersaglio da pollice, e togliere offre «Annulla», che rimette la voce
    const togli = page.getByRole("button", { name: "Togli prova scorrimento 1 dalla lista" });
    const box = await togli.boundingBox();
    expect(box!.width).toBeGreaterThanOrEqual(44);
    expect(box!.height).toBeGreaterThanOrEqual(44);
    await togli.click();
    await expect(page.getByText("Tolto dalla lista: prova scorrimento 1")).toBeVisible();
    await expect(page.getByRole("checkbox", { name: "prova scorrimento 1" })).toHaveCount(0);
    await page.getByRole("button", { name: "Annulla" }).click();
    await expect(page.getByRole("checkbox", { name: "prova scorrimento 1" })).toBeVisible();
  } finally {
    // pulizia in un `finally`: un `finally` che solleva nasconderebbe l'errore vero
    // del `try`, quindi ogni PATCH resta un `expect.soft` — non lancia, quindi non
    // salta le altre voci — ma segna comunque la prova fallita, così una riga
    // rimasta in lista non passa per un successo silenzioso
    for (const id of create) {
      try {
        const risposta = await page.request.patch(`/api/v1/shopping-list/${id}`, {
          data: { status: "archived" },
        });
        expect.soft(risposta.ok(), `pulizia: la voce ${id} non si è archiviata`).toBe(true);
      } catch (guasto) {
        expect.soft(false, `pulizia: non sono riuscito ad archiviare la voce ${id} (${guasto})`).toBe(true);
      }
    }
  }
});

test("Sistema la spesa a 375px: una riga per voce, e un pannello alla volta sotto la sua voce", async ({
  page,
}) => {
  // T3 Consegna 3. Il seme non ha voci nel carrello, e i percorsi prima di questo lasciano
  // in lista solo voci da comprare: le voci si creano qui con l'API, si spuntano, e si
  // tolgono in fondo. Tre con un ingrediente del seme che nessun altro file nomina — una
  // col nome lungo, per lo scorrimento di lato — e una a testo libero, per «Abbina».
  //
  // il `beforeEach` tocca «Entra» ma non aspetta la risposta: senza un'attesa qui la
  // prima `page.request` può partire prima del cookie di sessione, e tornare 401
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  const lungo =
    "fagioli cannellini lessati in barattolo di vetro formato famiglia del supermercato sotto casa";
  const libera = "prova sistemazione senza ingrediente";
  const voci = [
    { nome: "bresaola", raw_text: "bresaola" },
    { nome: "succo d'arancia", raw_text: "succo d'arancia" },
    { nome: "fagioli cannellini", raw_text: lungo },
  ];
  const create: string[] = [];
  try {
    for (const voce of voci) {
      const trovati = (await (
        await page.request.get(`/api/v1/ingredients/search?q=${encodeURIComponent(voce.nome)}`)
      ).json()) as { id: string; name: string }[];
      const ingrediente = trovati.find((trovato) => trovato.name === voce.nome);
      expect(ingrediente, `«${voce.nome}» non è nel seme`).toBeDefined();
      const risposta = await page.request.post("/api/v1/shopping-list", {
        data: { raw_text: voce.raw_text, ingredient_id: ingrediente!.id },
      });
      // 201: una voce che c'era già (S18) risponde 200 ed è di qualcun altro — la pulizia
      // in fondo la toglierebbe a chi l'ha messa
      expect(risposta.status(), `«${voce.nome}» era già in lista`).toBe(201);
      create.push(((await risposta.json()) as { id: string }).id);
    }
    const senza = await page.request.post("/api/v1/shopping-list", {
      data: { raw_text: libera, ingredient_id: null },
    });
    expect(senza.status()).toBe(201);
    create.push(((await senza.json()) as { id: string }).id);
    for (const id of create) {
      const spunta = await page.request.patch(`/api/v1/shopping-list/${id}`, {
        data: { status: "checked" },
      });
      expect(spunta.ok()).toBe(true);
    }

    await page.goto("/sistema");
    await expect(page.getByText(lungo, { exact: true })).toBeVisible();

    // 1. niente scorrimento di lato, nemmeno col nome lungo accanto alle tre icone.
    // Stringhe e non funzioni: questo file non ha la libreria DOM (vedi il test
    // dell'intestazione)
    await page.waitForLoadState("networkidle");
    const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
    const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
    expect(scrollWidth, "/sistema scorre di lato").toBeLessThanOrEqual(clientWidth);

    // 2. le tre icone della voce lunga: bersagli da pollice, e su una riga sola
    const scatole: { x: number; y: number; width: number; height: number }[] = [];
    for (const nome of [
      `Codice a barre per ${lungo}`,
      `Cerca a catalogo per ${lungo}`,
      `Sfuso, senza marca: ${lungo}`,
    ]) {
      const scatola = await page.getByRole("button", { name: nome, exact: true }).boundingBox();
      expect(scatola, nome).not.toBeNull();
      expect(scatola!.width, nome).toBeGreaterThanOrEqual(44);
      expect(scatola!.height, nome).toBeGreaterThanOrEqual(44);
      scatole.push(scatola!);
    }
    for (const scatola of scatole.slice(1)) {
      expect(Math.abs(scatola.y - scatole[0].y), "le tre icone vanno a capo").toBeLessThan(1);
    }

    // 3. il contrasto delle righe vere, nei due temi: una voce risolta (con «Sfuso» sotto
    // il nome), una col campo della scadenza aperto, una da abbinare
    await page.getByRole("button", { name: "Sfuso, senza marca: bresaola", exact: true }).click();
    await expect(page.getByText("Sfuso", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "+ scadenza per succo d'arancia", exact: true }).click();
    await expect(page.getByLabel("Scadenza di succo d'arancia")).toBeVisible();
    await expect(page.getByRole("button", { name: `Abbina: ${libera}`, exact: true })).toBeVisible();
    for (const tema of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: tema });
      await fermo(page);
      expect(await testiIlleggibili(page), `righe, tema ${tema}`).toEqual([]);
    }
    await page.emulateMedia({ colorScheme: "light" });

    // 4. il catalogo della voce lunga, nel terzo reparto: resta a video solo lei col suo
    // pannello, e l'inizio del pannello non finisce sotto l'intestazione fissa
    const catalogo = page.getByRole("button", { name: `Cerca a catalogo per ${lungo}`, exact: true });
    await catalogo.click();
    const titolo = page.getByRole("heading", { name: `Cerca a catalogo per «${lungo}»` });
    await expect(titolo).toBeVisible();
    await expect(page.getByText("bresaola", { exact: true })).toHaveCount(0);
    await expect(page.getByText(libera, { exact: true })).toHaveCount(0);
    // le intestazioni dei reparti se ne vanno: l'unico h2 rimasto è il titolo del
    // pannello, che è un h2 anche lui (Task 7)
    await expect(page.getByRole("heading", { level: 2 })).toHaveText([
      `Cerca a catalogo per «${lungo}»`,
    ]);
    await expect(page.getByRole("button", { name: /Metti in dispensa/ })).toHaveCount(0);
    await expect(titolo).toBeInViewport();
    const intestazione = await page.getByRole("banner").boundingBox();
    await expect
      .poll(async () => (await titolo.boundingBox())!.y, {
        message: "il pannello finisce sotto l'intestazione",
      })
      .toBeGreaterThanOrEqual(intestazione!.y + intestazione!.height);
    // e il titolo è davvero quel che si vede lì: il punto al suo centro appartiene a lui,
    // non a qualcosa che gli passa sopra
    const scoperto = await titolo.evaluate((el) => {
      const r = el.getBoundingClientRect();
      const sopra = el.ownerDocument.elementFromPoint(r.left + 10, r.top + r.height / 2);
      return !!sopra && el.contains(sopra);
    });
    expect(scoperto, "qualcosa copre il titolo del pannello").toBe(true);

    // 5. «Annulla» rimette tutto com'era: le altre voci, la scelta fatta, e il fuoco sul
    // pulsante che aveva aperto il pannello
    await page.getByRole("button", { name: "Annulla", exact: true }).click();
    await expect(page.getByText("bresaola", { exact: true })).toBeVisible();
    await expect(page.getByText("Sfuso", { exact: true })).toBeVisible();
    await expect(catalogo).toBeFocused();

    // 6. il pannello del codice dice per quale voce è aperto e chiede i numeri (S10), e
    // anche lui si legge nei due temi. Nel browser dell'e2e la fotocamera non c'è: il
    // pannello lo dice, e offre la strada a mano
    await page.getByRole("button", { name: `Codice a barre per ${lungo}`, exact: true }).click();
    await expect(page.getByRole("heading", { name: `Codice a barre per «${lungo}»` })).toBeVisible();
    await expect(page.getByLabel("Codice a barre", { exact: true })).toHaveAttribute(
      "inputmode",
      "numeric"
    );
    for (const tema of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: tema });
      await fermo(page);
      expect(await testiIlleggibili(page), `pannello del codice, tema ${tema}`).toEqual([]);
    }
    await page.emulateMedia({ colorScheme: "light" });
    await page.getByRole("button", { name: "Annulla", exact: true }).click();
    await expect(page.getByText(libera, { exact: true })).toBeVisible();

    // 7. un abbinamento riuscito porta la voce nel suo reparto, e il fuoco la segue sulla
    // prima icona (decisione 18) invece di restare sulla pagina: la riga rinasce in
    // un'altra sezione dopo la rilettura, e jsdom non vede dove il browser mette il fuoco.
    // L'abbinamento si scrive sulla voce e basta (S19), niente alias: la pulizia qui
    // sotto la archivia come le altre
    await page.getByRole("button", { name: `Abbina: ${libera}`, exact: true }).click();
    await page.getByRole("textbox", { name: `Abbina un ingrediente per ${libera}` }).fill("farina");
    await page.getByRole("option", { name: "Farina", exact: true }).click();
    await expect(
      page.getByRole("region", { name: "Cereali" }).getByText(libera, { exact: true })
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: `Codice a barre per ${libera}`, exact: true })
    ).toBeFocused();
  } finally {
    // pulizia in un `finally`, come la prova della barra della lista: ogni PATCH è un
    // `expect.soft` — non lancia, quindi non salta le altre voci, ma segna la prova
    // fallita, così una voce rimasta in lista non passa per un successo silenzioso
    for (const id of create) {
      try {
        const risposta = await page.request.patch(`/api/v1/shopping-list/${id}`, {
          data: { status: "archived" },
        });
        expect.soft(risposta.ok(), `pulizia: la voce ${id} non si è archiviata`).toBe(true);
      } catch (guasto) {
        expect.soft(false, `pulizia: non sono riuscito ad archiviare la voce ${id} (${guasto})`).toBe(true);
      }
    }
  }
});

test("i suggerimenti sotto la barra della lista scorrono nel loro elenco, dentro la finestra", async ({
  page,
}) => {
  // T3 Consegna 2, «Restano aperti»: l'elenco non aveva un'altezza massima, e su uno
  // schermo basso con la tastiera aperta gli ultimi suggerimenti chiedevano di scorrere
  // la pagina. Dodici suggerimenti li dà `page.route`: l'anagrafica del seme non ne ha
  // dodici che somiglino alla stessa parola, e lo schermo, il componente e il CSS sono
  // quelli veri. Niente si scrive, quindi niente da pulire.
  //
  // il `beforeEach` tocca «Entra» ma non aspetta la risposta: senza quest'attesa la
  // navigazione qui sotto può partire prima che il cookie di sessione sia scritto
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  const suggerimenti = Array.from({ length: 12 }, (_, i) => ({
    id: `00000000-0000-4000-8000-${String(i + 1).padStart(12, "0")}`,
    name: `prova suggerimento ${i + 1}`,
    display_name: `Prova suggerimento ${i + 1}`,
    category: "altro",
    kind: "food" as const,
  })) satisfies Ingredient[];
  await page.route("**/api/v1/ingredients/search?**", (route) =>
    route.fulfill({ json: suggerimenti })
  );

  // 375×812 è un telefono con la tastiera chiusa; 375×450 uno con la tastiera aperta,
  // che accorcia la finestra: `45dvh` deve seguirla
  for (const altezza of [812, 450]) {
    await page.setViewportSize({ width: 375, height: altezza });
    await page.goto("/lista");
    await page.getByLabel("Aggiungi alla lista", { exact: true }).fill("prova");
    const elenco = page.getByRole("listbox", { name: "Suggerimenti: Aggiungi alla lista" });
    await expect(elenco.getByRole("option")).toHaveCount(12);

    const scatola = await elenco.boundingBox();
    expect(
      scatola!.y + scatola!.height,
      `a 375×${altezza} l'elenco dei suggerimenti esce dalla finestra`
    ).toBeLessThanOrEqual(altezza);
    expect(
      await elenco.evaluate((el) => el.scrollHeight - el.clientHeight),
      `a 375×${altezza} l'elenco non scorre da sé`
    ).toBeGreaterThan(0);

    // l'ultimo si raggiunge scorrendo l'elenco
    await elenco.hover();
    await page.mouse.wheel(0, 2000);
    await expect.poll(() => elenco.evaluate((el) => el.scrollTop)).toBeGreaterThan(0);
    await expect(elenco.getByRole("option", { name: "Prova suggerimento 12" })).toBeInViewport();
  }
});

test("dopo una ✕ fallita in lista il fuoco resta sulla ✕", async ({ page }) => {
  // T3 Consegna 2, «Restano aperti»: la ✕ si spegneva con `disabled` mentre la PATCH era
  // in volo, e il browser toglie il fuoco a un pulsante che diventa `disabled` — chi
  // usa la tastiera lo ritrovava sulla pagina. jsdom non lo fa, quindi lo vede solo un
  // browser. La PATCH la fa fallire `page.route`, dopo un'attesa che lascia vedere la ✕
  // in volo; la voce la crea l'API e la toglie il `finally` (`page.request` non passa
  // da `page.route`).
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  const creata = await page.request.post("/api/v1/shopping-list", {
    data: { raw_text: "prova fuoco", ingredient_id: null },
  });
  expect(creata.ok()).toBe(true);
  const id = ((await creata.json()) as { id: string }).id;
  const rotta = `**/api/v1/shopping-list/${id}`;
  try {
    await page.route(rotta, async (route) => {
      if (route.request().method() !== "PATCH") return route.continue();
      await new Promise((resolve) => setTimeout(resolve, 1000));
      return route.fulfill({ status: 500, json: { detail: "guasto di prova" } });
    });
    await page.goto("/lista");
    const togli = page.getByRole("button", { name: "Togli prova fuoco dalla lista" });
    await togli.focus();
    await page.keyboard.press("Enter");

    // in volo: spenta, ma col fuoco
    await expect(togli).toHaveAttribute("aria-disabled", "true");
    await expect(togli).toBeFocused();
    // fallita: il messaggio nella riga, la ✕ di nuovo attiva, e il fuoco ancora lì
    const riga = page.getByRole("listitem").filter({ has: togli });
    await expect(riga.getByRole("alert")).toBeVisible();
    await expect(togli).not.toHaveAttribute("aria-disabled", "true");
    await expect(togli).toBeFocused();
  } finally {
    await page.unroute(rotta);
    try {
      const risposta = await page.request.patch(`/api/v1/shopping-list/${id}`, {
        data: { status: "archived" },
      });
      expect.soft(risposta.ok(), `pulizia: la voce ${id} non si è archiviata`).toBe(true);
    } catch (guasto) {
      expect.soft(false, `pulizia: non sono riuscito ad archiviare la voce ${id} (${guasto})`).toBe(true);
    }
  }
});

test("l'accesso a 375px: il fuoco nel campo, «Entra» non ancora col suo perché, l'Invio che non manda niente, l'occhio", async ({
  page,
}) => {
  // T3 Consegna 6a. Il `beforeEach` è entrato: si esce buttando il cookie, come in
  // `perOgniLuogo`, e la prima richiesta senza sessione riporta all'accesso. Prima si
  // aspetta che l'accesso del `beforeEach` sia finito, o il suo cookie arriverebbe dopo
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  await page.context().clearCookies();
  const accessi: string[] = [];
  page.on("request", (richiesta) => {
    if (richiesta.url().includes("/api/v1/auth/login")) accessi.push(richiesta.method());
  });
  await page.goto("/");

  const campo = page.getByLabel("Password", { exact: true });
  const entra = page.getByRole("button", { name: "Entra", exact: true });

  // 1. il campo prende il fuoco appena compare
  await expect(campo).toBeFocused();

  // 2. a campo vuoto «Entra» non ancora: spento senza `disabled`, col perché collegato,
  // e un bersaglio da pollice
  await expect(entra).toHaveAttribute("aria-disabled", "true");
  await expect(entra).not.toHaveAttribute("disabled");
  await expect(entra).toHaveAccessibleDescription("Scrivi la password per entrare.");
  expect((await entra.boundingBox())!.height).toBeGreaterThanOrEqual(44);

  // 3. l'Invio nel campo vuoto: l'invio implicito del browser passa da un clic su
  // «Entra», che si rifiuta
  await campo.press("Enter");
  // 4. «Entra» si raggiunge e tiene il fuoco, premuto da tastiera: un `disabled` non si
  // raggiungerebbe, e spegnendosi lo butterebbe sulla pagina. Tastiera e non `click()`:
  // Playwright non clicca un elemento `aria-disabled` (vedi le Global Constraints del piano)
  await entra.focus();
  await expect(entra).toBeFocused();
  await page.keyboard.press("Enter");
  await page.keyboard.press("Space");
  await expect(entra).toBeFocused();
  await expect(campo).toBeVisible();
  // un'attesa breve e dichiarata: si prova che una richiesta *non* parte, e non c'è un
  // evento da aspettare al suo posto
  await page.waitForTimeout(500);
  expect(accessi, "a campo vuoto è partito un accesso").toEqual([]);

  // 5. l'occhio: un bersaglio da pollice che mostra e rinasconde la password; il nome
  // resta fisso, `aria-pressed` dice se è premuto, e il fuoco resta lì
  await campo.fill("prova occhio");
  await expect(entra).not.toHaveAttribute("aria-disabled", "true");
  const mostra = page.getByRole("button", { name: "Mostra password", exact: true });
  const occhio = await mostra.boundingBox();
  expect(occhio!.width).toBeGreaterThanOrEqual(44);
  expect(occhio!.height).toBeGreaterThanOrEqual(44);
  await expect(mostra).toHaveAttribute("aria-pressed", "false");
  await expect(campo).toHaveAttribute("type", "password");
  await mostra.click();
  await expect(mostra).toHaveAttribute("aria-pressed", "true");
  await expect(mostra).toBeFocused();
  await expect(campo).toHaveAttribute("type", "text");
  await mostra.click();
  await expect(campo).toHaveAttribute("type", "password");

  // 6. «Password errata» se ne va alla prima battuta
  await campo.fill("sbagliata e2e");
  await campo.press("Enter");
  await expect(page.getByText("Password errata", { exact: true })).toBeVisible();
  await campo.press("x");
  await expect(page.getByText("Password errata", { exact: true })).toHaveCount(0);
  expect(accessi, "è partito un accesso che non doveva").toEqual(["POST"]);

  // 7. niente scorre di lato (stringhe e non funzioni: questo file non ha la libreria DOM)
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
  expect(scrollWidth, "l'accesso scorre di lato").toBeLessThanOrEqual(clientWidth);
});

test("le correzioni dell'anagrafica a 375px: icone da pollice accanto al titolo, su una riga, e niente scorre di lato", async ({
  page,
}) => {
  // T3 Consegna 6a. Un prodotto col codice, perché la scheda mostri anche «Togli il
  // codice», sotto un ingrediente del seme; il nome lungo è il caso che stringe il titolo
  // accanto alle icone. Si toglie nel `finally`.
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  const trovate = (await (
    await page.request.get("/api/v1/ingredients/search?q=farina")
  ).json()) as { id: string; name: string }[];
  const farina = trovate.find((voce) => voce.name === "farina");
  expect(farina, "«farina» non è nel seme").toBeDefined();
  const nome = `Farina di grano tenero tipo 00 macinata a pietra e2e ${Date.now()}`;
  const creato = await page.request.post("/api/v1/products", {
    data: { ingredient_id: farina!.id, name: nome, barcode: String(Date.now()) },
  });
  expect(creato.ok()).toBe(true);
  const prodottoId = ((await creato.json()) as { id: string }).id;

  try {
    const casi = [
      {
        indirizzo: `/anagrafica/ingrediente/${farina!.id}`,
        gruppo: "Correzioni dell'ingrediente",
        nomi: ["Rinomina", "Cambia reparto", "Unisci a un altro…"],
      },
      {
        indirizzo: `/anagrafica/prodotto/${prodottoId}`,
        gruppo: "Correzioni del prodotto",
        nomi: ["Spostalo", "Togli il codice"],
      },
    ];
    for (const caso of casi) {
      await page.goto(caso.indirizzo);
      const gruppo = page.getByRole("toolbar", { name: caso.gruppo });
      await expect(gruppo).toBeVisible();
      await page.waitForLoadState("networkidle");

      const scatole: { x: number; y: number; width: number; height: number }[] = [];
      for (const nomePulsante of caso.nomi) {
        const scatola = await gruppo.getByRole("button", { name: nomePulsante, exact: true }).boundingBox();
        expect(scatola, `${caso.gruppo}: ${nomePulsante}`).not.toBeNull();
        expect(scatola!.width, nomePulsante).toBeGreaterThanOrEqual(44);
        expect(scatola!.height, nomePulsante).toBeGreaterThanOrEqual(44);
        scatole.push(scatola!);
      }
      for (const scatola of scatole.slice(1)) {
        expect(Math.abs(scatola.y - scatole[0].y), `${caso.gruppo}: le icone vanno a capo`).toBeLessThan(1);
      }
      // accanto al titolo: le icone cominciano nella fascia del titolo, non sotto
      const titolo = await page.getByRole("heading", { level: 1 }).boundingBox();
      expect(scatole[0].y, `${caso.gruppo}: le icone non stanno accanto al titolo`).toBeLessThan(
        titolo!.y + titolo!.height
      );
      const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
      const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
      expect(scrollWidth, `${caso.indirizzo} scorre di lato`).toBeLessThanOrEqual(clientWidth);
    }

    // e il campo dell'Anagrafica ha il nome nuovo, che si vede
    await page.goto("/anagrafica");
    await expect(page.getByText("Cerca un ingrediente o un prodotto", { exact: true })).toBeVisible();
    await page.getByLabel("Cerca un ingrediente o un prodotto", { exact: true }).fill(nome);
    await expect(page.getByRole("link", { name: new RegExp(nome) })).toBeVisible();
  } finally {
    // `expect.soft`: non lancia (un `finally` che lancia nasconderebbe l'errore vero del
    // `try`) ma segna la prova fallita, così un prodotto rimasto non passa per un successo
    try {
      const risposta = await page.request.delete(`/api/v1/products/${prodottoId}`);
      expect.soft(risposta.ok(), `pulizia: il prodotto ${prodottoId} non si è eliminato`).toBe(true);
    } catch (guasto) {
      expect
        .soft(false, `pulizia: non sono riuscito a eliminare il prodotto ${prodottoId} (${guasto})`)
        .toBe(true);
    }
  }
});
