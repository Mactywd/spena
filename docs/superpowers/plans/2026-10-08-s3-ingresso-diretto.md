# S3 — Ingresso diretto in dispensa, veloce: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** dalla Dispensa una confezione entra senza passare dalla lista — «Scansiona» (codice letto → scheda di conferma → «Metti in dispensa», in serie) e il + (ingrediente scelto o creato lì → scheda sfusa, con le strade del codice e del catalogo) — con la scadenza scritta prima di entrare; e in «Sistema la spesa» «Articolo aggiuntivo» (una voce di lista nata spuntata) e «+ un'altra confezione» dello stesso ingrediente.

**Architecture:** nessuna tabella, nessuna migrazione. Nel backend `stock_one` (in `app/repositories/pantry.py`) è la sola copia di «`add_pantry_item`, poi `give_barcode_if_missing`»: la usano `stock_items` (una volta per confezione) e `POST /api/v1/pantry`, che prende `expires_on` e `barcode`; `StockRequest` rifiuta con 422 due confezioni della stessa voce con ingredienti diversi. Nel frontend la regia dei pannelli esce da `StockingScreen` in `ProductResolver` (scanner, catalogo, domanda di Open Food Facts, modulo, codice che segue, esito tardivo), con un modo nuovo senza ingrediente atteso (la scansione dalla Dispensa: prima l'ingrediente, poi il modulo); `MatchPanel` presta la creazione dell'ingrediente a `IngredientChooser`; `ScannerPanel` prende `label` e un ingrediente facoltativo; la riga di «Sistema la spesa» presta `ExpiryField`, `ResolutionNote` e `useReturnFocus`. La Dispensa ha `DirectEntry` (le due porte) e `EntryCard` (la scheda), e «Sistema la spesa» indicizza scelte, scadenze, codici e pannelli **per confezione** (`PackageRow`).

**Tech Stack:** React 19, TypeScript, Tailwind 4 (token in `@theme`), TanStack Query 5, react-router 7, Vitest + Testing Library (jsdom), Playwright; FastAPI, SQLAlchemy async, pytest su Postgres vero.

**Spec:** `docs/superpowers/specs/2026-10-06-ingresso-diretto-bozza.md` (le decisioni sono nel §8, le due richieste nuove nel §10, i criteri nel §6); in `docs/prossimi-passi.md` la voce **S3** (e, per il perché delle guardie, S8, S19, S20). Le decisioni di Mattia del 2026-10-07 sono riportate sotto, in «Decisioni prese».

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/s3-ingresso-diretto` (`.worktrees/` è già in `.gitignore`), ramo `night/s3-ingresso-diretto`, creato da **`master`**. Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì (o dalle sue `backend/` e `frontend/`), mai dalla radice del checkout principale. Il checkout principale non si tocca: se vi trovi modifiche non committate, sono dell'utente. **Nessun push, nessun merge, nessun deploy. Niente letture o scritture sulla produzione. Mai `git stash`.**
- **Questo piano è il primo della catena della notte** (S3 → S12 → tema scuro → S14 → S15; i suggerimenti partono da `master` a parte). I piani dopo questo partono dal suo ramo e leggono i file com'è qui li lascia: **i nomi pubblici fissati sotto («Margine di autonomia») non si cambiano**, perché S14 e S15 agganciano il loro codice a `afterEntry` di `PantryScreen` (la riga nuova da portare in vista).
- **Il piano dà file interi dove il file è nuovo o lo riscrive tutto** (`StockingScreen.tsx`, `StockingRow.tsx`, `ProductResolver.tsx`, `IngredientChooser.tsx`, `MatchPanel.tsx`, i file nuovi), e blocchi «sostituisci questo con questo» altrove. Il codice è scritto contro `master` 27aa06a: la Preparazione verifica che quei file su `master` non siano cambiati da allora; se lo sono, applica le modifiche blocco per blocco sopra la versione di `master` invece di sovrascrivere, e scrivilo nel report.
- **`Button`** (`frontend/src/components/ui/Button.tsx`) ha `variant`, `shape`, `icon`, `label` (sola icona), `busy`, `unavailableReason`, `accessibleName`, `ref`. **La regola (di Mattia):** in volo → `busy`; «non ancora» → `unavailableReason`; `disabled` nativo solo dove nessuno dei due vale. Ogni pulsante nuovo di questo piano passa da `Button`, tranne i due pulsanti di solo testo piccolo («+ scadenza», già così, e «+ un'altra confezione», che lo imita).
- **Un controllo che si spegne mentre ha il fuoco usa `aria-disabled`**, mai `disabled`: è quel che fanno `busy` e `unavailableReason`.
- Tutto il colore passa dai token di `frontend/src/index.css`. Nessuna schermata nomina un colore crudo: `grep -rn "emerald\|neutral-" frontend/src` resta vuoto. Il testo su un fondo pieno usa il suo `on-*`. Ogni testo sta sopra 4,5:1, in chiaro e in scuro, e lo misura `frontend/e2e/style.spec.ts`. **Nessun token nuovo**, nessuna riga nuova in `theme.test.ts`.
- Le icone si importano solo da `frontend/src/components/ui/icons.ts` (quelle che servono ci sono già: `IconBarcode`, `IconListSearch`, `IconScale`, `IconReplace`, `IconPackageImport`, `IconPlus`, `IconX`).
- Ogni bersaglio nuovo è almeno 44×44 px. A 375 px nessuna schermata scorre di lato.
- **Mai un vicolo cieco.** Ogni guasto lascia una strada: il lookup che fallisce → il modulo a mano; la ricerca degli ingredienti che non risponde → «Aggiungi «…»» resta (`createWhen="always"`); la scrittura in dispensa che fallisce → la scheda resta, con la scelta e la data, e «Metti in dispensa» si ritocca; un codice nuovo nella scansione dalla Dispensa → «Sfuso, senza marca» con l'ingrediente scelto.
- **Le guardie stanno in un posto solo** (prima lezione di `CLAUDE.md`). La cifra di controllo e il prodotto di un altro ingrediente solo in `ScannerPanel.tsx`; quando un codice letto segue un prodotto (S8) solo in `ProductResolver.tsx` (gli schermi tengono solo la stringa, col nome `rememberedCode`); il codice dato al prodotto solo in `stock_one`.
- **Il frontend non calcola logica di dominio.** Il `kind` di un ingrediente creato lo deriva il server dal reparto; se un codice si lega a un prodotto lo decide `give_barcode_if_missing`; il client manda e basta.
- Le parole a video sono in italiano e **si copiano esattamente come sono scritte qui**; gli identificatori in inglese; i commenti in italiano come nel resto del codice.
- **Il type check è `npm run typecheck`** (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0 (settima lezione di `CLAUDE.md`).
- Controlli del frontend, da `<worktree>/frontend`: `npx vitest run` (non esiste `npm test`), `npm run typecheck`, `npm run lint`, `npm run build`.
- **Backend su Postgres vero.** Il database dei test è il container `spena-db-1` (porta 5433), da usare solo come database dei test: se `docker ps --format '{{.Names}}'` non lo mostra, `docker start spena-db-1`. **Mai `docker compose up` dal worktree** (il nome del progetto Compose viene dalla cartella: nascerebbe un secondo Postgres che litiga sulla 5433), mai `-f docker-compose.prod.yml`. Nel worktree non c'è un `.venv`: si usa quello del checkout principale; `python -m` mette la cartella corrente in testa a `sys.path`, quindi si prova l'`app` del worktree. Il comando, sempre da `<worktree>/backend`:
  ```bash
  PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
  Se un test sembra ignorare una modifica, `python -c 'import app; print(app.__file__)'` da `<worktree>/backend` (con lo stesso `PATH`) deve stampare un percorso dentro il worktree. Nessuna chiamata di rete nella suite.
- **e2e** sullo stack `spena-e2e`, dalla radice di `<worktree>`. Serve un `.env`: **si copia da `.env.example`, che non ha segreti, solo per la prova, e si cancella alla fine. Mai leggere né copiare il `.env` del checkout principale.** Prima di alzarlo, `docker ps --format '{{.Names}}' | grep spena-e2e`: se c'è e non l'hai alzato tu (un altro piano della notte), non fare `down`, aspetta che sparisca.
  ```bash
  cp .env.example .env
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed --con-ricette
  (cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
  rm .env
  ```
  Il `-p spena-e2e` e il `-f docker-compose.e2e.yml` vanno in ogni comando: un `down -v` sul progetto di default cancellerebbe la dispensa vera. Una prova fallita lascia dati nello stack: prima di rieseguire, `down -v`, poi `up`, seme e prova.
- Nessuna dipendenza nuova, nessuna migrazione, nessun cambio di configurazione globale.

### Preparazione (una volta, prima del Task 1)

- [ ] Il ramo di partenza è `master`, e i file che il piano dà interi non sono cambiati da quando il piano è stato scritto:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify master
  git diff --stat 27aa06a master -- \
    backend/app/repositories/pantry.py backend/app/repositories/shopping.py \
    backend/app/api/pantry.py backend/app/schemas/pantry.py backend/app/schemas/shopping.py \
    frontend/src/features/stocking/ frontend/src/features/pantry/PantryScreen.tsx \
    frontend/src/features/pantry/PantryScreen.test.tsx frontend/src/features/pantry/api.ts \
    frontend/src/components/ui/ActionBar.tsx frontend/src/components/ui/ActionBar.test.tsx \
    frontend/e2e/style.spec.ts
  ```
  Expected: un hash, poi **niente**. Se il `diff` stampa qualcosa, i file elencati sono cambiati su `master` dopo il piano: si va avanti lo stesso, ma ogni file dato intero si applica blocco per blocco sopra la versione di `master` (le ancore sono le funzioni e gli elementi JSX nominati), e lo si scrive nel report.
- [ ] Dal checkout principale, allinea `node_modules` al lockfile (non aggiunge dipendenze, installa quelle di `package-lock.json`):
  ```bash
  cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund
  ```
- [ ] Crea il worktree da `master` e collega `node_modules` (e solo quello: **niente `.env`**):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/s3-ingresso-diretto -b night/s3-ingresso-diretto master
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/s3-ingresso-diretto/frontend/node_modules
  ```
- [ ] La voce passa `in corso`, sul ramo. In `<worktree>/next-steps.md` trova la riga di S3 (`grep -n "S3, ingresso diretto" next-steps.md`), toglila dalla sua sezione e scrivi sotto `## In corso` (al posto di `_(niente)_`, se c'è):
  ```markdown
  - [in corso] P2 · S3, ingresso diretto in dispensa, veloce — piano `docs/superpowers/plans/2026-10-08-s3-ingresso-diretto.md` → branch night/s3-ingresso-diretto
  ```
  La riga in testa diventa `_Ultimo aggiornamento: <data di oggi> (fase notte: S3 in corso)_`. Poi:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/s3-ingresso-diretto
  git add next-steps.md
  git commit -m "docs: S3 in corso, sul ramo night/s3-ingresso-diretto"
  ```
- [ ] La linea di partenza, dal worktree:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/s3-ingresso-diretto/frontend && npx vitest run 2>&1 | grep -E "Test Files|Tests "
  cd ../backend && PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q 2>&1 | tail -n 1
  cd ../frontend && npx playwright test --list 2>/dev/null | tail -n 1
  ```
  Expected: tutto verde. **Annota i numeri** (file e test di vitest, test di pytest, prove e2e elencate): sono `N_file`, `N_vitest`, `N_pytest`, `N_e2e` del Task 13. Se una delle due linee non è verde, fermati: non è un difetto di questo piano, va scritto nel report, e la riga di S3 in `next-steps.md` del ramo diventa `bloccato` con la diagnosi.

---

## Obiettivo e contesto

Mattia l'ha chiesto due volte, la seconda (2026-09-27) con un accento: **veloce**. Oggi per mettere in dispensa una confezione col suo codice bisogna scriverla in lista, spuntarla e passare da «Sistema la spesa»; la Dispensa ha solo un + che sceglie fra gli ingredienti già in anagrafica, entra sfuso e senza scadenza, e per quel che manca rimanda alla lista. I due casi sono la cosa comprata e non scritta, con la confezione in mano, e il censimento della dispensa: tante confezioni di fila.

La bozza ha deciso la parità subito (lo scontrino resta la fase 2) e ha trovato dove sta il lavoro vero: i pannelli sono già componenti, ma la **regia** — quale pannello è aperto, il codice letto che segue il prodotto (S8), la domanda di Open Food Facts (S20), l'esito che arriva a pannello chiuso — vive dentro `StockingScreen`, e una seconda schermata la copierebbe. Questo piano la estrae in `ProductResolver`, la fa usare a tutti e due gli schermi, e lato server fa lo stesso con `stock_one`. Poi costruisce le due porte della Dispensa e le due richieste nuove di «Sistema la spesa».

## Decisioni prese

Da Mattia il 2026-10-07 (bozza §8, tutte le raccomandate):

1. **Strada A: parità subito, senza scontrino.** Lo scontrino resta la fase 2, e si aggancerà ai pezzi estratti qui (bozza §7).
2. **Una scheda di conferma prima di scrivere** (un tocco in più): dice cosa entra, porta «+ scadenza», «Metti in dispensa» è il primario e prende il fuoco; dopo, l'avviso «In dispensa: …» con «Annulla», la riga nuova portata in vista, la barra vuota.
3. **Scansione in serie**: dopo «Metti in dispensa» da una scansione il pannello non si chiude, torna allo scanner (rimontato con una `key` nuova: `BarcodeScanner` non si tocca); si chiude con la ✕. Dal + invece si chiude. Lo stesso prodotto riletto subito dopo: la scheda lo dice invece di scriverlo due volte in silenzio.
4. **Una voce già in lista che entra dall'ingresso diretto: fuori da questa voce** (resta l'idea P3 nel backlog).
5. **Nomi**: «Scansiona» accanto al +, «Metti in dispensa» anche qui.
6. **«Articolo aggiuntivo»** in fondo a «Sistema la spesa», forma a: una voce di lista nata già spuntata, creata con le rotte di oggi, che compare fra le altre con le sue tre strade; la rotta `stock` non cambia.
7. **Più confezioni per una voce**: «+ un'altra confezione» sotto una voce risolta, **tutte dello stesso ingrediente**; «Metti in dispensa N» conta le confezioni.

Dalla bozza, già decise lì e riportate qui perché il piano le costruisce: `ScannerPanel` con `label` e l'ingrediente atteso facoltativo (senza, il prodotto trovato porta il suo ingrediente); dalla scansione della Dispensa un codice nuovo chiede **prima l'ingrediente** (`IngredientChooser`, che può crearlo) e poi va dritto al modulo, senza la domanda «È un …?»; dal + l'ingrediente si crea lì (il rimando alla lista sparisce) e la scheda sfusa offre «Codice» e «Catalogo»; `POST /pantry` prende `expires_on` e `barcode` e passa da `stock_one`.

Scelte di questo piano, dove la bozza non arrivava (**decise da Claude su delega di Mattia**: estetiche o tecniche interne, reversibili):

8. **`stock_one` sta in `app/repositories/pantry.py`**, accanto ad `add_pantry_item`, e importa `give_barcode_if_missing` da `products.py` (che non importa niente di `pantry.py`: nessun ciclo).
9. **Il backend rifiuta con 422** una sistemazione che manda due confezioni della stessa voce con ingredienti diversi (un `model_validator` di `StockRequest`): l'interfaccia non la costruisce mai, ma `stock_items` riscrive l'ingrediente della voce a ogni riga, e l'ultima vincerebbe in silenzio.
10. **Gli schermi tengono il codice letto per chiave** (`rememberedCode`), perché deve sopravvivere al pannello che si chiude (S8: chiuso il modulo, il catalogo lo porta ancora); quando seguirlo lo decide solo `ProductResolver`.
11. **«Scansiona» è un quadrato di sola icona** (`IconBarcode`, variante `secondary`, `shape="square"`), fra il campo e il +, col nome «Scansiona» per chi ascolta: è la forma del + accanto, e a 375 px lascia al campo lo spazio di oggi.
12. **«Cambia» nella scheda torna indietro di un passo**: dalla scansione, a un codice nuovo; dal + con un prodotto, alla stessa voce sfusa; dal + sfuso, alla scelta dell'ingrediente. **«Annulla» nella scheda**: dalla scansione scarta questa e torna allo scanner; dal + chiude. «Annulla» dello scanner nella scansione dalla Dispensa chiude, come la ✕.
13. **Nella scansione dalla Dispensa**, dal passo dell'ingrediente e da ciò che segue, «Annulla» torna allo scanner (non chiude: c'è una confezione in mano); il campo dell'ingrediente parte vuoto, col nome e la marca di Open Food Facts scritti sopra (bozza §4.2: «mostrando nome e marca … perché si sappia di cosa si sta parlando»), perché il nome di un prodotto non diventi il nome di un ingrediente.
14. **La scheda**: in alto il titolo (il nome del prodotto, o l'ingrediente con la maiuscola) e sotto, piccolo, «Marca · ingrediente» o «Sfuso, senza marca · ingrediente», con «Cambia» a destra; dal + a scheda sfusa, una riga «Con la marca:» con le icone del codice e del catalogo; poi la nota della serie, «+ scadenza», l'errore, e «Metti in dispensa» (con `IconPackageImport`, l'icona della sistemazione) accanto ad «Annulla».
15. **L'avviso** dice «In dispensa: Fage Total 0%» (marca davanti al nome, come sulla confezione) o «In dispensa: Mela» per lo sfuso; il suo «Annulla» archivia la voce appena creata, e se fallisce un avviso nuovo offre «Riprova» (come l'annulla della ✕ di una riga).
16. **Una confezione in più** è una riga sotto la voce, rientrata, col titolo «Confezione 2», le stesse tre icone (nomi «Codice a barre per mele, confezione 2» e così via), «Cambia» a scelta fatta, una ✕ «Togli la confezione 2 di mele», la sua «+ scadenza» e il suo pannello sotto di sé. **«+ un'altra confezione»** compare quando tutte le confezioni della voce sono scelte, in piccolo come «+ scadenza»; aggiunta una confezione, il fuoco va alla sua prima icona. La prima confezione è la riga di oggi, con le chiavi di oggi (l'id della voce): niente di ciò che c'è cambia nome.
17. **L'avviso dopo «Metti in dispensa» conta le confezioni entrate e le voci rimaste**: «3 in dispensa · 1 resta in lista». `stockNotice` prende ora `(sent, left)` invece di `(sent, checked)`, perché con più confezioni per voce la differenza non dice più quante voci restano.
18. **«Articolo aggiuntivo»** apre, al suo posto, un riquadro col titolo «Articolo aggiuntivo», la frase «Entra in lista già spuntato, e lo sistemi qui come le altre voci.», il selettore «Cosa hai comprato?» (che crea l'ingrediente, come «Abbina») e «Annulla»; scelta fatta, il riquadro si chiude e il fuoco va alla prima icona della voce nuova quando la lista riletta la porta (lo stesso meccanismo di S19). La voce in lista prende come testo il `display_name` dell'ingrediente.

**Decise da Mattia il 2026-10-09** (scelte di comportamento che la bozza non decideva; tutte e tre come raccomandato, e il piano le costruisce così):

- **A. «Articolo aggiuntivo» per un ingrediente che è già in lista.** Il backend non fa doppioni (S18): `POST /shopping-list` risponde con la voce che c'era. Il piano: se quella voce è **da comprare**, la spunta (è stata comprata: è quel che si sta dicendo); se è **già spuntata**, non fa niente di nuovo e porta il fuoco su di lei. Alternative: rifiutare con «è già in lista: spuntala da lì»; creare un doppione (vorrebbe cambiare S18 nel backend). Raccomandata la prima.
- **B. Nella scansione dalla Dispensa, dopo un codice nuovo e l'ingrediente, oltre a «Sfuso, senza marca» (dalla bozza) anche «Cerca a catalogo»**, col codice letto che segue il prodotto scelto (S8). Senza, un prodotto già a catalogo ma senza codice si duplicherebbe creandolo dal modulo, e la scansione successiva non lo troverebbe. Alternativa: solo il modulo e lo sfuso, come scritto nella bozza. Raccomandata l'aggiunta.
- **C. «Articolo aggiuntivo» compare solo quando c'è qualcosa da sistemare**, non nello schermo vuoto («Niente da sistemare», che porta alla Lista). Chi non ha spuntato niente e torna con una cosa sola ha l'ingresso diretto della Dispensa. Alternativa: offrirlo anche lì, accanto a «Vai alla Lista». Raccomandata la prima.

## Criteri di accettazione

- [ ] Dalla Dispensa, una confezione già a catalogo entra con **due tocchi** dopo aver aperto lo scanner: il codice letto e «Metti in dispensa» (che ha già il fuoco); lo scanner torna pronto per il prossimo codice; lo stesso codice riletto dice «L'hai appena messo in dispensa: se è un'altra confezione, mettila pure.».
- [ ] Una confezione con un codice nuovo entra senza passare dalla lista: «Di che ingrediente è?» (che può crearlo), poi il modulo (precompilato da Open Food Facts senza la domanda), poi la scheda; dal modulo si esce anche sfusi o dal catalogo.
- [ ] Uno sfuso entra dal + con l'ingrediente creato al volo se manca; «scrivilo in lista» non esiste più (`grep -rn "scrivilo in" frontend/src` vuoto).
- [ ] La scadenza si scrive nella scheda, nelle due porte, e parte con la voce; l'avviso «In dispensa: …» offre «Annulla», che archivia la voce.
- [ ] `POST /api/v1/pantry` scrive `expires_on`, dà il `barcode` al prodotto che non ne ha (mai riscrivendo, mai senza prodotto), e resta 409/404 come oggi.
- [ ] In «Sistema la spesa»: «+ un'altra confezione» su una voce risolta; «Metti in dispensa N» conta le confezioni; ogni confezione ha la sua scelta, la sua scadenza, il suo codice e il suo pannello; la ✕ di una confezione la toglie; due confezioni della stessa voce con ingredienti diversi → 422 dal backend.
- [ ] «Articolo aggiuntivo» crea una voce di lista spuntata (o spunta quella da comprare che c'era), che compare fra le altre col fuoco sulla prima icona.
- [ ] `StockingScreen.test.tsx`, `ScannerPanel.test.tsx` e `MatchPanel.test.tsx` passano **senza modifiche alle asserzioni**: in `ScannerPanel.test.tsx` cambia solo come si monta il pannello (Task 4). `StockingRow.test.tsx` passa senza modifiche.
- [ ] Le guardie in un posto solo: `grep -rln "valid_checksum" frontend/src/features/stocking frontend/src/features/pantry | grep -v test` → solo `ScannerPanel.tsx` (l'Anagrafica lo legge per un altro scopo: la scheda del prodotto dice se il suo codice torna); `grep -rli "unlinkedcode" frontend/src | grep -v test` → solo `ProductResolver.tsx` e `ScannerPanel.tsx`; `grep -rn "give_barcode_if_missing(" backend/app` → la definizione in `products.py` e la chiamata in `stock_one`.
- [ ] `e2e/style.spec.ts` misura la Dispensa con lo scanner aperto, con la scheda (sfusa e col prodotto, col campo della data aperto) e «Sistema la spesa» con due confezioni e «Articolo aggiuntivo» aperto, nei due temi, a 375 px; niente scorre di lato.
- [ ] vitest, `npm run typecheck`, lint, build, pytest e l'e2e intera verdi.
- [ ] `docs/prossimi-passi.md` e `next-steps.md` aggiornati sul ramo (Task 12).

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

Dalla radice di `<worktree>`:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -rn "scrivilo in" frontend/src
grep -rln "valid_checksum" frontend/src/features/stocking frontend/src/features/pantry | grep -v test
grep -rli "unlinkedcode" frontend/src | grep -v test | sort
grep -rn "give_barcode_if_missing(" backend/app
```

Expected: vuoto; vuoto; `frontend/src/features/stocking/ScannerPanel.tsx`; `frontend/src/features/stocking/ProductResolver.tsx` e `frontend/src/features/stocking/ScannerPanel.tsx`; due righe, la `async def give_barcode_if_missing(` in `backend/app/repositories/products.py` e la chiamata in `backend/app/repositories/pantry.py`. E l'e2e intera con i comandi delle Global Constraints.

## Fuori scope

- Lo scontrino (fase 2), la foto dell'etichetta, la foto del prodotto nella scheda (idea P3 nel backlog, da S12).
- Una voce già in lista che entra dall'ingresso diretto (decisione 4: resta l'idea P3).
- Uno stato all'ingresso diverso da «disponibile»; distinguere due confezioni dello stesso prodotto; le quantità.
- Tenere accesa la fotocamera fra un codice e l'altro della serie (`BarcodeScanner` non si tocca): da provare sul telefono, e se l'attesa si sente è un'idea nuova (Task 12).
- Qualunque modifica a `BarcodeScanner`, `CatalogSearchPanel`, `CustomProductForm`, `NewIngredientFields`, `IngredientPicker` (quest'ultimo lo tocca il piano dei suggerimenti, che parte da `master` a parte).
- Desktop.

## Margine di autonomia

- **Liberi:** i nomi di variabili locali e di funzioni interne non fissati qui; l'ordine dei test dentro un file; l'ordine delle classi Tailwind; la formulazione dei commenti, purché dicano il perché; le misure e gli spazi della scheda e della riga di una confezione, se a 375 px qualcosa non sta (scelte estetiche delegate: annotale nel report).
- **Fissi:** le parole a video, esattamente come sono scritte nel piano («Scansiona», «Metti in dispensa», «Di che ingrediente è?», «Ingrediente», «Cerca a catalogo», «Sfuso, senza marca», «Con la marca:», «L'hai appena messo in dispensa: se è un'altra confezione, mettila pure.», «Non sono riuscito ad aggiungere la voce in dispensa. Riprova.», «In dispensa: …», «Annulla», «Chiudi l'aggiunta», «Confezione N», «+ un'altra confezione», «Togli la confezione N di …», «Articolo aggiuntivo», «Cosa hai comprato?», «Entra in lista già spuntato, e lo sistemi qui come le altre voci.», «Non sono riuscito ad aggiungerlo alla spesa da sistemare. Riprova.», le frasi di `newCodeNote`); i nomi accessibili di oggi; i nomi pubblici che altri task e altri piani usano: `stock_one`, `ProductResolver` e le sue prop, `ResolverIngredient`, `IngredientChooser` e le sue prop, `ExpiryField`, `ResolutionNote`, `useReturnFocus`, `PackageRow`, `EntryCard`, `DirectEntry`, `EntryDoor`, `EntryChoice`, `entryTitle`, `entryLabel`, `addPantryItem` e la sua forma, `itemsLeft`, `stockNotice(sent, left)`, la prop `secondaryAction` di `ActionBar`, la prop `after` di `StockingRow`, e in `PantryScreen` la funzione `afterEntry(created, label)` (S14 e S15 ci aggiungono la loro riga).
- **Nessuna dipendenza nuova**, nessuna migrazione, nessun token di colore nuovo.
- **Un test di oggi si cambia solo dove il piano lo dice**: `ScannerPanel.test.tsx` (come si monta), `stockingView.test.ts` (`stockNotice` con `(sent, left)`), `PantryScreen.test.tsx` (le quattro prove dell'aggiunta, che ora passano dalla scheda), e in `style.spec.ts` le tre aggiunte che ora toccano «Metti in dispensa». Mai per indebolirli. Se ne serve un'altra, scrivila nel report con il perché.
- **Una decisione di comportamento non coperta e non reversibile** → si ferma quel task, si fa commit del lavoro parziale sul ramo, lo si segna `bloccato` in `next-steps.md` del ramo con la domanda precisa per Mattia, e si passa al task successivo che non ne dipende. Una scelta reversibile e a basso impatto → la più conservativa, annotata nel report.
- Se un test fallisce e non si risolve in modo ragionevole: niente test disattivati, niente asserzioni indebolite; `bloccato` con la diagnosi.

## Dipendenze

Parte da `master`. Non consuma niente da altri piani. **Gli altri piani della catena consumano da lui**: S12 (righe della dispensa) parte da questo ramo e tocca `PantryRow.tsx`, che qui non cambia; S14 (`Tutto / Cibo / Casa`) e S15 (reparti collassabili) cambiano `PantryScreen.tsx` e si agganciano a `afterEntry` (la riga appena entrata deve vedersi: S14 rimette «Tutto», S15 apre il reparto). Per questo `afterEntry` resta una funzione con quel nome, che fa invalidazione, barra vuota, riepilogo spento, `revealId` e avviso, in quest'ordine.

## Dopo il deploy (solo Mattia)

Nessuna azione sui dati: niente migrazioni, niente comandi da lanciare. Restano le prove sul telefono (Task 12 le scrive in `next-steps.md`).

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `backend/app/repositories/pantry.py` | 1 | `stock_one` |
| `backend/app/repositories/shopping.py` | 1 | `stock_items` usa `stock_one` |
| `backend/app/schemas/pantry.py` | 1 | `PantryItemCreate` + `expires_on`, `barcode` |
| `backend/app/schemas/shopping.py` | 1 | `StockRequest`: un ingrediente per voce |
| `backend/app/api/pantry.py` | 1 | `POST /pantry` via `stock_one` |
| `backend/tests/api/test_pantry.py`, `backend/tests/api/test_shopping.py` | 1 | sette prove |
| `frontend/src/features/stocking/ExpiryField.tsx` | 2 | nuovo, estratto da `StockingRow` |
| `frontend/src/features/stocking/ResolutionNote.tsx` | 2 | nuovo, estratto da `StockingRow` |
| `frontend/src/features/stocking/useReturnFocus.ts` | 2 | nuovo, estratto da `StockingRow` |
| `frontend/src/features/stocking/StockingRow.tsx` | 2, 9 | usa i tre pezzi; prop `after` |
| `frontend/src/features/stocking/IngredientChooser.tsx` (+ test) | 3 | nuovo, estratto da `MatchPanel` |
| `frontend/src/features/stocking/MatchPanel.tsx` | 3 | titolo + `IngredientChooser` + «Annulla» |
| `frontend/src/features/stocking/ScannerPanel.tsx` (+ test) | 4 | `label`, `ingredientId` facoltativo |
| `frontend/src/features/stocking/wording.ts` (+ test), `OffSuggestionQuestion.tsx` | 4 | `describeSuggestion` spostata, `newCodeNote` |
| `frontend/src/features/stocking/ProductResolver.tsx` (+ test) | 5 | nuovo: la regia |
| `frontend/src/features/stocking/StockingScreen.tsx` | 6, 9, 10 | usa `ProductResolver`; confezioni; «Articolo aggiuntivo» |
| `frontend/src/components/ui/ActionBar.tsx` (+ test) | 7 | `secondaryAction` |
| `frontend/src/features/pantry/api.ts` | 7 | `addPantryItem` con prodotto, scadenza, codice |
| `frontend/src/features/pantry/entryView.ts` (+ test) | 7 | nuovo: `EntryChoice`, `entryTitle`, `entryLabel` |
| `frontend/src/features/pantry/EntryCard.tsx` (+ test) | 7 | nuovo: la scheda |
| `frontend/src/features/pantry/DirectEntry.tsx` (+ test) | 8 | nuovo: le due porte |
| `frontend/src/features/pantry/PantryScreen.tsx` (+ test) | 8 | «Scansiona», `DirectEntry`, `afterEntry` |
| `frontend/src/features/stocking/stockingView.ts` (+ test) | 9 | confezioni, `itemsLeft`, `stockNotice(sent, left)` |
| `frontend/src/features/stocking/PackageRow.tsx` (+ test) | 9 | nuovo: una confezione in più |
| `frontend/src/features/stocking/StockingScreen.test.tsx`, `StockingRow.test.tsx` | 9, 10 | prove nuove in fondo |
| `frontend/e2e/style.spec.ts` | 11 | tre migrazioni, tre prove |
| `docs/prossimi-passi.md`, `next-steps.md` | 12 | documenti |
| `docs/night-reports/<data>.md` | 13 | report |

---

### Task 1: Il backend — `stock_one`, `POST /pantry` con scadenza e codice, un ingrediente per voce

**Files:**
- Modify: `backend/app/repositories/pantry.py`
- Modify: `backend/app/repositories/shopping.py` (`stock_items` e gli import)
- Modify: `backend/app/schemas/pantry.py` (`PantryItemCreate`)
- Modify: `backend/app/schemas/shopping.py` (`StockRequest`)
- Modify: `backend/app/api/pantry.py` (`create`)
- Test: `backend/tests/api/test_pantry.py`, `backend/tests/api/test_shopping.py`

**Interfaces:**
- Produces: `stock_one(session, *, ingredient_id: uuid.UUID, product_id: uuid.UUID | None, expires_on: date | None, barcode: str | None, status: PantryStatus = PantryStatus.AVAILABLE, note: str | None = None) -> PantryItem`. `POST /api/v1/pantry` accetta `{ingredient_id, product_id?, status?, note?, expires_on?, barcode?}` e risponde `PantryItemOut` (201), 409 per il prodotto di un altro ingrediente, 404 per un riferimento pendente. `POST /api/v1/shopping-list/stock` accetta più righe con lo stesso `shopping_item_id`, purché dello stesso `ingredient_id` (altrimenti 422).

- [ ] **Step 1: I test che falliscono**

In fondo a `backend/tests/api/test_pantry.py`:

```python
# S3: l'ingresso diretto porta la scadenza e il codice letto, come la sistemazione, e
# passa dalla stessa funzione (`stock_one`): l'ordine «voce, poi codice» è la guardia
# di S8, e una seconda copia resterebbe indietro al primo difetto corretto.


async def test_l_ingresso_diretto_porta_la_scadenza(logged_client, dispensa):
    response = await logged_client.post("/api/v1/pantry", json={
        "ingredient_id": str(dispensa["pomodoro"].id), "expires_on": "2026-10-20",
    })
    assert response.status_code == 201
    assert response.json()["expires_on"] == "2026-10-20"


async def test_l_ingresso_diretto_da_il_codice_al_prodotto_che_non_ne_ha(
    logged_client, db_session, dispensa
):
    """Scelto a catalogo dopo un codice ignoto (S8): la prossima scansione lo trova."""
    product = Product(ingredient_id=dispensa["yogurt"].id, name="Total 0%", brand="Fage",
                      source="custom")
    db_session.add(product)
    await db_session.flush()

    response = await logged_client.post("/api/v1/pantry", json={
        "ingredient_id": str(dispensa["yogurt"].id), "product_id": str(product.id),
        "barcode": "8001234567890",
    })
    assert response.status_code == 201
    await db_session.refresh(product)
    assert product.barcode == "8001234567890"


async def test_l_ingresso_diretto_non_riscrive_il_codice_di_un_prodotto(
    logged_client, db_session, dispensa
):
    product = Product(ingredient_id=dispensa["yogurt"].id, name="Total 0%", brand="Fage",
                      barcode="52010", source="custom")
    db_session.add(product)
    await db_session.flush()

    response = await logged_client.post("/api/v1/pantry", json={
        "ingredient_id": str(dispensa["yogurt"].id), "product_id": str(product.id),
        "barcode": "8001234567890",
    })
    assert response.status_code == 201
    await db_session.refresh(product)
    assert product.barcode == "52010"


async def test_un_codice_senza_prodotto_non_si_lega_a_niente(logged_client, db_session, dispensa):
    """Lo sfuso non ha un prodotto a cui darlo: la voce entra, il codice resta di nessuno."""
    from sqlalchemy import select

    response = await logged_client.post("/api/v1/pantry", json={
        "ingredient_id": str(dispensa["pomodoro"].id), "barcode": "8001234567890",
    })
    assert response.status_code == 201
    assert response.json()["product_id"] is None
    legato = await db_session.scalar(select(Product).where(Product.barcode == "8001234567890"))
    assert legato is None


async def test_il_prodotto_di_un_altro_ingrediente_resta_409_e_non_prende_il_codice(
    logged_client, db_session, dispensa
):
    product = Product(ingredient_id=dispensa["pomodoro"].id, name="Pomodori pelati",
                      source="custom")
    db_session.add(product)
    await db_session.flush()

    response = await logged_client.post("/api/v1/pantry", json={
        "ingredient_id": str(dispensa["yogurt"].id), "product_id": str(product.id),
        "barcode": "8001234567890",
    })
    assert response.status_code == 409
    await db_session.refresh(product)
    assert product.barcode is None
```

In fondo a `backend/tests/api/test_shopping.py`:

```python
# S3 §10.2: da una voce di lista possono uscire più confezioni — due vasetti, uno di
# marca e uno sfuso, con due scadenze. Sono righe con lo stesso `shopping_item_id`; la
# voce si chiude una volta sola. E sono dello stesso ingrediente: la voce ne ha uno.


async def test_due_confezioni_della_stessa_voce_entrano_tutte_e_due(
    logged_client, db_session, ingredienti
):
    product = Product(ingredient_id=ingredienti["yogurt"].id, name="Total 0%", brand="Fage",
                      source="custom")
    item = ShoppingListItem(raw_text="yogurt greco", ingredient_id=ingredienti["yogurt"].id,
                            status=ShoppingStatus.CHECKED, reason=ShoppingReason.MANUAL)
    db_session.add_all([product, item])
    await db_session.flush()

    response = await logged_client.post("/api/v1/shopping-list/stock", json={"entries": [
        {"shopping_item_id": str(item.id), "ingredient_id": str(ingredienti["yogurt"].id),
         "product_id": str(product.id), "expires_on": "2026-10-20"},
        {"shopping_item_id": str(item.id), "ingredient_id": str(ingredienti["yogurt"].id),
         "product_id": None, "expires_on": "2026-10-25"},
    ]})
    assert response.status_code == 201
    assert response.json() == {"created": 2}

    voci = list((await db_session.execute(select(PantryItem))).scalars())
    assert {(v.product_id, v.expires_on) for v in voci} == {
        (product.id, date(2026, 10, 20)), (None, date(2026, 10, 25)),
    }
    await db_session.refresh(item)
    assert item.status == "done"


async def test_le_confezioni_di_una_voce_sono_dello_stesso_ingrediente(
    logged_client, db_session, ingredienti
):
    item = ShoppingListItem(raw_text="yogurt greco", ingredient_id=ingredienti["yogurt"].id,
                            status=ShoppingStatus.CHECKED, reason=ShoppingReason.MANUAL)
    db_session.add(item)
    await db_session.flush()

    response = await logged_client.post("/api/v1/shopping-list/stock", json={"entries": [
        {"shopping_item_id": str(item.id), "ingredient_id": str(ingredienti["yogurt"].id)},
        {"shopping_item_id": str(item.id), "ingredient_id": str(ingredienti["mela"].id)},
    ]})
    assert response.status_code == 422
    assert list((await db_session.execute(select(PantryItem))).scalars()) == []
    await db_session.refresh(item)
    assert item.status == "checked"
```

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/backend`): `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/api/test_pantry.py tests/api/test_shopping.py`
Expected: FAIL in tre: `test_l_ingresso_diretto_porta_la_scadenza` (`expires_on` è `None`: il campo oggi si ignora), `test_l_ingresso_diretto_da_il_codice_al_prodotto_che_non_ne_ha` (barcode `None`), `test_le_confezioni_di_una_voce_sono_dello_stesso_ingrediente` (201 invece di 422). Le altre tre passano già (non riscrivere, niente prodotto, 409) e restano a guardia: il codice nuovo non deve romperle. `test_due_confezioni_…` passa già anche lei: lo schema oggi non vieta i doppioni (la bozza chiedeva di verificarlo), e da qui in poi lo fissa.

- [ ] **Step 3: `stock_one`**

In `backend/app/repositories/pantry.py`, fra gli import in testa aggiungi (dopo `from app.domain.rules import …`):

```python
from app.repositories.products import give_barcode_if_missing
```

e subito **dopo** la funzione `add_pantry_item` aggiungi:

```python
async def stock_one(
    session: AsyncSession,
    *,
    ingredient_id: uuid.UUID,
    product_id: uuid.UUID | None,
    expires_on: date | None,
    barcode: str | None,
    status: PantryStatus = PantryStatus.AVAILABLE,
    note: str | None = None,
) -> PantryItem:
    """Una confezione che entra in dispensa: la voce, e poi il codice letto al prodotto.

    L'ordine è la guardia di S8: il codice va solo a un prodotto che `add_pantry_item`
    ha già riconosciuto come dell'ingrediente dichiarato — se la coppia è sbagliata
    solleva prima, e il codice non si lega a niente. La usano la sistemazione (una volta
    per confezione) e l'ingresso diretto (S3): una copia sola di queste righe, perché
    due copie divergono al primo difetto corretto (prima lezione di CLAUDE.md).
    Lo sfuso non ha un prodotto a cui dare il codice: il codice si lascia cadere.
    """
    item = await add_pantry_item(
        session, ingredient_id=ingredient_id, product_id=product_id, status=status,
        note=note, expires_on=expires_on,
    )
    if product_id is not None and barcode:
        await give_barcode_if_missing(session, product_id, barcode)
    return item
```

- [ ] **Step 4: `stock_items` la usa**

In `backend/app/repositories/shopping.py`:

1. Gli import: togli `from app.domain.rules import PantryStatus` e `from app.repositories.products import give_barcode_if_missing`; `from app.repositories.pantry import add_pantry_item` diventa `from app.repositories.pantry import stock_one`. (Verifica con `grep -n "PantryStatus\|add_pantry_item\|give_barcode" app/repositories/shopping.py` che dopo il blocco qui sotto non resti nessun uso, fuori dal commento di `StockEntry`.)
2. Dentro `stock_items`, sostituisci:
   ```python
        item = await add_pantry_item(
            session, ingredient_id=entry.ingredient_id, product_id=entry.product_id,
            status=PantryStatus.AVAILABLE, expires_on=entry.expires_on,
        )
        # dopo add_pantry_item e non prima: il codice va solo a un prodotto che
        # quel controllo ha già riconosciuto come dell'ingrediente della voce
        if entry.product_id is not None and entry.barcode:
            await give_barcode_if_missing(session, entry.product_id, entry.barcode)
   ```
   con:
   ```python
        # una confezione: la voce e poi il codice, nell'ordine che è la guardia di S8
        # (stock_one). Più righe possono avere la stessa voce (S3 §10.2): la voce si
        # chiude alla prima, e alle altre non cambia niente
        item = await stock_one(
            session, ingredient_id=entry.ingredient_id, product_id=entry.product_id,
            expires_on=entry.expires_on, barcode=entry.barcode,
        )
   ```
3. Il commento di `StockEntry.barcode` (`# uno (S8): vedi give_barcode_if_missing`) resta com'è.

- [ ] **Step 5: lo schema e la rotta della dispensa**

In `backend/app/schemas/pantry.py`, `PantryItemCreate` diventa:

```python
class PantryItemCreate(BaseModel):
    ingredient_id: uuid.UUID
    product_id: uuid.UUID | None = None
    status: PantryStatus = PantryStatus.AVAILABLE
    note: str | None = Field(default=None, max_length=300)
    # S3: l'ingresso diretto scrive la scadenza con la confezione in mano (D5), come la
    # sistemazione
    expires_on: date | None = None
    # il codice letto prima di scegliere il prodotto a catalogo (S8). Senza max_length
    # per la stessa ragione di StockEntryIn: un codice che non entra in colonna non si
    # lega e basta (give_barcode_if_missing), mentre un 422 qui respingerebbe la voce
    # per un di più
    barcode: str | None = None
```

In `backend/app/api/pantry.py`:
1. Nell'import da `app.repositories.pantry`, `add_pantry_item,` diventa `stock_one,` (la lista resta in ordine alfabetico: `ProductIngredientMismatch, archive_item, availability_map, list_pantry, set_expiry, set_status, stock_one, unarchive_item`).
2. Dentro `create`, sostituisci:
   ```python
        item = await add_pantry_item(
            session, ingredient_id=payload.ingredient_id, product_id=payload.product_id,
            status=payload.status, note=payload.note,
        )
   ```
   con:
   ```python
        item = await stock_one(
            session, ingredient_id=payload.ingredient_id, product_id=payload.product_id,
            status=payload.status, note=payload.note, expires_on=payload.expires_on,
            barcode=payload.barcode,
        )
   ```

- [ ] **Step 6: un ingrediente per voce, nella sistemazione**

In `backend/app/schemas/shopping.py`:
1. `from pydantic import BaseModel, Field` diventa `from pydantic import BaseModel, Field, model_validator`.
2. `StockRequest` diventa:
   ```python
   class StockRequest(BaseModel):
       entries: list[StockEntryIn] = Field(min_length=1)

       @model_validator(mode="after")
       def _one_ingredient_per_item(self) -> "StockRequest":
           # Più confezioni per voce sì (S3 §10.2), ma dello stesso ingrediente: la voce
           # ne ha uno, e `stock_items` lo riscrive a ogni riga — con due diversi
           # vincerebbe l'ultimo, in silenzio. L'interfaccia non manda mai questa
           # coppia; se arriva, è un client sbagliato, e si rifiuta prima di scrivere.
           seen: dict[uuid.UUID, uuid.UUID] = {}
           for entry in self.entries:
               if seen.setdefault(entry.shopping_item_id, entry.ingredient_id) != entry.ingredient_id:
                   raise ValueError("le confezioni di una voce sono dello stesso ingrediente")
           return self
   ```

- [ ] **Step 7: Passano, e niente si è rotto**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q`
Expected: tutto verde, **`N_pytest` + 7**. Poi, dalla radice del worktree, `grep -rn "give_barcode_if_missing(" backend/app` → due righe: la definizione in `products.py` e la chiamata in `pantry.py`.

- [ ] **Step 8: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat(backend): stock_one, la confezione e il suo codice in un posto solo; POST /pantry con scadenza e codice; più confezioni per voce, dello stesso ingrediente (S3)"
```

---

### Task 2: La riga di «Sistema la spesa» presta tre pezzi — `ExpiryField`, `ResolutionNote`, `useReturnFocus`

Un rifacimento senza comportamento nuovo: la scheda della Dispensa e le confezioni in più vogliono la stessa «+ scadenza» con le sue guardie del fuoco, la stessa riga «Sfuso» / «prodotto · marca», e lo stesso ritorno del fuoco al pulsante che aveva aperto un pannello. Copiati, divergerebbero. La prova è che `StockingRow.test.tsx` e `StockingScreen.test.tsx` passano senza essere toccati.

**Files:**
- Create: `frontend/src/features/stocking/ExpiryField.tsx`
- Create: `frontend/src/features/stocking/ResolutionNote.tsx`
- Create: `frontend/src/features/stocking/useReturnFocus.ts`
- Modify: `frontend/src/features/stocking/StockingRow.tsx` (intero)

**Interfaces:**
- Produces: `ExpiryField({ name: string; value: string | undefined; onChange: (value: string | undefined) => void })` — `undefined` chiuso, stringa (anche vuota) aperto; nomi «+ scadenza per {name}», «Scadenza di {name}», «Togli la data di scadenza per {name}». `ResolutionNote({ resolution: Resolution })`. `useReturnFocus(container: RefObject<HTMLElement | null>, target: FocusTarget | null, onDone: () => void, attribute = "data-trigger")`.

- [ ] **Step 1: La rete**

Run (da `<worktree>/frontend`): `npx vitest run src/features/stocking`
Expected: verde. È la rete di questo task: alla fine deve esserlo uguale, con gli stessi numeri.

- [ ] **Step 2: `ExpiryField.tsx`**

```tsx
import { useEffect, useId, useRef } from "react";
import { Button } from "../../components/ui/Button";
import { IconCalendarPlus, IconX } from "../../components/ui/icons";
import { EXPIRY_INPUT_MAX } from "../pantry/expiryLabels";

/** La scadenza di una confezione che sta per entrare in dispensa (S7, D5): dietro
 * «+ scadenza», un campo data nativo con la sua ✕. Dietro un tocco, sempre: dieci campi
 * vuoti sarebbero rumore permanente sullo schermo più denso dell'app, per chi la
 * scadenza non la scrive mai.
 *
 * Estratta da StockingRow (S3): la usano la riga di «Sistema la spesa», le confezioni in
 * più di una voce e la scheda di conferma della Dispensa, e le sue guardie del fuoco
 * devono restare una. Il valore lo tiene chi la usa: la riga può rinascere mentre il
 * campo è aperto, e la data scritta non deve sparire con lei. */
export function ExpiryField({
  name,
  value,
  onChange,
}: {
  /** Di che cosa: entra nei nomi per chi ascolta («Scadenza di mele»). */
  name: string;
  /** `undefined`: il campo è chiuso. Una stringa, anche vuota: è aperto. */
  value: string | undefined;
  /** `""` apre il campo, una data la scrive, `undefined` lo chiude svuotandolo. */
  onChange: (value: string | undefined) => void;
}) {
  const expiryButton = useRef<HTMLButtonElement>(null);
  // la ✕ ed Esc chiudono il campo: il fuoco torna a «+ scadenza» invece di cadere sul
  // `body` insieme al campo che sparisce
  const refocusExpiry = useRef(false);
  // «+ scadenza» porta il fuoco nel campo. Non `autoFocus`: la riga rinasce a ogni
  // pannello aperto o chiuso (decisione 21, il campo resta aperto), e a ogni rinascita il
  // campo si riprendeva il fuoco — quello di «Annulla» finiva nella data di un'altra voce
  // invece che sul pulsante che aveva aperto il pannello (misurato nell'e2e). Solo il
  // tocco lo chiede, e un campo appena nato non l'ha avuto
  const expiryInput = useRef<HTMLInputElement>(null);
  const focusExpiryInput = useRef(false);
  const expiryId = useId();
  const open = value !== undefined;

  useEffect(() => {
    if (!open && refocusExpiry.current) {
      refocusExpiry.current = false;
      expiryButton.current?.focus();
    }
    if (open && focusExpiryInput.current) {
      focusExpiryInput.current = false;
      expiryInput.current?.focus();
    }
  }, [open]);

  function close() {
    refocusExpiry.current = true;
    onChange(undefined);
  }

  return open ? (
    <div className="flex items-end gap-1 pb-1">
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        {/* un'etichetta che si vede (dal giro): prima era solo per lo screen reader */}
        <label htmlFor={expiryId} className="text-xs text-ink-soft">
          Scadenza <span className="sr-only">di {name}</span>
        </label>
        <input
          ref={expiryInput}
          id={expiryId}
          type="date"
          max={EXPIRY_INPUT_MAX}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              // la data si manda con «Metti in dispensa», non c'è niente da
              // confermare; e senza `preventDefault` l'Invio arrivava al pulsante che
              // riprendeva il fuoco (la lezione della Consegna 1)
              e.preventDefault();
            } else if (e.key === "Escape") {
              e.preventDefault();
              close();
            }
          }}
        />
      </div>
      <Button
        variant="ghost"
        icon={IconX}
        label={`Togli la data di scadenza per ${name}`}
        onClick={close}
      />
    </div>
  ) : (
    <button
      ref={expiryButton}
      type="button"
      onClick={() => {
        focusExpiryInput.current = true;
        onChange("");
      }}
      className="flex min-h-11 items-center gap-1 text-xs font-medium text-ink-faint"
    >
      <IconCalendarPlus aria-hidden="true" className="size-4" stroke={1.8} />
      {/* qui lo `sr-only` resta: «+ scadenza» da solo non dice di quale voce, e il
          nome per {name} serve solo a chi ascolta. Lo spazio prima sta fuori dallo
          `sr-only`, non dentro: dentro, Chromium lo mangia insieme al resto del testo
          nascosto e «+ scadenza per X» arriva allo screen reader come «+ scadenzaper
          X», appiccicati */}
      + scadenza <span className="sr-only">per {name}</span>
    </button>
  );
}
```

- [ ] **Step 3: `ResolutionNote.tsx`**

```tsx
import type { Resolution } from "./stockingView";

/** A cosa si è risolta una confezione, sotto il suo nome, in piccolo: «Sfuso», o il
 * prodotto con la marca — come una riga della dispensa (dal giro: prima si riconosceva
 * solo dal verde). La usano la riga di una voce e quella di una confezione in più. */
export function ResolutionNote({ resolution }: { resolution: Resolution }) {
  return (
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
  );
}
```

- [ ] **Step 4: `useReturnFocus.ts`**

```ts
import { useEffect, type RefObject } from "react";
import type { FocusTarget } from "./stockingView";

/** Rimette il fuoco al pulsante giusto di una riga che rinasce.
 *
 * La vista cambia forma aprendo e chiudendo un pannello, e la riga rinasce: il pulsante
 * che aveva il fuoco non c'è più. Lo schermo dice dove rimetterlo; `Button` non passa
 * `ref` a chi lo avvolge, quindi lo si cerca per l'attributo dello span che lo avvolge
 * (`data-trigger` nella riga di una voce, `data-package-trigger` in quella di una
 * confezione: la seconda sta dentro la prima, e i due non devono trovarsi a vicenda).
 * Solo se il fuoco è caduto sulla pagina: è sempre così quando il pulsante che lo aveva
 * è sparito, e una richiesta arrivata in ritardo (la rilettura dopo un abbinamento) non
 * lo toglie a chi è già andato altrove. */
export function useReturnFocus(
  container: RefObject<HTMLElement | null>,
  target: FocusTarget | null,
  onDone: () => void,
  attribute = "data-trigger"
) {
  useEffect(() => {
    if (!target || !container.current) return;
    const lost = document.activeElement === null || document.activeElement === document.body;
    if (lost) {
      container.current.querySelector<HTMLElement>(`[${attribute}="${target}"] button`)?.focus();
    }
    onDone();
  }, [container, target, onDone, attribute]);
}
```

- [ ] **Step 5: `StockingRow.tsx` li usa**

Sostituisci il file intero con:

```tsx
import { useEffect, useRef, type ReactNode } from "react";
import { ExpiryField } from "./ExpiryField";
import { ResolutionNote } from "./ResolutionNote";
import { useReturnFocus } from "./useReturnFocus";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { IconToolbar } from "../../components/ui/IconToolbar";
import {
  IconBarcode,
  IconLink,
  IconListSearch,
  IconRefresh,
  IconReplace,
  IconScale,
} from "../../components/ui/icons";
import { revealAtTop } from "../../lib/revealAtTop";
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
  const name = item.raw_text;

  // `scroll-mt-16` sulla `<li>` dice dove fermarsi: l'intestazione fissa (h-12) più un
  // respiro, come in Dispensa
  useEffect(() => {
    if (focused && ref.current) revealAtTop(ref.current);
  }, [focused]);

  useReturnFocus(ref, returnFocusTo, onFocusReturned);

  return (
    <li ref={ref} className="scroll-mt-16 py-1">
      <div className="flex items-center gap-2">
        {/* `min-w-0` lascia stringere la colonna sotto la sua parola più lunga, e
            `break-words` spezza un nome che non ci sta: a 375px accanto alle tre icone
            restano circa 170px (S16, in Lista) */}
        <div className="min-w-0 flex-1 break-words">
          <p className="font-medium">{name}</p>
          {resolution && <ResolutionNote resolution={resolution} />}
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
          // e testo. Il nome della voce nel nome accessibile, dopo i due punti, con
          // `accessibleName` (Consegna 6a). Non uno `sr-only`: è posizionato, quindi a
          // blocco, e Chromium ci metteva uno spazio davanti — il nome diventava «Abbina :
          // X» (misurato nell'e2e; jsdom non lo vede)
          <span data-trigger="match" className="contents">
            <Button
              icon={IconLink}
              accessibleName={`Abbina: ${name}`}
              onClick={() => onOpen("match")}
              className="shrink-0"
            >
              Abbina
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
          {/* un pulsante da solo: icona e testo (regola delle icone, spec §2). Il nome
              dice cosa riprova, con `accessibleName` (Consegna 6a); `busy` mentre la
              scrittura è in volo, e il fuoco resta */}
          <Button
            icon={IconRefresh}
            accessibleName={`Riprova ad abbinare ${name}`}
            busy={retryingMatch}
            onClick={onRetryMatch}
          >
            Riprova
          </Button>
        </div>
      )}

      {/* resta raggiungibile anche a voce risolta: la data riguarda il lotto che entra,
          non come è stato scelto il prodotto */}
      <ExpiryField name={name} value={expiry} onChange={onExpiry} />
    </li>
  );
}
```

- [ ] **Step 6: La rete tiene**

Run: `npx vitest run src/features/stocking && npm run typecheck && npm run lint`
Expected: verde, con gli stessi numeri dello Step 1 (nessun test nuovo, nessun test toccato); typecheck e lint puliti.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/stocking
git commit -m "refactor(stocking): ExpiryField, ResolutionNote e useReturnFocus escono da StockingRow, per la scheda della Dispensa e le confezioni in più (S3)"
```

---

### Task 3: `IngredientChooser` — la scelta o la creazione dell'ingrediente, fuori da `MatchPanel`

`MatchPanel` sa scegliere un ingrediente dal selettore unico **o crearlo** (S6, col 409 che porta l'ingrediente omonimo, S19). La Dispensa (il +, e il passo «Di che ingrediente è?») e «Articolo aggiuntivo» vogliono la stessa cosa. `MatchPanel.test.tsx` deve passare senza essere toccato.

**Files:**
- Create: `frontend/src/features/stocking/IngredientChooser.tsx`
- Create: `frontend/src/features/stocking/IngredientChooser.test.tsx`
- Modify: `frontend/src/features/stocking/MatchPanel.tsx` (intero)

**Interfaces:**
- Produces: `IngredientChooser({ label: string; accessibleLabel?: string; failureNote: string; initialTerm: string; onChosen: (ingredient: Ingredient) => void; busy?: boolean; before?: ReactNode; after?: ReactNode })`. Rende un frammento (chi lo usa lo mette nella sua colonna): mentre si sceglie, `before`, `IngredientPicker` (con `autoFocus`, `onCreate`, `createWhen="always"`, `disabled={busy}`) e `after`; mentre si crea, `NewIngredientFields` e l'eventuale errore. `onChosen` riceve l'ingrediente scelto, creato, o quello omonimo che il 409 porta.

- [ ] **Step 1: Il test che fallisce**

`frontend/src/features/stocking/IngredientChooser.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { IngredientChooser } from "./IngredientChooser";
import type { Ingredient } from "../../domain/types";

const CECI_NERI: Ingredient = {
  id: "i4", name: "ceci neri", display_name: "ceci neri", category: "legumi", kind: "food",
};

/** Un fetch che risponde in base a percorso e metodo. */
function stubRoutedFetch(route: (path: string, init?: RequestInit) => [unknown, number]) {
  const spy = vi.fn((input: unknown, init?: RequestInit) => {
    const [body, status] = route(String(input), init);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function renderChooser(busy = false) {
  const onChosen = vi.fn();
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <IngredientChooser
        label="Cosa hai comprato?"
        failureNote="Puoi comunque aggiungerlo."
        initialTerm="ceci neri"
        onChosen={onChosen}
        busy={busy}
        before={<p>prima</p>}
        after={<button type="button">dopo</button>}
      />
    </QueryClientProvider>
  );
  return { onChosen };
}

describe("IngredientChooser", () => {
  it("quel che sta prima e dopo il selettore c'è solo mentre si sceglie, e l'ingrediente creato è la scelta", async () => {
    stubRoutedFetch((path, init) =>
      path.endsWith("/ingredients") && init?.method === "POST" ? [CECI_NERI, 201] : [[], 200]
    );
    const { onChosen } = renderChooser();
    expect(screen.getByText("prima")).toBeDefined();
    expect(screen.getByRole("button", { name: "dopo" })).toBeDefined();

    // l'anagrafica non ha «ceci neri»: si crea qui, col nome da correggere
    await userEvent.click(await screen.findByRole("button", { name: "Aggiungi «ceci neri»" }));
    expect(screen.getByLabelText("Come si chiama in generale?")).toHaveValue("ceci neri");
    expect(screen.queryByText("prima")).toBeNull();
    expect(screen.queryByRole("button", { name: "dopo" })).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Crea l'ingrediente" }));
    await vi.waitFor(() => expect(onChosen).toHaveBeenCalledWith(CECI_NERI));
  });

  it("mentre la scelta di prima è in volo, il campo è spento", () => {
    stubRoutedFetch(() => [[], 200]);
    renderChooser(true);
    expect(screen.getByRole("textbox", { name: "Cosa hai comprato?" })).toBeDisabled();
  });
});
```

- [ ] **Step 2: Fallisce**

Run (da `<worktree>/frontend`): `npx vitest run src/features/stocking/IngredientChooser.test.tsx`
Expected: FAIL, `Failed to resolve import "./IngredientChooser"`.

- [ ] **Step 3: `IngredientChooser.tsx`**

```tsx
import { useState, type ReactNode } from "react";
import { useMutation } from "@tanstack/react-query";
import { NewIngredientFields } from "./NewIngredientFields";
import { createIngredient } from "../shopping-list/api";
import { ApiError } from "../../api/client";
import { IngredientPicker } from "../../components/IngredientPicker";
import { Alert } from "../../components/ui/Alert";
import type { Ingredient } from "../../domain/types";

/** L'ingrediente omonimo che il 409 di `POST /ingredients` porta in `existing`, se
 * l'errore è quello. Ogni altro fallimento torna `null` e tiene il suo messaggio. */
function existingIngredient(error: unknown): Ingredient | null {
  if (!(error instanceof ApiError) || error.status !== 409) return null;
  const body = error.body;
  if (body === null || typeof body !== "object" || !("existing" in body)) return null;
  return (body as { existing: Ingredient }).existing ?? null;
}

/**
 * Scegliere un ingrediente dal selettore unico (spec §3.5), oppure crearlo. Estratto da
 * `MatchPanel` (S3): lo usano «Abbina» e «Articolo aggiuntivo» in «Sistema la spesa», il
 * + della Dispensa e il passo «Di che ingrediente è?» della sua scansione. Il sistema non
 * inventa niente da solo.
 *
 * La creazione è sempre raggiungibile, anche quando la ricerca trova qualcosa
 * (`createWhen="always"`): legarla all'assenza di suggerimenti era il difetto S6,
 * corretto il 2026-09-20 — misurato in produzione, di sette nomi plausibili di prodotti
 * per la casa tutti e sette pescavano almeno un suggerimento.
 *
 * Un frammento: `before` e `after` (una frase, un «Annulla») stanno nella colonna di chi
 * lo usa, e solo mentre si sceglie — mentre si crea, `NewIngredientFields` ha il suo
 * «Annulla», che torna alla scelta.
 */
export function IngredientChooser({
  label,
  accessibleLabel,
  failureNote,
  initialTerm,
  onChosen,
  busy = false,
  before,
  after,
}: {
  label: string;
  accessibleLabel?: string;
  failureNote: string;
  initialTerm: string;
  onChosen: (ingredient: Ingredient) => void;
  /** La scrittura nata dalla scelta precedente è ancora in volo. */
  busy?: boolean;
  before?: ReactNode;
  after?: ReactNode;
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
        // sceglie. Chi è «lo stesso nome» lo decide il backend, che lo ha appena
        // rifiutato: niente confronto di nomi qui.
        const existing = existingIngredient(error);
        if (existing) return existing;
        throw error;
      }
    },
  });

  if (creating === null) {
    return (
      <>
        {before}
        <IngredientPicker
          label={label}
          accessibleLabel={accessibleLabel}
          failureNote={failureNote}
          initialTerm={initialTerm}
          autoFocus
          onPick={onChosen}
          onCreate={(name) => setCreating(name)}
          createWhen="always"
          disabled={busy}
        />
        {after}
      </>
    );
  }

  return (
    <>
      <NewIngredientFields
        initialName={creating}
        busy={create.isPending}
        // `onSuccess` passato a `mutate` e non alle opzioni di `useMutation`: queste
        // girano dalla Mutation stessa anche dopo `reset()`, e «Annulla» durante la
        // creazione in volo sceglierebbe l'ingrediente scartato; quelle di `mutate` si
        // fermano quando `reset()` stacca l'osservatore. Solo l'ingrediente: chi usa la
        // scelta si aspetta un unico argomento
        onSubmit={(fields) =>
          create.mutate(fields, { onSuccess: (ingredient) => onChosen(ingredient) })
        }
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
  );
}
```

- [ ] **Step 4: `MatchPanel.tsx` lo usa**

Sostituisci il file intero con:

```tsx
import { IngredientChooser } from "./IngredientChooser";
import { Button } from "../../components/ui/Button";
import type { Ingredient, ShoppingItem } from "../../domain/types";

/**
 * «Abbina», sotto una voce spuntata senza ingrediente (spec T3 §4.3): il testo libero
 * della lista non ha mai trovato un corrispondente, e la voce non può sparire in
 * silenzio dal conto finale. Si sceglie un ingrediente dal selettore unico, oppure lo si
 * crea: la scelta e la creazione (S6, S19) stanno in `IngredientChooser`, che usano
 * anche «Articolo aggiuntivo» e la Dispensa (S3).
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
  return (
    <div className="flex flex-col gap-3 rounded-card border border-line p-3">
      <h2 className="font-semibold">Abbina «{item.raw_text}»</h2>
      <IngredientChooser
        label="Abbina un ingrediente"
        accessibleLabel={`Abbina un ingrediente per ${item.raw_text}`}
        failureNote="Puoi comunque aggiungerlo."
        initialTerm={item.raw_text}
        onChosen={onMatched}
        before={
          <p className="text-sm text-ink-soft">
            Scegli a quale ingrediente corrisponde: senza, non entra in dispensa.
          </p>
        }
        after={
          <Button variant="ghost" onClick={onCancel} className="self-start">
            Annulla
          </Button>
        }
      />
    </div>
  );
}
```

- [ ] **Step 5: Passano, e `MatchPanel` non è cambiato a video**

Run: `npx vitest run src/features/stocking && npm run typecheck && npm run lint`
Expected: verde; **`IngredientChooser.test.tsx` 2 test**; `MatchPanel.test.tsx` e `StockingScreen.test.tsx` verdi senza essere toccati.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/stocking
git commit -m "refactor(stocking): IngredientChooser, la scelta o la creazione dell'ingrediente, esce da MatchPanel (S3)"
```

---

### Task 4: `ScannerPanel` con `label` e l'ingrediente atteso facoltativo; le frasi del codice nuovo

La scansione dalla Dispensa parte senza ingrediente: lì il prodotto trovato porta il suo, ed è quello che entra. La guardia del 409 resta nello stesso file, accesa quando l'ingrediente è atteso: una guardia, due modi.

**Files:**
- Modify: `frontend/src/features/stocking/ScannerPanel.tsx`
- Modify: `frontend/src/features/stocking/ScannerPanel.test.tsx` (come si monta il pannello, più due prove)
- Modify: `frontend/src/features/stocking/wording.ts`, `frontend/src/features/stocking/wording.test.ts`
- Modify: `frontend/src/features/stocking/OffSuggestionQuestion.tsx`
- Modify: `frontend/src/features/stocking/StockingScreen.tsx` (la sola chiamata a `ScannerPanel`)

**Interfaces:**
- Produces: `ScannerPanel` con `label: string | null` (al posto di `item`) e `ingredientId: string | null`; le altre prop come oggi. In `wording.ts`: `describeSuggestion(suggestion: ProductSuggestion): string` (spostata da `OffSuggestionQuestion.tsx`) e `newCodeNote(barcode: string, suggestion: ProductSuggestion | null, lookedUp?: "not_found" | "failed"): string`.

- [ ] **Step 1: I test**

1. In `ScannerPanel.test.tsx` cambia **solo come si monta il pannello** (le asserzioni non si toccano): togli la costante `YOGURT` e `ShoppingItem` dall'import dei tipi (`import type { BarcodeLookup, Product } from "../../domain/types";`), e `renderPanel` diventa:
   ```tsx
   function renderPanel(over: { label?: string | null; ingredientId?: string | null } = {}) {
     const props = {
       onProduct: vi.fn(), onNewCode: vi.fn(), onUnlinkedCode: vi.fn(), onCreateByHand: vi.fn(),
       onCancel: vi.fn(),
     };
     const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
     render(
       <QueryClientProvider client={client}>
         <ScannerPanel
           label={over.label === undefined ? "yogurt greco" : over.label}
           ingredientId={over.ingredientId === undefined ? "i1" : over.ingredientId}
           {...props}
         />
       </QueryClientProvider>
     );
     return props;
   }
   ```
2. In fondo al `describe("ScannerPanel", …)` aggiungi:
   ```tsx
     it("senza una voce il titolo dice solo «Codice a barre» (la scansione dalla Dispensa, S3)", () => {
       stubLookup(lookup({}));
       renderPanel({ label: null, ingredientId: null });
       expect(screen.getByRole("heading", { name: "Codice a barre" })).toBeDefined();
     });

     it("senza un ingrediente atteso, il prodotto di qualunque ingrediente si aggancia: porta il suo (S3)", async () => {
       stubLookup(lookup({ found: true, origin: "catalog", product: PARMIGIANO }));
       const { onProduct } = renderPanel({ label: null, ingredientId: null });
       await userEvent.type(screen.getByLabelText("Codice a barre"), "8009876543217{Enter}");
       await waitFor(() => expect(onProduct).toHaveBeenCalledWith(PARMIGIANO));
       expect(screen.queryByText(/di un altro ingrediente/)).toBeNull();
     });
   ```
3. In `wording.test.ts`, l'import diventa `import { elsewhereNote, newCodeNote, otherIngredient } from "./wording";` e in fondo aggiungi:
   ```ts
   describe("newCodeNote", () => {
     const CODE = "8001234567890";

     it("con un suggerimento, dice cosa ne sa Open Food Facts", () => {
       const suggestion = {
         name: "Lenticchie rosse", brand: "Coop", barcode: CODE, nutrients: {}, image_url: null,
       };
       expect(newCodeNote(CODE, suggestion)).toBe("Su Open Food Facts è «Lenticchie rosse», di Coop.");
     });

     it("senza codice, dice cosa resta da fare", () => {
       expect(newCodeNote("", null)).toBe(
         "Nessun codice a barre: scegli l'ingrediente, poi scrivi il prodotto."
       );
     });

     it("un lookup fallito non è un «non trovato»: non l'ha cercato nessuno", () => {
       expect(newCodeNote(CODE, null, "failed")).toBe(
         `Non ho potuto cercare il codice ${CODE}: scegli l'ingrediente, poi scrivi il prodotto.`
       );
     });

     it("un codice che nessuno conosce", () => {
       expect(newCodeNote(CODE, null, "not_found")).toBe(
         `Il codice ${CODE} non è in catalogo né su Open Food Facts.`
       );
     });
   });
   ```

- [ ] **Step 2: Falliscono**

Run: `npx vitest run src/features/stocking/ScannerPanel.test.tsx src/features/stocking/wording.test.ts`
Expected: FAIL — `newCodeNote` non esiste; le due prove nuove dello scanner falliscono (il titolo è «Codice a barre per «»» o simile, e il prodotto del burro finisce in `mismatch`); `npm run typecheck` segnalerebbe `label` sconosciuta.

- [ ] **Step 3: `wording.ts` e `OffSuggestionQuestion.tsx`**

1. In testa a `wording.ts`, dopo il commento del file, aggiungi l'import:
   ```ts
   import type { ProductSuggestion } from "./CustomProductForm";
   ```
2. In fondo a `wording.ts` aggiungi:
   ```ts
   /** Il nome di Open Food Facts in una frase sola: la dicono la domanda «È un …?» (S20) e
    * il passo «Di che ingrediente è?» della Dispensa (S3). */
   export function describeSuggestion(suggestion: ProductSuggestion): string {
     const what = suggestion.name ? `«${suggestion.name}»` : "senza nome";
     const by = suggestion.brand ? `, di ${suggestion.brand}` : "";
     return `Su Open Food Facts è ${what}${by}.`;
   }

   /** Che cosa si sa di un codice nuovo al catalogo, sopra la scelta dell'ingrediente
    * nella scansione dalla Dispensa (S3): perché si sappia di cosa si sta parlando prima
    * di dire di che ingrediente è. «Non trovato» solo quando qualcuno l'ha cercato. */
   export function newCodeNote(
     barcode: string,
     suggestion: ProductSuggestion | null,
     lookedUp?: "not_found" | "failed"
   ): string {
     if (suggestion) return describeSuggestion(suggestion);
     if (barcode === "") return "Nessun codice a barre: scegli l'ingrediente, poi scrivi il prodotto.";
     if (lookedUp === "failed") {
       return `Non ho potuto cercare il codice ${barcode}: scegli l'ingrediente, poi scrivi il prodotto.`;
     }
     return `Il codice ${barcode} non è in catalogo né su Open Food Facts.`;
   }
   ```
3. In `OffSuggestionQuestion.tsx` togli la funzione `describeSuggestion` (e il suo commento «Il nome di Open Food Facts accanto alla domanda, in una frase sola.») e aggiungi in testa `import { describeSuggestion } from "./wording";`.

- [ ] **Step 4: `ScannerPanel.tsx`**

1. L'import dei tipi diventa `import type { Product } from "../../domain/types";`.
2. Nel commento sopra la funzione, dopo «il codice che segue o non segue la voce (S8).», aggiungi la frase: «Senza ingrediente atteso (la scansione dalla Dispensa, S3) la guardia del 409 non ha niente con cui confrontare, e non serve: il prodotto trovato porta il suo ingrediente, ed è quello che entra.».
3. Nella firma, `item,` diventa `label,`, e nel tipo delle prop sostituisci:
   ```ts
     item: ShoppingItem;
     /** L'ingrediente della voce, dalla lista o abbinato in questo schermo: la guardia
      * qui sotto ci confronta il prodotto che il codice trova. */
     ingredientId: string;
   ```
   con:
   ```ts
     /** Di che cosa si legge il codice, nel titolo: il testo della voce in «Sistema la
      * spesa», l'ingrediente dal + della Dispensa. `null` nella scansione dalla
      * Dispensa, che parte senza: il titolo dice solo «Codice a barre». */
     label: string | null;
     /** L'ingrediente atteso: la guardia qui sotto ci confronta il prodotto che il
      * codice trova. `null` nella scansione dalla Dispensa (S3). */
     ingredientId: string | null;
   ```
4. In `lookup.onSuccess`, `if (product && product.ingredient_id !== ingredientId) {` diventa:
   ```ts
         if (product && ingredientId !== null && product.ingredient_id !== ingredientId) {
   ```
5. Il titolo:
   ```tsx
         <h2 className="font-semibold">Codice a barre per «{item.raw_text}»</h2>
   ```
   diventa:
   ```tsx
         <h2 className="font-semibold">
           {label === null ? "Codice a barre" : `Codice a barre per «${label}»`}
         </h2>
   ```
6. Nella frase del `mismatch`, `conferma «{item.raw_text}» come` diventa `conferma «{label}» come`.

- [ ] **Step 5: `StockingScreen.tsx` passa `label`**

Nella sola chiamata `<ScannerPanel` di `renderPanel`, `item={item}` diventa `label={item.raw_text}`. (Il Task 6 riscrive comunque il file: qui basta che compili.)

- [ ] **Step 6: Passano**

Run: `npx vitest run src/features/stocking && npm run typecheck && npm run lint`
Expected: verde; **+6 test** (2 in `ScannerPanel.test.tsx`, 4 in `wording.test.ts`); `StockingScreen.test.tsx` verde senza essere toccato.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/stocking
git commit -m "feat(stocking): ScannerPanel con label e l'ingrediente atteso facoltativo; describeSuggestion e newCodeNote in wording (S3)"
```

---

### Task 5: `ProductResolver` — la regia dei pannelli per un bersaglio

Il cuore dell'estrazione: ciò che oggi sta dentro `StockingScreen` fra il tipo `Panel`, `proceedWithNewCode`, `openProductForm`, la domanda di Open Food Facts, il codice che segue (S8), la `key` del modulo e la regola dell'esito tardivo. Più il modo senza ingrediente atteso. In questo task nasce con le sue prove; il Task 6 lo fa usare a `StockingScreen`.

**Files:**
- Create: `frontend/src/features/stocking/ProductResolver.tsx`
- Create: `frontend/src/features/stocking/ProductResolver.test.tsx`

**Interfaces:**
- Consumes: `ScannerPanel` (Task 4), `IngredientChooser` (Task 3), `newCodeNote` (Task 4), `CatalogSearchPanel`, `CustomProductForm` e `ProductSuggestion`, `OffSuggestionQuestion`, `Resolution` e `PanelTrigger` da `stockingView.ts`, `capitalizeFirst` da `lib/text.ts`.
- Produces:
  ```ts
  export type ResolverIngredient = { id: string; name: string; kind: "food" | "non_food" | null };
  export function ProductResolver(props: {
    label: string | null;                       // nei titoli; null: la scansione dalla Dispensa
    ingredient: ResolverIngredient | null;      // null solo con start "scanner"
    start: "scanner" | "catalog";
    rememberedCode: string | undefined;         // il codice letto e rimasto senza prodotto (S8), tenuto da chi lo usa
    onRememberCode: (code: string | null) => void;
    onResolved: (resolution: Resolution, ingredient: ResolverIngredient) => void;
    onStep?: (trigger: PanelTrigger) => void;   // un passo nuovo è comparso: chi l'ha aperto, per il fuoco
    onCancel: (trigger: PanelTrigger) => void;  // chiuso senza scegliere, dal passo aperto da `trigger`
  }): JSX.Element | null;
  ```
  Chi lo usa lo rimonta (`key`) per aprire un pannello nuovo: un'istanza è un'apertura.

- [ ] **Step 1: I test che falliscono**

`frontend/src/features/stocking/ProductResolver.test.tsx`:

```tsx
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ProductResolver, type ResolverIngredient } from "./ProductResolver";
import type { Resolution } from "./stockingView";
import type { Ingredient, Product } from "../../domain/types";

const YOGURT: ResolverIngredient = { id: "i1", name: "yogurt greco", kind: "food" };
const LENTICCHIE: Ingredient = {
  id: "i3", name: "lenticchie", display_name: "Lenticchie", category: "legumi", kind: "food",
};
const FAGE: Product = {
  id: "p1", ingredient_id: "i1", ingredient_name: "yogurt greco", name: "Total 0%", brand: "Fage",
  barcode: "52010", source: "openfoodfacts", nutrients: null, image_url: null,
};
// un parmigiano registrato sotto «burro» (S9): con l'ingrediente atteso non si aggancia,
// senza porta il suo
const PARMIGIANO: Product = {
  id: "p2", ingredient_id: "i8", ingredient_name: "burro", name: "Parmigiano Reggiano",
  brand: null, barcode: "8009876543217", source: "custom", nutrients: null, image_url: null,
};
const DECORTICATE: Product = {
  id: "p5", ingredient_id: "i3", ingredient_name: "lenticchie", name: "Lenticchie decorticate",
  brand: "Coop", barcode: null, source: "custom", nutrients: null, image_url: null,
};
const CODE = "8001234567890";
const UNKNOWN = { found: false, origin: "unknown", product: null, suggestion: null, valid_checksum: true };
const IN_CATALOG = (product: Product) => ({
  found: true, origin: "catalog", product, suggestion: null, valid_checksum: true,
});

function respond(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function stubRoutedFetch(route: (path: string, init?: RequestInit) => unknown) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => Promise.resolve(respond(route(String(url), init))));
  vi.stubGlobal("fetch", spy);
  return spy;
}

/** Il resolver come lo usa uno schermo: il codice ricordato sta fuori, e sopravvive. */
function Harness(props: {
  ingredient: ResolverIngredient | null;
  label: string | null;
  onResolved: (resolution: Resolution, ingredient: ResolverIngredient) => void;
  onCancel: (trigger: string) => void;
}) {
  const [code, setCode] = useState<string | undefined>(undefined);
  return (
    <ProductResolver
      {...props}
      start="scanner"
      rememberedCode={code}
      onRememberCode={(next) => setCode(next ?? undefined)}
    />
  );
}

function renderResolver(over: { ingredient?: ResolverIngredient | null; label?: string | null } = {}) {
  const onResolved = vi.fn();
  const onCancel = vi.fn();
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <Harness
        ingredient={over.ingredient === undefined ? YOGURT : over.ingredient}
        label={over.label === undefined ? "yogurt greco" : over.label}
        onResolved={onResolved}
        onCancel={onCancel}
      />
    </QueryClientProvider>
  );
  return { onResolved, onCancel };
}

async function readCode(code: string) {
  await userEvent.type(screen.getByLabelText("Codice a barre"), `${code}{Enter}`);
}

describe("ProductResolver", () => {
  it("con l'ingrediente, il codice di un suo prodotto risolve col prodotto e con l'ingrediente atteso", async () => {
    stubRoutedFetch(() => IN_CATALOG(FAGE));
    const { onResolved } = renderResolver();
    await readCode("52010");
    await vi.waitFor(() =>
      expect(onResolved).toHaveBeenCalledWith({ kind: "product", product: FAGE }, YOGURT)
    );
  });

  it("un esito arrivato dopo «Annulla» non risolve niente", async () => {
    // react-query chiama gli `on…` di una mutazione anche quando nessuno guarda più
    let answer: (response: Response) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>((resolve) => { answer = resolve; }))
    );
    const { onResolved, onCancel } = renderResolver();
    await readCode("52010");
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(onCancel).toHaveBeenCalledWith("scanner");

    await act(async () => {
      answer(respond(IN_CATALOG(FAGE)));
      await new Promise((resolve) => setTimeout(resolve, 50));
    });
    expect(onResolved).not.toHaveBeenCalled();
  });

  it("senza ingrediente, il prodotto di qualunque ingrediente risolve, col suo ingrediente", async () => {
    stubRoutedFetch(() => IN_CATALOG(PARMIGIANO));
    const { onResolved } = renderResolver({ ingredient: null, label: null });
    expect(screen.getByRole("heading", { name: "Codice a barre" })).toBeDefined();
    await readCode("8009876543217");
    await vi.waitFor(() =>
      expect(onResolved).toHaveBeenCalledWith(
        { kind: "product", product: PARMIGIANO },
        { id: "i8", name: "burro", kind: null }
      )
    );
  });

  it("senza ingrediente, un codice nuovo chiede l'ingrediente; dal modulo il catalogo porta il codice letto (S8)", async () => {
    stubRoutedFetch((path) => {
      if (path.includes("/products/barcode/")) return UNKNOWN;
      if (path.includes("/ingredients/search")) return [LENTICCHIE];
      if (path.includes("/products/search")) return [DECORTICATE];
      return [];
    });
    const { onResolved, onCancel } = renderResolver({ ingredient: null, label: null });
    await readCode(CODE);

    expect(await screen.findByRole("heading", { name: "Di che ingrediente è?" })).toBeDefined();
    expect(screen.getByText(`Il codice ${CODE} non è in catalogo né su Open Food Facts.`)).toBeDefined();
    await userEvent.type(screen.getByRole("textbox", { name: "Ingrediente" }), "lentic");
    await userEvent.click(await screen.findByRole("option", { name: "Lenticchie" }));

    // il modulo, senza la domanda «È un …?»: l'ingrediente l'ha appena detto chi legge
    expect(await screen.findByRole("heading", { name: /Nuovo prodotto per «Lenticchie»/ })).toBeDefined();
    expect(screen.queryByRole("heading", { name: /^È un/ })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Cerca a catalogo" }));
    await userEvent.click(await screen.findByRole("option", { name: /Lenticchie decorticate/ }));

    expect(onResolved).toHaveBeenCalledWith(
      { kind: "product", product: DECORTICATE, barcode: CODE },
      { id: "i3", name: "lenticchie", kind: "food" }
    );
    expect(onCancel).not.toHaveBeenCalled();
  });

  it("senza ingrediente, dal modulo si esce sfusi; e «Annulla» dopo il codice torna allo scanner", async () => {
    stubRoutedFetch((path) => {
      if (path.includes("/products/barcode/")) return UNKNOWN;
      if (path.includes("/ingredients/search")) return [LENTICCHIE];
      return [];
    });
    const { onResolved, onCancel } = renderResolver({ ingredient: null, label: null });
    await readCode(CODE);
    await screen.findByRole("heading", { name: "Di che ingrediente è?" });
    // c'è una confezione in mano: «Annulla» non chiude, torna a leggere
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(screen.getByRole("heading", { name: "Codice a barre" })).toBeDefined();
    expect(screen.getByLabelText("Codice a barre")).toHaveValue("");
    expect(onCancel).not.toHaveBeenCalled();

    await readCode(CODE);
    await userEvent.type(await screen.findByRole("textbox", { name: "Ingrediente" }), "lentic");
    await userEvent.click(await screen.findByRole("option", { name: "Lenticchie" }));
    await userEvent.click(await screen.findByRole("button", { name: "Sfuso, senza marca" }));
    expect(onResolved).toHaveBeenCalledWith(
      { kind: "loose" },
      { id: "i3", name: "lenticchie", kind: "food" }
    );
  });

  it("con l'ingrediente, il modulo non offre lo sfuso né il catalogo: la voce ha già le sue strade", async () => {
    stubRoutedFetch(() => UNKNOWN);
    renderResolver();
    await readCode(CODE);
    expect(await screen.findByRole("heading", { name: /Nuovo prodotto per «yogurt greco»/ })).toBeDefined();
    expect(screen.queryByRole("button", { name: "Sfuso, senza marca" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Cerca a catalogo" })).toBeNull();
  });
});
```

- [ ] **Step 2: Falliscono**

Run: `npx vitest run src/features/stocking/ProductResolver.test.tsx`
Expected: FAIL, `Failed to resolve import "./ProductResolver"`.

- [ ] **Step 3: `ProductResolver.tsx`**

```tsx
import { useEffect, useRef, useState } from "react";
import { CatalogSearchPanel } from "./CatalogSearchPanel";
import { CustomProductForm, type ProductSuggestion } from "./CustomProductForm";
import { IngredientChooser } from "./IngredientChooser";
import { OffSuggestionQuestion } from "./OffSuggestionQuestion";
import { ScannerPanel } from "./ScannerPanel";
import type { PanelTrigger, Resolution } from "./stockingView";
import { newCodeNote } from "./wording";
import { Button } from "../../components/ui/Button";
import { IconListSearch, IconScale } from "../../components/ui/icons";
import { capitalizeFirst } from "../../lib/text";
import type { Ingredient } from "../../domain/types";

/** L'ingrediente a cui il prodotto si lega. `name` è quello canonico
 * (`Ingredient.name`, in minuscolo): lo stesso che il server manda come
 * `ingredient_name` di una voce o di un prodotto. `kind` `null` vuol dire «non lo so»
 * (un prodotto trovato dal codice non lo porta), e decide solo se il modulo chiede i
 * nutrienti: un detersivo non ha calorie. */
export type ResolverIngredient = {
  id: string;
  name: string;
  kind: "food" | "non_food" | null;
};

type LookedUp = "not_found" | "failed";

/** Il passo aperto: uno alla volta, in un solo stato (T3 Consegna 3). */
type Step =
  | { kind: "scanner" }
  | { kind: "catalog" }
  // il codice nuovo al catalogo che Open Food Facts conosce, per un ingrediente già
  // noto: prima del modulo, la domanda (S20)
  | { kind: "off-question"; barcode: string; suggestion: ProductSuggestion }
  // il codice nuovo nella scansione dalla Dispensa (S3): prima di tutto, di che
  // ingrediente è
  | { kind: "ingredient"; barcode: string; suggestion: ProductSuggestion | null; lookedUp?: LookedUp }
  | {
      kind: "product-form";
      /** Chi l'ha aperto: lì torna il fuoco, annullando. */
      trigger: PanelTrigger;
      barcode: string;
      suggestion: ProductSuggestion | null;
      lookedUp?: LookedUp;
    };

type IngredientStep = Extract<Step, { kind: "ingredient" }>;

/** Il pulsante che aveva aperto il passo, per chi deve rimettergli il fuoco. */
function triggerOf(step: Step): PanelTrigger {
  if (step.kind === "catalog") return "catalog";
  if (step.kind === "product-form") return step.trigger;
  return "scanner";
}

/**
 * La regia dei pannelli che legano una confezione a un prodotto (S3): il codice a
 * barre, il catalogo, la domanda di Open Food Facts, il modulo del prodotto nuovo.
 * Estratta da `StockingScreen`, che la usa per ogni confezione di una voce; la usa anche
 * la Dispensa, per l'ingresso diretto. Una copia sola, perché è qui che stanno le
 * guardie che la prima lezione di `CLAUDE.md` dice di non duplicare:
 *
 * - **l'esito tardivo**: le mutazioni dei pannelli (il lookup del codice, la creazione
 *   del prodotto) chiamano i loro `on…` anche a pannello chiuso o smontato — react-query
 *   li tiene — e con la chiusura di un render passato. Un esito vale solo se il suo passo
 *   è ancora quello aperto (lo stesso oggetto: riaperto è un altro) e il resolver è
 *   ancora montato. Dopo «Annulla», o con un'altra voce davanti, non sceglie niente;
 * - **il codice che segue (S8)**: il codice letto e rimasto senza prodotto — ignoto al
 *   catalogo, o lookup fallito — segue il catalogo e il modulo, da qualunque passo ci si
 *   arrivi. Lo tiene chi usa il resolver (`rememberedCode`), perché deve sopravvivere al
 *   pannello che si chiude; quando seguirlo lo decide solo questo file. Lo sfuso non lo
 *   legge: non c'è un prodotto a cui darlo;
 * - **la `key` del modulo**: un modulo riusato per un altro codice terrebbe i campi di
 *   prima, e salverebbe il prodotto sbagliato in silenzio.
 *
 * Due modi. **Con l'ingrediente** (una voce di «Sistema la spesa», il + della Dispensa)
 * la guardia del 409 è accesa nello scanner, un codice nuovo noto a Open Food Facts passa
 * dalla domanda «È un …?», e annullare chiude. **Senza** (la scansione dalla Dispensa) il
 * prodotto trovato porta il suo ingrediente; un codice nuovo chiede prima di che
 * ingrediente è (`IngredientChooser`, che può crearlo), poi il modulo senza domanda —
 * l'ingrediente l'ha appena detto chi legge —; dal modulo si esce anche sfusi o dal
 * catalogo; e annullare un passo dopo lo scanner torna allo scanner, perché c'è una
 * confezione in mano.
 */
export function ProductResolver({
  label,
  ingredient,
  start,
  rememberedCode,
  onRememberCode,
  onResolved,
  onStep,
  onCancel,
}: {
  /** Di che cosa, nei titoli dei pannelli. `null`: la scansione dalla Dispensa, che
   * parte senza; dopo la scelta dell'ingrediente i titoli dicono il suo nome. */
  label: string | null;
  /** L'ingrediente atteso; `null` solo con `start` "scanner". */
  ingredient: ResolverIngredient | null;
  start: "scanner" | "catalog";
  rememberedCode: string | undefined;
  onRememberCode: (code: string | null) => void;
  onResolved: (resolution: Resolution, ingredient: ResolverIngredient) => void;
  /** Un passo nuovo è comparso al posto di un altro: il pulsante che aveva il fuoco è
   * sparito, e chi ospita il resolver sa dove rimetterlo. */
  onStep?: (trigger: PanelTrigger) => void;
  onCancel: (trigger: PanelTrigger) => void;
}) {
  const [first] = useState<Step>(() =>
    start === "scanner" ? { kind: "scanner" } : { kind: "catalog" }
  );
  const [step, setStep] = useState<Step>(first);
  // Il passo aperto adesso, per chi arriva in ritardo (vedi sopra): un ref e non lo
  // stato, perché l'esito tardivo legge la chiusura di un render passato
  const current = useRef<Step | null>(first);
  const alive = useRef(false);
  // l'ingrediente scelto nel passo «Di che ingrediente è?», senza ingrediente atteso
  const [chosen, setChosen] = useState<ResolverIngredient | null>(null);
  // ogni ritorno allo scanner lo fa rinascere: la fotocamera si rilascia al primo codice
  // letto (`BarcodeScanner`), e chi torna a leggere ne vuole una accesa e un campo vuoto
  const [scannerRound, setScannerRound] = useState(0);
  const target = ingredient ?? chosen;

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  function isOpen(which: Step): boolean {
    return alive.current && current.current === which;
  }

  function show(next: Step) {
    current.current = next;
    setStep(next);
    onStep?.(triggerOf(next));
  }

  function backToScanner() {
    setChosen(null);
    // il codice di prima è di una confezione scartata: non segue la prossima
    onRememberCode(null);
    setScannerRound((round) => round + 1);
    show({ kind: "scanner" });
  }

  /** Chiude senza scegliere. Senza ingrediente atteso, un passo dopo lo scanner torna a
   * leggere; lo scanner stesso, e ogni passo con l'ingrediente, chiudono. */
  function close(which: Step) {
    if (!isOpen(which)) return;
    if (ingredient === null && which.kind !== "scanner") {
      backToScanner();
      return;
    }
    current.current = null;
    onCancel(triggerOf(which));
  }

  /** La scelta arrivata da un passo: vale solo se quel passo è ancora aperto. */
  function resolveFrom(which: Step, resolution: Resolution, of: ResolverIngredient) {
    if (!isOpen(which)) return;
    current.current = null;
    onResolved(resolution, of);
  }

  /** Un codice nuovo al catalogo, che si è deciso di usare: senza ingrediente, prima
   * l'ingrediente; con, se Open Food Facts lo conosce si chiede se è lui, se no il
   * modulo. Il codice da qui segue il catalogo e il modulo (S8). */
  function proceedWithNewCode(which: Step, code: string, suggestion: ProductSuggestion | null) {
    if (!isOpen(which)) return;
    onRememberCode(code);
    if (target === null) {
      show({
        kind: "ingredient",
        barcode: code,
        suggestion,
        lookedUp: suggestion ? undefined : "not_found",
      });
      return;
    }
    show(
      suggestion
        ? { kind: "off-question", barcode: code, suggestion }
        : {
            kind: "product-form",
            trigger: "scanner",
            barcode: code,
            suggestion: null,
            lookedUp: "not_found",
          }
    );
  }

  /** «Crea il prodotto a mano», dallo scanner o dal catalogo. Il codice letto prima
   * segue anche questa uscita (S8), da qualunque passo si arrivi. */
  function openProductForm(trigger: PanelTrigger, barcode: string, lookedUp?: "failed") {
    const code = barcode || rememberedCode || "";
    if (target === null) {
      show({ kind: "ingredient", barcode: code, suggestion: null, lookedUp });
      return;
    }
    show({ kind: "product-form", trigger, barcode: code, suggestion: null, lookedUp });
  }

  function chooseIngredient(which: IngredientStep, picked: Ingredient) {
    if (!isOpen(which)) return;
    setChosen({ id: picked.id, name: picked.name, kind: picked.kind });
    show({
      kind: "product-form",
      trigger: "scanner",
      barcode: which.barcode,
      suggestion: which.suggestion,
      lookedUp: which.lookedUp,
    });
  }

  if (step.kind === "scanner") {
    return (
      <ScannerPanel
        key={scannerRound}
        label={label}
        ingredientId={ingredient?.id ?? null}
        onProduct={(product) =>
          resolveFrom(
            step,
            { kind: "product", product },
            // senza ingrediente atteso, entra quello del prodotto: lo dice il server
            ingredient ?? { id: product.ingredient_id, name: product.ingredient_name, kind: null }
          )
        }
        onNewCode={(code, suggestion) => proceedWithNewCode(step, code, suggestion)}
        onUnlinkedCode={onRememberCode}
        onCreateByHand={(code, lookedUp) => openProductForm("scanner", code, lookedUp)}
        onCancel={() => close(step)}
      />
    );
  }

  if (step.kind === "ingredient") {
    return (
      <div className="flex flex-col gap-3 rounded-card border border-line p-3">
        <h2 className="font-semibold">Di che ingrediente è?</h2>
        {/* nome e marca di Open Food Facts, o cosa si sa del codice: perché si sappia di
            cosa si sta parlando. Il campo parte vuoto: il nome di un prodotto non deve
            diventare il nome di un ingrediente */}
        <p className="text-sm text-ink">{newCodeNote(step.barcode, step.suggestion, step.lookedUp)}</p>
        <IngredientChooser
          label="Ingrediente"
          failureNote="Puoi comunque aggiungerlo."
          initialTerm=""
          onChosen={(picked) => chooseIngredient(step, picked)}
          after={
            <Button variant="ghost" onClick={() => close(step)} className="self-start">
              Annulla
            </Button>
          }
        />
      </div>
    );
  }

  // ogni altro passo lega un prodotto a un ingrediente: senza, niente da mostrare (non
  // succede: senza ingrediente atteso ci si arriva solo dopo averlo scelto)
  if (target === null) return null;
  const targetLabel = label ?? capitalizeFirst(target.name);

  if (step.kind === "catalog") {
    return (
      <CatalogSearchPanel
        itemLabel={targetLabel}
        ingredientId={target.id}
        // il codice letto un attimo prima segue anche questa uscita (S8): senza, la
        // prossima scansione dello stesso codice non trovava niente
        onPicked={(product) =>
          resolveFrom(step, { kind: "product", product, barcode: rememberedCode }, target)
        }
        onCreateByHand={() => openProductForm("catalog", "")}
        onCancel={() => close(step)}
      />
    );
  }

  if (step.kind === "off-question") {
    return (
      <OffSuggestionQuestion
        ingredientName={target.name}
        suggestion={step.suggestion}
        onYes={() =>
          show({
            kind: "product-form",
            trigger: "scanner",
            barcode: step.barcode,
            suggestion: step.suggestion,
          })
        }
        onNo={() => {
          // indietro a prima del codice. Il codice non segue — è di un'altra cosa, e dal
          // catalogo finirebbe al prodotto sbagliato
          onRememberCode(null);
          close(step);
        }}
      />
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="rounded-card border border-line">
        <CustomProductForm
          // senza key React riusa l'istanza passando da un codice all'altro: i campi
          // restano quelli di prima mentre il codice è già il nuovo, e si salva il
          // prodotto sbagliato, in silenzio. Fra due bersagli diversi rinasce il resolver
          key={step.barcode}
          ingredientId={target.id}
          itemLabel={targetLabel}
          barcode={step.barcode}
          suggestion={step.suggestion}
          lookedUp={step.lookedUp}
          isNonFood={target.kind === "non_food"}
          onCreated={(product) => resolveFrom(step, { kind: "product", product }, target)}
          onCancel={() => close(step)}
        />
      </div>
      {/* Senza ingrediente atteso non ci sono le icone di una voce sotto cui tornare:
          le altre due strade stanno qui. Lo sfuso è «mai un vicolo cieco» (bozza §4.2);
          il catalogo trova il prodotto che c'è già senza codice, e il codice lo segue
          (S8) — B, deciso da Mattia il 2026-10-09 */}
      {ingredient === null && (
        <div className="flex flex-wrap gap-2">
          <Button icon={IconListSearch} onClick={() => show({ kind: "catalog" })}>
            Cerca a catalogo
          </Button>
          <Button icon={IconScale} onClick={() => resolveFrom(step, { kind: "loose" }, target)}>
            Sfuso, senza marca
          </Button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Passano**

Run: `npx vitest run src/features/stocking && npm run typecheck && npm run lint`
Expected: verde; **`ProductResolver.test.tsx` 6 test**. Se il lint segnala `react-hooks/refs` su `useRef<Step | null>(first)`, non lo è: il ref si legge e si scrive solo nei gestori; se la regola lo segnala comunque, inizializza il ref a `null` e assegnalo in un `useEffect` di montaggio insieme ad `alive` (scrivilo nel report).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/stocking
git commit -m "feat(stocking): ProductResolver, la regia dei pannelli per una confezione, con l'ingrediente atteso o senza (S3)"
```

---

### Task 6: `StockingScreen` usa `ProductResolver`

Un rifacimento senza comportamento nuovo, e la prova dell'estrazione: `StockingScreen.test.tsx` (una cinquantina di prove, comprese quelle dell'esito tardivo, del codice che segue e del fuoco) passa **senza essere toccato**. Lo schermo tiene per sé ciò che è della lista — le scelte, le scadenze e i codici per confezione, l'abbinamento salvato sulla voce (S19), la sistemazione tutto-o-niente e il suo errore — e indicizza già i pannelli **per confezione** (`packageKey`): la prima confezione di una voce ha la chiave della voce, e il Task 9 aggiunge le altre.

**Files:**
- Modify: `frontend/src/features/stocking/StockingScreen.tsx` (intero)

**Interfaces:**
- Consumes: `ProductResolver`, `ResolverIngredient` (Task 5), `MatchPanel` (Task 3), `StockingRow` (Task 2).
- Produces (per i Task 9 e 10, dentro il file): il tipo `Panel` con `{ kind: "resolver"; packageKey; start; serial }`; le funzioni `show`, `openPanelFor(item, packageKey, trigger)`, `closePanel(which, trigger)`, `resolve(packageKey, resolution)`, `changeResolution(packageKey)`, `writeExpiry(packageKey, value)`, `returnFocusFor(packageKey, item)`, `panelFor(item, packageKey)`, `renderRow(item)`; gli stati `resolved`, `expiry`, `rememberedCode` (per confezione), `returnFocus` (`{ key, target }`), `refocusAfterMatch`.

- [ ] **Step 1: La rete**

Run: `npx vitest run src/features/stocking/StockingScreen.test.tsx`
Expected: verde. Annota il numero di test: alla fine del task è lo stesso.

- [ ] **Step 2: Il file**

Sostituisci `frontend/src/features/stocking/StockingScreen.tsx` intero con:

```tsx
import { useCallback, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { fetchShoppingList, patchShoppingItem } from "../shopping-list/api";
import { groupForDisplay } from "../shopping-list/listView";
import { MatchPanel } from "./MatchPanel";
import { ProductResolver } from "./ProductResolver";
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

/** «Abbina», sotto una voce senza ingrediente: è della voce. */
type MatchPanelState = { itemId: string; kind: "match" };

/** Il codice, il catalogo e quel che ne segue: sono di una confezione, e li dirige
 * `ProductResolver` (S3). La prima confezione di una voce ha la chiave della voce
 * (`packageKey === itemId`). `serial` distingue due aperture: riaperto è un altro
 * pannello, e il suo resolver rinasce. */
type ResolverPanelState = {
  itemId: string;
  kind: "resolver";
  packageKey: string;
  start: "scanner" | "catalog";
  serial: number;
};

/** Il pannello aperto: uno alla volta, in un solo stato (T3 Consegna 3). Prima erano
 * quattro stati sparsi, e due pannelli potevano stare aperti insieme sulla stessa voce
 * — dicendo due cose diverse su cosa stava per entrare in dispensa. */
type Panel = MatchPanelState | ResolverPanelState;

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
    "Se insiste, è il server che non risponde: le conferme restano su questo schermo."
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

  // Le scelte, le scadenze e i codici sono per confezione (S3 §10.2): la prima
  // confezione di una voce ha la chiave della voce, come prima che ce ne fossero altre.
  const [resolved, setResolved] = useState<Record<string, Resolution>>({});
  // La scadenza scritta per confezione. Una chiave presente è un campo aperto — anche
  // vuoto, appena toccato «+ scadenza» — e la ✕ la toglie. Sta qui e non nella riga: la
  // riga sparisce mentre un'altra voce ha il pannello aperto (decisione 1), e la data
  // scritta non deve sparire con lei.
  const [expiry, setExpiry] = useState<Record<string, string>>({});
  // voci senza ingredient_id, abbinate a mano in questo schermo
  const [matchedIngredient, setMatchedIngredient] = useState<Record<string, Ingredient>>({});
  // S19: l'abbinamento fatto qui e non scritto sulla voce, con l'ingrediente per
  // riprovare. La voce resta sistemabile lo stesso, dal match locale
  const [matchNotSaved, setMatchNotSaved] = useState<Record<string, Ingredient>>({});
  // Il codice letto per una confezione e rimasto senza prodotto (S8). Lo tiene lo
  // schermo perché sopravviva al pannello che si chiude: chi chiude il modulo e passa
  // dal catalogo lo ritrova. Quando seguirlo lo decide ProductResolver.
  const [rememberedCode, setRememberedCode] = useState<Record<string, string>>({});
  const [panel, setPanel] = useState<Panel | null>(null);
  // Il pannello aperto adesso, per chi arriva in ritardo: la creazione di un
  // ingrediente in «Abbina» chiama i suoi `on…` anche a pannello chiuso. Un esito vale
  // solo se il suo pannello è ancora quello aperto (lo stesso oggetto: riaperto è un
  // altro). I pannelli di una confezione hanno la stessa guardia dentro ProductResolver
  const openPanel = useRef<Panel | null>(null);
  const panelSerial = useRef(0);
  // dove rimettere il fuoco quando la riga di una confezione rinasce (vedi StockingRow)
  const [returnFocus, setReturnFocus] = useState<{ key: string; target: FocusTarget } | null>(
    null
  );
  // La voce appena abbinata, finché la rilettura non la rimette nel suo reparto (S19).
  // Il fuoco sulla prima icona (decisione 18) non sopravvive al trasloco: la riga lascia
  // la sezione «Senza reparto» e rinasce in un'altra, e il pulsante che lo aveva sparisce
  // con la vecchia. La richiesta aspetta la voce riletta, che porta il suo ingrediente,
  // e scatta dove la riga rinasce; la riga non ruba il fuoco a chi è già altrove.
  const [refocusAfterMatch, setRefocusAfterMatch] = useState<string | null>(null);
  const clearReturnFocus = useCallback(() => {
    setReturnFocus(null);
    setRefocusAfterMatch(null);
  }, []);

  function setOpen(next: Panel | null) {
    openPanel.current = next;
    setPanel(next);
  }

  function isOpen(which: Panel): boolean {
    return openPanel.current === which;
  }

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

  // S19: l'abbinamento viveva solo nello stato fino a «Metti in dispensa». Una voce che
  // oggi non entra in dispensa lo perdeva, e in lista restava sotto «Senza reparto».
  // Adesso si scrive subito sulla voce; il match locale resta, così un salvataggio
  // fallito non toglie niente a chi sta sistemando la spesa.
  const persistMatch = useMutation({
    mutationFn: ({ item, ingredient }: { item: ShoppingItem; ingredient: Ingredient }) =>
      patchShoppingItem(item.id, { ingredient_id: ingredient.id }),
    onSuccess: (_saved, { item }) => {
      setMatchNotSaved((prev) => without(prev, item.id));
      setRefocusAfterMatch(item.id);
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
    setOpen(next);
    // chi apre un pannello ha già il fuoco altrove: l'abbinamento in attesa di
    // rilettura non deve riprenderselo quando la vista torna intera
    setRefocusAfterMatch(null);
    if (next.kind === "resolver") setReturnFocus({ key: next.packageKey, target: next.start });
  }

  function openPanelFor(item: ShoppingItem, packageKey: string, trigger: PanelTrigger) {
    if (trigger === "match") {
      show({ itemId: item.id, kind: "match" });
      return;
    }
    panelSerial.current += 1;
    show({ itemId: item.id, kind: "resolver", packageKey, start: trigger, serial: panelSerial.current });
  }

  /** Chiude il pannello senza scegliere: tutto torna a video, e il fuoco torna al
   * pulsante che l'aveva aperto (decisione 1). */
  function closePanel(which: Panel, trigger: PanelTrigger) {
    if (!isOpen(which)) return;
    setReturnFocus({ key: which.kind === "resolver" ? which.packageKey : which.itemId, target: trigger });
    setOpen(null);
  }

  /** Una scelta fatta: chiude il pannello di questa confezione, se c'è. Le tre icone
   * lasciano il posto a «Cambia», e il fuoco va lì. */
  function resolve(packageKey: string, resolution: Resolution) {
    setResolved((prev) => ({ ...prev, [packageKey]: resolution }));
    const open = openPanel.current;
    if (open?.kind === "resolver" && open.packageKey === packageKey) setOpen(null);
    setReturnFocus({ key: packageKey, target: "change" });
  }

  /** Disfa la scelta di una confezione, lasciando intatte le altre. Azzera anche
   * l'errore della sistemazione, che parlava di un tentativo fatto su scelte che da
   * adesso non sono più quelle. */
  function changeResolution(packageKey: string) {
    setResolved((prev) => without(prev, packageKey));
    stock.reset();
    setReturnFocus({ key: packageKey, target: "scanner" });
  }

  function matchIngredient(which: MatchPanelState, item: ShoppingItem, ingredient: Ingredient) {
    // un ingrediente creato dopo «Annulla» resta in anagrafica, e il selettore lo
    // ritrova: la voce però non si abbina da sola a cose chiuse
    if (!isOpen(which)) return;
    setMatchedIngredient((prev) => ({ ...prev, [item.id]: ingredient }));
    persistMatch.mutate({ item, ingredient });
    setOpen(null);
    // ora la voce ha le tre icone: il fuoco va alla prima (decisione 18)
    setReturnFocus({ key: item.id, target: "scanner" });
  }

  function writeExpiry(packageKey: string, value: string | undefined) {
    setExpiry((prev) =>
      value === undefined ? without(prev, packageKey) : { ...prev, [packageKey]: value }
    );
  }

  // una fonte per il corpo della richiesta e per il numero sul pulsante (decisione 4)
  const entries = stockEntries(items, resolved, ingredientOf, expiry);

  function submitStock() {
    // la guardia al posto di `disabled`: il pulsante resta dov'è il fuoco
    if (entries.length === 0 || stock.isPending) return;
    stock.mutate({ sent: entries, checked: items.length });
  }

  function renderMatch(item: ShoppingItem, open: MatchPanelState) {
    return (
      <MatchPanel
        key={item.id}
        item={item}
        onMatched={(ingredient) => matchIngredient(open, item, ingredient)}
        onCancel={() => closePanel(open, "match")}
      />
    );
  }

  function renderResolver(item: ShoppingItem, open: ResolverPanelState) {
    // ogni pannello di una confezione lega un prodotto a un ingrediente: una voce senza
    // non ha le tre icone, e un pannello rimasto aperto su di lei non ha niente da
    // mostrare. Lo scanner in particolare confronta il prodotto trovato con questo
    // ingrediente (la guardia del 409): senza, non ha niente con cui confrontarlo
    const ingredientId = ingredientOf(item);
    if (!ingredientId) return null;
    const key = open.packageKey;
    return (
      <ProductResolver
        // un'apertura, un resolver: il codice scritto a mano per un'altra confezione non
        // sopravvive nel campo (S8), e un esito tardivo trova il resolver già smontato
        key={`${key}:${open.serial}`}
        label={item.raw_text}
        ingredient={{ id: ingredientId, name: ingredientNameOf(item), kind: kindOf(item) }}
        start={open.start}
        rememberedCode={rememberedCode[key]}
        onRememberCode={(code) =>
          setRememberedCode((prev) => (code ? { ...prev, [key]: code } : without(prev, key)))
        }
        onResolved={(resolution) => resolve(key, resolution)}
        onStep={(trigger) => setReturnFocus({ key, target: trigger })}
        onCancel={(trigger) => closePanel(open, trigger)}
      />
    );
  }

  /** Il pannello aperto sotto questa confezione, se è suo. «Abbina» sta sotto la voce,
   * cioè sotto la sua prima confezione. */
  function panelFor(item: ShoppingItem, packageKey: string): ReactNode {
    if (!panel || panel.itemId !== item.id) return null;
    if (panel.kind === "match") return packageKey === item.id ? renderMatch(item, panel) : null;
    return panel.packageKey === packageKey ? renderResolver(item, panel) : null;
  }

  /** Dove rimettere il fuoco in questa confezione, quando rinasce. Una richiesta
   * esplicita vince sempre, anche se è per un'altra confezione: gli effetti delle righe
   * girano in ordine di albero, e una voce abbinata che viene prima prenderebbe il fuoco
   * dal `body` lasciando senza la riga che l'aveva chiesto. La richiesta dopo
   * l'abbinamento vale solo per la prima confezione della voce riletta col suo
   * ingrediente: prima, la riga è ancora quella di «Senza reparto» che sta per sparire. */
  function returnFocusFor(packageKey: string, item: ShoppingItem): FocusTarget | null {
    if (returnFocus) return returnFocus.key === packageKey ? returnFocus.target : null;
    if (packageKey === item.id && refocusAfterMatch === item.id && item.ingredient_id) {
      return resolved[item.id] ? "change" : "scanner";
    }
    return null;
  }

  function renderRow(item: ShoppingItem) {
    return (
      <StockingRow
        key={item.id}
        item={item}
        resolution={resolved[item.id]}
        ingredientId={ingredientOf(item)}
        expiry={expiry[item.id]}
        onExpiry={(value) => writeExpiry(item.id, value)}
        matchNotSaved={item.id in matchNotSaved}
        retryingMatch={persistMatch.isPending}
        onRetryMatch={() => persistMatch.mutate({ item, ingredient: matchNotSaved[item.id] })}
        focused={panel?.itemId === item.id}
        returnFocusTo={returnFocusFor(item.id, item)}
        onFocusReturned={clearReturnFocus}
        onOpen={(trigger) => openPanelFor(item, item.id, trigger)}
        onLoose={() => resolve(item.id, { kind: "loose" })}
        onChange={() => changeResolution(item.id)}
      >
        {panelFor(item, item.id)}
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
          // il pannello. Le scelte fatte sulle altre sono indicizzate per confezione, e restano
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
                        riuscire: la lista va riletta. Le scelte sono indicizzate per
                        confezione, quindi sopravvivono alla rilettura — e quelle della
                        voce sparita restano fuori dal corpo da sé */}
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
                {/* `busy` in volo, `unavailableReason` a zero voci (Consegna 6a): tutti e
                    due tengono il fuoco, e il perché — un pulsante spento e muto non si
                    spiega da sé, dal giro — lo scrive Button sotto di sé. Il numero è
                    quello delle confezioni che partono davvero */}
                <Button
                  variant="primary"
                  shape="block"
                  icon={IconPackageImport}
                  busy={stock.isPending}
                  unavailableReason={
                    entries.length === 0
                      ? "Scegli come entra almeno una voce: codice, catalogo o sfuso."
                      : undefined
                  }
                  onClick={submitStock}
                >
                  {entries.length > 0 ? `Metti in dispensa ${entries.length}` : "Metti in dispensa"}
                </Button>
              </div>
            </>
          )
        )}
      </div>
    </Screen>
  );
}
```

- [ ] **Step 3: La rete tiene**

Run: `npx vitest run src/features/stocking && npm run typecheck && npm run lint`
Expected: verde, `StockingScreen.test.tsx` con lo stesso numero di test dello Step 1, nessun file di test toccato. Se una prova fallisce, la differenza è nella regia e va cercata confrontando con `git show master:frontend/src/features/stocking/StockingScreen.tsx` (le funzioni `show`, `proceedWithNewCode`, `openProductForm`, `resolveFrom`, `closePanel`, `renderPanel` di prima): il test non si cambia.

- [ ] **Step 4: Le guardie in un posto solo**

Run (dalla radice del worktree): `grep -rli "unlinkedcode" frontend/src | grep -v test | sort; grep -rln "valid_checksum" frontend/src/features/stocking frontend/src/features/pantry | grep -v test`
Expected: `frontend/src/features/stocking/ProductResolver.tsx` (che passa `onUnlinkedCode` allo scanner) e `frontend/src/features/stocking/ScannerPanel.tsx` (la prop di S8), e nessun altro: `StockingScreen.tsx` non c'è più; poi solo `ScannerPanel.tsx`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/stocking/StockingScreen.tsx
git commit -m "refactor(stocking): StockingScreen usa ProductResolver, coi pannelli indicizzati per confezione (S3)"
```

---

### Task 7: La Dispensa, i pezzi — «Scansiona» nella barra, la scheda di conferma

**Files:**
- Modify: `frontend/src/components/ui/ActionBar.tsx`, `frontend/src/components/ui/ActionBar.test.tsx`
- Create: `frontend/src/features/pantry/entryView.ts`, `frontend/src/features/pantry/entryView.test.ts`
- Create: `frontend/src/features/pantry/EntryCard.tsx`, `frontend/src/features/pantry/EntryCard.test.tsx`

**Interfaces:**
- Consumes: `ResolverIngredient` (Task 5), `ExpiryField` (Task 2), `capitalizeFirst`.
- Produces:
  - `ActionBar` con `secondaryAction?: { icon: IconComponent; label: string; onClick: () => void }`: un quadrato di sola icona fra il campo e il +, che non manda il modulo.
  - `entryView.ts`: `type EntryIngredient = ResolverIngredient`; `type EntryChoice = { ingredient: EntryIngredient; product: Product | null; barcode?: string }`; `entryTitle(choice): string` (il nome del prodotto, o l'ingrediente con la maiuscola); `entryLabel(choice): string` (per l'avviso: «Fage Total 0%», o l'ingrediente con la maiuscola).
  - `EntryCard({ choice, expiry, onExpiry, busy, failed, justEntered, onCode?, onCatalog?, onChange, onConfirm, onCancel })`: la scheda. Nomi: «Cambia: {titolo}», «Codice a barre per {titolo}», «Cerca a catalogo per {titolo}» (gruppo «Con la marca: {titolo}»), «Metti in dispensa», «Annulla», e quelli di `ExpiryField` col titolo.

- [ ] **Step 1: I test che falliscono**

1. In fondo al `describe("ActionBar", …)` di `ActionBar.test.tsx` (e `import { IconBarcode } from "./icons";` in testa):
   ```tsx
     it("il pulsante in più sta accanto al +, col suo nome, e non manda il modulo (S3)", () => {
       const onAdd = vi.fn();
       const onScan = vi.fn();
       render(
         <ActionBar
           inputLabel="Cerca o aggiungi in dispensa"
           placeholder="Cerca o aggiungi"
           addLabel="Aggiungi in dispensa"
           value="latte"
           onChange={() => {}}
           onAdd={onAdd}
           secondaryAction={{ icon: IconBarcode, label: "Scansiona", onClick: onScan }}
         />
       );
       fireEvent.click(screen.getByRole("button", { name: "Scansiona" }));
       expect(onScan).toHaveBeenCalledTimes(1);
       expect(onAdd).not.toHaveBeenCalled();
     });
   ```
2. `frontend/src/features/pantry/entryView.test.ts`:
   ```ts
   import { describe, expect, it } from "vitest";
   import { entryLabel, entryTitle, type EntryChoice } from "./entryView";
   import type { Product } from "../../domain/types";

   const YOGURT = { id: "i1", name: "yogurt greco", kind: "food" } as const;
   const FAGE: Product = {
     id: "p1", ingredient_id: "i1", ingredient_name: "yogurt greco", name: "Total 0%", brand: "Fage",
     barcode: "52010", source: "openfoodfacts", nutrients: null, image_url: null,
   };

   describe("entryTitle ed entryLabel", () => {
     it("un prodotto: il titolo è il suo nome, l'avviso mette la marca davanti, come sulla confezione", () => {
       const choice: EntryChoice = { ingredient: YOGURT, product: FAGE };
       expect(entryTitle(choice)).toBe("Total 0%");
       expect(entryLabel(choice)).toBe("Fage Total 0%");
       expect(entryLabel({ ingredient: YOGURT, product: { ...FAGE, brand: null } })).toBe("Total 0%");
     });

     it("uno sfuso: l'ingrediente con la maiuscola, solo a video", () => {
       const choice: EntryChoice = { ingredient: YOGURT, product: null };
       expect(entryTitle(choice)).toBe("Yogurt greco");
       expect(entryLabel(choice)).toBe("Yogurt greco");
     });
   });
   ```
3. `frontend/src/features/pantry/EntryCard.test.tsx`:
   ```tsx
   import { type ComponentProps } from "react";
   import { describe, expect, it, vi } from "vitest";
   import { render, screen, within } from "@testing-library/react";
   import userEvent from "@testing-library/user-event";
   import { EntryCard } from "./EntryCard";
   import type { EntryChoice } from "./entryView";
   import type { Product } from "../../domain/types";

   const YOGURT = { id: "i1", name: "yogurt greco", kind: "food" } as const;
   const FAGE: Product = {
     id: "p1", ingredient_id: "i1", ingredient_name: "yogurt greco", name: "Total 0%", brand: "Fage",
     barcode: "52010", source: "openfoodfacts", nutrients: null, image_url: null,
   };

   type Props = ComponentProps<typeof EntryCard>;

   function renderCard(over: Partial<Props> = {}) {
     const props: Props = {
       choice: { ingredient: YOGURT, product: FAGE }, expiry: undefined, onExpiry: vi.fn(),
       busy: false, failed: false, justEntered: false, onChange: vi.fn(), onConfirm: vi.fn(),
       onCancel: vi.fn(), ...over,
     };
     const view = render(<EntryCard {...props} />);
     return { ...props, ...view };
   }

   const CASES: [string, EntryChoice, string, string][] = [
     ["un prodotto", { ingredient: YOGURT, product: FAGE }, "Total 0%", "Fage · yogurt greco"],
     ["uno sfuso", { ingredient: YOGURT, product: null }, "Yogurt greco", "Sfuso, senza marca · yogurt greco"],
   ];

   describe("EntryCard", () => {
     it.each(CASES)("dice cosa entra: %s", (_caso, choice, title, detail) => {
       renderCard({ choice });
       expect(screen.getByText(title)).toBeDefined();
       expect(screen.getByText(detail)).toBeDefined();
     });

     it("«Metti in dispensa» ha il fuoco appena la scheda compare, e i tre pulsanti fanno la loro", async () => {
       const { onConfirm, onChange, onCancel } = renderCard();
       const metti = screen.getByRole("button", { name: "Metti in dispensa" });
       expect(document.activeElement).toBe(metti);
       await userEvent.click(metti);
       expect(onConfirm).toHaveBeenCalledTimes(1);
       await userEvent.click(screen.getByRole("button", { name: "Cambia: Total 0%" }));
       expect(onChange).toHaveBeenCalledTimes(1);
       await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
       expect(onCancel).toHaveBeenCalledTimes(1);
     });

     it("le strade del codice e del catalogo ci sono solo se la scheda le offre", async () => {
       const sfuso: EntryChoice = { ingredient: YOGURT, product: null };
       const { unmount } = renderCard({ choice: sfuso });
       expect(screen.queryByRole("toolbar")).toBeNull();
       unmount();

       const onCode = vi.fn();
       const onCatalog = vi.fn();
       renderCard({ choice: sfuso, onCode, onCatalog });
       expect(screen.getByText("Con la marca:")).toBeDefined();
       const toolbar = screen.getByRole("toolbar", { name: "Con la marca: Yogurt greco" });
       await userEvent.click(within(toolbar).getByRole("button", { name: "Codice a barre per Yogurt greco" }));
       await userEvent.click(within(toolbar).getByRole("button", { name: "Cerca a catalogo per Yogurt greco" }));
       expect(onCode).toHaveBeenCalledTimes(1);
       expect(onCatalog).toHaveBeenCalledTimes(1);
     });

     it("la nota della serie, l'errore, e «Metti in dispensa» in volo", () => {
       renderCard({ justEntered: true, failed: true, busy: true });
       expect(
         screen.getByText("L'hai appena messo in dispensa: se è un'altra confezione, mettila pure.")
       ).toBeDefined();
       expect(screen.getByRole("alert")).toHaveTextContent(
         "Non sono riuscito ad aggiungere la voce in dispensa. Riprova."
       );
       expect(screen.getByRole("button", { name: "Metti in dispensa" })).toHaveAttribute(
         "aria-disabled",
         "true"
       );
     });
   });
   ```

- [ ] **Step 2: Falliscono**

Run: `npx vitest run src/components/ui/ActionBar.test.tsx src/features/pantry/entryView.test.ts src/features/pantry/EntryCard.test.tsx`
Expected: FAIL — «Scansiona» non c'è; `./entryView` e `./EntryCard` non si risolvono.

- [ ] **Step 3: `ActionBar`**

1. Nella firma, dopo `leadingIcon: Leading,` aggiungi `secondaryAction,`; nel tipo, dopo `leadingIcon?: IconComponent;`:
   ```ts
     /** Un secondo pulsante accanto al +, di sola icona e della stessa misura: «Scansiona»
      * in Dispensa (S3). Non manda il modulo: il testo scritto non c'entra. */
     secondaryAction?: { icon: IconComponent; label: string; onClick: () => void };
   ```
2. Subito prima di `<Button type="submit" variant="primary" shape="square" icon={IconPlus} label={addLabel} />` aggiungi:
   ```tsx
         {secondaryAction && (
           <Button
             type="button"
             variant="secondary"
             shape="square"
             icon={secondaryAction.icon}
             label={secondaryAction.label}
             onClick={secondaryAction.onClick}
           />
         )}
   ```

- [ ] **Step 4: `entryView.ts`**

```ts
import type { ResolverIngredient } from "../stocking/ProductResolver";
import type { Product } from "../../domain/types";
import { capitalizeFirst } from "../../lib/text";

/** L'ingrediente di una confezione che entra dalla Dispensa: quello scelto o creato col
 * +, o quello del prodotto letto dal codice (S3). */
export type EntryIngredient = ResolverIngredient;

/** Cosa sta per entrare: un ingrediente, e un prodotto o niente (sfuso). `barcode` è il
 * codice letto prima di scegliere il prodotto a catalogo (S8): se darlo al prodotto lo
 * decide il backend. */
export type EntryChoice = { ingredient: EntryIngredient; product: Product | null; barcode?: string };

/** Il titolo della scheda, e il nome nei nomi dei suoi pulsanti: il prodotto col suo
 * nome, o l'ingrediente sfuso con la maiuscola (solo a video, spec T3 §4.7). */
export function entryTitle(choice: EntryChoice): string {
  return choice.product ? choice.product.name : capitalizeFirst(choice.ingredient.name);
}

/** Quel che dice l'avviso «In dispensa: …»: la marca davanti al nome, come si legge
 * sulla confezione («Fage Total 0%»). */
export function entryLabel(choice: EntryChoice): string {
  const { product } = choice;
  if (!product) return capitalizeFirst(choice.ingredient.name);
  return product.brand ? `${product.brand} ${product.name}` : product.name;
}
```

- [ ] **Step 5: `EntryCard.tsx`**

```tsx
import { useEffect, useRef } from "react";
import { entryTitle, type EntryChoice } from "./entryView";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { IconToolbar } from "../../components/ui/IconToolbar";
import {
  IconBarcode,
  IconListSearch,
  IconPackageImport,
  IconReplace,
} from "../../components/ui/icons";
import { ExpiryField } from "../stocking/ExpiryField";

/** La scheda di conferma dell'ingresso diretto (S3 §4.4, decisa da Mattia il
 * 2026-10-07): un tocco in più prima di scrivere, perché un codice letto male o un
 * prodotto agganciato all'ingrediente sbagliato non finiscano in dispensa in silenzio
 * (S13), e perché è il solo posto dove la scadenza si scrive con la confezione in mano
 * (D5). Dice cosa entra; «Metti in dispensa» è il primario e prende il fuoco: dopo la
 * lettura del codice, è il secondo e ultimo tocco. */
export function EntryCard({
  choice,
  expiry,
  onExpiry,
  busy,
  failed,
  justEntered,
  onCode,
  onCatalog,
  onChange,
  onConfirm,
  onCancel,
}: {
  choice: EntryChoice;
  expiry: string | undefined;
  onExpiry: (value: string | undefined) => void;
  /** La scrittura è in volo: il pulsante si spegne ma tiene il fuoco. */
  busy: boolean;
  failed: boolean;
  /** Lo stesso prodotto è appena entrato, in questa serie: lo si dice, invece di
   * scriverlo due volte in silenzio (S3 §4.5). Due confezioni uguali esistono: si può
   * mettere lo stesso. */
  justEntered: boolean;
  /** Dal +, a scheda sfusa: le altre due strade della sistemazione, con la marca. */
  onCode?: () => void;
  onCatalog?: () => void;
  onChange: () => void;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const confirmRef = useRef<HTMLButtonElement>(null);
  // il fuoco su «Metti in dispensa» appena la scheda compare: chi l'ha aperta ha appena
  // letto un codice o scelto un ingrediente, e il pulsante che aveva il fuoco è sparito
  useEffect(() => {
    confirmRef.current?.focus();
  }, []);

  const title = entryTitle(choice);
  const { product } = choice;
  const detail = product
    ? [product.brand, choice.ingredient.name].filter(Boolean).join(" · ")
    : `Sfuso, senza marca · ${choice.ingredient.name}`;

  return (
    <div className="flex flex-col gap-2 rounded-card border border-line p-3">
      <div className="flex items-start gap-2">
        {/* `min-w-0` e `break-words`: il nome di un prodotto può essere lungo, e a 375px
            non deve spingere «Cambia» fuori dallo schermo */}
        <div className="min-w-0 flex-1 break-words">
          <p className="font-medium">{title}</p>
          <p className="text-xs text-ink-soft">{detail}</p>
        </div>
        <Button variant="ghost" icon={IconReplace} label={`Cambia: ${title}`} onClick={onChange} />
      </div>

      {onCode && onCatalog && (
        <div className="flex items-center gap-2">
          <p className="text-xs text-ink-soft">Con la marca:</p>
          <IconToolbar label={`Con la marca: ${title}`}>
            <Button
              variant="ghost"
              icon={IconBarcode}
              label={`Codice a barre per ${title}`}
              onClick={onCode}
            />
            <Button
              variant="ghost"
              icon={IconListSearch}
              label={`Cerca a catalogo per ${title}`}
              onClick={onCatalog}
            />
          </IconToolbar>
        </div>
      )}

      {justEntered && (
        <p className="text-sm text-ink">
          L'hai appena messo in dispensa: se è un'altra confezione, mettila pure.
        </p>
      )}

      <ExpiryField name={title} value={expiry} onChange={onExpiry} />

      {/* accanto al pulsante che ha fallito, e niente si perde: la scelta e la data
          restano, e «Metti in dispensa» si ritocca */}
      {failed && <Alert>Non sono riuscito ad aggiungere la voce in dispensa. Riprova.</Alert>}

      <div className="flex flex-wrap items-center gap-2">
        <Button
          ref={confirmRef}
          variant="primary"
          icon={IconPackageImport}
          busy={busy}
          onClick={onConfirm}
        >
          Metti in dispensa
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Annulla
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Passano**

Run: `npx vitest run src/components/ui src/features/pantry && npm run typecheck && npm run lint`
Expected: verde; **+8 test** (1 in `ActionBar.test.tsx`, 2 in `entryView.test.ts`, 5 in `EntryCard.test.tsx`).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ui/ActionBar.tsx frontend/src/components/ui/ActionBar.test.tsx frontend/src/features/pantry
git commit -m "feat(dispensa): «Scansiona» accanto al +, e la scheda di conferma dell'ingresso diretto (S3)"
```

---

### Task 8: La Dispensa, le due porte — `DirectEntry` e `PantryScreen`

**Files:**
- Modify: `frontend/src/features/pantry/api.ts` (`addPantryItem`)
- Create: `frontend/src/features/pantry/DirectEntry.tsx`, `frontend/src/features/pantry/DirectEntry.test.tsx`
- Modify: `frontend/src/features/pantry/PantryScreen.tsx`
- Modify: `frontend/src/features/pantry/PantryScreen.test.tsx` (quattro prove dell'aggiunta migrate, due nuove)

**Interfaces:**
- Consumes: `ProductResolver` (Task 5), `IngredientChooser` (Task 3), `EntryCard`, `entryTitle`, `entryLabel`, `EntryChoice` (Task 7), `ActionBar.secondaryAction` (Task 7).
- Produces:
  - `addPantryItem(entry: { ingredientId: string; productId: string | null; expiresOn: string | null; barcode: string | null }): Promise<PantryItem>` → `POST /pantry` con `{ ingredient_id, product_id, status: "available", expires_on, barcode }`.
  - `type EntryDoor = { kind: "plus"; text: string } | { kind: "scan" }`; `DirectEntry({ door, onEntered: (created: PantryItem, label: string) => void, onClose: () => void })`.
  - In `PantryScreen`: `afterEntry(created, label)` (vedi «Dipendenze»), `openEntry(door)`.

- [ ] **Step 1: I test che falliscono**

`frontend/src/features/pantry/DirectEntry.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DirectEntry, type EntryDoor } from "./DirectEntry";
import type { Ingredient, PantryItem, Product } from "../../domain/types";

const YOGURT: Ingredient = {
  id: "i1", name: "yogurt greco", display_name: "Yogurt greco", category: "latticini", kind: "food",
};
const LENTICCHIE: Ingredient = {
  id: "i3", name: "lenticchie", display_name: "Lenticchie", category: "legumi", kind: "food",
};
const CECI_NERI: Ingredient = {
  id: "i9", name: "ceci neri", display_name: "ceci neri", category: "altro", kind: "food",
};
const FAGE: Product = {
  id: "p1", ingredient_id: "i1", ingredient_name: "yogurt greco", name: "Total 0%", brand: "Fage",
  barcode: "52010", source: "openfoodfacts", nutrients: null, image_url: null,
};
const FAGE_SENZA_CODICE: Product = { ...FAGE, barcode: null };
const PARMIGIANO: Product = {
  id: "p2", ingredient_id: "i8", ingredient_name: "burro", name: "Parmigiano Reggiano",
  brand: null, barcode: "8009876543217", source: "custom", nutrients: null, image_url: null,
};
const LENTICCHIE_COOP: Product = {
  id: "p7", ingredient_id: "i3", ingredient_name: "lenticchie", name: "Lenticchie rosse",
  brand: "Coop", barcode: "8001234567890", source: "openfoodfacts", nutrients: null, image_url: null,
};
const CODE = "8001234567890";
const CREATED: PantryItem = {
  id: "n1", ingredient_id: "i1", product_id: null, ingredient_name: "yogurt greco",
  ingredient_category: "latticini", product_name: null, product_brand: null, status: "available",
  fill_percent: null, note: null, added_at: "2026-10-08T10:00:00Z", expires_on: null, expiry: null,
};
const UNKNOWN = { found: false, origin: "unknown", product: null, suggestion: null, valid_checksum: true };
const inCatalog = (product: Product) => ({
  found: true, origin: "catalog", product, suggestion: null, valid_checksum: true,
});

/** Un fetch che risponde in base a percorso e metodo; la scrittura in dispensa risponde
 * sempre con la voce creata. */
function stubRoutedFetch(route: (path: string, init?: RequestInit) => [unknown, number?]) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const path = String(url);
    if (path.endsWith("/pantry") && init?.method === "POST") {
      return Promise.resolve(new Response(JSON.stringify(CREATED), { status: 201 }));
    }
    const [body, status] = route(path, init);
    return Promise.resolve(new Response(JSON.stringify(body), { status: status ?? 200 }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function posts(spy: ReturnType<typeof stubRoutedFetch>, suffix: string) {
  return spy.mock.calls
    .filter(([url, init]) => String(url).endsWith(suffix) && (init as RequestInit)?.method === "POST")
    .map(([, init]) => JSON.parse(String((init as RequestInit).body)));
}

function renderEntry(door: EntryDoor) {
  const onEntered = vi.fn();
  const onClose = vi.fn();
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <DirectEntry door={door} onEntered={onEntered} onClose={onClose} />
    </QueryClientProvider>
  );
  return { onEntered, onClose };
}

async function readCode(code: string) {
  await userEvent.type(screen.getByLabelText("Codice a barre"), `${code}{Enter}`);
}

const LOOSE_BODY = (ingredientId: string) => ({
  ingredient_id: ingredientId, product_id: null, status: "available", expires_on: null, barcode: null,
});

describe("DirectEntry, dal +", () => {
  it("scelto l'ingrediente, la scheda dice «sfuso» e «Metti in dispensa» ha già il fuoco", async () => {
    const spy = stubRoutedFetch((path) => [path.includes("/ingredients/search") ? [YOGURT] : []]);
    const { onEntered, onClose } = renderEntry({ kind: "plus", text: "yog" });
    await userEvent.click(await screen.findByRole("option", { name: "Yogurt greco" }));
    const metti = screen.getByRole("button", { name: "Metti in dispensa" });
    expect(document.activeElement).toBe(metti);
    expect(screen.getByText("Sfuso, senza marca · yogurt greco")).toBeDefined();

    await userEvent.click(metti);
    await vi.waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(posts(spy, "/pantry")).toEqual([LOOSE_BODY("i1")]);
    expect(onEntered).toHaveBeenCalledWith(CREATED, "Yogurt greco");
  });

  it("un ingrediente che l'anagrafica non ha si crea lì: non si passa più dalla lista", async () => {
    const spy = stubRoutedFetch((path, init) =>
      path.endsWith("/ingredients") && init?.method === "POST" ? [CECI_NERI, 201] : [[]]
    );
    renderEntry({ kind: "plus", text: "ceci neri" });
    await userEvent.click(await screen.findByRole("button", { name: "Aggiungi «ceci neri»" }));
    await userEvent.click(screen.getByRole("button", { name: "Crea l'ingrediente" }));
    await userEvent.click(await screen.findByRole("button", { name: "Metti in dispensa" }));

    await vi.waitFor(() => expect(posts(spy, "/pantry")).toEqual([LOOSE_BODY("i9")]));
    expect(posts(spy, "/ingredients")).toEqual([
      { name: "ceci neri", display_name: "ceci neri", category: "altro" },
    ]);
    expect(screen.queryByText(/scrivilo in/)).toBeNull();
  });

  it("la scadenza scritta nella scheda parte con la voce", async () => {
    const spy = stubRoutedFetch((path) => [path.includes("/ingredients/search") ? [YOGURT] : []]);
    renderEntry({ kind: "plus", text: "yog" });
    await userEvent.click(await screen.findByRole("option", { name: "Yogurt greco" }));
    await userEvent.click(screen.getByRole("button", { name: "+ scadenza per Yogurt greco" }));
    fireEvent.change(screen.getByLabelText("Scadenza di Yogurt greco"), {
      target: { value: "2026-10-20" },
    });
    await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa" }));
    await vi.waitFor(() => expect(posts(spy, "/pantry")[0]?.expires_on).toBe("2026-10-20"));
  });

  it("«Codice» aggancia un prodotto dell'ingrediente, e la scheda dice prodotto e marca", async () => {
    const spy = stubRoutedFetch((path) => {
      if (path.includes("/ingredients/search")) return [[YOGURT]];
      if (path.includes("/products/barcode/")) return [inCatalog(FAGE)];
      return [[]];
    });
    renderEntry({ kind: "plus", text: "yog" });
    await userEvent.click(await screen.findByRole("option", { name: "Yogurt greco" }));
    await userEvent.click(screen.getByRole("button", { name: "Codice a barre per Yogurt greco" }));
    expect(screen.getByRole("heading", { name: "Codice a barre per «Yogurt greco»" })).toBeDefined();
    await readCode("52010");

    expect(await screen.findByText("Fage · yogurt greco")).toBeDefined();
    expect(screen.getByText("Total 0%")).toBeDefined();
    await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa" }));
    await vi.waitFor(() =>
      expect(posts(spy, "/pantry")).toEqual([
        { ingredient_id: "i1", product_id: "p1", status: "available", expires_on: null, barcode: null },
      ])
    );
  });

  it("il codice di un prodotto di un altro ingrediente non si aggancia, e si dice quale", async () => {
    stubRoutedFetch((path) => {
      if (path.includes("/ingredients/search")) return [[YOGURT]];
      if (path.includes("/products/barcode/")) return [inCatalog(PARMIGIANO)];
      return [[]];
    });
    renderEntry({ kind: "plus", text: "yog" });
    await userEvent.click(await screen.findByRole("option", { name: "Yogurt greco" }));
    await userEvent.click(screen.getByRole("button", { name: "Codice a barre per Yogurt greco" }));
    await readCode("8009876543217");
    expect(await screen.findByText(/è di un altro ingrediente: burro/)).toBeDefined();
    expect(screen.queryByRole("button", { name: "Metti in dispensa" })).toBeNull();
  });

  it("il codice ignoto letto prima segue il prodotto scelto poi a catalogo (S8)", async () => {
    const spy = stubRoutedFetch((path) => {
      if (path.includes("/ingredients/search")) return [[YOGURT]];
      if (path.includes("/products/barcode/")) return [UNKNOWN];
      if (path.includes("/products/search")) return [[FAGE_SENZA_CODICE]];
      return [[]];
    });
    renderEntry({ kind: "plus", text: "yog" });
    await userEvent.click(await screen.findByRole("option", { name: "Yogurt greco" }));
    await userEvent.click(screen.getByRole("button", { name: "Codice a barre per Yogurt greco" }));
    await readCode(CODE);
    await screen.findByRole("heading", { name: /Nuovo prodotto per «Yogurt greco»/ });
    // il modulo si chiude: si torna alla scheda sfusa, e di lì al catalogo
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    await userEvent.click(
      await screen.findByRole("button", { name: "Cerca a catalogo per Yogurt greco" })
    );
    await userEvent.click(await screen.findByRole("option", { name: /Total 0%/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Metti in dispensa" }));
    await vi.waitFor(() =>
      expect(posts(spy, "/pantry")).toEqual([
        { ingredient_id: "i1", product_id: "p1", status: "available", expires_on: null, barcode: CODE },
      ])
    );
  });
});

describe("DirectEntry, «Scansiona»", () => {
  it("un prodotto a catalogo entra con due tocchi, e lo scanner torna per il prossimo", async () => {
    const spy = stubRoutedFetch(() => [inCatalog(FAGE)]);
    const { onEntered, onClose } = renderEntry({ kind: "scan" });
    expect(screen.getByRole("heading", { name: "Codice a barre" })).toBeDefined();
    await readCode("52010");
    const metti = await screen.findByRole("button", { name: "Metti in dispensa" });
    expect(document.activeElement).toBe(metti);
    await userEvent.click(metti);

    await vi.waitFor(() => expect(onEntered).toHaveBeenCalledWith(CREATED, "Fage Total 0%"));
    expect(posts(spy, "/pantry")).toEqual([
      { ingredient_id: "i1", product_id: "p1", status: "available", expires_on: null, barcode: null },
    ]);
    // in serie: lo scanner è di nuovo lì, col campo vuoto, e il pannello non si è chiuso
    expect(await screen.findByRole("heading", { name: "Codice a barre" })).toBeDefined();
    expect(screen.getByLabelText("Codice a barre")).toHaveValue("");
    expect(onClose).not.toHaveBeenCalled();
  });

  it("in serie, lo stesso prodotto riletto lo dice, e non lo scrive da solo", async () => {
    const spy = stubRoutedFetch(() => [inCatalog(FAGE)]);
    renderEntry({ kind: "scan" });
    await readCode("52010");
    await userEvent.click(await screen.findByRole("button", { name: "Metti in dispensa" }));
    await screen.findByRole("heading", { name: "Codice a barre" });
    await readCode("52010");
    expect(
      await screen.findByText("L'hai appena messo in dispensa: se è un'altra confezione, mettila pure.")
    ).toBeDefined();
    expect(posts(spy, "/pantry")).toHaveLength(1);
  });

  it("un codice nuovo: l'ingrediente, poi il modulo già compilato senza la domanda, poi la scheda", async () => {
    const suggestion = { name: "Lenticchie rosse", brand: "Coop", barcode: CODE, nutrients: {}, image_url: null };
    const spy = stubRoutedFetch((path, init) => {
      if (path.includes("/products/barcode/")) {
        return [{ found: true, origin: "openfoodfacts", product: null, suggestion, valid_checksum: true }];
      }
      if (path.includes("/ingredients/search")) return [[LENTICCHIE]];
      if (path.endsWith("/products") && init?.method === "POST") return [LENTICCHIE_COOP, 201];
      return [[]];
    });
    renderEntry({ kind: "scan" });
    await readCode(CODE);

    expect(await screen.findByRole("heading", { name: "Di che ingrediente è?" })).toBeDefined();
    expect(screen.getByText("Su Open Food Facts è «Lenticchie rosse», di Coop.")).toBeDefined();
    await userEvent.type(screen.getByRole("textbox", { name: "Ingrediente" }), "lentic");
    await userEvent.click(await screen.findByRole("option", { name: "Lenticchie" }));

    expect(await screen.findByLabelText("Nome")).toHaveValue("Lenticchie rosse");
    expect(screen.queryByRole("heading", { name: /^È un/ })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Salva prodotto" }));

    expect(await screen.findByText("Coop · lenticchie")).toBeDefined();
    expect(posts(spy, "/products")[0]).toMatchObject({
      ingredient_id: "i3", name: "Lenticchie rosse", barcode: CODE,
    });
    await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa" }));
    await vi.waitFor(() =>
      expect(posts(spy, "/pantry")).toEqual([
        { ingredient_id: "i3", product_id: "p7", status: "available", expires_on: null, barcode: null },
      ])
    );
  });

  it("dal modulo si esce sfusi, con l'ingrediente scelto", async () => {
    const spy = stubRoutedFetch((path) => {
      if (path.includes("/products/barcode/")) return [UNKNOWN];
      if (path.includes("/ingredients/search")) return [[LENTICCHIE]];
      return [[]];
    });
    renderEntry({ kind: "scan" });
    await readCode(CODE);
    await userEvent.type(await screen.findByRole("textbox", { name: "Ingrediente" }), "lentic");
    await userEvent.click(await screen.findByRole("option", { name: "Lenticchie" }));
    await userEvent.click(await screen.findByRole("button", { name: "Sfuso, senza marca" }));
    expect(screen.getByText("Sfuso, senza marca · lenticchie")).toBeDefined();
    await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa" }));
    await vi.waitFor(() => expect(posts(spy, "/pantry")).toEqual([LOOSE_BODY("i3")]));
  });

  it("«Annulla» della scheda torna allo scanner; «Annulla» dello scanner chiude", async () => {
    stubRoutedFetch(() => [inCatalog(FAGE)]);
    const { onClose } = renderEntry({ kind: "scan" });
    await readCode("52010");
    // prima la scheda: finché non c'è, l'unico «Annulla» è quello dello scanner
    await screen.findByRole("button", { name: "Metti in dispensa" });
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(screen.getByRole("heading", { name: "Codice a barre" })).toBeDefined();
    expect(onClose).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(onClose).toHaveBeenCalled();
  });
});
```

In `PantryScreen.test.tsx`:

1. **«un testo che non trova niente offre di aggiungerlo»**: le ultime due righe
   ```tsx
       // l'anagrafica non ha «sale»: il pannello non resta muto, dice dove andare
       expect(await screen.findByText(/Non è in anagrafica/)).toBeDefined();
       expect(screen.getByRole("link", { name: "lista" }).getAttribute("href")).toBe("/lista");
   ```
   diventano:
   ```tsx
       // l'anagrafica non ha «sale»: la Dispensa lo crea lì (S3), e non rimanda più alla lista
       expect(await screen.findByRole("button", { name: "Aggiungi «sale»" })).toBeDefined();
       expect(screen.queryByRole("link", { name: "lista" })).toBeNull();
   ```
2. **«il + apre l'aggiunta con il testo della barra, e scegliere mette in dispensa»**: dopo `fireEvent.click(await screen.findByRole("option", { name: "Mela" }));` aggiungi
   ```tsx
       // la scheda di conferma (S3): un tocco in più, e lì si scrive la scadenza
       fireEvent.click(await screen.findByRole("button", { name: "Metti in dispensa" }));
   ```
   il corpo atteso `{ ingredient_id: "i2", status: "available" }` diventa `{ ingredient_id: "i2", product_id: null, status: "available", expires_on: null, barcode: null }`, e dopo `expect(screen.queryByLabelText("Ingrediente da mettere in dispensa")).toBeNull();` aggiungi `expect(screen.queryByRole("button", { name: "Metti in dispensa" })).toBeNull();`.
3. **«chiudere l'aggiunta dopo un fallimento non lo riporta nella prossima»**: dopo `fireEvent.click(await screen.findByRole("option", { name: "Mela" }));` aggiungi `fireEvent.click(await screen.findByRole("button", { name: "Metti in dispensa" }));`.
4. **«un'aggiunta rifiutata lo dice nella scheda dell'aggiunta, che resta aperta»**: dopo l'`option` aggiungi la stessa riga; l'ultima, `expect(screen.getByLabelText("Ingrediente da mettere in dispensa")).toBeDefined();`, diventa `expect(screen.getByRole("button", { name: "Metti in dispensa" })).toBeDefined();` (la scheda resta, con la scelta).
5. In fondo al `describe("PantryScreen", …)` aggiungi:
   ```tsx
     it("«Scansiona» apre lo scanner sotto la barra, con le righe a video, e la ✕ lo chiude (S3)", async () => {
       stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]));
       renderScreen();
       await screen.findByText("Total 0%");
       fireEvent.click(screen.getByRole("button", { name: "Scansiona" }));
       expect(screen.getByRole("heading", { name: "Codice a barre" })).toBeDefined();
       expect(screen.getByText("Total 0%")).toBeDefined();
       fireEvent.click(screen.getByRole("button", { name: "Chiudi l'aggiunta" }));
       expect(screen.queryByRole("heading", { name: "Codice a barre" })).toBeNull();
     });

     it("«Annulla» nell'avviso toglie la voce appena entrata (S3)", async () => {
       const created = { ...ITEMS[2], id: "p9" };
       const spy = stubRoutedFetch((path, init) => {
         if (path.includes("/shopping-list")) return [[], 200];
         if (path.includes("/ingredients")) return [[MELA], 200];
         if (init?.method === "POST") return [created, 201];
         if (init?.method === "PATCH") return [created, 200];
         return [ITEMS, 200];
       });
       renderScreen();
       await screen.findByText("Total 0%");
       fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "mel" } });
       fireEvent.click(screen.getByRole("button", { name: "Aggiungi in dispensa" }));
       fireEvent.click(await screen.findByRole("option", { name: "Mela" }));
       fireEvent.click(await screen.findByRole("button", { name: "Metti in dispensa" }));
       expect(await screen.findByText("In dispensa: Mela")).toBeDefined();
       fireEvent.click(screen.getByRole("button", { name: "Annulla" }));
       await vi.waitFor(() => {
         const patch = spy.mock.calls.find(([, init]) => init?.method === "PATCH");
         expect(String(patch?.[0])).toContain("/pantry/p9");
         expect(JSON.parse(String(patch?.[1]?.body))).toEqual({ archived: true });
       });
     });
   ```

- [ ] **Step 2: Falliscono**

Run: `npx vitest run src/features/pantry`
Expected: FAIL — `./DirectEntry` non si risolve; in `PantryScreen.test.tsx` le prove migrate e le due nuove falliscono (nessuna scheda, nessun «Scansiona»).

- [ ] **Step 3: `addPantryItem`**

In `frontend/src/features/pantry/api.ts` sostituisci `addPantryItem` e il suo commento con:

```ts
/** L'ingresso diretto in dispensa (S3): una confezione che non passa dalla lista. Entra
 * `available`; prodotto, scadenza e codice letto sono facoltativi, e si mandano sempre
 * (`null` quando non ci sono). Se il codice va al prodotto lo decide il backend
 * (`stock_one`, la stessa funzione della sistemazione): mai a un prodotto che ne ha già
 * uno, mai togliendolo a un altro. */
export function addPantryItem(entry: {
  ingredientId: string;
  productId: string | null;
  expiresOn: string | null;
  barcode: string | null;
}) {
  return apiFetch<PantryItem>("/pantry", {
    method: "POST",
    body: JSON.stringify({
      ingredient_id: entry.ingredientId,
      product_id: entry.productId,
      status: "available",
      expires_on: entry.expiresOn,
      barcode: entry.barcode,
    }),
  });
}
```

- [ ] **Step 4: `DirectEntry.tsx`**

```tsx
import { useRef, useState, type ReactNode } from "react";
import { useMutation } from "@tanstack/react-query";
import { EntryCard } from "./EntryCard";
import { addPantryItem } from "./api";
import { entryLabel, entryTitle, type EntryChoice } from "./entryView";
import { Button } from "../../components/ui/Button";
import { IconX } from "../../components/ui/icons";
import { IngredientChooser } from "../stocking/IngredientChooser";
import { ProductResolver } from "../stocking/ProductResolver";
import type { PantryItem } from "../../domain/types";

/** Da dove si entra: il + col testo della barra (uno sfuso, o quando il codice non c'è),
 * o «Scansiona» (la confezione in mano). */
export type EntryDoor = { kind: "plus"; text: string } | { kind: "scan" };

type Stage =
  // dal +: quale ingrediente
  | { kind: "choose" }
  // il codice o il catalogo, con l'ingrediente della scheda (`base`) o senza (la scansione)
  | { kind: "resolve"; start: "scanner" | "catalog"; base: EntryChoice | null; serial: number }
  // la scheda di conferma
  | { kind: "confirm"; choice: EntryChoice; serial: number };

/**
 * L'ingresso diretto in dispensa (S3, decisioni di Mattia del 2026-10-07): le stesse
 * strade e le stesse guardie di «Sistema la spesa», senza una voce di lista.
 *
 * - **«Scansiona»**: lo scanner senza ingrediente atteso; un prodotto a catalogo va
 *   dritto alla scheda (due tocchi: il codice e «Metti in dispensa»), un codice nuovo
 *   passa da «Di che ingrediente è?» e dal modulo (`ProductResolver`). Dopo «Metti in
 *   dispensa» il pannello non si chiude: torna allo scanner per il codice dopo — il
 *   censimento della dispensa è il secondo caso della richiesta, e riaprirlo a ogni
 *   confezione è il gesto che lo rende lento.
 * - **Il +**: l'ingrediente col testo della barra, che si può creare lì; la scheda
 *   sfusa offre il codice e il catalogo, con l'ingrediente atteso. Dopo «Metti in
 *   dispensa» si chiude, come prima.
 *
 * La scrittura passa da qui; cosa fare dopo (la riga in vista, l'avviso con «Annulla»)
 * lo decide la Dispensa in `onEntered`.
 */
export function DirectEntry({
  door,
  onEntered,
  onClose,
}: {
  door: EntryDoor;
  onEntered: (created: PantryItem, label: string) => void;
  onClose: () => void;
}) {
  const serial = useRef(0);
  const [stage, setStage] = useState<Stage>(() =>
    door.kind === "plus"
      ? { kind: "choose" }
      : { kind: "resolve", start: "scanner", base: null, serial: 0 }
  );
  const [expiry, setExpiry] = useState<string | undefined>(undefined);
  // il codice letto e rimasto senza prodotto (S8): sopravvive al resolver che si chiude,
  // per il catalogo aperto dopo dalla stessa scheda. Quando seguirlo lo decide il resolver
  const [rememberedCode, setRememberedCode] = useState<string | undefined>(undefined);
  // l'ultimo prodotto entrato in questa serie: riletto subito, la scheda lo dice
  const [lastProductId, setLastProductId] = useState<string | null>(null);

  const add = useMutation({
    mutationFn: ({ choice, expiresOn }: { choice: EntryChoice; expiresOn: string | null }) =>
      addPantryItem({
        ingredientId: choice.ingredient.id,
        productId: choice.product?.id ?? null,
        expiresOn,
        // solo un prodotto scelto a catalogo dopo un codice letto lo porta (S8)
        barcode: (choice.product && choice.barcode) || null,
      }),
    // nelle opzioni e non in `mutate`: la voce è in dispensa anche se il pannello si è
    // chiuso nel frattempo, e la Dispensa deve saperlo (la riga, l'avviso con «Annulla»)
    onSuccess: (created, { choice }) => onEntered(created, entryLabel(choice)),
  });

  function next(): number {
    serial.current += 1;
    return serial.current;
  }

  function confirm(choice: EntryChoice) {
    add.reset();
    setStage({ kind: "confirm", choice, serial: next() });
  }

  /** Un giro nuovo della scansione: un'altra confezione, senza niente di quella prima. */
  function scanAgain() {
    add.reset();
    setExpiry(undefined);
    setRememberedCode(undefined);
    setStage({ kind: "resolve", start: "scanner", base: null, serial: next() });
  }

  function chooseAgain() {
    add.reset();
    setExpiry(undefined);
    setRememberedCode(undefined);
    setStage({ kind: "choose" });
  }

  /** «Cambia» torna indietro di un passo: dalla scansione a un codice nuovo; dal + con
   * un prodotto alla stessa voce sfusa; dal + sfuso alla scelta dell'ingrediente. */
  function change(choice: EntryChoice) {
    if (door.kind === "scan") {
      scanAgain();
      return;
    }
    if (choice.product) {
      confirm({ ingredient: choice.ingredient, product: null });
      return;
    }
    chooseAgain();
  }

  function submit(choice: EntryChoice) {
    // la guardia al posto di `disabled`: il pulsante resta dov'è il fuoco
    if (add.isPending) return;
    add.mutate(
      { choice, expiresOn: expiry || null },
      {
        onSuccess: () => {
          if (door.kind === "plus") {
            onClose();
            return;
          }
          setLastProductId(choice.product?.id ?? null);
          scanAgain();
        },
      }
    );
  }

  let body: ReactNode;
  if (stage.kind === "choose") {
    body = (
      <IngredientChooser
        label="Ingrediente da mettere in dispensa"
        failureNote="Puoi comunque aggiungerlo."
        initialTerm={door.kind === "plus" ? door.text : ""}
        onChosen={(ingredient) =>
          confirm({
            ingredient: { id: ingredient.id, name: ingredient.name, kind: ingredient.kind },
            product: null,
          })
        }
      />
    );
  } else if (stage.kind === "resolve") {
    const { base } = stage;
    body = (
      <ProductResolver
        key={stage.serial}
        label={base ? entryTitle(base) : null}
        ingredient={base?.ingredient ?? null}
        start={stage.start}
        rememberedCode={rememberedCode}
        onRememberCode={(code) => setRememberedCode(code ?? undefined)}
        onResolved={(resolution, ingredient) =>
          confirm(
            resolution.kind === "product"
              ? { ingredient, product: resolution.product, barcode: resolution.barcode }
              : { ingredient, product: null }
          )
        }
        // dal +, annullare torna alla scheda; dalla scansione chiude, come la ✕
        onCancel={() => (base ? confirm(base) : onClose())}
      />
    );
  } else {
    const { choice } = stage;
    const loosePlus = door.kind === "plus" && choice.product === null;
    body = (
      <EntryCard
        key={stage.serial}
        choice={choice}
        expiry={expiry}
        onExpiry={setExpiry}
        busy={add.isPending}
        failed={add.isError}
        justEntered={
          door.kind === "scan" && choice.product !== null && choice.product.id === lastProductId
        }
        onCode={
          loosePlus
            ? () => setStage({ kind: "resolve", start: "scanner", base: choice, serial: next() })
            : undefined
        }
        onCatalog={
          loosePlus
            ? () => setStage({ kind: "resolve", start: "catalog", base: choice, serial: next() })
            : undefined
        }
        onChange={() => change(choice)}
        onConfirm={() => submit(choice)}
        onCancel={() => (door.kind === "plus" ? onClose() : scanAgain())}
      />
    );
  }

  return (
    <div className="flex items-start gap-2 rounded-2xl bg-card p-3">
      <div className="min-w-0 flex-1">{body}</div>
      <Button variant="ghost" icon={IconX} label="Chiudi l'aggiunta" onClick={onClose} />
    </div>
  );
}
```

- [ ] **Step 5: `PantryScreen.tsx`**

1. Gli import in testa (fino a `import type { Ingredient, PantryItem, PantryStatus } from "../../domain/types";` compreso) diventano:
   ```tsx
   import { useCallback, useState } from "react";
   import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
   import { Button } from "../../components/ui/Button";
   import { EmptyState } from "../../components/ui/EmptyState";
   import { ErrorState } from "../../components/ui/ErrorState";
   import { Screen } from "../../components/ui/Screen";
   import { Section } from "../../components/ui/Section";
   import { ActionBar } from "../../components/ui/ActionBar";
   import { IconBarcode, IconCalendarEvent, IconPlus, IconSearch, IconX } from "../../components/ui/icons";
   import { useNotice } from "../../components/ui/noticeContext";
   import { DirectEntry, type EntryDoor } from "./DirectEntry";
   import { PantryRow } from "./PantryRow";
   import { expiryCounts, expirySummary, groupForDisplay, hasExpiry, itemLabel, matchesQuery } from "./pantryView";
   import { fetchPantry, patchPantryItem, restockPantryItem } from "./api";
   import { fetchShoppingList } from "../shopping-list/api";
   import { ShoppingEntryCard } from "../shopping-list/ShoppingEntryCard";
   import type { PantryItem, PantryStatus } from "../../domain/types";
   ```
   (`IngredientPicker`, `Alert`, `Link`, `Ingredient` e `addPantryItem` non servono più qui.)
2. Il blocco che va dal commento `// Spec §4 e §8.3: l'ingresso diretto, cioè senza passare dalla lista.` fino alla fine di `const add = useMutation({ … });` compresa (cioè `addFailed`, `query`, `expiringOnly`, `adding`, `revealId`, `clearReveal` e `add`) diventa:
   ```tsx
     const [query, setQuery] = useState("");
     const [expiringOnly, setExpiringOnly] = useState(false);
     // L'ingresso diretto (S3): una confezione che non passa dalla lista — chi torna a
     // casa con una cosa che non aveva scritto, e il censimento della dispensa. Due porte:
     // il + col testo della barra, e «Scansiona». `null` quando è chiuso; `serial` lo fa
     // rinascere quando si riapre con un testo nuovo
     const [entry, setEntry] = useState<{ door: EntryDoor; serial: number } | null>(null);
     // la voce appena aggiunta, da portare in vista quando arriva nell'elenco
     const [revealId, setRevealId] = useState<string | null>(null);
     const clearReveal = useCallback(() => setRevealId(null), []);

     function openEntry(door: EntryDoor) {
       setEntry((prev) => ({ door, serial: (prev?.serial ?? 0) + 1 }));
     }

     // L'annulla di un ingresso: archivia la voce appena creata, come la ✕ di una riga.
     // Vive nell'avviso, che è dell'app: se fallisce, un avviso nuovo lo dice e offre di
     // riprovare — la voce è in dispensa davvero, e perderla qui sarebbe il vicolo cieco
     function undoEntry(created: PantryItem, label: string) {
       patchPantryItem(created.id, { archived: true }).then(
         () => queryClient.invalidateQueries({ queryKey: ["pantry"] }),
         () =>
           notice({
             text: `Non sono riuscito a togliere ${label} dalla dispensa.`,
             action: { label: "Riprova", onClick: () => undoEntry(created, label) },
           })
       );
     }

     /** Una confezione è entrata, da una delle due porte. La riga nuova deve potersi
      * vedere: la barra torna vuota, il riepilogo si spegne, e `revealId` la porta in
      * vista quando arriva nell'elenco. Chi aggiunge un filtro alla Dispensa (S14, S15)
      * lo rimette qui come deve stare perché la riga si veda. */
     function afterEntry(created: PantryItem, label: string) {
       invalidate();
       setQuery("");
       setExpiringOnly(false);
       setRevealId(created.id);
       notice({
         text: `In dispensa: ${label}`,
         action: { label: "Annulla", onClick: () => undoEntry(created, label) },
       });
     }
   ```
   (`notice` e `invalidate` sono già dichiarati più sopra nel componente, e `undoEntry` li usa solo nei gestori.)
3. In `<ActionBar`, sostituisci
   ```tsx
             onAdd={(text) => {
               setAddFailed(false);
               setAdding(text);
             }}
   ```
   con
   ```tsx
             onAdd={(text) => openEntry({ kind: "plus", text })}
             // la seconda porta (S3): la confezione in mano, il codice da leggere
             secondaryAction={{
               icon: IconBarcode,
               label: "Scansiona",
               onClick: () => openEntry({ kind: "scan" }),
             }}
   ```
4. Il blocco `{adding !== null && ( … )}` (dal `<div className="flex flex-col gap-2 rounded-2xl bg-card p-3">` con dentro l'`IngredientPicker`, «Chiudi l'aggiunta», «Entra come disponibile e senza marca.» e l'`Alert`, fino al suo `)}`) diventa:
   ```tsx
           {entry !== null && (
             <DirectEntry
               key={entry.serial}
               door={entry.door}
               onEntered={afterEntry}
               onClose={() => setEntry(null)}
             />
           )}
   ```
5. Nell'`EmptyState` di «Niente in dispensa per «…»», `adding === null && (` diventa `entry === null && (`, e
   ```tsx
                     onClick={() => {
                       setAddFailed(false);
                       setAdding(query.trim());
                     }}
   ```
   diventa `onClick={() => openEntry({ kind: "plus", text: query.trim() })}`.
6. Controlla che nel file non resti niente di `adding`, `setAdding`, `addFailed`, `add.`: `grep -n "adding\|addFailed\|add\.\(mutate\|isPending\)" src/features/pantry/PantryScreen.tsx` → vuoto.

- [ ] **Step 6: Passano**

Run: `npx vitest run src/features/pantry src/features/stocking && npm run typecheck && npm run lint`
Expected: verde; **+13 test** (11 in `DirectEntry.test.tsx`, 2 in `PantryScreen.test.tsx`); le altre prove di `PantryScreen.test.tsx` passano senza modifiche oltre alle quattro migrate.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/pantry
git commit -m "feat(dispensa): l'ingresso diretto — «Scansiona» in serie e il + che crea l'ingrediente, con la scheda di conferma, la scadenza e «Annulla» nell'avviso (S3)"
```

---

### Task 9: «+ un'altra confezione» in «Sistema la spesa»

Da una voce di lista possono uscire più confezioni dello stesso ingrediente — due vaschette con due scadenze, uno yogurt alla fragola e uno alla pesca. Il Task 6 ha già indicizzato i pannelli per confezione; qui nascono le confezioni in più, la loro riga, e il conto per confezione.

**Files:**
- Modify: `frontend/src/features/stocking/stockingView.ts`, `frontend/src/features/stocking/stockingView.test.ts`
- Create: `frontend/src/features/stocking/PackageRow.tsx`, `frontend/src/features/stocking/PackageRow.test.tsx`
- Modify: `frontend/src/features/stocking/StockingRow.tsx` (prop `after`), `frontend/src/features/stocking/StockingRow.test.tsx` (una prova in fondo)
- Modify: `frontend/src/features/stocking/StockingScreen.tsx`
- Modify: `frontend/src/features/stocking/StockingScreen.test.tsx` (un `describe` nuovo in fondo; niente di ciò che c'è si tocca)

**Interfaces:**
- Consumes: `ExpiryField`, `ResolutionNote`, `useReturnFocus` (Task 2); da `StockingScreen` del Task 6 `openPanelFor`, `resolve`, `changeResolution`, `writeExpiry`, `returnFocusFor`, `panelFor`, gli stati `resolved`, `expiry`, `rememberedCode`, `returnFocus`.
- Produces:
  - `stockEntries(items, resolved, ingredientOf, expiry, packagesOf = (item) => [item.id])`: una riga per confezione scelta, nell'ordine della lista e delle confezioni.
  - `itemsLeft(items: ShoppingItem[], entries: StockEntry[]): number`: le voci senza nessuna confezione mandata.
  - `stockNotice(sent: number, left: number): string` (prima era `(sent, checked)`).
  - `PackageRow({ name, index, resolution, expiry, onExpiry, returnFocusTo, onFocusReturned, onOpen, onLoose, onChange, onRemove, children })`.
  - `StockingRow` con `after?: ReactNode`, in fondo alla voce, dopo la sua scadenza.
  - Le chiavi delle confezioni in più: `${item.id}+${n}`, con `n` che non si riusa.

- [ ] **Step 1: I test che falliscono**

1. In `stockingView.test.ts`: l'import diventa `import { itemsLeft, stockEntries, stockNotice, type Resolution } from "./stockingView";`. Dentro `describe("stockEntries", …)`, in fondo, aggiungi:
   ```ts
     it("una voce con più confezioni manda una riga per confezione, ognuna con la sua scadenza e il suo codice (S3)", () => {
       const packagesOf = (row: ShoppingItem) => (row.id === "s1" ? ["s1", "s1+1"] : [row.id]);
       const resolved: Record<string, Resolution> = {
         s1: { kind: "loose" },
         "s1+1": { kind: "product", product: FAGE, barcode: "8001234567890" },
       };
       expect(
         stockEntries([item("s1", "i1")], resolved, ownIngredient, { "s1+1": "2026-10-20" }, packagesOf)
       ).toEqual([
         { shopping_item_id: "s1", ingredient_id: "i1", product_id: null, expires_on: null, barcode: null },
         { shopping_item_id: "s1", ingredient_id: "i1", product_id: "p1", expires_on: "2026-10-20",
           barcode: "8001234567890" },
       ]);
     });

     it("una confezione senza scelta non parte, le altre della stessa voce sì", () => {
       const packagesOf = () => ["s1", "s1+1", "s1+2"];
       const resolved: Record<string, Resolution> = { "s1+1": { kind: "loose" } };
       expect(ids(stockEntries([item("s1", "i1")], resolved, ownIngredient, {}, packagesOf))).toEqual(["s1"]);
     });
   ```
   Dopo quel `describe` aggiungi:
   ```ts
   describe("itemsLeft", () => {
     it("conta le voci senza nessuna confezione mandata, non le confezioni", () => {
       const items = [item("s1", "i1"), item("s2", "i2"), item("s3", "i3")];
       const resolved: Record<string, Resolution> = { s1: { kind: "loose" }, "s1+1": { kind: "loose" } };
       const sent = stockEntries(items, resolved, ownIngredient, {}, (row) =>
         row.id === "s1" ? ["s1", "s1+1"] : [row.id]
       );
       expect(sent).toHaveLength(2);
       expect(itemsLeft(items, sent)).toBe(2);
     });
   });
   ```
   E `describe("stockNotice", …)` diventa (la migrazione: il secondo numero è ora quante **voci** restano, non quante erano nel carrello — con più confezioni per voce la differenza non lo dice più):
   ```ts
   describe("stockNotice", () => {
     it.each([
       [4, 3, "4 in dispensa · 3 restano in lista"],
       [4, 0, "4 in dispensa"],
       [1, 0, "1 in dispensa"],
       [1, 1, "1 in dispensa · 1 resta in lista"],
       [2, 3, "2 in dispensa · 3 restano in lista"],
       // più confezioni che voci (S3): tre vasetti da due voci, e una voce rimasta
       [3, 1, "3 in dispensa · 1 resta in lista"],
     ] as const)("%i mandate, %i voci rimaste in lista → «%s»", (sent, left, text) => {
       expect(stockNotice(sent, left)).toBe(text);
     });
   });
   ```
2. `frontend/src/features/stocking/PackageRow.test.tsx`:
   ```tsx
   import { describe, expect, it, vi } from "vitest";
   import { render, screen, within } from "@testing-library/react";
   import userEvent from "@testing-library/user-event";
   import { type ComponentProps } from "react";
   import { PackageRow } from "./PackageRow";

   type Props = ComponentProps<typeof PackageRow>;

   function renderPackage(over: Partial<Props> = {}) {
     const props: Props = {
       name: "mele", index: 2, resolution: undefined, expiry: undefined, onExpiry: vi.fn(),
       returnFocusTo: null, onFocusReturned: vi.fn(), onOpen: vi.fn(), onLoose: vi.fn(),
       onChange: vi.fn(), onRemove: vi.fn(), ...over,
     };
     render(<PackageRow {...props} />);
     return props;
   }

   describe("PackageRow", () => {
     it("da scegliere: le tre strade col numero della confezione nel nome, e ognuna fa la sua", async () => {
       const { onOpen, onLoose } = renderPackage();
       expect(screen.getByText("Confezione 2")).toBeDefined();
       const toolbar = screen.getByRole("toolbar", { name: "Come entra in dispensa: mele, confezione 2" });
       await userEvent.click(within(toolbar).getByRole("button", { name: "Codice a barre per mele, confezione 2" }));
       await userEvent.click(within(toolbar).getByRole("button", { name: "Cerca a catalogo per mele, confezione 2" }));
       await userEvent.click(within(toolbar).getByRole("button", { name: "Sfuso, senza marca: mele, confezione 2" }));
       expect(onOpen.mock.calls).toEqual([["scanner"], ["catalog"]]);
       expect(onLoose).toHaveBeenCalledTimes(1);
       expect(screen.getByRole("button", { name: "+ scadenza per mele, confezione 2" })).toBeDefined();
     });

     it("scelta: dice a cosa, «Cambia» la disfa, e la ✕ toglie la confezione", async () => {
       const { onChange, onRemove } = renderPackage({ resolution: { kind: "loose" } });
       expect(screen.getByText("Sfuso")).toBeDefined();
       expect(screen.queryByRole("toolbar")).toBeNull();
       await userEvent.click(screen.getByRole("button", { name: "Cambia la scelta per mele, confezione 2" }));
       await userEvent.click(screen.getByRole("button", { name: "Togli la confezione 2 di mele" }));
       expect(onChange).toHaveBeenCalledTimes(1);
       expect(onRemove).toHaveBeenCalledTimes(1);
     });

     it("il fuoco torna alla sua icona, non a quella della voce che la contiene", () => {
       const onFocusReturned = vi.fn();
       render(
         <div>
           <span data-trigger="scanner" className="contents">
             <button type="button">della voce</button>
           </span>
           <PackageRow
             name="mele" index={2} resolution={undefined} expiry={undefined} onExpiry={vi.fn()}
             returnFocusTo="scanner" onFocusReturned={onFocusReturned} onOpen={vi.fn()}
             onLoose={vi.fn()} onChange={vi.fn()} onRemove={vi.fn()}
           />
         </div>
       );
       expect(document.activeElement).toBe(
         screen.getByRole("button", { name: "Codice a barre per mele, confezione 2" })
       );
       expect(onFocusReturned).toHaveBeenCalled();
     });
   });
   ```
3. In fondo al `describe("StockingRow", …)` di `StockingRow.test.tsx`:
   ```tsx
     it("quel che lo schermo mette dopo sta dentro la voce, sotto la sua scadenza (S3)", () => {
       renderRow({ after: <p>confezione in più</p> });
       const dopo = screen.getByText("confezione in più");
       expect(dopo.closest("li")).toBe(screen.getByText("mele").closest("li"));
       const scadenza = screen.getByRole("button", { name: "+ scadenza per mele" });
       expect(scadenza.compareDocumentPosition(dopo) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
     });
   ```
4. In fondo al file `StockingScreen.test.tsx`, **dentro** il `describe("StockingScreen", …)` (prima della sua `});` finale), aggiungi:
   ```tsx
     describe("più confezioni per una voce (S3 §10.2)", () => {
       it("non c'è finché la voce non è risolta", async () => {
         stubRoutedFetch(() => [CHECKED]);
         renderScreen();
         await screen.findByText("mele");
         expect(screen.queryByRole("button", { name: /un'altra confezione/ })).toBeNull();
       });

       it("su una voce risolta aggiunge una confezione con le sue tre strade, e il pulsante conta le confezioni", async () => {
         const spy = stubRoutedFetch((path) =>
           path.endsWith("/shopping-list/stock") ? [{ created: 2 }, 201] : [CHECKED]
         );
         renderScreen();
         await userEvent.click(await screen.findByRole("button", { name: /Sfuso.*mele/i }));
         await userEvent.click(screen.getByRole("button", { name: "+ un'altra confezione di mele" }));
         const toolbar = screen.getByRole("toolbar", { name: "Come entra in dispensa: mele, confezione 2" });
         // il fuoco va alla prima strada della confezione nuova
         expect(document.activeElement).toBe(
           within(toolbar).getByRole("button", { name: "Codice a barre per mele, confezione 2" })
         );
         await userEvent.click(
           within(toolbar).getByRole("button", { name: "Sfuso, senza marca: mele, confezione 2" })
         );
         await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa 2" }));
         await vi.waitFor(() =>
           expect(postBody(spy, "/shopping-list/stock").entries).toEqual([
             { shopping_item_id: "s2", ingredient_id: "i2", product_id: null, expires_on: null, barcode: null },
             { shopping_item_id: "s2", ingredient_id: "i2", product_id: null, expires_on: null, barcode: null },
           ])
         );
       });

       it("ogni confezione ha la sua scelta e la sua scadenza", async () => {
         const spy = stubRoutedFetch((path) => {
           if (path.includes("/products/search")) return [[FAGE]];
           if (path.endsWith("/shopping-list/stock")) return [{ created: 2 }, 201];
           return [CHECKED];
         });
         renderScreen();
         await userEvent.click(await screen.findByRole("button", { name: /Sfuso.*yogurt greco/i }));
         await userEvent.click(screen.getByRole("button", { name: "+ un'altra confezione di yogurt greco" }));
         await userEvent.click(
           screen.getByRole("button", { name: "Cerca a catalogo per yogurt greco, confezione 2" })
         );
         // il catalogo della confezione è quello della voce: lo stesso ingrediente
         expect(screen.getByRole("heading", { name: "Cerca a catalogo per «yogurt greco»" })).toBeDefined();
         await userEvent.click(await screen.findByRole("option", { name: /Total 0%/ }));
         await userEvent.click(
           screen.getByRole("button", { name: "+ scadenza per yogurt greco, confezione 2" })
         );
         fireEvent.change(screen.getByLabelText("Scadenza di yogurt greco, confezione 2"), {
           target: { value: "2026-10-20" },
         });
         await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa 2" }));
         await vi.waitFor(() =>
           expect(postBody(spy, "/shopping-list/stock").entries).toEqual([
             { shopping_item_id: "s1", ingredient_id: "i1", product_id: null, expires_on: null, barcode: null },
             { shopping_item_id: "s1", ingredient_id: "i1", product_id: "p1", expires_on: "2026-10-20",
               barcode: null },
           ])
         );
       });

       it("la ✕ toglie la confezione e la sua scelta, e il fuoco torna alla voce", async () => {
         stubRoutedFetch(() => [CHECKED]);
         renderScreen();
         await userEvent.click(await screen.findByRole("button", { name: /Sfuso.*mele/i }));
         await userEvent.click(screen.getByRole("button", { name: "+ un'altra confezione di mele" }));
         await userEvent.click(screen.getByRole("button", { name: "Sfuso, senza marca: mele, confezione 2" }));
         expect(screen.getByRole("button", { name: "Metti in dispensa 2" })).toBeDefined();

         await userEvent.click(screen.getByRole("button", { name: "Togli la confezione 2 di mele" }));
         expect(screen.queryByText("Confezione 2")).toBeNull();
         expect(screen.getByRole("button", { name: "Metti in dispensa 1" })).toBeDefined();
         expect(document.activeElement).toBe(
           screen.getByRole("button", { name: "Cambia la scelta per mele" })
         );
       });

       it("l'avviso in Dispensa conta le confezioni entrate e le voci rimaste", async () => {
         stubRoutedFetch((path) =>
           path.endsWith("/shopping-list/stock") ? [{ created: 2 }, 201] : [[...CHECKED, ...UNMATCHED]]
         );
         renderScreen();
         await userEvent.click(await screen.findByRole("button", { name: /Sfuso.*mele/i }));
         await userEvent.click(screen.getByRole("button", { name: "+ un'altra confezione di mele" }));
         await userEvent.click(screen.getByRole("button", { name: "Sfuso, senza marca: mele, confezione 2" }));
         await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa 2" }));
         expect(await screen.findByRole("heading", { name: "Dispensa" })).toBeDefined();
         expect(screen.getByText("2 in dispensa · 2 restano in lista")).toBeDefined();
       });
     });
   ```

- [ ] **Step 2: Falliscono**

Run: `npx vitest run src/features/stocking`
Expected: FAIL — `itemsLeft` non esiste, `stockNotice(4, 3)` dà ancora «4 in dispensa» (legge il 3 come le voci nel carrello), `./PackageRow` non si risolve, `after` è ignorata, «+ un'altra confezione» non c'è.

- [ ] **Step 3: `stockingView.ts`**

1. `stockEntries` diventa (il commento sopra resta, con una frase in più in fondo: «Una voce può avere più confezioni (S3 §10.2): `packagesOf` ne dice le chiavi, la prima è l'id della voce; parte una riga per ogni confezione scelta.»):
   ```ts
   export function stockEntries(
     items: ShoppingItem[],
     resolved: Record<string, Resolution>,
     ingredientOf: (item: ShoppingItem) => string | null,
     expiry: Record<string, string>,
     packagesOf: (item: ShoppingItem) => string[] = (item) => [item.id]
   ): StockEntry[] {
     const entries: StockEntry[] = [];
     for (const item of items) {
       const ingredientId = ingredientOf(item);
       if (!ingredientId) continue;
       for (const key of packagesOf(item)) {
         const resolution = resolved[key];
         if (!resolution) continue;
         entries.push({
           shopping_item_id: item.id,
           // tutte le confezioni di una voce sono del suo ingrediente: il backend
           // rifiuta il contrario (StockRequest)
           ingredient_id: ingredientId,
           product_id: resolution.kind === "product" ? resolution.product.id : null,
           // sempre presente, mai assente: una riga senza scadenza manda `null`.
           //
           // `||` e non `??`, e la differenza è tutta qui: svuotare il campo data (un
           // Backspace su un segmento basta) lascia la stringa vuota, e `''` non è una
           // data — il backend risponde 422, il messaggio dice «riprova», e il riprova
           // ricostruisce lo stesso corpo identico all'infinito. `PantryRow.commitExpiry`
           // fa la stessa cosa nello stesso modo: le due forme devono restare uguali.
           expires_on: expiry[key] || null,
           // sempre presente come la scadenza; `null` per lo sfuso e per ogni prodotto che
           // non è stato scelto a catalogo dopo un codice letto
           barcode: (resolution.kind === "product" && resolution.barcode) || null,
         });
       }
     }
     return entries;
   }

   /** Le voci del carrello da cui non parte nessuna confezione: restano in lista,
    * spuntate. Contate per voce, non per confezione. */
   export function itemsLeft(items: ShoppingItem[], entries: StockEntry[]): number {
     const sent = new Set(entries.map((entry) => entry.shopping_item_id));
     return items.filter((item) => !sent.has(item.id)).length;
   }
   ```
2. `stockNotice` diventa (il commento: «`left` è quante voci del carrello non sono partite: restano in lista, spuntate. Le confezioni si contano in `sent`, le voci in `left` (S3: da una voce ne possono partire più d'una). Le voci ancora da comprare non contano — non erano in questa spesa (deciso con Mattia il 2026-09-29). Se sono entrate tutte, della lista non si dice niente.»):
   ```ts
   export function stockNotice(sent: number, left: number): string {
     const head = `${sent} in dispensa`;
     if (left <= 0) return head;
     return `${head} · ${left} ${left === 1 ? "resta" : "restano"} in lista`;
   }
   ```

- [ ] **Step 4: `PackageRow.tsx`**

```tsx
import { useRef, type ReactNode } from "react";
import { ExpiryField } from "./ExpiryField";
import { ResolutionNote } from "./ResolutionNote";
import { useReturnFocus } from "./useReturnFocus";
import type { FocusTarget, Resolution } from "./stockingView";
import { Button } from "../../components/ui/Button";
import { IconToolbar } from "../../components/ui/IconToolbar";
import {
  IconBarcode,
  IconListSearch,
  IconReplace,
  IconScale,
  IconX,
} from "../../components/ui/icons";

/** Una confezione in più di una voce di «Sistema la spesa» (S3 §10.2, decisa da Mattia
 * il 2026-10-07): da «prosciutto cotto» due vaschette con due scadenze, da «yogurt» una
 * alla fragola e una alla pesca. Sta sotto la voce, rientrata, con le stesse tre strade,
 * la sua «+ scadenza» e il suo pannello; è dello stesso ingrediente della voce, che è
 * quello che la guardia dello scanner e il filtro del catalogo confrontano. I nomi per
 * chi ascolta dicono quale confezione («Codice a barre per mele, confezione 2»): la prima
 * è la riga della voce, coi nomi di sempre. Le sue icone si ritrovano per
 * `data-package-trigger`, non per `data-trigger`: sta dentro la riga della voce, e le
 * due ricerche del fuoco non devono trovarsi a vicenda. */
export function PackageRow({
  name,
  index,
  resolution,
  expiry,
  onExpiry,
  returnFocusTo,
  onFocusReturned,
  onOpen,
  onLoose,
  onChange,
  onRemove,
  children,
}: {
  /** Il testo della voce. */
  name: string;
  /** Il numero della confezione, dal 2: la prima è la voce. */
  index: number;
  resolution: Resolution | undefined;
  expiry: string | undefined;
  onExpiry: (value: string | undefined) => void;
  returnFocusTo: FocusTarget | null;
  onFocusReturned: () => void;
  onOpen: (trigger: "scanner" | "catalog") => void;
  onLoose: () => void;
  onChange: () => void;
  onRemove: () => void;
  /** Il pannello aperto per questa confezione. */
  children?: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const which = `${name}, confezione ${index}`;
  useReturnFocus(ref, returnFocusTo, onFocusReturned, "data-package-trigger");

  return (
    <div ref={ref} className="border-t border-line pt-1">
      <div className="flex items-center gap-2">
        <div className="min-w-0 flex-1 break-words">
          <p className="text-sm font-medium">Confezione {index}</p>
          {resolution && <ResolutionNote resolution={resolution} />}
        </div>
        {resolution ? (
          <span data-package-trigger="change" className="contents">
            <Button
              variant="ghost"
              icon={IconReplace}
              label={`Cambia la scelta per ${which}`}
              onClick={onChange}
            />
          </span>
        ) : (
          <IconToolbar label={`Come entra in dispensa: ${which}`}>
            <span data-package-trigger="scanner" className="contents">
              <Button
                variant="ghost"
                icon={IconBarcode}
                label={`Codice a barre per ${which}`}
                onClick={() => onOpen("scanner")}
              />
            </span>
            <span data-package-trigger="catalog" className="contents">
              <Button
                variant="ghost"
                icon={IconListSearch}
                label={`Cerca a catalogo per ${which}`}
                onClick={() => onOpen("catalog")}
              />
            </span>
            <Button
              variant="ghost"
              icon={IconScale}
              label={`Sfuso, senza marca: ${which}`}
              onClick={onLoose}
            />
          </IconToolbar>
        )}
        <Button
          variant="ghost"
          icon={IconX}
          label={`Togli la confezione ${index} di ${name}`}
          onClick={onRemove}
        />
      </div>

      {children && <div className="pt-2 pb-2">{children}</div>}

      <ExpiryField name={which} value={expiry} onChange={onExpiry} />
    </div>
  );
}
```

- [ ] **Step 5: `StockingRow` prende `after`**

In `StockingRow.tsx`: nella firma, dopo `children,` aggiungi `after,`; nel tipo, dopo la prop `children`:
```ts
  /** In fondo alla voce, dopo la sua scadenza: le confezioni in più e «+ un'altra
   * confezione» (S3 §10.2). */
  after?: ReactNode;
```
e in fondo alla `<li>`, subito dopo `<ExpiryField name={name} value={expiry} onChange={onExpiry} />`, aggiungi `{after}`.

- [ ] **Step 6: `StockingScreen.tsx`**

Leggi il file com'è dopo il Task 6, poi:

1. Gli import: aggiungi `import { PackageRow } from "./PackageRow";` (dopo `MatchPanel`), e nell'import da `./stockingView` aggiungi `itemsLeft,` prima di `stockEntries,`.
2. Subito dopo `const panelSerial = useRef(0);` aggiungi:
   ```tsx
     // Le confezioni in più di ogni voce (S3 §10.2), in ordine; la prima ha la chiave della
     // voce e non sta qui. Chiavi mai riusate: togliendone una, la scelta di un'altra non
     // le passa sopra
     const [extraPackages, setExtraPackages] = useState<Record<string, string[]>>({});
     const packageSerial = useRef(0);
   ```
3. In `stock`: `mutationFn: ({ sent }: { sent: StockEntry[]; checked: number }) => stockItems(sent),` diventa `mutationFn: ({ sent }: { sent: StockEntry[]; left: number }) => stockItems(sent),`; `onSuccess: (_created, { sent, checked }) => {` diventa `onSuccess: (_created, { sent, left }) => {`; `notice({ text: stockNotice(sent.length, checked) });` diventa `notice({ text: stockNotice(sent.length, left) });`.
4. Subito dopo la funzione `writeExpiry` aggiungi:
   ```tsx
     function packagesOf(item: ShoppingItem): string[] {
       return [item.id, ...(extraPackages[item.id] ?? [])];
     }

     /** «+ un'altra confezione»: una riga nuova sotto la voce, con le sue tre strade; il
      * fuoco va alla prima. */
     function addPackage(item: ShoppingItem) {
       packageSerial.current += 1;
       const key = `${item.id}+${packageSerial.current}`;
       setExtraPackages((prev) => ({ ...prev, [item.id]: [...(prev[item.id] ?? []), key] }));
       stock.reset();
       setReturnFocus({ key, target: "scanner" });
     }

     /** La ✕ di una confezione in più: via lei, la sua scelta, la sua data, il suo codice,
      * e il suo pannello se era aperto. Il fuoco torna alla voce. */
     function removePackage(item: ShoppingItem, key: string) {
       setExtraPackages((prev) => ({
         ...prev,
         [item.id]: (prev[item.id] ?? []).filter((other) => other !== key),
       }));
       setResolved((prev) => without(prev, key));
       setExpiry((prev) => without(prev, key));
       setRememberedCode((prev) => without(prev, key));
       const open = openPanel.current;
       if (open?.kind === "resolver" && open.packageKey === key) setOpen(null);
       stock.reset();
       setReturnFocus({ key: item.id, target: resolved[item.id] ? "change" : "scanner" });
     }
   ```
5. `const entries = stockEntries(items, resolved, ingredientOf, expiry);` diventa `const entries = stockEntries(items, resolved, ingredientOf, expiry, packagesOf);`.
6. In `submitStock`, `stock.mutate({ sent: entries, checked: items.length });` diventa `stock.mutate({ sent: entries, left: itemsLeft(items, entries) });`.
7. In `renderRow`, prima del `return` aggiungi:
   ```tsx
       const keys = packagesOf(item);
       const extras = keys.slice(1);
       // «+ un'altra confezione» quando ogni confezione che c'è ha la sua scelta: su una
       // voce risolta (bozza §10.2), senza impilare confezioni vuote
       const canAddPackage = ingredientOf(item) !== null && keys.every((key) => key in resolved);
   ```
   e fra le prop di `<StockingRow`, dopo `onChange={() => changeResolution(item.id)}`, aggiungi:
   ```tsx
           after={
             extras.length > 0 || canAddPackage ? (
               <div className="flex flex-col pl-3">
                 {extras.map((key, index) => (
                   <PackageRow
                     key={key}
                     name={item.raw_text}
                     index={index + 2}
                     resolution={resolved[key]}
                     expiry={expiry[key]}
                     onExpiry={(value) => writeExpiry(key, value)}
                     returnFocusTo={returnFocusFor(key, item)}
                     onFocusReturned={clearReturnFocus}
                     onOpen={(trigger) => openPanelFor(item, key, trigger)}
                     onLoose={() => resolve(key, { kind: "loose" })}
                     onChange={() => changeResolution(key)}
                     onRemove={() => removePackage(item, key)}
                   >
                     {panelFor(item, key)}
                   </PackageRow>
                 ))}
                 {canAddPackage && (
                   <button
                     type="button"
                     onClick={() => addPackage(item)}
                     className="flex min-h-11 items-center self-start text-xs font-medium text-ink-faint"
                   >
                     {/* come «+ scadenza»: piccolo, e il nome della voce solo per chi
                         ascolta, con lo spazio fuori dallo `sr-only` (Chromium lo mangia) */}
                     + un'altra confezione <span className="sr-only">di {item.raw_text}</span>
                   </button>
                 )}
               </div>
             ) : undefined
           }
   ```
8. Il commento sopra «Metti in dispensa» («Il numero è quello delle confezioni che partono davvero») è già giusto dal Task 6.

- [ ] **Step 7: Passano**

Run: `npx vitest run src/features/stocking && npm run typecheck && npm run lint`
Expected: verde; **+13 test** (4 in `stockingView.test.ts` contando la riga nuova di `stockNotice`, 3 in `PackageRow.test.tsx`, 1 in `StockingRow.test.tsx`, 5 in `StockingScreen.test.tsx`); le prove di prima di `StockingScreen.test.tsx` e `StockingRow.test.tsx` passano senza essere toccate.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/features/stocking
git commit -m "feat(stocking): «+ un'altra confezione» dello stesso ingrediente, con la sua scelta, la sua scadenza e il suo pannello; «Metti in dispensa N» conta le confezioni (S3 §10.2)"
```

---

### Task 10: «Articolo aggiuntivo» in «Sistema la spesa»

**Files:**
- Modify: `frontend/src/features/stocking/StockingScreen.tsx`
- Modify: `frontend/src/features/stocking/StockingScreen.test.tsx` (un `describe` nuovo in fondo)

**Interfaces:**
- Consumes: `IngredientChooser` con `busy` (Task 3); `addShoppingItem(rawText, ingredientId)` e `patchShoppingItem(id, { status })` da `features/shopping-list/api.ts` (esistono); `refocusAfterMatch` (Task 6).

- [ ] **Step 1: I test che falliscono**

In fondo al file `StockingScreen.test.tsx`, dentro il `describe("StockingScreen", …)` (dopo il `describe` del Task 9):

```tsx
  describe("«Articolo aggiuntivo» (S3 §10.1)", () => {
    const PANE = { id: "i5", name: "pane", display_name: "Pane", category: "cereali", kind: "food" };
    const PANE_IN_LISTA = {
      id: "s9", raw_text: "Pane", ingredient_id: "i5", ingredient_name: "pane",
      ingredient_category: "cereali", ingredient_kind: "food", status: "pending", reason: "manual",
      created_at: "2026-10-08T10:00:00Z",
    };

    function writes(spy: ReturnType<typeof stubRoutedFetch>) {
      return spy.mock.calls
        .filter(([, init]) => ["POST", "PATCH"].includes(String((init as RequestInit)?.method)))
        .map(([url, init]) => [
          String(url),
          (init as RequestInit).method,
          JSON.parse(String((init as RequestInit).body)),
        ]);
    }

    async function chooseExtra(term: string, option: string) {
      await userEvent.click(await screen.findByRole("button", { name: "Articolo aggiuntivo" }));
      await userEvent.type(screen.getByRole("textbox", { name: "Cosa hai comprato?" }), term);
      await userEvent.click(await screen.findByRole("option", { name: option }));
    }

    it("mette in lista una voce già spuntata, che compare fra le altre col fuoco sulla sua prima icona", async () => {
      let checked = false;
      const spy = stubRoutedFetch((path, init) => {
        if (path.includes("/ingredients/search")) return [[PANE]];
        if (path.endsWith("/shopping-list") && init?.method === "POST") {
          return [{ ...PANE_IN_LISTA, added: true }, 201];
        }
        if (path.endsWith("/shopping-list/s9") && init?.method === "PATCH") {
          checked = true;
          return [{ ...PANE_IN_LISTA, status: "checked" }];
        }
        return [checked ? [...CHECKED, { ...PANE_IN_LISTA, status: "checked" }] : CHECKED];
      });
      renderScreen();
      await chooseExtra("pan", "Pane");

      await vi.waitFor(() =>
        expect(document.activeElement).toBe(
          screen.getByRole("button", { name: "Codice a barre per Pane" })
        )
      );
      expect(writes(spy)).toEqual([
        ["/api/v1/shopping-list", "POST", { raw_text: "Pane", ingredient_id: "i5" }],
        ["/api/v1/shopping-list/s9", "PATCH", { status: "checked" }],
      ]);
      expect(screen.queryByRole("textbox", { name: "Cosa hai comprato?" })).toBeNull();
    });

    it("un ingrediente già spuntato non si doppia e non si rispunta: la sua voce prende il fuoco", async () => {
      const MELA = { id: "i2", name: "mela", display_name: "Mela", category: "frutta", kind: "food" };
      const spy = stubRoutedFetch((path, init) => {
        if (path.includes("/ingredients/search")) return [[MELA]];
        if (path.endsWith("/shopping-list") && init?.method === "POST") {
          return [{ ...CHECKED[1], ingredient_kind: "food", added: false }];
        }
        return [CHECKED];
      });
      renderScreen();
      await chooseExtra("mel", "Mela");
      await vi.waitFor(() =>
        expect(document.activeElement).toBe(
          screen.getByRole("button", { name: "Codice a barre per mele" })
        )
      );
      expect(writes(spy).map(([, method]) => method)).toEqual(["POST"]);
    });

    it("se non riesce lo dice, e la scelta resta lì da rifare", async () => {
      stubRoutedFetch((path, init) => {
        if (path.includes("/ingredients/search")) return [[PANE]];
        if (path.endsWith("/shopping-list") && init?.method === "POST") return [{ detail: "giù" }, 500];
        return [CHECKED];
      });
      renderScreen();
      await chooseExtra("pan", "Pane");
      expect(
        await screen.findByText("Non sono riuscito ad aggiungerlo alla spesa da sistemare. Riprova.")
      ).toBeDefined();
      expect(screen.getByRole("textbox", { name: "Cosa hai comprato?" })).toBeDefined();
    });

    it("a lista vuota non c'è: lo schermo vuoto porta alla Lista", async () => {
      stubRoutedFetch(() => [[]]);
      renderScreen();
      await screen.findByRole("heading", { name: "Niente da sistemare" });
      expect(screen.queryByRole("button", { name: "Articolo aggiuntivo" })).toBeNull();
    });
  });
```

- [ ] **Step 2: Falliscono**

Run: `npx vitest run src/features/stocking/StockingScreen.test.tsx`
Expected: FAIL nelle prime tre (il pulsante «Articolo aggiuntivo» non c'è); la quarta passa già e resta a guardia.

- [ ] **Step 3: `StockingScreen.tsx`**

Leggi il file com'è dopo il Task 9, poi:

1. Gli import: `import { fetchShoppingList, patchShoppingItem } from "../shopping-list/api";` diventa `import { addShoppingItem, fetchShoppingList, patchShoppingItem } from "../shopping-list/api";`; aggiungi `import { IngredientChooser } from "./IngredientChooser";` (dopo `./api` o in ordine con gli altri `./`), `import { Alert } from "../../components/ui/Alert";` (prima di `Button`), e `IconPackageImport` diventa `IconPackageImport, IconPlus`.
2. Subito dopo la `useMutation` di `stock` aggiungi:
   ```tsx
     // «Articolo aggiuntivo» (S3 §10.1, forma a): una cosa comprata che in lista non
     // c'era. Diventa una voce di lista nata spuntata, con le rotte di oggi, e si sistema
     // qui come le altre: la sistemazione resta tutto-o-niente, e la rotta `stock` non cambia
     const [extraOpen, setExtraOpen] = useState(false);
     const addExtra = useMutation({
       mutationFn: async (ingredient: Ingredient) => {
         // il testo della voce è il nome dell'ingrediente, come se l'avessi scritto. Un
         // ingrediente già in lista non si doppia (S18): il backend risponde con la voce che
         // c'era — da comprare, la si spunta, perché è stata comprata (A, deciso da Mattia il 2026-10-09);
         // già spuntata, è già qui
         const added = await addShoppingItem(ingredient.display_name, ingredient.id);
         if (added.status === "checked") return added;
         return patchShoppingItem(added.id, { status: "checked" });
       },
       onSuccess: (item) => {
         setExtraOpen(false);
         // il fuoco va alla prima icona della voce quando la lista riletta la porta: lo
         // stesso percorso di un abbinamento (S19)
         setRefocusAfterMatch(item.id);
         return queryClient.invalidateQueries({ queryKey: ["shopping-list"] });
       },
     });
   ```
3. Nel blocco in fondo (`<div className="flex flex-col gap-2 pt-1">`), **prima** di `{stock.isError && (`, aggiungi:
   ```tsx
                   {/* in fondo, prima di «Metti in dispensa»: si aggiunge quel che manca,
                       poi si mette tutto in dispensa. Solo con qualcosa da sistemare (C, deciso
                       da Mattia il 2026-10-09): a schermo vuoto la strada è la Lista, o la Dispensa */}
                   {extraOpen ? (
                     <div className="flex flex-col gap-3 rounded-card border border-line bg-card p-3">
                       <h2 className="font-semibold">Articolo aggiuntivo</h2>
                       <IngredientChooser
                         label="Cosa hai comprato?"
                         failureNote="Puoi comunque aggiungerlo."
                         initialTerm=""
                         busy={addExtra.isPending}
                         onChosen={(ingredient) => {
                           if (!addExtra.isPending) addExtra.mutate(ingredient);
                         }}
                         before={
                           <p className="text-sm text-ink-soft">
                             Entra in lista già spuntato, e lo sistemi qui come le altre voci.
                           </p>
                         }
                         after={
                           <Button
                             variant="ghost"
                             onClick={() => {
                               addExtra.reset();
                               setExtraOpen(false);
                             }}
                             className="self-start"
                           >
                             Annulla
                           </Button>
                         }
                       />
                       {addExtra.isError && (
                         <Alert>Non sono riuscito ad aggiungerlo alla spesa da sistemare. Riprova.</Alert>
                       )}
                     </div>
                   ) : (
                     <Button icon={IconPlus} onClick={() => setExtraOpen(true)} className="self-start">
                       Articolo aggiuntivo
                     </Button>
                   )}
   ```
4. Il commento sopra `refocusAfterMatch` prende in fondo la frase: «Lo usa anche «Articolo aggiuntivo»: la voce nuova arriva con la rilettura, e il fuoco la aspetta allo stesso modo.».

- [ ] **Step 4: Passano**

Run: `npx vitest run src/features/stocking && npm run typecheck && npm run lint`
Expected: verde; **+4 test**; tutte le prove di prima di `StockingScreen.test.tsx` passano senza essere toccate.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/stocking
git commit -m "feat(stocking): «Articolo aggiuntivo», una voce di lista nata spuntata che si sistema con le altre (S3 §10.1)"
```

---

### Task 11: L'e2e — l'ingresso diretto e le confezioni nel browser vero, a 375×812

jsdom non calcola il CSS (quarta lezione di `CLAUDE.md`): che «Scansiona» sia un bersaglio da 44 accanto al +, che la scheda e la riga di una confezione stiano nello schermo, che i loro testi reggano 4,5:1 nei due temi, e che il fuoco cada davvero su «Metti in dispensa», lo dice solo un browser. Nel browser dell'e2e la fotocamera non c'è: il codice si scrive nel campo, come fa già la prova di «Sistema la spesa».

**Files:**
- Modify: `frontend/e2e/style.spec.ts` (tre migrazioni, due aiuti e tre `test(...)` in fondo)

- [ ] **Step 1: Le tre aggiunte in dispensa che ora passano dalla scheda**

Tre prove del file aggiungono una voce con il + della Dispensa, e ora fra la scelta dell'ingrediente e la voce c'è la scheda. Subito dopo ciascuna di queste righe:

```ts
  await page.getByRole("option", { name: /^Cipolla\b/ }).click();
```
```ts
  await page.getByRole("option", { name: /^Carota\b/ }).click();
```
```ts
  await page.getByRole("option", { name: /^Mascarpone\b/ }).click();
```

aggiungi:

```ts
  // la scheda di conferma dell'ingresso diretto (S3): un tocco in più
  await page.getByRole("button", { name: "Metti in dispensa", exact: true }).click();
```

(Sono le prove «le tacche della dispensa sono bersagli da pollice», «il campo data si vede, e la pastiglia della scadenza porta il suo colore» e «a 375px nessuna schermata scorre di lato, e in lista si spunta toccando il nome». Nient'altro cambia in loro.)

- [ ] **Step 2: Le prove nuove**

In fondo a `frontend/e2e/style.spec.ts` (il `beforeEach` del file ha già fatto l'accesso; `fermo`, `testiIlleggibili` e `senzaScorrimentoLaterale` sono già definiti più sopra):

```ts
// --- S3: l'ingresso diretto in dispensa, e le confezioni in «Sistema la spesa» ---

/** Ogni testo della pagina sopra 4,5:1 nei due temi, nello stato che la prova ha aperto:
 * gli stati di S3 non li apre nessun altro giro di questo file. */
async function leggibileNeiDueTemi(page: Page, dove: string) {
  for (const tema of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: tema });
    await fermo(page);
    expect(await testiIlleggibili(page), `${dove}, tema ${tema}`).toEqual([]);
  }
  await page.emulateMedia({ colorScheme: "light" });
}

/** Pulsanti della stessa riga: ognuno almeno 44×44, e tutti alla stessa altezza. */
async function bersagliInFila(page: Page, nomi: string[]) {
  const scatole: { x: number; y: number; width: number; height: number }[] = [];
  for (const nome of nomi) {
    const scatola = await page.getByRole("button", { name: nome, exact: true }).boundingBox();
    expect(scatola, nome).not.toBeNull();
    expect(scatola!.width, nome).toBeGreaterThanOrEqual(44);
    expect(scatola!.height, nome).toBeGreaterThanOrEqual(44);
    scatole.push(scatola!);
  }
  for (const scatola of scatole.slice(1)) {
    expect(Math.abs(scatola.y - scatole[0].y), `${nomi.join(", ")}: vanno a capo`).toBeLessThan(1);
  }
}

test("l'ingresso diretto a 375px: «Scansiona», la scheda in due tocchi, la serie e «Annulla» nell'avviso", async ({
  page,
}) => {
  // il `beforeEach` tocca «Entra» ma non aspetta la risposta
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  // Una confezione vera da leggere: il seme non ha prodotti. Sotto «lenticchie», che
  // nessun altro file nomina, con un codice che cambia a ogni esecuzione. In fondo si
  // tolgono la voce (se «Annulla» non l'ha già tolta) e il prodotto: il file non lascia
  // niente dietro di sé
  const trovate = (await (
    await page.request.get("/api/v1/ingredients/search?q=lenticchie")
  ).json()) as { id: string; name: string }[];
  const lenticchie = trovate.find((voce) => voce.name === "lenticchie");
  expect(lenticchie, "«lenticchie» non è nel seme").toBeDefined();
  const codice = String(Date.now());
  const nome = `Lenticchie e2e ${codice}`;
  const creato = await page.request.post("/api/v1/products", {
    data: { ingredient_id: lenticchie!.id, name: nome, brand: "Marca e2e", barcode: codice },
  });
  expect(creato.ok()).toBe(true);
  const prodottoId = ((await creato.json()) as { id: string }).id;

  try {
    await page.goto("/dispensa");
    // «Scansiona» accanto al +: un bersaglio da pollice, sulla stessa riga
    await bersagliInFila(page, ["Scansiona", "Aggiungi in dispensa"]);
    await page.getByRole("button", { name: "Scansiona", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Codice a barre", exact: true })).toBeVisible();
    await senzaScorrimentoLaterale(page, "lo scanner della Dispensa");
    await leggibileNeiDueTemi(page, "lo scanner della Dispensa");

    // primo tocco: il codice letto (qui scritto: la fotocamera non c'è)
    const campo = page.getByLabel("Codice a barre", { exact: true });
    await campo.fill(codice);
    await campo.press("Enter");
    const metti = page.getByRole("button", { name: "Metti in dispensa", exact: true });
    await expect(metti).toBeFocused();
    await expect(page.getByText(nome, { exact: true })).toBeVisible();
    await expect(page.getByText("Marca e2e · lenticchie", { exact: true })).toBeVisible();
    await bersagliInFila(page, [`Cambia: ${nome}`]);
    // la scadenza aperta, perché si misuri anche il campo; poi richiusa
    await page.getByRole("button", { name: `+ scadenza per ${nome}`, exact: true }).click();
    await expect(page.getByLabel(`Scadenza di ${nome}`)).toBeVisible();
    await senzaScorrimentoLaterale(page, "la scheda di conferma");
    await leggibileNeiDueTemi(page, "la scheda di conferma, col campo della data");
    await page
      .getByRole("button", { name: `Togli la data di scadenza per ${nome}`, exact: true })
      .click();

    // secondo tocco
    await metti.click();
    const avviso = page.getByRole("status").filter({ hasText: `In dispensa: Marca e2e ${nome}` });
    await expect(avviso).toBeVisible();
    await expect(page.locator("li", { hasText: nome })).toBeVisible();
    // in serie: lo scanner è di nuovo lì, pronto per il codice dopo
    await expect(page.getByRole("heading", { name: "Codice a barre", exact: true })).toBeVisible();
    await expect(campo).toHaveValue("");

    // «Annulla» nell'avviso (che dura sei secondi) toglie la voce appena entrata
    await avviso.getByRole("button", { name: "Annulla", exact: true }).click();
    await expect(page.locator("li", { hasText: nome })).toHaveCount(0);

    // lo stesso codice riletto: la scheda lo dice, invece di scriverlo due volte
    await campo.fill(codice);
    await campo.press("Enter");
    await expect(
      page.getByText("L'hai appena messo in dispensa: se è un'altra confezione, mettila pure.")
    ).toBeVisible();
    await leggibileNeiDueTemi(page, "la scheda con la nota della serie");
    await page.getByRole("button", { name: "Chiudi l'aggiunta", exact: true }).click();
    await expect(metti).toHaveCount(0);
  } finally {
    // prima le voci, poi il prodotto (come `perOgniLuogo`): ogni passo è un `expect.soft`,
    // che non lancia e non salta il passo dopo, ma segna la prova fallita
    try {
      const dispensa = (await (await page.request.get("/api/v1/pantry")).json()) as {
        id: string;
        product_id: string | null;
      }[];
      for (const voce of dispensa.filter((riga) => riga.product_id === prodottoId)) {
        const risposta = await page.request.patch(`/api/v1/pantry/${voce.id}`, {
          data: { archived: true },
        });
        expect.soft(risposta.ok(), `pulizia: la voce ${voce.id} non si è archiviata`).toBe(true);
      }
    } catch (guasto) {
      expect.soft(false, `pulizia: non sono riuscito a rileggere la dispensa (${guasto})`).toBe(true);
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
});

test("il + della Dispensa a 375px: la scheda sfusa con le strade del codice e del catalogo, nei due temi", async ({
  page,
}) => {
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  // niente si scrive: la scheda si apre, si misura e si chiude. «melanzana» non la nomina
  // nessun altro file
  await page.goto("/dispensa");
  await page.getByLabel("Cerca o aggiungi in dispensa").fill("melanz");
  await page.getByRole("button", { name: "Aggiungi in dispensa" }).click();
  await page.getByRole("option", { name: /^Melanzana\b/ }).click();
  const metti = page.getByRole("button", { name: "Metti in dispensa", exact: true });
  await expect(metti).toBeFocused();
  await expect(page.getByText("Sfuso, senza marca · melanzana", { exact: true })).toBeVisible();
  await bersagliInFila(page, ["Codice a barre per Melanzana", "Cerca a catalogo per Melanzana"]);
  await bersagliInFila(page, ["Cambia: Melanzana"]);
  await senzaScorrimentoLaterale(page, "la scheda sfusa");
  await leggibileNeiDueTemi(page, "la scheda sfusa");

  // «Codice»: lo scanner con l'ingrediente atteso; il suo «Annulla» torna alla scheda
  await page.getByRole("button", { name: "Codice a barre per Melanzana", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Codice a barre per «Melanzana»" })).toBeVisible();
  await page.getByRole("button", { name: "Annulla", exact: true }).click();
  await expect(metti).toBeVisible();
  // «Annulla» della scheda chiude, e niente è entrato
  await page.getByRole("button", { name: "Annulla", exact: true }).click();
  await expect(metti).toHaveCount(0);
  await expect(page.locator("li", { hasText: "melanzana" })).toHaveCount(0);
});

test("Sistema la spesa a 375px: «+ un'altra confezione» e «Articolo aggiuntivo», nei due temi", async ({
  page,
}) => {
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  // una voce nel carrello con un ingrediente che nessun altro file nomina, creata con
  // l'API e tolta in fondo; niente entra in dispensa
  const trovati = (await (
    await page.request.get("/api/v1/ingredients/search?q=kiwi")
  ).json()) as { id: string; name: string }[];
  const kiwi = trovati.find((voce) => voce.name === "kiwi");
  expect(kiwi, "«kiwi» non è nel seme").toBeDefined();
  const risposta = await page.request.post("/api/v1/shopping-list", {
    data: { raw_text: "kiwi", ingredient_id: kiwi!.id },
  });
  // 201: una voce che c'era già (S18) risponde 200 ed è di qualcun altro
  expect(risposta.status(), "«kiwi» era già in lista").toBe(201);
  const voceId = ((await risposta.json()) as { id: string }).id;

  try {
    const spunta = await page.request.patch(`/api/v1/shopping-list/${voceId}`, {
      data: { status: "checked" },
    });
    expect(spunta.ok()).toBe(true);
    await page.goto("/sistema");

    await page.getByRole("button", { name: "Sfuso, senza marca: kiwi", exact: true }).click();
    await page.getByRole("button", { name: "+ un'altra confezione di kiwi", exact: true }).click();
    await expect(
      page.getByRole("button", { name: "Codice a barre per kiwi, confezione 2", exact: true })
    ).toBeFocused();
    await bersagliInFila(page, [
      "Codice a barre per kiwi, confezione 2",
      "Cerca a catalogo per kiwi, confezione 2",
      "Sfuso, senza marca: kiwi, confezione 2",
      "Togli la confezione 2 di kiwi",
    ]);
    await page.getByRole("button", { name: "+ scadenza per kiwi, confezione 2", exact: true }).click();
    await expect(page.getByLabel("Scadenza di kiwi, confezione 2")).toBeVisible();
    await expect(page.getByRole("button", { name: "Metti in dispensa 1", exact: true })).toBeVisible();
    await senzaScorrimentoLaterale(page, "Sistema la spesa con due confezioni");
    await leggibileNeiDueTemi(page, "Sistema la spesa con due confezioni");

    await page.getByRole("button", { name: "Articolo aggiuntivo", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Articolo aggiuntivo" })).toBeVisible();
    await expect(page.getByRole("textbox", { name: "Cosa hai comprato?" })).toBeFocused();
    await senzaScorrimentoLaterale(page, "«Articolo aggiuntivo» aperto");
    await leggibileNeiDueTemi(page, "«Articolo aggiuntivo» aperto");
    await page.getByRole("button", { name: "Annulla", exact: true }).click();
    await expect(page.getByRole("button", { name: "Articolo aggiuntivo", exact: true })).toBeVisible();
  } finally {
    try {
      const archiviata = await page.request.patch(`/api/v1/shopping-list/${voceId}`, {
        data: { status: "archived" },
      });
      expect.soft(archiviata.ok(), `pulizia: la voce ${voceId} non si è archiviata`).toBe(true);
    } catch (guasto) {
      expect
        .soft(false, `pulizia: non sono riuscito ad archiviare la voce ${voceId} (${guasto})`)
        .toBe(true);
    }
  }
});
```

Se una prova del contrasto segnala un testo di S3 sotto 4,5:1, **non cambiare token**: scrivi nel report quale testo, su quale fondo, in quale tema e con quale rapporto, e segna il task `bloccato` — un colore si decide di giorno. Se una misura di 44 px o lo scorrimento di lato non tornano, aggiusta classi e spazi della scheda o della riga (scelta estetica delegata) e scrivilo nel report.

- [ ] **Step 3: Il tipo del file**

Run (da `frontend/`): `npm run typecheck && npm run lint`
Expected: puliti. `tsc -b` compila anche gli e2e.

- [ ] **Step 4: Lo stack e2e, e l'e2e intera**

Dalla radice di `<worktree>`, con i comandi delle Global Constraints: `cp .env.example .env`, `up -d --build --wait`, il seme `--con-ricette`, poi `(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)`.
Expected: tutti verdi, **`N_e2e` + 3**. Se una prova fallisce e lascia dati nello stack, prima di rieseguire ricrea lo stack da zero (`down -v`, `up`, seme). Alla fine, sempre:

```bash
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
rm .env
```

- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/style.spec.ts
git commit -m "e2e: S3 a 375px — «Scansiona» e la scheda in due tocchi, la serie, «Annulla» nell'avviso, la scheda sfusa, le confezioni e «Articolo aggiuntivo» nei due temi"
```

---

### Task 12: I documenti

**Files:**
- Modify: `docs/prossimi-passi.md`
- Modify: `next-steps.md`

Leggi prima i due file com'è sul ramo.

- [ ] **Step 1: La voce S3**

In `docs/prossimi-passi.md`:

1. Il titolo `## S3. Ingresso diretto in dispensa, alla pari di «sistema la spesa» **[D]**` diventa `## S3. Ingresso diretto in dispensa, alla pari di «sistema la spesa» **[FATTO <data di oggi> — ramo night/s3-ingresso-diretto, non ancora in produzione]**`.
2. In fondo alla voce S3 (dopo il paragrafo che finisce con «È la prima lezione di `CLAUDE.md`.», prima di `## S4.`) aggiungi:
   ```markdown
   **Fatto il <data di oggi>** (bozza `docs/superpowers/specs/2026-10-06-ingresso-diretto-bozza.md`,
   piano `docs/superpowers/plans/2026-10-08-s3-ingresso-diretto.md`), parità subito e senza
   scontrino, come deciso da Mattia il 2026-10-07. In Dispensa, accanto al +, **«Scansiona»**:
   un prodotto a catalogo entra con due tocchi — il codice e «Metti in dispensa» nella scheda
   di conferma, che ha già il fuoco —, e il pannello torna allo scanner per la confezione
   dopo (in serie; lo stesso prodotto riletto lo dice); un codice nuovo chiede di che
   ingrediente è, poi il modulo, con l'uscita sfusa e quella dal catalogo. Il **+** crea
   l'ingrediente che manca, e la scheda sfusa offre codice e catalogo. La scadenza si scrive
   nella scheda; l'avviso «In dispensa: …» ha «Annulla». In «Sistema la spesa»
   **«Articolo aggiuntivo»** (una voce di lista nata spuntata) e **«+ un'altra confezione»**
   dello stesso ingrediente, con la sua scelta, la sua data e il suo pannello: «Metti in
   dispensa N» conta le confezioni. Le guardie non si sono copiate: la regia dei pannelli è
   uscita da `StockingScreen` in `ProductResolver` (l'esito tardivo, il codice che segue di
   S8, la `key` del modulo), la scelta o creazione dell'ingrediente da `MatchPanel` in
   `IngredientChooser`, e nel backend `stock_one` è la sola copia di «voce, poi codice», per
   la sistemazione e per `POST /pantry` (che ora prende `expires_on` e `barcode`). Due
   confezioni della stessa voce con ingredienti diversi: 422.

   **Le scelte del piano che Mattia può voler rivedere:** «Scansiona» come quadrato di sola
   icona; «Cambia» nella scheda che torna indietro di un passo; nella scansione, «Annulla»
   che torna allo scanner e il campo dell'ingrediente che parte vuoto; la riga di una
   confezione in più (rientrata, «Confezione 2», con la sua ✕); «+ un'altra confezione» solo
   quando tutte le confezioni hanno la loro scelta; l'avviso che conta confezioni entrate e
   voci rimaste. E le tre segnate «da confermare» nel piano: A (un articolo aggiuntivo già da
   comprare in lista si spunta), B («Cerca a catalogo» anche dopo un codice nuovo nella
   scansione), C («Articolo aggiuntivo» solo con qualcosa da sistemare).

   **Da provare sul telefono:** la fotocamera vera in serie (l'attesa fra un codice e
   l'altro, perché `BarcodeScanner` si riaccende a ogni giro), la fotocamera negata, la
   tastiera numerica del codice a mano, la scheda col pollice; «+ un'altra confezione» e
   «Articolo aggiuntivo» in corsia.
   ```
   Sostituisci `<data di oggi>` con la data vera.

- [ ] **Step 2: `next-steps.md`**

1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte: S3 fatto, da revisionare)_`.
2. Togli la riga `[in corso] … S3, ingresso diretto …` da «In corso» (se la sezione resta vuota, rimetti `_(niente)_`).
3. In cima a «Fatti (recenti)» aggiungi:
   ```markdown
   - [fatto] <data di oggi> · S3, ingresso diretto in dispensa: «Scansiona» in serie con la scheda di conferma (due tocchi per una confezione a catalogo), il + che crea l'ingrediente, la scadenza prima di entrare e «Annulla» nell'avviso; in «Sistema la spesa» «Articolo aggiuntivo» e «+ un'altra confezione»; la regia dei pannelli in `ProductResolver`, `stock_one` nel backend [S3] → branch night/s3-ingresso-diretto (da revisionare)
   ```
4. In cima a «Da fare a mano (solo Mattia)» aggiungi:
   ```markdown
   - [tbd] P1 · Prove sul telefono di S3: la fotocamera vera in serie (si sente l'attesa fra un codice e l'altro?), la fotocamera negata, la tastiera numerica del codice a mano, la scheda col pollice; «+ un'altra confezione» e «Articolo aggiuntivo» in corsia [S3]
   ```
5. Nessuna voce da confermare: le tre scelte A, B e C sono state decise da Mattia il 2026-10-09, prima della notte.
6. In «Idee» aggiungi:
   ```markdown
   - [idea] P3 · In serie la fotocamera si riaccende a ogni codice (`BarcodeScanner` la rilascia al primo letto): se sul telefono l'attesa si sente, tenerla accesa fra un codice e l'altro [S3]
   - [idea] P3 · Dopo S3 la prop `emptyNote` di `IngredientPicker` non ha più chiamanti (la usava solo l'aggiunta della Dispensa): toglierla, dopo il merge del piano dei suggerimenti, che tocca lo stesso file [S3]
   ```
   L'idea già presente «Una voce già in lista (in attesa o spuntata) che entra dall'ingresso diretto…» resta com'è (decisione 4).
7. Se nella notte sono emerse altre cose fuori da questo piano, aggiungile come `idea` o `tbd` nella sezione giusta, con la voce di `docs/prossimi-passi.md` fra parentesi quadre.

- [ ] **Step 3: Commit**

```bash
git add docs/prossimi-passi.md next-steps.md
git commit -m "docs: S3 fatto sul ramo — l'ingresso diretto in dispensa, «Articolo aggiuntivo» e le confezioni"
```

---

### Task 13: La verifica finale e il report

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

Expected: vitest tutto verde — **`N_vitest` della Preparazione più 52**, cioè 2 (Task 3) + 6 (Task 4) + 6 (Task 5) + 8 (Task 7) + 13 (Task 8) + 13 (Task 9) + 4 (Task 10), in **`N_file` + 6** file (`IngredientChooser.test.tsx`, `ProductResolver.test.tsx`, `entryView.test.ts`, `EntryCard.test.tsx`, `DirectEntry.test.tsx`, `PackageRow.test.tsx`); se il numero differisce, scrivi nel report da dove viene la differenza. Typecheck, lint e build puliti. `npx tsc -b --force` perché `node_modules` è condiviso col checkout principale, e con lui il `tsbuildinfo`: `--force` compila davvero tutto.

- [ ] **Step 2: Il backend**

Da `<worktree>/backend`:

```bash
PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Expected: tutto verde, **`N_pytest` + 7**. `git diff master -- backend/alembic` vuoto: nessuna migrazione.

- [ ] **Step 3: I grep**

Dalla radice del worktree, i comandi di «Comandi di verifica». Expected come scritto lì.

- [ ] **Step 4: L'e2e intera**

Con i comandi delle Global Constraints, su uno stack ricreato da zero (`down -v` prima dell'`up`, se ne era rimasto uno di questo ramo). Expected: tutti verdi, `N_e2e` + 3. Poi `down -v` e `rm .env`, sempre.

- [ ] **Step 5: Il report**

Nel report della notte (`docs/night-reports/<data>.md`, sul ramo; se il file c'è già, aggiungi una sezione per questo piano), per S3: il ramo e da dove parte (`master` e il suo hash), i conti veri (vitest, pytest, e2e) contro quelli della Preparazione, le migrazioni di test fatte oltre a quelle elencate (dovrebbero essere zero), cosa ha trovato il `git diff` della Preparazione, le scelte estetiche prese in autonomia (misure e spazi della scheda e delle confezioni, se cambiate), le tre scelte A, B e C decise da Mattia il 2026-10-09 e che il ramo le fa così, e le prove sul telefono che restano. Poi:

```bash
git add docs/night-reports/
git commit -m "docs: report della notte, S3"
```

Niente push, niente merge, niente deploy. Il ramo `night/s3-ingresso-diretto` resta lì: è il punto di partenza del piano dopo (S12).
