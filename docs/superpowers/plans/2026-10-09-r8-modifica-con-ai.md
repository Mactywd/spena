# R8 — Modifica con AI, che salva una ricetta nuova: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** dentro una ricetta aperta, «Modifica con AI» chiede con un prompt libero una variante; la proposta dell'AI apre il modulo della ricetta già compilato, e «Salva la variante» crea una ricetta **nuova** col legame all'originale («Variante di «…»» sotto il titolo), senza toccare l'originale. Se l'AI non risponde si resta sull'originale con un avviso ambra.

**Architecture:** una colonna `recipes.derived_from_id` (FK annullabile verso `recipes`, `ON DELETE SET NULL`, migrazione `0014`). `POST /recipes` la accetta, copia nella variante la foto e i tempi dell'originale (`variant_copy`), e `RecipeOut.derived_from` la restituisce (titolo di oggi e se è eliminata). La proposta è una rotta nuova, `POST /recipes/{id}/ai-variant`, sopra `draft_variant` in `services/ai_recipes.py`: lo stesso schema e la stessa lavorazione delle righe della bozza da zero (`_draft_from`, estratto da `draft_recipe`), con un prompt di sistema che estende quello della bozza, e la spesa in `llm_calls` con la sezione nuova `LlmCallSite.RECIPE_VARIANT`. L'annullamento di una decisione dell'import, che cancella e rifà l'originale, tiene gli id delle varianti nel `payload` della pagina come fa con le cotture. Nel frontend: il pannello `VariantPrompt` nel dettaglio dell'originale, lo schermo `RecipeVariantScreen` (`/ricette/:id/variante`, la proposta arriva nella cronologia) col `RecipeForm` di sempre, il collegamento `OriginLink` sotto il titolo della variante, e il dettaglio che riparte da capo quando cambia `:id`.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, pytest su Postgres vero; OpenRouter tramite `services/llm.py` (`complete_json`), provato con i finti di `backend/tests/llm_fakes.py`; React 19, TypeScript, Tailwind 4 (token in `@theme`), TanStack Query 5, react-router 7, Vitest + Testing Library (jsdom), Playwright.

**Spec:** `docs/superpowers/specs/2026-10-09-r8-modifica-con-ai-design.md` (tutta: le decisioni del §2 sono di Mattia, 2026-10-09 e 2026-10-13; le scelte segnate «(Claude)» sono delegate), e la voce **R8** di `docs/prossimi-passi.md`.

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/r8-modifica-con-ai` (`.worktrees/` è già in `.gitignore`), ramo `night/r8-modifica-con-ai`, creato da **`night/rimetti-in-lista`** (il ramo del piano 7 della catena, che parte da `night/s15-reparti-collassabili` ← `night/s14-cibo-casa` ← `night/tema-scuro-spenti` ← `night/s12-righe-dispensa` ← `night/s3-ingresso-diretto` ← `master`). Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì (o dalle sue `backend/` e `frontend/`), mai dalla radice del checkout principale. Il checkout principale non si tocca: se vi trovi modifiche non committate, sono dell'utente. **Nessun push, nessun merge, nessun deploy. Mai `git stash`.** Niente letture né scritture sulla produzione.
- **I file che anche i piani prima di questo toccano** — `frontend/src/features/cooking/RecipeDetailScreen.tsx` (il piano 7 «rimetti in lista» tocca il foglio della cottura, che ci vive dentro), `frontend/src/App.tsx` (S3), `frontend/src/domain/types.ts` (S12, S14, S15), `backend/app/services/llm.py` (S12 aggiunge `LlmCallSite.INGREDIENT_EMOJI`), `frontend/src/features/ai-draft/AiDraftScreen.tsx`, i test con una `RecipeDetail` scritta a mano, `frontend/e2e/style.spec.ts` (tutti), `docs/prossimi-passi.md`, `next-steps.md` — **leggili com'è sul ramo prima di cambiarli**. Il piano descrive ogni modifica contro un'ancora riconoscibile — una funzione, un elemento JSX, un testo esatto — e mai contro numeri di riga. Si aggiunge accanto a quel che gli altri hanno aggiunto, senza toccarlo. Dove il piano dà un file intero, è un file nuovo.
- **Una ricetta non nomina un non alimentare** (`CLAUDE.md`, decisione 2). Le righe della variante passano da `POST /recipes`, cioè da `_resolve_lines` e dall'imbuto `write_recipe_ingredients`: nessuna strada nuova per scrivere righe di ricetta. La proposta dell'AI non aggancia un non alimentare e non propone un reparto non alimentare (`_draft_from`, com'è oggi per la bozza).
- **L'LLM è uno, e ogni chiamata registra la spesa.** `complete_json` di `services/llm.py`, il modello della configurazione (`google/gemma-4-26b-a4b-it`); la sezione nuova è `LlmCallSite.RECIPE_VARIANT = "recipe_variant"` (la colonna `llm_calls.call_site` è `String(40)`: nessuna migrazione per lei). `tests/test_llm_spend_is_recorded.py` deve restare verde. **Nessuna chiamata di rete nella suite**: i test del servizio usano `FakeLlm` di `tests/llm_fakes.py`; i test delle rotte sostituiscono il servizio.
- **Il frontend non calcola logica di dominio.** Se una ricetta è una variante, di chi, e se l'originale è eliminata, lo dice il server (`RecipeOut.derived_from`). Il client non cerca l'originale da sé.
- **`Button` e la regola dei pulsanti.** I pulsanti nuovi sono `Button` (`frontend/src/components/ui/Button.tsx`): in volo → `busy`; «non ancora» → `unavailableReason` col perché; `disabled` nativo mai, qui. Nessun `<button>` scritto a mano. Il tasto di sola icona ha `label`.
- Tutto il colore passa dai token di `frontend/src/index.css`. Nessuna schermata nomina un colore crudo: `grep -rn "emerald\|neutral-" frontend/src` resta vuoto. Il guasto dell'AI è `Alert tone="degraded"` (l'ambra di `low`), come la bozza e la coda. Ogni testo sta sopra 4,5:1, in chiaro e in scuro, e lo misura `frontend/e2e/style.spec.ts`. **Nessun token nuovo.** Le icone si importano solo da `frontend/src/components/ui/icons.ts` (`IconSparkles` c'è già).
- Ogni bersaglio nuovo è almeno 44×44 px. A 375 px nessuna schermata scorre di lato.
- **Mai un vicolo cieco.** L'AI che non risponde lascia l'originale com'era, col testo scritto nel pannello; un'originale sparita al salvataggio non ferma la variante; `/variante` senza proposta porta all'originale.
- Le parole a video sono in italiano e **si copiano esattamente come sono scritte qui** (sono quelle del §4 della spec); gli identificatori in inglese; i commenti in italiano come nel resto del codice, e dicono il perché.
- **Il type check è `npm run typecheck`** (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0 (settima lezione di `CLAUDE.md`).
- Controlli del frontend, da `<worktree>/frontend`: `npx vitest run` (non esiste `npm test`), `npm run typecheck`, `npm run lint`, `npm run build`.
- **Backend su Postgres vero, in un database suo.** Il server dei test è il container `spena-db-1` (porta 5433): se `docker ps --format '{{.Names}}'` non lo mostra, `docker start spena-db-1`. **Mai `docker compose up` dal worktree** (il nome del progetto Compose viene dalla cartella: nascerebbe un secondo Postgres che litiga sulla 5433), mai `-f docker-compose.prod.yml`. Nel worktree non c'è un `.venv`: si usa quello del checkout principale; `python -m` mette la cartella corrente in testa a `sys.path`, quindi si prova l'`app` del worktree. Il comando, sempre da `<worktree>/backend` (dove un task dice «il comando di pytest» intende questo, con i percorsi di test che il task indica in coda):
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_r8 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
  Se un test sembra ignorare una modifica, `python -c 'import app; print(app.__file__)'` da `<worktree>/backend` (con lo stesso `PATH`) deve stampare un percorso dentro il worktree.
- **Il database dei test è `spena_test_r8`, non `spena_test`.** Questo ramo eredita la `0013` di S12 e aggiunge la `0014`; la suite fa `alembic upgrade head` sul suo database all'avvio, e girata su `spena_test` lo lascerebbe alla `0014`, rompendo `alembic upgrade head` ai piani che partono da `master` (R2, pagine scartate, H1: «Can't locate revision identified by '0014'»). Il database si crea nella Preparazione e si toglie alla fine della verifica finale:
  ```bash
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_r8 WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_r8'
  # … i task …
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_r8 WITH (FORCE)'
  ```
- **e2e** sullo stack `spena-e2e`, dalla radice di `<worktree>`. Serve un `.env`: **si copia da `.env.example`, che non ha segreti, solo per la prova, e si cancella alla fine. Mai leggere né copiare il `.env` del checkout principale.** `.env.example` ha `OPENROUTER_API_KEY` vuota: sullo stack e2e l'AI risponde 503 da sé, prima della rete (`build_headers`), ed è il guasto che le prove usano; la proposta riuscita la costruiscono le prove con `page.route`. Prima di alzarlo, `docker ps --format '{{.Names}}' | grep spena-e2e`: se c'è e non l'hai alzato tu (un altro piano della notte), non fare `down`, aspetta che sparisca.
  ```bash
  cp .env.example .env
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed --con-ricette
  (cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
  rm .env
  ```
  Il `-p spena-e2e` e il `-f docker-compose.e2e.yml` vanno in ogni comando: un `down -v` sul progetto di default cancellerebbe la dispensa vera. Il backend migra da sé alla `0014` all'avvio. Una prova fallita lascia dati nello stack: prima di rieseguire, `down -v`, poi `up`, seme e prova.
- **Nessuna dipendenza nuova.** Una sola migrazione, la `0014` (chiesta da Mattia: «il legame vuole una colonna»). Nessun cambio di configurazione globale.

### Preparazione (una volta, prima del Task 1)

- [ ] Il database dei test di questo ramo (prima di qualunque pytest):
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_r8 WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_r8'
  ```
- [ ] Il ramo di partenza c'è, e porta la `0013` e nessuna `0014`:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify night/rimetti-in-lista
  git log --oneline master..night/rimetti-in-lista | tail -n 8
  git ls-tree --name-only night/rimetti-in-lista backend/alembic/versions/ | grep -E '/00(13|14)'
  git show night/rimetti-in-lista:backend/alembic/versions/0013_figura_ingrediente.py | grep -E '^(revision|down_revision)'
  ```
  Expected: un hash; i commit di S3, S12, tema scuro, S14, S15 e «rimetti in lista»; una sola riga, `backend/alembic/versions/0013_figura_ingrediente.py`; `revision = "0013"` e `down_revision = "0012"`.
  - Se `night/rimetti-in-lista` non c'è, **fermati**: la catena della notte si è interrotta prima di questo piano, e nessun task parte. Il checkout principale non si tocca: la causa va nel report della notte (`docs/night-reports/<data>.md`), sull'ultimo ramo della catena che esiste, con la riga di R8 segnata `bloccato` in `next-steps.md` di quel ramo («attende: il ramo `night/rimetti-in-lista`»), e la domanda per Mattia.
  - Se la `0013` non c'è o ha un altro nome di revisione, fermati allo stesso modo: la `down_revision` di questo piano è sbagliata.
  - Se c'è già una `0014` (un piano non previsto), la tua prende il numero dopo, con `down_revision` sull'ultima: adatta nome del file, `revision`, `down_revision`, il test del Task 1 (nome, `upgrade`/`downgrade`), e scrivilo nel report.
- [ ] Dal checkout principale, allinea `node_modules` al lockfile (non aggiunge dipendenze, installa quelle di `package-lock.json`):
  ```bash
  cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund
  ```
- [ ] Crea il worktree e collega `node_modules` (e solo quello: **niente `.env`**):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/r8-modifica-con-ai -b night/r8-modifica-con-ai night/rimetti-in-lista
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/r8-modifica-con-ai/frontend/node_modules
  ```
- [ ] Cosa hanno già cambiato i piani prima di questo nei file di questo piano:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/r8-modifica-con-ai
  git diff --stat master -- \
    backend/app/api/recipes.py backend/app/schemas/recipe.py backend/app/schemas/ai.py \
    backend/app/db/models/recipe.py backend/app/repositories/recipes.py \
    backend/app/services/ai_recipes.py backend/app/services/llm.py \
    backend/app/services/recipe_import/undo.py backend/app/services/recipe_import/materialize.py \
    frontend/src/App.tsx frontend/src/domain/types.ts frontend/src/features/recipes/api.ts \
    frontend/src/features/ai-draft/ frontend/src/features/cooking/RecipeDetailScreen.tsx \
    frontend/src/features/recipe-form/
  grep -n "class LlmCallSite" -A12 backend/app/services/llm.py
  ls frontend/src/features/ai-variant 2>/dev/null
  ```
  Expected: nel `diff --stat` ci sono di sicuro `llm.py` (S12, `INGREDIENT_EMOJI`), `App.tsx` (S3), `types.ts` (S12/S14/S15), e forse `RecipeDetailScreen.tsx` (piano 7): **annota quali**, e leggili prima di cambiarli. I file del backend delle ricette (`api/recipes.py`, `schemas/recipe.py`, `models/recipe.py`, `repositories/recipes.py`, `ai_recipes.py`, `undo.py`, `materialize.py`) dovrebbero essere come su `master`: se uno non lo è, applica le modifiche di questo piano sopra la versione del ramo, blocco per blocco, e scrivilo nel report. `LlmCallSite` non ha `RECIPE_VARIANT`; `features/ai-variant` non esiste.
- [ ] La riga di R8 in `next-steps.md` del ramo diventa `in corso`. Trovala con `grep -n "R8, modifica con AI" next-steps.md` (fra i «Pronti per la notte», o ancora fra le voci decise). Toglila da dove sta e mettila sotto `## In corso` (al posto di `_(niente)_`, se c'è; altrimenti in fondo alle righe già lì, che sono degli altri piani della notte):
  ```markdown
  - [in corso] P3 · R8, modifica con AI che salva una ricetta nuova, col legame «Variante di «…»» — piano `docs/superpowers/plans/2026-10-09-r8-modifica-con-ai.md` → branch night/r8-modifica-con-ai [R8]
  ```
  ```bash
  git add next-steps.md
  git commit -m "next-steps: R8 in corso, sul ramo night/r8-modifica-con-ai"
  ```
- [ ] La linea di partenza, dal worktree:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/r8-modifica-con-ai/frontend && npx vitest run 2>&1 | grep -E "Test Files|Tests "
  cd ../backend && TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_r8 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q 2>&1 | tail -n 1
  ```
  Expected: tutto verde. **Annota i numeri** (file e test di vitest, test di pytest): sono `N_file`, `N_vitest`, `N_pytest` del Task 10, e dipendono da quel che i piani prima di questo hanno aggiunto. Se una delle due linee non è verde, fermati: non è un difetto di questo piano, e va scritto nel report.

---

## Obiettivo e contesto

L'AI dell'app oggi scrive solo da zero: «Scrivi una ricetta» (`AiDraftScreen`) chiede un prompt e propone una bozza da correggere nel modulo. Chi ha davanti una ricetta che gli va quasi bene — la torta di mele, ma col dolcificante — ha due strade, tutte e due sbagliate: correggerla a mano cambiando l'originale, o riscriverla da capo. R8 è la terza: un prompt dentro la ricetta aperta, e l'AI riscrive la ricetta intera ribilanciando il resto, perché sostituire un ingrediente cambia le dosi, i liquidi, la cottura. Il salvataggio è una ricetta nuova, e l'originale resta intatta. Mattia ha deciso il 2026-10-09 che la nuova ricorda da dove nasce, e lo fa vedere.

Quasi tutto c'è già: il modulo con `applyDraft`, il client dell'LLM con la spesa, `POST /recipes` con l'imbuto delle righe. Manca il legame (una colonna), la domanda all'AI con la ricetta dentro (una rotta e un prompt), e i due pezzi di schermo — il pannello nel dettaglio, e il modulo della variante.

## Decisioni prese

Da Mattia, il 2026-10-09 (non si rimettono in discussione):

1. **La nuova ricetta tiene un legame con l'originale, e si vede**: nella nuova, sotto il titolo, «Variante di «<titolo>»» che porta all'originale. Nell'originale niente in più. Un'originale eliminata si mostra seguendo R10: si apre dalla lapide.
2. **La proposta dell'AI apre il modulo della ricetta già compilato**, come la bozza AI: si corregge, «Salva» crea la ricetta nuova col legame. **Se l'AI non risponde si resta sull'originale con un avviso** ambra (`tone="degraded"`).
3. **Il legame è una colonna**, `recipes.derived_from_id`, FK annullabile verso `recipes`; migrazione `0014` con `down_revision = "0013"`.
4. **Le righe passano dall'imbuto** `write_recipe_ingredients`: l'AI non può introdurre un non alimentare.
5. **Una ricetta nata così è dell'utente**: non è importata, niente pagina d'import.
6. **La chiamata si registra in `llm_calls`** con una sezione `LlmCallSite` nuova; i test usano i finti registrati, nessuna rete.

Scelte di questo piano (**decise da Claude su delega di Mattia**: dove sta il tasto, le parole, il prompt di sistema, e le scelte tecniche interne; reversibili):

7. **Il tasto** è un pulsante di sola icona, «Modifica con AI» con `IconSparkles`, nel gruppo «Azioni della ricetta» accanto al titolo, **fra «Modifica» ed «Elimina»**: le due azioni rare stanno già lì (T3 Consegna 5), è una modifica, e la scintilla è l'icona di «scrivi con l'AI» (spec T3 §3.3). Non c'è sulla lapide di una ricetta eliminata, come «Modifica».
8. **Il prompt sta in un pannello dentro il dettaglio dell'originale**, subito sotto il titolo (`VariantPrompt`), e non in uno schermo suo: è il modo letterale di «si resta sull'originale» quando l'AI non risponde — la ricetta è lì sotto, intera. Il pannello prende il fuoco; «Annulla» lo chiude e ridà il fuoco al tasto; una proposta arrivata dopo «Annulla» non apre niente.
9. **Il modulo della variante è uno schermo suo**, `/ricette/:id/variante` (`RecipeVariantScreen`, accanto a `/ricette/:id/modifica`), e la proposta ci arriva nello stato della cronologia (`navigate(…, { state })`): regge un ricaricamento, se ne va con la voce della cronologia, e non serve una cache. Senza proposta (un indirizzo scritto a mano) porta all'originale. Salvato, il dettaglio della variante **sostituisce** il modulo nella cronologia: indietro si torna all'originale.
10. **La categoria della variante parte da quella dell'originale** (la proposta non ne ha); il resto viene da `applyDraft`. `source = "ai"`, `source_ref = sourceRef(prompt)` («prompt: …», accorciato a 500 come la bozza: `sourceRef` si sposta da `AiDraftScreen.tsx` in `features/ai-draft/sourceRef.ts`).
11. **Il legame a video** è `OriginLink`: testo `brand`, `text-sm font-medium`, alto 44 px, come «Apri l'originale»; con l'originale eliminata dice «(eliminata)», come l'Anagrafica per le ricette eliminate, e porta lo stesso al dettaglio dell'originale, cioè alla lapide con «Ripristina».
12. **Il dettaglio riparte da capo quando cambia `:id`** (`key={id}` su un involucro di `RecipeDetailScreen`): da una variante all'originale la rotta è la stessa, e senza la chiave le porzioni scelte, il foglio della cottura o il pannello aperti passerebbero all'altra ricetta. Oggi nessun collegamento porta da una ricetta a un'altra: R8 è il primo.
13. **`ON DELETE SET NULL`**: cancellare l'originale non cancella la variante (`CASCADE` butterebbe il lavoro di chi l'ha scritta) e non è vietato (`RESTRICT` bloccherebbe l'annullamento di una decisione dell'import, l'unica strada che cancella davvero una ricetta, oltre al comando `drop_seed_recipes`). **Nessun indice** sulla colonna: si legge per chiave primaria dell'originale, e la ricerca delle varianti la fa solo l'annullamento, raro e a mano.
14. **L'import che rifà l'originale non perde il legame**: come le cotture (S9 §5.2), `undo_decision` scrive gli id delle varianti nel `payload` della pagina alla chiave `variant_recipe_ids` (`VARIANTS_KEY` in `materialize.py`), e `materialize_ready` li rimette sulla ricetta rifatta (solo su varianti ancora senza legame). Creare una variante **non** prende in carico la pagina dell'originale (`adopt_import_page`): l'originale resta com'era, anche per l'import.
15. **Un'originale sparita al salvataggio** (rifatta dall'import mentre si correggeva la variante): la variante si salva **senza legame**. È la regola «mai un vicolo cieco»: un rifiuto butterebbe il lavoro, e dal modulo il legame non si toglie. Un'originale eliminata tiene il legame.
16. **La rotta della proposta** risponde 404 a una ricetta che non c'è, **409 con la frase di R10** («Questa ricetta è stata eliminata: ripristinala prima di modificarla.») a una eliminata, 503 all'AI che non risponde («variante AI non disponibile: …»). Il pannello mostra la stessa frase ambra per ogni errore: per chi guarda è sempre «l'AI non ha risposto».
17. **Il prompt di sistema della variante** è quello della bozza (`SYSTEM_PROMPT`: lo schema, i ruoli, i nomi generici, il costo, niente nutrienti, i reparti) **più** le regole della variante (Task 3). La domanda è un JSON con `ricetta` — titolo, descrizione, procedimento, porzioni, costo e righe col **nome canonico** dell'anagrafica, ruolo, dose e reparto — e `richiesta`. Col nome canonico, `match_name` riaggancia con certezza le righe che la variante tiene. Tetto di **4000** token in uscita (`VARIANT_MAX_TOKENS`): la ricetta intera torna indietro, e un procedimento importato è lungo; la bozza da zero resta a 2000.
18. **La lavorazione delle righe è una sola** (`_draft_from`, estratta da `draft_recipe` senza cambiarla): una riga che `match_name` aggancia a un non alimentare torna non agganciata e senza reparto, un reparto proposto fuori dai dodici del cibo si scarta (`CATEGORIES` di `decide.py` è già solo cibo). Così una riga così nel modulo non parte salvando, e dice «non è un alimento» quando l'anagrafica la conosce con certezza come non alimentare (`non_food`, dalle pulizie delle parole), «non in anagrafica» altrimenti.

Da Mattia, il 2026-10-13 (era la sola domanda aperta di questo piano; deciso da Mattia il 2026-10-13):

19. **La variante parte con la foto e i tempi dell'originale** — «Sì, copiali». `image_url`, `prep_minutes` e `cook_minutes` della ricetta nuova sono quelli dell'originale.

Come, **deciso da Claude su delega di Mattia**:

20. **La copia la fa il server, in `POST /recipes`**, quando `derived_from_id` punta a un'originale che c'è (eliminata compresa): `variant_copy` legge i tre campi nella stessa transazione, e `create_recipe` li scrive. Non il modulo: `RecipeForm` non ha campi per la foto e per i tempi, né alla creazione né alla modifica (R10, spec del 2026-09-27 §7), e farglieli portare avanti e indietro senza mostrarli vorrebbe dire un client che maneggia valori che solo il server conosce. `RecipeCreate` non dichiara i tre campi: il client non li sceglie, e se li manda si ignorano. Senza originale (`derived_from_id` assente, o un'originale che non c'è più, decisione 15) restano vuoti come oggi. Copiati, sono della variante: `PUT` li lascia com'erano (R10), e cambiare o cancellare l'originale non li tocca. **Correggerli:** oggi nessuno schermo cambia la foto e i tempi di una ricetta, nemmeno la modifica (R10 §7); è una voce nuova, che il Task 9 annota come `idea` in `next-steps.md`. Lo schermo della variante non cambia parole: la foto si vede dopo il salvataggio, nel dettaglio e nel ricettario, come per ogni ricetta che ne ha una.

## Criteri di accettazione

- [ ] `recipes.derived_from_id` esiste (migrazione `0014`, UUID annullabile, FK verso `recipes.id` con `ON DELETE SET NULL`), sale, scende e risale; cancellare l'originale lascia la variante senza legame; modello e schema coincidono (`test_metadata_matches_migrations.py`).
- [ ] `POST /api/v1/recipes` con `derived_from_id` crea la ricetta col legame; `RecipeOut.derived_from` è `{id, title, archived}` dell'originale, o `null`; l'originale resta com'era (titolo, righe, nessun legame, nessuna pagina d'import per la variante); `PUT` su una variante tiene il legame; un'originale eliminata dà `archived: true`; un `derived_from_id` che non c'è salva la variante senza legame; una riga non alimentare è rifiutata con 422.
- [ ] La variante salvata ha `image_url`, `prep_minutes` e `cook_minutes` dell'originale, copiati dal server (deciso da Mattia il 2026-10-13); un `image_url` o un tempo mandati dal client si ignorano; una ricetta nuova senza `derived_from_id` li ha vuoti; `PUT` sulla variante li lascia com'erano; il modulo della variante non li manda.
- [ ] `POST /api/v1/recipes/{id}/ai-variant` (`{"prompt"}`, 3–1000 caratteri) risponde con una `DraftOut` e non salva niente; 404, 409 (frase di R10), 503, 401 senza sessione.
- [ ] `draft_variant` manda all'LLM `VARIANT_SYSTEM_PROMPT` (che comincia con `SYSTEM_PROMPT`), lo schema della bozza, `max_tokens` 4000 e la domanda JSON con la ricetta (nomi canonici) e la richiesta; riaggancia con certezza le righe tenute; non aggancia né propone un non alimentare; registra la spesa con `call_site = "recipe_variant"`, riuscita o fallita, committata.
- [ ] Annullare una decisione dell'import che rifà l'originale lascia gli id delle varianti in `payload["variant_recipe_ids"]`; rifatta la ricetta, le varianti ritrovano il legame e la chiave sparisce.
- [ ] Nel dettaglio di una ricetta non eliminata il gruppo «Azioni della ricetta» è «Modifica», «Modifica con AI», «Elimina»; il tasto apre e chiude il pannello (`aria-expanded`), il fuoco va nel campo «Cosa vuoi cambiare?»; con meno di tre lettere «Proponi la variante» dice «Scrivi cosa cambiare: bastano tre lettere.» e non parte; «Annulla» chiude e ridà il fuoco al tasto. Una ricetta eliminata non ha il tasto.
- [ ] L'AI che non risponde lascia lo schermo sull'originale, col testo nel campo e «L'AI non ha risposto: questa ricetta resta com'è. Riprova fra poco.» in ambra (`text-low`, nei due temi, e2e).
- [ ] La proposta apre «Nuova variante» con «Variante di «<titolo>»», «Hai chiesto: «…». Correggi quel che serve: salvando nasce una ricetta nuova, e l'originale resta com'è.», il modulo compilato e la categoria dell'originale; «Salva la variante» manda `source: "ai"`, `source_ref: "prompt: …"`, `derived_from_id`, nessuna `PUT`/`PATCH` all'originale, e apre il dettaglio nuovo con «Salvata.». `/variante` senza proposta porta all'originale; con la proposta nella cronologia il modulo riparte da lì.
- [ ] Nel dettaglio di una variante, sotto il titolo, «Variante di «<titolo>»» (o «… (eliminata)») porta all'originale (o alla sua lapide), alto almeno 44 px; l'originale non mostra niente in più; passando dall'una all'altra le porzioni non passano.
- [ ] A 375 px, nei due temi, il dettaglio col pannello, il modulo della variante e il dettaglio di una variante non scorrono di lato e ogni testo sta sopra 4,5:1 (e2e); il giro intero nel browser vero (e2e: guasto vero dello stack, proposta finta, salvataggio vero, legame, lapide).
- [ ] Tutti i test di oggi passano, migrati solo dove una `RecipeDetail` scritta a mano prende `derived_from: null` (Task 6), mai indeboliti.
- [ ] vitest, typecheck, lint, build, pytest e l'e2e intera verdi.
- [ ] `docs/prossimi-passi.md` e `next-steps.md` aggiornati (Task 9).

## Comandi di verifica

Da `<worktree>/frontend`:

```bash
npx vitest run
npm run typecheck
npm run lint
npm run build
```

Da `<worktree>/backend`:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_r8 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Dalla radice di `<worktree>`:

```bash
grep -rn "emerald\|neutral-" frontend/src
git diff --name-only night/rimetti-in-lista -- backend/alembic/versions/
grep -rn "RECIPE_VARIANT" backend/app
```

Expected: il primo `grep` non stampa niente; il secondo solo `backend/alembic/versions/0014_varianti_ricette.py`; il terzo la definizione in `llm.py` e i due usi in `ai_recipes.py`. E l'e2e intera con i comandi delle Global Constraints.

## Fuori scope

- Nell'originale, l'elenco o il segno delle sue varianti (deciso: niente in più).
- Il legame negli elenchi del ricettario, nei filtri, nella ricerca.
- Riproporre dal modulo della variante: si torna all'originale e si riapre il pannello.
- Correggere a mano la foto e i tempi, della variante come di ogni ricetta: il modulo non li ha (R10 §7), e la variante li copia dall'originale (decisioni 19 e 20). Il Task 9 lo annota come `idea`.
- La pagina delle spese dell'AI (H1, piano a sé da `master`): la sezione `recipe_variant` le arriva come le altre; il suo nome a video è di H1 (vedi Dipendenze).
- La formula «non in anagrafica» per una riga non alimentare della bozza (idea già in `next-steps.md`).
- Qualunque cambiamento a «Scrivi una ricetta» oltre allo spostamento di `sourceRef`.

## Margine di autonomia

- **Liberi:** i nomi di variabili locali, helper di test e funzioni interne non fissati qui; l'ordine dei test dentro un file; l'ordine delle classi Tailwind; la formulazione dei commenti, purché dicano il perché.
- **Fissi:** le parole a video, esattamente come sono scritte nel piano; il prompt di sistema della variante come scritto nel Task 3 (si può migliorare solo con una ragione scritta nel report); i nomi pubblici che altri task usano (`derived_from_id`, `derived_from`, `RecipeOriginOut`, `RecipeOrigin`, `recipe_origin`, `VariantCopy`, `variant_copy`, `LlmCallSite.RECIPE_VARIANT`, `VARIANT_SYSTEM_PROMPT`, `VARIANT_MAX_TOKENS`, `variant_question`, `draft_variant`, `VARIANTS_KEY`, `draftVariant`, `sourceRef`, `VariantState`, `readVariantState`, `variantPath`, `VARIANT_PANEL_ID`, `VariantPrompt`, `OriginLink`, `RecipeVariantScreen`); la rotta `POST /api/v1/recipes/{id}/ai-variant` e il percorso `/ricette/:id/variante`; i nomi accessibili di oggi.
- **Nessuna dipendenza nuova**, nessuna migrazione oltre la `0014`, nessun token di colore nuovo.
- **Un test di oggi si cambia solo** per dare `derived_from: null` a una `RecipeDetail` scritta a mano (Task 6), mai per indebolirlo. Se ne serve un'altra migrazione, scrivila nel report con il perché.
- **Una decisione non coperta e non reversibile** → si ferma quel task, si fa commit del lavoro parziale sul ramo, lo si segna `bloccato` in `next-steps.md` del ramo con la domanda precisa per Mattia, e si passa al task successivo. Una scelta reversibile e a basso impatto → la più conservativa, annotata nel report della notte.
- Se un test fallisce e non si risolve in modo ragionevole: niente test disattivati, niente asserzioni indebolite; `bloccato` con la diagnosi.

## Dipendenze

**Parte da `night/rimetti-in-lista`** (piano 7, `docs/superpowers/plans/2026-10-09-rimetti-in-lista.md`), in fondo alla catena S3 → S12 → tema scuro → S14 → S15 → rimetti in lista. Da loro questo piano consuma **solo** la migrazione `0013` di S12 (la `down_revision` della `0014`); parte da lì perché tocca file che anche loro toccano (`App.tsx`, `types.ts`, `llm.py`, `RecipeDetailScreen.tsx`, `style.spec.ts`, i documenti), e al merge non ci siano conflitti.

**Verso H1** (piano 11, da `master`): H1 mostra le spese per sezione. Su `master` le sezioni sono quattro; questo ramo aggiunge `recipe_variant` (e S12 `ingredient_emoji`). Se H1 dà un nome a video a ogni sezione con una tabella chiusa, al merge dei due rami la tabella va completata: lo si scrive nel report e in `next-steps.md` (Task 9).

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `backend/alembic/versions/0014_varianti_ricette.py` (nuovo), `backend/tests/db/test_migration_0014.py` (nuovo) | 1 | la migrazione e la sua prova |
| `backend/app/db/models/recipe.py` | 1 | `Recipe.derived_from_id` |
| `backend/app/repositories/recipes.py` | 2 | `RecipeOrigin`, `recipe_origin`, `VariantCopy`, `variant_copy`; `create_recipe(derived_from_id=…, image_url=…, prep_minutes=…, cook_minutes=…)` |
| `backend/app/schemas/recipe.py` | 2 | `RecipeCreate.derived_from_id`, `RecipeOriginOut`, `RecipeOut.derived_from` |
| `backend/app/api/recipes.py` | 2, 4 | `create` col legame e con la foto e i tempi dell'originale, `_to_out` con `derived_from`; la rotta `ai-variant`, `_draft_out` |
| `backend/tests/api/test_recipes_variant.py` (nuovo) | 2, 4 | sei test del legame (uno sulla foto e i tempi); cinque della rotta |
| `backend/app/services/llm.py` | 3 | `LlmCallSite.RECIPE_VARIANT` |
| `backend/app/services/ai_recipes.py` | 3 | `VARIANT_SYSTEM_PROMPT`, `VARIANT_MAX_TOKENS`, `variant_question`, `draft_variant`; `_ask`, `_draft_from` estratti |
| `backend/tests/services/test_ai_recipes.py` | 3 | cinque test |
| `backend/app/services/recipe_import/materialize.py`, `undo.py` | 5 | `VARIANTS_KEY`, `_relink_variants`; gli id delle varianti nel `payload` |
| `backend/tests/services/test_undo.py` | 5 | due test |
| `frontend/src/domain/types.ts` | 6 | `RecipeOrigin`, `RecipeDetail.derived_from` |
| `frontend/src/features/recipes/api.ts` | 6 | `createRecipe` con `derived_from_id`, `draftVariant` |
| `frontend/src/features/ai-draft/sourceRef.ts`, `sourceRef.test.ts` (nuovi), `AiDraftScreen.tsx` | 6 | `sourceRef` spostato |
| i test con una `RecipeDetail` scritta a mano (sei su `master`) | 6 | `derived_from: null` |
| `frontend/src/features/ai-variant/variantState.ts`, `variantState.test.ts` (nuovi) | 7 | lo stato della cronologia |
| `frontend/src/features/ai-variant/VariantPrompt.tsx`, `OriginLink.tsx`, `RecipeVariantScreen.tsx`, `RecipeVariant.test.tsx` (nuovi) | 7 | il pannello, il legame, il modulo; undici test |
| `frontend/src/features/cooking/RecipeDetailScreen.tsx` | 7 | il tasto, il pannello, il legame, `key={id}` |
| `frontend/src/App.tsx` | 7 | la rotta `/ricette/:id/variante` |
| `frontend/e2e/variante-ai.spec.ts` (nuovo), `frontend/e2e/style.spec.ts` | 8 | il giro intero; due prove di stile |
| `docs/prossimi-passi.md`, `next-steps.md` | 9 | i documenti |

---

### Task 1: La colonna `recipes.derived_from_id` e la migrazione `0014`

**Files:**
- Create: `backend/alembic/versions/0014_varianti_ricette.py`
- Create: `backend/tests/db/test_migration_0014.py`
- Modify: `backend/app/db/models/recipe.py` (la classe `Recipe`)

**Interfaces:**
- Produces: `Recipe.derived_from_id: Mapped[uuid.UUID | None]`, FK verso `recipes.id` con `ondelete="SET NULL"`, annullabile; la revisione Alembic `"0014"` con `down_revision = "0013"`. I Task 2 e 5 la leggono e la scrivono.

- [ ] **Step 1: Il test che fallisce**

Crea `backend/tests/db/test_migration_0014.py`:

```python
"""La migrazione 0014 sale e scende (R8): il legame di una variante con la sua originale.

Su un database suo, creato e distrutto qui, come `test_migration_0012.py`: far scendere
quello della suite toglierebbe la colonna sotto i piedi a ogni altro test. Alembic gira
in un sottoprocesso, perché il suo template async chiama `asyncio.run`, che dentro un
loop già in corsa esplode.
"""

import os
import subprocess
import uuid

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://spena:spena@localhost:5433/spena_test"
)
SERVER, _, TEST_DB = TEST_DATABASE_URL.rpartition("/")
SCRATCH_DB = f"{TEST_DB}_migrazione_0014"

COLONNA = (
    "SELECT is_nullable FROM information_schema.columns "
    "WHERE table_name = 'recipes' AND column_name = 'derived_from_id'"
)
REGOLA = (
    "SELECT rc.delete_rule FROM information_schema.referential_constraints rc "
    "JOIN information_schema.key_column_usage k ON k.constraint_name = rc.constraint_name "
    "WHERE k.table_name = 'recipes' AND k.column_name = 'derived_from_id'"
)
RICETTA = (
    "INSERT INTO recipes (id, title, instructions, source, derived_from_id) "
    "VALUES (:id, :titolo, 'Cuoci.', :fonte, :da)"
)


def alembic(url: str, *args: str) -> None:
    subprocess.run(["alembic", *args], check=True, env={**os.environ, "DATABASE_URL": url})


@pytest_asyncio.fixture
async def scratch_url():
    admin = create_async_engine(f"{SERVER}/postgres", isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)'))
        await conn.execute(text(f'CREATE DATABASE "{SCRATCH_DB}"'))
    try:
        yield f"{SERVER}/{SCRATCH_DB}"
    finally:
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)'))
        await admin.dispose()


async def _scalar(url: str, sql: str, **params):
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            return (await conn.execute(text(sql), params)).scalar()
    finally:
        await engine.dispose()


async def _esegui(url: str, sql: str, **params) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(sql), params)
    finally:
        await engine.dispose()


async def test_la_0014_sale_scende_e_risale(scratch_url):
    alembic(scratch_url, "upgrade", "0014")
    assert await _scalar(scratch_url, COLONNA) == "YES"
    assert await _scalar(scratch_url, REGOLA) == "SET NULL"

    originale, variante = uuid.uuid4(), uuid.uuid4()
    await _esegui(scratch_url, RICETTA, id=originale, titolo="Torta di mele", fonte="manual", da=None)
    await _esegui(
        scratch_url, RICETTA, id=variante, titolo="Torta di mele con dolcificante", fonte="ai",
        da=originale,
    )
    # cancellare l'originale non cancella la variante: perde soltanto il legame
    await _esegui(scratch_url, "DELETE FROM recipes WHERE id = :id", id=originale)
    restata = "SELECT count(*) FROM recipes WHERE id = :id"
    assert await _scalar(scratch_url, restata, id=variante) == 1
    legame = "SELECT derived_from_id FROM recipes WHERE id = :id"
    assert await _scalar(scratch_url, legame, id=variante) is None

    alembic(scratch_url, "downgrade", "0013")
    assert await _scalar(scratch_url, COLONNA) is None

    alembic(scratch_url, "upgrade", "head")
    assert await _scalar(scratch_url, COLONNA) == "YES"
```

- [ ] **Step 2: Fallisce**

Run (da `<worktree>/backend`): `TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_r8 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/db/test_migration_0014.py`
Expected: FAIL, Alembic esce con errore («Can't locate revision identified by '0014'»).

- [ ] **Step 3: La migrazione**

Crea `backend/alembic/versions/0014_varianti_ricette.py`:

```python
"""la variante di una ricetta ricorda da quale nasce (R8)

Revision ID: 0014
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014"
down_revision = "0013"


def upgrade() -> None:
    # Annullabile e senza passo dati: ogni ricetta di oggi non è una variante, e non lo
    # diventa. `SET NULL` e non `CASCADE`: cancellare l'originale — lo fa solo
    # l'annullamento di una decisione dell'import, che la rifà subito dopo, o
    # `drop_seed_recipes` — non deve buttare il lavoro di chi ha scritto la variante. E
    # non `RESTRICT`, che quell'annullamento lo bloccherebbe. Nessun indice: si legge per
    # chiave primaria dell'originale, e le varianti di una ricetta le cerca solo
    # l'annullamento, raro e a mano.
    op.add_column(
        "recipes", sa.Column("derived_from_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "recipes_derived_from_id_fkey", "recipes", "recipes",
        ["derived_from_id"], ["id"], ondelete="SET NULL",
    )


def downgrade() -> None:
    # Scendere perde i legami: le varianti restano, come ricette qualunque.
    op.drop_constraint("recipes_derived_from_id_fkey", "recipes", type_="foreignkey")
    op.drop_column("recipes", "derived_from_id")
```

- [ ] **Step 4: Il modello**

In `backend/app/db/models/recipe.py`, nella classe `Recipe`, subito dopo la riga

```python
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

aggiungi:

```python
    # La ricetta da cui questa nasce, per una variante scritta con l'AI (R8). `SET NULL`:
    # cancellare l'originale non cancella la variante (vedi la migrazione 0014), e se a
    # cancellarla è l'import che la rifà, il legame torna con `materialize_ready`
    # (`VARIANTS_KEY`). Nessuna relazione ORM: di lei si legge solo il titolo e se è
    # eliminata (`recipe_origin` in `app/repositories/recipes.py`).
    derived_from_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True
    )
```

(`uuid`, `UUID` e `ForeignKey` sono già importati nel file.)

- [ ] **Step 5: Passano, con la rete di sicurezza dell'autogenerate**

Run: il comando di pytest con `tests/db/`
Expected: PASS, compreso `test_metadata_matches_migrations.py` (modello e schema coincidono: nessuna operazione proposta) e il test nuovo. Se `test_models_describe_the_migrated_schema` propone un'operazione sulla chiave esterna, confronta nome e `ondelete` fra migrazione e modello: devono dire la stessa cosa.

- [ ] **Step 6: Commit**

```bash
git add backend/app/db/models/recipe.py backend/alembic/versions/0014_varianti_ricette.py backend/tests/db/test_migration_0014.py
git commit -m "feat(db): R8, la colonna recipes.derived_from_id (migrazione 0014), SET NULL e senza passo dati"
```

---

### Task 2: Il legame nel salvataggio e nella lettura

**Files:**
- Modify: `backend/app/repositories/recipes.py` (`create_recipe`; nuovi `RecipeOrigin`, `recipe_origin`, `VariantCopy`, `variant_copy`)
- Modify: `backend/app/schemas/recipe.py` (`RecipeCreate`, `RecipeOut`; nuovo `RecipeOriginOut`)
- Modify: `backend/app/api/recipes.py` (`create`, `_to_out`)
- Create: `backend/tests/api/test_recipes_variant.py`

**Interfaces:**
- Consumes: `Recipe.derived_from_id` (Task 1).
- Produces: in `app.repositories.recipes`: `@dataclass(frozen=True) class RecipeOrigin(id: uuid.UUID, title: str, archived: bool)`, `async def recipe_origin(session: AsyncSession, recipe: Recipe) -> RecipeOrigin | None`, `@dataclass(frozen=True) class VariantCopy(image_url: str | None = None, prep_minutes: int | None = None, cook_minutes: int | None = None)`, `async def variant_copy(session: AsyncSession, origin_id: uuid.UUID) -> VariantCopy | None` (`None`: l'originale non c'è più), `create_recipe(..., derived_from_id: uuid.UUID | None = None, image_url: str | None = None, prep_minutes: int | None = None, cook_minutes: int | None = None)`. In `app.schemas.recipe`: `RecipeCreate.derived_from_id: uuid.UUID | None = None`, `class RecipeOriginOut(id: uuid.UUID, title: str, archived: bool)`, `RecipeOut.derived_from: RecipeOriginOut | None = None`. Il Task 4 aggiunge test allo stesso file di test; il Task 6 legge `derived_from` nel frontend.

- [ ] **Step 1: I test che falliscono**

Crea `backend/tests/api/test_recipes_variant.py`:

```python
"""R8: la variante di una ricetta — il legame con l'originale, e la proposta dell'AI.

Il legame (`derived_from_id`) si prova per intero, sul database vero. La proposta
(`POST /recipes/{id}/ai-variant`, più sotto) si prova con il servizio sostituito: il
servizio vero, con i finti dell'LLM, lo prova `tests/services/test_ai_recipes.py`.
"""

import uuid

import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import Recipe, RecipeSource
from app.db.models.recipe_import import RecipeImport
from app.repositories.recipes import create_recipe

TITOLO_VARIANTE = "Pasta al pomodoro senza basilico"


@pytest_asyncio.fixture
async def cucina(db_session):
    def voce(name: str, category: str) -> Ingredient:
        return Ingredient(name=name, display_name=name.capitalize(), category=category)

    voci = {
        "pasta": voce("pasta", IngredientCategory.CEREALI),
        "pomodoro": voce("pomodoro", IngredientCategory.VERDURA),
        "basilico": voce("basilico", IngredientCategory.SPEZIE),
        "sapone": voce("sapone per le mani", IngredientCategory.IGIENE),
    }
    db_session.add_all(voci.values())
    await db_session.flush()
    return voci


@pytest_asyncio.fixture
async def originale(db_session, cucina):
    return await create_recipe(
        db_session, title="Pasta al pomodoro", description="Di sempre", instructions="Cuoci.",
        servings=2, source=RecipeSource.MANUAL, source_ref=None,
        ingredients=[
            (cucina["pasta"].id, "primary", "180 g", None),
            (cucina["pomodoro"].id, "primary", "300 g", None),
            (cucina["basilico"].id, "secondary", "q.b.", None),
        ],
        embedding=None,
    )


def corpo_variante(cucina, originale_id, **altro) -> dict:
    """Il corpo che il modulo della variante manda a `POST /recipes`."""
    return {
        "title": TITOLO_VARIANTE, "description": None, "instructions": "Cuoci. Condisci.",
        "servings": 2, "source": "ai", "source_ref": "prompt: senza basilico", "cost": 1,
        "derived_from_id": str(originale_id),
        "ingredients": [
            {"ingredient_id": str(cucina["pasta"].id), "role": "primary", "quantity_text": "180 g"},
            {"ingredient_id": str(cucina["pomodoro"].id), "role": "primary", "quantity_text": "350 g"},
        ],
        **altro,
    }


async def test_salvare_una_variante_tiene_il_legame_e_non_tocca_l_originale(
    logged_client, db_session, cucina, originale, dal_database
):
    risposta = await logged_client.post("/api/v1/recipes", json=corpo_variante(cucina, originale.id))

    assert risposta.status_code == 201
    variante = risposta.json()
    assert variante["derived_from"] == {
        "id": str(originale.id), "title": "Pasta al pomodoro", "archived": False,
    }
    assert variante["source"] == "ai"
    assert variante["owned_by_import"] is False
    riga = await dal_database(Recipe, uuid.UUID(variante["id"]))
    assert riga.derived_from_id == originale.id

    # l'originale è com'era: il suo titolo, le sue tre righe con le sue dosi, nessun legame
    letta = (await logged_client.get(f"/api/v1/recipes/{originale.id}")).json()
    assert letta["title"] == "Pasta al pomodoro"
    assert sorted((r["ingredient_name"], r["quantity_text"]) for r in letta["ingredients"]) == [
        ("basilico", "q.b."), ("pasta", "180 g"), ("pomodoro", "300 g"),
    ]
    assert letta["derived_from"] is None
    # e la variante non è importata: nessuna pagina d'import
    pagine = (
        await db_session.execute(
            select(RecipeImport).where(RecipeImport.recipe_id == uuid.UUID(variante["id"]))
        )
    ).scalars().all()
    assert pagine == []


async def test_un_originale_eliminata_resta_nel_legame_e_lo_dice(logged_client, cucina, originale):
    """R10: un'eliminata si apre dalla lapide, quindi il legame resta e dice com'è."""
    prima = (await logged_client.post("/api/v1/recipes", json=corpo_variante(cucina, originale.id))).json()
    eliminata = await logged_client.patch(f"/api/v1/recipes/{originale.id}", json={"archived": True})
    assert eliminata.status_code == 200

    letta = (await logged_client.get(f"/api/v1/recipes/{prima['id']}")).json()
    assert letta["derived_from"] == {
        "id": str(originale.id), "title": "Pasta al pomodoro", "archived": True,
    }
    # e una variante salvata quando l'originale è già eliminata tiene il legame anche lei
    dopo = await logged_client.post("/api/v1/recipes", json=corpo_variante(cucina, originale.id))
    assert dopo.status_code == 201
    assert dopo.json()["derived_from"]["archived"] is True


async def test_un_originale_che_non_c_e_piu_non_ferma_la_variante(logged_client, cucina, dal_database):
    """Mai un vicolo cieco: l'import può aver rifatto l'originale mentre si correggeva la
    variante. Rifiutarla butterebbe il lavoro, e dal modulo il legame non si toglie."""
    risposta = await logged_client.post("/api/v1/recipes", json=corpo_variante(cucina, uuid.uuid4()))

    assert risposta.status_code == 201
    assert risposta.json()["derived_from"] is None
    riga = await dal_database(Recipe, uuid.UUID(risposta.json()["id"]))
    assert riga.derived_from_id is None


async def test_modificare_una_variante_tiene_il_legame(logged_client, cucina, originale):
    variante = (await logged_client.post("/api/v1/recipes", json=corpo_variante(cucina, originale.id))).json()
    corpo = corpo_variante(cucina, originale.id, title="Pasta al pomodoro, la mia")
    for chiave in ("derived_from_id", "source", "source_ref"):
        corpo.pop(chiave)

    risposta = await logged_client.put(f"/api/v1/recipes/{variante['id']}", json=corpo)

    assert risposta.status_code == 200
    assert risposta.json()["title"] == "Pasta al pomodoro, la mia"
    assert risposta.json()["derived_from"]["id"] == str(originale.id)


async def test_la_variante_parte_con_la_foto_e_i_tempi_dell_originale(
    logged_client, db_session, cucina, originale
):
    """Deciso da Mattia il 2026-10-13: «Sì, copiali». Li copia il server, perché il modulo
    non li ha (R10 §7): il client non li sceglie, e una modifica della variante li lascia."""
    originale.image_url = "https://esempio.invalid/pasta.jpg"
    originale.prep_minutes = 10
    originale.cook_minutes = 15
    await db_session.flush()

    # mandati dal client si ignorano: `RecipeCreate` non li dichiara
    corpo = corpo_variante(
        cucina, originale.id, image_url="https://altrove.invalid/altra.jpg", prep_minutes=1
    )
    risposta = await logged_client.post("/api/v1/recipes", json=corpo)

    assert risposta.status_code == 201
    variante = risposta.json()
    assert (variante["image_url"], variante["prep_minutes"], variante["cook_minutes"]) == (
        "https://esempio.invalid/pasta.jpg", 10, 15,
    )

    # la modifica della variante (R10) non li manda, e non li cancella
    modifica = corpo_variante(cucina, originale.id, title="Pasta al pomodoro, la mia")
    for chiave in ("derived_from_id", "source", "source_ref"):
        modifica.pop(chiave)
    modificata = await logged_client.put(f"/api/v1/recipes/{variante['id']}", json=modifica)
    assert modificata.status_code == 200
    assert (
        modificata.json()["image_url"], modificata.json()["prep_minutes"],
        modificata.json()["cook_minutes"],
    ) == ("https://esempio.invalid/pasta.jpg", 10, 15)

    # una ricetta nuova che non è una variante non prende niente da nessuno
    libero = corpo_variante(cucina, originale.id, title="Pasta mia")
    libero.pop("derived_from_id")
    libera = (await logged_client.post("/api/v1/recipes", json=libero)).json()
    assert (libera["image_url"], libera["prep_minutes"], libera["cook_minutes"]) == (
        None, None, None,
    )


async def test_una_variante_non_puo_avere_un_non_alimentare(logged_client, db_session, cucina, originale):
    """L'imbuto `write_recipe_ingredients` vale anche per lei: è l'ultima linea, se una
    riga non alimentare arrivasse fin qui."""
    corpo = corpo_variante(cucina, originale.id)
    corpo["ingredients"].append(
        {"ingredient_id": str(cucina["sapone"].id), "role": "secondary", "quantity_text": "1"}
    )

    risposta = await logged_client.post("/api/v1/recipes", json=corpo)

    assert risposta.status_code == 422
    assert "non è un alimento" in risposta.json()["detail"]
    salvate = (
        await db_session.execute(select(Recipe.id).where(Recipe.title == TITOLO_VARIANTE))
    ).scalars().all()
    assert salvate == []
```

- [ ] **Step 2: Falliscono**

Run: il comando di pytest con `tests/api/test_recipes_variant.py`
Expected: FAIL — `derived_from` manca nelle risposte (`KeyError`), `riga.derived_from_id` resta `None` perché `RecipeCreate` ignora il campo, e la variante ha foto e tempi `None` invece di quelli dell'originale. `test_una_variante_non_puo_avere_un_non_alimentare` può già passare: è il contratto di oggi, e resta.

- [ ] **Step 3: Il repository**

In `backend/app/repositories/recipes.py`:

1. In testa, accanto a `import uuid`, aggiungi `from dataclasses import dataclass` (se non c'è già).
2. In `create_recipe`, aggiungi i parametri dopo `category: str | None = None,`:
   ```python
       derived_from_id: uuid.UUID | None = None,
       # R8: solo per una variante, copiati dall'originale (vedi `variant_copy`); una
       # ricetta scritta da zero non li ha, come oggi
       image_url: str | None = None,
       prep_minutes: int | None = None,
       cook_minutes: int | None = None,
   ```
   e passali al costruttore: la riga
   ```python
           category=category,
       )
   ```
   dentro `recipe = Recipe(...)` diventa
   ```python
           category=category, derived_from_id=derived_from_id,
           image_url=image_url, prep_minutes=prep_minutes, cook_minutes=cook_minutes,
       )
   ```
3. Subito dopo la funzione `get_recipe`, aggiungi:
   ```python
   @dataclass(frozen=True)
   class RecipeOrigin:
       """La ricetta da cui una variante nasce (R8), come la si mostra: il titolo di oggi, e
       se è eliminata — un'eliminata si apre dalla sua lapide (R10)."""

       id: uuid.UUID
       title: str
       archived: bool


   async def recipe_origin(session: AsyncSession, recipe: Recipe) -> RecipeOrigin | None:
       """L'originale di `recipe`, o `None` se non è una variante o l'originale non c'è più.

       Due colonne e non `session.get`: l'originale porterebbe con sé le sue righe
       (`selectin`), che qui non servono.
       """
       if recipe.derived_from_id is None:
           return None
       row = (
           await session.execute(
               select(Recipe.title, Recipe.archived_at).where(Recipe.id == recipe.derived_from_id)
           )
       ).one_or_none()
       if row is None:
           return None
       return RecipeOrigin(
           id=recipe.derived_from_id, title=row.title, archived=row.archived_at is not None
       )


   @dataclass(frozen=True)
   class VariantCopy:
       """Quel che una variante prende dalla sua originale al salvataggio (R8; deciso da
       Mattia il 2026-10-13: «Sì, copiali»). Vuoto per una ricetta che non è una variante."""

       image_url: str | None = None
       prep_minutes: int | None = None
       cook_minutes: int | None = None


   async def variant_copy(session: AsyncSession, origin_id: uuid.UUID) -> VariantCopy | None:
       """La foto e i tempi dell'originale `origin_id`, o `None` se non c'è più (eliminata
       c'è ancora).

       Li copia il server e non il modulo: `RecipeForm` non ha campi per la foto e per i
       tempi (R10 §7), e il client non deve maneggiare valori che non mostra. Tre colonne e
       non `session.get`, come `recipe_origin`: le righe dell'originale qui non servono.
       """
       row = (
           await session.execute(
               select(Recipe.image_url, Recipe.prep_minutes, Recipe.cook_minutes).where(
                   Recipe.id == origin_id
               )
           )
       ).one_or_none()
       if row is None:
           return None
       return VariantCopy(
           image_url=row.image_url, prep_minutes=row.prep_minutes, cook_minutes=row.cook_minutes
       )
   ```

- [ ] **Step 4: Gli schemi**

In `backend/app/schemas/recipe.py`:

1. In `class RecipeCreate(RecipeFields)`, dopo la riga `source_ref: str | None = Field(default=None, max_length=500)`, aggiungi:
   ```python
       # R8: la ricetta da cui questa nasce, per una variante scritta con l'AI. Solo alla
       # creazione: `RecipeReplace` non lo dichiara, quindi una modifica non lo cambia.
       derived_from_id: uuid.UUID | None = None
   ```
2. Subito prima di `class RecipeOut(BaseModel):`, aggiungi:
   ```python
   class RecipeOriginOut(BaseModel):
       """L'originale di una variante (R8): «Variante di «…»» sotto il titolo. `archived`
       vero: è eliminata, e il collegamento porta alla sua lapide (R10)."""

       id: uuid.UUID
       title: str
       archived: bool
   ```
3. In `class RecipeOut(BaseModel)`, dopo il campo `owned_by_import: bool = False`, aggiungi:
   ```python
       # R8: da quale ricetta nasce, se è una variante; il titolo è quello di oggi
       derived_from: RecipeOriginOut | None = None
   ```

- [ ] **Step 5: La rotta**

In `backend/app/api/recipes.py`:

1. Nell'import da `app.repositories.recipes` aggiungi `VariantCopy`, `recipe_origin` e `variant_copy`; nell'import da `app.schemas.recipe` aggiungi `RecipeOriginOut`.
2. In `_to_out`, prima del `return RecipeOut(`, aggiungi:
   ```python
       origin = await recipe_origin(session, recipe)
   ```
   e nella chiamata `RecipeOut(...)`, dopo `owned_by_import=await owned_by_import(session, recipe.id),`, aggiungi:
   ```python
           derived_from=(
               RecipeOriginOut(id=origin.id, title=origin.title, archived=origin.archived)
               if origin is not None
               else None
           ),
   ```
3. In `create`, subito dopo `embedding = await _embedding_for(payload.title, payload.description)`, aggiungi:
   ```python
       # R8: un'originale che nel frattempo non c'è più (l'import l'ha rifatta mentre si
       # correggeva la variante) non ferma il salvataggio: la variante nasce senza legame.
       # Rifiutarla butterebbe il lavoro, e dal modulo il legame non si toglie — sarebbe un
       # vicolo cieco. Un'originale eliminata c'è ancora, e tiene il legame.
       # E la variante parte con la foto e i tempi dell'originale (deciso da Mattia il
       # 2026-10-13: «Sì, copiali»): li copia qui il server, perché il modulo non li ha.
       derived_from_id, copied = None, VariantCopy()
       if payload.derived_from_id is not None:
           found = await variant_copy(session, payload.derived_from_id)
           if found is not None:
               derived_from_id, copied = payload.derived_from_id, found
   ```
   e nella chiamata `create_recipe(...)`, dopo `category=payload.category,`, aggiungi:
   ```python
               derived_from_id=derived_from_id,
               image_url=copied.image_url,
               prep_minutes=copied.prep_minutes,
               cook_minutes=copied.cook_minutes,
   ```

- [ ] **Step 6: Passano**

Run: il comando di pytest con `tests/api/test_recipes_variant.py tests/api/test_recipes.py tests/api/test_recipes_edit.py`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/repositories/recipes.py backend/app/schemas/recipe.py backend/app/api/recipes.py backend/tests/api/test_recipes_variant.py
git commit -m "feat(api): R8, una ricetta salvata come variante ricorda l'originale (derived_from) e ne copia foto e tempi"
```

---

### Task 3: Il servizio della variante, con la sua sezione delle spese

**Files:**
- Modify: `backend/app/services/llm.py` (`LlmCallSite`)
- Modify: `backend/app/services/ai_recipes.py`
- Modify: `backend/tests/services/test_ai_recipes.py`

**Interfaces:**
- Consumes: `get_recipe` (per i test), `Recipe` con le righe caricate.
- Produces: `LlmCallSite.RECIPE_VARIANT = "recipe_variant"`; in `app.services.ai_recipes`: `VARIANT_MAX_TOKENS = 4000`, `VARIANT_SYSTEM_PROMPT: str` (comincia con `SYSTEM_PROMPT`), `def variant_question(recipe: Recipe, prompt: str) -> str`, `async def draft_variant(session: AsyncSession, recipe: Recipe, prompt: str, client: object | None = None) -> RecipeDraft`. `draft_recipe` resta con la stessa firma e lo stesso comportamento. Il Task 4 chiama `draft_variant`.

- [ ] **Step 1: I test che falliscono**

In `backend/tests/services/test_ai_recipes.py`:

1. La riga `from app.services.ai_recipes import draft_recipe` diventa:
   ```python
   from app.services.ai_recipes import (
       DRAFT_SCHEMA,
       SYSTEM_PROMPT,
       VARIANT_MAX_TOKENS,
       VARIANT_SYSTEM_PROMPT,
       draft_recipe,
       draft_variant,
   )
   ```
2. In fondo al file aggiungi:
   ```python
   # ---- R8: la variante di una ricetta che esiste ----

   VARIANTE = {
       "title": "Pasta al pomodoro senza basilico",
       "description": "Di sempre, senza erbe",
       "instructions": "1. Cuoci la pasta.\n2. Scalda il sugo con un pizzico di zucchero.",
       "servings": 2,
       "cost": 1,
       "ingredients": [
           {"name": "pasta", "role": "primary", "quantity_text": "180 g", "category": "cereali"},
           {"name": "pomodoro", "role": "primary", "quantity_text": "350 g", "category": "verdura"},
           {"name": "zucchero", "role": "secondary", "quantity_text": "1 pizzico", "category": "dolci"},
       ],
   }


   @pytest_asyncio.fixture
   async def originale(db_session, anagrafica):
       from sqlalchemy import select

       from app.db.models.recipe import RecipeSource
       from app.repositories.recipes import create_recipe, get_recipe

       ids = {i.name: i.id for i in (await db_session.execute(select(Ingredient))).scalars()}
       ricetta = await create_recipe(
           db_session, title="Pasta al pomodoro", description="Di sempre",
           instructions="1. Cuoci la pasta.\n2. Scalda il sugo.", servings=2,
           source=RecipeSource.MANUAL, source_ref=None,
           ingredients=[
               (ids["pasta"], "primary", "180 g", None),
               (ids["pomodoro"], "primary", "300 g", None),
               (ids["basilico"], "secondary", "q.b.", None),
           ],
           embedding=None, cost=1,
       )
       return await get_recipe(db_session, ricetta.id)


   async def test_la_variante_manda_all_ai_la_ricetta_e_la_richiesta(db_session, originale):
       """La domanda è la ricetta com'è salvata, coi nomi canonici dell'anagrafica — così le
       righe che la variante tiene si riagganciano con certezza — e la richiesta."""
       import json

       finto = FakeLlm(VARIANTE)
       await draft_variant(db_session, originale, "senza basilico", client=finto)

       corpo = finto.bodies[0]
       assert corpo["messages"][0]["content"] == VARIANT_SYSTEM_PROMPT
       # le regole della bozza valgono anche qui: la variante le estende, non le riscrive
       assert VARIANT_SYSTEM_PROMPT.startswith(SYSTEM_PROMPT)
       assert corpo["max_tokens"] == VARIANT_MAX_TOKENS == 4000
       # lo schema è quello della bozza: il modulo legge la stessa forma
       assert corpo["response_format"]["json_schema"]["schema"] == DRAFT_SCHEMA
       domanda = json.loads(corpo["messages"][1]["content"])
       assert domanda["richiesta"] == "senza basilico"
       ricetta = domanda["ricetta"]
       assert ricetta["title"] == "Pasta al pomodoro"
       assert ricetta["description"] == "Di sempre"
       assert ricetta["instructions"] == "1. Cuoci la pasta.\n2. Scalda il sugo."
       assert ricetta["servings"] == 2
       assert ricetta["cost"] == 1
       assert sorted(
           (r["name"], r["role"], r["quantity_text"], r["category"]) for r in ricetta["ingredients"]
       ) == [
           ("basilico", "secondary", "q.b.", "spezie"),
           ("pasta", "primary", "180 g", "cereali"),
           ("pomodoro", "primary", "300 g", "verdura"),
       ]


   async def test_le_righe_tenute_si_riagganciano_e_le_nuove_si_propongono(db_session, originale):
       draft = await draft_variant(db_session, originale, "senza basilico", client=FakeLlm(VARIANTE))

       assert draft.title == "Pasta al pomodoro senza basilico"
       assert draft.cost == 1
       righe = {i.raw_name: i for i in draft.ingredients}
       assert righe["pasta"].ingredient_id is not None
       assert righe["pasta"].confident is True
       assert righe["pomodoro"].quantity_text == "350 g"
       # uno nuovo che l'anagrafica non ha: si propone col reparto, «da creare salvando»
       assert righe["zucchero"].ingredient_id is None
       assert righe["zucchero"].proposed_category == "dolci"


   async def test_la_variante_non_introduce_un_non_alimentare(db_session, originale):
       """Né agganciato (la carta forno c'è, ma è di casa) né da creare (il detersivo non
       c'è, e il suo reparto non è del cibo): tutti e due tornano senza aggancio e senza
       reparto, e non partono salvando. La carta forno, che l'anagrafica conosce con
       certezza, dice «non è un alimento»; il detersivo, che non conosce, «non in anagrafica»."""
       db_session.add(
           Ingredient(name="carta forno", display_name="Carta forno", category=IngredientCategory.CASA)
       )
       await db_session.flush()
       risposta = {**VARIANTE, "ingredients": [
           *VARIANTE["ingredients"],
           {"name": "carta forno", "role": "secondary", "quantity_text": "1 foglio", "category": "casa"},
           {"name": "detersivo per piatti", "role": "secondary", "quantity_text": "1 goccia",
            "category": "casa"},
       ]}

       draft = await draft_variant(db_session, originale, "in forno", client=FakeLlm(risposta))

       righe = {i.raw_name: i for i in draft.ingredients}
       for nome in ("carta forno", "detersivo per piatti"):
           assert righe[nome].ingredient_id is None, nome
           assert righe[nome].proposed_category is None, nome


   async def test_la_spesa_della_variante_ha_la_sua_sezione(db_session, originale):
       from sqlalchemy import select

       from app.db.models.llm_call import LlmCall
       from app.services.llm import LlmCallSite
       from llm_fakes import COSTO_FINTO

       await draft_variant(db_session, originale, "senza basilico", client=FakeLlm(VARIANTE))

       # committata: una variante chiesta e buttata è pagata lo stesso (vedi `_record_spend`)
       assert not db_session.new, "la spesa è solo in sospeso: senza commit andrebbe persa"
       riga = (await db_session.execute(select(LlmCall))).scalar_one()
       assert riga.call_site == LlmCallSite.RECIPE_VARIANT == "recipe_variant"
       assert riga.ok is True
       assert riga.cost_usd == pytest.approx(COSTO_FINTO)


   async def test_un_modello_giu_durante_la_variante_e_spesa_fallita(db_session, originale):
       from sqlalchemy import select

       from app.db.models.llm_call import LlmCall
       from app.services.llm import LlmCallSite

       with pytest.raises(LlmUnavailable):
           await draft_variant(
               db_session, originale, "senza basilico",
               client=FakeLlm(httpx.ReadTimeout("troppo lento")),
           )

       assert not db_session.new, "la spesa è solo in sospeso: senza commit andrebbe persa"
       riga = (await db_session.execute(select(LlmCall))).scalar_one()
       assert riga.call_site == LlmCallSite.RECIPE_VARIANT
       assert riga.ok is False
       assert riga.cost_usd is None
   ```

- [ ] **Step 2: Falliscono**

Run: il comando di pytest con `tests/services/test_ai_recipes.py`
Expected: FAIL all'import (`ImportError: cannot import name 'VARIANT_MAX_TOKENS'`).

- [ ] **Step 3: La sezione delle spese**

In `backend/app/services/llm.py`, in `class LlmCallSite(StrEnum)`, **dopo l'ultimo membro** che trovi sul ramo (su `master` è `UNIT_FORMS = "unit_forms"`; S12 ha aggiunto `INGREDIENT_EMOJI = "ingredient_emoji"`), aggiungi:

```python
    # R8: «Modifica con AI», la variante di una ricetta che esiste
    RECIPE_VARIANT = "recipe_variant"
```

- [ ] **Step 4: Il servizio**

In `backend/app/services/ai_recipes.py`:

1. Gli import in testa diventano:
   ```python
   import json
   import uuid
   from dataclasses import dataclass
   from typing import Any

   from sqlalchemy.ext.asyncio import AsyncSession

   from app.db.models.recipe import Recipe
   from app.domain.rules import IngredientKind, IngredientRole, cost_in_scale
   from app.services.ingredient_match import match_name
   from app.repositories.llm_calls import record_llm_call
   from app.services.llm import LlmCallSite, LlmUnavailable, LlmUsage, complete_json
   from app.services.recipe_import.decide import CATEGORIES
   ```
2. Subito dopo la costante `DRAFT_MAX_TOKENS = 2000`, aggiungi:
   ```python
   # La variante rimanda indietro la ricetta intera, e un procedimento importato è lungo:
   # col tetto della bozza una risposta troncata sarebbe JSON rotto, cioè un 503.
   VARIANT_MAX_TOKENS = 4000
   ```
3. Subito dopo la chiusura di `SYSTEM_PROMPT` (la riga `"""` che chiude il testo, prima di `DRAFT_SCHEMA = {`), aggiungi:
   ```python
   # R8. Le regole della bozza valgono tutte — lo schema, i ruoli, i nomi generici, il
   # costo, niente nutrienti, i reparti del cibo — e la variante ne aggiunge di sue: per
   # questo il testo estende `SYSTEM_PROMPT` invece di ricopiarlo.
   VARIANT_SYSTEM_PROMPT = SYSTEM_PROMPT + """
   Questa volta non scrivi una ricetta da zero. Ricevi un oggetto JSON con due chiavi: "ricetta", una ricetta che esiste già, e "richiesta", la modifica che la persona vuole. Rispondi con la ricetta modificata, intera, nello stesso schema.
   - Applica la richiesta e ribilancia il resto: se togli, aggiungi o sostituisci un ingrediente, correggi le dosi, i tempi e i passaggi del procedimento che ne dipendono, perché il piatto riesca. Sostituire lo zucchero con un dolcificante, per esempio, cambia la dose e può cambiare i liquidi e la cottura.
   - Quel che la richiesta non tocca resta com'è: gli ingredienti con lo stesso "name", la stessa "quantity_text", lo stesso "role" e la stessa "category", e lo stesso numero di porzioni.
   - "title" dice in cosa la variante è diversa dall'originale: "Torta di mele con dolcificante", non di nuovo "Torta di mele".
   - "cost" è il costo della variante, non quello dell'originale.
   - Solo ingredienti alimentari: niente prodotti per la casa o per l'igiene, anche se la richiesta li nomina.
   """
   ```
4. Sostituisci **per intero** le due funzioni `draft_recipe` e `_record_spend` (dalla riga `async def draft_recipe(` alla fine del file) con:
   ```python
   async def draft_recipe(
       session: AsyncSession, prompt: str, client: object | None = None
   ) -> RecipeDraft:
       payload = await _ask(
           session, call_site=LlmCallSite.RECIPE_DRAFT, system=SYSTEM_PROMPT, user=prompt,
           max_tokens=DRAFT_MAX_TOKENS, client=client,
       )
       return await _draft_from(session, payload)


   def variant_question(recipe: Recipe, prompt: str) -> str:
       """La domanda della variante: la ricetta com'è salvata, e la richiesta (R8).

       Le righe col nome canonico dell'anagrafica e non col nome a video: è quello che
       `match_name` riconosce con certezza, quindi le righe che la variante tiene tornano
       agganciate senza niente da confermare. Il reparto c'è perché lo schema lo chiede a
       ogni riga, e il modello lo ripete invece di indovinarlo.
       """
       return json.dumps(
           {
               "ricetta": {
                   "title": recipe.title,
                   "description": recipe.description,
                   "instructions": recipe.instructions,
                   "servings": recipe.servings,
                   "cost": recipe.cost,
                   "ingredients": [
                       {
                           "name": line.ingredient.name,
                           "role": line.role,
                           "quantity_text": line.quantity_text,
                           "category": line.ingredient.category,
                       }
                       for line in recipe.ingredients
                   ],
               },
               "richiesta": prompt,
           },
           ensure_ascii=False,
       )


   async def draft_variant(
       session: AsyncSession, recipe: Recipe, prompt: str, client: object | None = None
   ) -> RecipeDraft:
       """Una variante di `recipe` secondo `prompt` (R8): la ricetta modificata, intera, da
       correggere nel modulo. Propone e non salva, e l'originale non si tocca: si salva con
       `POST /recipes` e `derived_from_id`, come ogni ricetta nuova.

       La domanda si costruisce prima della chiamata: dopo, la registrazione della spesa fa
       `commit` sulla sessione.
       """
       question = variant_question(recipe, prompt)
       payload = await _ask(
           session, call_site=LlmCallSite.RECIPE_VARIANT, system=VARIANT_SYSTEM_PROMPT,
           user=question, max_tokens=VARIANT_MAX_TOKENS, client=client,
       )
       return await _draft_from(session, payload)


   async def _ask(
       session: AsyncSession,
       *,
       call_site: LlmCallSite,
       system: str,
       user: str,
       max_tokens: int,
       client: object | None,
   ) -> dict[str, Any]:
       """Una chiamata con lo schema della bozza, con la spesa registrata comunque vada."""
       try:
           esito = await complete_json(
               call_site=call_site,
               system=system,
               user=user,
               schema=DRAFT_SCHEMA,
               schema_name="bozza_ricetta",
               max_tokens=max_tokens,
               client=client,
           )
       except LlmUnavailable:
           await _record_spend(session, call_site, LlmUsage(), ok=False)
           raise

       await _record_spend(session, call_site, esito.usage, ok=True)
       return esito.data


   async def _draft_from(session: AsyncSession, payload: dict[str, Any]) -> RecipeDraft:
       """La risposta del modello diventa una bozza: la stessa lavorazione per la stesura da
       zero e per la variante (R8), così le guardie sulle righe sono una sola."""
       raw_ingredients = payload.get("ingredients") or []
       if not isinstance(raw_ingredients, list):
           raise LlmUnavailable("la lista degli ingredienti ha una forma inutilizzabile")

       ingredients: list[DraftIngredient] = []
       for entry in raw_ingredients:
           if not isinstance(entry, dict):
               continue
           raw_name = str(entry.get("name", "")).strip()
           if not raw_name:
               continue
           role = (
               IngredientRole.SECONDARY
               if entry.get("role") == IngredientRole.SECONDARY
               else IngredientRole.PRIMARY
           )
           match = await match_name(session, raw_name)
           # Stessa idea di `proposed_category` due righe sotto: una riga non agganciata
           # che l'utente risolve col selettore è meglio di una già agganciata che
           # `POST /recipes` rifiuterebbe con un 422 (finding 3 della revisione
           # finale). Il selettore, dal Task 9, offre solo cibo.
           non_food = match.kind == IngredientKind.NON_FOOD
           category = str(entry.get("category") or "").strip().lower()
           ingredients.append(
               DraftIngredient(
                   raw_name=raw_name, role=role,
                   quantity_text=entry.get("quantity_text") or None,
                   ingredient_id=None if non_food else match.ingredient_id,
                   matched_name=None if non_food else match.name,
                   confident=False if non_food else match.certain,
                   # Solo se l'anagrafica non ce l'ha: proporre una categoria per un
                   # ingrediente che esiste già inviterebbe a cambiargliela da una
                   # schermata che non è il registro. E solo se è una delle dodici: un
                   # campo vuoto da riempire è meglio di un valore che il salvataggio
                   # rifiuterebbe.
                   proposed_category=(
                       category
                       if match.ingredient_id is None and category in CATEGORIES
                       else None
                   ),
               )
           )

       return RecipeDraft(
           title=str(payload.get("title", "Senza titolo")),
           description=payload.get("description") or None,
           instructions=str(payload.get("instructions", "")),
           servings=payload.get("servings"),
           ingredients=ingredients,
           # fuori scala, non intero o assente è nessun costo: il modulo lo mostra vuoto,
           # e un campo vuoto è meglio di un gradino inventato o arrotondato
           cost=cost_in_scale(payload.get("cost")),
       )


   async def _record_spend(
       session: AsyncSession, call_site: LlmCallSite, usage: LlmUsage, *, ok: bool
   ) -> None:
       """La spesa si committa anche se la bozza non si salva.

       Queste rotte propongono e non scrivono: la loro sessione non viene committata da
       nessuno. Ma la chiamata è avvenuta ed è stata pagata che l'utente salvi la ricetta
       o la butti, e legarne la registrazione al salvataggio renderebbe invisibile
       proprio il consumo più facile da fare per sbaglio — dieci bozze chieste e nessuna
       tenuta. La commit è sicura perché su questo percorso non c'è nient'altro in sospeso
       nella sessione.
       """
       await record_llm_call(session, call_site=call_site, usage=usage, ok=ok)
       await session.commit()
   ```
   Confronta il corpo di `_draft_from` con quello che `draft_recipe` aveva sul ramo (dalla riga `raw_ingredients = …` al `return RecipeDraft(…)`): deve essere identico. Se sul ramo era diverso da quello scritto qui, tieni quello del ramo.

- [ ] **Step 5: Passano, con le guardie della spesa**

Run: il comando di pytest con `tests/services/test_ai_recipes.py tests/test_llm_spend_is_recorded.py tests/services/test_llm.py tests/db/test_llm_calls.py`
Expected: PASS — i cinque test nuovi e tutti quelli della bozza da zero, che non cambiano.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/llm.py backend/app/services/ai_recipes.py backend/tests/services/test_ai_recipes.py
git commit -m "feat(ai): R8, draft_variant — la ricetta intera e la richiesta, la sezione recipe_variant nelle spese"
```

---

### Task 4: La rotta della proposta

**Files:**
- Modify: `backend/app/api/recipes.py` (nuova rotta `ai_variant`, nuovo `_draft_out`, `ai_draft` lo usa)
- Modify: `backend/tests/api/test_recipes_variant.py`

**Interfaces:**
- Consumes: `draft_variant` (Task 3), `get_recipe`, `RECIPE_ARCHIVED`, `DraftRequest`, `DraftOut`.
- Produces: `POST /api/v1/recipes/{recipe_id}/ai-variant` → `DraftOut`; 404, 409 (`RECIPE_ARCHIVED`), 503 («variante AI non disponibile: …»). Il frontend la chiama (Task 6).

- [ ] **Step 1: I test che falliscono**

In `backend/tests/api/test_recipes_variant.py`:

1. In testa, la riga `from sqlalchemy import select` diventa `from sqlalchemy import func, select`, e agli import di `app` aggiungi:
   ```python
   from app.domain.rules import IngredientRole
   from app.services.ai_recipes import DraftIngredient, RecipeDraft
   from app.services.llm import LlmUnavailable
   ```
2. In fondo al file aggiungi:

```python
# ---- la proposta: POST /recipes/{id}/ai-variant ----


def proposta() -> RecipeDraft:
    return RecipeDraft(
        title=TITOLO_VARIANTE, description=None, instructions="Cuoci. Condisci.",
        servings=2, cost=1,
        ingredients=[
            DraftIngredient(
                raw_name="zucchero", role=IngredientRole.SECONDARY, quantity_text="1 pizzico",
                ingredient_id=None, matched_name=None, confident=False, proposed_category="dolci",
            )
        ],
    )


async def test_la_proposta_passa_dal_servizio_e_non_salva_niente(
    logged_client, db_session, monkeypatch, originale
):
    import app.api.recipes as rotte

    chiamate = []

    async def variante_finta(_session, recipe, prompt):
        chiamate.append((recipe.id, recipe.title, len(recipe.ingredients), prompt))
        return proposta()

    monkeypatch.setattr(rotte, "draft_variant", variante_finta)
    risposta = await logged_client.post(
        f"/api/v1/recipes/{originale.id}/ai-variant", json={"prompt": "senza basilico"}
    )

    assert risposta.status_code == 200
    # il servizio riceve la ricetta con le sue righe, e la richiesta com'è
    assert chiamate == [(originale.id, "Pasta al pomodoro", 3, "senza basilico")]
    corpo = risposta.json()
    assert corpo["title"] == TITOLO_VARIANTE
    assert corpo["cost"] == 1
    assert corpo["ingredients"][0]["raw_name"] == "zucchero"
    assert corpo["ingredients"][0]["proposed_category"] == "dolci"
    # propone e non salva: nel ricettario c'è sempre e solo l'originale
    assert await db_session.scalar(select(func.count()).select_from(Recipe)) == 1


async def test_la_proposta_di_una_ricetta_che_non_c_e_e_un_404(logged_client):
    risposta = await logged_client.post(
        f"/api/v1/recipes/{uuid.uuid4()}/ai-variant", json={"prompt": "senza basilico"}
    )
    assert risposta.status_code == 404


async def test_una_ricetta_eliminata_non_propone_varianti(logged_client, monkeypatch, originale):
    """R10: un'eliminata si ripristina prima di modificarla, e la variante è una modifica."""
    import app.api.recipes as rotte

    async def mai(*_args):
        raise AssertionError("l'AI non si chiama per una ricetta eliminata")

    monkeypatch.setattr(rotte, "draft_variant", mai)
    await logged_client.patch(f"/api/v1/recipes/{originale.id}", json={"archived": True})

    risposta = await logged_client.post(
        f"/api/v1/recipes/{originale.id}/ai-variant", json={"prompt": "senza basilico"}
    )

    assert risposta.status_code == 409
    assert risposta.json()["detail"] == (
        "Questa ricetta è stata eliminata: ripristinala prima di modificarla."
    )


async def test_l_ai_che_non_risponde_e_un_503(logged_client, monkeypatch, originale):
    import app.api.recipes as rotte

    async def giu(*_args):
        raise LlmUnavailable("OPENROUTER_API_KEY non configurata")

    monkeypatch.setattr(rotte, "draft_variant", giu)
    risposta = await logged_client.post(
        f"/api/v1/recipes/{originale.id}/ai-variant", json={"prompt": "senza basilico"}
    )

    assert risposta.status_code == 503
    assert risposta.json()["detail"].startswith("variante AI non disponibile")


async def test_la_proposta_senza_sessione_e_rifiutata(client, originale):
    risposta = await client.post(
        f"/api/v1/recipes/{originale.id}/ai-variant", json={"prompt": "senza basilico"}
    )
    assert risposta.status_code == 401
```

- [ ] **Step 2: Falliscono**

Run: il comando di pytest con `tests/api/test_recipes_variant.py`
Expected: FAIL — `AttributeError: <module 'app.api.recipes'> has no attribute 'draft_variant'` (il `monkeypatch.setattr` è rigoroso), e 404/405 per la rotta che non c'è.

- [ ] **Step 3: La rotta**

In `backend/app/api/recipes.py`:

1. La riga `from app.services.ai_recipes import draft_recipe` diventa
   ```python
   from app.services.ai_recipes import RecipeDraft, draft_recipe, draft_variant
   ```
2. Sostituisci la funzione `ai_draft` per intero (dal decoratore `@router.post("/ai-draft", response_model=DraftOut)` alla fine del file) con:
   ```python
   def _draft_out(draft: RecipeDraft) -> DraftOut:
       """La bozza come la legge il modulo: la stessa forma per la stesura e per la variante."""
       return DraftOut(
           title=draft.title, description=draft.description, instructions=draft.instructions,
           servings=draft.servings,
           ingredients=[DraftIngredientOut(**vars(i)) for i in draft.ingredients],
           cost=draft.cost,
       )


   @router.post("/ai-draft", response_model=DraftOut)
   async def ai_draft(
       payload: DraftRequest, session: AsyncSession = Depends(get_session)
   ) -> DraftOut:
       """Propone, non salva. Il salvataggio passa da POST /recipes come le altre."""
       try:
           draft = await draft_recipe(session, payload.prompt)
       except LlmUnavailable as exc:
           raise HTTPException(
               status.HTTP_503_SERVICE_UNAVAILABLE, f"stesura AI non disponibile: {exc}"
           ) from exc
       return _draft_out(draft)


   @router.post("/{recipe_id}/ai-variant", response_model=DraftOut)
   async def ai_variant(
       recipe_id: uuid.UUID, payload: DraftRequest, session: AsyncSession = Depends(get_session)
   ) -> DraftOut:
       """Propone una variante della ricetta, e non salva niente (R8).

       La variante si salva con `POST /recipes` e `derived_from_id`: una ricetta nuova,
       mentre questa resta com'è. Un'eliminata risponde come alla modifica (R10): prima
       si ripristina.
       """
       recipe = await get_recipe(session, recipe_id)
       if recipe is None:
           raise HTTPException(status.HTTP_404_NOT_FOUND, "ricetta inesistente")
       if recipe.archived_at is not None:
           raise HTTPException(status.HTTP_409_CONFLICT, RECIPE_ARCHIVED)
       try:
           draft = await draft_variant(session, recipe, payload.prompt)
       except LlmUnavailable as exc:
           raise HTTPException(
               status.HTTP_503_SERVICE_UNAVAILABLE, f"variante AI non disponibile: {exc}"
           ) from exc
       return _draft_out(draft)
   ```

- [ ] **Step 4: Passano, con la suite delle ricette**

Run: il comando di pytest con `tests/api/`
Expected: PASS (compreso `test_recipes_cost.py::test_la_rotta_della_bozza_consegna_il_costo`, che prova `ai_draft` dopo `_draft_out`).

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/recipes.py backend/tests/api/test_recipes_variant.py
git commit -m "feat(api): R8, POST /recipes/{id}/ai-variant propone una variante e non salva"
```

---

### Task 5: L'import che rifà l'originale non perde il legame

**Files:**
- Modify: `backend/app/services/recipe_import/materialize.py` (`VARIANTS_KEY`, `_relink_variants`, `materialize_ready`)
- Modify: `backend/app/services/recipe_import/undo.py` (`undo_decision`)
- Modify: `backend/tests/services/test_undo.py`

**Interfaces:**
- Consumes: `Recipe.derived_from_id` (Task 1), `create_recipe(derived_from_id=…)` (Task 2).
- Produces: `VARIANTS_KEY = "variant_recipe_ids"` in `app.services.recipe_import.materialize`; `undo_decision` scrive lì gli id delle varianti di ogni ricetta che cancella; `materialize_ready` li rimette sulla ricetta rifatta. `Materialized` non cambia.

- [ ] **Step 1: I test che falliscono**

In `backend/tests/services/test_undo.py`, subito dopo il test `test_la_cottura_ritrova_la_ricetta_quando_la_pagina_torna`, aggiungi:

```python
async def _variante_di(db_session, recipe, speck):
    """Una variante scritta con l'AI (R8) della ricetta importata del `deciso`."""
    return await create_recipe(
        db_session, title="Pasta allo speck, senza panna", description=None,
        instructions="cuoci", servings=2, source=RecipeSource.AI,
        source_ref="prompt: senza panna", ingredients=[(speck.id, "primary", "80 g", None)],
        embedding=None, derived_from_id=recipe.id,
    )


async def test_le_varianti_di_una_ricetta_rifatta_aspettano_nella_pagina(
    db_session, deciso, dal_database
):
    """R8: annullare una decisione cancella la ricetta importata per rifarla, e
    `derived_from_id` è ON DELETE SET NULL. Come le cotture, gli id delle varianti passano
    nel `payload` prima della cancellazione; la variante resta, senza legame per ora."""
    term, speck, recipe, page = deciso
    variante = await _variante_di(db_session, recipe, speck)
    variante_id, page_id = variante.id, page.id

    await undo_decision(db_session, term)

    pagina = await dal_database(RecipeImport, page_id)
    assert pagina.payload["variant_recipe_ids"] == [str(variante_id)]
    letta = await dal_database(Recipe, variante_id)
    assert letta is not None
    assert letta.derived_from_id is None


async def test_la_variante_ritrova_l_originale_quando_la_pagina_torna(
    db_session, deciso, dal_database
):
    term, speck, recipe, page = deciso
    variante = await _variante_di(db_session, recipe, speck)
    variante_id, page_id = variante.id, page.id

    await undo_decision(db_session, term)
    pancetta = await create_ingredient(
        db_session, name="pancetta", display_name="Pancetta", category=IngredientCategory.CARNE
    )
    await decide_by_hand(db_session, term, ManualDecision(action="map", ingredient_id=pancetta.id))
    esito = await materialize_ready(db_session, GIALLOZAFFERANO)

    assert esito.created == 1
    pagina = await dal_database(RecipeImport, page_id)
    letta = await dal_database(Recipe, variante_id)
    assert pagina.recipe_id is not None
    assert letta.derived_from_id == pagina.recipe_id
    assert "variant_recipe_ids" not in pagina.payload
```

- [ ] **Step 2: Falliscono**

Run: il comando di pytest con `tests/services/test_undo.py -k variant`
Expected: FAIL — `KeyError: 'variant_recipe_ids'`, e nel secondo `letta.derived_from_id` resta `None`.

- [ ] **Step 3: `materialize.py`**

In `backend/app/services/recipe_import/materialize.py`:

1. Se `Recipe` non è già importato da `app.db.models.recipe`, aggiungilo a quell'import (accanto a `CookingEvent`).
2. Subito dopo la riga `COOKING_EVENTS_KEY = "cooking_event_ids"`, aggiungi:
   ```python
   # R8: le varianti di una ricetta cancellata per rifarla aspettano qui, come le cotture.
   VARIANTS_KEY = "variant_recipe_ids"
   ```
3. Subito dopo la funzione `_relink_cooking_events`, aggiungi:
   ```python
   async def _relink_variants(
       session: AsyncSession, page: RecipeImport, recipe_id: uuid.UUID
   ) -> None:
       """Rimette sulla ricetta rifatta il legame delle sue varianti (R8).

       Stessa forma di `_relink_cooking_events`: `derived_from_id IS NULL` nella condizione,
       perché una variante che nel frattempo qualcuno ha legato ad altro non si ruba; la
       chiave si toglie riassegnando il dizionario, perché SQLAlchemy non vede le mutazioni
       dentro un JSONB.
       """
       waiting = page.payload.get(VARIANTS_KEY)
       if not waiting:
           return
       await session.execute(
           update(Recipe)
           .where(
               Recipe.id.in_([uuid.UUID(str(value)) for value in waiting]),
               Recipe.derived_from_id.is_(None),
           )
           .values(derived_from_id=recipe_id)
       )
       page.payload = {key: value for key, value in page.payload.items() if key != VARIANTS_KEY}
   ```
4. In `materialize_ready`, subito dopo la riga
   ```python
           relinked += await _relink_cooking_events(session, page, recipe.id)
   ```
   aggiungi:
   ```python
           await _relink_variants(session, page, recipe.id)
   ```

- [ ] **Step 4: `undo.py`**

In `backend/app/services/recipe_import/undo.py`:

1. La riga `from app.services.recipe_import.materialize import COOKING_EVENTS_KEY` diventa
   ```python
   from app.services.recipe_import.materialize import COOKING_EVENTS_KEY, VARIANTS_KEY
   ```
2. In `undo_decision`, dentro il ciclo sulle pagine, subito dopo il blocco
   ```python
               if cooked:
                   payload[COOKING_EVENTS_KEY] = sorted(
                       {*payload.get(COOKING_EVENTS_KEY, []), *cooked}
                   )
   ```
   aggiungi:
   ```python
               # R8: `recipes.derived_from_id` è ON DELETE SET NULL come le cotture, e per lo
               # stesso motivo le varianti di questa ricetta aspettano nel `payload`:
               # `materialize_ready` rimette il legame sulla ricetta rifatta
               variants = [
                   str(variant_id)
                   for variant_id in (
                       await session.execute(
                           select(Recipe.id).where(Recipe.derived_from_id == recipe.id)
                       )
                   ).scalars()
               ]
               if variants:
                   payload[VARIANTS_KEY] = sorted({*payload.get(VARIANTS_KEY, []), *variants})
   ```
3. Nella docstring del modulo, in fondo al paragrafo che comincia con «Nelle ricette cancellate ci sono due cose da preservare», aggiungi la frase: «Da R8 ce n'è una terza, il legame delle varianti (`recipes.derived_from_id`, anche lui ON DELETE SET NULL): gli id delle varianti aspettano alla chiave `variant_recipe_ids` (`VARIANTS_KEY`), e tornano allo stesso modo.»

- [ ] **Step 5: Passano, con l'import intero**

Run: il comando di pytest con `tests/services/test_undo.py tests/services/test_materialize.py tests/services/test_registry_merge.py tests/api/test_imports_undo.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/recipe_import/materialize.py backend/app/services/recipe_import/undo.py backend/tests/services/test_undo.py
git commit -m "feat(import): R8, una ricetta rifatta dall'annullamento ritrova le sue varianti"
```

---

### Task 6: Il frontend — i tipi, le chiamate, `sourceRef` condiviso

**Files:**
- Modify: `frontend/src/domain/types.ts` (`RecipeDetail`; nuovo `RecipeOrigin`)
- Modify: `frontend/src/features/recipes/api.ts` (`createRecipe`; nuovo `draftVariant`)
- Create: `frontend/src/features/ai-draft/sourceRef.ts`, `frontend/src/features/ai-draft/sourceRef.test.ts`
- Modify: `frontend/src/features/ai-draft/AiDraftScreen.tsx`
- Modify (solo il campo nuovo): ogni test con una `RecipeDetail` scritta a mano — su `master` `frontend/src/features/cooking/RecipeDetailScreen.test.tsx`, `RecipeDetailActions.test.tsx`, `CookSheet.test.tsx`, `frontend/src/features/recipe-form/formModel.test.ts`, `RecipeEditScreen.test.tsx`, `RecipeForm.test.tsx`; più quelli che `npm run typecheck` segnala sul ramo

**Interfaces:**
- Produces: `interface RecipeOrigin { id: string; title: string; archived: boolean }`; `RecipeDetail.derived_from: RecipeOrigin | null`; `createRecipe(body: RecipeBody & { source: RecipeSource; source_ref: string | null; derived_from_id?: string })`; `draftVariant(id: string, prompt: string): Promise<RecipeDraft>`; `sourceRef(prompt: string): string` in `features/ai-draft/sourceRef.ts`. Il Task 7 li usa.

- [ ] **Step 1: Il test che fallisce**

Crea `frontend/src/features/ai-draft/sourceRef.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { sourceRef } from "./sourceRef";

describe("sourceRef", () => {
  it("un prompt corto passa com'è, dopo «prompt: »", () => {
    expect(sourceRef("senza basilico")).toBe("prompt: senza basilico");
  });

  it("un prompt lungo si accorcia a 500 caratteri, e l'ultimo è «…»", () => {
    const ref = sourceRef("a".repeat(1000));
    expect(ref).toHaveLength(500);
    expect(ref.startsWith("prompt: aaa")).toBe(true);
    expect(ref.endsWith("…")).toBe(true);
  });
});
```

Run (da `<worktree>/frontend`): `npx vitest run src/features/ai-draft/sourceRef.test.ts`
Expected: FAIL («Failed to resolve import "./sourceRef"»).

- [ ] **Step 2: `sourceRef` in un modulo suo**

Crea `frontend/src/features/ai-draft/sourceRef.ts`:

```ts
const SOURCE_REF_MAX = 500;

/** `source_ref` sta in 500 caratteri, il prompt può arrivarne a 1000: la provenienza si
 * accorcia, il testo scritto no — quello resta nel suo campo. Senza questo, un prompt
 * lungo faceva rifiutare il salvataggio con un 422. In un modulo suo perché lo usano la
 * bozza da zero e la variante (R8). */
export function sourceRef(prompt: string): string {
  const ref = `prompt: ${prompt}`;
  return ref.length <= SOURCE_REF_MAX ? ref : `${ref.slice(0, SOURCE_REF_MAX - 1)}…`;
}
```

In `frontend/src/features/ai-draft/AiDraftScreen.tsx` togli la costante `const SOURCE_REF_MAX = 500;`, il commento JSDoc che comincia con «`source_ref` sta in 500 caratteri» e la funzione `sourceRef` sotto di lui; fra gli import aggiungi:

```ts
import { sourceRef } from "./sourceRef";
```

- [ ] **Step 3: I tipi e le chiamate**

In `frontend/src/domain/types.ts`:

1. Subito prima di `export interface RecipeDetail extends RecipeSummary {`, aggiungi:
   ```ts
   /** La ricetta da cui una variante nasce (R8), come la manda il server: il titolo di oggi
    * e se è stata eliminata. Il collegamento la apre comunque: eliminata, si apre dalla sua
    * lapide con «Ripristina» (R10). */
   export interface RecipeOrigin {
     id: string;
     title: string;
     archived: boolean;
   }
   ```
2. In `RecipeDetail`, dopo il campo `owned_by_import: boolean;`, aggiungi:
   ```ts
     /** Da quale ricetta nasce, se è una variante scritta con l'AI (R8); `null` altrimenti.
      * Lo dice il server: il client non cerca l'originale da sé. */
     derived_from: RecipeOrigin | null;
   ```

In `frontend/src/features/recipes/api.ts`:

1. `createRecipe` diventa:
   ```ts
   /** Una ricetta nuova. `derived_from_id` solo per una variante (R8): la ricetta da cui
    * nasce, che il salvataggio non tocca. */
   export function createRecipe(
     body: RecipeBody & { source: RecipeSource; source_ref: string | null; derived_from_id?: string }
   ) {
     return apiFetch<RecipeDetail>("/recipes", { method: "POST", body: JSON.stringify(body) });
   }
   ```
2. Subito dopo la funzione `draftRecipe`, aggiungi:
   ```ts
   /** Propone una variante della ricetta `id` (R8): non salva, e non tocca l'originale. La
    * variante si salva con `createRecipe` e `derived_from_id`, come ogni ricetta nuova. */
   export function draftVariant(id: string, prompt: string) {
     return apiFetch<RecipeDraft>(`/recipes/${id}/ai-variant`, {
       method: "POST",
       body: JSON.stringify({ prompt }),
     });
   }
   ```

- [ ] **Step 4: Il campo nuovo negli oggetti scritti a mano**

Run (da `<worktree>/frontend`): `npm run typecheck`
Expected: errori `TS2741` (o `TS2739`) «Property 'derived_from' is missing» nei test con una `RecipeDetail` scritta a mano. Su `master` sono sei, e in ognuno la `RecipeDetail` contiene `owned_by_import: …,`: subito dopo aggiungi `derived_from: null,` —
`RecipeDetailScreen.test.tsx` (`DETAIL`), `RecipeDetailActions.test.tsx` (`DETAIL`), `CookSheet.test.tsx` (la ricetta in cima al file), `formModel.test.ts` (la ricetta in cima al file), `RecipeEditScreen.test.tsx` (`DETAIL`), `RecipeForm.test.tsx` (la ricetta in cima al file); più quelli che il ramo ha aggiunto. Nessun'altra modifica a quei test. Rilancia `npm run typecheck` finché non è pulito.

- [ ] **Step 5: Passano**

Run (da `<worktree>/frontend`): `npx vitest run src/features/ai-draft src/features/cooking src/features/recipe-form && npm run typecheck && npm run lint`
Expected: PASS, typecheck e lint puliti (`AiDraftScreen.test.tsx` prova ancora il prompt lungo accorciato, ora da `sourceRef.ts`).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/domain/types.ts frontend/src/features/recipes/api.ts frontend/src/features/ai-draft/ frontend/src/features/cooking/ frontend/src/features/recipe-form/
git commit -m "feat(frontend): R8, derived_from nel dettaglio, draftVariant, sourceRef condiviso"
```

(Se il typecheck ha segnalato file fuori da quelle cartelle, aggiungili al `git add`.)

---

### Task 7: Il pannello, il modulo della variante e il legame a video

**Files:**
- Create: `frontend/src/features/ai-variant/variantState.ts`, `variantState.test.ts`
- Create: `frontend/src/features/ai-variant/VariantPrompt.tsx`
- Create: `frontend/src/features/ai-variant/OriginLink.tsx`
- Create: `frontend/src/features/ai-variant/RecipeVariantScreen.tsx`
- Create: `frontend/src/features/ai-variant/RecipeVariant.test.tsx`
- Modify: `frontend/src/features/cooking/RecipeDetailScreen.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `draftVariant`, `createRecipe`, `sourceRef`, `RecipeOrigin`, `RecipeDetail.derived_from` (Task 6); `RecipeForm`, `EMPTY_FORM`, `applyDraft` (esistenti); `Button`, `Card`, `Alert tone="degraded"`, `Screen`, `IconToolbar`, `IconSparkles`, `useNotice` (esistenti).
- Produces: `VARIANT_PANEL_ID`, `variantPath(recipeId)`, `interface VariantState { prompt; draft; originTitle; originCategory }`, `readVariantState(state: unknown): VariantState | null`; i componenti `VariantPrompt({ recipe, onClose })`, `OriginLink({ origin })`, `RecipeVariantScreen()`; la rotta `/ricette/:id/variante`. Il Task 8 li prova nel browser.

- [ ] **Step 1: I test che falliscono**

Crea `frontend/src/features/ai-variant/variantState.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { readVariantState, variantPath } from "./variantState";
import type { RecipeDraft } from "../../domain/types";

const DRAFT: RecipeDraft = {
  title: "Torta di mele con dolcificante", description: null, instructions: "1. Impasta.",
  servings: 8, cost: 2, ingredients: [],
};

describe("readVariantState", () => {
  it("legge la proposta portata dalla cronologia", () => {
    const state = {
      prompt: "con dolcificante", draft: DRAFT, originTitle: "Torta di mele", originCategory: "Dolci",
    };
    expect(readVariantState(state)).toEqual(state);
  });

  it.each([
    [null],
    [undefined],
    ["testo"],
    [{}],
    [{ prompt: "x", originTitle: "y" }],
    [{ prompt: "x", originTitle: "y", draft: { title: "z" } }],
  ])("una voce della cronologia senza proposta (%j) non è una variante", (state) => {
    expect(readVariantState(state)).toBeNull();
  });

  it("una categoria assente vale «nessuna»", () => {
    expect(readVariantState({ prompt: "x", draft: DRAFT, originTitle: "y" })?.originCategory).toBeNull();
  });
});

describe("variantPath", () => {
  it("la variante si corregge sotto la ricetta da cui nasce", () => {
    expect(variantPath("r1")).toBe("/ricette/r1/variante");
  });
});
```

Crea `frontend/src/features/ai-variant/RecipeVariant.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { RecipeDetailScreen } from "../cooking/RecipeDetailScreen";
import { RecipeVariantScreen } from "./RecipeVariantScreen";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import type { RecipeDetail, RecipeDraft } from "../../domain/types";
import type { VariantState } from "./variantState";

const ORIGINALE: RecipeDetail = {
  id: "r1", title: "Pasta al pomodoro", description: null, source: "manual",
  missing: 0, cookable: true, missing_names: [], image_url: null, prep_minutes: null,
  cook_minutes: null, category: "Primi piatti", cost: 1, archived_at: null, main_department: null,
  instructions: "Cuoci.", servings: 2, source_ref: null, scaled_to: null,
  unscalable_lines: 0, dose_lines: 1, owned_by_import: false, derived_from: null,
  ingredients: [
    { ingredient_id: "i1", ingredient_name: "pasta", role: "primary", quantity_text: "180 g",
      quantity_display: "180 g", quantity_scaled: false, note: null,
      availability: "available", satisfied: true },
  ],
};

const VARIANTE: RecipeDetail = {
  ...ORIGINALE, id: "r2", title: "Pasta al pomodoro senza basilico", source: "ai",
  source_ref: "prompt: senza basilico",
  derived_from: { id: "r1", title: "Pasta al pomodoro", archived: false },
};

const PROPOSTA: RecipeDraft = {
  title: "Pasta al pomodoro senza basilico", description: null,
  instructions: "1. Cuoci la pasta.\n2. Condisci.", servings: 2, cost: 1,
  ingredients: [
    { raw_name: "pasta", role: "primary", quantity_text: "200 g", ingredient_id: "i1",
      matched_name: "pasta", confident: true, proposed_category: null },
  ],
};

type Rotta = (path: string, init?: RequestInit) => [unknown, number] | undefined;

/** Il test decide le risposte che gli interessano; le altre chiamate hanno una risposta
 * fissa: la dispensa vuota, una categoria, la variante per `r2` e l'originale per il resto. */
function stubFetch(route: Rotta = () => undefined) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const path = String(url);
    const [body, status] = route(path, init) ??
      (path.includes("/pantry")
        ? [[], 200]
        : path.includes("/recipes/categories")
          ? [["Primi piatti"], 200]
          : path.includes("/recipes/r2")
            ? [VARIANTE, 200]
            : [ORIGINALE, 200]);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function renderAt(entry: string | { pathname: string; state: unknown }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: defaultQueryRetryPredicate } },
  });
  return render(
    <QueryClientProvider client={client}>
      <NoticeProvider>
        <MemoryRouter initialEntries={[entry]}>
          <Routes>
            <Route path="/ricette" element={<p>Il ricettario</p>} />
            <Route path="/ricette/:id" element={<RecipeDetailScreen />} />
            <Route path="/ricette/:id/variante" element={<RecipeVariantScreen />} />
          </Routes>
        </MemoryRouter>
      </NoticeProvider>
    </QueryClientProvider>
  );
}

/** I corpi mandati con quel metodo a un indirizzo che finisce così. */
function mandati(spy: ReturnType<typeof stubFetch>, metodo: string, fine: string) {
  return spy.mock.calls
    .filter(([url, init]) => (init?.method ?? "GET") === metodo && String(url).endsWith(fine))
    .map(([, init]) => JSON.parse(String(init!.body)));
}

async function apriIlPannello() {
  const azioni = await screen.findByRole("toolbar", { name: "Azioni della ricetta" });
  await userEvent.click(within(azioni).getByRole("button", { name: "Modifica con AI" }));
  return screen.getByLabelText("Cosa vuoi cambiare?");
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("«Modifica con AI» nel dettaglio (R8)", () => {
  it("è un'icona fra «Modifica» ed «Elimina», e apre il pannello col fuoco nel campo", async () => {
    stubFetch();
    renderAt("/ricette/r1");

    const azioni = await screen.findByRole("toolbar", { name: "Azioni della ricetta" });
    expect(Array.from(azioni.children).map((el) => el.getAttribute("aria-label"))).toEqual([
      "Modifica", "Modifica con AI", "Elimina",
    ]);
    const tasto = within(azioni).getByRole("button", { name: "Modifica con AI" });
    expect(tasto).toHaveAttribute("aria-expanded", "false");

    await userEvent.click(tasto);

    expect(tasto).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByLabelText("Cosa vuoi cambiare?")).toHaveFocus();
    expect(
      screen.getByText("L'AI scrive una ricetta nuova, che correggi prima di salvare. Questa resta com'è.")
    ).toBeInTheDocument();
  });

  it("con meno di tre lettere «Proponi la variante» dice perché e non parte", async () => {
    const spy = stubFetch();
    renderAt("/ricette/r1");

    await userEvent.type(await apriIlPannello(), "zu");
    const proponi = screen.getByRole("button", { name: "Proponi la variante" });
    expect(proponi).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText("Scrivi cosa cambiare: bastano tre lettere.")).toBeInTheDocument();
    await userEvent.click(proponi);

    expect(mandati(spy, "POST", "/ai-variant")).toEqual([]);
  });

  it("«Annulla» chiude il pannello e ridà il fuoco a «Modifica con AI»", async () => {
    stubFetch();
    renderAt("/ricette/r1");

    await apriIlPannello();
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));

    expect(screen.queryByLabelText("Cosa vuoi cambiare?")).toBeNull();
    const tasto = screen.getByRole("button", { name: "Modifica con AI" });
    expect(tasto).toHaveFocus();
    expect(tasto).toHaveAttribute("aria-expanded", "false");
  });

  it("se l'AI non risponde si resta sulla ricetta, col testo scritto e l'avviso ambra", async () => {
    stubFetch((path) =>
      path.endsWith("/ai-variant") ? [{ detail: "variante AI non disponibile" }, 503] : undefined
    );
    renderAt("/ricette/r1");

    const campo = await apriIlPannello();
    await userEvent.type(campo, "senza basilico");
    await userEvent.click(screen.getByRole("button", { name: "Proponi la variante" }));

    const avviso = await screen.findByText(
      "L'AI non ha risposto: questa ricetta resta com'è. Riprova fra poco."
    );
    expect(avviso).toHaveAttribute("role", "alert");
    expect(avviso).toHaveClass("text-low");
    expect(screen.getByRole("heading", { level: 1, name: "Pasta al pomodoro" })).toBeInTheDocument();
    expect(campo).toHaveValue("senza basilico");
    expect(screen.queryByRole("heading", { name: "Nuova variante" })).toBeNull();
  });

  it("una ricetta eliminata non ha «Modifica con AI»", async () => {
    stubFetch((path) =>
      path.endsWith("/recipes/r1") ? [{ ...ORIGINALE, archived_at: "2026-10-01T10:00:00Z" }, 200] : undefined
    );
    renderAt("/ricette/r1");

    expect(await screen.findByText("Questa ricetta è stata eliminata.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Modifica con AI" })).toBeNull();
  });
});

describe("la variante, dalla proposta al salvataggio (R8)", () => {
  it("la proposta apre il modulo già compilato, e «Salva la variante» crea una ricetta nuova legata all'originale", async () => {
    const spy = stubFetch((path, init) => {
      if (path.endsWith("/ai-variant")) return [PROPOSTA, 200];
      if (path.endsWith("/api/v1/recipes") && init?.method === "POST") return [VARIANTE, 201];
      return undefined;
    });
    renderAt("/ricette/r1");

    await userEvent.type(await apriIlPannello(), "senza basilico");
    await userEvent.click(screen.getByRole("button", { name: "Proponi la variante" }));

    expect(await screen.findByRole("heading", { level: 1, name: "Nuova variante" })).toBeInTheDocument();
    expect(mandati(spy, "POST", "/recipes/r1/ai-variant")).toEqual([{ prompt: "senza basilico" }]);
    expect(screen.getByText("Variante di «Pasta al pomodoro»")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Hai chiesto: «senza basilico». Correggi quel che serve: salvando nasce una ricetta nuova, e l'originale resta com'è."
      )
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Titolo")).toHaveValue("Pasta al pomodoro senza basilico");

    await userEvent.click(screen.getByRole("button", { name: "Salva la variante" }));

    expect(
      await screen.findByRole("heading", { level: 1, name: "Pasta al pomodoro senza basilico" })
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Variante di «Pasta al pomodoro»" })).toHaveAttribute(
      "href", "/ricette/r1"
    );
    expect(screen.getByText("Salvata.")).toBeInTheDocument();
    const [corpo] = mandati(spy, "POST", "/api/v1/recipes");
    expect(corpo).toMatchObject({
      title: "Pasta al pomodoro senza basilico",
      category: "Primi piatti",
      source: "ai",
      source_ref: "prompt: senza basilico",
      derived_from_id: "r1",
      ingredients: [{ ingredient_id: "i1", role: "primary", quantity_text: "200 g" }],
    });
    // la foto e i tempi li copia il server dall'originale (Mattia, 2026-10-13): il modulo
    // non li ha, e non li manda
    for (const campo of ["image_url", "prep_minutes", "cook_minutes"]) {
      expect(corpo).not.toHaveProperty(campo);
    }
    // l'originale non si tocca: nessuna PUT e nessuna PATCH
    expect(
      spy.mock.calls.filter(([, init]) => init?.method === "PUT" || init?.method === "PATCH")
    ).toEqual([]);
  });

  it("con la proposta nella cronologia il modulo riparte da lì, anche dopo un ricaricamento", async () => {
    stubFetch();
    const state: VariantState = {
      prompt: "senza basilico", draft: PROPOSTA, originTitle: "Pasta al pomodoro",
      originCategory: "Primi piatti",
    };
    renderAt({ pathname: "/ricette/r1/variante", state });

    expect(await screen.findByRole("heading", { level: 1, name: "Nuova variante" })).toBeInTheDocument();
    expect(screen.getByLabelText("Titolo")).toHaveValue("Pasta al pomodoro senza basilico");
    expect(screen.getByRole("button", { name: "Salva la variante" })).toBeInTheDocument();
  });

  it("senza la proposta nella cronologia, «/variante» porta alla ricetta", async () => {
    stubFetch();
    renderAt("/ricette/r1/variante");

    expect(await screen.findByRole("heading", { level: 1, name: "Pasta al pomodoro" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Nuova variante" })).toBeNull();
  });
});

describe("il legame nel dettaglio della variante (R8)", () => {
  it("«Variante di «…»» porta all'originale, che non ne ha uno suo", async () => {
    stubFetch();
    renderAt("/ricette/r2");

    await userEvent.click(await screen.findByRole("link", { name: "Variante di «Pasta al pomodoro»" }));

    expect(await screen.findByRole("heading", { level: 1, name: "Pasta al pomodoro" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /^Variante di/ })).toBeNull();
  });

  it("un'originale eliminata si legge «(eliminata)», e il legame porta alla sua lapide", async () => {
    stubFetch((path) =>
      path.endsWith("/recipes/r2")
        ? [{ ...VARIANTE, derived_from: { id: "r1", title: "Pasta al pomodoro", archived: true } }, 200]
        : path.endsWith("/recipes/r1")
          ? [{ ...ORIGINALE, archived_at: "2026-10-01T10:00:00Z" }, 200]
          : undefined
    );
    renderAt("/ricette/r2");

    await userEvent.click(
      await screen.findByRole("link", { name: "Variante di «Pasta al pomodoro» (eliminata)" })
    );

    expect(await screen.findByText("Questa ricetta è stata eliminata.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ripristina" })).toBeInTheDocument();
  });

  it("dalla variante all'originale il dettaglio riparte da capo: le porzioni scelte non passano", async () => {
    const spy = stubFetch();
    renderAt("/ricette/r2");

    await userEvent.click(await screen.findByRole("button", { name: "Una porzione in più" }));
    await vi.waitFor(() =>
      expect(spy.mock.calls.some(([url]) => String(url).endsWith("/recipes/r2?servings=3"))).toBe(true)
    );
    await userEvent.click(screen.getByRole("link", { name: "Variante di «Pasta al pomodoro»" }));

    expect(await screen.findByRole("heading", { level: 1, name: "Pasta al pomodoro" })).toBeInTheDocument();
    const letture = spy.mock.calls.map(([url]) => String(url)).filter((url) => url.includes("/recipes/r1"));
    expect(letture).toContain("/api/v1/recipes/r1");
    expect(letture.filter((url) => url.includes("servings"))).toEqual([]);
  });
});
```

Run (da `<worktree>/frontend`): `npx vitest run src/features/ai-variant`
Expected: FAIL («Failed to resolve import "./variantState"» e «"./RecipeVariantScreen"»).

- [ ] **Step 2: Lo stato della cronologia**

Crea `frontend/src/features/ai-variant/variantState.ts`:

```ts
import type { RecipeDraft } from "../../domain/types";

/** L'id del pannello della variante nel dettaglio, per `aria-controls` del suo tasto. */
export const VARIANT_PANEL_ID = "variante-ai";

/** Dove si corregge la proposta: sotto la ricetta da cui nasce (R8). */
export function variantPath(recipeId: string): string {
  return `/ricette/${recipeId}/variante`;
}

/** Quel che il pannello consegna al modulo della variante, nella cronologia (R8): la
 * richiesta, la proposta dell'AI, e dell'originale il titolo (per le parole) e la
 * categoria (il modulo parte da lì: la proposta non ne ha). Nella cronologia e non in una
 * cache: regge un ricaricamento, e se ne va con la sua voce. */
export interface VariantState {
  prompt: string;
  draft: RecipeDraft;
  originTitle: string;
  originCategory: string | null;
}

/** La proposta portata dalla cronologia, o `null` se la voce non ne porta una — un
 * indirizzo scritto a mano, un preferito, una cronologia di prima. */
export function readVariantState(state: unknown): VariantState | null {
  if (typeof state !== "object" || state === null) return null;
  const candidate = state as Partial<VariantState>;
  const draft = candidate.draft;
  if (
    typeof candidate.prompt !== "string" ||
    typeof candidate.originTitle !== "string" ||
    typeof draft !== "object" ||
    draft === null ||
    !Array.isArray(draft.ingredients)
  )
    return null;
  return {
    prompt: candidate.prompt,
    draft,
    originTitle: candidate.originTitle,
    originCategory: typeof candidate.originCategory === "string" ? candidate.originCategory : null,
  };
}
```

- [ ] **Step 3: Il pannello**

Crea `frontend/src/features/ai-variant/VariantPrompt.tsx`:

```tsx
import { useEffect, useId, useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { draftVariant } from "../recipes/api";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { IconSparkles } from "../../components/ui/icons";
import { VARIANT_PANEL_ID, variantPath, type VariantState } from "./variantState";
import type { RecipeDetail } from "../../domain/types";

/** Il pannello di «Modifica con AI» nel dettaglio di una ricetta (R8): la richiesta, e la
 * proposta che apre il modulo della variante.
 *
 * Sta nel dettaglio dell'originale e non in uno schermo suo perché, se l'AI non risponde,
 * si resta sull'originale (Mattia, 2026-10-09): la ricetta è lì sotto, intera, e funziona
 * com'era. Il guasto ha il colore di ogni guasto dell'AI, l'ambra di `tone="degraded"`. */
export function VariantPrompt({ recipe, onClose }: { recipe: RecipeDetail; onClose: () => void }) {
  const navigate = useNavigate();
  const fieldId = useId();
  const fieldRef = useRef<HTMLTextAreaElement>(null);
  const [prompt, setPrompt] = useState("");
  const propose = useMutation({
    mutationFn: (request: string) => draftVariant(recipe.id, request),
  });

  // aperto il pannello, si scrive: il fuoco va nel campo
  useEffect(() => {
    fieldRef.current?.focus();
  }, []);

  function submit() {
    const request = prompt.trim();
    // La navigazione sta nelle callback di `mutate` e non nelle opzioni di `useMutation`:
    // quelle di `mutate` non partono se il pannello si è chiuso nel frattempo («Annulla»
    // con la proposta in volo), e una proposta rinunciata non deve aprire il modulo.
    propose.mutate(request, {
      onSuccess: (draft) => {
        const state: VariantState = {
          prompt: request,
          draft,
          originTitle: recipe.title,
          originCategory: recipe.category,
        };
        navigate(variantPath(recipe.id), { state });
      },
    });
  }

  return (
    <Card className="mt-3">
      <div id={VARIANT_PANEL_ID} className="flex flex-col gap-2">
        <label htmlFor={fieldId} className="text-sm text-ink-soft">
          Cosa vuoi cambiare?
        </label>
        <textarea
          id={fieldId}
          ref={fieldRef}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          // il limite di `DraftRequest` nel backend: oltre, il server risponderebbe 422
          maxLength={1000}
          placeholder="Sostituisci lo zucchero con il dolcificante"
        />
        <p className="text-xs text-ink-soft">
          L'AI scrive una ricetta nuova, che correggi prima di salvare. Questa resta com'è.
        </p>
        {/* secondario: il primario della vista resta «Cucina». Da solo, quindi icona e
            testo (spec T3 §2); «non ancora» col perché sotto, `busy` in volo */}
        <Button
          variant="secondary"
          shape="block"
          icon={IconSparkles}
          busy={propose.isPending}
          unavailableReason={
            prompt.trim().length < 3 ? "Scrivi cosa cambiare: bastano tre lettere." : undefined
          }
          onClick={submit}
        >
          {propose.isPending ? "Propongo…" : "Proponi la variante"}
        </Button>
        {propose.isError && (
          <Alert tone="degraded">
            L'AI non ha risposto: questa ricetta resta com'è. Riprova fra poco.
          </Alert>
        )}
        <Button variant="ghost" onClick={onClose}>
          Annulla
        </Button>
      </div>
    </Card>
  );
}
```

- [ ] **Step 4: Il legame a video**

Crea `frontend/src/features/ai-variant/OriginLink.tsx`:

```tsx
import { Link } from "react-router-dom";
import type { RecipeOrigin } from "../../domain/types";

/** Sotto il titolo di una variante, la ricetta da cui nasce (R8; Mattia: «Variante di
 * «…»» che porta all'originale). Eliminata, lo dice come l'Anagrafica dice le ricette
 * eliminate — «(eliminata)» — e porta lo stesso al suo dettaglio, cioè alla lapide con
 * «Ripristina» (R10). Alto 44 px come «Apri l'originale»; `break-words` perché un titolo
 * lungo vada a capo invece di allargare la pagina a 375 px. */
export function OriginLink({ origin }: { origin: RecipeOrigin }) {
  return (
    <Link
      to={`/ricette/${origin.id}`}
      className="inline-flex min-h-11 max-w-full items-center text-sm font-medium break-words text-brand"
    >
      {`Variante di «${origin.title}»${origin.archived ? " (eliminata)" : ""}`}
    </Link>
  );
}
```

- [ ] **Step 5: Il modulo della variante**

Crea `frontend/src/features/ai-variant/RecipeVariantScreen.tsx`:

```tsx
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Navigate, useLocation, useNavigate, useParams } from "react-router-dom";
import { createRecipe } from "../recipes/api";
import { Screen } from "../../components/ui/Screen";
import { useNotice } from "../../components/ui/noticeContext";
import { RecipeForm } from "../recipe-form/RecipeForm";
import { EMPTY_FORM, applyDraft } from "../recipe-form/formModel";
import { sourceRef } from "../ai-draft/sourceRef";
import { readVariantState, type VariantState } from "./variantState";

function VariantForm({ recipeId, state }: { recipeId: string; state: VariantState }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const notice = useNotice();
  // Una volta sola, dalla proposta: la categoria parte da quella dell'originale (la
  // proposta non ne ha, e una variante della torta resta un dolce), il resto da
  // `applyDraft` come nella bozza AI.
  const [values, setValues] = useState(() =>
    applyDraft({ ...EMPTY_FORM, category: state.originCategory }, state.draft)
  );

  return (
    <Screen
      title="Nuova variante"
      subtitle={`Variante di «${state.originTitle}»`}
      back={{ to: `/ricette/${recipeId}`, label: "Ricetta" }}
    >
      <p className="pb-3 text-sm break-words text-ink-soft">
        {`Hai chiesto: «${state.prompt}». Correggi quel che serve: salvando nasce una ricetta nuova, e l'originale resta com'è.`}
      </p>
      <RecipeForm
        values={values}
        onChange={setValues}
        // la foto e i tempi non passano di qui: li copia il server dall'originale, che
        // `derived_from_id` gli indica (Mattia, 2026-10-13; il modulo non li ha, R10 §7)
        save={(body) =>
          createRecipe({
            ...body,
            source: "ai",
            source_ref: sourceRef(state.prompt),
            derived_from_id: recipeId,
          })
        }
        onSaved={(saved) => {
          void queryClient.invalidateQueries({ queryKey: ["recipes"] });
          // «Salvata.» dall'avviso unico, prima di lasciare il modulo: `NoticeProvider`
          // sta sopra il router, e l'avviso resta passando al dettaglio
          notice({ text: "Salvata." });
          // `replace`: il dettaglio della variante prende il posto del modulo, e indietro
          // si torna all'originale, non a un modulo già salvato
          navigate(`/ricette/${saved.id}`, { replace: true });
        }}
        submitLabel="Salva la variante"
      />
    </Screen>
  );
}

/** `/ricette/:id/variante`: il modulo di una variante (R8), compilato dalla proposta che il
 * pannello del dettaglio ha messo nella cronologia. Salvando nasce una ricetta nuova col
 * legame all'originale (`derived_from_id`); l'originale non si tocca. Senza proposta — un
 * indirizzo scritto a mano — si torna all'originale, dove c'è il tasto: mai un vicolo
 * cieco. */
export function RecipeVariantScreen() {
  const { id = "" } = useParams();
  const location = useLocation();
  const state = readVariantState(location.state);
  if (state === null) return <Navigate to={`/ricette/${id}`} replace />;
  return <VariantForm recipeId={id} state={state} />;
}
```

- [ ] **Step 6: Il dettaglio**

In `frontend/src/features/cooking/RecipeDetailScreen.tsx` (leggilo com'è sul ramo: il piano 7 può averlo toccato intorno a `CookSheet`):

1. Nell'import da `"../../components/ui/icons"` aggiungi `IconSparkles`. Fra gli import aggiungi:
   ```tsx
   import { OriginLink } from "../ai-variant/OriginLink";
   import { VariantPrompt } from "../ai-variant/VariantPrompt";
   import { VARIANT_PANEL_ID } from "../ai-variant/variantState";
   ```
2. La riga di apertura del componente
   ```tsx
   export function RecipeDetailScreen() {
     const { id = "" } = useParams();
   ```
   diventa:
   ```tsx
   /** `key={id}`: da una variante alla sua originale (R8) la rotta resta la stessa e cambia
    * solo `:id`. Senza la chiave React terrebbe lo stato della ricetta di prima — le porzioni
    * scelte, il foglio della cottura o il pannello della variante aperti — e lo applicherebbe
    * all'altra. */
   export function RecipeDetailScreen() {
     const { id = "" } = useParams();
     return <RecipeDetailView key={id} id={id} />;
   }

   function RecipeDetailView({ id }: { id: string }) {
   ```
   Il resto del corpo resta com'è (usa già `id`).
3. Subito dopo la riga `const [servings, setServings] = useState<number | null>(null);`, aggiungi:
   ```tsx
     // R8: il pannello di «Modifica con AI», e il tasto che lo apre. Chiuso il pannello il
     // fuoco torna sul tasto: il pannello si smonta col campo che aveva il fuoco.
     const [variantOpen, setVariantOpen] = useState(false);
     const variantButtonRef = useRef<HTMLButtonElement>(null);
   ```
4. Nel gruppo `<IconToolbar label="Azioni della ricetta">`, subito dopo il `</Link>` di «Modifica» e prima del `<Button` di «Elimina», aggiungi:
   ```tsx
            {/* R8: fra le due azioni rare, perché è una modifica; la scintilla è l'icona di
                «scrivi con l'AI» (spec T3 §3.3) */}
            <Button
              ref={variantButtonRef}
              variant="ghost"
              icon={IconSparkles}
              label="Modifica con AI"
              aria-expanded={variantOpen}
              aria-controls={VARIANT_PANEL_ID}
              onClick={() => setVariantOpen((open) => !open)}
            />
   ```
5. Subito dopo il `</div>` che chiude la riga del titolo (il `<div className="flex items-start gap-2 pt-3">` che contiene `<h1>` e `<IconToolbar>`), e prima del blocco della categoria e del costo, aggiungi:
   ```tsx
         {/* R8, Mattia: nella variante, sotto il titolo, la ricetta da cui nasce */}
         {recipe.derived_from && <OriginLink origin={recipe.derived_from} />}

         {variantOpen && (
           <VariantPrompt
             recipe={recipe}
             onClose={() => {
               setVariantOpen(false);
               variantButtonRef.current?.focus();
             }}
           />
         )}
   ```

La lapide di una ricetta eliminata (il ramo `if (recipe.archived_at !== null)`) non cambia: non ha il gruppo di icone, quindi nemmeno il tasto.

- [ ] **Step 7: La rotta**

In `frontend/src/App.tsx` (leggilo com'è sul ramo: S3 l'ha toccato), aggiungi l'import

```tsx
import { RecipeVariantScreen } from "./features/ai-variant/RecipeVariantScreen";
```

e subito dopo la riga `<Route path="/ricette/:id/modifica" element={<RecipeEditScreen />} />` aggiungi:

```tsx
              <Route path="/ricette/:id/variante" element={<RecipeVariantScreen />} />
```

- [ ] **Step 8: Passano, e tutto il resto anche**

Run (da `<worktree>/frontend`): `npx vitest run src/features/ai-variant src/features/cooking src/features/ai-draft src/features/recipe-form && npm run typecheck && npm run lint`
Expected: PASS — i 9 test di `variantState.test.ts` e gli 11 di `RecipeVariant.test.tsx`; `RecipeDetailActions.test.tsx` (««Modifica» ed «Elimina» sono icone in un gruppo accanto al titolo») passa com'è, perché cerca per nome. Typecheck e lint puliti.

Poi la suite intera: `npx vitest run`. Expected: tutto verde.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/features/ai-variant/ frontend/src/features/cooking/RecipeDetailScreen.tsx frontend/src/App.tsx
git commit -m "feat(ricette): R8, «Modifica con AI» nel dettaglio, il modulo della variante e «Variante di «…»»"
```

---

### Task 8: Nel browser vero — il giro intero, e lo stile a 375 px nei due temi

**Files:**
- Create: `frontend/e2e/variante-ai.spec.ts`
- Modify: `frontend/e2e/style.spec.ts` (due prove in fondo al file)

**Interfaces:**
- Consumes: tutto il resto; in `style.spec.ts` gli helper che il file ha già — `ricettaDiProva`, `fermo`, `testiIlleggibili`, `contrastoAVideo`, `tokenDelTema`, `tokenDelTemaScuro`, `senzaScorrimentoLaterale` — **letti com'è sul ramo** (i piani prima di questo li possono aver toccato: se uno ha cambiato nome o firma, adatta le chiamate qui sotto e scrivilo nel report).

- [ ] **Step 1: Il giro intero**

Crea `frontend/e2e/variante-ai.spec.ts`:

```ts
import { expect, test, type Page } from "@playwright/test";
import type { RecipeDraft } from "../src/domain/types.ts";

/**
 * R8 nel browser vero, a 375×812: dal dettaglio di una ricetta, «Modifica con AI»; l'AI
 * dello stack e2e non ha la chiave, e il server risponde 503 da sé — il guasto vero, che
 * lascia sull'originale; poi una proposta, il modulo, il salvataggio vero, il legame sotto
 * il titolo, l'originale intatta, e la lapide quando l'originale è eliminata.
 *
 * IL LIMITE, detto chiaro: la proposta riuscita la costruisce il test con `page.route`,
 * perché il modello qui non si chiama (la prima lezione di CLAUDE.md: è un oggetto fatto
 * dal test). Non prova cosa l'AI risponde — lo provano i finti di `test_ai_recipes.py` —
 * ma il resto è vero: lo schermo, il salvataggio con `derived_from_id`, la risposta del
 * server col legame. La ricetta si crea con `page.request`; in fondo le due ricette si
 * eliminano (non esiste una cancellazione vera, R10) dentro un `finally`.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

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

test("R8: la variante nasce dal dettaglio col legame all'originale, che resta com'è", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();

  const cetriolo = await ingrediente(page, "cetriolo");
  const anguria = await ingrediente(page, "anguria");
  const titolo = `Insalata e2e ${Date.now()}`;
  const creata = await page.request.post("/api/v1/recipes", {
    data: {
      title: titolo, instructions: "1. Taglia.\n2. Condisci.", servings: 2, source: "manual",
      source_ref: null, cost: 1,
      ingredients: [
        { ingredient_id: cetriolo.id, role: "primary", quantity_text: "1" },
        { ingredient_id: anguria.id, role: "primary", quantity_text: "300 g" },
      ],
    },
  });
  expect(creata.ok()).toBe(true);
  const originaleId = ((await creata.json()) as { id: string }).id;
  let varianteId: string | null = null;

  try {
    await page.goto(`/ricette/${originaleId}`);
    await page
      .getByRole("toolbar", { name: "Azioni della ricetta" })
      .getByRole("button", { name: "Modifica con AI", exact: true })
      .click();
    await page.getByLabel("Cosa vuoi cambiare?").fill("senza anguria, con più cetriolo");

    // 1. il guasto vero: lo stack non ha la chiave dell'AI, e si resta sull'originale
    await page.getByRole("button", { name: "Proponi la variante", exact: true }).click();
    await expect(
      page.getByText("L'AI non ha risposto: questa ricetta resta com'è. Riprova fra poco.", { exact: true })
    ).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`/ricette/${originaleId}$`));
    await expect(page.getByRole("heading", { level: 1, name: titolo })).toBeVisible();
    await nonScorreDiLato(page, "il dettaglio col pannello della variante");

    // 2. la proposta, costruita qui: solo ingredienti del seme, così non nasce niente in anagrafica
    const titoloVariante = `${titolo} senza anguria`;
    await page.route(`**/api/v1/recipes/${originaleId}/ai-variant`, (route) =>
      route.fulfill({
        json: {
          title: titoloVariante, description: null,
          instructions: "1. Taglia i cetrioli.\n2. Condisci.", servings: 2, cost: 1,
          ingredients: [
            {
              raw_name: "cetriolo", role: "primary", quantity_text: "2", ingredient_id: cetriolo.id,
              matched_name: "cetriolo", confident: true, proposed_category: null,
            },
          ],
        } satisfies RecipeDraft,
      })
    );
    await page.getByRole("button", { name: "Proponi la variante", exact: true }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Nuova variante" })).toBeVisible();
    await expect(page.getByText(`Variante di «${titolo}»`, { exact: true })).toBeVisible();
    await expect(page.getByLabel("Titolo", { exact: true })).toHaveValue(titoloVariante);
    await nonScorreDiLato(page, "il modulo della variante");

    // 3. il salvataggio vero: la variante, col legame sotto il titolo
    await page.getByRole("button", { name: "Salva la variante", exact: true }).click();
    await expect(page.getByRole("heading", { level: 1, name: titoloVariante })).toBeVisible();
    await expect(page).toHaveURL(/\/ricette\/[0-9a-f-]{36}$/);
    varianteId = new URL(page.url()).pathname.split("/").pop()!;
    expect(varianteId).not.toBe(originaleId);
    const legame = page.getByRole("link", { name: `Variante di «${titolo}»`, exact: true });
    await expect(legame).toBeVisible();
    expect((await legame.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await nonScorreDiLato(page, "il dettaglio della variante");

    // 4. il legame porta all'originale, che è com'era e non ne ha uno suo
    await legame.click();
    await expect(page).toHaveURL(new RegExp(`/ricette/${originaleId}$`));
    await expect(page.getByRole("heading", { level: 1, name: titolo })).toBeVisible();
    await expect(page.getByRole("link", { name: /^Variante di/ })).toHaveCount(0);
    const letta = (await (await page.request.get(`/api/v1/recipes/${originaleId}`)).json()) as {
      title: string;
      derived_from: unknown;
      ingredients: { ingredient_name: string; quantity_text: string | null }[];
    };
    expect(letta.title).toBe(titolo);
    expect(letta.derived_from).toBeNull();
    expect(letta.ingredients.map((r) => [r.ingredient_name, r.quantity_text]).sort()).toEqual([
      ["anguria", "300 g"],
      ["cetriolo", "1"],
    ]);

    // 5. l'originale eliminata: il legame lo dice, e porta alla lapide
    const via = await page.request.patch(`/api/v1/recipes/${originaleId}`, { data: { archived: true } });
    expect(via.ok()).toBe(true);
    await page.goto(`/ricette/${varianteId}`);
    await page.getByRole("link", { name: `Variante di «${titolo}» (eliminata)`, exact: true }).click();
    await expect(page.getByText("Questa ricetta è stata eliminata.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Ripristina" })).toBeVisible();
  } finally {
    for (const id of [varianteId, originaleId]) {
      if (!id) continue;
      const risposta = await page.request.patch(`/api/v1/recipes/${id}`, { data: { archived: true } });
      expect.soft(risposta.ok(), `pulizia: la ricetta ${id} non si è eliminata`).toBe(true);
    }
  }
});
```

La copia della foto e dei tempi (decisioni 19 e 20) **non** ha una prova e2e, e non è una dimenticanza: nello stack e2e un'originale non può avere una foto né dei tempi — `POST /recipes` non li accetta dal client, e il seme non ne ha — e a video non c'è niente di nuovo: il dettaglio e il ricettario mostrano già foto e tempi di ogni ricetta che li ha. La copia la prova `test_la_variante_parte_con_la_foto_e_i_tempi_dell_originale` (Task 2) sul Postgres vero, e che il modulo non li mandi `RecipeVariant.test.tsx` (Task 7).

- [ ] **Step 2: Lo stile**

In fondo a `frontend/e2e/style.spec.ts` aggiungi (il `beforeEach` in cima al file fa già l'accesso; `ricettaDiProva` aspetta la barra delle schede):

```ts
test("Modifica con AI a 375px: il guasto è ambra, e il pannello e il modulo della variante si leggono nei due temi", async ({
  page,
}) => {
  const ricetta = await ricettaDiProva(page);
  try {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(`/ricette/${ricetta.id}`);
    const tasto = page
      .getByRole("toolbar", { name: "Azioni della ricetta" })
      .getByRole("button", { name: "Modifica con AI", exact: true });
    const scatola = (await tasto.boundingBox())!;
    expect(scatola.width).toBeGreaterThanOrEqual(44);
    expect(scatola.height).toBeGreaterThanOrEqual(44);

    await tasto.click();
    await page.getByLabel("Cosa vuoi cambiare?").fill("senza scamorza");
    // lo stack e2e non ha la chiave dell'AI: il server risponde 503 da sé, senza rete
    await page.getByRole("button", { name: "Proponi la variante", exact: true }).click();
    const guasto = page.getByText(
      "L'AI non ha risposto: questa ricetta resta com'è. Riprova fra poco.",
      { exact: true }
    );
    await expect(guasto).toBeVisible();
    for (const tema of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: tema });
      await fermo(page);
      const misura = await contrastoAVideo(guasto);
      expect(misura.colore, `il guasto della variante non è ambra, tema ${tema}`).toBe(
        tema === "light" ? tokenDelTema("low") : tokenDelTemaScuro("low")
      );
      expect(await testiIlleggibili(page), `dettaglio col pannello della variante, tema ${tema}`).toEqual([]);
    }
    await page.emulateMedia({ colorScheme: "light" });
    await senzaScorrimentoLaterale(page, "il dettaglio col pannello della variante");

    // il modulo della variante: la proposta la costruisce il test (il modello qui non si chiama)
    await page.route(`**/api/v1/recipes/${ricetta.id}/ai-variant`, (route) =>
      route.fulfill({
        json: {
          title: `${ricetta.titolo} senza scamorza`, description: null,
          instructions: "1. Pulisci le verdure.\n2. Cuoci il farro.", servings: 2, cost: 2,
          ingredients: [
            {
              raw_name: "farro", role: "primary", quantity_text: "160 g", ingredient_id: ricetta.ids.farro,
              matched_name: "farro", confident: true, proposed_category: null,
            },
          ],
        } satisfies RecipeDraft,
      })
    );
    await page.getByRole("button", { name: "Proponi la variante", exact: true }).click();
    await expect(page.getByRole("heading", { level: 1, name: "Nuova variante" })).toBeVisible();
    for (const tema of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: tema });
      await fermo(page);
      expect(await testiIlleggibili(page), `modulo della variante, tema ${tema}`).toEqual([]);
    }
    await page.emulateMedia({ colorScheme: "light" });
    await senzaScorrimentoLaterale(page, "il modulo della variante");
  } finally {
    await ricetta.pulisci();
  }
});

test("il legame «Variante di «…»» sta sotto il titolo, è un bersaglio da pollice e si legge nei due temi", async ({
  page,
}) => {
  const ricetta = await ricettaDiProva(page);
  let varianteId: string | null = null;
  try {
    const titoloVariante = `${ricetta.titolo} variante`;
    const creata = await page.request.post("/api/v1/recipes", {
      data: {
        title: titoloVariante, instructions: "1. Cuoci il farro.", servings: 2,
        source: "ai", source_ref: "prompt: prova e2e", derived_from_id: ricetta.id,
        ingredients: [{ ingredient_id: ricetta.ids.farro, role: "primary", quantity_text: "160 g" }],
      },
    });
    expect(creata.ok()).toBe(true);
    varianteId = ((await creata.json()) as { id: string }).id;

    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(`/ricette/${varianteId}`);
    const titolo = page.getByRole("heading", { level: 1, name: titoloVariante });
    const legame = page.getByRole("link", { name: `Variante di «${ricetta.titolo}»`, exact: true });
    await expect(legame).toBeVisible();
    const sTitolo = (await titolo.boundingBox())!;
    const sLegame = (await legame.boundingBox())!;
    expect(sLegame.y, "il legame sta sotto il titolo").toBeGreaterThanOrEqual(sTitolo.y + sTitolo.height - 1);
    expect(sLegame.height).toBeGreaterThanOrEqual(44);
    for (const tema of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: tema });
      await fermo(page);
      expect(await testiIlleggibili(page), `dettaglio di una variante, tema ${tema}`).toEqual([]);
    }
    await page.emulateMedia({ colorScheme: "light" });
    await senzaScorrimentoLaterale(page, "il dettaglio di una variante");

    // eliminata l'originale, il legame lo dice
    const via = await page.request.patch(`/api/v1/recipes/${ricetta.id}`, { data: { archived: true } });
    expect(via.ok()).toBe(true);
    await page.reload();
    await expect(
      page.getByRole("link", { name: `Variante di «${ricetta.titolo}» (eliminata)`, exact: true })
    ).toBeVisible();
  } finally {
    if (varianteId) {
      const risposta = await page.request.patch(`/api/v1/recipes/${varianteId}`, {
        data: { archived: true },
      });
      expect.soft(risposta.ok(), `pulizia: la variante ${varianteId} non si è eliminata`).toBe(true);
    }
    await ricetta.pulisci();
  }
});
```

Se `RecipeDraft` non è già fra i tipi importati in testa a `style.spec.ts` (su `master` c'è: `import type { ImportTerm, Ingredient, RecipeDraft } from "../src/domain/types.ts";`), aggiungilo a quell'import.

- [ ] **Step 3: Il type check delle prove**

Run (da `<worktree>/frontend`): `npm run typecheck && npm run lint`
Expected: puliti (le prove le compila `tsconfig.node.json`).

- [ ] **Step 4: L'e2e intera**

Dalla radice di `<worktree>`, con i comandi delle Global Constraints: `cp .env.example .env`, `up -d --build --wait` (il backend migra da sé alla `0014`), il seme `--con-ricette`, poi `(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)`.
Expected: tutte verdi, comprese le tre nuove. **Annota il numero** delle prove (`N_e2e`). Poi `down -v` e `rm .env`, sempre, anche se qualcosa è fallito.

Se una prova nuova fallisce per un motivo di stile (un testo sotto 4,5:1, una pagina che scorre di lato), la correzione sta nei componenti del Task 7 (classi e token esistenti), mai nella prova.

- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/variante-ai.spec.ts frontend/e2e/style.spec.ts
git commit -m "test(e2e): R8 nel browser vero — il guasto ambra, la proposta, il salvataggio col legame, la lapide"
```

---

### Task 9: I documenti

**Files:**
- Modify: `docs/prossimi-passi.md`
- Modify: `next-steps.md`

Leggi prima i due file com'è sul ramo: i piani prima di questo li hanno aggiornati.

- [ ] **Step 1: `docs/prossimi-passi.md`**

1. Il titolo `## R8. Modifica con AI **[D]**` diventa `## R8. Modifica con AI **[FATTO <data di oggi> — spec: `docs/superpowers/specs/2026-10-09-r8-modifica-con-ai-design.md`, sul ramo `night/r8-modifica-con-ai`, non ancora in produzione]**`.
2. La riga `TBD: se la nuova ricetta tiene un legame con quella da cui nasce, e se si vede.` diventa:
   ```markdown
   **Deciso da Mattia il 2026-10-09:** il legame si tiene e si vede — nella nuova, sotto il
   titolo, «Variante di «…»» che porta all'originale; nell'originale niente in più. La
   proposta dell'AI apre il modulo già compilato; se l'AI non risponde si resta
   sull'originale con un avviso ambra.

   **Fatto** il <data di oggi>, sul ramo `night/r8-modifica-con-ai`: nel dettaglio, fra
   «Modifica» ed «Elimina», l'icona «Modifica con AI» apre sotto il titolo un pannello con
   «Cosa vuoi cambiare?» e «Proponi la variante»; la proposta (`POST
   /recipes/{id}/ai-variant`, `draft_variant` in `services/ai_recipes.py`, il prompt della
   bozza esteso con le regole della variante, sezione `recipe_variant` in `llm_calls`) apre
   «Nuova variante» (`/ricette/:id/variante`) col modulo di sempre e la categoria
   dell'originale; «Salva la variante» crea una ricetta nuova con `derived_from_id`
   (colonna nuova, migrazione `0014`, `ON DELETE SET NULL`), e la variante mostra sotto il
   titolo «Variante di «…»», con «(eliminata)» se l'originale è eliminata (porta alla
   lapide). Le righe passano dall'imbuto: la proposta non aggancia e non propone un non
   alimentare. L'annullamento di una decisione dell'import, che rifà l'originale, tiene
   gli id delle varianti nel `payload` come le cotture (`variant_recipe_ids`). Un'originale
   sparita al salvataggio non ferma la variante: nasce senza legame.

   **Deciso da Mattia il 2026-10-13:** la variante parte con la foto e i tempi
   dell'originale («Sì, copiali»). Li copia il server al salvataggio (`variant_copy` in
   `app/repositories/recipes.py`), perché il modulo della ricetta non ha campi per la foto
   e per i tempi (R10 §7); `PUT` li lascia com'erano. Oggi nessuno schermo li corregge, per
   nessuna ricetta: è un'idea in `next-steps.md`.

   **Le scelte del piano che Mattia può voler rivedere:** il tasto fra le icone accanto al
   titolo; il prompt in un pannello dentro il dettaglio (e non in uno schermo suo); la
   categoria che parte da quella dell'originale; «(eliminata)» nel legame.

   **Da provare sul telefono:** il pannello con la tastiera aperta (il campo resta in
   vista?), una variante vera col modello vero — la notte ha provato solo coi finti, quindi
   la qualità del ribilanciamento («sostituisci lo zucchero con dolcificante») non è
   misurata — e il giro indietro: variante → originale → indietro.
   ```
3. Nel paragrafo che comincia con «`call_site` è oggi `TERM_DECISION`, `TERM_COLLAPSE`, `RECIPE_DRAFT`» (sotto T2; leggilo com'è sul ramo: S12 può avervi aggiunto `INGREDIENT_EMOJI`), aggiungi alla fine dell'elenco delle sezioni: «e — dal <data di oggi>, con R8 — `RECIPE_VARIANT`».

- [ ] **Step 2: `next-steps.md`**

1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte)_`.
2. Togli da `## In corso` la riga di R8 messa nella Preparazione (se resta vuota, rimetti `_(niente)_`).
3. In cima a «Fatti (recenti)» aggiungi:
   ```markdown
   - [fatto] <data di oggi> · R8, modifica con AI che salva una ricetta nuova: «Modifica con AI» nel dettaglio, la proposta nel modulo («Nuova variante»), «Salva la variante» con `derived_from_id` (migrazione 0014) e «Variante di «…»» sotto il titolo; la variante parte con la foto e i tempi dell'originale, copiati dal server (deciso da Mattia il 2026-10-13); sezione `recipe_variant` nelle spese [R8] → branch night/r8-modifica-con-ai (da revisionare)
   ```
4. In cima a «Da fare a mano (solo Mattia)» aggiungi:
   ```markdown
   - [tbd] P3 · Prove di R8: una variante vera col modello vero (la notte ha usato solo i finti: il ribilanciamento non è misurato), il pannello con la tastiera aperta al telefono, il giro variante → originale → indietro [R8]
   ```
5. In «Idee» aggiungi:
   ```markdown
   - [idea] P3 · Le spese dell'AI (H1) danno un nome a ogni sezione: `recipe_variant` (R8) e `ingredient_emoji` (S12) sono nate su rami a parte, controllare al merge che abbiano il loro [R8, H1]
   - [idea] P3 · Dal modulo della variante non si ripropone: per una richiesta diversa si torna all'originale e si riapre il pannello [R8]
   - [idea] P3 · Correggere la foto e i tempi di una ricetta: il modulo non li ha (R10 §7), e una variante li copia dall'originale (deciso da Mattia il 2026-10-13), quindi una variante «senza forno» tiene i minuti di cottura della torta finché non c'è un modo di cambiarli [R8, R10]
   ```
6. Se nella notte sono emerse altre cose da fare fuori da questo piano, aggiungile come `idea` o `tbd` nella sezione giusta, con la voce di `docs/prossimi-passi.md` fra parentesi quadre.

- [ ] **Step 3: Commit**

```bash
git add docs/prossimi-passi.md next-steps.md
git commit -m "docs: R8 fatto sul ramo — modifica con AI, la variante col legame all'originale"
```

---

### Task 10: La verifica finale

Niente di nuovo da scrivere: si prova tutto, dal worktree, com'è sul ramo.

- [ ] **Step 1: Il frontend**

Da `<worktree>/frontend`:

```bash
npx vitest run
npm run typecheck
npx tsc -b --force
npm run lint
npm run build
```

Expected: vitest tutto verde — **`N_vitest` della Preparazione più 22**, cioè 2 (Task 6, `sourceRef.test.ts`) + 9 (`variantState.test.ts`) + 11 (`RecipeVariant.test.tsx`), in **`N_file` + 3** file; se il numero differisce, scrivi nel report da dove viene la differenza. Typecheck, lint e build puliti. `npx tsc -b --force` perché `node_modules` è condiviso col checkout principale, e con lui il `tsbuildinfo`: `--force` compila davvero tutto.

- [ ] **Step 2: Il backend**

Da `<worktree>/backend`:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_r8 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Expected: tutto verde, **`N_pytest` + 19**: 1 (Task 1) + 6 (Task 2) + 5 (Task 3) + 5 (Task 4) + 2 (Task 5).

- [ ] **Step 3: I grep**

Dalla radice del worktree:

```bash
grep -rn "emerald\|neutral-" frontend/src
git diff --name-only night/rimetti-in-lista -- backend/alembic/versions/
grep -rn "RECIPE_VARIANT" backend/app
grep -rn "Modifica con AI\|Salva la variante\|Variante di «" frontend/src --include=*.tsx | grep -v "\.test\."
```

Expected: vuoto; solo `backend/alembic/versions/0014_varianti_ricette.py`; la definizione in `llm.py` e i due usi in `ai_recipes.py`; le parole in `RecipeDetailScreen.tsx`, `RecipeVariantScreen.tsx` e `OriginLink.tsx`.

- [ ] **Step 4: L'e2e intera**

Con i comandi delle Global Constraints, su uno stack ricreato da zero (`down -v` prima dell'`up`, se ne era rimasto uno di questo ramo). Expected: tutti verdi, `N_e2e` del Task 8. Poi `down -v` e `rm .env`, sempre.

- [ ] **Step 5: Il database dei test**

Dopo l'ultimo pytest:

```bash
docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_r8 WITH (FORCE)'
```

- [ ] **Step 6: Il report**

Nel report della notte (`docs/night-reports/<data>.md`, sul ramo; se il file c'è già, aggiungi una sezione per questo piano), per questo piano: il ramo e da dove parte; i conti veri (vitest, pytest, e2e) contro quelli della Preparazione; la migrazione `0014` (cosa aggiunge, e che parte da sé all'avvio del backend); cosa hanno trovato i `diff --stat` della Preparazione sui file già toccati dai piani prima; le migrazioni di test fatte oltre al `derived_from: null` (dovrebbero essere zero); le decisioni prese in autonomia; la copia della foto e dei tempi dell'originale (deciso da Mattia il 2026-10-13, costruita nel server: non è una domanda aperta), con l'idea annotata per poterli correggere. Commit del report:

```bash
git add docs/night-reports/
git commit -m "docs: report della notte, R8"
```

Niente push, niente merge, niente deploy.

## Dopo il deploy (solo Mattia)

- **Nessun comando da lanciare.** La migrazione `0014` aggiunge una colonna annullabile, senza passo dati, e parte da sé all'avvio del backend (come ogni migrazione: `docker-entrypoint.sh`). Il deploy resta quello di sempre: `docker compose -f docker-compose.prod.yml up -d --build --wait`, mai senza `-f`.
- **Da guardare dopo:** una variante vera, col modello vero, su una ricetta importata lunga (il tetto di 4000 token regge?) e su «sostituisci lo zucchero con dolcificante» (ribilancia davvero?); la riga `recipe_variant` in `llm_calls` col suo costo; e che la variante di una ricetta importata mostri la foto dell'originale nel dettaglio e nel ricettario (il seme non ha foto: nella notte l'ha provata solo pytest).
