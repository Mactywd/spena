# Le rifiniture della Dispensa e di «Sistema la spesa»: gli esiti che nessuno dice, il fuoco nella serie, il reparto chiuso che tace un errore, i campi che si spengono, la barra delle confezioni — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** cinque idee P3 dell'ingresso diretto e della Dispensa, nessuna un vicolo cieco ma tutte silenzi:
- chiuso il pannello mentre «Metti in dispensa» è in volo, una scrittura fallita lo dice un avviso, con «Riprova»;
- una confezione in più lasciata senza scelta dice che così non entra;
- un codice non letto il cui esito arriva dopo «Annulla» non resta ricordato;
- nella serie della scansione, dopo «Metti in dispensa» il fuoco va al titolo dello scanner invece di cadere sul `body`;
- il titolo di un reparto chiuso dice che una modifica di una sua riga non è stata salvata;
- il nome in «Rinomina», il reparto in «Cambia reparto» e il campo data della riga non si spengono più con `disabled` nativo; la scadenza esce da `PantryRow.tsx` in `ExpiryLine.tsx`;
- la barra delle tre icone e «Cambia» è un pezzo solo, usato dalla riga della voce e da quella della confezione in più.

**Architecture:**
- **L'errore a pannello chiuso.** `DirectEntry` sa se è ancora montato (un ref, come `alive` di `ProductResolver`). L'`onError` nelle opzioni della mutazione, che react-query chiama anche a componente smontato, passa la scelta a chi lo ospita (`onLost`) solo se il pannello non c'è più. A pannello aperto l'errore resta quello della scheda, come oggi. `PantryScreen` alza l'avviso e, con «Riprova», rifà la stessa scrittura. Il corpo della scrittura si costruisce in un posto solo (`entryBody`), usato da tutti e due.
- **Il codice ricordato.** È `ProductResolver` che decide quando un esito tardivo vale (`isOpen`). Oggi `onUnlinkedCode` dello scanner passa dritto a `onRememberCode`, senza quella guardia. La guardia si mette lì: una copia sola, e vale per la Dispensa e per «Sistema la spesa».
- **Il fuoco.** `ScannerPanel` impara `takeFocus`: appena montato, se il fuoco è caduto sul `body`, lo porta al suo titolo (`h2` con `tabIndex={-1}`). `ProductResolver` lo inoltra (`focusScanner`), e solo `DirectEntry` lo accende. In «Sistema la spesa» il fuoco resta quello di oggi.
- **Il reparto chiuso.** `attentionCounts` conta anche le righe con una modifica rifiutata (`failedIds`, che `PantryScreen` ha già). `attentionNote` la scrive per prima, in `text-danger`.
- **I campi.** `readOnly` più `aria-disabled` dove c'era `disabled`, come `IngredientPicker`. Il `<select>` non ha `readOnly`: ignora il cambio, come la casella di `ChangeCard`.
- **La barra.** `ResolutionButtons` (`frontend/src/features/stocking/`) ha le tre icone o «Cambia», con l'attributo del fuoco che ognuna delle due righe usa (`data-trigger` o `data-package-trigger`). «Abbina» resta in `StockingRow`.

**Tech Stack:** React 19, TanStack Query 5, Vitest + Testing Library, Playwright. Solo frontend.

**Spec:** le idee P3 di `next-steps.md` «Ingresso diretto, tre esiti che nessuno dice» [S3], «Nella serie della scansione, dopo «Metti in dispensa» lo scanner si rimonta…» [S3], «Un errore su una riga di un reparto chiuso…» [S15], «Campi che si spengono con `disabled` nativo…» [T3, Parte X], «La riga di una confezione in più (`PackageRow`) ripete la barra…» [S3]. Il ragionamento in `docs/prossimi-passi.md` §S3 e §S15. La bozza dell'ingresso diretto `docs/superpowers/specs/2026-10-06-ingresso-diretto-bozza.md`, quella dei reparti `docs/superpowers/specs/2026-10-06-reparti-collassabili-bozza.md`. Le regole a video: `docs/superpowers/specs/2026-09-28-ridisegno-design.md`.

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/dispensa-rifiniture`, ramo `night/dispensa-rifiniture`, creato **da `night/frontend-annulla-e-test`** e non da `master`. Quel piano cambia gli stessi `DirectEntry.tsx` e `PantryScreen.tsx` (la nota dopo «Annulla», `undoneItemIds`) e forse `NoticeProvider` (`durationMs`). Questo ramo si fa dopo, e si unisce dopo. Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì. **Nessun push, nessun merge, nessun deploy. Mai `git stash`. Niente letture o scritture sulla produzione, e mai il `.env` del checkout principale.**
- **Il carico sulla macchina**: al massimo 6 thread e 8 GB (Mattia, 2026-11-22). Ogni corsa più grande di un file gira dentro `systemd-run --user --scope -p MemoryMax=8G -p CPUQuota=600% …`, mai due suite intere insieme. Vitest gira con `--maxWorkers=4` (un file solo: `--maxWorkers=1`).
- **Il type check è `npm run typecheck`**, mai `tsc --noEmit`. Controlli, da `<worktree>/frontend`: `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`. Nei test dei componenti si usa `createTestQueryClient`.
- **Le prove che toccano un pulsante dell'avviso** («Riprova», «Annulla») montano `NoticeProvider` con `durationMs={60_000}`, se il ramo di partenza gliel'ha dato (`grep -n "durationMs" frontend/src/components/ui/NoticeProvider.tsx`). Se non c'è, si scrivono come le altre prove del file, e il report lo dice.
- **Colore**: solo i token di `frontend/src/index.css`, **nessun token nuovo**. Le coppie nuove a video sono `danger` su `card` e `ink-soft` su `card`, già in `src/theme.test.ts`. `grep -rn "emerald\|neutral-" frontend/src` resta vuoto. Ogni testo sta sopra 4,5:1 nei due temi, bersagli alti almeno 44 px, e a 375 px niente scorre di lato.
- **Mai `disabled` nativo su un controllo che salva**: `busy`, `aria-disabled`, `readOnly`, come le pulizie del 2026-10-13.
- Le parole a video **si copiano esatte** da questo piano (fra «»). Gli identificatori in inglese, i commenti in italiano.
- **I test di oggi si cambiano solo dove il piano lo dice**: nel Task 3 nessuno, perché l'estrazione non cambia un nome accessibile.
- **e2e** sullo stack `spena-e2e`, con i comandi delle Global Constraints di `docs/superpowers/plans/2026-11-18-pasti-correzioni.md`: il `.env` copiato da `.env.example` e cancellato alla fine, `-p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml` in ogni comando, il seme con le ricette e le due righe della fixture CIQUAL, e sempre `down -v` e `rm .env`.
- Nessuna dipendenza nuova. Il backend non si tocca.

## Review Focus

1. **Il pannello chiuso con la ✕ mentre «Metti in dispensa» è in volo, poi la scrittura fallisce**: compare l'avviso «Non sono riuscito a mettere ‹voce› in dispensa.» con «Riprova». A pannello aperto niente avviso: lo dice la scheda, come oggi. Task 1.
2. **«Riprova» dell'avviso che riesce**: il corpo è lo stesso della prima volta (scadenza e codice compresi), e poi tutto va come un ingresso riuscito: la riga in vista e l'avviso «In dispensa: …» con «Annulla». Task 1.
3. **Un codice non letto il cui esito arriva dopo «Annulla», poi «Cerca a catalogo» dalla stessa scheda**: il prodotto scelto entra senza quel codice (`barcode: null`). Task 2.
4. **Il fuoco dopo «Metti in dispensa» nella serie** va al titolo «Codice a barre». In «Sistema la spesa» torna, come oggi, al pulsante che ha aperto il pannello: i test di oggi di `StockingScreen.test.tsx` passano senza cambiare. Task 5.
5. **Un reparto chiuso con una tacca rifiutata** dice «1 modifica non salvata» nel titolo. La nota sparisce quando la modifica dopo riesce. Task 6.

### Preparazione (una volta, prima del Task 1)

- [ ] **Il ramo di partenza c'è ed è finito.** Da `/home/mactyws/coding/ais/spena`:
  ```bash
  git rev-parse --verify night/frontend-annulla-e-test
  git log --format=%s master..night/frontend-annulla-e-test | grep -F "dispensa: dopo «Annulla»"
  git show night/frontend-annulla-e-test:frontend/src/features/pantry/DirectEntry.tsx | grep -c undoneItemIds
  ```
  Poi leggi il report di quella notte (`docs/night-reports/`, sul checkout principale o sul ramo): la voce della nota dopo «Annulla» non deve essere `bloccato`. Se un comando non trova niente, o il report la dice bloccata, **fermati**. Nel report scrivi «dispensa-rifiniture non partito: attende night/frontend-annulla-e-test», e le voci di questo piano restano `pronto`. Che la voce del test sotto carico (Task 2 di quel piano) sia bloccata non ferma questo piano.
- [ ] Il worktree, con `node_modules` collegato e nessun `.env`:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/dispensa-rifiniture -b night/dispensa-rifiniture night/frontend-annulla-e-test
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/dispensa-rifiniture/frontend/node_modules
  ```
- [ ] Le cinque voci di `next-steps.md` che citano questo piano passano a `in corso` (` → in corso su night/dispensa-rifiniture`), e si committa: `next-steps: le rifiniture della Dispensa, in corso`.
- [ ] La linea di partenza: `npx vitest run --maxWorkers=4` dal worktree, tutto verde. **Annota** i numeri. Se non è verde, fermati e scrivilo nel report.

---

## Decisioni prese

1. **L'errore a pannello chiuso è un avviso con «Riprova»** (Claude, su delega). L'avviso dice «Non sono riuscito a mettere ‹etichetta› in dispensa.», con l'etichetta di `entryLabel`, la stessa dell'avviso «In dispensa: …». È la forma degli altri due avvisi d'errore della Dispensa («Non sono riuscito a togliere … dalla dispensa.», «Non sono riuscito a rimettere … in dispensa.»), che hanno tutti «Riprova». «Riprova» rimanda lo stesso `POST /pantry`. Se riesce, si va come un ingresso riuscito (`afterEntry`). Se fallisce ancora, torna lo stesso avviso.
2. **Chi sa che il pannello non c'è più è `DirectEntry`**, con un ref acceso nell'effetto di montaggio e spento nella pulizia. Vale per ogni chiusura: la ✕, «Annulla» della scheda dal +, «Annulla» dello scanner nella scansione, e un pannello riaperto (un'istanza nuova, con la sua `key`). Il ref è vero mentre il pannello è aperto: lì l'`onError` non chiama `onLost`, e l'errore lo dice la scheda (`failed`).
3. **Il corpo della scrittura in un posto solo**: `entryBody(choice: EntryChoice, expiresOn: string | null)` in `entryView.ts`, che rende l'argomento di `addPantryItem`. Lo usano la `mutationFn` di `DirectEntry` e il «Riprova» di `PantryScreen`. Due copie si scollerebbero sulla regola del codice («solo un prodotto scelto a catalogo dopo un codice letto lo porta», S8).
4. **Il «Riprova» legge l'`afterEntry` di adesso** (Claude, su delega). L'`onError` di una mutazione smontata chiama la `onLost` del render in cui si è premuto «Metti in dispensa». Per questo `PantryScreen` tiene `afterEntry` in un ref aggiornato in un effetto, e il «Riprova» chiama `afterEntryRef.current`. Così l'avviso e la riga in vista usano lo stato di quando si tocca «Riprova», non quello di quando il pannello era aperto.
5. **La confezione senza scelta lo dice nella sua riga** (Claude, su delega). Sotto «Confezione N», dove una confezione scelta ha la sua `ResolutionNote`, una riga dice «Senza una scelta non entra in dispensa.», in `text-xs text-ink-soft`. La riga c'è solo finché non si sceglie. «Metti in dispensa» non cambia: conta e manda le confezioni scelte, come oggi. La voce stessa senza scelta non ne ha bisogno, perché resta in lista e l'avviso lo dice già («… restano in lista»).
6. **La guardia del codice sta in `ProductResolver`**: `onUnlinkedCode={(code) => { if (isOpen(step)) onRememberCode(code); }}`. Vale per tutti e due gli esiti dello scanner che passano di lì: l'errore del lookup, che ricorda il codice, e il successo, che lo dimentica (`null`). Uno scanner chiuso non cambia più niente di quel che ricorda chi lo ospita.
7. **Il fuoco va al titolo dello scanner, non al campo del codice** (Claude, su delega: la voce suggeriva il campo). Sul telefono un campo che prende il fuoco può aprire la tastiera numerica sopra la fotocamera, proprio nella serie che deve essere veloce. Il titolo «Codice a barre» (`h2`, `tabIndex={-1}`) riporta chi usa la tastiera o lo screen reader nel pannello giusto, e il campo è il controllo dopo. Il fuoco si prende **solo se è caduto sul `body`** (`document.activeElement` nullo o `body`), come `useReturnFocus`: al primo giro, se «Scansiona» ha ancora il fuoco, resta lì. Per questo `DirectEntry` passa `focusScanner` sempre, e «dal secondo giro» lo decide la guardia. Il contorno del fuoco è quello di base, nessuna classe nuova.
8. **In «Sistema la spesa» lo scanner non prende il fuoco** (`takeFocus` spento). Lì `useReturnFocus` della riga rimette il fuoco al pulsante che ha aperto il pannello. Gli effetti dei figli girano prima di quelli dei padri, quindi uno scanner che lo prendesse lo ruberebbe alla riga.
9. **La nota del reparto chiuso** (Claude, su delega): «1 modifica non salvata» o «N modifiche non salvate», prima di finiti e in scadenza, separata da « · », in `font-medium text-danger`. «Modifica» è la parola dell'`Alert` della riga («Non sono riuscito a salvare la modifica. Riprova.»). Il reparto non si apre da solo: lo dice il titolo, e si apre toccandolo. La nota sparisce con `clearFailed`, cioè alla modifica dopo, come l'`Alert`.
10. **I campi senza `disabled`.** Il nome di `RenameForm` e il campo data di `ExpiryLine` hanno `readOnly` e `aria-disabled` mentre salvano, con `aria-disabled:text-ink-faint`, come `IngredientPicker`. `CategorySelect` con `disabled` ha `aria-disabled` e ignora il cambio: il valore controllato resta quello di prima. Nota per chi rivede: in «Rinomina» e «Cambia reparto» il salvataggio parte dal pulsante, che ha il fuoco. Lì il difetto si vede solo a chi è nel campo mentre si salva, per esempio con uno screen reader, ma la regola è una per tutti i controlli. Nel campo data della riga il fuoco è dentro il campo.
11. **`ExpiryLine` porta con sé tutto della scadenza**: lo stato `editingExpiry`, i tre ref (`expiryButton`, `expiryCancelled`, `refocusExpiry`), l'effetto del fuoco, `commitExpiry`, `EXPIRY_TONE_TEXT` e i commenti. `PantryRow` gli passa `item`, `label`, `busy` e `onExpiry`. I test della scadenza restano in `PantryRow.test.tsx`: provano la riga vera, con dentro la `ExpiryLine` vera (prima lezione di `CLAUDE.md`).
12. **`ResolutionButtons` non sa di voci e confezioni** (Claude, su delega). Riceve la frase dei nomi accessibili (`name`: «mele», oppure «mele, confezione 2») e l'attributo del fuoco. I nomi accessibili restano identici a oggi.

## Margine di autonomia

- Liberi: i nomi interni e dei test, il nome del ref di montaggio, dove sta l'helper delle prove se ne serve uno.
- Fissi: `entryBody`, `onLost`, `takeFocus`, `focusScanner`, `ResolutionButtons`, `ExpiryLine`, `failedText`, le parole a video.
- **Fermati** (voce `bloccato` nel report) se l'`onError` nelle opzioni di `useMutation` non scatta a componente smontato, nella versione di react-query installata: è la premessa della decisione 2. Non sostituirlo con una chiamata nuda senza dirlo.

---

### Task 1: un ingresso fallito a pannello chiuso lo dice un avviso

**Files:**
- Modify: `frontend/src/features/pantry/entryView.ts` (`entryBody`)
- Modify: `frontend/src/features/pantry/DirectEntry.tsx` (il ref di montaggio, `onError`, la prop `onLost`, `mutationFn` con `entryBody`)
- Modify: `frontend/src/features/pantry/PantryScreen.tsx` (`lostEntry`, `retryEntry`, `afterEntryRef`, la prop a `DirectEntry`)
- Test: `frontend/src/features/pantry/entryView.test.ts`, `frontend/src/features/pantry/DirectEntry.test.tsx`, `frontend/src/features/pantry/PantryScreen.test.tsx`

**Interfaces:**
- Produces: `export function entryBody(choice: EntryChoice, expiresOn: string | null): Parameters<typeof addPantryItem>[0]`, cioè `{ ingredientId, productId, expiresOn, barcode }` con `barcode: (choice.product && choice.barcode) || null`.
- Produces: `DirectEntry` riceve `onLost: (choice: EntryChoice, expiresOn: string | null) => void`.

- [ ] **Step 1: I test che falliscono.**
  - `entryView.test.ts`, «il corpo dell'ingresso»: un prodotto con il codice letto lo porta; un prodotto senza codice manda `barcode: null`; uno sfuso manda `productId: null` e `barcode: null` anche se la scelta avesse un codice; `expiresOn` passa com'è.
  - `DirectEntry.test.tsx`, «chiuso il pannello mentre entra, un errore lo passa a chi ospita»: un contenitore di prova che smonta `DirectEntry` quando arriva `onClose`; dal + una voce sfusa con la scadenza scritta; il `POST /pantry` finto resta in sospeso; «Metti in dispensa», poi «Chiudi l'aggiunta»; il `POST` risponde 500. `onLost` è chiamato una volta, con la scelta e la data.
  - `DirectEntry.test.tsx`, «a pannello aperto l'errore lo dice la scheda»: lo stesso 500 senza chiudere. Si legge «Non sono riuscito ad aggiungere la voce in dispensa. Riprova.», e `onLost` non è chiamato.
  - `PantryScreen.test.tsx`, «un ingresso fallito a pannello chiuso lo dice l'avviso, e «Riprova» lo rimette»: il giro intero, con lo schermo e `NoticeProvider` veri. Dopo la ✕ e il 500 compare «Non sono riuscito a mettere Yogurt greco in dispensa.» (o l'etichetta della voce della fixture) con «Riprova». Toccato «Riprova», il secondo `POST /pantry` ha lo stesso corpo del primo e riesce, e compare l'avviso «In dispensa: …» con «Annulla».
- [ ] **Step 2: Falliscono**: `npx vitest run --maxWorkers=1 src/features/pantry/entryView.test.ts src/features/pantry/DirectEntry.test.tsx src/features/pantry/PantryScreen.test.tsx`.
- [ ] **Step 3: Il codice**, secondo le decisioni 1–4. In `DirectEntry`:
  ```ts
  // vero finché il pannello è a video: l'`onError` qui sotto arriva anche dopo, a
  // componente smontato, e allora la scheda che direbbe l'errore non c'è più
  const shown = useRef(false);
  useEffect(() => {
    shown.current = true;
    return () => {
      shown.current = false;
    };
  }, []);
  ```
  Poi `onError: (_error, { choice, expiresOn }) => { if (!shown.current) onLost(choice, expiresOn); }` nelle opzioni di `useMutation`, accanto all'`onSuccess` che c'è. In `PantryScreen`:
  ```ts
  function lostEntry(choice: EntryChoice, expiresOn: string | null) {
    notice({
      text: `Non sono riuscito a mettere ${entryLabel(choice)} in dispensa.`,
      action: { label: "Riprova", onClick: () => retryEntry(choice, expiresOn) },
    });
  }
  function retryEntry(choice: EntryChoice, expiresOn: string | null) {
    addPantryItem(entryBody(choice, expiresOn)).then(
      (created) => afterEntryRef.current(created, entryLabel(choice)),
      () => lostEntry(choice, expiresOn)
    );
  }
  ```
  È una chiamata col client dell'app e non una `useMutation`, per la stessa ragione di `undoEntry`: l'avviso è dell'app e si tocca anche altrove.
- [ ] **Step 4: Passano**, poi `npx vitest run --maxWorkers=4 src/features/pantry`.
- [ ] **Step 5: Commit**: `dispensa: un ingresso fallito a pannello chiuso lo dice un avviso, con «Riprova»`.

### Task 2: un codice letto dopo «Annulla» non resta ricordato

**Files:**
- Modify: `frontend/src/features/stocking/ProductResolver.tsx` (`onUnlinkedCode` dello scanner)
- Test: `frontend/src/features/stocking/ProductResolver.test.tsx`, `frontend/src/features/pantry/DirectEntry.test.tsx`

**Interfaces:**
- Consumes: `isOpen(step)` di `ProductResolver`.
- Produces: niente di nuovo; `onRememberCode` non è più chiamato da uno scanner chiuso.

- [ ] **Step 1: I test che falliscono.**
  - `ProductResolver.test.tsx`, «un codice non letto il cui esito arriva dopo «Annulla» non si ricorda»: sullo schema di «un esito arrivato dopo «Annulla» non risolve niente». Con l'ingrediente, il lookup in sospeso, «Annulla», poi il lookup fallisce (500). `onRememberCode` non è stato chiamato col codice.
  - `ProductResolver.test.tsx`, lo stesso con un lookup che risponde «nuovo al catalogo» dopo «Annulla»: `onRememberCode` non è chiamato neanche con `null`.
  - `DirectEntry.test.tsx`, «dopo «Annulla» il codice non segue il catalogo»: dal + una voce sfusa, il codice dalla scheda, un codice scritto con «Cerca» e il lookup in sospeso, «Annulla» (si torna alla scheda), il lookup fallisce, «Cerca a catalogo», si sceglie un prodotto, «Metti in dispensa». Il corpo del `POST /pantry` ha `barcode: null`.
- [ ] **Step 2: Falliscono**: `npx vitest run --maxWorkers=1 src/features/stocking/ProductResolver.test.tsx src/features/pantry/DirectEntry.test.tsx`.
- [ ] **Step 3: Il codice**, secondo la decisione 6. Un commento sopra la riga dice che è la stessa guardia dell'esito tardivo, e che prima mancava qui (idea P3 [S3]).
- [ ] **Step 4: Passano**, poi `npx vitest run --maxWorkers=4 src/features/stocking src/features/pantry`.
- [ ] **Step 5: Commit**: `dispensa: un codice letto dopo «Annulla» non resta ricordato`.

### Task 3: la barra delle tre icone, un pezzo solo

**Files:**
- Create: `frontend/src/features/stocking/ResolutionButtons.tsx`
- Modify: `frontend/src/features/stocking/StockingRow.tsx`, `frontend/src/features/stocking/PackageRow.tsx`
- Test: `frontend/src/features/stocking/ResolutionButtons.test.tsx`; `StockingRow.test.tsx`, `PackageRow.test.tsx` e `StockingScreen.test.tsx` passano **senza cambiare**

**Interfaces:**
- Produces:
  ```ts
  export function ResolutionButtons({
    name,
    resolution,
    triggerAttribute,
    onOpen,
    onLoose,
    onChange,
  }: {
    /** Di che cosa, nei nomi accessibili: «mele», o «mele, confezione 2». */
    name: string;
    resolution: Resolution | undefined;
    /** Dove `useReturnFocus` ritrova i pulsanti: la riga della voce e quella di una
     * confezione hanno due attributi, perché la seconda sta dentro la prima. */
    triggerAttribute: "data-trigger" | "data-package-trigger";
    onOpen: (trigger: "scanner" | "catalog") => void;
    onLoose: () => void;
    onChange: () => void;
  });
  ```
  Con `resolution`: lo `span` `[triggerAttribute]="change"` con «Cambia» (`Cambia la scelta per ${name}`). Senza: `IconToolbar` `Come entra in dispensa: ${name}`, con gli `span` `scanner` e `catalog` e il terzo pulsante «Sfuso, senza marca: ${name}». Sono le stesse classi e gli stessi nomi di oggi.

- [ ] **Step 1: Il test che fallisce.** `ResolutionButtons.test.tsx`: senza scelta, i tre pulsanti con i nomi di oggi, dentro `[data-package-trigger="scanner"]` e `[data-package-trigger="catalog"]` quando `triggerAttribute` è quello; con la scelta, solo «Cambia la scelta per mele», dentro `[data-trigger="change"]`.
- [ ] **Step 2: Fallisce**: `npx vitest run --maxWorkers=1 src/features/stocking/ResolutionButtons.test.tsx`.
- [ ] **Step 3: Il codice.** `StockingRow` usa `ResolutionButtons` nei due rami «scelta» e «con ingrediente», con `name` e `data-trigger`. Il ramo «Abbina» resta suo. `PackageRow` lo usa con `which` e `data-package-trigger`. Gli import che non servono più escono.
- [ ] **Step 4: Passano**, e con loro `StockingRow.test.tsx`, `PackageRow.test.tsx` e `StockingScreen.test.tsx` così come sono: `npx vitest run --maxWorkers=4 src/features/stocking`.
- [ ] **Step 5: Commit**: `sistema la spesa: le tre icone e «Cambia» in un pezzo solo`.

### Task 4: una confezione senza scelta dice che non entra

**Files:**
- Modify: `frontend/src/features/stocking/PackageRow.tsx`
- Test: `frontend/src/features/stocking/PackageRow.test.tsx`, `frontend/src/features/stocking/StockingScreen.test.tsx`

**Interfaces:**
- Consumes: `ResolutionButtons` (Task 3).

- [ ] **Step 1: I test che falliscono.**
  - `PackageRow.test.tsx`, «senza scelta dice che non entra»: senza `resolution` si legge «Senza una scelta non entra in dispensa.»; con una `resolution` sfusa non c'è, e c'è «Sfuso».
  - `StockingScreen.test.tsx`, «una confezione in più lasciata senza scelta lo dice, e non parte»: una voce risolta, «+ un'altra confezione», nessuna scelta. Sotto «Confezione 2» c'è la frase, il pulsante dice «Metti in dispensa 1», e il corpo della sistemazione ha una confezione sola.
- [ ] **Step 2: Falliscono**: `npx vitest run --maxWorkers=1 src/features/stocking/PackageRow.test.tsx src/features/stocking/StockingScreen.test.tsx`.
- [ ] **Step 3: Il codice**, secondo la decisione 5: `{resolution ? <ResolutionNote resolution={resolution} /> : <p className="text-xs text-ink-soft">Senza una scelta non entra in dispensa.</p>}`.
- [ ] **Step 4: Passano**, poi `npx vitest run --maxWorkers=4 src/features/stocking`.
- [ ] **Step 5: Commit**: `sistema la spesa: una confezione senza scelta dice che non entra`.

### Task 5: nella serie, il fuoco al titolo dello scanner

**Files:**
- Modify: `frontend/src/features/stocking/ScannerPanel.tsx` (`takeFocus`, il ref e il `tabIndex` dell'`h2`)
- Modify: `frontend/src/features/stocking/ProductResolver.tsx` (`focusScanner`)
- Modify: `frontend/src/features/pantry/DirectEntry.tsx` (passa `focusScanner`)
- Test: `frontend/src/features/stocking/ScannerPanel.test.tsx`, `frontend/src/features/pantry/DirectEntry.test.tsx`

**Interfaces:**
- Produces: `ScannerPanel({ …, takeFocus = false })`, con `takeFocus?: boolean`. `ProductResolver({ …, focusScanner = false })`, con `focusScanner?: boolean`, inoltrato a ogni `ScannerPanel` che monta (anche quelli di `backToScanner`).

- [ ] **Step 1: I test che falliscono.**
  - `ScannerPanel.test.tsx`, «con `takeFocus`, il fuoco caduto va al titolo»: col fuoco sul `body`, il titolo «Codice a barre» ha il fuoco (`toHaveFocus`).
  - «con `takeFocus`, un fuoco che sta altrove resta lì»: un pulsante fuori dal pannello ha il fuoco prima del render, e lo tiene.
  - «senza `takeFocus` non lo prende»: col fuoco sul `body`, il titolo non ce l'ha.
  - `DirectEntry.test.tsx`, «dopo «Metti in dispensa» il fuoco va al titolo dello scanner»: dalla scansione, un codice a catalogo, «Metti in dispensa» toccato col clic (che gli dà il fuoco), il `POST` riesce. Lo scanner del giro dopo ha il fuoco sul titolo.
- [ ] **Step 2: Falliscono**: `npx vitest run --maxWorkers=1 src/features/stocking/ScannerPanel.test.tsx src/features/pantry/DirectEntry.test.tsx`.
- [ ] **Step 3: Il codice**, secondo le decisioni 7 e 8:
  ```ts
  const title = useRef<HTMLHeadingElement>(null);
  // Nella serie della Dispensa lo scanner rinasce dopo «Metti in dispensa», e il
  // pulsante che aveva il fuoco è sparito con la scheda. Il titolo e non il campo:
  // sul telefono il campo aprirebbe la tastiera sopra la fotocamera
  useEffect(() => {
    if (!takeFocus) return;
    const lost = document.activeElement === null || document.activeElement === document.body;
    if (lost) title.current?.focus();
  }, [takeFocus]);
  ```
  Un effetto solo al montaggio: `takeFocus` non cambia durante la vita del pannello.
- [ ] **Step 4: Passano**, poi `npx vitest run --maxWorkers=4 src/features/stocking src/features/pantry`. `StockingScreen.test.tsx` è verde senza cambiare.
- [ ] **Step 5: Commit**: `dispensa: nella serie della scansione il fuoco torna al pannello`.

### Task 6: il reparto chiuso dice la modifica non salvata

**Files:**
- Modify: `frontend/src/features/pantry/pantryView.ts` (`attentionCounts` con `failedIds`, `failedText`)
- Modify: `frontend/src/features/pantry/PantryScreen.tsx` (`attentionNote(rows, failedIds)`)
- Test: `frontend/src/features/pantry/pantryView.test.ts`, `frontend/src/features/pantry/PantryScreen.test.tsx`

**Interfaces:**
- Produces: `attentionCounts(rows: PantryItem[], failedIds: ReadonlySet<string> = new Set()): { failed: number; finished: number; expiring: number }`. `failed` conta le righe del reparto in `failedIds`, e una riga finita e rifiutata conta in tutti e due. `failedText(count: number): string` rende «1 modifica non salvata» o «N modifiche non salvate».

- [ ] **Step 1: I test che falliscono.**
  - `pantryView.test.ts`: `attentionCounts` con e senza `failedIds` (le chiamate di oggi danno `failed: 0`); `failedText(1)` e `failedText(3)`.
  - `PantryScreen.test.tsx`, «un reparto chiuso dice la modifica non salvata»: il `PATCH` di una tacca in sospeso, il reparto chiuso dal suo titolo, il `PATCH` risponde 500. Il nome del pulsante del titolo contiene «1 modifica non salvata». Riaperto, la riga ha il suo `Alert`. Una tacca dopo che riesce toglie la nota (il reparto richiuso non la dice più).
- [ ] **Step 2: Falliscono**: `npx vitest run --maxWorkers=1 src/features/pantry/pantryView.test.ts src/features/pantry/PantryScreen.test.tsx`.
- [ ] **Step 3: Il codice**, secondo la decisione 9. In `attentionNote`, la nota nulla solo se tutti e tre i numeri sono zero, e l'ordine è modifiche, finiti, in scadenza:
  ```tsx
  {failed > 0 && <span className="font-medium text-danger">{failedText(failed)}</span>}
  ```
  con « · » fra i pezzi presenti.
- [ ] **Step 4: Passano**, poi `npx vitest run --maxWorkers=4 src/features/pantry`.
- [ ] **Step 5: Commit**: `dispensa: il titolo di un reparto chiuso dice una modifica non salvata`.

### Task 7: i campi che salvano tengono il fuoco, e la scadenza esce dalla riga

**Files:**
- Create: `frontend/src/features/pantry/ExpiryLine.tsx`
- Modify: `frontend/src/features/pantry/PantryRow.tsx` (usa `ExpiryLine`)
- Modify: `frontend/src/features/registry/RenameForm.tsx`, `frontend/src/components/CategorySelect.tsx`
- Test: `frontend/src/features/pantry/PantryRow.test.tsx`, `frontend/src/components/CategorySelect.test.tsx`, e il file che prova `RenameForm` (`grep -rln "Salva il nome" frontend/src --include=*.test.tsx`)

**Interfaces:**
- Produces: `export function ExpiryLine({ item, label, busy, onExpiry }: { item: PantryItem; label: string; busy: boolean; onExpiry: (expiresOn: string | null) => Promise<unknown> })`, il blocco `<div className="flex min-h-11 items-start pl-9 text-xs text-ink-faint">` di oggi con tutto quel che gli serve (decisione 11).

- [ ] **Step 1: I test che falliscono.**
  - `PantryRow.test.tsx`, «il campo data aperto tiene il fuoco mentre una scrittura è in volo»: aperto il campo (con «+ scadenza per Total 0%»), ridisegnata la riga con `busy` vero, il campo «Scadenza di Total 0%» ha ancora il fuoco, `readOnly`, `aria-disabled="true"` e niente `disabled`.
  - `CategorySelect.test.tsx`, «spento non si spegne»: con `disabled`, il `select` ha `aria-disabled="true"` e niente `disabled`, e un `change` non chiama `onChange`.
  - Il file di `RenameForm`, «mentre salva il nome resta raggiungibile»: col `PATCH` in sospeso, «Nuovo nome» ha `readOnly`, `aria-disabled="true"` e niente `disabled`.
- [ ] **Step 2: Falliscono**: `npx vitest run --maxWorkers=1` con i tre file.
- [ ] **Step 3: Il codice.** Prima l'estrazione: `ExpiryLine` con dentro il blocco e i commenti di oggi, e `PantryRow` lo usa. I test di `PantryRow.test.tsx` di oggi restano verdi senza cambiare. Poi la decisione 10. Nel campo data: `readOnly={busy}` e `aria-disabled={busy || undefined}` al posto di `disabled={busy}`, e la classe `aria-disabled:text-ink-faint`. Nel nome: lo stesso, con `save.isPending`. In `CategorySelect`:
  ```tsx
  aria-disabled={disabled || undefined}
  // `aria-disabled` e non `disabled`: il nativo toglie il fuoco a chi è nel campo
  // mentre si salva (pulizie del 2026-10-13). Il cambio si ignora, e il valore
  // controllato resta quello di prima
  onChange={(event) => {
    if (!disabled) onChange(event.target.value);
  }}
  className="mt-1.5 aria-disabled:text-ink-faint"
  ```
- [ ] **Step 4: Passano**, poi `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- [ ] **Step 5: Commit**: `dispensa e anagrafica: i campi che salvano non si spengono, la scadenza esce dalla riga`.

### Task 8: e2e, la verifica nel browser, il backlog

- [ ] **Step 1: e2e intera**, con i comandi delle Global Constraints, dentro il limite di carico.
- [ ] **Step 2: Nel browser**, sullo stack e2e prima del `down`, a **375 px** e nei **due temi** (`prefers-color-scheme` chiaro e scuro):
  - in «Sistema la spesa», una voce risolta con «+ un'altra confezione» lasciata senza scelta: la frase sotto «Confezione 2», e la barra delle icone come prima;
  - in Dispensa, «Scansiona», un codice di un prodotto del seme scritto a mano, «Metti in dispensa» da tastiera (Tab e Invio): il fuoco è sul titolo «Codice a barre», col contorno visibile (`document.activeElement` dal pannello del browser);
  - una riga con il campo della scadenza aperto: uguale a prima dell'estrazione.
  Uno screenshot per tema va nel report. Niente scorre di lato.
- [ ] **Step 3: Il backlog.** Le cinque voci passano a `fatto <data>` in «Fatti (recenti)», con ` → branch night/dispensa-rifiniture (da revisionare, da unire dopo night/frontend-annulla-e-test)`. Commit: `next-steps: le rifiniture della Dispensa, fatte`.

## Fuori scope

- Il fuoco quando si apre il catalogo o il modulo dalla scheda sfusa del +: anche lì il pulsante sparisce. Se lo si vede cadere sul `body`, va nel report come idea.
- Un reparto che si apre da solo per mostrare l'errore.
- Un 401 nel «Riprova» dell'ingresso fallito: è una chiamata nuda come `undoEntry`, quindi non passa dal `MutationCache` di `App.tsx` e non riporta all'accesso. Mostra di nuovo l'avviso, come fa già `undoEntry`.
- Le altre righe di «Sistema la spesa» e il ramo «Abbina» di `StockingRow`.

## Comandi di verifica

- Da `<worktree>/frontend`: `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- e2e: la suite intera, verde.
- `grep -n "disabled={" frontend/src/features/pantry/ExpiryLine.tsx frontend/src/features/registry/RenameForm.tsx frontend/src/components/CategorySelect.tsx` non trova niente.
- `grep -n "IconToolbar" frontend/src/features/stocking/StockingRow.tsx frontend/src/features/stocking/PackageRow.tsx` non trova niente.
- `grep -rn "emerald\|neutral-" frontend/src` resta vuoto.
- `git -C <worktree> diff night/frontend-annulla-e-test --stat` tocca solo i file dei task, più `next-steps.md` e il report.
