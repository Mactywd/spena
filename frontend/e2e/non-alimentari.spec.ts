import { test, expect } from "@playwright/test";

// Il giro che questa funzione esiste per rendere possibile, sull'app costruita e
// servita da Nginx contro il backend vero: il detersivo entra in lista, va in
// dispensa, finisce, e torna in lista. Gira dopo cooking.spec.ts (workers: 1,
// ordine alfabetico), che pretende una lista vuota: il nome del file non è
// decorativo.
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

test("un detersivo fa il giro: lista, dispensa, e ritorno in lista", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();

  // 1. lo scelgo dall'autocomplete: c'è perché il seme lo porta
  await page.getByLabel("Aggiungi alla lista").fill("detersivo per i p");
  await page.getByRole("option", { name: /Detersivo per i piatti/ }).click();
  const voce = page.getByRole("checkbox", { name: "detersivo per i piatti" });
  await expect(voce).toBeVisible();

  // 2. lo spunto e lo sistemo in dispensa come sfuso
  await voce.click();
  await expect(voce).toBeChecked();
  await page.getByRole("link", { name: "Sistema la spesa" }).click();
  await page.getByRole("button", { name: /Sfuso.*detersivo per i piatti/i }).click();
  await page.getByRole("button", { name: "Metti in dispensa", exact: true }).click();

  // 3. in dispensa sta nel suo reparto, non fra il cibo. `page.getByText("casa")`
  // farebbe corrispondenza su tutta la pagina — "casa" è una parola corta, e con
  // dispensa vuota compare anche nel testo di cortesia "...quello che hai in
  // casa.": qui non è quel caso (la dispensa non è vuota), ma il controllo
  // ancorato alla riga del detersivo non dipende da quella coincidenza. Stesso
  // schema di style.spec.ts:126, che risale da un elemento della riga al suo
  // contenitore invece di cercare nella pagina intera.
  //
  // `exact: true` sul link di navigazione non è decorativo: misurato a
  // schermo vero, col ricettario che mostra tutte le 26 ricette del seme, la
  // scheda «Pasta e ceci» porta nel proprio nome accessibile la sua
  // descrizione intera — "...da credenza della dispensa..." — e senza
  // `exact` il link di navigazione «Dispensa» (sottostringa, maiuscole a
  // parte) trova anche quella scheda: due elementi, errore di strict mode.
  // Qui il ricettario non è ancora a video, ma lo sarà al passo 6: lo stesso
  // `exact` va tenuto ovunque in questo file per non riaprire la stessa crepa.
  await page.getByRole("link", { name: "Dispensa", exact: true }).click();
  const riga = page.locator("li", { hasText: "detersivo per i piatti" });
  const sezione = riga.locator("xpath=ancestor::section[1]");
  await expect(sezione.getByText("casa", { exact: true })).toBeVisible();

  // 4. lo porto a zero e la domanda del rientro arriva
  const cursore = page.getByRole("slider", { name: "Quanto ne resta di detersivo per i piatti" });
  await cursore.fill("0");
  await cursore.dispatchEvent("pointerup");
  await expect(page.getByText("Lo rimetto in lista?")).toBeVisible();
  await page.getByRole("button", { name: "Sì" }).click();
  await expect(page.getByText("Rimesso in lista.")).toBeVisible();

  // 5. nel ricettario invece non esiste: il filtro per ingrediente (kind=food)
  // non lo offre. Un conteggio a zero da solo non proverebbe niente — passerebbe
  // uguale se il campo non cercasse affatto, per esempio perché il debounce non
  // fosse mai scattato (lo stesso punto cieco già corretto una volta nel Task 7).
  // Per questo l'assenza si lega alla risposta VERA della ricerca (non a un
  // timeout a occhio) e si prova anche il positivo, nello stesso campo, con un
  // ingrediente alimentare del seme: solo se quello compare l'assenza del
  // detersivo dice quel che dichiara di dire.
  //
  // La garanzia vera sta nel CORPO della risposta, non nel conteggio a video:
  // `toHaveCount(0)` riprova solo finché fallisce, quindi se al primo sguardo
  // il DOM è già a zero passa comunque — e c'è una finestra, stretta ma vera,
  // fra la risoluzione di `waitForResponse` (evento di rete, CDP) e il commit
  // di React che segue la promise dentro la pagina, in cui il DOM non ha
  // ancora reso niente. In più `OptionList` monta la `<ul>` solo quando
  // `found.length > 0` e la query non ha `placeholderData`, quindi `found`
  // torna `[]` a ogni cambio di chiave finché la risposta non arriva: in una
  // ipotetica regressione del filtro per reparto il conteggio a video
  // partirebbe comunque da zero, e una lettura caduta in quella finestra
  // passerebbe lo stesso. Il JSON che il server risponde non ha questa corsa:
  // prova che il server esclude. L'asserzione sul DOM resta sotto e prova la
  // cosa diversa e utile che le compete: che a schermo non compare.
  await page.getByRole("link", { name: "Ricette", exact: true }).click();
  const filtro = page.getByLabel("Contiene ingredienti");

  const rispostaDetersivo = page.waitForResponse(
    (res) => res.url().includes("/ingredients/search") && res.url().includes("q=detersivo")
  );
  await filtro.fill("detersivo");
  const risposta = await rispostaDetersivo;
  expect(await risposta.json()).toEqual([]);
  await expect(page.getByRole("option", { name: /Detersivo/ })).toHaveCount(0);

  const rispostaPomodoro = page.waitForResponse(
    (res) => res.url().includes("/ingredients/search") && res.url().includes("q=pomodoro")
  );
  await filtro.fill("pomodoro");
  await rispostaPomodoro;
  await expect(page.getByRole("option", { name: /Pomodoro/ })).toBeVisible();

  // 6. la pulizia, che non è un contorno: la dispensa e la lista sono stato
  // condiviso con gli altri file, e cooking.spec.ts pretende una lista vuota.
  // La X archivia davvero sul server — la lapide che resta a video è solo la
  // finestra dell'annulla.
  await page.getByRole("link", { name: "Dispensa", exact: true }).click();
  await page
    .getByRole("button", { name: "Togli detersivo per i piatti dalla dispensa" })
    .click();
  await expect(page.getByText("Tolta dalla dispensa")).toBeVisible();

  await page.getByRole("link", { name: "Lista", exact: true }).click();
  await page
    .getByRole("button", { name: "Togli detersivo per i piatti dalla lista" })
    .click();
  // Non "Lista vuota.": misurato a schermo vero, `cooking.spec.ts` lascia di
  // proposito un pomodoro non spuntato in lista alla fine del proprio giro
  // (è la prova che il rientro automatico funziona, e resta commentato così
  // nel suo file) — quella riga sopravvive per il resto della corsa della
  // suite. Una prima stesura di questa asserzione dava per scontata una lista
  // vuota e falliva sempre qui, con "elemento non trovato", non perché la
  // pulizia del detersivo fosse incompleta ma perché l'assunzione lo era. La
  // prova che appartiene a questo file è che IL DETERSIVO sia sparito, non
  // che la lista lo sia: quella verità appartiene a `cooking.spec.ts`, che la
  // controlla già da sé al proprio avvio.
  await expect(page.getByRole("checkbox", { name: "detersivo per i piatti" })).toHaveCount(0);
});
