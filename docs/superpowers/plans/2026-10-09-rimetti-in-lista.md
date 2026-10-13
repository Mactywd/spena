# «Rimetti in lista» anche per quasi finito: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** la stessa domanda — «questa confezione va ricomprata?» — ha una risposta sola: in Dispensa «In lista» / «Già in lista» compare anche sulle righe gialle (`low`), non solo sulle rosse; nel foglio della cottura la casella «Rimetti in lista della spesa» c'è quando la confezione dopo la cottura è gialla (vuota) o rossa (spuntata), **anche se era già gialla prima**, e spuntata la rimette in lista senza toccarne lo stato, con il motivo del giallo.

**Architecture:** nel backend, `cook` (`backend/app/services/cooking.py`) riconosce la transizione allo stesso stato e non la applica alla voce (né `status`, né `fill_percent`, né `status_changed_at`): fa solo il rientro, con il motivo che `_RESTOCK_REASON` dà allo stato; `updated` nella risposta di `POST /recipes/{id}/cook` conta solo gli stati cambiati. Nessuna rotta nuova, nessun campo nuovo, nessuna migrazione. Nel frontend, una regola sola `offersRestock(status)` in `features/pantry/statusLabels.ts` dice dove si fa la domanda; la riga del rientro esce da `PantryRow.tsx` in un componente suo, `RestockLine.tsx`, che vale per giallo e rosso; `CookSheet.tsx` calcola lo stato dopo la cottura (`afterCooking`), mostra la casella quando `offersRestock` lo dice, e manda una confezione invariata con la spunta come transizione allo stesso stato.

**Tech Stack:** FastAPI, SQLAlchemy async, pytest su Postgres vero; React 19, TypeScript, Tailwind 4 (token in `@theme`), TanStack Query 5, Vitest + Testing Library (jsdom), Playwright.

**Spec:** `docs/superpowers/specs/2026-10-09-rimetti-in-lista-design.md` (tutta: §2 le decisioni di Mattia, §3 la tabella del comportamento, §4 la forma tecnica, §5 le parole, §6 le scelte estetiche, §7 fuori scope). In `docs/prossimi-passi.md`, Parte X, le note «Nel foglio della cottura la casella «Rimetti in lista» è pre-spuntata solo per «finito»» e «`PantryRow.tsx` è il file più affollato dell'app».

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/rimetti-in-lista` (`.worktrees/` è già in `.gitignore`), ramo `night/rimetti-in-lista`, creato da **`night/s15-reparti-collassabili`** (S15, che parte da `night/s14-cibo-casa`, che parte da `night/tema-scuro-spenti`, che parte da `night/s12-righe-dispensa`, che parte da `night/s3-ingresso-diretto`, che parte da `master`). Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì (o dalle sue `backend/` e `frontend/`), mai dalla radice del checkout principale. Il checkout principale non si tocca: se vi trovi modifiche non committate, sono dell'utente. **Nessun push, nessun merge, nessun deploy. Mai `git stash`.** Nessuna lettura né scrittura sulla produzione.
- **I file che anche i piani prima di questo toccano** — `frontend/src/features/pantry/PantryRow.tsx` e `PantryRow.test.tsx` (S12 la figura e il rientro della scadenza, S14 un campo nelle voci finte), `frontend/src/features/pantry/PantryScreen.test.tsx` (S3, S14, S15), `frontend/src/features/cooking/CookSheet.test.tsx` (S12, S14: un campo nelle voci finte), `backend/tests/api/test_pantry.py` (S3, S12, S14), `frontend/e2e/style.spec.ts` (tutti), `next-steps.md`, `docs/prossimi-passi.md` — **leggili com'è sul ramo prima di cambiarli**. Il piano descrive ogni modifica a questi file contro un'ancora riconoscibile (una funzione, un elemento JSX, un testo esatto), mai contro numeri di riga, e aggiunge sempre **in blocchi propri**, senza toccare le righe degli altri piani. `CookSheet.tsx`, `backend/app/services/cooking.py`, `backend/app/api/cooking.py`, `backend/tests/api/test_cooking.py` e `statusLabels.ts` nessun piano prima di questo li tocca: la Preparazione lo verifica.
- Tutto il colore passa dai token di `frontend/src/index.css`. Nessuna schermata nomina un colore crudo: `grep -rn "emerald\|neutral-" frontend/src` resta vuoto. **Nessun token nuovo**: la parola «Quasi finito» della riga gialla è `text-low`, già testo su `card` in `theme.test.ts` (`["low", "card"]`) e nei due temi; «Finito» resta `text-finished`. Ogni testo sta sopra 4,5:1, in chiaro e in scuro, e lo misura `frontend/e2e/style.spec.ts`.
- Le icone si importano solo da `frontend/src/components/ui/icons.ts`; servono `IconListCheck` e `IconShoppingCartPlus`, che ci sono già.
- Ogni bersaglio è almeno 44×44 px («In lista» è un `Button`, come oggi sulla riga rossa; la casella del foglio è nella sua `label` da `min-h-11`, come oggi). A 375 px nessuna schermata scorre di lato.
- **I pulsanti si spengono con `Button`** e `busy` (mai `disabled` per una richiesta in volo): «In lista» resta `busy={busy}` com'è oggi.
- **Mai un vicolo cieco.** Un rientro che fallisce lo dice la riga («Non sono riuscito a salvare la modifica. Riprova.»), e «In lista» resta per riprovare, come oggi sul rosso. Una spunta nel foglio non rientra in lista di nascosto: vale solo se la casella è a video.
- **Il frontend non calcola logica di dominio.** `offersRestock` dice dove l'app fa una domanda, non se una ricetta si può cucinare; il motivo del rientro lo decide il backend (`_RESTOCK_REASON`), mai il client.
- Le parole a video sono in italiano e **si copiano esattamente come sono scritte qui**; gli identificatori in inglese; i commenti in italiano come nel resto del codice.
- **Il type check è `npm run typecheck`** (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0 (settima lezione di `CLAUDE.md`).
- Controlli del frontend, da `<worktree>/frontend`: `npx vitest run` (non esiste `npm test`), `npm run typecheck`, `npm run lint`, `npm run build`.
- **Backend su Postgres vero.** Il database dei test è il container `spena-db-1` (porta 5433), da usare solo come database dei test: se `docker ps --format '{{.Names}}'` non lo mostra, `docker start spena-db-1`. **Mai `docker compose up` dal worktree** (il nome del progetto Compose viene dalla cartella: nascerebbe un secondo Postgres che litiga sulla 5433), mai `-f docker-compose.prod.yml`. Nel worktree non c'è un `.venv`: si usa quello del checkout principale; `python -m` mette la cartella corrente in testa a `sys.path`, quindi si prova l'`app` del worktree. Il comando, sempre da `<worktree>/backend`:
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_rimetti PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
- **Il database dei test è `spena_test_rimetti`, non `spena_test`.** Questo ramo discende da `night/s12-righe-dispensa`, che aggiunge la migrazione `0013`, e la suite fa `alembic upgrade head` sul suo database all'avvio: girata su `spena_test` lo porterebbe alla `0013`, e i piani che partono da `master` (ferma alla `0012`) troverebbero `alembic upgrade head` rotto («Can't locate revision identified by '0013'»). Per questo ogni comando di pytest di questo piano porta `TEST_DATABASE_URL` davanti, e il database si crea nella Preparazione e si toglie alla fine della verifica finale:
  ```bash
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_rimetti WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_rimetti'
  # … i task …
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_rimetti WITH (FORCE)'
  ```
  La creazione va fatta come primo passo della Preparazione, prima di qualunque pytest; il `DROP` come ultimo passo della verifica finale, dopo l'ultimo pytest.
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
- Nessuna dipendenza nuova, nessuna migrazione, nessun token nuovo, nessun cambio di configurazione globale.

### Preparazione (una volta, prima del Task 1)

- [ ] Il database dei test di questo ramo, prima di qualunque pytest:
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_rimetti WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_rimetti'
  ```
- [ ] Il ramo di partenza c'è, e i punti a cui questo piano si aggancia sono com'erano su `master`:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify night/s15-reparti-collassabili
  git log --oneline master..night/s15-reparti-collassabili | wc -l
  git show night/s15-reparti-collassabili:frontend/src/features/pantry/PantryRow.tsx | grep -n 'item.status === "finished" &&\|Già in lista\|onRestock'
  git diff --stat master night/s15-reparti-collassabili -- \
    frontend/src/features/cooking/CookSheet.tsx \
    frontend/src/features/pantry/statusLabels.ts \
    backend/app/services/cooking.py backend/app/api/cooking.py backend/app/schemas/cooking.py \
    backend/tests/api/test_cooking.py
  git show night/s15-reparti-collassabili:frontend/src/features/pantry/RestockLine.tsx 2>&1 | head -n 1
  ```
  Expected: un hash; un numero maggiore di zero; in `PantryRow.tsx` una riga con `item.status === "finished" &&`, una con `Già in lista` e almeno due con `onRestock` (la prop e il suo uso); il `diff --stat` **vuoto**; per `RestockLine.tsx` un errore `fatal: path … does not exist`.
  - Se `night/s15-reparti-collassabili` non c'è, **fermati**: la catena della notte si è interrotta prima di questo piano, e nessun task parte. Il checkout principale non si tocca: la causa va nel report della notte (`docs/night-reports/<data>.md`), sull'ultimo ramo della catena che esiste, con la riga di «Rimetti in lista» segnata `bloccato` in quel ramo e la domanda per Mattia.
  - Se il `diff --stat` non è vuoto, un piano prima di questo ha toccato un file che il piano dà per com'è su `master`: non sovrascriverlo coi blocchi del piano, applica le modifiche pezzo per pezzo sopra la versione del ramo, e scrivilo nel report.
  - Se in `PantryRow.tsx` non c'è più `item.status === "finished" &&`, la riga del rientro è stata riscritta: cerca il blocco che contiene `Già in lista` e il `Button` con `onClick={onRestock}`; è quello che il Task 2 sostituisce. Scrivilo nel report.
- [ ] Dal checkout principale, allinea `node_modules` al lockfile (non aggiunge dipendenze, installa quelle di `package-lock.json`):
  ```bash
  cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund
  ```
- [ ] Crea il worktree dal ramo di S15 e collega `node_modules` (e solo quello: **niente `.env`**):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/rimetti-in-lista -b night/rimetti-in-lista night/s15-reparti-collassabili
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/rimetti-in-lista/frontend/node_modules
  ```
- [ ] Le voci finte dei test che il piano usa, com'è sul ramo:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/rimetti-in-lista
  sed -n '/^const ITEMS/,/^];/p' frontend/src/features/pantry/PantryScreen.test.tsx | grep -n 'id: "\|status:'
  sed -n '/^const PANTRY/,/^];/p' frontend/src/features/cooking/CookSheet.test.tsx | grep -n 'id: "p\|product_name\|status:'
  grep -n "^async def dispensa\|\"pomodoro\"" backend/tests/api/test_pantry.py | head -n 5
  ```
  Expected: in `ITEMS` tre voci, `p1`, `p2`, `p3` (il test del Task 2 usa `ITEMS[1]` e ne forza lo stato a `low`, quindi va bene anche se un piano l'ha cambiato); in `PANTRY` di `CookSheet.test.tsx` le cinque voci di `master`, con `p3` = «Pesca», `low` (i test del Task 3 contano su di lei: se non è così, fermati e scrivilo nel report); in `test_pantry.py` la fixture `dispensa` con la chiave `"pomodoro"`.
- [ ] I nomi della prova e2e (Task 4) sono liberi sul ramo:
  ```bash
  grep -rnw "asparago\|fave" frontend/e2e
  ```
  Expected: vuoto. Se un piano prima di questo li ha usati, nel Task 4 sostituiscili con due altri ingredienti del seme che il `grep` non trova (per esempio `fagiolino` e `piselli secchi`), e scrivilo nel report.
- [ ] La linea di partenza, dal worktree:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/rimetti-in-lista/frontend && npx vitest run 2>&1 | grep -E "Test Files|Tests "
  cd ../backend && TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_rimetti PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q 2>&1 | tail -n 1
  ```
  Expected: tutto verde. **Annota i numeri** (file e test di vitest, test di pytest): sono `N_file`, `N_vitest`, `N_pytest` del Task 6, e dipendono da quel che i piani prima di questo hanno aggiunto. Se una delle due linee non è verde, fermati: non è un difetto di questo piano, e va scritto nel report.
- [ ] In `next-steps.md` del ramo, la riga di «Rimetti in lista» (`grep -n "Rimetti in lista" next-steps.md`: in «Pronti per la notte» o dove la trovi) passa in «In corso»: sostituisci lo stato che porta (`[pronto]`) con `[in corso]`, sposta la riga sotto `## In corso` (togliendo `_(niente)_` se c'è) e aggiungi in fondo `→ branch night/rimetti-in-lista`. Poi:
  ```bash
  git add next-steps.md
  git commit -m "docs: «Rimetti in lista» in corso sul ramo night/rimetti-in-lista"
  ```

---

## Obiettivo e contesto

La stessa domanda — «questa confezione va ricomprata?» — oggi ha tre risposte. In Dispensa «In lista» compare solo sulle righe rosse (il ridisegno di T3 l'ha rifatta come pulsante e l'ha lasciata sul rosso, dopo che S2 il 2026-09-17 l'aveva estesa al giallo). Nel foglio della cottura la casella compare per lo stato **scelto** giallo o rosso, spuntata solo sul rosso. E dalla Consegna 5, con le tacche che partono dallo stato della confezione, toccare lo stato di partenza vuol dire «invariato»: una confezione già gialla **non si può più rimettere in lista dal foglio**, perché non c'è una transizione da mandare e la casella non compare. La nota di Parte X chiedeva di decidere una volta; Mattia ha deciso il 2026-10-09.

## Decisioni prese

**Da Mattia, il 2026-10-09** (spec §2; non si rimettono in discussione):

1. **«Anche quasi finito, ovunque».** La Dispensa offre «In lista» / «Già in lista» anche sulle righe `low`. Nel foglio la casella resta per `low` (vuota) e `finished` (spuntata).
2. **Nel foglio, una confezione che dopo la cottura è `low` o `finished` ha la casella anche se lo stato non è cambiato**: vuota; spuntata, la rimette in lista senza toccarne lo stato. Il motivo del rientro di una voce gialla è quello del giallo (`low_while_cooking`).
3. **Le scelte estetiche le prende Claude** su delega: 44 px, token, niente scorrimento laterale a 375 px.

**Deciso da Claude su delega di Mattia** (spec §4 e §6; tecniche ed estetiche, reversibili):

4. **La forma tecnica è la transizione allo stesso stato** (`{pantry_item_id, to_status: <stato attuale>, restock: true}`), non un campo nuovo in `CookRequest`. Il contratto della rotta non cambia e `cook` la accetta già; cambia che **una transizione allo stesso stato non tocca la voce** (né `status`, né `fill_percent`, né `status_changed_at`), fa solo il rientro col motivo che `_RESTOCK_REASON` dà allo stato, e resta nell'istantanea con `from` uguale a `to`. `updated` conta solo gli stati cambiati. Il motivo, per esteso, è in spec §4.
5. **Una regola sola per dove si fa la domanda**, `offersRestock(status)` in `frontend/src/features/pantry/statusLabels.ts` (accanto alle parole e ai colori degli stati), predicato di tipo `status is RestockStatus` (`"low" | "finished"`); la usano la Dispensa e il foglio.
6. **La riga del rientro esce da `PantryRow.tsx`** in `frontend/src/features/pantry/RestockLine.tsx`, la stessa per giallo e rosso: la parola dello stato (`STATUS_LABELS`) in `text-sm font-medium` nel colore dello stato (`text-low`, `text-finished`), a destra «In lista» (`Button`, icona `IconShoppingCartPlus`, `busy`) o «Già in lista» (con `IconListCheck`). È il primo taglio che la nota di Parte X su `PantryRow.tsx` indicava; la scadenza resta il secondo. Il pulsante non va sulla riga della scadenza: quella è larga quanto la voce (S12 la fa rientrare sotto il nome) e un pulsante la stringerebbe proprio a campo data aperto.
7. **Nel foglio, lo stato dopo la cottura** è una funzione, `afterCooking(item, choice)`: quel che si è scelto, o lo stato di partenza. Le tacche lo mostrano, la casella c'è se `offersRestock` lo dice, e la spunta si manda solo se la casella è a video (una confezione cambiata altrove a foglio aperto, e non più gialla né rossa, non rientra di nascosto).
8. **`choose` non cambia**: tornare allo stato di partenza annulla la scelta, spunta compresa (la casella, se resta perché la confezione è gialla, torna vuota). Toccare la tacca già accesa non manda niente (`StockGauge` lo ignora), quindi una spunta su una gialla invariata non si perde toccando il giallo.
9. **Il rientro dalla Dispensa resta `manual`**, per il giallo come per il rosso: la rotta `POST /pantry/{id}/restock` non cambia (accetta già ogni stato), cambia solo il commento.

## Il titolo chiuso dei reparti (S15)

- **Il titolo chiuso di un reparto (S15) conta «N finito» e non le quasi finite**, anche se da questo piano hanno anche loro «In lista»: **deciso da Mattia il 2026-10-13, S15 resta com'è.** Il giallo non è urgente come il rosso, e una nota «· 3 quasi finiti» su molti reparti renderebbe i titoli chiusi rumorosi; una riga gialla dentro un reparto chiuso si vede riaprendolo.

## Criteri di accettazione

- [ ] In Dispensa una riga `low` ha, sotto la scadenza, «Quasi finito» in `text-low` e a destra «In lista» (o «Già in lista» se l'ingrediente ha una voce aperta in lista); una riga `finished` ha «Finito» e lo stesso pulsante, come prima; una riga `available` niente.
- [ ] «In lista» su una riga gialla chiama `POST /api/v1/pantry/{id}/restock`, non manda nessuno stato, dice «Rimesso in lista: <ingrediente>» (o «Era già in lista.»), e in lista la voce ha il motivo `manual`; la riga resta gialla e diventa «Già in lista».
- [ ] Nel foglio della cottura una confezione già `low` e non toccata ha la casella «Rimetti in lista della spesa», vuota; spuntata, «Ho cucinato» manda `{to_status: "low", restock: true}`; la confezione resta `low` (stato, `fill_percent` e `status_changed_at` intatti) e rientra in lista con `low_while_cooking`; l'avviso dice «Segnato. Una cosa è tornata in lista della spesa.».
- [ ] Nel foglio: `available` → casella assente; scelto «Quasi finito» → vuota; scelto «Finito» → spuntata; da «Finito» di nuovo allo stato di partenza giallo → casella vuota e niente si manda; una spunta su una confezione che intanto è tornata disponibile non si manda.
- [ ] `updated` di `POST /recipes/{id}/cook` conta solo le confezioni il cui stato è cambiato.
- [ ] La riga gialla e il foglio si leggono nei due temi sopra 4,5:1 (`testiIlleggibili`), «Quasi finito» è il token `low`; «In lista» è 44×44; a 375 px niente scorre di lato (e2e).
- [ ] Tutti i test di oggi passano; si cambiano solo i due che il piano nomina, per la decisione di Mattia (Task 2: «una voce non finita non offre «In lista»» → disponibile; Task 3: l'asserzione «nessuna domanda sul rientro finché non si tocca niente»). vitest, typecheck, lint, build, pytest e l'e2e intera verdi; vitest ha 13 test in più, pytest 4, `style.spec.ts` una prova.
- [ ] `docs/prossimi-passi.md` e `next-steps.md` aggiornati sul ramo (Task 5), report della notte scritto (Task 6).

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
TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_rimetti PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Dalla radice di `<worktree>`:

```bash
grep -rn "emerald\|neutral-" frontend/src
git diff night/s15-reparti-collassabili --stat -- frontend/src/features/shopping-list frontend/src/features/stocking backend/alembic frontend/src/index.css
grep -rn "offersRestock" frontend/src | grep -v "\.test\."
```

Expected: il primo vuoto; il secondo vuoto (né Lista, né Sistema la spesa, né migrazioni, né token cambiano); il terzo righe solo in `features/pantry/statusLabels.ts` (la definizione), `features/pantry/RestockLine.tsx` e `features/cooking/CookSheet.tsx`. E l'e2e intera con i comandi delle Global Constraints.

## Fuori scope

- Il titolo chiuso dei reparti di S15: non si tocca (deciso da Mattia il 2026-10-13, vedi sopra).
- Un motivo nuovo per il rientro dalla Dispensa (resta `manual`, giallo e rosso).
- Estrarre da `PantryRow.tsx` la scadenza: resta un'`idea`.
- La Lista, Sistema la spesa, l'ingresso diretto, le figure delle righe, i reparti, i mondi.

## Margine di autonomia

- **Liberi:** i nomi di variabili locali e di helper di test non fissati qui; l'ordine dei test dentro un file; l'ordine delle classi Tailwind; la formulazione dei commenti, purché dicano il perché; i dettagli estetici della riga del rientro (spazi, misura dell'icona), purché restino i vincoli: 44 px, nessun colore crudo, nessun token nuovo, nessuno scorrimento laterale.
- **Fissi:** le parole a video («Quasi finito», «Finito», «In lista», «Già in lista», «Rimetti in lista della spesa», gli avvisi di oggi); i nomi pubblici che altri task usano (`offersRestock`, `RestockStatus`, `RestockLine` e le sue props `status`, `listed`, `busy`, `onRestock`, `afterCooking`); il contratto di `POST /recipes/{id}/cook` (nessun campo nuovo); il comportamento della tabella di spec §3.2.
- **Un test di oggi si cambia solo dove il piano lo dice** (i due dei Task 2 e 3). L'unica altra eccezione ammessa: un test di un piano prima di questo (S3, S14, S15) che cerca «In lista» nella pagina intera con una voce gialla nei suoi dati, e ora ne trova due — si restringe alla riga della voce che il test intende (`within(<la riga>)`), senza cambiare cosa asserisce, e si scrive nel report. Lo stesso per una prova e2e che cerca `/Rimetti in lista/` senza il nome e ora trova anche la casella di una confezione gialla: si aggiunge il nome dell'ingrediente, come fa la prova del foglio con `/Rimetti in lista radicchio/`.
- **Una scelta di comportamento non coperta dal piano** → si ferma quel task, si fa commit del lavoro parziale sul ramo, lo si segna `bloccato` in `next-steps.md` del ramo con la domanda precisa per Mattia, e si passa al task successivo. Una scelta estetica o tecnica interna → la si prende, annotata nel report della notte.
- Se un test fallisce e non si risolve in modo ragionevole: niente test disattivati, niente asserzioni indebolite; `bloccato` con la diagnosi.

## Dipendenze

**Parte da `night/s15-reparti-collassabili`** (la catena: S3 → S12 → tema scuro → S14 → S15 → questo), così al merge `PantryRow.tsx` e i test della Dispensa non hanno conflitti. Da loro questo piano **non consuma** niente: usa `PantryRow` com'è dopo S12 (la figura a sinistra, la scadenza che rientra di 36 px) e lascia com'è tutto quel che hanno aggiunto. I punti di contatto:

- **S12:** la riga della Dispensa ha una figura in più a sinistra; `RestockLine` sta sotto la scadenza, a tutta larghezza, come oggi la riga del rosso, quindi la figura non le toglie spazio. Le voci finte dei test hanno `ingredient_emoji`.
- **Tema scuro:** cambia il disegno dei pulsanti spenti (`Button` con `busy`): «In lista» lo eredita.
- **S14, S15:** il mondo e i reparti chiusi decidono quali righe si vedono; una riga gialla dentro un reparto chiuso si vede riaprendolo (il titolo chiuso non la conta: deciso da Mattia il 2026-10-13).

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `backend/app/services/cooking.py` | 1 | la transizione allo stesso stato non tocca la voce |
| `backend/app/api/cooking.py` | 1 | `updated` conta solo gli stati cambiati |
| `backend/app/schemas/cooking.py` | 1 | il commento di `updated` |
| `backend/app/api/pantry.py` | 1 | il commento di `restock_item` |
| `backend/tests/api/test_cooking.py` | 1 | 3 test in fondo |
| `backend/tests/api/test_pantry.py` | 1 | 1 test in fondo |
| `frontend/src/features/pantry/statusLabels.ts` (+ test) | 2 | `RestockStatus`, `offersRestock`; 1 test |
| `frontend/src/features/pantry/RestockLine.tsx` (+ test) | 2 | nuovo: la riga del rientro; 6 test |
| `frontend/src/features/pantry/PantryRow.tsx` (+ test) | 2 | usa `RestockLine`; un test cambiato, uno nuovo |
| `frontend/src/features/pantry/PantryScreen.test.tsx` | 2 | 1 test |
| `frontend/src/features/cooking/CookSheet.tsx` (+ test) | 3 | `afterCooking`, la casella per lo stato dopo la cottura, la transizione allo stesso stato; un'asserzione cambiata, 4 test |
| `frontend/e2e/style.spec.ts` | 4 | una prova in fondo |
| `docs/prossimi-passi.md`, `next-steps.md` | Prep., 5 | la nota chiusa, l'idea dell'estrazione, le voci |
| `docs/night-reports/<data>.md` | 6 | il report |

---

### Task 1: Il backend — una transizione allo stesso stato è solo un rientro in lista

**Files:**
- Modify: `backend/app/services/cooking.py` (`cook`)
- Modify: `backend/app/api/cooking.py` (`cook_recipe`)
- Modify: `backend/app/schemas/cooking.py` (`CookResultOut`)
- Modify: `backend/app/api/pantry.py` (la docstring di `restock_item`)
- Test: `backend/tests/api/test_cooking.py`, `backend/tests/api/test_pantry.py`

**Interfaces:**
- Consumes: niente di altri task.
- Produces: `POST /api/v1/recipes/{id}/cook` accetta, come oggi, `{servings?, transitions: [{pantry_item_id, to_status, restock}]}`; una transizione con `to_status` uguale allo stato attuale **non tocca la voce** e fa solo il rientro, se chiesto, con il motivo di `_RESTOCK_REASON[to_status]` (`low` → `low_while_cooking`); la risposta `{event_id, updated, restocked}` ha `updated` = numero di transizioni con `from` ≠ `to`. `POST /api/v1/pantry/{id}/restock` invariata (accetta ogni stato, motivo `manual`). Il Task 3 manda la transizione allo stesso stato.

- [ ] **Step 1: I test che falliscono**

1. In `backend/tests/api/test_cooking.py`, in cima, accanto agli altri import, aggiungi:
   ```python
   from datetime import UTC, datetime
   ```
2. In fondo allo stesso file aggiungi:

```python
# --- «Rimetti in lista» anche per quasi finito (decisione di Mattia del 2026-10-09) ---

# una data qualsiasi nel passato: se la cottura la riscrive, se ne accorge il confronto
PRIMA = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)


async def test_a_same_status_transition_restocks_without_touching_the_item(
    logged_client, db_session, scenario
):
    """Una confezione già quasi finita si rimette in lista dal foglio senza toccarla.

    Nel foglio la casella c'è anche se lo stato non cambia, e il foglio la manda come
    transizione allo stesso stato. La voce resta com'è — stato, posizione del cursore,
    data del cambio — e il motivo del rientro è quello del giallo.
    """
    pasta_item = scenario["pasta_item"]
    pasta_item.status = PantryStatus.LOW
    pasta_item.fill_percent = 40
    pasta_item.status_changed_at = PRIMA
    await db_session.flush()

    response = await logged_client.post(
        f"/api/v1/recipes/{scenario['recipe'].id}/cook",
        json={"transitions": [
            {"pantry_item_id": str(pasta_item.id), "to_status": "low", "restock": True},
        ]},
    )
    assert response.status_code == 201
    assert response.json()["updated"] == 0
    assert response.json()["restocked"] == 1

    await db_session.refresh(pasta_item)
    assert pasta_item.status == "low"
    assert pasta_item.fill_percent == 40
    assert pasta_item.status_changed_at == PRIMA

    items = list((await db_session.execute(select(ShoppingListItem))).scalars())
    assert [(item.raw_text, item.reason) for item in items] == [("pasta", "low_while_cooking")]

    # la storia di quella sera: la confezione c'era, non è cambiata, è rientrata in lista
    event = (await db_session.execute(select(CookingEvent))).scalar_one()
    assert event.snapshot["transitions"] == [{
        "pantry_item_id": str(pasta_item.id),
        "ingredient_id": str(scenario["pasta"].id),
        "from": "low",
        "to": "low",
        "restocked": True,
    }]


async def test_a_same_status_transition_without_restock_leaves_no_trace_on_the_item(
    logged_client, db_session, scenario
):
    """Senza rientro, una transizione allo stesso stato non cambia niente della voce."""
    pasta_item = scenario["pasta_item"]
    pasta_item.status_changed_at = PRIMA
    await db_session.flush()

    response = await logged_client.post(
        f"/api/v1/recipes/{scenario['recipe'].id}/cook",
        json={"transitions": [
            {"pantry_item_id": str(pasta_item.id), "to_status": "available", "restock": False},
        ]},
    )
    assert response.status_code == 201
    assert response.json()["updated"] == 0
    assert response.json()["restocked"] == 0

    await db_session.refresh(pasta_item)
    assert pasta_item.status == "available"
    assert pasta_item.status_changed_at == PRIMA
    assert list((await db_session.execute(select(ShoppingListItem))).scalars()) == []


async def test_updated_counts_only_the_items_whose_state_changed(
    logged_client, db_session, scenario
):
    """`updated` dice quante confezioni hanno cambiato stato: un rientro senza cambio lo
    conta `restocked`, non `updated`."""
    scenario["pasta_item"].status = PantryStatus.LOW
    await db_session.flush()

    response = await logged_client.post(
        f"/api/v1/recipes/{scenario['recipe'].id}/cook",
        json={"transitions": [
            {"pantry_item_id": str(scenario["pomodoro_item"].id), "to_status": "finished",
             "restock": True},
            {"pantry_item_id": str(scenario["pasta_item"].id), "to_status": "low",
             "restock": True},
        ]},
    )
    assert response.json()["updated"] == 1
    assert response.json()["restocked"] == 2

    items = list((await db_session.execute(select(ShoppingListItem))).scalars())
    assert sorted((item.raw_text, item.reason) for item in items) == [
        ("pasta", "low_while_cooking"),
        ("pomodoro", "finished_while_cooking"),
    ]
```

3. In fondo a `backend/tests/api/test_pantry.py` (leggilo com'è sul ramo: S3, S12 e S14 ci hanno aggiunto prove; le tue vanno dopo le loro, e la fixture `dispensa` è quella che la Preparazione ha controllato) aggiungi:

```python
async def test_la_rotta_di_rientro_vale_anche_per_una_voce_quasi_finita(
    logged_client, db_session, dispensa
):
    """Dal 2026-10-09 la Dispensa offre «In lista» anche sul giallo (decisione di Mattia).

    La rotta lo accettava già: questa prova fissa il contratto che la riga gialla usa —
    scrive in lista con il motivo di una richiesta a mano, come per una finita, e non
    tocca lo stato della voce.
    """
    item = PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.LOW)
    db_session.add(item)
    await db_session.flush()

    risposta = await logged_client.post(f"/api/v1/pantry/{item.id}/restock")
    assert risposta.status_code == 200
    assert risposta.json() == {"added": True}

    lista = (await logged_client.get("/api/v1/shopping-list")).json()
    assert [(voce["raw_text"], voce["reason"]) for voce in lista] == [("pomodoro", "manual")]

    await db_session.refresh(item)
    assert item.status == "low"
```

- [ ] **Step 2: Falliscono (tre su quattro)**

Run (da `<worktree>/backend`):
```bash
TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_rimetti PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/api/test_cooking.py tests/api/test_pantry.py -k "same_status or updated_counts or quasi_finita"
```
Expected: 3 FAIL, 1 PASS. I tre di `test_cooking.py` falliscono su `updated` (`assert 1 == 0`, e `assert 2 == 1` nel terzo): oggi una transizione allo stesso stato è contata come un cambio, e riscrive `status_changed_at`. `test_la_rotta_di_rientro_vale_anche_per_una_voce_quasi_finita` **passa già**: la rotta non guarda lo stato, e la prova fissa quel contratto per la riga gialla (va bene così; se fallisce, fermati e diagnostica: la Dispensa del Task 2 conta su di lei).

- [ ] **Step 3: L'implementazione**

1. In `backend/app/services/cooking.py`, dentro `cook`, nel ciclo `for transition in transitions:`, il blocco

```python
        previous = item.status
        item.status = transition.to_status
        # la posizione del cursore non sopravvive a uno stato deciso qui: restare a
        # 80 mentre lo stato dice «finito» mostrerebbe un barattolo pieno per
        # qualcosa che non c'è più (stesso motivo di `set_status`)
        item.fill_percent = None
        item.status_changed_at = now
```

diventa

```python
        previous = item.status
        # Una «transizione» allo stesso stato non cambia niente della voce: è il foglio
        # che rimette in lista una confezione già quasi finita senza toccarla (decisione
        # di Mattia del 2026-10-09). Riscrivere `status_changed_at`, o azzerare il
        # cursore, direbbe un cambio che non c'è stato. Il rientro qui sotto vale lo
        # stesso, col motivo dello stato, e l'istantanea la registra con `from` uguale a
        # `to`: la storia vera di quella sera.
        if transition.to_status != previous:
            item.status = transition.to_status
            # la posizione del cursore non sopravvive a uno stato deciso qui: restare a
            # 80 mentre lo stato dice «finito» mostrerebbe un barattolo pieno per
            # qualcosa che non c'è più (stesso motivo di `set_status`)
            item.fill_percent = None
            item.status_changed_at = now
```

   Il resto del ciclo (il rientro con `_RESTOCK_REASON.get(transition.to_status, …)` e l'istantanea) non cambia: `to_status` è lo stato della voce in tutti e due i casi, quindi il motivo del giallo esce da solo.

2. In `backend/app/api/cooking.py`, in `cook_recipe`, il `return` diventa:

```python
    return CookResultOut(
        event_id=event.id,
        # le confezioni il cui stato è cambiato: una transizione allo stesso stato è solo
        # un rientro in lista, e lo conta `restocked`
        updated=sum(1 for t in event.snapshot["transitions"] if t["from"] != t["to"]),
        restocked=event.snapshot["restocked"],
    )
```

   (`from` è lo stato letto dalla voce, `to` la stringa dello stato chiesto: `PantryStatus` è una `StrEnum`, quindi i due si confrontano come stringhe.)

3. In `backend/app/schemas/cooking.py`, in `CookResultOut`, sopra `updated: int` aggiungi il commento:
   ```python
       # quante confezioni hanno cambiato stato (una transizione allo stesso stato no)
   ```

4. In `backend/app/api/pantry.py`, nella docstring di `restock_item`, la prima riga `"""Rimette in lista quel che è finito, se non c'è già.` diventa `"""Rimette in lista quel che è finito o quasi finito, se non c'è già.`; il resto della docstring resta. Nessun'altra riga della rotta cambia.

- [ ] **Step 4: Passano, e tutto il backend**

Run (da `<worktree>/backend`):
```bash
TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_rimetti PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```
Expected: tutto verde, **`N_pytest` + 4**. In particolare passano ancora, senza modifiche, `test_cooking_updates_statuses_and_records_the_event` (due cambi veri: `updated == 2`), `test_restocking_an_available_item_uses_manual_reason` (una transizione `available` → `available` col rientro: ora non tocca la voce, e il motivo resta `manual`) e `test_cooking_azzera_la_posizione_del_cursore`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/cooking.py backend/app/api/cooking.py backend/app/schemas/cooking.py backend/app/api/pantry.py backend/tests/api/test_cooking.py backend/tests/api/test_pantry.py
git commit -m "feat(cottura): una transizione allo stesso stato è solo un rientro in lista, e non tocca la voce; updated conta i cambi veri"
```

---

### Task 2: La Dispensa — «In lista» anche sul giallo, in `RestockLine`

**Files:**
- Modify: `frontend/src/features/pantry/statusLabels.ts`, `frontend/src/features/pantry/statusLabels.test.ts`
- Create: `frontend/src/features/pantry/RestockLine.tsx`, `frontend/src/features/pantry/RestockLine.test.tsx`
- Modify: `frontend/src/features/pantry/PantryRow.tsx`, `frontend/src/features/pantry/PantryRow.test.tsx`
- Test: `frontend/src/features/pantry/PantryScreen.test.tsx`

**Interfaces:**
- Consumes: `POST /api/v1/pantry/{id}/restock` (Task 1: accetta il giallo, motivo `manual`); in `PantryScreen` la mutazione `restock` e `listedIngredients` di oggi, che non cambiano.
- Produces: in `statusLabels.ts`, `export type RestockStatus = Extract<PantryStatus, "low" | "finished">` e `export function offersRestock(status: PantryStatus): status is RestockStatus`; in `RestockLine.tsx`, `export function RestockLine({ status, listed, busy, onRestock }: { status: PantryStatus; listed: boolean; busy: boolean; onRestock: () => void })`, che su `available` non disegna niente. Il Task 3 usa `offersRestock`.

Leggi `PantryRow.tsx`, `PantryRow.test.tsx` e `PantryScreen.test.tsx` com'è sul ramo prima di cambiarli: S12 ha aggiunto la figura e il rientro della scadenza, S14 un campo nelle voci finte, S3 e S15 prove in `PantryScreen.test.tsx`.

- [ ] **Step 1: I test che falliscono**

1. In `frontend/src/features/pantry/statusLabels.test.ts`, l'import `import { STATUS_LABELS, STATUS_TONE } from "./statusLabels";` diventa `import { STATUS_LABELS, STATUS_TONE, offersRestock } from "./statusLabels";`, e dentro il `describe("il modo in cui il sistema presenta uno stato", …)`, dopo l'ultimo `it`, aggiungi:

```ts
  // Una regola sola per le due sezioni (decisione di Mattia del 2026-10-09, «anche quasi
  // finito, ovunque»): prima la Dispensa faceva la domanda solo sul rosso e il foglio
  // della cottura anche sul giallo
  it("offre il rientro in lista sul giallo e sul rosso, non sul verde", () => {
    expect(STATUSES.filter(offersRestock)).toEqual(["low", "finished"]);
  });
```

2. Crea `frontend/src/features/pantry/RestockLine.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { RestockLine } from "./RestockLine";
import type { PantryStatus } from "../../domain/types";

function renderLine(status: PantryStatus, { listed = false, busy = false } = {}) {
  const onRestock = vi.fn();
  const view = render(
    <RestockLine status={status} listed={listed} busy={busy} onRestock={onRestock} />
  );
  return { ...view, onRestock };
}

describe("RestockLine", () => {
  it("su una voce finita dice «Finito», in rosso, e «In lista» la rimette in lista", () => {
    const { onRestock } = renderLine("finished");
    expect(screen.getByText("Finito")).toHaveClass("text-finished");
    fireEvent.click(screen.getByRole("button", { name: "In lista" }));
    expect(onRestock).toHaveBeenCalledTimes(1);
  });

  it("su una voce quasi finita dice «Quasi finito», nel colore del giallo, e offre «In lista» (Mattia, 2026-10-09)", () => {
    const { onRestock } = renderLine("low");
    expect(screen.getByText("Quasi finito")).toHaveClass("text-low");
    fireEvent.click(screen.getByRole("button", { name: "In lista" }));
    expect(onRestock).toHaveBeenCalledTimes(1);
  });

  it.each(["low", "finished"] as const)(
    "su una voce %s già in lista dice «Già in lista» e non offre di rimettercela",
    (status) => {
      renderLine(status, { listed: true });
      expect(screen.queryByRole("button", { name: "In lista" })).toBeNull();
      expect(screen.getByText("Già in lista")).toBeDefined();
    }
  );

  it("su una voce disponibile non disegna niente", () => {
    const { container } = renderLine("available");
    expect(container.innerHTML).toBe("");
  });

  it("mentre una scrittura è in volo «In lista» è spento con aria-disabled, e il tocco non parte", () => {
    const { onRestock } = renderLine("low", { busy: true });
    const button = screen.getByRole("button", { name: "In lista" });
    // `busy` e non `disabled`: il fuoco resta sul pulsante (regola di `Button`)
    expect(button.hasAttribute("disabled")).toBe(false);
    expect(button).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(button);
    expect(onRestock).not.toHaveBeenCalled();
  });
});
```

3. In `frontend/src/features/pantry/PantryRow.test.tsx`, dentro `describe("PantryRow", …)`, **il test di oggi** (cambia per la decisione 1 di Mattia: la sua premessa, «una voce gialla non offre «In lista»», è ora sbagliata)

```tsx
  it("una voce non finita non offre «In lista»", () => {
    renderRow({ status: "low" });
    expect(screen.queryByRole("button", { name: "In lista" })).toBeNull();
  });
```

diventa

```tsx
  it("una voce disponibile non offre «In lista»", () => {
    renderRow({ status: "available" });
    expect(screen.queryByRole("button", { name: "In lista" })).toBeNull();
  });

  it("una voce quasi finita dice «Quasi finito» e offre «In lista» (Mattia, 2026-10-09)", () => {
    const { onRestock } = renderRow({ status: "low" });
    expect(screen.getByText("Quasi finito")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "In lista" }));
    expect(onRestock).toHaveBeenCalled();
  });
```

4. In `frontend/src/features/pantry/PantryScreen.test.tsx`, dentro `describe("PantryScreen", …)`, subito dopo il test `it("se era già in lista, l'avviso lo dice", …)`, aggiungi (prova la mutazione vera dello schermo, non un `onRestock` finto: prima lezione di `CLAUDE.md`):

```tsx
  it("«In lista» su una voce quasi finita la rimette in lista, e lo stato resta quello (Mattia, 2026-10-09)", async () => {
    const low = [{ ...ITEMS[1], status: "low" }];
    const fetchSpy = stubRoutedFetch((path) =>
      path.includes("/restock") ? [{ added: true }, 200] : path.includes("/shopping-list") ? [[], 200] : [low, 200]
    );
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "In lista" }));
    expect(await screen.findByText(`Rimesso in lista: ${ITEMS[1].ingredient_name}`)).toBeDefined();
    expect(
      fetchSpy.mock.calls.some(
        ([url, init]) => String(url).includes(`/pantry/${ITEMS[1].id}/restock`) && init?.method === "POST"
      )
    ).toBe(true);
    // il rientro scrive solo in lista: nessuno stato parte, la voce resta gialla
    expect(fetchSpy.mock.calls.some(([, init]) => init?.method === "PATCH")).toBe(false);
  });
```

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/features/pantry/statusLabels.test.ts src/features/pantry/RestockLine.test.tsx src/features/pantry/PantryRow.test.tsx src/features/pantry/PantryScreen.test.tsx`
Expected: FAIL — `RestockLine.test.tsx` non trova il modulo `./RestockLine`; in `statusLabels.test.ts` `offersRestock` non è una funzione; in `PantryRow.test.tsx` «una voce quasi finita dice «Quasi finito»…» non trova il testo (il test «una voce disponibile…» passa già: va bene); in `PantryScreen.test.tsx` il test nuovo non trova il pulsante «In lista».

- [ ] **Step 3: La regola, il componente, la riga**

1. In `frontend/src/features/pantry/statusLabels.ts`, in fondo al file, aggiungi:

```ts
/** I due stati per cui l'app chiede «la rimetto in lista?». */
export type RestockStatus = Extract<PantryStatus, "low" | "finished">;

/** Dove l'app offre di rimettere in lista una confezione: in Dispensa («In lista») e nel
 * foglio della cottura («Rimetti in lista della spesa»), per lo stesso insieme di stati.
 * Una regola sola per le due sezioni (decisione di Mattia del 2026-10-09, «anche quasi
 * finito, ovunque»): prima la Dispensa faceva la domanda solo sul rosso e il foglio anche
 * sul giallo, e rispondevano in modo diverso alla stessa domanda. Sta qui, accanto alle
 * parole e ai colori degli stati, e non accanto a un componente: un export che non è un
 * componente romperebbe il fast refresh. */
export function offersRestock(status: PantryStatus): status is RestockStatus {
  return status === "low" || status === "finished";
}
```

2. Crea `frontend/src/features/pantry/RestockLine.tsx`:

```tsx
import { Button } from "../../components/ui/Button";
import { IconListCheck, IconShoppingCartPlus } from "../../components/ui/icons";
import { STATUS_LABELS, offersRestock, type RestockStatus } from "./statusLabels";
import type { PantryStatus } from "../../domain/types";

// La parola dello stato nel suo colore, come le tacche accese: rosso per finito, ambra
// per quasi finito. `text-finished` e `text-low` su `card` sono già misurati in
// `theme.test.ts`, e il tema scuro li ridefinisce.
const WORD_TONE: Record<RestockStatus, string> = {
  low: "text-low",
  finished: "text-finished",
};

/** La riga del rientro in lista, sotto una voce gialla o rossa della Dispensa: la parola
 * dello stato e, a destra, «In lista» — o «Già in lista» se l'ingrediente ha già una voce
 * aperta in lista (dal giro di T3: «la domanda del rientro compare anche per ciò che è
 * già in lista»). Su una voce disponibile non disegna niente.
 *
 * Era dentro `PantryRow`, per il solo rosso; dal 2026-10-09 vale anche per il giallo
 * (Mattia: «anche quasi finito, ovunque») ed è uscita in un file suo, il taglio che la
 * nota di Parte X su `PantryRow.tsx` indicava. Sta sotto la scadenza, a tutta larghezza,
 * e non sulla riga della scadenza: lì un pulsante stringerebbe il campo data quando è
 * aperto. Il tocco non cambia lo stato della voce: la rotta del rientro scrive solo in
 * lista. */
export function RestockLine({
  status,
  listed,
  busy,
  onRestock,
}: {
  status: PantryStatus;
  listed: boolean;
  busy: boolean;
  onRestock: () => void;
}) {
  if (!offersRestock(status)) return null;
  return (
    // «Lo rimetto in lista? Sì / No» aveva bersagli da 35px e non tornava più se
    // ignorato: è un pulsante che resta finché serve, e ignorarlo è il «No»
    <div className="flex items-center justify-between gap-2 pb-2">
      <span className={`text-sm font-medium ${WORD_TONE[status]}`}>{STATUS_LABELS[status]}</span>
      {listed ? (
        <span className="flex items-center gap-1 text-sm text-ink-soft">
          <IconListCheck aria-hidden="true" className="size-4" stroke={1.8} />
          Già in lista
        </span>
      ) : (
        <Button icon={IconShoppingCartPlus} onClick={onRestock} busy={busy}>
          In lista
        </Button>
      )}
    </div>
  );
}
```

3. In `frontend/src/features/pantry/PantryRow.tsx` (leggilo com'è sul ramo):
   - nell'import dalle icone, `import { IconListCheck, IconShoppingCartPlus, IconX } from "../../components/ui/icons";` diventa `import { IconX } from "../../components/ui/icons";` (se sul ramo l'import ha altre icone aggiunte da S12, togli solo `IconListCheck` e `IconShoppingCartPlus`);
   - accanto agli altri import locali (per esempio dopo `import { itemLabel } from "./pantryView";`) aggiungi `import { RestockLine } from "./RestockLine";`;
   - il blocco JSX che comincia con `{item.status === "finished" && (` e finisce con il `)}` che lo chiude, subito prima di `{failed && <Alert`, — cioè, su `master`:
     ```tsx
           {item.status === "finished" && (
             // «Lo rimetto in lista? Sì / No» aveva bersagli da 35px e non tornava più se
             // ignorato: ora è un pulsante che resta finché serve, e ignorarlo è il «No»
             <div className="flex items-center justify-between gap-2 pb-2">
               <span className="text-sm font-medium text-finished">Finito</span>
               {listed ? (
                 <span className="flex items-center gap-1 text-sm text-ink-soft">
                   <IconListCheck aria-hidden="true" className="size-4" stroke={1.8} />
                   Già in lista
                 </span>
               ) : (
                 <Button icon={IconShoppingCartPlus} onClick={onRestock} busy={busy}>
                   In lista
                 </Button>
               )}
             </div>
           )}
     ```
     — diventa:
     ```tsx
           {/* sotto una voce gialla o rossa, «In lista» (Mattia, 2026-10-09: «anche quasi
               finito, ovunque»); su una disponibile non c'è niente */}
           <RestockLine status={item.status} listed={listed} busy={busy} onRestock={onRestock} />
     ```
   - nella docstring di `PantryRow` (`/** Una riga della dispensa (spec T3 §4.1): …`), dopo la frase che finisce con `la scadenza.` aggiungi: ` Sotto ancora, per una voce gialla o rossa, il rientro in lista (\`RestockLine\`).`
   - `Button` resta importato: lo usa la ✕.

- [ ] **Step 4: Passano, e tutto il frontend**

Run (da `<worktree>/frontend`):
```bash
npx vitest run
npm run typecheck
npm run lint
```
Expected: vitest tutto verde, **`N_vitest` + 9** (1 + 6 + 1 + 1) in **`N_file` + 1** file; typecheck e lint puliti (il lint segnalerebbe un'icona rimasta importata e non usata). I test di oggi su «In lista» del rosso (`PantryRow.test.tsx` «una voce finita dice «Finito» e offre «In lista»», «se è già in lista…», «mentre una scrittura è in volo…»; `PantryScreen.test.tsx` ««In lista» su una voce finita…», «un rientro in lista che fallisce…», «se era già in lista…», «una voce finita che ha già una voce aperta in lista…») passano senza modifiche. Se un test di S3, S14 o S15 fallisce perché cerca «In lista» nella pagina intera e ora ne trova due (una voce gialla nei suoi dati), applica l'eccezione di «Margine di autonomia» e scrivilo nel report.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/pantry/statusLabels.ts frontend/src/features/pantry/statusLabels.test.ts frontend/src/features/pantry/RestockLine.tsx frontend/src/features/pantry/RestockLine.test.tsx frontend/src/features/pantry/PantryRow.tsx frontend/src/features/pantry/PantryRow.test.tsx frontend/src/features/pantry/PantryScreen.test.tsx
git commit -m "feat(dispensa): «In lista» anche sulle righe quasi finite — la riga del rientro esce in RestockLine, la regola in offersRestock"
```

---

### Task 3: Il foglio della cottura — la casella per lo stato dopo la cottura, anche su una gialla invariata

**Files:**
- Modify: `frontend/src/features/cooking/CookSheet.tsx`
- Test: `frontend/src/features/cooking/CookSheet.test.tsx`

**Interfaces:**
- Consumes: `offersRestock` da `../pantry/statusLabels` (Task 2); la transizione allo stesso stato di `POST /recipes/{id}/cook` (Task 1).
- Produces: in `CookSheet.tsx`, `function afterCooking(item: PantryItem, choice: Choice): PantryStatus` (locale al file). Il corpo mandato da `cookRecipe` resta `{servings, transitions: {pantry_item_id, to_status, restock}[]}`.

Leggi `CookSheet.test.tsx` com'è sul ramo: S12 e S14 hanno aggiunto un campo alle voci di `PANTRY` (le prove qui sotto le usano con lo spread, quindi valgono comunque).

- [ ] **Step 1: I test che falliscono**

In `frontend/src/features/cooking/CookSheet.test.tsx`:

1. **Il test di oggi** `it("le tacche partono da com'è la confezione: niente toccato è invariato", …)` cambia in due righe, per la decisione 2 di Mattia (le due confezioni gialle di `PANTRY`, `p3` e `p4`, ora hanno la casella, vuota). Le righe

```tsx
    // e nessuna domanda sul rientro finché non si tocca niente
    expect(screen.queryByRole("checkbox")).toBeNull();
```

diventano

```tsx
    // la domanda del rientro c'è dove la confezione resta gialla o rossa, anche senza
    // toccare niente: sulle due quasi finite, vuota (Mattia, 2026-10-09); sulle
    // disponibili no
    expect(within(yogurt).queryByRole("checkbox")).toBeNull();
    expect(within(pesca).getByRole("checkbox", { name: /Rimetti in lista/ })).not.toBeChecked();
    expect(screen.getAllByRole("checkbox")).toHaveLength(2);
```

   Il resto del test (le tacche di partenza, «Ho cucinato», `transitions` uguale a `[]`) resta com'è: le caselle vuote non mandano niente.

2. In fondo al `describe("CookSheet", …)`, dopo l'ultimo `it` (su `master`: «si può togliere la spunta al riacquisto di una voce finita»), aggiungi:

```tsx
  // --- «Rimetti in lista» anche per quasi finito (decisione di Mattia del 2026-10-09) ---

  it("una confezione già quasi finita si rimette in lista senza toccarne lo stato", async () => {
    // Dalla Consegna 5 toccare lo stato di partenza vuol dire «invariato», e una
    // confezione gialla non si poteva più rimettere in lista da qui. Ora la casella c'è,
    // e spuntata parte come transizione allo stesso stato: il backend non tocca la voce
    // e la rimette in lista col motivo del giallo
    const spy = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ event_id: "e1", updated: 0, restocked: 1 }), { status: 201 }
    ));
    vi.stubGlobal("fetch", spy);

    renderSheet();
    const row = screen.getByText("Pesca").closest("li")!;
    const box = within(row).getByRole("checkbox", { name: /Rimetti in lista/ });
    expect(box).not.toBeChecked();
    await userEvent.click(box);
    expect(box).toBeChecked();
    // le tacche restano dove partono: lo stato non si tocca
    expect(within(row).getByRole("radio", { name: "Quasi finito" })).toHaveAttribute("aria-checked", "true");

    await userEvent.click(screen.getByRole("button", { name: "Ho cucinato" }));
    expect(JSON.parse(spy.mock.calls[0][1].body).transitions).toEqual([
      { pantry_item_id: "p3", to_status: "low", restock: true },
    ]);
  });

  it("spuntata e poi tolta, una quasi finita invariata non manda niente", async () => {
    const spy = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ event_id: "e1", updated: 0, restocked: 0 }), { status: 201 }
    ));
    vi.stubGlobal("fetch", spy);

    renderSheet();
    const row = screen.getByText("Pesca").closest("li")!;
    const box = within(row).getByRole("checkbox", { name: /Rimetti in lista/ });
    await userEvent.click(box);
    await userEvent.click(box);
    expect(box).not.toBeChecked();

    await userEvent.click(screen.getByRole("button", { name: "Ho cucinato" }));
    expect(JSON.parse(spy.mock.calls[0][1].body).transitions).toEqual([]);
  });

  it("da quasi finito a finito la casella si spunta; tornando a quasi finito resta, vuota", async () => {
    // tornare allo stato di partenza annulla la scelta, spunta compresa: la casella resta
    // perché la confezione è ancora gialla, ma vuota come all'inizio
    const spy = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ event_id: "e1", updated: 0, restocked: 0 }), { status: 201 }
    ));
    vi.stubGlobal("fetch", spy);

    renderSheet();
    const row = screen.getByText("Pesca").closest("li")!;
    await userEvent.click(within(row).getByRole("radio", { name: "Finito" }));
    expect(within(row).getByRole("checkbox", { name: /Rimetti in lista/ })).toBeChecked();

    await userEvent.click(within(row).getByRole("radio", { name: "Quasi finito" }));
    expect(within(row).getByRole("checkbox", { name: /Rimetti in lista/ })).not.toBeChecked();

    await userEvent.click(screen.getByRole("button", { name: "Ho cucinato" }));
    expect(JSON.parse(spy.mock.calls[0][1].body).transitions).toEqual([]);
  });

  it("una spunta su una confezione che intanto è tornata disponibile non si manda", async () => {
    // la dispensa è una prop viva: se la confezione cambia altrove a foglio aperto e non è
    // più gialla, la casella sparisce, e una spunta che nessuno vede non rientra in lista
    const spy = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ event_id: "e1", updated: 0, restocked: 0 }), { status: 201 }
    ));
    vi.stubGlobal("fetch", spy);

    const { show } = renderSheet();
    const row = screen.getByText("Pesca").closest("li")!;
    await userEvent.click(within(row).getByRole("checkbox", { name: /Rimetti in lista/ }));

    show(PANTRY.map((item) => (item.id === "p3" ? { ...item, status: "available" as const } : item)));
    expect(within(screen.getByText("Pesca").closest("li")!).queryByRole("checkbox")).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Ho cucinato" }));
    expect(JSON.parse(spy.mock.calls[0][1].body).transitions).toEqual([]);
  });
```

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/features/cooking/CookSheet.test.tsx`
Expected: FAIL — «le tacche partono da com'è la confezione…» non trova la casella di «Pesca» (`Unable to find role="checkbox"`); i quattro test nuovi non trovano la casella su una gialla non toccata (il terzo: dopo il ritorno a «Quasi finito» la casella sparisce). Gli altri test del file passano.

- [ ] **Step 3: L'implementazione**

In `frontend/src/features/cooking/CookSheet.tsx`:

1. L'import `import { STATUS_LABELS } from "../pantry/statusLabels";` diventa `import { STATUS_LABELS, offersRestock } from "../pantry/statusLabels";`.

2. Subito dopo la costante `UNCHANGED` (e il suo commento) aggiungi:

```tsx
// Com'è la confezione dopo la cottura: quel che si è scelto, o com'era se non si è
// toccato niente. È lo stato che le tacche mostrano, e quello a cui si risponde «la
// rimetto in lista?» — anche quando non è cambiato (Mattia, 2026-10-09): una confezione
// già quasi finita prima di cucinare si può rimettere in lista da qui.
function afterCooking(item: PantryItem, choice: Choice): PantryStatus {
  return choice.status === "unchanged" ? item.status : choice.status;
}
```

3. Nel `mutationFn` di `cook`, la proprietà `transitions` e il commento sopra di lei — su `master`:

```tsx
        // si parte da ciò che è in elenco, non da ciò che è stato toccato: una voce
        // sparita dalla dispensa mentre il foglio era aperto farebbe fallire tutta
        // la cottura per un id che l'utente non ha più davanti e non può togliere.
        // E invariato non è una transizione: non si manda.
        transitions: used
          .map((item) => ({ item, choice: choices[item.id] ?? UNCHANGED }))
          .filter(({ choice }) => choice.status !== "unchanged")
          .map(({ item, choice }) => ({
            pantry_item_id: item.id,
            to_status: choice.status as PantryStatus,
            restock: choice.restock,
          })),
```

   — diventano:

```tsx
        // si parte da ciò che è in elenco, non da ciò che è stato toccato: una voce
        // sparita dalla dispensa mentre il foglio era aperto farebbe fallire tutta
        // la cottura per un id che l'utente non ha più davanti e non può togliere.
        // E invariato non è una transizione: non si manda — salvo che la si rimetta in
        // lista. Allora parte come transizione allo stesso stato, che il backend
        // riconosce e non applica alla voce: la rimette solo in lista, col motivo dello
        // stato (Mattia, 2026-10-09). La spunta vale solo se la casella è a video: una
        // confezione cambiata altrove a foglio aperto, e non più gialla né rossa, non
        // rientra in lista di nascosto.
        transitions: used
          .map((item) => {
            const choice = choices[item.id] ?? UNCHANGED;
            const status = afterCooking(item, choice);
            return { item, choice, status, restock: choice.restock && offersRestock(status) };
          })
          .filter(({ choice, restock }) => choice.status !== "unchanged" || restock)
          .map(({ item, status, restock }) => ({
            pantry_item_id: item.id,
            to_status: status,
            restock,
          })),
```

4. Il commento sopra `function choose(…)`: la frase finale `Finito propone il riacquisto già spuntato, quasi finito no (la regola di prima).` diventa `Finito propone il riacquisto già spuntato, quasi finito no (la regola di prima, confermata da Mattia il 2026-10-09). Tornare allo stato di partenza annulla anche la spunta: se la confezione è gialla la casella resta, vuota.` Il corpo di `choose` non cambia.

5. Nel JSX, dentro `used.map((item) => { … })`, dopo `const label = itemLabel(item);` aggiungi `const status = afterCooking(item, choice);`. Poi:
   - lo `StockGauge` passa da `status={choice.status === "unchanged" ? item.status : choice.status}` a `status={status}`;
   - la condizione della casella, `{(choice.status === "low" || choice.status === "finished") && (`, diventa:
     ```tsx
                     {/* la casella c'è quando la confezione, dopo la cottura, è gialla o
                         rossa — anche se lo era già prima (Mattia, 2026-10-09) */}
                     {offersRestock(status) && (
     ```
     Il contenuto della `label` (la casella, il suo `aria-label`, «Rimetti in lista della spesa») non cambia.

- [ ] **Step 4: Passano, e tutto il frontend**

Run (da `<worktree>/frontend`):
```bash
npx vitest run
npm run typecheck
npm run lint
```
Expected: vitest tutto verde, **`N_vitest` + 13** in **`N_file` + 1** file (i 9 del Task 2 e i 4 di questo); typecheck e lint puliti. Passano senza modifiche, fra gli altri: «dichiarare quasi finito manda 'low' e non spunta il riacquisto» (`{p2, low, false}`), ««Disponibile» si può scegliere…» (`{p3, available, false}`, nessuna casella), «toccare di nuovo lo stato di partenza annulla la scelta» (sullo yogurt disponibile), «due confezioni identiche…», «si può togliere la spunta…».

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/cooking/CookSheet.tsx frontend/src/features/cooking/CookSheet.test.tsx
git commit -m "feat(cottura): la casella del rientro segue lo stato dopo la cottura — una confezione già quasi finita si rimette in lista senza toccarla"
```

---

### Task 4: L'e2e — la riga gialla e il foglio nel browser vero, a 375 px, nei due temi

jsdom non calcola il CSS (quarta lezione di `CLAUDE.md`): che «In lista» sulla riga gialla sia un bersaglio da 44 px, che a 375 px la riga (con la figura di S12) non scorra di lato, che «Quasi finito» sia il token `low` e si legga sul fondo della scheda nei due temi, e che il giro intero — dispensa, foglio, lista — arrivi al backend vero col motivo giusto, lo dice solo un browser. Il seme non popola la dispensa: le voci e la ricetta si creano con `page.request`, come fanno il test del riepilogo delle scadenze e `ricettaDiProva` in questo stesso file, e si tolgono nel `finally`.

**Files:**
- Modify: `frontend/e2e/style.spec.ts` (una prova in fondo, in un blocco proprio)

- [ ] **Step 1: La prova**

In fondo a `frontend/e2e/style.spec.ts` aggiungi (il `beforeEach` del file ha già fatto l'accesso; `fermo`, `testiIlleggibili`, `contrastoAVideo`, `tokenDelTema`, `tokenDelTemaScuro` e `senzaScorrimentoLaterale` sono già definiti più sopra nel file). Se la Preparazione ha trovato `asparago` o `fave` già usati, sostituiscili qui con i due nomi scelti, ovunque compaiano:

```ts
// --- «Rimetti in lista» anche per quasi finito (2026-10-09) ---

test("«Rimetti in lista» a 375px: la riga gialla offre «In lista», e il foglio della cottura rimette in lista una confezione già quasi finita senza toccarla", async ({
  page,
}) => {
  // il `beforeEach` tocca «Entra» ma non aspetta la risposta: la prima cosa qui è una
  // `page.request`, quindi l'attesa va messa a mano (vedi il test del riepilogo)
  await expect(page.getByRole("link", { name: "Dispensa", exact: true })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });

  /** L'id di un ingrediente del seme, cercato per nome intero. */
  async function ingrediente(nome: string): Promise<string> {
    const trovati = (await (
      await page.request.get(`/api/v1/ingredients/search?q=${encodeURIComponent(nome)}`)
    ).json()) as { id: string; name: string }[];
    const voce = trovati.find((t) => t.name === nome);
    expect(voce, `«${nome}» non è nel seme`).toBeDefined();
    return voce!.id;
  }
  /** Le voci aperte della lista per un ingrediente. */
  async function inLista(ingredienteId: string) {
    const voci = (await (
      await page.request.get("/api/v1/shopping-list?status=pending&status=checked")
    ).json()) as { id: string; ingredient_id: string | null; reason: string }[];
    return voci.filter((voce) => voce.ingredient_id === ingredienteId);
  }

  // Due ingredienti che nessun altro file della suite nomina, e che nessuna ricetta del
  // seme usa: l'asparago quasi finito, le fave disponibili. Questo file non lascia niente
  // dietro di sé: voci di lista, confezioni e ricetta si tolgono nel `finally`
  const asparagoId = await ingrediente("asparago");
  const faveId = await ingrediente("fave");
  expect(
    await inLista(asparagoId),
    "lo stack e2e non è pulito: ricrealo con `down -v` e riesegui"
  ).toEqual([]);

  const confezioni: string[] = [];
  let ricettaId: string | undefined;
  try {
    const asparago = await page.request.post("/api/v1/pantry", {
      data: { ingredient_id: asparagoId, status: "low" },
    });
    expect(asparago.ok()).toBe(true);
    const asparagoVoce = ((await asparago.json()) as { id: string }).id;
    confezioni.push(asparagoVoce);
    const fave = await page.request.post("/api/v1/pantry", { data: { ingredient_id: faveId } });
    expect(fave.ok()).toBe(true);
    confezioni.push(((await fave.json()) as { id: string }).id);

    // 1. In Dispensa la riga gialla dice «Quasi finito» e offre «In lista»; la verde no
    await page.getByRole("link", { name: "Dispensa", exact: true }).click();
    const rigaAsparago = page.locator("li", { hasText: "asparago" });
    const rigaFave = page.locator("li", { hasText: "fave" });
    const parola = rigaAsparago.getByText("Quasi finito", { exact: true });
    const inListaBottone = rigaAsparago.getByRole("button", { name: "In lista", exact: true });
    await expect(parola).toBeVisible();
    await expect(inListaBottone).toBeVisible();
    await expect(rigaFave.getByRole("button", { name: "In lista", exact: true })).toHaveCount(0);
    const scatola = (await inListaBottone.boundingBox())!;
    expect(scatola.width).toBeGreaterThanOrEqual(44);
    expect(scatola.height).toBeGreaterThanOrEqual(44);
    await senzaScorrimentoLaterale(page, "la dispensa con una riga gialla");
    for (const tema of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: tema });
      await fermo(page);
      expect(await testiIlleggibili(page), `dispensa con la riga gialla, tema ${tema}`).toEqual([]);
      const token = tema === "light" ? tokenDelTema : tokenDelTemaScuro;
      const misura = await contrastoAVideo(parola);
      expect(misura.colore, `«Quasi finito», tema ${tema}`).toBe(token("low"));
      expect(misura.rapporto).toBeGreaterThanOrEqual(4.5);
    }
    await page.emulateMedia({ colorScheme: "light" });

    // il tocco rimette in lista come una richiesta a mano, e la riga resta gialla
    await inListaBottone.click();
    await expect(page.getByText("Rimesso in lista: asparago")).toBeVisible();
    await expect(rigaAsparago.getByText("Già in lista")).toBeVisible();
    await expect(
      rigaAsparago.getByRole("radio", { name: "Quasi finito", exact: true })
    ).toHaveAttribute("aria-checked", "true");
    const dallaDispensa = await inLista(asparagoId);
    expect(dallaDispensa.map((voce) => voce.reason)).toEqual(["manual"]);
    // si toglie, perché il foglio della cottura possa rimetterla in lista lui
    const tolta = await page.request.patch(`/api/v1/shopping-list/${dallaDispensa[0].id}`, {
      data: { status: "archived" },
    });
    expect(tolta.ok()).toBe(true);

    // 2. Il foglio della cottura: la confezione già gialla ha la casella, vuota
    const creata = await page.request.post("/api/v1/recipes", {
      data: {
        title: `Rimetti in lista e2e ${Date.now()}`,
        instructions: "1. Lessa gli asparagi.\n2. Unisci le fave.",
        servings: 2,
        source: "manual",
        ingredients: [
          { ingredient_id: asparagoId, role: "primary", quantity_text: "8 gambi" },
          { ingredient_id: faveId, role: "secondary", quantity_text: "100 g" },
        ],
      },
    });
    expect(creata.ok()).toBe(true);
    ricettaId = ((await creata.json()) as { id: string }).id;
    await page.goto(`/ricette/${ricettaId}`);
    await page.getByRole("button", { name: "Cucina", exact: true }).click();

    const tacche = page.getByRole("radiogroup", { name: /asparago/ });
    await expect(tacche.getByRole("radio", { name: "Quasi finito", exact: true })).toHaveAttribute(
      "aria-checked",
      "true"
    );
    const casella = page.getByRole("checkbox", { name: /Rimetti in lista asparago/ });
    await expect(casella).toBeVisible();
    await expect(casella).not.toBeChecked();
    await expect(page.getByRole("checkbox", { name: /Rimetti in lista fave/ })).toHaveCount(0);
    await senzaScorrimentoLaterale(page, "il foglio della cottura con una confezione gialla");
    for (const tema of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: tema });
      await fermo(page);
      expect(await testiIlleggibili(page), `foglio con la casella del giallo, tema ${tema}`).toEqual([]);
    }
    await page.emulateMedia({ colorScheme: "light" });

    await casella.click();
    await expect(casella).toBeChecked();
    await expect(tacche.getByRole("radio", { name: "Quasi finito", exact: true })).toHaveAttribute(
      "aria-checked",
      "true"
    );
    await page.getByRole("button", { name: "Ho cucinato", exact: true }).click();
    // per il testo: l'avviso unico tiene sempre la sua regione
    await expect(page.getByRole("status").filter({ hasText: /^Segnato\./ })).toHaveText(
      "Segnato. Una cosa è tornata in lista della spesa."
    );

    // la confezione è ancora gialla, e la voce in lista ha il motivo del giallo
    const dispensa = (await (await page.request.get("/api/v1/pantry")).json()) as {
      id: string;
      status: string;
    }[];
    expect(dispensa.find((voce) => voce.id === asparagoVoce)?.status).toBe("low");
    expect((await inLista(asparagoId)).map((voce) => voce.reason)).toEqual(["low_while_cooking"]);

    // 3. In Lista la nota del rientro lo dice
    await page.getByRole("link", { name: "Lista", exact: true }).click();
    await expect(
      page.locator("li", { hasText: "asparago" }).getByText("rientrata perché quasi finita cucinando")
    ).toBeVisible();
  } finally {
    for (const id of [asparagoId, faveId]) {
      for (const voce of await inLista(id)) {
        const tolta = await page.request.patch(`/api/v1/shopping-list/${voce.id}`, {
          data: { status: "archived" },
        });
        expect.soft(tolta.ok(), `archiviare la voce di lista ${voce.id}`).toBe(true);
      }
    }
    for (const id of confezioni) {
      const tolta = await page.request.patch(`/api/v1/pantry/${id}`, { data: { archived: true } });
      expect.soft(tolta.ok(), `archiviare la confezione ${id}`).toBe(true);
    }
    if (ricettaId) {
      const tolta = await page.request.patch(`/api/v1/recipes/${ricettaId}`, {
        data: { archived: true },
      });
      expect.soft(tolta.ok(), `eliminare la ricetta ${ricettaId}`).toBe(true);
    }
  }
});
```

Note per chi la esegue:
- Se `contrastoAVideo`, `tokenDelTemaScuro` o `senzaScorrimentoLaterale` sul ramo hanno un'altra firma (il piano del tema scuro e S15 possono averli toccati), usali come li usano le prove più recenti del file e scrivilo nel report.
- Se la misura del contrasto dà «Quasi finito» sotto 4,5:1, **non cambiare token**: scrivi nel report su quale fondo, in quale tema e con quale rapporto, e segna il task `bloccato` — un colore si decide di giorno.
- Se una prova di oggi fallisce perché cerca `/Rimetti in lista/` senza nome e ora trova anche la casella di una confezione gialla, applica l'eccezione di «Margine di autonomia» (aggiungi il nome dell'ingrediente) e scrivilo nel report.

- [ ] **Step 2: Il tipo del file**

Run (da `<worktree>/frontend`): `npm run typecheck && npm run lint`
Expected: puliti. `tsc -b` compila anche gli e2e (`tsconfig.node.json`, senza la libreria DOM).

- [ ] **Step 3: Lo stack e2e, e l'e2e intera**

Dalla radice di `<worktree>`, con i comandi delle Global Constraints: `cp .env.example .env`, `up -d --build --wait`, il seme `--con-ricette`, poi `(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)`.
Expected: tutti verdi, **una prova più del conto e2e di S15** (nel suo report della notte; se non lo trovi, conta le prove con `npx playwright test --list | tail -n 1` sul ramo prima di questo task e aggiungi uno). Annota il numero (`N_e2e`). Le prove di oggi sul foglio della cottura passano: in «il foglio della cottura a 375px…» il porro e la scamorza gialli ora mostrano la loro casella, vuota, e l'avviso conta ancora una cosa sola (il radicchio).

Se una prova fallisce e lascia dati nello stack, prima di rieseguire ricrea lo stack da zero (`down -v`, `up`, seme). Alla fine, sempre:

```bash
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
rm .env
```

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/style.spec.ts
git commit -m "e2e: «Rimetti in lista» a 375px — «In lista» sulla riga gialla nei due temi, il foglio che rimette in lista una gialla senza toccarla, il motivo giusto in lista"
```

---

### Task 5: I documenti

**Files:**
- Modify: `docs/prossimi-passi.md`
- Modify: `next-steps.md`

Leggi prima i due file com'è sul ramo: i piani prima di questo li hanno aggiornati.

- [ ] **Step 1: Le due note di Parte X in `docs/prossimi-passi.md`**

1. La nota che comincia con `- **Nel foglio della cottura la casella «Rimetti in lista» è pre-spuntata solo per` e finisce con `deciderlo una volta invece di riscoprirlo.` si chiude come le altre chiuse del file (barrata, «Chiusa il …», poi il testo di prima). Sostituisci la sua prima riga, `- **Nel foglio della cottura la casella «Rimetti in lista» è pre-spuntata solo per`, con:
   ```markdown
   - ~~**Nel foglio della cottura la casella «Rimetti in lista» è pre-spuntata solo per
     «finito»**~~ **Chiusa il <data di oggi>, decisa da Mattia il 2026-10-09** (spec
     `docs/superpowers/specs/2026-10-09-rimetti-in-lista-design.md`, piano
     `docs/superpowers/plans/2026-10-09-rimetti-in-lista.md`, sul ramo
     `night/rimetti-in-lista`, non ancora in produzione): «anche quasi finito, ovunque». In
     Dispensa «In lista» / «Già in lista» c'è anche sulle righe gialle, con la parola «Quasi
     finito»; nel foglio la casella c'è quando la confezione dopo la cottura è gialla (vuota)
     o rossa (spuntata), **anche se era già gialla prima**: spuntata, parte come transizione
     allo stesso stato, che `cook` non applica alla voce (né stato, né `status_changed_at`)
     e che rientra in lista col motivo `low_while_cooking`; `updated` conta solo gli stati
     cambiati. Quali stati offrono il rientro lo dice una funzione sola, `offersRestock` in
     `statusLabels.ts`, per le due sezioni. Il rientro dalla Dispensa resta `manual`. Il
     testo di prima, per la storia:
     **Nel foglio della cottura la casella «Rimetti in lista» è pre-spuntata solo per
   ```
   e lascia com'è il resto della nota (da `«finito»** (\`frontend/src/features/cooking/CookSheet.tsx\`)…` fino a `…invece di riscoprirlo.`), che ora è il testo di prima. Se in Markdown le righe del testo di prima perdono il rientro di due spazi, rimettilo: devono restare dentro la stessa voce dell'elenco.
2. Nella nota che comincia con `- **\`PantryRow.tsx\` è il file più affollato dell'app**`, dopo la frase che finisce con `la scadenza è il` / `secondo candidato.` aggiungi:
   ```markdown
     **Il primo taglio è fatto il <data di oggi>, con «Rimetti in lista»**: la riga del
     rientro («Finito» o «Quasi finito», e «In lista» o «Già in lista») è
     `features/pantry/RestockLine.tsx`. La lapide e l'esito non c'erano più dal ridisegno di
     T3: l'avviso lo dà `PantryScreen`. Resta la scadenza.
   ```
3. Sostituisci `<data di oggi>` con la data vera, in tutti e due i punti.

- [ ] **Step 2: `next-steps.md`**

1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte)_`.
2. Togli la riga di «Rimetti in lista» da «In corso» (l'ha messa lì la Preparazione); se «In corso» resta vuota, rimetti `_(niente)_`.
3. In cima a «Fatti (recenti)» aggiungi:
   ```markdown
   - [fatto] <data di oggi> · «Rimetti in lista» anche per quasi finito: in Dispensa «In lista» / «Già in lista» anche sulle righe gialle (la riga del rientro esce in `RestockLine`), nel foglio della cottura la casella anche su una confezione già gialla, che spuntata rientra in lista senza toccarla (transizione allo stesso stato, motivo `low_while_cooking`); `offersRestock` è la regola per le due sezioni [Parte X] → branch night/rimetti-in-lista (da revisionare)
   ```
4. In «Idee», la riga
   ```markdown
   - [idea] P3 · Estrarre da `PantryRow.tsx` la domanda del rientro in lista, poi la scadenza [Parte X]
   ```
   diventa
   ```markdown
   - [idea] P3 · Estrarre da `PantryRow.tsx` la scadenza (la domanda del rientro è uscita in `RestockLine.tsx` con «Rimetti in lista», sul ramo night/rimetti-in-lista) [Parte X]
   ```
5. In cima a «Da fare a mano (solo Mattia)» aggiungi:
   ```markdown
   - [tbd] P3 · Prova sul telefono di «Rimetti in lista»: «In lista» sulla riga gialla col pollice, e nel foglio della cottura la casella su una confezione già quasi finita [Parte X]
   ```
6. Se nella notte sono emerse altre cose da fare fuori da questo piano, aggiungile come `idea` o `tbd` nella sezione giusta, con la voce di `docs/prossimi-passi.md` fra parentesi quadre.

- [ ] **Step 3: Commit**

```bash
git add docs/prossimi-passi.md next-steps.md
git commit -m "docs: «Rimetti in lista» fatto sul ramo — la nota di Parte X chiusa, l'estrazione di PantryRow a metà, una prova sul telefono"
```

---

### Task 6: La verifica finale, e il report

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

Expected: vitest tutto verde — **`N_vitest` della Preparazione più 13**, cioè 1 (`statusLabels.test.ts`) + 6 (`RestockLine.test.tsx`) + 1 (`PantryRow.test.tsx`: uno cambiato, uno nuovo) + 1 (`PantryScreen.test.tsx`) + 4 (`CookSheet.test.tsx`), in **`N_file` + 1** file. Se il numero differisce, scrivi nel report da dove viene la differenza. Typecheck, lint e build puliti. `npx tsc -b --force` perché `node_modules` è condiviso col checkout principale, e con lui il `tsbuildinfo`: `--force` compila davvero tutto.

- [ ] **Step 2: Il backend**

Da `<worktree>/backend`:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_rimetti PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Expected: tutto verde, **`N_pytest` + 4**.

- [ ] **Step 3: I controlli dalla radice**

```bash
grep -rn "emerald\|neutral-" frontend/src
git diff night/s15-reparti-collassabili --stat -- frontend/src/features/shopping-list frontend/src/features/stocking backend/alembic frontend/src/index.css
grep -rn "offersRestock" frontend/src | grep -v "\.test\."
git diff night/s15-reparti-collassabili --stat
```

Expected: vuoto; vuoto; righe solo in `features/pantry/statusLabels.ts`, `features/pantry/RestockLine.tsx` e `features/cooking/CookSheet.tsx`; l'ultimo elenca solo i file della tabella «File toccati» (più `docs/night-reports/` dopo lo Step 6).

- [ ] **Step 4: L'e2e intera**

Con i comandi delle Global Constraints, su uno stack ricreato da zero (`down -v` prima dell'`up`, se ne era rimasto uno di questo ramo). Expected: tutti verdi, `N_e2e` del Task 4. Poi `down -v` e `rm .env`, sempre.

- [ ] **Step 5: Il database dei test**

Dopo l'ultimo pytest:

```bash
docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_rimetti WITH (FORCE)'
```

- [ ] **Step 6: Il report**

Nel report della notte (`docs/night-reports/<data>.md`, sul ramo; se il file c'è già perché un piano prima di questo l'ha scritto sul suo ramo, qui sul tuo ramo aggiungi una sezione «Rimetti in lista» senza toccare le altre), per questo piano: il ramo e da dove parte; i conti veri (vitest, pytest, e2e) contro quelli della Preparazione; cosa hanno trovato i controlli della Preparazione sui file già toccati da S3, S12, il tema scuro, S14 e S15, e dove le ancore del piano non c'erano più com'erano scritte; i due test di oggi cambiati per la decisione di Mattia (Task 2 e 3) e ogni altro test migrato con l'eccezione di «Margine di autonomia», col perché; le scelte prese in autonomia; le **tre decisioni di Mattia del 2026-10-09** (anche quasi finito, ovunque; la casella anche su una gialla invariata, che rientra senza toccarla col motivo del giallo; le scelte estetiche delegate) e quella del 2026-10-13 (il titolo chiuso di S15 non conta le quasi finite). Poi:

```bash
git add docs/night-reports/
git commit -m "docs: il report della notte per «Rimetti in lista»"
```

Niente push, niente merge, niente deploy.

## Dopo il deploy (solo Mattia)

Nessuna azione: il piano non tocca lo schema né i dati. Le confezioni gialle che ci sono già mostrano «In lista» dal primo caricamento della Dispensa.
