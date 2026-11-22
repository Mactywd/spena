# Pasti: la ricetta scritta a mano vince su quella di Claude non ancora toccata — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** mentre la ricetta di un pasto è «in preparazione», Mattia può scriverla a mano. Se quella di Claude arriva prima che lui salvi, e nessuno l'ha ancora toccata, il suo salvataggio la sostituisce, con un «Annulla» che rimette quella di Claude. Così la frase del pasto («Puoi anche scriverla tu: quella di Claude allora non arriva.») diventa vera in ogni caso.

**Architecture:** `POST /api/v1/recipes` con `meal_id`, su un pasto che ha già una ricetta, cerca la modifica con cui Claude l'ha creata (`untouched_ai_change`). Se la ricetta è ancora esattamente come Claude l'ha lasciata, la riscrive al suo posto con `write_meal_recipe`, la sola strada che salva la versione di prima in un `RecipeChange`. L'«Annulla» è quello che c'è già, `POST /meals/{meal_id}/chat/changes/{change_id}/undo`. Altrimenti risponde il 409 `has_recipe` di oggi, e il modulo offre quel che offre oggi. La coda delle ricette impara a ricordare quel che ha scritto, così non riscrive sopra la ricetta a mano.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, pytest su Postgres vero; React 19, TanStack Query 5, Vitest + Testing Library. Nessuna chiamata a Claude.

**Spec:** `docs/superpowers/specs/2026-11-12-pasti-claude-design.md` §5.2 («Quando si scrivono le ricette»), §5.3 («Annulla»), e §6–§7 per `write_meal_recipe`. La voce `tbd` P2 «Pasti: scrivere a mano la ricetta mentre è «in preparazione»» di `next-steps.md` [Parte IV]. Il piano che ha aperto i due pulsanti in preparazione è `docs/superpowers/plans/2026-11-21-pasti-terzo-giro.md` (Task 8, decisione 7). **Decisione di Mattia del 2026-11-22: strada (a)**, «Vince la tua, con Annulla».

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/ricetta-a-mano-vince`, ramo `night/ricetta-a-mano-vince`, creato da `master`. Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì, mai dalla radice del checkout principale, che non si tocca. **Nessun push, nessun merge, nessun deploy. Mai `git stash`. Niente letture o scritture sulla produzione, e mai il `.env` del checkout principale. Nessuna chiamata vera a Claude**: i test usano il client finto che c'è già.
- **Una scrittura sola per la ricetta di un pasto**: la sostituzione passa da `write_meal_recipe` (`backend/app/services/meal_recipes.py`). Così il lucchetto del pasto, il SAVEPOINT, l'imbuto `resolve_lines` / `write_recipe_ingredients` e il `RecipeChange` per «Annulla» sono quelli che ci sono già. Niente seconda strada che scriva le righe.
- **Le due decisioni fondanti restano intere**: le righe passano dall'imbuto, e un non alimentare si rifiuta come oggi.
- **Mai un vicolo cieco.** Se la sostituzione non si può fare (la ricetta di Claude è già stata toccata, o cambia a metà richiesta), resta il 409 `has_recipe`, e il modulo offre «Salva nel ricettario» e «Vedi la ricetta di Claude» come oggi. Un «Annulla» rifiutato dice perché, con la frase che manda il server.
- **Il frontend non decide** se la ricetta di Claude è ancora intatta: lo dice il server.
- Le parole a video **si copiano esatte** da questo piano (fra «»). Gli identificatori in inglese, i commenti in italiano.
- **Il type check è `npm run typecheck`**, mai `tsc --noEmit`. Controlli del frontend, da `<worktree>/frontend`: `npx vitest run`, `npm run typecheck`, `npm run lint`, `npm run build`. Nei test dei componenti si usa `createTestQueryClient`.
- **Backend su Postgres vero**: `spena-db-1` (porta 5433), con il database `spena_test_ricetta_a_mano`. Mai `docker compose up` dal worktree. Si usa il `.venv` del checkout principale. Il comando di pytest, da `<worktree>/backend`:
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_ricetta_a_mano \
    PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
- **e2e** sullo stack `spena-e2e`, con i comandi delle Global Constraints di `docs/superpowers/plans/2026-11-18-pasti-correzioni.md`: il `.env` da `.env.example` e cancellato alla fine; `-p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml` in ogni comando; il seme con le ricette e le due righe della fixture CIQUAL; `down -v` e `rm .env` sempre. Se lo stack c'è e non l'hai alzato tu, aspetta che sparisca.
- Nessuna dipendenza nuova, **nessuna migrazione**.
- **I test di oggi si cambiano solo dove il piano lo dice**: `test_scrivi_la_ricetta_dopo_la_coda_non_lascia_orfane` in `backend/tests/api/test_recipes_meal.py` (Task 2). Se cade altro, il comportamento è cambiato, e si corregge il codice.

## Review Focus

1. **La ricetta di Claude toccata dalla chat del piatto** (un secondo `RecipeChange`), **corretta a mano** (`PUT`), **salvata nel ricettario** o **annullata**: non si sostituisce mai, e la risposta è il 409 `has_recipe`. Task 1.
2. **La coda che scrive due volte nello stesso giro**, con la ricetta a mano arrivata in mezzo: la seconda scrittura della coda si rifiuta e non cancella il lavoro di Mattia. Task 3.
3. **La ricetta di Claude che cambia fra la lettura e la scrittura** (una chat che scrive in quell'istante): `expected` la ferma, e la rotta risponde 409 `has_recipe` senza scrivere niente. Task 2.
4. **«Annulla» dopo la sostituzione** rimette la ricetta di Claude intera, toglie gli ingredienti che il modulo aveva creato se nient'altro li usa, e una seconda volta dice «Questa modifica è già stata annullata.». Task 2.
5. **Il pasto che non può avere una ricetta** (avanzo, fuori casa, bozza): resta il rifiuto di oggi, prima di ogni sostituzione. Task 2.

### Preparazione (una volta, prima del Task 1)

- [ ] Il worktree, con `node_modules` collegato e nessun `.env`:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/ricetta-a-mano-vince -b night/ricetta-a-mano-vince master
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/ricetta-a-mano-vince/frontend/node_modules
  ```
- [ ] Il database dei test:
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_ricetta_a_mano WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_ricetta_a_mano'
  ```
- [ ] La voce di `next-steps.md` che cita questo piano passa a `in corso` (` → in corso su night/ricetta-a-mano-vince`), e si committa: `next-steps: la ricetta a mano che vince, in corso`.
- [ ] La linea di partenza: pytest e vitest dal worktree, tutto verde. **Annota** i numeri. Se non è verde, fermati e scrivilo nel report.

---

## Decisioni prese

1. **Di Mattia (2026-11-22): vince la ricetta scritta a mano, con «Annulla»**, solo se quella di Claude non è stata toccata. Se è stata toccata resta l'offerta di oggi.
2. **«Non toccata» vuol dire** (Claude, su delega): la ricetta del pasto è viva (`archived_at` vuoto) e fuori dal ricettario (`in_book` falso); il pasto ha **un solo** `RecipeChange` su quella ricetta, con `created_recipe` vero e `undone_at` vuoto; quella modifica è ancora annullabile (`change_is_undoable`: ricetta e piatto sono esattamente come li ha lasciati). Una correzione con il modulo, una risposta della chat, «Salva nel ricettario» o una scelta dal ricettario (che non ha un `RecipeChange`) la rendono «toccata». La coda e la chat che crea la ricetta valgono uguale: è «quella di Claude».
3. **Si riscrive la ricetta di Claude al suo posto, non se ne crea una nuova** (Claude, su delega). Passando da `write_meal_recipe` con `created_recipe` falso, l'«Annulla» che c'è già rimette la versione di Claude nella stessa ricetta. Non serve una seconda strada per scambiare due ricette. La provenienza (`source`) resta quella di Claude: non si vede a video, e il pasto tiene una ricetta sola.
4. **Il reparto e il costo del modulo** (`category`, `cost`) si scrivono sulla ricetta dopo `write_meal_recipe`, nello stesso commit. L'istantanea di «Annulla» non li porta, quindi un «Annulla» li lascia come li ha scritti Mattia. Va bene: contano solo nel ricettario, e la ricetta di Claude non ne aveva.
5. **La corsa a metà rotta resta un 409.** Se il pasto non aveva una ricetta alla prima lettura, ma la coda la lega mentre la rotta scrive, `link_recipe` rifiuta come oggi (`tests/db/test_meal_lock.py`), e il modulo offre le due strade di oggi. Ritentare la sostituzione in quel caso sarebbe una seconda transazione nella stessa rotta, per una finestra di millisecondi.
6. **La coda ricorda quel che ha scritto** (Claude, su delega): dopo una scrittura riuscita, un giro `create_only` tiene `ctx.seen` sull'istantanea che ha lasciato, come già fa la chat. Così una seconda `write_recipe` nello stesso giro, dopo la sostituzione a mano, trova la ricetta cambiata e si rifiuta con `STALE_WRITE_MESSAGE`.
7. **La risposta dice che cosa annullare**: `RecipeOut` ha un campo nuovo, `undo_change_id: uuid.UUID | None = None`, che vale solo per una sostituzione. Il frontend lo legge per mostrare «Annulla».

## Margine di autonomia

- Liberi: i nomi interni e dei test, la frase del `summary` del `RecipeChange` (non si vede a video: suggerita «Scritta a mano al posto di quella di Claude»).
- Fissi: `untouched_ai_change`, `undo_change_id`, le parole a video di questo piano, la rotta dell'«Annulla».
- **Fermati** (voce `bloccato` nel report) se per sostituire servisse una migrazione, o una seconda strada di scrittura delle righe accanto a `write_meal_recipe`.

---

### Task 1: quando la ricetta di Claude è ancora intatta

**Files:**
- Modify: `backend/app/services/meal_recipes.py` (`untouched_ai_change`; `MealRecipeDraft.servings: int | None`)
- Test: `backend/tests/services/test_meal_recipes.py`

**Interfaces:**
- Consumes: `change_is_undoable(session, change) -> bool`, `RecipeChange`, `Recipe`.
- Produces: `async def untouched_ai_change(session: AsyncSession, meal: Meal) -> RecipeChange | None`, cioè la modifica con cui Claude ha creato la ricetta del pasto, se la ricetta è ancora intatta (decisione 2), altrimenti `None`. Sola lettura. `MealRecipeDraft.servings` accetta `None`, perché il modulo lo permette (`RecipeFields.servings`). Gli strumenti di Claude continuano a mandare un intero.

- [ ] **Step 1: I test che falliscono**, con le fixture del file (un pasto ufficiale a casa e un ingrediente). La ricetta di Claude si scrive con `write_meal_recipe(..., allowed_recipe_ids=frozenset({None}))`, come fa la coda:
  - `test_la_ricetta_appena_scritta_da_claude_e_intatta`: restituisce la modifica con `created_recipe` vero.
  - `test_senza_ricetta_niente`: un pasto senza ricetta dà `None`.
  - `test_toccata_dalla_chat_non_e_intatta`: dopo una seconda `write_meal_recipe` sullo stesso pasto, `None`.
  - `test_annullata_non_e_intatta`: dopo `undo_recipe_change` sulla modifica, `None`.
  - `test_corretta_a_mano_non_e_intatta`: cambiato il titolo della ricetta nel database (come fa il `PUT`), `None`.
  - `test_nel_ricettario_non_e_intatta`: con `in_book` vero, `None`.
  - `test_scelta_dal_ricettario_non_e_di_claude`: una ricetta legata con `copy_recipe_to_meal` (senza `RecipeChange`) dà `None`.
- [ ] **Step 2: Falliscono**: il comando di pytest con `tests/services/test_meal_recipes.py`. Expected: `ImportError` su `untouched_ai_change`.
- [ ] **Step 3: Il codice.** `untouched_ai_change` legge la ricetta del pasto e le modifiche del pasto su quella ricetta, e applica le condizioni della decisione 2 nell'ordine in cui costano meno. Cambia anche l'annotazione di `MealRecipeDraft.servings`.
- [ ] **Step 4: Passano**, con tutto il file e con `tests/services/test_claude_tools.py`.
- [ ] **Step 5: Commit**: `pasti: sapere se la ricetta di Claude è ancora come l'ha lasciata`.

### Task 2: il salvataggio a mano la sostituisce, e «Annulla» la rimette

**Files:**
- Modify: `backend/app/api/recipes.py` (`create`)
- Modify: `backend/app/schemas/recipe.py` (`RecipeOut.undo_change_id`)
- Test: `backend/tests/api/test_recipes_meal.py`

**Interfaces:**
- Consumes: `untouched_ai_change` (Task 1); `write_meal_recipe(session, meal, draft, expected=...)`, `snapshot_from_json`, `RecipeWriteRefused`, `MealRecipeDraft`, `DraftLine`, `UNSET`; la rotta `POST /api/v1/meals/{meal_id}/chat/changes/{change_id}/undo`.
- Produces: `POST /api/v1/recipes` con `meal_id`. Su un pasto con la ricetta di Claude intatta risponde **201** con la ricetta riscritta (stesso `id` di quella di Claude, `in_book` falso) e `undo_change_id` valorizzato. Su un pasto con una ricetta toccata risponde 409 `has_recipe`, come oggi. `RecipeOut.undo_change_id` vale `None` in ogni altra risposta.

- [ ] **Step 1: I test che falliscono.** Riscrivi `test_scrivi_la_ricetta_dopo_la_coda_non_lascia_orfane` come `test_scrivi_la_ricetta_dopo_la_coda_prende_il_suo_posto`: 201; il pasto ha la ricetta con il titolo «Pasta a mano»; l'`id` è quello della ricetta della coda; il numero di ricette non cambia; `undo_change_id` non è vuoto. Poi aggiungi:
  - `test_annulla_rimette_la_ricetta_di_claude`: `POST {M}/{meal.id}/chat/changes/{undo_change_id}/undo` dà 200, il pasto torna a «Pasta della coda»; un secondo «Annulla» dà 409 con `code` `change_undone`.
  - `test_annulla_toglie_l_ingrediente_creato_dal_modulo`: il corpo ha una riga con un nome nuovo e il suo reparto. Dopo l'«Annulla» quell'ingrediente non c'è più, perché nient'altro lo usa.
  - `test_una_ricetta_toccata_dalla_chat_non_si_sostituisce`: dopo una seconda `write_meal_recipe`, 409 `has_recipe`, e il titolo resta quello della chat.
  - `test_il_reparto_e_il_costo_del_modulo_restano`: con `category` e `cost` nel corpo, la ricetta li ha.
  - `test_senza_sostituzione_undo_change_id_e_vuoto`: un pasto senza ricetta dà 201 con `undo_change_id` `None` (la ricetta è nuova, come oggi).
  - `test_un_avanzo_resta_rifiutato`: un pasto avanzo dà il rifiuto di oggi, `no_recipe_here`.
- [ ] **Step 2: Falliscono**: il comando di pytest con `tests/api/test_recipes_meal.py`.
- [ ] **Step 3: Il codice.** In `create`, quando il pasto ha già una ricetta, la rotta controlla `refuse_if_no_recipe_here` come fa oggi `check_can_take_recipe`. Poi:
  1. legge `untouched_ai_change`: se è `None`, risponde il 409 `has_recipe` di oggi;
  2. controlla il reparto (`_check_category`);
  3. costruisce un `MealRecipeDraft` dal corpo, con una `DraftLine` per riga, gli stessi campi di `RecipeIngredientIn`, `dish=None` e `sides=UNSET`;
  4. chiama `write_meal_recipe(..., expected=snapshot_from_json(change.after))`. Un `RecipeWriteRefused` col messaggio di `expected` (la ricetta cambiata a metà) diventa il 409 `has_recipe`, dopo il rollback; gli altri rifiuti diventano un 409 con il loro messaggio come `detail`;
  5. scrive `category` e `cost` sulla ricetta, fa il commit e risponde con `undo_change_id` uguale all'`id` del `RecipeChange` nuovo.

  Il ramo senza ricetta resta quello di oggi.
- [ ] **Step 4: Passano**, con `tests/api/test_recipes_meal.py`, `tests/db/test_meal_lock.py`, `tests/api/test_recipes.py`. Poi la suite intera.
- [ ] **Step 5: Commit**: `pasti: la ricetta a mano prende il posto di quella di Claude non ancora toccata`.

### Task 3: la coda non riscrive sopra la ricetta a mano

**Files:**
- Modify: `backend/app/services/claude/tools.py` (`write_recipe`, dove aggiorna `ctx.seen`)
- Test: `backend/tests/services/test_claude_tools.py`

**Interfaces:**
- Consumes: `TurnContext.create_only`, `TurnContext.seen`, `snapshot_from_json`, `STALE_WRITE_MESSAGE`.
- Produces: dopo una `write_recipe` riuscita, `ctx.seen` è l'istantanea lasciata anche quando `create_only` è vero.

- [ ] **Step 1: Il test che fallisce**, `test_la_coda_non_riscrive_la_ricetta_a_mano`. È un giro con `create_only=True` e `seen=None`, come quello di `recipe_jobs._ask_claude`, e chiama lo strumento vero due volte. Fra le due chiamate, una `write_meal_recipe` diretta cambia il titolo (è la sostituzione a mano). La seconda chiamata risponde l'errore con `STALE_WRITE_MESSAGE`, e il titolo resta quello scritto a mano.
- [ ] **Step 2: Fallisce**: il comando di pytest con `tests/services/test_claude_tools.py`. Expected: oggi la seconda chiamata riscrive.
- [ ] **Step 3: Il codice**: la condizione diventa `if ctx.seen is not None or ctx.create_only:`.
- [ ] **Step 4: Passano**, con `tests/services/test_claude_tools.py` e `tests/services/test_recipe_jobs.py`.
- [ ] **Step 5: Commit**: `pasti: la coda ricorda la ricetta che ha scritto`.

### Task 4: il modulo dice che ha preso il posto, con «Annulla»

**Files:**
- Modify: `frontend/src/features/meals/MealRecipeNewScreen.tsx` (`onSaved`)
- Modify: `frontend/src/domain/types.ts` (`RecipeDetail.undo_change_id?: string | null`)
- Test: `frontend/src/features/meals/MealRecipeNewScreen.test.tsx`

**Interfaces:**
- Consumes: `undo_change_id` nella risposta di `createRecipe` (Task 2); `undoChange(mealId, changeId)` di `frontend/src/features/meal-chat/api.ts`; `useNotice` con `action`.
- Produces: niente per altri task.

- [ ] **Step 1: I test che falliscono.**
  - «salvata al posto di quella di Claude, con Annulla»: la risposta ha `undo_change_id`. L'avviso dice «Salvata al posto di quella di Claude.» con il pulsante «Annulla», e si torna a `/pasti/<id>`.
  - «Annulla rimette quella di Claude»: toccato «Annulla», parte `POST /meals/<id>/chat/changes/<change>/undo`. L'avviso dice «Rimessa la ricetta di Claude.», e le query del pasto (`MEALS_KEY`) e della ricetta si invalidano.
  - «un Annulla rifiutato dice perché»: con un 409 `{ code: "change_stale", detail: "…" }`, l'avviso mostra il `detail` del server.
  - «senza sostituzione resta Salvata.»: senza `undo_change_id` l'avviso è «Salvata.», come oggi, e non ha pulsanti.
  - Il test di oggi su «Nel frattempo è arrivata la ricetta di Claude…» (409 `has_recipe`) resta com'è.
- [ ] **Step 2: Falliscono**: `npx vitest run src/features/meals/MealRecipeNewScreen.test.tsx`.
- [ ] **Step 3: Il codice.** `onSaved` sceglie l'avviso guardando `saved.undo_change_id`. L'«Annulla» chiama `undoChange`: se riesce, invalida le query e mostra «Rimessa la ricetta di Claude.»; se fallisce, mostra il `detail` del server o, senza `detail`, «Non sono riuscito ad annullare: la ricetta di Claude non è tornata.».
- [ ] **Step 4: Passano**, poi i controlli interi del frontend: `npx vitest run`, `npm run typecheck`, `npm run lint`, `npm run build`.
- [ ] **Step 5: Commit**: `pasti: «Salvata al posto di quella di Claude», con Annulla`.

### Task 5: e2e, la verifica, il backlog

- [ ] **Step 1: e2e intera**, con i comandi delle Global Constraints. Nessuna prova nuova: la corsa con la coda vuole Claude, e lo stack e2e non lo ha.
- [ ] **Step 2: Il backlog.** La voce passa a `fatto <data>` in «Fatti (recenti)», con ` → branch night/ricetta-a-mano-vince (da revisionare)`. In «Da fare a mano (solo Mattia)», nella voce del giro completo dei Pasti con Claude, aggiungi in coda: «e, mentre una ricetta è in preparazione, scriverla a mano e salvarla dopo che è arrivata quella di Claude: si legge «Salvata al posto di quella di Claude.», e «Annulla» la rimette». Commit: `next-steps: la ricetta a mano che vince, fatto`.

## Fuori scope

- Il lucchetto del pasto in `PUT /recipes/{id}` e nel `PATCH` (idea P2 a parte): qui il `PUT` conta solo perché rende «toccata» la ricetta.
- Togliere il pasto dalla coda quando si apre il modulo (strada (b), scartata da Mattia).
- Cambiare la frase del pasto in preparazione: resta quella del piano del 2026-11-21.
- Mostrare la sostituzione nella chat del piatto: il `RecipeChange` nuovo non ha un messaggio, e la chat non lo elenca.

## Comandi di verifica

- Backend: il comando di pytest delle Global Constraints, tutto verde, con i test nuovi.
- Frontend, da `<worktree>/frontend`: `npx vitest run`, `npm run typecheck`, `npm run lint`, `npm run build`.
- e2e: la suite intera, verde.
- `grep -rn "emerald\|neutral-" frontend/src` dà solo il commento di `index.css`.
- `git -C <worktree> diff master --stat` tocca solo i file dei task, più `next-steps.md` e il report.
