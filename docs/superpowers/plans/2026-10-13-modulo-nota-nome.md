# Modulo della ricetta: la nota modificabile e l'avviso sul nome non alimentare — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** nel modulo della ricetta la nota di ogni riga («da grattugiare», «a temperatura ambiente») si legge, si corregge e si toglie come la dose; e un nome nuovo che in anagrafica è un non alimentare lo dice il passo del nome mentre lo si scrive — con cosa fare e il collegamento all'Anagrafica — invece del 422 al salvataggio.

**Architecture:** nel backend una funzione sola, `ingredient_for_new_name` in `services/ingredient_match.py`, decide dove finisce un nome nuovo salvando; la usano `_resolve_lines` (al posto della sua condizione su `match_name`) e una rotta nuova di sola lettura, `GET /api/v1/ingredients/match?name=…`, che restituisce l'ingrediente (o `null`). `RecipeIngredientIn` toglie gli spazi ai bordi della nota e salva `null` una nota vuota. Nel frontend: `formModel.ts` (`NOTE_MAX`, la nota mandata pulita, il limite in `validationProblem`), il campo «Nota» o «Aggiungi una nota» in `LineRow`, e nel passo del nome di R12 `useNonFoodName` (la domanda al server) con `NonFoodNameNotice` (l'avviso) dentro `NewIngredientFields`, che guadagna tre prop facoltative. Nessuna migrazione, nessun token, nessuna dipendenza.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Pydantic 2, pytest su Postgres vero; React 19, TypeScript, @tanstack/react-query 5, React Router 7, Vitest + Testing Library (jsdom), Playwright.

**Spec:** `docs/superpowers/specs/2026-10-13-modulo-nota-nome-design.md` (tutta: §2 le decisioni di Mattia del 2026-10-13, §3 quelle di Claude su delega, §4 il comportamento esatto, §5 le parole a video, §7 il collegamento in un'altra scheda, deciso da Mattia). Il contesto della seconda metà è la spec delle pulizie delle parole, `docs/superpowers/specs/2026-10-13-pulizie-parole-design.md` §4.2 (opzione B, decisa da Mattia).

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/modulo-nota-nome` (`.worktrees/` è già in `.gitignore`), ramo `night/modulo-nota-nome`, creato da **`master`**: il piano non dipende dalla catena. Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì (o dalle sue `backend/` e `frontend/`), mai dalla radice del checkout principale. Il checkout principale non si tocca: se vi trovi modifiche non committate, sono dell'utente. **Nessun push, nessun merge, nessun deploy. Mai `git stash`.** Niente letture né scritture sulla produzione.
- **I file che anche altri piani della notte toccano** — `frontend/src/features/recipe-form/RecipeForm.tsx` e `RecipeForm.test.tsx` (piano 13 `pulizie-controlli`: la ✕ e i ruoli diventano `Button`; piano 15 `pulizie-parole`: `attach` e la frase sotto le righe da creare; R8 e R2 nei test; piano 14 `pulizie-test`: la fabbrica del client dei test), `frontend/src/features/recipe-form/formModel.ts` e `formModel.test.ts` (piano 15: `nonFood`, `attachIngredient`; R8 lo usa), `backend/app/api/recipes.py` (R2, R8, piano 12, piano 14: `_resolve_lines` col controllo delle righe doppie), `backend/app/api/ingredients.py` e `backend/app/schemas/ingredient.py` (S12: `_detail`, `update`, `IngredientDetailOut`, `IngredientPatch`), `backend/app/schemas/recipe.py` (R2, R8), `frontend/src/features/stocking/NewIngredientFields.tsx` (S3 lo usa in `IngredientChooser`, senza cambiarlo), `frontend/e2e/style.spec.ts` (tutti), `CLAUDE.md` (piano 12), `next-steps.md`, il report della notte. Sul tuo ramo, che parte da `master`, sono come su `master`. Il piano descrive comunque ogni modifica a un file esistente contro un'ancora riconoscibile — una funzione, un elemento JSX, una riga di codice esatta — e mai contro numeri di riga: **leggi il file com'è sul ramo prima di cambiarlo**. Le prove nuove vanno **in fondo** ai file o ai `describe`; i file di prova nuovi del backend sono file a sé, così i rami non scrivono negli stessi punti.
- **Le due decisioni fondanti** (`CLAUDE.md`): una ricetta non nomina un non alimentare. Questo piano non apre strade nuove per scrivere righe di ricetta: le righe passano ancora da `_resolve_lines` e dall'imbuto `write_recipe_ingredients`, che resta l'ultima linea. **Il frontend non calcola logica di dominio**: se un nome si collega a un ingrediente, a quale e se è un non alimentare lo dice il server (`GET /ingredients/match`, con la stessa funzione del salvataggio); il client legge il `kind` che arriva, come già fa `IngredientPicker`. La nota resta testo libero della riga: nessuna regola la legge.
- **Mai un vicolo cieco.** Se la domanda sul nome non risponde, o non ha ancora risposto, il passo del nome **non** si ferma: «Aggiungi alla ricetta» resta usabile e l'ultima linea resta il 422 di oggi al salvataggio, con la sua frase. L'avviso dice sempre cosa fare: un altro nome, o correggere l'anagrafica col collegamento.
- **Le parole a video si copiano esattamente come sono scritte qui** (spec §5): «Nota»; `Nota per <nome>`; il segnaposto «da grattugiare», «a temperatura ambiente»; «Aggiungi una nota» (nome accessibile `Aggiungi una nota: <nome>`); «La nota di «<nome>» è troppo lunga: massimo 300 caratteri.»; «In anagrafica questo nome è «<display_name>», un non alimentare: una ricetta non può averlo. Scrivi un altro nome; se invece è l'anagrafica a sbagliare, correggila.»; «Correggi «<display_name>» in Anagrafica»; «Si apre a parte: la ricetta resta qui com'è.»; «Cambia il nome: questo è un non alimentare.». Il nome di una riga dentro una frase o un nome accessibile resta com'è scritto (spec T3 §4.7). Identificatori in inglese, commenti in italiano che dicono il perché.
- **Pulsanti:** `Button` con `unavailableReason` per «non si può ancora», col perché sotto (la regola di casa, T3 Consegna 6a); nessun `<button>` scritto a mano nuovo (il piano 13 controlla che in `RecipeForm.tsx` non ne resti nessuno). Ogni bersaglio almeno 44×44 px (`min-h-11`); a 375 px nessuna schermata scorre di lato.
- Tutto il colore passa dai token di `frontend/src/index.css`; **nessun token nuovo**, nessuna riga nuova in `theme.test.ts`; `grep -rn "emerald\|neutral-" frontend/src` resta vuoto. Niente classi in conflitto sullo stesso elemento. Ogni testo sopra 4,5:1 nei due temi: lo misura `frontend/e2e/style.spec.ts`.
- **Il type check è `npm run typecheck`** (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0 (settima lezione di `CLAUDE.md`).
- Controlli del frontend, da `<worktree>/frontend`: `npx vitest run` (non esiste `npm test`), `npm run typecheck`, `npm run lint`, `npm run build`.
- **Backend su Postgres vero.** Il database dei test è il container `spena-db-1` (porta 5433): se `docker ps --format '{{.Names}}'` non lo mostra, `docker start spena-db-1`. **Mai `docker compose up` dal worktree**, mai `-f docker-compose.prod.yml`. Questo ramo parte da `master` e **non aggiunge migrazioni**: usa `spena_test`, se è alla `0012` (vedi la Preparazione). Nel worktree non c'è un `.venv`: si usa quello del checkout principale; `python -m` mette la cartella corrente in testa a `sys.path`, quindi si prova l'`app` del worktree. Il comando, sempre da `<worktree>/backend` («il comando di pytest», con i percorsi che il task indica in coda):
  ```bash
  PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
  Se la Preparazione trova `spena_test` oltre la `0012`, ogni pytest prende davanti `TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_nota`. Se un test sembra ignorare una modifica, `python -c 'import app; print(app.__file__)'` da `<worktree>/backend` (con lo stesso `PATH`) deve stampare un percorso dentro il worktree. **Nessuna chiamata di rete nella suite.**
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
    frontend/src/features/recipe-form/ frontend/src/features/stocking/NewIngredientFields.tsx \
    backend/app/api/recipes.py backend/app/api/ingredients.py backend/app/services/ingredient_match.py \
    backend/app/schemas/recipe.py backend/app/schemas/ingredient.py frontend/e2e/style.spec.ts CLAUDE.md
  ls frontend/src/features/recipe-form/api.ts frontend/src/features/recipe-form/useNonFoodName.ts \
    frontend/src/features/recipe-form/NonFoodNameNotice.tsx frontend/e2e/modulo-nota-nome.spec.ts \
    backend/tests/services/test_ingredient_for_new_name.py backend/tests/api/test_ingredients_match.py \
    backend/tests/api/test_recipes_note.py 2>&1 | grep -c "No such file"
  ```
  Expected: un hash; il `diff --stat` **vuoto**; `7` (nessuno dei file nuovi esiste). Se il `diff --stat` non è vuoto, `master` è andato avanti su questi file: applica le modifiche del piano sopra la versione di `master`, ancora per ancora, e scrivilo nel report.
- [ ] Il database dei test:
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d spena_test -tAc 'SELECT version_num FROM alembic_version'
  ```
  Expected: `0012`. Se stampa altro, **non toccare `spena_test`**: crea il database di questo ramo e usalo per tutta la notte (`TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_nota` davanti a ogni pytest), e scrivilo nel report:
  ```bash
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_nota WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_nota'
  ```
  (in quel caso, alla fine del Task 9, `DROP DATABASE IF EXISTS spena_test_nota WITH (FORCE)`).
- [ ] Dal checkout principale, allinea `node_modules` al lockfile:
  ```bash
  cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund
  ```
- [ ] Crea il worktree da `master` e collega `node_modules` (e solo quello: **niente `.env`**):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/modulo-nota-nome -b night/modulo-nota-nome master
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/modulo-nota-nome/frontend/node_modules
  ```
- [ ] La voce in `next-steps.md` del ramo passa a `in corso`. Cercala con `grep -n "modulo-nota-nome\|Modulo della ricetta: la nota" next-steps.md`: toglila da dove sta e mettila sotto `## In corso` (al posto di `_(niente)_`, se c'è) come
  ```markdown
  - [in corso] P3 · Modulo della ricetta: la nota modificabile e l'avviso sul nome non alimentare — piano `docs/superpowers/plans/2026-10-13-modulo-nota-nome.md` → branch night/modulo-nota-nome [T3 Consegna 6b, R12, Parte X]
  ```
  Se non la trovi, aggiungi solo questa riga. Commit:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/modulo-nota-nome
  git add next-steps.md
  git commit -m "next-steps: modulo della ricetta, nota e nome non alimentare, in corso"
  ```
- [ ] La linea di partenza, dal worktree:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/modulo-nota-nome/frontend && npx vitest run 2>&1 | grep -E "Test Files|Tests "
  npx playwright test --list 2>/dev/null | tail -n 1
  cd ../backend && PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q 2>&1 | tail -n 1
  ```
  Expected: tutto verde. **Annota** `N_file`, `N_vitest`, `N_e2e`, `N_pytest`. Se una linea non è verde, fermati e scrivilo nel report.

---

## Review Focus

- **Un nome scritto come alias di un non alimentare** («sapone piatti» per «Detersivo per i piatti»): l'avviso c'è e nomina la voce dell'anagrafica, non il testo scritto — Task 1 e Task 2 (l'alias), Task 6 (la frase dice «questo nome è «<display_name>»»).
- **Un nome che somiglia a un non alimentare ma non coincide** («detersivo»): nessun avviso, perché salvando nascerebbe un ingrediente nuovo — Task 1 e Task 2 (`null` per una somiglianza).
- **La domanda sul nome non risponde** (rete, 5xx) o non ha ancora risposto: il passo non si ferma, la riga si aggiunge, decide il salvataggio — Task 6.
- **Una nota svuotata o di soli spazi** si salva `null` e non `""`; gli spazi ai bordi non si salvano; un client che manda `""` ottiene `null` lo stesso — Task 3 (server) e Task 4 (modulo).
- **Tornati dall'Anagrafica dopo aver corretto il reparto**, l'avviso si rilegge da sé e sparisce — Task 6 (il fuoco della finestra rifà la domanda).

## Obiettivo e contesto

Il modulo della ricetta conserva la nota di ogni riga senza mostrarla: andava bene finché le note erano vuote, ma il piano 12 (`pulizia-dosi`) ne crea circa 10.000 dall'import e le mostra nel dettaglio, e chi ne trova una sbagliata deve poterla correggere o togliere. E il passo del nome di R12 lascia aggiungere un nome che salvando si collega a un non alimentare dell'anagrafica: lo scopre solo il 422 del salvataggio, dopo aver scritto tutto. Mattia ha deciso il 2026-10-13 che la nota diventa un campo come la dose, e che il passo del nome lo dica appena il nome è scritto (spec §2).

## Decisioni prese

Di Mattia (2026-10-13; spec §2):

1. **La nota della riga è un campo modificabile del modulo**, come la dose; massimo 300 caratteri; una nota vuota si salva `null`.
2. **Un nome nuovo che coincide con un non alimentare lo dice il passo del nome, appena scritto**, con una rotta di sola lettura sopra `match_name` e senza logica di dominio nel frontend; mai un vicolo cieco: un altro nome, o correggere l'anagrafica col collegamento.
3. Forma, parole e posizione delegate a Claude.

**Decise da Claude su delega di Mattia** (spec §3; reversibili):

4. `ingredient_for_new_name(session, raw_name) -> Ingredient | None` in `services/ingredient_match.py` è la sola regola: la usano `_resolve_lines` e la rotta.
5. `GET /api/v1/ingredients/match?name=` → `{"ingredient": IngredientOut | null}` (`NewNameMatchOut`), `name` 1–120, prima di `/{ingredient_id}`.
6. La domanda parte mentre si scrive, con l'attesa di 180 ms (`useDebounced`), e vale solo per il nome scritto adesso.
7. Con l'avviso, «Aggiungi alla ricetta» è spento con `unavailableReason`; «Annulla» resta. Senza risposta del server non si spegne niente.
8. Il collegamento apre `/anagrafica/ingrediente/<id>` in un'altra scheda (`target="_blank"`), e tornati la domanda si rifà (`refetchOnWindowFocus`). Deciso da Mattia il 2026-10-13 (spec §7, opzione A).
9. Nella riga: il campo «Nota» se la riga ha una nota, altrimenti «Aggiungi una nota» (`Button` `ghost` con `IconPlus`) che apre il campo col fuoco; solo sulle righe che partono salvando, sotto dose e ruoli.
10. Spazi ai bordi tolti e vuota → `null` nel backend (validatore di `RecipeIngredientIn`); il modulo non manda la chiave `note` per una nota vuota.
11. `NOTE_MAX = 300` in `formModel.ts`: `maxLength` del campo e controllo in `validationProblem`.

## Criteri di accettazione

- [ ] `GET /api/v1/ingredients/match?name=sapone%20piatti` (alias di un non alimentare) risponde l'ingrediente con `kind: "non_food"`; per un nome solo simile o sconosciuto `{"ingredient": null}`; 422 per un nome mancante, vuoto o di 121 caratteri; 401 senza sessione.
- [ ] Quel che la rotta dice è quel che il salvataggio fa: il nome che dice non alimentare dà il 422 «non è un alimento» in `POST /recipes`; il nome che collega a «pasta» si collega a «pasta» senza crearne un altro.
- [ ] `PUT /recipes/{id}` con `note: "  molto al dente  "` salva «molto al dente»; con `""` o `"   "` salva `null`; 301 caratteri → 422.
- [ ] Nel modulo: «Nota per pasta» mostra «al dente» e si corregge; svuotata, la riga parte senza nota; «Aggiungi una nota: basilico» apre il campo col fuoco; anche una riga nuova di R12 ha la sua nota.
- [ ] Nel passo del nome, «detersivo per i piatti» mostra l'avviso, il collegamento «Correggi «Detersivo per i piatti» in Anagrafica» (nuova scheda) e «Aggiungi alla ricetta» spento con «Cambia il nome: questo è un non alimentare.»; cambiato il nome, l'avviso sparisce; con il server giù il passo non si ferma.
- [ ] vitest, typecheck, lint, build, pytest e l'e2e intera verdi; nessun test di oggi cambiato né indebolito.
- [ ] `next-steps.md` aggiornato (l'idea del non alimentare nel modulo chiusa), `CLAUDE.md` con la riga sulla guardia nuova, il report scritto.

## Comandi di verifica

Da `<worktree>/frontend`: `npx vitest run`, `npm run typecheck`, `npm run lint`, `npm run build`. Da `<worktree>/backend`: il comando di pytest. Dalla radice di `<worktree>`:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -n "<button" frontend/src/features/recipe-form/RecipeForm.tsx frontend/src/features/recipe-form/NonFoodNameNotice.tsx
grep -n "match_name" backend/app/api/recipes.py
```

Expected: il primo vuoto; il secondo stampa **solo** le due righe `<button` che `RecipeForm.tsx` ha già su `master` (la ✕ e i ruoli, che toglie il piano 13) e niente in `NonFoodNameNotice.tsx`; il terzo vuoto (la regola passa da `ingredient_for_new_name`). E l'e2e intera con i comandi delle Global Constraints.

## Fuori scope

- Mostrare la nota nel dettaglio della ricetta (piano 12).
- Un nome nuovo che coincide con un **alimento**: salvando si collega a lui, com'è oggi (la frase sotto la riga la cambia il piano 15).
- I non alimentari fra i suggerimenti del selettore; le righe della bozza AI non alimentari (piano 15, `non_food`).
- Salvare una bozza del modulo per non perderla uscendo.
- Migrazioni, token, dipendenze.

## Margine di autonomia

- **Liberi:** nomi di variabili locali e di aiuti dei test; l'ordine dei test; i commenti, purché dicano il perché; le classi di spaziatura dentro i blocchi nuovi, purché a 375 px niente scorra di lato e i bersagli restino da 44 px.
- **Fissi:** le parole a video del piano; i nomi `ingredient_for_new_name`, `NewNameMatchOut`, `match_new_name` (la funzione della rotta: non `match`, che in Python è una parola chiave morbida), la rotta `GET /api/v1/ingredients/match` col parametro `name`, `NOTE_MAX`, `matchNewName`, `useNonFoodName`, `NON_FOOD_NAME_PROBLEM`, `NonFoodNameNotice`, le prop `onNameChange`, `nameNotice`, `nameProblem` di `NewIngredientFields`.
- **Nessun test di oggi si cambia.** Se uno cade, è un comportamento che il piano non ha previsto: fermati su quel task e scrivilo nel report con la diagnosi.
- **Una decisione non coperta e non reversibile** → si ferma quel task, commit del lavoro parziale, `bloccato` con la domanda per Mattia, e si passa al successivo. Una scelta reversibile e a basso impatto → la più conservativa, annotata nel report.
- Se un test fallisce e non si risolve in modo ragionevole: niente test disattivati, niente asserzioni indebolite; `bloccato` con la diagnosi.

## Dipendenze

**Parte da `master`.** Non consuma niente dagli altri piani. Al merge (i punti d'incontro, da riportare nel report):

- **Piano 13 (`pulizie-controlli`, da `night/r8-modifica-con-ai`)** cambia in `LineRow` la ✕ e i ruoli in `Button` e il contenitore della dose in `flex flex-wrap items-end gap-2`; aggiunge `import { IconX } from "../../components/ui/icons";`. Questo piano aggiunge `import { IconPlus } from "../../components/ui/icons";` e un blocco **dopo** quello della dose e dei ruoli: al merge le due righe d'import diventano `import { IconPlus, IconX } from "../../components/ui/icons";`, e i due blocchi stanno uno sotto l'altro. Il `grep -n "<button"` del piano 13 resta vuoto: qui non si scrivono `<button>`.
- **Piano 15 (`pulizie-parole`, da `master`)** aggiunge `nonFood` a `FormLine` e a ogni costruttore, `attachIngredient` dopo `addNewLine`, cambia `attach` e la frase «Salvando lo cerco in anagrafica…» in `LineRow`; aggiunge `attachIngredient` all'import di `formModel.test.ts` e prove in fondo al `describe` di R12 di `RecipeForm.test.tsx` e in fondo a `formModel.test.ts`. Questo piano tocca in `formModel.ts` il commento di `note`, `NOTE_MAX` accanto a `QUANTITY_MAX`, `validationProblem` e `lineBody`; aggiunge `NOTE_MAX` allo stesso import e i suoi `describe` in fondo agli stessi due file di prova. Le unioni sono righe vicine, non la stessa logica: si tengono tutte e due. Il piano 15 lascia aperta l'idea del non alimentare nel modulo «per il piano 20»: questo piano la chiude.
- **Piano 14 (`pulizie-test`, da `master`)** cambia `_resolve_lines` (l'insieme `seen` e `_RepeatedIngredient` prima di `resolved.append(…)`) e porta i test di schermata a `createTestQueryClient`, con una prova che vieta `new QueryClient(` nei test. Questo piano cambia in `_resolve_lines` solo le righe del `match_name` (tre righe, sopra), e non scrive client nuovi nei test: le prove nuove usano `renderForm` di `RecipeForm.test.tsx`, che il piano 14 migra. Il funzionamento «tornati dall'Anagrafica l'avviso si rilegge» chiede che la fabbrica del piano 14 lasci `refetchOnWindowFocus` com'è (il default, acceso): `useNonFoodName` lo chiede comunque in esplicito.
- **Piano 12 (`pulizia-dosi`, da `master`)** mostra la nota nel dettaglio e scrive le note nuove; tocca `api/recipes.py` (`_to_out`) e `CLAUDE.md` in punti diversi. Sul suo ramo il piano 12 non aggiunge voci al backlog per la nota nel modulo: c'è già questa.
- **R8 (piano 10)** usa `RecipeForm` nello schermo della variante: il campo della nota e l'avviso ci arrivano da sé. Aggiunge `derived_from` alla `DETAIL` dei test, che le prove nuove di questo piano usano senza riscriverla.
- **S12 (piano 2)** cambia `_detail` e `update` in `api/ingredients.py` e `IngredientDetailOut`/`IngredientPatch` in `schemas/ingredient.py`: questo piano aggiunge una rotta dopo `search` e una classe in fondo allo schema.
- **R2 (piano 8)** cambia `RecipeIngredientOut`/`RecipeOut` in `schemas/recipe.py`; questo piano cambia `RecipeIngredientIn` e l'import da `pydantic` in cima al file.
- **`style.spec.ts`**: la prova nuova va in fondo, come quelle degli altri rami.

## Dopo il deploy (solo Mattia)

Niente: nessuna migrazione, nessun dato da toccare.

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `backend/app/services/ingredient_match.py`, `backend/app/api/recipes.py`, `backend/tests/services/test_ingredient_for_new_name.py` (nuovo) | 1 | `ingredient_for_new_name`, `_resolve_lines` la usa |
| `backend/app/schemas/ingredient.py`, `backend/app/api/ingredients.py`, `backend/tests/api/test_ingredients_match.py` (nuovo) | 2 | `GET /ingredients/match` |
| `backend/app/schemas/recipe.py`, `backend/tests/api/test_recipes_note.py` (nuovo) | 3 | la nota pulita dal server |
| `frontend/src/features/recipe-form/formModel.ts`, `formModel.test.ts` | 4 | `NOTE_MAX`, la nota mandata, il limite |
| `frontend/src/features/recipe-form/RecipeForm.tsx`, `RecipeForm.test.tsx` | 5 | il campo «Nota» e «Aggiungi una nota» |
| `frontend/src/features/recipe-form/api.ts` (nuovo), `useNonFoodName.ts` (nuovo), `NonFoodNameNotice.tsx` (nuovo), `frontend/src/features/stocking/NewIngredientFields.tsx`, `RecipeForm.tsx`, `RecipeForm.test.tsx` | 6 | l'avviso nel passo del nome |
| `frontend/e2e/modulo-nota-nome.spec.ts` (nuovo), `frontend/e2e/style.spec.ts` | 7 | il browser vero |
| `next-steps.md`, `CLAUDE.md` | 8 | i documenti |
| `docs/night-reports/<data>.md` | 9 | il report |

---

### Task 1: Una funzione sola per dove finisce un nome nuovo

**Files:**
- Modify: `backend/app/services/ingredient_match.py`, `backend/app/api/recipes.py`
- Create: `backend/tests/services/test_ingredient_for_new_name.py`

**Interfaces:**
- Consumes: `match_name(session, raw_name) -> NameMatch` (esistente, invariata).
- Produces: `async def ingredient_for_new_name(session: AsyncSession, raw_name: str) -> Ingredient | None` in `app.services.ingredient_match`.

- [ ] **Step 1: Il test**

Crea `backend/tests/services/test_ingredient_for_new_name.py`:

```python
"""`ingredient_for_new_name`: dove finisce, salvando, un nome nuovo scritto nel modulo.

È la regola che `_resolve_lines` applica salvando e che `GET /ingredients/match` dice in
anticipo al passo del nome (piano 20): una funzione sola, perché l'avviso non dica una cosa
e il salvataggio ne faccia un'altra.
"""

from app.db.models.ingredient import IngredientCategory
from app.repositories.ingredients import add_alias, create_ingredient
from app.services.ingredient_match import ingredient_for_new_name


async def test_il_nome_canonico_si_collega_anche_scritto_diverso(db_session):
    pasta = await create_ingredient(db_session, "pasta", "Pasta", IngredientCategory.CEREALI)

    trovato = await ingredient_for_new_name(db_session, "  Pasta ")

    assert trovato is not None
    assert trovato.id == pasta.id


async def test_un_alias_porta_al_suo_ingrediente_anche_se_non_alimentare(db_session):
    detersivo = await create_ingredient(
        db_session, "detersivo per i piatti", "Detersivo per i piatti", IngredientCategory.CASA
    )
    await add_alias(db_session, detersivo.id, "sapone piatti", "manual")

    trovato = await ingredient_for_new_name(db_session, "Sapone piatti")

    assert trovato is not None
    assert trovato.id == detersivo.id
    assert trovato.kind == "non_food"


async def test_una_somiglianza_non_collega_salvando_nasce_un_ingrediente(db_session):
    await create_ingredient(
        db_session, "detersivo per i piatti", "Detersivo per i piatti", IngredientCategory.CASA
    )

    assert await ingredient_for_new_name(db_session, "detersivo") is None


async def test_un_nome_vuoto_non_collega_niente(db_session):
    assert await ingredient_for_new_name(db_session, "   ") is None
```

- [ ] **Step 2: Fallisce**

Run: il comando di pytest con `tests/services/test_ingredient_for_new_name.py`
Expected: FAIL — `ImportError: cannot import name 'ingredient_for_new_name'`.

- [ ] **Step 3: La funzione, e il salvataggio che la usa**

1. In `backend/app/services/ingredient_match.py`, in fondo al file (dopo `match_name`), aggiungi:
   ```python
   async def ingredient_for_new_name(session: AsyncSession, raw_name: str) -> Ingredient | None:
       """L'ingrediente a cui un nome nuovo del modulo si collega salvando, o `None`.

       `None` vuol dire che salvando l'ingrediente nasce (`_resolve_lines` in
       `app/api/recipes.py`). La regola è una sola e sta qui: la usa il salvataggio, e il
       passo del nome del modulo la chiede in anticipo (`GET /ingredients/match`), che così
       dice la stessa cosa che il salvataggio farà — per esempio che quel nome porta a un
       non alimentare, che l'imbuto `write_recipe_ingredients` rifiuterebbe. Solo la
       coincidenza certa di `match_name`: una somiglianza non collega, e salvando nasce un
       ingrediente nuovo.
       """
       match = await match_name(session, raw_name)
       if not match.certain or match.ingredient_id is None:
           return None
       # `match_name` l'ha appena letto: lo dà la identity map della sessione, senza query
       return await session.get(Ingredient, match.ingredient_id)
   ```
   (`Ingredient` e `AsyncSession` sono già importati in cima al file.)
2. In `backend/app/api/recipes.py`:
   - la riga `from app.services.ingredient_match import match_name` diventa `from app.services.ingredient_match import ingredient_for_new_name`;
   - in `_resolve_lines`, il blocco
     ```python
             # `match_name` e non una ricerca sul solo nome canonico: se la bozza dice
             # «pomodori» e l'anagrafica ha «pomodoro» con quell'alias, collegarsi è
             # giusto e creare sarebbe un duplicato travestito
             match = await match_name(session, line.name or "")
             if match.certain and match.ingredient_id is not None:
                 ingredient_id = match.ingredient_id
             else:
     ```
     diventa
     ```python
             # `match_name` (dentro `ingredient_for_new_name`) e non una ricerca sul solo
             # nome canonico: se la bozza dice «pomodori» e l'anagrafica ha «pomodoro» con
             # quell'alias, collegarsi è giusto e creare sarebbe un duplicato travestito. La
             # stessa funzione la chiede in anticipo il passo del nome del modulo
             # (`GET /ingredients/match`): l'avviso sul non alimentare dice quel che qui succede
             linked = await ingredient_for_new_name(session, line.name or "")
             if linked is not None:
                 ingredient_id = linked.id
             else:
     ```
     Il ramo `else:` con `create_ingredient(…)` resta com'è.

- [ ] **Step 4: Passano, e le prove del salvataggio**

Run: il comando di pytest con `tests/services/test_ingredient_for_new_name.py tests/api/test_recipes_create_ingredient.py tests/api/test_recipes_edit.py tests/api/test_recipes.py`, poi `grep -n "match_name" app/api/recipes.py`.
Expected: verde (le prove di oggi su «un nome che esiste già si collega» e sul 422 del non alimentare di R12 passano senza modifiche); il `grep` vuoto.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ingredient_match.py backend/app/api/recipes.py backend/tests/services/test_ingredient_for_new_name.py
git commit -m "refactor(ricette): ingredient_for_new_name, una regola sola per dove finisce un nome nuovo salvando"
```

---

### Task 2: `GET /api/v1/ingredients/match`

**Files:**
- Modify: `backend/app/schemas/ingredient.py`, `backend/app/api/ingredients.py`
- Create: `backend/tests/api/test_ingredients_match.py`

**Interfaces:**
- Consumes: `ingredient_for_new_name` (Task 1), `IngredientOut` (esistente).
- Produces: `class NewNameMatchOut(BaseModel): ingredient: IngredientOut | None`; la rotta `GET /api/v1/ingredients/match?name=<1..120 caratteri>` → `200 {"ingredient": {id, name, display_name, category, kind} | null}`, `422` per `name` mancante, vuoto o oltre 120, `401` senza sessione.

- [ ] **Step 1: Le prove**

Crea `backend/tests/api/test_ingredients_match.py`:

```python
"""`GET /ingredients/match`: il passo del nome del modulo chiede, prima di aggiungere la
riga, dove finirebbe quel nome salvando (piano 20).

La risposta è `ingredient_for_new_name`, la stessa funzione di `_resolve_lines`: le ultime
due prove lo verificano dal lato che conta, cioè che quel che la rotta dice è quel che il
salvataggio fa.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.repositories.ingredients import add_alias, create_ingredient

MATCH = "/api/v1/ingredients/match"


@pytest_asyncio.fixture
async def anagrafica(db_session):
    pasta = await create_ingredient(db_session, "pasta", "Pasta", IngredientCategory.CEREALI)
    await add_alias(db_session, pasta.id, "pennette", "manual")
    detersivo = await create_ingredient(
        db_session, "detersivo per i piatti", "Detersivo per i piatti", IngredientCategory.CASA
    )
    await add_alias(db_session, detersivo.id, "sapone piatti", "manual")
    await db_session.commit()
    return {"pasta": pasta, "detersivo": detersivo}


async def test_un_non_alimentare_torna_col_suo_nome_e_il_kind(logged_client, anagrafica):
    risposta = await logged_client.get(MATCH, params={"name": "Detersivo per i piatti"})

    assert risposta.status_code == 200
    trovato = risposta.json()["ingredient"]
    assert trovato["id"] == str(anagrafica["detersivo"].id)
    assert trovato["display_name"] == "Detersivo per i piatti"
    assert trovato["kind"] == "non_food"


async def test_un_alias_porta_all_ingrediente_che_lo_ha(logged_client, anagrafica):
    risposta = await logged_client.get(MATCH, params={"name": "sapone piatti"})

    trovato = risposta.json()["ingredient"]
    assert (trovato["id"], trovato["kind"]) == (str(anagrafica["detersivo"].id), "non_food")


async def test_un_alimento_torna_col_kind_food(logged_client, anagrafica):
    risposta = await logged_client.get(MATCH, params={"name": "pasta"})

    trovato = risposta.json()["ingredient"]
    assert (trovato["id"], trovato["kind"]) == (str(anagrafica["pasta"].id), "food")


async def test_un_nome_che_non_c_e_torna_null(logged_client, anagrafica):
    risposta = await logged_client.get(MATCH, params={"name": "zz mai visto"})

    assert risposta.status_code == 200
    assert risposta.json() == {"ingredient": None}


async def test_una_somiglianza_non_basta_torna_null(logged_client, anagrafica):
    """«detersivo» somiglia a «detersivo per i piatti», ma salvando nascerebbe un
    ingrediente nuovo: il passo del nome non deve dire «non alimentare»."""
    risposta = await logged_client.get(MATCH, params={"name": "detersivo"})

    assert risposta.json() == {"ingredient": None}


@pytest.mark.parametrize("params", [{}, {"name": ""}, {"name": "x" * 121}])
async def test_un_nome_mancante_vuoto_o_troppo_lungo_e_422(logged_client, params):
    assert (await logged_client.get(MATCH, params=params)).status_code == 422


async def test_senza_sessione_e_401(client):
    assert (await client.get(MATCH, params={"name": "pasta"})).status_code == 401


async def test_quel_che_la_rotta_dice_non_alimentare_il_salvataggio_lo_rifiuta(
    logged_client, anagrafica
):
    detto = (await logged_client.get(MATCH, params={"name": "sapone piatti"})).json()
    assert detto["ingredient"]["kind"] == "non_food"

    risposta = await logged_client.post("/api/v1/recipes", json={
        "title": "Pasta e sapone", "instructions": "1. no", "servings": 2, "source": "manual",
        "ingredients": [{"name": "sapone piatti", "category": "altro", "role": "primary"}],
    })

    assert risposta.status_code == 422
    assert "non è un alimento" in risposta.json()["detail"]


async def test_quel_che_la_rotta_collega_il_salvataggio_lo_collega(
    logged_client, db_session, anagrafica
):
    detto = (await logged_client.get(MATCH, params={"name": "pennette"})).json()
    assert detto["ingredient"]["id"] == str(anagrafica["pasta"].id)

    risposta = await logged_client.post("/api/v1/recipes", json={
        "title": "Pennette", "instructions": "1. cuoci", "servings": 2, "source": "manual",
        "ingredients": [{"name": "pennette", "category": "cereali", "role": "primary"}],
    })

    assert risposta.status_code == 201, risposta.text
    assert risposta.json()["ingredients"][0]["ingredient_id"] == str(anagrafica["pasta"].id)
    nuovi = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "pennette"))
    ).scalars().all()
    assert nuovi == []
```

- [ ] **Step 2: Falliscono**

Run: il comando di pytest con `tests/api/test_ingredients_match.py`
Expected: FAIL — le prove che aspettano 200 (anche le due sul salvataggio, alla loro prima riga) ricevono 422, perché `/match` finisce in `GET /{ingredient_id}` e «match» non è un UUID. Passano già il 401 e i tre 422.

- [ ] **Step 3: Lo schema e la rotta**

1. In fondo a `backend/app/schemas/ingredient.py` aggiungi:
   ```python
   class NewNameMatchOut(BaseModel):
       """`GET /ingredients/match`: l'ingrediente a cui un nome nuovo si collegherebbe
       salvando una ricetta, o `null` se salvando nascerebbe (piano 20). Intero, e non un
       sì/no: il modulo legge il `kind` che il server manda, il `display_name` per la frase e
       l'`id` per il collegamento all'anagrafica."""

       ingredient: IngredientOut | None
   ```
2. In `backend/app/api/ingredients.py`:
   - nell'import da `app.schemas.ingredient` aggiungi `NewNameMatchOut,` (dopo `MergeOut,`);
   - accanto agli altri import da `app.services`, aggiungi `from app.services.ingredient_match import ingredient_for_new_name`;
   - subito dopo la funzione `search` (la rotta `@router.get("/search", …)`), aggiungi:
     ```python
     @router.get("/match", response_model=NewNameMatchOut)
     async def match_new_name(
         # lo stesso limite di `RecipeIngredientIn.name`: è il nome che la riga manderebbe
         name: str = Query(min_length=1, max_length=120),
         session: AsyncSession = Depends(get_session),
     ) -> NewNameMatchOut:
         """Dove finirebbe questo nome, scritto nel passo del nome del modulo, salvando la
         ricetta (piano 20). Sola lettura.

         La risposta è `ingredient_for_new_name`, la stessa funzione che `_resolve_lines`
         chiama salvando: se dice un non alimentare, il salvataggio lo rifiuterebbe, e il
         modulo lo dice prima. Dichiarata prima di `/{ingredient_id}`, che altrimenti la
         prenderebbe e risponderebbe 422 su «match», che non è un UUID.
         """
         found = await ingredient_for_new_name(session, name)
         return NewNameMatchOut(
             ingredient=IngredientOut.model_validate(found) if found is not None else None
         )
     ```

- [ ] **Step 4: Passano, e la suite delle rotte degli ingredienti**

Run: il comando di pytest con `tests/api/test_ingredients_match.py tests/api/test_ingredients.py tests/api/test_registry_ingredients.py tests/api/test_auth.py`
Expected: verde.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/ingredient.py backend/app/api/ingredients.py backend/tests/api/test_ingredients_match.py
git commit -m "feat(ingredienti): GET /ingredients/match, dove finirebbe un nome nuovo salvando una ricetta"
```

---

### Task 3: La nota pulita dal server

**Files:**
- Modify: `backend/app/schemas/recipe.py`
- Create: `backend/tests/api/test_recipes_note.py`

**Interfaces:**
- Produces: `RecipeIngredientIn.note` senza spazi ai bordi, e `None` se vuota o di soli spazi, prima del limite di 300.

- [ ] **Step 1: Le prove**

Crea `backend/tests/api/test_recipes_note.py`:

```python
"""La nota di una riga si corregge e si toglie dal modulo (piano 20).

Il modulo non manda una nota vuota; ma l'autorità è qui: una nota vuota o di soli spazi si
salva `null`, e gli spazi ai bordi non fanno parte della nota.
"""

import pytest
import pytest_asyncio

from app.db.models.ingredient import IngredientCategory
from app.repositories.ingredients import create_ingredient


@pytest_asyncio.fixture
async def pasta(db_session):
    voce = await create_ingredient(db_session, "pasta", "Pasta", IngredientCategory.CEREALI)
    await db_session.commit()
    return voce


def _corpo(righe):
    return {
        "title": "Pasta al burro", "description": None, "category": None,
        "instructions": "Cuoci.", "servings": 2, "cost": None, "ingredients": righe,
    }


def _riga(pasta, note):
    return {"ingredient_id": str(pasta.id), "role": "primary", "quantity_text": "320 g", "note": note}


async def _scritta(client, pasta, note="al dente"):
    risposta = await client.post(
        "/api/v1/recipes", json={**_corpo([_riga(pasta, note)]), "source": "manual"}
    )
    assert risposta.status_code == 201, risposta.text
    return risposta.json()


async def _modifica(client, ricetta_id, pasta, note):
    return await client.put(f"/api/v1/recipes/{ricetta_id}", json=_corpo([_riga(pasta, note)]))


async def test_la_nota_si_corregge_con_la_modifica(logged_client, pasta):
    ricetta = await _scritta(logged_client, pasta)

    risposta = await _modifica(logged_client, ricetta["id"], pasta, "molto al dente")

    assert risposta.status_code == 200, risposta.text
    assert risposta.json()["ingredients"][0]["note"] == "molto al dente"
    riletta = (await logged_client.get(f"/api/v1/recipes/{ricetta['id']}")).json()
    assert riletta["ingredients"][0]["note"] == "molto al dente"


@pytest.mark.parametrize("vuota", ["", "   "])
async def test_una_nota_vuota_o_di_soli_spazi_si_salva_null(logged_client, pasta, vuota):
    ricetta = await _scritta(logged_client, pasta)

    risposta = await _modifica(logged_client, ricetta["id"], pasta, vuota)

    assert risposta.status_code == 200, risposta.text
    assert risposta.json()["ingredients"][0]["note"] is None


async def test_gli_spazi_ai_bordi_della_nota_non_si_salvano(logged_client, pasta):
    ricetta = await _scritta(logged_client, pasta, note="  da grattugiare  ")

    assert ricetta["ingredients"][0]["note"] == "da grattugiare"


async def test_la_nota_arriva_a_300_caratteri_e_non_oltre(logged_client, pasta):
    ricetta = await _scritta(logged_client, pasta)

    assert (await _modifica(logged_client, ricetta["id"], pasta, "a" * 301)).status_code == 422
    assert (await _modifica(logged_client, ricetta["id"], pasta, "a" * 300)).status_code == 200


async def test_una_riga_nuova_porta_la_sua_nota(logged_client):
    risposta = await logged_client.post("/api/v1/recipes", json={
        **_corpo([{"name": "zz nota", "category": "verdura", "role": "primary", "note": "a cubetti"}]),
        "source": "manual",
    })

    assert risposta.status_code == 201, risposta.text
    assert risposta.json()["ingredients"][0]["note"] == "a cubetti"
```

- [ ] **Step 2: Falliscono**

Run: il comando di pytest con `tests/api/test_recipes_note.py`
Expected: FAIL — le due note vuote tornano `""` e `"   "`, la nota con gli spazi torna con gli spazi. Le altre passano già.

- [ ] **Step 3: Il validatore**

In `backend/app/schemas/recipe.py`:

1. `from pydantic import BaseModel, Field, model_validator` diventa `from pydantic import BaseModel, Field, field_validator, model_validator`.
2. In `class RecipeIngredientIn`, subito dopo la riga `note: str | None = Field(default=None, max_length=300)`, aggiungi:
   ```python

       @field_validator("note", mode="before")
       @classmethod
       def _blank_note_is_none(cls, value: object) -> object:
           # Una nota vuota o di soli spazi non dice niente: si salva `null`, ed è così che il
           # modulo la toglie (piano 20). Gli spazi ai bordi non sono parte della nota. Prima
           # del limite di 300, che conta la nota vera.
           if isinstance(value, str):
               return value.strip() or None
           return value
   ```

- [ ] **Step 4: Passano, e la suite delle ricette**

Run: il comando di pytest con `tests/api/test_recipes_note.py tests/api/test_recipes.py tests/api/test_recipes_edit.py tests/api/test_recipes_create_ingredient.py`
Expected: verde.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/recipe.py backend/tests/api/test_recipes_note.py
git commit -m "feat(ricette): la nota di una riga si salva senza spazi ai bordi, e vuota è null"
```

---

### Task 4: La nota nel modello del modulo

**Files:**
- Modify: `frontend/src/features/recipe-form/formModel.ts`
- Test: `frontend/src/features/recipe-form/formModel.test.ts`

**Interfaces:**
- Produces: `export const NOTE_MAX = 300` in `formModel.ts`; `FormLine.note: string | null` invariato nel tipo (`null` = la riga non ha nota e il campo è chiuso; `""` = campo aperto e vuoto); `recipeBody` manda `note` senza spazi ai bordi e solo se non è vuota; `validationProblem` dice la nota troppo lunga.

- [ ] **Step 1: Le prove**

In `frontend/src/features/recipe-form/formModel.test.ts`:

1. nell'import da `./formModel`, aggiungi `NOTE_MAX,` (dopo `EMPTY_FORM,`);
2. in fondo al file aggiungi:
   ```ts
   describe("la nota della riga (piano 20)", () => {
     it("il limite è quello della colonna: 300", () => {
       expect(NOTE_MAX).toBe(300);
     });

     it("si manda senza spazi ai bordi; vuota o di soli spazi non si manda, e il server salva null", () => {
       const values = valuesFromRecipe(DETAIL);
       const [pasta, basilico] = values.lines;
       const corpo = recipeBody({
         ...values,
         lines: [{ ...pasta, note: "  molto al dente  " }, { ...basilico, note: "   " }],
       });
       expect(corpo.ingredients).toEqual([
         { ingredient_id: "i1", role: "primary", quantity_text: "320 g", note: "molto al dente" },
         { ingredient_id: "i2", role: "secondary", quantity_text: null },
       ]);
     });

     it("anche una riga nuova di R12 porta la sua nota", () => {
       const riga = { ...lineFromNewName("speck", "carne"), note: "a cubetti" };
       const corpo = recipeBody({ ...EMPTY_FORM, title: "Speck", instructions: "Taglia.", lines: [riga] });
       expect(corpo.ingredients).toEqual([
         { name: "speck", category: "carne", role: "primary", quantity_text: null, note: "a cubetti" },
       ]);
     });

     it("una nota oltre 300 caratteri si dice prima di salvare", () => {
       const values = valuesFromRecipe(DETAIL);
       const [pasta] = values.lines;
       expect(validationProblem({ ...values, lines: [{ ...pasta, note: "a".repeat(301) }] })).toBe(
         "La nota di «pasta» è troppo lunga: massimo 300 caratteri."
       );
       expect(validationProblem({ ...values, lines: [{ ...pasta, note: "a".repeat(300) }] })).toBeNull();
     });
   });
   ```
   (`DETAIL`, `EMPTY_FORM`, `lineFromNewName`, `recipeBody`, `validationProblem`, `valuesFromRecipe` sono già nel file.)

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/features/recipe-form/formModel.test.ts`
Expected: FAIL — `NOTE_MAX` non è esportato.

- [ ] **Step 3: Il modello**

In `frontend/src/features/recipe-form/formModel.ts`:

1. Il commento sopra le costanti, `// I limiti che \`RecipeFields\` applica nel backend.`, diventa `// I limiti che \`RecipeFields\` e \`RecipeIngredientIn\` applicano nel backend.` (il resto del commento resta). Subito dopo `export const QUANTITY_MAX = 100;` aggiungi:
   ```ts
   // la colonna `recipe_ingredients.note` è un varchar(300)
   export const NOTE_MAX = 300;
   ```
2. In `interface FormLine`, il commento sopra `note: string | null;`,
   ```ts
     /** La nota della riga salvata, portata com'è: il modulo non la mostra e non la
      * cambia, ma una modifica non deve perderla. */
   ```
   diventa
   ```ts
     /** La nota della riga («da grattugiare»), che il modulo mostra e fa correggere (piano
      * 20). `null`: la riga non ne ha, e al posto del campo c'è «Aggiungi una nota»; `""`:
      * il campo è aperto e vuoto. Vuota, salvando non si manda, e il server la tiene `null`. */
   ```
3. In `validationProblem`, subito dopo il blocco
   ```ts
     if (tooLong)
       return `La quantità di «${tooLong.label}» è troppo lunga: massimo ${QUANTITY_MAX} caratteri.`;
   ```
   aggiungi:
   ```ts

     const noteTooLong = savableLines(values.lines).find(
       (line) => (line.note ?? "").trim().length > NOTE_MAX
     );
     if (noteTooLong)
       return `La nota di «${noteTooLong.label}» è troppo lunga: massimo ${NOTE_MAX} caratteri.`;
   ```
4. In `lineBody`, le righe
   ```ts
     // la nota solo se c'è: una chiave `note: null` in più cambierebbe il corpo che
     // «Scrivi una ricetta» ha sempre mandato
     const note = line.note ? { note: line.note } : {};
   ```
   diventano
   ```ts
     // la nota solo se c'è: una chiave `note: null` in più cambierebbe il corpo che
     // «Scrivi una ricetta» ha sempre mandato. Senza spazi ai bordi; vuota non c'è, e il
     // server la salva `null` — è così che il modulo la toglie (piano 20)
     const noteText = line.note?.trim() ?? "";
     const note = noteText === "" ? {} : { note: noteText };
   ```

- [ ] **Step 4: Passano, e la suite**

Run: `npx vitest run src/features/recipe-form && npm run typecheck && npm run lint`
Expected: verde, `N_vitest` + 4. La prova di oggi «salvato senza toccare niente, torna identico, con la nota solo dove c'è» passa senza modifiche.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/recipe-form/formModel.ts frontend/src/features/recipe-form/formModel.test.ts
git commit -m "feat(ricette): il modello del modulo manda la nota pulita, e ne dice il limite"
```

---

### Task 5: Il campo «Nota» nella riga

**Files:**
- Modify: `frontend/src/features/recipe-form/RecipeForm.tsx`
- Test: `frontend/src/features/recipe-form/RecipeForm.test.tsx`

**Interfaces:**
- Consumes: `NOTE_MAX`, `FormLine.note` (Task 4); `Button` (`variant`, `icon`, `accessibleName`, `className`, `onClick`), `IconPlus`.
- Produces, a video: il campo con nome accessibile `Nota per <label>`; il pulsante con nome accessibile `Aggiungi una nota: <label>`.

- [ ] **Step 1: Le prove**

In fondo a `frontend/src/features/recipe-form/RecipeForm.test.tsx` (dopo l'ultimo `describe`) aggiungi:

```tsx
describe("la nota della riga (piano 20)", () => {
  it("si legge nel suo campo e si corregge; il salvataggio porta la nota nuova", async () => {
    stubCategories([[], 200]);
    const { save } = renderForm(valuesFromRecipe(DETAIL));

    const nota = screen.getByLabelText("Nota per pasta");
    expect(nota).toHaveValue("al dente");
    expect(nota).toHaveAttribute("maxlength", "300");
    await userEvent.clear(nota);
    await userEvent.type(nota, "molto al dente");
    await salva();

    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({
        ingredients: expect.arrayContaining([
          { ingredient_id: "i1", role: "primary", quantity_text: "320 g", note: "molto al dente" },
        ]),
      })
    );
  });

  it("svuotato il campo, la nota si toglie: la riga parte senza", async () => {
    stubCategories([[], 200]);
    const { save } = renderForm(valuesFromRecipe(DETAIL));

    await userEvent.clear(screen.getByLabelText("Nota per pasta"));
    await salva();

    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({
        ingredients: expect.arrayContaining([
          { ingredient_id: "i1", role: "primary", quantity_text: "320 g" },
        ]),
      })
    );
  });

  it("una riga senza nota offre «Aggiungi una nota», che apre il campo col fuoco", async () => {
    stubCategories([[], 200]);
    const { save } = renderForm(valuesFromRecipe(DETAIL));

    expect(screen.queryByLabelText("Nota per basilico")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Aggiungi una nota: basilico" }));

    const nota = screen.getByLabelText("Nota per basilico");
    expect(nota).toHaveFocus();
    expect(screen.queryByRole("button", { name: "Aggiungi una nota: basilico" })).toBeNull();
    await userEvent.type(nota, "fresco");
    await salva();

    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({
        ingredients: expect.arrayContaining([
          { ingredient_id: "i2", role: "secondary", quantity_text: null, note: "fresco" },
        ]),
      })
    );
  });

  it("aperto e lasciato vuoto, il campo non aggiunge niente al salvataggio", async () => {
    stubCategories([[], 200]);
    const { save } = renderForm(valuesFromRecipe(DETAIL));

    await userEvent.click(screen.getByRole("button", { name: "Aggiungi una nota: basilico" }));
    await salva();

    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({
        ingredients: expect.arrayContaining([
          { ingredient_id: "i2", role: "secondary", quantity_text: null },
        ]),
      })
    );
  });

  it("anche una riga nuova di R12 ha la sua nota", async () => {
    stubCategories([[], 200]);
    const { save } = renderForm(valuesFromRecipe(DETAIL));

    await userEvent.type(screen.getByLabelText("Aggiungi un ingrediente"), "zz tre");
    await userEvent.click(await screen.findByRole("button", { name: "Aggiungi «zz tre»" }));
    await userEvent.click(screen.getByRole("button", { name: "Aggiungi alla ricetta" }));
    await userEvent.click(screen.getByRole("button", { name: "Aggiungi una nota: zz tre" }));
    await userEvent.type(screen.getByLabelText("Nota per zz tre"), "a cubetti");
    await salva();

    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({
        ingredients: expect.arrayContaining([
          { name: "zz tre", category: "altro", role: "primary", quantity_text: null, note: "a cubetti" },
        ]),
      })
    );
  });
});
```

(`stubCategories`, `renderForm`, `salva`, `valuesFromRecipe`, `DETAIL` sono del file.)

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/features/recipe-form/RecipeForm.test.tsx`
Expected: FAIL — non c'è nessun campo «Nota per pasta» né il pulsante «Aggiungi una nota: basilico».

- [ ] **Step 3: Il campo**

In `frontend/src/features/recipe-form/RecipeForm.tsx`:

1. Accanto agli altri import da `../../components/ui/`, aggiungi `import { IconPlus } from "../../components/ui/icons";`.
2. Nell'import da `./formModel`, aggiungi `NOTE_MAX,` (dopo `QUANTITY_MAX,`).
3. In `function LineRow`, subito dopo la riga `const savableShape = line.ingredientId !== null || line.proposedCategory !== null;` aggiungi:
   ```tsx
     // vero dopo «Aggiungi una nota»: il campo nasce col fuoco, perché è lì che si scrive.
     // Una nota che c'era già si apre senza rubare il fuoco a nessuno
     const [focusNote, setFocusNote] = useState(false);
   ```
4. Sempre in `LineRow`, subito dopo la chiusura del blocco `{savableShape && (` che contiene il campo «Quantità» e il gruppo `Ruolo di …` (cioè subito prima di `</li>`), aggiungi:
   ```tsx

         {/* La nota della riga (piano 20): «da grattugiare», «a temperatura ambiente». Si
             corregge qui, e si toglie svuotando il campo (vuota si salva `null`). Il campo
             c'è solo dove la nota c'è: dodici campi vuoti su dodici righe allungherebbero il
             modulo di un telefono intero, e una nota è l'eccezione — le altre righe hanno
             «Aggiungi una nota», che apre il campo col fuoco. Svuotato resta aperto fino al
             salvataggio: chiuderlo mentre lo si cancella porterebbe via il fuoco. Solo dove la
             riga parte salvando, come la dose */}
         {savableShape &&
           (line.note === null ? (
             <Button
               variant="ghost"
               icon={IconPlus}
               accessibleName={`Aggiungi una nota: ${line.label}`}
               onClick={() => {
                 setFocusNote(true);
                 onUpdate({ note: "" });
               }}
               className="self-start"
             >
               Aggiungi una nota
             </Button>
           ) : (
             <label className="text-xs text-ink-soft">
               Nota
               <input
                 aria-label={`Nota per ${line.label}`}
                 value={line.note}
                 onChange={(e) => onUpdate({ note: e.target.value })}
                 maxLength={NOTE_MAX}
                 autoFocus={focusNote}
                 placeholder="«da grattugiare», «a temperatura ambiente»"
                 className="mt-1.5 text-ink"
               />
             </label>
           ))}
   ```

- [ ] **Step 4: Passano, e la suite**

Run: `npx vitest run src/features/recipe-form && npx vitest run && npm run typecheck && npm run lint`
Expected: verde, `N_vitest` + 4 + 5. Le prove di oggi (anche «una riga si toglie con la ✕, il ruolo si cambia, e la nota resta», e quelle di `AiDraftScreen.test.tsx` e `RecipeEditScreen.test.tsx`) passano senza modifiche.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/recipe-form/RecipeForm.tsx frontend/src/features/recipe-form/RecipeForm.test.tsx
git commit -m "feat(ricette): la nota di una riga si legge, si corregge e si toglie nel modulo"
```

---

### Task 6: Il passo del nome dice il non alimentare

**Files:**
- Create: `frontend/src/features/recipe-form/api.ts`, `frontend/src/features/recipe-form/useNonFoodName.ts`, `frontend/src/features/recipe-form/NonFoodNameNotice.tsx`
- Modify: `frontend/src/features/stocking/NewIngredientFields.tsx`, `frontend/src/features/recipe-form/RecipeForm.tsx`
- Test: `frontend/src/features/recipe-form/RecipeForm.test.tsx`

**Interfaces:**
- Consumes: `GET /api/v1/ingredients/match?name=` → `{ ingredient: Ingredient | null }` (Task 2); `apiFetch`, `useDebounced`, `ingredientPath(id, origin)` di `features/registry/origin.ts`, `IconExternalLink`.
- Produces: `matchNewName(name: string): Promise<{ ingredient: Ingredient | null }>` in `recipe-form/api.ts`; `useNonFoodName(name: string | null): Ingredient | null` e `NON_FOOD_NAME_PROBLEM` in `recipe-form/useNonFoodName.ts`; `NonFoodNameNotice({ ingredient }: { ingredient: Ingredient })`; in `NewIngredientFields` tre prop facoltative: `onNameChange?: (name: string) => void`, `nameNotice?: ReactNode`, `nameProblem?: string`.

- [ ] **Step 1: Le prove**

In `frontend/src/features/recipe-form/RecipeForm.test.tsx`:

1. `import { render, screen, within } from "@testing-library/react";` diventa `import { act, render, screen, waitFor, within } from "@testing-library/react";`; e subito sotto `import { QueryClient, QueryClientProvider } from "@tanstack/react-query";` aggiungi una riga a sé: `import { focusManager } from "@tanstack/react-query";` (una riga separata, così l'import del client, che il piano 14 cambia, resta com'è). Nell'import dei tipi da `../../domain/types` aggiungi `Ingredient`.
2. In fondo al file aggiungi:
   ```tsx
   describe("il passo del nome dice un non alimentare dell'anagrafica (piano 20)", () => {
     const DETERSIVO: Ingredient = {
       id: "i-det", name: "detersivo per i piatti", display_name: "Detersivo per i piatti",
       category: "casa", kind: "non_food",
     };

     /** `GET /ingredients/match` risponde con `risposta(nome)`; ogni altra chiamata con `[]`. */
     function stubMatch(risposta: (name: string) => Response) {
       const spy = vi.fn((url: unknown) => {
         const indirizzo = new URL(String(url), "http://spena.test");
         if (indirizzo.pathname.endsWith("/ingredients/match"))
           return Promise.resolve(risposta(indirizzo.searchParams.get("name") ?? ""));
         return Promise.resolve(new Response("[]", { status: 200 }));
       });
       vi.stubGlobal("fetch", spy);
       return spy;
     }

     function risponde(ingredient: Ingredient | null) {
       return new Response(JSON.stringify({ ingredient }), { status: 200 });
     }

     const comeDetersivo = (name: string) =>
       risponde(name.trim().toLowerCase() === "detersivo per i piatti" ? DETERSIVO : null);

     async function apriIlPasso(testo: string) {
       await userEvent.type(screen.getByLabelText("Aggiungi un ingrediente"), testo);
       await userEvent.click(await screen.findByRole("button", { name: `Aggiungi «${testo}»` }));
     }

     it("lo dice nel passo, col collegamento all'anagrafica, e la riga non si aggiunge", async () => {
       stubMatch(comeDetersivo);
       renderForm(valuesFromRecipe(DETAIL));

       await apriIlPasso("detersivo per i piatti");

       expect(
         await screen.findByText(
           "In anagrafica questo nome è «Detersivo per i piatti», un non alimentare: una ricetta non può averlo. Scrivi un altro nome; se invece è l'anagrafica a sbagliare, correggila."
         )
       ).toBeInTheDocument();
       const collegamento = screen.getByRole("link", {
         name: "Correggi «Detersivo per i piatti» in Anagrafica",
       });
       expect(collegamento).toHaveAttribute("href", "/anagrafica/ingrediente/i-det");
       expect(collegamento).toHaveAttribute("target", "_blank");
       expect(screen.getByText("Si apre a parte: la ricetta resta qui com'è.")).toBeInTheDocument();

       const aggiungi = screen.getByRole("button", { name: "Aggiungi alla ricetta" });
       expect(aggiungi).toHaveAttribute("aria-disabled", "true");
       expect(aggiungi).toHaveAccessibleDescription("Cambia il nome: questo è un non alimentare.");
       await userEvent.click(aggiungi);
       expect(screen.queryByRole("button", { name: "Togli detersivo per i piatti" })).toBeNull();
       expect(screen.getByLabelText("Come si chiama in generale?")).toBeInTheDocument();
     });

     it("cambiato il nome, l'avviso sparisce e la riga si aggiunge", async () => {
       stubMatch(comeDetersivo);
       renderForm(valuesFromRecipe(DETAIL));
       await apriIlPasso("detersivo per i piatti");
       await screen.findByText(/un non alimentare: una ricetta non può averlo/);

       const nome = screen.getByLabelText("Come si chiama in generale?");
       await userEvent.clear(nome);
       await userEvent.type(nome, "zucchine");

       await waitFor(() =>
         expect(screen.queryByText(/un non alimentare: una ricetta non può averlo/)).toBeNull()
       );
       const aggiungi = screen.getByRole("button", { name: "Aggiungi alla ricetta" });
       expect(aggiungi).not.toHaveAttribute("aria-disabled");
       await userEvent.click(aggiungi);
       expect(screen.getByRole("button", { name: "Togli zucchine" })).toBeInTheDocument();
     });

     it("se il server non risponde, il passo non si ferma: decide il salvataggio", async () => {
       const spy = stubMatch(() => new Response(JSON.stringify({ detail: "giù" }), { status: 500 }));
       renderForm(valuesFromRecipe(DETAIL));

       await apriIlPasso("detersivo per i piatti");
       await waitFor(() =>
         expect(spy.mock.calls.some(([url]) => String(url).includes("/ingredients/match"))).toBe(true)
       );

       expect(screen.queryByText(/un non alimentare/)).toBeNull();
       const aggiungi = screen.getByRole("button", { name: "Aggiungi alla ricetta" });
       expect(aggiungi).not.toHaveAttribute("aria-disabled");
       await userEvent.click(aggiungi);
       expect(screen.getByRole("button", { name: "Togli detersivo per i piatti" })).toBeInTheDocument();
     });

     it("tornati alla finestra dopo aver corretto l'anagrafica, l'avviso si rilegge", async () => {
       let attuale: Ingredient = DETERSIVO;
       stubMatch(() => risponde(attuale));
       renderForm(valuesFromRecipe(DETAIL));
       await apriIlPasso("detersivo per i piatti");
       await screen.findByText(/un non alimentare: una ricetta non può averlo/);

       // corretto in un'altra scheda: ora è un alimento; il ritorno alla finestra rifà la domanda
       attuale = { ...DETERSIVO, category: "altro", kind: "food" };
       try {
         act(() => focusManager.setFocused(false));
         act(() => focusManager.setFocused(true));
         await waitFor(() =>
           expect(screen.queryByText(/un non alimentare: una ricetta non può averlo/)).toBeNull()
         );
         expect(screen.getByRole("button", { name: "Aggiungi alla ricetta" })).not.toHaveAttribute(
           "aria-disabled"
         );
       } finally {
         focusManager.setFocused(undefined);
       }
     });
   });
   ```

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/features/recipe-form/RecipeForm.test.tsx`
Expected: FAIL — la prima, la seconda e la quarta non trovano l'avviso; la terza passa già (oggi il passo non chiede niente a nessuno).

- [ ] **Step 3: La domanda, l'avviso, il passo**

1. Crea `frontend/src/features/recipe-form/api.ts`:
   ```ts
   import { apiFetch } from "../../api/client";
   import type { Ingredient } from "../../domain/types";

   /** L'ingrediente a cui questo nome si collegherebbe salvando la ricetta, o `null` se
    * salvando nascerebbe (`GET /ingredients/match`, piano 20). La regola è del server — la
    * stessa di `_resolve_lines` — e qui non se ne copia niente. */
   export function matchNewName(name: string) {
     return apiFetch<{ ingredient: Ingredient | null }>(
       `/ingredients/match?${new URLSearchParams({ name })}`
     );
   }
   ```
2. Crea `frontend/src/features/recipe-form/useNonFoodName.ts`:
   ```ts
   import { useQuery } from "@tanstack/react-query";
   import type { Ingredient } from "../../domain/types";
   import { useDebounced } from "../../hooks/useDebounced";
   import { matchNewName } from "./api";

   // la stessa attesa del selettore degli ingredienti: una domanda per nome scritto, non
   // una per tasto
   const DEBOUNCE_MS = 180;

   /** Il perché sotto «Aggiungi alla ricetta» quando il nome è un non alimentare. */
   export const NON_FOOD_NAME_PROBLEM = "Cambia il nome: questo è un non alimentare.";

   /** Se il nome scritto nel passo del nome di R12 porta, salvando, a un non alimentare
    * dell'anagrafica: quell'ingrediente, o `null` (piano 20). `null` come argomento: il
    * passo è chiuso, e non si chiede niente.
    *
    * Lo dice il server, con la stessa funzione del salvataggio: il `kind` arriva, non si
    * calcola. La risposta vale solo per il nome scritto adesso — mentre si scrive, quella di
    * prima non dice niente — e `null` anche quando il server non risponde o non ha ancora
    * risposto: il passo non si ferma mai per una domanda senza risposta, e l'ultima linea
    * resta il 422 del salvataggio. `refetchOnWindowFocus` in esplicito: chi torna dalla
    * scheda dell'Anagrafica dopo averla corretta deve vedere la risposta nuova. */
   export function useNonFoodName(name: string | null): Ingredient | null {
     const typed = (name ?? "").trim();
     const settled = useDebounced(typed, DEBOUNCE_MS);
     const { data } = useQuery({
       queryKey: ["ingredient-match", settled.toLowerCase()],
       queryFn: () => matchNewName(settled),
       enabled: name !== null && settled !== "",
       refetchOnWindowFocus: true,
     });
     if (name === null || settled === "" || settled !== typed) return null;
     const ingredient = data?.ingredient;
     return ingredient?.kind === "non_food" ? ingredient : null;
   }
   ```
3. Crea `frontend/src/features/recipe-form/NonFoodNameNotice.tsx`:
   ```tsx
   import { Link } from "react-router-dom";
   import { IconExternalLink } from "../../components/ui/icons";
   import type { Ingredient } from "../../domain/types";
   import { ingredientPath } from "../registry/origin";

   /** L'avviso del passo del nome quando il nome è un non alimentare dell'anagrafica (piano
    * 20). Dice cosa fare, perché non sia un vicolo cieco: un altro nome, o correggere
    * l'anagrafica se è lei a sbagliare. «Questo nome è «…»» e non ««…» è»: il nome scritto
    * può essere un alias, e la voce da correggere è quella dell'anagrafica.
    *
    * Il collegamento apre la scheda dell'ingrediente in un'altra scheda del browser: uscire
    * dal modulo perderebbe la ricetta scritta fin qui. Tornati, `useNonFoodName` rifà la
    * domanda da sé. */
   export function NonFoodNameNotice({ ingredient }: { ingredient: Ingredient }) {
     return (
       <div role="status" className="flex flex-col gap-1">
         <p className="text-xs text-low">
           In anagrafica questo nome è «{ingredient.display_name}», un non alimentare: una ricetta
           non può averlo. Scrivi un altro nome; se invece è l'anagrafica a sbagliare, correggila.
         </p>
         <Link
           to={ingredientPath(ingredient.id, null)}
           target="_blank"
           rel="noopener"
           className="inline-flex min-h-11 items-center gap-1.5 self-start text-sm font-medium text-brand"
         >
           <IconExternalLink aria-hidden="true" className="size-[1.1em]" stroke={1.8} />
           Correggi «{ingredient.display_name}» in Anagrafica
         </Link>
         <p className="text-xs text-ink-soft">Si apre a parte: la ricetta resta qui com'è.</p>
       </div>
     );
   }
   ```
   Attenzione al testo del primo `<p>`: va a capo nel sorgente, ma a video è una riga sola con uno spazio fra «ricetta» e «non» (JSX unisce le righe con uno spazio). La prova dello Step 1 lo cerca intero: se il formattatore spezza diversamente, controlla che a video resti esattamente la frase della spec.
4. In `frontend/src/features/stocking/NewIngredientFields.tsx`:
   - `import { useId, useState, type FormEvent } from "react";` diventa `import { useId, useState, type FormEvent, type ReactNode } from "react";`;
   - nella destrutturazione delle prop, dopo `submitLabel = "Crea l'ingrediente",` aggiungi `onNameChange,`, `nameNotice,`, `nameProblem,`; nel tipo, dopo la riga `submitLabel?: string;` aggiungi:
     ```tsx
       /** Il nome scritto, a ogni tasto: lo legge il modulo della ricetta per chiedere al
        * server se è un non alimentare (piano 20). */
       onNameChange?: (name: string) => void;
       /** Un avviso sul nome scritto, sotto il suggerimento del campo. */
       nameNotice?: ReactNode;
       /** Il nome scritto non si può usare, e perché: spegne il pulsante come il nome vuoto,
        * col perché sotto di lui. */
       nameProblem?: string;
     ```
   - in `submit`, la riga `if (trimmed === "" || busy) return;` diventa `if (trimmed === "" || busy || nameProblem) return;`;
   - l'`onChange` del campo, `onChange={(e) => setName(e.target.value)}`, diventa
     ```tsx
               onChange={(e) => {
                 setName(e.target.value);
                 onNameChange?.(e.target.value);
               }}
     ```
   - subito dopo il `<p id={hintId} …>Il nome che scriveresti in lista: …</p>` aggiungi `{nameNotice}`;
   - nel `Button` di invio, `unavailableReason={trimmed === "" ? "Scrivi il nome per crearlo." : undefined}` diventa `unavailableReason={trimmed === "" ? "Scrivi il nome per crearlo." : nameProblem}`.
5. In `frontend/src/features/recipe-form/RecipeForm.tsx`:
   - subito dopo `import { CategoryField } from "./CategoryField";` aggiungi:
     ```tsx
     import { NonFoodNameNotice } from "./NonFoodNameNotice";
     import { NON_FOOD_NAME_PROBLEM, useNonFoodName } from "./useNonFoodName";
     ```
   - subito dopo `const [creating, setCreating] = useState<string | null>(null);` aggiungi:
     ```tsx
       // il nome che si sta scrivendo nel passo di R12, e se salvando porterebbe a un non
       // alimentare dell'anagrafica: lo dice il server, con la regola del salvataggio (piano 20)
       const [newName, setNewName] = useState("");
       const nonFoodName = useNonFoodName(creating === null ? null : newName);
     ```
   - subito prima di `function cancelNew() {` aggiungi:
     ```tsx
       function startNew(name: string) {
         setCreating(name);
         // il passo parte col nome dato da «Aggiungi «…»»: la domanda parte da lì
         setNewName(name);
       }

     ```
   - in `<IngredientPicker …>`, `onCreate={setCreating}` diventa `onCreate={startNew}`;
   - in `<NewIngredientFields …>`, dopo `onCancel={cancelNew}` aggiungi:
     ```tsx
                   onNameChange={setNewName}
                   nameNotice={nonFoodName && <NonFoodNameNotice ingredient={nonFoodName} />}
                   nameProblem={nonFoodName ? NON_FOOD_NAME_PROBLEM : undefined}
     ```
   - nel commento sopra il passo, `{/* Il passo di R12: il nome generico e il reparto, solo del cibo. …`, aggiungi in fondo, prima di `*/}`: ` Un nome che salvando porterebbe a un non alimentare lo dice qui, mentre lo si scrive (piano 20), invece del 422 al salvataggio.`

- [ ] **Step 4: Passano, e la suite**

Run: `npx vitest run src/features/recipe-form src/features/stocking && npx vitest run && npm run typecheck && npm run lint`
Expected: verde, `N_vitest` + 4 + 5 + 4. Le prove di oggi di `MatchPanel` e `StockingScreen` (che usano `NewIngredientFields` senza le prop nuove) e quelle di R12 passano senza modifiche.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/recipe-form/api.ts frontend/src/features/recipe-form/useNonFoodName.ts frontend/src/features/recipe-form/NonFoodNameNotice.tsx frontend/src/features/stocking/NewIngredientFields.tsx frontend/src/features/recipe-form/RecipeForm.tsx frontend/src/features/recipe-form/RecipeForm.test.tsx
git commit -m "feat(ricette): il passo del nome dice subito un non alimentare dell'anagrafica, col collegamento per correggerlo"
```

---

### Task 7: Nel browser vero

**Files:**
- Create: `frontend/e2e/modulo-nota-nome.spec.ts`
- Modify: `frontend/e2e/style.spec.ts` (una prova in fondo)

- [ ] **Step 1: La prova del flusso**

Crea `frontend/e2e/modulo-nota-nome.spec.ts`:

```ts
import { expect, test, type Page } from "@playwright/test";

/**
 * Il piano 20 nel browser vero, a 375×812: la nota di una riga si corregge, si toglie e si
 * aggiunge dal modulo di modifica, e arriva al server; e nel passo del nome un non
 * alimentare del seme («detersivo per i piatti») lo dice subito, col collegamento che apre
 * l'anagrafica in un'altra scheda lasciando il modulo com'era.
 *
 * La ricetta si crea con `page.request` e si elimina nel `finally`; il passo del nome si
 * chiude con «Annulla», così nessun ingrediente nasce. Niente resta dietro.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

async function entra(page: Page) {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();
}

async function ingrediente(page: Page, nome: string): Promise<{ id: string; name: string }> {
  const risposta = await page.request.get(`/api/v1/ingredients/search?q=${encodeURIComponent(nome)}`);
  expect(risposta.ok()).toBe(true);
  const trovati = (await risposta.json()) as { id: string; name: string }[];
  const voce = trovati.find((trovato) => trovato.name === nome);
  expect(voce, `«${nome}» non è nel seme`).toBeDefined();
  return voce!;
}

// stringhe e non funzioni: questo file lo compila tsconfig.node.json, senza la libreria DOM
async function nonScorreDiLato(page: Page, schermata: string) {
  await page.waitForLoadState("networkidle");
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
  expect(scrollWidth, `${schermata} scorre di lato`).toBeLessThanOrEqual(clientWidth);
}

test("la nota di una riga si corregge, si toglie e si aggiunge dal modulo di modifica", async ({ page }) => {
  await entra(page);
  const cetriolo = await ingrediente(page, "cetriolo");
  const anguria = await ingrediente(page, "anguria");
  const titolo = `Insalata con le note e2e ${Date.now()}`;
  const creata = await page.request.post("/api/v1/recipes", {
    data: {
      title: titolo, instructions: "Taglia e condisci.", servings: 2, source: "manual",
      ingredients: [
        { ingredient_id: cetriolo.id, role: "primary", quantity_text: "1", note: "a rondelle" },
        { ingredient_id: anguria.id, role: "primary", quantity_text: "1 fetta" },
      ],
    },
  });
  expect(creata.ok()).toBe(true);
  const { id: ricettaId } = (await creata.json()) as { id: string };

  try {
    await page.goto(`/ricette/${ricettaId}/modifica`);
    const notaCetriolo = page.getByLabel("Nota per cetriolo");
    await expect(notaCetriolo).toHaveValue("a rondelle");

    const aggiungiNota = page.getByRole("button", { name: "Aggiungi una nota: anguria" });
    await expect(aggiungiNota).toBeVisible();
    expect((await aggiungiNota.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await aggiungiNota.click();
    const notaAnguria = page.getByLabel("Nota per anguria");
    await expect(notaAnguria).toBeFocused();
    await notaAnguria.fill("senza semi");
    await notaCetriolo.fill("");
    await nonScorreDiLato(page, "il modulo con le note aperte");

    await page.getByRole("button", { name: "Salva le modifiche" }).click();
    await expect(page).toHaveURL(new RegExp(`/ricette/${ricettaId}$`));

    const salvata = (await (await page.request.get(`/api/v1/recipes/${ricettaId}`)).json()) as {
      ingredients: { ingredient_name: string; note: string | null }[];
    };
    const note = Object.fromEntries(salvata.ingredients.map((riga) => [riga.ingredient_name, riga.note]));
    expect(note).toEqual({ cetriolo: null, anguria: "senza semi" });
  } finally {
    await page.request.patch(`/api/v1/recipes/${ricettaId}`, { data: { archived: true } });
  }
});

test("nel passo del nome un non alimentare lo dice subito, e l'anagrafica si apre a parte", async ({ page }) => {
  await entra(page);
  const detersivo = await ingrediente(page, "detersivo per i piatti");

  await page.goto("/ricette/nuova-ai");
  await page.getByLabel("Aggiungi un ingrediente").fill("detersivo per i piatti");
  await page.getByRole("button", { name: "Aggiungi «detersivo per i piatti»" }).click();

  const avviso = page.getByText(
    "In anagrafica questo nome è «Detersivo per i piatti», un non alimentare: una ricetta non può averlo. Scrivi un altro nome; se invece è l'anagrafica a sbagliare, correggila."
  );
  await expect(avviso).toBeVisible();
  const aggiungi = page.getByRole("button", { name: "Aggiungi alla ricetta", exact: true });
  await expect(aggiungi).toHaveAttribute("aria-disabled", "true");
  await expect(page.getByText("Cambia il nome: questo è un non alimentare.")).toBeVisible();

  const collegamento = page.getByRole("link", { name: "Correggi «Detersivo per i piatti» in Anagrafica" });
  await expect(collegamento).toHaveAttribute("href", `/anagrafica/ingrediente/${detersivo.id}`);
  expect((await collegamento.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await nonScorreDiLato(page, "il passo del nome con l'avviso");

  // l'anagrafica si apre in un'altra scheda, e il modulo resta com'era
  const [scheda] = await Promise.all([page.context().waitForEvent("page"), collegamento.click()]);
  await expect(scheda.getByRole("heading", { name: "Detersivo per i piatti" })).toBeVisible();
  await scheda.close();
  await expect(page.getByLabel("Come si chiama in generale?")).toHaveValue("detersivo per i piatti");

  // un altro nome, e l'avviso se ne va
  await page.getByLabel("Come si chiama in generale?").fill("zz prova nome e2e");
  await expect(avviso).toHaveCount(0);
  await expect(aggiungi).not.toHaveAttribute("aria-disabled", "true");
  await page.getByRole("button", { name: "Annulla", exact: true }).click();
  await expect(page.getByLabel("Come si chiama in generale?")).toHaveCount(0);
});
```

- [ ] **Step 2: La prova del contrasto**

In fondo a `frontend/e2e/style.spec.ts` aggiungi:

```ts
test("il modulo della ricetta: la nota e l'avviso del non alimentare si leggono nei due temi (piano 20)", async ({
  page,
}) => {
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });

  async function leggibile(dove: string) {
    for (const tema of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: tema });
      await fermo(page);
      expect(await testiIlleggibili(page), `${dove}, tema ${tema}`).toEqual([]);
    }
    await page.emulateMedia({ colorScheme: "light" });
  }

  // niente si salva: la riga vive nel modulo, e il passo del non alimentare si chiude
  await page.goto("/ricette/nuova-ai");
  await page.getByLabel("Aggiungi un ingrediente").fill("zz prova nota");
  await page.getByRole("button", { name: "Aggiungi «zz prova nota»" }).click();
  await page.getByRole("button", { name: "Aggiungi alla ricetta", exact: true }).click();
  const aggiungiNota = page.getByRole("button", { name: "Aggiungi una nota: zz prova nota" });
  await expect(aggiungiNota).toBeVisible();
  await leggibile("modulo con «Aggiungi una nota»");

  await aggiungiNota.click();
  await page.getByLabel("Nota per zz prova nota").fill("da grattugiare");
  await leggibile("modulo con la nota aperta");

  await page.getByLabel("Aggiungi un ingrediente").fill("detersivo per i piatti");
  await page.getByRole("button", { name: "Aggiungi «detersivo per i piatti»" }).click();
  await expect(page.getByText(/un non alimentare: una ricetta non può averlo/)).toBeVisible();
  await expect(page.getByText("Cambia il nome: questo è un non alimentare.")).toBeVisible();
  await leggibile("passo del nome col non alimentare");
  await page.getByRole("button", { name: "Annulla", exact: true }).click();
});
```

(`fermo` e `testiIlleggibili` sono già nel file.)

- [ ] **Step 3: Si elencano, e l'e2e intera**

Run (da `<worktree>/frontend`): `npx playwright test --list 2>/dev/null | tail -n 1 && npm run typecheck`
Expected: `N_e2e` + 3; typecheck pulito (i file e2e li compila `tsconfig.node.json`).

Poi l'e2e intera con i comandi delle Global Constraints, su uno stack alzato da zero. Expected: tutto verde, con le prove di oggi di `modifica-ricette.spec.ts`, `ai-draft.spec.ts` e di `style.spec.ts` («in ogni luogo ogni testo sta sopra 4,5:1», che ora misura anche «Aggiungi una nota» nel modulo di modifica della prima ricetta). Se una prova cade, leggi lo screenshot in `frontend/test-results/` prima di cambiare qualcosa. Poi `down -v` e `rm .env`, sempre.

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/modulo-nota-nome.spec.ts frontend/e2e/style.spec.ts
git commit -m "e2e: la nota nel modulo e l'avviso del non alimentare nel passo del nome, a 375 px e nei due temi"
```

---

### Task 8: I documenti

**Files:**
- Modify: `next-steps.md`, `CLAUDE.md`

- [ ] **Step 1: L'idea chiusa esce**

In `next-steps.md`, sotto «### Idee», togli la riga che comincia con `- [idea] P3 · Nel modulo, un nome nuovo che coincide con un non alimentare dell'anagrafica si scopre solo salvando` (cercala con `grep -n "un nome nuovo che coincide" next-steps.md`; se non c'è più, scrivilo nel report). Se sul ramo c'è anche una riga che comincia con `- [idea] P3 · La nota di una riga della ricetta non si vede né si corregge nel modulo` (su `master` non c'è), togli anche quella.

- [ ] **Step 2: Le voci**

1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte)_` (se un piano prima di questo l'ha già scritta così stanotte, lasciala).
2. Togli la riga della voce da «In corso» (`grep -n "modulo-nota-nome" next-steps.md`); se «In corso» resta vuota, rimetti `_(niente)_`.
3. In cima a «Fatti (recenti)» aggiungi:
   ```markdown
   - [fatto] <data di oggi> · Modulo della ricetta: la nota di ogni riga si legge, si corregge e si toglie («Nota», «Aggiungi una nota»; vuota si salva `null`); un nome nuovo che salvando porterebbe a un non alimentare lo dice il passo del nome mentre lo si scrive, col collegamento all'Anagrafica in un'altra scheda (`GET /ingredients/match`, la stessa regola di `_resolve_lines`) (Mattia, 2026-10-13) [T3 Consegna 6b, R12, Parte X] → branch night/modulo-nota-nome (da revisionare)
   ```
4. Se nella notte sono emerse altre cose da fare fuori da questo piano, aggiungile come `idea` o `tbd`.

- [ ] **Step 3: `CLAUDE.md`**

In `CLAUDE.md`, nel riquadro che comincia con `> **Since 2026-09-17 the registry also holds non-food entries**`, le righe
```
> queue refuse a non-food term
> before it ever reaches a recipe, and the three ingredient pickers used by the
> recipe screens ask the registry for `kind=food` only. See
```
diventano (leggi il file com'è sul ramo: se gli a capo sono altrove, cambia solo la fine della frase prima di «See»; la riga dopo, `` > `docs/superpowers/specs/2026-09-17-non-alimentari-design.md` for where each of ``, resta com'è)
```
> queue refuse a non-food term
> before it ever reaches a recipe, the three ingredient pickers used by the
> recipe screens ask the registry for `kind=food` only, and the form's new-name
> step asks `GET /ingredients/match` as the name is typed — the same
> `ingredient_for_new_name` the save calls — and refuses a non-food there, with
> a way out. See
```

- [ ] **Step 4: Commit**

```bash
git add next-steps.md CLAUDE.md
git commit -m "docs: modulo della ricetta, nota e nome non alimentare fatti (da revisionare); l'idea del non alimentare nel modulo chiusa"
```

---

### Task 9: La verifica finale, e il report

- [ ] **Step 1: Il frontend**

Da `<worktree>/frontend`:

```bash
npx vitest run
npm run typecheck
npx tsc -b --force
npm run lint
npm run build
```

Expected: vitest tutto verde — **`N_vitest` + 13** (Task 4: 4; Task 5: 5; Task 6: 4), in **`N_file`** file (nessun file di test nuovo nel frontend); se il numero differisce, scrivi nel report da dove viene. Typecheck, lint e build puliti.

- [ ] **Step 2: Il backend**

Il comando di pytest, intero. Expected: verde, **`N_pytest` + 21** (Task 1: 4; Task 2: 11, con i tre casi del 422; Task 3: 6, con i due casi della nota vuota). Se si è usato `spena_test_nota`, ora `DROP DATABASE IF EXISTS spena_test_nota WITH (FORCE)`.

- [ ] **Step 3: I grep, e l'e2e intera**

I tre comandi di «Comandi di verifica» (con l'esito atteso lì), poi l'e2e intera su uno stack ricreato da zero: tutti verdi, `N_e2e` + 3. Poi `down -v` e `rm .env`, sempre.

- [ ] **Step 4: Il report**

Nel report della notte (`docs/night-reports/<data>.md` sul ramo: se c'è già, aggiungi una sezione in fondo; altrimenti crealo con un titolo `# Notte del <data di oggi>`), per questo piano: il ramo e da dove parte (`master`); quale database dei test; i conti veri contro quelli della Preparazione; le parole nuove che Mattia può voler rivedere (spec §5); cosa fare al merge (vedi «Dipendenze»: l'import delle icone con il piano 13, `formModel.ts` e le prove in fondo con il piano 15, `_resolve_lines` con il piano 14 e la sua fabbrica che deve lasciare acceso `refetchOnWindowFocus`, l'idea della nota nel modulo che il piano 12 non deve aggiungere). Niente da fare dopo il deploy. Niente push, niente merge, niente deploy.

```bash
git add docs/night-reports/
git commit -m "docs: report della notte, modulo della ricetta (nota e nome non alimentare)"
```
