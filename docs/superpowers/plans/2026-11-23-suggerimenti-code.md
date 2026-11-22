# Suggerimenti: da quale alias arriva una riga, e le code del taglio — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:**
- un suggerimento che arriva da un alias lo dice sotto il nome: «Ketchup» per «sal» si legge con «da «salsa ketchup»», e smette di sembrare rumore;
- si chiudono le code lasciate dalla revisione finale di `night/suggerimenti-soglia`:
  - le due famiglie di prove che mancano a `measure_suggestions`;
  - i refusi che finiscono con uno spazio;
  - la prova che `READ ONLY` rifiuta una scrittura;
  - la piega senza NFC;
  - gli spazi doppi del lato database.

**Architecture:**
- **L'alias.** Una funzione pura nel dominio, `matched_alias(query, name, aliases) -> str | None`, accanto a `fold_for_match`. La rotta `/ingredients/search` la chiama per ogni riga e mette il risultato in `IngredientOut.matched_alias`. `suggest_ingredients` non cambia firma: gli alias sono già caricati (`lazy="selectin"`). Nel frontend, `OptionList` e i risultati dell'Anagrafica mostrano «da «‹alias›»» sotto il nome.
- **La piega.** `fold_for_match` normalizza in NFC prima di tradurre. `_folded`, il lato database in `repositories/ingredients.py`, riduce gli spazi ripetuti dopo `translate`, così i due lati del confronto tornano uguali.
- **La misura.** `measure_suggestions` ha due famiglie nuove, «testo lungo» e «singolare/plurale», in fondo, così le prove di oggi restano quelle del seme. I refusi sui primi sei caratteri partono da un prefisso senza spazi in coda, e l'inizio della transazione in sola lettura diventa una funzione che un test prova.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Postgres 16 con `pg_trgm`, pytest su Postgres vero; React 19, TanStack Query 5, Vitest + Testing Library, Playwright.

**Spec:** la bozza `docs/superpowers/specs/2026-10-06-suggerimenti-soglia-bozza.md` e il piano `docs/superpowers/plans/2026-11-22-suggerimenti-anagrafica.md`, che questo piano segue. Le voci sono due idee P3 di `next-steps.md`:
- «Un suggerimento non dice da quale alias arriva» [bozza suggerimenti 2026-10-06];
- «Code dei suggerimenti tagliati» [revisione finale night/suggerimenti-soglia].

**Decisione di Mattia del 2026-11-23**: «da «‹alias›»» sotto il nome, in ogni elenco di suggerimenti, solo quando il nome non contiene il testo scritto.

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/suggerimenti-code`, ramo `night/suggerimenti-code`. Nel piano `<worktree>` è quel percorso.
- **La base.** Questo piano tocca `backend/app/repositories/ingredients.py` (`_folded`) e `frontend/src/features/registry/RegistryScreen.tsx`, come `2026-11-22-suggerimenti-anagrafica.md`.
  - Se il ramo `night/suggerimenti-anagrafica` esiste e ha il commit `next-steps: i quasi-doppioni in Anagrafica, fatto`, crea il ramo **da lì**.
  - Altrimenti crealo da `master`, e scrivi nel report i punti da cucire: `_suggestion_candidates` (l'`ORDER BY` lì, `_folded` qui), la query degli ingredienti di `RegistryScreen` (il `limit` lì, la riga dell'alias qui) e i test di `test_ingredients.py`.

  Anche `2026-11-23-pasti-quarto-giro.md` tocca `repositories/ingredients.py`, ma in `delete_ingredient_if_unused`: funzioni diverse, da segnalare nel report.

  Ogni comando parte dal worktree. **Nessun push, nessun merge, nessun deploy. Mai `git stash`. Niente letture o scritture sulla produzione, e mai il `.env` del checkout principale.**
- **Il taglio non cambia.** Le righe che l'elenco tagliato tiene e il loro ordine restano quelli di oggi. L'unica differenza voluta: un alias o un nome con l'apostrofo seguito da uno spazio ora combacia, perché i due lati della piega sono uguali (Task 3).
- **Prima lezione di `CLAUDE.md`: l'oggetto provato è quello che gira.** L'alias si prova dalla rotta vera. La misura si prova chiamando le funzioni del comando, non una copia.
- **Il frontend non decide** da quale alias arriva una riga: lo dice il server.
- Le parole a video **si copiano esatte** da questo piano (fra «»). Gli identificatori in inglese, i commenti in italiano.
- **Colore e primitive**: solo token di `frontend/src/index.css`, nessun token nuovo. A 375 px una riga dell'elenco con un alias lungo non allarga la pagina: l'alias si tronca.
- **Il type check è `npm run typecheck`**, mai `tsc --noEmit`. Controlli del frontend, da `<worktree>/frontend`: `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- **Il carico sulla macchina**: al massimo 6 thread e 8 GB (Mattia, 2026-11-22). Le suite intere girano dentro `systemd-run --user --scope -p MemoryMax=8G -p CPUQuota=600% …`, mai due insieme. Vitest gira con `--maxWorkers=4`, pytest senza parallelismo.
- **Backend su Postgres vero**: `spena-db-1` (porta 5433), con il database `spena_test_suggerimenti_code`. Mai `docker compose up` dal worktree. Si usa il `.venv` del checkout principale. Il comando di pytest, da `<worktree>/backend`:
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_suggerimenti_code \
    PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
- **e2e** sullo stack `spena-e2e`, con i comandi delle Global Constraints di `docs/superpowers/plans/2026-11-18-pasti-correzioni.md`:
  - il `.env` si copia da `.env.example` e si cancella alla fine;
  - in ogni comando `-p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml`;
  - il seme con le ricette e le due righe della fixture CIQUAL;
  - alla fine sempre `down -v` e `rm .env`;
  - se lo stack c'è e non l'hai alzato tu, aspetta che sparisca.
- Nessuna dipendenza nuova, nessuna migrazione.
- **`measure_suggestions` non si lancia sulla produzione.** È una lettura della produzione e la fa Mattia: va nel «Da fare a mano» (Task 5).

## Review Focus

1. **L'alias si dice solo quando il nome non contiene il testo.** «sal» su «Ketchup» (alias «salsa ketchup») dà `matched_alias == "salsa ketchup"`. «sal» su «Sale» dà `None`, anche se «Sale» ha un alias «sale fino». Una riga arrivata per somiglianza (un refuso), senza un alias che contenga il testo, dà `None`. Task 1.
2. **Fra più alias che contengono il testo vince quello che comincia col testo**, poi il più corto, poi l'ordine alfabetico: la scelta è ripetibile. Task 1.
3. **I due lati della piega sono uguali**, come prova un test che li confronta su ogni carattere di `FOLD_FROM`, più un apostrofo seguito da uno spazio e una lettera con l'accento scomposto. Task 3.
4. **Le prove di oggi della misura non cambiano.** Con lo stesso catalogo, le famiglie «digitazione», «due lettere» e «refusi» danno le stesse prove di prima. Fanno eccezione i refusi sui primi sei caratteri di un nome con lo spazio al sesto posto: lì cambiano, ed è il difetto. Task 4.
5. **`SET TRANSACTION READ ONLY` rifiuta davvero una scrittura**, nella funzione che il comando usa. Task 4.

### Preparazione (una volta, prima del Task 1)

- [ ] La base (Global Constraints), poi il worktree, con `node_modules` collegato e nessun `.env`:
  ```bash
  cd /home/mactyws/coding/ais/spena
  BASE=master
  git log night/suggerimenti-anagrafica --oneline 2>/dev/null | grep -q "i quasi-doppioni in Anagrafica, fatto" && BASE=night/suggerimenti-anagrafica
  echo "base: $BASE"
  git worktree add .worktrees/suggerimenti-code -b night/suggerimenti-code "$BASE"
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/suggerimenti-code/frontend/node_modules
  ```
  **Annota** la base nel report.
- [ ] Il database dei test:
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_suggerimenti_code WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_suggerimenti_code'
  ```
- [ ] Le due voci di `next-steps.md` che citano questo piano passano a `in corso` (` → in corso su night/suggerimenti-code`), e si committa: `next-steps: l'alias dei suggerimenti e le code del taglio, in corso`.
- [ ] La linea di partenza: pytest e vitest dal worktree, tutto verde. **Annota** i numeri. Se non è verde, fermati e scrivilo nel report.

---

## Decisioni prese

1. **Di Mattia (2026-11-23): «da «‹alias›»» sotto il nome, in ogni elenco di suggerimenti, solo quando il nome non contiene il testo scritto.** Gli elenchi sono:
   - `OptionList` (la Lista, il selettore di ingredienti delle ricette e della dispensa, «Abbina»);
   - i risultati dell'Anagrafica.
2. **«Contiene» vuol dire il riscontro dei suggerimenti** (Claude, su delega): il testo piegato all'inizio di una parola del nome piegato, la stessa regola di `is_hit`. Così la riga dice l'alias proprio quando il nome da solo non spiega perché è lì.
3. **Una riga arrivata per somiglianza non dice un alias** (Claude, su delega). Senza un alias che contenga il testo, non si saprebbe quale nominare senza la somiglianza trigram, che sta nel database. Indovinarne uno sarebbe peggio del rumore di oggi.
4. **Le due famiglie nuove della misura** (Claude, su delega), in fondo alle prove, dopo i refusi:
   - «testo lungo»: per ogni nome di almeno 4 lettere, il nome seguito da una parola di `LONGER_WORDS = ("fresco", "bio", "a pezzi", "grattugiato")`, scelta col generatore del seme;
   - «singolare/plurale»: per ogni nome di almeno 4 lettere che finisce per vocale, l'ultima vocale dell'ultima parola scambiata (o↔i, a↔e). «oliva» diventa «olive», «gelati» diventa «gelato».

   Il bersaglio è l'ingrediente da cui la prova nasce. Il rapporto le mostra come le altre famiglie.
5. **I refusi sui primi sei caratteri** partono da `name[:6].rstrip()`, e solo se ne restano almeno 4 lettere (la soglia di `typos`).
6. **La riduzione degli spazi del lato database** è `regexp_replace(…, ' {2,}', ' ', 'g')` dopo `translate`, dentro `_folded` (Claude, su delega). Lo spazio davanti resta, perché è quello che fa di «inizio di parola» «dopo uno spazio».

## Margine di autonomia

- Liberi: i nomi interni e dei test; come `OptionList` fa la seconda riga (purché l'alias sia nella descrizione accessibile, accanto alla categoria); il nome della funzione che apre la transazione in sola lettura (suggerito `begin_read_only(session)`).
- Fissi: `IngredientOut.matched_alias`, `matched_alias` nel dominio, i nomi delle due famiglie, le parole a video.
- **Fermati** (voce `bloccato` nel report) se una prova del taglio di oggi in `tests/api/test_ingredients.py` cambia risultato dopo il Task 3, a parte l'apostrofo seguito da uno spazio.

---

### Task 1: la rotta dice da quale alias arriva una riga

**Files:**
- Modify: `backend/app/domain/suggestions.py` (`matched_alias`)
- Modify: `backend/app/schemas/ingredient.py` (`IngredientOut.matched_alias: str | None = None`)
- Modify: `backend/app/api/ingredients.py` (`search`)
- Test: `backend/tests/domain/test_suggestions.py`, `backend/tests/api/test_ingredients.py`

**Interfaces:**
- Produces: `def matched_alias(query: str, name: str, aliases: Iterable[str]) -> str | None`, con la regola delle decisioni 2 e 3 e l'ordine del Review Focus 2. Riceve testo già in minuscolo, come `fold_for_match`.

- [ ] **Step 1: I test che falliscono.**
  - In `test_suggestions.py`, una tabella:
    - `("sal", "ketchup", ["salsa ketchup"])` → `"salsa ketchup"`;
    - `("sal", "sale", ["sale fino"])` → `None`;
    - `("burro", "olio di cocco", ["burro di cocco"])` → `"burro di cocco"`;
    - `("ketchap", "ketchup", ["salsa ketchup"])` → `None`;
    - `("pom", "pelati", ["passata di pomodoro", "pomodori pelati"])` → `"pomodori pelati"` (comincia col testo);
    - `("caffe", "caffè", ["caffe espresso"])` → `None` (il nome piegato lo contiene).
  - In `test_ingredients.py`, `test_il_suggerimento_dice_l_alias_da_cui_arriva`: «Ketchup» con l'alias «salsa ketchup» e «Sale». `GET /ingredients/search?q=sal` ha «Ketchup» con `matched_alias == "salsa ketchup"` e «Sale» con `matched_alias is None`. Con `trim=false` è lo stesso.
- [ ] **Step 2: Falliscono** (il comando di pytest con quei due file).
- [ ] **Step 3: Il codice.** `search` costruisce ogni `IngredientOut` con `matched_alias=matched_alias(q.strip().lower(), i.name, [a.alias for a in i.aliases])`. Le altre rotte che rispondono `IngredientOut` lasciano `None`. La docstring di `matched_alias` cita le decisioni 2 e 3.
- [ ] **Step 4: Passano**, con `tests/api/test_ingredients*.py`, poi la suite intera.
- [ ] **Step 5: Commit**: `suggerimenti: la rotta dice da quale alias arriva una riga`.

### Task 2: «da «‹alias›»» sotto il nome

**Files:**
- Modify: `frontend/src/domain/types.ts` (`Ingredient.matched_alias?: string | null`)
- Modify: `frontend/src/components/ui/OptionList.tsx`
- Modify: `frontend/src/features/registry/RegistryScreen.tsx` (le righe degli ingredienti, e il componente `Results` se serve una seconda riga)
- Test: `frontend/src/components/IngredientPicker.test.tsx`, `frontend/src/features/shopping-list/AddItemField.test.tsx` (o il test che monta `AddItemField`: `grep -rl AddItemField frontend/src --include=*.test.tsx`), `frontend/src/features/registry/RegistryScreen.test.tsx`

- [ ] **Step 1: I test che falliscono.**
  - In `IngredientPicker.test.tsx`, «il suggerimento dice da quale alias arriva»: con una risposta che ha «Ketchup» e `matched_alias: "salsa ketchup"`, l'opzione «Ketchup» mostra «da «salsa ketchup»», e la sua descrizione accessibile lo contiene. Un'opzione con `matched_alias: null` non mostra niente.
  - In `AddItemField`, lo stesso sul campo della Lista.
  - In `RegistryScreen.test.tsx`: la riga «Ketchup» mostra «da «salsa ketchup»».
- [ ] **Step 2: Falliscono**: `npx vitest run --maxWorkers=4 src/components src/features/shopping-list src/features/registry`.
- [ ] **Step 3: Il codice.**
  - Nell'opzione, il nome e sotto «da «‹alias›»» in `text-xs text-ink-soft`, troncato.
  - La categoria resta in fondo alla riga.
  - L'`id` della descrizione copre la categoria e l'alias insieme.
- [ ] **Step 4: Passano**, poi `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- [ ] **Step 5: Commit**: `suggerimenti: «da «…»» sotto un suggerimento arrivato da un alias`.

### Task 3: i due lati della piega uguali

**Files:**
- Modify: `backend/app/domain/suggestions.py` (`fold_for_match`: `unicodedata.normalize("NFC", text)` prima della traduzione)
- Modify: `backend/app/repositories/ingredients.py` (`_folded`)
- Test: `backend/tests/domain/test_suggestions.py`, `backend/tests/api/test_ingredients.py`

- [ ] **Step 1: I test che falliscono.**
  - `test_la_piega_normalizza_in_nfc`: `fold_for_match("caffè") == "caffe"`.
  - `test_i_due_lati_della_piega_sono_uguali`. Per ogni testo di una lista (ogni carattere di `FOLD_FROM` dentro una parola, «sott' olio», «sott'olio», «pan  grattato»), `SELECT` dell'espressione di `_folded` su quel testo, nel database dei test, dà `" " + fold_for_match(testo)`. È la prova che le due copie non si scollano.
  - In `test_ingredients.py`, `test_un_alias_con_l_apostrofo_e_lo_spazio_combacia`: «tonno» con l'alias «tonno sott' olio»; `GET /ingredients/search?q=tonno sott'olio` (tagliato) ha «tonno».
- [ ] **Step 2: Falliscono** (il comando di pytest con quei due file). Expected: il test dei due lati fallisce su «sott' olio» e «pan  grattato», mentre il test della rotta non trova «tonno».
- [ ] **Step 3: Il codice.** `_folded` diventa `func.concat(" ", func.regexp_replace(func.translate(column, FOLD_FROM, FOLD_TO, type_=String), " {2,}", " ", "g", type_=String))`. Il commento dice perché: `fold_for_match` riduce gli spazi con `split()`. Non tocca gli spazi in testa e in coda, che nei nomi e negli alias dell'anagrafica non ci sono, perché li scrive `canonical_name` con `strip()`. Se il test dei due lati dice il contrario, aggiungi un `btrim` e scrivilo nel report.
- [ ] **Step 4: Passano**, con tutto `tests/api/test_ingredients.py` e `tests/domain/test_suggestions.py`, poi la suite intera. Expected: le altre prove del taglio non cambiano (Margine di autonomia).
- [ ] **Step 5: Commit**: `suggerimenti: la piega uguale nei due lati, NFC e spazi doppi`.

### Task 4: la misura, con le due famiglie e la sola lettura provata

**Files:**
- Modify: `backend/app/cli/measure_suggestions.py` (`FAMILIES`, `LONGER_WORDS`, `longer_texts`, `number_variants`, `build_probes`, `begin_read_only`, `main`, la docstring del modulo)
- Test: `backend/tests/test_measure_suggestions_cli.py`

**Interfaces:**
- Produces:
  - `def number_variants(name: str) -> list[str]`: zero o una prova;
  - `def longer_texts(name: str, rng: random.Random) -> list[str]`: zero o una prova;
  - `async def begin_read_only(session: AsyncSession) -> None`: il primo statement della transazione.

- [ ] **Step 1: I test che falliscono.**
  - `test_le_prove_di_oggi_non_cambiano`: su un catalogo fisso di cinque voci senza spazi al sesto posto, le prove delle tre famiglie di oggi sono quelle che dà il codice di oggi. Prima del cambiamento, salva il risultato di `build_probes` su quel catalogo come elenco atteso nel test.
  - `test_i_refusi_non_finiscono_con_uno_spazio`: per il nome «aceto di mele», nessuna prova dei refusi finisce con uno spazio.
  - `test_singolare_e_plurale`: `number_variants("oliva") == ["olive"]`, `number_variants("gelati") == ["gelato"]`, `number_variants("olio di oliva") == ["olio di olive"]`, `number_variants("sale") == ["sala"]`, `number_variants("tè") == []`.
  - `test_il_testo_lungo`: `longer_texts("pomodoro", random.Random(1))` ha un solo testo, che comincia con «pomodoro » e finisce con una parola di `LONGER_WORDS`.
  - `test_le_famiglie_nuove_stanno_in_fondo`: in `build_probes`, ogni prova delle due famiglie nuove viene dopo l'ultima dei refusi.
  - `test_la_sola_lettura_rifiuta_una_scrittura`. Una sessione nuova sul database dei test (con la fabbrica di sessioni che il `conftest` usa, o con un `create_async_engine` sul `TEST_DATABASE_URL`), poi `begin_read_only`, poi un `INSERT` in `ingredients`. Solleva `DBAPIError` con «read-only» nel messaggio, e alla fine si fa rollback.
- [ ] **Step 2: Falliscono**: il comando di pytest con `tests/test_measure_suggestions_cli.py`.
- [ ] **Step 3: Il codice.**
  - `main` chiama `begin_read_only`.
  - Le famiglie nuove usano lo stesso `rng`, dopo i refusi.
  - La docstring del modulo descrive le cinque famiglie e dice che le due nuove misurano il prezzo del taglio dove la bozza non guardava (§6).
- [ ] **Step 4: Passano**, poi la suite intera.
- [ ] **Step 5: Commit**: `suggerimenti: la misura prova testo lungo e singolare/plurale, e la sola lettura`.

### Task 5: e2e, la verifica, il backlog

- [ ] **Step 1: e2e intera**, con i comandi delle Global Constraints. Se `frontend/e2e/suggerimenti.spec.ts` legge il testo intero di un'opzione, guarda se la riga dell'alias lo cambia, e scrivilo nel report.
- [ ] **Step 2: Nel browser**, sullo stack e2e prima del `down`, a 375 px:
  - in Lista scrivi le prime lettere di un alias del seme che non sono nel nome: si legge «da «…»»;
  - lancia `measure_suggestions` **sullo stack e2e** (`docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.measure_suggestions`): il rapporto ha le cinque famiglie;
  - lo screenshot e il rapporto vanno nel report.
- [ ] **Step 3: Il backlog.**
  - Le due voci passano a `fatto <data>` in «Fatti (recenti)», con ` → branch night/suggerimenti-code (da revisionare)`.
  - Alla riga di «Da fare a mano» che comincia con «Dopo il deploy dei suggerimenti tagliati: la misura sull'anagrafica vera», aggiungi in fondo: « Da night/suggerimenti-code la misura ha anche «testo lungo» e «singolare/plurale»: guarda quanti «persi» danno.».
  - Commit: `next-steps: l'alias dei suggerimenti e le code del taglio, fatto`.

## Fuori scope

- Cambiare il taglio perché tenga i plurali (per esempio «olive» per «oliva»): prima la misura sulla produzione, poi un'idea a parte.
- Normalizzare in NFC i nomi già scritti nel database.
- L'alias nelle risposte di altre rotte (`/match`, la scheda dell'Anagrafica).

## Comandi di verifica

- Backend: il comando di pytest delle Global Constraints, tutto verde, con i test nuovi.
- Frontend, da `<worktree>/frontend`: `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- e2e: la suite intera, verde.
- `git -C <worktree> diff <base> --stat` tocca solo i file dei task, più `next-steps.md` e il report.
