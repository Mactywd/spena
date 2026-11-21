# I suggerimenti tagliati, con l'elenco intero per «Abbina» e per l'Anagrafica: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** portare `night/suggerimenti-soglia` al pari di `master` con un `git merge master`, e poi dare a due chiamanti — «Abbina» in «Sistema la spesa» e la ricerca dell'Anagrafica — l'elenco dei suggerimenti **non tagliato**, mentre tutti gli altri tengono il taglio del piano del 2026-10-08.

**Architecture:** `GET /api/v1/ingredients/search` riceve un parametro `trim` (booleano, di default `true`). Con `trim=false` l'endpoint chiama la stessa `suggest_ingredients` con `trim=False`, che restituisce i candidati della stessa query (`_suggestion_candidates`, stesso filtro, stesso ordine, stesso `LIMIT`) senza passarli a `trim_suggestions`. Nel frontend `searchIngredients` impara l'opzione `{ trim: false }`, una funzione sola costruisce la chiave della cache (`ingredientSearchKey`), `IngredientPicker` e `IngredientChooser` ricevono una prop `trim` (default `true`), e solo `MatchPanel` e `RegistryScreen` chiedono l'elenco intero.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Postgres 16 con `pg_trgm`, pytest su Postgres vero; React 19, TanStack Query 5, Vitest + Testing Library, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-06-suggerimenti-soglia-bozza.md` (il taglio, §6–§10) e il piano che il ramo ha già costruito, `docs/superpowers/plans/2026-10-08-suggerimenti-soglia.md`. La domanda che questo piano chiude è nel report `docs/night-reports/2026-10-18.md` del ramo («Domande per Mattia prima del merge») e nel riepilogo `docs/night-reports/2026-10-18-riepilogo.md` («Domande per Mattia», 1). **Decisione di Mattia del 2026-11-18: strada (b)**, un elenco non tagliato per questi due chiamanti.

## Global Constraints

- **Dove si lavora.** Il worktree **esiste già**: `/home/mactyws/coding/ais/spena/.worktrees/suggerimenti-soglia`, ramo `night/suggerimenti-soglia` (10 commit sopra `e543ff9`, testa `0434cef` quando il piano è stato scritto, più il commit di questo piano). Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì (o dalle sue `backend/` e `frontend/`), mai dalla radice del checkout principale. Il checkout principale non si tocca: se vi trovi modifiche non committate, sono dell'utente. **Nessun push, nessun merge su `master`, nessun deploy. Mai `git stash`. Niente letture o scritture sulla produzione. Mai leggere il `.env` del checkout principale.**
- **Il ramo si porta al pari con `git merge master`, mai con un rebase**: il ramo esiste da un mese, con un report che cita i suoi hash. Un solo commit di merge (Task 1), poi i task.
- **Il taglio resta il default.** Senza `trim` nella richiesta, l'endpoint risponde esattamente come oggi sul ramo; tutti i chiamanti che non sono «Abbina» e l'Anagrafica non mandano il parametro e non cambiano. `match_name`, i vicini per l'AI e gli strumenti di Claude (`backend/app/services/claude/tools.py`, arrivato con la catena Pasti) restano su `search_ingredients`, che questo piano non tocca.
- **Le soglie si scrivono una volta sola** (`FUZZY_RELATIVE`, `FUZZY_FLOOR` in `backend/app/domain/suggestions.py`): questo piano non ne aggiunge e non le ricopia.
- **Prima lezione di `CLAUDE.md`: l'oggetto provato è quello che gira.** I test del backend passano dall'endpoint vero; quelli del frontend dal fetch che parte davvero (l'URL con o senza `trim=false`), non da una copia della chiave o dell'URL.
- **Mai un vicolo cieco.** «Abbina» tiene «Aggiungi «…»» (`createWhen="always"`); l'Anagrafica tiene «Nessun ingrediente con questo nome.»; gli altri cinque posti di `IngredientPicker` tengono la nota di ripiego del ramo.
- Tutto il colore passa dai token di `frontend/src/index.css`; **nessun token nuovo**, nessuna parola a video nuova. `grep -rn "emerald\|neutral-" frontend/src` dà solo il commento di `index.css` che c'è già.
- **Il type check è `npm run typecheck`** (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0 (settima lezione di `CLAUDE.md`). Più `npx tsc -b --force`, perché `node_modules` (e con lui il `tsbuildinfo`) è condiviso col checkout principale.
- Controlli del frontend, da `<worktree>/frontend`: `npx vitest run` (non esiste `npm test`), `npm run typecheck`, `npx tsc -b --force`, `npm run lint`, `npm run build`.
- **Backend su Postgres vero, sul database dei test di questo ramo, `spena_test_suggerimenti`**, ricreato vuoto nella Preparazione (dopo il merge il ramo ha le migrazioni di `master` fino alla `0022`; `conftest.py` le applica al primo pytest). Il container è `spena-db-1` (porta 5433), solo come database dei test: se `docker ps --format '{{.Names}}'` non lo mostra, `docker start spena-db-1`. **Mai `docker compose up` dal worktree**, mai `-f docker-compose.prod.yml`. Nel worktree non c'è un `.venv`: si usa quello del checkout principale, e `python -m` prova l'`app` del worktree. Il comando di pytest, sempre da `<worktree>/backend` (dove un task dice «il comando di pytest» intende questo, con i percorsi in coda):
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_suggerimenti \
    PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
  Se un test sembra ignorare una modifica, `python -c 'import app; print(app.__file__)'` da `<worktree>/backend` (con lo stesso `PATH`) deve stampare un percorso dentro il worktree. Nessuna chiamata di rete nella suite.
- **e2e** sullo stack `spena-e2e`, dalla radice di `<worktree>`. Serve un `.env`: **si copia da `.env.example`, che non ha segreti, solo per la prova, e si cancella alla fine.** Prima di alzarlo, `docker ps --format '{{.Names}}' | grep spena-e2e`: se c'è e non l'hai alzato tu (un'altra notte), non fare `down`, aspetta che sparisca. Dopo il seme si carica la tabella CIQUAL di prova (le due righe di S4: senza, 6 prove di S4 danno 409):
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
  Il `-p spena-e2e` e il `-f docker-compose.e2e.yml` vanno in ogni comando: un `down -v` sul progetto di default cancellerebbe la dispensa vera. Una prova fallita lascia dati nello stack: prima di rieseguire, `down -v`, poi `up`, seme, CIQUAL e prova.
- Nessuna dipendenza nuova, nessuna migrazione, nessun cambio di configurazione globale.

### Preparazione (una volta, prima del Task 1)

- [ ] Questo piano è committato sul ramo. Il giorno lo ha scritto nel worktree senza committarlo: se `git -C /home/mactyws/coding/ais/spena/.worktrees/suggerimenti-soglia status --short` mostra solo `?? docs/superpowers/plans/2026-11-18-suggerimenti-elenco-intero.md`, committalo:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/suggerimenti-soglia
  git add docs/superpowers/plans/2026-11-18-suggerimenti-elenco-intero.md
  git commit -m "docs: il piano dell'elenco intero per Abbina e l'Anagrafica"
  ```
- [ ] Il ramo e il worktree sono quelli attesi, puliti, e `master` è quello su cui il piano è scritto:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree list | grep suggerimenti-soglia
  git -C .worktrees/suggerimenti-soglia status --short
  ls .worktrees/suggerimenti-soglia/.env 2>&1 | grep -c "No such file"
  git rev-parse master
  git merge-tree --write-tree --name-only master night/suggerimenti-soglia | sed -n '2,10p'
  ```
  Expected: la riga del worktree su `[night/suggerimenti-soglia]`; `status` vuoto; `1` (nessun `.env` nel worktree); un hash (era `4537139` scrivendo il piano); dopo l'hash dell'albero, **tre** file in conflitto: `docs/night-reports/2026-10-18.md`, `frontend/e2e/style.spec.ts`, `next-steps.md`. Se i file in conflitto sono altri, `master` è andato avanti: risolvili con le stesse regole del Task 1 (si tiene il lavoro di tutti e due, `master` prima), e scrivilo nel report. Se lo `status` non è vuoto, **fermati**: sono modifiche di qualcun altro; scrivilo nel report e non partire.
- [ ] Nessuno ha già cominciato: `git -C .worktrees/suggerimenti-soglia log --oneline master..HEAD | grep -ci "merge"` stampa `0`, e `grep -c "trim: bool" .worktrees/suggerimenti-soglia/backend/app/api/ingredients.py` stampa `0`. Altrimenti **fermati** e scrivi nel report cosa hai trovato.
- [ ] Il database dei test di questo ramo, nuovo e vuoto (quello della notte del 2026-10-18 andava tolto; se c'è, si rifà):
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_suggerimenti WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_suggerimenti'
  ```
- [ ] Dal checkout principale (che è su `master`), allinea `node_modules` al lockfile; il worktree lo usa già con un collegamento (`ls -la <worktree>/frontend/node_modules` → una freccia verso `/home/mactyws/coding/ais/spena/frontend/node_modules`; se manca, `ln -s` come nel piano del 2026-10-08):
  ```bash
  cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund
  /home/mactyws/coding/ais/spena/backend/.venv/bin/python -c "import claude_agent_sdk"
  ```
  Expected: nessun errore. Il secondo prova che il `.venv` ha le dipendenze di `master` (la catena Pasti ha aggiunto `claude-agent-sdk`); se manca, `cd /home/mactyws/coding/ais/spena/backend && .venv/bin/pip install -e ".[dev]"` (README: installa solo quel che `pyproject.toml` di `master` già chiede).

---

## Obiettivo e contesto

Il ramo ha costruito il taglio dei suggerimenti: chi contiene il testo all'inizio di una parola, nel nome o in un alias; gli sfumati solo se nessuno lo contiene, sopra `max(0,30; 0,8 × il primo)`. La revisione finale della notte del 2026-10-18 ha trovato due chiamanti che vivevano dell'elenco lungo:

1. **«Abbina» in «Sistema la spesa»** (`MatchPanel`) precompila la ricerca con tutto il testo della voce. «pasta barilla integrale» non è contenuto da nessun nome, e contro «pasta» fa 0,250, sotto il pavimento: l'elenco resta vuoto accanto ad «Aggiungi «…»», e spinge a creare un doppione proprio nel flusso della spesa.
2. **La ricerca dell'Anagrafica** (`RegistryScreen`) nasconde i quasi-doppioni appena c'è un riscontro: cercando «zucchina» non si vede più una «zuchina» sbagliata (0,700), e quella schermata esiste per trovarli e unirli.

Mattia ha scelto (b): questi due ricevono l'elenco non tagliato, tutti gli altri tengono il taglio. Intanto `master` ha unito diciannove rami del 2026-10-18 (col rilascio del 2026-10-19) e la catena Pasti: il ramo va portato al pari prima di lavorare.

## Decisioni prese

1. **Strada (b)** (Mattia, 2026-11-18): un elenco non tagliato per «Sistema la spesa» e per il controllo dei quasi-doppioni dell'Anagrafica; il taglio resta per tutti gli altri.
2. **«Sistema la spesa» vuol dire «Abbina»** (`MatchPanel`), **confermato da Mattia il 2026-11-21**: è il solo posto della schermata che precompila la ricerca col testo della voce, cioè la causa del caso 1. «Articolo aggiuntivo» e «Di che ingrediente è?» di `ProductResolver` partono da un campo vuoto, dove si digita come in Lista, e `ProductResolver` (con `IngredientChooser`) lo usa anche la Dispensa: tengono il taglio. Se Mattia sceglie di dare l'elenco intero anche a loro, basta passare `trim={false}` ai loro `IngredientChooser`; il piano non lo fa.
3. **Un parametro della rotta, non un secondo endpoint** (Claude, su delega per le scelte tecniche). `GET /api/v1/ingredients/search?trim=false`, con `trim: bool = Query(default=True)`: senza parametro la risposta è quella di oggi, e nessun chiamante esistente cambia URL. Un secondo endpoint ricopierebbe `q`, `limit`, `kind` e i loro limiti, e sarebbe una seconda porta da tenere uguale alla prima; il parametro passa dalla stessa funzione, ed è quella che i test provano.
4. **L'elenco intero sono i candidati di `suggest_ingredients` senza `trim_suggestions`**, non `search_ingredients` (Claude, su delega). `suggest_ingredients(…, trim=False)` restituisce le righe di `_suggestion_candidates` così come arrivano: lo stesso filtro di `search_ingredients` (somiglianza ≥ 0,15 o prefisso) allargato ai riscontri, lo stesso `LIMIT`, e l'ordine del taglio (prefissi, poi riscontri, poi somiglianza). Ne viene una proprietà che un test fissa: **l'elenco tagliato è sempre l'inizio dell'elenco intero**, perché il taglio non riordina mai e i riscontri vengono prima di ogni sfumato. Rispetto alla lista di prima del 2026-10-18 cambia solo quel che il ramo ha già deciso per tutti (accenti, inizio di parola negli alias, `%` e `_` lettere). La scelta 7 del piano del 2026-10-08 («una query sorella, non un parametro» di `search_ingredients`) resta vera: il parametro sta in `suggest_ingredients`, dove sta il taglio, e `search_ingredients` non cambia.
5. **Una funzione sola per la chiave della cache**, `ingredientSearchKey(term, kind?, trim = true)` in `frontend/src/features/shopping-list/api.ts`, usata da `IngredientPicker` e da `RegistryScreen`. Oggi i due scrivono a mano la stessa chiave `["ingredients", term, "tutti"]` per condividere la risposta; con l'elenco intero, una chiave uguale farebbe vedere all'Anagrafica la lista tagliata di Lista (o il contrario) per la stessa parola. La chiave tagliata resta quella di oggi; quella intera ha un quarto elemento, `"intero"`.
6. **`trim` è una prop di `IngredientPicker` e di `IngredientChooser`, di default `true`.** Solo `MatchPanel` passa `trim={false}`. `RegistryScreen` non usa il selettore: chiama `searchIngredients` da sé, e lì passa `{ trim: false }`.
7. **`measure_suggestions` non cambia**: misura la lista tagliata (il default) contro `search_ingredients`, ed è ancora la misura giusta per tutti gli altri chiamanti.
8. **Il merge risolve i conflitti tenendo il lavoro di tutti e due**, `master` prima (Task 1): è la regola dei merge del 2026-10-19, dove le prove di `style.spec.ts` e le sezioni del report si sono messe in fila.

## Criteri di accettazione

- [ ] Il ramo contiene `master` (`git merge-base --is-ancestor master HEAD` esce 0), con un solo commit di merge e nessun marcatore di conflitto (`git grep -n '^<<<<<<<\|^>>>>>>>' -- . ':!*.lock'` vuoto).
- [ ] Dopo il merge e prima del Task 2, pytest, vitest, typecheck, lint, build e l'e2e intera sono verdi.
- [ ] `GET /ingredients/search?q=zucchina` con «zucchina» e «zuchina» dà `["zucchina"]`; con `trim=false` dà `["zucchina", "zuchina"]`.
- [ ] `?q=pasta barilla integrale` con «pasta» dà `[]`; con `trim=false` il primo è «pasta».
- [ ] Per ogni testo provato, l'elenco tagliato è l'inizio di quello intero; `trim=false` rispetta `limit` e `kind`; `trim=boh` è un 422.
- [ ] «Abbina» e l'Anagrafica chiedono `trim=false`; nessun altro chiamante manda `trim`; la stessa parola cercata in un selettore che taglia e in uno intero dà due richieste e due risposte.
- [ ] Nel browser, sul seme: «Abbina» di «pasta barilla integrale» suggerisce «Pasta»; l'Anagrafica con «zucchina» mostra anche «Zucca» e «Zucchero»; in Lista «zucch» continua a non suggerire la Zucca.
- [ ] Nessun test di oggi cambiato; vitest, typecheck, lint, build, pytest e l'e2e intera verdi.
- [ ] `docs/prossimi-passi.md`, la bozza della spec (§10), `next-steps.md` e il report della notte aggiornati (Task 5).

## Comandi di verifica

Da `<worktree>/backend`: il comando di pytest intero.

Da `<worktree>/frontend`:

```bash
npx vitest run
npm run typecheck
npx tsc -b --force
npm run lint
npm run build
```

Dalla radice di `<worktree>`:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -rln "trim: false\|trim={false}" frontend/src --include=*.tsx --include=*.ts | grep -v "\.test\."
grep -rln "search_ingredients(" backend/app
git diff master --name-only -- backend/alembic
```

Expected: il primo solo il commento di `frontend/src/index.css` che c'è già; il secondo **due** file, `frontend/src/features/stocking/MatchPanel.tsx` e `frontend/src/features/registry/RegistryScreen.tsx` (i commenti dicono «l'elenco intero», non ricopiano `trim={false}`); il terzo `cli/measure_suggestions.py`, `repositories/ingredients.py`, `services/claude/tools.py`, `services/ingredient_match.py`, `services/recipe_import/decide.py` (e **non** `api/ingredients.py`); l'ultimo vuoto. Poi l'e2e intera con i comandi delle Global Constraints.

## Review Focus

I casi più probabili che nessun test di oggi tiene fermi, ognuno fissato da un test nel task che possiede il codice:

1. **La stessa parola in due chiamanti diversi nella stessa sessione** (si cerca «zucchina» in Lista, poi in Anagrafica): con una chiave della cache condivisa, l'Anagrafica mostrerebbe la lista tagliata, e il caso 2 tornerebbe senza che nessuno se ne accorga — Task 3 (`con trim={false} chiede l'elenco intero, e non divide la cache con chi taglia`).
2. **Un chiamante che non dice niente** (Lista, Dispensa, «Articolo aggiuntivo», modulo della ricetta, filtri, coda, fondi, sostituti): deve restare tagliato e non mandare `trim` — Task 2 (`test_l_elenco_tagliato_e_l_inizio_di_quello_intero` col default), Task 3 (`IngredientChooser` senza prop).
3. **La voce lunga in «Abbina»** («pasta barilla integrale»): il caso 1, dall'endpoint fino al browser — Task 2 (`test_l_elenco_intero_trova_l_ingrediente_nel_testo_lungo_della_voce`), Task 4.
4. **`limit` e `kind` con l'elenco intero**: senza taglio nulla accorcia la lista, quindi il `LIMIT` della query è l'unico freno, e una ricetta non deve vedere un non alimentare — Task 2 (`test_l_elenco_intero_tiene_il_limite_e_il_kind`).
5. **Le prove di `master` scritte contro la lista di prima** (diciannove rami e la catena Pasti non hanno mai girato col taglio: sostituti, pasti, Claude, ingresso diretto): un e2e che digita un testo che il taglio ora nasconde — Task 1, l'e2e intera subito dopo il merge, prima di ogni modifica.

## Fuori scope

- Le strade (a) e (c), e ogni regola nuova del taglio (soglie, riscontro «inverso»).
- L'elenco intero per «Articolo aggiuntivo», per `ProductResolver`, per il + della Dispensa, per «Fondi» (`MergePanel`) o per qualunque altro chiamante (decisione 2).
- Togliere la prop `emptyNote` di `IngredientPicker`, che dopo S3 non ha chiamanti (resta l'idea in `next-steps.md`).
- Le code della revisione del 2026-10-18 (l'idea «Code dei suggerimenti tagliati»): famiglie nuove di `measure_suggestions`, NFC, spazi doppi.
- `search_ingredients`, `match_name`, i vicini per l'AI e gli strumenti di Claude.
- La misura sulla produzione: è di Mattia, dopo il deploy.

## Margine di autonomia

- **Liberi:** i nomi di variabili locali e helper di test non fissati qui; l'ordine dei test in un file; i docstring e i commenti, purché dicano il perché.
- **Fissi:** il nome e il default del parametro (`trim`, `true`); la firma di `suggest_ingredients`; `ingredientSearchKey` e la forma delle due chiavi; la prop `trim` di `IngredientPicker` e `IngredientChooser`; quali due chiamanti passano `false`.
- **Le somiglianze nei docstring** dei test nuovi (0,250 per «pasta barilla integrale», 0,700 per «zuchina», 0,364 per «zucca», 0,385 per «zucchero») vengono dalle misure del 2026-10-18 o sono calcolate a mano: misurale su Postgres (`SELECT similarity('zucchina', 'zucca')` sul database dei test) e correggi il docstring se differiscono. Le asserzioni non dipendono dai decimali, solo dall'essere sopra 0,15 e sotto 0,30.
- **Conflitti del merge diversi da quelli previsti**: si risolvono tenendo il lavoro di tutti e due, `master` prima; se un conflitto chiede di scegliere fra due comportamenti, si tiene `master` e lo si scrive nel report.
- **Un test di `master` che dopo il merge cade per colpa del taglio** (Task 1, passo 5): prima la diagnosi, con l'output. Se la prova cerca un ingrediente per un altro scopo (un'impostazione, non i suggerimenti) e digitava un testo che ora non è un riscontro, si può cambiare **il testo digitato** in uno che lo è (il nome intero, o il suo inizio), mai l'asserzione; si scrive nel report quale prova, quale testo prima e dopo, e perché. Se invece la prova difende un comportamento che il taglio cambia per chi usa l'app (una lista che deve mostrare uno sfumato), **non si tocca**: si segna la voce `bloccato` in `next-steps.md` del ramo con la domanda per Mattia, si fa commit del merge comunque, e si continua coi task 2–4 (il resto del piano non dipende da quella prova).
- **Un test di oggi si cambia solo dove il piano lo dice** (cioè mai, salvo il caso qui sopra). Niente test disattivati, niente asserzioni indebolite.
- **Una decisione di comportamento non coperta e non reversibile** → si ferma quel task, commit del lavoro parziale, voce `bloccato` con la domanda, task successivo. Una scelta reversibile e a basso impatto → la più conservativa, annotata nel report.

## File toccati

| File | Task | Cosa |
|---|---|---|
| `docs/night-reports/2026-10-18.md`, `frontend/e2e/style.spec.ts`, `next-steps.md` | 1 | conflitti del merge |
| `backend/app/repositories/ingredients.py`, `backend/app/api/ingredients.py`, `backend/tests/api/test_ingredients.py` | 2 | `trim` |
| `frontend/src/features/shopping-list/api.ts`, `frontend/src/components/IngredientPicker.tsx` (+ test), `frontend/src/features/stocking/IngredientChooser.tsx` (+ test), `frontend/src/features/stocking/MatchPanel.tsx` (+ test), `frontend/src/features/registry/RegistryScreen.tsx` (+ test) | 3 | chi chiede l'elenco intero |
| `frontend/e2e/suggerimenti.spec.ts` | 4 | nel browser |
| `docs/prossimi-passi.md`, `docs/superpowers/specs/2026-10-06-suggerimenti-soglia-bozza.md`, `next-steps.md`, `docs/night-reports/<data di oggi>.md` | 5 | documenti e report |

---

### Task 1: Il ramo al pari di `master`

**Files:**
- Modify (conflitti): `docs/night-reports/2026-10-18.md`, `frontend/e2e/style.spec.ts`, `next-steps.md`
- Controlla (uniti da soli): `backend/app/api/ingredients.py`, `frontend/src/components/IngredientPicker.tsx`, `frontend/src/components/IngredientPicker.test.tsx`, `docs/prossimi-passi.md`

**Interfaces:**
- Produces: un ramo che contiene `master`; i numeri `N_file`, `N_vitest`, `N_pytest`, `N_e2e` dopo il merge, che il Task 5 usa come partenza.

Nel worktree, dopo `git merge master`, `HEAD` è il ramo e `MERGE_HEAD` è `master`. Il ramo, su questi tre file, ha solo **aggiunto** (una sezione del report, una prova in fondo a `style.spec.ts`, poche righe di `next-steps.md`): per i primi due la risoluzione è la versione di `master` più l'aggiunta del ramo.

- [ ] **Step 1: Il merge**

```bash
cd /home/mactyws/coding/ais/spena/.worktrees/suggerimenti-soglia
git merge master --no-ff --no-commit
git diff --name-only --diff-filter=U
```

Expected: il merge si ferma sui conflitti; i tre file della Preparazione.

- [ ] **Step 2: Il report del 2026-10-18 (add/add)**

Su `master` il file è il report di diciotto rami (`# Report 2026-10-18 — fase notte`, 18 sezioni `## `); sul ramo è un file suo (`# Notte del 2026-10-18`) con una sezione sola, `## I suggerimenti tagliati (`suggerimenti-soglia`)`. Si tiene quello di `master` e in fondo la sezione del ramo, senza il suo titolo `#`:

```bash
git show MERGE_HEAD:docs/night-reports/2026-10-18.md > docs/night-reports/2026-10-18.md
printf '\n' >> docs/night-reports/2026-10-18.md
git show HEAD:docs/night-reports/2026-10-18.md | sed -n '/^## I suggerimenti tagliati/,$p' >> docs/night-reports/2026-10-18.md
grep -c '^## ' docs/night-reports/2026-10-18.md
grep -c '^# ' docs/night-reports/2026-10-18.md
```

Expected: `19` e `1`.

- [ ] **Step 3: `frontend/e2e/style.spec.ts`**

Un conflitto solo, in fondo al file: `master` ha aggiunto le prove dei suoi rami (da «S3: l'ingresso diretto in dispensa» in giù), il ramo una prova, «la nota di ripiego dei suggerimenti si legge nei due temi». Si tengono tutte, quelle di `master` prima:

```bash
git show MERGE_HEAD:frontend/e2e/style.spec.ts > frontend/e2e/style.spec.ts
printf '\n' >> frontend/e2e/style.spec.ts
git show HEAD:frontend/e2e/style.spec.ts | sed -n '/^test("la nota di ripiego dei suggerimenti si legge nei due temi"/,$p' >> frontend/e2e/style.spec.ts
git diff MERGE_HEAD --stat -- frontend/e2e/style.spec.ts
grep -n "^async function fermo\|^async function testiIlleggibili" frontend/e2e/style.spec.ts
```

Expected: `1 file changed, 16 insertions(+)` (la riga vuota e le quindici della prova); le due funzioni che la prova del ramo usa esistono ancora su `master`.

- [ ] **Step 4: `next-steps.md`, a mano**

Tre conflitti, da risolvere con un editor (nessuna riga riscritta, solo scelte):
1. **La riga «_Ultimo aggiornamento_»** in testa: si tiene quella di `master` (la data la aggiorna il Task 5).
2. **L'elenco di «Pronti per la notte»**: da una parte la voce `[pronto]` dei suggerimenti (`master`), dall'altra i diciannove piani del 2026-10-18 (il ramo, com'era un mese fa). Si tiene il lato di `master`: quei piani sono già uniti e fuori dall'elenco.
3. **Le `[tbd]` di «Da approfondire (giorno)»**: da una parte R6, il passaggio dell'LLM ad Anthropic e gli avvisi di `docker compose` (`master`), dall'altra P1, P2 e la `[tbd] P2 · Da decidere PRIMA di fare il merge di night/suggerimenti-soglia…` (il ramo). Si tiene il lato di `master`: P1 e P2 `master` li ha già tolti, e la `[tbd]` del merge è decisa (Mattia, 2026-11-18) e la chiude questo piano.

Poi le righe che il ramo ha aggiunto fuori dai conflitti restano dove git le ha messe (il Task 5 le sistema): l'idea «Code dei suggerimenti tagliati», la `[tbd]` «Dopo il deploy dei suggerimenti tagliati» in «Da fare a mano», le due `[fatto] 2026-10-18` dei suggerimenti in «Fatti (recenti)».

```bash
grep -c '^<<<<<<<\|^=======\|^>>>>>>>' next-steps.md
grep -c "Da decidere PRIMA di fare il merge" next-steps.md
grep -c "non protegge il testo cercato nel" next-steps.md
grep -c "Code dei suggerimenti tagliati" next-steps.md
```

Expected: `0`, `0`, `0` (l'idea dei jolly l'ha già tolta il ramo, e il merge la toglie anche da `master`), `1`.

- [ ] **Step 5: Quel che git ha unito da solo**

```bash
grep -n "suggest_ingredients(session, q, limit, kind=kind)\|@router.get(\"/match\"" backend/app/api/ingredients.py
grep -n "readOnly={disabled}\|Nessun ingrediente somiglia a" frontend/src/components/IngredientPicker.tsx
git grep -n '^<<<<<<<\|^>>>>>>>' -- . ':!*.lock'
```

Expected: la rotta `/search` chiama `suggest_ingredients` e la rotta `/match` di `master` c'è; in `IngredientPicker` ci sono sia il campo `readOnly` di `master` sia la nota di ripiego del ramo; nessun marcatore in tutto il repo.

- [ ] **Step 6: Il commit del merge**

```bash
git add docs/night-reports/2026-10-18.md frontend/e2e/style.spec.ts next-steps.md
git commit -m "merge: master nel ramo dei suggerimenti tagliati (il rilascio del 2026-10-19 e la catena Pasti)"
git merge-base --is-ancestor master HEAD && echo "al pari"
```

Expected: `al pari`.

- [ ] **Step 7: La voce in corso**

Cerca la voce di questo piano: `grep -n "2026-11-18-suggerimenti-elenco-intero" next-steps.md`; se non c'è (il giorno non l'ha ancora riscritta), quella che comincia con `4. [pronto] P3 · I suggerimenti degli ingredienti sono sempre dieci righe`. Cambia solo lo stato fra parentesi quadre in `in corso`.

```bash
git add next-steps.md
git commit -m "next-steps: l'elenco intero per Abbina e l'Anagrafica, in corso"
```

- [ ] **Step 8: Le prove intere sul ramo unito, prima di ogni modifica**

Il comando di pytest intero; da `<worktree>/frontend` i cinque controlli; l'e2e intera con i comandi delle Global Constraints, su uno stack ricreato da zero.

Expected: tutto verde. Come riferimento (non come soglia): l'ultimo report di `master` (`docs/night-reports/2026-11-13.md`) dava pytest 2068, vitest 129 file / 1599 test, e2e 126; il ramo aggiunge 33 test di pytest, 6 di vitest nei file che ci sono, 5 prove e2e e un file e2e. **Annota i numeri veri**: `N_pytest`, `N_file`, `N_vitest`, `N_e2e`. Se qualcosa non è verde, vedi «Margine di autonomia» (un test di `master` contro il taglio); un difetto che non viene dal taglio va nel report con la diagnosi, e non si corregge qui.

---

### Task 2: `trim` nell'endpoint e in `suggest_ingredients`

**Files:**
- Modify: `backend/app/repositories/ingredients.py` (`suggest_ingredients`)
- Modify: `backend/app/api/ingredients.py` (la rotta `search`)
- Test: `backend/tests/api/test_ingredients.py` (in fondo, dopo i test dei suggerimenti tagliati; usa gli helper `_ingredienti` e `_suggeriti` che ci sono)

**Interfaces:**
- Consumes: `_suggestion_candidates(session, query, limit, kind) -> list[ScoredIngredient]` e `trim_suggestions(candidates, limit)`, del ramo.
- Produces: `async def suggest_ingredients(session: AsyncSession, query: str, limit: int = 10, kind: IngredientKind | None = None, *, trim: bool = True) -> list[Ingredient]`; `GET /api/v1/ingredients/search?q=…&limit=…&kind=…&trim=false`, con `trim` di default `true`.

- [ ] **Step 1: I test che falliscono**

```python
async def test_l_elenco_intero_mostra_il_quasi_doppione_accanto_al_riscontro(logged_client, db_session):
    """Il caso 2 della revisione del 2026-10-18, deciso da Mattia il 2026-11-18 (strada b):
    l'Anagrafica chiede l'elenco intero, perché esiste per trovare i doppioni. «zuchina»
    (0,700) non contiene «zucchina»: il taglio la toglie, l'elenco intero no."""
    await _ingredienti(db_session, "zucchina", "zuchina")

    assert await _suggeriti(logged_client, "zucchina") == ["zucchina"]
    assert await _suggeriti(logged_client, "zucchina", trim="false") == ["zucchina", "zuchina"]


async def test_l_elenco_intero_trova_l_ingrediente_nel_testo_lungo_della_voce(logged_client, db_session):
    """Il caso 1: «Abbina» precompila il testo della voce. Nessun nome contiene «pasta
    barilla integrale», e pasta somiglia 0,250, sotto il pavimento: tagliato è vuoto,
    intero la pasta viene prima."""
    await _ingredienti(db_session, "pasta", "pane")

    assert await _suggeriti(logged_client, "pasta barilla integrale") == []
    intero = await _suggeriti(logged_client, "pasta barilla integrale", trim="false")
    assert intero[0] == "pasta"


async def test_l_elenco_tagliato_e_l_inizio_di_quello_intero(logged_client, db_session):
    """Decisione 4 del piano: il taglio non riordina, e i riscontri vengono prima di ogni
    sfumato, quindi la lista tagliata è sempre la testa di quella intera. Senza `trim` è
    la tagliata (il default che tutti gli altri chiamanti usano)."""
    await _ingredienti(
        db_session, "zucchero", "zucchina", "zucca", "olio di oliva",
        ("tonno in scatola", "tonno sott'olio"), "olive verdi", "pomodoro", "pomodorini",
        "pomodori secchi", "caffè", "caffelatte", "pasta",
    )

    for testo in ["zucch", "olio", "pomodorr", "caffe", "te", "zenzero", "pasta barilla integrale"]:
        tagliato = await _suggeriti(logged_client, testo)
        assert await _suggeriti(logged_client, testo, trim="true") == tagliato, testo
        intero = await _suggeriti(logged_client, testo, trim="false")
        assert intero[: len(tagliato)] == tagliato, testo
        assert len(intero) >= len(tagliato), testo


async def test_l_elenco_intero_tiene_il_limite_e_il_kind(logged_client, db_session):
    """Senza taglio il `LIMIT` della query è il solo freno, e il filtro del cibo vale
    come sempre: una ricetta non nomina un non alimentare (decisione 2 di CLAUDE.md)."""
    from app.repositories.ingredients import create_ingredient

    await _ingredienti(db_session, *[f"pollame {i:02}" for i in range(1, 13)])
    await create_ingredient(db_session, "candeggina", "Candeggina", "casa")
    await create_ingredient(db_session, "canditi", "Canditi", "dolci")
    await db_session.commit()

    assert len(await _suggeriti(logged_client, "pollo", trim="false")) == 10
    assert len(await _suggeriti(logged_client, "pollo", trim="false", limit="3")) == 3
    cibo = await _suggeriti(logged_client, "cand", trim="false", kind="food")
    assert "canditi" in cibo and "candeggina" not in cibo


async def test_trim_che_non_e_un_booleano_e_un_422(logged_client):
    risposta = await logged_client.get("/api/v1/ingredients/search", params={"q": "zucch", "trim": "boh"})
    assert risposta.status_code == 422
```

- [ ] **Step 2: Falliscono**

Il comando di pytest con `tests/api/test_ingredients.py -k "elenco_intero or elenco_tagliato or trim_che"`. Expected: FAIL dove si manda `trim=false` (l'elenco è tagliato: il parametro sconosciuto è ignorato) e sul 422 (risponde 200).

- [ ] **Step 3: Il codice**

In `suggest_ingredients` il parametro `*, trim: bool = True`: con `True` com'è oggi; con `False` restituisce `[candidate.ingredient for candidate in candidates]`, senza `trim_suggestions`. Il docstring dice chi lo chiede (`trim=False`: «Abbina» e l'Anagrafica, decisi da Mattia il 2026-11-18) e la proprietà della decisione 4. Nella rotta `search` di `api/ingredients.py` il parametro `trim: bool = Query(default=True)`, passato a `suggest_ingredients(session, q, limit, kind=kind, trim=trim)`, e il commento sopra la chiamata dice in una riga che `trim=false` è l'elenco intero dei due chiamanti, con la data.

- [ ] **Step 4: Passano, e passa tutto**

Lo stesso comando, poi il comando di pytest intero. Expected: 5 nuovi verdi; intero **`N_pytest` + 5**.

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/ingredients.py backend/app/api/ingredients.py backend/tests/api/test_ingredients.py
git commit -m "suggerimenti: trim=false dà l'elenco intero, per Abbina e l'Anagrafica; il default resta il taglio"
```

---

### Task 3: «Abbina» e l'Anagrafica chiedono l'elenco intero

**Files:**
- Modify: `frontend/src/features/shopping-list/api.ts` (`searchIngredients`, nuova `ingredientSearchKey`)
- Modify: `frontend/src/components/IngredientPicker.tsx`, `frontend/src/features/stocking/IngredientChooser.tsx`, `frontend/src/features/stocking/MatchPanel.tsx`, `frontend/src/features/registry/RegistryScreen.tsx`
- Test: `frontend/src/components/IngredientPicker.test.tsx`, `frontend/src/features/stocking/IngredientChooser.test.tsx`, `frontend/src/features/stocking/MatchPanel.test.tsx`, `frontend/src/features/registry/RegistryScreen.test.tsx` (ognuno con lo `stubRoutedFetch` che il file ha già)

**Interfaces:**
- Consumes: `GET /ingredients/search?…&trim=false` (Task 2).
- Produces:
  - `export function searchIngredients(query: string, kind?: "food", { trim = true }: { trim?: boolean } = {}): Promise<Ingredient[]>` — con `trim` falso aggiunge `trim=false` ai parametri; altrimenti l'URL è quello di oggi, senza `trim`.
  - `export function ingredientSearchKey(term: string, kind?: "food", trim = true)` — `["ingredients", term, kind ?? "tutti"]` col taglio, `["ingredients", term, kind ?? "tutti", "intero"]` senza.
  - `IngredientPicker` e `IngredientChooser`: prop `trim?: boolean`, default `true`; `IngredientChooser` la passa al suo `IngredientPicker`.

Per leggere i parametri di un URL nei test: `new URL(String(url), "http://localhost").searchParams.get("trim")`.

- [ ] **Step 1: I test che falliscono**

In `IngredientPicker.test.tsx`, `it("con trim={false} chiede l'elenco intero, e non divide la cache con chi taglia")`: il fetch risponde `[LATTE, LATTUGA]` quando l'URL ha `trim=false` e `[LATTE]` altrimenti (`LATTUGA` è un `Ingredient` nuovo del file); nello stesso client due selettori, «Taglia» senza prop e «Intero» con `trim={false}`; si cerca «latt» nel primo e si aspetta la sua opzione «Latte», poi si cerca «latt» nel secondo. Asserzioni: dentro il secondo selettore compare l'opzione «Lattuga», dentro il primo no; le chiamate a `/ingredients/search` sono due, una con `trim` uguale a `"false"` e una con `trim` `null`.

In `IngredientChooser.test.tsx`, `it("cerca col taglio, salvo trim={false}")`: montato senza la prop, la chiamata a `/ingredients/search` ha `trim` `null`; montato (in un altro `render`) con `trim={false}`, ha `trim` uguale a `"false"`.

In `MatchPanel.test.tsx`, `it("cerca il testo della voce nell'elenco intero")`: col `renderPanel()` del file, dopo `findByRole("option", { name: "Pera" })`, la chiamata a `/ingredients/search` ha `q` uguale a `"cera per pavimenti"` e `trim` uguale a `"false"`.

In `RegistryScreen.test.tsx`, `it("chiede l'elenco intero: l'Anagrafica serve a trovare i quasi-doppioni")`: si scrive «zucchina» nel campo; la chiamata a `/ingredients/search` ha `trim` uguale a `"false"` e nessun `kind`.

- [ ] **Step 2: Falliscono**

```bash
npx vitest run src/components/IngredientPicker.test.tsx src/features/stocking/IngredientChooser.test.tsx src/features/stocking/MatchPanel.test.tsx src/features/registry/RegistryScreen.test.tsx
```

Expected: FAIL nei quattro test nuovi (`trim` è sempre `null`; in `IngredientPicker` il secondo selettore legge la risposta del primo, o la prop non esiste per il typecheck di vitest), tutti gli altri verdi.

- [ ] **Step 3: Il codice**

- `api.ts`: `ingredientSearchKey` e l'opzione di `searchIngredients` come nelle Interfaces; il commento di `searchIngredients` dice che `trim=false` è l'elenco intero chiesto solo da «Abbina» e dall'Anagrafica (Mattia, 2026-11-18).
- `IngredientPicker.tsx`: prop `trim = true`, con il suo commento JSDoc accanto alle altre (chi la spegne e perché); `queryKey: ingredientSearchKey(debounced, kind, trim)`, `queryFn: () => searchIngredients(debounced, kind, { trim })`. Il commento che spiega perché il `kind` sta nella chiave resta, e vale ora per tutti e due.
- `IngredientChooser.tsx`: prop `trim?: boolean` passata a `IngredientPicker`; il commento in testa nomina che «Abbina» la spegne.
- `MatchPanel.tsx`: `trim={false}` sul suo `IngredientChooser`, con un commento di una riga: il campo nasce col testo intero della voce, che col taglio non trova quasi mai l'ingrediente (strada b, Mattia, 2026-11-18).
- `RegistryScreen.tsx`: `queryKey: ingredientSearchKey(debounced, undefined, false)`, `queryFn: () => searchIngredients(debounced, undefined, { trim: false })`; il commento sopra, che oggi dice «le stesse chiavi di IngredientPicker», si riscrive: la chiave viene da `ingredientSearchKey`, ed è quella intera, la stessa di «Abbina».

- [ ] **Step 4: Passano, e passa tutto**

Lo stesso comando, poi da `<worktree>/frontend` i cinque controlli. Expected: verdi; vitest **`N_vitest` + 4** in `N_file` file.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/shopping-list/api.ts frontend/src/components/IngredientPicker.tsx frontend/src/components/IngredientPicker.test.tsx frontend/src/features/stocking/IngredientChooser.tsx frontend/src/features/stocking/IngredientChooser.test.tsx frontend/src/features/stocking/MatchPanel.tsx frontend/src/features/stocking/MatchPanel.test.tsx frontend/src/features/registry/RegistryScreen.tsx frontend/src/features/registry/RegistryScreen.test.tsx
git commit -m "Abbina e l'Anagrafica chiedono l'elenco intero dei suggerimenti, con la loro chiave della cache"
```

---

### Task 4: Nel browser vero

**Files:**
- Modify: `frontend/e2e/suggerimenti.spec.ts` (due prove in fondo)

**Interfaces:**
- Consumes: i Task 2 e 3; il seme ha `pasta` (alias spaghetti, penne…), `pasta sfoglia`, `zucchina`, `zucca`, `zucchero`, `zucchero a velo` (`data/ingredients_seed.json`).

- [ ] **Step 1: Le prove**

1. **««Abbina» di una voce lunga suggerisce l'ingrediente: l'elenco intero»**. Copia lo schema della prova «Sistema la spesa a 375px» di `frontend/e2e/style.spec.ts` (l'attesa del link «Dispensa» prima della prima `page.request`; la voce creata con `POST /api/v1/shopping-list` e `ingredient_id: null`, status 201; spuntata con `PATCH … {status: "checked"}`; la pulizia in un `finally` che la archivia con `expect.soft`). La voce è «pasta barilla integrale»; su `/sistema` si tocca il pulsante `Abbina: pasta barilla integrale`; il campo `Abbina un ingrediente per pasta barilla integrale` ha quel testo; l'opzione `{ name: "Pasta", exact: true }` è visibile, e accanto c'è ancora `Aggiungi «pasta barilla integrale»`. Non si sceglie niente: la voce si archivia e basta.
2. **«l'Anagrafica con «zucchina» mostra anche i vicini, la Lista no»**. Su `/anagrafica` si scrive «zucchina» in `Cerca un ingrediente o un prodotto`: sotto «Ingredienti» ci sono i link `/^Zucchina\b/`, `/^Zucca\b/` e `/^Zucchero\b/` (quest'ultimo con `.first()`: anche «Zucchero a velo» comincia così; somiglianze circa 0,364 e 0,385, misurale come dice il Margine). Poi, con `suggerimentiInLista(page, "zucchina")` del file, l'elenco di Lista ha l'opzione `/^Zucchina\b/` e **non** `/^Zucca\b/`: lo stesso testo, nella stessa sessione, resta tagliato per chi non chiede l'elenco intero (Review Focus 1).

- [ ] **Step 2: L'e2e intera**

Con i comandi delle Global Constraints, su uno stack ricreato da zero. Expected: tutto verde, **`N_e2e` + 2**. Poi `down -v` e `rm .env`, sempre.

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/suggerimenti.spec.ts
git commit -m "e2e: Abbina trova la pasta nella voce lunga, l'Anagrafica mostra i vicini di zucchina e la Lista no"
```

---

### Task 5: I documenti, la verifica finale e il report

**Files:**
- Modify: `docs/prossimi-passi.md`, `docs/superpowers/specs/2026-10-06-suggerimenti-soglia-bozza.md`, `next-steps.md`
- Create o modify: `docs/night-reports/<data di oggi>.md`

Leggi i file com'è sul ramo prima di cambiarli. `<data di oggi>` è la data vera della notte.

- [ ] **Step 1: La bozza della spec.** In fondo al §10 («Decisioni per Mattia»), dopo la decisione 6, aggiungi:

```markdown
7. **Chi riceve l'elenco non tagliato** (dalla revisione finale del ramo, 2026-10-18).
   «Abbina» in «Sistema la spesa» precompila la ricerca col testo intero della voce, e la
   ricerca dell'Anagrafica serve a trovare i quasi-doppioni: col taglio restano senza le
   righe che servono. (a) un riscontro anche per il testo che contiene un nome intero;
   (b) l'elenco non tagliato per questi due chiamanti; (c) accettare. **Deciso da Mattia il
   2026-11-18: (b)**, con `trim=false` su `/ingredients/search`; tutti gli altri tengono il
   taglio. Piano `docs/superpowers/plans/2026-11-18-suggerimenti-elenco-intero.md`.
```

- [ ] **Step 2: `docs/prossimi-passi.md`.** Nella nota in corsivo che comincia con «*(Fatto il 2026-10-18, sul ramo `night/suggerimenti-soglia`», prima della parentesi che chiude, aggiungi la frase: «Il 2026-11-18 Mattia ha deciso che «Abbina» in «Sistema la spesa» e la ricerca dell'Anagrafica ricevono l'elenco non tagliato (`trim=false`), perché vivono delle righe sfumate: il testo intero della voce, i quasi-doppioni; piano `docs/superpowers/plans/2026-11-18-suggerimenti-elenco-intero.md`.»

- [ ] **Step 3: `next-steps.md`.**
1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte: i suggerimenti tagliati al pari di master, con l'elenco intero per Abbina e l'Anagrafica, sul ramo night/suggerimenti-soglia)_`.
2. Togli la voce di questo piano (quella `in corso` del Task 1). Se «Pronti per la notte» resta senza voci, il paragrafo che comincia con «Resta solo il 4, `suggerimenti-soglia`» diventa `_(niente)_`; se ci sono altre voci, togli solo le frasi su `suggerimenti-soglia`.
3. Togli le due `[fatto] 2026-10-18` dei suggerimenti (in «Fatti (recenti)», dove le ha messe il merge) e in cima a «Fatti (recenti)» aggiungi:
   ```markdown
   - [fatto] <data di oggi> · I suggerimenti degli ingredienti non sono più sempre dieci righe: chi contiene il testo all'inizio di una parola, nel nome o in un alias e senza accenti, e gli sfumati solo se nessuno lo contiene, sopra max(0,30; 0,8 × il primo); `%` e `_` lettere; la nota di ripiego in `IngredientPicker`; «Abbina» e l'Anagrafica ricevono l'elenco intero (`trim=false`, Mattia, 2026-11-18); il ramo è al pari di `master` [T3, esito del giro] → branch night/suggerimenti-soglia (da revisionare)
   ```
4. Nella `[tbd]` «Dopo il deploy dei suggerimenti tagliati» di «Da fare a mano», prima della parentesi quadra finale, aggiungi: «; in «Sistema la spesa», «Abbina» di una voce lunga («pasta barilla integrale») suggerisce l'ingrediente; in Anagrafica, cercando un nome si vedono anche i suoi quasi-doppioni».
5. Se nella notte sono emerse altre cose fuori da questo piano, aggiungile come `idea` o `tbd`, con la voce di `docs/prossimi-passi.md` fra parentesi quadre.

- [ ] **Step 4: Commit dei documenti**

```bash
git add docs/prossimi-passi.md docs/superpowers/specs/2026-10-06-suggerimenti-soglia-bozza.md next-steps.md
git commit -m "docs: l'elenco intero per Abbina e l'Anagrafica, deciso da Mattia; i suggerimenti tagliati al pari di master"
```

- [ ] **Step 5: La verifica finale.** I «Comandi di verifica», coi loro attesi. Expected: pytest **`N_pytest` + 5**, vitest **`N_vitest` + 4** in `N_file` file, typecheck, lint e build puliti, l'e2e intera su uno stack ricreato da zero **`N_e2e` + 2**, poi `down -v` e `rm .env`. Se un numero differisce, scrivi nel report da dove viene. Infine:

```bash
docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_suggerimenti WITH (FORCE)'
```

- [ ] **Step 6: Il report.** In `docs/night-reports/<data di oggi>.md` sul ramo (se c'è aggiungi una sezione in fondo, altrimenti crealo con `# Notte del <data di oggi>`), la sezione `## I suggerimenti tagliati, al pari di master e con l'elenco intero (`suggerimenti-soglia`)`: il ramo e il merge (l'hash del commit di merge, i conflitti veri e come sono stati risolti, quel che git ha unito da solo); i conti dopo il merge (`N_*`) e alla fine; le prove di `master` che dopo il merge sono cadute per il taglio, se ce ne sono, con cosa è stato fatto; il database dei test usato e tolto; le scelte del piano che Mattia può voler rivedere (la decisione 2, solo «Abbina», confermata il 2026-11-21; la 4, l'elenco intero sono i candidati del taglio e non la `search_ingredients` di prima); la sezione «Dopo il deploy (solo Mattia)» qui sotto, ricopiata; e **«Al merge»**: il ramo contiene già `master` a `<hash>`; se `master` è andato avanti, un altro `git merge master` prima del merge su `master`. Niente push, niente merge su `master`, niente deploy.

```bash
git add docs/night-reports/
git commit -m "report: i suggerimenti tagliati al pari di master, con l'elenco intero per Abbina e l'Anagrafica"
```

---

## Dopo il deploy (solo Mattia)

La notte non tocca la produzione. Dopo revisione, merge su `master` e il deploy di sempre (`docker compose -f docker-compose.prod.yml up -d --build --wait`; **il `-f docker-compose.prod.yml` non è opzionale**, CLAUDE.md). Nessuna migrazione.

1. **La misura sull'anagrafica vera**, in sola lettura (è una lettura della produzione; qualche minuto): `docker compose -f docker-compose.prod.yml exec -T backend python -m app.cli.measure_suggestions`, da confrontare col §6 della bozza. Misura la lista tagliata, che resta quella di tutti i chiamanti tranne due.
2. **Al telefono, in Lista:** «zucch» (niente zucca), «olio» (il tonno sì, le olive no), «pollo» (petto e coscia), e una parola con un refuso nelle prime lettere, che dà una lista vuota finché la parola non è finita.
3. **In «Sistema la spesa»:** «Abbina» di una voce lunga («pasta barilla integrale») suggerisce l'ingrediente, con «Aggiungi «…»» accanto.
4. **In Anagrafica:** cercando un ingrediente che ha un doppione scritto male, si vedono tutti e due.
