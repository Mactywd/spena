# La ricetta di un pasto: il lucchetto nella modifica e nel `PATCH`, il modulo che sa se è cambiata, «Annulla» dopo il pasto eliminato — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** chiudere le tre strade con cui la ricetta di un pasto si perde o resta in uno stato impossibile:
- la modifica a mano (`PUT`) e il `PATCH` che non prendono il lucchetto del pasto;
- un modulo aperto prima di una risposta di Claude, che la sovrascrive in silenzio;
- «Annulla» dopo che il pasto è stato eliminato, che offre un «Riprova» impossibile.

**Architecture:**
- **Il lucchetto.** `PUT /recipes/{id}` e `PATCH /recipes/{id}` prendono `lock_meal` sul pasto della ricetta, se ce l'ha, prima di ogni controllo. È lo stesso ordine di `delete_meal`: prima il pasto, poi la ricetta.
- **La versione.** La ricetta porta una versione, l'impronta del suo contenuto (`recipe_version`). Il modulo la rimanda con il `PUT`: se nel frattempo la ricetta è cambiata, il server risponde 409 `recipe_changed`, e il modulo lascia scegliere fra «Salva comunque la mia» e «Ricarica la ricetta».
- **«Annulla».** Nel frontend, un «Annulla» che trova la ricetta eliminata insieme al suo pasto la ripristina. Il server, per la decisione 18, la rimette nel ricettario.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, pytest su Postgres vero (anche con due sessioni concorrenti); React 19, TanStack Query 5, Vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-11-12-pasti-claude-design.md` §4 (la ricetta del pasto, l'invariante del ricettario) e §5.3. Il piano che ha messo il lucchetto è `docs/superpowers/plans/2026-11-21-pasti-terzo-giro.md` (Task 5, idea 52). Le voci sono l'idea P2 «Pasti: la ricetta di un pasto senza il lucchetto del pasto…» di `next-steps.md` [Parte IV], unita il 2026-11-22 con «Annulla» dopo il pasto eliminato. **Decisioni di Mattia del 2026-11-22**: il modulo vecchio «avvisa e lascia scegliere»; «Annulla» dopo il pasto eliminato «la rimette nel ricettario».

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/ricetta-pasto-lucchetto`, ramo `night/ricetta-pasto-lucchetto`, creato da `master`. Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì. **Nessun push, nessun merge, nessun deploy. Mai `git stash`. Niente letture o scritture sulla produzione, e mai il `.env` del checkout principale. Nessuna chiamata vera a Claude.**
- **Se nella stessa notte gira anche `2026-11-22-ricetta-a-mano-vince.md`**, i due piani toccano entrambi `backend/app/api/recipes.py` (`create` lui, `replace` e `update` questo) e `backend/app/schemas/recipe.py` (`RecipeOut`). Restano rami separati, entrambi da `master`. Nel report scrivi i punti dove il merge del secondo dovrà cucire.
- **L'invariante resta vera in ogni ordine delle scritture**: una ricetta viva fuori dal ricettario ha sempre un pasto (`_orfane` di `tests/db/test_meal_lock.py` dà 0).
- **Ordine dei lucchetti**: prima il pasto (`lock_meal`), poi le righe della ricetta, come `delete_meal` (il commento F-R6 sul ciclo). Nessuna chiamata di rete col pasto bloccato: nel `PUT`, `embedding_for` si calcola **prima** del lucchetto, e i controlli si rifanno dopo.
- **Mai un vicolo cieco**: il 409 `recipe_changed` ha le sue due strade a video; un «Annulla» che non può più rimettere la ricetta nel ricettario la ripristina.
- **Il frontend non decide** se la ricetta è cambiata: lo dice il server, confrontando le versioni.
- Le parole a video **si copiano esatte** da questo piano (fra «»). Gli identificatori in inglese, i commenti in italiano.
- **Il type check è `npm run typecheck`**, mai `tsc --noEmit`. Controlli del frontend, da `<worktree>/frontend`: `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- **Il carico sulla macchina**: al massimo 6 thread e 8 GB (Mattia, 2026-11-22). Le suite intere girano dentro `systemd-run --user --scope -p MemoryMax=8G -p CPUQuota=600% …`, mai due insieme. Vitest gira con `--maxWorkers=4`, pytest senza parallelismo.
- **Backend su Postgres vero**: `spena-db-1` (porta 5433), con il database `spena_test_ricetta_lucchetto`. Mai `docker compose up` dal worktree. Si usa il `.venv` del checkout principale. Il comando di pytest, da `<worktree>/backend`:
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_ricetta_lucchetto \
    PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
- **e2e** sullo stack `spena-e2e`, con i comandi delle Global Constraints di `docs/superpowers/plans/2026-11-18-pasti-correzioni.md` (il `.env` da `.env.example` e cancellato alla fine, `-p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml` in ogni comando, il seme con le ricette e le due righe della fixture CIQUAL, `down -v` e `rm .env` sempre).
- Nessuna dipendenza nuova, **nessuna migrazione** (la versione si calcola, non si salva).
- **I test di oggi si cambiano solo dove il piano lo dice**: nessuno. Un `PUT` senza `expected_version` funziona come oggi.

## Review Focus

1. **`PATCH archived=true` (ricetta di un pasto nel ricettario) mentre si elimina il pasto**: in tutti e due gli ordini l'invariante tiene, e la ricetta finisce o fuori dal ricettario col pasto, o archiviata senza pasto. Task 2.
2. **«Salva nel ricettario» (`in_book=true`) mentre si elimina il pasto**: in un ordine la ricetta resta nel ricettario senza pasto (va bene); nell'altro il `PATCH` risponde 409 `RECIPE_ARCHIVED`, e mai una ricetta eliminata nel ricettario con una risposta 200. Task 2.
3. **Il `PUT` mentre la chat scrive**: la chat committa prima e il `PUT` con la versione vecchia risponde 409 `recipe_changed`, oppure il `PUT` committa prima e la chat si ferma con `STALE_WRITE_MESSAGE`. Mai una delle due scritture persa in silenzio. Task 3.
4. **Un `PUT` senza `expected_version`** (un client vecchio o «Salva comunque la mia») scrive come oggi. Task 3.
5. **«Ricarica la ricetta»** rilegge dal server e rifà il modulo con la ricetta nuova, senza lasciare righe del modulo vecchio. Task 4.

### Preparazione (una volta, prima del Task 1)

- [ ] Il worktree, con `node_modules` collegato e nessun `.env`:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/ricetta-pasto-lucchetto -b night/ricetta-pasto-lucchetto master
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/ricetta-pasto-lucchetto/frontend/node_modules
  ```
- [ ] Il database dei test:
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_ricetta_lucchetto WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_ricetta_lucchetto'
  ```
- [ ] La voce di `next-steps.md` che cita questo piano passa a `in corso` (` → in corso su night/ricetta-pasto-lucchetto`), e si committa: `next-steps: il lucchetto della ricetta del pasto, in corso`.
- [ ] La linea di partenza: pytest e vitest dal worktree, tutto verde. **Annota** i numeri. Se non è verde, fermati e scrivilo nel report.

---

## Decisioni prese

1. **Di Mattia (2026-11-22): il modulo vecchio avvisa e lascia scegliere.** Per una ricetta di un pasto, salvando un modulo aperto prima di una risposta di Claude che l'ha cambiata, il modulo dice «Claude ha cambiato la ricetta mentre la correggevi.» e offre «Salva comunque la mia» e «Ricarica la ricetta». Per una ricetta senza pasto, cambiata da un altro dispositivo, la frase è «La ricetta è cambiata mentre la correggevi.». Le due strade sono le stesse.
2. **Di Mattia (2026-11-22): «Annulla» dopo il pasto eliminato la rimette nel ricettario.** Il `PATCH in_book=true` su una ricetta eliminata resta un 409 (`test_il_ricettario_di_una_ricetta_eliminata_non_si_cambia` non cambia). Sul 409, il frontend ripristina la ricetta con `archived=false`: il server, per la decisione 18, rimette nel ricettario una ricetta ripristinata senza pasto. L'avviso dice «Rimessa nel ricettario.».
3. **La versione è l'impronta del contenuto, non una colonna** (Claude, su delega). `recipe_version(snapshot: RecipeSnapshot) -> str` sono i primi 16 caratteri esadecimali dello SHA-256 del JSON canonico di titolo, descrizione, procedimento, porzioni e righe (ordinate per ingrediente, come `meal_snapshot`). Sono i campi che la chat cambia. Il costo e il reparto non entrano. Non servono migrazioni, e due letture della stessa ricetta danno la stessa versione.
4. **La versione vale per ogni ricetta**, non solo per quelle dei pasti: il modulo è uno, e un altro dispositivo è lo stesso caso.
5. **Il lucchetto si prende solo se la ricetta ha un pasto.** Senza pasto non c'è niente da bloccare, e il `PUT` e il `PATCH` restano come oggi. Preso il lucchetto, si rilegge il pasto della ricetta (`meal_of_recipe`): può essere stato eliminato mentre si aspettava. Poi si rilegge la ricetta (`session.refresh`), e solo dopo si fanno i controlli di oggi.

## Margine di autonomia

- Liberi: i nomi interni e dei test, il nome dell'helper che prende il lucchetto di una ricetta (suggerito `lock_meal_of_recipe(session, recipe) -> Meal | None`, in `backend/app/services/meals.py`).
- Fissi: `recipe_version`, `RecipeOut.version`, `RecipeReplace.expected_version`, il codice `recipe_changed`, le parole a video.
- **Fermati** (voce `bloccato` nel report) se un test di concorrenza va in stallo (un ciclo fra lucchetti): non allungare le attese per farlo passare.

---

### Task 1: la versione della ricetta

**Files:**
- Modify: `backend/app/domain/recipe_changes.py` (`recipe_version`)
- Modify: `backend/app/services/meal_recipes.py` (estrai `recipe_snapshot(recipe: Recipe) -> RecipeSnapshot` da `meal_snapshot`, che la usa)
- Modify: `backend/app/schemas/recipe.py` (`RecipeOut.version: str`) e il punto dove `_to_out` (`backend/app/api/recipes.py`) costruisce `RecipeOut`
- Modify: `frontend/src/domain/types.ts` (`RecipeDetail.version: string`)
- Test: `backend/tests/domain/test_recipe_changes.py` (o il file del dominio che c'è già per questo modulo), `backend/tests/api/test_recipes.py`

**Interfaces:**
- Produces: `recipe_version(snapshot: RecipeSnapshot) -> str` (16 caratteri esadecimali); `recipe_snapshot(recipe: Recipe) -> RecipeSnapshot`, da una ricetta con le righe caricate; `RecipeOut.version` in ogni risposta che restituisce una ricetta intera.

- [ ] **Step 1: I test che falliscono.**
  - `test_la_stessa_ricetta_ha_la_stessa_versione`: due snapshot uguali con le righe in ordine diverso danno la stessa versione.
  - `test_ogni_campo_cambia_la_versione`: titolo, descrizione, procedimento, porzioni, una dose, un ruolo, una nota.
  - `test_il_costo_non_cambia_la_versione`.
  - In `test_recipes.py`: `GET /recipes/{id}` ha `version`; dopo un `PUT` che cambia il procedimento, `version` cambia.
- [ ] **Step 2: Falliscono** (il comando di pytest con quei file).
- [ ] **Step 3: Il codice.** Il JSON canonico va con `json.dumps(..., sort_keys=True, separators=(",", ":"), default=str)`.
- [ ] **Step 4: Passano**, con la suite intera, e `npm run typecheck` (il tipo nuovo non rompe i finti dei test del frontend; se li rompe, aggiungi `version` ai finti che costruiscono un `RecipeDetail`).
- [ ] **Step 5: Commit**: `ricette: la versione, l'impronta di quel che la chat può cambiare`.

### Task 2: il `PATCH` col pasto bloccato

**Files:**
- Modify: `backend/app/services/meals.py` (`lock_meal_of_recipe`)
- Modify: `backend/app/api/recipes.py` (`update`)
- Test: `backend/tests/db/test_meal_lock.py`

**Interfaces:**
- Consumes: `lock_meal`, `meal_of_recipe` (`app.repositories.meals`), `delete_meal`.
- Produces: `async def lock_meal_of_recipe(session: AsyncSession, recipe: Recipe) -> Meal | None`. Blocca il pasto della ricetta se ce l'ha, poi rilegge il pasto (quello di ora, o `None`) e fa `session.refresh(recipe)`. Senza pasto non blocca niente.

- [ ] **Step 1: I test che falliscono**, con lo schema di `test_eliminare_il_pasto_aspetta_chi_scrive_senza_ciclo` (due sessioni, `_aspetta`, `_orfane`) e quello HTTP di `test_salvare_a_mano_mentre_la_coda_scrive_non_lascia_orfane`:
  - `test_elimina_dal_ricettario_mentre_si_elimina_il_pasto_non_lascia_orfane`: la sessione A tiene il pasto; il `PATCH archived=true` (la ricetta è nel ricettario) parte e aspetta (`_aspetta` va in `TimeoutError`); A elimina il pasto e committa; il `PATCH` finisce. Alla fine `_orfane == 0`.
  - Lo stesso con `in_book=false` («Togli dal ricettario»): `_orfane == 0`, e il `PATCH` risponde 409 `NOT_A_MEAL_RECIPE` perché il pasto non c'è più.
  - `test_salva_nel_ricettario_mentre_si_elimina_il_pasto`: A tiene il pasto ed elimina; il `PATCH in_book=true` aspetta e poi risponde 409 (ricetta eliminata). Nessuna ricetta eliminata con `in_book` vero.
- [ ] **Step 2: Falliscono**: il comando di pytest con `tests/db/test_meal_lock.py`. Expected: il `PATCH` non aspetta (il `_aspetta` non va in timeout), e `_orfane` dà 1.
- [ ] **Step 3: Il codice.** In `update`, subito dopo il 404, `meal = await lock_meal_of_recipe(session, recipe)`. Il resto della funzione usa `meal` al posto delle tre chiamate a `meal_of_recipe`, e `archived_after` si calcola dopo la rilettura.
- [ ] **Step 4: Passano**, con `tests/db/test_meal_lock.py`, `tests/api/test_recipes_meal.py`, `tests/api/test_recipes.py`.
- [ ] **Step 5: Commit**: `ricette: il PATCH prende il lucchetto del pasto`.

### Task 3: il `PUT` col pasto bloccato e la versione attesa

**Files:**
- Modify: `backend/app/api/recipes.py` (`replace`)
- Modify: `backend/app/schemas/recipe.py` (`RecipeReplace.expected_version: str | None = None`)
- Test: `backend/tests/db/test_meal_lock.py`, `backend/tests/api/test_recipes.py`, `backend/tests/api/test_recipes_meal.py`

**Interfaces:**
- Consumes: `lock_meal_of_recipe` (Task 2), `recipe_snapshot` e `recipe_version` (Task 1).
- Produces: `PUT /recipes/{id}` con `expected_version`. Se la versione di ora (sotto il lucchetto) è diversa, risponde **409** `{"code": "recipe_changed", "detail": …}` senza scrivere niente. Il `detail` è «Claude ha cambiato la ricetta mentre la correggevi.» se la ricetta ha un pasto, altrimenti «La ricetta è cambiata mentre la correggevi.». Senza `expected_version` scrive come oggi.

- [ ] **Step 1: I test che falliscono.**
  - `test_il_put_con_la_versione_vecchia_e_409`: GET, poi una `write_meal_recipe` (la chat), poi `PUT` con la versione del GET. Risponde 409 `recipe_changed` con la frase di Claude, e la ricetta resta quella della chat.
  - `test_il_put_senza_versione_scrive_come_oggi`.
  - `test_il_put_con_la_versione_giusta_scrive`.
  - Una ricetta senza pasto, cambiata da un `PUT`, e un secondo `PUT` con la versione vecchia: 409 con «La ricetta è cambiata mentre la correggevi.».
  - In `test_meal_lock.py`, `test_il_put_aspetta_la_chat_e_poi_dice_che_e_cambiata`: A tiene il pasto e scrive con `write_meal_recipe` senza committare; il `PUT` (con la versione di prima) aspetta; A committa; il `PUT` risponde 409 `recipe_changed`, e la ricetta è quella di A.
- [ ] **Step 2: Falliscono** (il comando di pytest con quei file).
- [ ] **Step 3: Il codice.** In `replace`:
  1. dopo il 404, i controlli che non toccano il pasto (il reparto) ed `embedding_for` restano **prima** del lucchetto;
  2. poi `lock_meal_of_recipe`;
  3. poi, sotto il lucchetto, il 409 `RECIPE_ARCHIVED` di oggi e il confronto della versione;
  4. poi la scrittura di oggi.

  La risposta 409 ha la forma `{"code", "detail"}`, come `_refuse` di `api/meal_chat.py`. Usa una `JSONResponse` con lo stesso schema e non importarla da lì.
- [ ] **Step 4: Passano**, poi la suite intera.
- [ ] **Step 5: Commit**: `ricette: il PUT prende il lucchetto del pasto e rifiuta una versione vecchia`.

### Task 4: il modulo dice che la ricetta è cambiata

**Files:**
- Modify: `frontend/src/features/recipes/api.ts` (`updateRecipe(id, body, expectedVersion?: string)`)
- Modify: `frontend/src/features/recipe-form/RecipeEditScreen.tsx` (`EditForm`)
- Test: `frontend/src/features/recipe-form/RecipeEditScreen.test.tsx`

**Interfaces:**
- Consumes: `RecipeDetail.version`, e il 409 `recipe_changed` del Task 3.
- Produces: niente per altri task.

- [ ] **Step 1: I test che falliscono.**
  - «salvando manda la versione letta»: il corpo del `PUT` ha `expected_version` uguale a `version` della ricetta caricata.
  - «se è cambiata, lo dice e lascia scegliere»: con un 409 `{ code: "recipe_changed", detail: "Claude ha cambiato la ricetta mentre la correggevi." }`, sotto il modulo compaiono quella frase (dal `detail`), «Salva comunque la mia» e «Ricarica la ricetta». Il modulo tiene quel che si è scritto.
  - «Salva comunque la mia»: manda il `PUT` senza `expected_version`, e poi «Salvata.» come oggi.
  - «Ricarica la ricetta»: rilegge `GET /recipes/<id>` e rifà il modulo dalla risposta nuova (si vede il titolo nuovo, non quello scritto); l'avviso sparisce.
- [ ] **Step 2: Falliscono**: `npx vitest run --maxWorkers=4 src/features/recipe-form/RecipeEditScreen.test.tsx`.
- [ ] **Step 3: Il codice.** `EditForm` passa `recipe.version` a `updateRecipe`. Su un `ApiError` 409 con `code === "recipe_changed"`, un `Alert tone="note"` col `detail` e i due pulsanti, come il blocco «Nel frattempo è arrivata la ricetta di Claude» di `MealRecipeNewScreen.tsx`. «Ricarica la ricetta» rifà `EditForm` con la risposta nuova: cambia la sua `key` con la `version` nuova, così lo stato del modulo riparte da `valuesFromRecipe`. L'errore del `save` di `RecipeForm` non deve mostrare anche la frase generica: guarda come `RecipeForm` mostra gli errori del `save` e fai in modo che un `recipe_changed` mostri solo l'avviso.
- [ ] **Step 4: Passano**, poi `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- [ ] **Step 5: Commit**: `ricette: il modulo dice se la ricetta è cambiata mentre la correggevi`.

### Task 5: «Annulla» dopo il pasto eliminato

**Files:**
- Modify: `frontend/src/features/recipes/useArchiveRecipe.ts` (`restoreToBook`)
- Test: `frontend/src/features/recipes/useArchiveRecipe.test.tsx`

**Interfaces:**
- Consumes: `setRecipeInBook(id, true)`, `setRecipeArchived(id, false)` (o come si chiama la funzione che `restore` usa già).

- [ ] **Step 1: I test che falliscono.**
  - «Annulla dopo il pasto eliminato la rimette nel ricettario»: il `PATCH {in_book: true}` risponde 409; parte allora `PATCH {archived: false}`, e l'avviso dice «Rimessa nel ricettario.». Le query di `["recipes"]`, della ricetta e di `["meals"]` si invalidano.
  - «se anche il ripristino fallisce»: l'avviso di oggi «Non sono riuscito a riportare «‹titolo›» nel ricettario.» con «Riprova», e «Riprova» rifà tutto il giro.
  - Il test di oggi con un 500 sul `PATCH in_book` resta com'è: un 500 non ripristina.
- [ ] **Step 2: Falliscono**: `npx vitest run --maxWorkers=4 src/features/recipes/useArchiveRecipe.test.tsx`.
- [ ] **Step 3: Il codice.** Solo un `ApiError` con `status === 409` sul `PATCH {in_book: true}` passa al ripristino. Un commento cita la decisione 18 e la decisione 2 di questo piano.
- [ ] **Step 4: Passano**, poi i controlli interi del frontend.
- [ ] **Step 5: Commit**: `ricette: «Annulla» dopo il pasto eliminato rimette la ricetta nel ricettario`.

### Task 6: e2e, la verifica, il backlog

- [ ] **Step 1: e2e intera**, con i comandi delle Global Constraints, dentro il limite di carico.
- [ ] **Step 2: Nel browser**, sullo stack e2e prima del `down`: apri «Modifica» di una ricetta in due schede; salva nella prima; salva nella seconda. Si legge «La ricetta è cambiata mentre la correggevi.», e «Ricarica la ricetta» mostra la versione della prima. Uno screenshot a 375 px va nel report.
- [ ] **Step 3: Il backlog.** La voce passa a `fatto <data>` in «Fatti (recenti)», con ` → branch night/ricetta-pasto-lucchetto (da revisionare)`. In `CLAUDE.md`, nella frase «the edit (`PUT /recipes/{id}`) and the recipe's `PATCH` do not yet», scrivi che ora lo prendono, e che il `PUT` rifiuta una versione vecchia (`recipe_changed`). Commit: `next-steps: il lucchetto della ricetta del pasto, fatto`.

## Fuori scope

- La ricetta a mano che vince su quella di Claude (piano `2026-11-22-ricetta-a-mano-vince.md`).
- Una colonna `updated_at` o un numero di versione salvato.
- La versione nel `PATCH` (`cost`, `in_book`, `archived` non li cambia la chat).

## Comandi di verifica

- Backend: il comando di pytest delle Global Constraints, tutto verde, con i test nuovi.
- Frontend, da `<worktree>/frontend`: `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- e2e: la suite intera, verde.
- `git -C <worktree> diff master --stat` tocca solo i file dei task, più `next-steps.md`, `CLAUDE.md` e il report.
