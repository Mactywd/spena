# R5, «Sostituisci» un ingrediente: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** dentro la ricetta, accanto a ogni ingrediente, «Sostituisci» apre sotto la riga cosa usare al suo posto — uno o più sostituti, «si può omettere» o «insostituibile» —, da una risposta precalcolata per ingrediente × {dolce, salato}, decisa dall'AI e salvata, correggibile per la singola ricetta («Non va bene qui») e rivista in Anagrafica; il comando `python -m app.cli.decide_substitutes` la calcola per tutto il ricettario.

**Architecture:** il dominio (`backend/app/domain/substitutions.py`) ha i tre vocabolari, i limiti e `recipe_context` (dolce se la categoria comincia con la parola «dolci»). La migrazione `0015` aggiunge `ingredient_substitutions` (la voce generale con `recipe_id` NULL, la correzione di una ricetta con `context` NULL, due indici unici parziali) e `substitution_options` (i sostituti). Il repository (`backend/app/repositories/substitutions.py`) legge, scrive, controlla una risposta scritta a mano, trova le voci scoperte e sposta tutto in una fusione (chiamato da `merge_ingredients`). Il servizio dell'AI (`backend/app/services/substitutions.py`) chiede una voce per chiamata con l'anagrafica alimentare nel prompt e verifica la risposta; lo usano il comando e la rotta `POST …/ask`. Le rotte stanno in `backend/app/api/substitutions.py`. Nel frontend una cartella nuova, `frontend/src/features/substitutes/` (tipi, chiamate, parole, la risposta da leggere, il modulo, il pannello della ricetta, la sezione dell'Anagrafica), montata in `IngredientRow` del dettaglio e in fondo alla scheda dell'ingrediente.

**Tech Stack:** FastAPI, Pydantic 2, SQLAlchemy 2 async, Alembic, pytest su Postgres vero; React 19, TypeScript, Tailwind 4 (token in `@theme`), TanStack Query 5, react-router 7, Vitest + Testing Library (jsdom), Playwright.

**Spec:** `docs/superpowers/specs/2026-10-13-r5-sostituti-design.md` (scritta con questo piano: le decisioni di Mattia del 2026-10-13 al §2, quelle di Claude su delega al §3, le parole a video al §5, la regola per R6 al §8, la domanda aperta al §10). Il ragionamento d'archivio è in `docs/prossimi-passi.md`, voci «## R5. Sostituisci ingrediente», «## R6» e «## M1». La riga di `next-steps.md` che questo piano chiude comincia con «R5, sostituisci ingrediente».

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/r5-sostituti` (`.worktrees/` è già in `.gitignore`), ramo `night/r5-sostituti`, creato da **`master`**: questo piano è il sedicesimo della notte ma non dipende dalla catena, e nessuno dei suoi file aspetta il lavoro degli altri. Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì (o dalle sue `backend/` e `frontend/`), mai dalla radice del checkout principale. Il checkout principale non si tocca: se vi trovi modifiche non committate, sono dell'utente. **Nessun push, nessun merge, nessun deploy. Mai `git stash`. Niente letture o scritture sulla produzione**: il comando che fa decidere i sostituti all'AI si costruisce e si prova qui, e lo lancia Mattia («Dopo il deploy (solo Mattia)»).
- **I file che anche altri piani della notte toccano** — `backend/app/services/llm.py` (S12 aggiunge `INGREDIENT_EMOJI`, R8 `RECIPE_VARIANT` a `LlmCallSite`), `backend/app/main.py` (H1 aggiunge un router), `backend/app/services/registry.py` (S12 una funzione nuova; la pulizia delle dosi cambia il ciclo delle righe gemelle in `merge_ingredients`), `frontend/src/features/cooking/RecipeDetailScreen.tsx` e il suo test (R2 riscrive `IngredientRow`; la pulizia delle dosi aggiunge la nota nel nome; R8, «rimetti in lista», le pulizie dei controlli lo toccano), `frontend/src/features/registry/IngredientScreen.tsx` e il suo test (S12, pulizie dei controlli), `frontend/src/components/ui/icons.ts` (S3, S12, S15, pulizie dei controlli), `frontend/e2e/style.spec.ts` (quasi tutti), `README.md` (S12), `next-steps.md`, `docs/prossimi-passi.md`, il report della notte. Sul tuo ramo, che parte da `master`, sono come su `master`. Il piano descrive comunque ogni modifica a un file esistente contro un'ancora riconoscibile — una funzione, una riga di codice esatta, un elemento JSX, un testo esatto — e mai contro numeri di riga: **leggi il file com'è sul ramo prima di cambiarlo**, e aggiungi in blocchi tuoi senza toccare le righe vicine. Dove il piano dà un file intero è un file nuovo. Le prove nuove di `style.spec.ts` vanno **in fondo al file**.
- **Le due decisioni fondanti** (`CLAUDE.md`): la dispensa non impara niente (nessuna colonna sua cambia); le ricette puntano solo a ingredienti, e un sostituto è un ingrediente **alimentare** dell'anagrafica, mai un prodotto.
- **Mai un vicolo cieco.** L'AI che non risponde (o senza chiave) lascia «Nessun suggerimento ancora.» con «Riprova» e «Scrivi tu»; una risposta dell'AI che non si verifica non si applica, e la voce resta da chiedere; un rifiuto del server su una risposta scritta a mano si legge com'è, e il modulo resta aperto; il comando senza l'AI non scrive niente e dice quante voci restano.
- **Il frontend non calcola logica di dominio.** Il contesto della ricetta, quale risposta vale per una riga, se un sostituto in dispensa basta (`satisfied`), la verifica di una risposta: tutto nel backend. Nel frontend restano le parole e il flusso (leggere, e se non c'è una risposta chiederla).
- Tutto il colore passa dai token di `frontend/src/index.css`. **Nessun token nuovo.** Nessuna schermata nomina un colore crudo: `grep -rn "emerald\|neutral-" frontend/src` resta vuoto. Ogni testo sta sopra 4,5:1, in chiaro e in scuro, e lo misura `frontend/e2e/style.spec.ts`. Niente classi in conflitto sullo stesso elemento (due `text-*` o due `px-*`).
- **`Button`** (`frontend/src/components/ui/Button.tsx`) non cambia. **La regola (di Mattia):** in volo → `busy`; «non ancora» → `unavailableReason` (il perché sotto, `aria-disabled`, il fuoco resta); `disabled` nativo solo dove nessuno dei due vale. Ogni pulsante nuovo di questo piano è un `Button`. Ogni bersaglio nuovo è almeno 44×44 px. A 375 px nessuna schermata scorre di lato.
- Le icone si importano solo da `frontend/src/components/ui/icons.ts` (questo piano ne aggiunge una: `IconArrowsExchange`, già nel pacchetto `@tabler/icons-react` installato).
- Le parole a video sono in italiano e **si copiano esattamente come sono scritte qui**; gli identificatori in inglese; i commenti in italiano come nel resto del codice. Il nome di un ingrediente dentro una frase o un nome accessibile resta minuscolo; a inizio riga prende la maiuscola solo a video (`capitalizeFirst`).
- **Il type check è `npm run typecheck`** (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0 (settima lezione di `CLAUDE.md`).
- Controlli del frontend, da `<worktree>/frontend`: `npx vitest run` (non esiste `npm test`), `npm run typecheck`, `npm run lint`, `npm run build`.
- **Backend su Postgres vero, in un database suo.** Il server dei test è il container `spena-db-1` (porta 5433): se `docker ps --format '{{.Names}}'` non lo mostra, `docker start spena-db-1`. **Mai `docker compose up` dal worktree**, mai `-f docker-compose.prod.yml`. Questo ramo aggiunge la migrazione **`0015`** (numero riservato dalla fase giorno, `down_revision = "0012"`), e la suite fa `alembic upgrade head` sul suo database all'avvio: girata su `spena_test` lo lascerebbe alla `0015`, e i piani che partono da `master` troverebbero `alembic upgrade head` rotto. Per questo **ogni pytest di questo piano gira su `spena_test_r5`**, creato nella Preparazione e tolto alla fine. Nel worktree non c'è un `.venv`: si usa quello del checkout principale; `python -m` mette la cartella corrente in testa a `sys.path`, quindi si prova l'`app` del worktree. Il comando, sempre da `<worktree>/backend` (dove un task dice «il comando di pytest» intende questo, con i percorsi che il task indica in coda):
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_r5 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
  Se un test sembra ignorare una modifica, `python -c 'import app; print(app.__file__)'` da `<worktree>/backend` (con lo stesso `PATH`) deve stampare un percorso dentro il worktree. **Nessuna chiamata di rete nella suite**: l'LLM risponde dai finti (`backend/tests/llm_fakes.py` e quello del Task 6).
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
- **Nessuna dipendenza nuova.** Una migrazione sola, la `0015`. Nessun cambio di configurazione globale.

## Review Focus

I casi che la spec implica e che nessun test di un task coprirebbe da solo, i cinque più probabili a dare fastidio a chi usa l'app; ognuno ha la sua prova nel task che possiede il codice.

1. **Una ricetta che cambia categoria** (da «Secondi piatti» a «Dolci» con «Modifica») deve mostrare la voce dolce dell'ingrediente, o chiederla, mai quella salata di prima → Task 8, `test_una_ricetta_che_diventa_dolce_legge_la_voce_dolce`.
2. **L'unico sostituto cancellato** (l'annullamento di una decisione della coda cancella l'ingrediente che l'AI aveva proposto): il pannello deve dire «Nessun suggerimento ancora» e «Riprova» deve poter richiedere la voce, non restare incastrato su una risposta vuota → Task 3, `test_un_sostituto_cancellato_lascia_la_voce_senza_risposta`, e Task 8, `test_ask_richiede_una_voce_rimasta_senza_sostituti`.
3. **Una correzione a mano fatta mentre il comando gira** (Mattia corregge in Anagrafica durante il lancio) non si riscrive → Task 6, `test_una_correzione_a_mano_fatta_mentre_l_ai_risponde_non_si_riscrive`.
4. **Nomi dell'AI con maiuscole e spazi** («Tacchino ») sono gli stessi nomi; lo stesso nome due volte con la maiuscola diversa è un doppione → Task 6, `test_maiuscole_e_spazi_non_contano_ma_un_doppione_si`.
5. **Una ricetta senza categoria** (scritta a mano, o del seme) è salata, e il suo pannello funziona come le altre → Task 1 (tabella di `recipe_context`) e Task 8, `test_senza_risposta_la_riga_lo_dice` (ricetta senza categoria, contesto «salato»).

### Preparazione (una volta, prima del Task 1)

- [ ] Il ramo di partenza è `master`, i file di questo piano sono quelli su cui è scritto (`master` era `b9be6bf` quando il piano è stato scritto), e la migrazione `0015` non c'è ancora:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify master
  git diff --stat b9be6bf master -- \
    backend/app/services/llm.py backend/app/services/registry.py backend/app/main.py \
    backend/app/db/models/__init__.py backend/app/repositories/pantry.py \
    frontend/src/features/cooking/RecipeDetailScreen.tsx frontend/src/features/registry/IngredientScreen.tsx \
    frontend/src/components/ui/icons.ts frontend/src/components/IngredientPicker.tsx
  git ls-tree --name-only master backend/alembic/versions/ | sort | tail -n 1
  ls backend/app/domain/substitutions.py backend/app/services/substitutions.py \
    backend/app/cli/decide_substitutes.py frontend/src/features/substitutes 2>&1 | grep -c "No such file"
  ```
  Expected: un hash; il `diff --stat` **vuoto**; `backend/alembic/versions/0012_modifica_ricette.py`; `4`. Se il `diff` non è vuoto, `master` è andato avanti su questi file: applica le modifiche del piano sopra la versione di `master`, ancora per ancora, e scrivilo nel report. Se l'ultima migrazione di `master` non è la `0012`, la `0015` resta comunque `down_revision = "0012"` stanotte (la ripunta Mattia al merge): scrivilo nel report. Se uno dei file nuovi esiste già, **fermati**: qualcuno ha già cominciato questa voce; scrivi nel report della notte (`docs/night-reports/<data>.md`, sul ramo `night/r5-sostituti` appena creato) cosa hai trovato, segna la voce `bloccato` in `next-steps.md` di quel ramo con la domanda per Mattia, e non partire.
- [ ] Il database dei test di questo ramo:
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_r5 WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_r5'
  ```
  (alla fine del Task 15 si toglie).
- [ ] Dal checkout principale, allinea `node_modules` al lockfile (non aggiunge dipendenze, installa quelle di `package-lock.json`):
  ```bash
  cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund
  ```
- [ ] Crea il worktree da `master` e collega `node_modules` (e solo quello: **niente `.env`**):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/r5-sostituti -b night/r5-sostituti master
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/r5-sostituti/frontend/node_modules
  ```
- [ ] La voce in `next-steps.md` del ramo passa a `in corso` (cercala per testo, `grep -n "R5, sostituisci" next-steps.md`: di giorno può essere stata spostata in «Pronti per la notte»; cambia solo lo stato fra parentesi quadre) e si committa:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/r5-sostituti
  git add next-steps.md
  git commit -m "next-steps: R5 sostituti, in corso"
  ```
- [ ] La linea di partenza, dal worktree:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/r5-sostituti/frontend && npx vitest run 2>&1 | grep -E "Test Files|Tests "
  cd ../backend && TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_r5 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q 2>&1 | tail -n 1
  ```
  Expected: tutto verde. **Annota i numeri** (file e test di vitest, test di pytest): sono `N_file`, `N_vitest`, `N_pytest` del Task 15. Se una delle due linee non è verde, fermati: non è un difetto di questo piano, e va scritto nel report.

---

## Obiettivo e contesto

Oggi il dettaglio di una ricetta dice cosa manca, e basta. R5 dice cosa usare al suo posto. La voce era ferma su un TBD pesante — quante coppie, quanto costano, se dipende dalla ricetta, come si corregge — e Mattia l'ha sciolto il 2026-10-13: una risposta per ingrediente e per contesto (dolce o salato), decisa dall'AI una volta e salvata, che si vede subito ed è segnata come sua; la correzione della singola ricetta; la revisione in Anagrafica; e il dato pronto per R6, che dirà «cucinabile con sostituti». Il costo stimato per tutto il ricettario è mezzo dollaro (spec §6).

## Decisioni prese

Di Mattia, il 2026-10-13 (spec §2):

1. **Granularità: ingrediente × {dolce, salato}**, la doppia voce solo dove serve, più la **correzione a mano per singola ricetta**.
2. **Un sostituto è solo un ingrediente alimentare dell'anagrafica**, con una nota breve facoltativa. Una risposta dell'AI che nomina qualcosa fuori anagrafica, non alimentare, l'ingrediente stesso o un doppione **si scarta**.
3. **«Si può omettere» soddisfa qualunque riga** ai fini di R6. R6 non si costruisce qui; il dato lo permette e la regola è scritta (spec §8).
4. **Le risposte dell'AI si vedono subito**, segnate col loro `decided_by`, e si rivedono in Anagrafica, nella scheda dell'ingrediente («Sostituti»). **Una correzione umana non si sovrascrive mai.**
5. Il calcolo è un comando sul modello di `decide_emoji` (S12): a lotti, commit per lotto, solo le voci scoperte, `--limit` / `--dry-run`, una `LlmCallSite` nuova. Una voce scoperta si calcola anche sul momento, toccando «Sostituisci». La fusione sposta i sostituti sul vincitore. Il lancio vero è di Mattia, prima con `--limit 20`.

Di Claude, su delega di Mattia (tecniche o estetiche; il perché è nella spec, §3):

6. **Il contesto**: dolce se la prima parola della categoria della ricetta è «dolci», salata in ogni altro caso (`recipe_context`).
7. **Una voce** = un ingrediente in un contesto in cui lo usa almeno una ricetta non eliminata.
8. **I dati**: `ingredient_substitutions` (voce generale o correzione di ricetta, `verdict`, `decided_by`) e `substitution_options` (sostituto, nota fino a 60 caratteri, posizione), migrazione `0015`, chiavi in `CASCADE`, due indici unici parziali.
9. **Una risposta «sostituti» senza sostituti visibili vale come nessuna** (`is_answered`).
10. **Da 1 a 3 sostituti**; **una chiamata per voce** con l'anagrafica alimentare nel prompt; **un solo difetto scarta la risposta intera**; l'AI scrive solo dove non c'è una risposta, con `ON CONFLICT DO NOTHING`.
11. **Il comando** `python -m app.cli.decide_substitutes`, sezione `LlmCallSite.INGREDIENT_SUBSTITUTES = "ingredient_substitutes"`, lotti da 20 in parallelo sotto `LLM_MAX_CONCURRENCY`, dalle voci più usate; si ferma al primo lotto con un guasto.
12. **Dalla ricetta si scrive solo la correzione della ricetta; da Anagrafica solo la voce generale** («Va bene così» la conferma come scelta a mano).
13. **A video**: un pulsante di sola icona (`IconArrowsExchange`, «Sostituisci {nome}») in fondo a ogni riga, il pannello sotto la riga, il pallino della dispensa e «ce l'hai» / «non basta» accanto a ogni sostituto; in Anagrafica una scheda per contesto, la voce dell'AI segnata in ambra («Deciso dall'AI: da rivedere.»).
14. **La fusione**: dove il perdente è un sostituto va il vincitore, mai due volte e mai come sostituto di sé stesso; fra due voci generali vince quella con una risposta, poi la scritta a mano, poi quella del vincitore; le correzioni seguono la riga; le risposte rimaste vuote si tolgono.
15. **I tipi del frontend stanno in `features/substitutes/types.ts`**, non in `domain/types.ts` (che stanotte cambiano S12, S14, S15, R2): li usa solo questa cartella e chi la monta. I due limiti copiati lì (`SUBSTITUTES_MAX`, `SUBSTITUTE_NOTE_MAX`) servono a non offrire il quarto selettore e a tagliare la nota; un test del backend li confronta col dominio.

16. **Una correzione di ricetta su una ricetta importata si perde se l'import la rifà da capo** (annullamento o fusione di un suo termine): deciso da Mattia il 2026-10-13 (spec §10, opzione (a)). Nessun codice in `undo.py` né in `materialize.py`; in `next-steps.md` va un'`idea` per farla viaggiare nel `payload` come le cotture (opzione (c)).

## Criteri di accettazione

- [ ] `alembic upgrade head` crea le due tabelle con i vincoli e i tre indici; la `0015` scende e risale; l'autogenerate non propone niente (`test_metadata_matches_migrations.py`).
- [ ] `recipe_context`: «Dolci e Desserts», «Dolci», « dolci » → dolce; «Primi piatti», «Lievitati», «Dolcificanti», «», `None` → salato.
- [ ] Una risposta scritta a mano si rifiuta con le frasi della spec §4 (nessun sostituto, sostituti con un esito che non li vuole, più di tre, un id che non c'è, l'ingrediente stesso, un non alimentare, un doppione, una nota oltre 60 caratteri); le note si puliscono degli spazi, e vuote diventano nulle.
- [ ] La correzione della ricetta vince sulla voce generale; tolta, torna la generale; una risposta senza sostituti visibili vale come nessuna.
- [ ] L'AI scrive solo dove non c'è una risposta, anche se la correzione arriva mentre il modello risponde.
- [ ] Le voci scoperte sono una per ingrediente e contesto in cui compare in una ricetta non eliminata, dalla più usata.
- [ ] `merge_ingredients` sposta voci, sostituti e correzioni sul vincitore con le regole della decisione 14; l'anteprima non sposta niente.
- [ ] Il servizio applica solo risposte verificate (esito, nomi canonici alimentari, non sé stesso, niente doppioni, da 1 a 3, note fino a 60), registra ogni chiamata in `llm_calls` come `ingredient_substitutes` (anche quelle fallite), va a lotti con un `after_batch`, si ferma al primo lotto con un guasto, senza chiave non chiama e non registra niente.
- [ ] `python -m app.cli.decide_substitutes` con `--limit N` e `--dry-run`; un argomento sbagliato esce 2; l'ultima riga dice quante voci restano.
- [ ] Le sei rotte della spec §4 rispondono come scritto; `POST …/ask` non risponde mai 503 (`ai_failed`).
- [ ] Nel dettaglio ogni riga ha «Sostituisci {nome}» (44×44, `aria-expanded`); il pannello dice la risposta con la sua provenienza, chiede all'AI se non c'è, lascia «Riprova» e «Scrivi tu» se non arriva; «Non va bene qui» salva una correzione per questa ricetta, «Torna al suggerimento generale» la toglie.
- [ ] In Anagrafica la sezione «Sostituti» di un ingrediente alimentare ha una scheda per contesto, «Deciso dall'AI: da rivedere.» con «Va bene così» e «Correggi», «Scrivi tu» dove non c'è risposta, «Corretto a mano in N ricette.»; un non alimentare non ha la sezione.
- [ ] Tutti i test di oggi passano, cambiati solo dove il piano lo dice (la risposta dei sostituti in `base()` di `IngredientScreen.test.tsx`), mai indeboliti.
- [ ] vitest, typecheck, lint, build, pytest e l'e2e intera verdi; `sostituti.spec.ts` ha una prova, `style.spec.ts` una in più; il comando lanciato sullo stack e2e (senza chiave) degrada come previsto e non scrive niente.
- [ ] `README.md`, `docs/prossimi-passi.md` e `next-steps.md` aggiornati (Task 14).

## Comandi di verifica

Da `<worktree>/backend`:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_r5 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
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
git diff master --stat -- backend/alembic | tail -n 1
grep -rn "complete_json(" backend/app/services/substitutions.py | wc -l
```

Expected: il primo vuoto; il secondo `1 file changed, …` (solo la `0015`); il terzo `1` (una sola chiamata all'LLM, in `_ask`). E l'e2e intera con i comandi delle Global Constraints.

## Fuori scope

- Il filtro «cucinabili con sostituti» (R6) e il motore di suggerimento (M1): qui solo il dato e la regola scritta.
- Un elenco di tutte le voci dell'AI da rivedere fuori dalla scheda dell'ingrediente; «Chiedi all'AI» da Anagrafica; rifare con l'AI una voce già decisa.
- Sostituti fuori anagrafica, o creati dal modulo; quantità dei sostituti oltre la nota.
- Far viaggiare le correzioni di ricetta nel `payload` dell'import (spec §10, deciso da Mattia il 2026-10-13): un'`idea`.
- Tutto quel che fanno gli altri piani della notte.

## Margine di autonomia

- **Liberi:** i nomi di variabili locali, helper di test e funzioni interne non fissati qui; l'ordine dei test dentro un file; l'ordine delle classi Tailwind; la formulazione dei commenti, purché dicano il perché.
- **Fissi:** le parole a video e le frasi dei rifiuti, esattamente come sono scritte nel piano; le righe che il comando stampa; le rotte, i loro corpi e i campi delle risposte; i nomi delle tabelle, delle colonne, dei vincoli e degli indici; la revisione `0015`; i nomi pubblici che altri task usano (`SubstitutionContext`, `SubstitutionVerdict`, `DecidedBy`, `SUBSTITUTES_MAX`, `SUBSTITUTE_NOTE_MAX`, `recipe_context`, `clean_note`, `IngredientSubstitution`, `SubstitutionOption`, `Answer`, `SubstitutionRefused`, `Voice`, `ContextView`, `IngredientView`, `visible_options`, `is_answered`, `general_row`, `recipe_row`, `effective_row`, `checked_answer`, `write_general`, `write_override`, `delete_override`, `store_ai_answer`, `pending_voices`, `ingredient_view`, `move_substitutions`, `LlmCallSite.INGREDIENT_SUBSTITUTES`, `SUBSTITUTE_BATCH`, `SUBSTITUTE_MAX_TOKENS`, `AI_VERDICTS`, `SUBSTITUTE_SYSTEM_PROMPT`, `SUBSTITUTE_SCHEMA`, `Rejected`, `verify_answer`, `load_food`, `question`, `describe`, `PairOutcome`, `decide_pair`, `SubstitutionRun`, `decide_substitutions`, `measured_cost`, gli schemi Pydantic, `recipe_router`, `ingredient_router`, e nel frontend i tipi, le funzioni di `api.ts` e `wording.ts`, `SubstituteAnswer`, `SubstituteEditor`, `SubstitutePanel`, `IngredientSubstitutes` e le loro prop).
- **Nessuna dipendenza nuova**, una migrazione sola, nessun token di colore nuovo.
- **Un test di oggi si cambia solo dove il piano lo dice** — mai per indebolirlo. Se ne serve un'altra migrazione, scrivila nel report con il perché.
- **Una decisione di comportamento non coperta e non reversibile** → si ferma quel task, si fa commit del lavoro parziale sul ramo, lo si segna `bloccato` in `next-steps.md` del ramo con la domanda precisa per Mattia, e si passa al task successivo. Una scelta reversibile e a basso impatto → la più conservativa, annotata nel report della notte.
- Se un test fallisce e non si risolve in modo ragionevole: niente test disattivati, niente asserzioni indebolite; `bloccato` con la diagnosi.

## Dipendenze

**Parte da `master`.** Non consuma niente dagli altri piani della notte. Al merge incontra, sugli stessi file: S12 e R8 in `llm.py` (tre valori nuovi uno sotto l'altro in `LlmCallSite`); H1 in `main.py` (un router ciascuno) e in `CALL_SITE_LABELS` (vedi «Al merge»); S12 e la pulizia delle dosi in `registry.py` (questo piano aggiunge una riga in `merge_ingredients`, prima della cancellazione degli alias del perdente: lontano dal ciclo delle righe gemelle); R2, la pulizia delle dosi, R8, «rimetti in lista» e le pulizie dei controlli in `RecipeDetailScreen.tsx` — R2 dà a `IngredientRow` la stessa forma che le dà questo piano (un `<li>` con un `<div className="flex items-center gap-2.5">` e sotto, se aperto, un pannello): al merge il pulsante «Sostituisci» va in fondo al `<div>` della riga, dopo la dose di R2, e `SubstitutePanel` dopo `AnchorField`; S12 e le pulizie dei controlli in `IngredientScreen.tsx` (questo piano aggiunge solo in fondo); quasi tutti in `icons.ts` e `style.spec.ts`. Modifiche in punti diversi degli stessi file, che la revisione unisce.

## Al merge (solo Mattia)

1. **La migrazione.** `backend/alembic/versions/0015_sostituti.py` ha `down_revision = "0012"`: va ripuntata sulla testa di `master` di quel momento (una riga, per esempio `down_revision = "0014"` se R8 è già dentro, o `"0018"` se lo sono anche S4 e H2). Poi, da `backend/` col `.venv`:
   ```bash
   alembic heads
   ```
   deve stampare **una testa sola**. Il test `tests/db/test_migration_0015.py` scende di una revisione (`downgrade -1`), non verso un numero: regge la ripuntatura.
2. **Le spese dell'AI (H1).** Se H1 è già su `master`, in `backend/app/domain/spending.py` `CALL_SITE_LABELS` prende la riga
   ```python
       "ingredient_substitutes": "Sostituti degli ingredienti",
   ```
   altrimenti il test di H1 che vuole un nome per ogni valore di `LlmCallSite` fallisce.

## Dopo il deploy (solo Mattia)

Nessun dato si sposta da solo: le risposte nascono dal comando o da «Sostituisci». In produzione, sul server, in quest'ordine:

```bash
ssh hetznerserver "cd ~/sites/spena && docker compose -f docker-compose.prod.yml exec -T backend python -m app.cli.decide_substitutes --dry-run"
ssh hetznerserver "cd ~/sites/spena && docker compose -f docker-compose.prod.yml exec -T backend python -m app.cli.decide_substitutes --limit 20"
```

Il primo non chiama nessuno: dice quante voci sono scoperte (attese fra 900 e 1.800) e quali chiederebbe. Il secondo chiede le venti più usate (~0,01 $): **guarda le venti righe stampate** — sono le risposte, una per voce — e qualcuna in Anagrafica, e la riga «spesa di questo lancio». Poi:

```bash
ssh hetznerserver "cd ~/sites/spena && docker compose -f docker-compose.prod.yml exec -T backend python -m app.cli.decide_substitutes --dry-run"
```

che ora stima il costo del resto con la media misurata. Se la stima sta sotto 0,8 $, il resto in un lancio:

```bash
ssh hetznerserver "cd ~/sites/spena && docker compose -f docker-compose.prod.yml exec -T backend python -m app.cli.decide_substitutes"
```

altrimenti in due giorni con `--limit` (metà delle voci il primo giorno). Si rilancia finché l'ultima riga dice «nessuna voce in attesa.». Le voci scartate restano scoperte e un lancio dopo le richiede.

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `backend/app/domain/substitutions.py` (nuovo), `backend/tests/domain/test_substitutions.py` (nuovo) | 1 | i vocabolari, i limiti, `recipe_context`, `clean_note` |
| `backend/app/db/models/substitution.py` (nuovo), `backend/app/db/models/__init__.py` | 2 | i due modelli |
| `backend/alembic/versions/0015_sostituti.py` (nuovo) | 2 | la migrazione |
| `backend/tests/db/test_migration_0015.py`, `backend/tests/db/test_substitution_schema.py` (nuovi) | 2 | la migrazione, i vincoli |
| `backend/app/repositories/substitutions.py` (nuovo) | 3, 4, 5 | leggere, scrivere, controllare; le voci; la fusione |
| `backend/tests/repositories/test_substitutions.py`, `test_substitution_voices.py` (nuovi) | 3, 4 | |
| `backend/app/services/registry.py`, `backend/tests/services/test_registry_merge_substitutes.py` (nuovo) | 5 | la fusione |
| `backend/app/services/llm.py` | 6 | `LlmCallSite.INGREDIENT_SUBSTITUTES` |
| `backend/app/services/substitutions.py` (nuovo), `backend/tests/services/test_substitutions_ai.py` (nuovo) | 6 | l'AI e la verifica |
| `backend/app/cli/decide_substitutes.py` (nuovo), `backend/tests/test_decide_substitutes_cli.py` (nuovo) | 7 | il comando |
| `backend/app/schemas/substitution.py`, `backend/app/api/substitutions.py` (nuovi), `backend/app/main.py` | 8 | le rotte |
| `backend/tests/api/test_substitutions_recipe.py`, `test_substitutions_registry.py` (nuovi) | 8 | |
| `frontend/src/features/substitutes/types.ts`, `api.ts`, `api.test.ts`, `wording.ts`, `wording.test.ts` (nuovi), `backend/tests/test_frontend_substitutes.py` (nuovo) | 9 | tipi, chiamate, parole, la guardia dei limiti |
| `frontend/src/features/substitutes/SubstituteAnswer.tsx`, `SubstituteEditor.tsx`, `SubstituteEditor.test.tsx` (nuovi) | 10 | la risposta da leggere, il modulo |
| `frontend/src/features/substitutes/SubstitutePanel.tsx`, `SubstitutePanel.test.tsx` (nuovi), `frontend/src/components/ui/icons.ts`, `frontend/src/features/cooking/RecipeDetailScreen.tsx`, `.test.tsx` | 11 | il pannello nella ricetta |
| `frontend/src/features/substitutes/IngredientSubstitutes.tsx`, `IngredientSubstitutes.test.tsx` (nuovi), `frontend/src/features/registry/IngredientScreen.tsx`, `.test.tsx` | 12 | la sezione in Anagrafica |
| `frontend/e2e/sostituti.spec.ts` (nuovo), `frontend/e2e/style.spec.ts` | 13 | nel browser vero |
| `README.md`, `docs/prossimi-passi.md`, `next-steps.md` | 14 | i documenti |
| `docs/night-reports/<data>.md` | 15 | il report |

---

### Task 1: Il dominio — i vocabolari, i limiti, il contesto della ricetta

**Files:**
- Create: `backend/app/domain/substitutions.py`
- Test: `backend/tests/domain/test_substitutions.py`

**Interfaces:**
- Produces (in `app.domain.substitutions`): `class SubstitutionContext(StrEnum)` con `SAVORY = "salato"`, `SWEET = "dolce"` (in quest'ordine: è l'ordine delle schede in Anagrafica); `class SubstitutionVerdict(StrEnum)` con `SUBSTITUTES = "substitutes"`, `OMIT = "omit"`, `IRREPLACEABLE = "irreplaceable"`; `class DecidedBy(StrEnum)` con `AI = "ai"`, `HUMAN = "human"`; `SUBSTITUTES_MAX = 3`; `SUBSTITUTE_NOTE_MAX = 60`; `SWEET_CATEGORY_WORD = "dolci"`; `recipe_context(category: str | None) -> SubstitutionContext`; `clean_note(note: str | None) -> str | None`. Tutti i task dopo li usano.

- [ ] **Step 1: I test che falliscono**

Crea `backend/tests/domain/test_substitutions.py`:

```python
"""Il vocabolario di «Sostituisci» (R5), e il contesto di una ricetta.

Il contesto si ricava dalla categoria della ricetta, senza AI: dolce se la prima parola
è «dolci» (le categorie di GialloZafferano sono «Dolci e Desserts», «Primi piatti»…),
salato in ogni altro caso. Il burro nella besciamella non è il burro nei biscotti.
"""

import pytest

from app.domain.substitutions import (
    SUBSTITUTE_NOTE_MAX,
    SUBSTITUTES_MAX,
    SubstitutionContext,
    clean_note,
    recipe_context,
)


@pytest.mark.parametrize(
    "category,expected",
    [
        ("Dolci e Desserts", SubstitutionContext.SWEET),
        ("Dolci", SubstitutionContext.SWEET),
        ("  dolci e desserts ", SubstitutionContext.SWEET),
        ("DOLCI", SubstitutionContext.SWEET),
        ("Primi piatti", SubstitutionContext.SAVORY),
        ("Secondi piatti", SubstitutionContext.SAVORY),
        ("Antipasti", SubstitutionContext.SAVORY),
        # pane e pizza, ma anche brioche: la voce generale è salata, e dove sbaglia c'è la
        # correzione della ricetta (spec §3.1)
        ("Lievitati", SubstitutionContext.SAVORY),
        # la prima parola, non l'inizio della stringa
        ("Dolcificanti", SubstitutionContext.SAVORY),
        ("", SubstitutionContext.SAVORY),
        ("   ", SubstitutionContext.SAVORY),
        # le ricette scritte a mano e quelle del seme non hanno categoria
        (None, SubstitutionContext.SAVORY),
    ],
)
def test_il_contesto_viene_dalla_prima_parola_della_categoria(category, expected):
    assert recipe_context(category) is expected


@pytest.mark.parametrize(
    "note,expected",
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("metà dose", "metà dose"),
        ("  metà   dose  ", "metà dose"),
        ("sciolto\nin acqua", "sciolto in acqua"),
    ],
)
def test_una_nota_si_pulisce_e_vuota_non_c_e(note, expected):
    assert clean_note(note) == expected


def test_i_limiti():
    assert SUBSTITUTES_MAX == 3
    assert SUBSTITUTE_NOTE_MAX == 60


def test_l_ordine_dei_contesti_e_salato_poi_dolce():
    """L'ordine delle schede in Anagrafica: la gran parte del ricettario è salata."""
    assert [c.value for c in SubstitutionContext] == ["salato", "dolce"]
```

- [ ] **Step 2: Fallisce**

Run (da `<worktree>/backend`): `TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_r5 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/domain/test_substitutions.py`
Expected: FAIL, `ModuleNotFoundError: No module named 'app.domain.substitutions'`.

- [ ] **Step 3: Il modulo**

Crea `backend/app/domain/substitutions.py`:

```python
"""I sostituti di un ingrediente (R5): il vocabolario e le regole pure.

Tre esiti per «Sostituisci», e sono tre cose diverse (docs/prossimi-passi.md, R5): uno o
più sostituti; «si può omettere»; «insostituibile». Si decidono per ingrediente e per
contesto — dolce o salato —, perché il burro nella besciamella non è il burro nei
biscotti; il contesto di una ricetta si ricava dalla sua categoria, senza AI.

Niente database qui: chi legge e chi scrive (`repositories/substitutions.py`,
`services/substitutions.py`) importa questi nomi. La regola che R6 userà per dire
«cucinabile con sostituti» è scritta nella spec R5 (§8), non qui: R5 non la costruisce.
"""

from enum import StrEnum


class SubstitutionContext(StrEnum):
    # in quest'ordine: è quello delle schede in Anagrafica, e la gran parte del
    # ricettario è salata
    SAVORY = "salato"
    SWEET = "dolce"


class SubstitutionVerdict(StrEnum):
    SUBSTITUTES = "substitutes"
    # soddisfa qualunque riga, anche principale (decisione 3 di Mattia, per R6)
    OMIT = "omit"
    IRREPLACEABLE = "irreplaceable"


class DecidedBy(StrEnum):
    """Chi ha scritto una risposta. Le stesse due parole di `import_terms.decided_by`."""

    AI = "ai"
    HUMAN = "human"


# Da uno a tre sostituti, dal migliore: più di tre in un pannello sotto una riga, al
# telefono, sono una lista da scorrere invece di una risposta
SUBSTITUTES_MAX = 3
# «metà dose», «sciolto in acqua»: poche parole. È anche la larghezza della colonna
SUBSTITUTE_NOTE_MAX = 60

# La prima parola della categoria di una ricetta dolce: «Dolci e Desserts», «Dolci»
SWEET_CATEGORY_WORD = "dolci"


def recipe_context(category: str | None) -> SubstitutionContext:
    """Dolce se la prima parola della categoria è «dolci», salato in ogni altro caso.

    La prima parola e non l'inizio della stringa: «Dolcificanti» non è un dolce. Senza
    categoria — le ricette scritte a mano, quelle del seme — è salato: è il caso più
    comune, e dove sbaglia c'è la correzione della singola ricetta.
    """
    words = (category or "").casefold().split()
    if words and words[0] == SWEET_CATEGORY_WORD:
        return SubstitutionContext.SWEET
    return SubstitutionContext.SAVORY


def clean_note(note: str | None) -> str | None:
    """La nota di un sostituto senza spazi di troppo; vuota non è una nota."""
    if note is None:
        return None
    cleaned = " ".join(note.split())
    return cleaned or None
```

- [ ] **Step 4: Passano**

Run: il comando di pytest con `tests/domain/test_substitutions.py`.
Expected: PASS, 20 test (12 + 6 + 1 + 1).

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/substitutions.py backend/tests/domain/test_substitutions.py
git commit -m "feat(domain): R5, il vocabolario dei sostituti e il contesto dolce/salato della ricetta"
```

---

### Task 2: Le tabelle e la migrazione `0015`

**Files:**
- Create: `backend/app/db/models/substitution.py`
- Modify: `backend/app/db/models/__init__.py`
- Create: `backend/alembic/versions/0015_sostituti.py`
- Create: `backend/tests/db/test_migration_0015.py`, `backend/tests/db/test_substitution_schema.py`

**Interfaces:**
- Consumes: `SUBSTITUTE_NOTE_MAX` (Task 1).
- Produces: `IngredientSubstitution` (tabella `ingredient_substitutions`: `id`, `ingredient_id`, `context: str | None`, `recipe_id: UUID | None`, `verdict: str`, `decided_by: str`, `created_at`, `updated_at`; relazione `options: list[SubstitutionOption]` ordinata per `position`) e `SubstitutionOption` (tabella `substitution_options`: `id`, `substitution_id`, `substitute_id`, `note: str | None`, `position: int`; relazioni `substitution` e `substitute: Ingredient`, quest'ultima `lazy="joined"`); la revisione `"0015"` con `down_revision = "0012"`. I Task 3–8 li usano.

- [ ] **Step 1: I test che falliscono**

Crea `backend/tests/db/test_migration_0015.py`:

```python
"""La migrazione 0015 sale e scende (R5).

Su un database suo, creato e distrutto qui, come `test_migration_0012.py`: far scendere
quello della suite toglierebbe le tabelle sotto i piedi a ogni altro test. Alembic gira
in un sottoprocesso, perché il suo template async chiama `asyncio.run`, che dentro un
loop già in corsa esplode.

Scende di **una** revisione (`downgrade -1`) e non verso un numero: al merge la
`down_revision` della 0015 si ripunta sulla testa di `master` di quel momento, e questo
test deve reggere senza essere toccato.
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
SCRATCH_DB = f"{TEST_DB}_migrazione_0015"

TABELLE = (
    "SELECT count(*) FROM information_schema.tables "
    "WHERE table_name IN ('ingredient_substitutions', 'substitution_options')"
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


async def _scrivi(url: str, sql: str, **params) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(sql), params)
    finally:
        await engine.dispose()


async def test_la_0015_sale_scende_e_risale(scratch_url):
    alembic(scratch_url, "upgrade", "0015")
    assert await _scalar(scratch_url, TABELLE) == 2
    await _scrivi(
        scratch_url,
        "INSERT INTO ingredients (id, name, display_name, category, kind) VALUES "
        "('00000000-0000-0000-0000-000000000001', 'pollo', 'Pollo', 'carne', 'food'), "
        "('00000000-0000-0000-0000-000000000002', 'tacchino', 'Tacchino', 'carne', 'food')",
    )
    await _scrivi(
        scratch_url,
        "INSERT INTO ingredient_substitutions (id, ingredient_id, context, verdict, decided_by) "
        "VALUES ('00000000-0000-0000-0000-0000000000a1', '00000000-0000-0000-0000-000000000001', "
        "'salato', 'substitutes', 'ai')",
    )
    await _scrivi(
        scratch_url,
        "INSERT INTO substitution_options (id, substitution_id, substitute_id, note, position) "
        "VALUES (gen_random_uuid(), '00000000-0000-0000-0000-0000000000a1', "
        "'00000000-0000-0000-0000-000000000002', 'metà dose', 0)",
    )
    assert await _scalar(scratch_url, "SELECT note FROM substitution_options") == "metà dose"

    alembic(scratch_url, "downgrade", "-1")
    assert await _scalar(scratch_url, TABELLE) == 0

    alembic(scratch_url, "upgrade", "head")
    assert await _scalar(scratch_url, TABELLE) == 2
```

Crea `backend/tests/db/test_substitution_schema.py`:

```python
"""I vincoli delle risposte di «Sostituisci» (R5), nel database.

Le regole che contano stanno nello schema e non solo nel codice che scrive: una voce
generale per ingrediente e contesto, una correzione per ricetta e ingrediente, una
correzione sempre scritta a mano, un sostituto una volta sola per risposta. Alembic non
confronta i predicati degli indici parziali (vedi `test_metadata_matches_migrations.py`):
per questo qui si provano col comportamento, inserendo i doppioni.
"""

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError

from app.core.db import Base
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import Recipe, RecipeSource
from app.db.models.substitution import IngredientSubstitution, SubstitutionOption
from app.repositories.recipes import create_recipe

INDICI = {"uq_substitution_general", "uq_substitution_recipe", "ix_substitution_options_substitute"}


@pytest_asyncio.fixture
async def voci(db_session):
    tutte = {
        nome: Ingredient(name=nome, display_name=nome.capitalize(), category=IngredientCategory.CARNE)
        for nome in ("pollo", "tacchino", "coniglio")
    }
    db_session.add_all(tutte.values())
    await db_session.flush()
    return tutte


async def _ricetta(db_session, titolo: str) -> Recipe:
    return await create_recipe(
        db_session, title=titolo, description=None, instructions="Cuoci.", servings=2,
        source=RecipeSource.MANUAL, source_ref=None, ingredients=[], embedding=None,
    )


async def _rifiutata(db_session, *righe) -> None:
    """Le righe, in un SAVEPOINT suo: il rifiuto non lascia la sessione rotta."""
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add_all(righe)
            await db_session.flush()


async def _accettata(db_session, *righe) -> None:
    async with db_session.begin_nested():
        db_session.add_all(righe)
        await db_session.flush()


def _generale(voce, contesto="salato", **altro) -> IngredientSubstitution:
    return IngredientSubstitution(
        ingredient_id=voce.id, context=contesto, verdict=altro.get("verdict", "omit"),
        decided_by=altro.get("decided_by", "ai"),
    )


def _correzione(voce, ricetta, **altro) -> IngredientSubstitution:
    return IngredientSubstitution(
        ingredient_id=voce.id, recipe_id=ricetta.id, verdict=altro.get("verdict", "omit"),
        decided_by=altro.get("decided_by", "human"),
    )


async def test_una_voce_generale_per_ingrediente_e_contesto(db_session, voci):
    await _accettata(db_session, _generale(voci["pollo"], "salato"))
    await _rifiutata(db_session, _generale(voci["pollo"], "salato", decided_by="human"))
    # l'altro contesto, e la correzione di una ricetta, stanno accanto
    ricetta = await _ricetta(db_session, "Pollo arrosto")
    await _accettata(db_session, _generale(voci["pollo"], "dolce"))
    await _accettata(db_session, _correzione(voci["pollo"], ricetta))


async def test_una_correzione_per_ricetta_e_ingrediente(db_session, voci):
    prima = await _ricetta(db_session, "Pollo arrosto")
    seconda = await _ricetta(db_session, "Pollo al curry")
    await _accettata(db_session, _correzione(voci["pollo"], prima))
    await _rifiutata(db_session, _correzione(voci["pollo"], prima, verdict="irreplaceable"))
    await _accettata(db_session, _correzione(voci["pollo"], seconda))


async def test_una_riga_e_o_generale_o_di_una_ricetta(db_session, voci):
    ricetta = await _ricetta(db_session, "Pollo arrosto")
    entrambi = IngredientSubstitution(
        ingredient_id=voci["pollo"].id, context="salato", recipe_id=ricetta.id,
        verdict="omit", decided_by="human",
    )
    nessuno = IngredientSubstitution(ingredient_id=voci["pollo"].id, verdict="omit", decided_by="human")
    await _rifiutata(db_session, entrambi)
    await _rifiutata(db_session, nessuno)


async def test_una_correzione_di_ricetta_e_sempre_a_mano(db_session, voci):
    ricetta = await _ricetta(db_session, "Pollo arrosto")
    await _rifiutata(db_session, _correzione(voci["pollo"], ricetta, decided_by="ai"))


async def test_esiti_contesti_e_autori_sono_quelli_del_dominio(db_session, voci):
    await _rifiutata(db_session, _generale(voci["pollo"], "salato", verdict="forse"))
    await _rifiutata(db_session, _generale(voci["pollo"], "speziato"))
    await _rifiutata(db_session, _generale(voci["pollo"], "salato", decided_by="auto"))


async def test_un_sostituto_una_volta_sola_per_risposta(db_session, voci):
    risposta = _generale(voci["pollo"], verdict="substitutes")
    await _accettata(db_session, risposta)
    await _accettata(
        db_session,
        SubstitutionOption(substitution_id=risposta.id, substitute_id=voci["tacchino"].id, position=0),
    )
    await _rifiutata(
        db_session,
        SubstitutionOption(substitution_id=risposta.id, substitute_id=voci["tacchino"].id, position=1),
    )


async def test_un_ingrediente_o_una_ricetta_che_spariscono_si_portano_via_le_loro_righe(
    db_session, voci
):
    ricetta = await _ricetta(db_session, "Pollo arrosto")
    risposta = _generale(voci["pollo"], verdict="substitutes")
    correzione = _correzione(voci["coniglio"], ricetta)
    await _accettata(db_session, risposta, correzione)
    await _accettata(
        db_session,
        SubstitutionOption(substitution_id=risposta.id, substitute_id=voci["tacchino"].id, position=0),
    )

    await db_session.execute(delete(Ingredient).where(Ingredient.id == voci["tacchino"].id))
    await db_session.execute(delete(Recipe).where(Recipe.id == ricetta.id))

    sostituti = (await db_session.execute(select(SubstitutionOption.id))).all()
    righe = (await db_session.execute(select(IngredientSubstitution.id))).scalars().all()
    assert sostituti == []
    assert righe == [risposta.id]


async def test_i_tre_indici_sono_dichiarati_e_ci_sono(db_session):
    dichiarati = {index.name for table in Base.metadata.tables.values() for index in table.indexes}
    assert INDICI <= dichiarati
    nel_database = await db_session.execute(
        text("SELECT indexname FROM pg_indexes WHERE schemaname = current_schema()")
    )
    assert INDICI <= {riga.indexname for riga in nel_database}
```

- [ ] **Step 2: Falliscono**

Run: il comando di pytest con `tests/db/test_migration_0015.py tests/db/test_substitution_schema.py`.
Expected: FAIL, `ModuleNotFoundError: No module named 'app.db.models.substitution'` (e la migrazione: «Can't locate revision identified by '0015'»).

- [ ] **Step 3: I modelli**

Crea `backend/app/db/models/substitution.py`:

```python
"""Le risposte di «Sostituisci» (R5): una tabella per due ambiti, e i sostituti.

`ingredient_substitutions` tiene:

- la **voce generale** di un ingrediente in un contesto — `recipe_id` NULL, `context`
  «dolce» o «salato» —, scritta dall'AI (`decided_by = "ai"`) o da una persona in
  Anagrafica (`"human"`);
- la **correzione di una ricetta** — `recipe_id` presente, `context` NULL —, sempre di
  una persona: «Non va bene qui».

`ck_substitution_scope` tiene separati i due ambiti; due indici unici **parziali** ne
fanno rispettare l'unicità (una voce per ingrediente e contesto, una correzione per
ricetta e ingrediente). Le chiavi esterne sono in CASCADE: un ingrediente o una ricetta
che spariscono — un annullamento della coda, l'import che rifà una ricetta — si portano
via le loro righe, e chi legge tratta una risposta rimasta senza sostituti come nessuna
risposta (`is_answered` in `repositories/substitutions.py`).
"""

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.db.models.base import TimestampMixin, UUIDMixin
from app.db.models.ingredient import Ingredient
from app.domain.substitutions import SUBSTITUTE_NOTE_MAX


class IngredientSubstitution(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ingredient_substitutions"
    __table_args__ = (
        CheckConstraint(
            "verdict IN ('substitutes', 'omit', 'irreplaceable')", name="ck_substitution_verdict"
        ),
        CheckConstraint("decided_by IN ('ai', 'human')", name="ck_substitution_decided_by"),
        CheckConstraint(
            "context IS NULL OR context IN ('dolce', 'salato')", name="ck_substitution_context"
        ),
        # o generale (un contesto, nessuna ricetta) o di una ricetta (nessun contesto)
        CheckConstraint("(recipe_id IS NULL) <> (context IS NULL)", name="ck_substitution_scope"),
        # la correzione di una ricetta la scrive solo una persona
        CheckConstraint(
            "recipe_id IS NULL OR decided_by = 'human'", name="ck_substitution_recipe_is_human"
        ),
        # dichiarati qui e non solo nella migrazione: l'autogenerate cancellerebbe ogni
        # indice che i modelli non conoscono. Il predicato Alembic non lo confronta: lo
        # provano i doppioni di `tests/db/test_substitution_schema.py`
        Index(
            "uq_substitution_general", "ingredient_id", "context",
            unique=True, postgresql_where=text("recipe_id IS NULL"),
        ),
        Index(
            "uq_substitution_recipe", "recipe_id", "ingredient_id",
            unique=True, postgresql_where=text("recipe_id IS NOT NULL"),
        ),
    )

    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="CASCADE")
    )
    context: Mapped[str | None] = mapped_column(String(10), nullable=True)
    recipe_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recipes.id", ondelete="CASCADE"), nullable=True
    )
    verdict: Mapped[str] = mapped_column(String(20))
    decided_by: Mapped[str] = mapped_column(String(10))

    options: Mapped[list["SubstitutionOption"]] = relationship(
        back_populates="substitution",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by="SubstitutionOption.position",
    )


class SubstitutionOption(UUIDMixin, Base):
    """Un sostituto di una risposta, con la sua nota e il suo posto (dal migliore)."""

    __tablename__ = "substitution_options"
    __table_args__ = (
        UniqueConstraint("substitution_id", "substitute_id"),
        # la fusione e le cancellazioni cercano per sostituto
        Index("ix_substitution_options_substitute", "substitute_id"),
    )

    substitution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingredient_substitutions.id", ondelete="CASCADE")
    )
    substitute_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="CASCADE")
    )
    note: Mapped[str | None] = mapped_column(String(SUBSTITUTE_NOTE_MAX), nullable=True)
    position: Mapped[int] = mapped_column(SmallInteger)

    substitution: Mapped[IngredientSubstitution] = relationship(back_populates="options")
    substitute: Mapped[Ingredient] = relationship(lazy="joined")
```

In `backend/app/db/models/__init__.py`, dopo `from app.db.models.shopping import ShoppingListItem` aggiungi:

```python
from app.db.models.substitution import IngredientSubstitution, SubstitutionOption
```

e in `__all__`, in ordine alfabetico, `"IngredientSubstitution",` dopo `"IngredientAlias",` e `"SubstitutionOption",` dopo `"ShoppingListItem",`.

- [ ] **Step 4: La migrazione**

Crea `backend/alembic/versions/0015_sostituti.py`:

```python
"""i sostituti degli ingredienti (R5)

Revision ID: 0015
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015"
# Numero riservato dalla fase giorno del 2026-10-13: R5 parte da `master`, ferma alla
# `0012`. Al merge questa riga si ripunta sulla testa di `master` di quel momento, e
# `alembic heads` deve dire una testa sola (il piano, «Al merge»).
down_revision = "0012"


def upgrade() -> None:
    # Nessun passo dati: le risposte le scrive `python -m app.cli.decide_substitutes`, o
    # «Sostituisci» la prima volta che serve. Un comando a parte e non un passo qui perché
    # chiama l'AI: una migrazione che va in rete renderebbe l'avvio del backend (che migra
    # da sé, `docker-entrypoint.sh`) dipendente da OpenRouter.
    op.create_table(
        "ingredient_substitutions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ingredient_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("context", sa.String(10)),
        sa.Column("recipe_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("recipes.id", ondelete="CASCADE")),
        sa.Column("verdict", sa.String(20), nullable=False),
        sa.Column("decided_by", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.CheckConstraint("verdict IN ('substitutes', 'omit', 'irreplaceable')",
                           name="ck_substitution_verdict"),
        sa.CheckConstraint("decided_by IN ('ai', 'human')", name="ck_substitution_decided_by"),
        sa.CheckConstraint("context IS NULL OR context IN ('dolce', 'salato')",
                           name="ck_substitution_context"),
        sa.CheckConstraint("(recipe_id IS NULL) <> (context IS NULL)",
                           name="ck_substitution_scope"),
        sa.CheckConstraint("recipe_id IS NULL OR decided_by = 'human'",
                           name="ck_substitution_recipe_is_human"),
    )
    op.create_index(
        "uq_substitution_general", "ingredient_substitutions", ["ingredient_id", "context"],
        unique=True, postgresql_where=sa.text("recipe_id IS NULL"),
    )
    op.create_index(
        "uq_substitution_recipe", "ingredient_substitutions", ["recipe_id", "ingredient_id"],
        unique=True, postgresql_where=sa.text("recipe_id IS NOT NULL"),
    )
    op.create_table(
        "substitution_options",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("substitution_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ingredient_substitutions.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("substitute_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False),
        sa.Column("note", sa.String(60)),
        sa.Column("position", sa.SmallInteger, nullable=False),
        sa.UniqueConstraint("substitution_id", "substitute_id"),
    )
    op.create_index(
        "ix_substitution_options_substitute", "substitution_options", ["substitute_id"]
    )


def downgrade() -> None:
    # Scendere perde ogni risposta, dell'AI e scritta a mano.
    op.drop_table("substitution_options")
    op.drop_table("ingredient_substitutions")
```

- [ ] **Step 5: Passano, con la rete di sicurezza dell'autogenerate**

Run: il comando di pytest con `tests/db/`.
Expected: PASS, compreso `test_metadata_matches_migrations.py` (modello e schema coincidono: nessuna operazione proposta) e i 9 test nuovi (1 + 8). Se l'autogenerate propone qualcosa, il modello e la migrazione divergono: correggi quello dei due che sbaglia, mai il test.

- [ ] **Step 6: Commit**

```bash
git add backend/app/db/models/substitution.py backend/app/db/models/__init__.py backend/alembic/versions/0015_sostituti.py backend/tests/db/test_migration_0015.py backend/tests/db/test_substitution_schema.py
git commit -m "feat(db): R5, le risposte di «Sostituisci» e i sostituti (migrazione 0015)"
```

---

### Task 3: Il repository — leggere, scrivere, controllare una risposta

**Files:**
- Create: `backend/app/repositories/substitutions.py`
- Test: `backend/tests/repositories/test_substitutions.py`

**Interfaces:**
- Consumes: Task 1 (`SubstitutionContext`, `SubstitutionVerdict`, `DecidedBy`, `SUBSTITUTES_MAX`, `SUBSTITUTE_NOTE_MAX`, `clean_note`); Task 2 (`IngredientSubstitution`, `SubstitutionOption`); `IngredientKind` (`app.domain.rules`).
- Produces (in `app.repositories.substitutions`):
  - `@dataclass(frozen=True) class Answer(verdict: SubstitutionVerdict, substitutes: tuple[tuple[uuid.UUID, str | None], ...] = ())`;
  - `class SubstitutionRefused(Exception)` con `.message: str`;
  - `visible_options(row: IngredientSubstitution) -> list[SubstitutionOption]`; `is_answered(row: IngredientSubstitution) -> bool`;
  - `async general_row(session, ingredient_id: uuid.UUID, context: SubstitutionContext) -> IngredientSubstitution | None`;
  - `async recipe_row(session, recipe_id: uuid.UUID, ingredient_id: uuid.UUID) -> IngredientSubstitution | None`;
  - `async effective_row(session, recipe_id: uuid.UUID, ingredient_id: uuid.UUID, context: SubstitutionContext) -> IngredientSubstitution | None` (solo righe con una risposta);
  - `async checked_answer(session, ingredient_id: uuid.UUID, verdict: SubstitutionVerdict, substitutes: Sequence[tuple[uuid.UUID, str | None]]) -> Answer` (solleva `SubstitutionRefused`);
  - `async write_general(session, ingredient_id, context, answer: Answer) -> None` (scritta a mano);
  - `async write_override(session, recipe_id, ingredient_id, answer: Answer) -> None`;
  - `async delete_override(session, recipe_id, ingredient_id) -> bool`;
  - `async store_ai_answer(session, ingredient_id, context, answer: Answer) -> bool` (solo dove non c'è una risposta).
  - Nessuna funzione fa commit. Le letture rileggono dal database anche le righe già nella sessione (`populate_existing`). I Task 4–8 le usano.

- [ ] **Step 1: I test che falliscono**

Crea `backend/tests/repositories/test_substitutions.py`:

```python
"""Le risposte di «Sostituisci» (R5): leggerle, scriverle, controllarle.

Due ambiti in una tabella — la voce generale (ingrediente × contesto) e la correzione di
una ricetta —, e una regola che li lega: per una riga vale la correzione, se c'è, poi la
voce generale. Una risposta «sostituti» rimasta senza sostituti visibili non vale niente.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import RecipeSource
from app.db.models.substitution import IngredientSubstitution
from app.domain.substitutions import DecidedBy, SubstitutionContext, SubstitutionVerdict
from app.repositories import substitutions as repo
from app.repositories.recipes import create_recipe
from app.repositories.substitutions import Answer, SubstitutionRefused

SALATO = SubstitutionContext.SAVORY
DOLCE = SubstitutionContext.SWEET


@pytest_asyncio.fixture
async def voci(db_session):
    def voce(nome: str, reparto: str) -> Ingredient:
        return Ingredient(name=nome, display_name=nome.capitalize(), category=reparto)

    tutte = {
        "pollo": voce("pollo", IngredientCategory.CARNE),
        "tacchino": voce("tacchino", IngredientCategory.CARNE),
        "coniglio": voce("coniglio", IngredientCategory.CARNE),
        "burro": voce("burro", IngredientCategory.LATTICINI),
        "margarina": voce("margarina", IngredientCategory.CONDIMENTI),
        "detersivo": voce("detersivo", IngredientCategory.CASA),
    }
    db_session.add_all(tutte.values())
    await db_session.flush()
    return tutte


@pytest_asyncio.fixture
async def ricetta(db_session, voci):
    return await create_recipe(
        db_session, title="Pollo arrosto", description=None, instructions="Cuoci.",
        servings=2, source=RecipeSource.MANUAL, source_ref=None,
        ingredients=[(voci["pollo"].id, "primary", "1", None)], embedding=None,
    )


def sostituti(*voci_: Ingredient) -> Answer:
    return Answer(SubstitutionVerdict.SUBSTITUTES, tuple((voce.id, None) for voce in voci_))


def nomi(riga: IngredientSubstitution | None) -> list[str]:
    assert riga is not None
    return [opzione.substitute.name for opzione in repo.visible_options(riga)]


# --- controllare una risposta scritta a mano ---------------------------------------


async def test_una_risposta_giusta_esce_con_le_note_pulite(db_session, voci):
    risposta = await repo.checked_answer(
        db_session, voci["pollo"].id, SubstitutionVerdict.SUBSTITUTES,
        [(voci["tacchino"].id, "  metà   dose "), (voci["coniglio"].id, "   ")],
    )
    assert risposta == Answer(
        SubstitutionVerdict.SUBSTITUTES,
        ((voci["tacchino"].id, "metà dose"), (voci["coniglio"].id, None)),
    )


async def test_omettere_e_insostituibile_non_hanno_sostituti(db_session, voci):
    for esito in (SubstitutionVerdict.OMIT, SubstitutionVerdict.IRREPLACEABLE):
        assert await repo.checked_answer(db_session, voci["pollo"].id, esito, []) == Answer(esito)


async def test_i_rifiuti_dicono_cosa_fare(db_session, voci):
    pollo = voci["pollo"].id

    async def rifiuto(esito, scelti) -> str:
        with pytest.raises(SubstitutionRefused) as preso:
            await repo.checked_answer(db_session, pollo, esito, scelti)
        return preso.value.message

    S = SubstitutionVerdict.SUBSTITUTES
    assert await rifiuto(S, []) == "Scegli almeno un ingrediente da usare al suo posto."
    assert await rifiuto(SubstitutionVerdict.OMIT, [(voci["tacchino"].id, None)]) == (
        "Chi si omette o è insostituibile non ha sostituti: toglili, poi salva."
    )
    quattro = [(voci[n].id, None) for n in ("tacchino", "coniglio", "burro", "margarina")]
    assert await rifiuto(S, quattro) == "Al massimo tre sostituti: togline uno, poi salva."
    assert await rifiuto(S, [(uuid.uuid4(), None)]) == (
        "Uno dei sostituti scelti non è più in anagrafica: toglilo e scegline un altro."
    )
    assert await rifiuto(S, [(pollo, None)]) == (
        "«Pollo» non può sostituire sé stesso: scegli un altro ingrediente."
    )
    assert await rifiuto(S, [(voci["detersivo"].id, None)]) == (
        "«Detersivo» non è un alimento: non può sostituire un ingrediente."
    )
    assert await rifiuto(S, [(voci["tacchino"].id, None), (voci["tacchino"].id, "a fette")]) == (
        "«Tacchino» è scelto due volte: tienilo una volta sola."
    )
    assert await rifiuto(S, [(voci["tacchino"].id, "x" * 61)]) == (
        "La nota per «Tacchino» è troppo lunga: bastano poche parole, al massimo 60 caratteri."
    )


async def test_una_nota_di_sessanta_caratteri_basta(db_session, voci):
    risposta = await repo.checked_answer(
        db_session, voci["pollo"].id, SubstitutionVerdict.SUBSTITUTES,
        [(voci["tacchino"].id, "x" * 60)],
    )
    assert risposta.substitutes == ((voci["tacchino"].id, "x" * 60),)


# --- scrivere e leggere ---------------------------------------------------------------


async def test_la_voce_scritta_a_mano_sostituisce_quella_dell_ai(db_session, voci):
    pollo = voci["pollo"].id
    assert await repo.store_ai_answer(db_session, pollo, SALATO, sostituti(voci["tacchino"]))
    await repo.write_general(
        db_session, pollo, SALATO, sostituti(voci["coniglio"], voci["tacchino"])
    )

    riga = await repo.general_row(db_session, pollo, SALATO)
    assert riga is not None and riga.decided_by == DecidedBy.HUMAN
    assert nomi(riga) == ["coniglio", "tacchino"]  # nell'ordine dato
    tutte = (await db_session.execute(select(IngredientSubstitution))).scalars().all()
    assert len(tutte) == 1


async def test_i_due_contesti_sono_due_voci(db_session, voci):
    pollo = voci["pollo"].id
    await repo.write_general(db_session, pollo, SALATO, Answer(SubstitutionVerdict.OMIT))
    await repo.write_general(db_session, pollo, DOLCE, Answer(SubstitutionVerdict.IRREPLACEABLE))
    assert (await repo.general_row(db_session, pollo, SALATO)).verdict == "omit"
    assert (await repo.general_row(db_session, pollo, DOLCE)).verdict == "irreplaceable"


async def test_la_correzione_della_ricetta_vince_e_tolta_torna_la_generale(
    db_session, voci, ricetta
):
    pollo = voci["pollo"].id
    await repo.write_general(db_session, pollo, SALATO, sostituti(voci["tacchino"]))
    await repo.write_override(db_session, ricetta.id, pollo, Answer(SubstitutionVerdict.OMIT))

    vale = await repo.effective_row(db_session, ricetta.id, pollo, SALATO)
    assert vale is not None
    assert (vale.recipe_id, vale.context, vale.verdict, vale.decided_by) == (
        ricetta.id, None, "omit", "human",
    )

    assert await repo.delete_override(db_session, ricetta.id, pollo) is True
    assert nomi(await repo.effective_row(db_session, ricetta.id, pollo, SALATO)) == ["tacchino"]
    assert await repo.delete_override(db_session, ricetta.id, pollo) is False


async def test_una_nuova_correzione_prende_il_posto_della_vecchia(db_session, voci, ricetta):
    pollo = voci["pollo"].id
    await repo.write_override(db_session, ricetta.id, pollo, Answer(SubstitutionVerdict.OMIT))
    await repo.write_override(db_session, ricetta.id, pollo, sostituti(voci["coniglio"]))
    assert nomi(await repo.recipe_row(db_session, ricetta.id, pollo)) == ["coniglio"]


async def test_senza_risposte_non_vale_niente(db_session, voci, ricetta):
    assert await repo.effective_row(db_session, ricetta.id, voci["pollo"].id, SALATO) is None


async def test_un_sostituto_cancellato_lascia_la_voce_senza_risposta(db_session, voci, ricetta):
    """L'annullamento di una decisione della coda cancella l'ingrediente che l'AI aveva
    proposto: la risposta resta, vuota, e vale come nessuna (Review Focus 2)."""
    pollo = voci["pollo"].id
    await repo.store_ai_answer(db_session, pollo, SALATO, sostituti(voci["tacchino"]))
    await db_session.execute(delete(Ingredient).where(Ingredient.id == voci["tacchino"].id))

    riga = await repo.general_row(db_session, pollo, SALATO)
    assert riga is not None and repo.is_answered(riga) is False
    assert await repo.effective_row(db_session, ricetta.id, pollo, SALATO) is None


async def test_un_sostituto_diventato_non_alimentare_non_si_vede(db_session, voci):
    pollo = voci["pollo"].id
    await repo.store_ai_answer(
        db_session, pollo, SALATO, sostituti(voci["tacchino"], voci["coniglio"])
    )
    voci["tacchino"].category = IngredientCategory.CASA
    await db_session.flush()
    assert nomi(await repo.general_row(db_session, pollo, SALATO)) == ["coniglio"]


async def test_omettere_risponde_anche_senza_sostituti(db_session, voci):
    await repo.store_ai_answer(db_session, voci["pollo"].id, SALATO, Answer(SubstitutionVerdict.OMIT))
    riga = await repo.general_row(db_session, voci["pollo"].id, SALATO)
    assert repo.is_answered(riga) is True


# --- l'AI scrive solo dove non c'è una risposta ----------------------------------------


async def test_l_ai_scrive_dove_non_c_e_niente(db_session, voci):
    pollo = voci["pollo"].id
    assert await repo.store_ai_answer(db_session, pollo, SALATO, sostituti(voci["tacchino"])) is True
    riga = await repo.general_row(db_session, pollo, SALATO)
    assert riga.decided_by == DecidedBy.AI and nomi(riga) == ["tacchino"]


async def test_l_ai_non_tocca_una_risposta_che_c_e(db_session, voci):
    pollo = voci["pollo"].id
    await repo.write_general(db_session, pollo, SALATO, Answer(SubstitutionVerdict.IRREPLACEABLE))
    assert await repo.store_ai_answer(db_session, pollo, SALATO, sostituti(voci["tacchino"])) is False
    await repo.store_ai_answer(db_session, pollo, DOLCE, sostituti(voci["tacchino"]))
    assert await repo.store_ai_answer(db_session, pollo, DOLCE, sostituti(voci["coniglio"])) is False

    assert (await repo.general_row(db_session, pollo, SALATO)).verdict == "irreplaceable"
    assert nomi(await repo.general_row(db_session, pollo, DOLCE)) == ["tacchino"]


async def test_l_ai_rimpiazza_una_risposta_rimasta_vuota(db_session, voci):
    pollo = voci["pollo"].id
    await repo.write_general(db_session, pollo, SALATO, sostituti(voci["tacchino"]))
    await db_session.execute(delete(Ingredient).where(Ingredient.id == voci["tacchino"].id))

    assert await repo.store_ai_answer(db_session, pollo, SALATO, sostituti(voci["coniglio"])) is True
    riga = await repo.general_row(db_session, pollo, SALATO)
    assert riga.decided_by == DecidedBy.AI and nomi(riga) == ["coniglio"]


async def test_l_ai_non_scavalca_chi_scrive_fra_il_controllo_e_la_scrittura(
    db_session, voci, monkeypatch
):
    """La scrittura stessa controlla (`ON CONFLICT DO NOTHING`): se fra la lettura e
    l'`INSERT` una persona ha scritto, vince la persona."""
    pollo = voci["pollo"].id
    await repo.write_general(db_session, pollo, SALATO, Answer(SubstitutionVerdict.OMIT))

    async def non_vede_niente(*_args):
        return None

    monkeypatch.setattr(repo, "general_row", non_vede_niente)
    assert await repo.store_ai_answer(db_session, pollo, SALATO, sostituti(voci["tacchino"])) is False
    monkeypatch.undo()
    riga = await repo.general_row(db_session, pollo, SALATO)
    assert (riga.verdict, riga.decided_by) == ("omit", "human")
```

- [ ] **Step 2: Fallisce**

Run: il comando di pytest con `tests/repositories/test_substitutions.py`.
Expected: FAIL, `ModuleNotFoundError: No module named 'app.repositories.substitutions'`.

- [ ] **Step 3: Il repository**

Crea `backend/app/repositories/substitutions.py`:

```python
"""Le risposte di «Sostituisci» (R5): leggerle, scriverle, controllarle.

Una tabella sola per due ambiti (vedi `app/db/models/substitution.py`): la **voce
generale** di un ingrediente in un contesto, e la **correzione di una ricetta**. Per una
riga di ricetta vale la correzione, se c'è, altrimenti la voce generale del contesto
della ricetta (`effective_row`).

Una risposta «sostituti» che non ha più sostituti visibili — l'unico è stato cancellato,
o è diventato non alimentare — **vale come nessuna risposta** (`is_answered`): a video
«Nessun suggerimento ancora», e il calcolo la richiede. È la regola che rende innocue le
strade che cancellano un ingrediente (un annullamento della coda, l'import che rifà una
ricetta) senza che ognuna debba sapere dei sostituti; vale anche per una risposta scritta
a mano, perché non resta niente da proteggere.

L'AI scrive solo dove non c'è una risposta (`store_ai_answer`), e lo controlla nella
stessa scrittura: una correzione a mano non si riscrive mai (decisione 4 di Mattia).

Nessuna funzione fa commit: chi chiama decide, come in `services/registry.py`.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.ingredient import Ingredient
from app.db.models.substitution import IngredientSubstitution, SubstitutionOption
from app.domain.rules import IngredientKind
from app.domain.substitutions import (
    SUBSTITUTE_NOTE_MAX,
    SUBSTITUTES_MAX,
    DecidedBy,
    SubstitutionContext,
    SubstitutionVerdict,
    clean_note,
)


@dataclass(frozen=True)
class Answer:
    """Una risposta da scrivere: l'esito e, per «sostituti», gli ingredienti con la nota,
    nell'ordine in cui si mostrano (dal migliore)."""

    verdict: SubstitutionVerdict
    substitutes: tuple[tuple[uuid.UUID, str | None], ...] = ()


class SubstitutionRefused(Exception):
    """Una risposta scritta a mano che non si può salvare, col perché da mostrare."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _loaded(statement):
    # `populate_existing`: una riga già nella sessione si rilegge dal database, sostituti
    # compresi. Senza, dopo una scrittura la sessione restituirebbe la copia in memoria,
    # i cui sostituti appena aggiunti non hanno l'ingrediente caricato — e leggerlo in una
    # sessione async è un MissingGreenlet.
    return statement.options(
        selectinload(IngredientSubstitution.options).joinedload(SubstitutionOption.substitute)
    ).execution_options(populate_existing=True)


def visible_options(row: IngredientSubstitution) -> list[SubstitutionOption]:
    """I sostituti che si possono ancora proporre: solo alimenti (decisione 2)."""
    return [option for option in row.options if option.substitute.kind == IngredientKind.FOOD]


def is_answered(row: IngredientSubstitution) -> bool:
    return row.verdict != SubstitutionVerdict.SUBSTITUTES or bool(visible_options(row))


async def general_row(
    session: AsyncSession, ingredient_id: uuid.UUID, context: SubstitutionContext
) -> IngredientSubstitution | None:
    statement = select(IngredientSubstitution).where(
        IngredientSubstitution.ingredient_id == ingredient_id,
        IngredientSubstitution.context == context.value,
        IngredientSubstitution.recipe_id.is_(None),
    )
    return (await session.execute(_loaded(statement))).scalars().first()


async def recipe_row(
    session: AsyncSession, recipe_id: uuid.UUID, ingredient_id: uuid.UUID
) -> IngredientSubstitution | None:
    statement = select(IngredientSubstitution).where(
        IngredientSubstitution.recipe_id == recipe_id,
        IngredientSubstitution.ingredient_id == ingredient_id,
    )
    return (await session.execute(_loaded(statement))).scalars().first()


async def effective_row(
    session: AsyncSession,
    recipe_id: uuid.UUID,
    ingredient_id: uuid.UUID,
    context: SubstitutionContext,
) -> IngredientSubstitution | None:
    """La risposta che vale per una riga di ricetta, se ce n'è una che risponde."""
    override = await recipe_row(session, recipe_id, ingredient_id)
    if override is not None and is_answered(override):
        return override
    general = await general_row(session, ingredient_id, context)
    if general is not None and is_answered(general):
        return general
    return None


async def checked_answer(
    session: AsyncSession,
    ingredient_id: uuid.UUID,
    verdict: SubstitutionVerdict,
    substitutes: Sequence[tuple[uuid.UUID, str | None]],
) -> Answer:
    """Una risposta scritta a mano, controllata: la stessa regola che scarta quelle
    dell'AI (decisione 2), detta con la frase che lo schermo mostra accanto a «Salva»."""
    if verdict != SubstitutionVerdict.SUBSTITUTES:
        if substitutes:
            raise SubstitutionRefused(
                "Chi si omette o è insostituibile non ha sostituti: toglili, poi salva."
            )
        return Answer(verdict)
    if not substitutes:
        raise SubstitutionRefused("Scegli almeno un ingrediente da usare al suo posto.")
    if len(substitutes) > SUBSTITUTES_MAX:
        raise SubstitutionRefused("Al massimo tre sostituti: togline uno, poi salva.")
    ids = {substitute_id for substitute_id, _ in substitutes} | {ingredient_id}
    found = {
        ingredient.id: ingredient
        for ingredient in (
            await session.execute(select(Ingredient).where(Ingredient.id.in_(ids)))
        ).scalars()
    }
    seen: set[uuid.UUID] = set()
    cleaned: list[tuple[uuid.UUID, str | None]] = []
    for substitute_id, raw_note in substitutes:
        substitute = found.get(substitute_id)
        if substitute is None:
            raise SubstitutionRefused(
                "Uno dei sostituti scelti non è più in anagrafica: toglilo e scegline un altro."
            )
        name = substitute.display_name
        if substitute_id == ingredient_id:
            raise SubstitutionRefused(
                f"«{name}» non può sostituire sé stesso: scegli un altro ingrediente."
            )
        if substitute.kind != IngredientKind.FOOD:
            raise SubstitutionRefused(
                f"«{name}» non è un alimento: non può sostituire un ingrediente."
            )
        if substitute_id in seen:
            raise SubstitutionRefused(f"«{name}» è scelto due volte: tienilo una volta sola.")
        seen.add(substitute_id)
        note = clean_note(raw_note)
        if note is not None and len(note) > SUBSTITUTE_NOTE_MAX:
            raise SubstitutionRefused(
                f"La nota per «{name}» è troppo lunga: bastano poche parole, al massimo "
                f"{SUBSTITUTE_NOTE_MAX} caratteri."
            )
        cleaned.append((substitute_id, note))
    return Answer(verdict, tuple(cleaned))


def _options(answer: Answer) -> list[SubstitutionOption]:
    return [
        SubstitutionOption(substitute_id=substitute_id, note=note, position=position)
        for position, (substitute_id, note) in enumerate(answer.substitutes)
    ]


async def write_general(
    session: AsyncSession,
    ingredient_id: uuid.UUID,
    context: SubstitutionContext,
    answer: Answer,
) -> None:
    """La voce generale scritta a mano, in Anagrafica: prende il posto di quel che c'era,
    dell'AI o di una persona. «Va bene così» passa di qui con la risposta com'è."""
    await session.execute(
        delete(IngredientSubstitution).where(
            IngredientSubstitution.ingredient_id == ingredient_id,
            IngredientSubstitution.context == context.value,
            IngredientSubstitution.recipe_id.is_(None),
        )
    )
    session.add(
        IngredientSubstitution(
            ingredient_id=ingredient_id, context=context.value, recipe_id=None,
            verdict=answer.verdict.value, decided_by=DecidedBy.HUMAN.value,
            options=_options(answer),
        )
    )
    await session.flush()


async def write_override(
    session: AsyncSession, recipe_id: uuid.UUID, ingredient_id: uuid.UUID, answer: Answer
) -> None:
    """La correzione di una ricetta («Non va bene qui»): prende il posto di quella di prima."""
    await delete_override(session, recipe_id, ingredient_id)
    session.add(
        IngredientSubstitution(
            ingredient_id=ingredient_id, context=None, recipe_id=recipe_id,
            verdict=answer.verdict.value, decided_by=DecidedBy.HUMAN.value,
            options=_options(answer),
        )
    )
    await session.flush()


async def delete_override(
    session: AsyncSession, recipe_id: uuid.UUID, ingredient_id: uuid.UUID
) -> bool:
    """Toglie la correzione di una ricetta. Vero se c'era."""
    result = await session.execute(
        delete(IngredientSubstitution).where(
            IngredientSubstitution.recipe_id == recipe_id,
            IngredientSubstitution.ingredient_id == ingredient_id,
        )
    )
    await session.flush()
    return (result.rowcount or 0) > 0


async def store_ai_answer(
    session: AsyncSession,
    ingredient_id: uuid.UUID,
    context: SubstitutionContext,
    answer: Answer,
) -> bool:
    """La voce generale decisa dall'AI, solo dove non c'è una risposta. Vero se scritta.

    Una risposta rimasta vuota (`is_answered` falso) si toglie prima: non dice più niente.
    Poi l'`INSERT` stesso controlla, con `ON CONFLICT DO NOTHING` sull'indice parziale:
    se fra la lettura e la scrittura una persona ha scritto la voce, vince la persona —
    il comando gira minuti, e la correzione fatta nel frattempo non si riscrive.
    """
    existing = await general_row(session, ingredient_id, context)
    if existing is not None:
        if is_answered(existing):
            return False
        await session.execute(
            delete(IngredientSubstitution).where(IngredientSubstitution.id == existing.id)
        )
    inserted = (
        await session.execute(
            pg_insert(IngredientSubstitution)
            .values(
                id=uuid.uuid4(), ingredient_id=ingredient_id, context=context.value,
                recipe_id=None, verdict=answer.verdict.value, decided_by=DecidedBy.AI.value,
            )
            .on_conflict_do_nothing(
                index_elements=["ingredient_id", "context"],
                index_where=IngredientSubstitution.recipe_id.is_(None),
            )
            .returning(IngredientSubstitution.id)
        )
    ).scalar_one_or_none()
    if inserted is None:
        return False
    session.add_all(
        SubstitutionOption(
            substitution_id=inserted, substitute_id=substitute_id, note=note, position=position
        )
        for position, (substitute_id, note) in enumerate(answer.substitutes)
    )
    await session.flush()
    return True
```

- [ ] **Step 4: Passano**

Run: il comando di pytest con `tests/repositories/test_substitutions.py`.
Expected: PASS, 16 test.

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/substitutions.py backend/tests/repositories/test_substitutions.py
git commit -m "feat(substitutes): R5, leggere, scrivere e controllare le risposte di «Sostituisci»"
```

---

### Task 4: Le voci — quali mancano, e cosa sa un ingrediente

**Files:**
- Modify: `backend/app/repositories/substitutions.py` (gli import in cima; in fondo, due funzioni e tre classi)
- Test: `backend/tests/repositories/test_substitution_voices.py`

**Interfaces:**
- Consumes: Task 1 (`recipe_context`), Task 3 (`_loaded`, `is_answered`).
- Produces (in `app.repositories.substitutions`):
  - `@dataclass(frozen=True) class Voice(ingredient_id: uuid.UUID, name: str, context: SubstitutionContext, recipes: int)` — un ingrediente in un contesto, con le ricette non eliminate di quel contesto che lo usano;
  - `async pending_voices(session) -> list[Voice]` — le voci senza una risposta generale che risponda, dalla più usata (poi per nome, poi per contesto);
  - `@dataclass(frozen=True) class ContextView(context: SubstitutionContext, recipes: int, row: IngredientSubstitution | None)`; `@dataclass(frozen=True) class IngredientView(contexts: tuple[ContextView, ...], recipe_overrides: int)`;
  - `async ingredient_view(session, ingredient_id: uuid.UUID) -> IngredientView` — i contesti in cui l'ingrediente compare o ha una risposta, in ordine salato → dolce, con la risposta (solo se risponde) e il numero delle correzioni di ricetta che rispondono.
  - Il Task 6 usa `pending_voices`, il Task 8 `ingredient_view`.

- [ ] **Step 1: I test che falliscono**

Crea `backend/tests/repositories/test_substitution_voices.py`:

```python
"""Le voci di «Sostituisci» (R5): un ingrediente per ogni contesto in cui compare.

La doppia voce solo dove serve (decisione 1 di Mattia): il burro dei biscotti e quello
del pollo al burro sono due voci, lo zucchero dei biscotti una sola. Le ricette eliminate
non contano.
"""

from datetime import UTC, datetime

import pytest_asyncio
from sqlalchemy import delete

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import RecipeSource
from app.domain.substitutions import SubstitutionContext, SubstitutionVerdict
from app.repositories import substitutions as repo
from app.repositories.recipes import create_recipe
from app.repositories.substitutions import Answer

SALATO = SubstitutionContext.SAVORY
DOLCE = SubstitutionContext.SWEET


@pytest_asyncio.fixture
async def cucina(db_session):
    def voce(nome: str, reparto: str) -> Ingredient:
        return Ingredient(name=nome, display_name=nome.capitalize(), category=reparto)

    voci = {
        "pollo": voce("pollo", IngredientCategory.CARNE),
        "burro": voce("burro", IngredientCategory.LATTICINI),
        "zucchero": voce("zucchero", IngredientCategory.DOLCI),
        "miele": voce("miele", IngredientCategory.DOLCI),
    }
    db_session.add_all(voci.values())
    await db_session.flush()

    async def ricetta(titolo: str, categoria: str | None, *nomi: str):
        return await create_recipe(
            db_session, title=titolo, description=None, instructions="Cuoci.", servings=2,
            source=RecipeSource.MANUAL, source_ref=None,
            ingredients=[(voci[nome].id, "primary", None, None) for nome in nomi],
            embedding=None, category=categoria,
        )

    ricette = {
        "pollo al burro": await ricetta("Pollo al burro", "Secondi piatti", "pollo", "burro"),
        "biscotti": await ricetta("Biscotti", "Dolci e Desserts", "burro", "zucchero"),
        "torta": await ricetta("Torta", "Dolci", "burro", "zucchero"),
        # senza categoria è salata (Review Focus 5)
        "pollo lesso": await ricetta("Pollo lesso", None, "pollo"),
    }
    vecchia = await ricetta("Pollo vecchio", "Secondi piatti", "pollo")
    vecchia.archived_at = datetime.now(UTC)
    await db_session.flush()
    return voci, ricette


def _voci(elenco) -> list[tuple[str, str, int]]:
    return [(voce.name, voce.context.value, voce.recipes) for voce in elenco]


async def test_una_voce_per_ogni_contesto_in_cui_compare_dalla_piu_usata(db_session, cucina):
    assert _voci(await repo.pending_voices(db_session)) == [
        ("burro", "dolce", 2),
        ("pollo", "salato", 2),  # la ricetta eliminata non conta
        ("zucchero", "dolce", 2),
        ("burro", "salato", 1),
    ]


async def test_una_voce_con_una_risposta_non_manca_piu(db_session, cucina):
    voci, _ = cucina
    await repo.write_general(db_session, voci["pollo"].id, SALATO, Answer(SubstitutionVerdict.OMIT))
    await repo.store_ai_answer(
        db_session, voci["burro"].id, DOLCE, Answer(SubstitutionVerdict.IRREPLACEABLE)
    )
    assert _voci(await repo.pending_voices(db_session)) == [
        ("zucchero", "dolce", 2),
        ("burro", "salato", 1),
    ]


async def test_una_voce_rimasta_senza_sostituti_torna_a_mancare(db_session, cucina):
    voci, _ = cucina
    await repo.store_ai_answer(
        db_session, voci["burro"].id, DOLCE,
        Answer(SubstitutionVerdict.SUBSTITUTES, ((voci["miele"].id, None),)),
    )
    assert ("burro", "dolce", 2) not in _voci(await repo.pending_voices(db_session))

    await db_session.execute(delete(Ingredient).where(Ingredient.id == voci["miele"].id))
    assert ("burro", "dolce", 2) in _voci(await repo.pending_voices(db_session))


async def test_la_scheda_di_un_ingrediente_ha_i_suoi_contesti(db_session, cucina):
    voci, ricette = cucina
    burro = voci["burro"].id
    await repo.write_general(db_session, burro, DOLCE, Answer(SubstitutionVerdict.OMIT))
    await repo.write_override(
        db_session, ricette["pollo al burro"].id, burro, Answer(SubstitutionVerdict.IRREPLACEABLE)
    )

    scheda = await repo.ingredient_view(db_session, burro)

    assert [(c.context.value, c.recipes) for c in scheda.contexts] == [("salato", 1), ("dolce", 2)]
    assert scheda.contexts[0].row is None
    assert scheda.contexts[1].row is not None and scheda.contexts[1].row.verdict == "omit"
    assert scheda.recipe_overrides == 1


async def test_una_voce_senza_ricette_resta_nella_scheda(db_session, cucina):
    """La voce dolce del pollo, scritta a mano, anche se nessun dolce usa il pollo."""
    voci, _ = cucina
    pollo = voci["pollo"].id
    await repo.write_general(db_session, pollo, DOLCE, Answer(SubstitutionVerdict.IRREPLACEABLE))

    scheda = await repo.ingredient_view(db_session, pollo)
    assert [(c.context.value, c.recipes) for c in scheda.contexts] == [("salato", 2), ("dolce", 0)]


async def test_un_ingrediente_in_nessuna_ricetta_non_ha_contesti(db_session, cucina):
    voci, _ = cucina
    scheda = await repo.ingredient_view(db_session, voci["miele"].id)
    assert scheda.contexts == () and scheda.recipe_overrides == 0
```

- [ ] **Step 2: Fallisce**

Run: il comando di pytest con `tests/repositories/test_substitution_voices.py`.
Expected: FAIL, `AttributeError: module 'app.repositories.substitutions' has no attribute 'pending_voices'`.

- [ ] **Step 3: Le funzioni**

In `backend/app/repositories/substitutions.py`:

1. `from sqlalchemy import delete, select` diventa `from sqlalchemy import delete, func, select`.
2. `from app.db.models.ingredient import Ingredient` diventa due righe:
   ```python
   from app.db.models.ingredient import Ingredient
   from app.db.models.recipe import Recipe, RecipeIngredient
   ```
3. Nell'import da `app.domain.substitutions` aggiungi `recipe_context` (in fondo all'elenco).
4. In fondo al file aggiungi:

```python
@dataclass(frozen=True)
class Voice:
    """Un ingrediente in un contesto: la granularità delle risposte generali."""

    ingredient_id: uuid.UUID
    name: str
    context: SubstitutionContext
    # le ricette non eliminate di quel contesto che lo usano: l'ordine del comando
    recipes: int


async def _usage(
    session: AsyncSession, ingredient_id: uuid.UUID | None = None
) -> dict[tuple[uuid.UUID, SubstitutionContext], Voice]:
    """Le voci del ricettario: un ingrediente per ogni contesto in cui compare.

    Si raggruppa per categoria in SQL e si piega in contesti qui, con `recipe_context`:
    la regola del contesto resta una sola, nel dominio, invece di una seconda copia in
    SQL che si scollerebbe (prima lezione di CLAUDE.md). Le categorie sono una ventina.
    """
    statement = (
        select(RecipeIngredient.ingredient_id, Ingredient.name, Recipe.category, func.count())
        .join(Recipe, Recipe.id == RecipeIngredient.recipe_id)
        .join(Ingredient, Ingredient.id == RecipeIngredient.ingredient_id)
        .where(Recipe.archived_at.is_(None), Ingredient.kind == IngredientKind.FOOD)
        .group_by(RecipeIngredient.ingredient_id, Ingredient.name, Recipe.category)
    )
    if ingredient_id is not None:
        statement = statement.where(RecipeIngredient.ingredient_id == ingredient_id)
    voices: dict[tuple[uuid.UUID, SubstitutionContext], Voice] = {}
    for found_id, name, category, count in (await session.execute(statement)).all():
        context = recipe_context(category)
        before = voices.get((found_id, context))
        voices[(found_id, context)] = Voice(
            found_id, name, context, count + (before.recipes if before else 0)
        )
    return voices


async def pending_voices(session: AsyncSession) -> list[Voice]:
    """Le voci senza una risposta generale che risponda, dalla più usata.

    Le più usate prima: `--limit 20` mostra le risposte che contano di più, e un lancio
    interrotto ha già coperto le ricette più frequenti.
    """
    usage = await _usage(session)
    rows = (
        await session.execute(
            _loaded(select(IngredientSubstitution).where(IngredientSubstitution.recipe_id.is_(None)))
        )
    ).scalars().all()
    answered = {
        (row.ingredient_id, SubstitutionContext(row.context)) for row in rows if is_answered(row)
    }
    pending = [voice for key, voice in usage.items() if key not in answered]
    pending.sort(key=lambda voice: (-voice.recipes, voice.name, voice.context.value))
    return pending


@dataclass(frozen=True)
class ContextView:
    context: SubstitutionContext
    recipes: int
    # la voce generale, solo se risponde (`is_answered`)
    row: IngredientSubstitution | None


@dataclass(frozen=True)
class IngredientView:
    contexts: tuple[ContextView, ...]
    # le correzioni di ricetta che rispondono: «Corretto a mano in N ricette»
    recipe_overrides: int


async def ingredient_view(session: AsyncSession, ingredient_id: uuid.UUID) -> IngredientView:
    """Cosa sa di sostituti la scheda di un ingrediente in Anagrafica (R5).

    I contesti in cui compare in una ricetta, più quelli in cui ha una risposta anche
    senza ricette (scritta a mano, o rimasta dopo che l'ultima ricetta è stata eliminata),
    nell'ordine di `SubstitutionContext`: salato, poi dolce.
    """
    usage = await _usage(session, ingredient_id)
    rows = (
        await session.execute(
            _loaded(
                select(IngredientSubstitution).where(
                    IngredientSubstitution.ingredient_id == ingredient_id
                )
            )
        )
    ).scalars().all()
    general = {
        SubstitutionContext(row.context): row
        for row in rows
        if row.recipe_id is None and is_answered(row)
    }
    contexts = []
    for context in SubstitutionContext:
        voice = usage.get((ingredient_id, context))
        row = general.get(context)
        if voice is None and row is None:
            continue
        contexts.append(ContextView(context, voice.recipes if voice else 0, row))
    overrides = sum(1 for row in rows if row.recipe_id is not None and is_answered(row))
    return IngredientView(tuple(contexts), overrides)
```

- [ ] **Step 4: Passano**

Run: il comando di pytest con `tests/repositories/`.
Expected: PASS (i 6 test nuovi, e quelli del Task 3).

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/substitutions.py backend/tests/repositories/test_substitution_voices.py
git commit -m "feat(substitutes): R5, le voci scoperte dalla più usata e la scheda di un ingrediente"
```

---

### Task 5: La fusione sposta i sostituti sul vincitore

**Files:**
- Modify: `backend/app/repositories/substitutions.py` (gli import; in fondo, `move_substitutions`)
- Modify: `backend/app/services/registry.py` (l'import e una chiamata in `merge_ingredients`)
- Test: `backend/tests/services/test_registry_merge_substitutes.py`

**Interfaces:**
- Consumes: Task 3 (`_loaded`, `is_answered`); `merge_ingredients`, `preview_merge` (`app.services.registry`).
- Produces: `async move_substitutions(session, loser_id: uuid.UUID, winner_id: uuid.UUID) -> None` in `app.repositories.substitutions`, chiamata da `merge_ingredients` prima che il perdente sparisca. Non fa commit.

- [ ] **Step 1: I test che falliscono**

Crea `backend/tests/services/test_registry_merge_substitutes.py`:

```python
"""La fusione di due ingredienti e i sostituti (R5): tutto passa al vincitore.

Dove il perdente è un sostituto va il vincitore, mai due volte nella stessa risposta e
mai come sostituto di sé stesso. Fra due voci generali dello stesso contesto vince quella
che risponde, poi quella scritta a mano, poi quella del vincitore. Le correzioni di
ricetta seguono la riga della ricetta. Una risposta «sostituti» rimasta vuota si toglie.
Sempre attraverso `merge_ingredients`, la funzione che le rotte e il comando chiamano.
"""

import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import RecipeSource
from app.db.models.substitution import IngredientSubstitution, SubstitutionOption
from app.repositories.recipes import create_recipe
from app.services.registry import merge_ingredients, preview_merge


@pytest_asyncio.fixture
async def voci(db_session):
    tutte = {
        nome: Ingredient(name=nome, display_name=nome.capitalize(), category=IngredientCategory.CARNE)
        for nome in ("pollo", "tacchino", "coniglio", "manzo", "agnello")
    }
    db_session.add_all(tutte.values())
    await db_session.flush()
    return {nome: voce.id for nome, voce in tutte.items()}


async def _risposta(db_session, voce, contesto=None, ricetta=None, verdetto="substitutes",
                    sostituti=(), decided_by="ai"):
    riga = IngredientSubstitution(
        ingredient_id=voce, context=contesto, recipe_id=ricetta, verdict=verdetto,
        decided_by=decided_by,
        options=[
            SubstitutionOption(substitute_id=sostituto, position=posto)
            for posto, sostituto in enumerate(sostituti)
        ],
    )
    db_session.add(riga)
    await db_session.flush()
    return riga


async def _risposte(db_session, voce) -> set[tuple]:
    righe = (
        await db_session.execute(
            select(IngredientSubstitution)
            .where(IngredientSubstitution.ingredient_id == voce)
            .options(
                selectinload(IngredientSubstitution.options).joinedload(SubstitutionOption.substitute)
            )
            .execution_options(populate_existing=True)
        )
    ).scalars().all()
    return {
        (
            riga.context, riga.recipe_id, riga.verdict, riga.decided_by,
            tuple(opzione.substitute.name for opzione in riga.options),
        )
        for riga in righe
    }


async def _ricetta(db_session, titolo: str, *voci_):
    return (
        await create_recipe(
            db_session, title=titolo, description=None, instructions="Cuoci.", servings=2,
            source=RecipeSource.MANUAL, source_ref=None,
            ingredients=[(voce, "primary", None, None) for voce in voci_], embedding=None,
        )
    ).id


async def test_la_voce_del_perdente_passa_al_vincitore_che_non_ne_ha(db_session, voci):
    await _risposta(db_session, voci["tacchino"], "salato", sostituti=[voci["coniglio"]])

    await merge_ingredients(db_session, voci["tacchino"], voci["pollo"])

    assert await _risposte(db_session, voci["pollo"]) == {
        ("salato", None, "substitutes", "ai", ("coniglio",)),
    }
    assert await _risposte(db_session, voci["tacchino"]) == set()


async def test_fra_due_voci_vince_la_mano(db_session, voci):
    await _risposta(db_session, voci["pollo"], "salato", sostituti=[voci["coniglio"]])
    await _risposta(db_session, voci["tacchino"], "salato", verdetto="omit", decided_by="human")
    await _risposta(db_session, voci["pollo"], "dolce", verdetto="irreplaceable", decided_by="human")
    await _risposta(db_session, voci["tacchino"], "dolce", verdetto="omit")

    await merge_ingredients(db_session, voci["tacchino"], voci["pollo"])

    assert await _risposte(db_session, voci["pollo"]) == {
        ("salato", None, "omit", "human", ()),
        ("dolce", None, "irreplaceable", "human", ()),
    }


async def test_a_parita_resta_la_voce_del_vincitore(db_session, voci):
    await _risposta(db_session, voci["pollo"], "salato", verdetto="omit")
    await _risposta(db_session, voci["tacchino"], "salato", verdetto="irreplaceable")

    await merge_ingredients(db_session, voci["tacchino"], voci["pollo"])

    assert await _risposte(db_session, voci["pollo"]) == {("salato", None, "omit", "ai", ())}


async def test_una_voce_che_risponde_batte_una_rimasta_vuota(db_session, voci):
    """La voce del vincitore, scritta a mano, ha perso il suo unico sostituto: non dice più
    niente, e quella dell'AI del perdente prende il suo posto."""
    await _risposta(db_session, voci["pollo"], "salato", sostituti=[voci["agnello"]], decided_by="human")
    await db_session.execute(delete(Ingredient).where(Ingredient.id == voci["agnello"]))
    await _risposta(db_session, voci["tacchino"], "salato", verdetto="omit")

    await merge_ingredients(db_session, voci["tacchino"], voci["pollo"])

    assert await _risposte(db_session, voci["pollo"]) == {("salato", None, "omit", "ai", ())}


async def test_dove_il_perdente_era_un_sostituto_c_e_il_vincitore(db_session, voci):
    await _risposta(db_session, voci["coniglio"], "salato", sostituti=[voci["tacchino"], voci["manzo"]])
    # il vincitore c'è già: il perdente non diventa un doppione
    await _risposta(db_session, voci["manzo"], "salato", sostituti=[voci["pollo"], voci["tacchino"]])
    # il vincitore non diventa sostituto di sé stesso, e la risposta rimasta vuota se ne va
    await _risposta(db_session, voci["pollo"], "salato", sostituti=[voci["tacchino"]])

    await merge_ingredients(db_session, voci["tacchino"], voci["pollo"])

    assert await _risposte(db_session, voci["coniglio"]) == {
        ("salato", None, "substitutes", "ai", ("pollo", "manzo")),
    }
    assert await _risposte(db_session, voci["manzo"]) == {
        ("salato", None, "substitutes", "ai", ("pollo",)),
    }
    assert await _risposte(db_session, voci["pollo"]) == set()


async def test_le_risposte_del_perdente_non_propongono_il_vincitore(db_session, voci):
    await _risposta(db_session, voci["tacchino"], "salato", sostituti=[voci["pollo"], voci["coniglio"]])
    await _risposta(db_session, voci["tacchino"], "dolce", sostituti=[voci["pollo"]])

    await merge_ingredients(db_session, voci["tacchino"], voci["pollo"])

    assert await _risposte(db_session, voci["pollo"]) == {
        ("salato", None, "substitutes", "ai", ("coniglio",)),
    }


async def test_una_correzione_di_ricetta_segue_la_riga(db_session, voci):
    spezzatino = await _ricetta(db_session, "Spezzatino", voci["tacchino"])
    misto = await _ricetta(db_session, "Misto", voci["pollo"], voci["tacchino"])
    await _risposta(db_session, voci["tacchino"], ricetta=spezzatino, verdetto="omit", decided_by="human")
    await _risposta(db_session, voci["pollo"], ricetta=misto, verdetto="irreplaceable", decided_by="human")
    await _risposta(db_session, voci["tacchino"], ricetta=misto, verdetto="omit", decided_by="human")

    await merge_ingredients(db_session, voci["tacchino"], voci["pollo"])

    assert await _risposte(db_session, voci["pollo"]) == {
        (None, spezzatino, "omit", "human", ()),
        (None, misto, "irreplaceable", "human", ()),
    }


async def test_l_anteprima_non_sposta_niente(db_session, voci):
    await _risposta(db_session, voci["tacchino"], "salato", verdetto="omit")
    await _risposta(db_session, voci["coniglio"], "salato", sostituti=[voci["tacchino"]])

    await preview_merge(db_session, voci["tacchino"], voci["pollo"])

    assert await _risposte(db_session, voci["tacchino"]) == {("salato", None, "omit", "ai", ())}
    assert await _risposte(db_session, voci["coniglio"]) == {
        ("salato", None, "substitutes", "ai", ("tacchino",)),
    }
    assert await _risposte(db_session, voci["pollo"]) == set()
```

- [ ] **Step 2: Falliscono**

Run: il comando di pytest con `tests/services/test_registry_merge_substitutes.py`.
Expected: FAIL. Senza `move_substitutions`, le righe del perdente spariscono con lui (`CASCADE`) o restano a puntare a lui fino alla cancellazione: le asserzioni sui sostituti del vincitore falliscono; `test_l_anteprima_non_sposta_niente` può già passare.

- [ ] **Step 3: `move_substitutions`**

In `backend/app/repositories/substitutions.py`:

1. `from sqlalchemy import delete, func, select` diventa `from sqlalchemy import delete, func, or_, select, update`.
2. In fondo al file aggiungi:

```python
async def _rows_of(session: AsyncSession, ingredient_id: uuid.UUID) -> list[IngredientSubstitution]:
    statement = select(IngredientSubstitution).where(
        IngredientSubstitution.ingredient_id == ingredient_id
    )
    return list((await session.execute(_loaded(statement))).scalars())


def _rank(row: IngredientSubstitution) -> tuple[bool, bool]:
    # prima chi risponde, poi chi è scritto a mano; a parità resta il vincitore
    return (is_answered(row), row.decided_by == DecidedBy.HUMAN)


async def move_substitutions(
    session: AsyncSession, loser_id: uuid.UUID, winner_id: uuid.UUID
) -> None:
    """La metà di `merge_ingredients` che riguarda i sostituti (R5).

    Va chiamata prima che il perdente sparisca: le chiavi esterne sono in CASCADE, e
    cancellato lui le sue risposte se ne andrebbero con lui. Quattro passi:

    1. dove il perdente è un sostituto, va il vincitore — tolto prima dove il vincitore
       c'è già, o dove la risposta è proprio del vincitore (sarebbe sostituto di sé);
    2. le risposte del perdente non possono proporre il vincitore: dopo la fusione
       sarebbe un sostituto di sé stesso;
    3. le risposte del perdente passano al vincitore: una voce generale vince su quella
       del vincitore solo se risponde dove l'altra no, o è scritta a mano dove l'altra è
       dell'AI (`_rank`); una correzione di ricetta passa se la ricetta non ne ha già una
       per il vincitore;
    4. una risposta «sostituti» rimasta senza sostituti non dice più niente, e si toglie.
    """
    rows_of_winner = select(IngredientSubstitution.id).where(
        IngredientSubstitution.ingredient_id == winner_id
    )
    rows_of_loser = select(IngredientSubstitution.id).where(
        IngredientSubstitution.ingredient_id == loser_id
    )
    listing_winner = select(SubstitutionOption.substitution_id).where(
        SubstitutionOption.substitute_id == winner_id
    )
    await session.execute(
        delete(SubstitutionOption).where(
            SubstitutionOption.substitute_id == loser_id,
            or_(
                SubstitutionOption.substitution_id.in_(rows_of_winner),
                SubstitutionOption.substitution_id.in_(listing_winner),
            ),
        )
    )
    await session.execute(
        update(SubstitutionOption)
        .where(SubstitutionOption.substitute_id == loser_id)
        .values(substitute_id=winner_id)
    )
    await session.execute(
        delete(SubstitutionOption).where(
            SubstitutionOption.substitute_id == winner_id,
            SubstitutionOption.substitution_id.in_(rows_of_loser),
        )
    )

    winner_rows = await _rows_of(session, winner_id)
    general = {row.context: row for row in winner_rows if row.recipe_id is None}
    overridden = {row.recipe_id for row in winner_rows if row.recipe_id is not None}
    for row in await _rows_of(session, loser_id):
        if row.recipe_id is None:
            rival = general.get(row.context)
            if rival is not None:
                if _rank(rival) >= _rank(row):
                    await session.execute(
                        delete(IngredientSubstitution).where(IngredientSubstitution.id == row.id)
                    )
                    continue
                await session.execute(
                    delete(IngredientSubstitution).where(IngredientSubstitution.id == rival.id)
                )
        elif row.recipe_id in overridden:
            await session.execute(
                delete(IngredientSubstitution).where(IngredientSubstitution.id == row.id)
            )
            continue
        await session.execute(
            update(IngredientSubstitution)
            .where(IngredientSubstitution.id == row.id)
            .values(ingredient_id=winner_id)
        )

    await session.execute(
        delete(IngredientSubstitution).where(
            IngredientSubstitution.verdict == SubstitutionVerdict.SUBSTITUTES.value,
            ~select(SubstitutionOption.id)
            .where(SubstitutionOption.substitution_id == IngredientSubstitution.id)
            .exists(),
        )
    )
    await session.flush()
```

- [ ] **Step 4: La chiamata in `merge_ingredients`**

In `backend/app/services/registry.py` (leggilo com'è sul ramo):

1. Dopo `from app.repositories.products import find_by_barcode` aggiungi:
   ```python
   from app.repositories.substitutions import move_substitutions
   ```
2. In `merge_ingredients`, subito **prima** della riga
   ```python
       await session.execute(delete(IngredientAlias).where(IngredientAlias.ingredient_id == loser_id))
   ```
   aggiungi:
   ```python
       # I sostituti (R5): le voci, le correzioni di ricetta e i posti da sostituto del
       # perdente passano al vincitore — prima che il perdente sparisca, e le sue righe
       # (CASCADE) con lui. Dopo le righe di ricetta: una correzione segue la sua riga.
       await move_substitutions(session, loser_id, winner.id)
   ```

- [ ] **Step 5: Passano, con le fusioni di prima**

Run: il comando di pytest con `tests/services/test_registry_merge_substitutes.py tests/services/test_registry_merge.py tests/services/test_registry.py tests/api/test_registry_ingredients.py`.
Expected: PASS (8 test nuovi; quelli di prima invariati).

- [ ] **Step 6: Commit**

```bash
git add backend/app/repositories/substitutions.py backend/app/services/registry.py backend/tests/services/test_registry_merge_substitutes.py
git commit -m "feat(registry): R5, la fusione sposta i sostituti sul vincitore"
```

---

### Task 6: L'AI decide i sostituti — la domanda, la verifica, i lotti, la voce sul momento

**Files:**
- Modify: `backend/app/services/llm.py` (`LlmCallSite`)
- Create: `backend/app/services/substitutions.py`
- Test: `backend/tests/services/test_substitutions_ai.py`

**Interfaces:**
- Consumes: Task 1; Task 3 (`Answer`, `general_row`, `is_answered`, `store_ai_answer`); Task 4 (`Voice`, `pending_voices`); `complete_json`, `build_headers`, `open_client`, `LlmUnavailable`, `LlmUsage` (`app.services.llm`); `record_llm_call` (`app.repositories.llm_calls`); `USAGE_FINTO`, `COSTO_FINTO` (`backend/tests/llm_fakes.py`).
- Produces:
  - `LlmCallSite.INGREDIENT_SUBSTITUTES = "ingredient_substitutes"`;
  - in `app.services.substitutions`: `SUBSTITUTE_BATCH = 20`, `SUBSTITUTE_MAX_TOKENS = 400`, `AI_VERDICTS: dict[str, SubstitutionVerdict]`, `CONTEXT_WORDS: dict[SubstitutionContext, str]`, `SUBSTITUTE_SYSTEM_PROMPT: str`, `SUBSTITUTE_SCHEMA: dict`, `@dataclass(frozen=True) class Rejected(reason: str)`, `verify_answer(data: dict, ingredient_id: uuid.UUID, food: Mapping[str, uuid.UUID]) -> Answer | Rejected`, `async load_food(session) -> dict[str, uuid.UUID]` (nome in minuscolo → id, solo alimenti, per nome), `question(name: str, context: SubstitutionContext, food: Mapping[str, uuid.UUID]) -> str`, `describe(outcome: Answer | Rejected, names: Mapping[uuid.UUID, str]) -> str`, `@dataclass(frozen=True) class PairOutcome(stored: bool = False, failed: bool = False)`, `async decide_pair(session, ingredient_id: uuid.UUID, context: SubstitutionContext, client: httpx.AsyncClient | None = None) -> PairOutcome`, `@dataclass(frozen=True) class SubstitutionRun(substitutes: int = 0, omit: int = 0, irreplaceable: int = 0, rejected: int = 0, calls: int = 0, cost_usd: float | None = None, pending: int = 0, unavailable: str | None = None)` con la proprietà `stored`, `async decide_substitutions(session, client=None, limit: int | None = None, batch_size: int = SUBSTITUTE_BATCH, after_batch: Callable[[], Awaitable[None]] | None = None, report: Callable[[str], None] | None = None) -> SubstitutionRun`, `async measured_cost(session) -> tuple[int, float | None]`. Nessuna funzione fa commit (`after_batch` sì, se il chiamante gli passa `session.commit`).
  - Il Task 7 usa `decide_substitutions`, `measured_cost`, `pending_voices`; il Task 8 `decide_pair`; i test di rotta sostituiscono `app.services.substitutions.open_client`.

- [ ] **Step 1: I test che falliscono**

Crea `backend/tests/services/test_substitutions_ai.py`:

```python
"""I sostituti decisi dall'AI (R5), e la verifica della sua risposta.

Come per i termini dell'import, la parte che conta è la verifica: una risposta che non
si può controllare non si applica (decisione 2 di Mattia), e la voce resta da chiedere.
L'AI scrive solo dove non c'è una risposta (decisione 4).

Il finto sostituisce `httpx.AsyncClient`, non il client di OpenRouter: sotto prova c'è
`complete_json` per intero. Risponde guardando la domanda e non l'ordine d'arrivo,
perché le chiamate di un lotto partono insieme (lo stesso motivo di `ScriptedLlm`).
"""

import json as _json
import uuid

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.llm_call import LlmCall
from app.db.models.recipe import RecipeSource
from app.domain.substitutions import SubstitutionContext, SubstitutionVerdict
from app.repositories import substitutions as repo
from app.repositories.recipes import create_recipe
from app.repositories.substitutions import Answer
from app.services.substitutions import (
    SUBSTITUTE_SCHEMA,
    PairOutcome,
    Rejected,
    SubstitutionRun,
    decide_pair,
    decide_substitutions,
    verify_answer,
)
from llm_fakes import COSTO_FINTO, USAGE_FINTO

SALATO = SubstitutionContext.SAVORY
DOLCE = SubstitutionContext.SWEET


@pytest.fixture(autouse=True)
def chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


class SostitutiFinti:
    """Una risposta per (ingrediente, ricetta), scelta guardando la domanda.

    `prima`, se c'è, gira prima di rispondere: è il modo di far scrivere qualcuno mentre
    il modello «pensa». Un'`Exception` fra le risposte si solleva invece di rispondere.
    """

    def __init__(self, risposte: dict[tuple[str, str], object], prima=None) -> None:
        self._risposte = risposte
        self._prima = prima
        self.bodies: list[dict] = []

    async def post(self, url, json, headers):  # noqa: A002
        self.bodies.append(json)
        if self._prima is not None:
            await self._prima()
        domanda = _json.loads(json["messages"][1]["content"])
        payload = self._risposte[(domanda["ingrediente"], domanda["ricetta"])]
        if isinstance(payload, Exception):
            raise payload
        corpo = {
            "id": "gen-finta",
            "model": "google/gemma-4-26b-a4b-it",
            "choices": [{"message": {"content": _json.dumps(payload)}}],
            "usage": dict(USAGE_FINTO),
        }
        return httpx.Response(200, json=corpo, request=httpx.Request("POST", url))

    async def aclose(self):
        return None

    def domande(self) -> list[tuple[str, str]]:
        return sorted(
            (domanda["ingrediente"], domanda["ricetta"])
            for domanda in (_json.loads(corpo["messages"][1]["content"]) for corpo in self.bodies)
        )


def sostituti(*righe: tuple[str, str]) -> dict:
    return {"esito": "sostituti", "sostituti": [{"nome": nome, "nota": nota} for nome, nota in righe]}


OMETTERE = {"esito": "omettere", "sostituti": []}
INSOSTITUIBILE = {"esito": "insostituibile", "sostituti": []}


@pytest_asyncio.fixture
async def cucina(db_session):
    """Quattro voci: pollo salato (2 ricette), burro dolce, burro salato, zucchero dolce."""

    def voce(nome: str, reparto: str) -> Ingredient:
        return Ingredient(name=nome, display_name=nome.capitalize(), category=reparto)

    voci = {
        "pollo": voce("pollo", IngredientCategory.CARNE),
        "tacchino": voce("tacchino", IngredientCategory.CARNE),
        "coniglio": voce("coniglio", IngredientCategory.CARNE),
        "burro": voce("burro", IngredientCategory.LATTICINI),
        "margarina": voce("margarina", IngredientCategory.CONDIMENTI),
        "zucchero": voce("zucchero", IngredientCategory.DOLCI),
        "detersivo": voce("detersivo", IngredientCategory.CASA),
    }
    db_session.add_all(voci.values())
    await db_session.flush()
    for titolo, categoria, nomi in (
        ("Pollo al burro", "Secondi piatti", ("pollo", "burro")),
        ("Pollo arrosto", "Secondi piatti", ("pollo",)),
        ("Biscotti", "Dolci e Desserts", ("burro", "zucchero")),
    ):
        await create_recipe(
            db_session, title=titolo, description=None, instructions="Cuoci.", servings=2,
            source=RecipeSource.MANUAL, source_ref=None,
            ingredients=[(voci[nome].id, "primary", None, None) for nome in nomi],
            embedding=None, category=categoria,
        )
    return voci


TUTTE = {
    ("pollo", "salata"): sostituti(("tacchino", "metà dose"), ("coniglio", "")),
    ("burro", "dolce"): sostituti(("margarina", "")),
    ("burro", "salata"): OMETTERE,
    ("zucchero", "dolce"): INSOSTITUIBILE,
}


async def _spese(db_session) -> list[bool]:
    righe = await db_session.execute(
        select(LlmCall.ok).where(LlmCall.call_site == "ingredient_substitutes")
    )
    return sorted(righe.scalars().all())


# --- la verifica, pura ------------------------------------------------------------------

P, T, C, B = (uuid.uuid4() for _ in range(4))
CIBO = {"burro": B, "coniglio": C, "pollo": P, "tacchino": T}


def test_una_risposta_giusta_si_applica_con_le_note_pulite():
    risposta = verify_answer(sostituti(("Tacchino ", " metà  dose "), ("coniglio", "")), P, CIBO)
    assert risposta == Answer(SubstitutionVerdict.SUBSTITUTES, ((T, "metà dose"), (C, None)))


def test_maiuscole_e_spazi_non_contano_ma_un_doppione_si():
    """Review Focus 4: «Tacchino » è tacchino, e «TACCHINO» dopo «tacchino» è un doppione."""
    assert isinstance(verify_answer(sostituti(("tacchino", ""), ("TACCHINO ", "")), P, CIBO), Rejected)


@pytest.mark.parametrize(
    "risposta",
    [
        {"esito": "forse", "sostituti": []},
        {"esito": "sostituti", "sostituti": "tacchino"},
        {"esito": "omettere", "sostituti": [{"nome": "tacchino", "nota": ""}]},
        {"esito": "sostituti", "sostituti": []},
        sostituti(("tacchino", ""), ("coniglio", ""), ("burro", ""), ("pollo", "")),
        {"esito": "sostituti", "sostituti": ["tacchino"]},
        sostituti(("seitan", "")),        # fuori anagrafica
        sostituti(("detersivo", "")),     # non alimentare: non è fra il cibo
        sostituti(("pollo", "")),         # l'ingrediente stesso
        sostituti(("tacchino", "x" * 61)),
    ],
)
def test_una_risposta_che_non_si_verifica_si_scarta_intera(risposta):
    assert isinstance(verify_answer(risposta, P, CIBO), Rejected)


def test_omettere_e_insostituibile_si_applicano():
    assert verify_answer(OMETTERE, P, CIBO) == Answer(SubstitutionVerdict.OMIT)
    assert verify_answer(INSOSTITUIBILE, P, CIBO) == Answer(SubstitutionVerdict.IRREPLACEABLE)


# --- il giro del comando ---------------------------------------------------------------


async def test_applica_le_risposte_verificate_e_registra_la_spesa(db_session, cucina):
    righe: list[str] = []

    esito = await decide_substitutions(db_session, client=SostitutiFinti(TUTTE), report=righe.append)

    assert (esito.substitutes, esito.omit, esito.irreplaceable, esito.rejected) == (2, 1, 1, 0)
    assert (esito.calls, esito.pending, esito.unavailable) == (4, 0, None)
    assert esito.cost_usd == pytest.approx(4 * COSTO_FINTO)
    pollo = await repo.general_row(db_session, cucina["pollo"].id, SALATO)
    assert pollo.decided_by == "ai"
    assert [(o.substitute.name, o.note) for o in repo.visible_options(pollo)] == [
        ("tacchino", "metà dose"), ("coniglio", None),
    ]
    assert await _spese(db_session) == [True, True, True, True]
    assert "pollo (salato): tacchino (metà dose), coniglio" in righe
    assert "burro (salato): si può omettere" in righe
    assert "zucchero (dolce): insostituibile" in righe


async def test_una_risposta_che_non_si_verifica_lascia_la_voce_scoperta(db_session, cucina):
    risposte = {**TUTTE, ("pollo", "salata"): sostituti(("seitan", ""))}
    righe: list[str] = []

    esito = await decide_substitutions(db_session, client=SostitutiFinti(risposte), report=righe.append)

    assert (esito.rejected, esito.pending) == (1, 1)
    assert await repo.general_row(db_session, cucina["pollo"].id, SALATO) is None
    assert "pollo (salato): scartata («seitan» non è un alimento dell'anagrafica)" in righe


async def test_chiede_solo_le_voci_scoperte(db_session, cucina):
    await repo.write_general(db_session, cucina["pollo"].id, SALATO, Answer(SubstitutionVerdict.OMIT))
    await repo.store_ai_answer(
        db_session, cucina["burro"].id, DOLCE, Answer(SubstitutionVerdict.IRREPLACEABLE)
    )
    finto = SostitutiFinti(TUTTE)

    await decide_substitutions(db_session, client=finto)

    assert finto.domande() == [("burro", "salata"), ("zucchero", "dolce")]
    di_nuovo = SostitutiFinti({})
    assert await decide_substitutions(db_session, client=di_nuovo) == SubstitutionRun()
    assert di_nuovo.bodies == []


async def test_una_correzione_a_mano_fatta_mentre_l_ai_risponde_non_si_riscrive(db_session, cucina):
    """Review Focus 3: il comando gira minuti, e Mattia corregge in Anagrafica."""

    async def mano():
        await repo.write_general(
            db_session, cucina["pollo"].id, SALATO, Answer(SubstitutionVerdict.IRREPLACEABLE)
        )

    righe: list[str] = []
    esito = await decide_substitutions(
        db_session, client=SostitutiFinti(TUTTE, prima=mano), limit=1, report=righe.append
    )

    assert esito.substitutes == 0
    riga = await repo.general_row(db_session, cucina["pollo"].id, SALATO)
    assert (riga.verdict, riga.decided_by) == ("irreplaceable", "human")
    assert righe == ["pollo (salato): già decisa, lasciata com'era"]


async def test_va_a_lotti_e_dopo_ogni_lotto_chiama_after_batch(db_session, cucina):
    finto = SostitutiFinti(TUTTE)
    giri: list[int] = []

    async def dopo():
        giri.append(len(finto.bodies))

    esito = await decide_substitutions(db_session, client=finto, batch_size=2, after_batch=dopo)

    assert giri == [2, 4]
    assert esito.pending == 0


async def test_limit_chiede_le_voci_piu_usate(db_session, cucina):
    finto = SostitutiFinti(TUTTE)

    esito = await decide_substitutions(db_session, client=finto, limit=2)

    # pollo salato (2 ricette) e, a parità, il primo per nome: burro dolce
    assert finto.domande() == [("burro", "dolce"), ("pollo", "salata")]
    assert esito.pending == 2


async def test_il_primo_lotto_con_un_guasto_ferma_il_giro(db_session, cucina):
    risposte = {**TUTTE, ("pollo", "salata"): httpx.ConnectError("rete giù")}
    finto = SostitutiFinti(risposte)

    esito = await decide_substitutions(db_session, client=finto, batch_size=2)

    assert len(finto.bodies) == 2  # il secondo lotto non parte
    assert esito.unavailable is not None and "rete giù" in esito.unavailable
    assert (esito.substitutes, esito.calls, esito.pending) == (1, 2, 3)
    assert await _spese(db_session) == [False, True]


async def test_senza_chiave_non_chiama_e_non_registra(db_session, cucina, monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    finto = SostitutiFinti(TUTTE)

    esito = await decide_substitutions(db_session, client=finto)

    assert finto.bodies == []
    assert esito.unavailable is not None and "OPENROUTER_API_KEY" in esito.unavailable
    assert esito.pending == 4
    assert await _spese(db_session) == []


async def test_la_domanda_porta_l_ingrediente_il_contesto_e_il_cibo_dell_anagrafica(db_session, cucina):
    finto = SostitutiFinti(TUTTE)

    await decide_substitutions(db_session, client=finto, limit=1)

    corpo = finto.bodies[0]
    assert _json.loads(corpo["messages"][1]["content"]) == {
        "ingrediente": "pollo",
        "ricetta": "salata",
        # solo il cibo, per nome, senza l'ingrediente stesso
        "anagrafica": ["burro", "coniglio", "margarina", "tacchino", "zucchero"],
    }
    assert "insostituibile" in corpo["messages"][0]["content"]
    assert corpo["response_format"]["json_schema"]["schema"] == SUBSTITUTE_SCHEMA


# --- la voce sul momento ---------------------------------------------------------------


async def test_una_voce_sul_momento_si_salva(db_session, cucina):
    finto = SostitutiFinti({("pollo", "salata"): OMETTERE})

    esito = await decide_pair(db_session, cucina["pollo"].id, SALATO, client=finto)

    assert esito == PairOutcome(stored=True, failed=False)
    riga = await repo.general_row(db_session, cucina["pollo"].id, SALATO)
    assert (riga.verdict, riga.decided_by) == ("omit", "ai")
    assert await _spese(db_session) == [True]


async def test_una_voce_che_ha_gia_una_risposta_non_chiama(db_session, cucina):
    await repo.write_general(db_session, cucina["pollo"].id, SALATO, Answer(SubstitutionVerdict.OMIT))
    finto = SostitutiFinti({})

    assert await decide_pair(db_session, cucina["pollo"].id, SALATO, client=finto) == PairOutcome()
    assert finto.bodies == []


async def test_l_ai_giu_sul_momento_lo_dice_e_registra_la_chiamata(db_session, cucina):
    finto = SostitutiFinti({("pollo", "salata"): httpx.ConnectError("rete giù")})

    assert await decide_pair(db_session, cucina["pollo"].id, SALATO, client=finto) == PairOutcome(failed=True)
    assert await repo.general_row(db_session, cucina["pollo"].id, SALATO) is None
    assert await _spese(db_session) == [False]


async def test_una_risposta_scartata_sul_momento_lo_dice(db_session, cucina):
    finto = SostitutiFinti({("pollo", "salata"): sostituti(("pollo", ""))})

    assert await decide_pair(db_session, cucina["pollo"].id, SALATO, client=finto) == PairOutcome(failed=True)
    assert await repo.general_row(db_session, cucina["pollo"].id, SALATO) is None
    assert await _spese(db_session) == [True]  # pagata anche se inutile


async def test_senza_chiave_sul_momento_non_chiama(db_session, cucina, monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    finto = SostitutiFinti({})

    assert await decide_pair(db_session, cucina["pollo"].id, SALATO, client=finto) == PairOutcome(failed=True)
    assert finto.bodies == [] and await _spese(db_session) == []
```

- [ ] **Step 2: Falliscono**

Run: il comando di pytest con `tests/services/test_substitutions_ai.py`.
Expected: FAIL, `ModuleNotFoundError: No module named 'app.services.substitutions'`.

- [ ] **Step 3: La sezione della spesa**

In `backend/app/services/llm.py`, in `class LlmCallSite(StrEnum)`, dopo `UNIT_FORMS = "unit_forms"` (sul ramo è l'ultima voce; se ce ne fossero altre dopo, mettila in fondo) aggiungi:

```python
    INGREDIENT_SUBSTITUTES = "ingredient_substitutes"
```

- [ ] **Step 4: Il servizio**

Crea `backend/app/services/substitutions.py`:

```python
"""L'AI che decide i sostituti di un ingrediente (R5), e la verifica della sua risposta.

Due strade, un solo modo di chiedere e di verificare:

- `decide_substitutions`, per `python -m app.cli.decide_substitutes`: tutte le voci
  scoperte (`pending_voices`), dalla più usata, a lotti di `SUBSTITUTE_BATCH` con le
  chiamate del lotto in parallelo, e `after_batch` (il commit) dopo ogni lotto;
- `decide_pair`, per «Sostituisci» su una voce che non ha ancora una risposta: una
  chiamata, sul momento.

Una chiamata per voce e non un lotto per chiamata, per la ragione scritta in testa a
`recipe_import/decide.py`: un modello piccolo che deve riecheggiare venti nomi in un
array si sfalda, e il degrado non si vede. L'anagrafica alimentare intera sta nel
prompt, perché un sostituto si sceglie solo lì (decisione 2 di Mattia): ~0,0004 $ a
chiamata, misurato su `term_decision`, che porta lo stesso elenco.

Una risposta che non si può verificare non si applica (decisione 2): un nome fuori
anagrafica o non alimentare, l'ingrediente stesso, un doppione, più di tre sostituti,
una nota troppo lunga, un esito che non torna. **Un solo difetto scarta la risposta
intera**: la voce resta scoperta, e il giro dopo la richiede. L'AI scrive solo dove non
c'è una risposta (`store_ai_answer`): una correzione a mano non si riscrive mai
(decisione 4).
"""

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.ingredient import Ingredient
from app.db.models.llm_call import LlmCall
from app.domain.rules import IngredientKind
from app.domain.substitutions import (
    SUBSTITUTE_NOTE_MAX,
    SUBSTITUTES_MAX,
    SubstitutionContext,
    SubstitutionVerdict,
    clean_note,
)
from app.repositories.llm_calls import record_llm_call
from app.repositories.substitutions import (
    Answer,
    Voice,
    general_row,
    is_answered,
    pending_voices,
    store_ai_answer,
)
from app.services.llm import (
    LlmCallSite,
    LlmUnavailable,
    LlmUsage,
    build_headers,
    complete_json,
    open_client,
)

# Venti voci per lotto: il commit dopo ogni lotto non butta il lavoro fatto se il quinto
# lotto si rompe, e venti chiamate insieme stanno sotto `LLM_MAX_CONCURRENCY` (8) a giri.
SUBSTITUTE_BATCH = 20
# Una risposta è al più tre nomi con tre note: un centinaio di token. Il resto è spazio
# per divagare, che lo schema non lascia usare.
SUBSTITUTE_MAX_TOKENS = 400

# Le parole dell'esito nella risposta del modello, in italiano come il prompt, verso il
# vocabolario del dominio
AI_VERDICTS: dict[str, SubstitutionVerdict] = {
    "sostituti": SubstitutionVerdict.SUBSTITUTES,
    "omettere": SubstitutionVerdict.OMIT,
    "insostituibile": SubstitutionVerdict.IRREPLACEABLE,
}

# «la ricetta è dolce / salata»: il contesto come lo legge il modello
CONTEXT_WORDS: dict[SubstitutionContext, str] = {
    SubstitutionContext.SAVORY: "salata",
    SubstitutionContext.SWEET: "dolce",
}

SUBSTITUTE_SYSTEM_PROMPT = """Sei un aiuto in cucina. Ricevi un ingrediente, se la ricetta in cui compare è dolce o salata, e l'elenco degli ingredienti alimentari di un'app di dispensa. Di' cosa può fare chi non ce l'ha in casa, scegliendo UN esito.

- "sostituti": da 1 a 3 ingredienti dell'elenco che lo sostituiscono bene in una ricetta di quel tipo, dal migliore, scritti identici a come compaiono nell'elenco. Per ognuno, in "nota", poche parole solo se servono per usarlo al suo posto ("metà dose", "sciolto in acqua"), altrimenti una stringa vuota.
- "omettere": nessun ingrediente dell'elenco lo sostituisce, ma il piatto riesce anche senza: una spezia, un'erba, una guarnizione.
- "insostituibile": senza di lui il piatto non si fa, come la farina nel pane.

Regole:
- Solo nomi dell'elenco, mai l'ingrediente stesso, mai lo stesso nome due volte.
- Con "omettere" e "insostituibile", "sostituti" è una lista vuota.
- Preferisci ingredienti comuni, che si trovano in una dispensa di casa.
- Non inserire valori nutrizionali, calorie o macronutrienti.
"""

# Vincolo dello strict mode: ogni proprietà in `required`, `additionalProperties` falso.
# Il numero dei sostituti non sta nello schema (`maxItems` non lo onorano tutti i
# provider): lo dice il prompt e lo controlla `verify_answer`.
SUBSTITUTE_SCHEMA = {
    "type": "object",
    "properties": {
        "esito": {"type": "string", "enum": list(AI_VERDICTS)},
        "sostituti": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"nome": {"type": "string"}, "nota": {"type": "string"}},
                "required": ["nome", "nota"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["esito", "sostituti"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class Rejected:
    """Una risposta che non si applica, e perché (il comando lo stampa)."""

    reason: str


def verify_answer(
    data: dict, ingredient_id: uuid.UUID, food: Mapping[str, uuid.UUID]
) -> Answer | Rejected:
    """La risposta del modello, verificata contro l'anagrafica alimentare (`food`).

    Uno schema rispettato non è una risposta verificata: si ricontrolla tutto qui.
    """
    raw_verdict = data.get("esito")
    verdict = AI_VERDICTS.get(raw_verdict) if isinstance(raw_verdict, str) else None
    if verdict is None:
        return Rejected("esito sconosciuto")
    raw = data.get("sostituti")
    if not isinstance(raw, list):
        return Rejected("«sostituti» non è una lista")
    if verdict is not SubstitutionVerdict.SUBSTITUTES:
        return Answer(verdict) if not raw else Rejected("sostituti con un esito che non ne vuole")
    if not raw:
        return Rejected("nessun sostituto")
    if len(raw) > SUBSTITUTES_MAX:
        return Rejected("più di tre sostituti")
    seen: set[uuid.UUID] = set()
    chosen: list[tuple[uuid.UUID, str | None]] = []
    for item in raw:
        if not isinstance(item, dict):
            return Rejected("un sostituto malformato")
        name = str(item.get("nome") or "").strip().casefold()
        substitute_id = food.get(name)
        if substitute_id is None:
            return Rejected(f"«{name}» non è un alimento dell'anagrafica")
        if substitute_id == ingredient_id:
            return Rejected("l'ingrediente stesso")
        if substitute_id in seen:
            return Rejected(f"«{name}» due volte")
        seen.add(substitute_id)
        raw_note = item.get("nota")
        note = clean_note(raw_note if isinstance(raw_note, str) else None)
        if note is not None and len(note) > SUBSTITUTE_NOTE_MAX:
            return Rejected(f"la nota di «{name}» è troppo lunga")
        chosen.append((substitute_id, note))
    return Answer(verdict, tuple(chosen))


async def load_food(session: AsyncSession) -> dict[str, uuid.UUID]:
    """Il cibo dell'anagrafica, nome in minuscolo → id, per nome: l'offerta al modello e
    il controllo della risposta sono lo stesso elenco, e non si possono scollare."""
    rows = await session.execute(
        select(Ingredient.id, Ingredient.name)
        .where(Ingredient.kind == IngredientKind.FOOD)
        .order_by(Ingredient.name)
    )
    return {name.casefold(): ingredient_id for ingredient_id, name in rows.all()}


def question(name: str, context: SubstitutionContext, food: Mapping[str, uuid.UUID]) -> str:
    own = name.casefold()
    return json.dumps(
        {
            "ingrediente": name,
            "ricetta": CONTEXT_WORDS[context],
            # senza l'ingrediente stesso: un nome in meno da non scegliere
            "anagrafica": [candidate for candidate in food if candidate != own],
        },
        ensure_ascii=False,
    )


async def _ask(
    name: str,
    ingredient_id: uuid.UUID,
    context: SubstitutionContext,
    food: Mapping[str, uuid.UUID],
    client: object,
) -> tuple[Answer | Rejected, LlmUsage]:
    """Una voce, una chiamata. `LlmUnavailable` risale: chi chiama la registra."""
    esito = await complete_json(
        call_site=LlmCallSite.INGREDIENT_SUBSTITUTES,
        system=SUBSTITUTE_SYSTEM_PROMPT,
        user=question(name, context, food),
        schema=SUBSTITUTE_SCHEMA,
        schema_name="sostituti_ingrediente",
        max_tokens=SUBSTITUTE_MAX_TOKENS,
        client=client,
    )
    return verify_answer(esito.data, ingredient_id, food), esito.usage


def describe(outcome: Answer | Rejected, names: Mapping[uuid.UUID, str]) -> str:
    """Una risposta in una riga, per chi lancia il comando e guarda la qualità."""
    if isinstance(outcome, Rejected):
        return f"scartata ({outcome.reason})"
    if outcome.verdict is SubstitutionVerdict.OMIT:
        return "si può omettere"
    if outcome.verdict is SubstitutionVerdict.IRREPLACEABLE:
        return "insostituibile"
    return ", ".join(
        names.get(substitute_id, str(substitute_id)) + (f" ({note})" if note else "")
        for substitute_id, note in outcome.substitutes
    )


@dataclass(frozen=True)
class PairOutcome:
    stored: bool = False
    # l'AI non ha risposto, o ha risposto qualcosa che non si applica: a video
    # «Nessun suggerimento ancora», con la strada a mano
    failed: bool = False


async def decide_pair(
    session: AsyncSession,
    ingredient_id: uuid.UUID,
    context: SubstitutionContext,
    client: httpx.AsyncClient | None = None,
) -> PairOutcome:
    """La voce generale di un ingrediente in un contesto, chiesta sul momento se manca.

    Non chiama nessuno se la voce ha già una risposta, né senza chiave: una chiave che
    manca è la configurazione, non un guasto, e non si registra come spesa.
    """
    existing = await general_row(session, ingredient_id, context)
    if existing is not None and is_answered(existing):
        return PairOutcome()
    ingredient = await session.get(Ingredient, ingredient_id)
    if ingredient is None:
        raise LookupError(f"nessun ingrediente {ingredient_id}")
    try:
        build_headers()
    except LlmUnavailable:
        return PairOutcome(failed=True)
    food = await load_food(session)
    owned = client is None
    api = client if client is not None else open_client()
    try:
        verified, usage = await _ask(ingredient.name, ingredient.id, context, food, api)
    except LlmUnavailable:
        await record_llm_call(
            session, call_site=LlmCallSite.INGREDIENT_SUBSTITUTES, usage=LlmUsage(), ok=False
        )
        return PairOutcome(failed=True)
    finally:
        if owned:
            await api.aclose()
    await record_llm_call(
        session, call_site=LlmCallSite.INGREDIENT_SUBSTITUTES, usage=usage, ok=True
    )
    if isinstance(verified, Rejected):
        return PairOutcome(failed=True)
    return PairOutcome(stored=await store_ai_answer(session, ingredient.id, context, verified))


@dataclass(frozen=True)
class SubstitutionRun:
    """Quel che un lancio ha fatto, e quel che resta."""

    substitutes: int = 0  # voci salvate coi loro sostituti
    omit: int = 0  # voci salvate «si può omettere»
    irreplaceable: int = 0  # voci salvate «insostituibile»
    rejected: int = 0  # risposte che non si potevano verificare
    calls: int = 0
    # la somma dei costi dichiarati da OpenRouter; None se nessuno ne ha dichiarato uno
    # (zero direbbe «gratis», ed è un'affermazione: la regola dei nutrienti)
    cost_usd: float | None = None
    # le voci ancora scoperte alla fine: senza, «0 salvate» vorrebbe dire insieme «niente
    # da fare» e «è andato tutto storto»
    pending: int = 0
    unavailable: str | None = None

    @property
    def stored(self) -> int:
        return self.substitutes + self.omit + self.irreplaceable


async def decide_substitutions(
    session: AsyncSession,
    client: httpx.AsyncClient | None = None,
    limit: int | None = None,
    batch_size: int = SUBSTITUTE_BATCH,
    after_batch: Callable[[], Awaitable[None]] | None = None,
    report: Callable[[str], None] | None = None,
) -> SubstitutionRun:
    """Chiede all'AI le voci scoperte, dalla più usata, al più `limit`.

    Le domande di un lotto partono insieme sotto `LLM_MAX_CONCURRENCY`; le scritture si
    fanno dopo, in sequenza (il parallelo è sulla rete, non sul database). Dopo ogni lotto
    `after_batch` — il comando passa `session.commit`. Al primo lotto con un guasto
    dell'AI si ferma dopo averlo scritto: chiedere i lotti dopo sarebbe pagare per sapere
    che è ancora giù. `report` riceve una riga per voce («pollo (salato): tacchino»).
    """
    try:
        build_headers()
    except LlmUnavailable as exc:
        # senza chiave non si apre niente e non si registra niente: è la configurazione
        return SubstitutionRun(pending=len(await pending_voices(session)), unavailable=str(exc))
    voices = await pending_voices(session)
    if limit is not None:
        voices = voices[:limit]
    if not voices:
        return SubstitutionRun(pending=len(await pending_voices(session)))
    food = await load_food(session)
    names = {ingredient_id: name for name, ingredient_id in food.items()}
    # `max(1, …)`: a 0 il semaforo non si aprirebbe mai (lo stesso motivo di decide.py)
    semaphore = asyncio.Semaphore(max(1, get_settings().llm_max_concurrency))
    stored = {verdict: 0 for verdict in SubstitutionVerdict}
    rejected = calls = 0
    cost: float | None = None
    unavailable: str | None = None

    async def ask(voice: Voice, api: object):
        async with semaphore:
            try:
                verified, usage = await _ask(
                    voice.name, voice.ingredient_id, voice.context, food, api
                )
            except LlmUnavailable as exc:
                return None, LlmUsage(), str(exc)
            return verified, usage, None

    owned = client is None
    api = client if client is not None else open_client()
    try:
        for start in range(0, len(voices), batch_size):
            lot = voices[start : start + batch_size]
            answers = await asyncio.gather(*(ask(voice, api) for voice in lot))
            for voice, (verified, usage, error) in zip(lot, answers, strict=True):
                calls += 1
                # la spesa si scrive comunque: una chiamata inutile costa come una buona
                await record_llm_call(
                    session,
                    call_site=LlmCallSite.INGREDIENT_SUBSTITUTES,
                    usage=usage,
                    ok=error is None,
                )
                if usage.cost_usd is not None:
                    cost = (cost or 0.0) + usage.cost_usd
                if error is not None:
                    unavailable = error
                    text = f"non decisa ({error})"
                elif isinstance(verified, Rejected):
                    rejected += 1
                    text = describe(verified, names)
                elif await store_ai_answer(session, voice.ingredient_id, voice.context, verified):
                    stored[verified.verdict] += 1
                    text = describe(verified, names)
                else:
                    text = "già decisa, lasciata com'era"
                if report is not None:
                    report(f"{voice.name} ({voice.context.value}): {text}")
            await session.flush()
            if after_batch is not None:
                await after_batch()
            if unavailable is not None:
                break
    finally:
        if owned:
            await api.aclose()

    return SubstitutionRun(
        substitutes=stored[SubstitutionVerdict.SUBSTITUTES],
        omit=stored[SubstitutionVerdict.OMIT],
        irreplaceable=stored[SubstitutionVerdict.IRREPLACEABLE],
        rejected=rejected,
        calls=calls,
        cost_usd=cost,
        pending=len(await pending_voices(session)),
        unavailable=unavailable,
    )


async def measured_cost(session: AsyncSession) -> tuple[int, float | None]:
    """Quante chiamate riuscite hanno dichiarato un costo, e la loro media: la stima del
    `--dry-run` si fa su quel che è stato pagato davvero, non su un listino."""
    count, average = (
        await session.execute(
            select(func.count(LlmCall.cost_usd), func.avg(LlmCall.cost_usd)).where(
                LlmCall.call_site == LlmCallSite.INGREDIENT_SUBSTITUTES.value,
                LlmCall.ok.is_(True),
            )
        )
    ).one()
    return count, (float(average) if average is not None else None)
```

- [ ] **Step 5: Passano, e tutta la suite**

Run: il comando di pytest (tutta la suite).
Expected: tutto verde, con i 27 test nuovi di questo file (13 della verifica pura, 10 dei quali sono i parametri dei rifiuti; 9 del giro; 5 sul momento). Anche `test_llm_spend_is_recorded.py`, che ora trova `services/substitutions.py` fra i chiamanti dell'LLM e vi trova `record_llm_call`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/llm.py backend/app/services/substitutions.py backend/tests/services/test_substitutions_ai.py
git commit -m "feat(ai): R5, l'AI decide i sostituti — una voce per chiamata, solo risposte verificate, solo dove non c'è una risposta"
```

---

### Task 7: Il comando `decide_substitutes`

**Files:**
- Create: `backend/app/cli/decide_substitutes.py`
- Test: `backend/tests/test_decide_substitutes_cli.py`

**Interfaces:**
- Consumes: `pending_voices` (Task 4); `decide_substitutions`, `measured_cost` (Task 6); `SessionLocal` (`app.core.db`); `FakeLlm` (`llm_fakes.py`).
- Produces: `python -m app.cli.decide_substitutes [--dry-run] [--limit N]`, con `async def main(argv: list[str]) -> int` e `parse(argv: list[str]) -> tuple[bool, int | None] | str`. Il Task 13 lo lancia sullo stack e2e; Mattia in produzione.

- [ ] **Step 1: I test che falliscono**

Crea `backend/tests/test_decide_substitutes_cli.py`:

```python
"""Il comando che fa decidere all'AI i sostituti (R5): quel che dice a chi lo lancia.
Il lavoro vero lo provano i test del servizio, coi finti dell'LLM."""

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.cli.decide_substitutes import main
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.llm_call import LlmCall
from app.db.models.recipe import RecipeSource
from app.db.models.substitution import IngredientSubstitution
from app.repositories.recipes import create_recipe
from llm_fakes import FakeLlm


class _SessioneFinta:
    """`SessionLocal()` nel test: consegna la sessione della fixture invece di aprirne una
    vera, così `main()` gira contro la stessa transazione annullabile degli altri test.
    Stessa forma di `test_decide_units_cli.py`."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


@pytest_asyncio.fixture
async def due_voci(db_session, monkeypatch):
    """Pollo in un secondo (salato), burro in un dolce: due voci, una ricetta ciascuna."""
    pollo = Ingredient(name="pollo", display_name="Pollo", category=IngredientCategory.CARNE)
    burro = Ingredient(name="burro", display_name="Burro", category=IngredientCategory.LATTICINI)
    db_session.add_all([pollo, burro])
    await db_session.flush()
    for titolo, categoria, voce in (("Pollo arrosto", "Secondi piatti", pollo), ("Biscotti", "Dolci", burro)):
        await create_recipe(
            db_session, title=titolo, description=None, instructions="Cuoci.", servings=2,
            source=RecipeSource.MANUAL, source_ref=None,
            ingredients=[(voce.id, "primary", None, None)], embedding=None, category=categoria,
        )
    monkeypatch.setattr(
        "app.cli.decide_substitutes.SessionLocal", lambda: _SessioneFinta(db_session)
    )
    return {"pollo": pollo, "burro": burro}


@pytest.fixture
def senza_chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    yield
    get_settings.cache_clear()


@pytest.fixture
def con_chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


async def test_un_argomento_sconosciuto_esce_con_errore(capsys):
    assert await main(["--tutto"]) == 2
    assert "argomento sconosciuto: --tutto" in capsys.readouterr().out


@pytest.mark.parametrize("argv", [["--limit"], ["--limit", "0"], ["--limit", "due"], ["--limit", "-3"]])
async def test_limit_vuole_un_numero_maggiore_di_zero(argv, capsys):
    assert await main(argv) == 2
    assert "uso: --limit" in capsys.readouterr().out


async def test_dry_run_dice_cosa_chiederebbe_e_non_chiama_nessuno(
    db_session, due_voci, con_chiave, monkeypatch, capsys
):
    finto = FakeLlm()
    monkeypatch.setattr("app.services.substitutions.open_client", lambda: finto)

    assert await main(["--dry-run"]) == 0

    stampato = capsys.readouterr().out
    assert "2 voci senza sostituti: 1 nei piatti salati, 1 nei dolci." in stampato
    assert "ne chiederei 2, dalle più usate:" in stampato
    assert "- burro (dolce, 1 ricetta)" in stampato
    assert "nessun costo misurato ancora: lancia con --limit 20 per misurarlo." in stampato
    assert finto.bodies == []
    assert (await db_session.execute(select(LlmCall.id))).all() == []


async def test_dry_run_stima_con_il_costo_misurato(db_session, due_voci, capsys):
    db_session.add_all([
        LlmCall(call_site="ingredient_substitutes", ok=True, cost_usd=0.0004),
        LlmCall(call_site="ingredient_substitutes", ok=True, cost_usd=0.0006),
        # una fallita e una d'altra sezione non contano
        LlmCall(call_site="ingredient_substitutes", ok=False, cost_usd=None),
        LlmCall(call_site="term_decision", ok=True, cost_usd=0.1),
    ])
    await db_session.flush()

    assert await main(["--dry-run", "--limit", "1"]) == 0

    stampato = capsys.readouterr().out
    assert "ne chiederei 1, dalle più usate:" in stampato
    assert "costo medio misurato: 0.00050 $ a voce su 2 chiamate; stima per 1: 0.0005 $." in stampato


async def test_senza_chiave_lo_dice_e_non_scrive(db_session, due_voci, senza_chiave, capsys):
    assert await main([]) == 0

    righe = capsys.readouterr().out.strip().splitlines()
    assert righe[0].startswith("sostituti non disponibili (OPENROUTER_API_KEY")
    assert righe[-1] == "2 voci restano da decidere: rilancia questo comando."
    assert (await db_session.execute(select(IngredientSubstitution.id))).all() == []


async def test_con_l_ai_salva_stampa_e_dice_quanto_resta(db_session, due_voci, con_chiave, monkeypatch, capsys):
    finto = FakeLlm({"esito": "omettere", "sostituti": []})
    monkeypatch.setattr("app.services.substitutions.open_client", lambda: finto)

    assert await main(["--limit", "1"]) == 0

    righe = capsys.readouterr().out.strip().splitlines()
    # a parità di ricette, il primo per nome
    assert righe[0] == "burro (dolce): si può omettere"
    assert "1 voce salvata (0 con sostituti, 1 da omettere, 0 insostituibili), 0 risposte scartate." in righe
    assert "spesa di questo lancio: 0.00004 $ in 1 chiamata." in righe
    assert righe[-1] == "1 voce resta da decidere: rilancia questo comando."
    salvata = (await db_session.execute(select(IngredientSubstitution))).scalars().one()
    assert (salvata.ingredient_id, salvata.context, salvata.verdict, salvata.decided_by) == (
        due_voci["burro"].id, "dolce", "omit", "ai",
    )


async def test_senza_voci_l_ultima_riga_lo_dice(db_session, con_chiave, monkeypatch, capsys):
    monkeypatch.setattr(
        "app.cli.decide_substitutes.SessionLocal", lambda: _SessioneFinta(db_session)
    )
    assert await main([]) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] == "nessuna voce in attesa."
```

- [ ] **Step 2: Falliscono**

Run: il comando di pytest con `tests/test_decide_substitutes_cli.py`.
Expected: FAIL, `ModuleNotFoundError: No module named 'app.cli.decide_substitutes'`.

- [ ] **Step 3: Il comando**

Crea `backend/app/cli/decide_substitutes.py`:

```python
"""Fa decidere all'AI i sostituti degli ingredienti che non li hanno (R5).

    python -m app.cli.decide_substitutes --dry-run
    python -m app.cli.decide_substitutes --limit 20
    python -m app.cli.decide_substitutes

Una «voce» è un ingrediente in un contesto (dolce o salato) in cui compare in una
ricetta. Il comando chiede all'AI le voci che non hanno una risposta, dalla più usata,
una chiamata per voce, a lotti con un commit dopo ognuno: interrotto, rilanciato riprende
da quel che manca. Scrive solo dove non c'è una risposta: una correzione fatta in
Anagrafica non si tocca. Una voce che nessuno ha chiesto si calcola anche da sola, la
prima volta che qualcuno tocca «Sostituisci» su quell'ingrediente.

`--dry-run` non chiama nessuno e non scrive: dice quante voci mancano, quali chiederebbe,
e — dopo un primo lancio vero — quanto costerebbe, con la media di quel che è stato
pagato. `--limit N` chiede al più N voci: la prima volta `--limit 20`, per guardare le
risposte (una riga stampata per voce) e il costo prima del resto.
"""

import asyncio
import sys

from app.core.db import SessionLocal
from app.domain.substitutions import SubstitutionContext
from app.repositories.substitutions import pending_voices
from app.services.substitutions import decide_substitutions, measured_cost

FLAG_DRY_RUN = "--dry-run"
FLAG_LIMIT = "--limit"
# quante voci elenca il `--dry-run`: il resto si conta
SHOWN = 20


def parse(argv: list[str]) -> tuple[bool, int | None] | str:
    """`(dry_run, limit)`, o il messaggio d'errore da stampare."""
    dry_run = False
    limit: int | None = None
    position = 0
    while position < len(argv):
        arg = argv[position]
        if arg == FLAG_DRY_RUN:
            dry_run = True
            position += 1
            continue
        if arg == FLAG_LIMIT:
            value = argv[position + 1] if position + 1 < len(argv) else ""
            if not value.isdigit() or int(value) < 1:
                return f"uso: {FLAG_LIMIT} <un numero maggiore di zero>"
            limit = int(value)
            position += 2
            continue
        return f"argomento sconosciuto: {arg}"
    return dry_run, limit


def _voices(count: int) -> str:
    return "1 voce" if count == 1 else f"{count} voci"


def _recipes(count: int) -> str:
    return "1 ricetta" if count == 1 else f"{count} ricette"


def _pending_line(count: int) -> str:
    # L'ultima riga dice sempre quanto resta, come `decide_units`: chi mette in produzione
    # legge proprio quella per sapere se deve rilanciare.
    if count == 1:
        return "1 voce resta da decidere: rilancia questo comando."
    if count:
        return f"{count} voci restano da decidere: rilancia questo comando."
    return "nessuna voce in attesa."


async def _dry_run(session, limit: int | None) -> None:
    voices = await pending_voices(session)
    if not voices:
        print("nessuna voce in attesa.")
        return
    savory = sum(1 for voice in voices if voice.context is SubstitutionContext.SAVORY)
    print(
        f"{_voices(len(voices))} senza sostituti: {savory} nei piatti salati, "
        f"{len(voices) - savory} nei dolci."
    )
    asked = voices[:limit] if limit is not None else voices
    print(f"ne chiederei {len(asked)}, dalle più usate:")
    for voice in asked[:SHOWN]:
        print(f"- {voice.name} ({voice.context.value}, {_recipes(voice.recipes)})")
    if len(asked) > SHOWN:
        print(f"… e altre {len(asked) - SHOWN}.")
    calls, average = await measured_cost(session)
    if average is None:
        print(f"nessun costo misurato ancora: lancia con {FLAG_LIMIT} 20 per misurarlo.")
    else:
        print(
            f"costo medio misurato: {average:.5f} $ a voce su {calls} chiamate; "
            f"stima per {len(asked)}: {average * len(asked):.4f} $."
        )


async def main(argv: list[str]) -> int:
    parsed = parse(argv)
    # Un codice d'uscita diverso da zero, non solo la stampa: un refuso in uno script che
    # controlla l'exit code non deve passare per un successo.
    if isinstance(parsed, str):
        print(parsed)
        return 2
    dry_run, limit = parsed

    async with SessionLocal() as session:
        if dry_run:
            await _dry_run(session, limit)
            return 0
        # Si stampa, non si logga: `app/` non configura nessun logging, e sotto `python -m`
        # una riga a `logger.info` non esce da nessuna parte (la scelta di `decide_units`).
        esito = await decide_substitutions(
            session, limit=limit, after_batch=session.commit, report=print
        )
        await session.commit()

    if esito.unavailable is not None:
        print(
            f"sostituti non disponibili ({esito.unavailable}): chi tocca «Sostituisci» trova "
            "«Nessun suggerimento ancora» e la strada a mano."
        )
    saved = "1 voce salvata" if esito.stored == 1 else f"{esito.stored} voci salvate"
    print(
        f"{saved} ({esito.substitutes} con sostituti, {esito.omit} da omettere, "
        f"{esito.irreplaceable} insostituibili), {esito.rejected} risposte scartate."
    )
    if esito.calls:
        spent = "costo non dichiarato" if esito.cost_usd is None else f"{esito.cost_usd:.5f} $"
        calls = "1 chiamata" if esito.calls == 1 else f"{esito.calls} chiamate"
        print(f"spesa di questo lancio: {spent} in {calls}.")
    print(_pending_line(esito.pending))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
```

- [ ] **Step 4: Passano**

Run: il comando di pytest con `tests/test_decide_substitutes_cli.py`.
Expected: PASS, 10 test (1 + 4 parametri + 5).

- [ ] **Step 5: Commit**

```bash
git add backend/app/cli/decide_substitutes.py backend/tests/test_decide_substitutes_cli.py
git commit -m "feat(cli): R5, decide_substitutes — a lotti, --limit e --dry-run, una riga per voce e quanto resta"
```

---

### Task 8: Le rotte — la riga della ricetta, la scheda dell'ingrediente

**Files:**
- Create: `backend/app/schemas/substitution.py`
- Create: `backend/app/api/substitutions.py`
- Modify: `backend/app/main.py` (l'import dei router e due `include_router`)
- Test: `backend/tests/api/test_substitutions_recipe.py`, `backend/tests/api/test_substitutions_registry.py`

**Interfaces:**
- Consumes: Task 1, Task 3 (`Answer`, `SubstitutionRefused`, `checked_answer`, `effective_row`, `visible_options`, `write_general`, `write_override`, `delete_override`), Task 4 (`ingredient_view`), Task 6 (`decide_pair`); `availability_map` (`app.repositories.pantry`); `is_satisfied`, `Availability`, `IngredientRole`, `IngredientKind` (`app.domain.rules`).
- Produces: in `app.schemas.substitution` `SubstituteOut`, `LineSubstituteOut`, `LineSubstitutionOut`, `SubstituteIn`, `SubstitutionIn`, `ContextSubstitutionOut`, `IngredientSubstitutionsOut`; in `app.api.substitutions` `recipe_router` e `ingredient_router`. Le rotte (il frontend dei Task 9–12 le chiama):
  - `GET /api/v1/recipes/{recipe_id}/substitutes/{ingredient_id}` → `LineSubstitutionOut`;
  - `POST /api/v1/recipes/{recipe_id}/substitutes/{ingredient_id}/ask` → `LineSubstitutionOut` (mai 503: `ai_failed`);
  - `PUT /api/v1/recipes/{recipe_id}/substitutes/{ingredient_id}` corpo `SubstitutionIn` → `LineSubstitutionOut`, 422 con la frase;
  - `DELETE /api/v1/recipes/{recipe_id}/substitutes/{ingredient_id}` → 204;
  - `GET /api/v1/ingredients/{ingredient_id}/substitutes` → `IngredientSubstitutionsOut`;
  - `PUT /api/v1/ingredients/{ingredient_id}/substitutes/{context}` (`dolce` | `salato`) corpo `SubstitutionIn` → `IngredientSubstitutionsOut`, 422 con la frase.
  - 404 con `detail`: «ricetta inesistente», «Questo ingrediente non è nella ricetta.», «ingrediente inesistente».

- [ ] **Step 1: I test della riga, che falliscono**

Crea `backend/tests/api/test_substitutions_recipe.py`:

```python
"""«Sostituisci» nella ricetta (R5): la risposta di una riga, chiesta, corretta, tolta.

Per una riga vale la correzione della ricetta, se c'è, poi la voce generale del contesto
della ricetta. Ogni sostituto porta la sua disponibilità e se, in dispensa, soddisfa la
stessa regola della riga (`satisfied`, la metà della regola di R6 che R5 già calcola).
"""

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.llm_call import LlmCall
from app.db.models.pantry import PantryItem
from app.db.models.recipe import RecipeSource
from app.domain.substitutions import SubstitutionContext, SubstitutionVerdict
from app.repositories import substitutions as repo
from app.repositories.recipes import create_recipe
from app.repositories.substitutions import Answer
from llm_fakes import FakeLlm

SALATO = SubstitutionContext.SAVORY
DOLCE = SubstitutionContext.SWEET


@pytest.fixture
def con_chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def cucina(db_session):
    def voce(nome: str, reparto: str) -> Ingredient:
        return Ingredient(name=nome, display_name=nome.capitalize(), category=reparto)

    voci = {
        nome: voce(nome, IngredientCategory.CEREALI) for nome in ("pasta", "riso", "farro", "orzo")
    }
    db_session.add_all(voci.values())
    await db_session.flush()
    db_session.add_all([
        PantryItem(ingredient_id=voci["riso"].id, status="available"),
        PantryItem(ingredient_id=voci["farro"].id, status="low"),
    ])

    async def ricetta(titolo: str, ruolo: str):
        return await create_recipe(
            db_session, title=titolo, description=None, instructions="Cuoci.", servings=2,
            source=RecipeSource.MANUAL, source_ref=None,
            # senza categoria: una ricetta salata (Review Focus 5)
            ingredients=[(voci["pasta"].id, ruolo, "180 g", None)], embedding=None,
        )

    ricette = {
        "pasta": await ricetta("Pasta al pomodoro", "primary"),
        "minestra": await ricetta("Minestra", "secondary"),
    }
    return voci, ricette


def _url(ricetta, voce, coda: str = "") -> str:
    return f"/api/v1/recipes/{ricetta.id}/substitutes/{voce.id}{coda}"


async def test_senza_risposta_la_riga_lo_dice(logged_client, cucina):
    voci, ricette = cucina

    risposta = await logged_client.get(_url(ricette["pasta"], voci["pasta"]))

    assert risposta.status_code == 200
    assert risposta.json() == {
        "ingredient_id": str(voci["pasta"].id), "ingredient_name": "pasta", "context": "salato",
        "scope": None, "verdict": None, "decided_by": None, "substitutes": [], "ai_failed": False,
    }


async def test_la_voce_generale_dice_cosa_c_e_in_dispensa_secondo_la_riga(
    db_session, logged_client, cucina
):
    voci, ricette = cucina
    await repo.store_ai_answer(
        db_session, voci["pasta"].id, SALATO,
        Answer(SubstitutionVerdict.SUBSTITUTES, ((voci["riso"].id, "cottura più lunga"), (voci["farro"].id, None))),
    )

    principale = (await logged_client.get(_url(ricette["pasta"], voci["pasta"]))).json()
    secondaria = (await logged_client.get(_url(ricette["minestra"], voci["pasta"]))).json()

    assert (principale["scope"], principale["verdict"], principale["decided_by"]) == (
        "general", "substitutes", "ai",
    )
    assert principale["substitutes"] == [
        {"ingredient_id": str(voci["riso"].id), "name": "riso", "note": "cottura più lunga",
         "availability": "available", "satisfied": True},
        # quasi finito non basta a una riga principale…
        {"ingredient_id": str(voci["farro"].id), "name": "farro", "note": None,
         "availability": "low", "satisfied": False},
    ]
    # …e basta a una secondaria
    assert secondaria["substitutes"][1]["satisfied"] is True


async def test_la_correzione_della_ricetta_vince_sulla_voce_generale(db_session, logged_client, cucina):
    voci, ricette = cucina
    await repo.store_ai_answer(db_session, voci["pasta"].id, SALATO, Answer(SubstitutionVerdict.OMIT))
    await repo.write_override(
        db_session, ricette["pasta"].id, voci["pasta"].id, Answer(SubstitutionVerdict.IRREPLACEABLE)
    )

    corpo = (await logged_client.get(_url(ricette["pasta"], voci["pasta"]))).json()

    assert (corpo["scope"], corpo["verdict"], corpo["decided_by"]) == ("recipe", "irreplaceable", "human")
    altra = (await logged_client.get(_url(ricette["minestra"], voci["pasta"]))).json()
    assert (altra["scope"], altra["verdict"]) == ("general", "omit")


async def test_una_ricetta_che_diventa_dolce_legge_la_voce_dolce(db_session, logged_client, cucina):
    """Review Focus 1: cambiata la categoria con «Modifica», la voce è l'altra."""
    voci, ricette = cucina
    await repo.write_general(db_session, voci["pasta"].id, SALATO, Answer(SubstitutionVerdict.OMIT))
    await repo.write_general(
        db_session, voci["pasta"].id, DOLCE, Answer(SubstitutionVerdict.IRREPLACEABLE)
    )
    assert (await logged_client.get(_url(ricette["pasta"], voci["pasta"]))).json()["verdict"] == "omit"

    ricette["pasta"].category = "Dolci e Desserts"
    await db_session.flush()

    corpo = (await logged_client.get(_url(ricette["pasta"], voci["pasta"]))).json()
    assert (corpo["context"], corpo["verdict"]) == ("dolce", "irreplaceable")


async def test_una_ricetta_o_una_riga_che_non_ci_sono(logged_client, cucina):
    voci, ricette = cucina
    import uuid

    nessuna = await logged_client.get(f"/api/v1/recipes/{uuid.uuid4()}/substitutes/{voci['pasta'].id}")
    assert (nessuna.status_code, nessuna.json()["detail"]) == (404, "ricetta inesistente")
    fuori = await logged_client.get(_url(ricette["pasta"], voci["riso"]))
    assert (fuori.status_code, fuori.json()["detail"]) == (404, "Questo ingrediente non è nella ricetta.")


async def test_ask_salva_la_risposta_dell_ai(db_session, logged_client, cucina, con_chiave, monkeypatch):
    voci, ricette = cucina
    finto = FakeLlm({"esito": "sostituti", "sostituti": [{"nome": "riso", "nota": ""}]})
    monkeypatch.setattr("app.services.substitutions.open_client", lambda: finto)

    corpo = (await logged_client.post(_url(ricette["pasta"], voci["pasta"], "/ask"))).json()

    assert (corpo["scope"], corpo["verdict"], corpo["decided_by"], corpo["ai_failed"]) == (
        "general", "substitutes", "ai", False,
    )
    assert [s["name"] for s in corpo["substitutes"]] == ["riso"]
    assert len(finto.bodies) == 1
    chiamate = (await db_session.execute(select(LlmCall.call_site))).scalars().all()
    assert chiamate == ["ingredient_substitutes"]


async def test_ask_senza_ai_lascia_la_strada_a_mano(db_session, logged_client, cucina, monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    voci, ricette = cucina

    risposta = await logged_client.post(_url(ricette["pasta"], voci["pasta"], "/ask"))

    assert risposta.status_code == 200
    assert (risposta.json()["verdict"], risposta.json()["ai_failed"]) == (None, True)
    get_settings.cache_clear()


async def test_ask_con_una_risposta_non_chiama(db_session, logged_client, cucina, con_chiave, monkeypatch):
    voci, ricette = cucina
    await repo.store_ai_answer(db_session, voci["pasta"].id, SALATO, Answer(SubstitutionVerdict.OMIT))
    finto = FakeLlm()
    monkeypatch.setattr("app.services.substitutions.open_client", lambda: finto)

    corpo = (await logged_client.post(_url(ricette["pasta"], voci["pasta"], "/ask"))).json()

    assert (corpo["verdict"], corpo["ai_failed"]) == ("omit", False)
    assert finto.bodies == []


async def test_ask_richiede_una_voce_rimasta_senza_sostituti(
    db_session, logged_client, cucina, con_chiave, monkeypatch
):
    """Review Focus 2: l'unico sostituto è stato cancellato (un annullamento della coda)."""
    voci, ricette = cucina
    await repo.store_ai_answer(
        db_session, voci["pasta"].id, SALATO,
        Answer(SubstitutionVerdict.SUBSTITUTES, ((voci["orzo"].id, None),)),
    )
    await db_session.execute(delete(Ingredient).where(Ingredient.id == voci["orzo"].id))
    assert (await logged_client.get(_url(ricette["pasta"], voci["pasta"]))).json()["verdict"] is None

    monkeypatch.setattr(
        "app.services.substitutions.open_client",
        lambda: FakeLlm({"esito": "sostituti", "sostituti": [{"nome": "riso", "nota": ""}]}),
    )
    corpo = (await logged_client.post(_url(ricette["pasta"], voci["pasta"], "/ask"))).json()
    assert [s["name"] for s in corpo["substitutes"]] == ["riso"]


async def test_put_scrive_la_correzione_della_sola_ricetta(db_session, logged_client, cucina):
    voci, ricette = cucina

    risposta = await logged_client.put(
        _url(ricette["pasta"], voci["pasta"]),
        json={"verdict": "substitutes", "substitutes": [{"ingredient_id": str(voci["riso"].id), "note": " metà  dose "}]},
    )

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert (corpo["scope"], corpo["decided_by"]) == ("recipe", "human")
    assert corpo["substitutes"][0]["note"] == "metà dose"
    assert await repo.general_row(db_session, voci["pasta"].id, SALATO) is None


async def test_put_rifiuta_con_la_frase(logged_client, cucina):
    voci, ricette = cucina

    se_stesso = await logged_client.put(
        _url(ricette["pasta"], voci["pasta"]),
        json={"verdict": "substitutes", "substitutes": [{"ingredient_id": str(voci["pasta"].id)}]},
    )
    assert se_stesso.status_code == 422
    assert se_stesso.json()["detail"] == "«Pasta» non può sostituire sé stesso: scegli un altro ingrediente."
    sconosciuto = await logged_client.put(_url(ricette["pasta"], voci["pasta"]), json={"verdict": "forse"})
    assert sconosciuto.status_code == 422


async def test_delete_toglie_la_correzione_e_torna_la_generale(db_session, logged_client, cucina):
    voci, ricette = cucina
    await repo.write_general(db_session, voci["pasta"].id, SALATO, Answer(SubstitutionVerdict.OMIT))
    await repo.write_override(
        db_session, ricette["pasta"].id, voci["pasta"].id, Answer(SubstitutionVerdict.IRREPLACEABLE)
    )

    assert (await logged_client.delete(_url(ricette["pasta"], voci["pasta"]))).status_code == 204
    corpo = (await logged_client.get(_url(ricette["pasta"], voci["pasta"]))).json()
    assert (corpo["scope"], corpo["verdict"]) == ("general", "omit")
    # togliere quel che non c'è non è un errore
    assert (await logged_client.delete(_url(ricette["pasta"], voci["pasta"]))).status_code == 204
```

- [ ] **Step 2: I test della scheda, che falliscono**

Crea `backend/tests/api/test_substitutions_registry.py`:

```python
"""I sostituti nella scheda di un ingrediente (R5): i contesti, la voce dell'AI da
rivedere, la voce scritta a mano, le correzioni delle ricette."""

import uuid

import pytest_asyncio

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import RecipeSource
from app.domain.substitutions import SubstitutionContext, SubstitutionVerdict
from app.repositories import substitutions as repo
from app.repositories.recipes import create_recipe
from app.repositories.substitutions import Answer

SALATO = SubstitutionContext.SAVORY


@pytest_asyncio.fixture
async def burro(db_session):
    def voce(nome: str, reparto: str) -> Ingredient:
        return Ingredient(name=nome, display_name=nome.capitalize(), category=reparto)

    voci = {
        "burro": voce("burro", IngredientCategory.LATTICINI),
        "margarina": voce("margarina", IngredientCategory.CONDIMENTI),
        "detersivo": voce("detersivo", IngredientCategory.CASA),
    }
    db_session.add_all(voci.values())
    await db_session.flush()
    ricette = []
    for titolo, categoria in (("Pollo al burro", "Secondi piatti"), ("Biscotti", "Dolci"), ("Torta", "Dolci")):
        ricette.append(
            await create_recipe(
                db_session, title=titolo, description=None, instructions="Cuoci.", servings=2,
                source=RecipeSource.MANUAL, source_ref=None,
                ingredients=[(voci["burro"].id, "primary", None, None)], embedding=None,
                category=categoria,
            )
        )
    return voci, ricette


async def test_la_scheda_ha_un_contesto_per_dove_compare(db_session, logged_client, burro):
    voci, ricette = burro
    await repo.store_ai_answer(
        db_session, voci["burro"].id, SALATO,
        Answer(SubstitutionVerdict.SUBSTITUTES, ((voci["margarina"].id, "metà dose"),)),
    )
    await repo.write_override(
        db_session, ricette[1].id, voci["burro"].id, Answer(SubstitutionVerdict.OMIT)
    )

    risposta = await logged_client.get(f"/api/v1/ingredients/{voci['burro'].id}/substitutes")

    assert risposta.status_code == 200
    assert risposta.json() == {
        "ingredient_id": str(voci["burro"].id),
        "recipe_overrides": 1,
        "contexts": [
            {"context": "salato", "recipes": 1, "verdict": "substitutes", "decided_by": "ai",
             "substitutes": [{"ingredient_id": str(voci["margarina"].id), "name": "margarina", "note": "metà dose"}]},
            {"context": "dolce", "recipes": 2, "verdict": None, "decided_by": None, "substitutes": []},
        ],
    }


async def test_va_bene_cosi_fa_la_voce_scritta_a_mano(db_session, logged_client, burro):
    voci, _ = burro
    await repo.store_ai_answer(db_session, voci["burro"].id, SALATO, Answer(SubstitutionVerdict.OMIT))

    risposta = await logged_client.put(
        f"/api/v1/ingredients/{voci['burro'].id}/substitutes/salato",
        json={"verdict": "omit", "substitutes": []},
    )

    assert risposta.status_code == 200
    salato = risposta.json()["contexts"][0]
    assert (salato["context"], salato["verdict"], salato["decided_by"]) == ("salato", "omit", "human")


async def test_la_voce_dolce_si_scrive_dove_non_c_era(logged_client, burro):
    voci, _ = burro

    risposta = await logged_client.put(
        f"/api/v1/ingredients/{voci['burro'].id}/substitutes/dolce",
        json={"verdict": "substitutes", "substitutes": [{"ingredient_id": str(voci["margarina"].id), "note": None}]},
    )

    dolce = risposta.json()["contexts"][1]
    assert (dolce["context"], dolce["decided_by"], [s["name"] for s in dolce["substitutes"]]) == (
        "dolce", "human", ["margarina"],
    )


async def test_i_rifiuti(logged_client, burro):
    voci, _ = burro
    base = f"/api/v1/ingredients/{voci['burro'].id}/substitutes"

    assert (await logged_client.put(f"{base}/speziato", json={"verdict": "omit"})).status_code == 422
    se_stesso = await logged_client.put(
        f"{base}/salato",
        json={"verdict": "substitutes", "substitutes": [{"ingredient_id": str(voci["burro"].id)}]},
    )
    assert (se_stesso.status_code, se_stesso.json()["detail"]) == (
        422, "«Burro» non può sostituire sé stesso: scegli un altro ingrediente.",
    )
    detersivo = await logged_client.put(
        f"/api/v1/ingredients/{voci['detersivo'].id}/substitutes/salato", json={"verdict": "omit"}
    )
    assert (detersivo.status_code, detersivo.json()["detail"]) == (
        422, "«Detersivo» non è un alimento: non ha sostituti.",
    )
    for metodo, corpo in (("get", None), ("put", {"verdict": "omit"})):
        url = f"/api/v1/ingredients/{uuid.uuid4()}/substitutes" + ("/salato" if metodo == "put" else "")
        risposta = await getattr(logged_client, metodo)(url, **({"json": corpo} if corpo else {}))
        assert (risposta.status_code, risposta.json()["detail"]) == (404, "ingrediente inesistente")


async def test_un_non_alimentare_non_ha_contesti(logged_client, burro):
    voci, _ = burro
    corpo = (await logged_client.get(f"/api/v1/ingredients/{voci['detersivo'].id}/substitutes")).json()
    assert (corpo["contexts"], corpo["recipe_overrides"]) == ([], 0)
```

- [ ] **Step 3: Falliscono**

Run: il comando di pytest con `tests/api/test_substitutions_recipe.py tests/api/test_substitutions_registry.py`.
Expected: FAIL, 404 su ogni rotta nuova (e `ModuleNotFoundError` per gli import che il Step 4 crea solo se un test li importa: non li importa).

- [ ] **Step 4: Gli schemi**

Crea `backend/app/schemas/substitution.py`:

```python
"""Le risposte di «Sostituisci» in HTTP (R5)."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.rules import Availability
from app.domain.substitutions import DecidedBy, SubstitutionContext, SubstitutionVerdict


class SubstituteOut(BaseModel):
    ingredient_id: uuid.UUID
    # il nome canonico, minuscolo: il frontend mette la maiuscola solo a inizio riga
    name: str
    note: str | None


class LineSubstituteOut(SubstituteOut):
    availability: Availability
    # se in dispensa soddisfa la stessa regola della riga (`is_satisfied`): «ce l'hai»
    satisfied: bool


class LineSubstitutionOut(BaseModel):
    ingredient_id: uuid.UUID
    ingredient_name: str
    context: SubstitutionContext
    # da dove viene la risposta: la correzione della ricetta o la voce generale
    scope: Literal["recipe", "general"] | None
    verdict: SubstitutionVerdict | None
    decided_by: DecidedBy | None
    substitutes: list[LineSubstituteOut]
    # `POST …/ask`: l'AI non ha risposto, o ha risposto qualcosa che non si applica
    ai_failed: bool = False


class SubstituteIn(BaseModel):
    ingredient_id: uuid.UUID
    # Il limite vero (60, dopo la pulizia degli spazi) lo controlla `checked_answer`, con
    # la sua frase; questo è solo un tetto al corpo della richiesta.
    note: str | None = Field(default=None, max_length=500)


class SubstitutionIn(BaseModel):
    verdict: SubstitutionVerdict
    # quanti, lo dice `checked_answer` con la sua frase; qui solo un tetto al corpo
    substitutes: list[SubstituteIn] = Field(default_factory=list, max_length=20)


class ContextSubstitutionOut(BaseModel):
    context: SubstitutionContext
    recipes: int
    verdict: SubstitutionVerdict | None
    decided_by: DecidedBy | None
    substitutes: list[SubstituteOut]


class IngredientSubstitutionsOut(BaseModel):
    ingredient_id: uuid.UUID
    contexts: list[ContextSubstitutionOut]
    recipe_overrides: int
```

- [ ] **Step 5: Le rotte**

Crea `backend/app/api/substitutions.py`:

```python
"""«Sostituisci» (R5): la risposta di una riga di ricetta, e quelle di un ingrediente.

Le regole stanno altrove — quale risposta vale per una riga e cosa conta come risposta
in `repositories/substitutions.py`, la domanda all'AI e la sua verifica in
`services/substitutions.py`, se un sostituto in dispensa basta in `domain/rules.py`
(`is_satisfied`, la stessa regola delle righe): qui si legge, si scrive e si risponde.

Dalla ricetta si scrive solo la correzione di quella ricetta; la voce generale si
scrive dalla scheda dell'ingrediente (spec §3.10).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import require_session
from app.db.models.ingredient import Ingredient
from app.db.models.recipe import Recipe, RecipeIngredient
from app.domain.rules import Availability, IngredientKind, IngredientRole, is_satisfied
from app.domain.substitutions import SubstitutionContext, SubstitutionVerdict, recipe_context
from app.repositories.pantry import availability_map
from app.repositories.substitutions import (
    Answer,
    SubstitutionRefused,
    checked_answer,
    delete_override,
    effective_row,
    ingredient_view,
    visible_options,
    write_general,
    write_override,
)
from app.schemas.substitution import (
    ContextSubstitutionOut,
    IngredientSubstitutionsOut,
    LineSubstituteOut,
    LineSubstitutionOut,
    SubstituteOut,
    SubstitutionIn,
)
from app.services.substitutions import decide_pair

recipe_router = APIRouter(
    prefix="/api/v1/recipes", tags=["substitutions"], dependencies=[Depends(require_session)]
)
ingredient_router = APIRouter(
    prefix="/api/v1/ingredients", tags=["substitutions"], dependencies=[Depends(require_session)]
)

LINE_GONE = "Questo ingrediente non è nella ricetta."


async def _line(
    session: AsyncSession, recipe_id: uuid.UUID, ingredient_id: uuid.UUID
) -> tuple[Recipe, RecipeIngredient]:
    recipe = await session.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ricetta inesistente")
    line = (
        await session.execute(
            select(RecipeIngredient).where(
                RecipeIngredient.recipe_id == recipe_id,
                RecipeIngredient.ingredient_id == ingredient_id,
            )
        )
    ).scalars().first()
    if line is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, LINE_GONE)
    return recipe, line


async def _line_out(
    session: AsyncSession, recipe: Recipe, line: RecipeIngredient, *, ai_failed: bool = False
) -> LineSubstitutionOut:
    context = recipe_context(recipe.category)
    row = await effective_row(session, recipe.id, line.ingredient_id, context)
    common = {
        "ingredient_id": line.ingredient_id,
        "ingredient_name": line.ingredient.name,
        "context": context,
        "ai_failed": ai_failed,
    }
    if row is None:
        return LineSubstitutionOut(
            **common, scope=None, verdict=None, decided_by=None, substitutes=[]
        )
    options = visible_options(row)
    have = await availability_map(session, [option.substitute_id for option in options])
    role = IngredientRole(line.role)
    substitutes = []
    for option in options:
        availability = have.get(option.substitute_id, Availability.MISSING)
        substitutes.append(
            LineSubstituteOut(
                ingredient_id=option.substitute_id,
                name=option.substitute.name,
                note=option.note,
                availability=availability,
                satisfied=is_satisfied(role, availability),
            )
        )
    return LineSubstitutionOut(
        **common,
        scope="recipe" if row.recipe_id is not None else "general",
        verdict=SubstitutionVerdict(row.verdict),
        decided_by=row.decided_by,
        substitutes=substitutes,
    )


async def _checked(
    session: AsyncSession, ingredient_id: uuid.UUID, payload: SubstitutionIn
) -> Answer:
    try:
        return await checked_answer(
            session,
            ingredient_id,
            payload.verdict,
            [(substitute.ingredient_id, substitute.note) for substitute in payload.substitutes],
        )
    except SubstitutionRefused as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, exc.message) from exc


@recipe_router.get("/{recipe_id}/substitutes/{ingredient_id}", response_model=LineSubstitutionOut)
async def line_substitution(
    recipe_id: uuid.UUID, ingredient_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> LineSubstitutionOut:
    recipe, line = await _line(session, recipe_id, ingredient_id)
    return await _line_out(session, recipe, line)


@recipe_router.post(
    "/{recipe_id}/substitutes/{ingredient_id}/ask", response_model=LineSubstitutionOut
)
async def ask_line_substitution(
    recipe_id: uuid.UUID, ingredient_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> LineSubstitutionOut:
    """La voce generale della riga, chiesta all'AI sul momento se manca, e salvata.

    Mai un 503: l'AI che non risponde è `ai_failed`, e lo schermo offre la strada a mano.
    """
    recipe, line = await _line(session, recipe_id, ingredient_id)
    outcome = await decide_pair(session, line.ingredient_id, recipe_context(recipe.category))
    await session.commit()
    return await _line_out(session, recipe, line, ai_failed=outcome.failed)


@recipe_router.put("/{recipe_id}/substitutes/{ingredient_id}", response_model=LineSubstitutionOut)
async def correct_line_substitution(
    recipe_id: uuid.UUID,
    ingredient_id: uuid.UUID,
    payload: SubstitutionIn,
    session: AsyncSession = Depends(get_session),
) -> LineSubstitutionOut:
    """«Non va bene qui»: la correzione di questa ricetta, e solo di questa."""
    recipe, line = await _line(session, recipe_id, ingredient_id)
    answer = await _checked(session, line.ingredient_id, payload)
    await write_override(session, recipe.id, line.ingredient_id, answer)
    await session.commit()
    return await _line_out(session, recipe, line)


@recipe_router.delete(
    "/{recipe_id}/substitutes/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def reset_line_substitution(
    recipe_id: uuid.UUID, ingredient_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    """«Torna al suggerimento generale». Togliere quel che non c'è non è un errore."""
    recipe, line = await _line(session, recipe_id, ingredient_id)
    await delete_override(session, recipe.id, line.ingredient_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _ingredient(session: AsyncSession, ingredient_id: uuid.UUID) -> Ingredient:
    ingredient = await session.get(Ingredient, ingredient_id)
    if ingredient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ingrediente inesistente")
    return ingredient


async def _ingredient_out(
    session: AsyncSession, ingredient_id: uuid.UUID
) -> IngredientSubstitutionsOut:
    view = await ingredient_view(session, ingredient_id)
    contexts = []
    for item in view.contexts:
        row = item.row
        contexts.append(
            ContextSubstitutionOut(
                context=item.context,
                recipes=item.recipes,
                verdict=SubstitutionVerdict(row.verdict) if row is not None else None,
                decided_by=row.decided_by if row is not None else None,
                substitutes=[
                    SubstituteOut(
                        ingredient_id=option.substitute_id,
                        name=option.substitute.name,
                        note=option.note,
                    )
                    for option in (visible_options(row) if row is not None else [])
                ],
            )
        )
    return IngredientSubstitutionsOut(
        ingredient_id=ingredient_id, contexts=contexts, recipe_overrides=view.recipe_overrides
    )


@ingredient_router.get("/{ingredient_id}/substitutes", response_model=IngredientSubstitutionsOut)
async def ingredient_substitutions(
    ingredient_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> IngredientSubstitutionsOut:
    await _ingredient(session, ingredient_id)
    return await _ingredient_out(session, ingredient_id)


@ingredient_router.put(
    "/{ingredient_id}/substitutes/{context}", response_model=IngredientSubstitutionsOut
)
async def correct_ingredient_substitution(
    ingredient_id: uuid.UUID,
    context: SubstitutionContext,
    payload: SubstitutionIn,
    session: AsyncSession = Depends(get_session),
) -> IngredientSubstitutionsOut:
    """La voce generale, scritta a mano in Anagrafica: «Correggi», «Scrivi tu», e «Va
    bene così», che rimanda la risposta dell'AI com'è e la fa diventare `human`."""
    ingredient = await _ingredient(session, ingredient_id)
    if ingredient.kind != IngredientKind.FOOD:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"«{ingredient.display_name}» non è un alimento: non ha sostituti.",
        )
    answer = await _checked(session, ingredient_id, payload)
    await write_general(session, ingredient_id, context, answer)
    await session.commit()
    return await _ingredient_out(session, ingredient_id)
```

- [ ] **Step 6: I router nell'app**

In `backend/app/main.py` (leggilo com'è sul ramo):

1. `from app.api import auth, cooking, imports, ingredients, pantry, products, recipes, shopping` diventa
   ```python
   from app.api import (
       auth,
       cooking,
       imports,
       ingredients,
       pantry,
       products,
       recipes,
       shopping,
       substitutions,
   )
   ```
2. Dopo `app.include_router(imports.router)` aggiungi:
   ```python
   app.include_router(substitutions.recipe_router)
   app.include_router(substitutions.ingredient_router)
   ```

- [ ] **Step 7: Passano, e tutta la suite**

Run: il comando di pytest (tutta la suite).
Expected: tutto verde, con i 17 test nuovi (12 della riga, 5 della scheda).

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/substitution.py backend/app/api/substitutions.py backend/app/main.py backend/tests/api/test_substitutions_recipe.py backend/tests/api/test_substitutions_registry.py
git commit -m "feat(api): R5, le rotte di «Sostituisci» — la riga della ricetta, chiesta, corretta, tolta; la scheda dell'ingrediente"
```

---

### Task 9: Il frontend — i tipi, le chiamate, le parole

**Files:**
- Create: `frontend/src/features/substitutes/types.ts`, `api.ts`, `api.test.ts`, `wording.ts`, `wording.test.ts`
- Create: `backend/tests/test_frontend_substitutes.py`

**Interfaces:**
- Consumes: le rotte del Task 8; `apiFetch`, `ApiError` (`frontend/src/api/client.ts`); `Availability` (`frontend/src/domain/types.ts`).
- Produces:
  - `types.ts`: `SubstitutionVerdict`, `SubstitutionContext`, `DecidedBy`, `SUBSTITUTES_MAX = 3`, `SUBSTITUTE_NOTE_MAX = 60`, `Substitute`, `LineSubstitute`, `LineSubstitution`, `ContextSubstitution`, `IngredientSubstitutions`, `SubstitutionBody`;
  - `api.ts`: `fetchLineSubstitution`, `askLineSubstitution`, `loadLineSubstitution`, `saveLineSubstitution`, `resetLineSubstitution`, `fetchIngredientSubstitutions`, `saveIngredientSubstitution`;
  - `wording.ts`: `contextIn(context) -> "nei piatti salati" | "nei dolci"`, `contextTitle(context)`, `provenanceText(answer)`, `recipesText(count)`, `overridesText(count) -> string | null`, `saveErrorText(error: unknown) -> string`.
  - I Task 10–12 li usano.

- [ ] **Step 1: I test che falliscono**

Crea `frontend/src/features/substitutes/wording.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { ApiError } from "../../api/client";
import {
  contextIn,
  contextTitle,
  overridesText,
  provenanceText,
  recipesText,
  saveErrorText,
} from "./wording";

describe("le parole dei sostituti", () => {
  it("dice il contesto dentro una frase e come titolo", () => {
    expect(contextIn("salato")).toBe("nei piatti salati");
    expect(contextIn("dolce")).toBe("nei dolci");
    expect(contextTitle("salato")).toBe("Nei piatti salati");
    expect(contextTitle("dolce")).toBe("Nei dolci");
  });

  it("dice da dove viene una risposta", () => {
    expect(provenanceText({ scope: "general", decided_by: "ai", context: "salato" })).toBe(
      "Suggerito dall'AI per i piatti salati."
    );
    expect(provenanceText({ scope: "general", decided_by: "human", context: "dolce" })).toBe(
      "Scelto a mano per i dolci."
    );
    expect(provenanceText({ scope: "recipe", decided_by: "human", context: "dolce" })).toBe(
      "Scelto a mano per questa ricetta."
    );
  });

  it("conta le ricette e le correzioni", () => {
    expect(recipesText(0)).toBe("in nessuna ricetta");
    expect(recipesText(1)).toBe("in 1 ricetta");
    expect(recipesText(120)).toBe("in 120 ricette");
    expect(overridesText(0)).toBeNull();
    expect(overridesText(1)).toBe("Corretto a mano in 1 ricetta.");
    expect(overridesText(2)).toBe("Corretto a mano in 2 ricette.");
  });

  it("un rifiuto del server si legge com'è, ogni altro guasto no", () => {
    const rifiuto = new ApiError("x", 422, { detail: "«Pasta» non può sostituire sé stesso: scegli un altro ingrediente." });
    expect(saveErrorText(rifiuto)).toBe("«Pasta» non può sostituire sé stesso: scegli un altro ingrediente.");
    // un 422 di validazione ha `detail` come lista: non è una frase da mostrare
    expect(saveErrorText(new ApiError("x", 422, { detail: [{ msg: "x" }] }))).toBe(
      "Non sono riuscito a salvare. Riprova."
    );
    expect(saveErrorText(new ApiError("x", 500, null))).toBe("Non sono riuscito a salvare. Riprova.");
    expect(saveErrorText(new Error("rete"))).toBe("Non sono riuscito a salvare. Riprova.");
  });
});
```

Crea `frontend/src/features/substitutes/api.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  loadLineSubstitution,
  resetLineSubstitution,
  saveIngredientSubstitution,
  saveLineSubstitution,
} from "./api";
import type { LineSubstitution } from "./types";

const VUOTA: LineSubstitution = {
  ingredient_id: "i-pasta", ingredient_name: "pasta", context: "salato", scope: null,
  verdict: null, decided_by: null, substitutes: [], ai_failed: false,
};
const OMETTERE: LineSubstitution = { ...VUOTA, scope: "general", verdict: "omit", decided_by: "ai" };

function stubFetch(risposte: Record<string, unknown>) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const chiave = `${init?.method ?? "GET"} ${String(url)}`;
    const corpo = risposte[chiave];
    return Promise.resolve(
      corpo === undefined ? new Response(null, { status: 204 }) : new Response(JSON.stringify(corpo), { status: 200 })
    );
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("le chiamate dei sostituti", () => {
  it("una risposta salvata si legge e basta", async () => {
    const spy = stubFetch({ "GET /api/v1/recipes/r1/substitutes/i-pasta": OMETTERE });
    expect(await loadLineSubstitution("r1", "i-pasta")).toEqual(OMETTERE);
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("senza una risposta la chiede al server, che la chiede all'AI", async () => {
    const spy = stubFetch({
      "GET /api/v1/recipes/r1/substitutes/i-pasta": VUOTA,
      "POST /api/v1/recipes/r1/substitutes/i-pasta/ask": OMETTERE,
    });
    expect(await loadLineSubstitution("r1", "i-pasta")).toEqual(OMETTERE);
    expect(spy.mock.calls.map(([url, init]) => `${init?.method ?? "GET"} ${String(url)}`)).toEqual([
      "GET /api/v1/recipes/r1/substitutes/i-pasta",
      "POST /api/v1/recipes/r1/substitutes/i-pasta/ask",
    ]);
  });

  it("la correzione della ricetta va con PUT, il ritorno con DELETE", async () => {
    const spy = stubFetch({ "PUT /api/v1/recipes/r1/substitutes/i-pasta": OMETTERE });
    await saveLineSubstitution("r1", "i-pasta", { verdict: "omit", substitutes: [] });
    await resetLineSubstitution("r1", "i-pasta");
    const [put, del] = spy.mock.calls;
    expect(put[1]?.method).toBe("PUT");
    expect(JSON.parse(String(put[1]?.body))).toEqual({ verdict: "omit", substitutes: [] });
    expect(`${del[1]?.method} ${String(del[0])}`).toBe("DELETE /api/v1/recipes/r1/substitutes/i-pasta");
  });

  it("la voce generale si scrive per contesto", async () => {
    const spy = stubFetch({ "PUT /api/v1/ingredients/i-pasta/substitutes/dolce": { ingredient_id: "i-pasta", contexts: [], recipe_overrides: 0 } });
    await saveIngredientSubstitution("i-pasta", "dolce", { verdict: "irreplaceable", substitutes: [] });
    expect(String(spy.mock.calls[0][0])).toBe("/api/v1/ingredients/i-pasta/substitutes/dolce");
  });
});
```

Crea `backend/tests/test_frontend_substitutes.py`:

```python
"""I limiti dei sostituti copiati nel frontend devono essere quelli del dominio (R5).

Il frontend li usa per non offrire il quarto selettore e per tagliare la nota; il server
li controlla comunque. Due copie si scollano, e la prima a scollarsi sarebbe un modulo
che lascia scrivere una nota che il salvataggio poi rifiuta. Nello stile di
`test_frontend_categories.py`.
"""

import re
from pathlib import Path

from app.domain.substitutions import SUBSTITUTE_NOTE_MAX, SUBSTITUTES_MAX

TYPES_TS = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "features" / "substitutes" / "types.ts"
)


def _costante(nome: str) -> int:
    trovata = re.search(rf"export const {nome} = (\d+);", TYPES_TS.read_text())
    assert trovata is not None, f"{TYPES_TS}: manca la costante {nome}"
    return int(trovata.group(1))


def test_i_limiti_del_frontend_sono_quelli_del_dominio():
    assert _costante("SUBSTITUTES_MAX") == SUBSTITUTES_MAX
    assert _costante("SUBSTITUTE_NOTE_MAX") == SUBSTITUTE_NOTE_MAX
```

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/features/substitutes/`
Expected: FAIL, i moduli `./wording` e `./api` non esistono. E il comando di pytest con `tests/test_frontend_substitutes.py`: FAIL, il file `types.ts` non c'è.

- [ ] **Step 3: I tipi**

Crea `frontend/src/features/substitutes/types.ts`:

```ts
// I sostituti di R5, come li manda il backend (`backend/app/schemas/substitution.py`).
// Qui e non in `domain/types.ts`: li usano solo questa cartella e chi la monta.
import type { Availability } from "../../domain/types";

export type SubstitutionVerdict = "substitutes" | "omit" | "irreplaceable";
export type SubstitutionContext = "dolce" | "salato";
export type DecidedBy = "ai" | "human";

// Gli stessi limiti di `backend/app/domain/substitutions.py`: qui servono a non offrire il
// quarto selettore e a tagliare la nota, il server li controlla comunque. Un test del
// backend (`tests/test_frontend_substitutes.py`) li confronta.
export const SUBSTITUTES_MAX = 3;
export const SUBSTITUTE_NOTE_MAX = 60;

export interface Substitute {
  ingredient_id: string;
  /** Il nome canonico, minuscolo: la maiuscola solo a inizio riga, a video. */
  name: string;
  note: string | null;
}

export interface LineSubstitute extends Substitute {
  availability: Availability;
  /** In dispensa soddisfa la stessa regola della riga: «ce l'hai». Lo dice il server. */
  satisfied: boolean;
}

/** La risposta che vale per una riga di ricetta. */
export interface LineSubstitution {
  ingredient_id: string;
  ingredient_name: string;
  context: SubstitutionContext;
  /** La correzione di questa ricetta, o la voce generale; `null` senza risposta. */
  scope: "recipe" | "general" | null;
  verdict: SubstitutionVerdict | null;
  decided_by: DecidedBy | null;
  substitutes: LineSubstitute[];
  /** L'AI chiesta adesso non ha risposto, o ha risposto qualcosa che non si applica. */
  ai_failed: boolean;
}

export interface ContextSubstitution {
  context: SubstitutionContext;
  recipes: number;
  verdict: SubstitutionVerdict | null;
  decided_by: DecidedBy | null;
  substitutes: Substitute[];
}

export interface IngredientSubstitutions {
  ingredient_id: string;
  contexts: ContextSubstitution[];
  recipe_overrides: number;
}

export interface SubstitutionBody {
  verdict: SubstitutionVerdict;
  substitutes: { ingredient_id: string; note: string | null }[];
}
```

- [ ] **Step 4: Le chiamate**

Crea `frontend/src/features/substitutes/api.ts`:

```ts
import { apiFetch } from "../../api/client";
import type {
  IngredientSubstitutions,
  LineSubstitution,
  SubstitutionBody,
  SubstitutionContext,
} from "./types";

function linePath(recipeId: string, ingredientId: string) {
  return `/recipes/${recipeId}/substitutes/${ingredientId}`;
}

export function fetchLineSubstitution(recipeId: string, ingredientId: string) {
  return apiFetch<LineSubstitution>(linePath(recipeId, ingredientId));
}

export function askLineSubstitution(recipeId: string, ingredientId: string) {
  return apiFetch<LineSubstitution>(`${linePath(recipeId, ingredientId)}/ask`, { method: "POST" });
}

/** Quel che il pannello mostra: la risposta salvata, o — se non c'è — quella che il
 * server chiede adesso all'AI e salva (R5: una voce scoperta si calcola al primo tocco).
 * Senza AI torna una risposta vuota con `ai_failed`, mai un errore: la strada a mano
 * resta. */
export async function loadLineSubstitution(recipeId: string, ingredientId: string) {
  const saved = await fetchLineSubstitution(recipeId, ingredientId);
  return saved.verdict !== null ? saved : askLineSubstitution(recipeId, ingredientId);
}

/** «Non va bene qui»: la correzione di questa ricetta, e solo di questa. */
export function saveLineSubstitution(recipeId: string, ingredientId: string, body: SubstitutionBody) {
  return apiFetch<LineSubstitution>(linePath(recipeId, ingredientId), {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

/** «Torna al suggerimento generale». */
export function resetLineSubstitution(recipeId: string, ingredientId: string) {
  return apiFetch<null>(linePath(recipeId, ingredientId), { method: "DELETE" });
}

export function fetchIngredientSubstitutions(ingredientId: string) {
  return apiFetch<IngredientSubstitutions>(`/ingredients/${ingredientId}/substitutes`);
}

/** La voce generale, scritta a mano in Anagrafica (anche «Va bene così»). */
export function saveIngredientSubstitution(
  ingredientId: string,
  context: SubstitutionContext,
  body: SubstitutionBody
) {
  return apiFetch<IngredientSubstitutions>(`/ingredients/${ingredientId}/substitutes/${context}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}
```

- [ ] **Step 5: Le parole**

Crea `frontend/src/features/substitutes/wording.ts`:

```ts
import { ApiError } from "../../api/client";
import type { DecidedBy, SubstitutionContext } from "./types";

/** «nei piatti salati» / «nei dolci»: dentro una frase o un nome accessibile. */
export function contextIn(context: SubstitutionContext): string {
  return context === "dolce" ? "nei dolci" : "nei piatti salati";
}

/** Il titolo di una scheda in Anagrafica. */
export function contextTitle(context: SubstitutionContext): string {
  return context === "dolce" ? "Nei dolci" : "Nei piatti salati";
}

/** Da dove viene una risposta: la riga piccola sotto di lei. */
export function provenanceText(answer: {
  scope: "recipe" | "general" | null;
  decided_by: DecidedBy | null;
  context: SubstitutionContext;
}): string {
  if (answer.scope === "recipe") return "Scelto a mano per questa ricetta.";
  const forWhat = answer.context === "dolce" ? "per i dolci" : "per i piatti salati";
  return answer.decided_by === "ai" ? `Suggerito dall'AI ${forWhat}.` : `Scelto a mano ${forWhat}.`;
}

export function recipesText(count: number): string {
  if (count === 0) return "in nessuna ricetta";
  return count === 1 ? "in 1 ricetta" : `in ${count} ricette`;
}

export function overridesText(count: number): string | null {
  if (count === 0) return null;
  return count === 1 ? "Corretto a mano in 1 ricetta." : `Corretto a mano in ${count} ricette.`;
}

/** Il 422 del server porta la frase che dice cosa togliere: si mostra com'è. Un 422 di
 * validazione (con `detail` lista) e ogni altro guasto dicono di riprovare. */
export function saveErrorText(error: unknown): string {
  if (error instanceof ApiError && error.status === 422) {
    const detail = (error.body as { detail?: unknown } | null)?.detail;
    if (typeof detail === "string") return detail;
  }
  return "Non sono riuscito a salvare. Riprova.";
}
```

- [ ] **Step 6: Passano**

Run (da `<worktree>/frontend`): `npx vitest run src/features/substitutes/ && npm run typecheck`
Expected: PASS, 8 test (4 + 4); typecheck pulito. E il comando di pytest con `tests/test_frontend_substitutes.py`: PASS, 1 test.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/substitutes/ backend/tests/test_frontend_substitutes.py
git commit -m "feat(frontend): R5, i tipi, le chiamate e le parole dei sostituti"
```

---

### Task 10: La risposta da leggere e il modulo

**Files:**
- Create: `frontend/src/features/substitutes/SubstituteAnswer.tsx`
- Create: `frontend/src/features/substitutes/SubstituteEditor.tsx`, `SubstituteEditor.test.tsx`

**Interfaces:**
- Consumes: Task 9 (tipi, `saveErrorText`); `IngredientPicker` (`frontend/src/components/IngredientPicker.tsx`, con `kind="food"`, `failureNote`, `emptyNote`, `onPick`); `Button`, `Alert`, `StatusDot`, `buttonClasses`, `IconX`; `capitalizeFirst` (`frontend/src/lib/text.ts`).
- Produces:
  - `SubstituteAnswer({ ingredientName: string; verdict: SubstitutionVerdict; substitutes: readonly (Substitute | LineSubstitute)[] })` — la risposta in frasi; coi `LineSubstitute` aggiunge il pallino della dispensa, «ce l'hai» e «non basta»;
  - `SubstituteEditor<T>({ legend: string; saveLabel: string; initialVerdict: SubstitutionVerdict | null; initialSubstitutes: readonly Substitute[]; save: (body: SubstitutionBody) => Promise<T>; onSaved: (result: T) => void; onCancel: () => void })` — il modulo: tre pastiglie, il selettore del cibo fino a tre, la nota, la ✕, «Salva …» con `busy` e `unavailableReason`, «Annulla». I Task 11 e 12 li montano.

- [ ] **Step 1: I test che falliscono**

Crea `frontend/src/features/substitutes/SubstituteEditor.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ApiError } from "../../api/client";
import type { Ingredient } from "../../domain/types";
import { SubstituteEditor } from "./SubstituteEditor";
import type { Substitute, SubstitutionBody, SubstitutionVerdict } from "./types";

const RISO: Substitute = { ingredient_id: "i-riso", name: "riso", note: "cottura più lunga" };
const FARRO: Substitute = { ingredient_id: "i-farro", name: "farro", note: null };
const ORZO: Substitute = { ingredient_id: "i-orzo", name: "orzo", note: null };
const RISO_IN_ANAGRAFICA: Ingredient = {
  id: "i-riso", name: "riso", display_name: "Riso", category: "cereali", kind: "food",
};

function renderEditor({
  initialVerdict = null,
  initialSubstitutes = [],
  save = vi.fn(async (body: SubstitutionBody) => body),
}: {
  initialVerdict?: SubstitutionVerdict | null;
  initialSubstitutes?: Substitute[];
  save?: (body: SubstitutionBody) => Promise<unknown>;
} = {}) {
  const onSaved = vi.fn();
  const onCancel = vi.fn();
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <SubstituteEditor
        legend="Al posto di pasta, in questa ricetta:"
        saveLabel="Salva per questa ricetta"
        initialVerdict={initialVerdict}
        initialSubstitutes={initialSubstitutes}
        save={save}
        onSaved={onSaved}
        onCancel={onCancel}
      />
    </QueryClientProvider>
  );
  return { save, onSaved, onCancel };
}

function stubSearch() {
  const spy = vi.fn((url: unknown) =>
    Promise.resolve(
      new Response(
        JSON.stringify(String(url).includes("/ingredients/search") ? [RISO_IN_ANAGRAFICA] : []),
        { status: 200 }
      )
    )
  );
  vi.stubGlobal("fetch", spy);
  return spy;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SubstituteEditor", () => {
  it("parte dalla risposta di prima", () => {
    renderEditor({ initialVerdict: "substitutes", initialSubstitutes: [RISO] });
    expect(screen.getByRole("group", { name: "Al posto di pasta, in questa ricetta:" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Un altro ingrediente" })).toBeChecked();
    expect(screen.getByRole("textbox", { name: "Nota per riso" })).toHaveValue("cottura più lunga");
  });

  it("senza sostituti «Salva» dice perché, e non salva", async () => {
    const { save } = renderEditor();
    const salva = screen.getByRole("button", { name: "Salva per questa ricetta" });
    expect(salva).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText("Scegli almeno un ingrediente.")).toBeInTheDocument();
    await userEvent.click(salva);
    expect(save).not.toHaveBeenCalled();
  });

  it("si sceglie dal cibo dell'anagrafica, e lo stesso una volta sola", async () => {
    const spy = stubSearch();
    renderEditor();
    await userEvent.type(screen.getByRole("textbox", { name: "Cosa usare al suo posto" }), "ris");
    await userEvent.click(await screen.findByRole("option", { name: "Riso" }));
    expect(screen.getByRole("textbox", { name: "Nota per riso" })).toHaveValue("");
    expect(String(spy.mock.calls.at(-1)?.[0])).toContain("kind=food");

    await userEvent.type(screen.getByRole("textbox", { name: "Aggiungine un altro" }), "ris");
    await userEvent.click(await screen.findByRole("option", { name: "Riso" }));
    expect(screen.getAllByRole("textbox", { name: "Nota per riso" })).toHaveLength(1);
  });

  it("con tre sostituti non ne offre un quarto", () => {
    renderEditor({ initialVerdict: "substitutes", initialSubstitutes: [RISO, FARRO, ORZO] });
    expect(screen.queryByRole("textbox", { name: "Aggiungine un altro" })).toBeNull();
  });

  it("manda l'esito e i sostituti con le note", async () => {
    const { save, onSaved } = renderEditor({
      initialVerdict: "substitutes", initialSubstitutes: [{ ...RISO, note: null }, FARRO],
    });
    await userEvent.type(screen.getByRole("textbox", { name: "Nota per riso" }), "metà dose");
    await userEvent.click(screen.getByRole("button", { name: "Salva per questa ricetta" }));
    const atteso = {
      verdict: "substitutes",
      substitutes: [{ ingredient_id: "i-riso", note: "metà dose" }, { ingredient_id: "i-farro", note: null }],
    };
    expect(save).toHaveBeenCalledWith(atteso);
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(atteso));
  });

  it("«Si può omettere» non manda sostituti", async () => {
    const { save } = renderEditor({ initialVerdict: "substitutes", initialSubstitutes: [RISO] });
    await userEvent.click(screen.getByRole("radio", { name: "Si può omettere" }));
    expect(screen.queryByRole("textbox", { name: "Nota per riso" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Salva per questa ricetta" }));
    expect(save).toHaveBeenCalledWith({ verdict: "omit", substitutes: [] });
  });

  it("la ✕ toglie un sostituto", async () => {
    renderEditor({ initialVerdict: "substitutes", initialSubstitutes: [RISO] });
    await userEvent.click(screen.getByRole("button", { name: "Togli riso" }));
    expect(screen.queryByRole("textbox", { name: "Nota per riso" })).toBeNull();
    expect(screen.getByRole("button", { name: "Salva per questa ricetta" })).toHaveAttribute(
      "aria-disabled", "true"
    );
  });

  it("il rifiuto del server si legge com'è", async () => {
    const frase = "«Pasta» non può sostituire sé stesso: scegli un altro ingrediente.";
    renderEditor({
      initialVerdict: "substitutes", initialSubstitutes: [RISO],
      save: vi.fn(async () => {
        throw new ApiError(frase, 422, { detail: frase });
      }),
    });
    await userEvent.click(screen.getByRole("button", { name: "Salva per questa ricetta" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(frase);
  });

  it("ogni altro guasto dice di riprovare", async () => {
    renderEditor({
      initialVerdict: "omit",
      save: vi.fn(async () => {
        throw new Error("rete");
      }),
    });
    await userEvent.click(screen.getByRole("button", { name: "Salva per questa ricetta" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Non sono riuscito a salvare. Riprova.");
  });

  it("«Annulla» chiude senza salvare", async () => {
    const { save, onCancel } = renderEditor({ initialVerdict: "omit" });
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(onCancel).toHaveBeenCalled();
    expect(save).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Fallisce**

Run (da `<worktree>/frontend`): `npx vitest run src/features/substitutes/SubstituteEditor.test.tsx`
Expected: FAIL, `./SubstituteEditor` non esiste.

- [ ] **Step 3: La risposta da leggere**

Crea `frontend/src/features/substitutes/SubstituteAnswer.tsx`:

```tsx
import { StatusDot } from "../../components/ui/StatusDot";
import { capitalizeFirst } from "../../lib/text";
import type { LineSubstitute, Substitute, SubstitutionVerdict } from "./types";

/** Una risposta di «Sostituisci», da leggere (R5): nel pannello della ricetta, coi
 * pallini della dispensa, e in Anagrafica, senza. Se un sostituto basta lo dice il server
 * (`satisfied`, la stessa regola delle righe): qui si legge, non si giudica. Il nome
 * dentro la frase resta minuscolo; a inizio riga la maiuscola, solo a video. */
export function SubstituteAnswer({
  ingredientName,
  verdict,
  substitutes,
}: {
  ingredientName: string;
  verdict: SubstitutionVerdict;
  substitutes: readonly (Substitute | LineSubstitute)[];
}) {
  if (verdict === "omit") {
    return <p className="text-sm">{`Si può omettere: il piatto riesce anche senza ${ingredientName}.`}</p>;
  }
  if (verdict === "irreplaceable") {
    return <p className="text-sm">{`Insostituibile: senza ${ingredientName} il piatto non si fa.`}</p>;
  }
  return (
    <div>
      <p className="text-sm text-ink-soft">{`Al posto di ${ingredientName}:`}</p>
      <ul>
        {substitutes.map((substitute) => (
          <li key={substitute.ingredient_id} className="flex items-center gap-2 py-1 text-sm">
            {"availability" in substitute && <StatusDot availability={substitute.availability} />}
            <span className="min-w-0">
              <span className="font-medium">{capitalizeFirst(substitute.name)}</span>
              {substitute.note && <span className="text-ink-soft"> · {substitute.note}</span>}
              {"satisfied" in substitute && substitute.satisfied && (
                <span className="ml-2 text-xs font-medium text-brand">ce l'hai</span>
              )}
              {"satisfied" in substitute && !substitute.satisfied && substitute.availability === "low" && (
                <span className="ml-2 text-xs font-medium text-low">non basta</span>
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 4: Il modulo**

Crea `frontend/src/features/substitutes/SubstituteEditor.tsx`:

```tsx
import { useId, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { IngredientPicker } from "../../components/IngredientPicker";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { IconX } from "../../components/ui/icons";
import type { Ingredient } from "../../domain/types";
import { capitalizeFirst } from "../../lib/text";
import {
  SUBSTITUTE_NOTE_MAX,
  SUBSTITUTES_MAX,
  type Substitute,
  type SubstitutionBody,
  type SubstitutionVerdict,
} from "./types";
import { saveErrorText } from "./wording";

const CHOICES: { value: SubstitutionVerdict; label: string }[] = [
  { value: "substitutes", label: "Un altro ingrediente" },
  { value: "omit", label: "Si può omettere" },
  { value: "irreplaceable", label: "Insostituibile" },
];

type Chosen = { id: string; name: string; note: string };

/** Scrivere a mano una risposta di «Sostituisci» (R5): nella ricetta per quella ricetta
 * («Non va bene qui», «Scrivi tu»), in Anagrafica per un contesto. Chi lo monta dice dove
 * salvare (`save`) e cosa fare dopo (`onSaved`).
 *
 * I tre esiti sono pastiglie su radio veri, come i filtri del ricettario
 * (`MissingBudgetFilter`): la scelta singola e la tastiera sono del browser. Un sostituto
 * si sceglie solo dal cibo dell'anagrafica (decisione 2 di Mattia): niente «Aggiungi»
 * qui. Senza un `<form>`: l'Invio nel selettore non deve salvare a metà. */
export function SubstituteEditor<T>({
  legend,
  saveLabel,
  initialVerdict,
  initialSubstitutes,
  save,
  onSaved,
  onCancel,
}: {
  legend: string;
  saveLabel: string;
  initialVerdict: SubstitutionVerdict | null;
  initialSubstitutes: readonly Substitute[];
  save: (body: SubstitutionBody) => Promise<T>;
  onSaved: (result: T) => void;
  onCancel: () => void;
}) {
  const [verdict, setVerdict] = useState<SubstitutionVerdict>(initialVerdict ?? "substitutes");
  const [chosen, setChosen] = useState<Chosen[]>(
    initialSubstitutes.map((substitute) => ({
      id: substitute.ingredient_id,
      name: substitute.name,
      note: substitute.note ?? "",
    }))
  );
  const group = useId();
  const mutation = useMutation({
    mutationFn: (body: SubstitutionBody) => save(body),
    onSuccess: (result) => onSaved(result),
  });

  function pick(ingredient: Ingredient) {
    // lo stesso ingrediente scelto due volte non aggiunge una riga: c'è già
    setChosen((current) =>
      current.some((item) => item.id === ingredient.id)
        ? current
        : [...current, { id: ingredient.id, name: ingredient.name, note: "" }]
    );
  }

  function submit() {
    mutation.mutate({
      verdict,
      substitutes:
        verdict === "substitutes"
          ? chosen.map((item) => ({
              ingredient_id: item.id,
              // gli spazi li pulisce il server; vuota non è una nota
              note: item.note.trim() === "" ? null : item.note,
            }))
          : [],
    });
  }

  const reason = verdict === "substitutes" && chosen.length === 0 ? "Scegli almeno un ingrediente." : undefined;

  return (
    <div className="flex flex-col gap-3">
      <fieldset>
        <legend className="pb-1.5 text-sm font-medium text-ink-soft">{legend}</legend>
        <div className="flex flex-wrap gap-2">
          {CHOICES.map((choice) => {
            const checked = choice.value === verdict;
            return (
              <label key={choice.value}>
                <input
                  type="radio"
                  name={group}
                  className="peer sr-only"
                  checked={checked}
                  onChange={() => setVerdict(choice.value)}
                />
                <span
                  className={`${buttonClasses(checked ? "primary" : "secondary", "pill")} peer-focus-visible:ring-2 peer-focus-visible:ring-brand peer-focus-visible:ring-offset-2`}
                >
                  {choice.label}
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>

      {verdict === "substitutes" && (
        <>
          {chosen.length > 0 && (
            <ul className="flex flex-col gap-2">
              {chosen.map((item) => (
                <li key={item.id} className="flex items-end gap-2">
                  <label className="min-w-0 flex-1 text-sm font-medium">
                    {capitalizeFirst(item.name)}
                    <input
                      aria-label={`Nota per ${item.name}`}
                      value={item.note}
                      maxLength={SUBSTITUTE_NOTE_MAX}
                      placeholder="Nota, per esempio: metà dose"
                      onChange={(event) => {
                        const note = event.target.value;
                        setChosen((current) =>
                          current.map((other) => (other.id === item.id ? { ...other, note } : other))
                        );
                      }}
                      className="mt-1.5"
                    />
                  </label>
                  <Button
                    variant="ghost"
                    icon={IconX}
                    label={`Togli ${item.name}`}
                    onClick={() => setChosen((current) => current.filter((other) => other.id !== item.id))}
                  />
                </li>
              ))}
            </ul>
          )}
          {chosen.length < SUBSTITUTES_MAX && (
            <IngredientPicker
              label={chosen.length === 0 ? "Cosa usare al suo posto" : "Aggiungine un altro"}
              kind="food"
              failureNote="Puoi scegliere «Si può omettere» o «Insostituibile»."
              emptyNote="Non è in anagrafica: un sostituto si sceglie fra gli ingredienti che ci sono."
              onPick={pick}
            />
          )}
        </>
      )}

      {mutation.isError && <Alert>{saveErrorText(mutation.error)}</Alert>}

      <div className="flex flex-col items-start gap-2">
        <Button variant="primary" busy={mutation.isPending} unavailableReason={reason} onClick={submit}>
          {saveLabel}
        </Button>
        <Button variant="ghost" onClick={onCancel}>
          Annulla
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Passano**

Run (da `<worktree>/frontend`): `npx vitest run src/features/substitutes/ && npm run typecheck && npm run lint`
Expected: PASS (10 test nuovi del modulo, più gli 8 del Task 9); typecheck e lint puliti.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/substitutes/SubstituteAnswer.tsx frontend/src/features/substitutes/SubstituteEditor.tsx frontend/src/features/substitutes/SubstituteEditor.test.tsx
git commit -m "feat(frontend): R5, la risposta da leggere e il modulo dei sostituti"
```

---

### Task 11: Il pannello nella ricetta

**Files:**
- Create: `frontend/src/features/substitutes/SubstitutePanel.tsx`, `SubstitutePanel.test.tsx`
- Modify: `frontend/src/components/ui/icons.ts` (un export)
- Modify: `frontend/src/features/cooking/RecipeDetailScreen.tsx` (gli import, `IngredientRow`, il punto in cui le righe si disegnano)
- Test: `frontend/src/features/cooking/RecipeDetailScreen.test.tsx` (due test in fondo)

**Interfaces:**
- Consumes: Task 9 (`loadLineSubstitution`, `saveLineSubstitution`, `resetLineSubstitution`, `provenanceText`, `LineSubstitution`), Task 10 (`SubstituteAnswer`, `SubstituteEditor`).
- Produces: `substitutionKey(recipeId: string, ingredientId: string)` (la chiave di query `["substitution", recipeId, ingredientId]`, il Task 12 invalida `["substitution"]`); `SubstitutePanel({ recipeId: string; ingredientId: string; ingredientName: string })`; `IconArrowsExchange` in `icons.ts`; in `IngredientRow` il pulsante «Sostituisci {nome}».

- [ ] **Step 1: I test del pannello, che falliscono**

Crea `frontend/src/features/substitutes/SubstitutePanel.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SubstitutePanel } from "./SubstitutePanel";
import type { LineSubstitution } from "./types";

const LINE = "/api/v1/recipes/r1/substitutes/i-pasta";
const GENERALE: LineSubstitution = {
  ingredient_id: "i-pasta", ingredient_name: "pasta", context: "salato", scope: "general",
  verdict: "substitutes", decided_by: "ai", ai_failed: false,
  substitutes: [
    { ingredient_id: "i-riso", name: "riso", note: "cottura più lunga", availability: "available", satisfied: true },
    { ingredient_id: "i-farro", name: "farro", note: null, availability: "low", satisfied: false },
  ],
};
const VUOTA: LineSubstitution = { ...GENERALE, scope: null, verdict: null, decided_by: null, substitutes: [] };
const CORRETTA: LineSubstitution = {
  ...GENERALE, scope: "recipe", decided_by: "human", verdict: "irreplaceable", substitutes: [],
};

type FetchRoute = (path: string, method: string, init?: RequestInit) => [unknown, number];

function stubRoutedFetch(route: FetchRoute) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = route(String(url), init?.method ?? "GET", init);
    return Promise.resolve(
      status === 204 ? new Response(null, { status }) : new Response(JSON.stringify(body), { status })
    );
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function callsTo(spy: ReturnType<typeof stubRoutedFetch>, method: string, path: string) {
  return spy.mock.calls.filter(
    ([url, init]) => String(url) === path && ((init as RequestInit | undefined)?.method ?? "GET") === method
  );
}

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <SubstitutePanel recipeId="r1" ingredientId="i-pasta" ingredientName="pasta" />
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SubstitutePanel", () => {
  it("dice la voce generale dell'AI, con quel che c'è in dispensa", async () => {
    const spy = stubRoutedFetch(() => [GENERALE, 200]);
    renderPanel();
    expect(await screen.findByText("Al posto di pasta:")).toBeInTheDocument();
    expect(screen.getByText("Riso")).toBeInTheDocument();
    expect(screen.getByText("· cottura più lunga")).toBeInTheDocument();
    expect(screen.getByText("ce l'hai")).toBeInTheDocument();
    expect(screen.getByText("non basta")).toBeInTheDocument();
    expect(screen.getByText("Suggerito dall'AI per i piatti salati.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Non va bene qui" })).toBeInTheDocument();
    expect(callsTo(spy, "POST", `${LINE}/ask`)).toHaveLength(0);
  });

  it("senza una risposta la chiede, e mentre aspetta lo dice", async () => {
    stubRoutedFetch((_path, method) => [method === "POST" ? GENERALE : VUOTA, 200]);
    renderPanel();
    expect(screen.getByRole("status")).toHaveTextContent("Cerco cosa usare al posto di pasta…");
    expect(await screen.findByText("Suggerito dall'AI per i piatti salati.")).toBeInTheDocument();
  });

  it("se l'AI non risponde lascia «Riprova» e «Scrivi tu»", async () => {
    const spy = stubRoutedFetch((_path, method) => [method === "POST" ? { ...VUOTA, ai_failed: true } : VUOTA, 200]);
    renderPanel();
    expect(await screen.findByText("Nessun suggerimento ancora.")).toBeInTheDocument();
    expect(callsTo(spy, "POST", `${LINE}/ask`)).toHaveLength(1);

    await userEvent.click(screen.getByRole("button", { name: "Riprova" }));
    await waitFor(() => expect(callsTo(spy, "POST", `${LINE}/ask`)).toHaveLength(2));

    await userEvent.click(screen.getByRole("button", { name: "Scrivi tu" }));
    expect(screen.getByRole("group", { name: "Al posto di pasta, in questa ricetta:" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Un altro ingrediente" })).toBeChecked();
  });

  it("«si può omettere» è una frase", async () => {
    stubRoutedFetch(() => [{ ...GENERALE, verdict: "omit", substitutes: [] }, 200]);
    renderPanel();
    expect(await screen.findByText("Si può omettere: il piatto riesce anche senza pasta.")).toBeInTheDocument();
  });

  it("«insostituibile» è una frase", async () => {
    stubRoutedFetch(() => [{ ...GENERALE, verdict: "irreplaceable", substitutes: [] }, 200]);
    renderPanel();
    expect(await screen.findByText("Insostituibile: senza pasta il piatto non si fa.")).toBeInTheDocument();
  });

  it("«Non va bene qui» salva una correzione per questa ricetta", async () => {
    const spy = stubRoutedFetch((_path, method) => [method === "PUT" ? CORRETTA : GENERALE, 200]);
    renderPanel();
    await userEvent.click(await screen.findByRole("button", { name: "Non va bene qui" }));
    expect(screen.getByRole("textbox", { name: "Nota per riso" })).toHaveValue("cottura più lunga");
    await userEvent.click(screen.getByRole("radio", { name: "Insostituibile" }));
    await userEvent.click(screen.getByRole("button", { name: "Salva per questa ricetta" }));

    expect(await screen.findByText("Insostituibile: senza pasta il piatto non si fa.")).toBeInTheDocument();
    expect(screen.getByText("Scelto a mano per questa ricetta.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Torna al suggerimento generale" })).toBeInTheDocument();
    // chiuso il modulo, il fuoco torna al pulsante che apre il modulo
    expect(screen.getByRole("button", { name: "Cambia" })).toHaveFocus();
    const [put] = callsTo(spy, "PUT", LINE);
    expect(JSON.parse(String((put[1] as RequestInit).body))).toEqual({ verdict: "irreplaceable", substitutes: [] });
  });

  it("«Torna al suggerimento generale» toglie la correzione e rilegge", async () => {
    let corretta = true;
    const spy = stubRoutedFetch((_path, method) => {
      if (method === "DELETE") {
        corretta = false;
        return [null, 204];
      }
      return [corretta ? CORRETTA : GENERALE, 200];
    });
    renderPanel();
    await userEvent.click(await screen.findByRole("button", { name: "Torna al suggerimento generale" }));
    expect(await screen.findByText("Suggerito dall'AI per i piatti salati.")).toBeInTheDocument();
    expect(callsTo(spy, "DELETE", LINE)).toHaveLength(1);
  });

  it("una riga che non c'è più lo dice, senza «Riprova»", async () => {
    stubRoutedFetch(() => [{ detail: "Questo ingrediente non è nella ricetta." }, 404]);
    renderPanel();
    expect(
      await screen.findByText("Questo ingrediente non è più nella ricetta: ricarica la pagina.")
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Riprova" })).toBeNull();
  });

  it("un guasto del server lascia «Riprova»", async () => {
    stubRoutedFetch(() => [{ detail: "x" }, 500]);
    renderPanel();
    expect(await screen.findByText("Non sono riuscito a leggere i sostituti.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Riprova" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Fallisce**

Run (da `<worktree>/frontend`): `npx vitest run src/features/substitutes/SubstitutePanel.test.tsx`
Expected: FAIL, `./SubstitutePanel` non esiste.

- [ ] **Step 3: Il pannello**

Crea `frontend/src/features/substitutes/SubstitutePanel.tsx`:

```tsx
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError } from "../../api/client";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { loadLineSubstitution, resetLineSubstitution, saveLineSubstitution } from "./api";
import { SubstituteAnswer } from "./SubstituteAnswer";
import { SubstituteEditor } from "./SubstituteEditor";
import type { LineSubstitution } from "./types";
import { provenanceText } from "./wording";

/** La chiave della risposta di una riga: l'Anagrafica invalida `["substitution"]` quando
 * cambia una voce generale. */
export function substitutionKey(recipeId: string, ingredientId: string) {
  return ["substitution", recipeId, ingredientId] as const;
}

/** Sotto una riga d'ingrediente, cosa usare al suo posto (R5).
 *
 * Legge la risposta che vale per la riga; se non c'è, il server la chiede all'AI adesso
 * e la salva (`loadLineSubstitution`). Se l'AI non risponde, «Nessun suggerimento
 * ancora.» con «Riprova» e «Scrivi tu»: mai un vicolo cieco. Da qui si scrive solo la
 * correzione di questa ricetta; la voce generale si corregge in Anagrafica. */
export function SubstitutePanel({
  recipeId,
  ingredientId,
  ingredientName,
}: {
  recipeId: string;
  ingredientId: string;
  ingredientName: string;
}) {
  const queryClient = useQueryClient();
  const key = substitutionKey(recipeId, ingredientId);
  const [editing, setEditing] = useState(false);
  const query = useQuery({ queryKey: key, queryFn: () => loadLineSubstitution(recipeId, ingredientId) });
  const reset = useMutation({
    mutationFn: () => resetLineSubstitution(recipeId, ingredientId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  // Chiuso il modulo — salvato o annullato — il fuoco torna sul pulsante che apre il
  // modulo: quello che l'aveva si è smontato col modulo, e cadrebbe sul `body`. Un `ref`
  // e non uno stato: è un'intenzione per il prossimo disegno (la stessa forma di «Cucina»).
  const actionRef = useRef<HTMLButtonElement>(null);
  const refocus = useRef(false);
  useEffect(() => {
    if (editing || !refocus.current) return;
    refocus.current = false;
    actionRef.current?.focus();
  }, [editing]);
  function closeEditor() {
    refocus.current = true;
    setEditing(false);
  }

  let body: ReactNode;
  if (query.isPending) {
    body = (
      <p role="status" className="text-sm text-ink-soft">
        {`Cerco cosa usare al posto di ${ingredientName}…`}
      </p>
    );
  } else if (query.isError) {
    // una riga che non c'è più (la ricetta è cambiata) non torna riprovando
    const gone = query.error instanceof ApiError && query.error.status === 404;
    body = (
      <div className="flex flex-col items-start gap-2">
        <Alert>
          {gone
            ? "Questo ingrediente non è più nella ricetta: ricarica la pagina."
            : "Non sono riuscito a leggere i sostituti."}
        </Alert>
        {!gone && (
          <Button busy={query.isFetching} onClick={() => void query.refetch()}>
            Riprova
          </Button>
        )}
      </div>
    );
  } else if (editing) {
    body = (
      <SubstituteEditor
        legend={`Al posto di ${ingredientName}, in questa ricetta:`}
        saveLabel="Salva per questa ricetta"
        initialVerdict={query.data.verdict}
        initialSubstitutes={query.data.substitutes}
        save={(answer) => saveLineSubstitution(recipeId, ingredientId, answer)}
        onSaved={(saved: LineSubstitution) => {
          queryClient.setQueryData(key, saved);
          closeEditor();
        }}
        onCancel={closeEditor}
      />
    );
  } else if (query.data.verdict === null) {
    body = (
      <>
        <p className="text-sm text-ink-soft">Nessun suggerimento ancora.</p>
        <div className="flex flex-wrap gap-2 pt-2">
          <Button busy={query.isFetching} onClick={() => void query.refetch()}>
            Riprova
          </Button>
          <Button ref={actionRef} onClick={() => setEditing(true)}>
            Scrivi tu
          </Button>
        </div>
      </>
    );
  } else {
    const data = query.data;
    // il ramo sopra ha escluso `null`: TypeScript lo sa su `query.data.verdict`, non su `data`
    const verdict = query.data.verdict;
    body = (
      <>
        <SubstituteAnswer ingredientName={ingredientName} verdict={verdict} substitutes={data.substitutes} />
        <p className="pt-1 text-xs text-ink-faint">{provenanceText(data)}</p>
        <div className="flex flex-wrap gap-2 pt-2">
          <Button ref={actionRef} onClick={() => setEditing(true)}>
            {data.scope === "recipe" ? "Cambia" : "Non va bene qui"}
          </Button>
          {data.scope === "recipe" && (
            <Button variant="ghost" busy={reset.isPending} onClick={() => reset.mutate()}>
              Torna al suggerimento generale
            </Button>
          )}
        </div>
        {reset.isError && (
          <Alert className="pt-2">Non sono riuscito a tornare al suggerimento generale. Riprova.</Alert>
        )}
      </>
    );
  }

  // rientrato sotto il nome: il pallino della riga è largo 12 px, più lo spazio
  return <div className="pt-2 pl-6">{body}</div>;
}
```

Se `npm run typecheck` non restringe `query.data.verdict` (dipende da come TanStack Query tipa `data` sul ramo), non usare la `!`: scrivi `if (verdict === null) return null;` subito dopo la costante — il caso non si raggiunge — e annotalo nel report.

- [ ] **Step 4: L'icona**

In `frontend/src/components/ui/icons.ts` (leggilo com'è sul ramo), subito dopo il blocco che comincia con `// ricette` e finisce con `} from "@tabler/icons-react";`, aggiungi un blocco suo:

```ts
// sostituti (R5): «Sostituisci» in fondo a ogni riga d'ingrediente della ricetta
export { IconArrowsExchange } from "@tabler/icons-react";
```

- [ ] **Step 5: I test del dettaglio, che falliscono**

In fondo a `frontend/src/features/cooking/RecipeDetailScreen.test.tsx` (i nomi `DETAIL`, `PANTRY`, `renderScreen`, `stubFetch` sono quelli in cima al file) aggiungi:

```tsx
describe("RecipeDetailScreen — Sostituisci (R5)", () => {
  it("ogni riga d'ingrediente ha «Sostituisci», chiuso", async () => {
    stubFetch({});
    renderScreen();
    for (const nome of ["pasta", "pomodoro", "aglio", "basilico", "olio"]) {
      expect(await screen.findByRole("button", { name: `Sostituisci ${nome}` })).toHaveAttribute(
        "aria-expanded", "false"
      );
    }
  });

  it("il tocco apre sotto la riga cosa usare al suo posto, un secondo tocco lo chiude", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: unknown) => {
        const path = String(url);
        const corpo = path.includes("/substitutes/i4")
          ? { ingredient_id: "i4", ingredient_name: "basilico", context: "salato", scope: "general",
              verdict: "omit", decided_by: "ai", ai_failed: false, substitutes: [] }
          : path.includes("/pantry")
            ? PANTRY
            : DETAIL;
        return Promise.resolve(new Response(JSON.stringify(corpo), { status: 200 }));
      })
    );
    renderScreen();
    const apri = await screen.findByRole("button", { name: "Sostituisci basilico" });
    await userEvent.click(apri);
    const riga = apri.closest("li")!;
    expect(
      await within(riga).findByText("Si può omettere: il piatto riesce anche senza basilico.")
    ).toBeInTheDocument();
    expect(apri).toHaveAttribute("aria-expanded", "true");

    await userEvent.click(apri);
    expect(within(riga).queryByText("Si può omettere: il piatto riesce anche senza basilico.")).toBeNull();
    expect(apri).toHaveFocus();
  });
});
```

Run: `npx vitest run src/features/cooking/RecipeDetailScreen.test.tsx`
Expected: FAIL, nessun pulsante «Sostituisci …».

- [ ] **Step 6: La riga del dettaglio**

In `frontend/src/features/cooking/RecipeDetailScreen.tsx` (leggilo com'è sul ramo):

1. Nell'import da `"../../components/ui/icons"` aggiungi `IconArrowsExchange,` in testa all'elenco.
2. Dopo `import { capitalizeFirst } from "../../lib/text";` aggiungi:
   ```tsx
   import { SubstitutePanel } from "../substitutes/SubstitutePanel";
   ```
3. La funzione `IngredientRow` (il commento sopra di lei resta; aggiungi in fondo al commento la riga «In fondo, «Sostituisci» (R5): apre sotto la riga cosa usare al suo posto.») diventa:

```tsx
function IngredientRow({ line, recipeId }: { line: RecipeIngredientLine; recipeId: string }) {
  // R5: lo stato del pannello è della riga. Due pannelli aperti insieme non si danno
  // fastidio, e uscire dalla ricetta li chiude tutti
  const [substituting, setSubstituting] = useState(false);
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
        {line.quantity_display && (
          <span className="shrink-0 text-sm text-ink-faint">{line.quantity_display}</span>
        )}
        {/* Un'icona sola (spec T3 §2: più pulsanti uguali in fila → solo icone), col nome
            per chi ascolta. `-my-2.5` restituisce il `py-2.5` della riga: il bersaglio è
            44 px senza alzarla; `-mr-2` lo avvicina al bordo. Il fuoco resta qui quando si
            chiude, perché il pulsante non si smonta. */}
        <Button
          variant="ghost"
          icon={IconArrowsExchange}
          label={`Sostituisci ${line.ingredient_name}`}
          aria-expanded={substituting}
          onClick={() => setSubstituting((open) => !open)}
          className="-my-2.5 -mr-2 shrink-0"
        />
      </div>
      {substituting && (
        <SubstitutePanel
          recipeId={recipeId}
          ingredientId={line.ingredient_id}
          ingredientName={line.ingredient_name}
        />
      )}
    </li>
  );
}
```

4. Dove le righe si disegnano, `<IngredientRow key={line.ingredient_id} line={line} />` diventa:
   ```tsx
   <IngredientRow key={line.ingredient_id} line={line} recipeId={recipe.id} />
   ```

- [ ] **Step 7: Passano, e tutto il frontend**

Run (da `<worktree>/frontend`): `npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde (11 test nuovi: 9 del pannello, 2 del dettaglio); i test di oggi del dettaglio passano senza cambiare (il pulsante è di sola icona: il testo delle righe resta «Pasta180 g»). Se un test di oggi conta i pulsanti di una riga, **fermati e scrivilo nel report**: non va indebolito; va ristretto per nome, e il report dice quale e perché.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/features/substitutes/SubstitutePanel.tsx frontend/src/features/substitutes/SubstitutePanel.test.tsx frontend/src/components/ui/icons.ts frontend/src/features/cooking/RecipeDetailScreen.tsx frontend/src/features/cooking/RecipeDetailScreen.test.tsx
git commit -m "feat(ricette): R5, «Sostituisci» in fondo a ogni riga e il pannello sotto, con la correzione per la ricetta"
```

---

### Task 12: La sezione «Sostituti» in Anagrafica

**Files:**
- Create: `frontend/src/features/substitutes/IngredientSubstitutes.tsx`, `IngredientSubstitutes.test.tsx`
- Modify: `frontend/src/features/registry/IngredientScreen.tsx` (un import, la sezione in fondo)
- Test: `frontend/src/features/registry/IngredientScreen.test.tsx` (una riga in `base()`, due test in fondo)

**Interfaces:**
- Consumes: Task 9 (`fetchIngredientSubstitutions`, `saveIngredientSubstitution`, le parole), Task 10 (`SubstituteAnswer`, `SubstituteEditor`); `Card`, `SectionHeading`, `Button`.
- Produces: `IngredientSubstitutes({ ingredientId: string; ingredientName: string })` — la sezione, con la chiave di query `["registry", "substitutes", ingredientId]` (sotto `"registry"`: le correzioni dell'anagrafica la invalidano già, `TOUCHED` in `registry/api.ts`); dopo ogni scrittura invalida `["substitution"]`, i pannelli delle ricette.

- [ ] **Step 1: I test della sezione, che falliscono**

Crea `frontend/src/features/substitutes/IngredientSubstitutes.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { IngredientSubstitutes } from "./IngredientSubstitutes";
import type { IngredientSubstitutions } from "./types";

const BASE = "/api/v1/ingredients/i-burro/substitutes";
const SCHEDA: IngredientSubstitutions = {
  ingredient_id: "i-burro",
  recipe_overrides: 2,
  contexts: [
    { context: "salato", recipes: 1, verdict: "substitutes", decided_by: "ai",
      substitutes: [{ ingredient_id: "i-margarina", name: "margarina", note: "metà dose" }] },
    { context: "dolce", recipes: 12, verdict: null, decided_by: null, substitutes: [] },
  ],
};

type FetchRoute = (path: string, method: string, init?: RequestInit) => [unknown, number];

function stubRoutedFetch(route: FetchRoute) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = route(String(url), init?.method ?? "GET", init);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function renderSection() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <IngredientSubstitutes ingredientId="i-burro" ingredientName="burro" />
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("IngredientSubstitutes", () => {
  it("una scheda per contesto, la voce dell'AI da rivedere, le correzioni delle ricette", async () => {
    stubRoutedFetch(() => [SCHEDA, 200]);
    renderSection();
    expect(await screen.findByRole("heading", { name: "Nei piatti salati · in 1 ricetta" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Sostituti" })).toBeInTheDocument();
    expect(screen.getByText("Margarina")).toBeInTheDocument();
    expect(screen.getByText("Deciso dall'AI: da rivedere.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Va bene così: nei piatti salati" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Correggi: nei piatti salati" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Nei dolci · in 12 ricette" })).toBeInTheDocument();
    expect(
      screen.getByText("Nessun suggerimento ancora: lo chiedo all'AI la prima volta che lo sostituisci in una ricetta.")
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Scrivi tu: nei dolci" })).toBeInTheDocument();
    expect(screen.getByText("Corretto a mano in 2 ricette.")).toBeInTheDocument();
  });

  it("«Va bene così» rimanda la risposta com'è, e diventa scelta a mano", async () => {
    const confermata: IngredientSubstitutions = {
      ...SCHEDA, contexts: [{ ...SCHEDA.contexts[0], decided_by: "human" }, SCHEDA.contexts[1]],
    };
    const spy = stubRoutedFetch((_path, method) => [method === "PUT" ? confermata : SCHEDA, 200]);
    renderSection();
    await userEvent.click(await screen.findByRole("button", { name: "Va bene così: nei piatti salati" }));

    expect(await screen.findByText("Scelto a mano.")).toBeInTheDocument();
    expect(screen.queryByText("Deciso dall'AI: da rivedere.")).toBeNull();
    const put = spy.mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === "PUT")!;
    expect(String(put[0])).toBe(`${BASE}/salato`);
    expect(JSON.parse(String((put[1] as RequestInit).body))).toEqual({
      verdict: "substitutes", substitutes: [{ ingredient_id: "i-margarina", note: "metà dose" }],
    });
  });

  it("«Scrivi tu» scrive la voce dolce", async () => {
    const scritta: IngredientSubstitutions = {
      ...SCHEDA,
      contexts: [SCHEDA.contexts[0], { context: "dolce", recipes: 12, verdict: "irreplaceable", decided_by: "human", substitutes: [] }],
    };
    const spy = stubRoutedFetch((_path, method) => [method === "PUT" ? scritta : SCHEDA, 200]);
    renderSection();
    await userEvent.click(await screen.findByRole("button", { name: "Scrivi tu: nei dolci" }));
    expect(screen.getByRole("group", { name: "Al posto di burro, nei dolci:" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "Insostituibile" }));
    await userEvent.click(screen.getByRole("button", { name: "Salva" }));

    expect(await screen.findByText("Insostituibile: senza burro il piatto non si fa.")).toBeInTheDocument();
    const put = spy.mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === "PUT")!;
    expect(String(put[0])).toBe(`${BASE}/dolce`);
  });

  it("«Annulla» chiude il modulo e ridà il fuoco a «Correggi»", async () => {
    stubRoutedFetch(() => [SCHEDA, 200]);
    renderSection();
    await userEvent.click(await screen.findByRole("button", { name: "Correggi: nei piatti salati" }));
    expect(screen.getByRole("textbox", { name: "Nota per margarina" })).toHaveValue("metà dose");
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(screen.getByRole("button", { name: "Correggi: nei piatti salati" })).toHaveFocus();
  });

  it("un ingrediente in nessuna ricetta lo dice", async () => {
    stubRoutedFetch(() => [{ ingredient_id: "i-burro", contexts: [], recipe_overrides: 0 }, 200]);
    renderSection();
    expect(
      await screen.findByText("Non è in nessuna ricetta: i sostituti servono dentro una ricetta.")
    ).toBeInTheDocument();
  });

  it("un guasto lascia «Riprova»", async () => {
    stubRoutedFetch(() => [{ detail: "x" }, 500]);
    renderSection();
    expect(await screen.findByText("Non sono riuscito a leggere i sostituti.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Riprova a leggere i sostituti" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Fallisce**

Run (da `<worktree>/frontend`): `npx vitest run src/features/substitutes/IngredientSubstitutes.test.tsx`
Expected: FAIL, `./IngredientSubstitutes` non esiste.

- [ ] **Step 3: La sezione**

Crea `frontend/src/features/substitutes/IngredientSubstitutes.tsx`:

```tsx
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { fetchIngredientSubstitutions, saveIngredientSubstitution } from "./api";
import { SubstituteAnswer } from "./SubstituteAnswer";
import { SubstituteEditor } from "./SubstituteEditor";
import type { ContextSubstitution, IngredientSubstitutions, SubstitutionVerdict } from "./types";
import { contextIn, contextTitle, overridesText, recipesText, saveErrorText } from "./wording";

/** «Sostituti» nella scheda di un ingrediente (R5): una scheda per contesto, la voce
 * dell'AI segnata da rivedere — sul modello delle decisioni della coda —, la voce scritta
 * a mano, e quante ricette hanno una correzione loro. Qui si scrive la voce generale;
 * le correzioni delle ricette si scrivono nelle ricette. */
export function IngredientSubstitutes({
  ingredientId,
  ingredientName,
}: {
  ingredientId: string;
  ingredientName: string;
}) {
  const queryClient = useQueryClient();
  const key = ["registry", "substitutes", ingredientId] as const;
  const query = useQuery({ queryKey: key, queryFn: () => fetchIngredientSubstitutions(ingredientId) });

  function saved(data: IngredientSubstitutions) {
    queryClient.setQueryData(key, data);
    // i pannelli delle ricette rileggono: la voce generale è cambiata
    void queryClient.invalidateQueries({ queryKey: ["substitution"] });
  }

  let content: ReactNode;
  if (query.isPending) {
    content = <p className="px-1 text-sm text-ink-soft">Carico…</p>;
  } else if (query.isError) {
    content = (
      <div className="flex flex-col items-start gap-2 px-1">
        <p className="text-sm text-ink-soft">Non sono riuscito a leggere i sostituti.</p>
        <Button
          accessibleName="Riprova a leggere i sostituti"
          busy={query.isFetching}
          onClick={() => void query.refetch()}
        >
          Riprova
        </Button>
      </div>
    );
  } else if (query.data.contexts.length === 0) {
    content = (
      <p className="px-1 text-sm text-ink-soft">
        Non è in nessuna ricetta: i sostituti servono dentro una ricetta.
      </p>
    );
  } else {
    const overrides = overridesText(query.data.recipe_overrides);
    content = (
      <>
        {query.data.contexts.map((item) => (
          <ContextCard
            key={item.context}
            ingredientId={ingredientId}
            ingredientName={ingredientName}
            item={item}
            onSaved={saved}
          />
        ))}
        {overrides && <p className="px-1 text-sm text-ink-soft">{overrides}</p>}
      </>
    );
  }

  return (
    <section>
      <SectionHeading>Sostituti</SectionHeading>
      {content}
    </section>
  );
}

function ContextCard({
  ingredientId,
  ingredientName,
  item,
  onSaved,
}: {
  ingredientId: string;
  ingredientName: string;
  item: ContextSubstitution;
  onSaved: (data: IngredientSubstitutions) => void;
}) {
  const [editing, setEditing] = useState(false);
  const where = contextIn(item.context);
  // «Va bene così» rimanda la risposta com'è: il server la scrive scelta a mano
  const confirm = useMutation({
    mutationFn: (verdict: SubstitutionVerdict) =>
      saveIngredientSubstitution(ingredientId, item.context, {
        verdict,
        substitutes: item.substitutes.map((substitute) => ({
          ingredient_id: substitute.ingredient_id,
          note: substitute.note,
        })),
      }),
    onSuccess: (data) => onSaved(data),
  });

  // chiuso il modulo, il fuoco torna sul pulsante che lo apre (come nel pannello della ricetta)
  const actionRef = useRef<HTMLButtonElement>(null);
  const refocus = useRef(false);
  useEffect(() => {
    if (editing || !refocus.current) return;
    refocus.current = false;
    actionRef.current?.focus();
  }, [editing]);
  function closeEditor() {
    refocus.current = true;
    setEditing(false);
  }

  let body: ReactNode;
  if (editing) {
    body = (
      <div className="pt-2">
        <SubstituteEditor
          legend={`Al posto di ${ingredientName}, ${where}:`}
          saveLabel="Salva"
          initialVerdict={item.verdict}
          initialSubstitutes={item.substitutes}
          save={(answer) => saveIngredientSubstitution(ingredientId, item.context, answer)}
          onSaved={(data: IngredientSubstitutions) => {
            onSaved(data);
            closeEditor();
          }}
          onCancel={closeEditor}
        />
      </div>
    );
  } else if (item.verdict === null) {
    body = (
      <>
        <p className="pt-1 text-sm text-ink-soft">
          Nessun suggerimento ancora: lo chiedo all'AI la prima volta che lo sostituisci in una ricetta.
        </p>
        <div className="pt-2">
          <Button ref={actionRef} accessibleName={`Scrivi tu: ${where}`} onClick={() => setEditing(true)}>
            Scrivi tu
          </Button>
        </div>
      </>
    );
  } else {
    const verdict = item.verdict;
    body = (
      <>
        <div className="pt-1">
          <SubstituteAnswer ingredientName={ingredientName} verdict={verdict} substitutes={item.substitutes} />
        </div>
        {/* l'ambra di «funziona, ma non del tutto»: una risposta c'è, e non l'ha ancora
            guardata nessuno */}
        {item.decided_by === "ai" ? (
          <p className="pt-1 text-xs font-medium text-low">Deciso dall'AI: da rivedere.</p>
        ) : (
          <p className="pt-1 text-xs text-ink-faint">Scelto a mano.</p>
        )}
        <div className="flex flex-wrap gap-2 pt-2">
          {item.decided_by === "ai" && (
            <Button
              accessibleName={`Va bene così: ${where}`}
              busy={confirm.isPending}
              onClick={() => confirm.mutate(verdict)}
            >
              Va bene così
            </Button>
          )}
          <Button ref={actionRef} accessibleName={`Correggi: ${where}`} onClick={() => setEditing(true)}>
            Correggi
          </Button>
        </div>
        {confirm.isError && <Alert className="pt-2">{saveErrorText(confirm.error)}</Alert>}
      </>
    );
  }

  return (
    <Card className="mb-2">
      <h3 className="text-sm font-semibold">
        {contextTitle(item.context)}
        <span className="font-normal text-ink-faint">{` · ${recipesText(item.recipes)}`}</span>
      </h3>
      {body}
    </Card>
  );
}
```

- [ ] **Step 4: La sezione nella scheda**

In `frontend/src/features/registry/IngredientScreen.tsx` (leggilo com'è sul ramo):

1. Dopo `import { RenameForm } from "./RenameForm";` aggiungi:
   ```tsx
   import { IngredientSubstitutes } from "../substitutes/IngredientSubstitutes";
   ```
2. Nel `return` di `IngredientCard`, dopo il blocco dei prodotti — quello che comincia con `<SectionHeading>Prodotti</SectionHeading>` e finisce con la `)}` che chiude `ingredient.products.length === 0 ? … : …` — e prima di `</Screen>`, aggiungi:
   ```tsx
         {/* R5: i sostituti, solo per il cibo — un non alimentare non sta in una ricetta */}
         {ingredient.kind === "food" && (
           <IngredientSubstitutes ingredientId={ingredient.id} ingredientName={ingredient.name} />
         )}
   ```

- [ ] **Step 5: I test della scheda**

In `frontend/src/features/registry/IngredientScreen.test.tsx` (leggilo com'è sul ramo):

1. In `function base(path: string)`, come prima riga del corpo, aggiungi:
   ```ts
     // R5: la sezione dei sostituti chiede la sua parte; vuota, non cambia niente agli altri test
     if (path.endsWith("/substitutes")) return [{ ingredient_id: "i-pomodori", contexts: [], recipe_overrides: 0 }, 200];
   ```
2. In fondo al file aggiungi:
   ```tsx
   describe("IngredientScreen — Sostituti (R5)", () => {
     it("in fondo alla scheda di un alimento, i suoi sostituti", async () => {
       stubRoutedFetch((path) =>
         path.endsWith("/ingredients/i-pomodori/substitutes")
           ? [{ ingredient_id: "i-pomodori", recipe_overrides: 0, contexts: [
               { context: "salato", recipes: 42, verdict: "omit", decided_by: "ai", substitutes: [] },
             ] }, 200]
           : base(path) ?? [{}, 404]
       );
       renderAt("/anagrafica/ingrediente/i-pomodori");
       expect(await screen.findByRole("heading", { name: "Sostituti" })).toBeInTheDocument();
       expect(await screen.findByText("Deciso dall'AI: da rivedere.")).toBeInTheDocument();
     });

     it("un non alimentare non ha la sezione", async () => {
       stubRoutedFetch((path) =>
         path.endsWith("/ingredients/i-detersivo")
           ? [{ ...DETERSIVO, aliases: [], products: [], usage: { recipes: 0, pantry: 0, shopping: 0 } }, 200]
           : [{}, 404]
       );
       renderAt("/anagrafica/ingrediente/i-detersivo");
       expect(await screen.findByRole("heading", { name: "Detersivo" })).toBeInTheDocument();
       expect(screen.queryByRole("heading", { name: "Sostituti" })).toBeNull();
     });
   });
   ```
   Se sul ramo `IngredientDetail` ha un campo obbligatorio in più (S12 aggiunge `emoji`, ma da `master` non c'è), `npm run typecheck` lo dice: completa l'oggetto del secondo test e basta.

- [ ] **Step 6: Passano, e tutto il frontend**

Run (da `<worktree>/frontend`): `npx vitest run && npm run typecheck && npm run lint && npm run build`
Expected: tutto verde (8 test nuovi: 6 della sezione, 2 della scheda); i test di oggi della scheda invariati, salvo la riga in `base()`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/substitutes/IngredientSubstitutes.tsx frontend/src/features/substitutes/IngredientSubstitutes.test.tsx frontend/src/features/registry/IngredientScreen.tsx frontend/src/features/registry/IngredientScreen.test.tsx
git commit -m "feat(anagrafica): R5, la sezione «Sostituti» — la voce dell'AI da rivedere, «Va bene così», «Correggi», «Scrivi tu»"
```

---

### Task 13: Nel browser vero — `sostituti.spec.ts`, il contrasto in `style.spec.ts`, il comando sullo stack

**Files:**
- Create: `frontend/e2e/sostituti.spec.ts`
- Modify: `frontend/e2e/style.spec.ts` (una prova in fondo)

**Interfaces:**
- Consumes: tutto quel che c'è prima; in `style.spec.ts` gli aiuti già definiti più sopra nel file (`ricettaDiProva`, `fermo`, `testiIlleggibili`, `senzaScorrimentoLaterale`) e il `beforeEach` che fa l'accesso.

Lo stack e2e non ha la chiave dell'AI: il pannello lì dice sempre «Nessun suggerimento ancora.» e la strada a mano è quella che si prova davvero; le risposte dell'AI si fingono deviando le **letture** con `page.route`, senza scrivere niente. Gli ingredienti di `sostituti.spec.ts` — «lonza di maiale», «fettina di manzo», «tacchino» — non li nomina nessun altro file della suite né degli altri piani della notte (verificato il 2026-10-13); se sul ramo `grep -rn "lonza di maiale\|fettina di manzo\|tacchino" frontend/e2e` trova altro oltre a questo file, scegli tre ingredienti del seme che nessuno nomina, sostituiscili ovunque qui, e scrivilo nel report.

- [ ] **Step 1: La prova del flusso**

Crea `frontend/e2e/sostituti.spec.ts`:

```ts
import { expect, test, type Page } from "@playwright/test";

// R5 nel browser vero: «Sostituisci» senza l'AI (lo stack e2e non ha la chiave), la
// strada a mano per una ricetta, la voce generale scritta in Anagrafica, il ritorno. La
// prova lascia dietro di sé la voce generale della lonza (non c'è una rotta per toglierla,
// e non serve): su uno stack riusato la guardia in cima lo dice. Toglie il resto.
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  // senza quest'attesa la prima `page.request` può partire prima del cookie di sessione
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
});

async function ingrediente(page: Page, nome: string): Promise<string> {
  const trovati = (await (
    await page.request.get(`/api/v1/ingredients/search?q=${encodeURIComponent(nome)}`)
  ).json()) as { id: string; name: string }[];
  const voce = trovati.find((trovato) => trovato.name === nome);
  expect(voce, `«${nome}» non è nel seme`).toBeDefined();
  return voce!.id;
}

async function senzaScorrimentoLaterale(page: Page, luogo: string) {
  await page.waitForLoadState("networkidle");
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
  expect(scrollWidth, `${luogo} scorre di lato`).toBeLessThanOrEqual(clientWidth);
}

test("«Sostituisci» senza l'AI: la strada a mano per la ricetta, la voce generale in Anagrafica, il ritorno", async ({ page }) => {
  const lonza = await ingrediente(page, "lonza di maiale");
  const fettina = await ingrediente(page, "fettina di manzo");
  const tacchino = await ingrediente(page, "tacchino");
  const prima = (await (await page.request.get(`/api/v1/ingredients/${lonza}/substitutes`)).json()) as {
    contexts: { verdict: string | null }[];
  };
  expect(
    prima.contexts.every((contesto) => contesto.verdict === null),
    "lo stack e2e non è pulito: ricrealo con `down -v` e riesegui"
  ).toBe(true);

  const creata = await page.request.post("/api/v1/recipes", {
    data: {
      title: `Sostituti e2e ${Date.now()}`,
      instructions: "Cuoci.",
      servings: 2,
      source: "manual",
      // niente categoria: una ricetta salata
      ingredients: [
        { ingredient_id: lonza, role: "primary", quantity_text: "300 g" },
        { ingredient_id: fettina, role: "secondary", quantity_text: "1" },
      ],
    },
  });
  expect(creata.ok()).toBe(true);
  const ricetta = ((await creata.json()) as { id: string }).id;
  const inDispensa = await page.request.post("/api/v1/pantry", {
    data: { ingredient_id: tacchino, status: "available" },
  });
  expect(inDispensa.ok()).toBe(true);
  const confezione = ((await inDispensa.json()) as { id: string }).id;

  try {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(`/ricette/${ricetta}`);
    const apri = page.getByRole("button", { name: "Sostituisci lonza di maiale" });
    const riga = page.getByRole("listitem").filter({ has: apri });
    const scatola = (await apri.boundingBox())!;
    expect(scatola.width).toBeGreaterThanOrEqual(44);
    expect(scatola.height).toBeGreaterThanOrEqual(44);

    await apri.click();
    await expect(apri).toHaveAttribute("aria-expanded", "true");
    // senza chiave il server non chiama nessuno: resta la strada a mano
    await expect(riga.getByText("Nessun suggerimento ancora.")).toBeVisible();
    await riga.getByRole("button", { name: "Scrivi tu" }).click();
    await riga.getByLabel("Cosa usare al suo posto").fill("tacchin");
    await riga.getByRole("option", { name: "Tacchino" }).click();
    await riga.getByLabel("Nota per tacchino").fill("a fette sottili");
    await riga.getByRole("button", { name: "Salva per questa ricetta" }).click();

    await expect(riga.getByText("Al posto di lonza di maiale:")).toBeVisible();
    await expect(riga.getByText("Tacchino", { exact: true })).toBeVisible();
    await expect(riga.getByText("· a fette sottili")).toBeVisible();
    await expect(riga.getByText("ce l'hai")).toBeVisible();
    await expect(riga.getByText("Scelto a mano per questa ricetta.")).toBeVisible();
    await senzaScorrimentoLaterale(page, "il pannello dei sostituti");

    // è salvata: si ritrova dopo un ricaricamento
    await page.reload();
    await page.getByRole("button", { name: "Sostituisci lonza di maiale" }).click();
    await expect(riga.getByText("Scelto a mano per questa ricetta.")).toBeVisible();

    // in Anagrafica la voce generale non c'è ancora, la correzione della ricetta sì
    await page.goto(`/anagrafica/ingrediente/${lonza}`);
    await expect(page.getByRole("heading", { name: "Sostituti" })).toBeVisible();
    await expect(page.getByText("Corretto a mano in 1 ricetta.")).toBeVisible();
    await page.getByRole("button", { name: "Scrivi tu: nei piatti salati" }).click();
    await page.getByText("Si può omettere", { exact: true }).click();
    await page.getByRole("button", { name: "Salva", exact: true }).click();
    await expect(page.getByText("Si può omettere: il piatto riesce anche senza lonza di maiale.")).toBeVisible();
    await expect(page.getByText("Scelto a mano.", { exact: true })).toBeVisible();
    await senzaScorrimentoLaterale(page, "la sezione dei sostituti");

    // nella ricetta la correzione vince; tolta, vale la voce generale
    await page.goto(`/ricette/${ricetta}`);
    await page.getByRole("button", { name: "Sostituisci lonza di maiale" }).click();
    await expect(riga.getByText("Scelto a mano per questa ricetta.")).toBeVisible();
    await riga.getByRole("button", { name: "Torna al suggerimento generale" }).click();
    await expect(riga.getByText("Si può omettere: il piatto riesce anche senza lonza di maiale.")).toBeVisible();
    await expect(riga.getByText("Scelto a mano per i piatti salati.")).toBeVisible();
  } finally {
    try {
      const via = await page.request.delete(`/api/v1/recipes/${ricetta}/substitutes/${lonza}`);
      expect.soft(via.status(), "pulizia: la correzione non si è tolta").toBe(204);
      const archiviata = await page.request.patch(`/api/v1/pantry/${confezione}`, { data: { archived: true } });
      expect.soft(archiviata.ok(), "pulizia: il tacchino non si è archiviato").toBe(true);
      const eliminata = await page.request.patch(`/api/v1/recipes/${ricetta}`, { data: { archived: true } });
      expect.soft(eliminata.ok(), "pulizia: la ricetta non si è eliminata").toBe(true);
    } catch (guasto) {
      expect.soft(false, `pulizia dei sostituti: ${guasto}`).toBe(true);
    }
  }
});
```

- [ ] **Step 2: Il contrasto, in fondo a `style.spec.ts`**

In fondo a `frontend/e2e/style.spec.ts` (leggilo com'è sul ramo) aggiungi:

```ts
// R5: i sostituti nei due temi, a 375 px. Nessuna scrittura: le risposte dell'AI si
// fingono deviando le letture, perché lo stack e2e non ha la chiave. La ricetta è quella
// di `ricettaDiProva`, che toglie da sé quel che mette.
test("i sostituti a 375px: il pannello, il modulo e la sezione in Anagrafica si leggono nei due temi", async ({ page }) => {
  const ricetta = await ricettaDiProva(page);
  try {
    await page.setViewportSize({ width: 375, height: 812 });
    const risposta = {
      ingredient_id: ricetta.ids.carciofo, ingredient_name: "carciofo", context: "salato",
      scope: "general", verdict: "substitutes", decided_by: "ai", ai_failed: false,
      substitutes: [
        { ingredient_id: ricetta.ids.radicchio, name: "radicchio", note: "cotto a parte",
          availability: "available", satisfied: true },
        { ingredient_id: ricetta.ids.porro, name: "porro", note: null, availability: "low", satisfied: false },
      ],
    };
    await page.route(
      new RegExp(`/api/v1/recipes/${ricetta.id}/substitutes/${ricetta.ids.carciofo}$`),
      (route) => route.fulfill({ json: risposta })
    );
    await page.goto(`/ricette/${ricetta.id}`);
    await page.getByRole("button", { name: "Sostituisci carciofo" }).click();
    await expect(page.getByText("Suggerito dall'AI per i piatti salati.")).toBeVisible();
    for (const tema of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: tema });
      await fermo(page);
      expect(await testiIlleggibili(page), `il pannello dei sostituti, tema ${tema}`).toEqual([]);
    }
    await page.emulateMedia({ colorScheme: "light" });
    for (const nome of ["Sostituisci carciofo", "Non va bene qui"]) {
      const scatola = (await page.getByRole("button", { name: nome }).boundingBox())!;
      expect(scatola.height, nome).toBeGreaterThanOrEqual(44);
      expect(scatola.width, nome).toBeGreaterThanOrEqual(44);
    }

    // il modulo aperto: le pastiglie, le note, i pulsanti
    await page.getByRole("button", { name: "Non va bene qui" }).click();
    await expect(page.getByRole("radio", { name: "Un altro ingrediente" })).toBeChecked();
    for (const tema of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: tema });
      await fermo(page);
      expect(await testiIlleggibili(page), `il modulo dei sostituti, tema ${tema}`).toEqual([]);
    }
    await page.emulateMedia({ colorScheme: "light" });
    await senzaScorrimentoLaterale(page, "il modulo dei sostituti");

    // in Anagrafica: una voce dell'AI da rivedere, una senza risposta, le correzioni
    await page.route(
      new RegExp(`/api/v1/ingredients/${ricetta.ids.carciofo}/substitutes$`),
      (route) =>
        route.fulfill({
          json: {
            ingredient_id: ricetta.ids.carciofo, recipe_overrides: 2,
            contexts: [
              { context: "salato", recipes: 12, verdict: "omit", decided_by: "ai", substitutes: [] },
              { context: "dolce", recipes: 1, verdict: null, decided_by: null, substitutes: [] },
            ],
          },
        })
    );
    await page.goto(`/anagrafica/ingrediente/${ricetta.ids.carciofo}`);
    await expect(page.getByText("Deciso dall'AI: da rivedere.")).toBeVisible();
    for (const tema of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: tema });
      await fermo(page);
      expect(await testiIlleggibili(page), `la sezione dei sostituti, tema ${tema}`).toEqual([]);
    }
    await page.emulateMedia({ colorScheme: "light" });
    for (const nome of ["Va bene così: nei piatti salati", "Correggi: nei piatti salati", "Scrivi tu: nei dolci"]) {
      expect((await page.getByRole("button", { name: nome }).boundingBox())!.height, nome).toBeGreaterThanOrEqual(44);
    }
    await senzaScorrimentoLaterale(page, "la sezione dei sostituti");
  } finally {
    await ricetta.pulisci();
  }
});
```

- [ ] **Step 3: L'e2e intera**

Con i comandi delle Global Constraints, dalla radice di `<worktree>`, su uno stack ricreato da zero (`down -v` prima dell'`up`, se ne era rimasto uno di questo ramo). **Non fare ancora il `down -v`**: serve allo Step 4.
Expected: tutte verdi, le due nuove comprese. **Annota il numero** delle prove passate: è `N_e2e` del Task 15.

Se una prova nuova fallisce: guarda prima se il seme ha davvero «lonza di maiale», «fettina di manzo», «tacchino» e i sei ingredienti di `ricettaDiProva` (`/api/v1/ingredients/search`). Se fallisce `testiIlleggibili`, scrivi nel report quale testo e con che rapporto: **nessun token nuovo**; se il colpevole è un testo di questo piano, il task si ferma `bloccato` con la misura.

- [ ] **Step 4: Il comando sullo stack, senza chiave**

Dalla radice di `<worktree>`, con lo stack ancora su:

```bash
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.decide_substitutes --dry-run; echo "uscita: $?"
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.decide_substitutes --limit 3; echo "uscita: $?"
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.decide_substitutes --limite 3; echo "uscita: $?"
```

Expected: il primo stampa «N voci senza sostituti: N nei piatti salati, 0 nei dolci.» (il seme non ha categorie: tutto salato), l'elenco, «nessun costo misurato ancora: lancia con --limit 20 per misurarlo.», `uscita: 0`; il secondo «sostituti non disponibili (OPENROUTER_API_KEY non configurata): …», «0 voci salvate (0 con sostituti, 0 da omettere, 0 insostituibili), 0 risposte scartate.», per ultima «N voci restano da decidere: rilancia questo comando.», `uscita: 0`; il terzo «argomento sconosciuto: --limite», `uscita: 2`. Copia le righe nel report. Poi `down -v` e `rm .env`, sempre.

- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/sostituti.spec.ts frontend/e2e/style.spec.ts
git commit -m "R5: nel browser vero, la strada a mano senza l'AI, la voce generale in Anagrafica, il contrasto nei due temi"
```

---

### Task 14: I documenti

**Files:**
- Modify: `README.md` (una sottosezione nuova)
- Modify: `docs/prossimi-passi.md` (voci «## R5. Sostituisci ingrediente» e «## R6»)
- Modify: `next-steps.md`

Leggi i tre file com'è sul ramo prima di cambiarli.

- [ ] **Step 1: `README.md`**

Subito **prima** della riga `### I vettori della ricerca semantica` aggiungi:

````markdown
### I sostituti degli ingredienti

«Sostituisci», dentro una ricetta, legge una risposta salvata per ingrediente e contesto
(dolce o salato): uno o più sostituti, «si può omettere», «insostituibile». Le decide
l'AI, una voce per chiamata, e le scrive solo dove non c'è una risposta:

```bash
docker compose exec backend python -m app.cli.decide_substitutes --dry-run
docker compose exec backend python -m app.cli.decide_substitutes --limit 20
docker compose exec backend python -m app.cli.decide_substitutes
```

Il primo non chiama nessuno: dice quante voci mancano e, dopo un lancio vero, quanto
costerebbe il resto con la media pagata. Il secondo chiede le venti più usate e stampa
una riga per voce, da guardare prima del resto. L'ultima riga dice sempre quante voci
restano. Senza il comando non si rompe niente: una voce che manca si chiede all'AI la
prima volta che qualcuno tocca «Sostituisci». Le risposte si correggono in Anagrafica,
nella scheda dell'ingrediente, e per una ricetta sola dalla ricetta («Non va bene qui»);
una correzione a mano il comando non la tocca mai.
````

- [ ] **Step 2: `docs/prossimi-passi.md`**

1. Il titolo `## R5. Sostituisci ingrediente **[D, con TBD pesante]**` diventa:
   ```markdown
   ## R5. Sostituisci ingrediente **[FATTO <data di oggi> — sul ramo `night/r5-sostituti`, non ancora in produzione]**
   ```
2. In fondo alla voce R5 (dopo il paragrafo che comincia con «↳ R4 (serve l'anagrafica ampia)»), aggiungi:
   ```markdown
   **Il TBD è deciso** (Mattia, 2026-10-13): una risposta per **ingrediente × {dolce,
   salato}**, la doppia voce solo dove serve, più la correzione per singola ricetta; un
   sostituto è solo un ingrediente alimentare dell'anagrafica, e una risposta dell'AI che
   non si verifica si scarta; «si può omettere» soddisfa qualunque riga ai fini di R6; le
   risposte dell'AI si vedono subito, segnate, e si rivedono in Anagrafica; una correzione
   umana non si sovrascrive mai. Una correzione di ricetta si perde se l'import rifà la
   ricetta (deciso da Mattia il 2026-10-13). Spec:
   `docs/superpowers/specs/2026-10-13-r5-sostituti-design.md`.

   **Fatto il <data di oggi>**, sul ramo `night/r5-sostituti` (da revisionare). Il contesto
   viene dalla categoria della ricetta (`recipe_context`: dolce se la prima parola è
   «dolci»). Le risposte stanno in `ingredient_substitutions` e `substitution_options`
   (migrazione `0015`); le scrive l'AI con `python -m app.cli.decide_substitutes` (a lotti,
   dalle voci più usate, `--limit` e `--dry-run`) o sul momento al primo «Sostituisci»;
   una chiamata per voce con l'anagrafica alimentare nel prompt, ~0,0004 $, ~0,5 $ per
   tutto il ricettario. Nel dettaglio un'icona in fondo a ogni riga apre il pannello sotto
   la riga, coi sostituti, il pallino della dispensa e «ce l'hai»; «Non va bene qui» scrive
   la correzione della ricetta. In Anagrafica la sezione «Sostituti» con «Deciso dall'AI:
   da rivedere.», «Va bene così» e «Correggi». La fusione sposta tutto sul vincitore.

   **Da provare sul telefono:** l'icona in fondo alla riga col pollice, accanto alla dose;
   il pannello che si apre sotto la riga senza far saltare la pagina; il selettore del
   sostituto con la tastiera aperta.
   ```
3. In fondo alla voce `## R6`, aggiungi:
   ```markdown
   **La regola è scritta** (spec R5 §8, 2026-10-13): una riga che manca conta se la
   risposta che vale per lei è «si può omettere» (qualunque ruolo; la ricetta dirà «senza
   X»), o se almeno un sostituto in dispensa soddisfa la stessa regola della riga (primary
   → available, secondary → available o low); un passo solo; «insostituibile» o nessuna
   risposta resta mancante. R5 calcola già `satisfied` per ogni sostituto di una riga.
   ```
   Sostituisci `<data di oggi>` con la data vera, ovunque.

- [ ] **Step 3: `next-steps.md`**

1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte)_`.
2. Togli la riga della voce (`grep -n "R5, sostituisci" next-steps.md`: `in corso` dalla Preparazione, dovunque sia). Se in «Pronti per la notte» era una voce numerata, lascia com'è la numerazione delle altre.
3. In cima a «Fatti (recenti)» aggiungi:
   ```markdown
   - [fatto] <data di oggi> · R5, sostituisci ingrediente: risposte per ingrediente × {dolce, salato} decise dall'AI (`decide_substitutes`, a lotti, `--limit`/`--dry-run`) o al primo tocco, l'icona «Sostituisci» in fondo a ogni riga col pannello sotto, «Non va bene qui» per la ricetta, la sezione «Sostituti» in Anagrafica con le voci dell'AI da rivedere, la fusione che sposta tutto; migrazione `0015` [R5] → branch night/r5-sostituti (da revisionare)
   ```
4. In cima a «Da fare a mano (solo Mattia)» aggiungi:
   ```markdown
   - [tbd] P3 · Dopo il deploy di R5: al merge ripuntare la `down_revision` della `0015` sulla testa di `master` (`alembic heads` = una testa) e, se H1 è dentro, `"ingredient_substitutes": "Sostituti degli ingredienti"` in `CALL_SITE_LABELS`; poi in produzione `decide_substitutes --dry-run`, `--limit 20` (guardare le venti righe e la spesa), di nuovo `--dry-run` per la stima, e il resto (comandi nel piano R5, «Dopo il deploy»). Sul telefono: l'icona in fondo alla riga col pollice, il pannello sotto la riga, il selettore con la tastiera aperta [R5]
   ```
5. La riga di R6 (`grep -n "R6, cucinabili con sostituti" next-steps.md`) passa da «attende: R5» a «attende: il merge di R5 (`night/r5-sostituti`); la regola è nella spec R5 §8». Lo stato resta `bloccato`.
6. In «Idee» aggiungi:
   ```markdown
   - [idea] P3 · Le correzioni dei sostituti di una ricetta importata potrebbero viaggiare nel `payload` come le cotture (`cooking_event_ids`), così l'import che rifà la ricetta le rimette: oggi si perdono (deciso da Mattia il 2026-10-13, opzione (a) della spec R5 §10) [R5]
   - [idea] P3 · Un elenco delle voci dei sostituti decise dall'AI da rivedere, fuori dalla scheda dell'ingrediente (oggi si rivedono ingrediente per ingrediente) [R5]
   - [idea] P3 · «Chiedi all'AI» nella sezione «Sostituti» dell'Anagrafica, per una voce senza risposta (oggi la chiede il primo «Sostituisci» in una ricetta, o il comando) [R5]
   ```
7. Se nella notte sono emerse altre cose da fare fuori da questo piano, aggiungile come `idea` o `tbd` nella sezione giusta, con la voce di `docs/prossimi-passi.md` fra parentesi quadre.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/prossimi-passi.md next-steps.md
git commit -m "docs: R5 fatto sul ramo — decide_substitutes nel README, la regola di R6 scritta, il passo a mano dopo il deploy"
```

---

### Task 15: La verifica finale e il report

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

Expected: vitest tutto verde — **`N_vitest` della Preparazione più 37** (8 del Task 9, 10 del Task 10, 11 del Task 11, 8 del Task 12), in **`N_file` + 5** file (`wording.test.ts`, `api.test.ts`, `SubstituteEditor.test.tsx`, `SubstitutePanel.test.tsx`, `IngredientSubstitutes.test.tsx`); se il numero differisce, scrivi nel report da dove viene la differenza. Typecheck, lint e build puliti. `npx tsc -b --force` perché `node_modules` è condiviso col checkout principale, e con lui il `tsbuildinfo`: `--force` compila davvero tutto.

- [ ] **Step 2: Il backend**

Da `<worktree>/backend`:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_r5 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Expected: tutto verde, **`N_pytest` + 114** (20 del Task 1, 9 del Task 2, 16 del Task 3, 6 del Task 4, 8 del Task 5, 27 del Task 6, 10 del Task 7, 17 del Task 8, 1 del Task 9).

- [ ] **Step 3: I grep**

Dalla radice del worktree:

```bash
grep -rn "emerald\|neutral-" frontend/src
git diff master --stat -- backend/alembic | tail -n 1
grep -c "await complete_json(" backend/app/services/substitutions.py
grep -rn "down_revision" backend/alembic/versions/0015_sostituti.py
```

Expected: il primo vuoto; il secondo `1 file changed, …`; il terzo `1`; il quarto `down_revision = "0012"`.

- [ ] **Step 4: L'e2e, se il Task 13 non l'ha appena fatta su questo stesso ramo**

Con i comandi delle Global Constraints, su uno stack ricreato da zero. Expected: tutte verdi, `N_e2e` del Task 13. Poi `down -v` e `rm .env`, sempre. Poi il database dei test di questo ramo:

```bash
docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_r5 WITH (FORCE)'
```

- [ ] **Step 5: Il report**

Nel report della notte, `docs/night-reports/<data di oggi>.md` sul ramo: se il file c'è già sul ramo aggiungi una sezione in fondo, altrimenti crealo con un titolo `# Notte del <data di oggi>` (gli altri piani della notte scrivono lo stesso file sui loro rami: l'unione la fa la revisione). Per questo piano:

- il ramo e da dove parte (`master`); i conti veri (vitest, pytest, e2e) contro quelli della Preparazione; il database dei test (`spena_test_r5`, tolto alla fine);
- **la migrazione `0015`** (`ingredient_substitutions`, `substitution_options`), con `down_revision = "0012"`: al merge va ripuntata sulla testa di `master` di quel momento, e `alembic heads` deve dire una testa sola;
- **la sezione della spesa nuova**, `LlmCallSite.INGREDIENT_SUBSTITUTES = "ingredient_substitutes"`: se H1 è già su `master`, `CALL_SITE_LABELS` prende `"ingredient_substitutes": "Sostituti degli ingredienti"`;
- le righe del comando lanciato sullo stack e2e (Task 13, Step 4);
- le scelte che Mattia può voler rivedere: la regola del contesto (solo «Dolci…» è dolce; «Lievitati» e «Bevande» salati), un solo difetto che scarta la risposta intera, da 1 a 3 sostituti, dalla ricetta solo la correzione della ricetta e da Anagrafica solo la voce generale, l'icona in fondo alla riga, «ce l'hai» accanto al sostituto, l'ambra di «Deciso dall'AI: da rivedere.», le regole della fusione;
- che **la correzione di una ricetta importata si perde se l'import la rifà** (deciso da Mattia il 2026-10-13, opzione (a)), con l'`idea` per l'opzione (c) in `next-steps.md`;
- le migrazioni di test fatte oltre alla riga di `base()` in `IngredientScreen.test.tsx` (dovrebbero essere zero);
- i file che al merge incontrano altri rami della notte: `llm.py` (S12, R8), `main.py` e `CALL_SITE_LABELS` (H1), `registry.py` (S12, pulizia delle dosi), `RecipeDetailScreen.tsx` e il suo test (R2 — il pulsante va in fondo al `<div>` della riga dopo la dose di R2, `SubstitutePanel` dopo `AnchorField` —, pulizia delle dosi, R8, «rimetti in lista», pulizie dei controlli), `IngredientScreen.tsx` e il suo test (S12, pulizie dei controlli), `icons.ts`, `style.spec.ts`, `README.md` (S12).

Niente push, niente merge, niente deploy.

```bash
git add docs/night-reports/
git commit -m "report: R5 sostituti, la notte"
```
