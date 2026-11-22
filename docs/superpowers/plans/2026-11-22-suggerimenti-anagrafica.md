# I quasi-doppioni in Anagrafica: 50 righe, e i simili subito dopo i prefissi — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** cercando «pomodoro» in Anagrafica, i quasi-doppioni scritti al plurale o con un refuso («pomodori», «pomodro») si vedono subito dopo «pomodoro», anche quando dieci o più nomi contengono la parola.

**Architecture:** l'elenco intero (`trim=false`) cambia ordine: dopo i prefissi va per somiglianza, non più «prima tutti i riscontri». È un argomento di `_suggestion_candidates` (`hits_first`), che `suggest_ingredients(trim=False)` spegne. L'elenco tagliato, cioè il default di tutti gli altri chiamanti, non cambia di una riga. Nel frontend, `searchIngredients` impara un `limit`, e solo l'Anagrafica chiede 50 righe, con una chiave della cache sua.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Postgres 16 con `pg_trgm`, pytest su Postgres vero; React 19, TanStack Query 5, Vitest + Testing Library, Playwright.

**Spec:** la voce `tbd` P2 «Suggerimenti: nell'Anagrafica l'elenco intero…» di `next-steps.md` (revisione finale del 2026-11-21, ramo `night/suggerimenti-soglia`), più il piano che ha fatto l'elenco intero, `docs/superpowers/plans/2026-11-18-suggerimenti-elenco-intero.md`, e la bozza `docs/superpowers/specs/2026-10-06-suggerimenti-soglia-bozza.md`. **Decisione di Mattia del 2026-11-22**: «50 righe e simili in alto», senza una misura sulla produzione prima.

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/suggerimenti-anagrafica`, ramo `night/suggerimenti-anagrafica`, creato da `master`. Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì, mai dalla radice del checkout principale, che non si tocca. **Nessun push, nessun merge, nessun deploy. Mai `git stash`. Niente letture o scritture sulla produzione, e mai il `.env` del checkout principale.**
- **L'elenco tagliato non cambia.** Senza `trim=false`, `GET /api/v1/ingredients/search` risponde come oggi: stesso filtro, stesso ordine, stesso `LIMIT`. I test che lo fissano oggi restano come sono. `search_ingredients`, `match_name`, i vicini per l'AI, gli strumenti di Claude e `measure_suggestions` non si toccano.
- **Il filtro non cambia nemmeno per l'elenco intero**: lo stesso `HAVING` (somiglianza ≥ `SIMILARITY_FLOOR`, prefisso o riscontro). Cambia solo l'`ORDER BY`.
- **I numeri si scrivono una volta sola.** Il 50 dell'Anagrafica è una costante del frontend (`REGISTRY_SEARCH_LIMIT = 50` in `frontend/src/features/registry/RegistryScreen.tsx`). Il tetto della rotta resta `le=50`. Nessuna soglia nuova nel backend.
- **Prima lezione di `CLAUDE.md`: l'oggetto provato è quello che gira.** I test del backend passano dall'endpoint vero. Quelli del frontend guardano l'URL che parte davvero, non una copia.
- **Mai un vicolo cieco**: l'Anagrafica tiene «Nessun ingrediente con questo nome.», e «Abbina» tiene «Aggiungi «…»».
- Nessuna parola a video nuova, nessun token di colore nuovo. `grep -rn "emerald\|neutral-" frontend/src` dà solo il commento che c'è già in `index.css`.
- **Il type check è `npm run typecheck`**, mai `tsc --noEmit`. Controlli del frontend, da `<worktree>/frontend`: `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- **Il carico sulla macchina**: al massimo 6 thread e 8 GB (Mattia, 2026-11-22). Le suite intere girano dentro `systemd-run --user --scope -p MemoryMax=8G -p CPUQuota=600% …`, mai due insieme; vitest con `--maxWorkers=4`.
- **Backend su Postgres vero**: `spena-db-1` (porta 5433), con il database `spena_test_suggerimenti_anagrafica`. Mai `docker compose up` dal worktree. Si usa il `.venv` del checkout principale. Il comando di pytest, da `<worktree>/backend`:
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_suggerimenti_anagrafica \
    PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
- **e2e** sullo stack `spena-e2e`, con i comandi delle Global Constraints di `docs/superpowers/plans/2026-11-18-suggerimenti-elenco-intero.md`: il `.env` da `.env.example` e cancellato alla fine; `-p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml` in ogni comando; il seme con le ricette e le due righe della fixture CIQUAL; `down -v` e `rm .env` sempre. Se lo stack c'è e non l'hai alzato tu, aspetta che sparisca.
- Nessuna dipendenza nuova, nessuna migrazione.

## Review Focus

1. **Un chiamante che non dice niente** (Lista, Dispensa, modulo della ricetta, coda, sostituti, «Fondi»): resta tagliato, non manda `limit` e riceve 10 righe. Lo provano il Task 1 (i test del taglio che restano) e il Task 2 (`IngredientPicker` senza `limit`).
2. **«Abbina» e l'Anagrafica cercano la stessa parola nella stessa sessione**: con la chiave della cache condivisa, «Abbina» riceverebbe 50 righe o l'Anagrafica 10. Lo prova il Task 2 (`ingredientSearchKey` con e senza `limit`).
3. **Un prefisso esatto resta in cima** anche quando un quasi-doppione è più simile in punteggio. Lo prova il Task 1 (`pomodoro` primo).
4. **Il testo lungo di «Abbina»** («pasta barilla integrale») trova ancora la pasta per prima, perché lì non ci sono prefissi né riscontri e l'ordine per somiglianza era già quello. Resta il test di oggi `test_l_elenco_intero_trova_l_ingrediente_nel_testo_lungo_della_voce`.
5. **`limit` oltre 50 o non numerico** è un 422, come oggi. Il frontend non lo manda mai.

### Preparazione (una volta, prima del Task 1)

- [ ] Il worktree, con `node_modules` collegato e nessun `.env`:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/suggerimenti-anagrafica -b night/suggerimenti-anagrafica master
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/suggerimenti-anagrafica/frontend/node_modules
  ```
- [ ] Il database dei test:
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_suggerimenti_anagrafica WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_suggerimenti_anagrafica'
  ```
- [ ] La voce di `next-steps.md` che cita questo piano passa a `in corso` (` → in corso su night/suggerimenti-anagrafica`), e si committa: `next-steps: i quasi-doppioni in Anagrafica, in corso`.
- [ ] La linea di partenza: pytest e vitest dal worktree, tutto verde. **Annota** i numeri. Se non è verde, fermati e scrivilo nel report.

---

## Decisioni prese

1. **Di Mattia (2026-11-22): 50 righe e i simili in alto**, per l'Anagrafica. Una misura su `measure_suggestions` prima non serve: è una lettura della produzione, e oggi il comando non prova singolari e plurali (idea «Code dei suggerimenti tagliati»), quindi non risponderebbe alla domanda.
2. **L'ordine nuovo vale per tutto l'elenco intero, quindi anche per «Abbina»** (Claude, su delega per le scelte tecniche). Con il testo lungo della voce non ci sono riscontri, e l'ordine per somiglianza era già quello. Con un testo corto, un quasi-doppione più simile sale sopra un riscontro lontano, che è quel che serve anche lì. Un terzo modo di ordinare, solo per l'Anagrafica, sarebbe una porta in più da tenere uguale.
3. **I 50 li chiede solo l'Anagrafica.** «Abbina» resta a 10: un pannello aperto sotto una voce della spesa non deve diventare una pagina.
4. **Cade la proprietà «l'elenco tagliato è l'inizio di quello intero»**, decisione 4 del piano del 2026-11-18. Era vera solo perché i due elenchi avevano lo stesso ordine. Ora resta vera una proprietà più debole: con un `limit` che li contiene tutti, **ogni riga tagliata è anche nell'elenco intero** (stesso filtro). Il test di oggi si riscrive così, e la docstring di `suggest_ingredients` lo dice.
5. **Il nuovo ordine dell'elenco intero**: prima i prefissi, con gli acquisti fra i prefissi (come oggi); poi la somiglianza dal più simile; poi gli acquisti; poi il nome. `is_hit` non entra più nell'ordine.

## Margine di autonomia

- Liberi: i nomi interni e dei test, le parole dei commenti.
- Fissi: il nome `hits_first` e il suo default `True`; la firma pubblica di `suggest_ingredients`; il parametro `limit` di `searchIngredients` e la forma della chiave; il 50.
- **Fermati** (voce `bloccato` nel report) se una prova del taglio di oggi cambia risultato: vorrebbe dire che l'elenco tagliato è stato toccato.

---

### Task 1: l'elenco intero va per somiglianza dopo i prefissi

**Files:**
- Modify: `backend/app/repositories/ingredients.py` (`_suggestion_candidates`, `suggest_ingredients` e la sua docstring)
- Test: `backend/tests/api/test_ingredients.py`

**Interfaces:**
- Produces: `async def _suggestion_candidates(session, query: str, limit: int, kind: IngredientKind | None, *, hits_first: bool = True) -> list[ScoredIngredient]`. `suggest_ingredients(..., trim=False)` la chiama con `hits_first=False`, mentre `trim=True` la chiama come oggi.

- [ ] **Step 1: I test che falliscono**, accanto a quelli dell'elenco intero, con gli helper `_ingredienti` e `_suggeriti` che il file ha già:

```python
async def test_l_elenco_intero_mette_i_quasi_doppioni_subito_dopo_i_prefissi(logged_client, db_session):
    """La voce P2 del 2026-11-21, decisa da Mattia il 2026-11-22: con dieci riscontri o più
    il quasi-doppione restava fuori. «pomodori» e «pomodro» non contengono «pomodoro», ma
    gli somigliano più di ogni «sugo … di pomodoro»."""
    sughi = [f"sugo {i:02} di pomodoro" for i in range(1, 12)]
    await _ingredienti(db_session, "pomodoro", "pomodori", "pomodro", *sughi)

    intero = await _suggeriti(logged_client, "pomodoro", trim="false")
    assert len(intero) == 10
    assert intero[0] == "pomodoro"
    assert set(intero[1:3]) == {"pomodori", "pomodro"}

    # il taglio non cambia: solo chi contiene il testo
    tagliato = await _suggeriti(logged_client, "pomodoro")
    assert "pomodori" not in tagliato and "pomodro" not in tagliato
```

Poi riscrivi `test_l_elenco_tagliato_e_l_inizio_di_quello_intero` come `test_ogni_riga_tagliata_e_anche_nell_elenco_intero`, con gli stessi ingredienti e gli stessi testi: per ogni testo, `tagliato` è quello senza `trim`, ed è uguale a quello con `trim="true"`; `intero` è quello con `trim="false", limit="50"`; si controlla `set(tagliato) <= set(intero)`. La docstring cita la decisione 4 di questo piano.

- [ ] **Step 2: Falliscono.** Il comando di pytest con `tests/api/test_ingredients.py`. Expected: il test nuovo FAIL, perché `pomodori` e `pomodro` restano fuori dalle prime dieci righe; quello riscritto passa già.

- [ ] **Step 3: Il codice.** Con `hits_first=False`, l'`order_by` di `_suggestion_candidates` è `is_prefix_match.desc()`, `case((is_prefix_match, purchase_count), else_=0).desc()`, `best_similarity.desc()`, `purchase_count.desc()`, `Ingredient.name.asc()`. Con `True` resta quello di oggi. Il `HAVING` è lo stesso nei due casi. La docstring di `_suggestion_candidates` dice perché il `LIMIT` resta sicuro anche così: nell'elenco intero nessun taglio viene dopo. Quella di `suggest_ingredients` sostituisce «l'elenco tagliato è sempre l'inizio di quello intero» con la decisione 4.

- [ ] **Step 4: Passano**, con tutto `tests/api/test_ingredients.py`, `tests/domain/test_suggestions.py` e i test di `measure_suggestions` (`grep -rl measure_suggestions tests`). Poi la suite intera. Expected: tutto verde, e gli altri test toccati sono zero.

- [ ] **Step 5: Commit**: `suggerimenti: l'elenco intero mette i simili subito dopo i prefissi`.

### Task 2: l'Anagrafica chiede 50 righe

**Files:**
- Modify: `frontend/src/features/shopping-list/api.ts` (`ingredientSearchKey`, `searchIngredients`)
- Modify: `frontend/src/features/registry/RegistryScreen.tsx` (la query degli ingredienti, `REGISTRY_SEARCH_LIMIT`, il commento)
- Test: `frontend/src/features/registry/RegistryScreen.test.tsx`; Create: `frontend/src/features/shopping-list/api.test.ts` per la chiave (oggi nessun test la nomina)

**Interfaces:**
- Consumes: la rotta di oggi, `GET /api/v1/ingredients/search?q=…&trim=false&limit=50`.
- Produces: `searchIngredients(query: string, kind?: "food", { trim = true, limit }: { trim?: boolean; limit?: number } = {})`, che manda `limit` solo se c'è. `ingredientSearchKey(term: string, kind?: "food", trim = true, limit?: number)`: senza `limit`, le chiavi di oggi; con `limit`, quella stessa chiave con `limit` aggiunto in coda.

- [ ] **Step 1: I test che falliscono.**
  - In `RegistryScreen.test.tsx`, «chiede l'elenco intero di 50 righe»: dopo aver scritto «pomodoro», l'URL che parte ha `trim=false` e `limit=50`.
  - Nel test della chiave: `ingredientSearchKey("pomodoro", undefined, false, 50)` è diversa da `ingredientSearchKey("pomodoro", undefined, false)`, e quest'ultima è uguale a quella di oggi.
  - I test di `IngredientPicker` e di `MatchPanel` che guardano l'URL restano come sono: niente `limit`.
- [ ] **Step 2: Falliscono**: `npx vitest run src/features/registry src/features/shopping-list/api.test.ts src/components/IngredientPicker.test.tsx`.
- [ ] **Step 3: Il codice.** `RegistryScreen` usa `ingredientSearchKey(debounced, undefined, false, REGISTRY_SEARCH_LIMIT)` e `searchIngredients(debounced, undefined, { trim: false, limit: REGISTRY_SEARCH_LIMIT })`. Il commento sopra la query dice anche il 50, e che la chiave non è quella di «Abbina».
- [ ] **Step 4: Passano**, poi i controlli interi del frontend: `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- [ ] **Step 5: Commit**: `anagrafica: fino a 50 ingredienti, con una chiave della cache sua`.

### Task 3: e2e, la verifica finale, il backlog

- [ ] **Step 1: e2e intera** con i comandi delle Global Constraints. Se `frontend/e2e/anagrafica.spec.ts` cerca una parola e conta le righe, guarda se l'ordine nuovo la cambia. Va corretta solo se la riga che si aspetta era un riscontro che ora viene dopo un simile: scrivilo nel report.
- [ ] **Step 2: Verifica nel browser**, sullo stack e2e prima del `down`, a 375 px: in Anagrafica, cercando una parola del seme con un plurale o un refuso nell'anagrafica (aggiungilo dal ☰ se il seme non ne ha), il quasi-doppione è nelle prime righe. Uno screenshot va nel report.
- [ ] **Step 3: Il backlog.** La voce passa a `fatto <data>` in «Fatti (recenti)», con ` → branch night/suggerimenti-anagrafica (da revisionare)`. La voce di «Da fare a mano» sulla misura dei suggerimenti tagliati resta com'è. Commit: `next-steps: i quasi-doppioni in Anagrafica, fatto`.

## Fuori scope

- Le famiglie di prove che mancano a `measure_suggestions` (singolare e plurale, testo più lungo): restano nell'idea «Code dei suggerimenti tagliati».
- Dire da quale alias arriva un suggerimento (idea a parte).
- L'elenco intero per altri chiamanti, o 50 righe per «Abbina».

## Comandi di verifica

- Backend: il comando di pytest delle Global Constraints, tutto verde, con i test nuovi.
- Frontend, da `<worktree>/frontend`: `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- e2e: la suite intera, verde.
- `git -C <worktree> diff master --stat` tocca solo i file dei due task, più `next-steps.md` e il report.
