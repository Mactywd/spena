# Pulizie: i test instabili e i piccoli difetti del backend — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** le prove di vitest smettono di cadere sotto carico (attese di Testing Library a 4 s, prove a 15 s); tutti i test di schermata usano il client react-query dell'app, col suo predicato di retry, da una fabbrica condivisa; le date dell'e2e si calcolano nel giorno di Roma; la suite del backend non stampa più avvisi di Starlette, e non potrà ristamparli; l'annullamento di una decisione riconta `occurrences` con una `COUNT` invece di leggere tutti i `payload`; il 409 delle due righe dice quale ingrediente; la coda d'import ha i test dei pulsanti con una decisione in volo.

**Architecture:** frontend: `src/lib/queryClient.ts` (`createAppQueryClient`, usata da `App.tsx`) e `src/test/queryClient.ts` (`createTestQueryClient`, la stessa con `retryDelay: 0`); la migrazione dei 22 file di test che si fanno il client a mano, con una prova strutturale che lo vieta; `configure` di Testing Library in `vitest.setup.ts` e `testTimeout` in `vite.config.ts`; `e2e/giornoDiRoma.ts` con la sua prova. Backend: `HTTP_422_UNPROCESSABLE_CONTENT` più `filterwarnings` e una prova statica; `count_pending_recipes_with_key` in `repositories/imports.py` usata da `undo_decision`; il controllo delle righe doppie in `_resolve_lines` di `api/recipes.py`. Nessuna migrazione, nessuna rotta nuova.

**Tech Stack:** FastAPI, SQLAlchemy async (JSONB `@>`), pytest su Postgres vero; React 19, TypeScript, TanStack Query 5, Vitest 5 + Testing Library (jsdom), Playwright.

**Spec:** `docs/superpowers/specs/2026-10-13-pulizie-test-design.md` (tutta: il §1 dice quali voci di `next-steps.md` chiude e quale sposta al piano 15, il §4 le scelte delegate). La prima lezione di `CLAUDE.md` («A test that builds its own object is not testing the one production uses»).

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/pulizie-test` (`.worktrees/` è già in `.gitignore`), ramo `night/pulizie-test`, creato da **`master`**: questo piano non dipende dalla catena, e nessuno dei suoi file aspetta il lavoro di un altro piano. Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì (o dalle sue `backend/` e `frontend/`), mai dalla radice del checkout principale. Il checkout principale non si tocca: se vi trovi modifiche non committate, sono dell'utente. **Nessun push, nessun merge, nessun deploy. Mai `git stash`.** Niente letture né scritture sulla produzione.
- **I file che anche altri piani della notte toccano** — quasi tutti i test di schermata (ogni piano ne aggiunge), `frontend/src/App.tsx` (S3, R8: le rotte), `frontend/e2e/style.spec.ts` (tutti), `backend/app/api/recipes.py` (R2, R8), `backend/app/services/recipe_import/undo.py` (R8), `backend/app/repositories/imports.py` (il piano 9), `next-steps.md`, il report della notte. Sul tuo ramo, che parte da `master`, sono come su `master`. Il piano descrive comunque ogni modifica a un file esistente contro un'ancora riconoscibile — una funzione, un elemento JSX, un testo esatto — e mai contro numeri di riga: **leggi il file com'è sul ramo prima di cambiarlo**. Le prove nuove vanno **in fondo** ai file o ai `describe`; al merge, l'unione con gli altri rami la fa la revisione.
- **Prima lezione di `CLAUDE.md`**: ciò che si prova è ciò che gira. Il client dei test è quello dell'app (`createAppQueryClient`), con **una sola** differenza dichiarata: `retryDelay: 0`. Nessun test torna a `retry: false`; nessun test si costruisce un `QueryClient` a mano (lo controlla `noLocalQueryClient.test.ts`).
- **Nessun test si indebolisce.** Un test che passava solo perché `retry: false` mostrava l'errore al primo tentativo si corregge **verso la produzione**: il guasto si finge permanente (ogni lettura di quella rotta fallisce), un conteggio di chiamate dopo un guasto conta quelle che l'app fa davvero (3: la prima e due tentativi, `defaultQueryRetryPredicate`). Nessuna asserzione si toglie.
- **Decisione fondante 2 e l'imbuto delle righe** (`CLAUDE.md`): le righe di una ricetta passano da `_resolve_lines` e da `write_recipe_ingredients`; questo piano aggiunge un controllo in `_resolve_lines` e **non tocca** `write_recipe_ingredients` (l'import si aspetta da lui l'`IntegrityError` di oggi).
- Le parole a video **non cambiano**, tranne la frase del 409 (§2.6 della spec), che si copia esattamente: `Due righe puntano allo stesso ingrediente, «<nome>»: togline una, poi salva.` Gli identificatori in inglese; i commenti in italiano, e dicono il perché.
- **Il type check è `npm run typecheck`** (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0 (settima lezione di `CLAUDE.md`).
- Controlli del frontend, da `<worktree>/frontend`: `npx vitest run` (non esiste `npm test`), `npm run typecheck`, `npm run lint`, `npm run build`.
- **Backend su Postgres vero.** Il database dei test è il container `spena-db-1` (porta 5433): se `docker ps --format '{{.Names}}'` non lo mostra, `docker start spena-db-1`. **Mai `docker compose up` dal worktree**, mai `-f docker-compose.prod.yml`. Questo ramo parte da `master` e **non aggiunge migrazioni**: usa `spena_test`, il database dei rami che partono da `master`, se è alla `0012` (vedi la Preparazione). Nel worktree non c'è un `.venv`: si usa quello del checkout principale; `python -m` mette la cartella corrente in testa a `sys.path`, quindi si prova l'`app` del worktree. Il comando, sempre da `<worktree>/backend` (dove un task dice «il comando di pytest» intende questo, con i percorsi che il task indica in coda):
  ```bash
  PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
  Se la Preparazione trova `spena_test` già portato oltre la `0012` da un altro ramo, ogni pytest di questo piano prende davanti `TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_ptest`. Se un test sembra ignorare una modifica, `python -c 'import app; print(app.__file__)'` da `<worktree>/backend` (con lo stesso `PATH`) deve stampare un percorso dentro il worktree. Nessuna chiamata di rete nella suite.
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
- Nessuna dipendenza nuova, nessuna migrazione. Due cambi di configurazione dei test, decisi qui: `testTimeout` di vitest e `filterwarnings` di pytest.

### Preparazione (una volta, prima del Task 1)

- [ ] Il ramo di partenza è `master`, e i file di questo piano sono quelli su cui è scritto (`master` era `b9be6bf` quando il piano è stato scritto):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify master
  git diff --stat b9be6bf master -- \
    frontend/src/App.tsx frontend/vitest.setup.ts frontend/vite.config.ts frontend/src/lib/ \
    frontend/e2e/style.spec.ts backend/pyproject.toml backend/app/api/recipes.py backend/app/api/imports.py \
    backend/app/repositories/imports.py backend/app/services/recipe_import/undo.py \
    backend/app/services/recipe_import/terms.py
  ls frontend/src/lib/queryClient.ts frontend/src/test frontend/e2e/giornoDiRoma.ts 2>&1 | grep -c "No such file"
  ```
  Expected: un hash; il `diff --stat` **vuoto**; `3`. Se il `diff` non è vuoto, `master` è andato avanti su questi file: applica le modifiche del piano sopra la versione di `master`, ancora per ancora, e scrivilo nel report. Se uno dei file nuovi esiste già, **fermati**: qualcuno ha già cominciato questa voce; scrivi nel report della notte (`docs/night-reports/<data>.md`, sul ramo appena creato) cosa hai trovato, segna la voce `bloccato` in `next-steps.md` di quel ramo con la domanda per Mattia, e non partire.
- [ ] Il database dei test:
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d spena_test -tAc 'SELECT version_num FROM alembic_version'
  ```
  Expected: `0012`. Se stampa altro (per esempio `0013` o `0014`, lasciata da un ramo della catena che ha usato il database sbagliato), **non toccare `spena_test`**: crea il database di questo ramo e usalo per tutta la notte, mettendo `TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_ptest` davanti a ogni comando di pytest di questo piano, e scrivilo nel report:
  ```bash
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_ptest WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_ptest'
  ```
  (in quel caso, alla fine del Task 10, `DROP DATABASE IF EXISTS spena_test_ptest WITH (FORCE)`).
- [ ] Dal checkout principale, allinea `node_modules` al lockfile (non aggiunge dipendenze):
  ```bash
  cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund
  ```
- [ ] Crea il worktree da `master` e collega `node_modules` (e solo quello: **niente `.env`**):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/pulizie-test -b night/pulizie-test master
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/pulizie-test/frontend/node_modules
  ```
- [ ] La voce in `next-steps.md` del ramo passa a `in corso`. Cercala con `grep -n "pulizie-test\|Pulizie: test instabili" next-steps.md` (di giorno è stata messa fra i «Pronti per la notte»): toglila da dove sta e mettila sotto `## In corso` (al posto di `_(niente)_`) come
  ```markdown
  - [in corso] P3 · Pulizie: i test instabili, un client react-query solo per app e test, e piccoli difetti del backend — piano `docs/superpowers/plans/2026-10-13-pulizie-test.md` → branch night/pulizie-test [Parte X]
  ```
  Se non la trovi, aggiungi solo questa riga. Commit:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/pulizie-test
  git add next-steps.md
  git commit -m "next-steps: pulizie dei test e del backend, in corso"
  ```
- [ ] La linea di partenza, dal worktree:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/pulizie-test/frontend && npx vitest run 2>&1 | grep -E "Test Files|Tests |Duration"
  npx playwright test --list 2>/dev/null | tail -n 1
  cd ../backend && PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q 2>&1 | tail -n 3
  ```
  Expected: tutto verde; pytest con `8 warnings` (gli `StarletteDeprecationWarning`). **Annota** `N_file`, `N_vitest`, la durata di vitest, `N_e2e`, `N_pytest`. Se una linea non è verde, fermati: non è un difetto di questo piano, e va scritto nel report.

---

## Review Focus

- **Un test che passava solo grazie a `retry: false`**: si corregge verso la produzione (guasto permanente, tre chiamate), mai togliendo un'asserzione — Task 3, regole dello Step 2.
- **La mezzanotte e il cambio d'ora** per le date dell'e2e — Task 4 (tre istanti fissati).
- **Due righe che diventano lo stesso ingrediente per strade diverse** (un id e un nome, due nomi nuovi uguali) e un id inesistente due volte (resta il 404) — Task 7.
- **Pagine con la chiave ripetuta, senza chiave, di un'altra fonte, non in attesa, senza ingredienti**: il conto SQL è quello di `count_pending_keys` — Task 6.
- **Un secondo tocco mentre una decisione o un annullamento sono in volo** — Task 8.

## Obiettivo e contesto

Due prove di vitest cadono a caso quando la macchina è carica; i test di schermata provano un client react-query che non è quello dell'app (la prima lezione di `CLAUDE.md`, che li ha già traditi una volta); un'e2e cade fra mezzanotte e le due; la suite del backend stampa otto avvisi che nessuno legge; l'annullamento di una decisione legge l'intero archivio per contare un numero; e un rifiuto del modulo della ricetta dice «due righe» senza dire quali. Sono sette voci `idea` piccole, che non cambiano niente di quel che l'utente fa: rendono i test affidabili e i messaggi utili.

## Decisioni prese

Di Mattia: **le scelte estetiche e tecniche di queste pulizie sono delegate a Claude** (2026-10-13); solo il comportamento non ovvio va confermato. Qui non ce n'è: l'unica cosa che l'utente vede è la frase del 409, che dice di più senza cambiare cosa succede.

Scelte di questo piano (**decise da Claude su delega di Mattia**, reversibili; la spec, §4):

1. **Le attese globali**: `asyncUtilTimeout` di Testing Library a 4000 ms, `testTimeout` di vitest a 15 000 ms. Prima e dopo si misura con le due prove instabili in parallelo.
2. **La fabbrica del client**: `createAppQueryClient(onUnauthorized)` in `src/lib/queryClient.ts`, usata da `App.tsx`; `createTestQueryClient(onUnauthorized = () => {})` in `src/test/queryClient.ts`, la stessa con `retryDelay: 0`. Una prova strutturale vieta `new QueryClient(` nei test.
3. **`giornoDiRoma(fraGiorni, adesso = new Date())`** in `frontend/e2e/giornoDiRoma.ts`: il giorno di Roma di adesso, più N giorni di calendario.
4. **Le costanti di Starlette**: `HTTP_422_UNPROCESSABLE_CONTENT`; `filterwarnings = ["error::starlette.exceptions.StarletteDeprecationWarning"]`; una prova statica sui nomi di `starlette.status.__deprecated__`.
5. **`count_pending_recipes_with_key(session, source, key) -> int`**: una `COUNT(*)` con `payload->'ingredients' @> '[{"key": …}]'` sulle pagine `pending` della fonte. Senza indice.
6. **Le righe doppie in `_resolve_lines`**: un'eccezione locale, `_RepeatedIngredient(display_name)`, presa da `_writing_recipe` con `rollback` e 409. Il ramo del vincolo d'unicità resta, con la frase di oggi.
7. **`attach` del modulo della ricetta va al piano 15**, non qui (spec, §1).

## Criteri di accettazione

- [ ] Le due prove instabili, sei volte in parallelo per tre giri, passano tutte (Task 1); `getConfig().asyncUtilTimeout` è 4000.
- [ ] `App.tsx` costruisce il client con `createAppQueryClient`; `grep -rln "new QueryClient(" frontend/src --include=*.test.ts --include=*.test.tsx` stampa solo `frontend/src/test/noLocalQueryClient.test.ts` (che lo cerca); nessun test ha `retry: false`.
- [ ] `giornoDiRoma` dà il giorno di Roma alle 00:30 italiane e attraverso il cambio d'ora; `style.spec.ts` non chiama più `toISOString()` per una data.
- [ ] pytest senza avvisi di Starlette; un uso di una costante deprecata fa fallire la suite.
- [ ] `undo_decision` non legge più le pagine in attesa; il conto SQL è uguale a `count_pending_keys` sull'insieme di prova.
- [ ] Due righe sullo stesso ingrediente: 409 con la frase che lo nomina; nessun ingrediente orfano.
- [ ] Coda d'import: con una decisione (o un annullamento) in volo, i pulsanti sono `aria-disabled`, tengono il fuoco, e non mandano una seconda richiesta.
- [ ] vitest, typecheck, lint, build, pytest e l'e2e intera verdi; nessun test indebolito.
- [ ] `next-steps.md` aggiornato (Task 9), il report scritto (Task 10).

## Comandi di verifica

Da `<worktree>/frontend`: `npx vitest run`, `npm run typecheck`, `npm run lint`, `npm run build`. Da `<worktree>/backend`: il comando di pytest. Dalla radice di `<worktree>`:

```bash
grep -rln "new QueryClient(" frontend/src --include=*.test.ts --include=*.test.tsx
grep -rn "retry: false" frontend/src
grep -n "toISOString" frontend/e2e/style.spec.ts
grep -rn "HTTP_422_UNPROCESSABLE_ENTITY" backend/app
grep -n "count_pending_keys\|pending_pages" backend/app/services/recipe_import/undo.py
```

Expected: la prima solo `frontend/src/test/noLocalQueryClient.test.ts`; le altre quattro vuote. E l'e2e intera con i comandi delle Global Constraints.

## Fuori scope

- `attach` del modulo della ricetta: piano 15.
- I test aggiunti dagli altri rami della notte: al merge passano alla fabbrica (la prova strutturale li segnala).
- Un indice sul JSONB delle pagine.
- Ogni cambiamento del frontend per il 409: il modulo mostra già il `detail`.

## Margine di autonomia

- **Liberi:** nomi di variabili locali e di aiuti dei test; l'ordine dei test; i commenti, purché dicano il perché; come raggruppare i commit della migrazione del Task 3.
- **Fissi:** i nomi `createAppQueryClient`, `createTestQueryClient`, `giornoDiRoma`, `count_pending_recipes_with_key`; i valori 4000 e 15 000; la frase del 409.
- **Migrazione del Task 3:** un test che fallisce col client vero si corregge verso la produzione (Global Constraints). Se un test non si lascia correggere così — il comportamento che prova esiste solo senza tentativi — **non** rimettere `retry: false`: lascia il test com'era su quel client (con un commento `// TODO pulizie-test: …` che dice perché), segna la voce `bloccato` con la domanda per Mattia («questo test prova un ramo che con i tentativi veri non si raggiunge: …»), fai commit del resto e vai avanti. La prova strutturale del Task 3 in quel caso elenca quel file, e il report lo dice.
- **Le attese del Task 1:** se dopo la cura la misura trova ancora cadute, e la causa è una prova precisa, correggi quella prova (un `getBy…` dopo un gesto asincrono diventa `findBy…`); se la causa non si trova in un'ora, scrivi nel report cosa hai visto e vai avanti, lasciando la voce dell'instabilità aperta (Task 9).
- **`filterwarnings`:** se, oltre ai nostri, la suite fa partire uno `StarletteDeprecationWarning` da dentro una libreria (FastAPI, httpx), restringi il filtro ai nostri moduli — `"error::starlette.exceptions.StarletteDeprecationWarning:app"` — e scrivilo nel report.
- **Una decisione non coperta e non reversibile** → si ferma quel task, commit del lavoro parziale, `bloccato` con la domanda precisa per Mattia, e si passa al successivo. Una scelta reversibile e a basso impatto → la più conservativa, annotata nel report.

## Dipendenze

**Parte da `master`.** Non consuma niente dagli altri piani della notte. Al merge:

- **R2** (piano 8) aggiunge tre `status.HTTP_422_UNPROCESSABLE_ENTITY` in `backend/app/api/recipes.py`: col `filterwarnings` di questo piano la suite di R2 fallisce dopo il merge finché non diventano `HTTP_422_UNPROCESSABLE_CONTENT`, e la prova statica li elenca. È voluto: la revisione li rinomina al merge (una parola per riga). R2 cambia anche `frontend/src/lib/queryRetry.ts` (il 422 non si ritenta): la fabbrica di questo piano usa `defaultQueryRetryPredicate` per nome, e prende la versione di R2 senza modifiche.
- **S15** (piano 6) aggiunge in `style.spec.ts` una data con `toISOString()` (`fraDueGiorni`, nella prova dei reparti): al merge diventa `giornoDiRoma(2)`.
- **Tutti i piani** aggiungono test di schermata con `new QueryClient(...)`: al merge la prova `noLocalQueryClient.test.ts` li elenca, e ciascuno passa a `createTestQueryClient()` con la regola del Task 3.
- **R8** (piano 10) cambia `undo_decision` (gli id delle varianti nel `payload`) e `create`/`_to_out` in `api/recipes.py`: righe diverse da queste.
- **Le pagine scartate** (piano 9) aggiungono funzioni in `repositories/imports.py`: accanto a questa.
- **Il piano 13** (`pulizie-controlli`) aggiunge test in `ImportQueueScreen.test.tsx`, `RecipeDetailScreen.test.tsx`, `InlineField.test.tsx` e altri, coi client dei loro file: al merge passano alla fabbrica.

## Dopo il deploy (solo Mattia)

Niente: nessuna migrazione, nessun dato.

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `frontend/vitest.setup.ts`, `frontend/vite.config.ts`, `frontend/src/test/waits.test.ts` (nuovo) | 1 | le attese |
| `frontend/src/lib/queryClient.ts` (nuovo), `frontend/src/lib/queryClient.test.ts` (nuovo), `frontend/src/test/queryClient.ts` (nuovo), `frontend/src/App.tsx` | 2 | la fabbrica |
| i 22 file di test con `new QueryClient(`, `frontend/src/test/noLocalQueryClient.test.ts` (nuovo) | 3 | la migrazione e la prova strutturale |
| `frontend/e2e/giornoDiRoma.ts` (nuovo), `frontend/e2e/giornoDiRoma.spec.ts` (nuovo), `frontend/e2e/style.spec.ts` | 4 | le date di Roma |
| `backend/app/api/imports.py`, `backend/app/api/recipes.py`, `backend/pyproject.toml`, `backend/tests/test_no_deprecated_status.py` (nuovo) | 5 | le costanti di Starlette |
| `backend/app/repositories/imports.py`, `backend/app/services/recipe_import/undo.py`, `backend/app/services/recipe_import/terms.py`, `backend/tests/repositories/test_imports_count.py` (nuovo) | 6 | il conto SQL |
| `backend/app/api/recipes.py`, `backend/tests/api/test_recipes_create_ingredient.py` | 7 | il 409 che nomina |
| `frontend/src/features/recipe-import/ImportQueueScreen.test.tsx` | 8 | i pulsanti in volo |
| `next-steps.md` | 9 | i documenti |
| `docs/night-reports/<data>.md` | 10 | il report |

---

### Task 1: Le attese troppo corte

**Files:**
- Modify: `frontend/vitest.setup.ts`, `frontend/vite.config.ts`
- Create: `frontend/src/test/waits.test.ts`

- [ ] **Step 1: La misura, prima**

Da `<worktree>/frontend`, le due prove instabili sei volte in parallelo, tre giri (è il carico dell'e2e accanto, riprodotto):

```bash
LOG=$(mktemp -d)
for giro in 1 2 3; do
  for i in 1 2 3 4 5 6; do
    npx vitest run src/features/shopping-list/ShoppingListScreen.test.tsx src/features/registry/IngredientScreen.test.tsx > "$LOG/prima-$giro-$i.txt" 2>&1 &
  done
  wait
done
grep -L "Test Files .*passed" "$LOG"/prima-*.txt | wc -l
grep -h -B2 -A12 "FAIL" "$LOG"/prima-*.txt | head -n 80
echo "$LOG"
```

Annota nel report quante corse su 18 sono cadute e su quali asserzioni (la seconda riga stampa le corse senza «passed»). Zero cadute non vuol dire che il difetto non c'è: vuol dire che stanotte la macchina non era abbastanza carica. Si va avanti comunque.

- [ ] **Step 2: Il test**

Crea `frontend/src/test/waits.test.ts`:

```ts
import { getConfig } from "@testing-library/react";
import { describe, expect, it } from "vitest";

// Le attese di Testing Library (`findBy…`, `waitFor`) rinunciavano dopo 1 s, e sotto il
// carico dell'e2e accanto le schermate con due o tre letture finte e un `useDebounced`
// cadevano ogni volta su un'asserzione diversa (T3 Consegne 5 e 6a). 4 s per tutte, in
// vitest.setup.ts: una prova che passa passa al primo disegno buono, una che fallisce
// fallisce lo stesso, solo più tardi (pulizie del 2026-10-13).
describe("le attese dei test", () => {
  it("un'attesa di Testing Library dura fino a 4 secondi", () => {
    expect(getConfig().asyncUtilTimeout).toBe(4000);
  });
});
```

- [ ] **Step 3: Fallisce**

Run: `npx vitest run src/test/waits.test.ts`
Expected: FAIL — `expected 1000 to be 4000`.

- [ ] **Step 4: Le attese**

1. In `frontend/vitest.setup.ts`, sotto `import "@testing-library/jest-dom/vitest";`, aggiungi:
   ```ts
   import { configure } from "@testing-library/react";

   // Le attese di Testing Library (`findBy…`, `waitFor`) arrivano a 4 s invece di 1: sotto
   // carico — l'e2e che gira accanto — le schermate con più letture finte cadevano a caso,
   // ogni volta su un'asserzione diversa (src/test/waits.test.ts).
   configure({ asyncUtilTimeout: 4000 });
   ```
2. In `frontend/vite.config.ts`, nel blocco `test: { … }`, dopo `globals: true,` aggiungi:
   ```ts
       // una prova intera: più lunga delle attese di Testing Library (4 s, vitest.setup.ts),
       // perché una prova ne fa più d'una di fila, e sotto carico 5 s non bastavano
       testTimeout: 15_000,
   ```

- [ ] **Step 5: Passa, la suite, il tipo**

Run: `npx vitest run src/test/waits.test.ts && npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde, `N_vitest` + 1 in `N_file` + 1 file. (`vitest.setup.ts` sta nel progetto `tsconfig.node.json`, senza la libreria DOM: i tipi di Testing Library che nominano `Element` stanno nei `.d.ts`, che `skipLibCheck` salta. Se il typecheck si lamenta lo stesso, sposta le tre righe in `frontend/src/test/setup.ts` e aggiungilo a `setupFiles` in `vite.config.ts`: `["./vitest.setup.ts", "./src/test/setup.ts"]`.)

- [ ] **Step 6: La misura, dopo**

Lo stesso ciclo dello Step 1, coi file `dopo-*`. Expected: 0 corse cadute su 18. Se ne cade ancora una, leggi l'asserzione: un `getBy…`/`queryBy…` sincrono subito dopo un gesto che parte una richiesta (un `userEvent.click`, un `fireEvent.change` col `useDebounced`) diventa `findBy…` o sta dentro un `waitFor`; correggi quella e rimisura. Vedi il Margine di autonomia.

- [ ] **Step 7: Commit**

```bash
git add frontend/vitest.setup.ts frontend/vite.config.ts frontend/src/test/waits.test.ts
git commit -m "test: le attese di Testing Library a 4 s e le prove a 15 s — sotto carico la Lista e l'Anagrafica cadevano a caso"
```

(e, se lo Step 6 ha corretto una prova, `git add` di quel file nello stesso commit.)

---

### Task 2: Un client react-query solo, per l'app e per i test

**Files:**
- Create: `frontend/src/lib/queryClient.ts`, `frontend/src/test/queryClient.ts`, `frontend/src/lib/queryClient.test.ts`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Produces: `createAppQueryClient(onUnauthorized: () => void): QueryClient`; `createTestQueryClient(onUnauthorized?: () => void): QueryClient`. Il Task 3 usa `createTestQueryClient`.

- [ ] **Step 1: I test**

Crea `frontend/src/lib/queryClient.test.ts`:

```ts
import { MutationObserver } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { ApiError, UnauthorizedError } from "../api/client";
import { createTestQueryClient } from "../test/queryClient";
import { createAppQueryClient } from "./queryClient";
import { defaultQueryRetryPredicate } from "./queryRetry";

describe("il client react-query dell'app", () => {
  it("ritenta col predicato dell'app, quello che finisce", () => {
    const client = createAppQueryClient(() => {});
    expect(client.getDefaultOptions().queries?.retry).toBe(defaultQueryRetryPredicate);
  });

  it("un 401 da una lettura riporta all'accesso; un altro guasto no", async () => {
    const onUnauthorized = vi.fn();
    const client = createAppQueryClient(onUnauthorized);
    await client
      .fetchQuery({ queryKey: ["guasto"], queryFn: () => Promise.reject(new ApiError("rotto", 500)), retry: false })
      .catch(() => {});
    expect(onUnauthorized).not.toHaveBeenCalled();
    await client
      .fetchQuery({ queryKey: ["scaduta"], queryFn: () => Promise.reject(new UnauthorizedError()) })
      .catch(() => {});
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it("un 401 da una scrittura riporta all'accesso", async () => {
    const onUnauthorized = vi.fn();
    const client = createAppQueryClient(onUnauthorized);
    const scrittura = new MutationObserver(client, {
      mutationFn: () => Promise.reject(new UnauthorizedError()),
    });
    await scrittura.mutate().catch(() => {});
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });
});

describe("il client dei test", () => {
  it("è quello dell'app, senza l'attesa fra un tentativo e l'altro", () => {
    const queries = createTestQueryClient().getDefaultOptions().queries;
    expect(queries?.retry).toBe(defaultQueryRetryPredicate);
    expect(queries?.retryDelay).toBe(0);
  });

  it("un guasto permanente si prova tre volte, come in produzione, e poi si dice", async () => {
    const queryFn = vi.fn(() => Promise.reject(new ApiError("rotto", 500)));
    const client = createTestQueryClient();
    await expect(client.fetchQuery({ queryKey: ["sempre-rotto"], queryFn })).rejects.toThrow("rotto");
    expect(queryFn).toHaveBeenCalledTimes(3);
  });
});
```

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/lib/queryClient.test.ts`
Expected: FAIL — `Failed to resolve import "../test/queryClient"` (e `./queryClient`).

- [ ] **Step 3: Le due fabbriche**

Crea `frontend/src/lib/queryClient.ts`:

```ts
import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";
import { UnauthorizedError } from "../api/client";
import { defaultQueryRetryPredicate } from "./queryRetry";

/** Il client react-query dell'app. Uno solo, per `App.tsx` e — con i tentativi senza
 * attesa — per i test (`src/test/queryClient.ts`): un test che si costruisce il suo client
 * prova quello e non questo, e un client che ritentava per sempre è passato così sotto
 * ogni test di schermata (prima lezione di CLAUDE.md).
 *
 * Un 401 da qualsiasi chiamata riporta all'accesso, senza schermate rotte. Servono
 * entrambe le cache: le query leggono, ma spuntare una voce, cambiare uno stato in
 * dispensa e cucinare una ricetta sono mutazioni, e una sessione scaduta a metà di una di
 * quelle lascerebbe la schermata ferma su dati vecchi senza dire perché. */
export function createAppQueryClient(onUnauthorized: () => void): QueryClient {
  const bounceToLogin = (error: unknown) => {
    if (error instanceof UnauthorizedError) onUnauthorized();
  };
  return new QueryClient({
    queryCache: new QueryCache({ onError: bounceToLogin }),
    mutationCache: new MutationCache({ onError: bounceToLogin }),
    defaultOptions: {
      queries: {
        retry: defaultQueryRetryPredicate,
      },
    },
  });
}
```

Crea `frontend/src/test/queryClient.ts`:

```ts
import type { QueryClient } from "@tanstack/react-query";
import { createAppQueryClient } from "../lib/queryClient";

/** Il client dei test di schermata: quello dell'app (`createAppQueryClient`), col suo
 * predicato di retry e le sue due cache, con una sola differenza — i tentativi non
 * aspettano (`retryDelay: 0`). I tentativi sono quelli veri: un guasto si vede dopo il
 * terzo, come in produzione; l'attesa vera fra l'uno e l'altro (1 s, 2 s) renderebbe ogni
 * ramo d'errore lungo tre secondi. Nessun test se ne costruisce uno a mano
 * (`noLocalQueryClient.test.ts`). */
export function createTestQueryClient(onUnauthorized: () => void = () => {}): QueryClient {
  const client = createAppQueryClient(onUnauthorized);
  const defaults = client.getDefaultOptions();
  client.setDefaultOptions({ ...defaults, queries: { ...defaults.queries, retryDelay: 0 } });
  return client;
}
```

- [ ] **Step 4: `App.tsx`**

In `frontend/src/App.tsx`:

1. L'import
   ```tsx
   import {
     MutationCache,
     QueryCache,
     QueryClient,
     QueryClientProvider,
   } from "@tanstack/react-query";
   ```
   diventa `import { QueryClientProvider } from "@tanstack/react-query";`; sotto gli altri import da `./lib/`, aggiungi `import { createAppQueryClient } from "./lib/queryClient";`; l'import `import { defaultQueryRetryPredicate } from "./lib/queryRetry";` si toglie (il lint lo segnalerebbe non usato).
2. Il blocco `const [queryClient] = useState(() => { … return new QueryClient({ … }); });` (dal commento `// un 401 da qualsiasi chiamata riporta all'accesso` fino alla chiusura dello `useState`) diventa:
   ```tsx
     // creato una volta sola: ricostruirlo a ogni render svuoterebbe la cache. Com'è fatto
     // (i 401 che riportano all'accesso, i tentativi) sta in lib/queryClient.ts, dove lo
     // prendono anche i test
     const [queryClient] = useState(() => createAppQueryClient(() => setAuthenticated(false)));
   ```
   (il commento `// creato una volta sola: ricostruirlo a ogni render svuoterebbe la cache` che c'era sopra lo `useState` si sostituisce con questo). `UnauthorizedError` non serve più in `App.tsx` se non per questo: se il lint lo segnala non usato, togli il suo import.

- [ ] **Step 5: Passano, e la suite**

Run: `npx vitest run src/lib/queryClient.test.ts && npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde, `N_vitest` + 1 + 5 in `N_file` + 2. `App.test.tsx` («un errore che non è un 401 non viene ritentato all'infinito», «un 401 … riporta all'accesso») passa senza modifiche: prova `App` intera, cioè il client vero.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/queryClient.ts frontend/src/lib/queryClient.test.ts frontend/src/test/queryClient.ts frontend/src/App.tsx
git commit -m "feat: il client react-query dell'app esce da App.tsx (createAppQueryClient), e i test ne hanno la copia senza attese (createTestQueryClient)"
```

---

### Task 3: Ogni test di schermata usa il client dell'app

**Files:**
- Modify: i file elencati da `grep -rln "new QueryClient(" frontend/src --include=*.test.ts --include=*.test.tsx` — su `master` 22: `components/IngredientPicker.test.tsx`; in `features/`: `ai-draft/AiDraftScreen.test.tsx`, `cooking/AddMissingButton.test.tsx`, `cooking/CookSheet.test.tsx`, `cooking/RecipeDetailActions.test.tsx`, `cooking/RecipeDetailScreen.test.tsx`, `pantry/PantryScreen.test.tsx`, `recipe-form/RecipeEditScreen.test.tsx`, `recipe-form/RecipeForm.test.tsx`, `recipe-import/ImportQueueScreen.test.tsx`, `recipes/RecipeBookScreen.test.tsx`, `recipes/useArchiveRecipe.test.tsx`, `registry/IngredientScreen.test.tsx`, `registry/ProductScreen.test.tsx`, `registry/RegistryScreen.test.tsx`, `shopping-list/AddItemField.test.tsx`, `shopping-list/ShoppingListScreen.test.tsx`, `stocking/CatalogSearchPanel.test.tsx`, `stocking/CustomProductForm.test.tsx`, `stocking/MatchPanel.test.tsx`, `stocking/ScannerPanel.test.tsx`, `stocking/StockingScreen.test.tsx`
- Create: `frontend/src/test/noLocalQueryClient.test.ts`

**Interfaces:**
- Consumes: `createTestQueryClient` (Task 2).

- [ ] **Step 1: La prova strutturale**

Crea `frontend/src/test/noLocalQueryClient.test.ts`:

```ts
// @vitest-environment node
//
// Legge i sorgenti dei test, non tocca il DOM: in ambiente `node` per lo stesso motivo di
// theme.test.ts (l'`URL` di jsdom ignora la base `file://`), coi tipi di Node chiesti qui.
/// <reference types="node" />
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const SRC = fileURLToPath(new URL("..", import.meta.url));
const SELF = fileURLToPath(import.meta.url);

function tests(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return tests(path);
    return /\.test\.tsx?$/.test(name) && path !== SELF ? [path] : [];
  });
}

// Prima lezione di CLAUDE.md: un test che si costruisce il suo oggetto non prova quello
// che gira. Ogni test di schermata prende il client da `createTestQueryClient`, che è
// quello dell'app; un `new QueryClient(` qui vorrebbe dire un client che la produzione
// non ha (pulizie del 2026-10-13).
describe("i test di schermata", () => {
  it("nessuno si costruisce il client react-query a mano", () => {
    const found = tests(SRC).filter((file) => readFileSync(file, "utf8").includes("new QueryClient("));
    expect(found.map((file) => file.slice(SRC.length))).toEqual([]);
  });
});
```

Run (da `<worktree>/frontend`): `npx vitest run src/test/noLocalQueryClient.test.ts`
Expected: FAIL — elenca i 22 file.

- [ ] **Step 2: La migrazione, un file alla volta**

Per ogni file elencato:

1. Ogni `new QueryClient({ … })` (con qualunque opzione: `retry: false`, `retry: defaultQueryRetryPredicate`, `retryDelay: 0`, `mutations: { retry: false }` — le mutazioni dell'app non ritentano già, è il default di react-query) diventa `createTestQueryClient()`. Dove un aiuto riceve il client come parametro con un default (`client = new QueryClient(…)`), il default diventa `client = createTestQueryClient()`. Dove un test passava un client suo solo per avere `retryDelay: 0` (in `ImportQueueScreen.test.tsx`, «un guasto nel leggere il termine non si spaccia per «non c'è»…»), passa `createTestQueryClient()` o niente.
2. In cima al file aggiungi `import { createTestQueryClient } from "<percorso>/test/queryClient";` (relativo: `../test/queryClient` da `components/`, `../../test/queryClient` da `features/<cartella>/`). Togli gli import rimasti senza uso (`QueryClient` se serviva solo lì — resta se il file lo usa come tipo —, `defaultQueryRetryPredicate`): il lint li segnala.
3. Dove un commento diceva perché il file usava `retry: false` o il predicato vero (per esempio quello sopra `renderScreen` in `ImportQueueScreen.test.tsx`), sostituiscilo con una riga: `// il client dell'app (src/test/queryClient.ts): predicato vero, tentativi senza attesa`. Dove un commento giustificava un `timeout: 8000` con «l'attesa reale» dei tentativi, aggiungi in coda `— dal 2026-10-13 i tentativi non aspettano, e il tempo lungo resta solo come margine` (il tempo si lascia: non fa danno).
4. Run: `npx vitest run <il file>`. Se è verde, passa al prossimo. Se un test cade, è uno dei tre casi:
   - **un guasto finto una volta sola** (`mockResolvedValueOnce(new Response("", { status: 500 }))`, un contatore che fallisce solo alla prima lettura) che ora il secondo tentativo guarisce: l'app vera lo guarirebbe uguale. Il test vuole il ramo d'errore: rendi il guasto permanente per quella rotta (ogni lettura fallisce). Se il test vuole proprio «fallisce una volta, poi va» (un «Riprova»), il guasto deve durare tre letture, e il «Riprova» trova la quarta;
   - **un conteggio di chiamate dopo un guasto** (`toHaveBeenCalledTimes(1)`): ora sono 3 (la prima e due tentativi), come in produzione; cambia il numero, e scrivi accanto `// 3: la prima lettura e i due tentativi di defaultQueryRetryPredicate`;
   - **altro**: vedi il Margine di autonomia.
   In nessun caso si toglie un'asserzione o si rimette `retry: false`.
5. Ogni sei o sette file, la suite intera e un commit (`git add` dei file migrati):
   ```bash
   npx vitest run && npm run typecheck && npm run lint
   git commit -m "test: <cartelle> col client dell'app (createTestQueryClient) invece di un client fatto a mano"
   ```

- [ ] **Step 3: La prova strutturale passa**

Run: `npx vitest run src/test/noLocalQueryClient.test.ts && grep -rn "retry: false" src`
Expected: PASS; il `grep` vuoto.

- [ ] **Step 4: La suite, il tipo, e le due prove instabili**

Run: `npx vitest run 2>&1 | grep -E "Test Files|Tests |Duration" && npm run typecheck && npm run lint`
Expected: tutto verde, `N_vitest` + 6 + 1 in `N_file` + 3 (i test migrati sono gli stessi, cambiati dentro). Annota la durata: dovrebbe essere più corta di quella della Preparazione (i rami d'errore non aspettano più 1 s + 2 s). Poi rifai la misura del Task 1, Step 1, con i file `migrati-*`: expected 0 cadute su 18.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/test/noLocalQueryClient.test.ts
git add -u frontend/src
git commit -m "test: nessun test si costruisce il client react-query a mano — la prova che lo tiene"
```

---

### Task 4: Le date dell'e2e nel giorno di Roma

**Files:**
- Create: `frontend/e2e/giornoDiRoma.ts`, `frontend/e2e/giornoDiRoma.spec.ts`
- Modify: `frontend/e2e/style.spec.ts`

**Interfaces:**
- Produces: `giornoDiRoma(fraGiorni: number, adesso?: Date): string` (`"AAAA-MM-GG"`).

- [ ] **Step 1: La prova**

Crea `frontend/e2e/giornoDiRoma.spec.ts`:

```ts
import { expect, test } from "@playwright/test";
import { giornoDiRoma } from "./giornoDiRoma.ts";

// Il backend giudica le scadenze nel giorno di Europe/Rome (`PANTRY_TZ`): le date delle
// prove si calcolano nello stesso giorno. Con `toISOString()`, in UTC, fra mezzanotte e
// le 2 ora italiana la prova mandava il giorno prima, e falliva («tra 4 gg» invece di
// «tra 5 gg», T3 Consegna 6a). Questa prova non apre pagine: prova solo l'aiuto.
test.describe("giornoDiRoma", () => {
  test("alle 00:30 italiane è già il giorno dopo di UTC", () => {
    const adesso = new Date("2026-10-13T22:30:00Z"); // 00:30 del 14 a Roma (ora legale, +2)
    expect(giornoDiRoma(0, adesso)).toBe("2026-10-14");
    expect(giornoDiRoma(5, adesso)).toBe("2026-10-19");
  });

  test("di pomeriggio è lo stesso giorno", () => {
    expect(giornoDiRoma(3, new Date("2026-10-14T13:00:00Z"))).toBe("2026-10-17");
  });

  test("attraverso il cambio d'ora del 25 ottobre i giorni restano giorni di calendario", () => {
    // 00:30 del 25 a Roma (ancora ora legale): fra un giorno è il 26, anche se quel giorno
    // dura 25 ore
    expect(giornoDiRoma(1, new Date("2026-10-24T22:30:00Z"))).toBe("2026-10-26");
    // 00:30 del 26 a Roma (ora solare, +1)
    expect(giornoDiRoma(0, new Date("2026-10-25T23:30:00Z"))).toBe("2026-10-26");
  });
});
```

Run (da `<worktree>/frontend`): `npx playwright test e2e/giornoDiRoma.spec.ts`
Expected: FAIL — non trova il modulo `./giornoDiRoma.ts`. (Queste tre prove non usano la pagina: girano senza lo stack, e se `E2E_BASE_URL` manca Playwright non lo chiede finché nessuna prova apre una pagina. Se il `playwright.config.ts` alza da sé un server o rifiuta di partire senza `E2E_BASE_URL`, falle girare nello Step 4 insieme all'e2e intera.)

- [ ] **Step 2: L'aiuto**

Crea `frontend/e2e/giornoDiRoma.ts`:

```ts
/** Il giorno di calendario a Roma fra `fraGiorni` giorni, come «AAAA-MM-GG».
 *
 * Il backend giudica le scadenze nel giorno di Europe/Rome (`PANTRY_TZ`), non in quello di
 * UTC: una data scritta da una prova deve essere quella che un utente a Roma vedrebbe sul
 * calendario. Si prende il giorno di Roma di `adesso` e ci si sommano giorni di calendario,
 * non 24 ore: la notte del cambio d'ora dura 23 o 25 ore, e il giorno dopo resta il giorno
 * dopo. */
export function giornoDiRoma(fraGiorni: number, adesso: Date = new Date()): string {
  // `en-CA` scrive le date come AAAA-MM-GG
  const oggi = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Rome",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(adesso);
  const [anno, mese, giorno] = oggi.split("-").map(Number);
  return new Date(Date.UTC(anno, mese - 1, giorno + fraGiorni)).toISOString().slice(0, 10);
}
```

(Il `toISOString()` qui è giusto: la data è costruita a mezzanotte UTC del giorno già scelto, e serve solo a scriverla.)

- [ ] **Step 3: Le tre date di `style.spec.ts`**

In `frontend/e2e/style.spec.ts`:

1. In cima, accanto agli altri import, aggiungi `import { giornoDiRoma } from "./giornoDiRoma.ts";`.
2. `const fraDueGiorni = new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);` diventa `const fraDueGiorni = giornoDiRoma(2);`.
3. `const fraTreGiorni = new Date(Date.now() + 3 * 24 * 60 * 60 * 1000)` con le sue due righe `.toISOString()` e `.slice(0, 10);` diventa `const fraTreGiorni = giornoDiRoma(3);`; nel commento sopra, dopo `La data si calcola qui e non si scrive a` / `mano, o il test scadrebbe da solo.` aggiungi ` Nel giorno di Roma, come il server (giornoDiRoma.ts).`
4. `const fraCinqueGiorni = new Date(Date.now() + 5 * 24 * 60 * 60 * 1000)` con le sue due righe diventa `const fraCinqueGiorni = giornoDiRoma(5);`.

Run: `grep -n "toISOString" e2e/style.spec.ts && npm run typecheck && npm run lint && npx playwright test --list 2>/dev/null | tail -n 1`
Expected: il `grep` vuoto; typecheck e lint puliti; **`N_e2e` + 3**.

- [ ] **Step 4: L'e2e intera**

Con i comandi delle Global Constraints. Expected: tutti verdi, `N_e2e` + 3. Poi `down -v` e `rm .env`.

- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/giornoDiRoma.ts frontend/e2e/giornoDiRoma.spec.ts frontend/e2e/style.spec.ts
git commit -m "e2e: le date delle scadenze nel giorno di Roma, come il server — fra mezzanotte e le 2 la prova mandava il giorno prima"
```

---

### Task 5: Le costanti di stato deprecate di Starlette

**Files:**
- Modify: `backend/app/api/imports.py`, `backend/app/api/recipes.py`, `backend/pyproject.toml`
- Create: `backend/tests/test_no_deprecated_status.py`

- [ ] **Step 1: La prova**

Crea `backend/tests/test_no_deprecated_status.py`:

```python
"""Le costanti di stato che Starlette ha deprecato non si usano.

`status.HTTP_422_UNPROCESSABLE_ENTITY` stampava 8 `StarletteDeprecationWarning` a ogni
suite, e nessuno li leggeva. Il `filterwarnings` di pyproject.toml fa di quell'avviso un
errore, ma solo dove un test passa; questa prova guarda il sorgente intero, anche le righe
che nessun test attraversa (pulizie del 2026-10-13).
"""

from pathlib import Path

from starlette import status

APP = Path(__file__).resolve().parents[1] / "app"


def test_nessuna_costante_di_stato_deprecata_in_app():
    deprecated = set(status.__deprecated__)
    trovati = [
        f"{path.relative_to(APP.parent)}:{numero}"
        for path in sorted(APP.rglob("*.py"))
        for numero, riga in enumerate(path.read_text().splitlines(), start=1)
        if any(nome in riga for nome in deprecated)
    ]
    assert trovati == []
```

Run: il comando di pytest con `tests/test_no_deprecated_status.py`
Expected: FAIL — elenca `app/api/imports.py` e `app/api/recipes.py` (tre righe).

- [ ] **Step 2: Le costanti, e il filtro**

1. In `backend/app/api/imports.py` e `backend/app/api/recipes.py`, ogni `status.HTTP_422_UNPROCESSABLE_ENTITY` diventa `status.HTTP_422_UNPROCESSABLE_CONTENT` (stesso numero, 422).
2. In `backend/pyproject.toml`, in `[tool.pytest.ini_options]`, dopo `testpaths = ["tests"]` aggiungi:
   ```toml
   # Una costante deprecata di Starlette è un errore, non un avviso: gli 8 avvisi per
   # `HTTP_422_UNPROCESSABLE_ENTITY` li stampava ogni suite e non li leggeva nessuno
   # (tests/test_no_deprecated_status.py guarda anche le righe che nessun test attraversa)
   filterwarnings = [
       "error::starlette.exceptions.StarletteDeprecationWarning",
   ]
   ```

- [ ] **Step 3: Passa, e la suite senza avvisi**

Run: il comando di pytest, intero, con `2>&1 | tail -n 3`.
Expected: verde, **`N_pytest` + 1**, e nessuna riga `warnings` per Starlette. Se compare un errore `StarletteDeprecationWarning` che parte da una libreria e non da `app/`, vedi il Margine di autonomia (il filtro si restringe con `:app`).

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/imports.py backend/app/api/recipes.py backend/pyproject.toml backend/tests/test_no_deprecated_status.py
git commit -m "fix(backend): HTTP_422_UNPROCESSABLE_CONTENT al posto della costante deprecata; un avviso di Starlette fa fallire la suite"
```

---

### Task 6: L'annullamento riconta `occurrences` con una `COUNT`

**Files:**
- Modify: `backend/app/repositories/imports.py`, `backend/app/services/recipe_import/undo.py`, `backend/app/services/recipe_import/terms.py`
- Create: `backend/tests/repositories/test_imports_count.py`

**Interfaces:**
- Produces: `count_pending_recipes_with_key(session: AsyncSession, source: str, key: str) -> int` in `app/repositories/imports.py`.

- [ ] **Step 1: La prova**

Crea `backend/tests/repositories/test_imports_count.py`:

```python
"""Le ricette in attesa che nominano una chiave, contate dal database.

`undo_decision` riconta `occurrences` per il termine annullato: prima caricava tutte le
pagine in attesa col loro `payload` intero per contare una chiave sola, e la fusione
dell'anagrafica lo fa una volta per termine. Il conto SQL deve dire esattamente quel che
dice `count_pending_keys`, la funzione di `sync_terms`: due conti scritti due volte
divergono, e la coda direbbe numeri diversi a seconda di chi l'ha toccata per ultimo.
"""

from app.db.models.recipe_import import GIALLOZAFFERANO, ImportState, RecipeImport
from app.repositories.imports import count_pending_recipes_with_key, pending_pages
from app.services.recipe_import.terms import count_pending_keys


async def test_il_conto_sql_e_quello_di_count_pending_keys(db_session):
    db_session.add_all([
        # la stessa chiave in due righe: la ricetta conta una volta
        RecipeImport(
            source=GIALLOZAFFERANO, url="https://esempio.invalid/conto-1",
            payload={"title": "Speck due volte", "ingredients": [
                {"key": "k-speck", "name": "Speck"},
                {"key": "k-speck", "name": "Speck a cubetti"},
                {"key": "k-uova", "name": "Uova"},
            ]},
            state=ImportState.PENDING,
        ),
        # righe senza chiave o con la chiave vuota non contano
        RecipeImport(
            source=GIALLOZAFFERANO, url="https://esempio.invalid/conto-2",
            payload={"title": "Senza chiavi", "ingredients": [
                {"name": "Sale"},
                {"key": "", "name": "Pepe"},
                {"key": "k-uova", "name": "Uova"},
            ]},
            state=ImportState.PENDING,
        ),
        RecipeImport(
            source=GIALLOZAFFERANO, url="https://esempio.invalid/conto-3",
            payload={"title": "Senza ingredienti"},
            state=ImportState.PENDING,
        ),
        # non in attesa
        RecipeImport(
            source=GIALLOZAFFERANO, url="https://esempio.invalid/conto-4",
            payload={"title": "Già dentro", "ingredients": [{"key": "k-speck", "name": "Speck"}]},
            state=ImportState.IMPORTED,
        ),
        RecipeImport(
            source=GIALLOZAFFERANO, url="https://esempio.invalid/conto-5",
            payload={"title": "Scartata", "ingredients": [{"key": "k-speck", "name": "Speck"}]},
            state=ImportState.SKIPPED, skipped_reason="prova",
        ),
        # un'altra fonte
        RecipeImport(
            source="altra-fonte", url="https://altro.invalid/conto-6",
            payload={"title": "Altrove", "ingredients": [{"key": "k-speck", "name": "Speck"}]},
            state=ImportState.PENDING,
        ),
    ])
    await db_session.flush()

    attesi = count_pending_keys(await pending_pages(db_session, GIALLOZAFFERANO)).occurrences
    assert attesi == {"k-speck": 1, "k-uova": 2}
    for key in ["k-speck", "k-uova", "k-nessuno"]:
        assert (
            await count_pending_recipes_with_key(db_session, GIALLOZAFFERANO, key)
        ) == attesi.get(key, 0), key
```

Run: il comando di pytest con `tests/repositories/test_imports_count.py`
Expected: FAIL — `ImportError: cannot import name 'count_pending_recipes_with_key'`. (Se `attesi` non è `{"k-speck": 1, "k-uova": 2}`, il seme del database dei test ha pagine in attesa sue: non è così su `master`, ma se succede, togli quell'`assert` e lascia il confronto, che resta la prova; scrivilo nel report.)

- [ ] **Step 2: La funzione**

In `backend/app/repositories/imports.py`, subito dopo `async def pending_pages(…)` e il suo corpo, aggiungi:

```python
async def count_pending_recipes_with_key(session: AsyncSession, source: str, key: str) -> int:
    """Le ricette in attesa della fonte che nominano `key` in almeno una riga.

    È il numero che `count_pending_keys` (services/recipe_import/terms.py) dà per quella
    chiave, contato dal database: `payload->'ingredients' @> '[{"key": …}]'` è vero una
    volta per pagina, anche se la chiave sta in due righe, e mai per una riga senza chiave.
    Lo usa `undo_decision`, che riconta un termine solo e prima leggeva tutte le pagine in
    attesa col loro JSONB intero (tests/repositories/test_imports_count.py tiene uguali i
    due conti).
    """
    return (
        await session.execute(
            select(func.count())
            .select_from(RecipeImport)
            .where(
                RecipeImport.source == source,
                RecipeImport.state == ImportState.PENDING,
                RecipeImport.payload["ingredients"].contains([{"key": key}]),
            )
        )
    ).scalar_one()
```

- [ ] **Step 3: Passa**

Run: il comando di pytest con `tests/repositories/test_imports_count.py`
Expected: PASS.

- [ ] **Step 4: `undo_decision` la usa**

1. In `backend/app/services/recipe_import/undo.py`:
   - gli import `from app.repositories.imports import pending_pages` e `from app.services.recipe_import.terms import count_pending_keys` diventano uno solo, `from app.repositories.imports import count_pending_recipes_with_key` (nel file non hanno altri usi: `grep -n "pending_pages\|count_pending_keys" app/services/recipe_import/undo.py` dopo la modifica dev'essere vuoto);
   - le due righe
     ```python
         counted = count_pending_keys(await pending_pages(session, term.source))
         term.occurrences = counted.occurrences.get(term.term_key, 0)
     ```
     diventano
     ```python
         term.occurrences = await count_pending_recipes_with_key(session, term.source, term.term_key)
     ```
   - nel commento sopra, la frase `Si riconta il termine annullato, e solo lui, con la funzione di \`sync_terms\`, dopo il \`flush\` che ha scritto le pagine tornate \`pending\`.` diventa `Si riconta il termine annullato, e solo lui, con lo stesso conto di \`sync_terms\` fatto dal database (\`count_pending_recipes_with_key\`: prima si leggevano tutte le pagine in attesa per una chiave sola), dopo il \`flush\` che ha scritto le pagine tornate \`pending\`.`
2. In `backend/app/services/recipe_import/terms.py`:
   - nel docstring di `count_pending_keys`, la frase `Una funzione sola per \`sync_terms\` e per \`undo_decision\`: due conteggi scritti due volte divergono, e la coda direbbe numeri diversi a seconda di chi l'ha toccata per ultimo.` diventa `\`sync_terms\` la usa per tutte le chiavi; \`undo_decision\` conta una chiave sola dal database (\`count_pending_recipes_with_key\`), e tests/repositories/test_imports_count.py tiene uguali i due conti: due conteggi che divergono farebbero dire alla coda numeri diversi a seconda di chi l'ha toccata per ultimo.`
   - nel docstring di `sync_terms`, la frase `L'altro posto che lo ricalcola è \`undo_decision\`, per il termine annullato.` diventa `L'altro posto che lo ricalcola è \`undo_decision\`, per il termine annullato, con lo stesso conto fatto dal database.`

- [ ] **Step 5: La suite**

Run: il comando di pytest, intero.
Expected: verde, `N_pytest` + 2. Le prove di `tests/services/test_undo.py` su `occurrences` dopo l'annullamento e quelle della fusione (`tests/services/test_registry_merge.py`) passano senza modifiche.

- [ ] **Step 6: Commit**

```bash
git add backend/app/repositories/imports.py backend/app/services/recipe_import/undo.py backend/app/services/recipe_import/terms.py backend/tests/repositories/test_imports_count.py
git commit -m "perf(import): l'annullamento riconta occurrences con una COUNT sul JSONB invece di leggere tutte le pagine in attesa"
```

---

### Task 7: Il 409 delle due righe nomina l'ingrediente

**Files:**
- Modify: `backend/app/api/recipes.py`
- Test: `backend/tests/api/test_recipes_create_ingredient.py`

- [ ] **Step 1: I test**

In `backend/tests/api/test_recipes_create_ingredient.py`:

1. Nel test `test_se_il_salvataggio_fallisce_nessun_ingrediente_resta_orfano`, subito dopo `assert response.status_code == 409`, aggiungi:
   ```python
       # e dice quale: le due righe «speck» diventano lo stesso ingrediente
       assert response.json()["detail"] == (
           "Due righe puntano allo stesso ingrediente, «Speck»: togline una, poi salva."
       )
   ```
2. In fondo al file aggiungi:
   ```python
   async def test_due_righe_sullo_stesso_ingrediente_dicono_quale(logged_client, db_session):
       """Un nome nuovo che coincide con una riga già agganciata: il 409 lo nomina.

       Prima la frase diceva «due righe» e basta, e su dodici righe si cercavano a occhio.
       """
       pasta = await create_ingredient(
           db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI,
       )
       await db_session.commit()

       response = await logged_client.post("/api/v1/recipes", json={
           "title": "Pasta e pasta", "instructions": "1. cuoci", "servings": 2, "source": "manual",
           "ingredients": [
               {"ingredient_id": str(pasta.id), "role": "primary"},
               {"name": "pasta", "category": "cereali", "role": "secondary"},
           ],
       })

       assert response.status_code == 409
       assert response.json()["detail"] == (
           "Due righe puntano allo stesso ingrediente, «Pasta»: togline una, poi salva."
       )
   ```

Run: il comando di pytest con `tests/api/test_recipes_create_ingredient.py`
Expected: FAIL — il `detail` è ancora `Due righe puntano allo stesso ingrediente: togline una, poi salva.`

- [ ] **Step 2: Il controllo**

In `backend/app/api/recipes.py`:

1. Accanto agli altri import da `app.db.models`, aggiungi `from app.db.models.ingredient import Ingredient` (se il file non lo importa già).
2. Subito prima di `async def _resolve_lines(`, aggiungi:
   ```python
   class _RepeatedIngredient(Exception):
       """Due righe del modulo che, risolte, puntano allo stesso ingrediente."""

       def __init__(self, display_name: str) -> None:
           super().__init__(display_name)
           self.display_name = display_name
   ```
3. In `_resolve_lines`:
   - nel docstring, dopo `ingrediente, non un doppione.` aggiungi:
     ```python

         Due righe che puntano allo stesso ingrediente — lo stesso id due volte, un nome nuovo
         uguale a una riga agganciata, due nomi che `match_name` porta allo stesso — si
         rifiutano qui, nominandolo (`_RepeatedIngredient`, 409 in `_writing_recipe`): il
         vincolo d'unicità della tabella delle righe le rifiuterebbe comunque, ma non sa dire
         quale ingrediente.
     ```
   - subito dopo `resolved: list[IngredientLine] = []` aggiungi `seen: set[uuid.UUID] = set()`;
   - subito prima di `resolved.append((ingredient_id, line.role, line.quantity_text, line.note))` aggiungi:
     ```python
             if ingredient_id in seen:
                 ingredient = await session.get(Ingredient, ingredient_id)
                 # un id che non esiste due volte non è un doppione da nominare: lo
                 # scopre la scrittura, col suo 404 «inesistente», come prima
                 if ingredient is not None:
                     raise _RepeatedIngredient(ingredient.display_name)
             seen.add(ingredient_id)
     ```
4. In `_writing_recipe`, subito dopo il blocco `except NonFoodInRecipe as exc: …` (che finisce con `) from exc`), aggiungi:
   ```python
       except _RepeatedIngredient as exc:
           # un ingrediente creato da una riga precedente se ne va con la ricetta
           await session.rollback()
           raise HTTPException(
               status.HTTP_409_CONFLICT,
               f"Due righe puntano allo stesso ingrediente, «{exc.display_name}»: "
               "togline una, poi salva.",
           ) from exc
   ```
   Il ramo `except IntegrityError` resta com'è: il vincolo d'unicità è il ripiego per una corsa fra due salvataggi.

- [ ] **Step 3: Passano, e la suite**

Run: il comando di pytest con `tests/api/test_recipes_create_ingredient.py tests/api/test_recipes.py`, poi intero.
Expected: verde, `N_pytest` + 3. `test_repeating_an_ingredient_in_a_recipe_is_409_not_500` (stesso id due volte) passa: è sempre 409, ora dal controllo. `test_se_il_salvataggio_fallisce_nessun_ingrediente_resta_orfano` passa anche nella parte sull'orfano: il `rollback` toglie lo «speck» creato dalla prima riga.

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/recipes.py backend/tests/api/test_recipes_create_ingredient.py
git commit -m "fix(ricette): il 409 delle due righe dice quale ingrediente"
```

---

### Task 8: La coda d'import con una decisione in volo

**Files:**
- Test: `frontend/src/features/recipe-import/ImportQueueScreen.test.tsx`

Solo test: la schermata spegne già ogni pulsante delle schede con `busy` (T3 Consegna 6b); nessuno lo provava. Il campo del selettore non si guarda: lo cambia il piano 13.

- [ ] **Step 1: I test**

In `frontend/src/features/recipe-import/ImportQueueScreen.test.tsx`, dentro `describe("coda di revisione dell'import", …)`, in fondo, aggiungi:

```tsx
  /** Coda, decisioni e stato come `renderQueue`, ma la decisione e l'annullamento non
   * tornano mai: restano in volo per tutta la prova. Conta quante ne partono. */
  function stubInVolo(decided: ImportTerm[] = []) {
    const partite = { decisioni: 0, annullamenti: 0 };
    vi.stubGlobal(
      "fetch",
      vi.fn((url: unknown, init?: RequestInit) => {
        const path = String(url);
        const method = init?.method ?? "GET";
        const rispondi = (body: unknown, status = 200) =>
          Promise.resolve(new Response(JSON.stringify(body), { status }));
        if (path.includes("/decision") && method === "POST") {
          partite.decisioni += 1;
          return new Promise<Response>(() => {});
        }
        if (path.includes("/undo") && method === "POST") {
          partite.annullamenti += 1;
          return new Promise<Response>(() => {});
        }
        if (path.includes("decided_by=ai")) return rispondi(decided);
        if (path.includes("decided_by=human")) return rispondi([]);
        if (path.includes("/imports/terms")) return rispondi(TERMINI);
        if (path.includes("/imports/status")) return rispondi(STATO_NORMALE);
        return rispondi({}, 404);
      })
    );
    return partite;
  }

  it("con una decisione in volo i pulsanti di ogni scheda sono spenti ma tengono il fuoco, e non si decide due volte", async () => {
    const partite = stubInVolo();
    renderScreen();

    const ignoraAcqua = await screen.findByRole("button", { name: /^Ignora «Acqua»$/ });
    ignoraAcqua.focus();
    await userEvent.keyboard("{Enter}");

    await waitFor(() => expect(ignoraAcqua).toHaveAttribute("aria-disabled", "true"));
    expect(ignoraAcqua).not.toBeDisabled();
    expect(ignoraAcqua).toHaveFocus();
    // ogni pulsante di ogni scheda, non solo quello premuto: una decisione alla volta
    for (const nome of [
      /Forse «pasta»/,
      /^Ignora «Rigatoni»$/,
      /Crea un ingrediente nuovo per «Rigatoni»/,
      /Crea un ingrediente nuovo per «Acqua»/,
    ]) {
      const pulsante = screen.getByRole("button", { name: nome });
      expect(pulsante).toHaveAttribute("aria-disabled", "true");
      expect(pulsante).not.toBeDisabled();
    }

    await userEvent.click(ignoraAcqua);
    await userEvent.click(screen.getByRole("button", { name: /^Ignora «Rigatoni»$/ }));
    expect(partite.decisioni).toBe(1);
  });

  it("con un annullamento in volo ogni «Annulla» è spento ma tiene il fuoco, e non si annulla due volte", async () => {
    const decisa = (id: string, nome: string): ImportTerm => ({
      ...TERMINI[1], id, display_name: nome, decided_by: "ai", decided_action: "map",
      decided_name: nome.toLowerCase(), decided_at: "2026-10-01T10:00:00Z",
    });
    const partite = stubInVolo([decisa("t7", "Speck"), decisa("t8", "Bottarga")]);
    renderScreen();

    const annullaSpeck = await screen.findByRole("button", { name: "Annulla la decisione su «Speck»" });
    annullaSpeck.focus();
    await userEvent.keyboard("{Enter}");

    await waitFor(() => expect(annullaSpeck).toHaveAttribute("aria-disabled", "true"));
    expect(annullaSpeck).not.toBeDisabled();
    expect(annullaSpeck).toHaveFocus();
    const annullaBottarga = screen.getByRole("button", { name: "Annulla la decisione su «Bottarga»" });
    expect(annullaBottarga).toHaveAttribute("aria-disabled", "true");

    await userEvent.click(annullaBottarga);
    await userEvent.click(annullaSpeck);
    expect(partite.annullamenti).toBe(1);
  });
```

(`TERMINI`, `STATO_NORMALE`, `renderScreen`, `ImportTerm`, `waitFor`, `userEvent`, `vi` sono già nel file; `renderScreen` ora prende il client da `createTestQueryClient`, Task 3.)

- [ ] **Step 2: Passano**

Run (da `<worktree>/frontend`): `npx vitest run src/features/recipe-import/ImportQueueScreen.test.tsx`
Expected: PASS al primo colpo (è il comportamento di oggi, che nessuno provava). **Prova che sanno fallire**: in `TermCard.tsx` togli per un momento `busy={pending}` dal `Button` di «Ignora «…»» e rilancia: il primo test deve fallire (`aria-disabled` assente e due decisioni partite). Rimetti la riga (`git diff src/features/recipe-import/TermCard.tsx` vuoto).

- [ ] **Step 3: La suite, e commit**

Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: verde, `N_vitest` + 7 + 2.

```bash
git add frontend/src/features/recipe-import/ImportQueueScreen.test.tsx
git commit -m "test(coda): i pulsanti delle schede con una decisione o un annullamento in volo"
```

---

### Task 9: I documenti

**Files:**
- Modify: `next-steps.md`

- [ ] **Step 1: Le idee chiuse escono**

In `next-steps.md`, sotto «### Idee», togli le righe che cominciano con questi testi (cercale con `grep -n`; se una non c'è più, scrivilo nel report):

1. `- [idea] P3 · Oltre a \`ShoppingListScreen.test.tsx\`, anche \`IngredientScreen.test.tsx\` è fallito una volta`
2. `- [idea] P3 · \`ShoppingListScreen.test.tsx\` è fallito in alcune corse della suite intera sotto carico`
3. `- [idea] P3 · I test di schermata si costruiscono il client react-query con \`retry: false\``
4. `- [idea] P3 · La suite del backend stampa 8 \`StarletteDeprecationWarning\``
5. `- [idea] P3 · L'annullamento riconta \`occurrences\` caricando tutte le pagine in attesa`
6. `- [idea] P3 · Una prova e2e di \`style.spec.ts\` («il campo data si vede…») calcola la data con \`toISOString()\``
7. `- [idea] P3 · Il 409 «Due righe puntano allo stesso ingrediente» non dice quale`
8. `- [idea] P3 · Nella coda d'import nessun test di schermo prova i pulsanti di una voce mentre una decisione è in volo`

Le prime due restano se il Task 1 ha chiuso col Margine di autonomia (cadute ancora presenti): in quel caso, invece di toglierle, aggiungi in coda alla seconda ` — il 2026-10-13 attese a 4 s e client vero: <quante cadute su 18> dopo la cura, su <quale asserzione>`.

La riga `- [idea] P3 · Nel modulo della ricetta, dopo «Aggiungi «pasta»» …` **resta**: la chiude il piano 15.

- [ ] **Step 2: Le voci nuove**

1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte)_` (se un piano prima di questo l'ha già scritta così stanotte, lasciala).
2. Togli la riga della voce da «In corso» (`grep -n "pulizie-test" next-steps.md`); se «In corso» resta vuota, rimetti `_(niente)_`.
3. In cima a «Fatti (recenti)» aggiungi:
   ```markdown
   - [fatto] <data di oggi> · Pulizie dei test e del backend: attese di Testing Library a 4 s e prove a 15 s (la Lista e l'Anagrafica cadevano sotto carico); un client react-query solo per l'app e i test (`createAppQueryClient`, `createTestQueryClient` con i tentativi veri senza attesa), e una prova che nessun test se ne faccia uno; le date dell'e2e nel giorno di Roma; `HTTP_422_UNPROCESSABLE_CONTENT` e gli avvisi di Starlette come errori; l'annullamento riconta `occurrences` con una `COUNT`; il 409 delle due righe nomina l'ingrediente; i test della coda con una decisione in volo [Parte X, T3] → branch night/pulizie-test (da revisionare)
   ```
4. Se nella notte sono emerse altre cose da fare fuori da questo piano (per esempio test che la migrazione ha lasciato al Margine di autonomia), aggiungile come `idea` o `tbd` nella sezione giusta.

- [ ] **Step 3: Commit**

```bash
git add next-steps.md
git commit -m "docs: pulizie dei test e del backend fatte (da revisionare) — otto idee chiuse"
```

---

### Task 10: La verifica finale, e il report

- [ ] **Step 1: Il frontend**

Da `<worktree>/frontend`:

```bash
npx vitest run 2>&1 | grep -E "Test Files|Tests |Duration"
npm run typecheck
npx tsc -b --force
npm run lint
npm run build
```

Expected: vitest tutto verde — **`N_vitest` + 9** (1 + 5 + 1 + 2), in **`N_file` + 3** file (`waits.test.ts`, `queryClient.test.ts`, `noLocalQueryClient.test.ts`); se il numero differisce, scrivi nel report da dove viene. Typecheck, lint e build puliti. `npx tsc -b --force` perché `node_modules` è condiviso col checkout principale, e con lui il `tsbuildinfo`.

- [ ] **Step 2: Il backend**

Il comando di pytest, intero. Expected: verde, **`N_pytest` + 3** (la prova statica del Task 5, il conto del Task 6, il test nuovo del 409 del Task 7; quello dell'orfano è cambiato, non aggiunto), nessun avviso di Starlette. Se si è usato `spena_test_ptest`, ora `DROP DATABASE IF EXISTS spena_test_ptest WITH (FORCE)`.

- [ ] **Step 3: I grep**

Dalla radice del worktree, i cinque comandi di «Comandi di verifica». Expected: come scritto lì.

- [ ] **Step 4: L'e2e intera**

Con i comandi delle Global Constraints, su uno stack ricreato da zero. Expected: tutti verdi, `N_e2e` + 3. Poi `down -v` e `rm .env`, sempre.

- [ ] **Step 5: Il report**

Nel report della notte (`docs/night-reports/<data>.md` sul ramo: se c'è già una sezione di un altro piano, aggiungi la tua in fondo; altrimenti crealo con un titolo `# Notte del <data di oggi>`), per questo piano: il ramo e da dove parte (`master`); quale database dei test; i conti veri (vitest con la durata prima e dopo, pytest, e2e) contro quelli della Preparazione; la misura delle prove instabili prima, dopo le attese e dopo la migrazione (cadute su 18, e su quali asserzioni); i test cambiati nella migrazione e come (guasti resi permanenti, conteggi a 3), uno per riga; i test lasciati al Margine di autonomia, se ce ne sono; cosa fare al merge (vedi «Dipendenze»: gli `HTTP_422` di R2, la data di S15, i `new QueryClient(` di tutti gli altri rami); le scelte che Mattia può voler rivedere (le attese globali, la frase del 409). Niente da fare dopo il deploy. Niente push, niente merge, niente deploy.

```bash
git add docs/night-reports/
git commit -m "docs: report della notte, pulizie dei test e del backend"
```
