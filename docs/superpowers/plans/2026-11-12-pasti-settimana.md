# Pasti e settimana, senza Claude: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** una scheda «Pasti» con la settimana da lunedì a domenica, pranzo e cena; pasti scritti a mano (piatto, accompagnamenti, fuori casa, avanzo), spostati, corretti e cancellati; una ricetta per pasto, scritta col modulo di sempre o copiata dal ricettario, che resta **fuori dal ricettario** finché non la si salva lì; e la schermata del piatto con la ricetta sopra, senza «Cucina». Tutto quello che la sezione Pasti fa **senza Claude**.

**Architecture:** una tabella `meals` (posto unico per giorno e pasto, legame uno a uno con la ricetta, avanzo legato al pasto d'origine) e una colonna `recipes.in_book`, nella migrazione `0020`. Le regole pure stanno in `app/domain/meals.py`, le letture in `app/repositories/meals.py`, le scritture con le loro regole (posto occupato, avanzo, ricetta da liberare, copia) in `app/services/meals.py`, le rotte in `app/api/meals.py`. Ogni elenco del ricettario filtra con una sola espressione, `in_the_book()`, accanto alla colonna. Nel frontend una cartella `features/meals/` e una modalità «pasto» del dettaglio della ricetta che c'è già.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Alembic, pytest su Postgres vero; React 19, TypeScript, Tailwind 4 (token in `@theme`), TanStack Query, Vitest + Testing Library (jsdom), Playwright.

**Spec:** `docs/superpowers/specs/2026-11-12-pasti-claude-design.md` (approvata da Mattia il 2026-11-12). Questo piano copre §4.1, §4.2, §5.1 e §5.3 per la parte senza Claude, e §11 per quel che tocca questo ramo. È il **piano 2 di 4** della catena (vedi «Dipendenze»). La riga di `next-steps.md` legata a questo ramo contiene «Sezione Pasti», e **resta aperta** finché i piani 3 e 4 non finiscono.

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/pasti-settimana`, ramo `night/pasti-settimana`, creato da **`night/utensili`** (il piano 1, Utensili). Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì (o dalle sue `backend/` e `frontend/`), mai dalla radice del checkout principale. Il checkout principale non si tocca: se vi trovi modifiche non committate, sono dell'utente. **Nessun push, nessun merge, nessun deploy. Mai `git stash`. Niente letture o scritture sulla produzione.**
- **Leggi ogni file com'è sul ramo prima di cambiarlo.** Il piano descrive le modifiche ai file esistenti contro ancore riconoscibili (una funzione, una riga di codice esatta, un elemento JSX), mai contro numeri di riga: il ramo di partenza ha già le modifiche di Utensili (una voce nel ☰, una rotta `/utensili`, `App.tsx`, `icons.ts`, `domain/types.ts`, `app/main.py`, `app/db/models/__init__.py`, `ai_recipes.py`, `style.spec.ts`). Dove il piano dà un file intero è un file nuovo.
- **Decisione fondante 2.** Le ricette dei pasti sono ricette vere: le righe passano **solo** da `write_recipe_ingredients` (l'imbuto che rifiuta i non alimentari), dosi lette dal parser, riscalabili. Nessuna scrittura di `recipe_ingredients` fuori da lì, nemmeno per la copia.
- **Sesta lezione di `CLAUDE.md`.** Ogni elenco e ogni ricerca del ricettario esclude le ricette fuori dal ricettario **dentro la query che porta il limite**, come le archiviate, e sempre con `in_the_book()`: niente filtri dopo `.limit()`, niente seconde copie della condizione.
- **Il frontend non calcola logica di dominio.** Il lunedì della settimana, «oggi» (nel giorno di Roma, `today_in_pantry`), «non registrata», chi può ricevere una ricetta, se un avanzo è valido: tutto nel backend. Il frontend formatta le date che riceve e mostra.
- **Mai un vicolo cieco.** Un posto occupato offre «Sostituisci»; un pasto senza ricetta offre «Scrivi la ricetta» e «Scegli dal ricettario»; un rifiuto dice sempre cosa fare.
- Tutto il colore passa dai token di `frontend/src/index.css`. **Nessun token nuovo.** `grep -rn "emerald\|neutral-" frontend/src` resta vuoto. Ogni testo sta sopra 4,5:1 nei due temi, misurato da `frontend/e2e/style.spec.ts`. Primitive da `frontend/src/components/ui/` (`Button`, `Card`, `Chip`, `Alert`, `SectionHeading`, `IconToolbar`); `Button` non cambia. A 375 px nessuna schermata scorre di lato.
- Le parole a video sono in italiano e **si copiano esattamente come sono scritte qui** (fra «»); gli identificatori in inglese; i commenti in italiano.
- **Il type check è `npm run typecheck`** (`tsc -b`). **Mai `tsc --noEmit`** (settima lezione di `CLAUDE.md`). Controlli del frontend, da `<worktree>/frontend`: `npx vitest run`, `npm run typecheck`, `npm run lint`, `npm run build`. I test dei componenti usano `createTestQueryClient` da `src/test/queryClient.ts`, mai un `QueryClient` loro (`noLocalQueryClient.test.ts` lo controlla).
- **Backend su Postgres vero.** Il container `spena-db-1` (porta 5433), solo come database dei test: se `docker ps --format '{{.Names}}'` non lo mostra, `docker start spena-db-1`. **Mai `docker compose up` dal worktree**, mai `-f docker-compose.prod.yml`. Questo ramo porta lo schema alla `0020`, oltre `master` e oltre Utensili: usa **sempre** il database suo, `spena_test_pasti_settimana` (Preparazione). Nel worktree non c'è un `.venv`: si usa quello del checkout principale. Il comando di pytest, sempre da `<worktree>/backend` (dove un task dice «il comando di pytest» intende questo, con i percorsi in coda):
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_pasti_settimana \
    PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
  Se un test sembra ignorare una modifica, `python -c 'import app; print(app.__file__)'` da `<worktree>/backend` (con lo stesso `PATH`) deve stampare un percorso dentro il worktree. Nessuna chiamata di rete nella suite.
- **e2e** sullo stack `spena-e2e`, dalla radice di `<worktree>`. Il `.env` **si copia da `.env.example`, solo per la prova, e si cancella alla fine. Mai leggere né copiare il `.env` del checkout principale.** Prima di alzarlo, `docker ps --format '{{.Names}}' | grep spena-e2e`: se c'è e non l'hai alzato tu, non fare `down`, aspetta che sparisca.
  ```bash
  cp .env.example .env
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed --con-ricette
  (cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
  rm .env
  ```
  Il `-p spena-e2e` e il `-f docker-compose.e2e.yml` vanno in ogni comando: un `down -v` sul progetto di default cancellerebbe la dispensa vera. Una prova fallita lascia dati: prima di rieseguire, `down -v`, poi `up`, seme e prova.
- Nessuna dipendenza nuova. Una migrazione sola, la `0020`. Nessun cambio di configurazione globale.

### Preparazione (una volta, prima del Task 1)

- [ ] **Il ramo di partenza.** Il piano 1 deve aver lasciato `night/utensili` con la sua migrazione:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify night/utensili
  git ls-tree -r --name-only night/utensili -- backend/alembic/versions | grep 0019
  git show night/utensili:docs/superpowers/specs/2026-11-12-pasti-claude-design.md >/dev/null && echo spec-ok
  ls .worktrees/pasti-settimana 2>&1 | head -1
  ```
  Expected: un hash (**annotalo**: è `BASE` del Task 11); un file `0019_….py`; `spec-ok` (se manca, la spec si legge dal checkout principale, `/home/mactyws/coding/ais/spena/docs/superpowers/specs/2026-11-12-pasti-claude-design.md`, e non si copia); `No such file or directory`. **Se `night/utensili` non esiste** o non ha la `0019`: non creare niente, fermati, e scrivi nel messaggio finale della notte che il piano 2 non è partito perché manca il piano 1 (i piani 3 e 4 dipendono da questo). Se `.worktrees/pasti-settimana` esiste già, qualcuno ha cominciato: fermati e scrivilo nel messaggio finale.
- [ ] **Il database dei test di questo ramo**:
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_pasti_settimana WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_pasti_settimana'
  ```
- [ ] Dal checkout principale, allinea `node_modules` al lockfile: `cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund`.
- [ ] **Il worktree** da `night/utensili`, con `node_modules` collegato (niente `.env`):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/pasti-settimana -b night/pasti-settimana night/utensili
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/pasti-settimana/frontend/node_modules
  ```
- [ ] **La revisione da cui parte la `0020`**, da `<worktree>/backend`:
  ```bash
  DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_pasti_settimana \
    PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" alembic heads
  ```
  Expected: **una riga sola**, la revisione della `0019` di Utensili (per esempio `0019 (head)`). **Annota l'identificatore esatto**: è il `down_revision` del Task 1. Se le teste sono due o più, fermati: segna la voce `bloccato` (sotto) con «attende: le teste di Alembic su night/utensili sono più d'una».
- [ ] La voce in `next-steps.md` del ramo passa a `in corso` (cercala con `grep -n "Sezione Pasti" next-steps.md`; cambia solo lo stato fra parentesi quadre, dovunque sia; se è già `in corso` lasciala) e si committa:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/pasti-settimana
  git add next-steps.md && git commit -m "next-steps: sezione Pasti, piano 2 (pasti e settimana senza Claude) in corso"
  ```
- [ ] **La linea di partenza**, dal worktree:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/pasti-settimana/frontend && npx vitest run 2>&1 | grep -E "Test Files|Tests "
  cd ../backend && TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_pasti_settimana \
    PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q 2>&1 | tail -n 1
  ```
  Expected: tutto verde. **Annota** `N_file`, `N_vitest`, `N_pytest`. Se una delle due non è verde, fermati: non è un difetto di questo piano, va nel report.

---

## Obiettivo e contesto

Oggi i pasti vivono sul planner del reMarkable e nella skill `pasti`. La spec porta tutto il giro in spena, in quattro consegne (§10): (1) Utensili, (2) **pasti e settimana a mano, con le ricette fuori dal ricettario** — questo piano —, (3) Claude e la chat del piatto, (4) la pianificazione con le schede dei cambi. Questo piano costruisce il terreno su cui gli altri due mettono Claude: il modello dei pasti, la settimana, il piatto, e le ricette dei pasti che non riempiono il ricettario (anti-obiettivo §2: «ricette dei pasti che riempiono il ricettario di frittate fatte una volta sola»). Alla fine Mattia può già usare spena al posto del planner, scrivendo i pasti a mano.

## Decisioni prese

Della spec (Mattia, 2026-11-12; il perché è nella spec):

1. **Un pasto è un posto**: una data, pranzo o cena, al più un pasto per posto; piatto, accompagnamenti (testo breve), fuori casa, ricetta facoltativa (§4.1).
2. **Bozza o ufficiale**: i pasti scritti a mano nascono ufficiali; una bozza non ha ricetta; una bozza nel passato si mostra «non registrata» (§4.1, §5.2).
3. **La ricetta di un pasto è una ricetta vera, fuori dal ricettario** finché non si sceglie «Salva nel ricettario»; «Togli dal ricettario» la rimette fuori (§4.2).
4. **Uno a uno pasto → ricetta**: «Scegli dal ricettario» e «rifacciamo» fanno una copia; «Scrivi la ricetta» apre il modulo di sempre; la ricetta del ricettario non si tocca mai da un pasto (§4.2).
5. **Avanzo**: un pasto senza ricetta propria, legato al pasto d'origine, che si apre sulla sua ricetta in sola lettura (§4.2).
6. **Eliminare un pasto** archivia la sua ricetta se non è nel ricettario; se lo è, la lascia (§4.2).
7. **Esclusioni** dagli elenchi del ricettario, dalla ricerca semantica, dal calcolo dei cucinabili e dal motore dei sostituti; **inclusione** nei conteggi dell'Anagrafica, marcate «(da un pasto)» (§4.2).
8. **La settimana**: scheda «Pasti» nella barra in basso, lunedì–domenica con le frecce, oggi evidenziato, posti vuoti «+ da pianificare»; spostare e cancellare a mano, nel modo che si vuole (§5.1).
9. **Il piatto (versione A)**: la ricetta sopra, piatto/accompagnamenti/posto correggibili, «Modifica» al modulo di sempre, «Salva nel ricettario», niente «Cucina» aperta da un pasto, «Cucina» sì aperta dal ricettario (§5.3).

Di Claude, su delega (non funzionali o reversibili; Mattia le può rivedere nel report):

10. **Valori salvati in inglese**: `slot` è `lunch`/`dinner`, `status` è `draft`/`official`; a video «Pranzo», «Cena», «Bozza». Come `recipes.source` e gli stati della dispensa.
11. **«Pasti» è la quarta scheda**, dopo Ricette, con l'icona `IconCalendarWeek`.
12. **Spostare e cancellare si fa dalla schermata del piatto** («Correggi», che comprende giorno e pasto, ed «Elimina»), non dalla riga della settimana: la settimana resta una griglia di collegamenti.
13. **Spostare su un posto occupato sostituisce il vecchio, solo con una conferma** («Sostituisci»): stessa regola che la spec dà alla scheda di Claude (§5.2). Nessuno scambio.
14. **Diventare «fuori casa» libera il pasto**: la ricetta si toglie (e si archivia se non è nel ricettario) e il legame d'avanzo si toglie, come per un pasto eliminato. Un pasto fuori casa non ha ricetta (vincolo nel database).
15. **Un avanzo** si sceglie nel modulo fra i pasti dei 3 giorni prima del posto (`LEFTOVER_WINDOW_DAYS = 3`), cucinati prima di lui, che non sono a loro volta avanzi né fuori casa. Cancellato il pasto d'origine, l'avanzo resta come pasto a mano con il suo piatto (`ON DELETE SET NULL`).
16. **La copia** porta titolo, descrizione, procedimento, porzioni, categoria, costo, foto, tempi, righe (con le note) e il vettore della ricetta d'origine; nasce `source = 'manual'`, senza `source_ref` e senza `derived_from_id` (non è una variante R8: a video direbbe «Variante di»).
17. **La ricetta scritta a mano per un pasto** nasce con `source = 'manual'` (la spec dice `ai` per quelle che scrive Claude, piano 3) e il modulo parte con il titolo uguale al piatto e 1 porzione (§7: le dosi del pasto come lo si mangia).
18. **L'invariante del ricettario**: una ricetta viva fuori dal ricettario ha sempre un pasto. Per tenerla: «Togli dal ricettario» si rifiuta su una ricetta senza pasto; ripristinare un'eliminata fuori dal ricettario e senza pasto la rimette nel ricettario.
19. **Il dettaglio `/ricette/:id` di una ricetta fuori dal ricettario porta al suo pasto** (`/pasti/:id`, `replace`): un collegamento dell'Anagrafica o uno vecchio non mostra mai «Cucina» su una ricetta di un pasto.
20. **`reindex` include le ricette fuori dal ricettario**: il vettore serve il giorno in cui la si salva nel ricettario, e la ricerca non la vede comunque.
21. **Nella modalità «pasto» il dettaglio nasconde** «Cucina», «Elimina» (si elimina il pasto) e «Modifica con AI» (R8 creerebbe una variante nel ricettario da una ricetta che non c'è; la chat del piano 3 ne prende il posto). Restano dosi, riporziona, sostituti, «Metti in lista ciò che manca», nutrienti.
22. **Il tipo `RecipeDetail` riceve `in_book` e `meal` come campi facoltativi**: una risposta di un backend vecchio, in cache nel service worker, non li ha (si legge `recipe.in_book ?? true`), e le decine di dati di prova dei test esistenti restano validi.

## Criteri di accettazione

- [ ] La `0020` sale e scende; le ricette che c'erano restano nel ricettario; i vincoli dei pasti tengono nel database.
- [ ] Una ricetta fuori dal ricettario non compare nello sfoglio, nei cucinabili, nella ricerca testuale e semantica, nelle categorie, nelle voci dei sostituti — nemmeno quando ce ne sono più del limite davanti alla viva; compare in `recipes_using` (con `from_meal`), in `ingredient_usage`, nella fusione dell'Anagrafica e in `reindex`.
- [ ] `GET /api/v1/meals/week` dà la settimana da lunedì a domenica con «oggi» nel giorno di Roma; i pasti si scrivono, si correggono, si spostano (posto occupato → 409 con chi c'è, poi `replace`), si eliminano (con la regola della ricetta), ricevono una copia di una ricetta del ricettario.
- [ ] `POST /api/v1/recipes` con `meal_id` scrive la ricetta di un pasto fuori dal ricettario; `PATCH` con `in_book` la salva e la toglie; ripristinare tiene l'invariante della decisione 18.
- [ ] Nell'app: la scheda «Pasti», la settimana con le frecce e oggi evidenziato, «+ da pianificare», il modulo del pasto, il piatto con la ricetta sopra e senza «Cucina», «Scrivi la ricetta», «Scegli dal ricettario», «Salva nel ricettario» / «Togli dal ricettario», «(da un pasto)» nell'Anagrafica; nel browser vero, a 375 px nei due temi, ogni testo sopra 4,5:1 e niente scorre di lato.
- [ ] Tutti i test di oggi passano; cambiano solo le due asserzioni di `test_registry_ingredients.py` dette nel Task 2.
- [ ] `CLAUDE.md`, `docs/prossimi-passi.md`, `next-steps.md` e il report aggiornati (Task 11).

## Comandi di verifica

Da `<worktree>/backend`: il comando di pytest. Da `<worktree>/frontend`: `npx vitest run`, `npm run typecheck`, `npm run lint`, `npm run build`. Dalla radice di `<worktree>`:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -rn "Recipe.archived_at.is_(None)" backend/app --include=*.py
grep -rn "in_the_book()" backend/app --include=*.py | wc -l
git diff night/utensili --stat -- backend/alembic/versions
```

Expected: il primo vuoto; il secondo **due righe**, la definizione di `in_the_book()` in `backend/app/db/models/recipe.py` e `backend/app/cli/reindex.py` (decisione 20: ogni altro filtro sulle archiviate è diventato `in_the_book()`); il terzo `7` (la definizione e sei chiamate: `_semantic_ranking`, `_textual_ranking`, `_browse`, `_any_recipe_has_a_vector`, `recipe_categories`, `_usage`); il quarto un file solo, `0020_pasti.py`. E l'e2e intera con i comandi delle Global Constraints.

## Review Focus

1. **Una ricetta di un pasto davanti al limite** (cento frittate fuori dal ricettario che dicono «frittata» più della viva, o che precedono la viva nell'ordine della pagina): la viva deve restare — Task 2 (`…_prima_della_pagina`, `…_prima_della_piscina`, testuale e semantica).
2. **Una ricetta eliminata insieme al suo pasto, poi ripristinata da un collegamento dell'Anagrafica**: non deve diventare una ricetta viva che nessun elenco mostra e nessun pasto apre — Task 5 (`test_ripristinare_una_ricetta_senza_pasto_la_rimette_nel_ricettario`).
3. **Spostare un pasto sul posto di un altro** con il vincolo d'unicità: con la conferma, il vecchio se ne va e il nuovo prende il posto nella stessa transazione, senza `IntegrityError` — Task 3 (`test_spostare_su_un_posto_occupato_chiede_la_sostituzione_e_poi_sostituisce`) e Task 4 (rotta).
4. **Domenica notte a Roma è già lunedì**: «oggi» e la settimana aperta seguono il giorno di Roma, non quello di UTC — Task 3 (`test_la_settimana_di_oggi_e_quella_di_roma`).
5. **Eliminare un pasto la cui ricetta è stata salvata nel ricettario**, o il pasto da cui viene un avanzo: la ricetta del ricettario resta viva e intatta, l'avanzo resta senza legame — Task 3 (`test_eliminare_lascia_la_ricetta_del_ricettario`, `test_eliminare_il_pasto_d_origine_lascia_l_avanzo_senza_legame`).

## Fuori scope

- **Claude, in ogni forma** (piani 3 e 4): le conversazioni (§4.3), la chat del piatto e «Annulla» delle sue modifiche, «Pianifica con Claude», «chiedilo a Claude» sul posto vuoto, «Chiedi la ricetta a Claude», la «ricetta in preparazione», `CLAUDE.md` sui fornitori di modelli (§3).
- **Le schede dei cambi a dispensa e lista** (§6.2, piano 4), compresa quella vuota proposta quando una bozza diventa ufficiale a mano, e la **scheda inversa** quando si cancella, si sostituisce o diventa fuori casa un pasto ufficiale. Qui «Rendi ufficiale» cambia solo lo stato; il piano 4 ci aggancia la scheda.
- Creare bozze dall'app: le scrive Claude (piano 4). L'API le accetta (`status: "draft"`), e la settimana le mostra.
- Colazione e spuntini, l'import delle settimane del reMarkable, NutriScore, budget (spec §2).
- Ritirare la skill `pasti` (§11: dopo la prova in produzione).
- Le voci di `next-steps.md` P1, P2, M1, H3: si tolgono di giorno, insieme alla voce «Sezione Pasti» quando tutta la sezione sarà finita (Task 11 dice cosa fare se sono ancora lì).

## Margine di autonomia

- **Liberi:** i nomi di variabili locali, helper dei test, funzioni private non fissati qui; l'ordine delle classi Tailwind; l'aspetto delle schermate dentro il sistema visivo di spena (spazi, `Card` o no, dove sta un `Chip`); la formulazione dei commenti, purché dicano il perché.
- **Fissi:** le parole a video fra «» di questo piano; i nomi pubblici dei blocchi Interfaces (i piani 3 e 4 li usano); le rotte API e del frontend; i valori `lunch`/`dinner`/`draft`/`official`; i codici e le frasi dei rifiuti.
- **Un test di oggi si cambia solo dove il piano lo dice** (le due asserzioni del Task 2). Se un altro cade, è un comportamento che il piano non ha previsto: scrivilo nel report con il perché, non indebolirlo.
- **Una decisione di comportamento non coperta e non reversibile** → si ferma quel task, si fa commit del lavoro parziale, la voce «Sezione Pasti» passa a `bloccato` con «attende: …» e la domanda precisa per Mattia, e si passa al task successivo se non dipende da quello. Una scelta reversibile e a basso impatto → la più conservativa, annotata nel report.
- Se un test fallisce e non si risolve: niente test disattivati, niente asserzioni indebolite; `bloccato` con la diagnosi.
- Se un'icona nominata qui (`IconCalendarWeek`, `IconBookmarkPlus`, `IconBookmarkOff`) non esiste nella versione installata di `@tabler/icons-react` (`ls frontend/node_modules/@tabler/icons-react/dist/esm/icons/ | grep -i <nome>`), scegli la più vicina e scrivilo nel report.

## Dipendenze

- **Parte da `night/utensili` (piano 1)**, di cui consuma solo la testa di Alembic (`0019`) e i file così come li lascia (☰, rotte, icone, `style.spec.ts`). Nessun'altra interfaccia.
- **Il piano 3 (`night/pasti-claude`) parte da questo ramo** e usa: `Meal`, `meals_between`, `get_meal`, `meal_of_recipe`, `link_recipe`, `check_can_take_recipe`, `copy_recipe`, `create_recipe(in_book=False)`, `RecipeOut.in_book`/`meal`, `MealScreen` con il posto per la chat sotto la ricetta, `RecipeDetailView` in modalità pasto.
- **Il piano 4 (`night/pasti-pianificazione`)** usa: `create_meal(status=…)`, `update_meal` (bozza → ufficiale), `release_recipe`, `delete_meal`, il rifiuto `slot_taken` con l'occupante, `WeekScreen` con il posto per «Pianifica con Claude», `NewMealScreen` con il posto per «Chiedilo a Claude».
- Al merge su `master` i quattro rami vanno uniti in ordine; la `0020` ha `down_revision` uguale alla `0019` di Utensili e così deve restare.

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `backend/alembic/versions/0020_pasti.py` (nuovo), `backend/app/db/models/meal.py` (nuovo), `backend/app/db/models/recipe.py`, `backend/app/db/models/__init__.py`, `backend/tests/db/test_migration_0020.py` (nuovo) | 1 | `meals`, `recipes.in_book`, `in_the_book()` |
| `backend/app/services/recipe_search.py`, `backend/app/repositories/recipes.py`, `backend/app/repositories/substitutions.py`, `backend/app/services/registry.py`, `backend/app/api/refusals.py`, `backend/tests/api/test_registry_ingredients.py`, tre file di test nuovi | 2 | i consumatori del ricettario |
| `backend/app/domain/meals.py`, `backend/app/repositories/meals.py`, `backend/app/services/meals.py` (nuovi), `backend/app/repositories/recipes.py`, due file di test nuovi | 3 | regole, letture, scritture, copia |
| `backend/app/schemas/meal.py`, `backend/app/api/meals.py` (nuovi), `backend/app/api/refusals.py`, `backend/app/main.py`, `backend/tests/api/test_meals.py` (nuovo) | 4 | le rotte dei pasti |
| `backend/app/api/recipes.py`, `backend/app/schemas/recipe.py`, `backend/tests/api/test_recipes_meal.py` (nuovo) | 5 | la ricetta di un pasto dalla parte delle ricette |
| `frontend/src/domain/types.ts`, `frontend/src/features/meals/{api,format}.ts`, `WeekScreen.tsx`, `frontend/src/components/TabBar.tsx`, `frontend/src/components/ui/icons.ts`, `frontend/src/App.tsx` e test | 6 | la settimana |
| `frontend/src/features/meals/{MealForm,NewMealScreen,MealScreen}.tsx` e test | 7 | il pasto a mano |
| `frontend/src/features/cooking/RecipeDetailScreen.tsx`, `MealScreen.tsx`, `frontend/src/features/recipes/api.ts`, `frontend/src/features/registry/CategoryForm.tsx` e test | 8 | la ricetta nel piatto |
| `frontend/src/features/meals/{MealRecipeNewScreen,MealRecipePickScreen}.tsx`, `frontend/src/features/recipe-form/RecipeEditScreen.tsx` e test | 9 | scrivere e scegliere la ricetta |
| `frontend/e2e/pasti.spec.ts` (nuovo), `frontend/e2e/style.spec.ts` | 10 | nel browser vero |
| `CLAUDE.md`, `docs/prossimi-passi.md`, `next-steps.md`, `docs/night-reports/<data>.md` | 11 | documenti e report |

---

### Task 1: Lo schema — `meals` e `recipes.in_book`

**Files:**
- Create: `backend/alembic/versions/0020_pasti.py`, `backend/app/db/models/meal.py`, `backend/tests/db/test_migration_0020.py`
- Modify: `backend/app/db/models/recipe.py` (la colonna accanto ad `archived_at`, la funzione `in_the_book` in fondo al file), `backend/app/db/models/__init__.py` (import e `__all__`)

**Interfaces:**
- Consumes: la revisione della `0019` letta nella Preparazione.
- Produces:
  - `Recipe.in_book: Mapped[bool]` — `Boolean`, `nullable=False`, `server_default=sa.true()`, `default=True`.
  - `in_the_book() -> ColumnElement[bool]` in `app.db.models.recipe`: `and_(Recipe.in_book.is_(True), Recipe.archived_at.is_(None))`. La docstring dice che è **la** condizione di ogni elenco del ricettario, dentro la query che porta il limite.
  - `Meal(UUIDMixin, TimestampMixin, Base)` in `app.db.models.meal`, tabella `meals`: `day: date` (`Date`, non nullo); `slot: str` (`String(10)`); `dish: str` (`String(200)`); `sides: str | None` (`String(200)`); `away: bool` (`server_default=false()`); `status: str` (`String(10)`, `server_default="official"`); `recipe_id: uuid | None` (FK `recipes.id`, `ondelete="SET NULL"`); `leftover_of_id: uuid | None` (FK `meals.id`, `ondelete="SET NULL"`); relazioni `recipe: Mapped[Recipe | None]` e `leftover_of: Mapped[Meal | None]` (`remote_side`), entrambe `lazy="raise"` (le letture le caricano con `selectinload`, Task 3).
  - Vincoli, con questi nomi (la migrazione e il modello li dichiarano uguali): `uq_meals_day_slot` (`day`, `slot`); `uq_meals_recipe` (`recipe_id`); `ck_meal_slot` (`slot IN ('lunch', 'dinner')`); `ck_meal_status` (`status IN ('draft', 'official')`); `ck_meal_dish_not_blank` (`length(btrim(dish)) > 0`); `ck_meal_leftover_no_recipe` (`leftover_of_id IS NULL OR recipe_id IS NULL`); `ck_meal_away_no_recipe` (`NOT away OR recipe_id IS NULL`); `ck_meal_away_not_leftover` (`NOT away OR leftover_of_id IS NULL`); `ck_meal_draft_no_recipe` (`status = 'official' OR recipe_id IS NULL`); `ck_meal_not_own_leftover` (`leftover_of_id IS NULL OR leftover_of_id <> id`).
  - Migrazione: `revision = "0020"`, `down_revision = "<la 0019 letta nella Preparazione>"`; `upgrade` aggiunge `recipes.in_book` (le righe che ci sono prendono `true` dal `server_default`) e crea `meals`; `downgrade` toglie `meals` e poi `in_book`. Nessun indice nuovo (la tabella ha due pasti al giorno).

- [ ] **Step 1: Il test che fallisce.** `tests/db/test_migration_0020.py`, sul modello di `tests/db/test_migration_0018.py` (un database suo, `f"{TEST_DB}_migrazione_0020"`, creato e distrutto dalla fixture `scratch_url`; Alembic in un sottoprocesso; `alembic(url, "upgrade", "0019…")` con la revisione letta). I test:
  - `test_la_0020_sale_e_le_ricette_che_ci_sono_restano_nel_ricettario`: sulla revisione di Utensili si inserisce una ricetta con SQL crudo; dopo `upgrade head`, `SELECT in_book FROM recipes` vale `True`.
  - `test_un_posto_tiene_un_pasto_solo`: due `INSERT` con lo stesso `(day, slot)` → `IntegrityError`.
  - `test_una_ricetta_appartiene_a_un_pasto_solo`: due pasti (posti diversi) con lo stesso `recipe_id` → `IntegrityError`.
  - `test_i_vincoli_del_pasto`, parametrizzato su otto righe che devono fallire con `IntegrityError`: `slot='brunch'`; `status='maybe'`; `dish='   '`; avanzo con ricetta; fuori casa con ricetta; fuori casa con avanzo; bozza con ricetta; `leftover_of_id = id`.
  - `test_cancellare_la_ricetta_o_il_pasto_d_origine_lascia_il_pasto`: `DELETE` della ricetta → il pasto resta con `recipe_id` NULL; `DELETE` del pasto d'origine → l'avanzo resta con `leftover_of_id` NULL.
  - `test_la_0020_scende`: `downgrade` alla `0019` → `meals` non c'è e `recipes` non ha la colonna `in_book` (da `information_schema`).

- [ ] **Step 2: Fallisce.** Il comando di pytest con `tests/db/test_migration_0020.py`. Expected: FAIL (la revisione `0020` non esiste).

- [ ] **Step 3: La migrazione e i modelli** come nel blocco Interfaces. In `Recipe`, un commento accanto a `in_book` dice: falso per le ricette nate da un pasto finché non si salvano nel ricettario (spec §4.2), e che ogni elenco lo legge da `in_the_book()`. In `meal.py` la docstring di `Meal` riassume §4.1 (un posto, bozza/ufficiale, avanzo, fuori casa) e la regola dell'uno a uno.

- [ ] **Step 4: Passa, e lo schema coincide coi modelli.** Il comando di pytest con `tests/db/test_migration_0020.py tests/db/test_metadata_matches_migrations.py`. Expected: PASS (il secondo file è la guardia di `autogenerate`: se fallisce, modello e migrazione divergono).

- [ ] **Step 5: Commit**
  ```bash
  git add backend/alembic/versions/0020_pasti.py backend/app/db/models/ backend/tests/db/test_migration_0020.py
  git commit -m "feat(pasti): la tabella dei pasti e il segno «nel ricettario» sulle ricette (0020)"
  ```

---

### Task 2: Le ricette fuori dal ricettario, in ogni consumatore

Il punto dove un errore si vede meno (sesta lezione di `CLAUDE.md`). **L'elenco completo** dei punti del backend che leggono «tutte le ricette» o le loro righe, trovato il 2026-11-12, e cosa fa ciascuno:

| # | Consumatore | Dove | Ricette dei pasti | Test |
|---|---|---|---|---|
| 1 | Sfoglio del ricettario (categoria, ingredienti, soglia dei mancanti, ordine e pagina, `X-Total-Count`) | `recipe_search.py::_browse` | **escluse** con `in_the_book()` al posto di `Recipe.archived_at.is_(None)` | 1, 2 |
| 2 | Calcolo dei cucinabili (`max_missing`, `only_cookable`) | stesso `_browse` (`having`) | escluse | 3 |
| 3 | Ricerca testuale | `recipe_search.py::_textual_ranking` | escluse | 4, 5 |
| 4 | Ricerca semantica | `recipe_search.py::_semantic_ranking` | escluse | 6, 7 |
| 5 | «La ricerca semantica serve?» | `recipe_search.py::_any_recipe_has_a_vector` | escluse | 8 |
| 6 | Categorie del filtro (e `_check_category` che le legge) | `repositories/recipes.py::recipe_categories` | escluse | 9 |
| 7 | Motore dei sostituti: voci da decidere e scheda dell'ingrediente | `repositories/substitutions.py::_usage` (`pending_voices`, `ingredient_view`) | escluse | 11, 12 |
| 8 | Vettori mancanti | `cli/reindex.py::reindex` | **incluse** (decisione 20): resta solo il filtro sulle archiviate | 10 |
| 9 | Ricette che usano un ingrediente | `services/registry.py::recipes_using` | **incluse** e segnate (`RecipeRef.from_meal`) | 13, 16 |
| 10 | Conteggi dell'Anagrafica | `repositories/ingredients.py::ingredient_usage` | incluse (conta le righe, com'è) | 14 |
| 11 | Fusione dell'Anagrafica | `services/registry.py::merge_ingredients` | incluse: le righe si spostano | 15 |
| 12 | Dettaglio, riporziona, nutrienti, sostituti di una riga, cottura, variante | per id (`get_recipe`, `recipe_nutrition`, `api/substitutions._line`, `api/cooking`, `draft_variant`) | incluse, per id; il frontend decide cosa mostrare (Task 8) | Task 5 |
| 13 | Grammi per unità (`decide_grams`) | `services/unit_grams.py` | incluse: guarda le unità delle righe, non elenca ricette | — |
| 14 | Import: annulla, materializza, rilegge i costi, rimuove il seme | `recipe_import/undo.py`, `materialize.py`, `cli/reread_costs.py`, `cli/drop_seed_recipes.py` | **non toccate**: lavorano solo su ricette con una `RecipeImport` o con `source = 'dataset'` del seme; una ricetta di un pasto nasce `manual` (o `ai`, piano 3) e senza pagina d'import | — |

Se trovi un altro punto che seleziona da `recipes` o da `recipe_ingredients` per elencare (`grep -rn "select(Recipe\|join(Recipe\|from_(Recipe" backend/app`), aggiungilo alla tabella nel report e dagli un test qui: è esattamente il buco che questo task chiude.

**Files:**
- Modify: `backend/app/services/recipe_search.py` (le quattro funzioni della tabella), `backend/app/repositories/recipes.py` (`recipe_categories`; `create_recipe` riceve `in_book`), `backend/app/repositories/substitutions.py` (`_usage`), `backend/app/services/registry.py` (`RecipeRef`, `recipes_using`), `backend/app/api/refusals.py` (il ramo `RecipesInUse`), `backend/tests/api/test_registry_ingredients.py` (solo le due asserzioni dette sotto)
- Create: `backend/tests/api/test_recipes_out_of_book_lists.py`, `backend/tests/repositories/test_substitution_voices_pasti.py`, `backend/tests/services/test_registry_pasti.py`

**Interfaces:**
- Consumes: `Recipe.in_book`, `in_the_book()` (Task 1).
- Produces: `create_recipe(..., in_book: bool = True) -> Recipe` (ultimo argomento per nome); `RecipeRef.from_meal: bool = False` (vero quando la ricetta non è nel ricettario; il default tiene valido `RecipeRef(id=…, title=…)` dei test di oggi); il 409 `non_food_in_recipes` porta in ogni ricetta di `recipes` anche `"from_meal": bool`.

- [ ] **Step 1: I test che falliscono.** `tests/api/test_recipes_out_of_book_lists.py` ricalca `tests/api/test_recipes_archived_lists.py` (stessi aiutanti, ricopiati: i file di test non si importano fra loro), con le ricette dei pasti al posto delle archiviate: una ricetta dei pasti si fa con `create_recipe(..., in_book=False)`, e «salvarla nel ricettario» qui vuol dire scrivere `in_book = True` e fare `flush` (la rotta arriva nel Task 5). I test, con le asserzioni:
  1. `test_lo_sfoglio_esclude_le_ricette_dei_pasti_e_le_ritrova_salvate`: due ricette con tutti i filtri dello sfoglio validi (come la fixture `ricettario`), una fuori → `_titoli(…)` ha solo l'altra e `X-Total-Count` è `"1"`; messa `in_book = True` → tutte e due e `"2"`.
  2. `test_lo_sfoglio_esclude_le_ricette_dei_pasti_prima_della_pagina`: tre ricette fuori titolate «A …», una viva «Z …», `?limit=1` → la pagina è «Z …».
  3. `test_i_cucinabili_non_contano_le_ricette_dei_pasti`: una ricetta fuori cucinabile (riga primaria su un ingrediente `available` in dispensa) → `?max_missing=0` non la dà, e `X-Total-Count` non la conta.
  4. `test_la_ricerca_testuale_esclude_le_ricette_dei_pasti`: «Frittata di spinaci» fuori e «Frittata di zucchine» dentro → `q=frittata` dà solo la seconda.
  5. `test_la_ricerca_testuale_le_esclude_prima_della_piscina`: `CANDIDATE_POOL + 5` ricette fuori «Zuppa zuppa zuppa N», una viva «Zuppa di pane» → `q=zuppa` dà `{"Zuppa di pane"}`.
  6. `test_la_ricerca_semantica_esclude_le_ricette_dei_pasti` e 7. `test_la_ricerca_semantica_le_esclude_prima_della_piscina`: come i due gemelli delle archiviate (fixture `query_nel_punto_zero`, vettori a distanza nota), con le ricette fuori al posto delle archiviate.
  8. `test_la_ricerca_semantica_non_si_accende_per_una_ricetta_di_un_pasto`: l'unico vettore del database è su una ricetta fuori → `GET /api/v1/recipes/search-mode` dà `{"semantic": false}`.
  9. `test_le_categorie_non_contano_le_ricette_dei_pasti`: categoria «Frittate» solo su una ricetta fuori → `GET /api/v1/recipes/categories` non la contiene.
  10. `test_reindex_scrive_il_vettore_anche_delle_ricette_dei_pasti`: una ricetta fuori senza vettore → `await reindex(db_session)` vale `1` e la ricetta ha un vettore.

  `tests/repositories/test_substitution_voices_pasti.py`:
  11. `test_un_ingrediente_solo_in_una_ricetta_di_un_pasto_non_e_una_voce`: l'ingrediente compare solo in una ricetta fuori → non è fra le voci di `pending_voices(db_session)`.
  12. `test_la_scheda_dell_ingrediente_non_conta_le_ricette_dei_pasti`: lo stesso ingrediente in una ricetta del ricettario e in una fuori, stessa categoria → `ingredient_view` ha quel contesto con `recipes == 1`.

  `tests/services/test_registry_pasti.py`:
  13. `test_recipes_using_conta_e_segna_le_ricette_dei_pasti`: una ricetta dentro, una fuori → `count == 2`, e la fuori ha `from_meal is True`, la dentro `False`.
  14. `test_ingredient_usage_conta_le_righe_delle_ricette_dei_pasti`: → `recipes == 2`.
  15. `test_la_fusione_sposta_anche_le_righe_delle_ricette_dei_pasti`: la riga della ricetta fuori sul perdente passa al vincitore (`merge_ingredients`, come in `tests/services/test_registry_merge.py`).
  16. `test_il_rifiuto_del_non_alimentare_nomina_la_ricetta_del_pasto` (con `logged_client`): l'ingrediente sta solo in una ricetta fuori; `PATCH /api/v1/ingredients/{id}` con `{"category": "casa"}` → 409, `code == "non_food_in_recipes"`, `recipes == [{"id": …, "title": …, "archived": False, "from_meal": True}]`.

- [ ] **Step 2: Fallisce.** Il comando di pytest con i tre file nuovi. Expected: FAIL (`create_recipe` non accetta `in_book`; poi le esclusioni mancano).

- [ ] **Step 3: Le modifiche.**
  - `create_recipe`: il parametro `in_book: bool = True`, passato a `Recipe(...)`.
  - Le sei funzioni escluse della tabella: la condizione `Recipe.archived_at.is_(None)` diventa `in_the_book()` nello stesso punto della query (dentro il `where` che precede `limit`/`having`/`group_by`); i commenti che parlano delle archiviate nominano anche le ricette dei pasti. `reindex` non cambia: un commento accanto al filtro dice perché include le ricette dei pasti (decisione 20).
  - `RecipeRef`: il campo `from_meal: bool = False`, con un commento («fuori dal ricettario: la ricetta di un pasto (spec §4.2); conta per lo stesso motivo delle eliminate»); `recipes_using` seleziona anche `Recipe.in_book` e lo passa (`from_meal=not row.in_book`).
  - `api/refusals.py`: nel ramo `RecipesInUse`, ogni ricetta porta anche `"from_meal": recipe.from_meal`.
  - `tests/api/test_registry_ingredients.py`: le due asserzioni con il dizionario `{"id": str(anagrafica["risotto"]), "title": "Risotto al burro", "archived": …}` ricevono `"from_meal": False`. **Sono gli unici test di oggi che cambiano in questo piano.**

- [ ] **Step 4: Passa.** Il comando di pytest con i tre file nuovi, poi la suite intera. Expected: PASS; la suite tutta verde.

- [ ] **Step 5: Commit**
  ```bash
  git add backend/app backend/tests
  git commit -m "feat(pasti): le ricette fuori dal ricettario escluse da sfoglio, ricerche, cucinabili, categorie e sostituti, contate nell'Anagrafica"
  ```

---

### Task 3: Le regole dei pasti — dominio, letture, scritture, copia

**Files:**
- Create: `backend/app/domain/meals.py`, `backend/app/repositories/meals.py`, `backend/app/services/meals.py`, `backend/tests/domain/test_meals.py`, `backend/tests/services/test_meals.py`
- Modify: `backend/app/repositories/recipes.py` (`copy_recipe`, dopo `create_recipe`)

**Interfaces:**
- Consumes: `Meal`, `Recipe.in_book` (Task 1); `create_recipe(in_book=…)` (Task 2); `today_in_pantry` da `app.domain.rules`.
- Produces, in `app.domain.meals` (puro, niente database):
  - `class MealSlot(StrEnum)`: `LUNCH = "lunch"`, `DINNER = "dinner"`; `class MealStatus(StrEnum)`: `DRAFT = "draft"`, `OFFICIAL = "official"`.
  - `LEFTOVER_WINDOW_DAYS = 3`.
  - `week_bounds(day: date) -> tuple[date, date]` — il lunedì e la domenica della settimana di `day`.
  - `slot_rank(slot: MealSlot) -> int` — pranzo 0, cena 1.
  - `is_before(day: date, slot: MealSlot, other_day: date, other_slot: MealSlot) -> bool` — il primo posto viene strettamente prima del secondo.
  - `is_unrecorded(status: MealStatus, day: date, today: date) -> bool` — bozza con `day < today`.
- Produces, in `app.repositories.meals` (letture; caricano `recipe` e `leftover_of` con `selectinload`, e `leftover_of.recipe` anche lui):
  - `get_meal(session, meal_id: uuid.UUID) -> Meal | None`
  - `meal_at(session, day: date, slot: MealSlot) -> Meal | None`
  - `meals_between(session, start: date, end: date) -> list[Meal]` — estremi compresi, in ordine di giorno e poi pranzo prima di cena.
  - `meal_of_recipe(session, recipe_id: uuid.UUID) -> Meal | None`
  - `leftover_candidates(session, day: date, slot: MealSlot) -> list[Meal]` — i pasti da `day - LEFTOVER_WINDOW_DAYS` fino a prima del posto, non avanzi, non fuori casa, dal più recente.
- Produces, in `app.repositories.recipes`: `copy_recipe(session, source: Recipe, *, in_book: bool = False) -> Recipe` — la decisione 16, passando da `create_recipe` (quindi dall'imbuto) con le righe di `source` come `IngredientLine` (ingrediente, ruolo, `quantity_text`, `note`); il vettore copiato, non ricalcolato.
- Produces, in `app.services.meals` (scrivono e fanno `flush`, mai `commit`: il commit è della rotta):
  - `class MealRefusalCode(StrEnum)`: `SLOT_TAKEN = "slot_taken"`, `HAS_RECIPE = "has_recipe"`, `NO_RECIPE_HERE = "no_recipe_here"`, `BAD_LEFTOVER = "bad_leftover"`, `STAYS_OFFICIAL = "stays_official"`, `RECIPE_ARCHIVED = "recipe_archived"`.
  - `class MealRefusal(Exception)`: `code: MealRefusalCode`, `message: str`, `occupant: Meal | None = None`.
  - `create_meal(session, *, day: date, slot: MealSlot, dish: str, sides: str | None = None, away: bool = False, status: MealStatus = MealStatus.OFFICIAL, leftover_of_id: uuid.UUID | None = None, replace: bool = False) -> Meal`
  - `update_meal(session, meal: Meal, changes: Mapping[str, object], *, replace: bool = False) -> Meal` — chiavi ammesse: `dish`, `sides`, `away`, `day`, `slot`, `status`.
  - `delete_meal(session, meal: Meal) -> None`
  - `release_recipe(session, meal: Meal) -> None` — stacca la ricetta; se non è nel ricettario la archivia (`archived_at = now`), se lo è la lascia com'è.
  - `check_can_take_recipe(meal: Meal) -> None` — solleva `MealRefusal` se il pasto ha già una ricetta, è un avanzo, è fuori casa o è una bozza.
  - `link_recipe(session, meal: Meal, recipe: Recipe) -> None` — `check_can_take_recipe`, poi `meal.recipe_id = recipe.id`.
  - `copy_recipe_to_meal(session, meal: Meal, source: Recipe) -> Recipe` — `check_can_take_recipe`; rifiuta una `source` archiviata; `copy_recipe`; `link_recipe`.
- Le frasi dei rifiuti, esatte:
  - `SLOT_TAKEN`: «C'è già «{dish}» in questo posto.» (con `occupant`)
  - `HAS_RECIPE`: «Il pasto ha già una ricetta.»
  - `NO_RECIPE_HERE`: per un avanzo «Un avanzo usa la ricetta del pasto da cui viene.»; fuori casa «Un pasto fuori casa non ha una ricetta.»; bozza «È una bozza: la ricetta arriva quando diventa ufficiale.»
  - `BAD_LEFTOVER`: «Un avanzo viene da un pasto cucinato prima, che non sia a sua volta un avanzo.»
  - `STAYS_OFFICIAL`: «Un pasto ufficiale non torna bozza.»
  - `RECIPE_ARCHIVED`: «Questa ricetta è stata eliminata: ripristinala prima di copiarla.»

Le regole di `create_meal` e `update_meal`, che i test fissano: un posto occupato da un altro pasto è `SLOT_TAKEN` con l'occupante, a meno di `replace=True`, che prima elimina l'occupante (con `delete_meal`, quindi `release_recipe`) e fa `flush`, poi scrive; l'avanzo deve esistere, venire prima del posto (`is_before`), non essere un avanzo né fuori casa (altrimenti `BAD_LEFTOVER`); `away=True` chiama `release_recipe` e toglie `leftover_of_id`; `status` può solo passare da `draft` a `official` (il contrario è `STAYS_OFFICIAL`); spostare un avanzo controlla di nuovo `is_before`. `dish` e `sides` arrivano già ripuliti dallo schema (Task 4).

- [ ] **Step 1: I test del dominio.** `tests/domain/test_meals.py`:
  - `test_week_bounds`, parametrizzato: `date(2026,11,10)` (lunedì) → `(date(2026,11,10), date(2026,11,16))`; `date(2026,11,16)` (domenica) → stesso; `date(2026,11,12)` → stesso; `date(2026,12,31)` → `(date(2026,12,28), date(2027,1,3))`.
  - `test_is_before`, parametrizzato: (10 pranzo, 10 cena) → `True`; (10 cena, 10 pranzo) → `False`; (10 cena, 10 cena) → `False`; (9 cena, 10 pranzo) → `True`; (11 pranzo, 10 cena) → `False`.
  - `test_is_unrecorded`, parametrizzato con `today = date(2026,11,12)`: bozza dell'11 → `True`; bozza del 12 → `False`; bozza del 13 → `False`; ufficiale dell'11 → `False`.
  - `test_la_settimana_di_oggi_e_quella_di_roma`: `week_bounds(today_in_pantry(datetime(2026,11,15,23,30,tzinfo=UTC)))` → `(date(2026,11,16), date(2026,11,22))` (a Roma è già lunedì).

- [ ] **Step 2: I test del servizio.** `tests/services/test_meals.py` (fixture: due ingredienti alimentari, una ricetta del ricettario «Frittata» con due righe e un vettore, `create_recipe`; i pasti si fanno con `create_meal`). Ogni test fa `flush` e rilegge dal database, non dall'oggetto in memoria:
  1. `test_un_pasto_scritto_a_mano_nasce_ufficiale`: `status == "official"`, `away is False`, `recipe_id is None`.
  2. `test_un_posto_occupato_rifiuta_e_nomina_chi_c_e`: secondo pasto sullo stesso posto → `MealRefusal` con `code == SLOT_TAKEN`, `occupant.id` il primo, `message == "C'è già «Pizza» in questo posto."`.
  3. `test_sostituire_toglie_il_vecchio_e_archivia_la_sua_ricetta_fuori_dal_ricettario`: il vecchio ha una copia della Frittata; `replace=True` → `get_meal(vecchio)` è `None`, la copia ha `archived_at` non nullo, il nuovo occupa il posto.
  4. `test_un_avanzo_viene_da_un_pasto_prima`: cena del 10 con ricetta, avanzo al pranzo dell'11 → `leftover_of_id` è la cena.
  5. `test_un_avanzo_rifiutato`, parametrizzato, per un avanzo al pranzo dell'11: origine alla cena dell'11 (dopo il posto); origine che è a sua volta un avanzo; origine fuori casa; origine inesistente (`uuid4()`) → `BAD_LEFTOVER`, e nessun pasto scritto.
  6. `test_spostare_su_un_posto_vuoto`: `update_meal(m, {"day": date(2026,11,13), "slot": "lunch"})` → il pasto è lì, il vecchio posto è libero (`meal_at` è `None`).
  7. `test_spostare_su_un_posto_occupato_chiede_la_sostituzione_e_poi_sostituisce`: senza `replace` → `SLOT_TAKEN` e niente è cambiato; con `replace=True` → l'occupante non c'è più e il pasto spostato sta al suo posto, **senza** `IntegrityError` al `flush`.
  8. `test_fuori_casa_toglie_la_ricetta_e_l_avanzo`: un pasto con una copia fuori dal ricettario e un avanzo con origine → `away=True` sul primo: `recipe_id is None` e copia archiviata; sul secondo: `leftover_of_id is None`.
  9. `test_fuori_casa_lascia_nel_ricettario_la_ricetta_salvata`: la copia con `in_book = True` → dopo `away=True` la ricetta ha `archived_at is None` e `in_book is True`.
  10. `test_una_bozza_diventa_ufficiale_e_non_torna_indietro`: `create_meal(status=DRAFT)` → `update_meal({"status": "official"})` ufficiale; `update_meal({"status": "draft"})` → `STAYS_OFFICIAL`.
  11. `test_eliminare_archivia_la_ricetta_fuori_dal_ricettario`: → il pasto non c'è, la copia ha `archived_at` non nullo.
  12. `test_eliminare_lascia_la_ricetta_del_ricettario`: copia con `in_book = True` → resta viva, `in_book is True`.
  13. `test_eliminare_il_pasto_d_origine_lascia_l_avanzo_senza_legame`: → l'avanzo c'è, `leftover_of_id is None`, il piatto è quello di prima.
  14. `test_la_copia_e_una_ricetta_nuova_fuori_dal_ricettario`: `copy_recipe_to_meal` → id diverso; `in_book is False`; `source == "manual"`; `source_ref is None`; `derived_from_id is None`; titolo, procedimento, porzioni, categoria, costo, foto, tempi e vettore uguali; le righe uguali per `(ingredient_id, role, quantity_text, note, quantity_value)`; `meal.recipe_id` è la copia.
  15. `test_la_copia_non_tocca_l_originale`: l'originale ha le stesse righe di prima, `in_book is True`, e nessun pasto lo punta (`meal_of_recipe` è `None`).
  16. `test_non_si_copia_una_ricetta_eliminata`: originale archiviata → `RECIPE_ARCHIVED`, il pasto resta senza ricetta.
  17. `test_chi_non_puo_ricevere_una_ricetta`, parametrizzato: pasto che ha già una ricetta → `HAS_RECIPE`; avanzo, fuori casa, bozza → `NO_RECIPE_HERE` con la frase del caso.
  18. `test_gli_avanzi_possibili`: pasti il 7 (fuori dalla finestra), il 9 cena, il 10 pranzo fuori casa, il 10 cena avanzo, l'11 pranzo; `leftover_candidates(11, cena)` → `[11 pranzo, 9 cena]`.
  19. `test_meals_between_in_ordine`: cena del 10, pranzo dell'11, pranzo del 10, cena del 17 → `meals_between(10, 16)` dà pranzo 10, cena 10, pranzo 11.

- [ ] **Step 3: Falliscono.** Il comando di pytest con `tests/domain/test_meals.py tests/services/test_meals.py`. Expected: FAIL (`ModuleNotFoundError: app.domain.meals`).

- [ ] **Step 4: Il codice**, con le firme del blocco Interfaces. `meals_between` ordina in SQL con `Meal.day` e un `case` su `slot` (pranzo prima); `leftover_candidates` filtra in SQL la finestra e i due segni e scarta in Python i posti non prima (`is_before`), poi ordina dal più recente. `copy_recipe` legge la `source` con le righe caricate (`get_recipe`).

- [ ] **Step 5: Passano.** Lo stesso comando, poi la suite intera. Expected: PASS.

- [ ] **Step 6: Commit**
  ```bash
  git add backend/app/domain/meals.py backend/app/repositories/meals.py backend/app/services/meals.py backend/app/repositories/recipes.py backend/tests/domain/test_meals.py backend/tests/services/test_meals.py
  git commit -m "feat(pasti): le regole dei pasti — posto, avanzo, fuori casa, bozza, la ricetta che si libera e la copia dal ricettario"
  ```

---

### Task 4: Le rotte dei pasti

**Files:**
- Create: `backend/app/schemas/meal.py`, `backend/app/api/meals.py`, `backend/tests/api/test_meals.py`
- Modify: `backend/app/api/refusals.py` (una funzione nuova), `backend/app/main.py` (`app.include_router(meals.router)` accanto agli altri)

**Interfaces:**
- Consumes: Task 3 per intero.
- Produces, in `app.schemas.meal`:
  - `MealRefOut`: `id`, `day: date`, `slot: MealSlot`, `dish: str`, `recipe_id: uuid | None`.
  - `MealRecipeOut`: `id`, `title: str`, `in_book: bool`.
  - `MealOut`: `id`, `day: date`, `slot: MealSlot`, `week: date` (il lunedì di `day`), `dish: str`, `sides: str | None`, `away: bool`, `status: MealStatus`, `unrecorded: bool`, `recipe: MealRecipeOut | None`, `leftover_of: MealRefOut | None`.
  - `WeekOut`: `monday: date`, `sunday: date`, `today: date`, `previous: date`, `next: date` (i lunedì accanto), `days: list[date]` (i sette giorni da `monday`, così il frontend non fa aritmetica di date), `meals: list[MealOut]`.
  - `MealCreate`: `day: date`, `slot: MealSlot`, `dish: str` (ripulito degli spazi ai bordi, 1–200 caratteri dopo la pulizia), `sides: str | None` (ripulito; vuoto → `None`; ≤ 200), `away: bool = False`, `status: MealStatus = OFFICIAL`, `leftover_of_id: uuid | None = None`, `replace: bool = False`.
  - `MealUpdate`: gli stessi campi tranne `leftover_of_id`, tutti facoltativi; si usano solo quelli mandati (`model_fields_set`); `replace: bool = False` non è un cambio.
  - `RecipeCopyIn`: `recipe_id: uuid`.
- Produces, in `app.api.refusals`: `meal_refusal_response(exc: MealRefusal) -> JSONResponse` — corpo `{"detail": exc.message, "code": exc.code}` più `"occupant": MealOut` per `SLOT_TAKEN`; stato **409** per `SLOT_TAKEN`, `HAS_RECIPE`, `NO_RECIPE_HERE`, `RECIPE_ARCHIVED`; **422** per `BAD_LEFTOVER`, `STAYS_OFFICIAL`.
- Produces, in `app.api.meals` (`router = APIRouter(prefix="/api/v1/meals")`, dietro l'accesso come le altre rotte), con `meal_out(meal: Meal, today: date) -> MealOut` (i piani 3 e 4 la riusano). Le rotte con un nome fisso stanno **sopra** `/{meal_id}`:
  - `GET /week?of=YYYY-MM-DD` (facoltativo; assente = `today_in_pantry()`) → `WeekOut`.
  - `GET /leftover-candidates?day=…&slot=…` → `list[MealOut]`.
  - `GET /{meal_id}` → `MealOut`; 404 `«pasto inesistente»`.
  - `POST ""` (`MealCreate`) → 201 `MealOut`.
  - `PATCH /{meal_id}` (`MealUpdate`) → `MealOut`.
  - `DELETE /{meal_id}` → 204.
  - `POST /{meal_id}/recipe/copy` (`RecipeCopyIn`) → 201 `MealOut`; la ricetta d'origine inesistente → 404 `«ricetta inesistente»`.
  Ogni rotta che scrive fa `commit` dopo il servizio; un `MealRefusal` passa da `meal_refusal_response` dopo il `rollback`, leggendo l'occupante **prima** del rollback (come dice `refusals.py` per gli ostacoli).

- [ ] **Step 1: I test che falliscono.** `tests/api/test_meals.py`, con `logged_client` (i pasti di contorno si fanno con `create_meal` e `commit`):
  1. `test_la_settimana_di_oggi`: `GET /api/v1/meals/week` → `today == today_in_pantry().isoformat()`, `monday <= today <= sunday`, `monday` è un lunedì, `previous` e `next` a 7 giorni.
  2. `test_la_settimana_di_una_data_e_i_suoi_pasti_in_ordine`: pasti cena 10, pranzo 10, pranzo 17 → `?of=2026-11-12` dà `monday == "2026-11-10"`, `sunday == "2026-11-16"`, `days` da `"2026-11-10"` a `"2026-11-16"` (sette), i pasti in ordine `[pranzo 10, cena 10]`, ognuno con `week == "2026-11-10"`.
  3. `test_una_bozza_passata_e_non_registrata`: bozza del 2026-01-05 → `unrecorded is True`; ufficiale lo stesso giorno → `False`.
  4. `test_scrivere_un_pasto_a_mano`: `POST` `{"day": "2026-11-11", "slot": "dinner", "dish": "  Frittata di spinaci  ", "sides": "piadina · banana"}` → 201, `dish == "Frittata di spinaci"`, `status == "official"`, `recipe is None`, `leftover_of is None`; con `"sides": "  "` → `sides is None`.
  5. `test_un_piatto_vuoto_e_422`, parametrizzato su `""` e `"   "`.
  6. `test_un_posto_occupato_e_409_con_chi_c_e`: → 409, `code == "slot_taken"`, `detail == "C'è già «Pizza» in questo posto."`, `occupant.dish == "Pizza"`.
  7. `test_correggere_e_spostare`: `PATCH` `{"dish": "Frittata di zucchine", "sides": null}` → cambiati; `PATCH` `{"day": "2026-11-13", "slot": "lunch"}` → spostato, `week` invariata.
  8. `test_spostare_su_un_posto_occupato_con_replace`: senza → 409 con l'occupante; con `"replace": true` → 200, `GET` dell'occupante → 404.
  9. `test_eliminare_e_204_e_la_ricetta_fuori_dal_ricettario_si_archivia`: pasto con una copia → `DELETE` 204; `GET /api/v1/recipes/{copia}` ha `archived_at` non nullo.
  10. `test_copiare_una_ricetta_del_ricettario_nel_pasto`: → 201, `recipe.title` uguale, `recipe.in_book is False`, `recipe.id` diverso dall'originale; `GET /api/v1/recipes/search?q=<titolo>` dà ancora **un** risultato, l'originale.
  11. `test_copiare_in_un_pasto_che_ha_gia_la_ricetta_e_409`: → 409, `code == "has_recipe"`.
  12. `test_gli_avanzi_possibili_dalla_rotta`: come il test 18 del Task 3, dalla rotta.
  13. `test_un_pasto_inesistente_e_404`, parametrizzato su `GET`, `PATCH`, `DELETE` di un `uuid4()`.
  14. `test_senza_accesso_401`: `client` senza accesso, `GET /api/v1/meals/week` → 401.

- [ ] **Step 2: Fallisce.** Il comando di pytest con `tests/api/test_meals.py`. Expected: FAIL (404 sulle rotte).

- [ ] **Step 3: Schemi, rotte, rifiuto, registrazione del router**, come nel blocco Interfaces.

- [ ] **Step 4: Passa.** Lo stesso file, poi la suite intera. Expected: PASS.

- [ ] **Step 5: Commit**
  ```bash
  git add backend/app/schemas/meal.py backend/app/api/meals.py backend/app/api/refusals.py backend/app/main.py backend/tests/api/test_meals.py
  git commit -m "feat(pasti): le rotte della settimana e dei pasti, la copia di una ricetta nel pasto"
  ```

---

### Task 5: La ricetta di un pasto, dalla parte delle ricette

**Files:**
- Modify: `backend/app/schemas/recipe.py` (`RecipeCreate`, `RecipeUpdate`, `RecipeOut`), `backend/app/api/recipes.py` (`_to_out`, `create`, `update`)
- Create: `backend/tests/api/test_recipes_meal.py`

**Interfaces:**
- Consumes: Task 3 (`get_meal`, `meal_of_recipe`, `check_can_take_recipe`, `link_recipe`, `MealRefusal`), Task 4 (`meal_refusal_response`, `MealRefOut`).
- Produces:
  - `RecipeCreate.meal_id: uuid | None = None` — presente: il pasto si cerca (404 `«pasto inesistente»`), `check_can_take_recipe` prima di scrivere (rifiuto con `meal_refusal_response`, e **nessuna ricetta creata**), la ricetta nasce `in_book=False` e si lega col pasto nella stessa transazione.
  - `RecipeUpdate.in_book: bool | None = Field(default=None, strict=True)` — con una ricetta eliminata (prima o dopo questa richiesta) è 409 `RECIPE_ARCHIVED`, come il costo; `False` su una ricetta senza pasto è 409 con `«Questa ricetta non è di un pasto: per toglierla dal ricettario eliminala.»`.
  - Ripristinare (`archived: false`) una ricetta con `in_book` falso e nessun pasto la rimette `in_book = True` (decisione 18).
  - `RecipeOut.in_book: bool = True` e `RecipeOut.meal: MealRefOut | None = None`, riempiti da `_to_out` (`meal_of_recipe`).

- [ ] **Step 1: I test che falliscono.** `tests/api/test_recipes_meal.py` (corpo della ricetta come in `tests/api/test_recipes_note.py`, con un ingrediente alimentare):
  1. `test_scrivere_la_ricetta_di_un_pasto`: `POST /api/v1/recipes` con `meal_id` → 201, `in_book is False`, `meal.id` è il pasto; `GET /api/v1/meals/{id}` ha `recipe.id` uguale; `GET /api/v1/recipes/search?q=<titolo>` vuoto.
  2. `test_la_ricetta_non_si_scrive_per_chi_non_puo_riceverla`, parametrizzato su pasto con ricetta (409 `has_recipe`), avanzo, fuori casa, bozza (409 `no_recipe_here`) → e il numero di righe di `recipes` è quello di prima.
  3. `test_un_pasto_inesistente_e_404_e_niente_si_crea`.
  4. `test_salva_e_togli_dal_ricettario`: `PATCH` `{"in_book": true}` → `in_book is True` e la ricerca la trova; `{"in_book": false}` → non la trova più.
  5. `test_togliere_dal_ricettario_una_ricetta_senza_pasto_e_409`: ricetta del ricettario qualunque → 409 con la frase esatta.
  6. `test_il_ricettario_di_una_ricetta_eliminata_non_si_cambia`: eliminata → `PATCH {"in_book": true}` 409.
  7. `test_ripristinare_una_ricetta_senza_pasto_la_rimette_nel_ricettario`: pasto con ricetta scritta, `DELETE` del pasto, `PATCH {"archived": false}` → `in_book is True`, `meal is None`, la ricerca la trova.
  8. `test_ripristinare_la_ricetta_di_un_pasto_la_lascia_fuori`: ricetta di un pasto eliminata dal `PATCH {"archived": true}` e ripristinata → `in_book is False`, `meal` presente.
  9. `test_il_dettaglio_dice_ricettario_e_pasto`: una ricetta del ricettario → `in_book is True`, `meal is None`; una ricetta di un pasto salvata nel ricettario → `in_book is True`, `meal.dish` è il piatto.
  10. `test_la_modifica_della_ricetta_di_un_pasto_la_lascia_fuori_dal_ricettario`: `PUT /api/v1/recipes/{id}` con un titolo nuovo → 200, `in_book is False`, `meal` presente.

- [ ] **Step 2: Fallisce.** Il comando di pytest con il file nuovo. Expected: FAIL.

- [ ] **Step 3: Le modifiche** del blocco Interfaces. In `create`, il pasto si cerca e si controlla **prima** di `_writing_recipe`, e `link_recipe` sta dentro lo stesso `async with` di `create_recipe`, prima del `commit`.

- [ ] **Step 4: Passa.** Il file nuovo, poi la suite intera. Expected: PASS.

- [ ] **Step 5: Commit**
  ```bash
  git add backend/app/schemas/recipe.py backend/app/api/recipes.py backend/tests/api/test_recipes_meal.py
  git commit -m "feat(pasti): la ricetta scritta per un pasto, «Salva nel ricettario» e «Togli dal ricettario», il ripristino che non la perde"
  ```

---

### Task 6: La settimana nel frontend

**Files:**
- Modify: `frontend/src/domain/types.ts` (tipi nuovi in fondo; `RecipeDetail` riceve i due campi facoltativi; la ricetta del rifiuto `non_food_in_recipes` riceve `from_meal?: boolean`), `frontend/src/components/ui/icons.ts` (una sezione `// pasti`), `frontend/src/components/TabBar.tsx`, `frontend/src/components/TabBar.test.tsx`, `frontend/src/App.tsx`
- Create: `frontend/src/features/meals/api.ts`, `frontend/src/features/meals/format.ts`, `format.test.ts`, `WeekScreen.tsx`, `WeekScreen.test.tsx`

**Interfaces:**
- Consumes: le rotte del Task 4.
- Produces, in `domain/types.ts`:
  ```ts
  export type MealSlot = "lunch" | "dinner";
  export type MealStatus = "draft" | "official";
  export interface MealRef { id: string; day: string; slot: MealSlot; dish: string; recipe_id: string | null }
  export interface Meal {
    id: string; day: string; slot: MealSlot; week: string; dish: string; sides: string | null;
    away: boolean; status: MealStatus; unrecorded: boolean;
    recipe: { id: string; title: string; in_book: boolean } | null;
    leftover_of: MealRef | null;
  }
  export interface MealWeek { monday: string; sunday: string; today: string; previous: string; next: string; days: string[]; meals: Meal[] }
  export interface MealBody { day: string; slot: MealSlot; dish: string; sides: string | null; away: boolean; leftover_of_id: string | null; replace?: boolean }
  export type MealPatch = Partial<Pick<MealBody, "day" | "slot" | "dish" | "sides" | "away">> & { status?: "official"; replace?: boolean };
  ```
  e in `RecipeDetail`: `in_book?: boolean; meal?: MealRef | null;` (decisione 22).
- Produces, in `features/meals/api.ts`: `fetchWeek(of: string | null): Promise<MealWeek>`; `fetchMeal(id): Promise<Meal>`; `fetchLeftoverCandidates(day, slot): Promise<Meal[]>`; `createMeal(body: MealBody): Promise<Meal>`; `updateMeal(id, patch: MealPatch): Promise<Meal>`; `deleteMeal(id): Promise<void>`; `copyRecipeToMeal(mealId, recipeId): Promise<Meal>`. Chiavi di cache: `["meals", "week", of]`, `["meals", "meal", id]`, `["meals", "leftovers", day, slot]`; chi scrive invalida `["meals"]`.
- Produces, in `features/meals/format.ts` (solo forma, con `Intl.DateTimeFormat("it-IT", { timeZone: "UTC", … })` su `"<giorno>T00:00:00Z"`, così il giorno non scivola col fuso del telefono): `SLOT_LABELS: Record<MealSlot, string>` = `{ lunch: "Pranzo", dinner: "Cena" }`; `dayLabel(day: string): string` («Lunedì 10»); `longDayLabel(day: string): string` («martedì 11 novembre»); `weekLabel(monday: string, sunday: string): string` («10–16 novembre», «27 ottobre – 2 novembre», «29 dicembre 2025 – 4 gennaio 2026» quando cambia l'anno).
- Produces: la rotta `/pasti` (`WeekScreen`, `?settimana=YYYY-MM-DD` = qualunque giorno della settimana da aprire); la scheda `{ to: "/pasti", label: "Pasti", icon: IconCalendarWeek }` in fondo a `TABS`, con la griglia a `grid-cols-4`.

**La schermata** (`WeekScreen`): titolo `h1` «Pasti»; sotto, una riga con il pulsante ‹ (`aria-label` «Settimana prima»), l'intervallo (`weekLabel`) e › («Settimana dopo»), che portano a `/pasti?settimana=<previous|next>`; se `today` non sta fra `monday` e `sunday`, un collegamento «Torna a oggi» a `/pasti`. Poi i sette giorni di `week.days` (li dà il backend: nessuna aritmetica di date nel client). Ogni giorno è una `Card` con `dayLabel`; il giorno uguale a `today` ha il fondo `bg-brand-tint`, la parola «oggi» accanto all'etichetta e `aria-current="date"`. Dentro, «Pranzo» e «Cena» (`SLOT_LABELS`, testo piccolo `text-ink-soft`) e per ciascuno:
- un pasto: un collegamento a `/pasti/<id>` con il piatto e, sotto, gli accompagnamenti; accanto, i segni come `Chip`: «Fuori casa» se `away`, «Non registrata» se `unrecorded`, altrimenti «Bozza» se `status === "draft"`, «Avanzo» se `leftover_of`;
- un posto vuoto: un collegamento «+ da pianificare» a `/pasti/nuovo?giorno=<giorno>&posto=<slot>`.
In fondo, un commento che segna il posto di «Pianifica con Claude» (piano 4). Caricamento ed errore come nelle altre schermate (l'errore con «Riprova»). Ogni bersaglio alto almeno 44 px (`min-h-11`).

- [ ] **Step 1: I test che falliscono.**
  - `format.test.ts`: `dayLabel("2026-11-10") === "Lunedì 10"`; `longDayLabel("2026-11-11") === "martedì 11 novembre"`; `weekLabel("2026-11-10","2026-11-16") === "10–16 novembre"`; `weekLabel("2026-10-27","2026-11-02") === "27 ottobre – 2 novembre"`; `weekLabel("2025-12-29","2026-01-04") === "29 dicembre 2025 – 4 gennaio 2026"`.
  - `TabBar.test.tsx`, un caso nuovo: su `/pasti/abc` il collegamento «Pasti» ha `aria-current="page"`, e nessun altro.
  - `WeekScreen.test.tsx` (rotte `/pasti`, `/pasti/:id`, `/pasti/nuovo` in un `MemoryRouter`; `fetch` sostituito come in `RecipeEditScreen.test.tsx`), con una settimana `monday "2026-11-10"`, `today "2026-11-12"`, `days` dal 10 al 16 e quattro pasti (cena del 10 con accompagnamenti «piadina · banana»; pranzo dell'11 fuori casa; cena dell'11 bozza con `unrecorded: true`; pranzo del 12 avanzo della cena del 10):
    1. «mostra sette giorni da lunedì, con pranzo e cena»: sette etichette da «Lunedì 10» a «Domenica 16»; quattordici posti fra pasti e «+ da pianificare».
    2. «oggi è evidenziato»: l'elemento con `aria-current="date"` contiene «Giovedì 12» e «oggi».
    3. «un posto vuoto porta al modulo»: il primo «+ da pianificare» ha `href` `/pasti/nuovo?giorno=2026-11-10&posto=lunch`.
    4. «un pasto mostra piatto, accompagnamenti e segni»: il collegamento della cena del 10 porta a `/pasti/<id>` e contiene il piatto e «piadina · banana»; si leggono «Fuori casa», «Non registrata», «Avanzo».
    5. «le frecce cambiano settimana»: «Settimana dopo» porta a `?settimana=2026-11-17` e la nuova richiesta ha `of=2026-11-17`; lì compare «Torna a oggi».
    6. «un errore offre Riprova»: la prima risposta 500 → «Riprova» → la seconda richiesta parte.

- [ ] **Step 2: Falliscono.** Da `<worktree>/frontend`: `npx vitest run src/features/meals src/components/TabBar.test.tsx`. Expected: FAIL.

- [ ] **Step 3: Il codice** del blocco Interfaces. In `App.tsx` la rotta `/pasti` (le altre del Task 7–9 si aggiungono là, con `/pasti/nuovo` dichiarata **sopra** `/pasti/:id` come `/ricette/nuova-ai`). In `icons.ts` una sezione `// pasti` con `IconCalendarWeek` (le icone dei task dopo si aggiungono lì).

- [ ] **Step 4: Passano, e il resto resta verde.** `npx vitest run`, `npm run typecheck`, `npm run lint`. Expected: verdi.

- [ ] **Step 5: Commit**
  ```bash
  git add frontend/src
  git commit -m "feat(pasti): la scheda Pasti e la settimana, da lunedì a domenica, con oggi evidenziato e i posti da pianificare"
  ```

---

### Task 7: Il pasto a mano — modulo, nuovo pasto, il piatto senza ricetta

**Files:**
- Create: `frontend/src/features/meals/MealForm.tsx`, `NewMealScreen.tsx`, `MealScreen.tsx` e i loro `.test.tsx`
- Modify: `frontend/src/App.tsx` (rotte `/pasti/nuovo`, `/pasti/:id`)

**Interfaces:**
- Consumes: Task 6 (`api.ts`, `format.ts`, tipi).
- Produces:
  - `MealForm({ initial, slotEditable, leftoverChoices, submitLabel, save, onSaved, onCancel })` — campi «Piatto» (obbligatorio), «Accompagnamenti» (segnaposto «piadina · banana»), casella «Fuori casa», e, se `leftoverChoices` non è vuoto, la scelta «Avanzo di» con «Nessuno» e una voce per pasto, scritta `«<piatto> (<longDayLabel>, <pranzo|cena>)»`; con `slotEditable` anche «Giorno» (`<input type="date">`) e «Pasto» (Pranzo/Cena). «Salva» non ancora pronto con il perché «Scrivi il piatto.» finché il piatto è vuoto. Accompagnamenti vuoti si mandano `null`. **Un posto occupato**: se `save` fallisce con 409 `slot_taken`, sotto il modulo «C'è già «X» in questo posto.» (il `detail` del server) con i pulsanti «Sostituisci» (rimanda lo stesso corpo con `replace: true`) e «Annulla». Gli altri errori mostrano il `detail` del server in un `Alert`.
  - `NewMealScreen` su `/pasti/nuovo?giorno=…&posto=…`: `BackLink` a `/pasti?settimana=<giorno>` «Pasti», `h1` «Nuovo pasto», sotto `«<longDayLabel> · <Pranzo|Cena>»`; un commento segna il posto di «Chiedilo a Claude» (piano 4); poi `MealForm` (`slotEditable` falso, `leftoverChoices` da `fetchLeftoverCandidates`, `submitLabel` «Salva»). Salvato: avviso «Pasto salvato.» e ritorno a `/pasti?settimana=<giorno>`.
  - `MealScreen` su `/pasti/:id`: `BackLink` a `/pasti?settimana=<week>` «Pasti»; sopra il titolo `«<longDayLabel> · <Pranzo|Cena>»`; `h1` il piatto; gli accompagnamenti; i segni come nella settimana; una `IconToolbar` «Azioni del pasto» con «Correggi» (`IconPencil`) ed «Elimina» (`IconTrash`), entrambi `ghost`.
    - «Correggi» apre `MealForm` sul posto (`slotEditable` vero, `submitLabel` «Salva le modifiche», `onCancel` lo chiude), che manda solo i campi cambiati con `updateMeal`.
    - «Elimina» apre una conferma in linea: «Eliminare «<piatto>»?», più, se il pasto ha una ricetta con `in_book` falso, «La sua ricetta non è nel ricettario: si elimina con il pasto.»; pulsanti «Sì, elimina» (`variant="danger"`) e «Annulla». Eliminato: avviso «Pasto eliminato.» e ritorno alla settimana.
    - Una bozza mostra «Rendi ufficiale» (`updateMeal(id, { status: "official" })`); un commento dice che il piano 4 ci aggancia la scheda dei cambi.
    - **Sotto l'intestazione** (questo task; la ricetta è del Task 8): fuori casa → «Fuori casa: non c'è niente da cucinare.»; bozza → «È una bozza: la ricetta arriva quando diventa ufficiale.»; ufficiale senza ricetta e non avanzo → «Questo pasto non ha ancora una ricetta.» con due collegamenti a forma di pulsante, «Scrivi la ricetta» (`/pasti/<id>/ricetta/nuova`) e «Scegli dal ricettario» (`/pasti/<id>/ricetta/scegli`).

- [ ] **Step 1: I test che falliscono.**
  - `MealForm.test.tsx`: (1) con il piatto vuoto «Salva» dice «Scrivi il piatto.» e non manda niente; (2) manda `{ dish: "Frittata", sides: null, away: false, leftover_of_id: null, … }` con gli accompagnamenti vuoti; (3) con due `leftoverChoices` la scelta «Avanzo di» ha «Nessuno» e le due voci scritte come sopra, e scegliendone una il corpo porta il suo id.
  - `NewMealScreen.test.tsx`: (1) salva: `POST /api/v1/meals` con `day` e `slot` presi dall'indirizzo, poi la settimana e «Pasto salvato.»; (2) 409 `slot_taken` → si legge «C'è già «Pizza» in questo posto.», «Sostituisci» rimanda con `replace: true`.
  - `MealScreen.test.tsx`: (1) intestazione: «martedì 11 novembre · Cena», `h1` il piatto, gli accompagnamenti; (2) «Correggi», giorno cambiato, «Salva le modifiche» → `PATCH` con solo `day`, e il modulo si chiude; (3) spostare su un posto occupato → «Sostituisci» rimanda con `replace: true`; (4) «Elimina» con una ricetta fuori dal ricettario → si legge la frase della ricetta, «Sì, elimina» → `DELETE`, ritorno alla settimana con «Pasto eliminato.»; (5) una bozza: «Rendi ufficiale» → `PATCH` `{ status: "official" }`; (6) un pasto ufficiale senza ricetta mostra «Scrivi la ricetta» e «Scegli dal ricettario» con i loro `href`, e un pasto fuori casa mostra «Fuori casa: non c'è niente da cucinare.» e nessuno dei due.

- [ ] **Step 2: Falliscono.** `npx vitest run src/features/meals`. Expected: FAIL.

- [ ] **Step 3: Il codice** del blocco Interfaces.

- [ ] **Step 4: Passano.** `npx vitest run`, `npm run typecheck`, `npm run lint`. Expected: verdi.

- [ ] **Step 5: Commit**
  ```bash
  git add frontend/src
  git commit -m "feat(pasti): il pasto scritto a mano — piatto, accompagnamenti, fuori casa, avanzo — corretto, spostato ed eliminato"
  ```

---

### Task 8: La ricetta nel piatto

**Files:**
- Modify: `frontend/src/features/cooking/RecipeDetailScreen.tsx`, `frontend/src/features/meals/MealScreen.tsx`, `frontend/src/features/recipes/api.ts`, `frontend/src/features/registry/CategoryForm.tsx`, `frontend/src/components/ui/icons.ts`
- Test: `frontend/src/features/meals/MealScreen.test.tsx`, `frontend/src/features/cooking/RecipeDetailScreen.test.tsx`, un test di `CategoryForm` dove sta oggi il caso «(eliminata)» (`grep -rln "(eliminata)" frontend/src/features/registry`)

**Interfaces:**
- Consumes: `RecipeDetail.in_book`/`meal` (Task 5, tipo nel Task 6), `MealScreen` (Task 7).
- Produces:
  - `RecipeDetailView` **esportata** da `RecipeDetailScreen.tsx`, con una prop facoltativa `meal?: { mealId: string; readOnly: boolean }`. Senza `meal` è il dettaglio di oggi, più una regola: se la ricetta non è eliminata, `recipe.in_book === false` e `recipe.meal` c'è, rende `<Navigate to={`/pasti/${recipe.meal.id}`} replace />` (decisione 19). Con `meal`:
    - niente `RecipeHero` col ritorno alle Ricette: solo la foto (senza il margine negativo che la mette sotto il tasto);
    - il titolo è un `h2` (l'`h1` è il piatto);
    - nella barra delle azioni solo «Modifica», che porta a `/ricette/<id>/modifica?pasto=<mealId>`; niente «Modifica con AI», niente «Elimina»; con `readOnly` nessuna azione;
    - **niente «Cucina» e niente foglio della cottura**; al suo posto, se non `readOnly`, «Salva nel ricettario» (`secondary`, `shape="block"`, `IconBookmarkPlus`) quando `in_book` è falso, «Togli dal ricettario» (`ghost`, `IconBookmarkOff`) quando è vero; avvisi «Salvata nel ricettario.» e «Tolta dal ricettario.»; dopo, invalida `["recipe", id]`, `["recipes"]`, `["recipe-categories"]`, `["meals"]`;
    - restano dosi, porzioni, riporziona, sostituti, «Metti in lista ciò che manca», procedimento, nutrienti; una ricetta eliminata mostra la lapide di oggi (con «Ripristina»), senza il ritorno alle Ricette.
  - `setRecipeInBook(id: string, inBook: boolean): Promise<RecipeDetail>` in `features/recipes/api.ts` (`PATCH` `{ in_book }`).
  - In `MealScreen`, sotto l'intestazione: con `meal.recipe` → `<RecipeDetailView id={meal.recipe.id} meal={{ mealId: meal.id, readOnly: false }} />`; con `meal.leftover_of` → un collegamento «Avanzo di «<piatto>», <longDayLabel> · <pasto>» a `/pasti/<origine>` e, se l'origine ha una ricetta, `RecipeDetailView` in sola lettura (`readOnly: true`), altrimenti «Il pasto da cui viene non ha una ricetta.». Sotto la ricetta un commento segna il posto della chat del piatto (piano 3).
  - `CategoryForm`: accanto al titolo di una ricetta del rifiuto, «(eliminata)» se `archived`, altrimenti « (da un pasto)» se `from_meal`.

- [ ] **Step 1: I test che falliscono.**
  - `MealScreen.test.tsx`, cinque casi nuovi (la ricetta servita da `GET /api/v1/recipes/<id>` con `in_book: false`, `meal: {…}`): (1) il titolo della ricetta è un `heading` di livello 2 e non c'è nessun pulsante «Cucina»; (2) «Modifica» ha `href` `/ricette/r1/modifica?pasto=m1` e non ci sono «Modifica con AI» né «Elimina» della ricetta; (3) «Salva nel ricettario» → `PATCH /api/v1/recipes/r1` con `{ in_book: true }` e l'avviso «Salvata nel ricettario.»; (4) con `in_book: true` c'è «Togli dal ricettario» → `{ in_book: false }` e «Tolta dal ricettario.»; (5) un avanzo: il collegamento «Avanzo di «Frittata di spinaci», martedì 11 novembre · Cena» porta a `/pasti/<origine>`, la ricetta d'origine si legge, e non ci sono né «Modifica» né «Salva nel ricettario».
  - `RecipeDetailScreen.test.tsx`, due casi: (1) su `/ricette/r1` una ricetta con `in_book: false` e `meal.id "m1"` porta a `/pasti/m1`; (2) una ricetta con `in_book: true` e un `meal` mostra «Cucina».
  - `CategoryForm`: un rifiuto con una ricetta `{ archived: false, from_meal: true }` mostra «(da un pasto)».

- [ ] **Step 2: Falliscono.** `npx vitest run src/features/meals src/features/cooking src/features/registry`. Expected: FAIL.

- [ ] **Step 3: Il codice** del blocco Interfaces. Le condizioni sulla modalità stanno in pochi punti (l'eroe, il titolo, la barra, il blocco di «Cucina»), non sparse riga per riga.

- [ ] **Step 4: Passano, e i test di oggi del dettaglio restano verdi.** `npx vitest run`, `npm run typecheck`, `npm run lint`. Expected: verdi, nessun test di oggi cambiato.

- [ ] **Step 5: Commit**
  ```bash
  git add frontend/src
  git commit -m "feat(pasti): il piatto con la ricetta sopra, senza «Cucina», con «Salva nel ricettario»; la ricetta di un pasto aperta dal ricettario porta al pasto"
  ```

---

### Task 9: Scrivere e scegliere la ricetta di un pasto

**Files:**
- Create: `frontend/src/features/meals/MealRecipeNewScreen.tsx`, `MealRecipePickScreen.tsx` e i loro `.test.tsx`
- Modify: `frontend/src/features/recipe-form/RecipeEditScreen.tsx`, `RecipeEditScreen.test.tsx` (un caso nuovo), `frontend/src/features/recipes/api.ts` (`createRecipe` accetta `meal_id?: string`), `frontend/src/App.tsx` (due rotte)

**Interfaces:**
- Consumes: `RecipeForm`, `EMPTY_FORM` (`features/recipe-form/`), `createRecipe`, `searchRecipes`, `copyRecipeToMeal`, `fetchMeal`.
- Produces:
  - `/pasti/:id/ricetta/nuova` → `MealRecipeNewScreen`: `BackLink` al pasto «Pasto», `h1` «Scrivi la ricetta», sotto «Resta fuori dal ricettario finché non la salvi lì.»; `RecipeForm` con `EMPTY_FORM` più titolo uguale al piatto e 1 porzione; `save` = `createRecipe({ ...body, source: "manual", source_ref: null, meal_id })`; `submitLabel` «Salva la ricetta»; salvata: invalida `["meals"]` e `["recipe", id]`, avviso «Salvata.», `navigate("/pasti/<id>", { replace: true })`.
  - `/pasti/:id/ricetta/scegli` → `MealRecipePickScreen`: `BackLink` al pasto «Pasto», `h1` «Scegli dal ricettario», sotto «Il pasto riceve una copia: la ricetta del ricettario non cambia.»; un campo «Cerca nel ricettario» (con `useDebounced` come il ricettario) e la prima pagina di `searchRecipes({ query })` come elenco di pulsanti col titolo (e i mancanti, se `RecipeRow` si presta; altrimenti solo il titolo); vuoto: «Nessuna ricetta.». Un tocco → `copyRecipeToMeal`, avviso «Ricetta copiata nel pasto.», `navigate("/pasti/<id>", { replace: true })`; un errore mostra il `detail` del server in un `Alert`.
  - `RecipeEditScreen`: con `?pasto=<id>` il ritorno è `BackLink` a `/pasti/<id>` «Pasto», e dopo il salvataggio `navigate("/pasti/<id>", { replace: true })` invalidando anche `["meals"]`; senza, com'è oggi.

- [ ] **Step 1: I test che falliscono.**
  - `MealRecipeNewScreen.test.tsx`: (1) il titolo del modulo vale il piatto e le porzioni 1; (2) «Salva la ricetta» manda `POST /api/v1/recipes` con `meal_id: "m1"` e `source: "manual"`, poi `/pasti/m1` con «Salvata.».
  - `MealRecipePickScreen.test.tsx`: (1) scrivendo «frittata» parte `GET /api/v1/recipes/search?q=frittata…` e si leggono i titoli; (2) un tocco → `POST /api/v1/meals/m1/recipe/copy` con `{ recipe_id: "r9" }`, poi `/pasti/m1` con «Ricetta copiata nel pasto.».
  - `RecipeEditScreen.test.tsx`, un caso: da `/ricette/r1/modifica?pasto=m1` il ritorno dice «Pasto» e porta a `/pasti/m1`, e dopo «Salva le modifiche» si arriva a `/pasti/m1`.

- [ ] **Step 2: Falliscono.** `npx vitest run src/features/meals src/features/recipe-form`. Expected: FAIL.

- [ ] **Step 3: Il codice** del blocco Interfaces.

- [ ] **Step 4: Passano.** `npx vitest run`, `npm run typecheck`, `npm run lint`, `npm run build`. Expected: verdi.

- [ ] **Step 5: Commit**
  ```bash
  git add frontend/src
  git commit -m "feat(pasti): «Scrivi la ricetta» col modulo di sempre e «Scegli dal ricettario» con una copia; la modifica torna al pasto"
  ```

---

### Task 10: Nel browser vero, a 375 px, nei due temi

**Files:**
- Create: `frontend/e2e/pasti.spec.ts`
- Modify: `frontend/e2e/style.spec.ts` (una riga nell'elenco `SCHERMATE`; due prove **in fondo al file**)

Leggi `style.spec.ts` com'è sul ramo: `testiIlleggibili`, `fermo`, `perOgniLuogo` e il `beforeEach` che fa l'accesso ci sono già; `e2e/giornoDiRoma.ts` dà il giorno di Roma. Le prove creano quel che serve con `page.request` (che condivide i cookie della pagina) e lo tolgono nel `finally` (`DELETE /api/v1/meals/<id>`; una ricetta creata a parte con `PATCH {archived: true}`). `playwright.config.ts` ha `workers: 1`: le prove non si pestano, ma usano posti diversi.

- [ ] **Step 1: Le prove funzionali**, `frontend/e2e/pasti.spec.ts` (a 375×812, accesso come in `dosi-pulite.spec.ts`):
  1. **«la settimana a mano: scrivere, ricetta fuori dal ricettario, salvarla, spostare, eliminare»**: dalla barra, «Pasti»; nella giornata con «oggi», il «+ da pianificare» della **cena** → «Piatto» «Frittata di prova e2e», «Accompagnamenti» «piadina · banana», «Salva» → la settimana mostra il piatto e gli accompagnamenti. Tocco sul pasto → «Scrivi la ricetta» → il titolo vale il piatto; una riga con l'ingrediente «uova» del seme, il procedimento → «Salva la ricetta» → il piatto mostra la ricetta, **nessun pulsante «Cucina»**, «Salva nel ricettario». `GET /api/v1/recipes/search?q=Frittata di prova e2e` è vuoto; «Salva nel ricettario» → lo stesso `GET` la trova; «Togli dal ricettario» → di nuovo vuoto. «Correggi» → giorno domani (`giornoDiRoma(1)`), «Pranzo», «Salva le modifiche» → nella settimana di domani il pasto sta al pranzo. «Elimina» → «Sì, elimina» → il posto torna «+ da pianificare»; `GET /api/v1/recipes/<id>` ha `archived_at` non nullo.
  2. **«Scegli dal ricettario fa una copia»**: un pasto creato con `page.request` (pranzo di dopodomani); aprirlo, «Scegli dal ricettario», cercare il titolo della prima ricetta del seme (letto da `GET /api/v1/recipes/search?limit=1`), toccarlo → il piatto mostra quel titolo; `GET /api/v1/recipes/search?q=<titolo>` dà ancora **una** ricetta, con l'id di prima; il pasto (`GET /api/v1/meals/<id>`) ha `recipe.id` diverso.
  3. **«la ricetta di un pasto aperta da /ricette porta al pasto»**: col pasto della prova 2, `page.goto("/ricette/<id della copia>")` → l'indirizzo diventa `/pasti/<id del pasto>`.

- [ ] **Step 2: Le prove di stile.** In `style.spec.ts`, aggiungi `"/pasti"` all'elenco `SCHERMATE` (dopo `"/ricette/importa"`): così la settimana passa da ogni misura di `perOgniLuogo`, nei due temi. **In fondo al file**, due prove:
  1. **«la settimana dei pasti a 375 px: si legge nei due temi, oggi si distingue, niente scorre di lato»**: crea con `page.request` un pranzo di oggi con accompagnamenti; e nella settimana del 2026-01-05 (passata) una bozza il lunedì a pranzo (`status: "draft"`, quindi «Non registrata»), un pasto fuori casa il lunedì a cena, un avanzo del pranzo di lunedì il martedì a pranzo (un fuori casa non può essere l'origine di un avanzo). A 375×812, per `"light"` e `"dark"` (`page.emulateMedia({ colorScheme })`): su `/pasti` e su `/pasti?settimana=2026-01-05`, `fermo`, `testiIlleggibili(page)` è `[]`, `scrollWidth <= clientWidth`; su `/pasti` l'elemento `[aria-current="date"]` ha un `background-color` diverso da quello di una giornata qualunque; si leggono «Non registrata», «Fuori casa», «Avanzo».
  2. **«il piatto con la ricetta a 375 px, nei due temi»**: un pasto con una ricetta scritta (`POST /api/v1/recipes` con `meal_id`, un ingrediente del seme); su `/pasti/<id>`, nei due temi: `testiIlleggibili` vuoto, niente scorre di lato, «Salva nel ricettario» visibile e alto almeno 44 px, nessun «Cucina».

- [ ] **Step 3: Typecheck e lint.** Da `<worktree>/frontend`: `npm run typecheck && npm run lint`. Expected: puliti.

- [ ] **Step 4: L'e2e intera**, con i comandi delle Global Constraints, su uno stack ricreato da zero. Expected: tutte verdi, le nuove comprese. **Annota il numero** delle prove passate (`N_e2e`). Poi `down -v` e `rm .env`, sempre. Se una prova nuova fallisce per un testo illeggibile: scrivi nel report quale testo, in quale tema e con che rapporto; **nessun token nuovo**: si sceglie un altro token esistente (per esempio `text-ink-soft` invece di `text-ink-faint`); se nessun token esistente basta, il task si ferma `bloccato` con la misura. Se «uova» non è nel seme, usa un altro ingrediente alimentare del seme (`/api/v1/ingredients/search`) e scrivilo nel report.

- [ ] **Step 5: Commit**
  ```bash
  git add frontend/e2e/pasti.spec.ts frontend/e2e/style.spec.ts
  git commit -m "pasti: nel browser vero — la settimana a mano, la ricetta fuori dal ricettario, la copia, il contrasto nei due temi a 375 px"
  ```

---

### Task 11: I documenti, la verifica finale e il report

**Files:**
- Modify: `CLAUDE.md`, `docs/prossimi-passi.md`, `next-steps.md`
- Create o modify: `docs/night-reports/<data di oggi>.md`

Leggi ogni file com'è sul ramo prima di cambiarlo.

- [ ] **Step 1: `CLAUDE.md`.** Nella sezione «Conventions worth knowing», nel paragrafo sulle ricette adottate ed eliminate (R10), subito dopo la frase che finisce con `` `docs/superpowers/specs/2026-09-27-modifica-ricette-design.md`. `` aggiungi, con lo stesso rientro:
  ```
  **A recipe written for a meal stays out of the recipe book** (`recipes.in_book`
  false, decided by Mattia on 2026-11-12) until «Salva nel ricettario». Every book
  listing and search — browse, the cookable count, text and semantic search, the
  categories, the substitution engine's voices — excludes it inside the query that
  carries the limit, through the one expression `in_the_book()` beside the column, the
  same rule as archived recipes; the registry's usage lists include it and mark it
  «(da un pasto)», for the reason they include archived ones, and `reindex` gives it a
  vector for the day it is saved. A meal owns its recipe one to one
  (`meals.recipe_id` is unique): picking from the book makes a copy, and deleting a
  meal archives its recipe unless it is in the book. A live recipe out of the book
  always has a meal: «Togli dal ricettario» refuses one without, and restoring one
  without puts it back in the book. Spec:
  `docs/superpowers/specs/2026-11-12-pasti-claude-design.md` §4.
  ```
  La sezione su LLM e fornitori (§3 della spec) **non** si tocca: è del piano 3.

- [ ] **Step 2: `docs/prossimi-passi.md`.** Subito sotto il titolo `# Parte IV — Pasti (sezione primaria nuova) ↳ D1, D2, D3` aggiungi:
  ```markdown
  > **Sostituita il 2026-11-12** dalla spec `docs/superpowers/specs/2026-11-12-pasti-claude-design.md`
  > (Pasti con Claude e Utensili, decisa con Mattia). P1, P2 e P3 qui sotto, M1 (Parte V) e
  > H3 (Parte VI) sono sostituiti (spec §11) e restano come archivio del ragionamento. Il
  > primo pezzo senza Claude — la settimana, i pasti a mano, le ricette fuori dal ricettario —
  > è sul ramo `night/pasti-settimana` (<data di oggi>, da revisionare).
  ```
  E nei cinque titoli `## P1. Creazione di un pasto **[D]**`, `## P2. NutriScore **[D, con TBD]**`, `## P3. Pianificare più giorni **[D in parte il 2026-09-24, con TBD]** ↳ P1, P2, M1, R9`, `## M1. Motore di suggerimento ricette **[TBD]** ↳ P2, S4`, `## H3. Profilo **[D]** ↳ P2` sostituisci lo stato fra `**[…]**` con `**[SOSTITUITO 2026-11-12 — spec Pasti con Claude, §11]**` (il resto del titolo resta).

- [ ] **Step 3: `next-steps.md`.**
  1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte: sezione Pasti, piano 2 di 4)_`.
  2. **La voce «Sezione Pasti» resta aperta** (`grep -n "Sezione Pasti" next-steps.md`): lo stato resta `in corso` e il testo non si riscrive; in coda alla riga aggiungi ` · piano 2 di 4 (pasti e settimana senza Claude) fatto il <data di oggi> → branch night/pasti-settimana (da revisionare); il prossimo è il piano 3, night/pasti-claude`. Se un task di questo piano è rimasto `bloccato`, la voce passa a `bloccato` con «attende: …» invece.
  3. In cima a «Fatti (recenti)» aggiungi:
     ```markdown
     - [fatto] <data di oggi> · Sezione Pasti, piano 2 di 4: la scheda Pasti con la settimana, i pasti a mano (piatto, accompagnamenti, fuori casa, avanzo, bozza «non registrata»), spostati e cancellati; la ricetta del pasto scritta col modulo o copiata dal ricettario, fuori dal ricettario finché non la si salva lì, esclusa da sfoglio, ricerche, cucinabili e sostituti; il piatto senza «Cucina» [Parte IV] → branch night/pasti-settimana (da revisionare)
     ```
  4. Le voci P1 e P2 (NutriScore), e M1 e H3 se ci sono, escono (spec §11): se sono ancora nel file, toglile; scrivi nel report quali hai tolto.
  5. Quel che è emerso nella notte fuori da questo piano va come `idea` o `tbd`, con `[Parte IV]`.

- [ ] **Step 4: La verifica finale.** Da `<worktree>/frontend`: `npx vitest run`, `npm run typecheck`, `npx tsc -b --force` (`node_modules` è condiviso col checkout principale, e con lui il `tsbuildinfo`), `npm run lint`, `npm run build`. Expected: verdi; vitest **`N_vitest` + 36** in `N_file` + 7 file (Task 6: 12; Task 7: 11; Task 8: 8; Task 9: 5). Da `<worktree>/backend`, il comando di pytest: verde, **`N_pytest` + 98** (Task 1: 13; Task 2: 16; Task 3: 39; Task 4: 17; Task 5: 13). Se i numeri differiscono, scrivi nel report da dove viene la differenza. Poi i grep dei «Comandi di verifica» con i loro attesi, e l'e2e intera su uno stack ricreato da zero (`N_e2e` del Task 10), con `down -v` e `rm .env` alla fine. Infine `docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_pasti_settimana WITH (FORCE)'`.

- [ ] **Step 5: Il report.** In `docs/night-reports/<data di oggi>.md` sul ramo (se c'è già, una sezione in fondo; altrimenti `# Notte del <data di oggi>`). Per questo piano: il ramo e da dove parte (`night/utensili` a `BASE`) e la revisione `0019` letta; i conti veri contro la Preparazione; i consumatori del ricettario della tabella del Task 2 e se ne è emerso uno nuovo; le due asserzioni di `test_registry_ingredients.py` cambiate; le decisioni 10–22 che Mattia può voler rivedere (in particolare: lo spostamento che sostituisce invece di scambiare, «fuori casa» che libera la ricetta, la copia con `source = 'manual'` e senza «Variante di», la ricetta a mano con 1 porzione, «Modifica con AI» nascosto nel piatto, il ripristino che rimette nel ricettario); le icone sostituite, se è successo; i posti lasciati per i piani 3 e 4 (`MealScreen` sotto la ricetta, `WeekScreen` in fondo, `NewMealScreen`, «Rendi ufficiale»); e la sezione «Dopo il deploy (solo Mattia)» qui sotto. Niente push, niente merge, niente deploy.
  ```bash
  git add CLAUDE.md docs/prossimi-passi.md next-steps.md docs/night-reports/
  git commit -m "docs: la sezione Pasti senza Claude fatta sul ramo (piano 2 di 4); le ricette fuori dal ricettario in CLAUDE.md, la Parte IV sostituita dalla spec"
  ```

---

## Dopo il deploy (solo Mattia)

La notte non tocca la produzione. Questo ramo si unisce **dopo** `night/utensili` e prima di `night/pasti-claude`; ha senso metterlo in produzione anche da solo (la sezione Pasti funziona senza Claude), oppure insieme ai piani 3 e 4.

1. Il deploy di sempre, **con il `-f`**: `docker compose -f docker-compose.prod.yml up -d --build --wait --wait-timeout 120`. La migrazione `0020` gira all'avvio (`docker-entrypoint.sh`): aggiunge `recipes.in_book` (vero su tutte le ricette che ci sono, quindi il ricettario non cambia) e crea `meals`, vuota. Nessun comando da lanciare.
2. **A video, sul telefono:** la scheda «Pasti»; scrivere a mano la settimana corrente (una cena con accompagnamenti, un pranzo fuori casa, un avanzo); su un pasto «Scrivi la ricetta» e su un altro «Scegli dal ricettario»; controllare che il ricettario non mostri le due ricette e che «Salva nel ricettario» ne porti una dentro, con «Cucina» quando la si apre dal ricettario.
3. **Il ricettario resta com'era:** il numero in testa al ricettario, senza filtri, è lo stesso di prima del deploy.
