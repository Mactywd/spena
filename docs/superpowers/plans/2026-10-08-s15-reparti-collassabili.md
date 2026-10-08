# S15 — I reparti della dispensa si aprono e si chiudono: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** in Dispensa il titolo di ogni reparto diventa il pulsante che lo apre e lo chiude; chiuso, il titolo dice quante voci ha e, se ci sono, quante sono finite e quante in scadenza; i reparti chiusi si ricordano nel `localStorage`; una ricerca e il riepilogo delle scadenze aprono i reparti che hanno un risultato senza cambiare quel che è salvato; la voce appena aggiunta apre il suo reparto e lo salva aperto.

**Architecture:** solo frontend, nessuna rotta nuova, nessuna migrazione, nessun token nuovo. Tre pezzi piccoli e una schermata: in `pantryView.ts` le funzioni pure (`sectionOpen`, la regola della tabella di §3 della spec; `attentionCounts`, `finishedText`, `expiringText` per il titolo chiuso); un file nuovo `features/pantry/collapsedSections.ts` con l'involucro del `localStorage` (`loadCollapsed`, `saveCollapsed`, come quello di `recipeFilters.ts`) e il hook `useCollapsedSections(filtering)`; `Section` prende tre props facoltative (`collapsed`, `onToggle`, `closedNote`) e senza `onToggle` resta la sezione di oggi, quindi Lista e Sistema la spesa non cambiano; `PantryScreen` passa alle sezioni lo stato del hook e la nota, e apre il reparto della voce aggiunta dove già la porta in vista (`setRevealId`).

**Tech Stack:** React 19, TypeScript, Tailwind 4 (token in `@theme`), TanStack Query 5, react-router 7, Vitest + Testing Library (jsdom), Playwright. Il backend non si tocca.

**Spec:** `docs/superpowers/specs/2026-10-06-reparti-collassabili-bozza.md` (tutta: §2 il titolo, §3 la tabella di cosa apre un reparto, §4 dove si ricorda, §5 cosa cambia nel codice, §6 le decisioni di Mattia, §7 fuori scope). Va letta con `docs/superpowers/specs/2026-10-06-cibo-casa-bozza.md` §4 (S14: il mondo nasconde i reparti dell'altro mondo, non li apre né li chiude). In `docs/prossimi-passi.md` la voce **S15** e, in S11, la frase «Con i reparti chiusi (S15) una ricerca apre quelli che contengono un risultato».

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/s15-reparti-collassabili` (`.worktrees/` è già in `.gitignore`), ramo `night/s15-reparti-collassabili`, creato da **`night/s14-cibo-casa`** (S14, che parte da `night/tema-scuro-spenti`, che parte da `night/s12-righe-dispensa`, che parte da `night/s3-ingresso-diretto`, che parte da `master`). Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì (o dalle sue `backend/` e `frontend/`), mai dalla radice del checkout principale. Il checkout principale non si tocca: se vi trovi modifiche non committate, sono dell'utente. **Nessun push, nessun merge, nessun deploy. Mai `git stash`.** Nessuna lettura né scrittura sulla produzione.
- **I file che anche i piani prima di questo toccano** — `frontend/src/features/pantry/PantryScreen.tsx` e il suo test, `frontend/src/features/pantry/pantryView.ts` e il suo test (S3, S12, S14), `frontend/src/components/ui/icons.ts` (forse S3, S12), `frontend/e2e/style.spec.ts` (tutti), `next-steps.md`, `docs/prossimi-passi.md` — **leggili com'è sul ramo prima di cambiarli**. Il piano descrive ogni modifica a questi file contro un'ancora riconoscibile (una funzione, un elemento JSX, un testo esatto), mai contro numeri di riga, e aggiunge sempre **in blocchi propri**, senza toccare le righe degli altri piani. Dove il piano dà un file intero (`Section.tsx`, `collapsedSections.ts` e il suo test) è perché nessun piano precedente lo tocca: la Preparazione lo verifica.
- Tutto il colore passa dai token di `frontend/src/index.css`. Nessuna schermata nomina un colore crudo: `grep -rn "emerald\|neutral-" frontend/src` resta vuoto. Ogni testo sta sopra 4,5:1, in chiaro e in scuro, e lo misura `frontend/e2e/style.spec.ts`. **Nessun token nuovo**: i due colori del titolo chiuso sono `text-finished` (il «Finito» della riga) e `text-expiry` (la scadenza della riga), già testo su `card` oggi.
- Le icone si importano solo da `frontend/src/components/ui/icons.ts`. Servono `IconChevronDown` e `IconChevronRight`, che il Task 3 aggiunge lì (in `@tabler/icons-react` ci sono già: `node_modules/@tabler/icons-react/dist/esm/icons/IconChevronDown.mjs`).
- Ogni bersaglio nuovo è almeno 44×44 px (il titolo che apre e chiude: `min-h-11`, largo quanto la scheda). A 375 px nessuna schermata scorre di lato.
- **Il pulsante del titolo è un `<button>` scritto a mano**, non `Button`: è l'intestazione di un accordion (icona, nome, numero e chevron a tutta larghezza), come il riepilogo delle scadenze è un `<button>` con `aria-pressed`. Non è mai spento: niente `disabled`, niente `aria-disabled`.
- **Mai un vicolo cieco.** Con lo spazio del sito bloccato o un valore illeggibile i reparti partono tutti aperti e si aprono e chiudono lo stesso, per la durata dello schermo. Un reparto chiuso non nasconde in silenzio: dice quante voci ha, quante sono finite (con il loro «In lista») e quante in scadenza.
- **Il frontend non calcola logica di dominio.** «In scadenza» è il verdetto del server (`expiry`), letto con `isExpiring` com'è oggi; «finito» è `status === "finished"`. Nessuna soglia di giorni nel client.
- Le parole a video sono in italiano e **si copiano esattamente come sono scritte qui**; gli identificatori in inglese; i commenti in italiano come nel resto del codice.
- **Il type check è `npm run typecheck`** (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0 (settima lezione di `CLAUDE.md`).
- Controlli del frontend, da `<worktree>/frontend`: `npx vitest run` (non esiste `npm test`), `npm run typecheck`, `npm run lint`, `npm run build`.
- **Backend su Postgres vero**, solo per la verifica finale (questo piano non cambia una riga del backend). Il database dei test è il container `spena-db-1` (porta 5433), da usare solo come database dei test: se `docker ps --format '{{.Names}}'` non lo mostra, `docker start spena-db-1`. **Mai `docker compose up` dal worktree** (il nome del progetto Compose viene dalla cartella: nascerebbe un secondo Postgres che litiga sulla 5433), mai `-f docker-compose.prod.yml`. Nel worktree non c'è un `.venv`: si usa quello del checkout principale; `python -m` mette la cartella corrente in testa a `sys.path`, quindi si prova l'`app` del worktree. Il comando, sempre da `<worktree>/backend`:
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_s15 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
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
- Nessuna dipendenza nuova, nessuna migrazione, nessun cambio di configurazione globale.

- **Il database dei test è `spena_test_s15`, non `spena_test`** (deciso dall'orchestrazione della fase giorno del 2026-10-08). Questo ramo discende da `night/s12-righe-dispensa`, che aggiunge la migrazione `0013`, e la suite fa `alembic upgrade head` sul suo database all'avvio: girata su `spena_test` lo porterebbe alla `0013`, e il piano `suggerimenti-soglia`, che parte da `master` (ferma alla `0012`), troverebbe `alembic upgrade head` rotto («Can't locate revision identified by '0013'»). Per questo ogni comando di pytest di questo piano porta `TEST_DATABASE_URL` davanti, e il database si crea nella Preparazione e si toglie alla fine della verifica finale:
  ```bash
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_s15 WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_s15'
  # … i task …
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_s15 WITH (FORCE)'
  ```
  La creazione va fatta come primo passo della Preparazione, prima di qualunque pytest; il `DROP` come ultimo passo della verifica finale, dopo l'ultimo pytest.

### Preparazione (una volta, prima del Task 1)

- [ ] Il ramo di partenza c'è, e porta quel che questo piano consuma:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify night/s14-cibo-casa
  git log --oneline master..night/s14-cibo-casa | wc -l
  git merge-base --is-ancestor night/s3-ingresso-diretto night/s14-cibo-casa && echo "S3 dentro"
  git show night/s14-cibo-casa:frontend/src/features/pantry/PantryScreen.tsx | grep -n "setRevealId("
  git show night/s14-cibo-casa:frontend/src/domain/types.ts | sed -n '/interface PantryItem /,/^}/p' | grep -c "ingredient_kind"
  ```
  Expected: un hash; un numero maggiore di zero; `S3 dentro`; almeno due righe con `setRevealId(` (la `useCallback` che lo spegne e almeno un punto che lo accende con l'id della voce creata); `1`.
  - Se `night/s14-cibo-casa` non c'è, **fermati**: la catena della notte si è interrotta prima di questo piano, e nessun task parte. Il checkout principale non si tocca: la causa va nel report della notte (`docs/night-reports/<data>.md`), sull'ultimo ramo della catena che esiste, con la riga di S15 segnata `bloccato` in quel ramo e la domanda per Mattia.
  - Se il ramo c'è ma `PantryItem` non ha `ingredient_kind` (S14 si è fermato a metà), il piano parte lo stesso: S15 non consuma niente di S14 se non la composizione dei filtri. **Salta solo il test «il mondo scelto (S14)…» del Task 5** e scrivilo nel report.
  - Se `setRevealId(` compare solo nella `useCallback` (nessun punto lo accende), l'ingresso diretto di S3 ha cambiato strada: il Task 5 non ha dove agganciarsi. Fai i Task 1–4 e 6–8, segna il Task 5 `bloccato` con la diagnosi.
- [ ] Dal checkout principale, allinea `node_modules` al lockfile (non aggiunge dipendenze, installa quelle di `package-lock.json`):
  ```bash
  cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund
  ```
- [ ] Crea il worktree dal ramo di S14 e collega `node_modules` (e solo quello: **niente `.env`**):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/s15-reparti-collassabili -b night/s15-reparti-collassabili night/s14-cibo-casa
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/s15-reparti-collassabili/frontend/node_modules
  ```
- [ ] Cosa hanno già cambiato i piani prima di questo nei file di questo piano:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/s15-reparti-collassabili
  git diff --stat master -- \
    frontend/src/components/ui/Section.tsx \
    frontend/src/components/ui/Section.test.tsx
  ls frontend/src/features/pantry/collapsedSections.ts 2>/dev/null
  git diff --stat master -- \
    frontend/src/features/pantry/PantryScreen.tsx \
    frontend/src/features/pantry/PantryScreen.test.tsx \
    frontend/src/features/pantry/pantryView.ts \
    frontend/src/features/pantry/pantryView.test.ts \
    frontend/src/components/ui/icons.ts
  grep -n "IconChevronDown\|IconChevronRight" frontend/src/components/ui/icons.ts
  ```
  Expected: il primo `diff` **vuoto**, nessun `collapsedSections.ts`; il secondo `diff` non vuoto (S3, S12, S14 hanno toccato la Dispensa: è previsto). Se `Section.tsx` è cambiato, non sovrascriverlo col file intero del Task 3: applica le modifiche di questo piano sopra la versione del ramo, pezzo per pezzo (il ramo senza `onToggle` deve restare com'è sul ramo), e scrivilo nel report. Se `icons.ts` esporta già i due chevron, il Task 3 non li aggiunge di nuovo.
- [ ] I nomi della prova e2e (Task 6) sono liberi sul ramo:
  ```bash
  grep -rn "orata\|calamaro" frontend/e2e
  ```
  Expected: vuoto. Se un piano prima di questo li ha usati, nel Task 6 sostituiscili con due altri ingredienti del reparto `pesce` del seme (`merluzzo`, `vongola`, `cozza`, `gambero`) che il `grep` non trova, e scrivilo nel report.
- [ ] La linea di partenza, dal worktree:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/s15-reparti-collassabili/frontend && npx vitest run 2>&1 | grep -E "Test Files|Tests "
  cd ../backend && TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_s15 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q 2>&1 | tail -n 1
  ```
  Expected: tutto verde. **Annota i numeri** (file e test di vitest, test di pytest): sono `N_file`, `N_vitest`, `N_pytest` del Task 8, e dipendono da quel che i piani prima di questo hanno aggiunto. Se una delle due linee non è verde, fermati: non è un difetto di questo piano, e va scritto nel report.
- [ ] In `next-steps.md` del ramo, la riga di S15 (in «Pronti per la notte», o dove la trovi: `grep -n "S15" next-steps.md`) passa in «In corso» con lo stato `in corso` e il ramo: sostituisci `[pronto]` (o lo stato che porta) con `[in corso]`, sposta la riga sotto `## In corso` e aggiungi in fondo `→ branch night/s15-reparti-collassabili`. Poi:
  ```bash
  git add next-steps.md
  git commit -m "docs: S15 in corso sul ramo night/s15-reparti-collassabili"
  ```

---

## Obiettivo e contesto

La Dispensa raggruppa per reparto, ogni gruppo in una `Section` con l'icona, il nome e il numero di voci. Con una dispensa vera si scorre molto per arrivare a un reparto: Mattia ha chiesto (S15) che i titoli si aprano e si chiudano, così la dispensa si naviga per reparto. Due cose da non sbagliare, già scritte nella voce: **una ricerca apre i reparti che hanno un risultato**, e **un reparto chiuso dice quante voci contiene**, altrimenti chiuso sembra vuoto. La bozza aggiunge la regola che tiene insieme tutto: **un filtro mostra quel che ha trovato, e non cambia quel che l'utente aveva deciso**. Ricerca e riepilogo delle scadenze sono filtri; il mondo di S14 («Tutto / Cibo / Casa») è una vista, e una vista non apre niente.

## Decisioni prese

Da Mattia, il 2026-10-07 (spec §6, tutte le raccomandate):

1. **Chiuso, il titolo dice «N finito» e «N in scadenza»** oltre al numero, solo quando ci sono: un reparto chiuso non deve nascondere le righe che hanno un pulsante da toccare («In lista» su una finita) o un tempo che corre. In parole, non con un pallino.
2. **`localStorage`** per i reparti chiusi, chiave `spena.dispensa.reparti-chiusi`, l'elenco dei **chiusi** (un reparto nuovo nasce aperto; chi non ha mai chiuso niente vede la dispensa di oggi). Diverso da S14 (`sessionStorage`): chiudere «Spezie» è una disposizione della propria dispensa, e ritrovarla domani è il punto.
3. **Il riepilogo delle scadenze premuto apre i reparti con una scadenza**, come la ricerca, senza salvare.
4. **Una voce aggiunta in un reparto chiuso lo apre e lo salva aperto**: l'utente ha appena messo lì qualcosa.
5. **Niente «chiudi tutto / apri tutto»** per ora (resta un'idea in `next-steps.md`, Task 7).

Dalla spec, decise con la bozza e qui solo riportate: tutto il titolo è il pulsante (icona, nome, numero, chevron), alto almeno 44 px, dentro l'`h2` con `aria-expanded` e `aria-controls` (schema ARIA dell'accordion); il contenuto chiuso ha `hidden`, così tacche e ✕ escono dall'ordine del Tab; chevron `chevron-down` aperto e `chevron-right` chiuso, in `ink-faint`; **nessuna animazione**; il numero resta lo stesso aperto e chiuso; se a 375 px la nota non ci sta accanto al nome, va a capo sotto il nome, piccola; ricerca e riepilogo aprono senza salvare, e cancellati la dispensa torna allo stato salvato; toccare il titolo durante una ricerca chiude o apre per davvero, e si salva; il mondo di S14 non apre e non chiude; `Section` prende `collapsed`, `onToggle`, `closedNote`, e senza `onToggle` è la sezione di oggi (Lista, Sistema la spesa); la nota la scrive la Dispensa; involucro dello spazio locale come `recipeFilters.ts` (bloccato o illeggibile → tutto aperto); nessun token nuovo.

Scelte di questo piano, dove la spec non arrivava (deciso da Claude su delega di Mattia; reversibili):

6. **La regola a video è una funzione pura**, `sectionOpen(category, view)` in `pantryView.ts`: senza filtro conta il salvato; con un filtro acceso (ricerca scritta o riepilogo premuto) un reparto a video è aperto, salvo che lo si sia chiuso a mano durante quel filtro. Per ricordare «chiuso a mano durante il filtro» il hook tiene un secondo insieme, `closedWhileFiltering`, che si svuota quando il filtro si spegne. La voce aggiunta non passa da qui: il suo reparto si apre **nei salvati** nel momento stesso in cui la si porta in vista (decisione 4), quindi quando la riga arriva il reparto è già aperto.
7. **Dove vive lo stato:** `features/pantry/collapsedSections.ts`, con `COLLAPSED_KEY`, `loadCollapsed`, `saveCollapsed` e il hook `useCollapsedSections(filtering)` → `{ isOpen(category), setOpen(category, open) }`. Si salva con un `useEffect` su `collapsed` (anche al montaggio, che riscrive quel che ha letto: innocuo, e ripulisce un valore illeggibile). L'elenco si scrive in ordine alfabetico, per un valore stabile.
8. **Un nome salvato che non è un reparto della dispensa di oggi resta in memoria e non fa niente** (è il «si ignora» di §4): nessun gruppo ha quel nome. L'elenco dei reparti validi non si legge da `domain/categories` (che ha un solo importatore, `CategorySelect`, per regola della Consegna 6b). Vedi la scelta 3 decisa da Mattia.
9. **Le parole del titolo chiuso:** il numero com'è oggi, poi ` · ` e la nota: «1 finito», «2 finiti» (l'accordo al plurale, dal giro di T3: «Accordi sbagliati»), «1 in scadenza», «2 in scadenza»; con tutte e due, «1 finito · 2 in scadenza». Esempio intero: «Verdura 7 · 1 finito · 2 in scadenza». La nota sta accanto al numero, a destra del nome; il gruppo numero+nota va a capo sotto il nome quando non ci sta (`flex-wrap`, `justify-between`). «finito» in `font-medium text-finished`, «in scadenza» in `font-medium text-expiry`, il numero e i ` · ` in `text-ink-faint`, tutto `text-xs`.
10. **Cosa conta la nota:** «finito» conta le voci `finished`; «in scadenza» conta `isExpiring` (`expiry` non nullo e non finita: in scadenza **e** oltre la scadenza, come dice la spec, «in `expiry`»). Una finita con la scadenza conta una volta, come finita: è la regola di oggi del riepilogo, che lascia fuori le finite. Vedi la scelta 2 decisa da Mattia.
11. **Il titolo, nel disegno:** aperto ha lo stesso spazio di oggi (`pt-3 pb-1.5`, quadratino da 28 px: 46 px d'altezza); chiuso `py-3`, perché sotto non c'è più niente. Il contorno del fuoco sta **dentro** il pulsante (`focus-visible:-outline-offset-2`): la sezione ha `overflow-hidden` e il contorno globale, fuori di 2 px, verrebbe tagliato. Chevron `size-5`.
12. **Il nome della regione resta il solo nome del reparto** («Latticini»): `aria-labelledby` punta a uno `span` col nome, dentro il pulsante. Il nome del pulsante (e quindi dell'`h2`) è tutto il titolo, «Latticini 2» aperto, «Latticini 2 · 1 finito» chiuso: chi ascolta sente anche il numero, e chiuso sente cosa chiede attenzione. Fra il nome e il gruppo del numero c'è uno spazio di testo (`{" "}`): in un contenitore flex non si vede, ma senza, il calcolo del nome accessibile in jsdom incollerebbe «Latticini2».

**Decise da Mattia il 2026-10-09** (tutte e tre come raccomandato):

- **1. Un reparto chiuso a mano durante una ricerca resta chiuso finché la ricerca non si cancella**, anche se il testo cambia («mel» → «mela»). Alternativa: ogni testo nuovo riapre tutti i reparti con un risultato, e la chiusura vale solo per i salvati. Il piano tiene la prima: rispetta il gesto appena fatto, e cancellata la ricerca vale comunque il salvato. Fissato dal test «durante una ricerca il titolo chiude e apre per davvero, e si salva» (Task 4).
- **2. «N in scadenza» comprende anche le voci oltre la scadenza.** Alternativa: due conti, «N in scadenza · N oltre la scadenza», come il riepilogo in cima. Il piano tiene il conto unico della spec («in `expiry`»): il titolo resta corto, e il riepilogo in cima distingue già i due casi.
- **3. Un reparto chiuso che si svuota e poi torna (per esempio da «Sistema la spesa») torna chiuso**, col suo numero e la sua nota. Dall'ingresso diretto invece si apre (decisione 4). Alternativa: dimenticare un reparto chiuso quando sparisce dalla dispensa. Il piano tiene la prima: è una disposizione dell'utente, e il titolo chiuso dice cosa contiene.

## Criteri di accettazione

- [ ] In Dispensa ogni titolo di reparto è un pulsante dentro l'`h2`, largo quanto la scheda e alto almeno 44 px (e2e), con `aria-expanded` e `aria-controls` verso il contenuto; toccato, il reparto si chiude (`hidden`: righe, tacche e ✕ fuori dalla pagina accessibile) e si riapre.
- [ ] Chiuso, il titolo dice il numero di sempre e, solo se ci sono, «N finito/finiti» e «N in scadenza» (es. «Latticini 2 · 1 finito · 1 in scadenza»); aperto dice solo il numero. Chevron giù aperto, a destra chiuso.
- [ ] I reparti chiusi sono in `localStorage` alla chiave `spena.dispensa.reparti-chiusi` (elenco JSON dei chiusi, in ordine) e restano chiusi tornando in dispensa e dopo un ricaricamento (e2e).
- [ ] Una ricerca scritta apre i reparti chiusi che hanno un risultato, il riepilogo premuto quelli con una scadenza; nessuno dei due cambia l'elenco salvato; cancellata la ricerca o spento il riepilogo torna il salvato (vitest ed e2e).
- [ ] Durante una ricerca toccare un titolo chiude o apre per davvero, e si salva.
- [ ] La voce aggiunta dall'ingresso diretto in un reparto chiuso lo apre **prima** di essere portata in vista (la riga non è dentro un `[hidden]` quando si chiama `scrollIntoView`), e il reparto resta salvato aperto.
- [ ] Il mondo di S14 non apre e non chiude i reparti: nasconde quelli dell'altro mondo, e tornando su «Tutto» il reparto chiuso è ancora chiuso.
- [ ] Con lo spazio del sito bloccato i reparti partono aperti e si chiudono lo stesso, senza errori.
- [ ] La Lista e Sistema la spesa sono come prima: `Section` senza `onToggle` disegna lo stesso markup di oggi, e i loro test passano senza modifiche.
- [ ] Il titolo chiuso si legge nei due temi sopra 4,5:1 (e2e, `testiIlleggibili`), «finito» è il token `finished` e «in scadenza» il token `expiry`; a 375 px niente scorre di lato.
- [ ] Tutti i test di oggi passano senza modifiche alle asserzioni. vitest, typecheck, lint, build, pytest e l'e2e intera verdi; vitest ha 35 test in più, `style.spec.ts` una prova in più.
- [ ] `docs/prossimi-passi.md` e `next-steps.md` aggiornati sul ramo (Task 7), report della notte scritto (Task 8).

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
TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_s15 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Dalla radice di `<worktree>`:

```bash
grep -rn "emerald\|neutral-" frontend/src
git diff night/s14-cibo-casa --stat -- backend/ frontend/src/features/shopping-list frontend/src/features/stocking
grep -rn "spena.dispensa.reparti-chiusi" frontend/src | grep -v "\.test\."
```

Expected: il primo vuoto; il secondo vuoto (né backend né Lista né Sistema la spesa cambiano); il terzo una riga sola, in `frontend/src/features/pantry/collapsedSections.ts`. E l'e2e intera con i comandi delle Global Constraints.

## Fuori scope

- Reparti apribili in Lista e in Sistema la spesa (spec §7: la Lista si scorre camminando, e un reparto chiuso in corsia è una cosa dimenticata).
- Riordinare i reparti a mano; animazioni di apertura; «chiudi tutto / apri tutto» (decisione 5).
- Tutto quel che fanno S3, S12, il tema scuro e S14: l'ingresso diretto (scheda di conferma, scansione in serie), le emoji delle righe, i pulsanti spenti, il selettore dei mondi. Questo piano ne usa il risultato e non lo cambia.
- Un errore su una riga di un reparto chiuso (una tacca rifiutata dopo averlo chiuso) si vede solo riaprendolo: resta un'idea (Task 7).
- Qualunque modifica al backend.

## Margine di autonomia

- **Liberi:** i nomi di variabili locali, helper di test e funzioni interne non fissati qui; l'ordine dei test dentro un file; l'ordine delle classi Tailwind; la formulazione dei commenti, purché dicano il perché; i dettagli estetici del titolo (spazi, misura del chevron) purché restino i vincoli: 44 px, nessuna animazione, nessun colore crudo, nessun token nuovo, il contorno del fuoco non tagliato.
- **Fissi:** le parole a video («1 finito», «N finiti», «N in scadenza», il separatore ` · `); la chiave `spena.dispensa.reparti-chiusi` e il formato (elenco JSON dei chiusi); i nomi pubblici che altri task usano (`sectionOpen`, `SectionView`, `attentionCounts`, `finishedText`, `expiringText`, `COLLAPSED_KEY`, `loadCollapsed`, `saveCollapsed`, `useCollapsedSections`, le props `collapsed`, `onToggle`, `closedNote` di `Section`); il comportamento della tabella di §3 e delle tre scelte decise da Mattia il 2026-10-09, così come il piano lo scrive.
- **Nessuna dipendenza nuova**, nessuna migrazione, nessun token di colore nuovo.
- **Nessun test di oggi si cambia.** Se un test esistente di Dispensa, Lista o Sistema la spesa fallisce per questo piano, è un difetto del piano o del codice: si diagnostica. L'unica eccezione ammessa: un test che cercava un `h2` della **Dispensa** per nome esatto (oggi nessuno; un piano prima di questo potrebbe averne aggiunto uno) e ora trova «Latticini 2» — si migra alla regione (`getByRole("region", { name: "Latticini" })`), che tiene il nome del reparto, e si scrive nel report.
- **Una scelta di comportamento non coperta dal piano** → si ferma quel task, si fa commit del lavoro parziale sul ramo, lo si segna `bloccato` in `next-steps.md` del ramo con la domanda precisa per Mattia, e si passa al task successivo. Una scelta estetica o tecnica interna → la si prende, annotata nel report della notte.
- Se un test fallisce e non si risolve in modo ragionevole: niente test disattivati, niente asserzioni indebolite; `bloccato` con la diagnosi.

## Dipendenze

**Parte da `night/s14-cibo-casa`** (la catena: S3 → S12 → tema scuro → S14 → S15), così al merge i file della Dispensa non hanno conflitti. Da loro questo piano consuma:

- **S3 (ingresso diretto):** il punto (o i punti) di `PantryScreen.tsx` dove una voce appena entrata in dispensa viene portata in vista con `setRevealId(<voce creata>.id)` — il Task 5 si aggancia lì. E il modo in cui i test di `PantryScreen.test.tsx` fanno entrare una voce dalla Dispensa, che il test del Task 5 ripete.
- **S12:** niente di specifico; le righe (`PantryRow`) cambiano aspetto, non props che questo piano usa.
- **Tema scuro:** niente di specifico; i token sono quelli che `style.spec.ts` legge.
- **S14:** la composizione dei filtri prima di `groupForDisplay` (mondo → ricerca → scadenze) e il selettore «Tutto / Cibo / Casa», che il test del Task 5 preme. S14 decide quali reparti ci sono; S15 decide come stanno.

Il piano 4 della notte (suggerimenti, da `master`) non è nella catena e non serve: la prova e2e cerca gli ingredienti per nome intero.

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `frontend/src/features/pantry/pantryView.ts` | 1 | `SectionView`, `sectionOpen`, `attentionCounts`, `finishedText`, `expiringText` (in fondo, in un blocco proprio) |
| `frontend/src/features/pantry/pantryView.test.ts` | 1 | 13 test in fondo |
| `frontend/src/features/pantry/collapsedSections.ts` | 2 | nuovo: chiave, involucro del `localStorage`, `useCollapsedSections` |
| `frontend/src/features/pantry/collapsedSections.test.ts` | 2 | nuovo: 10 test |
| `frontend/src/components/ui/icons.ts` | 3 | `IconChevronDown`, `IconChevronRight` |
| `frontend/src/components/ui/Section.tsx` | 3 | `collapsed`, `onToggle`, `closedNote`; senza `onToggle` com'è |
| `frontend/src/components/ui/Section.test.tsx` | 3 | 4 test |
| `frontend/src/features/pantry/PantryScreen.tsx` | 4, 5 | il hook, la nota, le props della `Section`; il reparto della voce aggiunta |
| `frontend/src/features/pantry/PantryScreen.test.tsx` | 4, 5 | un `describe` nuovo in fondo, 8 test |
| `frontend/e2e/style.spec.ts` | 6 | una prova in fondo |
| `docs/prossimi-passi.md`, `next-steps.md` | Prep., 7 | S15 fatto sul ramo, idee |
| `docs/night-reports/<data>.md` | 8 | il report |

---

### Task 1: Le regole pure — quale reparto è aperto a video, cosa dice un reparto chiuso

**Files:**
- Modify: `frontend/src/features/pantry/pantryView.ts` (un blocco nuovo in fondo al file)
- Test: `frontend/src/features/pantry/pantryView.test.ts` (tre `describe` nuovi in fondo)

**Interfaces:**
- Consumes: `isExpiring(item: PantryItem): boolean`, già in `pantryView.ts`.
- Produces:
  - `interface SectionView { collapsed: ReadonlySet<string>; filtering: boolean; closedWhileFiltering: ReadonlySet<string> }`
  - `sectionOpen(category: string, view: SectionView): boolean`
  - `attentionCounts(rows: PantryItem[]): { finished: number; expiring: number }`
  - `finishedText(count: number): string` → «1 finito» / «N finiti»
  - `expiringText(count: number): string` → «N in scadenza»

Leggi `pantryView.ts` e `pantryView.test.ts` com'è sul ramo: S14 vi ha probabilmente aggiunto la funzione del mondo, e l'helper `item(...)` del test ha forse campi in più (`ingredient_kind`, `ingredient_emoji`). Non toccare niente di quel che c'è: si aggiunge in fondo.

- [ ] **Step 1: I test**

1. Nell'import da `./pantryView` in cima a `pantryView.test.ts` aggiungi, senza togliere niente, `attentionCounts`, `expiringText`, `finishedText`, `sectionOpen` e `type SectionView`.
2. In fondo al file aggiungi:

```ts
// --- S15: i reparti che si aprono e si chiudono ---

describe("sectionOpen", () => {
  const NIENTE: ReadonlySet<string> = new Set();
  const FRUTTA: ReadonlySet<string> = new Set(["frutta"]);
  // Le righe della tabella di §3 della spec S15 che passano da qui. La voce aggiunta e
  // il mondo di S14 stanno fuori: la prima apre il suo reparto nei salvati (`setOpen`,
  // nel momento in cui la si porta in vista), il secondo decide quali reparti ci sono,
  // non come stanno.
  const casi: [string, SectionView, boolean][] = [
    [
      "nessun filtro, mai chiuso: aperto",
      { collapsed: NIENTE, filtering: false, closedWhileFiltering: NIENTE },
      true,
    ],
    [
      "nessun filtro, chiuso e salvato: chiuso",
      { collapsed: FRUTTA, filtering: false, closedWhileFiltering: NIENTE },
      false,
    ],
    [
      "ricerca o riepilogo, chiuso e salvato: aperto, perché a video c'è solo se ha un risultato",
      { collapsed: FRUTTA, filtering: true, closedWhileFiltering: NIENTE },
      true,
    ],
    [
      "ricerca o riepilogo, aperto: aperto",
      { collapsed: NIENTE, filtering: true, closedWhileFiltering: NIENTE },
      true,
    ],
    [
      "ricerca o riepilogo, chiuso a mano durante il filtro: chiuso",
      { collapsed: FRUTTA, filtering: true, closedWhileFiltering: FRUTTA },
      false,
    ],
    [
      "filtro spento: vale il salvato, non quel che si era chiuso durante il filtro",
      { collapsed: NIENTE, filtering: false, closedWhileFiltering: FRUTTA },
      true,
    ],
  ];
  it.each(casi)("%s", (_caso, view, atteso) => {
    expect(sectionOpen("frutta", view)).toBe(atteso);
  });
});

describe("attentionCounts", () => {
  const casi: [string, PantryItem[], { finished: number; expiring: number }][] = [
    ["niente da dire", [item({}), item({ status: "low" })], { finished: 0, expiring: 0 }],
    ["una finita", [item({ status: "finished" }), item({})], { finished: 1, expiring: 0 }],
    [
      "in scadenza e oltre la scadenza contano tutte e due",
      [
        item({ expires_on: "2026-10-10", expiry: "soon" }),
        item({ expires_on: "2026-10-01", expiry: "expired" }),
      ],
      { finished: 0, expiring: 2 },
    ],
    [
      "una finita con la scadenza conta una volta, come finita (come nel riepilogo)",
      [item({ status: "finished", expires_on: "2026-10-10", expiry: "soon" })],
      { finished: 1, expiring: 0 },
    ],
  ];
  it.each(casi)("%s", (_caso, rows, atteso) => {
    expect(attentionCounts(rows)).toEqual(atteso);
  });
});

describe("finishedText e expiringText", () => {
  // l'accordo al plurale: «2 finito» era uno degli «accordi sbagliati» del giro di T3
  const casi: [number, string, string][] = [
    [1, "1 finito", "1 in scadenza"],
    [2, "2 finiti", "2 in scadenza"],
    [11, "11 finiti", "11 in scadenza"],
  ];
  it.each(casi)("%i", (n, finito, scadenza) => {
    expect(finishedText(n)).toBe(finito);
    expect(expiringText(n)).toBe(scadenza);
  });
});
```

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/features/pantry/pantryView.test.ts`
Expected: FAIL — `sectionOpen`, `attentionCounts`, `finishedText`, `expiringText` non sono esportati.

- [ ] **Step 3: Le funzioni**

In fondo a `pantryView.ts` aggiungi:

```ts
// --- S15: i reparti che si aprono e si chiudono ---

/** Come sta un reparto a video (spec S15 §3). `collapsed` è quel che l'utente ha chiuso
 * e che si ricorda; `filtering` è una ricerca scritta o il riepilogo delle scadenze
 * premuto; `closedWhileFiltering` sono i reparti chiusi a mano mentre quel filtro era
 * acceso, e si svuota quando il filtro si spegne. */
export interface SectionView {
  collapsed: ReadonlySet<string>;
  filtering: boolean;
  closedWhileFiltering: ReadonlySet<string>;
}

/** Se un reparto è aperto a video. Un filtro mostra quel che ha trovato e non cambia
 * quel che l'utente aveva deciso: con un filtro acceso a video restano solo i reparti
 * che hanno un risultato, e sono aperti — salvo quelli che si chiudono a mano proprio
 * adesso, perché toccare il titolo durante una ricerca chiude per davvero. Spento il
 * filtro, vale il salvato. Il mondo di S14 non passa da qui: decide quali reparti ci
 * sono, non come stanno. */
export function sectionOpen(category: string, view: SectionView): boolean {
  return view.filtering
    ? !view.closedWhileFiltering.has(category)
    : !view.collapsed.has(category);
}

/** Quel che un reparto chiuso non deve nascondere (spec S15 §2): le voci finite, che
 * hanno il loro «In lista» da toccare, e quelle in scadenza o oltre, che hanno un tempo
 * che corre. Una finita conta una volta, come finita: è la regola del riepilogo in cima
 * (`isExpiring` lascia fuori le finite). */
export function attentionCounts(rows: PantryItem[]): { finished: number; expiring: number } {
  let finished = 0;
  let expiring = 0;
  for (const row of rows) {
    if (row.status === "finished") finished += 1;
    else if (isExpiring(row)) expiring += 1;
  }
  return { finished, expiring };
}

export function finishedText(count: number): string {
  return count === 1 ? "1 finito" : `${count} finiti`;
}

export function expiringText(count: number): string {
  return `${count} in scadenza`;
}
```

- [ ] **Step 4: Passano**

Run: `npx vitest run src/features/pantry/pantryView.test.ts`
Expected: PASS, 13 test in più di prima nel file.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/pantry/pantryView.ts frontend/src/features/pantry/pantryView.test.ts
git commit -m "feat(dispensa): S15, le regole pure dei reparti — aperto a video, e cosa dice un reparto chiuso"
```

---

### Task 2: Dove si ricordano i reparti chiusi, e lo stato dello schermo

**Files:**
- Create: `frontend/src/features/pantry/collapsedSections.ts`
- Test: `frontend/src/features/pantry/collapsedSections.test.ts`

**Interfaces:**
- Consumes: `sectionOpen` (Task 1).
- Produces:
  - `COLLAPSED_KEY = "spena.dispensa.reparti-chiusi"`
  - `loadCollapsed(store?: Storage | null): ReadonlySet<string>`
  - `saveCollapsed(collapsed: ReadonlySet<string>, store?: Storage | null): void`
  - `useCollapsedSections(filtering: boolean): { isOpen: (category: string) => boolean; setOpen: (category: string, open: boolean) => void }`

Il hook non ha un test suo: lo provano i test della schermata (Task 4 e 5), che usano quello vero. L'involucro sì, qui, con una memoria finta come in `recipeFilters.test.ts`.

- [ ] **Step 1: I test**

Crea `frontend/src/features/pantry/collapsedSections.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { COLLAPSED_KEY, loadCollapsed, saveCollapsed } from "./collapsedSections";

/** Una memoria di prova: la stessa interfaccia del `localStorage`, in una mappa. */
class MemoriaFinta {
  private valori = new Map<string, string>();
  get length() {
    return this.valori.size;
  }
  clear() {
    this.valori.clear();
  }
  getItem(key: string) {
    return this.valori.get(key) ?? null;
  }
  key(index: number) {
    return [...this.valori.keys()][index] ?? null;
  }
  removeItem(key: string) {
    this.valori.delete(key);
  }
  setItem(key: string, value: string) {
    this.valori.set(key, value);
  }
}

function memoria(valore?: string): Storage {
  const m = new MemoriaFinta();
  if (valore !== undefined) m.setItem(COLLAPSED_KEY, valore);
  return m as unknown as Storage;
}

/** Una memoria che lancia a ogni accesso: i dati del sito bloccati, o lo spazio pieno. */
function memoriaRotta(): Storage {
  return {
    getItem: () => {
      throw new Error("bloccata");
    },
    setItem: () => {
      throw new Error("bloccata");
    },
  } as unknown as Storage;
}

describe("loadCollapsed", () => {
  it("niente salvato: nessun reparto chiuso, la dispensa di oggi", () => {
    expect([...loadCollapsed(memoria())]).toEqual([]);
  });

  it("l'elenco salvato torna", () => {
    expect([...loadCollapsed(memoria('["spezie","casa"]'))].sort()).toEqual(["casa", "spezie"]);
  });

  // illeggibile o non un elenco: tutto aperto, che è la dispensa di oggi
  it.each(["{rotto", '{"spezie":true}', '"spezie"', "null"])("«%s» non è un elenco: tutto aperto", (valore) => {
    expect([...loadCollapsed(memoria(valore))]).toEqual([]);
  });

  it("dentro l'elenco si tiene solo quel che è un nome", () => {
    expect([...loadCollapsed(memoria('["spezie", 3, null, "", {"a": 1}]'))]).toEqual(["spezie"]);
  });

  it("senza memoria (dati del sito bloccati) tutto aperto, e scrivere non lancia", () => {
    expect([...loadCollapsed(null)]).toEqual([]);
    expect(() => saveCollapsed(new Set(["spezie"]), null)).not.toThrow();
  });

  it("una memoria che lancia, leggendo o scrivendo, non ferma niente", () => {
    expect([...loadCollapsed(memoriaRotta())]).toEqual([]);
    expect(() => saveCollapsed(new Set(["spezie"]), memoriaRotta())).not.toThrow();
  });
});

describe("saveCollapsed", () => {
  it("scrive l'elenco in ordine, e si rilegge uguale", () => {
    const m = memoria();
    saveCollapsed(new Set(["spezie", "casa"]), m);
    expect(m.getItem(COLLAPSED_KEY)).toBe('["casa","spezie"]');
    expect([...loadCollapsed(m)].sort()).toEqual(["casa", "spezie"]);
  });
});
```

Sono 10 test (2 + 4 + 1 + 1 + 1 nel primo `describe`, 1 nel secondo).

- [ ] **Step 2: Falliscono**

Run: `npx vitest run src/features/pantry/collapsedSections.test.ts`
Expected: FAIL — il modulo `./collapsedSections` non esiste.

- [ ] **Step 3: Il modulo**

Crea `frontend/src/features/pantry/collapsedSections.ts`:

```ts
import { useEffect, useState } from "react";
import { sectionOpen } from "./pantryView";

/** Dove si ricordano i reparti chiusi della dispensa (spec S15 §4, deciso da Mattia il
 * 2026-10-07). `localStorage` e non `sessionStorage`, a differenza dei filtri del
 * ricettario e del mondo di S14: chiudere «Spezie» perché non si guardano mai è una
 * disposizione della propria dispensa, come l'ordine delle cartelle, e ritrovarla domani
 * è il punto. Si salvano i **chiusi** e non gli aperti: un reparto nuovo nasce aperto, e
 * chi non ha mai chiuso niente vede la dispensa di sempre. */
export const COLLAPSED_KEY = "spena.dispensa.reparti-chiusi";

const NONE: ReadonlySet<string> = new Set();

/** Il `localStorage`, se si riesce ad aprirlo: già leggerlo può lanciare (dati del sito
 * bloccati), quindi anche l'accesso sta nel try. */
function localStore(): Storage | null {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

/** I reparti chiusi ricordati, o nessuno. Un valore illeggibile vale «tutto aperto»; un
 * elemento che non è un nome si scarta. Un nome che non è un reparto della dispensa di
 * oggi resta e non fa niente: nessun gruppo si chiama così. */
export function loadCollapsed(store: Storage | null = localStore()): ReadonlySet<string> {
  if (store === null) return NONE;
  let saved: unknown;
  try {
    saved = JSON.parse(store.getItem(COLLAPSED_KEY) ?? "[]");
  } catch {
    return NONE;
  }
  if (!Array.isArray(saved)) return NONE;
  return new Set(saved.filter((name): name is string => typeof name === "string" && name !== ""));
}

/** Scrive i reparti chiusi, in ordine. Se non si può (memoria piena o bloccata), lo stato
 * vale lo stesso finché lo schermo è aperto: il ricordo è una comodità, non una
 * condizione. */
export function saveCollapsed(
  collapsed: ReadonlySet<string>,
  store: Storage | null = localStore()
): void {
  if (store === null) return;
  try {
    store.setItem(COLLAPSED_KEY, JSON.stringify([...collapsed].sort()));
  } catch {
    // vedi sopra: niente da fare, e niente da dire
  }
}

/** Lo stesso insieme se `category` ci sta già come si chiede, uno nuovo altrimenti: così
 * React non ridisegna per un tocco che non cambia niente. */
function withMember(set: ReadonlySet<string>, category: string, member: boolean): ReadonlySet<string> {
  if (set.has(category) === member) return set;
  const next = new Set(set);
  if (member) next.add(category);
  else next.delete(category);
  return next;
}

/** Lo stato dei reparti della Dispensa. `filtering` è una ricerca scritta o il riepilogo
 * delle scadenze premuto: aprono i reparti senza salvare (`sectionOpen`). `setOpen` è un
 * gesto dell'utente — il tocco sul titolo, o la voce appena aggiunta (spec S15 §3) — e
 * si salva sempre, anche durante un filtro; chiudere durante un filtro si ricorda anche
 * in `closedWhileFiltering`, finché il filtro resta acceso, o il reparto resterebbe
 * aperto sotto il dito. */
export function useCollapsedSections(filtering: boolean) {
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(() => loadCollapsed());
  const [closedWhileFiltering, setClosedWhileFiltering] = useState<ReadonlySet<string>>(NONE);
  // spento il filtro, quel che si era chiuso durante non conta più: la prossima ricerca
  // riapre ogni reparto che ha un risultato. Si azzera qui, durante il disegno, come fa la
  // Dispensa col riepilogo che sparisce: niente giro con uno stato vecchio
  if (!filtering && closedWhileFiltering.size > 0) setClosedWhileFiltering(NONE);

  useEffect(() => {
    saveCollapsed(collapsed);
  }, [collapsed]);

  return {
    isOpen: (category: string) => sectionOpen(category, { collapsed, filtering, closedWhileFiltering }),
    setOpen: (category: string, open: boolean) => {
      setCollapsed((prev) => withMember(prev, category, !open));
      setClosedWhileFiltering((prev) => withMember(prev, category, !open && filtering));
    },
  };
}
```

- [ ] **Step 4: Passano, e il resto è pulito**

Run: `npx vitest run src/features/pantry/collapsedSections.test.ts && npm run typecheck && npm run lint`
Expected: 10 test PASS; typecheck e lint puliti. Se il lint delle regole di React (`eslint-plugin-react-hooks` 7) segnala la riga che azzera `closedWhileFiltering` durante il disegno, controlla che sia scritta **dentro l'`if`** come sopra (è lo stesso schema di `if (summary === null && expiringOnly) setExpiringOnly(false);` in `PantryScreen.tsx`, che il lint accetta); se la segnala lo stesso, spostala in un `useEffect` su `[filtering]` e scrivilo nel report.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/pantry/collapsedSections.ts frontend/src/features/pantry/collapsedSections.test.ts
git commit -m "feat(dispensa): S15, i reparti chiusi si ricordano nel localStorage, e lo stato dello schermo"
```

---

### Task 3: `Section` apribile

**Files:**
- Modify: `frontend/src/components/ui/icons.ts`
- Modify: `frontend/src/components/ui/Section.tsx` (file intero: nessun piano prima lo tocca, vedi la Preparazione)
- Test: `frontend/src/components/ui/Section.test.tsx` (4 test in fondo al `describe`)

**Interfaces:**
- Consumes: niente dai task prima.
- Produces: `Section` con, oltre a `category`, `title`, `count`, `children`, le props facoltative `collapsed?: boolean` (default `false`), `onToggle?: () => void`, `closedNote?: ReactNode`. Senza `onToggle` il markup è quello di oggi.

- [ ] **Step 1: I test**

1. In cima a `Section.test.tsx` cambia l'import di Testing Library e aggiungi `vi`:
   ```ts
   import { describe, expect, it, vi } from "vitest";
   import { fireEvent, render, screen, within } from "@testing-library/react";
   ```
2. Dentro il `describe("Section", …)`, dopo l'ultimo `it`, aggiungi:

```tsx
  // --- S15: il titolo che apre e chiude ---

  it("senza `onToggle` è la sezione di sempre: nessun pulsante, l'`h2` col solo nome", () => {
    render(
      <Section category="latticini" count={3}>
        <p>Latte</p>
      </Section>
    );
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByRole("heading", { level: 2, name: "Latticini" })).toBeInTheDocument();
  });

  it("con `onToggle` il titolo intero è un pulsante dentro l'`h2`, che controlla il contenuto", () => {
    const onToggle = vi.fn();
    render(
      <Section category="latticini" count={3} onToggle={onToggle}>
        <p>Latte</p>
      </Section>
    );
    const heading = screen.getByRole("heading", { level: 2 });
    const button = within(heading).getByRole("button");
    // quadratino, nome, numero e chevron: tutto dentro il pulsante
    expect(button).toHaveAccessibleName(/^Latticini\s+3$/);
    expect(button.querySelector("[data-dept-badge]")).not.toBeNull();
    expect(button.querySelector(".tabler-icon-chevron-down")).not.toBeNull();
    // `Array.from`: la libreria del progetto è `DOM` senza `DOM.Iterable`, e un `NodeList`
    // non si scorre con `for…of`
    for (const svg of Array.from(button.querySelectorAll("svg"))) {
      expect(svg.closest("[aria-hidden=true]")).not.toBeNull();
    }
    expect(button).toHaveAttribute("aria-expanded", "true");
    const content = document.getElementById(button.getAttribute("aria-controls")!);
    expect(content).toHaveTextContent("Latte");
    expect(content).not.toHaveAttribute("hidden");
    fireEvent.click(button);
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("chiusa: il contenuto ha `hidden`, la regione tiene il nome del reparto, il titolo porta la nota", () => {
    render(
      <Section category="latticini" count={3} collapsed onToggle={() => {}} closedNote="1 finito">
        <p>Latte</p>
      </Section>
    );
    // il nome della regione è il solo reparto: chi la cerca per nome la trova chiusa e aperta
    const region = screen.getByRole("region", { name: "Latticini" });
    const button = within(region).getByRole("button");
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button).toHaveAccessibleName(/^Latticini\s+3\s+·\s+1 finito$/);
    expect(button.querySelector(".tabler-icon-chevron-right")).not.toBeNull();
    expect(document.getElementById(button.getAttribute("aria-controls")!)).toHaveAttribute("hidden");
    // fuori dalla pagina accessibile, quindi anche dall'ordine del Tab
    expect(screen.queryByText("Latte")).not.toBeVisible();
  });

  it("aperta, la nota non c'è: le righe sono lì sotto", () => {
    render(
      <Section category="latticini" count={3} collapsed={false} onToggle={() => {}} closedNote="1 finito">
        <p>Latte</p>
      </Section>
    );
    expect(screen.queryByText("1 finito")).toBeNull();
    expect(screen.getByRole("button")).toHaveAccessibleName(/^Latticini\s+3$/);
  });
```

- [ ] **Step 2: Falliscono**

Run: `npx vitest run src/components/ui/Section.test.tsx`
Expected: il primo dei quattro passa già (è il comportamento di oggi, e resta: è la guardia per Lista e Sistema la spesa); gli altri tre FAIL (nessun pulsante). Typecheck: `onToggle`, `collapsed`, `closedNote` non sono props di `Section`.

- [ ] **Step 3: Le icone**

In `frontend/src/components/ui/icons.ts`, subito dopo la riga
```ts
export { IconShoppingCartPlus, IconCalendarEvent } from "@tabler/icons-react";
```
(com'è sul ramo: se un piano prima l'ha allungata, subito dopo di lei), aggiungi — **solo se la Preparazione non li ha trovati già esportati**:
```ts
// dispensa, i reparti che si aprono e si chiudono (S15): giù aperto, a destra chiuso
export { IconChevronDown, IconChevronRight } from "@tabler/icons-react";
```

- [ ] **Step 4: `Section`**

Sostituisci `frontend/src/components/ui/Section.tsx` con:

```tsx
import { useId, type ReactNode } from "react";
import { departmentStyle, TINT_CLASSES } from "./departments";
import { IconChevronDown, IconChevronRight } from "./icons";
import { capitalizeFirst } from "../../lib/text";

/** Un reparto: la scheda bianca con il quadratino colorato, il nome e il conteggio
 * (spec T3 §2, presa dalla direzione «Vivace»). Dentro, le righe non hanno linee fra
 * loro — deciso da Mattia: lo spazio basta a separarle, e la sezione resta un blocco
 * solo. Chi la usa passa righe che portano il proprio spazio verticale.
 *
 * Con `onToggle` il titolo diventa il pulsante che apre e chiude il reparto (spec S15
 * §2): tutto il titolo — quadratino, nome, numero, chevron — dentro l'`h2`, con
 * `aria-expanded` e `aria-controls`, lo schema ARIA dell'accordion. Chiuso, il contenuto
 * ha `hidden`: le sue tacche e le sue ✕ escono anche dall'ordine del Tab. `closedNote` è
 * quel che il titolo chiuso dice oltre al numero; lo scrive chi usa la sezione, perché la
 * sezione non sa cosa sia una voce. Nessuna animazione: a 375 px un'altezza che si apre
 * sposta il resto sotto il dito. Senza `onToggle` è la sezione di sempre: la Lista e
 * Sistema la spesa non si chiudono (spec S15 §7). */
export function Section({
  category,
  title,
  count,
  collapsed = false,
  onToggle,
  closedNote,
  children,
}: {
  category: string | null;
  title?: string;
  count?: number;
  collapsed?: boolean;
  onToggle?: () => void;
  closedNote?: ReactNode;
  children: ReactNode;
}) {
  const headingId = useId();
  const contentId = useId();
  const { icon: Icon, tint } = departmentStyle(category);
  const name = title ?? (category ? capitalizeFirst(category) : "Senza reparto");
  const badge = (
    <span
      data-dept-badge
      aria-hidden="true"
      className={`flex size-7 shrink-0 items-center justify-center rounded-lg ${TINT_CLASSES[tint]}`}
    >
      <Icon className="size-4" stroke={1.8} />
    </span>
  );

  if (onToggle === undefined) {
    return (
      <section aria-labelledby={headingId} className="overflow-hidden rounded-2xl bg-card">
        <div className="flex items-center gap-2.5 px-3 pt-3 pb-1.5">
          {badge}
          <h2 id={headingId} className="flex-1 text-sm font-semibold">
            {name}
          </h2>
          {count !== undefined && <span className="text-xs text-ink-faint">{count}</span>}
        </div>
        <div className="px-3 pb-2">{children}</div>
      </section>
    );
  }

  const Chevron = collapsed ? IconChevronRight : IconChevronDown;
  const note = collapsed && closedNote ? closedNote : null;
  return (
    // la regione si chiama col solo nome del reparto («Latticini»), aperta e chiusa: il
    // pulsante, e con lui l'`h2`, si chiama col titolo intero («Latticini 2 · 1 finito»)
    <section aria-labelledby={headingId} className="overflow-hidden rounded-2xl bg-card">
      <h2 className="text-sm font-semibold">
        <button
          type="button"
          aria-expanded={!collapsed}
          aria-controls={contentId}
          onClick={onToggle}
          // il contorno del fuoco sta dentro: la sezione ha `overflow-hidden`, e quello di
          // base, 2 px fuori, verrebbe tagliato sui tre lati
          className={`flex min-h-11 w-full items-center gap-2.5 px-3 text-left focus-visible:-outline-offset-2 ${
            collapsed ? "py-3" : "pt-3 pb-1.5"
          }`}
        >
          {badge}
          {/* il numero, e chiuso la nota, a destra del nome; quando non ci stanno vanno a
              capo sotto il nome, piccoli (spec S15 §2). Lo spazio fra i due `span` non si
              vede in un contenitore flex, ma tiene separate le parole nel nome accessibile */}
          <span className="flex min-w-0 flex-1 flex-wrap items-baseline justify-between gap-x-2">
            <span id={headingId}>{name}</span>{" "}
            <span className="text-xs font-normal text-ink-faint">
              {count !== undefined && <span>{count}</span>}
              {count !== undefined && note !== null && " · "}
              {note}
            </span>
          </span>
          <Chevron aria-hidden="true" className="size-5 shrink-0 text-ink-faint" stroke={1.8} />
        </button>
      </h2>
      <div id={contentId} hidden={collapsed} className="px-3 pb-2">
        {children}
      </div>
    </section>
  );
}
```

- [ ] **Step 5: Passano, e Lista e Sistema la spesa non se ne accorgono**

Run:
```bash
npx vitest run src/components/ui/Section.test.tsx src/features/shopping-list src/features/stocking
npm run typecheck && npm run lint
```
Expected: `Section.test.tsx` tutto PASS (4 test in più); i test di Lista e Sistema la spesa passano senza modifiche; typecheck e lint puliti.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ui/icons.ts frontend/src/components/ui/Section.tsx frontend/src/components/ui/Section.test.tsx
git commit -m "feat(ui): S15, Section apribile — il titolo intero è il pulsante, chiusa dice il numero e la nota"
```

---

### Task 4: La Dispensa — reparti che si chiudono, si ricordano, e che ricerca e riepilogo aprono

**Files:**
- Modify: `frontend/src/features/pantry/PantryScreen.tsx`
- Test: `frontend/src/features/pantry/PantryScreen.test.tsx` (un `describe` nuovo in fondo al file)

**Interfaces:**
- Consumes: `useCollapsedSections` (Task 2); `attentionCounts`, `finishedText`, `expiringText` (Task 1); `Section` con `collapsed`, `onToggle`, `closedNote` (Task 3).
- Produces: in `PantryScreen`, la costante `filtering` e l'oggetto `sections` (`{ isOpen, setOpen }`), che il Task 5 usa.

Leggi `PantryScreen.tsx` e `PantryScreen.test.tsx` com'è sul ramo prima di cambiarli: S3 ha rifatto l'ingresso diretto, S12 le righe, S14 ha aggiunto il mondo (stato, selettore, e un filtro in più nella costruzione di `visible`). Le ancore qui sotto sono quelle che quei piani non hanno ragione di cambiare; se una non c'è più com'è scritta, trova il punto equivalente e scrivilo nel report.

- [ ] **Step 1: I test**

1. In cima a `PantryScreen.test.tsx`, nell'import da `vitest`, aggiungi `afterEach` e `beforeEach` a quel che c'è già (per esempio `import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";`).
2. In fondo al file, **fuori** dal `describe("PantryScreen", …)` di oggi, aggiungi:

```tsx
// --- S15: i reparti che si aprono e si chiudono ---

const CHIUSI = "spena.dispensa.reparti-chiusi";

/** I reparti chiusi che la Dispensa ha salvato, in ordine. */
function chiusiSalvati(): string[] {
  return (JSON.parse(localStorage.getItem(CHIUSI) ?? "[]") as string[]).sort();
}

/** Il nome del titolo di un reparto, con gli spazi che il calcolo del nome accessibile
 * mette o non mette fra un elemento e l'altro: «Latticini 2 · 1 finito». */
function titolo(testo: string): RegExp {
  return new RegExp(`^${testo.split(" ").join("\\s+")}$`);
}

/** Il pulsante del titolo di un reparto: il primo pulsante della sua regione, che si
 * chiama col solo nome del reparto, aperta e chiusa. Non per nome del pulsante: «Casa»
 * è anche un mondo di S14. */
function reparto(nome: string): HTMLElement {
  return within(screen.getByRole("region", { name: nome })).getAllByRole("button")[0];
}

describe("PantryScreen, i reparti che si chiudono (S15)", () => {
  beforeEach(() => {
    localStorage.clear();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("toccare il titolo chiude il reparto e lo ricorda; chiuso dice quante voci ha e quali chiedono attenzione", async () => {
    const rows = [
      { ...ITEMS[0], status: "finished" },
      { ...ITEMS[1], expires_on: "2026-09-29", expiry: "soon" },
      ITEMS[2],
    ];
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [rows, 200]));
    renderScreen();
    await screen.findByText("Total 0%");
    const latticini = reparto("Latticini");
    expect(latticini).toHaveAttribute("aria-expanded", "true");
    // aperto, il titolo dice il numero e basta: le righe sono lì sotto
    expect(latticini).toHaveAccessibleName(titolo("Latticini 2"));

    fireEvent.click(latticini);
    expect(latticini).toHaveAttribute("aria-expanded", "false");
    expect(latticini).toHaveAccessibleName(titolo("Latticini 2 · 1 finito · 1 in scadenza"));
    // le righe chiuse escono dalla pagina accessibile, tacche e ✕ comprese
    expect(screen.queryByRole("link", { name: "Yogurt greco" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Togli Total 0% dalla dispensa" })).toBeNull();
    // gli altri reparti non si toccano
    expect(screen.getByRole("link", { name: "Mela" })).toBeDefined();
    expect(chiusiSalvati()).toEqual(["latticini"]);

    fireEvent.click(latticini);
    expect(latticini).toHaveAttribute("aria-expanded", "true");
    expect(screen.getAllByRole("link", { name: "Yogurt greco" })).toHaveLength(2);
    expect(chiusiSalvati()).toEqual([]);
  });

  it("un reparto chiuso resta chiuso tornando in dispensa", async () => {
    localStorage.setItem(CHIUSI, JSON.stringify(["frutta"]));
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]));
    renderScreen();
    await screen.findByText("Total 0%");
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "false");
    expect(reparto("Frutta")).toHaveAccessibleName(titolo("Frutta 1 · 1 in scadenza"));
    expect(screen.queryByRole("link", { name: "Mela" })).toBeNull();
    expect(reparto("Latticini")).toHaveAttribute("aria-expanded", "true");
  });

  it("una ricerca apre i reparti chiusi che hanno un risultato, senza cambiare quel che è salvato", async () => {
    localStorage.setItem(CHIUSI, JSON.stringify(["frutta", "latticini"]));
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]));
    renderScreen();
    await screen.findByRole("region", { name: "Frutta" });
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "false");

    const barra = screen.getByLabelText("Cerca o aggiungi in dispensa");
    fireEvent.change(barra, { target: { value: "mel" } });
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: "Mela" })).toBeDefined();
    expect(chiusiSalvati()).toEqual(["frutta", "latticini"]);

    // cancellata la ricerca, la dispensa torna com'era stata lasciata
    fireEvent.change(barra, { target: { value: "" } });
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "false");
    expect(reparto("Latticini")).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("link", { name: "Mela" })).toBeNull();
  });

  it("il riepilogo delle scadenze premuto apre i reparti con una scadenza, senza salvare", async () => {
    localStorage.setItem(CHIUSI, JSON.stringify(["frutta"]));
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]));
    renderScreen();
    const riepilogo = await screen.findByRole("button", { name: "1 in scadenza questa settimana" });
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "false");

    fireEvent.click(riepilogo);
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: "Mela" })).toBeDefined();
    expect(chiusiSalvati()).toEqual(["frutta"]);

    fireEvent.click(riepilogo);
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "false");
  });

  it("durante una ricerca il titolo chiude e apre per davvero, e si salva", async () => {
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]));
    renderScreen();
    await screen.findByText("Total 0%");
    const barra = screen.getByLabelText("Cerca o aggiungi in dispensa");

    fireEvent.change(barra, { target: { value: "mel" } });
    fireEvent.click(reparto("Frutta"));
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "false");
    expect(chiusiSalvati()).toEqual(["frutta"]);
    // la stessa ricerca, una lettera in più: quel che si è appena chiuso resta chiuso
    // (decisione 1 di Mattia del 2026-10-09: si rispetta il gesto finché la ricerca non si cancella)
    fireEvent.change(barra, { target: { value: "mela" } });
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "false");
    // riaperto a mano durante la ricerca: aperto, e salvato aperto
    fireEvent.click(reparto("Frutta"));
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "true");
    expect(chiusiSalvati()).toEqual([]);
    // cancellata la ricerca vale il salvato
    fireEvent.change(barra, { target: { value: "" } });
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "true");

    // chiuso senza filtro, una ricerca nuova lo riapre come ogni reparto con un risultato
    fireEvent.click(reparto("Frutta"));
    fireEvent.change(barra, { target: { value: "mel" } });
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "true");
    fireEvent.change(barra, { target: { value: "" } });
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "false");
  });

  it("con lo spazio del sito bloccato i reparti partono aperti, e si chiudono lo stesso", async () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloccato");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloccato");
    });
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]));
    renderScreen();
    await screen.findByText("Total 0%");
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(reparto("Frutta"));
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("link", { name: "Mela" })).toBeNull();
  });
});
```

Se sul ramo un piano prima di questo ha aggiunto a `PantryScreen` qualcos'altro che legge o scrive una memoria del sito (per esempio il mondo di S14 nella `sessionStorage`) e l'ultimo test fallisce per un'eccezione che nasce lì e non in `collapsedSections.ts`, non è un difetto di S15 e non va aggirato qui: non disattivare né indebolire il test, fai commit del resto del Task 4, scrivi nel report la riga che lancia, e segna il Task 4 `bloccato` in `next-steps.md` del ramo con la domanda per Mattia («l'involucro di S14 lancia con lo spazio del sito bloccato: lo si corregge sul ramo di S14 o su quello di S15?»). Un involucro che lancia è un vicolo cieco vero. Poi prosegui col Task 5.

- [ ] **Step 2: Falliscono**

Run: `npx vitest run src/features/pantry/PantryScreen.test.tsx`
Expected: i sei test nuovi FAIL (nessun pulsante nei titoli: `getAllByRole("button")[0]` trova la prima tacca o la ✕, e `aria-expanded` manca); tutti i test di oggi PASS.

- [ ] **Step 3: La Dispensa**

In `frontend/src/features/pantry/PantryScreen.tsx`:

1. **Gli import.** Nell'import da `"react"` aggiungi `type ReactNode` (per esempio `import { useCallback, useState, type ReactNode } from "react";`, tenendo quel che il ramo vi ha già). Nell'import da `"./pantryView"` aggiungi, senza togliere niente, `attentionCounts`, `expiringText`, `finishedText`. Sotto gli import da `./pantryView` e `./api` aggiungi:
   ```ts
   import { useCollapsedSections } from "./collapsedSections";
   ```
2. **La nota del titolo chiuso.** Subito prima di `export function PantryScreen() {` aggiungi:
   ```tsx
   /** Quel che un reparto chiuso non deve nascondere (spec S15 §2): le voci finite, che
    * hanno il loro «In lista» da toccare, e quelle in scadenza, che hanno un tempo che
    * corre. In parole, e non con un pallino: un colore solo non dice niente a chi non lo
    * distingue. Gli stessi colori delle righe: il «Finito» e la scadenza di `PantryRow`. */
   function attentionNote(rows: PantryItem[]): ReactNode {
     const { finished, expiring } = attentionCounts(rows);
     if (finished === 0 && expiring === 0) return null;
     return (
       <>
         {finished > 0 && <span className="font-medium text-finished">{finishedText(finished)}</span>}
         {finished > 0 && expiring > 0 && " · "}
         {expiring > 0 && <span className="font-medium text-expiry">{expiringText(expiring)}</span>}
       </>
     );
   }
   ```
   (`PantryItem` è già importato dal file per tipo; se sul ramo non lo fosse, aggiungilo all'import di `../../domain/types`.)
3. **Lo stato dei reparti.** Subito dopo la riga
   ```ts
   const [expiringOnly, setExpiringOnly] = useState(false);
   ```
   aggiungi:
   ```ts
   // S15: ricerca e riepilogo sono filtri, e aprono i reparti che hanno un risultato senza
   // salvare niente; il mondo di S14 no, è una vista. `matchesQuery` ignora gli spazi ai
   // lati, e così questa condizione
   const filtering = query.trim() !== "" || expiringOnly;
   const sections = useCollapsedSections(filtering);
   ```
   (Se sul ramo `query` o `expiringOnly` sono dichiarati più giù di quella riga, metti le due costanti subito dopo la dichiarazione che viene per ultima fra le due. Il hook va chiamato sempre, mai dentro un `if`.)
4. **Le sezioni.** Nel JSX, dentro `groupForDisplay(…).map(([category, rows]) => (`, sostituisci il tag d'apertura
   ```tsx
   <Section key={category} category={category} count={rows.length}>
   ```
   con
   ```tsx
   <Section
     key={category}
     category={category}
     count={rows.length}
     collapsed={!sections.isOpen(category)}
     onToggle={() => sections.setOpen(category, !sections.isOpen(category))}
     closedNote={attentionNote(rows)}
   >
   ```
   Il resto della `map` (l'`<ul>` e le `PantryRow`, come le hanno lasciate S3 e S12) non si tocca.

- [ ] **Step 4: Passano**

Run:
```bash
npx vitest run src/features/pantry
npm run typecheck && npm run lint
```
Expected: tutti PASS, i sei test nuovi compresi, e nessun test di oggi cambiato; typecheck e lint puliti.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/pantry/PantryScreen.tsx frontend/src/features/pantry/PantryScreen.test.tsx
git commit -m "feat(dispensa): S15, i reparti si chiudono toccando il titolo, si ricordano, e ricerca e riepilogo li aprono senza salvare"
```

---

### Task 5: La voce aggiunta apre il suo reparto; il mondo non apre né chiude

**Files:**
- Modify: `frontend/src/features/pantry/PantryScreen.tsx`
- Test: `frontend/src/features/pantry/PantryScreen.test.tsx` (due test nel `describe` del Task 4)

**Interfaces:**
- Consumes: `sections.setOpen(category: string, open: boolean)` (Task 4); i punti in cui S3 porta in vista una voce appena entrata, `setRevealId(<voce creata>.id)`, dove `<voce creata>` è il `PantryItem` che la `POST /api/v1/pantry` restituisce; il selettore dei mondi di S14.
- Produces: niente per altri task.

**Perché nel momento del `setRevealId` e non quando la riga arriva:** la riga nuova si porta in vista nell'effetto di `PantryRow` (`revealAtTop`), che React esegue **prima** degli effetti di `PantryScreen`. Se il reparto si aprisse solo dopo, in un effetto della schermata, la riga verrebbe fatta scorrere mentre è ancora dentro un contenuto `hidden`, cioè da nessuna parte. Aprendolo nello stesso gesto che accende `revealId`, quando la riga arriva col ricaricamento il reparto è già aperto.

- [ ] **Step 1: I test**

Prima di scrivere il primo test, **leggi sul ramo il test di `PantryScreen.test.tsx` che fa entrare una voce dalla Dispensa e controlla che venga portata in vista una volta sola** (su `master` è «il + apre l'aggiunta con il testo della barra, e scegliere mette in dispensa»; S3 l'ha rifatto per la scheda di conferma: cercalo con `grep -n "scrollIntoView" frontend/src/features/pantry/PantryScreen.test.tsx`). Il test qui sotto è scritto col flusso di `master`, fra i due commenti `--- l'aggiunta ---` e `--- fine dell'aggiunta ---`: **sostituisci quel tratto con i passi esatti del test di S3** (stessi tocchi, stesse risposte finte di `fetch`, stesso avviso atteso), facendo entrare la mela (`ITEMS[2]`, reparto `frutta`) con id `p9`. Tutto il resto del test, e le asserzioni dopo, restano come sono scritte qui.

Dentro il `describe("PantryScreen, i reparti che si chiudono (S15)", …)` del Task 4, dopo l'ultimo `it`, aggiungi:

```tsx
  it("la voce aggiunta in un reparto chiuso lo apre prima di portarla in vista, e lo salva aperto", async () => {
    localStorage.setItem(CHIUSI, JSON.stringify(["frutta"]));
    const created = { ...ITEMS[2], id: "p9" };
    let added = false;
    stubRoutedFetch((path, init) => {
      if (path.includes("/shopping-list")) return [[], 200];
      if (path.includes("/ingredients")) return [[MELA], 200];
      if (init?.method === "POST") {
        added = true;
        return [created, 201];
      }
      return [added ? [...ITEMS, created] : ITEMS, 200];
    });
    // per ogni chiamata, se la riga portata in vista stava dentro un contenuto chiuso:
    // `this` è l'elemento. Uno spy e non un'assegnazione (vedi il test dell'aggiunta)
    const dentroUnChiuso: boolean[] = [];
    vi.spyOn(Element.prototype, "scrollIntoView").mockImplementation(function (this: Element) {
      dentroUnChiuso.push(this.closest("[hidden]") !== null);
    });
    renderScreen();
    await screen.findByText("Total 0%");
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "false");

    // --- l'aggiunta (com'è su master: sostituisci con i passi del test di S3 sul ramo) ---
    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "mel" } });
    fireEvent.click(screen.getByRole("button", { name: "Aggiungi in dispensa" }));
    fireEvent.click(await screen.findByRole("option", { name: "Mela" }));
    expect(await screen.findByText("In dispensa: Mela")).toBeDefined();
    // --- fine dell'aggiunta ---

    await waitFor(() => expect(dentroUnChiuso).toHaveLength(1));
    // la riga era a video quando ci si è andati: il reparto si era già aperto
    expect(dentroUnChiuso).toEqual([false]);
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "true");
    expect(chiusiSalvati()).toEqual([]);
  });

  it("il mondo scelto (S14) non apre e non chiude i reparti: nasconde quelli dell'altro mondo", async () => {
    localStorage.setItem(CHIUSI, JSON.stringify(["frutta"]));
    const detersivo = {
      ...ITEMS[2],
      id: "p8",
      ingredient_id: "i8",
      ingredient_name: "detersivo per i piatti",
      ingredient_category: "casa",
      ingredient_kind: "non_food",
      expires_on: null,
      expiry: null,
    };
    const rows = [...ITEMS.map((row) => ({ ...row, ingredient_kind: "food" })), detersivo];
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [rows, 200]));
    renderScreen();
    await screen.findByText("Total 0%");

    fireEvent.click(screen.getByRole("button", { name: "Casa" }));
    // un reparto del cibo sotto «Casa» non c'è, non è chiuso
    expect(screen.queryByRole("region", { name: "Frutta" })).toBeNull();
    expect(reparto("Casa")).toHaveAttribute("aria-expanded", "true");

    fireEvent.click(screen.getByRole("button", { name: "Cibo" }));
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(screen.getByRole("button", { name: "Tutto" }));
    expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "false");
    expect(chiusiSalvati()).toEqual(["frutta"]);
  });
```

Il secondo test usa il selettore di S14 coi nomi della sua spec («Tutto», «Cibo», «Casa», pulsanti con `aria-pressed`). Se sul ramo il selettore si tocca in un altro modo, prendi il modo dai test di S14 in questo stesso file e cambia **solo** quei tre `fireEvent.click`. Se la Preparazione ha trovato `PantryItem` senza `ingredient_kind`, **non scrivere questo test** e scrivilo nel report.

- [ ] **Step 2: Il primo fallisce, il secondo passa già**

Run: `npx vitest run src/features/pantry/PantryScreen.test.tsx`
Expected: il test della voce aggiunta FAIL (`dentroUnChiuso` è `[true]`, oppure il reparto resta chiuso: la riga arriva in un contenuto `hidden`); quello del mondo PASS già, perché S14 decide quali reparti ci sono e il Task 4 non lo ha toccato — è la guardia che resti così.

- [ ] **Step 3: Il reparto della voce aggiunta si apre, e si salva aperto**

In `PantryScreen.tsx` trova ogni punto in cui una voce appena entrata viene portata in vista:

```bash
grep -n "setRevealId(" frontend/src/features/pantry/PantryScreen.tsx
```

A ogni chiamata **che accende** `revealId` con l'id di una voce creata — su `master` è una sola, `setRevealId(created.id);` nell'`onSuccess` della mutazione `add`; con S3 possono essere una o due (lo sfuso dal +, la scheda di conferma, la scansione in serie) — aggiungi, sulla riga subito dopo:

```ts
// S15: la voce entra in un reparto forse chiuso. Si apre adesso, insieme a `revealId`, e
// si salva aperto (l'utente ha appena messo lì qualcosa): `PantryRow` la porta in vista
// nel suo effetto, che React esegue prima di quelli di questo schermo, quindi quando la
// riga arriva il suo reparto deve essere già aperto
sections.setOpen(created.ingredient_category, true);
```

sostituendo `created` col nome che la voce creata ha in quel punto. **Non** toccare `useCallback(() => setRevealId(null), [])`. Se in un punto c'è solo l'id e non la voce creata (il `PantryItem` della risposta della `POST`), fermati: segna il Task 5 `bloccato` in `next-steps.md` del ramo con la diagnosi («in `<funzione>` la voce creata non arriva fino a `setRevealId`: il reparto non si può aprire senza il suo `ingredient_category`») e passa al Task 6.

- [ ] **Step 4: Passano**

Run:
```bash
npx vitest run src/features/pantry
npm run typecheck && npm run lint
```
Expected: tutti PASS; typecheck e lint puliti.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/pantry/PantryScreen.tsx frontend/src/features/pantry/PantryScreen.test.tsx
git commit -m "feat(dispensa): S15, la voce aggiunta apre il suo reparto prima di andarci, e lo salva aperto; il mondo non apre né chiude"
```

---

### Task 6: L'e2e — il reparto chiuso nel browser vero, a 375×812, nei due temi

jsdom non calcola il CSS (quarta lezione di `CLAUDE.md`): che il titolo sia davvero un bersaglio da 44 px largo quanto la scheda, che la nota a 375 px non faccia scorrere di lato, che «finito» e «in scadenza» siano i due token e si leggano sul fondo `card` in chiaro e in scuro, e che il reparto chiuso sopravviva a un ricaricamento, lo dice solo un browser. Il seme non popola la dispensa: le due voci si creano con `page.request`, come fa il test del riepilogo delle scadenze in questo stesso file, e si archiviano nel `finally`. L'ingresso dalla barra non serve qui (lo prova S3), e la voce aggiunta che apre il reparto la prova il Task 5.

**Files:**
- Modify: `frontend/e2e/style.spec.ts` (una prova in fondo, in un blocco proprio)

- [ ] **Step 1: La prova**

In fondo a `frontend/e2e/style.spec.ts` aggiungi (il `beforeEach` del file ha già fatto l'accesso; `fermo`, `testiIlleggibili`, `contrastoAVideo`, `tokenDelTema` e `tokenDelTemaScuro` sono già definiti più sopra nel file). Se la Preparazione ha trovato `orata` o `calamaro` già usati, sostituiscili qui con i due nomi scelti, ovunque compaiano:

```ts
// --- S15: i reparti della dispensa che si aprono e si chiudono ---

test("S15 a 375px: un reparto chiuso dice quante voci ha e cosa chiede attenzione, si legge nei due temi, e ricerca e riepilogo lo aprono senza salvarlo", async ({
  page,
}) => {
  // il `beforeEach` tocca «Entra» ma non aspetta la risposta: la prima cosa qui è una
  // `page.request`, quindi l'attesa va messa a mano (vedi il test del riepilogo)
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
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
  /** I reparti chiusi che la Dispensa ha salvato nel `localStorage`. */
  const chiusiSalvati = async () =>
    JSON.parse(
      await page.evaluate<string>("localStorage.getItem('spena.dispensa.reparti-chiusi') ?? '[]'")
    ) as string[];

  // Due voci nel reparto «pesce», che nessun altro file della suite nomina: l'orata finita,
  // il calamaro che scade fra due giorni. Questo file non lascia niente dietro di sé:
  // si archiviano nel `finally`
  const creati: string[] = [];
  try {
    const orata = await page.request.post("/api/v1/pantry", {
      data: { ingredient_id: await ingrediente("orata"), status: "finished" },
    });
    expect(orata.ok()).toBe(true);
    creati.push(((await orata.json()) as { id: string }).id);
    const calamaro = await page.request.post("/api/v1/pantry", {
      data: { ingredient_id: await ingrediente("calamaro") },
    });
    expect(calamaro.ok()).toBe(true);
    const calamaroId = ((await calamaro.json()) as { id: string }).id;
    creati.push(calamaroId);
    const fraDueGiorni = new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
    const scritta = await page.request.patch(`/api/v1/pantry/${calamaroId}`, {
      data: { expires_on: fraDueGiorni },
    });
    expect(scritta.ok()).toBe(true);

    await page.getByRole("link", { name: "Dispensa" }).click();
    const pesce = page.getByRole("region", { name: "Pesce" });
    const titolo = pesce.getByRole("button", { name: /^Pesce\b/ });
    const rigaOrata = pesce.locator("li", { hasText: "orata" });
    const rigaCalamaro = pesce.locator("li", { hasText: "calamaro" });

    // aperto, come per chi non ha mai chiuso niente; il titolo intero è il bersaglio
    await expect(titolo).toHaveAttribute("aria-expanded", "true");
    await expect(rigaOrata).toBeVisible();
    const box = await titolo.boundingBox();
    const scheda = await pesce.boundingBox();
    expect(box!.height).toBeGreaterThanOrEqual(44);
    expect(box!.width, "il titolo intero è il pulsante").toBeGreaterThanOrEqual(scheda!.width - 1);

    // chiuso: le righe spariscono, il titolo dice il numero e cosa chiede attenzione
    await titolo.click();
    await expect(titolo).toHaveAttribute("aria-expanded", "false");
    await expect(rigaOrata).toBeHidden();
    await expect(titolo).toHaveAccessibleName(/^Pesce\s+2\s+·\s+1 finito\s+·\s+1 in scadenza$/);
    expect(await chiusiSalvati()).toEqual(["pesce"]);
    const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
    const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
    expect(scrollWidth, "il titolo chiuso fa scorrere di lato").toBeLessThanOrEqual(clientWidth);

    // i due colori sono quelli delle righe, e si leggono sul fondo della scheda, nei due temi
    const finito = titolo.getByText("1 finito", { exact: true });
    const inScadenza = titolo.getByText("1 in scadenza", { exact: true });
    for (const tema of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: tema });
      await fermo(page);
      expect(await testiIlleggibili(page), `dispensa col reparto chiuso, tema ${tema}`).toEqual([]);
      const token = tema === "light" ? tokenDelTema : tokenDelTemaScuro;
      const misuraFinito = await contrastoAVideo(finito);
      expect(misuraFinito.colore, `«1 finito», tema ${tema}`).toBe(token("finished"));
      expect(misuraFinito.rapporto).toBeGreaterThanOrEqual(4.5);
      const misuraScadenza = await contrastoAVideo(inScadenza);
      expect(misuraScadenza.colore, `«1 in scadenza», tema ${tema}`).toBe(token("expiry"));
      expect(misuraScadenza.rapporto).toBeGreaterThanOrEqual(4.5);
    }
    await page.emulateMedia({ colorScheme: "light" });

    // ricordato: ricaricata la pagina, è ancora chiuso
    await page.reload();
    await expect(titolo).toHaveAttribute("aria-expanded", "false");

    // la ricerca lo apre, e non lo salva aperto; cancellata, torna chiuso
    const barra = page.getByLabel("Cerca o aggiungi in dispensa");
    await barra.fill("orat");
    await expect(titolo).toHaveAttribute("aria-expanded", "true");
    await expect(rigaOrata).toBeVisible();
    expect(await chiusiSalvati()).toEqual(["pesce"]);
    await barra.fill("");
    await expect(titolo).toHaveAttribute("aria-expanded", "false");

    // il riepilogo delle scadenze premuto lo apre allo stesso modo, e spento lo richiude
    const riepilogo = page.getByRole("button", { name: /in scadenza questa settimana/ });
    await riepilogo.click();
    await expect(titolo).toHaveAttribute("aria-expanded", "true");
    await expect(rigaCalamaro).toBeVisible();
    await riepilogo.click();
    await expect(titolo).toHaveAttribute("aria-expanded", "false");
    expect(await chiusiSalvati()).toEqual(["pesce"]);
  } finally {
    for (const id of creati) {
      const tolta = await page.request.patch(`/api/v1/pantry/${id}`, { data: { archived: true } });
      expect.soft(tolta.ok(), `archiviare la voce ${id}`).toBe(true);
    }
  }
});
```

Note per chi la esegue:
- Se `contrastoAVideo` o `tokenDelTemaScuro` sul ramo hanno un'altra firma (il piano del tema scuro può averli toccati), usali come li usano le prove del tema scuro e scrivilo nel report.
- Se una delle misure del contrasto dà un testo del titolo chiuso sotto 4,5:1, **non cambiare token**: scrivi nel report quale testo, su quale fondo, in quale tema e con quale rapporto, e segna il task `bloccato` — un colore si decide di giorno.

- [ ] **Step 2: Il tipo del file**

Run (da `frontend/`): `npm run typecheck && npm run lint`
Expected: puliti. `tsc -b` compila anche gli e2e (`tsconfig.node.json`, senza la libreria DOM: per questo la memoria del sito si legge con `page.evaluate` e una stringa).

- [ ] **Step 3: Lo stack e2e, e l'e2e intera**

Dalla radice di `<worktree>`, con i comandi delle Global Constraints: `cp .env.example .env`, `up -d --build --wait`, il seme `--con-ricette`, poi `(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)`.
Expected: tutti verdi, **una prova più del conto e2e di S14** (nel suo report della notte; se non lo trovi, conta le prove con `npx playwright test --list | tail -n 1` sul ramo prima di questo task e aggiungi uno). Annota il numero (`N_e2e`). Le prove di oggi che toccano la Dispensa passano senza modifiche: ogni prova ha il suo contesto del browser, quindi parte con il `localStorage` vuoto e tutti i reparti aperti.

Se una prova fallisce e lascia dati nello stack, prima di rieseguire ricrea lo stack da zero (`down -v`, `up`, seme). Alla fine, sempre:

```bash
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
rm .env
```

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/style.spec.ts
git commit -m "e2e: S15 a 375px — il titolo chiuso da 44, la nota nei due temi, il ricordo dopo un ricaricamento, ricerca e riepilogo che aprono senza salvare"
```

---

### Task 7: I documenti

**Files:**
- Modify: `docs/prossimi-passi.md`
- Modify: `next-steps.md`

Leggi prima i due file com'è sul ramo: i piani prima di questo li hanno aggiornati.

- [ ] **Step 1: La voce S15 in `docs/prossimi-passi.md`**

1. Il titolo `## S15. Reparti della dispensa collassabili **[D]**` diventa `## S15. Reparti della dispensa collassabili **[FATTO <data di oggi> — sul ramo night/s15-reparti-collassabili, non ancora in produzione]**`.
2. In fondo alla voce (dopo il paragrafo che finisce con «altrimenti chiuso sembra vuoto.») aggiungi:
   ```markdown
   **Fatto** (spec `docs/superpowers/specs/2026-10-06-reparti-collassabili-bozza.md`, piano
   `docs/superpowers/plans/2026-10-08-s15-reparti-collassabili.md`): in Dispensa il titolo
   di ogni reparto — quadratino, nome, numero, chevron — è il pulsante che lo apre e lo
   chiude, dentro l'`h2` (`aria-expanded`, `aria-controls`); chiuso, il contenuto ha
   `hidden` e il titolo dice il numero e, se ci sono, «N finito/finiti» e «N in scadenza»
   (in scadenza e oltre), negli stessi colori delle righe. I reparti chiusi si ricordano nel
   `localStorage` (`spena.dispensa.reparti-chiusi`, l'elenco dei chiusi); una ricerca e il
   riepilogo delle scadenze aprono i reparti con un risultato senza salvare, e cancellati
   torna il salvato; toccare un titolo durante una ricerca chiude o apre per davvero, e si
   salva; la voce aggiunta dall'ingresso diretto apre il suo reparto prima di essere portata
   in vista, e lo salva aperto; il mondo di S14 non apre né chiude. `Section` senza
   `onToggle` è quella di prima: Lista e Sistema la spesa non cambiano. Tre scelte decise
   da Mattia il 2026-10-09: un reparto chiuso durante una ricerca resta chiuso finché la
   ricerca non si cancella; «in scadenza» conta anche le voci oltre la scadenza; un reparto
   chiuso che si svuota e torna, torna chiuso.
   ```
   Sostituisci `<data di oggi>` con la data vera.

- [ ] **Step 2: `next-steps.md`**

1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte)_`.
2. Togli la riga di S15 da «In corso» (l'ha messa lì la Preparazione).
3. In cima a «Fatti (recenti)» aggiungi:
   ```markdown
   - [fatto] <data di oggi> · S15, reparti della dispensa collassabili: il titolo intero apre e chiude, chiuso dice il numero e «N finito» / «N in scadenza», i chiusi si ricordano nel `localStorage`, ricerca e riepilogo aprono senza salvare, la voce aggiunta apre e salva aperto, il mondo non apre né chiude [S15] → branch night/s15-reparti-collassabili (da revisionare)
   ```
4. In cima a «Da fare a mano (solo Mattia)» aggiungi:
   ```markdown
   - [tbd] P3 · Prove sul telefono di S15: il tocco sui titoli dei reparti col pollice, la nota del titolo chiuso a 375 px coi nomi lunghi, e i reparti chiusi che restano chiusi dopo aver chiuso e riaperto l'app installata [S15]
   ```
5. In «Idee» aggiungi:
   ```markdown
   - [idea] P3 · «Chiudi tutto / apri tutto» sui reparti della dispensa, se sul telefono toccarli uno per uno non basta (deciso di no per ora, spec S15 §6.5) [S15]
   - [idea] P3 · Un errore su una riga di un reparto chiuso (una tacca rifiutata dopo averlo chiuso) si vede solo riaprendolo: il titolo chiuso potrebbe dirlo [S15]
   ```
6. Se nella notte sono emerse altre cose da fare fuori da questo piano, aggiungile come `idea` o `tbd` nella sezione giusta, con la voce di `docs/prossimi-passi.md` fra parentesi quadre.

- [ ] **Step 3: Commit**

```bash
git add docs/prossimi-passi.md next-steps.md
git commit -m "docs: S15 fatto sul ramo, le prove sul telefono e due idee"
```

---

### Task 8: La verifica finale, e il report

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

Expected: vitest tutto verde — **`N_vitest` della Preparazione più 35**, cioè 13 (Task 1) + 10 (Task 2) + 4 (Task 3) + 6 (Task 4) + 2 (Task 5), in **`N_file` + 1** file (`collapsedSections.test.ts`); 34 se il test del mondo è stato saltato (Preparazione). Se il numero differisce, scrivi nel report da dove viene la differenza. Typecheck, lint e build puliti. `npx tsc -b --force` perché `node_modules` è condiviso col checkout principale, e con lui il `tsbuildinfo`: `--force` compila davvero tutto.

- [ ] **Step 2: Il backend**

Da `<worktree>/backend`:

```bash
TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_s15 PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Expected: tutto verde, **`N_pytest`** esatto: nessun test nuovo, nessuna riga del backend cambiata.

- [ ] **Step 3: I controlli dalla radice**

```bash
grep -rn "emerald\|neutral-" frontend/src
git diff night/s14-cibo-casa --stat -- backend/ frontend/src/features/shopping-list frontend/src/features/stocking
grep -rn "spena.dispensa.reparti-chiusi" frontend/src | grep -v "\.test\."
git diff night/s14-cibo-casa --stat
```

Expected: vuoto; vuoto; una riga sola, in `frontend/src/features/pantry/collapsedSections.ts`; l'ultimo elenca solo i file della tabella «File toccati» (più `docs/night-reports/` dopo lo Step 5).

- [ ] **Step 4: L'e2e intera**

Con i comandi delle Global Constraints, su uno stack ricreato da zero (`down -v` prima dell'`up`, se ne era rimasto uno di questo ramo). Expected: tutti verdi, `N_e2e` del Task 6. Poi `down -v` e `rm .env`, sempre.

- [ ] **Step 5: Il report**

Nel report della notte (`docs/night-reports/<data>.md`, sul ramo; se il file c'è già perché un piano prima di questo l'ha scritto sul suo ramo, qui sul tuo ramo aggiungi una sezione «S15» senza toccare le altre), per questo piano: il ramo e da dove parte; i conti veri (vitest, pytest, e2e) contro quelli della Preparazione; cosa hanno trovato i controlli della Preparazione sui file già toccati da S3, S12, il tema scuro e S14, e dove le ancore del piano non c'erano più com'erano scritte; i punti di `setRevealId(` a cui il Task 5 si è agganciato; come il test della voce aggiunta fa entrare la voce sul ramo; le scelte prese in autonomia; e le **tre scelte decise da Mattia il 2026-10-09** (un reparto chiuso durante una ricerca resta chiuso finché la ricerca non si cancella; «in scadenza» comprende le voci oltre la scadenza; un reparto chiuso che si svuota e torna, torna chiuso). Poi:

```bash
git add docs/night-reports/
git commit -m "docs: il report della notte per S15"
```

Niente push, niente merge, niente deploy.

## Dopo il deploy (solo Mattia)

Nessuna azione: S15 non tocca i dati né lo schema. Il `localStorage` nasce vuoto su ogni telefono, cioè con la dispensa tutta aperta, com'è oggi.
