# Pasti, quarto giro: «Continua» dopo i troppi passaggi, gli ingredienti che restano dopo «Annulla», l'inversa e la riga smarcata — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** chiudere le quattro idee P3 dei Pasti rimaste in `next-steps.md` [Parte IV], con le decisioni di Mattia del 2026-11-23:
- la risposta interrotta dai «troppi passaggi» ha un pulsante «Continua», e al giro dopo Claude sa di essere stato interrotto;
- dopo «Annulla» di una modifica, la chat dice quali ingredienti creati da quella modifica restano in Anagrafica, e un ingrediente nominato da una scheda dei cambi ancora proposta non si cancella più;
- nell'inversa, una riga di lista che Mattia ha smarcato applicando la scheda di un altro pasto non tiene più la voce in lista; il vettore della ricetta si calcola fuori dal lucchetto del pasto;
- i legami d'avanzo già fuori dalla finestra di 3 giorni: nessun codice, la voce si chiude (decisione 4).

**Architecture:**
- **La cronologia.** `HistoryItem` sa se una risposta si è interrotta. La regola sta nel dominio della chat, `reply_interrupted`: una risposta di Claude `sent` con un `notice`, che oggi scrive solo `_reply` nel caso `MAX_TURNS`. `_history_rows` aggiunge una riga fissa per Claude, e vale per le tre specie: piatto, pianificazione e coda delle ricette.
- **«Continua».** `ChatMessageOut.can_continue` lo decide il backend: è vero solo sull'ultimo messaggio della conversazione, se è una risposta interrotta. Il frontend mostra il pulsante e manda un messaggio normale, «Continua da dove ti sei fermato.», con il tetto di sempre. Il backend non riceve niente di nuovo.
- **Gli ingredienti che restano.** `RecipeChangeOut.kept_note` porta la frase già pronta dal backend. La vista la calcola con una query sola per tutte le modifiche annullate (la regola di C7). `delete_ingredient_if_unused` conta come uso anche le righe delle schede `proposed`.
- **L'inversa.** In `_list_still_needed`, la riga di una scheda applicata conta solo se è stata applicata o non era modificabile («Già in lista.»). Le schede proposte contano come oggi.
- **Il vettore.** In `write_meal_recipe` e in `undo_recipe_change`, `embedding_for` gira prima di `lock_meal`. Sotto il lucchetto gira solo nella corsa rara in cui, fra la lettura e il lucchetto, la ricetta è cambiata e il vettore serve.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, pytest su Postgres vero (anche con due sessioni); React 19, TanStack Query 5, Vitest + Testing Library; Playwright per l'e2e.

**Spec:** `docs/superpowers/specs/2026-11-12-pasti-claude-design.md` §6.2 (la scheda inversa), §6.3 («Annulla» e gli ingredienti creati), §9 (quando Claude non c'è). I piani da cui si parte: `docs/superpowers/plans/2026-11-18-pasti-chiave-api.md` (decisioni C4 e C6, che restano: nessun «Riprova» sulla risposta interrotta; la «Ricetta scritta» annullata tiene i suoi ingredienti), `2026-11-18-pasti-correzioni.md` e `2026-11-21-pasti-terzo-giro.md` (l'inversa per voce, `NO_LONGER_FINISHED_NOTE`, il lucchetto del pasto). **Decisioni di Mattia del 2026-11-23**: sotto. Le voci di `next-steps.md` cominciano per «Pasti con Claude: la risposta interrotta dai «troppi passaggi»», «Pasti con Claude: «Annulla» di una modifica che aveva creato ingredienti», «Pasti con Claude: nell'inversa, una riga di lista smarcata da Mattia» e «Pasti: i legami di avanzo già fuori dalla finestra di 3 giorni».

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/pasti-quarto-giro`, ramo `night/pasti-quarto-giro`, creato da `master`. Nel piano `<worktree>` è quel percorso, e ogni comando parte da lì. **Nessun push, nessun merge, nessun deploy. Mai `git stash`. Niente letture o scritture sulla produzione, e mai il `.env` del checkout principale. Nessuna chiamata vera a Claude.**
- **Se nella stessa notte girano anche `2026-11-22-ricetta-a-mano-vince.md` e `2026-11-22-ricetta-pasto-lucchetto.md`**, i tre piani restano rami separati, tutti da `master`. Si toccano solo in `backend/app/services/meal_recipes.py`:
  - qui `write_meal_recipe` (il vettore) e `undo_recipe_change`;
  - in `ricetta-a-mano-vince`, `untouched_ai_change` e `MealRecipeDraft.servings`;
  - in `ricetta-pasto-lucchetto`, `recipe_snapshot` estratta da `meal_snapshot`.

  Questo piano non tocca `backend/app/api/recipes.py` né `backend/app/services/claude/tools.py`. Nel report scrivi le funzioni toccate da entrambi, dove il merge dovrà cucire.
- **«Claude propone, Mattia applica» non cambia**: nessuna scrittura nuova su dispensa o lista. L'inversa cambia solo quali righe propone.
- **Il frontend non decide** se si può continuare né quali ingredienti restano: lo dice il server (`can_continue`, `kept_note`). Il frontend mostra soltanto.
- **Mai un vicolo cieco**: «Continua» rifiutato (503 senza Claude, 409 `claude_busy`) mostra il rifiuto come ogni altro messaggio della chat, e il messaggio non si perde (il comportamento di `sendText` di oggi).
- **Ordine dei lucchetti e rete**: prima il pasto (`lock_meal`), poi la ricetta, come oggi. Nel percorso normale `embedding_for` non gira mai col pasto bloccato.
- Le parole a video **si copiano esatte** da questo piano (fra «»). Gli identificatori in inglese, i commenti in italiano.
- **Il type check è `npm run typecheck`**, mai `tsc --noEmit`. Controlli del frontend, da `<worktree>/frontend`: `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- **Il carico sulla macchina**: al massimo 6 thread e 8 GB (Mattia, 2026-11-22). Le suite intere girano dentro `systemd-run --user --scope -p MemoryMax=8G -p CPUQuota=600% …`, mai due insieme. Vitest gira con `--maxWorkers=4`, pytest senza parallelismo.
- **Backend su Postgres vero**: `spena-db-1` (porta 5433), con il database `spena_test_pasti_quarto_giro`. Mai `docker compose up` dal worktree. Si usa il `.venv` del checkout principale. Il comando di pytest, da `<worktree>/backend`:
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_pasti_quarto_giro \
    PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
- **e2e** sullo stack `spena-e2e`, con i comandi delle Global Constraints di `docs/superpowers/plans/2026-11-18-pasti-correzioni.md`:
  - il `.env` da `.env.example`, cancellato alla fine;
  - `-p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml` in ogni comando;
  - il seme con le ricette e le due righe della fixture CIQUAL;
  - `down -v` e `rm .env`, sempre.
- Nessuna dipendenza nuova, **nessuna migrazione**: le colonne che servono ci sono già (`conversation_messages.notice`, `recipe_changes.created_ingredient_ids`, `change_card_rows.applied` ed `editable`).
- **I test di oggi si cambiano solo dove il piano lo dice**: i confronti a dizionario intero di un messaggio o di una modifica della chat, che ricevono il campo nuovo (`can_continue`, `kept_note`) e nient'altro. Se cade altro, il comportamento è cambiato, e si corregge il codice.

## Review Focus

1. **«Continua» solo dove ha senso**: sull'ultima risposta interrotta, non su una risposta interrotta seguita da altri messaggi, non su una risposta normale, non su un messaggio fallito (che ha «Riprova»). Il messaggio mandato è esattamente «Continua da dove ti sei fermato.», senza `retry_of`. Task 2 e Task 6.
2. **La cronologia dice l'interruzione** nelle tre specie (piatto, pianificazione, coda delle ricette), solo per le risposte interrotte, e il giro dopo una risposta interrotta la riceve davvero nel prompt. Task 1.
3. **«Resta/Restano in Anagrafica»**:
   - c'è solo sotto una modifica annullata i cui ingredienti creati esistono ancora;
   - un ingrediente nominato da una scheda `proposed` non si cancella, e la riga della scheda tiene il suo `ingredient_id`;
   - le schede applicate, scartate o superate non trattengono niente;
   - la vista fa lo stesso numero di query con una o con otto modifiche annullate.

   Task 3.
4. **L'inversa e la riga smarcata**: una riga modificabile, lasciata senza spunta su una scheda applicata di un altro pasto, non tiene la voce in lista, e l'inversa la propone già spuntata. La «Già in lista.» e le schede proposte la tengono come oggi (`test_l_inversa_non_toglie_dalla_lista_cio_che_serve_a_un_altro_pasto` non cambia). Task 4.
5. **Il vettore fuori dal lucchetto**: scrivendo una ricetta e annullando una modifica che aveva cambiato il titolo, `embedding_for` gira con il pasto libero, e nella corsa fra la lettura e il lucchetto il vettore salvato è quello giusto. Task 5.

### Preparazione (una volta, prima del Task 1)

- [ ] Il worktree, con `node_modules` collegato e nessun `.env`:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/pasti-quarto-giro -b night/pasti-quarto-giro master
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/pasti-quarto-giro/frontend/node_modules
  ```
- [ ] Il database dei test:
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_pasti_quarto_giro WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_pasti_quarto_giro'
  ```
- [ ] Le tre voci di `next-steps.md` che questo piano costruisce (le prime tre del Goal) passano a `in corso` (` → in corso su night/pasti-quarto-giro`), e si committa: `next-steps: pasti, quarto giro, in corso`.
- [ ] La linea di partenza: pytest e vitest dal worktree, tutto verde. **Annota** i numeri. Se non è verde, fermati e scrivilo nel report.

---

## Decisioni prese

1. **Di Mattia (2026-11-23): «Continua» sotto la risposta interrotta.** Il pulsante manda, come messaggio di Mattia, «Continua da dove ti sei fermato.», con lo stesso tetto di passaggi di sempre (`DISH_MAX_TURNS`, `PLANNING_MAX_TURNS`). Resta la decisione C4: nessun «Riprova» sulla risposta interrotta.
2. **Di Mattia (2026-11-23): la cronologia porta l'interruzione.** Al giro dopo, Claude legge che quella risposta si era fermata.
3. **Di Mattia (2026-11-23): dopo «Annulla» gli ingredienti restano, e la chat lo dice.** La «Ricetta scritta» annullata resta archiviata e i suoi ingredienti restano (C6 non cambia, nessuna migrazione). Sotto la riga «… — annullata» la chat scrive «Restano in Anagrafica: ‹nomi›.».
4. **Di Mattia (2026-11-23): i legami d'avanzo già fuori dalla finestra, nessun codice.** In produzione non ce ne sono: il controllo della scrittura (c7c536a, piano `2026-11-21-pasti-terzo-giro.md`, Task 1) è andato in produzione insieme ai Pasti, nel deploy del 2026-11-22, e nessun'altra strada crea legami d'avanzo (la pianificazione non ne crea). La voce si chiude come `fatto` con questo motivo (Task 7).
5. **Di Mattia (2026-11-23): nell'inversa la riga smarcata non conta.** Una riga di lista che Mattia ha lasciato senza spunta applicando la scheda di un altro pasto non dice che quella voce serve a lui. L'inversa propone di togliere la voce, già spuntata se è ancora da comprare (le regole di `_inverse_list_row` di oggi).
6. **Le schede proposte contano come uso** in `delete_ingredient_if_unused` (Claude, su delega, confermata da Mattia il 2026-11-23). Contano solo le `proposed`: in una scheda applicata, quello che la riga ha scritto vive già nella dispensa o nella lista, che contano da sé. Una scheda scartata o superata non si applica più. Vale per tutti i chiamanti: «Annulla» della chat, l'annullamento dell'import, l'Anagrafica.
7. **Il vettore prima del lucchetto** (Claude, su delega, confermata da Mattia il 2026-11-23).
   - In `undo_recipe_change`, se serve ricalcolarlo lo dice la modifica stessa (`change.changed["title"] or change.changed["description"]`): una modifica annullabile ha la ricetta com'era dopo di lei, quindi la scelta non dipende da cosa succede dopo il lucchetto.
   - In `write_meal_recipe`, la scelta (`new_text`) si fa su una lettura senza lucchetto e si rifà sotto il lucchetto. Il vettore si calcola sotto il lucchetto solo se la seconda scelta lo chiede e la prima no: è la corsa rara, e un commento lo dice.
8. **La riga della cronologia** (Claude, su delega): `INTERRUPTED_HISTORY_LINE = "(Qui la risposta si è interrotta: erano finiti i passaggi. Mattia ha letto solo il testo sopra.)"`, nel dominio della chat. Sta dopo il testo di Claude e dopo le righe delle sue modifiche, proposte e schede: le modifiche sono avvenute prima dell'interruzione.
9. **Il singolare** (Claude, su delega): con un ingrediente solo la frase è «Resta in Anagrafica: Spinaci novelli.». Con due, «Restano in Anagrafica: Spinaci novelli e Bietole.». Con tre o più, «Restano in Anagrafica: A, B e C.». I nomi sono i `display_name`, nell'ordine di `created_ingredient_ids`.
10. **La frase vale per ogni modifica annullata**, non solo per la «Ricetta scritta» (Claude, su delega). Anche la modifica di una ricetta che esisteva può lasciare un ingrediente, se lo usa altro. La frase dice quello che c'è, da qualsiasi parte venga.
11. **Dove sta «Continua»** (Claude, su delega): sotto l'avviso della risposta interrotta, a sinistra come la risposta, con la variante `ghost` di `Button` come «Riprova». Con la chat occupata aspetta (`busy`), come «Annulla» e «Riprova». C'è solo dove c'è il campo per scrivere (`ChatComposer`).

## Margine di autonomia

- Liberi: i nomi interni e dei test, il file del dominio dove stanno `reply_interrupted` e `kept_ingredients_note` (suggerito `backend/app/domain/meal_chat.py`), la costante del testo di «Continua» nel frontend (suggerito `CONTINUE_TEXT`, esportata da `ChatThread.tsx`).
- Fissi: le parole fra «», `INTERRUPTED_HISTORY_LINE`, `ChatMessageOut.can_continue`, `RecipeChangeOut.kept_note`.
- **Fermati** (voce `bloccato` nel report) se un test di concorrenza va in stallo: non allungare le attese per farlo passare. Fermati anche se `notice` di una risposta di Claude risulta scritto da un'altra strada oltre a `_reply` con `MAX_TURNS`: la regola di `reply_interrupted` non reggerebbe.

---

### Task 1: la cronologia sa della risposta interrotta

**Files:**
- Modify: `backend/app/domain/meal_chat.py` (`reply_interrupted`, `INTERRUPTED_HISTORY_LINE`)
- Modify: `backend/app/services/claude/prompts.py` (`HistoryItem.interrupted: bool = False`; `_history_rows`; `render_turn_prompt` usa `_history_rows` invece del suo doppione)
- Modify: `backend/app/services/meal_chat.py` (`chat_history`)
- Test: `backend/tests/domain/test_meal_chat.py`, `backend/tests/services/test_claude_prompts.py`, `backend/tests/services/test_meal_chat_turn.py`, `backend/tests/services/test_planning_turn.py`

**Interfaces:**
- Produces: `def reply_interrupted(role: str, status: str, notice: str | None) -> bool`, vero per `assistant` + `sent` + `notice` non vuoto; `HistoryItem.interrupted`; `_history_rows` che, per un elemento interrotto, mette `INTERRUPTED_HISTORY_LINE` dopo il testo e le righe dei prodotti.

- [ ] **Step 1: I test che falliscono.**
  - Dominio, `test_reply_interrupted`, parametrizzato: (`assistant`, `sent`, «…») → vero. (`assistant`, `sent`, `None`) → falso. (`user`, `failed`, «…») → falso. (`user`, `sent`, «…») → falso.
  - `test_claude_prompts.py`, `test_la_cronologia_dice_la_risposta_interrotta`: con `[HistoryItem("user", "Cambia gli spinaci"), HistoryItem("assistant", "Ho cambiato", ("Ricetta aggiornata: spinaci",), interrupted=True)]`, i tre prompt (`render_turn_prompt`, `render_planning_prompt`, `render_recipe_prompt`) hanno, in fila, «Claude: Ho cambiato», la riga della modifica, `INTERRUPTED_HISTORY_LINE`. Senza `interrupted`, la riga non c'è. `test_render_turn_prompt` resta com'è.
  - `test_meal_chat_turn.py`, `test_dopo_i_troppi_passaggi_il_giro_dopo_sa_dell_interruzione`: il primo giro è `[Say("Ho cambiato gli spinaci. "), Fail(FailureKind.MAX_TURNS, …)]`, il secondo un giro normale. Il prompt del secondo giro, letto dal finto come in `test_la_cronologia_torna_nel_prompt`, contiene `INTERRUPTED_HISTORY_LINE` dopo «Claude: Ho cambiato gli spinaci.».
  - `test_una_risposta_normale_non_porta_l_interruzione`.
  - `test_planning_turn.py`, `test_dopo_i_troppi_passaggi_la_pianificazione_sa_dell_interruzione`: lo stesso, sul giro di pianificazione.
- [ ] **Step 2: Falliscono** (il comando di pytest con quei file).
- [ ] **Step 3: Il codice.** In `chat_history`, `HistoryItem(m.role, m.text, …, interrupted=reply_interrupted(m.role, m.status, m.notice))`. Un commento in `_reply` dice che la regola del dominio si regge sul fatto che solo qui una risposta di Claude prende un `notice`.
- [ ] **Step 4: Passano**, poi la suite intera.
- [ ] **Step 5: Commit**: `fix(pasti): al giro dopo i troppi passaggi Claude sa che la risposta si era interrotta`.

### Task 2: `can_continue` sull'ultima risposta interrotta

**Files:**
- Modify: `backend/app/schemas/meal_chat.py` (`ChatMessageOut.can_continue: bool = False`)
- Modify: `backend/app/services/meal_chat.py` (`chat_messages_out`)
- Test: `backend/tests/services/test_meal_chat_turn.py`, `backend/tests/services/test_planning_turn.py`, `backend/tests/api/test_meal_chat.py`

**Interfaces:**
- Consumes: `reply_interrupted` (Task 1).
- Produces: `can_continue` vero solo sull'ultimo messaggio di `messages_of` se `reply_interrupted`. Il `ChatMessageOut` dell'evento `start` (`api/meal_chat.py`) resta col default.

- [ ] **Step 1: I test che falliscono.**
  - `test_continua_solo_sull_ultima_risposta_interrotta`: dopo un giro `MAX_TURNS`, la vista del piatto ha l'ultimo messaggio (Claude) con `can_continue` vero e gli altri falsi. Dopo un secondo giro normale, la risposta interrotta ha `can_continue` falso, e anche l'ultima.
  - `test_una_risposta_normale_non_si_continua`, e `test_un_messaggio_fallito_non_si_continua` (un `Fail(UNAVAILABLE)`: il messaggio di Mattia è `failed`, e `can_continue` è falso dappertutto).
  - `test_planning_turn.py`, `test_la_pianificazione_interrotta_si_continua`: lo stesso, sulla vista della pianificazione.
  - API, in `test_meal_chat.py`: `GET` della chat dopo un giro interrotto → `messages[-1]["can_continue"] is True`.
- [ ] **Step 2: Falliscono** (il comando di pytest con quei file).
- [ ] **Step 3: Il codice.** In `chat_messages_out`, l'ultimo `m` del ciclo è `messages[-1]`. Niente query in più.
- [ ] **Step 4: Passano**, poi la suite intera. Un confronto a dizionario intero di un messaggio riceve `can_continue` (Global Constraints).
- [ ] **Step 5: Commit**: `feat(pasti): la vista della chat dice quando l'ultima risposta interrotta si può continuare`.

### Task 3: gli ingredienti che restano dopo «Annulla», e le schede proposte che li tengono

**Files:**
- Modify: `backend/app/domain/meal_chat.py` (`kept_ingredients_note`)
- Modify: `backend/app/schemas/meal_chat.py` (`RecipeChangeOut.kept_note: str | None = None`)
- Modify: `backend/app/services/meal_chat.py` (`_change_out`, `chat_messages_out`, `dish_chat_view`)
- Modify: `backend/app/repositories/ingredients.py` (`delete_ingredient_if_unused`, e la sua docstring)
- Test: `backend/tests/domain/test_meal_chat.py`, `backend/tests/services/test_meal_recipes.py`, `backend/tests/services/test_meal_chat_turn.py`, `backend/tests/api/test_meal_chat.py`

**Interfaces:**
- Produces:
  - `def kept_ingredients_note(names: Sequence[str]) -> str | None` (decisione 9; `None` per nessun nome).
  - `kept_note` su ogni modifica annullata con almeno un id di `created_ingredient_ids` ancora esistente. Le modifiche non annullate, e l'evento `change` del giro, hanno `None`.
  - `delete_ingredient_if_unused` torna `False` anche se l'ingrediente sta su una `ChangeCardRow` di una `ChangeCard` con `status == proposed`.

- [ ] **Step 1: I test che falliscono.**
  - Dominio, `test_kept_ingredients_note`: `[]` → `None`. `["Spinaci novelli"]` → «Resta in Anagrafica: Spinaci novelli.». Due nomi → «Restano in Anagrafica: Spinaci novelli e Bietole.». Tre → «Restano in Anagrafica: Spinaci novelli, Bietole e Cavolo nero.».
  - API, `test_annullare_una_ricetta_scritta_dice_gli_ingredienti_che_restano`: una «Ricetta scritta» dalla chat con la riga nuova «Spinaci novelli», poi «Annulla» dalla rotta. Nella vista restituita la modifica ha `undone` vero e `kept_note` «Resta in Anagrafica: Spinaci novelli.».
  - `test_annullare_una_modifica_che_toglie_l_ingrediente_non_dice_niente`: lo schema di `test_annulla_toglie_l_ingrediente_creato`, con le modifiche nella conversazione; dopo «Annulla», `kept_note is None`.
  - `test_una_modifica_annullata_senza_ingredienti_creati_non_dice_niente`.
  - `test_la_vista_legge_gli_ingredienti_rimasti_con_una_query_sola`: sul modello di `test_la_vista_della_chat_non_rilegge_il_pasto_per_ogni_modifica` e del suo contatore. Con una o con otto modifiche annullate, ognuna con un ingrediente rimasto, si conta lo stesso numero di query.
  - `test_meal_recipes.py`, `test_annulla_non_toglie_un_ingrediente_di_una_scheda_proposta`: dopo `_with_new_ingredient`, una scheda proposta per il pasto (`propose_card`) con `ListProposal(novelli.id, "Spinaci novelli")`; poi «Annulla» della seconda modifica. L'ingrediente c'è ancora, e la riga della scheda ha ancora `ingredient_id == novelli.id`.
  - `@pytest.mark.parametrize("chiusa", ["applicata", "scartata", "superata"])`, `test_una_scheda_chiusa_non_tiene_l_ingrediente`: dopo «Annulla», l'ingrediente non c'è più. Ogni stato si raggiunge con i servizi veri:
    - applicata: `apply_card` con `RowOverride(riga.id, checked=False)`, così niente va in lista;
    - scartata: `discard_card`;
    - superata: una seconda `propose_card` per lo stesso pasto.
- [ ] **Step 2: Falliscono** (il comando di pytest con quei file).
- [ ] **Step 3: Il codice.**
  1. In `delete_ingredient_if_unused`, dopo il ciclo dei modelli, una `select(ChangeCardRow.id)` con `join` su `ChangeCard`, filtrata su ingrediente e `status == proposed`, con `limit(1)`. La docstring dice perché contano solo le proposte (decisione 6).
  2. In `chat_messages_out`, una query sola sugli `Ingredient` (`id`, `display_name`) per l'unione degli id creati dalle modifiche annullate. `_change_out` riceve i nomi rimasti di quella modifica. `dish_chat_view` passa da lì come oggi.
- [ ] **Step 4: Passano**, poi la suite intera: anche `tests/db/test_ingredient_aliases.py` e i test dell'annullamento dell'import, che usano la stessa funzione.
- [ ] **Step 5: Commit**: `fix(pasti): dopo «Annulla» la chat dice gli ingredienti che restano in Anagrafica; una scheda proposta tiene i suoi ingredienti`.

### Task 4: l'inversa non conta la riga smarcata sulla scheda di un altro pasto

**Files:**
- Modify: `backend/app/services/change_cards.py` (`_list_still_needed` e le docstring sue e di `propose_inverse_card`)
- Test: `backend/tests/services/test_inverse_cards.py`

**Interfaces:**
- Produces: nella query delle altre righe di `_list_still_needed`, una riga conta se la sua scheda è `proposed`, oppure se `ChangeCardRow.applied` è vero, oppure se `ChangeCardRow.editable` è falso («Già in lista.»).

- [ ] **Step 1: I test che falliscono.**
  - `test_una_riga_smarcata_sulla_scheda_di_un_altro_pasto_non_tiene_la_voce_in_lista`, in quest'ordine:
    1. la scheda di B propone il pesto in lista (riga modificabile e spuntata);
    2. si applica con `RowOverride(riga_b.id, checked=False)`: la riga ha `applied` falso, e il pesto non è in lista;
    3. la scheda di A mette il pesto in lista, e si applica;
    4. `delete_meal(A)`.

    L'inversa ha `[("unlist", "Pesto")]`, con `checked` vero.
  - `test_una_riga_smarcata_su_una_scheda_ancora_proposta_tiene_la_voce`: B propone il pesto **dopo** che A l'ha messo in lista, e B resta proposta. Eliminato A, nessuna inversa. È il caso `applicata_b=False` di oggi, scritto apposta perché il Review Focus 4 lo nomina.
  - `test_l_inversa_non_toglie_dalla_lista_cio_che_serve_a_un_altro_pasto` (i due casi) resta com'è e deve passare.
- [ ] **Step 2: Falliscono**: il comando di pytest con `tests/services/test_inverse_cards.py`. Expected: il primo test non trova nessuna inversa.
- [ ] **Step 3: Il codice.** Una condizione `or_(…)` nella `where` di oggi, dopo quella di `NO_LONGER_FINISHED_NOTE`, con un commento che cita la decisione 5. La docstring di `_list_still_needed` dice che una riga smarcata da Mattia su una scheda applicata non conta.
- [ ] **Step 4: Passano**, poi `tests/services/test_change_cards.py`, `tests/api/test_change_cards.py`, e la suite intera.
- [ ] **Step 5: Commit**: `fix(pasti): nell'inversa una riga di lista smarcata sulla scheda di un altro pasto non tiene la voce in lista`.

### Task 5: il vettore della ricetta fuori dal lucchetto del pasto

**Files:**
- Modify: `backend/app/services/meal_recipes.py` (`write_meal_recipe`, `undo_recipe_change`)
- Test: `backend/tests/db/test_meal_lock.py`

**Interfaces:**
- Produces: nessuna firma nuova. `write_meal_recipe` legge il pasto e la ricetta senza lucchetto, decide `new_text` e, se serve, calcola il vettore. Poi prende `lock_meal` e rifà la decisione. `undo_recipe_change` calcola il vettore prima di `lock_meal`, se `change.changed["title"] or change.changed["description"]` e la modifica non ha creato la ricetta.

- [ ] **Step 1: I test che falliscono**, con `maker`, `dati` e lo schema di `test_salvare_a_mano_mentre_la_coda_scrive_non_lascia_orfane`, che sostituisce `embedding_for` con `monkeypatch`, qui su `app.services.meal_recipes`. Il finto apre una seconda sessione e prova `SELECT id FROM meals WHERE id = :id FOR UPDATE NOWAIT`. Annota se riesce, poi rilascia con un rollback e torna un vettore fisso.
  - `test_scrivere_la_ricetta_calcola_il_vettore_col_pasto_libero`: `write_meal_recipe` su un pasto senza ricetta → il finto è chiamato una volta, col pasto libero, e la ricetta ha il vettore del finto.
  - `test_annulla_calcola_il_vettore_col_pasto_libero`: una seconda modifica che cambia il titolo, poi `undo_recipe_change` → il finto è chiamato una volta col titolo di prima, col pasto libero.
  - `test_annulla_senza_titolo_cambiato_non_calcola_il_vettore`: il finto non è chiamato.
  - `test_la_ricetta_cambiata_fra_la_lettura_e_il_lucchetto_ha_il_vettore_giusto`:
    1. la ricetta del pasto ha già titolo e descrizione della bozza, quindi la prima decisione dice che il vettore non serve;
    2. un finto di `lock_meal` (con `monkeypatch` su `app.services.meal_recipes.lock_meal`), prima di chiamare quello vero, cambia il titolo della ricetta in un'altra sessione e committa;
    3. dopo la scrittura, il titolo è quello della bozza e il vettore è quello del finto di `embedding_for`.
- [ ] **Step 2: Falliscono**: il comando di pytest con `tests/db/test_meal_lock.py`. Expected: il `NOWAIT` fallisce nei primi due test.
- [ ] **Step 3: Il codice.** In `write_meal_recipe`, la lettura senza lucchetto usa `get_recipe` come oggi. Il vettore calcolato prima vale solo se la decisione sotto il lucchetto è la stessa. Un commento nomina la corsa rara (decisione 7). I controlli di oggi (`allowed_recipe_ids`, `refuse_if_no_recipe_here`, `expected`) restano tutti **dopo** il lucchetto, nello stesso ordine.
- [ ] **Step 4: Passano**, con `tests/db/test_meal_lock.py`, `tests/services/test_meal_recipes.py`, `tests/services/test_recipe_jobs.py`, poi la suite intera.
- [ ] **Step 5: Commit**: `fix(pasti): il vettore della ricetta si calcola fuori dal lucchetto del pasto`.

### Task 6: «Continua» e gli ingredienti che restano, a video

**Files:**
- Modify: `frontend/src/domain/types.ts` (`ChatMessage.can_continue?: boolean`, `RecipeChange.kept_note?: string | null`; facoltativi per le risposte vecchie in cache)
- Modify: `frontend/src/features/meal-chat/ChatThread.tsx` (`onContinue?: () => void`, `CONTINUE_TEXT`, `ChangeLine`, il commento «niente «Riprova»»)
- Modify: `frontend/src/features/meal-chat/DishChat.tsx`, `frontend/src/features/planning/PlanningScreen.tsx` (`onContinue={() => sender.sendText(CONTINUE_TEXT)}`, solo dove c'è `ChatComposer`)
- Test: `frontend/src/features/meal-chat/ChatThread.test.tsx`, `frontend/src/features/meal-chat/DishChat.test.tsx`, il test di `PlanningScreen`

**Interfaces:**
- Consumes: `can_continue` (Task 2), `kept_note` (Task 3), `useChatSender().sendText`.
- Produces: `export const CONTINUE_TEXT = "Continua da dove ti sei fermato."`.

- [ ] **Step 1: I test che falliscono.**
  - `ChatThread.test.tsx`, «la risposta interrotta che si può continuare ha Continua»: un messaggio di Claude `sent`, con l'avviso dei troppi passaggi e `can_continue: true` → si leggono il testo, l'avviso e un pulsante «Continua». Premuto, `onContinue` è chiamato una volta. Nessun «Riprova».
  - «senza can_continue niente Continua»: il test di oggi «una risposta interrotta dai troppi passaggi mostra il testo e l'avviso, senza Riprova» resta com'è, e in più nessun «Continua».
  - «Continua aspetta mentre la chat è occupata»: con `busy`, il pulsante è nello stato `busy` di `Button`.
  - «sotto una modifica annullata, gli ingredienti che restano»: una modifica con `undone: true` e `kept_note` «Resta in Anagrafica: Spinaci novelli.» → la riga «Ricetta scritta: … — annullata» e sotto la frase. Con `kept_note: null`, nessuna frase.
  - `DishChat.test.tsx`, «Continua manda il messaggio fisso»: la chat letta ha come ultimo messaggio una risposta interrotta con `can_continue: true`. Premuto «Continua», il `POST` dei messaggi ha corpo esattamente `{ text: "Continua da dove ti sei fermato." }`, senza `retry_of`.
  - Il test di `PlanningScreen`: lo stesso, sulla pianificazione.
- [ ] **Step 2: Falliscono**: `npx vitest run --maxWorkers=4 src/features/meal-chat src/features/planning`.
- [ ] **Step 3: Il codice.**
  - «Continua» sta sotto l'`Alert` della risposta interrotta (decisione 11).
  - `kept_note` è un `<p>` sotto la riga della modifica, con le classi della riga (`text-sm text-ink-soft`).
  - Nessun colore nuovo, nessun token nuovo.
- [ ] **Step 4: Passano**, poi `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- [ ] **Step 5: Commit**: `pasti: «Continua» sotto la risposta interrotta, e gli ingredienti che restano in Anagrafica dopo «Annulla»`.

### Task 7: e2e, la verifica, la spec, il backlog, il report

- [ ] **Step 1: e2e intera**, con i comandi delle Global Constraints, dentro il limite di carico. Expected: tutto verde, con le prove nuove dello Step 2. **Annota** il numero.
- [ ] **Step 2: Nel browser vero.** Lo stack e2e non ha Claude, quindi la risposta interrotta si semina.
  - Aggiungi a `backend/tests/e2e_planning.py` un sottocomando suo, `interrupted`. Scrive in una conversazione del piatto, nuova e su un pasto «e2e-plan» suo, un messaggio di Mattia e una risposta di Claude `sent` con l'avviso dei troppi passaggi: le due righe che scrive `_reply`. `clean` li toglie.
  - Lo stato che vedono le altre prove non cambia.
  - In `frontend/e2e/pianificazione.spec.ts`, «la risposta interrotta ha Continua»: sulla pagina del pasto, si leggono l'avviso e «Continua». Premuto, compare il rifiuto «Claude non è collegato: manca la chiave API sul server.» e il messaggio non si perde (il comportamento di oggi senza Claude).
  - In `style.spec.ts`, **«la risposta interrotta con Continua a 375 px, nei due temi»**: `testiIlleggibili(page)` è `[]`, `scrollWidth <= clientWidth`, e «Continua» è visibile e alto almeno 44 px.
  - Nel `finally`, `clean`. Se il seme separato non si può fare senza toccare lo stato delle altre prove, salta queste due prove, fai la verifica a mano con uno screenshot a 375 px nei due temi, e scrivilo nel report.
- [ ] **Step 3: La spec** (`docs/superpowers/specs/2026-11-12-pasti-claude-design.md`).
  - In §6.3, dopo il punto su «Annulla» e gli ingredienti creati, aggiungi: «Sotto la modifica annullata la chat dice quali restano («Restano in Anagrafica: …»); un ingrediente nominato da una scheda dei cambi ancora proposta conta come usato (deciso da Mattia il 2026-11-23).»
  - In §9, aggiungi il punto: «una risposta fermata dai troppi passaggi resta con il suo avviso e il pulsante «Continua», che manda «Continua da dove ti sei fermato.»; al giro dopo Claude sa che si era interrotta (deciso da Mattia il 2026-11-23).»
  - In §6.2, al punto della scheda inversa, aggiungi: «Una riga di lista che Mattia ha smarcato applicando la scheda di un altro pasto non tiene la voce in lista (deciso da Mattia il 2026-11-23).»
- [ ] **Step 4: Il backlog** (`next-steps.md`, sul ramo). Cerca le voci per il testo, non per numero di riga.
  - Le tre voci costruite passano a `fatto <data di oggi>` in «Fatti (recenti)», ognuna con « — risolta col piano `2026-11-23-pasti-quarto-giro.md` → branch night/pasti-quarto-giro (da revisionare)».
  - La voce «Pasti: i legami di avanzo già fuori dalla finestra di 3 giorni…» è già `fatto` dal 2026-11-23, chiusa nella fase giorno: non toccarla.
  - Aggiorna la data in testa.
  - Commit: `next-steps: pasti, quarto giro, fatto`.
- [ ] **Step 5: Il report**, `docs/night-reports/<data di oggi>.md` sul ramo (in fondo, se c'è già). Dentro:
  - il ramo e i conti veri contro la Preparazione;
  - le funzioni di `meal_recipes.py` da cucire con i due piani del 2026-11-22;
  - le decisioni 6–11 che Mattia può voler rivedere, in particolare il singolare «Resta in Anagrafica» (9), la frase su ogni modifica annullata (10) e la corsa rara del vettore sotto il lucchetto (7);
  - l'esito dello Step 2;
  - la sezione «Dopo il deploy (solo Mattia)»: sul telefono, una risposta interrotta ha «Continua» e Claude riprende dal punto giusto; «Annulla» di una «Ricetta scritta» con un ingrediente nuovo dice «Resta in Anagrafica: …».

  Niente push, niente merge, niente deploy.

## Fuori scope

- Un tetto di passaggi più alto per «Continua» (deciso da Mattia: lo stesso tetto).
- Cancellare davvero la «Ricetta scritta» annullata o i suoi ingredienti (deciso da Mattia: restano), e ogni migrazione.
- I legami d'avanzo fuori finestra (decisione 4: nessun codice).
- Il lucchetto e la versione nel `PUT`/`PATCH` delle ricette, e la ricetta a mano che vince: piani `2026-11-22-ricetta-pasto-lucchetto.md` e `2026-11-22-ricetta-a-mano-vince.md`.
- I prompt di Claude, salvo la riga della cronologia.

## Comandi di verifica

- Backend: il comando di pytest delle Global Constraints, tutto verde, con i test nuovi.
- Frontend, da `<worktree>/frontend`: `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- e2e: la suite intera, verde.
- `git -C <worktree> diff master --stat` tocca solo i file dei task, più `next-steps.md`, la spec e il report.
