# I suggerimenti degli ingredienti non sono più sempre dieci righe: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** i suggerimenti di `GET /api/v1/ingredients/search` mostrano chi contiene il testo digitato all'inizio di una parola — nel nome o in un alias, senza badare agli accenti — e gli altri solo se nessuno lo contiene, sopra un pavimento di 0,30; dove la lista resta vuota e nessuno sa creare, `IngredientPicker` lo dice con una nota di ripiego; la misura della bozza si rifà sul seme con un comando di sola lettura che Mattia potrà lanciare anche sulla produzione.

**Architecture:** la regola del taglio è una funzione pura, `trim_suggestions`, in un modulo nuovo del dominio (`backend/app/domain/suggestions.py`), accanto a `fold_for_match`, che toglie accenti e separatori dal testo cercato con la stessa coppia di stringhe (`FOLD_FROM`/`FOLD_TO`) che la query passa a `translate()` di Postgres. Nel repository nasce `suggest_ingredients`: una query sorella di `search_ingredients` che calcola anche `is_hit` (il testo all'inizio di una parola del nome o di un alias) e lo mette nell'`ORDER BY` subito dopo il prefisso, poi applica il taglio. L'endpoint passa a `suggest_ingredients`; `search_ingredients` resta com'è per `match_name` e per i vicini dell'AI (decisione 3), salvo che `%` e `_` diventano lettere anche lì (`autoescape`). Il comando `python -m app.cli.measure_suggestions` confronta le due funzioni sull'anagrafica del database a cui è collegato. Nel frontend cambia solo `IngredientPicker`.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Postgres 16 con `pg_trgm`, pytest su Postgres vero; React 19, TanStack Query 5, Vitest + Testing Library, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-06-suggerimenti-soglia-bozza.md` — la misura (§3–§5), il criterio raccomandato (§6), i chiamanti a lista vuota (§7), dove va nel codice (§8), i test (§9) e **le sei decisioni del §10, prese il 2026-10-07**. La voce di `next-steps.md` che questo piano chiude comincia con «I suggerimenti degli ingredienti sono sempre dieci righe» ([T3, esito del giro]; in `docs/prossimi-passi.md` il punto «**I suggerimenti sono rumorosi.**» della voce T3).

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/suggerimenti-soglia` (`.worktrees/` è già in `.gitignore`), ramo `night/suggerimenti-soglia`, creato da **`master`**: questo piano è il quarto della notte ma non dipende dai tre prima di lui, e nessuno dei suoi file aspetta il loro lavoro. Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì (o dalle sue `backend/` e `frontend/`), mai dalla radice del checkout principale. Il checkout principale non si tocca: se vi trovi modifiche non committate, sono dell'utente. **Nessun push, nessun merge, nessun deploy. Mai `git stash`.**
- **I file che anche altri piani della notte toccano** (`frontend/src/components/IngredientPicker.tsx`, che S3 usa e potrebbe ritoccare; `frontend/e2e/style.spec.ts`, dove quasi ogni piano aggiunge prove; `backend/app/api/ingredients.py`, che S12 potrebbe toccare per l'emoji dell'ingrediente; `next-steps.md`, `docs/prossimi-passi.md`, il report della notte): sul tuo ramo, che parte da `master`, sono come su `master`. Il piano descrive comunque ogni modifica contro un'ancora riconoscibile — una funzione, un elemento JSX, un testo esatto — e mai contro numeri di riga: **leggi il file com'è sul ramo prima di cambiarlo**. Le prove nuove di `style.spec.ts` si aggiungono **in fondo al file**, senza toccare quelle che ci sono; al merge, l'unione con le prove aggiunte dagli altri rami la fa la revisione.
- **Il dominio non tocca il database.** `backend/app/domain/suggestions.py` è puro come `rules.py`: niente SQLAlchemy, niente sessione. La query sta nel repository.
- **Le soglie si scrivono una volta sola**: `FUZZY_RELATIVE = 0.8` e `FUZZY_FLOOR = 0.30` in `suggestions.py`, e `FOLD_FROM`/`FOLD_TO` lì accanto. La query le importa; nessun numero si ricopia altrove, né in Python né in TypeScript (il frontend non sa che esistono).
- **Il taglio vale solo per l'endpoint** (decisione 3): `match_name` (`backend/app/services/ingredient_match.py`, `limit=1`) e i vicini per l'AI (`backend/app/services/recipe_import/decide.py`, `limit=3`) continuano a chiamare `search_ingredients`, il cui ordine e il cui filtro non cambiano. L'unica differenza per loro: un `%` o un `_` scritti non fanno più da jolly.
- **Mai un vicolo cieco.** Una lista vuota lascia sempre una strada: in Lista il testo libero, in «Sistema la spesa» e nel modulo della ricetta «Aggiungi «…»», in Dispensa la sua `emptyNote`, e negli altri cinque posti di `IngredientPicker` (coda d'import, sposta alias, fondi, prodotto, filtri del ricettario) la nota di ripiego di questo piano.
- **Una ricetta non nomina un non alimentare** (`CLAUDE.md`, decisione 2): il filtro `kind` della ricerca resta com'è, e `suggest_ingredients` lo applica come `search_ingredients`.
- Tutto il colore passa dai token di `frontend/src/index.css`: la nota di ripiego usa `text-ink-soft`, come `emptyNote` oggi. **Nessun token nuovo.** `grep -rn "emerald\|neutral-" frontend/src` resta vuoto. Ogni testo sta sopra 4,5:1, in chiaro e in scuro, e lo misura `frontend/e2e/style.spec.ts`.
- Le parole a video sono in italiano e **si copiano esattamente come sono scritte qui**; gli identificatori in inglese; i commenti in italiano come nel resto del codice.
- **Il type check è `npm run typecheck`** (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0 (settima lezione di `CLAUDE.md`).
- Controlli del frontend, da `<worktree>/frontend`: `npx vitest run` (non esiste `npm test`), `npm run typecheck`, `npm run lint`, `npm run build`.
- **Backend su Postgres vero.** Il database dei test è il container `spena-db-1` (porta 5433), da usare solo come database dei test: se `docker ps --format '{{.Names}}'` non lo mostra, `docker start spena-db-1`. **Mai `docker compose up` dal worktree** (il nome del progetto Compose viene dalla cartella: nascerebbe un secondo Postgres che litiga sulla 5433), mai `-f docker-compose.prod.yml`. Nel worktree non c'è un `.venv`: si usa quello del checkout principale; `python -m` mette la cartella corrente in testa a `sys.path`, quindi si prova l'`app` del worktree. Il comando, sempre da `<worktree>/backend`:
  ```bash
  PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
  Se un test sembra ignorare una modifica, `python -c 'import app; print(app.__file__)'` da `<worktree>/backend` (con lo stesso `PATH`) deve stampare un percorso dentro il worktree. Nessuna chiamata di rete nella suite.
- **e2e** sullo stack `spena-e2e`, dalla radice di `<worktree>`. Serve un `.env`: **si copia da `.env.example`, che non ha segreti, solo per la prova, e si cancella alla fine. Mai leggere né copiare il `.env` del checkout principale.** Prima di alzarlo, `docker ps --format '{{.Names}}' | grep spena-e2e`: se c'è e non l'hai alzato tu (un altro piano della notte), non fare `down`, aspetta che sparisca.
  ```bash
  cp .env.example .env
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed --con-ricette
  (cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
  rm .env
  ```
  Il `-p spena-e2e` e il `-f docker-compose.e2e.yml` vanno in ogni comando: un `down -v` sul progetto di default cancellerebbe la dispensa vera. Una prova fallita lascia dati nello stack: prima di rieseguire, `down -v`, poi `up`, seme e prova.
- **Niente produzione, di notte.** La misura sull'anagrafica vera non si fa: il comando si costruisce e si prova sul seme dello stack e2e (Task 5), e il comando per la produzione sta in «Dopo il deploy (solo Mattia)».
- Nessuna dipendenza nuova, nessuna migrazione, nessun cambio di configurazione globale.

### Preparazione (una volta, prima del Task 1)

- [ ] Il ramo di partenza è `master`, e i file di questo piano sono quelli su cui è scritto (`master` era `27aa06a` quando il piano è stato scritto):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify master
  git diff --stat 27aa06a master -- \
    backend/app/repositories/ingredients.py \
    backend/app/api/ingredients.py \
    backend/tests/api/test_ingredients.py \
    frontend/src/components/IngredientPicker.tsx \
    frontend/src/components/IngredientPicker.test.tsx
  ls backend/app/domain/suggestions.py backend/app/cli/measure_suggestions.py frontend/e2e/suggerimenti.spec.ts 2>&1 | grep -c "No such file"
  ```
  Expected: un hash; il `diff --stat` **vuoto**; `3` (i tre file nuovi non esistono ancora). Se il `diff` non è vuoto, `master` è andato avanti su questi file: applica le modifiche del piano sopra la versione di `master`, ancora per ancora, e scrivilo nel report. Se uno dei tre file nuovi esiste già, **fermati**: qualcuno ha già cominciato questa voce; scrivi nel report della notte (`docs/night-reports/<data>.md`, sul ramo `night/suggerimenti-soglia` appena creato) cosa hai trovato, segna la voce `bloccato` in `next-steps.md` di quel ramo con la domanda per Mattia, e non partire.
- [ ] Dal checkout principale, allinea `node_modules` al lockfile (non aggiunge dipendenze, installa quelle di `package-lock.json`):
  ```bash
  cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund
  ```
- [ ] Crea il worktree da `master` e collega `node_modules` (e solo quello: **niente `.env`**):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/suggerimenti-soglia -b night/suggerimenti-soglia master
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/suggerimenti-soglia/frontend/node_modules
  ```
- [ ] La voce in `next-steps.md` del ramo passa a `in corso` (cercala per testo, `grep -n "I suggerimenti degli ingredienti sono sempre dieci righe" next-steps.md`: di giorno può essere stata spostata in «Pronti per la notte»; cambia solo lo stato fra parentesi quadre) e si committa:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/suggerimenti-soglia
  git add next-steps.md
  git commit -m "next-steps: i suggerimenti tagliati, in corso"
  ```
- [ ] La linea di partenza, dal worktree:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/suggerimenti-soglia/frontend && npx vitest run 2>&1 | grep -E "Test Files|Tests "
  cd ../backend && PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q 2>&1 | tail -n 1
  ```
  Expected: tutto verde. **Annota i numeri** (file e test di vitest, test di pytest): sono `N_file`, `N_vitest`, `N_pytest` del Task 7. Se una delle due linee non è verde, fermati: non è un difetto di questo piano, e va scritto nel report.

---

## Obiettivo e contesto

Dal giro di T3: i suggerimenti degli ingredienti sono sempre dieci righe, anche quando dopo la terza non somigliano più, e un tocco sbagliato lega la voce all'ingrediente sbagliato. La bozza ha misurato perché (§4): sopra lo 0,15 di `SIMILARITY_FLOOR` non c'è nessun taglio, e il punteggio trigram non separa il giusto dal rumore — dalla terza riga in giù tutto sta fra 0,17 e 0,30, e un prefisso lungo ha un punteggio basso per come è fatta `similarity` («zucch» contro «zucchero a velo» fa 0,29, meno di «zucca»). Nessuna soglia sul solo punteggio toglie il rumore senza perdere bersagli. Quel che li separa è se la riga **contiene il testo digitato**: chi lo contiene passa sempre; gli altri solo se nessuno lo contiene, ed è il caso del refuso. Sul seme la lista media scende da 5,2 righe a circa 1,6, senza perdere un bersaglio (simulazione fatta scrivendo il piano, sotto nel Task 5).

«Zucchero prima di Zucchina» non è rumore e resta (decisione 5): tutti e due cominciano con «zucch» e hanno la stessa somiglianza; basta una lettera in più.

## Decisioni prese

Le sei del §10 della bozza, prese il 2026-10-07:

1. **Il criterio B col pavimento a 0,30** (Mattia). Se c'è almeno un riscontro si mostrano solo i riscontri, al massimo 10, nell'ordine; se non c'è nessun riscontro si mostrano gli sfumati con `best ≥ max(0,30; 0,8 × best del primo)`, al massimo 10; se non resta niente, la lista è vuota.
2. **Gli accenti si tolgono con `translate()`** sulle vocali accentate, nella query, senza migrazioni e senza `unaccent` (Claude, su delega di Mattia).
3. **Il taglio vale solo per l'endpoint `/ingredients/search`** (Claude, su delega): `match_name` e i vicini per l'AI vivono degli sfumati.
4. **Un riscontro è il testo all'inizio di una parola nel nome o in un alias qualunque** (Mattia, diversa dalla raccomandazione: «se scrivo "pollo" voglio "petto di pollo", "ali di pollo" eccetera»). Inizio di una parola: all'inizio, dopo uno spazio, un apostrofo o un trattino. Così «olio» trova anche «Tonno in scatola» per il suo alias «tonno sott'olio».
5. **Nessuno spareggio nuovo per «zucch»** (Mattia): il taglio lascia le righe che contengono «zucch», con Zucchina dopo Zucchero. Se il giro dopo il taglio dice ancora che sbaglia, lo spareggio diventa una voce sua.
6. **La nota di ripiego in `IngredientPicker`** sta in questa voce (Claude, su delega): senza, il taglio creerebbe pannelli muti dove oggi c'è rumore.

Scelte di questo piano, dove la bozza non arrivava (tecniche o di testo, decise da Claude su delega di Mattia; reversibili):

7. **Una query sorella, non un parametro.** `suggest_ingredients` è una funzione nuova del repository accanto a `search_ingredients`, con la sua query: riscontro, prefisso senza accenti, `is_hit` nell'ordine e nel filtro. `search_ingredients` non riceve un parametro «taglia sì/no», perché il suo ordine deve restare quello di oggi per `match_name` e i vicini dell'AI, e un parametro farebbe passare dallo stesso `ORDER BY` due ordini diversi. In comune le due funzioni hanno solo il conteggio degli acquisti (`_purchase_counts`), estratto.
8. **Il taglio è in `suggest_ingredients`, e l'endpoint la chiama.** Così il comando di misura (Task 3) prova esattamente la funzione che l'endpoint usa, e non una sua copia (prima lezione di `CLAUDE.md`). «Solo nell'endpoint» resta vero: nessun altro chiamante passa da `suggest_ingredients`.
9. **Il `LIMIT` della query basta, e il taglio gli sta dietro senza perdere niente.** È la sesta lezione di `CLAUDE.md` («un filtro che lavora sul risultato non può stare dietro un limite»), ed è il motivo per cui `is_hit` entra nell'`ORDER BY` subito dopo il prefisso: i riscontri vengono prima di ogni sfumato, quindi se ce n'è uno i primi `limit` candidati contengono i primi `limit` riscontri; se non ce n'è nessuno gli sfumati arrivano dal più simile in giù, e quelli sopra la soglia sono in testa. Un test lo fissa con undici sfumati più simili di un riscontro (Task 2).
10. **Anche il prefisso, nei suggerimenti, si confronta senza accenti.** «caffe» è un prefisso di «caffè», e la riga va fra i prefissi, non dopo: con la regola della decisione 2 applicata solo al riscontro, «caffe» darebbe «Caffelatte» prima di «Caffè». Un confronto solo, senza accenti, per prefisso e riscontro. In `search_ingredients` il prefisso resta quello di oggi.
11. **Apostrofi e trattini diventano spazi nella stessa `translate()`** che toglie gli accenti (`'`, `’` e `-` in `FOLD_FROM`, spazi in `FOLD_TO`), e il nome si confronta con uno spazio davanti: «inizio di una parola» diventa «dopo uno spazio», con un solo `LIKE` per il nome e uno per gli alias. Il testo cercato passa per `fold_for_match`, che usa le stesse due stringhe e riduce gli spazi a uno.
12. **`%` e `_` sono lettere**, con l'`autoescape=True` di SQLAlchemy (`startswith`/`contains`), in `suggest_ingredients` e anche in `search_ingredients`: chiude l'idea di `next-steps.md` che comincia con «`search_ingredients` non protegge il testo cercato nel `LIKE`». Per `match_name` e i vicini dell'AI cambia solo questo, e solo per chi scrive `%` o `_`.
13. **La nota di ripiego dice:** «Nessun ingrediente somiglia a «…». Prova con un'altra parola.» — il testo cercato fra le virgolette basse, e la strada che resta (scrivere altro: in quei cinque schermi non c'è altro da fare a ricerca vuota). Stesso stile e stesse condizioni di `emptyNote` (a ricerca finita e vuota, per il testo cercato, solo senza `onCreate`); se chi usa il selettore passa `emptyNote`, vince la sua.
14. **La misura è un comando, `python -m app.cli.measure_suggestions`**, di sola lettura (`SET TRANSACTION READ ONLY`, poi rollback), che costruisce le prove dall'anagrafica del database a cui è collegato con le regole del §3.2 della bozza (seme del campionamento `20261006`) e confronta per ogni prova `search_ingredients` (la lista di prima) con `suggest_ingredients` (quella di adesso). Di notte gira sul seme dello stack e2e; sull'anagrafica vera lo lancia Mattia dopo il deploy. Le famiglie sono tre: «digitazione», «due lettere», «refusi»; gli «assenti» della bozza chiedevano due anagrafiche e restano fuori.

## Criteri di accettazione

- [ ] `GET /api/v1/ingredients/search?q=zucch`, con zucchero, zucchina e zucca, risponde zucchero e zucchina, in quest'ordine; la zucca no.
- [ ] «olio» trova «olio di oliva» e «tonno in scatola» (alias «tonno sott'olio»), e non «olive verdi»; `search_ingredients(…, "olio", limit=3)` trova ancora «olive verdi».
- [ ] «pollo» trova «petto di pollo» e «ali di pollo» a metà nome, e non «pollame»; un riscontro con somiglianza 0,25 passa anche con undici sfumati più simili davanti, mentre `search_ingredients` con `limit=1` dà ancora lo sfumato più simile.
- [ ] «te» trova «tè»; «caffe» dà «caffè» prima di «caffelatte».
- [ ] «pomodorr» dà pomodoro e pomodorini, non «pomodori secchi» (sotto 0,8 × il primo); «zenzero», con solo «zucchero» a 0,21, dà `[]`.
- [ ] `%` e `_` non fanno da jolly, né nei suggerimenti né in `search_ingredients`.
- [ ] Nessuna risposta supera `limit`.
- [ ] Tutti i test di oggi passano, senza toccarne nessuno.
- [ ] `IngredientPicker` senza `onCreate` né `emptyNote`, a ricerca finita e vuota, mostra «Nessun ingrediente somiglia a «…». Prova con un'altra parola.» per il testo cercato; non la mostra mentre la ricerca è in corso, se la ricerca trova qualcosa, se non risponde, se c'è `emptyNote` o `onCreate`.
- [ ] Nel browser, sul seme: in Lista «zucch» non suggerisce la Zucca, «olio» suggerisce il Tonno in scatola e non le Olive, «pollo» suggerisce Petto e Coscia di pollo e non il Pisello; nei filtri del ricettario «tamarindo» mostra la nota di ripiego, leggibile nei due temi.
- [ ] `python -m app.cli.measure_suggestions` gira sullo stack e2e col seme e nella famiglia «digitazione» non perde nessun bersaglio; i suoi numeri sono nel report e in `docs/prossimi-passi.md`.
- [ ] vitest, typecheck, lint, build, pytest e l'e2e intera verdi.
- [ ] `docs/prossimi-passi.md` e `next-steps.md` aggiornati (Task 6).

## Comandi di verifica

Da `<worktree>/backend`:

```bash
PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Da `<worktree>/frontend`:

```bash
npx vitest run
npm run typecheck
npm run lint
npm run build
```

Dalla radice di `<worktree>`:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -rln "FUZZY_RELATIVE\|FUZZY_FLOOR" backend/app
grep -rln "search_ingredients(" backend/app | sort
```

Expected: il primo vuoto; il secondo solo `backend/app/domain/suggestions.py` (le soglie stanno lì e basta); il terzo `backend/app/cli/measure_suggestions.py`, `backend/app/repositories/ingredients.py`, `backend/app/services/ingredient_match.py`, `backend/app/services/recipe_import/decide.py` — e **non** `backend/app/api/ingredients.py`. E l'e2e intera con i comandi delle Global Constraints.

## Fuori scope

- **L'ordine fra i prefissi** (acquisti, poi somiglianza, poi nome) resta com'è; nessuno spareggio per «zucch» (decisione 5).
- **Mostrare da quale alias arriva una riga** («Ketchup · salsa ketchup»): resta l'idea che c'è già in `next-steps.md`. Con la decisione 4 le righe giuste che sembrano rumore saranno qualcuna in più (Tonno in scatola per «olio»), e quell'idea pesa un po' di più: scrivilo nel report.
- **Gli alias discutibili** («pasta tandoori» su «mix tandoori»): si correggono dall'Anagrafica.
- `unaccent` dentro `similarity`, la ricerca semantica, le prestazioni della query, il `limit` chiesto dal frontend (resta 10).
- La misura sull'anagrafica di produzione (sezione «Dopo il deploy»).
- Lo spegnimento con `disabled` del campo di `IngredientPicker` mentre la scelta è in volo (idea a parte in `next-steps.md`).

## Margine di autonomia

- **Liberi:** i nomi di variabili locali e di helper di test non fissati qui; l'ordine dei test dentro un file; la formulazione dei commenti, purché dicano il perché; la forma della tabella stampata dal comando di misura.
- **Fissi:** le parole a video («Nessun ingrediente somiglia a «…». Prova con un'altra parola.»); le soglie (0,8 e 0,30) e la regola del riscontro; i nomi pubblici che altri task usano (`trim_suggestions`, `fold_for_match`, `FOLD_FROM`, `FOLD_TO`, `FUZZY_RELATIVE`, `FUZZY_FLOOR`, `suggest_ingredients`, `ScoredIngredient`, `app.cli.measure_suggestions` con `build_probes`, `typos`, `load_catalog`, `measure`, `format_report`, `CatalogEntry`, `Probe`, `FamilyStats`); il seme `20261006` del campionamento.
- **Nessuna dipendenza nuova**, nessuna migrazione, nessun token di colore nuovo.
- **Nessun test di oggi si cambia.** Se un test di oggi fallisce per il taglio, è un comportamento che il piano non ha previsto: si diagnostica e si scrive nel report, non si migra. Unica eccezione ammessa: un test del frontend di un chiamante di `IngredientPicker` (coda d'import, Anagrafica, filtri del ricettario) che cerca con un'espressione regolare larga un testo che ora coincide con la nota di ripiego — si stringe quella ricerca al testo che voleva, e lo si scrive nel report.
- **I numeri delle somiglianze nei docstring dei test** vengono da un'emulazione di `pg_trgm` fatta scrivendo il piano (gli stessi numeri della bozza dove li cita: 0,500, 0,529, 0,467, 0,636, 0,538). Se un'asserzione fallisce perché Postgres dà un numero diverso, misuralo (`SELECT similarity('…','…')` dentro `spena-db-1`, sul database `spena_test`, in sola lettura) e: se l'asserzione regge col numero vero, correggi solo il docstring; se non regge, la parola del fixture non fa il ruolo che il test le chiede — scegline un'altra che lo faccia, misurata, e scrivilo nel report. Mai cambiare l'asserzione per farla passare.
- **Una decisione di comportamento non coperta e non reversibile** → si ferma quel task, si fa commit del lavoro parziale sul ramo, lo si segna `bloccato` in `next-steps.md` del ramo con la domanda precisa per Mattia, e si passa al task successivo. Una scelta reversibile e a basso impatto → la più conservativa, annotata nel report della notte.
- Se un test fallisce e non si risolve in modo ragionevole: niente test disattivati, niente asserzioni indebolite; `bloccato` con la diagnosi.

## Dipendenze

Nessuna: parte da `master`. Non consuma niente dei piani prima di lui nella catena (S3, S12, tema scuro), e nessun piano dopo di lui parte da questo ramo (S14 parte da `night/tema-scuro-spenti`). Al merge i conflitti possibili sono testuali, nei file elencati nelle Global Constraints.

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `backend/app/domain/suggestions.py` | 1 | **nuovo**: `trim_suggestions`, `fold_for_match`, le soglie, `FOLD_FROM`/`FOLD_TO` |
| `backend/tests/domain/test_suggestions.py` | 1 | **nuovo**: la regola, table-driven |
| `backend/app/repositories/ingredients.py` | 2 | `_purchase_counts` estratto; `autoescape` in `search_ingredients`; `ScoredIngredient`, `_folded`, `_suggestion_candidates`, `suggest_ingredients` |
| `backend/app/api/ingredients.py` | 2 | l'endpoint `/search` passa a `suggest_ingredients` |
| `backend/tests/api/test_ingredients.py` | 2 | dodici test nuovi, attraverso l'endpoint e su Postgres vero |
| `backend/app/cli/measure_suggestions.py` | 3 | **nuovo**: la misura, in sola lettura |
| `backend/tests/test_measure_suggestions_cli.py` | 3 | **nuovo** |
| `frontend/src/components/IngredientPicker.tsx` | 4 | la nota di ripiego |
| `frontend/src/components/IngredientPicker.test.tsx` | 4 | sei test nuovi |
| `frontend/e2e/suggerimenti.spec.ts` | 5 | **nuovo**: quattro prove sul seme |
| `frontend/e2e/style.spec.ts` | 5 | una prova in fondo: la nota di ripiego nei due temi |
| `docs/prossimi-passi.md`, `next-steps.md` | 6 | lo stato della voce, i numeri della misura |
| `docs/night-reports/<data>.md` | 7 | il report |

---

### Task 1: La regola del taglio, pura

**Files:**
- Create: `backend/app/domain/suggestions.py`
- Test: `backend/tests/domain/test_suggestions.py`

**Interfaces:**
- Consumes: niente.
- Produces:
  - `FUZZY_RELATIVE: float = 0.8`, `FUZZY_FLOOR: float = 0.30`;
  - `FOLD_FROM: str`, `FOLD_TO: str` (stessa lunghezza; li usa la query del Task 2 in `translate()`);
  - `fold_for_match(text: str) -> str` (riceve testo già in minuscolo);
  - `class Candidate(Protocol)` con le proprietà `best: float` e `is_hit: bool`;
  - `trim_suggestions(candidates: Sequence[C], limit: int) -> list[C]`, con `C = TypeVar("C", bound=Candidate)`.

- [ ] **Step 1: Il test che fallisce**

Crea `backend/tests/domain/test_suggestions.py`:

```python
"""La regola che decide quali suggerimenti si vedono (spec
docs/superpowers/specs/2026-10-06-suggerimenti-soglia-bozza.md, §6 e §10).

Table-driven come `test_rules.py`: la regola è pura, e qui si prova ogni ramo — solo
riscontri, riscontri e sfumati, solo sfumati sopra e sotto le due soglie, il limite.
"""

from dataclasses import dataclass

import pytest

from app.domain.suggestions import FOLD_FROM, FOLD_TO, fold_for_match, trim_suggestions


@dataclass(frozen=True)
class C:
    name: str
    best: float
    is_hit: bool


def names(rows: list[C]) -> list[str]:
    return [row.name for row in rows]


@pytest.mark.parametrize(
    "candidates,limit,expected",
    [
        pytest.param([], 10, [], id="niente in ingresso, niente in uscita"),
        pytest.param(
            [C("zucchero", 0.5, True), C("zucchina", 0.5, True), C("zucchero a velo", 0.29, True)],
            10,
            ["zucchero", "zucchina", "zucchero a velo"],
            id="solo riscontri: passano tutti, anche sotto il pavimento",
        ),
        pytest.param(
            [C("olio di oliva", 0.45, True), C("olive verdi", 0.9, False)],
            10,
            ["olio di oliva"],
            id="un riscontro basta a tenere fuori ogni sfumato, anche il più simile",
        ),
        pytest.param(
            [C("pomodoro", 0.60, False), C("pomodorini", 0.50, False), C("porro", 0.45, False)],
            10,
            ["pomodoro", "pomodorini"],
            id="senza riscontri, gli sfumati da 0,8 per il primo in su (0,48)",
        ),
        pytest.param(
            [C("bietola", 0.35, False), C("bresaola", 0.30, False), C("burro", 0.29, False)],
            10,
            ["bietola", "bresaola"],
            id="il pavimento vale quando 0,8 per il primo gli sta sotto, e 0,30 passa",
        ),
        pytest.param(
            [C("zucchero", 0.28, False)],
            10,
            [],
            id="senza riscontri e sotto il pavimento: la lista è vuota",
        ),
        pytest.param(
            [C(f"pasta {i:02}", 0.4, True) for i in range(12)],
            10,
            [f"pasta {i:02}" for i in range(10)],
            id="più riscontri del limite: i primi dieci",
        ),
        pytest.param(
            [C(f"riso {i:02}", 0.5, False) for i in range(12)],
            10,
            [f"riso {i:02}" for i in range(10)],
            id="più sfumati del limite: i primi dieci",
        ),
        pytest.param(
            [C("tè", 0.2, True), C("tempeh", 0.25, True), C("patate", 0.4, False)],
            1,
            ["tè"],
            id="il limite vale anche sotto dieci, e l'ordine non cambia",
        ),
    ],
)
def test_trim_suggestions(candidates, limit, expected):
    assert names(trim_suggestions(candidates, limit)) == expected


def test_le_due_stringhe_di_translate_sono_lunghe_uguali():
    """`translate()` di Postgres cancella in silenzio un carattere di FOLD_FROM senza il
    suo corrispondente in FOLD_TO: una lettera accentata aggiunta da una parte sola
    sparirebbe dal nome, invece di perdere l'accento, e nessun errore lo direbbe."""
    assert len(FOLD_FROM) == len(FOLD_TO)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("caffè", "caffe"),
        ("tè", "te"),
        ("perché più così", "perche piu cosi"),
        ("sott'olio", "sott olio"),
        ("sott’olio", "sott olio"),
        ("pan-carré", "pan carre"),
        ("  olio   di  semi ", "olio di semi"),
        ("jalapeño, açaí", "jalapeno, acai"),
    ],
)
def test_fold_for_match(raw, expected):
    assert fold_for_match(raw) == expected
```

- [ ] **Step 2: Il test fallisce**

Run (da `<worktree>/backend`): `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/domain/test_suggestions.py`
Expected: FAIL all'import, `ModuleNotFoundError: No module named 'app.domain.suggestions'`.

- [ ] **Step 3: Il modulo**

Crea `backend/app/domain/suggestions.py`:

```python
"""Dove si taglia la lista dei suggerimenti. Modulo puro: nessun accesso al database.

Spec: docs/superpowers/specs/2026-10-06-suggerimenti-soglia-bozza.md (§6, §10). La
misura dice che il punteggio non separa il giusto dal rumore — un prefisso lungo ha una
somiglianza trigram bassa per come è fatta `similarity`, e il rumore sta fra 0,17 e 0,30
come una parte dei bersagli — mentre «contiene il testo» sì. Per questo il taglio guarda
prima chi contiene il testo, e il punteggio solo quando nessuno lo contiene.
"""

from collections.abc import Sequence
from typing import Protocol, TypeVar

# Senza riscontri passano gli sfumati con best ≥ max(FUZZY_FLOOR, FUZZY_RELATIVE × il
# più simile). Il pavimento l'ha deciso Mattia il 2026-10-07 (decisione 1): senza, un
# ingrediente che non c'è mostrerebbe quasi sempre una o due righe sbagliate.
FUZZY_RELATIVE = 0.8
FUZZY_FLOOR = 0.30

# Quel che il riscontro non distingue: gli accenti (decisione 2) e i separatori di parola,
# che diventano spazi. `translate()` di Postgres riceve queste due stringhe com'è, e
# `fold_for_match` ne fa la tabella di Python: una copia sola, per i due lati del
# confronto. Devono restare lunghe uguali (`translate()` cancella un carattere senza
# corrispondente, in silenzio).
FOLD_FROM = "àáâäèéêëìíîïòóôöùúûüçñ'’-"
FOLD_TO = "aaaaeeeeiiiioooouuuucn   "

_FOLD_TABLE = str.maketrans(FOLD_FROM, FOLD_TO)


def fold_for_match(text: str) -> str:
    """Il testo cercato come lo confronta il riscontro: senza accenti, con apostrofi e
    trattini diventati spazi, e gli spazi ridotti a uno. Riceve testo già in minuscolo,
    come i nomi e gli alias dell'anagrafica."""
    return " ".join(text.translate(_FOLD_TABLE).split())


class Candidate(Protocol):
    @property
    def best(self) -> float: ...

    @property
    def is_hit(self) -> bool: ...


C = TypeVar("C", bound=Candidate)


def trim_suggestions(candidates: Sequence[C], limit: int) -> list[C]:
    """Le righe da mostrare, al massimo `limit`, nell'ordine in cui arrivano.

    1. Un riscontro (`is_hit`) è un candidato che contiene il testo all'inizio di una
       parola, nel nome o in un alias: lo calcola la query.
    2. Se c'è almeno un riscontro, passano solo i riscontri.
    3. Se non ce n'è nessuno, passano gli sfumati con best ≥ max(FUZZY_FLOOR,
       FUZZY_RELATIVE × il più simile): è il caso del refuso.
    4. Se non resta niente, la lista è vuota, e il chiamante mostra la sua via d'uscita.

    Non riordina mai: chi arriva primo ed è tenuto resta primo.
    """
    hits = [candidate for candidate in candidates if candidate.is_hit]
    if hits:
        return hits[:limit]
    if not candidates:
        return []
    threshold = max(FUZZY_FLOOR, FUZZY_RELATIVE * max(c.best for c in candidates))
    return [candidate for candidate in candidates if candidate.best >= threshold][:limit]
```

- [ ] **Step 4: Il test passa**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/domain/test_suggestions.py`
Expected: `18 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/suggestions.py backend/tests/domain/test_suggestions.py
git commit -m "dominio: la regola dei suggerimenti — chi contiene il testo, e gli altri solo se nessuno lo contiene, col pavimento a 0,30"
```

---

### Task 2: La query dei suggerimenti, e l'endpoint che la usa

**Files:**
- Modify: `backend/app/repositories/ingredients.py` (le importazioni in testa; `search_ingredients`; dopo `search_ingredients`, le funzioni nuove)
- Modify: `backend/app/api/ingredients.py` (le importazioni da `app.repositories.ingredients`; la funzione `search` sotto `@router.get("/search", …)`)
- Test: `backend/tests/api/test_ingredients.py`

**Interfaces:**
- Consumes (Task 1): `FOLD_FROM`, `FOLD_TO`, `fold_for_match(text) -> str`, `trim_suggestions(candidates, limit) -> list`.
- Produces:
  - `ScoredIngredient` (dataclass frozen: `ingredient: Ingredient`, `best: float`, `is_hit: bool`);
  - `async def suggest_ingredients(session: AsyncSession, query: str, limit: int = 10, kind: IngredientKind | None = None) -> list[Ingredient]` — la usano l'endpoint e il Task 3;
  - `search_ingredients` con la firma di oggi, invariata.

- [ ] **Step 1: I test che falliscono**

Leggi `backend/tests/api/test_ingredients.py` com'è sul ramo. In fondo al file aggiungi (le importazioni che servono ci sono già: `Ingredient`, `IngredientAlias`, `IngredientCategory`, `search_ingredients`; la fixture `catalogo` è quella in testa al file):

```python
# --- I suggerimenti tagliati (spec docs/superpowers/specs/2026-10-06-suggerimenti-soglia-bozza.md)
#
# Passano tutti dall'endpoint che il frontend chiama, su Postgres vero (prima lezione di
# CLAUDE.md: si prova la cosa che gira). Le somiglianze nei docstring sono quelle di
# pg_trgm: `similarity` di tutta la stringa.


async def _ingredienti(db_session, *voci):
    """Ogni voce è un nome, o una tupla (nome, alias, …). Il reparto è uno qualunque del
    cibo: la ricerca non lo guarda."""
    creati = {}
    for voce in voci:
        nome, *alias = (voce,) if isinstance(voce, str) else voce
        ingrediente = Ingredient(name=nome, display_name=nome.capitalize(),
                                 category=IngredientCategory.ALTRO)
        for uno in alias:
            ingrediente.aliases.append(IngredientAlias(alias=uno, source="manual"))
        db_session.add(ingrediente)
        creati[nome] = ingrediente
    await db_session.flush()
    return creati


async def _suggeriti(client, q: str, **params) -> list[str]:
    risposta = await client.get("/api/v1/ingredients/search", params={"q": q, **params})
    assert risposta.status_code == 200
    return [voce["name"] for voce in risposta.json()]


async def test_i_suggerimenti_tengono_solo_chi_contiene_il_testo(logged_client, db_session):
    """Il caso del giro di T3. Zucchero e zucchina cominciano con «zucch» (0,500 tutti e
    due); la zucca no, anche se somiglia uguale (0,500): esce. Fra i due resta l'ordine di
    sempre, alfabetico a parità di tutto (decisione 5: nessuno spareggio nuovo). La ricerca
    di `match_name` e dei vicini dell'AI la zucca la vede ancora."""
    await _ingredienti(db_session, "zucchero", "zucchina", "zucca")

    assert await _suggeriti(logged_client, "zucch") == ["zucchero", "zucchina"]
    assert "zucca" in [i.name for i in await search_ingredients(db_session, "zucch")]


async def test_un_alias_con_il_testo_a_inizio_parola_e_un_riscontro(logged_client, db_session):
    """Decisione 4 (Mattia): l'inizio di una parola vale in ogni alias. «tonno sott'olio»
    ha «olio» dopo l'apostrofo, quindi Tonno in scatola resta; «olive verdi» (0,214) non
    contiene «olio» ed esce."""
    await _ingredienti(
        db_session, "olio di oliva", ("tonno in scatola", "tonno sott'olio"), "olive verdi"
    )

    assert set(await _suggeriti(logged_client, "olio")) == {"olio di oliva", "tonno in scatola"}


async def test_i_vicini_per_l_ai_restano_sfumati(db_session):
    """Decisione 3: il taglio vale solo per l'endpoint. `decide.py` chiede a
    `search_ingredients` tre vicini, e lì uno sfumato che non contiene il testo è
    proprio quel che serve all'AI."""
    await _ingredienti(
        db_session, "olio di oliva", ("tonno in scatola", "tonno sott'olio"), "olive verdi"
    )

    vicini = [i.name for i in await search_ingredients(db_session, "olio", limit=3)]
    assert "olive verdi" in vicini


async def test_pollo_trova_le_parti_del_pollo_a_meta_nome(logged_client, db_session):
    """Le parole di Mattia: «se scrivo "pollo" voglio "petto di pollo", "ali di pollo"».
    «pollame» (0,400) non contiene «pollo» ed esce."""
    await _ingredienti(db_session, "petto di pollo", "ali di pollo", "pollame")

    assert set(await _suggeriti(logged_client, "pollo")) == {"petto di pollo", "ali di pollo"}


async def test_un_riscontro_non_resta_fuori_dal_limite_ne_sotto_il_pavimento(
    logged_client, db_session
):
    """La sesta lezione di CLAUDE.md: un filtro sul risultato non può stare dietro un
    limite. Undici «pollame NN» somigliano a «pollo» più (0,308) di «coscia di pollo
    disossata» (0,250, sotto il pavimento): nell'ordine di `search_ingredients` la coscia
    resta fuori dai dieci, e il taglio dopo non la ritroverebbe. Nei suggerimenti
    `is_hit` la porta davanti, e un riscontro non guarda il pavimento. `match_name`
    (`limit=1`) prende ancora lo sfumato più simile."""
    pollame = [f"pollame {i:02}" for i in range(1, 12)]
    await _ingredienti(db_session, *pollame, "coscia di pollo disossata")

    assert await _suggeriti(logged_client, "pollo") == ["coscia di pollo disossata"]
    oggi = [i.name for i in await search_ingredients(db_session, "pollo")]
    assert "coscia di pollo disossata" not in oggi
    assert (await search_ingredients(db_session, "pollo", limit=1))[0].name in pollame


async def test_senza_accenti_te_trova_il_te(logged_client, db_session):
    """Decisione 2. «tè» somiglia a «te» solo 0,200, sotto il pavimento: senza togliere
    gli accenti sarebbe uno sfumato, e con «tempeh» che è un riscontro resterebbe fuori.
    «patate» contiene «te» ma non all'inizio di una parola."""
    await _ingredienti(db_session, "tè", "tempeh", "patate")

    assert set(await _suggeriti(logged_client, "te")) == {"tè", "tempeh"}


async def test_senza_accenti_caffe_e_un_prefisso_di_caffe(logged_client, db_session):
    """Scelta 10 del piano: anche il prefisso, nei suggerimenti, si confronta senza
    accenti. Tutti e due sono prefissi di «caffe», e vince la somiglianza: caffè 0,500,
    caffelatte 0,417."""
    await _ingredienti(db_session, "caffè", "caffelatte")

    assert await _suggeriti(logged_client, "caffe") == ["caffè", "caffelatte"]


async def test_senza_riscontri_passano_gli_sfumati_vicini_al_primo(logged_client, db_session):
    """Il refuso nella parola intera: nessuno contiene «pomodorr». La soglia è
    max(0,30; 0,8 × 0,636) = 0,509: pomodorini (0,538) passa, pomodori secchi (0,389)
    no."""
    await _ingredienti(db_session, "pomodoro", "pomodorini", "pomodori secchi")

    assert await _suggeriti(logged_client, "pomodorr") == ["pomodoro", "pomodorini"]


async def test_un_ingrediente_che_non_c_e_da_una_lista_vuota(logged_client, db_session):
    """«zenzero» somiglia a «zucchero» 0,214: oggi è un suggerimento (sopra lo 0,15), e
    toccarlo legava la voce all'ingrediente sbagliato. Sotto il pavimento la lista è
    vuota, e il chiamante mostra la sua via d'uscita."""
    await _ingredienti(db_session, "zucchero")

    assert [i.name for i in await search_ingredients(db_session, "zenzero")] == ["zucchero"]
    assert await _suggeriti(logged_client, "zenzero") == []


async def test_percento_e_trattino_basso_sono_lettere(logged_client, db_session, catalogo):
    """Prima, «p%» faceva `LIKE 'p%%'` e trovava come prefisso ogni nome che comincia per
    p. Ora `%` e `_` sono lettere, nei suggerimenti e in `search_ingredients`; e una sola
    lettera somiglia a ogni nome meno di 0,15."""
    assert await search_ingredients(db_session, "p%") == []
    assert await search_ingredients(db_session, "p_") == []
    assert await _suggeriti(logged_client, "p%") == []
    assert await _suggeriti(logged_client, "p_") == []


async def test_i_suggerimenti_non_superano_il_limite(logged_client, db_session):
    await _ingredienti(db_session, *[f"pasta {i:02}" for i in range(1, 13)])

    assert len(await _suggeriti(logged_client, "pasta")) == 10
    assert len(await _suggeriti(logged_client, "pasta", limit=3)) == 3


async def test_il_refuso_e_l_alias_di_sempre_passano_anche_dall_endpoint(logged_client, catalogo):
    """I due test di sempre che passavano dagli sfumati, ora attraverso l'endpoint:
    «yogrut greco» non contiene niente e somiglia 0,529, sopra le due soglie; «pelati»
    sta a metà dell'alias «pomodori pelati», e con la decisione 4 è un riscontro."""
    assert (await _suggeriti(logged_client, "yogrut greco"))[0] == "yogurt greco"
    assert await _suggeriti(logged_client, "pelati") == ["pomodoro"]
```

- [ ] **Step 2: I test falliscono**

Run (da `<worktree>/backend`): `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/api/test_ingredients.py`
Expected: falliscono otto test nuovi — `test_i_suggerimenti_tengono_solo_chi_contiene_il_testo` (c'è la zucca), `test_un_alias_con_il_testo_a_inizio_parola_e_un_riscontro` (ci sono le olive), `test_pollo_trova_le_parti_del_pollo_a_meta_nome` (c'è il pollame), `test_un_riscontro_non_resta_fuori_dal_limite_ne_sotto_il_pavimento`, `test_senza_accenti_caffe_e_un_prefisso_di_caffe` (caffelatte primo), `test_senza_riscontri_passano_gli_sfumati_vicini_al_primo` (ci sono i pomodori secchi), `test_un_ingrediente_che_non_c_e_da_una_lista_vuota` e `test_percento_e_trattino_basso_sono_lettere`. Ne passano già quattro, che sono le guardie di quel che non deve cambiare o che oggi riesce per un'altra strada: `test_i_vicini_per_l_ai_restano_sfumati`, `test_i_suggerimenti_non_superano_il_limite`, `test_il_refuso_e_l_alias_di_sempre_passano_anche_dall_endpoint`, e `test_senza_accenti_te_trova_il_te` (oggi il tè passa come sfumato a 0,200, sopra lo 0,15; dopo il taglio passa solo perché senza accenti è un riscontro). I test di oggi del file passano.

- [ ] **Step 3: Il repository**

Leggi `backend/app/repositories/ingredients.py` com'è sul ramo.

1. Le importazioni in testa. Sostituisci

```python
from sqlalchemy import case, func, select
```

con

```python
from sqlalchemy import String, case, func, select
```

e, dopo `from app.domain.rules import IngredientKind`, aggiungi

```python
from app.domain.suggestions import FOLD_FROM, FOLD_TO, fold_for_match, trim_suggestions
```

2. Sopra `async def search_ingredients(`, aggiungi:

```python
def _purchase_counts():
    """Quante righe di lista ha ogni ingrediente: lo spareggio di «quel che compri
    davvero», in comune fra la ricerca e i suggerimenti."""
    return (
        select(ShoppingListItem.ingredient_id, func.count().label("uses"))
        .where(ShoppingListItem.ingredient_id.is_not(None))
        .group_by(ShoppingListItem.ingredient_id)
        .subquery()
    )
```

3. In `search_ingredients`: in fondo al docstring, prima delle virgolette che lo chiudono, aggiungi il paragrafo

```python

    È la ricerca di `match_name` e dei vicini per l'AI, che vivono degli sfumati: i
    suggerimenti a video passano da `suggest_ingredients`, che taglia (spec
    2026-10-06-suggerimenti-soglia, decisione 3).
```

poi sostituisci

```python
    purchases = (
        select(ShoppingListItem.ingredient_id, func.count().label("uses"))
        .where(ShoppingListItem.ingredient_id.is_not(None))
        .group_by(ShoppingListItem.ingredient_id)
        .subquery()
    )
```

con

```python
    purchases = _purchase_counts()
```

e sostituisci

```python
    name_is_prefix = Ingredient.name.like(f"{cleaned}%")
    alias_is_prefix = func.bool_or(IngredientAlias.alias.like(f"{cleaned}%"))
```

con

```python
    # `autoescape`: un `%` o un `_` scritti sono lettere, non jolly del LIKE
    name_is_prefix = Ingredient.name.startswith(cleaned, autoescape=True)
    alias_is_prefix = func.bool_or(IngredientAlias.alias.startswith(cleaned, autoescape=True))
```

Nient'altro cambia in `search_ingredients`: né il filtro, né l'ordine, né il limite.

4. Subito dopo la fine di `search_ingredients` (prima di `def canonical_name(`), aggiungi:

```python
@dataclass(frozen=True)
class ScoredIngredient:
    """Un candidato dei suggerimenti, con quel che serve a `trim_suggestions` per
    decidere se si vede: la somiglianza migliore fra nome e alias, e se contiene il
    testo all'inizio di una parola."""

    ingredient: Ingredient
    best: float
    is_hit: bool


def _folded(column):
    """La colonna come la confronta il riscontro: senza accenti, apostrofi e trattini
    (le stesse `FOLD_FROM`/`FOLD_TO` di `fold_for_match`), e con uno spazio davanti,
    così «all'inizio di una parola» diventa «dopo uno spazio» anche per la prima."""
    return func.concat(" ", func.translate(column, FOLD_FROM, FOLD_TO, type_=String))


async def _suggestion_candidates(
    session: AsyncSession, query: str, limit: int, kind: IngredientKind | None,
) -> list[ScoredIngredient]:
    """I candidati dei suggerimenti, già nell'ordine in cui `trim_suggestions` li vuole.

    Rispetto a `search_ingredients`: il prefisso si confronta senza accenti; un
    riscontro (`is_hit`, il testo all'inizio di una parola del nome o di un alias)
    passa il filtro anche sotto lo 0,15 e viene subito dopo i prefissi. È quel che
    rende sicuro il `LIMIT`: i riscontri arrivano prima di ogni sfumato, e senza
    riscontri gli sfumati arrivano dal più simile in giù, quindi le righe che il taglio
    tiene sono sempre in testa (sesta lezione di CLAUDE.md).
    """
    cleaned = query.strip().lower()
    folded = fold_for_match(cleaned)
    if not folded:
        return []

    purchases = _purchase_counts()

    name_similarity = func.similarity(Ingredient.name, cleaned)
    alias_similarity = func.coalesce(func.max(func.similarity(IngredientAlias.alias, cleaned)), 0.0)
    best_similarity = func.greatest(name_similarity, alias_similarity)

    # `autoescape`: un `%` o un `_` scritti sono lettere, non jolly del LIKE
    name_folded = _folded(Ingredient.name)
    alias_folded = _folded(IngredientAlias.alias)
    word = f" {folded}"
    is_prefix_match = name_folded.startswith(word, autoescape=True) | func.coalesce(
        func.bool_or(alias_folded.startswith(word, autoescape=True)), False
    )
    is_hit = name_folded.contains(word, autoescape=True) | func.coalesce(
        func.bool_or(alias_folded.contains(word, autoescape=True)), False
    )

    purchase_count = func.coalesce(func.max(purchases.c.uses), 0)

    statement = (
        select(Ingredient, best_similarity.label("best"), is_hit.label("is_hit"))
        .outerjoin(IngredientAlias, IngredientAlias.ingredient_id == Ingredient.id)
        .outerjoin(purchases, purchases.c.ingredient_id == Ingredient.id)
        .group_by(Ingredient.id)
    )
    if kind is not None:
        statement = statement.where(Ingredient.kind == kind)
    statement = (
        statement
        .having((best_similarity >= SIMILARITY_FLOOR) | is_prefix_match | is_hit)
        .order_by(
            # l'ordine di `search_ingredients`, con i riscontri subito dopo i prefissi
            is_prefix_match.desc(),
            is_hit.desc(),
            case((is_prefix_match, purchase_count), else_=0).desc(),
            best_similarity.desc(),
            purchase_count.desc(),
            Ingredient.name.asc(),
        )
        .limit(limit)
    )
    rows = (await session.execute(statement)).all()
    return [
        ScoredIngredient(ingredient=row[0], best=float(row.best), is_hit=bool(row.is_hit))
        for row in rows
    ]


async def suggest_ingredients(
    session: AsyncSession, query: str, limit: int = 10,
    kind: IngredientKind | None = None,
) -> list[Ingredient]:
    """I suggerimenti che `/ingredients/search` mostra: chi contiene il testo, e gli altri
    solo se nessuno lo contiene (`trim_suggestions`; spec
    docs/superpowers/specs/2026-10-06-suggerimenti-soglia-bozza.md).

    La chiamano l'endpoint e il comando che misura (`app.cli.measure_suggestions`), e
    nessun altro: `match_name` e i vicini per l'AI restano su `search_ingredients`
    (decisione 3).
    """
    candidates = await _suggestion_candidates(session, query, limit, kind)
    return [candidate.ingredient for candidate in trim_suggestions(candidates, limit)]
```

`dataclass` è già importato in testa al file (`from dataclasses import dataclass`): verificalo, e se sul ramo non c'è aggiungilo.

- [ ] **Step 4: L'endpoint**

Leggi `backend/app/api/ingredients.py` com'è sul ramo. Nelle importazioni da `app.repositories.ingredients`, sostituisci la riga `    search_ingredients,` con `    suggest_ingredients,` (l'endpoint era l'unica chiamata di `search_ingredients` in questo file: `grep -n "search_ingredients(\|    search_ingredients," backend/app/api/ingredients.py` dopo la modifica non stampa niente; il commento qui sotto la nomina, e va bene).

Nella funzione `search` sotto `@router.get("/search", response_model=list[IngredientOut])`, sostituisci

```python
    found = await search_ingredients(session, q, limit, kind=kind)
    return [IngredientOut.model_validate(i) for i in found]
```

con

```python
    # i suggerimenti tagliati: chi contiene il testo, e gli altri solo se nessuno lo
    # contiene. La ricerca coi suoi sfumati resta `search_ingredients`, per `match_name`
    # e per i vicini dell'AI (spec 2026-10-06-suggerimenti-soglia, decisione 3)
    found = await suggest_ingredients(session, q, limit, kind=kind)
    return [IngredientOut.model_validate(i) for i in found]
```

La firma della funzione, i parametri (`q`, `limit` con `le=50`, `kind`) e la risposta non cambiano.

- [ ] **Step 5: I test passano, tutti**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/api/test_ingredients.py`
Expected: tutto verde, dodici test in più di prima nel file.

Poi la suite intera (gli altri chiamanti di `search_ingredients` e `test_decide_terms.py` devono restare verdi senza toccarli):

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q`
Expected: `N_pytest` + 30 (18 del Task 1, 12 di questo), tutti verdi. Se un test di oggi fallisce, vedi «Margine di autonomia»: non si migra, si diagnostica.

- [ ] **Step 6: Commit**

```bash
git add backend/app/repositories/ingredients.py backend/app/api/ingredients.py backend/tests/api/test_ingredients.py
git commit -m "suggerimenti: l'endpoint mostra chi contiene il testo a inizio parola, nel nome o in un alias e senza accenti, e gli sfumati solo senza riscontri; % e _ sono lettere"
```

---

### Task 3: La misura, un comando di sola lettura

**Files:**
- Create: `backend/app/cli/measure_suggestions.py`
- Test: `backend/tests/test_measure_suggestions_cli.py`

**Interfaces:**
- Consumes (Task 2): `search_ingredients(session, query, limit)` (la lista di prima) e `suggest_ingredients(session, query, limit)` (quella di adesso), da `app.repositories.ingredients`.
- Produces: `python -m app.cli.measure_suggestions`, e per il test: `CatalogEntry(id, name, aliases)`, `Probe(family, text, target)`, `typos(word, rng) -> list[str]`, `build_probes(catalog, rng) -> list[Probe]`, `async load_catalog(session) -> list[CatalogEntry]`, `async measure(session, probes) -> dict[str, FamilyStats]`, `format_report(stats) -> str`, `SEED = 20261006`.

- [ ] **Step 1: I test che falliscono**

Crea `backend/tests/test_measure_suggestions_cli.py`:

```python
import random
import uuid

from app.cli.measure_suggestions import (
    SEED,
    CatalogEntry,
    Probe,
    build_probes,
    format_report,
    load_catalog,
    measure,
    typos,
)
from app.db.models.ingredient import Ingredient, IngredientCategory


def test_tre_refusi_diversi_dalla_parola_e_sempre_gli_stessi():
    primi = typos("pomodoro", random.Random(1))
    assert primi == typos("pomodoro", random.Random(1))
    assert len(primi) == 3
    assert all(refuso != "pomodoro" for refuso in primi)
    # una lettera che manca, due scambiate, una sostituita: la lunghezza cambia di uno
    # solo nel primo
    assert [len(refuso) for refuso in primi] == [7, 8, 8]


def test_le_prove_nascono_dal_nome_e_dagli_alias():
    """Le regole del §3.2 della bozza: i prefissi di 3–6 lettere e il nome intero, i
    prefissi di 4 e 6 lettere e l'alias intero, i due caratteri a parte, tre refusi sul
    nome intero e tre sui primi sei caratteri."""
    target = uuid.uuid4()
    probes = build_probes([CatalogEntry(target, "pomodoro", ("pelati",))], random.Random(SEED))

    def testi(family: str) -> list[str]:
        return [p.text for p in probes if p.family == family]

    assert testi("digitazione") == ["pom", "pomo", "pomod", "pomodo", "pomodoro", "pela", "pelati"]
    assert testi("due lettere") == ["po"]
    assert len(testi("refusi")) == 6
    assert {p.target for p in probes} == {target}


async def test_la_misura_conta_chi_resta_e_chi_si_perde(db_session):
    """Sul Postgres vero, con le due funzioni vere. «zucch» → zucchina: c'è prima e dopo,
    ma non è prima (zucchero, alfabetico); le righe scendono da 3 a 2 (via la zucca).
    «zenzero» → zucchero: prima c'era (0,214), dopo no, ed è un perso."""
    for nome in ("zucchero", "zucchina", "zucca"):
        db_session.add(Ingredient(name=nome, display_name=nome.capitalize(),
                                  category=IngredientCategory.ALTRO))
    await db_session.flush()
    catalog = {entry.name: entry for entry in await load_catalog(db_session)}
    assert {"zucchero", "zucchina", "zucca"} <= catalog.keys()

    stats = await measure(db_session, [
        Probe("digitazione", "zucch", catalog["zucchina"].id),
        Probe("digitazione", "zenzero", catalog["zucchero"].id),
    ])

    digitazione = stats["digitazione"]
    assert digitazione.probes == 2
    assert (digitazione.kept_before, digitazione.kept_after) == (2, 1)
    assert (digitazione.first_before, digitazione.first_after) == (1, 0)
    assert digitazione.rows_before == [3, 1]
    assert digitazione.rows_after == [2, 0]
    assert digitazione.lost == ["zenzero"]
    assert "digitazione: 2 prove" in format_report(stats)
```

- [ ] **Step 2: I test falliscono**

Run (da `<worktree>/backend`): `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/test_measure_suggestions_cli.py`
Expected: FAIL all'import, `ModuleNotFoundError: No module named 'app.cli.measure_suggestions'`.

- [ ] **Step 3: Il comando**

Crea `backend/app/cli/measure_suggestions.py`:

```python
"""La misura dei suggerimenti: quante righe si vedono, e se il bersaglio c'è ancora.

Eseguire con `python -m app.cli.measure_suggestions` dentro il container del backend.
Legge e basta: la transazione è `READ ONLY` e finisce con un rollback, quindi si può
lanciare anche sulla produzione (con il via di Mattia: è una lettura della produzione).

Rifà, sull'anagrafica del database a cui è collegato, la misura della bozza
docs/superpowers/specs/2026-10-06-suggerimenti-soglia-bozza.md (§3.2), con lo stesso seme
del campionamento. Le prove nascono dall'anagrafica stessa:

- «digitazione»: per ogni ingrediente i prefissi di 3, 4, 5 e 6 lettere e il nome
  intero; per un campione di alias (fino a 150) i prefissi di 4 e 6 lettere e l'alias
  intero. Il bersaglio è l'ingrediente da cui la prova nasce;
- «due lettere»: il prefisso di due lettere di ogni nome, a parte, perché lì la
  somiglianza trigram non dice quasi niente;
- «refusi»: tre refusi sul nome intero (se ha almeno 5 lettere) e tre sui suoi primi
  sei caratteri — una lettera che manca, due vicine scambiate, una sostituita.

Ogni prova passa da `search_ingredients` (la lista di prima: lo stesso ordine e il
taglio a dieci di sempre) e da `suggest_ingredients` (quella che l'endpoint mostra
adesso). «Persi» sono le prove il cui bersaglio c'era prima e non c'è più: nella
famiglia «digitazione» devono essere zero; nei refusi a metà parola sono il prezzo
dichiarato del pavimento (§6 della bozza).
"""

import asyncio
import random
import statistics
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.db.models.ingredient import Ingredient
from app.repositories.ingredients import search_ingredients, suggest_ingredients

SEED = 20261006
ALIAS_SAMPLE = 150
LIMIT = 10
TYPO_LETTERS = "abcdefghilmnoprstuvz"
MAX_LOST_SHOWN = 20
FAMILIES = ("digitazione", "due lettere", "refusi")


@dataclass(frozen=True)
class CatalogEntry:
    id: uuid.UUID
    name: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class Probe:
    family: str
    text: str
    target: uuid.UUID


def typos(word: str, rng: random.Random) -> list[str]:
    """Tre refusi di `word`, sempre a una posizione interna (né la prima lettera né
    l'ultima): una lettera che manca, due vicine scambiate (saltato se sono uguali),
    una sostituita con un'altra lettera dell'alfabeto italiano."""
    if len(word) < 4:
        return []
    out = []
    i = rng.randrange(1, len(word) - 1)
    out.append(word[:i] + word[i + 1:])
    j = rng.randrange(1, len(word) - 2)
    if word[j] != word[j + 1]:
        out.append(word[:j] + word[j + 1] + word[j] + word[j + 2:])
    k = rng.randrange(1, len(word) - 1)
    replacement = rng.choice([letter for letter in TYPO_LETTERS if letter != word[k]])
    out.append(word[:k] + replacement + word[k + 1:])
    return out


def build_probes(catalog: list[CatalogEntry], rng: random.Random) -> list[Probe]:
    """Le prove, nell'ordine in cui il seme le rende ripetibili: prima i nomi, poi il
    campione di alias, poi i refusi. `catalog` va passato già ordinato per nome."""
    probes: list[Probe] = []
    for entry in catalog:
        name = entry.name
        for size in (3, 4, 5, 6):
            if len(name) > size:
                probes.append(Probe("digitazione", name[:size], entry.id))
        probes.append(Probe("digitazione", name, entry.id))
        if len(name) > 2:
            probes.append(Probe("due lettere", name[:2], entry.id))
    pairs = sorted((alias, entry.id) for entry in catalog for alias in entry.aliases)
    for alias, target in rng.sample(pairs, min(ALIAS_SAMPLE, len(pairs))):
        for size in (4, 6):
            if len(alias) > size:
                probes.append(Probe("digitazione", alias[:size], target))
        probes.append(Probe("digitazione", alias, target))
    for entry in catalog:
        if len(entry.name) >= 5:
            probes += [Probe("refusi", t, entry.id) for t in typos(entry.name, rng)]
        if len(entry.name) > 6:
            probes += [Probe("refusi", t, entry.id) for t in typos(entry.name[:6], rng)]
    return probes


@dataclass
class FamilyStats:
    probes: int = 0
    kept_before: int = 0
    kept_after: int = 0
    first_before: int = 0
    first_after: int = 0
    rows_before: list[int] = field(default_factory=list)
    rows_after: list[int] = field(default_factory=list)
    lost: list[str] = field(default_factory=list)

    def add(self, probe: Probe, before: list[uuid.UUID], after: list[uuid.UUID]) -> None:
        self.probes += 1
        self.kept_before += probe.target in before
        self.kept_after += probe.target in after
        self.first_before += bool(before) and before[0] == probe.target
        self.first_after += bool(after) and after[0] == probe.target
        self.rows_before.append(len(before))
        self.rows_after.append(len(after))
        if probe.target in before and probe.target not in after:
            self.lost.append(probe.text)


async def load_catalog(session: AsyncSession) -> list[CatalogEntry]:
    """Tutta l'anagrafica, ordinata per nome: l'ordine fa parte del seme."""
    ingredients = (await session.execute(select(Ingredient).order_by(Ingredient.name))).scalars()
    return [
        CatalogEntry(i.id, i.name, tuple(sorted(a.alias for a in i.aliases)))
        for i in ingredients
    ]


async def measure(session: AsyncSession, probes: list[Probe]) -> dict[str, FamilyStats]:
    stats: dict[str, FamilyStats] = {}
    for probe in probes:
        before = [i.id for i in await search_ingredients(session, probe.text, LIMIT)]
        after = [i.id for i in await suggest_ingredients(session, probe.text, LIMIT)]
        stats.setdefault(probe.family, FamilyStats()).add(probe, before, after)
    return stats


def _pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.1f} %" if whole else "–"


def format_report(stats: dict[str, FamilyStats]) -> str:
    lines: list[str] = []
    for family in FAMILIES:
        s = stats.get(family)
        if s is None or s.probes == 0:
            continue
        lost = f"persi: {len(s.lost)}"
        if s.lost:
            lost += f" (i primi: {', '.join(repr(t) for t in s.lost[:MAX_LOST_SHOWN])})"
        lines += [
            f"{family}: {s.probes} prove",
            f"  bersaglio in lista: {_pct(s.kept_before, s.probes)} prima, {_pct(s.kept_after, s.probes)} dopo",
            f"  bersaglio primo:    {_pct(s.first_before, s.probes)} prima, {_pct(s.first_after, s.probes)} dopo",
            f"  righe, media:       {statistics.mean(s.rows_before):.2f} prima, {statistics.mean(s.rows_after):.2f} dopo",
            f"  righe, mediana:     {statistics.median(s.rows_before):g} prima, {statistics.median(s.rows_after):g} dopo",
            f"  liste da {LIMIT}:       {_pct(s.rows_before.count(LIMIT), s.probes)} prima, {_pct(s.rows_after.count(LIMIT), s.probes)} dopo",
            f"  liste vuote:        {_pct(s.rows_before.count(0), s.probes)} prima, {_pct(s.rows_after.count(0), s.probes)} dopo",
            f"  {lost}",
        ]
    return "\n".join(lines)


async def main() -> int:
    async with SessionLocal() as session:
        # la prima istruzione della transazione: da qui in poi Postgres rifiuta ogni
        # scrittura, qualunque cosa faccia il codice sotto
        await session.execute(text("SET TRANSACTION READ ONLY"))
        catalog = await load_catalog(session)
        if not catalog:
            print("L'anagrafica è vuota: niente da misurare. Semina prima (python -m app.cli.seed).")
            await session.rollback()
            return 0
        probes = build_probes(catalog, random.Random(SEED))
        stats = await measure(session, probes)
        await session.rollback()
    print(f"Anagrafica: {len(catalog)} ingredienti, {sum(len(e.aliases) for e in catalog)} alias.")
    print(format_report(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
```

- [ ] **Step 4: I test passano**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/test_measure_suggestions_cli.py`
Expected: `3 passed`.

Se `test_le_prove_nascono_dal_nome_e_dagli_alias` trova 5 refusi e non 6, uno scambio è caduto su due lettere uguali con questo seme: il conto è giusto così; correggi il numero atteso a quel che `typos` produce davvero e scrivilo nel report (non è un difetto: è la regola «saltato se sono uguali»). Con il codice qui sopra, scrivendo il piano sono usciti 6.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cli/measure_suggestions.py backend/tests/test_measure_suggestions_cli.py
git commit -m "cli: measure_suggestions, la misura della bozza rifatta sull'anagrafica del database, in sola lettura"
```

---

### Task 4: La nota di ripiego in `IngredientPicker`

**Files:**
- Modify: `frontend/src/components/IngredientPicker.tsx` (il commento della prop `emptyNote`; il `<p>` di `emptyNote` nel JSX)
- Test: `frontend/src/components/IngredientPicker.test.tsx`

**Interfaces:**
- Consumes: niente dei task prima (la regola del backend arriva dall'endpoint; qui i test stubbano `fetch`).
- Produces: il testo a video «Nessun ingrediente somiglia a «…». Prova con un'altra parola.», che il Task 5 cerca nel browser.

- [ ] **Step 1: I test che falliscono**

Leggi `frontend/src/components/IngredientPicker.test.tsx` com'è sul ramo. Dentro `describe("IngredientPicker", …)`, dopo il test `"con onCreate la nota del vuoto lascia il posto all'offerta di creare"`, aggiungi:

```tsx
  // La nota di ripiego (spec 2026-10-06-suggerimenti-soglia, §7 e decisione 6): coi
  // suggerimenti tagliati una ricerca vuota non è più rara, e cinque schermi non passano
  // né `onCreate` né `emptyNote`. Senza la nota il pannello resterebbe muto sotto un campo
  // pieno: il vicolo cieco che il commento di `emptyNote` nomina.
  it("senza onCreate né emptyNote, a ricerca finita e vuota dice che niente somiglia, e come andare avanti", async () => {
    stubRoutedFetch(() => [[], 200]);
    renderWithClient(<IngredientPicker label="Ingrediente" failureNote="x" onPick={() => {}} />);
    fireEvent.change(screen.getByLabelText("Ingrediente"), { target: { value: "tamarindo" } });
    // mentre si scrive, prima che la ricerca sia finita, niente nota
    expect(screen.queryByText(/Nessun ingrediente somiglia/)).toBeNull();
    expect(
      await screen.findByText("Nessun ingrediente somiglia a «tamarindo». Prova con un'altra parola.")
    ).toBeDefined();
  });

  it("la nota di ripiego non compare se la ricerca trova qualcosa", async () => {
    stubRoutedFetch(() => [[LATTE], 200]);
    renderWithClient(<IngredientPicker label="Ingrediente" failureNote="x" onPick={() => {}} />);
    fireEvent.change(screen.getByLabelText("Ingrediente"), { target: { value: "lat" } });
    await screen.findByRole("option", { name: "Latte" });
    expect(screen.queryByText(/Nessun ingrediente somiglia/)).toBeNull();
  });

  it("la nota di ripiego non compare se la ricerca non risponde: lì parla il guasto", async () => {
    stubRoutedFetch(() => [{ detail: "giù" }, 500]);
    renderWithClient(<IngredientPicker label="Ingrediente" failureNote="Riprova." onPick={() => {}} />);
    fireEvent.change(screen.getByLabelText("Ingrediente"), { target: { value: "tamarindo" } });
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "La ricerca degli ingredienti non risponde. Riprova."
    );
    expect(screen.queryByText(/Nessun ingrediente somiglia/)).toBeNull();
  });

  it("la nota di chi lo usa prende il posto di quella di ripiego", async () => {
    stubRoutedFetch(() => [[], 200]);
    renderWithClient(
      <IngredientPicker label="Ingrediente" failureNote="x" onPick={() => {}} emptyNote="Scrivilo in lista." />
    );
    fireEvent.change(screen.getByLabelText("Ingrediente"), { target: { value: "tamarindo" } });
    await screen.findByText("Scrivilo in lista.");
    expect(screen.queryByText(/Nessun ingrediente somiglia/)).toBeNull();
  });

  it("con onCreate, al posto della nota di ripiego c'è «Aggiungi «…»»", async () => {
    stubRoutedFetch(() => [[], 200]);
    renderWithClient(
      <IngredientPicker label="Ingrediente" failureNote="x" onPick={() => {}} onCreate={() => {}} />
    );
    fireEvent.change(screen.getByLabelText("Ingrediente"), { target: { value: "tamarindo" } });
    await screen.findByRole("button", { name: "Aggiungi «tamarindo»" });
    expect(screen.queryByText(/Nessun ingrediente somiglia/)).toBeNull();
  });

  // S18 anche per la nota: corretto «lattr» in «latte», per tutta l'attesa la risposta
  // vuota in mano è ancora quella di «lattr», e dire che «latte» non somiglia a niente
  // sarebbe falso
  it("la nota di ripiego vale per il testo cercato, mai per uno di prima", async () => {
    stubRoutedFetch(() => [[], 200]);
    renderWithClient(<IngredientPicker label="Ingrediente" failureNote="x" onPick={() => {}} />);
    const campo = screen.getByLabelText("Ingrediente");
    fireEvent.change(campo, { target: { value: "lattr" } });
    await screen.findByText("Nessun ingrediente somiglia a «lattr». Prova con un'altra parola.");

    fireEvent.change(campo, { target: { value: "latte" } });
    expect(screen.queryByText(/Nessun ingrediente somiglia/)).toBeNull();
    expect(
      await screen.findByText("Nessun ingrediente somiglia a «latte». Prova con un'altra parola.")
    ).toBeDefined();
  });
```

- [ ] **Step 2: I test falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/components/IngredientPicker.test.tsx`
Expected: falliscono il primo e l'ultimo dei sei nuovi (la nota non c'è); gli altri quattro passano già — sono le guardie dei confini della nota — e passano tutti i test di oggi.

- [ ] **Step 3: La nota**

Leggi `frontend/src/components/IngredientPicker.tsx` com'è sul ramo.

1. Nel commento della prop `emptyNote`, sostituisci

```tsx
  /** Chi non sa creare un ingrediente dice qui dove andare quando la ricerca non
   * trova niente: senza, il pannello resterebbe muto sotto un campo pieno, ed è un
   * vicolo cieco. Compare alle stesse condizioni dell'offerta di creare, che quando
   * c'è ha la precedenza. */
```

con

```tsx
  /** Chi non sa creare un ingrediente dice qui dove andare quando la ricerca non
   * trova niente. Senza, compare la nota di ripiego «Nessun ingrediente somiglia a
   * «…». Prova con un'altra parola.»: un pannello muto sotto un campo pieno è un vicolo
   * cieco, e coi suggerimenti tagliati (spec 2026-10-06-suggerimenti-soglia) una
   * ricerca vuota non è più rara. Compare alle stesse condizioni dell'offerta di creare,
   * che quando c'è ha la precedenza. */
```

2. Nel JSX, sostituisci

```tsx
      {!onCreate && emptyNote && emptySearch && <p className="text-sm text-ink-soft">{emptyNote}</p>}
```

con

```tsx
      {/* senza chi crea, una ricerca finita e vuota dice sempre qualcosa: la nota di chi
          usa il selettore se la passa, quella di ripiego altrimenti. Per il testo cercato,
          mai per uno di prima (S18): `emptySearch` lo garantisce */}
      {!onCreate && emptySearch && (
        <p className="text-sm text-ink-soft">
          {emptyNote ?? `Nessun ingrediente somiglia a «${debounced}». Prova con un'altra parola.`}
        </p>
      )}
```

(`emptySearch` vale solo quando `debounced` coincide con il testo scritto, già senza spazi ai lati: il nome nella nota è quello cercato.)

- [ ] **Step 4: I test passano, e il resto del frontend**

Run: `npx vitest run src/components/IngredientPicker.test.tsx`
Expected: tutto verde, sei test in più di prima nel file.

Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: vitest `N_vitest` + 6 in `N_file` file, tutto verde; typecheck e lint puliti. Se un test di un chiamante (coda d'import, Anagrafica, filtri del ricettario) fallisce perché una sua ricerca larga ora trova la nota di ripiego, vedi «Margine di autonomia»: si stringe quella ricerca, e lo si scrive nel report.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/IngredientPicker.tsx frontend/src/components/IngredientPicker.test.tsx
git commit -m "IngredientPicker: senza onCreate né emptyNote, a ricerca vuota dice «Nessun ingrediente somiglia a «…». Prova con un'altra parola.»"
```

---

### Task 5: Nel browser vero, e la misura sul seme

**Files:**
- Create: `frontend/e2e/suggerimenti.spec.ts`
- Modify: `frontend/e2e/style.spec.ts` (una prova in fondo al file)

**Interfaces:**
- Consumes: l'endpoint del Task 2, la nota del Task 4, il comando del Task 3; in `style.spec.ts` le funzioni `testiIlleggibili(page)` e `fermo(page)` che ci sono già.
- Produces: i numeri della misura sul seme, per i Task 6 e 7.

- [ ] **Step 1: Le prove**

Crea `frontend/e2e/suggerimenti.spec.ts`:

```ts
import { expect, test, type Page } from "@playwright/test";

/**
 * I suggerimenti tagliati (spec docs/superpowers/specs/2026-10-06-suggerimenti-soglia-bozza.md),
 * provati sull'anagrafica del seme attraverso l'app vera: chi contiene il testo all'inizio
 * di una parola, nel nome o in un alias, e gli altri solo se nessuno lo contiene. Queste
 * prove leggono e basta: non scrivono niente nello stack.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
});

async function suggerimentiInLista(page: Page, testo: string) {
  await page.goto("/lista");
  await page.getByLabel("Aggiungi alla lista", { exact: true }).fill(testo);
  return page.getByRole("listbox", { name: "Suggerimenti: Aggiungi alla lista" });
}

test("«zucch» in lista: lo zucchero e la zucchina sì, la zucca no", async ({ page }) => {
  const elenco = await suggerimentiInLista(page, "zucch");
  await expect(elenco.getByRole("option", { name: /^Zucchina\b/ })).toBeVisible();
  await expect(elenco.getByRole("option", { name: /^Zucchero\b/ }).first()).toBeVisible();
  await expect(elenco.getByRole("option", { name: /^Zucca\b/ })).toHaveCount(0);
  await expect(elenco.getByRole("option", { name: /^Semi misti\b/ })).toHaveCount(0);
});

test("«olio» in lista: il tonno sott'olio sì, per il suo alias; le olive no", async ({ page }) => {
  const elenco = await suggerimentiInLista(page, "olio");
  await expect(elenco.getByRole("option", { name: /^Olio di oliva\b/ })).toBeVisible();
  await expect(elenco.getByRole("option", { name: /^Tonno in scatola\b/ })).toBeVisible();
  await expect(elenco.getByRole("option", { name: /^Olive\b/ })).toHaveCount(0);
  await expect(elenco.getByRole("option", { name: /^Aglio\b/ })).toHaveCount(0);
});

test("«pollo» in lista: petto e coscia di pollo a metà nome, il pisello no", async ({ page }) => {
  const elenco = await suggerimentiInLista(page, "pollo");
  await expect(elenco.getByRole("option", { name: /^Petto di pollo\b/ })).toBeVisible();
  await expect(elenco.getByRole("option", { name: /^Coscia di pollo\b/ })).toBeVisible();
  await expect(elenco.getByRole("option", { name: /^Pisello\b/ })).toHaveCount(0);
  await expect(elenco.getByRole("option", { name: /^Polenta\b/ })).toHaveCount(0);
});

test("un ingrediente che non c'è: nei filtri del ricettario niente righe, e la nota lo dice", async ({
  page,
}) => {
  await page.goto("/ricette");
  await page.getByRole("button", { name: /^Filtri/ }).click();
  await page.getByLabel("Contiene ingredienti").fill("tamarindo");
  await expect(
    page.getByText("Nessun ingrediente somiglia a «tamarindo». Prova con un'altra parola.")
  ).toBeVisible();
  // l'elenco dei suggerimenti, non `option` in tutta la pagina: il «Categoria» del
  // pannello è un <select>, e le sue voci sono `option` anche loro
  await expect(
    page.getByRole("listbox", { name: "Suggerimenti: Contiene ingredienti" })
  ).toHaveCount(0);
});
```

Leggi `frontend/e2e/style.spec.ts` com'è sul ramo e, **in fondo al file**, aggiungi:

```ts
test("la nota di ripiego dei suggerimenti si legge nei due temi", async ({ page }) => {
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  await page.goto("/ricette");
  await page.getByRole("button", { name: /^Filtri/ }).click();
  await page.getByLabel("Contiene ingredienti").fill("tamarindo");
  await expect(
    page.getByText("Nessun ingrediente somiglia a «tamarindo». Prova con un'altra parola.")
  ).toBeVisible();
  for (const tema of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: tema });
    await fermo(page);
    expect(await testiIlleggibili(page), `filtri con la nota di ripiego, tema ${tema}`).toEqual([]);
  }
  await page.emulateMedia({ colorScheme: "light" });
});
```

Se la prova del contrasto segnala la nota sotto 4,5:1, **non cambiare token**: è `text-ink-soft`, lo stesso colore di `emptyNote` in Dispensa; scrivi nel report quale testo, su quale fondo, in quale tema e con quale rapporto, e segna il task `bloccato` — un colore si decide di giorno.

- [ ] **Step 2: Il tipo dei file**

Run (da `frontend/`): `npm run typecheck && npm run lint`
Expected: puliti. `tsc -b` compila anche gli e2e (`tsconfig.node.json`).

- [ ] **Step 3: Lo stack, la misura sul seme, l'e2e intera**

Dalla radice di `<worktree>`, con i comandi delle Global Constraints: `cp .env.example .env`, `up -d --build --wait`, il seme `--con-ricette`. **Prima delle prove**, sul seme appena caricato, la misura:

```bash
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.measure_suggestions
```

Expected: stampa l'anagrafica (187 ingredienti, 299 alias: è `data/ingredients_seed.json`; se le ricette del seme ne aggiungono, il numero è un po' più alto) e le tre famiglie. Scrivendo il piano la stessa misura è stata simulata fuori da Postgres, con un'emulazione di `pg_trgm` e le stesse regole: **digitazione** 1.270 prove, bersaglio in lista 100 % prima e dopo, bersaglio primo 85,9 % prima e dopo, righe in media da 5,16 a 1,65 (mediana da 5 a 1), liste da dieci da 15,9 % a 0,6 %, **persi 0**; **due lettere** 186 prove, bersaglio in lista 95,7 % prima e dopo, righe in media da 5,60 a 6,54 (con due lettere i riscontri a metà nome e negli alias sono tanti: è l'effetto della decisione 4, non un difetto); **refusi** 912 prove, bersaglio in lista da 93,0 % a 59,0 %, liste vuote da 1,8 % a 33,8 % (il prezzo del pavimento, dichiarato nel §6 della bozza). I numeri veri possono scostarsi di poco (purchase_count, alias delle ricette del seme). **Copia l'uscita intera nel report** (Task 7): è l'anagrafica pubblica del seme, non dati di produzione.

Se nella famiglia «digitazione» i persi non sono zero: non è un motivo per fermare il piano, ma è un fatto che contraddice la bozza. Guarda i primi persi, prova a spiegarli (per esempio: più di dieci riscontri davanti al bersaglio con due o tre lettere accentate), e scrivi spiegazione ed esempi nel report e una voce `tbd` in `next-steps.md` (Task 6).

Poi l'e2e intera: `(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)`.
Expected: tutti verdi, **cinque più del conto di partenza** (conta le prove sul ramo prima di questo task con `npx playwright test --list | tail -n 1` da `frontend/`, o leggilo nell'ultimo report della notte); annota il numero (`N_e2e`). Se una prova di un altro file fallisce perché cercava un suggerimento che ora è tagliato (uno sfumato che non contiene il testo), è un comportamento cambiato apposta: scrivi nel report quale prova, cosa cercava e perché ora non c'è, e segna il task `bloccato` con la domanda per Mattia — non si migra da soli una prova di un'altra consegna.

Se una prova fallisce e lascia dati nello stack, prima di rieseguire ricrea lo stack da zero (`down -v`, `up`, seme). Alla fine, sempre:

```bash
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
rm .env
```

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/suggerimenti.spec.ts frontend/e2e/style.spec.ts
git commit -m "e2e: i suggerimenti tagliati sul seme — zucch senza zucca, olio col tonno sott'olio, pollo a metà nome — e la nota di ripiego leggibile nei due temi"
```

---

### Task 6: I documenti

**Files:**
- Modify: `docs/prossimi-passi.md`
- Modify: `next-steps.md`

Leggi prima i due file com'è sul ramo.

- [ ] **Step 1: `docs/prossimi-passi.md`**

Nella voce T3, nell'«Esito del giro», in fondo al punto che comincia con `- **I suggerimenti sono rumorosi.**` (finisce con «Va sistemato lato server, con una soglia o un salto di punteggio.»), aggiungi, nello stesso punto elenco:

```markdown
  *(Fatto il <data di oggi>, sul ramo `night/suggerimenti-soglia`, non ancora in
  produzione — misura e decisioni in `docs/superpowers/specs/2026-10-06-suggerimenti-soglia-bozza.md`,
  piano `docs/superpowers/plans/2026-10-08-suggerimenti-soglia.md`. I suggerimenti di
  `/ingredients/search` mostrano chi contiene il testo all'inizio di una parola, nel nome o
  in un alias, senza accenti; gli altri solo se nessuno lo contiene, sopra
  max(0,30; 0,8 × il primo). Il taglio vale solo per l'endpoint: `match_name` e i vicini
  per l'AI restano sugli sfumati. `IngredientPicker` senza `onCreate` né `emptyNote` dice
  «Nessun ingrediente somiglia a «…». Prova con un'altra parola.». Sul seme
  (`python -m app.cli.measure_suggestions`): <le righe della famiglia «digitazione» —
  bersaglio in lista prima e dopo, righe in media prima e dopo, persi — e le due righe in
  media di «due lettere» e il bersaglio in lista dei «refusi», copiate dall'uscita del
  Task 5>. «Zucch» dà ancora Zucchero prima di Zucchina (decisione 5): se il giro dopo il
  taglio dice che sbaglia, lo spareggio diventa una voce sua.)*
```

Sostituisci `<data di oggi>` con la data vera e il segnaposto fra parentesi angolate con i numeri veri del Task 5.

- [ ] **Step 2: `next-steps.md`**

1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte: i suggerimenti tagliati, sul ramo night/suggerimenti-soglia)_`.
2. Togli la voce di questo piano (`grep -n "I suggerimenti degli ingredienti sono sempre dieci righe" next-steps.md`, ora `in corso`).
3. Togli l'idea chiusa dalla scelta 12: quella che comincia con `- [idea] P3 · \`search_ingredients\` non protegge il testo cercato nel \`LIKE\``.
4. In cima a «Fatti (recenti)» aggiungi:
   ```markdown
   - [fatto] <data di oggi> · I suggerimenti degli ingredienti non sono più sempre dieci righe: chi contiene il testo all'inizio di una parola, nel nome o in un alias e senza accenti, e gli sfumati solo se nessuno lo contiene, sopra max(0,30; 0,8 × il primo); il taglio solo nell'endpoint; la nota di ripiego in `IngredientPicker`; la misura sul seme con `python -m app.cli.measure_suggestions` (digitazione: righe in media da <prima> a <dopo>, <persi> bersagli persi) [T3, esito del giro] → branch night/suggerimenti-soglia (da revisionare)
   - [fatto] <data di oggi> · `search_ingredients` e i suggerimenti trattano `%` e `_` come lettere (`autoescape`) [bozza suggerimenti 2026-10-06] → branch night/suggerimenti-soglia (da revisionare)
   ```
5. In cima a «Da fare a mano (solo Mattia)» aggiungi:
   ```markdown
   - [tbd] P3 · Dopo il deploy dei suggerimenti tagliati: la misura sull'anagrafica vera, `docker compose -f docker-compose.prod.yml exec -T backend python -m app.cli.measure_suggestions` (sola lettura, qualche minuto; è una lettura della produzione), da confrontare col §6 della bozza; e al telefono, in Lista, «zucch», «olio», «pollo» e una parola con un refuso nelle prime lettere [T3, esito del giro]
   ```
6. Se nella misura del Task 5 la famiglia «digitazione» ha persi, in «Da approfondire (giorno)», sotto «Code della Consegna 2 e pulizie», aggiungi una voce `tbd` P3 con gli esempi e la spiegazione trovata.
7. Se nella notte sono emerse altre cose da fare fuori da questo piano, aggiungile come `idea` o `tbd` nella sezione giusta, con la voce di `docs/prossimi-passi.md` fra parentesi quadre.

Sostituisci ogni `<…>` con il valore vero.

- [ ] **Step 3: Commit**

```bash
git add docs/prossimi-passi.md next-steps.md
git commit -m "docs: i suggerimenti tagliati, fatti sul ramo; la misura sul seme, e quella sulla produzione per Mattia"
```

---

### Task 7: La verifica finale, e il report

Niente di nuovo da scrivere oltre al report: si prova tutto, dal worktree, com'è sul ramo.

- [ ] **Step 1: Il backend**

Da `<worktree>/backend`:

```bash
PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Expected: tutto verde, **`N_pytest` + 33** (18 del Task 1, 12 del Task 2, 3 del Task 3). Se il numero differisce, scrivi nel report da dove viene la differenza.

- [ ] **Step 2: Il frontend**

Da `<worktree>/frontend`:

```bash
npx vitest run
npm run typecheck
npx tsc -b --force
npm run lint
npm run build
```

Expected: vitest **`N_vitest` + 6** in `N_file` file, tutto verde; typecheck, lint e build puliti. `npx tsc -b --force` perché `node_modules` è condiviso col checkout principale, e con lui il `tsbuildinfo`: `--force` compila davvero tutto.

- [ ] **Step 3: I grep**

Dalla radice del worktree, i tre `grep` di «Comandi di verifica». Expected: come scritto lì. In più:

```bash
git diff master --stat -- backend/app/services frontend/src/features
```

Expected: vuoto — né i servizi del backend (`match_name`, `decide.py`) né le schermate del frontend sono cambiati; cambiano l'endpoint, il repository, il dominio, `IngredientPicker`. Unica eccezione ammessa: un file di test di un chiamante stretto secondo il «Margine di autonomia», già scritto nel report.

- [ ] **Step 4: L'e2e intera**

Con i comandi delle Global Constraints, su uno stack ricreato da zero (`down -v` prima dell'`up`, se ne era rimasto uno di questo ramo). Expected: tutti verdi, `N_e2e` del Task 5. Poi `down -v` e `rm .env`, sempre.

- [ ] **Step 5: Il report**

Nel report della notte, `docs/night-reports/<data di oggi>.md` sul ramo: se il file c'è già sul ramo aggiungi una sezione in fondo, altrimenti crealo con un titolo `# Notte del <data di oggi>` (gli altri piani della notte scrivono lo stesso file sui loro rami, che non partono da questo: l'unione la fa la revisione). Per questo piano: il ramo e da dove parte (`master`); i conti veri (vitest, pytest, e2e) contro quelli della Preparazione; **l'uscita intera di `measure_suggestions` sul seme** e il confronto con i numeri simulati del Task 5; le somiglianze dei test del Task 2 che Postgres ha dato diverse dal docstring, se ce ne sono; le migrazioni di test fatte (dovrebbero essere zero); le scelte del piano che Mattia può voler rivedere — il prefisso senza accenti nell'ordine (scelta 10), il testo della nota di ripiego (scelta 13), le liste di due lettere più lunghe di prima per la decisione 4, e l'idea «Un suggerimento non dice da quale alias arriva», che con la decisione 4 pesa un po' di più —; e il comando per la produzione di «Dopo il deploy». Niente push, niente merge, niente deploy.

```bash
git add docs/night-reports/
git commit -m "report: la notte dei suggerimenti tagliati"
```

---

## Dopo il deploy (solo Mattia)

Di notte non si fa niente di questo. Dopo il merge e il deploy (che restano di Mattia):

1. **La misura sull'anagrafica vera**, in sola lettura (il comando apre la transazione con `SET TRANSACTION READ ONLY` e finisce con un rollback; dura qualche minuto, perché fa due ricerche per prova e le prove sono qualche migliaio):
   ```bash
   docker compose -f docker-compose.prod.yml exec -T backend python -m app.cli.measure_suggestions
   ```
   Da confrontare col §6 della bozza, misurato sull'anagrafica «corretta» (276 ingredienti) quando la produzione ne aveva 884: digitazione con il bersaglio in lista al 99,9 % prima e dopo, righe in media da 6,7 a circa 2,2 (2,0 della bozza più l'effetto della decisione 4). Se la famiglia «digitazione» ha persi, sono il caso da guardare.
2. **Al telefono, in Lista:** «zucch» (niente zucca), «olio» (il tonno sì, le olive no), «pollo» (petto e coscia), e una parola con un refuso nelle prime lettere, che ora dà una lista vuota finché la parola non è finita — il prezzo dichiarato del pavimento.
