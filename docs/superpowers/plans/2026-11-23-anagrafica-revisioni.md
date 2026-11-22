# L'Anagrafica da rivedere: la fusione che eredita, i sostituti dell'AI in un elenco, «Chiedi all'AI», le scelte CIQUAL da controllare — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** tre cose che oggi in Anagrafica si perdono o si rivedono solo una scheda per volta.
- **La fusione** fa ereditare al vincitore la figura, l'alimento CIQUAL e i pesi per unità del perdente, dove il vincitore non ha niente.
- **I sostituti decisi dall'AI** si rivedono da un elenco solo, e una voce senza risposta si chiede all'AI dalla scheda.
- **Una scelta CIQUAL dell'AI** che non sta col reparto dell'ingrediente si legge «Da controllare», nella scheda e nello stesso elenco.

**Architecture:**
- **La fusione.** `merge_ingredients` fotografa all'inizio le tre scelte del perdente, prima che l'annullamento dei termini possa cancellarlo. Alla fine le scrive sul vincitore, ciascuna dal servizio che ne è l'unico scrittore:
  - la figura con `set_ingredient_emoji` (o la sua parte di scrittura);
  - l'alimento con `inherit_choice` in `ingredient_nutrition.py`;
  - i pesi con `inherit_grams` in `unit_grams.py`.

  `MergeCounts` dice cosa ha ereditato, e l'anteprima lo dice prima.
- **La revisione.** Una rotta nuova, `backend/app/api/review.py` sotto `/api/v1/review`, con tre letture:
  - `counts`, per i due link in cima all'Anagrafica;
  - `substitutes`, le voci generali decise dall'AI, dalla più usata, 50 per volta;
  - `foods`, le scelte CIQUAL dell'AI da controllare.

  Una pagina nuova, `/anagrafica/sostituti`, mostra i due elenchi con le schede che la scheda dell'ingrediente usa già (`ContextCard`).
- **«Chiedi all'AI».** `POST /api/v1/ingredients/{id}/substitutes/{context}/ask` chiama `decide_pair`, come «Sostituisci» in una ricetta, e risponde come la lettura della scheda, più `ai_failed` e `ai_notice`.
- **Il controllo CIQUAL.** È una funzione pura nel dominio, `food_fits_category(category, group_fr) -> bool | None`, con una tabella dei sottogruppi CIQUAL per reparto. Si calcola alla lettura, senza migrazione, quindi vale anche per le scelte che ci sono già.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, pytest su Postgres vero; React 19, TanStack Query 5, Vitest + Testing Library, Playwright.

**Spec:**
- `docs/superpowers/specs/2026-09-27-anagrafica-design.md` (§5.1, la fusione);
- `docs/superpowers/specs/2026-10-13-r5-sostituti-design.md` (la sezione «Sostituti»);
- `docs/superpowers/specs/2026-10-13-s4-nutrienti-ingrediente-design.md` (§4.14 la correzione, §4.15 la fusione, che questo piano cambia).

Le voci sono le tre idee P3 di `next-steps.md`:
- «Una fusione in Anagrafica perde ciò che aveva solo il perdente» [S12, S4];
- «I sostituti in Anagrafica» [R5];
- «S4: la scelta CIQUAL dell'AI sbaglia di più dove il nome italiano è un preparato…» [S4].

**Decisioni di Mattia del 2026-11-23**: le trovi sotto, in «Decisioni prese».

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/anagrafica-revisioni`, ramo `night/anagrafica-revisioni`, creato da `master`. Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì. **Nessun push, nessun merge, nessun deploy. Mai `git stash`. Niente letture o scritture sulla produzione, e mai il `.env` del checkout principale. Nessuna chiamata vera all'AI**: «Chiedi all'AI» si prova col client finto di `tests/llm_fakes.py`, come `decide_pair` oggi.
- **Da cucire con `2026-11-22-tempi-ai.md`** (stessa notte, ramo `night/tempi-ai`):
  - quel piano cambia `decide_pair` (il profilo `SYNC_PROFILE`) e aggiunge in `frontend/nginx.conf` una location a 300 s per `^/api/v1/(imports/terms/decide|recipes/[^/]+/substitutes/[^/]+/ask)$`;
  - la rotta nuova di questo piano, `/api/v1/ingredients/[^/]+/substitutes/[^/]+/ask`, va **nella stessa regex**, e il suo test (`backend/tests/test_nginx_ai_sync.py`) deve provarla.
  - Se quando cominci `night/tempi-ai` è già su `master`, aggiungila tu, col test. Altrimenti **non toccare `nginx.conf`**, e scrivi nel report il punto da cucire: la regex, il test e il fatto che `decide_pair` porta il profilo da sé.
- **Da cucire con `2026-11-22-suggerimenti-anagrafica.md`**: tocca anche lui `frontend/src/features/registry/RegistryScreen.tsx` (la query degli ingredienti). Questo piano ci aggiunge solo i link in cima. Rami separati; scrivilo nel report.
- **Da cucire con `2026-11-23-s4-rifiniture.md`** (ramo `night/s4-rifiniture`). Quel piano scrive di non avere cuciture, ma tocca `backend/app/services/unit_grams.py` (`realign_weights`) e `backend/tests/services/test_unit_grams.py`, come il Task 1 di questo (`inherit_grams`). Le funzioni sono diverse, ma è lo stesso file. Le righe dei pesi stanno sull'unità canonica: `inherit_grams` copia `unit_id` com'è, e un peso del perdente rimasto su un'unità non canonica lo rimette a posto `realign_weights`. Scrivilo nel report.
- **Da cucire con `2026-11-23-pasti-quarto-giro.md`**: cambia `delete_ingredient_if_unused` (`backend/app/repositories/ingredients.py`), che la fusione chiama. Questo piano non la tocca. Se il merge cambia cosa conta come «usato», i test della fusione del Task 1 sono quelli da rilanciare.
- **L'unico scrittore resta uno**:
  - i pesi li scrive solo `app/services/unit_grams.py`;
  - la scelta CIQUAL solo `app/services/ingredient_nutrition.py`;
  - la figura passa da `canonical_emoji`.

  La fusione chiama loro, non scrive le tabelle da sé.
- **Il frontend non decide** se una scelta CIQUAL è da controllare, né l'ordine delle voci: lo dice il server.
- **Mai un vicolo cieco**: «Chiedi all'AI» che non riesce lascia «Scrivi tu» in vista, con la frase del guasto; un elenco che non si legge ha «Riprova».
- **Colore e primitive**: solo token di `frontend/src/index.css`, **nessun token nuovo**. `grep -rn "emerald\|neutral-" frontend/src` resta come oggi. Ogni testo sta sopra 4,5:1 nei due temi: la pagina nuova va aggiunta alle rotte di `frontend/e2e/style.spec.ts`.
- Le parole a video **si copiano esatte** da questo piano (fra «»). Gli identificatori in inglese, i commenti in italiano.
- **Il type check è `npm run typecheck`**, mai `tsc --noEmit`. Controlli del frontend, da `<worktree>/frontend`: `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- **Il carico sulla macchina**: al massimo 6 thread e 8 GB (Mattia, 2026-11-22). Le suite intere girano dentro `systemd-run --user --scope -p MemoryMax=8G -p CPUQuota=600% …`, mai due insieme. Vitest gira con `--maxWorkers=4`, pytest senza parallelismo.
- **Backend su Postgres vero**: `spena-db-1` (porta 5433), con il database `spena_test_anagrafica_revisioni`. Mai `docker compose up` dal worktree. Si usa il `.venv` del checkout principale. Il comando di pytest, da `<worktree>/backend`:
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_anagrafica_revisioni \
    PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
- **e2e** sullo stack `spena-e2e`, con i comandi delle Global Constraints di `docs/superpowers/plans/2026-11-18-pasti-correzioni.md`:
  - il `.env` si copia da `.env.example` e si cancella alla fine;
  - in ogni comando `-p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml`;
  - il seme con le ricette e le due righe della fixture CIQUAL;
  - alla fine sempre `down -v` e `rm .env`;
  - se lo stack c'è e non l'hai alzato tu, aspetta che sparisca.
- Nessuna dipendenza nuova, **nessuna migrazione**.
- **I test di oggi si cambiano solo dove il piano lo dice**: le docstring dei due test della fusione che citano «deciso il 2026-10-13» (Task 1). Le loro asserzioni restano vere: in entrambi il vincitore ha già una scelta sua.

## Review Focus

1. **La fusione eredita solo dove il vincitore non ha niente, o ha un «nessuno» deciso dall'AI.** Un «nessuno» deciso da una persona resta, e una scelta vera del vincitore resta sempre. Per la figura, che non sa chi l'ha decisa, il perdente passa quando il vincitore ha `NULL` o `""`. Task 1, una tabella su ogni combinazione.
2. **Il perdente cancellato a metà fusione** (l'annullamento del suo ultimo termine lo cancella in CASCADE, insieme alle sue righe) **lascia comunque l'eredità**, perché le scelte sono state fotografate all'inizio. L'anteprima dice gli stessi numeri dell'esito. Task 1.
3. **L'elenco dei sostituti da rivedere ha solo voci generali dell'AI che rispondono**, dalla più usata. Dopo «Va bene così» la voce esce dall'elenco e il conto cala. Task 4.
4. **«Chiedi all'AI» non chiama nessuno** se intanto la voce ha già una risposta, e senza chiave dice il perché senza registrare una spesa: è la regola di `decide_pair`, che la rotta non riscrive. Task 3.
5. **«Da controllare» compare solo per una scelta dell'AI su un reparto controllato.** Una scelta fatta a mano, un reparto senza controllo («altro», «condimenti», «spezie», «dolci») e un alimento senza gruppo non la mostrano mai. Ogni sottogruppo della tabella esiste nel file CIQUAL vero. Task 5.

### Preparazione (una volta, prima del Task 1)

- [ ] Il worktree, con `node_modules` collegato e nessun `.env`:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/anagrafica-revisioni -b night/anagrafica-revisioni master
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/anagrafica-revisioni/frontend/node_modules
  ```
- [ ] Il database dei test:
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_anagrafica_revisioni WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_anagrafica_revisioni'
  ```
- [ ] Le tre voci di `next-steps.md` che citano questo piano passano a `in corso` (` → in corso su night/anagrafica-revisioni`), e si committa: `next-steps: l'Anagrafica da rivedere, in corso`.
- [ ] La linea di partenza: pytest e vitest dal worktree, tutto verde. **Annota** i numeri. Se non è verde, fermati e scrivilo nel report.
- [ ] Guarda se `night/tempi-ai` è già su `master` (`git -C <worktree> log master --oneline | grep -i "quattro minuti"`), e annotalo: decide il punto del Task 3 su Nginx.

---

## Decisioni prese

1. **Di Mattia (2026-11-23): nella fusione la scelta vera passa al vincitore**, quando il vincitore non ha niente o ha un «nessuno» deciso dall'AI. Un «nessuno» deciso da una persona resta. **La figura passa sempre** quando il vincitore non ne ha una: `emoji` non dice chi l'ha decisa. Questo rovescia, per quel caso, la decisione del 2026-10-13 (spec S4 §4.15, `test_la_fusione_perde_…`): dove il vincitore ha una scelta sua, la tiene, come allora.
2. **I pesi si ereditano unità per unità** (Claude, su delega). Per ogni unità del perdente vale la regola della decisione 1 sulla riga del vincitore per la stessa unità: nessuna riga, oppure `grams` `NULL` deciso dall'AI, e il peso del perdente passa con il suo `decided_by`. Le altre righe del perdente se ne vanno con lui, come oggi.
3. **Chi ha deciso passa con la scelta** (Claude, su delega): una scelta ereditata dall'AI resta `ai`, quindi resta da rivedere.
4. **Di Mattia (2026-11-23): la pagina `/anagrafica/sostituti`.**
   - In cima all'Anagrafica c'è il link «Sostituti da rivedere (n)».
   - Le voci vanno dalla più usata.
   - Ogni voce è la scheda di oggi della sezione «Sostituti», con «Va bene così» e «Correggi», e il nome dell'ingrediente che porta alla sua scheda.
   - Una voce senza risposta ha «Chiedi all'AI», sia qui sia nella scheda dell'ingrediente.
5. **Di Mattia (2026-11-23): «Da controllare» alla lettura, senza migrazione**, anche sulle scelte che ci sono già, con le stesse voci nella pagina della decisione 4. La pagina ha due sezioni: «Sostituti da rivedere» e «Alimenti da controllare».
   - Il secondo link in cima all'Anagrafica, «Alimenti da controllare (m)», porta a `/anagrafica/sostituti#alimenti` (Claude, su delega: un solo link con un conto solo nasconderebbe l'altra metà).
   - Ciascun link c'è solo con un conto sopra zero.
6. **I reparti che si controllano** (Claude, su delega): verdura, frutta, carne, pesce, latticini, cereali, legumi, bevande. «Altro», «condimenti», «spezie» e «dolci» sono troppo misti, e lì il controllo direbbe solo rumore.
   - La tabella sta in `backend/app/domain/ciqual_check.py` e va dal reparto all'insieme dei sottogruppi CIQUAL che gli stanno.
   - I nomi sono quelli del file del 2025 con gli spazi e gli a capo ridotti a uno spazio, come `group_fr` li conserva una volta normalizzati.
   - Un sottogruppo può stare in più reparti.
   - Un limite noto, da scrivere nel report: «uova» in «latticini» con «Lait entier» non si segnalerebbe, perché il latte sta nei latticini. Il controllo prende gli errori fra reparti, non quelli dentro un reparto.
7. **«Va bene così» su un alimento da controllare** rimanda la stessa scelta come scelta a mano (`PUT /ingredients/{id}/nutrition` con lo stesso codice). La scelta diventa `human` ed esce dall'elenco: lo stesso gesto della voce dei sostituti (Claude, su delega).
8. **Le letture della revisione** (Claude, su delega).
   - `GET /api/v1/review/counts` → `{substitutes: int, foods: int}`.
   - `GET /api/v1/review/substitutes?offset=&limit=` (al più 50) → `{total, voices: [...]}`. Ogni voce ha `ingredient_id`, `ingredient_name`, il `display_name`, `context`, `recipes` e i campi di `ContextSubstitutionOut`.
   - `GET /api/v1/review/foods` → l'elenco intero, perché sono decine e non migliaia. Ogni voce ha `ingredient_id`, `ingredient_name`, `category` e `food` (`CiqualFoodOut`).

## Margine di autonomia

- Liberi: i nomi interni e dei test; come si sposta `ContextCard` per riusarla (export da `IngredientSubstitutes.tsx`, o un file suo); l'aspetto delle righe della pagina, con i primitivi di `components/ui/`.
- Fissi: le rotte, i campi nuovi di `MergeOut`, `IngredientNutritionOut.to_check`, `food_fits_category`, le parole a video.
- **Fermati** (voce `bloccato` nel report) in due casi:
  - un sottogruppo del file CIQUAL non si lascia attribuire a un reparto senza indovinare: lascialo fuori dalla tabella e scrivilo nel report, non fermare tutto;
  - l'eredità dei pesi richiede di scrivere una riga per un'unità che `resolve_pair_unit` non riconosce.

---

### Task 1: la fusione eredita figura, alimento e pesi

**Files:**
- Modify: `backend/app/services/registry.py`:
  - `merge_ingredients`: la fotografia all'inizio e l'eredità alla fine, dopo `delete_ingredient_if_unused` e prima di `materialize_ready`;
  - `MergeCounts`.
- Modify: `backend/app/services/ingredient_nutrition.py` (`inherit_choice`), `backend/app/services/unit_grams.py` (`inherit_grams`)
- Modify: `backend/app/schemas/ingredient.py` (`MergeOut`: `inherited_emoji: bool`, `inherited_food: bool`, `inherited_weights: int`) e la rotta della fusione che lo costruisce
- Modify: il commento sul `CASCADE` in `backend/app/db/models/nutrition.py` (oggi dice «La fusione la perde»)
- Test: `backend/tests/services/test_registry_merge.py`, e le docstring di `test_la_fusione_perde_i_pesi_del_perdente` (`tests/services/test_unit_grams.py`) e di `test_la_fusione_perde_la_scelta_del_perdente_e_tiene_quella_del_vincitore` (`tests/services/test_ingredient_nutrition.py`)

**Interfaces:**
- Produces:
  - `async def inherit_choice(session, winner_id, code: str | None, decided_by: str) -> bool`: scrive solo con la regola della decisione 1, e torna `True` se ha scritto;
  - `async def inherit_grams(session, winner_id, weights: Sequence[tuple[uuid.UUID | None, Decimal | None, str]]) -> int`: quanti pesi ha scritto;
  - `MergeCounts.inherited_emoji`, `inherited_food`, `inherited_weights`.

- [ ] **Step 1: I test che falliscono**, in `test_registry_merge.py`, con gli helper che il file ha già.
  - `test_la_fusione_eredita_la_figura_se_il_vincitore_non_ne_ha`: una tabella con il vincitore `NULL`, `""` e «🍅», e il perdente «🥫». Il risultato è «🥫», «🥫», «🍅»; `inherited_emoji` vale vero, vero, falso. Con il perdente `NULL` o `""` non passa niente.
  - `test_la_fusione_eredita_l_alimento`: una tabella su vincitore × perdente. Il vincitore è senza riga, «nessuno» AI, «nessuno» umano o un codice; il perdente è un codice AI o un codice umano. Passa nei primi due casi del vincitore, con il `decided_by` del perdente; negli altri due resta quello del vincitore.
  - `test_la_fusione_eredita_i_pesi_unita_per_unita`.
    - Il vincitore ha `pezzo` = 50 (umano) e `cucchiaio` = NULL (AI).
    - Il perdente ha `pezzo` = 55 (AI), `cucchiaio` = 12 (AI) e `tazza` = 200 (AI).
    - Dopo: `pezzo` = 50, `cucchiaio` = 12, `tazza` = 200; `inherited_weights == 2`.
  - `test_l_eredita_resta_anche_se_l_annullamento_cancella_il_perdente`: il perdente è creato da un termine dell'import (`created_ingredient`) e ha figura, alimento e un peso. La fusione lo cancella annullando il termine, e il vincitore ha comunque le tre cose.
  - `test_l_anteprima_dice_cosa_eredita`: `preview_merge` dà gli stessi tre campi della fusione vera, e dopo l'anteprima il vincitore non ha ereditato niente.
- [ ] **Step 2: Falliscono**: il comando di pytest con `tests/services/test_registry_merge.py`. Expected: il vincitore resta senza le scelte del perdente.
- [ ] **Step 3: Il codice.**
  - Le tre letture del perdente si fanno con `select` di colonne, accanto a `alias_names`, prima del ciclo dei termini.
  - Le scritture vanno alla fine, prima di `materialize_ready`, così le ricette rifatte leggono già l'alimento del vincitore.
  - La figura si scrive con la stessa assegnazione di `set_ingredient_emoji`, passando da `canonical_emoji`.
  - `inherit_choice` e `inherit_grams` usano l'`INSERT … ON CONFLICT DO UPDATE` di `choose_food` e `set_grams`, con `decided_at=func.now()` e la condizione della decisione 1 nel `WHERE` dell'update (oppure letta prima: è la stessa transazione).
  - La docstring di `merge_ingredients` dice cosa eredita e cita le decisioni 1 e 2.
  - Le docstring dei due test di oggi dicono che il vincitore tiene la sua scelta quando ne ha una (Mattia, 2026-11-23).
- [ ] **Step 4: Passano**, con `tests/services/test_registry_merge*.py`, `tests/services/test_unit_grams.py`, `tests/services/test_ingredient_nutrition.py`, `tests/api/test_registry_ingredients.py`. Poi la suite intera.
- [ ] **Step 5: Commit**: `anagrafica: la fusione eredita figura, alimento e pesi dove il vincitore non ne ha`.

### Task 2: l'anteprima e l'esito della fusione dicono cosa eredita

**Files:**
- Modify: `frontend/src/domain/types.ts` (`MergeCounts`: i tre campi), `frontend/src/features/registry/wording.ts` (`inheritedText`, usata da `mergePreviewText` e `mergeDoneText`)
- Test: `frontend/src/features/registry/wording.test.ts`

**Interfaces:**
- Produces: `inheritedText(counts: MergeCounts, done: boolean): string`.
  - Anteprima: ««pomodoro» prende da «pomodori» la figura, l'alimento CIQUAL e 2 pesi.»
  - Esito: ««pomodoro» ha preso da «pomodori» la figura, l'alimento CIQUAL e 2 pesi.»
  - Le parti sono «la figura», «l'alimento CIQUAL», «1 peso» o «‹n› pesi», unite come le altre frasi del file («a, b e c»).
  - Senza niente da ereditare, `""`.

- [ ] **Step 1: I test che falliscono.**
  - `mergePreviewText` con le tre cose mette la frase subito prima di ««pomodori» diventa un alias di «pomodoro».»;
  - con il solo peso: ««pomodoro» prende da «pomodori» 1 peso.»;
  - `mergeDoneText` usa «ha preso»;
  - senza niente da ereditare, i testi di oggi non cambiano, e i test di oggi restano come sono.
- [ ] **Step 2: Falliscono**: `npx vitest run --maxWorkers=4 src/features/registry/wording.test.ts`.
- [ ] **Step 3: Il codice.**
- [ ] **Step 4: Passano**, poi `npm run typecheck` (i finti di `IngredientScreen.test.tsx` che costruiscono un `MergeCounts` prendono i tre campi a `false`/`0`).
- [ ] **Step 5: Commit**: `anagrafica: la fusione dice cosa eredita il vincitore`.

### Task 3: «Chiedi all'AI» per una voce senza risposta

**Files:**
- Modify: `backend/app/api/substitutions.py` (`ask_ingredient_substitution`, `POST /{ingredient_id}/substitutes/{context}/ask` su `ingredient_router`)
- Modify: `backend/app/schemas/substitution.py` (`IngredientSubstitutionsOut`: `ai_failed: bool = False`, `ai_notice: str | None = None`)
- Modify: `frontend/src/features/substitutes/api.ts` (`askIngredientSubstitution(ingredientId, context)`), `frontend/src/features/substitutes/IngredientSubstitutes.tsx` (il ramo `item.verdict === null` di `ContextCard`)
- Test: `backend/tests/api/test_substitutions_registry.py`, `frontend/src/features/substitutes/IngredientSubstitutes.test.tsx`

**Interfaces:**
- Consumes: `decide_pair(session, ingredient_id, context)`, che torna `PairOutcome(failed, notice, stored)`.
- Produces:
  - la rotta: 404 per un ingrediente che non c'è e 422 per un non alimentare, con la frase di `correct_ingredient_substitution`. Altrimenti `decide_pair`, `commit`, e `_ingredient_out` con `ai_failed=outcome.failed` e `ai_notice=outcome.notice`;
  - `askIngredientSubstitution` → `IngredientSubstitutions`.

- [ ] **Step 1: I test che falliscono.**
  - Backend:
    - `test_chiedi_all_ai_scrive_la_voce`, col client finto che risponde una voce valida: la risposta ha quel contesto con `verdict` e `decided_by == "ai"`, e c'è una riga in `llm_calls`;
    - `test_chiedi_all_ai_non_chiama_se_la_voce_c_e_gia`: il finto non riceve chiamate;
    - `test_chiedi_all_ai_senza_chiave_dice_perche`: `ai_failed` vero, `ai_notice` è la frase di `LlmUnavailable` e nessuna riga in `llm_calls`;
    - `test_chiedi_all_ai_rifiuta_un_non_alimentare`: 422.
  - Frontend:
    - «una voce senza risposta si chiede all'AI»: nella scheda col `verdict` `null` si leggono «Nessun suggerimento ancora.» e due pulsanti, «Chiedi all'AI» (nome accessibile «Chiedi all'AI: ‹in un piatto salato›», con le parole di `contextIn`) e «Scrivi tu». Toccato «Chiedi all'AI», parte il `POST …/ask`, e la risposta mostra la voce con «Deciso dall'AI: da rivedere.».
    - «se l'AI non risponde»: con `ai_failed: true` e `ai_notice`, sotto la scheda si legge «‹ai_notice› Scrivila tu, o riprova fra poco.»; senza `ai_notice`, «L'AI non ha risposto. Scrivila tu, o riprova fra poco.». «Scrivi tu» resta.
- [ ] **Step 2: Falliscono** (il comando di pytest con `tests/api/test_substitutions_registry.py`; `npx vitest run --maxWorkers=4 src/features/substitutes`).
- [ ] **Step 3: Il codice.**
  - La frase di oggi, «Nessun suggerimento ancora: lo chiedo all'AI la prima volta che lo sostituisci in una ricetta.», diventa «Nessun suggerimento ancora.».
  - L'avviso del guasto usa `Alert tone="degraded"`, il colore di ogni guasto dell'AI.
  - Sopra la rotta, un commento cita la regex di Nginx: il punto da cucire con `tempi-ai`, nelle Global Constraints.
  - Se `night/tempi-ai` è già su `master`, aggiungi qui la rotta alla regex in `frontend/nginx.conf` e una prova in `tests/test_nginx_ai_sync.py`.
- [ ] **Step 4: Passano**, poi la suite intera del backend e i controlli del frontend.
- [ ] **Step 5: Commit**: `sostituti: «Chiedi all'AI» dalla scheda dell'ingrediente`.

### Task 4: le letture della revisione e la pagina dei sostituti

**Files:**
- Modify: `backend/app/repositories/substitutions.py` (`ai_voices_to_review(session, offset, limit) -> tuple[int, list[ReviewVoice]]`, sopra `_usage`)
- Create: `backend/app/api/review.py` (`counts`, `substitutes`; `foods` arriva nel Task 5, e intanto `counts` dà `foods: 0`), registrata dove si registrano le altre rotte (`backend/app/main.py`)
- Create: `backend/app/schemas/review.py`
- Create: `frontend/src/features/registry/ReviewScreen.tsx`, `frontend/src/features/registry/reviewApi.ts`
- Modify: `frontend/src/App.tsx` (la rotta `/anagrafica/sostituti`, prima di `/anagrafica/ingrediente/:id`)
- Modify: `frontend/src/features/registry/RegistryScreen.tsx` (i link in cima)
- Modify: `frontend/src/features/substitutes/IngredientSubstitutes.tsx` (`ContextCard` esportata, con una prop facoltativa per il titolo con il nome dell'ingrediente come link)
- Test: `backend/tests/api/test_review.py` (nuovo), `frontend/src/features/registry/ReviewScreen.test.tsx` (nuovo), `frontend/src/features/registry/RegistryScreen.test.tsx`

**Interfaces:**
- Produces:
  - `ai_voices_to_review`: le voci generali con `decided_by == "ai"` che rispondono (`is_answered`), con le ricette di `_usage` per quel contesto (0 se nessuna). L'ordine è ricette decrescenti, poi nome, poi contesto. Il totale si conta sullo stesso insieme.
  - Le rotte della decisione 8.

- [ ] **Step 1: I test che falliscono.**
  - Backend:
    - `test_le_voci_da_rivedere_vanno_dalla_piu_usata`: tre voci AI usate in 1, 5 e 3 ricette, più una voce umana, più una voce AI senza sostituti visibili (che non risponde). L'elenco ha 5, 3, 1, e `total == 3`.
    - `test_va_bene_cosi_toglie_la_voce`: dopo il `PUT` della voce generale, `total` cala di uno e `counts.substitutes` pure.
    - `test_le_voci_si_leggono_a_pagine`: 55 voci; `offset=50` ne dà 5.
  - Frontend:
    - In `ReviewScreen.test.tsx`, «la pagina dei sostituti da rivedere»: titolo «Da rivedere», sezione «Sostituti da rivedere», una scheda per voce col nome dell'ingrediente che porta a `/anagrafica/ingrediente/<id>`, con «Va bene così» e «Correggi». Dopo «Va bene così» la scheda sparisce dalla pagina, perché la query si rilegge.
    - «altre voci»: con `total` sopra le righe arrivate c'è «Mostra altre voci», e toccarlo chiede `offset=50`.
    - «niente da rivedere»: con `total: 0` si legge «Nessun sostituto da rivedere: li hai guardati tutti.».
    - «l'elenco non si legge»: «Non sono riuscito a leggere le voci da rivedere.» con «Riprova».
    - In `RegistryScreen.test.tsx`, con `counts` `{substitutes: 1105, foods: 0}`: c'è il link «Sostituti da rivedere (1105)» verso `/anagrafica/sostituti`, e non c'è «Alimenti da controllare». Con `{0, 0}` non c'è nessuno dei due.
- [ ] **Step 2: Falliscono** (il comando di pytest con `tests/api/test_review.py`; `npx vitest run --maxWorkers=4 src/features/registry src/features/substitutes`).
- [ ] **Step 3: Il codice.**
  - La pagina usa `Screen` con il titolo «Da rivedere» e `back={{ to: "/anagrafica", label: "Anagrafica" }}`, e `useInfiniteQuery` come `SkippedPages`.
  - Ogni scheda è `ContextCard`. La chiave della query sta sotto `["registry", "review"]`, e un «Va bene così» o un «Correggi» salvato la invalida, insieme a `["substitution"]` come fa oggi la scheda.
  - I link in cima all'Anagrafica stanno sopra il campo di ricerca, come righe di testo-link, non come pulsanti primari.
- [ ] **Step 4: Passano**, poi le suite intere.
- [ ] **Step 5: Commit**: `anagrafica: i sostituti decisi dall'AI da rivedere in una pagina sola`.

### Task 5: la scelta CIQUAL da controllare, nel backend

**Files:**
- Create: `backend/app/domain/ciqual_check.py` (`CHECKED_GROUPS: Mapping[str, frozenset[str]]`, `normalize_group`, `food_fits_category`)
- Modify: `backend/app/services/ingredient_nutrition.py` (`NutritionView.to_check: bool`, calcolato in `nutrition_of`), `backend/app/schemas/nutrition.py` (`IngredientNutritionOut.to_check: bool = False`), `backend/app/api/nutrition.py` (`nutrition_out`)
- Modify: `backend/app/api/review.py` (`foods`, e `counts.foods`)
- Test: `backend/tests/domain/test_ciqual_check.py` (nuovo), `backend/tests/api/test_nutrition.py`, `backend/tests/api/test_review.py`

**Interfaces:**
- Produces:
  - `def food_fits_category(category: str, group_fr: str | None) -> bool | None`: `None` se il reparto non si controlla o il gruppo manca; altrimenti se il gruppo normalizzato sta nell'insieme del reparto;
  - `to_check`, vero solo con `state == "food"`, `decided_by == "ai"` e `food_fits_category(...) is False`.

- [ ] **Step 1: Prima della tabella, l'elenco dei sottogruppi veri.** Leggi i gruppi distinti del file del repository con `read_ciqual` (il percorso è in `CANDIDATE_FILES` di `app.cli.load_ciqual`). Va lanciato una volta e non sta nel codice. È una lettura del file, leggera.
  ```bash
  cd <worktree>/backend && PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -c "
  from app.cli.load_ciqual import CANDIDATE_FILES
  from app.services.ciqual_file import read_ciqual
  import pathlib
  path = next(p for p in map(pathlib.Path, CANDIDATE_FILES) if p.exists())
  rows = read_ciqual(path)
  rows = rows[0] if isinstance(rows, tuple) else rows
  print(sorted({' '.join((r.group_fr or '').split()) for r in rows}))"
  ```
  Adatta la chiamata se `read_ciqual` ha un'altra forma. Copia l'elenco nel report e costruisci la tabella dei reparti della decisione 6.
- [ ] **Step 2: I test che falliscono.**
  - `test_ogni_gruppo_della_tabella_esiste_nel_file_vero`: legge il file vero e controlla che ogni nome di `CHECKED_GROUPS` sia fra i gruppi normalizzati. È la guardia contro un refuso, che altrimenti renderebbe tutto «da controllare».
  - `test_il_controllo_per_reparto`, una tabella:
    - `("pesce", "viandes cuites")` → `False`;
    - `("pesce", <il gruppo dei poissons>)` → `True`;
    - `("latticini", <il gruppo dei fromages>)` → `True`;
    - `("altro", qualunque)` → `None`;
    - `("carne", None)` → `None`;
    - un gruppo con l'a capo in mezzo combacia come quello normalizzato.

    Usa i nomi veri trovati allo Step 1.
  - In `test_nutrition.py`:
    - `test_una_scelta_dell_ai_fuori_reparto_e_da_controllare`: `to_check` vero;
    - con la stessa scelta fatta a mano, falso;
    - con il reparto «altro», falso.
  - In `test_review.py`, `test_gli_alimenti_da_controllare`: due scelte AI fuori reparto e una dentro; `foods` dà le due, `counts.foods == 2`. Dopo il `PUT` della stessa scelta a mano, una.
- [ ] **Step 3: Falliscono** (il comando di pytest con quei file).
- [ ] **Step 4: Il codice.**
  - `foods` legge in una query le scelte `ai` con un codice, con l'ingrediente e `ciqual_foods.group_fr`, e filtra in Python con `food_fits_category`. La regola sta in un posto solo, nel dominio.
  - L'ordine è per nome dell'ingrediente.
  - La docstring del modulo dice la decisione 6, compreso il limite su «uova».
- [ ] **Step 5: Passano**, poi la suite intera.
- [ ] **Step 6: Commit**: `S4: la scelta CIQUAL dell'AI fuori dal reparto è da controllare`.

### Task 6: «Da controllare» nella scheda e nella pagina

**Files:**
- Modify: `frontend/src/features/registry/nutrition.ts` (il tipo con `to_check`), `frontend/src/features/registry/NutritionSection.tsx`
- Modify: `frontend/src/features/registry/ReviewScreen.tsx` (la sezione «Alimenti da controllare», con `id="alimenti"`), `frontend/src/features/registry/RegistryScreen.tsx` (il secondo link)
- Test: `frontend/src/features/registry/NutritionSection.test.tsx`, `frontend/src/features/registry/ReviewScreen.test.tsx`, `frontend/src/features/registry/RegistryScreen.test.tsx`

- [ ] **Step 1: I test che falliscono.**
  - In `NutritionSection.test.tsx`, «una scelta fuori reparto è da controllare». Con `to_check: true`, sotto il nome dell'alimento si legge «Da controllare: l'AI ha scelto un alimento di «‹group_fr›», che non è del reparto «‹reparto›».». C'è «Va bene così», che manda `PUT …/nutrition` con lo stesso `ciqual_code`; dopo la risposta (con `to_check: false`) la frase sparisce. Con `to_check: false` niente.
  - In `ReviewScreen.test.tsx`, «gli alimenti da controllare»:
    - la sezione «Alimenti da controllare» ha una riga per voce, col nome dell'ingrediente (link alla sua scheda), «‹reparto› · ‹name_fr›» e «Va bene così»;
    - con l'elenco vuoto, «Nessun alimento da controllare.».
  - In `RegistryScreen.test.tsx`: con `foods: 3` c'è «Alimenti da controllare (3)» verso `/anagrafica/sostituti#alimenti`.
- [ ] **Step 2: Falliscono**: `npx vitest run --maxWorkers=4 src/features/registry`.
- [ ] **Step 3: Il codice.**
  - La frase ha l'ambra di «funziona, ma non del tutto» (`text-low`), come «Deciso dall'AI: da rivedere.».
  - Il gruppo si mostra normalizzato: gli a capo diventano spazi.
  - «Va bene così» invalida la query della scheda e `["registry", "review"]`.
  - Arrivando su `#alimenti`, la sezione si scorre in vista una volta caricata.
- [ ] **Step 4: Passano**, poi i controlli interi del frontend.
- [ ] **Step 5: Commit**: `S4: «Da controllare» nella scheda e fra le cose da rivedere`.

### Task 7: e2e, la verifica, il backlog

- [ ] **Step 1: La rotta nuova in `frontend/e2e/style.spec.ts`**, accanto alle altre dell'Anagrafica. Poi la **e2e intera**, con i comandi delle Global Constraints, dentro il limite di carico.
- [ ] **Step 2: Nel browser**, sullo stack e2e prima del `down`, a 375 px:
  - unisci due ingredienti del seme, dove il perdente ha una figura e il vincitore no: l'anteprima dice «prende da …»;
  - apri «Da rivedere» dal link in Anagrafica, se il seme ha voci AI. Se non ne ha, apri `/anagrafica/sostituti` a mano e guarda lo stato vuoto «Nessun sostituto da rivedere: li hai guardati tutti.».
  - Gli screenshot vanno nel report.
- [ ] **Step 3: Il backlog.**
  - Le tre voci passano a `fatto <data>` in «Fatti (recenti)», con ` → branch night/anagrafica-revisioni (da revisionare)`.
  - In «Da fare a mano (solo Mattia)» va una riga `tbd` P3: «Dopo il deploy di night/anagrafica-revisioni: in Anagrafica, «Alimenti da controllare (m)» sulle scelte vere; se m è grande o le voci sono quasi tutte giuste, la tabella dei reparti va ristretta (decisione 6 del piano 2026-11-23-anagrafica-revisioni)».
  - In `CLAUDE.md` non cambia niente.
  - Commit: `next-steps: l'Anagrafica da rivedere, fatto`.

## Fuori scope

- Un pilota CIQUAL con più nomi comuni, o il controllo al momento della scelta (opzioni scartate da Mattia il 2026-11-23).
- Ereditare il reparto, il nome o i prodotti oltre a quel che la fusione sposta già.
- Rivedere le correzioni di ricetta dei sostituti (sono sempre a mano).
- «Chiedi all'AI» per tutte le voci scoperte in blocco: resta il comando `decide_substitutes`.

## Comandi di verifica

- Backend: il comando di pytest delle Global Constraints, tutto verde, con i test nuovi.
- Frontend, da `<worktree>/frontend`: `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- e2e: la suite intera, verde.
- `git -C <worktree> diff master --stat` tocca solo i file dei task, più `next-steps.md` e il report. `frontend/nginx.conf` è toccato solo se `night/tempi-ai` era già su `master`.
