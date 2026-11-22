# Pasti con Claude: la chiave API e le correzioni della chat — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** la chat dei Pasti (piatto, pianificazione, ricette della coda) passa dal token dell'abbonamento alla **chiave API** di Anthropic, con il costo vero registrato e contato nelle «Spese dell'AI» come ogni altra sezione; e si chiudono i sette rilievi della revisione del 2026-11-18 sulla chat (C1–C7).

**Architecture:** l'impostazione `anthropic_api_key` (variabile `ANTHROPIC_API_KEY`) prende il posto di `claude_code_oauth_token`, e il client la passa all'SDK con i due token spenti. Il client porta in `ClaudeUsage` il `total_cost_usd` del `ResultMessage`, anche sui giri falliti, e riconosce due guasti nuovi (credito finito, troppi passaggi). Il resto sono correzioni puntuali: un flag del CLI che non scrive trascrizioni, l'istantanea del pasto che protegge le correzioni a mano, le letture degli strumenti che chiudono la transazione, «Annulla» che toglie gli ingredienti creati, la vista della chat che legge lo stato del pasto una volta sola. Una migrazione, la `0023`.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Alembic, pytest su Postgres vero; `claude-agent-sdk==0.2.180` (già nel progetto, binario Claude Code 2.1.321), mai chiamato in rete nei test; React 19, TypeScript, Tailwind 4, TanStack Query, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-12-pasti-claude-design.md` (§3 cambia con questo piano, Task 11). I rilievi e le decisioni di Mattia sono quelli della revisione del 2026-11-18, riportati qui sotto («Decisioni prese»); la catena da cui parte è descritta in `docs/superpowers/plans/2026-11-12-pasti-claude.md`, `docs/superpowers/plans/2026-11-12-pasti-pianificazione.md` e nel report `docs/night-reports/2026-11-13.md`. Leggi `CLAUDE.md` del repo prima di cominciare: le sette lezioni valgono tutte.

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/pasti-chiave-api`, ramo `night/pasti-chiave-api`, creato da **`master`**. Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì, mai dalla radice del checkout principale, che non si tocca (le modifiche non committate che ci trovi sono dell'utente). **Nessun push, nessun merge, nessun deploy. Mai `git stash`. Niente letture o scritture sulla produzione, e mai il `.env` del checkout principale. Nessuna chiamata vera a Claude: niente chiave, niente rete** (il Task 2 lancia il binario vero contro `127.0.0.1:9`, una porta chiusa sulla macchina: non è rete).
- **Leggi ogni file com'è sul ramo prima di cambiarlo.** Le righe citate dai rilievi sono indicative; il piano descrive le modifiche contro ancore riconoscibili (una funzione, una costante, una riga esatta). Dove il piano dà un elenco di firme per un file che non c'è, è un file nuovo.
- **I nomi della catena si usano così come sono**: `SdkClaudeClient`, `build_options`, `translate`, `TurnState`, `_classify_status`, `claude_configured`, `ClaudeUsage`, `ClaudeFailure`, `TurnFinished`, `TurnFailed`, `TextDelta` (`app.services.claude.client`); `FailureKind`, `failure_notice`, `DISH_MAX_TURNS` (`app.domain.meal_chat`); `run_chat_turn`, `_turn`, `_fail`, `chat_messages_out`, `change_out`, `dish_chat_view`, `_dish_prepare` (`app.services.meal_chat`); `TurnContext`, `read_tools`, `write_recipe_tool` (`app.services.claude.tools`); `write_meal_recipe`, `meal_snapshot`, `change_is_undoable`, `undo_recipe_change` (`app.services.meal_recipes`); `resolve_lines` (`app.services.recipe_writing`); `_settle_meal`, `TERMINAL_FAILURES`, `NOT_WRITTEN_NOTICE` (`app.services.recipe_jobs`); `delete_ingredient_if_unused` (`app.repositories.ingredients`); `FakeClaude`, `Say`, `UseTool`, `Finish`, `Fail`, `Hang` (`backend/tests/claude_fakes.py`). **Se un nome sul ramo è diverso**, vale il codice: usalo e scrivilo nel report.
- **Prima lezione di `CLAUDE.md`.** I test non usano la rete: il client si inietta (`get_claude_client`), il finto chiama gli stessi strumenti della produzione, e il client di produzione si prova con i tipi veri dell'SDK e `query` sostituita. L'unica eccezione è il Task 2, che lancia il **binario vero** incluso nel pacchetto, senza rete.
- **Mai un vicolo cieco.** Senza chiave, con il credito finito o il limite di frequenza, la chat lo dice e la ricetta, «Modifica», «Scrivi la ricetta», «Scegli dal ricettario» e la settimana funzionano a mano.
- **Il frontend non calcola logica di dominio**: gli avvisi arrivano scritti dal backend.
- **Colore e primitive**: solo token di `frontend/src/index.css`, **nessun token nuovo**; `grep -rn "emerald\|neutral-" frontend/src` resta vuoto; ogni testo sopra 4,5:1 nei due temi (misurato da `frontend/e2e/style.spec.ts`); primitive da `frontend/src/components/ui/`.
- Le parole a video sono in italiano e **si copiano esatte** da questo piano (fra «»; ‹…› è un valore). Gli identificatori in inglese, i commenti in italiano.
- **Il type check è `npm run typecheck`**, mai `tsc --noEmit`. Controlli del frontend, da `<worktree>/frontend`: `npx vitest run`, `npm run typecheck`, `npm run lint`, `npm run build`. Nei test dei componenti si usa `createTestQueryClient`.
- **Backend su Postgres vero**: `spena-db-1` (porta 5433), con il database di questo ramo, `spena_test_pasti_chiave_api`. Mai `docker compose up` dal worktree, mai `-f docker-compose.prod.yml`. Si usa il `.venv` del checkout principale (ha già `claude-agent-sdk==0.2.180`). Il comando di pytest, da `<worktree>/backend`:
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_pasti_chiave_api \
    PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
- **e2e** sullo stack `spena-e2e` (il `.env` copiato da `.env.example` e cancellato alla fine; `-p spena-e2e` e `-f docker-compose.e2e.yml` in ogni comando; se lo stack c'è e non l'hai alzato tu, aspetta che sparisca). Con le due righe della fixture CIQUAL, senza le quali 6 prove di S4 danno 409:
  ```bash
  cp .env.example .env
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed --con-ricette
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python tests/ciqual_fixture.py /tmp/ciqual-e2e.xlsx
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.load_ciqual /tmp/ciqual-e2e.xlsx
  (cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
  rm .env
  ```
- **Nessuna dipendenza nuova**, nel backend e nel frontend. Nel `pyproject.toml` non va scritta la parola `anthropic` (lo controlla `test_anthropic_non_e_piu_una_dipendenza_di_nessun_tipo`). **Una migrazione sola, la `0023`** (`backend/alembic/versions/0023_modifiche_ingredienti.py`, `down_revision = "0022"`).
- **I test di oggi si cambiano solo dove il piano lo dice.** Questo piano cambia, e solo in questi punti: le frasi vecchie degli avvisi (token, piano, `claude setup-token`) e `FailureKind.PLAN_LIMIT`/`"plan_limit"` ovunque compaiano (Task 3 e Task 10); il dizionario `env` e la prova sulla chiave nell'ambiente in `test_claude_client.py` (Task 1); la classificazione di `error_max_turns` in `test_i_guasti` (Task 3); `cost_usd is None` sui giri dei Pasti (Task 4); `test_settings_claude.py` e il blocco «sul piano» delle spese (Task 1, Task 5). Il resto, se cade, è un comportamento cambiato: si corregge il codice.

### Preparazione (una volta, prima del Task 1)

- [ ] **Il ramo di partenza.**
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify master
  ls backend/alembic/versions | grep -E '^002[0-9]_'
  ls .worktrees/pasti-chiave-api 2>&1 | head -1
  ```
  Expected: un hash (**annotalo**: è `BASE` del Task 11); `0020_pasti.py`, `0021_chat_pasti.py`, `0022_pianificazione.py` e nient'altro; `No such file or directory`. Se c'è già una `0023`, o il worktree esiste, fermati e scrivilo nel messaggio finale della notte.
- [ ] **Il database dei test di questo ramo**:
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_pasti_chiave_api WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_pasti_chiave_api'
  ```
- [ ] `cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund`.
- [ ] **Il worktree**, con `node_modules` collegato e nessun `.env`:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/pasti-chiave-api -b night/pasti-chiave-api master
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/pasti-chiave-api/frontend/node_modules
  ```
- [ ] **La testa di Alembic**, da `<worktree>/backend`: `DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_pasti_chiave_api PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" alembic heads`. Expected: una riga sola, `0022 (head)`.
- [ ] **La voce del backlog.** In `next-steps.md` la voce che cita questo piano (`2026-11-18-pasti-chiave-api.md`) passa a `in corso`, con in coda ` → in corso su night/pasti-chiave-api`. Commit: `git commit -m "next-steps: la chiave API e le correzioni della chat dei Pasti, in corso"`. Se la voce non c'è, aggiungila sotto «In corso» nello stile delle altre, con `[Parte IV]`.
- [ ] **La linea di partenza**: vitest e pytest dal worktree, tutto verde. **Annota** `N_file`, `N_vitest` e `N_pytest`. Se non è verde, fermati: va nel report.

---

## Obiettivo e contesto

La catena «Pasti con Claude» è su `master` (4537139) e non è mai andata in produzione. Era costruita sul token dell'abbonamento di Mattia (`CLAUDE_CODE_OAUTH_TOKEN`), con le chiamate registrate senza costo e mostrate a parte «sul piano». Il 2026-11-18 Mattia ha deciso di passare alla chiave API, sui suoi crediti: è la strada che i termini dell'Agent SDK indicano (vedi l'avvertenza in testa al piano del 2026-11-12), ed è la stessa chiave che userà il passaggio dell'LLM dell'import a Claude Haiku (voce separata del backlog, spec a parte). Lo stesso giorno quattro revisori hanno trovato sette difetti nella chat; questo piano li chiude.

## Decisioni prese

Di Mattia (2026-11-18):

1. **La chat dei Pasti usa la chiave API**, `ANTHROPIC_API_KEY` (impostazione `anthropic_api_key`), la stessa che userà l'LLM dell'import con Haiku. `CLAUDE_CODE_OAUTH_TOKEN` e `ANTHROPIC_AUTH_TOKEN` si passano **vuoti** all'SDK. Il modello resta `claude-opus-5-5`.
2. **Il costo vero** (`ResultMessage.total_cost_usd`) va in `llm_calls.cost_usd`, e «Spese dell'AI» smette di mostrare i Pasti a parte: le tre sezioni (`meal_chat`, `meal_planning`, `meal_recipe`) contano nel totale, nelle quote e nei giorni come tutte le altre.
3. **Gli avvisi parlano di chiave API, credito e limite di frequenza**, non di token e di limite del piano; `check_claude` controlla la chiave.
4. **C6: «Annulla» toglie l'ingrediente creato da quella modifica se nient'altro lo usa** (ricette, dispensa, lista), come l'annullamento dell'import.

Del piano (Claude, sui rilievi; Mattia le rivede nel report):

5. **C1 — l'istantanea del pasto.** All'inizio del giro del piatto si tiene l'istantanea (`meal_snapshot`) del pasto che Claude vede nel prompt. `write_recipe` scrive solo se il pasto è ancora uguale a quella; se no rifiuta con una frase che dice a Claude di rileggere, e non scrive niente. L'istantanea si aggiorna dopo ogni scrittura riuscita dello stesso giro e quando `read_meals` rilegge quel pasto.
6. **C2 — niente trascrizioni su disco.** Il CLI riceve `--no-session-persistence` (`extra_args`). **Verificato dalla fase giorno il 2026-11-18 sul binario 2.1.321 incluso nel pacchetto**, con `query()` vera, `ANTHROPIC_BASE_URL=http://127.0.0.1:9` e un `HOME` vuoto: senza il flag nasce `.claude/projects/<cwd>/<sessione>.jsonl`, con il flag no; in tutti e due i casi il giro finisce con un `ResultMessage` e poi un `ResultError` (connessione rifiutata), in circa 2 secondi. `CLAUDE_CODE_SKIP_PROMPT_HISTORY=1` resta (ferma la cronologia dei prompt, che è un'altra cosa).
7. **C4 — troppi passaggi.** Un `ResultMessage` con `subtype="error_max_turns"` è un guasto suo, `FailureKind.MAX_TURNS`, che porta il testo arrivato fin lì. Nella chat **non è un messaggio fallito**: il messaggio di Mattia diventa `sent`, la risposta di Claude si salva con il testo parziale e sotto ha l'avviso, senza «Riprova» (rifarebbe la stessa richiesta). Le modifiche e le schede del giro restano sotto quella risposta. Nella coda delle ricette conta come «ha risposto senza scrivere la ricetta» se la ricetta non c'è.
8. **C5 — l'uso anche sui giri falliti.** Ogni giro registra token e costo che l'SDK dichiara, riuscito o no; un guasto senza `ResultMessage` (tempo massimo, rete, eccezione) resta senza token e senza costo, perché l'assenza è la verità.
9. **Gli avvisi nuovi.** `FailureKind.PLAN_LIMIT` diventa `RATE_LIMIT = "rate_limit"` (429, `rate_limit`, `RateLimitEvent` respinto) e nasce `CREDIT = "credit"` (`billing_error`, 402). `AUTH` (401, 403, `authentication_failed`) parla della chiave. Le frasi sono nel Task 3, fisse.
10. **C3 — le letture chiudono la transazione** con un `commit` dopo ogni lettura degli strumenti (con `expire_on_commit=False` gli oggetti restano; non c'è mai niente in sospeso, perché le scritture si committano da sé).
11. **C6 — come si sa che cosa ha creato una modifica.** `resolve_lines` riceve un elenco facoltativo in cui annota gli id degli ingredienti che crea (gli altri chiamanti non cambiano), e `write_meal_recipe` lo salva nella colonna nuova `recipe_changes.created_ingredient_ids` (JSONB, `'[]'` di default: le modifiche di prima non tolgono niente). L'annullamento chiama `delete_ingredient_if_unused` per ognuno, **dopo** aver rimesso la versione di prima. Conseguenza voluta: annullare una «Ricetta scritta» archivia la ricetta (come oggi) e quella ricetta archiviata usa ancora i suoi ingredienti, che quindi restano (si può ripristinarla dall'Anagrafica).
12. **C7 — una lettura del pasto per vista.** `undoable_change_ids` calcola quali modifiche si possono annullare leggendo una volta per pasto; la vista della chat e `change_is_undoable` passano tutte da lì (una copia sola). Il frontend continua a rileggere ogni 2 s mentre Claude risponde.
13. **`check_claude`** stampa `chiave API: presente` o `chiave API: assente` (mai il valore) e avvisa se nell'ambiente c'è `CLAUDE_CODE_OAUTH_TOKEN`, che la chat ignora. `--prova` resta, e con la chiave costa qualche centesimo.

## Criteri di accettazione

- [ ] Con `ANTHROPIC_API_KEY` valorizzata la chat è collegata; vuota o assente, dice «Claude non è collegato: manca la chiave API sul server.». L'SDK riceve la chiave, i due token vuoti e `--no-session-persistence`.
- [ ] Il binario vero, con le opzioni di produzione, non scrive nessun JSONL sotto `projects/` (e senza il flag lo scriverebbe: il test lo mostra).
- [ ] Ogni giro dei Pasti, riuscito o fallito con un `ResultMessage`, ha in `llm_calls` token e `cost_usd` dell'SDK; «Spese dell'AI» li conta nel totale, senza il blocco «Claude».
- [ ] Gli avvisi parlano di chiave API, credito e limite di frequenza; «troppi passaggi» lascia la risposta parziale con l'avviso e senza «Riprova».
- [ ] Una correzione a mano durante il giro non si perde (C1); le letture non lasciano la sessione «idle in transaction» (C3); «Annulla» toglie l'ingrediente creato se nient'altro lo usa (C6); la vista della chat fa lo stesso numero di query con una o otto modifiche (C7).
- [ ] La `0023` sale e scende. Tutti i test di oggi passano, cambiati solo dove il piano lo dice. L'e2e intera è verde.
- [ ] Spec §3, `CLAUDE.md`, `README.md`, `.env.example`, l'avvertenza del piano del 2026-11-12, la nota nel report del 2026-11-13, `next-steps.md` e il report di questa notte sono aggiornati.

## Comandi di verifica

Da `<worktree>/backend`: il comando di pytest. Da `<worktree>/frontend`: `npx vitest run`, `npm run typecheck`, `npx tsc -b --force`, `npm run lint`, `npm run build`. Dalla radice di `<worktree>`:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -rn "claude_code_oauth_token\|PLAN_LIMIT\|plan_limit\|PLAN_CALL_SITES\|PLAN_NOTE\|plan_sections\|PlanSection" backend/app backend/tests frontend/src frontend/e2e
grep -rn "token del piano\|limite del piano\|setup-token\|sul piano di Claude" backend/app backend/tests frontend/src frontend/e2e .env.example README.md CLAUDE.md
grep -n "no-session-persistence" backend/app/services/claude/client.py
git diff master --stat -- backend/alembic/versions
```

Expected: il primo vuoto; il secondo vuoto; il terzo vuoto; il quarto una riga; l'ultimo un file solo, `0023_modifiche_ingredienti.py`. Poi l'e2e intera con i comandi delle Global Constraints e, dentro lo stack, `exec -T backend python -m app.cli.check_claude` (Task 10).

## Review Focus

1. **La chiave nell'ambiente del processo di prova o della notte.** La shell di un agente può avere `ANTHROPIC_*` o `CLAUDE_CODE_*` nell'ambiente (questa ha `ANTHROPIC_BASE_URL`). La suite non deve mai credersi collegata per caso, né mandare una chiave vera da qualche parte: il fixture automatico di `conftest.py` toglie `ANTHROPIC_API_KEY` e `CLAUDE_CODE_OAUTH_TOKEN` (Task 1, `test_la_suite_parte_senza_chiave`).
2. **Il credito che finisce a metà settimana.** La coda delle ricette si ferma al primo «credito finito» e non chiama Claude per gli altri sei pasti; ognuno resta con l'avviso e con «Scrivi la ricetta» (Task 4, `test_il_credito_finito_ferma_la_coda`).
3. **Mattia corregge la dose mentre Claude risponde, poi Claude scrive** (C1): la correzione resta, e lo strumento torna a Claude con la frase di rilettura (Task 6, `test_una_correzione_a_mano_durante_il_giro_non_si_perde`).
4. **Un giro che finisce i passaggi dopo aver scritto la ricetta**: la modifica resta con «Annulla», la risposta parziale si legge, l'avviso c'è e «Riprova» no (Task 4, `test_troppi_passaggi_tengono_la_risposta_e_la_modifica`).
5. **«Annulla» di una modifica che aveva creato un ingrediente già messo in lista** da una scheda applicata: l'ingrediente resta, la lista non perde la voce (Task 8, `test_annulla_non_toglie_un_ingrediente_in_lista`).

## Fuori scope

- Il passaggio dell'LLM dell'import (Gemma) a Claude Haiku: voce separata, con la sua spec. Qui si sceglie solo il nome dell'impostazione che condivideranno.
- Le correzioni S1–S3, P1–P4, U1–U2: piano `docs/superpowers/plans/2026-11-18-pasti-correzioni.md`, che parte da questo ramo.
- Cambiare il modello, lo sforzo, i tempi massimi o i prompt di sistema (nessun prompt cambia in questo piano).
- Un tetto di spesa nell'app: il limite di spesa si mette nella console di Anthropic (lo scrive il report, «Dopo il deploy»).
- Leggere il costo fatturato dalla console di Anthropic: il costo registrato è quello che Claude Code calcola dai token col suo listino.

## Margine di autonomia

- **Liberi:** nomi locali, helper dei test, funzioni private non fissate qui, la forma esatta dei messaggi di log.
- **Fissi:** le frasi fra «» di questo piano; i valori `rate_limit`, `credit`, `max_turns`; il nome `ANTHROPIC_API_KEY`/`anthropic_api_key`; il flag `no-session-persistence`; la colonna `created_ingredient_ids`; i nomi pubblici dei blocchi Interfaces.
- **La documentazione e il sorgente dell'SDK vincono sul piano per i nomi dell'SDK** (`ResultMessage.total_cost_usd`, `extra_args`, `subtype`). Se nella 0.2.180 un nome è diverso, usa quello che c'è e scrivilo nel report.
- **Una decisione di comportamento non coperta e non reversibile**: si ferma quel task, si committa il lavoro parziale, la voce del backlog passa a `bloccato` con «attende: …» e la domanda precisa, e si va al task dopo se non dipende da quello. Una scelta reversibile e a basso impatto: la più conservativa, annotata nel report.
- Un test che fallisce e non si risolve: niente test disattivati, niente asserzioni indebolite. `bloccato` con la diagnosi.

## Interfacce prodotte (per il piano `2026-11-18-pasti-correzioni.md` e per il passaggio a Haiku)

- `Settings.anthropic_api_key: str | None = None` (da `ANTHROPIC_API_KEY`); `claude_code_oauth_token` non c'è più.
- `ClaudeUsage(model, session_id, input_tokens, output_tokens, cost_usd: float | None = None)`; `ClaudeFailure(kind, resets_at=None, detail="", usage: ClaudeUsage | None = None, partial_text: str = "")`; `def llm_usage(usage: ClaudeUsage | None) -> LlmUsage` in `app.services.claude.client`.
- `FailureKind`: `NOT_CONFIGURED`, `RATE_LIMIT = "rate_limit"`, `CREDIT = "credit"`, `AUTH`, `MAX_TURNS = "max_turns"`, `TIMEOUT`, `UNAVAILABLE`, `INTERRUPTED`.
- `write_meal_recipe(session, meal, draft, *, conversation_id=None, turn_message_id=None, expected: MealSnapshot | None = None) -> RecipeChange`; `STALE_WRITE_MESSAGE`; `TurnContext.seen: MealSnapshot | None = None`.
- `resolve_lines(session, lines, *, created: list[uuid.UUID] | None = None)`; `RecipeChange.created_ingredient_ids: list[str]`.
- `async def undoable_change_ids(session: AsyncSession, changes: Sequence[RecipeChange]) -> set[uuid.UUID]` in `app.services.meal_recipes`.
- Migrazione `0023` (`revision = "0023"`, `down_revision = "0022"`).

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `backend/app/core/config.py`, `backend/app/services/claude/client.py`, `backend/app/cli/check_claude.py`, `backend/tests/conftest.py`, `backend/tests/test_settings_claude.py`, `backend/tests/services/test_claude_client.py`, `.env.example` | 1 | la chiave API |
| `backend/app/services/claude/client.py`, `backend/tests/test_claude_binary.py` | 2 | niente trascrizioni |
| `backend/app/domain/meal_chat.py`, `backend/app/services/claude/client.py`, `backend/app/services/recipe_jobs.py`, `backend/tests/claude_fakes.py`, `backend/tests/domain/test_meal_chat.py`, `backend/tests/services/test_claude_client.py` | 3 | avvisi, guasti, costo nel client |
| `backend/app/services/meal_chat.py`, `backend/app/services/recipe_jobs.py`, `backend/tests/services/test_meal_chat_turn.py`, `backend/tests/services/test_planning_turn.py`, `backend/tests/services/test_recipe_jobs.py` | 4 | uso e costo di ogni giro, troppi passaggi |
| `backend/app/domain/spending.py`, `backend/app/services/spending.py`, `backend/app/schemas/spending.py`, `backend/app/services/llm.py` (commento), `frontend/src/features/spending/*`, test | 5 | le spese senza il blocco «sul piano» |
| `backend/app/services/meal_recipes.py`, `backend/app/services/claude/tools.py`, `backend/app/services/meal_chat.py`, test | 6 | C1 |
| `backend/app/services/claude/tools.py`, test | 7 | C3 |
| `backend/alembic/versions/0023_modifiche_ingredienti.py` (nuovo), `backend/app/db/models/recipe_change.py`, `backend/app/services/recipe_writing.py`, `backend/app/services/meal_recipes.py`, test | 8 | C6 |
| `backend/app/services/meal_recipes.py`, `backend/app/services/meal_chat.py`, test | 9 | C7 |
| `frontend/src/features/meal-chat/ChatThread.tsx`, test del frontend con le frasi vecchie, `backend/tests/e2e_chat.py`, `backend/tests/e2e_planning.py`, `frontend/e2e/*.spec.ts` | 10 | la chat nel frontend e nel browser vero |
| `docs/superpowers/specs/2026-11-12-pasti-claude-design.md`, `CLAUDE.md`, `README.md`, `docs/superpowers/plans/2026-11-12-pasti-claude.md`, `docs/night-reports/2026-11-13.md`, `next-steps.md`, `docs/night-reports/<data>.md` | 11 | documenti e report |

---

### Task 1: La chiave API nelle impostazioni, nel client e in `check_claude`

**Files:**
- Modify: `backend/app/core/config.py` (il campo `claude_code_oauth_token` e il commento sopra `openrouter_api_key`), `backend/app/services/claude/client.py` (`claude_configured`, `build_options`), `backend/app/cli/check_claude.py`, `backend/tests/conftest.py` (il fixture automatico che già fa `get_settings.cache_clear()`), `.env.example` (il blocco di `CLAUDE_CODE_OAUTH_TOKEN`)
- Test: `backend/tests/test_settings_claude.py` (riscritto), `backend/tests/services/test_claude_client.py`

**Interfaces:**
- Produces: `Settings.anthropic_api_key: str | None = None`; `claude_configured() -> bool` = `bool(get_settings().anthropic_api_key)`; in `build_options`, `env` è **esattamente** `{"ANTHROPIC_API_KEY": <chiave o "">, "CLAUDE_CODE_OAUTH_TOKEN": "", "ANTHROPIC_AUTH_TOKEN": "", "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "ENABLE_TOOL_SEARCH": "false", "CLAUDE_CODE_SKIP_PROMPT_HISTORY": "1"}`.

- [ ] **Step 1: I test che falliscono.**
  - `test_settings_claude.py`, al posto dei test sul token: `test_la_chiave_si_legge_da_anthropic_api_key` (`monkeypatch.setenv("ANTHROPIC_API_KEY", CHIAVE_FINTA)`, `get_settings.cache_clear()`, il campo vale `CHIAVE_FINTA`); `test_senza_chiave_e_none`; `test_la_chiave_vuota_conta_come_assente` (`ANTHROPIC_API_KEY=""` → `claude_configured()` falso, e `check_claude.main([])` stampa `chiave API: assente`); `test_il_modello_di_default_e_opus` (resta); `test_check_claude_non_stampa_la_chiave` (con la chiave finta: `main([]) == 0`, l'uscita contiene `chiave API: presente` e `claude-agent-sdk`, e né `out` né `err` contengono la chiave); `test_check_claude_avvisa_del_token_senza_stamparlo` (con `CLAUDE_CODE_OAUTH_TOKEN` finto nell'ambiente: l'uscita contiene «attenzione: CLAUDE_CODE_OAUTH_TOKEN è nell'ambiente; la chat lo ignora e usa la chiave API.» e non il valore); `test_check_claude_senza_token_non_avvisa`. `CHIAVE_FINTA = "chiave-finta-per-i-test"`: **niente che somigli a una chiave vera** (il repo è pubblico; vedi l'idea sul commit `3df53ee`).
  - `test_la_suite_parte_senza_chiave` (in `test_settings_claude.py`): senza `setenv`, `get_settings().anthropic_api_key is None` e `claude_configured()` è falso, qualunque cosa abbia l'ambiente della shell.
  - `test_claude_client.py`: in `test_le_opzioni_di_produzione` il dizionario `env` atteso diventa quello delle Interfaces, con la chiave finta impostata come sopra. `test_una_chiave_api_nell_ambiente_non_prende_il_posto_del_token` si rovescia e si rinomina `test_un_token_nell_ambiente_non_prende_il_posto_della_chiave`: con `CLAUDE_CODE_OAUTH_TOKEN` e `ANTHROPIC_AUTH_TOKEN` nell'ambiente, `options.env` li ha tutti e due `""`, e `ANTHROPIC_API_KEY` vale la chiave delle impostazioni. `test_senza_token_non_parte_niente` e `test_con_il_token_e_configurato` diventano `…_senza_chiave_…` e `…_con_la_chiave_…`, con `ANTHROPIC_API_KEY`.
- [ ] **Step 2: Falliscono.** Il comando di pytest con i due file. Expected: FAIL.
- [ ] **Step 3: Il codice.**
  - `config.py`: `anthropic_api_key: str | None = None` al posto di `claude_code_oauth_token`, con il commento «La chiave API di Anthropic: oggi per i Pasti (chat, pianificazione, ricette dei pasti), domani anche per l'LLM dell'import con Claude Haiku. Vuota o assente: la chat dice che Claude non è collegato.». Nel commento sopra `openrouter_api_key`, la frase sul secondo percorso diventa: «C'è un secondo percorso, ed è per i Pasti: Claude via Agent SDK, con la chiave API di Anthropic. Non è il caso che la regola vieta, perché non è una scelta fra due client per lo stesso lavoro: ogni lavoro ha un solo percorso, che in produzione gira davvero (la chiave è obbligatoria per la chat, e `check_claude` prova il binario nello stack).».
  - `client.py`: `claude_configured` legge la chiave; il commento sopra le due variabili vuote di `env` dice: l'SDK passa al CLI `{**os.environ, **env}`, e un token del piano rimasto nell'ambiente prenderebbe il posto della chiave senza che niente lo mostri; vuoti, il CLI li legge come assenti.
  - `check_claude.py`: la docstring dice chiave API e non token; `chiave API: presente`/`chiave API: assente`; l'avviso del Step 1 sul token al posto di quello sulla chiave.
  - `conftest.py`: nel fixture automatico che già pulisce le impostazioni, `monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)` e `monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)` **prima** di `get_settings.cache_clear()`.
  - `.env.example`, al posto del blocco del token:
    ```
    # La chiave API di Anthropic, per i Pasti (la chat dei piatti, la pianificazione e le
    # ricette dei pasti); la userà anche l'LLM dell'import quando passerà a Claude Haiku.
    # Si crea nella console di Anthropic e si scrive SOLO nel `.env` del server: il
    # repository è pubblico. Si paga a consumo, sul credito API. Vuota, la chat dice che
    # Claude non è collegato e tutto il resto dei Pasti funziona a mano.
    # Controllo: `python -m app.cli.check_claude`.
    ANTHROPIC_API_KEY=
    # Il modello dei Pasti, con la chiave API (non su OpenRouter).
    CLAUDE_MODEL=claude-opus-5-5
    CLAUDE_REPLY_TIMEOUT_SECONDS=240
    ```
- [ ] **Step 4: Passano**, poi la suite intera. Expected: PASS. L'avviso «non collegato» dice ancora «token del piano» fino al Task 3: i test che lo fissano non cambiano qui.
- [ ] **Step 5: Commit** — `feat(pasti): la chat di Claude con la chiave API di Anthropic al posto del token del piano`.

---

### Task 2: Niente trascrizioni delle sessioni su disco (C2)

**Files:**
- Modify: `backend/app/services/claude/client.py` (`build_options`)
- Test: `backend/tests/test_claude_binary.py`, `backend/tests/services/test_claude_client.py` (`test_le_opzioni_di_produzione`)

**Interfaces:**
- Produces: `build_options(...)` con `extra_args={"no-session-persistence": None}`.

- [ ] **Step 1: I test che falliscono.**
  - In `test_le_opzioni_di_produzione`: `options.extra_args == {"no-session-persistence": None}`.
  - In `test_claude_binary.py`, `test_il_client_vero_non_lascia_trascrizioni(tmp_path, monkeypatch)`, che lancia il **binario incluso** attraverso il **client di produzione**:
    1. dall'ambiente si tolgono tutte le variabili che cominciano per `ANTHROPIC_` o `CLAUDE_CODE_` (`monkeypatch.delenv`), così il test fa lo stesso su ogni macchina;
    2. `HOME=tmp_path/"home"`, `CLAUDE_CONFIG_DIR=tmp_path/"home"/".claude"`, `ANTHROPIC_BASE_URL=http://127.0.0.1:9`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, `CLAUDE_CODE_MAX_RETRIES=0`, `API_TIMEOUT_MS=3000`, `ANTHROPIC_API_KEY=chiave-finta-per-i-test`, `CLAUDE_WORKDIR=str(tmp_path/"lavoro")`; `get_settings.cache_clear()`;
    3. `SdkClaudeClient().run(system_prompt="Rispondi solo: ok", prompt="ok?", tools=[], effort="low", max_turns=1)` letto fino in fondo: l'ultimo evento è un `TurnFailed` (la porta è chiusa);
    4. `list((tmp_path/"home"/".claude"/"projects").rglob("*.jsonl")) == []`.

    E il suo controllo, `test_senza_il_flag_il_binario_scriverebbe_la_trascrizione`, con lo stesso ambiente: `dataclasses.replace(build_options(...), extra_args={})` passato a `claude_agent_sdk.query` (prendendo l'eventuale `ResultError` come previsto), poi `rglob("*.jsonl")` trova **un** file. Senza questo, il primo test passerebbe anche su un binario che non scrive mai niente.
- [ ] **Step 2: Fallisce.** Il comando di pytest con i due file. Expected: FAIL sul primo dei due test nuovi (il JSONL c'è) e su `extra_args`.
- [ ] **Step 3: Il codice.** `extra_args={"no-session-persistence": None}` in `build_options`, con un commento: «Senza, il CLI scrive la trascrizione di ogni giro (prompt di sistema, dispensa, pasti, chiamate degli strumenti) sotto `~/.claude/projects/` nel container. `CLAUDE_CODE_SKIP_PROMPT_HISTORY` ferma solo la cronologia dei prompt. Verificato sul binario 2.1.321: `tests/test_claude_binary.py`.». La docstring del modulo, dove dice delle sessioni, aggiunge che non si scrivono nemmeno su disco.
- [ ] **Step 4: Passano.** Expected: PASS, in pochi secondi (il binario parte due volte). Se il primo test trova ancora un JSONL con il flag, fermati: la voce va a `bloccato` con «attende: --no-session-persistence non basta sul binario 2.1.321» e l'elenco dei file trovati.
- [ ] **Step 5: Commit** — `fix(pasti): il CLI di Claude non scrive le trascrizioni delle sessioni (--no-session-persistence), provato sul binario incluso`.

---

### Task 3: Gli avvisi, i guasti e il costo nel client

**Files:**
- Modify: `backend/app/domain/meal_chat.py` (`FailureKind`, `_limit_notice`, `failure_notice`), `backend/app/services/claude/client.py` (`ClaudeUsage`, `ClaudeFailure`, `_classify_status`, `translate`, `SdkClaudeClient.run`, `llm_usage` nuova), `backend/app/services/recipe_jobs.py` (`TERMINAL_FAILURES` e il commento che parla del «limite del piano»), `backend/tests/claude_fakes.py`
- Test: `backend/tests/domain/test_meal_chat.py`, `backend/tests/services/test_claude_client.py`

**Interfaces:**
- Produces: le firme di `ClaudeUsage`, `ClaudeFailure`, `llm_usage` e `FailureKind` del blocco «Interfacce prodotte». `llm_usage(None)` è `LlmUsage()`; altrimenti `LlmUsage(generation_id=u.session_id, model=u.model, prompt_tokens=u.input_tokens, completion_tokens=u.output_tokens, cost_usd=u.cost_usd)`. `TERMINAL_FAILURES = {RATE_LIMIT, CREDIT, AUTH, NOT_CONFIGURED}`.
- Produces, in `claude_fakes.py`: `Finish(input_tokens=100, output_tokens=20, cost_usd: float | None = 0.05)`; `Fail(kind, resets_at=None, input_tokens: int | None = None, output_tokens: int | None = None, cost_usd: float | None = None)`, che porta `usage` (se uno dei tre è valorizzato) e `partial_text` = i `Say` detti fin lì, uniti come fa `Finish`; `Do(action: Callable[[], Awaitable[None]])`, un passo che esegue `action` (serve al Task 6 e al Task 7).

- [ ] **Step 1: I test che falliscono.**
  - `test_meal_chat.py` (dominio), le frasi esatte, con `now` alle 10:00 di Roma:
    - `NOT_CONFIGURED` → «Claude non è collegato: manca la chiave API sul server.»
    - `RATE_LIMIT` senza ora → «Claude non risponde: hai raggiunto il limite di frequenza della chiave API, riprova tra qualche minuto.»; con l'ora oggi → «Claude non risponde: hai raggiunto il limite di frequenza della chiave API, riprova dopo le 18:40»; domani → «… riprova domani dopo le 9:05»; più in là → «… riprova dopo le 9:05 del 21 novembre» (la logica dei giorni di `_limit_notice` resta, cambia la base; il caso di mezzanotte a Roma resta com'è).
    - `CREDIT` → «Claude non risponde: il credito della chiave API è finito. Va ricaricato nella console di Anthropic.»
    - `AUTH` → «Claude non risponde: la chiave API non vale più (sbagliata o revocata). Va sostituita nel .env del server.»
    - `MAX_TURNS` → «Claude si è fermato prima di finire: questo messaggio gli chiedeva troppi passaggi. Scrivigli come andare avanti.»
    - `TIMEOUT`, `UNAVAILABLE`, `INTERRUPTED`: come oggi.
  - `test_claude_client.py`:
    - `test_la_fine_porta_il_costo`: un `ResultMessage(subtype="success", is_error=False, total_cost_usd=0.0421, usage={...})` → `TurnFinished` con `usage.cost_usd == 0.0421`.
    - `test_troppi_passaggi_tengono_il_testo`: un `AssistantMessage` con «Ecco la ricetta.», poi `ResultMessage(subtype="error_max_turns", is_error=True, total_cost_usd=0.31, usage={"input_tokens": 900, "output_tokens": 300})` → `TurnFailed` con `kind == MAX_TURNS`, `partial_text == "Ecco la ricetta."`, `usage.cost_usd == 0.31`, `usage.input_tokens == 900`.
    - `test_un_guasto_con_il_risultato_porta_l_uso`: un `ResultMessage` d'errore con `api_error_status=500`, `total_cost_usd=0.002` → `TurnFailed(UNAVAILABLE)` con `usage.cost_usd == 0.002`.
    - In `test_i_guasti` (parametrizzato): `error_max_turns` passa da `UNAVAILABLE` a `MAX_TURNS`; `rate_limit` e 429 → `RATE_LIMIT`; `billing_error` e 402 → `CREDIT`; `authentication_failed`, 401 e 403 → `AUTH`. `test_il_limite_del_piano_porta_l_ora` diventa `test_il_limite_di_frequenza_porta_l_ora`, con `RATE_LIMIT`.
    - `test_llm_usage`: `llm_usage(None) == LlmUsage()`, e un `ClaudeUsage` pieno passa i cinque campi.
- [ ] **Step 2: Falliscono.** Expected: FAIL.
- [ ] **Step 3: Il codice.**
  - `FailureKind` come nelle Interfaces; `PLAN_LIMIT` non c'è più (né nel codice né nei test: `grep` dei «Comandi di verifica»).
  - `translate`: sul `ResultMessage` legge `total_cost_usd` (un numero resta il numero, `None` resta `None`) e costruisce l'uso **anche per gli errori**. Un `ResultMessage` con `subtype == "error_max_turns"` marca `MAX_TURNS` (salvo un guasto già visto nello stesso giro, che vale per primo come oggi) e porta `partial_text = "\n\n".join(state.texts)`. Le altre classificazioni come nella decisione 9. In `SdkClaudeClient.run`, i `TurnFailed` costruiti nei rami `except` portano `state.failure` com'è (con l'uso, se il `ResultMessage` era arrivato).
  - `TERMINAL_FAILURES` come nelle Interfaces; il commento di `recipe_jobs.py` che dice «il limite del piano» dice «il limite di frequenza».
  - `claude_fakes.py` come nelle Interfaces.
- [ ] **Step 4: Passano.** Poi `grep -rn "PLAN_LIMIT\|plan_limit" backend` e correggi ogni uso rimasto nei test (`test_meal_chat_turn.py`, `test_planning_turn.py`, `test_recipe_jobs.py`, `tests/api/*`, `e2e_chat.py`, `e2e_planning.py`) con `RATE_LIMIT` e la frase nuova: è uno dei cambi permessi. La suite intera: verde salvo i test del costo NULL, che cambia il Task 4.
- [ ] **Step 5: Commit** — `feat(pasti): avvisi per chiave API, credito e limite di frequenza; troppi passaggi; il costo e l'uso dell'SDK anche sui giri falliti`.

---

### Task 4: L'uso e il costo di ogni giro, e i troppi passaggi (C4, C5)

**Files:**
- Modify: `backend/app/services/meal_chat.py` (`_fail`, il ramo di successo di `_turn`), `backend/app/services/recipe_jobs.py` (`_settle_meal`)
- Test: `backend/tests/services/test_meal_chat_turn.py`, `backend/tests/services/test_planning_turn.py`, `backend/tests/services/test_recipe_jobs.py`

**Interfaces:**
- Consumes: `llm_usage`, `ClaudeFailure.usage`, `ClaudeFailure.partial_text`, `FailureKind.MAX_TURNS` (Task 3).

- [ ] **Step 1: I test che falliscono.**
  - `test_meal_chat_turn.py`:
    - in `test_un_giro_che_risponde` l'asserzione `row.cost_usd is None` diventa `row.cost_usd == 0.05` (il default di `Finish`).
    - `test_un_giro_fallito_registra_l_uso`: `Fail(FailureKind.UNAVAILABLE, input_tokens=500, output_tokens=40, cost_usd=0.012)` → una riga `meal_chat`, `ok` falso, 500/40 token, `cost_usd == 0.012`; il messaggio è `failed` con l'avviso.
    - `test_un_tempo_massimo_non_ha_costo`: con `Hang()` la riga c'è, senza token e con `cost_usd` NULL.
    - `test_troppi_passaggi_tengono_la_risposta_e_la_modifica`: `[Say("Ho cambiato gli spinaci. "), UseTool("write_recipe", <spinaci 150 g>), Say("Poi"), Fail(FailureKind.MAX_TURNS, input_tokens=2000, output_tokens=600, cost_usd=0.4)]`. Dopo il giro: il messaggio di Mattia è `sent` e senza avviso; c'è una risposta di Claude `sent` con il testo «Ho cambiato gli spinaci. \n\nPoi» (come lo unisce `Finish`) e `notice` = l'avviso `MAX_TURNS`; la modifica sta sotto quella risposta ed è annullabile; l'evento finale è `done`; in `llm_calls` una riga con `ok` falso e il costo 0.4.
    - `test_il_limite_del_piano` diventa `test_il_limite_di_frequenza` (con `RATE_LIMIT` e la frase nuova).
  - `test_planning_turn.py`: `test_troppi_passaggi_nella_pianificazione`, lo stesso comportamento sul giro di pianificazione (stesso `run_chat_turn`: un test basta a dire che la specie non lo cambia).
  - `test_recipe_jobs.py`: `test_la_ricetta_scritta_registra_il_costo` (la riga `meal_recipe` ha `cost_usd == 0.05`); `test_un_giro_fallito_della_coda_registra_l_uso`; `test_troppi_passaggi_senza_ricetta_dicono_che_non_l_ha_scritta` (`recipe_notice == NOT_WRITTEN_NOTICE`); `test_il_credito_finito_ferma_la_coda` (tre pasti in coda, il primo `Fail(CREDIT)`: Claude è chiamato una volta sola, e tutti e tre hanno l'avviso del credito e `can_ask_recipe` vero).
- [ ] **Step 2: Falliscono.** Expected: FAIL.
- [ ] **Step 3: Il codice.**
  - In `_turn`, il successo e i troppi passaggi diventano una funzione sola, `_reply(session, lock, spec, *, message_id, conversation_id, text, usage, ok, notice, emit)`: il messaggio di Mattia `sent`, la risposta di Claude con `text` e `notice`, `record_llm_call(..., usage=llm_usage(usage), ok=ok)`, commit, evento `done`. Il successo la chiama con `outcome.text or "".join(deltas)`, `ok=True`, `notice=None`; `MAX_TURNS` con `failure.partial_text or "".join(deltas)`, `ok=False` e `failure_notice(MAX_TURNS, None, now)`. Gli altri guasti restano in `_fail`, che registra `llm_usage(failure.usage)` invece di `LlmUsage()`.
  - In `_settle_meal`: il successo registra `llm_usage(outcome.finished.usage)`, il guasto `llm_usage(outcome.failure.usage)`; `MAX_TURNS` senza ricetta prende `NOT_WRITTEN_NOTICE` invece di `failure_notice`. Un `MAX_TURNS` non è terminale per la coda.
  - Nessun `cost_usd=None` scritto a mano resta nei due file.
- [ ] **Step 4: Passano**, poi la suite intera. Expected: PASS (salvo le spese, Task 5).
- [ ] **Step 5: Commit** — `fix(pasti): ogni giro registra token e costo, anche fallito; i troppi passaggi tengono la risposta parziale con l'avviso`.

---

### Task 5: «Spese dell'AI» senza il blocco «sul piano»

**Files:**
- Modify: `backend/app/domain/spending.py` (via `PLAN_CALL_SITES`, `PLAN_NOTE`; la docstring del modulo), `backend/app/services/spending.py`, `backend/app/schemas/spending.py` (via `PlanSectionOut` e `plan_sections`; il commento di `total_usd`), `backend/app/services/llm.py` (i commenti su `MEAL_CHAT`/`MEAL_PLANNING`), `frontend/src/features/spending/SpendingScreen.tsx`, `frontend/src/features/spending/types.ts`
- Delete: `frontend/src/features/spending/PlanSections.tsx`, `frontend/src/features/spending/PlanSections.test.tsx`, `backend/tests/api/test_llm_spending_plan.py`
- Create: `backend/tests/api/test_llm_spending_meals.py`
- Test: `frontend/src/features/spending/SpendingScreen.test.tsx`

- [ ] **Step 1: I test che falliscono.**
  - `test_llm_spending_meals.py`: `test_i_pasti_contano_nel_totale` (oggi: una `meal_chat` da 0,30 $ e una `term_decision` da 0,10 $ → `total_usd == 0.4`, `calls == 2`, la sezione «Chat dei piatti» con `share == 0.75` in testa, il giorno di oggi a 0,4; nella risposta non c'è la chiave `plan_sections`); `test_un_giro_dei_pasti_senza_costo_sta_fra_quelli_senza_costo` (una `meal_planning` fallita senza costo → `unpriced_calls == 1`).
  - `SpendingScreen.test.tsx`: il test «senza chiamate a consumo ma con la chat sul piano…» si toglie; al suo posto «la chat dei piatti è una sezione come le altre»: una risposta con la sezione `meal_chat` da 0,30 $ mostra «Chat dei piatti» fra le barre, e nessun testo «Claude» da solo come titolo di blocco.
- [ ] **Step 2: Falliscono.** Expected: FAIL.
- [ ] **Step 3: Il codice.** `spending_report` usa tutte le sezioni; `SpendingOut` perde `plan_sections`; nel frontend `Report` perde `plan` e `PlanSections`, `types.ts` perde `PlanSection` e `plan_sections`. La docstring di `app/domain/spending.py` dice: «Le cifre sono quelle che dichiarano i fornitori, in dollari: OpenRouter (`usage.cost`) e Claude Code per i Pasti (`ResultMessage.total_cost_usd`, calcolato dai token col suo listino).». I commenti in `llm.py` dicono che i Pasti girano con la chiave API, a consumo, e che il costo lo registra il giro (o la coda), non questo client. `CALL_SITE_LABELS` non cambia.
- [ ] **Step 4: Passano**, backend e frontend; `npm run typecheck && npm run lint`. Expected: PASS, puliti.
- [ ] **Step 5: Commit** — `feat(spese): i Pasti contano nel totale come le altre sezioni; via il blocco «sul piano»`.

---

### Task 6: Una correzione a mano durante il giro non si perde (C1)

**Files:**
- Modify: `backend/app/services/meal_recipes.py` (`write_meal_recipe`, costante nuova), `backend/app/services/claude/tools.py` (`TurnContext`, `write_recipe_tool`, `read_meals`), `backend/app/services/meal_chat.py` (`_dish_prepare`)
- Test: `backend/tests/services/test_meal_recipes.py`, `backend/tests/services/test_meal_chat_turn.py`, `backend/tests/services/test_claude_tools.py`

**Interfaces:**
- Produces: `write_meal_recipe(..., expected: MealSnapshot | None = None)`: con `expected` valorizzato e `meal_snapshot` di adesso diverso, solleva `RecipeWriteRefused(STALE_WRITE_MESSAGE)` **prima di ogni scrittura**. `STALE_WRITE_MESSAGE = "La ricetta di questo pasto è cambiata mentre rispondevi (l'ha corretta Mattia, o ha annullato una modifica): rileggila con read_meals e riscrivila partendo da com'è adesso. Non ho scritto niente."`. `TurnContext.seen: MealSnapshot | None = None` (`None`: nessun controllo, come nei giri della coda delle ricette, che hanno già `create_only`).

- [ ] **Step 1: I test che falliscono.**
  - `test_meal_recipes.py`: `test_una_scrittura_su_una_ricetta_cambiata_si_rifiuta` (istantanea presa, poi la dose degli spinaci cambiata con `write_recipe_ingredients` come fa il modulo; `write_meal_recipe(..., expected=istantanea)` → `RecipeWriteRefused` con `STALE_WRITE_MESSAGE`, la dose resta quella della correzione, nessun `RecipeChange` nuovo); `test_con_l_istantanea_giusta_si_scrive`.
  - `test_meal_chat_turn.py`: `test_una_correzione_a_mano_durante_il_giro_non_si_perde`: `[Say("Guardo. "), Do(corregge_a_mano), UseTool("write_recipe", <spinaci 150 g>), Finish()]`, dove `corregge_a_mano` apre una sessione sua da `factory`, porta gli spinaci a «300 g» e committa. Dopo il giro gli spinaci dicono «300 g», `fake.tool_results[0]` è un errore con `STALE_WRITE_MESSAGE`, e non c'è nessuna modifica registrata.
  - `test_una_seconda_scrittura_nello_stesso_giro_passa`: due `write_recipe` di fila senza correzioni in mezzo → due modifiche (l'istantanea segue la scrittura di Claude).
  - `test_rileggere_il_pasto_aggiorna_l_istantanea`: correzione a mano, poi `UseTool("read_meals", {start, end})` che comprende il pasto, poi `write_recipe` → scritta.
- [ ] **Step 2: Falliscono.** Expected: FAIL.
- [ ] **Step 3: Il codice.** In `write_meal_recipe` il confronto sta subito dopo `before = await meal_snapshot(session, meal)`. In `_dish_prepare`, dopo aver letto il pasto e la ricetta per il prompt, `ctx.seen = await meal_snapshot(session, meal)` (stessa transazione: è il pasto che Claude vede). In `write_recipe`, `expected=ctx.seen`, e dopo una scrittura riuscita `ctx.seen = snapshot_from_json(change.after)`. In `read_meals`, se fra i pasti letti c'è `ctx.meal_id` e `ctx.seen` non è `None`, `ctx.seen = await meal_snapshot(ctx.session, quel pasto)`, sotto lo stesso `ctx.lock`.
- [ ] **Step 4: Passano**, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `fix(pasti): Claude non sovrascrive una ricetta corretta a mano durante la risposta`.

---

### Task 7: Le letture degli strumenti chiudono la transazione (C3)

**Files:**
- Modify: `backend/app/services/claude/tools.py` (`read_pantry`, `read_shopping_list`, `read_meals`, `search_ingredients`, e ogni altro strumento di sola lettura che il ramo abbia)
- Test: `backend/tests/services/test_meal_chat_turn.py`

- [ ] **Step 1: Il test che fallisce.** `test_le_letture_non_lasciano_la_transazione_aperta`, parametrizzato su `read_pantry {}`, `read_shopping_list {}`, `read_meals {start: oggi, end: oggi}`, `search_ingredients {"name": "uova"}`: `[UseTool(<strumento>, <argomenti>), Do(guarda), Finish()]`, con `guarda` che annota `sessions[0].in_transaction()` (la sessione del giro, presa con `spia(factory, sessions)` come in `test_il_giro_non_tiene_aperta_la_transazione_mentre_claude_pensa`). Expected: `[False]`.
- [ ] **Step 2: Fallisce.** Expected: FAIL, `[True]`.
- [ ] **Step 3: Il codice.** Un helper `async def _end_read(ctx: TurnContext) -> None` che fa `await ctx.session.commit()`, chiamato dentro `async with ctx.lock:` subito dopo la lettura, in ogni strumento di sola lettura. Commento: un `commit` e non un `rollback`, perché il rollback scade gli oggetti caricati e il commit no (`expire_on_commit=False`); non c'è mai niente in sospeso, perché le scritture si committano da sé.
- [ ] **Step 4: Passa**, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `fix(pasti): le letture di Claude non lasciano la connessione «idle in transaction» per tutto il giro`.

---

### Task 8: «Annulla» toglie gli ingredienti creati da quella modifica (C6)

**Files:**
- Create: `backend/alembic/versions/0023_modifiche_ingredienti.py`, `backend/tests/db/test_migration_0023.py`
- Modify: `backend/app/db/models/recipe_change.py`, `backend/app/services/recipe_writing.py` (`resolve_lines`), `backend/app/services/meal_recipes.py` (`write_meal_recipe`, `undo_recipe_change`)
- Test: `backend/tests/services/test_meal_recipes.py`

**Interfaces:**
- Produces: colonna `recipe_changes.created_ingredient_ids JSONB NOT NULL DEFAULT '[]'::jsonb` (gli id come stringhe, come `meal_ids` delle schede); `RecipeChange.created_ingredient_ids: Mapped[list[str]]`; `resolve_lines(session, lines, *, created: list[uuid.UUID] | None = None)`, che appende a `created` l'id di ogni ingrediente che crea (non di quelli che aggancia); nessun altro comportamento cambia.

- [ ] **Step 1: I test che falliscono.**
  - `test_migration_0023.py`, sul modello di `test_migration_0021.py`: `test_la_0023_sale_e_scende` (dopo `upgrade head` la colonna c'è e una riga di `recipe_changes` scritta con la `0022` vale `[]`; `downgrade 0022` la toglie).
  - `test_meal_recipes.py`:
    - `test_la_modifica_ricorda_gli_ingredienti_che_crea`: una riga con nome nuovo «Spinaci novelli» e reparto `verdura`, e una con un nome che `ingredient_for_new_name` aggancia → `created_ingredient_ids` ha solo l'id degli spinaci novelli.
    - `test_annulla_toglie_l_ingrediente_creato`: dopo `undo_recipe_change` l'ingrediente non c'è più e la ricetta è com'era.
    - `test_annulla_non_toglie_un_ingrediente_usato_altrove`, parametrizzato: un'altra ricetta lo usa; c'è in dispensa; `test_annulla_non_toglie_un_ingrediente_in_lista` (una voce di lista attiva lo porta). In tutti i casi l'annullamento riesce e l'ingrediente resta.
    - `test_annullare_una_ricetta_scritta_lascia_gli_ingredienti_alla_ricetta_archiviata`: una modifica `created_recipe` con un ingrediente nuovo; dopo «Annulla» la ricetta è archiviata e l'ingrediente c'è ancora (decisione 11).
    - I test di oggi del modulo delle ricette restano verdi senza cambiare (`resolve_lines` senza `created` fa quel che faceva).
- [ ] **Step 2: Falliscono.** Expected: FAIL.
- [ ] **Step 3: Migrazione e codice.** La migrazione aggiunge la colonna con `server_default`. `write_meal_recipe` passa un elenco a `resolve_lines` e lo salva (come stringhe) nel `RecipeChange`. In `undo_recipe_change`, dentro il SAVEPOINT, dopo `flush` della versione di prima, `delete_ingredient_if_unused(session, uuid.UUID(i))` per ogni id. La docstring di `RecipeChange` dice che cos'è la colonna e perché le modifiche di prima della `0023` non tolgono niente.
- [ ] **Step 4: Passano**, con `tests/db/test_metadata_matches_migrations.py`, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(pasti): «Annulla» toglie l'ingrediente creato da quella modifica se nient'altro lo usa (0023)`.

---

### Task 9: La vista della chat legge il pasto una volta sola (C7)

**Files:**
- Modify: `backend/app/services/meal_recipes.py` (`undoable_change_ids` nuova, `change_is_undoable`), `backend/app/services/meal_chat.py` (`chat_messages_out`, `change_out`, `dish_chat_view`)
- Test: `backend/tests/services/test_meal_chat_turn.py`, `backend/tests/services/test_meal_recipes.py`

**Interfaces:**
- Produces: `undoable_change_ids(session, changes) -> set[uuid.UUID]`: per ogni pasto distinto fra le modifiche non annullate, **una** lettura (`get_meal`, la ricetta, `meal_snapshot`); una modifica è annullabile se non è annullata, il pasto punta ancora a `change.recipe_id`, la ricetta non è archiviata e l'istantanea è uguale a `change.after`. `change_is_undoable(session, change)` diventa `change.id in await undoable_change_ids(session, [change])`. `chat_messages_out` calcola l'insieme una volta e lo usa per ogni `RecipeChangeOut`; `dish_chat_view` lo riusa per l'evidenza invece di richiamare `change_is_undoable` per ogni modifica del giro.

- [ ] **Step 1: I test che falliscono.**
  - `test_undoable_change_ids`: tre modifiche dello stesso pasto, l'ultima viva → solo l'ultima; con l'ultima annullata → la penultima (se la ricetta è tornata com'era lei la ha lasciata); con la ricetta archiviata → nessuna.
  - `test_la_vista_della_chat_non_rilegge_il_pasto_per_ogni_modifica`: con un ascoltatore `before_cursor_execute` sul motore sincrono della sessione dei test che conta le istruzioni, `dish_chat_view` di un pasto con **una** modifica e quella dello stesso pasto con **otto** modifiche (otto giri) contano lo stesso numero di istruzioni.
  - I test di oggi su «Annulla» e sull'evidenza restano verdi senza cambiare.
- [ ] **Step 2: Falliscono.** Expected: FAIL (il conteggio cresce con le modifiche).
- [ ] **Step 3: Il codice**, come nelle Interfaces.
- [ ] **Step 4: Passano**, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `perf(pasti): la vista della chat calcola le modifiche annullabili con una lettura per pasto`.

---

### Task 10: La chat nel frontend e nel browser vero

**Files:**
- Modify: `frontend/src/features/meal-chat/ChatThread.tsx`, `frontend/src/features/meal-chat/ChatThread.test.tsx`, `frontend/src/features/meal-chat/DishChat.test.tsx`, `frontend/src/features/meals/MealScreen.test.tsx`, `frontend/src/features/planning/PlanningScreen.test.tsx`, `backend/tests/e2e_chat.py`, `backend/tests/e2e_planning.py`, `frontend/e2e/chat-piatto.spec.ts`, `frontend/e2e/pianificazione.spec.ts`, `frontend/e2e/style.spec.ts`

- [ ] **Step 1: Il test che fallisce.** In `ChatThread.test.tsx`, «una risposta interrotta dai troppi passaggi mostra il testo e l'avviso, senza Riprova»: un messaggio di Claude `sent` con `text` «Ho cambiato gli spinaci.» e `notice` = la frase `MAX_TURNS` → si leggono i due testi e non c'è nessun «Riprova»; e «una risposta vuota con l'avviso mostra solo l'avviso» (nessun fumetto vuoto).
- [ ] **Step 2: Fallisce.** `npx vitest run src/features/meal-chat`. Expected: FAIL.
- [ ] **Step 3: Il codice.** In `ChatThread`, il fumetto si disegna solo se `message.text !== ""`; sotto un messaggio `sent` con `notice`, l'`Alert tone="degraded"` con l'avviso, allineato come il fumetto, senza pulsanti. Poi le frasi vecchie nei test del frontend, nei semi e nelle prove e2e diventano quelle del Task 3 («manca la chiave API sul server», «limite di frequenza della chiave API», `rate_limit` al posto di `plan_limit`); le espressioni regolari delle prove (`/^Claude non risponde: hai raggiunto il limite del piano…/`) diventano `/^Claude non risponde: hai raggiunto il limite di frequenza della chiave API/`. I semi `e2e_chat.py` ed `e2e_planning.py` scrivono l'avviso con `FailureKind.RATE_LIMIT`.
- [ ] **Step 4: Frontend verde.** `npx vitest run`, `npm run typecheck`, `npm run lint`. Expected: verdi, puliti.
- [ ] **Step 5: L'e2e intera** su uno stack ricreato da zero, con i comandi delle Global Constraints. **Prima di Playwright**, dentro lo stack:
  ```bash
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.check_claude
  ```
  Expected: `claude-agent-sdk 0.2.180`, il binario che stampa `2.1.321 (Claude Code)`, `chiave API: assente`. Poi Playwright: tutto verde, `N_e2e` uguale a quello di prima (nessuna prova nuova, alcune cambiate). Un testo illeggibile si corregge con un altro token esistente, mai con uno nuovo. `down -v` e `rm .env`, sempre.
- [ ] **Step 6: Commit** — `pasti: la risposta interrotta dai troppi passaggi a video; gli avvisi della chiave API nelle prove e nel browser vero`.

---

### Task 11: I documenti, la verifica finale e il report

**Files:**
- Modify: `docs/superpowers/specs/2026-11-12-pasti-claude-design.md`, `CLAUDE.md`, `README.md`, `docs/superpowers/plans/2026-11-12-pasti-claude.md`, `docs/night-reports/2026-11-13.md`, `next-steps.md`
- Create o modify: `docs/night-reports/<data di oggi>.md`

- [ ] **Step 1: La spec.** Sotto il titolo, una riga: «_2026-11-18: la chat passa alla chiave API (deciso da Mattia); §3 e §9 aggiornati, vedi `docs/superpowers/plans/2026-11-18-pasti-chiave-api.md`._». Il primo punto di §3 si riscrive così:
  ```
  - **Il modello è Claude Opus (`claude-opus-5-5`) con la chiave API di Mattia, sui suoi
    crediti API** (deciso da Mattia il 2026-11-18; fino ad allora la spec diceva
    l'abbonamento, che i termini dell'Agent SDK riservano all'uso individuale di Claude
    Code). Conseguenze:
    - la strada tecnica resta il **Claude Agent SDK** per Python (`claude-agent-sdk`),
      autenticato con `ANTHROPIC_API_KEY` nel `.env` del server, mai nel repo, che è
      pubblico. È la stessa chiave che userà l'LLM dell'import quando passerà a Claude
      Haiku. Il token dell'abbonamento non si usa: l'SDK riceve `CLAUDE_CODE_OAUTH_TOKEN`
      e `ANTHROPIC_AUTH_TOKEN` vuoti;
    - le chat si pagano a consumo. Quando il credito finisce o si supera il limite di
      frequenza, la chat lo dice e la strada a mano resta (§9);
    - in `llm_calls` ogni giro ha la sua sezione, i token e il costo che Claude Code
      dichiara (`ResultMessage.total_cost_usd`), e «Spese dell'AI» lo conta come le
      altre sezioni.
  ```
  In §2 (anti-obiettivi), «limite del piano raggiunto, token scaduto, rete» diventa «credito finito, limite di frequenza, chiave che non vale più, rete»; in §5.2 «limite del piano, errore» diventa «credito, limite di frequenza, errore»; in §9 la prima riga diventa «La chiave manca o non vale più, il credito è finito, il limite di frequenza è raggiunto, la rete cade, …», l'esempio dell'avviso diventa «Claude non risponde: hai raggiunto il limite di frequenza della chiave API, riprova dopo le 18:40», e l'ultimo paragrafo («La sezione nelle spese dell'AI (H1) mostra le chiamate e i token senza costo…») diventa «La sezione nelle spese dell'AI (H1) conta le chiamate dei Pasti con il loro costo, come le altre.».
- [ ] **Step 2: `CLAUDE.md`.** Il paragrafo «**A second path to a model, on purpose: Claude for the meals.**» si riscrive così:
  ```
  **A second path to a model, on purpose: Claude for the meals.** The meal chat, the
  planning and the meals' recipes run on Claude Opus (`claude-opus-5-5`) through the
  Claude Agent SDK for Python (`claude-agent-sdk`, pinned, with its bundled Claude Code
  binary), authenticated with Mattia's Anthropic API key, `ANTHROPIC_API_KEY`, kept only
  in the server's `.env` (decided by Mattia on 2026-11-18; the same key will serve the
  import's LLM when it moves to Claude Haiku). The SDK gets `CLAUDE_CODE_OAUTH_TOKEN` and
  `ANTHROPIC_AUTH_TOKEN` empty, so a subscription token left in the environment can never
  take over. This is not what the one-provider rule above forbids: that rule is against
  two implementations behind a switch, one of which never runs. Here there are two paths
  with two jobs, and both run in production — Gemma via OpenRouter for import, drafts and
  variants; Claude via the Agent SDK for the meals. The SDK is driven with every built-in
  tool off (`tools=[]`), no settings or `CLAUDE.md` loaded (`setting_sources=[]`),
  `permission_mode="dontAsk"`, no session transcripts on disk
  (`--no-session-persistence`, proven on the bundled binary by
  `tests/test_claude_binary.py`), and spena's own tools as an in-process MCP server
  (`backend/app/services/claude/`). Its calls go into `llm_calls` as `meal_chat`,
  `meal_planning` and `meal_recipe` with their tokens and the cost Claude Code reports
  (`ResultMessage.total_cost_usd`, an estimate from its price list), failed turns
  included, and «Spese dell'AI» counts them like any other section. Claude writes a
  meal's recipe only through `write_meal_recipe` (`backend/app/services/meal_recipes.py`),
  which goes through the `write_recipe_ingredients` funnel, inside a savepoint, refuses
  when the meal changed since Claude saw it, and stores the version before for «Annulla».
  Tests never run the SDK against the network: `get_claude_client` is injected, the fake
  calls the very tool objects production builds, and the production client is tested
  against the SDK's real message types. Spec:
  `docs/superpowers/specs/2026-11-12-pasti-claude-design.md` §3, §6, §7, §9.
  ```
- [ ] **Step 3: `README.md`.** Nella tabella delle variabili, la riga di `CLAUDE_CODE_OAUTH_TOKEN` diventa: «| `ANTHROPIC_API_KEY` | vuoto | la chiave API di Anthropic: oggi la chat, la pianificazione e le ricette dei Pasti, a consumo sul credito API; domani anche l'LLM dell'import con Claude Haiku. **Solo nel `.env` del server**. Vuota, la chat dice che Claude non è collegato e il resto dei Pasti funziona a mano |»; la riga di `CLAUDE_MODEL` dice «il modello dei Pasti, con la chiave API (non su OpenRouter)». Il paragrafo «**Claude per i Pasti** si controlla…» si riscrive: stampa `chiave API: presente` o `chiave API: assente` (mai il valore), avvisa se nell'ambiente c'è `CLAUDE_CODE_OAUTH_TOKEN` (la chat lo spegne), `--prova` fa una chiamata minima che costa qualche centesimo e deve dire «prova: ok»; le trascrizioni delle sessioni non si scrivono (`--no-session-persistence`).
- [ ] **Step 4: Il piano e il report del 2026-11-12/13.** In `docs/superpowers/plans/2026-11-12-pasti-claude.md`, subito sotto l'avvertenza in testa: «> **Superata il 2026-11-18.** Mattia ha scelto la chiave API: `docs/superpowers/plans/2026-11-18-pasti-chiave-api.md`. Anche la decisione 9 qui sotto era sbagliata su un punto: `CLAUDE_CODE_SKIP_PROMPT_HISTORY` non ferma le trascrizioni delle sessioni; le ferma `--no-session-persistence`.»; nella decisione 9, dopo «Le trascrizioni dell'SDK non si scrivono (`CLAUDE_CODE_SKIP_PROMPT_HISTORY=1`).», aggiungi «(Corretto il 2026-11-18: quella variabile ferma solo la cronologia dei prompt; le trascrizioni le ferma `--no-session-persistence`.)». In `docs/night-reports/2026-11-13.md`, in fondo alla sezione 6b, una nota: «_Correzione del 2026-11-18: le trascrizioni delle sessioni si scrivevano lo stesso sotto `~/.claude/projects/`; `CLAUDE_CODE_SKIP_PROMPT_HISTORY` ferma solo la cronologia dei prompt. Corretto su `night/pasti-chiave-api` con `--no-session-persistence`._»
- [ ] **Step 5: `next-steps.md`.**
  1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte: la chiave API e le correzioni della chat dei Pasti)_`.
  2. La voce di questo piano diventa `fatto <data di oggi>` con ` → branch night/pasti-chiave-api (da revisionare)`, e va in cima a «Fatti (recenti)».
  3. In «Da fare a mano (solo Mattia)», la voce «Prima del deploy dei Pasti con Claude: confermare l'uso del token del piano con l'Agent SDK …» diventa `fatto` con «superata il <data di oggi>: Mattia ha scelto la chiave API», e al suo posto: «[tbd] P2 · Prima del deploy dei Pasti con Claude: una chiave API nuova nella console di Anthropic, nel `.env` del server come `ANTHROPIC_API_KEY` (al posto di quella vecchia, mai usata dal codice), un limite di spesa nella console, poi `check_claude --prova` e il giro completo sul telefono (vedi «Dopo il deploy» in `docs/superpowers/plans/2026-11-18-pasti-chiave-api.md`) [Parte IV]». Nella voce «Sul server: restringere `Bash(ssh hetznerserver:*)` …», il pezzo «togliere `ANTHROPIC_API_KEY` dal `.env`» diventa «sostituire `ANTHROPIC_API_KEY` nel `.env` con la chiave nuova dei Pasti».
  4. Quel che è emerso fuori da questo piano va come `idea` o `tbd`, con `[Parte IV]`.
- [ ] **Step 6: La verifica finale.** I «Comandi di verifica» con i loro attesi; vitest circa **`N_vitest`** (−2 test di `PlanSections`, −1 file, +3 test circa), pytest circa **`N_pytest` + 40**. Se i numeri differiscono, scrivi nel report da dove viene la differenza. L'e2e del Task 10 vale se dopo non è cambiato codice; se è cambiato, rifalla. Infine `docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_pasti_chiave_api WITH (FORCE)'`.
- [ ] **Step 7: Il report**, `docs/night-reports/<data di oggi>.md` sul ramo (in fondo, se c'è già). Dentro: il ramo e `BASE`; i conti veri contro la Preparazione; l'output di `check_claude` nello stack; le interfacce prodotte come sono finite nel codice (una firma diversa dal piano va scritta per prima: il piano `2026-11-18-pasti-correzioni.md` parte da qui); i nomi dell'SDK diversi dal piano; le decisioni 5–13 che Mattia può voler rivedere, in particolare i troppi passaggi senza «Riprova», l'istantanea che si aggiorna anche con `read_meals`, e gli ingredienti che restano dopo l'annullamento di una «Ricetta scritta»; la sezione «Dopo il deploy (solo Mattia)» qui sotto. Niente push, niente merge, niente deploy.
  ```bash
  git add CLAUDE.md README.md docs/ next-steps.md
  git commit -m "docs: la chiave API dei Pasti nella spec, in CLAUDE.md e nel README; la correzione delle trascrizioni; il report"
  ```

---

## Dopo il deploy (solo Mattia)

La notte non tocca la produzione. Questo ramo si unisce su `master` prima di `night/pasti-correzioni`; la catena dei Pasti va in produzione per la prima volta con questi due rami (o con questo solo, se l'altro aspetta).

1. **La chiave.** Nella console di Anthropic si crea una chiave nuova per spena e, nella stessa console, un limite di spesa mensile. Nel `.env` **del server** si scrive `ANTHROPIC_API_KEY=<chiave nuova>`, **al posto** della `ANTHROPIC_API_KEY` vecchia che c'è già (il codice non l'ha mai usata; da questo deploy la legge). La chiave vecchia si revoca nella console. Niente `claude setup-token`, niente `CLAUDE_CODE_OAUTH_TOKEN`.
2. **Il deploy di sempre, con il `-f`**: `docker compose -f docker-compose.prod.yml up -d --build --wait --wait-timeout 120`. La `0021`, la `0022` e la `0023` girano all'avvio. L'immagine del backend cresce di circa 340 MB per il binario di Claude Code.
3. **Il controllo**: `docker compose -f docker-compose.prod.yml exec backend python -m app.cli.check_claude --prova`. Expected: il binario con la sua versione, `chiave API: presente`, nessun avviso sul token, `prova: ok` (costa qualche centesimo). Se dice credito, chiave o limite di frequenza, l'avviso dice cosa fare.
4. **Sul telefono, il giro completo.** Il caso della spec §1: una cena «Frittata di spinaci e parmigiano» scritta a mano, «Scrivi la ricetta» in chat, poi la domanda sugli spinaci congelati; la risposta arriva un po' alla volta, la ricetta cambia con le righe evidenziate e «Annulla» la rimette. Poi la pianificazione nei due giri (bozza → scheda della lista → spesa → «Sistema la spesa» → ufficializzazione con Claude → ricette arrivate → scheda della dispensa applicata), togliere un pasto e applicare la scheda inversa. Poi decidere se ritirare o ridurre la skill `pasti`.
5. **Le spese dell'AI**: «Chat dei piatti», «Pianificazione dei pasti» e «Ricette dei pasti» compaiono fra le sezioni, con il loro costo nel totale. Il costo è la stima di Claude Code: confrontalo una volta con la console di Anthropic.
6. **Senza Claude**: togliendo per un momento la chiave dal `.env` (e riavviando il backend), la chat dice «Claude non è collegato: manca la chiave API sul server.», mentre la ricetta, «Modifica» e la settimana funzionano.
