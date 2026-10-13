# Pulizie: le parole a video — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** la domanda di Open Food Facts diventa «È «…»?», senza l'articolo sbagliato; il titolo di una confezione senza prodotto nel foglio della cottura prende la maiuscola; una riga della bozza AI che è un non alimentare lo dice («non è un alimento») invece di «non in anagrafica»; la nota delle righe da creare dice il vero («Salvando lo cerco in anagrafica; se non c'è, lo creo in questo reparto.»); scegliere un ingrediente dal selettore del modulo aggancia la riga senza aggancio che porta lo stesso nome, invece di farne una seconda; nella Lista e in Sistema la spesa il testo della voce si legge con la maiuscola, solo a video.

**Architecture:** cinque cambiamenti del frontend (`OffSuggestionQuestion.tsx`, `CookSheet.tsx`, `formModel.ts` con `attachIngredient` e la nota del non alimentare, `RecipeForm.tsx`, `ListRow.tsx` e `StockingRow.tsx` con `capitalizeFirst`) e uno del backend: il campo `non_food` di `DraftIngredient`/`DraftIngredientOut`, vero quando `match_name` trova con certezza un non alimentare. Nessuna rotta nuova, nessuna migrazione, nessun token.

**Tech Stack:** FastAPI, pytest su Postgres vero (i finti dell'LLM in `tests/llm_fakes.py`); React 19, TypeScript, Vitest + Testing Library (jsdom), Playwright.

**Spec:** `docs/superpowers/specs/2026-10-13-pulizie-parole-design.md` (tutta: il §1 dice quali voci chiude, quale arriva dal piano 14 e quale passa al piano 20; il §3 le scelte delegate; il §4 le due scelte di comportamento, decise da Mattia il 2026-10-13).

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/pulizie-parole` (`.worktrees/` è già in `.gitignore`), ramo `night/pulizie-parole`, creato da **`master`**: il piano non dipende dalla catena. Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì (o dalle sue `backend/` e `frontend/`), mai dalla radice del checkout principale. Il checkout principale non si tocca: se vi trovi modifiche non committate, sono dell'utente. **Nessun push, nessun merge, nessun deploy. Mai `git stash`.** Niente letture né scritture sulla produzione.
- **I file che anche altri piani della notte toccano** — `frontend/src/features/stocking/OffSuggestionQuestion.tsx` e `StockingScreen.test.tsx` (S3), `frontend/src/features/stocking/StockingRow.tsx` e `StockingRow.test.tsx` (S3 riscrive il file intero), `frontend/src/features/shopping-list/ListRow.tsx` e `ListRow.test.tsx` (piano 13), `frontend/src/features/shopping-list/ShoppingListScreen.test.tsx`, `frontend/src/features/cooking/CookSheet.tsx` e il suo test (piano 7, R2, S12, S14, piano 13), `frontend/src/features/recipe-form/RecipeForm.tsx` e il suo test (piano 13, R8 e R2 nei test), `frontend/src/features/recipe-form/formModel.ts` (R8 lo usa), `frontend/src/domain/types.ts` (S12, S14, S15, R2, R8), `backend/app/services/ai_recipes.py` e `backend/app/schemas/ai.py` (R8), `frontend/e2e/style.spec.ts` e `ai-draft.spec.ts` (tutti), `next-steps.md`, il report della notte. Sul tuo ramo, che parte da `master`, sono come su `master`. Il piano descrive comunque ogni modifica a un file esistente contro un'ancora riconoscibile — una funzione, un elemento JSX, un testo esatto — e mai contro numeri di riga: **leggi il file com'è sul ramo prima di cambiarlo**. Le prove nuove vanno in fondo ai file o ai `describe`.
- **Le due decisioni fondanti** (`CLAUDE.md`): una ricetta non nomina un non alimentare. Questo piano non apre strade nuove: `non_food` è solo un'informazione per le parole del modulo, e le righe passano ancora da `_resolve_lines` e `write_recipe_ingredients`. **Il frontend non calcola logica di dominio**: se una riga della bozza è un non alimentare lo dice il server; il confronto dei nomi di `attachIngredient` è lo stesso di `addNewLine` (R12), che già c'è.
- **Le parole a video si copiano esattamente come sono scritte qui** (spec §2): «È «<nome>»?»; «<nome> non è un alimento, sarà escluso»; «Salvando lo cerco in anagrafica; se non c'è, lo creo in questo reparto.». Il nome di un ingrediente dentro una frase o un nome accessibile resta minuscolo; la maiuscola solo a video, dove un nome apre una riga (`capitalizeFirst`, spec T3 §4.7). Identificatori in inglese, commenti in italiano che dicono il perché.
- Tutto il colore passa dai token di `frontend/src/index.css`; nessun token nuovo; `grep -rn "emerald\|neutral-" frontend/src` resta vuoto. Ogni bersaglio resta almeno 44×44 px; a 375 px nessuna schermata scorre di lato.
- **Il type check è `npm run typecheck`** (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0 (settima lezione di `CLAUDE.md`).
- Controlli del frontend, da `<worktree>/frontend`: `npx vitest run` (non esiste `npm test`), `npm run typecheck`, `npm run lint`, `npm run build`.
- **Backend su Postgres vero.** Il database dei test è il container `spena-db-1` (porta 5433): se `docker ps --format '{{.Names}}'` non lo mostra, `docker start spena-db-1`. **Mai `docker compose up` dal worktree**, mai `-f docker-compose.prod.yml`. Questo ramo parte da `master` e **non aggiunge migrazioni**: usa `spena_test`, se è alla `0012` (vedi la Preparazione). Nel worktree non c'è un `.venv`: si usa quello del checkout principale; `python -m` mette la cartella corrente in testa a `sys.path`, quindi si prova l'`app` del worktree. Il comando, sempre da `<worktree>/backend` («il comando di pytest», con i percorsi che il task indica in coda):
  ```bash
  PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
  Se la Preparazione trova `spena_test` oltre la `0012`, ogni pytest prende davanti `TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_parole`. **Nessuna chiamata di rete nella suite**: l'LLM nei test è `FakeLlm` di `tests/llm_fakes.py`.
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

- [ ] Il ramo di partenza è `master`, e i file di questo piano sono quelli su cui è scritto (`master` era `b9be6bf`):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify master
  git diff --stat b9be6bf master -- \
    frontend/src/features/stocking/OffSuggestionQuestion.tsx frontend/src/features/cooking/CookSheet.tsx \
    frontend/src/features/stocking/StockingRow.tsx frontend/src/features/stocking/StockingRow.test.tsx \
    frontend/src/features/stocking/StockingScreen.test.tsx frontend/src/features/shopping-list/ \
    frontend/e2e/style.spec.ts \
    frontend/src/features/recipe-form/ frontend/src/domain/types.ts frontend/src/features/ai-draft/ \
    backend/app/services/ai_recipes.py backend/app/schemas/ai.py frontend/e2e/ai-draft.spec.ts
  ```
  Expected: un hash; il `diff --stat` **vuoto**. Se non è vuoto, `master` è andato avanti su questi file: applica le modifiche del piano sopra la versione di `master`, ancora per ancora, e scrivilo nel report.
- [ ] Il database dei test:
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d spena_test -tAc 'SELECT version_num FROM alembic_version'
  ```
  Expected: `0012`. Se stampa altro, **non toccare `spena_test`**: crea il database di questo ramo e usalo per tutta la notte (`TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_parole` davanti a ogni pytest), e scrivilo nel report:
  ```bash
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_parole WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_parole'
  ```
  (in quel caso, alla fine del Task 10, `DROP DATABASE IF EXISTS spena_test_parole WITH (FORCE)`).
- [ ] Dal checkout principale, allinea `node_modules` al lockfile:
  ```bash
  cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund
  ```
- [ ] Crea il worktree da `master` e collega `node_modules` (e solo quello: **niente `.env`**):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/pulizie-parole -b night/pulizie-parole master
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/pulizie-parole/frontend/node_modules
  ```
- [ ] La voce in `next-steps.md` del ramo passa a `in corso`. Cercala con `grep -n "pulizie-parole\|Pulizie: parole" next-steps.md`: toglila da dove sta e mettila sotto `## In corso` (al posto di `_(niente)_`) come
  ```markdown
  - [in corso] P3 · Pulizie: le parole a video — piano `docs/superpowers/plans/2026-10-13-pulizie-parole.md` → branch night/pulizie-parole [T3, Parte X]
  ```
  Se non la trovi, aggiungi solo questa riga. Commit:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/pulizie-parole
  git add next-steps.md
  git commit -m "next-steps: pulizie delle parole, in corso"
  ```
- [ ] La linea di partenza, dal worktree:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/pulizie-parole/frontend && npx vitest run 2>&1 | grep -E "Test Files|Tests "
  npx playwright test --list 2>/dev/null | tail -n 1
  cd ../backend && PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q 2>&1 | tail -n 1
  ```
  Expected: tutto verde. **Annota** `N_file`, `N_vitest`, `N_e2e`, `N_pytest`. Se una linea non è verde, fermati e scrivilo nel report.

---

## Review Focus

- **Una somiglianza incerta con un non alimentare** non deve far dire «non è un alimento» — Task 3 (la premessa su `match_name` è nel test).
- **Lo stesso nome scritto diversamente** («Farro», «farro ») per `attachIngredient` — Task 6 (confronto in minuscolo e senza spazi ai bordi, come `addNewLine`).
- **La riga agganciata da `attachIngredient` tiene dose e ruolo** — Task 6.
- **Il nome di un prodotto** resta com'è scritto; solo il nome dell'ingrediente prende la maiuscola, e i nomi accessibili no — Task 2.
- **Una bozza senza `non_food`** (un server di prima, le bozze finte di R8) resta «non in anagrafica» — Task 4.
- **La maiuscola della Lista e di Sistema la spesa è solo a video**: il testo salvato, la casella, la ✕, le icone e il campo della scadenza tengono il testo com'è scritto; e un `queryByText` in minuscolo che aspettava `null` va migrato anche lui, o passerebbe a vuoto — Task 7.

## Obiettivo e contesto

Sei punti in cui lo schermo dice qualcosa di sbagliato o di brutto: un articolo che non si accorda («È un «zucchina»?»), un nome in minuscolo in testa a una riga del foglio della cottura, una formula che dice «non in anagrafica» di qualcosa che in anagrafica c'è (come non alimentare), una promessa («lo creo io») che a volte non si mantiene, un modulo che con due gesti ragionevoli fa due righe dello stesso ingrediente e poi le rifiuta, e il testo delle voci della Lista e di Sistema la spesa in minuscolo in testa alla riga, l'unico posto dell'app senza la maiuscola a video. Sono voci `idea` piccole, decise nelle parole dalla delega di Mattia del 2026-10-13. Le due voci vicine che cambiavano cosa fa l'app le ha decise Mattia il 2026-10-13 (spec §4): la maiuscola a video nella Lista e in Sistema la spesa entra in questo piano; l'avviso sul nome non alimentare nel passo del nome è una voce a sé (piano 20).

## Decisioni prese

Di Mattia: **le scelte estetiche e tecniche di queste pulizie sono delegate a Claude** (2026-10-13); il comportamento non ovvio va confermato. La maiuscola solo a video (spec T3 §4.7) è sua.

Scelte di questo piano (**decise da Claude su delega di Mattia**, reversibili; la spec, §3):

1. **«È «<nome>»?»** per la domanda di Open Food Facts.
2. **`capitalizeFirst`** sul titolo di una confezione senza prodotto nel foglio della cottura.
3. **`non_food: bool`** in `DraftIngredient` e `DraftIngredientOut` (default `false`), vero solo per una coincidenza **certa** con un non alimentare; nel tipo TypeScript `non_food?: boolean`. La nota: **«<nome> non è un alimento, sarà escluso»**.
4. **«Salvando lo cerco in anagrafica; se non c'è, lo creo in questo reparto.»** al posto di «Non è in anagrafica: lo creo io salvando.»
5. **`attachIngredient(lines, ingredient)`** in `formModel.ts`: include la riga che ha già l'id; se no aggancia la riga senza aggancio con lo stesso nome (confronto di `addNewLine`); se no aggiunge.

Di Mattia, sulle due scelte di comportamento della spec (§4; **deciso da Mattia il 2026-10-13**):

6. **Il testo delle voci della Lista e di Sistema la spesa prende la maiuscola solo a video** (opzione B): `capitalizeFirst(item.raw_text)` dove il testo apre la riga — il `<span>` del testo in `ListRow` e il `<p className="font-medium">` del nome in `StockingRow`. Il testo salvato (`raw_text`) non cambia, e nemmeno i nomi accessibili, che lo mettono in mezzo a una frase («Togli cosa verde dalla lista», «Sfuso, senza marca: mele»): come Dispensa, ricette e foglio della cottura (spec T3 §4.7). Task 7.
7. **Un nome nuovo che coincide con un non alimentare lo dirà il passo del nome**, in una voce a sé: il piano 20 (`modulo-nota-nome`). Questo piano non lo fa e non tocca quella voce di `next-steps.md`.

## Criteri di accettazione

- [ ] La domanda dice «È «yogurt greco»?»; `grep -rn "È un «" frontend/src` vuoto.
- [ ] Nel foglio della cottura una confezione senza prodotto si legge «Pasta», una con prodotto «Total 0%»; i nomi accessibili restano minuscoli.
- [ ] `POST /recipes/ai-draft` porta `non_food` su ogni riga; vero per «carta forno» non alimentare, falso per «pasta» e per una somiglianza incerta.
- [ ] Il modulo dice «carta forno non è un alimento, sarà escluso» per quella riga, e «Zafferano non in anagrafica, sarà escluso» per una riga sconosciuta.
- [ ] Sotto una riga da creare: «Salvando lo cerco in anagrafica; se non c'è, lo creo in questo reparto.»; `grep -rn "lo creo io salvando" frontend` vuoto.
- [ ] Dopo «Aggiungi «farro»», scegliere «Farro» dai suggerimenti lascia una riga sola, agganciata, con la dose scritta.
- [ ] vitest, typecheck, lint, build, pytest e l'e2e intera verdi; nessun test indebolito; i test cambiati sono solo quelli che cercavano le parole vecchie o il testo di una voce della Lista o di Sistema la spesa in minuscolo (Task 7).
- [ ] Nella Lista «cosa verde» si legge «Cosa verde», in Sistema la spesa «mele» si legge «Mele»; la casella, la ✕ e le icone hanno ancora il nome com'è scritto («cosa verde», «Sfuso, senza marca: mele»); il testo mandato al server non cambia.
- [ ] `next-steps.md` aggiornato (Task 9), il report scritto (Task 10).

## Comandi di verifica

Da `<worktree>/frontend`: `npx vitest run`, `npm run typecheck`, `npm run lint`, `npm run build`. Da `<worktree>/backend`: il comando di pytest. Dalla radice di `<worktree>`:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -rn "È un «" frontend/src
grep -rn "lo creo io salvando" frontend
```

Expected: tutti vuoti. E l'e2e intera con i comandi delle Global Constraints.

## Fuori scope

- L'avviso su un nome nuovo che coincide con un non alimentare (spec §4.2): lo fa il piano 20, e la sua voce in `next-steps.md` resta aperta.
- La maiuscola nel dato (`raw_text` salvato com'è scritto) e nei nomi accessibili.
- Le altre parole dell'app.
- Ogni rotta nuova.

## Margine di autonomia

- **Liberi:** nomi di variabili locali e di aiuti dei test; l'ordine dei test; i commenti, purché dicano il perché.
- **Fissi:** le parole a video del piano; i nomi `non_food`, `nonFood`, `attachIngredient`.
- **Un test di oggi si cambia solo se cercava le parole che questo piano cambia** («È un «…»?», «lo creo io salvando», «pasta» minuscolo nel titolo del foglio, il testo di una voce della Lista o di Sistema la spesa in minuscolo): li elencano i task. Se ne serve un altro, scrivilo nel report con il perché.
- **Una decisione non coperta e non reversibile** → si ferma quel task, commit del lavoro parziale, `bloccato` con la domanda per Mattia, e si passa al successivo. Una scelta reversibile e a basso impatto → la più conservativa, annotata nel report.
- Se un test fallisce e non si risolve in modo ragionevole: niente test disattivati, niente asserzioni indebolite; `bloccato` con la diagnosi.

## Dipendenze

**Parte da `master`.** Non consuma niente dagli altri piani. Al merge:

- **R8** (piano 10) estrae le righe della bozza da `draft_recipe` in `_draft_from` (in `services/ai_recipes.py`), «senza cambiarla»: al merge `_draft_from` deve passare `non_food=non_food and match.certain` come fa qui `draft_recipe`. Così anche le righe della variante dicono «non è un alimento». R8 costruisce la risposta della variante in `_draft_out` (`api/recipes.py`): se lo fa come la bozza di oggi (`DraftIngredientOut(**vars(i))`) il campo arriva da sé; se elenca i campi uno per uno, al merge si aggiunge `non_food`. R8 aggiunge anche prove in `tests/services/test_ai_recipes.py`, in fondo come queste.
- **S3** (piano 1) sposta `describeSuggestion` da `OffSuggestionQuestion.tsx` in `wording.ts` e riscrive molte prove di `StockingScreen.test.tsx`: la riga della domanda (`<h2>`) e le due prove che la cercano si uniscono a mano, se git non ci riesce.
- **Il piano 7, R2, il piano 13** toccano `CookSheet.tsx` in punti diversi dal titolo; **il piano 13** cambia in `RecipeForm.tsx` la ✕ e i ruoli (righe diverse da `attach` e dalla nota) e aggiunge un `Checkbox` in `CookSheet.tsx`.
- **S3**, ancora: riscrive `StockingRow.tsx` intero, ma tiene `<p className="font-medium">{name}</p>`: al merge `capitalizeFirst` va lì, e le prove nuove di S3 (e di S14, S15, del piano 7) che cercano a video il nome di una voce della Lista o di Sistema la spesa in minuscolo — `getByText`/`findByText` in jsdom, `getByText(…, { exact: true })` o `toContainText` in Playwright — prendono la maiuscola come quelle del Task 7. I nomi accessibili restano com'erano.
- **Il piano 13** cambia in `ListRow.tsx` la casella (un `Checkbox`), non il `<span>` del testo: si uniscono a mano se git non ci riesce.
- **Il piano 14** passa i test di schermata a `createTestQueryClient`: i test nuovi di questo piano usano gli aiuti dei loro file, e al merge passano alla fabbrica con loro.

## Dopo il deploy (solo Mattia)

Niente: nessuna migrazione, nessun dato.

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `frontend/src/features/stocking/OffSuggestionQuestion.tsx`, `StockingScreen.test.tsx` | 1 | «È «…»?» |
| `frontend/src/features/cooking/CookSheet.tsx`, `CookSheet.test.tsx` | 2 | la maiuscola del titolo |
| `backend/app/services/ai_recipes.py`, `backend/app/schemas/ai.py`, `backend/tests/services/test_ai_recipes.py`, `backend/tests/api/test_recipes_ai_draft.py` (nuovo) | 3 | `non_food` |
| `frontend/src/domain/types.ts`, `frontend/src/features/recipe-form/formModel.ts`, `formModel.test.ts`, `frontend/src/features/ai-draft/AiDraftScreen.test.tsx` | 4 | la nota del non alimentare |
| `frontend/src/features/recipe-form/RecipeForm.tsx`, `RecipeForm.test.tsx`, `AiDraftScreen.test.tsx`, `frontend/e2e/ai-draft.spec.ts`, `frontend/e2e/style.spec.ts` | 5 | «Salvando lo cerco…» |
| `frontend/src/features/recipe-form/formModel.ts`, `formModel.test.ts`, `RecipeForm.tsx`, `RecipeForm.test.tsx` | 6 | `attachIngredient` |
| `frontend/src/features/shopping-list/ListRow.tsx`, `ListRow.test.tsx`, `ShoppingListScreen.test.tsx`, `frontend/src/features/stocking/StockingRow.tsx`, `StockingRow.test.tsx`, `StockingScreen.test.tsx`, `frontend/e2e/style.spec.ts` | 7 | la maiuscola a video nella Lista e in Sistema la spesa |
| `frontend/e2e/style.spec.ts` | 8 | una prova nuova |
| `next-steps.md` | 9 | i documenti |
| `docs/night-reports/<data>.md` | 10 | il report |

---

### Task 1: «È «…»?»

**Files:**
- Modify: `frontend/src/features/stocking/OffSuggestionQuestion.tsx`
- Test: `frontend/src/features/stocking/StockingScreen.test.tsx`

- [ ] **Step 1: I test**

In `frontend/src/features/stocking/StockingScreen.test.tsx`, le due righe che cercano la domanda,
```tsx
      expect(await screen.findByRole("heading", { name: "È un «yogurt greco»?" })).toBeDefined();
```
e
```tsx
      expect(screen.queryByRole("heading", { name: "È un «yogurt greco»?" })).toBeNull();
```
diventano, con `"È «yogurt greco»?"` al posto di `"È un «yogurt greco»?"`. Sopra la prima aggiungi `// senza articolo: «È un «zucchina»?» non si accordava (giro del 2026-10-07)`.

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/features/stocking/StockingScreen.test.tsx`
Expected: FAIL — non trova il titolo «È «yogurt greco»?».

- [ ] **Step 3: La domanda**

In `frontend/src/features/stocking/OffSuggestionQuestion.tsx`, `<h2 className="font-semibold">È un «{ingredientName}»?</h2>` diventa:

```tsx
      {/* senza articolo: «È un «zucchina»?» non si accordava, e un articolo giusto per ogni
          nome lo saprebbe solo un dizionario (giro del 2026-10-07) */}
      <h2 className="font-semibold">È «{ingredientName}»?</h2>
```

- [ ] **Step 4: Passano, e la suite**

Run: `npx vitest run src/features/stocking && npx vitest run && npm run typecheck && npm run lint && grep -rn "È un «" src`
Expected: tutto verde, `N_vitest` invariato; il `grep` vuoto.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/stocking/OffSuggestionQuestion.tsx frontend/src/features/stocking/StockingScreen.test.tsx
git commit -m "fix(parole): la domanda di Open Food Facts è «È «…»?», senza l'articolo che non si accordava"
```

---

### Task 2: Il titolo della confezione nel foglio della cottura

**Files:**
- Modify: `frontend/src/features/cooking/CookSheet.tsx`
- Test: `frontend/src/features/cooking/CookSheet.test.tsx`

- [ ] **Step 1: I test**

In `frontend/src/features/cooking/CookSheet.test.tsx`:

1. Nel test `"ogni riga porta marca, nota e stato attuale, non il solo nome"`, la riga `expect(aperta.textContent).toContain("pasta");` diventa `expect(aperta.textContent).toContain("Pasta");` (il titolo ora ha la maiuscola: è la parola che questo piano cambia).
2. In fondo a `describe("CookSheet", …)` aggiungi:
   ```tsx
     // la maiuscola solo a video, come le righe della Dispensa (spec T3 §4.7): il titolo di
     // una confezione senza prodotto è il nome dell'ingrediente, e apre la riga. Il nome di un
     // prodotto resta com'è scritto; i nomi accessibili restano in minuscolo
     it("una confezione senza prodotto si intitola con la maiuscola, una con prodotto col suo nome", () => {
       renderSheet();
       const aperta = screen.getByText("quella aperta").closest("li")!;
       expect(within(aperta).getByText("Pasta")).toBeInTheDocument();
       expect(within(aperta).getByRole("radiogroup").getAttribute("aria-label")).toMatch(/di pasta/);
       expect(screen.getByText("Total 0%")).toBeInTheDocument();
     });
   ```

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/features/cooking/CookSheet.test.tsx`
Expected: FAIL — il titolo è «pasta».

- [ ] **Step 3: Il titolo**

In `frontend/src/features/cooking/CookSheet.tsx`:

1. Accanto agli altri import, aggiungi `import { capitalizeFirst } from "../../lib/text";`.
2. Nel JSX della riga, `<span className="font-medium">{item.product_name ?? item.ingredient_name}</span>` diventa:
   ```tsx
                         {/* la maiuscola solo a video, dove il nome dell'ingrediente apre la
                             riga (spec T3 §4.7); il nome di un prodotto resta com'è scritto, e
                             `itemLabel` — il nome dei controlli — resta in minuscolo */}
                         <span className="font-medium">
                           {item.product_name ?? capitalizeFirst(item.ingredient_name)}
                         </span>
   ```
   La funzione `itemLabel` in cima al file **non** cambia.

- [ ] **Step 4: Passano, e la suite**

Run: `npx vitest run src/features/cooking && npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde, `N_vitest` + 1. Le prove di `RecipeDetailScreen.test.tsx` che aprono il foglio cercano «Pelati» (un prodotto): non cambiano.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/cooking/CookSheet.tsx frontend/src/features/cooking/CookSheet.test.tsx
git commit -m "fix(parole): nel foglio della cottura una confezione senza prodotto si intitola con la maiuscola"
```

---

### Task 3: Il backend dice quando una riga della bozza è un non alimentare

**Files:**
- Modify: `backend/app/services/ai_recipes.py`, `backend/app/schemas/ai.py`
- Test: `backend/tests/services/test_ai_recipes.py`
- Create: `backend/tests/api/test_recipes_ai_draft.py`

**Interfaces:**
- Produces: `DraftIngredient.non_food: bool = False`; `DraftIngredientOut.non_food: bool = False`; nel JSON di `POST /api/v1/recipes/ai-draft` ogni riga ha `non_food`.

- [ ] **Step 1: I test**

1. In `backend/tests/services/test_ai_recipes.py`:
   - nel test `test_una_voce_non_alimentare_non_si_aggancia_alla_bozza`, dopo `assert riga.confident is False`, aggiungi:
     ```python
             # e dice perché: il modulo scrive «non è un alimento», non «non in anagrafica»
             assert riga.non_food is True
     ```
   - nel test `test_una_voce_alimentare_continua_ad_agganciarsi_alla_bozza`, dopo `assert pasta.confident is True`, aggiungi `assert pasta.non_food is False`;
   - in fondo al file aggiungi:
     ```python
     async def test_una_somiglianza_incerta_con_un_non_alimentare_non_lo_dice(db_session):
         """`non_food` dice solo una coincidenza certa (nome o alias esatto): una somiglianza
         con «carta forno» non autorizza a dire che «carta forn» non è un alimento. La riga resta
         staccata (com'è oggi per ogni non alimentare) e «non in anagrafica»."""
         from app.services.ingredient_match import match_name

         db_session.add(
             Ingredient(name="carta forno", display_name="Carta forno",
                        category=IngredientCategory.CASA)
         )
         await db_session.flush()
         somiglianza = await match_name(db_session, "carta forn")
         # la premessa: c'è una somiglianza, e non è certa. Se cade, scegli un altro refuso
         assert somiglianza.ingredient_id is not None
         assert somiglianza.certain is False

         finto = FakeLlm({
             "title": "Torta", "description": None, "instructions": "1. cuoci", "servings": 2,
             "ingredients": [
                 {"name": "carta forn", "role": "secondary", "quantity_text": "1 foglio",
                  "category": "casa"}
             ],
         })
         riga = (await draft_recipe(db_session, "torta", client=finto)).ingredients[0]
         assert riga.ingredient_id is None
         assert riga.non_food is False
     ```
2. Crea `backend/tests/api/test_recipes_ai_draft.py`:
   ```python
   """La rotta della bozza AI consegna `non_food` di ogni riga.

   Il servizio lo calcola (tests/services/test_ai_recipes.py); qui si guarda che la rotta non lo
   perda: un campo che manca in `DraftIngredientOut` Pydantic lo scarterebbe senza dire niente.
   """

   from app.domain.rules import IngredientRole


   async def test_la_rotta_della_bozza_consegna_non_food(logged_client, monkeypatch):
       import app.api.recipes as rotte
       from app.services.ai_recipes import DraftIngredient, RecipeDraft

       async def bozza_finta(_session, _prompt):
           return RecipeDraft(
               title="Torta", description=None, instructions="1. cuoci", servings=2,
               ingredients=[
                   DraftIngredient(
                       raw_name="carta forno", role=IngredientRole.SECONDARY,
                       quantity_text="1 foglio", ingredient_id=None, matched_name=None,
                       confident=False, non_food=True,
                   ),
                   DraftIngredient(
                       raw_name="farina", role=IngredientRole.PRIMARY, quantity_text="200 g",
                       ingredient_id=None, matched_name=None, confident=False,
                       proposed_category="cereali",
                   ),
               ],
           )

       monkeypatch.setattr(rotte, "draft_recipe", bozza_finta)
       response = await logged_client.post("/api/v1/recipes/ai-draft", json={"prompt": "torta"})
       assert response.status_code == 200
       assert [riga["non_food"] for riga in response.json()["ingredients"]] == [True, False]
   ```

Run: il comando di pytest con `tests/services/test_ai_recipes.py tests/api/test_recipes_ai_draft.py`
Expected: FAIL — `AttributeError: 'DraftIngredient' object has no attribute 'non_food'` e `TypeError: … unexpected keyword argument 'non_food'`.

- [ ] **Step 2: Il campo**

1. In `backend/app/services/ai_recipes.py`, nella dataclass `DraftIngredient`, dopo `proposed_category: str | None = None` aggiungi:
   ```python
       # Vero quando la riga nomina con certezza (nome o alias esatto) un ingrediente non
       # alimentare: l'aggancio si stacca (una ricetta non lo può avere), e il modulo dice
       # «non è un alimento» invece di «non in anagrafica», che lì sarebbe falso.
       non_food: bool = False
   ```
2. In `draft_recipe`, nel `DraftIngredient(…)` dentro il ciclo delle righe, dopo l'argomento `proposed_category=(…),` aggiungi:
   ```python
                   # solo la coincidenza certa: una somiglianza con un non alimentare non
                   # dice che la riga lo sia, e lì resta «non in anagrafica»
                   non_food=non_food and match.certain,
   ```
3. In `backend/app/schemas/ai.py`, in `DraftIngredientOut`, dopo `proposed_category: str | None = None` aggiungi `non_food: bool = False`.

- [ ] **Step 3: Passano, e la suite**

Run: il comando di pytest con `tests/services/test_ai_recipes.py tests/api/test_recipes_ai_draft.py`, poi intero.
Expected: verde, `N_pytest` + 2 (le altre due prove sono cambiate, non nuove).

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/ai_recipes.py backend/app/schemas/ai.py backend/tests/services/test_ai_recipes.py backend/tests/api/test_recipes_ai_draft.py
git commit -m "feat(ai): una riga della bozza che è un non alimentare lo dice (non_food), solo sulla coincidenza certa"
```

---

### Task 4: Il modulo dice «non è un alimento»

**Files:**
- Modify: `frontend/src/domain/types.ts`, `frontend/src/features/recipe-form/formModel.ts`
- Test: `frontend/src/features/recipe-form/formModel.test.ts`, `frontend/src/features/ai-draft/AiDraftScreen.test.tsx`

**Interfaces:**
- Consumes: `non_food` nel JSON della bozza (Task 3).
- Produces: `DraftIngredient.non_food?: boolean`; `FormLine.nonFood: boolean` (falso per ogni riga che non viene da una bozza con `non_food: true`). Il Task 6 lo usa.

- [ ] **Step 1: I test**

1. In `frontend/src/features/recipe-form/formModel.test.ts`, dentro il `describe` che contiene il test con `.toBe("Zafferano non in anagrafica, sarà escluso")` (cercalo con `grep -n "non in anagrafica" src/features/recipe-form/formModel.test.ts`), dopo quel test aggiungi:
   ```ts
     // la bozza dice perché una riga non è agganciata: un non alimentare in anagrafica c'è,
     // e «non in anagrafica» sarebbe falso (Parte X)
     it("una riga che il server dice non alimentare lo dice, e resta esclusa", () => {
       const riga = lineFromDraft(
         bozza({ raw_name: "carta forno", ingredient_id: null, matched_name: null, confident: false, non_food: true }),
         0
       );
       expect(riga.nonFood).toBe(true);
       expect(matchNote(riga)).toBe("carta forno non è un alimento, sarà escluso");
       expect(savableLines([riga])).toEqual([]);
     });

     it("senza `non_food` una riga sconosciuta resta «non in anagrafica»", () => {
       const riga = lineFromDraft(
         bozza({ raw_name: "Zafferano", ingredient_id: null, matched_name: null, confident: false }),
         0
       );
       expect(riga.nonFood).toBe(false);
       expect(matchNote(riga)).toBe("Zafferano non in anagrafica, sarà escluso");
     });
   ```
2. In `frontend/src/features/ai-draft/AiDraftScreen.test.tsx`, accanto al test che cerca `/zafferano di Navelli.*non in anagrafica/i` (cercalo con `grep -n "non in anagrafica" src/features/ai-draft/AiDraftScreen.test.tsx`), aggiungi un test gemello che monta la schermata come quello, con la stessa bozza finta a cui aggiungi in coda agli `ingredients` la riga
   ```ts
   { raw_name: "carta forno", role: "secondary", quantity_text: "1 foglio", ingredient_id: null,
     matched_name: null, confident: false, proposed_category: null, non_food: true },
   ```
   e che verifica `expect(await screen.findByText("carta forno non è un alimento, sarà escluso")).toBeInTheDocument();`. Chiamalo `"una riga che il server dice non alimentare lo dice, invece di «non in anagrafica»"`. (Copia del test vicino il modo di montare la schermata e di fingere la bozza: è l'apparato del file.)

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/features/recipe-form/formModel.test.ts src/features/ai-draft/AiDraftScreen.test.tsx`
Expected: FAIL — `nonFood` è `undefined`, la nota è «carta forno non in anagrafica, sarà escluso»; il typecheck del test segnala `non_food` sconosciuto in `DraftIngredient` (vitest lo esegue lo stesso).

- [ ] **Step 3: Il tipo e il modello**

1. In `frontend/src/domain/types.ts`, in `interface DraftIngredient`, dopo `proposed_category: string | null;` aggiungi:
   ```ts
     /** La riga nomina con certezza un non alimentare: è staccata, e il modulo lo dice. Il
      * server lo manda sempre; facoltativo qui perché le bozze scritte a mano (i test, la
      * variante di R8) non lo portano, e senza vale «no». */
     non_food?: boolean;
   ```
2. In `frontend/src/features/recipe-form/formModel.ts`:
   - in `interface FormLine`, dopo `proposedCategory: string | null;` (e il suo commento) aggiungi:
     ```ts
       /** Vero solo per una riga della bozza che il server dice non alimentare (`non_food`):
        * non è agganciata e non si salva, e la nota lo dice invece di «non in anagrafica». */
       nonFood: boolean;
     ```
   - in `lineFromDraft`, dopo `proposedCategory: attached ? null : line.proposed_category ?? null,` aggiungi `nonFood: !attached && line.non_food === true,`;
   - in `lineFromIngredient`, `lineFromNewName` e `lineFromRecipe`, dopo la riga `proposedCategory: null,` (o `proposedCategory: category,` in `lineFromNewName`) aggiungi `nonFood: false,`;
   - in `matchNote`, la riga `return \`${line.label} non in anagrafica, sarà escluso\`;` diventa:
     ```ts
         // un non alimentare in anagrafica c'è: «non in anagrafica» sarebbe falso (Parte X).
         // Le parole del 422 del salvataggio, «non è un alimento»
         if (line.nonFood) return `${line.label} non è un alimento, sarà escluso`;
         return `${line.label} non in anagrafica, sarà escluso`;
     ```

- [ ] **Step 4: Passano, e la suite**

Run: `npx vitest run src/features/recipe-form src/features/ai-draft && npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde, `N_vitest` + 1 + 3. Se il typecheck segnala altri punti che costruiscono un `FormLine` a mano (su `master` non ce ne sono fuori da `formModel.ts`), aggiungi `nonFood: false` lì.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/domain/types.ts frontend/src/features/recipe-form/formModel.ts frontend/src/features/recipe-form/formModel.test.ts frontend/src/features/ai-draft/AiDraftScreen.test.tsx
git commit -m "fix(parole): una riga della bozza non alimentare dice «non è un alimento», non «non in anagrafica»"
```

---

### Task 5: «Salvando lo cerco in anagrafica; se non c'è, lo creo in questo reparto.»

**Files:**
- Modify: `frontend/src/features/recipe-form/RecipeForm.tsx`
- Test: `frontend/src/features/recipe-form/RecipeForm.test.tsx`, `frontend/src/features/ai-draft/AiDraftScreen.test.tsx`, `frontend/e2e/ai-draft.spec.ts`, `frontend/e2e/style.spec.ts`

- [ ] **Step 1: I test**

Le prove che cercano la frase vecchia cercano la nuova (sono le parole che questo piano cambia):

1. `frontend/src/features/recipe-form/RecipeForm.test.tsx`: `within(riga).getByText("Non è in anagrafica: lo creo io salvando.")` → `within(riga).getByText("Salvando lo cerco in anagrafica; se non c'è, lo creo in questo reparto.")`.
2. `frontend/src/features/ai-draft/AiDraftScreen.test.tsx`: `screen.findByText(/lo creo io salvando/i)` → `screen.findByText(/se non c'è, lo creo in questo reparto/)`.
3. `frontend/e2e/ai-draft.spec.ts`: `riga.getByText("Non è in anagrafica: lo creo io salvando.")` → `riga.getByText("Salvando lo cerco in anagrafica; se non c'è, lo creo in questo reparto.")`.
4. `frontend/e2e/style.spec.ts`: le due righe con `"Non è in anagrafica: lo creo io salvando."` → la frase nuova, allo stesso modo.

Run: `grep -rn "lo creo io salvando" src e2e`
Expected: solo `src/features/recipe-form/RecipeForm.tsx` (la frase vera, che lo Step 3 cambia).

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/features/recipe-form/RecipeForm.test.tsx src/features/ai-draft/AiDraftScreen.test.tsx`
Expected: FAIL — non trovano la frase nuova.

- [ ] **Step 3: La frase**

In `frontend/src/features/recipe-form/RecipeForm.tsx`, in `LineRow`, `<p className="text-xs text-ink-soft">Non è in anagrafica: lo creo io salvando.</p>` diventa:

```tsx
          {/* Quel che il server fa davvero (`_resolve_lines`): cerca il nome in anagrafica, e
              se lo trova collega quello — il reparto scelto qui allora non conta —; se no lo
              crea in questo reparto. «Non è in anagrafica: lo creo io» era falso per un nome
              che c'era già, offerto da «Aggiungi «…»» anche accanto ai suggerimenti */}
          <p className="text-xs text-ink-soft">
            Salvando lo cerco in anagrafica; se non c'è, lo creo in questo reparto.
          </p>
```

- [ ] **Step 4: Passano, e la suite**

Run: `npx vitest run && npm run typecheck && npm run lint && grep -rn "lo creo io salvando" src e2e`
Expected: tutto verde, `N_vitest` + 4; il `grep` vuoto.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/recipe-form/RecipeForm.tsx frontend/src/features/recipe-form/RecipeForm.test.tsx frontend/src/features/ai-draft/AiDraftScreen.test.tsx frontend/e2e/ai-draft.spec.ts frontend/e2e/style.spec.ts
git commit -m "fix(parole): sotto una riga da creare, «Salvando lo cerco in anagrafica; se non c'è, lo creo in questo reparto.»"
```

---

### Task 6: Scegliere un ingrediente aggancia la riga che ha lo stesso nome

**Files:**
- Modify: `frontend/src/features/recipe-form/formModel.ts`, `frontend/src/features/recipe-form/RecipeForm.tsx`
- Test: `frontend/src/features/recipe-form/formModel.test.ts`, `frontend/src/features/recipe-form/RecipeForm.test.tsx`

**Interfaces:**
- Consumes: `FormLine.nonFood` (Task 4), `comparableName` (già in `formModel.ts`).
- Produces: `attachIngredient(lines: FormLine[], ingredient: Ingredient): FormLine[]`.

- [ ] **Step 1: I test**

1. In `frontend/src/features/recipe-form/formModel.test.ts`: aggiungi `attachIngredient` all'import da `./formModel`; in fondo al file:
   ```ts
   describe("attachIngredient: scegliere un ingrediente dal selettore", () => {
     const FARRO: Ingredient = {
       id: "i7", name: "farro", display_name: "Farro", category: "cereali", kind: "food",
     };

     it("dopo «Aggiungi «farro»», scegliere «Farro» aggancia quella riga: una sola, con la sua dose", () => {
       const nuova = { ...lineFromNewName("farro", "cereali"), quantityText: "160 g", role: "secondary" as const };
       const righe = attachIngredient([nuova], FARRO);
       expect(righe).toHaveLength(1);
       expect(righe[0]).toMatchObject({
         key: nuova.key, label: "farro", ingredientId: "i7", matchedName: "farro",
         proposedCategory: null, included: true, quantityText: "160 g", role: "secondary",
       });
     });

     it("una riga dell'AI «non in anagrafica» con lo stesso nome si aggancia anche lei", () => {
       const ai = lineFromDraft(
         bozza({ raw_name: "Zafferano", ingredient_id: null, matched_name: null, confident: false }),
         0
       );
       const righe = attachIngredient([ai], ZAFFERANO);
       expect(righe).toHaveLength(1);
       expect(righe[0]).toMatchObject({ ingredientId: "i9", included: true, proposedCategory: null });
       expect(savableLines(righe)).toHaveLength(1);
     });

     it("un nome diverso fa una riga nuova", () => {
       const righe = attachIngredient([lineFromNewName("orzo", "cereali")], FARRO);
       expect(righe.map((riga) => riga.label)).toEqual(["orzo", "Farro"]);
     });

     it("una riga che lo indica già si include e basta", () => {
       const esclusa = { ...lineFromIngredient(FARRO), included: false };
       const righe = attachIngredient([esclusa], FARRO);
       expect(righe).toHaveLength(1);
       expect(righe[0].included).toBe(true);
     });
   });
   ```
   (`Ingredient` è già importato come tipo, `bozza`, `ZAFFERANO`, `lineFromDraft`, `lineFromIngredient`, `lineFromNewName`, `savableLines` sono già nel file.)
2. In `frontend/src/features/recipe-form/RecipeForm.test.tsx`, dentro `describe("R12: un ingrediente che non c'è si aggiunge dal modulo", …)`, in fondo:
   ```tsx
     // Dopo «Aggiungi «farro»» scegliere anche «Farro» dai suggerimenti faceva due righe, e
     // il salvataggio tornava col 409 delle due righe (T3 Consegna 6b): ora aggancia la riga
     it("dopo «Aggiungi «farro»», scegliere «Farro» dai suggerimenti aggancia quella riga invece di farne due", async () => {
       vi.stubGlobal(
         "fetch",
         vi.fn((url: unknown) =>
           Promise.resolve(
             new Response(
               JSON.stringify(
                 String(url).includes("/ingredients/search")
                   ? [{ id: "i7", name: "farro", display_name: "Farro", category: "cereali", kind: "food" }]
                   : []
               ),
               { status: 200 }
             )
           )
         )
       );
       const { save } = renderForm(valuesFromRecipe(DETAIL));

       await userEvent.click(await offri("farro"));
       await userEvent.click(screen.getByRole("button", { name: "Aggiungi alla ricetta" }));
       await userEvent.type(screen.getByLabelText("Quantità per farro"), "160 g");
       await userEvent.type(screen.getByLabelText("Aggiungi un ingrediente"), "farro");
       await userEvent.click(await screen.findByRole("option", { name: /Farro/ }));

       expect(screen.getAllByRole("button", { name: /^Togli farro$/i })).toHaveLength(1);
       await salva();
       expect(save).toHaveBeenCalledWith(
         expect.objectContaining({
           ingredients: expect.arrayContaining([
             expect.objectContaining({ ingredient_id: "i7", quantity_text: "160 g" }),
           ]),
         })
       );
     });
   ```
   (`offri` è la funzione del `describe`; `salva`, `renderForm`, `valuesFromRecipe`, `DETAIL` sono del file.)

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/features/recipe-form`
Expected: FAIL — `attachIngredient` non esiste; nel modulo ci sono due «Togli farro».

- [ ] **Step 3: La funzione, e il modulo che la usa**

1. In `frontend/src/features/recipe-form/formModel.ts`, subito dopo la funzione `addNewLine`, aggiungi:
   ```ts
   /** Aggancia l'ingrediente scelto dal selettore del modulo. Due righe sullo stesso
    * ingrediente sono un 409 del backend, e non vorrebbero dire niente:
    * - se una riga lo indica già, la si include e basta — che è anche il modo di confermare
    *   un aggancio incerto scegliendolo di persona;
    * - se una riga senza aggancio porta lo stesso nome (una riga nuova di «Aggiungi «…»», o
    *   una dell'AI «non in anagrafica»), si aggancia quella: è la stessa cosa, e salvando il
    *   server l'avrebbe collegata a lui comunque. Tiene dose e ruolo, perde il reparto
    *   proposto. Il confronto dei nomi è quello di `addNewLine` (T3 Consegna 6b);
    * - altrimenti, una riga nuova. */
   export function attachIngredient(lines: FormLine[], ingredient: Ingredient): FormLine[] {
     if (lines.some((line) => line.ingredientId === ingredient.id))
       return lines.map((line) =>
         line.ingredientId === ingredient.id ? { ...line, included: true } : line
       );
     const names = new Set(
       [ingredient.name, ingredient.display_name].map((name) => name.trim().toLowerCase())
     );
     const sameName = lines.find(
       (line) => line.ingredientId === null && names.has(comparableName(line))
     );
     if (sameName)
       return lines.map((line) =>
         line.key === sameName.key
           ? {
               ...line,
               ingredientId: ingredient.id,
               matchedName: ingredient.name,
               uncertain: false,
               included: true,
               proposedCategory: null,
               nonFood: false,
             }
           : line
       );
     return [...lines, lineFromIngredient(ingredient)];
   }
   ```
   (`Ingredient` è già fra i tipi importati in cima al file.)
2. In `frontend/src/features/recipe-form/RecipeForm.tsx`:
   - nell'import da `./formModel`, aggiungi `attachIngredient,` (in ordine alfabetico, prima di `QUANTITY_MAX`… o dove il lint lo vuole);
   - la funzione `attach` (con il suo commento interno sulle «due righe sullo stesso ingrediente») diventa:
     ```tsx
       // la regola delle righe doppie sta in `attachIngredient` (formModel.ts): una riga che
       // c'è già si include, una senza aggancio con lo stesso nome si aggancia
       function attach(ingredient: Ingredient) {
         onChange((prev) => ({ ...prev, lines: attachIngredient(prev.lines, ingredient) }));
       }
     ```
   - se `lineFromIngredient` non ha più usi in `RecipeForm.tsx`, togli il suo import (il lint lo dice).

- [ ] **Step 4: Passano, e la suite**

Run: `npx vitest run src/features/recipe-form && npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde, `N_vitest` + 4 + 5. I test di oggi su `attach` (l'aggancio incerto confermato scegliendolo, «il nome di una riga che c'è non ne aggiunge un'altra») passano senza modifiche.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/recipe-form/formModel.ts frontend/src/features/recipe-form/formModel.test.ts frontend/src/features/recipe-form/RecipeForm.tsx frontend/src/features/recipe-form/RecipeForm.test.tsx
git commit -m "fix(ricette): scegliere un ingrediente aggancia la riga senza aggancio con lo stesso nome, invece di farne una seconda"
```

---

### Task 7: La maiuscola a video nella Lista e in Sistema la spesa

Deciso da Mattia il 2026-10-13 (spec §4.1, opzione B): il testo di una voce apre la riga, e prende la maiuscola come i nomi della Dispensa, delle ricette e del foglio della cottura (Task 2). Solo a video: `raw_text` resta com'è scritto, e i nomi accessibili pure, perché lo mettono in mezzo a una frase.

**Files:**
- Modify: `frontend/src/features/shopping-list/ListRow.tsx`, `frontend/src/features/stocking/StockingRow.tsx`
- Test: `frontend/src/features/shopping-list/ListRow.test.tsx`, `frontend/src/features/stocking/StockingRow.test.tsx`, `frontend/src/features/shopping-list/ShoppingListScreen.test.tsx`, `frontend/src/features/stocking/StockingScreen.test.tsx`, `frontend/e2e/style.spec.ts`

Leggi i file com'è sul ramo prima di cambiarli.

- [ ] **Step 1: I test nuovi**

1. In fondo a `describe("ListRow", …)` di `frontend/src/features/shopping-list/ListRow.test.tsx`:
   ```tsx
     // la maiuscola solo a video, come Dispensa e ricette (spec T3 §4.7; Mattia, 2026-10-13):
     // il testo salvato resta com'è scritto, e anche i nomi accessibili, che lo mettono in
     // mezzo a una frase («Togli cosa verde dalla lista»)
     it("il testo scritto in minuscolo si legge con la maiuscola; i nomi accessibili restano com'è scritto", () => {
       renderRow({ ingredient_id: null, ingredient_name: null, raw_text: "cosa verde" });
       expect(screen.getByText("Cosa verde")).toBeDefined();
       expect(screen.queryByText("cosa verde")).toBeNull();
       expect(screen.getByRole("checkbox", { name: "cosa verde" })).toBeDefined();
       expect(screen.getByRole("button", { name: "Togli cosa verde dalla lista" })).toBeDefined();
     });
   ```
2. In fondo a `describe("StockingRow", …)` di `frontend/src/features/stocking/StockingRow.test.tsx`:
   ```tsx
     // come in Lista: la maiuscola solo a video (Mattia, 2026-10-13); le icone e il campo
     // della scadenza tengono il testo com'è scritto
     it("il nome della voce si legge con la maiuscola; i nomi accessibili restano com'è scritto", () => {
       renderRow();
       expect(screen.getByText("Mele")).toBeDefined();
       expect(screen.queryByText("mele")).toBeNull();
       expect(screen.getByRole("toolbar", { name: "Come entra in dispensa: mele" })).toBeDefined();
       expect(screen.getByRole("button", { name: "Sfuso, senza marca: mele" })).toBeDefined();
     });
   ```

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/features/shopping-list/ListRow.test.tsx src/features/stocking/StockingRow.test.tsx`
Expected: FAIL — non trovano «Cosa verde» e «Mele».

- [ ] **Step 3: La maiuscola**

1. In `frontend/src/features/shopping-list/ListRow.tsx`, accanto agli altri import aggiungi `import { capitalizeFirst } from "../../lib/text";`; il `<span>` del testo, `<span className={checked ? "text-ink-faint line-through" : ""}>{item.raw_text}</span>`, diventa:
   ```tsx
               {/* la maiuscola solo a video, dove il testo apre la riga (spec T3 §4.7;
                   Mattia, 2026-10-13): il testo salvato resta com'è scritto, e il nome della
                   casella e della ✕ pure, perché lo mettono in mezzo a una frase */}
               <span className={checked ? "text-ink-faint line-through" : ""}>
                 {capitalizeFirst(item.raw_text)}
               </span>
   ```
   L'`aria-label` della casella e il `label` della ✕ **non** cambiano.
2. In `frontend/src/features/stocking/StockingRow.tsx`, accanto agli altri import aggiungi `import { capitalizeFirst } from "../../lib/text";`; `<p className="font-medium">{name}</p>` diventa:
   ```tsx
             {/* la maiuscola solo a video, come in Lista (Mattia, 2026-10-13); `name` resta
                 com'è scritto per i nomi accessibili qui sotto, che lo mettono in una frase */}
             <p className="font-medium">{capitalizeFirst(name)}</p>
   ```
   `const name = item.raw_text;` e tutti gli altri usi di `name` **non** cambiano.

Run: `npx vitest run src/features/shopping-list/ListRow.test.tsx src/features/stocking/StockingRow.test.tsx`
Expected: le due prove nuove passano; in `StockingRow.test.tsx` cadono le due prove di oggi che cercano `getByText("mele")` (lo Step 4 le migra).

- [ ] **Step 4: Le prove di oggi che leggevano il testo in minuscolo**

Sono le parole che questo piano cambia. Cercano il testo a video della riga; i nomi accessibili (`{ name: … }`, `getByLabelText`) e le frasi che contengono il testo («è di un altro ingrediente: cosa strana», «Tolto dalla lista: pomodoro») **non** si toccano. Trovale, da `<worktree>/frontend`:

```bash
grep -nE 'ByText\("(pomodoro|pomodori|cosa verde)"\)' src/features/shopping-list/ShoppingListScreen.test.tsx
grep -nE 'ByText\("(yogurt greco|mele|cosa strana)"\)|of \["yogurt greco", "mele"\]' src/features/stocking/StockingScreen.test.tsx src/features/stocking/StockingRow.test.tsx
```

Expected (su `master` più lo Step 1): 5 righe nel primo; 19 nel secondo (16 in `StockingScreen.test.tsx`, 2 di oggi in `StockingRow.test.tsx` e il `queryByText("mele")` della prova nuova dello Step 1). In ognuna, tranne quella della prova nuova, il testo prende la maiuscola: `"pomodoro"` → `"Pomodoro"`, `"pomodori"` → `"Pomodori"`, `"cosa verde"` → `"Cosa verde"`, `"yogurt greco"` → `"Yogurt greco"`, `"mele"` → `"Mele"`, `"cosa strana"` → `"Cosa strana"`, e i due cicli `for (const testo of ["yogurt greco", "mele"])` → `["Yogurt greco", "Mele"]`. **Anche i `queryByText(…)` che aspettano `null`** (`queryByText("pomodoro")` in `ShoppingListScreen.test.tsx`, `queryByText("yogurt greco")` e i due `queryByText("cosa strana")` in `StockingScreen.test.tsx`): in minuscolo passerebbero a vuoto, senza più guardare niente. Rilanciati i due `grep`, il primo è vuoto e il secondo stampa solo il `queryByText("mele")` della prova nuova.

Poi in `frontend/e2e/style.spec.ts` (Playwright: `getByText(…, { exact: true })` e `toContainText` distinguono maiuscole e minuscole):

```bash
grep -nE 'toContainText\("mascarpone"\)|getByText\((lungo|libera|"bresaola"), \{ exact: true \}\)' e2e/style.spec.ts
```

Expected su `master`: 7 righe, in due prove.

1. In `test("a 375px nessuna schermata scorre di lato, e in lista si spunta toccando il nome", …)`, `await expect(etichetta).toContainText("mascarpone");` → `await expect(etichetta).toContainText("Mascarpone");`.
2. In `test("Sistema la spesa a 375px: una riga per voce, e un pannello alla volta sotto la sua voce", …)`, subito dopo `const libera = "prova sistemazione senza ingrediente";` aggiungi:
   ```ts
     // a video il testo di una voce prende la maiuscola (Mattia, 2026-10-13); i nomi
     // accessibili delle icone e dei pannelli restano com'è scritto
     const aVideo = (testo: string) => testo.charAt(0).toUpperCase() + testo.slice(1);
   ```
   e le sei righe trovate dal `grep` diventano `getByText(aVideo(lungo), { exact: true })`, `getByText("Bresaola", { exact: true })` (due) e `getByText(aVideo(libera), { exact: true })` (tre). Anche qui i due `toHaveCount(0)`: in minuscolo passerebbero a vuoto.

Rilanciato il `grep`, è vuoto.

- [ ] **Step 5: Passano, e la suite**

Run: `npx vitest run && npm run typecheck && npm run lint && npx playwright test --list 2>/dev/null | tail -n 1`
Expected: tutto verde, `N_vitest` + 9 + 2; `N_e2e` invariato (le prove e2e sono cambiate, non nuove; girano nel Task 8). Se cade un'altra prova che cercava a video il testo di una voce in minuscolo, migrala allo stesso modo e scrivila nel report; se ne cade una che cerca altro, fermati: è un comportamento che il piano non ha previsto.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/shopping-list/ListRow.tsx frontend/src/features/shopping-list/ListRow.test.tsx frontend/src/features/shopping-list/ShoppingListScreen.test.tsx frontend/src/features/stocking/StockingRow.tsx frontend/src/features/stocking/StockingRow.test.tsx frontend/src/features/stocking/StockingScreen.test.tsx frontend/e2e/style.spec.ts
git commit -m "fix(parole): nella Lista e in Sistema la spesa il testo della voce si legge con la maiuscola, solo a video"
```

---

### Task 8: Nel browser vero

Le parole cambiate le provano vitest e le prove e2e aggiornate ai Task 5 e 7; qui una prova nuova per la maiuscola del foglio della cottura, che solo uno stack vero porta dalla dispensa al foglio, e l'e2e intera con il contrasto dei due temi.

**Files:**
- Modify: `frontend/e2e/style.spec.ts`

- [ ] **Step 1: La prova**

In fondo a `frontend/e2e/style.spec.ts` aggiungi:

```ts
// --- Pulizie del 2026-10-13: le parole a video ---

test("nel foglio della cottura una confezione senza prodotto si legge con la maiuscola", async ({ page }) => {
  // «porro» del seme entra in dispensa senza prodotto (ricettaDiProva): il titolo della sua
  // confezione è il nome dell'ingrediente, e apre la riga (spec T3 §4.7)
  const ricetta = await ricettaDiProva(page);
  try {
    await page.goto(`/ricette/${ricetta.id}`);
    await page.getByRole("button", { name: "Cucina", exact: true }).click();
    const porro = page.getByRole("radiogroup", { name: /porro/ });
    await expect(porro).toBeVisible();
    const riga = page.getByRole("listitem").filter({ has: porro });
    await expect(riga.getByText("Porro", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Annulla", exact: true }).click();
  } finally {
    await ricetta.pulisci();
  }
});
```

Run (da `<worktree>/frontend`): `npm run typecheck && npm run lint && npx playwright test --list 2>/dev/null | tail -n 1`
Expected: puliti; `N_e2e` + 1.

- [ ] **Step 2: L'e2e intera**

Con i comandi delle Global Constraints. Expected: tutti verdi, `N_e2e` + 1, compresi «in ogni luogo ogni testo sta sopra 4,5:1» nei due temi, le prove del modulo e della bozza con la frase nuova, e quelle della Lista e di Sistema la spesa con la maiuscola (Task 7). Poi `down -v` e `rm .env`.

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/style.spec.ts
git commit -m "e2e: nel foglio della cottura una confezione senza prodotto si legge con la maiuscola"
```

---

### Task 9: I documenti

**Files:**
- Modify: `next-steps.md`

- [ ] **Step 1: Le idee chiuse escono**

In `next-steps.md`, sotto «### Idee», togli le righe che cominciano con (cercale con `grep -n`; se una non c'è più, scrivilo nel report):

1. `- [idea] P3 · La domanda di Open Food Facts in Sistema la spesa dice sempre «È un «…»?»`
2. `- [idea] P3 · Il titolo del foglio della cottura, per una confezione senza prodotto, è il nome dell'ingrediente in minuscolo`
3. `- [idea] P3 · Nella bozza AI, «non in anagrafica» è la formula sbagliata per una riga non alimentare`
4. `- [idea] P3 · «Non è in anagrafica: lo creo io salvando.» può essere falso`
5. `- [idea] P3 · Nel modulo della ricetta, dopo «Aggiungi «pasta»» scegliere anche «Pasta» dai suggerimenti fa due righe`
6. `- [idea] P3 · Lista e Sistema la spesa mostrano il testo della voce com'è stato scritto` (deciso da Mattia il 2026-10-13: la maiuscola solo a video, Task 7)

**Resta** `- [idea] P3 · Nel modulo, un nome nuovo che coincide con un non alimentare dell'anagrafica si scopre solo salvando…`: la chiude il piano 20 (`modulo-nota-nome`), deciso da Mattia il 2026-10-13. Non toccarla.

- [ ] **Step 2: Le voci nuove**

1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte)_` (se un piano prima di questo l'ha già scritta così stanotte, lasciala).
2. Togli la riga della voce da «In corso» (`grep -n "pulizie-parole" next-steps.md`); se «In corso» resta vuota, rimetti `_(niente)_`.
3. In cima a «Fatti (recenti)» aggiungi:
   ```markdown
   - [fatto] <data di oggi> · Pulizie delle parole: «È «…»?» nella domanda di Open Food Facts; il titolo di una confezione senza prodotto nel foglio della cottura con la maiuscola; una riga della bozza AI non alimentare dice «non è un alimento» (`non_food` dal server); «Salvando lo cerco in anagrafica; se non c'è, lo creo in questo reparto.»; scegliere un ingrediente aggancia la riga nuova con lo stesso nome invece di farne due (`attachIngredient`); il testo delle voci della Lista e di Sistema la spesa con la maiuscola, solo a video [T3 Consegna 6b, Parte X] → branch night/pulizie-parole (da revisionare)
   ```
4. Se nella notte sono emerse altre cose da fare fuori da questo piano, aggiungile come `idea` o `tbd`.

- [ ] **Step 3: Commit**

```bash
git add next-steps.md
git commit -m "docs: pulizie delle parole fatte (da revisionare) — sei idee chiuse; quella del non alimentare nel modulo la chiude il piano 20"
```

---

### Task 10: La verifica finale, e il report

- [ ] **Step 1: Il frontend**

Da `<worktree>/frontend`:

```bash
npx vitest run
npm run typecheck
npx tsc -b --force
npm run lint
npm run build
```

Expected: vitest tutto verde — **`N_vitest` + 11** (Task 2: 1; Task 4: 3; Task 6: 5; Task 7: 2), in **`N_file`** file (nessun file di test nuovo nel frontend); se il numero differisce, scrivi nel report da dove viene. Typecheck, lint e build puliti.

- [ ] **Step 2: Il backend**

Il comando di pytest, intero. Expected: verde, **`N_pytest` + 2**. Se si è usato `spena_test_parole`, ora `DROP DATABASE IF EXISTS spena_test_parole WITH (FORCE)`.

- [ ] **Step 3: I grep, e l'e2e intera**

I tre comandi di «Comandi di verifica» (tutti vuoti), poi l'e2e intera su uno stack ricreato da zero: tutti verdi, `N_e2e` + 1. Poi `down -v` e `rm .env`, sempre.

- [ ] **Step 4: Il report**

Nel report della notte (`docs/night-reports/<data>.md` sul ramo: se c'è già, aggiungi una sezione in fondo; altrimenti crealo con un titolo `# Notte del <data di oggi>`), per questo piano: il ramo e da dove parte (`master`); quale database dei test; i conti veri contro quelli della Preparazione; i test cambiati perché cercavano le parole vecchie o il testo di una voce in minuscolo (quelli del Task 7, e ogni altro trovato); le parole nuove che Mattia può voler rivedere; cosa fare al merge (vedi «Dipendenze»: `_draft_from` di R8, la domanda e le prove di S3, la maiuscola nello `StockingRow` riscritto da S3 e nelle prove nuove degli altri rami). Niente da fare dopo il deploy. Niente push, niente merge, niente deploy.

```bash
git add docs/night-reports/
git commit -m "docs: report della notte, pulizie delle parole"
```
