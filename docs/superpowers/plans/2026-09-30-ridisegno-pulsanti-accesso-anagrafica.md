# T3 Consegna 6a — Pulsanti, Accesso, Anagrafica: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** una regola sola per i pulsanti spenti in tutta l'app — `Button` impara `unavailableReason` («non si può ancora», col perché scritto sotto) e `accessibleName` (un nome più lungo del testo in vista) — e con lei tre pezzi della Consegna 6: i pulsanti scritti a mano di «Sistema la spesa» passano a `Button`, l'accesso prende il fuoco e impara «Mostra password», le correzioni dell'Anagrafica diventano gruppi di icone accanto al titolo e il suo campo si chiama «Cerca un ingrediente o un prodotto».

**Architecture:** tutto nel frontend. `Button` (`frontend/src/components/ui/Button.tsx`) diventa l'unico posto dove un pulsante si spegne: `busy` (in volo) e `unavailableReason` (non ancora) spengono con `aria-disabled`, ignorano tocco e invio del modulo, tengono il fuoco; `unavailableReason` disegna un `<p>` fratello del pulsante e lo collega con `aria-describedby`. I chiamanti smettono di riscrivere a mano `aria-disabled`, la guardia e il motivo. Nessuna rotta, nessuna migrazione, nessuna dipendenza, nessun cambio al backend.

**Tech Stack:** React 19, TypeScript, Tailwind 4 (token in `@theme`), TanStack Query 5, react-router 7, Vitest + Testing Library (jsdom), Playwright 1.63.

**Spec:** `docs/superpowers/specs/2026-09-28-ridisegno-design.md`, §2 (regola delle icone), §3.3 (icone dell'Anagrafica), §3.5 (`Button`, `IconToolbar`), §4.7 (Anagrafica, Accesso), §6 (nomi accessibili stabili). Le decisioni vincolanti sono quelle della fase giorno del 2026-09-29 (seconda), riportate sotto in «Decisioni prese»; la sezione «Interfacce condivise» di quelle decisioni è un contratto con i piani 2, 3 e 4 della stessa notte.

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/c6a-pulsanti` (`.worktrees/` è già in `.gitignore`), ramo `night/c6a-pulsanti`, creato da `master`. Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì (o dalle sue `backend/` e `frontend/`), mai dalla radice del checkout principale. Il checkout principale non si tocca: se vi trovi modifiche non committate, sono dell'utente. **Mai `git stash`.** **Nessun push, nessun merge, nessun deploy.**
- Tutto il colore passa dai token di `frontend/src/index.css`. Nessuna schermata nomina un colore crudo: `grep -rn "emerald\|neutral-" frontend/src` resta vuoto. Ogni testo sta sopra 4,5:1, in chiaro e in scuro.
- Le icone si importano solo da `frontend/src/components/ui/icons.ts` (quelle che servono ci sono già tutte: `IconEye`, `IconEyeOff`, `IconCursorText`, `IconCategory`, `IconArrowsJoin2`, `IconArrowsTransferDown`, `IconBarcodeOff`).
- Regola delle icone (spec §2): **più pulsanti in gruppo → solo icone; un pulsante da solo → icona e testo.** Ogni pulsante di sola icona ha il nome completo come `aria-label`: `Button` con `icon` e `label`.
- **La regola dei pulsanti spenti** (decisa da Mattia, è il cuore di questo piano): una richiesta partita da qui è in volo → `busy`; l'azione non si può *ancora* fare → `unavailableReason` col perché; `disabled` nativo solo dove nessuno dei due vale. Il browser toglie il fuoco a un pulsante che diventa `disabled`, e chi usa la tastiera lo ritrova sul `body`.
- **Nomi accessibili stabili** (spec §6): un pulsante che cambia forma tiene il nome di oggi. «Metti in dispensa N», «Cerca», «Crea l'ingrediente», «Abbina: X», «Riprova ad abbinare X», «Entra», «Rinomina», «Cambia reparto», «Unisci a un altro…», «Spostalo», «Togli il codice», «Sposta l'alias «X»», «Togli l'alias «X»» restano quelli.
- Ogni bersaglio è almeno 44×44 px. A 375 px nessuna schermata scorre di lato.
- **Mai un vicolo cieco.** Un pulsante spento dice perché (è la ragione di `unavailableReason`), e resta raggiungibile.
- Le parole a video sono in italiano e **si copiano esattamente come sono scritte qui**; gli identificatori in inglese; i commenti in italiano, e dicono il perché.
- **Frontend**, sempre da `<worktree>/frontend`: `npx vitest run` (non esiste `npm test`), `npm run lint`, `npm run typecheck`, `npm run build`. Il type check è `npm run typecheck` (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0 (`CLAUDE.md`, settima lezione).
- **Backend** (solo per la verifica finale: questo piano non lo tocca). Il database di test è il container `spena-db-1`: se `docker ps --format '{{.Names}}'` non lo mostra, `docker start spena-db-1` (mai `docker compose up` dal worktree: il nome del progetto Compose viene dalla cartella e ne nascerebbe un secondo Postgres sulla stessa porta). Il venv è quello del checkout principale; da `<worktree>/backend`:
  ```bash
  PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
  `python -m` mette la cartella corrente in testa a `sys.path`: si prova l'`app` del worktree.
- **e2e** (Task 7 e Task 9) sullo stack `spena-e2e`, dalla radice di `<worktree>`. Serve un `.env`: **si copia da `.env.example`, che non ha segreti, solo per la prova, e si cancella alla fine. Mai leggere né copiare il `.env` del checkout principale.** Prima di alzarlo, `docker ps --format '{{.Names}}' | grep spena-e2e`: se c'è e non l'hai alzato tu (un altro piano della notte), non toccarlo e aspetta che sparisca.
  ```bash
  cp .env.example .env
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed --con-ricette
  (cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
  rm .env
  ```
  Il `-p spena-e2e` e il `-f docker-compose.e2e.yml` vanno in ogni comando: un `down -v` sul progetto di default cancellerebbe la dispensa vera. Una prova fallita lascia dati nello stack: prima di rieseguire, `down -v`, poi `up`, seme e prova.
- **Playwright e `aria-disabled`.** `locator.click()` aspetta che l'elemento sia «enabled», e per Playwright un elemento con `aria-disabled="true"` non lo è: il clic resterebbe in attesa fino al timeout. Su un pulsante spento le prove usano la tastiera (`focus()` e `keyboard.press`), come già fa la prova della ✕ in fondo a `style.spec.ts`.
- Nessuna dipendenza nuova, nessuna migrazione, nessun token di colore nuovo.

### Preparazione (una volta, prima del Task 1)

- [ ] Le modifiche della fase giorno (i quattro piani, `next-steps.md`) devono essere su `master` prima del worktree: `git -C /home/mactyws/coding/ais/spena log -1 --format=%s master` e `git -C /home/mactyws/coding/ais/spena status --short`. Se `next-steps.md` o i piani del 2026-09-30 risultano modificati o non tracciati, vanno committati su `master` prima del worktree da chi avvia la notte (come la notte del 2026-09-29); se non lo sono, **fermati** e scrivilo nel report: il Task 8 lavorerebbe su un `next-steps.md` vecchio.
- [ ] Dal checkout principale, allinea `node_modules` al lockfile (non aggiunge dipendenze, installa quelle di `package-lock.json`; il 2026-09-29 erano vecchi e 24 file di test non partivano):
  ```bash
  cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund
  ```
- [ ] Crea il worktree e collega `node_modules` (e solo quello: **niente `.env`**):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/c6a-pulsanti -b night/c6a-pulsanti master
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/c6a-pulsanti/frontend/node_modules
  ```
- [ ] La linea di partenza, dal worktree, **prima del Task 1**:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/c6a-pulsanti/frontend && npx vitest run 2>&1 | grep -E "Test Files|Tests "
  ```
  Expected: tutto verde. L'ultima misura scritta (`docs/prossimi-passi.md`, T3, dopo il merge della Consegna 3 e delle pulizie) è **766 test in 58 file**; annota il numero vero nel report della notte: è la base dei conti di ogni task. Poi il backend (comando sopra, da `<worktree>/backend`): tutto verde, annota il numero (l'ultimo scritto è 940); questo piano non lo cambia. Se una delle due linee non è verde, fermati: non è un difetto di questo piano.

---

## Obiettivo e contesto

Dopo le Consegne 2 e 3 l'app aveva tre modi di spegnere un pulsante: `disabled` nativo (che toglie il fuoco a chi usa la tastiera), `Button busy` (Consegna 2, per le richieste in volo) e `aria-disabled` scritto a mano con la sua guardia e il suo motivo sotto (Consegna 3, in «Sistema la spesa»). In `next-steps.md` c'era la domanda aperta — «una regola sola per i pulsanti spenti: chi vince, e se `Button` impara un «non ancora» col motivo» — e Mattia l'ha decisa il 2026-09-29: in volo `busy`, «non ancora» `unavailableReason`, `disabled` solo dove nessuno dei due vale. Questo piano la scrive dentro `Button`, così i tre piani che seguono la stessa notte (Ricette, Dettaglio, Modulo) la trovano pronta, e la porta nelle schermate che la Consegna 6 doveva comunque toccare: «Sistema la spesa» (dove `aria-disabled` era scritto a mano), l'accesso (che il giro ha trovato senza fuoco e senza modo di vedere la password) e l'Anagrafica (azioni come testo, un campo con due nomi).

## Decisioni prese

Prese di giorno il 2026-09-29 (seconda fase giorno), con Mattia o dal coordinatore; la notte non le riapre.

1. **`Button` impara `unavailableReason?: string`** — «non si può ancora», col perché. Valorizzato: `aria-disabled="true"`, tocco e invio del modulo ignorati come per `busy`, il fuoco resta; `Button` disegna **sotto di sé** un `<p>` col testo (piccolo, `text-ink-faint`, id da `useId`) e lo collega con `aria-describedby`, unito a un eventuale `aria-describedby` del chiamante. *Perché:* un pulsante spento e muto non si spiega da sé (dal giro), e scritto a mano ogni volta il motivo si scollava dal pulsante.
2. **La regola** (Mattia): in volo → `busy`; «non ancora» → `unavailableReason`; `disabled` nativo solo dove nessuno dei due vale.
3. **`Button` impara `accessibleName?: string`**, solo per i pulsanti con testo visibile: diventa `aria-label`; il testo visibile deve stare all'inizio del nome (label-in-name). *Perché:* «Abbina» e «Riprova» di `StockingRow.tsx` ricodificavano il markup di `Button` per dire di quale voce parlavano (idea in `next-steps.md`).
4. **JSDoc di `busy` e `unavailableReason`**: il clic risale comunque ai gestori degli antenati (un `disabled` no). Chiude l'idea in `next-steps.md`.
5. **Sistema la spesa**, i pulsanti scritti a mano passano a `Button`: «Metti in dispensa» (a zero voci `unavailableReason` con la frase di oggi «Scegli come entra almeno una voce: codice, catalogo o sfuso.»; in volo `busy`), «Cerca» (`busy`), «Crea l'ingrediente» (nome vuoto → `unavailableReason`; in volo → `busy`), «Riprova ad abbinare» (`busy`), «Abbina» (`accessibleName="Abbina: X"`). I nomi accessibili restano quelli di oggi.
6. **`IngredientPicker`**: «Aggiungi «…»» passa da `disabled` a `busy`; campo e suggerimenti restano come sono (resta l'idea in `next-steps.md`).
7. **Accesso** (`LoginScreen.tsx`): il campo prende il fuoco all'apertura; «Password errata» se ne va appena si riscrive; «Mostra password» con `IconEye`/`IconEyeOff`, un pulsante di sola icona col nome fisso «Mostra password» e `aria-pressed` che dice se la password è in vista (l'icona passa da occhio a occhio barrato; il nome non cambia, perché nome che cambia *e* `aria-pressed` insieme fanno leggere a uno screen reader «Nascondi password, premuto»: corretto dal coordinatore della fase giorno); «Entra» con `Button` (in volo `busy`, campo vuoto `unavailableReason`).
8. **Anagrafica**: le azioni della scheda ingrediente (Rinomina, Cambia reparto, Unisci a un altro…) e della scheda prodotto (Spostalo, Togli il codice) diventano un `IconToolbar` di `Button` di sola icona (`IconCursorText`, `IconCategory`, `IconArrowsJoin2`, `IconArrowsTransferDown`, `IconBarcodeOff`), coi nomi accessibili di oggi. «Cerca in anagrafica» diventa «Cerca un ingrediente o un prodotto»; il segnaposto di `IngredientPicker` diventa «Cerca un ingrediente».
9. **I `<button disabled>` grezzi dei file toccati da questo piano passano a `Button`** con la regola sopra.
10. Test del primitivo in jsdom, e una prova e2e per quel che jsdom non vede (il fuoco tenuto da un pulsante `unavailableReason`; l'Invio in un modulo col submit «non ancora» che non invia).

Scelte di questo piano, dove le dieci sopra non arrivavano (reversibili; Mattia le rivede):

11. **Il `<p>` del motivo è un fratello del `<button>`**, non un figlio né un contenitore nuovo: `Button` restituisce `<>` `<button>` e, se c'è un motivo, `<p>` `</>`. Un contenitore sempre presente cambierebbe la disposizione di ogni pulsante dell'app; uno presente solo col motivo farebbe rinascere il `<button>` ogni volta che il motivo compare o sparisce, e il fuoco cadrebbe proprio come con `disabled`. Chi passa `unavailableReason` mette il pulsante dove una riga sotto di lui ci sta (una colonna, un blocco), e mai dentro un `<p>`. Classi del `<p>`: `pt-1 text-xs text-ink-faint` (`ink-faint` regge 4,5:1 su `card` e su `page` nei due temi: è scritto in `index.css`).
12. **Una stringa vuota non è un motivo**: `unavailableReason=""` si comporta come se non ci fosse. I chiamanti scrivono `cond ? "…" : undefined`.
13. **`Button` passa anche `aria-expanded` e `aria-pressed`**: servono a «Spostalo» e «Sposta» (che aprono qualcosa, e oggi portano `aria-expanded`) e all'occhio dell'accesso (`aria-pressed`). Due attributi in più nel tipo `Common`, nessun comportamento.
14. **I gruppi di icone dell'Anagrafica stanno nell'`action` di `Screen`**, accanto al titolo (lo stesso posto che il piano 3 usa per Modifica/Elimina del dettaglio), con la variante `ghost` come le icone di «Sistema la spesa». Il gruppo si chiama «Correzioni dell'ingrediente» e «Correzioni del prodotto». Nella scheda prodotto lo spostamento (`IngredientPicker` «Sposta sotto») si apre sotto l'intestazione, come i pannelli della scheda dell'ingrediente, e la domanda «È sotto l'ingrediente sbagliato?» che introduceva il pulsante se ne va con lui. «Togli il codice» è nel gruppo solo quando c'è un codice, come oggi.
15. **Nelle correzioni dell'ingrediente, un valore invariato è «non ancora»**: «Salva il nome» dice «Scrivi un nome per salvarlo.» (la frase di oggi) a nome vuoto e «È già il suo nome: scrivine un altro.» a nome invariato; «Salva il reparto» dice «È già il suo reparto: scegline un altro.». Il pulsante e «Lascia com'è» vanno in colonna, perché il motivo sotto «Salva» non spinga a capo «Lascia com'è» a metà riga.
16. **Si convertono solo i `<button>` grezzi con `disabled`**, più quelli che diventano icone del gruppo e quelli che la decisione 5 nomina. Gli altri `<button>` grezzi dei file toccati («Riprova» del caricamento fallito, «Uniscili», «Cambia reparto» e «Riprova» dentro `MergePanel`, «Elimina il prodotto», «Lascia», «Lascia com'è») restano come sono: non si spengono mai, e la regola non li riguarda.
17. **`InlineField.tsx` resta fuori** (il «Salva» accanto a nome, marca e codice del prodotto): non è fra i file che questo piano tocca per altre ragioni, il suo «Salva» sta nella riga del campo, dove un motivo sotto il pulsante stringerebbe il campo, e il suo stato «invariato» è quello di ogni campo a riposo — tre righe «è com'era» fisse sulla scheda sarebbero rumore. Va in `next-steps.md` come idea (Task 8), col difetto che resta: dopo un salvataggio riuscito il «Salva» si spegne con `disabled` e il fuoco cade.
18. **Nell'Anagrafica l'etichetta visibile diventa il nome del campo**: oggi si vede «Cerca» e si sente «Cerca in anagrafica» (due nomi per un campo). Ora l'etichetta in vista è «Cerca un ingrediente o un prodotto», senza `aria-label`; il segnaposto resta l'esempio «pomodoro, Fage…».
19. **Accesso**: ogni errore se ne va riscrivendo, non solo «Password errata» (anche «Impossibile contattare il server», che al tentativo dopo tornerebbe da sé se vale ancora); il campo mostrato come testo non prende la maiuscola né il correttore del telefono (`autoCapitalize="none"`, `autoCorrect="off"`, `spellCheck={false}`); il motivo di «Entra» è «Scrivi la password per entrare.», e «Entra» sta in un contenitore suo, perché il motivo gli stia attaccato e non a 16 px come le righe della colonna.
20. **Gli e2e cercano il campo con `getByLabel("Password", { exact: true })`**: `getByLabel` di Playwright confronta anche gli `aria-label`, per sottostringa e senza badare alle maiuscole, quindi «Password» troverebbe anche il pulsante «Mostra password» e ogni `fill` fallirebbe per ambiguità. Dodici righe in dieci file, cambiate insieme al pulsante (Task 4).

## Criteri di accettazione

- [ ] `Button` con `unavailableReason`: `aria-disabled="true"`, nessun `disabled`, tocco e Invio non chiamano `onClick` né inviano il modulo, il fuoco resta; il motivo è un `<p>` sotto, e la descrizione accessibile del pulsante (unita a quella del chiamante). Senza motivo il `<p>` non c'è e il `<button>` è lo stesso elemento di prima.
- [ ] `Button` con `accessibleName`: il nome è quello, il testo in vista resta; non compila su un pulsante di sola icona.
- [ ] Il JSDoc di `busy` e `unavailableReason` dice che il clic risale agli antenati, e un test lo fissa.
- [ ] In `frontend/src/features/stocking/` nessun `aria-disabled=` scritto a mano: `grep -rn "aria-disabled=" frontend/src/features/stocking --include=*.tsx | grep -v test` è vuoto. «Metti in dispensa» a zero voci ha come descrizione «Scegli come entra almeno una voce: codice, catalogo o sfuso.».
- [ ] «Aggiungi «…»» di `IngredientPicker` si spegne con `aria-disabled`; il segnaposto del campo è «Cerca un ingrediente».
- [ ] Accesso: il campo ha il fuoco all'apertura; a campo vuoto «Entra» è spento col perché e né tocco né Invio mandano niente; in volo è spento e tiene il fuoco; «Password errata» sparisce alla prima battuta; «Mostra password» (nome fisso) con `aria-pressed`, da 44 px, mostra e rinasconde la password.
- [ ] Anagrafica: «Correzioni dell'ingrediente» (tre icone) e «Correzioni del prodotto» (due, o una senza codice) accanto al titolo, a 375 px su una riga, 44×44 px, senza scorrimento di lato; nessun `<button disabled>` grezzo in `IngredientScreen.tsx`, `ProductScreen.tsx`, `RenameForm.tsx`, `CategoryForm.tsx`, `MergePanel.tsx`, `AliasRow.tsx`, `LoginScreen.tsx`. Il campo dell'Anagrafica si chiama «Cerca un ingrediente o un prodotto», e quel nome si vede.
- [ ] Ogni test di oggi passa, migrato solo dove un controllo ha cambiato forma (elenco nei Task 5 e 6), mai indebolito.
- [ ] vitest, typecheck, lint, build, pytest e l'e2e intera verdi; `style.spec.ts` ha due prove nuove a 375×812.
- [ ] `docs/prossimi-passi.md` e `next-steps.md` aggiornati (Task 8).

## Comandi di verifica

Da `<worktree>/frontend`:

```bash
npx vitest run
npm run typecheck
npx tsc -b --force
npm run lint
npm run build
```

Da `<worktree>/backend`:

```bash
PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Dalla radice di `<worktree>`:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -rn "aria-disabled=" frontend/src/features/stocking --include=*.tsx | grep -v "\.test\."
grep -rn "Cerca in anagrafica" frontend/src frontend/e2e
grep -rn 'getByLabel("Password")' frontend/e2e
grep -n -B1 -A4 "<button" frontend/src/features/registry/IngredientScreen.tsx frontend/src/features/registry/ProductScreen.tsx frontend/src/features/registry/RenameForm.tsx frontend/src/features/registry/CategoryForm.tsx frontend/src/features/registry/MergePanel.tsx frontend/src/features/registry/AliasRow.tsx frontend/src/features/auth/LoginScreen.tsx | grep "disabled"
```

Expected: i cinque `grep` non stampano niente. E l'e2e intera con i comandi delle Global Constraints.

## Fuori scope

- Tutto ciò che appartiene ai piani 2, 3 e 4 della stessa notte: il ricettario (Consegna 4), il dettaglio della ricetta (Consegna 5), il modulo della ricetta, la coda d'import, le parole a video, `CategorySelect` e le maiuscole (Consegna 6b). In particolare non si tocca `NewIngredientFields.tsx` oltre al suo pulsante, né il `<select>` del reparto.
- `InlineField.tsx` (decisione 17), `CustomProductForm.tsx` («Salva prodotto» resta con `disabled`), `AiDraftScreen.tsx` e `RecipeForm.tsx` (piano 4), `DecidedTermRow.tsx`: tutti con `disabled` oggi, nessuno toccato qui.
- I controlli che non sono pulsanti e già usano `aria-disabled` a mano per la stessa ragione: le tacche (`StockGauge.tsx`), la casella della lista (`ListRow.tsx`), il pulsante della scadenza in dispensa (`PantryRow.tsx`). Sono una casella, un `radio` e un pulsante con un `ref` che `Button` non passa: restano come sono.
- Campo e suggerimenti di `IngredientPicker` spenti con `disabled` mentre la scelta è in volo (decisione 6).
- I due pulsanti di testo «Sposta» e «Togli» di ogni alias (`AliasRow.tsx`) restano di testo: cambiano solo in `Button` con `busy` e `accessibleName`.
- Il backend, `CLAUDE.md`, il README.

## Margine di autonomia

- **Liberi:** i nomi di variabili locali e helper di test; l'ordine dei test dentro un file; la formulazione dei commenti, purché dicano il perché.
- **Fissi:** le parole a video, esattamente come scritte qui («Scegli come entra almeno una voce: codice, catalogo o sfuso.», «Scrivi il nome per crearlo.», «Scrivi la password per entrare.», «Scrivi un nome per salvarlo.», «È già il suo nome: scrivine un altro.», «È già il suo reparto: scegline un altro.», «Mostra password», «Correzioni dell'ingrediente», «Correzioni del prodotto», «Cerca un ingrediente o un prodotto», «Cerca un ingrediente»); i nomi accessibili elencati nelle Global Constraints; le prop pubbliche di `Button` (`unavailableReason`, `accessibleName`, `busy`, `aria-expanded`, `aria-pressed`) e il loro comportamento, che i piani 2, 3 e 4 usano.
- **Nessuna dipendenza nuova**, nessuna migrazione, nessun token di colore nuovo, nessun cambio di configurazione.
- **Un test di oggi si cambia solo per seguire un controllo che ha cambiato forma**, mai per indebolirlo: un `toBeDisabled` diventa `aria-disabled="true"` + nessun `disabled` + «un tocco non fa niente». Le migrazioni ammesse sono elencate nei Task 5 e 6; se ne serve un'altra, scrivila nel report col perché.
- **Una decisione non coperta da questo piano e non reversibile** → si ferma quel task, si fa commit del lavoro parziale sul ramo, lo si segna `bloccato` in `next-steps.md` con la domanda precisa, e si passa al task successivo che non ne dipende. Una scelta reversibile e a basso impatto → la più conservativa, annotata nel report della notte (`docs/night-reports/<data>.md`).
- Se un test fallisce e non si risolve in modo ragionevole: niente test disattivati, niente asserzioni indebolite; `bloccato` con la diagnosi.

## Dipendenze

**Primo della catena.** Il ramo `night/c6a-pulsanti` parte da `master` com'è quando la notte comincia, con le modifiche della fase giorno già committate (vedi la Preparazione). Non dipende da nessun altro piano.

Dopo di lui, nell'ordine e ciascuno dal ramo del precedente: `night/c4-ricette` (piano `2026-09-30-ridisegno-ricette.md`), `night/c5-dettaglio` (`2026-09-30-ridisegno-dettaglio-ricetta.md`), `night/c6b-modulo-coda-parole` (`2026-09-30-ridisegno-modulo-coda-parole.md`). Da questo ramo usano:
- `Button` con `unavailableReason` (piano 3: lo stepper delle porzioni senza porzioni; piano 4: «Salva» del modulo), `busy` (tutti), `accessibleName` e `aria-expanded` (piano 2: «Filtri» apre un pannello in linea). Attenzione per il piano 3: il `<p>` del motivo nasce accanto a **ogni** pulsante che lo porta, quindi due pulsanti con lo stesso motivo lo scrivono due volte.
- il segnaposto «Cerca un ingrediente» di `IngredientPicker` (tutti i selettori del mondo ricette);
- gli e2e con `getByLabel("Password", { exact: true })`: ogni prova nuova degli altri piani deve cercare il campo così.

Se questo ramo finisce `bloccato` a metà, gli altri tre partono comunque dal suo ultimo commit: il Task 1 (`Button`) è quello da cui dipendono, e va chiuso per primo.

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `frontend/src/components/ui/Button.tsx` | 1 | `unavailableReason`, `accessibleName`, `aria-expanded`, `aria-pressed`, JSDoc |
| `frontend/src/components/ui/Button.test.tsx` | 1 | nove test |
| `frontend/src/features/stocking/StockingScreen.tsx` (+ test) | 2 | «Metti in dispensa» con `Button` |
| `frontend/src/features/stocking/ScannerPanel.tsx` | 2 | «Cerca» con `Button busy` |
| `frontend/src/features/stocking/NewIngredientFields.tsx` (+ test) | 2 | «Crea l'ingrediente» con `Button` |
| `frontend/src/features/stocking/StockingRow.tsx` (+ test) | 2 | «Abbina» e «Riprova» con `accessibleName` |
| `frontend/src/components/IngredientPicker.tsx` (+ test) | 3 | «Aggiungi «…»» `busy`, segnaposto |
| `frontend/src/features/auth/LoginScreen.tsx` (+ test) | 4 | fuoco, errore che se ne va, occhio, «Entra» |
| `frontend/e2e/*.spec.ts` (dieci file) | 4 | `getByLabel("Password", { exact: true })` |
| `frontend/src/features/registry/IngredientScreen.tsx` (+ test) | 5 | il gruppo di icone |
| `frontend/src/features/registry/RenameForm.tsx`, `CategoryForm.tsx`, `MergePanel.tsx`, `AliasRow.tsx` | 5 | `Button` con la regola |
| `frontend/src/features/registry/ProductScreen.tsx` (+ test) | 6 | il gruppo di icone, `busy` |
| `frontend/src/features/registry/RegistryScreen.tsx` (+ test) | 6 | «Cerca un ingrediente o un prodotto» |
| `frontend/e2e/anagrafica.spec.ts` | 6 | il nome nuovo del campo |
| `frontend/e2e/style.spec.ts` | 6, 7 | il nome nuovo del campo; due prove nuove |
| `docs/prossimi-passi.md`, `next-steps.md` | 8 | i documenti |

---

### Task 1: `Button` impara «non ancora» e un nome più lungo del testo

**Files:**
- Modify: `frontend/src/components/ui/Button.tsx` (per intero)
- Test: `frontend/src/components/ui/Button.test.tsx`

**Interfaces:**
- Produces: `Button` accetta, in tutte e due le forme, `unavailableReason?: string`, `"aria-expanded"?: boolean`, `"aria-pressed"?: boolean`; nella forma con testo `accessibleName?: string` (nella forma di sola icona non compila). `busy` e `unavailableReason` → `aria-disabled="true"`, niente `disabled`, clic e invio del modulo ignorati (il clic risale agli antenati). `unavailableReason` non vuoto → un `<p id>` fratello, dopo il `<button>`, con classi `pt-1 text-xs text-ink-faint`, collegato con `aria-describedby` dopo gli id del chiamante. Lo consumano i Task 2–6 e i piani 2, 3 e 4.

- [ ] **Step 1: Scrivere i test che falliscono**

In `frontend/src/components/ui/Button.test.tsx` cambia le prime righe:

```tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Button } from "./Button";
import { buttonClasses, type ButtonShape, type ButtonVariant } from "./buttonClasses";
import { IconToolbar } from "./IconToolbar";
import { IconPencil, IconTrash } from "./icons";
```

in:

```tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "./Button";
import { buttonClasses, type ButtonShape, type ButtonVariant } from "./buttonClasses";
import { IconToolbar } from "./IconToolbar";
import { IconEye, IconLink, IconPencil, IconTrash } from "./icons";
```

Poi, dentro il `describe("Button", …)`, subito dopo il test «disabled resta, per un'azione che adesso non si può proprio fare» (l'ultimo del blocco), aggiungi:

```tsx
  // `unavailableReason` (T3 Consegna 6a, la regola di Mattia): in volo → `busy`; «non si
  // può ancora» → `unavailableReason`, col perché; `disabled` solo dove nessuno dei due
  // vale. Il perché lo scrive `Button` sotto di sé, e lo lega al pulsante: prima ogni
  // chiamante lo scriveva a mano, e si scollava.
  it("«non ancora» è spento con aria-disabled, dice perché sotto e nella descrizione, e un tocco non fa niente", () => {
    const onClick = vi.fn();
    render(
      <Button onClick={onClick} unavailableReason="Scrivi il nome per crearlo.">
        Crea
      </Button>
    );
    const button = screen.getByRole("button", { name: "Crea" });
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button.hasAttribute("disabled")).toBe(false);
    expect(button).toHaveAccessibleDescription("Scrivi il nome per crearlo.");
    const reason = screen.getByText("Scrivi il nome per crearlo.");
    // sotto il pulsante, non dentro: il nome resta «Crea»
    expect(reason.tagName).toBe("P");
    expect(button.compareDocumentPosition(reason) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(reason.className.split(/\s+/)).toContain("text-ink-faint");
    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("«non ancora» resta raggiungibile dal fuoco, e diventato pronto è lo stesso pulsante", () => {
    const onClick = vi.fn();
    const { rerender } = render(
      <Button onClick={onClick} unavailableReason="Manca il nome.">
        Salva
      </Button>
    );
    const button = screen.getByRole("button", { name: "Salva" });
    button.focus();
    expect(button).toHaveFocus();
    rerender(<Button onClick={onClick}>Salva</Button>);
    // lo stesso elemento, col fuoco: un `<button>` rinato lo avrebbe perso
    expect(screen.getByRole("button", { name: "Salva" })).toBe(button);
    expect(button).toHaveFocus();
    expect(button).not.toHaveAttribute("aria-disabled");
    expect(button).not.toHaveAttribute("aria-describedby");
    expect(screen.queryByText("Manca il nome.")).toBeNull();
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("il perché si aggiunge alla descrizione del chiamante, non la sostituisce", () => {
    render(
      <>
        <p id="nota-di-prova">Serve la rete.</p>
        <Button aria-describedby="nota-di-prova" unavailableReason="Manca il nome.">
          Salva
        </Button>
      </>
    );
    expect(screen.getByRole("button", { name: "Salva" })).toHaveAccessibleDescription(
      "Serve la rete. Manca il nome."
    );
  });

  it("un submit «non ancora» non invia il modulo, né col tocco né con l'Invio nel campo", async () => {
    const onSubmit = vi.fn((event: { preventDefault: () => void }) => event.preventDefault());
    render(
      <form onSubmit={onSubmit}>
        <label>
          Nome
          <input />
        </label>
        <Button type="submit" unavailableReason="Scrivi il nome per salvarlo.">
          Salva
        </Button>
      </form>
    );
    // l'Invio in un campo arriva al submit come un clic sul pulsante (l'invio implicito
    // del browser): è quel clic che `Button` rifiuta
    await userEvent.type(screen.getByLabelText("Nome"), "{Enter}");
    await userEvent.click(screen.getByRole("button", { name: "Salva" }));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("un motivo vuoto non è un motivo: il pulsante risponde, e sotto non c'è niente", () => {
    const onClick = vi.fn();
    const { container } = render(
      <Button onClick={onClick} unavailableReason="">
        Salva
      </Button>
    );
    const button = screen.getByRole("button", { name: "Salva" });
    expect(button).not.toHaveAttribute("aria-disabled");
    expect(container.querySelector("p")).toBeNull();
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("spento, il clic risale comunque agli antenati: si ignora solo dentro Button (vedi il JSDoc)", () => {
    // un `disabled` non manderebbe nessun clic; `aria-disabled` sì, e il gestore di un
    // antenato lo riceve. Nessun chiamante di oggi ne dipende: il test fissa quel che
    // il JSDoc promette, così chi lo cambia lo cambia apposta
    const onParent = vi.fn();
    const onClick = vi.fn();
    render(
      <div onClick={onParent}>
        <Button onClick={onClick} busy>
          In volo
        </Button>
        <Button onClick={onClick} unavailableReason="Non ancora.">
          Non ancora
        </Button>
      </div>
    );
    fireEvent.click(screen.getByRole("button", { name: "In volo" }));
    fireEvent.click(screen.getByRole("button", { name: "Non ancora" }));
    expect(onClick).not.toHaveBeenCalled();
    expect(onParent).toHaveBeenCalledTimes(2);
  });

  // `accessibleName` (Consegna 6a): un pulsante con testo che deve dire di più di quel
  // che mostra. «Abbina» e «Riprova» in «Sistema la spesa» ricodificavano il markup di
  // Button per riuscirci (idea di `next-steps.md`).
  it("con accessibleName il nome è quello, e il testo che si vede ne è l'inizio", () => {
    render(
      <Button icon={IconLink} accessibleName="Abbina: cosa strana">
        Abbina
      </Button>
    );
    const button = screen.getByRole("button", { name: "Abbina: cosa strana" });
    expect(button.textContent).toBe("Abbina");
    // label-in-name (WCAG 2.5.3): chi comanda a voce dice quel che vede
    expect("Abbina: cosa strana".startsWith(button.textContent!)).toBe(true);
  });

  it("accessibleName non compila su un pulsante di sola icona (vedi il @ts-expect-error qui dentro)", () => {
    // la forma di sola icona ha già `label`: due nomi per lo stesso pulsante sarebbero
    // un modo di sbagliarne uno
    // @ts-expect-error `accessibleName` è solo della forma con testo
    render(<Button icon={IconTrash} label="Elimina" accessibleName="Elimina tutto" />);
  });

  it("passa aria-pressed e aria-expanded, per un interruttore e per chi apre qualcosa", () => {
    render(
      <>
        <Button icon={IconEye} label="Mostra password" aria-pressed={false} />
        <Button aria-expanded={true}>Spostalo</Button>
      </>
    );
    expect(screen.getByRole("button", { name: "Mostra password" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "Spostalo" })).toHaveAttribute("aria-expanded", "true");
  });
```

- [ ] **Step 2: Farli fallire**

Run (da `<worktree>/frontend`): `npx vitest run src/components/ui/Button.test.tsx`
Expected: FAIL. Vitest non controlla i tipi: falliscono «non ancora è spento…» (niente `aria-disabled`), «il perché si aggiunge…», «un submit non ancora…», «con accessibleName…» (il nome è «Abbina»), «spento, il clic risale…» (il pulsante «Non ancora» chiama `onClick`), «passa aria-pressed…». Possono già passare ««non ancora» resta raggiungibile dal fuoco…» (oggi il motivo è ignorato, e il pulsante è sempre attivo), «un motivo vuoto…» e «accessibleName non compila…» (a runtime non fa niente). `npm run typecheck` fallirebbe anche lui: le prop nuove non esistono.

- [ ] **Step 3: Scrivere `Button`**

Sostituisci `frontend/src/components/ui/Button.tsx` per intero con:

```tsx
import { useId, type MouseEvent, type ReactNode } from "react";
import { buttonClasses, type ButtonShape, type ButtonVariant } from "./buttonClasses";
import type { IconComponent } from "./icons";

// La regola dei pulsanti spenti, una per tutta l'app (T3 Consegna 6a, decisa da Mattia):
// - una richiesta partita da qui è in volo → `busy`;
// - l'azione non si può ancora fare, e chi guarda può rimediare → `unavailableReason`,
//   col perché scritto sotto;
// - `disabled` nativo solo dove nessuna delle due vale.
// `busy` e `unavailableReason` spengono con `aria-disabled` e non con `disabled`: il
// browser toglie il fuoco a un pulsante che diventa `disabled`, e chi usa la tastiera lo
// ritrova sul `body`; e un `disabled` non si raggiunge nemmeno col Tab, quindi il suo
// perché non lo sente nessuno.
type Common = {
  variant?: ButtonVariant;
  shape?: ButtonShape;
  type?: "button" | "submit";
  onClick?: () => void;
  /** Un'azione che adesso non si può fare, dove non c'è niente da aspettare né da
   * spiegare. Il browser toglie il fuoco a un pulsante che diventa `disabled`: per «sto
   * già lavorando» c'è `busy`, per «non ancora» c'è `unavailableReason`. */
  disabled?: boolean;
  /** Una richiesta partita da qui è in volo (T3 Consegna 2). Il pulsante si spegne con
   * `aria-disabled` e non con `disabled`, così tiene il fuoco: dopo una ✕ fallita chi
   * naviga da tastiera lo ritrovava sul `body`. Il tocco si ignora qui dentro, e non in
   * ogni chiamante, perché nessuno possa dimenticare la guardia — come fanno a mano le
   * tacche (`StockGauge`) e la casella della lista.
   *
   * Il clic risale comunque ai gestori `onClick` degli antenati: si ignora solo qui
   * dentro, mentre un pulsante `disabled` non ne manda nessuno. Nessun chiamante di oggi
   * sta dentro un elemento cliccabile; chi ce lo mette lo guardi. */
  busy?: boolean;
  /** «Non si può ancora», col perché (T3 Consegna 6a): il nome vuoto, niente di scelto.
   * Spento con `aria-disabled` come `busy`: tocco e invio del modulo si ignorano qui
   * dentro — anche l'Invio in un campo, che il browser fa arrivare al submit come un
   * clic su questo pulsante — e il fuoco resta. Il perché lo scrive `Button` sotto di sé,
   * in un `<p>` piccolo, e lo collega con `aria-describedby` dopo quello del chiamante:
   * chi ascolta lo sente arrivando sul pulsante, chi guarda lo legge sotto.
   *
   * Il `<p>` è un fratello del `<button>`, non un figlio: il chiamante mette il pulsante
   * dove una riga sotto di lui ci sta (una colonna, un blocco), e mai dentro un `<p>`.
   * Una stringa vuota non è un motivo. Come per `busy`, il clic risale comunque agli
   * antenati. */
  unavailableReason?: string;
  className?: string;
  "aria-describedby"?: string;
  /** Per chi apre e chiude qualcosa sotto di sé («Spostalo», «Sposta»). */
  "aria-expanded"?: boolean;
  /** Per un interruttore («Mostra password»). */
  "aria-pressed"?: boolean;
};

// Le due forme della regola delle icone (spec T3 §2), e nessuna terza: un pulsante di
// sola icona senza `label` non compila, perché un pulsante muto per uno screen reader
// è un pulsante che non c'è.
type WithText = Common & {
  children: ReactNode;
  icon?: IconComponent;
  label?: never;
  /** Il nome per chi ascolta, quando deve dire più del testo in vista: «Abbina» si
   * sente «Abbina: cosa strana» (T3 Consegna 6a). Il testo in vista sta all'inizio del
   * nome (WCAG 2.5.3, «label in name»): chi comanda a voce dice quel che vede. Prima lo
   * si otteneva con uno `sr-only` dentro al pulsante — che Chromium staccava con uno
   * spazio — o riscrivendo a mano il markup di questo componente. */
  accessibleName?: string;
};
type IconOnly = Common & {
  icon: IconComponent;
  label: string;
  children?: never;
  accessibleName?: never;
};

export function Button(props: WithText | IconOnly) {
  const {
    variant = "secondary",
    type = "button",
    onClick,
    disabled,
    busy = false,
    unavailableReason,
    className = "",
  } = props;
  const reasonId = useId();
  const Icon = props.icon;
  const iconOnly = props.label !== undefined;
  const shape = props.shape ?? (iconOnly ? "icon" : "pill");
  // una stringa vuota non è un motivo: i chiamanti scrivono `cond ? "…" : undefined`
  const reason = unavailableReason ? unavailableReason : null;
  const inert = busy || reason !== null;
  const describedBy =
    [props["aria-describedby"], reason !== null ? reasonId : undefined].filter(Boolean).join(" ") ||
    undefined;

  function handleClick(event: MouseEvent<HTMLButtonElement>) {
    if (inert) {
      // anche l'invio del modulo: un submit in volo non deve partire una seconda volta,
      // e uno «non ancora» non deve partire affatto
      event.preventDefault();
      return;
    }
    onClick?.();
  }

  // Un frammento, sempre: il `<button>` resta il primo figlio con o senza motivo, e
  // React non lo fa rinascere quando il motivo compare o sparisce — rinato, perderebbe
  // il fuoco proprio come con `disabled`
  return (
    <>
      <button
        type={type}
        onClick={handleClick}
        disabled={disabled}
        aria-disabled={inert || undefined}
        aria-label={iconOnly ? props.label : props.accessibleName}
        aria-describedby={describedBy}
        aria-expanded={props["aria-expanded"]}
        aria-pressed={props["aria-pressed"]}
        className={`${buttonClasses(variant, shape)} ${className}`}
      >
        {Icon && <Icon aria-hidden="true" className={iconOnly ? "size-5" : "size-[1.1em]"} stroke={1.8} />}
        {props.children}
      </button>
      {reason !== null && (
        <p id={reasonId} className="pt-1 text-xs text-ink-faint">
          {reason}
        </p>
      )}
    </>
  );
}
```

- [ ] **Step 4: Farli passare**

Run: `npx vitest run src/components/ui/Button.test.tsx`
Expected: PASS, tutto il file (i test di oggi compresi: `busy` non è cambiato).

- [ ] **Step 5: Le verifiche del frontend**

Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde; vitest = linea di partenza + 9. Typecheck pulito vuol dire anche che il `@ts-expect-error` nuovo dà davvero errore.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ui/Button.tsx frontend/src/components/ui/Button.test.tsx
git commit -m "ui: Button impara unavailableReason (non ancora, col perché) e accessibleName"
```

---

### Task 2: «Sistema la spesa» senza pulsanti scritti a mano

**Files:**
- Modify: `frontend/src/features/stocking/StockingScreen.tsx` (il blocco di «Metti in dispensa», ~righe 537-553)
- Modify: `frontend/src/features/stocking/ScannerPanel.tsx` («Cerca», ~righe 156-165, e un import)
- Modify: `frontend/src/features/stocking/NewIngredientFields.tsx` («Crea l'ingrediente», ~righe 83-97, e un import)
- Modify: `frontend/src/features/stocking/StockingRow.tsx` («Abbina» ~righe 175-194, «Riprova» ~righe 207-221, un import)
- Test: `frontend/src/features/stocking/StockingScreen.test.tsx`, `NewIngredientFields.test.tsx`, `StockingRow.test.tsx`

**Interfaces:**
- Consumes: `Button` con `busy`, `unavailableReason`, `accessibleName` (Task 1).
- Produces: niente di nuovo; nomi accessibili e testi a video invariati.

I test di oggi di questi file provano già `aria-disabled`, il tocco ignorato e i nomi: restano tutti come sono e devono restare verdi. I test nuovi provano quel che la migrazione aggiunge — il motivo come descrizione del pulsante, il testo in vista di «Riprova».

- [ ] **Step 1: Scrivere i test che falliscono**

`frontend/src/features/stocking/StockingScreen.test.tsx`, nel test «non manda in dispensa nulla se non hai confermato niente», sostituisci:

```tsx
    const stock = screen.getByRole("button", { name: "Metti in dispensa" });
    expect(stock).toHaveAttribute("aria-disabled", "true");
    expect(
      screen.getByText("Scegli come entra almeno una voce: codice, catalogo o sfuso.")
    ).toBeDefined();
    await userEvent.click(stock);
```

con:

```tsx
    const stock = screen.getByRole("button", { name: "Metti in dispensa" });
    expect(stock).toHaveAttribute("aria-disabled", "true");
    expect(stock.hasAttribute("disabled")).toBe(false);
    // il perché non è solo scritto sotto: è la descrizione del pulsante, e chi ci arriva
    // da tastiera lo sente (`unavailableReason`, Consegna 6a)
    expect(stock).toHaveAccessibleDescription(
      "Scegli come entra almeno una voce: codice, catalogo o sfuso."
    );
    expect(
      screen.getByText("Scegli come entra almeno una voce: codice, catalogo o sfuso.")
    ).toBeDefined();
    await userEvent.click(stock);
```

`frontend/src/features/stocking/NewIngredientFields.test.tsx`, nel test «senza nome non crea, e dice perché», sostituisci:

```tsx
    expect(create).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText("Scrivi il nome per crearlo.")).toBeDefined();
```

con:

```tsx
    expect(create).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText("Scrivi il nome per crearlo.")).toBeDefined();
    // `unavailableReason` (Consegna 6a): il perché è anche la descrizione del pulsante
    expect(create).toHaveAccessibleDescription("Scrivi il nome per crearlo.");
```

e subito dopo quel test aggiungi:

```tsx
  it("a nome vuoto nemmeno l'Invio nel campo crea", async () => {
    const { onSubmit } = renderFields({ initialName: "" });
    await userEvent.type(screen.getByLabelText("Come si chiama in generale?"), "{Enter}");
    expect(onSubmit).not.toHaveBeenCalled();
  });
```

`frontend/src/features/stocking/StockingRow.test.tsx`, nel test «una voce senza ingrediente è chiusa: solo «Abbina»», sostituisci:

```tsx
    await userEvent.click(screen.getByRole("button", { name: "Abbina: cosa strana" }));
    expect(onOpen).toHaveBeenCalledWith("match");
```

con:

```tsx
    const abbina = screen.getByRole("button", { name: "Abbina: cosa strana" });
    // label-in-name: il testo in vista è l'inizio del nome
    expect(abbina.textContent).toBe("Abbina");
    await userEvent.click(abbina);
    expect(onOpen).toHaveBeenCalledWith("match");
```

e in fondo al `describe`, dopo «mentre riprova, «Riprova» si spegne ma tiene il fuoco, e non riparte», aggiungi:

```tsx
  it("«Riprova» mostra solo la sua parola, e il nome dice cosa riprova", () => {
    renderRow({ item: STRANA, ingredientId: "i9", matchNotSaved: true });
    const retry = screen.getByRole("button", { name: "Riprova ad abbinare cosa strana" });
    // prima il resto del nome stava in uno `sr-only` dentro al pulsante; ora è
    // `accessibleName` di Button, e il testo in vista ne è l'inizio (label-in-name)
    expect(retry.textContent).toBe("Riprova");
    expect(retry.querySelector(".sr-only")).toBeNull();
  });
```

- [ ] **Step 2: Farli fallire**

Run (da `<worktree>/frontend`): `npx vitest run src/features/stocking`
Expected: FAIL in tre punti: `toHaveAccessibleDescription` in `StockingScreen.test.tsx` e in `NewIngredientFields.test.tsx` (oggi il motivo non è collegato), e ««Riprova» mostra solo la sua parola» (oggi `textContent` è «Riprova ad abbinare cosa strana»). «a nome vuoto nemmeno l'Invio» e l'asserzione su «Abbina» passano già: fissano quel che non deve cambiare.

- [ ] **Step 3: «Metti in dispensa»**

In `frontend/src/features/stocking/StockingScreen.tsx` sostituisci:

```tsx
                {/* `aria-disabled` e non `disabled`: mentre la sistemazione è in volo il
                    fuoco resta qui. Il numero è quello delle voci che partono davvero */}
                <button
                  type="button"
                  onClick={submitStock}
                  aria-disabled={entries.length === 0 || stock.isPending || undefined}
                  className={`${buttonClasses("primary", "block")} aria-disabled:opacity-40`}
                >
                  <IconPackageImport aria-hidden="true" className="size-[1.1em]" stroke={1.8} />
                  {entries.length > 0 ? `Metti in dispensa ${entries.length}` : "Metti in dispensa"}
                </button>
                {/* un pulsante spento e muto non si spiega da sé (dal giro) */}
                {entries.length === 0 && (
                  <p className="text-xs text-ink-soft">
                    Scegli come entra almeno una voce: codice, catalogo o sfuso.
                  </p>
                )}
```

con:

```tsx
                {/* `busy` in volo, `unavailableReason` a zero voci (Consegna 6a): tutti e
                    due tengono il fuoco, e il perché — un pulsante spento e muto non si
                    spiega da sé, dal giro — lo scrive Button sotto di sé. Il numero è
                    quello delle voci che partono davvero */}
                <Button
                  variant="primary"
                  shape="block"
                  icon={IconPackageImport}
                  busy={stock.isPending}
                  unavailableReason={
                    entries.length === 0
                      ? "Scegli come entra almeno una voce: codice, catalogo o sfuso."
                      : undefined
                  }
                  onClick={submitStock}
                >
                  {entries.length > 0 ? `Metti in dispensa ${entries.length}` : "Metti in dispensa"}
                </Button>
```

`submitStock` resta com'è, guardia compresa. `buttonClasses` resta importato: lo usa il collegamento «Vai alla Lista».

- [ ] **Step 4: «Cerca»**

In `frontend/src/features/stocking/ScannerPanel.tsx` sostituisci:

```tsx
            <button
              type="button"
              aria-disabled={lookup.isPending || undefined}
              onClick={search}
              className={`${buttonClasses("secondary")} shrink-0 aria-disabled:opacity-40`}
            >
              {/* un pulsante da solo → icona e testo (spec §3.3); il nome resta «Cerca» */}
              <IconSearch aria-hidden="true" className="size-[1.1em]" stroke={1.8} />
              Cerca
            </button>
```

con:

```tsx
            {/* un pulsante da solo → icona e testo (spec §3.3); il nome resta «Cerca».
                `busy` (Consegna 6a): mentre cerca tiene il fuoco. A campo vuoto non c'è
                niente da spiegare: `search` non fa niente, come prima */}
            <Button icon={IconSearch} busy={lookup.isPending} onClick={search} className="shrink-0">
              Cerca
            </Button>
```

e togli la riga `import { buttonClasses } from "../../components/ui/buttonClasses";` (non la usa più nessuno nel file).

- [ ] **Step 5: «Crea l'ingrediente»**

In `frontend/src/features/stocking/NewIngredientFields.tsx` sostituisci:

```tsx
      <div>
        {/* `aria-disabled` e non `disabled`: mentre la creazione è in volo il fuoco
            resta qui invece di cadere sul `body` */}
        <button
          type="submit"
          aria-disabled={busy || trimmed === "" || undefined}
          className={`${buttonClasses("primary", "block")} aria-disabled:opacity-40`}
        >
          Crea l'ingrediente
        </button>
        {/* un pulsante spento e muto non si spiega da sé */}
        {trimmed === "" && (
          <p className="pt-2 text-xs text-ink-soft">Scrivi il nome per crearlo.</p>
        )}
      </div>
```

con:

```tsx
      <div>
        {/* `busy` in volo, `unavailableReason` a nome vuoto (Consegna 6a): il fuoco resta
            qui invece di cadere sul `body`, e il perché lo scrive Button sotto di sé */}
        <Button
          type="submit"
          variant="primary"
          shape="block"
          busy={busy}
          unavailableReason={trimmed === "" ? "Scrivi il nome per crearlo." : undefined}
        >
          Crea l'ingrediente
        </Button>
      </div>
```

e togli la riga `import { buttonClasses } from "../../components/ui/buttonClasses";`. La guardia in `submit` resta: un invio arrivato per un'altra strada non deve creare a vuoto.

- [ ] **Step 6: «Abbina» e «Riprova»**

In `frontend/src/features/stocking/StockingRow.tsx` sostituisci:

```tsx
          // la voce non abbinata è chiusa: una riga con «Abbina» (dal giro: il blocco
          // aperto occupava una schermata e mezza per voce). Un pulsante da solo: icona
          // e testo. Il nome della voce nel nome accessibile, dopo i due punti. In
          // `aria-label` e non in uno `sr-only`: lo `sr-only` è posizionato, quindi a
          // blocco, e Chromium ci mette uno spazio davanti — il nome diventava «Abbina :
          // X» (misurato nell'e2e; jsdom non lo vede). `Button` con del testo non accetta
          // `label`, da cui il `<button>` a mano, come «Riprova» qui sotto
          <span data-trigger="match" className="contents">
            <button
              type="button"
              aria-label={`Abbina: ${name}`}
              onClick={() => onOpen("match")}
              className={`${buttonClasses("secondary")} shrink-0`}
            >
              <IconLink aria-hidden="true" className="size-[1.1em]" stroke={1.8} />
              Abbina
            </button>
          </span>
```

con:

```tsx
          // la voce non abbinata è chiusa: una riga con «Abbina» (dal giro: il blocco
          // aperto occupava una schermata e mezza per voce). Un pulsante da solo: icona
          // e testo. Il nome della voce nel nome accessibile, dopo i due punti, con
          // `accessibleName` (Consegna 6a). Non uno `sr-only`: è posizionato, quindi a
          // blocco, e Chromium ci metteva uno spazio davanti — il nome diventava «Abbina :
          // X» (misurato nell'e2e; jsdom non lo vede)
          <span data-trigger="match" className="contents">
            <Button
              icon={IconLink}
              accessibleName={`Abbina: ${name}`}
              onClick={() => onOpen("match")}
              className="shrink-0"
            >
              Abbina
            </Button>
          </span>
```

e sostituisci:

```tsx
          <button
            type="button"
            aria-disabled={retryingMatch || undefined}
            onClick={() => {
              if (!retryingMatch) onRetryMatch();
            }}
            className={`${buttonClasses("secondary")} aria-disabled:opacity-40`}
          >
            {/* un pulsante da solo: icona e testo (regola delle icone, spec §2) */}
            <IconRefresh aria-hidden="true" className="size-[1.1em]" stroke={1.8} />
            {/* lo spazio fuori dallo `sr-only` (dal giro): dentro, il calcolo del nome
                accessibile lo perde, e «Riprova» e «ad abbinare X» si univano senza
                spazio */}
            Riprova <span className="sr-only">ad abbinare {name}</span>
          </button>
```

con:

```tsx
          {/* un pulsante da solo: icona e testo (regola delle icone, spec §2). Il nome
              dice cosa riprova, con `accessibleName` (Consegna 6a); `busy` mentre la
              scrittura è in volo, e il fuoco resta */}
          <Button
            icon={IconRefresh}
            accessibleName={`Riprova ad abbinare ${name}`}
            busy={retryingMatch}
            onClick={onRetryMatch}
          >
            Riprova
          </Button>
```

e togli la riga `import { buttonClasses } from "../../components/ui/buttonClasses";`. Il `<button>` di «+ scadenza» resta a mano: porta un `ref` (il fuoco ci torna quando il campo si chiude), e `Button` non ne passa.

- [ ] **Step 7: Farli passare**

Run: `npx vitest run src/features/stocking`
Expected: PASS, tutti i file della cartella.

- [ ] **Step 8: Le verifiche del frontend, e il grep**

Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde; vitest = linea di partenza + 11 (9 del Task 1, 1 in `NewIngredientFields.test.tsx`, 1 in `StockingRow.test.tsx`).
Run (dalla radice di `<worktree>`): `grep -rn "aria-disabled=" frontend/src/features/stocking --include=*.tsx | grep -v "\.test\."`
Expected: niente.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/features/stocking/StockingScreen.tsx frontend/src/features/stocking/StockingScreen.test.tsx frontend/src/features/stocking/ScannerPanel.tsx frontend/src/features/stocking/NewIngredientFields.tsx frontend/src/features/stocking/NewIngredientFields.test.tsx frontend/src/features/stocking/StockingRow.tsx frontend/src/features/stocking/StockingRow.test.tsx
git commit -m "sistema la spesa: i pulsanti scritti a mano passano a Button, col perché collegato"
```

---

### Task 3: `IngredientPicker` — «Aggiungi «…»» in volo, e il segnaposto

**Files:**
- Modify: `frontend/src/components/IngredientPicker.tsx` (~righe 101-109 e 129-140)
- Test: `frontend/src/components/IngredientPicker.test.tsx`

**Interfaces:**
- Consumes: `Button busy` (Task 1).
- Produces: il segnaposto del campo è «Cerca un ingrediente» in ogni selettore; la prop `disabled` di `IngredientPicker` non cambia nome né significato per campo e suggerimenti.

- [ ] **Step 1: Scrivere i test che falliscono**

In fondo al `describe("IngredientPicker", …)` di `frontend/src/components/IngredientPicker.test.tsx`, dopo «di norma accanto ai suggerimenti non offre di aggiungere: resta com'era», aggiungi:

```tsx
  it("mentre la scelta di prima è in volo, «Aggiungi «…»» è spento ma tiene il fuoco, e non crea", async () => {
    stubRoutedFetch(() => [[], 200]);
    const onCreate = vi.fn();
    renderWithClient(
      <IngredientPicker
        label="Ingrediente"
        failureNote="x"
        onPick={() => {}}
        onCreate={onCreate}
        initialTerm="zz tre"
        disabled
      />
    );
    const aggiungi = await screen.findByRole("button", { name: "Aggiungi «zz tre»" });
    // `busy` e non `disabled` (Consegna 6a): il browser toglie il fuoco a un pulsante che
    // diventa `disabled`. Campo e suggerimenti restano spenti come prima (idea in
    // next-steps.md): cambia solo il pulsante
    expect(aggiungi).toHaveAttribute("aria-disabled", "true");
    expect(aggiungi.hasAttribute("disabled")).toBe(false);
    aggiungi.focus();
    expect(aggiungi).toHaveFocus();
    fireEvent.click(aggiungi);
    expect(onCreate).not.toHaveBeenCalled();
  });

  it("il campo invita a cercare un ingrediente (spec T3 §4.7)", () => {
    vi.stubGlobal("fetch", vi.fn());
    renderWithClient(<IngredientPicker label="Ingrediente" failureNote="x" onPick={() => {}} />);
    expect(screen.getByLabelText("Ingrediente")).toHaveAttribute("placeholder", "Cerca un ingrediente");
  });
```

- [ ] **Step 2: Farli fallire**

Run: `npx vitest run src/components/IngredientPicker.test.tsx`
Expected: FAIL nei due test nuovi (oggi `disabled` e «Cerca in anagrafica»).

- [ ] **Step 3: Il codice**

In `frontend/src/components/IngredientPicker.tsx` sostituisci:

```tsx
          placeholder="Cerca in anagrafica"
```

con:

```tsx
          placeholder="Cerca un ingrediente"
```

e sostituisci:

```tsx
          disabled={disabled}
        >
          {`Aggiungi «${debounced}»`}
        </Button>
```

con:

```tsx
          // `busy` e non `disabled` (Consegna 6a): mentre la scelta di prima è in volo il
          // pulsante tiene il fuoco. Campo e suggerimenti restano spenti con `disabled`:
          // sono un'altra forma, annotata in next-steps.md
          busy={disabled}
        >
          {`Aggiungi «${debounced}»`}
        </Button>
```

(Il commento sta fra gli attributi del `<Button>`, com'è già d'uso in `MergePanel.tsx`.)

- [ ] **Step 4: Farli passare, e il resto**

Run: `npx vitest run src/components/IngredientPicker.test.tsx && npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde; vitest = linea di partenza + 13.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/IngredientPicker.tsx frontend/src/components/IngredientPicker.test.tsx
git commit -m "selettore: «Aggiungi «…»» in volo tiene il fuoco; il campo dice «Cerca un ingrediente»"
```

---

### Task 4: L'accesso — il fuoco nel campo, l'errore che se ne va, «Mostra password», «Entra»

**Files:**
- Modify: `frontend/src/features/auth/LoginScreen.tsx` (per intero)
- Test: `frontend/src/features/auth/LoginScreen.test.tsx`
- Modify: `frontend/e2e/ai-draft.spec.ts`, `anagrafica.spec.ts`, `cooking.spec.ts`, `deep-link.spec.ts`, `error-branch.spec.ts`, `import-review.spec.ts`, `menu.spec.ts`, `modifica-ricette.spec.ts`, `non-alimentari.spec.ts`, `style.spec.ts` (solo `getByLabel("Password")`)

**Interfaces:**
- Consumes: `Button` con `busy`, `unavailableReason`, `aria-pressed` (Task 1); `IconEye`, `IconEyeOff` da `icons.ts`.
- Produces: il campo resta `id="password"` con l'etichetta «Password»; «Entra» resta il nome del submit. Nasce il pulsante «Mostra password» (nome fisso, `aria-pressed`): da qui in poi negli e2e il campo si cerca con `getByLabel("Password", { exact: true })` (decisione 20).

- [ ] **Step 1: Scrivere i test che falliscono**

In `frontend/src/features/auth/LoginScreen.test.tsx` cambia la seconda riga:

```tsx
import { render, screen } from "@testing-library/react";
```

in:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
```

e in fondo al `describe("LoginScreen", …)`, dopo «mostra un messaggio leggibile quando la password è sbagliata», aggiungi:

```tsx
  // Consegna 6a (spec T3 §4.7): l'accesso dal giro non dava il fuoco al campo, lasciava
  // «Password errata» a video mentre si riscriveva, e non c'era modo di vedere la password
  it("il campo prende il fuoco all'apertura", () => {
    vi.stubGlobal("fetch", vi.fn());
    render(<LoginScreen onSuccess={vi.fn()} />);
    expect(screen.getByLabelText("Password")).toHaveFocus();
  });

  it("a campo vuoto «Entra» non ancora: dice perché, e né il tocco né l'Invio mandano niente", async () => {
    const spy = vi.fn();
    vi.stubGlobal("fetch", spy);
    render(<LoginScreen onSuccess={vi.fn()} />);
    const entra = screen.getByRole("button", { name: "Entra" });
    // `unavailableReason` e non `disabled`: resta raggiungibile, e il perché si legge
    expect(entra).toHaveAttribute("aria-disabled", "true");
    expect(entra.hasAttribute("disabled")).toBe(false);
    expect(entra).toHaveAccessibleDescription("Scrivi la password per entrare.");
    await userEvent.type(screen.getByLabelText("Password"), "{Enter}");
    await userEvent.click(entra);
    expect(spy).not.toHaveBeenCalled();

    await userEvent.type(screen.getByLabelText("Password"), "a");
    expect(entra).not.toHaveAttribute("aria-disabled");
    expect(screen.queryByText("Scrivi la password per entrare.")).toBeNull();
  });

  it("in volo «Entra» è spento ma tiene il fuoco, e non parte un secondo accesso", async () => {
    let risolvi: ((response: Response) => void) | null = null;
    const pendente = new Promise<Response>((resolve) => {
      risolvi = resolve;
    });
    const spy = vi.fn(() => pendente);
    vi.stubGlobal("fetch", spy);
    const onSuccess = vi.fn();
    render(<LoginScreen onSuccess={onSuccess} />);

    await userEvent.type(screen.getByLabelText("Password"), "apriti sesamo");
    const entra = screen.getByRole("button", { name: "Entra" });
    await userEvent.click(entra);
    await waitFor(() => expect(entra).toHaveAttribute("aria-disabled", "true"));
    expect(entra.hasAttribute("disabled")).toBe(false);
    expect(entra).toHaveFocus();
    await userEvent.click(entra);
    expect(spy).toHaveBeenCalledTimes(1);

    risolvi!(new Response(null, { status: 204 }));
    await waitFor(() => expect(onSuccess).toHaveBeenCalledOnce());
  });

  it("«Password errata» se ne va appena si riscrive", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 401 })));
    render(<LoginScreen onSuccess={vi.fn()} />);
    const campo = screen.getByLabelText("Password");
    await userEvent.type(campo, "sbagliata");
    await userEvent.click(screen.getByRole("button", { name: "Entra" }));
    expect(await screen.findByText("Password errata")).toBeDefined();

    await userEvent.type(campo, "x");
    expect(screen.queryByText("Password errata")).toBeNull();
  });

  it("«Mostra password» mostra e rinasconde la password, col nome fisso e aria-pressed", async () => {
    const spy = vi.fn();
    vi.stubGlobal("fetch", spy);
    render(<LoginScreen onSuccess={vi.fn()} />);
    const campo = screen.getByLabelText("Password");
    expect(campo).toHaveAttribute("type", "password");

    const mostra = screen.getByRole("button", { name: "Mostra password" });
    // un pulsante di sola icona: il nome sta nell'`aria-label`
    expect(mostra.textContent).toBe("");
    expect(mostra).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(mostra);
    expect(campo).toHaveAttribute("type", "text");
    // lo stesso pulsante, lo stesso nome, premuto, col fuoco ancora lì
    expect(screen.getByRole("button", { name: "Mostra password" })).toBe(mostra);
    expect(mostra).toHaveAttribute("aria-pressed", "true");
    expect(mostra).toHaveFocus();

    await userEvent.click(mostra);
    expect(campo).toHaveAttribute("type", "password");
    // e non è un submit: l'occhio non manda la password
    expect(spy).not.toHaveBeenCalled();
  });
```

- [ ] **Step 2: Farli fallire**

Run: `npx vitest run src/features/auth/LoginScreen.test.tsx`
Expected: FAIL nei cinque test nuovi (niente `autoFocus`, `disabled` al posto di `aria-disabled`, l'errore resta, nessun «Mostra password»); i tre di oggi passano.

- [ ] **Step 3: Scrivere `LoginScreen`**

Sostituisci `frontend/src/features/auth/LoginScreen.tsx` per intero con:

```tsx
import { useState } from "react";
import type { FormEvent } from "react";
import { apiFetch, UnauthorizedError } from "../../api/client";
import { Alert } from "../../components/ui/Alert";
import { BrandMark } from "../../components/ui/BrandMark";
import { Button } from "../../components/ui/Button";
import { IconEye, IconEyeOff } from "../../components/ui/icons";

export function LoginScreen({ onSuccess }: { onSuccess: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // «Mostra password» (spec T3 §4.7): sul telefono un tasto sbagliato non si vede
  const [shown, setShown] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    // `Button` rifiuta già tocco e Invio quando «Entra» è in volo o non ancora pronto:
    // la guardia resta qui perché un invio arrivato per un'altra strada non parta a vuoto
    if (busy || password.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      await apiFetch("/auth/login", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      onSuccess();
    } catch (failure) {
      // solo un 401 dice qualcosa sulla password: chiamare "errata" un server
      // spento manda a riprovare il tasto giusto convinti che sia sbagliato
      setError(
        failure instanceof UnauthorizedError
          ? "Password errata"
          : "Impossibile contattare il server. Riprova."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-dvh items-center justify-center p-6">
      <form onSubmit={submit} className="w-full max-w-sm">
        {/* il marchio prima del campo: è l'unica schermata dove l'app si presenta,
            e quella in cui si arriva senza sapere se si è nel posto giusto */}
        <div className="pb-6 text-center">
          {/* lo stesso cesto dell'icona sul telefono: chi apre l'app installata
              deve ritrovare qui il segno che ha toccato sulla schermata iniziale */}
          <BrandMark className="inline-block size-16" />
          <h1 className="pt-3 text-2xl font-semibold tracking-tight">Spena</h1>
        </div>
        <div className="flex flex-col gap-4 rounded-card bg-card p-5">
          <label htmlFor="password" className="text-sm font-medium text-ink-soft">
            Password
          </label>
          <div className="-mt-2 flex items-center gap-2">
            <input
              id="password"
              type={shown ? "text" : "password"}
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                // l'errore parlava della password di prima: riscrivendola non vale più
                setError(null);
              }}
              // l'unica cosa da fare qui: il campo prende il fuoco appena si apre
              autoFocus
              // mostrata, resta una password: niente maiuscola d'ufficio né correttore
              autoCapitalize="none"
              autoCorrect="off"
              spellCheck={false}
              autoComplete="current-password"
              className="min-w-0 flex-1"
            />
            {/* un interruttore di sola icona (Consegna 6a): il nome resta fisso,
                `aria-pressed` dice se la password è in vista, l'icona lo mostra */}
            <Button
              variant="ghost"
              icon={shown ? IconEyeOff : IconEye}
              label="Mostra password"
              aria-pressed={shown}
              onClick={() => setShown((visible) => !visible)}
            />
          </div>
          {error && <Alert>{error}</Alert>}
          {/* in un contenitore suo: il perché che Button scrive sotto «Entra» gli sta
              attaccato, e non a 16 px come le righe di questa colonna */}
          <div>
            <Button
              type="submit"
              variant="primary"
              shape="block"
              busy={busy}
              unavailableReason={password.length === 0 ? "Scrivi la password per entrare." : undefined}
            >
              Entra
            </Button>
          </div>
        </div>
      </form>
    </div>
  );
}
```

- [ ] **Step 4: Farli passare**

Run: `npx vitest run src/features/auth/LoginScreen.test.tsx src/App.test.tsx`
Expected: PASS (`App.test.tsx` cerca ancora «Entra»).

- [ ] **Step 5: Gli e2e cercano il campo per nome esatto**

`getByLabel` di Playwright confronta anche gli `aria-label`, per sottostringa e senza maiuscole: «Password» troverebbe ora anche «Mostra password», e ogni `fill` fallirebbe per ambiguità (decisione 20). Dalla radice di `<worktree>`:

```bash
sed -i 's/getByLabel("Password")/getByLabel("Password", { exact: true })/g' frontend/e2e/*.ts
grep -rn 'getByLabel("Password")' frontend/e2e
grep -rn 'getByLabel("Password", { exact: true })' frontend/e2e | wc -l
```

Expected: il primo `grep` non stampa niente; il conto è **12** (una riga in ciascuno di `ai-draft`, `anagrafica`, `cooking`, `deep-link`, `error-branch`, `import-review`, `menu`, `modifica-ricette`, `non-alimentari`, e tre in `style.spec.ts`: il `beforeEach`, `perOgniLuogo` due volte).

- [ ] **Step 6: Le verifiche del frontend**

Run (da `<worktree>/frontend`): `npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde; vitest = linea di partenza + 18. `tsc -b` compila anche `e2e/` (`tsconfig.node.json`): il `sed` non deve aver rotto niente.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/auth/LoginScreen.tsx frontend/src/features/auth/LoginScreen.test.tsx frontend/e2e
git commit -m "accesso: il campo col fuoco, l'errore che se ne va, «Mostra password», «Entra» con Button"
```

---

### Task 5: La scheda dell'ingrediente — le correzioni come icone, e i pulsanti con la regola

**Files:**
- Modify: `frontend/src/features/registry/IngredientScreen.tsx` (import; l'intestazione del ramo principale)
- Modify: `frontend/src/features/registry/RenameForm.tsx`
- Modify: `frontend/src/features/registry/CategoryForm.tsx`
- Modify: `frontend/src/features/registry/MergePanel.tsx`
- Modify: `frontend/src/features/registry/AliasRow.tsx`
- Test: `frontend/src/features/registry/IngredientScreen.test.tsx`

**Interfaces:**
- Consumes: `Button` (`busy`, `unavailableReason`, `accessibleName`, `aria-expanded`), `IconToolbar`, `IconCursorText`, `IconCategory`, `IconArrowsJoin2`.
- Produces: il gruppo `toolbar` «Correzioni dell'ingrediente» nell'`action` di `Screen`, coi pulsanti «Rinomina», «Cambia reparto», «Unisci a un altro…». Nomi accessibili di oggi ovunque.

**Migrazioni di test ammesse in questo task** (tutte in `IngredientScreen.test.tsx`, tutte per seguire un pulsante passato da `disabled` a `busy`): le tre asserzioni `toBeDisabled` del test ««Unisci», «Cambia» e «Lascia com'è» restano disabilitati…» e le tre (`not.toBeDisabled`, `toBeDisabled`, `not.toBeDisabled`) del test ««Unisci» resta disabilitato mentre l'anteprima si ricalcola…», più i due titoli di quei test. Le 21 ricerche per nome delle azioni restano come sono: i nomi non cambiano.

- [ ] **Step 1: Scrivere i test che falliscono, e migrare quelli che seguono `busy`**

In cima a `frontend/src/features/registry/IngredientScreen.test.tsx` l'import di Testing Library ha già `within`: non cambia.

Nel test che comincia con `it("«Unisci», «Cambia» e «Lascia com'è» restano disabilitati mentre la fusione vera è in corso", async () => {`, cambia il titolo in `it("«Unisci», «Cambia» e «Lascia com'è» restano spenti, col fuoco, mentre la fusione vera è in corso", async () => {` e sostituisci:

```tsx
    expect(await screen.findByRole("button", { name: "Unisco…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cambia" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Lascia com'è" })).toBeDisabled();
```

con:

```tsx
    // `busy` e non `disabled` (Consegna 6a): spenti con `aria-disabled`, così chi ha
    // premuto «Unisci» da tastiera tiene il fuoco; e un tocco non fa niente
    const unisco = await screen.findByRole("button", { name: "Unisco…" });
    const cambia = screen.getByRole("button", { name: "Cambia" });
    const lascia = screen.getByRole("button", { name: "Lascia com'è" });
    for (const button of [unisco, cambia, lascia]) {
      expect(button).toHaveAttribute("aria-disabled", "true");
      expect(button.hasAttribute("disabled")).toBe(false);
    }
    await userEvent.click(unisco);
    await userEvent.click(cambia);
    await userEvent.click(lascia);
    // nessuna seconda fusione, il vincitore resta scelto, il pannello resta aperto
    expect(
      spy.mock.calls.filter(
        ([url, init]) =>
          String(url).endsWith("/ingredients/i-pomodori/merge") &&
          JSON.parse(String(init?.body)).dry_run === false
      )
    ).toHaveLength(1);
    expect(screen.getByText(/Resta:/)).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Unisci «Pomodori» a un altro ingrediente" })
    ).toBeInTheDocument();
```

Nel test che comincia con `it("«Unisci» resta disabilitato mentre l'anteprima si ricalcola dopo un'invalidazione", async () => {`, cambia il titolo in `it("«Unisci» resta spento mentre l'anteprima si ricalcola dopo un'invalidazione", async () => {` e sostituisci, nell'ordine:

```tsx
    expect(screen.getByRole("button", { name: "Unisci" })).not.toBeDisabled();
```

con:

```tsx
    expect(screen.getByRole("button", { name: "Unisci" })).not.toHaveAttribute("aria-disabled");
```

poi:

```tsx
    await waitFor(() => expect(screen.getByRole("button", { name: "Unisci" })).toBeDisabled());
```

con:

```tsx
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Unisci" })).toHaveAttribute("aria-disabled", "true")
    );
    // spento, un tocco non conferma i numeri vecchi: nessuna fusione vera parte (le due
    // chiamate sono l'anteprima e il suo ricalcolo)
    await userEvent.click(screen.getByRole("button", { name: "Unisci" }));
    expect(rilanci).toBe(2);
```

e infine:

```tsx
    await waitFor(() => expect(screen.getByRole("button", { name: "Unisci" })).not.toBeDisabled());
```

con:

```tsx
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Unisci" })).not.toHaveAttribute("aria-disabled")
    );
```

Poi, in fondo al `describe("IngredientScreen", …)`, dopo «un nome già preso offre «Uniscili», e porta alla fusione con quel vincitore già scelto», aggiungi:

```tsx
  it("le correzioni sono un gruppo di icone accanto al titolo, coi nomi di sempre", async () => {
    stubRoutedFetch((path) => base(path) ?? [{}, 404]);
    renderAt("/anagrafica/ingrediente/i-pomodori");

    const toolbar = await screen.findByRole("toolbar", { name: "Correzioni dell'ingrediente" });
    // accanto al titolo: nella riga dell'intestazione (`action` di Screen)
    expect(toolbar.parentElement).toContainElement(
      screen.getByRole("heading", { level: 1, name: "Pomodori" })
    );
    const buttons = within(toolbar).getAllByRole("button");
    expect(buttons.map((button) => button.getAttribute("aria-label"))).toEqual([
      "Rinomina",
      "Cambia reparto",
      "Unisci a un altro…",
    ]);
    for (const button of buttons) {
      // più pulsanti in gruppo → solo icone (spec T3 §2), col nome di prima come `aria-label`
      expect(button.textContent).toBe("");
      expect(button.querySelector('svg[aria-hidden="true"]')).not.toBeNull();
    }
    await userEvent.click(buttons[0]);
    expect(screen.getByLabelText("Nuovo nome")).toBeInTheDocument();
  });

  it("«Salva il nome» dice perché non salva ancora: il nome è quello di ora, o non c'è", async () => {
    const spy = stubRoutedFetch((path) => base(path) ?? [{}, 404]);
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Rinomina" }));
    const salva = screen.getByRole("button", { name: "Salva il nome" });
    // `unavailableReason` (Consegna 6a): spento senza `disabled`, col perché
    expect(salva).toHaveAttribute("aria-disabled", "true");
    expect(salva.hasAttribute("disabled")).toBe(false);
    expect(salva).toHaveAccessibleDescription("È già il suo nome: scrivine un altro.");
    await userEvent.clear(screen.getByLabelText("Nuovo nome"));
    expect(salva).toHaveAccessibleDescription("Scrivi un nome per salvarlo.");
    await userEvent.click(salva);
    expect(callsTo(spy, "PATCH", "/ingredients/i-pomodori")).toHaveLength(0);
  });

  it("«Salva il reparto» a reparto invariato dice perché, e non manda niente", async () => {
    const spy = stubRoutedFetch((path) => base(path) ?? [{}, 404]);
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Cambia reparto" }));
    const salva = screen.getByRole("button", { name: "Salva il reparto" });
    expect(salva).toHaveAttribute("aria-disabled", "true");
    expect(salva.hasAttribute("disabled")).toBe(false);
    expect(salva).toHaveAccessibleDescription("È già il suo reparto: scegline un altro.");
    await userEvent.click(salva);
    expect(callsTo(spy, "PATCH", "/ingredients/i-pomodori")).toHaveLength(0);

    await userEvent.selectOptions(screen.getByLabelText("Reparto"), "legumi");
    expect(salva).not.toHaveAttribute("aria-disabled");
    expect(screen.queryByText("È già il suo reparto: scegline un altro.")).toBeNull();
  });

  it("mentre l'alias si toglie, «Sposta» e «Togli» restano spenti col fuoco, e non ripartono", async () => {
    let risolvi: ((response: Response) => void) | null = null;
    const pendente = new Promise<Response>((resolve) => {
      risolvi = resolve;
    });
    const spy = vi.fn((url: unknown, init?: RequestInit) => {
      if (init?.method === "DELETE") return pendente;
      const [body, status] = base(String(url)) ?? [{}, 404];
      return Promise.resolve(new Response(JSON.stringify(body), { status }));
    });
    vi.stubGlobal("fetch", spy);
    renderAt("/anagrafica/ingrediente/i-pomodori");

    const togli = await screen.findByRole("button", { name: "Togli l'alias «pomodorini»" });
    const sposta = screen.getByRole("button", { name: "Sposta l'alias «pomodorini»" });
    // `accessibleName` (Consegna 6a): il testo in vista è l'inizio del nome
    expect(togli.textContent).toBe("Togli");
    expect(sposta.textContent).toBe("Sposta");
    await userEvent.click(togli);
    await waitFor(() => expect(togli).toHaveAttribute("aria-disabled", "true"));
    for (const button of [togli, sposta]) {
      expect(button).toHaveAttribute("aria-disabled", "true");
      expect(button.hasAttribute("disabled")).toBe(false);
    }
    expect(togli).toHaveFocus();
    await userEvent.click(togli);
    await userEvent.click(sposta);
    expect(spy.mock.calls.filter(([, init]) => init?.method === "DELETE")).toHaveLength(1);
    // «Sposta» spento non apre la scelta
    expect(screen.queryByLabelText("Sposta «pomodorini» sotto")).toBeNull();

    risolvi!(new Response(null, { status: 204 }));
  });
```

- [ ] **Step 2: Farli fallire**

Run: `npx vitest run src/features/registry/IngredientScreen.test.tsx`
Expected: FAIL nei test migrati (i pulsanti hanno ancora `disabled`, senza `aria-disabled`) e nei quattro nuovi (nessun `toolbar`, nessuna descrizione, `disabled` sugli alias). Gli altri passano.

- [ ] **Step 3: Il gruppo di icone**

In `frontend/src/features/registry/IngredientScreen.tsx` sostituisci:

```tsx
import { Alert } from "../../components/ui/Alert";
import { Card } from "../../components/ui/Card";
import { Screen } from "../../components/ui/Screen";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { buttonClasses } from "../../components/ui/buttonClasses";
```

con:

```tsx
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { IconToolbar } from "../../components/ui/IconToolbar";
import { Screen } from "../../components/ui/Screen";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { IconArrowsJoin2, IconCategory, IconCursorText } from "../../components/ui/icons";
```

e sostituisci:

```tsx
    <Screen
      title={ingredient.display_name}
      subtitle={`${ingredient.category} · ${usageText(ingredient.usage)}`}
      back={back}
    >
      {merged && (
        <p role="status" className="pb-2 text-sm font-medium text-brand">
          {mergeDoneText(merged)}
        </p>
      )}
      <div className="flex flex-wrap gap-2 pb-1">
        <button
          type="button"
          onClick={() => setPanel({ kind: "rename" })}
          className={buttonClasses("secondary")}
        >
          Rinomina
        </button>
        <button
          type="button"
          onClick={() => setPanel({ kind: "category" })}
          className={buttonClasses("secondary")}
        >
          Cambia reparto
        </button>
        <button
          type="button"
          onClick={() => setPanel({ kind: "merge", winner: null })}
          className={buttonClasses("secondary")}
        >
          Unisci a un altro…
        </button>
      </div>
```

con:

```tsx
    <Screen
      title={ingredient.display_name}
      subtitle={`${ingredient.category} · ${usageText(ingredient.usage)}`}
      back={back}
      // le correzioni accanto al titolo (spec T3 §4.7): più pulsanti in gruppo → solo
      // icone, coi nomi di prima come `aria-label` (spec §6). Il pannello si apre sotto
      // l'intestazione, come prima
      action={
        <IconToolbar label="Correzioni dell'ingrediente">
          <Button
            variant="ghost"
            icon={IconCursorText}
            label="Rinomina"
            onClick={() => setPanel({ kind: "rename" })}
          />
          <Button
            variant="ghost"
            icon={IconCategory}
            label="Cambia reparto"
            onClick={() => setPanel({ kind: "category" })}
          />
          <Button
            variant="ghost"
            icon={IconArrowsJoin2}
            label="Unisci a un altro…"
            onClick={() => setPanel({ kind: "merge", winner: null })}
          />
        </IconToolbar>
      }
    >
      {merged && (
        <p role="status" className="pb-2 text-sm font-medium text-brand">
          {mergeDoneText(merged)}
        </p>
      )}
```

`buttonClasses` resta importato: lo usa il «Riprova» del caricamento fallito.

- [ ] **Step 4: «Salva il nome»**

In `frontend/src/features/registry/RenameForm.tsx` aggiungi l'import, sotto quello di `Alert`:

```tsx
import { Button } from "../../components/ui/Button";
```

sostituisci:

```tsx
  const cleaned = name.trim();
  // (F17) un pulsante spento e muto non si spiega da sé: il motivo va scritto sotto
  const nameMissing = cleaned === "";
```

con:

```tsx
  const cleaned = name.trim();
  // (F17) un pulsante spento e muto non si spiega da sé: il perché lo scrive Button sotto
  // di sé (`unavailableReason`, Consegna 6a). Il nome di ora è un «non ancora» anche lui:
  // basta scriverne un altro
  const notYet =
    cleaned === ""
      ? "Scrivi un nome per salvarlo."
      : cleaned === ingredient.display_name
        ? "È già il suo nome: scrivine un altro."
        : undefined;
```

e sostituisci:

```tsx
      <div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={save.isPending || nameMissing || cleaned === ingredient.display_name}
            onClick={() => save.mutate(cleaned)}
            className={buttonClasses("primary")}
          >
            Salva il nome
          </button>
          <button type="button" onClick={onDone} className={buttonClasses("ghost")}>
            Lascia com'è
          </button>
        </div>
        {nameMissing && (
          <p className="pt-2 text-xs text-ink-soft">Scrivi un nome per salvarlo.</p>
        )}
      </div>
```

con:

```tsx
      {/* in colonna: il perché che Button scrive sotto «Salva il nome» gli sta attaccato,
          e «Lascia com'è» non va a capo a metà riga */}
      <div className="flex flex-col items-start gap-2">
        <Button
          variant="primary"
          busy={save.isPending}
          unavailableReason={notYet}
          onClick={() => save.mutate(cleaned)}
        >
          Salva il nome
        </Button>
        <button type="button" onClick={onDone} className={buttonClasses("ghost")}>
          Lascia com'è
        </button>
      </div>
```

`buttonClasses` resta importato («Lascia com'è», «Uniscili»).

- [ ] **Step 5: «Salva il reparto»**

In `frontend/src/features/registry/CategoryForm.tsx` aggiungi l'import, sotto quello di `Alert`:

```tsx
import { Button } from "../../components/ui/Button";
```

e sostituisci:

```tsx
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={save.isPending || category === ingredient.category}
          onClick={() => save.mutate(category)}
          className={buttonClasses("primary")}
        >
          Salva il reparto
        </button>
        <button type="button" onClick={onDone} className={buttonClasses("ghost")}>
          Lascia com'è
        </button>
      </div>
```

con:

```tsx
      {/* in colonna, come nella rinomina: il perché sta attaccato a «Salva il reparto» */}
      <div className="flex flex-col items-start gap-2">
        <Button
          variant="primary"
          busy={save.isPending}
          unavailableReason={
            category === ingredient.category ? "È già il suo reparto: scegline un altro." : undefined
          }
          onClick={() => save.mutate(category)}
        >
          Salva il reparto
        </Button>
        <button type="button" onClick={onDone} className={buttonClasses("ghost")}>
          Lascia com'è
        </button>
      </div>
```

- [ ] **Step 6: La fusione**

In `frontend/src/features/registry/MergePanel.tsx` aggiungi l'import, sotto quello di `Alert`:

```tsx
import { Button } from "../../components/ui/Button";
```

sostituisci:

```tsx
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              // altrimenti l'alert della fusione fallita resta in vista col vincitore
              // sbagliato sotto, e il suo «Riprova» punterebbe a un'anteprima che non
              // c'è più (Minor a)
              merge.reset();
              setWinner(null);
            }}
            className={buttonClasses("ghost")}
          >
            Cambia
          </button>
```

con:

```tsx
          {/* `busy` e non `disabled` (Consegna 6a): chi l'ha raggiunto da tastiera tiene
              il fuoco mentre l'anteprima o la fusione sono in volo */}
          <Button
            variant="ghost"
            busy={busy}
            onClick={() => {
              // altrimenti l'alert della fusione fallita resta in vista col vincitore
              // sbagliato sotto, e il suo «Riprova» punterebbe a un'anteprima che non
              // c'è più (Minor a)
              merge.reset();
              setWinner(null);
            }}
          >
            Cambia
          </Button>
```

sostituisci:

```tsx
          <button
            type="button"
            // anche mentre l'anteprima si ricalcola (`preview.isFetching`), non solo
            // mentre la fusione vera è in corso: un'invalidazione può rilanciarla a
            // pannello aperto (F13, sopra), e i numeri vecchi non vanno confermabili
            // finché quelli nuovi non sono arrivati (rilievo della revisione finale)
            disabled={busy}
            onClick={() => merge.mutate(counts.winner_id)}
            className={buttonClasses("warn", "block")}
          >
            {merge.isPending ? "Unisco…" : "Unisci"}
          </button>
```

con:

```tsx
          <Button
            variant="warn"
            shape="block"
            // anche mentre l'anteprima si ricalcola (`preview.isFetching`), non solo
            // mentre la fusione vera è in corso: un'invalidazione può rilanciarla a
            // pannello aperto (F13, sopra), e i numeri vecchi non vanno confermabili
            // finché quelli nuovi non sono arrivati (rilievo della revisione finale).
            // `busy` e non `disabled` (Consegna 6a): il fuoco resta su «Unisci»
            busy={busy}
            onClick={() => merge.mutate(counts.winner_id)}
          >
            {merge.isPending ? "Unisco…" : "Unisci"}
          </Button>
```

e sostituisci:

```tsx
      <button type="button" disabled={merge.isPending} onClick={onClose} className={buttonClasses("ghost")}>
        Lascia com'è
      </button>
```

con:

```tsx
      <Button variant="ghost" busy={merge.isPending} onClick={onClose}>
        Lascia com'è
      </Button>
```

`buttonClasses` resta importato (il collegamento «Vai a «…»» e i due «Riprova» e «Cambia reparto» dei rifiuti, che non si spengono mai).

- [ ] **Step 7: Gli alias**

In `frontend/src/features/registry/AliasRow.tsx` sostituisci:

```tsx
import { Alert } from "../../components/ui/Alert";
import { buttonClasses } from "../../components/ui/buttonClasses";
```

con:

```tsx
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
```

e sostituisci:

```tsx
          <span className="flex shrink-0 gap-1">
            <button
              type="button"
              disabled={busy}
              aria-expanded={moving}
              aria-label={`Sposta l'alias «${alias.alias}»`}
              onClick={() => setMoving((open) => !open)}
              className={buttonClasses("ghost")}
            >
              Sposta
            </button>
            <button
              type="button"
              disabled={busy}
              aria-label={`Togli l'alias «${alias.alias}»`}
              onClick={() => remove.mutate()}
              className={buttonClasses("danger")}
            >
              Togli
            </button>
          </span>
```

con:

```tsx
          <span className="flex shrink-0 gap-1">
            {/* `busy` e non `disabled` (Consegna 6a): chi ha tolto un alias da tastiera
                tiene il fuoco. Il nome dice quale alias, con `accessibleName`: il testo in
                vista ne è l'inizio */}
            <Button
              variant="ghost"
              busy={busy}
              aria-expanded={moving}
              accessibleName={`Sposta l'alias «${alias.alias}»`}
              onClick={() => setMoving((open) => !open)}
            >
              Sposta
            </Button>
            <Button
              variant="danger"
              busy={busy}
              accessibleName={`Togli l'alias «${alias.alias}»`}
              onClick={() => remove.mutate()}
            >
              Togli
            </Button>
          </span>
```

- [ ] **Step 8: Farli passare**

Run: `npx vitest run src/features/registry`
Expected: PASS, tutti i file della cartella.

- [ ] **Step 9: Le verifiche del frontend**

Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde; vitest = linea di partenza + 22 (i test migrati non cambiano il conto).

- [ ] **Step 10: Commit**

```bash
git add frontend/src/features/registry/IngredientScreen.tsx frontend/src/features/registry/IngredientScreen.test.tsx frontend/src/features/registry/RenameForm.tsx frontend/src/features/registry/CategoryForm.tsx frontend/src/features/registry/MergePanel.tsx frontend/src/features/registry/AliasRow.tsx
git commit -m "anagrafica: le correzioni dell'ingrediente come icone accanto al titolo, e i pulsanti con la regola"
```

---

### Task 6: La scheda del prodotto e il campo dell'Anagrafica

**Files:**
- Modify: `frontend/src/features/registry/ProductScreen.tsx` (import; `barcodeRefusal`; il ramo principale)
- Modify: `frontend/src/features/registry/RegistryScreen.tsx` (il campo)
- Test: `frontend/src/features/registry/ProductScreen.test.tsx`, `frontend/src/features/registry/RegistryScreen.test.tsx`
- Modify: `frontend/e2e/anagrafica.spec.ts` (riga ~125), `frontend/e2e/style.spec.ts` (riga ~1069)

**Interfaces:**
- Consumes: `Button` (`busy`, `aria-expanded`), `IconToolbar`, `IconArrowsTransferDown`, `IconBarcodeOff`.
- Produces: il gruppo `toolbar` «Correzioni del prodotto» con «Spostalo» (sempre) e «Togli il codice» (solo con un codice); il campo dell'Anagrafica ha nome ed etichetta visibile «Cerca un ingrediente o un prodotto». Il Task 7 li misura.

**Migrazioni di test ammesse in questo task:** in `ProductScreen.test.tsx`, nel test ««Spostalo»: la scelta dell'ingrediente…», l'attesa sulla domanda «È sotto l'ingrediente sbagliato?» (che se ne va con il pulsante che introduceva, decisione 14) diventa l'attesa sul gruppo «Correzioni del prodotto»; in `RegistryScreen.test.tsx` le due ricerche per etichetta «Cerca in anagrafica» diventano «Cerca un ingrediente o un prodotto». Le asserzioni di `InlineField` («Salva nome» `toBeDisabled`) **non** cambiano: `InlineField` resta fuori (decisione 17).

- [ ] **Step 1: Scrivere i test che falliscono, e migrare**

`frontend/src/features/registry/ProductScreen.test.tsx` — cambia la seconda riga:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
```

in:

```tsx
import { render, screen, waitFor, within } from "@testing-library/react";
```

nel test ««Spostalo»: la scelta dell'ingrediente, senza filtro sul tipo, e il fatto detto dopo» sostituisci:

```tsx
    expect(await screen.findByText("È sotto l'ingrediente sbagliato?")).toBeInTheDocument();
```

con:

```tsx
    // «Spostalo» sta nel gruppo di icone accanto al titolo (Consegna 6a), senza più la
    // domanda che lo introduceva
    expect(await screen.findByRole("toolbar", { name: "Correzioni del prodotto" })).toBeInTheDocument();
```

e in fondo al `describe("ProductScreen", …)`, dopo «eliminare chiede conferma, dice cosa resta, e torna da dove si è venuti», aggiungi:

```tsx
  it("le correzioni sono un gruppo di icone accanto al titolo, coi nomi di sempre", async () => {
    stubRoutedFetch((path) => base(path) ?? [{}, 404]);
    renderAt("/anagrafica/prodotto/p-reggiano");

    const toolbar = await screen.findByRole("toolbar", { name: "Correzioni del prodotto" });
    expect(toolbar.parentElement).toContainElement(
      screen.getByRole("heading", { level: 1, name: "Parmigiano Reggiano 24 mesi" })
    );
    const buttons = within(toolbar).getAllByRole("button");
    expect(buttons.map((button) => button.getAttribute("aria-label"))).toEqual([
      "Spostalo",
      "Togli il codice",
    ]);
    for (const button of buttons) {
      expect(button.textContent).toBe("");
      expect(button.querySelector('svg[aria-hidden="true"]')).not.toBeNull();
    }
    // «Spostalo» apre e chiude la scelta dell'ingrediente, e lo dice
    expect(buttons[0]).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(buttons[0]);
    expect(buttons[0]).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByLabelText("Sposta sotto")).toBeInTheDocument();
  });

  it("senza codice, nel gruppo non c'è «Togli il codice»", async () => {
    stubRoutedFetch((path) =>
      path.endsWith("/products/p-reggiano")
        ? [{ ...REGGIANO, barcode: null, valid_checksum: null }, 200]
        : (base(path) ?? [{}, 404])
    );
    renderAt("/anagrafica/prodotto/p-reggiano");

    const toolbar = await screen.findByRole("toolbar", { name: "Correzioni del prodotto" });
    expect(within(toolbar).getAllByRole("button").map((button) => button.getAttribute("aria-label"))).toEqual([
      "Spostalo",
    ]);
  });

  it("mentre il codice si toglie, «Togli il codice» resta spento col fuoco, e non riparte", async () => {
    let risolvi: ((response: Response) => void) | null = null;
    const pendente = new Promise<Response>((resolve) => {
      risolvi = resolve;
    });
    const spy = vi.fn((url: unknown, init?: RequestInit) => {
      if (init?.method === "PATCH") return pendente;
      const [body, status] = base(String(url)) ?? [{}, 404];
      return Promise.resolve(new Response(JSON.stringify(body), { status }));
    });
    vi.stubGlobal("fetch", spy);
    renderAt("/anagrafica/prodotto/p-reggiano");

    const togli = await screen.findByRole("button", { name: "Togli il codice" });
    await userEvent.click(togli);
    // `busy` e non `disabled` (Consegna 6a)
    await waitFor(() => expect(togli).toHaveAttribute("aria-disabled", "true"));
    expect(togli.hasAttribute("disabled")).toBe(false);
    expect(togli).toHaveFocus();
    await userEvent.click(togli);
    expect(spy.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(1);

    risolvi!(
      new Response(JSON.stringify({ ...REGGIANO, barcode: null, valid_checksum: null }), { status: 200 })
    );
  });
```

`frontend/src/features/registry/RegistryScreen.test.tsx` — sostituisci le due righe:

```tsx
    await userEvent.type(screen.getByLabelText("Cerca in anagrafica"), "parmig");
```

```tsx
    await userEvent.type(screen.getByLabelText("Cerca in anagrafica"), "reggiano");
```

con, rispettivamente:

```tsx
    await userEvent.type(screen.getByLabelText("Cerca un ingrediente o un prodotto"), "parmig");
```

```tsx
    await userEvent.type(screen.getByLabelText("Cerca un ingrediente o un prodotto"), "reggiano");
```

e in fondo al `describe("RegistryScreen", …)` aggiungi:

```tsx
  it("il campo si chiama come dice l'etichetta che si vede (spec T3 §4.7)", () => {
    stubRoutedFetch(() => [[], 200]);
    renderScreen();
    const campo = screen.getByLabelText("Cerca un ingrediente o un prodotto");
    // prima si vedeva «Cerca» e si sentiva un altro nome, dall'`aria-label`: due nomi per
    // un campo. Ora il nome è l'etichetta che si vede
    expect(campo).not.toHaveAttribute("aria-label");
    expect(campo).toHaveAccessibleName("Cerca un ingrediente o un prodotto");
    expect(campo).toHaveAttribute("placeholder", "pomodoro, Fage…");
  });
```

- [ ] **Step 2: Farli fallire**

Run: `npx vitest run src/features/registry/ProductScreen.test.tsx src/features/registry/RegistryScreen.test.tsx`
Expected: FAIL: in `ProductScreen.test.tsx` il test di «Spostalo» migrato e i tre nuovi (nessun `toolbar`, `disabled` su «Togli il codice»); in `RegistryScreen.test.tsx` i due test migrati e quello nuovo (l'etichetta si chiama ancora «Cerca in anagrafica»).

- [ ] **Step 3: La scheda del prodotto**

In `frontend/src/features/registry/ProductScreen.tsx` sostituisci:

```tsx
import { Alert } from "../../components/ui/Alert";
import { Card } from "../../components/ui/Card";
import { Screen } from "../../components/ui/Screen";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { buttonClasses } from "../../components/ui/buttonClasses";
```

con:

```tsx
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { IconToolbar } from "../../components/ui/IconToolbar";
import { Screen } from "../../components/ui/Screen";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { IconArrowsTransferDown, IconBarcodeOff } from "../../components/ui/icons";
```

In `barcodeRefusal` sostituisci:

```tsx
          <button
            type="button"
            disabled={barcodeAction.isPending}
            onClick={() => barcodeAction.mutate({ barcode: draft, take_barcode: true })}
            className={buttonClasses("warn")}
          >
            Sposta il codice qui
          </button>
```

con:

```tsx
          <Button
            variant="warn"
            busy={barcodeAction.isPending}
            onClick={() => barcodeAction.mutate({ barcode: draft, take_barcode: true })}
          >
            Sposta il codice qui
          </Button>
```

e sostituisci:

```tsx
          <button
            type="button"
            disabled={barcodeAction.isPending}
            onClick={() => barcodeAction.mutate({ barcode: draft, accept_bad_checksum: true })}
            className={buttonClasses("secondary")}
          >
            Usalo lo stesso
          </button>
```

con:

```tsx
          <Button
            busy={barcodeAction.isPending}
            onClick={() => barcodeAction.mutate({ barcode: draft, accept_bad_checksum: true })}
          >
            Usalo lo stesso
          </Button>
```

Poi sostituisci tutto l'ultimo `return (` di `ProductCard` — quello che comincia con `    <Screen title={product.name} subtitle={product.brand ?? undefined} back={back}>` — fino alla fine del file, con:

```tsx
  return (
    <Screen
      title={product.name}
      subtitle={product.brand ?? undefined}
      back={back}
      // le correzioni accanto al titolo, come quelle dell'ingrediente (spec T3 §4.7): più
      // pulsanti in gruppo → solo icone, coi nomi di prima come `aria-label` (spec §6).
      // «Togli il codice» c'è solo se c'è un codice da togliere, come prima
      action={
        <IconToolbar label="Correzioni del prodotto">
          <Button
            variant="ghost"
            icon={IconArrowsTransferDown}
            label="Spostalo"
            aria-expanded={moving}
            onClick={() => setMoving((open) => !open)}
          />
          {product.barcode && (
            <Button
              variant="ghost"
              icon={IconBarcodeOff}
              label="Togli il codice"
              // `busy` e non `disabled` (Consegna 6a): chi l'ha premuto da tastiera
              // tiene il fuoco finché la richiesta è in volo
              busy={barcodeAction.isPending}
              onClick={() => barcodeAction.mutate({ barcode: null })}
            />
          )}
        </IconToolbar>
      }
    >
      {movedNote && (
        <p role="status" className="pb-2 text-sm font-medium text-brand">
          {movedNote}
        </p>
      )}

      {/* lo spostamento si apre qui, sotto l'intestazione, come i pannelli della scheda
          dell'ingrediente. Senza filtro sul `kind`: in anagrafica si corregge anche il
          non alimentare */}
      {moving && (
        <Card as="section" className="mb-3 flex flex-col gap-2">
          <IngredientPicker
            label="Sposta sotto"
            failureNote="Il prodotto resta dov'è: riprova tra poco."
            disabled={move.isPending}
            onPick={(target) => move.mutate(target)}
          />
        </Card>
      )}
      {move.isError && (
        <div className="pb-3">
          <Alert>
            Non sono riuscito a spostarlo: è ancora sotto «{product.ingredient.display_name}». Riprova.
          </Alert>
        </div>
      )}

      <Card className="flex flex-col gap-3">
        {/* obbligatorio (F17): il nome non può restare nullo in colonna */}
        <InlineField
          label="Nome"
          value={product.name}
          required
          onSave={(next) => patch.mutateAsync({ name: next })}
        />
        {/* non obbligatoria: una marca vuota è una richiesta valida, toglierla */}
        <InlineField
          label="Marca"
          value={product.brand ?? ""}
          placeholder="Nessuna marca"
          onSave={(next) => patch.mutateAsync({ brand: next === "" ? null : next })}
        />
      </Card>

      <SectionHeading>Codice a barre</SectionHeading>
      <Card className="flex flex-col gap-2">
        <InlineField
          label="Codice"
          value={product.barcode ?? ""}
          placeholder="Nessun codice"
          inputMode="numeric"
          onSave={(next) => patch.mutateAsync({ barcode: next === "" ? null : next })}
          describeError={barcodeRefusal}
        />
        {product.valid_checksum === false && (
          <p className="text-xs text-ink-faint">
            La cifra di controllo di questo codice non torna: può essere un codice del negozio.
          </p>
        )}
        {barcodeAction.isError && <Alert>{barcodeActionFailureText(barcodeAction.variables)}</Alert>}
      </Card>

      <SectionHeading>Ingrediente</SectionHeading>
      <Card className="flex flex-col gap-2">
        <Link
          to={ingredientPath(product.ingredient.id, origin)}
          className="inline-flex min-h-11 items-center font-medium text-brand"
        >
          {product.ingredient.display_name}
        </Link>
        <p className="text-xs text-ink-faint">{pantryText(product.pantry_items.length)}</p>
      </Card>

      <div className="pt-6">
        {!confirmingDelete ? (
          <button
            type="button"
            onClick={() => setConfirmingDelete(true)}
            className={buttonClasses("danger")}
          >
            Elimina il prodotto
          </button>
        ) : (
          <div
            role="alertdialog"
            aria-label="Conferma l'eliminazione"
            className="flex flex-col gap-2 rounded-card bg-card p-3"
          >
            <p className="text-sm">
              Gli elementi in dispensa restano, come «{product.ingredient.display_name}» sfuso.
            </p>
            <div className="flex flex-wrap gap-2">
              {/* `busy` e non `disabled` (Consegna 6a): il fuoco resta su «Elimina» */}
              <Button variant="danger" busy={remove.isPending} onClick={() => remove.mutate()}>
                Elimina
              </Button>
              <button
                type="button"
                onClick={() => setConfirmingDelete(false)}
                className={buttonClasses("ghost")}
              >
                Lascia
              </button>
            </div>
            {remove.isError && <Alert>Non sono riuscito a eliminarlo. È ancora qui: riprova.</Alert>}
          </div>
        )}
      </div>
    </Screen>
  );
}
```

- [ ] **Step 4: Il campo dell'Anagrafica**

In `frontend/src/features/registry/RegistryScreen.tsx` sostituisci:

```tsx
      <label className="block text-sm font-medium text-ink-soft">
        Cerca
        <input
          aria-label="Cerca in anagrafica"
          value={term}
```

con:

```tsx
      {/* l'etichetta che si vede è il nome del campo (spec T3 §4.7): prima si vedeva
          «Cerca» e si sentiva un altro nome, da un `aria-label`: due nomi per un campo */}
      <label className="block text-sm font-medium text-ink-soft">
        Cerca un ingrediente o un prodotto
        <input
          value={term}
```

- [ ] **Step 5: Gli e2e che cercano il campo per nome**

In `frontend/e2e/anagrafica.spec.ts` sostituisci:

```ts
    await page.getByLabel("Cerca in anagrafica").fill("parmigiano");
```

con:

```ts
    await page.getByLabel("Cerca un ingrediente o un prodotto", { exact: true }).fill("parmigiano");
```

In `frontend/e2e/style.spec.ts` (in `perOgniLuogo`) sostituisci:

```ts
    await page.getByLabel("Cerca in anagrafica").fill(nome);
```

con:

```ts
    await page.getByLabel("Cerca un ingrediente o un prodotto", { exact: true }).fill(nome);
```

- [ ] **Step 6: Farli passare, e il grep**

Run: `npx vitest run src/features/registry`
Expected: PASS.
Run (dalla radice di `<worktree>`): `grep -rn "Cerca in anagrafica" frontend/src frontend/e2e`
Expected: niente.

- [ ] **Step 7: Le verifiche del frontend**

Run (da `<worktree>/frontend`): `npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde; vitest = linea di partenza + 26 (con la base del 2026-09-29, **792 test in 58 file**: nessun file di test nuovo).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/features/registry/ProductScreen.tsx frontend/src/features/registry/ProductScreen.test.tsx frontend/src/features/registry/RegistryScreen.tsx frontend/src/features/registry/RegistryScreen.test.tsx frontend/e2e/anagrafica.spec.ts frontend/e2e/style.spec.ts
git commit -m "anagrafica: le correzioni del prodotto come icone; il campo si chiama «Cerca un ingrediente o un prodotto»"
```

---

### Task 7: L'e2e — l'accesso e le correzioni dell'Anagrafica a 375×812 nel browser vero

jsdom non sa se un pulsante `aria-disabled` tiene davvero il fuoco in Chromium, né se l'Invio in un campo arriva a un submit che si rifiuta (l'invio implicito lo fa il browser), né quanto sono grandi le icone e se stanno su una riga accanto a un titolo (quarta lezione di `CLAUDE.md`). Due prove nuove, in blocchi `test(...)` propri in fondo a `style.spec.ts`, così la fusione coi rami che seguono resta un'unione di blocchi.

**Files:**
- Modify: `frontend/e2e/style.spec.ts` (due test in fondo)

- [ ] **Step 1: Le due prove**

In fondo a `frontend/e2e/style.spec.ts`, dopo il test «dopo una ✕ fallita in lista il fuoco resta sulla ✕», aggiungi (il `beforeEach` del file ha già fatto l'accesso; `page.request` condivide i cookie della pagina):

```ts
test("l'accesso a 375px: il fuoco nel campo, «Entra» non ancora col suo perché, l'Invio che non manda niente, l'occhio", async ({
  page,
}) => {
  // T3 Consegna 6a. Il `beforeEach` è entrato: si esce buttando il cookie, come in
  // `perOgniLuogo`, e la prima richiesta senza sessione riporta all'accesso. Prima si
  // aspetta che l'accesso del `beforeEach` sia finito, o il suo cookie arriverebbe dopo
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  await page.context().clearCookies();
  const accessi: string[] = [];
  page.on("request", (richiesta) => {
    if (richiesta.url().includes("/api/v1/auth/login")) accessi.push(richiesta.method());
  });
  await page.goto("/");

  const campo = page.getByLabel("Password", { exact: true });
  const entra = page.getByRole("button", { name: "Entra", exact: true });

  // 1. il campo prende il fuoco appena compare
  await expect(campo).toBeFocused();

  // 2. a campo vuoto «Entra» non ancora: spento senza `disabled`, col perché collegato,
  // e un bersaglio da pollice
  await expect(entra).toHaveAttribute("aria-disabled", "true");
  await expect(entra).not.toHaveAttribute("disabled");
  await expect(entra).toHaveAccessibleDescription("Scrivi la password per entrare.");
  expect((await entra.boundingBox())!.height).toBeGreaterThanOrEqual(44);

  // 3. l'Invio nel campo vuoto: l'invio implicito del browser passa da un clic su
  // «Entra», che si rifiuta
  await campo.press("Enter");
  // 4. «Entra» si raggiunge e tiene il fuoco, premuto da tastiera: un `disabled` non si
  // raggiungerebbe, e spegnendosi lo butterebbe sulla pagina. Tastiera e non `click()`:
  // Playwright non clicca un elemento `aria-disabled` (vedi le Global Constraints del piano)
  await entra.focus();
  await expect(entra).toBeFocused();
  await page.keyboard.press("Enter");
  await page.keyboard.press("Space");
  await expect(entra).toBeFocused();
  await expect(campo).toBeVisible();
  // un'attesa breve e dichiarata: si prova che una richiesta *non* parte, e non c'è un
  // evento da aspettare al suo posto
  await page.waitForTimeout(500);
  expect(accessi, "a campo vuoto è partito un accesso").toEqual([]);

  // 5. l'occhio: un bersaglio da pollice che mostra e rinasconde la password; il nome
  // resta fisso, `aria-pressed` dice se è premuto, e il fuoco resta lì
  await campo.fill("prova occhio");
  await expect(entra).not.toHaveAttribute("aria-disabled", "true");
  const mostra = page.getByRole("button", { name: "Mostra password", exact: true });
  const occhio = await mostra.boundingBox();
  expect(occhio!.width).toBeGreaterThanOrEqual(44);
  expect(occhio!.height).toBeGreaterThanOrEqual(44);
  await expect(mostra).toHaveAttribute("aria-pressed", "false");
  await expect(campo).toHaveAttribute("type", "password");
  await mostra.click();
  await expect(mostra).toHaveAttribute("aria-pressed", "true");
  await expect(mostra).toBeFocused();
  await expect(campo).toHaveAttribute("type", "text");
  await mostra.click();
  await expect(campo).toHaveAttribute("type", "password");

  // 6. «Password errata» se ne va alla prima battuta
  await campo.fill("sbagliata e2e");
  await campo.press("Enter");
  await expect(page.getByText("Password errata", { exact: true })).toBeVisible();
  await campo.press("x");
  await expect(page.getByText("Password errata", { exact: true })).toHaveCount(0);
  expect(accessi, "è partito un accesso che non doveva").toEqual(["POST"]);

  // 7. niente scorre di lato (stringhe e non funzioni: questo file non ha la libreria DOM)
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
  expect(scrollWidth, "l'accesso scorre di lato").toBeLessThanOrEqual(clientWidth);
});

test("le correzioni dell'anagrafica a 375px: icone da pollice accanto al titolo, su una riga, e niente scorre di lato", async ({
  page,
}) => {
  // T3 Consegna 6a. Un prodotto col codice, perché la scheda mostri anche «Togli il
  // codice», sotto un ingrediente del seme; il nome lungo è il caso che stringe il titolo
  // accanto alle icone. Si toglie nel `finally`.
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  const trovate = (await (
    await page.request.get("/api/v1/ingredients/search?q=farina")
  ).json()) as { id: string; name: string }[];
  const farina = trovate.find((voce) => voce.name === "farina");
  expect(farina, "«farina» non è nel seme").toBeDefined();
  const nome = `Farina di grano tenero tipo 00 macinata a pietra e2e ${Date.now()}`;
  const creato = await page.request.post("/api/v1/products", {
    data: { ingredient_id: farina!.id, name: nome, barcode: String(Date.now()) },
  });
  expect(creato.ok()).toBe(true);
  const prodottoId = ((await creato.json()) as { id: string }).id;

  try {
    const casi = [
      {
        indirizzo: `/anagrafica/ingrediente/${farina!.id}`,
        gruppo: "Correzioni dell'ingrediente",
        nomi: ["Rinomina", "Cambia reparto", "Unisci a un altro…"],
      },
      {
        indirizzo: `/anagrafica/prodotto/${prodottoId}`,
        gruppo: "Correzioni del prodotto",
        nomi: ["Spostalo", "Togli il codice"],
      },
    ];
    for (const caso of casi) {
      await page.goto(caso.indirizzo);
      const gruppo = page.getByRole("toolbar", { name: caso.gruppo });
      await expect(gruppo).toBeVisible();
      await page.waitForLoadState("networkidle");

      const scatole: { x: number; y: number; width: number; height: number }[] = [];
      for (const nomePulsante of caso.nomi) {
        const scatola = await gruppo.getByRole("button", { name: nomePulsante, exact: true }).boundingBox();
        expect(scatola, `${caso.gruppo}: ${nomePulsante}`).not.toBeNull();
        expect(scatola!.width, nomePulsante).toBeGreaterThanOrEqual(44);
        expect(scatola!.height, nomePulsante).toBeGreaterThanOrEqual(44);
        scatole.push(scatola!);
      }
      for (const scatola of scatole.slice(1)) {
        expect(Math.abs(scatola.y - scatole[0].y), `${caso.gruppo}: le icone vanno a capo`).toBeLessThan(1);
      }
      // accanto al titolo: le icone cominciano nella fascia del titolo, non sotto
      const titolo = await page.getByRole("heading", { level: 1 }).boundingBox();
      expect(scatole[0].y, `${caso.gruppo}: le icone non stanno accanto al titolo`).toBeLessThan(
        titolo!.y + titolo!.height
      );
      const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
      const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
      expect(scrollWidth, `${caso.indirizzo} scorre di lato`).toBeLessThanOrEqual(clientWidth);
    }

    // e il campo dell'Anagrafica ha il nome nuovo, che si vede
    await page.goto("/anagrafica");
    await expect(page.getByText("Cerca un ingrediente o un prodotto", { exact: true })).toBeVisible();
    await page.getByLabel("Cerca un ingrediente o un prodotto", { exact: true }).fill(nome);
    await expect(page.getByRole("link", { name: new RegExp(nome) })).toBeVisible();
  } finally {
    // `expect.soft`: non lancia (un `finally` che lancia nasconderebbe l'errore vero del
    // `try`) ma segna la prova fallita, così un prodotto rimasto non passa per un successo
    try {
      const risposta = await page.request.delete(`/api/v1/products/${prodottoId}`);
      expect.soft(risposta.ok(), `pulizia: il prodotto ${prodottoId} non si è eliminato`).toBe(true);
    } catch (guasto) {
      expect
        .soft(false, `pulizia: non sono riuscito a eliminare il prodotto ${prodottoId} (${guasto})`)
        .toBe(true);
    }
  }
});
```

- [ ] **Step 2: Il tipo del file**

Run (da `<worktree>/frontend`): `npm run typecheck && npm run lint`
Expected: puliti (`tsc -b` compila anche `e2e/`, senza la libreria DOM: per questo `evaluate` riceve stringhe).

- [ ] **Step 3: Lo stack e2e, e l'e2e intera**

Dalla radice di `<worktree>`, con i comandi delle Global Constraints: controlla che `spena-e2e` non sia già alzato da un altro, `cp .env.example .env`, `up -d --build --wait`, il seme `--con-ricette`, poi `(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)`.
Expected: tutti verdi, due più della linea di partenza (erano 34 dopo il merge del 2026-09-29: **36**). In particolare ogni file che entra dal `beforeEach` trova il campo con `getByLabel("Password", { exact: true })`, e `anagrafica.spec.ts` preme ancora «Spostalo».

Se la prova 1 si ferma al passo 4 perché il fuoco non è su «Entra» dopo l'Invio o lo Spazio, non indebolirla: è il difetto che la prova esiste per vedere (il browser toglie il fuoco a un `disabled`). Controlla che «Entra» non abbia `disabled` e segna il task `bloccato` con la diagnosi se non si risolve.

Se una prova fallisce e lascia dati nello stack, prima di rieseguire ricrea lo stack da zero (`down -v`, `up`, seme). Alla fine, sempre:

```bash
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
rm .env
```

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/style.spec.ts
git commit -m "e2e: l'accesso e le correzioni dell'anagrafica a 375px, nel browser vero"
```

---

### Task 8: I documenti

**Files:**
- Modify: `docs/prossimi-passi.md`
- Modify: `next-steps.md`

- [ ] **Step 1: Il paragrafo della consegna**

In `docs/prossimi-passi.md`, nella voce T3, subito **prima** del paragrafo che comincia con «Dei tre punti di disegno del tema scuro annotati per questa consegna», aggiungi:

```markdown
**Consegna 6a (Pulsanti, Accesso, Anagrafica) fatta il <data di oggi>, sul ramo
`night/c6a-pulsanti`, non ancora in produzione.** È la prima metà della Consegna 6 (spec
§4.7); la seconda, 6b (modulo della ricetta, coda d'import, parole), viene dopo Ricette e
Dettaglio. **Una regola sola per i pulsanti spenti** (decisa da Mattia il 2026-09-29): una
richiesta in volo → `busy`; «non si può ancora» → `unavailableReason`, col perché; `disabled`
nativo solo dove nessuno dei due vale. Sta tutta in `Button`: `unavailableReason` spegne
con `aria-disabled` come `busy`, ignora tocco e Invio (l'invio implicito del browser passa
da un clic sul submit, ed è quel clic che si rifiuta), tiene il fuoco, e scrive il perché
sotto di sé in un `<p>` collegato con `aria-describedby`. `Button` ha imparato anche
`accessibleName`, per un pulsante con testo che deve dire di più («Abbina» si sente
«Abbina: X»; il testo in vista resta l'inizio del nome), e passa `aria-expanded` e
`aria-pressed`. Il JSDoc di `busy` e `unavailableReason` dice che il clic risale agli
antenati. Cosa è cambiato a video: in «Sistema la spesa» nessun pulsante è più scritto a
mano («Metti in dispensa», «Cerca», «Crea l'ingrediente», «Abbina», «Riprova»); «Aggiungi
«…»» del selettore tiene il fuoco in volo, e il suo campo dice «Cerca un ingrediente»;
l'accesso dà il fuoco al campo, toglie «Password errata» alla prima battuta, ha «Mostra
password» con l'occhio e «Entra» che a campo vuoto dice «Scrivi la password per
entrare.»; nell'Anagrafica le correzioni dell'ingrediente (Rinomina, Cambia reparto, Unisci)
e del prodotto (Spostalo, Togli il codice) sono icone accanto al titolo, e il campo si chiama
«Cerca un ingrediente o un prodotto», col nome che si vede. Suite finale: <vitest> vitest,
<pytest> backend, <e2e> e2e, tutti verdi.

**Le scelte del piano che Mattia può voler rivedere:** il perché del «non ancora» in
`text-ink-faint` sotto il pulsante, anche in colonne dove prima era `text-ink-soft`; nelle
correzioni dell'ingrediente anche un valore invariato è «non ancora» («È già il suo nome:
scrivine un altro.», «È già il suo reparto: scegline un altro.»), con «Salva» e «Lascia
com'è» in colonna; la domanda «È sotto l'ingrediente sbagliato?» della scheda prodotto se
n'è andata col pulsante che introduceva; l'occhio dell'accesso ha il nome fisso «Mostra password» e
porta `aria-pressed` (un nome che cambia insieme ad `aria-pressed` si leggerebbe «Nascondi
password, premuto»); `InlineField` (il «Salva» accanto a nome, marca e codice del prodotto) è rimasto
con `disabled`, ed è una voce in `next-steps.md`.

**Da provare sul telefono:** all'accesso, se il campo col fuoco apre davvero la tastiera
(iOS non la apre da `autoFocus` senza un tocco: il fuoco c'è lo stesso), l'occhio, e la
password mostrata senza maiuscola né correttore; nell'Anagrafica, se le icone delle
correzioni si capiscono senza testo; in «Sistema la spesa», «Metti in dispensa» spento col
perché sotto.
```

Sostituisci `<data di oggi>` con la data vera e `<vitest>`, `<pytest>`, `<e2e>` coi conti misurati nel Task 9 (scrivi il paragrafo adesso e i numeri dopo il Task 9, in un commit a parte se serve).

- [ ] **Step 2: `next-steps.md`**

1. Aggiorna la riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte)_`.
2. Se in «Pronti per la notte» c'è la riga di questo piano (contiene `Consegna 6a` o `c6a`), toglila. Non toccare le righe degli altri tre piani. Se la riga «Consegna 6, il resto» in «Da approfondire» esiste ancora, non toglierla: resta la 6b; aggiungi in fondo alla riga ` — la 6a è fatta (night/c6a-pulsanti)`.
3. Togli da «Da approfondire» la riga che comincia con `- [tbd] P2 · Una regola sola per i pulsanti spenti` (chiusa da questo piano).
4. Togli da «Idee» le righe che cominciano con `- [idea] P3 · \`Button\` non sa dare un nome accessibile insieme a figli visibili` e con `- [idea] P3 · Un \`Button\` \`busy\` cliccato fa comunque risalire l'evento` (chiuse: `accessibleName`, e il JSDoc).
5. Nella riga che comincia con `- [idea] P3 · \`IngredientPicker\` spegne campo, suggerimenti e «Aggiungi «…»» con \`disabled\``, sostituisci il testo con:
   ```markdown
   - [idea] P3 · `IngredientPicker` spegne campo e suggerimenti con `disabled` mentre la scelta è in volo (dalla Consegna 6a «Aggiungi «…»» usa `busy`): lo stesso fuoco perso della ✕ di Lista, in una forma diversa [T3 Consegna 2]
   ```
6. In «Idee» aggiungi:
   ```markdown
   - [idea] P3 · `InlineField.tsx` (nome, marca e codice del prodotto) ha ancora `<button disabled>`: dopo un salvataggio riuscito il «Salva» si spegne e il fuoco cade sulla pagina. Il motivo sotto un pulsante che sta nella riga del campo non ci sta, e «invariato» è lo stato di ogni campo a riposo — decidere la forma [T3 Consegna 6a]
   - [idea] P3 · `CustomProductForm.tsx` («Salva prodotto») spegne ancora con `disabled`: passarlo alla regola dei pulsanti (`unavailableReason` col perché) [T3 Consegna 6a]
   ```
7. In cima a «Fatti (recenti)» aggiungi:
   ```markdown
   - [fatto] <data di oggi> · T3 Consegna 6a, pulsanti, accesso e anagrafica: `Button` con `unavailableReason` e `accessibleName` (una regola sola per i pulsanti spenti), «Sistema la spesa» senza pulsanti scritti a mano, l'accesso col fuoco nel campo e «Mostra password», le correzioni dell'anagrafica come icone accanto al titolo, «Cerca un ingrediente o un prodotto» → branch night/c6a-pulsanti (da revisionare)
   ```
8. In cima a «Da fare a mano (solo Mattia)» aggiungi:
   ```markdown
   - [tbd] P2 · Prove sul telefono della Consegna 6a: l'accesso (la tastiera col campo che ha il fuoco, l'occhio, la password mostrata senza maiuscola), le icone delle correzioni in Anagrafica senza testo, «Metti in dispensa» spento col perché sotto
   ```
9. Se nella notte sono emerse cose da fare fuori da questo piano, aggiungile come `idea` o `tbd` nella sezione giusta, con la voce di `docs/prossimi-passi.md` fra parentesi quadre.

- [ ] **Step 3: Commit**

```bash
git add docs/prossimi-passi.md next-steps.md
git commit -m "docs: T3 Consegna 6a, una regola sola per i pulsanti spenti; accesso e anagrafica"
```

---

### Task 9: La verifica finale

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

Expected: vitest tutto verde — **la linea di partenza più 26**, cioè 9 (`Button`) + 1 (`NewIngredientFields`) + 1 (`StockingRow`) + 2 (`IngredientPicker`) + 5 (`LoginScreen`) + 4 (`IngredientScreen`) + 3 (`ProductScreen`) + 1 (`RegistryScreen`); con la base del 2026-09-29, **792 test in 58 file**. Se il numero differisce, scrivi nel report da dove viene la differenza. Typecheck, lint e build puliti. `npx tsc -b --force` perché `node_modules` è condiviso col checkout principale e con lui il `tsbuildinfo`: `--force` compila davvero tutto invece di fidarsi di una build precedente.

- [ ] **Step 2: Il backend**

Da `<worktree>/backend`:

```bash
PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Expected: tutto verde, lo stesso numero della linea di partenza (questo piano non tocca il backend).

- [ ] **Step 3: I grep**

Dalla radice di `<worktree>`, i cinque `grep` di «Comandi di verifica». Expected: niente, cinque volte.

- [ ] **Step 4: L'e2e intera**

Con i comandi delle Global Constraints, su uno stack ricreato da zero (`down -v` prima dell'`up`, se ne era rimasto uno di questo ramo; mai se è di un altro piano). Expected: tutti verdi, **36**. Poi `down -v` e `rm .env`, sempre.

- [ ] **Step 5: I numeri nei documenti**

Scrivi i conti veri (vitest, pytest, e2e) al posto di `<vitest>`, `<pytest>`, `<e2e>` nel paragrafo del Task 8, e committa:

```bash
git add docs/prossimi-passi.md
git commit -m "docs: i conti finali della Consegna 6a"
```

- [ ] **Step 6: Il report**

Nel report della notte (`docs/night-reports/<data>.md`), per questo piano: il ramo, i conti veri (vitest, pytest, e2e), le migrazioni di test fatte oltre a quelle elencate nei Task 5 e 6 (dovrebbero essere zero), le decisioni prese in autonomia, e un promemoria per i tre piani che seguono: partono da `night/c6a-pulsanti`, e le loro prove e2e cercano il campo con `getByLabel("Password", { exact: true })`. Niente push, niente merge, niente deploy.
