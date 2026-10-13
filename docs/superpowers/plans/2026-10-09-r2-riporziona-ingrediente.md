# R2, secondo modo — riporzionare da un ingrediente: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** nel dettaglio della ricetta ogni dose riscalabile si tocca e apre sotto la riga «Quanto ne fai?»; scritta la dose, il backend riscala tutte le altre righe da lì, lo stepper dice le porzioni equivalenti («≈ 1,5») e − / + tornano alle porzioni intere; niente si salva, e la cottura registra la dose nello `snapshot`.

**Architecture:** tre funzioni pure nuove in `backend/app/domain/quantities.py` (`anchor_factor`, `equivalent_servings`, `decimal_text`, con `ANCHOR_MAX_FACTOR = 50`); un modulo di servizio nuovo, `backend/app/services/rescale.py`, che trova la riga d'ancora e risolve il fattore (`resolve_anchor`) per **due** chiamanti — `_to_out` del dettaglio e `cook` della cottura —, così la riga che il dettaglio mostra come ancora è la stessa che la cottura registra. `GET /api/v1/recipes/{id}` prende `anchor` + `amount` accanto a `servings` (un modo alla volta, 422 oltre le 50 volte con la frase); `POST /recipes/{id}/cook` prende la stessa coppia e la scrive in `snapshot["anchor"]`, con `servings` null. Nessuna migrazione. Nel frontend: i tipi e `fetchRecipe` con un `RecipeScale`; il 422 non si ritenta; `ServingsStepper` con `approx`; due pezzi nuovi in `features/cooking/` — `anchorAmount.ts` (legge il numero scritto) e `AnchorField.tsx` (il campo) —; `RecipeDetailScreen` li monta, chiedendo la ricetta riscalata con `fetchQuery` **prima** di cambiare vista; `CookSheet` manda l'ancora.

**Tech Stack:** FastAPI 0.141, Pydantic 2, SQLAlchemy 2 async, pytest su Postgres vero; React 19, TypeScript, Tailwind 4 (token in `@theme`), TanStack Query 5, Vitest + Testing Library (jsdom), Playwright.

**Spec:** `docs/superpowers/specs/2026-10-09-r2-riporziona-ingrediente-design.md` (scritta con questo piano: le tre decisioni di Mattia del 2026-10-09 al §2, quelle di Claude su delega al §3, le parole a video al §4, con l'etichetta decisa da Mattia il 2026-10-13). Il ragionamento d'archivio è in `docs/prossimi-passi.md`, voce «## R2. Riporziona»; il primo modo è nella spec `docs/superpowers/specs/2026-09-20-quantita-ricette-design.md`, §5. La riga di `next-steps.md` che questo piano chiude comincia con «R2, secondo modo».

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/r2-riporziona-ingrediente` (`.worktrees/` è già in `.gitignore`), ramo `night/r2-riporziona-ingrediente`, creato da **`master`**: questo piano è l'ottavo della notte ma non dipende dalla catena dei sette prima di lui, e nessuno dei suoi file aspetta il loro lavoro. Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì (o dalle sue `backend/` e `frontend/`), mai dalla radice del checkout principale. Il checkout principale non si tocca: se vi trovi modifiche non committate, sono dell'utente. **Nessun push, nessun merge, nessun deploy. Mai `git stash`.**
- **I file che anche altri piani della notte toccano** — `frontend/src/domain/types.ts` (S12, S14, S15 cambiano `PantryItem` e altre interfacce; questo piano cambia `RecipeIngredientLine` e `RecipeDetail`), `frontend/src/features/cooking/CookSheet.tsx` e il suo test, `backend/app/services/cooking.py` e `backend/app/api/cooking.py` («Rimetti in lista», piano 7, cambia il ciclo delle transizioni e il conto di `updated`), `frontend/src/features/cooking/RecipeDetailScreen.test.tsx` (S12 e S14 aggiungono campi alle voci di `PANTRY`), `frontend/e2e/style.spec.ts` (quasi tutti), `next-steps.md`, `docs/prossimi-passi.md`, il report della notte. Sul tuo ramo, che parte da `master`, sono come su `master`. Il piano descrive comunque ogni modifica a un file esistente contro un'ancora riconoscibile — una funzione, un campo, un elemento JSX, un testo esatto — e mai contro numeri di riga: **leggi il file com'è sul ramo prima di cambiarlo**. Dove il piano dà un file intero è un file nuovo, oppure `ServingsStepper.tsx`, che nessun piano della notte tocca (la Preparazione lo verifica). Le prove nuove di `style.spec.ts` vanno **in fondo al file**; al merge, l'unione con quelle degli altri rami la fa la revisione.
- **Il frontend non calcola logica di dominio.** Il fattore, le dosi riscalate, le porzioni equivalenti, il limite delle 50 volte e la frase che lo dice stanno nel backend. Nel frontend restano: leggere il numero scritto (forma, virgola → punto), scrivere `equivalent_servings` con la virgola, e il passo dello stepper all'intero sotto e sopra.
- **Decisione fondante 1** (`CLAUDE.md`): `quantity_text` non si riscrive mai (a 1× si mostra lui); una riga senza dose strutturata non si riscala, e si conta in `unscalable_lines`. La dispensa e la lista non cambiano di una riga.
- **Mai un vicolo cieco.** Un'ancora che la ricetta non ha più si ignora (la ricetta com'è); oltre le 50 volte la frase del server resta sotto il campo e la ricetta resta com'era; un server che non risponde lascia il campo aperto con «Non sono riuscito a riscalare. Riprova.»; una vista già accettata che smette di valere porta a «Torna alle dosi della ricetta», non a un «Riprova» che rifarebbe la stessa domanda; una cottura con un'ancora che non vale più si cucina lo stesso.
- Tutto il colore passa dai token di `frontend/src/index.css`. **Nessun token nuovo.** Nessuna schermata nomina un colore crudo: `grep -rn "emerald\|neutral-" frontend/src` resta vuoto. Ogni testo sta sopra 4,5:1, in chiaro e in scuro, e lo misura `frontend/e2e/style.spec.ts`. Niente classi in conflitto sullo stesso elemento (due `text-*` o due `px-*`): fra due utilità della stessa proprietà decide l'ordine del CSS compilato, non quello scritto (`buttonClasses.ts` lo racconta per i raggi). Per evidenziare la dose fissata si avvolge il testo in un `<strong>`, non si aggiunge una classe al pulsante.
- **`Button`** (`frontend/src/components/ui/Button.tsx`) non cambia. **La regola (di Mattia):** in volo → `busy`; «non ancora» → `unavailableReason` (il perché sotto, `aria-disabled`, il fuoco resta); `disabled` nativo solo dove nessuno dei due vale. Ogni bersaglio nuovo è almeno 44×44 px (`min-h-11` viene da `buttonClasses`). A 375 px nessuna schermata scorre di lato.
- Le parole a video sono in italiano e **si copiano esattamente come sono scritte qui**; gli identificatori in inglese; i commenti in italiano come nel resto del codice. Il nome di un ingrediente dentro una frase o un nome accessibile resta minuscolo (scelta 20 del piano della Consegna 6b): «Riscalata da pasta: 135 g.», «180 g: riscala da pasta».
- **Il type check è `npm run typecheck`** (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0 (settima lezione di `CLAUDE.md`).
- Controlli del frontend, da `<worktree>/frontend`: `npx vitest run` (non esiste `npm test`), `npm run typecheck`, `npm run lint`, `npm run build`.
- **Backend su Postgres vero.** Il database dei test è il container `spena-db-1` (porta 5433), da usare solo come database dei test: se `docker ps --format '{{.Names}}'` non lo mostra, `docker start spena-db-1`. **Mai `docker compose up` dal worktree** (il nome del progetto Compose viene dalla cartella: nascerebbe un secondo Postgres che litiga sulla 5433), mai `-f docker-compose.prod.yml`. Questo ramo parte da `master` e **non aggiunge migrazioni**: usa `spena_test`, il database dei rami che partono da `master` (i rami dopo S12, che porta la `0013`, ne usano uno loro). Nel worktree non c'è un `.venv`: si usa quello del checkout principale; `python -m` mette la cartella corrente in testa a `sys.path`, quindi si prova l'`app` del worktree. Il comando, sempre da `<worktree>/backend` (dove un task dice «il comando di pytest» intende questo, con i percorsi che il task indica in coda):
  ```bash
  PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
  Se la Preparazione trova `spena_test` già portato oltre la `0012` da un altro ramo, ogni pytest di questo piano prende davanti `TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_r2` (vedi la Preparazione). Se un test sembra ignorare una modifica, `python -c 'import app; print(app.__file__)'` da `<worktree>/backend` (con lo stesso `PATH`) deve stampare un percorso dentro il worktree. Nessuna chiamata di rete nella suite.
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
- **Niente produzione, di notte.** Nessuna lettura né scrittura sui dati veri. Questo piano non ha azioni da fare dopo il deploy oltre al deploy stesso (nessuna migrazione, nessun comando).
- Nessuna dipendenza nuova, nessuna migrazione, nessun cambio di configurazione globale.

### Preparazione (una volta, prima del Task 1)

- [ ] Il ramo di partenza è `master`, e i file di questo piano sono quelli su cui è scritto (`master` era `1df86c7` quando il piano è stato scritto):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify master
  git diff --stat 1df86c7 master -- \
    backend/app/domain/quantities.py backend/app/api/recipes.py backend/app/schemas/recipe.py \
    backend/app/services/cooking.py backend/app/api/cooking.py backend/app/schemas/cooking.py \
    frontend/src/domain/types.ts frontend/src/features/recipes/api.ts frontend/src/lib/queryRetry.ts \
    frontend/src/features/cooking/
  ls backend/app/services/rescale.py frontend/src/features/cooking/AnchorField.tsx \
    frontend/src/features/cooking/anchorAmount.ts frontend/e2e/riporziona.spec.ts 2>&1 | grep -c "No such file"
  ```
  Expected: un hash; il `diff --stat` **vuoto**; `4` (i quattro file nuovi non esistono ancora). Se il `diff` non è vuoto, `master` è andato avanti su questi file: applica le modifiche del piano sopra la versione di `master`, ancora per ancora, e scrivilo nel report; se a cambiare è `ServingsStepper.tsx`, non sovrascriverlo col file intero del Task 5: porta le sue modifiche dentro la versione del ramo. Se uno dei quattro file nuovi esiste già, **fermati**: qualcuno ha già cominciato questa voce; scrivi nel report della notte (`docs/night-reports/<data>.md`, sul ramo `night/r2-riporziona-ingrediente` appena creato) cosa hai trovato, segna la voce `bloccato` in `next-steps.md` di quel ramo con la domanda per Mattia, e non partire.
- [ ] Il database dei test:
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d spena_test -tAc 'SELECT version_num FROM alembic_version'
  ```
  Expected: `0012`. Se stampa altro (per esempio `0013`, lasciata da un ramo della catena che ha usato il database sbagliato), **non toccare `spena_test`**: crea il database di questo ramo e usalo per tutta la notte, mettendo `TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_r2` davanti a ogni comando di pytest di questo piano, e scrivilo nel report:
  ```bash
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_r2 WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_r2'
  ```
  (in quel caso, alla fine del Task 9, `DROP DATABASE IF EXISTS spena_test_r2 WITH (FORCE)`).
- [ ] Dal checkout principale, allinea `node_modules` al lockfile (non aggiunge dipendenze, installa quelle di `package-lock.json`):
  ```bash
  cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund
  ```
- [ ] Crea il worktree da `master` e collega `node_modules` (e solo quello: **niente `.env`**):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/r2-riporziona-ingrediente -b night/r2-riporziona-ingrediente master
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/r2-riporziona-ingrediente/frontend/node_modules
  ```
- [ ] La voce in `next-steps.md` del ramo passa a `in corso` (cercala per testo, `grep -n "R2, secondo modo" next-steps.md`: di giorno può essere stata spostata in «Pronti per la notte»; cambia solo lo stato fra parentesi quadre) e si committa:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/r2-riporziona-ingrediente
  git add next-steps.md
  git commit -m "next-steps: R2 secondo modo, in corso"
  ```
- [ ] La linea di partenza, dal worktree:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/r2-riporziona-ingrediente/frontend && npx vitest run 2>&1 | grep -E "Test Files|Tests "
  cd ../backend && PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q 2>&1 | tail -n 1
  ```
  Expected: tutto verde. **Annota i numeri** (file e test di vitest, test di pytest): sono `N_file`, `N_vitest`, `N_pytest` del Task 9. Se una delle due linee non è verde, fermati: non è un difetto di questo piano, e va scritto nel report.

---

## Obiettivo e contesto

Il riporziona per porzioni è in produzione dal 2026-09-20: lo stepper chiede `?servings=N`, il backend riscala le righe che hanno una dose strutturata e dichiara quelle che non si riscalano. Manca il modo che le altre app non hanno: **partire dalla dose di un ingrediente** — «la ricetta è per 400 g di pasta, io ne faccio 150 g». La matematica è la stessa (un fattore per riga, `scale_quantity`); cambia da dove viene il fattore, e come lo si chiede. Mattia ha deciso il 2026-10-09 che è una vista e basta, che si chiede toccando la dose, e che i due modi non convivono: con un ingrediente fissato lo stepper dice le porzioni equivalenti, e toccarlo torna alle porzioni intere.

## Decisioni prese

Di Mattia, il 2026-10-09:

1. **Solo vista**, come lo stepper: niente si salva sulla ricetta, né come ricetta nuova.
2. **Il gesto parte da un tocco sulla dose della riga**: ogni dose riscalabile è toccabile e apre sotto la riga un campo per dire quanto se ne fa, con l'unità della riga. Le righe senza dose strutturata non lo offrono.
3. **Un modo alla volta**: con un ingrediente fissato lo stepper dice le porzioni equivalenti («≈ 1,5 porzioni»); toccare − o + torna al modo per porzioni intere.

Di Claude, su delega di Mattia (tecniche o estetiche; il perché è nella spec, §3):

4. **Il contratto:** `GET /api/v1/recipes/{id}?anchor=<ingredient_id>&amount=<decimale col punto>`. `anchor` e `amount` insieme o niente; mai con `servings` (422). `amount` > 0, < 10 000 000, al massimo tre decimali. La riga d'ancora mostra esattamente la dose scritta. Un'ancora che la ricetta non ha (o una riga senza dose strutturata > 0) si ignora: `anchor: null` e la ricetta com'è. Fattore 1 = come non chiedere niente (l'ancora resta nella risposta). Per riga `anchorable` e `anchor_unit`; per la ricetta `anchor: {ingredient_id, amount, equivalent_servings} | null`; `scaled_to` resta del modo per porzioni.
5. **Il limite: 50 volte** (`ANCHOR_MAX_FACTOR`), lo stesso massimo dello stepper; oltre, 422 con «Così la ricetta cambierebbe più di 50 volte: scrivi un numero fra {minimo} e {massimo}.», estremi già scalati e scritti con l'unità della riga.
6. **Le porzioni equivalenti** (`equivalent_servings`): metà in su, un decimale da 1 in su, due sotto; `null` senza porzioni nella ricetta.
7. **Lo stepper con un ingrediente fissato:** «≈ 1,5»; − all'intero sotto, + all'intero sopra, dentro 1–50.
8. **Ricette senza porzioni:** il fattore vale; lo stepper resta com'è oggi su di loro («—», spento, col perché).
9. **«Riscalata da {nome}: {dose}.»** sotto lo stepper con **«Torna alle dosi della ricetta»** (`ghost`), in ogni vista riscalata da una dose.
10. **Il campo:** «Quanto ne fai?», casella `inputMode="decimal"` col fuoco, l'unità accanto, «Riscala» (`secondary`, `submit`) e «Annulla» (`ghost`); si riscala al tocco o all'Invio, non a ogni cifra; la ricetta riscalata si chiede **prima** di cambiare vista (`queryClient.fetchQuery`): un 422 resta sotto il campo con la frase del server; un altro guasto, «Non sono riuscito a riscalare. Riprova.»; riuscito, il campo si chiude e il fuoco torna sulla dose. Un campo aperto alla volta; il campo di una riga già fissata parte dalla sua dose.
11. **La dose toccabile:** `Button variant="ghost"` sottolineato a puntini, nome «{dose}: riscala da {nome}», `aria-expanded`; la dose fissata in `<strong>`. «q.b.» resta testo.
12. **La cottura:** manda `anchor` + `amount` al posto di `servings`; `cooking_events.servings` resta null; `snapshot["anchor"] = {ingredient_id, amount, unit, factor, equivalent_servings}` (stringhe col punto o null); un'ancora che al momento della cottura non vale più si registra con `factor: null` e la cottura riesce. Nessuna migrazione.
13. **«Metti in lista ciò che manca» e il foglio della cottura** non cambiano a video.
14. **Il 422 non si ritenta** (`queryRetry.ts`); una vista riscalata già accettata che torna 422 porta a «Non riesco più a riscalare da quella dose: la ricetta è cambiata.» con «Torna alle dosi della ricetta».

Scelte interne di questo piano (Claude, su delega; reversibili):

15. **`resolve_anchor` in un modulo di servizio suo**, `backend/app/services/rescale.py`, con `is_anchorable`, `anchor_unit`, `unit_forms`, `find_anchor_line` e l'eccezione `AnchorRefused` che porta la frase. Il dominio (`quantities.py`) resta puro e non sa cos'è una riga di ricetta. Il dettaglio e la cottura chiamano la stessa funzione: la prima lezione di `CLAUDE.md`.
16. **`amount` torna come stringa** (`decimal_text`: col punto, senza esponente) e **`equivalent_servings` come numero** (`float`, già arrotondato): il primo deve tornare tale e quale alla cottura; il secondo il frontend lo scrive con `toLocaleString("it-IT")`.
17. **I test nuovi del backend in file nuovi** (`test_recipes_riporziona_ingrediente.py`, `test_cooking_riporziona.py`): `test_cooking.py` lo cambia il piano 7 stanotte.
18. **Una rilettura in più**: dopo `fetchQuery`, la query del dettaglio con la chiave nuova trova il dato già pronto e lo rilegge comunque in sottofondo (è vecchio da subito, `staleTime` 0). È quel che rende possibile la decisione 14, e costa una `GET` leggera.

**L'etichetta del campo, decisa da Mattia il 2026-10-13: «Quanto ne fai?».** Mattia aveva scritto «Quanti g ne fai?». Con l'unità dentro la domanda l'accordo dipende dall'unità, e il registro delle unità non sa il genere: nel seme ci sono «fette», «scatole», «coste», «tazzine», «bustina», «medie» («Quanti fette ne fai?»), e i numeri nudi non hanno unità. **Si scrive «Quanto ne fai?» con l'unità accanto alla casella** («Quanto ne fai? [150] g»), giusta per ogni riga. Le alternative scartate: la domanda letterale «Quanti {unità} ne fai?» (sbagliata con le unità femminili); il genere nel registro delle unità (colonna, migrazione, l'AI che lo decide), fuori da questa voce.

## Criteri di accettazione

- [ ] `GET /api/v1/recipes/{id}?anchor=…&amount=112.5` su una ricetta per 4 con «300 g» di pasta risponde la pasta «112,5 g», «1» cipolla → «0,375», «q.b.» com'è e contata, `scaled_to` null, `anchor` = `{ingredient_id, "112.5", 1.5}`; ogni riga ha `anchorable` e `anchor_unit` («g» / null).
- [ ] Oltre 50 volte: 422 con «Così la ricetta cambierebbe più di 50 volte: scrivi un numero fra 6 g e 15000 g.»; i due estremi si accettano. Un'ancora che la ricetta non ha si ignora. `anchor` senza `amount`, `amount` senza `anchor`, `anchor` con `servings`, `amount` non valido: 422.
- [ ] `POST /recipes/{id}/cook` con `anchor` + `amount`: `servings` null, `snapshot["anchor"]` = `{ingredient_id, amount, unit, factor, equivalent_servings}`; senza ancora lo `snapshot` è quello di sempre; un'ancora che non vale più non blocca la cottura (`factor: null`); i parametri sbagliati 422 senza scrivere niente.
- [ ] Nel dettaglio la dose «180 g» di pasta è un pulsante «180 g: riscala da pasta», alto 44 px, sottolineato a puntini; «q.b.» no. Il tocco apre «Quanto ne fai?» sotto la riga, col fuoco e l'unità accanto; uno alla volta; «Riscala» non ancora pronto dice perché.
- [ ] Scritto «135» e «Riscala»: «135 g», «300 g», «≈ 1,5», «Riscalata da pasta: 135 g.», «Torna alle dosi della ricetta», il campo chiuso e il fuoco sulla dose. + va a 2 porzioni, − a 1. «Torna alle dosi della ricetta» toglie l'ancora.
- [ ] Oltre il limite: la frase del server sotto il campo, la ricetta com'era. Server che non risponde: «Non sono riuscito a riscalare. Riprova.». Vista che smette di valere: «Non riesco più a riscalare da quella dose: la ricetta è cambiata.» con l'uscita.
- [ ] Senza porzioni: si riscala lo stesso; lo stepper resta «—», spento, col suo perché.
- [ ] «Ho cucinato» in una vista riscalata da una dose manda `anchor` e `amount`, non `servings`.
- [ ] Un 422 non si ritenta.
- [ ] Tutti i test di oggi passano; quelli toccati lo sono solo per i campi nuovi delle voci finte (Task 4), mai indeboliti.
- [ ] vitest, typecheck, lint, build, pytest e l'e2e intera verdi; `riporziona.spec.ts` ha due prove, `style.spec.ts` una in più.
- [ ] `docs/prossimi-passi.md` e `next-steps.md` aggiornati (Task 8).

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
git diff master --stat -- backend/alembic
grep -rn "Quanti g ne fai" frontend/src frontend/e2e
```

Expected: i tre comandi non stampano niente. E l'e2e intera con i comandi delle Global Constraints.

## Fuori scope

- Salvare una riporzionatura (decisione 1); ricordare la vista uscendo dalla ricetta.
- Riscalare da una riga senza dose strutturata; correggere da qui una dose letta male (si fa da «Modifica»).
- Le conversioni fra unità («1 kg» su una riga in grammi): la dose si scrive nell'unità della riga. I grammi della coppia ingrediente × unità sono di S4.
- Il genere delle unità nel registro (vedi l'etichetta del campo, sopra).
- Il «−» dello stepper spento con `disabled` a 1 porzione: è già un'idea a sé in `next-steps.md`; qui il «−» si spegne allo stesso modo anche sotto una porzione equivalente.
- Tutto quel che fanno gli altri piani della notte.

## Margine di autonomia

- **Liberi:** i nomi di variabili locali, helper di test e funzioni interne non fissati qui; l'ordine dei test dentro un file; l'ordine delle classi Tailwind; la formulazione dei commenti, purché dicano il perché.
- **Fissi:** le parole a video, esattamente come sono scritte nel piano; i nomi pubblici che altri task usano (`ANCHOR_MAX_FACTOR`, `ANCHOR_AMOUNT_CEILING`, `AnchorOutOfRange`, `anchor_factor`, `equivalent_servings`, `decimal_text`, `AnchorRefused`, `ResolvedAnchor`, `resolve_anchor`, `find_anchor_line`, `is_anchorable`, `anchor_unit`, `unit_forms`, `anchor_record`, `AnchorOut`, i campi `anchorable`, `anchor_unit`, `anchor`, `RecipeScale`, `RecipeAnchor`, `readAmount`, `AnchorField` e le sue prop, la prop `approx` di `ServingsStepper`); i parametri `anchor` e `amount` dell'API; le chiavi di `snapshot["anchor"]`.
- **Nessuna dipendenza nuova**, nessuna migrazione, nessun token di colore nuovo.
- **Un test di oggi si cambia solo per i campi nuovi delle voci finte** (`anchorable`, `anchor_unit`, `anchor`, Task 4) — mai per indebolirlo. Se ne serve un'altra migrazione, scrivila nel report con il perché.
- **Una decisione di comportamento non coperta e non reversibile** → si ferma quel task, si fa commit del lavoro parziale sul ramo, lo si segna `bloccato` in `next-steps.md` del ramo con la domanda precisa per Mattia, e si passa al task successivo. Una scelta reversibile e a basso impatto → la più conservativa, annotata nel report della notte.
- Se un test fallisce e non si risolve in modo ragionevole: niente test disattivati, niente asserzioni indebolite; `bloccato` con la diagnosi.

## Dipendenze

**Parte da `master`.** Non consuma niente dagli altri piani della notte. Al merge può incontrare, sugli stessi file, il piano 7 («Rimetti in lista», sul ciclo delle transizioni di `cook`, sul conto di `updated` in `api/cooking.py` e sulla scelta delle tacche di `CookSheet.tsx`), S12 e S14 (le voci di `PANTRY` nei test della cottura e del dettaglio, `PantryItem` in `types.ts`) e tutti in `style.spec.ts`: modifiche in punti diversi degli stessi file, che la revisione unisce.

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `backend/app/domain/quantities.py`, `backend/tests/domain/test_quantities.py` | 1 | `ANCHOR_MAX_FACTOR`, `ANCHOR_AMOUNT_CEILING`, `AnchorOutOfRange`, `anchor_factor`, `equivalent_servings`, `decimal_text`; 22 test |
| `backend/app/services/rescale.py` (nuovo) | 2 | `AnchorRefused`, `ResolvedAnchor`, `unit_forms`, `is_anchorable`, `anchor_unit`, `find_anchor_line`, `resolve_anchor` |
| `backend/app/schemas/recipe.py` | 2 | `AnchorOut`; `anchorable`, `anchor_unit` su `RecipeIngredientOut`; `anchor` su `RecipeOut` |
| `backend/app/api/recipes.py` | 2 | `_to_out` con `anchor`; `detail` con `anchor` e `amount` |
| `backend/tests/api/test_recipes_riporziona_ingrediente.py` (nuovo) | 2 | 19 test |
| `backend/app/schemas/cooking.py`, `backend/app/services/cooking.py`, `backend/app/api/cooking.py` | 3 | `anchor` e `amount`; `anchor_record`; lo `snapshot` |
| `backend/tests/api/test_cooking_riporziona.py` (nuovo) | 3 | 9 test |
| `frontend/src/domain/types.ts` | 4 | `anchorable`, `anchor_unit`, `RecipeAnchor`, `anchor` |
| `frontend/src/features/recipes/api.ts`, `api.test.ts` | 4 | `RecipeScale`, `fetchRecipe`, `cookRecipe`; 3 test |
| `frontend/src/lib/queryRetry.ts`, `queryRetry.test.ts` | 4 | il 422 non si ritenta; 1 test |
| `frontend/src/features/cooking/CookSheet.tsx`, `CookSheet.test.tsx` | 4 | manda l'ancora; 1 test |
| le voci finte di `RecipeDetail`/`RecipeIngredientLine` nei test | 4 | i campi nuovi |
| `frontend/src/features/cooking/ServingsStepper.tsx`, `.test.tsx` | 5 | `approx`; 3 test |
| `frontend/src/features/cooking/anchorAmount.ts`, `.test.ts` (nuovi) | 5 | `readAmount`; 16 test |
| `frontend/src/features/cooking/AnchorField.tsx`, `.test.tsx` (nuovi) | 5 | il campo; 8 test |
| `frontend/src/features/cooking/RecipeDetailScreen.tsx`, `.test.tsx` | 6 | la dose toccabile, il campo, la riga sotto lo stepper, il 422; 10 test |
| `frontend/e2e/riporziona.spec.ts` (nuovo), `frontend/e2e/style.spec.ts` | 7 | 2 prove; 1 prova in fondo |
| `docs/prossimi-passi.md`, `next-steps.md` | 8 | i documenti |
| `docs/night-reports/<data>.md` | 9 | il report |

---

### Task 1: Il dominio — il fattore da una dose, le porzioni equivalenti

**Files:**
- Modify: `backend/app/domain/quantities.py` (in fondo, dopo `render_quantity`)
- Test: `backend/tests/domain/test_quantities.py`

**Interfaces:**
- Produces: `ANCHOR_MAX_FACTOR: Decimal` (50), `ANCHOR_AMOUNT_CEILING: Decimal` (10 000 000, escluso), `class AnchorOutOfRange(ValueError)` con `.low: Decimal` e `.high: Decimal`, `anchor_factor(base: Decimal, amount: Decimal) -> Decimal` (solleva `AnchorOutOfRange`), `equivalent_servings(servings: int, factor: Decimal) -> Decimal`, `decimal_text(value: Decimal) -> str`. I Task 2 e 3 li usano.

- [ ] **Step 1: I test che falliscono**

In `backend/tests/domain/test_quantities.py`, l'import in cima diventa:

```python
from app.domain.quantities import (
    UNIT_MAX_LENGTH,
    AnchorOutOfRange,
    UnitForms,
    anchor_factor,
    decimal_text,
    equivalent_servings,
    parse_quantity,
    render_quantity,
    scale_quantity,
)
```

e in fondo al file aggiungi:

```python
# R2, secondo modo: la dose di una riga fissata a mano, e il resto che la segue


@pytest.mark.parametrize(
    "base,amount,expected",
    [
        (Decimal("400"), Decimal("150"), Decimal("0.375")),
        (Decimal("300"), Decimal("112.5"), Decimal("0.375")),
        # un mezzo bicchiere fissato a uno: il doppio
        (Decimal("0.5"), Decimal("1"), Decimal("2")),
        (Decimal("300"), Decimal("300"), Decimal("1")),
        # gli estremi sono dentro: cinquanta volte in giù e in su
        (Decimal("300"), Decimal("6"), Decimal("0.02")),
        (Decimal("300"), Decimal("15000"), Decimal("50")),
    ],
)
def test_anchor_factor(base, amount, expected):
    assert anchor_factor(base, amount) == expected


@pytest.mark.parametrize("amount", [Decimal("5.999"), Decimal("15000.001"), Decimal("0.001")])
def test_anchor_factor_oltre_50_volte(amount):
    with pytest.raises(AnchorOutOfRange) as caught:
        anchor_factor(Decimal("300"), amount)
    # gli estremi arrivano già scalati come si mostrano: la frase che li cita non
    # promette un numero che poi si rifiuta
    assert caught.value.low == Decimal("6")
    assert caught.value.high == Decimal("15000")


@pytest.mark.parametrize(
    "servings,factor,expected",
    [
        (4, Decimal("0.375"), Decimal("1.5")),
        # sotto una porzione, due decimali: «≈ 0,75» e non «≈ 0,8»
        (2, Decimal("0.375"), Decimal("0.75")),
        (4, Decimal("1"), Decimal("4")),
        (3, Decimal(1) / Decimal(3), Decimal("1")),
        (2, Decimal(1) / Decimal(3), Decimal("0.67")),
        (1, Decimal("0.02"), Decimal("0.02")),
        # metà in su: 1,85 → 1,9
        (4, Decimal("0.4625"), Decimal("1.9")),
        (50, Decimal("50"), Decimal("2500")),
    ],
)
def test_equivalent_servings(servings, factor, expected):
    assert equivalent_servings(servings, factor) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (Decimal("150"), "150"),
        (Decimal("150.500"), "150.5"),
        # un «1e3» arrivato dalla query: niente esponenti nello storico
        (Decimal("1E+3"), "1000"),
        (Decimal("0.375"), "0.375"),
        (Decimal("50.000000"), "50"),
    ],
)
def test_decimal_text(value, expected):
    assert decimal_text(value) == expected
```

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/backend`): `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/domain/test_quantities.py`
Expected: errore di raccolta, `ImportError: cannot import name 'AnchorOutOfRange'`.

- [ ] **Step 3: Il codice**

In `backend/app/domain/quantities.py`, in fondo al file (dopo `render_quantity`), aggiungi:

```python
# Il secondo modo del riporziona (R2): la dose di una riga fissata a mano, e il resto
# che la segue. Quanto ci si può allontanare dalla ricetta: lo stesso che lo stepper
# delle porzioni permette al massimo (da 1 a 50 porzioni su ricette che ne dicono da 1
# a 50), cioè cinquanta volte in su o in giù. Una regola sola per i due modi; oltre, è
# quasi sempre uno zero di troppo, e le altre righe diventerebbero dosi che non si pesano.
ANCHOR_MAX_FACTOR = Decimal(50)

# Il tetto, escluso, di quel che si può scrivere come dose. Sta sopra la dose più grande
# che la colonna regge (99999,999) per cinquanta volte: non taglia mai una richiesta che
# il fattore accetterebbe, ferma solo i numeri che non sono dosi.
ANCHOR_AMOUNT_CEILING = Decimal(10_000_000)


class AnchorOutOfRange(ValueError):
    """La dose scritta porta la ricetta oltre `ANCHOR_MAX_FACTOR` volte la sua.

    Porta i due estremi già scalati, `low` e `high`: chi la intercetta li scrive a
    video con l'unità della riga, che questo modulo non conosce."""

    def __init__(self, low: Decimal, high: Decimal) -> None:
        super().__init__(f"fuori scala: fra {low} e {high}")
        self.low = low
        self.high = high


def anchor_factor(base: Decimal, amount: Decimal) -> Decimal:
    """Il fattore che porta la dose della ricetta (`base`, più di zero) a quella scritta.

    Non arrotonda: si arrotonda una volta sola, riga per riga, in `scale_quantity`. Gli
    estremi si confrontano già arrotondati come li si mostrerebbe, così la frase che li
    cita non promette un numero che poi si rifiuta."""
    low = scale_quantity(base, 1 / ANCHOR_MAX_FACTOR)
    high = scale_quantity(base, ANCHOR_MAX_FACTOR)
    if not low <= amount <= high:
        raise AnchorOutOfRange(low, high)
    return amount / base


def equivalent_servings(servings: int, factor: Decimal) -> Decimal:
    """Le porzioni che fa una ricetta da `servings` porzioni scalata di `factor`.

    Un decimale da una porzione in su, due sotto («≈ 1,5», «≈ 0,75»): sotto l'unità un
    decimale solo direbbe «≈ 0,8» di tre quarti. Metà in su, come `scale_quantity`."""
    value = Decimal(servings) * factor
    step = Decimal("0.1") if value >= 1 else Decimal("0.01")
    return value.quantize(step, rounding=ROUND_HALF_UP).normalize()


def decimal_text(value: Decimal) -> str:
    """Un decimale scritto per una macchina: col punto, senza esponente né zeri di coda.

    `str(Decimal("1E+3"))` è «1E+3», e `normalize()` di 50 è `5E+1`: nello storico e nelle
    risposte va «1000» e «50»."""
    return format(value.normalize(), "f")
```

- [ ] **Step 4: Passano**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/domain/test_quantities.py`
Expected: tutto verde, 22 test in più di prima nel file.

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/quantities.py backend/tests/domain/test_quantities.py
git commit -m "R2: il fattore da una dose, il limite delle 50 volte e le porzioni equivalenti, nel dominio"
```

---

### Task 2: Il dettaglio — `anchor` e `amount`

**Files:**
- Create: `backend/app/services/rescale.py`
- Modify: `backend/app/schemas/recipe.py` (`RecipeIngredientOut`, `RecipeOut`, una classe nuova `AnchorOut`)
- Modify: `backend/app/api/recipes.py` (`_to_out`, `detail`, gli import)
- Test: `backend/tests/api/test_recipes_riporziona_ingrediente.py` (nuovo)

**Interfaces:**
- Consumes: dal Task 1 `ANCHOR_MAX_FACTOR`, `ANCHOR_AMOUNT_CEILING`, `AnchorOutOfRange`, `anchor_factor`, `equivalent_servings`, `decimal_text`.
- Produces: in `app/services/rescale.py` `class AnchorRefused(ValueError)` con `.sentence: str`; `@dataclass(frozen=True) class ResolvedAnchor(line: RecipeIngredient, amount: Decimal, factor: Decimal, equivalent_servings: Decimal | None)`; `unit_forms(line) -> UnitForms | None`; `is_anchorable(line) -> bool`; `anchor_unit(line) -> str | None`; `find_anchor_line(recipe, ingredient_id) -> RecipeIngredient | None`; `resolve_anchor(recipe, ingredient_id, amount) -> ResolvedAnchor | None` (solleva `AnchorRefused`). Nella risposta di `GET /api/v1/recipes/{id}`: per riga `anchorable: bool`, `anchor_unit: str | null`; per la ricetta `anchor: {ingredient_id: uuid, amount: str, equivalent_servings: float | null} | null`. Il Task 3 usa `resolve_anchor`, `find_anchor_line`, `AnchorRefused`; il Task 4 i campi.

- [ ] **Step 1: I test che falliscono**

Crea `backend/tests/api/test_recipes_riporziona_ingrediente.py`:

```python
"""Il riporziona da una dose (R2, secondo modo), visto dalla rotta che lo serve."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import IngredientCategory
from app.db.models.unit import Unit
from app.repositories.ingredients import create_ingredient
from app.repositories.recipes import create_recipe

FRASE_FUORI_SCALA = (
    "Così la ricetta cambierebbe più di 50 volte: scrivi un numero fra 6 g e 15000 g."
)


@pytest_asyncio.fixture
async def cucina(db_session):
    return {
        "pasta": await create_ingredient(
            db_session, name="pasta", display_name="Pasta",
            category=IngredientCategory.CEREALI,
        ),
        "cipolla": await create_ingredient(
            db_session, name="cipolla", display_name="Cipolla",
            category=IngredientCategory.VERDURA,
        ),
        "sale": await create_ingredient(
            db_session, name="sale", display_name="Sale",
            category=IngredientCategory.SPEZIE,
        ),
    }


async def _ricetta(db_session, cucina, servings):
    """Tre righe, tre stati di dose: piena («300 g»), numero nudo («1»), non parsata."""
    recipe = await create_recipe(
        db_session,
        title="Mista", description=None, instructions="i", servings=servings,
        source="dataset", source_ref=None,
        ingredients=[
            (cucina["pasta"].id, "primary", "300 g", None),
            (cucina["cipolla"].id, "primary", "1", None),
            (cucina["sale"].id, "secondary", "q.b.", None),
        ],
        embedding=None,
    )
    # «g» decisa a mano, come in test_recipes_riporziona.py: qui non gira nessun AI
    unit = (
        await db_session.execute(select(Unit).where(Unit.key == "g"))
    ).scalars().one()
    unit.singular, unit.plural, unit.decided_by = "g", "g", "human"
    await db_session.flush()
    return recipe.id


@pytest_asyncio.fixture
async def ricetta_mista(db_session, cucina):
    return await _ricetta(db_session, cucina, servings=4)


@pytest_asyncio.fixture
async def ricetta_senza_porzioni(db_session, cucina):
    return await _ricetta(db_session, cucina, servings=None)


async def _dettaglio(client, recipe_id, **params):
    return await client.get(f"/api/v1/recipes/{recipe_id}", params=params)


def _per_nome(corpo):
    return {line["ingredient_name"]: line for line in corpo["ingredients"]}


async def test_ogni_riga_dice_se_ci_si_puo_ancorare(logged_client, ricetta_mista):
    corpo = (await _dettaglio(logged_client, ricetta_mista)).json()
    righe = _per_nome(corpo)
    assert (righe["pasta"]["anchorable"], righe["pasta"]["anchor_unit"]) == (True, "g")
    # un numero nudo si riscala, e non ha un'unità da scrivere accanto al campo
    assert (righe["cipolla"]["anchorable"], righe["cipolla"]["anchor_unit"]) == (True, None)
    # «q.b.» non è una dose da cui partire
    assert (righe["sale"]["anchorable"], righe["sale"]["anchor_unit"]) == (False, None)
    assert corpo["anchor"] is None


async def test_da_una_dose_le_altre_seguono(logged_client, cucina, ricetta_mista):
    # la ricetta è per 4 con 300 g di pasta: 112,5 g sono 0,375 della ricetta
    risposta = await _dettaglio(
        logged_client, ricetta_mista, anchor=str(cucina["pasta"].id), amount="112.5"
    )
    assert risposta.status_code == 200
    corpo = risposta.json()
    righe = _per_nome(corpo)

    # la riga dell'ancora dice la dose scritta, non il suo ricalcolo
    assert righe["pasta"]["quantity_display"] == "112,5 g"
    assert righe["pasta"]["quantity_scaled"] is True
    assert righe["cipolla"]["quantity_display"] == "0,375"
    assert righe["cipolla"]["quantity_scaled"] is True
    # quel che non si capisce resta com'è, e si conta
    assert righe["sale"]["quantity_display"] == "q.b."
    assert righe["sale"]["quantity_scaled"] is False
    assert corpo["unscalable_lines"] == 1
    assert corpo["dose_lines"] == 3
    # la verità a 1× non si riscrive
    assert righe["pasta"]["quantity_text"] == "300 g"
    # il modo per porzioni non c'entra
    assert corpo["scaled_to"] is None
    assert corpo["anchor"] == {
        "ingredient_id": str(cucina["pasta"].id),
        "amount": "112.5",
        "equivalent_servings": 1.5,
    }


async def test_da_un_numero_nudo_si_riscala_lo_stesso(logged_client, cucina, ricetta_mista):
    corpo = (
        await _dettaglio(logged_client, ricetta_mista, anchor=str(cucina["cipolla"].id), amount="2")
    ).json()
    righe = _per_nome(corpo)
    assert righe["cipolla"]["quantity_display"] == "2"
    assert righe["pasta"]["quantity_display"] == "600 g"
    assert corpo["anchor"]["equivalent_servings"] == 8


async def test_la_dose_della_ricetta_e_come_non_chiedere_niente(
    logged_client, cucina, ricetta_mista
):
    """A 1× il testo originale dice la verità meglio di quanto sappiamo riscriverla."""
    corpo = (
        await _dettaglio(logged_client, ricetta_mista, anchor=str(cucina["pasta"].id), amount="300")
    ).json()
    for line in corpo["ingredients"]:
        assert line["quantity_display"] == line["quantity_text"]
        assert line["quantity_scaled"] is False
    assert corpo["unscalable_lines"] == 0
    # l'ancora resta: lo stepper dice «≈ 4», e «Torna alle dosi della ricetta» ha senso
    assert corpo["anchor"]["equivalent_servings"] == 4


async def test_senza_porzioni_si_riscala_lo_stesso(logged_client, cucina, ricetta_senza_porzioni):
    corpo = (
        await _dettaglio(
            logged_client, ricetta_senza_porzioni, anchor=str(cucina["pasta"].id), amount="150"
        )
    ).json()
    righe = _per_nome(corpo)
    assert righe["pasta"]["quantity_display"] == "150 g"
    assert righe["cipolla"]["quantity_display"] == "0,5"
    # senza porzioni nella ricetta non ci sono porzioni equivalenti da dire
    assert corpo["anchor"] == {
        "ingredient_id": str(cucina["pasta"].id),
        "amount": "150",
        "equivalent_servings": None,
    }


@pytest.mark.parametrize("amount", ["5.999", "15000.001"])
async def test_oltre_50_volte_un_422_che_dice_dove_stare(
    logged_client, cucina, ricetta_mista, amount
):
    risposta = await _dettaglio(
        logged_client, ricetta_mista, anchor=str(cucina["pasta"].id), amount=amount
    )
    assert risposta.status_code == 422
    assert risposta.json()["detail"] == FRASE_FUORI_SCALA


@pytest.mark.parametrize("amount,attesa", [("6", "6 g"), ("15000", "15000 g")])
async def test_gli_estremi_della_frase_si_accettano(
    logged_client, cucina, ricetta_mista, amount, attesa
):
    risposta = await _dettaglio(
        logged_client, ricetta_mista, anchor=str(cucina["pasta"].id), amount=amount
    )
    assert risposta.status_code == 200
    assert _per_nome(risposta.json())["pasta"]["quantity_display"] == attesa


async def test_un_ancora_che_la_ricetta_non_ha_si_ignora(logged_client, cucina, ricetta_mista):
    """Una ricetta modificata in un'altra scheda: la vista torna quella di tutti i giorni,
    come `servings` su una ricetta senza porzioni, invece di un errore."""
    for anchor in (str(cucina["sale"].id), str(uuid.uuid4())):
        corpo = (await _dettaglio(logged_client, ricetta_mista, anchor=anchor, amount="5")).json()
        assert corpo["anchor"] is None
        for line in corpo["ingredients"]:
            assert line["quantity_display"] == line["quantity_text"]


@pytest.mark.parametrize(
    "params",
    [
        {"anchor": "PASTA"},
        {"amount": "150"},
        {"anchor": "PASTA", "amount": "150", "servings": "2"},
    ],
)
async def test_i_parametri_vanno_insieme_e_un_modo_alla_volta(
    logged_client, cucina, ricetta_mista, params
):
    params = {k: (str(cucina["pasta"].id) if v == "PASTA" else v) for k, v in params.items()}
    assert (await _dettaglio(logged_client, ricetta_mista, **params)).status_code == 422


@pytest.mark.parametrize("amount", ["0", "-1", "1.2345", "abc", "10000000", "NaN"])
async def test_una_dose_che_non_e_un_numero_buono(logged_client, cucina, ricetta_mista, amount):
    risposta = await _dettaglio(
        logged_client, ricetta_mista, anchor=str(cucina["pasta"].id), amount=amount
    )
    assert risposta.status_code == 422
```

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/backend`): `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/api/test_recipes_riporziona_ingrediente.py`
Expected: FAIL. `KeyError: 'anchorable'` nel primo; negli altri l'ancora si ignora oggi (le righe restano a 1×, `anchor` manca) e i 422 non arrivano (200). Qualcuno dei 422 di `test_una_dose_che_non_e_un_numero_buono` può già passare per caso? No: oggi `amount` non è un parametro e si ignora, quindi tutti e sei rispondono 200 e falliscono.

- [ ] **Step 3: Il servizio**

Crea `backend/app/services/rescale.py`:

```python
"""Il riporziona da una dose (R2, secondo modo): quale riga fa da ancora, e cosa ne segue.

Lo chiamano il dettaglio della ricetta (`_to_out` in `app/api/recipes.py`) e la cottura
(`app/services/cooking.py`): una funzione sola, perché la riga che il dettaglio ha
mostrato come ancora sia la stessa che la cottura registra (prima lezione di
`CLAUDE.md`). La matematica sta nel dominio (`app/domain/quantities.py`); qui si sa cos'è
una riga di ricetta.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal

from app.db.models.recipe import Recipe, RecipeIngredient
from app.domain.quantities import (
    ANCHOR_MAX_FACTOR,
    AnchorOutOfRange,
    UnitForms,
    anchor_factor,
    equivalent_servings,
    render_quantity,
)


class AnchorRefused(ValueError):
    """La dose scritta porta la ricetta oltre 50 volte la sua. `sentence` è la frase da
    mostrare sotto il campo, con gli estremi e l'unità della riga."""

    def __init__(self, sentence: str) -> None:
        super().__init__(sentence)
        self.sentence = sentence


@dataclass(frozen=True)
class ResolvedAnchor:
    line: RecipeIngredient
    amount: Decimal
    factor: Decimal
    # `None` quando la ricetta non dice per quante porzioni è
    equivalent_servings: Decimal | None


def unit_forms(line: RecipeIngredient) -> UnitForms | None:
    if line.unit is None:
        return None
    return UnitForms(line.unit.key, line.unit.singular, line.unit.plural)


def is_anchorable(line: RecipeIngredient) -> bool:
    """Una riga da cui si riscala: ha una dose strutturata, e più di zero — da zero non
    si ricava nessun fattore. «q.b.» e le righe senza dose no."""
    return line.quantity_value is not None and line.quantity_value > 0


def anchor_unit(line: RecipeIngredient) -> str | None:
    """La parola dell'unità accanto al campo «Quanto ne fai?»: il plurale, se deciso, se
    no la chiave com'è arrivata. `None` per un numero nudo («1» cipolla)."""
    if line.unit is None:
        return None
    return line.unit.plural or line.unit.key


def find_anchor_line(recipe: Recipe, ingredient_id: uuid.UUID) -> RecipeIngredient | None:
    # (recipe_id, ingredient_id) è unico: una riga per ingrediente, quindi l'ingrediente
    # basta a dire quale riga
    return next(
        (
            line
            for line in recipe.ingredients
            if line.ingredient_id == ingredient_id and is_anchorable(line)
        ),
        None,
    )


def resolve_anchor(
    recipe: Recipe, ingredient_id: uuid.UUID, amount: Decimal
) -> ResolvedAnchor | None:
    """Il fattore che porta la riga di `ingredient_id` ad `amount`, e le porzioni che fa.

    `None` se la ricetta non ha (più) una riga di quell'ingrediente da cui riscalare: chi
    chiama mostra la ricetta com'è invece di un errore — una ricetta modificata in
    un'altra scheda non deve diventare un vicolo cieco. Solleva `AnchorRefused` oltre
    `ANCHOR_MAX_FACTOR` volte."""
    line = find_anchor_line(recipe, ingredient_id)
    if line is None or line.quantity_value is None:
        return None
    try:
        factor = anchor_factor(line.quantity_value, amount)
    except AnchorOutOfRange as exc:
        forms = unit_forms(line)
        raise AnchorRefused(
            f"Così la ricetta cambierebbe più di {ANCHOR_MAX_FACTOR} volte: scrivi un "
            f"numero fra {render_quantity(exc.low, forms)} e "
            f"{render_quantity(exc.high, forms)}."
        ) from exc
    equivalent = (
        equivalent_servings(recipe.servings, factor) if recipe.servings is not None else None
    )
    return ResolvedAnchor(line=line, amount=amount, factor=factor, equivalent_servings=equivalent)
```

(`line.quantity_value is None` dopo `find_anchor_line` non succede mai — `is_anchorable` l'ha già escluso —: la condizione c'è perché `anchor_factor` vuole un `Decimal`, e dirlo qui costa meno di un `assert`.)

- [ ] **Step 4: Gli schemi**

In `backend/app/schemas/recipe.py`:

1. In `class RecipeIngredientOut`, dopo il campo `quantity_scaled: bool`, aggiungi:
   ```python
       # R2, secondo modo: se da questa riga si può riscalare (una dose strutturata più
       # grande di zero), e la parola dell'unità da scrivere accanto al campo («g»,
       # «cucchiai»); `None` per un numero nudo o per una riga che non si riscala
       anchorable: bool = False
       anchor_unit: str | None = None
   ```
2. Subito **prima** di `class RecipeOut(BaseModel):`, aggiungi:
   ```python
   class AnchorOut(BaseModel):
       """La dose fissata da cui la risposta è riscalata (R2, secondo modo)."""

       ingredient_id: uuid.UUID
       # la dose come il server l'ha letta, col punto («112.5»): torna tale e quale alla
       # cottura, per questo è una stringa e non un numero
       amount: str
       # le porzioni che quella dose fa, già arrotondate (`equivalent_servings` in
       # app/domain/quantities.py); `None` se la ricetta non dice per quante porzioni è
       equivalent_servings: float | None
   ```
3. In `class RecipeOut`, dopo il campo `dose_lines: int = 0` (e il suo commento), aggiungi:
   ```python
       # la dose fissata, se questa risposta è riscalata da un ingrediente (R2). `scaled_to`
       # resta del modo per porzioni: in questo modo è `None`
       anchor: AnchorOut | None = None
   ```

- [ ] **Step 5: La rotta**

In `backend/app/api/recipes.py`:

1. L'import dal dominio:
   ```python
   from app.domain.quantities import UnitForms, render_quantity, scale_quantity
   ```
   diventa
   ```python
   from app.domain.quantities import (
       ANCHOR_AMOUNT_CEILING,
       decimal_text,
       render_quantity,
       scale_quantity,
   )
   ```
   (`UnitForms` non serve più in questo file: le forme le dà `unit_forms`. Se `grep -n "UnitForms" backend/app/api/recipes.py` dopo le modifiche trova ancora un uso, rimettilo nell'import.)
2. Nell'import da `app.schemas.recipe` aggiungi `AnchorOut` (in ordine alfabetico, prima di `RecipeCreate`). Dopo l'import di `app.services.recipe_search` aggiungi:
   ```python
   from app.services.rescale import (
       AnchorRefused,
       anchor_unit,
       is_anchorable,
       resolve_anchor,
       unit_forms,
   )
   ```
3. Sotto la costante `RECIPE_ARCHIVED`, aggiungi:
   ```python
   # R2: le due regole dei parametri del dettaglio. Il frontend non le viola mai, quindi
   # non sono frasi a video: dicono il contratto a chi chiama la rotta a mano
   ANCHOR_NEEDS_AMOUNT = "La dose di un ingrediente vuole `anchor` e `amount` insieme."
   ONE_SCALE_AT_A_TIME = (
       "Un modo alla volta: le porzioni (`servings`) oppure la dose di un ingrediente "
       "(`anchor` con `amount`)."
   )
   ```
4. In `_to_out`, la firma
   ```python
   async def _to_out(
       session: AsyncSession, recipe: Recipe, servings: int | None = None
   ) -> RecipeOut:
   ```
   diventa
   ```python
   async def _to_out(
       session: AsyncSession,
       recipe: Recipe,
       servings: int | None = None,
       anchor: tuple[uuid.UUID, Decimal] | None = None,
   ) -> RecipeOut:
   ```
5. Sempre in `_to_out`, il blocco
   ```python
       factor: Decimal | None = None
       # `is not None` e non la verità: che `servings=0` non arrivi mai qui lo garantisce
       # `Query(ge=1)` in fondo a questo file, e una condizione che dipende da un
       # validatore scritto altrove smette di valere il giorno in cui quello cambia
       if servings is not None and recipe.servings is not None:
           factor = Decimal(servings) / Decimal(recipe.servings)
           if factor == 1:
               factor = None  # chiedere le porzioni che ha già è come non chiedere niente
   ```
   diventa
   ```python
       factor: Decimal | None = None
       # R2, secondo modo: una dose fissata su una riga. `resolve_anchor` solleva
       # `AnchorRefused` oltre le 50 volte (la rotta ne fa un 422 con la frase); un'ancora
       # che la ricetta non ha più si ignora, come `servings` su una ricetta senza porzioni
       resolved = resolve_anchor(recipe, *anchor) if anchor is not None else None
       if resolved is not None:
           factor = resolved.factor
       # `is not None` e non la verità: che `servings=0` non arrivi mai qui lo garantisce
       # `Query(ge=1)` in fondo a questo file, e una condizione che dipende da un
       # validatore scritto altrove smette di valere il giorno in cui quello cambia
       elif servings is not None and recipe.servings is not None:
           factor = Decimal(servings) / Decimal(recipe.servings)
       if factor == 1:
           factor = None  # chiedere quel che la ricetta dice già è come non chiedere niente
   ```
6. Nel ciclo `for ri in recipe.ingredients:`, il blocco
   ```python
           if factor is not None and ri.quantity_value is not None:
               forms = (
                   UnitForms(ri.unit.key, ri.unit.singular, ri.unit.plural)
                   if ri.unit
                   else None
               )
               display = render_quantity(scale_quantity(ri.quantity_value, factor), forms)
               scaled = True
   ```
   diventa
   ```python
           if factor is not None and ri.quantity_value is not None:
               # la riga dell'ancora dice la dose scritta, non il suo ricalcolo: chi ha
               # scritto 150 deve leggere 150, anche quando 150 / 400 × 400 non torna esatto
               value = (
                   resolved.amount
                   if resolved is not None and ri is resolved.line
                   else scale_quantity(ri.quantity_value, factor)
               )
               display = render_quantity(value, unit_forms(ri))
               scaled = True
   ```
7. Nello stesso ciclo, nella costruzione di `RecipeIngredientOut(...)`, dopo `quantity_scaled=scaled,` aggiungi:
   ```python
                   anchorable=is_anchorable(ri),
                   anchor_unit=anchor_unit(ri) if is_anchorable(ri) else None,
   ```
8. Nel `return RecipeOut(...)`, la riga
   ```python
           scaled_to=servings if factor is not None else None,
   ```
   diventa
   ```python
           scaled_to=servings if factor is not None and resolved is None else None,
   ```
   e dopo `unscalable_lines=unscalable, dose_lines=dose_lines,` aggiungi:
   ```python
           anchor=(
               AnchorOut(
                   ingredient_id=resolved.line.ingredient_id,
                   amount=decimal_text(resolved.amount),
                   equivalent_servings=(
                       float(resolved.equivalent_servings)
                       if resolved.equivalent_servings is not None
                       else None
                   ),
               )
               if resolved is not None
               else None
           ),
   ```
9. La rotta `detail` (decorata con `@router.get("/{recipe_id}", response_model=RecipeOut)`) diventa:
   ```python
   @router.get("/{recipe_id}", response_model=RecipeOut)
   async def detail(
       recipe_id: uuid.UUID,
       servings: int | None = Query(default=None, ge=1, le=50),
       # R2, secondo modo: la riga (per ingrediente) e la dose scritta, col punto. Tre
       # decimali come la colonna `quantity_value`
       anchor: uuid.UUID | None = Query(default=None),
       amount: Decimal | None = Query(
           default=None, gt=0, lt=ANCHOR_AMOUNT_CEILING, decimal_places=3
       ),
       session: AsyncSession = Depends(get_session),
   ) -> RecipeOut:
       if (anchor is None) != (amount is None):
           raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, ANCHOR_NEEDS_AMOUNT)
       if anchor is not None and servings is not None:
           raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, ONE_SCALE_AT_A_TIME)
       recipe = await get_recipe(session, recipe_id)
       if recipe is None:
           raise HTTPException(status.HTTP_404_NOT_FOUND, "ricetta inesistente")
       try:
           return await _to_out(
               session,
               recipe,
               servings=servings,
               anchor=(anchor, amount) if anchor is not None and amount is not None else None,
           )
       except AnchorRefused as exc:
           raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, exc.sentence) from exc
   ```

- [ ] **Step 6: Passano, e il primo modo non è cambiato**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/api/test_recipes_riporziona_ingrediente.py tests/api/test_recipes_riporziona.py tests/api/test_recipes_quantities.py tests/api/test_recipes.py tests/api/test_recipes_edit.py`
Expected: tutto verde (19 nuovi; i file del primo modo e del dettaglio passano senza essere toccati).

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/rescale.py backend/app/schemas/recipe.py backend/app/api/recipes.py backend/tests/api/test_recipes_riporziona_ingrediente.py
git commit -m "R2: GET /recipes/{id} riscala da una dose (anchor + amount), un modo alla volta, 422 oltre le 50 volte"
```

---

### Task 3: La cottura — la dose nello `snapshot`

**Files:**
- Modify: `backend/app/schemas/cooking.py` (`CookRequest`)
- Modify: `backend/app/services/cooking.py` (`cook`, una funzione nuova `anchor_record`)
- Modify: `backend/app/api/cooking.py` (`cook_recipe`, solo la chiamata a `cook`)
- Test: `backend/tests/api/test_cooking_riporziona.py` (nuovo)

Leggi `backend/app/services/cooking.py` e `backend/app/api/cooking.py` com'è sul ramo prima di cambiarli: stanotte il piano 7 («Rimetti in lista») cambia il ciclo delle transizioni e il conto di `updated`, su un altro ramo. Questo task tocca solo la firma di `cook`, la costruzione di `CookingEvent` e gli argomenti della chiamata: punti diversi.

**Interfaces:**
- Consumes: dal Task 1 `ANCHOR_AMOUNT_CEILING`, `decimal_text`; dal Task 2 `resolve_anchor`, `find_anchor_line`, `AnchorRefused`.
- Produces: `CookRequest.anchor: uuid.UUID | None`, `CookRequest.amount: Decimal | None` (insieme o niente, mai con `servings`); `cook(..., anchor: tuple[uuid.UUID, Decimal] | None = None)`; `anchor_record(recipe, ingredient_id, amount) -> dict[str, str | None]`; `snapshot["anchor"]` con le chiavi `ingredient_id`, `amount`, `unit`, `factor`, `equivalent_servings`. Il Task 4 manda `anchor` e `amount` da `CookSheet`.

- [ ] **Step 1: I test che falliscono**

Crea `backend/tests/api/test_cooking_riporziona.py`:

```python
"""La cottura riscalata da una dose (R2, secondo modo): cosa resta nello storico.

In file suo e non in `test_cooking.py`, che stanotte cambia anche un altro ramo."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe import CookingEvent
from app.repositories.ingredients import create_ingredient
from app.repositories.recipes import create_recipe


@pytest_asyncio.fixture
async def ricetta(db_session):
    pasta = await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    sale = await create_ingredient(
        db_session, name="sale", display_name="Sale", category=IngredientCategory.SPEZIE
    )
    recipe = await create_recipe(
        db_session,
        title="Pasta in bianco", description=None, instructions="Cuoci.", servings=4,
        source="dataset", source_ref=None,
        ingredients=[
            (pasta.id, "primary", "400 g", None),
            (sale.id, "secondary", "q.b.", None),
        ],
        embedding=None,
    )
    await db_session.flush()
    return {"id": recipe.id, "pasta": pasta.id, "sale": sale.id}


async def _cucina(client, recipe_id, **body):
    return await client.post(
        f"/api/v1/recipes/{recipe_id}/cook", json={"transitions": [], **body}
    )


async def _evento(dal_database, risposta):
    # da una sessione nuova: lo `snapshot` com'è nel JSONB, non com'è in memoria
    return await dal_database(CookingEvent, uuid.UUID(risposta.json()["event_id"]))


async def test_cucinata_da_una_dose_lo_snapshot_ha_l_ancora(logged_client, dal_database, ricetta):
    risposta = await _cucina(
        logged_client, ricetta["id"], anchor=str(ricetta["pasta"]), amount="150"
    )
    assert risposta.status_code == 201
    evento = await _evento(dal_database, risposta)
    # «≈ 1,5» non è un numero di porzioni uscito dalla pentola: la colonna resta vuota,
    # e il fatto vero — la dose — sta nello storico
    assert evento.servings is None
    assert evento.snapshot["anchor"] == {
        "ingredient_id": str(ricetta["pasta"]),
        "amount": "150",
        "unit": "g",
        "factor": "0.375",
        "equivalent_servings": "1.5",
    }
    # il resto dello snapshot è quello di sempre
    assert evento.snapshot["transitions"] == []
    assert evento.snapshot["restocked"] == 0


async def test_per_porzioni_lo_snapshot_non_cambia_forma(logged_client, dal_database, ricetta):
    risposta = await _cucina(logged_client, ricetta["id"], servings=2)
    assert risposta.status_code == 201
    evento = await _evento(dal_database, risposta)
    assert evento.servings == 2
    assert "anchor" not in evento.snapshot


@pytest.mark.parametrize(
    "ancora,amount,unita",
    [
        # una riga senza dose da cui riscalare (tolta, o diventata «q.b.», in un'altra scheda)
        ("sale", "1", None),
        # oltre le 50 volte: il dettaglio l'avrebbe rifiutata, ma la ricetta può essere
        # cambiata fra la vista e la cottura
        ("pasta", "100000", "g"),
    ],
)
async def test_un_ancora_che_non_vale_piu_non_blocca_la_cottura(
    logged_client, dal_database, ricetta, ancora, amount, unita
):
    risposta = await _cucina(
        logged_client, ricetta["id"], anchor=str(ricetta[ancora]), amount=amount
    )
    assert risposta.status_code == 201
    assert (await _evento(dal_database, risposta)).snapshot["anchor"] == {
        "ingredient_id": str(ricetta[ancora]),
        "amount": amount,
        "unit": unita,
        "factor": None,
        "equivalent_servings": None,
    }


@pytest.mark.parametrize(
    "body",
    [
        {"anchor": "PASTA"},
        {"amount": "150"},
        {"anchor": "PASTA", "amount": "150", "servings": 2},
        {"anchor": "PASTA", "amount": "0"},
        {"anchor": "PASTA", "amount": "1.2345"},
    ],
)
async def test_la_cottura_rifiuta_quel_che_il_dettaglio_rifiuta(
    logged_client, db_session, ricetta, body
):
    body = {k: (str(ricetta["pasta"]) if v == "PASTA" else v) for k, v in body.items()}
    risposta = await _cucina(logged_client, ricetta["id"], **body)
    assert risposta.status_code == 422
    eventi = (
        await db_session.execute(select(func.count()).select_from(CookingEvent))
    ).scalar_one()
    assert eventi == 0
```

- [ ] **Step 2: Falliscono**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/api/test_cooking_riporziona.py`
Expected: FAIL. Oggi `anchor` e `amount` non sono nel modello e si ignorano: i primi tre test trovano `KeyError: 'anchor'` nello snapshot; quelli del 422 rispondono 201 (tranne `{"anchor": "PASTA", "amount": "150", "servings": 2}`, che risponde 201 anche lui). `test_per_porzioni_lo_snapshot_non_cambia_forma` passa già, ed è giusto: fissa che lo `snapshot` di sempre non cambia.

- [ ] **Step 3: Lo schema**

In `backend/app/schemas/cooking.py`:

1. Gli import diventano:
   ```python
   import uuid
   from decimal import Decimal

   from pydantic import BaseModel, Field, model_validator

   from app.domain.quantities import ANCHOR_AMOUNT_CEILING
   from app.domain.rules import PantryStatus
   ```
2. `class CookRequest` diventa:
   ```python
   class CookRequest(BaseModel):
       servings: int | None = Field(default=None, ge=1, le=50)
       # R2, secondo modo: la dose fissata da cui si è riscalato, con le regole del dettaglio
       # (`GET /recipes/{id}`): insieme o niente, mai con `servings`
       anchor: uuid.UUID | None = None
       amount: Decimal | None = Field(
           default=None, gt=0, lt=ANCHOR_AMOUNT_CEILING, decimal_places=3
       )
       transitions: list[TransitionIn] = Field(default_factory=list)

       @model_validator(mode="after")
       def _one_scale_at_a_time(self) -> "CookRequest":
           if (self.anchor is None) != (self.amount is None):
               raise ValueError("`anchor` e `amount` vanno insieme")
           if self.anchor is not None and self.servings is not None:
               raise ValueError("un modo alla volta: `servings` oppure `anchor` con `amount`")
           return self
   ```

- [ ] **Step 4: Il servizio**

In `backend/app/services/cooking.py`:

1. Agli import aggiungi `from decimal import Decimal` e `from typing import Any` (accanto agli altri della libreria standard), e dopo `from app.services.restock import restock`:
   ```python
   from app.domain.quantities import decimal_text
   from app.services.rescale import AnchorRefused, find_anchor_line, resolve_anchor
   ```
   (`from app.domain.quantities …` va nel blocco degli import di `app.domain`, accanto a `from app.domain.rules import PantryStatus`.)
2. Sotto il dizionario `_RESTOCK_REASON`, aggiungi:
   ```python
   # il fattore nello storico: sei decimali bastano a ricostruire ogni dose, che ne ha tre
   FACTOR_PRECISION = Decimal("0.000001")


   def anchor_record(
       recipe: Recipe, ingredient_id: uuid.UUID, amount: Decimal
   ) -> dict[str, str | None]:
       """Cosa si è cucinato quando si è riscalato da una dose (R2, secondo modo).

       Va nello `snapshot` e non in `servings`: le porzioni sono un intero che dice
       quante ne sono uscite dalla pentola, ed è un fatto solo quando lo si è scelto; «1,5»
       è un derivato, e scriverlo arrotondato sarebbe falso per sempre. Il fatto vero è la
       dose dell'ancora. Il fattore si ricalcola con la funzione del dettaglio; un'ancora
       che adesso non vale più (riga tolta, fuori scala) non blocca la cottura: si registra
       con `factor` nullo. Stringhe col punto e non `Decimal`: il JSONB non li sa scrivere.
       """
       line = find_anchor_line(recipe, ingredient_id)
       try:
           resolved = resolve_anchor(recipe, ingredient_id, amount)
       except AnchorRefused:
           resolved = None
       return {
           "ingredient_id": str(ingredient_id),
           "amount": decimal_text(amount),
           "unit": line.unit.key if line is not None and line.unit is not None else None,
           "factor": (
               decimal_text(resolved.factor.quantize(FACTOR_PRECISION))
               if resolved is not None
               else None
           ),
           "equivalent_servings": (
               decimal_text(resolved.equivalent_servings)
               if resolved is not None and resolved.equivalent_servings is not None
               else None
           ),
       }
   ```
3. La firma di `cook`:
   ```python
       servings: int | None,
       transitions: list[Transition],
   ) -> CookingEvent:
   ```
   diventa
   ```python
       servings: int | None,
       transitions: list[Transition],
       anchor: tuple[uuid.UUID, Decimal] | None = None,
   ) -> CookingEvent:
   ```
4. In fondo a `cook`, il blocco
   ```python
       event = CookingEvent(
           recipe_id=recipe_id, cooked_at=now, servings=servings,
           snapshot={"transitions": snapshot, "restocked": restocked},
       )
   ```
   diventa
   ```python
       record: dict[str, Any] = {"transitions": snapshot, "restocked": restocked}
       if anchor is not None:
           record["anchor"] = anchor_record(recipe, *anchor)
       event = CookingEvent(
           recipe_id=recipe_id, cooked_at=now, servings=servings, snapshot=record,
       )
   ```
   (`recipe` è quello caricato in testa a `cook` con `session.get(Recipe, recipe_id)`: la relazione `ingredients` è `lazy="selectin"` e la riga porta `unit` in `lazy="joined"`, quindi le righe e le loro unità arrivano con lui. Se un test desse `MissingGreenlet` leggendo `recipe.ingredients`, carica la ricetta con `get_recipe(session, recipe_id)` da `app.repositories.recipes`, come fa il dettaglio, e scrivilo nel report.)

- [ ] **Step 5: La rotta**

In `backend/app/api/cooking.py`, in `cook_recipe`, la chiamata
```python
        event = await cook(
            session, recipe_id=recipe_id, servings=payload.servings, transitions=transitions
        )
```
diventa
```python
        event = await cook(
            session, recipe_id=recipe_id, servings=payload.servings, transitions=transitions,
            anchor=(
                (payload.anchor, payload.amount)
                if payload.anchor is not None and payload.amount is not None
                else None
            ),
        )
```

- [ ] **Step 6: Passano, e la cottura di sempre non è cambiata**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/api/test_cooking_riporziona.py tests/api/test_cooking.py`
Expected: tutto verde (9 nuovi; `test_cooking.py` senza modifiche).

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/cooking.py backend/app/services/cooking.py backend/app/api/cooking.py backend/tests/api/test_cooking_riporziona.py
git commit -m "R2: la cottura riscalata da una dose registra l'ancora nello snapshot, servings resta null"
```

---

### Task 4: I tipi, l'API del frontend, il 422 che non si ritenta, la cottura che manda l'ancora

**Files:**
- Modify: `frontend/src/domain/types.ts` (`RecipeIngredientLine`, `RecipeDetail`, un'interfaccia nuova `RecipeAnchor`)
- Modify: `frontend/src/features/recipes/api.ts` (`fetchRecipe`, `cookRecipe`, un tipo nuovo `RecipeScale`); Test: `frontend/src/features/recipes/api.test.ts`
- Modify: `frontend/src/lib/queryRetry.ts`; Test: `frontend/src/lib/queryRetry.test.ts`
- Modify: `frontend/src/features/cooking/CookSheet.tsx`; Test: `frontend/src/features/cooking/CookSheet.test.tsx`
- Modify (solo i campi nuovi delle voci finte): i test che scrivono a mano un `RecipeDetail` o una `RecipeIngredientLine` — su `master` `RecipeDetailScreen.test.tsx`, `RecipeDetailActions.test.tsx`, `CookSheet.test.tsx`, `AddMissingButton.test.tsx`, `missingToList.test.ts` in `features/cooking/`, e `formModel.test.ts`, `RecipeForm.test.tsx`, `RecipeEditScreen.test.tsx` in `features/recipe-form/`; più ogni altro file che `npm run typecheck` segnala

**Interfaces:**
- Consumes: dal Task 2 i campi `anchorable`, `anchor_unit`, `anchor` della risposta; dal Task 3 `anchor` e `amount` nel corpo della cottura.
- Produces: `RecipeIngredientLine.anchorable: boolean`, `RecipeIngredientLine.anchor_unit: string | null`, `interface RecipeAnchor { ingredient_id: string; amount: string; equivalent_servings: number | null }`, `RecipeDetail.anchor: RecipeAnchor | null`; `type RecipeScale = { servings: number } | { anchor: string; amount: string }` e `fetchRecipe(id: string, scale?: RecipeScale)` in `features/recipes/api.ts`; `cookRecipe` che accetta `anchor?: string` e `amount?: string`. I Task 5 e 6 li usano.

- [ ] **Step 1: I test che falliscono**

1. In `frontend/src/features/recipes/api.test.ts`, l'import in cima diventa
   ```ts
   import {
     fetchRecipe,
     lowerBoundFrom,
     nextPageOffset,
     searchRecipes,
     totalFrom,
     type RecipePage,
     type RecipeScale,
   } from "./api";
   ```
   (se l'import sul ramo ha altri nomi, aggiungi solo `fetchRecipe` e `type RecipeScale`), e in fondo al file:
   ```ts
   describe("fetchRecipe", () => {
     // il client chiede e basta: per porzioni, o da una dose fissata (R2). Il calcolo è
     // del server, quindi qui c'è solo l'indirizzo
     const casi: [string, RecipeScale | undefined, string][] = [
       ["la ricetta com'è", undefined, "/api/v1/recipes/r1"],
       ["per porzioni", { servings: 3 }, "/api/v1/recipes/r1?servings=3"],
       ["da una dose", { anchor: "i1", amount: "112.5" }, "/api/v1/recipes/r1?anchor=i1&amount=112.5"],
     ];
     it.each(casi)("%s", async (_nome, scale, indirizzo) => {
       const spy = vi.fn().mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));
       vi.stubGlobal("fetch", spy);
       await fetchRecipe("r1", scale);
       expect(spy.mock.calls[0][0]).toBe(indirizzo);
     });
   });
   ```
2. In `frontend/src/lib/queryRetry.test.ts`, nella tabella del secondo `it.each` (quella con «non si ritenta mai»), dopo la riga del 404 aggiungi:
   ```ts
       ["un 422 (la domanda è sbagliata, e rifatta uguale lo resta)", new ApiError("fuori scala", 422)],
   ```
3. In `frontend/src/features/cooking/CookSheet.test.tsx`, subito dopo il test `it("senza riporziona restano le porzioni della ricetta", …)`, aggiungi:
   ```ts
     it("riscalata da una dose, manda la dose e non le porzioni (R2)", async () => {
       // «≈ 1,5» non è un numero di porzioni uscito dalla pentola: la cottura registra la
       // dose fissata, e il server ricalcola il resto
       const spy = vi.fn().mockResolvedValue(new Response(
         JSON.stringify({ event_id: "e1", updated: 0, restocked: 0 }), { status: 201 }
       ));
       vi.stubGlobal("fetch", spy);

       renderSheet(vi.fn(), undefined, PANTRY, {
         ...RECIPE,
         anchor: { ingredient_id: "i1", amount: "135", equivalent_servings: 1.5 },
       });
       await userEvent.click(screen.getByRole("button", { name: "Ho cucinato" }));

       const corpo = JSON.parse(spy.mock.calls[0][1].body);
       expect(corpo.anchor).toBe("i1");
       expect(corpo.amount).toBe("135");
       expect("servings" in corpo).toBe(false);
     });
   ```

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/features/recipes/api.test.ts src/lib/queryRetry.test.ts src/features/cooking/CookSheet.test.tsx`
Expected: FAIL — «da una dose» chiede `/api/v1/recipes/r1` (oggi il secondo argomento è un numero, e un oggetto senza `servings` non dà query) e «per porzioni» chiede `?servings=[object Object]`; il 422 oggi si ritenta (`true`); la cottura manda `servings: 2` e nessuna `anchor`.

- [ ] **Step 3: I tipi**

In `frontend/src/domain/types.ts`:

1. In `export interface RecipeIngredientLine`, dopo `quantity_scaled: boolean;` (e il suo commento), aggiungi:
   ```ts
     /** Se da questa riga si può riscalare (R2, secondo modo): ha una dose strutturata più
      * grande di zero. Lo decide il server; «q.b.» e le righe senza dose no. */
     anchorable: boolean;
     /** La parola dell'unità da scrivere accanto al campo «Quanto ne fai?»: il plurale
      * deciso, o la parola com'è arrivata. `null` per un numero nudo, o se la riga non si
      * riscala. */
     anchor_unit: string | null;
   ```
2. Subito **prima** di `export interface RecipeDetail extends RecipeSummary {`, aggiungi:
   ```ts
   /** La dose fissata da cui il server ha riscalato la ricetta (R2, secondo modo). */
   export interface RecipeAnchor {
     ingredient_id: string;
     /** La dose come il server l'ha letta, col punto («112.5»): torna così alla cottura. */
     amount: string;
     /** Le porzioni che quella dose fa, già arrotondate dal server; `null` se la ricetta
      * non dice per quante porzioni è. */
     equivalent_servings: number | null;
   }
   ```
3. In `export interface RecipeDetail`, dopo `dose_lines: number;` (e il suo commento), aggiungi:
   ```ts
     /** La dose fissata, se la risposta è riscalata da un ingrediente; `null` altrimenti —
      * anche quando il server ha ignorato un'ancora che la ricetta non ha più. */
     anchor: RecipeAnchor | null;
   ```

- [ ] **Step 4: L'API**

In `frontend/src/features/recipes/api.ts`:

1. La funzione
   ```ts
   export function fetchRecipe(id: string, servings?: number) {
     const query = servings ? `?servings=${servings}` : "";
     return apiFetch<RecipeDetail>(`/recipes/${id}${query}`);
   }
   ```
   diventa
   ```ts
   /** Come si chiede la ricetta: per porzioni, o da una dose fissata su una riga (R2,
    * secondo modo). Un modo alla volta: il server rifiuta i due insieme. `amount` va col
    * punto. */
   export type RecipeScale = { servings: number } | { anchor: string; amount: string };

   export function fetchRecipe(id: string, scale?: RecipeScale) {
     let query = "";
     if (scale !== undefined && "servings" in scale) {
       query = `?servings=${scale.servings}`;
     } else if (scale !== undefined) {
       query = `?anchor=${encodeURIComponent(scale.anchor)}&amount=${encodeURIComponent(scale.amount)}`;
     }
     return apiFetch<RecipeDetail>(`/recipes/${id}${query}`);
   }
   ```
2. In `cookRecipe`, il tipo del corpo
   ```ts
     body: {
       servings?: number;
       transitions: { pantry_item_id: string; to_status: string; restock: boolean }[];
     }
   ```
   diventa
   ```ts
     body: {
       servings?: number;
       // R2, secondo modo: la dose fissata, al posto di `servings`
       anchor?: string;
       amount?: string;
       transitions: { pantry_item_id: string; to_status: string; restock: boolean }[];
     }
   ```

- [ ] **Step 5: Il 422 non si ritenta**

In `frontend/src/lib/queryRetry.ts`, in fondo al commento sopra `NOT_RETRIED` (dopo «…che è il vicolo cieco che le regole di casa vietano.») aggiungi la riga
```ts
// E un 422: la domanda è sbagliata (la dose oltre le 50 volte di R2), e rifatta uguale
// resta sbagliata — ritentarla faceva aspettare tre secondi la frase che dice cosa fare.
```
e la riga
```ts
const NOT_RETRIED = new Set([401, 404]);
```
diventa
```ts
const NOT_RETRIED = new Set([401, 404, 422]);
```

- [ ] **Step 6: La cottura manda l'ancora**

In `frontend/src/features/cooking/CookSheet.tsx`, dentro `mutationFn` di `cook`, la riga
```ts
        servings: recipe.scaled_to ?? recipe.servings ?? undefined,
```
(quella sotto il commento che comincia con «le porzioni per cui si è scalato, se si è scalato») diventa
```ts
        // Riscalata da una dose (R2, secondo modo): si manda la dose, non le porzioni.
        // «≈ 1,5» non è un numero di porzioni che qualcuno ha scelto, e scriverlo
        // arrotondato sarebbe lo stesso errore di un 2 al posto di un 6; il server
        // registra la dose nello storico e ne ricalcola il fattore.
        ...(recipe.anchor
          ? { anchor: recipe.anchor.ingredient_id, amount: recipe.anchor.amount }
          : { servings: recipe.scaled_to ?? recipe.servings ?? undefined }),
```
(`recipe.anchor` e non `recipe.anchor !== null`: una risposta di un backend vecchio, in cache nel service worker, non ha il campo.)

- [ ] **Step 7: I campi nuovi nelle voci finte**

Run: `npm run typecheck`
Expected: errori `TS2739`/`TS2741` («Property 'anchorable' is missing», «Property 'anchor' is missing») nei test che costruiscono a mano un `RecipeDetail` o una `RecipeIngredientLine` (su `master`: `RecipeDetailScreen.test.tsx` `DETAIL`, `RecipeDetailActions.test.tsx`, `CookSheet.test.tsx` `RECIPE`, `AddMissingButton.test.tsx` e `missingToList.test.ts` nella funzione `riga`, `formModel.test.ts`, `RecipeForm.test.tsx`, `RecipeEditScreen.test.tsx`). In ognuno, e solo lì:

- in ogni riga, subito dopo `quantity_scaled: …,` aggiungi i due campi come il server li manderebbe: se `quantity_text` è un numero seguito da `g` («180 g», «320 g», «400 g») → `anchorable: true, anchor_unit: "g",`; se è un numero nudo → `anchorable: true, anchor_unit: null,`; altrimenti («q.b.», `null`) → `anchorable: false, anchor_unit: null,`;
- in ogni `RecipeDetail`, subito dopo `dose_lines: …,` aggiungi `anchor: null,`.

Nessun'altra modifica a quei test. In `RecipeDetailScreen.test.tsx` vuol dire che le righe «pasta» (180 g) e «pomodoro» (400 g) di `DETAIL` sono `anchorable: true, anchor_unit: "g"`, le altre tre `false`/`null`: il Task 6 conta su questo. Rilancia `npm run typecheck` finché non è pulito.

- [ ] **Step 8: Passano, e tutto il resto anche**

Run: `npx vitest run`
Expected: tutto verde, `N_vitest` + 5 (3 di `fetchRecipe`, 1 del 422, 1 della cottura). I test del dettaglio passano anche con le dosi «180 g» e «400 g» ancora testo: il Task 6 le fa diventare pulsanti.

- [ ] **Step 9: Commit**

```bash
git add frontend/src
git commit -m "R2: i tipi e fetchRecipe con la dose fissata, il 422 non si ritenta, la cottura manda l'ancora"
```

---

### Task 5: Lo stepper con «≈», il numero scritto, il campo «Quanto ne fai?»

**Files:**
- Modify (file intero): `frontend/src/features/cooking/ServingsStepper.tsx`; Test: `frontend/src/features/cooking/ServingsStepper.test.tsx`
- Create: `frontend/src/features/cooking/anchorAmount.ts`, `frontend/src/features/cooking/anchorAmount.test.ts`
- Create: `frontend/src/features/cooking/AnchorField.tsx`, `frontend/src/features/cooking/AnchorField.test.tsx`

**Interfaces:**
- Produces: `ServingsStepper({ value, approx?, onChange })` con `approx?: number | null`; `readAmount(text: string): AmountReading` dove `AmountReading = { amount: string; problem?: undefined } | { amount?: undefined; problem: string }`, e le costanti `AMOUNT_EMPTY`, `AMOUNT_NOT_A_NUMBER`, `AMOUNT_ZERO`; `AnchorField({ unit: string | null; initial: string; onSubmit: (amount: string) => Promise<string | null>; onCancel: () => void })`. Il Task 6 li usa.

- [ ] **Step 1: I test che falliscono**

1. In `frontend/src/features/cooking/ServingsStepper.test.tsx`, dentro `describe("ServingsStepper", …)`, in fondo, aggiungi:
   ```tsx
     it("con una dose fissata dice le porzioni che fa, e − e + vanno all'intero sotto e sopra", async () => {
       const onChange = vi.fn();
       render(<ServingsStepper value={2} approx={1.5} onChange={onChange} />);

       expect(screen.getByText("≈ 1,5")).toBeInTheDocument();
       await userEvent.click(screen.getByRole("button", { name: "Una porzione in più" }));
       await userEvent.click(screen.getByRole("button", { name: "Una porzione in meno" }));
       expect(onChange.mock.calls).toEqual([[2], [1]]);
     });

     it("su un numero intero di porzioni equivalenti, − e + vanno al precedente e al successivo", async () => {
       const onChange = vi.fn();
       render(<ServingsStepper value={4} approx={2} onChange={onChange} />);

       expect(screen.getByText("≈ 2")).toBeInTheDocument();
       await userEvent.click(screen.getByRole("button", { name: "Una porzione in più" }));
       await userEvent.click(screen.getByRole("button", { name: "Una porzione in meno" }));
       expect(onChange.mock.calls).toEqual([[3], [1]]);
     });

     it("sotto una porzione il − si spegne; sopra 50 il + si spegne e il − va a 50", async () => {
       const onChange = vi.fn();
       const { rerender } = render(<ServingsStepper value={2} approx={0.75} onChange={onChange} />);

       expect(screen.getByText("≈ 0,75")).toBeInTheDocument();
       expect(screen.getByRole("button", { name: "Una porzione in meno" })).toBeDisabled();
       await userEvent.click(screen.getByRole("button", { name: "Una porzione in più" }));

       rerender(<ServingsStepper value={4} approx={200} onChange={onChange} />);
       expect(screen.getByRole("button", { name: "Una porzione in più" })).toBeDisabled();
       await userEvent.click(screen.getByRole("button", { name: "Una porzione in meno" }));
       expect(onChange.mock.calls).toEqual([[1], [50]]);
     });
   ```
2. Crea `frontend/src/features/cooking/anchorAmount.test.ts`:
   ```ts
   import { describe, expect, it } from "vitest";
   import { AMOUNT_EMPTY, AMOUNT_NOT_A_NUMBER, AMOUNT_ZERO, readAmount } from "./anchorAmount";

   describe("readAmount", () => {
     // la forma e basta: se la dose vada bene per la ricetta lo dice il server
     it.each([
       ["150", "150"],
       ["150,5", "150.5"],
       ["1.5", "1.5"],
       [" 80 ", "80"],
       ["0,001", "0.001"],
       ["9999999", "9999999"],
     ])("«%s» parte come %s", (scritto, atteso) => {
       expect(readAmount(scritto)).toEqual({ amount: atteso });
     });

     it.each([
       ["", AMOUNT_EMPTY],
       ["   ", AMOUNT_EMPTY],
       ["tanta", AMOUNT_NOT_A_NUMBER],
       ["-5", AMOUNT_NOT_A_NUMBER],
       // tre decimali, come la colonna delle dosi
       ["1,2345", AMOUNT_NOT_A_NUMBER],
       // l'unità sta accanto alla casella, non dentro
       ["1,5 g", AMOUNT_NOT_A_NUMBER],
       // sette cifre intere: sotto i 10 000 000 che il server accetta
       ["10000000", AMOUNT_NOT_A_NUMBER],
       ["1e3", AMOUNT_NOT_A_NUMBER],
       ["0", AMOUNT_ZERO],
       ["0,000", AMOUNT_ZERO],
     ])("«%s» non parte: %s", (scritto, perche) => {
       expect(readAmount(scritto)).toEqual({ problem: perche });
     });
   });
   ```
3. Crea `frontend/src/features/cooking/AnchorField.test.tsx`:
   ```tsx
   import { describe, expect, it, vi } from "vitest";
   import { render, screen } from "@testing-library/react";
   import userEvent from "@testing-library/user-event";
   import { AnchorField } from "./AnchorField";
   import { AMOUNT_EMPTY, AMOUNT_NOT_A_NUMBER } from "./anchorAmount";

   const FUORI_SCALA =
     "Così la ricetta cambierebbe più di 50 volte: scrivi un numero fra 6 g e 15000 g.";

   function renderField(props: Partial<Parameters<typeof AnchorField>[0]> = {}) {
     const onSubmit = props.onSubmit ?? vi.fn().mockResolvedValue(null);
     const onCancel = props.onCancel ?? vi.fn();
     render(
       <AnchorField
         unit={props.unit === undefined ? "g" : props.unit}
         initial={props.initial ?? ""}
         onSubmit={onSubmit}
         onCancel={onCancel}
       />
     );
     return {
       onSubmit,
       onCancel,
       campo: screen.getByRole("textbox", { name: "Quanto ne fai?" }),
       riscala: screen.getByRole("button", { name: "Riscala" }),
     };
   }

   describe("AnchorField", () => {
     it("si apre col fuoco nella casella, la tastiera dei numeri, e l'unità della riga accanto", () => {
       const { campo } = renderField();
       expect(campo).toHaveFocus();
       expect(campo).toHaveAttribute("inputmode", "decimal");
       expect(campo).toHaveAccessibleDescription("g");
       expect(screen.getByText("g")).toBeInTheDocument();
     });

     it("un numero nudo non ha un'unità accanto", () => {
       const { campo } = renderField({ unit: null });
       expect(campo).not.toHaveAttribute("aria-describedby");
     });

     it("vuoto o non un numero, «Riscala» dice perché e non manda niente", async () => {
       const { campo, riscala, onSubmit } = renderField();
       expect(riscala).toHaveAttribute("aria-disabled", "true");
       expect(riscala).toHaveAccessibleDescription(AMOUNT_EMPTY);

       await userEvent.type(campo, "tanta");
       expect(riscala).toHaveAccessibleDescription(AMOUNT_NOT_A_NUMBER);
       await userEvent.click(riscala);
       await userEvent.type(campo, "{Enter}");
       expect(onSubmit).not.toHaveBeenCalled();
     });

     it("la virgola parte come punto", async () => {
       const { campo, riscala, onSubmit } = renderField();
       await userEvent.type(campo, "150,5");
       expect(riscala).not.toHaveAttribute("aria-disabled");
       await userEvent.click(riscala);
       expect(onSubmit).toHaveBeenCalledWith("150.5");
     });

     it("il perché del server resta sotto la casella, col numero scritto, e scrivendo se ne va", async () => {
       const onSubmit = vi.fn().mockResolvedValue(FUORI_SCALA);
       const { campo, riscala } = renderField({ onSubmit });
       await userEvent.type(campo, "99999");
       await userEvent.click(riscala);

       expect(await screen.findByRole("alert")).toHaveTextContent(FUORI_SCALA);
       expect(campo).toHaveValue("99999");
       // si può correggere e riprovare subito
       expect(riscala).not.toHaveAttribute("aria-disabled");
       await userEvent.type(campo, "{Backspace}");
       expect(screen.queryByRole("alert")).toBeNull();
     });

     it("«Annulla» chiude senza mandare niente", async () => {
       const { campo, onSubmit, onCancel } = renderField();
       await userEvent.type(campo, "80");
       await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
       expect(onCancel).toHaveBeenCalledTimes(1);
       expect(onSubmit).not.toHaveBeenCalled();
     });

     it("parte dalla dose già fissata, se c'è", () => {
       const { campo, riscala } = renderField({ initial: "112,5" });
       expect(campo).toHaveValue("112,5");
       expect(riscala).not.toHaveAttribute("aria-disabled");
     });

     it("in volo «Riscala» aspetta, e un secondo tocco non riparte", async () => {
       const onSubmit = vi.fn(() => new Promise<string | null>(() => {}));
       const { campo, riscala } = renderField({ onSubmit });
       await userEvent.type(campo, "150");
       await userEvent.click(riscala);
       await userEvent.click(riscala);
       expect(onSubmit).toHaveBeenCalledTimes(1);
       expect(riscala).toHaveAttribute("aria-disabled", "true");
     });
   });
   ```

- [ ] **Step 2: Falliscono**

Run: `npx vitest run src/features/cooking/ServingsStepper.test.tsx src/features/cooking/anchorAmount.test.ts src/features/cooking/AnchorField.test.tsx`
Expected: FAIL — i due file nuovi non trovano i moduli (`Failed to resolve import "./anchorAmount"`, `"./AnchorField"`); i tre test nuovi dello stepper non trovano «≈ 1,5» (la prop `approx` non esiste, si vede il numero). I quattro test di oggi dello stepper passano.

- [ ] **Step 3: Lo stepper**

Sostituisci `frontend/src/features/cooking/ServingsStepper.tsx` con:

```tsx
import { Button } from "../../components/ui/Button";
import { IconMinus, IconPlus } from "../../components/ui/icons";

// Il perché dello stepper fermo. Sta sul «+» soltanto: `Button` disegna il motivo sotto
// di sé, e con due pulsanti la stessa frase comparirebbe due volte in una riga.
const SERVINGS_UNKNOWN = "Porzioni non indicate: si cambiano da «Modifica».";

// la scala delle porzioni, la stessa del backend (`Query(ge=1, le=50)`)
const MIN = 1;
const MAX = 50;

/** «≈ 1,5»: le porzioni che fa una dose fissata, col numero già arrotondato dal server.
 * Qui si mette solo la virgola. */
function approxText(approx: number): string {
  return `≈ ${approx.toLocaleString("it-IT", { maximumFractionDigits: 2 })}`;
}

/** Per quante porzioni si vuole la ricetta.
 *
 * Si vede sempre (spec T3 §4.6): senza porzioni dichiarate non c'è una base da cui
 * riscalare, e invece di sparire — dal giro, «senza porzioni lo stepper sparisce senza
 * dirlo» — lo dice. Il «−» a porzioni ignote è spento come ai bordi: non c'è niente da
 * togliere. I due tasti sono bersagli da 44 px (`Button` di sola icona): questo si tocca
 * in cucina, con le mani occupate.
 *
 * Con una dose fissata su una riga (R2, secondo modo) `approx` porta le porzioni che quella
 * dose fa, e lo stepper le dice al posto del numero: «≈ 1,5». Toccarlo torna alle porzioni
 * intere (un modo alla volta, Mattia): − all'intero più grande sotto, + al più piccolo
 * sopra — da ≈ 1,5 a 1 e a 2, da ≈ 2 a 1 e a 3 —, dentro 1–50. */
export function ServingsStepper({
  value,
  approx = null,
  onChange,
}: {
  value: number | null;
  approx?: number | null;
  onChange: (next: number) => void;
}) {
  const below =
    approx !== null ? Math.min(Math.ceil(approx) - 1, MAX) : value !== null ? value - 1 : null;
  const above =
    approx !== null ? Math.max(Math.floor(approx) + 1, MIN) : value !== null ? value + 1 : null;
  const unknown = value === null && approx === null;

  return (
    // `[&>p]:basis-full`: il motivo del «+» (un `<p>` fratello del `<button>`, disegnato
    // da `Button`) è un figlio diretto di questa riga `flex flex-wrap`; senza questa
    // classe finirebbe a fianco dello stepper invece che a capo, sotto di lui (R-2).
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 [&>p]:basis-full">
      <span className="text-sm text-ink-soft">Porzioni</span>
      <Button
        icon={IconMinus}
        label="Una porzione in meno"
        disabled={below === null || below < MIN}
        onClick={() => {
          if (below !== null) onChange(below);
        }}
      />
      <span className="min-w-8 text-center font-medium" aria-live="polite">
        {approx !== null ? approxText(approx) : (value ?? "—")}
      </span>
      <Button
        icon={IconPlus}
        label="Una porzione in più"
        disabled={above !== null && above > MAX}
        unavailableReason={unknown ? SERVINGS_UNKNOWN : undefined}
        onClick={() => {
          if (above !== null) onChange(above);
        }}
      />
    </div>
  );
}
```

- [ ] **Step 4: Il numero scritto**

Crea `frontend/src/features/cooking/anchorAmount.ts`:

```ts
/** Il numero scritto in «Quanto ne fai?» (R2, secondo modo), letto per il server.
 *
 * Solo la forma: un numero più grande di zero, con la virgola o il punto, fino a sette
 * cifre intere e tre decimali — i tre decimali della colonna `quantity_value`, e sotto i
 * 10 000 000 che il server accetta. Se quel numero vada bene per la ricetta (il limite
 * delle 50 volte) lo dice il server: qui non si sa la dose della ricetta, e non si calcola
 * niente. */

export const AMOUNT_EMPTY = "Scrivi quanto ne fai.";
export const AMOUNT_NOT_A_NUMBER = "Scrivi un numero, come 150 o 1,5.";
export const AMOUNT_ZERO = "Scrivi un numero più grande di zero.";

const NUMBER = /^\d{1,7}(?:[.,]\d{1,3})?$/;

export type AmountReading =
  | { amount: string; problem?: undefined }
  | { amount?: undefined; problem: string };

export function readAmount(text: string): AmountReading {
  const trimmed = text.trim();
  if (trimmed === "") return { problem: AMOUNT_EMPTY };
  if (!NUMBER.test(trimmed)) return { problem: AMOUNT_NOT_A_NUMBER };
  // il server vuole il punto; chi scrive in italiano mette la virgola
  const amount = trimmed.replace(",", ".");
  if (Number(amount) === 0) return { problem: AMOUNT_ZERO };
  return { amount };
}
```

- [ ] **Step 5: Il campo**

Crea `frontend/src/features/cooking/AnchorField.tsx`:

```tsx
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { readAmount } from "./anchorAmount";

/** «Quanto ne fai?», sotto una riga d'ingrediente del dettaglio (R2, secondo modo).
 *
 * Il campo legge un numero e basta: il fattore, le dosi delle altre righe, le porzioni
 * equivalenti e il limite delle 50 volte li decide il server, che risponde a `onSubmit`.
 * Si riscala al tocco di «Riscala» o all'Invio, non a ogni cifra: ogni cifra sarebbe una
 * rilettura della ricetta, e le dosi salterebbero mentre si scrive.
 *
 * `onSubmit` torna `null` se la vista è cambiata — allora chi ha aperto il campo lo chiude
 * e questo componente si smonta — oppure la frase da mostrare sotto la casella, che resta
 * aperta col numero scritto: la strada per correggerlo (mai un vicolo cieco).
 *
 * L'etichetta è «Quanto ne fai?» con l'unità accanto alla casella, e non «Quanti g ne
 * fai?»: con l'unità dentro la domanda l'accordo dipende dall'unità («Quanti fette»), e il
 * registro delle unità non sa il genere (deciso da Mattia il 2026-10-13, spec §4). */
export function AnchorField({
  unit,
  initial,
  onSubmit,
  onCancel,
}: {
  /** La parola dell'unità della riga, accanto alla casella; `null` per un numero nudo. */
  unit: string | null;
  /** Il testo con cui si apre: vuoto, o la dose già fissata su questa riga. */
  initial: string;
  onSubmit: (amount: string) => Promise<string | null>;
  onCancel: () => void;
}) {
  const [text, setText] = useState(initial);
  const [pending, setPending] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const inputId = useId();
  const unitId = useId();

  // il campo si apre per essere scritto: il fuoco ci va da sé, e al telefono la tastiera
  // dei numeri si apre senza un secondo tocco
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const reading = readAmount(text);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (reading.amount === undefined || pending) return;
    setPending(true);
    setRefusal(null);
    const problem = await onSubmit(reading.amount);
    if (problem !== null) {
      setRefusal(problem);
      setPending(false);
    }
  }

  return (
    // `[&>p]`: il perché di «Riscala» (un `<p>` fratello disegnato da `Button`) e il
    // rifiuto del server vanno a capo in fondo, sotto tutta la riga, invece di stringersi
    // fra i due pulsanti
    <form
      onSubmit={(event) => void submit(event)}
      className="flex flex-wrap items-center gap-2 pt-2 [&>p]:order-last [&>p]:basis-full"
    >
      <label htmlFor={inputId} className="text-sm text-ink-soft">
        Quanto ne fai?
      </label>
      <input
        ref={inputRef}
        id={inputId}
        value={text}
        onChange={(event) => {
          setText(event.target.value);
          setRefusal(null);
        }}
        inputMode="decimal"
        autoComplete="off"
        enterKeyHint="done"
        aria-describedby={unit !== null ? unitId : undefined}
        className="min-h-11 w-28 text-right"
      />
      {unit !== null && (
        <span id={unitId} className="text-sm text-ink-soft">
          {unit}
        </span>
      )}
      <Button type="submit" busy={pending} unavailableReason={reading.problem}>
        Riscala
      </Button>
      <Button variant="ghost" onClick={onCancel}>
        Annulla
      </Button>
      {refusal !== null && <Alert>{refusal}</Alert>}
    </form>
  );
}
```

- [ ] **Step 6: Passano**

Run: `npx vitest run src/features/cooking/ServingsStepper.test.tsx src/features/cooking/anchorAmount.test.ts src/features/cooking/AnchorField.test.tsx`
Expected: tutto verde: 4 + 3 test dello stepper, 16 di `readAmount`, 8 del campo.

Poi `npm run typecheck` e `npm run lint`: puliti.

- [ ] **Step 7: Commit**

```bash
git add src/features/cooking/ServingsStepper.tsx src/features/cooking/ServingsStepper.test.tsx src/features/cooking/anchorAmount.ts src/features/cooking/anchorAmount.test.ts src/features/cooking/AnchorField.tsx src/features/cooking/AnchorField.test.tsx
git commit -m "R2: lo stepper dice «≈ 1,5» e torna alle porzioni intere; il campo «Quanto ne fai?»"
```

---

### Task 6: Il dettaglio — la dose si tocca, il campo si apre, la vista cambia

**Files:**
- Modify: `frontend/src/features/cooking/RecipeDetailScreen.tsx` (gli import, `IngredientRow`, lo stato, la query, `anchorOn`, il ramo d'errore, lo stepper e le righe)
- Test: `frontend/src/features/cooking/RecipeDetailScreen.test.tsx`

Leggi `RecipeDetailScreen.tsx` com'è sul ramo prima di cambiarlo (da `master` nessun piano della notte lo tocca; il test sì, il Task 4 ci ha aggiunto i campi nuovi).

**Interfaces:**
- Consumes: dal Task 4 `RecipeScale`, `fetchRecipe(id, scale)`, `RecipeDetail.anchor`, `RecipeIngredientLine.anchorable`/`anchor_unit`; dal Task 5 `ServingsStepper` con `approx`, `AnchorField`.
- Produces: nel dettaglio, la dose riscalabile come pulsante «{dose}: riscala da {nome}» con `aria-expanded`; il campo sotto la riga; «Riscalata da {nome}: {dose}.» con «Torna alle dosi della ricetta». Il Task 7 li prova nel browser.

- [ ] **Step 1: I test che falliscono**

In fondo a `frontend/src/features/cooking/RecipeDetailScreen.test.tsx` aggiungi (i nomi `DETAIL`, `PANTRY`, `renderScreen` sono quelli in cima al file; `DETAIL` dopo il Task 4 ha «pasta» e «pomodoro» `anchorable` con `anchor_unit: "g"`):

```tsx
describe("riporzionare da un ingrediente (R2, secondo modo)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  // il server riscala, il client chiede e mostra: queste stringhe le detta il finto.
  // 135 g dei 180 della ricetta per 2 sono 0,75: 300 g di pomodoro, «≈ 1,5»
  const ANCORATA: RecipeDetail = {
    ...DETAIL,
    anchor: { ingredient_id: "i1", amount: "135", equivalent_servings: 1.5 },
    unscalable_lines: 2,
    ingredients: [
      { ...DETAIL.ingredients[0], quantity_display: "135 g", quantity_scaled: true },
      { ...DETAIL.ingredients[1], quantity_display: "300 g", quantity_scaled: true },
      ...DETAIL.ingredients.slice(2),
    ],
  };
  const FUORI_SCALA =
    "Così la ricetta cambierebbe più di 50 volte: scrivi un numero fra 3,6 g e 9000 g.";

  const json = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), { status });

  /** La dispensa per la dispensa, `anchored` per una ricetta chiesta da una dose, `base`
   * per tutto il resto (la ricetta com'è e per porzioni). Torna gli indirizzi chiesti. */
  function stubAnchored(
    anchored: (url: string) => Response = () => json(ANCORATA),
    base: RecipeDetail = DETAIL
  ) {
    const urls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: unknown) => {
        const indirizzo = String(url);
        urls.push(indirizzo);
        if (indirizzo.includes("/pantry")) return Promise.resolve(json(PANTRY));
        if (indirizzo.includes("anchor=")) return Promise.resolve(anchored(indirizzo));
        return Promise.resolve(json(base));
      })
    );
    return urls;
  }

  async function riscala(dose: string, nome: string, quanto: string) {
    await userEvent.click(await screen.findByRole("button", { name: `${dose}: riscala da ${nome}` }));
    const campo = screen.getByRole("textbox", { name: "Quanto ne fai?" });
    await userEvent.clear(campo);
    await userEvent.type(campo, quanto);
    await userEvent.click(screen.getByRole("button", { name: "Riscala" }));
  }

  it("una dose che si riscala si tocca; «q.b.» no", async () => {
    stubAnchored();
    renderScreen();
    expect(await screen.findByRole("button", { name: "180 g: riscala da pasta" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "400 g: riscala da pomodoro" })).toBeInTheDocument();
    const aglio = screen.getByText("Aglio").closest("li")!;
    expect(within(aglio).getByText("q.b.")).toBeInTheDocument();
    expect(within(aglio).queryByRole("button")).toBeNull();
  });

  it("il tocco apre «Quanto ne fai?» sotto la sua riga, col fuoco; un campo alla volta", async () => {
    stubAnchored();
    renderScreen();
    const pasta = await screen.findByRole("button", { name: "180 g: riscala da pasta" });
    expect(pasta).toHaveAttribute("aria-expanded", "false");

    await userEvent.click(pasta);
    expect(pasta).toHaveAttribute("aria-expanded", "true");
    const riga = pasta.closest("li")!;
    const campo = within(riga).getByRole("textbox", { name: "Quanto ne fai?" });
    expect(campo).toHaveFocus();
    expect(campo).toHaveAccessibleDescription("g");

    await userEvent.click(screen.getByRole("button", { name: "400 g: riscala da pomodoro" }));
    expect(within(riga).queryByRole("textbox")).toBeNull();
    expect(screen.getAllByRole("textbox", { name: "Quanto ne fai?" })).toHaveLength(1);
    expect(
      within(screen.getByText("Pomodoro").closest("li")!).getByRole("textbox")
    ).toHaveFocus();
  });

  it("«Riscala» chiede la ricetta da quella dose, e mostra quel che dice il server", async () => {
    const urls = stubAnchored();
    renderScreen();
    await riscala("180 g", "pasta", "135");

    expect(await screen.findByText("300 g")).toBeInTheDocument();
    expect(urls.some((url) => url.endsWith("/recipes/r1?anchor=i1&amount=135"))).toBe(true);
    expect(screen.getByText("≈ 1,5")).toBeInTheDocument();
    expect(screen.getByText("Riscalata da pasta: 135 g.")).toBeInTheDocument();
    expect(screen.getByText(/2 dosi su 4 non si riscalano/)).toBeInTheDocument();
    // il campo si chiude, e il fuoco torna sulla dose, che dice quella scritta
    expect(screen.queryByRole("textbox", { name: "Quanto ne fai?" })).toBeNull();
    expect(screen.getByRole("button", { name: "135 g: riscala da pasta" })).toHaveFocus();
  });

  it("con una dose fissata, + torna alle porzioni intere", async () => {
    const urls = stubAnchored();
    renderScreen();
    await riscala("180 g", "pasta", "135");
    await screen.findByText("≈ 1,5");

    // da ≈ 1,5 il + va a 2: le porzioni della ricetta, cioè la ricetta com'è
    await userEvent.click(screen.getByRole("button", { name: "Una porzione in più" }));
    expect(await screen.findByText("180 g")).toBeInTheDocument();
    expect(urls.some((url) => url.endsWith("/recipes/r1?servings=2"))).toBe(true);
    expect(screen.queryByText(/Riscalata da/)).toBeNull();
    expect(screen.queryByText("≈ 1,5")).toBeNull();
  });

  it("«Torna alle dosi della ricetta» toglie la dose fissata", async () => {
    stubAnchored();
    renderScreen();
    await riscala("180 g", "pasta", "135");

    await userEvent.click(await screen.findByRole("button", { name: "Torna alle dosi della ricetta" }));
    expect(await screen.findByText("180 g")).toBeInTheDocument();
    expect(screen.queryByText(/Riscalata da/)).toBeNull();
    expect(screen.queryByText("≈ 1,5")).toBeNull();
  });

  it("oltre le 50 volte la frase del server resta sotto il campo, e la ricetta com'era", async () => {
    stubAnchored(() => json({ detail: FUORI_SCALA }, 422));
    renderScreen();
    await riscala("180 g", "pasta", "99999");

    const riga = screen.getByRole("button", { name: "180 g: riscala da pasta" }).closest("li")!;
    expect(await within(riga).findByRole("alert")).toHaveTextContent(FUORI_SCALA);
    expect(within(riga).getByRole("textbox", { name: "Quanto ne fai?" })).toHaveValue("99999");
    expect(screen.getByText("400 g")).toBeInTheDocument();
    expect(screen.queryByText(/Riscalata da/)).toBeNull();
  });

  it("se il server non risponde, il campo resta e lo dice", async () => {
    stubAnchored(() => json({ detail: "guasto" }, 500));
    renderScreen();
    await riscala("180 g", "pasta", "135");

    expect(await screen.findByRole("alert")).toHaveTextContent("Non sono riuscito a riscalare. Riprova.");
    expect(screen.getByRole("textbox", { name: "Quanto ne fai?" })).toHaveValue("135");
    expect(screen.getByText("400 g")).toBeInTheDocument();
  });

  it("senza porzioni dichiarate si riscala lo stesso, e lo stepper resta fermo col suo perché", async () => {
    stubAnchored(
      () => json({ ...ANCORATA, servings: null, anchor: { ...ANCORATA.anchor!, equivalent_servings: null } }),
      { ...DETAIL, servings: null }
    );
    renderScreen();
    await riscala("180 g", "pasta", "135");

    expect(await screen.findByText("Riscalata da pasta: 135 g.")).toBeInTheDocument();
    const piu = screen.getByRole("button", { name: "Una porzione in più" });
    expect(piu).toHaveAttribute("aria-disabled", "true");
    expect(piu).toHaveAccessibleDescription("Porzioni non indicate: si cambiano da «Modifica».");
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.queryByText(/≈/)).toBeNull();
    // l'uscita c'è anche qui, dove − e + sono spenti
    expect(screen.getByRole("button", { name: "Torna alle dosi della ricetta" })).toBeInTheDocument();
  });

  it("«Annulla» chiude il campo e ridà il fuoco alla dose", async () => {
    stubAnchored();
    renderScreen();
    const pasta = await screen.findByRole("button", { name: "180 g: riscala da pasta" });
    await userEvent.click(pasta);
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));

    expect(screen.queryByRole("textbox", { name: "Quanto ne fai?" })).toBeNull();
    expect(pasta).toHaveFocus();
  });

  it("una vista riscalata che il server smette di dare porta alle dosi della ricetta, non a «Riprova»", async () => {
    // la prima risposta accetta la dose; la rilettura (la ricetta è stata modificata in
    // un'altra scheda) la rifiuta. «Riprova» rifarebbe la stessa domanda
    let volte = 0;
    stubAnchored(() => (++volte === 1 ? json(ANCORATA) : json({ detail: FUORI_SCALA }, 422)));
    renderScreen();
    await riscala("180 g", "pasta", "135");

    expect(
      await screen.findByText("Non riesco più a riscalare da quella dose: la ricetta è cambiata.")
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Riprova" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Torna alle dosi della ricetta" }));
    expect(await screen.findByText("180 g")).toBeInTheDocument();
  });
});
```

Se `RecipeDetail` non è già importato come tipo in cima al file, è nell'import `import type { PantryItem, RecipeDetail } from "../../domain/types";` (su `master` c'è).

- [ ] **Step 2: Falliscono**

Run: `npx vitest run src/features/cooking/RecipeDetailScreen.test.tsx`
Expected: i dieci nuovi FAIL (nessun pulsante «180 g: riscala da pasta»: la dose è un `<span>`); gli altri del file passano.

- [ ] **Step 3: Gli import**

In `frontend/src/features/cooking/RecipeDetailScreen.tsx`:

1. `import { fetchRecipe, setRecipeArchived } from "../recipes/api";` diventa
   ```tsx
   import { fetchRecipe, setRecipeArchived, type RecipeScale } from "../recipes/api";
   ```
2. Dopo `import { AddMissingButton } from "./AddMissingButton";` aggiungi
   ```tsx
   import { AnchorField } from "./AnchorField";
   ```

- [ ] **Step 4: La riga d'ingrediente**

La funzione `IngredientRow` (col suo commento sopra, che resta) diventa:

```tsx
function IngredientRow({
  line,
  anchoredAmount,
  open,
  onOpen,
  onClose,
  onAnchor,
}: {
  line: RecipeIngredientLine;
  /** La dose fissata su questa riga, se è lei l'ancora (R2), come la manda il server. */
  anchoredAmount: string | null;
  /** Se il campo «Quanto ne fai?» di questa riga è aperto: uno alla volta. */
  open: boolean;
  onOpen: () => void;
  onClose: () => void;
  /** Riscala da questa riga: `null` se è fatto, o il perché se no. */
  onAnchor: (amount: string) => Promise<string | null>;
}) {
  // la dose toccabile riprende il fuoco quando il campo si chiude, da «Annulla» o da una
  // riscala riuscita: il campo che lo aveva si smonta, e il fuoco cadrebbe sul `body`
  const doseRef = useRef<HTMLButtonElement>(null);
  return (
    <li className="px-3 py-2.5">
      <div className="flex items-center gap-2.5">
        <StatusDot availability={line.availability} />
        <span className="min-w-0 flex-1">
          {/* la maiuscola solo a video (spec T3 §4.7): apre la riga, non è dentro una
              frase né in un nome accessibile */}
          <span>{capitalizeFirst(line.ingredient_name)}</span>
          {line.availability === "low" && !line.satisfied && (
            <span className="ml-2 text-xs font-medium text-low">non basta</span>
          )}
        </span>
        {line.quantity_display &&
          (line.anchorable ? (
            // R2, secondo modo: una dose che si riscala si tocca. Un pulsante leggero,
            // sottolineato a puntini (il segno che si tocca), alto 44 px senza alzare la
            // riga (`-my-2.5` restituisce il `py-2.5` della riga); `-mr-3` riporta il testo
            // verso il bordo, dove stanno le dosi che non si toccano. La dose fissata in
            // grassetto dentro un `<strong>`: una seconda classe di colore o di peso sul
            // pulsante litigherebbe con quella di `ghost` nel CSS compilato
            <Button
              ref={doseRef}
              variant="ghost"
              accessibleName={`${line.quantity_display}: riscala da ${line.ingredient_name}`}
              aria-expanded={open}
              onClick={open ? onClose : onOpen}
              className="-my-2.5 -mr-3 shrink-0 underline decoration-dotted underline-offset-4"
            >
              {anchoredAmount !== null ? (
                <strong className="font-semibold text-ink">{line.quantity_display}</strong>
              ) : (
                line.quantity_display
              )}
            </Button>
          ) : (
            <span className="shrink-0 text-sm text-ink-faint">{line.quantity_display}</span>
          ))}
      </div>
      {open && (
        <AnchorField
          unit={line.anchor_unit}
          initial={anchoredAmount?.replace(".", ",") ?? ""}
          onSubmit={async (amount) => {
            const problem = await onAnchor(amount);
            if (problem === null) doseRef.current?.focus();
            return problem;
          }}
          onCancel={() => {
            onClose();
            doseRef.current?.focus();
          }}
        />
      )}
    </li>
  );
}
```

- [ ] **Step 5: Lo stato e la query**

In `RecipeDetailScreen`:

1. Il blocco
   ```tsx
     // le porzioni chieste: è una vista, non si salva. Uscire dalla ricetta se ne
     // dimentica, ed è quel che vuole chi sta guardando cosa cucinare stasera.
     const [servings, setServings] = useState<number | null>(null);
   ```
   diventa
   ```tsx
     // come si vuole vedere la ricetta: per porzioni, o da una dose fissata su una riga
     // (R2, secondo modo). Un modo alla volta, ed è una vista: non si salva, e uscire
     // dalla ricetta se ne dimentica — è quel che vuole chi guarda cosa cucinare stasera.
     // `null` è la ricetta com'è.
     const [scale, setScale] = useState<RecipeScale | null>(null);
     // la riga il cui campo «Quanto ne fai?» è aperto: uno alla volta
     const [anchorField, setAnchorField] = useState<string | null>(null);
   ```
2. Nella `useQuery` della ricetta,
   ```tsx
       queryKey: ["recipe", id, servings],
       queryFn: () => fetchRecipe(id, servings ?? undefined),
   ```
   diventa
   ```tsx
       queryKey: ["recipe", id, scale],
       queryFn: () => fetchRecipe(id, scale ?? undefined),
   ```
   (il commento sotto, su `placeholderData: keepPreviousData`, parla delle porzioni: vale uguale per la dose; lascialo.)
3. Subito **prima** della riga `if (isRecipeLoading) return <p className="p-4 text-ink-soft">Carico…</p>;`, aggiungi:
   ```tsx
     // R2, secondo modo: si chiede prima la ricetta riscalata, e solo se il server la dà
     // la vista cambia. Un 422 (oltre le 50 volte) resta così sotto il campo, con la
     // frase del server, e la ricetta resta com'era: cambiare vista e scoprire dopo il
     // rifiuto avrebbe mandato lo schermo intero nel ramo d'errore. La risposta finisce
     // nella cache con la chiave della query qui sopra, che la trova già pronta (e la
     // rilegge in sottofondo, come ogni dato vecchio).
     async function anchorOn(ingredientId: string, amount: string): Promise<string | null> {
       const next: RecipeScale = { anchor: ingredientId, amount };
       try {
         await queryClient.fetchQuery({
           queryKey: ["recipe", id, next],
           queryFn: () => fetchRecipe(id, next),
         });
       } catch (error) {
         if (error instanceof ApiError && error.status === 422) {
           const detail = (error.body as { detail?: unknown } | null)?.detail;
           if (typeof detail === "string") return detail;
         }
         return "Non sono riuscito a riscalare. Riprova.";
       }
       setAnchorField(null);
       setScale(next);
       return null;
     }
   ```

- [ ] **Step 6: Il ramo d'errore**

Dentro `if (isRecipeError || !recipe) {`, subito **dopo** il blocco del 404 (quello che finisce con il `<Link to="/ricette" …>Torna al ricettario</Link>` e la sua `)` `}`), aggiungi:

```tsx
    // Una vista riscalata già accettata che il server ora rifiuta: la ricetta è stata
    // modificata altrove e la dose è uscita dalle 50 volte. «Riprova» rifarebbe la stessa
    // domanda; l'uscita è la ricetta com'è.
    if (
      recipeError instanceof ApiError &&
      recipeError.status === 422 &&
      scale !== null &&
      "anchor" in scale
    ) {
      return (
        <div className="flex flex-col items-start gap-3 p-4">
          <Alert>Non riesco più a riscalare da quella dose: la ricetta è cambiata.</Alert>
          <Button onClick={() => setScale(null)}>Torna alle dosi della ricetta</Button>
        </div>
      );
    }
```

- [ ] **Step 7: Lo stepper, la riga sotto, le righe**

1. Subito dopo la riga `const missing = recipe.ingredients.filter((line) => !line.satisfied);` (e il suo commento), aggiungi:
   ```tsx
     // la dose fissata, se la vista è riscalata da un ingrediente (R2). `?? null`: una
     // risposta di un backend vecchio, in cache nel service worker, non ha il campo
     const anchor = recipe.anchor ?? null;
     const anchorLine =
       anchor === null
         ? null
         : (recipe.ingredients.find((line) => line.ingredient_id === anchor.ingredient_id) ??
           null);
   ```
2. Il blocco
   ```tsx
             {/* sempre, anche senza porzioni: allora dice perché è fermo */}
             <div className="pt-3">
               <ServingsStepper
                 value={recipe.servings === null ? null : (servings ?? recipe.servings)}
                 onChange={setServings}
               />
             </div>
   ```
   diventa
   ```tsx
             {/* sempre, anche senza porzioni: allora dice perché è fermo. Con una dose
                 fissata dice le porzioni che fa, «≈ 1,5», e toccarlo torna alle porzioni
                 intere (R2: un modo alla volta) */}
             <div className="pt-3">
               <ServingsStepper
                 value={
                   recipe.servings === null
                     ? null
                     : scale !== null && "servings" in scale
                       ? scale.servings
                       : recipe.servings
                 }
                 approx={anchor?.equivalent_servings ?? null}
                 onChange={(next) => {
                   setAnchorField(null);
                   setScale({ servings: next });
                 }}
               />
               {anchorLine !== null && (
                 // da quale dose è riscalata, e l'uscita: sulle ricette senza porzioni − e +
                 // sono spenti, e sarebbe l'unica strada per tornare indietro
                 <div className="flex flex-wrap items-center gap-x-2 pt-1">
                   <p className="text-sm text-ink-soft">
                     Riscalata da {anchorLine.ingredient_name}: {anchorLine.quantity_display}.
                   </p>
                   <Button
                     variant="ghost"
                     onClick={() => {
                       setAnchorField(null);
                       setScale(null);
                     }}
                   >
                     Torna alle dosi della ricetta
                   </Button>
                 </div>
               )}
             </div>
   ```
3. Nelle righe dei gruppi,
   ```tsx
                     {lines.map((line) => (
                       <IngredientRow key={line.ingredient_id} line={line} />
                     ))}
   ```
   diventa
   ```tsx
                     {lines.map((line) => (
                       <IngredientRow
                         key={line.ingredient_id}
                         line={line}
                         anchoredAmount={
                           anchor !== null && anchor.ingredient_id === line.ingredient_id
                             ? anchor.amount
                             : null
                         }
                         open={anchorField === line.ingredient_id}
                         onOpen={() => setAnchorField(line.ingredient_id)}
                         onClose={() => setAnchorField(null)}
                         onAnchor={(amount) => anchorOn(line.ingredient_id, amount)}
                       />
                     ))}
   ```

- [ ] **Step 8: Passano, e il resto del dettaglio anche**

Run: `npx vitest run src/features/cooking/`
Expected: tutto verde, i dieci nuovi compresi. In particolare passano senza modifiche i test di oggi sul selettore delle porzioni (`servings=1`), sull'ordine delle righe (`"Pasta180 g"`: il testo del pulsante è lo stesso) e sulla ricetta senza porzioni.

Poi: `npx vitest run` (tutto verde), `npm run typecheck`, `npm run lint`, `npm run build` (puliti). Se `lint` segnala `react-hooks` su `anchorOn` (una funzione nel corpo del componente, non un hook): non lo è, e non serve `useCallback`; se la regola insiste, scrivilo nel report.

- [ ] **Step 9: Commit**

```bash
git add src/features/cooking/RecipeDetailScreen.tsx src/features/cooking/RecipeDetailScreen.test.tsx
git commit -m "R2: nel dettaglio la dose si tocca, «Quanto ne fai?» riscala tutto da lì, e si torna alle dosi della ricetta"
```

---

### Task 7: Nel browser vero — `riporziona.spec.ts` e il contrasto in `style.spec.ts`

**Files:**
- Create: `frontend/e2e/riporziona.spec.ts`
- Modify: `frontend/e2e/style.spec.ts` (una prova in fondo al file)

Leggi `style.spec.ts` com'è sul ramo: da `master` nessun piano della notte l'ha cambiato su questo ramo. Le funzioni `testiIlleggibili`, `fermo` e `senzaScorrimentoLaterale` ci sono già (su `master`; cercale per nome).

**Interfaces:**
- Consumes: tutto quel che hanno fatto i Task 1–6, sull'app costruita e servita da Nginx.

- [ ] **Step 1: Le prove**

Crea `frontend/e2e/riporziona.spec.ts`:

```ts
import { expect, test, type Page } from "@playwright/test";

/**
 * R2, secondo modo, nel browser vero: si tocca una dose, si scrive quanto se ne fa, e il
 * server riscala il resto. A 375×812, il telefono.
 *
 * Le due ricette si creano con `page.request`, che condivide i cookie della pagina — il
 * seme non ha una ricetta senza porzioni — e si eliminano nel `finally`. La cottura della
 * prima scrive solo uno storico: nessuna confezione di questi ingredienti è in dispensa,
 * quindi niente cambia in dispensa né in lista.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

async function entra(page: Page) {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();
}

async function ingrediente(page: Page, nome: string): Promise<string> {
  const risposta = await page.request.get(`/api/v1/ingredients/search?q=${encodeURIComponent(nome)}`);
  expect(risposta.ok()).toBe(true);
  const trovati = (await risposta.json()) as { id: string; name: string }[];
  const voce = trovati.find((trovato) => trovato.name === nome);
  expect(voce, `«${nome}» non è nel seme`).toBeDefined();
  return voce!.id;
}

/** Farro «160 g», porro «1», sale «q.b.»: una dose piena, un numero nudo, una che non si
 * riscala. */
async function ricetta(page: Page, servings: number | null) {
  const farro = await ingrediente(page, "farro");
  const porro = await ingrediente(page, "porro");
  const sale = await ingrediente(page, "sale");
  const creata = await page.request.post("/api/v1/recipes", {
    data: {
      title: `Farro e2e ${servings === null ? "senza porzioni" : `per ${servings}`} ${Date.now()}`,
      instructions: "Cuoci il farro, poi unisci il porro.",
      servings,
      source: "manual",
      ingredients: [
        { ingredient_id: farro, role: "primary", quantity_text: "160 g" },
        { ingredient_id: porro, role: "primary", quantity_text: "1" },
        { ingredient_id: sale, role: "secondary", quantity_text: "q.b." },
      ],
    },
  });
  expect(creata.ok()).toBe(true);
  const id = ((await creata.json()) as { id: string }).id;
  return {
    id,
    farro,
    elimina: async () => {
      const risposta = await page.request.patch(`/api/v1/recipes/${id}`, { data: { archived: true } });
      expect.soft(risposta.ok(), `pulizia: la ricetta ${id} non si è eliminata`).toBe(true);
    },
  };
}

function riga(page: Page, nome: string) {
  return page.getByRole("listitem").filter({ hasText: nome });
}

// stringhe e non funzioni: questo file lo compila tsconfig.node.json, senza la libreria DOM
async function nonScorreDiLato(page: Page, schermata: string) {
  await page.waitForLoadState("networkidle");
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
  expect(scrollWidth, `${schermata} scorre di lato`).toBeLessThanOrEqual(clientWidth);
}

test("da una dose le altre seguono, lo stepper dice le porzioni che fa, e la cottura registra la dose", async ({
  page,
}) => {
  await entra(page);
  const r = await ricetta(page, 2);
  try {
    await page.goto(`/ricette/${r.id}`);
    const dose = page.getByRole("button", { name: "160 g: riscala da farro" });
    await expect(dose).toBeVisible();
    expect((await dose.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    // «q.b.» non è una dose da cui partire: resta testo
    await expect(riga(page, "sale").getByRole("button")).toHaveCount(0);

    await dose.click();
    const campo = page.getByRole("textbox", { name: "Quanto ne fai?" });
    await expect(campo).toBeFocused();
    await expect(campo).toHaveAccessibleDescription("g");
    const riscala = page.getByRole("button", { name: "Riscala", exact: true });
    await expect(riscala).toHaveAttribute("aria-disabled", "true");
    await expect(riscala).toHaveAccessibleDescription("Scrivi quanto ne fai.");

    // oltre 50 volte: la frase del server sotto il campo, la ricetta com'era
    await campo.fill("10000");
    await riscala.click();
    await expect(page.getByRole("alert").filter({ hasText: "50 volte" })).toHaveText(
      "Così la ricetta cambierebbe più di 50 volte: scrivi un numero fra 3,2 g e 8000 g."
    );
    await expect(riga(page, "farro")).toContainText("160 g");
    await expect(campo).toBeVisible();
    await nonScorreDiLato(page, "il dettaglio col campo aperto e il rifiuto");

    await campo.fill("120");
    await riscala.click();
    await expect(page.getByText("≈ 1,5", { exact: true })).toBeVisible();
    await expect(riga(page, "farro").getByRole("button")).toHaveText("120 g");
    await expect(riga(page, "porro").getByRole("button")).toHaveText("0,75");
    await expect(riga(page, "sale")).toContainText("q.b.");
    await expect(page.getByText("1 dose su 3 non si riscala: resta com'è.")).toBeVisible();
    await expect(page.getByText("Riscalata da farro: 120 g.")).toBeVisible();
    await expect(campo).toHaveCount(0);
    await expect(page.getByRole("button", { name: "120 g: riscala da farro" })).toBeFocused();

    // la cottura manda la dose, non le porzioni
    await page.getByRole("button", { name: "Cucina", exact: true }).click();
    const cottura = page.waitForRequest(
      (richiesta) =>
        richiesta.method() === "POST" && richiesta.url().endsWith(`/api/v1/recipes/${r.id}/cook`)
    );
    await page.getByRole("button", { name: "Ho cucinato", exact: true }).click();
    const corpo = (await cottura).postDataJSON() as Record<string, unknown>;
    expect(corpo.anchor).toBe(r.farro);
    expect(corpo.amount).toBe("120");
    expect("servings" in corpo).toBe(false);
    await expect(page.getByRole("status").filter({ hasText: /^Segnato\./ })).toBeVisible();

    // + torna alle porzioni intere: da ≈ 1,5 a 2, cioè la ricetta com'è
    await page.getByRole("button", { name: "Una porzione in più" }).click();
    await expect(riga(page, "farro").getByRole("button")).toHaveText("160 g");
    await expect(page.getByText(/^Riscalata da/)).toHaveCount(0);
  } finally {
    await r.elimina();
  }
});

test("senza porzioni si riscala lo stesso, lo stepper resta fermo, e si torna alle dosi della ricetta", async ({
  page,
}) => {
  await entra(page);
  const r = await ricetta(page, null);
  try {
    await page.goto(`/ricette/${r.id}`);
    await page.getByRole("button", { name: "160 g: riscala da farro" }).click();
    const campo = page.getByRole("textbox", { name: "Quanto ne fai?" });
    await campo.fill("80");
    // l'Invio basta, come al telefono il tasto «fatto» della tastiera
    await campo.press("Enter");

    await expect(riga(page, "farro").getByRole("button")).toHaveText("80 g");
    await expect(riga(page, "porro").getByRole("button")).toHaveText("0,5");
    const piu = page.getByRole("button", { name: "Una porzione in più" });
    await expect(piu).toHaveAttribute("aria-disabled", "true");
    await expect(piu).toHaveAccessibleDescription("Porzioni non indicate: si cambiano da «Modifica».");
    await expect(page.getByText("—", { exact: true })).toBeVisible();

    const torna = page.getByRole("button", { name: "Torna alle dosi della ricetta" });
    expect((await torna.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await torna.click();
    await expect(riga(page, "farro").getByRole("button")).toHaveText("160 g");
    await expect(riga(page, "porro").getByRole("button")).toHaveText("1");
    await expect(torna).toHaveCount(0);
  } finally {
    await r.elimina();
  }
});
```

- [ ] **Step 2: Il contrasto**

In fondo a `frontend/e2e/style.spec.ts` aggiungi:

```ts
test("il campo «Quanto ne fai?» e la dose fissata si leggono nei due temi, coi bersagli da pollice (R2)", async ({
  page,
}) => {
  // jsdom non calcola il CSS: la sottolineatura, i 44 px senza alzare la riga e il
  // contrasto del campo dentro la scheda si vedono solo qui. La vista riscalata non scrive
  // niente: la ricetta del seme basta, ed è letta e basta.
  await page.setViewportSize({ width: 375, height: 812 });
  await page.getByRole("link", { name: "Ricette", exact: true }).click();
  await page.getByRole("link", { name: /Pasta al pomodoro/ }).first().click();

  const dose = page.getByRole("button", { name: "180 g: riscala da pasta" });
  expect((await dose.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  await expect(dose).toHaveCSS("text-decoration-style", "dotted");
  await dose.click();
  const campo = page.getByRole("textbox", { name: "Quanto ne fai?" });
  await expect(campo).toBeFocused();
  for (const [nome, bersaglio] of [
    ["la casella", campo],
    ["Riscala", page.getByRole("button", { name: "Riscala", exact: true })],
    ["Annulla", page.getByRole("button", { name: "Annulla", exact: true })],
  ] as const) {
    expect((await bersaglio.boundingBox())!.height, nome).toBeGreaterThanOrEqual(44);
  }
  for (const tema of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: tema });
    await fermo(page);
    expect(await testiIlleggibili(page), `il campo aperto, tema ${tema}`).toEqual([]);
  }
  await page.emulateMedia({ colorScheme: "light" });
  await senzaScorrimentoLaterale(page, "il dettaglio col campo «Quanto ne fai?» aperto");

  // «Pasta al pomodoro» del seme è per 2, con 180 g di pasta: 135 g sono «≈ 1,5»
  await campo.fill("135");
  await page.getByRole("button", { name: "Riscala", exact: true }).click();
  await expect(page.getByText("≈ 1,5", { exact: true })).toBeVisible();
  const torna = page.getByRole("button", { name: "Torna alle dosi della ricetta" });
  expect((await torna.boundingBox())!.height).toBeGreaterThanOrEqual(44);
  for (const tema of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: tema });
    await fermo(page);
    expect(await testiIlleggibili(page), `la dose fissata, tema ${tema}`).toEqual([]);
  }
  await page.emulateMedia({ colorScheme: "light" });
  await senzaScorrimentoLaterale(page, "il dettaglio riscalato da una dose");

  await torna.click();
  await expect(page.getByRole("button", { name: "180 g: riscala da pasta" })).toBeVisible();
});
```

Se sul ramo una delle tre funzioni (`fermo`, `testiIlleggibili`, `senzaScorrimentoLaterale`) ha un altro nome o un'altra firma, usa quella che c'è e scrivilo nel report; non duplicarla.

- [ ] **Step 3: Il type check delle prove**

Run (da `<worktree>/frontend`): `npm run typecheck`
Expected: pulito (le prove le compila `tsconfig.node.json`).

- [ ] **Step 4: L'e2e intera**

Con i comandi delle Global Constraints, dalla radice di `<worktree>`, su uno stack ricreato da zero (`down -v` prima dell'`up`, se ne era rimasto uno di questo ramo).
Expected: tutte verdi, le tre nuove comprese. **Annota il numero** delle prove passate: è `N_e2e` del Task 9. Poi `down -v` e `rm .env`, sempre.

Se una prova nuova fallisce: guarda prima se il seme ha davvero «farro», «porro», «sale» (`/api/v1/ingredients/search`) e «Pasta al pomodoro» per 2 con «180 g» di pasta; se l'unità «g» nello stack si legge diversa (le forme non le decide nessun AI, lì: si mostra la chiave, «g»), adegua solo l'attesa del testo e scrivilo nel report. Se fallisce `testiIlleggibili`, scrivi nel report quale testo e con che rapporto: **nessun token nuovo**; se il colpevole è la dose `ghost` o il campo, il task si ferma `bloccato` con la misura.

- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/riporziona.spec.ts frontend/e2e/style.spec.ts
git commit -m "R2: nel browser vero, la dose che si tocca, il rifiuto oltre le 50 volte, la cottura con l'ancora, il contrasto nei due temi"
```

---

### Task 8: I documenti

**Files:**
- Modify: `docs/prossimi-passi.md` (voce «## R2. Riporziona»)
- Modify: `next-steps.md`

Leggi i due file com'è sul ramo prima di cambiarli.

- [ ] **Step 1: `docs/prossimi-passi.md`**

1. Il titolo `## R2. Riporziona **[FATTO IN PARTE 2026-09-20: la metà per porzioni]** ↳ D1` diventa:
   ```markdown
   ## R2. Riporziona **[FATTO <data di oggi> — il secondo modo sul ramo `night/r2-riporziona-ingrediente`, non ancora in produzione; la metà per porzioni dal 2026-09-20]** ↳ D1
   ```
2. In fondo alla voce (dopo il paragrafo che comincia con «**Resta il secondo modo**»), aggiungi:
   ```markdown
   **Il TBD è deciso** (Mattia, 2026-10-09): **solo vista**, come lo stepper; si parte da un
   tocco sulla dose della riga; un modo alla volta, e con un ingrediente fissato lo stepper
   dice le porzioni equivalenti. Spec: `docs/superpowers/specs/2026-10-09-r2-riporziona-ingrediente-design.md`.

   **Il secondo modo è fatto il <data di oggi>**, sul ramo `night/r2-riporziona-ingrediente`
   (da revisionare): `GET /api/v1/recipes/{id}?anchor=<ingrediente>&amount=<dose>` riscala
   dalla dose scritta (la riga d'ancora la dice com'è scritta, le altre seguono, quelle senza
   dose strutturata si contano come nel primo modo); oltre 50 volte la ricetta, in su o in giù,
   un 422 dice fra quali dosi stare; un'ancora che la ricetta non ha più si ignora. Il calcolo è
   in `resolve_anchor` (`backend/app/services/rescale.py`), lo stesso per il dettaglio e per la
   cottura. A video la dose riscalabile è sottolineata a puntini e si tocca; sotto la riga
   «Quanto ne fai?», con l'unità accanto; lo stepper dice «≈ 1,5» e − / + tornano alle porzioni
   intere; «Riscalata da pasta: 150 g.» con «Torna alle dosi della ricetta», l'unica uscita sulle
   ricette senza porzioni. La cottura manda la dose e non le porzioni: `cooking_events.servings`
   resta null, e lo `snapshot` guadagna `anchor` (ingrediente, dose, unità, fattore, porzioni
   equivalenti), senza migrazione.

   **L'etichetta** è «Quanto ne fai?» con l'unità accanto alla casella, non «Quanti g ne
   fai?» (deciso da Mattia il 2026-10-13): il registro delle unità non sa il genere, e con
   «fette», «scatole», «coste» la domanda letterale sbaglia l'accordo.

   **Da provare sul telefono:** la tastiera dei numeri che si apre da sola col tocco sulla
   dose, la virgola della tastiera italiana, il tocco sulla dose sottolineata col pollice senza
   prendere la riga accanto, l'Invio («fatto») che riscala.
   ```
   Sostituisci `<data di oggi>` con la data vera.

- [ ] **Step 2: `next-steps.md`**

1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte)_`.
2. Togli la riga della voce (`grep -n "R2, secondo modo" next-steps.md`: `in corso` dalla Preparazione, dovunque sia — «Pronti per la notte» o «Da approfondire»). Se in «Pronti per la notte» era una voce numerata, lascia com'è la numerazione delle altre.
3. In cima a «Fatti (recenti)» aggiungi:
   ```markdown
   - [fatto] <data di oggi> · R2, secondo modo: si riscala dalla dose di un ingrediente toccando la dose («Quanto ne fai?»), lo stepper dice «≈ 1,5» e − / + tornano alle porzioni intere, «Torna alle dosi della ricetta»; oltre 50 volte un 422 con la frase; la cottura registra la dose nello `snapshot`, senza migrazione [R2] → branch night/r2-riporziona-ingrediente (da revisionare)
   ```
4. In cima a «Da fare a mano (solo Mattia)» aggiungi:
   ```markdown
   - [tbd] P2 · Prove sul telefono di R2, secondo modo: la tastiera dei numeri che si apre da sola dopo il tocco sulla dose, la virgola, il tocco sulla dose sottolineata col pollice, il tasto «fatto» che riscala. Nel browser passati il rifiuto oltre le 50 volte, «≈ 1,5» con − / +, la ricetta senza porzioni con «Torna alle dosi della ricetta», la cottura che manda la dose, il contrasto nei due temi
   ```
5. In «Idee» aggiungi:
   ```markdown
   - [idea] P3 · R2 riscala nell'unità della riga: «ne faccio 1 kg» su una riga in grammi va scritto 1000. Una conversione fra g/kg e ml/l sarebbe semplice, le altre sono di S4 [R2]
   ```
6. Se nella notte sono emerse altre cose da fare fuori da questo piano, aggiungile come `idea` o `tbd` nella sezione giusta, con la voce di `docs/prossimi-passi.md` fra parentesi quadre.

- [ ] **Step 3: Commit**

```bash
git add docs/prossimi-passi.md next-steps.md
git commit -m "docs: R2, il secondo modo fatto sul ramo"
```

---

### Task 9: La verifica finale e il report

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

Expected: vitest tutto verde — **`N_vitest` della Preparazione più 42**, cioè 5 (Task 4) + 27 (Task 5: 3 dello stepper, 16 di `readAmount`, 8 del campo) + 10 (Task 6), in **`N_file` + 2** file (`anchorAmount.test.ts`, `AnchorField.test.tsx`); se il numero differisce, scrivi nel report da dove viene la differenza. Typecheck, lint e build puliti. `npx tsc -b --force` perché `node_modules` è condiviso col checkout principale, e con lui il `tsbuildinfo`: `--force` compila davvero tutto.

- [ ] **Step 2: Il backend**

Da `<worktree>/backend` (con `TEST_DATABASE_URL` davanti se la Preparazione ha scelto `spena_test_r2`):

```bash
PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Expected: tutto verde, **`N_pytest` + 50** (22 del dominio, 19 del dettaglio, 9 della cottura).

- [ ] **Step 3: I grep**

Dalla radice del worktree:

```bash
grep -rn "emerald\|neutral-" frontend/src
git diff master --stat -- backend/alembic
grep -rn "Quanti g ne fai" frontend/src frontend/e2e
grep -rn "UnitForms(" backend/app/api/recipes.py
```

Expected: tutti vuoti (nessun colore crudo, nessuna migrazione, l'etichetta letterale non è a video, le forme delle unità passano solo da `unit_forms`).

- [ ] **Step 4: L'e2e intera**

Con i comandi delle Global Constraints, su uno stack ricreato da zero. Expected: tutte verdi, `N_e2e` del Task 7. Poi `down -v` e `rm .env`, sempre. Se la Preparazione ha creato `spena_test_r2`: `docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_r2 WITH (FORCE)'`.

- [ ] **Step 5: Il report**

Nel report della notte, `docs/night-reports/<data di oggi>.md` sul ramo: se il file c'è già sul ramo aggiungi una sezione in fondo, altrimenti crealo con un titolo `# Notte del <data di oggi>` (gli altri piani della notte scrivono lo stesso file sui loro rami: l'unione la fa la revisione). Per questo piano: il ramo e da dove parte (`master`); i conti veri (vitest, pytest, e2e) contro quelli della Preparazione; quale database dei test ha usato; le migrazioni di test fatte oltre ai campi nuovi delle voci finte (dovrebbero essere zero); le scelte del piano che Mattia può voler rivedere: il limite delle 50 volte, «Torna alle dosi della ricetta» anche sulle ricette con porzioni, il campo che riscala al tocco di «Riscala» e non a ogni cifra, la dose sottolineata a puntini, `servings` null e la dose nello `snapshot` per la cottura; e i file che al merge incontrano altri rami della notte (`cooking.py`, `api/cooking.py`, `CookSheet.tsx` col piano 7; i test della cottura e del dettaglio, `types.ts` con S12 e S14; `style.spec.ts` con tutti). Niente push, niente merge, niente deploy.

```bash
git add docs/night-reports/
git commit -m "report: R2 secondo modo, la notte"
```
