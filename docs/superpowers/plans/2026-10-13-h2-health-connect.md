# H2, l'attività da Health Connect via HC Webhook: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Spena riceve da HC Webhook (l'app Android che legge Health Connect, dove scrive Samsung Health) i passi del giorno, gli allenamenti e le pesate, su una rotta aperta da una chiave sua; li salva una volta sola anche se arrivano due volte o da telefono e orologio; e li mostra in «Attività», dal ☰, con il collegamento spiegato passo per passo.

**Architecture:** il backend legge, decide e salva; il frontend mostra. Un modulo puro `backend/app/domain/activity.py` legge il corpo di HC Webhook voce per voce (mai un'eccezione: quel che non capisce lo conta e lo scrive in italiano), riconosce i passi in forma «Giornaliero» e tiene un totale solo per giorno di Roma (`merge_steps_day`), dà i nomi a video. `backend/app/core/webhook_token.py` crea la chiave e la confronta a tempo costante sull'impronta SHA-256. Cinque tabelle nuove (migrazione `0018`, modelli in `backend/app/db/models/activity.py`), un repository, un servizio (`backend/app/services/activity.py`) e tre rotte in `backend/app/api/activity.py`: `POST /api/v1/activity/hc-webhook` fuori dalla sessione (la chiave in `X-Spena-Token`, il corpo letto a pezzi fino a 2 MB, le richieste una alla volta con un advisory lock), `GET /api/v1/activity` e `POST /api/v1/activity/token` dietro la sessione. Nginx dà a quella sola rotta 4 MB, così il rifiuto oltre i 2 lo dà il backend e si vede. Nel frontend una cartella nuova, `frontend/src/features/activity/`: i tipi, la chiamata, le parole, `CopyField`, `ActivityScreen` su `/attivita` (voce «Attività» del ☰) e `ConnectScreen` su `/attivita/collega`. Nel browser vero il telefono lo fa la prova, con `page.request` attraverso Nginx.

**Tech Stack:** FastAPI, Pydantic 2, SQLAlchemy 2 async, Alembic, pytest su Postgres vero; React 19, TypeScript, Tailwind 4 (token in `@theme`), TanStack Query 5, react-router 7, Vitest + Testing Library (jsdom), Playwright; Nginx.

**Spec:** `docs/superpowers/specs/2026-10-13-h2-health-connect-design.md` (scritta con questo piano: la ricerca sul formato di HC Webhook al §1, le decisioni di Mattia del 2026-10-13 al §2, quelle di Claude su delega al §3 — la chiave, i limiti, i doppioni fra telefono e orologio, le tabelle, la schermata —, le parole a video al §4, quel che resta a P2 e H3 al §9). Il ragionamento d'archivio è in `docs/prossimi-passi.md`, voci «## H2. Connettore Samsung Health», «## P2. NutriScore» e «## H3. Profilo». La riga di `next-steps.md` che questo piano chiude contiene «H2,».

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/h2-health-connect` (`.worktrees/` è già in `.gitignore`), ramo `night/h2-health-connect`, creato da **`master`**: è il diciannovesimo piano della notte ma non dipende dalla catena. Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì (o dalle sue `backend/` e `frontend/`), mai dalla radice del checkout principale. Il checkout principale non si tocca: se vi trovi modifiche non committate, sono dell'utente. **Nessun push, nessun merge, nessun deploy. Mai `git stash`.** Niente letture né scritture sulla produzione.
- **I file che anche altri piani della notte toccano** — `backend/app/main.py` (H1 riscrive la riga degli import dei router e aggiunge `spending`), `frontend/src/App.tsx` (S3, R8, le pagine scartate, H1 aggiungono rotte), `frontend/src/components/AppHeader.tsx` e `AppHeader.test.tsx` (H1 aggiunge «Spese dell'AI» in fondo a `INDEX` e sposta l'«ultima voce» del test del fuoco; il tema scuro cambia il portale), `frontend/src/components/ui/icons.ts`, `frontend/e2e/style.spec.ts` (quasi tutti, e `SCHERMATE`), `next-steps.md`, `docs/prossimi-passi.md`, il report della notte. Sul tuo ramo, che parte da `master`, sono come su `master`. Il piano descrive comunque ogni modifica a un file esistente contro un'ancora riconoscibile — una costante, una funzione, un elemento JSX, un testo esatto — e mai contro numeri di riga: **leggi il file com'è sul ramo prima di cambiarlo**. Dove il piano dà un file intero è un file nuovo. Le prove nuove di `style.spec.ts` vanno **in fondo al file**; le voci nuove di `SCHERMATE` subito dopo `"/anagrafica",`. Al merge, l'unione con gli altri rami la fa la revisione (vedi «Al merge»).
- **La rotta del webhook è l'unica fuori dalla sessione che scrive.** La apre solo la chiave in `X-Spena-Token`; senza la chiave giusta: `401` **senza corpo**, prima di leggere il corpo, **nessuna scrittura** (né il registro né `last_used_at`). Mai la chiave in un indirizzo, mai la chiave in chiaro nel database, mai il corpo ricevuto nel database (solo nomi di chiavi, conteggi e frasi).
- **Mai un 500 su un corpo inatteso.** `parse_payload` non solleva mai: una voce illeggibile si scarta e si conta, un tipo che non è un elenco si salta, le chiavi sconosciute si registrano per nome. Un corpo che non è JSON (compreso il `RecursionError` di un annidamento profondo) o non è un oggetto → `400` registrato; oltre 2 MB → `413` registrato.
- **I doppioni non si sommano** (spec §3.2): i passi solo in forma «Giornaliero», un totale per giorno di Roma scelto da `merge_steps_day`, mai una somma; allenamenti unici per `(source, started_at)`, pesate per `(source, measured_at)`, aggiornati se tornano.
- **Il frontend non calcola logica di dominio.** I giorni e le ore di Roma, i 7 giorni coi buchi, i minuti, i chilometri, i nomi (allenamenti, app, tipi ignorati), se la sincronizzazione è vecchia: li decide il backend. Nel frontend restano «Oggi» / «Ieri» / «lun 12 ott», i numeri all'italiana, l'indirizzo del webhook (l'origine della pagina più il percorso) e il disegno.
- **Mai un vicolo cieco.** Mai sincronizzato → uno stato vuoto che porta al collegamento; un problema nel corpo → la frase che dice cosa fare in HC Webhook; niente da più di un giorno → l'avviso sulla batteria; «Copia» che non riesce → il testo selezionato e la frase per copiarlo a mano; un guasto del server → `ErrorState` con «Riprova»; la chiave persa → «Rigenera la chiave».
- **Niente dipendenze nuove.** Tutto il colore passa dai token di `frontend/src/index.css`: **nessun token nuovo**, `index.css` e `theme.test.ts` non si toccano. Nessuna schermata nomina un colore crudo: `grep -rn "emerald\|neutral-" frontend/src` resta vuoto. Ogni testo sta sopra 4,5:1, in chiaro e in scuro, e lo misura `frontend/e2e/style.spec.ts`. Le icone si importano solo da `frontend/src/components/ui/icons.ts` (si aggiunge `IconCopy`, che `@tabler/icons-react` ha già). Niente classi in conflitto sullo stesso elemento; **nessun `text-sm` su un `<input>`**: sotto i 16 px iOS ingrandisce la pagina al fuoco (`index.css` li veste a 1rem).
- **`Button`** (`frontend/src/components/ui/Button.tsx`) non cambia: in volo → `busy`; nessun `<button>` scritto a mano; un `Link` che naviga usa `buttonClasses`. Ogni bersaglio nuovo è almeno 44×44 px. A 375 px nessuna schermata scorre di lato.
- Le parole a video sono in italiano e **si copiano esattamente come sono scritte qui** (sono quelle del §4 della spec); gli identificatori in inglese; i commenti in italiano come nel resto del codice, e dicono il perché.
- **Il type check è `npm run typecheck`** (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0 (settima lezione di `CLAUDE.md`).
- Controlli del frontend, da `<worktree>/frontend`: `npx vitest run` (non esiste `npm test`), `npm run typecheck`, `npm run lint`, `npm run build`.
- **Backend su Postgres vero, in un database suo.** Il server dei test è il container `spena-db-1` (porta 5433): se `docker ps --format '{{.Names}}'` non lo mostra, `docker start spena-db-1`. **Mai `docker compose up` dal worktree** (il nome del progetto Compose viene dalla cartella: nascerebbe un secondo Postgres che litiga sulla 5433), mai `-f docker-compose.prod.yml`. Nel worktree non c'è un `.venv`: si usa quello del checkout principale; `python -m` mette la cartella corrente in testa a `sys.path`, quindi si prova l'`app` del worktree. Il comando, sempre da `<worktree>/backend` (dove un task dice «il comando di pytest» intende questo, con i percorsi di test che il task indica in coda):
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_h2 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
  Se un test sembra ignorare una modifica, `python -c 'import app; print(app.__file__)'` da `<worktree>/backend` (con lo stesso `PATH`) deve stampare un percorso dentro il worktree. Nessuna chiamata di rete nella suite.
- **Il database dei test è `spena_test_h2`, non `spena_test`** (regola dell'orchestrazione del 2026-10-13 per i piani 16–19). Questo ramo aggiunge la migrazione `0018`; la suite fa `alembic upgrade head` sul suo database all'avvio, e girata su `spena_test` lo lascerebbe alla `0018`, rompendo `alembic upgrade head` ai piani che partono da `master` («Can't locate revision identified by '0018'»). Il database si crea nella Preparazione e si toglie alla fine della verifica finale:
  ```bash
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_h2 WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_h2'
  # … i task …
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_h2 WITH (FORCE)'
  ```
- **La migrazione è la `0018`, con `down_revision = "0012"`** (numero riservato a H2; R5 ha la `0015`, S4 la `0016` e la `0017`, tutti da `master`). Se la Preparazione trova su `master` una testa diversa dalla `0012`, la `down_revision` va su quella testa (vedi la Preparazione). Al merge la ripunta Mattia («Al merge»).
- **e2e** sullo stack `spena-e2e`, dalla radice di `<worktree>`. Serve un `.env`: **si copia da `.env.example`, che non ha segreti, solo per la prova, e si cancella alla fine. Mai leggere né copiare il `.env` del checkout principale.** Prima di alzarlo, `docker ps --format '{{.Names}}' | grep spena-e2e`: se c'è e non l'hai alzato tu (un altro piano della notte), non fare `down`, aspetta che sparisca.
  ```bash
  cp .env.example .env
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed --con-ricette
  (cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
  rm .env
  ```
  Il `-p spena-e2e` e il `-f docker-compose.e2e.yml` vanno in ogni comando: un `down -v` sul progetto di default cancellerebbe la dispensa vera. Il backend migra da sé alla `0018` all'avvio; il frontend si costruisce dal worktree, con il suo `nginx.conf`. Una prova fallita lascia dati nello stack: prima di rieseguire, `down -v`, poi `up`, seme e prova.
- **Il telefono, nel browser vero, lo fa la prova.** Nessuna rete verso fuori: i corpi di HC Webhook li scrive la prova e li manda con `page.request` a `http://localhost:5174/api/v1/activity/hc-webhook`, attraverso Nginx come farebbe il telefono.
- Una sola migrazione, la `0018`. Nessun cambio di configurazione globale oltre alla `location` del webhook in `frontend/nginx.conf`.

### Preparazione (una volta, prima del Task 1)

- [ ] Il database dei test di questo ramo (prima di qualunque pytest):
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_h2 WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_h2'
  ```
- [ ] Il ramo di partenza è `master`, la sua testa delle migrazioni è la `0012`, e i file di questo piano sono quelli su cui è scritto (`master` era `b9be6bf` quando il piano è stato scritto):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify master
  git ls-tree --name-only master backend/alembic/versions/ | grep -E '/00[0-9]{2}_' | sort | tail -n 2
  git diff --stat b9be6bf master -- \
    backend/app/main.py backend/app/db/models/__init__.py backend/app/domain/rules.py \
    backend/app/core/security.py backend/tests/conftest.py frontend/nginx.conf \
    frontend/src/App.tsx frontend/src/components/AppHeader.tsx frontend/src/components/AppHeader.test.tsx \
    frontend/src/components/ui/icons.ts frontend/src/components/ui/Button.tsx frontend/e2e/style.spec.ts
  ls backend/app/domain/activity.py backend/app/core/webhook_token.py backend/app/db/models/activity.py \
    backend/app/repositories/activity.py backend/app/services/activity.py backend/app/schemas/activity.py \
    backend/app/api/activity.py backend/alembic/versions/0018_attivita_health_connect.py \
    frontend/src/features/activity frontend/e2e/attivita.spec.ts 2>&1 | grep -c "No such file"
  ```
  Expected: un hash; le ultime due righe sono `backend/alembic/versions/0011_termine_crea_ingrediente.py` e `backend/alembic/versions/0012_modifica_ricette.py`; il `diff --stat` **vuoto**; `10` (i file nuovi non esistono ancora).
  - Se l'ultima migrazione di `master` non è la `0012` (un ramo della notte è già stato unito), la `0018` di questo piano prende come `down_revision` **quella testa** (il valore di `revision` nel file), e il test del Task 1 scende a quella invece che alla `0012`: scrivilo nel report. Se esiste già una `0018`, **fermati** (vedi sotto).
  - Se il `diff` non è vuoto, `master` è andato avanti su questi file: applica le modifiche del piano sopra la versione di `master`, ancora per ancora, e scrivilo nel report.
  - Se uno dei file nuovi esiste già, **fermati**: qualcuno ha già cominciato questa voce. Crea comunque il ramo (passo sotto), scrivi nel report della notte (`docs/night-reports/<data>.md`, sul ramo `night/h2-health-connect`) cosa hai trovato, segna la voce `bloccato` in `next-steps.md` di quel ramo con la domanda per Mattia, e non partire.
- [ ] Dal checkout principale, allinea `node_modules` al lockfile (non aggiunge dipendenze, installa quelle di `package-lock.json`):
  ```bash
  cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund
  ```
- [ ] Crea il worktree da `master` e collega `node_modules` (e solo quello: **niente `.env`**):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/h2-health-connect -b night/h2-health-connect master
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/h2-health-connect/frontend/node_modules
  ```
- [ ] La voce in `next-steps.md` del ramo passa a `in corso`. Trovala con `grep -n "H2," next-steps.md` (fra i «Pronti per la notte», o ancora fra le voci da approfondire). Toglila da dove sta e mettila sotto `## In corso` (al posto di `_(niente)_`, se c'è; altrimenti in fondo alle righe già lì):
  ```markdown
  - [in corso] P3 · H2, l'attività da Health Connect via HC Webhook: passi, allenamenti e pesate in «Attività» dal ☰, la chiave del webhook, migrazione `0018` — piano `docs/superpowers/plans/2026-10-13-h2-health-connect.md` → branch night/h2-health-connect [H2]
  ```
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/h2-health-connect
  git add next-steps.md
  git commit -m "next-steps: H2 in corso, sul ramo night/h2-health-connect"
  ```
- [ ] La linea di partenza, dal worktree:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/h2-health-connect/frontend && npx vitest run 2>&1 | grep -E "Test Files|Tests "
  cd ../backend && TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_h2 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q 2>&1 | tail -n 1
  ```
  Expected: tutto verde. **Annota i numeri** (file e test di vitest, test di pytest): sono `N_file`, `N_vitest`, `N_pytest` del Task 10. Se una delle due linee non è verde, fermati: non è un difetto di questo piano, e va scritto nel report.

---

## Obiettivo e contesto

P2 vuole un fabbisogno calorico che tenga conto dell'attività, e inserirla a mano non si fa. La via ufficiale di Samsung chiede di diventare partner; la ricerca del 2026-10-13 ha trovato quella praticabile: Samsung Health scrive in Health Connect passi, allenamenti e pesate (e altro), e **HC Webhook**, un'app Android libera, legge Health Connect e manda i dati a un indirizzo con un `POST` JSON e le intestazioni che si vogliono. Mattia ha deciso il 2026-10-13 di prendere questa strada subito, con la PWA di oggi, e di leggere passi, allenamenti e peso; il calcolo del dispendio resta a P2.

Mancano: una rotta che accetti quel corpo da internet senza aprire niente a nessun altro, un modo di non contare due volte i passi di telefono e orologio, tre tabelle per i dati e due per la chiave e il registro, e una schermata che dica cosa è arrivato e come collegare l'app.

## Decisioni prese

Di Mattia, il 2026-10-13 (non si rimettono in discussione):

1. **La via è HC Webhook, subito**, con la PWA di oggi. Più avanti, col wrapper Capacitor, la lettura di Health Connect passerà dentro l'app (fuori scope): il backend resta lo stesso.
2. **Spena legge passi, allenamenti e peso.** Il dispendio lo calcolerà Spena (passi e allenamenti col metodo a MET, più il metabolismo di base dal Profilo), ma il **calcolo del fabbisogno è di P2 e H3**: questo piano riceve, salva e mostra. La funzione del dispendio è descritta, rinviata, al §9 della spec.
3. **I dati arrivano da telefono e Galaxy Watch**: i doppioni vanno evitati (decisione 9–12 sotto).
4. Le scelte tecniche ed estetiche sono delegate a Claude.

Di Claude, su delega di Mattia (il perché è nella spec, §3):

5. **La rotta** `POST /api/v1/activity/hc-webhook` sta fuori dalla sessione; la apre la **chiave** nell'intestazione **`X-Spena-Token`**: `secrets.token_urlsafe(32)`, 43 caratteri. Il database tiene **solo l'impronta SHA-256**, in una tabella a riga unica, con la creazione e l'ultimo uso. **Si vede una volta**, quando la si crea (`POST /api/v1/activity/token`, dietro la sessione); persa, **si rigenera** e la vecchia smette subito di funzionare.
6. **Il rifiuto è silenzioso**: intestazione mancante, forma sbagliata, chiave sbagliata, nessuna chiave → lo stesso `401` senza corpo, nessuna scrittura. Una forma sbagliata non tocca il database; il confronto è `hmac.compare_digest` sulle impronte, e senza chiave si confronta con un'impronta finta.
7. **Limiti**: il corpo si legge a pezzi fino a **2 MB** (`413` registrato); Nginx dà a questa rotta **4 MB**, così il rifiuto lo dà il backend e si vede; al più **5.000 voci per tipo**. Le richieste del webhook passano una alla volta (`pg_advisory_xact_lock`).
8. **Il registro** (`activity_syncs`): per ogni corpo autenticato quando, esito (`ok`, `test`, `rejected`), versione dell'app, istante del corpo, byte, quante voci salvate, i nomi delle chiavi ignorate, i problemi in italiano. **Mai il corpo.** Restano le ultime 200 righe. La prova (`"test": true`) non salva niente.
9. **I passi si accettano solo in forma «Giornaliero»** (il default di HC Webhook, l'unica calcolata con la lettura aggregata di Health Connect, che toglie i doppioni fra le app). Un record con `metadata` («Completo») o lungo al più 60 minuti con inizio e fine al minuto tondo (le finestre «1 / 5 / 15 min») non si salva, e si scrive il problema.
10. **Un giorno di Roma ha un totale solo, mai una somma** (`merge_steps_day`): un record che copre almeno l'intervallo tenuto lo sostituisce (anche più basso: è una correzione), uno che ci sta dentro si ignora, uno che si sovrappone in parte o sta accanto lascia il più alto dei due.
11. **Allenamenti** unici per `(origine, inizio)`, aggiornati se tornano; due app diverse sullo stesso tempo restano due righe, ognuna con la sua origine a video (il tempo in comune lo conterà una volta P2). **Pesate** uniche per `(origine, istante)`.
12. **Migrazione `0018`**, cinque tabelle: `activity_tokens`, `activity_steps_days`, `activity_exercises`, `activity_weights`, `activity_syncs`; giorni di Roma come la scadenza. Il tipo dell'allenamento resta la costante intera di Health Connect (la chiave dei MET di P2), il nome a video viene da `EXERCISE_LABELS`.
13. **Dove**: il ☰, voce **«Attività»** dopo «Anagrafica», percorso `/attivita`; il collegamento è la sottosezione `/attivita/collega` col tasto indietro. **«Attività»** mostra l'ultima sincronizzazione (con prova, rifiuto, problemi, tipi non usati, l'avviso dopo 24 ore senza niente), i passi degli ultimi 7 giorni (oggi per primo), gli allenamenti degli ultimi 7 giorni (al più 20), le ultime 5 pesate; mai sincronizzato, uno stato vuoto che porta al collegamento. **«Collega HC Webhook»** ha la chiave (crea; rigenera con una conferma) e dieci passi, con l'indirizzo e le intestazioni da copiare.
14. **Niente grafici**, niente token nuovi, nessuna dipendenza; un'icona in più, `IconCopy`.

Scelte interne di questo piano (Claude, su delega; reversibili):

15. **Le intestazioni da incollare sono un oggetto JSON** (`{"X-Spena-Token":"…"}`): HC Webhook ha «Gestisci intestazioni» › «JSON» › «Applica JSON», e un incolla solo sul telefono sbaglia meno di due campi scritti a mano.
16. **I tipi stanno in `frontend/src/features/activity/types.ts`**, non in `domain/types.ts`, che stanotte cambiano S12, S14, S15 e R2.
17. **Il giorno di un record è il giorno di Roma del suo inizio** (`rome_day(start)`): il telefono di Mattia è sullo stesso fuso, e il totale «Giornaliero» parte dalla mezzanotte del telefono.
18. **`CopyField` prova `navigator.clipboard.writeText`** e, se non c'è o rifiuta, seleziona il testo e lo dice: niente `document.execCommand("copy")`, deprecato.

## Criteri di accettazione

- [ ] La migrazione `0018` sale, scende e risale; le cinque tabelle esistono coi loro vincoli; modelli e schema coincidono (`test_metadata_matches_migrations.py`).
- [ ] `POST /api/v1/activity/hc-webhook` senza `X-Spena-Token`, con una chiave sbagliata o di forma sbagliata, senza una chiave configurata, o con la sola sessione dell'app → `401` col corpo vuoto, e nel database non cambia niente.
- [ ] Con la chiave giusta il corpo di HC Webhook salva il totale del giorno, l'allenamento, la pesata; risponde `200` con `saved`, `ignored`, `problems`; registra la sincronizzazione `ok` e l'ultimo uso della chiave.
- [ ] Lo stesso corpo due volte non duplica niente; un totale dei passi più ampio sostituisce, uno più stretto arrivato dopo no; un allenamento rimandato aggiorna la sua riga.
- [ ] I passi a finestre o grezzi non si salvano, e il problema dice di scegliere «Giornaliero».
- [ ] Corpo oltre i 2 MB (dichiarato o a pezzi) → `413`; non JSON, annidato a fondo o non oggetto → `400`; registrati come `rejected` con la frase. Voci illeggibili, tipi nuovi, numeri impossibili → `200` col resto salvato. Mai un `500`.
- [ ] `"test": true` → `200`, niente salvato, registrata come `test`.
- [ ] `GET /api/v1/activity` (sessione) dà oggi, l'ultima sincronizzazione (giorno e ora di Roma, vecchia dopo 24 ore, nomi italiani dei tipi ignorati), 7 giorni di passi da oggi indietro con `null` dove mancano, gli allenamenti degli ultimi 7 giorni dal più recente, le ultime 5 pesate, lo stato della chiave. La chiave non vi compare mai.
- [ ] `POST /api/v1/activity/token` (sessione) → `201` con una chiave di 43 caratteri; rigenerare spegne la vecchia.
- [ ] Nginx dà alla rotta del webhook `client_max_body_size 4m` (un test lo legge).
- [ ] Nel ☰ «Attività» è dopo «Anagrafica» e porta a `/attivita`. Mai sincronizzato: «Nessun dato da Health Connect, per ora» con «Collega HC Webhook». Con dati: l'ultima sincronizzazione, «Passi» coi 7 giorni («8.421», «nessun dato»), «Allenamenti» («Corsa · 32 min · 5,1 km», «Oggi, 18:00 · Samsung Health»), «Peso» («72,4 kg»), «Collegamento con HC Webhook».
- [ ] «Collega HC Webhook»: la chiave si crea e si vede una volta con «Copia»; rigenerarla chiede conferma; l'indirizzo c'è sempre; le intestazioni JSON solo con la chiave appena creata; dieci passi nell'ordine della spec.
- [ ] Nel browser vero (e2e): la chiave creata dalla schermata apre il webhook attraverso Nginx; senza o sbagliata `401`; lo stesso corpo due volte salva una volta; «Attività» mostra passi, corsa e pesata; un corpo da 3 MB è rifiutato dal backend e si legge in «Attività»; la prova pure. A 375 px niente scorre di lato; i testi sopra 4,5:1 nei due temi.
- [ ] Tutti i test di oggi passano; l'unico cambiato è «il fuoco resta dentro» di `AppHeader.test.tsx` (l'ultima voce del ☰ ora è «Attività»), mai indebolito.
- [ ] vitest, typecheck, lint, build, pytest e l'e2e intera verdi.
- [ ] `docs/prossimi-passi.md` e `next-steps.md` aggiornati (Task 9).

## Comandi di verifica

Da `<worktree>/backend`:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_h2 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
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
git diff master --stat -- frontend/src/index.css frontend/src/theme.test.ts frontend/package.json frontend/package-lock.json backend/pyproject.toml
git diff master --name-only -- backend/alembic
```

Expected: i primi due non stampano niente (nessun colore crudo; nessun token, nessuna dipendenza); il terzo solo `backend/alembic/versions/0018_attivita_health_connect.py`. E l'e2e intera con i comandi delle Global Constraints.

## Fuori scope

- La lettura di Health Connect dentro l'app col wrapper Capacitor (decisione 1).
- Il calcolo del dispendio e del fabbisogno, i MET, il metabolismo di base: P2 e H3 (spec §9).
- Gli altri tipi di Health Connect: arrivano, si registrano per nome, non si salvano.
- Cancellare i dati arrivati, scollegare senza rigenerare, più chiavi, un grafico dei passi, più di 7 giorni a video.
- Protobuf/gRPC e il server HTTP locale di HC Webhook.
- Un limitatore di frequenza nell'app (spec §5).
- Tutto quel che fanno gli altri piani della notte.

## Margine di autonomia

- **Liberi:** i nomi di variabili locali, helper di test e funzioni interne non fissati qui; l'ordine dei test dentro un file; l'ordine delle classi Tailwind; la formulazione dei commenti, purché dicano il perché.
- **Fissi:** le parole a video, esattamente come sono scritte nel piano (anche i problemi del backend e i nomi di allenamenti, app e tipi); le rotte, l'intestazione `X-Spena-Token`, i campi delle risposte; i percorsi `/attivita` e `/attivita/collega`; i nomi delle tabelle, delle colonne e dei vincoli; la revisione `0018`; i limiti (2 MB, 4 MB in Nginx, 5.000 voci, 200 righe di registro, 7 giorni, 20 allenamenti, 5 pesate, 24 ore); i nomi pubblici che altri task usano (`parse_payload`, `ParsedPayload`, `StepsDay`, `Exercise`, `Weight`, `merge_steps_day`, `rome_day`, `rome_clock`, `parse_instant`, `exercise_label`, `source_label`, `hc_type_label`, `TOKEN_HEADER`, `WEBHOOK_MAX_BYTES`, `STEPS_NOT_DAILY`, `TOO_BIG`, `NOT_JSON`, `NOT_OBJECT`, `new_token`, `token_hash`, `looks_like_token`, `token_matches`, `ActivityToken`, `ActivityStepsDay`, `ActivityExercise`, `ActivityWeight`, `ActivitySync`, `save_token`, `record_sync`, `SYNCS_KEPT`, `receive_payload`, `reject_payload`, `authenticate_webhook`, `regenerate_token`, `activity_summary`, `ActivityOut`, `TokenOut`, `fetchActivity`, `createToken`, `webhookUrl`, `headersJson`, `WEBHOOK_PATH`, `dayLabel`, `momentText`, `formatSteps`, `formatKg`, `exerciseLine`, `syncText`, `connectionText`, `ignoredText`, `CopyField`, `ActivityScreen`, `ConnectScreen`); i nomi accessibili che l'e2e usa («Passi degli ultimi 7 giorni», «Allenamenti degli ultimi 7 giorni», «Ultime pesate», «I passi in HC Webhook», i campi «Indirizzo», «Chiave», «Intestazioni (JSON)»).
- **Nessuna dipendenza nuova**, nessuna migrazione oltre la `0018`, nessun token di colore nuovo.
- **Un test di oggi si cambia solo dove il piano lo dice** (`AppHeader.test.tsx`, Task 7) — mai per indebolirlo. Se ne serve un'altra migrazione, scrivila nel report con il perché.
- **Una decisione di comportamento non coperta e non reversibile** → si ferma quel task, si fa commit del lavoro parziale sul ramo, lo si segna `bloccato` in `next-steps.md` del ramo con la domanda precisa per Mattia, e si passa al task successivo. Una scelta reversibile e a basso impatto → la più conservativa, annotata nel report della notte.
- Se un test fallisce e non si risolve in modo ragionevole: niente test disattivati, niente asserzioni indebolite; `bloccato` con la diagnosi.

## Dipendenze

**Parte da `master`.** Non consuma niente dagli altri piani della notte. Al merge incontra: H1 su `backend/app/main.py` (la riga degli import dei router e gli `include_router`), su `INDEX` di `AppHeader.tsx` e sul test del fuoco di `AppHeader.test.tsx` (entrambi aggiungono una voce in fondo); S3, R8, le pagine scartate e H1 su `App.tsx` (rotte in punti vicini); quasi tutti su `SCHERMATE` e in fondo a `style.spec.ts`; R5 e S4 sulle migrazioni (numeri riservati, tutte da `0012`).

## Al merge (solo Mattia)

1. **La `down_revision` della `0018`.** In `backend/alembic/versions/0018_attivita_health_connect.py` la riga `down_revision = "0012"` va ripuntata sulla testa di `master` di quel momento (una riga: per esempio `"0017"` se S4 fetta 2 è già dentro). Poi, da `backend/` del checkout:
   ```bash
   PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" alembic heads
   ```
   Expected: **una riga sola**, `0018 (head)`. Se ne escono due, c'è ancora una migrazione con la stessa `down_revision`: ripunta quella che arriva per ultima. Il test `backend/tests/db/test_migration_0018.py` scende alla `0012`: va cambiato `"0012"` nella riga `alembic(scratch_url, "downgrade", "0012")` con la stessa testa.
2. **Il ☰ con H1.** `INDEX` in `frontend/src/components/AppHeader.tsx` tiene entrambe le voci, in quest'ordine: `…, «Anagrafica», «Spese dell'AI», «Attività»`; nel test «il fuoco resta dentro» di `AppHeader.test.tsx` l'ultima voce è `«Attività»`. Il test «il ☰ apre un dialogo con l'indice» tiene entrambe le asserzioni.
3. **`backend/app/main.py`**: gli import e gli `include_router` di `spending` (H1) e `activity` (questo piano) restano entrambi.
4. `SCHERMATE` e il fondo di `style.spec.ts`: si tengono tutte le voci e tutte le prove.

## Dopo il deploy (solo Mattia)

Il deploy è il solito (`docker compose -f docker-compose.prod.yml up -d --build --wait`): il backend applica la `0018` all'avvio. Poi:

1. Sul server, che la migrazione c'è e che la rotta risponde chiusa:
   ```bash
   docker compose -f docker-compose.prod.yml exec -T backend alembic current
   curl -s -o /dev/null -w '%{http_code}\n' -X POST "https://$SPENA_HOST/api/v1/activity/hc-webhook"
   ```
   Expected: `0018 (head)` (o la testa dopo il merge); `401`.
2. Sul telefono, **Samsung Health › Impostazioni › Health Connect**: lascia scrivere a Samsung Health passi, esercizio e peso; tieni attiva la sincronizzazione con Samsung Cloud (i dati dell'orologio passano da lì).
3. **La prova dei 10 minuti** in Health Connect (Impostazioni del telefono › Health Connect, «Connessione Salute» in italiano) › **Dati e accesso**: devono esserci i passi, l'esercizio, le calorie e il peso scritti da Samsung Health, **e i dati di ieri**. Se mancano, il problema è fra Samsung Health e Health Connect, non in Spena: fermati qui.
4. Installa **HC Webhook** («Health Connect to Webhook») da Google Play; togli l'app dall'**ottimizzazione della batteria** (il suo avviso «Ottimizzazione batteria attiva» › «Risolvi ora», o Impostazioni › App › HC Webhook › Batteria › Senza restrizioni).
5. In Spena, ☰ › «Attività» › «Collega HC Webhook» › «Crea la chiave», e segui i dieci passi a video: tipi di dati, «Risoluzione passi» su «Giornaliero», l'indirizzo, le intestazioni JSON, il filtro dei tipi del webhook, «Testa Webhook», l'intervallo.
6. In «Attività»: dopo «Testa Webhook», «Ultima sincronizzazione: …, la prova di HC Webhook»; dopo «Sincronizza ora», i passi di oggi e di ieri, gli allenamenti, le pesate. Confronta i passi di ieri con quelli di Samsung Health: devono coincidere (un numero doppio vorrebbe dire due app che scrivono passi in Health Connect senza priorità). Per i giorni passati, «Sincronizzazione manuale» › «Ultimi 30 giorni».

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `backend/app/db/models/activity.py` (nuovo), `backend/app/db/models/__init__.py` | 1 | i cinque modelli |
| `backend/alembic/versions/0018_attivita_health_connect.py` (nuovo), `backend/tests/db/test_migration_0018.py` (nuovo) | 1 | la migrazione e la sua prova; 1 test |
| `backend/app/domain/activity.py` (nuovo), `backend/tests/domain/test_activity.py` (nuovo) | 2 | la lettura del corpo, `merge_steps_day`, i nomi; 52 test |
| `backend/app/core/webhook_token.py` (nuovo), `backend/tests/test_webhook_token.py` (nuovo) | 3 | la chiave; 11 test |
| `backend/app/repositories/activity.py`, `backend/app/services/activity.py`, `backend/app/schemas/activity.py`, `backend/app/api/activity.py` (nuovi), `backend/app/main.py` | 3 | il webhook |
| `frontend/nginx.conf`, `backend/tests/test_nginx_webhook.py` (nuovo) | 3 | la `location` da 4 MB; 1 test |
| `backend/tests/api/test_activity_webhook.py` (nuovo) | 3 | 21 test |
| `backend/app/services/activity.py`, `backend/app/schemas/activity.py`, `backend/app/api/activity.py`, `backend/tests/api/test_activity.py` (nuovo) | 4 | il riepilogo e la chiave; 10 test |
| `frontend/src/features/activity/types.ts`, `api.ts`, `api.test.ts`, `format.ts`, `format.test.ts` (nuovi) | 5 | i tipi, le chiamate, le parole; 27 test |
| `frontend/src/components/ui/icons.ts`, `frontend/src/features/activity/CopyField.tsx`, `.test.tsx`, `ConnectScreen.tsx`, `.test.tsx` (nuovi) | 6 | `IconCopy`, il campo da copiare, il collegamento; 10 test |
| `frontend/src/features/activity/ActivityScreen.tsx`, `.test.tsx` (nuovi), `frontend/src/App.tsx`, `frontend/src/components/AppHeader.tsx`, `AppHeader.test.tsx` | 7 | la schermata, le rotte, la voce del ☰; 7 test |
| `frontend/e2e/attivita.spec.ts` (nuovo), `frontend/e2e/style.spec.ts` | 8 | 3 prove; due voci in `SCHERMATE` e 1 prova in fondo |
| `docs/prossimi-passi.md`, `next-steps.md` | 9 | i documenti |
| `docs/night-reports/<data>.md` | 10 | il report |

## Review Focus

Le cinque condizioni che la spec implica e che più facilmente pungerebbero Mattia, ciascuna col test che la fissa:

1. **Lo stesso dato che arriva due volte, o un invio vecchio che arriva dopo uno nuovo** (i tre tentativi di HC Webhook, la «Sincronizzazione manuale» sopra quella automatica) — niente doppioni, e il totale del giorno non scende per un pezzo già contato. Fissato da `test_lo_stesso_corpo_due_volte_non_duplica_niente`, `test_il_totale_del_giorno_cresce_e_un_invio_vecchio_non_lo_abbassa`, `test_un_allenamento_rimandato_aggiorna_la_sua_riga` (Task 3), dalla tabella di `test_un_giorno_ha_un_totale_solo_mai_una_somma` (Task 2) e dall'e2e dei due invii (Task 8).
2. **I passi di telefono e orologio contati due volte** — succederebbe con la forma «Completo» o a finestre. Fissato da `test_i_passi_a_finestre_di_minuti_non_si_salvano`, `test_i_passi_grezzi_con_l_origine_non_si_salvano`, `test_due_totali_dello_stesso_giorno_nello_stesso_corpo_non_si_sommano` (Task 2) e `test_i_passi_a_finestre_non_si_salvano_e_si_dice_perche` (Task 3).
3. **Un corpo inatteso** (una versione nuova di HC Webhook, un tipo nuovo, un numero `NaN`, un intero di trenta cifre, un JSON annidato centomila volte, byte che non sono UTF-8) — mai un 500, il resto salvato, il perché a video. Fissato da `test_numeri_impossibili_non_rompono_niente`, `test_un_allenamento_con_campi_nuovi_o_mancanti_si_salva_lo_stesso` (Task 2), `test_un_corpo_che_non_e_un_oggetto_json_e_400_registrato` (cinque casi) e `test_voci_illeggibili_e_tipi_nuovi_non_fermano_il_resto` (Task 3).
4. **Qualcuno su internet che prova la rotta** (senza chiave, con una inventata, col solo cookie dell'app, prima che una chiave esista) — sempre lo stesso 401 vuoto e nessuna scrittura. Fissato dai primi quattro test di `test_activity_webhook.py` (Task 3), da `test_la_chiave_si_crea_si_usa_e_si_rigenera` (la vecchia chiave dopo la rigenerazione, Task 4) e dai due 401 dell'e2e (Task 8).
5. **Un corpo troppo grosso** (Mattia lascia attivi tutti i tipi nel webhook) — rifiutato dal backend e non da Nginx, così «Attività» lo dice. Fissato da `test_un_corpo_troppo_grosso_si_rifiuta_e_si_registra`, `test_anche_senza_lunghezza_dichiarata_il_corpo_si_ferma_al_limite`, `test_nginx_porta_al_backend_i_corpi_oltre_il_limite_del_webhook` (Task 3) e dalla prova dei 3 MB nell'e2e (Task 8).

---

### Task 1: Le cinque tabelle e la migrazione `0018`

**Files:**
- Create: `backend/app/db/models/activity.py`
- Modify: `backend/app/db/models/__init__.py`
- Create: `backend/alembic/versions/0018_attivita_health_connect.py`
- Test: `backend/tests/db/test_migration_0018.py` (nuovo)

**Interfaces:**
- Consumes: `Base` (`app.core.db`), `UUIDMixin` (`app.db.models.base`).
- Produces, in `app.db.models.activity` (i Task 3 e 4 li leggono e li scrivono):
  - `ActivityToken`: tabella `activity_tokens`; `id: int` (`SmallInteger`, chiave, sempre `1`), `token_hash: str` (`String(64)`), `created_at: datetime`, `last_used_at: datetime | None`.
  - `ActivityStepsDay`: tabella `activity_steps_days`; `day: date` (chiave), `steps: int`, `covered_from: datetime`, `covered_to: datetime`, `updated_at: datetime`.
  - `ActivityExercise` (con `id` UUID): tabella `activity_exercises`; `source: str` (`String(120)`, `""` se l'origine manca), `started_at`, `ended_at`, `day: date`, `exercise_type: int | None`, `title: str | None` (`String(200)`), `distance_m: float | None`, `steps: int | None`, `updated_at`; unico `uq_activity_exercises_source_started_at`.
  - `ActivityWeight` (con `id` UUID): tabella `activity_weights`; `source: str`, `measured_at`, `day: date`, `kilograms: float`, `updated_at`; unico `uq_activity_weights_source_measured_at`.
  - `ActivitySync` (con `id` UUID): tabella `activity_syncs`; `received_at`, `status: str` (`ok` | `test` | `rejected`), `app_version: str | None` (`String(40)`), `sent_at: datetime | None`, `body_bytes: int`, `steps_days: int`, `exercises: int`, `weights: int`, `ignored_keys: list[str]` (JSONB), `problems: list[str]` (JSONB).
  - la revisione Alembic `"0018"` con `down_revision = "0012"` (o la testa trovata dalla Preparazione).

- [ ] **Step 1: Il test che fallisce**

Crea `backend/tests/db/test_migration_0018.py`:

```python
"""La migrazione 0018 sale e scende (H2): le cinque tabelle dell'attività.

Su un database suo, creato e distrutto qui, come `test_migration_0012.py`: far scendere
quello della suite toglierebbe le tabelle sotto i piedi a ogni altro test. Alembic gira
in un sottoprocesso, perché il suo template async chiama `asyncio.run`, che dentro un
loop già in corsa esplode.
"""

import os
import subprocess
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://spena:spena@localhost:5433/spena_test"
)
SERVER, _, TEST_DB = TEST_DATABASE_URL.rpartition("/")
SCRATCH_DB = f"{TEST_DB}_migrazione_0018"

TABELLE = (
    "SELECT count(*) FROM information_schema.tables WHERE table_name IN "
    "('activity_tokens', 'activity_steps_days', 'activity_exercises', 'activity_weights', "
    "'activity_syncs')"
)
CHIAVE = (
    "INSERT INTO activity_tokens (id, token_hash, created_at) "
    "VALUES (:id, :impronta, now())"
)
ALLENAMENTO = (
    "INSERT INTO activity_exercises (id, source, started_at, ended_at, day) "
    "VALUES (:id, 'com.sec.android.app.shealth', '2026-10-12T16:00:00Z', :fine, '2026-10-12')"
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


async def test_la_0018_sale_scende_e_risale(scratch_url):
    alembic(scratch_url, "upgrade", "0018")
    assert await _scalar(scratch_url, TABELLE) == 5

    # la chiave è una sola: la riga 1, e nessun'altra
    await _esegui(scratch_url, CHIAVE, id=1, impronta="a" * 64)
    with pytest.raises(IntegrityError):
        await _esegui(scratch_url, CHIAVE, id=2, impronta="b" * 64)

    # lo stesso allenamento della stessa app non entra due volte
    await _esegui(scratch_url, ALLENAMENTO, id=uuid.uuid4(), fine="2026-10-12T16:30:00Z")
    with pytest.raises(IntegrityError):
        await _esegui(scratch_url, ALLENAMENTO, id=uuid.uuid4(), fine="2026-10-12T16:45:00Z")

    alembic(scratch_url, "downgrade", "0012")
    assert await _scalar(scratch_url, TABELLE) == 0

    alembic(scratch_url, "upgrade", "head")
    assert await _scalar(scratch_url, TABELLE) == 5
```

(Se la Preparazione ha trovato su `master` una testa diversa dalla `0012`, il `downgrade` va a quella.)

- [ ] **Step 2: Fallisce**

Run (da `<worktree>/backend`): il comando di pytest con `tests/db/test_migration_0018.py`
Expected: FAIL, Alembic esce con errore («Can't locate revision identified by '0018'»).

- [ ] **Step 3: La migrazione**

Crea `backend/alembic/versions/0018_attivita_health_connect.py`:

```python
"""l'attività da Health Connect via HC Webhook (H2)

Revision ID: 0018
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0018"
# La testa di `master` quando H2 è stato scritto. I piani R5, S4 e H2 partono tutti da
# lì con numeri riservati (0015–0018): al merge questa riga va ripuntata sulla testa di
# `master` di quel momento, e `alembic heads` deve tornare una riga sola.
down_revision = "0012"


def upgrade() -> None:
    # La chiave del webhook: una sola, quindi una riga sola. Se ne tiene l'impronta
    # SHA-256, mai la chiave (app/core/webhook_token.py).
    op.create_table(
        "activity_tokens",
        sa.Column("id", sa.SmallInteger, primary_key=True, autoincrement=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_activity_token_single"),
    )
    # Un totale dei passi per giorno di Roma, con l'intervallo che copre: serve a
    # `merge_steps_day` per decidere se un totale nuovo lo sostituisce. Mai una somma.
    op.create_table(
        "activity_steps_days",
        sa.Column("day", sa.Date, primary_key=True),
        sa.Column("steps", sa.Integer, nullable=False),
        sa.Column("covered_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("covered_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("steps >= 0", name="ck_activity_steps_non_negative"),
        sa.CheckConstraint("covered_to > covered_from", name="ck_activity_steps_span"),
    )
    # Un allenamento per app e istante d'inizio: lo stesso, rimandato, aggiorna la sua
    # riga. Due app sullo stesso tempo restano due righe (il tempo in comune è di P2).
    op.create_table(
        "activity_exercises",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(120), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("exercise_type", sa.Integer, nullable=True),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("distance_m", sa.Float, nullable=True),
        sa.Column("steps", sa.Integer, nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("source", "started_at", name="uq_activity_exercises_source_started_at"),
        sa.CheckConstraint("ended_at >= started_at", name="ck_activity_exercise_span"),
    )
    op.create_table(
        "activity_weights",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(120), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("kilograms", sa.Float, nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("source", "measured_at", name="uq_activity_weights_source_measured_at"),
        sa.CheckConstraint("kilograms > 0", name="ck_activity_weight_positive"),
    )
    # Il registro delle sincronizzazioni: nomi, conteggi e frasi, mai il corpo ricevuto
    # (porterebbe dati di salute che Spena non ha chiesto). Restano le ultime 200 righe.
    op.create_table(
        "activity_syncs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("app_version", sa.String(40), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("body_bytes", sa.Integer, nullable=False),
        sa.Column("steps_days", sa.Integer, nullable=False),
        sa.Column("exercises", sa.Integer, nullable=False),
        sa.Column("weights", sa.Integer, nullable=False),
        sa.Column("ignored_keys", postgresql.JSONB, nullable=False),
        sa.Column("problems", postgresql.JSONB, nullable=False),
        sa.CheckConstraint("status IN ('ok', 'test', 'rejected')", name="ck_activity_sync_status"),
    )


def downgrade() -> None:
    # Scendere perde tutto quel che è arrivato da Health Connect, e la chiave: HC Webhook
    # riceverà 401 finché, risaliti, non se ne crea una nuova.
    for table in (
        "activity_syncs",
        "activity_weights",
        "activity_exercises",
        "activity_steps_days",
        "activity_tokens",
    ):
        op.drop_table(table)
```

- [ ] **Step 4: I modelli**

Crea `backend/app/db/models/activity.py`:

```python
"""L'attività che arriva da Health Connect via HC Webhook (H2, migrazione 0018).

I giorni (`day`) sono giorni di calendario a Roma, come la scadenza (`PANTRY_TZ`): li
calcola `app.domain.activity` dall'istante, e si scrivono accanto a lui perché P2 conterà
per giorno. Le righe le scrive solo `app.services.activity`.
"""

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.db.models.base import UUIDMixin


class ActivityToken(Base):
    """La chiave del webhook: una sola, quindi una riga sola (`id = 1`).

    Si tiene l'impronta (`app.core.webhook_token.token_hash`), mai la chiave: si vede una
    volta, quando si crea, e chi legge il database non la ritrova.
    """

    __tablename__ = "activity_tokens"
    __table_args__ = (CheckConstraint("id = 1", name="ck_activity_token_single"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ActivityStepsDay(Base):
    """Il totale dei passi di un giorno di Roma, con l'intervallo che copre.

    L'intervallo serve a `merge_steps_day`: un totale arrivato dopo sostituisce questo
    solo se ne copre almeno l'intervallo, e i due non si sommano mai (spec H2 §3.2).
    """

    __tablename__ = "activity_steps_days"
    __table_args__ = (
        CheckConstraint("steps >= 0", name="ck_activity_steps_non_negative"),
        CheckConstraint("covered_to > covered_from", name="ck_activity_steps_span"),
    )

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    steps: Mapped[int] = mapped_column(Integer, nullable=False)
    covered_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    covered_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ActivityExercise(UUIDMixin, Base):
    """Un allenamento, uno per app (`source`, il `data_origin` di Health Connect) e inizio.

    `exercise_type` è la costante intera di Health Connect, non tradotta: è la chiave su
    cui P2 metterà i MET. Il nome a video lo dà `exercise_label`.
    """

    __tablename__ = "activity_exercises"
    __table_args__ = (
        UniqueConstraint("source", "started_at", name="uq_activity_exercises_source_started_at"),
        CheckConstraint("ended_at >= started_at", name="ck_activity_exercise_span"),
    )

    source: Mapped[str] = mapped_column(String(120), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    exercise_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    # i passi dentro l'allenamento: a P2 servono per non contarli due volte col totale
    steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ActivityWeight(UUIDMixin, Base):
    __tablename__ = "activity_weights"
    __table_args__ = (
        UniqueConstraint("source", "measured_at", name="uq_activity_weights_source_measured_at"),
        CheckConstraint("kilograms > 0", name="ck_activity_weight_positive"),
    )

    source: Mapped[str] = mapped_column(String(120), nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    kilograms: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ActivitySync(UUIDMixin, Base):
    """Una sincronizzazione arrivata con la chiave giusta: com'è andata, mai cosa portava.

    `received_at` lo scrive chi chiama, non `now()`: dentro una transazione `now()` è
    fermo, e due righe della stessa prova non avrebbero un ordine.
    """

    __tablename__ = "activity_syncs"
    __table_args__ = (
        CheckConstraint("status IN ('ok', 'test', 'rejected')", name="ck_activity_sync_status"),
    )

    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    app_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    body_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    steps_days: Mapped[int] = mapped_column(Integer, nullable=False)
    exercises: Mapped[int] = mapped_column(Integer, nullable=False)
    weights: Mapped[int] = mapped_column(Integer, nullable=False)
    # i nomi delle chiavi del corpo che Spena non usa, e i problemi in italiano
    ignored_keys: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    problems: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
```

In `backend/app/db/models/__init__.py`:

1. Prima della riga `from app.db.models.ingredient import Ingredient, IngredientAlias` aggiungi:
   ```python
   from app.db.models.activity import (
       ActivityExercise,
       ActivityStepsDay,
       ActivitySync,
       ActivityToken,
       ActivityWeight,
   )
   ```
2. In `__all__`, in testa all'elenco (prima di `"CookingEvent",`), aggiungi:
   ```python
       "ActivityExercise",
       "ActivityStepsDay",
       "ActivitySync",
       "ActivityToken",
       "ActivityWeight",
   ```

- [ ] **Step 5: Passano, con la rete di sicurezza dell'autogenerate**

Run: il comando di pytest con `tests/db/`
Expected: PASS, compreso `test_metadata_matches_migrations.py` (modelli e schema coincidono: nessuna operazione proposta) e il test nuovo. Se `test_models_describe_the_migrated_schema` propone un'operazione, confronta nome, tipo e `nullable` della colonna o del vincolo unico fra migrazione e modello: devono dire la stessa cosa.

- [ ] **Step 6: Commit**

```bash
git add backend/app/db/models/activity.py backend/app/db/models/__init__.py \
  backend/alembic/versions/0018_attivita_health_connect.py backend/tests/db/test_migration_0018.py
git commit -m "feat(db): H2, le cinque tabelle dell'attività da Health Connect (migrazione 0018)"
```

---

### Task 2: Il dominio — leggere il corpo di HC Webhook, un totale dei passi al giorno, i nomi

**Files:**
- Create: `backend/app/domain/activity.py`
- Test: `backend/tests/domain/test_activity.py` (nuovo)

**Interfaces:**
- Consumes: `PANTRY_TZ` (`ZoneInfo("Europe/Rome")`) da `app.domain.rules`.
- Produces, in `app.domain.activity` (i Task 3 e 4 li usano):
  - costanti: `TOKEN_HEADER = "X-Spena-Token"`, `WEBHOOK_MAX_BYTES = 2 * 1024 * 1024`, `MAX_RECORDS = 5000`; le frasi `STEPS_NOT_DAILY`, `TOO_BIG`, `NOT_JSON`, `NOT_OBJECT`.
  - `@dataclass(frozen=True) StepsDay(day: date, steps: int, covered_from: datetime, covered_to: datetime)`.
  - `@dataclass(frozen=True) Exercise(source: str, started_at: datetime, ended_at: datetime, exercise_type: int | None, title: str | None, distance_m: float | None, steps: int | None)` con la proprietà `day: date`.
  - `@dataclass(frozen=True) Weight(source: str, measured_at: datetime, kilograms: float)` con la proprietà `day: date`.
  - `@dataclass(frozen=True) ParsedPayload(is_test: bool, app_version: str | None, sent_at: datetime | None, steps_days: list[StepsDay], exercises: list[Exercise], weights: list[Weight], ignored_keys: list[str], problems: list[str])`.
  - `parse_payload(body: Mapping[str, object]) -> ParsedPayload` (non solleva mai); `merge_steps_day(stored: StepsDay | None, incoming: StepsDay) -> StepsDay`; `parse_instant(value: object) -> datetime | None`; `rome_day(instant: datetime) -> date`; `rome_clock(instant: datetime) -> str` («18:05»).
  - `EXERCISE_LABELS: dict[int, str]`, `exercise_label(exercise_type: int | None) -> str`; `SOURCE_LABELS`, `source_label(source: str) -> str`; `HC_TYPE_LABELS`, `hc_type_label(key: str) -> str`.

- [ ] **Step 1: I test che falliscono**

Crea `backend/tests/domain/test_activity.py`:

```python
"""H2, la parte pura: leggere il corpo di HC Webhook e tenere un totale dei passi al giorno.

I corpi qui sono scritti a mano sul formato di `docs/webhook.md` di HC Webhook (letto il
2026-10-13). Gli istanti sono in UTC come li manda l'app; i giorni sono quelli di Roma.
"""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.domain import activity
from app.domain.activity import (
    STEPS_NOT_DAILY,
    Exercise,
    StepsDay,
    Weight,
    exercise_label,
    hc_type_label,
    merge_steps_day,
    parse_instant,
    parse_payload,
    rome_clock,
    rome_day,
    source_label,
)

SAMSUNG = {
    "data_origin": "com.sec.android.app.shealth",
    "recording_method": "automatically_recorded",
}


def utc(*parti: int) -> datetime:
    return datetime(*parti, tzinfo=UTC)


def passi(conta, inizio: str, fine: str, **altro) -> dict:
    return {"count": conta, "start_time": inizio, "end_time": fine, **altro}


@pytest.mark.parametrize(
    ("testo", "istante"),
    [
        ("2026-10-12T07:30:00Z", utc(2026, 10, 12, 7, 30)),
        ("2026-10-12T07:30:00.123Z", utc(2026, 10, 12, 7, 30, 0, 123000)),
        # `Instant.toString()` di Android arriva ai nanosecondi: Python ne tiene sei
        ("2026-10-12T07:30:00.123456789Z", utc(2026, 10, 12, 7, 30, 0, 123456)),
        ("2026-10-12T09:30:00+02:00", utc(2026, 10, 12, 7, 30)),
    ],
)
def test_un_istante_di_hc_webhook_si_legge(testo, istante):
    assert parse_instant(testo) == istante


@pytest.mark.parametrize(
    "valore",
    [
        None,
        1760254200,
        "",
        "ieri",
        "2026-10-12T07:30:00",  # senza fuso: non si sa quando
        "1970-01-01T00:00:00Z",  # prima del 2000: un orologio a zero, non un dato
        "2026-10-12T07:30:00Z" + " " * 30,  # troppo lungo per essere un istante
    ],
)
def test_un_istante_illeggibile_non_si_legge(valore):
    assert parse_instant(valore) is None


@pytest.mark.parametrize(
    ("istante", "giorno"),
    [
        (utc(2026, 10, 12, 22, 30), date(2026, 10, 13)),  # 00:30 a Roma, ora legale
        (utc(2026, 10, 12, 21, 30), date(2026, 10, 12)),  # 23:30 a Roma
        (utc(2026, 1, 15, 23, 30), date(2026, 1, 16)),  # 00:30 a Roma, ora solare
    ],
)
def test_il_giorno_e_quello_di_roma(istante, giorno):
    assert rome_day(istante) == giorno


def test_l_ora_e_quella_di_roma():
    assert rome_clock(utc(2026, 10, 12, 16, 5)) == "18:05"


GIORNO = date(2026, 10, 12)
MEZZANOTTE = utc(2026, 10, 11, 22)  # la mezzanotte del 12 a Roma
ORE_8 = MEZZANOTTE + timedelta(hours=8)
ORE_14 = MEZZANOTTE + timedelta(hours=14)
FINE = MEZZANOTTE + timedelta(days=1)


def totale(conta: int, dalle: datetime, alle: datetime) -> StepsDay:
    return StepsDay(day=GIORNO, steps=conta, covered_from=dalle, covered_to=alle)


@pytest.mark.parametrize(
    ("tenuto", "arrivato", "atteso"),
    [
        # niente di tenuto: si tiene quel che arriva
        (None, totale(800, MEZZANOTTE, ORE_8), totale(800, MEZZANOTTE, ORE_8)),
        # dalla mezzanotte a più tardi: copre di più, sostituisce
        (
            totale(800, MEZZANOTTE, ORE_8),
            totale(5000, MEZZANOTTE, ORE_14),
            totale(5000, MEZZANOTTE, ORE_14),
        ),
        # lo stesso intervallo, più basso: è una correzione, sostituisce
        (
            totale(5000, MEZZANOTTE, ORE_14),
            totale(4800, MEZZANOTTE, ORE_14),
            totale(4800, MEZZANOTTE, ORE_14),
        ),
        # un pezzo già contato (arriva tardi un invio vecchio): si ignora
        (
            totale(9000, MEZZANOTTE, FINE),
            totale(5000, MEZZANOTTE, ORE_14),
            totale(9000, MEZZANOTTE, FINE),
        ),
        # dopo un buco di più di un giorno: due pezzi sovrapposti, resta il più alto
        (totale(5000, MEZZANOTTE, ORE_14), totale(7000, ORE_8, FINE), totale(7000, ORE_8, FINE)),
        (
            totale(5000, MEZZANOTTE, ORE_14),
            totale(3000, ORE_8, FINE),
            totale(5000, MEZZANOTTE, ORE_14),
        ),
    ],
)
def test_un_giorno_ha_un_totale_solo_mai_una_somma(tenuto, arrivato, atteso):
    assert merge_steps_day(tenuto, arrivato) == atteso


def test_i_passi_giornalieri_si_leggono_un_giorno_per_uno():
    corpo = {
        "timestamp": "2026-10-12T12:00:00.500Z",
        "app_version": "2.4.0",
        "steps": [
            # il giorno prima, intero: dalla mezzanotte alla mezzanotte di Roma
            passi(9876, "2026-10-10T22:00:00Z", "2026-10-11T22:00:00Z"),
            # oggi, da mezzanotte ad adesso: la fine porta i millesimi
            passi(4321, "2026-10-11T22:00:00Z", "2026-10-12T12:00:00.123Z"),
        ],
    }

    letto = parse_payload(corpo)

    assert letto.problems == []
    assert [(giorno.day, giorno.steps) for giorno in letto.steps_days] == [
        (date(2026, 10, 11), 9876),
        (date(2026, 10, 12), 4321),
    ]
    assert letto.app_version == "2.4.0"
    assert letto.sent_at == utc(2026, 10, 12, 12, 0, 0, 500000)
    assert letto.is_test is False


def test_i_passi_a_finestre_di_minuti_non_si_salvano():
    """«15 min» somma gli intervalli grezzi di tutte le app: i doppioni di telefono e
    orologio tornerebbero. Si dice come rimediare, e non si salva niente."""
    corpo = {
        "steps": [
            passi(120, "2026-10-12T06:00:00Z", "2026-10-12T06:15:00Z"),
            passi(340, "2026-10-12T06:15:00Z", "2026-10-12T06:30:00Z"),
        ]
    }

    letto = parse_payload(corpo)

    assert letto.steps_days == []
    assert letto.problems == [STEPS_NOT_DAILY]


def test_i_passi_grezzi_con_l_origine_non_si_salvano():
    corpo = {
        "steps": [
            passi(4321, "2026-10-11T22:00:00Z", "2026-10-12T12:00:00.123Z", metadata=SAMSUNG)
        ]
    }

    letto = parse_payload(corpo)

    assert letto.steps_days == []
    assert letto.problems == [STEPS_NOT_DAILY]


def test_due_totali_dello_stesso_giorno_nello_stesso_corpo_non_si_sommano():
    corpo = {
        "steps": [
            passi(5000, "2026-10-11T22:00:00Z", "2026-10-12T12:00:00.100Z"),
            passi(7000, "2026-10-12T06:00:00.200Z", "2026-10-12T22:00:00Z"),
        ]
    }

    letto = parse_payload(corpo)

    assert [(giorno.day, giorno.steps) for giorno in letto.steps_days] == [
        (date(2026, 10, 12), 7000)
    ]


def test_le_voci_illeggibili_si_scartano_e_si_contano_le_altre_restano():
    corpo = {
        "steps": [
            passi(4321, "2026-10-11T22:00:00Z", "2026-10-12T12:00:00.123Z"),
            passi("tanti", "2026-10-10T22:00:00Z", "2026-10-11T22:00:00Z"),
            passi(True, "2026-10-09T22:00:00Z", "2026-10-10T22:00:00Z"),
            passi(-1, "2026-10-08T22:00:00Z", "2026-10-09T22:00:00Z"),
            # finisce prima di cominciare
            passi(100, "2026-10-08T22:00:00Z", "2026-10-07T22:00:00Z"),
            "non un oggetto",
        ]
    }

    letto = parse_payload(corpo)

    assert [giorno.steps for giorno in letto.steps_days] == [4321]
    assert letto.problems == ["Passi: 5 voci illeggibili, scartate."]


def test_una_voce_illeggibile_si_dice_al_singolare():
    corpo = {"weight": [{"kilograms": 72.4, "time": "2026-10-12T05:30:00Z"}, {"kilograms": 72.4}]}

    letto = parse_payload(corpo)

    assert len(letto.weights) == 1
    assert letto.problems == ["Pesate: 1 voce illeggibile, scartata."]


def test_un_tipo_che_non_e_un_elenco_si_salta():
    corpo = {
        "exercise": {"type": "56"},
        "weight": [{"kilograms": 72.4, "time": "2026-10-12T05:30:00Z"}],
    }

    letto = parse_payload(corpo)

    assert letto.exercises == []
    assert len(letto.weights) == 1
    assert letto.problems == ["Allenamenti: non è un elenco, non letto."]


def test_oltre_le_voci_massime_si_leggono_le_prime(monkeypatch):
    monkeypatch.setattr(activity, "MAX_RECORDS", 3)
    pesate = [{"kilograms": 70 + i, "time": f"2026-10-0{i + 1}T05:30:00Z"} for i in range(5)]

    letto = parse_payload({"weight": pesate})

    assert [pesata.kilograms for pesata in letto.weights] == [70.0, 71.0, 72.0]
    assert letto.problems == ["Pesate: 5 voci, lette le prime 3."]


def test_un_allenamento_si_legge_con_tutto_quel_che_porta():
    corpo = {
        "exercise": [
            {
                "type": "56",
                "title": "Giro del parco",
                "start_time": "2026-10-12T16:00:00Z",
                "end_time": "2026-10-12T16:32:00Z",
                "duration_seconds": 1920,
                "distance_meters": 5100.5,
                "steps": 5400,
                "avg_cadence_spm": 168.2,
                "metadata": SAMSUNG,
            }
        ]
    }

    letto = parse_payload(corpo)

    assert letto.problems == []
    assert letto.exercises == [
        Exercise(
            source="com.sec.android.app.shealth",
            started_at=utc(2026, 10, 12, 16),
            ended_at=utc(2026, 10, 12, 16, 32),
            exercise_type=56,
            title="Giro del parco",
            distance_m=5100.5,
            steps=5400,
        )
    ]
    assert letto.exercises[0].day == date(2026, 10, 12)


def test_un_allenamento_con_campi_nuovi_o_mancanti_si_salva_lo_stesso():
    corpo = {
        "exercise": [
            {
                "type": "EXERCISE_TYPE_DEL_FUTURO",
                # durata zero: certi orologi lo fanno
                "start_time": "2026-10-12T16:00:00Z",
                "end_time": "2026-10-12T16:00:00Z",
                "distance_meters": "lontano",
                "steps": -3,
                "campo_nuovo": {"a": 1},
            }
        ]
    }

    letto = parse_payload(corpo)

    assert letto.problems == []
    (allenamento,) = letto.exercises
    assert (allenamento.source, allenamento.exercise_type, allenamento.title) == ("", None, None)
    assert (allenamento.distance_m, allenamento.steps) == (None, None)


def test_un_allenamento_senza_tempi_sensati_si_scarta():
    corpo = {
        "exercise": [
            {"type": "56", "start_time": "2026-10-12T16:00:00Z", "end_time": "2026-10-12T15:00:00Z"},
            # più di 48 ore
            {"type": "56", "start_time": "2026-10-10T16:00:00Z", "end_time": "2026-10-12T17:00:00Z"},
            {"type": "56", "start_time": "2026-10-12T16:00:00Z"},
        ]
    }

    letto = parse_payload(corpo)

    assert letto.exercises == []
    assert letto.problems == ["Allenamenti: 3 voci illeggibili, scartate."]


def test_lo_stesso_allenamento_due_volte_nello_stesso_corpo_e_uno():
    voce = {
        "type": "79",
        "start_time": "2026-10-12T16:00:00Z",
        "end_time": "2026-10-12T16:20:00Z",
        "metadata": SAMSUNG,
    }
    piu_lungo = {**voce, "end_time": "2026-10-12T16:25:00Z"}

    letto = parse_payload({"exercise": [voce, piu_lungo]})

    assert [allenamento.ended_at for allenamento in letto.exercises] == [utc(2026, 10, 12, 16, 25)]


def test_le_pesate_si_leggono_e_quelle_impossibili_si_scartano():
    corpo = {
        "weight": [
            {"kilograms": 72.4, "time": "2026-10-12T05:30:00Z", "metadata": SAMSUNG},
            {"kilograms": 1.0, "time": "2026-10-11T05:30:00Z"},
            {"kilograms": 500, "time": "2026-10-10T05:30:00Z"},
        ]
    }

    letto = parse_payload(corpo)

    assert letto.weights == [
        Weight(
            source="com.sec.android.app.shealth",
            measured_at=utc(2026, 10, 12, 5, 30),
            kilograms=72.4,
        )
    ]
    assert letto.weights[0].day == date(2026, 10, 12)
    assert letto.problems == ["Pesate: 2 voci illeggibili, scartate."]


def test_i_tipi_che_spena_non_usa_si_registrano_solo_per_nome():
    corpo = {
        "timestamp": "2026-10-12T12:00:00Z",
        "app_version": "2.4.0",
        "test": False,
        "sleep": [{"session_end_time": "2026-10-12T05:00:00Z"}],
        "heart_rate": [{"bpm": 70, "time": "2026-10-12T06:00:00Z"}],
        "x" * 60: [1],
    }

    letto = parse_payload(corpo)

    assert letto.ignored_keys == ["heart_rate", "sleep", "x" * 40]
    assert letto.problems == []


@pytest.mark.parametrize(
    ("valore", "prova"), [(True, True), ("true", False), (1, False), (None, False)]
)
def test_la_prova_di_hc_webhook_e_solo_test_true(valore, prova):
    assert parse_payload({"test": valore}).is_test is prova


def test_versione_e_istante_del_corpo_sono_facoltativi():
    letto = parse_payload({"timestamp": "ieri", "app_version": "v" * 100})

    assert letto.sent_at is None
    assert letto.app_version == "v" * 40
    assert letto.problems == []


def test_un_corpo_vuoto_va_bene():
    letto = parse_payload({})

    assert (letto.steps_days, letto.exercises, letto.weights) == ([], [], [])
    assert (letto.ignored_keys, letto.problems) == ([], [])


def test_numeri_impossibili_non_rompono_niente():
    corpo = {
        "steps": [
            passi(10**30, "2026-10-11T22:00:00Z", "2026-10-12T12:00:00.1Z"),
            passi(float("inf"), "2026-10-10T22:00:00Z", "2026-10-11T22:00:00Z"),
        ],
        "exercise": [
            {
                "type": 10**20,
                "start_time": "2026-10-12T16:00:00Z",
                "end_time": "2026-10-12T16:20:00Z",
                "distance_meters": 10**400,
            }
        ],
        "weight": [
            {"kilograms": float("nan"), "time": "2026-10-12T05:30:00Z"},
            {"kilograms": 10**400, "time": "2026-10-12T05:31:00Z"},
        ],
    }

    letto = parse_payload(corpo)

    assert (letto.steps_days, letto.weights) == ([], [])
    assert [(a.exercise_type, a.distance_m) for a in letto.exercises] == [(None, None)]
    assert letto.problems == [
        "Passi: 2 voci illeggibili, scartate.",
        "Pesate: 2 voci illeggibili, scartate.",
    ]


@pytest.mark.parametrize(
    ("tipo", "nome"),
    [
        (56, "Corsa"),
        (79, "Camminata"),
        (70, "Allenamento di forza"),
        (None, "Allenamento"),
        (9999, "Allenamento"),
    ],
)
def test_il_nome_di_un_allenamento(tipo, nome):
    assert exercise_label(tipo) == nome


@pytest.mark.parametrize(
    ("origine", "nome"),
    [
        ("com.sec.android.app.shealth", "Samsung Health"),
        ("", "origine non indicata"),
        ("com.esempio.app", "com.esempio.app"),
    ],
)
def test_il_nome_di_un_app(origine, nome):
    assert source_label(origine) == nome


@pytest.mark.parametrize(
    ("chiave", "nome"),
    [("heart_rate", "frequenza cardiaca"), ("tipo_del_futuro", "tipo_del_futuro")],
)
def test_il_nome_di_un_tipo_non_usato(chiave, nome):
    assert hc_type_label(chiave) == nome
```

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/backend`): il comando di pytest con `tests/domain/test_activity.py`
Expected: FAIL in raccolta — `ModuleNotFoundError: No module named 'app.domain.activity'`.

- [ ] **Step 3: Il modulo**

Crea `backend/app/domain/activity.py`:

```python
"""L'attività da Health Connect (H2): leggere il corpo di HC Webhook, senza database.

HC Webhook (https://github.com/mcnaveen/health-connect-webhook) legge Health Connect sul
telefono e manda a un indirizzo un oggetto JSON: `timestamp` e `app_version` sempre, poi
un elenco per ogni tipo che ha qualcosa di nuovo. Spena ne usa tre — `steps`, `exercise`,
`weight` (decisione di Mattia del 2026-10-13) — e degli altri registra solo il nome. Il
formato è quello di `docs/webhook.md` del progetto, letto il 2026-10-13; l'app può
aggiungere tipi e campi a ogni versione, e qui nessuna voce inattesa fa cadere le altre:
`parse_payload` non solleva mai, salva quel che capisce e dice in italiano cosa ha scartato.

Puro come `rules.py`: niente database, niente orologio. I giorni sono giorni di Roma
(`PANTRY_TZ`), come la scadenza.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.domain.rules import PANTRY_TZ

# L'intestazione che porta la chiave (spec H2 §3.1): un nome solo da incollare, senza il
# «Bearer » da scrivere a mano sul telefono.
TOKEN_HEADER = "X-Spena-Token"
# Oltre, il corpo si rifiuta. Spena coi suoi tre tipi riceve pochi kB; 2 MB servono a chi
# lascia attivi tutti i 31 tipi. Nginx ne lascia passare 4 (frontend/nginx.conf), così il
# rifiuto lo dà il backend, e si vede in «Attività».
WEBHOOK_MAX_BYTES = 2 * 1024 * 1024

ENVELOPE_KEYS = frozenset({"timestamp", "app_version", "test"})
USED_KEYS = frozenset({"steps", "exercise", "weight"})

MAX_RECORDS = 5000
MAX_DAY_STEPS = 200_000
# un giorno con il cambio dell'ora dura 25 ore; 26 lascia un margine al fuso del telefono
MAX_STEPS_SPAN = timedelta(hours=26)
# le finestre di HC Webhook sono di 1, 5 o 15 minuti; sotto l'ora, al minuto tondo, è una
# finestra e non un totale del giorno (vedi `_is_daily_total`)
BUCKET_SPAN = timedelta(minutes=60)
MAX_EXERCISE_SPAN = timedelta(hours=48)
MAX_EXERCISE_STEPS = 200_000
MAX_DISTANCE_M = 1_000_000.0
MIN_KG = 2.0
MAX_KG = 400.0
MAX_EXERCISE_TYPE = 10_000
MAX_SOURCE = 120
MAX_TITLE = 200
MAX_APP_VERSION = 40
MAX_KEY = 40
MAX_IGNORED_KEYS = 50
MAX_INSTANT_TEXT = 40

STEPS_LABEL = "Passi"
EXERCISES_LABEL = "Allenamenti"
WEIGHTS_LABEL = "Pesate"

STEPS_NOT_DAILY = (
    "Passi non salvati: arrivano a intervalli e non come totale del giorno. In HC Webhook, "
    "alla voce «Risoluzione passi», scegli «Giornaliero»."
)
TOO_BIG = (
    "Rifiutato: il corpo supera i 2 MB. Nel webhook di Spena, in HC Webhook, lascia solo "
    "Passi, Sessioni di esercizio e Peso."
)
NOT_JSON = "Rifiutato: il corpo non è JSON."
NOT_OBJECT = "Rifiutato: il corpo è JSON, ma non un oggetto."


def rome_day(instant: datetime) -> date:
    """Il giorno di calendario a Roma di un istante."""
    return instant.astimezone(PANTRY_TZ).date()


def rome_clock(instant: datetime) -> str:
    """L'ora a Roma, «18:05»: il frontend non sa di fusi."""
    return instant.astimezone(PANTRY_TZ).strftime("%H:%M")


@dataclass(frozen=True)
class StepsDay:
    """Il totale dei passi di un giorno di Roma, con l'intervallo che copre."""

    day: date
    steps: int
    covered_from: datetime
    covered_to: datetime


@dataclass(frozen=True)
class Exercise:
    # il `data_origin` di Health Connect, `""` se manca
    source: str
    started_at: datetime
    ended_at: datetime
    # la costante di Health Connect (56 è la corsa), `None` se illeggibile
    exercise_type: int | None
    title: str | None
    distance_m: float | None
    steps: int | None

    @property
    def day(self) -> date:
        return rome_day(self.started_at)


@dataclass(frozen=True)
class Weight:
    source: str
    measured_at: datetime
    kilograms: float

    @property
    def day(self) -> date:
        return rome_day(self.measured_at)


@dataclass(frozen=True)
class ParsedPayload:
    is_test: bool
    app_version: str | None
    sent_at: datetime | None
    steps_days: list[StepsDay]
    exercises: list[Exercise]
    weights: list[Weight]
    # i nomi delle chiavi del corpo che Spena non usa, ordinati
    ignored_keys: list[str]
    # in italiano, nell'ordine passi, allenamenti, pesate: si mostrano così in «Attività»
    problems: list[str]


def parse_instant(value: object) -> datetime | None:
    """Un istante ISO-8601 col fuso (`Instant.toString()`, fino ai nanosecondi), o `None`.

    Senza fuso non si sa quando; prima del 2000 o dopo il 2100 è un orologio sbagliato.
    """
    if not isinstance(value, str) or len(value) > MAX_INSTANT_TEXT:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None or not 2000 <= parsed.year <= 2100:
        return None
    return parsed


def _int(value: object) -> int | None:
    # `True` è un `int` per Python, e un conteggio per nessuno
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    return None


def _float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    try:
        number = float(value)
    except OverflowError:
        # un intero di quattrocento cifre: JSON lo permette, un float no
        return None
    return number if math.isfinite(number) else None


def _text(value: object, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text[:limit] if text else None


def _records(raw: object, label: str, problems: list[str]) -> list[object]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        problems.append(f"{label}: non è un elenco, non letto.")
        return []
    if len(raw) > MAX_RECORDS:
        problems.append(f"{label}: {len(raw)} voci, lette le prime {MAX_RECORDS}.")
        return raw[:MAX_RECORDS]
    return raw


def _unreadable(label: str, count: int, problems: list[str]) -> None:
    if count == 1:
        problems.append(f"{label}: 1 voce illeggibile, scartata.")
    elif count > 1:
        problems.append(f"{label}: {count} voci illeggibili, scartate.")


def _source(record: Mapping) -> str:
    metadata = record.get("metadata")
    if not isinstance(metadata, Mapping):
        return ""
    return _text(metadata.get("data_origin"), MAX_SOURCE) or ""


def merge_steps_day(stored: StepsDay | None, incoming: StepsDay) -> StepsDay:
    """Il totale di un giorno, fra quello tenuto e uno nuovo dello stesso giorno: mai la somma.

    Un totale che copre almeno l'intervallo tenuto lo sostituisce, anche se più basso: è lo
    stesso giorno visto più tardi, o corretto. Uno che ci sta dentro è un pezzo già contato
    (un invio vecchio arrivato dopo). Due pezzi che si sovrappongono solo in parte — succede
    dopo un buco di più di un giorno fra due sincronizzazioni — sono due stime per difetto
    dello stesso giorno: resta la più alta, perché sommarle conterebbe due volte le ore in
    comune.
    """
    if stored is None:
        return incoming
    if incoming.covered_from <= stored.covered_from and incoming.covered_to >= stored.covered_to:
        return incoming
    if incoming.covered_from >= stored.covered_from and incoming.covered_to <= stored.covered_to:
        return stored
    return incoming if incoming.steps > stored.steps else stored


def _steps_reading(record: object) -> StepsDay | None:
    if not isinstance(record, Mapping):
        return None
    start = parse_instant(record.get("start_time"))
    end = parse_instant(record.get("end_time"))
    count = _int(record.get("count"))
    if start is None or end is None or count is None:
        return None
    if not start < end <= start + MAX_STEPS_SPAN or not 0 <= count <= MAX_DAY_STEPS:
        return None
    return StepsDay(day=rome_day(start), steps=count, covered_from=start, covered_to=end)


def _is_daily_total(record: object, reading: StepsDay) -> bool:
    """Vero se il record è un totale del giorno, la forma «Giornaliero» di HC Webhook.

    È l'unica calcolata con la lettura aggregata di Health Connect, che toglie i doppioni
    fra le app (spec H2 §3.2). «Completo» porta `metadata`, un record per app e intervallo;
    le finestre di 1, 5 o 15 minuti cominciano e finiscono al minuto tondo. Un totale del
    giorno o dura un giorno intero o finisce «adesso», coi millesimi.
    """
    if isinstance(record, Mapping) and "metadata" in record:
        return False
    on_the_minute = all(
        instant.second == 0 and instant.microsecond == 0
        for instant in (reading.covered_from, reading.covered_to)
    )
    return not (on_the_minute and reading.covered_to - reading.covered_from <= BUCKET_SPAN)


def _steps(raw: object, problems: list[str]) -> list[StepsDay]:
    by_day: dict[date, StepsDay] = {}
    unreadable = 0
    not_daily = 0
    for record in _records(raw, STEPS_LABEL, problems):
        reading = _steps_reading(record)
        if reading is None:
            unreadable += 1
            continue
        if not _is_daily_total(record, reading):
            not_daily += 1
            continue
        by_day[reading.day] = merge_steps_day(by_day.get(reading.day), reading)
    _unreadable(STEPS_LABEL, unreadable, problems)
    if not_daily:
        problems.append(STEPS_NOT_DAILY)
    return sorted(by_day.values(), key=lambda reading: reading.day)


def _exercise_type(value: object) -> int | None:
    # HC Webhook manda la costante come stringa («56»); un intero va bene lo stesso
    if isinstance(value, str):
        text = value.strip()
        number = int(text) if text.isascii() and text.isdigit() and len(text) <= 5 else None
    else:
        number = _int(value)
    return number if number is not None and 0 <= number <= MAX_EXERCISE_TYPE else None


def _exercise(record: object) -> Exercise | None:
    if not isinstance(record, Mapping):
        return None
    start = parse_instant(record.get("start_time"))
    end = parse_instant(record.get("end_time"))
    # durata zero sì: certi orologi scrivono sessioni così
    if start is None or end is None or not start <= end <= start + MAX_EXERCISE_SPAN:
        return None
    distance = _float(record.get("distance_meters"))
    if distance is not None and not 0 <= distance <= MAX_DISTANCE_M:
        distance = None
    steps = _int(record.get("steps"))
    if steps is not None and not 0 <= steps <= MAX_EXERCISE_STEPS:
        steps = None
    return Exercise(
        source=_source(record),
        started_at=start,
        ended_at=end,
        exercise_type=_exercise_type(record.get("type")),
        title=_text(record.get("title"), MAX_TITLE),
        distance_m=distance,
        steps=steps,
    )


def _exercises(raw: object, problems: list[str]) -> list[Exercise]:
    # lo stesso allenamento due volte nello stesso corpo: vale l'ultimo
    found: dict[tuple[str, datetime], Exercise] = {}
    unreadable = 0
    for record in _records(raw, EXERCISES_LABEL, problems):
        exercise = _exercise(record)
        if exercise is None:
            unreadable += 1
            continue
        found[(exercise.source, exercise.started_at)] = exercise
    _unreadable(EXERCISES_LABEL, unreadable, problems)
    return sorted(found.values(), key=lambda exercise: (exercise.started_at, exercise.source))


def _weight(record: object) -> Weight | None:
    if not isinstance(record, Mapping):
        return None
    measured_at = parse_instant(record.get("time"))
    kilograms = _float(record.get("kilograms"))
    if measured_at is None or kilograms is None or not MIN_KG <= kilograms <= MAX_KG:
        return None
    return Weight(source=_source(record), measured_at=measured_at, kilograms=kilograms)


def _weights(raw: object, problems: list[str]) -> list[Weight]:
    found: dict[tuple[str, datetime], Weight] = {}
    unreadable = 0
    for record in _records(raw, WEIGHTS_LABEL, problems):
        weight = _weight(record)
        if weight is None:
            unreadable += 1
            continue
        found[(weight.source, weight.measured_at)] = weight
    _unreadable(WEIGHTS_LABEL, unreadable, problems)
    return sorted(found.values(), key=lambda weight: (weight.measured_at, weight.source))


def parse_payload(body: Mapping[str, object]) -> ParsedPayload:
    """Quel che Spena capisce di un corpo di HC Webhook. Non solleva mai."""
    problems: list[str] = []
    steps_days = _steps(body.get("steps"), problems)
    exercises = _exercises(body.get("exercise"), problems)
    weights = _weights(body.get("weight"), problems)
    ignored = sorted(
        {str(key)[:MAX_KEY] for key in body if key not in ENVELOPE_KEYS | USED_KEYS}
    )
    return ParsedPayload(
        # solo `true`: la prova di HC Webhook lo scrive così, e una stringa «true» no
        is_test=body.get("test") is True,
        app_version=_text(body.get("app_version"), MAX_APP_VERSION),
        sent_at=parse_instant(body.get("timestamp")),
        steps_days=steps_days,
        exercises=exercises,
        weights=weights,
        ignored_keys=ignored[:MAX_IGNORED_KEYS],
        problems=problems,
    )


# I nomi a video degli allenamenti, per costante di Health Connect
# (androidx.health.connect.client.records.ExerciseSessionRecord, letta il 2026-10-13).
EXERCISE_LABELS: dict[int, str] = {
    0: "Allenamento",
    2: "Badminton",
    4: "Baseball",
    5: "Pallacanestro",
    8: "Bicicletta",
    9: "Cyclette",
    10: "Boot camp",
    11: "Pugilato",
    13: "Calistenia",
    14: "Cricket",
    16: "Ballo",
    25: "Ellittica",
    26: "Lezione di gruppo",
    27: "Scherma",
    28: "Football americano",
    29: "Football australiano",
    31: "Frisbee",
    32: "Golf",
    33: "Respirazione guidata",
    34: "Ginnastica",
    35: "Pallamano",
    36: "Allenamento a intervalli",
    37: "Escursionismo",
    38: "Hockey su ghiaccio",
    39: "Pattinaggio su ghiaccio",
    44: "Arti marziali",
    46: "Canoa e kayak",
    47: "Parapendio",
    48: "Pilates",
    50: "Racquetball",
    51: "Arrampicata",
    52: "Hockey su rotelle",
    53: "Canottaggio",
    54: "Vogatore",
    55: "Rugby",
    56: "Corsa",
    57: "Tapis roulant",
    58: "Vela",
    59: "Immersione",
    60: "Pattinaggio",
    61: "Sci",
    62: "Snowboard",
    63: "Ciaspole",
    64: "Calcio",
    65: "Softball",
    66: "Squash",
    68: "Scale",
    69: "Stepper",
    70: "Allenamento di forza",
    71: "Stretching",
    72: "Surf",
    73: "Nuoto in acque libere",
    74: "Nuoto in piscina",
    75: "Ping pong",
    76: "Tennis",
    78: "Pallavolo",
    79: "Camminata",
    80: "Pallanuoto",
    81: "Sollevamento pesi",
    82: "Sedia a rotelle",
    83: "Yoga",
}
DEFAULT_EXERCISE_LABEL = "Allenamento"


def exercise_label(exercise_type: int | None) -> str:
    if exercise_type is None:
        return DEFAULT_EXERCISE_LABEL
    return EXERCISE_LABELS.get(exercise_type, DEFAULT_EXERCISE_LABEL)


SOURCE_LABELS: dict[str, str] = {
    "com.sec.android.app.shealth": "Samsung Health",
    "com.google.android.apps.fitness": "Google Fit",
    "com.google.android.apps.healthdata": "Health Connect",
    "com.strava": "Strava",
    "com.fitbit.FitbitMobile": "Fitbit",
}
UNKNOWN_SOURCE_LABEL = "origine non indicata"


def source_label(source: str) -> str:
    if not source:
        return UNKNOWN_SOURCE_LABEL
    return SOURCE_LABELS.get(source, source)


# I tipi di HC Webhook che Spena non usa, col loro nome per la riga «Arrivati e non usati».
HC_TYPE_LABELS: dict[str, str] = {
    "sleep": "sonno",
    "heart_rate": "frequenza cardiaca",
    "heart_rate_variability": "variabilità del battito",
    "distance": "distanza",
    "active_calories": "calorie attive",
    "total_calories": "calorie totali",
    "height": "altezza",
    "blood_pressure": "pressione",
    "blood_glucose": "glicemia",
    "oxygen_saturation": "ossigenazione",
    "body_temperature": "temperatura corporea",
    "skin_temperature": "temperatura della pelle",
    "respiratory_rate": "frequenza respiratoria",
    "resting_heart_rate": "battito a riposo",
    "hydration": "idratazione",
    "nutrition": "alimentazione",
    "basal_metabolic_rate": "metabolismo basale",
    "body_fat": "massa grassa",
    "lean_body_mass": "massa magra",
    "body_water_mass": "acqua corporea",
    "vo2_max": "VO₂ max",
    "bone_mass": "massa ossea",
    "menstruation_flow": "flusso mestruale",
    "menstruation_period": "ciclo mestruale",
    "intermenstrual_bleeding": "perdite intermestruali",
    "ovulation_test": "test di ovulazione",
    "cervical_mucus": "muco cervicale",
    "sexual_activity": "attività sessuale",
    "basal_body_temperature": "temperatura basale",
}


def hc_type_label(key: str) -> str:
    return HC_TYPE_LABELS.get(key, key)
```

- [ ] **Step 4: Passano**

Run: il comando di pytest con `tests/domain/test_activity.py`
Expected: PASS, 52 test.

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/activity.py backend/tests/domain/test_activity.py
git commit -m "H2: il dominio — il corpo di HC Webhook letto voce per voce, un totale dei passi al giorno, i nomi"
```

---

### Task 3: La chiave e il webhook `POST /api/v1/activity/hc-webhook`

**Files:**
- Create: `backend/app/core/webhook_token.py`, `backend/tests/test_webhook_token.py`
- Create: `backend/app/repositories/activity.py`, `backend/app/services/activity.py`, `backend/app/schemas/activity.py`, `backend/app/api/activity.py`
- Modify: `backend/app/main.py`, `frontend/nginx.conf`
- Test: `backend/tests/api/test_activity_webhook.py`, `backend/tests/test_nginx_webhook.py` (nuovi)

**Interfaces:**
- Consumes: dal Task 1 i modelli; dal Task 2 `parse_payload`, `ParsedPayload`, `StepsDay`, `Exercise`, `Weight`, `merge_steps_day`, `TOKEN_HEADER`, `WEBHOOK_MAX_BYTES`, `TOO_BIG`, `NOT_JSON`, `NOT_OBJECT`; `get_session` (`app.core.db`).
- Produces:
  - in `app.core.webhook_token`: `TOKEN_LENGTH = 43`; `new_token() -> str`; `token_hash(token: str) -> str` (SHA-256 esadecimale, 64 caratteri); `looks_like_token(candidate: str) -> bool`; `token_matches(candidate: str, stored_hash: str | None) -> bool`.
  - in `app.repositories.activity`: `SYNCS_KEPT = 200`; `lock_webhook(session)`; `get_token(session) -> ActivityToken | None`; `save_token(session, hashed: str, now: datetime) -> ActivityToken`; `upsert_steps_day(session, reading: StepsDay) -> None`; `upsert_exercise(session, exercise: Exercise) -> None`; `upsert_weight(session, weight: Weight) -> None`; `record_sync(session, *, status, received_at, body_bytes, app_version=None, sent_at=None, steps_days=0, exercises=0, weights=0, ignored_keys=(), problems=()) -> None`; `prune_syncs(session) -> None`.
  - in `app.services.activity`: `authenticate_webhook(session, candidate: str | None) -> ActivityToken | None`; `receive_payload(session, parsed: ParsedPayload, body_bytes: int, now: datetime) -> dict[str, object]`; `reject_payload(session, problem: str, body_bytes: int, now: datetime) -> None`. Nessuno dei tre fa commit: lo fa la rotta.
  - in `app.api.activity`: `webhook_router` con `POST /api/v1/activity/hc-webhook`, fuori dalla sessione; `router` (dietro la sessione, vuoto qui: le rotte le aggiunge il Task 4). La risposta `200` è `{"test": bool, "saved": {"steps_days": int, "exercises": int, "weights": int}, "ignored": [str], "problems": [str]}`; `413` e `400` sono `{"detail": <la frase>}`; `401` è vuoto.
  - `app.schemas.activity` nasce qui vuoto di modelli (solo la docstring), il Task 4 lo riempie.

- [ ] **Step 1: I test che falliscono**

Crea `backend/tests/test_webhook_token.py`:

```python
"""La chiave del webhook di H2: lunga, casuale, conservata solo come impronta.

256 bit casuali non si indovinano, quindi l'impronta è un SHA-256 semplice (un hash lento
serve alle password, che si indovinano). Il confronto è a tempo costante.
"""

import pytest

from app.core.webhook_token import (
    TOKEN_LENGTH,
    looks_like_token,
    new_token,
    token_hash,
    token_matches,
)


def test_una_chiave_nuova_e_lunga_casuale_e_ben_fatta():
    prima, seconda = new_token(), new_token()

    assert len(prima) == TOKEN_LENGTH == 43
    assert looks_like_token(prima)
    assert prima != seconda


@pytest.mark.parametrize(
    "candidata",
    ["", "a" * 42, "a" * 44, "a" * 42 + "!", "a" * 42 + " ", "à" * 43],
)
def test_cosa_non_ha_la_forma_di_una_chiave(candidata):
    assert not looks_like_token(candidata)


def test_la_chiave_giusta_passa():
    chiave = new_token()

    assert token_matches(chiave, token_hash(chiave))


def test_una_chiave_sbagliata_no():
    assert not token_matches(new_token(), token_hash(new_token()))


def test_senza_una_chiave_configurata_niente_passa():
    assert not token_matches(new_token(), None)


def test_si_conserva_solo_l_impronta():
    chiave = new_token()
    impronta = token_hash(chiave)

    assert len(impronta) == 64
    assert chiave not in impronta
    assert impronta == token_hash(chiave)
```

Crea `backend/tests/api/test_activity_webhook.py`:

```python
"""H2: il webhook di HC Webhook — la chiave, i limiti, e quel che si salva.

La rotta sta fuori dalla sessione: la apre solo la chiave in `X-Spena-Token`. Le chiavi qui
si scrivono nel database con `save_token`, come farà `POST /api/v1/activity/token` (Task 4).
I corpi seguono `docs/webhook.md` di HC Webhook (letto il 2026-10-13).
"""

import json
from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.core.webhook_token import new_token, token_hash
from app.db.models.activity import (
    ActivityExercise,
    ActivityStepsDay,
    ActivitySync,
    ActivityToken,
    ActivityWeight,
)
from app.domain.activity import NOT_JSON, NOT_OBJECT, STEPS_NOT_DAILY, TOO_BIG, WEBHOOK_MAX_BYTES
from app.repositories import activity as activity_repo
from app.repositories.activity import save_token

WEBHOOK = "/api/v1/activity/hc-webhook"
SAMSUNG = {
    "data_origin": "com.sec.android.app.shealth",
    "recording_method": "automatically_recorded",
}

CORPO = {
    "timestamp": "2026-10-12T12:00:00.500Z",
    "app_version": "2.4.0",
    "steps": [
        {"count": 4321, "start_time": "2026-10-11T22:00:00Z", "end_time": "2026-10-12T12:00:00.123Z"}
    ],
    "exercise": [
        {
            "type": "56",
            "start_time": "2026-10-12T06:00:00Z",
            "end_time": "2026-10-12T06:30:00Z",
            "duration_seconds": 1800,
            "distance_meters": 5200.0,
            "metadata": SAMSUNG,
        }
    ],
    "weight": [{"kilograms": 72.4, "time": "2026-10-12T05:30:00Z", "metadata": SAMSUNG}],
}


@pytest_asyncio.fixture
async def chiave(db_session) -> str:
    token = new_token()
    await save_token(db_session, token_hash(token), datetime(2026, 10, 12, 8, tzinfo=UTC))
    return token


async def conta(db_session, modello) -> int:
    return await db_session.scalar(select(func.count()).select_from(modello))


async def manda(client, chiave: str | None, corpo=CORPO):
    intestazioni = {} if chiave is None else {"X-Spena-Token": chiave}
    return await client.post(WEBHOOK, json=corpo, headers=intestazioni)


async def test_senza_chiave_401_vuoto_e_niente_scritto(client, chiave, db_session):
    risposta = await manda(client, None)

    assert (risposta.status_code, risposta.content) == (401, b"")
    assert await conta(db_session, ActivitySync) == 0
    assert await conta(db_session, ActivityStepsDay) == 0


@pytest.mark.parametrize("sbagliata", ["x" * 43, "corta", "inventata"])
async def test_una_chiave_sbagliata_e_lo_stesso_401(client, chiave, db_session, sbagliata):
    risposta = await manda(client, sbagliata)

    assert (risposta.status_code, risposta.content) == (401, b"")
    assert await conta(db_session, ActivitySync) == 0
    assert (await db_session.get(ActivityToken, 1)).last_used_at is None


async def test_senza_una_chiave_configurata_niente_passa(client, db_session):
    risposta = await manda(client, new_token())

    assert (risposta.status_code, risposta.content) == (401, b"")
    assert await conta(db_session, ActivitySync) == 0


async def test_la_sessione_dell_app_non_basta(logged_client, chiave):
    risposta = await manda(logged_client, None)

    assert risposta.status_code == 401


async def test_il_corpo_giusto_salva_passi_allenamenti_e_pesate(client, chiave, db_session):
    risposta = await manda(client, chiave)

    assert risposta.status_code == 200
    assert risposta.json() == {
        "test": False,
        "saved": {"steps_days": 1, "exercises": 1, "weights": 1},
        "ignored": [],
        "problems": [],
    }
    giorno = await db_session.get(ActivityStepsDay, date(2026, 10, 12))
    assert giorno.steps == 4321
    allenamento = await db_session.scalar(select(ActivityExercise))
    assert (
        allenamento.source,
        allenamento.exercise_type,
        allenamento.distance_m,
        allenamento.day,
    ) == ("com.sec.android.app.shealth", 56, 5200.0, date(2026, 10, 12))
    pesata = await db_session.scalar(select(ActivityWeight))
    assert (pesata.kilograms, pesata.day) == (72.4, date(2026, 10, 12))
    sync = await db_session.scalar(select(ActivitySync))
    assert (sync.status, sync.app_version, sync.steps_days, sync.exercises, sync.weights) == (
        "ok",
        "2.4.0",
        1,
        1,
        1,
    )
    assert sync.sent_at == datetime(2026, 10, 12, 12, 0, 0, 500000, tzinfo=UTC)
    assert sync.body_bytes > 0
    assert (await db_session.get(ActivityToken, 1)).last_used_at is not None


async def test_lo_stesso_corpo_due_volte_non_duplica_niente(client, chiave, db_session):
    for _ in range(2):
        assert (await manda(client, chiave)).status_code == 200

    assert await conta(db_session, ActivityStepsDay) == 1
    assert await conta(db_session, ActivityExercise) == 1
    assert await conta(db_session, ActivityWeight) == 1
    assert await conta(db_session, ActivitySync) == 2


async def test_il_totale_del_giorno_cresce_e_un_invio_vecchio_non_lo_abbassa(
    client, chiave, db_session
):
    def corpo(passi: int, fine: str) -> dict:
        return {"steps": [{"count": passi, "start_time": "2026-10-11T22:00:00Z", "end_time": fine}]}

    await manda(client, chiave, corpo(4321, "2026-10-12T12:00:00.123Z"))
    await manda(client, chiave, corpo(6500, "2026-10-12T15:00:00.456Z"))
    # un tentativo ripetuto dell'invio di prima arriva dopo: è un pezzo già contato
    await manda(client, chiave, corpo(4321, "2026-10-12T12:00:00.123Z"))

    giorno = await db_session.get(ActivityStepsDay, date(2026, 10, 12))
    await db_session.refresh(giorno)
    assert giorno.steps == 6500
    assert giorno.covered_to == datetime(2026, 10, 12, 15, 0, 0, 456000, tzinfo=UTC)


async def test_un_allenamento_rimandato_aggiorna_la_sua_riga(client, chiave, db_session):
    await manda(client, chiave)
    allungato = {
        "exercise": [
            {**CORPO["exercise"][0], "end_time": "2026-10-12T06:45:00Z", "title": "Giro lungo"}
        ]
    }

    await manda(client, chiave, allungato)

    righe = (await db_session.scalars(select(ActivityExercise))).all()
    assert len(righe) == 1
    await db_session.refresh(righe[0])
    assert (righe[0].ended_at, righe[0].title) == (
        datetime(2026, 10, 12, 6, 45, tzinfo=UTC),
        "Giro lungo",
    )


async def test_la_prova_di_hc_webhook_non_salva_niente(client, chiave, db_session):
    corpo = {**CORPO, "test": True, "heart_rate": [{"bpm": 70, "time": "2026-10-12T06:00:00Z"}]}

    risposta = await manda(client, chiave, corpo)

    assert risposta.status_code == 200
    assert risposta.json() == {
        "test": True,
        "saved": {"steps_days": 0, "exercises": 0, "weights": 0},
        "ignored": ["heart_rate"],
        "problems": [],
    }
    assert await conta(db_session, ActivityStepsDay) == 0
    assert await conta(db_session, ActivityExercise) == 0
    sync = await db_session.scalar(select(ActivitySync))
    assert (sync.status, sync.ignored_keys) == ("test", ["heart_rate"])


async def test_un_corpo_troppo_grosso_si_rifiuta_e_si_registra(client, chiave, db_session):
    grosso = json.dumps({**CORPO, "imbottitura": "x" * (WEBHOOK_MAX_BYTES + 1)})

    risposta = await client.post(
        WEBHOOK,
        content=grosso,
        headers={"X-Spena-Token": chiave, "Content-Type": "application/json"},
    )

    assert risposta.status_code == 413
    assert risposta.json() == {"detail": TOO_BIG}
    assert await conta(db_session, ActivityStepsDay) == 0
    sync = await db_session.scalar(select(ActivitySync))
    assert (sync.status, sync.problems) == ("rejected", [TOO_BIG])


async def test_anche_senza_lunghezza_dichiarata_il_corpo_si_ferma_al_limite(
    client, chiave, db_session
):
    async def a_pezzi():
        for _ in range(3):
            yield b"x" * (WEBHOOK_MAX_BYTES // 2)

    risposta = await client.post(WEBHOOK, content=a_pezzi(), headers={"X-Spena-Token": chiave})

    assert risposta.status_code == 413
    sync = await db_session.scalar(select(ActivitySync))
    assert sync.problems == [TOO_BIG]


@pytest.mark.parametrize(
    ("corpo", "problema"),
    [
        (b"non json", NOT_JSON),
        (b"\xff\xfe\x00", NOT_JSON),  # byte che non sono testo
        (b"[" * 100_000, NOT_JSON),  # annidato a fondo: in Python è un RecursionError
        (b"[1, 2]", NOT_OBJECT),
        (b'"una stringa"', NOT_OBJECT),
    ],
)
async def test_un_corpo_che_non_e_un_oggetto_json_e_400_registrato(
    client, chiave, db_session, corpo, problema
):
    risposta = await client.post(WEBHOOK, content=corpo, headers={"X-Spena-Token": chiave})

    assert risposta.status_code == 400
    assert risposta.json() == {"detail": problema}
    sync = await db_session.scalar(select(ActivitySync))
    assert (sync.status, sync.problems) == ("rejected", [problema])


async def test_voci_illeggibili_e_tipi_nuovi_non_fermano_il_resto(client, chiave, db_session):
    corpo = {
        **CORPO,
        "steps": [*CORPO["steps"], {"count": "tanti", "start_time": "x", "end_time": "y"}],
        "weight": "non un elenco",
        "tipo_del_futuro": [{"a": 1}],
    }

    risposta = await manda(client, chiave, corpo)

    assert risposta.status_code == 200
    corpo_risposta = risposta.json()
    assert corpo_risposta["saved"] == {"steps_days": 1, "exercises": 1, "weights": 0}
    assert corpo_risposta["ignored"] == ["tipo_del_futuro"]
    assert corpo_risposta["problems"] == [
        "Passi: 1 voce illeggibile, scartata.",
        "Pesate: non è un elenco, non letto.",
    ]
    sync = await db_session.scalar(select(ActivitySync))
    assert (sync.status, sync.ignored_keys, sync.problems) == (
        "ok",
        ["tipo_del_futuro"],
        corpo_risposta["problems"],
    )


async def test_i_passi_a_finestre_non_si_salvano_e_si_dice_perche(client, chiave, db_session):
    corpo = {
        "steps": [
            {"count": 120, "start_time": "2026-10-12T06:00:00Z", "end_time": "2026-10-12T06:15:00Z"}
        ]
    }

    risposta = await manda(client, chiave, corpo)

    assert risposta.json()["problems"] == [STEPS_NOT_DAILY]
    assert await conta(db_session, ActivityStepsDay) == 0


async def test_il_registro_tiene_solo_le_ultime_sincronizzazioni(
    client, chiave, db_session, monkeypatch
):
    monkeypatch.setattr(activity_repo, "SYNCS_KEPT", 3)

    for _ in range(5):
        assert (await manda(client, chiave, {"timestamp": "2026-10-12T12:00:00Z"})).status_code == 200

    assert await conta(db_session, ActivitySync) == 3
```

Crea `backend/tests/test_nginx_webhook.py`:

```python
"""Nginx lascia arrivare al backend i corpi del webhook di H2 oltre il limite del backend.

Il limite di default di Nginx è 1 MB, e un suo 413 non arriva mai al backend: HC Webhook
lo scriverebbe nel suo registro, e in «Attività» non si vedrebbe niente. Con 4 MB sulla
sola rotta del webhook il rifiuto oltre i 2 MB lo dà il backend, che lo registra e lo
mostra (spec H2 §3.1, 4). Un `location` tolto «per pulizia» lo riporterebbe muto.
"""

import re
from pathlib import Path

from app.domain.activity import WEBHOOK_MAX_BYTES

NGINX = Path(__file__).resolve().parents[2] / "frontend" / "nginx.conf"


def test_nginx_porta_al_backend_i_corpi_oltre_il_limite_del_webhook():
    blocco = re.search(
        r"location = /api/v1/activity/hc-webhook \{(?P<corpo>[^}]*)\}", NGINX.read_text()
    )
    assert blocco, "manca la location del webhook in frontend/nginx.conf"
    misura = re.search(r"client_max_body_size (\d+)m;", blocco["corpo"])
    assert misura, "la location del webhook non alza client_max_body_size"
    assert int(misura[1]) * 1024 * 1024 > WEBHOOK_MAX_BYTES
    assert "proxy_pass http://backend:8000;" in blocco["corpo"]
```

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/backend`): il comando di pytest con `tests/test_webhook_token.py tests/api/test_activity_webhook.py tests/test_nginx_webhook.py`
Expected: FAIL in raccolta — `ModuleNotFoundError: No module named 'app.core.webhook_token'` (e `app.repositories.activity`); il test di Nginx fallisce con «manca la location del webhook».

- [ ] **Step 3: La chiave**

Crea `backend/app/core/webhook_token.py`:

```python
"""La chiave del webhook di HC Webhook (H2): creata qui, conservata come impronta.

Non è la sessione dell'app: HC Webhook non ha il cookie, e una chiave sua si rigenera
senza toccare la password. 32 byte casuali (43 caratteri) non si indovinano: per questo
l'impronta è un SHA-256 semplice, e non un hash lento come quello della password, che una
persona sceglie e qualcuno può indovinare.
"""

import hashlib
import hmac
import secrets
import string

TOKEN_BYTES = 32
# `token_urlsafe(32)`: 32 byte in base64 per URL, senza `=`
TOKEN_LENGTH = 43
_ALPHABET = frozenset(string.ascii_letters + string.digits + "-_")
# Senza una chiave configurata si confronta lo stesso, con questa: il tempo della risposta
# non deve dire se una chiave c'è.
_NO_TOKEN_HASH = hashlib.sha256(b"spena: nessuna chiave configurata").hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def looks_like_token(candidate: str) -> bool:
    """La forma di una chiave: si controlla prima di toccare il database."""
    return len(candidate) == TOKEN_LENGTH and set(candidate) <= _ALPHABET


def token_matches(candidate: str, stored_hash: str | None) -> bool:
    """Il confronto a tempo costante fra le impronte (`hmac.compare_digest`)."""
    expected = stored_hash if stored_hash is not None else _NO_TOKEN_HASH
    same = hmac.compare_digest(token_hash(candidate), expected)
    return same and stored_hash is not None
```

- [ ] **Step 4: Il repository**

Crea `backend/app/repositories/activity.py`:

```python
"""Scrivere e rileggere l'attività da Health Connect (H2). Il commit resta di chi chiama."""

import uuid
from collections.abc import Sequence
from datetime import date, datetime

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.activity import (
    ActivityExercise,
    ActivityStepsDay,
    ActivitySync,
    ActivityToken,
    ActivityWeight,
)
from app.domain.activity import Exercise, StepsDay, Weight, merge_steps_day

# Le sincronizzazioni che restano nel registro: a una ogni 15 minuti sono due giorni,
# abbastanza per vedere quando le cose hanno smesso di arrivare.
SYNCS_KEPT = 200
# La chiave dell'advisory lock del webhook: un numero qualunque, purché solo suo.
WEBHOOK_LOCK_KEY = 180_018


async def lock_webhook(session: AsyncSession) -> None:
    """Un corpo alla volta, fino alla fine della transazione.

    Due invii che si sovrappongono (HC Webhook riprova dopo un timeout mentre il primo
    sta ancora scrivendo) leggerebbero lo stesso totale del giorno e l'ultimo vincerebbe
    senza averlo confrontato con l'altro.
    """
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": WEBHOOK_LOCK_KEY})


async def get_token(session: AsyncSession) -> ActivityToken | None:
    return await session.get(ActivityToken, 1)


async def save_token(session: AsyncSession, hashed: str, now: datetime) -> ActivityToken:
    """Crea la chiave, o la sostituisce: la vecchia smette di valere subito."""
    row = await session.get(ActivityToken, 1)
    if row is None:
        row = ActivityToken(id=1, token_hash=hashed, created_at=now, last_used_at=None)
        session.add(row)
    else:
        row.token_hash = hashed
        row.created_at = now
        row.last_used_at = None
    await session.flush()
    return row


async def upsert_steps_day(session: AsyncSession, reading: StepsDay) -> None:
    row = await session.get(ActivityStepsDay, reading.day)
    if row is None:
        session.add(
            ActivityStepsDay(
                day=reading.day,
                steps=reading.steps,
                covered_from=reading.covered_from,
                covered_to=reading.covered_to,
            )
        )
        return
    stored = StepsDay(
        day=row.day, steps=row.steps, covered_from=row.covered_from, covered_to=row.covered_to
    )
    merged = merge_steps_day(stored, reading)
    row.steps = merged.steps
    row.covered_from = merged.covered_from
    row.covered_to = merged.covered_to


async def upsert_exercise(session: AsyncSession, exercise: Exercise) -> None:
    values = {
        "source": exercise.source,
        "started_at": exercise.started_at,
        "ended_at": exercise.ended_at,
        "day": exercise.day,
        "exercise_type": exercise.exercise_type,
        "title": exercise.title,
        "distance_m": exercise.distance_m,
        "steps": exercise.steps,
    }
    statement = pg_insert(ActivityExercise).values(id=uuid.uuid4(), **values)
    await session.execute(
        statement.on_conflict_do_update(
            constraint="uq_activity_exercises_source_started_at",
            set_={
                "ended_at": statement.excluded.ended_at,
                "day": statement.excluded.day,
                "exercise_type": statement.excluded.exercise_type,
                "title": statement.excluded.title,
                "distance_m": statement.excluded.distance_m,
                "steps": statement.excluded.steps,
                "updated_at": func.now(),
            },
        )
    )


async def upsert_weight(session: AsyncSession, weight: Weight) -> None:
    statement = pg_insert(ActivityWeight).values(
        id=uuid.uuid4(),
        source=weight.source,
        measured_at=weight.measured_at,
        day=weight.day,
        kilograms=weight.kilograms,
    )
    await session.execute(
        statement.on_conflict_do_update(
            constraint="uq_activity_weights_source_measured_at",
            set_={"kilograms": statement.excluded.kilograms, "updated_at": func.now()},
        )
    )


async def record_sync(
    session: AsyncSession,
    *,
    status: str,
    received_at: datetime,
    body_bytes: int,
    app_version: str | None = None,
    sent_at: datetime | None = None,
    steps_days: int = 0,
    exercises: int = 0,
    weights: int = 0,
    ignored_keys: Sequence[str] = (),
    problems: Sequence[str] = (),
) -> None:
    session.add(
        ActivitySync(
            received_at=received_at,
            status=status,
            app_version=app_version,
            sent_at=sent_at,
            body_bytes=body_bytes,
            steps_days=steps_days,
            exercises=exercises,
            weights=weights,
            ignored_keys=list(ignored_keys),
            problems=list(problems),
        )
    )
    await session.flush()


async def prune_syncs(session: AsyncSession) -> None:
    """Tiene le ultime `SYNCS_KEPT` sincronizzazioni, toglie le altre."""
    keep = (
        select(ActivitySync.id)
        .order_by(ActivitySync.received_at.desc(), ActivitySync.id.desc())
        .limit(SYNCS_KEPT)
    )
    await session.execute(delete(ActivitySync).where(ActivitySync.id.not_in(keep)))


async def latest_sync(session: AsyncSession) -> ActivitySync | None:
    return await session.scalar(
        select(ActivitySync).order_by(ActivitySync.received_at.desc()).limit(1)
    )


async def steps_between(session: AsyncSession, first: date, last: date) -> dict[date, int]:
    rows = await session.execute(
        select(ActivityStepsDay.day, ActivityStepsDay.steps).where(
            ActivityStepsDay.day >= first, ActivityStepsDay.day <= last
        )
    )
    return {day: steps for day, steps in rows.all()}


async def exercises_since(
    session: AsyncSession, first: date, limit: int
) -> list[ActivityExercise]:
    rows = await session.scalars(
        select(ActivityExercise)
        .where(ActivityExercise.day >= first)
        .order_by(ActivityExercise.started_at.desc(), ActivityExercise.source)
        .limit(limit)
    )
    return list(rows)


async def latest_weights(session: AsyncSession, limit: int) -> list[ActivityWeight]:
    rows = await session.scalars(
        select(ActivityWeight)
        .order_by(ActivityWeight.measured_at.desc(), ActivityWeight.source)
        .limit(limit)
    )
    return list(rows)
```

`SYNCS_KEPT` si legge dentro `prune_syncs` al momento della chiamata: il test lo abbassa con `monkeypatch` sul modulo.

- [ ] **Step 5: Il servizio, lo schema, la rotta**

Crea `backend/app/services/activity.py`:

```python
"""L'attività da Health Connect (H2): ricevere quel che manda HC Webhook, e mostrarlo.

Nessuna funzione qui fa commit: lo fa la rotta, una volta per richiesta, così il registro
della sincronizzazione e i dati che racconta entrano insieme o per niente.
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.webhook_token import looks_like_token, token_matches
from app.db.models.activity import ActivityToken
from app.domain.activity import ParsedPayload
from app.repositories.activity import (
    get_token,
    lock_webhook,
    prune_syncs,
    record_sync,
    upsert_exercise,
    upsert_steps_day,
    upsert_weight,
)


async def authenticate_webhook(
    session: AsyncSession, candidate: str | None
) -> ActivityToken | None:
    """La riga della chiave se `candidate` è quella giusta, `None` altrimenti.

    Una forma sbagliata si rifiuta senza leggere il database; senza una chiave configurata
    il confronto si fa lo stesso (`token_matches`), così il tempo non dice se c'è.
    """
    if candidate is None or not looks_like_token(candidate):
        return None
    stored = await get_token(session)
    if not token_matches(candidate, stored.token_hash if stored else None):
        return None
    return stored


async def receive_payload(
    session: AsyncSession, parsed: ParsedPayload, body_bytes: int, now: datetime
) -> dict[str, object]:
    """Salva quel che `parse_payload` ha capito, registra la sincronizzazione, e risponde.

    La prova di HC Webhook («Testa Webhook», `"test": true`) porta dati inventati: non si
    salva niente, e i problemi non si contano (non sono quelli del telefono di Mattia).
    """
    await lock_webhook(session)
    if parsed.is_test:
        saved = {"steps_days": 0, "exercises": 0, "weights": 0}
        problems: list[str] = []
    else:
        for reading in parsed.steps_days:
            await upsert_steps_day(session, reading)
        for exercise in parsed.exercises:
            await upsert_exercise(session, exercise)
        for weight in parsed.weights:
            await upsert_weight(session, weight)
        saved = {
            "steps_days": len(parsed.steps_days),
            "exercises": len(parsed.exercises),
            "weights": len(parsed.weights),
        }
        problems = parsed.problems
    await record_sync(
        session,
        status="test" if parsed.is_test else "ok",
        received_at=now,
        body_bytes=body_bytes,
        app_version=parsed.app_version,
        sent_at=parsed.sent_at,
        ignored_keys=parsed.ignored_keys,
        problems=problems,
        **saved,
    )
    await prune_syncs(session)
    return {
        "test": parsed.is_test,
        "saved": saved,
        "ignored": parsed.ignored_keys,
        "problems": problems,
    }


async def reject_payload(
    session: AsyncSession, problem: str, body_bytes: int, now: datetime
) -> None:
    """Un corpo autenticato ma rifiutato: si registra, perché in «Attività» si veda."""
    await lock_webhook(session)
    await record_sync(
        session, status="rejected", received_at=now, body_bytes=body_bytes, problems=[problem]
    )
    await prune_syncs(session)
```

Crea `backend/app/schemas/activity.py` (il Task 4 ci aggiunge i modelli delle risposte):

```python
"""Le risposte di «Attività» (H2): `GET /api/v1/activity` e `POST /api/v1/activity/token`."""
```

Crea `backend/app/api/activity.py`:

```python
"""L'attività da Health Connect (H2).

Due router con lo stesso prefisso. `webhook_router` porta l'unica rotta dell'app fuori
dalla sessione che scrive: la apre la chiave in `X-Spena-Token`, perché HC Webhook non ha
il cookie. `router` porta quelle della schermata, dietro la sessione come tutte.
"""

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import require_session
from app.domain.activity import (
    NOT_JSON,
    NOT_OBJECT,
    TOKEN_HEADER,
    TOO_BIG,
    WEBHOOK_MAX_BYTES,
    parse_payload,
)
from app.services.activity import authenticate_webhook, receive_payload, reject_payload

router = APIRouter(
    prefix="/api/v1/activity", tags=["activity"], dependencies=[Depends(require_session)]
)
webhook_router = APIRouter(prefix="/api/v1/activity", tags=["activity"])


async def _read_capped(request: Request) -> bytes | None:
    """Il corpo, o `None` se supera `WEBHOOK_MAX_BYTES`.

    Letto a pezzi e fermato al limite: una lunghezza dichiarata si può non dichiarare
    (`Transfer-Encoding: chunked`), e leggere tutto per poi misurarlo vorrebbe dire tenere
    in memoria quel che si voleva rifiutare.
    """
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > WEBHOOK_MAX_BYTES:
        return None
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > WEBHOOK_MAX_BYTES:
            return None
    return bytes(body)


async def _rejected(
    session: AsyncSession, problem: str, body_bytes: int, now: datetime, code: int
) -> JSONResponse:
    await reject_payload(session, problem, body_bytes, now)
    await session.commit()
    return JSONResponse({"detail": problem}, status_code=code)


@webhook_router.post("/hc-webhook", include_in_schema=False)
async def hc_webhook(request: Request, session: AsyncSession = Depends(get_session)) -> Response:
    # Il rifiuto è silenzioso e uguale per tutti (spec H2 §3.1): niente corpo, niente
    # scritture, nessun indizio su cosa mancava. Prima della chiave non si legge il corpo.
    token = await authenticate_webhook(session, request.headers.get(TOKEN_HEADER))
    if token is None:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    now = datetime.now(UTC)
    token.last_used_at = now
    body = await _read_capped(request)
    if body is None:
        declared = request.headers.get("content-length", "")
        size = int(declared) if declared.isdigit() else WEBHOOK_MAX_BYTES + 1
        return await _rejected(
            session, TOO_BIG, min(size, 2**31 - 1), now, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        )
    try:
        data = json.loads(body)
    except (ValueError, RecursionError):
        # ValueError copre anche i byte che non sono UTF-8 e gli interi di migliaia di
        # cifre; RecursionError un JSON annidato a fondo. Nessuno dei due è un 500.
        return await _rejected(session, NOT_JSON, len(body), now, status.HTTP_400_BAD_REQUEST)
    if not isinstance(data, dict):
        return await _rejected(session, NOT_OBJECT, len(body), now, status.HTTP_400_BAD_REQUEST)

    result = await receive_payload(session, parse_payload(data), len(body), now)
    await session.commit()
    return JSONResponse(result)
```

In `backend/app/main.py`:

1. Subito sopra la riga `from app.api import auth, cooking, imports, ingredients, pantry, products, recipes, shopping` (leggila com'è sul ramo) aggiungi:
   ```python
   from app.api import activity
   ```
   Una riga a parte e non dentro quella esistente: H1 riscrive quella riga stanotte, e al merge due righe diverse si uniscono da sole.
2. Subito dopo `app.include_router(imports.router)` aggiungi:
   ```python
   # Il webhook di HC Webhook (H2) è fuori dalla sessione: lo apre la sua chiave, perché il
   # telefono non ha il cookie. È l'unica rotta che scrive senza sessione; le altre di
   # «Attività» stanno dietro la sessione come tutte.
   app.include_router(activity.webhook_router)
   app.include_router(activity.router)
   ```

In `frontend/nginx.conf`, subito **prima** del blocco `location /api/ {` aggiungi:

```nginx
  # Il webhook di HC Webhook (H2). Nginx tiene di suo 1 MB, e un suo 413 non arriva mai
  # al backend: HC Webhook lo scriverebbe nel suo registro, e in «Attività» non si vedrebbe
  # niente. Qui fino a 4 MB, così oltre i 2 MB il rifiuto lo dà il backend, che lo registra
  # e lo mostra. `=` vince su ogni altra location per questo solo percorso.
  location = /api/v1/activity/hc-webhook {
    client_max_body_size 4m;
    proxy_pass http://backend:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
  }

```

- [ ] **Step 6: Passano**

Run: il comando di pytest con `tests/test_webhook_token.py tests/api/test_activity_webhook.py tests/test_nginx_webhook.py`
Expected: PASS — 11 della chiave, 21 del webhook, 1 di Nginx.

Se `pg_advisory_xact_lock` desse un errore dentro la transazione di prova, scrivilo nel report e segna il task `bloccato` con l'errore esatto: non togliere il lock.

- [ ] **Step 7: Tutta la suite**

Run: il comando di pytest, senza percorsi
Expected: PASS, `N_pytest` + 86 (1 del Task 1, 52 del Task 2, 33 di questo).

- [ ] **Step 8: Commit**

```bash
git add backend/app/core/webhook_token.py backend/app/repositories/activity.py \
  backend/app/services/activity.py backend/app/schemas/activity.py backend/app/api/activity.py \
  backend/app/main.py frontend/nginx.conf backend/tests/test_webhook_token.py \
  backend/tests/api/test_activity_webhook.py backend/tests/test_nginx_webhook.py
git commit -m "H2: il webhook di HC Webhook — la chiave a tempo costante, 2 MB a pezzi, mai un 500, un corpo alla volta"
```

---

### Task 4: «Attività» dal server — `GET /api/v1/activity` e `POST /api/v1/activity/token`

**Files:**
- Modify: `backend/app/services/activity.py` (aggiunte in fondo), `backend/app/schemas/activity.py`, `backend/app/api/activity.py`
- Test: `backend/tests/api/test_activity.py` (nuovo)

**Interfaces:**
- Consumes: dal Task 2 `rome_day`, `rome_clock`, `exercise_label`, `source_label`, `hc_type_label`, `TOKEN_HEADER`; dal Task 3 il repository, `new_token`, `token_hash`; `today_in_pantry` (`app.domain.rules`).
- Produces:
  - in `app.schemas.activity`: `SyncOut` (`day: date`, `time: str`, `status: Literal["ok", "test", "rejected"]`, `stale: bool`, `steps_days: int`, `exercises: int`, `weights: int`, `ignored: list[str]` — i nomi a video —, `problems: list[str]`); `StepsDayOut` (`day`, `steps: int | None`); `ExerciseOut` (`day`, `time`, `label`, `title: str | None`, `minutes: int`, `distance_km: float | None`, `source` — il nome a video); `WeightOut` (`day`, `time`, `kilograms` a un decimale); `ConnectionOut` (`has_token`, `created_day`, `created_time`, `last_used_day`, `last_used_time`, tutti annullabili tranne il primo); `ActivityOut` (`today`, `last_sync: SyncOut | None`, `steps_days`, `exercises`, `weights`, `connection`); `TokenOut` (`token`, `header`).
  - in `app.services.activity`: `SUMMARY_DAYS = 7`, `EXERCISES_SHOWN = 20`, `WEIGHTS_SHOWN = 5`, `STALE_AFTER = timedelta(hours=24)`; `activity_summary(session, now: datetime) -> ActivityOut`; `regenerate_token(session, now: datetime) -> str`.
  - le rotte `GET /api/v1/activity` → `ActivityOut` e `POST /api/v1/activity/token` → `201` `TokenOut`, dietro la sessione. I Task 5–7 le chiamano.

- [ ] **Step 1: I test che falliscono**

Crea `backend/tests/api/test_activity.py`:

```python
"""H2: «Attività» — cosa è arrivato da Health Connect, e la chiave del webhook.

Il riepilogo si prova sul servizio con «adesso» scritto a mano (il 13 ottobre 2026 alle
12:00 UTC, le 14:00 a Roma); le rotte con l'orologio vero, dove il risultato non dipende
da che ora è.
"""

from datetime import UTC, date, datetime, time, timedelta

import pytest

from app.db.models.activity import ActivityExercise, ActivityStepsDay, ActivityWeight
from app.domain.activity import rome_day
from app.domain.rules import PANTRY_TZ, today_in_pantry
from app.repositories.activity import record_sync
from app.services.activity import activity_summary

ADESSO = datetime(2026, 10, 13, 12, tzinfo=UTC)
OGGI = date(2026, 10, 13)
SAMSUNG = "com.sec.android.app.shealth"
WEBHOOK = "/api/v1/activity/hc-webhook"


def utc(*parti: int) -> datetime:
    return datetime(*parti, tzinfo=UTC)


def passi_del_giorno(giorno: date, passi: int) -> ActivityStepsDay:
    inizio = datetime.combine(giorno, time.min, tzinfo=PANTRY_TZ)
    return ActivityStepsDay(
        day=giorno, steps=passi, covered_from=inizio, covered_to=inizio + timedelta(hours=10)
    )


def allenamento(inizio: datetime, minuti: int, tipo: int | None = 56, **altro) -> ActivityExercise:
    return ActivityExercise(
        source=SAMSUNG,
        started_at=inizio,
        ended_at=inizio + timedelta(minutes=minuti),
        day=rome_day(inizio),
        exercise_type=tipo,
        **altro,
    )


def pesata(istante: datetime, chili: float) -> ActivityWeight:
    return ActivityWeight(source=SAMSUNG, measured_at=istante, day=rome_day(istante), kilograms=chili)


async def test_le_rotte_della_schermata_vogliono_la_sessione(client):
    assert (await client.get("/api/v1/activity")).status_code == 401
    assert (await client.post("/api/v1/activity/token")).status_code == 401


async def test_mai_sincronizzato(db_session):
    riepilogo = await activity_summary(db_session, ADESSO)

    assert riepilogo.today == OGGI
    assert riepilogo.last_sync is None
    assert [giorno.day for giorno in riepilogo.steps_days] == [
        OGGI - timedelta(days=giorni) for giorni in range(7)
    ]
    assert all(giorno.steps is None for giorno in riepilogo.steps_days)
    assert (riepilogo.exercises, riepilogo.weights) == ([], [])
    assert riepilogo.connection.has_token is False
    assert riepilogo.connection.created_day is None


async def test_i_passi_degli_ultimi_sette_giorni_oggi_per_primo(db_session):
    db_session.add_all(
        [
            passi_del_giorno(OGGI, 4321),
            passi_del_giorno(OGGI - timedelta(days=2), 9876),
            # otto giorni fa: fuori
            passi_del_giorno(OGGI - timedelta(days=7), 5555),
        ]
    )
    await db_session.flush()

    riepilogo = await activity_summary(db_session, ADESSO)

    assert [giorno.steps for giorno in riepilogo.steps_days] == [
        4321, None, 9876, None, None, None, None
    ]


async def test_gli_allenamenti_degli_ultimi_sette_giorni_dal_piu_recente(db_session):
    db_session.add_all(
        [
            allenamento(utc(2026, 10, 10, 7), 45, tipo=None),
            allenamento(
                utc(2026, 10, 13, 16), 32, title="Giro del parco", distance_m=5100.0, steps=5400
            ),
            # nove giorni fa: fuori
            allenamento(utc(2026, 10, 4, 7), 30),
        ]
    )
    await db_session.flush()

    riepilogo = await activity_summary(db_session, ADESSO)

    assert [e.model_dump() for e in riepilogo.exercises] == [
        {
            "day": OGGI,
            "time": "18:00",
            "label": "Corsa",
            "title": "Giro del parco",
            "minutes": 32,
            "distance_km": 5.1,
            "source": "Samsung Health",
        },
        {
            "day": date(2026, 10, 10),
            "time": "09:00",
            "label": "Allenamento",
            "title": None,
            "minutes": 45,
            "distance_km": None,
            "source": "Samsung Health",
        },
    ]


async def test_le_ultime_cinque_pesate(db_session):
    db_session.add_all(
        [pesata(utc(2026, 10, giorno, 5, 30), 70 + giorno / 10) for giorno in range(1, 7)]
    )
    await db_session.flush()

    riepilogo = await activity_summary(db_session, ADESSO)

    assert [(p.day, p.time, p.kilograms) for p in riepilogo.weights] == [
        (date(2026, 10, 6), "07:30", 70.6),
        (date(2026, 10, 5), "07:30", 70.5),
        (date(2026, 10, 4), "07:30", 70.4),
        (date(2026, 10, 3), "07:30", 70.3),
        (date(2026, 10, 2), "07:30", 70.2),
    ]


@pytest.mark.parametrize(("ore_fa", "vecchia"), [(1, False), (25, True)])
async def test_l_ultima_sincronizzazione_coi_nomi_e_se_e_vecchia(db_session, ore_fa, vecchia):
    await record_sync(
        db_session,
        status="ok",
        received_at=ADESSO - timedelta(hours=ore_fa + 48),
        body_bytes=10,
    )
    await record_sync(
        db_session,
        status="ok",
        received_at=ADESSO - timedelta(hours=ore_fa),
        body_bytes=812,
        steps_days=1,
        exercises=2,
        weights=0,
        ignored_keys=["heart_rate", "tipo_del_futuro"],
        problems=["Pesate: 1 voce illeggibile, scartata."],
    )

    sync = (await activity_summary(db_session, ADESSO)).last_sync

    assert sync is not None
    assert (sync.day, sync.status, sync.stale) == (
        rome_day(ADESSO - timedelta(hours=ore_fa)),
        "ok",
        vecchia,
    )
    assert (sync.steps_days, sync.exercises, sync.weights) == (1, 2, 0)
    assert sync.ignored == ["frequenza cardiaca", "tipo_del_futuro"]
    assert sync.problems == ["Pesate: 1 voce illeggibile, scartata."]


async def test_la_chiave_si_crea_si_usa_e_si_rigenera(logged_client):
    creata = await logged_client.post("/api/v1/activity/token")
    assert creata.status_code == 201
    prima = creata.json()
    assert prima["header"] == "X-Spena-Token"
    assert len(prima["token"]) == 43

    collegamento = (await logged_client.get("/api/v1/activity")).json()["connection"]
    assert collegamento["has_token"] is True
    assert collegamento["created_day"] == today_in_pantry().isoformat()
    assert collegamento["last_used_day"] is None

    usata = await logged_client.post(WEBHOOK, json={}, headers={"X-Spena-Token": prima["token"]})
    assert usata.status_code == 200
    collegamento = (await logged_client.get("/api/v1/activity")).json()["connection"]
    assert collegamento["last_used_day"] == today_in_pantry().isoformat()

    seconda = (await logged_client.post("/api/v1/activity/token")).json()
    assert seconda["token"] != prima["token"]
    vecchia = await logged_client.post(WEBHOOK, json={}, headers={"X-Spena-Token": prima["token"]})
    assert vecchia.status_code == 401
    nuova = await logged_client.post(WEBHOOK, json={}, headers={"X-Spena-Token": seconda["token"]})
    assert nuova.status_code == 200


async def test_la_chiave_non_si_rilegge_dal_riepilogo(logged_client):
    chiave = (await logged_client.post("/api/v1/activity/token")).json()["token"]

    risposta = await logged_client.get("/api/v1/activity")

    assert chiave not in risposta.text


async def test_la_rotta_risponde_coi_giorni_di_roma(logged_client):
    corpo = (await logged_client.get("/api/v1/activity")).json()

    assert corpo["today"] == today_in_pantry().isoformat()
    assert len(corpo["steps_days"]) == 7
    assert corpo["last_sync"] is None
```

- [ ] **Step 2: Falliscono**

Run: il comando di pytest con `tests/api/test_activity.py`
Expected: FAIL in raccolta — `ImportError: cannot import name 'activity_summary' from 'app.services.activity'`.

- [ ] **Step 3: Lo schema**

Sostituisci `backend/app/schemas/activity.py` (nato vuoto nel Task 3) con:

```python
"""Le risposte di «Attività» (H2): `GET /api/v1/activity` e `POST /api/v1/activity/token`.

Tutto quel che è dominio arriva già deciso: i giorni e le ore di Roma, i nomi a video, se
la sincronizzazione è vecchia. Il frontend scrive «Oggi», i numeri all'italiana, e disegna.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel


class SyncOut(BaseModel):
    # il giorno e l'ora di Roma in cui è arrivata
    day: date
    time: str
    status: Literal["ok", "test", "rejected"]
    # più di 24 ore fa: in «Attività» compare l'avviso sulla batteria
    stale: bool
    steps_days: int
    exercises: int
    weights: int
    # i nomi a video dei tipi arrivati e non usati
    ignored: list[str]
    problems: list[str]


class StepsDayOut(BaseModel):
    day: date
    # `None`: nessun totale arrivato per quel giorno, che non è zero passi
    steps: int | None


class ExerciseOut(BaseModel):
    day: date
    time: str
    label: str
    title: str | None
    minutes: int
    distance_km: float | None
    # il nome a video dell'app che l'ha scritto
    source: str


class WeightOut(BaseModel):
    day: date
    time: str
    kilograms: float


class ConnectionOut(BaseModel):
    has_token: bool
    created_day: date | None
    created_time: str | None
    last_used_day: date | None
    last_used_time: str | None


class ActivityOut(BaseModel):
    today: date
    last_sync: SyncOut | None
    # gli ultimi 7 giorni di Roma, oggi per primo
    steps_days: list[StepsDayOut]
    # degli ultimi 7 giorni, dal più recente, al più 20
    exercises: list[ExerciseOut]
    # le ultime 5, dalla più recente
    weights: list[WeightOut]
    connection: ConnectionOut


class TokenOut(BaseModel):
    # si vede solo qui, una volta: il database ne tiene l'impronta
    token: str
    header: str
```

- [ ] **Step 4: Il servizio**

In `backend/app/services/activity.py`:

1. Sostituisci le importazioni in cima (dal `from datetime import datetime` fino alla chiusura di `from app.repositories.activity import (…)`) con:
   ```python
   from datetime import date, datetime, timedelta

   from sqlalchemy.ext.asyncio import AsyncSession

   from app.core.webhook_token import looks_like_token, new_token, token_hash, token_matches
   from app.db.models.activity import (
       ActivityExercise,
       ActivitySync,
       ActivityToken,
       ActivityWeight,
   )
   from app.domain.activity import (
       ParsedPayload,
       exercise_label,
       hc_type_label,
       rome_clock,
       rome_day,
       source_label,
   )
   from app.domain.rules import today_in_pantry
   from app.repositories.activity import (
       exercises_since,
       get_token,
       latest_sync,
       latest_weights,
       lock_webhook,
       prune_syncs,
       record_sync,
       save_token,
       steps_between,
       upsert_exercise,
       upsert_steps_day,
       upsert_weight,
   )
   from app.schemas.activity import (
       ActivityOut,
       ConnectionOut,
       ExerciseOut,
       StepsDayOut,
       SyncOut,
       WeightOut,
   )
   ```
2. In fondo al file, dopo `reject_payload`, aggiungi:
   ```python
   SUMMARY_DAYS = 7
   EXERCISES_SHOWN = 20
   WEIGHTS_SHOWN = 5
   # Oltre, «Attività» avvisa: con l'intervallo di HC Webhook a 15 minuti o un'ora, un
   # giorno intero senza niente vuol dire che Android lo sta fermando.
   STALE_AFTER = timedelta(hours=24)


   def _moment(instant: datetime) -> tuple[date, str]:
       return rome_day(instant), rome_clock(instant)


   def _sync_out(sync: ActivitySync, now: datetime) -> SyncOut:
       day, clock = _moment(sync.received_at)
       return SyncOut(
           day=day,
           time=clock,
           status=sync.status,
           stale=now - sync.received_at > STALE_AFTER,
           steps_days=sync.steps_days,
           exercises=sync.exercises,
           weights=sync.weights,
           ignored=[hc_type_label(key) for key in sync.ignored_keys],
           problems=list(sync.problems),
       )


   def _exercise_out(exercise: ActivityExercise) -> ExerciseOut:
       seconds = (exercise.ended_at - exercise.started_at).total_seconds()
       return ExerciseOut(
           day=exercise.day,
           time=rome_clock(exercise.started_at),
           label=exercise_label(exercise.exercise_type),
           title=exercise.title,
           minutes=round(seconds / 60),
           # zero metri è «nessuna distanza», non «0,0 km»
           distance_km=round(exercise.distance_m / 1000, 1) if exercise.distance_m else None,
           source=source_label(exercise.source),
       )


   def _weight_out(weight: ActivityWeight) -> WeightOut:
       day, clock = _moment(weight.measured_at)
       return WeightOut(day=day, time=clock, kilograms=round(weight.kilograms, 1))


   def _connection_out(token: ActivityToken | None) -> ConnectionOut:
       if token is None:
           return ConnectionOut(
               has_token=False,
               created_day=None,
               created_time=None,
               last_used_day=None,
               last_used_time=None,
           )
       created_day, created_time = _moment(token.created_at)
       used = _moment(token.last_used_at) if token.last_used_at else (None, None)
       return ConnectionOut(
           has_token=True,
           created_day=created_day,
           created_time=created_time,
           last_used_day=used[0],
           last_used_time=used[1],
       )


   async def activity_summary(session: AsyncSession, now: datetime) -> ActivityOut:
       """Quel che mostra «Attività»: tutto in giorni e ore di Roma, coi nomi a video."""
       today = today_in_pantry(now)
       first = today - timedelta(days=SUMMARY_DAYS - 1)
       steps = await steps_between(session, first, today)
       sync = await latest_sync(session)
       return ActivityOut(
           today=today,
           last_sync=_sync_out(sync, now) if sync is not None else None,
           steps_days=[
               StepsDayOut(day=day, steps=steps.get(day))
               for day in (today - timedelta(days=back) for back in range(SUMMARY_DAYS))
           ],
           exercises=[
               _exercise_out(exercise)
               for exercise in await exercises_since(session, first, EXERCISES_SHOWN)
           ],
           weights=[_weight_out(weight) for weight in await latest_weights(session, WEIGHTS_SHOWN)],
           connection=_connection_out(await get_token(session)),
       )


   async def regenerate_token(session: AsyncSession, now: datetime) -> str:
       """Una chiave nuova: si torna a chi la chiede, e nel database va solo l'impronta."""
       token = new_token()
       await save_token(session, token_hash(token), now)
       return token
   ```

- [ ] **Step 5: Le rotte**

In `backend/app/api/activity.py`:

1. Sostituisci la riga `from app.services.activity import authenticate_webhook, receive_payload, reject_payload` con:
   ```python
   from app.schemas.activity import ActivityOut, TokenOut
   from app.services.activity import (
       activity_summary,
       authenticate_webhook,
       receive_payload,
       regenerate_token,
       reject_payload,
   )
   ```
2. In fondo al file aggiungi:
   ```python
   @router.get("", response_model=ActivityOut)
   async def get_activity(session: AsyncSession = Depends(get_session)) -> ActivityOut:
       return await activity_summary(session, datetime.now(UTC))


   @router.post("/token", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
   async def create_token(session: AsyncSession = Depends(get_session)) -> TokenOut:
       # crea o rigenera: la chiave di prima smette di valere con questo commit
       token = await regenerate_token(session, datetime.now(UTC))
       await session.commit()
       return TokenOut(token=token, header=TOKEN_HEADER)
   ```

- [ ] **Step 6: Passano**

Run: il comando di pytest con `tests/api/test_activity.py tests/api/test_activity_webhook.py`
Expected: PASS — 10 nuovi e i 21 del webhook.

- [ ] **Step 7: Tutta la suite**

Run: il comando di pytest, senza percorsi
Expected: PASS, `N_pytest` + 96.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/activity.py backend/app/schemas/activity.py backend/app/api/activity.py \
  backend/tests/api/test_activity.py
git commit -m "H2: GET /api/v1/activity e la chiave — 7 giorni di passi, allenamenti, pesate, l'ultima sincronizzazione"
```

---

### Task 5: Il frontend — i tipi, le chiamate, le parole

**Files:**
- Create: `frontend/src/features/activity/types.ts`, `frontend/src/features/activity/api.ts`, `frontend/src/features/activity/format.ts`
- Test: `frontend/src/features/activity/api.test.ts`, `frontend/src/features/activity/format.test.ts` (nuovi)

**Interfaces:**
- Consumes: le rotte del Task 4; `apiFetch` da `frontend/src/api/client.ts`.
- Produces:
  - `types.ts`: `SyncStatus = "ok" | "test" | "rejected"`; `ActivitySync { day; time; status; stale; steps_days; exercises; weights; ignored: string[]; problems: string[] }`; `StepsDay { day: string; steps: number | null }`; `ExerciseSession { day; time; label; title: string | null; minutes: number; distance_km: number | null; source: string }`; `WeighIn { day; time; kilograms: number }`; `Connection { has_token: boolean; created_day: string | null; created_time: string | null; last_used_day: string | null; last_used_time: string | null }`; `Activity { today: string; last_sync: ActivitySync | null; steps_days: StepsDay[]; exercises: ExerciseSession[]; weights: WeighIn[]; connection: Connection }`; `NewToken { token: string; header: string }`.
  - `api.ts`: `WEBHOOK_PATH = "/api/v1/activity/hc-webhook"`; `fetchActivity(): Promise<Activity>`; `createToken(): Promise<NewToken>`; `webhookUrl(origin?: string): string`; `headersJson(token: NewToken): string`.
  - `format.ts`: `dayLabel(day, today)` («Oggi», «Ieri», «dom 11 ott»); `momentText(day, time, today)` («oggi alle 14:05», «12 ottobre alle 09:10»); `formatSteps(n)` («8.421»); `formatKg(kg)` («72,4 kg»); `exerciseLine(e)`; `syncText(sync, today)`; `connectionText(c, today)`; `ignoredText(labels)`. I Task 6 e 7 li usano.

- [ ] **Step 1: I test che falliscono**

Crea `frontend/src/features/activity/api.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { createToken, fetchActivity, headersJson, webhookUrl } from "./api";

function stubFetch() {
  const spy = vi.fn((_url: unknown, _init?: RequestInit) =>
    Promise.resolve(new Response(JSON.stringify({}), { status: 200 }))
  );
  vi.stubGlobal("fetch", spy);
  return spy;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("le chiamate di «Attività»", () => {
  it("fetchActivity legge il riepilogo", async () => {
    const spy = stubFetch();

    await fetchActivity();

    expect(String(spy.mock.calls[0][0])).toBe("/api/v1/activity");
  });

  it("createToken chiede una chiave nuova con un POST", async () => {
    const spy = stubFetch();

    await createToken();

    expect(String(spy.mock.calls[0][0])).toBe("/api/v1/activity/token");
    expect(spy.mock.calls[0][1]?.method).toBe("POST");
  });

  it("l'indirizzo del webhook è l'origine della pagina più il percorso", () => {
    expect(webhookUrl("https://spena.example")).toBe("https://spena.example/api/v1/activity/hc-webhook");
  });

  it("le intestazioni da incollare in HC Webhook sono un oggetto JSON", () => {
    expect(headersJson({ token: "abc", header: "X-Spena-Token" })).toBe('{"X-Spena-Token":"abc"}');
  });
});
```

Crea `frontend/src/features/activity/format.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import {
  connectionText,
  dayLabel,
  exerciseLine,
  formatKg,
  formatSteps,
  ignoredText,
  momentText,
  syncText,
} from "./format";
import type { ActivitySync, Connection, ExerciseSession } from "./types";

const OGGI = "2026-10-13";

describe("dayLabel", () => {
  it.each([
    ["2026-10-13", "Oggi"],
    ["2026-10-12", "Ieri"],
    ["2026-10-11", "dom 11 ott"],
    ["2026-09-30", "mer 30 set"],
  ])("%s è «%s»", (giorno, atteso) => {
    expect(dayLabel(giorno, OGGI)).toBe(atteso);
  });
});

describe("momentText", () => {
  it.each([
    ["2026-10-13", "14:05", "oggi alle 14:05"],
    ["2026-10-12", "23:50", "ieri alle 23:50"],
    ["2026-10-07", "09:10", "7 ottobre alle 09:10"],
  ])("%s %s è «%s»", (giorno, ora, atteso) => {
    expect(momentText(giorno, ora, OGGI)).toBe(atteso);
  });
});

describe("formatSteps", () => {
  it.each([
    [0, "0"],
    [999, "999"],
    [8421, "8.421"],
    [12345, "12.345"],
    [1234567, "1.234.567"],
  ])("%s passi si scrivono «%s»", (passi, atteso) => {
    expect(formatSteps(passi)).toBe(atteso);
  });
});

describe("formatKg", () => {
  it.each([
    [72.4, "72,4 kg"],
    [80, "80,0 kg"],
  ])("%s → «%s»", (chili, atteso) => {
    expect(formatKg(chili)).toBe(atteso);
  });
});

describe("exerciseLine", () => {
  const corsa: ExerciseSession = {
    day: OGGI,
    time: "18:00",
    label: "Corsa",
    title: null,
    minutes: 32,
    distance_km: 5.1,
    source: "Samsung Health",
  };

  it.each([
    [corsa, "Corsa · 32 min · 5,1 km"],
    [{ ...corsa, title: "Giro del parco" }, "Corsa («Giro del parco») · 32 min · 5,1 km"],
    [{ ...corsa, label: "Allenamento di forza", distance_km: null, minutes: 45 }, "Allenamento di forza · 45 min"],
  ])("%# → «%s»", (allenamento, atteso) => {
    expect(exerciseLine(allenamento)).toBe(atteso);
  });
});

describe("syncText", () => {
  const sync: ActivitySync = {
    day: OGGI,
    time: "14:05",
    status: "ok",
    stale: false,
    steps_days: 1,
    exercises: 0,
    weights: 0,
    ignored: [],
    problems: [],
  };

  it.each([
    ["ok", "Ultima sincronizzazione: oggi alle 14:05."],
    ["test", "Ultima sincronizzazione: oggi alle 14:05, la prova di HC Webhook: arrivata, e non salva niente."],
    ["rejected", "Ultima sincronizzazione: oggi alle 14:05, rifiutata."],
  ] as const)("%s → «%s»", (status, atteso) => {
    expect(syncText({ ...sync, status }, OGGI)).toBe(atteso);
  });
});

describe("connectionText", () => {
  const chiave: Connection = {
    has_token: true,
    created_day: "2026-10-12",
    created_time: "21:00",
    last_used_day: OGGI,
    last_used_time: "14:05",
  };

  it("creata e usata", () => {
    expect(connectionText(chiave, OGGI)).toBe(
      "Chiave creata ieri alle 21:00. Usata l'ultima volta oggi alle 14:05."
    );
  });

  it("creata e mai usata", () => {
    expect(connectionText({ ...chiave, last_used_day: null, last_used_time: null }, OGGI)).toBe(
      "Chiave creata ieri alle 21:00. Non ancora usata."
    );
  });
});

describe("ignoredText", () => {
  it("elenca i tipi e dice dove toglierli", () => {
    expect(ignoredText(["frequenza cardiaca", "sonno"])).toBe(
      "Arrivati e non usati: frequenza cardiaca, sonno. Nel webhook di Spena, in HC Webhook, si possono togliere."
    );
  });
});
```

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/features/activity`
Expected: FAIL — i moduli `./api` e `./format` non esistono.

- [ ] **Step 3: I tipi, le chiamate, le parole**

Crea `frontend/src/features/activity/types.ts`:

```ts
// Le risposte di «Attività» (H2), come le scrive `backend/app/schemas/activity.py`. I giorni
// sono `YYYY-MM-DD` di Roma e le ore «18:05» di Roma: il fuso lo decide il server.

export type SyncStatus = "ok" | "test" | "rejected";

export interface ActivitySync {
  day: string;
  time: string;
  status: SyncStatus;
  /** più di 24 ore fa */
  stale: boolean;
  steps_days: number;
  exercises: number;
  weights: number;
  /** i nomi a video dei tipi arrivati e non usati */
  ignored: string[];
  problems: string[];
}

export interface StepsDay {
  day: string;
  /** `null`: nessun totale arrivato, che non vuol dire zero passi */
  steps: number | null;
}

export interface ExerciseSession {
  day: string;
  time: string;
  label: string;
  title: string | null;
  minutes: number;
  distance_km: number | null;
  /** il nome a video dell'app che l'ha scritto */
  source: string;
}

export interface WeighIn {
  day: string;
  time: string;
  kilograms: number;
}

export interface Connection {
  has_token: boolean;
  created_day: string | null;
  created_time: string | null;
  last_used_day: string | null;
  last_used_time: string | null;
}

export interface Activity {
  today: string;
  last_sync: ActivitySync | null;
  /** gli ultimi 7 giorni, oggi per primo */
  steps_days: StepsDay[];
  exercises: ExerciseSession[];
  weights: WeighIn[];
  connection: Connection;
}

/** La chiave appena creata: si vede solo qui, una volta. */
export interface NewToken {
  token: string;
  header: string;
}
```

Crea `frontend/src/features/activity/api.ts`:

```ts
import { apiFetch } from "../../api/client";
import type { Activity, NewToken } from "./types";

/** La rotta che HC Webhook chiama dal telefono (fuori dalla sessione, con la chiave). */
export const WEBHOOK_PATH = "/api/v1/activity/hc-webhook";

export function fetchActivity(): Promise<Activity> {
  return apiFetch<Activity>("/activity");
}

/** Crea la chiave, o la rigenera: quella di prima smette di valere. */
export function createToken(): Promise<NewToken> {
  return apiFetch<NewToken>("/activity/token", { method: "POST" });
}

/** L'indirizzo da incollare in HC Webhook: il dominio da cui si sta guardando Spena, che è
 * quello su cui il server risponde. Nessuna configurazione da tenere allineata. */
export function webhookUrl(origin: string = window.location.origin): string {
  return `${origin}${WEBHOOK_PATH}`;
}

/** Le intestazioni per «Gestisci intestazioni» › «JSON» di HC Webhook: un incolla solo. */
export function headersJson(token: NewToken): string {
  return JSON.stringify({ [token.header]: token.token });
}
```

Crea `frontend/src/features/activity/format.ts`:

```ts
import type { ActivitySync, Connection, ExerciseSession } from "./types";

// I giorni arrivano già di Roma (`YYYY-MM-DD`): qui si scrivono e basta. In UTC, perché la
// data letta non scivoli al giorno prima nel fuso del telefono.
const WEEKDAY = new Intl.DateTimeFormat("it-IT", { weekday: "short", timeZone: "UTC" });
const MONTH_SHORT = new Intl.DateTimeFormat("it-IT", { month: "short", timeZone: "UTC" });
const MONTH_LONG = new Intl.DateTimeFormat("it-IT", { month: "long", timeZone: "UTC" });
const DAY_MS = 86_400_000;

function asDate(iso: string): Date {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day));
}

function daysBefore(day: string, today: string): number {
  return Math.round((asDate(today).getTime() - asDate(day).getTime()) / DAY_MS);
}

/** Il nome di un giorno in un elenco: «Oggi», «Ieri», «dom 11 ott». */
export function dayLabel(day: string, today: string): string {
  const before = daysBefore(day, today);
  if (before === 0) return "Oggi";
  if (before === 1) return "Ieri";
  const date = asDate(day);
  return `${WEEKDAY.format(date)} ${date.getUTCDate()} ${MONTH_SHORT.format(date)}`;
}

/** Un momento dentro una frase: «oggi alle 14:05», «ieri alle 23:50», «7 ottobre alle 09:10». */
export function momentText(day: string, time: string, today: string): string {
  const before = daysBefore(day, today);
  const date = asDate(day);
  const when =
    before === 0 ? "oggi" : before === 1 ? "ieri" : `${date.getUTCDate()} ${MONTH_LONG.format(date)}`;
  return `${when} alle ${time}`;
}

/** 8421 → «8.421». A mano e non con `Intl`: in italiano `Intl` non separa le migliaia sotto
 * le diecimila (misurato: «8421»), e in una colonna di passi «8421» sopra «12.345» non si
 * legge. */
export function formatSteps(steps: number): string {
  return String(steps).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

function decimal(value: number): string {
  return value.toFixed(1).replace(".", ",");
}

/** 72.4 → «72,4 kg». */
export function formatKg(kilograms: number): string {
  return `${decimal(kilograms)} kg`;
}

/** «Corsa · 32 min · 5,1 km», col titolo «Corsa («Giro del parco») · 32 min». */
export function exerciseLine(exercise: ExerciseSession): string {
  const name = exercise.title ? `${exercise.label} («${exercise.title}»)` : exercise.label;
  const parts = [name, `${exercise.minutes} min`];
  if (exercise.distance_km !== null) parts.push(`${decimal(exercise.distance_km)} km`);
  return parts.join(" · ");
}

/** La prima riga di «Attività». */
export function syncText(sync: ActivitySync, today: string): string {
  const moment = momentText(sync.day, sync.time, today);
  if (sync.status === "test") {
    return `Ultima sincronizzazione: ${moment}, la prova di HC Webhook: arrivata, e non salva niente.`;
  }
  if (sync.status === "rejected") return `Ultima sincronizzazione: ${moment}, rifiutata.`;
  return `Ultima sincronizzazione: ${moment}.`;
}

/** Lo stato della chiave, quando c'è. */
export function connectionText(connection: Connection, today: string): string {
  const created = `Chiave creata ${momentText(connection.created_day ?? today, connection.created_time ?? "", today)}.`;
  if (connection.last_used_day === null || connection.last_used_time === null) {
    return `${created} Non ancora usata.`;
  }
  return `${created} Usata l'ultima volta ${momentText(connection.last_used_day, connection.last_used_time, today)}.`;
}

/** I tipi arrivati che Spena non usa, e dove toglierli. */
export function ignoredText(labels: string[]): string {
  return `Arrivati e non usati: ${labels.join(", ")}. Nel webhook di Spena, in HC Webhook, si possono togliere.`;
}
```

- [ ] **Step 4: Passano**

Run: `npx vitest run src/features/activity`
Expected: PASS, 27 test (4 delle chiamate, 23 delle parole).

- [ ] **Step 5: Il type check**

Run: `npm run typecheck`
Expected: pulito.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/activity/types.ts frontend/src/features/activity/api.ts \
  frontend/src/features/activity/api.test.ts frontend/src/features/activity/format.ts \
  frontend/src/features/activity/format.test.ts
git commit -m "H2: il frontend di «Attività» — i tipi, le chiamate, i giorni e i numeri all'italiana"
```

---

### Task 6: «Collega HC Webhook» — il campo da copiare, la chiave, i dieci passi

**Files:**
- Modify: `frontend/src/components/ui/icons.ts`
- Create: `frontend/src/features/activity/CopyField.tsx`, `frontend/src/features/activity/ConnectScreen.tsx`
- Test: `frontend/src/features/activity/CopyField.test.tsx`, `frontend/src/features/activity/ConnectScreen.test.tsx` (nuovi)

**Interfaces:**
- Consumes: dal Task 5 `fetchActivity`, `createToken`, `webhookUrl`, `headersJson`, `connectionText`, i tipi; `Screen`, `Card`, `Button`, `Alert`, `ErrorState`, `SectionHeading` (`frontend/src/components/ui/`); `useNotice` (`frontend/src/components/ui/noticeContext.ts`).
- Produces: `CopyField({ label, value })`; `ConnectScreen()` su `/attivita/collega` (la rotta la aggiunge il Task 7). La chiave della query è `["activity"]`, la stessa di `ActivityScreen`.

- [ ] **Step 1: L'icona**

In `frontend/src/components/ui/icons.ts`, nel blocco `// ovunque`, dopo `IconEyeOff,` aggiungi:

```ts
  IconCopy,
```

(`@tabler/icons-react` la ha: `node_modules/@tabler/icons-react/dist/esm/icons/IconCopy.mjs`.)

- [ ] **Step 2: I test che falliscono**

Crea `frontend/src/features/activity/CopyField.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import { CopyField } from "./CopyField";

const INDIRIZZO = "https://spena.example/api/v1/activity/hc-webhook";

// Gli appunti del browser, finti. Il click diretto di user-event (`userEvent.click`, senza
// `setup()`) non installa i suoi: quel che c'è qui è quel che vede il componente.
function appunti(valore: unknown) {
  Object.defineProperty(window.navigator, "clipboard", { value: valore, configurable: true });
}

afterEach(() => {
  appunti(undefined);
});

function renderField() {
  return render(
    <NoticeProvider>
      <CopyField label="Indirizzo" value={INDIRIZZO} />
    </NoticeProvider>
  );
}

describe("CopyField", () => {
  it("mostra il testo in un campo di sola lettura, col suo nome", () => {
    renderField();

    const campo = screen.getByLabelText("Indirizzo");
    expect(campo).toHaveValue(INDIRIZZO);
    expect(campo).toHaveAttribute("readonly");
  });

  it("«Copia» scrive negli appunti e lo dice", async () => {
    const writeText = vi.fn(() => Promise.resolve());
    appunti({ writeText });
    renderField();

    await userEvent.click(screen.getByRole("button", { name: "Copia: Indirizzo" }));

    expect(writeText).toHaveBeenCalledWith(INDIRIZZO);
    expect(await screen.findByText("Copiato.")).toBeInTheDocument();
  });

  it("se il telefono non lascia copiare, seleziona il testo e dice come fare a mano", async () => {
    appunti({ writeText: () => Promise.reject(new Error("negato")) });
    renderField();

    await userEvent.click(screen.getByRole("button", { name: "Copia: Indirizzo" }));

    expect(
      await screen.findByText("Non riesco a copiare: tieni premuto sul testo e copialo a mano.")
    ).toBeInTheDocument();
    const campo = screen.getByLabelText<HTMLInputElement>("Indirizzo");
    expect(campo).toHaveFocus();
    expect([campo.selectionStart, campo.selectionEnd]).toEqual([0, INDIRIZZO.length]);
  });

  it("senza appunti del tutto (fuori da HTTPS) è lo stesso", async () => {
    appunti(undefined);
    renderField();

    await userEvent.click(screen.getByRole("button", { name: "Copia: Indirizzo" }));

    expect(
      await screen.findByText("Non riesco a copiare: tieni premuto sul testo e copialo a mano.")
    ).toBeInTheDocument();
  });
});
```

Crea `frontend/src/features/activity/ConnectScreen.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ConnectScreen } from "./ConnectScreen";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import type { Activity } from "./types";

const CHIAVE = "k".repeat(43);

const SENZA_CHIAVE: Activity = {
  today: "2026-10-13",
  last_sync: null,
  steps_days: [],
  exercises: [],
  weights: [],
  connection: {
    has_token: false,
    created_day: null,
    created_time: null,
    last_used_day: null,
    last_used_time: null,
  },
};

const CON_CHIAVE: Activity = {
  ...SENZA_CHIAVE,
  connection: {
    has_token: true,
    created_day: "2026-10-13",
    created_time: "14:00",
    last_used_day: "2026-10-13",
    last_used_time: "14:05",
  },
};

function stubRoutedFetch(route: (path: string, init?: RequestInit) => [unknown, number]) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = route(String(url), init);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function conChiaveNuova(attivita: Activity, statoChiave = 201) {
  return stubRoutedFetch((path, init) =>
    path === "/api/v1/activity/token" && init?.method === "POST"
      ? [{ token: CHIAVE, header: "X-Spena-Token" }, statoChiave]
      : [attivita, 200]
  );
}

// Il predicato vero di App.tsx, non un `retry: false` di comodo (prima lezione di
// CLAUDE.md); senza attesa fra un tentativo e l'altro.
function renderScreen() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: defaultQueryRetryPredicate, retryDelay: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ConnectScreen />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ConnectScreen", () => {
  it("senza chiave la spiega e la crea; la chiave e le intestazioni si vedono subito", async () => {
    const spy = conChiaveNuova(SENZA_CHIAVE);
    renderScreen();

    expect(
      await screen.findByText(
        "Spena accetta i dati solo da chi porta la sua chiave. Creala, poi incollala in HC Webhook come dicono i passi qui sotto."
      )
    ).toBeInTheDocument();
    expect(
      screen.getByText("Le intestazioni da incollare compaiono qui quando crei la chiave.")
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Crea la chiave" }));

    expect(
      await screen.findByText("Ecco la chiave. Si vede solo adesso: copiala in HC Webhook prima di uscire da qui.")
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Chiave")).toHaveValue(CHIAVE);
    expect(screen.getByLabelText("Intestazioni (JSON)")).toHaveValue(`{"X-Spena-Token":"${CHIAVE}"}`);
    expect(spy.mock.calls.some(([url, init]) => String(url) === "/api/v1/activity/token" && init?.method === "POST")).toBe(true);
  });

  it("l'indirizzo c'è sempre, con l'origine della pagina", async () => {
    conChiaveNuova(SENZA_CHIAVE);
    renderScreen();

    expect(screen.getByLabelText("Indirizzo")).toHaveValue(
      `${window.location.origin}/api/v1/activity/hc-webhook`
    );
    await screen.findByRole("button", { name: "Crea la chiave" });
  });

  it("con una chiave: quando è nata e quando è stata usata; rigenerarla chiede conferma", async () => {
    conChiaveNuova(CON_CHIAVE);
    renderScreen();

    expect(
      await screen.findByText("Chiave creata oggi alle 14:00. Usata l'ultima volta oggi alle 14:05.")
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Rigenera la chiave" }));
    expect(
      screen.getByText("La chiave di adesso smetterà di funzionare, e in HC Webhook andrà incollata quella nuova.")
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(screen.getByRole("button", { name: "Rigenera la chiave" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Rigenera la chiave" }));
    await userEvent.click(screen.getByRole("button", { name: "Rigenera" }));
    expect(await screen.findByLabelText("Chiave")).toHaveValue(CHIAVE);
  });

  it("la creazione che non riesce lo dice, e il pulsante resta", async () => {
    conChiaveNuova(SENZA_CHIAVE, 500);
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: "Crea la chiave" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Non sono riuscito a creare la chiave.");
    expect(screen.getByRole("button", { name: "Crea la chiave" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Chiave")).toBeNull();
  });

  it("lo stato della chiave che non si legge: lo dice, e «Riprova» richiede", async () => {
    const spy = stubRoutedFetch(() => [{ detail: "rotto" }, 500]);
    renderScreen();

    expect(await screen.findByRole("alert")).toHaveTextContent("Non sono riuscito a leggere la chiave.");
    const prima = spy.mock.calls.length;
    await userEvent.click(screen.getByRole("button", { name: "Riprova" }));
    await waitFor(() => expect(spy.mock.calls.length).toBeGreaterThan(prima));
  });

  it("i passi sono dieci, nell'ordine, e il ritorno porta ad «Attività»", async () => {
    conChiaveNuova(SENZA_CHIAVE);
    renderScreen();

    const passi = within(screen.getByRole("list", { name: "I passi in HC Webhook" })).getAllByRole("listitem");
    expect(passi).toHaveLength(10);
    expect(passi[0]).toHaveTextContent("In Samsung Health: Impostazioni › Health Connect.");
    expect(passi[3]).toHaveTextContent("Alla voce «Risoluzione passi» lascia «Giornaliero»");
    expect(passi[7]).toHaveTextContent("Tocca «Testa Webhook»");
    expect(screen.getByRole("link", { name: "Attività" })).toHaveAttribute("href", "/attivita");
    await screen.findByRole("button", { name: "Crea la chiave" });
  });
});
```

- [ ] **Step 3: Falliscono**

Run: `npx vitest run src/features/activity/CopyField.test.tsx src/features/activity/ConnectScreen.test.tsx`
Expected: FAIL — i moduli `./CopyField` e `./ConnectScreen` non esistono.

- [ ] **Step 4: Il campo da copiare**

Crea `frontend/src/features/activity/CopyField.tsx`:

```tsx
import { useId, useRef } from "react";
import { Button } from "../../components/ui/Button";
import { IconCopy } from "../../components/ui/icons";
import { useNotice } from "../../components/ui/noticeContext";

/** Un testo da portare in un'altra app (l'indirizzo, la chiave, le intestazioni di HC
 * Webhook): un campo di sola lettura e «Copia».
 *
 * Se gli appunti non ci sono (fuori da HTTPS) o il telefono rifiuta, il testo si seleziona
 * e l'avviso dice di copiarlo a mano tenendoci il dito sopra: mai un vicolo cieco. Niente
 * `document.execCommand("copy")`, deprecato. Il campo non ha `text-sm`: sotto i 16 px iOS
 * ingrandisce la pagina quando prende il fuoco. */
export function CopyField({ label, value }: { label: string; value: string }) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const notify = useNotice();

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      notify({ text: "Copiato." });
    } catch {
      input.current?.focus();
      input.current?.select();
      notify({ text: "Non riesco a copiare: tieni premuto sul testo e copialo a mano." });
    }
  }

  return (
    <div className="flex w-full flex-col gap-1">
      <label htmlFor={id} className="text-sm text-ink-soft">
        {label}
      </label>
      <div className="flex items-center gap-2">
        <input
          id={id}
          ref={input}
          readOnly
          value={value}
          spellCheck={false}
          autoCapitalize="none"
          autoCorrect="off"
          onFocus={(event) => event.currentTarget.select()}
          className="min-w-0 flex-1 font-mono"
        />
        <Button icon={IconCopy} accessibleName={`Copia: ${label}`} onClick={() => void copy()} className="shrink-0">
          Copia
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: La schermata del collegamento**

Crea `frontend/src/features/activity/ConnectScreen.tsx`:

```tsx
import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { ErrorState } from "../../components/ui/ErrorState";
import { Screen } from "../../components/ui/Screen";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { createToken, fetchActivity, headersJson, webhookUrl } from "./api";
import { CopyField } from "./CopyField";
import { connectionText } from "./format";
import type { NewToken } from "./types";

/** «Collega HC Webhook» (H2): la chiave del webhook e i passi da fare sul telefono.
 *
 * La chiave si vede una volta sola, appena creata, e vive solo nello stato di questa
 * schermata: uscendo si perde, e la si rigenera. Il server ne tiene l'impronta. Rigenerare
 * chiede una conferma, perché spegne quella che HC Webhook sta usando. */
export function ConnectScreen() {
  const queryClient = useQueryClient();
  const activity = useQuery({ queryKey: ["activity"], queryFn: fetchActivity });
  const [fresh, setFresh] = useState<NewToken | null>(null);
  const [confirming, setConfirming] = useState(false);
  const create = useMutation({
    mutationFn: createToken,
    onSuccess: (token) => {
      setFresh(token);
      setConfirming(false);
      void queryClient.invalidateQueries({ queryKey: ["activity"] });
    },
  });

  let key: ReactNode;
  if (fresh) {
    key = (
      <>
        <p className="text-sm">Ecco la chiave. Si vede solo adesso: copiala in HC Webhook prima di uscire da qui.</p>
        <CopyField label="Chiave" value={fresh.token} />
      </>
    );
  } else if (activity.isPending) {
    key = <p className="text-sm text-ink-soft">Carico…</p>;
  } else if (activity.isError) {
    key = (
      <ErrorState
        message="Non sono riuscito a leggere la chiave."
        onRetry={() => activity.refetch()}
        retrying={activity.isFetching}
      />
    );
  } else if (!activity.data.connection.has_token) {
    key = (
      <>
        <p className="text-sm">
          Spena accetta i dati solo da chi porta la sua chiave. Creala, poi incollala in HC Webhook come dicono i
          passi qui sotto.
        </p>
        <Button variant="primary" onClick={() => create.mutate()} busy={create.isPending}>
          Crea la chiave
        </Button>
      </>
    );
  } else if (!confirming) {
    key = (
      <>
        <p className="text-sm">{connectionText(activity.data.connection, activity.data.today)}</p>
        <p className="text-sm text-ink-soft">
          La chiave si vede solo quando la crei. Se non l'hai più, rigenerala: quella di prima smette di funzionare.
        </p>
        <Button onClick={() => setConfirming(true)}>Rigenera la chiave</Button>
      </>
    );
  } else {
    key = (
      <>
        <p className="text-sm">
          La chiave di adesso smetterà di funzionare, e in HC Webhook andrà incollata quella nuova.
        </p>
        <div className="flex gap-2">
          <Button variant="primary" onClick={() => create.mutate()} busy={create.isPending}>
            Rigenera
          </Button>
          <Button variant="ghost" onClick={() => setConfirming(false)}>
            Annulla
          </Button>
        </div>
      </>
    );
  }

  return (
    <Screen
      title="Collega HC Webhook"
      subtitle="Una volta sola, dal telefono con Samsung Health."
      back={{ to: "/attivita", label: "Attività" }}
    >
      <SectionHeading>La chiave</SectionHeading>
      <Card className="flex flex-col items-start gap-3">
        {key}
        {create.isError && <Alert>Non sono riuscito a creare la chiave.</Alert>}
      </Card>
      <SectionHeading>In HC Webhook</SectionHeading>
      <Card>
        <ol aria-label="I passi in HC Webhook" className="list-decimal space-y-3 pl-5 text-sm">
          <li>
            In Samsung Health: Impostazioni › Health Connect. Lascia scrivere a Samsung Health passi, esercizio e
            peso, e tieni attiva la sincronizzazione con Samsung Cloud.
          </li>
          <li>Installa HC Webhook (Health Connect to Webhook) da Google Play.</li>
          <li>
            Aprila e attiva Passi, Sessioni di esercizio e Peso fra i «Tipi di dati»; concedi i permessi di Health
            Connect, anche quello in background.
          </li>
          <li>
            Alla voce «Risoluzione passi» lascia «Giornaliero»: così Health Connect conta una volta sola i passi del
            telefono e dell'orologio.
          </li>
          {/* un `div` dentro il `li`, e non `flex` sul `li`: un `li` flessibile perde il
              suo numero */}
          <li>
            <div className="flex flex-col gap-2">
              <span>In «Webhook» aggiungi questo indirizzo:</span>
              <CopyField label="Indirizzo" value={webhookUrl()} />
            </div>
          </li>
          <li>
            <div className="flex flex-col gap-2">
              <span>Nel webhook, «Gestisci intestazioni» › «JSON»: incolla questo e tocca «Applica JSON».</span>
              {fresh ? (
                <CopyField label="Intestazioni (JSON)" value={headersJson(fresh)} />
              ) : (
                <span className="text-ink-soft">Le intestazioni da incollare compaiono qui quando crei la chiave.</span>
              )}
            </div>
          </li>
          <li>Sempre nel webhook, fra i «Tipi di dati» scegli solo Passi, Sessioni di esercizio e Peso.</li>
          <li>
            Tocca «Testa Webhook»: in «Attività», l'ultima sincronizzazione deve dire che è arrivata la prova.
          </li>
          <li>
            Intervallo: 15 minuti o più. E togli HC Webhook dall'ottimizzazione della batteria («Ottimizzazione
            batteria attiva» › «Risolvi ora»), o Android salta le sincronizzazioni.
          </li>
          <li>Per portare i giorni passati: «Sincronizzazione manuale» › «Ultimi 30 giorni».</li>
        </ol>
      </Card>
    </Screen>
  );
}
```

- [ ] **Step 6: Passano**

Run: `npx vitest run src/features/activity`
Expected: PASS — 27 del Task 5, 4 di `CopyField`, 6 di `ConnectScreen`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ui/icons.ts frontend/src/features/activity/CopyField.tsx \
  frontend/src/features/activity/CopyField.test.tsx frontend/src/features/activity/ConnectScreen.tsx \
  frontend/src/features/activity/ConnectScreen.test.tsx
git commit -m "H2: «Collega HC Webhook» — la chiave una volta sola, «Copia» col ripiego a mano, i dieci passi"
```

---

### Task 7: «Attività», le rotte e la voce del ☰

**Files:**
- Create: `frontend/src/features/activity/ActivityScreen.tsx`
- Test: `frontend/src/features/activity/ActivityScreen.test.tsx` (nuovo)
- Modify: `frontend/src/App.tsx`, `frontend/src/components/AppHeader.tsx`, `frontend/src/components/AppHeader.test.tsx`

**Interfaces:**
- Consumes: dal Task 5 `fetchActivity`, `dayLabel`, `formatSteps`, `formatKg`, `exerciseLine`, `syncText`, `ignoredText`, i tipi; dal Task 6 `ConnectScreen`; `Screen`, `Card`, `Alert`, `EmptyState`, `ErrorState`, `SectionHeading`, `buttonClasses`.
- Produces: `ActivityScreen()` su `/attivita`; `ConnectScreen` su `/attivita/collega`; la voce «Attività» in `INDEX` di `AppHeader.tsx`.

- [ ] **Step 1: I test che falliscono**

Crea `frontend/src/features/activity/ActivityScreen.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ActivityScreen } from "./ActivityScreen";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import type { Activity } from "./types";

const GIORNI = ["2026-10-13", "2026-10-12", "2026-10-11", "2026-10-10", "2026-10-09", "2026-10-08", "2026-10-07"];

const CON_DATI: Activity = {
  today: "2026-10-13",
  last_sync: {
    day: "2026-10-13",
    time: "14:05",
    status: "ok",
    stale: false,
    steps_days: 1,
    exercises: 1,
    weights: 1,
    ignored: [],
    problems: [],
  },
  steps_days: GIORNI.map((day, i) => ({ day, steps: i === 0 ? 8421 : i === 2 ? 12345 : null })),
  exercises: [
    {
      day: "2026-10-13",
      time: "18:00",
      label: "Corsa",
      title: "Giro del parco",
      minutes: 32,
      distance_km: 5.1,
      source: "Samsung Health",
    },
  ],
  weights: [{ day: "2026-10-13", time: "07:30", kilograms: 72.4 }],
  connection: {
    has_token: true,
    created_day: "2026-10-12",
    created_time: "21:00",
    last_used_day: "2026-10-13",
    last_used_time: "14:05",
  },
};

function stubFetch(body: unknown, status = 200) {
  const spy = vi.fn(() => Promise.resolve(new Response(JSON.stringify(body), { status })));
  vi.stubGlobal("fetch", spy);
  return spy;
}

function renderScreen() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: defaultQueryRetryPredicate, retryDelay: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ActivityScreen />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ActivityScreen", () => {
  it("mostra l'ultima sincronizzazione, i passi dei 7 giorni, gli allenamenti e le pesate", async () => {
    stubFetch(CON_DATI);
    renderScreen();

    expect(screen.getByRole("heading", { name: "Attività", level: 1 })).toBeInTheDocument();
    expect(await screen.findByText("Ultima sincronizzazione: oggi alle 14:05.")).toBeInTheDocument();

    const passi = within(screen.getByRole("list", { name: "Passi degli ultimi 7 giorni" })).getAllByRole("listitem");
    expect(passi).toHaveLength(7);
    expect(passi[0]).toHaveTextContent("Oggi8.421");
    expect(passi[1]).toHaveTextContent("Ierinessun dato");
    expect(passi[2]).toHaveTextContent("dom 11 ott12.345");

    const allenamenti = screen.getByRole("list", { name: "Allenamenti degli ultimi 7 giorni" });
    expect(within(allenamenti).getByText("Corsa («Giro del parco») · 32 min · 5,1 km")).toBeInTheDocument();
    expect(within(allenamenti).getByText("Oggi, 18:00 · Samsung Health")).toBeInTheDocument();

    const pesate = screen.getByRole("list", { name: "Ultime pesate" });
    expect(within(pesate).getByText("72,4 kg")).toBeInTheDocument();
    expect(within(pesate).getByText("Oggi, 07:30")).toBeInTheDocument();

    expect(screen.getByRole("link", { name: "Collegamento con HC Webhook" })).toHaveAttribute(
      "href",
      "/attivita/collega"
    );
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("mai sincronizzato: dice cosa manca e porta al collegamento", async () => {
    stubFetch({ ...CON_DATI, last_sync: null, exercises: [], weights: [] });
    renderScreen();

    expect(await screen.findByRole("heading", { name: "Nessun dato da Health Connect, per ora" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Collega HC Webhook" })).toHaveAttribute("href", "/attivita/collega");
    expect(screen.queryByRole("heading", { name: "Passi" })).toBeNull();
  });

  it("la prova di HC Webhook si riconosce", async () => {
    stubFetch({ ...CON_DATI, last_sync: { ...CON_DATI.last_sync!, status: "test" } });
    renderScreen();

    expect(
      await screen.findByText(
        "Ultima sincronizzazione: oggi alle 14:05, la prova di HC Webhook: arrivata, e non salva niente."
      )
    ).toBeInTheDocument();
  });

  it("un rifiuto vecchio: il perché, e l'avviso sulla batteria", async () => {
    stubFetch({
      ...CON_DATI,
      last_sync: {
        ...CON_DATI.last_sync!,
        day: "2026-10-11",
        time: "09:10",
        status: "rejected",
        stale: true,
        problems: ["Rifiutato: il corpo non è JSON."],
      },
    });
    renderScreen();

    expect(await screen.findByText("Ultima sincronizzazione: 11 ottobre alle 09:10, rifiutata.")).toBeInTheDocument();
    const avvisi = screen.getAllByRole("alert").map((avviso) => avviso.textContent);
    expect(avvisi).toEqual([
      "Da più di un giorno non arriva niente. Controlla che HC Webhook non sia limitato dall'ottimizzazione della batteria, e prova «Sincronizza ora».",
      "Rifiutato: il corpo non è JSON.",
    ]);
  });

  it("i tipi arrivati e non usati si nominano", async () => {
    stubFetch({ ...CON_DATI, last_sync: { ...CON_DATI.last_sync!, ignored: ["frequenza cardiaca", "sonno"] } });
    renderScreen();

    expect(
      await screen.findByText(
        "Arrivati e non usati: frequenza cardiaca, sonno. Nel webhook di Spena, in HC Webhook, si possono togliere."
      )
    ).toBeInTheDocument();
  });

  it("senza allenamenti né pesate lo dice", async () => {
    stubFetch({ ...CON_DATI, exercises: [], weights: [] });
    renderScreen();

    expect(await screen.findByText("Nessun allenamento negli ultimi 7 giorni.")).toBeInTheDocument();
    expect(screen.getByText("Nessuna pesata, per ora.")).toBeInTheDocument();
  });

  it("il server che non risponde: lo dice, e «Riprova» richiede", async () => {
    const spy = stubFetch({ detail: "rotto" }, 500);
    renderScreen();

    expect(await screen.findByRole("alert")).toHaveTextContent("Non sono riuscito a leggere l'attività.");
    const prima = spy.mock.calls.length;
    await userEvent.click(screen.getByRole("button", { name: "Riprova" }));
    await waitFor(() => expect(spy.mock.calls.length).toBeGreaterThan(prima));
  });
});
```

- [ ] **Step 2: Falliscono**

Run: `npx vitest run src/features/activity/ActivityScreen.test.tsx`
Expected: FAIL — il modulo `./ActivityScreen` non esiste.

- [ ] **Step 3: La schermata**

Crea `frontend/src/features/activity/ActivityScreen.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Alert } from "../../components/ui/Alert";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { Card } from "../../components/ui/Card";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorState } from "../../components/ui/ErrorState";
import { Screen } from "../../components/ui/Screen";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { fetchActivity } from "./api";
import { dayLabel, exerciseLine, formatKg, formatSteps, ignoredText, syncText } from "./format";
import type { Activity } from "./types";

const ROW = "flex min-h-11 items-center justify-between gap-3 border-b border-line px-3 py-2 last:border-b-0";
const STACKED_ROW = "flex flex-col gap-0.5 border-b border-line px-3 py-2 last:border-b-0";

/** «Attività» (H2): cosa è arrivato da Health Connect via HC Webhook.
 *
 * Il server decide tutto — i giorni e le ore di Roma, i nomi, se la sincronizzazione è
 * vecchia —; qui si scrive e si disegna. Senza tasto indietro: ci si arriva dal ☰, come
 * all'Anagrafica. Niente grafici: sette numeri si leggono meglio in fila. */
export function ActivityScreen() {
  const activity = useQuery({ queryKey: ["activity"], queryFn: fetchActivity });

  return (
    <Screen title="Attività" subtitle="Passi, allenamenti e peso da Health Connect.">
      {activity.isPending ? (
        <p className="px-1 text-sm text-ink-soft">Carico l'attività…</p>
      ) : activity.isError ? (
        <ErrorState
          message="Non sono riuscito a leggere l'attività."
          onRetry={() => activity.refetch()}
          retrying={activity.isFetching}
        />
      ) : (
        <Report activity={activity.data} />
      )}
    </Screen>
  );
}

function Report({ activity }: { activity: Activity }) {
  const sync = activity.last_sync;
  // mai arrivato niente: cosa manca, e la strada (mai un vicolo cieco)
  if (sync === null) {
    return (
      <EmptyState
        title="Nessun dato da Health Connect, per ora"
        body="Spena riceve passi, allenamenti e pesate da HC Webhook, un'app per Android che li legge da Health Connect, dove li scrive Samsung Health. Si collega una volta sola."
        action={
          <Link to="/attivita/collega" className={buttonClasses("primary")}>
            Collega HC Webhook
          </Link>
        }
      />
    );
  }

  return (
    <div className="flex flex-col">
      <Card className="flex flex-col gap-2">
        <p className="text-sm">{syncText(sync, activity.today)}</p>
        {sync.stale && (
          <Alert tone="degraded">
            Da più di un giorno non arriva niente. Controlla che HC Webhook non sia limitato dall'ottimizzazione della
            batteria, e prova «Sincronizza ora».
          </Alert>
        )}
        {sync.problems.map((problem, index) => (
          <Alert key={index} tone="degraded">
            {problem}
          </Alert>
        ))}
        {sync.ignored.length > 0 && <p className="text-sm text-ink-soft">{ignoredText(sync.ignored)}</p>}
      </Card>

      <SectionHeading>Passi</SectionHeading>
      <Card pad={false}>
        <ul aria-label="Passi degli ultimi 7 giorni">
          {activity.steps_days.map((entry) => (
            <li key={entry.day} className={ROW}>
              <span className="text-sm">{dayLabel(entry.day, activity.today)}</span>
              {entry.steps === null ? (
                <span className="text-sm text-ink-soft">nessun dato</span>
              ) : (
                <span className="font-semibold tabular-nums">{formatSteps(entry.steps)}</span>
              )}
            </li>
          ))}
        </ul>
      </Card>

      <SectionHeading>Allenamenti</SectionHeading>
      {activity.exercises.length === 0 ? (
        <Card>
          <p className="text-sm text-ink-soft">Nessun allenamento negli ultimi 7 giorni.</p>
        </Card>
      ) : (
        <Card pad={false}>
          <ul aria-label="Allenamenti degli ultimi 7 giorni">
            {activity.exercises.map((exercise, index) => (
              <li key={`${exercise.day}-${exercise.time}-${index}`} className={STACKED_ROW}>
                <p className="text-sm font-medium">{exerciseLine(exercise)}</p>
                <p className="text-xs text-ink-soft">
                  {`${dayLabel(exercise.day, activity.today)}, ${exercise.time} · ${exercise.source}`}
                </p>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <SectionHeading>Peso</SectionHeading>
      {activity.weights.length === 0 ? (
        <Card>
          <p className="text-sm text-ink-soft">Nessuna pesata, per ora.</p>
        </Card>
      ) : (
        <Card pad={false}>
          <ul aria-label="Ultime pesate">
            {activity.weights.map((weight, index) => (
              <li key={`${weight.day}-${weight.time}-${index}`} className={ROW}>
                <span className="font-semibold tabular-nums">{formatKg(weight.kilograms)}</span>
                <span className="text-sm text-ink-soft">{`${dayLabel(weight.day, activity.today)}, ${weight.time}`}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="pt-4">
        <Link to="/attivita/collega" className={buttonClasses("secondary")}>
          Collegamento con HC Webhook
        </Link>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Passano i test della schermata**

Run: `npx vitest run src/features/activity/ActivityScreen.test.tsx`
Expected: PASS, 7 test.

- [ ] **Step 5: Le rotte e la voce del ☰**

In `frontend/src/App.tsx` (leggilo com'è sul ramo):

1. Dopo la riga `import { StockingScreen } from "./features/stocking/StockingScreen";` aggiungi:
   ```tsx
   import { ActivityScreen } from "./features/activity/ActivityScreen";
   import { ConnectScreen } from "./features/activity/ConnectScreen";
   ```
2. Subito **prima** del commento `{/* in fondo: prende solo ciò che nessuna rotta sopra ha preso */}` aggiungi:
   ```tsx
   <Route path="/attivita" element={<ActivityScreen />} />
   <Route path="/attivita/collega" element={<ConnectScreen />} />
   ```

In `frontend/src/components/AppHeader.tsx`, sostituisci il commento e la costante `INDEX` (com'è su `master`):

```tsx
// L'indice completo (D3, T1): le sezioni che la barra in basso non porta. Pasti,
// Spese, Profilo e Connettori si aggiungeranno qui quando esisteranno.
const INDEX = [
  { to: "/sistema", label: "Sistema la spesa" },
  { to: "/ricette/importa", label: "Ingredienti da abbinare" },
  { to: "/anagrafica", label: "Anagrafica" },
];
```

con:

```tsx
// L'indice completo (D3, T1): le sezioni che la barra in basso non porta. «Attività»
// (H2) è il connettore di Samsung Health, via Health Connect e HC Webhook: in fondo.
// Pasti, Spese e Profilo si aggiungeranno qui quando esisteranno.
const INDEX = [
  { to: "/sistema", label: "Sistema la spesa" },
  { to: "/ricette/importa", label: "Ingredienti da abbinare" },
  { to: "/anagrafica", label: "Anagrafica" },
  { to: "/attivita", label: "Attività" },
];
```

In `frontend/src/components/AppHeader.test.tsx`:

1. Nel test «il ☰ apre un dialogo con l'indice, e ogni voce porta al suo posto», dopo l'asserzione su «Anagrafica», aggiungi:
   ```tsx
   expect(within(menu).getByRole("link", { name: "Attività" })).toHaveAttribute("href", "/attivita");
   ```
2. **Migrazione** — nel test «il fuoco resta dentro: dopo l'ultima voce si torna alla prima, e al contrario», l'ultima voce del ☰ non è più «Anagrafica»: la riga `const ultima = screen.getByRole("link", { name: "Anagrafica" });` diventa:
   ```tsx
   const ultima = screen.getByRole("link", { name: "Attività" });
   ```
   Nessun'altra riga di quel file cambia (gli altri test che nominano «Anagrafica» la usano come una voce qualsiasi, e lo resta).

- [ ] **Step 6: Tutta la suite del frontend**

Run: `npx vitest run && npm run typecheck && npm run lint && npm run build`
Expected: verdi; vitest a `N_vitest` + 44 in `N_file` + 5 file.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/activity/ActivityScreen.tsx frontend/src/features/activity/ActivityScreen.test.tsx \
  frontend/src/App.tsx frontend/src/components/AppHeader.tsx frontend/src/components/AppHeader.test.tsx
git commit -m "H2: «Attività» dal ☰ — l'ultima sincronizzazione, 7 giorni di passi, allenamenti, pesate, il collegamento"
```

---

### Task 8: Nel browser vero — il telefono lo fa la prova, attraverso Nginx

**Files:**
- Create: `frontend/e2e/attivita.spec.ts`
- Modify: `frontend/e2e/style.spec.ts` (`"/attivita"` e `"/attivita/collega"` in `SCHERMATE`; una prova in fondo al file)

Leggi `style.spec.ts` com'è sul ramo: da `master` nessun piano della notte l'ha cambiato su questo ramo. `testiIlleggibili`, `fermo` e `senzaScorrimentoLaterale` ci sono già (cercali per nome); il `test.beforeEach` in cima fa già l'accesso, quindi `page.request` porta la sessione.

**Interfaces:**
- Consumes: tutto quel che hanno fatto i Task 1–7, sull'app costruita e servita da Nginx col `nginx.conf` del ramo.
- Produces: nessun aiutante nel container. I corpi li scrive la prova; i dati restano nello stack, che `down -v` toglie. I valori sono diversi fra i due file (12.345 passi, una corsa, 72,4 kg in `attivita.spec.ts`; 6.789 passi, una camminata, 81,7 kg in `style.spec.ts`), così una prova non vede quelli dell'altra.

- [ ] **Step 1: Le prove della schermata e del webhook**

Crea `frontend/e2e/attivita.spec.ts`:

```ts
import { expect, test, type Page } from "@playwright/test";

/**
 * H2, «Attività» e il collegamento con HC Webhook, nel browser vero, a 375×812.
 *
 * Il telefono non c'è: quel che HC Webhook manderebbe lo manda la prova, con `page.request`
 * attraverso Nginx — lo stesso percorso del telefono, compresa la `location` del webhook in
 * `frontend/nginx.conf`. La chiave si crea dalla schermata, come la creerà Mattia, e si
 * legge dal suo campo. Nessuna rete verso fuori.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";
const WEBHOOK = "/api/v1/activity/hc-webhook";

/** Il giorno di Roma di `giorniFa` giorni fa, `YYYY-MM-DD`. */
function giornoDiRoma(giorniFa: number): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Rome" }).format(
    new Date(Date.now() - giorniFa * 86_400_000)
  );
}

/** Un corpo come quello di HC Webhook: i passi del giorno in forma «Giornaliero» (la fine
 * porta i millesimi), una corsa di Samsung Health, una pesata, e un tipo che Spena non usa.
 * Le ore sono a metà giornata in UTC: a Roma restano nello stesso giorno, con l'ora legale
 * o senza. */
function corpo(giorno: string) {
  const samsung = { data_origin: "com.sec.android.app.shealth", recording_method: "automatically_recorded" };
  return {
    timestamp: new Date().toISOString(),
    app_version: "e2e",
    steps: [{ count: 12345, start_time: `${giorno}T08:00:00.123Z`, end_time: `${giorno}T20:00:00.456Z` }],
    exercise: [
      {
        type: "56",
        start_time: `${giorno}T16:00:00Z`,
        end_time: `${giorno}T16:30:00Z`,
        duration_seconds: 1800,
        distance_meters: 5200,
        metadata: samsung,
      },
    ],
    weight: [{ kilograms: 72.4, time: `${giorno}T06:00:00Z`, metadata: samsung }],
    heart_rate: [{ bpm: 70, time: `${giorno}T06:00:00Z` }],
  };
}

/** Una chiave nuova dalla schermata: «Crea la chiave», o «Rigenera» se un'altra prova ne
 * ha già creata una. Si legge dal campo «Chiave». */
async function nuovaChiave(page: Page): Promise<string> {
  await page.goto("/attivita/collega");
  const crea = page.getByRole("button", { name: "Crea la chiave" });
  const rigenera = page.getByRole("button", { name: "Rigenera la chiave" });
  await expect(crea.or(rigenera)).toBeVisible();
  if (await rigenera.isVisible()) {
    await rigenera.click();
    await page.getByRole("button", { name: "Rigenera", exact: true }).click();
  } else {
    await crea.click();
  }
  const campo = page.getByLabel("Chiave", { exact: true });
  await expect(campo).toHaveValue(/^[A-Za-z0-9_-]{43}$/);
  return campo.inputValue();
}

async function senzaScorrimentoLaterale(page: Page, luogo: string) {
  await page.waitForLoadState("networkidle");
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
  expect(scrollWidth, `${luogo} scorre di lato`).toBeLessThanOrEqual(clientWidth);
}

test.use({ viewport: { width: 375, height: 812 } });

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();
});

test("dal ☰ si arriva ad «Attività», e da lì al collegamento coi suoi dieci passi", async ({ page }) => {
  await page.getByRole("button", { name: "Apri il menu" }).click();
  await page.getByRole("dialog", { name: "Menu" }).getByRole("link", { name: "Attività" }).click();

  await expect(page).toHaveURL(/\/attivita$/);
  await expect(page.getByRole("heading", { name: "Attività", level: 1 })).toBeVisible();
  // vuota o no, a seconda di cosa hanno lasciato le altre prove: una delle due strade c'è
  await page.getByRole("link", { name: /^(Collega HC Webhook|Collegamento con HC Webhook)$/ }).click();

  await expect(page).toHaveURL(/\/attivita\/collega$/);
  await expect(page.getByRole("heading", { name: "Collega HC Webhook" })).toBeVisible();
  await expect(page.getByRole("list", { name: "I passi in HC Webhook" }).getByRole("listitem")).toHaveCount(10);
  await expect(page.getByLabel("Indirizzo", { exact: true })).toHaveValue(/\/api\/v1\/activity\/hc-webhook$/);
  for (const pulsante of await page.getByRole("button", { name: /^Copia: / }).all()) {
    expect((await pulsante.boundingBox())!.height, "«Copia»").toBeGreaterThanOrEqual(44);
  }
  await senzaScorrimentoLaterale(page, "il collegamento");
});

test("la chiave apre il webhook: senza o sbagliata è 401, lo stesso corpo due volte salva una volta, e «Attività» lo mostra", async ({
  page,
}) => {
  const chiave = await nuovaChiave(page);
  const dati = corpo(giornoDiRoma(2));

  const senza = await page.request.post(WEBHOOK, { data: dati });
  expect(senza.status(), "senza chiave").toBe(401);
  const sbagliata = await page.request.post(WEBHOOK, { data: dati, headers: { "X-Spena-Token": "x".repeat(43) } });
  expect(sbagliata.status(), "chiave sbagliata").toBe(401);
  for (const volta of [1, 2]) {
    const risposta = await page.request.post(WEBHOOK, { data: dati, headers: { "X-Spena-Token": chiave } });
    expect(risposta.status(), `invio ${volta}`).toBe(200);
    expect(await risposta.json()).toMatchObject({ saved: { steps_days: 1, exercises: 1, weights: 1 } });
  }

  await page.goto("/attivita");
  await expect(page.getByText(/^Ultima sincronizzazione: oggi alle \d\d:\d\d\.$/)).toBeVisible();
  await expect(page.getByText(/^Arrivati e non usati: frequenza cardiaca\./)).toBeVisible();
  await expect(
    page.getByRole("list", { name: "Passi degli ultimi 7 giorni" }).getByText("12.345", { exact: true })
  ).toHaveCount(1);
  await expect(
    page.getByRole("list", { name: "Allenamenti degli ultimi 7 giorni" }).getByText("Corsa · 30 min · 5,2 km", { exact: true })
  ).toHaveCount(1);
  await expect(page.getByRole("list", { name: "Ultime pesate" }).getByText("72,4 kg", { exact: true })).toHaveCount(1);
  await senzaScorrimentoLaterale(page, "«Attività»");
});

test("un corpo troppo grosso lo rifiuta il backend, e si legge in «Attività»; la prova di HC Webhook pure", async ({
  page,
}) => {
  const chiave = await nuovaChiave(page);
  const grosso = JSON.stringify({ timestamp: new Date().toISOString(), imbottitura: "x".repeat(3 * 1024 * 1024) });

  const rifiutato = await page.request.post(WEBHOOK, {
    data: grosso,
    headers: { "X-Spena-Token": chiave, "Content-Type": "application/json" },
  });
  // 413 del backend, con la sua frase: Nginx l'ha lasciato passare (4 MB su questa rotta)
  expect(rifiutato.status()).toBe(413);
  expect(await rifiutato.json()).toEqual({
    detail:
      "Rifiutato: il corpo supera i 2 MB. Nel webhook di Spena, in HC Webhook, lascia solo Passi, Sessioni di esercizio e Peso.",
  });
  await page.goto("/attivita");
  await expect(page.getByText(/^Ultima sincronizzazione: oggi alle \d\d:\d\d, rifiutata\.$/)).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "Rifiutato: il corpo supera i 2 MB." })).toBeVisible();

  const prova = await page.request.post(WEBHOOK, {
    data: { ...corpo(giornoDiRoma(0)), test: true },
    headers: { "X-Spena-Token": chiave },
  });
  expect(prova.status()).toBe(200);
  expect(await prova.json()).toMatchObject({ test: true, saved: { steps_days: 0, exercises: 0, weights: 0 } });
  await page.reload();
  await expect(
    page.getByText(/^Ultima sincronizzazione: oggi alle \d\d:\d\d, la prova di HC Webhook: arrivata, e non salva niente\.$/)
  ).toBeVisible();
});
```

- [ ] **Step 2: Il contrasto in `style.spec.ts`**

1. In `const SCHERMATE = [`, subito dopo la riga `"/anagrafica",`, aggiungi:
   ```ts
     "/attivita",
     "/attivita/collega",
   ```
   Così il giro dei due temi (`perOgniLuogo`) e la prova delle parole tecniche passano anche da qui, nello stato che le prove lasciano.
2. **In fondo al file**, aggiungi:

```ts
// H2, «Attività». Il telefono non c'è: il corpo di HC Webhook lo manda la prova, con la chiave
// creata dalla rotta (la sessione della prova la apre). Un totale dei passi, una finestra di
// 15 minuti che non si salva (per misurare l'avviso ambra del problema), una camminata, una
// pesata, il sonno che Spena non usa. Vedi `frontend/e2e/attivita.spec.ts`.
test("attività e collegamento a 375px: i testi si leggono nei due temi, e niente scorre di lato", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 });
  const creata = await page.request.post("/api/v1/activity/token");
  expect(creata.status()).toBe(201);
  const { token } = (await creata.json()) as { token: string };
  const giorno = new Intl.DateTimeFormat("en-CA", { timeZone: "Europe/Rome" }).format(
    new Date(Date.now() - 86_400_000)
  );
  const inviato = await page.request.post("/api/v1/activity/hc-webhook", {
    headers: { "X-Spena-Token": token },
    data: {
      timestamp: new Date().toISOString(),
      steps: [
        { count: 6789, start_time: `${giorno}T08:00:00.123Z`, end_time: `${giorno}T20:00:00.456Z` },
        { count: 120, start_time: `${giorno}T06:00:00Z`, end_time: `${giorno}T06:15:00Z` },
      ],
      exercise: [
        {
          type: "79",
          title: "Giro del parco",
          start_time: `${giorno}T15:00:00Z`,
          end_time: `${giorno}T15:20:00Z`,
          metadata: { data_origin: "com.sec.android.app.shealth" },
        },
      ],
      weight: [{ kilograms: 81.7, time: `${giorno}T05:00:00Z` }],
      sleep: [{ session_end_time: `${giorno}T05:00:00Z`, duration_seconds: 25200, stages: [] }],
    },
  });
  expect(inviato.status()).toBe(200);

  await page.goto("/attivita");
  await expect(page.getByRole("list", { name: "Passi degli ultimi 7 giorni" })).toBeVisible();
  await expect(page.getByRole("alert").filter({ hasText: "Passi non salvati" })).toBeVisible();
  for (const tema of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: tema });
    await fermo(page);
    expect(await testiIlleggibili(page), `«Attività», tema ${tema}`).toEqual([]);
  }
  await page.emulateMedia({ colorScheme: "light" });
  await senzaScorrimentoLaterale(page, "«Attività»");

  // il collegamento con la chiave appena creata: i tre campi da copiare a video
  await page.goto("/attivita/collega");
  await page.getByRole("button", { name: "Rigenera la chiave" }).click();
  await page.getByRole("button", { name: "Rigenera", exact: true }).click();
  await expect(page.getByLabel("Intestazioni (JSON)", { exact: true })).toBeVisible();
  for (const tema of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: tema });
    await fermo(page);
    expect(await testiIlleggibili(page), `il collegamento, tema ${tema}`).toEqual([]);
  }
  await page.emulateMedia({ colorScheme: "light" });
  await senzaScorrimentoLaterale(page, "il collegamento");
});
```

Se sul ramo una delle funzioni usate (`testiIlleggibili`, `fermo`, `senzaScorrimentoLaterale`) ha un altro nome o un'altra firma, usa quella che c'è e scrivilo nel report; non duplicarla.

- [ ] **Step 3: Il type check delle prove**

Run (da `<worktree>/frontend`): `npm run typecheck`
Expected: pulito (le prove le compila `tsconfig.node.json`).

- [ ] **Step 4: L'e2e intera**

Con i comandi delle Global Constraints, dalla radice di `<worktree>`, su uno stack ricreato da zero (`down -v` prima dell'`up`, se ne era rimasto uno di questo ramo).
Expected: tutte verdi, le quattro nuove comprese (e le prove di `perOgniLuogo` e delle parole tecniche, che ora passano anche da `/attivita` e `/attivita/collega`). **Annota il numero** delle prove passate: è `N_e2e` del Task 10. Poi `down -v` e `rm .env`, sempre.

Se una prova nuova fallisce:
- un `413` che arriva **senza** il JSON del backend (una pagina HTML di Nginx) vuol dire che la `location` del webhook non è nell'immagine: controlla che `frontend/nginx.conf` del ramo la abbia e che lo stack sia stato ricostruito (`--build`);
- un `401` con la chiave appena letta vuol dire che il campo «Chiave» non portava la chiave intera: scrivi nel report cosa c'era;
- un testo sotto 4,5:1: scrivi nel report quale e con che rapporto, **nessun token nuovo**; il task si ferma `bloccato` con la misura.

- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/attivita.spec.ts frontend/e2e/style.spec.ts
git commit -m "H2: nel browser vero — la chiave dalla schermata, il webhook attraverso Nginx, il rifiuto dei 3 MB, il contrasto nei due temi"
```

---

### Task 9: I documenti

**Files:**
- Modify: `docs/prossimi-passi.md` (voce «## H2. Connettore Samsung Health»)
- Modify: `next-steps.md`

Leggi i due file com'è sul ramo prima di cambiarli.

- [ ] **Step 1: `docs/prossimi-passi.md`**

1. Il titolo `## H2. Connettore Samsung Health **[TBD]**` diventa:
   ```markdown
   ## H2. Connettore Samsung Health **[FATTO <data di oggi> — sul ramo `night/h2-health-connect`, non ancora in produzione]**
   ```
2. In fondo alla voce (dopo il paragrafo che comincia con «**TODO (sottoagente):**»), aggiungi:
   ```markdown
   **Il TODO è risolto** (ricerca del 2026-10-13): Samsung Health scrive in Health Connect
   passi, allenamenti, peso e altro (non il riepilogo delle calorie attive), e **HC Webhook**,
   un'app Android libera, legge Health Connect e manda i dati a un indirizzo. Mattia ha deciso
   il 2026-10-13: HC Webhook subito, con la PWA (col wrapper Capacitor la lettura passerà
   dentro l'app, il backend resta); Spena legge passi, allenamenti e peso; il dispendio lo
   calcola Spena, ma è di P2 e H3. Spec:
   `docs/superpowers/specs/2026-10-13-h2-health-connect-design.md` (il §9 dice cosa resta a P2).

   **Fatto il <data di oggi>**, sul ramo `night/h2-health-connect` (da revisionare):
   `POST /api/v1/activity/hc-webhook` fuori dalla sessione, aperto da una chiave sua in
   `X-Spena-Token` (si vede una volta, si rigenera; nel database solo l'impronta), rifiuto
   silenzioso, 2 MB letti a pezzi, mai un 500 su un corpo inatteso. I passi solo nella forma
   «Giornaliero» di HC Webhook, l'unica in cui Health Connect toglie i doppioni fra telefono e
   orologio, e un totale per giorno di Roma che non si somma mai (`merge_steps_day` in
   `backend/app/domain/activity.py`); allenamenti e pesate unici per app e istante. Migrazione
   `0018`, cinque tabelle `activity_*`. A video «Attività» dal ☰ (l'ultima sincronizzazione,
   7 giorni di passi, allenamenti, pesate) e «Collega HC Webhook» coi dieci passi da fare sul
   telefono.

   **Ora P2 può contare l'attività**: la frase sopra («il fabbisogno calorico di P2 non può
   dipendere dall'attività») non vale più, ma resta vero che P2 deve funzionare anche senza:
   un giorno senza dati è un giorno senza dispendio calcolato, non uno zero.

   **Da provare sul telefono e coi dati veri:** la prova dei 10 minuti in Health Connect, il
   collegamento coi dieci passi, i passi di ieri uguali a quelli di Samsung Health, una
   settimana di sincronizzazioni senza buchi (l'ottimizzazione della batteria).
   ```
   Sostituisci `<data di oggi>` con la data vera.

- [ ] **Step 2: `next-steps.md`**

1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte)_`.
2. Togli la riga della voce (`grep -n "H2," next-steps.md`: `in corso` dalla Preparazione, sotto `## In corso`). Se `## In corso` resta vuota, rimetti `_(niente)_`.
3. In cima a «Fatti (recenti)» aggiungi:
   ```markdown
   - [fatto] <data di oggi> · H2, l'attività da Health Connect via HC Webhook: il webhook con la sua chiave (`X-Spena-Token`, rifiuto silenzioso, 2 MB, mai un 500), i passi solo «Giornaliero» e un totale per giorno di Roma, allenamenti e pesate senza doppioni, migrazione `0018`; «Attività» dal ☰ e «Collega HC Webhook» coi dieci passi [H2] → branch night/h2-health-connect (da revisionare)
   ```
4. In cima a «Da fare a mano (solo Mattia)» aggiungi:
   ```markdown
   - [tbd] P2 · H2 sul telefono, dopo il deploy: Samsung Health › Impostazioni › Health Connect (passi, esercizio, peso; sincronizzazione Samsung Cloud attiva); la prova dei 10 minuti in Health Connect › Dati e accesso (i dati di ieri ci sono); HC Webhook installato e fuori dall'ottimizzazione della batteria; la chiave e i dieci passi di «Collega HC Webhook»; «Testa Webhook»; i passi di ieri uguali a Samsung Health. Nel browser passati la chiave, il webhook attraverso Nginx, i 401, il doppio invio, il rifiuto dei 3 MB, la prova, il contrasto nei due temi, i 375 px [H2]
   ```
5. Nella sezione `### Idee` aggiungi:
   ```markdown
   - [idea] P3 · P2: il dispendio del giorno dall'attività di H2 — MET per tipo di allenamento su `exercise_type`, i passi fuori dagli allenamenti, il tempo in comune fra due app contato una volta, il peso dall'ultima pesata; vedi il §9 di `docs/superpowers/specs/2026-10-13-h2-health-connect-design.md` [P2]
   ```
6. Se nella notte sono emerse altre cose da fare fuori da questo piano, aggiungile come `idea` o `tbd` nella sezione giusta, con la voce di `docs/prossimi-passi.md` fra parentesi quadre.

- [ ] **Step 3: Commit**

```bash
git add docs/prossimi-passi.md next-steps.md
git commit -m "docs: H2, l'attività da Health Connect fatta sul ramo"
```

---

### Task 10: La verifica finale e il report

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

Expected: vitest tutto verde — **`N_vitest` della Preparazione più 44**, cioè 27 (Task 5: 4 delle chiamate, 23 delle parole) + 10 (Task 6: 4 di `CopyField`, 6 di `ConnectScreen`) + 7 (Task 7), in **`N_file` + 5** file (`api.test.ts`, `format.test.ts`, `CopyField.test.tsx`, `ConnectScreen.test.tsx`, `ActivityScreen.test.tsx`); se il numero differisce, scrivi nel report da dove viene la differenza. Typecheck, lint e build puliti. `npx tsc -b --force` perché `node_modules` è condiviso col checkout principale, e con lui il `tsbuildinfo`: `--force` compila davvero tutto.

- [ ] **Step 2: Il backend**

Da `<worktree>/backend`:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_h2 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Expected: tutto verde, **`N_pytest` + 96** (1 della migrazione, 52 del dominio, 11 della chiave, 21 del webhook, 1 di Nginx, 10 del riepilogo e della chiave).

- [ ] **Step 3: I grep**

Dalla radice del worktree:

```bash
grep -rn "emerald\|neutral-" frontend/src
git diff master --stat -- frontend/src/index.css frontend/src/theme.test.ts frontend/package.json frontend/package-lock.json backend/pyproject.toml
git diff master --name-only -- backend/alembic
grep -n "token_hash" backend/app/api/activity.py backend/app/schemas/activity.py
```

Expected: i primi due vuoti (nessun colore crudo; nessun token, nessuna dipendenza); il terzo solo `backend/alembic/versions/0018_attivita_health_connect.py`; il quarto vuoto (l'impronta della chiave non esce mai dal servizio e dal repository).

- [ ] **Step 4: L'e2e intera**

Con i comandi delle Global Constraints, su uno stack ricreato da zero. Expected: tutte verdi, `N_e2e` del Task 8. Poi `down -v` e `rm .env`, sempre. Poi il database dei test di questo ramo:

```bash
docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_h2 WITH (FORCE)'
```

- [ ] **Step 5: Il report**

Nel report della notte, `docs/night-reports/<data di oggi>.md` sul ramo: se il file c'è già sul ramo aggiungi una sezione in fondo, altrimenti crealo con un titolo `# Notte del <data di oggi>` (gli altri piani della notte scrivono lo stesso file sui loro rami: l'unione la fa la revisione). Per questo piano: il ramo e da dove parte (`master`); la `down_revision` usata (`0012`, o la testa trovata nella Preparazione) e che **al merge va ripuntata** (sezione «Al merge» del piano); i conti veri (vitest, pytest, e2e) contro quelli della Preparazione; il database dei test (`spena_test_h2`, tolto); le migrazioni di test fatte oltre a quella di `AppHeader.test.tsx` (dovrebbero essere zero); le scelte che Mattia può voler rivedere: la voce «Attività» nel ☰ e i percorsi `/attivita` e `/attivita/collega`, l'intestazione `X-Spena-Token` e le intestazioni da incollare come JSON, la chiave che si vede una volta sola, i passi accettati solo in forma «Giornaliero», le ultime 200 sincronizzazioni nel registro, i 7 giorni / 20 allenamenti / 5 pesate a video; i file che al merge incontrano altri rami della notte (`main.py` e `AppHeader.tsx`/`AppHeader.test.tsx` con H1, `App.tsx` con S3, R8, le pagine scartate e H1, `SCHERMATE` e il fondo di `style.spec.ts` con quasi tutti; le migrazioni con R5 e S4); e le azioni di «Dopo il deploy (solo Mattia)». Niente push, niente merge, niente deploy.

```bash
git add docs/night-reports/
git commit -m "report: H2, l'attività da Health Connect, la notte"
```
