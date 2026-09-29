# T3 Consegna 3 — Sistema la spesa ridisegnata: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** portare «Sistema la spesa» (`/sistema`) sulle primitive della Consegna 0: una riga per voce con le tre icone codice / catalogo / sfuso, le voci in sezioni per reparto come in Lista, un pannello alla volta che si apre sotto la sua voce e lascia a video solo lei (S10), «Abbina» chiuso che apre il selettore unico, «Metti in dispensa N» con l'avviso in Dispensa (T4), e i messaggi del catalogo e del «di un altro ingrediente» rifatti.

**Architecture:** un solo cambio nel backend: `ProductOut` porta `ingredient_name`, così «È di un altro ingrediente: burro» lo dice il server. Nel frontend `StockingScreen.tsx` (916 righe, 13 `useState`) si divide: le funzioni pure in `stockingView.ts` (il corpo di «Metti in dispensa» e il testo dell'avviso, testati a tabella), la riga in `StockingRow.tsx`, i pannelli in `ScannerPanel.tsx`, `MatchPanel.tsx` (con `NewIngredientFields.tsx`, riusabile da R12) e `OffSuggestionQuestion.tsx`; `CatalogSearchPanel.tsx` e `BarcodeScanner.tsx` cambiano poco. Lo schermo tiene le scelte per voce e **un solo stato per il pannello aperto**, un'unione discriminata; compone `Screen`, `Section`, `EmptyState`, `ErrorState` e l'avviso unico (`useNotice`). Nessuna rotta nuova, nessuna migrazione.

**Tech Stack:** FastAPI + SQLAlchemy async + pytest su Postgres (solo Task 1); React 19, TypeScript, Tailwind 4 (token in `@theme`), TanStack Query 5, react-router 7, Vitest + Testing Library (jsdom), Playwright.

**Spec:** `docs/superpowers/specs/2026-09-28-ridisegno-design.md`, §2, §3.3, §3.5 e **§4.3**; più **S10** (con i suoi tre dettagli) e **T4** in `docs/prossimi-passi.md`, e le nove osservazioni del giro sotto «**Sistema la spesa** (oltre a S10, S19 e S20)». Si leggono insieme a questo piano.

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/sistema-la-spesa` (`.worktrees/` è già in `.gitignore`), ramo `night/sistema-la-spesa`, creato da `master`. Ogni comando parte da lì (o dalle sue `backend/` e `frontend/`), mai dalla radice del repository principale. **Nessun push, nessun merge, nessun deploy.**
- Tutto il colore passa dai token di `frontend/src/index.css`. Nessuna schermata nomina un colore crudo: `grep -rn "emerald\|neutral-" frontend/src` resta vuoto. Il testo su un fondo pieno usa il suo `on-*`. Ogni testo sta sopra 4,5:1, in chiaro e in scuro, e lo misura `frontend/e2e/style.spec.ts`.
- Le icone si importano solo da `frontend/src/components/ui/icons.ts`.
- Regola delle icone (spec §2): **più pulsanti in gruppo → solo icone; un pulsante da solo → icona e testo.** Ogni pulsante di sola icona ha il nome completo come `aria-label`: `Button` con `icon` e `label`.
- Ogni bersaglio nuovo è almeno 44×44 px. A 375 px nessuna schermata scorre di lato.
- **Un controllo che si spegne mentre ha il fuoco usa `aria-disabled` e una guardia nel gestore, non `disabled`**: il browser toglie il fuoco a un controllo che diventa `disabled`, e chi usa la tastiera lo ritrova sul `body` (è il difetto già corretto su tacche, casella della lista e scadenza della dispensa). Vale per «Metti in dispensa», «Cerca», «Crea l'ingrediente» e «Riprova» dell'abbinamento.
- **Nomi accessibili stabili** (spec §6): «Codice a barre per X», «Cerca a catalogo per X», «Sfuso, senza marca: X», «Cambia la scelta per X», «+ scadenza per X», «Riprova ad abbinare X» restano quelli di oggi, anche se diventano icone. Il campo manuale resta «Codice a barre», quello del catalogo «Cerca a catalogo», il selettore del reparto «Reparto».
- **Il frontend non calcola logica di dominio del backend.** Il nome dell'ingrediente di un prodotto arriva dal server (`ingredient_name`), mai cercato dal client.
- **Mai un vicolo cieco.** Ogni guasto lascia una strada: il catalogo e lo scanner offrono «Crea il prodotto a mano», l'abbinamento offre sempre la creazione, la sistemazione fallita resta con le sue scelte.
- Nessuna dipendenza nuova. Nessuna migrazione (aggiungere un campo a una risposta non lo è).
- Le parole a video sono in italiano, gli identificatori in inglese, i commenti in italiano come nel resto del codice. **Accordi**: niente participi che concordano col nome della voce.
- **Il type check è `npm run typecheck`** (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0 (sesta lezione di `CLAUDE.md`).
- Controlli del frontend, da `frontend/`: `npx vitest run`, `npm run typecheck`, `npm run lint`, `npm run build`. Il progetto **non ha** uno script `npm test`.
- **Backend su Postgres vero.** Il database di test è il container `spena-db-1` (porta 5433), da usare solo come database dei test: se `docker ps` non lo mostra, `docker start spena-db-1`. **Mai `docker compose up` dal worktree**: il nome del progetto Compose viene dalla cartella, e ne nascerebbe un secondo Postgres che litiga sulla 5433. Il comando dei test, da `<worktree>/backend`:
  ```bash
  PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
  Il venv è quello del repository principale (il worktree non ne ha uno): `python -m` mette la cartella corrente in testa a `sys.path`, quindi si prova l'`app` del worktree. Se un test sembra ignorare una modifica, `python -c 'import app; print(app.__file__)'` da `backend/` (con lo stesso `PATH`) deve stampare un percorso dentro il worktree.
- **e2e** sullo stack `spena-e2e`, dalla radice del worktree. Serve un `.env`: **si copia da `.env.example`, che non ha segreti, solo per la prova, e si cancella dopo. Mai leggere né copiare il `.env` del checkout principale.** Prima di alzarlo, `docker ps --format '{{.Names}}' | grep spena-e2e`: se c'è e non l'hai alzato tu, non toccarlo e aspetta.
  ```bash
  cp .env.example .env
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed --con-ricette
  cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e; cd ..
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
  rm .env
  ```
  Una prova fallita lascia dati nello stack: prima di rieseguire, `down -v` e di nuovo `up`, seme e prova.

### Preparazione (una volta, prima del Task 1)

- [ ] Dal checkout principale, allinea `node_modules` al lockfile (fino al 2026-09-29 era vecchio: mancavano `@fontsource-variable/inter` e altri due pacchetti, e 24 file di test non si caricavano). Non aggiunge dipendenze, installa quelle di `package-lock.json`:
  ```bash
  cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund
  ```
- [ ] Crea il worktree e collega `node_modules` (e solo quello: **niente `.env`**):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/sistema-la-spesa -b night/sistema-la-spesa master
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/sistema-la-spesa/frontend/node_modules
  ```
- [ ] La linea di partenza, dal worktree:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/sistema-la-spesa/frontend && npx vitest run
  ```
  Expected: **51 file, 663 test verdi**. E il backend (comando sopra, da `backend/`): tutto verde; annota il numero nel report, cresce di 3 col Task 1. Se una delle due linee non è verde, fermati: non è un difetto di questo piano.

---

## Obiettivo e contesto

«Sistema la spesa» è lo schermo in cui la spesa entra in dispensa, voce per voce: con il codice a barre, cercando a catalogo, o sfusa. È lo schermo più denso dell'app e quello che il giro di T3 ha trovato più confuso: due righe di pulsanti per voce, pannelli che si aprono in fondo alla pagina fuori vista (S10), un blocco «non abbinata» sempre aperto alto una schermata e mezza, «È di un altro ingrediente» in rosso senza dire quale, il catalogo con due messaggi che si contraddicono, «Metti in dispensa» che non dice quante voci entrano e poi porta in Dispensa senza dire niente (T4). Questa consegna lo porta sulle primitive e chiude quelle osservazioni, senza toccare quel che il giro ha chiesto di non riprogettare via: gli errori accanto alla riga che li ha causati, il caricamento fallito che non si traveste da lista vuota, i nomi accessibili che portano il nome della voce, i campi a 16 px, il catalogo che si apre già cercando il nome della voce.

## Decisioni prese

Prese di giorno (le prime tredici con Mattia o dal coordinatore della fase giorno, il 2026-09-29), con la ragione: la notte non le riapre.

1. **Il pannello aperto lascia a video solo la sua voce** (Mattia). Quando si apre un pannello — scanner, catalogo, modulo del prodotto, domanda di Open Food Facts, «Abbina» — restano a video solo quella voce e il suo pannello: le altre voci, le intestazioni dei reparti e «Metti in dispensa» spariscono, e la voce va in cima con `revealAtTop` (`scroll-mt-16`). Confermare o annullare rimette tutto; le scelte già fatte restano, perché sono indicizzate per voce. Annullando, il fuoco torna al pulsante che aveva aperto il pannello. *Perché:* è la richiesta di S10; e con un pannello alla volta sotto la sua voce, cosa sta entrando in dispensa si legge senza ambiguità.
2. **Un pannello alla volta**, in un solo stato: un'unione discriminata `Panel` (scanner, catalogo, abbinamento, domanda, modulo) al posto di `scanningFor`, `searchingFor`, `creatingFor`, `confirmingFor`. I pannelli stanno dentro la `<li>` della voce, sotto la sua riga. *Perché:* oggi due pannelli possono stare aperti insieme (lo annota S8), e quattro stati sparsi sono quattro modi di dimenticarne uno.
3. **Sezioni per reparto come in Lista** (Mattia): le stesse `Section`, lo stesso ordine con `groupForDisplay` di `frontend/src/features/shopping-list/listView.ts` (riusata, non copiata), le voci senza reparto in fondo. Una voce appena abbinata passa nel suo reparto dopo la rilettura: va bene. *Perché:* dal giro, «l'ordine delle voci non è quello per reparto della lista».
4. **«3 restano in lista» conta solo le voci nel carrello che non sono entrate** (Mattia): le voci ancora da comprare non contano, non erano in questa spesa. Si calcola nel client: voci spuntate meno voci mandate. A zero l'avviso dice solo «4 in dispensa»; al singolare «1 in dispensa», e «1 resta in lista». L'avviso parte con `useNotice` prima di `navigate("/dispensa")` (`NoticeProvider` sta sopra `BrowserRouter` in `App.tsx`, quindi sopravvive al passaggio). Il pulsante dice «Metti in dispensa 4», dove 4 sono le voci che partono davvero: **la stessa lista filtrata del corpo della richiesta** (`stockEntries`), una fonte per i due. *Perché:* spec §4.3 e T4; contati a parte, numero e corpo si scollerebbero proprio sulla voce che non parte.
5. **«Abbina» usa l'`IngredientPicker` unico** (spec §3.5): `MatchIngredientField` e il suo ARIA non valido (`ul[role=listbox] > li > button[role=option]`) se ne vanno. La voce non abbinata è una riga chiusa con «Abbina», che apre il selettore. Creare l'ingrediente è un passo della sistemazione dopo `onCreate(name)`: un campo col nome, precompilato, con l'etichetta visibile «Come si chiama in generale?», più il reparto, poi «Crea l'ingrediente». Quel passo sta in un componente suo, `NewIngredientFields.tsx`, perché la Consegna 6 (R12) lo riusi — ma il modulo della ricetta non si tocca ora. Il 409 che riaggancia l'ingrediente omonimo (`existingIngredient`, S19) continua a funzionare. *Perché:* dal giro, «zucchine tonde di Nizza della signora Pina» diventava il nome dell'ingrediente; e tre selettori con tre aspetti erano un'osservazione del giro.
6. **«È di un altro ingrediente» dice quale, e non è rosso.** `ProductOut` (che il lookup del codice e la ricerca a catalogo restituiscono entrambi) porta `ingredient_name`, con un test del backend scritto prima. Lo schermo scrive ««Parmigiano Reggiano» è di un altro ingrediente: burro.» in tono neutro (`text-ink`, `role="status"`, mai `text-danger` né `role="alert"`). Il frontend non cerca mai il nome da sé. *Perché:* non è un guasto, ed è il caso del parmigiano sotto «burro» (S9) visto dall'altra parte.
7. **Il catalogo dà un messaggio per stato**, mai due che si contraddicono; l'esempio «yogurt greco» compare solo col campo vuoto o quasi (meno di due lettere), mai accanto ai risultati di un'altra ricerca. Resta vero che **il catalogo si apre già cercando il nome della voce** (è fra le cose da non riprogettare via). *Perché:* dal giro, «altri 2 prodotti, di un altro ingrediente» e «nessun prodotto» insieme.
8. **La riga risolta** ha il nome sopra e, sotto in piccolo, a cosa si è risolta: «Sfuso», o il nome del prodotto con la marca se c'è — come una riga della dispensa. «Cambia» diventa l'icona `IconReplace`. **La riga da risolvere** ha il nome e un `IconToolbar` con tre icone da 44 px — `IconBarcode`, `IconListSearch`, `IconScale` — coi nomi accessibili di oggi. *Perché:* spec §4.3; dal giro, «una voce risolta si riconosce solo dal colore verde», e «Cambia» pesava quanto le azioni principali.
9. **La scadenza**: «+ scadenza» apre un campo data con un'etichetta visibile e una ✕ che lo richiude svuotandolo; svuotato, parte `null`. L'Invio nel campo ha `preventDefault` (la lezione della Consegna 1: arrivava al pulsante che riprendeva il fuoco); Esc lo chiude come la ✕. *Perché:* dal giro, il campo non aveva un'etichetta visibile né un modo di richiuderlo.
10. **I tre dettagli di S10**: il titolo del pannello del codice nomina la voce; il campo manuale ha `inputMode="numeric"` e un pulsante «Cerca»; senza fotocamera il pannello offre «Crea il prodotto a mano», che apre il modulo per quella voce.
11. **Gli errori**: quelli di una voce restano accanto alla sua riga (dal giro, da non riprogettare via); il caricamento fallito usa `ErrorState` con «Riprova»; il fallimento della sistemazione resta accanto al pulsante.
12. **Niente da sistemare**: `EmptyState` con un collegamento alla Lista, senza il pulsante spento.
13. **`StockingScreen.tsx` si restringe**: la riga e i pannelli escono in file loro. Le guardie — il controllo ingrediente/prodotto prima del 409, il codice di S8 che non sopravvive a un'altra voce, S19, S20 — stanno in un posto solo ciascuna, non duplicate.

Scelte di questo piano, dove le tredici sopra non arrivavano (reversibili; Mattia le rivede):

14. **`IngredientPicker` impara `createWhen="always"`.** Di norma offre «Aggiungi «…»» solo a ricerca vuota; così la sistemazione perderebbe la creazione ogni volta che la ricerca trova qualcosa, cioè il difetto S6 («cera per pavimenti» pescava sette suggerimenti, `Pera` in testa, e la porta spariva). Con `"always"` l'offerta compare appena la ricerca del testo scritto ha risposto, bene o male (anche se non risponde). Un pulsante di creazione solo, quello del selettore unico. Il valore di partenza resta `"empty"`: gli altri schermi non cambiano.
15. **Il nome del passo di creazione parte da quel che il selettore consegna** con `onCreate(name)`, cioè il testo cercato: il selettore nasce col testo della voce, quindi è il testo della voce finché non lo si riscrive. Chi ha già corretto la ricerca non si ritrova il testo di prima.
16. **Anche l'elenco del catalogo diventa un `listbox` valido** (`div[role=listbox] > button[role=option]`, come `OptionList`): aveva lo stesso ARIA sbagliato di `MatchIngredientField`, e l'osservazione del giro vale per tutti e due.
17. **«Metti in dispensa» senza niente di scelto** dice «Metti in dispensa» senza numero, spento con `aria-disabled`, con sotto «Scegli come entra almeno una voce: codice, catalogo o sfuso.» (dal giro, da non riprogettare via: il pulsante spento col motivo scritto sotto).
18. **Il fuoco**: aprendo un pannello la vista cambia forma e la riga rinasce, quindi il fuoco tornerebbe sul `body`: torna al pulsante che l'ha aperto (il selettore di «Abbina» lo prende da sé). Una scelta fatta porta il fuoco a «Cambia»; «Cambia» lo porta alla prima icona; un abbinamento riuscito alla prima icona.
19. **«Annulla» dello scanner va in fondo al pannello**: `BarcodeScanner` accetta dei `children`, disegnati fra la fotocamera e il suo «Annulla» (S10: «c'è solo il campo del codice, con «Annulla» in mezzo»).
20. **`ingredient_name` è `Ingredient.name`**, il nome canonico in minuscolo, come `ingredient_name` di `ShoppingItemOut` e `PantryItemOut`.
21. **Il campo della scadenza è aperto finché la voce ha una chiave nel registro delle scadenze** (anche vuota): la riga sparisce e rinasce col pannello di un'altra voce, e la data scritta non deve sparire con lei.

## Criteri di accettazione

- [ ] `GET /products/barcode/{code}` (prodotto del catalogo), `GET /products/search` e `POST /products` restituiscono `ingredient_name` per ogni prodotto; tre test del backend lo provano.
- [ ] Le voci stanno in sezioni per reparto, nell'ordine della Lista; quelle senza ingrediente in una sezione «Senza reparto» in fondo.
- [ ] Una voce da risolvere ha tre icone in un `toolbar`, ciascuna da almeno 44×44 px e sulla stessa riga anche a 375 px con un nome lungo; una voce risolta dice «Sfuso» o prodotto e marca sotto il nome, e ha «Cambia» come icona.
- [ ] Aprire un pannello nasconde le altre voci, le intestazioni dei reparti e «Metti in dispensa»; la voce va in cima, sotto l'intestazione fissa; chiudere rimette tutto, con le scelte già fatte e il fuoco sul pulsante che l'aveva aperto. Un pannello alla volta.
- [ ] Il pannello del codice nomina la voce nel titolo; il campo ha `inputmode="numeric"` e «Cerca»; senza fotocamera offre «Crea il prodotto a mano», uno solo anche quando il lookup fallisce.
- [ ] «È di un altro ingrediente» nomina l'ingrediente, senza `role="alert"` e senza `text-danger`, sia dal codice sia dal catalogo.
- [ ] Il catalogo mostra un messaggio per stato; l'esempio «yogurt greco» solo a campo (quasi) vuoto.
- [ ] La voce senza ingrediente è chiusa, con «Abbina»; il selettore unico parte dal testo della voce; «Aggiungi «…»» c'è sempre dopo che la ricerca ha risposto; la creazione chiede «Come si chiama in generale?» e il reparto; il 409 riaggancia l'omonimo.
- [ ] «+ scadenza» apre un campo con etichetta visibile e ✕; svuotato o chiuso parte `null`; Invio non preme niente, Esc chiude.
- [ ] «Metti in dispensa N» con N = voci mandate; dopo, in Dispensa, l'avviso «N in dispensa · M restano in lista» (o solo «N in dispensa»).
- [ ] Niente da sistemare: `EmptyState` con «Vai alla Lista», nessun pulsante spento. Caricamento fallito: `ErrorState` con «Riprova».
- [ ] `StockingScreen.tsx` non contiene più `MatchIngredientField`, `OffSuggestionQuestion`, `scanningFor`, `searchingFor`, `creatingFor`, `confirmingFor`, `badCode`, `mismatch`, `manualCode`; `OTHER_INGREDIENT` non esiste più.
- [ ] Tutti i test di oggi di `StockingScreen.test.tsx` passano, migrati solo dove un controllo ha cambiato nome o posto (elencati nel Task 7), mai indeboliti.
- [ ] vitest, typecheck, lint, build, pytest e l'e2e intera verdi; `style.spec.ts` ha la prova nuova a 375×812.
- [ ] `docs/prossimi-passi.md` e `next-steps.md` aggiornati (Task 9).

## Comandi di verifica

Da `<worktree>/frontend`:

```bash
npx vitest run
npm run typecheck
npm run lint
npm run build
```

Da `<worktree>/backend`:

```bash
PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Dalla radice del worktree:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -rn "OTHER_INGREDIENT\|MatchIngredientField\|scanningFor\|searchingFor\|creatingFor\|confirmingFor" frontend/src
```

Expected: i due `grep` non stampano niente. E l'e2e intera con i comandi delle Global Constraints.

## Fuori scope

- Le Consegne 4, 5 e 6 del ridisegno; in particolare R12 nel modulo della ricetta (`NewIngredientFields` nasce pronto, ma `RecipeForm` non si tocca).
- S3, l'ingresso diretto in dispensa; S12 (icone per reparto nelle righe della dispensa); S14, S15.
- La Dispensa oltre al ricevere l'avviso: `PantryScreen` non cambia.
- Qualunque cambio al backend oltre a `ingredient_name` su `ProductOut`: niente rotte nuove, niente migrazioni, la risposta di `POST /shopping-list/stock` resta `{"created": n}`.
- Una variante `aria-disabled` del primitivo `Button` (è una voce sua in `next-steps.md`): qui i controlli che si spengono col fuoco sono `<button>` scritti con `buttonClasses`.
- `CustomProductForm.tsx` non cambia (resta com'è, «Salva prodotto» compreso).

## Margine di autonomia

- **Liberi**: i nomi di funzioni, stati e componenti interni non fissati nelle interfacce qui sotto; l'ordine delle classi Tailwind; i commenti, purché dicano il perché.
- **Non liberi**: le parole a video, che si scrivono **esattamente** come in questo piano; i nomi accessibili; i nomi dei file e delle prop esportate che un task successivo consuma.
- **Nessuna dipendenza nuova**, nessuna migrazione, nessun token di colore nuovo.
- **Un test di oggi si cambia solo per seguire un controllo che ha cambiato nome o posto**, mai per indebolire un'asserzione. Le migrazioni ammesse sono elencate nel Task 7; se ne serve un'altra, scrivila nel report con il perché.
- Se si presenta una decisione che il piano non copre e che non è reversibile e a basso impatto: ferma quel task, lascia il lavoro fatto in un commit sul ramo, e segnalo come bloccato — nel report della notte (`docs/night-reports/<data>.md`) e in `next-steps.md` — con la domanda precisa per Mattia.

## Dipendenze

Nessun altro piano. Si parte da `master` com'è quando la notte comincia. Le modifiche della fase giorno ancora da committare nel checkout principale (la spec §3.5 e `next-steps.md`) vanno committate su `master` **prima** di creare il worktree, o il Task 9 lavorerà su un `next-steps.md` vecchio.

---

## File toccati

| File | Cosa |
|---|---|
| `backend/app/schemas/product.py` | `ProductOut.ingredient_name` |
| `backend/app/api/products.py` | `_products_out`: il nome dell'ingrediente in una query sola |
| `backend/tests/api/test_products.py` | tre test |
| `frontend/src/domain/types.ts` | `Product.ingredient_name` |
| `frontend/src/features/registry/RegistryScreen.test.tsx` | il prodotto di prova porta `ingredient_name` (il tipo lo chiede) |
| `frontend/src/features/stocking/stockingView.ts` (nuovo) | `Resolution`, `PanelTrigger`, `FocusTarget`, `StockEntry`, `stockEntries`, `stockNotice` |
| `frontend/src/features/stocking/stockingView.test.ts` (nuovo) | test a tabella |
| `frontend/src/features/stocking/wording.ts` | `otherIngredient`, `elsewhereNote`; via `OTHER_INGREDIENT` (Task 7) |
| `frontend/src/features/stocking/wording.test.ts` (nuovo) | test a tabella |
| `frontend/src/features/stocking/CatalogSearchPanel.tsx` | un messaggio per stato, `listbox` valido, i nomi degli altri ingredienti |
| `frontend/src/features/stocking/CatalogSearchPanel.test.tsx` (nuovo) | test |
| `frontend/src/features/stocking/BarcodeScanner.tsx` (+ test) | `onUnavailable`, `children` prima di «Annulla» |
| `frontend/src/features/stocking/ScannerPanel.tsx` (nuovo) | il pannello del codice (S10, S20, la guardia del 409) |
| `frontend/src/features/stocking/ScannerPanel.test.tsx` (nuovo) | test |
| `frontend/src/components/IngredientPicker.tsx` (+ test) | `createWhen` |
| `frontend/src/features/stocking/NewIngredientFields.tsx` (nuovo) | «Come si chiama in generale?» e il reparto |
| `frontend/src/features/stocking/NewIngredientFields.test.tsx` (nuovo) | test |
| `frontend/src/features/stocking/MatchPanel.tsx` (nuovo) | «Abbina»: il selettore unico e la creazione |
| `frontend/src/features/stocking/MatchPanel.test.tsx` (nuovo) | test |
| `frontend/src/features/stocking/StockingRow.tsx` (nuovo) | la riga |
| `frontend/src/features/stocking/StockingRow.test.tsx` (nuovo) | test |
| `frontend/src/features/stocking/OffSuggestionQuestion.tsx` (nuovo) | la domanda di S20, estratta |
| `frontend/src/features/stocking/StockingScreen.tsx` | riscritto |
| `frontend/src/features/stocking/StockingScreen.test.tsx` | migrato e allargato |
| `frontend/e2e/cooking.spec.ts`, `frontend/e2e/non-alimentari.spec.ts` | «Metti in dispensa 1», e l'avviso |
| `frontend/e2e/style.spec.ts` | la prova a 375×812 |
| `docs/prossimi-passi.md`, `next-steps.md` | Consegna 3, S10, T4 |

---

### Task 1: Il prodotto dice di quale ingrediente è (`ingredient_name`)

**Files:**
- Modify: `backend/tests/api/test_products.py` (tre test in fondo)
- Modify: `backend/app/schemas/product.py` (`ProductOut`)
- Modify: `backend/app/api/products.py` (`lookup_barcode`, `search`, `create`)
- Modify: `frontend/src/domain/types.ts` (`Product`)
- Modify: `frontend/src/features/registry/RegistryScreen.test.tsx` (il prodotto `REGGIANO`)

**Interfaces:**
- Produces: ogni `ProductOut` — in `BarcodeLookupOut.product`, nella lista di `GET /products/search`, nella risposta di `POST /products` — ha `ingredient_name: str`, il `name` dell'ingrediente del prodotto. Nel frontend `Product.ingredient_name: string`. Lo consumano i Task 3 e 4.

Perché non con `ProductOut.model_validate(product)`: il modello `Product` non ha una relazione con `Ingredient`, e aggiungerne una caricata sempre (`lazy="joined"`) cambierebbe ogni query che legge un prodotto, dispensa compresa. Il nome si legge con una query sola per tutta la risposta, e `ProductOut` si costruisce a mano.

- [ ] **Step 1: Scrivere i test che falliscono**

In fondo a `backend/tests/api/test_products.py` aggiungi:

```python
async def test_a_catalog_hit_names_its_ingredient(logged_client, db_session, yogurt):
    """T3 Consegna 3: «È di un altro ingrediente: burro» dice quale. Il nome lo manda il
    server: il client non va a cercarselo."""
    db_session.add(Product(ingredient_id=yogurt.id, name="Fage Total 0%", brand="Fage",
                           barcode="5201054000138", source="openfoodfacts"))
    await db_session.flush()

    body = (await logged_client.get("/api/v1/products/barcode/5201054000138")).json()
    assert body["product"]["ingredient_name"] == "yogurt greco"


async def test_catalog_search_names_the_ingredient_of_each_product(
    logged_client, db_session, yogurt
):
    """Il catalogo dice di chi è ogni prodotto che trova: «altri 2 prodotti, di un altro
    ingrediente» diventa «…: burro di prova», e i nomi arrivano con la risposta."""
    burro = Ingredient(name="burro di prova", display_name="Burro di prova",
                       category=IngredientCategory.LATTICINI)
    db_session.add(burro)
    await db_session.flush()
    db_session.add_all([
        Product(ingredient_id=yogurt.id, name="Crema zafferanata", source="custom"),
        Product(ingredient_id=burro.id, name="Panetto zafferanato", source="custom"),
    ])
    await db_session.flush()

    response = await logged_client.get("/api/v1/products/search", params={"q": "zafferan"})
    assert response.status_code == 200
    assert {p["name"]: p["ingredient_name"] for p in response.json()} == {
        "Crema zafferanata": "yogurt greco",
        "Panetto zafferanato": "burro di prova",
    }


async def test_a_created_product_names_its_ingredient(logged_client, yogurt):
    response = await logged_client.post("/api/v1/products", json={
        "ingredient_id": str(yogurt.id), "name": "Yogurt greco al miele",
    })
    assert response.status_code == 201
    assert response.json()["ingredient_name"] == "yogurt greco"
```

- [ ] **Step 2: Farli fallire**

Run (da `<worktree>/backend`): `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/api/test_products.py`
Expected: FAIL, 3 test, `KeyError: 'ingredient_name'`; gli altri verdi.

- [ ] **Step 3: Lo schema**

In `backend/app/schemas/product.py` sostituisci l'intera classe `ProductOut` con:

```python
class ProductOut(BaseModel):
    """Un prodotto del catalogo, come lo leggono la sistemazione e l'anagrafica.

    `ingredient_name` è il `name` dell'ingrediente del prodotto: la sistemazione dice
    «È di un altro ingrediente: burro» (T3 Consegna 3), e il nome lo manda il server
    invece di lasciarlo cercare al client. Si costruisce con `_products_out` in
    `app/api/products.py`, non da un `Product` da solo: il modello non ha la relazione
    con l'ingrediente, e il nome arriva da una query a parte.
    """

    id: uuid.UUID
    ingredient_id: uuid.UUID
    ingredient_name: str
    name: str
    brand: str | None
    barcode: str | None
    source: str
    nutrients: dict[str, float] | None
    image_url: str | None
```

(Il `model_config = ConfigDict(from_attributes=True)` di `ProductOut` se ne va: nessuno la valida più da un oggetto. `ConfigDict` resta importato, lo usano le altre classi del file.)

- [ ] **Step 4: Le rotte**

In `backend/app/api/products.py`, subito sopra `@router.get("/barcode/{barcode}", ...)`, aggiungi:

```python
async def _products_out(session: AsyncSession, products: list[Product]) -> list[ProductOut]:
    """I prodotti con il nome del loro ingrediente, in una query sola per tutta la
    risposta (T3 Consegna 3: «È di un altro ingrediente: burro»).

    Una relazione `Product.ingredient` sempre caricata avrebbe cambiato ogni query che
    legge un prodotto, dispensa compresa; qui il nome serve a tre rotte, e lo chiedono
    loro. `ingredient_id` è una chiave esterna non annullabile, quindi il nome c'è sempre.
    """
    ids = {product.ingredient_id for product in products}
    names: dict[uuid.UUID, str] = {}
    if ids:
        rows = await session.execute(
            select(Ingredient.id, Ingredient.name).where(Ingredient.id.in_(ids))
        )
        names = {ingredient_id: name for ingredient_id, name in rows.all()}
    return [
        ProductOut(
            id=product.id,
            ingredient_id=product.ingredient_id,
            ingredient_name=names[product.ingredient_id],
            name=product.name,
            brand=product.brand,
            barcode=product.barcode,
            source=product.source,
            nutrients=product.nutrients,
            image_url=product.image_url,
        )
        for product in products
    ]
```

Poi, nella stessa file:

1. in `lookup_barcode` sostituisci
   ```python
           return BarcodeLookupOut(
               found=True, origin="catalog", product=ProductOut.model_validate(existing),
               valid_checksum=valid_checksum,
           )
   ```
   con
   ```python
           [product] = await _products_out(session, [existing])
           return BarcodeLookupOut(
               found=True, origin="catalog", product=product, valid_checksum=valid_checksum,
           )
   ```
2. in `search` sostituisci `return [ProductOut.model_validate(p) for p in found]` con
   ```python
       return await _products_out(session, found)
   ```
3. in `create` sostituisci l'ultima riga, `return ProductOut.model_validate(product)`, con
   ```python
       [created] = await _products_out(session, [product])
       return created
   ```

`uuid`, `select` e `Ingredient` sono già importati in cima al file.

Run: `grep -n "ProductOut.model_validate" backend/app` (dalla radice del worktree)
Expected: niente.

- [ ] **Step 5: Farli passare, e tutta la suite**

Run (da `backend/`): `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/api/test_products.py`
Expected: PASS, tutti.

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q`
Expected: tutto verde, tre test in più della linea di partenza. (`test_integrity_mapping.py` sostituisce `create_product` in `app.api.products` con una funzione che solleva: il `create` riscritto la chiama ancora per nome, e il test resta valido.)

- [ ] **Step 6: Il tipo nel frontend**

In `frontend/src/domain/types.ts`, nell'interfaccia `Product`, sotto `ingredient_id: string;` aggiungi:

```ts
  /** Il nome dell'ingrediente del prodotto (`Ingredient.name`), mandato dal server:
   * «È di un altro ingrediente: burro» lo dice senza che il client vada a cercarlo
   * (T3 Consegna 3). */
  ingredient_name: string;
```

In `frontend/src/features/registry/RegistryScreen.test.tsx` il prodotto di prova è tipato `Product` e ora non compila: nella costante `REGGIANO`, dopo `ingredient_id: "i-burro",` aggiungi `ingredient_name: "burro",`.

Run (da `frontend/`): `npm run typecheck && npx vitest run src/features/registry src/features/stocking`
Expected: typecheck pulito, test verdi. Se `npm run typecheck` segnala un altro oggetto tipato `Product` senza `ingredient_name` (non dovrebbe: gli altri sono letterali non tipati), aggiungi il campo allo stesso modo e scrivilo nel report.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/product.py backend/app/api/products.py backend/tests/api/test_products.py frontend/src/domain/types.ts frontend/src/features/registry/RegistryScreen.test.tsx
git commit -m "prodotti: la risposta dice di quale ingrediente è il prodotto"
```

---

### Task 2: Le funzioni pure — il corpo di «Metti in dispensa», l'avviso, le frasi del «di un altro ingrediente»

**Files:**
- Create: `frontend/src/features/stocking/stockingView.ts`
- Create: `frontend/src/features/stocking/stockingView.test.ts`
- Modify: `frontend/src/features/stocking/wording.ts` (due funzioni in più; `OTHER_INGREDIENT` resta fino al Task 7)
- Create: `frontend/src/features/stocking/wording.test.ts`

**Interfaces:**
- Consumes: `Product`, `ShoppingItem` da `frontend/src/domain/types.ts`; il tipo di `stockItems` da `./api`.
- Produces (da `stockingView.ts`):
  - `type Resolution = { kind: "loose" } | { kind: "product"; product: Product; barcode?: string }`
  - `type PanelTrigger = "scanner" | "catalog" | "match"`
  - `type FocusTarget = PanelTrigger | "change"`
  - `type StockEntry` — una voce del corpo di `stockItems`
  - `stockEntries(items: ShoppingItem[], resolved: Record<string, Resolution>, ingredientOf: (item: ShoppingItem) => string | null, expiry: Record<string, string>): StockEntry[]`
  - `stockNotice(sent: number, checked: number): string`
- Produces (da `wording.ts`): `otherIngredient(productName: string, ingredientName: string): string`, `elsewhereNote(ingredientNames: string[]): string`.

- [ ] **Step 1: Scrivere i test che falliscono**

`frontend/src/features/stocking/stockingView.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { stockEntries, stockNotice, type Resolution } from "./stockingView";
import type { Product, ShoppingItem } from "../../domain/types";

function item(id: string, ingredientId: string | null): ShoppingItem {
  return {
    id, raw_text: id, ingredient_id: ingredientId, ingredient_name: ingredientId ? id : null,
    ingredient_category: ingredientId ? "altro" : null, ingredient_kind: ingredientId ? "food" : null,
    status: "checked", reason: "manual", created_at: "2026-09-29T10:00:00Z",
  };
}

const FAGE: Product = {
  id: "p1", ingredient_id: "i-yogurt", ingredient_name: "yogurt greco", name: "Total 0%",
  brand: "Fage", barcode: "5201054000138", source: "openfoodfacts", nutrients: null, image_url: null,
};

const ownIngredient = (row: ShoppingItem) => row.ingredient_id;
const ids = (entries: { shopping_item_id: string }[]) => entries.map((entry) => entry.shopping_item_id);

describe("stockEntries", () => {
  it("una voce sfusa parte senza prodotto e senza codice", () => {
    expect(stockEntries([item("s1", "i1")], { s1: { kind: "loose" } }, ownIngredient, {})).toEqual([
      { shopping_item_id: "s1", ingredient_id: "i1", product_id: null, expires_on: null, barcode: null },
    ]);
  });

  it("un prodotto porta il suo id, e il codice letto solo se c'è (S8)", () => {
    const resolved: Record<string, Resolution> = {
      s1: { kind: "product", product: FAGE, barcode: "8001234567890" },
      s2: { kind: "product", product: FAGE },
    };
    expect(stockEntries([item("s1", "i1"), item("s2", "i2")], resolved, ownIngredient, {})).toEqual([
      { shopping_item_id: "s1", ingredient_id: "i1", product_id: "p1", expires_on: null,
        barcode: "8001234567890" },
      { shopping_item_id: "s2", ingredient_id: "i2", product_id: "p1", expires_on: null,
        barcode: null },
    ]);
  });

  it("parte solo chi ha una scelta e un ingrediente", () => {
    const entries = stockEntries(
      [item("scelta", "i1"), item("senza-scelta", "i2"), item("senza-ingrediente", null)],
      { scelta: { kind: "loose" }, "senza-ingrediente": { kind: "loose" } },
      ownIngredient,
      {}
    );
    expect(ids(entries)).toEqual(["scelta"]);
  });

  it("l'ingrediente abbinato qui vale quanto quello della lista (S19)", () => {
    const matched = (row: ShoppingItem) => row.ingredient_id ?? "i-abbinato";
    const [entry] = stockEntries([item("s3", null)], { s3: { kind: "loose" } }, matched, {});
    expect(entry.ingredient_id).toBe("i-abbinato");
  });

  it("la scelta di una voce che non c'è più non parte: decide la lista riletta", () => {
    const resolved: Record<string, Resolution> = { s1: { kind: "loose" }, sparita: { kind: "loose" } };
    expect(ids(stockEntries([item("s1", "i1")], resolved, ownIngredient, {}))).toEqual(["s1"]);
  });

  it("nell'ordine della lista, non in quello delle scelte", () => {
    const resolved: Record<string, Resolution> = { s2: { kind: "loose" }, s1: { kind: "loose" } };
    expect(ids(stockEntries([item("s1", "i1"), item("s2", "i2")], resolved, ownIngredient, {})))
      .toEqual(["s1", "s2"]);
  });

  // `||` e non `??`: un campo data svuotato lascia "", che non è una data — il backend
  // risponderebbe 422, e riprovare rimanderebbe lo stesso corpo per sempre
  it.each([
    ["mai scritta", undefined, null],
    ["scritta e poi svuotata", "", null],
    ["scritta", "2026-10-02", "2026-10-02"],
  ] as const)("la scadenza %s parte come %s", (_caso, written, sent) => {
    const expiry: Record<string, string> = written === undefined ? {} : { s1: written };
    const [entry] = stockEntries([item("s1", "i1")], { s1: { kind: "loose" } }, ownIngredient, expiry);
    expect(entry.expires_on).toBe(sent);
  });
});

describe("stockNotice", () => {
  it.each([
    [4, 7, "4 in dispensa · 3 restano in lista"],
    [4, 4, "4 in dispensa"],
    [1, 1, "1 in dispensa"],
    [1, 2, "1 in dispensa · 1 resta in lista"],
    [2, 5, "2 in dispensa · 3 restano in lista"],
  ] as const)("%i mandate su %i nel carrello → «%s»", (sent, checked, text) => {
    expect(stockNotice(sent, checked)).toBe(text);
  });
});
```

`frontend/src/features/stocking/wording.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { elsewhereNote, otherIngredient } from "./wording";

describe("otherIngredient", () => {
  it("dice quale ingrediente, non solo che è un altro", () => {
    expect(otherIngredient("Parmigiano Reggiano 24 mesi", "burro")).toBe(
      "«Parmigiano Reggiano 24 mesi» è di un altro ingrediente: burro."
    );
  });
});

describe("elsewhereNote", () => {
  it.each([
    [["burro"], "Un altro prodotto corrisponde, ma è di un altro ingrediente: burro."],
    [["burro", "burro"], "Altri 2 prodotti corrispondono, ma sono di un altro ingrediente: burro."],
    [
      ["burro", "latte", "burro"],
      "Altri 3 prodotti corrispondono, ma sono di altri ingredienti: burro, latte.",
    ],
  ] as const)("%j → «%s»", (names, text) => {
    expect(elsewhereNote([...names])).toBe(text);
  });
});
```

- [ ] **Step 2: Farli fallire**

Run (da `frontend/`): `npx vitest run src/features/stocking/stockingView.test.ts src/features/stocking/wording.test.ts`
Expected: FAIL, `Failed to resolve import "./stockingView"` e `otherIngredient is not a function` (o l'import mancante).

- [ ] **Step 3: Scrivere il codice**

`frontend/src/features/stocking/stockingView.ts`:

```ts
import type { stockItems } from "./api";
import type { Product, ShoppingItem } from "../../domain/types";

/** Come una voce entra in dispensa: sfusa, o con un prodotto del catalogo. */
export type Resolution =
  | { kind: "loose" }
  // `barcode`: il codice letto per la voce prima di scegliere il prodotto a
  // catalogo (S8), che la sistemazione porta al backend perché lo dia al
  // prodotto se non ne ha. Solo quella scelta lo porta: il prodotto trovato dal
  // codice ce l'ha già, e quello creato a mano lo riceve alla creazione
  | { kind: "product"; product: Product; barcode?: string };

/** Chi apre un pannello sotto una voce: due delle tre icone di una voce con
 * l'ingrediente (il codice, il catalogo), e «Abbina» di una voce senza. Lo sfuso non
 * apre niente: è già una scelta. */
export type PanelTrigger = "scanner" | "catalog" | "match";

/** Dove va il fuoco quando la riga rinasce: al pulsante che aveva aperto il pannello,
 * o a «Cambia» quando la voce è stata risolta e le tre icone non ci sono più. */
export type FocusTarget = PanelTrigger | "change";

/** Una voce del corpo di `POST /shopping-list/stock`. */
export type StockEntry = Parameters<typeof stockItems>[0][number];

/** Le voci che «Metti in dispensa» manda, nell'ordine della lista. Una fonte sola per
 * il corpo della richiesta e per il numero sul pulsante (spec T3 §4.3, «Metti in
 * dispensa 4»): contati a parte, i due si scollerebbero proprio sulla voce che non
 * parte — scelta ma senza ingrediente, o sparita dalla lista riletta.
 *
 * Parte chi ha una scelta e un ingrediente. `ingredientOf` dice quello della voce: dalla
 * lista, o abbinato in questo schermo (S19). */
export function stockEntries(
  items: ShoppingItem[],
  resolved: Record<string, Resolution>,
  ingredientOf: (item: ShoppingItem) => string | null,
  expiry: Record<string, string>
): StockEntry[] {
  const entries: StockEntry[] = [];
  for (const item of items) {
    const resolution = resolved[item.id];
    const ingredientId = ingredientOf(item);
    if (!resolution || !ingredientId) continue;
    entries.push({
      shopping_item_id: item.id,
      ingredient_id: ingredientId,
      product_id: resolution.kind === "product" ? resolution.product.id : null,
      // sempre presente, mai assente: una riga senza scadenza manda `null`.
      //
      // `||` e non `??`, e la differenza è tutta qui: svuotare il campo data (un
      // Backspace su un segmento basta) lascia la stringa vuota, e `''` non è una
      // data — il backend risponde 422, il messaggio dice «riprova», e il riprova
      // ricostruisce lo stesso corpo identico all'infinito. `PantryRow.commitExpiry`
      // fa la stessa cosa nello stesso modo: le due forme devono restare uguali.
      expires_on: expiry[item.id] || null,
      // sempre presente come la scadenza; `null` per lo sfuso e per ogni prodotto che
      // non è stato scelto a catalogo dopo un codice letto
      barcode: (resolution.kind === "product" && resolution.barcode) || null,
    });
  }
  return entries;
}

/** L'avviso che arriva in Dispensa dopo «Metti in dispensa» (T4, spec T3 §4.3).
 * `checked` è quante voci erano nel carrello: quelle non mandate restano in lista,
 * spuntate. Le voci ancora da comprare non contano — non erano in questa spesa
 * (deciso con Mattia il 2026-09-29). Se sono entrate tutte, della lista non si dice
 * niente. */
export function stockNotice(sent: number, checked: number): string {
  const head = `${sent} in dispensa`;
  const left = checked - sent;
  if (left <= 0) return head;
  return `${head} · ${left} ${left === 1 ? "resta" : "restano"} in lista`;
}
```

In `frontend/src/features/stocking/wording.ts`, in fondo al file (dopo `OTHER_INGREDIENT`, che resta finché il Task 7 non toglie l'ultimo che la usa), aggiungi:

```ts
/** Il prodotto letto o cercato è di un altro ingrediente, e si dice quale (spec T3
 * §4.3): «è di un altro ingrediente» e basta lasciava a chi ha la confezione in mano il
 * compito di indovinare di quale. Non è un guasto: il tono lo sceglie chi la mostra, e
 * non è il rosso. Il nome arriva dal server (`Product.ingredient_name`). */
export function otherIngredient(productName: string, ingredientName: string): string {
  return `«${productName}» è di un altro ingrediente: ${ingredientName}.`;
}

/** Il catalogo: i prodotti che corrispondono alle parole ma sono di altri ingredienti,
 * contati e nominati — senza, sembrerebbe che il catalogo non li conosca. I nomi senza
 * doppioni: tre yogurt sotto «yogurt bianco» sono un ingrediente, non tre. */
export function elsewhereNote(ingredientNames: string[]): string {
  const distinct = [...new Set(ingredientNames)];
  const names = distinct.join(", ");
  if (ingredientNames.length === 1) {
    return `Un altro prodotto corrisponde, ma è di un altro ingrediente: ${names}.`;
  }
  const whose = distinct.length === 1 ? "di un altro ingrediente" : "di altri ingredienti";
  return `Altri ${ingredientNames.length} prodotti corrispondono, ma sono ${whose}: ${names}.`;
}
```

- [ ] **Step 4: Farli passare**

Run: `npx vitest run src/features/stocking/stockingView.test.ts src/features/stocking/wording.test.ts`
Expected: PASS, 14 test in `stockingView.test.ts` e 4 in `wording.test.ts`.

- [ ] **Step 5: Controlli**

Run: `npm run typecheck && npm run lint`
Expected: puliti.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/stocking/stockingView.ts frontend/src/features/stocking/stockingView.test.ts frontend/src/features/stocking/wording.ts frontend/src/features/stocking/wording.test.ts
git commit -m "sistema la spesa: il corpo di «Metti in dispensa», l'avviso e le frasi del «di un altro ingrediente», in funzioni pure"
```

---

### Task 3: Il catalogo — un messaggio per stato, e chi è di un altro ingrediente ha un nome

**Files:**
- Modify: `frontend/src/features/stocking/CatalogSearchPanel.tsx` (riscritto)
- Create: `frontend/src/features/stocking/CatalogSearchPanel.test.tsx`

**Interfaces:**
- Consumes: `elsewhereNote` (Task 2); `Product.ingredient_name` (Task 1); `Button` (`variant`, `icon`, `className`, `onClick`); `IconPencilPlus`.
- Produces: `CatalogSearchPanel` con **le stesse prop di oggi** (`itemLabel`, `ingredientId`, `onPicked`, `onCreateByHand`, `onCancel`). Il Task 7 lo monta dentro la riga.

Gli stati, uno alla volta, ciascuno col suo messaggio:

| Stato | Quando | Cosa si vede |
|---|---|---|
| `hint` | nel campo meno di due lettere | l'esempio «yogurt greco» |
| `searching` | la ricerca del testo non ha ancora risposto | «Cerco…» |
| `failed` | la ricerca non risponde | l'avviso, e «Crea il prodotto a mano» |
| `found` | c'è almeno un prodotto di questo ingrediente | le opzioni; sotto, se ce ne sono, chi è di altri ingredienti |
| `elsewhere` | solo prodotti di altri ingredienti | un messaggio che li nomina, e «Crea il prodotto a mano» |
| `none` | niente | «Nessun prodotto con queste parole…», e «Crea il prodotto a mano» |

- [ ] **Step 1: Scrivere il test che fallisce**

`frontend/src/features/stocking/CatalogSearchPanel.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CatalogSearchPanel } from "./CatalogSearchPanel";
import type { Product } from "../../domain/types";

const FAGE: Product = {
  id: "p1", ingredient_id: "i1", ingredient_name: "yogurt greco", name: "Total 0%", brand: "Fage",
  barcode: "52010", source: "openfoodfacts", nutrients: null, image_url: null,
};
const BURRO: Product = {
  id: "p2", ingredient_id: "i8", ingredient_name: "burro", name: "Burro greco", brand: null,
  barcode: null, source: "custom", nutrients: null, image_url: null,
};
const LATTE: Product = {
  id: "p3", ingredient_id: "i9", ingredient_name: "latte", name: "Latte greco", brand: null,
  barcode: null, source: "custom", nutrients: null, image_url: null,
};

/** La ricerca a catalogo risponde sempre la stessa cosa, o non risponde. */
function stubSearch(found: Product[] | "down") {
  const spy = vi.fn((_url: unknown) =>
    Promise.resolve(
      found === "down"
        ? new Response(JSON.stringify({ detail: "giù" }), { status: 500 })
        : new Response(JSON.stringify(found), { status: 200 })
    )
  );
  vi.stubGlobal("fetch", spy);
  return spy;
}

function renderPanel() {
  const props = { onPicked: vi.fn(), onCreateByHand: vi.fn(), onCancel: vi.fn() };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <CatalogSearchPanel itemLabel="yogurt greco" ingredientId="i1" {...props} />
    </QueryClientProvider>
  );
  return props;
}

const HINT = /Scrivi il nome o la marca/;

describe("CatalogSearchPanel", () => {
  it("si apre già cercando il nome della voce, e offre i prodotti del suo ingrediente", async () => {
    const spy = stubSearch([FAGE]);
    const { onPicked } = renderPanel();
    await userEvent.click(await screen.findByRole("option", { name: /Total 0% Fage/ }));
    expect(onPicked).toHaveBeenCalledWith(FAGE);
    expect(String(spy.mock.calls[0][0])).toContain("/products/search?q=yogurt%20greco");
    // l'esempio è l'invito di un campo vuoto: accanto ai risultati sembrava una risposta
    expect(screen.queryByText(HINT)).toBeNull();
  });

  it("l'elenco è un listbox di opzioni, senza voci d'elenco in mezzo", async () => {
    stubSearch([FAGE]);
    renderPanel();
    const listbox = await screen.findByRole("listbox", { name: "Prodotti per «yogurt greco»" });
    expect(within(listbox).getByRole("option", { name: /Total 0%/ }).parentElement).toBe(listbox);
    expect(listbox.querySelector("li")).toBeNull();
  });

  it("svuotato il campo compare l'esempio, e nient'altro", async () => {
    stubSearch([FAGE]);
    renderPanel();
    await screen.findByRole("option", { name: /Total 0%/ });
    await userEvent.clear(screen.getByLabelText("Cerca a catalogo"));
    expect(screen.getByText(HINT)).toBeDefined();
    expect(screen.queryByRole("option")).toBeNull();
    expect(screen.queryByText(/Nessun prodotto/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Crea il prodotto a mano" })).toBeNull();
  });

  it("solo prodotti di altri ingredienti: un messaggio solo, che dice quali, e la creazione a mano", async () => {
    stubSearch([BURRO, LATTE]);
    const { onCreateByHand } = renderPanel();
    const note = await screen.findByText(
      /Altri 2 prodotti corrispondono, ma sono di altri ingredienti: burro, latte\./
    );
    // non è un guasto: niente rosso (dal giro)
    expect(note.className).not.toContain("text-danger");
    expect(screen.queryByText(/Nessun prodotto con queste parole/)).toBeNull();
    expect(screen.queryByRole("option")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Crea il prodotto a mano" }));
    expect(onCreateByHand).toHaveBeenCalled();
  });

  it("niente di niente: «nessun prodotto», e non l'altro messaggio", async () => {
    stubSearch([]);
    renderPanel();
    expect(await screen.findByText(/Nessun prodotto con queste parole/)).toBeDefined();
    expect(screen.queryByText(/di un altro ingrediente|di altri ingredienti/)).toBeNull();
    expect(screen.getByRole("button", { name: "Crea il prodotto a mano" })).toBeDefined();
  });

  it("risultati misti: le opzioni, e sotto chi è di un altro ingrediente, per nome", async () => {
    stubSearch([FAGE, BURRO]);
    renderPanel();
    await screen.findByRole("option", { name: /Total 0%/ });
    expect(screen.queryByRole("option", { name: /Burro greco/ })).toBeNull();
    expect(
      screen.getByText("Un altro prodotto corrisponde, ma è di un altro ingrediente: burro.")
    ).toBeDefined();
  });

  it("una ricerca che non risponde lo dice, e lascia creare a mano", async () => {
    stubSearch("down");
    renderPanel();
    expect(await screen.findByRole("alert")).toHaveTextContent(/non risponde/);
    expect(screen.getByRole("button", { name: "Crea il prodotto a mano" })).toBeDefined();
  });

  it("«Annulla» chiude il pannello", async () => {
    stubSearch([]);
    const { onCancel } = renderPanel();
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(onCancel).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Farlo fallire**

Run: `npx vitest run src/features/stocking/CatalogSearchPanel.test.tsx`
Expected: FAIL — almeno l'esempio che oggi compare sempre, il `listbox` senza nome e con le `li`, «Altri 2 prodotti…» che oggi non nomina gli ingredienti.

- [ ] **Step 3: Riscrivere il componente**

Sostituisci tutto `frontend/src/features/stocking/CatalogSearchPanel.tsx` con:

```tsx
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchProducts } from "./api";
import { elsewhereNote } from "./wording";
import { useDebounced } from "../../hooks/useDebounced";
import { Button } from "../../components/ui/Button";
import { IconPencilPlus } from "../../components/ui/icons";
import type { Product } from "../../domain/types";

const DEBOUNCE_MS = 180;

/**
 * La seconda delle tre strade della spec §8.2: «ricerca a catalogo per nome con
 * affinamento progressivo — da `yogurt greco` a `yogurt greco carrefour pesca`
 * finché non compare la referenza giusta». Serve per il prodotto che si ricompra
 * ogni settimana: è già in catalogo con marca e nutrienti, e senza questa strada
 * l'unico modo di riagganciarlo è riscansionare il codice a barre — che non si può
 * fare se la confezione è già aperta, se il codice è rovinato o se la fotocamera
 * non c'è. L'alternativa, «sfuso», perde la marca e con essa i nutrienti.
 *
 * Il campo parte dal testo della voce di lista, perché l'affinamento è aggiungere
 * parole a quello che si è già scritto (dal giro di T3: da non riprogettare via).
 *
 * Un messaggio per stato (T3 Consegna 3): «altri 2 prodotti, di un altro ingrediente»
 * e «nessun prodotto» a video insieme si contraddicevano, e l'esempio «yogurt greco»
 * compariva anche cercando le uova.
 */
export function CatalogSearchPanel({
  itemLabel,
  ingredientId,
  onPicked,
  onCreateByHand,
  onCancel,
}: {
  itemLabel: string;
  /** L'ingrediente della voce di lista. Filtra i risultati, e non per estetica:
   * `add_pantry_item` (app/repositories/pantry.py) respinge con 409 la coppia
   * (ingrediente, prodotto) incoerente, e la sistemazione è tutto-o-niente —
   * quindi una scelta sbagliata accettata qui farebbe fallire l'intero giro di
   * spesa, comprese le voci risolte bene. Rifiutare dopo aver confermato è
   * peggio che non offrire una scelta che non si può accettare. */
  ingredientId: string;
  onPicked: (product: Product) => void;
  onCreateByHand: () => void;
  onCancel: () => void;
}) {
  const [term, setTerm] = useState(itemLabel);
  const debounced = useDebounced(term, DEBOUNCE_MS).trim();
  const ready = debounced.length >= 2;

  // come ogni altra ricerca dell'app: la chiave porta il termine, quindi una
  // risposta superata non può sovrascrivere una più recente, e un 401 arriva alla
  // QueryCache che riporta all'accesso
  const { data: found = [], isError, isSuccess } = useQuery({
    queryKey: ["products", debounced],
    queryFn: () => searchProducts(debounced),
    enabled: ready,
  });

  const mine = found.filter((product) => product.ingredient_id === ingredientId);
  // di chi sono gli altri: lo dice il server (`ingredient_name`), il client non va a
  // cercarselo
  const elsewhere = found
    .filter((product) => product.ingredient_id !== ingredientId)
    .map((product) => product.ingredient_name);

  // `term` e non `debounced` per l'esempio: svuotato il campo, l'invito compare subito
  const state: "hint" | "searching" | "failed" | "found" | "elsewhere" | "none" =
    term.trim().length < 2
      ? "hint"
      : isError
        ? "failed"
        : !isSuccess
          ? "searching"
          : mine.length > 0
            ? "found"
            : elsewhere.length > 0
              ? "elsewhere"
              : "none";

  return (
    <div className="flex flex-col gap-3 rounded-card border border-line p-3">
      <h3 className="font-semibold">Cerca a catalogo per «{itemLabel}»</h3>
      <label className="text-sm">
        Nome o marca del prodotto
        <input
          aria-label="Cerca a catalogo"
          value={term}
          onChange={(e) => setTerm(e.target.value)}
          className="mt-1.5"
        />
      </label>

      {state === "hint" && (
        <p className="text-sm text-ink-soft">
          Scrivi il nome o la marca, poi aggiungi parole per restringere: «yogurt greco», poi
          «yogurt greco pesca».
        </p>
      )}

      {state === "searching" && <p className="text-sm text-ink-soft">Cerco…</p>}

      {state === "found" && (
        <>
          {/* un listbox contiene opzioni e basta: niente `<ul>/<li>` in mezzo, come in
              OptionList (dal giro di T3) */}
          <div
            role="listbox"
            aria-label={`Prodotti per «${itemLabel}»`}
            className="flex flex-col overflow-hidden rounded-card ring-1 ring-line ring-inset"
          >
            {mine.map((product) => (
              <button
                key={product.id}
                type="button"
                role="option"
                aria-selected={false}
                onClick={() => onPicked(product)}
                className="flex min-h-11 w-full items-baseline gap-2 px-3 py-2.5 text-left text-sm"
              >
                {/* lo spazio esplicito: senza, il nome accessibile del pulsante è
                    "Total 0%Fage", che è quello che legge uno screen reader */}
                <span>{product.name}</span>{" "}
                {product.brand && <span className="text-xs text-ink-soft">{product.brand}</span>}
              </button>
            ))}
          </div>
          {/* perché un prodotto che esiste può non comparire: senza questa riga
              sembrerebbe che il catalogo non lo conosca */}
          {elsewhere.length > 0 && (
            <p className="text-xs text-ink-soft">{elsewhereNote(elsewhere)}</p>
          )}
        </>
      )}

      {state === "elsewhere" && (
        <p className="text-sm text-ink-soft">
          {elsewhereNote(elsewhere)} Per questa voce prova con la marca, oppure crealo adesso.
        </p>
      )}

      {/* "con queste parole", non "in catalogo": la ricerca guarda nome e marca del
          prodotto, e il campo parte dal testo della voce di lista, che per una
          referenza di marca può non comparire da nessuna parte — «Total 0% Fage»
          non contiene «yogurt greco». Dire che il catalogo è vuoto sarebbe un
          verdetto sbagliato sulla prima schermata del pannello. */}
      {state === "none" && (
        <p className="text-sm text-ink-soft">
          Nessun prodotto con queste parole: la ricerca guarda nome e marca, prova con la
          marca. Oppure crealo adesso, leggi il codice a barre, o conferma la voce come sfusa.
        </p>
      )}

      {/* anche qui la rete può essere giù, e il catalogo è solo una delle tre
          strade: dirlo senza togliere le altre */}
      {state === "failed" && (
        <p role="alert" className="text-sm text-danger">
          La ricerca a catalogo non risponde. Riprova, oppure crea il prodotto a mano.
        </p>
      )}

      {(state === "none" || state === "elsewhere" || state === "failed") && (
        <Button icon={IconPencilPlus} onClick={onCreateByHand} className="self-start">
          Crea il prodotto a mano
        </Button>
      )}

      <Button variant="ghost" onClick={onCancel} className="self-start">
        Annulla
      </Button>
    </div>
  );
}
```

- [ ] **Step 4: Farlo passare, con lo schermo che lo usa**

Run: `npx vitest run src/features/stocking`
Expected: PASS — 8 test nuovi in `CatalogSearchPanel.test.tsx`, e `StockingScreen.test.tsx` ancora verde (il catalogo ha le stesse prop, gli stessi nomi «Cerca a catalogo», «Crea il prodotto a mano», «Annulla», e le frasi che quei test cercano: «Nessun prodotto con queste parole», «di un altro ingrediente»). Se un test dello schermo cerca il vecchio `ul[role=listbox]`, fermati e scrivilo nel report: nessuno dovrebbe.

Run: `npm run typecheck && npm run lint`
Expected: puliti.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/stocking/CatalogSearchPanel.tsx frontend/src/features/stocking/CatalogSearchPanel.test.tsx
git commit -m "sistema la spesa: il catalogo dà un messaggio per stato, e dice di quale ingrediente sono gli altri prodotti"
```

---

### Task 4: Il pannello del codice — per quale voce, «Cerca», i numeri, e la strada a mano senza fotocamera (S10)

**Files:**
- Modify: `frontend/src/features/stocking/BarcodeScanner.tsx` (`onUnavailable`, `children`)
- Modify: `frontend/src/features/stocking/BarcodeScanner.test.tsx` (due test in fondo)
- Create: `frontend/src/features/stocking/ScannerPanel.tsx`
- Create: `frontend/src/features/stocking/ScannerPanel.test.tsx`

**Interfaces:**
- Consumes: `lookupBarcode` da `./api`; `otherIngredient` (Task 2); `ProductSuggestion` da `./CustomProductForm`; `Alert`, `Button`, `buttonClasses`, `IconPencilPlus`.
- Produces:
  - `BarcodeScanner({ onDetected, onCancel, onUnavailable?, children? })` — `onUnavailable` si chiama una volta quando la fotocamera manca o è negata; `children` si disegnano fra la fotocamera e «Annulla». **`onDetected` e `onUnavailable` devono essere stabili** (l'effetto della fotocamera ne dipende).
  - `ScannerPanel({ item, ingredientId, onProduct, onNewCode, onUnlinkedCode, onCreateByHand, onCancel })`:
    - `onProduct(product: Product)` — il codice ha trovato un prodotto del catalogo **di questo ingrediente**;
    - `onNewCode(code: string, suggestion: ProductSuggestion | null)` — un codice nuovo al catalogo, che si è deciso di usare;
    - `onUnlinkedCode(code: string | null)` — il codice letto resta alla voce (S8), o se ne va;
    - `onCreateByHand(code: string, lookedUp?: "failed")` — «Crea il prodotto a mano»: `code` è `""` quando non c'è un codice fallito da portare;
    - `onCancel()`.
  Il Task 7 lo monta dentro la riga.

La logica del lookup (la guardia del 409, la cifra di controllo di S20, il codice di S8) si sposta qui da `StockingScreen.tsx` **così com'è**, e da qui in poi vive solo qui: il Task 7 la toglie dallo schermo. Il codice scritto a mano sta nello stato del pannello, che nasce e muore con lui: il residuo di un'altra voce (il difetto che `openScanner` correggeva svuotando il campo) non può più esistere.

- [ ] **Step 1: I test nuovi dello scanner**

In fondo al `describe("BarcodeScanner", …)` di `frontend/src/features/stocking/BarcodeScanner.test.tsx` aggiungi:

```tsx
  it("senza fotocamera lo dice anche a chi lo ospita, che offre la strada a mano (S10)", async () => {
    vi.stubGlobal("navigator", {
      mediaDevices: { getUserMedia: vi.fn().mockRejectedValue(new Error("NotFoundError")) },
    });
    const onUnavailable = vi.fn();
    render(<BarcodeScanner onDetected={vi.fn()} onCancel={vi.fn()} onUnavailable={onUnavailable} />);
    await vi.waitFor(() => expect(onUnavailable).toHaveBeenCalledTimes(1));
  });

  it("quel che gli si mette dentro sta prima di «Annulla», che chiude in fondo (S10)", () => {
    // un permesso che non arriva mai: qui conta solo l'ordine
    vi.stubGlobal("navigator", {
      mediaDevices: { getUserMedia: vi.fn(() => new Promise(() => {})) },
    });
    render(
      <BarcodeScanner onDetected={vi.fn()} onCancel={vi.fn()}>
        <p>il campo del codice</p>
      </BarcodeScanner>
    );
    const campo = screen.getByText("il campo del codice");
    const annulla = screen.getByRole("button", { name: "Annulla" });
    expect(campo.compareDocumentPosition(annulla) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
```

- [ ] **Step 2: Farli fallire**

Run: `npx vitest run src/features/stocking/BarcodeScanner.test.tsx`
Expected: FAIL, i due test nuovi (`onUnavailable` mai chiamata; `children` non disegnati); gli altri 9 verdi.

- [ ] **Step 3: Lo scanner**

In `frontend/src/features/stocking/BarcodeScanner.tsx`:

1. La prima riga diventa `import { useEffect, useRef, useState, type ReactNode } from "react";`.
2. La firma diventa:
   ```tsx
   export function BarcodeScanner({
     onDetected,
     onCancel,
     onUnavailable,
     children,
   }: {
     onDetected: (code: string) => void;
     onCancel: () => void;
     /** La fotocamera non c'è, o è stata negata. Chi ospita lo scanner offre allora la
      * strada a mano (S10: il pannello la prometteva senza darla). Deve essere stabile,
      * come `onDetected`: l'effetto della fotocamera ne dipende, e un'identità nuova a
      * ogni disegno la spegnerebbe e riaccenderebbe. */
     onUnavailable?: () => void;
     /** Quel che sta fra la fotocamera e «Annulla»: il codice scritto a mano, e ciò che
      * ne segue. Così «Annulla» chiude il pannello in fondo invece di stare in mezzo
      * (S10). */
     children?: ReactNode;
   }) {
   ```
3. Nel `catch` di `start()`, sostituisci
   ```tsx
           if (!wasReleased) setError("Fotocamera non disponibile. Puoi inserire il prodotto a mano.");
   ```
   con
   ```tsx
           if (!wasReleased) {
             setError("Fotocamera non disponibile. Puoi inserire il prodotto a mano.");
             onUnavailable?.();
           }
   ```
4. Le dipendenze dell'effetto passano da `}, [onDetected]);` a `}, [onDetected, onUnavailable]);`.
5. Nel `return`, fra il blocco `{error ? (…) : (<video …/>)}` e il `<button>` «Annulla», aggiungi `{children}`.

La frase «Fotocamera non disponibile. Puoi inserire il prodotto a mano.» non cambia: ora la strada c'è, ed è il pulsante che `ScannerPanel` mette sotto.

Run: `npx vitest run src/features/stocking/BarcodeScanner.test.tsx`
Expected: PASS, 11 test.

- [ ] **Step 4: Il test del pannello**

`frontend/src/features/stocking/ScannerPanel.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ScannerPanel } from "./ScannerPanel";
import type { BarcodeLookup, Product, ShoppingItem } from "../../domain/types";

const YOGURT: ShoppingItem = {
  id: "s1", raw_text: "yogurt greco", ingredient_id: "i1", ingredient_name: "yogurt greco",
  ingredient_category: "latticini", ingredient_kind: "food", status: "checked", reason: "manual",
  created_at: "2026-09-29T10:00:00Z",
};
const FAGE: Product = {
  id: "p1", ingredient_id: "i1", ingredient_name: "yogurt greco", name: "Total 0%", brand: "Fage",
  barcode: "52010", source: "openfoodfacts", nutrients: null, image_url: null,
};
// il caso di S9 visto dall'altra parte: un parmigiano registrato sotto «burro»
const PARMIGIANO: Product = {
  id: "p2", ingredient_id: "i8", ingredient_name: "burro", name: "Parmigiano Reggiano",
  brand: null, barcode: "8009876543217", source: "custom", nutrients: null, image_url: null,
};

function lookup(over: Partial<BarcodeLookup>): BarcodeLookup {
  return { found: false, origin: "unknown", product: null, suggestion: null, valid_checksum: true, ...over };
}

/** Il lookup risponde sempre lo stesso esito, o non risponde. */
function stubLookup(answer: BarcodeLookup | "down") {
  const spy = vi.fn((_url: unknown) =>
    Promise.resolve(
      answer === "down"
        ? new Response(JSON.stringify({ detail: "giù" }), { status: 500 })
        : new Response(JSON.stringify(answer), { status: 200 })
    )
  );
  vi.stubGlobal("fetch", spy);
  return spy;
}

function renderPanel() {
  const props = {
    onProduct: vi.fn(), onNewCode: vi.fn(), onUnlinkedCode: vi.fn(), onCreateByHand: vi.fn(),
    onCancel: vi.fn(),
  };
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <ScannerPanel item={YOGURT} ingredientId="i1" {...props} />
    </QueryClientProvider>
  );
  return props;
}

describe("ScannerPanel", () => {
  it("il titolo dice per quale voce è aperto (S10)", () => {
    stubLookup(lookup({}));
    renderPanel();
    expect(screen.getByRole("heading", { name: "Codice a barre per «yogurt greco»" })).toBeDefined();
  });

  it("il campo del codice chiede la tastiera dei numeri (S10)", () => {
    stubLookup(lookup({}));
    renderPanel();
    expect(screen.getByLabelText("Codice a barre")).toHaveAttribute("inputmode", "numeric");
  });

  it("«Cerca» cerca il codice scritto, senza bisogno dell'Invio (S10)", async () => {
    const spy = stubLookup(lookup({ found: true, origin: "catalog", product: FAGE }));
    const { onProduct } = renderPanel();
    await userEvent.type(screen.getByLabelText("Codice a barre"), "52010");
    await userEvent.click(screen.getByRole("button", { name: "Cerca" }));
    await waitFor(() => expect(onProduct).toHaveBeenCalledWith(FAGE));
    expect(String(spy.mock.calls[0][0])).toContain("/products/barcode/52010");
  });

  it("l'Invio cerca anche lui, e non arriva a nessun altro pulsante", async () => {
    stubLookup(lookup({ found: true, origin: "catalog", product: FAGE }));
    const { onProduct } = renderPanel();
    const field = screen.getByLabelText("Codice a barre");
    await userEvent.type(field, "52010");
    // `false`: l'evento è stato annullato (`preventDefault`)
    expect(fireEvent.keyDown(field, { key: "Enter" })).toBe(false);
    await waitFor(() => expect(onProduct).toHaveBeenCalledWith(FAGE));
  });

  it("un campo vuoto non cerca niente", async () => {
    const spy = stubLookup(lookup({}));
    renderPanel();
    await userEvent.click(screen.getByRole("button", { name: "Cerca" }));
    expect(spy).not.toHaveBeenCalled();
  });

  it("mentre cerca, «Cerca» si spegne ma tiene il fuoco, e non parte una seconda ricerca", async () => {
    let release: (response: Response) => void = () => {};
    const spy = vi.fn(() => new Promise<Response>((resolve) => { release = resolve; }));
    vi.stubGlobal("fetch", spy);
    renderPanel();
    await userEvent.type(screen.getByLabelText("Codice a barre"), "52010");
    const cerca = screen.getByRole("button", { name: "Cerca" });
    await userEvent.click(cerca);
    await waitFor(() => expect(cerca).toHaveAttribute("aria-disabled", "true"));
    // `aria-disabled` e non `disabled`: un pulsante che diventa `disabled` perde il fuoco
    expect(cerca).not.toBeDisabled();
    await userEvent.click(cerca);
    expect(spy).toHaveBeenCalledTimes(1);
    release(new Response(JSON.stringify(lookup({})), { status: 200 }));
  });

  it("senza fotocamera offre di creare il prodotto a mano, e ci porta (S10)", async () => {
    stubLookup(lookup({}));
    const { onCreateByHand } = renderPanel();
    // jsdom non ha fotocamera: è il caso del telefono che la nega
    await userEvent.click(await screen.findByRole("button", { name: "Crea il prodotto a mano" }));
    expect(onCreateByHand).toHaveBeenCalledWith("", undefined);
  });

  it("il prodotto di un altro ingrediente non si aggancia, e si dice quale, senza allarme", async () => {
    stubLookup(lookup({ found: true, origin: "catalog", product: PARMIGIANO }));
    const { onProduct, onUnlinkedCode } = renderPanel();
    await userEvent.type(screen.getByLabelText("Codice a barre"), "8009876543217{Enter}");
    const note = await screen.findByText(/è di un altro ingrediente: burro\./);
    expect(note).toHaveTextContent("«Parmigiano Reggiano» è di un altro ingrediente: burro.");
    expect(note).not.toHaveAttribute("role", "alert");
    expect(note.className).not.toContain("text-danger");
    expect(onProduct).not.toHaveBeenCalled();
    // il codice è già di un altro prodotto: non segue la voce (S8)
    expect(onUnlinkedCode).toHaveBeenCalledWith(null);
  });

  it("un codice nuovo va avanti con quel che Open Food Facts ne sa", async () => {
    const suggestion = {
      name: "Spaghetti n.5", brand: "Barilla", barcode: "8076800195057", nutrients: {},
      image_url: null,
    };
    stubLookup(lookup({ found: true, origin: "openfoodfacts", suggestion }));
    const { onNewCode } = renderPanel();
    await userEvent.type(screen.getByLabelText("Codice a barre"), "8076800195057{Enter}");
    await waitFor(() => expect(onNewCode).toHaveBeenCalledWith("8076800195057", suggestion));
  });

  it("un codice che non torna si ferma qui, correggibile, e si può usare lo stesso (S20)", async () => {
    stubLookup(lookup({ valid_checksum: false }));
    const { onNewCode } = renderPanel();
    const field = screen.getByLabelText("Codice a barre");
    await userEvent.type(field, "1234{Enter}");
    expect(await screen.findByText("Questo codice non torna: ricontrollalo.")).toBeDefined();
    expect(field).toHaveValue("1234");
    expect(onNewCode).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Usa questo codice lo stesso" }));
    expect(onNewCode).toHaveBeenCalledWith("1234", null);
  });

  it("un lookup fallito lo dice, tiene il codice, e offre la creazione a mano una volta sola", async () => {
    stubLookup("down");
    const { onCreateByHand, onUnlinkedCode } = renderPanel();
    await userEvent.type(screen.getByLabelText("Codice a barre"), "52010{Enter}");
    expect(await screen.findByText(/non sono riuscito a leggere il codice/i)).toBeDefined();
    expect(screen.getByLabelText("Codice a barre")).toHaveValue("52010");
    expect(onUnlinkedCode).toHaveBeenCalledWith("52010");
    // senza fotocamera il pulsante c'era già: resta uno, e ora porta il codice
    const create = screen.getAllByRole("button", { name: "Crea il prodotto a mano" });
    expect(create).toHaveLength(1);
    await userEvent.click(create[0]);
    expect(onCreateByHand).toHaveBeenCalledWith("52010", "failed");
  });

  it("«Annulla» chiude il pannello, ed è in fondo", async () => {
    stubLookup(lookup({}));
    const { onCancel } = renderPanel();
    const annulla = screen.getByRole("button", { name: "Annulla" });
    const field = screen.getByLabelText("Codice a barre");
    expect(field.compareDocumentPosition(annulla) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    await userEvent.click(annulla);
    expect(onCancel).toHaveBeenCalled();
  });
});
```

- [ ] **Step 5: Farlo fallire**

Run: `npx vitest run src/features/stocking/ScannerPanel.test.tsx`
Expected: FAIL, `Failed to resolve import "./ScannerPanel"`.

- [ ] **Step 6: Scrivere il pannello**

`frontend/src/features/stocking/ScannerPanel.tsx`:

```tsx
import { useCallback, useId, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { BarcodeScanner } from "./BarcodeScanner";
import type { ProductSuggestion } from "./CustomProductForm";
import { lookupBarcode } from "./api";
import { otherIngredient } from "./wording";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { IconPencilPlus } from "../../components/ui/icons";
import type { Product, ShoppingItem } from "../../domain/types";

/** Il pannello del codice a barre di una voce (spec T3 §4.3, S10): la fotocamera, il
 * codice scritto a mano con «Cerca», e ciò che il lookup risponde.
 *
 * Qui vivono, e solo qui, le guardie del codice: il prodotto di un altro ingrediente
 * che non si aggancia (il 409 della sistemazione tutto-o-niente), la cifra di controllo
 * che non torna (S20), il codice che segue o non segue la voce (S8). Il codice scritto
 * è stato di questo pannello, che nasce e muore con lui: quello di un'altra voce non
 * può restare nel campo. */
export function ScannerPanel({
  item,
  ingredientId,
  onProduct,
  onNewCode,
  onUnlinkedCode,
  onCreateByHand,
  onCancel,
}: {
  item: ShoppingItem;
  /** L'ingrediente della voce, dalla lista o abbinato in questo schermo: la guardia
   * qui sotto ci confronta il prodotto che il codice trova. */
  ingredientId: string;
  /** Il codice ha trovato un prodotto del catalogo, di questo ingrediente. */
  onProduct: (product: Product) => void;
  /** Un codice nuovo al catalogo, che si è deciso di usare: se Open Food Facts lo
   * conosce prima si chiede se è l'ingrediente della voce (S20), se no il modulo. */
  onNewCode: (code: string, suggestion: ProductSuggestion | null) => void;
  /** Il codice letto resta alla voce (S8), o se ne va (`null`). */
  onUnlinkedCode: (code: string | null) => void;
  /** «Crea il prodotto a mano»: senza fotocamera (`code` vuoto), o dopo un lookup
   * fallito (`code` letto, `lookedUp` "failed"). */
  onCreateByHand: (code: string, lookedUp?: "failed") => void;
  onCancel: () => void;
}) {
  const codeId = useId();
  const [manualCode, setManualCode] = useState("");
  const [cameraMissing, setCameraMissing] = useState(false);
  // un codice letto che porta al prodotto di un altro ingrediente: non è una
  // risoluzione, è la ragione per cui non c'è
  const [mismatch, setMismatch] = useState<Product | null>(null);
  // un codice nuovo al catalogo la cui cifra di controllo non torna: si ferma qui,
  // correggibile, finché chi l'ha letto non lo usa lo stesso
  const [badCode, setBadCode] = useState<
    { code: string; suggestion: ProductSuggestion | null } | null
  >(null);

  // Il lookup passa da una mutazione e non da una chiamata nuda per due ragioni: un
  // errore non resta una promise rifiutata che nessuno guarda (prima, con la rete giù,
  // premere Invio non faceva assolutamente niente), e un 401 passa dalla MutationCache
  // di App.tsx, cioè riporta all'accesso come ogni altra scrittura.
  const lookup = useMutation({
    mutationFn: (code: string) => lookupBarcode(code),
    // gli avvisi parlavano del codice di prima: con uno nuovo in volo non valgono più
    onMutate: () => {
      setBadCode(null);
      setMismatch(null);
    },
    onSuccess: (result, code) => {
      const product = result.product;
      // un codice che ha già il suo prodotto non segue la voce altrove, neanche
      // quando quel prodotto è di un altro ingrediente: darlo a un prodotto nuovo
      // sarebbe un 409, e a uno scelto a catalogo un furto che il backend rifiuta.
      // Uno nuovo al catalogo lo ricorda chi riceve `onNewCode`, quando si decide di
      // usarlo
      onUnlinkedCode(null);
      if (product && product.ingredient_id !== ingredientId) {
        // `GET /products/barcode/{code}` cerca per codice e basta, quindi la referenza
        // che torna può essere di un altro ingrediente. Adottarla faceva fallire con
        // 409 l'intera sistemazione — che è tutto-o-niente — comprese le voci risolte
        // bene. Il controllo del backend resta l'ultima difesa; l'interfaccia non deve
        // arrivarci.
        setMismatch(product);
        return;
      }
      // un prodotto del catalogo si aggancia anche se la cifra di controllo non torna:
      // qualcuno l'ha già confermato con la confezione in mano
      if (product) {
        onProduct(product);
        return;
      }
      if (result.valid_checksum === false) {
        // S20: `1234` apriva la creazione di un prodotto sotto un codice che nessuna
        // confezione porta. Il codice resta nel campo, correggibile — uno letto dalla
        // fotocamera ci arriva adesso — e «Usa questo codice lo stesso» lascia andare
        // avanti: i codici interni di negozio esistono.
        setBadCode({ code, suggestion: result.suggestion });
        setManualCode(code);
        return;
      }
      onNewCode(code, result.suggestion);
    },
    // il codice è stato letto anche se il lookup no: la creazione a mano lo porta, e
    // il catalogo pure (S8). Se poi risultasse di un altro prodotto, il backend non lo
    // sposta
    onError: (_error, code) => onUnlinkedCode(code),
  });
  const { mutate: lookupCode } = lookup;
  const failedCode = lookup.isError ? (lookup.variables ?? null) : null;

  // Stabili: l'effetto della fotocamera dipende da tutti e due, e un'identità nuova a
  // ogni tasto premuto nel campo la spegnerebbe e riaccenderebbe a ogni carattere.
  // `mutate` di react-query è già stabile.
  const handleDetected = useCallback((code: string) => lookupCode(code), [lookupCode]);
  const markCameraMissing = useCallback(() => setCameraMissing(true), []);

  function search() {
    const code = manualCode.trim();
    // la guardia al posto di `disabled`: il pulsante resta dov'è il fuoco
    if (code === "" || lookup.isPending) return;
    lookupCode(code);
  }

  return (
    <div className="flex flex-col gap-3 rounded-card border border-line p-3">
      {/* il nome della voce nel titolo: prima stava solo nel testo per lo screen reader
          del pulsante che apre il pannello, e arrivati qui non si sapeva più cosa si
          stava scansionando (S10) */}
      <h3 className="font-semibold">Codice a barre per «{item.raw_text}»</h3>
      <BarcodeScanner
        onDetected={handleDetected}
        onCancel={onCancel}
        onUnavailable={markCameraMissing}
      >
        <div className="flex flex-col gap-1.5">
          <label htmlFor={codeId} className="text-sm">
            Codice a barre
          </label>
          <div className="flex gap-2">
            {/* `inputMode="numeric"`: tredici cifre sulla tastiera delle lettere erano
                il secondo dettaglio di S10 */}
            <input
              id={codeId}
              inputMode="numeric"
              autoComplete="off"
              value={manualCode}
              onChange={(e) => setManualCode(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  search();
                }
              }}
              className="min-w-0 flex-1"
            />
            <button
              type="button"
              aria-disabled={lookup.isPending || undefined}
              onClick={search}
              className={`${buttonClasses("secondary")} shrink-0 aria-disabled:opacity-40`}
            >
              Cerca
            </button>
          </div>
        </div>

        {lookup.isPending && <p className="text-sm text-ink-soft">Cerco il codice…</p>}

        {/* il codice esiste in catalogo, ma sotto un altro ingrediente: si dice quale, e
            non in rosso — non è un guasto (spec T3 §4.3). Nessuna risoluzione: le tre
            icone della voce sono ancora là sopra */}
        {mismatch && (
          <p role="status" className="text-sm text-ink">
            {otherIngredient(mismatch.name, mismatch.ingredient_name)} Qui non si aggancia:
            leggi un altro codice, cercalo a catalogo, oppure conferma «{item.raw_text}» come
            sfuso.
          </p>
        )}

        {badCode && (
          <div className="flex flex-col items-start gap-2">
            <Alert>Questo codice non torna: ricontrollalo.</Alert>
            <Button onClick={() => onNewCode(badCode.code, badCode.suggestion)}>
              Usa questo codice lo stesso
            </Button>
          </div>
        )}

        {/* anche il fallimento di rete degrada al manuale: un errore muto qui era il
            muro più silenzioso dello schermo */}
        {failedCode !== null && (
          <p role="alert" className="text-sm text-danger">
            Non sono riuscito a leggere il codice. Riprova, oppure crea il prodotto a mano.
          </p>
        )}

        {/* senza fotocamera il pannello prometteva «Puoi inserire il prodotto a mano» e
            non offriva quella strada (S10). Un pulsante solo anche a lookup fallito: lì
            porta il codice che non si è potuto cercare */}
        {(cameraMissing || failedCode !== null) && (
          <Button
            icon={IconPencilPlus}
            onClick={() =>
              onCreateByHand(failedCode ?? "", failedCode !== null ? "failed" : undefined)
            }
            className="self-start"
          >
            Crea il prodotto a mano
          </Button>
        )}
      </BarcodeScanner>
    </div>
  );
}
```

- [ ] **Step 7: Farlo passare**

Run: `npx vitest run src/features/stocking`
Expected: PASS — 12 test in `ScannerPanel.test.tsx`, 11 in `BarcodeScanner.test.tsx`, e `StockingScreen.test.tsx` verde (lo schermo non usa ancora il pannello, e le prop nuove dello scanner sono facoltative).

Run: `npm run typecheck && npm run lint`
Expected: puliti. Se `react-hooks` segnala le dipendenze di `useCallback`, controlla di non aver scritto `lookup.mutate` al posto di `lookupCode`: la regola vuole la funzione destrutturata.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/features/stocking/BarcodeScanner.tsx frontend/src/features/stocking/BarcodeScanner.test.tsx frontend/src/features/stocking/ScannerPanel.tsx frontend/src/features/stocking/ScannerPanel.test.tsx
git commit -m "sistema la spesa: il pannello del codice dice per quale voce, ha «Cerca» e i numeri, e senza fotocamera porta al modulo"
```

---

### Task 5: «Abbina» — il selettore unico, e il nome generico dell'ingrediente nuovo

**Files:**
- Modify: `frontend/src/components/IngredientPicker.tsx` (`createWhen`)
- Modify: `frontend/src/components/IngredientPicker.test.tsx` (tre test)
- Create: `frontend/src/features/stocking/NewIngredientFields.tsx`
- Create: `frontend/src/features/stocking/NewIngredientFields.test.tsx`
- Create: `frontend/src/features/stocking/MatchPanel.tsx`
- Create: `frontend/src/features/stocking/MatchPanel.test.tsx`

**Interfaces:**
- Consumes: `IngredientPicker` (prop `label`, `accessibleLabel`, `failureNote`, `onPick`, `onCreate`, `initialTerm`, `autoFocus`); `createIngredient` da `../shopping-list/api`; `ApiError` da `../../api/client`; `FOOD_CATEGORIES`, `NON_FOOD_CATEGORIES` da `../../domain/categories`; `Alert`, `Button`, `buttonClasses`.
- Produces:
  - `IngredientPicker` accetta `createWhen?: "empty" | "always"` (di norma `"empty"`, cioè com'è oggi).
  - `NewIngredientFields({ initialName, busy, onSubmit, onCancel })` — `onSubmit({ name, category })` col nome già senza spazi ai lati. Nessuna chiamata di rete: la creazione la fa chi lo usa. È il pezzo che R12 riuserà.
  - `MatchPanel({ item, onMatched, onCancel })` — `onMatched(ingredient: Ingredient)` quando si sceglie un suggerimento, quando la creazione riesce, e quando il 409 riporta l'omonimo (S19). Il Task 7 lo monta dentro la riga.

Il nome accessibile del campo resta «Abbina un ingrediente per X», come oggi. **Attenzione nei test:** `getByLabelText(/Abbina un ingrediente/)` troverebbe anche l'elenco dei suggerimenti, che `OptionList` chiama «Suggerimenti: Abbina un ingrediente per X»; si cerca il campo per ruolo, `getByRole("textbox", { name: "Abbina un ingrediente per X" })`.

- [ ] **Step 1: I test del selettore**

In fondo al `describe("IngredientPicker", …)` di `frontend/src/components/IngredientPicker.test.tsx` aggiungi:

```tsx
  // S6: in «Sistema la spesa» la creazione non può dipendere dal vuoto — «cera per
  // pavimenti» pescava sette suggerimenti, `Pera` in testa, e la porta spariva
  it("con createWhen «always» offre di aggiungere anche accanto ai suggerimenti", async () => {
    stubRoutedFetch(() => [[LATTE], 200]);
    const onCreate = vi.fn();
    renderWithClient(
      <IngredientPicker label="Ingrediente" failureNote="x" onPick={() => {}} onCreate={onCreate} createWhen="always" />
    );
    fireEvent.change(screen.getByLabelText("Ingrediente"), { target: { value: "latte di capra" } });
    await screen.findByRole("option", { name: "Latte" });
    fireEvent.click(await screen.findByRole("button", { name: "Aggiungi «latte di capra»" }));
    expect(onCreate).toHaveBeenCalledWith("latte di capra");
  });

  it("con createWhen «always» offre di aggiungere anche se la ricerca non risponde", async () => {
    stubRoutedFetch(() => [{ detail: "giù" }, 500]);
    renderWithClient(
      <IngredientPicker label="Ingrediente" failureNote="x" onPick={() => {}} onCreate={() => {}} createWhen="always" />
    );
    fireEvent.change(screen.getByLabelText("Ingrediente"), { target: { value: "cera" } });
    expect(await screen.findByRole("button", { name: "Aggiungi «cera»" })).toBeDefined();
  });

  it("di norma accanto ai suggerimenti non offre di aggiungere: resta com'era", async () => {
    stubRoutedFetch(() => [[LATTE], 200]);
    renderWithClient(
      <IngredientPicker label="Ingrediente" failureNote="x" onPick={() => {}} onCreate={() => {}} />
    );
    fireEvent.change(screen.getByLabelText("Ingrediente"), { target: { value: "lat" } });
    await screen.findByRole("option", { name: "Latte" });
    expect(screen.queryByRole("button", { name: /Aggiungi/ })).toBeNull();
  });
```

Run: `npx vitest run src/components/IngredientPicker.test.tsx`
Expected: FAIL, i primi due (nessun «Aggiungi» accanto a un suggerimento o dopo un guasto); il terzo passa già.

- [ ] **Step 2: Il selettore**

In `frontend/src/components/IngredientPicker.tsx`:

1. Nella lista delle prop destrutturate, dopo `onCreate,` aggiungi `createWhen = "empty",`.
2. Nel tipo delle prop, subito dopo la voce `onCreate?: (name: string) => void;`, aggiungi:
   ```tsx
     /** Quando offrire «Aggiungi «…»»: di norma solo a ricerca finita e vuota. Con
      * `"always"` anche accanto ai suggerimenti, e anche se la ricerca non risponde —
      * appena la ricerca del testo scritto ha detto la sua. Lo chiede «Sistema la
      * spesa» (S6): lì una voce spaiata deve poter diventare un ingrediente anche se il
      * suo nome pesca «Pera» per «cera per pavimenti». */
     createWhen?: "empty" | "always";
   ```
3. Subito sotto la riga `const emptySearch = searchedIsTyped && isSuccess && found.length === 0;` aggiungi:
   ```tsx
     // l'offerta vale per il testo che la ricerca ha cercato, mai per uno di prima (S18)
     const offerCreate =
       createWhen === "always" ? searchedIsTyped && (isSuccess || isError) : emptySearch;
   ```
4. Sostituisci la condizione `{onCreate && emptySearch && (` con `{onCreate && offerCreate && (`.

Il resto non cambia: `emptyNote` compare ancora solo senza `onCreate` e a ricerca vuota.

Run: `npx vitest run src/components/IngredientPicker.test.tsx`
Expected: PASS, tutti (quelli di prima più 3).

- [ ] **Step 3: Il test dei campi dell'ingrediente nuovo**

`frontend/src/features/stocking/NewIngredientFields.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NewIngredientFields } from "./NewIngredientFields";

function renderFields(props: { initialName?: string; busy?: boolean } = {}) {
  const onSubmit = vi.fn();
  const onCancel = vi.fn();
  render(
    <NewIngredientFields
      initialName={props.initialName ?? "zucchine tonde di Nizza"}
      busy={props.busy ?? false}
      onSubmit={onSubmit}
      onCancel={onCancel}
    />
  );
  return { onSubmit, onCancel };
}

describe("NewIngredientFields", () => {
  it("chiede il nome generico con un'etichetta che si vede, e parte dal nome dato", () => {
    renderFields();
    const name = screen.getByLabelText("Come si chiama in generale?") as HTMLInputElement;
    expect(name).toHaveValue("zucchine tonde di Nizza");
    expect(name.labels![0]).not.toHaveClass("sr-only");
  });

  it("crea col nome corretto, senza spazi ai lati, e col reparto scelto", async () => {
    const { onSubmit } = renderFields();
    const name = screen.getByLabelText("Come si chiama in generale?");
    await userEvent.clear(name);
    await userEvent.type(name, "  zucchina  ");
    await userEvent.selectOptions(screen.getByLabelText("Reparto"), "verdura");
    await userEvent.click(screen.getByRole("button", { name: "Crea l'ingrediente" }));
    expect(onSubmit).toHaveBeenCalledWith({ name: "zucchina", category: "verdura" });
  });

  it("chi non sceglie il reparto ottiene «altro», e il non alimentare è offerto a parte", async () => {
    const { onSubmit } = renderFields({ initialName: "cera per pavimenti" });
    const reparto = screen.getByLabelText("Reparto") as HTMLSelectElement;
    expect(reparto.value).toBe("altro");
    expect(reparto.querySelector('optgroup[label="Non alimentari"] option[value="casa"]')).not.toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Crea l'ingrediente" }));
    expect(onSubmit).toHaveBeenCalledWith({ name: "cera per pavimenti", category: "altro" });
  });

  it("l'Invio nel nome crea, come il pulsante", async () => {
    const { onSubmit } = renderFields({ initialName: "zucchina" });
    await userEvent.type(screen.getByLabelText("Come si chiama in generale?"), "{Enter}");
    expect(onSubmit).toHaveBeenCalledWith({ name: "zucchina", category: "altro" });
  });

  it("senza nome non crea, e dice perché", async () => {
    const { onSubmit } = renderFields({ initialName: "   " });
    const create = screen.getByRole("button", { name: "Crea l'ingrediente" });
    expect(create).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText("Scrivi il nome per crearlo.")).toBeDefined();
    await userEvent.click(create);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("mentre crea, il pulsante si spegne ma resta dov'è il fuoco, e non crea due volte", async () => {
    const { onSubmit } = renderFields({ busy: true });
    const create = screen.getByRole("button", { name: "Crea l'ingrediente" });
    expect(create).toHaveAttribute("aria-disabled", "true");
    expect(create).not.toBeDisabled();
    await userEvent.click(create);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("«Annulla» torna indietro senza creare", async () => {
    const { onSubmit, onCancel } = renderFields();
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(onCancel).toHaveBeenCalled();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
```

Run: `npx vitest run src/features/stocking/NewIngredientFields.test.tsx`
Expected: FAIL, `Failed to resolve import "./NewIngredientFields"`.

- [ ] **Step 4: I campi dell'ingrediente nuovo**

`frontend/src/features/stocking/NewIngredientFields.tsx`:

```tsx
import { useId, useState, type FormEvent } from "react";
import { Button } from "../../components/ui/Button";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { FOOD_CATEGORIES, NON_FOOD_CATEGORIES } from "../../domain/categories";

/** Il passo che crea un ingrediente nuovo: come si chiama in generale, e in che
 * reparto (spec T3 §4.3). Il nome parte da quel che gli si dà — il testo della voce —
 * ma è un campo da correggere: dal giro, «zucchine tonde di Nizza della signora Pina»
 * diventava il nome dell'ingrediente, e con lui ogni ricerca e ogni ricetta.
 *
 * Solo i campi: la creazione la fa chi lo usa, perché «Sistema la spesa» chiama
 * `POST /ingredients` e il modulo della ricetta (R12, Consegna 6) manda nome e reparto
 * dentro la ricetta. Sta in un file suo per quello.
 *
 * Il reparto non si indovina: si chiede. Parte da «altro», che è dove finiva d'ufficio:
 * chi non ha niente da dire fa esattamente quello che faceva prima. */
export function NewIngredientFields({
  initialName,
  busy,
  onSubmit,
  onCancel,
}: {
  initialName: string;
  /** Mentre la creazione è in volo: il pulsante si spegne ma tiene il fuoco. */
  busy: boolean;
  onSubmit: (fields: { name: string; category: string }) => void;
  onCancel: () => void;
}) {
  const nameId = useId();
  const hintId = useId();
  const [name, setName] = useState(initialName);
  const [category, setCategory] = useState<string>("altro");
  const trimmed = name.trim();

  function submit(event: FormEvent) {
    event.preventDefault();
    // l'Invio nel campo invia il modulo anche col pulsante spento: la guardia sta qui
    if (trimmed === "" || busy) return;
    onSubmit({ name: trimmed, category });
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <div className="flex flex-col gap-1.5">
        <label htmlFor={nameId} className="text-sm font-medium">
          Come si chiama in generale?
        </label>
        <input
          id={nameId}
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          aria-describedby={hintId}
        />
        <p id={hintId} className="text-xs text-ink-soft">
          Il nome che scriveresti in lista: «zucchine», non «zucchine tonde di Nizza».
        </p>
      </div>
      <label className="text-sm">
        Reparto
        <select
          aria-label="Reparto"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="mt-1.5"
        >
          {FOOD_CATEGORIES.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
          {/* staccati, perché sono un'altra cosa: non è un reparto in più del
              supermercato, è la metà dell'anagrafica che le ricette non vedono */}
          <optgroup label="Non alimentari">
            {NON_FOOD_CATEGORIES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </optgroup>
        </select>
      </label>
      <div>
        {/* `aria-disabled` e non `disabled`: mentre la creazione è in volo il fuoco
            resta qui invece di cadere sul `body` */}
        <button
          type="submit"
          aria-disabled={busy || trimmed === "" || undefined}
          className={`${buttonClasses("primary", "block")} aria-disabled:opacity-40`}
        >
          Crea l'ingrediente
        </button>
        {/* un pulsante spento e muto non si spiega da sé */}
        {trimmed === "" && (
          <p className="pt-2 text-xs text-ink-soft">Scrivi il nome per crearlo.</p>
        )}
      </div>
      <Button variant="ghost" onClick={onCancel} className="self-start">
        Annulla
      </Button>
    </form>
  );
}
```

Run: `npx vitest run src/features/stocking/NewIngredientFields.test.tsx`
Expected: PASS, 7 test.

- [ ] **Step 5: Il test del pannello «Abbina»**

`frontend/src/features/stocking/MatchPanel.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MatchPanel } from "./MatchPanel";
import type { Ingredient, ShoppingItem } from "../../domain/types";

const ITEM: ShoppingItem = {
  id: "s3", raw_text: "cera per pavimenti", ingredient_id: null, ingredient_name: null,
  ingredient_category: null, ingredient_kind: null, status: "checked", reason: "manual",
  created_at: "2026-09-29T10:00:00Z",
};
const PERA: Ingredient = { id: "i7", name: "pera", display_name: "Pera", category: "frutta", kind: "food" };
const CERA: Ingredient = { id: "i9", name: "cera", display_name: "cera", category: "casa", kind: "non_food" };

type Route = (path: string, init?: RequestInit) => [unknown, number];

/** Un fetch che risponde in base a percorso e metodo, e tiene le chiamate. */
function stubRoutedFetch(route: Route) {
  const spy = vi.fn((input: unknown, init?: RequestInit) => {
    const [body, status] = route(String(input), init);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

const creations = (spy: ReturnType<typeof stubRoutedFetch>) =>
  spy.mock.calls
    .filter(([url, init]) => String(url).endsWith("/ingredients") && init?.method === "POST")
    .map(([, init]) => JSON.parse(String(init?.body)));

function renderPanel() {
  const onMatched = vi.fn();
  const onCancel = vi.fn();
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MatchPanel item={ITEM} onMatched={onMatched} onCancel={onCancel} />
    </QueryClientProvider>
  );
  return { onMatched, onCancel };
}

const FIELD = { name: "Abbina un ingrediente per cera per pavimenti" };
const OFFER = { name: "Aggiungi «cera per pavimenti»" };

describe("MatchPanel", () => {
  it("cerca subito il testo della voce, col fuoco nel campo", async () => {
    stubRoutedFetch(() => [[PERA], 200]);
    renderPanel();
    const field = screen.getByRole("textbox", FIELD);
    expect(field).toHaveValue("cera per pavimenti");
    expect(document.activeElement).toBe(field);
    expect(await screen.findByRole("option", { name: "Pera" })).toBeDefined();
  });

  it("scegliere un suggerimento abbina quello", async () => {
    stubRoutedFetch(() => [[PERA], 200]);
    const { onMatched } = renderPanel();
    await userEvent.click(await screen.findByRole("option", { name: "Pera" }));
    expect(onMatched).toHaveBeenCalledWith(PERA);
  });

  // S6: «cera per pavimenti» pescava sette suggerimenti, `Pera` in testa, e l'unica
  // porta che crea un ingrediente spariva dietro di loro
  it("offre di crearlo anche quando la ricerca trova qualcosa, col nome da correggere", async () => {
    stubRoutedFetch(() => [[PERA], 200]);
    renderPanel();
    await screen.findByRole("option", { name: "Pera" });
    await userEvent.click(screen.getByRole("button", OFFER));
    expect(screen.getByLabelText("Come si chiama in generale?")).toHaveValue("cera per pavimenti");
  });

  it("crea col nome corretto e il reparto scelto, e abbina l'ingrediente nuovo", async () => {
    const spy = stubRoutedFetch((_path, init) => (init?.method === "POST" ? [CERA, 201] : [[], 200]));
    const { onMatched } = renderPanel();
    await userEvent.click(await screen.findByRole("button", OFFER));
    const name = screen.getByLabelText("Come si chiama in generale?");
    await userEvent.clear(name);
    await userEvent.type(name, "cera");
    await userEvent.selectOptions(screen.getByLabelText("Reparto"), "casa");
    await userEvent.click(screen.getByRole("button", { name: "Crea l'ingrediente" }));
    await waitFor(() => expect(onMatched).toHaveBeenCalledWith(CERA));
    // `name` e `display_name` sono lo stesso testo: normalizzare è del backend
    expect(creations(spy)).toEqual([{ name: "cera", display_name: "cera", category: "casa" }]);
  });

  it("un ingrediente che c'è già si aggancia, senza errore (S19)", async () => {
    stubRoutedFetch((_path, init) =>
      init?.method === "POST"
        ? [{ detail: "ingrediente già presente", existing: CERA }, 409]
        : [[], 200]
    );
    const { onMatched } = renderPanel();
    await userEvent.click(await screen.findByRole("button", OFFER));
    await userEvent.click(screen.getByRole("button", { name: "Crea l'ingrediente" }));
    await waitFor(() => expect(onMatched).toHaveBeenCalledWith(CERA));
    expect(screen.queryByText(/Non sono riuscito a creare/)).toBeNull();
  });

  it("un altro fallimento lo dice, e il nome scritto resta", async () => {
    stubRoutedFetch((_path, init) => (init?.method === "POST" ? [{ detail: "giù" }, 500] : [[], 200]));
    const { onMatched } = renderPanel();
    await userEvent.click(await screen.findByRole("button", OFFER));
    const name = screen.getByLabelText("Come si chiama in generale?");
    await userEvent.clear(name);
    await userEvent.type(name, "cera");
    await userEvent.click(screen.getByRole("button", { name: "Crea l'ingrediente" }));
    expect(await screen.findByText(/Non sono riuscito a creare l'ingrediente/)).toBeDefined();
    expect(name).toHaveValue("cera");
    expect(onMatched).not.toHaveBeenCalled();
  });

  it("«Annulla» nella creazione torna alla ricerca; nella ricerca chiude il pannello", async () => {
    stubRoutedFetch(() => [[], 200]);
    const { onCancel } = renderPanel();
    await userEvent.click(await screen.findByRole("button", OFFER));
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(screen.getByRole("textbox", FIELD)).toBeDefined();
    expect(onCancel).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(onCancel).toHaveBeenCalled();
  });

  it("una ricerca che non risponde lo dice, e lascia crearlo lo stesso (S6)", async () => {
    stubRoutedFetch(() => [{ detail: "giù" }, 500]);
    renderPanel();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "La ricerca degli ingredienti non risponde."
    );
    expect(screen.getByRole("button", OFFER)).toBeDefined();
  });
});
```

Run: `npx vitest run src/features/stocking/MatchPanel.test.tsx`
Expected: FAIL, `Failed to resolve import "./MatchPanel"`.

- [ ] **Step 6: Il pannello «Abbina»**

`frontend/src/features/stocking/MatchPanel.tsx`:

```tsx
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { NewIngredientFields } from "./NewIngredientFields";
import { createIngredient } from "../shopping-list/api";
import { ApiError } from "../../api/client";
import { IngredientPicker } from "../../components/IngredientPicker";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import type { Ingredient, ShoppingItem } from "../../domain/types";

/** L'ingrediente omonimo che il 409 di `POST /ingredients` porta in `existing`, se
 * l'errore è quello. Ogni altro fallimento torna `null` e tiene il suo messaggio. */
function existingIngredient(error: unknown): Ingredient | null {
  if (!(error instanceof ApiError) || error.status !== 409) return null;
  const body = error.body;
  if (body === null || typeof body !== "object" || !("existing" in body)) return null;
  return (body as { existing: Ingredient }).existing ?? null;
}

/**
 * «Abbina», sotto una voce spuntata senza ingrediente (spec T3 §4.3): il testo libero
 * della lista non ha mai trovato un corrispondente, e la voce non può sparire in
 * silenzio dal conto finale. Qui il sistema non inventa niente da solo: si sceglie un
 * ingrediente dal selettore unico (spec §3.5), oppure lo si crea.
 *
 * La creazione è sempre raggiungibile, anche quando la ricerca trova qualcosa
 * (`createWhen="always"`): legarla all'assenza di suggerimenti era il difetto S6,
 * corretto il 2026-09-20 — misurato in produzione, di sette nomi plausibili di prodotti
 * per la casa tutti e sette pescavano almeno un suggerimento. Questo resta l'unico posto
 * dell'app che crea un ingrediente da una voce di lista.
 */
export function MatchPanel({
  item,
  onMatched,
  onCancel,
}: {
  item: ShoppingItem;
  onMatched: (ingredient: Ingredient) => void;
  onCancel: () => void;
}) {
  // `null`: si cerca. Una stringa: si crea, e il campo del nome parte da lì
  const [creating, setCreating] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: async ({ name, category }: { name: string; category: string }) => {
      try {
        // name e display_name sono lo stesso testo: il backend normalizza il primo
        // (strip + lower), e inventare noi una forma canonica sarebbe logica di dominio
        // sul client
        return await createIngredient({ name, display_name: name, category });
      } catch (error) {
        // Il nome c'è già (S19): il 409 porta l'ingrediente che ce l'ha, e quello si
        // aggancia. Chi è «lo stesso nome» lo decide il backend, che lo ha appena
        // rifiutato: niente confronto di nomi qui.
        const existing = existingIngredient(error);
        if (existing) return existing;
        throw error;
      }
    },
    onSuccess: onMatched,
  });

  return (
    <div className="flex flex-col gap-3 rounded-card border border-line p-3">
      <h3 className="font-semibold">Abbina «{item.raw_text}»</h3>
      {creating === null ? (
        <>
          <p className="text-sm text-ink-soft">
            Scegli a quale ingrediente corrisponde: senza, non entra in dispensa.
          </p>
          <IngredientPicker
            label="Abbina un ingrediente"
            accessibleLabel={`Abbina un ingrediente per ${item.raw_text}`}
            failureNote="Puoi comunque aggiungerlo."
            initialTerm={item.raw_text}
            autoFocus
            onPick={onMatched}
            onCreate={(name) => setCreating(name)}
            createWhen="always"
          />
          <Button variant="ghost" onClick={onCancel} className="self-start">
            Annulla
          </Button>
        </>
      ) : (
        <>
          <NewIngredientFields
            initialName={creating}
            busy={create.isPending}
            onSubmit={(fields) => create.mutate(fields)}
            onCancel={() => {
              create.reset();
              setCreating(null);
            }}
          />
          {create.isError && (
            <Alert>
              Non sono riuscito a creare l'ingrediente. Quel che hai scritto è ancora qui:
              riprova, oppure torna indietro e scegline uno.
            </Alert>
          )}
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 7: Farlo passare**

Run: `npx vitest run src/features/stocking src/components/IngredientPicker.test.tsx`
Expected: PASS — 8 test in `MatchPanel.test.tsx`, 7 in `NewIngredientFields.test.tsx`, e tutto il resto della cartella verde (lo schermo non usa ancora il pannello).

Run: `npm run typecheck && npm run lint`
Expected: puliti.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/IngredientPicker.tsx frontend/src/components/IngredientPicker.test.tsx frontend/src/features/stocking/NewIngredientFields.tsx frontend/src/features/stocking/NewIngredientFields.test.tsx frontend/src/features/stocking/MatchPanel.tsx frontend/src/features/stocking/MatchPanel.test.tsx
git commit -m "sistema la spesa: «Abbina» col selettore unico, e l'ingrediente nuovo chiede il nome generico"
```

---

### Task 6: La riga — il nome, a cosa si è risolta, le tre icone, «Abbina», la scadenza

**Files:**
- Create: `frontend/src/features/stocking/StockingRow.tsx`
- Create: `frontend/src/features/stocking/StockingRow.test.tsx`

**Interfaces:**
- Consumes: `Resolution`, `PanelTrigger`, `FocusTarget` (Task 2); `Alert`, `Button`, `IconToolbar`, `buttonClasses`; le icone `IconBarcode`, `IconListSearch`, `IconScale`, `IconReplace`, `IconLink`, `IconCalendarPlus`, `IconX`; `revealAtTop`; `EXPIRY_INPUT_MAX` da `../pantry/expiryLabels`.
- Produces: `StockingRow` con queste prop (il Task 7 le passa tutte):
  - `item: ShoppingItem`
  - `resolution: Resolution | undefined`
  - `ingredientId: string | null` — dalla lista o abbinato qui; `null` finché non c'è
  - `expiry: string | undefined` — `undefined`: campo chiuso; una stringa, anche vuota: campo aperto con quel valore
  - `onExpiry: (value: string | undefined) => void` — `""` apre, una data scrive, `undefined` chiude e svuota
  - `matchNotSaved: boolean`, `retryingMatch: boolean`, `onRetryMatch: () => void` — S19
  - `focused: boolean` — il pannello di questa voce è aperto: la voce va in cima
  - `returnFocusTo: FocusTarget | null`, `onFocusReturned: () => void`
  - `onOpen: (trigger: PanelTrigger) => void`, `onLoose: () => void`, `onChange: () => void`
  - `children?: ReactNode` — il pannello aperto, disegnato dentro la `<li>` sotto la riga

Due cose da sapere prima di scrivere:

1. **Il fuoco.** Aprendo o chiudendo un pannello la vista cambia forma (Task 7: le altre voci spariscono, poi tornano), e la `<li>` rinasce: il pulsante che aveva il fuoco non esiste più. Lo schermo dice alla riga dove rimetterlo (`returnFocusTo`), e la riga lo cerca per il suo `data-trigger`. `Button` non passa `ref` né attributi `data-*`, quindi ogni pulsante che può riprendere il fuoco sta in uno `<span data-trigger="…" className="contents">`: `contents` toglie lo span dal disegno, e il pulsante resta figlio diretto del flex.
2. **I nomi e il testo.** I nomi accessibili delle icone sono `aria-label`, quelli di «Abbina», «+ scadenza» e «Riprova» sono testo con una parte `sr-only`. La parte nascosta non deve mai essere il solo nome della voce: `getByText("cosa strana")` troverebbe anche lei, e i test dello schermo cercano la riga così. Per questo «Abbina» si legge «Abbina: cosa strana», come «Sfuso, senza marca: cosa strana».

- [ ] **Step 1: Scrivere il test che fallisce**

`frontend/src/features/stocking/StockingRow.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState, type ComponentProps } from "react";
import { StockingRow } from "./StockingRow";
import type { Product, ShoppingItem } from "../../domain/types";

const MELE: ShoppingItem = {
  id: "s2", raw_text: "mele", ingredient_id: "i2", ingredient_name: "mela",
  ingredient_category: "frutta", ingredient_kind: "food", status: "checked", reason: "manual",
  created_at: "2026-09-29T10:00:00Z",
};
const STRANA: ShoppingItem = {
  ...MELE, id: "s3", raw_text: "cosa strana", ingredient_id: null, ingredient_name: null,
  ingredient_category: null, ingredient_kind: null,
};
const FAGE: Product = {
  id: "p1", ingredient_id: "i2", ingredient_name: "mela", name: "Total 0%", brand: "Fage",
  barcode: "52010", source: "openfoodfacts", nutrients: null, image_url: null,
};

type Props = ComponentProps<typeof StockingRow>;

function baseProps(): Props {
  return {
    item: MELE, resolution: undefined, ingredientId: "i2", expiry: undefined, onExpiry: vi.fn(),
    matchNotSaved: false, retryingMatch: false, onRetryMatch: vi.fn(), focused: false,
    returnFocusTo: null, onFocusReturned: vi.fn(), onOpen: vi.fn(), onLoose: vi.fn(),
    onChange: vi.fn(),
  };
}

function renderRow(over: Partial<Props> = {}) {
  const props = { ...baseProps(), ...over };
  render(
    <ul>
      <StockingRow {...props} />
    </ul>
  );
  return props;
}

/** La scadenza tenuta da un genitore vero, come la tiene lo schermo. */
function ExpiryHarness() {
  const [expiry, setExpiry] = useState<string | undefined>(undefined);
  return (
    <ul>
      <StockingRow {...baseProps()} expiry={expiry} onExpiry={setExpiry} />
    </ul>
  );
}

describe("StockingRow", () => {
  it("una voce da scegliere ha le tre icone in un gruppo con un nome, e ognuna fa la sua", async () => {
    const { onOpen, onLoose } = renderRow();
    const toolbar = screen.getByRole("toolbar", { name: "Come entra in dispensa: mele" });
    const [codice, catalogo, sfuso] = within(toolbar).getAllByRole("button");
    expect(codice).toHaveAccessibleName("Codice a barre per mele");
    expect(catalogo).toHaveAccessibleName("Cerca a catalogo per mele");
    expect(sfuso).toHaveAccessibleName("Sfuso, senza marca: mele");
    await userEvent.click(codice);
    await userEvent.click(catalogo);
    await userEvent.click(sfuso);
    expect(onOpen.mock.calls).toEqual([["scanner"], ["catalog"]]);
    expect(onLoose).toHaveBeenCalledTimes(1);
  });

  it("risolta sfusa dice «Sfuso» sotto il nome, e «Cambia» è un'icona", async () => {
    const { onChange } = renderRow({ resolution: { kind: "loose" } });
    expect(screen.getByText("Sfuso")).toBeDefined();
    expect(screen.queryByRole("toolbar")).toBeNull();
    const cambia = screen.getByRole("button", { name: "Cambia la scelta per mele" });
    expect(cambia.textContent).toBe("");
    await userEvent.click(cambia);
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it("risolta con un prodotto dice quale, con la marca", () => {
    renderRow({ resolution: { kind: "product", product: FAGE } });
    expect(screen.getByText("Total 0%").parentElement).toHaveTextContent("Total 0% · Fage");
  });

  it("una voce senza ingrediente è chiusa: solo «Abbina»", async () => {
    const { onOpen } = renderRow({ item: STRANA, ingredientId: null });
    expect(screen.queryByRole("toolbar")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Abbina: cosa strana" }));
    expect(onOpen).toHaveBeenCalledWith("match");
  });

  it("«+ scadenza» apre il campo", async () => {
    const { onExpiry } = renderRow();
    expect(screen.queryByLabelText(/Scadenza di mele/)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "+ scadenza per mele" }));
    expect(onExpiry).toHaveBeenCalledWith("");
  });

  it("il campo ha un'etichetta che si vede, e la ✕ lo chiude svuotandolo", async () => {
    const { onExpiry } = renderRow({ expiry: "2026-10-02" });
    const field = screen.getByLabelText(/Scadenza di mele/) as HTMLInputElement;
    expect(field).toHaveValue("2026-10-02");
    expect(field.labels![0]).not.toHaveClass("sr-only");
    await userEvent.click(screen.getByRole("button", { name: "Togli la data di scadenza per mele" }));
    expect(onExpiry).toHaveBeenCalledWith(undefined);
  });

  it("l'Invio nel campo non preme niente; Esc lo chiude svuotandolo", () => {
    const { onExpiry } = renderRow({ expiry: "2026-10-02" });
    const field = screen.getByLabelText(/Scadenza di mele/);
    // senza `preventDefault` l'Invio arrivava al pulsante che riprendeva il fuoco (Consegna 1)
    expect(fireEvent.keyDown(field, { key: "Enter" })).toBe(false);
    expect(onExpiry).not.toHaveBeenCalled();
    fireEvent.keyDown(field, { key: "Escape" });
    expect(onExpiry).toHaveBeenCalledWith(undefined);
  });

  it("chiuso il campo con la ✕, il fuoco torna a «+ scadenza»", async () => {
    render(<ExpiryHarness />);
    await userEvent.click(screen.getByRole("button", { name: "+ scadenza per mele" }));
    const field = screen.getByLabelText(/Scadenza di mele/);
    expect(document.activeElement).toBe(field);
    await userEvent.click(screen.getByRole("button", { name: "Togli la data di scadenza per mele" }));
    expect(screen.queryByLabelText(/Scadenza di mele/)).toBeNull();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "+ scadenza per mele" }));
  });

  it("il fuoco torna al pulsante che aveva aperto il pannello", () => {
    const { onFocusReturned } = renderRow({ returnFocusTo: "catalog" });
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Cerca a catalogo per mele" }));
    expect(onFocusReturned).toHaveBeenCalled();
  });

  it("a voce risolta il fuoco va a «Cambia»", () => {
    renderRow({ resolution: { kind: "loose" }, returnFocusTo: "change" });
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Cambia la scelta per mele" }));
  });

  it("col pannello aperto la voce viene in cima (S10)", () => {
    const targets: Element[] = [];
    const spy = vi
      .spyOn(Element.prototype, "scrollIntoView")
      .mockImplementation(function (this: Element) {
        targets.push(this);
      });
    renderRow({ focused: true });
    expect(targets).toEqual([screen.getByText("mele").closest("li")]);
    spy.mockRestore();
  });

  it("il pannello sta dentro la voce, sotto la sua riga", () => {
    renderRow({ children: <p>il pannello</p> });
    const name = screen.getByText("mele");
    const panel = screen.getByText("il pannello");
    expect(panel.closest("li")).toBe(name.closest("li"));
    expect(name.compareDocumentPosition(panel) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("l'abbinamento non ricordato lo dice accanto, con «Riprova» (S19)", async () => {
    const { onRetryMatch } = renderRow({ item: STRANA, ingredientId: "i9", matchNotSaved: true });
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Non sono riuscito a ricordare l'abbinamento in lista"
    );
    await userEvent.click(screen.getByRole("button", { name: "Riprova ad abbinare cosa strana" }));
    expect(onRetryMatch).toHaveBeenCalledTimes(1);
  });

  it("mentre riprova, «Riprova» si spegne ma tiene il fuoco, e non riparte", async () => {
    const { onRetryMatch } = renderRow({
      item: STRANA, ingredientId: "i9", matchNotSaved: true, retryingMatch: true,
    });
    const retry = screen.getByRole("button", { name: "Riprova ad abbinare cosa strana" });
    expect(retry).toHaveAttribute("aria-disabled", "true");
    expect(retry).not.toBeDisabled();
    await userEvent.click(retry);
    expect(onRetryMatch).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Farlo fallire**

Run: `npx vitest run src/features/stocking/StockingRow.test.tsx`
Expected: FAIL, `Failed to resolve import "./StockingRow"`.

- [ ] **Step 3: Scrivere la riga**

`frontend/src/features/stocking/StockingRow.tsx`:

```tsx
import { useEffect, useId, useRef, type ReactNode } from "react";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { IconToolbar } from "../../components/ui/IconToolbar";
import { buttonClasses } from "../../components/ui/buttonClasses";
import {
  IconBarcode,
  IconCalendarPlus,
  IconLink,
  IconListSearch,
  IconReplace,
  IconScale,
  IconX,
} from "../../components/ui/icons";
import { revealAtTop } from "../../lib/revealAtTop";
import { EXPIRY_INPUT_MAX } from "../pantry/expiryLabels";
import type { FocusTarget, PanelTrigger, Resolution } from "./stockingView";
import type { ShoppingItem } from "../../domain/types";

/** Una voce di «Sistema la spesa» (spec T3 §4.3). Il nome sopra; sotto, in piccolo, a
 * cosa si è risolta — «Sfuso», o il prodotto con la marca — come una riga della
 * dispensa (dal giro: prima si riconosceva solo dal verde). A destra le tre icone
 * codice / catalogo / sfuso, o «Cambia» a voce risolta, o «Abbina» a una voce senza
 * ingrediente. Sotto, il pannello aperto per questa voce, l'avviso di S19 e la
 * scadenza. */
export function StockingRow({
  item,
  resolution,
  ingredientId,
  expiry,
  onExpiry,
  matchNotSaved,
  retryingMatch,
  onRetryMatch,
  focused,
  returnFocusTo,
  onFocusReturned,
  onOpen,
  onLoose,
  onChange,
  children,
}: {
  item: ShoppingItem;
  resolution: Resolution | undefined;
  /** L'ingrediente della voce, dalla lista o abbinato in questo schermo. */
  ingredientId: string | null;
  /** `undefined`: il campo della scadenza è chiuso. Una stringa, anche vuota: è aperto. */
  expiry: string | undefined;
  /** `""` apre il campo, una data la scrive, `undefined` lo chiude svuotandolo. */
  onExpiry: (value: string | undefined) => void;
  matchNotSaved: boolean;
  retryingMatch: boolean;
  onRetryMatch: () => void;
  /** Il pannello di questa voce è aperto: la voce va in cima (S10). */
  focused: boolean;
  returnFocusTo: FocusTarget | null;
  onFocusReturned: () => void;
  onOpen: (trigger: PanelTrigger) => void;
  onLoose: () => void;
  onChange: () => void;
  /** Il pannello aperto, sotto la riga e dentro la voce: prima stavano tutti in fondo
   * alla pagina, fuori vista (S10). */
  children?: ReactNode;
}) {
  const ref = useRef<HTMLLIElement>(null);
  const expiryButton = useRef<HTMLButtonElement>(null);
  // la ✕ ed Esc chiudono il campo: il fuoco torna a «+ scadenza» invece di cadere sul
  // `body` insieme al campo che sparisce
  const refocusExpiry = useRef(false);
  const expiryId = useId();
  const name = item.raw_text;
  const expiryOpen = expiry !== undefined;

  // `scroll-mt-16` sulla `<li>` dice dove fermarsi: l'intestazione fissa (h-12) più un
  // respiro, come in Dispensa
  useEffect(() => {
    if (focused && ref.current) revealAtTop(ref.current);
  }, [focused]);

  // La vista cambia forma aprendo e chiudendo un pannello, e questa riga rinasce: il
  // pulsante che aveva il fuoco non c'è più. Lo schermo dice dove rimetterlo; `Button`
  // non passa `ref`, quindi lo si cerca per il `data-trigger` dello span che lo avvolge
  useEffect(() => {
    if (!returnFocusTo || !ref.current) return;
    ref.current.querySelector<HTMLElement>(`[data-trigger="${returnFocusTo}"] button`)?.focus();
    onFocusReturned();
  }, [returnFocusTo, onFocusReturned]);

  useEffect(() => {
    if (!expiryOpen && refocusExpiry.current) {
      refocusExpiry.current = false;
      expiryButton.current?.focus();
    }
  }, [expiryOpen]);

  function closeExpiry() {
    refocusExpiry.current = true;
    onExpiry(undefined);
  }

  return (
    <li ref={ref} className="scroll-mt-16 py-1">
      <div className="flex items-center gap-2">
        {/* `min-w-0` lascia stringere la colonna sotto la sua parola più lunga, e
            `break-words` spezza un nome che non ci sta: a 375px accanto alle tre icone
            restano circa 170px (S16, in Lista) */}
        <div className="min-w-0 flex-1 break-words">
          <p className="font-medium">{name}</p>
          {resolution && (
            <p className="text-xs text-ink-soft">
              {resolution.kind === "loose" ? (
                "Sfuso"
              ) : (
                <>
                  <span>{resolution.product.name}</span>
                  {resolution.product.brand && <span> · {resolution.product.brand}</span>}
                </>
              )}
            </p>
          )}
        </div>
        {resolution ? (
          // «Cambia» non è più un'azione principale: un'icona, grigia (spec §4.3)
          <span data-trigger="change" className="contents">
            <Button
              variant="ghost"
              icon={IconReplace}
              label={`Cambia la scelta per ${name}`}
              onClick={onChange}
            />
          </span>
        ) : ingredientId ? (
          <IconToolbar label={`Come entra in dispensa: ${name}`}>
            <span data-trigger="scanner" className="contents">
              <Button
                variant="ghost"
                icon={IconBarcode}
                label={`Codice a barre per ${name}`}
                onClick={() => onOpen("scanner")}
              />
            </span>
            <span data-trigger="catalog" className="contents">
              <Button
                variant="ghost"
                icon={IconListSearch}
                label={`Cerca a catalogo per ${name}`}
                onClick={() => onOpen("catalog")}
              />
            </span>
            <Button
              variant="ghost"
              icon={IconScale}
              label={`Sfuso, senza marca: ${name}`}
              onClick={onLoose}
            />
          </IconToolbar>
        ) : (
          // la voce non abbinata è chiusa: una riga con «Abbina» (dal giro: il blocco
          // aperto occupava una schermata e mezza per voce). Un pulsante da solo: icona
          // e testo. Il nome della voce nel nome accessibile, dopo i due punti — da solo,
          // lo `sr-only` sarebbe un secondo testo uguale al nome della riga
          <span data-trigger="match" className="contents">
            <Button icon={IconLink} onClick={() => onOpen("match")} className="shrink-0">
              Abbina<span className="sr-only">: {name}</span>
            </Button>
          </span>
        )}
      </div>

      {children && <div className="pt-2 pb-2">{children}</div>}

      {/* accanto alla voce, e non un muro: la voce resta sistemabile dal match locale,
          e l'abbinamento si può riprovare a scrivere (S19) */}
      {matchNotSaved && (
        <div className="flex flex-col items-start gap-2 pb-2">
          <Alert>
            Non sono riuscito a ricordare l'abbinamento in lista: la voce si sistema lo stesso,
            ma se oggi non la metti in dispensa andrà rifatto.
          </Alert>
          <button
            type="button"
            aria-disabled={retryingMatch || undefined}
            onClick={() => {
              if (!retryingMatch) onRetryMatch();
            }}
            className={`${buttonClasses("secondary")} aria-disabled:opacity-40`}
          >
            Riprova<span className="sr-only"> ad abbinare {name}</span>
          </button>
        </div>
      )}

      {/* Dietro un tocco, sempre: dieci campi vuoti sarebbero rumore permanente sullo
          schermo più denso dell'app, per chi la scadenza non la scrive mai. Resta
          raggiungibile anche a voce risolta: la data riguarda il lotto che entra, non
          come è stato scelto il prodotto */}
      {expiryOpen ? (
        <div className="flex items-end gap-1 pb-1">
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            {/* un'etichetta che si vede (dal giro): prima era solo per lo screen reader */}
            <label htmlFor={expiryId} className="text-xs text-ink-soft">
              Scadenza<span className="sr-only"> di {name}</span>
            </label>
            <input
              id={expiryId}
              type="date"
              max={EXPIRY_INPUT_MAX}
              autoFocus
              value={expiry}
              onChange={(e) => onExpiry(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  // la data si manda con «Metti in dispensa», non c'è niente da
                  // confermare; e senza `preventDefault` l'Invio arrivava al pulsante che
                  // riprendeva il fuoco (la lezione della Consegna 1)
                  e.preventDefault();
                } else if (e.key === "Escape") {
                  e.preventDefault();
                  closeExpiry();
                }
              }}
            />
          </div>
          <Button
            variant="ghost"
            icon={IconX}
            label={`Togli la data di scadenza per ${name}`}
            onClick={closeExpiry}
          />
        </div>
      ) : (
        <button
          ref={expiryButton}
          type="button"
          onClick={() => onExpiry("")}
          className="flex min-h-11 items-center gap-1 text-xs font-medium text-ink-faint"
        >
          <IconCalendarPlus aria-hidden="true" className="size-4" stroke={1.8} />
          + scadenza<span className="sr-only"> per {name}</span>
        </button>
      )}
    </li>
  );
}
```

- [ ] **Step 4: Farlo passare**

Run: `npx vitest run src/features/stocking/StockingRow.test.tsx`
Expected: PASS, 14 test.

Run: `npm run typecheck && npm run lint`
Expected: puliti. Se la regola `react-hooks` segnala l'effetto del fuoco (una prop chiamata dentro un effetto), non spostarlo in un gestore: il pulsante da raggiungere nasce solo al disegno dopo; `PantryRow` fa lo stesso con `onRevealed`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/stocking/StockingRow.tsx frontend/src/features/stocking/StockingRow.test.tsx
git commit -m "sistema la spesa: la riga con le tre icone, «Cambia» come icona, «Abbina» chiuso, e la scadenza con la ✕"
```

---

### Task 7: Lo schermo — sezioni, un pannello alla volta sotto la sua voce, «Metti in dispensa N» e l'avviso

**Files:**
- Create: `frontend/src/features/stocking/OffSuggestionQuestion.tsx` (estratto dallo schermo)
- Modify: `frontend/src/features/stocking/StockingScreen.tsx` (riscritto)
- Modify: `frontend/src/features/stocking/StockingScreen.test.tsx` (migrato e allargato)
- Modify: `frontend/src/features/stocking/wording.ts` (via `OTHER_INGREDIENT`)
- Modify: `frontend/e2e/cooking.spec.ts`, `frontend/e2e/non-alimentari.spec.ts` (il pulsante cambia nome)

**Interfaces:**
- Consumes: tutto quel che producono i Task 2–6; `groupForDisplay` da `../shopping-list/listView`; `fetchShoppingList`, `patchShoppingItem` da `../shopping-list/api`; `stockItems` da `./api`; `CustomProductForm` (prop di oggi); `Screen` (`title`, `back`), `Section` (`category`, `count`), `EmptyState` (`title`, `body`, `action`), `ErrorState` (`message`, `onRetry`, `retrying`), `Button`, `buttonClasses`, `IconPackageImport`, `useNotice`.
- Produces: `StockingScreen()` — la rotta `/sistema` di `App.tsx` non cambia.

Le forme del pannello aperto, una sola alla volta:

| `kind` | Da dove | Cosa porta |
|---|---|---|
| `scanner` | icona del codice | — |
| `catalog` | icona del catalogo | — |
| `match` | «Abbina» | — |
| `off-question` | un codice nuovo che Open Food Facts conosce (S20) | `barcode`, `suggestion` |
| `product-form` | codice ignoto, «Sì» alla domanda, «Crea il prodotto a mano» | `trigger` (chi l'ha aperto, per il fuoco), `barcode`, `suggestion`, `lookedUp` |

- [ ] **Step 1: La domanda di S20 in un file suo**

`frontend/src/features/stocking/OffSuggestionQuestion.tsx`:

```tsx
import { Button } from "../../components/ui/Button";
import type { ProductSuggestion } from "./CustomProductForm";

/** Il nome di Open Food Facts accanto alla domanda, in una frase sola. */
function describeSuggestion(suggestion: ProductSuggestion): string {
  const what = suggestion.name ? `«${suggestion.name}»` : "senza nome";
  const by = suggestion.brand ? `, di ${suggestion.brand}` : "";
  return `Su Open Food Facts è ${what}${by}.`;
}

/**
 * La domanda prima del modulo, quando un codice nuovo al catalogo è noto a Open
 * Food Facts (S20). Il modulo precompilato si apriva direttamente per
 * l'ingrediente della voce, con «Salva» pieno: gli spaghetti letti sulla voce
 * «pomodoro» diventavano per sempre un prodotto di pomodoro, e le ricette al
 * pomodoro cucinabili con la pasta. La domanda si fa sempre, senza confrontare i
 * nomi: «Spaghetti n.5» e «pomodoro» non si somigliano, ma nemmeno «Passata
 * Rustica» e «passata di pomodoro» in modo affidabile, e un confronto che a volte
 * tace è peggio di una domanda che costa un tocco.
 */
export function OffSuggestionQuestion({
  ingredientName,
  suggestion,
  onYes,
  onNo,
}: {
  ingredientName: string;
  suggestion: ProductSuggestion;
  onYes: () => void;
  onNo: () => void;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-card border border-line p-3">
      <h3 className="text-lg font-semibold">È un «{ingredientName}»?</h3>
      <p className="text-ink">{describeSuggestion(suggestion)}</p>
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" onClick={onYes}>
          Sì
        </Button>
        <Button onClick={onNo}>No, è un'altra cosa</Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Migrare il test dello schermo**

Tutte in `frontend/src/features/stocking/StockingScreen.test.tsx`. Sono le sole modifiche ammesse ai test di oggi: ognuna segue un controllo che ha cambiato nome o posto, e nessuna toglie un'asserzione senza metterne al suo posto una che dice la stessa cosa.

**2a. Import, provider, dati.** La riga `import { MemoryRouter } from "react-router-dom";` diventa:

```tsx
import { MemoryRouter, Route, Routes } from "react-router-dom";
```

e sotto `import { UnauthorizedError } from "../../api/client";` aggiungi:

```tsx
import { NoticeProvider } from "../../components/ui/NoticeProvider";
```

Nella costante `FAGE`, dopo `id: "p1", ingredient_id: "i1",` aggiungi `ingredient_name: "yogurt greco",`. Nella costante `OTHER_INGREDIENT_PRODUCT` sostituisci `...FAGE, id: "p2", ingredient_id: "i9", name: "Total 0% magro",` con `...FAGE, id: "p2", ingredient_id: "i9", ingredient_name: "cosa strana", name: "Total 0% magro",`.

Sostituisci tutta la funzione `renderScreen` con:

```tsx
// come in App.tsx: l'avviso unico sta sopra il router, e sopravvive al passaggio in
// Dispensa che segue «Metti in dispensa» (T4)
function renderScreen(client?: QueryClient) {
  const queryClient =
    client ??
    new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
  return render(
    <QueryClientProvider client={queryClient}>
      <NoticeProvider>
        <MemoryRouter initialEntries={["/sistema"]}>
          <Routes>
            <Route path="/sistema" element={<StockingScreen />} />
            <Route path="/dispensa" element={<h1>Dispensa</h1>} />
          </Routes>
        </MemoryRouter>
      </NoticeProvider>
    </QueryClientProvider>
  );
}

/** Apre «Abbina» su una voce senza ingrediente — la riga nasce chiusa (spec T3 §4.3) — e
 * torna il campo del selettore, che parte già dal testo della voce. Per ruolo e non per
 * etichetta: l'elenco dei suggerimenti si chiama «Suggerimenti: Abbina un ingrediente
 * per …», e `getByLabelText(/Abbina un ingrediente/)` troverebbe anche lui. */
async function openMatch(rawText = "cosa strana") {
  await userEvent.click(await screen.findByRole("button", { name: `Abbina: ${rawText}` }));
  return screen.getByRole("textbox", { name: `Abbina un ingrediente per ${rawText}` });
}
```

**2b. «permette di confermare una voce come sfusa, senza prodotto».** Dopo la sistemazione lo schermo rilegge la lista, e lo stub di oggi risponde `{ created: 1 }` a ogni chiamata dopo la prima: sostituisci le righe da `const spy = vi.fn()` fino a `vi.stubGlobal("fetch", spy);` con

```tsx
    const spy = stubRoutedFetch((path) =>
      path.endsWith("/shopping-list/stock") ? [{ created: 1 }, 201] : [CHECKED]
    );
```

e le due righe

```tsx
    const post = spy.mock.calls.find(([url]) => String(url).endsWith("/shopping-list/stock"));
    expect(JSON.parse(post?.[1].body).entries).toEqual([
```

con

```tsx
    expect(postBody(spy, "/shopping-list/stock").entries).toEqual([
```

Le `entries` attese restano identiche.

**2c. Il pulsante dice quante voci entrano.** In questi sei test sostituisci `{ name: "Metti in dispensa" }` con `{ name: "Metti in dispensa 1" }` (una voce scelta in ognuno):
- «un prodotto già in catalogo si aggancia cercandolo per nome»
- «una conferma sbagliata si disfà con «Cambia», senza perdere le altre»
- «una sistemazione fallita dice cosa fare, non «riprova» quando riprovare non può riuscire»
- (S8) «un prodotto scelto a catalogo porta il codice appena letto nella sistemazione»
- (S8) «confermare sfuso dopo un codice ignoto non porta il codice: non c'è un prodotto»
- (S8) «un codice che è di un prodotto di un altro ingrediente non segue la voce»

**2d. «un prodotto di un altro ingrediente non si può agganciare a questa voce».** Sostituisci l'ultima asserzione, `expect(screen.getByText(/di un altro ingrediente/)).toBeDefined();`, con:

```tsx
    const note = screen.getByText(/di un altro ingrediente/);
    // e dice quale (spec T3 §4.3): il nome lo manda il server
    expect(note).toHaveTextContent("è di un altro ingrediente: cosa strana");
```

**2e. «un codice a barre di un altro ingrediente non si aggancia, e non parte nessuna richiesta».** Sostituisci tutto da `expect(await screen.findByText(/di un altro ingrediente/)).toBeDefined();` alla fine del test con:

```tsx
    const note = await screen.findByText(/di un altro ingrediente/);
    // dice quale, e non è un guasto: niente allarme, niente rosso (spec T3 §4.3)
    expect(note).toHaveTextContent("«Total 0% magro» è di un altro ingrediente: cosa strana.");
    expect(note).not.toHaveAttribute("role", "alert");
    expect(note.className).not.toContain("text-danger");
    // la voce non è risolta: le tre strade sono ancora tutte aperte
    expect(screen.getByRole("button", { name: /Sfuso.*yogurt greco/i })).toBeDefined();
    // col pannello aperto «Metti in dispensa» non c'è (decisione 1), e chiuso il
    // pannello è spento: il 409 non è raggiungibile da qui
    expect(screen.queryByRole("button", { name: /Metti in dispensa/ })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    const stock = screen.getByRole("button", { name: "Metti in dispensa" });
    expect(stock).toHaveAttribute("aria-disabled", "true");
    await userEvent.click(stock);
    expect(spy.mock.calls.some(([url]) => String(url).endsWith("/shopping-list/stock"))).toBe(
      false
    );
```

**2f. «non manda in dispensa nulla se non hai confermato niente».** Sostituisci tutto il test con:

```tsx
  it("non manda in dispensa nulla se non hai confermato niente", async () => {
    const spy = vi.fn().mockResolvedValue(respond(CHECKED));
    vi.stubGlobal("fetch", spy);
    renderScreen();
    await screen.findByText("mele");
    // `aria-disabled` e non `disabled`: mentre la sistemazione è in volo il pulsante deve
    // tenere il fuoco. E spento dice perché (dal giro, da non riprogettare via)
    const stock = screen.getByRole("button", { name: "Metti in dispensa" });
    expect(stock).toHaveAttribute("aria-disabled", "true");
    expect(
      screen.getByText("Scegli come entra almeno una voce: codice, catalogo o sfuso.")
    ).toBeDefined();
    await userEvent.click(stock);
    expect(spy.mock.calls.some(([url]) => String(url).endsWith("/shopping-list/stock"))).toBe(
      false
    );
  });
```

**2g. «il campo del codice non conserva il codice della voce precedente».** Il modulo aperto lascia a video solo la sua voce: prima di `await userEvent.click(screen.getByRole("button", { name: /Codice.*mele/i }));` aggiungi

```tsx
    // il modulo aperto lascia a video solo la sua voce (decisione 1): si chiude
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
```

**2h. «il modulo non si ricicla fra due voci, con i dati della prima».** Allo stesso modo, prima di `await userEvent.click(screen.getByRole("button", { name: /Codice.*mele/i }));` aggiungi le stesse due righe.

**2i. «una voce senza ingrediente abbinato si sistema abbinandone uno a mano».** Sostituisci le due righe

```tsx
    const matchField = screen.getByLabelText(/Abbina un ingrediente/i);
    await userEvent.type(matchField, "strana");
```

con

```tsx
    // la voce non abbinata è chiusa: «Abbina» apre il selettore (spec T3 §4.3)
    const matchField = await openMatch();
    await userEvent.clear(matchField);
    await userEvent.type(matchField, "strana");
```

**2j. «se nessun ingrediente corrisponde lo dice, e lascia crearlo».** Sostituisci tutto il test con:

```tsx
  it("se nessun ingrediente corrisponde lo dice, e lascia crearlo col nome da correggere", async () => {
    // è il caso normale per un testo spaiato: cercare lo stesso testo che non ha
    // trovato niente non troverà niente neanche ora
    const spy = stubRoutedFetch((path, init) => {
      if (path.includes("/ingredients/search")) return [[]];
      if (path.endsWith("/ingredients") && init?.method === "POST") return [STRANGE, 201];
      return [UNMATCHED];
    });

    renderScreen();
    await openMatch();
    // «nessun ingrediente corrisponde» lo dice il selettore unico, offrendo di
    // aggiungerlo (spec T3 §3.5)
    await userEvent.click(await screen.findByRole("button", { name: "Aggiungi «cosa strana»" }));
    // il nome parte dal testo della voce, ma è un campo da correggere (dal giro)
    expect(screen.getByLabelText("Come si chiama in generale?")).toHaveValue("cosa strana");
    // non tocca il <select>: è la prova che chi non sceglie niente ottiene
    // esattamente quel che otteneva prima, cioè "altro"
    await userEvent.click(screen.getByRole("button", { name: "Crea l'ingrediente" }));

    expect(await screen.findByRole("button", { name: /Sfuso.*cosa strana/i })).toBeDefined();
    expect(postBody(spy, "/ingredients")).toEqual({
      name: "cosa strana",
      display_name: "cosa strana",
      category: "altro",
    });
  });
```

**2k. «il reparto di una voce nuova si sceglie, e fra i reparti c'è anche il non alimentare».** Sostituisci le righe da `renderScreen();` alla fine del test con:

```tsx
    renderScreen();
    await openMatch();
    await userEvent.click(await screen.findByRole("button", { name: "Aggiungi «cosa strana»" }));

    const reparto = screen.getByLabelText("Reparto");
    // il non alimentare è offerto: è l'unico modo perché un detersivo entri in
    // dispensa senza passare per «altro», che è il reparto delle cose da chiarire
    expect(
      [...(reparto as HTMLSelectElement).options].map((o) => o.value)
    ).toContain("casa");

    await userEvent.selectOptions(reparto, "casa");
    await userEvent.click(screen.getByRole("button", { name: "Crea l'ingrediente" }));

    await vi.waitFor(() =>
      expect(postBody(spy, "/ingredients")).toEqual({
        name: "cosa strana",
        display_name: "cosa strana",
        category: "casa",
      })
    );
```

**2l. «la creazione resta raggiungibile anche quando la ricerca trova qualcosa».** Sostituisci le righe da `renderScreen();` alla fine del test con:

```tsx
    renderScreen();
    await openMatch();

    // il suggerimento c'è e resta: la correzione non sta nella ricerca
    expect(await screen.findByRole("option", { name: /Pera/i })).toBeDefined();
    // ...ma non è più lui a decidere se si può creare: l'offerta sta accanto (S6)
    await userEvent.click(screen.getByRole("button", { name: "Aggiungi «cosa strana»" }));
    await userEvent.selectOptions(screen.getByLabelText("Reparto"), "casa");
    await userEvent.click(screen.getByRole("button", { name: "Crea l'ingrediente" }));

    await vi.waitFor(() =>
      expect(postBody(spy, "/ingredients")).toEqual({
        name: "cosa strana",
        display_name: "cosa strana",
        category: "casa",
      })
    );
    // la frase del caso vuoto resta al caso vuoto: davanti a un suggerimento
    // «nessun ingrediente corrisponde» sarebbe falso
    expect(screen.queryByText(/Nessun ingrediente corrisponde/)).toBeNull();
```

**2m. S19, i primi due test** («l'ingrediente scelto si scrive subito sulla voce…» e «se la voce non si aggiorna lo dice accanto…»). In ciascuno sostituisci

```tsx
      await userEvent.type(await screen.findByLabelText(/Abbina un ingrediente/i), "strana");
```

con

```tsx
      const field = await openMatch();
      await userEvent.clear(field);
      await userEvent.type(field, "strana");
```

**2n. S19, gli altri due** («creare un ingrediente che c'è già aggancia quello…» e «gli altri fallimenti della creazione tengono il loro messaggio»). In ciascuno sostituisci

```tsx
      await userEvent.click(await screen.findByRole("button", { name: /Crea l'ingrediente/i }));
```

con

```tsx
      await openMatch();
      await userEvent.click(await screen.findByRole("button", { name: "Aggiungi «cosa strana»" }));
      await userEvent.click(screen.getByRole("button", { name: "Crea l'ingrediente" }));
```

**2n-bis. «il campo della scadenza non c'è finché non lo si chiede».** Le voci ora sono in ordine di reparto (decisione 3): «mele» (frutta) viene prima di «yogurt greco» (latticini), e il primo «+ scadenza» non è più quello dello yogurt. Sostituisci

```tsx
    await user.click(screen.getAllByRole("button", { name: /scadenza/i })[0]);
```

con

```tsx
    await user.click(screen.getByRole("button", { name: "+ scadenza per yogurt greco" }));
```

**2o. I test nuovi.** In fondo al `describe("StockingScreen", …)` più esterno (prima della sua `});` finale) aggiungi:

```tsx
  describe("la vista (T3 Consegna 3)", () => {
    it("una sezione per reparto, nell'ordine della lista; le voci senza ingrediente in fondo", async () => {
      stubRoutedFetch(() => [[...UNMATCHED, ...CHECKED]]);
      renderScreen();
      await screen.findByText("mele");
      expect(screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)).toEqual([
        "Frutta",
        "Latticini",
        "Senza reparto",
      ]);
    });

    it("un pannello aperto lascia a video solo la sua voce, e chiuderlo rimette tutto com'era", async () => {
      stubRoutedFetch((path) =>
        path.includes("/products/search") ? [[]] : [[...CHECKED, ...UNMATCHED]]
      );
      renderScreen();
      await userEvent.click(await screen.findByRole("button", { name: /Sfuso.*yogurt greco/i }));
      await userEvent.click(screen.getByRole("button", { name: "Cerca a catalogo per mele" }));

      expect(screen.getByRole("heading", { name: "Cerca a catalogo per «mele»" })).toBeDefined();
      // le altre voci, i reparti e «Metti in dispensa» non ci sono (decisione 1, Mattia)
      expect(screen.queryByText("yogurt greco")).toBeNull();
      expect(screen.queryByText("cosa strana")).toBeNull();
      expect(screen.queryAllByRole("heading", { level: 2 })).toEqual([]);
      expect(screen.queryByRole("button", { name: /Metti in dispensa/ })).toBeNull();
      // il fuoco resta sul pulsante che l'ha aperto, non cade sulla pagina
      expect(document.activeElement).toBe(
        screen.getByRole("button", { name: "Cerca a catalogo per mele" })
      );

      await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
      // tutto com'era, e la scelta fatta prima resta
      const yogurt = screen.getByText("yogurt greco").closest("li")!;
      expect(within(yogurt).getByText("Sfuso")).toBeDefined();
      expect(screen.getByText("cosa strana")).toBeDefined();
      expect(screen.getByRole("button", { name: "Metti in dispensa 1" })).toBeDefined();
      expect(document.activeElement).toBe(
        screen.getByRole("button", { name: "Cerca a catalogo per mele" })
      );
    });

    it("un pannello alla volta: aprirne un altro sulla stessa voce chiude il primo", async () => {
      stubRoutedFetch((path) => (path.includes("/products/search") ? [[]] : [CHECKED]));
      renderScreen();
      await userEvent.click(await screen.findByRole("button", { name: "Codice a barre per mele" }));
      expect(screen.getByRole("heading", { name: "Codice a barre per «mele»" })).toBeDefined();
      await userEvent.click(screen.getByRole("button", { name: "Cerca a catalogo per mele" }));
      expect(screen.getByRole("heading", { name: "Cerca a catalogo per «mele»" })).toBeDefined();
      expect(screen.queryByRole("heading", { name: "Codice a barre per «mele»" })).toBeNull();
      expect(screen.queryByLabelText("Codice a barre")).toBeNull();
    });

    it("il pannello porta in cima la sua voce (S10)", async () => {
      const targets: Element[] = [];
      const reveal = vi
        .spyOn(Element.prototype, "scrollIntoView")
        .mockImplementation(function (this: Element) {
          targets.push(this);
        });
      stubRoutedFetch(() => [CHECKED]);
      renderScreen();
      await userEvent.click(await screen.findByRole("button", { name: "Codice a barre per mele" }));
      expect(targets.at(-1)).toBe(screen.getByText("mele").closest("li"));
      reveal.mockRestore();
    });

    it("niente da sistemare: lo dice, e porta alla Lista, senza pulsanti spenti", async () => {
      stubRoutedFetch(() => [[]]);
      renderScreen();
      expect(await screen.findByRole("heading", { name: "Niente da sistemare" })).toBeDefined();
      expect(screen.getByRole("link", { name: "Vai alla Lista" }).getAttribute("href")).toBe("/lista");
      expect(screen.queryByRole("button", { name: /Metti in dispensa/ })).toBeNull();
    });
  });

  describe("«Metti in dispensa» dice quante, e l'avviso arriva in Dispensa (T4)", () => {
    function stubStock() {
      return stubRoutedFetch((path) =>
        path.endsWith("/shopping-list/stock") ? [{ created: 1 }, 201] : [[...CHECKED, ...UNMATCHED]]
      );
    }

    it("il numero sul pulsante è quello delle voci che partono", async () => {
      const spy = stubStock();
      renderScreen();
      await userEvent.click(await screen.findByRole("button", { name: /Sfuso.*mele/i }));
      await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa 1" }));
      await vi.waitFor(() =>
        expect(postBody(spy, "/shopping-list/stock").entries).toHaveLength(1)
      );
    });

    it("in Dispensa, quante sono entrate e quante restano in lista", async () => {
      stubStock();
      renderScreen();
      await userEvent.click(await screen.findByRole("button", { name: /Sfuso.*mele/i }));
      await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa 1" }));
      expect(await screen.findByRole("heading", { name: "Dispensa" })).toBeDefined();
      // le due non mandate — lo yogurt senza scelta, la voce senza ingrediente — restano
      // spuntate in lista; le voci ancora da comprare non contano (decisione 4)
      expect(screen.getByText("1 in dispensa · 2 restano in lista")).toBeDefined();
    });

    it("se sono entrate tutte, l'avviso non parla della lista", async () => {
      stubRoutedFetch((path) =>
        path.endsWith("/shopping-list/stock") ? [{ created: 2 }, 201] : [CHECKED]
      );
      renderScreen();
      await userEvent.click(await screen.findByRole("button", { name: /Sfuso.*yogurt greco/i }));
      await userEvent.click(await screen.findByRole("button", { name: /Sfuso.*mele/i }));
      await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa 2" }));
      expect(await screen.findByText("2 in dispensa")).toBeDefined();
      expect(screen.queryByText(/in lista/)).toBeNull();
    });
  });
```

- [ ] **Step 3: Farlo fallire**

Run: `npx vitest run src/features/stocking/StockingScreen.test.tsx`
Expected: FAIL — fra gli altri «Abbina: cosa strana» che non esiste, «Metti in dispensa 1», le sezioni, l'avviso. Annota quanti falliscono: è la misura di quel che lo schermo nuovo deve fare.

- [ ] **Step 4: Riscrivere lo schermo**

Sostituisci tutto `frontend/src/features/stocking/StockingScreen.tsx` con:

```tsx
import { useCallback, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { fetchShoppingList, patchShoppingItem } from "../shopping-list/api";
import { groupForDisplay } from "../shopping-list/listView";
import { CatalogSearchPanel } from "./CatalogSearchPanel";
import { CustomProductForm } from "./CustomProductForm";
import type { ProductSuggestion } from "./CustomProductForm";
import { MatchPanel } from "./MatchPanel";
import { OffSuggestionQuestion } from "./OffSuggestionQuestion";
import { ScannerPanel } from "./ScannerPanel";
import { StockingRow } from "./StockingRow";
import { stockItems } from "./api";
import {
  stockEntries,
  stockNotice,
  type FocusTarget,
  type PanelTrigger,
  type Resolution,
  type StockEntry,
} from "./stockingView";
import { ApiError } from "../../api/client";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorState } from "../../components/ui/ErrorState";
import { Screen } from "../../components/ui/Screen";
import { Section } from "../../components/ui/Section";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { IconPackageImport } from "../../components/ui/icons";
import { useNotice } from "../../components/ui/noticeContext";
import type { Ingredient, ShoppingItem } from "../../domain/types";

/** Il pannello aperto sotto una voce: uno alla volta, in un solo stato (T3 Consegna 3).
 * Prima erano quattro stati sparsi, e due pannelli potevano stare aperti insieme sulla
 * stessa voce — dicendo due cose diverse su cosa stava per entrare in dispensa. */
type Panel =
  | { itemId: string; kind: "scanner" }
  | { itemId: string; kind: "catalog" }
  | { itemId: string; kind: "match" }
  // il codice nuovo al catalogo che Open Food Facts conosce: prima del modulo, la
  // domanda (S20)
  | { itemId: string; kind: "off-question"; barcode: string; suggestion: ProductSuggestion }
  | {
      itemId: string;
      kind: "product-form";
      /** Chi l'ha aperto: lì torna il fuoco, annullando. */
      trigger: PanelTrigger;
      barcode: string;
      suggestion: ProductSuggestion | null;
      lookedUp?: "not_found" | "failed";
    };

/** Il pulsante della voce che aveva aperto il pannello. */
function triggerOf(panel: Panel): PanelTrigger {
  if (panel.kind === "off-question") return "scanner";
  if (panel.kind === "product-form") return panel.trigger;
  return panel.kind;
}

/** Il registro senza la chiave; lo stesso registro se non c'era. */
function without<T>(record: Record<string, T>, key: string): Record<string, T> {
  if (!(key in record)) return record;
  const next = { ...record };
  delete next[key];
  return next;
}

/** Perché la sistemazione è fallita, in una frase che dice cosa fare.
 *
 * «Riprova» da solo era un vicolo cieco su due delle tre cause: la sistemazione è
 * tutto-o-niente, quindi lo stesso corpo rimandato dà lo stesso errore per sempre.
 * Riprovare è l'azione giusta solo quando la causa è passeggera (rete, backend
 * giù); le altre due si risolvono cambiando una scelta o rileggendo la lista, e
 * vanno nominate. Il 409 non dovrebbe più essere raggiungibile dall'interfaccia
 * (vedi la guardia in ScannerPanel e il filtro di CatalogSearchPanel): se arriva, la
 * via d'uscita è «Cambia» sulla voce sbagliata.
 */
function stockFailureMessage(error: unknown): string {
  const status = error instanceof ApiError ? error.status : null;
  const nothingWritten =
    "Non ho messo in dispensa niente, e quel che hai confermato è ancora qui";
  if (status === 409) {
    return (
      `${nothingWritten}: un prodotto scelto è di un altro ingrediente. ` +
      "Premi «Cambia» su quella voce e scegline un altro, o confermala come sfusa."
    );
  }
  if (status === 404) {
    return (
      `${nothingWritten}: una voce o un prodotto non esiste più. ` +
      "Rileggi la spesa da sistemare qui sotto, poi riprova."
    );
  }
  return (
    `${nothingWritten}: riprova. ` +
    "Se insiste, è il backend che non risponde: le conferme restano su questo schermo."
  );
}

/** «Sistema la spesa» (spec T3 §4.3): le voci nel carrello, per reparto come in Lista,
 * ciascuna da far entrare in dispensa col codice, dal catalogo o sfusa. */
export function StockingScreen() {
  const navigate = useNavigate();
  const notice = useNotice();
  const queryClient = useQueryClient();
  const { data, isLoading, isError, isFetching, refetch } = useQuery({
    queryKey: ["shopping-list", "checked"],
    queryFn: () => fetchShoppingList(["checked"]),
  });
  // un caricamento fallito non è una lista vuota; ma se uno era già riuscito, React
  // Query ne tiene i dati anche quando il successivo fallisce, e quelli restano a video
  // sotto l'errore. `loaded` distingue i due casi, come in Lista e in Dispensa
  const loaded = data !== undefined;
  const items = data ?? [];

  const [resolved, setResolved] = useState<Record<string, Resolution>>({});
  // La scadenza scritta per voce. Una chiave presente è un campo aperto — anche vuoto,
  // appena toccato «+ scadenza» — e la ✕ la toglie. Sta qui e non nella riga: la riga
  // sparisce mentre un'altra voce ha il pannello aperto (decisione 1), e la data scritta
  // non deve sparire con lei.
  const [expiry, setExpiry] = useState<Record<string, string>>({});
  // voci senza ingredient_id, abbinate a mano in questo schermo
  const [matchedIngredient, setMatchedIngredient] = useState<Record<string, Ingredient>>({});
  // S19: l'abbinamento fatto qui e non scritto sulla voce, con l'ingrediente per
  // riprovare. La voce resta sistemabile lo stesso, dal match locale
  const [matchNotSaved, setMatchNotSaved] = useState<Record<string, Ingredient>>({});
  // Il codice letto per una voce e rimasto senza prodotto — ignoto al catalogo, o
  // lookup fallito — indicizzato come `resolved` (S8). Chi poi chiude il modulo e passa
  // dal catalogo, lì crea il prodotto a mano o ne sceglie uno esistente: senza questo il
  // codice si perdeva, e la scansione successiva non trovava niente. Lo sfuso non lo
  // legge: non c'è un prodotto a cui darlo.
  const [unlinkedCode, setUnlinkedCode] = useState<Record<string, string>>({});
  const [panel, setPanel] = useState<Panel | null>(null);
  // dove rimettere il fuoco quando la riga rinasce (vedi StockingRow)
  const [returnFocus, setReturnFocus] = useState<{ itemId: string; target: FocusTarget } | null>(
    null
  );
  const clearReturnFocus = useCallback(() => setReturnFocus(null), []);

  function ingredientOf(item: ShoppingItem): string | null {
    return item.ingredient_id ?? matchedIngredient[item.id]?.id ?? null;
  }

  // Lo stesso ragionamento di `ingredientOf`: la voce può avere il suo ingrediente dalla
  // lista, oppure averlo appena abbinato qui dentro. `null` vuol dire "non lo so" e fa
  // mostrare i campi nutrienti come per un alimentare; non è raggiungibile dove si usa,
  // perché il modulo si apre solo se `ingredientOf(item)` c'è, e reparto e
  // identificativo arrivano sempre insieme dalla stessa fonte.
  function kindOf(item: ShoppingItem): "food" | "non_food" | null {
    return item.ingredient_kind ?? matchedIngredient[item.id]?.kind ?? null;
  }

  // lo stesso nome canonico nei due casi: `ingredient_name` del backend è
  // `ingredient.name`, non `display_name`
  function ingredientNameOf(item: ShoppingItem): string {
    return item.ingredient_name ?? matchedIngredient[item.id]?.name ?? item.raw_text;
  }

  function rememberUnlinkedCode(item: ShoppingItem, code: string | null) {
    setUnlinkedCode((prev) => (code ? { ...prev, [item.id]: code } : without(prev, item.id)));
  }

  // S19: l'abbinamento viveva solo nello stato fino a «Metti in dispensa». Una voce che
  // oggi non entra in dispensa lo perdeva, e in lista restava sotto «Senza reparto».
  // Adesso si scrive subito sulla voce; il match locale resta, così un salvataggio
  // fallito non toglie niente a chi sta sistemando la spesa.
  const persistMatch = useMutation({
    mutationFn: ({ item, ingredient }: { item: ShoppingItem; ingredient: Ingredient }) =>
      patchShoppingItem(item.id, { ingredient_id: ingredient.id }),
    onSuccess: (_saved, { item }) => {
      setMatchNotSaved((prev) => without(prev, item.id));
      // la lista, qui e nella schermata «Lista», deve rimettere la voce nel suo reparto:
      // la cache dice ancora «Senza reparto»
      queryClient.invalidateQueries({ queryKey: ["shopping-list"] });
    },
    onError: (_error, { item, ingredient }) =>
      setMatchNotSaved((prev) => ({ ...prev, [item.id]: ingredient })),
  });

  const stock = useMutation({
    mutationFn: ({ sent }: { sent: StockEntry[]; checked: number }) => stockItems(sent),
    onSuccess: (_created, { sent, checked }) => {
      // la lista della spesa tiene in cache le stesse voci: senza invalidare questo
      // prefisso, tornando a "Lista" le voci appena sistemate restano spuntate
      queryClient.invalidateQueries({ queryKey: ["shopping-list"] });
      // prima di cambiare schermata: l'avviso vive in NoticeProvider, sopra il router
      // (App.tsx), e arriva in Dispensa (T4)
      notice({ text: stockNotice(sent.length, checked) });
      navigate("/dispensa");
    },
  });

  /** Apre un pannello. La vista cambia forma e la riga rinasce: il fuoco torna al
   * pulsante che l'ha aperto, o cadrebbe sul `body`. Il selettore di «Abbina» il fuoco
   * lo prende da sé. */
  function show(next: Panel) {
    setPanel(next);
    if (next.kind !== "match") setReturnFocus({ itemId: next.itemId, target: triggerOf(next) });
  }

  function openPanel(item: ShoppingItem, trigger: PanelTrigger) {
    if (trigger === "scanner") show({ itemId: item.id, kind: "scanner" });
    else if (trigger === "catalog") show({ itemId: item.id, kind: "catalog" });
    else show({ itemId: item.id, kind: "match" });
  }

  /** Chiude il pannello senza scegliere: tutto torna a video, e il fuoco torna al
   * pulsante che l'aveva aperto (decisione 1). */
  function closePanel() {
    if (!panel) return;
    setReturnFocus({ itemId: panel.itemId, target: triggerOf(panel) });
    setPanel(null);
  }

  /** Una scelta fatta: chiude il pannello di questa voce, se c'è. Le tre icone lasciano
   * il posto a «Cambia», e il fuoco va lì. */
  function resolve(item: ShoppingItem, resolution: Resolution) {
    setResolved((prev) => ({ ...prev, [item.id]: resolution }));
    if (panel?.itemId === item.id) setPanel(null);
    setReturnFocus({ itemId: item.id, target: "change" });
  }

  /** Disfa la scelta di una voce, lasciando intatte le altre. Azzera anche l'errore della
   * sistemazione, che parlava di un tentativo fatto su scelte che da adesso non sono più
   * quelle. */
  function changeResolution(item: ShoppingItem) {
    setResolved((prev) => without(prev, item.id));
    stock.reset();
    setReturnFocus({ itemId: item.id, target: "scanner" });
  }

  function matchIngredient(item: ShoppingItem, ingredient: Ingredient) {
    setMatchedIngredient((prev) => ({ ...prev, [item.id]: ingredient }));
    persistMatch.mutate({ item, ingredient });
    setPanel(null);
    // ora la voce ha le tre icone: il fuoco va alla prima
    setReturnFocus({ itemId: item.id, target: "scanner" });
  }

  /** Un codice nuovo al catalogo, che si è deciso di usare: se Open Food Facts lo
   * conosce prima si chiede se è l'ingrediente della voce, se no il modulo. */
  function proceedWithNewCode(item: ShoppingItem, code: string, suggestion: ProductSuggestion | null) {
    rememberUnlinkedCode(item, code);
    show(
      suggestion
        ? { itemId: item.id, kind: "off-question", barcode: code, suggestion }
        : {
            itemId: item.id, kind: "product-form", trigger: "scanner", barcode: code,
            suggestion: null, lookedUp: "not_found",
          }
    );
  }

  /** «Crea il prodotto a mano», dallo scanner o dal catalogo. Il codice letto prima per
   * questa voce segue anche questa uscita (S8), da qualunque pannello si arrivi. */
  function openProductForm(
    item: ShoppingItem,
    trigger: PanelTrigger,
    barcode: string,
    lookedUp?: "failed"
  ) {
    show({
      itemId: item.id,
      kind: "product-form",
      trigger,
      barcode: barcode || unlinkedCode[item.id] || "",
      suggestion: null,
      lookedUp,
    });
  }

  // una fonte per il corpo della richiesta e per il numero sul pulsante (decisione 4)
  const entries = stockEntries(items, resolved, ingredientOf, expiry);

  function submitStock() {
    // la guardia al posto di `disabled`: il pulsante resta dov'è il fuoco
    if (entries.length === 0 || stock.isPending) return;
    stock.mutate({ sent: entries, checked: items.length });
  }

  function renderPanel(item: ShoppingItem, open: Panel): ReactNode {
    if (open.kind === "match") {
      return (
        <MatchPanel
          item={item}
          onMatched={(ingredient) => matchIngredient(item, ingredient)}
          onCancel={closePanel}
        />
      );
    }
    // ogni altro pannello lega un prodotto a un ingrediente: una voce senza non ha le
    // tre icone, e un pannello rimasto aperto su di lei non ha niente da mostrare
    const ingredientId = ingredientOf(item);
    if (!ingredientId) return null;
    if (open.kind === "scanner") {
      return (
        <ScannerPanel
          key={item.id}
          item={item}
          ingredientId={ingredientId}
          onProduct={(product) => resolve(item, { kind: "product", product })}
          onNewCode={(code, suggestion) => proceedWithNewCode(item, code, suggestion)}
          onUnlinkedCode={(code) => rememberUnlinkedCode(item, code)}
          onCreateByHand={(code, lookedUp) => openProductForm(item, "scanner", code, lookedUp)}
          onCancel={closePanel}
        />
      );
    }
    if (open.kind === "catalog") {
      return (
        <CatalogSearchPanel
          key={item.id}
          itemLabel={item.raw_text}
          ingredientId={ingredientId}
          // il codice letto un attimo prima segue entrambe le uscite che danno un
          // prodotto (S8): senza, la prossima scansione dello stesso codice non trovava
          // niente e si ricominciava da capo
          onPicked={(product) =>
            resolve(item, { kind: "product", product, barcode: unlinkedCode[item.id] })
          }
          onCreateByHand={() => openProductForm(item, "catalog", "")}
          onCancel={closePanel}
        />
      );
    }
    if (open.kind === "off-question") {
      return (
        <OffSuggestionQuestion
          ingredientName={ingredientNameOf(item)}
          suggestion={open.suggestion}
          onYes={() =>
            show({
              itemId: item.id, kind: "product-form", trigger: "scanner", barcode: open.barcode,
              suggestion: open.suggestion,
            })
          }
          onNo={() => {
            // indietro a prima del codice: le icone della voce sono ancora là. Il codice
            // non segue la voce — è di un'altra cosa, e dal catalogo finirebbe al
            // prodotto sbagliato
            rememberUnlinkedCode(item, null);
            closePanel();
          }}
        />
      );
    }
    return (
      <div className="rounded-card border border-line">
        <CustomProductForm
          // senza key React riusa l'istanza passando da una voce all'altra: i campi
          // restano quelli di prima mentre ingrediente e codice sono già i nuovi, e si
          // salva il prodotto sbagliato sotto l'ingrediente sbagliato, in silenzio
          key={`${item.id}:${open.barcode}`}
          ingredientId={ingredientId}
          itemLabel={item.raw_text}
          barcode={open.barcode}
          suggestion={open.suggestion}
          lookedUp={open.lookedUp}
          isNonFood={kindOf(item) === "non_food"}
          onCreated={(product) => resolve(item, { kind: "product", product })}
          onCancel={closePanel}
        />
      </div>
    );
  }

  function renderRow(item: ShoppingItem) {
    return (
      <StockingRow
        key={item.id}
        item={item}
        resolution={resolved[item.id]}
        ingredientId={ingredientOf(item)}
        expiry={expiry[item.id]}
        onExpiry={(value) =>
          setExpiry((prev) =>
            value === undefined ? without(prev, item.id) : { ...prev, [item.id]: value }
          )
        }
        matchNotSaved={item.id in matchNotSaved}
        retryingMatch={persistMatch.isPending}
        onRetryMatch={() => persistMatch.mutate({ item, ingredient: matchNotSaved[item.id] })}
        focused={panel?.itemId === item.id}
        returnFocusTo={returnFocus?.itemId === item.id ? returnFocus.target : null}
        onFocusReturned={clearReturnFocus}
        onOpen={(trigger) => openPanel(item, trigger)}
        onLoose={() => resolve(item, { kind: "loose" })}
        onChange={() => changeResolution(item)}
      >
        {panel?.itemId === item.id ? renderPanel(item, panel) : null}
      </StockingRow>
    );
  }

  // la voce del pannello aperto; se è sparita da una rilettura, la vista torna intera
  const focusItem = panel ? items.find((item) => item.id === panel.itemId) : undefined;

  return (
    <Screen title="Sistema la spesa" back={{ to: "/lista", label: "Lista" }}>
      <div className="flex flex-col gap-3">
        {isLoading && <p className="text-ink-soft">Carico…</p>}

        {/* un caricamento fallito non è una lista vuota: dire "non hai spuntato niente"
            a chi è tornato dalla spesa con le borse in mano è una bugia */}
        {isError && (
          <ErrorState
            message={
              loaded
                ? "Non sono riuscito ad aggiornare la spesa da sistemare. Quella qui sotto è dell'ultimo caricamento."
                : "Non sono riuscito a caricare la spesa da sistemare. La lista non è vuota: non l'ho letta."
            }
            onRetry={() => void refetch()}
            retrying={isFetching}
          />
        )}

        {loaded && items.length === 0 && (
          <EmptyState
            title="Niente da sistemare"
            body="Qui arriva quel che spunti in Lista mentre fai la spesa."
            action={
              <Link to="/lista" className={buttonClasses("primary")}>
                Vai alla Lista
              </Link>
            }
          />
        )}

        {focusItem ? (
          // decisione 1 (Mattia): col pannello aperto restano a video solo la sua voce e
          // il pannello. Le scelte fatte sulle altre sono indicizzate per voce, e restano
          <div className="rounded-2xl bg-card px-3 py-2">
            <ul>{renderRow(focusItem)}</ul>
          </div>
        ) : (
          items.length > 0 && (
            <>
              {groupForDisplay(items).map(([category, rows]) => (
                <Section key={category ?? "senza-reparto"} category={category} count={rows.length}>
                  <ul>{rows.map((item) => renderRow(item))}</ul>
                </Section>
              ))}

              <div className="flex flex-col gap-2 pt-1">
                {stock.isError && (
                  <div className="flex flex-col items-start gap-2">
                    <p role="alert" className="text-sm text-danger">
                      {stockFailureMessage(stock.error)}
                    </p>
                    {/* un 404 è l'unico caso in cui riprovare così com'è non può
                        riuscire: la lista va riletta. Le scelte sono indicizzate per id
                        di voce, quindi sopravvivono alla rilettura — e quella della voce
                        sparita resta fuori dal corpo da sé */}
                    {stock.error instanceof ApiError && stock.error.status === 404 && (
                      <Button
                        onClick={() => {
                          // anche l'errore va via: acceso dopo la rilettura direbbe che
                          // c'è ancora un guasto su uno schermo già rimesso in sesto
                          stock.reset();
                          void refetch();
                        }}
                      >
                        Rileggi la spesa da sistemare
                      </Button>
                    )}
                  </div>
                )}
                {/* `aria-disabled` e non `disabled`: mentre la sistemazione è in volo il
                    fuoco resta qui. Il numero è quello delle voci che partono davvero */}
                <button
                  type="button"
                  onClick={submitStock}
                  aria-disabled={entries.length === 0 || stock.isPending || undefined}
                  className={`${buttonClasses("primary", "block")} aria-disabled:opacity-40`}
                >
                  <IconPackageImport aria-hidden="true" className="size-[1.1em]" stroke={1.8} />
                  {entries.length > 0 ? `Metti in dispensa ${entries.length}` : "Metti in dispensa"}
                </button>
                {/* un pulsante spento e muto non si spiega da sé (dal giro) */}
                {entries.length === 0 && (
                  <p className="text-xs text-ink-soft">
                    Scegli come entra almeno una voce: codice, catalogo o sfuso.
                  </p>
                )}
              </div>
            </>
          )
        )}
      </div>
    </Screen>
  );
}
```

- [ ] **Step 5: Via `OTHER_INGREDIENT`**

In `frontend/src/features/stocking/wording.ts` togli il blocco `/** Il prodotto esiste ma appartiene a un altro ingrediente. … */ export const OTHER_INGREDIENT = { … };` per intero: le due frasi ora sono `otherIngredient` ed `elsewhereNote`. Il commento in cima al file resta.

Run (dalla radice del worktree): `grep -rn "OTHER_INGREDIENT\|MatchIngredientField\|scanningFor\|searchingFor\|creatingFor\|confirmingFor" frontend/src`
Expected: niente.

- [ ] **Step 6: Farlo passare, e tutto il resto**

Run (da `frontend/`): `npx vitest run src/features/stocking`
Expected: PASS. `StockingScreen.test.tsx` ha 50 test (i 42 di prima più 8 nuovi).

Se un test migrato fallisce per un motivo che non è nell'elenco del passo 2, **non cambiarlo**: è lo schermo che sbaglia. Correggi lo schermo; se la correzione contraddice una decisione del piano, fermati (Margine di autonomia).

Run: `npx vitest run && npm run typecheck && npm run lint && npm run build`
Expected: tutto verde.

Run (dalla radice del worktree): `grep -rn "emerald\|neutral-" frontend/src`
Expected: niente.

Run: `wc -l frontend/src/features/stocking/StockingScreen.tsx`
Expected: intorno alle 450 righe (erano 916); scrivi il numero nel report.

- [ ] **Step 7: Gli e2e che attraversano «Sistema la spesa»**

Il pulsante ora dice quante voci entrano, e i due percorsi che lo premono ne hanno una sola nel carrello.

In `frontend/e2e/cooking.spec.ts` sostituisci

```ts
  await page.getByRole("button", { name: "Metti in dispensa", exact: true }).click();
```

con

```ts
  await page.getByRole("button", { name: "Metti in dispensa 1", exact: true }).click();
  // l'avviso arriva in Dispensa (T4, spec T3 §4.3): il pomodoro era l'unica voce nel
  // carrello, quindi della lista non si dice niente. La regione `status` si sceglie per
  // il testo: l'avviso unico ne tiene sempre una sua nella pagina
  await expect(page.getByRole("status").filter({ hasText: "in dispensa" })).toHaveText(
    "1 in dispensa"
  );
```

In `frontend/e2e/non-alimentari.spec.ts` sostituisci

```ts
  await page.getByRole("button", { name: "Metti in dispensa", exact: true }).click();
```

con

```ts
  await page.getByRole("button", { name: "Metti in dispensa 1", exact: true }).click();
```

In tutti e due resta com'è la riga prima, `getByRole("button", { name: /Sfuso.*…/i })`: il nome accessibile dell'icona è «Sfuso, senza marca: …», lo stesso di oggi.

Run (dalla radice del worktree): `grep -rn "Metti in dispensa\|sistema" frontend/e2e`
Expected: le due righe appena cambiate, `menu.spec.ts` (che cerca l'intestazione «Sistema la spesa», che c'è ancora: `Screen` la scrive come `h1`), e `style.spec.ts` (`/sistema` fra le schermate misurate, vuota nel seme). Nessun altro cerca un testo cambiato. Gli e2e si eseguono nel Task 8.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/features/stocking frontend/e2e/cooking.spec.ts frontend/e2e/non-alimentari.spec.ts
git commit -m "sistema la spesa: sezioni per reparto, un pannello alla volta sotto la sua voce, e «Metti in dispensa N» con l'avviso in Dispensa"
```

---

### Task 8: L'e2e — «Sistema la spesa» a 375×812 nel browser vero

jsdom non calcola il CSS (quarta lezione di `CLAUDE.md`): che le tre icone siano da 44 px e stiano su una riga con un nome lungo, che la pagina non scorra di lato, che il pannello non finisca sotto l'intestazione fissa, e che ogni testo delle righe vere si legga in scuro, lo dice solo un browser. Il seme non ha voci nel carrello e lo scanner del contrasto di oggi vede `/sistema` solo vuota: la prova crea le sue voci con l'API.

**Files:**
- Modify: `frontend/e2e/style.spec.ts` (un aiuto e un test in fondo)

- [ ] **Step 1: Il test**

In fondo a `frontend/e2e/style.spec.ts` aggiungi (il `beforeEach` del file ha già fatto l'accesso, `page.request` condivide i cookie della pagina, e `testiIlleggibili` e il tipo `Animazione` sono già definiti più sopra nel file):

```ts
/** Aspetta che le transizioni in corso finiscano, come `misuraFermo` in `perOgniLuogo`:
 * cambiando tema `transition-colors` sposta il colore in 150 ms, e misurato a metà il
 * rapporto sarebbe di un colore che nessuno vede fermo. */
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
    await expect(page.getByRole("heading", { level: 2 })).toHaveCount(0);
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
```

Se il passo 6 si ferma perché la fotocamera c'è (un Chromium con un dispositivo finto) e al posto dell'avviso compare il video, non è un difetto: il passo non ne dipende, e le altre asserzioni restano. Se il contrasto del passo 6 segnala «Fotocamera non disponibile…» (`text-low` su `card`), fermati e scrivilo nel report: è il colore di oggi, non di questa consegna, e va deciso di giorno.

- [ ] **Step 2: Il tipo del file**

Run (da `frontend/`): `npm run typecheck && npm run lint`
Expected: puliti. `tsc -b` compila anche gli e2e: `tsconfig.node.json`, fra i riferimenti di `tsconfig.json`, include `e2e/` — senza la libreria DOM, ed è per questo che dentro `evaluate` l'elemento è `any` e si passa da `el.ownerDocument`.

- [ ] **Step 3: Lo stack e2e, e l'e2e intera**

Dalla radice del worktree, con i comandi delle Global Constraints: `cp .env.example .env`, `up -d --build --wait`, il seme `--con-ricette`, poi `cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e; cd ..`.
Expected: tutti verdi, uno in più di prima (erano 31 dopo la Consegna 2). In particolare `cooking.spec.ts` preme «Metti in dispensa 1» e legge «1 in dispensa» in Dispensa, e `non-alimentari.spec.ts` preme «Metti in dispensa 1».

Se una prova fallisce e lascia dati nello stack, prima di rieseguire ricrea lo stack da zero (`down -v`, `up`, seme). Alla fine, sempre:

```bash
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
rm .env
```

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/style.spec.ts
git commit -m "e2e: Sistema la spesa a 375px, un pannello alla volta sotto la sua voce, e il contrasto delle righe vere"
```

---

### Task 9: I documenti

**Files:**
- Modify: `docs/prossimi-passi.md`
- Modify: `next-steps.md`

- [ ] **Step 1: Il paragrafo della consegna**

In `docs/prossimi-passi.md`, nella voce T3, dopo il paragrafo che comincia con «**Restano aperti, da questa consegna:**» (quello della Consegna 2) e prima di quello che comincia con «Dei tre punti di disegno del tema scuro annotati per questa consegna», aggiungi:

```markdown
**Consegna 3 (Sistema la spesa) fatta il <data di oggi>, sul ramo `night/sistema-la-spesa`,
non ancora in produzione.** Cosa è cambiato: una riga per voce, col nome sopra e sotto a
cosa si è risolta («Sfuso», o il prodotto con la marca), le tre icone codice / catalogo /
sfuso a destra e «Cambia» come icona; le voci in sezioni per reparto, nell'ordine della
Lista; un pannello alla volta, sotto la voce che l'ha chiesto, e mentre è aperto restano a
video solo la voce e il pannello (S10, richiesta di Mattia) — chiudendolo torna tutto, con
le scelte fatte e il fuoco sul pulsante che l'aveva aperto; il pannello del codice nomina
la voce, ha «Cerca» e la tastiera dei numeri, e senza fotocamera offre «Crea il prodotto a
mano»; la voce non abbinata è chiusa, con «Abbina», che apre il selettore unico
(`IngredientPicker`, che per questo ha imparato `createWhen="always"`: la creazione resta
raggiungibile anche quando la ricerca trova qualcosa, S6); l'ingrediente nuovo chiede
«Come si chiama in generale?» (`NewIngredientFields`, pronto per R12); «È di un altro
ingrediente» dice quale, in tono neutro, col nome mandato dal server (`ProductOut` porta
`ingredient_name`); il catalogo dà un messaggio per stato, e l'esempio «yogurt greco» solo
a campo vuoto; «+ scadenza» apre un campo con l'etichetta visibile e una ✕; «Metti in
dispensa N» conta le voci che partono, e in Dispensa l'avviso dice «N in dispensa · M
restano in lista» (T4); niente da sistemare è un `EmptyState` con «Vai alla Lista».
`StockingScreen.tsx` è passato da 916 a <righe> righe: la riga (`StockingRow`) e i
pannelli (`ScannerPanel`, `MatchPanel`, `OffSuggestionQuestion`) stanno in file loro, e le
guardie di S8, S19 e S20 in un posto solo ciascuna.

**Le scelte del piano che Mattia può voler rivedere:** «1 resta in lista» al singolare;
«Metti in dispensa» senza numero e spento, con sotto «Scegli come entra almeno una voce»,
quando non c'è niente di scelto; il nome del passo di creazione che parte dal testo
cercato (il testo della voce, finché non si riscrive la ricerca); anche l'elenco del
catalogo diventato un `listbox` valido; «Annulla» dello scanner spostato in fondo al
pannello; aprendo un pannello il fuoco resta sul pulsante che l'ha aperto, e una scelta
fatta lo porta a «Cambia».

**Da provare sul telefono:** un pannello aperto su una voce in fondo alla lista (la voce
deve arrivare in cima, sotto l'intestazione), e la lista che torna chiudendolo; lo scanner
con la fotocamera vera e con la fotocamera negata; il codice scritto a mano con la
tastiera dei numeri e «Cerca»; il campo data nativo del «+ scadenza» e la sua ✕;
l'avviso in Dispensa dopo «Metti in dispensa».
```

Sostituisci `<data di oggi>` con la data vera e `<righe>` col numero misurato nel Task 7.

- [ ] **Step 2: S10 fatto, T4 e le osservazioni del giro**

1. Il titolo `## S10. «Sistema la spesa»: lo scanner e il modulo si aprono in fondo, fuori vista **[D]**` diventa `## S10. «Sistema la spesa»: lo scanner e il modulo si aprono in fondo, fuori vista **[FATTO <data di oggi> — T3 Consegna 3, non ancora in produzione]**`. In fondo alla voce, dopo il terzo dettaglio del giro, aggiungi:
   ```markdown
   **Fatto** con la Consegna 3 di T3: un pannello alla volta, dentro la voce e sotto la sua
   riga; mentre è aperto le altre voci, i reparti e «Metti in dispensa» non si vedono, e la
   voce va in cima con `revealAtTop`. I tre dettagli: il titolo del pannello del codice
   nomina la voce; il campo ha `inputMode="numeric"` e «Cerca»; senza fotocamera c'è «Crea il
   prodotto a mano», che apre il modulo per quella voce. Misurato a 375×812 in
   `e2e/style.spec.ts`; il telefono vero resta da provare.
   ```
2. In T4, sostituisci la frase «**Restano aperti** «Metti in dispensa» (Consegna 3) e «Salva nel ricettario», con lo stesso avviso che li servirebbe.» con:
   ```markdown
   **«Metti in dispensa» è fatto** (T3 Consegna 3, <data di oggi>): il pulsante dice quante
   voci entrano, e in Dispensa l'avviso dice «4 in dispensa · 3 restano in lista» — contando
   solo le voci nel carrello che non sono entrate. **Resta aperto** «Salva nel ricettario»,
   con lo stesso avviso che lo servirebbe.
   ```
3. Nella sezione del giro, sotto «**Sistema la spesa** (oltre a S10, S19 e S20)», segna *(T3 Consegna 3)* in fondo a ognuna delle nove voci, da «**Una voce risolta si riconosce solo dal colore verde.**» a «**Con niente da sistemare**».

- [ ] **Step 3: `next-steps.md`**

1. Aggiorna la riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte)_`.
2. Togli la riga della Consegna 3 da dove si trova («Pronti per la notte», o «Da approfondire» se la fase giorno non l'ha spostata): è quella che comincia con `- [tbd] P1 · Consegna 3, Sistema la spesa` o `- [pronto] P1 · Consegna 3`.
3. In cima a «Fatti (recenti)» aggiungi:
   ```markdown
   - [fatto] <data di oggi> · T3 Consegna 3, Sistema la spesa: una riga per voce, un pannello alla volta sotto la sua voce (S10), «Abbina» col selettore unico, «Metti in dispensa N» con l'avviso in Dispensa (T4) → branch night/sistema-la-spesa (da revisionare)
   ```
4. In cima a «Da fare a mano (solo Mattia)» aggiungi:
   ```markdown
   - [tbd] P1 · Prove sul telefono di Sistema la spesa (Consegna 3): un pannello aperto su una voce in fondo, lo scanner con la fotocamera vera e negata, il codice a mano con «Cerca», il campo data e la sua ✕, l'avviso in Dispensa
   ```
5. Se nella notte sono emerse cose da fare fuori da questo piano, aggiungile come `idea` o `tbd` nella sezione giusta, con la voce di `docs/prossimi-passi.md` fra parentesi quadre.

- [ ] **Step 4: Commit**

```bash
git add docs/prossimi-passi.md next-steps.md
git commit -m "docs: T3 Consegna 3, Sistema la spesa; S10 fatto, e «Metti in dispensa» di T4"
```

---

### Task 10: La verifica finale

Niente di nuovo da scrivere: si prova tutto, dal worktree, com'è sul ramo.

- [ ] **Step 1: Il frontend**

Da `<worktree>/frontend`:

```bash
npx vitest run
npm run typecheck
npx tsc -b --force
npm run lint
npm run build
```

Expected: vitest tutto verde — **663 della linea di partenza più i nuovi**, cioè 663 + 14 (`stockingView`) + 4 (`wording`) + 8 (`CatalogSearchPanel`) + 2 (`BarcodeScanner`) + 12 (`ScannerPanel`) + 3 (`IngredientPicker`) + 7 (`NewIngredientFields`) + 8 (`MatchPanel`) + 14 (`StockingRow`) + 8 (`StockingScreen`) = **743 test in 58 file**; se il numero differisce, scrivi nel report da dove viene la differenza. Typecheck, lint e build puliti. `npx tsc -b --force` perché `node_modules` è condiviso col checkout principale e con lui il `tsbuildinfo`: `--force` compila davvero tutto invece di fidarsi di una build precedente.

- [ ] **Step 2: Il backend**

Da `<worktree>/backend`:

```bash
PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Expected: tutto verde, tre test più della linea di partenza.

- [ ] **Step 3: I grep**

Dalla radice del worktree:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -rn "OTHER_INGREDIENT\|MatchIngredientField\|scanningFor\|searchingFor\|creatingFor\|confirmingFor" frontend/src
grep -rn "ProductOut.model_validate" backend/app
```

Expected: niente, tre volte.

- [ ] **Step 4: L'e2e intera**

Con i comandi delle Global Constraints, su uno stack ricreato da zero (`down -v` prima dell'`up`, se ne era rimasto uno di questo ramo). Expected: tutti verdi. Poi `down -v` e `rm .env`, sempre.

- [ ] **Step 5: Il report**

Nel report della notte, per questo piano: il ramo, i conti veri (vitest, pytest, e2e), le righe di `StockingScreen.tsx`, le migrazioni di test fatte oltre a quelle del Task 7 (dovrebbero essere zero) e le decisioni prese in autonomia. Niente push, niente merge, niente deploy.






