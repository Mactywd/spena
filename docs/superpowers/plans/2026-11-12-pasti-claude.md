# Pasti con Claude: la chat del piatto — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Avvertenza per Mattia (non blocca la notte).** La documentazione corrente di Claude Code, letta il 2026-11-12, dice due cose che la spec §3 non cita. In «Legal and compliance» (code.claude.com/docs/en/legal-and-compliance): «Developers building products or services that interact with Claude's capabilities, including those using the Agent SDK, should use API key authentication», e Anthropic non permette di instradare richieste con le credenziali di un piano Pro/Max «on behalf of their users». La pagina dell'Agent SDK ripete che le app di terzi non possono offrire il login di claude.ai né i limiti del piano. Tecnicamente la strada funziona: `claude setup-token` dà un token di un anno, «for CI pipelines and scripts», che l'SDK legge da `CLAUDE_CODE_OAUTH_TOKEN` (pagina «Authentication»). La stessa pagina legale dice anche che i limiti dei piani presuppongono un «ordinary, individual usage of Claude Code and the Agent SDK». Spena ha un solo utente, Mattia, e usa il suo token: la spec lo considera un uso personale (§3, «Mattia ha valutato che l'uso è personale»). **La notte costruisce tutto senza token e senza rete, quindi non si ferma.** Prima del deploy però Mattia deve confermare la scelta, o passare a una chiave API (vedi «Dopo il deploy»).

> **Superata il 2026-11-18.** Mattia ha scelto la chiave API: `docs/superpowers/plans/2026-11-18-pasti-chiave-api.md`. Dal 2026-11-21 il CLI riceve anche `--no-session-persistence`: una garanzia esplicita, provata da sola, perché sul binario 2.1.321 `CLAUDE_CODE_SKIP_PROMPT_HISTORY` ferma le trascrizioni per conto suo ma non è documentata per farlo.

**Goal:** sotto la ricetta di ogni pasto ufficiale c'è una chat con Claude (Opus, via Agent SDK, sul piano di Mattia). Claude legge dispensa, lista, pasti, utensili e anagrafica, e quando la risposta cambia il piatto riscrive direttamente la ricetta del pasto. La scrittura passa dall'imbuto, è atomica, si può annullare, e se il pasto non ha ancora una ricetta la scrive da zero. Quando Claude non c'è, la chat lo dice e tutto il resto funziona a mano.

**Architecture:** tre tabelle nuove nella migrazione `0021` (`conversations`, `conversation_messages`, `recipe_changes`). La scrittura della ricetta di un pasto sta in un servizio riusabile, `write_meal_recipe`, che il piano 4 chiamerà per generare le ricette dopo l'ufficializzazione. Claude passa da un client sottile sopra `claude_agent_sdk.query()`: strumenti di spena come server MCP nel processo, strumenti integrati e impostazioni spenti. Ogni giro è una `query()` nuova, che ricostruisce la conversazione dai messaggi salvati in spena (niente sessioni dell'SDK su disco). Il giro gira in un task del backend, staccato dalla richiesta HTTP, e lo streaming arriva al telefono come SSE su una `POST` letta con `fetch` e `ReadableStream`.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Alembic, pytest su Postgres vero; `claude-agent-sdk==0.2.180` (nuova dipendenza: porta con sé il binario di Claude Code 2.1.321, niente Node); React 19, TypeScript, Tailwind 4, TanStack Query, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-12-pasti-claude-design.md` (approvata da Mattia il 2026-11-12). Questo piano ne copre §3 (vincoli del modello), §4.3 (conversazioni e messaggi; il tipo `planning` esiste nello schema ma lo usa il piano 4), §5.3 (la chat sotto la ricetta, la riga «Ricetta aggiornata: …» con «Annulla», le righe evidenziate), §6.1 (gli strumenti di lettura), §6.3 (Claude scrive la ricetta), §7 (il prompt di sistema), §9 (quando Claude non c'è), §11 per `CLAUDE.md` (LLM e fornitori), e la sezione nelle spese dell'AI. È il **piano 3 di 4**. Si leggono insieme i piani da cui parte: `docs/superpowers/plans/2026-11-12-utensili.md` e `docs/superpowers/plans/2026-11-12-pasti-settimana.md`.

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/pasti-claude`, ramo `night/pasti-claude`, creato da **`night/pasti-settimana`** (piano 2). Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì, mai dalla radice del checkout principale, che non si tocca (le modifiche non committate che ci trovi sono dell'utente). **Nessun push, nessun merge, nessun deploy. Mai `git stash`. Niente letture o scritture sulla produzione. Nessuna chiamata vera a Claude: niente token, niente rete.**
- **Leggi ogni file com'è sul ramo prima di cambiarlo.** Il ramo di partenza ha le modifiche dei piani 1 e 2. Il piano descrive le modifiche ai file esistenti contro ancore riconoscibili (una funzione, una riga di codice esatta, un elemento JSX), mai contro numeri di riga. Dove il piano dà un elenco di firme per un file che non c'è, è un file nuovo.
- **I nomi dei piani 1 e 2 si usano così come sono**: `utensils_prompt_block(session) -> str | None` (`app.services.utensils`); `Meal`, `MealSlot`, `MealStatus` (`app.db.models.meal`, `app.domain.meals`); `get_meal`, `meals_between` (`app.repositories.meals`); `link_recipe`, `check_can_take_recipe`, `release_recipe`, `MealRefusal` (`app.services.meals`); `meal_out(meal, today)` e `MealOut` (`app.api.meals`, `app.schemas.meal`); `create_recipe(..., in_book=False)`, `get_recipe`, `write_recipe_ingredients` (`app.repositories.recipes`); nel frontend `MealScreen`, `RecipeDetailView` con `meal={{ mealId, readOnly }}`, `fetchMeal`, le chiavi `["meals", …]` e `["recipe", id]`. **Se un nome sul ramo è diverso da come lo scrive il piano 2**, vale il codice: usalo e scrivilo nel report.
- **Decisione fondante 2.** Ogni riga che Claude scrive passa da `write_recipe_ingredients`. Un nome che l'anagrafica non conosce passa dalla stessa strada del modulo (`ingredient_for_new_name`, poi la creazione), e il non alimentare si rifiuta. La dispensa non riceve quantità, e Claude non scrive né in dispensa né in lista (le schede dei cambi sono del piano 4).
- **Prima lezione di `CLAUDE.md`.** I test non usano l'SDK vero né la rete: il client di Claude si inietta (`get_claude_client`), e il finto chiama **gli stessi oggetti strumento** che il codice di produzione costruisce. Il client di produzione si prova a parte, con i **tipi veri dell'SDK** e `query` sostituita (Task 4). L'immagine deve contenere l'SDK e il suo binario: lo provano un test sul `pyproject.toml`, un test che lancia il binario e un comando, `python -m app.cli.check_claude`, eseguito nello stack e2e (Task 1, Task 11).
- **Il frontend non calcola logica di dominio.** Chi può avere la chat, quali righe sono evidenziate, se una modifica si può annullare, il testo degli avvisi, «oggi»: tutto nel backend.
- **Mai un vicolo cieco.** Senza Claude restano la ricetta, «Modifica», «Scrivi la ricetta», «Scegli dal ricettario» e la settimana. Un messaggio non risposto resta con «Riprova», e un messaggio non partito resta nel campo.
- **Colore e primitive** come nei piani 1 e 2: solo token di `frontend/src/index.css`, **nessun token nuovo**; `grep -rn "emerald\|neutral-" frontend/src` resta vuoto; ogni testo sopra 4,5:1 nei due temi (misurato da `frontend/e2e/style.spec.ts`); primitive da `frontend/src/components/ui/`, `Button` non cambia; bersagli alti almeno 44 px; a 375 px niente scorre di lato.
- Le parole a video sono in italiano e **si copiano esatte** da questo piano (fra «»). Gli identificatori sono in inglese e i commenti in italiano. Il prompt di sistema del Task 5 è copia fissata.
- **Il type check è `npm run typecheck`**, mai `tsc --noEmit`. Controlli del frontend, da `<worktree>/frontend`: `npx vitest run`, `npm run typecheck`, `npm run lint`, `npm run build`. Nei test dei componenti si usa `createTestQueryClient`.
- **Backend su Postgres vero**: `spena-db-1` (porta 5433), con il database di questo ramo, `spena_test_pasti_claude`. Mai `docker compose up` dal worktree, mai `-f docker-compose.prod.yml`. Si usa il `.venv` del checkout principale. Il comando di pytest, da `<worktree>/backend`:
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_pasti_claude \
    PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
- **e2e** sullo stack `spena-e2e`, con gli stessi comandi e le stesse cautele del piano 2 (il `.env` copiato da `.env.example` e cancellato alla fine; `-p spena-e2e` e `-f docker-compose.e2e.yml` in ogni comando; se lo stack c'è e non l'hai alzato tu, aspetta che sparisca):
  ```bash
  cp .env.example .env
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed --con-ricette
  (cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
  rm .env
  ```
- **Una dipendenza nuova, una sola**: `claude-agent-sdk==0.2.180`, fra le dipendenze di base del `pyproject.toml` e fissata col `==` (il binario di Claude Code segue la versione del pacchetto). Nel `pyproject.toml` non va scritta la parola `anthropic`, nemmeno in un commento: `test_anthropic_non_e_piu_una_dipendenza_di_nessun_tipo` legge il file intero. Nessun pacchetto nuovo nel frontend. Una migrazione sola, la `0021`.

### Preparazione (una volta, prima del Task 1)

- [ ] **Il ramo di partenza.** Il piano 2 deve aver lasciato `night/pasti-settimana` con la sua migrazione:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify night/pasti-settimana
  git ls-tree -r --name-only night/pasti-settimana -- backend/alembic/versions | grep 0020
  git show night/pasti-settimana:backend/app/services/utensils.py | grep -c "async def utensils_prompt_block"
  git show night/pasti-settimana:backend/app/services/meals.py | grep -cE "def (link_recipe|release_recipe|check_can_take_recipe)"
  ls .worktrees/pasti-claude 2>&1 | head -1
  ```
  Expected: un hash (**annotalo**: è `BASE` del Task 12); un file `0020_….py`; `1`; `3`; `No such file or directory`. **Se `night/pasti-settimana` non esiste** o non ha la `0020`, non creare niente: fermati e scrivi nel messaggio finale della notte che il piano 3 non è partito perché manca il piano 2 (il piano 4 dipende da questo). Se uno dei due `grep -c` dà meno del previsto, il piano 2 è finito a metà: leggi il suo report in `docs/night-reports/` sul ramo e, se mancano i pezzi che questo piano consuma (blocco «Dipendenze»), fermati allo stesso modo. Se `.worktrees/pasti-claude` esiste già, qualcuno ha cominciato: fermati e scrivilo.
- [ ] **L'SDK nel `.venv` condiviso**, senza toccare l'installazione di `spena-backend` (un `pip install -e` dal worktree sposterebbe il pacchetto del checkout principale sul worktree):
  ```bash
  PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" pip install "claude-agent-sdk==0.2.180"
  PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -c "import claude_agent_sdk, pathlib; print(claude_agent_sdk.__version__); print((pathlib.Path(claude_agent_sdk.__file__).parent/'_bundled'/'claude').exists())"
  ```
  Expected: `0.2.180` e `True`. Se `pip` non raggiunge PyPI, o la versione non c'è più, fermati: la voce passa a `bloccato` con «attende: claude-agent-sdk 0.2.180 non installabile stanotte (<errore>)». Scrivi nel report che il `.venv` del checkout principale ha un pacchetto in più (innocuo per `master`).
- [ ] **Il database dei test di questo ramo**:
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_pasti_claude WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_pasti_claude'
  ```
- [ ] `cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund`.
- [ ] **Il worktree**, con `node_modules` collegato e nessun `.env`:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/pasti-claude -b night/pasti-claude night/pasti-settimana
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/pasti-claude/frontend/node_modules
  ```
- [ ] **La revisione da cui parte la `0021`**, da `<worktree>/backend`:
  ```bash
  DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_pasti_claude \
    PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" alembic heads
  ```
  Expected: una riga sola, la `0020` del piano 2. **Annota l'identificatore**: è il `down_revision` del Task 2. Se le teste sono più d'una, fermati con «attende: le teste di Alembic su night/pasti-settimana sono più d'una».
- [ ] La voce «Sezione Pasti» di `next-steps.md` resta `in corso`, perché l'ha già messa così il piano 2 (se non lo è, cambia solo lo stato fra parentesi quadre). In coda alla riga si aggiunge ` · piano 3 di 4 (Claude e la chat del piatto) in corso su night/pasti-claude`, poi si committa con `git commit -m "next-steps: sezione Pasti, piano 3 (Claude e la chat del piatto) in corso"`.
- [ ] **La linea di partenza** (vitest e pytest dal worktree, come nel piano 2): tutto verde. **Annota** `N_file`, `N_vitest` e `N_pytest`. Se non è verde, fermati: va nel report.

---

## Obiettivo e contesto

L'esempio guida della spec (§1) è questo: martedì sera c'è «frittata di spinaci e parmigiano». Mattia apre il piatto e trova la ricetta, con sotto la chat: «ho gli spinaci congelati nella busta da 1 kg, quanti ne prendo? Posso metterli in padella da congelati e poi versare le uova?». Claude risponde, e intanto la ricetta diventa 150 g di spinaci congelati in padella unica, senza strizzatura. Il messaggio resta nella chat e la scheda cambia.

Il piano 2 ha costruito i pasti, la settimana e il piatto con la ricetta sopra, e ha lasciato sotto la ricetta il posto per la chat. Questo piano ci mette Claude. Il piano 4 aggiungerà la pianificazione, le schede dei cambi a dispensa e lista e la generazione delle ricette quando i pasti diventano ufficiali, e userà il servizio di scrittura e il client di questo piano.

## Decisioni prese

Della spec (Mattia; il perché è nella spec):

1. **Claude Opus `claude-opus-5-5` sul piano di Mattia, via Claude Agent SDK per Python.** Il token viene da `claude setup-token` e va in `CLAUDE_CODE_OAUTH_TOKEN`, solo nel `.env` del server. Niente SDK `anthropic`, niente chiave API (§3). Vedi l'avvertenza in testa.
2. **In `llm_calls` ogni giro ha la sua sezione e i suoi token, con `cost_usd` NULL**. Le spese dell'AI li mostrano senza costo, con la nota «sul piano di Claude, non a consumo» (§3, §9).
3. **Claude scrive la ricetta direttamente**, senza una scheda da confermare. Ogni scrittura passa dall'imbuto, è atomica e salva la versione di prima per «Annulla». Nella stessa modifica Claude può cambiare anche il piatto e gli accompagnamenti, ma non il posto (§6.3).
4. **Sotto la risposta compare la riga «Ricetta aggiornata: …» con «Annulla»**, e le righe cambiate restano evidenziate fino al messaggio successivo (§5.3).
5. **Gli strumenti di lettura** sono dispensa, lista, pasti di un intervallo con le ricette, utensili e ricerca nell'anagrafica. **Il ricettario non si legge** (§6.1).
6. **Il prompt di sistema è la skill `pasti` adattata**: leggere solo il necessario, dispensa al netto, sughi avviati, equilibrio approssimativo per gruppi col sale stimato, proposte varie, non sostituire un piatto deciso, chiedere le parole incerte. Le dosi sono quelle del pasto così come si mangia (`servings = 1` di norma), ogni ricetta rispetta gli utensili, e Claude non scrive tabelle (§7). Lo sforzo della chat del piatto è `medium`.
7. **Quando Claude non c'è**, la chat lo dice in parole semplici e il messaggio resta. Una risposta interrotta non lascia una ricetta scritta a metà (§9).
8. **Strumenti integrati spenti, nessun `CLAUDE.md` né impostazioni caricati** (§6).

Di questo piano (Claude, su delega: non funzionali o reversibili, Mattia le rivede nel report):

9. **La cronologia si ricostruisce dai messaggi salvati in spena, non dalle sessioni dell'SDK.** Ogni giro è una `query()` nuova: in testa ci sono il contesto (oggi, il pasto e la ricetta com'è adesso) e gli ultimi `HISTORY_MESSAGES = 40` messaggi, comprese le righe delle modifiche e il loro «annullata». Così un `up -d --build` non fa dimenticare niente e non serve un volume. Le trascrizioni dell'SDK non si scrivono (`CLAUDE_CODE_SKIP_PROMPT_HISTORY=1`). (Aggiunto il 2026-11-21: sul binario 2.1.321 quella variabile basta di fatto, ma non è documentata per le trascrizioni; il CLI riceve anche `--no-session-persistence`, che le ferma per garanzia esplicita.)
10. **Lo streaming è SSE su una `POST`**, letta dal frontend con `fetch` e `ReadableStream`. Una `location` di Nginx tiene `proxy_buffering off` sulla sola rotta dei messaggi, il backend manda `X-Accel-Buffering: no` e un commento `: ping` ogni 15 s.
11. **Il giro gira in un task del backend, staccato dalla richiesta.** Se il telefono si blocca a metà risposta, Claude finisce comunque e la risposta si trova riaprendo il piatto. Il registro dei giri è nel processo (uvicorn ha un solo worker) e tiene **una sola risposta alla volta per conversazione**. Un secondo messaggio intanto riceve un 409.
12. **Il tempo massimo di una risposta è di 240 s** (`CLAUDE_REPLY_TIMEOUT_SECONDS`), con `max_turns = 12`. Un messaggio rimasto in attesa oltre il tempo massimo più 60 s, e senza un giro vivo (il container è ripartito a metà), conta come interrotto.
13. **Gli strumenti hanno nomi inglesi e descrizioni italiane**: `read_pantry`, `read_shopping_list`, `read_meals`, `search_ingredients`, `write_recipe`, sul server MCP `spena`. **Gli utensili non sono uno strumento**: il loro blocco (`utensils_prompt_block`) va in coda al prompt di sistema a ogni giro, perché servono a ogni ricetta e uno strumento costerebbe un giro in più. Con l'elenco vuoto non si aggiunge niente (nessun vincolo).
14. **`write_recipe` vuole la ricetta intera** (titolo, porzioni, procedimento, tutte le righe), più `summary`, la riga che Mattia legge, e facoltativamente `dish` e `sides`. Non ha campi per il giorno e il pasto. Una riga punta a un `ingredient_id` trovato con `search_ingredients`, oppure porta nome e reparto (solo reparti alimentari) e passa da `ingredient_for_new_name`.
15. **La riga della chat dice «Ricetta scritta: …» quando Claude crea la ricetta da zero**, e «Ricetta aggiornata: …» quando la cambia. Annullata, dice «… — annullata».
16. **«Annulla» rimette la versione di prima solo se la ricetta e il piatto sono ancora esattamente come li ha lasciati quella modifica.** Dopo una correzione a mano dal modulo, o una modifica successiva di Claude, si rifiuta con una frase: non sovrascrive mai un lavoro più nuovo. Quindi in pratica si annulla solo l'ultima modifica. Annullare una ricetta scritta da zero la stacca dal pasto con `release_recipe` (archiviata, se non è nel ricettario).
17. **Le righe evidenziate** sono quelle nuove o cambiate (ruolo, dose, nota) dalla modifica viva del **giro più recente**, più il segno su titolo, porzioni e procedimento se cambiano. Il messaggio successivo di Mattia apre un giro nuovo, e l'evidenza sparisce.
18. **La chat c'è solo per i pasti ufficiali, non fuori casa e non avanzi** (`MealOut.can_chat`). Una bozza non può avere una ricetta (vincolo del piano 2): la sua chat è del piano 4.
19. **Senza token la `POST` risponde 503 prima di salvare qualunque cosa**, e il testo resta nel campo. Gli altri guasti arrivano dopo che il messaggio è stato salvato: il messaggio resta con l'avviso e «Riprova», che rimanda lo stesso testo e toglie il tentativo fallito.
20. **Le spese dell'AI separano le sezioni «sul piano»** (`PLAN_CALL_SITES`, oggi solo `meal_chat`) dal conto a consumo. Escono da totale, quote, chiamate senza costo e giorni, ed entrano in `plan_sections` con chiamate e token. A video stanno in un blocco «Claude», sempre visibile quando ci sono, anche in un periodo senza spese a consumo.
21. **`_resolve_lines`, `_RepeatedIngredient` ed `_embedding_for` escono da `app/api/recipes.py`** e vanno in un servizio, `app/services/recipe_writing.py`, senza cambiare comportamento. È la condizione perché Claude usi «lo stesso percorso del modulo» (§6.3) e non una seconda copia.
22. **Il modello è un'impostazione** (`CLAUDE_MODEL`, default `claude-opus-5-5`), come `OPENROUTER_MODEL`. Il token è un'impostazione (`claude_code_oauth_token`) e arriva al processo dell'SDK in `env` esplicitamente: non si conta sul fatto che Compose lo esporti.

## Criteri di accettazione

- [ ] L'immagine del backend installa `claude-agent-sdk==0.2.180` come dipendenza di base, e nel container `python -m app.cli.check_claude` dice che il binario parte e con che versione (stack e2e).
- [ ] La `0021` sale e scende, e i vincoli di conversazioni, messaggi e modifiche tengono.
- [ ] `write_meal_recipe` crea la ricetta di un pasto senza ricetta (`source = 'ai'`, fuori dal ricettario, legata) o riscrive quella che c'è, con piatto e accompagnamenti. Passa dall'imbuto, rifiuta il non alimentare, i doppioni e gli id che non esistono senza lasciare niente di scritto, e registra la modifica. `undo_recipe_change` la annulla, e rifiuta se nel frattempo la ricetta è cambiata.
- [ ] Il client di produzione costruisce le opzioni giuste: `claude-opus-5-5`, `effort="medium"`, `tools=[]`, `setting_sources=[]`, `permission_mode="dontAsk"`, gli strumenti `mcp__spena__…`, il token in `env`. Traduce i messaggi veri dell'SDK in testo, fine e guasti (limite del piano con l'ora, token, tempo massimo).
- [ ] La `POST` dei messaggi trasmette la risposta un pezzo alla volta, salva domanda e risposta, registra il giro in `llm_calls` (`meal_chat`, token, `cost_usd` NULL), rifiuta un secondo messaggio mentre Claude risponde e finisce il giro anche se il telefono se ne va. La `GET` della chat dà i messaggi, le modifiche annullabili e le righe da evidenziare.
- [ ] Nell'app: la chat sotto la ricetta, la risposta che arriva un po' alla volta, «Ricetta aggiornata: …» con «Annulla», le righe evidenziate, l'avviso con «Riprova», il blocco «Claude» nelle spese. Nel browser vero, a 375 px nei due temi, ogni testo sta sopra 4,5:1 e niente scorre di lato.
- [ ] Tutti i test di oggi passano. Quelli del modulo delle ricette restano verdi dopo lo spostamento di `_resolve_lines` (Task 3).
- [ ] `CLAUDE.md`, `.env.example`, `README.md`, `docs/prossimi-passi.md`, `next-steps.md` e il report sono aggiornati (Task 12).

## Comandi di verifica

Da `<worktree>/backend`: il comando di pytest. Da `<worktree>/frontend`: `npx vitest run`, `npm run typecheck`, `npm run lint`, `npm run build`. Dalla radice di `<worktree>`:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -rn "from claude_agent_sdk import\|import claude_agent_sdk" backend/app --include=*.py
grep -rn "_resolve_lines\|_RepeatedIngredient\|_embedding_for" backend/app --include=*.py
grep -n "claude-agent-sdk==0.2.180" backend/pyproject.toml
git diff night/pasti-settimana --stat -- backend/alembic/versions
```

Expected: il primo vuoto; il secondo solo righe di `backend/app/services/claude/client.py`, `backend/app/services/claude/tools.py` e `backend/app/cli/check_claude.py`; il terzo vuoto (decisione 21); il quarto una riga; l'ultimo un file solo, `0021_chat_pasti.py`. Poi l'e2e intera con i comandi delle Global Constraints, e dentro lo stack `exec -T backend python -m app.cli.check_claude` (Task 11).

## Review Focus

1. **Due messaggi di fila, o la pagina ricaricata mentre Claude risponde.** Il secondo messaggio è un 409 «Claude sta ancora rispondendo al messaggio di prima.». Ricaricando si vede `replying: true` finché il giro non finisce. Un messaggio rimasto «in attesa» dopo un riavvio del container diventa «La risposta si è interrotta. Riprova.» e non blocca la chat per sempre. Lo provano il Task 7 (`test_un_secondo_messaggio_mentre_risponde_e_409`) e il Task 6 (`test_un_attesa_orfana_conta_come_interrotta`).
2. **Il telefono si blocca a metà risposta.** Chi legge lo stream sparisce, ma il giro finisce, salva la risposta e la modifica, e la `GET` le mostra. Lo prova il Task 7 (`test_il_giro_finisce_anche_se_chi_legge_se_ne_va`).
3. **Una scrittura rifiutata dopo che una riga ha già creato un ingrediente nuovo** (nome nuovo, poi una riga doppia): niente ingrediente orfano, ricetta e piatto come prima, nessuna modifica registrata. Lo prova il Task 3 (`test_un_rifiuto_non_lascia_niente`).
4. **«Annulla» dopo una correzione a mano dal modulo.** Rifiuta senza toccare la ricetta. Lo prova il Task 3 (`test_annulla_dopo_una_correzione_a_mano_si_rifiuta`).
5. **Il limite del piano che si azzera dopo mezzanotte a Roma** (le 23:30 UTC sono già il giorno dopo): l'avviso dice «domani», con l'ora di Roma. Lo prova il Task 4 (`test_l_avviso_del_limite`).

## Fuori scope

- **Il piano 4** (`night/pasti-pianificazione`): la chat di pianificazione (il tipo `planning` esiste nello schema, ma nessuna rotta lo usa), la bozza e l'ufficializzazione, «Pianifica con Claude», «Chiedilo a Claude» sul posto vuoto, «Chiedi la ricetta a Claude», la «ricetta in preparazione», le schede dei cambi a dispensa e lista (anche quella che la chat del piatto potrà proporre, §6.2) e le schede inverse. Il piano 4 aggiunge i suoi strumenti nel punto che questo lascia (Task 5, `dish_tools` e `DISH_PANTRY_RULE`) e chiama `write_meal_recipe` per le ricette dell'ufficializzazione.
- La chiave API di Anthropic e l'SDK `anthropic` (§3). Il passaggio di Gemma all'API di Anthropic (voce separata del backlog).
- Le sessioni dell'SDK su disco o su un `SessionStore` (decisione 9).
- Ritirare la skill `pasti` (§11: dopo la prova in produzione).
- Rendere in markdown il testo di Claude: si mostra com'è, con gli a capo (il prompt gli chiede niente titoli e niente tabelle).

## Margine di autonomia

- **Liberi:** nomi locali, helper dei test, funzioni private non fissate qui; l'aspetto della chat dentro il sistema visivo di spena (fumetti, spazi, dove sta il segno «Claude sta scrivendo…»); la formattazione esatta dei testi che gli strumenti di lettura restituiscono, purché contengano quello che i test chiedono.
- **Fissi:** le parole a video e gli avvisi fra «» di questo piano; il prompt di sistema del Task 5, parola per parola; i nomi pubblici dei blocchi Interfaces (li usa il piano 4); i nomi e gli schemi degli strumenti; le rotte e gli eventi SSE; i valori `dish`/`planning`, `user`/`assistant`, `pending`/`sent`/`failed`; il modello, lo sforzo, `max_turns` e il tempo massimo.
- **La documentazione dell'SDK vince sul piano per i nomi dell'SDK.** Se nella versione installata un campo o un tipo ha un altro nome (`ClaudeAgentOptions.effort`, `RateLimitEvent`, `AssistantMessage.error`, `ResultMessage.usage`), usa quello che c'è e scrivilo nel report. Se manca una capacità (per esempio non si spengono gli strumenti integrati, o lo streaming parziale non esiste), fermati: la voce va a `bloccato` con «attende: …» e la misura.
- **Un test di oggi si cambia solo dove il piano lo dice**: nessuno, in questo piano. Lo spostamento del Task 3 non cambia nessun test: se uno cade, lo spostamento ha cambiato un comportamento, e va corretto il codice.
- **Una decisione di comportamento non coperta e non reversibile**: si ferma quel task, si fa commit del lavoro parziale, la voce «Sezione Pasti» passa a `bloccato` con «attende: …» e la domanda precisa, e si va al task dopo se non dipende da quello. Una scelta reversibile e a basso impatto: la più conservativa, annotata nel report.
- Un test che fallisce e non si risolve: niente test disattivati, niente asserzioni indebolite. `bloccato` con la diagnosi.

## Dipendenze

- **Parte da `night/pasti-settimana` (piano 2)**, che parte da `night/utensili` (piano 1). Consuma dal piano 1 `utensils_prompt_block`. Dal piano 2 consuma `Meal` e i suoi vincoli (in particolare `uq_meals_recipe` e `ck_meal_draft_no_recipe`), `get_meal`, `meals_between`, `link_recipe`, `check_can_take_recipe`, `release_recipe`, `MealRefusal`, `meal_out`/`MealOut`, `create_recipe(in_book=False)`, `RecipeOut.in_book`/`meal`, `MealScreen` con il posto della chat sotto la ricetta, e `RecipeDetailView` con `meal={{ mealId, readOnly }}`.
- **Il piano 4 (`night/pasti-pianificazione`) parte da questo ramo** e usa le «Interfacce prodotte» qui sotto.
- Al merge su `master` i quattro rami si uniscono in ordine. La `0021` ha come `down_revision` la `0020` del piano 2.

### Interfacce prodotte (per il piano 4)

- **Tabelle** (migrazione `0021`, file `backend/alembic/versions/0021_chat_pasti.py`, `revision = "0021"`):
  - `conversations`: `id`, `kind VARCHAR(10)` (`ck_conversation_kind`: `dish`|`planning`), `meal_id UUID NULL` FK `meals.id` `ON DELETE CASCADE`, unico (`uq_conversations_meal`), `created_at`, `updated_at`; `ck_conversation_dish_has_meal` (`kind <> 'dish' OR meal_id IS NOT NULL`), `ck_conversation_planning_no_meal` (`kind <> 'planning' OR meal_id IS NULL`).
  - `conversation_messages`: `id`, `conversation_id` FK `ON DELETE CASCADE`, `role VARCHAR(10)` (`ck_message_role`: `user`|`assistant`), `text TEXT NOT NULL`, `status VARCHAR(10) NOT NULL DEFAULT 'sent'` (`ck_message_status`: `pending`|`sent`|`failed`), `failure VARCHAR(20) NULL`, `notice TEXT NULL`, `reply_to_id UUID NULL` FK `conversation_messages.id` `ON DELETE CASCADE`, `created_at`; indice `ix_conversation_messages_conversation_created` (`conversation_id`, `created_at`).
  - `recipe_changes`: `id`, `meal_id` FK `ON DELETE CASCADE`, `recipe_id` FK `ON DELETE CASCADE`, `conversation_id NULL` FK `ON DELETE SET NULL`, `turn_message_id NULL` FK `conversation_messages.id` `ON DELETE SET NULL`, `created_recipe BOOLEAN NOT NULL`, `summary VARCHAR(200) NOT NULL`, `before JSONB NOT NULL`, `after JSONB NOT NULL`, `changed JSONB NOT NULL`, `undone_at TIMESTAMPTZ NULL`, `created_at`; indice `ix_recipe_changes_meal_created`.
- **Servizio di scrittura** `app.services.meal_recipes`:
  - `@dataclass(frozen=True) class DraftLine`: `ingredient_id: uuid.UUID | None`, `name: str | None`, `category: IngredientCategory | None`, `role: IngredientRole`, `quantity_text: str | None`, `note: str | None`.
  - `@dataclass(frozen=True) class MealRecipeDraft`: `title: str`, `description: str | None`, `instructions: str`, `servings: int`, `lines: tuple[DraftLine, ...]`, `summary: str`, `dish: str | None = None`, `sides: str | None | Unset = UNSET` (`UNSET` = non cambiare; `None` = togli).
  - `class RecipeWriteRefused(Exception)`: `message: str` (la frase per Claude, o per il chiamante).
  - `async def write_meal_recipe(session: AsyncSession, meal: Meal, draft: MealRecipeDraft, *, conversation_id: uuid.UUID | None = None, turn_message_id: uuid.UUID | None = None) -> RecipeChange`. Crea la ricetta (`source = 'ai'`, `in_book = False`, legata) se il pasto non ce l'ha, altrimenti la riscrive. Dentro un SAVEPOINT; fa `flush`, mai `commit`. Solleva `MealRefusal` (pasto che non può avere una ricetta) o `RecipeWriteRefused`, e in tutti e due i casi non resta niente di scritto. **È la funzione che il piano 4 chiama per generare le ricette dopo l'ufficializzazione.**
  - `async def undo_recipe_change(session: AsyncSession, change: RecipeChange) -> None`, che solleva `ChangeRefusal(code: ChangeRefusalCode)` con `ALREADY_UNDONE = "change_undone"` o `STALE = "change_stale"`.
- **Client di Claude** `app.services.claude.client`:
  - eventi `TextDelta(text: str)`, `TurnFinished(text: str, usage: ClaudeUsage)`, `TurnFailed(failure: ClaudeFailure)`; `ClaudeUsage(model: str | None, session_id: str | None, input_tokens: int | None, output_tokens: int | None)`; `ClaudeFailure(kind: FailureKind, resets_at: datetime | None, detail: str)`.
  - `class ClaudeClient(Protocol)`: `def run(self, *, system_prompt: str, prompt: str, tools: Sequence[SdkMcpTool], effort: Effort, max_turns: int) -> AsyncIterator[ClaudeEvent]`.
  - `class SdkClaudeClient(ClaudeClient)`; `build_options(...) -> ClaudeAgentOptions`; `def get_claude_client() -> ClaudeClient` (dipendenza FastAPI); `def claude_configured() -> bool`.
- **Dominio** `app.domain.meal_chat`: `FailureKind` (`not_configured`, `plan_limit`, `auth`, `timeout`, `unavailable`, `interrupted`), `failure_notice(kind, resets_at, now) -> str`, `BUSY_NOTICE`, `can_chat(meal) -> bool`, `pending_is_stale(created_at, now, timeout_seconds) -> bool`, `HISTORY_MESSAGES`, `DISH_EFFORT = "medium"`, `DISH_MAX_TURNS = 12`.
- **Prompt** `app.services.claude.prompts`: `COMMON_PROMPT`, `DISH_PROMPT`, `DISH_PANTRY_RULE` (il punto che il piano 4 sostituisce con la regola delle schede), `def dish_system_prompt(utensils_block: str | None) -> str`. Il piano 4 aggiunge `PLANNING_PROMPT` accanto e compone con `COMMON_PROMPT`.
- **Strumenti** `app.services.claude.tools`: `TurnContext`, `def read_tools(ctx: TurnContext) -> list[SdkMcpTool]` (i quattro di lettura, riusabili), `def write_recipe_tool(ctx: TurnContext) -> SdkMcpTool`, `def dish_tools(ctx: TurnContext) -> list[SdkMcpTool]` (oggi `[*read_tools(ctx), write_recipe_tool(ctx)]`: **qui il piano 4 aggiunge i suoi**), `SPENA_SERVER = "spena"`.
- **Giro** `app.services.meal_chat`: `async def run_dish_turn(session_factory, client, *, conversation_id, user_message_id, emit, timeout_seconds) -> None`. Il registro `app.services.chat_turns.TurnRegistry` e `get_turn_registry()`.
- **`LlmCallSite.MEAL_CHAT = "meal_chat"`**, `PLAN_CALL_SITES` e `CALL_SITE_LABELS["meal_chat"] = "Chat dei piatti"` in `app.domain.spending`. Il piano 4 aggiunge le sue sezioni a tutti e due.
- **Rotte** (dietro la sessione, `prefix="/api/v1/meals/{meal_id}/chat"`): `GET ""` → `DishChatOut`; `POST "/messages"` `{text, retry_of?}` → `text/event-stream`; `POST "/changes/{change_id}/undo"` → `DishChatOut`. Il campo `MealOut.can_chat: bool`.
- **Frontend**: `apiStream(path, init): Promise<Response>` in `src/api/client.ts`; `readSse(response, onEvent)` in `src/features/meal-chat/sse.ts`; `features/meal-chat/api.ts` (`fetchDishChat`, `sendDishMessage`, `undoRecipeChange`, la chiave `dishChatKey(mealId) = ["meal-chat", mealId]`); il componente `ChatThread` (fumetti, streaming, campo), riusabile dalla pianificazione, e `DishChat({ mealId, hasRecipe })`; `RecipeDetailView` con la prop `highlight?: RecipeHighlight | null`.

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `backend/pyproject.toml`, `backend/Dockerfile` (commento), `backend/app/core/config.py`, `.env.example`, `backend/app/cli/check_claude.py` (nuovo), `backend/tests/test_image_dependencies.py`, `backend/tests/test_claude_binary.py` (nuovo), `backend/tests/test_settings_claude.py` (nuovo) | 1 | l'SDK nell'immagine e le impostazioni |
| `backend/alembic/versions/0021_chat_pasti.py`, `backend/app/db/models/conversation.py`, `backend/app/db/models/recipe_change.py` (nuovi), `backend/app/db/models/__init__.py`, `backend/tests/db/test_migration_0021.py` (nuovo) | 2 | lo schema |
| `backend/app/services/recipe_writing.py`, `backend/app/domain/recipe_changes.py`, `backend/app/services/meal_recipes.py` (nuovi), `backend/app/api/recipes.py`, tre file di test nuovi | 3 | la scrittura della ricetta di un pasto e «Annulla» |
| `backend/app/domain/meal_chat.py`, `backend/app/services/claude/__init__.py`, `backend/app/services/claude/client.py` (nuovi), `backend/tests/claude_fakes.py`, due file di test nuovi | 4 | il client di Claude e gli avvisi |
| `backend/app/services/claude/prompts.py`, `backend/app/services/claude/tools.py` (nuovi), due file di test nuovi | 5 | il prompt di sistema e gli strumenti |
| `backend/app/services/meal_chat.py`, `backend/app/services/chat_turns.py`, `backend/app/repositories/conversations.py` (nuovi), `backend/app/services/llm.py`, `backend/app/domain/spending.py`, `backend/app/core/db.py`, due file di test nuovi | 6 | il giro della chat |
| `backend/app/schemas/meal_chat.py`, `backend/app/api/meal_chat.py` (nuovi), `backend/app/schemas/meal.py`, `backend/app/api/meals.py`, `backend/app/main.py`, `frontend/nginx.conf`, `backend/tests/api/test_meal_chat.py`, `backend/tests/test_nginx_chat.py` (nuovi) | 7 | le rotte e Nginx |
| `backend/app/repositories/llm_calls.py`, `backend/app/services/spending.py`, `backend/app/schemas/spending.py`, `frontend/src/features/spending/*`, test | 8 | le spese sul piano |
| `frontend/src/api/client.ts`, `frontend/src/domain/types.ts`, `frontend/src/features/meal-chat/*` (nuovi), test | 9 | la chat nel frontend |
| `frontend/src/features/meals/MealScreen.tsx`, `frontend/src/features/cooking/RecipeDetailScreen.tsx`, test | 10 | la chat nel piatto e le righe evidenziate |
| `backend/tests/e2e_chat.py`, `backend/tests/test_e2e_chat_guard.py`, `frontend/e2e/chat-piatto.spec.ts` (nuovi), `frontend/e2e/style.spec.ts` | 11 | nel browser vero |
| `CLAUDE.md`, `README.md`, `docs/prossimi-passi.md`, `next-steps.md`, `docs/night-reports/<data>.md` | 12 | documenti e report |

---

### Task 1: L'SDK nell'immagine, le impostazioni, il controllo

**Files:**
- Modify: `backend/pyproject.toml` (in `dependencies`), `backend/Dockerfile` (il commento sopra `ARG INSTALL_EMBEDDINGS`), `backend/app/core/config.py` (campi nuovi dopo `llm_max_concurrency`; il commento «OpenRouter è l'unico fornitore» dice ora che c'è un secondo percorso, per i Pasti, e perché non è il caso che la regola vieta), `.env.example` (in fondo), `backend/tests/test_image_dependencies.py` (due test in fondo)
- Create: `backend/app/cli/check_claude.py`, `backend/tests/test_claude_binary.py`, `backend/tests/test_settings_claude.py`

**Interfaces:**
- Produces, in `Settings`: `claude_code_oauth_token: str | None = None` (si legge da `CLAUDE_CODE_OAUTH_TOKEN`); `claude_model: str = "claude-opus-5-5"`; `claude_reply_timeout_seconds: float = 240.0`; `claude_workdir: str = "/tmp/spena-claude"` (una cartella vuota come `cwd` dell'SDK, così nessun `CLAUDE.md` di progetto è vicino).
- Produces: `python -m app.cli.check_claude [--prova]`. Senza argomenti non usa la rete. Stampa `claude-agent-sdk <versione>`, poi `binario: <percorso> → <output di --version>` (il binario in `claude_agent_sdk/_bundled/claude`, lanciato con `--version` e un `HOME` temporaneo, timeout 30 s) e `token: presente` o `token: assente` (**mai il valore**). Esce con 1 se il binario manca o non parte. Con `--prova` fa una sola `query()` minima («Rispondi solo: ok», nessuno strumento, opzioni di `build_options` del Task 4), e stampa `prova: ok` oppure l'avviso di `failure_notice`. Serve a Mattia dopo il deploy. Il comando c'è dal Task 1, e `--prova` si completa nel Task 4.

- [ ] **Step 1: I test che falliscono.**
  - In `test_image_dependencies.py`: `test_claude_agent_sdk_e_una_dipendenza_di_base_fissata`, dove fra le `dependencies` del `pyproject.toml` c'è esattamente `"claude-agent-sdk==0.2.180"` (con il `==`: il binario segue il pacchetto, e un `>=` cambierebbe Claude Code a ogni ricostruzione). Poi `test_il_dockerfile_non_installa_node`, dove nessuna riga del Dockerfile nomina `nodejs`, `npm` o `@anthropic-ai`: l'SDK porta il binario da sé.
  - `test_claude_binary.py`: `test_il_binario_di_claude_code_c_e_e_parte`. `Path(claude_agent_sdk.__file__).parent / "_bundled" / "claude"` esiste ed è eseguibile, e lanciato con `--version` (un `HOME` in `tmp_path`, timeout 30 s) esce con 0 e stampa `claude_agent_sdk._cli_version.__cli_version__`. Nessuna rete: `--version` non autentica.
  - `test_settings_claude.py`: `test_il_token_si_legge_da_claude_code_oauth_token` (con `monkeypatch.setenv`, poi `get_settings.cache_clear()`), `test_senza_token_e_none`, `test_il_modello_di_default_e_opus` (`"claude-opus-5-5"`), e `test_check_claude_non_stampa_il_token`: con un token finto nell'ambiente, `main([])` di `app.cli.check_claude` stampa `token: presente` e non contiene il token.
- [ ] **Step 2: Falliscono.** Il comando di pytest con i tre file. Expected: FAIL.
- [ ] **Step 3: Il codice.** In `pyproject.toml`, la riga `"claude-agent-sdk==0.2.180",` in ordine alfabetico fra le dipendenze di base, con un commento sopra: «Claude Code come libreria, per i Pasti: porta il suo binario, niente Node. Fissata: il binario segue la versione.» (nessuna parola `anthropic`). Nel Dockerfile, al commento che racconta la lezione dell'extra mancante si aggiunge una riga: anche l'Agent SDK è una dipendenza di base, e il suo binario arriva con la ruota di pip. In `.env.example`, in fondo:
  ```
  # Il token del piano Claude di Mattia, per i Pasti (la chat dei piatti). Si genera sul
  # proprio computer con `claude setup-token` (dura un anno) e si scrive SOLO nel `.env`
  # del server: il repository è pubblico. Vuoto, la chat dice che Claude non è collegato
  # e tutto il resto dei Pasti funziona a mano. Controllo: `python -m app.cli.check_claude`.
  CLAUDE_CODE_OAUTH_TOKEN=
  # Il modello dei Pasti, sul piano di Claude (non su OpenRouter).
  CLAUDE_MODEL=claude-opus-5-5
  CLAUDE_REPLY_TIMEOUT_SECONDS=240
  ```
  `check_claude.py` va sul modello dei comandi in `app/cli/` (`main(argv) -> int`, `if __name__ == "__main__": raise SystemExit(main(sys.argv[1:]))`). Fino al Task 4, `--prova` stampa «prova: il client arriva col Task 4» ed esce con 2. Il Task 4 lo sostituisce.
- [ ] **Step 4: Passano.** Lo stesso comando, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit**
  ```bash
  git add backend/pyproject.toml backend/Dockerfile backend/app/core/config.py backend/app/cli/check_claude.py backend/tests .env.example
  git commit -m "feat(pasti): l'Agent SDK di Claude nell'immagine, fissato, con il suo binario; il token del piano fra le impostazioni"
  ```

---

### Task 2: Lo schema — conversazioni, messaggi, modifiche della ricetta

**Files:**
- Create: `backend/alembic/versions/0021_chat_pasti.py`, `backend/app/db/models/conversation.py` (`Conversation`, `ConversationMessage`), `backend/app/db/models/recipe_change.py` (`RecipeChange`), `backend/tests/db/test_migration_0021.py`
- Modify: `backend/app/db/models/__init__.py` (import e `__all__`)

**Interfaces:**
- Consumes: la `0020` letta nella Preparazione.
- Produces: le tre tabelle del blocco «Interfacce prodotte», con quei nomi di vincolo, e i modelli `Conversation(UUIDMixin, TimestampMixin, Base)`, `ConversationMessage(UUIDMixin, Base)` (con `created_at` come `LlmCall`: `server_default=func.now()`) e `RecipeChange(UUIDMixin, Base)` (idem). Le relazioni sono `lazy="raise"`, come nel piano 2. In `conversation.py`: `class ConversationKind(StrEnum)`: `DISH = "dish"`, `PLANNING = "planning"`; `class MessageRole(StrEnum)`: `USER`, `ASSISTANT`; `class MessageStatus(StrEnum)`: `PENDING`, `SENT`, `FAILED`.

- [ ] **Step 1: Il test che fallisce.** `tests/db/test_migration_0021.py`, sul modello di `test_migration_0020.py` del piano 2 (un database suo, Alembic in un sottoprocesso):
  - `test_la_0021_sale_e_scende`. Dopo `upgrade head` ci sono le tre tabelle. `downgrade` alla `0020` le toglie (da `information_schema`), e `meals` resta.
  - `test_una_chat_del_piatto_per_pasto`: due `conversations` `dish` con lo stesso `meal_id` → `IntegrityError`.
  - `test_i_vincoli_della_conversazione`, parametrizzato su tre righe che devono fallire: `kind='chat'`; `dish` senza pasto; `planning` con un pasto.
  - `test_i_vincoli_del_messaggio`, parametrizzato: `role='system'`; `status='lost'`.
  - `test_cancellare_il_pasto_porta_via_chat_messaggi_e_modifiche`: un pasto con una conversazione, un messaggio e una modifica. Dopo il `DELETE` del pasto le tre righe non ci sono più.
- [ ] **Step 2: Fallisce.** Il comando di pytest con il file. Expected: FAIL.
- [ ] **Step 3: Migrazione e modelli.** La docstring di `Conversation` riassume §4.3 (due tipi, una chat per pasto, i messaggi in spena perché la cronologia sopravviva ai riavvii: decisione 9). La docstring di `RecipeChange` dice cosa sono `before`, `after` e `changed` (forma nel Task 3) e perché si confrontano per «Annulla» (decisione 16).
- [ ] **Step 4: Passa, e lo schema coincide coi modelli.** Il comando di pytest con `tests/db/test_migration_0021.py tests/db/test_metadata_matches_migrations.py`. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(pasti): conversazioni, messaggi e modifiche della ricetta (0021)`.

---

### Task 3: La scrittura della ricetta di un pasto, e «Annulla»

**Files:**
- Create: `backend/app/services/recipe_writing.py`, `backend/app/domain/recipe_changes.py`, `backend/app/services/meal_recipes.py`, `backend/tests/domain/test_recipe_changes.py`, `backend/tests/services/test_meal_recipes.py`, `backend/tests/services/test_recipe_writing.py`
- Modify: `backend/app/api/recipes.py` (`_resolve_lines`, `_RepeatedIngredient`, `_embedding_for` se ne vanno; le chiamate usano i nomi nuovi)

**Interfaces:**
- Consumes: `write_recipe_ingredients`, `create_recipe(in_book=…)`, `get_recipe`, `NonFoodInRecipe` (`app.repositories.recipes`); `ingredient_for_new_name`; `create_ingredient`; `link_recipe`, `release_recipe`, `check_can_take_recipe`, `MealRefusal` (piano 2); `RecipeChange` (Task 2).
- Produces, in `app.services.recipe_writing` (spostati e resi pubblici, **senza cambiare una riga di comportamento**): `class RepeatedIngredient(Exception)` (`display_name`); `async def resolve_lines(session, lines: list[RecipeIngredientIn]) -> list[IngredientLine]`; `async def embedding_for(title: str, description: str | None) -> list[float] | None`. `app/api/recipes.py` li importa, e `_writing_recipe` intercetta `RepeatedIngredient`.
- Produces, in `app.domain.recipe_changes` (puro):
  - `LineSnapshot(ingredient_id: uuid.UUID, role: str, quantity_text: str | None, note: str | None)`; `RecipeSnapshot(title, description, instructions, servings, lines: tuple[LineSnapshot, ...])`; `MealSnapshot(dish: str, sides: str | None, recipe: RecipeSnapshot | None)`. Tutti `frozen`. Le righe stanno nell'ordine della ricetta.
  - `def snapshot_to_json(s: MealSnapshot) -> dict` e `def snapshot_from_json(d: dict) -> MealSnapshot` (gli UUID come stringhe).
  - `ChangedParts(ingredient_ids: frozenset[uuid.UUID], title: bool, servings: bool, instructions: bool, description: bool)` con `changed_parts(before: RecipeSnapshot | None, after: RecipeSnapshot) -> ChangedParts`. Una riga di `after` è cambiata se il suo ingrediente non c'era in `before`, o se c'era con ruolo, dose o nota diversi. Con `before` `None`, tutte le righe e tutti i segni.
- Produces, in `app.services.meal_recipes`, le firme del blocco «Interfacce prodotte», più:
  - `async def meal_snapshot(session, meal: Meal) -> MealSnapshot` (rilegge la ricetta con `get_recipe`).
  - `class ChangeRefusalCode(StrEnum)`: `ALREADY_UNDONE = "change_undone"`, `STALE = "change_stale"`; `class ChangeRefusal(Exception)`: `code`, `message`.
  - `async def change_is_undoable(session, change: RecipeChange) -> bool`: non annullata, e `meal_snapshot` del pasto è uguale a `after`.
- Le frasi, esatte:
  - `ALREADY_UNDONE`: «Questa modifica è già stata annullata.»
  - `STALE`: «La ricetta è cambiata dopo questa modifica: non si può più annullare.»
  - `STALE` con un ingrediente che non esiste più: «Un ingrediente della versione di prima non c'è più: correggi la ricetta dal modulo.»
  - `RecipeWriteRefused` (le legge Claude): non alimentare «‹nome› non è un alimento: una ricetta non può averlo. Togli quella riga o scegli un altro ingrediente.»; doppione «Due righe puntano allo stesso ingrediente, ‹nome›: tienine una.»; id che non c'è «L'ingrediente ‹id› non esiste: cercalo di nuovo con search_ingredients.»; ricetta eliminata «La ricetta di questo pasto è stata eliminata: Mattia deve ripristinarla prima.» (‹…› qui è il valore, non sono caporali da copiare).

Le regole di `write_meal_recipe`, fissate dai test:
- Il pasto deve essere ufficiale, non fuori casa e non un avanzo (altrimenti il `MealRefusal` di `check_can_take_recipe` del piano 2, con le sue frasi). Se il pasto non ha ricetta, la crea con `create_recipe(source=RecipeSource.AI, source_ref=None, in_book=False, embedding=await embedding_for(...))` e chiama `link_recipe`. Se ce l'ha, la rilegge con `get_recipe`, rifiuta se è eliminata, scrive titolo, descrizione, procedimento e porzioni, e le righe con `write_recipe_ingredients`. Il vettore si rifà solo se cambiano titolo o descrizione, come in `replace`.
- Le righe passano da `resolve_lines`: le `DraftLine` diventano `RecipeIngredientIn` (`ingredient_id`, oppure `name` e `category`). Prima di scrivere, ogni `ingredient_id` dato si controlla con `session.get(Ingredient, …)`.
- `dish` (ripulito degli spazi) e `sides` (`UNSET` non tocca; `None` o una stringa vuota toglie) si scrivono sul pasto.
- Tutto dentro `async with session.begin_nested()`. `NonFoodInRecipe`, `RepeatedIngredient` e un id mancante diventano `RecipeWriteRefused` dopo il rollback del SAVEPOINT: nessun ingrediente creato resta. Poi si registra `RecipeChange` (`before` = `meal_snapshot` prima, `after` = dopo, `changed` = `changed_parts` come JSON con gli id in stringa, `created_recipe`, `summary` ripulito e tagliato a 200).

`undo_recipe_change`: se `undone_at` c'è → `ALREADY_UNDONE`. Se `meal_snapshot` del pasto non è uguale ad `after` → `STALE`. Altrimenti, dentro un SAVEPOINT: con `created_recipe` → `release_recipe(session, meal)`; senza → si riscrivono la ricetta (campi, e righe con `write_recipe_ingredients`) e il pasto da `before`. Un ingrediente di `before` che non c'è più dà `STALE` con la seconda frase, senza toccare niente. Infine `undone_at = now`.

- [ ] **Step 1: I test che falliscono.**
  - `tests/services/test_recipe_writing.py`: `test_resolve_lines_e_quello_che_usa_il_modulo`, dove `app.api.recipes` importa `resolve_lines` da `app.services.recipe_writing` (si controlla l'identità dell'oggetto: `app.api.recipes.resolve_lines is app.services.recipe_writing.resolve_lines`), e `_resolve_lines` non esiste più in `app.api.recipes`. **I test di oggi del modulo delle ricette restano verdi senza toccarli.**
  - `tests/domain/test_recipe_changes.py`: `test_changed_parts` (parametrizzato: riga nuova, dose cambiata, nota cambiata, ruolo cambiato → nell'insieme; riga uguale → no; riga tolta → no, perché non c'è più niente da evidenziare; titolo e procedimento → i segni), `test_changed_parts_di_una_ricetta_nuova_segna_tutto`, `test_lo_snapshot_va_e_torna_dal_json`.
  - `tests/services/test_meal_recipes.py` (fixture: ingredienti `uova`, `spinaci`, `parmigiano` alimentari e `detersivo` in `casa`; un pasto ufficiale con `create_meal` del piano 2; ogni test fa `flush` e rilegge):
    1. `test_scrive_da_zero_la_ricetta_di_un_pasto_senza_ricetta`. La ricetta ha `source == "ai"`, `in_book is False` e `servings == 1`. `meal.recipe_id` è lei, e le righe hanno `quantity_value` letto dal parser («150 g» → 150). La modifica ha `created_recipe is True` e `before["recipe"] is None`.
    2. `test_riscrive_la_ricetta_che_c_e_e_ricorda_quella_di_prima`. La seconda scrittura cambia gli spinaci da «200 g» a «150 g», con la nota «congelati». `before` ha «200 g», `after` ha «150 g», e `changed["ingredient_ids"]` è `[spinaci]`.
    3. `test_cambia_piatto_e_accompagnamenti_ma_non_il_posto`. Con `dish="Frittata di zucchine"` e `sides=None` il pasto ha il piatto nuovo e nessun accompagnamento; `day` e `slot` restano quelli di prima. Con `sides=UNSET` gli accompagnamenti restano.
    4. `test_un_nome_nuovo_passa_dalla_strada_del_modulo`. La riga `name="Spinaci"` senza id si aggancia a `spinaci` (via `ingredient_for_new_name`) e nessun ingrediente nuovo nasce. La riga `name="erba cipollina", category="verdura"` crea l'ingrediente.
    5. `test_il_non_alimentare_si_rifiuta`, parametrizzato su id di `detersivo` e su `name="detersivo"`: si ottiene `RecipeWriteRefused`, con la frase che nomina «Detersivo».
    6. `test_un_rifiuto_non_lascia_niente`. La ricetta ha già una versione. Si manda una riga col nome nuovo «erba cipollina» e due righe su `uova`: `RecipeWriteRefused` (doppione). Dopo non esiste nessun ingrediente «erba cipollina», ricetta e piatto sono identici a prima (`meal_snapshot` uguale) e le modifiche registrate sono quelle di prima.
    7. `test_un_id_che_non_c_e_si_rifiuta`: un `uuid4()` → `RecipeWriteRefused` con la frase dell'id.
    8. `test_chi_non_puo_avere_una_ricetta`, parametrizzato su bozza, fuori casa e avanzo: `MealRefusal`, e nessuna ricetta creata.
    9. `test_annulla_rimette_la_versione_di_prima`. Dopo la scrittura 2 e `undo_recipe_change`, la ricetta ha di nuovo «200 g» e nessuna nota, il piatto è quello di prima e `undone_at` non è nullo. Le righe sono passate dall'imbuto (`quantity_value == 200`).
    10. `test_annulla_una_ricetta_scritta_da_zero_la_stacca_dal_pasto`: il pasto ha `recipe_id is None` e la ricetta è archiviata.
    11. `test_annulla_dopo_una_correzione_a_mano_si_rifiuta`. Dopo la scrittura, la ricetta si cambia come fa `PUT /api/v1/recipes/{id}` (con `logged_client`, il titolo cambiato). `undo_recipe_change` → `ChangeRefusal(STALE)`, la ricetta ha il titolo della correzione e `change_is_undoable` è `False`.
    12. `test_annulla_solo_l_ultima`: due scritture, poi annullare la prima → `STALE`; la seconda si annulla.
    13. `test_annullare_due_volte`: `ALREADY_UNDONE`.
    14. `test_annulla_con_un_ingrediente_sparito`. La versione di prima usava `parmigiano`, che poi si fonde in un altro con `merge_ingredients`. L'annullamento dà `STALE` con la frase dell'ingrediente, e la ricetta resta com'è.
- [ ] **Step 2: Falliscono.** Il comando di pytest con i tre file. Expected: FAIL.
- [ ] **Step 3: Il codice.** Prima lo spostamento: lancia la suite delle ricette (`tests/api/test_recipes*.py`) e verifica che resti verde. Poi il dominio e il servizio. La docstring di `write_meal_recipe` dice che è la sola strada con cui Claude scrive una ricetta (chat del piatto ora, ufficializzazione nel piano 4), e perché il SAVEPOINT: un rifiuto non lascia niente, e un chiamante che scrive più pasti in una transazione perde solo quello rifiutato.
- [ ] **Step 4: Passano.** I tre file, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(pasti): la ricetta di un pasto scritta da un servizio solo — imbuto, atomica, con la versione di prima per «Annulla»`.

---

### Task 4: Il client di Claude e gli avvisi

**Files:**
- Create: `backend/app/domain/meal_chat.py`, `backend/app/services/claude/__init__.py` (vuoto), `backend/app/services/claude/client.py`, `backend/tests/claude_fakes.py`, `backend/tests/domain/test_meal_chat.py`, `backend/tests/services/test_claude_client.py`
- Modify: `backend/app/cli/check_claude.py` (`--prova`)

**Interfaces:**
- Consumes: `get_settings()` (Task 1); `Meal`, `MealStatus` (piano 2).
- Produces, in `app.domain.meal_chat` (puro): le firme del blocco «Interfacce prodotte», più `STALE_MARGIN_SECONDS = 60`, `MESSAGE_MAX_CHARS = 4000` e `MAX_MEALS_RANGE_DAYS = 28`. `can_chat(meal)` è vero per un pasto ufficiale, non fuori casa e senza `leftover_of_id`. `pending_is_stale(created_at, now, timeout_seconds)` è vero quando `now - created_at > timeout + STALE_MARGIN_SECONDS`.
- Produces, in `app.services.claude.client`: le firme del blocco «Interfacce prodotte». `Effort = Literal["low", "medium", "high", "xhigh", "max"]`. `ClaudeEvent = TextDelta | TurnFinished | TurnFailed`. `build_options(*, system_prompt: str, tools: Sequence[SdkMcpTool], effort: Effort, max_turns: int) -> ClaudeAgentOptions`. `def translate(message: object, state: TurnState) -> list[ClaudeEvent]`, dove `TurnState` tiene il testo dei blocchi completi, il modello, l'ultimo `resets_at` e il guasto visto.

Gli avvisi di `failure_notice`, esatti (l'ora è quella di Roma, scritta `f"{ora}:{minuti:02d}"`, cioè «9:05», «18:40»):
- `NOT_CONFIGURED`: «Claude non è collegato: manca il token del piano sul server.»
- `PLAN_LIMIT` con `resets_at` nello stesso giorno di Roma di `now`: «Claude non risponde: hai raggiunto il limite del piano, riprova dopo le 18:40». Il giorno dopo: «Claude non risponde: hai raggiunto il limite del piano, riprova domani dopo le 9:00». Più in là: «Claude non risponde: hai raggiunto il limite del piano, riprova dopo le 9:00 del 14 novembre». Senza ora: «Claude non risponde: hai raggiunto il limite del piano, riprova più tardi». (Senza punto finale, come la spec §9.)
- `AUTH`: «Claude non risponde: il token del piano è scaduto o non vale più. Va rifatto con claude setup-token e scritto nel .env del server.»
- `TIMEOUT`: «Claude non risponde: ci sta mettendo troppo. Riprova tra poco.»
- `UNAVAILABLE`: «Claude non risponde in questo momento. Riprova tra poco.»
- `INTERRUPTED`: «La risposta si è interrotta. Riprova.»
- `BUSY_NOTICE`: «Claude sta ancora rispondendo al messaggio di prima.»

`build_options`, i valori fissati (verificati sulla documentazione dell'SDK il 2026-11-12):

| Opzione | Valore | Perché |
|---|---|---|
| `model` | `settings.claude_model` (`claude-opus-5-5`) | spec §3 |
| `system_prompt` | la stringa (non il preset `claude_code`) | il prompt è tutto nostro (§7) |
| `tools` | `[]` | toglie ogni strumento integrato dal contesto: niente file, shell, web (§6) |
| `mcp_servers` | `{SPENA_SERVER: create_sdk_mcp_server(name=SPENA_SERVER, version="1", tools=list(tools))}` | gli strumenti di spena, nel processo |
| `allowed_tools` | `[f"mcp__spena__{t.name}" for t in tools]` | approvati senza chiedere |
| `permission_mode` | `"dontAsk"` | qualunque altra chiamata è negata, non chiesta: non c'è nessuno a cui chiedere |
| `setting_sources` | `[]` | niente `settings.json`, `CLAUDE.md`, skill (§6) |
| `strict_mcp_config` | `True` | nessun altro server MCP |
| `include_partial_messages` | `True` | lo streaming (`StreamEvent` con `content_block_delta`/`text_delta`) |
| `effort` | il parametro (`DISH_EFFORT = "medium"` per la chat del piatto) | spec §7 |
| `max_turns` | il parametro (`DISH_MAX_TURNS = 12`) | la sessione non ha un tempo massimo suo |
| `cwd` | `settings.claude_workdir` (creata se manca) | nessun `CLAUDE.md` di progetto vicino |
| `env` | `{"CLAUDE_CODE_OAUTH_TOKEN": token, "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "ENABLE_TOOL_SEARCH": "false", "CLAUDE_CODE_SKIP_PROMPT_HISTORY": "1"}` | il token esplicito (decisione 22); niente memoria automatica (che `setting_sources` non spegne); con cinque strumenti le definizioni si caricano subito invece di passare dalla ricerca degli strumenti; nessuna trascrizione su disco (decisione 9) |

`translate`, la mappa:
- `StreamEvent` con `event["type"] == "content_block_delta"` e `delta["type"] == "text_delta"` → `TextDelta(delta["text"])`.
- `AssistantMessage`: i suoi `TextBlock` si aggiungono al testo del giro (separati da una riga vuota fra un messaggio e l'altro), e `model` si ricorda. Con `error` `"rate_limit"` si segna `PLAN_LIMIT`, con `"authentication_failed"` o `"billing_error"` si segna `AUTH`, con un altro valore `UNAVAILABLE`.
- `RateLimitEvent` con `rate_limit_info.status == "rejected"` → si segna `PLAN_LIMIT` con `resets_at` (secondi Unix → `datetime` UTC).
- `ResultMessage`: senza `is_error` e con `subtype == "success"` → `TurnFinished(text, ClaudeUsage(model, session_id, input_tokens, output_tokens))`, dove `input_tokens` è la somma di `input_tokens`, `cache_creation_input_tokens` e `cache_read_input_tokens` di `usage`, e i valori assenti restano `None`, non `0`. Altrimenti → `TurnFailed` col guasto segnato. Se non ce n'è uno: `api_error_status` 401/403 → `AUTH`, 429 → `PLAN_LIMIT`, altro → `UNAVAILABLE`.
- Il resto (`SystemMessage`, `UserMessage`, gli altri `StreamEvent`) → niente.

`SdkClaudeClient.run`: senza token → un solo `TurnFailed(NOT_CONFIGURED)`, senza lanciare niente. Altrimenti itera `query(prompt=prompt, options=build_options(...))` e traduce. Ogni eccezione dell'SDK (`ClaudeSDKError` e figlie: `CLINotFoundError`, `CLIConnectionError`, `ProcessError`, `ResultError`), se non è già uscito un `TurnFailed`, diventa `TurnFailed(UNAVAILABLE)` (`ResultError` con `api_error_status` classificato come sopra). Si importa `query` nel modulo (`from claude_agent_sdk import query`) proprio perché i test la sostituiscano lì. Il tempo massimo non sta qui ma nel giro (Task 6).

- [ ] **Step 1: I test che falliscono.**
  - `tests/domain/test_meal_chat.py`: `test_l_avviso_del_limite`, parametrizzato con `now` alle 15:00 UTC del 2026-11-12. `resets_at` alle 17:40 UTC → «… riprova dopo le 18:40»; alle 23:30 UTC (a Roma è il 13 alle 0:30) → «… riprova domani dopo le 0:30»; il 14 alle 8:00 UTC → «… riprova dopo le 9:00 del 14 novembre»; `None` → «… riprova più tardi». Poi `test_gli_altri_avvisi` (ogni `FailureKind` con la sua frase esatta), `test_can_chat` (parametrizzato: ufficiale → vero; bozza, fuori casa, avanzo → falso) e `test_pending_is_stale` (a 299 s no, a 301 s sì, con un tempo massimo di 240).
  - `tests/claude_fakes.py` (non un test): `FakeClaude(ClaudeClient)` con un copione di passi: `Say(text)` (escono `TextDelta` a pezzi di 5 caratteri), `UseTool(name, args)` (chiama `handler(args)` dello strumento **con quel nome fra i `tools` ricevuti** e ne conserva il risultato in `tool_results`), `Finish(input_tokens=…, output_tokens=…)`, `Fail(kind, resets_at=None)`, `Hang()` (aspetta per sempre: serve al tempo massimo). Registra in `calls` il `system_prompt`, il `prompt`, i nomi degli strumenti, `effort` e `max_turns`.
  - `tests/services/test_claude_client.py`, con i **tipi veri** di `claude_agent_sdk` e `app.services.claude.client.query` sostituita da un generatore che registra `options` e restituisce messaggi costruiti a mano:
    1. `test_le_opzioni_di_produzione`: con un token finto nelle impostazioni, uno strumento finto `ping` e `effort="medium"`, `max_turns=12`, le opzioni registrate hanno ogni valore della tabella. Ci sono `allowed_tools == ["mcp__spena__ping"]` e la chiave `"spena"` in `mcp_servers`; `env["CLAUDE_CODE_OAUTH_TOKEN"]` è il token finto.
    2. `test_lo_streaming_diventa_testo_e_fine`. Due `StreamEvent` di testo, un `AssistantMessage` con un `TextBlock` e un `ResultMessage(subtype="success", usage={"input_tokens": 10, "cache_read_input_tokens": 90, "output_tokens": 7}, session_id="s1", …)` danno `[TextDelta, TextDelta, TurnFinished]`. Il testo finale è quello del blocco e `usage == ClaudeUsage(model=…, session_id="s1", input_tokens=100, output_tokens=7)`.
    3. `test_il_limite_del_piano_porta_l_ora`: un `RateLimitEvent(rate_limit_info=RateLimitInfo(status="rejected", resets_at=<t>), …)` poi un `ResultMessage` con `is_error=True` → `TurnFailed(PLAN_LIMIT, resets_at=<t in UTC>)`.
    4. `test_i_guasti`, parametrizzato: `AssistantMessage(error="authentication_failed")` → `AUTH`; `ResultMessage(is_error=True, api_error_status=429)` → `PLAN_LIMIT`; `query` che solleva `CLINotFoundError` → `UNAVAILABLE`. In ogni caso un solo `TurnFailed`.
    5. `test_senza_token_non_parte_niente`: nessuna chiamata a `query`, un solo `TurnFailed(NOT_CONFIGURED)`.
    6. `test_get_claude_client_e_quello_di_produzione`: `isinstance(get_claude_client(), SdkClaudeClient)`.
- [ ] **Step 2: Falliscono.** Il comando di pytest con i due file. Expected: FAIL.
- [ ] **Step 3: Il codice**, con la tabella e la mappa qui sopra. Nella docstring del modulo vanno le pagine dell'SDK da cui vengono le scelte (agent-sdk/python, custom-tools, permissions, claude-code-features, streaming-output, sessions) e la versione `0.2.180`. Poi `--prova` in `check_claude.py`: un giro con `SdkClaudeClient`, `system_prompt` «Rispondi solo: ok», nessuno strumento, `effort="low"`, `max_turns=1`; stampa `prova: ok` o `prova: <failure_notice>`.
- [ ] **Step 4: Passano.** I due file, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(pasti): il client di Claude sull'Agent SDK — strumenti di spena nel processo, integrati e impostazioni spenti, streaming, limite del piano`.

---

### Task 5: Il prompt di sistema e gli strumenti

**Files:**
- Create: `backend/app/services/claude/prompts.py`, `backend/app/services/claude/tools.py`, `backend/tests/services/test_claude_prompts.py`, `backend/tests/services/test_claude_tools.py`

**Interfaces:**
- Consumes: `utensils_prompt_block` (piano 1); `list_pantry`, `list_items`, `ACTIVE_SHOPPING`, `search_ingredients`, `kind_for_category`, `expiry_state`, `today_in_pantry`; `meals_between`, `get_meal`, `get_recipe` (piano 2); `write_meal_recipe`, `DraftLine`, `MealRecipeDraft`, `RecipeWriteRefused` (Task 3); `MAX_MEALS_RANGE_DAYS` (Task 4).
- Produces, in `prompts.py`: le costanti e `dish_system_prompt` del blocco «Interfacce prodotte», più `def render_turn_prompt(context: DishContext, history: Sequence[HistoryItem], text: str) -> str`. `DishContext(today: date, day: date, slot: MealSlot, dish: str, sides: str | None, recipe: Recipe | None)` è la ricetta caricata con le righe. `HistoryItem(role: str, text: str, changes: tuple[str, ...])` porta le righe delle modifiche già scritte a video, per esempio «Ricetta aggiornata: … — annullata».
- Produces, in `tools.py`:
  - `@dataclass class TurnContext`: `session: AsyncSession`, `lock: asyncio.Lock`, `today: date`, `meal_id: uuid.UUID | None`, `conversation_id: uuid.UUID`, `turn_message_id: uuid.UUID`, `on_change: Callable[[RecipeChange], Awaitable[None]]`.
  - `read_tools`, `write_recipe_tool`, `dish_tools`, `SPENA_SERVER`, come nel blocco «Interfacce prodotte». **Ogni handler tiene `ctx.lock` per tutto il tempo in cui usa `ctx.session`**: gli strumenti di sola lettura (`ToolAnnotations(readOnlyHint=True)`) possono arrivare in parallelo, e una sessione async non regge due operazioni insieme.

**Il prompt di sistema, copia fissata** (`dish_system_prompt(block)` = `"\n\n".join([COMMON_PROMPT, DISH_PROMPT, DISH_PANTRY_RULE] + ([block] if block else []))`):

`COMMON_PROMPT`:
```
Sei Claude, dentro spena, l'app di cucina di Mattia: lista della spesa, dispensa, ricette e pasti della settimana. Parli con lui di cucina, in italiano, diretto e breve, come in una chat sul telefono: niente titoli, niente tabelle, al massimo un elenco corto.

Le tue fonti sono gli strumenti di spena, e solo quelli: la dispensa (read_pantry), la lista della spesa (read_shopping_list), i pasti di un intervallo di date con le loro ricette (read_meals), l'anagrafica degli ingredienti (search_ingredients). Non hai file, terminale o web.

Leggi solo quello che serve alla domanda. Una domanda di tecnica («come cuocio il salmone in padella?») non legge niente. Un piatto già deciso legge la dispensa, per farlo con quello che c'è. I pasti passati e l'equilibrio si guardano solo se Mattia ne parla.

Il ricettario di spena non lo leggi e non lo citi: le ricette le inventi tu, partendo dalla dispensa e dall'equilibrio. Le ricette dei pasti passati invece le leggi con read_meals, perché sono la storia («rifacciamo la frittata di martedì»).

La dispensa:
- è già al netto dei pasti pianificati: quello che risulta presente è libero, non sottrarre i pasti già scritti;
- non conosce quantità: ogni voce è «c'è», «quasi finito» o «finito»;
- un pesto, un sugo pronto o un ragù «quasi finito» è un vasetto avviato, non uno che sta finendo: va usato presto, non ricomprato;
- le voci in scadenza, i sughi avviati e le confezioni aperte hanno la precedenza;
- le voci non alimentari non ti riguardano.

Quando proponi, varia: non riproporre ogni volta il piatto più ovvio. Per ogni idea di' in breve cosa usa della dispensa, come si fa e come insaporirla con quello che c'è; al massimo una o due cose da comprare, dette come tali. Se Mattia ha già deciso il piatto, non proporgliene un altro: aiutalo a farlo bene, con i sostituti presi da casa. Le parole incerte le chiedi, non le indovini.

Le dosi: Mattia non ragiona in persone ma in quantità di ingredienti. Ogni ricetta è scritta per il pasto così come lo si mangerà, di norma per lui solo (1 porzione), con dosi misurate su quello che c'è in casa e sulle confezioni («150 g dalla busta da 1 kg»). Se dice «ho solo 2 uova», le dosi ripartono da lì.

L'equilibrio, quando serve, è uno sguardo approssimativo per gruppi, non per calorie: carboidrati (pasta, riso, pane, piadina, patate, gnocchi, canederli, cereali); proteine per fonte (carne rossa, carne bianca, salumi, pesce, uova, legumi, latticini e formaggi); verdura; frutta. I piatti composti si scompongono (il cordon bleu è carne bianca più salume e formaggio, i canederli sono pane più speck, i piselli contano come verdura); se non sai cosa c'è dentro, chiedilo. Gli squilibri si dicono con i numeri dei pasti («cinque pasti su sei hanno la pasta», «niente verdura da martedì»); se i pasti registrati sono pochi, dillo. Un posto passato vuoto è un pasto non registrato, non un digiuno; un pasto fuori casa non conta come un piatto noto. Niente grammi, niente calorie, niente punteggi.

Il sale si stima a spanne contro i 5 g al giorno, sempre detto come stima, e lo segnali quando i pasti salati si accumulano. Valori indicativi per porzione: prosciutto crudo, speck o salame (50 g) 2–3 g; prosciutto cotto o mortadella (50 g) 1–1,5 g; salsiccia (100 g) o un cordon bleu 1,5–2 g; una pizza 4–5 g; una scodella di brodo da dado 2 g; pesto, sugo pronto o ragù 1–1,5 g; canederli in brodo 3–4 g; pane (100 g) o pasta cotta in acqua salata 1–1,5 g; formaggi stagionati (30 g) o due sottilette 0,5–1 g; un cucchiaio di acciughe, capperi, olive o salsa di soia 1–2 g.
```

`DISH_PROMPT`:
```
Questa è la chat di un piatto: un pasto della settimana di Mattia, con la sua ricetta. In testa a ogni messaggio trovi il contesto: che giorno è oggi, il pasto (giorno, pranzo o cena, piatto, accompagnamenti) e la ricetta com'è adesso, oppure che non ce l'ha ancora.

La ricetta la cambi tu, direttamente, con write_recipe: Mattia la vede aggiornata sopra la chat, con le righe cambiate evidenziate, e può annullare la modifica con un tocco. Quindi:
- quando la tua risposta cambia come si fa il piatto (dosi, ingredienti, passaggi), chiama write_recipe nello stesso giro, senza chiedere il permesso, e nel testo di' in breve cosa hai cambiato e perché;
- una domanda che non cambia la ricetta non la riscrive;
- write_recipe vuole la ricetta intera: titolo, porzioni, procedimento a passi numerati e tutte le righe degli ingredienti, anche quelle che non cambiano;
- ogni riga ha l'ingrediente, il ruolo, la dose come la scriveresti («150 g», «2», «q.b.») e una nota facoltativa («congelati, senza scongelare»). Il ruolo è primary se senza quell'ingrediente il piatto non si fa, secondary se si fa anche con poco o senza;
- cerca prima l'ingrediente con search_ingredients e usa il suo ingredient_id; un nome nuovo, con il suo reparto, crea una voce nell'anagrafica di Mattia, quindi solo se proprio non c'è;
- summary è la riga che Mattia legge sotto la tua risposta: poche parole su cosa è cambiato («spinaci congelati, padella unica»);
- se il piatto cambia davvero (le zucchine al posto degli spinaci), aggiorna anche dish, il nome che si legge nella settimana, ed eventualmente sides, gli accompagnamenti. Il giorno e il pasto non li cambi tu;
- se write_recipe rifiuta, non è stato scritto niente: correggi e riprova, oppure spiega a Mattia cosa non torna;
- se il pasto non ha ancora una ricetta e Mattia la chiede, scrivila da zero con write_recipe.
```

`DISH_PANTRY_RULE`:
```
Non scrivi in dispensa né nella lista della spesa. Se una modifica cambia quello che si usa («non ho spinaci, uso le zucchine»), dillo in una riga: Mattia aggiorna spena a mano.
```

**Gli strumenti** (nomi, descrizioni italiane e schemi, fissi):

| Nome | Argomenti | Cosa restituisce |
|---|---|---|
| `read_pantry` | nessuno | La dispensa per reparto, nell'ordine di `IngredientCategory`. Per ogni voce: il nome, il prodotto se c'è, lo stato a parole («c'è», «quasi finito», «finito») e, se c'è, la scadenza («scade il 14 novembre», «scade presto: il 14 novembre», «scaduto il 10 novembre»). Senza le voci non alimentari e le archiviate. Vuota: «La dispensa è vuota.» |
| `read_shopping_list` | nessuno | Le voci attive (`ACTIVE_SHOPPING`), una per riga, con «da comprare» o «nel carrello». Vuota: «La lista della spesa è vuota.» |
| `read_meals` | `start`, `end` (date `AAAA-MM-GG`, obbligatorie) | Per ogni giorno dell'intervallo, pranzo e cena: il piatto, gli accompagnamenti, i segni («fuori casa», «bozza», «avanzo di …») e, se c'è, la ricetta (righe con dose e procedimento); un posto vuoto è «(vuoto)». Con `end < start`, o con più di `MAX_MEALS_RANGE_DAYS` giorni: `is_error` con «Chiedi al massimo 28 giorni alla volta, con end non prima di start.» |
| `search_ingredients` | `name` (obbligatorio) | Fino a 8 ingredienti **alimentari** (`kind=FOOD`): «- ‹nome› · id ‹uuid› · reparto ‹reparto›». Nessuno: «Nessun ingrediente con questo nome: usa name e department nella riga.» |
| `write_recipe` | `title` (1–200), `servings` (intero 1–50), `description` (facoltativo), `instructions` (non vuoto), `ingredients` (almeno uno: `ingredient_id` oppure `name` + `department` fra i reparti alimentari di `IngredientCategory`; `role` `primary`/`secondary`; `quantity` ≤ 100 caratteri, facoltativo; `note` ≤ 300, facoltativo), `summary` (1–200), `dish` (facoltativo, 1–200), `sides` (facoltativo, ≤ 200; stringa vuota = togli) | Senza pasto (`ctx.meal_id is None`): `is_error`. Argomenti non validi, o in più (giorno, pasto): `is_error` con l'errore di validazione in breve, e niente scritto. Poi `write_meal_recipe`, `commit`, `await ctx.on_change(change)`, e «Scritta. Mattia vede la ricetta aggiornata.» `RecipeWriteRefused` o `MealRefusal`: `is_error` con il loro messaggio. |

Gli schemi sono JSON Schema completi (`type`, `properties`, `required`, `additionalProperties: false`, `enum` per `role` e `department`), con le descrizioni dei campi in italiano. Gli argomenti di `write_recipe` si validano con un modello Pydantic (`extra="forbid"`) prima di toccare il database.

- [ ] **Step 1: I test che falliscono.**
  - `test_claude_prompts.py`: `test_il_prompt_del_piatto_senza_utensili` (è esattamente `COMMON_PROMPT + "\n\n" + DISH_PROMPT + "\n\n" + DISH_PANTRY_RULE`); `test_il_prompt_del_piatto_con_gli_utensili` (finisce con il blocco di `render_utensils_block([("frusta elettrica", None)])` del piano 1); `test_il_prompt_dice_le_regole_della_skill`, un controllo di presenza su frasi chiave che protegge dalle riscritture: «già al netto dei pasti pianificati», «vasetto avviato», «5 g al giorno», «1 porzione», «Il ricettario di spena non lo leggi», «Il giorno e il pasto non li cambi tu»; `test_render_turn_prompt` (con una ricetta di due righe: il testo contiene «Oggi: giovedì 12 novembre 2026», il pasto «martedì 11 novembre, cena», il piatto, gli accompagnamenti, ogni riga con l'id dell'ingrediente e la dose, il procedimento, la storia nell'ordine con «Ricetta aggiornata: … — annullata», e in fondo il messaggio nuovo; senza ricetta: «Il pasto non ha ancora una ricetta.»).
  - `test_claude_tools.py`. Ogni strumento si prova chiamando `tool.handler(args)` sugli oggetti che `dish_tools(ctx)` restituisce, con `ctx.session = db_session`:
    1. `test_dish_tools_sono_i_cinque_di_spena`: nomi nell'ordine `read_pantry`, `read_shopping_list`, `read_meals`, `search_ingredients`, `write_recipe`; i primi quattro con `readOnlyHint` vero.
    2. `test_read_pantry_per_reparto_senza_non_alimentari`: spinaci `low` con scadenza fra 3 giorni, uova `available`, detersivo (`casa`). Il testo contiene «quasi finito» e «scade presto», e non contiene «detersivo».
    3. `test_read_shopping_list`: una voce da comprare e una nel carrello → le due frasi.
    4. `test_read_meals_con_le_ricette_e_i_posti_vuoti`: una cena con ricetta il 10, nient'altro, con `start=end=2026-11-10`. C'è il piatto, una riga della ricetta, e «(vuoto)» per il pranzo.
    5. `test_read_meals_rifiuta_un_intervallo_troppo_lungo` (29 giorni) e con `end` prima di `start`: `is_error`.
    6. `test_search_ingredients_solo_alimentari`: «spinaci» dà l'id; «detersivo» dà la frase del niente.
    7. `test_write_recipe_scrive_e_avvisa`: su un pasto ufficiale senza ricetta, il risultato non è un errore, il pasto ha la ricetta e `on_change` è stato chiamato una volta con la modifica.
    8. `test_write_recipe_non_accetta_il_posto`: con `"day": "2026-11-13"` fra gli argomenti → `is_error`, e niente scritto.
    9. `test_write_recipe_rifiutata_lo_dice_a_claude`: una riga col detersivo → `is_error` con il messaggio di `RecipeWriteRefused`, `on_change` non chiamato.
    10. `test_due_letture_in_parallelo_non_si_pestano`: `asyncio.gather` di `read_pantry` e `read_shopping_list` sulla stessa sessione → nessuna eccezione.
- [ ] **Step 2: Falliscono.** Il comando di pytest con i due file. Expected: FAIL.
- [ ] **Step 3: Il codice.** I nomi italiani dei giorni e dei mesi stanno in `prompts.py` (una tupla per ciascuno), perché il backend non ne ha. Le date di `read_meals` e del contesto si scrivono allo stesso modo. Un commento in `dish_tools` segna il punto dove il piano 4 aggiunge i suoi strumenti, e uno accanto a `DISH_PANTRY_RULE` dice che il piano 4 la sostituisce con la regola delle schede (§6.2).
- [ ] **Step 4: Passano.** I due file, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(pasti): il prompt della skill pasti adattato a spena, e gli strumenti di Claude — dispensa, lista, pasti, anagrafica, scrittura della ricetta`.

---

### Task 6: Il giro della chat

**Files:**
- Create: `backend/app/repositories/conversations.py`, `backend/app/services/meal_chat.py`, `backend/app/services/chat_turns.py`, `backend/tests/services/test_meal_chat_turn.py`, `backend/tests/services/test_chat_turns.py`
- Modify: `backend/app/services/llm.py` (`MEAL_CHAT = "meal_chat"` in `LlmCallSite`, con un commento: la chat dei piatti, su Claude via Agent SDK, sul piano), `backend/app/domain/spending.py` (`"meal_chat": "Chat dei piatti"` in `CALL_SITE_LABELS`; `PLAN_CALL_SITES: frozenset[str] = frozenset({"meal_chat"})` e `PLAN_NOTE = "sul piano di Claude, non a consumo"`), `backend/app/core/db.py` (`def get_session_factory() -> async_sessionmaker[AsyncSession]`, che restituisce `SessionLocal`)

**Interfaces:**
- Consumes: Task 2–5; `record_llm_call`, `LlmUsage`; `utensils_prompt_block`.
- Produces, in `app.repositories.conversations`: `dish_conversation(session, meal_id) -> Conversation | None`; `get_or_create_dish_conversation(session, meal_id) -> Conversation`; `messages_of(session, conversation_id) -> list[ConversationMessage]` (in ordine di `created_at`, poi `id`); `changes_of(session, conversation_id) -> list[RecipeChange]`; `latest_turn(session, conversation_id) -> ConversationMessage | None` (l'ultimo messaggio `user`).
- Produces, in `app.services.meal_chat`:
  - `@dataclass(frozen=True) class ChatEvent`: `name: Literal["delta", "change", "done", "error"]`, `data: dict`.
  - `run_dish_turn`, con la firma del blocco «Interfacce prodotte» (`emit: Callable[[ChatEvent], Awaitable[None]]`).
  - `async def dish_chat_view(session, meal: Meal, *, replying: bool, now: datetime) -> DishChatOut`, la vista che la `GET` restituisce e che il giro usa per i dati degli eventi (gli schemi sono del Task 7: crea qui `app/schemas/meal_chat.py` con le classi del Task 7, così il giro ha i suoi dati).
- Produces, in `app.services.chat_turns`: `class TurnRegistry`, con `def running(self, conversation_id) -> bool`, `def start(self, conversation_id, run: Callable[[Emit], Awaitable[None]]) -> AsyncIterator[ChatEvent]` e `async def wait(self, conversation_id) -> None` (per i test e per lo spegnimento). C'è un'istanza di modulo, con `get_turn_registry()`.

**Il giro** (`run_dish_turn`), nell'ordine:
1. Con una sessione nuova da `session_factory`: rilegge il messaggio (`pending`), la conversazione e il pasto. Se il pasto non c'è più, o `can_chat` è falso, il messaggio passa a `failed` con `INTERRUPTED`, esce l'evento `error` e il giro finisce.
2. Costruisce il prompt: `dish_system_prompt(await utensils_prompt_block(session))` e `render_turn_prompt(...)`, con gli ultimi `HISTORY_MESSAGES` messaggi `sent` della conversazione (esclusi il messaggio di questo giro, i `failed` e i `pending`) e le righe delle loro modifiche.
3. `ctx = TurnContext(...)` con `on_change`, che emette `change` (dati: il `RecipeChangeOut` della modifica).
4. Itera `client.run(system_prompt, prompt, tools=dish_tools(ctx), effort=DISH_EFFORT, max_turns=DISH_MAX_TURNS)` dentro `asyncio.timeout(timeout_seconds)`. `TextDelta` → evento `delta` `{"text": …}`. `TurnFinished` → con `ctx.lock`, il messaggio dell'utente diventa `sent`, nasce il messaggio `assistant` (`reply_to_id` = l'utente; il testo è `TurnFinished.text`, o il testo dei `delta` se quello è vuoto), si registra `llm_calls` (`MEAL_CHAT`, `ok=True`, `model`, `generation_id` = `session_id`, `prompt_tokens` = `input_tokens`, `completion_tokens` = `output_tokens`, `cost_usd=None`), `commit`, ed esce `done` `{"chat": DishChatOut}`. `TurnFailed`, o il tempo massimo (`TIMEOUT`) → il messaggio dell'utente diventa `failed` con `failure` e `notice` (`failure_notice(kind, resets_at, now)`), si registra `llm_calls` con `ok=False` (tranne che per `NOT_CONFIGURED`, che non ha chiamato niente), `commit`, ed esce `error` `{"code": kind, "notice": …, "chat": DishChatOut}`.
5. Le modifiche già scritte da `write_recipe` restano anche se il giro poi fallisce: ognuna è stata committata da sola (§9: le scritture sono atomiche).

**`dish_chat_view`**: i messaggi in ordine. Ogni messaggio porta le sue modifiche: quelle del giro vanno sotto la risposta di Claude, o sotto il messaggio dell'utente se la risposta non c'è. `undoable` viene da `change_is_undoable`. Un messaggio `pending` con `pending_is_stale(...)` vero e nessun giro vivo (`replying` falso) si mostra `failed` con l'avviso `INTERRUPTED`, e così si scrive anche nel database alla prima lettura. `highlight` sono i `changed` dell'ultima modifica viva (non annullata e annullabile) del giro più recente (`latest_turn`), altrimenti `null`. Ci sono anche `claude_ready = claude_configured()` e `claude_notice` (l'avviso `NOT_CONFIGURED` quando manca il token).

- [ ] **Step 1: I test che falliscono.** `tests/services/test_meal_chat_turn.py`, con `FakeClaude` e una `session_factory` legata alla connessione del test (`async_sessionmaker(bind=db_session.bind, expire_on_commit=False, join_transaction_mode="create_savepoint")`). Gli eventi si raccolgono in una lista.
  1. `test_un_giro_che_risponde`: copione `Say("Prendine 150 g."), Finish(input_tokens=1200, output_tokens=80)`. Gli eventi sono dei `delta` che insieme fanno il testo, poi un `done`. Nel database il messaggio dell'utente è `sent` e quello di Claude ha il testo e `reply_to_id`. In `llm_calls` c'è una riga `meal_chat`, `ok`, con `prompt_tokens == 1200`, `completion_tokens == 80` e `cost_usd is None`.
  2. `test_il_giro_usa_prompt_strumenti_e_sforzo_della_chat_del_piatto`: in `FakeClaude.calls[0]`, `effort == "medium"`, `max_turns == 12`, i cinque strumenti, il prompt di sistema uguale a `dish_system_prompt(...)`, e il prompt che contiene il piatto e il messaggio.
  3. `test_l_esempio_degli_spinaci`. La cena «Frittata di spinaci e parmigiano» ha la ricetta con «spinaci 200 g». Il copione è `UseTool("write_recipe", {… spinaci "150 g", nota "congelati, senza scongelare", summary "spinaci congelati, padella unica"}), Say("…"), Finish()`. Gli eventi sono `change` (con `summary` e `undoable: true`), `delta`, `done`. La ricetta nel database ha «150 g», e `done.chat.highlight.ingredient_ids == [spinaci]`.
  4. `test_la_ricetta_scritta_da_zero`: pasto senza ricetta; dopo il `write_recipe` il pasto ha una ricetta `ai`, fuori dal ricettario, e la modifica ha `created_recipe`.
  5. `test_il_limite_del_piano`: copione `Fail(PLAN_LIMIT, resets_at=…)` → evento `error` con `code == "plan_limit"` e l'avviso con l'ora. Il messaggio è `failed` con lo stesso `notice`, e `llm_calls` ha una riga `ok=False`.
  6. `test_senza_token_nessuna_riga_di_spesa`: `Fail(NOT_CONFIGURED)` → `error`, nessuna riga in `llm_calls`.
  7. `test_il_tempo_massimo`: copione `Hang()` con `timeout_seconds=0.2` → `error` con `code == "timeout"`.
  8. `test_una_modifica_resta_anche_se_poi_il_giro_fallisce`: `UseTool("write_recipe", …), Fail(UNAVAILABLE)` → la ricetta è cambiata, la modifica c'è ed è annullabile, il messaggio è `failed`.
  9. `test_la_cronologia_torna_nel_prompt`: due giri di fila; il prompt del secondo contiene il messaggio e la risposta del primo, e la riga «Ricetta aggiornata: …».
  10. `test_l_evidenza_sparisce_al_messaggio_dopo`: dopo il giro 3, un nuovo messaggio `pending` dell'utente → `dish_chat_view(...).highlight is None`.
  11. `test_un_attesa_orfana_conta_come_interrotta`: un messaggio `pending` creato 10 minuti fa, nessun giro vivo → la vista lo dà `failed` con «La risposta si è interrotta. Riprova.», e nel database è `failed`.

  `tests/services/test_chat_turns.py`:
  12. `test_un_giro_alla_volta`: mentre un giro è vivo, `running` è vero; dopo `wait`, falso.
  13. `test_il_giro_finisce_anche_senza_chi_legge`: si avvia un giro che emette e si chiude, si abbandona l'iteratore dopo il primo evento (`aclose`), e `wait` torna con il giro completato (un flag scritto dal giro alla fine).
- [ ] **Step 2: Falliscono.** Il comando di pytest con i due file. Expected: FAIL.
- [ ] **Step 3: Il codice.** `TurnRegistry.start` crea il task con `asyncio.create_task` e lo tiene in un dizionario finché non finisce. Gli eventi vanno in una coda per chi legge: chi legge e se ne va toglie solo la sua coda, il task continua. Un'eccezione inattesa nel giro va nei log (`logger.exception`) e lascia il messaggio `failed` con `UNAVAILABLE`, mai `pending`. La docstring di `meal_chat.py` dice perché la cronologia si ricostruisce dai messaggi (decisione 9) e perché il giro non dipende dalla richiesta (decisione 11).
- [ ] **Step 4: Passano.** I due file, poi la suite intera (`test_ogni_sezione_del_client_llm_ha_un_nome_a_video` compreso). Expected: PASS.
- [ ] **Step 5: Commit** — `feat(pasti): il giro della chat del piatto — cronologia da spena, una risposta alla volta, registrata nelle spese senza costo`.

---

### Task 7: Le rotte della chat, e Nginx

**Files:**
- Create: `backend/app/api/meal_chat.py`, `backend/tests/api/test_meal_chat.py`, `backend/tests/test_nginx_chat.py`
- Modify: `backend/app/schemas/meal_chat.py` (Task 6), `backend/app/schemas/meal.py` (`MealOut.can_chat: bool`), `backend/app/api/meals.py` (`meal_out` riempie `can_chat` con `can_chat(meal)`), `backend/app/main.py` (`include_router`), `frontend/nginx.conf` (una `location` sopra `location /api/`)

**Interfaces:**
- Produces, in `app.schemas.meal_chat`:
  - `RecipeChangeOut`: `id`, `summary: str`, `created_recipe: bool`, `undone: bool`, `undoable: bool`.
  - `ChatMessageOut`: `id`, `role: Literal["user", "assistant"]`, `text: str`, `status: Literal["pending", "sent", "failed"]`, `notice: str | None`, `created_at: datetime`, `changes: list[RecipeChangeOut]`.
  - `HighlightOut`: `ingredient_ids: list[uuid.UUID]`, `title: bool`, `servings: bool`, `instructions: bool`, `description: bool`.
  - `DishChatOut`: `meal_id`, `conversation_id: uuid | None`, `messages: list[ChatMessageOut]`, `replying: bool`, `highlight: HighlightOut | None`, `claude_ready: bool`, `claude_notice: str | None`.
  - `ChatMessageIn`: `text: str` (ripulito ai bordi, 1–`MESSAGE_MAX_CHARS`), `retry_of: uuid | None = None`.
- Produces, in `app.api.meal_chat` (`router = APIRouter(prefix="/api/v1/meals/{meal_id}/chat", dependencies=[Depends(require_session)])`), con le dipendenze `get_session`, `get_session_factory`, `get_claude_client` e `get_turn_registry`:
  - `GET ""` → `DishChatOut`. 404 «pasto inesistente»; 409 `{"code": "no_chat_here", "detail": "Questo pasto non ha una chat: è una bozza, è fuori casa o è un avanzo."}` se `can_chat` è falso.
  - `POST "/messages"` (`ChatMessageIn`). Prima dello stream, in JSON: 404; 409 `no_chat_here`; 503 `{"code": "claude_not_configured", "detail": <avviso NOT_CONFIGURED>}` senza salvare niente; 409 `{"code": "claude_busy", "detail": BUSY_NOTICE}` se il registro ha un giro vivo o c'è un `pending` non orfano; 422 per il testo. Con `retry_of`, il messaggio indicato (deve essere un `user` `failed` di questa conversazione, altrimenti 404) si cancella nella stessa transazione. Poi `get_or_create_dish_conversation`, il messaggio `pending`, `commit`, `registry.start(...)` con `run_dish_turn`, e `StreamingResponse(media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})`. Lo stream comincia con `event: start` (`{"message": ChatMessageOut}` del messaggio dell'utente), poi passa gli eventi del giro (`event: <name>\ndata: <json>\n\n`) e un `: ping\n\n` ogni 15 s di silenzio, e si chiude dopo `done` o `error`.
  - `POST "/changes/{change_id}/undo"` → `DishChatOut`. 404 se la modifica non è di questo pasto; 409 `{"code": …, "detail": …}` da `ChangeRefusal`.
- `frontend/nginx.conf`:
  ```
  # La chat dei piatti (Pasti, piano 3): la risposta di Claude arriva un pezzo alla volta
  # (SSE). Senza `proxy_buffering off` Nginx la tratterrebbe fino alla fine; il backend
  # manda un ping ogni 15 s e risponde entro 240 s.
  location ~ ^/api/v1/meals/[^/]+/chat/messages$ {
    proxy_pass http://backend:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 300s;
    proxy_send_timeout 300s;
  }
  ```

- [ ] **Step 1: I test che falliscono.** `tests/api/test_meal_chat.py`, con `logged_client`, `FakeClaude` messo in `app.dependency_overrides[get_claude_client]` e una `session_factory` come nel Task 6 in `get_session_factory`. La risposta SSE si legge intera (con `ASGITransport` arriva alla fine del giro) e si spezza in eventi con un aiutante del test.
  1. `test_la_chat_di_un_pasto_nuovo_e_vuota`: `GET` → `conversation_id is None`, `messages == []`, `replying is False`, `claude_ready` com'è nelle impostazioni.
  2. `test_un_messaggio_e_la_sua_risposta_in_streaming`: gli eventi sono `start`, almeno un `delta`, `done`. Dopo, `GET` ha i due messaggi; l'intestazione è `text/event-stream` con `X-Accel-Buffering: no`.
  3. `test_la_modifica_e_la_sua_riga`: con il copione degli spinaci, `GET` ha sotto la risposta una modifica `{"summary": "spinaci congelati, padella unica", "created_recipe": false, "undone": false, "undoable": true}` e `highlight.ingredient_ids == [spinaci]`. `GET /api/v1/recipes/{id}` ha «150 g».
  4. `test_annulla_dalla_rotta`: `POST /changes/{id}/undo` → 200; la modifica ha `undone: true`, `highlight is None` e la ricetta è di nuovo «200 g». Una seconda volta → 409 `change_undone`.
  5. `test_annulla_dopo_il_modulo_e_409`: `PUT /api/v1/recipes/{id}` con un titolo nuovo, poi `undo` → 409 `change_stale` con la frase esatta.
  6. `test_senza_token_503_e_niente_salvato`: il finto non serve, perché il controllo è prima (token vuoto nelle impostazioni). → 503 `claude_not_configured` con l'avviso, e `GET` non ha messaggi.
  7. `test_un_secondo_messaggio_mentre_risponde_e_409`: un messaggio `pending` recente già nel database → 409 `claude_busy` con `BUSY_NOTICE`.
  8. `test_riprova_toglie_il_tentativo_fallito`: copione `Fail(UNAVAILABLE)` → `error`, e `GET` ha il messaggio `failed` con l'avviso. Poi `POST` con lo stesso testo e `retry_of` e un copione che risponde → `GET` ha un solo messaggio dell'utente, `sent`, e la risposta.
  9. `test_il_giro_finisce_anche_se_chi_legge_se_ne_va`: con un finto più lento (un `asyncio.sleep(0.05)` fra i pezzi), si apre lo stream con `client.stream(...)`, si legge il primo evento e si chiude; poi `await registry.wait(conversation_id)`, e `GET` ha la risposta e la modifica.
  10. `test_niente_chat_per_bozza_fuori_casa_avanzo`, parametrizzato: `GET` e `POST` → 409 `no_chat_here`.
  11. `test_il_pasto_dice_se_ha_la_chat`: `GET /api/v1/meals/{id}` → `can_chat` vero per un pasto ufficiale, falso per un fuori casa.
  12. `test_un_testo_vuoto_e_422` e `test_senza_accesso_401`.

  `tests/test_nginx_chat.py`, sul modello di `test_nginx_webhook.py`: `test_nginx_non_trattiene_la_risposta_di_claude`. C'è la `location ~ ^/api/v1/meals/[^/]+/chat/messages$`, con `proxy_buffering off;`, `proxy_pass http://backend:8000;` e un `proxy_read_timeout` in secondi maggiore di `Settings().claude_reply_timeout_seconds`.
- [ ] **Step 2: Falliscono.** Il comando di pytest con i due file. Expected: FAIL.
- [ ] **Step 3: Il codice**, come nel blocco Interfaces. Lo stream sta in una funzione generatrice che legge dal registro. Se il client se ne va, Starlette cancella il generatore, e il `finally` chiude solo l'iteratore del registro.
- [ ] **Step 4: Passano.** I due file, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(pasti): le rotte della chat del piatto — SSE, una risposta alla volta, «Annulla»; Nginx non trattiene lo streaming`.

---

### Task 8: Le spese sul piano di Claude

**Files:**
- Modify: `backend/app/repositories/llm_calls.py` (`SectionSpend` riceve `prompt_tokens: int = 0` e `completion_tokens: int = 0`; `spend_by_section` somma le due colonne con `coalesce`), `backend/app/schemas/spending.py` (`PlanSectionOut`; `SpendingOut.plan_sections: list[PlanSectionOut] = []`), `backend/app/services/spending.py`, `frontend/src/features/spending/types.ts`, `frontend/src/features/spending/SpendingScreen.tsx`, `frontend/src/features/spending/format.ts`
- Create: `backend/tests/api/test_llm_spending_plan.py`, `frontend/src/features/spending/PlanSections.tsx` e il suo test

**Interfaces:**
- Produces: `PlanSectionOut`: `call_site: str`, `label: str`, `calls: int`, `tokens: int` (prompt più completamento), `note: str` (`PLAN_NOTE`). In `spending_report`, le sezioni di `PLAN_CALL_SITES` escono da `sections`, `total_usd`, `calls` e `unpriced_calls` ed entrano in `plan_sections`. `days` non cambia: le chiamate sul piano non hanno costo.
- Produces, nel frontend: `interface PlanSection { call_site: string; label: string; calls: number; tokens: number; note: string }`; `Spending.plan_sections?: PlanSection[]` (facoltativo: una risposta vecchia in cache non l'ha); `formatTokens(n: number): string` («48.300», separatore delle migliaia italiano); `PlanSections({ sections })`, cioè `SectionHeading` «Claude» e una `Card` con una riga per sezione: il nome, poi `«{callsText(calls)} · {formatTokens(tokens)} token»`, poi la nota.

- [ ] **Step 1: I test che falliscono.**
  - `test_llm_spending_plan.py`: due `recipe_draft` da 0,01 $ e tre `meal_chat` (`cost_usd` NULL, 1000 e 200 token ciascuna, una fallita). Si controlla `total_usd == 0.02`, `calls == 2`, `unpriced_calls == 0`; nessuna sezione `meal_chat` in `sections`; `plan_sections == [{"call_site": "meal_chat", "label": "Chat dei piatti", "calls": 3, "tokens": 3600, "note": "sul piano di Claude, non a consumo"}]`. Poi `test_solo_chiamate_sul_piano`: con solo `meal_chat`, `calls == 0` e `plan_sections` con una voce.
  - `PlanSections.test.tsx`: si leggono «Claude», «Chat dei piatti», «3 chiamate · 3.600 token» (se `callsText` scrive diverso, usa la sua forma: il test la importa) e «sul piano di Claude, non a consumo».
  - Un caso in `SpendingScreen.test.tsx`: con `calls: 0` e una `plan_sections`, si legge il blocco «Claude» oltre alla frase del periodo vuoto.
- [ ] **Step 2: Falliscono.** pytest con il file nuovo; `npx vitest run src/features/spending`. Expected: FAIL.
- [ ] **Step 3: Il codice.** In `Report`, `PlanSections` va in fondo, fuori dalla condizione `total_usd > 0`, e la frase vuota resta com'è.
- [ ] **Step 4: Passano.** La suite backend intera, `npx vitest run`, `npm run typecheck`, `npm run lint`. Expected: verdi. Se un test di oggi di `test_llm_spending.py` cade, il cambio ha toccato il conto a consumo: si corregge il codice.
- [ ] **Step 5: Commit** — `feat(spese): le chiamate sul piano di Claude contate a parte, con chiamate e token, «sul piano di Claude, non a consumo»`.

---

### Task 9: La chat nel frontend

**Files:**
- Modify: `frontend/src/api/client.ts` (`apiStream`), `frontend/src/domain/types.ts` (tipi nuovi in fondo; `Meal.can_chat?: boolean`)
- Create: `frontend/src/features/meal-chat/sse.ts`, `api.ts`, `ChatThread.tsx`, `DishChat.tsx`, e i test `sse.test.ts`, `ChatThread.test.tsx`, `DishChat.test.tsx`

**Interfaces:**
- Produces, in `client.ts`: `export async function apiStream(path: string, init: RequestInit = {}): Promise<Response>`, che passa da `request` (stessi errori, stesso 401) e restituisce la risposta senza leggerne il corpo.
- Produces, in `domain/types.ts`: `RecipeChange`, `ChatMessage`, `RecipeHighlight`, `DishChat`, che rispecchiano gli schemi del Task 7 (date come stringhe). E `type ChatStreamEvent = { name: "start"; message: ChatMessage } | { name: "delta"; text: string } | { name: "change"; change: RecipeChange } | { name: "done"; chat: DishChat } | { name: "error"; code: string; notice: string; chat: DishChat }`.
- Produces, in `sse.ts`: `export async function readSse(response: Response, onEvent: (event: ChatStreamEvent) => void): Promise<void>`. Legge `response.body` con `getReader()` e `TextDecoder`, spezza sugli `\n\n`, ignora le righe che cominciano con `:`, unisce le righe `data:` e fa `JSON.parse`. Un evento sconosciuto si ignora.
- Produces, in `api.ts`: `dishChatKey(mealId)`; `fetchDishChat(mealId): Promise<DishChat>`; `sendDishMessage(mealId, body: { text: string; retry_of?: string }, onEvent): Promise<void>` (`apiStream` + `readSse`); `undoRecipeChange(mealId, changeId): Promise<DishChat>`.
- Produces: `ChatThread({ messages, streaming, onUndo, onRetry })`, cioè i fumetti, riusabili dalla pianificazione. `DishChat({ mealId, hasRecipe }: { mealId: string; hasRecipe: boolean })`, la chat del piatto completa. Il hook `useDishChat(mealId, enabled)` (`useQuery` su `dishChatKey`; `refetchInterval: 2000` finché `replying` è vero).

**La schermata** (`DishChat`): `SectionHeading` «Chat con Claude». Se `claude_ready` è falso, un `Alert` con `claude_notice` in testa. Vuota, una riga d'aiuto: con la ricetta «Chiedi a Claude di cambiare la ricetta: la vedi aggiornata qui sopra.», senza «Chiedi a Claude di scrivere la ricetta di questo piatto.». Poi `ChatThread`, con i messaggi di Mattia a destra e quelli di Claude a sinistra, il testo con `whitespace-pre-wrap` e i colori dai token esistenti (per esempio `bg-brand-tint` con `text-ink` per Mattia, il fondo della `Card` per Claude). Sotto ogni messaggio vengono le sue modifiche: «Ricetta aggiornata: {summary}», oppure «Ricetta scritta: {summary}» con `created_recipe`, più « — annullata» se `undone`, e un pulsante `ghost` «Annulla» se `undoable`. Un messaggio `failed` ha sotto un `Alert` con il suo `notice` e il pulsante «Riprova». In fondo un `<form>` con un `<textarea>` (`aria-label` «Messaggio per Claude», segnaposto «Scrivi a Claude…», `maxLength` 4000) e «Invia» (`type="submit"`, non pronto con il campo vuoto o mentre Claude risponde). Invio della tastiera = a capo.
- Mentre si invia: il testo esce dal campo e compare subito come fumetto (`start`). I `delta` si accodano in un fumetto di Claude, con «Claude sta scrivendo…» in un `aria-live="polite"`. Ogni `change` invalida `["recipe", …]` (la ricetta del pasto) e `["meals"]`. `done` ed `error` mettono la `DishChat` arrivata nella cache (`setQueryData`) e invalidano `["meals"]`.
- Un rifiuto prima dello stream: 503 `claude_not_configured` → il testo **torna nel campo** e compare un `Alert` con il `detail`; 409 `claude_busy` → `Alert` con il `detail` e il testo nel campo; ogni altro errore → il `detail` in un `Alert`, e il testo nel campo.
- «Annulla» → `undoRecipeChange`, poi `setQueryData`, l'invalidazione di `["recipe"]` e `["meals"]` e l'avviso (`useNotice`) «Modifica annullata.». Un 409 mostra il `detail` in un `Alert`.
- «Riprova» → `sendDishMessage` con lo stesso testo e `retry_of`.
- Ogni bersaglio alto almeno 44 px (`min-h-11`).

- [ ] **Step 1: I test che falliscono.**
  - `sse.test.ts`: un `Response` costruito su un `ReadableStream` che spezza gli eventi a metà riga in tre pezzi, con un `: ping` in mezzo, dà gli eventi interi e in ordine; un `data:` su due righe si unisce; un evento con un nome sconosciuto si ignora.
  - `ChatThread.test.tsx`: (1) un messaggio dell'utente e uno di Claude con una modifica annullabile → «Ricetta aggiornata: spinaci congelati, padella unica» e il pulsante «Annulla», che chiama `onUndo` con l'id; (2) una modifica annullata → «Ricetta aggiornata: spinaci congelati, padella unica — annullata» e nessun «Annulla»; (3) `created_recipe` → «Ricetta scritta: …»; (4) un messaggio `failed` → il suo avviso e «Riprova», che chiama `onRetry`.
  - `DishChat.test.tsx` (con `fetch` sostituito, come negli altri test, e una risposta in streaming costruita con `ReadableStream`): (1) vuota e con la ricetta → la riga d'aiuto con la ricetta; (2) «Invia» manda `POST /api/v1/meals/m1/chat/messages` con `{ text }`, il fumetto dell'utente compare subito, i `delta` compongono la risposta, e dopo `done` «Claude sta scrivendo…» non c'è più; (3) un evento `change` fa ripartire la richiesta di `GET /api/v1/recipes/r1`; (4) 503 → l'`Alert` con «Claude non è collegato: manca il token del piano sul server.» e il campo che contiene ancora il testo scritto; (5) un `error` con «Claude non risponde: hai raggiunto il limite del piano, riprova dopo le 18:40» → l'avviso sotto il messaggio e «Riprova», che rimanda con `retry_of`; (6) «Annulla» → `POST …/changes/c1/undo` e l'avviso «Modifica annullata.»; (7) con `claude_ready: false` l'`Alert` in testa c'è già prima di scrivere.
- [ ] **Step 2: Falliscono.** `npx vitest run src/features/meal-chat`. Expected: FAIL.
- [ ] **Step 3: Il codice** del blocco Interfaces. Il frontend non decide niente: le righe, «Annulla», gli avvisi e l'evidenza arrivano dal server.
- [ ] **Step 4: Passano.** `npx vitest run`, `npm run typecheck`, `npm run lint`. Expected: verdi.
- [ ] **Step 5: Commit** — `feat(pasti): la chat con Claude nel frontend — streaming da una POST, «Ricetta aggiornata» con «Annulla», l'avviso con «Riprova»`.

---

### Task 10: La chat nel piatto, e le righe evidenziate

**Files:**
- Modify: `frontend/src/features/meals/MealScreen.tsx` (il commento del piano 2 che segna il posto della chat diventa la chat), `frontend/src/features/cooking/RecipeDetailScreen.tsx` (`RecipeDetailView` riceve `highlight`; `IngredientRow` riceve `changed: boolean`), `MealScreen.test.tsx`, `RecipeDetailScreen.test.tsx`

**Interfaces:**
- Consumes: `DishChat`, `useDishChat` (Task 9); `Meal.can_chat` (Task 7); `RecipeDetailView` con `meal` (piano 2).
- Produces: la prop `highlight?: RecipeHighlight | null` di `RecipeDetailView`. Una riga con l'ingrediente in `ingredient_ids` ha `data-changed=""`, il fondo `bg-brand-tint` e un testo per i lettori di schermo «(cambiata)». Con `title`, `servings` o `instructions` veri, anche quei pezzi hanno lo stesso segno. Senza `highlight` non cambia niente rispetto a oggi.
- In `MealScreen`: se `meal.can_chat`, si chiama `useDishChat(meal.id, true)`, si passa `highlight={chat.data?.highlight ?? null}` alla `RecipeDetailView` del pasto (non a quella in sola lettura di un avanzo) e si rende `<DishChat mealId={meal.id} hasRecipe={meal.recipe !== null} />` sotto la ricetta. Senza ricetta va sotto «Questo pasto non ha ancora una ricetta.», che tiene «Scrivi la ricetta» e «Scegli dal ricettario».

- [ ] **Step 1: I test che falliscono.**
  - `MealScreen.test.tsx`, quattro casi: (1) un pasto con `can_chat: true` e una ricetta → si leggono «Chat con Claude» e il campo «Messaggio per Claude»; (2) con `can_chat: false` (fuori casa) → nessuna chat; (3) con una chat il cui `highlight.ingredient_ids` contiene l'ingrediente «spinaci» → la riga degli spinaci ha `data-changed` e le altre no; (4) un pasto senza ricetta con la chat → «Scrivi la ricetta» e la riga d'aiuto «Chiedi a Claude di scrivere la ricetta di questo piatto.» insieme.
  - `RecipeDetailScreen.test.tsx`, un caso: senza `highlight` nessuna riga ha `data-changed` (e i test di oggi restano verdi).
- [ ] **Step 2: Falliscono.** `npx vitest run src/features/meals src/features/cooking`. Expected: FAIL.
- [ ] **Step 3: Il codice.** Quando un `change` cambia la ricetta, `DishChat` invalida la stessa chiave che `RecipeDetailView` legge, e la ricetta sopra si aggiorna da sé.
- [ ] **Step 4: Passano.** `npx vitest run`, `npm run typecheck`, `npm run lint`, `npm run build`. Expected: verdi.
- [ ] **Step 5: Commit** — `feat(pasti): la chat sotto la ricetta del piatto, con le righe cambiate evidenziate fino al messaggio dopo`.

---

### Task 11: Nel browser vero, a 375 px, nei due temi

**Files:**
- Create: `backend/tests/e2e_chat.py`, `backend/tests/test_e2e_chat_guard.py`, `frontend/e2e/chat-piatto.spec.ts`
- Modify: `frontend/e2e/style.spec.ts` (due prove **in fondo al file**)

Lo stack e2e non ha il token (`.env.example`): la chat vera risponde 503, ed è proprio §9. Lo stato con le modifiche e l'evidenza non si raggiunge senza Claude: lo semina `backend/tests/e2e_chat.py`, sul modello di `backend/tests/e2e_spese.py` (stessa guardia `SPENA_E2E=1`, stesso lancio da Playwright con `execFileSync` e `COMPOSE_E2E`, come fa `frontend/e2e/spese.spec.ts`). Lo script scrive passando dai servizi veri (`create_meal`, `write_meal_recipe`, i messaggi con il repository del Task 6), non con SQL crudo, così lo stato seminato è uno stato che il codice sa produrre.

- [ ] **Step 1: Lo script e la sua guardia.** `e2e_chat.py seed|clean`. `seed` crea, su posti lontani da quelli delle altre prove (la cena fra 20 giorni e il pranzo fra 21, nel giorno di Roma), due pasti col piatto che comincia per «e2e-chat».
  - **A**: «e2e-chat Frittata di spinaci», con la ricetta scritta da `write_meal_recipe` (uova «2», spinaci «200 g», parmigiano «30 g», ingredienti del seme). Poi la conversazione: un messaggio di Mattia `sent` («Ho gli spinaci congelati nella busta da 1 kg: quanti ne prendo?»), una seconda `write_meal_recipe` legata a quel giro (spinaci «150 g», nota «congelati, senza scongelare», `summary` «spinaci congelati, padella unica») e la risposta di Claude `sent`.
  - **B**: «e2e-chat Pasta al pesto», con un messaggio di Mattia `failed` e l'avviso del limite del piano.

  `seed` stampa il JSON `{"meal_change": "<id A>", "meal_failed": "<id B>"}`; `clean` toglie i pasti «e2e-chat» (le chat se ne vanno in cascata) e le loro ricette. `test_e2e_chat_guard.py` ricalca `test_e2e_spese_guard.py`: senza `SPENA_E2E` lo script si rifiuta di partire.
- [ ] **Step 2: Le prove funzionali**, `frontend/e2e/chat-piatto.spec.ts` (375×812, accesso come nelle altre prove):
  1. **«senza token la chat lo dice, e il messaggio resta»**: con `page.request` si crea un pasto ufficiale (la cena di dopodomani) e la sua ricetta (`POST /api/v1/recipes` con `meal_id`). Su `/pasti/<id>` c'è «Chat con Claude» e già l'`Alert` «Claude non è collegato: manca il token del piano sul server.». Scritto «quanti spinaci?» e premuto «Invia», l'avviso resta, il campo contiene ancora «quanti spinaci?», «Modifica» della ricetta c'è e porta a `/ricette/<id>/modifica?pasto=<id>`, e `GET …/chat` non ha messaggi. Nel `finally`, `DELETE` del pasto.
  2. **«la modifica di Claude si vede, si evidenzia e si annulla»**: `seed`. Su `/pasti/<A>` si leggono «Ricetta aggiornata: spinaci congelati, padella unica» e «Annulla», la riga degli spinaci ha `data-changed` e dice «150 g». Dopo «Annulla» si leggono «Modifica annullata.» e «… — annullata», la riga degli spinaci dice «200 g» e nessuna riga ha più `data-changed`. Nel `finally`, `clean`.
  3. **«un messaggio senza risposta offre Riprova»**: su `/pasti/<B>` si leggono l'avviso del limite del piano e «Riprova».
- [ ] **Step 3: Le prove di stile, in fondo a `style.spec.ts`.**
  1. **«la chat del piatto a 375 px, con la modifica evidenziata, nei due temi»**: `seed`. Su `/pasti/<A>`, per `"light"` e `"dark"`: `fermo`, `testiIlleggibili(page)` è `[]`, `scrollWidth <= clientWidth`, «Annulla» visibile e alto almeno 44 px, e la riga con `data-changed` ha un `background-color` diverso da quello di una riga senza.
  2. **«la chat con l'avviso e il campo, nei due temi»**: su `/pasti/<B>`, nei due temi, `testiIlleggibili` vuoto, niente che scorre di lato, «Riprova» e «Invia» alti almeno 44 px. Nel `finally`, `clean`.
- [ ] **Step 4: Typecheck e lint**, `npm run typecheck && npm run lint`. Expected: puliti.
- [ ] **Step 5: L'e2e intera** su uno stack ricreato da zero, con i comandi delle Global Constraints. **Prima di lanciare Playwright**, dentro lo stack:
  ```bash
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.check_claude
  ```
  Expected: `claude-agent-sdk 0.2.180`, il binario che stampa `2.1.321 (Claude Code)` e `token: assente`. È la prova che l'**immagine** contiene l'SDK e un binario che parte sulla sua libc (spec §3). Se il binario non parte nell'immagine, fermati: `bloccato` con l'output. Poi Playwright: tutto verde, le prove nuove comprese. **Annota** `N_e2e`. Poi `down -v` e `rm .env`, sempre. Un testo illeggibile si corregge con un altro token esistente, mai con un token nuovo; se nessuno basta, `bloccato` con la misura.
- [ ] **Step 6: Commit** — `pasti: nel browser vero — la chat senza token, la modifica evidenziata e annullata, il contrasto nei due temi a 375 px; l'SDK prova di partire nell'immagine`.

---

### Task 12: I documenti, la verifica finale e il report

**Files:**
- Modify: `CLAUDE.md`, `README.md`, `docs/prossimi-passi.md`, `next-steps.md`
- Create o modify: `docs/night-reports/<data di oggi>.md`

- [ ] **Step 1: `CLAUDE.md`.** In «Stack and layout», dopo il paragrafo sugli utensili aggiunto dal piano 1 (quello che finisce con «§4.4 and §8.»), aggiungi:
  ```
  **A second path to a model, on purpose: Claude for the meals.** The meal chat (and,
  next, the planning) runs on Claude Opus (`claude-opus-5-5`) through the Claude Agent
  SDK for Python (`claude-agent-sdk`, pinned, with its bundled Claude Code binary),
  authenticated with Mattia's own subscription through `CLAUDE_CODE_OAUTH_TOKEN` from
  `claude setup-token`, kept only in the server's `.env` (decided by Mattia on
  2026-11-10; check the authentication terms in the spec's plan before changing it).
  This is not what the one-provider rule above forbids: that rule is against two
  implementations behind a switch, one of which never runs. Here there are two paths
  with two jobs, and both run in production — Gemma via OpenRouter for import, drafts
  and variants; Claude via the Agent SDK for the meals. The SDK is driven with every
  built-in tool off (`tools=[]`), no settings or `CLAUDE.md` loaded
  (`setting_sources=[]`), `permission_mode="dontAsk"`, and spena's own tools as an
  in-process MCP server (`backend/app/services/claude/`). Its calls go into `llm_calls`
  as `meal_chat` with their tokens and `cost_usd` NULL: they are on the plan, not paid
  per use, and «Spese dell'AI» shows them apart. Claude writes a meal's recipe only
  through `write_meal_recipe` (`backend/app/services/meal_recipes.py`), which goes
  through the `write_recipe_ingredients` funnel, inside a savepoint, and stores the
  version before for «Annulla». Tests never run the SDK: `get_claude_client` is
  injected, the fake calls the very tool objects production builds, and the production
  client is tested against the SDK's real message types. Spec:
  `docs/superpowers/specs/2026-11-12-pasti-claude-design.md` §3, §6, §7, §9.
  ```
  E nel paragrafo dell'LLM, la frase «There is one provider and one client on purpose» riceve in coda « — for the jobs Gemma does; the meals are the exception explained below».
- [ ] **Step 2: `README.md`.** Nella tabella o nell'elenco delle variabili dell'`.env` (cerca `OPENROUTER_API_KEY`): `CLAUDE_CODE_OAUTH_TOKEN`, `CLAUDE_MODEL` e `CLAUDE_REPLY_TIMEOUT_SECONDS`, una riga ciascuna nello stile del file. In più, una riga sul controllo `docker compose -f docker-compose.prod.yml exec backend python -m app.cli.check_claude [--prova]`.
- [ ] **Step 3: `docs/prossimi-passi.md`.** Nella nota «Sostituita il 2026-11-12» che il piano 2 ha messo sotto il titolo della Parte IV, aggiungi in coda: «Il secondo pezzo — Claude e la chat del piatto — è sul ramo `night/pasti-claude` (<data di oggi>, da revisionare).»
- [ ] **Step 4: `next-steps.md`.**
  1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte: sezione Pasti, piano 3 di 4)_`.
  2. La voce «Sezione Pasti» **resta aperta**, `in corso`. In coda alla riga, il pezzo « · piano 3 di 4 … in corso su night/pasti-claude» della Preparazione diventa « · piano 3 di 4 (Claude e la chat del piatto) fatto il <data di oggi> → branch night/pasti-claude (da revisionare); il prossimo è il piano 4, night/pasti-pianificazione». Se un task è rimasto `bloccato`, la voce passa a `bloccato` con «attende: …».
  3. In cima a «Fatti (recenti)»:
     ```markdown
     - [fatto] <data di oggi> · Sezione Pasti, piano 3 di 4: la chat con Claude sotto la ricetta di ogni pasto (Opus via Agent SDK sul piano di Mattia, token da `claude setup-token`), con dispensa, lista, pasti, utensili e anagrafica in lettura; Claude riscrive la ricetta (o la scrive da zero) passando dall'imbuto, con «Ricetta aggiornata: …», «Annulla» e le righe evidenziate; avvisi quando Claude non c'è; le chiamate nelle spese «sul piano di Claude, non a consumo» [Parte IV] → branch night/pasti-claude (da revisionare)
     ```
  4. Fra «Da fare a mano (solo Mattia)», nello stile della sezione: «Prima del deploy dei Pasti con Claude: confermare l'uso del token del piano con l'Agent SDK (vedi l'avvertenza in testa a `docs/superpowers/plans/2026-11-12-pasti-claude.md`), poi `claude setup-token` e il token nel `.env` del server».
  5. Quel che è emerso nella notte fuori da questo piano va come `idea` o `tbd`, con `[Parte IV]`.
- [ ] **Step 5: La verifica finale.** Da `<worktree>/frontend`: `npx vitest run`, `npm run typecheck`, `npx tsc -b --force`, `npm run lint`, `npm run build`. Expected: verdi; vitest circa **`N_vitest` + 35** in `N_file` + 4 file. Da `<worktree>/backend`, il comando di pytest: verde, circa **`N_pytest` + 115**. Se i numeri differiscono, scrivi nel report da dove viene la differenza. Poi i «Comandi di verifica» con i loro attesi, e l'e2e intera su uno stack ricreato da zero (`N_e2e`), con `check_claude` dentro lo stack, `down -v` e `rm .env`. Infine `docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_pasti_claude WITH (FORCE)'`.
- [ ] **Step 6: Il report**, in `docs/night-reports/<data di oggi>.md` sul ramo (in fondo, se il file c'è già). Dentro vanno:
  - **in testa, l'avvertenza sui termini d'uso del token** di questo piano, con le citazioni;
  - il ramo e da dove parte (`night/pasti-settimana` a `BASE`), la revisione `0020` letta, la versione dell'SDK installata nel `.venv` condiviso;
  - i conti veri contro la Preparazione, e l'output di `check_claude` nello stack e2e (la dimensione dell'immagine cresce di circa 340 MB per il binario: misurala con `docker image ls` e scrivila);
  - le **interfacce prodotte** così come sono finite nel codice (una firma diversa dal piano va scritta per prima: il piano 4 la usa);
  - i nomi dell'SDK che differivano dalla documentazione;
  - le decisioni 9–22 che Mattia può voler rivedere, in particolare: la cronologia ricostruita da spena, il giro staccato dalla richiesta, i 240 s, gli utensili nel prompt invece che in uno strumento, «Annulla» solo sull'ultima modifica, le spese a parte;
  - i posti lasciati al piano 4 (`dish_tools`, `DISH_PANTRY_RULE`, `ChatThread`, il tipo `planning`, `write_meal_recipe`);
  - la sezione «Dopo il deploy (solo Mattia)» qui sotto.

  Niente push, niente merge, niente deploy.
  ```bash
  git add CLAUDE.md README.md docs/prossimi-passi.md next-steps.md docs/night-reports/
  git commit -m "docs: Claude e la chat del piatto fatti sul ramo (piano 3 di 4); il secondo percorso verso un modello in CLAUDE.md"
  ```

---

## Dopo il deploy (solo Mattia)

La notte non tocca la produzione. Questo ramo si unisce dopo `night/utensili` e `night/pasti-settimana`, e prima di `night/pasti-pianificazione`.

0. **Prima di tutto, la decisione sui termini d'uso** (avvertenza in testa a questo piano). Se resta il token del piano, si va avanti. Se si passa a una chiave API, il codice da cambiare è poco: il controllo `claude_configured` e la variabile passata in `env`. La CLI preferisce già `ANTHROPIC_API_KEY` a `CLAUDE_CODE_OAUTH_TOKEN`. Va però cambiata anche la spec (§3), e si fa di giorno.
1. **Il token**, sul proprio computer: `claude setup-token`. Si approva nel browser e si copia il token che il terminale stampa (dura un anno: segnati la scadenza). Poi va nel `.env` **del server**, e mai nel repository: `CLAUDE_CODE_OAUTH_TOKEN=<token>`.
2. **Il deploy di sempre, con il `-f`**: `docker compose -f docker-compose.prod.yml up -d --build --wait --wait-timeout 120`. La `0021` gira all'avvio. L'immagine del backend cresce di circa 340 MB per il binario di Claude Code.
3. **Il controllo**: `docker compose -f docker-compose.prod.yml exec backend python -m app.cli.check_claude --prova`. Expected: il binario con la sua versione, `token: presente`, `prova: ok`. Se dice il limite del piano o il token, l'avviso dice cosa fare.
4. **Sul telefono, il caso della spec §1**: si scrive a mano una cena «Frittata di spinaci e parmigiano» con accompagnamenti «piadina · banana». Nella chat si chiede: «Scrivi la ricetta». Arriva «Ricetta scritta: …» e la ricetta compare sopra, con 1 porzione. Poi: «ho gli spinaci congelati nella busta da 1 kg, quanti ne prendo? Posso metterli in padella da congelati e poi versare le uova, senza tritarli?». La risposta arriva un po' alla volta, e la ricetta passa a spinaci congelati in padella unica, senza strizzatura, con le righe cambiate evidenziate e «Ricetta aggiornata: …». «Annulla» rimette la versione di prima, e il messaggio dopo toglie l'evidenza.
5. **Le spese dell'AI**: nel blocco «Claude» ci sono «Chat dei piatti» con chiamate e token e «sul piano di Claude, non a consumo», e il totale in dollari non cambia.
6. **Senza Claude**: togliendo per un momento il token (o col limite del piano raggiunto), la chat lo dice, mentre la ricetta, «Modifica» e la settimana funzionano.
