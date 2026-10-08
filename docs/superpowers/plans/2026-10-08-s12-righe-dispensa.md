# S12 — Le righe della dispensa riconoscibili: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ogni riga della Dispensa ha a sinistra del nome un quadratino da 28 px con l'emoji del suo ingrediente — scelta da un elenco chiuso fermo a Emoji 14.0, decisa una volta dall'AI sulle colonne vuote, correggibile in Anagrafica — e dove l'emoji non c'è, l'icona del reparto in grigio.

**Architecture:** una colonna nuova `ingredients.emoji` (testo nullabile, migrazione `0013`) con tre stati — `NULL` non deciso, `""` «nessuna» decisa, un'emoji dell'elenco. L'elenco chiuso e la sua verifica stanno nel dominio (`backend/app/domain/emoji.py`); li usano i due soli scrittori della colonna: il servizio unico dell'anagrafica (`registry.set_ingredient_emoji`, chiamato dalla `PATCH /api/v1/ingredients/{id}`) e il servizio dell'AI (`services/ingredient_emoji.py`, lanciato a mano con `python -m app.cli.decide_emoji`). `PantryItemOut` porta `ingredient_emoji`, la scheda dell'ingrediente porta `emoji`; il client non decide niente: mostra l'emoji o, dove è `null`, l'icona del reparto con `departmentStyle`, come fa `Section`. Nel frontend nascono `components/IngredientFigure.tsx` (il quadratino), `domain/emoji.ts` (la copia dell'elenco per la griglia, confrontata da un test del backend) e `features/registry/EmojiForm.tsx` («Cambia figura»).

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, pytest su Postgres vero; OpenRouter tramite `services/llm.py` (`complete_json`), provato con i finti di `backend/tests/llm_fakes.py`; React 19, TypeScript, Tailwind 4 (token in `@theme`), TanStack Query 5, Vitest + Testing Library (jsdom), Playwright.

**Spec:** `docs/superpowers/specs/2026-10-06-righe-dispensa-bozza.md` — §3.A (la direzione scelta, con dati, API, accessibilità, rischio), **§5 (le decisioni di Mattia del 2026-10-07)**, §6 (fuori scope), §7 (cosa deve provare il piano); mockup `docs/mockups/2026-10-06-righe-dispensa.html` (direzione A). In `docs/prossimi-passi.md` la voce **[S12]**. Le decisioni sono riportate sotto, in «Decisioni prese».

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/s12-righe-dispensa` (`.worktrees/` è già in `.gitignore`), ramo `night/s12-righe-dispensa`, creato da **`night/s3-ingresso-diretto`** (il ramo del piano S3, primo della catena della notte). Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì (o dalle sue `backend/` e `frontend/`), mai dalla radice del checkout principale. Il checkout principale non si tocca: se vi trovi modifiche non committate, sono dell'utente. **Nessun push, nessun merge, nessun deploy. Mai `git stash`. Niente letture o scritture sulla produzione**: il comando che fa decidere le figure all'AI in produzione si costruisce e si prova qui, e lo lancia Mattia (sezione «Dopo il deploy (solo Mattia)»).
- **I file che anche il piano S3 tocca** (con buona probabilità `backend/app/api/pantry.py`, `backend/app/schemas/pantry.py`, `frontend/src/domain/types.ts`, `frontend/src/components/ui/icons.ts`, `frontend/e2e/style.spec.ts`, `README.md`, `docs/prossimi-passi.md`, `next-steps.md`, e i test del frontend che costruiscono un `PantryItem`): **leggili com'è sul ramo prima di cambiarli**. Il piano descrive ogni modifica a un file esistente contro un'ancora riconoscibile — una funzione, un campo, un elemento JSX per nome, o un testo esatto — e non contro numeri di riga. Dove il piano dà un file intero, è un file nuovo.
- **`Button`** (`frontend/src/components/ui/Button.tsx`) ha `variant`, `shape`, `icon`, `label`, `busy`, `unavailableReason`, `accessibleName`. **La regola (di Mattia):** in volo → `busy`; «non ancora» → `unavailableReason` (il perché sotto il pulsante, `aria-disabled`, il tocco ignorato); `disabled` nativo solo dove nessuno dei due vale. Ogni pulsante nuovo di questo piano è un `Button`.
- Tutto il colore passa dai token di `frontend/src/index.css`. Nessuna schermata nomina un colore crudo: `grep -rn "emerald\|neutral-" frontend/src` resta vuoto. **Nessun token nuovo.** Le tinte dei reparti (`dept-*`) stanno solo nel quadratino del titolo di una sezione, **mai sulle righe** (spec T3 §3.3): il ripiego della figura è monocromo, `ink-faint` su `page`. Ogni testo sta sopra 4,5:1 in chiaro e in scuro, e lo misura `frontend/e2e/style.spec.ts`; un segno (l'icona del ripiego) sopra 3:1.
- Le icone si importano solo da `frontend/src/components/ui/icons.ts` (questo piano ne aggiunge una: `IconMoodSmile`, già nel pacchetto `@tabler/icons-react` installato).
- Ogni bersaglio nuovo è almeno 44×44 px. A 375 px nessuna schermata scorre di lato.
- **Mai un vicolo cieco.** L'AI che non risponde lascia le righe col ripiego del reparto, e il comando lo dice e dice quanti ingredienti restano; una figura rifiutata dal server in Anagrafica si legge col suo perché, e il pannello resta aperto per sceglierne un'altra.
- **Il frontend non calcola logica di dominio.** L'emoji è un dato che arriva dal server; il ripiego si sceglie col reparto che c'è già (`ingredient_category`), con `departmentStyle`. La verifica dell'elenco chiuso è del backend: la copia del frontend serve solo a offrire la griglia.
- Le parole a video sono in italiano e **si copiano esattamente come sono scritte qui**; gli identificatori in inglese; i commenti in italiano come nel resto del codice.
- **Il type check è `npm run typecheck`** (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0 (settima lezione di `CLAUDE.md`). Questo piano aggiunge un campo **obbligatorio** a `PantryItem` e uno a `IngredientDetail`: ogni oggetto scritto a mano con quei tipi nei test va completato, e solo `tsc -b` lo dice.
- Controlli del frontend, da `<worktree>/frontend`: `npx vitest run` (non esiste `npm test`), `npm run typecheck`, `npm run lint`, `npm run build`.
- **Backend su Postgres vero, in un database suo.** Il server dei test è il container `spena-db-1` (porta 5433): se `docker ps --format '{{.Names}}'` non lo mostra, `docker start spena-db-1`. **Mai `docker compose up` dal worktree** (il nome del progetto Compose viene dalla cartella: nascerebbe un secondo Postgres che litiga sulla 5433), mai `-f docker-compose.prod.yml`. Questo ramo aggiunge la migrazione `0013`, e la suite fa `alembic upgrade head` sul suo database all'avvio: girata su `spena_test`, lo lascerebbe alla `0013`, e il primo piano della notte che parte da `master` (suggerimenti-soglia) troverebbe `alembic upgrade head` rotto («Can't locate revision identified by '0013'»). Per questo **ogni pytest di questo piano gira su `spena_test_s12`**, creato nella Preparazione e tolto alla fine. Nel worktree non c'è un `.venv`: si usa quello del checkout principale; `python -m` mette la cartella corrente in testa a `sys.path`, quindi si prova l'`app` del worktree. Il comando, sempre da `<worktree>/backend` (qui sotto e nei task è scritto per intero; dove un task dice «il comando di pytest» intende questo, con i percorsi di test che il task indica in coda):
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_s12 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
  Se un test sembra ignorare una modifica, `python -c 'import app; print(app.__file__)'` da `<worktree>/backend` (con lo stesso `PATH`) deve stampare un percorso dentro il worktree. Nessuna chiamata di rete nella suite: l'LLM risponde dai finti di `backend/tests/llm_fakes.py`.
- **e2e** sullo stack `spena-e2e`, dalla radice di `<worktree>`. Serve un `.env`: **si copia da `.env.example`, che non ha segreti, solo per la prova, e si cancella alla fine. Mai leggere né copiare il `.env` del checkout principale.** Prima di alzarlo, `docker ps --format '{{.Names}}' | grep spena-e2e`: se c'è e non l'hai alzato tu (un altro piano della notte), non fare `down`, aspetta che sparisca.
  ```bash
  cp .env.example .env
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed --con-ricette
  (cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
  rm .env
  ```
  Il `-p spena-e2e` e il `-f docker-compose.e2e.yml` vanno in ogni comando: un `down -v` sul progetto di default cancellerebbe la dispensa vera. Una prova fallita lascia dati nello stack: prima di rieseguire, `down -v`, poi `up`, seme e prova. Lo stack e2e ha `OPENROUTER_API_KEY` vuota (`.env.e2e`): nessuna prova e nessun comando lanciato lì spende.
- **Nessuna dipendenza nuova.** Una sola migrazione, la `0013` (la bozza la prevede: «una colonna `ingredients.emoji`, testo nullabile»). Nessun cambio di configurazione globale.

### Preparazione (una volta, prima del Task 1)

- [ ] Il ramo di partenza c'è:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify night/s3-ingresso-diretto
  git log --oneline master..night/s3-ingresso-diretto | tail -n 3
  git ls-tree --name-only night/s3-ingresso-diretto backend/alembic/versions/ | sort | tail -n 2
  ```
  Expected: un hash; i commit del piano S3; due righe che finiscono con `0011_termine_crea_ingrediente.py` e `0012_modifica_ricette.py` (le ultime due migrazioni). Questo piano non consuma niente di S3 — parte da lì perché la catena tocca gli stessi file (la Dispensa) e al merge non ci siano conflitti. Quindi:
  - se `night/s3-ingresso-diretto` **non c'è**, **fermati**: la catena della notte si è interrotta prima di questo piano, e nessun task parte. Il checkout principale non si tocca; il report di S3 dirà perché. Se nemmeno quel report esiste, crea il ramo `night/s12-righe-dispensa` da `master` solo per scriverci `docs/night-reports/<data>.md` (la causa: «manca `night/s3-ingresso-diretto`») e la riga di S12 di `next-steps.md` segnata `bloccato` con «attende: il ramo di S3, primo della catena»; nessun codice;
  - se c'è ma la riga di S3 nel suo `next-steps.md` è `bloccato`, vai avanti lo stesso: il lavoro di S3 a metà non cambia questo piano. Scrivilo nel report;
  - se fra le migrazioni del ramo c'è già una `0013` (un piano non previsto), la tua prende il numero dopo, con `down_revision` sull'ultima: adatta nome, `revision`, `down_revision` e i test del Task 2, e scrivilo nel report.
- [ ] Dal checkout principale, allinea `node_modules` al lockfile (non aggiunge dipendenze, installa quelle di `package-lock.json`):
  ```bash
  cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund
  ```
- [ ] Crea il worktree dal ramo di S3 e collega `node_modules` (e solo quello: **niente `.env`**):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/s12-righe-dispensa -b night/s12-righe-dispensa night/s3-ingresso-diretto
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/s12-righe-dispensa/frontend/node_modules
  ```
- [ ] Il database dei test di questo ramo (vedi le Global Constraints: la `0013` non deve finire in `spena_test`):
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_s12 WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_s12'
  ```
  Expected: `DROP DATABASE` (o la nota che non esisteva) e `CREATE DATABASE`.
- [ ] Cosa ha già cambiato S3 nei file di questo piano:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/s12-righe-dispensa
  git diff --stat master -- \
    backend/app/api/pantry.py backend/app/schemas/pantry.py backend/app/schemas/ingredient.py \
    backend/app/api/ingredients.py backend/app/services/registry.py backend/app/services/llm.py \
    backend/app/db/models/ingredient.py \
    frontend/src/domain/types.ts frontend/src/components/ui/icons.ts \
    frontend/src/features/pantry/PantryRow.tsx frontend/src/features/registry/ \
    frontend/src/theme.test.ts frontend/e2e/style.spec.ts README.md
  ```
  Expected: forse qualche file (S3 cambia la `POST /api/v1/pantry`, i tipi, l'e2e della Dispensa). È normale: le ancore del piano (`_to_out`, il campo `ingredient_category`, `PantryItemOut`, `IngredientPatch`, `update`, `_detail`, l'elemento JSX della riga, `MARK_PAIRS`) restano quelle; applica ogni blocco sopra la versione del ramo, senza sovrascrivere quel che S3 ha scritto, e scrivi nel report quali file hai trovato cambiati. Se un'ancora del piano **non c'è più**, fermati su quel task e segnalo `bloccato` (vedi «Margine di autonomia»).
- [ ] La linea di partenza, dal worktree:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/s12-righe-dispensa/frontend && npx vitest run 2>&1 | grep -E "Test Files|Tests "
  cd ../backend && TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_s12 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q 2>&1 | tail -n 1
  ```
  Expected: tutto verde. **Annota i tre numeri** (file e test di vitest, test di pytest): sono `N_file`, `N_vitest`, `N_pytest` del Task 9, e dipendono da quel che S3 ha aggiunto. Se una delle due linee non è verde, fermati: non è un difetto di questo piano, e va scritto nel report.
- [ ] La voce passa `in corso`, sul ramo. In `<worktree>/next-steps.md` trova la riga che contiene `S12, righe della dispensa riconoscibili` (in «Pronti per la notte» o in «Voci decise, da portare a spec e piano», com'è sul ramo), toglila da lì, e mettila sotto `## In corso` al posto di `_(niente)_` (o in coda alle righe che ci sono già), con lo stato `[in corso]` e in fondo ` → branch night/s12-righe-dispensa`, il resto del testo com'è. Poi:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/s12-righe-dispensa
  git add next-steps.md
  git commit -m "docs: S12 in corso sul ramo night/s12-righe-dispensa"
  ```

---

## Obiettivo e contesto

Le righe della Dispensa sono tutte uguali: il nome, sotto il prodotto o «sfuso», a destra le tre tacche e la ✕. Per trovare il sale bisogna leggere (S12). La bozza del 2026-10-06 ha misurato le strade sul seme (187 ingredienti): un'icona del reparto su ogni riga ripeterebbe la figura del titolo della sezione; le tinte dei reparti sulle righe si confonderebbero coi colori degli stati; le foto dei prodotti sarebbero una parte delle righe, chiare macchie in scuro e richieste a un server di terzi. Un'emoji per ingrediente dà una figura propria a quasi un terzo delle righe e una di famiglia a quasi metà, e rende riconoscibili a colpo d'occhio frutta, verdura e bevande. Mattia l'ha scelta il 2026-10-07, con il ripiego monocromo sull'icona del reparto, l'elenco fermo a Emoji 14.0, l'AI che decide una volta sulle colonne vuote, la correzione in Anagrafica, e solo in Dispensa.

Il limite è dichiarato nella bozza (§4): latticini, carne e pesce restano poco distinguibili (🧀🧀). La mossa dopo, se sul telefono si sente, è S15 (reparti collassabili) e la ricerca che c'è già, non un'altra figura.

## Decisioni prese

Dalla bozza `docs/superpowers/specs/2026-10-06-righe-dispensa-bozza.md` §5, **decise da Mattia il 2026-10-07** (non si rimettono in discussione):

1. **Direzione A**: un quadratino da 28 px a sinistra del nome, fondo `page`, con l'emoji dell'ingrediente a 18 px; dove non c'è, l'icona Tabler del reparto in `ink-faint` (monocroma: niente tinte sulle righe). La figura è `aria-hidden`.
2. **Elenco chiuso fino a Emoji 14.0** (2021): fuori 🫚 zenzero e 🫛 baccello (15.0) e il fungo marrone e il lime (15.1).
3. **Solo la Dispensa**: l'emoji arriva in `PantryItemOut` e basta; Lista, Sistema la spesa e il foglio della cottura non la mostrano.
4. **Nessuna emoji alla creazione** di un ingrediente (a mano, dall'import, dalla coda): nasce senza, mostra il ripiego, e il comando dell'AI la riempie quando si lancia, come `decide_units`.
5. **La foto del prodotto nelle schede grandi è una voce a sé** (l'`idea` P3 già in `next-steps.md`): fuori da questo piano.

E dal corpo della bozza (§3.A), parte della stessa decisione:

6. **Dati**: una colonna `ingredients.emoji`, testo nullabile. **La decide l'AI una volta** per gli ingredienti che non ce l'hanno: un comando come `decide_units`, `app.cli.decide_emoji`, a lotti di un centinaio di nomi, che scrive **solo dove la colonna è vuota** e **solo un'emoji dell'elenco chiuso**, che sta in `backend/app/domain/`: una risposta fuori elenco lascia la colonna vuota, cioè il ripiego.
7. **Si corregge in Anagrafica**: un selettore dell'elenco chiuso nella scheda dell'ingrediente, e «nessuna», dal servizio unico `registry.py`. **Una scelta a mano non viene mai riscritta dall'AI.**
8. **Niente `decided_by` e niente undo**: l'emoji non lega niente a niente.
9. **API**: `PantryItemOut.ingredient_emoji: str | None`; il ripiego si decide nel client con `departmentStyle`, dal reparto che c'è già.

Scelte di questo piano, dove la bozza non arrivava — tecniche ed estetiche, **decise da Claude su delega di Mattia** (reversibili; Mattia le rivede):

10. **Tre stati nella colonna, non due.** `NULL` = non ancora deciso (l'AI lo chiede); `""` (`NO_EMOJI`) = deciso «nessuna» — da una persona in Anagrafica o dall'AI che risponde «nessuna» — e l'AI non lo chiede più; un'emoji dell'elenco. A video `NULL` e `""` sono identici (il ripiego); fuori dal backend esce solo `null` o un'emoji (`shown_emoji`). È il modo più piccolo di tenere insieme la decisione 7 («una scelta a mano non si riscrive», «nessuna» compresa) e la 6 («l'AI scrive solo dove è vuota»), senza la colonna `decided_by` che la decisione 8 esclude. *(La metà «l'AI che risponde «nessuna»» è la decisione 22.)*
11. **L'elenco: 148 emoji in nove famiglie** (frutta; verdura, legumi, frutta secca, erbe; pane e forno; formaggi, carne, uova, piatti; cucina asiatica; pesce e mare; dolci; bevande e barattoli; casa e igiene), tutte fino a Emoji 14.0, scritte nel Task 1. Tre portano il selettore di variante U+FE0F (🌶️, 🕯️, 🗑️); la verifica accetta la figura con o senza, e scrive sempre la forma dell'elenco.
12. **L'AI risponde per numero e nome.** Ogni lotto numera i nomi da 1; la risposta riporta `n`, `nome` ed `emoji`, e si applica solo se `n` è uno di quelli chiesti, non ripetuto, e `nome` è quello chiesto (senza maiuscole né spazi ai lati). Lo schema JSON stretto restringe `emoji` all'elenco più la parola `"nessuna"` (`enum`, come `action` nelle decisioni dell'import); il backend lo verifica comunque, perché uno schema rispettato non è una risposta verificata. Lotti da 100 (`EMOJI_BATCH`), `max_tokens` 4000; il comando li fa tutti in un lancio, fa commit dopo ognuno, e al primo guasto dell'AI si ferma e dice quanti ne restano.
13. **La UPDATE che scrive controlla che la colonna sia ancora `NULL`**: una figura scelta in Anagrafica mentre il comando gira non si sovrascrive.
14. **Ogni chiamata registra la spesa** in `llm_calls`, con la sezione nuova `LlmCallSite.INGREDIENT_EMOJI = "ingredient_emoji"` (la colonna è `String(40)`: nessuna migrazione).
15. **Il rifiuto di una figura fuori elenco** in Anagrafica è un `RegistryRefusal` col codice nuovo `unknown_emoji` (un 409 come gli altri rifiuti dell'anagrafica), col messaggio ««…» non è fra le figure che l'app mostra: scegline una dell'elenco.».
16. **`PATCH /api/v1/ingredients/{id}` prende `emoji`**: un'emoji scrive quella; `null` scrive «nessuna». Lì `null` vuol dire qualcosa (a differenza di `name` e `category`), quindi la rotta lo legge per presenza (`model_fields_set`), come la scadenza in `PATCH /api/v1/pantry/{id}`. La scheda (`IngredientDetailOut`) porta `emoji`; `IngredientOut` — quello della ricerca e del selettore — no: la decisione 3 la vuole solo dove serve.
17. **In Anagrafica**: sotto le correzioni, prima di «Alias», una riga in una `Card` con la figura, «In dispensa» (o «In dispensa: l'icona del reparto») e il pulsante «Cambia figura» con `IconMoodSmile`. Non è una quarta icona nella barra accanto al titolo: lì a 375 px il titolo resterebbe con 143 px, e la figura attuale non si vedrebbe senza aprire niente. Il pannello prende il posto della riga (un pannello solo alla volta, come gli altri).
18. **«Cambia figura» è una griglia di radio veri**, non un `<select>`: una figura si sceglie guardandola, e un menu nativo ne mostrerebbe una per riga su 148 righe. Il radio nascosto dà selezione singola e frecce della tastiera (come `MissingBudgetFilter`); il nome accessibile di ciascuno è l'emoji, che lo screen reader legge col suo nome. Riquadri da 44 px; quello scelto su `brand-tint` con l'anello `brand`. In cima, a tutta larghezza, «Nessuna: l'icona del reparto» con il ripiego disegnato. Poi «Salva la figura» (primario) e «Lascia com'è» (`ghost`), come «Cambia reparto».
19. **«Salva la figura» non ancora** solo quando la scelta è l'emoji che l'ingrediente ha già: `unavailableReason` «È già la sua figura: scegline un'altra.». «Nessuna» si salva sempre, anche su un ingrediente che mostra già il ripiego: lì il ripiego può voler dire «non ancora deciso», e la scelta a mano lo fissa perché l'AI non lo decida dopo (decisione 7).
20. **La riga della Dispensa**: la figura è il primo figlio della riga in alto (`mr-1`, quindi 28 + 4 + 4 = 36 px prima del nome), e la riga della scadenza rientra di 36 px (`pl-9`) per cominciare sotto il nome, come nel mockup. Il nome va a capo (`break-words`); il prodotto resta su una riga coi puntini, com'è.
21. **Il comando non ha opzioni**: niente `--azzera` né `--imposta` come `decide_units`, perché la correzione è in Anagrafica (decisione 7). Un argomento qualsiasi è un errore (uscita 2), come in `decide_units`.

22. **L'AI che risponde «nessuna» scrive «nessuna» (`""`), non lascia la colonna vuota** — deciso da Claude su delega di Mattia il 2026-10-09 (è una scelta tecnica: a video i due casi sono identici). La bozza dice che una risposta fuori elenco lascia la colonna vuota, e che l'AI decide «una volta»; non dice cosa fa una risposta *nell'elenco* che è «nessuna figura va bene». Il piano scrive `""`: l'ingrediente è deciso, il comando non lo richiede più, e la riga mostra il ripiego (come prima). L'alternativa è lasciarlo `NULL`: a ogni lancio il comando richiederebbe gli stessi 200–400 ingredienti senza figura (stima della bozza: il 22% del seme, di più in produzione), pagando ogni volta, e la sua ultima riga non direbbe mai «nessun ingrediente in attesa». In tutti e due i casi Mattia può dare una figura a mano in Anagrafica, e a video non cambia niente. Raccomandato: `""`, come nel piano.

## Criteri di accettazione

- [ ] A 375 px, ogni riga della Dispensa ha a sinistra del nome un quadratino da 28×28 px, `aria-hidden`, con l'emoji dell'ingrediente se ce l'ha, altrimenti l'icona del suo reparto in `ink-faint` su `page` (≥ 3:1 nei due temi, misurato nel browser), senza tinte di reparto. Il nome più lungo del seme («Detersivo per la lavatrice») va a capo, tacche e ✕ restano intere nello schermo, la scadenza comincia sotto il nome, e niente scorre di lato, in chiaro e in scuro (e2e).
- [ ] I nomi accessibili della riga non cambiano (il link «Yogurt greco», «Togli … dalla dispensa», le tacche, la scadenza).
- [ ] `GET /api/v1/pantry` e la `POST` portano `ingredient_emoji`: l'emoji, o `null` sia per «non deciso» sia per «nessuna».
- [ ] `ingredients.emoji` esiste (migrazione `0013`, `String(16)` nullabile), sale, scende e risale; il modello e lo schema coincidono (`test_metadata_matches_migrations.py`).
- [ ] L'elenco chiuso: 148 emoji, nessun doppione, nessuna oltre Emoji 14.0 fra quelle che un modello proporrebbe (🫚, 🫛, le sequenze ZWJ della 15.1), ognuna nella colonna; `canonical_emoji` accetta la figura con o senza U+FE0F e rifiuta il resto (test a tabella); la copia del frontend è identica, nello stesso ordine (test del backend).
- [ ] `PATCH /api/v1/ingredients/{id}` con `{"emoji": "🍅"}` la scrive; con `{"emoji": null}` scrive «nessuna» (`""` nella colonna) e la scheda dice `null`; con una figura fuori elenco risponde 409 `unknown_emoji` e la colonna resta com'era; `{}` resta un 400. La scrittura passa da `registry.set_ingredient_emoji`.
- [ ] `python -m app.cli.decide_emoji` chiede all'AI a lotti da 100 solo gli ingredienti con la colonna `NULL`; applica solo le risposte con un numero chiesto, il nome giusto e un'emoji dell'elenco (o «nessuna»); non riscrive mai una colonna non `NULL`, nemmeno se è cambiata durante la chiamata; registra ogni chiamata in `llm_calls` come `ingredient_emoji`; senza l'AI non scrive niente, lo dice, e dice quanti ingredienti restano; un argomento qualsiasi esce 2. Tutto provato con i finti di `llm_fakes.py`, e il comando lanciato sullo stack e2e (senza chiave) degrada come previsto e non scrive niente.
- [ ] In Anagrafica la scheda dell'ingrediente mostra la figura e «Cambia figura»; il pannello offre «Nessuna: l'icona del reparto» e le 148 emoji come radio da 44 px; «Salva la figura» manda `{ "emoji": … }` (`null` per «Nessuna»), non ancora col suo perché quando la scelta è la figura che ha già; il rifiuto e il guasto si leggono; «Lascia com'è» chiude senza scrivere. Scelta lì, la figura compare nella riga della Dispensa; «Nessuna» la riporta al ripiego (e2e, a 375 px, nei due temi).
- [ ] `theme.test.ts`: la coppia di segno `ink-faint` su `page` ≥ 3:1 nei due temi.
- [ ] Tutti i test di oggi passano, migrati solo dove un oggetto `PantryItem` o `IngredientDetail` scritto a mano prende il campo nuovo (`ingredient_emoji: null`, `emoji: null`), mai indeboliti.
- [ ] vitest, typecheck, lint, build, pytest e l'e2e intera verdi; `style.spec.ts` ha due prove nuove.
- [ ] `README.md`, `docs/prossimi-passi.md` e `next-steps.md` aggiornati (Task 8), col comando per dopo il deploy.

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
TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_s12 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Dalla radice di `<worktree>`:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -rn "dept-" frontend/src/components/IngredientFigure.tsx frontend/src/features/pantry/PantryRow.tsx
grep -rln "ingredient_emoji" frontend/src --include=*.tsx | grep -v "\.test\." | sort
```

Expected: i primi due `grep` non stampano niente (nessuna tinta di reparto sulla riga); il terzo stampa solo `frontend/src/features/pantry/PantryRow.tsx` (l'emoji si mostra solo in Dispensa). E l'e2e intera con i comandi delle Global Constraints.

## Fuori scope

- Le foto dei prodotti, sulle righe e nelle schede grandi (decisione 5: voce a sé, già in `next-steps.md`), e copiare immagini di Open Food Facts sul server.
- Fondi colorati sulle righe (spec T3 §3.3), un'emoji per prodotto (la figura è dell'ingrediente), un font di emoji incluso nell'app, il layout da desktop (bozza §6).
- L'emoji in Lista, in Sistema la spesa e nel foglio della cottura (decisione 3): un'`idea` nel Task 8.
- Un'emoji chiesta alla creazione di un ingrediente (decisione 4): nessun modulo cambia.
- `import_gz` che nomina `decide_emoji` quando ha creato ingredienti nuovi, come nomina `decide_units`: un'`idea`.
- La fusione in Anagrafica: il vincitore tiene la sua figura, anche vuota, e quella del perdente si perde con lui. Un'`idea`.
- Lanciare il comando dell'AI sui dati di produzione: lo fa Mattia (sezione sotto).

## Margine di autonomia

- **Liberi:** i nomi di variabili locali, helper di test e funzioni interne non fissati qui; l'ordine dei test dentro un file; l'ordine delle classi Tailwind; la formulazione dei commenti, purché dicano il perché; l'impaginazione della griglia se a 375 px una colonna in più o in meno la rende più ordinata, purché i riquadri restino da 44 px.
- **Fissi:** le parole a video, esattamente come sono scritte nel piano («In dispensa», «In dispensa: l'icona del reparto», «Cambia figura», «Figura in dispensa», «Nessuna: l'icona del reparto», «Salva la figura», «Lascia com'è», «È già la sua figura: scegline un'altra.», «Non sono riuscito a cambiare la figura. Riprova.», il messaggio di `unknown_emoji`); le righe che il comando stampa; i nomi pubblici che altri task usano (`INGREDIENT_EMOJI`, `NO_EMOJI`, `EMOJI_MAX_LENGTH`, `canonical_emoji`, `shown_emoji`, `RefusalCode.UNKNOWN_EMOJI`, `set_ingredient_emoji`, `LlmCallSite.INGREDIENT_EMOJI`, `decide_ingredient_emoji`, `EmojiRun`, `EMOJI_BATCH`, `ingredient_emoji`, `emoji`, `IngredientFigure` e le sue prop, `EmojiForm`, l'attributo `data-figure` coi valori `emoji` e `reparto`); l'elenco delle 148 emoji, nell'ordine; i nomi accessibili di oggi.
- **Nessuna dipendenza nuova**, nessuna migrazione oltre la `0013`, nessun token di colore nuovo.
- **Un test di oggi si cambia solo per completare un oggetto scritto a mano col campo nuovo** (`ingredient_emoji: null` in un `PantryItem`, `emoji: null` in un `IngredientDetail`), che `npm run typecheck` segnala — mai per indebolirlo. Se ne serve un'altra migrazione, scrivila nel report con il perché.
- **Una decisione di comportamento non coperta e non reversibile** → si ferma quel task, si fa commit del lavoro parziale sul ramo, lo si segna `bloccato` in `next-steps.md` del ramo con la domanda precisa per Mattia, e si passa al task successivo che non ne dipende. Una scelta estetica o tecnica interna → la notte la prende da sola (Mattia le ha delegate), annotata nel report.
- Se un test fallisce e non si risolve in modo ragionevole: niente test disattivati, niente asserzioni indebolite; `bloccato` con la diagnosi.
- Se una prova di contrasto segnala un testo o un segno di questo piano sotto soglia, **non cambiare token**: scrivi nel report quale, su quale fondo, in quale tema e con quale rapporto, e segna il task `bloccato` — un colore si decide di giorno.

## Dipendenze

**Parte da `night/s3-ingresso-diretto`** (il piano S3, primo della catena, da `master`). Non ne consuma niente: ci sta sopra perché S3 cambia la Dispensa (la barra, lo scanner, la `POST /api/v1/pantry`) e al merge i due rami non devono litigare. Dopo di lui, nella catena, partono da questo ramo il tema scuro (`night/tema-scuro-spenti`) e poi S14 e S15: **S14 aggiunge anche lui un campo a `PantryItemOut` e a `PantryItem`** (`ingredient_kind`), e troverà già `ingredient_emoji` accanto.

**La migrazione `0013` e il database dei test.** I piani che partono da questo ramo (tema scuro, S14, S15) ereditano la `0013`: se fanno girare la suite su `spena_test`, lo portano alla `0013`, e il piano dei suggerimenti — che parte da `master`, dopo il tema scuro — troverà `alembic upgrade head` rotto. Questo piano non lo può risolvere da sé (usa `spena_test_s12` e lo toglie alla fine); va detto nel report, perché chi orchestra la notte lo sappia.

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `backend/app/domain/emoji.py` (nuovo), `backend/tests/domain/test_emoji.py` (nuovo) | 1 | l'elenco chiuso, `canonical_emoji`, `shown_emoji` |
| `backend/app/db/models/ingredient.py` | 2 | la colonna `emoji` |
| `backend/alembic/versions/0013_figura_ingrediente.py` (nuovo), `backend/tests/db/test_migration_0013.py` (nuovo) | 2 | la migrazione e la sua prova |
| `backend/app/services/registry.py`, `backend/tests/services/test_registry.py` | 3 | `set_ingredient_emoji`, `UNKNOWN_EMOJI` |
| `backend/app/schemas/ingredient.py`, `backend/app/api/ingredients.py`, `backend/tests/api/test_registry_ingredients.py` | 3 | `emoji` nella scheda e nella `PATCH` |
| `backend/app/schemas/pantry.py`, `backend/app/api/pantry.py`, `backend/tests/api/test_pantry.py` | 3 | `ingredient_emoji` |
| `backend/app/services/llm.py` | 4 | `LlmCallSite.INGREDIENT_EMOJI` |
| `backend/app/services/ingredient_emoji.py` (nuovo), `backend/tests/services/test_ingredient_emoji.py` (nuovo) | 4 | l'AI decide le figure |
| `backend/app/cli/decide_emoji.py` (nuovo), `backend/tests/test_decide_emoji_cli.py` (nuovo) | 4 | il comando |
| `frontend/src/domain/types.ts` | 5, 6 | `ingredient_emoji`, `emoji`, `unknown_emoji` |
| `frontend/src/components/IngredientFigure.tsx` (nuovo), `IngredientFigure.test.tsx` (nuovo) | 5 | il quadratino |
| `frontend/src/features/pantry/PantryRow.tsx`, `PantryRow.test.tsx` | 5 | la figura nella riga |
| `frontend/src/theme.test.ts` | 5 | la coppia di segno |
| i test che scrivono a mano un `PantryItem` (`pantryView.test.ts`, `CookSheet.test.tsx`, `RecipeDetailScreen.test.tsx`, e quelli di S3) | 5 | `ingredient_emoji: null` |
| `frontend/src/domain/emoji.ts` (nuovo), `backend/tests/test_frontend_emoji.py` (nuovo) | 6 | la copia dell'elenco, e la sua guardia |
| `frontend/src/components/ui/icons.ts` | 6 | `IconMoodSmile` |
| `frontend/src/features/registry/api.ts`, `EmojiForm.tsx` (nuovo), `IngredientScreen.tsx`, `IngredientScreen.test.tsx` | 6 | «Cambia figura» |
| `frontend/e2e/style.spec.ts` | 7 | due prove |
| `README.md`, `docs/prossimi-passi.md`, `next-steps.md` | 8 | i documenti |
| `docs/night-reports/<data>.md` | 9 | il report |

---

### Task 1: L'elenco chiuso, nel dominio

**Files:**
- Create: `backend/app/domain/emoji.py`
- Create: `backend/tests/domain/test_emoji.py`

**Interfaces:**
- Produces (in `app.domain.emoji`): `EMOJI_MAX_LENGTH: int = 16`; `NO_EMOJI: str = ""`; `INGREDIENT_EMOJI: tuple[str, ...]` (148 voci, nell'ordine scritto qui); `canonical_emoji(value: str) -> str | None`; `shown_emoji(stored: str | None) -> str | None`. I Task 2–6 li usano.

- [ ] **Step 1: I test che falliscono**

Crea `backend/tests/domain/test_emoji.py`:

```python
"""L'elenco chiuso delle figure (S12) e la sua verifica: senza database, come le regole.

L'elenco è il confine fra quel che l'AI o una persona possono scrivere nella colonna e
quel che no. La bozza lo ferma a Emoji 14.0 perché una figura più recente, su un
telefono non aggiornato, diventa un quadratino vuoto (§5.2): le prove qui sotto
guardano proprio le figure che un modello proporrebbe per prime e che non ci devono
essere.
"""

import pytest

from app.domain.emoji import (
    EMOJI_MAX_LENGTH,
    INGREDIENT_EMOJI,
    NO_EMOJI,
    canonical_emoji,
    shown_emoji,
)

VS16 = "️"


@pytest.mark.parametrize(
    ("scritta", "attesa"),
    [
        ("🥕", "🥕"),
        # il peperoncino è nell'elenco col selettore di variante, e lo si accetta con e senza
        ("\U0001F336️", "\U0001F336️"),
        ("\U0001F336", "\U0001F336️"),
        (" 🥕 ", "🥕"),
        ("🚗", None),
        ("", None),
        ("🥕🥕", None),
        # Emoji 15.0: zenzero e baccello, le prime che un modello proporrebbe
        ("\U0001FADA", None),
        ("\U0001FADB", None),
        # la parola con cui l'AI dice «nessuna» non è una figura
        ("nessuna", None),
    ],
)
def test_canonical_emoji_accetta_solo_l_elenco(scritta, attesa):
    assert canonical_emoji(scritta) == attesa


@pytest.mark.parametrize(
    ("colonna", "a_video"),
    [(None, None), (NO_EMOJI, None), ("🥕", "🥕")],
)
def test_shown_emoji_tiene_la_stringa_vuota_nel_backend(colonna, a_video):
    """«Non deciso» e «nessuna» sono lo stesso ripiego per chi guarda: la differenza
    serve solo al comando dell'AI, e fuori dal backend non esce."""
    assert shown_emoji(colonna) == a_video


def test_l_elenco_non_ha_doppioni():
    """Nemmeno uno che differisca solo per il selettore di variante: la verifica li
    tratterebbe come la stessa figura, e la griglia ne mostrerebbe due."""
    nude = [voce.replace(VS16, "") for voce in INGREDIENT_EMOJI]
    assert len(nude) == len(set(nude))
    assert len(INGREDIENT_EMOJI) == 148


def test_l_elenco_e_fermo_a_emoji_14():
    """Le figure della 15.0 e della 15.1 che riguardano la cucina restano fuori, e con
    loro ogni sequenza ZWJ (U+200D): fino alla 14.0 nessuna figura di cibo, bevande o
    casa ne usa una, dalla 15.1 il lime e il fungo marrone sì."""
    vietate = {"\U0001FADA", "\U0001FADB", "\U0001FAAD", "\U0001FAAE"}
    for voce in INGREDIENT_EMOJI:
        assert "‍" not in voce, voce
        assert not (set(voce) & vietate), voce


def test_le_tre_figure_col_selettore_lo_portano():
    """Peperoncino, candela e cestino si disegnano come emoji solo col selettore di
    variante: senza, alcuni sistemi li mostrano come simboli in bianco e nero. Una copia
    dell'elenco che lo perdesse cambierebbe figura senza che niente fallisca."""
    for voce in ("\U0001F336️", "\U0001F56F️", "\U0001F5D1️"):
        assert voce in INGREDIENT_EMOJI


def test_ogni_figura_sta_nella_colonna():
    assert all(0 < len(voce) <= EMOJI_MAX_LENGTH for voce in INGREDIENT_EMOJI)


def test_nessuna_non_e_una_figura():
    """La stringa vuota è «nessuna» nella colonna: se fosse anche una voce dell'elenco,
    una figura scelta e una non scelta sarebbero la stessa cosa."""
    assert NO_EMOJI not in INGREDIENT_EMOJI
    assert "nessuna" not in INGREDIENT_EMOJI
```

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/backend`): `TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_s12 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/domain/test_emoji.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'app.domain.emoji'`.

- [ ] **Step 3: Il modulo**

Crea `backend/app/domain/emoji.py` (le emoji si copiano carattere per carattere; tre portano U+FE0F, e il test lo controlla):

```python
"""Le figure degli ingredienti in Dispensa (S12): l'elenco chiuso, e la sua verifica.

Bozza `docs/superpowers/specs/2026-10-06-righe-dispensa-bozza.md`, §3.A e §5. Un
ingrediente ha al più un'emoji, scelta da questo elenco e da nessun altro posto: dall'AI
(`python -m app.cli.decide_emoji`) o a mano in Anagrafica. L'elenco è fermo a **Emoji
14.0** (2021, deciso da Mattia il 2026-10-07): una figura più recente, su un telefono non
aggiornato, diventa un quadratino vuoto, che è peggio del ripiego. Restano fuori per
questo 🫚 zenzero e 🫛 baccello (15.0) e le sequenze della 15.1 (il lime, il fungo
marrone), che sono le prime che un modello proporrebbe.

Sta nel dominio e non in un servizio perché i punti che scrivono la colonna sono due —
il servizio dell'anagrafica e quello dell'AI — e la stessa verifica deve valere per
tutti e due (prima lezione di CLAUDE.md). Il frontend ne tiene una copia,
`frontend/src/domain/emoji.ts`, solo per offrire la griglia di «Cambia figura»:
`backend/tests/test_frontend_emoji.py` la confronta con questa, voce per voce e
nell'ordine.

`ingredients.emoji` ha tre stati, non due:
- `NULL`: nessuno ha ancora deciso. La riga mostra l'icona del reparto, e il comando
  dell'AI la chiederà;
- `NO_EMOJI`, la stringa vuota: qualcuno ha deciso che nessuna figura dell'elenco va
  bene — l'AI rispondendo «nessuna», o una persona scegliendo «Nessuna» in Anagrafica.
  A video è identica a `NULL`, ma l'AI non la chiede più: scrive solo dove è `NULL`, e
  così una scelta fatta a mano non si riscrive mai (bozza §3.A);
- un'emoji dell'elenco.
Fuori dal backend esce solo `None` o un'emoji (`shown_emoji`): la stringa vuota è un
dettaglio della colonna, e il client non ha motivo di conoscerlo.
"""

# La larghezza della colonna. La figura più lunga dell'elenco è di due code point
# (l'emoji e il selettore di variante U+FE0F): sedici lasciano margine senza invitare a
# scriverci altro.
EMOJI_MAX_LENGTH = 16

NO_EMOJI = ""

# Il selettore di variante «disegnala come emoji». Tre voci lo portano (peperoncino,
# candela, cestino): senza, alcuni sistemi le mostrano come simboli in bianco e nero.
_VS16 = "️"

# Nell'ordine della griglia dell'Anagrafica, per famiglie: chi cerca la carota la trova
# vicino alle altre verdure. Le figure «di famiglia» (🧀 per ogni formaggio, 🐟 per ogni
# pesce) sono volute: la bozza le conta come figure, e sono meglio del ripiego.
INGREDIENT_EMOJI: tuple[str, ...] = (
    # frutta
    "🍇", "🍈", "🍉", "🍊", "🍋", "🍌", "🍍", "🥭", "🍎", "🍏", "🍐", "🍑", "🍒", "🍓", "🫐",
    "🥝", "🍅", "🫒", "🥥",
    # verdura, legumi, frutta secca, erbe
    "🥑", "🍆", "🥔", "🥕", "🌽", "🌶️", "🫑", "🥒", "🥬", "🥦", "🧄", "🧅", "🍄", "🥜", "🫘",
    "🌰", "🌿", "🌱", "🌾",
    # pane e forno
    "🍞", "🥐", "🥖", "🫓", "🥨", "🥯", "🥞", "🧇",
    # formaggi, carne, uova, piatti
    "🧀", "🍖", "🍗", "🥩", "🥓", "🍔", "🍟", "🍕", "🌭", "🥪", "🌮", "🌯", "🫔", "🥙", "🧆",
    "🥚", "🍳", "🥘", "🍲", "🫕", "🥣", "🥗", "🍿", "🧈", "🧂", "🥫",
    # cucina asiatica
    "🍱", "🍘", "🍙", "🍚", "🍛", "🍜", "🍝", "🍠", "🍢", "🍣", "🍤", "🍥", "🥮", "🍡", "🥟",
    "🥠", "🥡",
    # pesce e mare
    "🦀", "🦞", "🦐", "🦑", "🦪", "🐟", "🐙", "🐚",
    # dolci
    "🍦", "🍧", "🍨", "🍩", "🍪", "🎂", "🍰", "🧁", "🥧", "🍫", "🍬", "🍭", "🍮", "🍯",
    # bevande e barattoli
    "🍼", "🥛", "☕", "🫖", "🍵", "🍶", "🍾", "🍷", "🍸", "🍹", "🍺", "🥂", "🥃", "🫗", "🥤",
    "🧋", "🧃", "🧉", "🧊", "🫙",
    # casa e igiene
    "🧻", "🧽", "🧴", "🧼", "🪥", "🪒", "🧹", "🧺", "🪣", "🧤", "🧷", "🩹", "💊", "🕯️", "💡",
    "🔋", "🗑️",
)

_BY_BARE = {voce.replace(_VS16, ""): voce for voce in INGREDIENT_EMOJI}


def canonical_emoji(value: str) -> str | None:
    """La voce dell'elenco che `value` scrive, o `None` se non è nell'elenco.

    Il selettore di variante può esserci o no: «🌶» e «🌶️» sono la stessa figura, e un
    modello o una tastiera a volte lo omettono. Si torna sempre la forma dell'elenco,
    così la colonna ne ha una sola. Gli spazi ai lati non contano."""
    bare = value.strip().replace(_VS16, "")
    return _BY_BARE.get(bare) if bare else None


def shown_emoji(stored: str | None) -> str | None:
    """Quel che la colonna dice a chi guarda: un'emoji, o `None` per il ripiego."""
    return stored or None
```

- [ ] **Step 4: Passano**

Run: `TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_s12 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/domain/test_emoji.py`
Expected: PASS, 18 test (10 + 3 + 5).

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/emoji.py backend/tests/domain/test_emoji.py
git commit -m "feat(dominio): S12, l'elenco chiuso delle figure degli ingredienti fino a Emoji 14.0"
```

---

### Task 2: La colonna `ingredients.emoji` e la migrazione `0013`

**Files:**
- Modify: `backend/app/db/models/ingredient.py` (la classe `Ingredient`)
- Create: `backend/alembic/versions/0013_figura_ingrediente.py`
- Create: `backend/tests/db/test_migration_0013.py`

**Interfaces:**
- Consumes: `EMOJI_MAX_LENGTH` (Task 1).
- Produces: `Ingredient.emoji: Mapped[str | None]`, `String(16)`, nullabile; la revisione Alembic `"0013"` con `down_revision = "0012"`. I Task 3–4 leggono e scrivono la colonna.

- [ ] **Step 1: Il test che fallisce**

Crea `backend/tests/db/test_migration_0013.py`:

```python
"""La migrazione 0013 sale e scende (S12).

Su un database suo, creato e distrutto qui, come `test_migration_0012.py`: far scendere
quello della suite toglierebbe la colonna sotto i piedi a ogni altro test. Alembic gira
in un sottoprocesso, perché il suo template async chiama `asyncio.run`, che dentro un
loop già in corsa esplode.
"""

import os
import subprocess

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://spena:spena@localhost:5433/spena_test"
)
SERVER, _, TEST_DB = TEST_DATABASE_URL.rpartition("/")
SCRATCH_DB = f"{TEST_DB}_migrazione_0013"

EMOJI = (
    "SELECT character_maximum_length FROM information_schema.columns "
    "WHERE table_name = 'ingredients' AND column_name = 'emoji'"
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


async def _ingrediente(url: str, nome: str, emoji: str | None) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO ingredients (id, name, display_name, category, kind, emoji) "
                    "VALUES (gen_random_uuid(), :nome, :nome, 'verdura', 'food', :emoji)"
                ),
                {"nome": nome, "emoji": emoji},
            )
    finally:
        await engine.dispose()


async def test_la_0013_sale_scende_e_risale(scratch_url):
    alembic(scratch_url, "upgrade", "0013")
    assert await _scalar(scratch_url, EMOJI) == 16
    await _ingrediente(scratch_url, "carota", "🥕")
    await _ingrediente(scratch_url, "sedano", None)
    figura = "SELECT emoji FROM ingredients WHERE name = :nome"
    assert await _scalar(scratch_url, figura, nome="carota") == "🥕"
    # un ingrediente nasce «non deciso» (decisione 4 della bozza: nessuna emoji alla
    # creazione): è il comando dell'AI, non la migrazione, che lo decide
    assert await _scalar(scratch_url, figura, nome="sedano") is None

    alembic(scratch_url, "downgrade", "0012")
    assert await _scalar(scratch_url, EMOJI) is None

    alembic(scratch_url, "upgrade", "head")
    assert await _scalar(scratch_url, EMOJI) == 16
```

- [ ] **Step 2: Fallisce**

Run: `TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_s12 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/db/test_migration_0013.py`
Expected: FAIL, Alembic esce con errore («Can't locate revision identified by '0013'»).

- [ ] **Step 3: La migrazione**

Crea `backend/alembic/versions/0013_figura_ingrediente.py`:

```python
"""la figura dell'ingrediente in dispensa (S12)

Revision ID: 0013
"""
import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"


def upgrade() -> None:
    # Nessun passo dati: ogni ingrediente resta `NULL`, «non deciso», e mostra l'icona del
    # reparto finché `python -m app.cli.decide_emoji` non lo decide. È un comando a parte
    # e non un passo qui perché chiama l'AI: una migrazione che va in rete renderebbe
    # l'avvio del backend (che migra da sé, `docker-entrypoint.sh`) dipendente da
    # OpenRouter. I tre stati della colonna sono spiegati in `app/domain/emoji.py`.
    op.add_column("ingredients", sa.Column("emoji", sa.String(16), nullable=True))


def downgrade() -> None:
    # Scendere perde le figure decise, dall'AI e a mano.
    op.drop_column("ingredients", "emoji")
```

- [ ] **Step 4: Il modello**

In `backend/app/db/models/ingredient.py`:

1. Accanto all'import di `kind_for_category` aggiungi:
   ```python
   from app.domain.emoji import EMOJI_MAX_LENGTH
   ```
2. Nella classe `Ingredient`, subito dopo la riga
   ```python
       composition_ref: Mapped[str | None] = mapped_column(String(60), nullable=True)
   ```
   aggiungi:
   ```python
       # La figura delle sue righe in Dispensa (S12). Tre stati: `NULL` non ancora deciso
       # (l'AI lo chiederà), `""` deciso «nessuna», altrimenti una voce di
       # `INGREDIENT_EMOJI`. Chi la scrive passa da `canonical_emoji`
       # (`app/domain/emoji.py`, dove i tre stati sono spiegati): oggi
       # `registry.set_ingredient_emoji` e `services/ingredient_emoji.py`, nessun altro.
       emoji: Mapped[str | None] = mapped_column(String(EMOJI_MAX_LENGTH), nullable=True)
   ```

- [ ] **Step 5: Passano, con la rete di sicurezza dell'autogenerate**

Run: `TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_s12 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/db/`
Expected: PASS, compreso `test_metadata_matches_migrations.py` (modello e schema coincidono: nessuna operazione proposta) e il test nuovo.

- [ ] **Step 6: Commit**

```bash
git add backend/app/db/models/ingredient.py backend/alembic/versions/0013_figura_ingrediente.py backend/tests/db/test_migration_0013.py
git commit -m "feat(db): S12, la colonna ingredients.emoji (migrazione 0013), nullabile e senza passo dati"
```

---

### Task 3: La figura nelle risposte, e la correzione dall'Anagrafica

**Files:**
- Modify: `backend/app/services/registry.py` (`RefusalCode`, una funzione nuova dopo `recategorize_ingredient`)
- Modify: `backend/app/schemas/ingredient.py` (`IngredientDetailOut`, `IngredientPatch`)
- Modify: `backend/app/api/ingredients.py` (`_detail`, `update`)
- Modify: `backend/app/schemas/pantry.py` (`PantryItemOut`), `backend/app/api/pantry.py` (`_to_out`)
- Test: `backend/tests/services/test_registry.py`, `backend/tests/api/test_registry_ingredients.py`, `backend/tests/api/test_pantry.py`

**Interfaces:**
- Consumes: `NO_EMOJI`, `canonical_emoji`, `shown_emoji`, `EMOJI_MAX_LENGTH` (Task 1); `Ingredient.emoji` (Task 2).
- Produces: `RefusalCode.UNKNOWN_EMOJI = "unknown_emoji"`; `async def set_ingredient_emoji(session: AsyncSession, ingredient_id: uuid.UUID, emoji: str | None) -> Ingredient` in `app.services.registry` (`None` → «nessuna»; non fa commit; `LookupError` per un id che non c'è; `RegistryRefusal(UNKNOWN_EMOJI)` fuori elenco); `IngredientDetailOut.emoji: str | None`; `IngredientPatch.emoji: str | None`; `PantryItemOut.ingredient_emoji: str | None`. Il frontend (Task 5–6) legge `ingredient_emoji` ed `emoji` e manda `{"emoji": …}`.

- [ ] **Step 1: I test del servizio, che falliscono**

In `backend/tests/services/test_registry.py`:

1. Nell'import da `app.services.registry` aggiungi `set_ingredient_emoji` (in ordine alfabetico, dopo `set_barcode`). Aggiungi in cima, fra gli import:
   ```python
   from app.domain.emoji import NO_EMOJI
   ```
2. In fondo al file aggiungi:

```python
# --- S12: la figura dell'ingrediente in Dispensa ---


async def _figura_salvata(db_session, ingrediente: Ingredient) -> str | None:
    """Dal database e non dall'oggetto in memoria: è la colonna che il comando dell'AI
    legge per sapere chi è ancora da decidere."""
    return (
        await db_session.execute(select(Ingredient.emoji).where(Ingredient.id == ingrediente.id))
    ).scalar_one()


async def test_una_figura_dell_elenco_si_scrive(db_session, anagrafica):
    salvia = await set_ingredient_emoji(db_session, anagrafica["salvia"].id, "🌿")
    assert salvia.emoji == "🌿"
    assert await _figura_salvata(db_session, anagrafica["salvia"]) == "🌿"


async def test_senza_selettore_di_variante_si_scrive_la_forma_dell_elenco(db_session, anagrafica):
    await set_ingredient_emoji(db_session, anagrafica["salvia"].id, "\U0001F336")
    assert await _figura_salvata(db_session, anagrafica["salvia"]) == "\U0001F336️"


async def test_nessuna_si_scrive_come_decisa_e_non_come_vuota(db_session, anagrafica):
    """`None` non torna `NULL`: `NULL` vuol dire «non ancora deciso», e il comando
    dell'AI lo deciderebbe al giro dopo, riscrivendo una scelta fatta a mano."""
    await set_ingredient_emoji(db_session, anagrafica["salvia"].id, "🌿")
    await set_ingredient_emoji(db_session, anagrafica["salvia"].id, None)
    assert await _figura_salvata(db_session, anagrafica["salvia"]) == NO_EMOJI


async def test_una_figura_fuori_elenco_rifiuta_e_non_scrive(db_session, anagrafica):
    await set_ingredient_emoji(db_session, anagrafica["salvia"].id, "🌿")
    with pytest.raises(RegistryRefusal) as rifiuto:
        await set_ingredient_emoji(db_session, anagrafica["salvia"].id, "🚗")
    assert rifiuto.value.code == RefusalCode.UNKNOWN_EMOJI
    assert "🚗" in rifiuto.value.message
    assert await _figura_salvata(db_session, anagrafica["salvia"]) == "🌿"


async def test_la_figura_di_un_ingrediente_che_non_c_e(db_session):
    with pytest.raises(LookupError):
        await set_ingredient_emoji(db_session, uuid.uuid4(), "🌿")
```

- [ ] **Step 2: I test delle rotte, che falliscono**

In `backend/tests/api/test_registry_ingredients.py`, in fondo al file:

```python
# --- S12: la figura dell'ingrediente in Dispensa ---


async def test_la_scheda_dice_la_figura_e_nasce_senza(logged_client, anagrafica):
    corpo = (await logged_client.get(f"{BASE}/{anagrafica['pomodori']}")).json()
    assert corpo["emoji"] is None


async def test_cambiare_la_figura(logged_client, anagrafica):
    risposta = await logged_client.patch(f"{BASE}/{anagrafica['pomodori']}", json={"emoji": "🍅"})
    assert risposta.status_code == 200
    assert risposta.json()["emoji"] == "🍅"


async def test_nessuna_si_manda_null_e_resta_decisa(logged_client, db_session, anagrafica):
    """`null` qui vuol dire «Nessuna» e non «nessun cambiamento»: a video è il ripiego,
    nella colonna la stringa vuota, che il comando dell'AI non chiede più."""
    await logged_client.patch(f"{BASE}/{anagrafica['pomodori']}", json={"emoji": "🍅"})

    risposta = await logged_client.patch(f"{BASE}/{anagrafica['pomodori']}", json={"emoji": None})

    assert risposta.status_code == 200
    assert risposta.json()["emoji"] is None
    salvata = (
        await db_session.execute(
            select(Ingredient.emoji).where(Ingredient.id == anagrafica["pomodori"])
        )
    ).scalar_one()
    assert salvata == ""


async def test_una_figura_fuori_elenco_e_un_409_e_non_scrive(logged_client, db_session, anagrafica):
    risposta = await logged_client.patch(f"{BASE}/{anagrafica['pomodori']}", json={"emoji": "🚗"})

    assert risposta.status_code == 409
    assert risposta.json()["code"] == "unknown_emoji"
    salvata = (
        await db_session.execute(
            select(Ingredient.emoji).where(Ingredient.id == anagrafica["pomodori"])
        )
    ).scalar_one()
    assert salvata is None
```

(`select` e `Ingredient` sono già importati in cima al file; `test_un_corpo_vuoto_e_un_400` resta com'è e deve restare verde.)

- [ ] **Step 3: I test della dispensa, che falliscono**

In `backend/tests/api/test_pantry.py`, in fondo al file:

```python
# --- S12: la figura dell'ingrediente, nella risposta della dispensa ---


async def test_la_dispensa_manda_la_figura_dell_ingrediente(logged_client, db_session, dispensa):
    """L'emoji o `null`: «non ancora deciso» e «nessuna» sono lo stesso ripiego per il
    client, e la stringa vuota della colonna non esce dal backend."""
    from app.domain.emoji import NO_EMOJI

    dispensa["yogurt"].emoji = "🥛"
    dispensa["pomodoro"].emoji = NO_EMOJI
    db_session.add_all([
        PantryItem(ingredient_id=dispensa[chiave].id, status=PantryStatus.AVAILABLE)
        for chiave in ("yogurt", "pomodoro", "aglio")
    ])
    await db_session.flush()

    body = (await logged_client.get("/api/v1/pantry")).json()

    assert {e["ingredient_name"]: e["ingredient_emoji"] for e in body} == {
        "yogurt greco": "🥛", "pomodoro": None, "aglio": None,
    }


async def test_una_voce_appena_entrata_porta_la_figura(logged_client, db_session, dispensa):
    dispensa["pomodoro"].emoji = "🍅"
    await db_session.flush()

    risposta = await logged_client.post("/api/v1/pantry", json={
        "ingredient_id": str(dispensa["pomodoro"].id), "status": "available",
    })

    assert risposta.status_code == 201
    assert risposta.json()["ingredient_emoji"] == "🍅"
```

Se sul ramo la `POST /api/v1/pantry` di S3 chiede altri campi obbligatori, aggiungili al corpo come li manda `test_loose_produce_enters_without_a_product` nello stesso file (leggilo com'è sul ramo).

- [ ] **Step 4: Falliscono**

Run: `TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_s12 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/services/test_registry.py tests/api/test_registry_ingredients.py tests/api/test_pantry.py`
Expected: FAIL — `ImportError: cannot import name 'set_ingredient_emoji'` (raccolta di `test_registry.py`), e nelle rotte `KeyError: 'emoji'` / `'ingredient_emoji'` o un 400 sulla `PATCH`.

- [ ] **Step 5: Il servizio**

In `backend/app/services/registry.py`:

1. Fra gli import, accanto a `from app.domain.barcodes import has_valid_check_digit`, aggiungi:
   ```python
   from app.domain.emoji import NO_EMOJI, canonical_emoji
   ```
2. In `class RefusalCode(StrEnum)`, dopo `BAD_CHECKSUM = "bad_checksum"`, aggiungi:
   ```python
       UNKNOWN_EMOJI = "unknown_emoji"
   ```
3. Subito dopo la funzione `recategorize_ingredient` (prima di `queue_terms_by_alias`) aggiungi:

```python
async def set_ingredient_emoji(
    session: AsyncSession, ingredient_id: uuid.UUID, emoji: str | None
) -> Ingredient:
    """La figura delle righe di questo ingrediente in Dispensa (S12), scelta a mano.

    `None` è «Nessuna»: si scrive `NO_EMOJI` e non `NULL`, perché `NULL` vuol dire «non
    ancora deciso» e il comando dell'AI lo deciderebbe al giro dopo, riscrivendo una
    scelta fatta a mano (bozza S12 §3.A). Un'emoji fuori dall'elenco chiuso è un rifiuto,
    e la colonna resta com'era: la verifica è la stessa che fa il comando dell'AI
    (`canonical_emoji`), perché la colonna ha due scrittori e una regola sola.
    """
    ingredient = await _ingredient(session, ingredient_id)
    if emoji is None:
        ingredient.emoji = NO_EMOJI
    else:
        canonical = canonical_emoji(emoji)
        if canonical is None:
            raise RegistryRefusal(
                RefusalCode.UNKNOWN_EMOJI,
                f"«{emoji.strip()}» non è fra le figure che l'app mostra: scegline una "
                "dell'elenco.",
            )
        ingredient.emoji = canonical
    await session.flush()
    return ingredient
```

- [ ] **Step 6: Gli schemi e le rotte**

1. In `backend/app/schemas/ingredient.py`:
   - in cima, accanto a `from app.db.models.ingredient import IngredientCategory`, aggiungi `from app.domain.emoji import EMOJI_MAX_LENGTH`;
   - in `class IngredientDetailOut(IngredientOut)`, prima di `aliases: list[AliasOut]`, aggiungi:
     ```python
         # la figura delle sue righe in Dispensa (S12): un'emoji, o `None` per l'icona del
         # reparto. Solo qui e non in `IngredientOut`: la ricerca e i selettori non la
         # mostrano (decisione 3 della bozza, solo la Dispensa)
         emoji: str | None
     ```
   - in `class IngredientPatch(BaseModel)`, dopo il campo `category`, aggiungi:
     ```python
         # Qui `null` vuol dire qualcosa: «Nessuna», l'icona del reparto, decisa a mano. Per
         # questo il campo si legge per presenza (`model_fields_set`), come la scadenza in
         # `PantryItemPatch`, e non per valore come `name` e `category`. Che sia un'emoji
         # dell'elenco lo verifica il servizio (`set_ingredient_emoji`), non lo schema: il
         # rifiuto deve arrivare come gli altri rifiuti dell'anagrafica, col suo codice.
         emoji: str | None = Field(default=None, max_length=EMOJI_MAX_LENGTH)
     ```
     e nella docstring di `IngredientPatch`, in fondo, aggiungi la frase: «`emoji` fa eccezione: vedi il commento sul campo.»
2. In `backend/app/api/ingredients.py`:
   - in cima, aggiungi `from app.domain.emoji import shown_emoji`;
   - in `_detail`, nella costruzione di `IngredientDetailOut(...)`, dopo `**IngredientOut.model_validate(ingredient).model_dump(),` aggiungi la riga:
     ```python
             emoji=shown_emoji(ingredient.emoji),
     ```
   - in `update`, la guardia
     ```python
         if payload.name is None and payload.category is None:
             raise HTTPException(status.HTTP_400_BAD_REQUEST, "niente da cambiare")
     ```
     diventa
     ```python
         if (
             payload.name is None
             and payload.category is None
             and "emoji" not in payload.model_fields_set
         ):
             raise HTTPException(status.HTTP_400_BAD_REQUEST, "niente da cambiare")
     ```
     e dentro il `try`, dopo il blocco `if payload.category is not None: …`, aggiungi:
     ```python
             if "emoji" in payload.model_fields_set:
                 await registry.set_ingredient_emoji(session, ingredient_id, payload.emoji)
     ```
3. In `backend/app/schemas/pantry.py`, in `class PantryItemOut(BaseModel)`, subito dopo `ingredient_category: str` aggiungi:
   ```python
       # La figura della riga (S12): l'emoji dell'ingrediente, o `None` per il ripiego
       # sull'icona del reparto, che il client sceglie da `ingredient_category`. Un dato e
       # non un calcolo: «non deciso» e «nessuna» escono tutti e due `None`.
       ingredient_emoji: str | None
   ```
4. In `backend/app/api/pantry.py`:
   - in cima, aggiungi `from app.domain.emoji import shown_emoji` (accanto agli altri import da `app.domain`);
   - in `_to_out`, subito dopo la riga `ingredient_category=item.ingredient.category,` aggiungi:
     ```python
             ingredient_emoji=shown_emoji(item.ingredient.emoji),
     ```

- [ ] **Step 7: Passano, e tutta la suite**

Run: `TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_s12 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q`
Expected: tutto verde, **`N_pytest` + 30** (18 + 1 + 5 + 4 + 2). Nessun altro test cambiato.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/registry.py backend/app/schemas/ingredient.py backend/app/api/ingredients.py backend/app/schemas/pantry.py backend/app/api/pantry.py backend/tests/services/test_registry.py backend/tests/api/test_registry_ingredients.py backend/tests/api/test_pantry.py
git commit -m "feat(api): S12, la figura nella dispensa e nella scheda dell'ingrediente, e la sua correzione dal servizio unico dell'anagrafica"
```

---

### Task 4: L'AI decide le figure — il servizio e il comando

**Files:**
- Modify: `backend/app/services/llm.py` (`LlmCallSite`)
- Create: `backend/app/services/ingredient_emoji.py`
- Create: `backend/app/cli/decide_emoji.py`
- Create: `backend/tests/services/test_ingredient_emoji.py`
- Create: `backend/tests/test_decide_emoji_cli.py`

**Interfaces:**
- Consumes: `INGREDIENT_EMOJI`, `NO_EMOJI`, `canonical_emoji` (Task 1); `Ingredient.emoji` (Task 2); `complete_json`, `LlmUnavailable`, `LlmUsage` (`app.services.llm`); `record_llm_call` (`app.repositories.llm_calls`); `FakeLlm` (`backend/tests/llm_fakes.py`).
- Produces: `LlmCallSite.INGREDIENT_EMOJI = "ingredient_emoji"`; in `app.services.ingredient_emoji`: `EMOJI_BATCH = 100`, `EMOJI_MAX_TOKENS = 4000`, `NONE_ANSWER = "nessuna"`, `EMOJI_SYSTEM_PROMPT: str`, `EMOJI_SCHEMA: dict`, `@dataclass(frozen=True) class EmojiRun(applied: int = 0, none: int = 0, refused: int = 0, pending: int = 0, unavailable: str | None = None)`, `async def decide_ingredient_emoji(session: AsyncSession, client: httpx.AsyncClient | None = None, batch_size: int = EMOJI_BATCH, after_batch: Callable[[], Awaitable[None]] | None = None) -> EmojiRun`; il comando `python -m app.cli.decide_emoji` (`async def main(argv: list[str]) -> int`). Il Task 9 lo lancia sullo stack e2e; Mattia in produzione.

- [ ] **Step 1: I test del servizio, che falliscono**

Crea `backend/tests/services/test_ingredient_emoji.py`:

```python
"""Le figure degli ingredienti decise dall'AI (S12), e la verifica della sua risposta.

Come per le unità e i termini dell'import, la parte che conta è la verifica: una
risposta che non si può controllare non si applica, e l'ingrediente resta senza figura
— cioè col ripiego del reparto, che è meno bello e non è sbagliato.

Il finto sostituisce `httpx.AsyncClient`, non il client di OpenRouter: sotto prova c'è
`complete_json` per intero, header e corpo compresi.
"""

import json

import httpx
import pytest
from sqlalchemy import select, update

from app.db.models.ingredient import Ingredient
from app.db.models.llm_call import LlmCall
from app.domain.emoji import INGREDIENT_EMOJI, NO_EMOJI
from app.services.ingredient_emoji import EmojiRun, decide_ingredient_emoji
from llm_fakes import FakeLlm


@pytest.fixture(autouse=True)
def chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


async def _voci(db_session, *voci: tuple[str, str, str | None]) -> dict[str, Ingredient]:
    """(nome, reparto, emoji) → l'ingrediente, già nel database."""
    creati = {
        nome: Ingredient(name=nome, display_name=nome.capitalize(), category=reparto, emoji=emoji)
        for nome, reparto, emoji in voci
    }
    db_session.add_all(creati.values())
    await db_session.flush()
    return creati


async def _figura(db_session, ingrediente: Ingredient) -> str | None:
    """Dal database, non dall'oggetto in memoria."""
    return (
        await db_session.execute(select(Ingredient.emoji).where(Ingredient.id == ingrediente.id))
    ).scalar_one()


def _risposta(*righe: tuple[int, str, str]) -> dict:
    return {"emoji": [{"n": n, "nome": nome, "emoji": emoji} for n, nome, emoji in righe]}


def _domanda(corpo: dict) -> list[dict]:
    return json.loads(corpo["messages"][1]["content"])["ingredienti"]


async def test_applica_le_figure_dell_elenco(db_session):
    voci = await _voci(db_session, ("carota", "verdura", None), ("mozzarella", "latticini", None))
    finto = FakeLlm(_risposta((1, "carota", "🥕"), (2, "mozzarella", "🧀")))

    esito = await decide_ingredient_emoji(db_session, client=finto)

    assert esito == EmojiRun(applied=2, none=0, refused=0, pending=0, unavailable=None)
    assert await _figura(db_session, voci["carota"]) == "🥕"
    assert await _figura(db_session, voci["mozzarella"]) == "🧀"


async def test_nessuna_si_scrive_e_non_si_richiede(db_session):
    """«nessuna» è una risposta dell'elenco, non un rifiuto: l'ingrediente è deciso, e
    il lancio dopo non lo chiede di nuovo (decisione 22 del piano)."""
    voci = await _voci(db_session, ("sedano", "verdura", None))
    finto = FakeLlm(_risposta((1, "sedano", "nessuna")))

    esito = await decide_ingredient_emoji(db_session, client=finto)

    assert (esito.none, esito.applied, esito.pending) == (1, 0, 0)
    assert await _figura(db_session, voci["sedano"]) == NO_EMOJI


async def test_una_figura_fuori_elenco_non_si_applica(db_session):
    """Lo zenzero di Emoji 15.0 è la prima figura che un modello proporrebbe, ed è
    proprio quella che un telefono vecchio mostra come un quadratino vuoto."""
    voci = await _voci(db_session, ("zenzero", "spezie", None))
    finto = FakeLlm(_risposta((1, "zenzero", "\U0001FADA")))

    esito = await decide_ingredient_emoji(db_session, client=finto)

    assert (esito.refused, esito.applied, esito.pending) == (1, 0, 1)
    assert await _figura(db_session, voci["zenzero"]) is None


async def test_un_numero_non_chiesto_un_nome_che_non_torna_e_un_doppione_non_si_applicano(
    db_session,
):
    """In un lotto di cento un modello piccolo sbaglia riga: il nome accanto al numero
    è quel che lo fa vedere. E di due risposte per lo stesso numero vale la prima."""
    voci = await _voci(db_session, ("carota", "verdura", None), ("sedano", "verdura", None))
    finto = FakeLlm(_risposta(
        (7, "carota", "🥕"),       # 7 non è stato chiesto
        (2, "carota", "🥕"),       # il 2 è il sedano
        (1, "Carota ", "🥕"),      # giusto: maiuscole e spazi ai lati non contano
        (1, "carota", "🥦"),       # doppione del primo
    ))

    esito = await decide_ingredient_emoji(db_session, client=finto)

    assert (esito.applied, esito.refused, esito.pending) == (1, 3, 1)
    assert await _figura(db_session, voci["carota"]) == "🥕"
    assert await _figura(db_session, voci["sedano"]) is None


async def test_senza_selettore_di_variante_si_scrive_la_forma_dell_elenco(db_session):
    voci = await _voci(db_session, ("peperoncino", "spezie", None))
    finto = FakeLlm(_risposta((1, "peperoncino", "\U0001F336")))

    await decide_ingredient_emoji(db_session, client=finto)

    assert await _figura(db_session, voci["peperoncino"]) == "\U0001F336️"


async def test_chi_ha_gia_una_figura_o_nessuna_non_si_chiede(db_session):
    """L'AI scrive solo dove la colonna è vuota: una figura scelta a mano, «Nessuna»
    compresa, non torna al modello. E se non c'è niente da chiedere, non si chiama."""
    voci = await _voci(
        db_session,
        ("carota", "verdura", None),
        ("melanzana", "verdura", "🍆"),
        ("sedano", "verdura", NO_EMOJI),
    )
    finto = FakeLlm(_risposta((1, "carota", "🥕")))

    await decide_ingredient_emoji(db_session, client=finto)

    assert [voce["nome"] for voce in _domanda(finto.bodies[0])] == ["carota"]
    assert await _figura(db_session, voci["melanzana"]) == "🍆"
    assert await _figura(db_session, voci["sedano"]) == NO_EMOJI

    di_nuovo = FakeLlm()
    esito = await decide_ingredient_emoji(db_session, client=di_nuovo)
    assert di_nuovo.bodies == []
    assert esito == EmojiRun()


class _LlmMentreUnaManoCorregge(FakeLlm):
    """Prima di rispondere, qualcuno sceglie una figura in Anagrafica."""

    def __init__(self, mano, *payloads: object) -> None:
        super().__init__(*payloads)
        self._mano = mano

    async def post(self, url, json, headers):  # noqa: A002
        await self._mano()
        return await super().post(url, json, headers)


async def test_una_scelta_a_mano_fatta_mentre_l_ai_risponde_non_si_riscrive(db_session):
    """Il comando può girare minuti; la scelta fatta nel frattempo vince, perché la
    UPDATE che scrive controlla che la colonna sia ancora vuota."""
    voci = await _voci(db_session, ("carota", "verdura", None))

    async def mano():
        await db_session.execute(
            update(Ingredient).where(Ingredient.id == voci["carota"].id).values(emoji="🥦")
        )

    finto = _LlmMentreUnaManoCorregge(mano, _risposta((1, "carota", "🥕")))

    esito = await decide_ingredient_emoji(db_session, client=finto)

    assert esito.applied == 0
    assert await _figura(db_session, voci["carota"]) == "🥦"


async def test_va_a_lotti_e_dopo_ogni_lotto_chiama_after_batch(db_session):
    """Il comando fa commit dopo ogni lotto: un guasto al quinto non butta i primi
    quattro. Ogni lotto numera da 1."""
    await _voci(
        db_session,
        ("aglio", "verdura", None), ("banana", "frutta", None), ("carota", "verdura", None),
    )
    finto = FakeLlm(
        _risposta((1, "aglio", "🧄"), (2, "banana", "🍌")),
        _risposta((1, "carota", "🥕")),
    )
    giri: list[int] = []

    async def dopo():
        giri.append(len(finto.bodies))

    esito = await decide_ingredient_emoji(db_session, client=finto, batch_size=2, after_batch=dopo)

    assert (esito.applied, esito.pending) == (3, 0)
    assert giri == [1, 2]
    assert [[(v["n"], v["nome"]) for v in _domanda(corpo)] for corpo in finto.bodies] == [
        [(1, "aglio"), (2, "banana")],
        [(1, "carota")],
    ]


async def test_l_ai_che_non_risponde_non_scrive_niente_e_lo_dice(db_session):
    voci = await _voci(db_session, ("carota", "verdura", None))
    finto = FakeLlm(httpx.ConnectError("rete giù"))

    esito = await decide_ingredient_emoji(db_session, client=finto)

    assert (esito.applied, esito.pending) == (0, 1)
    assert esito.unavailable is not None and "rete giù" in esito.unavailable
    assert await _figura(db_session, voci["carota"]) is None


async def test_il_primo_guasto_ferma_il_giro(db_session):
    """Dopo un guasto i lotti dopo non si chiedono: sarebbe pagare per sapere che è
    ancora giù. Quel che è già scritto resta."""
    voci = await _voci(
        db_session,
        ("aglio", "verdura", None), ("banana", "frutta", None), ("carota", "verdura", None),
    )
    finto = FakeLlm(_risposta((1, "aglio", "🧄")), httpx.ConnectError("rete giù"))

    esito = await decide_ingredient_emoji(db_session, client=finto, batch_size=1)

    assert len(finto.bodies) == 2
    assert (esito.applied, esito.pending) == (1, 2)
    assert esito.unavailable is not None
    assert await _figura(db_session, voci["aglio"]) == "🧄"


async def test_ogni_chiamata_registra_la_spesa(db_session):
    """Anche quella fallita, come le altre sezioni: una chiamata che non entra in
    `llm_calls` non compare mai nel conto."""
    await _voci(db_session, ("aglio", "verdura", None), ("banana", "frutta", None))
    finto = FakeLlm(_risposta((1, "aglio", "🧄")), httpx.ConnectError("rete giù"))

    await decide_ingredient_emoji(db_session, client=finto, batch_size=1)

    righe = (
        await db_session.execute(select(LlmCall).where(LlmCall.call_site == "ingredient_emoji"))
    ).scalars().all()
    assert sorted(riga.ok for riga in righe) == [False, True]


async def test_la_domanda_porta_numero_nome_e_reparto_e_l_elenco_chiuso(db_session):
    await _voci(db_session, ("carota", "verdura", None))
    finto = FakeLlm(_risposta((1, "carota", "🥕")))

    await decide_ingredient_emoji(db_session, client=finto)

    corpo = finto.bodies[0]
    assert _domanda(corpo) == [{"n": 1, "nome": "carota", "reparto": "verdura"}]
    assert "🥕" in corpo["messages"][0]["content"]
    assert "nessuna" in corpo["messages"][0]["content"]
    schema = corpo["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["emoji"]["items"]["properties"]["emoji"]["enum"] == [
        *INGREDIENT_EMOJI, "nessuna",
    ]
```

- [ ] **Step 2: I test del comando, che falliscono**

Crea `backend/tests/test_decide_emoji_cli.py`:

```python
"""Il comando che fa decidere all'AI le figure degli ingredienti (S12): quel che dice a
chi lo lancia. Il lavoro vero lo provano i test del servizio, con i finti dell'LLM."""

from sqlalchemy import select

from app.cli.decide_emoji import main
from app.db.models.ingredient import Ingredient


class _SessioneFinta:
    """`SessionLocal()` nel test: consegna la sessione della fixture invece di
    aprirne una vera, così `main()` gira contro la stessa transazione annullabile
    che usano tutti gli altri test. Stessa forma di `test_decide_units_cli.py`."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


async def test_un_argomento_qualsiasi_esce_con_errore(capsys):
    """Il comando non ha opzioni: la correzione è in Anagrafica. Un `--azzera` copiato
    da `decide_units` non deve passare per un successo."""
    assert await main(["--azzera"]) == 2
    assert "sconosciuto" in capsys.readouterr().out


async def test_senza_niente_da_decidere_l_ultima_riga_lo_dice(db_session, monkeypatch, capsys):
    db_session.add(Ingredient(name="carota", display_name="Carota", category="verdura", emoji="🥕"))
    await db_session.flush()
    monkeypatch.setattr("app.cli.decide_emoji.SessionLocal", lambda: _SessioneFinta(db_session))

    assert await main([]) == 0

    stampato = capsys.readouterr().out
    assert "nessun ingrediente in attesa" in stampato
    assert "non disponibili" not in stampato


async def test_senza_chiave_dice_quanti_ne_restano_e_non_scrive(db_session, monkeypatch, capsys):
    """La degradazione dichiarata: nessuna chiave, nessuna rete, nessuna scrittura, e
    l'ultima riga dice che c'è ancora del lavoro. È quel che il comando fa sullo stack
    e2e, dove la chiave è vuota (Task 9)."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    try:
        carota = Ingredient(name="carota", display_name="Carota", category="verdura")
        db_session.add(carota)
        await db_session.flush()
        monkeypatch.setattr("app.cli.decide_emoji.SessionLocal", lambda: _SessioneFinta(db_session))

        assert await main([]) == 0

        stampato = capsys.readouterr().out
        assert "figure non disponibili" in stampato
        assert "1 ingrediente resta da decidere" in stampato
        assert (
            await db_session.execute(select(Ingredient.emoji).where(Ingredient.id == carota.id))
        ).scalar_one() is None
    finally:
        get_settings.cache_clear()
```

- [ ] **Step 3: Falliscono**

Run: `TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_s12 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/services/test_ingredient_emoji.py tests/test_decide_emoji_cli.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'app.services.ingredient_emoji'` e `'app.cli.decide_emoji'`.

- [ ] **Step 4: La sezione della spesa**

In `backend/app/services/llm.py`, in `class LlmCallSite(StrEnum)`, dopo `UNIT_FORMS = "unit_forms"` aggiungi:

```python
    INGREDIENT_EMOJI = "ingredient_emoji"
```

- [ ] **Step 5: Il servizio**

Crea `backend/app/services/ingredient_emoji.py`:

```python
"""Chi decide la figura di un ingrediente in Dispensa (S12).

Una volta, per gli ingredienti che non ce l'hanno: `python -m app.cli.decide_emoji`.
L'AI sceglie solo dentro l'elenco chiuso di `app/domain/emoji.py`, a lotti di
`EMOJI_BATCH` nomi. Una risposta che non si può verificare — un numero non chiesto o già
risposto, un nome che non è quello chiesto, un'emoji fuori elenco — non si applica, e la
colonna resta vuota: la riga mostra il ripiego del reparto, e il lancio dopo la richiede.

Scrive solo dove la colonna è `NULL`, e lo controlla nella stessa UPDATE che scrive: una
figura scelta a mano in Anagrafica, «Nessuna» compresa, non si tocca, nemmeno se è stata
scelta mentre il comando girava (bozza §3.A).

Niente `decided_by` e niente undo, a differenza delle decisioni dell'import: l'emoji non
lega niente a niente — non cambia una disponibilità né una ricetta — e sbagliata si
corregge in un tocco, in Anagrafica (bozza §3.A).

I nomi si numerano, e la risposta riporta numero e nome: in un lotto di cento un modello
piccolo può scivolare di una riga, e il nome accanto al numero è ciò che lo fa vedere.
Lo schema stretto restringe l'emoji all'elenco (`enum`); la verifica qui la ripete
comunque, perché uno schema rispettato non è una risposta verificata.
"""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingredient import Ingredient
from app.domain.emoji import INGREDIENT_EMOJI, NO_EMOJI, canonical_emoji
from app.repositories.llm_calls import record_llm_call
from app.services.llm import LlmCallSite, LlmUnavailable, LlmUsage, complete_json

# Cento nomi per chiamata (bozza §3.A: «a lotti di un centinaio di nomi»). Una risposta
# è `{"n": …, "nome": …, "emoji": …}` per nome, ~20 token: duemila per lotto, la metà
# del tetto qui sotto. Sui ~900 ingredienti di produzione sono nove chiamate, qualche
# decina di migliaia di token in tutto: molto sotto il tetto di 1 $/giorno.
EMOJI_BATCH = 100
EMOJI_MAX_TOKENS = 4000

# La parola con cui l'AI dice «nessuna figura dell'elenco va bene». Non è un'emoji, e
# `canonical_emoji` la rifiuta: si traduce in `NO_EMOJI` qui, e solo qui.
NONE_ANSWER = "nessuna"

EMOJI_SYSTEM_PROMPT = (
    "Ricevi un elenco numerato di voci della dispensa di casa: ingredienti e prodotti per "
    "la casa, ciascuno col suo reparto del supermercato. Per ognuna scegli l'emoji che la "
    "fa riconoscere a colpo d'occhio, solo fra queste:\n"
    + " ".join(INGREDIENT_EMOJI)
    + "\n\nRegole:\n"
    '- "n" e "nome" vanno riscritti identici a come te li ho passati.\n'
    "- Va bene un'emoji della stessa famiglia: 🧀 per un formaggio, 🐟 per un pesce, 🥩 "
    "per un taglio di carne.\n"
    f'- Se nessuna emoji dell\'elenco è quella cosa o una della sua famiglia, rispondi "{NONE_ANSWER}": '
    "meglio nessuna figura che una sbagliata.\n"
    "- Una risposta per ogni voce, nessuna in più."
)

EMOJI_SCHEMA = {
    "type": "object",
    "properties": {
        "emoji": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer"},
                    "nome": {"type": "string"},
                    "emoji": {"type": "string", "enum": [*INGREDIENT_EMOJI, NONE_ANSWER]},
                },
                "required": ["n", "nome", "emoji"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["emoji"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class EmojiRun:
    """Quel che un lancio ha fatto, e quel che resta."""

    applied: int = 0  # emoji scritte
    none: int = 0  # «nessuna» scritte
    refused: int = 0  # risposte che non si potevano verificare
    # gli ingredienti ancora `NULL` alla fine: i rifiutati, quelli dei lotti dopo un
    # guasto, tutti quando l'AI non risponde. Senza, «0 scritte» vorrebbe dire insieme
    # «niente da fare» e «è andato tutto storto» (la stessa ragione di `Decided.pending`
    # in `unit_forms.py`)
    pending: int = 0
    # il perché, se l'AI non ha risposto: il comando lo stampa
    unavailable: str | None = None


async def _pending(session: AsyncSession) -> int:
    return (
        await session.execute(
            select(func.count()).select_from(Ingredient).where(Ingredient.emoji.is_(None))
        )
    ).scalar_one()


async def decide_ingredient_emoji(
    session: AsyncSession,
    client: httpx.AsyncClient | None = None,
    batch_size: int = EMOJI_BATCH,
    after_batch: Callable[[], Awaitable[None]] | None = None,
) -> EmojiRun:
    """Chiede all'AI la figura di ogni ingrediente ancora `NULL`, una volta ciascuno.

    Non fa commit: lo fa `after_batch`, se c'è, dopo ogni lotto (il comando passa
    `session.commit`, così un guasto al quinto lotto non butta i primi quattro). Al primo
    guasto dell'AI si ferma: chiedere i lotti dopo sarebbe pagare per sapere che è
    ancora giù.
    """
    rows = (
        await session.execute(
            select(Ingredient.id, Ingredient.name, Ingredient.category)
            .where(Ingredient.emoji.is_(None))
            .order_by(Ingredient.name)
        )
    ).all()
    applied = none = refused = 0
    unavailable: str | None = None

    for start in range(0, len(rows), batch_size):
        asked = {n: row for n, row in enumerate(rows[start : start + batch_size], start=1)}
        question = {
            "ingredienti": [
                {"n": n, "nome": row.name, "reparto": row.category} for n, row in asked.items()
            ]
        }
        try:
            esito = await complete_json(
                call_site=LlmCallSite.INGREDIENT_EMOJI,
                system=EMOJI_SYSTEM_PROMPT,
                user=json.dumps(question, ensure_ascii=False),
                schema=EMOJI_SCHEMA,
                schema_name="figure_ingredienti",
                max_tokens=EMOJI_MAX_TOKENS,
                client=client,
            )
        except LlmUnavailable as exc:
            # mai un vicolo cieco: chi resta `NULL` mostra l'icona del reparto
            await record_llm_call(
                session, call_site=LlmCallSite.INGREDIENT_EMOJI, usage=LlmUsage(), ok=False
            )
            unavailable = str(exc)
            break
        await record_llm_call(
            session, call_site=LlmCallSite.INGREDIENT_EMOJI, usage=esito.usage, ok=True
        )

        answered: set[int] = set()
        for answer in esito.data.get("emoji") or []:
            n = answer.get("n")
            row = asked.get(n) if type(n) is int else None
            name = str(answer.get("nome") or "").strip().casefold()
            if row is None or n in answered or name != row.name.casefold():
                refused += 1
                continue
            answered.add(n)
            value = answer.get("emoji")
            if value == NONE_ANSWER:
                stored: str | None = NO_EMOJI
            else:
                stored = canonical_emoji(value) if isinstance(value, str) else None
            if stored is None:
                refused += 1
                continue
            written = await session.execute(
                update(Ingredient)
                .where(Ingredient.id == row.id, Ingredient.emoji.is_(None))
                .values(emoji=stored)
            )
            if written.rowcount == 1:
                if stored == NO_EMOJI:
                    none += 1
                else:
                    applied += 1
        await session.flush()
        if after_batch is not None:
            await after_batch()

    return EmojiRun(
        applied=applied,
        none=none,
        refused=refused,
        pending=await _pending(session),
        unavailable=unavailable,
    )
```

- [ ] **Step 6: Il comando**

Crea `backend/app/cli/decide_emoji.py`:

```python
"""Fa decidere all'AI la figura degli ingredienti che non ce l'hanno (S12).

    python -m app.cli.decide_emoji

Una volta dopo il deploy di S12, e poi quando si vuole: gli ingredienti nati dopo (a
mano, dall'import, dalla coda) nascono senza figura e mostrano l'icona del reparto finché
questo comando non gira (bozza S12 §5.4). Scrive solo dove la colonna è vuota: una
figura scelta in Anagrafica, «Nessuna» compresa, non si tocca. Non ha opzioni, a
differenza di `decide_units`: una figura sbagliata si corregge in Anagrafica, nella
scheda dell'ingrediente («Cambia figura»).
"""

import asyncio
import sys

from app.core.db import SessionLocal
from app.services.ingredient_emoji import decide_ingredient_emoji


async def main(argv: list[str]) -> int:
    # La guardia esce con codice diverso da zero, non solo stampando: un refuso in uno
    # script che controlla l'exit code non deve passare per un successo.
    if argv:
        print(f"argomento sconosciuto: {argv[0]}")
        return 2

    async with SessionLocal() as session:
        esito = await decide_ingredient_emoji(session, after_batch=session.commit)
        await session.commit()

    if esito.unavailable is not None:
        # Si stampa, non si logga: `app/` non configura nessun logging, e sotto
        # `python -m` una riga a `logger.info` non esce da nessuna parte (la stessa
        # scelta di `unit_forms.py` e `import_gz.py`).
        print(
            f"figure non disponibili ({esito.unavailable}): gli ingredienti senza figura "
            "mostrano l'icona del reparto."
        )
    print(
        f"{esito.applied} figure scritte, {esito.none} ingredienti senza una figura adatta, "
        f"{esito.refused} risposte rifiutate"
    )
    # L'ultima riga dice sempre quanto resta, come `decide_units`: chi mette in
    # produzione legge proprio quella per sapere se deve rilanciare.
    if esito.pending == 1:
        print("1 ingrediente resta da decidere: rilancia questo comando.")
    elif esito.pending:
        print(f"{esito.pending} ingredienti restano da decidere: rilancia questo comando.")
    else:
        print("nessun ingrediente in attesa.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
```

- [ ] **Step 7: Passano, e tutta la suite**

Run: `TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_s12 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q`
Expected: tutto verde, **`N_pytest` + 45** (30 + 12 + 3). Anche `test_llm_spend_is_recorded.py`, che ora trova `services/ingredient_emoji.py` fra i chiamanti dell'LLM e vi trova `record_llm_call`.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/llm.py backend/app/services/ingredient_emoji.py backend/app/cli/decide_emoji.py backend/tests/services/test_ingredient_emoji.py backend/tests/test_decide_emoji_cli.py
git commit -m "feat(ai): S12, decide_emoji — l'AI sceglie la figura degli ingredienti senza, a lotti da 100, solo dall'elenco chiuso e solo sulle colonne vuote"
```

---

### Task 5: La figura nella riga della Dispensa

**Files:**
- Modify: `frontend/src/domain/types.ts` (`PantryItem`)
- Create: `frontend/src/components/IngredientFigure.tsx`, `frontend/src/components/IngredientFigure.test.tsx`
- Modify: `frontend/src/features/pantry/PantryRow.tsx`, `frontend/src/features/pantry/PantryRow.test.tsx`
- Modify: `frontend/src/theme.test.ts` (`MARK_PAIRS`)
- Modify (solo il campo nuovo): ogni test che scrive a mano un `PantryItem` — su `master` `frontend/src/features/pantry/pantryView.test.ts` (la funzione `item`), `frontend/src/features/cooking/CookSheet.test.tsx` (`PANTRY` e `bag`), `frontend/src/features/cooking/RecipeDetailScreen.test.tsx` (`PANTRY`); più quelli che `npm run typecheck` segnala sul ramo (S3)

**Interfaces:**
- Consumes: `PantryItemOut.ingredient_emoji` (Task 3); `departmentStyle` (`frontend/src/components/ui/departments.ts`).
- Produces: `PantryItem.ingredient_emoji: string | null`; `IngredientFigure({ emoji, category, className? }: { emoji: string | null | undefined; category: string | null; className?: string })` in `frontend/src/components/IngredientFigure.tsx`, che disegna un `<span aria-hidden="true" data-figure="emoji" | "reparto">` da 28×28. Il Task 6 lo riusa in Anagrafica; il Task 7 lo trova con `[data-figure]`.

- [ ] **Step 1: I test che falliscono**

1. Crea `frontend/src/components/IngredientFigure.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { IngredientFigure } from "./IngredientFigure";

function figura(container: HTMLElement): HTMLElement {
  return container.querySelector("[data-figure]") as HTMLElement;
}

describe("IngredientFigure (S12)", () => {
  it("con un'emoji mostra l'emoji, ed è nascosta a chi ascolta", () => {
    const { container } = render(<IngredientFigure emoji="🥕" category="verdura" />);
    const el = figura(container);
    expect(el.dataset.figure).toBe("emoji");
    expect(el.textContent).toBe("🥕");
    // senza, uno screen reader leggerebbe «carota Carota» (bozza §3.A)
    expect(el.getAttribute("aria-hidden")).toBe("true");
    expect(el.querySelector("svg")).toBeNull();
  });

  it("senza emoji mostra l'icona del reparto, in grigio e senza la tinta del reparto", () => {
    const { container } = render(<IngredientFigure emoji={null} category="latticini" />);
    const el = figura(container);
    expect(el.dataset.figure).toBe("reparto");
    expect(el.querySelector("svg.tabler-icon-cheese")).not.toBeNull();
    expect(el.className).toContain("text-ink-faint");
    expect(el.className).toContain("bg-page");
    // le tinte dei reparti stanno solo nel titolo della sezione (spec T3 §3.3)
    expect(el.className).not.toMatch(/dept-/);
  });

  it("una risposta senza il campo vale come nessuna emoji", () => {
    const { container } = render(<IngredientFigure emoji={undefined} category="verdura" />);
    expect(figura(container).dataset.figure).toBe("reparto");
    expect(figura(container).querySelector("svg.tabler-icon-carrot")).not.toBeNull();
  });

  it("un reparto sconosciuto ripiega sulla scatola, come i titoli delle sezioni", () => {
    const { container } = render(<IngredientFigure emoji={null} category="inventato" />);
    expect(figura(container).querySelector("svg.tabler-icon-package")).not.toBeNull();
  });
});
```

2. In `frontend/src/features/pantry/PantryRow.test.tsx`:
   - nell'oggetto `BASE`, dopo `expires_on: null, expiry: null,` aggiungi `ingredient_emoji: null,`;
   - dentro `describe("PantryRow", …)`, dopo il test «una voce senza prodotto dice «sfuso»», aggiungi:

```tsx
  it("la figura sta prima del nome: l'emoji dell'ingrediente, nascosta a chi ascolta (S12)", () => {
    renderRow({ ingredient_emoji: "🥛" });
    const figura = document.querySelector("[data-figure]") as HTMLElement;
    expect(figura.dataset.figure).toBe("emoji");
    expect(figura.textContent).toBe("🥛");
    expect(figura.getAttribute("aria-hidden")).toBe("true");
    // il nome accessibile del link non cambia, e la figura viene prima di lui
    const nome = screen.getByRole("link", { name: "Yogurt greco" });
    expect(figura.compareDocumentPosition(nome) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("senza emoji, la figura è l'icona del reparto (S12)", () => {
    renderRow();
    const figura = document.querySelector("[data-figure]") as HTMLElement;
    expect(figura.dataset.figure).toBe("reparto");
    expect(figura.querySelector("svg.tabler-icon-cheese")).not.toBeNull();
  });
```

3. In `frontend/src/theme.test.ts`, la costante
   ```ts
   const MARK_PAIRS: [string, string][] = [["notch-off", "card"]];
   ```
   diventa
   ```ts
   const MARK_PAIRS: [string, string][] = [
     ["notch-off", "card"],
     // il ripiego della figura di una riga in Dispensa (S12): l'icona del reparto in
     // `ink-faint` sul quadratino `page`. Come testo sta già sopra 4,5:1 (PAIRS); qui si
     // dice che per lei la soglia è quella di un segno
     ["ink-faint", "page"],
   ];
   ```
   Se sul ramo `MARK_PAIRS` ha già altre coppie, aggiungi la tua in coda senza toccarle.

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/components/IngredientFigure.test.tsx src/features/pantry/PantryRow.test.tsx src/theme.test.ts`
Expected: FAIL — `IngredientFigure.test.tsx` non trova il modulo `./IngredientFigure`; in `PantryRow.test.tsx` i due test nuovi non trovano `[data-figure]` (`Cannot read properties of null`). `theme.test.ts` passa già (la coppia regge): va bene, è una dichiarazione.

- [ ] **Step 3: Il tipo, il componente, la riga**

1. In `frontend/src/domain/types.ts`, in `export interface PantryItem`, dopo il campo `expiry: ExpiryState | null;` (e il suo commento) aggiungi:
   ```ts
     /** La figura della riga (S12): l'emoji dell'ingrediente, `null` per il ripiego
      * sull'icona del reparto. La decide il server (l'AI o una persona in Anagrafica): qui
      * si mostra e basta. */
     ingredient_emoji: string | null;
   ```
2. Crea `frontend/src/components/IngredientFigure.tsx`:

```tsx
import { departmentStyle } from "./ui/departments";

/** La figura di un ingrediente (S12, bozza §3.A): la sua emoji su un quadratino da 28 px,
 * o, dove non ce l'ha, l'icona del suo reparto in `ink-faint`. Monocroma e senza la tinta
 * del reparto: le tinte stanno solo nel titolo della sezione (spec T3 §3.3), e su una
 * riga si confonderebbero coi colori degli stati.
 *
 * Il fondo `page` sul `card` della sezione sta a 1,11:1 di proposito: è un appoggio, non
 * un bordo che dice qualcosa. Il ripiego sta sopra 3:1 sul suo fondo (`theme.test.ts`,
 * misurato anche nel browser da `e2e/style.spec.ts`).
 *
 * `aria-hidden`: il nome è già scritto accanto, e «formaggio Mozzarella» letto a voce
 * è rumore. `data-figure` dice quale delle due si vede, per le prove.
 *
 * Sta in `components/` e non in `features/pantry/` perché la usa anche l'Anagrafica,
 * dove la figura si corregge. */
export function IngredientFigure({
  emoji,
  category,
  className = "",
}: {
  emoji: string | null | undefined;
  category: string | null;
  className?: string;
}) {
  const { icon: Icon } = departmentStyle(category);
  return (
    <span
      aria-hidden="true"
      data-figure={emoji ? "emoji" : "reparto"}
      className={`flex size-7 shrink-0 items-center justify-center rounded-lg bg-page text-ink-faint ${className}`}
    >
      {emoji ? (
        <span className="text-lg leading-none">{emoji}</span>
      ) : (
        <Icon className="size-4.5" stroke={1.8} />
      )}
    </span>
  );
}
```

3. In `frontend/src/features/pantry/PantryRow.tsx` (leggilo com'è sul ramo):
   - in cima, accanto agli altri import da `../../components/`, aggiungi:
     ```tsx
     import { IngredientFigure } from "../../components/IngredientFigure";
     ```
   - nel JSX, il primo `<div className="flex items-center gap-1">` dentro `<li ref={ref} className="scroll-mt-16">`: come **primo figlio** di quel `div`, prima del commento che comincia con `{/* Il prodotto sta su una riga sola`, metti:
     ```tsx
             {/* La figura (S12): l'emoji dell'ingrediente o l'icona del reparto, per
                 riconoscere la riga senza leggerla. 28 px più `mr-1` e il `gap-1` della
                 riga: il nome comincia 36 px più in là, e la scadenza sotto rientra
                 altrettanto */}
             <IngredientFigure
               emoji={item.ingredient_emoji}
               category={item.ingredient_category}
               className="mr-1"
             />
     ```
   - nel commento che comincia con `{/* Il prodotto sta su una riga sola, tagliato coi puntini: accanto alle tacche` sostituisci `restano 135px a 375px di larghezza` con `restano 99px a 375px di larghezza (135 prima della figura di S12)`;
   - nella `className` del `<Link to={registryPath(item)} …>`, dopo `font-medium` aggiungi ` break-words` (il nome va a capo anche con una parola lunga, invece di spingere le tacche);
   - il `div` della scadenza, `<div className="flex min-h-11 items-start text-xs text-ink-faint">`, diventa `<div className="flex min-h-11 items-start pl-9 text-xs text-ink-faint">`, e nel commento sopra di lui (`{/* La scadenza ha la sua riga, larga quanto la voce: …`) aggiungi in coda: ` Rientra di 36 px (pl-9) per cominciare sotto il nome e non sotto la figura (S12).`
4. **Il campo nuovo negli oggetti scritti a mano.** Run (da `<worktree>/frontend`): `npm run typecheck`. Expected: errori `TS2741`/`TS2739` «Property 'ingredient_emoji' is missing» nei test che costruiscono un `PantryItem`. In ciascuno aggiungi `ingredient_emoji: null` all'oggetto, accanto a `expiry: null` — su `master` sono: `pantryView.test.ts` (nel `return` della funzione `item`), `CookSheet.test.tsx` (le cinque voci di `PANTRY` e l'oggetto di `bag`), `RecipeDetailScreen.test.tsx` (le due voci di `PANTRY`); sul ramo forse anche test di S3. Nessun'altra modifica a quei test. Rilancia `npm run typecheck` finché non è pulito.

- [ ] **Step 4: Passano, e tutto il frontend**

Run (da `<worktree>/frontend`):
```bash
npx vitest run
npm run typecheck
npm run lint
```
Expected: vitest tutto verde, **`N_vitest` + 8** (4 + 2 + 2) in **`N_file` + 1** file; typecheck e lint puliti.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/domain/types.ts frontend/src/components/IngredientFigure.tsx frontend/src/components/IngredientFigure.test.tsx frontend/src/features/pantry/PantryRow.tsx frontend/src/features/pantry/PantryRow.test.tsx frontend/src/theme.test.ts
git add -u frontend/src
git commit -m "feat(dispensa): S12, la figura a sinistra del nome — l'emoji dell'ingrediente o l'icona del reparto in grigio"
```

---

### Task 6: «Cambia figura» in Anagrafica

**Files:**
- Create: `frontend/src/domain/emoji.ts`
- Create: `backend/tests/test_frontend_emoji.py`
- Modify: `frontend/src/domain/types.ts` (`IngredientDetail`, `RegistryRefusal`)
- Modify: `frontend/src/components/ui/icons.ts` (l'export «anagrafica»)
- Modify: `frontend/src/features/registry/api.ts` (`patchIngredient`)
- Create: `frontend/src/features/registry/EmojiForm.tsx`
- Modify: `frontend/src/features/registry/IngredientScreen.tsx`, `frontend/src/features/registry/IngredientScreen.test.tsx`

**Interfaces:**
- Consumes: `INGREDIENT_EMOJI` del backend (Task 1); `IngredientDetailOut.emoji`, la `PATCH` con `emoji`, il rifiuto `unknown_emoji` (Task 3); `IngredientFigure` (Task 5).
- Produces: `INGREDIENT_EMOJI` in `frontend/src/domain/emoji.ts`; `IngredientDetail.emoji: string | null`; `patchIngredient(id, body: { name?: string; category?: string; emoji?: string | null })`; `EmojiForm({ ingredient, onDone })`; `IconMoodSmile` da `icons.ts`. Il Task 7 usa le parole a video di qui.

- [ ] **Step 1: La copia dell'elenco, e la sua guardia (il test fallisce)**

Crea `backend/tests/test_frontend_emoji.py`:

```python
"""Le figure che la griglia dell'Anagrafica offre devono essere quelle che il backend
accetta, nello stesso ordine (S12).

Come `test_frontend_categories.py`: una figura offerta dal frontend e sconosciuta al
backend tornerebbe un 409 su una scelta che sembrava valida; una che il backend conosce
e la griglia no non si potrebbe mai scegliere a mano. L'ordine conta anche lui: è quello
delle famiglie della griglia, e la copia deve dire la stessa cosa dell'originale. Il
confronto è carattere per carattere: una copia che perdesse il selettore di variante di
🌶️ sembrerebbe giusta a occhio.
"""

import re
from pathlib import Path

from app.domain.emoji import INGREDIENT_EMOJI

REPO_ROOT = Path(__file__).resolve().parents[2]
EMOJI_TS = REPO_ROOT / "frontend" / "src" / "domain" / "emoji.ts"


def test_il_frontend_offre_le_figure_del_backend_nello_stesso_ordine():
    contenuto = EMOJI_TS.read_text(encoding="utf-8")
    blocco = re.search(r"export const INGREDIENT_EMOJI = \[(.*?)\] as const", contenuto, re.DOTALL)
    assert blocco is not None, f"{EMOJI_TS}: manca la costante INGREDIENT_EMOJI"
    assert re.findall(r'"([^"]+)"', blocco.group(1)) == list(INGREDIENT_EMOJI)
```

Run (da `<worktree>/backend`): `TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_s12 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/test_frontend_emoji.py`
Expected: FAIL, `FileNotFoundError` su `frontend/src/domain/emoji.ts`.

Crea `frontend/src/domain/emoji.ts` (le stesse emoji del Task 1, carattere per carattere, nello stesso ordine; i commenti dentro l'array senza virgolette doppie, perché la guardia le leggerebbe come voci):

```ts
/** Le figure che un ingrediente può avere in Dispensa (S12), nell'ordine della griglia di
 * «Cambia figura» in Anagrafica.
 *
 * È una copia di `INGREDIENT_EMOJI` in `backend/app/domain/emoji.py`, che è l'originale e
 * dice perché l'elenco è chiuso e fermo a Emoji 14.0; `backend/tests/test_frontend_emoji.py`
 * le confronta voce per voce. Il frontend non decide niente con questo elenco: lo offre da
 * scegliere, e il server verifica la scelta.
 */
export const INGREDIENT_EMOJI = [
  // frutta
  "🍇", "🍈", "🍉", "🍊", "🍋", "🍌", "🍍", "🥭", "🍎", "🍏", "🍐", "🍑", "🍒", "🍓", "🫐",
  "🥝", "🍅", "🫒", "🥥",
  // verdura, legumi, frutta secca, erbe
  "🥑", "🍆", "🥔", "🥕", "🌽", "🌶️", "🫑", "🥒", "🥬", "🥦", "🧄", "🧅", "🍄", "🥜", "🫘",
  "🌰", "🌿", "🌱", "🌾",
  // pane e forno
  "🍞", "🥐", "🥖", "🫓", "🥨", "🥯", "🥞", "🧇",
  // formaggi, carne, uova, piatti
  "🧀", "🍖", "🍗", "🥩", "🥓", "🍔", "🍟", "🍕", "🌭", "🥪", "🌮", "🌯", "🫔", "🥙", "🧆",
  "🥚", "🍳", "🥘", "🍲", "🫕", "🥣", "🥗", "🍿", "🧈", "🧂", "🥫",
  // cucina asiatica
  "🍱", "🍘", "🍙", "🍚", "🍛", "🍜", "🍝", "🍠", "🍢", "🍣", "🍤", "🍥", "🥮", "🍡", "🥟",
  "🥠", "🥡",
  // pesce e mare
  "🦀", "🦞", "🦐", "🦑", "🦪", "🐟", "🐙", "🐚",
  // dolci
  "🍦", "🍧", "🍨", "🍩", "🍪", "🎂", "🍰", "🧁", "🥧", "🍫", "🍬", "🍭", "🍮", "🍯",
  // bevande e barattoli
  "🍼", "🥛", "☕", "🫖", "🍵", "🍶", "🍾", "🍷", "🍸", "🍹", "🍺", "🥂", "🥃", "🫗", "🥤",
  "🧋", "🧃", "🧉", "🧊", "🫙",
  // casa e igiene
  "🧻", "🧽", "🧴", "🧼", "🪥", "🪒", "🧹", "🧺", "🪣", "🧤", "🧷", "🩹", "💊", "🕯️", "💡",
  "🔋", "🗑️",
] as const;
```

Il modo più sicuro di copiare le voci è generarle dall'originale, e incollare il risultato fra le due righe dell'array:
```bash
cd <worktree>/backend && PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -c 'from app.domain.emoji import INGREDIENT_EMOJI as E; print(len(E)); print(", ".join(chr(34)+e+chr(34) for e in E))'
```

Run di nuovo il test della guardia. Expected: PASS.

- [ ] **Step 2: I test della scheda, che falliscono**

In `frontend/src/features/registry/IngredientScreen.test.tsx`:

1. In cima, aggiungi `import { INGREDIENT_EMOJI } from "../../domain/emoji";`.
2. Nell'oggetto `POMODORI`, dopo `kind: "food",` aggiungi `emoji: null,`; in `POMODORO_SCHEDA`, dopo `...POMODORO,` aggiungi `emoji: null,`.
3. In fondo al file aggiungi:

```tsx
describe("la figura in dispensa (S12)", () => {
  const CON_POMODORO: IngredientDetail = { ...POMODORI, emoji: "🍅" };

  /** La scheda di «pomodori» com'è in `detail`; la PATCH risponde con `patch`, o con la
   * scheda e la figura mandata. */
  function scheda(detail: IngredientDetail, patch?: () => [unknown, number]) {
    return stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH" && path.endsWith("/ingredients/i-pomodori")) {
        const body = JSON.parse(String(init.body)) as { emoji: string | null };
        return patch ? patch() : [{ ...detail, emoji: body.emoji }, 200];
      }
      if (path.endsWith("/ingredients/i-pomodori")) return [detail, 200];
      return base(path) ?? [{}, 404];
    });
  }

  function corpoDellaPatch(spy: ReturnType<typeof stubRoutedFetch>) {
    const [, init] = callsTo(spy, "PATCH", "/ingredients/i-pomodori")[0];
    return JSON.parse(String((init as RequestInit).body));
  }

  it("la scheda dice la figura delle sue righe in dispensa: senza, l'icona del reparto", async () => {
    scheda(POMODORI);
    renderAt("/anagrafica/ingrediente/i-pomodori");

    expect(await screen.findByText("In dispensa: l'icona del reparto")).toBeInTheDocument();
    const figura = document.querySelector("[data-figure]") as HTMLElement;
    expect(figura.dataset.figure).toBe("reparto");
    expect(figura.querySelector("svg.tabler-icon-carrot")).not.toBeNull();
  });

  it("con un'emoji, la scheda la mostra", async () => {
    scheda(CON_POMODORO);
    renderAt("/anagrafica/ingrediente/i-pomodori");

    expect(await screen.findByText("In dispensa")).toBeInTheDocument();
    expect((document.querySelector("[data-figure]") as HTMLElement).textContent).toBe("🍅");
  });

  it("«Cambia figura» apre l'elenco chiuso con «Nessuna», e la scelta va al server", async () => {
    const spy = scheda(POMODORI);
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Cambia figura" }));
    const gruppo = screen.getByRole("group", { name: "Figura in dispensa" });
    expect(within(gruppo).getAllByRole("radio")).toHaveLength(INGREDIENT_EMOJI.length + 1);
    expect(within(gruppo).getByRole("radio", { name: "Nessuna: l'icona del reparto" })).toBeChecked();

    await userEvent.click(within(gruppo).getByRole("radio", { name: "🍅" }));
    await userEvent.click(screen.getByRole("button", { name: "Salva la figura" }));

    await waitFor(() => expect(callsTo(spy, "PATCH", "/ingredients/i-pomodori")).toHaveLength(1));
    expect(corpoDellaPatch(spy)).toEqual({ emoji: "🍅" });
    await waitFor(() =>
      expect(screen.queryByRole("group", { name: "Figura in dispensa" })).toBeNull()
    );
  });

  it("«Nessuna» manda null", async () => {
    const spy = scheda(CON_POMODORO);
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Cambia figura" }));
    const gruppo = screen.getByRole("group", { name: "Figura in dispensa" });
    expect(within(gruppo).getByRole("radio", { name: "🍅" })).toBeChecked();
    await userEvent.click(within(gruppo).getByRole("radio", { name: "Nessuna: l'icona del reparto" }));
    await userEvent.click(screen.getByRole("button", { name: "Salva la figura" }));

    await waitFor(() => expect(callsTo(spy, "PATCH", "/ingredients/i-pomodori")).toHaveLength(1));
    expect(corpoDellaPatch(spy)).toEqual({ emoji: null });
  });

  it("la figura che ha già non si salva di nuovo, e dice perché", async () => {
    const spy = scheda(CON_POMODORO);
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Cambia figura" }));
    const salva = screen.getByRole("button", { name: "Salva la figura" });
    expect(salva).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText("È già la sua figura: scegline un'altra.")).toBeInTheDocument();

    await userEvent.click(salva);
    expect(callsTo(spy, "PATCH", "/ingredients/i-pomodori")).toHaveLength(0);
  });

  it("un rifiuto del server si legge col suo perché, e il pannello resta aperto", async () => {
    const detail = "«🍅» non è fra le figure che l'app mostra: scegline una dell'elenco.";
    scheda(POMODORI, () => [{ code: "unknown_emoji", detail }, 409]);
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Cambia figura" }));
    await userEvent.click(screen.getByRole("radio", { name: "🍅" }));
    await userEvent.click(screen.getByRole("button", { name: "Salva la figura" }));

    expect(await screen.findByText(detail)).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Figura in dispensa" })).toBeInTheDocument();
  });

  it("un guasto lo dice, e il pannello resta aperto", async () => {
    scheda(POMODORI, () => [{ detail: "guasto" }, 500]);
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Cambia figura" }));
    await userEvent.click(screen.getByRole("radio", { name: "🍅" }));
    await userEvent.click(screen.getByRole("button", { name: "Salva la figura" }));

    expect(
      await screen.findByText("Non sono riuscito a cambiare la figura. Riprova.")
    ).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Figura in dispensa" })).toBeInTheDocument();
  });

  it("«Lascia com'è» chiude senza scrivere", async () => {
    const spy = scheda(POMODORI);
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Cambia figura" }));
    await userEvent.click(screen.getByRole("radio", { name: "🍅" }));
    await userEvent.click(screen.getByRole("button", { name: "Lascia com'è" }));

    expect(screen.queryByRole("group", { name: "Figura in dispensa" })).toBeNull();
    expect(screen.getByRole("button", { name: "Cambia figura" })).toBeInTheDocument();
    expect(callsTo(spy, "PATCH", "/ingredients/i-pomodori")).toHaveLength(0);
  });
});
```

Run (da `<worktree>/frontend`): `npx vitest run src/features/registry/IngredientScreen.test.tsx`
Expected: FAIL — gli otto test nuovi non trovano «In dispensa…» né «Cambia figura»; i test di prima passano.

- [ ] **Step 3: Tipi, icona, api**

1. In `frontend/src/domain/types.ts`:
   - in `export interface IngredientDetail extends Ingredient`, prima di `aliases: AliasEntry[];` aggiungi:
     ```ts
       /** La figura delle sue righe in Dispensa (S12): un'emoji, o `null` per l'icona del
        * reparto. Solo nella scheda: la ricerca non la porta. */
       emoji: string | null;
     ```
   - in `export type RegistryRefusal`, nell'ultimo ramo, l'elenco dei codici `| "same_ingredient" | "empty_name" | "unknown_category" | "still_used" | "bad_checksum"` prende in coda `| "unknown_emoji"`.
2. In `frontend/src/components/ui/icons.ts`, nel blocco `// anagrafica`, aggiungi `IconMoodSmile,` dopo `IconBarcodeOff,`.
3. In `frontend/src/features/registry/api.ts`, la funzione `patchIngredient` diventa:
   ```ts
   /** `name` rinomina (nome e nome a video insieme), `category` cambia reparto, `emoji`
    * cambia la figura in Dispensa (S12): `null` è «Nessuna», l'icona del reparto. */
   export function patchIngredient(
     id: string,
     body: { name?: string; category?: string; emoji?: string | null }
   ) {
     return apiFetch<IngredientDetail>(`/ingredients/${id}`, {
       method: "PATCH",
       body: JSON.stringify(body),
     });
   }
   ```

- [ ] **Step 4: Il pannello**

Crea `frontend/src/features/registry/EmojiForm.tsx`:

```tsx
import { useId, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { IngredientFigure } from "../../components/IngredientFigure";
import { INGREDIENT_EMOJI } from "../../domain/emoji";
import type { IngredientDetail } from "../../domain/types";
import { patchIngredient, refreshAfterCorrection, registryRefusal } from "./api";

const CHOSEN = "bg-brand-tint ring-2 ring-brand ring-inset";

/** «Cambia figura» (S12, bozza §3.A): la figura delle righe di questo ingrediente in
 * Dispensa, scelta dall'elenco chiuso, o «Nessuna», che lascia l'icona del reparto.
 *
 * Una griglia di radio veri e non un `<select>`: una figura si sceglie guardandola, e un
 * menu nativo ne mostrerebbe una per riga, in piccolo, su 148 righe. Il radio nascosto dà
 * la selezione singola e le frecce della tastiera, come in `MissingBudgetFilter`; il nome
 * accessibile di ciascuno è l'emoji, che uno screen reader legge col suo nome («carota»).
 *
 * «Nessuna» si salva anche quando la scheda mostra già il ripiego: senza figura può voler
 * dire «non ancora decisa», e allora l'AI la deciderebbe al prossimo giro. Salvata a mano,
 * l'AI non la tocca più (`set_ingredient_emoji` nel servizio dell'anagrafica). */
export function EmojiForm({
  ingredient,
  onDone,
}: {
  ingredient: IngredientDetail;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const group = useId();
  const [choice, setChoice] = useState<string | null>(ingredient.emoji);
  const save = useMutation({
    mutationFn: (next: string | null) => patchIngredient(ingredient.id, { emoji: next }),
    onSuccess: async () => {
      // anche la dispensa: è lì che la figura si vede
      await refreshAfterCorrection(queryClient);
      onDone();
    },
  });
  const refusal = registryRefusal(save.error);
  const unchanged = choice !== null && choice === ingredient.emoji;

  return (
    <Card as="section" className="mt-2 flex flex-col gap-3">
      <fieldset>
        <legend className="pb-1.5 text-sm font-medium text-ink-soft">Figura in dispensa</legend>
        <label className="flex">
          <input
            type="radio"
            name={group}
            className="peer sr-only"
            checked={choice === null}
            onChange={() => setChoice(null)}
          />
          <span
            className={`flex min-h-11 flex-1 items-center gap-3 rounded-lg px-2 text-sm peer-focus-visible:ring-2 peer-focus-visible:ring-brand ${
              choice === null ? CHOSEN : ""
            }`}
          >
            <IngredientFigure emoji={null} category={ingredient.category} />
            Nessuna: l'icona del reparto
          </span>
        </label>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(2.75rem,1fr))] justify-items-center gap-1 pt-2">
          {INGREDIENT_EMOJI.map((emoji) => (
            <label key={emoji}>
              <input
                type="radio"
                name={group}
                className="peer sr-only"
                checked={choice === emoji}
                onChange={() => setChoice(emoji)}
              />
              <span
                className={`flex size-11 items-center justify-center rounded-lg text-2xl leading-none peer-focus-visible:ring-2 peer-focus-visible:ring-brand ${
                  choice === emoji ? CHOSEN : "bg-page"
                }`}
              >
                {emoji}
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      {/* in colonna, come «Cambia reparto»: il perché sta attaccato a «Salva la figura» */}
      <div className="flex flex-col items-start gap-2">
        <Button
          variant="primary"
          busy={save.isPending}
          unavailableReason={unchanged ? "È già la sua figura: scegline un'altra." : undefined}
          onClick={() => save.mutate(choice)}
        >
          Salva la figura
        </Button>
        <Button variant="ghost" onClick={onDone}>
          Lascia com'è
        </Button>
      </div>
      {refusal !== null && <Alert>{refusal.detail}</Alert>}
      {save.isError && refusal === null && (
        <Alert>Non sono riuscito a cambiare la figura. Riprova.</Alert>
      )}
    </Card>
  );
}
```

- [ ] **Step 5: La scheda**

In `frontend/src/features/registry/IngredientScreen.tsx` (leggilo com'è sul ramo):

1. Import: aggiungi `IconMoodSmile` all'import da `../../components/ui/icons`; aggiungi
   ```tsx
   import { IngredientFigure } from "../../components/IngredientFigure";
   import { EmojiForm } from "./EmojiForm";
   ```
2. Il tipo `Panel` prende un ramo in più: dopo `| { kind: "category" }` aggiungi `| { kind: "emoji" }`.
3. Nel JSX di `IngredientCard`, subito **prima** di `<SectionHeading>Alias</SectionHeading>` (dopo il blocco `{panel?.kind === "merge" && (…)}`), aggiungi:

```tsx
      {/* La figura delle sue righe in Dispensa (S12): si vede qui, e qui si corregge. Il
          pannello prende il posto della riga — un pannello solo alla volta, come gli
          altri — e non è una quarta icona accanto al titolo, che a 375 px lo
          stringerebbe e non mostrerebbe la figura attuale senza aprire niente */}
      {panel?.kind === "emoji" ? (
        <EmojiForm ingredient={ingredient} onDone={() => setPanel(null)} />
      ) : (
        <Card className="mt-2 flex items-center gap-3">
          <IngredientFigure emoji={ingredient.emoji} category={ingredient.category} />
          <p className="min-w-0 flex-1 text-sm text-ink-soft">
            {ingredient.emoji ? "In dispensa" : "In dispensa: l'icona del reparto"}
          </p>
          <Button variant="secondary" icon={IconMoodSmile} onClick={() => setPanel({ kind: "emoji" })}>
            Cambia figura
          </Button>
        </Card>
      )}
```

- [ ] **Step 6: Passano, e tutto il frontend**

Run (da `<worktree>/frontend`):
```bash
npx vitest run
npm run typecheck
npm run lint
npm run build
```
Expected: vitest tutto verde, **`N_vitest` + 16** (8 del Task 5 + 8) in **`N_file` + 1** file; typecheck, lint e build puliti. Se `npm run typecheck` segnala un altro `IngredientDetail` scritto a mano senza `emoji`, aggiungi `emoji: null` lì (e scrivilo nel report).

Da `<worktree>/backend`: `TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_s12 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q`
Expected: tutto verde, **`N_pytest` + 46**.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/domain/emoji.ts backend/tests/test_frontend_emoji.py frontend/src/domain/types.ts frontend/src/components/ui/icons.ts frontend/src/features/registry/api.ts frontend/src/features/registry/EmojiForm.tsx frontend/src/features/registry/IngredientScreen.tsx frontend/src/features/registry/IngredientScreen.test.tsx
git commit -m "feat(anagrafica): S12, «Cambia figura» — la griglia dell'elenco chiuso e «Nessuna», nella scheda dell'ingrediente"
```

---

### Task 7: L'e2e — la riga a 375 px nei due temi, e la figura scelta in Anagrafica

jsdom non calcola il CSS (quarta lezione di `CLAUDE.md`): che la figura sia davvero 28×28, che il nome più lungo vada a capo senza spingere fuori tacche e ✕, che la scadenza cominci sotto il nome, che il ripiego regga 3:1 sul suo fondo nei due temi e che niente scorra di lato lo dice solo un browser. Le due prove mettono in dispensa una voce con `page.request` (il seme non popola la dispensa) e la tolgono nel `finally`, come le altre di questo file: il file non lascia niente dietro di sé. L'unica traccia è la figura di «melanzana», che in fondo torna «Nessuna»: a video identica a prima, nella colonna la stringa vuota invece di `NULL`, che nessuna prova legge.

**Files:**
- Modify: `frontend/e2e/style.spec.ts` (tre aiuti e due `test(...)` in fondo, in un blocco proprio)

- [ ] **Step 1: I test**

In fondo a `frontend/e2e/style.spec.ts` aggiungi (il `beforeEach` del file ha già fatto l'accesso; `fermo`, `testiIlleggibili`, `contrastoAVideo`, `tokenDelTema`, `tokenDelTemaScuro` sono definiti più sopra nel file; se sul ramo uno dei tre nomi nuovi qui sotto c'è già, rinomina il tuo):

```ts
// --- S12: le righe della dispensa riconoscibili ---

/** Un ingrediente del seme, per nome, dalla ricerca vera. */
async function dalSeme(page: Page, nome: string): Promise<{ id: string; name: string }> {
  const risposta = await page.request.get(`/api/v1/ingredients/search?q=${encodeURIComponent(nome)}`);
  expect(risposta.ok()).toBe(true);
  const trovati = (await risposta.json()) as { id: string; name: string }[];
  const voce = trovati.find((trovato) => trovato.name === nome);
  expect(voce, `«${nome}» non è nel seme`).toBeDefined();
  return voce!;
}

/** Una voce sfusa in dispensa, messa con `page.request`; chi la chiede la toglie nel suo
 * `finally` con `togliDallaDispensa`. */
async function inDispensa(page: Page, ingredientId: string): Promise<string> {
  const risposta = await page.request.post("/api/v1/pantry", { data: { ingredient_id: ingredientId } });
  expect(risposta.ok()).toBe(true);
  return ((await risposta.json()) as { id: string }).id;
}

async function togliDallaDispensa(page: Page, voceId: string) {
  await page.request.patch(`/api/v1/pantry/${voceId}`, { data: { archived: true } });
}

test("S12 a 375px: la figura a sinistra del nome, il ripiego del reparto si legge nei due temi, e il nome più lungo del seme va a capo senza spingere fuori tacche e ✕", async ({
  page,
}) => {
  // il `beforeEach` tocca «Entra» ma non aspetta la risposta, e la prima cosa qui è una
  // `page.request`: l'attesa va messa a mano
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  // il nome più lungo del seme, e nessun altro file della suite lo nomina. Il seme non
  // decide figure, quindi la riga mostra il ripiego: lo spruzzino di «casa», in grigio
  const detersivo = await dalSeme(page, "detersivo per la lavatrice");
  const voceId = await inDispensa(page, detersivo.id);
  try {
    await page.goto("/dispensa");
    const togli = page.getByRole("button", { name: "Togli detersivo per la lavatrice dalla dispensa" });
    const riga = page.getByRole("listitem").filter({ has: togli });
    await riga.scrollIntoViewIfNeeded();

    const figura = riga.locator("[data-figure]");
    await expect(figura).toHaveAttribute("data-figure", "reparto");
    await expect(figura).toHaveAttribute("aria-hidden", "true");
    await expect(figura.locator("svg.tabler-icon-spray")).toHaveCount(1);
    const boxFigura = (await figura.boundingBox())!;
    expect(boxFigura.width).toBe(28);
    expect(boxFigura.height).toBe(28);

    // a sinistra del nome, e il nome va a capo invece di spingere le tacche
    const nome = riga.getByRole("link", { name: "Detersivo per la lavatrice" });
    const boxNome = (await nome.boundingBox())!;
    expect(boxFigura.x + boxFigura.width, "la figura e il nome si sovrappongono").toBeLessThanOrEqual(
      boxNome.x
    );
    expect(boxNome.height, "il nome lungo non va a capo: la prova non misura niente").toBeGreaterThan(44);
    for (const tacca of await riga.getByRole("radio").all()) {
      await expect(tacca).toBeInViewport({ ratio: 1 });
    }
    await expect(togli).toBeInViewport({ ratio: 1 });

    // la scadenza comincia sotto il nome, non sotto la figura
    const scadenza = riga.getByRole("button", { name: "+ scadenza per detersivo per la lavatrice" });
    const boxScadenza = (await scadenza.boundingBox())!;
    expect(Math.abs(boxScadenza.x - boxNome.x), "la scadenza non è allineata al nome").toBeLessThanOrEqual(1);

    for (const tema of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: tema });
      await fermo(page);
      const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
      const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
      expect(scrollWidth, `la dispensa scorre di lato, tema ${tema}`).toBeLessThanOrEqual(clientWidth);

      // il ripiego è un segno (WCAG 1.4.11): `ink-faint` sul quadratino `page`, ≥ 3:1
      const misura = await contrastoAVideo(figura);
      const token = tema === "light" ? tokenDelTema : tokenDelTemaScuro;
      expect(misura.colore, `il ripiego non è ink-faint, tema ${tema}`).toBe(token("ink-faint"));
      expect(misura.fondo, `il quadratino non è page, tema ${tema}`).toBe(token("page"));
      test.info().annotations.push({
        type: "contrasto",
        description: `ripiego della figura su page, ${tema}: ${misura.rapporto.toFixed(2)}:1`,
      });
      expect(misura.rapporto, `il ripiego su --color-page, tema ${tema}`).toBeGreaterThanOrEqual(3);
      expect(await testiIlleggibili(page), `dispensa, tema ${tema}`).toEqual([]);
    }
    await page.emulateMedia({ colorScheme: "light" });
  } finally {
    await togliDallaDispensa(page, voceId);
  }
});

test("S12: la figura si sceglie in Anagrafica e compare nella riga della Dispensa; «Nessuna» torna all'icona del reparto", async ({
  page,
}) => {
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  // «melanzana»: nessun altro file della suite la nomina
  const melanzana = await dalSeme(page, "melanzana");
  const voceId = await inDispensa(page, melanzana.id);
  const figuraInDispensa = () =>
    page
      .getByRole("listitem")
      .filter({ has: page.getByRole("button", { name: "Togli melanzana dalla dispensa" }) })
      .locator("[data-figure]");

  /** Dalla scheda dell'ingrediente: «Cambia figura», la scelta, «Salva la figura». La
   * prima volta misura anche la griglia aperta: a 375 px non scorre di lato, e ogni
   * testo si legge nei due temi. */
  async function scegli(voce: string, misura: boolean) {
    await page.goto(`/anagrafica/ingrediente/${melanzana.id}`);
    await page.getByRole("button", { name: "Cambia figura", exact: true }).click();
    const gruppo = page.getByRole("group", { name: "Figura in dispensa" });
    // si tocca il riquadro che si vede, non il radio nascosto: è quel che fa il pollice
    await gruppo.locator("label").filter({ hasText: voce }).click();
    await expect(gruppo.getByRole("radio", { name: voce, exact: true })).toBeChecked();
    if (misura) {
      for (const tema of ["light", "dark"] as const) {
        await page.emulateMedia({ colorScheme: tema });
        await fermo(page);
        const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
        const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
        expect(scrollWidth, `la griglia scorre di lato, tema ${tema}`).toBeLessThanOrEqual(clientWidth);
        expect(await testiIlleggibili(page), `«Cambia figura», tema ${tema}`).toEqual([]);
      }
      await page.emulateMedia({ colorScheme: "light" });
      // i riquadri sono bersagli da pollice
      const riquadro = (await gruppo.locator("label").filter({ hasText: "🥕" }).boundingBox())!;
      expect(riquadro.width).toBeGreaterThanOrEqual(44);
      expect(riquadro.height).toBeGreaterThanOrEqual(44);
    }
    await page.getByRole("button", { name: "Salva la figura", exact: true }).click();
    await expect(gruppo).toHaveCount(0);
  }

  try {
    await scegli("🍆", true);
    await expect(page.getByText("In dispensa", { exact: true })).toBeVisible();
    await page.goto("/dispensa");
    await expect(figuraInDispensa()).toHaveAttribute("data-figure", "emoji");
    await expect(figuraInDispensa()).toHaveText("🍆");

    await scegli("Nessuna: l'icona del reparto", false);
    await expect(page.getByText("In dispensa: l'icona del reparto", { exact: true })).toBeVisible();
    await page.goto("/dispensa");
    await expect(figuraInDispensa()).toHaveAttribute("data-figure", "reparto");
    await expect(figuraInDispensa().locator("svg.tabler-icon-carrot")).toHaveCount(1);
  } finally {
    await togliDallaDispensa(page, voceId);
  }
});
```

Se una delle prove del contrasto segnala un testo o il ripiego sotto soglia, **non cambiare token** (vedi «Margine di autonomia»).

- [ ] **Step 2: Il tipo del file**

Run (da `<worktree>/frontend`): `npm run typecheck && npm run lint`
Expected: puliti. `tsc -b` compila anche gli e2e (`tsconfig.node.json`, senza la libreria DOM: per questo si passa da `contrastoAVideo` e da `page.evaluate` con stringhe).

- [ ] **Step 3: Lo stack e2e, e l'e2e intera**

Dalla radice di `<worktree>`, con i comandi delle Global Constraints: `cp .env.example .env`, `up -d --build --wait` (il backend migra da sé alla `0013` all'avvio), il seme `--con-ricette`, poi `(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)`.
Expected: tutti verdi, **due più del conto e2e del piano S3** (nel suo report della notte; se non lo trovi, conta le prove con `cd frontend && npx playwright test --list | tail -n 1` sul ramo `night/s3-ingresso-diretto` e aggiungi due). Annota il numero (`N_e2e`). Le prove di prima non cambiano: la figura è `aria-hidden` e i nomi accessibili sono quelli di prima. Se una prova di altri file fallisce, diagnosticala; non si migra.

Se una prova fallisce e lascia dati nello stack, prima di rieseguire ricrea lo stack da zero (`down -v`, `up`, seme). Alla fine, sempre:

```bash
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
rm .env
```

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/style.spec.ts
git commit -m "e2e: S12 a 375px — la figura e il ripiego nei due temi, il nome lungo a capo, la figura scelta in Anagrafica fino alla riga della Dispensa"
```

---

### Task 8: I documenti

**Files:**
- Modify: `README.md`
- Modify: `docs/prossimi-passi.md`
- Modify: `next-steps.md`

Leggi prima i tre file com'è sul ramo: S3 li ha forse aggiornati.

- [ ] **Step 1: Il README**

In `README.md`, subito **prima** della riga `### I vettori della ricerca semantica`, aggiungi:

````markdown
### Le figure degli ingredienti in dispensa

Ogni riga della Dispensa ha a sinistra del nome la figura del suo ingrediente: un'emoji
di un elenco chiuso (fermo a Emoji 14.0, in `backend/app/domain/emoji.py`), o, dove non
ce n'è una, l'icona del reparto in grigio. Un ingrediente nasce senza figura; a deciderla
è l'AI, con un comando da lanciare a mano — una volta dopo la migrazione `0013`, e poi
quando si vuole dare una figura agli ingredienti nati dopo:

```bash
docker compose exec backend python -m app.cli.decide_emoji
```

Chiede all'AI cento nomi per volta, e scrive solo dove la figura non è ancora decisa e
solo un'emoji dell'elenco (o «nessuna», se nessuna va bene); una risposta che non sa
verificare la lascia da decidere. L'ultima riga dice quanti ingredienti restano, e allora
si rilancia. Senza `OPENROUTER_API_KEY` non si rompe niente: le righe mostrano l'icona
del reparto. Una figura sbagliata si corregge nella scheda dell'ingrediente in
Anagrafica, «Cambia figura»; una scelta fatta lì, «Nessuna» compresa, il comando non la
tocca più. In produzione, con `-f docker-compose.prod.yml` come ogni altro comando.
````

- [ ] **Step 2: `docs/prossimi-passi.md`**

1. Il titolo `## S12. Le righe della dispensa sono tutte uguali **[TBD — brainstorming]**` (o com'è sul ramo) diventa `## S12. Le righe della dispensa sono tutte uguali **[FATTO <data di oggi> — sul ramo night/s12-righe-dispensa, non ancora in produzione]**`.
2. In fondo alla voce S12, prima di `## S13.`, aggiungi (sostituisci `<data di oggi>` con la data vera):

```markdown
**Fatto il <data di oggi>** sul ramo `night/s12-righe-dispensa` (piano
`docs/superpowers/plans/2026-10-08-s12-righe-dispensa.md`), con le decisioni della bozza
`docs/superpowers/specs/2026-10-06-righe-dispensa-bozza.md` §5, che superano quel che qui
sopra si diceva dell'undo: l'emoji non lega niente a niente, e si corregge in Anagrafica.
Ogni riga della Dispensa ha a sinistra del nome un quadratino da 28 px: l'emoji
dell'ingrediente (`ingredients.emoji`, migrazione `0013`), o dove non c'è l'icona del
reparto in `ink-faint`, monocroma. L'elenco è chiuso — 148 emoji fino a Emoji 14.0, in
`backend/app/domain/emoji.py`, con la copia del frontend confrontata da un test — e la
colonna ha tre stati: `NULL` non deciso, `""` «nessuna» decisa, un'emoji. La decide l'AI
una volta, con `python -m app.cli.decide_emoji`, a lotti di cento nomi e solo dove è
`NULL`; una risposta fuori elenco, o con un numero o un nome che non tornano, non si
applica. Si corregge nella scheda dell'ingrediente in Anagrafica («Cambia figura»: la
griglia dell'elenco e «Nessuna»), dal servizio unico `registry.py`; una scelta a mano non
torna mai all'AI. Solo in Dispensa: Lista, Sistema la spesa e la cottura non la mostrano.
**In produzione serve un passo a mano dopo il deploy**: il comando, una volta, finché
non dice «nessun ingrediente in attesa».

**Le scelte del piano che Mattia può voler rivedere:** l'AI che risponde «nessuna» scrive
«nessuna» e non lascia la colonna da decidere (decisione 22); le 148 emoji
dell'elenco e le loro famiglie; la figura in Anagrafica in una riga sua sotto le
correzioni, con «Cambia figura», e non come quarta icona accanto al titolo; la griglia di
riquadri da 44 px invece di un menu; «Nessuna» che si salva anche su un ingrediente che
mostra già il ripiego, per fissarlo.

**Da provare sul telefono:** le emoji del proprio telefono, a colpo d'occhio, in una
dispensa vera di una trentina di voci; la griglia di «Cambia figura» col pollice.
```

- [ ] **Step 3: `next-steps.md`**

1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte: S12 sul ramo night/s12-righe-dispensa)_`.
2. Togli la riga di S12 da `## In corso` (quella messa nella Preparazione); se la sezione resta vuota, rimetti `_(niente)_`.
3. In cima a `## Fatti (recenti)` aggiungi:
   ```markdown
   - [fatto] <data di oggi> · S12, righe della dispensa riconoscibili: l'emoji dell'ingrediente a sinistra del nome (elenco chiuso fino a Emoji 14.0, colonna `ingredients.emoji`, migrazione 0013) col ripiego sull'icona del reparto in grigio; «Cambia figura» in Anagrafica; il comando `decide_emoji` per l'AI, da lanciare dopo il deploy [S12] → branch night/s12-righe-dispensa (da revisionare)
   ```
4. In cima a `## Da fare a mano (solo Mattia)`, dopo il paragrafo in corsivo che apre la sezione (se c'è), aggiungi:
   ```markdown
   - [tbd] P2 · Dopo il deploy di S12: una volta `ssh hetznerserver "cd ~/sites/spena && docker compose -f docker-compose.prod.yml exec -T backend python -m app.cli.decide_emoji"`, rilanciato finché l'ultima riga dice «nessun ingrediente in attesa» (le figure degli ingredienti di produzione; ~9 chiamate all'AI), poi sul telefono le emoji del proprio telefono in una dispensa vera di una trentina di voci, e la griglia di «Cambia figura» col pollice [S12]
   ```
5. In `### Idee` aggiungi:
   ```markdown
   - [idea] P3 · L'emoji dell'ingrediente anche in Lista, in Sistema la spesa e nel foglio della cottura: un campo in tre risposte (oggi solo in Dispensa, deciso da Mattia il 2026-10-07) [S12]
   - [idea] P3 · `import_gz` potrebbe nominare `decide_emoji` quando ha creato ingredienti nuovi, come nomina `decide_units` per le unità [S12]
   - [idea] P3 · Una fusione in Anagrafica tiene la figura del vincitore anche quando non ne ha una e il perdente sì: potrebbe ereditarla [S12]
   ```
6. Se nella notte sono emerse altre cose da fare fuori da questo piano, aggiungile come `idea` o `tbd` nella sezione giusta, con la voce di `docs/prossimi-passi.md` fra parentesi quadre.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/prossimi-passi.md next-steps.md
git commit -m "docs: S12 fatto sul ramo — le figure in dispensa, decide_emoji nel README, il passo a mano dopo il deploy"
```

---

### Task 9: La verifica finale, la prova del comando sullo stack, il report

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

Expected: vitest tutto verde — **`N_vitest` + 16**, cioè 8 (Task 5) + 8 (Task 6), in **`N_file` + 1** file (`IngredientFigure.test.tsx`); se il numero differisce, scrivi nel report da dove viene la differenza. Typecheck, lint e build puliti. `npx tsc -b --force` perché `node_modules` è condiviso col checkout principale, e con lui il `tsbuildinfo`: `--force` compila davvero tutto.

- [ ] **Step 2: Il backend**

Da `<worktree>/backend`:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_s12 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Expected: tutto verde, **`N_pytest` + 46**: 18 (Task 1) + 1 (Task 2) + 11 (Task 3) + 15 (Task 4) + 1 (Task 6).

- [ ] **Step 3: I grep**

Dalla radice del worktree:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -rn "dept-" frontend/src/components/IngredientFigure.tsx frontend/src/features/pantry/PantryRow.tsx
grep -rln "ingredient_emoji" frontend/src --include=*.tsx | grep -v "\.test\." | sort
grep -rn "\.emoji = \|values(emoji=" backend/app | sort
```

Expected: vuoto; vuoto; solo `frontend/src/features/pantry/PantryRow.tsx`; e gli unici scrittori della colonna sono `backend/app/services/registry.py` (due righe, in `set_ingredient_emoji`) e `backend/app/services/ingredient_emoji.py` (una).

- [ ] **Step 4: L'e2e intera, e la prova del comando sullo stack**

Con i comandi delle Global Constraints, su uno stack ricreato da zero (`down -v` prima dell'`up`, se ne era rimasto uno di questo ramo): `cp .env.example .env`, `up -d --build --wait`, il seme `--con-ricette`, l'e2e intera. Expected: tutti verdi, `N_e2e` del Task 7.

Poi, **prima del `down -v`**, la prova del comando che Mattia lancerà in produzione, sullo stesso stack (seme di sviluppo, nessun dato vero; la chiave di OpenRouter lì è vuota, quindi niente si spende e l'AI «non risponde»):

```bash
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend alembic current
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.decide_emoji; echo "uscita: $?"
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.decide_emoji --azzera; echo "uscita: $?"
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T db psql -U spena -d spena -tAc "SELECT count(*) FROM ingredients WHERE emoji <> ''"
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T db psql -U spena -d spena -tAc "SELECT call_site, ok FROM llm_calls WHERE call_site = 'ingredient_emoji'"
```

Expected:
1. `0013 (head)`;
2. tre righe — `figure non disponibili (OPENROUTER_API_KEY non configurata): gli ingredienti senza figura mostrano l'icona del reparto.`, `0 figure scritte, 0 ingredienti senza una figura adatta, 0 risposte rifiutate`, `<N> ingredienti restano da decidere: rilancia questo comando.` con `<N>` almeno 186 (gli ingredienti del seme, meno «melanzana» che l'e2e ha lasciato «Nessuna», più quelli creati dalle prove) — e `uscita: 0`;
3. `argomento sconosciuto: --azzera` e `uscita: 2`;
4. `0`: il comando non ha scritto nessuna figura;
5. una riga `ingredient_emoji|f`: la chiamata mancata è registrata come le altre.

Se una di queste non torna, non è un dettaglio: il comando è quello che girerà sui dati di produzione. Segna il Task 4 `bloccato` con quel che hai visto, e scrivilo nel report.

Alla fine, sempre:

```bash
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
rm .env
```

- [ ] **Step 5: Il database dei test, via**

```bash
docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_s12 WITH (FORCE)'
docker exec spena-db-1 psql -U spena -d postgres -tAc "SELECT datname FROM pg_database WHERE datname LIKE 'spena_test_s12%'"
```

Expected: `DROP DATABASE`, poi niente (nemmeno un `spena_test_s12_migrazione_0013` rimasto da una prova interrotta: se c'è, toglilo allo stesso modo). `spena_test` non l'hai toccato.

- [ ] **Step 6: Il report**

Nel report della notte (`docs/night-reports/<data>.md`, sul ramo; se il file c'è già, una sezione `## S12, righe della dispensa riconoscibili` in coda), per questo piano:
- il ramo e da dove parte; i file che S3 aveva già cambiato fra quelli di questo piano (Preparazione), e come ci hai messo sopra le modifiche;
- i conti veri (vitest, pytest, e2e) contro quelli della Preparazione;
- i test migrati per il campo nuovo (`ingredient_emoji: null`, `emoji: null`): quali file, e se ce n'erano di S3;
- l'esito della prova del comando sullo stack (Step 4), con le righe stampate;
- le decisioni prese in autonomia (estetiche o tecniche), e la decisione 22 (il «nessuna» dell'AI scritto come `""`), presa su delega;
- **per chi orchestra la notte**: «Il ramo aggiunge la migrazione `0013`. Questo piano ha fatto girare la suite su `spena_test_s12`, poi tolto, e `spena_test` è rimasto com'era; ma i piani che partono da questo ramo (tema scuro, S14, S15) ereditano la `0013`, e se fanno girare la suite su `spena_test` lo portano alla `0013`: il piano dei suggerimenti, che parte da `master`, troverebbe `alembic upgrade head` rotto.»;
- la sezione «Dopo il deploy (solo Mattia)» qui sotto, ricopiata.

Poi:

```bash
git add docs/night-reports/
git commit -m "docs: il report della notte per S12"
```

Niente push, niente merge, niente deploy. Il worktree resta com'è, per la revisione.

---

## Dopo il deploy (solo Mattia)

La notte non tocca la produzione. Quando Mattia avrà rivisto, unito e messo in produzione il ramo:

1. **La migrazione `0013` si applica da sé** all'avvio del backend (`docker-entrypoint.sh` fa `alembic upgrade head`): il deploy di sempre, `docker compose -f docker-compose.prod.yml up -d --build --wait --wait-timeout 120`. Da quel momento ogni riga della Dispensa mostra l'icona del reparto in grigio: nessun ingrediente ha ancora una figura. Per controllare: `ssh hetznerserver "cd ~/sites/spena && docker compose -f docker-compose.prod.yml exec -T backend alembic current"` → `0013 (head)`.
2. **Le figure degli ingredienti di produzione, una volta**, con la chiave di OpenRouter già configurata in produzione (~900 ingredienti, nove chiamate da cento nomi; qualche decina di migliaia di token, molto sotto il tetto di 1 $/giorno):
   ```bash
   ssh hetznerserver "cd ~/sites/spena && docker compose -f docker-compose.prod.yml exec -T backend python -m app.cli.decide_emoji"
   ```
   L'ultima riga dice quanti ingredienti restano da decidere (le risposte che il comando non ha potuto verificare, o tutti quelli dopo un guasto dell'AI): se non è «nessun ingrediente in attesa.», si rilancia lo stesso comando, che chiede solo quelli. Se la prima riga è «figure non disponibili (…)», l'AI non ha risposto: il perché è fra parentesi, e niente è stato scritto. **Il `-f docker-compose.prod.yml` non è opzionale** (CLAUDE.md: senza, lo stack di produzione viene sostituito da quello di sviluppo). Il comando è stato provato sullo stack e2e (Task 9, Step 4) e il suo lavoro con l'AI con le risposte registrate nei test (`backend/tests/services/test_ingredient_emoji.py`).
3. **Sul telefono**: le emoji del proprio telefono, a colpo d'occhio, in una dispensa vera di una trentina di voci; una figura sbagliata si corregge dalla scheda dell'ingrediente in Anagrafica, «Cambia figura».
4. **Più avanti**, quando gli ingredienti nuovi (dall'import, dalla coda, a mano) sono abbastanza da volerli con la figura: lo stesso comando del punto 2. Non tocca le figure già decise, né quelle scelte a mano.
