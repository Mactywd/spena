# Le rifiniture del ricettario e del foglio della cottura: lo zero a piscina piena, la categoria che il menu non ha, l'aggiornamento fallito, il «Riprova» che porta via, le confezioni che il foglio non distingue — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** due idee P3, sei cose dette male e nessun vicolo cieco.
- **Nel ricettario:**
  - con la piscina delle parole piena e un filtro che scarta tutti i candidati, lo zero dice che si è guardato solo un pezzo;
  - una categoria ricordata che il ricettario non elenca si vede scelta nel menu;
  - una rilettura fallita lascia a video le righe e dice che l'aggiornamento non è riuscito;
  - il «Riprova» di un'eliminazione fallita, toccato fuori dal dettaglio, non cambia pagina.
- **Nel foglio della cottura:**
  - una riga cambiata lo dice accanto allo stato di partenza;
  - ogni confezione dice la sua scadenza;
  - due confezioni uguali in tutto hanno nomi diversi per chi ascolta.

**Architecture:**
- **Lo zero.** Il server lo dice già. `search_recipes` mette `total_is_lower_bound` quando una graduatoria ha riempito `CANDIDATE_POOL`, prima dei filtri, quindi anche quando i filtri lasciano zero risultati. La rotta manda allora `X-Total-Count-Lower-Bound: 1` con `X-Total-Count: 0`. È il frontend che lo ignora: `resultsLabel` risponde «Nessuna ricetta» a zero prima di guardare `lowerBound`, ed `EmptyState` non lo riceve. Il backend non cambia: un test fissa il contratto su cui il frontend ora conta.
- **La categoria.** `RecipeFiltersPanel` mette fra le voci del menu la categoria scelta quando le categorie arrivate non la contengono, e mostra il menu anche se le categorie non sono arrivate ma una categoria è ricordata.
- **L'aggiornamento.** `isLoadingError` (nessun dato) mostra l'errore pieno, come oggi. `isRefetchError` (dati già a video, e non l'errore di una pagina dopo) tiene l'elenco e mette sopra un `ErrorState` con «Riprova».
- **Il «Riprova».** `useArchiveRecipe` porta al ricettario solo se chi l'ha chiamato è ancora montato e ancora sul dettaglio di quella ricetta (`/ricette/<id>`).
- **Il foglio.** `CookSheet` scrive la transizione scelta accanto allo stato di partenza, aggiunge la scadenza con `expiryText` della Dispensa alla riga e al nome dei controlli, e numera nel nome accessibile le confezioni che restano uguali.

**Tech Stack:** FastAPI e pytest su Postgres vero (un test solo); React 19, TanStack Query 5, Vitest + Testing Library, Playwright.

**Spec:** le idee P3 di `next-steps.md` «Il ricettario, quattro cose dette male» [T3 Consegna 4] e «Il foglio della cottura dice poco di ogni confezione» [T3 Consegna 5, T3 esito del giro]. Il ragionamento in `docs/prossimi-passi.md` §T3. Le regole a video: `docs/superpowers/specs/2026-09-28-ridisegno-design.md` (§4.4 il foglio, §4.5 il ricettario). Il limite della piscina è scritto in `backend/app/services/recipe_search.py` sopra `_containing_all` (R-A).

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/ricettario-rifiniture`, ramo `night/ricettario-rifiniture`. Il ramo si crea **da `night/ricetta-pasto-lucchetto`**, se c'è ed è finito (Preparazione). Quel piano cambia `frontend/src/features/recipes/useArchiveRecipe.ts` (`restoreToBook`), che il Task 5 tocca. Se non c'è o è bloccato, il ramo si crea da `master` e **il Task 5 non si fa**. Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì. **Nessun push, nessun merge, nessun deploy. Mai `git stash`. Niente letture o scritture sulla produzione, e mai il `.env` del checkout principale.**
- **Il carico sulla macchina**: al massimo 6 thread e 8 GB (Mattia, 2026-11-22). Le suite intere girano dentro `systemd-run --user --scope -p MemoryMax=8G -p CPUQuota=600% …`, mai due insieme. Vitest gira con `--maxWorkers=4` (un file solo: `--maxWorkers=1`), pytest senza parallelismo.
- **Backend su Postgres vero**: `spena-db-1` (porta 5433), con il database `spena_test_ricettario_rifiniture`. Mai `docker compose up` dal worktree. Si usa il `.venv` del checkout principale. Il comando di pytest, da `<worktree>/backend`:
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_ricettario_rifiniture \
    PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
- **Il backend non cambia**: un test nuovo, nessun codice, nessuna migrazione.
- **Il type check è `npm run typecheck`**, mai `tsc --noEmit`. Controlli del frontend, da `<worktree>/frontend`: `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`. Nei test dei componenti si usa `createTestQueryClient`.
- **Colore**: solo i token di `frontend/src/index.css`, **nessun token nuovo**. Le coppie nuove a video sono `brand`, `expiry` e `ink-soft` su `card`, già in `src/theme.test.ts`. `grep -rn "emerald\|neutral-" frontend/src` resta vuoto. Ogni testo sta sopra 4,5:1 nei due temi, bersagli alti almeno 44 px, e a 375 px niente scorre di lato.
- **Nessun numero del backend copiato nel frontend**: `CANDIDATE_POOL` (100) non compare nelle frasi. Una costante ricopiata si scolla al primo cambio.
- Le parole a video **si copiano esatte** da questo piano (fra «»). Gli identificatori in inglese, i commenti in italiano.
- **I test di oggi si cambiano solo dove il piano lo dice**: nessuno. `resultsLabel(0, false)` resta «Nessuna ricetta», e «senza categorie nel ricettario il filtro non compare» resta vero quando non c'è una categoria ricordata.
- **e2e** sullo stack `spena-e2e`, con i comandi delle Global Constraints di `docs/superpowers/plans/2026-11-18-pasti-correzioni.md`: il `.env` copiato da `.env.example` e cancellato alla fine, `-p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml` in ogni comando, il seme con le ricette e le due righe della fixture CIQUAL, e sempre `down -v` e `rm .env`.
- Nessuna dipendenza nuova.

## Review Focus

1. **Lo zero a piscina piena**: «Nessuna fra le più vicine», nel pannello e come titolo del vuoto, e la frase in più. Uno zero senza piscina piena dice «Nessuna ricetta» come oggi. Task 1 e 2.
2. **Una categoria ricordata che non c'è più, o con le categorie non arrivate**: il menu la mostra scelta, «Filtri» la conta, e «Tutte» la toglie davvero (la richiesta dopo non ha `category`). Task 3.
3. **Una rilettura fallita con l'elenco a video** tiene le righe e dice «Non sono riuscito ad aggiornare il ricettario…» con «Riprova». Una ricerca nuova che fallisce mostra l'errore pieno, come oggi, perché la sua chiave non ha dati. Task 4.
4. **Il «Riprova» di un'eliminazione**: dal dettaglio della ricetta porta al ricettario come oggi. Dopo essere usciti, o passati al dettaglio di un'altra ricetta, resta lì, e l'avviso «Eliminata: …» con «Annulla» compare lo stesso. Task 5.
5. **Il foglio della cottura**: una riga cambiata dice «Disponibile → quasi finito», e tornando allo stato di partenza il segno sparisce. La scadenza c'è nella riga e nel nome dei controlli, e due confezioni uguali in tutto si chiamano «… · confezione 1» e «… · confezione 2». Task 6 e 7.

### Preparazione (una volta, prima del Task 1)

- [ ] **Il ramo di partenza.** Da `/home/mactyws/coding/ais/spena`:
  ```bash
  git rev-parse --verify night/ricetta-pasto-lucchetto
  git log --format=%s master..night/ricetta-pasto-lucchetto | grep -F "ricette: «Annulla» dopo il pasto eliminato"
  ```
  Poi leggi il report di quella notte (`docs/night-reports/`): la voce del lucchetto non deve essere `bloccato`. Se tutto torna, `BASE=night/ricetta-pasto-lucchetto`. Altrimenti `BASE=master`, e il Task 5 si salta. Scrivi nel report quale base hai usato e perché.
- [ ] Il worktree, con `node_modules` collegato e nessun `.env`:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/ricettario-rifiniture -b night/ricettario-rifiniture "$BASE"
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/ricettario-rifiniture/frontend/node_modules
  ```
- [ ] Il database dei test:
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_ricettario_rifiniture WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_ricettario_rifiniture'
  ```
- [ ] Le due voci di `next-steps.md` che citano questo piano passano a `in corso` (` → in corso su night/ricettario-rifiniture`), e si committa: `next-steps: le rifiniture del ricettario, in corso`.
- [ ] La linea di partenza: pytest e vitest dal worktree, tutto verde. **Annota** i numeri. Se non è verde, fermati e scrivilo nel report.

---

## Decisioni prese

1. **Lo zero si qualifica nel frontend, il server resta com'è** (Claude, su delega). Verificato il 2026-11-23: `lower_bound` in `search_recipes` si decide sulle graduatorie, prima di categoria, ingredienti e soglia, e arriva anche con `total == 0`. La rotta manda l'intestazione ogni volta che il servizio lo dice (`test_la_ricerca_manda_il_minimo_solo_a_piscina_piena`). Il Task 1 aggiunge solo la prova che lo zero filtrato resta un minimo, perché è su questo che il frontend comincia a contare.
2. **Le parole dello zero qualificato** (Claude, su delega).
   - `resultsLabel(0, true)` dà «Nessuna fra le più vicine».
   - `EmptyState`, con `totalIsLowerBound`, ha il titolo «Nessuna fra le più vicine». Il corpo è il messaggio di oggi di `emptyMessage` seguito da « Ho guardato solo le ricette più vicine a queste parole: senza parole, i filtri guardano tutto il ricettario.».
   - La seconda metà è vera. Senza parole, categoria, ingredienti e soglia vanno in SQL su tutto il ricettario (`_browse`, `_containing_all`). Ed è la via d'uscita vera: altre parole cambiano la piscina, ma non la tolgono.
   - Nessun pulsante nuovo: le parole si cancellano dal campo della ricerca, che è subito sopra.
3. **La categoria ricordata si mostra, non si scarta** (Claude, su delega: cosa si può fare non cambia, il menu dice quel che vale già). Quando la categoria scelta non è fra quelle arrivate, il menu la aggiunge in fondo, col suo nome com'è, e la mostra scelta. Il menu compare se ci sono categorie **o** una categoria scelta. Scartarla in silenzio cambierebbe i risultati senza che nessuno l'abbia chiesto. Mostrarla lascia la strada di oggi: «Tutte», o «Azzera».
4. **L'aggiornamento fallito** (Claude, su delega): un `ErrorState` sopra l'elenco con «Non sono riuscito ad aggiornare il ricettario. Le ricette qui sotto sono dell'ultimo caricamento.», «Riprova» (`refetch`) e `retrying={isRefetching}`. È la frase di «Sistema la spesa» per lo stesso caso. Il conteggio del pannello resta quello delle righe a video.
5. **Il «Riprova» guarda dove si è** (Claude, su delega: che non debba portare via è la voce stessa). `useArchiveRecipe` tiene `alive` (montato) e il `pathname` di adesso in due ref aggiornati negli effetti, non durante il render. Il `navigate("/ricette", { replace: true })` dell'`onSuccess` parte solo se `alive.current && here.current === \`/ricette/${recipe.id}\``. Nient'altro dell'`onSuccess` cambia: l'avviso «Eliminata: …» con «Annulla» e il rinfresco arrivano dovunque si sia. Il dettaglio di un'altra ricetta tiene il gancio montato, per questo non basta `alive`.
6. **Il segno di una riga cambiata** (Claude, su delega). Nella riga piccola sotto il nome, lo stato di partenza resta. Se lo stato scelto è un altro, seguono una freccia «→», nascosta a chi ascolta, e lo stato scelto in minuscolo, in `font-medium text-brand`, preceduto per chi ascolta da «diventa». Si legge «Disponibile → quasi finito · in dispensa dal 23/11/2026». Parole e non un colore solo. Una riga dove si è spuntato solo «Rimetti in lista» non ha la freccia, perché la casella spuntata si vede già.
7. **La scadenza nel foglio è quella della Dispensa** (Claude, su delega): `expiryText(item.expires_on, item.expiry)` da `frontend/src/features/pantry/expiryLabels.ts`, in fondo alla riga dopo « · », in `font-medium text-expiry` quando `item.expiry` non è `null`. La riga è già piccola, quindi niente `font-semibold` per lo scaduto. Entra anche in `itemLabel`, cioè nel nome delle tacche e della casella. `EXPIRY_TONE_TEXT` non si importa da `PantryRow.tsx`: un altro piano della stessa notte lo sposta.
8. **Due confezioni uguali in tutto** (Claude, su delega). Se due righe del foglio hanno lo stesso `itemLabel` (prodotto, marca, nota, stato, data d'ingresso e scadenza), il nome accessibile di ognuna finisce con « · confezione N», con N secondo l'ordine del foglio. A video no: non c'è niente che leghi «confezione 2» a un vasetto vero. Le due sono intercambiabili, e il numero serve solo a non avere due gruppi di tacche con lo stesso nome.
9. **In Dispensa due confezioni con la stessa data restano uguali**: la voce lo cita come confronto. Lì il nome della riga lo tocca un altro piano della stessa notte (`2026-11-23-dispensa-rifiniture.md`, `PantryRow`), quindi resta fuori (vedi Fuori scope).

## Margine di autonomia

- Liberi: i nomi interni e dei test, la forma dell'helper che numera le confezioni uguali (suggerito `distinctLabels(items: PantryItem[]): Map<string, string>`, nello stesso file di `CookSheet`).
- Fissi: le parole a video, `isLoadingError`/`isRefetchError` come criterio, la regola del percorso della decisione 5.
- **Fermati** (voce `bloccato` nel report) se il test del Task 1 fallisce: vuol dire che lo zero filtrato non arriva come minimo, e il frontend non può qualificarlo senza cambiare il backend. Quella è una decisione da prendere di giorno.

---

### Task 1: il contratto, lo zero filtrato resta un minimo

**Files:**
- Test: `backend/tests/services/test_recipe_search.py`, `backend/tests/api/test_recipes.py`

**Interfaces:**
- Consumes: `search_recipes`, `RecipeSearchPage`, `CANDIDATE_POOL` abbassato con `monkeypatch`, come `test_con_parole_la_piscina_piena_rende_il_totale_un_minimo`.

- [ ] **Step 1: I test.**
  - `test_a_piscina_piena_lo_zero_di_un_filtro_resta_un_minimo`: `CANDIDATE_POOL` a 2, tre ricette «Zuppa n» senza categoria, `search_recipes(db_session, "zuppa", category="Dolci", limit=10)`. `total == 0` e `total_is_lower_bound is True`.
  - In `test_recipes.py`, accanto a `test_la_ricerca_manda_il_minimo_solo_a_piscina_piena`: un servizio finto che rende `RecipeSearchPage([], 0, total_is_lower_bound=True)`. La risposta ha `x-total-count: 0` e `x-total-count-lower-bound: 1`.
- [ ] **Step 2: Passano subito**: il comando di pytest con quei due file. Sono prove di un comportamento che c'è già (decisione 1). Se una fallisce, **fermati** (Margine di autonomia).
- [ ] **Step 3: Commit**: `ricette: una prova che lo zero filtrato a piscina piena resta un minimo`.

### Task 2: «Nessuna fra le più vicine»

**Files:**
- Modify: `frontend/src/features/recipes/recipeFilters.ts` (`resultsLabel`)
- Modify: `frontend/src/features/recipes/RecipeBookScreen.tsx` (`emptyMessage` con `lowerBound`, il titolo di `EmptyState`)
- Test: `frontend/src/features/recipes/recipeFilters.test.ts`, `frontend/src/features/recipes/RecipeBookScreen.test.tsx`

**Interfaces:**
- Produces: `resultsLabel(0, true) === "Nessuna fra le più vicine"`. `emptyMessage({ …, lowerBound: boolean })`.

- [ ] **Step 1: I test che falliscono.**
  - `recipeFilters.test.ts`: `resultsLabel(0, true)` dà «Nessuna fra le più vicine»; `resultsLabel(0, false)` dà «Nessuna ricetta», come oggi.
  - `RecipeBookScreen.test.tsx`, «uno zero a piscina piena dice che ho guardato solo le più vicine»: parole cercate e una categoria, la risposta `[]` con `X-Total-Count: 0` e `X-Total-Count-Lower-Bound: 1`. Il vuoto ha il titolo «Nessuna fra le più vicine», e il corpo comincia con la frase di oggi per una categoria e finisce con «Ho guardato solo le ricette più vicine a queste parole: senza parole, i filtri guardano tutto il ricettario.».
  - Lo stesso senza l'intestazione: «Nessuna ricetta», e la frase in più non c'è.
- [ ] **Step 2: Falliscono**: `npx vitest run --maxWorkers=1 src/features/recipes/recipeFilters.test.ts src/features/recipes/RecipeBookScreen.test.tsx`.
- [ ] **Step 3: Il codice**, secondo la decisione 2. Il commento sopra `resultsLabel` dice che a zero il minimo vuol dire «fra i candidati guardati nessuna», e che lo zero filtrato arriva così dal server (Task 1).
- [ ] **Step 4: Passano**, poi `npx vitest run --maxWorkers=4 src/features/recipes`.
- [ ] **Step 5: Commit**: `ricettario: lo zero a piscina piena dice che ho guardato solo le più vicine`.

### Task 3: la categoria ricordata si vede nel menu

**Files:**
- Modify: `frontend/src/features/recipes/RecipeFiltersPanel.tsx`
- Test: `frontend/src/features/recipes/RecipeBookScreen.test.tsx`

**Interfaces:**
- Produces: niente di nuovo. Le voci del menu sono `categories`, più `category` in fondo quando non è vuota e non è fra loro.

- [ ] **Step 1: I test che falliscono**, con i filtri ricordati scritti come le prove di oggi che partono da una sessione (`saveFilters` o la chiave della `sessionStorage` di `recipeFilters.ts`):
  - «una categoria ricordata che il ricettario non ha più si vede scelta»: categoria ricordata «Zuppe fredde», categorie arrivate `["Primi piatti", "Dolci e Desserts"]`. «Filtri, 1 attivo», e il menu «Categoria» ha il valore «Zuppe fredde» con l'opzione omonima. Scelto «Tutte», «Filtri» torna senza numero, e la richiesta dopo non ha `category`.
  - «con le categorie che non arrivano, la ricordata resta nel menu»: `/recipes/categories` risponde 500, la categoria ricordata è «Primi piatti». Il menu c'è, con «Tutte» e «Primi piatti» scelta.
- [ ] **Step 2: Falliscono**: `npx vitest run --maxWorkers=1 src/features/recipes/RecipeBookScreen.test.tsx`.
- [ ] **Step 3: Il codice**, secondo la decisione 3:
  ```ts
  // la categoria scelta c'è sempre fra le voci: ricordata dalla sessione, vale e «Filtri»
  // la conta anche quando il ricettario non la elenca (le categorie non sono arrivate, o
  // quella non c'è più). Senza, il menu mostrava «Tutte» su un filtro acceso
  const shown = category && !categories.includes(category) ? [...categories, category] : categories;
  ```
  Il blocco del menu si mostra con `shown.length > 0`.
- [ ] **Step 4: Passano**, con «senza categorie nel ricettario il filtro non compare» com'è, poi `npx vitest run --maxWorkers=4 src/features/recipes`.
- [ ] **Step 5: Commit**: `ricettario: una categoria ricordata si vede nel menu anche quando non è elencata`.

### Task 4: un aggiornamento fallito tiene l'elenco

**Files:**
- Modify: `frontend/src/features/recipes/RecipeBookScreen.tsx`
- Test: `frontend/src/features/recipes/RecipeBookScreen.test.tsx`

**Interfaces:**
- Consumes: `isLoadingError` e `isRefetchError` di `useInfiniteQuery`. Nella versione installata, `isRefetchError` è già falso per l'errore di una pagina dopo (`infiniteQueryObserver.js`: `isRefetchError && !isFetchNextPageError && !isFetchPreviousPageError`).

- [ ] **Step 1: I test che falliscono.**
  - «una rilettura fallita tiene le ricette e lo dice»: la prima pagina arriva con due ricette; poi la ricerca risponde 500 e la query `["recipes"]` si invalida (come fa un'eliminazione). Le due righe restano in «Ricette trovate», sopra c'è «Non sono riuscito ad aggiornare il ricettario. Le ricette qui sotto sono dell'ultimo caricamento.», e non c'è «Non sono riuscito a cercare nel ricettario.». «Riprova» con la risposta di nuovo buona toglie l'avviso.
  - Le prove di oggi «una ricerca fallita lo dice, e non sembra un ricettario vuoto» e «se la pagina dopo fallisce, le ricette restano e si può riprovare» restano com'è.
- [ ] **Step 2: Fallisce**: `npx vitest run --maxWorkers=1 src/features/recipes/RecipeBookScreen.test.tsx`.
- [ ] **Step 3: Il codice**, secondo la decisione 4. `searchFailed` diventa `isLoadingError`, e `refreshFailed` è `isRefetchError`. Il commento dice che una chiave nuova (una ricerca diversa) non ha dati, quindi il suo errore resta pieno.
- [ ] **Step 4: Passano**, poi `npx vitest run --maxWorkers=4 src/features/recipes`.
- [ ] **Step 5: Commit**: `ricettario: un aggiornamento fallito tiene l'elenco a video e lo dice`.

### Task 5: il «Riprova» di un'eliminazione non porta via (solo con `BASE=night/ricetta-pasto-lucchetto`)

**Files:**
- Modify: `frontend/src/features/recipes/useArchiveRecipe.ts` (i due ref, la condizione del `navigate`)
- Test: `frontend/src/features/recipes/useArchiveRecipe.navigation.test.tsx`, un file nuovo. Quello di oggi lo cambiano già i due piani della notte prima, e non serve una terza mano.

**Interfaces:**
- Consumes: `useLocation` di `react-router-dom`.
- Produces: niente di nuovo; `archive(recipe)` ha la firma di oggi.

- [ ] **Step 1: I test che falliscono**, con lo schema di `useArchiveRecipe.test.tsx` (un `MemoryRouter` che parte da `/ricette/r-carb`, il percorso letto da un `data-testid`). Questa volta il gancio sta dentro una `Route path="/ricette/:id"`, così uscendo si smonta. Le prove che toccano «Riprova» montano `NoticeProvider` con `durationMs={60_000}` se il ramo l'ha già; se no, come le altre del file, e il report lo dice.
  - «un «Riprova» toccato dopo essere usciti dal dettaglio non cambia pagina»: il primo `PATCH {archived: true}` fallisce, e compare «Non sono riuscito a eliminarla: è ancora nel ricettario.» con «Riprova». Si va a `/lista`. «Riprova», il `PATCH` riesce: il percorso resta `/lista`, e c'è l'avviso «Eliminata: ‹titolo›» con «Annulla».
  - «… passati al dettaglio di un'altra ricetta, non cambia pagina»: lo stesso, ma si va a `/ricette/r-altra`. Il gancio resta montato, e il percorso resta `/ricette/r-altra`.
  - La prova di oggi «un'eliminazione che fallisce lascia la ricetta dov'è, e «Riprova» ci riprova» (dal dettaglio, porta a `/ricette`) resta com'è.
- [ ] **Step 2: Falliscono**: `npx vitest run --maxWorkers=1 src/features/recipes/useArchiveRecipe.navigation.test.tsx`.
- [ ] **Step 3: Il codice**, secondo la decisione 5:
  ```ts
  const { pathname } = useLocation();
  // dove si è adesso, e se chi ha eliminato c'è ancora: il «Riprova» vive nell'avviso,
  // che è dell'app, e si tocca anche dopo essere usciti dal dettaglio
  const here = useRef(pathname);
  const alive = useRef(false);
  useEffect(() => {
    here.current = pathname;
  }, [pathname]);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  ```
  Nell'`onSuccess`: `if (alive.current && here.current === \`/ricette/${recipe.id}\`) navigate("/ricette", { replace: true });`, con un commento che dice perché `alive` da solo non basta. `restoreToBook` e `restore` non si toccano.
- [ ] **Step 4: Passano**, con `useArchiveRecipe.test.tsx` e `src/features/cooking/RecipeDetailScreen.test.tsx`, poi `npx vitest run --maxWorkers=4 src/features/recipes src/features/cooking`.
- [ ] **Step 5: Commit**: `ricette: il «Riprova» di un'eliminazione non cambia pagina fuori dal dettaglio`.

### Task 6: il foglio della cottura dice cosa hai dichiarato

**Files:**
- Modify: `frontend/src/features/cooking/CookSheet.tsx`
- Test: `frontend/src/features/cooking/CookSheet.test.tsx`

**Interfaces:**
- Consumes: `STATUS_LABELS`, `afterCooking`.

- [ ] **Step 1: I test che falliscono.**
  - «una riga cambiata dice in che stato va»: su una confezione disponibile si tocca «Quasi finito». La riga piccola contiene «Disponibile», «→» e «quasi finito», e «quasi finito» ha la classe `text-brand`.
  - «tornando allo stato di partenza il segno sparisce»: poi «Disponibile», e nella riga non c'è più «→».
  - «spuntare solo «Rimetti in lista» non mette la freccia»: una quasi finita invariata con la casella spuntata, e nella riga nessun «→».
- [ ] **Step 2: Falliscono**: `npx vitest run --maxWorkers=1 src/features/cooking/CookSheet.test.tsx`.
- [ ] **Step 3: Il codice**, secondo la decisione 6:
  ```tsx
  <p className="text-xs text-ink-soft">
    {STATUS_LABELS[item.status]}
    {changed && (
      <>
        {" "}
        <span aria-hidden="true">→</span>{" "}
        <span className="font-medium text-brand">
          {/* lo spazio fuori dallo `sr-only`: Chromium lo mangia (vedi StockingScreen) */}
          <span className="sr-only">diventa</span> {STATUS_LABELS[status].toLowerCase()}
        </span>
      </>
    )}
    {" · "}in dispensa dal {addedOn(item)}
  </p>
  ```
  dove `changed` è `choice.status !== "unchanged"`.
- [ ] **Step 4: Passano**, poi `npx vitest run --maxWorkers=4 src/features/cooking`.
- [ ] **Step 5: Commit**: `cottura: una riga cambiata dice in che stato va`.

### Task 7: il foglio distingue le confezioni

**Files:**
- Modify: `frontend/src/features/cooking/CookSheet.tsx` (`itemLabel` con la scadenza, la riga, `distinctLabels`)
- Test: `frontend/src/features/cooking/CookSheet.test.tsx`

**Interfaces:**
- Consumes: `expiryText` da `frontend/src/features/pantry/expiryLabels.ts`.

- [ ] **Step 1: I test che falliscono.**
  - «ogni riga dice la scadenza»: due vasetti dello stesso yogurt, uno con `expires_on` lontano (`expiry: null`) e uno vicino (`expiry: "soon"`). Ogni riga finisce col testo di `expiryText` per la sua data, calcolato nel test con la stessa funzione. Quella vicina ha `text-expiry`. Il nome del gruppo delle tacche contiene quel testo.
  - «due confezioni uguali in tutto hanno nomi diversi per chi ascolta»: due voci con lo stesso prodotto, marca, stato, `added_at` e scadenza. I gruppi delle tacche si chiamano «… · confezione 1» e «… · confezione 2», e così anche le caselle «Rimetti in lista …». A video la riga non ha «confezione».
  - La prova di oggi «due confezioni identiche tranne la data d'ingresso restano distinguibili» resta com'è: lì i nomi sono già diversi, e il numero non c'è.
- [ ] **Step 2: Falliscono**: `npx vitest run --maxWorkers=1 src/features/cooking/CookSheet.test.tsx`.
- [ ] **Step 3: Il codice**, secondo le decisioni 7 e 8. `itemLabel` aggiunge la scadenza dopo la data d'ingresso. `distinctLabels(used)` dà a ogni id il suo nome, col numero solo per i nomi ripetuti, e `label` nella riga viene da lì. Nella riga, dopo «in dispensa dal …»:
  ```tsx
  {expiry && (
    <>
      {" · "}
      <span className={item.expiry ? "font-medium text-expiry" : undefined}>{expiry}</span>
    </>
  )}
  ```
- [ ] **Step 4: Passano**, poi `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- [ ] **Step 5: Commit**: `cottura: ogni confezione dice la sua scadenza, e due uguali si chiamano diverse`.

### Task 8: e2e, la verifica nel browser, il backlog

- [ ] **Step 1: e2e intera**, con i comandi delle Global Constraints, dentro il limite di carico. Il backend intero col comando di pytest.
- [ ] **Step 2: Nel browser**, sullo stack e2e prima del `down`, a **375 px** e nei **due temi**:
  - in Dispensa una scadenza fra pochi giorni su una confezione di un ingrediente di una ricetta del seme; poi, dal dettaglio di quella ricetta, il foglio della cottura. La scadenza c'è nella riga, in viola. Toccata un'altra tacca, si legge «… → quasi finito» in colore. La riga non va a capo male;
  - nel ricettario, con la categoria ricordata scritta a mano nella `sessionStorage` (la chiave di `recipeFilters.ts`) come «Zuppe fredde», e la pagina ricaricata: «Filtri» col numero, e nel pannello il menu con «Zuppe fredde» scelta.

  Uno screenshot per tema va nel report. Lo zero a piscina piena non si vede col seme (26 ricette, la piscina è 100): lo provano i Task 1 e 2.
- [ ] **Step 3: Il backlog.** Le due voci passano a `fatto <data>` in «Fatti (recenti)», con ` → branch night/ricettario-rifiniture (da revisionare)`, più «, da unire dopo night/ricetta-pasto-lucchetto» se `BASE` era quel ramo. **Se il Task 5 è stato saltato**, la voce del ricettario si divide: i tre punti fatti vanno a `fatto`, e resta una riga `[pronto] P3 · Il ricettario: il «Riprova» di un'eliminazione fallita, toccato dopo essere usciti dal dettaglio, porta comunque al ricettario [T3 Consegna 4] → docs/superpowers/plans/2026-11-23-ricettario-rifiniture.md, Task 5, da night/ricetta-pasto-lucchetto`. Commit: `next-steps: le rifiniture del ricettario, fatte`.

## Fuori scope

- In Dispensa, due confezioni con la stessa data che restano uguali (decisione 9). Se serve, va nel report come idea: dopo `dispensa-rifiniture`, sullo stesso `itemLabel` di `pantryView.ts`.
- Cambiare `CANDIDATE_POOL` o far guardare ai filtri tutto il ricettario anche con le parole: è la scelta scritta in `recipe_search.py`, da rimisurare se il ricettario cresce.
- Un pulsante «Togli le parole» nel vuoto.
- Il «Riprova» dell'annullamento (`restore`, `restoreToBook`): non porta da nessuna parte già oggi.

## Comandi di verifica

- Backend: il comando di pytest delle Global Constraints, tutto verde, con i due test nuovi.
- Frontend, da `<worktree>/frontend`: `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- e2e: la suite intera, verde.
- `grep -rn "100" frontend/src/features/recipes/RecipeBookScreen.tsx frontend/src/features/recipes/recipeFilters.ts` non trova la piscina scritta in una frase.
- `grep -rn "emerald\|neutral-" frontend/src` resta vuoto.
- `git -C <worktree> diff "$BASE" --stat` tocca solo i file dei task, più `next-steps.md` e il report. Il codice del backend non c'è.
