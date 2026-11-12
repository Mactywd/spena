# Pasti con Claude: la pianificazione e le schede dei cambi — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** «Pianifica con Claude» apre una chat a tutta pagina dove Claude propone i pasti come una scheda («Metti nella settimana»), nei due giri della spec: con quello che c'è (pasti subito ufficiali) e prima della spesa (bozza che compila la lista, poi ufficializzazione dopo «Sistema la spesa»). I pasti ufficiali ricevono la ricetta da Claude, uno per uno, in sottofondo. Ogni cambio a dispensa e lista passa da una **scheda dei cambi** che Mattia corregge e applica, anche dalla chat del piatto; quando un pasto ufficiale si toglie, si sostituisce o va fuori casa, spena propone la **scheda inversa**, anche senza Claude.

**Architecture:** la migrazione `0022` aggiunge le proposte di pasti (`meal_proposals`), le schede dei cambi (`change_cards`, `change_card_rows`), il posto di partenza della conversazione e lo stato della ricetta chiesta a Claude sul pasto. Le schede sono un servizio a sé (`app/services/change_cards.py`): costruzione, applicazione in una transazione con `SELECT … FOR UPDATE`, scarto, righe aggiunte a mano, scheda inversa. Le proposte e la loro messa nella settimana stanno in `app/services/planning.py`. Il giro della chat del piano 3 si generalizza (`run_chat_turn` con un `TurnSpec`): la chat del piatto e quella di pianificazione sono due specie dello stesso giro. Le ricette dell'ufficializzazione le scrive una coda nel processo (`app/services/recipe_jobs.py`), un pasto alla volta, ognuno in una transazione sua con `write_meal_recipe`. Nel frontend: `features/planning/`, `features/change-cards/`, e i posti lasciati dal piano 2 in `WeekScreen`, `NewMealScreen`, `MealScreen`.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Alembic, pytest su Postgres vero; `claude-agent-sdk==0.2.180` già nel ramo (piano 3), mai chiamato nei test; React 19, TypeScript, Tailwind 4, TanStack Query, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-12-pasti-claude-design.md` (approvata da Mattia il 2026-11-12). Questo piano copre tutto quello che resta: §5.1 («Pianifica con Claude», «Chiedilo a Claude»), §5.2 per intero, §6.2 per intero (anche dalla chat del piatto), §7 per la parte di pianificazione, §9 per la pianificazione e la generazione delle ricette, §11 per la chiusura. È il **piano 4 di 4**, l'ultimo della catena. Si leggono insieme i tre piani da cui parte: `docs/superpowers/plans/2026-11-12-utensili.md`, `docs/superpowers/plans/2026-11-12-pasti-settimana.md`, `docs/superpowers/plans/2026-11-12-pasti-claude.md`.

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/pasti-pianificazione`, ramo `night/pasti-pianificazione`, creato da **`night/pasti-claude`** (piano 3). Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì, mai dalla radice del checkout principale, che non si tocca (le modifiche non committate che ci trovi sono dell'utente). **Nessun push, nessun merge, nessun deploy. Mai `git stash`. Niente letture o scritture sulla produzione. Nessuna chiamata vera a Claude: niente token, niente rete.**
- **Leggi ogni file com'è sul ramo prima di cambiarlo.** Il ramo di partenza ha le modifiche dei piani 1, 2 e 3. Il piano descrive le modifiche ai file esistenti contro ancore riconoscibili (una funzione, una costante, un elemento JSX), mai contro numeri di riga. Dove il piano dà un elenco di firme per un file che non c'è, è un file nuovo.
- **I nomi dei piani 1–3 si usano così come sono.** Piano 2: `Meal`, `MealSlot`, `MealStatus`, `get_meal`, `meal_at`, `meals_between`, `create_meal`, `update_meal`, `delete_meal`, `release_recipe`, `check_can_take_recipe`, `MealRefusal`/`MealRefusalCode`, `meal_out`, `MealOut`, `MealRefOut`, `meal_refusal_response`, `WeekScreen`, `NewMealScreen`, `MealScreen`, `longDayLabel`, `SLOT_LABELS`, `fetchMeal`, `updateMeal`, le chiavi `["meals", …]`. Piano 3: `Conversation`, `ConversationMessage`, `ConversationKind.PLANNING`, `MessageRole`, `MessageStatus`, `RecipeChange`, `write_meal_recipe`, `MealRecipeDraft`, `ClaudeClient.run`, `TurnFinished`/`TurnFailed`/`TextDelta`, `FailureKind`, `failure_notice`, `claude_configured`, `get_claude_client`, `COMMON_PROMPT`, `DISH_PROMPT`, `DISH_PANTRY_RULE`, `dish_system_prompt`, `render_turn_prompt`, `DishContext`, `HistoryItem`, `TurnContext`, `read_tools`, `write_recipe_tool`, `dish_tools`, `SPENA_SERVER`, `run_dish_turn`, `dish_chat_view`, `ChatEvent`, `TurnRegistry`, `get_turn_registry`, `HISTORY_MESSAGES`, `pending_is_stale`, `BUSY_NOTICE`, `LlmCallSite.MEAL_CHAT`, `PLAN_CALL_SITES`, `CALL_SITE_LABELS`, `ChatMessageOut`, `DishChatOut`, `ChatMessageIn`, `FakeClaude` (`Say`, `UseTool`, `Finish`, `Fail`, `Hang`), `apiStream`, `readSse`, `ChatStreamEvent`, `ChatThread`, `DishChat`, `useDishChat`, `dishChatKey`. **Se un nome sul ramo è diverso** da come lo scrivono quei piani, vale il codice: usalo e scrivilo nel report (i report dei piani 1–3 in `docs/night-reports/` sul ramo dicono già le differenze: leggili per primi).
- **Le interfacce dei piani 1–3 che questo piano cambia** sono elencate tutte nel blocco «Cambi alle interfacce dei piani precedenti» (sotto «Dipendenze»), ognuna col suo perché. Nessun altro cambio.
- **Decisione fondante 1.** La dispensa resta senza quantità: le schede cambiano solo i tre stati, con `set_status`, e scrivono in lista con `add_item`. **Decisione fondante 2.** Ogni ricetta scritta da Claude passa da `write_meal_recipe` (quindi dall'imbuto).
- **Claude non scrive mai in dispensa né in lista** (anti-obiettivo §2): propone una scheda, Mattia la applica. Nessuno strumento di Claude chiama `set_status`, `add_item`, `patch_item`.
- **Prima lezione di `CLAUDE.md`.** I test non usano l'SDK né la rete: `FakeClaude` chiama **gli stessi oggetti strumento** che la produzione costruisce. Le due logiche nuove che hanno un gemello (il giro della pianificazione e quello del piatto; la scrittura in lista della scheda e quella della lista) hanno **una copia sola**: `run_chat_turn` e `add_item`.
- **Il frontend non calcola logica di dominio.** Lo stato «ora» di una voce, cosa fa una riga della proposta su un posto occupato, chi può chiedere la ricetta, se la ricetta è in preparazione, se la conversazione è conclusa, i titoli delle schede, il testo del messaggio dopo «Metti nella settimana»: tutto nel backend.
- **Mai un vicolo cieco.** Senza Claude: le bozze si ufficializzano a mano con la scheda vuota da compilare; un pasto senza ricetta ha «Chiedi la ricetta a Claude», «Scrivi la ricetta» e «Scegli dal ricettario»; la scheda inversa nasce da spena; la dispensa si cambia sempre dalla sua schermata.
- **Colore e primitive** come nei piani 1–3: solo token di `frontend/src/index.css`, **nessun token nuovo**; `grep -rn "emerald\|neutral-" frontend/src` resta vuoto; ogni testo sopra 4,5:1 nei due temi (misurato da `frontend/e2e/style.spec.ts`); primitive da `frontend/src/components/ui/`, `Button` non cambia; bersagli alti almeno 44 px (`min-h-11`); a 375 px niente scorre di lato. Gli stati a video si dicono con `STATUS_LABELS` di `frontend/src/features/pantry/statusLabels.ts` («Disponibile», «Quasi finito», «Finito»).
- Le parole a video sono in italiano e **si copiano esatte** da questo piano (fra «»; ‹…› è un valore, non un carattere da copiare). Gli identificatori in inglese, i commenti in italiano. I testi dei prompt del Task 6 sono copia fissata.
- **Il type check è `npm run typecheck`**, mai `tsc --noEmit`. Controlli del frontend, da `<worktree>/frontend`: `npx vitest run`, `npm run typecheck`, `npm run lint`, `npm run build`. Nei test dei componenti si usa `createTestQueryClient`.
- **Backend su Postgres vero**: `spena-db-1` (porta 5433), con il database di questo ramo, `spena_test_pasti_pianificazione`. Mai `docker compose up` dal worktree, mai `-f docker-compose.prod.yml`. Si usa il `.venv` del checkout principale (ha già `claude-agent-sdk==0.2.180` dal piano 3). Il comando di pytest, da `<worktree>/backend`:
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_pasti_pianificazione \
    PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
- **e2e** sullo stack `spena-e2e`, con gli stessi comandi e le stesse cautele dei piani 2 e 3 (il `.env` copiato da `.env.example` e cancellato alla fine; `-p spena-e2e` e `-f docker-compose.e2e.yml` in ogni comando; se lo stack c'è e non l'hai alzato tu, aspetta che sparisca):
  ```bash
  cp .env.example .env
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed --con-ricette
  (cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
  rm .env
  ```
- Nessuna dipendenza nuova, nel backend e nel frontend. Una migrazione sola, la `0022`.

### Preparazione (una volta, prima del Task 1)

- [ ] **Il ramo di partenza.** Il piano 3 deve aver lasciato `night/pasti-claude` con la sua migrazione e i pezzi che questo piano consuma:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify night/pasti-claude
  git ls-tree -r --name-only night/pasti-claude -- backend/alembic/versions | grep 0021
  git show night/pasti-claude:backend/app/services/meal_recipes.py | grep -c "async def write_meal_recipe"
  git show night/pasti-claude:backend/app/services/claude/tools.py | grep -cE "def (read_tools|write_recipe_tool|dish_tools)"
  git show night/pasti-claude:backend/app/services/claude/prompts.py | grep -c "DISH_PANTRY_RULE"
  git show night/pasti-claude:backend/app/services/meal_chat.py | grep -c "async def run_dish_turn"
  ls .worktrees/pasti-pianificazione 2>&1 | head -1
  ```
  Expected: un hash (**annotalo**: è `BASE` del Task 14); un file `0021_….py`; `1`; `3`; almeno `1`; `1`; `No such file or directory`. **Se `night/pasti-claude` non esiste** o non ha la `0021`, non creare niente: fermati e scrivi nel messaggio finale della notte che il piano 4 non è partito perché manca il piano 3. Se un `grep -c` dà meno del previsto, il piano 3 è finito a metà: leggi il suo report in `docs/night-reports/` sul ramo; se mancano pezzi che questo piano consuma (blocco «Dipendenze»), fermati allo stesso modo. Se `.worktrees/pasti-pianificazione` esiste già, qualcuno ha cominciato: fermati e scrivilo.
- [ ] **Il database dei test di questo ramo**:
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_pasti_pianificazione WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_pasti_pianificazione'
  ```
- [ ] `cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund`.
- [ ] **Il worktree**, con `node_modules` collegato e nessun `.env`:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/pasti-pianificazione -b night/pasti-pianificazione night/pasti-claude
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/pasti-pianificazione/frontend/node_modules
  ```
- [ ] **La revisione da cui parte la `0022`**, da `<worktree>/backend`:
  ```bash
  DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_pasti_pianificazione \
    PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" alembic heads
  ```
  Expected: una riga sola, la `0021` del piano 3. **Annota l'identificatore**: è il `down_revision` del Task 1. Se le teste sono più d'una, fermati con «attende: le teste di Alembic su night/pasti-claude sono più d'una».
- [ ] La voce «Sezione Pasti» di `next-steps.md` resta `in corso` (se non lo è, cambia solo lo stato fra parentesi quadre). In coda alla riga si aggiunge ` · piano 4 di 4 (pianificazione e schede dei cambi) in corso su night/pasti-pianificazione`, poi `git commit -m "next-steps: sezione Pasti, piano 4 (pianificazione e schede dei cambi) in corso"`.
- [ ] **La linea di partenza** (vitest e pytest dal worktree, come nei piani 2 e 3): tutto verde. **Annota** `N_file`, `N_vitest` e `N_pytest`. Se non è verde, fermati: va nel report.

---

## Obiettivo e contesto

Oggi Mattia pianifica con la skill `pasti` in due modi: qualche pasto con quello che c'è, o tutta la settimana prima della spesa, chiudendo con una tabella di cambi che approva in chat. I piani 1–3 hanno portato in spena gli utensili, la settimana a mano, le ricette fuori dal ricettario, il client di Claude e la chat del piatto. Questo piano chiude il giro (spec §10, punto 4): la pianificazione con Claude, la bozza e l'ufficializzazione, le ricette scritte dopo l'ufficializzazione, le schede dei cambi al posto della tabella della skill, e la scheda inversa. Alla fine il reMarkable e la skill escono dal giro, ma la skill resta finché Mattia non ha provato tutto in produzione (§11).

## Decisioni prese

Della spec (Mattia; il perché è nella spec):

1. **La chat di pianificazione è a tutta pagina**, nello stile della chat del piatto; «Pianifica con Claude» in fondo alla settimana riapre l'ultima conversazione non conclusa, e c'è sempre «Nuova» (§5.2).
2. **I due giri**: con quello che c'è → pasti subito ufficiali, ricette e scheda dei cambi alla dispensa; prima della spesa → **bozza** che compila la lista (scheda con le sole righe della lista), poi **ufficializzazione** al ritorno, con la dispensa già sistemata (§5.2).
3. **La proposta è una scheda** posto per posto, con piatto e accompagnamenti; si discute a parole e Claude ne manda una nuova; «Metti nella settimana» la mette; un posto occupato si sostituisce solo con una conferma (§5.2).
4. **Le ricette si scrivono dopo l'ufficializzazione**, una per pasto, con «ricetta in preparazione»; se una non arriva, il pasto resta con «Chiedi la ricetta a Claude» e «Scrivi la ricetta» (§5.2).
5. **Una bozza si ufficializza anche a mano**, pasto per pasto: il pasto diventa ufficiale senza ricetta e spena propone la scheda vuota da compilare (§5.2).
6. **La scheda dei cambi** ha le colonne voce, ora, diventa; una casella per riga; lo stato si corregge; «Applica» fa tutto in una transazione, con `set_status` e l'aggiunta in lista di sempre, senza duplicati; le voci finite sono già proposte in lista; per una bozza solo righe della lista (§6.2).
7. **La chat del piatto propone la stessa scheda** quando una modifica cambia cosa si usa (§6.2).
8. **La scheda inversa**: ogni scheda applicata si conserva legata ai suoi pasti con lo stato di prima di ogni voce; quando un pasto ufficiale si cancella, si sostituisce o diventa fuori casa, spena propone la scheda inversa, anche senza Claude; spostarlo non propone niente (§6.2).
9. **Le regole sugli stati** della skill entrano nel prompt: una porzione → `finished`, confezione grande com'è, sugo appena aperto → `low`, sugo `low` avviato e non da ricomprare (§6.2, §7).
10. **Il prompt di pianificazione**: quadro della settimana per gruppi, sale stimato con la tabella della skill (già in `COMMON_PROMPT`), precedenza a scadenze e sughi avviati, per ogni proposta perché aiuta l'equilibrio; sforzo `high` (§7).

Di questo piano (Claude, su delega: non funzionali o reversibili; Mattia le rivede nel report):

11. **Claude propone con due strumenti**, `propose_meals` e `propose_changes`. La proposta e la scheda nascono quando Claude le chiama, legate al giro, e restano anche se il giro poi fallisce (§9: il limite del piano a metà non butta via una proposta già fatta).
12. **Una proposta nuova sostituisce quelle aperte** della stessa conversazione (`superseded`). Una proposta messa nella settimana non si rimette (`proposal_placed`): il doppio tocco su «Metti nella settimana» non duplica niente.
13. **Che cosa fa una riga su un posto occupato** lo decide il backend: posto vuoto → pasto nuovo; proposta ufficiale su una **bozza** → la bozza diventa ufficiale (stesso pasto, piatto e accompagnamenti aggiornati), **senza conferma**, perché è l'ufficializzazione; qualunque altro occupante (ufficiale, fuori casa, bozza sotto una proposta di bozza) → serve la conferma, e la sostituzione passa da `create_meal(replace=True)` del piano 2 (quindi la scheda inversa del vecchio, se ne ha). Senza conferma, la messa si rifiuta **prima di scrivere qualunque cosa** con l'elenco degli occupanti. Le proposte non sono mai nel passato (giorno prima di oggi, nel giorno di Roma) e non creano avanzi né fuori casa.
14. **Dopo «Metti nella settimana» il messaggio a Claude lo manda il telefono**: la risposta della messa porta `follow_up` (un testo fisso del backend, per esempio «Ho messo nella settimana: martedì 11 novembre · cena, Frittata di spinaci. Mandami la scheda dei cambi.») e il frontend lo invia come un messaggio qualsiasi. Così passa dallo stesso streaming, dallo stesso 503 e dallo stesso «Riprova»; se Claude non c'è, il testo resta nel campo e i pasti sono comunque nella settimana.
15. **Le ricette le scrive una coda nel processo** (`RecipeJobs`), **un pasto alla volta e una sola coda alla volta**: un'ufficializzazione di sette pasti non lancia sette processi di Claude Code. Ogni pasto è un giro suo (`meal_recipe`, sforzo `medium`, `RECIPE_MAX_TURNS = 12`, tempo massimo `claude_reply_timeout_seconds`), con gli strumenti di lettura e `write_recipe` legato a quel pasto in **sola creazione** (`create_only`): se nel frattempo Mattia ha scritto la ricetta a mano, Claude non la tocca. Ogni pasto si committa da solo. Un guasto che vale per tutti (limite del piano, token, Claude non collegato) ferma la coda e scrive l'avviso su ogni pasto rimasto, senza altre chiamate; un guasto del singolo (tempo massimo, errore) passa al pasto dopo.
16. **«Ricetta in preparazione» è vera solo se la coda ha davvero quel pasto.** Il pasto ha `recipe_requested_at` e `recipe_notice`; un pasto chiesto ma non più nella coda (il container è ripartito) diventa, alla prima lettura, «La ricetta non è arrivata: chiedila di nuovo a Claude o scrivila a mano.», scritto anche nel database. La settimana e il piatto si rileggono ogni 3 s finché qualcosa è in preparazione.
17. **Il giro della ricetta riceve la conversazione** in cui il pasto è stato deciso (gli ultimi `HISTORY_MESSAGES` messaggi), così «il merluzzo non c'era, ho preso il salmone» arriva anche alla ricetta.
18. **La scheda ha una riga per voce di dispensa e una per ingrediente in lista.** Se Claude nomina due volte la stessa voce (due pasti usano il parmigiano), le righe si fondono: lo stato più consumato vince (`finished` su `low` su `available`) e i pasti si uniscono. Ogni riga sa **per quali pasti** serve (`meal_ids`), di norma tutti quelli della scheda.
19. **Le righe della lista**: una voce di dispensa che diventa `finished` porta con sé, già spuntata, la riga «in lista» del suo ingrediente (con il nome del prodotto, come `restock`). Una che diventa `low` **no**: è la regola del sugo avviato fatta struttura, non solo prompt. Una riga per un ingrediente già in lista (da comprare o nel carrello) resta visibile, non spuntabile, con «già in lista». All'applicazione ogni riga della lista passa da `add_item`, che non duplica nemmeno ciò che è entrato in lista dopo la proposta.
20. **«Ora» si legge dal vivo** finché la scheda è proposta (lo stato della voce adesso, non quello del momento della proposta); da applicata mostra lo stato di prima registrato.
21. **L'applicazione** blocca la scheda (`SELECT … FOR UPDATE`) e controlla che sia ancora `proposed`: una seconda applicazione, anche contemporanea, è un 409 `card_applied` che porta la scheda com'è, e il frontend la mostra applicata con «La scheda era già applicata.». Una voce sparita o archiviata nel frattempo si salta, con la sua nota, e il resto si applica.
22. **La scheda inversa** nasce dentro `delete_meal` e dentro `update_meal` quando `away` diventa vero, **prima** del cambio, solo per un pasto ufficiale. Per ogni riga applicata (e non già annullata) di una scheda in avanti che serve a quel pasto:
    - se la riga serve anche a un altro pasto della scheda che è ancora ufficiale e non fuori casa, si salta (la usa ancora lui);
    - riga di dispensa: si propone «ora → stato di prima», spuntata solo se la voce è ancora nello stato che la scheda le aveva dato; se nel frattempo è cambiata, non spuntata con «Cambiata dopo la scheda: controlla prima di rimetterla.»; se è già nello stato di prima, niente; se la voce non c'è più, niente;
    - riga della lista che la scheda aveva **davvero aggiunto**: se la voce è ancora da comprare, «via dalla lista» spuntata; nel carrello, non spuntata con «È già nel carrello.»; sistemata o tolta (comprata di nuovo nel frattempo), niente.
    Una scheda inversa senza righe non nasce. Applicarla segna le righe d'origine come annullate (`reversed_at`), così due inverse non rimettono due volte. Le schede in avanti ancora **proposte** di quel pasto perdono le righe che servivano solo a lui, e si scartano da sole se restano vuote e senza pasti.
23. **La scheda vuota dell'ufficializzazione a mano** nasce nella rotta `PATCH /api/v1/meals/{id}` quando `status` passa da `draft` a `official` (non nel servizio: la messa nella settimana ufficializza le bozze con lo stesso servizio, e lì la scheda la manda Claude). Il frontend, dopo «Rendi ufficiale», apre la scheda.
24. **Dove si trovano le schede proposte**: in testa alla settimana un riquadro «Schede dei cambi da applicare» con tutte quelle `proposed`; nel piatto un collegamento «Scheda dei cambi da applicare» se una riguarda quel pasto; nella chat, sotto il messaggio del giro che l'ha proposta; e la pagina `/pasti/cambi/:id`.
25. **Il posto di partenza** («Chiedilo a Claude» sul posto vuoto) si scrive sulla conversazione (`focus_day`, `focus_slot`): riapre l'ultima non conclusa e la punta lì, o ne crea una. Il campo si precompila con «Cosa mi proponi per ‹giorno lungo› a ‹pranzo|cena›?», che Mattia può cambiare.
26. **Una conversazione di pianificazione è conclusa** (calcolato, non salvato) quando ha almeno una proposta messa, nessuna proposta aperta, nessuna sua scheda `proposed`, una sua scheda applicata o scartata dopo l'ultima messa, e nessuna bozza messa da lei ancora bozza da oggi in avanti. Così il giro della bozza resta aperto fino all'ufficializzazione, e «Pianifica con Claude» riporta Mattia lì dopo la spesa.
27. **Le sezioni sul piano** in `llm_calls`: `meal_planning` («Pianificazione dei pasti») e `meal_recipe` («Ricette dei pasti»), in `PLAN_CALL_SITES` accanto a `meal_chat`.
28. **«Riprova» porta con sé quello che il giro fallito aveva prodotto**: proposte, schede e modifiche della ricetta legate al messaggio fallito passano al messaggio nuovo prima che il vecchio si cancelli. Senza questo, una proposta fatta prima del limite del piano sparirebbe dalla chat al primo «Riprova».

## Criteri di accettazione

- [ ] La `0022` sale e scende, e i vincoli di proposte, schede e righe tengono.
- [ ] Una scheda si costruisce da quello che Claude propone (righe fuse, finite già in lista, «già in lista», nessuna riga di dispensa per una bozza), si corregge, si applica una volta sola in una transazione con `set_status` e `add_item`, si scarta, riceve righe a mano.
- [ ] Togliere, sostituire o mandare fuori casa un pasto ufficiale con una scheda applicata propone la scheda inversa con le regole della decisione 22; spostarlo no.
- [ ] Una proposta si mette nella settimana (pasti nuovi, bozze ufficializzate, sostituzioni solo con conferma, una volta sola), e le ricette dei pasti ufficiali arrivano una per pasto; un'interruzione a metà lascia ogni pasto usabile.
- [ ] La chat di pianificazione trasmette come quella del piatto, con le schede di proposta e di cambi sotto i messaggi; la chat del piatto propone la sua scheda; il limite del piano a metà lascia la proposta e «Riprova».
- [ ] Nell'app: «Pianifica con Claude», «Chiedilo a Claude», «Nuova», «Metti nella settimana» con la conferma, «Ricetta in preparazione», «Chiedi la ricetta a Claude», la scheda dei cambi con «Applica» e «Scarta», «Rendi ufficiale» che apre la scheda vuota, il riquadro delle schede da applicare. Nel browser vero, a 375 px nei due temi, ogni testo sopra 4,5:1 e niente scorre di lato.
- [ ] Tutti i test di oggi passano; cambiano solo i test dei piani precedenti nominati nel blocco «Cambi alle interfacce».
- [ ] `CLAUDE.md`, `README.md` (se serve), `docs/prossimi-passi.md`, `next-steps.md` e il report aggiornati; la voce «Sezione Pasti» è `fatto … (da revisionare)` con i quattro rami (Task 14).

## Comandi di verifica

Da `<worktree>/backend`: il comando di pytest. Da `<worktree>/frontend`: `npx vitest run`, `npm run typecheck`, `npm run lint`, `npm run build`. Dalla radice di `<worktree>`:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -rn "DISH_PANTRY_RULE" backend/app frontend/src
grep -rn "set_status\|add_item\|patch_item" backend/app/services/claude
grep -rn "from claude_agent_sdk import\|import claude_agent_sdk" backend/app --include=*.py
git diff night/pasti-claude --stat -- backend/alembic/versions
```

Expected: il primo vuoto; il secondo vuoto (sostituita da `CHANGES_RULE`); il terzo vuoto (Claude non scrive mai in dispensa né in lista); il quarto solo i tre file del piano 3 (`client.py`, `tools.py`, `check_claude.py`); l'ultimo un file solo, `0022_pianificazione.py`. Poi l'e2e intera con i comandi delle Global Constraints.

## Review Focus

Dove un errore costa di più a Mattia. Ogni riga ha il suo test nel task che possiede il codice.

1. **La scheda applicata due volte** (doppio tocco, rete lenta, due schede aperte). La seconda applicazione, anche contemporanea su un'altra connessione, è un 409 `card_applied`; la dispensa cambia una volta e la lista ha una riga sola. Task 2 (`test_applicare_due_volte_e_409_e_non_cambia_niente`), Task 4 (`test_applicare_insieme_da_due_connessioni`), Task 10 (`«Applica» toccato due volte manda una richiesta sola`).
2. **La scheda che propone in lista una voce già in lista.** Alla proposta la riga dice «già in lista» e non si spunta; e se la voce entra in lista dopo la proposta, l'applicazione non la duplica. Task 2 (`test_una_voce_gia_in_lista_non_si_ripropone`, `test_una_voce_entrata_in_lista_dopo_non_si_duplica`).
3. **Un sugo `low` letto come da ricomprare.** Una voce che diventa `low`, o che lo è già, non porta mai una riga «in lista» da sé; la regola è nel prompt. Task 2 (`test_quasi_finito_non_va_in_lista_da_solo`), Task 6 (`test_i_prompt_dicono_le_regole_degli_stati`).
4. **Due pasti che sottraggono la stessa voce.** Nella scheda la voce è una riga sola, con lo stato più consumato e i due pasti; togliendo uno dei due, la scheda inversa non rimette la voce che serve ancora all'altro. Task 2 (`test_due_pasti_sulla_stessa_voce_fanno_una_riga`), Task 3 (`test_l_inversa_non_rimette_cio_che_serve_ancora_a_un_altro_pasto`).
5. **La scheda inversa dopo che la voce è stata comprata di nuovo.** La riga della lista sistemata non si tocca; la voce di dispensa nuova (della spesa) non si tocca; quella vecchia torna allo stato di prima solo se è ancora nello stato della scheda. Task 3 (`test_l_inversa_dopo_una_spesa_nel_frattempo`).
6. **La generazione di N ricette che si interrompe a metà** (limite del piano al secondo di tre pasti, o container che riparte). Il primo pasto ha la ricetta; gli altri due sono nella settimana, senza ricetta, con l'avviso e «Chiedi la ricetta a Claude»; dopo il limite nessun'altra chiamata. Task 8 (`test_il_limite_a_meta_lascia_ogni_pasto_usabile`, `test_una_preparazione_orfana_diventa_un_avviso`).
7. **Il limite del piano raggiunto a metà pianificazione** (§9). La proposta già fatta resta e si mette nella settimana; il messaggio è `failed` con l'avviso e «Riprova»; dopo «Riprova» la proposta è ancora sotto il messaggio. Task 7 (`test_il_limite_a_meta_lascia_la_proposta`, `test_riprova_si_porta_dietro_la_proposta`).

## Fuori scope

- **Ritirare la skill `pasti`**: resta finché la sezione non è in produzione e provata (§11; riga «Dopo il deploy»).
- Colazione e spuntini, l'import del reMarkable, NutriScore, budget, calorie (spec §2).
- Avanzi e pasti fuori casa proposti da Claude: la proposta porta solo piatti; un avanzo o un «Fuori» si scrivono a mano (piano 2).
- La scheda inversa di una **bozza** (la spec la dà per i pasti ufficiali): togliere una bozza non propone niente, anche se la sua scheda aveva messo voci in lista.
- Quantità in dispensa, e qualunque deduzione dello stato dalle ricette: lo stato lo propone Claude, lo decide Mattia.
- Segnalare le ricette importate che chiedono uno strumento mancante (resta un'idea, spec §2).
- Il passaggio di Gemma all'API di Anthropic (voce separata del backlog).

## Margine di autonomia

- **Liberi:** nomi locali, helper dei test, funzioni private non fissate qui; l'aspetto delle schede e della chat dentro il sistema visivo di spena; la formattazione esatta del testo di contesto che arriva a Claude, purché contenga quello che i test chiedono.
- **Fissi:** le parole a video e i messaggi degli strumenti fra «» di questo piano; i testi dei prompt del Task 6, parola per parola; i nomi pubblici dei blocchi Interfaces; i nomi e gli schemi degli strumenti; le rotte, i codici dei rifiuti e gli eventi SSE; i valori salvati (`official`/`draft`, `open`/`placed`/`superseded`, `forward`/`inverse`, `proposed`/`applied`/`discarded`, `pantry`/`list`/`unlist`); lo sforzo e i limiti dei giri.
- **Un test dei piani 1–3 si cambia solo dove questo piano lo dice** (blocco «Cambi alle interfacce»). Se un altro cade, il cambio ha toccato un comportamento: si corregge il codice.
- **Una decisione di comportamento non coperta e non reversibile**: si ferma quel task, si fa commit del lavoro parziale, la voce «Sezione Pasti» passa a `bloccato` con «attende: …» e la domanda precisa, e si va al task dopo se non dipende da quello. Una scelta reversibile e a basso impatto: la più conservativa, annotata nel report.
- Un test che fallisce e non si risolve: niente test disattivati, niente asserzioni indebolite. `bloccato` con la diagnosi.
- Se la versione dell'SDK sul ramo non lascia passare più di un evento di strumento per giro, o il piano 3 ha dovuto cambiare la forma degli strumenti (lo dice il suo report), si segue il piano 3 e si scrive nel report.

## Dipendenze

- **Parte da `night/pasti-claude` (piano 3)**, che parte da `night/pasti-settimana` (piano 2) e `night/utensili` (piano 1). Consuma tutti i nomi elencati nelle Global Constraints, più `utensils_prompt_block` (piano 1).
- **Nessun piano parte da questo.** Al merge su `master` i quattro rami si uniscono in ordine: `night/utensili`, `night/pasti-settimana`, `night/pasti-claude`, `night/pasti-pianificazione`. La `0022` ha come `down_revision` la `0021` del piano 3.

### Cambi alle interfacce dei piani precedenti

Ognuno è necessario, e ognuno è additivo o sostituisce un punto che il piano precedente aveva lasciato apposta.

| Piano | Interfaccia | Cambio | Perché | Test di quel piano che cambiano |
|---|---|---|---|---|
| 2 | `delete_meal`, `update_meal` | chiamano `propose_inverse_card(session, meal, reason)` prima di togliere il pasto o di renderlo fuori casa | la scheda inversa nasce per ogni strada che toglie un pasto, sostituzione compresa (decisione 22) | nessuno |
| 2 | rotta `PATCH /api/v1/meals/{id}` | da `draft` a `official` crea la scheda vuota (`create_empty_card`) | decisione 23 | nessuno |
| 2 | `meal_out(meal, today)` | `meal_out(meal, today, *, preparing: frozenset[uuid.UUID] = frozenset(), open_card_id: uuid.UUID \| None = None)`; `MealOut` riceve `recipe_state`, `recipe_notice`, `can_ask_recipe`, `open_card_id` | lo stato della ricetta e la scheda aperta | nessuno (valori di default) |
| 2 | tipo TS `Meal` | campi facoltativi `recipe_state?`, `recipe_notice?`, `can_ask_recipe?`, `open_card_id?` | idem; facoltativi per le risposte vecchie in cache | nessuno |
| 2 | `merge_ingredients` | sposta anche `change_card_rows.ingredient_id` dal perdente al vincitore | una tabella nuova punta agli ingredienti | `test_registry_merge.py` riceve una riga di scheda nel mondo di prova (Task 2) |
| 3 | `TurnContext` | `conversation_id` e `turn_message_id` diventano `uuid.UUID \| None`; nuovi campi in coda con default: `on_proposal`, `on_card` (callback asincrone, `None` = niente), `create_only: bool = False` | i giri delle ricette non hanno un messaggio; gli strumenti nuovi emettono i loro eventi | nessuno |
| 3 | `read_pantry` | ogni voce porta anche «id ‹uuid›» | `propose_changes` indica le voci per id | nessuno (il test controlla solo la presenza) |
| 3 | `write_recipe_tool` | con `ctx.create_only` rifiuta di riscrivere una ricetta che non ha creato in quel giro | decisione 15 | nessuno |
| 3 | `dish_tools` | `[*read_tools(ctx), write_recipe_tool(ctx), propose_changes_tool(ctx)]` | §6.2: la chat del piatto propone la scheda | `test_dish_tools_sono_i_cinque_di_spena` diventa `test_dish_tools_sono_i_sei_di_spena`, con `propose_changes` in coda |
| 3 | `DISH_PANTRY_RULE` | tolta; al suo posto `CHANGES_RULE`; `dish_system_prompt` compone `COMMON_PROMPT`, `DISH_PROMPT`, `CHANGES_RULE` | era il posto lasciato apposta dal piano 3 | `test_il_prompt_del_piatto_senza_utensili` usa `CHANGES_RULE` |
| 3 | `run_dish_turn` | stessa firma, diventa un involucro sottile di `run_chat_turn(…, spec=DISH_TURN)` | una copia sola del giro (prima lezione) | nessuno |
| 3 | rotta `POST …/chat/messages` | il corpo comune (controlli, `retry_of`, `pending`, avvio, stream) esce in `start_turn_stream(...)`; con `retry_of`, proposte, schede e modifiche del messaggio fallito passano al nuovo | decisione 28 | nessuno |
| 3 | `ChatMessageOut` | campi `proposals: list[MealProposalOut] = []` e `cards: list[ChangeCardOut] = []` | le schede sotto i messaggi | nessuno |
| 3 | eventi SSE | due nomi nuovi, `proposal` e `card` (`{"proposal": …}`, `{"card": …}`) | le schede arrivano mentre Claude scrive | nessuno (`readSse` ignora gli sconosciuti; il tipo si allarga) |
| 3 | tipo TS `ChatStreamEvent` | generico sulla vista: `ChatStreamEvent<TChat = DishChat>`, più `{ name: "proposal"; proposal: MealProposal }` e `{ name: "card"; card: ChangeCard }`; `ChatMessage` riceve `proposals?` e `cards?` | la pianificazione ha un'altra vista | nessuno |
| 3 | `ChatThread` | prop facoltativa `renderExtras?: (message: ChatMessage) => ReactNode`, resa sotto le modifiche del messaggio | le schede sotto i fumetti | nessuno |
| 3 | `FakeClaude` (`tests/claude_fakes.py`) | `FakeClaude.per_call(*scripts)`: la n-esima `run` usa l'n-esimo copione; una `run` in più fallisce con `AssertionError` | la coda delle ricette chiama Claude una volta per pasto | nessuno |
| 3 | `LlmCallSite`, `PLAN_CALL_SITES`, `CALL_SITE_LABELS` | `MEAL_PLANNING = "meal_planning"` («Pianificazione dei pasti»), `MEAL_RECIPE = "meal_recipe"` («Ricette dei pasti») | decisione 27 | nessuno |

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `backend/alembic/versions/0022_pianificazione.py`, `backend/app/db/models/planning.py`, `backend/app/db/models/change_card.py` (nuovi), `backend/app/db/models/meal.py`, `backend/app/db/models/conversation.py`, `backend/app/db/models/__init__.py`, `backend/tests/db/test_migration_0022.py` (nuovo) | 1 | lo schema |
| `backend/app/domain/change_cards.py`, `backend/app/services/change_cards.py` (nuovi), `backend/app/services/registry.py`, `backend/tests/domain/test_change_cards.py`, `backend/tests/services/test_change_cards.py` (nuovi), `backend/tests/services/test_registry_merge.py` | 2 | costruire, applicare, scartare una scheda |
| `backend/app/services/change_cards.py`, `backend/app/services/meals.py`, `backend/tests/services/test_inverse_cards.py` (nuovo) | 3 | la scheda inversa |
| `backend/app/schemas/change_card.py`, `backend/app/api/change_cards.py` (nuovi), `backend/app/api/meals.py`, `backend/app/schemas/meal.py`, `backend/app/main.py`, `backend/tests/api/test_change_cards.py`, `backend/tests/db/test_double_tap.py` (nuovi) | 4 | le rotte delle schede |
| `backend/app/services/planning.py` (nuovo), `backend/app/repositories/conversations.py`, `backend/tests/services/test_planning.py` (nuovo) | 5 | proposte e messa nella settimana |
| `backend/app/services/claude/prompts.py`, `backend/app/services/claude/tools.py`, `backend/tests/claude_fakes.py`, `backend/tests/services/test_claude_prompts.py`, `backend/tests/services/test_claude_tools.py`, `backend/tests/services/test_claude_planning_tools.py` (nuovo) | 6 | prompt e strumenti |
| `backend/app/services/meal_chat.py`, `backend/app/services/planning_chat.py` (nuovo), `backend/app/services/llm.py`, `backend/app/domain/spending.py`, `backend/app/domain/meal_chat.py`, `backend/tests/services/test_planning_turn.py` (nuovo) | 7 | il giro della pianificazione |
| `backend/app/services/recipe_jobs.py` (nuovo), `backend/app/api/meals.py`, `backend/tests/services/test_recipe_jobs.py`, `backend/tests/api/test_meal_recipe_ask.py` (nuovi) | 8 | le ricette in coda |
| `backend/app/schemas/planning.py`, `backend/app/api/planning.py` (nuovi), `backend/app/api/meal_chat.py`, `backend/app/schemas/meal_chat.py`, `backend/app/main.py`, `frontend/nginx.conf`, `backend/tests/api/test_planning.py`, `backend/tests/test_nginx_chat.py` | 9 | le rotte della pianificazione |
| `frontend/src/domain/types.ts`, `frontend/src/features/change-cards/*` (nuovi), `frontend/src/App.tsx`, test | 10 | la scheda dei cambi nel frontend |
| `frontend/src/features/planning/*` (nuovi), `frontend/src/features/meal-chat/ChatThread.tsx`, `frontend/src/features/meal-chat/sse.ts`, `frontend/src/features/meals/WeekScreen.tsx`, `frontend/src/features/meals/NewMealScreen.tsx`, `frontend/src/App.tsx`, test | 11 | la chat di pianificazione |
| `frontend/src/features/meals/MealScreen.tsx`, `frontend/src/features/meals/WeekScreen.tsx`, `frontend/src/features/meal-chat/DishChat.tsx`, `frontend/src/features/meals/api.ts`, test | 12 | ricetta in preparazione, scheda nel piatto |
| `backend/tests/e2e_planning.py`, `backend/tests/test_e2e_planning_guard.py`, `frontend/e2e/pianificazione.spec.ts` (nuovi), `frontend/e2e/style.spec.ts` | 13 | nel browser vero |
| `CLAUDE.md`, `docs/prossimi-passi.md`, `next-steps.md`, `docs/night-reports/<data>.md` | 14 | documenti e report |

---

### Task 1: Lo schema — proposte, schede dei cambi, posto di partenza, ricetta chiesta

**Files:**
- Create: `backend/alembic/versions/0022_pianificazione.py`, `backend/app/db/models/planning.py` (`MealProposal`), `backend/app/db/models/change_card.py` (`ChangeCard`, `ChangeCardRow`), `backend/tests/db/test_migration_0022.py`
- Modify: `backend/app/db/models/meal.py` (due colonne), `backend/app/db/models/conversation.py` (due colonne), `backend/app/db/models/__init__.py`

**Interfaces:**
- Consumes: la `0021` letta nella Preparazione.
- Produces (migrazione `revision = "0022"`):
  - `conversations` riceve `focus_day DATE NULL`, `focus_slot VARCHAR(10) NULL`; `ck_conversation_focus` (`(focus_day IS NULL) = (focus_slot IS NULL)` e `focus_slot IS NULL OR focus_slot IN ('lunch','dinner')`).
  - `meals` riceve `recipe_requested_at TIMESTAMPTZ NULL`, `recipe_notice TEXT NULL`.
  - `meal_proposals`: `id`, `conversation_id` FK `conversations.id` `ON DELETE CASCADE` non nullo, `turn_message_id` FK `conversation_messages.id` `ON DELETE SET NULL`, `kind VARCHAR(10)` (`ck_proposal_kind`: `official`|`draft`), `status VARCHAR(12) NOT NULL DEFAULT 'open'` (`ck_proposal_status`: `open`|`placed`|`superseded`), `rows JSONB NOT NULL` (elenco di `{"day": "AAAA-MM-GG", "slot", "dish", "sides", "meal_id": null|uuid}`), `created_at`, `placed_at TIMESTAMPTZ NULL`; indice `ix_meal_proposals_conversation_created`.
  - `change_cards`: `id`, `kind VARCHAR(10)` (`ck_card_kind`: `forward`|`inverse`), `status VARCHAR(10) NOT NULL DEFAULT 'proposed'` (`ck_card_status`: `proposed`|`applied`|`discarded`), `list_only BOOLEAN NOT NULL DEFAULT false`, `title VARCHAR(300) NOT NULL`, `meal_ids JSONB NOT NULL DEFAULT '[]'`, `conversation_id` FK `ON DELETE SET NULL`, `turn_message_id` FK `conversation_messages.id` `ON DELETE SET NULL`, `created_at`, `applied_at`, `discarded_at`; indice `ix_change_cards_status`.
  - `change_card_rows`: `id`, `card_id` FK `ON DELETE CASCADE`, `position INTEGER NOT NULL`, `kind VARCHAR(10)` (`ck_card_row_kind`: `pantry`|`list`|`unlist`), `label VARCHAR(300) NOT NULL`, `pantry_item_id` FK `pantry_items.id` `ON DELETE SET NULL`, `ingredient_id` FK `ingredients.id` `ON DELETE SET NULL`, `shopping_item_id` FK `shopping_list_items.id` `ON DELETE SET NULL`, `to_status VARCHAR(10) NULL`, `before_status VARCHAR(10) NULL`, `checked BOOLEAN NOT NULL`, `editable BOOLEAN NOT NULL DEFAULT true`, `note TEXT NULL`, `meal_ids JSONB NOT NULL DEFAULT '[]'`, `applied BOOLEAN NULL`, `list_added BOOLEAN NULL`, `source_row_id` FK `change_card_rows.id` `ON DELETE SET NULL`, `reversed_at TIMESTAMPTZ NULL`; `ck_card_row_status` (`to_status` e `before_status` nulli o fra `available`,`low`,`finished`); `ck_card_row_pantry_has_status` (`kind <> 'pantry' OR to_status IS NOT NULL`).
  - Modelli: `MealProposal(UUIDMixin, Base)` con `ProposalKind(StrEnum)` (`OFFICIAL`, `DRAFT`) e `ProposalStatus(StrEnum)` (`OPEN`, `PLACED`, `SUPERSEDED`); `ChangeCard(UUIDMixin, Base)` con `rows` (`order_by=position`, `lazy="raise"`), `CardKind`, `CardStatus`; `ChangeCardRow(UUIDMixin, Base)` con `RowKind` (`PANTRY`, `LIST`, `UNLIST`). `created_at` come `ConversationMessage`. `Conversation.focus_day`/`focus_slot`, `Meal.recipe_requested_at`/`recipe_notice`.

- [ ] **Step 1: Il test che fallisce.** `tests/db/test_migration_0022.py`, sul modello di `test_migration_0021.py`: `test_la_0022_sale_e_scende` (le tre tabelle e le quattro colonne ci sono; `downgrade` alla `0021` le toglie, e `meals`, `conversations` restano); `test_i_vincoli_della_proposta_e_della_scheda`, parametrizzato su righe che devono fallire (`kind='maybe'` su una proposta; `status='done'` su una scheda; riga `pantry` senza `to_status`; `to_status='empty'`; `focus_day` senza `focus_slot`); `test_cancellare_la_conversazione_porta_via_le_proposte_e_lascia_le_schede` (la proposta sparisce, la scheda resta con `conversation_id` NULL); `test_cancellare_la_scheda_porta_via_le_righe`.
- [ ] **Step 2: Fallisce.** Il comando di pytest con il file. Expected: FAIL.
- [ ] **Step 3: Migrazione e modelli.** La docstring di `ChangeCard` dice §6.2 in breve (Claude propone, Mattia applica; lo stato di prima resta per la scheda inversa) e cosa vuol dire `meal_ids` sulla scheda e sulla riga (decisione 18).
- [ ] **Step 4: Passa, e lo schema coincide coi modelli.** Il comando di pytest con `tests/db/test_migration_0022.py tests/db/test_metadata_matches_migrations.py`. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(pasti): proposte di pasti, schede dei cambi e la ricetta chiesta a Claude (0022)`.

---

### Task 2: La scheda dei cambi — costruirla, applicarla, scartarla

**Files:**
- Create: `backend/app/domain/change_cards.py`, `backend/app/services/change_cards.py`, `backend/tests/domain/test_change_cards.py`, `backend/tests/services/test_change_cards.py`
- Modify: `backend/app/services/registry.py` (`merge_ingredients`, accanto allo spostamento delle voci in lista), `backend/tests/services/test_registry_merge.py` (una riga di scheda nel mondo di prova e nell'istantanea delle tabelle)

**Interfaces:**
- Consumes: Task 1; `set_status` (`app.repositories.pantry`); `add_item`, `active_item_for`, `patch_item` (`app.repositories.shopping`); `exact_ingredient` (`app.services.ingredient_match`); `kind_for_category`; `get_meal`.
- Produces, in `app.domain.change_cards` (puro):
  - `STATUS_RANK = {"available": 0, "low": 1, "finished": 2}`; `def most_consumed(a: str, b: str) -> str`.
  - `def adds_to_list(to_status: str) -> bool` — vero solo per `finished` (decisione 19).
- Produces, in `app.services.change_cards`:
  - `@dataclass(frozen=True) class PantryProposal`: `pantry_item_id: uuid.UUID`, `to_status: PantryStatus`, `meal_ids: tuple[uuid.UUID, ...] = ()` (vuoto = i pasti della scheda).
  - `@dataclass(frozen=True) class ListProposal`: `ingredient_id: uuid.UUID | None`, `raw_text: str`, `meal_ids: tuple[uuid.UUID, ...] = ()`.
  - `@dataclass(frozen=True) class RowOverride`: `row_id: uuid.UUID`, `checked: bool`, `to_status: PantryStatus | None = None`.
  - `class CardRefusalCode(StrEnum)`: `ALREADY_APPLIED = "card_applied"`, `DISCARDED = "card_discarded"`, `LIST_ONLY = "list_only"`, `ROW_EXISTS = "row_exists"`, `NOT_IN_PANTRY = "not_in_pantry"`, `NOT_FOOD = "not_food"`, `NO_MEAL = "no_meal"`; `class CardRefusal(Exception)`: `code`, `message`.
  - `async def propose_card(session, *, meals: Sequence[Meal], pantry: Sequence[PantryProposal], shopping: Sequence[ListProposal], conversation_id: uuid.UUID | None = None, turn_message_id: uuid.UUID | None = None) -> ChangeCard` — `list_only` vero se tutti i pasti sono bozze (e allora una riga di dispensa è `LIST_ONLY`); voce di dispensa sparita o archiviata → `NOT_IN_PANTRY`; voce non alimentare → `NOT_FOOD`; le regole delle decisioni 18–19; `flush`, mai `commit`.
  - `async def create_empty_card(session, meal: Meal) -> ChangeCard` — scheda in avanti, senza righe, per un pasto.
  - `async def add_row(session, card: ChangeCard, *, pantry_item_id: uuid.UUID | None = None, raw_text: str | None = None) -> ChangeCard` — la riga a mano, con le stesse regole (una voce di dispensa nasce con `to_status` uguale allo stato di adesso, spuntata; un testo si aggancia con `exact_ingredient`); doppione → `ROW_EXISTS`; scheda non proposta → `ALREADY_APPLIED`/`DISCARDED`.
  - `async def apply_card(session, card_id: uuid.UUID, overrides: Sequence[RowOverride]) -> ChangeCard` — decisione 21.
  - `async def discard_card(session, card_id: uuid.UUID) -> ChangeCard` — da `proposed` a `discarded`; applicata → `ALREADY_APPLIED`.
  - `async def get_card(session, card_id) -> ChangeCard | None` (con le righe); `async def cards_with_status(session, status: CardStatus) -> list[ChangeCard]` (dal più recente); `async def open_card_for_meal(session, meal_id) -> ChangeCard | None` (la più recente `proposed` con il pasto in `meal_ids`, via contenimento JSONB).
  - `def card_title(...)` non è pubblica: i titoli, esatti, sono: in avanti per un pasto «Per «‹piatto›»»; per più pasti «Per ‹n› pasti»; con `list_only` «Per la spesa: ‹n› pasti in bozza» (un pasto: «Per la spesa: «‹piatto›» in bozza»); vuota dell'ufficializzazione «Per «‹piatto›»: compila a mano».
- Le note delle righe, esatte: «Già in lista.»; all'applicazione «La voce non è più in dispensa.».

**Le regole che i test fissano.** Una riga di dispensa ha `label` = nome del prodotto se c'è, altrimenti dell'ingrediente (come `restock`). Una riga della lista nata da una `finished` ha lo stesso `label` e `meal_ids` della sua riga di dispensa. Una riga «già in lista» (`active_item_for` trova una voce) ha `checked=False`, `editable=False`, `note="Già in lista."`. All'applicazione, dentro la transazione del chiamante: `select(ChangeCard).where(id).with_for_update()`, poi controllo dello stato; ogni override si applica alla sua riga (un override su una riga non `editable`, o un `to_status` su una riga che non è di dispensa, si ignora); per ogni riga spuntata: `pantry` → `before_status` = stato di adesso, `set_status` se diverso, `applied=True`; `list` → `add_item(session, label, ingredient_id)`, `shopping_item_id` = la voce restituita, `list_added` = `added`, `applied=True`; `unlist` → (Task 3); non spuntata → `applied=False`. Poi `status=applied`, `applied_at`.

- [ ] **Step 1: I test che falliscono.**
  - `tests/domain/test_change_cards.py`: `test_most_consumed` (parametrizzato sulle nove coppie), `test_adds_to_list` (solo `finished`).
  - `tests/services/test_change_cards.py` (fixture: ingredienti `ricotta`, `parmigiano`, `pesto`, `pasta` alimentari e `detersivo` in `casa`; voci di dispensa per ciascuno, `available`; il pesto con un prodotto «Pesto Barilla»; due pasti ufficiali e una bozza con `create_meal`; ogni test fa `flush` e rilegge):
    1. `test_una_scheda_dalla_proposta`: ricotta → `finished`, parmigiano → `low`. Le righe sono: ricotta (dispensa, `finished`, spuntata), parmigiano (dispensa, `low`), ricotta (lista, spuntata). Il titolo è «Per «‹piatto›»».
    2. `test_quasi_finito_non_va_in_lista_da_solo`: pesto → `low`, e un'altra scheda con un pesto già `low` → `low`. Nessuna riga `list` per il pesto, in nessuna delle due.
    3. `test_una_voce_gia_in_lista_non_si_ripropone`: ricotta già da comprare in lista; ricotta → `finished` e una `ListProposal` esplicita per la ricotta. C'è una sola riga `list` per la ricotta, con `checked is False`, `editable is False`, `note == "Già in lista."`.
    4. `test_due_pasti_sulla_stessa_voce_fanno_una_riga`: parmigiano → `low` per il pasto A, parmigiano → `finished` per il pasto B. Una riga sola di dispensa, `to_status == "finished"`, `meal_ids` con A e B.
    5. `test_una_bozza_ha_solo_la_lista`: scheda per la bozza con una riga di dispensa → `CardRefusal(LIST_ONLY)`; con sole `ListProposal` → `list_only is True`, titolo «Per la spesa: «‹piatto›» in bozza».
    6. `test_niente_non_alimentari_e_voci_sparite`: il detersivo → `NOT_FOOD`; una voce archiviata → `NOT_IN_PANTRY`.
    7. `test_applicare_cambia_dispensa_e_lista_e_ricorda_lo_stato_di_prima`: dopo `apply_card` senza override, la ricotta è `finished` (via `set_status`: `status_changed_at` aggiornato, `fill_percent` nullo), la lista ha la ricotta da comprare, e la riga di dispensa ha `before_status == "available"`, `applied is True`; la riga di lista ha `shopping_item_id` e `list_added is True`; la scheda è `applied`.
    8. `test_le_correzioni_di_mattia`: override che toglie la spunta al parmigiano e porta la ricotta a `low` → il parmigiano non cambia (`applied is False`), la ricotta è `low`, e la riga di lista della ricotta (ancora spuntata) entra in lista: quel che è spuntato si applica.
    9. `test_una_voce_entrata_in_lista_dopo_non_si_duplica`: la scheda si propone, poi la ricotta entra in lista con `add_item`, poi `apply_card` → in lista c'è **una** voce attiva per la ricotta, e la riga ha `list_added is False`.
    10. `test_applicare_due_volte_e_409_e_non_cambia_niente`: la seconda `apply_card` → `CardRefusal(ALREADY_APPLIED)`; la lista ha una voce sola e `status_changed_at` della ricotta è quello della prima.
    11. `test_scartare`: `discard_card` → `discarded`, niente cambiato; poi `apply_card` → `DISCARDED`; `discard_card` su un'applicata → `ALREADY_APPLIED`.
    12. `test_una_voce_sparita_si_salta`: dopo la proposta la voce del parmigiano si archivia; `apply_card` applica il resto e la riga ha `applied is False` con «La voce non è più in dispensa.».
    13. `test_la_scheda_vuota_e_le_righe_a_mano`: `create_empty_card` → titolo «Per «‹piatto›»: compila a mano», nessuna riga; `add_row(pantry_item_id=parmigiano)` → riga con `to_status` uguale allo stato di adesso; di nuovo → `ROW_EXISTS`; `add_row(raw_text="Ricotta")` → riga di lista agganciata alla ricotta; `add_row(raw_text="zenzero candito")` → riga di lista senza ingrediente.
    14. `test_open_card_for_meal`: la scheda proposta del pasto A si trova; applicata, non più.
  - In `test_registry_merge.py`: il mondo di prova riceve una riga di scheda sul perdente; dopo la fusione punta al vincitore (e l'istantanea delle tabelle la conta).
- [ ] **Step 2: Falliscono.** Il comando di pytest con i due file nuovi. Expected: FAIL.
- [ ] **Step 3: Il codice.** La docstring di `apply_card` dice perché il blocco della riga (decisione 21) e perché `add_item` e non una copia (prima lezione: la regola del non duplicare sta in un posto solo).
- [ ] **Step 4: Passano.** I due file, `tests/services/test_registry_merge.py`, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(pasti): la scheda dei cambi — una riga per voce, le finite già in lista, applicata una volta sola con lo stato di prima`.

---

### Task 3: La scheda inversa

**Files:**
- Modify: `backend/app/services/change_cards.py`, `backend/app/services/meals.py` (`delete_meal` e `update_meal`, piano 2)
- Create: `backend/tests/services/test_inverse_cards.py`

**Interfaces:**
- Consumes: Task 2; `delete_meal`, `update_meal`, `create_meal(replace=True)` (piano 2).
- Produces, in `app.services.change_cards`:
  - `class InverseReason(StrEnum)`: `DELETED = "deleted"`, `REPLACED = "replaced"`, `AWAY = "away"`.
  - `async def propose_inverse_card(session, meal: Meal, reason: InverseReason) -> ChangeCard | None` — decisione 22; `None` se il pasto non è ufficiale o non c'è niente da rimettere. Pulisce anche le schede in avanti proposte di quel pasto (ultimo punto della decisione 22).
  - In `apply_card`, le righe delle inverse: `pantry` come le altre, e la riga d'origine riceve `reversed_at`; `unlist` → se la voce in lista è ancora da comprare o nel carrello, `patch_item(status=ShoppingStatus.ARCHIVED)` (la stessa strada di «Togli» della lista), altrimenti `applied=False` con «Già comprata: resta com'è.».
- I titoli, esatti: `DELETED` «Hai tolto «‹piatto›»: rimetti quello che usava?»; `REPLACED` «Hai sostituito «‹piatto›»: rimetti quello che usava?»; `AWAY` ««‹piatto›» è fuori casa: rimetti quello che usava?». Le note, esatte: «Cambiata dopo la scheda: controlla prima di rimetterla.», «È già nel carrello.».
- In `app.services.meals` (piano 2): `delete_meal(session, meal)` chiama `propose_inverse_card(session, meal, InverseReason.DELETED)` prima di cancellare; `create_meal`/`update_meal` con `replace=True` passano `REPLACED` per l'occupante (un parametro privato `_reason` di `delete_meal`, o una funzione privata comune: libero); `update_meal` con `away` che passa da falso a vero chiama `AWAY` prima di `release_recipe`. Spostare (`day`/`slot`) non chiama niente.

- [ ] **Step 1: I test che falliscono.** `tests/services/test_inverse_cards.py` (fixture come il Task 2; «applicata» vuol dire `propose_card` + `apply_card`):
  1. `test_togliere_un_pasto_propone_l_inversa`: pasto A con la scheda applicata (ricotta → `finished` più la riga in lista). `delete_meal(A)` → una scheda `inverse`, `proposed`, titolo «Hai tolto «‹piatto›»: rimetti quello che usava?», con la riga di dispensa ricotta `finished → available` spuntata e la riga `unlist` della ricotta spuntata.
  2. `test_applicare_l_inversa_rimette_e_toglie_dalla_lista`: applicata l'inversa, la ricotta è `available`, la voce in lista è `archived`, e la riga d'origine ha `reversed_at`; un'altra cancellazione che coinvolge la stessa scheda d'origine non ripropone quella riga.
  3. `test_sostituire_e_fuori_casa_propongono_spostare_no`, parametrizzato: `create_meal(replace=True)` sul posto di A → titolo `REPLACED`; `update_meal(A, {"away": True})` → titolo `AWAY`; `update_meal(A, {"day": …})` → nessuna scheda nuova.
  4. `test_l_inversa_non_rimette_cio_che_serve_ancora_a_un_altro_pasto`: una scheda per A e B con parmigiano (A e B) e ricotta (solo A). Togliendo A, l'inversa ha la ricotta e non il parmigiano. Togliendo poi anche B, l'inversa ha il parmigiano.
  5. `test_l_inversa_dopo_una_spesa_nel_frattempo`: dopo la scheda, la voce in lista della ricotta passa a sistemata con `stock_items` (che crea una voce di dispensa nuova, `available`). Togliendo A, l'inversa non ha la riga `unlist`; ha la riga della **vecchia** voce della ricotta (`finished → available`, spuntata); applicata, la voce nuova della spesa è intatta (stesso id, stesso `status_changed_at`).
  6. `test_una_voce_cambiata_dopo_non_si_spunta`: dopo la scheda (parmigiano → `low`) Mattia porta il parmigiano a `finished` dalla dispensa. Togliendo A, la riga c'è, `checked is False`, con «Cambiata dopo la scheda: controlla prima di rimetterla.».
  7. `test_una_voce_gia_tornata_allo_stato_di_prima_non_c_e`: la ricotta rimessa `available` a mano → nessuna riga per lei; se non resta nessuna riga, nessuna scheda.
  8. `test_nel_carrello_non_si_spunta`: la voce in lista spuntata nel carrello → riga `unlist` non spuntata con «È già nel carrello.».
  9. `test_una_bozza_non_propone_niente`: una bozza con la sua scheda della lista applicata, cancellata → nessuna inversa.
  10. `test_le_schede_proposte_del_pasto_tolto_si_puliscono`: una scheda proposta solo per A, A cancellato → la scheda è `discarded`; una proposta per A e B perde le righe che servivano solo ad A e resta `proposed`.
- [ ] **Step 2: Falliscono.** Il comando di pytest con il file. Expected: FAIL.
- [ ] **Step 3: Il codice.** La docstring di `propose_inverse_card` dice perché senza quantità l'inverso non si ricava dallo stato di oggi (§6.2) e le tre regole di sicurezza (serve ancora a un altro pasto; cambiata dopo; comprata di nuovo).
- [ ] **Step 4: Passano.** Il file, `tests/services/test_meals.py` del piano 2 (deve restare verde senza cambi), poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(pasti): la scheda inversa quando un pasto ufficiale si toglie, si sostituisce o va fuori casa — senza rimettere ciò che serve ancora o che è stato ricomprato`.

---

### Task 4: Le rotte delle schede, e la scheda aperta del pasto

**Files:**
- Create: `backend/app/schemas/change_card.py`, `backend/app/api/change_cards.py`, `backend/tests/api/test_change_cards.py`, `backend/tests/db/test_double_tap.py`
- Modify: `backend/app/schemas/meal.py` (`MealOut.open_card_id`), `backend/app/api/meals.py` (`meal_out`; `PATCH` che ufficializza), `backend/app/main.py`

**Interfaces:**
- Produces, in `app.schemas.change_card`:
  - `ChangeRowOut`: `id`, `kind: Literal["pantry", "list", "unlist"]`, `label: str`, `from_status: PantryStatus | None` (per `pantry`: lo stato di adesso finché la scheda è proposta, `before_status` dopo; `None` per le altre), `to_status: PantryStatus | None`, `listed: bool` (riga di lista con una voce già in lista), `checked: bool`, `editable: bool`, `note: str | None`, `applied: bool | None`.
  - `ChangeCardOut`: `id`, `kind: Literal["forward", "inverse"]`, `status: Literal["proposed", "applied", "discarded"]`, `list_only: bool`, `title: str`, `meals: list[MealRefOut]` (i pasti che ci sono ancora), `rows: list[ChangeRowOut]`, `created_at`, `applied_at: datetime | None`.
  - `CardApplyIn`: `rows: list[RowOverrideIn]` (`id`, `checked: bool`, `to_status: PantryStatus | None = None`); `CardRowIn`: `pantry_item_id: uuid | None = None`, `raw_text: str | None = None` (uno dei due, ripulito, 1–200).
  - `async def card_out(session, card: ChangeCard) -> ChangeCardOut`.
- Produces, in `app.api.change_cards` (`prefix="/api/v1/change-cards"`, dietro la sessione):
  - `GET ""?status=proposed` → `list[ChangeCardOut]`; `GET /{id}` → `ChangeCardOut` (404 «scheda inesistente»).
  - `POST /{id}/rows` (`CardRowIn`) → `ChangeCardOut`.
  - `POST /{id}/apply` (`CardApplyIn`) → `ChangeCardOut`.
  - `POST /{id}/discard` → `ChangeCardOut`.
  - Un `CardRefusal` → 409 `{"code", "detail", "card": ChangeCardOut}` dopo il `rollback`, rileggendo la scheda (il frontend mostra la scheda com'è). Le frasi dei codici, esatte: `card_applied` «La scheda era già applicata.»; `card_discarded` «La scheda è stata scartata.»; `list_only` «Per una bozza la scheda ha solo le righe della lista.»; `row_exists` «Questa voce è già nella scheda.»; `not_in_pantry` «La voce non è più in dispensa.»; `not_food` «Le voci non alimentari non vanno nella scheda.».
- In `app.api.meals`: ogni `MealOut` porta `open_card_id` (da `open_card_for_meal`); `PATCH` con `status` da `draft` a `official` chiama `create_empty_card` prima del `commit`, e la risposta ha `open_card_id` della scheda nuova.

- [ ] **Step 1: I test che falliscono.**
  - `tests/api/test_change_cards.py` (con `logged_client`; schede costruite con i servizi e `commit`):
    1. `test_leggere_una_scheda`: `GET /{id}` → righe con `from_status` (lo stato di adesso), `to_status`, `checked`, `editable`; la riga «già in lista» ha `listed: true`.
    2. `test_ora_si_legge_dal_vivo`: dopo la proposta la voce cambia stato dalla dispensa (`PATCH /api/v1/pantry/{id}`) → `from_status` è quello nuovo.
    3. `test_applicare_dalla_rotta`: `POST /apply` con una riga tolta → 200, `status == "applied"`, `GET /api/v1/pantry` e `GET /api/v1/shopping-list` riflettono i cambi; ora `from_status` è lo stato di prima.
    4. `test_applicare_due_volte_dalla_rotta`: il secondo `POST /apply` → 409 `card_applied` con `card.status == "applied"`; `GET /api/v1/shopping-list` ha una voce sola per la ricotta.
    5. `test_scartare_e_poi_applicare`: `POST /discard` → 200 `discarded`; `POST /apply` → 409 `card_discarded`.
    6. `test_righe_a_mano`: `POST /rows` con `pantry_item_id` → 200 e la riga; di nuovo → 409 `row_exists`; con `raw_text` → la riga di lista; su una scheda `list_only` con `pantry_item_id` → 409 `list_only`.
    7. `test_le_schede_proposte`: `GET ?status=proposed` ha la proposta e non l'applicata.
    8. `test_rendere_ufficiale_una_bozza_apre_la_scheda_vuota`: `PATCH /api/v1/meals/{bozza}` `{"status": "official"}` → `open_card_id` non nullo; `GET /api/v1/change-cards/{id}` ha il titolo «Per «‹piatto›»: compila a mano» e nessuna riga; un `PATCH` che corregge solo il piatto di un ufficiale non crea schede.
    9. `test_cancellare_un_pasto_lascia_l_inversa_fra_le_proposte`: `DELETE /api/v1/meals/{id}` di un pasto con scheda applicata → 204, e `GET ?status=proposed` ha l'inversa.
  - `tests/db/test_double_tap.py`, su un database suo (come `test_migration_0022.py`: `f"{TEST_DB}_doppio_tocco"`, `alembic upgrade head` in un sottoprocesso, creato e distrutto dalla fixture): `test_applicare_insieme_da_due_connessioni`. Con due `AsyncSession` su due connessioni diverse e i dati committati (una voce, una scheda proposta con la sua riga di lista), `asyncio.gather` di due `apply_card` seguiti ciascuno dal suo `commit`: uno riesce, l'altro solleva `CardRefusal(ALREADY_APPLIED)`; la lista ha una voce sola. (Il Task 5 aggiunge qui il gemello della proposta.)
- [ ] **Step 2: Falliscono.** Il comando di pytest con i due file. Expected: FAIL.
- [ ] **Step 3: Il codice**, come nel blocco Interfaces.
- [ ] **Step 4: Passano.** I due file, `tests/api/test_meals.py` del piano 2, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(pasti): le rotte delle schede dei cambi; «Rendi ufficiale» apre la scheda vuota da compilare`.

---

### Task 5: Le proposte di pasti e la messa nella settimana

**Files:**
- Create: `backend/app/services/planning.py`, `backend/tests/services/test_planning.py`
- Modify: `backend/app/repositories/conversations.py`, `backend/tests/db/test_double_tap.py` (un test)

**Interfaces:**
- Consumes: Task 1–3; `meal_at`, `create_meal`, `update_meal` (piano 2); `today_in_pantry`.
- Produces, in `app.repositories.conversations`: `latest_planning(session) -> Conversation | None` (la più recente per `created_at`); `create_planning(session, *, focus: tuple[date, MealSlot] | None = None) -> Conversation`; `set_focus(session, conversation, focus: tuple[date, MealSlot] | None) -> None`; `proposals_of(session, conversation_id) -> list[MealProposal]`; `cards_of(session, conversation_id) -> list[ChangeCard]`; `move_turn_products(session, *, from_message_id, to_message_id) -> None` (proposte, schede e `recipe_changes`: decisione 28).
- Produces, in `app.services.planning`:
  - `@dataclass(frozen=True) class ProposedMeal`: `day: date`, `slot: MealSlot`, `dish: str`, `sides: str | None`.
  - `class PlanningRefusalCode(StrEnum)`: `PAST = "proposal_past"`, `DUPLICATE_SLOT = "proposal_duplicate"`, `PLACED = "proposal_placed"`, `SUPERSEDED = "proposal_superseded"`, `SLOTS_TAKEN = "slots_taken"`; `class PlanningRefusal(Exception)`: `code`, `message`, `occupants: list[Meal] = []`.
  - `async def propose_meals(session, *, conversation_id, turn_message_id, kind: ProposalKind, meals: Sequence[ProposedMeal], today: date) -> MealProposal` — rifiuta un giorno prima di `today` e due righe sullo stesso posto; le proposte `open` della conversazione diventano `superseded`.
  - `RowEffect = Literal["new", "officialize", "replace"]`; `async def row_occupants(session, proposal) -> list[tuple[dict, Meal | None, RowEffect]]` (decisione 13, letto dal vivo).
  - `@dataclass(frozen=True) class Placement`: `proposal: MealProposal`, `meals: list[Meal]`, `follow_up: str`.
  - `async def place_proposal(session, proposal_id: uuid.UUID, *, replace: bool, now: datetime) -> Placement` — `with_for_update()` sulla proposta; non `open` → `PLACED`/`SUPERSEDED`; con occupanti da sostituire e `replace` falso → `SLOTS_TAKEN` con gli occupanti, **prima di scrivere**; poi per ogni riga `create_meal` / `update_meal(…, {"dish", "sides", "status": "official"})` / `create_meal(replace=True)`; scrive `meal_id` nelle righe, `status=placed`, `placed_at`; sui pasti ufficiali `recipe_requested_at = now` e `recipe_notice = None`. `flush`, mai `commit`.
  - `async def planning_concluded(session, conversation: Conversation, today: date) -> bool` — decisione 26.
  - `async def conversation_for_meal(session, meal_id) -> uuid.UUID | None` — la conversazione dell'ultima proposta messa che contiene il pasto.
- Le frasi, esatte: `PAST` «Non si pianifica nel passato: ‹giorno lungo› è prima di oggi.»; `DUPLICATE_SLOT` «Due pasti nello stesso posto: ‹giorno lungo› · ‹pranzo|cena›.»; `PLACED` «Questa proposta è già nella settimana.»; `SUPERSEDED` «C'è una proposta più nuova: usa quella.»; `SLOTS_TAKEN` «Alcuni posti sono occupati.».
- `follow_up`, esatto: ufficiale «Ho messo nella settimana: ‹elenco›. Mandami la scheda dei cambi.»; bozza «Ho messo nella settimana come bozza: ‹elenco›. Mandami le cose da mettere in lista.»; ‹elenco› è «‹giorno lungo› · ‹pranzo|cena›, ‹piatto›» unito da «; » (giorno lungo come `longDayLabel` del frontend: «martedì 11 novembre»; i nomi dei giorni e dei mesi sono quelli di `prompts.py` del piano 3).

- [ ] **Step 1: I test che falliscono.** `tests/services/test_planning.py` (oggi fissato a giovedì 2026-11-12):
  1. `test_una_proposta_nuova_sostituisce_quella_aperta`: due `propose_meals` → la prima `superseded`, la seconda `open`.
  2. `test_niente_passato_niente_doppioni`: un giorno dell'11 → `PAST` con la frase; due righe sul 13 a cena → `DUPLICATE_SLOT`.
  3. `test_mettere_su_posti_vuoti`: proposta ufficiale per 13 cena e 14 pranzo → due pasti ufficiali con piatto e accompagnamenti, `recipe_requested_at` scritto, le righe con il loro `meal_id`, la proposta `placed`; `follow_up` è «Ho messo nella settimana: venerdì 13 novembre · cena, ‹piatto›; sabato 14 novembre · pranzo, ‹piatto›. Mandami la scheda dei cambi.» (con le date del test).
  4. `test_una_bozza_si_mette_come_bozza`: proposta `draft` → pasti `draft`, nessun `recipe_requested_at`, `follow_up` della bozza.
  5. `test_l_ufficializzazione_aggiorna_la_bozza_senza_conferma`: una bozza al 13 cena; proposta ufficiale sul 13 cena con un piatto cambiato → stesso id del pasto, `official`, piatto nuovo; `row_occupants` aveva dato `officialize`.
  6. `test_un_posto_occupato_chiede_la_conferma_e_non_scrive_niente`: un pasto ufficiale al 13 cena e un posto vuoto al 14; senza `replace` → `SLOTS_TAKEN` con l'occupante, e nessun pasto creato al 14; con `replace=True` → l'occupante non c'è più (e, se aveva una scheda applicata, c'è la sua inversa), il nuovo sì.
  7. `test_mettere_due_volte`: la seconda `place_proposal` → `PLACED`; una `superseded` → `SUPERSEDED`.
  8. `test_conclusa`, a passi: nuova → falso; proposta messa ufficiale → falso; la sua scheda applicata → vero. Con una bozza messa e la scheda della lista applicata → falso finché la bozza è bozza; ufficializzata con la sua scheda applicata → vero.
  9. `test_move_turn_products`: una proposta e una scheda legate al messaggio X passano al messaggio Y.
  - In `tests/db/test_double_tap.py`: `test_mettere_insieme_da_due_connessioni` — due `place_proposal` contemporanee: uno riesce, l'altro `PLACED`; un pasto solo per posto.
- [ ] **Step 2: Falliscono.** Il comando di pytest con i due file. Expected: FAIL.
- [ ] **Step 3: Il codice.** La docstring di `place_proposal` dice la decisione 13 e perché tutto si controlla prima di scrivere.
- [ ] **Step 4: Passano.** I due file, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(pasti): le proposte di pasti e «Metti nella settimana» — bozze ufficializzate, sostituzioni solo con conferma, una volta sola`.

---

### Task 6: I prompt e gli strumenti della pianificazione

**Files:**
- Modify: `backend/app/services/claude/prompts.py`, `backend/app/services/claude/tools.py`, `backend/tests/claude_fakes.py`, `backend/tests/services/test_claude_prompts.py`, `backend/tests/services/test_claude_tools.py`
- Create: `backend/tests/services/test_claude_planning_tools.py`

**Interfaces:**
- Consumes: Task 2 (`propose_card`, `PantryProposal`, `ListProposal`, `CardRefusal`), Task 5 (`propose_meals`, `ProposedMeal`, `PlanningRefusal`); `meal_at`.
- Produces, in `prompts.py`: `CHANGES_RULE`, `PLANNING_PROMPT`, `RECIPE_PROMPT` (testi qui sotto); `DISH_PANTRY_RULE` **tolta**; `dish_system_prompt(block)` = `COMMON_PROMPT`, `DISH_PROMPT`, `CHANGES_RULE` (+ blocco); `planning_system_prompt(block) -> str` = `COMMON_PROMPT`, `PLANNING_PROMPT`, `CHANGES_RULE` (+ blocco); `recipe_system_prompt(block) -> str` = `COMMON_PROMPT`, `RECIPE_PROMPT` (+ blocco), sempre uniti da `"\n\n"`. `PlanningContext(now: datetime, focus: tuple[date, MealSlot] | None, open_proposal: MealProposal | None)`; `render_planning_prompt(context, history: Sequence[HistoryItem], text: str) -> str`; `render_recipe_prompt(context: DishContext, history: Sequence[HistoryItem]) -> str`. Nella storia di pianificazione, `HistoryItem.changes` porta le righe «Proposta: ‹elenco› — messa nella settimana / sostituita / aperta» e «Scheda dei cambi: ‹titolo› — applicata / scartata / da applicare».
- Produces, in `tools.py`: i cambi di `TurnContext` e `read_pantry` del blocco «Cambi alle interfacce»; `propose_meals_tool(ctx)`, `propose_changes_tool(ctx)`; `dish_tools(ctx)` con sei strumenti; `planning_tools(ctx) -> list[SdkMcpTool]` = `[*read_tools(ctx), propose_meals_tool(ctx), propose_changes_tool(ctx)]`; `recipe_tools(ctx) -> list[SdkMcpTool]` = `[*read_tools(ctx), write_recipe_tool(ctx)]`.
- Produces, in `claude_fakes.py`: `FakeClaude.per_call(*scripts)`.

**I testi, copia fissata.**

`CHANGES_RULE`:
```
In dispensa e nella lista della spesa non scrivi mai: i cambi li proponi con propose_changes, una scheda con le voci, com'è adesso ogni voce e cosa diventa. Mattia la rivede, toglie o corregge le righe e la applica lui.
- Ogni voce della dispensa si indica con il suo id, letto con read_pantry. Uno stato per voce, proposto da te: una confezione da una porzione (una ricotta, una scatola di legumi, una vaschetta di affettato) diventa finito; una confezione grande (pasta, riso, olio, farina) resta com'è e non va nella scheda; un vasetto di sugo appena aperto diventa quasi finito.
- Un pesto, un sugo pronto o un ragù già quasi finito è avviato: non va in lista per questo.
- Le voci che diventano finite spena le mette da sé fra le cose da comprare: non ripeterle. Non proporre quello che è già nella lista.
- Quando la scheda è per più pasti, ogni voce dice per quali pasti serve: se poi un pasto si toglie, spena propone di rimettere solo quello che serviva a lui.
- Nella chat di un piatto, proponi la scheda quando una modifica cambia quello che si usa («non ho spinaci, uso le zucchine»), anche per rimettere disponibile quello che non si usa più.
```

`PLANNING_PROMPT`:
```
Questa è la chat di pianificazione: Mattia decide con te i pranzi e le cene dei prossimi giorni. In testa a ogni messaggio trovi il contesto: adesso (giorno e ora), il posto da cui Mattia è partito se ce n'è uno, e la proposta che è sul tavolo.

Mattia pianifica in due modi, e da come ne parla capisci quale; se non è chiaro, chiedilo:
- con quello che c'è in casa: proponi pasti fatti con la dispensa di adesso, che entrano nella settimana subito ufficiali;
- prima della spesa: proponi una bozza dei pasti, che serve a compilare la lista; i pasti entrano come bozza e la dispensa non si tocca. Quando Mattia torna dalla spesa e ha sistemato la dispensa, ti dice cosa ha trovato e cosa no («il merluzzo non c'era, ho preso il salmone in offerta»): rileggi la dispensa, rivedi la bozza cambiando solo quello che serve, e riproponila come pasti ufficiali.

Qui si pianifica, quindi il quadro della settimana serve. Prima di proporre leggi i pasti di questa settimana e della precedente (read_meals), la dispensa e la lista. Il quadro dillo in breve: i pasti registrati e i loro gruppi, gli squilibri con i numeri dei pasti, il sale stimato contro i 5 g al giorno. Poi le proposte: varie, con la precedenza alle voci in scadenza, ai sughi avviati e alle confezioni aperte, e per ognuna una riga su perché aiuta l'equilibrio («porta legumi, che mancano da sabato»).

I posti: si pianifica da adesso in avanti, mai nel passato. Un pasto già ufficiale non si ripianifica da capo: lo giudichi, al massimo proponi un ritocco, e passi ai posti vuoti. Un pasto fuori casa resta com'è.

I pasti li proponi con propose_meals, mai solo a parole: Mattia vede una scheda con il posto, il piatto e gli accompagnamenti, e la mette nella settimana con un tocco. Il piatto è il nome breve che si legge nella settimana («Frittata di spinaci e parmigiano»); gli accompagnamenti sono pane, frutta e contorni semplici, scritti corti («piadina · banana»). kind è official per i pasti con quello che c'è e per l'ufficializzazione di una bozza, draft per la bozza prima della spesa. Se Mattia vuole cambiare qualcosa, manda una proposta nuova intera: sostituisce la precedente. Se un posto è occupato, la scheda lo dice a Mattia e sostituire chiede la sua conferma: non chiederla tu.

Le ricette non le scrivi qui: quando i pasti ufficiali entrano nella settimana, spena le fa scrivere una per pasto, e Mattia le trova aprendo il piatto.

Quando Mattia ti dice che ha messo i pasti nella settimana, manda con propose_changes la scheda dei cambi per quei pasti: per pasti ufficiali le voci della dispensa che usano, con lo stato che diventano, e le cose da comprare che mancano; per una bozza solo le cose da comprare che mancano per quei piatti, perché la dispensa si aggiorna quando i pasti diventano ufficiali.
```

`RECIPE_PROMPT`:
```
Scrivi la ricetta di un pasto che Mattia ha appena messo nella settimana. Nel messaggio trovi il pasto (giorno, pranzo o cena, piatto, accompagnamenti) e, se c'è, la conversazione in cui l'avete deciso: segui quello che vi siete detti.
- Leggi la dispensa e scrivi la ricetta con quello che c'è, con le dosi del pasto come lo si mangerà (di norma 1 porzione), misurate sulle confezioni.
- Scrivila con write_recipe, una volta: titolo, porzioni, procedimento a passi numerati e tutte le righe degli ingredienti; summary è una riga su cosa hai scritto. Non cambiare dish e sides.
- Se un contorno ha bisogno di una ricetta, mettilo nella ricetta del piatto.
- Non c'è nessuno a cui fare domande: se qualcosa non è chiaro, scegli la strada più semplice e dillo nel procedimento.
- Dopo write_recipe rispondi solo: fatta.
```

**Gli strumenti nuovi** (nomi, descrizioni italiane e schemi fissi; JSON Schema completi con `additionalProperties: false`, argomenti validati con Pydantic `extra="forbid"` prima di toccare il database):

| Nome | Argomenti | Cosa fa |
|---|---|---|
| `propose_meals` | `kind` (`official`/`draft`), `meals` (1–14: `day` `AAAA-MM-GG`, `slot` `lunch`/`dinner`, `dish` 1–200, `sides` ≤ 200 facoltativo) | `propose_meals` del Task 5 con `ctx.conversation_id`, `ctx.turn_message_id`, `ctx.today`; `commit`; `await ctx.on_proposal(proposal)` se c'è; risponde «Proposta mandata: Mattia la vede come scheda e la mette nella settimana con un tocco.». `PlanningRefusal` → `is_error` con il messaggio. Senza conversazione: `is_error`. |
| `propose_changes` | `meals` (facoltativo; 1–14 posti `{day, slot}`; nella chat del piatto, assente = il pasto del piatto), `pantry` (≤ 40: `pantry_item_id`, `to` `available`/`low`/`finished`, `meals` facoltativo), `shopping` (≤ 40: `ingredient_id` oppure `name`, `meals` facoltativo) | I posti diventano pasti con `meal_at` (un posto vuoto → `is_error` «Nessun pasto in ‹giorno lungo› · ‹pranzo|cena›: la scheda è per pasti già nella settimana.»); un `name` passa da `exact_ingredient` (niente → `is_error` «‹nome› non è nell'anagrafica: cercalo con search_ingredients.»); poi `propose_card`, `commit`, `await ctx.on_card(card)`, e «Scheda mandata: Mattia la rivede e la applica.». `CardRefusal` → `is_error`, con questi messaggi: `LIST_ONLY` «Per una bozza la scheda ha solo le cose da comprare: la dispensa si aggiorna quando i pasti diventano ufficiali.»; `NOT_IN_PANTRY` «La voce ‹id› non è in dispensa: rileggi con read_pantry.»; `NOT_FOOD` «‹nome› non è un alimento: non va nella scheda.». |

`write_recipe` con `ctx.create_only`: se il pasto ha una ricetta che **non** è stata creata in questo giro → `is_error` «Il pasto ha già una ricetta: non riscriverla.» e niente scritto.

- [ ] **Step 1: I test che falliscono.**
  - `test_claude_prompts.py`: `test_il_prompt_del_piatto_senza_utensili` diventa `COMMON_PROMPT + "\n\n" + DISH_PROMPT + "\n\n" + CHANGES_RULE`; nuovi `test_il_prompt_della_pianificazione` (`COMMON_PROMPT`, `PLANNING_PROMPT`, `CHANGES_RULE`, e il blocco degli utensili in coda se c'è) e `test_il_prompt_della_ricetta`; `test_i_prompt_dicono_le_regole_degli_stati`, presenza in `CHANGES_RULE` di «diventa finito», «resta com'è», «appena aperto diventa quasi finito», «è avviato: non va in lista», e in `PLANNING_PROMPT` di «mai nel passato», «5 g al giorno», «perché aiuta l'equilibrio», «propose_meals», «draft per la bozza»; `test_render_planning_prompt` (contiene «Adesso: giovedì 12 novembre 2026, 18:40» con un `now` alle 17:40 UTC, il posto di partenza «venerdì 13 novembre, cena», le righe della proposta aperta, la storia con «Proposta: … — messa nella settimana», e il messaggio in fondo); `test_render_recipe_prompt` (il pasto e la storia).
  - `test_claude_tools.py`: `test_dish_tools_sono_i_sei_di_spena` (al posto di `…_i_cinque_…`); `test_read_pantry_porta_gli_id`.
  - `test_claude_planning_tools.py` (strumenti chiamati con `tool.handler(args)` sugli oggetti di `planning_tools(ctx)` / `dish_tools(ctx)` / `recipe_tools(ctx)`):
    1. `test_planning_tools_sono_sei`: nomi `read_pantry`, `read_shopping_list`, `read_meals`, `search_ingredients`, `propose_meals`, `propose_changes`; nessuno `write_recipe`.
    2. `test_propose_meals_salva_e_avvisa`: la proposta c'è, `on_proposal` chiamato una volta.
    3. `test_propose_meals_nel_passato_lo_dice_a_claude`: `is_error` con la frase `PAST`, niente salvato.
    4. `test_propose_changes_per_i_posti`: due pasti ufficiali, una voce `to: "finished"` → scheda con le righe, `on_card` chiamato.
    5. `test_propose_changes_su_un_posto_vuoto`: `is_error` con «Nessun pasto in …».
    6. `test_propose_changes_dal_piatto_senza_posti`: in `dish_tools` con `ctx.meal_id`, senza `meals` → scheda per quel pasto.
    7. `test_propose_changes_una_bozza_senza_dispensa`: `is_error` con il messaggio `LIST_ONLY`.
    8. `test_recipe_tools_non_riscrive_una_ricetta_a_mano`: pasto con una ricetta scritta col modulo, `ctx.create_only=True` → `write_recipe` `is_error` «Il pasto ha già una ricetta: non riscriverla.», la ricetta è intatta; su un pasto senza ricetta scrive, e una seconda `write_recipe` nello stesso giro riscrive la sua.
    9. `test_fake_per_call`: `FakeClaude.per_call(a, b)` usa `a` poi `b`; una terza `run` → `AssertionError`.
- [ ] **Step 2: Falliscono.** Il comando di pytest con i tre file. Expected: FAIL.
- [ ] **Step 3: Il codice.** Il commento del piano 3 accanto a `DISH_PANTRY_RULE` se ne va con lei; quello in `dish_tools` dice ora che la scheda è `propose_changes`.
- [ ] **Step 4: Passano.** I tre file, poi la suite intera (i test di `test_meal_chat_turn.py` del piano 3 che confrontano il prompt usano `dish_system_prompt`, quindi seguono). Expected: PASS.
- [ ] **Step 5: Commit** — `feat(pasti): il prompt della pianificazione e la regola delle schede; propose_meals e propose_changes, anche dalla chat del piatto`.

---

### Task 7: Il giro della pianificazione

**Files:**
- Modify: `backend/app/services/meal_chat.py` (`run_chat_turn`, `TurnSpec`, `run_dish_turn` involucro; la vista dei messaggi con `proposals` e `cards`), `backend/app/services/llm.py`, `backend/app/domain/spending.py`, `backend/app/domain/meal_chat.py` (costanti)
- Create: `backend/app/services/planning_chat.py`, `backend/tests/services/test_planning_turn.py`

**Interfaces:**
- Consumes: Task 5–6; il giro del piano 3.
- Produces, in `app.domain.meal_chat`: `PLANNING_EFFORT = "high"`, `PLANNING_MAX_TURNS = 20`, `RECIPE_EFFORT = "medium"`, `RECIPE_MAX_TURNS = 12`.
- Produces, in `app.services.meal_chat`:
  - `@dataclass(frozen=True) class TurnSpec`: `call_site: LlmCallSite`, `effort: Effort`, `max_turns: int`, `allowed: Callable[[AsyncSession, Conversation], Awaitable[bool]]` (il pasto c'è e può chattare; per la pianificazione, sempre), `prepare: Callable[[AsyncSession, Conversation, ConversationMessage, TurnContext], Awaitable[tuple[str, str, list[SdkMcpTool]]]]` (prompt di sistema, prompt, strumenti), `view: Callable[[AsyncSession, Conversation, bool, datetime], Awaitable[BaseModel]]`.
  - `async def run_chat_turn(session_factory, client, *, conversation_id, user_message_id, emit, timeout_seconds, spec: TurnSpec) -> None` — i passi del giro del piano 3, uguali, con `spec` al posto delle scelte del piatto; `on_proposal` e `on_card` emettono gli eventi `proposal` (`{"proposal": MealProposalOut}`) e `card` (`{"card": ChangeCardOut}`).
  - `DISH_TURN: TurnSpec`; `run_dish_turn(...)` = `run_chat_turn(..., spec=DISH_TURN)`, stessa firma.
  - `async def chat_messages_out(session, conversation, *, now) -> list[ChatMessageOut]` — la costruzione dei messaggi della vista del piatto, estratta, che attacca a ogni messaggio le modifiche, le proposte e le schede del suo giro (sotto la risposta, o sotto il messaggio dell'utente se la risposta non c'è).
- Produces, in `app.services.planning_chat`: `PLANNING_TURN: TurnSpec` (`MEAL_PLANNING`, `PLANNING_EFFORT`, `PLANNING_MAX_TURNS`, `planning_system_prompt(await utensils_prompt_block(session))`, `render_planning_prompt` con l'ultima proposta aperta e il posto di partenza, `planning_tools`); `async def run_planning_turn(session_factory, client, *, conversation_id, user_message_id, emit, timeout_seconds) -> None`; `async def planning_view(session, conversation: Conversation | None, *, replying: bool, now: datetime) -> PlanningChatOut` (schema nel Task 9: crealo qui, come il piano 3 fa con `DishChatOut`).
- In `LlmCallSite`: `MEAL_PLANNING`, `MEAL_RECIPE`; in `CALL_SITE_LABELS` e `PLAN_CALL_SITES` come nella decisione 27.

- [ ] **Step 1: I test che falliscono.** `tests/services/test_planning_turn.py`, con `FakeClaude` e la `session_factory` del piano 3:
  1. `test_un_giro_di_pianificazione_che_propone`: copione `UseTool("propose_meals", {...}), Say("Ecco tre cene."), Finish(input_tokens=3000, output_tokens=400)`. Gli eventi: `proposal`, dei `delta`, `done`; nella vista la proposta è sotto la risposta di Claude; `llm_calls` ha una riga `meal_planning` con i token e `cost_usd` NULL.
  2. `test_il_giro_usa_sforzo_e_strumenti_della_pianificazione`: `effort == "high"`, `max_turns == 20`, i sei strumenti, il prompt di sistema uguale a `planning_system_prompt(...)`.
  3. `test_il_limite_a_meta_lascia_la_proposta`: copione `UseTool("propose_meals", …), Fail(PLAN_LIMIT, resets_at=…)` → evento `error` con l'avviso; il messaggio è `failed`; la proposta è `open`, sotto il messaggio dell'utente nella vista, e `place_proposal` la mette nella settimana.
  4. `test_la_scheda_dopo_la_messa`: dopo una messa, un giro con il `follow_up` e il copione `UseTool("propose_changes", …)` → evento `card`, e la scheda è sotto la risposta.
  5. `test_la_chat_del_piatto_resta_quella_di_prima`: i test di `tests/services/test_meal_chat_turn.py` del piano 3 passano senza cambi (si lancia quel file); e un giro del piatto con `UseTool("propose_changes", …)` emette `card`.
  6. `test_la_storia_della_pianificazione_torna_nel_prompt`: il secondo giro contiene «Proposta: … — aperta» del primo.
- [ ] **Step 2: Falliscono.** Il comando di pytest con il file. Expected: FAIL.
- [ ] **Step 3: Il codice.** Prima l'estrazione di `run_chat_turn` con `tests/services/test_meal_chat_turn.py` verde a ogni passo; poi la pianificazione.
- [ ] **Step 4: Passano.** Il file, i due file di test del giro del piano 3, poi la suite intera (`test_ogni_sezione_del_client_llm_ha_un_nome_a_video` compreso). Expected: PASS.
- [ ] **Step 5: Commit** — `feat(pasti): il giro della pianificazione — lo stesso giro del piatto con un'altra specie, proposte e schede sotto i messaggi`.

---

### Task 8: Le ricette dei pasti ufficiali, in coda

**Files:**
- Create: `backend/app/services/recipe_jobs.py`, `backend/tests/services/test_recipe_jobs.py`, `backend/tests/api/test_meal_recipe_ask.py`
- Modify: `backend/app/api/meals.py` (`meal_out` e la rotta nuova), `backend/app/schemas/meal.py`

**Interfaces:**
- Consumes: Task 5–7; `write_meal_recipe` tramite `write_recipe_tool` con `create_only`; `failure_notice`, `claude_configured`.
- Produces, in `app.services.recipe_jobs`:
  - `INTERRUPTED_RECIPE_NOTICE = "La ricetta non è arrivata: chiedila di nuovo a Claude o scrivila a mano."`; `NOT_WRITTEN_NOTICE = "Claude ha risposto senza scrivere la ricetta: chiedila di nuovo o scrivila a mano."`; `TERMINAL_FAILURES = frozenset({FailureKind.PLAN_LIMIT, FailureKind.AUTH, FailureKind.NOT_CONFIGURED})`.
  - `async def generate_meal_recipe(session_factory, client, *, meal_id, conversation_id: uuid.UUID | None, timeout_seconds: float) -> FailureKind | None` — un giro: rilegge il pasto (sparito, non ufficiale, fuori casa, avanzo, o già con una ricetta → pulisce `recipe_requested_at` e torna `None` senza chiamare Claude); `recipe_system_prompt`, `render_recipe_prompt` con la storia della conversazione, `recipe_tools` con `create_only=True` e `conversation_id`/`turn_message_id` nulli, `RECIPE_EFFORT`, `RECIPE_MAX_TURNS`, tempo massimo; registra `llm_calls` `meal_recipe`. Alla fine: se il pasto ha una ricetta, `recipe_requested_at` e `recipe_notice` nulli; se no, `recipe_requested_at` nullo e `recipe_notice` = `failure_notice(...)` del guasto, o `NOT_WRITTEN_NOTICE`. Un commit per pasto.
  - `class RecipeJobs`: `def enqueue(self, meal_ids: Sequence[uuid.UUID], conversation_id: uuid.UUID | None, run: Callable[...]) -> None`; `def live_ids(self) -> frozenset[uuid.UUID]`; `async def wait_idle(self) -> None`. Un `asyncio.Lock` fa girare una coda alla volta; dentro, un pasto alla volta; un guasto in `TERMINAL_FAILURES` scrive lo stesso avviso su tutti i pasti rimasti della coda (`recipe_requested_at` nullo) e la chiude. Istanza di modulo e `get_recipe_jobs()`.
  - `async def settle_orphans(session, meals: Sequence[Meal], live: frozenset[uuid.UUID]) -> bool` — decisione 16; torna se ha scritto.
- Produces, in `MealOut`: `recipe_state: Literal["none", "preparing", "failed"]` (`preparing` se il pasto è in `live_ids`; `failed` se non ha ricetta e ha `recipe_notice`), `recipe_notice: str | None`, `can_ask_recipe: bool` (ufficiale, non fuori casa, non avanzo, senza ricetta, non `preparing`). `WeekOut.preparing: bool` (qualche pasto della settimana è `preparing`). Le letture della settimana e del pasto chiamano `settle_orphans` e, se ha scritto, fanno `commit`.
- Produces, la rotta `POST /api/v1/meals/{meal_id}/recipe/ask` → 202 `MealOut` (`preparing`). Prima di scrivere: 404; 503 `{"code": "claude_not_configured", "detail": <avviso NOT_CONFIGURED>}`; 409 `{"code": "recipe_preparing", "detail": "La ricetta è già in preparazione."}`; il `MealRefusal` di `check_can_take_recipe` con `meal_refusal_response`. Poi `recipe_requested_at`, `recipe_notice` nullo, `commit`, `enqueue([meal.id], conversation_for_meal(...))`.
- La rotta della messa (Task 9) mette in coda i pasti ufficiali appena messi; se Claude non è collegato, invece, scrive su di loro l'avviso `NOT_CONFIGURED` e nessun `recipe_requested_at`.

- [ ] **Step 1: I test che falliscono.**
  - `tests/services/test_recipe_jobs.py`:
    1. `test_tre_pasti_tre_ricette`: `FakeClaude.per_call` con tre copioni `UseTool("write_recipe", …), Say("fatta"), Finish()`; dopo `wait_idle`, i tre pasti hanno una ricetta `ai`, fuori dal ricettario, e nessun `recipe_notice`; `llm_calls` ha tre righe `meal_recipe`; il prompt di sistema è `recipe_system_prompt(...)`, lo sforzo `medium`.
    2. `test_il_limite_a_meta_lascia_ogni_pasto_usabile`: copioni `[ok, Fail(PLAN_LIMIT, resets_at=…)]` per tre pasti → il primo ha la ricetta; il secondo e il terzo no, con `recipe_notice` uguale all'avviso del limite con l'ora, `recipe_requested_at` nullo e `can_ask_recipe` vero in `meal_out`; il finto è stato chiamato **due** volte.
    3. `test_un_guasto_del_singolo_passa_al_dopo`: `[Hang(), ok]` con un tempo massimo di 0,2 s → il primo ha l'avviso del tempo massimo, il secondo la ricetta.
    4. `test_senza_write_recipe`: copione `Say("ecco"), Finish()` → `NOT_WRITTEN_NOTICE`.
    5. `test_la_ricetta_scritta_a_mano_nel_frattempo_resta`: il pasto riceve una ricetta col modulo prima che la coda arrivi a lui → niente chiamata a Claude per quel pasto, ricetta intatta, nessun avviso.
    6. `test_una_preparazione_orfana_diventa_un_avviso`: un pasto con `recipe_requested_at` e nessuna coda viva → `settle_orphans` scrive `INTERRUPTED_RECIPE_NOTICE`; `meal_out` dà `failed`.
    7. `test_il_giro_della_ricetta_sa_cosa_si_e_detto`: con una conversazione che contiene «ho preso il salmone», il prompt del giro lo contiene.
  - `tests/api/test_meal_recipe_ask.py`: `test_chiedere_la_ricetta` (202, `recipe_state == "preparing"`, poi dopo `wait_idle` la ricetta); `test_senza_token_503_e_niente_scritto`; `test_due_volte_e_409`; `test_chi_non_puo_avere_una_ricetta` (bozza, fuori casa → il rifiuto del piano 2); `test_la_settimana_dice_se_qualcosa_e_in_preparazione` (`preparing` vero mentre il finto è fermo su un `asyncio.Event`, falso dopo).
- [ ] **Step 2: Falliscono.** Il comando di pytest con i due file. Expected: FAIL.
- [ ] **Step 3: Il codice.** La docstring di `RecipeJobs` dice la decisione 15 (un pasto alla volta, perché; cosa ferma la coda) e perché ogni pasto si committa da sé.
- [ ] **Step 4: Passano.** I due file, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(pasti): le ricette dei pasti ufficiali scritte da Claude in coda, una alla volta — un'interruzione lascia ogni pasto usabile`.

---

### Task 9: Le rotte della pianificazione

**Files:**
- Create: `backend/app/schemas/planning.py`, `backend/app/api/planning.py`, `backend/tests/api/test_planning.py`
- Modify: `backend/app/api/meal_chat.py` (`start_turn_stream` estratto), `backend/app/schemas/meal_chat.py` (`ChatMessageOut.proposals`, `.cards`), `backend/app/main.py`, `frontend/nginx.conf`, `backend/tests/test_nginx_chat.py`

**Interfaces:**
- Produces, in `app.schemas.planning`:
  - `ProposalRowOut`: `day: date`, `slot: MealSlot`, `dish: str`, `sides: str | None`, `effect: Literal["new", "officialize", "replace"]`, `occupant: MealRefOut | None`, `meal_id: uuid | None`.
  - `MealProposalOut`: `id`, `kind: Literal["official", "draft"]`, `status: Literal["open", "placed", "superseded"]`, `rows: list[ProposalRowOut]`, `created_at`.
  - `PlanningChatOut`: `conversation_id: uuid | None`, `focus: FocusOut | None` (`day`, `slot`), `messages: list[ChatMessageOut]`, `replying: bool`, `concluded: bool`, `claude_ready: bool`, `claude_notice: str | None`.
  - `PlanningCreateIn` / `FocusIn`: `focus: FocusIn | None = None`; `PlaceIn`: `replace: bool = False`; `PlaceOut`: `chat: PlanningChatOut`, `meals: list[MealOut]`, `follow_up: str`.
- Produces, in `app.api.meal_chat`: `async def start_turn_stream(session, registry, client, session_factory, *, conversation, body: ChatMessageIn, run, settings) -> StreamingResponse` — i controlli e lo stream della `POST` del piano 3 (503 prima di salvare; 409 `claude_busy`; `retry_of` con `move_turn_products` prima di cancellare il fallito; il messaggio `pending`; `registry.start`; `event: start`, gli eventi, `: ping`), usato dalla chat del piatto e da quella di pianificazione.
- Produces, in `app.api.planning` (`prefix="/api/v1/planning"`, dietro la sessione):
  - `GET /current` → `PlanningChatOut` dell'ultima conversazione se non è conclusa, altrimenti la vista vuota (`conversation_id: null`).
  - `POST /conversations` (`PlanningCreateIn`) → 201 `PlanningChatOut` («Nuova», anche con il posto).
  - `GET /conversations/{id}` → `PlanningChatOut` (404 «conversazione inesistente»; una conversazione `dish` è 404).
  - `PATCH /conversations/{id}` (`{"focus": FocusIn | null}`) → `PlanningChatOut`.
  - `POST /conversations/{id}/messages` (`ChatMessageIn`) → `text/event-stream`, con `start_turn_stream` e `run_planning_turn`.
  - `POST /proposals/{id}/place` (`PlaceIn`) → `PlaceOut`; `PlanningRefusal` → 409 `{"code", "detail", "chat"}` più `"occupants": list[MealOut]` per `slots_taken`. Dopo il `commit`, `enqueue` dei pasti ufficiali (o l'avviso `NOT_CONFIGURED` senza Claude, decisione 15).
- `frontend/nginx.conf`: la `location` del piano 3 per lo streaming diventa `location ~ ^/api/v1/(meals/[^/]+/chat|planning/conversations/[^/]+)/messages$` con gli stessi valori.

- [ ] **Step 1: I test che falliscono.** `tests/api/test_planning.py` (con `logged_client`, `FakeClaude` in `get_claude_client`, la `session_factory` del piano 3):
  1. `test_senza_conversazioni_la_vista_e_vuota`: `GET /current` → `conversation_id is None`, `concluded is False`.
  2. `test_nuova_con_il_posto`: `POST /conversations` `{"focus": {"day": "2026-11-13", "slot": "dinner"}}` → 201 con `focus`; `GET /current` la riapre; `PATCH` con `{"focus": null}` lo toglie.
  3. `test_un_messaggio_che_propone_in_streaming`: eventi `start`, `proposal`, `delta`, `done`; `GET /conversations/{id}` ha la proposta sotto la risposta, con `effect` per ogni riga.
  4. `test_mettere_nella_settimana_e_il_seguito`: `POST /proposals/{id}/place` → 200, `meals` ufficiali con `recipe_state == "preparing"`, `follow_up` col testo del Task 5; dopo `wait_idle` della coda, i pasti hanno la ricetta.
  5. `test_mettere_su_un_posto_occupato_e_409_con_gli_occupanti`: → 409 `slots_taken`, `occupants[0].dish`; con `{"replace": true}` → 200.
  6. `test_mettere_due_volte_e_409`: → 409 `proposal_placed` con `chat`.
  7. `test_senza_token_i_pasti_entrano_con_l_avviso`: token vuoto nelle impostazioni; una proposta già salvata col servizio; la messa → 200, i pasti hanno `recipe_state == "failed"` e l'avviso «Claude non è collegato: manca il token del piano sul server.»; il `POST …/messages` → 503 senza salvare.
  8. `test_riprova_si_porta_dietro_la_proposta`: un giro `UseTool("propose_meals"), Fail(UNAVAILABLE)`, poi `POST …/messages` con `retry_of` e un copione che risponde → un solo messaggio dell'utente e la proposta di prima sotto di lui (o sotto la risposta nuova).
  9. `test_conclusa_e_nuova`: dopo messa e scheda applicata, `GET /current` → vuota; la conversazione si legge ancora da `GET /conversations/{id}` con `concluded: true`.
  10. `test_una_conversazione_del_piatto_non_e_una_pianificazione`: `GET /conversations/{id dish}` → 404.
  11. `test_la_chat_del_piatto_ha_la_sua_scheda`: con il copione `UseTool("propose_changes", …)` sulla chat del piatto, `GET …/chat` ha la scheda sotto la risposta.
  - In `tests/test_nginx_chat.py`: `test_nginx_non_trattiene_la_pianificazione` — la `location` copre i due percorsi (la regex accetta `/api/v1/planning/conversations/<uuid>/messages` e `/api/v1/meals/<uuid>/chat/messages`) con `proxy_buffering off;`.
- [ ] **Step 2: Falliscono.** Il comando di pytest con i due file. Expected: FAIL.
- [ ] **Step 3: Il codice**, come nel blocco Interfaces. Prima l'estrazione di `start_turn_stream` con `tests/api/test_meal_chat.py` del piano 3 verde.
- [ ] **Step 4: Passano.** I due file, `tests/api/test_meal_chat.py`, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(pasti): le rotte della pianificazione — la conversazione da riaprire o nuova, lo streaming, «Metti nella settimana» con il seguito`.

---

### Task 10: La scheda dei cambi nel frontend

**Files:**
- Modify: `frontend/src/domain/types.ts` (tipi in fondo; i campi facoltativi di `Meal`), `frontend/src/App.tsx` (rotta)
- Create: `frontend/src/features/change-cards/api.ts`, `ChangeCard.tsx`, `ChangeCardScreen.tsx`, `PendingCards.tsx` e i loro test

**Interfaces:**
- Produces, in `domain/types.ts`: `ChangeRow`, `ChangeCard`, `MealProposal`, `ProposalRow`, `PlanningChat`, che rispecchiano gli schemi dei Task 4 e 9; in `Meal`: `recipe_state?: "none" | "preparing" | "failed"; recipe_notice?: string | null; can_ask_recipe?: boolean; open_card_id?: string | null`; in `MealWeek`: `preparing?: boolean`.
- Produces, in `change-cards/api.ts`: `cardKey(id) = ["change-card", id]`, `PENDING_CARDS_KEY = ["change-cards", "proposed"]`; `fetchCard(id)`, `fetchPendingCards()`, `applyCard(id, rows: { id: string; checked: boolean; to_status?: PantryStatus }[])`, `discardCard(id)`, `addCardRow(id, body: { pantry_item_id: string } | { raw_text: string })`. Chi scrive invalida `["change-card"]`, `["change-cards"]`, `["meals"]`, e le chiavi di dispensa e lista usate da `PantryScreen` e dalla lista (leggile in `features/pantry/api.ts` e `features/shopping-list/api.ts`).
- Produces: `ChangeCard({ card }: { card: ChangeCard })`, la scheda riusabile (nella pagina e nelle chat); `ChangeCardScreen` su `/pasti/cambi/:id` (`BackLink` a `/pasti` «Pasti», `h1` «Scheda dei cambi», poi `ChangeCard`); `PendingCards()`, il riquadro.

**La scheda** (`ChangeCard`): in testa il `title` e, come `Chip`, i pasti («‹longDayLabel› · ‹Pranzo|Cena›»). Una riga d'intestazione con «Voce», «Ora», «Diventa», e una riga per voce in una griglia che sta in 375 px: una casella (`aria-label` «Applica: ‹voce›», disattivata se non `editable`), la voce, «Ora» (per `pantry` lo `STATUS_LABELS` di `from_status`; per `list` «—», o «già in lista» se `listed`; per `unlist` «in lista»), «Diventa» (per `pantry` un `<select>` con i tre `STATUS_LABELS`, `aria-label` «Diventa: ‹voce›»; per `list` «in lista»; per `unlist` «via dalla lista»), e sotto la `note` se c'è. Le caselle e gli stati si correggono **solo in locale**, e partono con `applyCard` alla fine. Con `status === "proposed"`: «Applica» (primario, `shape="block"`, non pronto mentre la richiesta è in volo) e «Scarta» (`ghost`); sotto, due campi: «Cerca in dispensa» (filtra per nome le voci di `fetchPantry`, escluse quelle già nella scheda; un tocco → `addCardRow({ pantry_item_id })`) e «Aggiungi alla lista» con «Aggiungi» (`addCardRow({ raw_text })`); senza righe, «Nessuna voce: aggiungi quello che il pasto usa, o scarta la scheda.». Con `applied`: «Applicata.» e le righe in sola lettura (le non applicate con la loro nota); con `discarded`: «Scartata.». Avvisi (`useNotice`): «Scheda applicata.», «Scheda scartata.»; un 409 `card_applied` mette la `card` della risposta in cache e dice «La scheda era già applicata.»; gli altri 409 mostrano il `detail` in un `Alert`.

**Il riquadro** (`PendingCards`): se `fetchPendingCards()` non è vuoto, una `Card` con `SectionHeading` «Schede dei cambi da applicare» e una riga per scheda (il titolo e un collegamento «Apri» a `/pasti/cambi/<id>`); vuoto, niente.

- [ ] **Step 1: I test che falliscono.**
  - `ChangeCard.test.tsx`: (1) le intestazioni «Voce», «Ora», «Diventa» e una riga «Ricotta» con «Disponibile» e il `select` su «Finito»; (2) la riga «già in lista» ha la casella disattivata; (3) tolta la spunta al parmigiano e portata la ricotta a «Quasi finito», «Applica» manda `POST /api/v1/change-cards/c1/apply` con `rows` che dicono `checked: false` per il parmigiano e `to_status: "low"` per la ricotta, poi «Scheda applicata.»; (4) **«Applica» toccato due volte manda una richiesta sola**; (5) un 409 `card_applied` → «La scheda era già applicata.» e «Applicata.»; (6) «Scarta» → `POST …/discard` e «Scheda scartata.»; (7) scheda vuota → la frase vuota; «Cerca in dispensa» con «parm» mostra «Parmigiano», un tocco manda `POST …/rows` con `{ pantry_item_id }`; (8) una scheda applicata mostra «Applicata.» e nessun «Applica».
  - `PendingCards.test.tsx`: due schede → «Schede dei cambi da applicare» e due «Apri» con i loro `href`; nessuna → niente a video.
  - `ChangeCardScreen.test.tsx`: su `/pasti/cambi/c1` il titolo «Scheda dei cambi» e la scheda.
- [ ] **Step 2: Falliscono.** `npx vitest run src/features/change-cards`. Expected: FAIL.
- [ ] **Step 3: Il codice** del blocco Interfaces. Nessuna regola nel client: «Ora», le note, chi è `editable` arrivano dal server.
- [ ] **Step 4: Passano.** `npx vitest run`, `npm run typecheck`, `npm run lint`. Expected: verdi.
- [ ] **Step 5: Commit** — `feat(pasti): la scheda dei cambi nell'app — voce, ora, diventa, una casella per riga, «Applica» una volta sola`.

---

### Task 11: La chat di pianificazione

**Files:**
- Create: `frontend/src/features/planning/api.ts`, `PlanningScreen.tsx`, `ProposalCard.tsx` e i loro test
- Modify: `frontend/src/features/meal-chat/ChatThread.tsx` (`renderExtras`), `frontend/src/features/meal-chat/sse.ts` e `domain/types.ts` (gli eventi `proposal`/`card`, il tipo generico), `frontend/src/features/meals/WeekScreen.tsx` (il commento del piano 2 in fondo diventa «Pianifica con Claude»; `PendingCards` in testa), `frontend/src/features/meals/NewMealScreen.tsx` (il commento del piano 2 diventa «Chiedilo a Claude»), `frontend/src/App.tsx` (`/pasti/pianifica` sopra `/pasti/:id`)

**Interfaces:**
- Produces, in `planning/api.ts`: `PLANNING_KEY = ["planning"]`; `fetchCurrentPlanning()`, `fetchPlanning(id)`, `createPlanning(focus?)`, `setPlanningFocus(id, focus | null)`, `sendPlanningMessage(id, body, onEvent)` (`apiStream` + `readSse`), `placeProposal(id, replace: boolean): Promise<PlaceResult>`.
- Produces: `PlanningScreen` su `/pasti/pianifica` (`?conversazione=<id>`, `?giorno=…&posto=…`); `ProposalCard({ proposal, onPlaced })`.

**La schermata** (`PlanningScreen`): `BackLink` a `/pasti` «Pasti», `h1` «Pianifica con Claude», un pulsante `ghost` «Nuova» (→ `createPlanning()`, poi `?conversazione=<id>` con `replace`). Si apre su `?conversazione` se c'è, altrimenti su `fetchCurrentPlanning()`. Con `?giorno&posto`: se c'è una conversazione la punta lì (`setPlanningFocus`), altrimenti ne crea una con il posto; poi l'indirizzo diventa `?conversazione=<id>`, e il campo si precompila con «Cosa mi proponi per ‹longDayLabel› a ‹pranzo|cena›?». Il posto si mostra come `Chip` «Per: ‹longDayLabel› · ‹Pranzo|Cena›» con un pulsante «Togli il posto» (`aria-label`). Se `claude_ready` è falso, l'`Alert` con `claude_notice` in testa. Vuota: «Dimmi come vuoi pianificare: con quello che c'è in casa, o una bozza prima della spesa.». Poi `ChatThread` (gli stessi fumetti del piatto) con `renderExtras` che rende, sotto ogni messaggio, le sue `ProposalCard` e `ChangeCard`; il campo e «Invia» come in `DishChat` (stesse regole: il testo torna nel campo su 503/409; «Riprova»). Il primo messaggio senza conversazione la crea prima (`createPlanning`). Gli eventi `proposal` e `card` compaiono subito sotto il fumetto che si sta scrivendo; `done`/`error` mettono la vista in cache.

**La proposta** (`ProposalCard`): intestazione «Proposta» (o «Bozza per la spesa» con `kind === "draft"`); una riga per posto: «‹longDayLabel› · ‹Pranzo|Cena›», il piatto, gli accompagnamenti, e per `effect` `replace` «Al posto di «‹occupante›»», per `officialize` «La bozza «‹occupante›» diventa ufficiale». Con `status === "open"`, «Metti nella settimana» (primario, `shape="block"`, non pronto mentre la richiesta è in volo) → `placeProposal(id, false)`. Un 409 `slots_taken` apre sotto la conferma: «Questi posti sono occupati:», una riga «‹longDayLabel› · ‹Pranzo|Cena›: «‹piatto›»» per occupante, «Sostituisci e metti» (→ `placeProposal(id, true)`) e «Annulla». Riuscita: avviso «Pasti messi nella settimana.», invalidazione di `["meals"]` e `PLANNING_KEY`, e `onPlaced(result.follow_up)`, che la schermata **invia subito** come messaggio. Un 409 `proposal_placed` mette la `chat` in cache senza errore. Con `placed`: «Messa nella settimana.»; con `superseded`: «Sostituita da una proposta più nuova.».

**Gli ingressi**: in fondo a `WeekScreen` un collegamento a forma di pulsante primario «Pianifica con Claude» a `/pasti/pianifica`, e in testa `PendingCards`. In `NewMealScreen`, sopra il modulo, un collegamento a forma di pulsante secondario «Chiedilo a Claude» a `/pasti/pianifica?giorno=<giorno>&posto=<slot>`.

- [ ] **Step 1: I test che falliscono.**
  - `sse.test.ts`, un caso: gli eventi `proposal` e `card` arrivano interi.
  - `ChatThread.test.tsx`, un caso: con `renderExtras` il suo contenuto sta sotto il messaggio giusto; senza, niente cambia (i test di oggi restano verdi).
  - `ProposalCard.test.tsx`: (1) righe con giorno, piatto, accompagnamenti, «Al posto di «Pizza»» e «La bozza «Pasta» diventa ufficiale»; (2) «Metti nella settimana» → `POST /api/v1/planning/proposals/p1/place` con `{ replace: false }`, avviso «Pasti messi nella settimana.» e `onPlaced` con il `follow_up`; (3) un 409 `slots_taken` → «Questi posti sono occupati:», «Sostituisci e metti» rimanda con `{ replace: true }`; (4) toccato due volte, una richiesta sola; (5) `placed` → «Messa nella settimana.» e nessun pulsante.
  - `PlanningScreen.test.tsx`: (1) senza conversazione, la frase vuota e «Invia» crea la conversazione e poi manda il messaggio; (2) con `?giorno=2026-11-13&posto=dinner` e nessuna conversazione → `POST /api/v1/planning/conversations` con il `focus`, il `Chip` «Per: venerdì 13 novembre · Cena» e il campo con «Cosa mi proponi per venerdì 13 novembre a cena?»; (3) uno stream con `proposal` → la `ProposalCard` sotto il fumetto prima di `done`; (4) dopo la messa, il `follow_up` parte come `POST …/messages`; (5) «Nuova» → `POST /api/v1/planning/conversations` e l'indirizzo con il nuovo id; (6) 503 → l'`Alert` e il testo nel campo.
  - `WeekScreen.test.tsx`, un caso: «Pianifica con Claude» porta a `/pasti/pianifica`, e con una scheda proposta si legge «Schede dei cambi da applicare». `NewMealScreen.test.tsx`, un caso: «Chiedilo a Claude» ha `href` `/pasti/pianifica?giorno=2026-11-10&posto=lunch`.
- [ ] **Step 2: Falliscono.** `npx vitest run src/features/planning src/features/meal-chat src/features/meals`. Expected: FAIL.
- [ ] **Step 3: Il codice** del blocco Interfaces. `PlanningScreen` riusa `ChatThread` e la logica d'invio di `DishChat`: se in `DishChat` è dentro il componente, estraila in un hook comune `useChatSender` in `features/meal-chat/` (stessi test verdi), invece di copiarla.
- [ ] **Step 4: Passano.** `npx vitest run`, `npm run typecheck`, `npm run lint`. Expected: verdi.
- [ ] **Step 5: Commit** — `feat(pasti): «Pianifica con Claude» — la chat a tutta pagina, la proposta con «Metti nella settimana», «Chiedilo a Claude» dal posto vuoto`.

---

### Task 12: La ricetta in preparazione, e la scheda nel piatto

**Files:**
- Modify: `frontend/src/features/meals/MealScreen.tsx`, `frontend/src/features/meals/WeekScreen.tsx`, `frontend/src/features/meals/api.ts` (`askMealRecipe`), `frontend/src/features/meal-chat/DishChat.tsx`, i loro test

**Interfaces:**
- Produces: `askMealRecipe(id): Promise<Meal>` (`POST /api/v1/meals/<id>/recipe/ask`).
- In `WeekScreen`: un pasto con `recipe_state === "preparing"` ha il `Chip` «Ricetta in preparazione»; la query della settimana ha `refetchInterval: 3000` finché `week.preparing` è vero.
- In `MealScreen` (ufficiale, senza ricetta, non avanzo):
  - `preparing` → al posto dei pulsanti, «Ricetta in preparazione: arriva fra poco.» in un `aria-live="polite"`; la query del pasto si rilegge ogni 3 s finché dura;
  - altrimenti, sotto «Questo pasto non ha ancora una ricetta.»: se `recipe_notice`, un `Alert` con l'avviso; se `can_ask_recipe`, «Chiedi la ricetta a Claude» (secondario) accanto a «Scrivi la ricetta» e «Scegli dal ricettario» (piano 2). Il tocco → `askMealRecipe`, avviso «Ricetta chiesta a Claude.»; un 503 o 409 mostra il `detail` in un `Alert` e i pulsanti restano.
  - `open_card_id` → un collegamento «Scheda dei cambi da applicare» a `/pasti/cambi/<id>`, sotto l'intestazione.
  - «Rendi ufficiale» (piano 2): riuscito, se la risposta ha `open_card_id`, `navigate("/pasti/cambi/<id>")`.
- In `DishChat`: `renderExtras` rende le `ChangeCard` sotto i messaggi.

- [ ] **Step 1: I test che falliscono.**
  - `MealScreen.test.tsx`: (1) `preparing` → «Ricetta in preparazione: arriva fra poco.» e nessun «Scrivi la ricetta»; (2) `failed` con l'avviso del limite → l'avviso, «Chiedi la ricetta a Claude», «Scrivi la ricetta», «Scegli dal ricettario»; il tocco → `POST /api/v1/meals/m1/recipe/ask` e «Ricetta chiesta a Claude.»; (3) un 503 → l'`Alert` con il `detail`; (4) `open_card_id` → «Scheda dei cambi da applicare» con l'`href`; (5) «Rendi ufficiale» → `PATCH`, poi `/pasti/cambi/c9`.
  - `WeekScreen.test.tsx`: un pasto `preparing` mostra «Ricetta in preparazione».
  - `DishChat.test.tsx`: un messaggio con una scheda mostra «Applica» sotto il fumetto.
- [ ] **Step 2: Falliscono.** `npx vitest run src/features/meals src/features/meal-chat`. Expected: FAIL.
- [ ] **Step 3: Il codice** del blocco Interfaces.
- [ ] **Step 4: Passano.** `npx vitest run`, `npm run typecheck`, `npm run lint`, `npm run build`. Expected: verdi.
- [ ] **Step 5: Commit** — `feat(pasti): «Ricetta in preparazione» e «Chiedi la ricetta a Claude»; la scheda dei cambi dal piatto e dopo «Rendi ufficiale»`.

---

### Task 13: Nel browser vero, a 375 px, nei due temi

**Files:**
- Create: `backend/tests/e2e_planning.py`, `backend/tests/test_e2e_planning_guard.py`, `frontend/e2e/pianificazione.spec.ts`
- Modify: `frontend/e2e/style.spec.ts` (`"/pasti/pianifica"` nell'elenco `SCHERMATE`; tre prove **in fondo al file**)

Lo stack e2e non ha il token: la chat vera risponde 503, ed è §9. Le proposte e le schede di Claude non si raggiungono senza Claude: le semina `backend/tests/e2e_planning.py`, sul modello di `backend/tests/e2e_chat.py` del piano 3 (guardia `SPENA_E2E=1`, lanciato da Playwright con `execFileSync` e `COMPOSE_E2E`), **passando dai servizi veri** (`create_planning`, i messaggi del repository, `propose_meals`, `propose_card`, `stock_one` per le voci di dispensa), mai con SQL crudo.

- [ ] **Step 1: Lo script e la sua guardia.** `e2e_planning.py seed|clean`. `seed` crea, su posti lontani da quelli delle altre prove (dal giorno +30 al +33, nel giorno di Roma), con ingredienti e voci di dispensa il cui nome comincia per «e2e-plan» (una «e2e-plan ricotta», una «e2e-plan parmigiano»): una conversazione di pianificazione con un messaggio di Mattia e la risposta di Claude, una proposta `draft` aperta per due posti, e una proposta `official` aperta per un terzo posto, legata a un messaggio successivo; poi un pasto ufficiale al giorno +33 con una scheda **proposta** (ricotta → «Finito», parmigiano → «Quasi finito», la ricotta in lista). Stampa il JSON `{"conversation": …, "proposal_draft": …, "proposal_official": …, "card": …, "meal": …}`; `clean` toglie i pasti dei posti seminati, le conversazioni, le schede, le voci di lista e di dispensa «e2e-plan» e i loro ingredienti. `test_e2e_planning_guard.py` ricalca `test_e2e_chat_guard.py`.
- [ ] **Step 2: Le prove funzionali**, `frontend/e2e/pianificazione.spec.ts` (375×812):
  1. **«senza token la pianificazione lo dice, e il testo resta»**: dalla settimana, «Pianifica con Claude» → `/pasti/pianifica`, l'`Alert` «Claude non è collegato: manca il token del piano sul server.»; scritto «una settimana leggera» e «Invia», il campo lo contiene ancora. «Nuova» c'è.
  2. **«la bozza entra nella settimana»**: `seed`; su `/pasti/pianifica?conversazione=<id>` la proposta «Bozza per la spesa» → «Metti nella settimana» → «Pasti messi nella settimana.»; il seguito parte e torna nel campo con l'avviso (niente token); nella settimana del giorno +30 i due pasti hanno «Bozza». Nel `finally`, `clean`.
  3. **«la scheda dei cambi si corregge e si applica una volta»**: `seed`; su `/pasti/cambi/<card>` si toglie la spunta al parmigiano e «Applica» → «Scheda applicata.» e «Applicata.»; `GET /api/v1/pantry` ha la ricotta «finished» e il parmigiano com'era; `GET /api/v1/shopping-list` ha **una** «e2e-plan ricotta».
  4. **«togliere il pasto propone la scheda inversa»**: (dopo la prova 3, stesso seme) «Elimina» del pasto → nella settimana «Schede dei cambi da applicare» con «Hai tolto «‹piatto›»: rimetti quello che usava?» → «Apri» → «Applica» → la ricotta è di nuovo «available» e la voce in lista non è più attiva.
  5. **«una bozza resa ufficiale a mano apre la scheda vuota»**: uno dei pasti della prova 2, «Rendi ufficiale» → `/pasti/cambi/<id>` con «Nessuna voce: aggiungi quello che il pasto usa, o scarta la scheda.»; «Cerca in dispensa» «e2e-plan parm» → la riga → «Applica»; il pasto ha «Chiedi la ricetta a Claude» e «Scrivi la ricetta».
- [ ] **Step 3: Le prove di stile, in fondo a `style.spec.ts`.** Con `seed` e `clean` nel `finally`, a 375×812, per `"light"` e `"dark"`: `fermo`, `testiIlleggibili(page)` è `[]`, `scrollWidth <= clientWidth`, e i bersagli nominati alti almeno 44 px.
  1. **«la pianificazione con le proposte, nei due temi»**: `/pasti/pianifica?conversazione=<id>`; «Metti nella settimana» e «Invia».
  2. **«la scheda dei cambi, nei due temi»**: `/pasti/cambi/<card>`; «Applica», «Scarta» e le caselle (il loro contenitore cliccabile) alti almeno 44 px; il `select` leggibile.
  3. **«la settimana con le schede da applicare e il piatto con l'avviso della ricetta, nei due temi»**: una scheda proposta e un pasto con `recipe_notice` (seminato con l'avviso del limite); `/pasti` con «Schede dei cambi da applicare» e `/pasti/<id>` con l'avviso e «Chiedi la ricetta a Claude».
- [ ] **Step 4: Typecheck e lint**, `npm run typecheck && npm run lint`. Expected: puliti.
- [ ] **Step 5: L'e2e intera** su uno stack ricreato da zero, con i comandi delle Global Constraints. Expected: tutto verde, le prove nuove comprese. **Annota** `N_e2e`. Poi `down -v` e `rm .env`, sempre. Un testo illeggibile si corregge con un altro token esistente, mai con un token nuovo; se nessuno basta, `bloccato` con la misura.
- [ ] **Step 6: Commit** — `pasti: nel browser vero — la pianificazione senza token, la bozza nella settimana, la scheda applicata una volta, l'inversa, il contrasto a 375 px nei due temi`.

---

### Task 14: I documenti, la verifica finale e il report

**Files:**
- Modify: `CLAUDE.md`, `docs/prossimi-passi.md`, `next-steps.md`
- Create o modify: `docs/night-reports/<data di oggi>.md`

- [ ] **Step 1: `CLAUDE.md`.** In «Conventions worth knowing», dopo il paragrafo «**A recipe written for a meal stays out of the recipe book**» del piano 2, aggiungi:
  ```
  **Claude proposes, Mattia applies.** No Claude tool writes the pantry or the shopping
  list: the meal planning and the dish chat send a change card (`propose_changes`), one
  row per pantry item and per ingredient to buy, with the state it becomes, and Mattia
  ticks, corrects and applies it (`backend/app/services/change_cards.py`). Applying is
  one transaction that locks the card first, through `set_status` and `add_item` — the
  one rule against duplicates in the list — and keeps the state each item had before.
  That is what makes the inverse possible without quantities: when an official meal is
  deleted, replaced or goes «fuori casa», spena itself proposes the inverse card, never
  restoring what another meal still uses, what changed since, or what was bought again.
  A `low` sauce is a started jar: only a row that becomes `finished` brings its list row
  along. Planned meals arrive from a proposal card («Metti nella settimana»); their
  recipes are written afterwards by an in-process queue, one meal at a time, each in its
  own transaction, so a plan limit halfway leaves every meal usable by hand. Spec:
  `docs/superpowers/specs/2026-11-12-pasti-claude-design.md` §5.2, §6.2.
  ```
  E nel paragrafo «A second path to a model» del piano 3, la frase sulle chiamate in `llm_calls` nomina anche `meal_planning` e `meal_recipe`.
- [ ] **Step 2: `docs/prossimi-passi.md`.** In coda alla nota «Sostituita il 2026-11-12» della Parte IV: «Il quarto e ultimo pezzo — la pianificazione con Claude, la bozza e l'ufficializzazione, le schede dei cambi e la scheda inversa — è sul ramo `night/pasti-pianificazione` (<data di oggi>, da revisionare). La skill `pasti` resta finché la sezione non è in produzione e provata.»
- [ ] **Step 3: `next-steps.md`.**
  1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte: sezione Pasti, piano 4 di 4)_`.
  2. La voce «Sezione Pasti» **esce** dalla sua sezione (`grep -n "Sezione Pasti" next-steps.md`), e in cima a «Fatti (recenti)» va:
     ```markdown
     - [fatto] <data di oggi> · Sezione Pasti, piani 1–4: utensili; la settimana e i pasti a mano con le ricette fuori dal ricettario; la chat con Claude sotto ogni piatto; la pianificazione con Claude nei due giri (con quello che c'è, e bozza prima della spesa con l'ufficializzazione dopo «Sistema la spesa»), le ricette scritte dopo l'ufficializzazione, le schede dei cambi a dispensa e lista e la scheda inversa [Parte IV] → branch night/utensili, night/pasti-settimana, night/pasti-claude, night/pasti-pianificazione, da unire in quest'ordine (da revisionare)
     ```
     Se un task di questo piano è rimasto `bloccato`, la voce resta dov'è, passa a `bloccato` con «attende: …», e la riga qui sopra non si scrive.
  3. In «Da fare a mano (solo Mattia)», nello stile della sezione: «Dopo il deploy dei Pasti con Claude: provare il giro completo bozza → spesa → ufficializzazione (bozza della settimana, scheda della lista applicata, spesa, «Sistema la spesa», ufficializzazione con Claude, ricette arrivate, scheda della dispensa applicata), togliere un pasto e applicare la scheda inversa; poi decidere se ritirare o ridurre la skill `pasti` [Parte IV]».
  4. Le voci P1, P2, P3, M1 e H3, se sono ancora nel file, escono (spec §11); scrivi nel report quali hai tolto.
  5. Quel che è emerso nella notte fuori da questo piano va come `idea` o `tbd`, con `[Parte IV]`.
- [ ] **Step 4: La verifica finale.** Da `<worktree>/frontend`: `npx vitest run`, `npm run typecheck`, `npx tsc -b --force`, `npm run lint`, `npm run build`. Expected: verdi; vitest circa **`N_vitest` + 45** in `N_file` + 6 file. Da `<worktree>/backend`, il comando di pytest: verde, circa **`N_pytest` + 120**. Se i numeri differiscono, scrivi nel report da dove viene la differenza. Poi i «Comandi di verifica» con i loro attesi, e l'e2e intera su uno stack ricreato da zero (`N_e2e`), con `down -v` e `rm .env`. Infine `docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_pasti_pianificazione WITH (FORCE)'`.
- [ ] **Step 5: Il report**, in `docs/night-reports/<data di oggi>.md` sul ramo (in fondo, se il file c'è già). Dentro: il ramo e da dove parte (`night/pasti-claude` a `BASE`), la `0021` letta; i conti veri contro la Preparazione; ogni riga del blocco «Cambi alle interfacce» com'è finita nel codice, e i test dei piani precedenti cambiati; le decisioni 11–28 che Mattia può voler rivedere, in particolare: la bozza ufficializzata senza conferma, il seguito mandato dal telefono, la coda delle ricette un pasto alla volta, la riga in lista solo per le voci finite, la scheda inversa che non rimette ciò che serve ancora o che è cambiato, la conversazione «conclusa» calcolata; i posti dove la notte ha scelto da sola; la sezione «Dopo il deploy (solo Mattia)» qui sotto. Niente push, niente merge, niente deploy.
  ```bash
  git add CLAUDE.md docs/prossimi-passi.md next-steps.md docs/night-reports/
  git commit -m "docs: la pianificazione con Claude e le schede dei cambi fatte sul ramo (piano 4 di 4); la sezione Pasti è completa da revisionare"
  ```

---

## Dopo il deploy (solo Mattia)

La notte non tocca la produzione. I quattro rami si uniscono in ordine (`night/utensili`, `night/pasti-settimana`, `night/pasti-claude`, `night/pasti-pianificazione`), dopo la decisione sui termini d'uso del token che il piano 3 chiede in testa.

1. **Il deploy di sempre, con il `-f`**: `docker compose -f docker-compose.prod.yml up -d --build --wait --wait-timeout 120`. Le migrazioni `0019`–`0022` girano all'avvio. Poi `docker compose -f docker-compose.prod.yml exec backend python -m app.cli.check_claude --prova` (piano 3).
2. **Il giro con quello che c'è**: «Pianifica con Claude», «pianifichiamo le cene di domani e dopodomani con quello che ho»; il quadro della settimana, le proposte con il perché; «Metti nella settimana»; nella settimana «Ricetta in preparazione», poi le ricette; in chat la scheda dei cambi: correggere una riga, «Applica»; in dispensa e in lista i cambi, senza doppioni.
3. **Il giro prima della spesa**: «Nuova», «pianifichiamo la settimana prima della spesa»; la bozza nella settimana con «Bozza»; la scheda con le sole righe della lista, «Applica». Fare la spesa e «Sistema la spesa». Poi «Pianifica con Claude» riapre la stessa conversazione: «il merluzzo non c'era, ho preso il salmone»; la proposta ufficiale sulle bozze, «Metti nella settimana» (nessuna conferma per le bozze), le ricette, la scheda della dispensa.
4. **La scheda inversa**: eliminare uno dei pasti ufficiali; in testa alla settimana «Schede dei cambi da applicare»; aprirla, controllare che non rimetta ciò che serve a un altro pasto, «Applica».
5. **Senza Claude** (o col limite del piano): «Rendi ufficiale» su una bozza apre la scheda vuota da compilare; «Scrivi la ricetta» funziona.
6. **La skill `pasti`**: dopo il giro completo, decidere se ritirarla o ridurla (spec §11), e scriverlo in `next-steps.md`.
