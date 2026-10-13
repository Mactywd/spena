# Le pagine scartate dell'import, a video e rimesse in coda: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** nella coda d'import («Ingredienti da abbinare») una sezione «Scartate (N)», chiusa di partenza, elenca le pagine scaricate che non sono diventate ricette — titolo o indirizzo, il perché in parole da persona con la strada per correggerlo, le cotture che aspettano — e «Rimetti in coda» le rimanda per la strada normale, `materialize_ready`, dicendo nell'avviso com'è finita.

**Architecture:** la causa di uno scarto si legge con una funzione pura, `explain_skip`, accanto a chi la scrive (`backend/app/services/recipe_import/materialize.py`), e lo scarto non alimentare si scrive con la stessa costante che lei legge. Un servizio nuovo, `requeue_page` (`backend/app/services/recipe_import/requeue.py`), rimette la pagina `pending`, riallinea i termini (`sync_terms`), materializza, riallinea, e dice l'esito di quella pagina. Due rotte sotto `/api/v1/imports/pages/`: l'elenco paginato e la rimessa. Nel frontend le parole stanno in funzioni pure (`skippedWords.ts`), la sezione in un componente suo (`SkippedPages.tsx`), montato in fondo a `ImportQueueScreen`. Nessuna migrazione.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, pytest su Postgres vero; React 19, TypeScript, Tailwind 4 (token in `@theme`), TanStack Query 5 (`useInfiniteQuery`), react-router 7, Vitest + Testing Library (jsdom), Playwright.

**Spec:** `docs/superpowers/specs/2026-10-09-scartate-in-coda-design.md` — le decisioni di Mattia del 2026-10-09 (§2, 1–4), quelle di Claude su delega (§2, 5–13), la pagina illeggibile (opzione A, decisa da Mattia il 2026-10-13), il comportamento esatto (§3) e le parole a video (§4). Il ragionamento di partenza è in `docs/prossimi-passi.md`, Parte X («**Una pagina `SKIPPED` non torna mai in coda, nemmeno dopo aver corretto la causa.**» e «**`skipped_reason` non affiora da nessuna rotta né da nessuna schermata**»), e nella «Nota della revisione del Task 3, chiusa il 2026-09-28» (gli id delle cotture che restano nel `payload`).

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/scartate-in-coda` (`.worktrees/` è già in `.gitignore`), ramo `night/scartate-in-coda`, creato da **`master`**: questo piano è il nono della notte ma non dipende da nessuno dei rami prima di lui, e nessun piano parte dal suo. Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì (o dalle sue `backend/` e `frontend/`), mai dalla radice del checkout principale. Il checkout principale non si tocca: se vi trovi modifiche non committate, sono dell'utente. **Nessun push, nessun merge, nessun deploy. Mai `git stash`.**
- **I file che anche altri piani della notte toccano**: `frontend/src/components/ui/icons.ts` (S15 aggiunge gli **stessi** due chevron, con le stesse due righe: vedi Task 5; S3 e S12 ci aggiungono altre icone), `frontend/src/domain/types.ts` (S12, S14, S15), `frontend/e2e/style.spec.ts` (quasi tutti), `next-steps.md`, `docs/prossimi-passi.md`, il report della notte. Sul tuo ramo, che parte da `master`, sono come su `master`. Il piano descrive comunque ogni modifica a un file esistente contro un'ancora riconoscibile — una funzione, un elemento JSX, un testo esatto — e mai contro numeri di riga: **leggi il file com'è sul ramo prima di cambiarlo**. Le prove nuove di `style.spec.ts` si aggiungono **in fondo al file**, i tipi nuovi di `types.ts` **dopo `UndoResult`**, senza toccare il resto; al merge, l'unione con gli altri rami la fa la revisione.
- **Il frontend non calcola logica di dominio.** La causa di uno scarto, se la pagina si può rimettere, com'è finita una rimessa: tutto viene dal backend in codici (`cause`, `requeueable`, `outcome`). Il frontend li traduce in parole e basta.
- **Una ricetta non nomina un non alimentare** (`CLAUDE.md`, decisione 2): la rimessa non aggira niente. Passa da `materialize_ready` → `create_recipe` → `write_recipe_ingredients`, che continua a rifiutare; una pagina con la causa ancora lì torna scartata.
- **Mai un vicolo cieco.** Ogni riga dice la sua strada (spec §2, 9); una rimessa che non riesce lo dice nell'avviso, e la riga resta; un rifiuto della rotta si legge nella sezione; una pagina illeggibile ha «Apri la pagina».
- **Un controllo che si spegne mentre ha il fuoco usa `aria-disabled`**, mai `disabled`: «Rimetti in coda», «Mostra altre» e «Riprova» sono `Button` con `busy` in volo (la regola di `frontend/src/components/ui/Button.tsx`). Il titolo della sezione è un `<button>` scritto a mano dentro l'`h2`, come l'intestazione dei reparti di S15: non è mai spento.
- Tutto il colore passa dai token di `frontend/src/index.css`: `text-ink-soft`, `text-ink-faint`, `border-line`, e le varianti di `buttonClasses`. **Nessun token nuovo.** `grep -rn "emerald\|neutral-" frontend/src` resta vuoto. Ogni testo sta sopra 4,5:1, in chiaro e in scuro, e lo misura `frontend/e2e/style.spec.ts`.
- Le icone si importano solo da `frontend/src/components/ui/icons.ts`. Servono `IconChevronDown` e `IconChevronRight` (il Task 5 li aggiunge; sono già nel pacchetto `@tabler/icons-react` installato).
- Ogni bersaglio nuovo è almeno 44×44 px (`min-h-11` di `buttonClasses`). A 375 px nessuna schermata scorre di lato.
- Le parole a video sono in italiano e **si copiano esattamente come sono scritte qui** (sono quelle del §4 della spec); gli identificatori in inglese; i commenti in italiano come nel resto del codice.
- **Il type check è `npm run typecheck`** (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0 (settima lezione di `CLAUDE.md`).
- Controlli del frontend, da `<worktree>/frontend`: `npx vitest run` (non esiste `npm test`), `npm run typecheck`, `npm run lint`, `npm run build`.
- **Backend su Postgres vero.** Il database dei test è il container `spena-db-1` (porta 5433), da usare solo come database dei test: se `docker ps --format '{{.Names}}'` non lo mostra, `docker start spena-db-1`. Questo piano parte da `master` e non ha migrazioni: usa il database `spena_test` di sempre (nessun `TEST_DATABASE_URL`). **Mai `docker compose up` dal worktree** (il nome del progetto Compose viene dalla cartella: nascerebbe un secondo Postgres che litiga sulla 5433), mai `-f docker-compose.prod.yml`. Nel worktree non c'è un `.venv`: si usa quello del checkout principale; `python -m` mette la cartella corrente in testa a `sys.path`, quindi si prova l'`app` del worktree. Il comando, sempre da `<worktree>/backend`:
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
- **Niente produzione, di notte.** Nessuna lettura e nessuna scrittura sulle pagine scartate vere: la rimessa in produzione la fa Mattia dall'app, dopo il deploy («Dopo il deploy (solo Mattia)»). Nei documenti non vanno numeri della produzione.
- Nessuna dipendenza nuova, nessuna migrazione, nessun cambio di configurazione globale.

### Preparazione (una volta, prima del Task 1)

- [ ] Il ramo di partenza è `master`, e i file di questo piano sono quelli su cui è scritto (`master` era `1df86c7` quando il piano è stato scritto; i commit che ci aggiungono solo documenti non contano):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify master
  git diff --stat 1df86c7 master -- \
    backend/app/services/recipe_import/ \
    backend/app/repositories/imports.py \
    backend/app/api/imports.py \
    backend/app/schemas/recipe_import.py \
    frontend/src/features/recipe-import/ \
    frontend/src/domain/types.ts \
    frontend/src/components/ui/icons.ts
  ls backend/app/services/recipe_import/requeue.py frontend/src/features/recipe-import/SkippedPages.tsx frontend/e2e/scartate.spec.ts 2>&1 | grep -c "No such file"
  ```
  Expected: un hash; il `diff --stat` **vuoto**; `3` (i tre file nuovi non esistono ancora). Se il `diff` non è vuoto, `master` è andato avanti su questi file: applica le modifiche del piano sopra la versione di `master`, ancora per ancora, e scrivilo nel report. Se uno dei tre file nuovi esiste già, **fermati**: qualcuno ha già cominciato questa voce; scrivi nel report della notte (`docs/night-reports/<data>.md`, sul ramo `night/scartate-in-coda` appena creato) cosa hai trovato, segna la voce `bloccato` in `next-steps.md` di quel ramo con la domanda per Mattia, e non partire.
- [ ] Dal checkout principale, allinea `node_modules` al lockfile (non aggiunge dipendenze, installa quelle di `package-lock.json`):
  ```bash
  cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund
  ```
- [ ] Crea il worktree da `master` e collega `node_modules` (e solo quello: **niente `.env`**):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/scartate-in-coda -b night/scartate-in-coda master
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/scartate-in-coda/frontend/node_modules
  ```
- [ ] La voce in `next-steps.md` del ramo passa a `in corso`. Cercala per testo, `grep -n "SKIPPED\|scartate" next-steps.md`: di giorno può essere stata spostata in «Pronti per la notte» e riscritta («Pagine scartate rimesse in coda…»); cambia solo lo stato fra parentesi quadre della voce di questo piano, non l'idea su `skipped_reason` (la toglie il Task 7). Poi:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/scartate-in-coda
  git add next-steps.md
  git commit -m "next-steps: le pagine scartate rimesse in coda, in corso"
  ```
- [ ] La linea di partenza, dal worktree:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/scartate-in-coda/frontend && npx vitest run 2>&1 | grep -E "Test Files|Tests "
  cd ../backend && PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q 2>&1 | tail -n 1
  cd ../frontend && npx playwright test --list 2>/dev/null | tail -n 1
  ```
  Expected: tutto verde. **Annota i numeri** (file e test di vitest, test di pytest, prove e file dell'e2e): sono `N_file`, `N_vitest`, `N_pytest`, `N_e2e` del Task 8. Se una delle due suite non è verde, fermati: non è un difetto di questo piano, e va scritto nel report.

---

## Obiettivo e contesto

Una pagina scaricata diventa ricetta quando tutti i suoi termini sono decisi. Se non può, finisce `skipped` col motivo in `recipe_imports.skipped_reason`, e oggi da lì non esce: nessuna strada dell'app la rimette `pending` (`undo_decision` riprende solo le `imported`), e il motivo non si vede (`/imports/status` ne dà solo il numero). Così una ricetta scartata per una riga non alimentare resta fuori anche dopo che l'ingrediente è tornato cibo, e le cotture che aspettavano nel suo `payload` restano senza ricetta; per rimetterla si apriva il database. Le scartate sono di tre tipi (spec §1): **illeggibili** (scartate allo scarico, `payload` vuoto), **tutte ignorate** (`EMPTY_REASON`), **riga non alimentare** («riga non alimentare: «…»»). Questo piano le mette a video nella coda e dà a ciascuna, dove serve, «Rimetti in coda».

## Decisioni prese

Da Mattia, il 2026-10-09:

1. **Una sezione «Scartate» nella coda d'import**, **chiusa di partenza**, col numero: **«Scartate (N)»**.
2. Per ogni pagina il **titolo** (o l'**indirizzo**), il **motivo in parole da persona**, e **«Rimetti in coda»**.
3. Rimessa, la pagina torna `pending` e segue la **strada normale** (`materialize_ready`): se la causa è corretta diventa ricetta e rilega le cotture che aspettano nel `payload`; se no torna scartata col suo motivo, **e lo si dice all'utente**.
4. Chiude anche l'idea su `skipped_reason`.

Da Claude, su delega di Mattia (tecniche ed estetiche; reversibili):

5. **Le rotte**: `GET /api/v1/imports/pages/skipped?limit=&offset=` (1–100, 50 di default; da 0) → `{total, pages}`; `POST /api/v1/imports/pages/{id}/requeue`.
6. **La causa si legge in un posto solo**: `explain_skip(payload, skipped_reason)` in `materialize.py`, accanto a chi scrive i motivi, con `NON_FOOD_PREFIX` usato sia per scrivere sia per leggere. Dà `cause` (`unreadable` | `all_ignored` | `non_food` | `other`), `non_food_name`, `requeueable`.
7. **«Rimetti in coda» materializza subito**, nella stessa richiesta: `materialize_ready` gira solo a ogni decisione e allo scarico, e lasciata al ciclo normale una pagina rimessa non avrebbe un esito da dire. Ordine: `pending` → `sync_terms` → `materialize_ready` → `sync_terms`. Il primo `sync_terms` fa rinascere un termine sparito dal dizionario (in coda, o deciso da sé se coincide con l'anagrafica), il secondo rifà `occurrences` sulle pagine davvero in attesa. Esiti: `imported` (con `recipe_id` e le cotture rilegate), `skipped` (con la causa), `waiting` (coi nomi dei termini ancora in coda — il caso di una decisione della pagina annullata nel frattempo).
8. **L'esito va nell'avviso unico** (`useNotice`); se la pagina è entrata, l'avviso ha l'azione «Apri» verso la ricetta. Un rifiuto della rotta (409 col `detail`, o un guasto) è un `Alert` nella sezione.
9. **Ogni riga dice anche la strada** (Anagrafica, o l'annullamento della decisione), così l'avviso di una rimessa che non riesce può restare corto e la strada non sparisce con lui.
10. **Le cotture che aspettano si dicono nella riga** (`waiting_cooking_events`, il numero di id in `cooking_event_ids`).
11. **La sezione sta in fondo alla coda**, dopo «Decisioni recenti», e non c'è con N = 0. N è `skipped` di `/imports/status`, che la schermata legge già; l'elenco si chiede solo aprendo, 50 per volta con «Mostra altre». La chiave è `["import-status", "skipped-pages"]`: le tre mutazioni della coda (decidi, chiedi all'AI, annulla), che possono scartare pagine, invalidano già `["import-status"]` e rileggono così anche l'elenco, senza toccare il loro codice.
12. **Ordine dell'elenco**: `fetched_at` decrescente, a parità per indirizzo.
13. **Il titolo della sezione è un `<button>` dentro l'`h2`**, con `aria-expanded`, `aria-controls`, chevron giù aperta e a destra chiusa, alto almeno 44 px; il contenuto chiuso ha `hidden`. Nessuna animazione.

**La pagina illeggibile: l'opzione A della spec, decisa da Mattia il 2026-10-13:** **si mostra col suo perché, senza «Rimetti in coda», con «Apri la pagina»** (l'indirizzo originale, in una scheda nuova), e la rotta la rifiuta con un 409. Rimetterla non può riuscire: il `payload` è vuoto e l'indirizzo non si riscarica, quindi tornerebbe scartata — e col motivo sbagliato, «ogni ingrediente è stato ignorato». Le alternative scartate (B: offrire lo stesso il pulsante; C: non mostrarla; D: un «Riscarica») sono nella spec.

## Criteri di accettazione

- [ ] `explain_skip` riconosce le tre cause vere e il resto, e rilegge esattamente il motivo che `materialize_ready` scrive (due test passano per la materializzazione vera).
- [ ] `requeue_page`: con la causa corretta la pagina diventa `imported` con la sua ricetta e le cotture del `payload` rilegate; senza, torna `skipped` col motivo di prima; con un termine tornato in coda resta `pending` e dice quale, con `occurrences` ricontato; un termine sparito che coincide con l'anagrafica rinasce deciso e la pagina entra; una pagina illeggibile o non scartata si rifiuta e resta com'era.
- [ ] `GET /api/v1/imports/pages/skipped` elenca solo le scartate, col perché in codici, il totale e le cotture che aspettano; si sfoglia con `limit`/`offset` senza doppioni; rifiuta `limit` fuori da 1–100 e `offset` negativo; senza sessione risponde 401.
- [ ] `POST /api/v1/imports/pages/{id}/requeue` risponde l'esito di quella pagina; 404 per una pagina che non c'è, 409 col perché per una non scartata o illeggibile; senza sessione 401.
- [ ] Nella coda, con pagine scartate, in fondo c'è «Scartate (N)», chiusa, che non chiede l'elenco finché non si apre; con N = 0 non c'è.
- [ ] Aperta: per ogni pagina il titolo (o l'indirizzo), il perché con la strada, le cotture che aspettano; «Rimetti in coda» dove serve, «Apri la pagina» per l'illeggibile; «Mostra altre» finché ne mancano. Nessun nome di variabile né motivo tecnico a video.
- [ ] Rimessa: l'avviso dice ««…» è entrata nel ricettario.» (con le cotture ritrovate e «Apri»), ««…» è tornata in coda: aspetta …», o ««…» è ancora scartata: …»; un rifiuto si legge nella sezione; in volo il pulsante è `aria-disabled` e tiene il fuoco.
- [ ] Nel browser vero, sullo stack e2e: la pagina illeggibile e la ricetta col non alimentare si vedono a 375 px senza scorrere di lato; rimessa senza correggere torna scartata; corretta la causa col servizio dell'anagrafica, rimessa entra nel ricettario, il numero cala di uno e «Apri» porta alla ricetta. Bersagli da 44 px e testi leggibili nei due temi (`style.spec.ts`).
- [ ] Tutti i test di oggi passano, senza toccarne nessuno.
- [ ] vitest, typecheck, lint, build, pytest e l'e2e intera verdi.
- [ ] `docs/prossimi-passi.md` e `next-steps.md` aggiornati (Task 7).

## Comandi di verifica

Da `<worktree>/backend`:

```bash
PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Da `<worktree>/frontend`:

```bash
npx vitest run
npm run typecheck
npm run lint
npm run build
```

Dalla radice di `<worktree>`:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -rn "riga non alimentare: " backend/app
grep -rln "skipped_reason" backend/app | sort
```

Expected: il primo vuoto; il secondo una riga sola, la definizione di `NON_FOOD_PREFIX` in `backend/app/services/recipe_import/materialize.py` (lo scarto lo scrive con la costante); il terzo `backend/app/api/imports.py`, `backend/app/db/models/recipe_import.py`, `backend/app/repositories/imports.py`, `backend/app/services/recipe_import/giallozafferano.py`, `backend/app/services/recipe_import/materialize.py`, `backend/app/services/recipe_import/requeue.py` (su `master` erano quattro: si aggiungono la rotta e il servizio). E l'e2e intera con i comandi delle Global Constraints.

## Fuori scope

- **Riscaricare una pagina illeggibile** (alternativa D della spec): `known_urls` resta com'è.
- **Un collegamento dalla riga al termine che blocca la pagina** (`?termine=<id>`): la riga dice la strada a parole; una decisione vecchia oltre le 50 «Decisioni recenti» si ritrova per ora solo dall'idea che c'è già in `next-steps.md` («Deciso nella coda» porta a una coda che mostra solo le 50 decisioni più recenti). Il Task 7 aggiunge l'idea del collegamento.
- Rimettere più pagine in un tocco, filtrare o cercare nell'elenco.
- Le pagine `imported` e `adopted`, `undo_decision`, `fix_registry`: non cambiano.
- Il 503 della coda, le schede dei termini, «Decisioni recenti»: non cambiano.
- Le scartate della produzione (sezione «Dopo il deploy»).

## Margine di autonomia

- **Liberi:** i nomi di variabili locali, helper di test e funzioni interne non fissati qui; l'ordine dei test dentro un file; l'ordine delle classi Tailwind; la formulazione dei commenti, purché dicano il perché; i dettagli estetici della sezione (spazi, misura del chevron) purché restino i vincoli: 44 px, nessuna animazione, nessun colore crudo, nessun token nuovo.
- **Fissi:** le parole a video, esattamente come nel §4 della spec e nel Task 4; le rotte, i loro parametri e le forme delle risposte (`SkippedPageOut`, `SkippedPagesOut`, `RequeueOut`); i codici `cause` e `outcome`; i nomi pubblici che altri task usano (`NON_FOOD_PREFIX`, `SkipCause`, `SkipExplained`, `explain_skip`, `requeue_page`, `Requeued`, `NotRequeueable`, `RequeueRefusal`, `get_page`, `skipped_pages`, `fetchSkippedPages`, `requeuePage`, `SKIPPED_PAGE_SIZE`, `SKIPPED_PAGES_KEY`, `skippedTitle`, `skipReasonText`, `cookingWaitingText`, `requeueResultMessage`, `SkippedPages`); la stringa del motivo non alimentare, che resta quella di oggi («riga non alimentare: «…»»).
- **Nessuna dipendenza nuova**, nessuna migrazione, nessun token di colore nuovo.
- **Nessun test di oggi si cambia.** Se uno fallisce, è un comportamento che il piano non ha previsto: si diagnostica e si scrive nel report.
- **Una decisione di comportamento non coperta e non reversibile** → si ferma quel task, si fa commit del lavoro parziale sul ramo, lo si segna `bloccato` in `next-steps.md` del ramo con la domanda precisa per Mattia, e si passa al task successivo. Una scelta reversibile e a basso impatto → la più conservativa, annotata nel report della notte.
- Se un test fallisce e non si risolve in modo ragionevole: niente test disattivati, niente asserzioni indebolite; `bloccato` con la diagnosi.

## Dipendenze

Nessuna: parte da `master`. Non consuma niente dei piani prima di lui nella catena, e nessun piano parte da questo ramo. Al merge i conflitti possibili sono testuali, nei file condivisi elencati nelle Global Constraints. **`icons.ts` con S15:** le due righe che il Task 5 aggiunge sono identiche a quelle di S15 (stesso commento, stessa posizione, subito dopo la riga di `IconShoppingCartPlus`): se arrivano al merge nella stessa forma git le fonde da sé; se no, al merge si tiene **una** copia dell'export — due `export { IconChevronDown, … }` dallo stesso modulo non compilano.

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `backend/app/services/recipe_import/materialize.py` | 1 | `NON_FOOD_PREFIX`, `SkipCause`, `SkipExplained`, `explain_skip`; lo scarto non alimentare scritto con la costante |
| `backend/tests/services/test_skip_reasons.py` | 1 | **nuovo**: nove test |
| `backend/app/repositories/imports.py` | 2, 3 | `get_page`; `skipped_pages` |
| `backend/app/services/recipe_import/requeue.py` | 2 | **nuovo**: `requeue_page` |
| `backend/tests/services/test_requeue.py` | 2 | **nuovo**: otto test |
| `backend/app/schemas/recipe_import.py` | 3 | `SkippedPageOut`, `SkippedPagesOut`, `RequeueOut` |
| `backend/app/api/imports.py` | 3 | le due rotte |
| `backend/tests/api/test_imports_skipped.py` | 3 | **nuovo**: dieci test |
| `frontend/src/domain/types.ts` | 4 | `SkipCause`, `SkippedPage`, `SkippedPages`, `RequeueResult` |
| `frontend/src/features/recipe-import/api.ts` | 4 | `SKIPPED_PAGE_SIZE`, `SKIPPED_PAGES_KEY`, `fetchSkippedPages`, `requeuePage` |
| `frontend/src/features/recipe-import/skippedWords.ts`, `skippedWords.test.ts` | 4 | **nuovi**: le parole; ventidue test |
| `frontend/src/components/ui/icons.ts` | 5 | `IconChevronDown`, `IconChevronRight` |
| `frontend/src/features/recipe-import/SkippedPages.tsx`, `SkippedPages.test.tsx` | 5 | **nuovi**: la sezione; dieci test |
| `frontend/src/features/recipe-import/ImportQueueScreen.tsx`, `ImportQueueScreen.test.tsx` | 5 | la sezione in fondo; due test |
| `backend/tests/e2e_skipped_pages.py` | 6 | **nuovo**: semina, correzione e pulizia per l'e2e |
| `backend/tests/test_e2e_skipped_pages_guard.py` | 6 | **nuovo**: un test |
| `frontend/e2e/scartate.spec.ts` | 6 | **nuovo**: una prova sul codice vero |
| `frontend/e2e/style.spec.ts` | 6 | una prova in fondo |
| `docs/prossimi-passi.md`, `next-steps.md` | 7 | i documenti |
| `docs/night-reports/<data>.md` | 8 | il report |

---

### Task 1: La causa di uno scarto, letta da un posto solo

**Files:**
- Modify: `backend/app/services/recipe_import/materialize.py`
- Test: `backend/tests/services/test_skip_reasons.py` (nuovo)

**Interfaces:**
- Consumes: `EMPTY_REASON`, `materialize_ready` (ci sono già).
- Produces, in `app.services.recipe_import.materialize`:
  - `NON_FOOD_PREFIX: str = "riga non alimentare: "`;
  - `class SkipCause(StrEnum)`: `UNREADABLE = "unreadable"`, `ALL_IGNORED = "all_ignored"`, `NON_FOOD = "non_food"`, `OTHER = "other"`;
  - `@dataclass(frozen=True) class SkipExplained` con `cause: SkipCause`, `non_food_name: str | None`, `requeueable: bool`;
  - `explain_skip(payload: dict, reason: str | None) -> SkipExplained`.

- [ ] **Step 1: Il test che fallisce**

Crea `backend/tests/services/test_skip_reasons.py`:

```python
"""Perché una pagina è scartata, letto da quel che la pagina conserva (spec
docs/superpowers/specs/2026-10-09-scartate-in-coda-design.md §3.1).

Gli ultimi due test passano per la materializzazione vera: il motivo che
`explain_skip` rilegge deve essere quello che `materialize_ready` scrive, non una sua
copia scritta nel test (prima lezione di CLAUDE.md).
"""

import pytest

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportState, ImportTerm, TermDecision
from app.repositories.imports import store_page
from app.repositories.ingredients import create_ingredient
from app.services.recipe_import.materialize import (
    EMPTY_REASON,
    NON_FOOD_PREFIX,
    SkipCause,
    explain_skip,
    materialize_ready,
)

RIGHE = {"title": "Torta", "ingredients": [{"key": "k-farina", "name": "Farina 00"}]}


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({}, "nessuna riga dd.gz-ingredient nella pagina"),
        ({}, "la fonte ha risposto 404"),
        ({"title": "Torta", "ingredients": []}, None),
    ],
)
def test_una_pagina_senza_righe_e_illeggibile_e_non_si_rimette(payload, reason):
    """Senza righe non c'è niente da materializzare, e l'indirizzo non si riscarica:
    rimessa in coda tornerebbe scartata, e col motivo sbagliato («ogni ingrediente è
    stato ignorato»)."""
    spiegato = explain_skip(payload, reason)
    assert spiegato.cause == SkipCause.UNREADABLE
    assert spiegato.requeueable is False
    assert spiegato.non_food_name is None


def test_le_righe_tutte_ignorate():
    spiegato = explain_skip(RIGHE, EMPTY_REASON[:200])
    assert (spiegato.cause, spiegato.non_food_name, spiegato.requeueable) == (
        SkipCause.ALL_IGNORED, None, True,
    )


def test_una_riga_non_alimentare_porta_il_nome_della_voce():
    spiegato = explain_skip(RIGHE, f"{NON_FOOD_PREFIX}«Carta forno»")
    assert (spiegato.cause, spiegato.non_food_name, spiegato.requeueable) == (
        SkipCause.NON_FOOD, "Carta forno", True,
    )


def test_un_nome_tagliato_dal_limite_della_colonna_resta_quel_che_ce():
    """`skipped_reason` è String(200): un nome lunghissimo perde la chiusa »."""
    motivo = f"{NON_FOOD_PREFIX}«{'x' * 300}»"[:200]
    spiegato = explain_skip(RIGHE, motivo)
    assert spiegato.cause == SkipCause.NON_FOOD
    assert spiegato.non_food_name == "x" * (200 - len(NON_FOOD_PREFIX) - 1)


def test_un_motivo_sconosciuto_con_le_righe_si_rimette():
    spiegato = explain_skip(RIGHE, "un motivo scritto da una versione di prima")
    assert (spiegato.cause, spiegato.non_food_name, spiegato.requeueable) == (
        SkipCause.OTHER, None, True,
    )


async def test_il_motivo_non_alimentare_scritto_da_materialize_si_rilegge(db_session):
    panna = await create_ingredient(
        db_session, name="panna", display_name="Panna", category=IngredientCategory.CASA
    )
    db_session.add(ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-panna", display_name="Panna fresca",
        occurrences=1, decision=TermDecision.MAPPED, ingredient_id=panna.id,
        decided_by="human", created_ingredient=False,
    ))
    await db_session.flush()
    pagina = await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/torta",
        payload={"title": "Torta", "ingredients": [{"key": "k-panna", "name": "Panna fresca"}]},
    )

    await materialize_ready(db_session, GIALLOZAFFERANO)

    assert pagina.state == ImportState.SKIPPED
    spiegato = explain_skip(pagina.payload, pagina.skipped_reason)
    assert (spiegato.cause, spiegato.non_food_name) == (SkipCause.NON_FOOD, "Panna")


async def test_il_motivo_delle_righe_ignorate_scritto_da_materialize_si_rilegge(db_session):
    db_session.add(ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-acqua", display_name="Acqua",
        occurrences=1, decision=TermDecision.IGNORED, decided_by="human",
    ))
    await db_session.flush()
    pagina = await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/acqua",
        payload={"title": "Acqua calda", "ingredients": [{"key": "k-acqua", "name": "Acqua"}]},
    )

    await materialize_ready(db_session, GIALLOZAFFERANO)

    assert pagina.state == ImportState.SKIPPED
    assert explain_skip(pagina.payload, pagina.skipped_reason).cause == SkipCause.ALL_IGNORED
```

- [ ] **Step 2: Il test fallisce**

Run (da `<worktree>/backend`): `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/services/test_skip_reasons.py`
Expected: FAIL in raccolta, `ImportError: cannot import name 'NON_FOOD_PREFIX'`.

- [ ] **Step 3: L'implementazione**

Leggi `backend/app/services/recipe_import/materialize.py` com'è sul ramo. Fra gli import in cima aggiungi, dopo `from dataclasses import dataclass`:

```python
from enum import StrEnum
```

Subito dopo il blocco di `EMPTY_REASON` (la costante che finisce con `"e una ricetta senza ingredienti risulterebbe sempre cucinabile"\n)`) aggiungi:

```python
# L'inizio del motivo di una pagina scartata per una riga non alimentare. Lo scrive
# `materialize_ready` e lo rilegge `explain_skip`: una costante sola, perché la stringa
# scritta e quella letta non possano scollarsi.
NON_FOOD_PREFIX = "riga non alimentare: "


class SkipCause(StrEnum):
    """Perché una pagina è scartata, in un codice. Le parole le scrive la schermata."""

    # scartata allo scarico (`store_unparsable`): niente righe da materializzare
    UNREADABLE = "unreadable"
    # ogni riga ignorata: resterebbe una ricetta senza ingredienti (`EMPTY_REASON`)
    ALL_IGNORED = "all_ignored"
    # `create_recipe` ha rifiutato una riga non alimentare (`NON_FOOD_PREFIX`)
    NON_FOOD = "non_food"
    # un motivo che questa versione non scrive più: le righe ci sono, si può riprovare
    OTHER = "other"


@dataclass(frozen=True)
class SkipExplained:
    cause: SkipCause
    # la voce non alimentare com'era scritta allo scarto; None per le altre cause, o se il
    # taglio a 200 caratteri del motivo non ne ha lasciato niente
    non_food_name: str | None
    # se rimetterla in coda può cambiare qualcosa
    requeueable: bool


def explain_skip(payload: dict, reason: str | None) -> SkipExplained:
    """Perché questa pagina è scartata, da quel che conserva (spec 2026-10-09 §3.1).

    Le righe prima del motivo: una pagina illeggibile ha il `payload` vuoto qualunque
    cosa dica il suo motivo, e rimessa in coda tornerebbe scartata subito — con
    `EMPTY_REASON`, che per lei sarebbe falso. Per questo non si rimette.
    """
    if not payload.get("ingredients"):
        return SkipExplained(SkipCause.UNREADABLE, None, requeueable=False)
    if reason == EMPTY_REASON[:200]:
        return SkipExplained(SkipCause.ALL_IGNORED, None, requeueable=True)
    if reason is not None and reason.startswith(NON_FOOD_PREFIX):
        name = reason[len(NON_FOOD_PREFIX):].strip().removeprefix("«").removesuffix("»").strip()
        return SkipExplained(SkipCause.NON_FOOD, name or None, requeueable=True)
    return SkipExplained(SkipCause.OTHER, None, requeueable=True)
```

In `materialize_ready`, nel ramo `except NonFoodInRecipe as exc:`, sostituisci

```python
            page.skipped_reason = f"riga non alimentare: «{exc.display_name}»"[:200]
```

con

```python
            page.skipped_reason = f"{NON_FOOD_PREFIX}«{exc.display_name}»"[:200]
```

(la stringa scritta resta identica, carattere per carattere).

- [ ] **Step 4: Il test passa, e il resto della materializzazione non si è mosso**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/services/test_skip_reasons.py tests/services/test_materialize.py tests/services/test_undo.py`
Expected: PASS, 9 test nuovi e quelli di prima.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/recipe_import/materialize.py backend/tests/services/test_skip_reasons.py
git commit -m "import: il perché di una pagina scartata si legge da un posto solo, accanto a chi lo scrive"
```

---

### Task 2: Rimettere in coda una pagina scartata

**Files:**
- Modify: `backend/app/repositories/imports.py` (`get_page`)
- Create: `backend/app/services/recipe_import/requeue.py`
- Test: `backend/tests/services/test_requeue.py` (nuovo)

**Interfaces:**
- Consumes: `explain_skip`, `SkipExplained`, `SkipCause` (Task 1); `materialize_ready`; `sync_terms` (`app.services.recipe_import.terms`); `terms_by_key` (`app.repositories.imports`).
- Produces:
  - `get_page(session: AsyncSession, page_id: uuid.UUID) -> RecipeImport | None` in `app.repositories.imports`;
  - in `app.services.recipe_import.requeue`: `class RequeueRefusal(StrEnum)` (`NOT_SKIPPED`, `UNREADABLE`); `class NotRequeueable(Exception)` con `.refusal: RequeueRefusal` e `.message: str`; `@dataclass(frozen=True) class Requeued` con `outcome: Literal["imported", "skipped", "waiting"]`, `recipe_id: uuid.UUID | None = None`, `cooking_relinked: int = 0`, `skip: SkipExplained | None = None`, `waiting_terms: list[str]` (vuota di default); `async def requeue_page(session: AsyncSession, page: RecipeImport) -> Requeued`.

- [ ] **Step 1: Il test che fallisce**

Crea `backend/tests/services/test_requeue.py`:

```python
"""Rimettere in coda una pagina scartata (spec
docs/superpowers/specs/2026-10-09-scartate-in-coda-design.md).

Le pagine si scartano col codice vero (`materialize_ready`), non scrivendo lo stato a
mano: il motivo che la rimessa rilegge è quello che la produzione scrive. La correzione
della causa si fa come la fa l'anagrafica: il reparto cambia, e `kind` lo segue dal
validatore del modello.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe import CookingEvent, Recipe
from app.db.models.recipe_import import (
    GIALLOZAFFERANO,
    ImportState,
    ImportTerm,
    RecipeImport,
    TermDecision,
)
from app.repositories.imports import store_page, store_unparsable
from app.repositories.ingredients import create_ingredient, remember_alias
from app.services.recipe_import.materialize import SkipCause, materialize_ready
from app.services.recipe_import.requeue import NotRequeueable, RequeueRefusal, requeue_page
from app.services.recipe_import.undo import undo_decision


def pagina(title: str, righe: list[tuple[str, str]]) -> dict:
    return {
        "title": title, "instructions": "Cuoci.", "servings": 4,
        "ingredients": [
            {"key": key, "name": name, "quantity_text": "100 g"} for key, name in righe
        ],
    }


@pytest_asyncio.fixture
async def scartate(db_session):
    """Due pagine scartate dal codice vero. «Torta alla panna» ha una riga su «Panna»,
    finita per sbaglio fra i prodotti per la casa: `create_recipe` la rifiuta. «Acqua
    calda» ha una riga sola, ignorata: resterebbe una ricetta senza ingredienti."""
    farina = await create_ingredient(
        db_session, name="farina", display_name="Farina", category=IngredientCategory.CEREALI
    )
    panna = await create_ingredient(
        db_session, name="panna", display_name="Panna", category=IngredientCategory.CASA
    )
    termini = {
        "farina": ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-farina", display_name="Farina 00",
            occurrences=1, decision=TermDecision.MAPPED, ingredient_id=farina.id,
            decided_by="human", created_ingredient=False,
        ),
        "panna": ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-panna", display_name="Panna fresca",
            occurrences=1, decision=TermDecision.MAPPED, ingredient_id=panna.id,
            decided_by="human", created_ingredient=False,
        ),
        "acqua": ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-acqua", display_name="Acqua",
            occurrences=1, decision=TermDecision.IGNORED, decided_by="human",
        ),
    }
    db_session.add_all(termini.values())
    await db_session.flush()
    torta = await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/torta",
        payload=pagina("Torta alla panna", [("k-farina", "Farina 00"), ("k-panna", "Panna fresca")]),
    )
    acqua = await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/acqua",
        payload=pagina("Acqua calda", [("k-acqua", "Acqua")]),
    )
    await materialize_ready(db_session, GIALLOZAFFERANO)
    assert (torta.state, acqua.state) == (ImportState.SKIPPED, ImportState.SKIPPED)
    return {"torta": torta, "acqua": acqua, "farina": farina, "panna": panna, "termini": termini}


async def test_con_la_causa_corretta_la_pagina_entra_nel_ricettario(db_session, scartate):
    torta = scartate["torta"]
    scartate["panna"].category = IngredientCategory.LATTICINI  # la correzione
    await db_session.flush()

    esito = await requeue_page(db_session, torta)

    assert esito.outcome == "imported"
    assert torta.state == ImportState.IMPORTED
    assert torta.skipped_reason is None
    assert torta.recipe_id is not None
    assert esito.recipe_id == torta.recipe_id
    assert esito.cooking_relinked == 0
    ricetta = await db_session.get(Recipe, torta.recipe_id)
    assert ricetta.title == "Torta alla panna"


async def test_le_cotture_che_aspettano_ritrovano_la_ricetta(db_session, scartate, dal_database):
    """Gli id che `undo_decision` lascia nel `payload` (S9 §5.2) tornano sulla ricetta
    rifatta: è `materialize_ready` a rilegarli, e la rimessa lo dice."""
    torta = scartate["torta"]
    evento = CookingEvent(recipe_id=None, servings=2, snapshot={"titolo": "Torta alla panna"})
    db_session.add(evento)
    await db_session.flush()
    torta.payload = {**torta.payload, "cooking_event_ids": [str(evento.id)]}
    scartate["panna"].category = IngredientCategory.LATTICINI
    await db_session.flush()
    evento_id, page_id = evento.id, torta.id

    esito = await requeue_page(db_session, torta)

    assert esito.cooking_relinked == 1
    assert (await dal_database(CookingEvent, evento_id)).recipe_id == torta.recipe_id
    assert "cooking_event_ids" not in (await dal_database(RecipeImport, page_id)).payload


async def test_senza_correggere_torna_scartata_col_suo_motivo(db_session, scartate):
    torta = scartate["torta"]

    esito = await requeue_page(db_session, torta)

    assert esito.outcome == "skipped"
    assert (esito.skip.cause, esito.skip.non_food_name) == (SkipCause.NON_FOOD, "Panna")
    assert torta.state == ImportState.SKIPPED
    assert torta.skipped_reason == "riga non alimentare: «Panna»"
    assert (await db_session.execute(select(Recipe))).scalars().all() == []


async def test_le_righe_ancora_tutte_ignorate_la_riscartano(db_session, scartate):
    esito = await requeue_page(db_session, scartate["acqua"])

    assert esito.outcome == "skipped"
    assert esito.skip.cause == SkipCause.ALL_IGNORED
    assert scartate["acqua"].state == ImportState.SKIPPED


async def test_con_un_termine_tornato_in_coda_aspetta_e_dice_quale(db_session, scartate):
    """La decisione «ignora» annullata nel frattempo: la pagina non è pronta, resta in
    coda, e la coda conta una ricetta in attesa di quel termine."""
    acqua, termine = scartate["acqua"], scartate["termini"]["acqua"]
    await undo_decision(db_session, termine)
    assert termine.occurrences == 0  # nessuna pagina in attesa lo usava

    esito = await requeue_page(db_session, acqua)

    assert esito.outcome == "waiting"
    assert esito.waiting_terms == ["Acqua"]
    assert acqua.state == ImportState.PENDING
    assert termine.occurrences == 1


async def test_un_termine_sparito_che_coincide_con_lanagrafica_rinasce_deciso(
    db_session, scartate
):
    """Il primo `sync_terms` della rimessa. Senza, `materialize_ready` lascerebbe la
    pagina ad aspettare un termine che non esiste, e il termine rinato dopo, deciso da
    sé, non la materializzerebbe fino alla prossima decisione qualunque."""
    torta, farina = scartate["torta"], scartate["farina"]
    scartate["panna"].category = IngredientCategory.LATTICINI
    await remember_alias(db_session, farina.id, "Farina 00")
    await db_session.delete(scartate["termini"]["farina"])
    await db_session.flush()

    esito = await requeue_page(db_session, torta)

    assert esito.outcome == "imported"
    rinato = (
        await db_session.execute(select(ImportTerm).where(ImportTerm.term_key == "k-farina"))
    ).scalars().one()
    assert (rinato.decision, rinato.decided_by, rinato.ingredient_id) == (
        TermDecision.MAPPED, "auto", farina.id,
    )


async def test_una_pagina_illeggibile_non_si_rimette(db_session):
    vuota = await store_unparsable(
        db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/vuota",
        reason="nessuna riga dd.gz-ingredient nella pagina",
    )

    with pytest.raises(NotRequeueable) as rifiuto:
        await requeue_page(db_session, vuota)

    assert rifiuto.value.refusal == RequeueRefusal.UNREADABLE
    assert vuota.state == ImportState.SKIPPED
    assert vuota.skipped_reason == "nessuna riga dd.gz-ingredient nella pagina"


async def test_una_pagina_che_non_e_scartata_non_si_rimette(db_session):
    in_attesa = await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/attesa",
        payload=pagina("Pane", [("k-lievito", "Lievito madre")]),
    )

    with pytest.raises(NotRequeueable) as rifiuto:
        await requeue_page(db_session, in_attesa)

    assert rifiuto.value.refusal == RequeueRefusal.NOT_SKIPPED
    assert in_attesa.state == ImportState.PENDING
```

- [ ] **Step 2: Il test fallisce**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/services/test_requeue.py`
Expected: FAIL in raccolta, `ModuleNotFoundError: No module named 'app.services.recipe_import.requeue'`.

- [ ] **Step 3: L'implementazione**

In `backend/app/repositories/imports.py`, subito dopo la funzione `get_term`, aggiungi:

```python
async def get_page(session: AsyncSession, page_id: uuid.UUID) -> RecipeImport | None:
    return await session.get(RecipeImport, page_id)
```

Crea `backend/app/services/recipe_import/requeue.py`:

```python
"""Rimettere in coda una pagina scartata (spec 2026-10-09-scartate-in-coda §2, §3.3).

Una pagina `skipped` non tornava indietro da nessuna strada dell'app: `undo_decision`
riprende solo le pagine `imported` con la loro ricetta. Qui la si rimette `pending` e la
si lascia alla strada di tutte, `materialize_ready`, che la fa ricetta se la causa è
stata corretta — rilegando le cotture che aspettano nel `payload` — o la scarta di nuovo
col suo motivo. Nessun percorso parallelo: lo stesso codice che materializza dopo una
decisione.

Si materializza subito, nella stessa chiamata, e non al giro dopo: `materialize_ready`
gira solo quando si decide un termine o si scarica, e una pagina rimessa resterebbe
`pending` senza un esito da dire a chi ha toccato il pulsante.
"""

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.recipe import CookingEvent
from app.db.models.recipe_import import ImportState, RecipeImport, TermDecision
from app.repositories.imports import terms_by_key
from app.services.recipe_import.materialize import (
    SkipExplained,
    explain_skip,
    materialize_ready,
)
from app.services.recipe_import.terms import sync_terms


class RequeueRefusal(StrEnum):
    NOT_SKIPPED = "not_skipped"
    UNREADABLE = "unreadable"


class NotRequeueable(Exception):
    """La pagina non si rimette in coda. `message` è la frase per chi ha toccato."""

    def __init__(self, refusal: RequeueRefusal, message: str) -> None:
        super().__init__(message)
        self.refusal = refusal
        self.message = message


@dataclass(frozen=True)
class Requeued:
    """Com'è finita questa pagina, e solo lei: `materialize_ready` può aver fatto
    ricette anche di altre pagine pronte, ma chi ha toccato chiede di questa."""

    outcome: Literal["imported", "skipped", "waiting"]
    recipe_id: uuid.UUID | None = None
    # le cotture che ora stanno sulla ricetta rifatta: tutte arrivate dal `payload`,
    # perché la ricetta è appena nata
    cooking_relinked: int = 0
    skip: SkipExplained | None = None
    # i termini della pagina ancora da decidere, nell'ordine delle righe
    waiting_terms: list[str] = field(default_factory=list)


async def requeue_page(session: AsyncSession, page: RecipeImport) -> Requeued:
    if page.state != ImportState.SKIPPED:
        raise NotRequeueable(
            RequeueRefusal.NOT_SKIPPED,
            "Questa pagina non è più scartata: l'elenco era vecchio.",
        )
    if not explain_skip(page.payload, page.skipped_reason).requeueable:
        raise NotRequeueable(
            RequeueRefusal.UNREADABLE,
            "La pagina non aveva una ricetta leggibile: rimetterla in coda non "
            "cambierebbe niente.",
        )

    page.state = ImportState.PENDING
    page.skipped_reason = None
    await session.flush()
    # Prima: un termine della pagina sparito dal dizionario rinasce — in coda, o deciso
    # da sé se coincide con l'anagrafica — invece di far aspettare la pagina un termine
    # che la coda non mostra, il vicolo cieco.
    await sync_terms(session, page.source)
    await materialize_ready(session, page.source)
    # Dopo: `occurrences` conta le ricette davvero in attesa, e questa forse non lo è più.
    await sync_terms(session, page.source)

    if page.state == ImportState.IMPORTED:
        relinked = await session.scalar(
            select(func.count())
            .select_from(CookingEvent)
            .where(CookingEvent.recipe_id == page.recipe_id)
        )
        return Requeued("imported", recipe_id=page.recipe_id, cooking_relinked=relinked or 0)
    if page.state == ImportState.SKIPPED:
        return Requeued("skipped", skip=explain_skip(page.payload, page.skipped_reason))

    terms = await terms_by_key(session, page.source)
    waiting: list[str] = []
    for line in page.payload.get("ingredients") or []:
        term = terms.get(line.get("key"))
        if (
            term is not None
            and term.decision == TermDecision.PENDING
            and term.display_name not in waiting
        ):
            waiting.append(term.display_name)
    return Requeued("waiting", waiting_terms=waiting)
```

- [ ] **Step 4: Il test passa**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/services/test_requeue.py tests/services/test_skip_reasons.py`
Expected: PASS (8 + 9).

Se `test_un_termine_sparito_che_coincide_con_lanagrafica_rinasce_deciso` fallisce perché il termine rinato resta `pending`: guarda in `backend/app/services/ingredient_match.py` cosa rende `certain` una coincidenza (nome canonico o alias) e su quale forma del nome confronta. Se l'alias scritto con `remember_alias(…, "Farina 00")` non basta, cambia nel test solo il modo di far coincidere il termine con l'anagrafica (per esempio un ingrediente il cui nome canonico è proprio «farina 00»), mai l'asserzione `MAPPED`/`auto`, e scrivilo nel report.

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/imports.py backend/app/services/recipe_import/requeue.py backend/tests/services/test_requeue.py
git commit -m "import: una pagina scartata si rimette in coda e segue la strada normale, con l'esito di quella pagina"
```

---

### Task 3: Le rotte — l'elenco delle scartate e la rimessa

**Files:**
- Modify: `backend/app/repositories/imports.py` (`skipped_pages`)
- Modify: `backend/app/schemas/recipe_import.py`
- Modify: `backend/app/api/imports.py`
- Test: `backend/tests/api/test_imports_skipped.py` (nuovo)

**Interfaces:**
- Consumes: `explain_skip`, `COOKING_EVENTS_KEY` (`materialize.py`); `get_page`, `requeue_page`, `NotRequeueable` (Task 2).
- Produces:
  - `skipped_pages(session, source, *, limit: int, offset: int) -> tuple[int, list[RecipeImport]]` in `app.repositories.imports`;
  - `SkippedPageOut` (`id`, `url`, `title: str | None`, `cause`, `non_food_name: str | None`, `requeueable: bool`, `waiting_cooking_events: int`), `SkippedPagesOut` (`total: int`, `pages: list[SkippedPageOut]`), `RequeueOut` (`outcome`, `title: str | None`, `url`, `recipe_id: uuid | None`, `cooking_relinked: int`, `cause: … | None`, `non_food_name: str | None`, `waiting_terms: list[str]`);
  - `GET /api/v1/imports/pages/skipped?limit=&offset=` → `SkippedPagesOut`; `POST /api/v1/imports/pages/{id}/requeue` → `RequeueOut`, 404 «pagina inesistente», 409 col `message` di `NotRequeueable`. Il Task 4 le chiama.

- [ ] **Step 1: Il test che fallisce**

Crea `backend/tests/api/test_imports_skipped.py`:

```python
"""Le pagine scartate dell'import: l'elenco col perché, e la rimessa in coda (spec
docs/superpowers/specs/2026-10-09-scartate-in-coda-design.md).

Le rotte di `/imports` sono dietro `require_session` (vedi
`test_senza_sessione_non_si_guarda_niente` in `test_imports.py`): qui si usa
`logged_client`, tranne nell'ultimo test.
"""

import uuid

import pytest_asyncio

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportState, ImportTerm, TermDecision
from app.repositories.imports import store_page, store_unparsable
from app.repositories.ingredients import create_ingredient
from app.services.recipe_import.materialize import materialize_ready

ELENCO = "/api/v1/imports/pages/skipped"


def pagina(title: str, righe: list[tuple[str, str]]) -> dict:
    return {
        "title": title, "instructions": "Cuoci.", "servings": 4,
        "ingredients": [
            {"key": key, "name": name, "quantity_text": "100 g"} for key, name in righe
        ],
    }


@pytest_asyncio.fixture
async def scarico(db_session):
    """Cinque pagine: tre scartate — una illeggibile, una con la riga tutta ignorata, una
    con una riga non alimentare — una in attesa e una importata."""
    farina = await create_ingredient(
        db_session, name="farina", display_name="Farina", category=IngredientCategory.CEREALI
    )
    panna = await create_ingredient(
        db_session, name="panna", display_name="Panna", category=IngredientCategory.CASA
    )
    db_session.add_all([
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-farina", display_name="Farina 00",
            occurrences=1, decision=TermDecision.MAPPED, ingredient_id=farina.id,
            decided_by="human", created_ingredient=False,
        ),
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-panna", display_name="Panna fresca",
            occurrences=1, decision=TermDecision.MAPPED, ingredient_id=panna.id,
            decided_by="human", created_ingredient=False,
        ),
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-acqua", display_name="Acqua",
            occurrences=1, decision=TermDecision.IGNORED, decided_by="human",
        ),
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-lievito", display_name="Lievito madre",
            occurrences=1, decision=TermDecision.PENDING,
        ),
    ])
    await db_session.flush()
    pagine = {
        "vuota": await store_unparsable(
            db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/vuota",
            reason="nessuna riga dd.gz-ingredient nella pagina",
        ),
        "torta": await store_page(
            db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/torta",
            payload=pagina("Torta alla panna", [("k-farina", "Farina 00"), ("k-panna", "Panna fresca")]),
        ),
        "acqua": await store_page(
            db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/acqua",
            payload=pagina("Acqua calda", [("k-acqua", "Acqua")]),
        ),
        "pane": await store_page(
            db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/pane",
            payload=pagina("Pane", [("k-farina", "Farina 00")]),
        ),
        "focaccia": await store_page(
            db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/focaccia",
            payload=pagina("Focaccia", [("k-farina", "Farina 00"), ("k-lievito", "Lievito madre")]),
        ),
    }
    await materialize_ready(db_session, GIALLOZAFFERANO)
    assert [pagine[n].state for n in ("vuota", "torta", "acqua", "pane", "focaccia")] == [
        ImportState.SKIPPED, ImportState.SKIPPED, ImportState.SKIPPED,
        ImportState.IMPORTED, ImportState.PENDING,
    ]
    return {**pagine, "panna": panna}


async def test_lelenco_dice_per_ogni_scartata_il_perche(logged_client, scarico):
    risposta = await logged_client.get(ELENCO)

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert corpo["total"] == 3
    per_indirizzo = {voce["url"]: voce for voce in corpo["pages"]}
    assert set(per_indirizzo) == {
        "https://esempio.invalid/vuota", "https://esempio.invalid/torta",
        "https://esempio.invalid/acqua",
    }
    assert per_indirizzo["https://esempio.invalid/vuota"] == {
        "id": str(scarico["vuota"].id), "url": "https://esempio.invalid/vuota", "title": None,
        "cause": "unreadable", "non_food_name": None, "requeueable": False,
        "waiting_cooking_events": 0,
    }
    torta = per_indirizzo["https://esempio.invalid/torta"]
    assert (torta["title"], torta["cause"], torta["non_food_name"], torta["requeueable"]) == (
        "Torta alla panna", "non_food", "Panna", True,
    )
    acqua = per_indirizzo["https://esempio.invalid/acqua"]
    assert (acqua["title"], acqua["cause"], acqua["non_food_name"], acqua["requeueable"]) == (
        "Acqua calda", "all_ignored", None, True,
    )


async def test_le_cotture_che_aspettano_si_contano(logged_client, db_session, scarico):
    torta = scarico["torta"]
    torta.payload = {**torta.payload, "cooking_event_ids": [str(uuid.uuid4()), str(uuid.uuid4())]}
    await db_session.flush()

    corpo = (await logged_client.get(ELENCO)).json()

    assert {voce["url"]: voce["waiting_cooking_events"] for voce in corpo["pages"]}[
        "https://esempio.invalid/torta"
    ] == 2


async def test_lelenco_si_sfoglia_senza_doppioni(logged_client, scarico):
    prima = (await logged_client.get(f"{ELENCO}?limit=2&offset=0")).json()
    seconda = (await logged_client.get(f"{ELENCO}?limit=2&offset=2")).json()

    assert (prima["total"], seconda["total"]) == (3, 3)
    assert (len(prima["pages"]), len(seconda["pages"])) == (2, 1)
    assert len({voce["id"] for voce in prima["pages"] + seconda["pages"]}) == 3


async def test_un_limite_fuori_misura_si_rifiuta(logged_client, scarico):
    for query in ("limit=0", "limit=101", "offset=-1"):
        assert (await logged_client.get(f"{ELENCO}?{query}")).status_code == 422, query


async def test_rimessa_dopo_la_correzione_entra_nel_ricettario(logged_client, db_session, scarico):
    scarico["panna"].category = IngredientCategory.LATTICINI
    await db_session.flush()

    risposta = await logged_client.post(f"/api/v1/imports/pages/{scarico['torta'].id}/requeue")

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert (corpo["outcome"], corpo["title"], corpo["url"]) == (
        "imported", "Torta alla panna", "https://esempio.invalid/torta",
    )
    assert (corpo["cooking_relinked"], corpo["cause"], corpo["non_food_name"], corpo["waiting_terms"]) == (
        0, None, None, [],
    )
    ricetta = await logged_client.get(f"/api/v1/recipes/{corpo['recipe_id']}")
    assert ricetta.status_code == 200
    assert ricetta.json()["title"] == "Torta alla panna"
    assert (await logged_client.get("/api/v1/imports/status")).json()["skipped"] == 2


async def test_rimessa_senza_correggere_torna_scartata_e_dice_perche(logged_client, scarico):
    risposta = await logged_client.post(f"/api/v1/imports/pages/{scarico['torta'].id}/requeue")

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert (corpo["outcome"], corpo["cause"], corpo["non_food_name"], corpo["recipe_id"]) == (
        "skipped", "non_food", "Panna", None,
    )
    assert (await logged_client.get("/api/v1/imports/status")).json()["skipped"] == 3


async def test_una_pagina_illeggibile_si_rifiuta_col_perche(logged_client, scarico):
    risposta = await logged_client.post(f"/api/v1/imports/pages/{scarico['vuota'].id}/requeue")

    assert risposta.status_code == 409
    assert "non aveva una ricetta leggibile" in risposta.json()["detail"]


async def test_una_pagina_non_scartata_si_rifiuta(logged_client, scarico):
    risposta = await logged_client.post(f"/api/v1/imports/pages/{scarico['focaccia'].id}/requeue")

    assert risposta.status_code == 409
    assert "non è più scartata" in risposta.json()["detail"]


async def test_una_pagina_che_non_ce(logged_client, scarico):
    risposta = await logged_client.post(f"/api/v1/imports/pages/{uuid.uuid4()}/requeue")

    assert risposta.status_code == 404


async def test_senza_sessione_non_si_guarda_e_non_si_rimette_niente(client):
    assert (await client.get(ELENCO)).status_code == 401
    assert (await client.post(f"/api/v1/imports/pages/{uuid.uuid4()}/requeue")).status_code == 401
```

- [ ] **Step 2: Il test fallisce**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/api/test_imports_skipped.py`
Expected: FAIL — le rotte rispondono 404 (o 405), non 200/409/422.

- [ ] **Step 3: Il repository**

In `backend/app/repositories/imports.py`, subito dopo la funzione `pending_pages`, aggiungi:

```python
async def skipped_pages(
    session: AsyncSession, source: str, *, limit: int, offset: int
) -> tuple[int, list[RecipeImport]]:
    """Le pagine scartate, dalla scaricata per ultima, col loro totale.

    A parità di `fetched_at` (una transazione sola scrive lo stesso istante) decide
    l'indirizzo: senza un secondo ordine stabile, `offset` potrebbe mostrare due volte
    la stessa pagina e mai un'altra.
    """
    where = (RecipeImport.source == source, RecipeImport.state == ImportState.SKIPPED)
    total = (
        await session.execute(select(func.count()).select_from(RecipeImport).where(*where))
    ).scalar_one()
    rows = await session.execute(
        select(RecipeImport)
        .where(*where)
        .order_by(RecipeImport.fetched_at.desc(), RecipeImport.url)
        .limit(limit)
        .offset(offset)
    )
    return total, list(rows.scalars())
```

- [ ] **Step 4: Gli schemi**

In `backend/app/schemas/recipe_import.py`, in fondo al file, aggiungi:

```python
# Perché una pagina è scartata, in un codice (spec 2026-10-09-scartate-in-coda §3.1): i
# valori di `SkipCause` in `app/services/recipe_import/materialize.py`. Le parole le
# scrive la schermata.
SkipCauseName = Literal["unreadable", "all_ignored", "non_food", "other"]


class SkippedPageOut(BaseModel):
    id: uuid.UUID
    url: str
    # il titolo della ricetta; None per una pagina illeggibile, che non ne ha
    title: str | None
    cause: SkipCauseName
    non_food_name: str | None
    # falso per una pagina illeggibile: rimetterla in coda non cambierebbe niente
    requeueable: bool
    # le cotture registrate che aspettano nel `payload` la ricetta di questa pagina
    waiting_cooking_events: int


class SkippedPagesOut(BaseModel):
    total: int
    pages: list[SkippedPageOut]


class RequeueOut(BaseModel):
    """Com'è finita la pagina rimessa in coda: entrata, di nuovo scartata, o in attesa
    di termini ancora da decidere."""

    outcome: Literal["imported", "skipped", "waiting"]
    title: str | None
    url: str
    recipe_id: uuid.UUID | None
    cooking_relinked: int
    cause: SkipCauseName | None
    non_food_name: str | None
    waiting_terms: list[str]
```

- [ ] **Step 5: Le rotte**

In `backend/app/api/imports.py`:

1. Nell'import da `app.db.models.recipe_import` aggiungi `RecipeImport`:
   ```python
   from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, RecipeImport, TermDecision
   ```
2. Nell'import da `app.repositories.imports` aggiungi `get_page` e `skipped_pages` (in ordine alfabetico con gli altri).
3. Nell'import da `app.schemas.recipe_import` aggiungi `RequeueOut`, `SkippedPageOut`, `SkippedPagesOut`.
4. Sostituisci
   ```python
   from app.services.recipe_import.materialize import materialize_ready
   ```
   con
   ```python
   from app.services.recipe_import.materialize import (
       COOKING_EVENTS_KEY,
       explain_skip,
       materialize_ready,
   )
   from app.services.recipe_import.requeue import NotRequeueable, requeue_page
   ```
5. In fondo al file aggiungi:

```python
def _page_title(page: RecipeImport) -> str | None:
    return str(page.payload.get("title") or "").strip() or None


@router.get("/pages/skipped", response_model=SkippedPagesOut)
async def read_skipped_pages(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> SkippedPagesOut:
    """Le pagine scaricate che non sono diventate ricette, col perché in un codice.

    `skipped_reason` fino a qui non affiorava da nessuna parte: chi voleva sapere perché
    una ricetta mancava doveva aprire il database (Parte X). Il codice e non il motivo
    scritto, che per una pagina illeggibile è una frase del lettore di HTML.
    """
    total, pages = await skipped_pages(session, GIALLOZAFFERANO, limit=limit, offset=offset)
    out = []
    for page in pages:
        explained = explain_skip(page.payload, page.skipped_reason)
        out.append(
            SkippedPageOut(
                id=page.id, url=page.url, title=_page_title(page),
                cause=explained.cause.value, non_food_name=explained.non_food_name,
                requeueable=explained.requeueable,
                waiting_cooking_events=len(page.payload.get(COOKING_EVENTS_KEY) or []),
            )
        )
    return SkippedPagesOut(total=total, pages=out)


@router.post("/pages/{page_id:uuid}/requeue", response_model=RequeueOut)
async def requeue_skipped(
    page_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> RequeueOut:
    """Rimette in coda una pagina scartata, la materializza subito, e dice com'è finita.

    La risposta si costruisce prima del `commit`: dopo, la pagina potrebbe essere
    scaduta nella sessione, e rileggerla in un contesto asincrono fallirebbe.
    """
    page = await get_page(session, page_id)
    if page is None or page.source != GIALLOZAFFERANO:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pagina inesistente")
    try:
        done = await requeue_page(session, page)
    except NotRequeueable as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, exc.message) from exc
    out = RequeueOut(
        outcome=done.outcome, title=_page_title(page), url=page.url,
        recipe_id=done.recipe_id, cooking_relinked=done.cooking_relinked,
        cause=done.skip.cause.value if done.skip else None,
        non_food_name=done.skip.non_food_name if done.skip else None,
        waiting_terms=done.waiting_terms,
    )
    await session.commit()
    return out
```

- [ ] **Step 6: Il test passa, e il resto della coda non si è mosso**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/api/test_imports_skipped.py tests/api/test_imports.py tests/api/test_imports_undo.py tests/api/test_imports_term.py tests/api/test_imports_decide.py tests/api/test_imports_decided_list.py`
Expected: PASS, 10 test nuovi e quelli di prima.

- [ ] **Step 7: Commit**

```bash
git add backend/app/repositories/imports.py backend/app/schemas/recipe_import.py backend/app/api/imports.py backend/tests/api/test_imports_skipped.py
git commit -m "api: l'elenco delle pagine scartate col perché, e la rimessa in coda con l'esito"
```

---

### Task 4: Le parole delle scartate, e le chiamate

**Files:**
- Modify: `frontend/src/domain/types.ts`
- Modify: `frontend/src/features/recipe-import/api.ts`
- Create: `frontend/src/features/recipe-import/skippedWords.ts`
- Test: `frontend/src/features/recipe-import/skippedWords.test.ts` (nuovo)

**Interfaces:**
- Consumes: le rotte del Task 3.
- Produces:
  - in `types.ts`: `SkipCause`, `SkippedPage`, `SkippedPages`, `RequeueResult`;
  - in `recipe-import/api.ts`: `SKIPPED_PAGE_SIZE = 50`, `SKIPPED_PAGES_KEY = ["import-status", "skipped-pages"] as const`, `fetchSkippedPages(offset: number): Promise<SkippedPages>`, `requeuePage(pageId: string): Promise<RequeueResult>`;
  - in `skippedWords.ts`: `skippedTitle(count: number): string`, `skipReasonText(cause: SkipCause, nonFoodName: string | null): string`, `cookingWaitingText(count: number): string`, `requeueResultMessage(result: RequeueResult): string`. Il Task 5 li usa.

- [ ] **Step 1: I tipi e le chiamate**

Leggi `frontend/src/domain/types.ts` com'è sul ramo e, subito dopo l'interfaccia `UndoResult` (finisce con `ingredient_kept_for_adopted: boolean;\n}`), aggiungi:

```ts
/** Perché una pagina dell'import è scartata, in un codice: le parole le scrive la
 * schermata (`features/recipe-import/skippedWords.ts`). Spec 2026-10-09-scartate-in-coda
 * §3.1. */
export type SkipCause = "unreadable" | "all_ignored" | "non_food" | "other";

export interface SkippedPage {
  id: string;
  url: string;
  /** Il titolo della ricetta; `null` per una pagina illeggibile, che non ne ha. */
  title: string | null;
  cause: SkipCause;
  /** La voce non alimentare, solo per `non_food` (e non sempre: un nome lunghissimo può
   * essere stato tagliato via dal limite del motivo). */
  non_food_name: string | null;
  /** Se «Rimetti in coda» può cambiare qualcosa: falso per una pagina illeggibile. */
  requeueable: boolean;
  /** Le cotture registrate che aspettano la ricetta di questa pagina. */
  waiting_cooking_events: number;
}

export interface SkippedPages {
  total: number;
  pages: SkippedPage[];
}

/** Com'è finita una pagina rimessa in coda. `recipe_id` solo se è entrata; `cause` e
 * `non_food_name` solo se è di nuovo scartata; `waiting_terms` solo se aspetta. */
export interface RequeueResult {
  outcome: "imported" | "skipped" | "waiting";
  title: string | null;
  url: string;
  recipe_id: string | null;
  cooking_relinked: number;
  cause: SkipCause | null;
  non_food_name: string | null;
  waiting_terms: string[];
}
```

In `frontend/src/features/recipe-import/api.ts`, aggiungi `RequeueResult` e `SkippedPages` all'import da `"../../domain/types"` (in ordine alfabetico con gli altri), e in fondo al file:

```ts
/** Quante pagine scartate per volta: il default della rotta. */
export const SKIPPED_PAGE_SIZE = 50;

/** La chiave dell'elenco delle scartate. Sotto `import-status` di proposito: decidere un
 * termine, chiedere all'AI e annullare possono scartare una pagina, e tutte e tre le
 * mutazioni della coda invalidano già `["import-status"]` — così rileggono anche questo
 * elenco senza che il loro codice lo sappia. */
export const SKIPPED_PAGES_KEY = ["import-status", "skipped-pages"] as const;

/** Le pagine scaricate che non sono diventate ricette, col perché, a partire da `offset`. */
export function fetchSkippedPages(offset: number) {
  return apiFetch<SkippedPages>(
    `/imports/pages/skipped?limit=${SKIPPED_PAGE_SIZE}&offset=${offset}`
  );
}

/** Rimette in coda una pagina scartata. Il backend la materializza subito e risponde com'è
 * finita: entrata, di nuovo scartata, o in attesa di termini da decidere. */
export function requeuePage(pageId: string) {
  return apiFetch<RequeueResult>(`/imports/pages/${encodeURIComponent(pageId)}/requeue`, {
    method: "POST",
  });
}
```

- [ ] **Step 2: Il test che fallisce**

Crea `frontend/src/features/recipe-import/skippedWords.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { RequeueResult, SkipCause } from "../../domain/types";
import {
  cookingWaitingText,
  requeueResultMessage,
  skipReasonText,
  skippedTitle,
} from "./skippedWords";

const STRADA_NON_ALIMENTARE =
  "Rendilo un alimento in Anagrafica, o annulla la decisione che lo ha scelto; poi rimettila in coda.";

describe("skipReasonText", () => {
  const casi: [SkipCause, string | null, string][] = [
    [
      "non_food",
      "Panna",
      `Fra gli ingredienti c'è «Panna», che non è un alimento. ${STRADA_NON_ALIMENTARE}`,
    ],
    ["non_food", null, `Uno degli ingredienti non è un alimento. ${STRADA_NON_ALIMENTARE}`],
    [
      "all_ignored",
      null,
      "Tutti i suoi ingredienti sono ignorati, e una ricetta senza ingredienti non entra nel ricettario. Annulla la decisione su uno di loro; poi rimettila in coda.",
    ],
    [
      "unreadable",
      null,
      "Sul sito la pagina non aveva una ricetta leggibile: rimetterla in coda non cambierebbe niente.",
    ],
    ["other", null, "Non è entrata nel ricettario durante l'import."],
  ];
  it.each(casi)("%s (%s)", (causa, nome, frase) => {
    expect(skipReasonText(causa, nome)).toBe(frase);
  });
});

describe("cookingWaitingText", () => {
  it.each([
    [1, "1 cottura registrata aspetta questa ricetta."],
    [3, "3 cotture registrate aspettano questa ricetta."],
  ])("%i", (quante, frase) => {
    expect(cookingWaitingText(quante)).toBe(frase);
  });
});

it("il titolo della sezione porta il numero", () => {
  expect(skippedTitle(7)).toBe("Scartate (7)");
});

describe("requeueResultMessage", () => {
  const BASE: RequeueResult = {
    outcome: "imported",
    title: "Torta alla panna",
    url: "https://esempio.invalid/torta.html",
    recipe_id: "r-torta",
    cooking_relinked: 0,
    cause: null,
    non_food_name: null,
    waiting_terms: [],
  };

  it.each([
    [0, "«Torta alla panna» è entrata nel ricettario."],
    [1, "«Torta alla panna» è entrata nel ricettario. Ha ritrovato 1 cottura."],
    [2, "«Torta alla panna» è entrata nel ricettario. Ha ritrovato 2 cotture."],
  ])("entrata, con %i cotture ritrovate", (cotture, frase) => {
    expect(requeueResultMessage({ ...BASE, cooking_relinked: cotture })).toBe(frase);
  });

  it.each([
    [["Acqua"], "«Torta alla panna» è tornata in coda: aspetta la decisione su «Acqua»."],
    [["Acqua", "Sale"], "«Torta alla panna» è tornata in coda: aspetta le decisioni su «Acqua» e «Sale»."],
    [
      ["Acqua", "Sale", "Pepe"],
      "«Torta alla panna» è tornata in coda: aspetta le decisioni su «Acqua», «Sale» e «Pepe».",
    ],
    [
      ["Acqua", "Sale", "Pepe", "Olio"],
      "«Torta alla panna» è tornata in coda: aspetta le decisioni su «Acqua», «Sale», «Pepe» e un altro.",
    ],
    [
      ["Acqua", "Sale", "Pepe", "Olio", "Aglio"],
      "«Torta alla panna» è tornata in coda: aspetta le decisioni su «Acqua», «Sale», «Pepe» e altri 2.",
    ],
  ])("in coda, in attesa di %j", (termini, frase) => {
    expect(
      requeueResultMessage({ ...BASE, outcome: "waiting", recipe_id: null, waiting_terms: termini })
    ).toBe(frase);
  });

  it("in coda senza nomi da dire", () => {
    expect(requeueResultMessage({ ...BASE, outcome: "waiting", recipe_id: null })).toBe(
      "«Torta alla panna» è tornata in coda: aspetta che i suoi ingredienti siano decisi."
    );
  });

  const ancoraScartata: [SkipCause, string | null, string][] = [
    ["non_food", "Panna", "«Torta alla panna» è ancora scartata: «Panna» non è un alimento."],
    ["non_food", null, "«Torta alla panna» è ancora scartata: un ingrediente non è un alimento."],
    ["all_ignored", null, "«Torta alla panna» è ancora scartata: tutti i suoi ingredienti sono ignorati."],
    ["other", null, "«Torta alla panna» è ancora scartata."],
  ];
  it.each(ancoraScartata)("ancora scartata: %s (%s)", (causa, nome, frase) => {
    expect(
      requeueResultMessage({
        ...BASE,
        outcome: "skipped",
        recipe_id: null,
        cause: causa,
        non_food_name: nome,
      })
    ).toBe(frase);
  });

  it("senza titolo, nomina la pagina col suo indirizzo", () => {
    expect(requeueResultMessage({ ...BASE, title: null })).toBe(
      "«https://esempio.invalid/torta.html» è entrata nel ricettario."
    );
  });
});
```

- [ ] **Step 3: Il test fallisce**

Run (da `<worktree>/frontend`): `npx vitest run src/features/recipe-import/skippedWords.test.ts`
Expected: FAIL, il modulo `./skippedWords` non esiste.

- [ ] **Step 4: L'implementazione**

Crea `frontend/src/features/recipe-import/skippedWords.ts`:

```ts
import type { RequeueResult, SkipCause } from "../../domain/types";

// Le parole delle pagine scartate (spec 2026-10-09-scartate-in-coda §4). Funzioni pure in
// un file loro: si provano frase per frase senza montare la schermata, e la schermata non
// decide niente — traduce i codici che il backend ha già deciso.

export function skippedTitle(count: number): string {
  return `Scartate (${count})`;
}

// la strada, scritta nella riga e non solo nell'avviso: la riga resta, l'avviso no
const NON_FOOD_WAY =
  "Rendilo un alimento in Anagrafica, o annulla la decisione che lo ha scelto; poi rimettila in coda.";

/** Il perché di una scartata, con la strada per correggerlo dove ce n'è una. */
export function skipReasonText(cause: SkipCause, nonFoodName: string | null): string {
  switch (cause) {
    case "non_food":
      return nonFoodName
        ? `Fra gli ingredienti c'è «${nonFoodName}», che non è un alimento. ${NON_FOOD_WAY}`
        : `Uno degli ingredienti non è un alimento. ${NON_FOOD_WAY}`;
    case "all_ignored":
      return "Tutti i suoi ingredienti sono ignorati, e una ricetta senza ingredienti non entra nel ricettario. Annulla la decisione su uno di loro; poi rimettila in coda.";
    case "unreadable":
      return "Sul sito la pagina non aveva una ricetta leggibile: rimetterla in coda non cambierebbe niente.";
    case "other":
      return "Non è entrata nel ricettario durante l'import.";
  }
}

export function cookingWaitingText(count: number): string {
  return count === 1
    ? "1 cottura registrata aspetta questa ricetta."
    : `${count} cotture registrate aspettano questa ricetta.`;
}

/** «A», «A» e «B», «A», «B» e «C». */
function quotedList(names: string[]): string {
  const quoted = names.map((name) => `«${name}»`);
  if (quoted.length === 1) return quoted[0];
  return `${quoted.slice(0, -1).join(", ")} e ${quoted[quoted.length - 1]}`;
}

function waitingPart(terms: string[]): string {
  if (terms.length === 0) return "aspetta che i suoi ingredienti siano decisi";
  if (terms.length === 1) return `aspetta la decisione su «${terms[0]}»`;
  if (terms.length <= 3) return `aspetta le decisioni su ${quotedList(terms)}`;
  const shown = terms
    .slice(0, 3)
    .map((name) => `«${name}»`)
    .join(", ");
  const rest = terms.length - 3;
  return `aspetta le decisioni su ${shown} e ${rest === 1 ? "un altro" : `altri ${rest}`}`;
}

function stillSkippedPart(cause: SkipCause | null, nonFoodName: string | null): string {
  if (cause === "non_food")
    return nonFoodName
      ? `: «${nonFoodName}» non è un alimento`
      : ": un ingrediente non è un alimento";
  if (cause === "all_ignored") return ": tutti i suoi ingredienti sono ignorati";
  return "";
}

/** L'avviso dopo «Rimetti in coda»: com'è finita quella pagina. Corto quando non è
 * riuscita: la strada per correggere resta scritta nella sua riga. */
export function requeueResultMessage(result: RequeueResult): string {
  const name = `«${result.title ?? result.url}»`;
  if (result.outcome === "imported") {
    const count = result.cooking_relinked;
    const cooking =
      count === 0 ? "" : count === 1 ? " Ha ritrovato 1 cottura." : ` Ha ritrovato ${count} cotture.`;
    return `${name} è entrata nel ricettario.${cooking}`;
  }
  if (result.outcome === "waiting")
    return `${name} è tornata in coda: ${waitingPart(result.waiting_terms)}.`;
  return `${name} è ancora scartata${stillSkippedPart(result.cause, result.non_food_name)}.`;
}
```

- [ ] **Step 5: Il test passa, e i tipi tornano**

Run: `npx vitest run src/features/recipe-import/skippedWords.test.ts && npm run typecheck && npm run lint`
Expected: PASS (22 test); typecheck e lint puliti.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/domain/types.ts frontend/src/features/recipe-import/api.ts frontend/src/features/recipe-import/skippedWords.ts frontend/src/features/recipe-import/skippedWords.test.ts
git commit -m "coda d'import: le parole delle pagine scartate e le due chiamate"
```

---

### Task 5: La sezione «Scartate (N)» nella coda

**Files:**
- Modify: `frontend/src/components/ui/icons.ts`
- Create: `frontend/src/features/recipe-import/SkippedPages.tsx`
- Test: `frontend/src/features/recipe-import/SkippedPages.test.tsx` (nuovo)
- Modify: `frontend/src/features/recipe-import/ImportQueueScreen.tsx`, `ImportQueueScreen.test.tsx`

**Interfaces:**
- Consumes: `fetchSkippedPages`, `requeuePage`, `SKIPPED_PAGES_KEY` (`api.ts`), le quattro funzioni di `skippedWords.ts` (Task 4); `Button` (con `busy`, `accessibleName`, `className`), `buttonClasses`, `Alert`, `useNotice`.
- Produces: `SkippedPages({ count }: { count: number })`, montato da `ImportQueueScreen`.

- [ ] **Step 1: Le icone**

In `frontend/src/components/ui/icons.ts`, subito dopo la riga
```ts
export { IconShoppingCartPlus, IconCalendarEvent } from "@tabler/icons-react";
```
(com'è sul ramo: se è stata allungata, subito dopo di lei), aggiungi — **queste due righe esatte, identiche a quelle del piano S15** (`docs/superpowers/plans/2026-10-08-s15-reparti-collassabili.md`, Task 3), perché al merge git le fonda invece di farne due export; il commento parla dei reparti perché è il testo di S15, e vale anche qui:
```ts
// dispensa, i reparti che si aprono e si chiudono (S15): giù aperto, a destra chiuso
export { IconChevronDown, IconChevronRight } from "@tabler/icons-react";
```
Se sul ramo `icons.ts` esporta già i due chevron, non aggiungere niente.

- [ ] **Step 2: Il test che fallisce**

Crea `frontend/src/features/recipe-import/SkippedPages.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { SkippedPages } from "./SkippedPages";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import type { RequeueResult, SkippedPage } from "../../domain/types";

const ILLEGGIBILE: SkippedPage = {
  id: "p-vuota",
  url: "https://esempio.invalid/vuota.html",
  title: null,
  cause: "unreadable",
  non_food_name: null,
  requeueable: false,
  waiting_cooking_events: 0,
};
const TORTA: SkippedPage = {
  id: "p-torta",
  url: "https://esempio.invalid/torta.html",
  title: "Torta alla panna",
  cause: "non_food",
  non_food_name: "Panna",
  requeueable: true,
  waiting_cooking_events: 2,
};
const ACQUA: SkippedPage = {
  id: "p-acqua",
  url: "https://esempio.invalid/acqua.html",
  title: "Acqua calda",
  cause: "all_ignored",
  non_food_name: null,
  requeueable: true,
  waiting_cooking_events: 0,
};
const ENTRATA: RequeueResult = {
  outcome: "imported",
  title: "Torta alla panna",
  url: TORTA.url,
  recipe_id: "r-torta",
  cooking_relinked: 2,
  cause: null,
  non_food_name: null,
  waiting_terms: [],
};

// Il predicato vero di App.tsx, non un `retry: false` di comodo (CLAUDE.md, prima
// lezione). `retryDelay: 0` solo dove si prova un errore: i tentativi restano tre.
function clientVero(retryDelay?: number) {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: defaultQueryRetryPredicate,
        ...(retryDelay === undefined ? {} : { retryDelay }),
      },
    },
  });
}

function renderSkipped(count = 3, client = clientVero()) {
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/ricette/importa"]}>
        <NoticeProvider>
          <Routes>
            <Route path="/ricette/importa" element={<SkippedPages count={count} />} />
            <Route path="/ricette/:id" element={<p>La ricetta aperta</p>} />
          </Routes>
        </NoticeProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

type Risposta = [unknown, number] | "in volo";

/** Un fetch che risponde in base al percorso e al metodo; «in volo» non risponde mai. */
function stubFetch(route: (path: string, method: string) => Risposta) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const risposta = route(String(url), init?.method ?? "GET");
    if (risposta === "in volo") return new Promise<Response>(() => {});
    const [body, status] = risposta;
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

/** L'elenco delle tre pagine in una volta, e la rimessa come la si chiede. */
function stubElenco(rimessa: Risposta = [ENTRATA, 200]) {
  return stubFetch((path, method) => {
    if (path.includes("/requeue") && method === "POST") return rimessa;
    if (path.includes("/imports/pages/skipped"))
      return [{ total: 3, pages: [ILLEGGIBILE, TORTA, ACQUA] }, 200];
    return [{}, 404];
  });
}

async function apri() {
  await userEvent.click(screen.getByRole("button", { name: "Scartate (3)" }));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SkippedPages", () => {
  it("è chiusa di partenza, col numero, e non chiede l'elenco finché non si apre", () => {
    const spy = stubElenco();
    renderSkipped();
    const titolo = screen.getByRole("button", { name: "Scartate (3)" });
    expect(titolo).toHaveAttribute("aria-expanded", "false");
    expect(titolo.closest("h2")).not.toBeNull();
    expect(screen.queryByRole("list")).toBeNull();
    expect(spy).not.toHaveBeenCalled();
  });

  it("con nessuna pagina scartata non c'è", () => {
    stubElenco();
    const { container } = renderSkipped(0);
    expect(container.querySelector("section")).toBeNull();
    expect(screen.queryByRole("button", { name: /^Scartate/ })).toBeNull();
  });

  it("aperta, dice per ogni pagina il nome, il perché e cosa si può fare", async () => {
    stubElenco();
    renderSkipped();
    await apri();
    expect(screen.getByRole("button", { name: "Scartate (3)" })).toHaveAttribute(
      "aria-expanded",
      "true"
    );
    const righe = await screen.findAllByRole("listitem");
    expect(righe).toHaveLength(3);
    const [vuota, torta, acqua] = righe;

    // senza titolo, l'indirizzo; e al posto di «Rimetti in coda», la pagina da aprire
    expect(within(vuota).getByText(ILLEGGIBILE.url)).toBeInTheDocument();
    expect(
      within(vuota).getByText(
        "Sul sito la pagina non aveva una ricetta leggibile: rimetterla in coda non cambierebbe niente."
      )
    ).toBeInTheDocument();
    expect(within(vuota).queryByRole("button")).toBeNull();
    const pagina = within(vuota).getByRole("link", {
      name: `Apri la pagina «${ILLEGGIBILE.url}»`,
    });
    expect(pagina).toHaveAttribute("href", ILLEGGIBILE.url);
    expect(pagina).toHaveAttribute("target", "_blank");

    // il titolo, il perché in parole con la strada, le cotture che aspettano
    expect(within(torta).getByText("Torta alla panna")).toBeInTheDocument();
    expect(
      within(torta).getByText(/^Fra gli ingredienti c'è «Panna», che non è un alimento\./)
    ).toBeInTheDocument();
    expect(
      within(torta).getByText("2 cotture registrate aspettano questa ricetta.")
    ).toBeInTheDocument();
    expect(
      within(torta).getByRole("button", { name: "Rimetti in coda «Torta alla panna»" })
    ).toBeInTheDocument();
    expect(within(acqua).getByText(/^Tutti i suoi ingredienti sono ignorati/)).toBeInTheDocument();
    expect(within(acqua).queryByText(/cottur/)).toBeNull();

    // nessun codice, nessun motivo tecnico
    expect(screen.queryByText(/non_food|all_ignored|unreadable|dd\.gz/)).toBeNull();
  });

  it("rimessa e entrata: l'avviso lo dice, e «Apri» porta alla ricetta", async () => {
    const spy = stubElenco([ENTRATA, 200]);
    renderSkipped();
    await apri();
    await userEvent.click(
      await screen.findByRole("button", { name: "Rimetti in coda «Torta alla panna»" })
    );
    expect(spy).toHaveBeenCalledWith(
      "/api/v1/imports/pages/p-torta/requeue",
      expect.objectContaining({ method: "POST" })
    );
    const avviso = screen.getByRole("status");
    await waitFor(() =>
      expect(avviso).toHaveTextContent(
        "«Torta alla panna» è entrata nel ricettario. Ha ritrovato 2 cotture."
      )
    );
    await userEvent.click(within(avviso).getByRole("button", { name: "Apri" }));
    expect(await screen.findByText("La ricetta aperta")).toBeInTheDocument();
  });

  it("rimessa e ancora scartata: l'avviso dice perché, senza «Apri», e la riga resta", async () => {
    stubElenco([
      {
        ...ENTRATA,
        outcome: "skipped",
        recipe_id: null,
        cooking_relinked: 0,
        cause: "non_food",
        non_food_name: "Panna",
      },
      200,
    ]);
    renderSkipped();
    await apri();
    await userEvent.click(
      await screen.findByRole("button", { name: "Rimetti in coda «Torta alla panna»" })
    );
    const avviso = screen.getByRole("status");
    await waitFor(() =>
      expect(avviso).toHaveTextContent(
        "«Torta alla panna» è ancora scartata: «Panna» non è un alimento."
      )
    );
    expect(within(avviso).queryByRole("button", { name: "Apri" })).toBeNull();
    expect(
      screen.getByRole("button", { name: "Rimetti in coda «Torta alla panna»" })
    ).toBeInTheDocument();
  });

  it.each([
    [
      409,
      { detail: "Questa pagina non è più scartata: l'elenco era vecchio." },
      "Questa pagina non è più scartata: l'elenco era vecchio.",
    ],
    [500, { detail: "errore" }, "Non sono riuscito a rimetterla in coda. Niente è andato perso: riprova."],
  ])("un rifiuto %i si legge nella sezione", async (stato, corpo, frase) => {
    stubElenco([corpo, stato]);
    renderSkipped();
    await apri();
    await userEvent.click(
      await screen.findByRole("button", { name: "Rimetti in coda «Torta alla panna»" })
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(frase);
  });

  it("«Mostra altre» porta le pagine che mancano, e poi sparisce", async () => {
    const spy = stubFetch((path) => {
      if (path.includes("offset=2")) return [{ total: 3, pages: [ACQUA] }, 200];
      if (path.includes("/imports/pages/skipped"))
        return [{ total: 3, pages: [ILLEGGIBILE, TORTA] }, 200];
      return [{}, 404];
    });
    renderSkipped();
    await apri();
    expect(await screen.findAllByRole("listitem")).toHaveLength(2);
    expect(spy).toHaveBeenCalledWith(
      "/api/v1/imports/pages/skipped?limit=50&offset=0",
      expect.anything()
    );
    await userEvent.click(screen.getByRole("button", { name: "Mostra altre" }));
    await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(3));
    expect(screen.queryByRole("button", { name: "Mostra altre" })).toBeNull();
  });

  it("se l'elenco non arriva lo dice, e «Riprova» lo richiede", async () => {
    let tentativi = 0;
    stubFetch((path) => {
      if (path.includes("/imports/pages/skipped")) {
        tentativi += 1;
        // i tre tentativi del predicato falliscono; quello di «Riprova» no
        return tentativi <= 3 ? [{ detail: "guasto" }, 500] : [{ total: 3, pages: [TORTA] }, 200];
      }
      return [{}, 404];
    });
    renderSkipped(3, clientVero(0));
    await apri();
    expect(
      await screen.findByText("Non sono riuscito a leggere le pagine scartate.")
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Riprova" }));
    expect(await screen.findByText("Torta alla panna")).toBeInTheDocument();
  });

  it("mentre una rimessa è in volo, «Rimetti in coda» è spento e tiene il fuoco", async () => {
    stubElenco("in volo");
    renderSkipped();
    await apri();
    const tasto = await screen.findByRole("button", { name: "Rimetti in coda «Torta alla panna»" });
    await userEvent.click(tasto);
    await waitFor(() => expect(tasto).toHaveAttribute("aria-disabled", "true"));
    expect(tasto).toHaveFocus();
  });
});
```

- [ ] **Step 3: Il test fallisce**

Run: `npx vitest run src/features/recipe-import/SkippedPages.test.tsx`
Expected: FAIL, il modulo `./SkippedPages` non esiste.

- [ ] **Step 4: Il componente**

Crea `frontend/src/features/recipe-import/SkippedPages.tsx`:

```tsx
import { useId, useState } from "react";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../../api/client";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { IconChevronDown, IconChevronRight } from "../../components/ui/icons";
import { useNotice } from "../../components/ui/noticeContext";
import type { SkippedPage } from "../../domain/types";
import { fetchSkippedPages, requeuePage, SKIPPED_PAGES_KEY } from "./api";
import {
  cookingWaitingText,
  requeueResultMessage,
  skipReasonText,
  skippedTitle,
} from "./skippedWords";

/** Un 4xx porta nel `detail` il perché vero («non è più scartata», «non aveva una ricetta
 * leggibile»): si mostra com'è, come fa la coda con le decisioni. Un guasto no. */
function requeueErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
    return error.message;
  }
  return "Non sono riuscito a rimetterla in coda. Niente è andato perso: riprova.";
}

function SkippedPageRow({
  page,
  pending,
  onRequeue,
}: {
  page: SkippedPage;
  pending: boolean;
  onRequeue: () => void;
}) {
  // una pagina illeggibile non ha titolo: la si nomina col suo indirizzo
  const name = page.title ?? page.url;
  return (
    <li className="flex items-center justify-between gap-3 border-b border-line py-3 last:border-b-0">
      <div className="min-w-0">
        <p className="truncate font-medium">{name}</p>
        <p className="pt-0.5 text-xs text-ink-soft">
          {skipReasonText(page.cause, page.non_food_name)}
        </p>
        {page.waiting_cooking_events > 0 && (
          <p className="pt-0.5 text-xs text-ink-soft">
            {cookingWaitingText(page.waiting_cooking_events)}
          </p>
        )}
      </div>
      {page.requeueable ? (
        // il nome accessibile porta la pagina: una riga per pagina, e senza il nome chi
        // ascolta sente N «Rimetti in coda» indistinguibili
        <Button
          variant="ghost"
          busy={pending}
          onClick={onRequeue}
          accessibleName={`Rimetti in coda «${name}»`}
          className="shrink-0 whitespace-nowrap"
        >
          Rimetti in coda
        </Button>
      ) : (
        // spec §2: rimetterla non può riuscire, quindi la strada è la
        // pagina originale, da leggere sul sito e scrivere a mano
        <a
          href={page.url}
          target="_blank"
          rel="noreferrer"
          aria-label={`Apri la pagina «${name}»`}
          className={`${buttonClasses("ghost")} shrink-0 whitespace-nowrap`}
        >
          Apri la pagina
        </a>
      )}
    </li>
  );
}

/** Le pagine scaricate che non sono diventate ricette (spec 2026-10-09-scartate-in-coda).
 *
 * Chiusa di partenza: la coda resta la cosa da fare, e le scartate sono un'eccezione da
 * guardare quando serve. Il numero arriva dallo stato che la coda legge già; l'elenco si
 * chiede solo aprendo, 50 per volta. «Rimetti in coda» manda la pagina per la strada
 * normale e l'avviso dice com'è finita; la riga dice sempre la strada per correggere la
 * causa, perché resta anche quando l'avviso se n'è andato.
 */
export function SkippedPages({ count }: { count: number }) {
  const [open, setOpen] = useState(false);
  const [requeueError, setRequeueError] = useState<string | null>(null);
  const contentId = useId();
  const queryClient = useQueryClient();
  const notice = useNotice();
  const navigate = useNavigate();

  const list = useInfiniteQuery({
    queryKey: SKIPPED_PAGES_KEY,
    initialPageParam: 0,
    queryFn: ({ pageParam }) => fetchSkippedPages(pageParam),
    // da dove riparte la pagina dopo: quante ne sono arrivate, finché il totale non è
    // raggiunto; una pagina vuota chiude (l'elenco si è accorciato sotto di noi)
    getNextPageParam: (lastPage, allPages) => {
      const loaded = allPages.reduce((sum, page) => sum + page.pages.length, 0);
      return lastPage.pages.length > 0 && loaded < lastPage.total ? loaded : undefined;
    },
    enabled: open,
  });
  const pages = list.data?.pages.flatMap((page) => page.pages) ?? [];

  const requeue = useMutation({
    mutationFn: (pageId: string) => requeuePage(pageId),
    onMutate: () => setRequeueError(null),
    onSuccess: (result) => {
      const text = requeueResultMessage(result);
      const recipeId = result.outcome === "imported" ? result.recipe_id : null;
      notice(
        recipeId !== null
          ? { text, action: { label: "Apri", onClick: () => navigate(`/ricette/${recipeId}`) } }
          : { text }
      );
      // `["import-status"]` è anche il prefisso di questo elenco (vedi SKIPPED_PAGES_KEY):
      // si rileggono il numero e le righe insieme. La coda e il ricettario sono cambiati
      // anche loro: un termine può essere tornato in attesa, una ricetta è entrata.
      queryClient.invalidateQueries({ queryKey: ["import-status"] });
      queryClient.invalidateQueries({ queryKey: ["import-terms"] });
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
    },
    onError: (error) => setRequeueError(requeueErrorMessage(error)),
  });

  if (count === 0) return null;

  const Chevron = open ? IconChevronDown : IconChevronRight;
  return (
    <section aria-label={skippedTitle(count)} className="pt-6">
      {/* tutto il titolo è il pulsante, dentro l'`h2` (lo schema ARIA dell'accordion, come
          i reparti di S15); mai spento, quindi un `<button>` scritto a mano */}
      <h2 className="text-sm font-medium text-ink-soft">
        <button
          type="button"
          aria-expanded={open}
          aria-controls={contentId}
          onClick={() => setOpen((value) => !value)}
          className="flex min-h-11 w-full items-center gap-2 text-left"
        >
          <Chevron aria-hidden="true" className="size-4 shrink-0 text-ink-faint" stroke={1.8} />
          {skippedTitle(count)}
        </button>
      </h2>
      <div id={contentId} hidden={!open}>
        <p className="text-xs text-ink-faint">
          Le pagine scaricate che non sono diventate ricette, ciascuna col suo perché.
          Rimessa in coda, una pagina entra nel ricettario se la causa è stata corretta; se
          no torna qui.
        </p>
        {requeueError && <Alert className="pt-2">{requeueError}</Alert>}
        {open && list.isPending && (
          <p className="pt-2 text-sm text-ink-soft">Carico le pagine scartate…</p>
        )}
        {list.isError && (
          <div className="flex flex-wrap items-center gap-2 pt-2">
            <Alert>Non sono riuscito a leggere le pagine scartate.</Alert>
            <Button busy={list.isFetching} onClick={() => void list.refetch()}>
              Riprova
            </Button>
          </div>
        )}
        {pages.length > 0 && (
          <ul className="pt-2">
            {pages.map((page) => (
              <SkippedPageRow
                key={page.id}
                page={page}
                pending={requeue.isPending}
                onRequeue={() => requeue.mutate(page.id)}
              />
            ))}
          </ul>
        )}
        {list.hasNextPage && (
          <Button
            busy={list.isFetchingNextPage}
            onClick={() => void list.fetchNextPage()}
            className="mt-2"
          >
            Mostra altre
          </Button>
        )}
      </div>
    </section>
  );
}
```

Note per chi implementa:
- `<section aria-label>` e non `aria-labelledby` verso il pulsante: il nome della regione resta «Scartate (N)» senza dipendere da come uno screen reader compone il nome di un `h2` che contiene un pulsante.
- Se `npm run lint` segnala `react-hooks/exhaustive-deps` o simili sul componente, sistemalo senza cambiare il comportamento; se segnala il `return null` dopo gli hook, non è un errore (gli hook sono tutti prima).
- Se il typecheck si lamenta che `Chevron` non accetta `aria-hidden` o `stroke`, guarda `IconComponent` in `icons.ts`: li accetta tutti e due.

- [ ] **Step 5: Il test passa**

Run: `npx vitest run src/features/recipe-import/SkippedPages.test.tsx`
Expected: PASS (10 test).

- [ ] **Step 6: Il test della coda che fallisce**

Leggi `frontend/src/features/recipe-import/ImportQueueScreen.test.tsx` com'è sul ramo e, in fondo al file, aggiungi:

```tsx
describe("le pagine scartate", () => {
  it("con pagine scartate, in fondo alla coda c'è «Scartate (N)», chiusa", async () => {
    renderQueue({ status: { ...STATO_NORMALE, skipped: 4 } });
    const titolo = await screen.findByRole("button", { name: "Scartate (4)" });
    expect(titolo).toHaveAttribute("aria-expanded", "false");
  });

  it("senza pagine scartate la sezione non c'è", async () => {
    renderQueue();
    // lo stato è arrivato: la riga che lo racconta c'è
    await screen.findByText(/19 ricette scaricate aspettano/);
    expect(screen.queryByRole("button", { name: /^Scartate/ })).toBeNull();
  });
});
```

Run: `npx vitest run src/features/recipe-import/ImportQueueScreen.test.tsx`
Expected: il primo dei due FAIL (nessun pulsante «Scartate (4)»), il secondo passa già.

- [ ] **Step 7: La sezione nella coda**

In `frontend/src/features/recipe-import/ImportQueueScreen.tsx`:

1. Fra gli import, dopo `import { DecidedTermRow } from "./DecidedTermRow";`, aggiungi:
   ```tsx
   import { SkippedPages } from "./SkippedPages";
   ```
2. Subito prima di `</Screen>` (dopo il blocco `{decided.length > 0 && ( <section className="pt-6"> … «Decisioni recenti» … </section> )}`), aggiungi:
   ```tsx
      {/* le pagine scartate, chiuse di partenza (spec 2026-10-09-scartate-in-coda): in
          fondo, perché la coda resta la cosa da fare; il numero è quello che lo stato porta
          già, e senza scartate la sezione non c'è */}
      <SkippedPages count={status?.skipped ?? 0} />
   ```

- [ ] **Step 8: I test passano, e il resto del frontend non si è mosso**

Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde: `N_vitest` + 34 in `N_file` + 2 file; typecheck e lint puliti.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/ui/icons.ts frontend/src/features/recipe-import/SkippedPages.tsx frontend/src/features/recipe-import/SkippedPages.test.tsx frontend/src/features/recipe-import/ImportQueueScreen.tsx frontend/src/features/recipe-import/ImportQueueScreen.test.tsx
git commit -m "coda d'import: la sezione «Scartate (N)», chiusa, col perché di ogni pagina e «Rimetti in coda»"
```

---

### Task 6: Nel browser vero

**Files:**
- Create: `backend/tests/e2e_skipped_pages.py`, `backend/tests/test_e2e_skipped_pages_guard.py`
- Create: `frontend/e2e/scartate.spec.ts`
- Modify: `frontend/e2e/style.spec.ts` (una prova in fondo al file)

**Interfaces:**
- Consumes: tutto quello dei Task 1–5; in `style.spec.ts` le funzioni `testiIlleggibili(page)` e `fermo(page)` che ci sono già; il modello di `backend/tests/e2e_import_review.py` e di `frontend/e2e/import-review.spec.ts`.
- Produces: `N_e2e` + 2 prove (una in un file nuovo).

- [ ] **Step 1: La guardia dell'aiutante, che fallisce**

Crea `backend/tests/test_e2e_skipped_pages_guard.py`:

```python
"""L'aiutante della prova e2e delle pagine scartate non parte fuori dallo stack e2e.

`tests/e2e_skipped_pages.py` scrive e cancella pagine dell'import, ricette, termini e
ingredienti: lanciato nel container di produzione, `clean` cancellerebbe davvero. Il
contrassegno `SPENA_E2E=1` sta solo in `.env.e2e`; qui si prova che senza, il file esce
con errore prima di toccare `app` — cioè prima di aprire una sessione. Un processo a
parte, perché il controllo sta in cima al modulo, al momento dell'import.
"""

import os
import subprocess
import sys
from pathlib import Path

AIUTANTE = Path(__file__).with_name("e2e_skipped_pages.py")


def test_senza_il_contrassegno_e2e_non_parte():
    env = {chiave: valore for chiave, valore in os.environ.items() if chiave != "SPENA_E2E"}

    esito = subprocess.run(
        [sys.executable, str(AIUTANTE), "clean"],
        env=env, capture_output=True, text=True, timeout=30,
    )

    assert esito.returncode != 0
    assert "SPENA_E2E=1" in esito.stderr
    assert esito.stdout == ""
```

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/test_e2e_skipped_pages_guard.py`
Expected: FAIL (il file dell'aiutante non c'è: Python esce con errore, ma `stderr` non contiene `SPENA_E2E=1`).

- [ ] **Step 2: L'aiutante**

Crea `backend/tests/e2e_skipped_pages.py`:

```python
"""Semina, correzione e pulizia per `frontend/e2e/scartate.spec.ts`. Non è un test di pytest.

Le pagine scartate si provano nel browser vero solo se ce ne sono, e lo stack e2e non ne
ha: il seme porta anagrafica e ricette, non pagine dell'import, e nessuna rotta ne
scarica. Questo file le fa nascere **dal codice vero**: una pagina illeggibile con
`store_unparsable` — quel che fa lo scarico davanti a una pagina senza righe — e una
ricetta con una riga non alimentare scartata da `materialize_ready`, che scrive il
motivo come in produzione. `fix` corregge la causa col servizio vero dell'anagrafica,
`recategorize_ingredient`: la correzione che una persona fa dalla scheda
dell'ingrediente.

Si lancia dentro il container del backend, dove `./backend` è montato su `/app`:

    $E2E exec -T backend python tests/e2e_skipped_pages.py seed <etichetta>
    $E2E exec -T backend python tests/e2e_skipped_pages.py fix <id-ingrediente>
    $E2E exec -T backend python tests/e2e_skipped_pages.py clean

`seed` stampa su stdout, in JSON, quel che la prova cerca a video. `clean` toglie pagine,
ricette, termini e ingredienti di questo file, anche quelli di un giro interrotto: si può
rieseguire, e chiamare anche prima di seminare.

Scrive e cancella nel database, quindi **si rifiuta di partire fuori dallo stack e2e**:
vuole `SPENA_E2E=1`, che sta solo in `.env.e2e`.

Non si chiama `test_*.py` apposta: pytest non lo raccoglie.
"""

import os
import sys

if os.environ.get("SPENA_E2E") != "1":
    raise SystemExit(
        "e2e_skipped_pages.py scrive e cancella nel database: gira solo sullo stack "
        "spena-e2e, che porta SPENA_E2E=1 da .env.e2e. Qui manca, e non parto."
    )

import asyncio  # noqa: E402
import json  # noqa: E402
import uuid  # noqa: E402

from sqlalchemy import delete, select  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.db.models.ingredient import Ingredient, IngredientCategory  # noqa: E402
from app.db.models.recipe import Recipe  # noqa: E402
from app.db.models.recipe_import import (  # noqa: E402
    GIALLOZAFFERANO,
    ImportState,
    ImportTerm,
    RecipeImport,
    TermDecision,
)
from app.repositories.imports import store_page, store_unparsable  # noqa: E402
from app.repositories.ingredients import create_ingredient, delete_ingredient_if_unused  # noqa: E402
from app.services.recipe_import.materialize import materialize_ready  # noqa: E402
from app.services.registry import recategorize_ingredient  # noqa: E402

# Il segno che porta ogni nome di questo file, e i prefissi di chiavi e indirizzi: la
# pulizia ritrova tutto da qui, e non tocca niente del seme.
NAME_MARK = "e2e-scartate"
KEY_PREFIX = f"{NAME_MARK}-"
URL_PREFIX = "https://e2e.invalid/scartate/"


async def seed(tag: str) -> dict:
    # Un titolo lungo come quelli veri: a 375px la riga lo tronca, e il tasto resta intero.
    title = (
        "Torta della nonna con crema pasticcera, pinoli tostati e scorza di limone "
        f"({NAME_MARK} {tag})"
    )
    async with SessionLocal() as session:
        farina = await create_ingredient(
            session, name=f"farina {NAME_MARK} {tag}",
            display_name=f"Farina {NAME_MARK} {tag}", category=IngredientCategory.CEREALI,
        )
        # la causa dello scarto: la panna finita per sbaglio fra i prodotti per la casa
        panna = await create_ingredient(
            session, name=f"panna {NAME_MARK} {tag}",
            display_name=f"Panna {NAME_MARK} {tag}", category=IngredientCategory.CASA,
        )
        righe = [
            (f"{KEY_PREFIX}{tag}-farina", f"Farina 00 {NAME_MARK} {tag}", farina.id, "300 g"),
            (f"{KEY_PREFIX}{tag}-panna", f"Panna fresca {NAME_MARK} {tag}", panna.id, "200 ml"),
        ]
        session.add_all([
            ImportTerm(
                source=GIALLOZAFFERANO, term_key=key, display_name=name, occurrences=1,
                decision=TermDecision.MAPPED, ingredient_id=ingredient_id,
                decided_by="human", created_ingredient=False,
            )
            for key, name, ingredient_id, _ in righe
        ])
        await session.flush()
        torta = await store_page(
            session, source=GIALLOZAFFERANO, url=f"{URL_PREFIX}{tag}/torta.html",
            payload={
                "title": title, "instructions": "Cuoci in forno.", "servings": 8,
                "ingredients": [
                    {"key": key, "name": name, "quantity_text": quantity}
                    for key, name, _, quantity in righe
                ],
            },
        )
        unreadable_url = (
            f"{URL_PREFIX}{tag}/una-pagina-senza-ricetta-con-un-indirizzo-lungo-come-quelli-veri.html"
        )
        await store_unparsable(
            session, source=GIALLOZAFFERANO, url=unreadable_url,
            reason="nessuna riga dd.gz-ingredient nella pagina",
        )
        await materialize_ready(session, GIALLOZAFFERANO)
        if torta.state != ImportState.SKIPPED:
            raise SystemExit(f"la semina non ha scartato la torta: {torta.state}")
        await session.commit()
        return {
            "title": title,
            "nonFood": panna.display_name,
            "nonFoodId": str(panna.id),
            "unreadableUrl": unreadable_url,
        }


async def fix(ingredient_id: str) -> dict:
    async with SessionLocal() as session:
        ingredient = await recategorize_ingredient(
            session, uuid.UUID(ingredient_id), IngredientCategory.LATTICINI
        )
        await session.commit()
        return {"fixed": ingredient.display_name, "category": ingredient.category}


async def clean() -> dict:
    async with SessionLocal() as session:
        pages = (
            await session.execute(
                delete(RecipeImport).where(RecipeImport.url.like(f"{URL_PREFIX}%"))
            )
        ).rowcount
        # una cancellazione vera e non l'archivio: sono ricette di prova, e le righe se ne
        # vanno con loro (`cascade`), così gli ingredienti qui sotto tornano liberi
        recipes = list(
            (
                await session.execute(
                    select(Recipe).where(Recipe.source_ref.like(f"{URL_PREFIX}%"))
                )
            ).scalars()
        )
        for recipe in recipes:
            await session.delete(recipe)
        terms = (
            await session.execute(
                delete(ImportTerm).where(ImportTerm.term_key.like(f"{KEY_PREFIX}%"))
            )
        ).rowcount
        await session.flush()
        ids = list(
            (
                await session.execute(
                    select(Ingredient.id).where(Ingredient.name.like(f"%{NAME_MARK}%"))
                )
            ).scalars()
        )
        # `delete_ingredient_if_unused` e non una cancellazione cieca: se qualcosa li usa
        # ancora, lo si dice invece di rompere un vincolo
        kept = [str(i) for i in ids if not await delete_ingredient_if_unused(session, i)]
        await session.commit()
        return {
            "pages": pages, "recipes": len(recipes), "terms": terms,
            "ingredients": len(ids) - len(kept), "kept": kept,
        }


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "seed" and len(sys.argv) == 3:
        print(json.dumps(asyncio.run(seed(sys.argv[2]))))
    elif command == "fix" and len(sys.argv) == 3:
        print(json.dumps(asyncio.run(fix(sys.argv[2]))))
    elif command == "clean":
        print(json.dumps(asyncio.run(clean())))
    else:
        raise SystemExit("uso: e2e_skipped_pages.py seed <etichetta> | fix <id-ingrediente> | clean")


if __name__ == "__main__":
    main()
```

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/test_e2e_skipped_pages_guard.py`
Expected: PASS.

- [ ] **Step 3: La prova sul codice vero**

Crea `frontend/e2e/scartate.spec.ts`:

```ts
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
```

Se il dettaglio della ricetta mostra il titolo in un `h1` con una forma diversa (per esempio con la maiuscola), cerca il titolo com'è a video in `frontend/src/features/cooking/RecipeDetailScreen.tsx` e adatta solo quella riga, scrivendolo nel report.

- [ ] **Step 4: La prova dello stile**

Leggi `frontend/e2e/style.spec.ts` com'è sul ramo e, **in fondo al file**, aggiungi:

```ts
test("le pagine scartate della coda d'import: bersagli da pollice, niente di lato a 375px, leggibili nei due temi", async ({
  page,
}) => {
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  // L'elenco finto: il seme non ha pagine scartate, e qui si misura solo come si vedono.
  // Un indirizzo lungo senza titolo e un titolo lungo con le cotture che aspettano: i due
  // casi che a 375px potrebbero spingere la pagina di lato
  await page.route("**/api/v1/imports/**", (route) => {
    const url = new URL(route.request().url());
    if (url.pathname.endsWith("/imports/pages/skipped"))
      return route.fulfill({
        json: {
          total: 2,
          pages: [
            {
              id: "e2e-vuota",
              url: "https://e2e.invalid/scartate/una-pagina-senza-ricetta-con-un-indirizzo-molto-lungo.html",
              title: null,
              cause: "unreadable",
              non_food_name: null,
              requeueable: false,
              waiting_cooking_events: 0,
            },
            {
              id: "e2e-torta",
              url: "https://e2e.invalid/scartate/torta.html",
              title: "Torta della nonna con crema pasticcera, pinoli tostati e scorza di limone",
              cause: "non_food",
              non_food_name: "Carta forno",
              requeueable: true,
              waiting_cooking_events: 2,
            },
          ],
        },
      });
    if (url.pathname.endsWith("/imports/terms")) return route.fulfill({ json: [] });
    if (url.pathname.endsWith("/imports/status"))
      return route.fulfill({
        json: { fetched: 2, pending_recipes: 0, imported: 0, skipped: 2, pending_terms: 0 },
      });
    return route.fallback();
  });
  await page.goto("/ricette/importa");

  const titolo = page.getByRole("button", { name: "Scartate (2)", exact: true });
  await expect(titolo).toBeVisible();
  expect((await titolo.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await titolo.click();

  for (const bersaglio of [
    page.getByRole("button", { name: /^Rimetti in coda/ }),
    page.getByRole("link", { name: /^Apri la pagina/ }),
  ]) {
    await bersaglio.scrollIntoViewIfNeeded();
    await expect(bersaglio).toBeInViewport({ ratio: 1 });
    expect((await bersaglio.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  }
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
  expect(scrollWidth, "la coda con le scartate scorre di lato").toBeLessThanOrEqual(clientWidth);

  for (const tema of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: tema });
    await fermo(page);
    expect(await testiIlleggibili(page), `scartate aperte, tema ${tema}`).toEqual([]);
  }
  await page.emulateMedia({ colorScheme: "light" });
});
```

Se la prova del contrasto segnala un testo sotto 4,5:1, **non cambiare token**: i colori sono `text-ink-soft` e `text-ink-faint`, gli stessi di «Decisioni recenti»; scrivi nel report quale testo, su quale fondo, in quale tema e con quale rapporto, e segna il task `bloccato` — un colore si decide di giorno.

- [ ] **Step 5: Il tipo dei file**

Run (da `frontend/`): `npm run typecheck && npm run lint`
Expected: puliti. `tsc -b` compila anche gli e2e (`tsconfig.node.json`).

- [ ] **Step 6: Lo stack e l'e2e intera**

Dalla radice di `<worktree>`, con i comandi delle Global Constraints: `cp .env.example .env`, `up -d --build --wait`, il seme `--con-ricette`, poi `(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)`.
Expected: tutti verdi, `N_e2e` + 2 prove in un file in più. Se una prova fallisce e lascia dati nello stack, prima di rieseguire ricrea lo stack da zero (`down -v`, `up`, seme). Alla fine, sempre:

```bash
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
rm .env
```

- [ ] **Step 7: Commit**

```bash
git add backend/tests/e2e_skipped_pages.py backend/tests/test_e2e_skipped_pages_guard.py frontend/e2e/scartate.spec.ts frontend/e2e/style.spec.ts
git commit -m "e2e: le pagine scartate nel browser vero — il perché, la rimessa che non riesce, la correzione e la ricetta che entra — e lo stile a 375px nei due temi"
```

---

### Task 7: I documenti

**Files:**
- Modify: `docs/prossimi-passi.md`
- Modify: `next-steps.md`

Leggi prima i due file com'è sul ramo.

- [ ] **Step 1: `docs/prossimi-passi.md`**

In «Parte X — Piccole cose aperte»:

1. In fondo al punto che comincia con `- **\`skipped_reason\` non affiora da nessuna rotta né da nessuna schermata**` (finisce con «chi vuole sapere perché deve aprire il database.»), nello stesso punto elenco, aggiungi:
   ```markdown
     *(Fatto il <data di oggi>, sul ramo `night/scartate-in-coda`, non ancora in
     produzione: `GET /api/v1/imports/pages/skipped` elenca le scartate col perché in un
     codice — `explain_skip` in `materialize.py`, accanto a chi scrive i motivi — e la coda
     d'import le mostra in «Scartate (N)» con le parole da persona. Spec
     `docs/superpowers/specs/2026-10-09-scartate-in-coda-design.md`.)*
   ```
2. In fondo al punto che comincia con `- **Una pagina \`SKIPPED\` non torna mai in coda, nemmeno dopo aver corretto la causa.**` (finisce con «(deciso il 2026-09-28).»), nello stesso punto elenco, aggiungi:
   ```markdown
     *(Fatto il <data di oggi>, sul ramo `night/scartate-in-coda`, non ancora in
     produzione: «Rimetti in coda» nella sezione «Scartate (N)» della coda d'import
     (`POST /api/v1/imports/pages/{id}/requeue`, `requeue_page` in
     `services/recipe_import/requeue.py`) rimette la pagina `pending`, riallinea i termini,
     la materializza subito e dice com'è finita: entrata (con le cotture del `payload`
     rilegate), di nuovo scartata col motivo, o in attesa dei termini che nomina. Una pagina
     illeggibile non si rimette: si mostra con «Apri la pagina». Piano
     `docs/superpowers/plans/2026-10-09-scartate-in-coda.md`.)*
   ```

Sostituisci `<data di oggi>` con la data vera.

- [ ] **Step 2: `next-steps.md`**

1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte: le pagine scartate a video e rimesse in coda, sul ramo night/scartate-in-coda)_`.
2. Togli la voce di questo piano (ora `in corso`; `grep -n "SKIPPED\|scartate" next-steps.md`) e l'idea `- [idea] P3 · \`skipped_reason\` non affiora da nessuna rotta né schermata [Parte X]`.
3. In cima a «Fatti (recenti)» aggiungi:
   ```markdown
   - [fatto] <data di oggi> · Le pagine scartate dell'import a video e rimesse in coda: «Scartate (N)» chiusa in fondo alla coda, col perché in parole e la strada per ogni pagina, «Rimetti in coda» che materializza subito e dice l'esito (entrata con le cotture ritrovate, ancora scartata, in attesa di termini); chiude anche `skipped_reason` che non affiorava [Parte X] → branch night/scartate-in-coda (da revisionare)
   ```
4. In «Idee» aggiungi:
   ```markdown
   - [idea] P3 · Nelle scartate, un collegamento dalla riga al termine che blocca la pagina (`?termine=<id>`), per annullarlo senza cercarlo fra le «Decisioni recenti», che ne mostrano 50 [Parte X]
   ```
5. In cima a «Da fare a mano (solo Mattia)» aggiungi:
   ```markdown
   - [tbd] P3 · Dopo il deploy delle pagine scartate, al telefono: aprire «Scartate (N)» in «Ingredienti da abbinare», leggere i perché; per quelle con una riga non alimentare, correggere l'ingrediente in Anagrafica (o annullare la decisione) e «Rimetti in coda»; controllare che una ricetta rientrata compaia nel ricettario [Parte X]
   ```
6. Se nella notte sono emerse altre cose da fare fuori da questo piano, aggiungile come `idea` o `tbd` nella sezione giusta, con la voce di `docs/prossimi-passi.md` fra parentesi quadre.

Sostituisci ogni `<…>` con il valore vero.

- [ ] **Step 3: Commit**

```bash
git add docs/prossimi-passi.md next-steps.md
git commit -m "docs: le pagine scartate a video e rimesse in coda, fatte sul ramo"
```

---

### Task 8: La verifica finale, e il report

Niente di nuovo da scrivere oltre al report: si prova tutto, dal worktree, com'è sul ramo.

- [ ] **Step 1: Il backend**

Da `<worktree>/backend`:

```bash
PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Expected: tutto verde, **`N_pytest` + 28** (9 del Task 1, 8 del Task 2, 10 del Task 3, 1 del Task 6). Se il numero differisce, scrivi nel report da dove viene la differenza.

- [ ] **Step 2: Il frontend**

Da `<worktree>/frontend`:

```bash
npx vitest run
npm run typecheck
npx tsc -b --force
npm run lint
npm run build
```

Expected: vitest **`N_vitest` + 34** (22 del Task 4, 10 + 2 del Task 5) in **`N_file` + 2** file, tutto verde; typecheck, lint e build puliti. `npx tsc -b --force` perché `node_modules` è condiviso col checkout principale, e con lui il `tsbuildinfo`: `--force` compila davvero tutto.

- [ ] **Step 3: I grep**

Dalla radice del worktree, i tre `grep` di «Comandi di verifica». Expected: come scritto lì. In più:

```bash
git diff master --stat -- backend/app/services/recipe_import/undo.py backend/app/services/recipe_import/terms.py backend/app/services/recipe_import/manual.py backend/app/services/recipe_import/decide.py frontend/src/features/recipe-import/TermCard.tsx frontend/src/features/recipe-import/DecidedTermRow.tsx
```

Expected: vuoto — l'annullamento, il dizionario, le decisioni e le schede della coda non sono cambiati.

- [ ] **Step 4: L'e2e intera**

Con i comandi delle Global Constraints, su uno stack ricreato da zero (`down -v` prima dell'`up`, se ne era rimasto uno di questo ramo). Expected: tutti verdi, `N_e2e` + 2. Poi `down -v` e `rm .env`, sempre.

- [ ] **Step 5: Il report**

Nel report della notte, `docs/night-reports/<data di oggi>.md` sul ramo: se il file c'è già sul ramo aggiungi una sezione in fondo, altrimenti crealo con un titolo `# Notte del <data di oggi>` (gli altri piani della notte scrivono lo stesso file sui loro rami, che non partono da questo: l'unione la fa la revisione). Per questo piano: il ramo e da dove parte (`master`); i conti veri (vitest, pytest, e2e) contro quelli della Preparazione; le scelte del piano che Mattia può voler rivedere — la materializzazione immediata e i due `sync_terms` (scelta 7), le parole a video (in particolare la strada scritta in ogni riga, scelta 9), l'azione «Apri» dell'avviso, l'ordine dell'elenco —; le due righe di `icons.ts` identiche a quelle di S15 e cosa fare al merge (vedi «Dipendenze»); gli scostamenti dal piano, se ce ne sono (per esempio il test del termine rinato del Task 2, il titolo dell'`h1` del Task 6); e la prova a mano per Mattia di «Dopo il deploy». Niente push, niente merge, niente deploy.

```bash
git add docs/night-reports/
git commit -m "report: la notte delle pagine scartate rimesse in coda"
```

---

## Dopo il deploy (solo Mattia)

Di notte non si fa niente di questo. Nessun comando sulla produzione, nessuna migrazione: le pagine scartate della produzione si rimettono dall'app, una per una, da chi sa se la causa è stata corretta. Dopo il merge e il deploy (che restano di Mattia):

1. **Al telefono, in «Ingredienti da abbinare»:** aprire «Scartate (N)» e leggere i perché. Per le pagine con una riga non alimentare: correggere l'ingrediente in Anagrafica (o annullare in coda la decisione che lo ha scelto), poi «Rimetti in coda» e controllare l'avviso; per le illeggibili, «Apri la pagina» porta al sito.
2. **Nel ricettario:** una ricetta rientrata c'è, e se aveva cotture registrate le ritrova.
