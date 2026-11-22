# La coda dell'import: cercare fra tutte le decisioni, e dalle pagine scartate al termine che le blocca — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** una decisione della coda si ritrova anche quando è più vecchia delle 50 recenti, e una pagina scartata porta al termine che la blocca, per annullarlo senza cercarlo.

**Architecture:**
- **La ricerca.** Una rotta nuova, `GET /api/v1/imports/terms/search?q=…`, cerca fra **tutte** le decisioni: dell'AI, a mano e automatiche. Cerca nel termine e nel nome dell'ingrediente su cui è finito, e risponde con i `TermOut` delle decisioni recenti. Nella coda, sopra «Decisioni recenti», c'è un campo: con un testo, l'elenco diventa quello trovato.
- **Le scartate.** `SkippedPageOut` porta i termini che bloccano la pagina, al più tre, e quanti sono in tutto. Li calcola il server dalle righe del `payload`:
  - per «non alimentare», i termini finiti su un ingrediente non alimentare;
  - per «tutti ignorati», i termini ignorati.

  La riga della scartata mostra «Annulla «x»» per ciascuno, più «e altri n». Il link apre `?termine=<id>`, che la coda legge già.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, pytest su Postgres vero; React 19, TanStack Query 5, Vitest + Testing Library, Playwright.

**Spec:** l'idea P3 «La coda dell'import mostra solo le 50 decisioni più recenti…» di `next-steps.md` [T3 esito del giro, Parte X], e la nota di `docs/prossimi-passi.md` sotto la Parte X: «"Deciso nella coda" porta a una coda che può non mostrare quella decisione». Le scartate sono quelle della spec `docs/superpowers/specs/2026-10-09-scartate-in-coda-design.md` (se il file ha un altro nome, `ls docs/superpowers/specs | grep scartate`). **Decisioni del 2026-11-23**: le trovi sotto, in «Decisioni prese».

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/coda-decisioni`, ramo `night/coda-decisioni`, creato da `master`. Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì, mai dalla radice del checkout principale. **Nessun push, nessun merge, nessun deploy. Mai `git stash`. Niente letture o scritture sulla produzione, e mai il `.env` del checkout principale. Nessuna chiamata vera all'AI.**
- **Se nella stessa notte gira `2026-11-22-tempi-ai.md`**: tocca anche lui `backend/app/api/imports.py`, ma solo `decide_with_ai`. Questo piano aggiunge una rotta e cambia `read_skipped_pages`. Restano rami separati; scrivi nel report se il merge dovrà cucire.
- **Il frontend non decide** quali termini bloccano una pagina: lo dice il server. Non ricalcola nemmeno quali decisioni combaciano col testo.
- **Mai un vicolo cieco**:
  - la ricerca che non risponde lascia in vista le decisioni recenti;
  - una scartata senza termini da mostrare tiene la frase di oggi con la sua strada.
- Le parole a video **si copiano esatte** da questo piano (fra «»). Gli identificatori in inglese, i commenti in italiano.
- **Il type check è `npm run typecheck`**, mai `tsc --noEmit`. Controlli del frontend, da `<worktree>/frontend`: `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- **Il carico sulla macchina**: al massimo 6 thread e 8 GB (Mattia, 2026-11-22). Le suite intere girano dentro `systemd-run --user --scope -p MemoryMax=8G -p CPUQuota=600% …`, mai due insieme. Vitest gira con `--maxWorkers=4`, pytest senza parallelismo.
- **Backend su Postgres vero**: `spena-db-1` (porta 5433), con il database `spena_test_coda_decisioni`. Mai `docker compose up` dal worktree. Si usa il `.venv` del checkout principale. Il comando di pytest, da `<worktree>/backend`:
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_coda_decisioni \
    PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
- **e2e** sullo stack `spena-e2e`, con i comandi delle Global Constraints di `docs/superpowers/plans/2026-11-18-pasti-correzioni.md`:
  - il `.env` si copia da `.env.example` e si cancella alla fine;
  - in ogni comando `-p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml`;
  - il seme con le ricette e le due righe della fixture CIQUAL;
  - alla fine sempre `down -v` e `rm .env`;
  - se lo stack c'è e non l'hai alzato tu, aspetta che sparisca.
- Nessuna dipendenza nuova, nessuna migrazione.
- **I test di oggi si cambiano solo dove il piano lo dice**: nessuno. `GET /imports/terms` con e senza `decided_by` risponde come oggi.

## Review Focus

1. **La ricerca trova anche le decisioni automatiche e quelle più vecchie delle 50 recenti, e mai un termine in coda.** Task 1.
2. **`%` e `_` nel testo sono lettere, non jolly**: «50%» non trova tutto. Task 1.
3. **I termini che bloccano una scartata sono quelli giusti per la sua causa.** «Non alimentare» dà solo i termini finiti su un non alimentare, «tutti ignorati» solo gli ignorati. Al più tre, nell'ordine delle righe della pagina e senza doppioni, con il totale. Un termine tornato in coda dopo lo scarto non compare. Task 3.
4. **Una pagina illeggibile e una con causa `other` hanno l'elenco vuoto**, e la riga resta quella di oggi. Task 3 e Task 4.
5. **«Annulla «x»» porta al termine dentro la stessa schermata**: l'indirizzo diventa `?termine=<id>`, la scheda «Il termine che cercavi» si vede in cima e prende il fuoco. Task 4.

### Preparazione (una volta, prima del Task 1)

- [ ] Il worktree, con `node_modules` collegato e nessun `.env`:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/coda-decisioni -b night/coda-decisioni master
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/coda-decisioni/frontend/node_modules
  ```
- [ ] Il database dei test:
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_coda_decisioni WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_coda_decisioni'
  ```
- [ ] La voce di `next-steps.md` che cita questo piano passa a `in corso` (` → in corso su night/coda-decisioni`), e si committa: `next-steps: la coda cerca fra le decisioni, in corso`.
- [ ] La linea di partenza: pytest e vitest dal worktree, tutto verde. **Annota** i numeri. Se non è verde, fermati e scrivilo nel report.

---

## Decisioni prese

1. **La ricerca è fra tutte le decisioni, automatiche comprese** (Claude, su delega, 2026-11-23). Anche una decisione automatica si annulla (`POST /terms/{id}/undo` non guarda chi ha deciso), e un aggancio automatico sbagliato è proprio quello che non si trova fra le «Decisioni recenti», perché lì le automatiche non ci sono.
2. **Una scartata mostra fino a tre «Annulla «x»» più «e altri n»** (Claude, su delega, 2026-11-23). Vale anche per «tutti ignorati», dove i termini possono essere molti: ne bastano tre per sbloccarla, perché annullarne uno solo basta.
3. **Dove si cerca** (Claude, su delega). Nel nome a video del termine e nel nome e nel nome a video dell'ingrediente, ignorando maiuscole e minuscole (`ILIKE`, `autoescape`). Un ignorato non ha ingrediente: si trova per il termine. Si cerca da 2 caratteri. Si tengono le 50 più recenti, con lo stesso ordine di `decided_terms`: data di decisione (le senza data in fondo), poi nome.
4. **Il testo non ripiega gli accenti** (Claude, su delega): termini e nomi sono già minuscoli e scritti come l'import li ha letti. Una ricerca senza accenti è un'altra idea, se serve.
5. **La chiave della ricerca sta sotto `["import-terms"]`** (`["import-terms", "search", q]`): ogni decisione e ogni annullamento la rileggono, come le decisioni recenti.
6. **Con un testo, l'elenco trovato prende il posto di «Decisioni recenti»** (Claude, su delega, scelta di aspetto). Svuotato il campo, tornano le recenti. Le righe sono le `DecidedTermRow` di oggi, con lo stesso annulla.

## Margine di autonomia

- Liberi: i nomi interni e dei test; il debounce del campo, 250 ms come `RegistryScreen` se ne ha uno, altrimenti 250; dove sta il calcolo dei termini bloccanti, purché sia una funzione pura provata da sola.
- Fissi: la rotta `/imports/terms/search`; `SkippedPageOut.blocking_terms` e `blocking_total`; le parole a video.
- **Fermati** (voce `bloccato` nel report) se per trovare i termini di una pagina servisse leggere qualcosa che il `payload` non ha: oggi ogni riga porta la sua `key`, la stessa che `materialize_ready` usa.

---

### Task 1: la ricerca fra le decisioni, nel backend

**Files:**
- Modify: `backend/app/repositories/imports.py` (`search_decided_terms`, accanto a `decided_terms`)
- Modify: `backend/app/api/imports.py` (`GET /terms/search`, scritta prima di `/terms/{term_id:uuid}`)
- Test: `backend/tests/api/test_imports_decided_list.py`

**Interfaces:**
- Produces:
  - `async def search_decided_terms(session, source: str, q: str, limit: int = 50) -> list[ImportTerm]`;
  - `GET /api/v1/imports/terms/search?q=<testo>&limit=<n>`, con `q` da 2 a 120 caratteri e `limit` al più 50 (default 50). Risponde `list[TermOut]` costruita con `_decided_out`.

- [ ] **Step 1: I test che falliscono**, con gli helper che il file ha già per creare termini decisi:
  - `test_la_ricerca_trova_una_decisione_vecchia`: 55 termini decisi dall'AI, e quello cercato è il più vecchio. `GET /terms?decided_by=ai` non lo ha, mentre `GET /terms/search?q=<il suo nome>` sì.
  - `test_la_ricerca_trova_le_decisioni_automatiche_e_a_mano`: tre termini, uno per autore, tutti col testo «pomod». La ricerca li dà tutti e tre, ciascuno col suo `decided_by`.
  - `test_la_ricerca_trova_per_l_ingrediente`: il termine «pelati in scatola», agganciato a «pomodoro», si trova con `q=pomodoro`.
  - `test_la_ricerca_non_da_i_termini_in_coda`: un termine in attesa con lo stesso testo non c'è.
  - `test_la_ricerca_tratta_i_jolly_come_lettere`: con `q=%a`, nessun risultato se nessun nome contiene «%a».
  - `test_la_ricerca_vuole_due_caratteri`: con `q=a` risponde 422.
- [ ] **Step 2: Falliscono.** Il comando di pytest con `tests/api/test_imports_decided_list.py`. Expected: 404 o 405 sulla rotta nuova.
- [ ] **Step 3: Il codice.** `outerjoin(Ingredient, Ingredient.id == ImportTerm.ingredient_id)`; il filtro è `ImportTerm.decision != TermDecision.PENDING`, `ImportTerm.source == source` e un `or_` dei tre `ilike` con `autoescape=True`. Si ordina come `decided_terms`. La docstring dice la decisione 1.
- [ ] **Step 4: Passano**, con `tests/api/test_imports*.py`, poi la suite intera.
- [ ] **Step 5: Commit**: `coda: si cerca fra tutte le decisioni`.

### Task 2: il campo «Cerca fra le decisioni»

**Files:**
- Modify: `frontend/src/features/recipe-import/api.ts` (`searchDecidedTerms(q: string): Promise<ImportTerm[]>`)
- Modify: `frontend/src/features/recipe-import/ImportQueueScreen.tsx` (il campo, la query, l'elenco trovato)
- Test: `frontend/src/features/recipe-import/ImportQueueScreen.test.tsx`

**Interfaces:**
- Consumes: la rotta del Task 1.

- [ ] **Step 1: I test che falliscono.**
  - «cerca fra le decisioni»: scritto «pomod» nel campo «Cerca fra le decisioni», parte `GET /api/v1/imports/terms/search?q=pomod`. Sotto il titolo «Decisioni trovate» c'è la riga della risposta, con «Annulla» che manda l'annulla di oggi. «Decisioni recenti» non è in vista.
  - «nessuna decisione trovata»: con una risposta vuota si legge «Nessuna decisione con queste lettere.».
  - «il tetto si dice»: con 50 righe nella risposta si legge «Ne mostro 50: scrivi di più per restringere.».
  - «la ricerca che non risponde lascia le recenti»: con un 500 si leggono «La ricerca fra le decisioni non risponde. Riprova tra poco.» e, sotto, «Decisioni recenti» con le sue righe.
  - «svuotato il campo tornano le recenti».
  - «una lettera sola non cerca»: con «p» non parte nessuna richiesta di ricerca.
- [ ] **Step 2: Falliscono**: `npx vitest run --maxWorkers=4 src/features/recipe-import/ImportQueueScreen.test.tsx`.
- [ ] **Step 3: Il codice.** Il campo sta sopra la sezione delle decisioni, con l'etichetta visibile «Cerca fra le decisioni» e il placeholder «Il termine o l'ingrediente». C'è anche senza decisioni recenti, se lo stato dice che l'import ha decisioni. Se è più semplice, c'è sempre. La query ha `enabled: debounced.trim().length >= 2`, e la frase del tetto si mostra con 50 righe esatte. Gli stili vengono dai primitivi di `components/ui/`, senza token nuovi.
- [ ] **Step 4: Passano**, poi `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- [ ] **Step 5: Commit**: `coda: il campo per cercare fra le decisioni`.

### Task 3: i termini che bloccano una scartata

**Files:**
- Modify: `backend/app/services/recipe_import/materialize.py` (`blocking_terms`, accanto a `explain_skip`)
- Modify: `backend/app/schemas/recipe_import.py` (`BlockingTermOut`, `SkippedPageOut.blocking_terms`, `SkippedPageOut.blocking_total`)
- Modify: `backend/app/api/imports.py` (`read_skipped_pages`)
- Test: `backend/tests/services/test_skip_reasons.py`, `backend/tests/api/test_imports_skipped.py`

**Interfaces:**
- Produces:
  - `def blocking_terms(cause: SkipCause, lines: list[dict], terms: Mapping[str, ImportTerm], non_food_ids: Set[uuid.UUID]) -> list[ImportTerm]`, pura. Prende i termini nell'ordine delle righe (la `key` di ogni riga), senza doppioni. Per `NON_FOOD`, quelli decisi con un `ingredient_id` in `non_food_ids`; per `ALL_IGNORED`, quelli `IGNORED`; per le altre cause, nessuno. Un termine in coda non entra mai.
  - `BlockingTermOut { id: uuid, name: str }` (il `display_name` del termine); `SkippedPageOut.blocking_terms: list[BlockingTermOut]` (al più 3); `blocking_total: int`.

- [ ] **Step 1: I test che falliscono.**
  - In `test_skip_reasons.py`, una tabella su `blocking_terms` per le quattro cause. Il non alimentare in mezzo a due alimenti dà solo lui; quattro ignorati danno quattro termini nell'ordine delle righe; due righe con la stessa `key` danno un termine solo; un termine `PENDING` con la causa `ALL_IGNORED` non c'è.
  - In `test_imports_skipped.py`:
    - `test_la_scartata_non_alimentare_porta_il_suo_termine`: pagina scartata per «non alimentare», e `blocking_terms` è `[{id, name}]` del termine agganciato al non alimentare, con `blocking_total == 1`.
    - `test_la_scartata_tutta_ignorata_porta_tre_termini_e_il_totale`: cinque righe ignorate, `blocking_terms` ha le prime tre e `blocking_total == 5`.
    - `test_la_scartata_illeggibile_non_ha_termini`: `[]` e `0`.
- [ ] **Step 2: Falliscono** (il comando di pytest con quei due file).
- [ ] **Step 3: Il codice.** `read_skipped_pages` legge in una query i termini delle `key` di tutte le pagine della risposta, e in una seconda gli id non alimentari fra i loro `ingredient_id`: niente query per pagina. Poi chiama `blocking_terms` per ciascuna pagina.
- [ ] **Step 4: Passano**, poi la suite intera.
- [ ] **Step 5: Commit**: `coda: una pagina scartata dice quali termini la bloccano`.

### Task 4: «Annulla «x»» dalla scartata al termine

**Files:**
- Modify: `frontend/src/domain/types.ts` (`SkippedPage.blocking_terms`, `blocking_total`)
- Modify: `frontend/src/features/recipe-import/SkippedPages.tsx` (`SkippedPageRow`), `frontend/src/features/recipe-import/skippedWords.ts` (`othersText`)
- Modify: `frontend/src/features/recipe-import/ImportQueueScreen.tsx` (il fuoco sulla scheda del termine quando `?termine` cambia)
- Test: `frontend/src/features/recipe-import/SkippedPages.test.tsx`, `frontend/src/features/recipe-import/skippedWords.test.ts`, `frontend/src/features/recipe-import/ImportQueueScreen.test.tsx`

**Interfaces:**
- Consumes: il Task 3.
- Produces: `othersText(rest: number): string`, che dà «e un altro» per 1 e «e altri ‹n›» per più di 1.

- [ ] **Step 1: I test che falliscono.**
  - In `SkippedPages.test.tsx`, «la scartata porta ai termini». Con `blocking_terms` di due termini, sotto il motivo ci sono i link «Annulla «salvietta»» e «Annulla «sapone»», con `href` uguale a `/ricette/importa?termine=<id>`. Con `blocking_total: 5` e tre termini, dopo i link si legge «e altri 2».
  - «senza termini la riga è quella di oggi»: nessun link «Annulla».
  - In `skippedWords.test.ts`: `othersText(1) === "e un altro"` e `othersText(4) === "e altri 4"`.
  - In `ImportQueueScreen.test.tsx`, «dal link della scartata al termine». Aperte le scartate, si tocca «Annulla «sapone»»: parte `GET /imports/terms/<id>`, «Il termine che cercavi» è in vista, e il fuoco è sul suo titolo.
- [ ] **Step 2: Falliscono**: `npx vitest run --maxWorkers=4 src/features/recipe-import`.
- [ ] **Step 3: Il codice.**
  - I link sono `Link` di React Router (`to={`/ricette/importa?termine=${id}`}`), con le classi di `buttonClasses("ghost")` come «Apri la pagina». Ciascuno ha un nome accessibile suo, «Annulla «‹nome›»», che è anche il testo.
  - Il titolo «Il termine che cercavi» ha `tabIndex={-1}`. Quando `focused` arriva per un `focusId` nuovo, prende il fuoco e si scorre in vista (`scrollIntoView({ block: "start" })`). Non deve rubare il fuoco a ogni rilettura della stessa scheda: tienilo legato al cambio di `focusId`.
  - La frase «Rendilo un alimento in Anagrafica, o annulla la decisione che lo ha scelto; poi rimettila in coda.» non cambia.
- [ ] **Step 4: Passano**, poi i controlli interi del frontend.
- [ ] **Step 5: Commit**: `coda: dalla pagina scartata al termine che la blocca`.

### Task 5: e2e, la verifica, il backlog

- [ ] **Step 1: e2e intera**, con i comandi delle Global Constraints, dentro il limite di carico. Se `frontend/e2e/scartate.spec.ts` o `import-review.spec.ts` contano i link di una riga, guarda se quelli nuovi li cambiano, e scrivilo nel report.
- [ ] **Step 2: Nel browser**, sullo stack e2e prima del `down`, a 375 px:
  - in «Ingredienti da abbinare», scrivi due lettere di una decisione del seme in «Cerca fra le decisioni»: si vede la riga trovata;
  - se il seme ha una pagina scartata, «Annulla «x»» porta alla scheda in cima;
  - uno screenshot di ciascuna va nel report;
  - niente scorre di lato.
- [ ] **Step 3: Il backlog.** La voce passa a `fatto <data>` in «Fatti (recenti)», con ` → branch night/coda-decisioni (da revisionare)`. Commit: `next-steps: la coda cerca fra le decisioni, fatto`.

## Fuori scope

- L'annulla direttamente dalla scheda dell'ingrediente in Anagrafica (l'altra strada della nota della Parte X).
- Una ricerca che ignora gli accenti, o che cerca fra i termini in coda (la coda ha già il suo ordine).
- Rimettere in coda la pagina dopo l'annulla: resta «Rimetti in coda» com'è.

## Comandi di verifica

- Backend: il comando di pytest delle Global Constraints, tutto verde, con i test nuovi.
- Frontend, da `<worktree>/frontend`: `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- e2e: la suite intera, verde.
- `git -C <worktree> diff master --stat` tocca solo i file dei task, più `next-steps.md` e il report.
