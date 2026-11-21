# La serie della scansione e i reparti che il riepilogo lascia aperti: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** in Dispensa, (1) finché il pannello di «Scansiona» è aperto la pagina non scorre più alla riga nuova, e alla chiusura del pannello va in vista l'ultima riga entrata; in serie, su «Cibo» o «Casa», una voce dell'altro mondo lascia il selettore com'è e l'avviso dice dov'è finita (S3 + S14); (2) quando è lo schermo a spegnere il riepilogo delle scadenze (non ha più voci), i reparti che il riepilogo aveva aperto restano aperti a video, senza salvarli, finché non si tocca qualcosa (S15).

**Architecture:** solo frontend, tre file di codice. In `pantryView.ts` tre pezzi puri: `SectionView.held` (i reparti tenuti aperti), `worldSummary` (il riepilogo di un mondo, oggi scritto in linea in `PantryScreen`) ed `enteredNotice` (il testo dell'avviso dopo un ingresso). In `collapsedSections.ts` il hook impara a ricordare quali reparti il riepilogo mostra aperti (`noteFiltered`), a tenerli aperti quando lo schermo lo spegne (`holdFiltered`) e a lasciarli andare al primo gesto (`releaseHold`). In `PantryScreen.tsx` la riga da portare in vista **aspetta** finché la serie è aperta (`pendingReveal`): la stessa `revealId` di oggi, la stessa `settleWorld`, la stessa `PantryRow`; cambia solo quando la si guarda. `DirectEntry`, `ProductResolver`, `PantryRow` e il backend non cambiano.

**Tech Stack:** React 19, TypeScript, TanStack Query 5, Tailwind 4 (token in `@theme`), Vitest + Testing Library (jsdom), Playwright.

**Spec:** le tre bozze, che questo piano aggiorna nel Task 5:
- S3 `docs/superpowers/specs/2026-10-06-ingresso-diretto-bozza.md` (§4.4, §4.5);
- S14 `docs/superpowers/specs/2026-10-06-cibo-casa-bozza.md` (§4);
- S15 `docs/superpowers/specs/2026-10-06-reparti-collassabili-bozza.md` (§3);

e le decisioni di Mattia del 2026-11-18, scritte qui sotto in «Decisioni prese» (1–4). I piani che hanno costruito quel che si tocca: `docs/superpowers/plans/2026-10-08-s3-ingresso-diretto.md`, `2026-10-08-s14-cibo-casa.md`, `2026-10-08-s15-reparti-collassabili.md`. Le righe di `next-steps.md` che questo piano chiude cominciano con «S3, la serie della scansione» e «S15, il riepilogo delle scadenze che si spegne da solo».

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/dispensa-serie-reparti` (`.worktrees/` è già in `.gitignore`), ramo `night/dispensa-serie-reparti`, creato da **`master`**. Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì (o dalla sua `frontend/`), mai dalla radice del checkout principale. Il checkout principale non si tocca: se vi trovi modifiche non committate, sono dell'utente. **Nessun push, nessun merge, nessun deploy. Mai `git stash`. Niente letture o scritture sulla produzione, e mai leggere né copiare il `.env` del checkout principale.**
- **Il backend non cambia.** Nessuna rotta, nessuno schema, nessuna migrazione: niente pytest in questo piano (il backend gira solo dentro lo stack e2e, com'è su `master`).
- **I file che si toccano.** Codice: `frontend/src/features/pantry/pantryView.ts`, `collapsedSections.ts`, `PantryScreen.tsx`. Prove: `pantryView.test.ts`, `PantryScreen.test.tsx`, `frontend/e2e/style.spec.ts`. Documenti (Task 5): le tre bozze qui sopra, `docs/prossimi-passi.md`, `next-steps.md`, il report. **Non si toccano** `DirectEntry.tsx`, `DirectEntry.test.tsx`, `EntryCard.tsx`, `PantryRow.tsx`, `features/stocking/*`, `Section.tsx`. Il piano descrive ogni modifica contro un'ancora riconoscibile (una funzione, una riga di codice esatta), mai contro numeri di riga: **leggi il file com'è sul ramo prima di cambiarlo**. Le prove nuove di `style.spec.ts` vanno **in fondo al file**; quelle di `PantryScreen.test.tsx` in due `describe` nuovi **in fondo al file** (usano `CHIUSI`, `chiusiSalvati`, `reparto`, `mondo`, già definiti lì).
- **Mai un vicolo cieco.** Ogni stato nuovo lascia una strada: una riga che non va in vista alla ✕ è comunque in dispensa e a video nel suo reparto; un reparto tenuto aperto si chiude con un tocco sul titolo; l'avviso dice sempre dov'è finita una voce che il mondo scelto nasconde.
- **Prima lezione di `CLAUDE.md`: l'oggetto provato è quello che gira.** Le prove di schermo montano `PantryScreen` vero con `DirectEntry` vero (nessun mock dei componenti): il fetch è finto, la regia no. Il hook non ha prove sue: lo provano le prove di `PantryScreen`, che è il suo solo chiamante.
- **Il frontend non calcola logica di dominio.** Il mondo di una voce resta `ingredient_kind` del server; «in scadenza» resta il verdetto `expiry` del server. I pezzi nuovi confrontano verdetti, non li calcolano.
- Tutto il colore passa dai token di `frontend/src/index.css`. **Nessun token nuovo, nessuna classe di colore nuova**: questo piano non cambia l'aspetto di niente. `grep -rn "emerald\|neutral-" frontend/src` resta vuoto.
- Le parole a video sono in italiano e **si copiano esattamente come sono scritte qui**. L'unica frase nuova è il seguito dell'avviso: `, sotto «Cibo»` e `, sotto «Casa»` (virgola, spazio, «sotto», spazio, il nome del pulsante del selettore fra caporali, nessun punto finale). Gli identificatori in inglese; i commenti in italiano come nel resto del codice, e dicono il perché.
- **Il type check è `npm run typecheck`** (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0 (settima lezione di `CLAUDE.md`).
- Controlli del frontend, da `<worktree>/frontend`: `npx vitest run` (non esiste `npm test`), `npm run typecheck`, `npm run lint`, `npm run build`.
- **e2e** sullo stack `spena-e2e`, dalla radice di `<worktree>`. Serve un `.env`: **si copia da `.env.example`, che non ha segreti, solo per la prova, e si cancella alla fine.** Prima di alzarlo, `docker ps --format '{{.Names}}' | grep spena-e2e`: se c'è e non l'hai alzato tu (un altro piano della notte), non fare `down`, aspetta che sparisca.
  ```bash
  cp .env.example .env
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed --con-ricette
  (cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
  rm .env
  ```
  Il `-p spena-e2e` e il `-f docker-compose.e2e.yml` vanno in ogni comando: un `down -v` sul progetto di default cancellerebbe la dispensa vera. Una prova fallita lascia dati nello stack: prima di rieseguire, `down -v`, poi `up`, seme e prova. Per una prova sola: `npm run e2e -- -g "<inizio del titolo>"`.
- Nessuna dipendenza nuova, nessun cambio di configurazione globale.

### Preparazione (una volta, prima del Task 1)

- [ ] Il ramo di partenza è `master` e i file di questo piano sono quelli su cui è scritto (`master` era `4537139` quando il piano è stato scritto):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify master
  git show master:next-steps.md | grep -c "serie della scansione\|si spegne da solo"
  git diff --stat 4537139 master -- \
    frontend/src/features/pantry/PantryScreen.tsx frontend/src/features/pantry/pantryView.ts \
    frontend/src/features/pantry/collapsedSections.ts frontend/src/features/pantry/DirectEntry.tsx \
    frontend/src/features/pantry/PantryScreen.test.tsx frontend/src/features/pantry/pantryView.test.ts \
    frontend/e2e/style.spec.ts
  ```
  Expected: un hash; almeno `1`; il `diff --stat` **vuoto**. Se il `grep` dà `0`, la voce non è più su `master` (qualcuno l'ha fatta o tolta): **fermati** e scrivilo nel report. Se il `diff` non è vuoto, `master` è andato avanti su questi file: applica le modifiche del piano sopra la versione di `master`, ancora per ancora, e scrivilo nel report.
- [ ] Nessuno ha già cominciato:
  ```bash
  git branch --list night/dispensa-serie-reparti
  git grep -c "worldSummary\|enteredNotice\|holdFiltered" master -- frontend/src
  ```
  Expected: nessuna riga stampata da tutti e due. Altrimenti **fermati**, scrivi nel report cosa hai trovato e non partire.
- [ ] Dal checkout principale, allinea `node_modules` al lockfile (non aggiunge dipendenze):
  ```bash
  cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund
  ```
- [ ] Crea il worktree da `master` e collega `node_modules` (e solo quello: **niente `.env`**):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/dispensa-serie-reparti -b night/dispensa-serie-reparti master
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/dispensa-serie-reparti/frontend/node_modules
  ```
- [ ] La voce (o le due voci) in `next-steps.md` del ramo passa a `in corso`: `grep -n "serie della scansione\|si spegne da solo" next-steps.md` (di giorno possono essere state unite in una riga sola in «Pronti per la notte»); cambia solo lo stato fra parentesi quadre, e si committa:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/dispensa-serie-reparti
  git add next-steps.md
  git commit -m "next-steps: la serie della scansione e i reparti del riepilogo, in corso"
  ```
- [ ] La linea di partenza:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/dispensa-serie-reparti/frontend
  npx vitest run 2>&1 | grep -E "Test Files|Tests "
  ```
  Expected: tutto verde. **Annota i numeri** (`N_file`, `N_vitest`): servono al Task 5. Se non è verde, fermati: non è un difetto di questo piano, e va scritto nel report.

---

## Obiettivo e contesto

Due difetti trovati provando i rami S3, S14 e S15, entrambi su `afterEntry` e sui reparti della Dispensa.

**La serie.** «Scansiona» resta aperto dopo «Metti in dispensa» e torna allo scanner (S3 §4.5, il censimento). Ma `afterEntry` mette `revealId` a ogni ingresso, e `PantryRow` porta la riga nuova in cima alla vista (`revealAtTop`): il pannello dello scanner, che sta sopra le righe, esce dallo schermo, e con una dispensa lunga a ogni codice bisogna risalire. In più, su «Cibo» o «Casa», una voce dell'altro mondo porta il selettore a «Tutto» (`settleWorld`, che guarda `revealId`): a metà di un censimento di cose di casa la vista cambia sotto il dito.

**Il riepilogo che si spegne da solo.** Con «Latticini» chiuso si preme il riepilogo delle scadenze, che apre i reparti con una scadenza senza salvarli (S15 §3). Si segna «Finito» l'ultimo yogurt in scadenza, o se ne toglie la data: il riepilogo non ha più voci, sparisce, e il suo filtro si spegne nel disegno (`if (summary === null && expiringOnly) setExpiringOnly(false)`). Spento il filtro vale il salvato, e «Latticini» si richiude sotto il dito, portandosi via la riga col suo «In lista» — proprio il pulsante che chi ha appena finito lo yogurt vuole toccare.

## Decisioni prese

Di Mattia, il 2026-11-18 (non si rimettono in discussione):

1. **In serie la pagina non scorre.** Finché il pannello dello scanner è aperto, la riga nuova non si porta in vista: l'avviso «In dispensa: …» basta come conferma. Quando il pannello si chiude si porta in vista l'**ultima riga entrata** nella serie.
2. **In serie il selettore resta com'è (S14).** Il codice di una voce dell'altro mondo non porta il selettore a «Tutto»; l'avviso dice dov'è finita la voce. Il passaggio a «Tutto» resta per l'aggiunta singola, dal +.
3. **Il riepilogo spento dallo schermo lascia aperti i reparti che aveva aperto (S15)**, a video e senza salvarli, finché non si tocca qualcosa; alla prossima apertura della Dispensa torna lo stato salvato.
4. **Il riepilogo spento da chi guarda** segue la spec di oggi: spento il riepilogo torna il salvato.

Di questo piano (Claude, su delega di Mattia: scelte reversibili, da rivedere leggendo):

5. **Le parole dell'avviso.** In serie, quando la voce entrata non sta nel mondo scelto: `In dispensa: <etichetta>, sotto «Cibo»` per un alimento, `In dispensa: <etichetta>, sotto «Casa»` per una cosa di casa. «Cibo» e «Casa» sono i nomi dei pulsanti del selettore (`WORLD_LABELS`), e «sotto «Cibo»» è il modo in cui il codice e le spec dicono già dove sta una voce («il sale può stare sotto «Cibo»», S14 §4): chi legge sa quale pulsante premere per vederla. Con «Tutto», o con la voce dello stesso mondo, l'avviso è quello di oggi. Fuori dalla serie (dal +) l'avviso è quello di oggi anche per l'altro mondo, perché il selettore va a «Tutto» e la riga si vede.
6. **Alla chiusura, una riga dell'altro mondo porta il selettore a «Tutto»** e va in vista: è l'aggiunta singola di oggi, che la chiusura della serie ritrova da sé. `revealId` resta messo durante la serie; `settleWorld` e `PantryRow` lo ricevono solo a pannello chiuso (`pendingReveal`), e allora fanno esattamente quel che fanno oggi dopo un +. Nessun codice nuovo per questo caso, ed è la strada che finisce sempre con la riga a video. L'alternativa — lasciare il mondo e non scorrere — chiuderebbe la serie senza mostrare niente di quel che è entrato.
7. **«Chiudere il pannello»** è ogni modo in cui `DirectEntry` chiama `onClose` nella serie: la ✕ «Chiudi l'aggiunta» e «Annulla» dello scanner (che oggi chiude, come la ✕).
8. **S15 in serie: il reparto si apre lo stesso, e si salva aperto, a ogni ingresso.** È la regola di S15 §3 («la voce aggiunta apre il suo reparto e lo salva aperto: l'utente ha appena messo lì qualcosa»), che vale per ogni voce della serie e non solo per l'ultima: aprirne solo uno alla chiusura lascerebbe chiusi i reparti delle altre. Senza scorrimento aprire un reparto non sposta il pannello, che sta sopra. `afterEntry` continua a chiamare `sections.setOpen(category, true)` come oggi.
9. **Un reparto chiuso a mano durante la serie, dopo l'ingresso, resta chiuso alla chiusura del pannello**, e la sua riga non va in vista: il tocco sul titolo è venuto dopo l'ingresso, e vince. Il titolo chiuso dice quante voci ha (S15 §2): nessun vicolo cieco.
10. **Cosa conta come «toccare qualcosa» (S15).** Lasciano andare i reparti tenuti aperti:
    - un tocco sul **titolo di un reparto**, qualunque (e il reparto toccato si apre o chiude rispetto a com'è a video: un reparto tenuto aperto, toccato, si chiude);
    - ogni cambio del **testo della barra** (scrivere, cancellare);
    - un tocco sul **selettore** «Tutto / Cibo / Casa» o su «Cerca in tutto»;
    - un tocco sul **riepilogo delle scadenze** (se è tornato) o su «Mostra tutto»;
    - una **voce entrata** dall'ingresso diretto (passa da `setOpen`, come il titolo);
    - **lasciare la Dispensa**: lo stato tenuto vive solo nello schermo montato, e non si salva mai.

    **Non** li lasciano andare i gesti sulle righe — le tacche, la ✕ di una riga, «In lista», la scadenza della riga — né «Annulla» o «Riprova» negli avvisi, né aprire o chiudere il pannello dell'ingresso senza mettere niente in dispensa, né una dispensa riletta: sono proprio i gesti che la decisione 3 protegge (si segna «Finito», poi si tocca «In lista» sulla stessa riga).
11. **Chi spegne il riepilogo.** Lo spegne **chi guarda** quando tocca il riepilogo, «Mostra tutto», o sceglie dal selettore un mondo in cui il riepilogo non c'è (oggi il filtro si spegneva nel disegno anche in questo caso: ora lo spegne `chooseWorld`, come gesto). Lo spegne **lo schermo** in ogni altro caso in cui il riepilogo resta senza voci col filtro acceso: una voce in scadenza segnata «Finito», tolta con la ✕, o senza più data; una dispensa riletta. Dopo un ingresso, `afterEntry` spegne il filtro come oggi: è un gesto (decisione 10).
12. **Quali reparti si tengono aperti:** quelli che il riepilogo mostrava aperti nell'ultimo disegno col filtro acceso — i reparti con un risultato del filtro, meno quelli chiusi a mano durante il filtro (`closedWhileFiltering`). Non tutti i reparti: un reparto chiuso e senza scadenze, che col filtro non c'era, torna chiuso com'era. Si ricordano a ogni disegno col filtro acceso, perché al disegno in cui il riepilogo sparisce i dati sono già nuovi (la voce senza più data non sta più nel filtro, e il suo reparto non si potrebbe più ricavare).
13. **«Annulla» sull'ultima voce della serie** la toglie dalla dispensa: alla chiusura del pannello non c'è niente da portare in vista, e non va in vista quella prima. Si accetta: la serie è finita, le righe sono a video nei loro reparti aperti.

## Criteri di accettazione

- [ ] Da «Scansiona», con una dispensa più lunga dello schermo, dopo «Metti in dispensa» il campo del codice resta in vista e la pagina non si è mossa; l'avviso «In dispensa: …» c'è.
- [ ] Chiuso il pannello (✕ o «Annulla» dello scanner), l'ultima riga entrata va in vista; se è entrata mentre il pannello si chiudeva, va in vista quando arriva.
- [ ] In serie su «Casa», una voce di cibo lascia «Casa» premuto e l'avviso dice `In dispensa: <etichetta>, sotto «Cibo»`; chiuso il pannello, il selettore va a «Tutto» e la riga va in vista. Dal +, tutto come oggi (selettore a «Tutto», avviso senza seguito).
- [ ] In serie la voce che entra in un reparto chiuso lo apre e lo salva aperto, senza scorrere.
- [ ] Con un reparto chiuso, il riepilogo premuto e l'ultima voce in scadenza segnata «Finito» (o senza più data): il riepilogo sparisce, il reparto resta aperto con la riga e il suo «In lista», e il salvato non cambia; «In lista» toccato non lo chiude; un titolo, la barra o il selettore toccati lo chiudono; lasciata e riaperta la Dispensa è chiuso.
- [ ] Il riepilogo spento toccandolo, o scegliendo un mondo senza scadenze, torna al salvato come oggi.
- [ ] Nel browser vero a 375 px: le due prove nuove di `style.spec.ts` (Task 4) verdi, e tutte le prove e2e di oggi verdi senza modifiche.
- [ ] Tutti i test Vitest di oggi passano **senza modifiche**; le tre bozze, `docs/prossimi-passi.md`, `next-steps.md` aggiornati; il report scritto (Task 5).

## Comandi di verifica

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
git diff master --name-only -- backend frontend/src/features/stocking frontend/src/features/pantry/DirectEntry.tsx frontend/src/features/pantry/PantryRow.tsx
git diff master -- frontend/src/features/pantry/PantryScreen.test.tsx frontend/src/features/pantry/pantryView.test.ts frontend/e2e/style.spec.ts | grep "^-[^-]"
```

Expected: il primo e il secondo non stampano niente; il terzo stampa solo la vecchia riga (o le righe) dell'`import` da `./pantryView` in `pantryView.test.ts`, che il Task 1 allarga: nessun test di oggi tolto o cambiato. E l'e2e intera con i comandi delle Global Constraints.

## Review Focus

I casi che le decisioni implicano e che un test deve tenere fermi, i più probabili per primi; ognuno è fissato da un test nel task che possiede il codice:

1. **La ✕ toccata mentre «Metti in dispensa» è in volo**: la voce entra a pannello già chiuso, e deve andare in vista quando arriva, come un'aggiunta singola — non restare in attesa per sempre — Task 3 (`chiusa la serie mentre «Metti in dispensa» è in volo, la riga va in vista quando arriva`).
2. **Il riepilogo spento dal selettore** (si sceglie «Casa», che non ha scadenze): è un gesto, e i reparti non devono restare aperti; altrimenti tornando su «Tutto» si troverebbero aperti reparti che il salvato vuole chiusi — Task 2 (`spegnere il riepilogo scegliendo un mondo senza scadenze torna al salvato`).
3. **La data tolta invece di «Finito»**: la voce esce dal filtro prima che il riepilogo sparisca, e il suo reparto va tenuto aperto lo stesso (per questo i reparti si ricordano dal disegno prima) — Task 2 (`togliere la data all'ultima voce in scadenza lascia aperto il suo reparto`).
4. **Un reparto chiuso a mano a metà serie**: alla chiusura del pannello non deve riaprirsi né far scorrere verso una riga nascosta — Task 3 (`un reparto chiuso a mano durante la serie resta chiuso alla ✕, e non si scorre`).
5. **L'avviso più lungo a 375 px** («In dispensa: Marca e2e Broccoli e2e 1731…, sotto «Cibo»»): va a capo dentro lo schermo, senza far scorrere la pagina di lato — Task 4 (la prova della serie).

## Fuori scope

- La fotocamera che resta accesa fra un codice e l'altro, il fuoco che torna al campo del codice dopo «Metti in dispensa», la nota «L'hai appena messo…» dopo «Annulla», l'avviso d'errore a pannello chiuso, il codice ignoto arrivato dopo «Annulla»: restano le loro `idea` P3 [S3].
- «È anche in lista» nella scheda di conferma [S3, bozza 2026-10-06]; «Chiudi tutto / apri tutto» [S15]; l'errore di una riga dentro un reparto chiuso [S15].
- I reparti collassabili in Lista e in Sistema la spesa (S15 §7); il selettore fuori dalla Dispensa (S14 §7).
- Qualunque cambio al backend, a `DirectEntry`, a `ProductResolver`, a `PantryRow`, a `Section`.
- Le prove sul telefono (Mattia, dopo il deploy).

## Margine di autonomia

- **Liberi:** i nomi di variabili locali e di helper di test non fissati qui; l'ordine dei test dentro un `describe`; la formulazione dei commenti, purché dicano il perché.
- **Fissi:** i nomi pubblici della sezione «Interfacce» di ogni task (`worldSummary`, `enteredNotice`, `SectionView.held`, `noteFiltered`, `holdFiltered`, `releaseHold`); le parole a video; l'elenco della decisione 10.
- **Un test di oggi non si cambia.** Se uno cade, è un comportamento che il piano non ha previsto: scrivilo nel report con il perché, e non indebolirlo. In particolare restano verdi senza modifiche: in `PantryScreen.test.tsx` «una voce aggiunta dell'altro mondo porta il selettore a «Tutto», e va in vista» (il + fuori dalla serie, con `findByText("In dispensa: Mela")` esatto), «in un mondo senza scadenze il riepilogo non c'è, e il suo filtro premuto si spegne», «il riepilogo delle scadenze premuto apre i reparti con una scadenza, senza salvare», «la voce aggiunta in un reparto chiuso lo apre prima di portarla in vista, e lo salva aperto»; tutto `DirectEntry.test.tsx`; in `style.spec.ts` «l'ingresso diretto a 375px: …» e «S15 a 375px: …».
- **`npm run lint` deve passare senza disattivare regole.** Se `eslint-plugin-react-hooks` segnala `noteFiltered` o `holdFiltered` chiamati nel disegno, non spegnere la regola: scrivi nel report l'errore esatto, e sposta il ricordo (`noteFiltered`) in un `useEffect` senza dipendenze dentro il hook (lo stato si aggiorna dopo il disegno col filtro, prima di qualunque risposta del server), tenendo verdi le prove del Task 2.
- **Una decisione di comportamento non coperta e non reversibile** → si ferma quel task, si fa commit del lavoro parziale sul ramo, lo si segna `bloccato` in `next-steps.md` del ramo con la domanda precisa per Mattia, e si passa al task successivo. Una scelta reversibile e a basso impatto → la più conservativa, annotata nel report.
- Se un test fallisce e non si risolve in modo ragionevole: niente test disattivati, niente asserzioni indebolite; `bloccato` con la diagnosi.

## Dipendenze

**Parte da `master`.** Non consuma niente da altri piani. Al merge incontra, sugli stessi file, solo `night/suggerimenti-soglia` (l'unico ramo `pronto` rimasto), che aggiunge prove in fondo a `style.spec.ts`: punti diversi dello stesso file, che la revisione unisce.

## File toccati

| File | Cosa | Task |
|---|---|---|
| `frontend/src/features/pantry/pantryView.ts` | `SectionView.held`, `worldSummary`, `enteredNotice` | 1 |
| `frontend/src/features/pantry/pantryView.test.ts` | casi nuovi in coda | 1 |
| `frontend/src/features/pantry/collapsedSections.ts` | `held`, `noteFiltered`, `holdFiltered`, `releaseHold` | 2 |
| `frontend/src/features/pantry/PantryScreen.tsx` | il riepilogo tenuto (Task 2); la serie (Task 3) | 2, 3 |
| `frontend/src/features/pantry/PantryScreen.test.tsx` | due `describe` nuovi in fondo | 2, 3 |
| `frontend/e2e/style.spec.ts` | due prove in fondo | 4 |
| le tre bozze, `docs/prossimi-passi.md`, `next-steps.md`, `docs/night-reports/<data>.md` | documenti | 5 |

---

### Task 1: I tre pezzi puri

**Files:**
- Modify: `frontend/src/features/pantry/pantryView.ts`
- Test: `frontend/src/features/pantry/pantryView.test.ts`

**Interfaces:**
- Produces:
  - `interface SectionView { collapsed; filtering; closedWhileFiltering; held?: ReadonlySet<string> }` — `held` facoltativo, così i casi di oggi della tabella non cambiano.
  - `sectionOpen(category, view)`: con `filtering` come oggi (`!closedWhileFiltering.has`); senza, `!collapsed.has(category) || (held?.has(category) ?? false)`.
  - `export function worldSummary(items: PantryItem[], world: PantryWorld): string | null` — `expirySummary(expiryCounts(items.filter((item) => inWorld(item, world))))`.
  - `export function enteredNotice(label: string, kind: PantryItem["ingredient_kind"], world: PantryWorld, series: boolean): string` — `In dispensa: ${label}`, con in coda `, sotto «${WORLD_LABELS[kind]}»` solo se `series && world !== "all" && kind !== world`.

- [ ] **Step 1: Scrivi i test che falliscono**

In `pantryView.test.ts` aggiungi `enteredNotice` e `worldSummary` all'`import` da `./pantryView` (l'unica riga di oggi che cambia). Nella tabella `casi` di `describe("sectionOpen")`, **in coda**, tre casi (`LATTICINI` è un `ReadonlySet` nuovo con `"latticini"`, accanto a `FRUTTA`):

```ts
[
  "riepilogo spento dallo schermo: tenuto aperto, anche chiuso e salvato",
  { collapsed: FRUTTA, filtering: false, closedWhileFiltering: NIENTE, held: FRUTTA },
  true,
],
[
  "tenuto aperto un altro reparto: questo, chiuso e salvato, resta chiuso",
  { collapsed: FRUTTA, filtering: false, closedWhileFiltering: NIENTE, held: LATTICINI },
  false,
],
[
  "tenuto aperto, ma con un filtro acceso vale il filtro: chiuso a mano durante, chiuso",
  { collapsed: FRUTTA, filtering: true, closedWhileFiltering: FRUTTA, held: FRUTTA },
  false,
],
```

In fondo al file:

```ts
describe("worldSummary", () => {
  it("conta solo il mondo scelto", () => {
    const yogurt = item({ id: "y", expires_on: "2026-10-10", expiry: "soon" });
    const spugne = item({ ...CASA, id: "s", expires_on: "2026-10-01", expiry: "expired" });
    expect(worldSummary([yogurt, spugne], "food")).toBe("1 in scadenza questa settimana");
    expect(worldSummary([yogurt, spugne], "all")).toBe("1 in scadenza questa settimana · 1 oltre la scadenza");
  });
  it("in un mondo senza scadenze non c'è", () => {
    const yogurt = item({ id: "y", expires_on: "2026-10-10", expiry: "soon" });
    expect(worldSummary([yogurt, CASA], "non_food")).toBeNull();
  });
});

describe("enteredNotice", () => {
  const casi: [string, PantryItem["ingredient_kind"], PantryWorld, boolean, string][] = [
    ["in serie su «Tutto»: l'avviso di sempre", "food", "all", true, "In dispensa: Fage Total 0%"],
    ["in serie, lo stesso mondo: l'avviso di sempre", "food", "food", true, "In dispensa: Fage Total 0%"],
    ["in serie su «Casa», un cibo: dove è finito", "food", "non_food", true, "In dispensa: Fage Total 0%, sotto «Cibo»"],
    ["in serie su «Cibo», una cosa di casa: dove è finita", "non_food", "food", true, "In dispensa: Fage Total 0%, sotto «Casa»"],
    ["dal +, l'altro mondo: l'avviso di sempre (il selettore va a «Tutto»)", "food", "non_food", false, "In dispensa: Fage Total 0%"],
  ];
  it.each(casi)("%s", (_caso, kind, world, series, atteso) => {
    expect(enteredNotice("Fage Total 0%", kind, world, series)).toBe(atteso);
  });
});
```

- [ ] **Step 2: Falliscono**

Run: `npx vitest run src/features/pantry/pantryView.test.ts`
Expected: FAIL — `worldSummary` ed `enteredNotice` non esportate; il primo caso nuovo di `sectionOpen` dà `false`.

- [ ] **Step 3: Implementa** i tre pezzi in `pantryView.ts` con le firme dell'«Interfaces». `held` sta nella sezione `// --- S15 ---`, documentato nel commento di `SectionView` (i reparti che il riepilogo aveva aperti quando lo schermo l'ha spento: decisione 3 e 12 di questo piano). `worldSummary` va accanto a `expirySummary`; `enteredNotice` accanto a `settleWorld`, col commento che dice perché il seguito c'è solo in serie (decisione 5).

- [ ] **Step 4: Passano**

Run: `npx vitest run src/features/pantry/pantryView.test.ts`
Expected: PASS, 10 test in più (3 + 2 + 5).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/pantry/pantryView.ts frontend/src/features/pantry/pantryView.test.ts
git commit -m "feat(dispensa): i reparti tenuti aperti, il riepilogo di un mondo e l'avviso che dice dove è finita la voce"
```

---

### Task 2: Il riepilogo che si spegne da solo lascia aperti i suoi reparti (S15)

**Files:**
- Modify: `frontend/src/features/pantry/collapsedSections.ts` (`useCollapsedSections`)
- Modify: `frontend/src/features/pantry/PantryScreen.tsx`
- Test: `frontend/src/features/pantry/PantryScreen.test.tsx` (un `describe` nuovo in fondo)

**Interfaces:**
- Consumes: `SectionView.held`, `sectionOpen`, `worldSummary` (Task 1).
- Produces: `useCollapsedSections(filtering)` restituisce, oltre a `isOpen` e `setOpen` di oggi:
  - `noteFiltered(categories: readonly string[]): void` — si chiama **nel disegno**, solo col riepilogo premuto e presente; ricorda i reparti mostrati aperti (quelli dati, meno `closedWhileFiltering`), e cambia stato solo se l'insieme è diverso da quello ricordato;
  - `holdFiltered(): void` — lo schermo ha spento il riepilogo: `held` diventa l'ultimo insieme ricordato;
  - `releaseHold(): void` — `held` torna vuoto (lo stesso insieme se è già vuoto: niente disegno in più).
  - `setOpen` lascia andare `held` anche lui (decisione 10: il titolo e la voce entrata).

- [ ] **Step 1: Scrivi i test che falliscono**

In fondo a `PantryScreen.test.tsx`, un `describe("PantryScreen, il riepilogo che si spegne da solo (S15, 2026-11-18)")` con `beforeEach(() => localStorage.clear())` e `afterEach(() => vi.restoreAllMocks())`. Un fetch che tiene le righe e applica le `PATCH` (stato e scadenza) e risponde ai rientri:

```ts
/** La dispensa di `start`, che cambia con le PATCH come farebbe il server: lo stato, o la
 * data (senza data il verdetto `expiry` se ne va con lei). */
function dispensaViva(start: typeof DUE_MONDI) {
  let rows = start.map((row) => ({ ...row }));
  return stubRoutedFetch((path, init) => {
    if (path.includes("/shopping-list")) return [[], 200];
    if (path.includes("/restock")) return [{ added: true }, 200];
    if (init?.method === "PATCH") {
      const body = JSON.parse(String(init.body));
      rows = rows.map((row) =>
        path.includes(`/pantry/${row.id}`)
          ? { ...row, ...body, ...(body.expires_on === null ? { expiry: null } : {}) }
          : row
      );
      return [rows.find((row) => path.includes(`/pantry/${row.id}`)), 200];
    }
    return [rows, 200];
  });
}

/** Frutta chiusa e salvata, il riepilogo premuto (la mela è l'unica in scadenza), la mela
 * segnata «Finito»: il riepilogo sparisce. */
async function riepilogoSpentoDalloSchermo(start: typeof DUE_MONDI = ITEMS) {
  localStorage.setItem(CHIUSI, JSON.stringify(["frutta"]));
  dispensaViva(start);
  const view = renderScreen();
  fireEvent.click(await screen.findByRole("button", { name: "1 in scadenza questa settimana" }));
  expect(reparto("Frutta")).toHaveAttribute("aria-expanded", "true");
  const gauge = screen.getByRole("radiogroup", { name: "Quanto resta di mela" });
  fireEvent.click(within(gauge).getByRole("radio", { name: "Finito" }));
  await waitFor(() => expect(screen.queryByRole("button", { name: /in scadenza/ })).toBeNull());
  return view;
}
```

I test (nomi esatti, asserzioni come scritte):

1. `«Finito» sull'ultima voce in scadenza: il riepilogo sparisce, il reparto resta aperto con il suo «In lista», e il salvato non cambia` — dopo `riepilogoSpentoDalloSchermo()`: `reparto("Frutta")` ha `aria-expanded="true"`; la riga (`screen.getByRole("link", { name: "Mela" }).closest("li")`) ha il pulsante «In lista»; `chiusiSalvati()` è `["frutta"]`. Poi un tocco su «In lista»: `await screen.findByText("Rimesso in lista: mela")`, e `reparto("Frutta")` è ancora `"true"` (un gesto sulla riga non lascia andare).
2. `togliere la data all'ultima voce in scadenza lascia aperto il suo reparto` — come il test 1 fino al riepilogo premuto, poi al posto di «Finito» il gesto di «svuotare il campo manda null, non un corpo vuoto» sulla riga della mela (il pulsante `/scadenza/i`, il campo `/scadenza/i` a `""`, `blur`); `await waitFor` riepilogo sparito; `reparto("Frutta")` `"true"`; `chiusiSalvati()` `["frutta"]`.
3. `un tocco su un altro titolo lascia andare il reparto tenuto aperto` — `riepilogoSpentoDalloSchermo()`, `fireEvent.click(reparto("Latticini"))`: `reparto("Frutta")` `"false"`.
4. `scrivere nella barra, e cancellare, lascia andare il reparto tenuto aperto` — `riepilogoSpentoDalloSchermo()`, la barra a `"y"` e poi a `""`: `reparto("Frutta")` `"false"`; `chiusiSalvati()` `["frutta"]`.
5. `un tocco sul selettore lascia andare il reparto tenuto aperto` — `riepilogoSpentoDalloSchermo(DUE_MONDI)`, `fireEvent.click(mondo("Cibo"))`: `reparto("Frutta")` `"false"`.
6. `lasciata e riaperta la Dispensa, torna il salvato` — `const { unmount } = await riepilogoSpentoDalloSchermo()`, `unmount()`, `renderScreen()`, `await screen.findByRole("region", { name: "Frutta" })`: `reparto("Frutta")` `"false"`.
7. `spegnere il riepilogo scegliendo un mondo senza scadenze torna al salvato` — `localStorage` con `["frutta"]`, `dispensaViva(DUE_MONDI)`, il riepilogo premuto (`reparto("Frutta")` `"true"`), `fireEvent.click(mondo("Casa"))`, poi `fireEvent.click(mondo("Tutto"))`: `reparto("Frutta")` `"false"`, e il riepilogo c'è e non è premuto (`aria-pressed="false"`).

Il test 7 passa anche su `master` (oggi niente resta aperto): tiene fermo che la regola nuova non scatti per un gesto (Review Focus 2). Il test 6 è la guardia di «non si salva mai».

- [ ] **Step 2: Falliscono**

Run: `npx vitest run src/features/pantry/PantryScreen.test.tsx -t "si spegne da solo"`
Expected: FAIL i test 1 e 2 (`aria-expanded` è `"false"`: il reparto si è richiuso); 3–7 passano già (descrivono il salvato, che non cambia).

- [ ] **Step 3: Il hook**

In `useCollapsedSections`, due stati nuovi accanto a `closedWhileFiltering`: `held` e `shownByFilter`, tutti e due `ReadonlySet<string>` che partono da `NONE`. Un helper privato `sameMembers(a: ReadonlySet<string>, b: ReadonlySet<string>): boolean` (stessa grandezza, ogni elemento di `a` in `b`). La forma del ritorno:

```ts
const release = () => setHeld((prev) => (prev.size === 0 ? prev : NONE));
return {
  isOpen: (category: string) =>
    sectionOpen(category, { collapsed, filtering, closedWhileFiltering, held }),
  setOpen: (category: string, open: boolean) => {
    // …le due righe di oggi…
    release();
  },
  noteFiltered: (categories: readonly string[]) => {
    const shown = new Set(categories.filter((category) => !closedWhileFiltering.has(category)));
    if (!sameMembers(shown, shownByFilter)) setShownByFilter(shown);
  },
  holdFiltered: () => setHeld(shownByFilter),
  releaseHold: release,
};
```

Il commento del hook dice: il riepilogo spento dallo schermo lascia aperto a video quel che mostrava, senza salvarlo (decisione 3); perché si ricorda a ogni disegno col filtro e non al momento in cui si spegne (decisione 12); che `held` non va mai in `saveCollapsed`; che `noteFiltered` cambia stato nel disegno come le altre due righe del file, e per questo confronta prima di scrivere.

- [ ] **Step 4: Lo schermo**

In `PantryScreen.tsx`:

1. `const summary = worldSummary(items, world);` al posto della riga che oggi chiama `expirySummary(expiryCounts(items.filter(...)))` (togli dall'`import` quel che non serve più).
2. Il ramo che spegne il filtro nel disegno diventa:
   ```ts
   if (summary === null && expiringOnly) {
     setExpiringOnly(false);
     // è lo schermo a spegnerlo, non chi guarda: i reparti che il riepilogo aveva aperti
     // restano aperti a video finché non si tocca qualcosa (Mattia, 2026-11-18)
     sections.holdFiltered();
   }
   ```
3. Subito dopo `const visible = visibleItems(...)`: `const groups = groupForDisplay(visible);`, e `if (expiringOnly && summary !== null) sections.noteFiltered(groups.map(([category]) => category));`. Il JSX usa `groups` al posto di `groupForDisplay(visible)`.
4. `chooseWorld(next)`: in testa `sections.releaseHold();`, e se `expiringOnly && worldSummary(items, next) === null` allora `setExpiringOnly(false)` (decisione 11: è chi guarda a spegnerlo), poi le due righe di oggi.
5. Una funzione `changeQuery(text: string)` — `sections.releaseHold(); setQuery(text);` — passata come `onChange` di `ActionBar` al posto di `setQuery`. `afterEntry` continua a chiamare `setQuery("")` diretto (lascia andare già con `setOpen`).
6. Il pulsante del riepilogo: `onClick={() => { sections.releaseHold(); setExpiringOnly((prev) => !prev); }}`. «Mostra tutto»: `onClick={() => { sections.releaseHold(); setExpiringOnly(false); }}`.

Le righe, le tacche, la ✕ della riga, «In lista», la scadenza e gli avvisi non chiamano `releaseHold` (decisione 10).

- [ ] **Step 5: Passano**

Run: `npx vitest run src/features/pantry/`
Expected: PASS, i 7 nuovi e tutti quelli di oggi.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/pantry/collapsedSections.ts frontend/src/features/pantry/PantryScreen.tsx frontend/src/features/pantry/PantryScreen.test.tsx
git commit -m "feat(dispensa): il riepilogo che si spegne da solo lascia aperti i reparti che aveva aperto, finché non si tocca qualcosa"
```

---

### Task 3: La serie della scansione non scorre, e alla chiusura porta in vista l'ultima riga (S3, S14)

**Files:**
- Modify: `frontend/src/features/pantry/PantryScreen.tsx`
- Modify: `frontend/src/features/pantry/pantryView.ts` (solo il commento di `settleWorld`)
- Test: `frontend/src/features/pantry/PantryScreen.test.tsx` (un secondo `describe` nuovo in fondo)

**Interfaces:**
- Consumes: `enteredNotice` (Task 1); `sections.isOpen`, `sections.setOpen` (Task 2). Da oggi, invariati: `DirectEntry` (`door`, `onEntered(created, label)`, `onClose`), `settleWorld(world, items, revealId)`, la prop `reveal` di `PantryRow`, che porta la riga in vista nel suo effetto quando diventa `true` (anche su una riga già montata) e poi chiama `onRevealed`.
- Produces: in `PantryScreen`, `inSeries` (`entry !== null && entry.door.kind === "scan"`), `pendingReveal` (`inSeries ? null : revealId`), `closeEntry()`.

- [ ] **Step 1: Scrivi i test che falliscono**

`import userEvent from "@testing-library/user-event";` in testa al file. In fondo, `describe("PantryScreen, la serie della scansione (S3, S14, S15, 2026-11-18)")`, con `beforeEach(() => localStorage.clear())` e `afterEach(() => vi.restoreAllMocks())`. Gli oggetti e il fetch:

```ts
const FAGE = { id: "pr1", ingredient_id: "i1", ingredient_name: "yogurt greco", name: "Total 0%",
  brand: "Fage", barcode: "52010", source: "openfoodfacts", nutrients: null, image_url: null };
const PESCA = { ...FAGE, id: "pr2", name: "Pesca", brand: "Carrefour", barcode: "52011" };
const inCatalog = (product: typeof FAGE) =>
  ({ found: true, origin: "catalog", product, suggestion: null, valid_checksum: true });

/** La dispensa di `start`; i codici 52010 e 52011 sono Fage e Pesca a catalogo; ogni
 * «Metti in dispensa» crea la voce dopo in `created` e la aggiunge alla dispensa riletta.
 * `gate`, se c'è, trattiene la risposta della scrittura finché il test non la libera: per
 * questo non `stubRoutedFetch`, che risponde subito. */
function serieFinta(start: typeof DUE_MONDI, created: typeof DUE_MONDI, gate?: Promise<void>) {
  const rows = [...start];
  const respond = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
  const spy = vi.fn(async (url: unknown, init?: RequestInit) => {
    const path = String(url);
    if (path.includes("/shopping-list")) return respond([]);
    if (path.includes("/products/barcode/52010")) return respond(inCatalog(FAGE));
    if (path.includes("/products/barcode/52011")) return respond(inCatalog(PESCA));
    if (path.endsWith("/pantry") && init?.method === "POST") {
      if (gate) await gate;
      const voce = created[rows.length - start.length];
      rows.push(voce);
      return respond(voce, 201);
    }
    return respond([...rows]);
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

/** Aspetta che la dispensa sia stata letta `volte` volte, e che lo schermo l'abbia
 * disegnata: la riga nuova è arrivata anche quando il mondo scelto la nasconde. */
async function dispensaLetta(spy: ReturnType<typeof serieFinta>, volte: number) {
  await waitFor(() =>
    expect(
      spy.mock.calls.filter(
        ([url, init]) => String(url).endsWith("/pantry") && (init?.method ?? "GET") === "GET"
      ).length
    ).toBeGreaterThanOrEqual(volte)
  );
  await act(async () => {});
}

async function leggi(codice: string) {
  await userEvent.type(screen.getByLabelText("Codice a barre"), `${codice}{Enter}`);
  await userEvent.click(await screen.findByRole("button", { name: "Metti in dispensa" }));
}

/** Le righe portate in vista, nell'ordine: `this` è l'elemento (uno spy e non
 * un'assegnazione, come nei test di S15). */
function righePortateInVista(): Element[] {
  const scrolled: Element[] = [];
  vi.spyOn(Element.prototype, "scrollIntoView").mockImplementation(function (this: Element) {
    scrolled.push(this);
  });
  return scrolled;
}
```

Le voci create: `const P9 = { ...ITEMS[0], id: "p9" }` (Fage) e `const P10 = { ...ITEMS[1], id: "p10" }` (Pesca). «Scansiona» è `fireEvent.click(screen.getByRole("button", { name: "Scansiona" }))` dopo `await screen.findByText("Total 0%")`; «chiudi il pannello» è `fireEvent.click(screen.getByRole("button", { name: "Chiudi l'aggiunta" }))`.

I test (nomi esatti):

1. `in serie la riga nuova non va in vista, basta l'avviso; chiuso il pannello va in vista l'ultima entrata` — `const scrolled = righePortateInVista()`; `const spy = serieFinta(ITEMS, [P9, P10])`; «Scansiona»; `await leggi("52010")`; `await screen.findByText("In dispensa: Fage Total 0%")`; `await dispensaLetta(spy, 2)`; `expect(scrolled).toHaveLength(0)`; lo scanner è di nuovo lì (`heading "Codice a barre"`). `await leggi("52011")`; `await screen.findByText("In dispensa: Carrefour Pesca")`; `await dispensaLetta(spy, 3)`; `expect(scrolled).toHaveLength(0)`. Chiudi il pannello: `await waitFor(() => expect(scrolled).toHaveLength(1))`, e `expect(scrolled[0].textContent).toContain("Pesca")` (la riga di P10, l'ultima).
2. `in serie la voce che entra in un reparto chiuso lo apre e lo salva aperto, senza scorrere` — `localStorage` con `["latticini"]`; `righePortateInVista()`; `const spy = serieFinta(ITEMS, [P9])`; «Scansiona»; `await leggi("52010")`; `await dispensaLetta(spy, 2)`: `reparto("Latticini")` `"true"`, `chiusiSalvati()` `[]`, nessuna riga portata in vista.
3. `in serie su «Casa» una voce di cibo lascia il selettore com'è e l'avviso dice dov'è finita; chiuso il pannello, «Tutto» e la riga in vista` — `const spy = serieFinta(DUE_MONDI, [P9])`; `fireEvent.click(mondo("Casa"))`; «Scansiona»; `await leggi("52010")`; `expect(await screen.findByText("In dispensa: Fage Total 0%, sotto «Cibo»")).toBeDefined()`; `await dispensaLetta(spy, 2)`; `mondo("Casa")` ha `aria-pressed="true"` e `scrolled` è vuoto. Chiudi il pannello: `await waitFor(() => expect(mondo("Tutto").getAttribute("aria-pressed")).toBe("true"))`, `await waitFor(() => expect(scrolled).toHaveLength(1))`.
4. `chiusa la serie mentre «Metti in dispensa» è in volo, la riga va in vista quando arriva` — un `gate` come in «un tocco sul selettore spegne la riga da portare in vista» (`let releaseWrite = () => {}; const gate = new Promise<void>((r) => { releaseWrite = r; })`); `serieFinta(ITEMS, [P9], gate)`; «Scansiona»; `await leggi("52010")`; chiudi il pannello **prima** di liberare la scrittura; `await act(async () => releaseWrite())`; `await screen.findByText("In dispensa: Fage Total 0%")`; `await waitFor(() => expect(scrolled).toHaveLength(1))`.
5. `un reparto chiuso a mano durante la serie resta chiuso alla ✕, e non si scorre` — `const spy = serieFinta(ITEMS, [P9])`; «Scansiona»; `await leggi("52010")`; `await dispensaLetta(spy, 2)`; `fireEvent.click(reparto("Latticini"))` (chiuso); chiudi il pannello; `await act(async () => {})`; `expect(scrolled).toHaveLength(0)`; `reparto("Latticini")` `"false"`; `chiusiSalvati()` `["latticini"]`.

- [ ] **Step 2: Falliscono**

Run: `npx vitest run src/features/pantry/PantryScreen.test.tsx -t "la serie della scansione"`
Expected: FAIL 1, 2, 3 e 5 (oggi la riga va in vista a ogni ingresso, appena arriva; nel 3 anche l'avviso senza il seguito e il selettore a «Tutto»); 4 passa già (oggi la riga va in vista comunque, ed è la guardia che la serie non la lasci in attesa per sempre).

- [ ] **Step 3: Implementa** in `PantryScreen.tsx`

1. Dopo lo stato `revealId`:
   ```ts
   // S3, Mattia 2026-11-18: finché la serie della scansione è aperta la riga nuova aspetta,
   // perché portarla in vista spinge fuori dallo schermo il pannello che sta sopra le righe;
   // l'avviso conferma già. Chiuso il pannello, la riga in attesa (l'ultima entrata) va in
   // vista con le regole di un'aggiunta singola, mondo compreso (settleWorld)
   const inSeries = entry !== null && entry.door.kind === "scan";
   const pendingReveal = inSeries ? null : revealId;
   ```
2. `settleWorld(world, items, pendingReveal)` al posto di `settleWorld(world, items, revealId)`, e `reveal={item.id === pendingReveal}` in `PantryRow`. Aggiorna il commento di `settleWorld` in `pantryView.ts` e quello di `afterEntry`: «l'altro mondo porta a «Tutto»» vale per la riga **non in attesa**.
3. In `afterEntry` l'avviso diventa `text: enteredNotice(label, created.ingredient_kind, world, entry?.door.kind === "scan")`. Il resto di `afterEntry` non cambia: `revealId` si mette anche in serie (è la riga in attesa), e `sections.setOpen(created.ingredient_category, true)` apre e salva il reparto anche in serie (decisione 8).
4. `closeEntry()` al posto di `() => setEntry(null)` in `onClose` di `DirectEntry`:
   ```ts
   function closeEntry() {
     setEntry(null);
     // un reparto chiuso a mano dopo l'ingresso resta chiuso: la riga in attesa non va in
     // vista dentro un contenuto nascosto. Il confronto in `setRevealId` lascia stare una
     // riga più nuova, messa da un `afterEntry` arrivato nello stesso giro
     const pending = items.find((item) => item.id === revealId);
     if (pending !== undefined && !sections.isOpen(pending.ingredient_category)) {
       setRevealId((current) => (current === pending.id ? null : current));
     }
   }
   ```

`DirectEntry` chiama `onClose` sia dalla ✕ sia da «Annulla» dello scanner (decisione 7), e dal + dopo «Metti in dispensa»: lì `revealId` non è in attesa (il + non è una serie), e `closeEntry` non cambia niente di quel che succede oggi.

**Il caso accettato** (scrivilo nel commento di `afterEntry`): se la ✕ arriva mentre «Metti in dispensa» è in volo, `afterEntry` gira dopo con la chiusura di prima del tocco, che dice ancora «in serie»; l'avviso può quindi dire «sotto «Cibo»» mentre il selettore passa a «Tutto». È vero, solo ridondante, e la riga va in vista (test 4).

- [ ] **Step 4: Passano**

Run: `npx vitest run src/features/pantry/ && npm run typecheck && npm run lint`
Expected: PASS, i 5 nuovi e tutti quelli di oggi (`DirectEntry.test.tsx` compreso, intatto); typecheck e lint puliti.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/pantry/PantryScreen.tsx frontend/src/features/pantry/pantryView.ts frontend/src/features/pantry/PantryScreen.test.tsx
git commit -m "feat(dispensa): la serie della scansione non scorre e non cambia mondo; chiusa, porta in vista l'ultima riga entrata"
```

---

### Task 4: Nel browser vero, a 375 px

**Files:**
- Modify: `frontend/e2e/style.spec.ts` (due prove **in fondo al file**)

**Interfaces:**
- Consumes: gli helper del file, già definiti: `dalSeme(page, nome)`, `inDispensa(page, ingredientId)`, `togliDallaDispensa(page, voceId)`, `senzaScorrimentoLaterale(page, luogo)`, `leggibileNeiDueTemi(page, dove)`, `fermo(page)`, e `giornoDiRoma` importato in testa.

Gli ingredienti del seme che queste prove usano non li nomina nessun altro file di `frontend/e2e/` (verificato il 2026-11-18; ricontrolla con `grep -rn "<nome>" frontend/e2e` prima di usarli, e se uno è nominato scegline un altro dello stesso reparto e scrivilo nel report). Ogni prova toglie quel che crea nel `finally`, con `expect.soft` e un `try/catch` per voce, come «l'ingresso diretto a 375px»: prima le voci, poi i prodotti.

- [ ] **Step 1: La prova della serie**

`test("S3 in serie a 375px: con la dispensa lunga lo scanner resta in vista dopo «Metti in dispensa», chiuso il pannello va in vista l'ultima riga; su «Casa» un cibo lascia il selettore e l'avviso dice dov'è finito", …)`:

1. `await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible()`; viewport 375×812; `await page.emulateMedia({ reducedMotion: "reduce" })` (il salto secco di `revealAtTop`: sul codice di prima la pagina è già scesa quando la prova guarda).
2. Riempitivi, sfusi, in reparti che vengono prima di «verdura»: `birra`, `camomilla`, `cous cous`, `polenta`, `grissini`, `senape`, `ketchup`, `capperi`, `cacao amaro`, `marmellata`, `savoiardi`, `salsiccia`; e una cosa di casa perché il selettore ci sia, `fazzoletti di carta`. Tre prodotti con `page.request.post("/api/v1/products", …)`, marca `Marca e2e`, sotto `broccolo`, `zucca` e `bietola` (reparto «verdura», l'ultimo: le righe nuove finiscono in fondo), nomi `Broccoli e2e ${base}`, `Zucca e2e ${base}`, `Bietola e2e ${base}`, codici `String(base)`, `String(base + 1)`, `String(base + 2)` con `const base = Date.now()`.
3. `page.goto("/dispensa")`, aspetta una riga dei riempitivi; poi la guardia: `scrollHeight - clientHeight` di `document.documentElement` **almeno 600**, con il messaggio «la dispensa non è abbastanza lunga perché la prova dica qualcosa».
4. «Scansiona». Per Broccoli e poi Zucca: il codice nel campo «Codice a barre», Invio, «Metti in dispensa»; l'avviso `In dispensa: Marca e2e <nome>` visibile; `page.locator("li", { hasText: nome })` con `toHaveCount(1)`; `page.waitForLoadState("networkidle")`; `fermo(page)`; poi `expect(await page.evaluate<number>("window.scrollY")).toBe(0)` e `await expect(campo).toBeInViewport()`.
5. «Chiudi l'aggiunta»: `await expect(page.locator("li", { hasText: nomeZucca })).toBeInViewport()`.
6. `page.evaluate("window.scrollTo(0, 0)")`; nel gruppo «Cosa mostrare», «Casa» → `aria-pressed="true"`. «Scansiona», Bietola: l'avviso `In dispensa: Marca e2e ${nomeBietola}, sotto «Cibo»` visibile (filtro `getByRole("status")` col testo intero); `senzaScorrimentoLaterale(page, "l'avviso col mondo della voce")`; «Casa» ancora premuto; `window.scrollY` ancora `0`.
7. «Chiudi l'aggiunta»: «Tutto» `aria-pressed="true"`, e la riga di Bietola `toBeInViewport()`.
8. `finally`: le voci con `product_id` dei tre prodotti (da `GET /api/v1/pantry`), poi i tre prodotti (`DELETE /api/v1/products/{id}`), poi i riempitivi con `togliDallaDispensa`; `page.emulateMedia({ reducedMotion: "no-preference" })`.

- [ ] **Step 2: La prova del riepilogo**

`test("S15 a 375px: il riepilogo che si spegne da solo lascia aperto il reparto che aveva aperto, con il suo «In lista», e riaperta la Dispensa torna il salvato", …)`:

1. Attesa del link «Dispensa», viewport 375×812. `prosciutto cotto` in dispensa (`inDispensa`), poi `PATCH` con `expires_on: giornoDiRoma(2)`.
2. La guardia: in `GET /api/v1/pantry` nessun'altra voce non finita con `expiry` diversa da `null` (messaggio: «altre voci in scadenza nello stack: il riepilogo non può sparire»).
3. Dal link «Dispensa». `const carne = page.getByRole("region", { name: "Carne" })`, `const titolo = carne.getByRole("button", { name: /^Carne\b/ })`. Un tocco: `aria-expanded="false"`, e nel `localStorage` `spena.dispensa.reparti-chiusi` è `["carne"]`.
4. Il riepilogo `/in scadenza questa settimana/`: `titolo` `aria-expanded="true"`. Nella riga del prosciutto, il gruppo «Quanto resta di prosciutto cotto», «Finito». Il riepilogo `toHaveCount(0)`; `titolo` ancora `"true"`; il pulsante «In lista» della riga visibile; il `localStorage` ancora `["carne"]`.
5. `leggibileNeiDueTemi(page, "il reparto tenuto aperto dopo il riepilogo spento")`.
6. Il link «Lista», poi il link «Dispensa»: `titolo` `aria-expanded="false"`.
7. `finally`: `togliDallaDispensa` sul prosciutto.

- [ ] **Step 3: Le due prove passano**

Con lo stack alzato sul ramo (Global Constraints): `npm run e2e -- -g "S3 in serie a 375px"` e `npm run e2e -- -g "S15 a 375px: il riepilogo che si spegne"`. Expected: PASS tutte e due. Il rosso sul codice di prima non è richiesto; se lo provi (un worktree temporaneo di `master` con le due prove copiate in fondo a `style.spec.ts`, poi tolto), l'atteso è: la prima cade al punto 4 su `window.scrollY`, la seconda al punto 4 su `aria-expanded`. Scrivi nel report se l'hai fatto.

- [ ] **Step 4: L'e2e intera**

Lo stack ricreato da zero (`down -v`, `up`, seme), `npm run e2e`. Expected: tutte verdi, `N_e2e` di oggi più 2; **annota `N_e2e`**. Poi `down -v` e `rm .env`, sempre.

- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/style.spec.ts
git commit -m "e2e: la serie della scansione a 375px con la dispensa lunga, e il riepilogo che si spegne da solo"
```

---

### Task 5: Le spec, i documenti, la verifica finale e il report

**Files:**
- Modify: `docs/superpowers/specs/2026-10-06-ingresso-diretto-bozza.md`, `docs/superpowers/specs/2026-10-06-cibo-casa-bozza.md`, `docs/superpowers/specs/2026-10-06-reparti-collassabili-bozza.md`, `docs/prossimi-passi.md`, `next-steps.md`
- Create o modify: `docs/night-reports/<data di oggi>.md`

Leggi ogni file com'è sul ramo prima di cambiarlo. `<data di oggi>` è la data vera della notte. Si aggiunge, non si riscrive: nessun paragrafo di oggi cambia.

- [ ] **Step 1: La bozza di S3**, in fondo a §4.5 («In serie, per il censimento»), dopo il paragrafo che finisce con «invece di scriverlo due volte in silenzio.»:

```markdown
**Aggiornato il 2026-11-18 (Mattia).** Finché il pannello della scansione è aperto la pagina
non scorre fino alla riga nuova: il pannello sta sopra le righe, e con una dispensa lunga a
ogni codice bisognava risalire. L'avviso «In dispensa: …» basta come conferma. Quando il
pannello si chiude (la ✕, o «Annulla» dello scanner) va in vista l'ultima riga entrata nella
serie, con le regole dell'aggiunta singola: se è dell'altro mondo il selettore passa a
«Tutto» (S14 §4). Il reparto di ogni voce entrata si apre e si salva aperto come fuori dalla
serie (S15 §3); se chi guarda lo richiude a mano prima della fine, resta chiuso e la riga non
va in vista. Piano `docs/superpowers/plans/2026-11-18-dispensa-serie-reparti.md`.
```

- [ ] **Step 2: La bozza di S14**, in §4, subito dopo il punto che comincia con «**Aggiungere una voce dell'altro mondo**»:

```markdown
- **In serie** (la scansione di S3 §4.5, deciso da Mattia il 2026-11-18) il selettore resta
  com'è: l'avviso dice dov'è finita la voce, «In dispensa: Fage Total 0%, sotto «Cibo»»
  (o «sotto «Casa»»), coi nomi dei pulsanti del selettore. Chiuso il pannello, l'ultima riga
  entrata va in vista come un'aggiunta singola: se è dell'altro mondo, il selettore passa a
  «Tutto». Scegliere un mondo in cui il riepilogo delle scadenze non c'è spegne il suo filtro:
  è un gesto di chi guarda (S15 §3).
```

- [ ] **Step 3: La bozza di S15**, in §3: nella tabella, dopo la riga «Toccare il titolo durante una ricerca», due righe:

```markdown
| Riepilogo spento dallo schermo (l'ultima voce in scadenza finita, tolta o senza più data) | i reparti che il riepilogo mostrava aperti restano aperti, finché non si tocca qualcosa (sotto) | niente: alla prossima apertura della Dispensa torna il salvato |
| Voce entrata nella serie della scansione (S3 §4.5) | il suo reparto si apre, senza scorrere; chiuso il pannello, l'ultima riga va in vista | sì, si salva aperto |
```

e dopo il paragrafo che comincia con «Cancellata la ricerca o spento il riepilogo»:

```markdown
**Chi spegne il riepilogo (deciso da Mattia il 2026-11-18).** Se lo spegne chi guarda — un
tocco sul riepilogo, «Mostra tutto», un mondo senza scadenze scelto dal selettore — torna il
salvato, come sopra. Se lo spegne lo schermo, perché il riepilogo è rimasto senza voci (si è
segnata «Finito» l'ultima voce in scadenza, o le si è tolta la data, o la ✕), i reparti che
mostrava aperti restano aperti a video, senza salvarli: altrimenti il reparto si richiuderebbe
sotto il dito portandosi via la riga col suo «In lista». Li lascia andare il primo tocco su un
titolo di reparto, sulla barra, sul selettore o su «Cerca in tutto», sul riepilogo tornato, una
voce entrata dall'ingresso diretto, o lasciare la Dispensa. I gesti sulle righe (tacche, ✕,
«In lista», scadenza) e gli avvisi no: sono quelli che questa regola protegge. Piano
`docs/superpowers/plans/2026-11-18-dispensa-serie-reparti.md`.
```

- [ ] **Step 4: `docs/prossimi-passi.md`.** In fondo alla voce `## S3.`, dopo il paragrafo «**Da provare sul telefono:** …»:

```markdown
↳ **2026-11-18, la serie e la riga in vista** (decisione di Mattia, piano
`docs/superpowers/plans/2026-11-18-dispensa-serie-reparti.md`, ramo
`night/dispensa-serie-reparti`): finché il pannello della scansione è aperto la pagina non
scorre più alla riga nuova, e chiuso il pannello va in vista l'ultima riga entrata. In serie
su «Cibo» o «Casa» il selettore resta com'è e l'avviso dice dov'è finita la voce («…, sotto
«Cibo»»). Le bozze di S3 §4.5, S14 §4 e S15 §3 lo dicono.
```

In fondo alla voce `## S14.` e in fondo alla voce `## S15.`, una riga ciascuna:

```markdown
↳ **2026-11-18:** in serie il selettore non va più a «Tutto»; vedi S3 e la bozza §4.
```
```markdown
↳ **2026-11-18:** il riepilogo spento dallo schermo lascia aperti a video i reparti che aveva aperto, finché non si tocca qualcosa; spento da chi guarda torna il salvato. Vedi la bozza §3 e il piano `docs/superpowers/plans/2026-11-18-dispensa-serie-reparti.md`.
```

- [ ] **Step 5: `next-steps.md`**

1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte)_`.
2. Togli la riga o le due righe di questa voce (`grep -n "serie della scansione\|si spegne da solo" next-steps.md`: `in corso` dalla Preparazione, dovunque siano). Se in «Pronti per la notte» era una voce numerata, lascia com'è la numerazione delle altre.
3. In cima a «Fatti (recenti)»:
   ```markdown
   - [fatto] <data di oggi> · S3 e S15, la Dispensa che non si muove sotto il dito: la serie della scansione non scorre più alla riga nuova e, su «Cibo» o «Casa», non cambia mondo (l'avviso dice «…, sotto «Cibo»»); chiuso il pannello va in vista l'ultima riga entrata. Il riepilogo delle scadenze spento dallo schermo lascia aperti i reparti che aveva aperto, finché non si tocca un titolo, la barra o il selettore [S3, S14, S15] → branch night/dispensa-serie-reparti (da revisionare)
   ```
4. In cima a «Da fare a mano (solo Mattia)»:
   ```markdown
   - [tbd] P2 · Prove sul telefono dopo il deploy di night/dispensa-serie-reparti: un censimento vero con la dispensa lunga (lo scanner resta in vista, alla ✕ si arriva all'ultima riga), una serie su «Casa» con un cibo in mezzo (l'avviso «sotto «Cibo»» si legge in tempo?), e il riepilogo premuto con un reparto chiuso, «Finito» sull'ultima voce e poi «In lista» [S3, S15]
   ```
5. Se nella notte sono emerse altre cose fuori da questo piano, aggiungile come `idea` o `tbd` nella sezione giusta, con la voce di `docs/prossimi-passi.md` fra parentesi quadre.

- [ ] **Step 6: Commit dei documenti**

```bash
git add docs/superpowers/specs/2026-10-06-ingresso-diretto-bozza.md docs/superpowers/specs/2026-10-06-cibo-casa-bozza.md docs/superpowers/specs/2026-10-06-reparti-collassabili-bozza.md docs/prossimi-passi.md next-steps.md
git commit -m "docs: la serie della scansione e il riepilogo che si spegne da solo, nelle bozze di S3, S14 e S15"
```

- [ ] **Step 7: La verifica finale**

Da `<worktree>/frontend`: i cinque comandi della sezione «Comandi di verifica». Expected: vitest tutto verde — **`N_vitest` della Preparazione più 22** (10 del Task 1, 7 del Task 2, 5 del Task 3) in **`N_file`** file (nessun file nuovo); se il numero differisce, scrivi nel report da dove viene. Typecheck, lint e build puliti. `npx tsc -b --force` perché `node_modules` è condiviso col checkout principale, e con lui il `tsbuildinfo`.

Dalla radice del worktree, i tre comandi della stessa sezione. Expected: quel che dice quella sezione.

L'e2e intera (Task 4, Step 4) se il codice è cambiato dopo l'ultima volta che l'hai fatta girare. Poi `down -v` e `rm .env`, sempre.

- [ ] **Step 8: Il report**

`docs/night-reports/<data di oggi>.md` sul ramo: se il file c'è già aggiungi una sezione in fondo, altrimenti crealo con il titolo `# Notte del <data di oggi>`. Per questo piano: il ramo e da dove parte (`master`); i conti veri (vitest, e2e) contro quelli della Preparazione; i test di oggi cambiati (atteso: nessuno; cambiano solo due righe di `import`); come sono andati gli Step 2 dei Task 2 e 3 (quali test erano rossi prima); se hai verificato il rosso delle due prove e2e su `master`; se il lint ha chiesto di spostare `noteFiltered` in un effetto (Margine di autonomia); le **scelte del piano che Mattia può voler rivedere**, cioè le decisioni 5–13 (le parole «sotto «Cibo»»; «Tutto» e la riga in vista alla chiusura; «Annulla» dello scanner che conta come chiusura; il reparto che si apre a ogni ingresso della serie; il reparto chiuso a mano che resta chiuso; l'elenco di «toccare qualcosa», con la voce entrata e il riepilogo in più rispetto a quel che ha detto Mattia; il selettore che spegne il riepilogo come gesto; «Annulla» sull'ultima voce che lascia la chiusura senza riga); il caso accettato della ✕ durante la scrittura (avviso «sotto «Cibo»» mentre il selettore va a «Tutto»); il file che al merge incontra altro (`style.spec.ts` con `night/suggerimenti-soglia`); e la sezione «Dopo il deploy (solo Mattia)» qui sotto, ricopiata. Niente push, niente merge, niente deploy.

```bash
git add docs/night-reports/
git commit -m "report: la serie della scansione e i reparti del riepilogo, la notte"
```

---

## Dopo il deploy (solo Mattia)

La notte non tocca la produzione. Nessuna migrazione, nessun passo a mano sul server: dopo il deploy di sempre (`docker compose -f docker-compose.prod.yml up -d --build --wait`; **il `-f docker-compose.prod.yml` non è opzionale**, `CLAUDE.md`), sul telefono:

1. In Dispensa, con tante righe, «Scansiona» e tre o quattro confezioni di fila: dopo ogni «Metti in dispensa» lo scanner resta lì; alla ✕ la pagina va all'ultima entrata.
2. Su «Casa», una serie con un cibo in mezzo: il selettore resta su «Casa» e l'avviso dice «…, sotto «Cibo»» (si legge nei sei secondi?); alla ✕ il selettore va a «Tutto».
3. Un reparto chiuso con una voce in scadenza: il riepilogo premuto, «Finito» sulla voce, il reparto resta aperto con «In lista»; un tocco su un altro titolo lo richiude; uscendo e rientrando è chiuso.
