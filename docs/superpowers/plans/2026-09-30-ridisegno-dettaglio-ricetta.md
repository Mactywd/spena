# T3 Consegna 5 — Il dettaglio della ricetta ridisegnato, e «Salva nel ricettario»: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** portare il dettaglio della ricetta (`/ricette/:id`) sulle primitive della Consegna 0: in cima il tasto indietro sopra la foto (o al suo posto se la foto non c'è), titolo con «Modifica» ed «Elimina» come icone, categoria e costo in sola lettura; lo stepper delle porzioni sempre visibile; gli ingredienti con lo `StatusDot` e «non basta»; «Cucina» e il nuovo «Metti in lista ciò che manca» in fondo agli ingredienti; il foglio della cottura con `StockGauge`; l'esito di «Ho cucinato» e di «Salva nel ricettario» / «Salva le modifiche» dall'avviso unico (l'ultimo punto di T4).

**Architecture:** nessun cambio al backend. Nel frontend: `Button` impara `ref` (React 19, una prop); il nuovo `missingToList.ts` tiene le due funzioni pure di «Metti in lista ciò che manca» (le `POST /shopping-list` in parallelo con `Promise.allSettled`, e la frase dell'avviso), testate a tabella; `AddMissingButton.tsx` è il pulsante, col «Riprova» nell'avviso; `ServingsStepper` accetta `null`; `CookSheet` sostituisce i tre pulsanti con `StockGauge`; `RecipeDetailScreen.tsx` si riscrive (via `CostPicker`, via `updateRecipeCost` dal client, via `state.saved`); `AiDraftScreen` e `RecipeEditScreen` dicono «Salvata.» con `useNotice` prima di navigare. Nessuna rotta nuova, nessuna migrazione, nessuna dipendenza.

**Tech Stack:** React 19, TypeScript, Tailwind 4 (token in `@theme`), TanStack Query 5, react-router 7, Vitest + Testing Library (jsdom), Playwright. Il backend non cambia, ma la sua suite gira nella verifica finale.

**Spec:** `docs/superpowers/specs/2026-09-28-ridisegno-design.md`, §2, §3.1, §3.5 (`StatusDot`, `Notice`), **§4.4** (`StockGauge` nel foglio della cottura) e **§4.6**; le decisioni della fase giorno del 2026-09-29 (seconda), «Piano 3», riportate qui sotto in «Decisioni prese»; T4 e l'esito del giro sotto «**Dettaglio ricetta** (oltre a R10 e T4)» in `docs/prossimi-passi.md`. Si leggono insieme a questo piano.

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/c5-dettaglio` (`.worktrees/` è già in `.gitignore`), ramo **`night/c5-dettaglio`, creato da `night/c4-ricette`** (vedi «Dipendenze»). Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì (o dalle sue `backend/` e `frontend/`), mai dalla radice del checkout principale; il checkout principale non si tocca: se vi trovi modifiche non committate, sono dell'utente. **Nessun push, nessun merge, nessun deploy.** **Mai `git stash`.**
- Tutto il colore passa dai token di `frontend/src/index.css`. Nessuna schermata nomina un colore crudo: `grep -rn "emerald\|neutral-" frontend/src` resta vuoto. Il testo su un fondo pieno usa il suo `on-*`. Ogni testo sta sopra 4,5:1, ogni segno non testuale (i pallini) sopra 3:1, in chiaro e in scuro, e lo misura `frontend/e2e/style.spec.ts`.
- Le icone si importano solo da `frontend/src/components/ui/icons.ts` (servono `IconChefHat`, `IconShoppingCartPlus`, `IconPencil`, `IconTrash`, `IconExternalLink`, `IconChevronLeft`, `IconCircleCheck`, `IconRestore`, `IconMinus`, `IconPlus`: ci sono tutte).
- Regola delle icone (spec §2): **più pulsanti in gruppo → solo icone; un pulsante da solo → icona e testo.** Ogni pulsante di sola icona ha il nome completo come `aria-label`.
- **Regola dei pulsanti spenti** (Mattia, Piano 1): in volo → `busy`; «non si può ancora» → `unavailableReason` col perché; `disabled` nativo solo dove nessuno dei due vale. Ogni bersaglio nuovo è almeno 44×44 px. A 375 px nessuna schermata scorre di lato.
- **Il frontend non calcola la cucinabilità.** Quali righe mancano lo dice `satisfied`, quale pallino lo dice `availability`: arrivano dal server (`_to_out` in `backend/app/api/recipes.py`, la regola in `backend/app/domain/rules.py`). Il client filtra e mostra, non giudica.
- **Nomi accessibili stabili** (spec §6): «Ricette» (il ritorno), «Modifica», «Elimina», «Cucina», «Ho cucinato», «Annulla», «Una porzione in meno», «Una porzione in più», «Apri l'originale», «Rimetti in lista …» restano quelli di oggi anche se diventano icone.
- **Mai un vicolo cieco.** Un invio in lista fallito dice quante righe non sono andate e offre «Riprova» per quelle sole; la dispensa che non carica lascia «Riprova»; la ricetta sparita lascia «Torna al ricettario».
- Nessuna dipendenza nuova, nessuna migrazione, nessuna modifica al backend.
- Le parole a video sono in italiano e **si copiano esattamente come sono scritte qui**; gli identificatori in inglese; i commenti in italiano come nel resto del codice. **Accordi**: niente participi che concordano col nome di un ingrediente.
- **Il type check è `npm run typecheck`** (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0 (settima lezione di `CLAUDE.md`).
- Controlli del frontend, da `<worktree>/frontend`: `npx vitest run`, `npm run typecheck`, `npm run lint`, `npm run build`. Il progetto **non ha** uno script `npm test`.
- **Backend su Postgres vero** (solo nella verifica finale). Il database di test è il container `spena-db-1` (porta 5433), da usare solo come database dei test: se `docker ps --format '{{.Names}}'` non lo mostra, `docker start spena-db-1`. **Mai `docker compose up` dal worktree**: il nome del progetto Compose viene dalla cartella, e ne nascerebbe un secondo Postgres che litiga sulla 5433. Il comando dei test, da `<worktree>/backend`:
  ```bash
  PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
  Il venv è quello del checkout principale (il worktree non ne ha uno): `python -m` mette la cartella corrente in testa a `sys.path`, quindi si prova l'`app` del worktree.
- **e2e** sullo stack `spena-e2e`, dalla radice di `<worktree>`. Serve un `.env`: **si copia da `.env.example`, che non ha segreti, solo per la prova, e si cancella dopo. Mai leggere né copiare il `.env` del checkout principale.** Prima di alzarlo, `docker ps --format '{{.Names}}' | grep spena-e2e`: se c'è e non l'hai alzato tu (un altro piano della notte), non toccarlo e aspetta che sparisca.
  ```bash
  cp .env.example .env
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed --con-ricette
  (cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
  rm .env
  ```
  Il `-p spena-e2e` e il `-f docker-compose.e2e.yml` vanno in ogni comando: un `down -v` sul progetto di default cancellerebbe la dispensa vera. Una prova fallita lascia dati nello stack: prima di rieseguire, `down -v`, di nuovo `up`, seme e prova.

### Preparazione (una volta, prima del Task 1)

- [ ] Il ramo di partenza c'è ed è finito. Dal checkout principale:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify night/c4-ricette
  git show night/c4-ricette:next-steps.md | grep -n "Consegna 4"
  ```
  Expected: il primo comando stampa un hash; il secondo mostra la Consegna 4 fra i `[fatto]` (non `bloccato`, non `in corso`). Se il ramo manca o la Consegna 4 è bloccata, **fermati**: scrivi `bloccato` sulla riga della Consegna 5 in `next-steps.md` del checkout principale con «attende: night/c4-ricette», e passa al piano successivo della notte.
- [ ] Allinea `node_modules` al lockfile, dal checkout principale (non aggiunge dipendenze, installa quelle di `package-lock.json`):
  ```bash
  cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund
  ```
- [ ] Crea il worktree dal ramo della Consegna 4 e collega `node_modules` (e solo quello: **niente `.env`**):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/c5-dettaglio -b night/c5-dettaglio night/c4-ricette
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/c5-dettaglio/frontend/node_modules
  ```
- [ ] Le due interfacce dei piani precedenti ci sono:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/c5-dettaglio
  test -f frontend/src/features/recipes/useArchiveRecipe.ts && grep -q "unavailableReason" frontend/src/components/ui/Button.tsx && echo pronte
  grep -n "export function useArchiveRecipe" frontend/src/features/recipes/useArchiveRecipe.ts
  ```
  Expected: `pronte`, e la firma `useArchiveRecipe(): { archive(recipe: { id: string; title: string }): void; pending: boolean }` (o equivalente con quei due nomi). Se una delle due manca, fermati come sopra («attende: `Button.unavailableReason` / `useArchiveRecipe`»).
- [ ] Leggi com'è oggi, su questo ramo, ciò che i Piani 1 e 2 hanno toccato e che qui si riscrive: `frontend/src/components/ui/Button.tsx` (come disegna il `<p>` di `unavailableReason`), `frontend/src/features/cooking/RecipeDetailScreen.tsx` (come chiama `useArchiveRecipe`, e se ha lasciato qualcosa per il guasto dell'eliminazione), `frontend/src/features/cooking/RecipeDetailActions.test.tsx` e `frontend/e2e/modifica-ricette.spec.ts` (i test dell'eliminazione).
- [ ] La linea di partenza, dal worktree:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/c5-dettaglio/frontend && npx vitest run 2>&1 | grep -E "Test Files|Tests "
  ```
  Expected: tutto verde. **Annota i due numeri (file e test) nel report**: sono la base del conto finale (Task 10). Se non è verde, fermati: non è un difetto di questo piano.

---

## Obiettivo e contesto

Il dettaglio è lo schermo che si guarda in cucina, col telefono appoggiato e le mani occupate, e quello da cui si decide se cucinare. Il giro di T3 ci ha trovato: «Cucina» in fondo sotto il procedimento, che sembra dire «inizia a cucinare»; i mancanti che non si mettono in lista dal dettaglio (la freccia ricetta → lista esiste solo dopo aver cucinato); i cinque € che sono pulsanti e non sembrano, così un tocco scorrendo cambia il costo; «Apri l'originale» alto 19 px; lo stepper che sparisce senza dirlo quando la ricetta non dichiara le porzioni; pastiglie di testo per riga che nessuno legge, mentre `availability` e `satisfied` arrivano già dal server; il foglio della cottura con tre pulsanti per confezione, mentre la dispensa ha le tacche (spec §4.4: «lo stesso giudizio ha due controlli»). E T4 ha ancora un punto aperto: «Salva nel ricettario» porta al dettaglio senza dire niente.

Questa consegna porta il dettaglio sulle primitive e chiude quelle osservazioni, senza toccare quel che il giro chiede di non riprogettare via: il riporziona che rilegge dal server senza far sparire lo schermo (`keepPreviousData`), «N dosi su M non si riscalano» col denominatore del server, il foglio che si apre portando in vista il suo inizio, la dispensa che non carica e non si traveste da foglio vuoto, la ricetta sparita che riporta al ricettario.

## Decisioni prese

Prese di giorno con Mattia o dal coordinatore della fase giorno (2026-09-29, seconda): la notte non le riapre.

1. **In cima**: con la foto, il tasto indietro sta sopra la foto, e la foto non ne abbassa il contrasto (fondo del tasto pieno); senza foto, o se non carica, il tasto indietro sta al suo posto nel flusso. Titolo, categoria e costo in sola lettura (`CostMeter`; niente più `CostPicker` nel dettaglio: il costo si cambia da «Modifica»). `updateRecipeCost` resta senza chiamanti e **si toglie dal client**; la `PATCH` del backend resta.
2. **«Modifica» ed «Elimina»** come `IconToolbar` accanto al titolo (`IconPencil`, `IconTrash`); «Elimina» chiama `useArchiveRecipe().archive` (Piano 2).
3. **Porzioni**: lo stepper si vede sempre; senza porzioni i pulsanti non si usano e dicono perché con `unavailableReason`, «Porzioni non indicate: si cambiano da «Modifica».».
4. **Ingredienti** in «Principali» e «Secondari» (`SectionHeading`, non `Section`), ognuno col `StatusDot` da `availability`. **Un principale quasi finito non soddisfatto**: pallino giallo e, accanto al nome, «non basta» in piccolo (Mattia). Il nome accessibile del pallino resta dal vocabolario `STATUS_LABELS`; il test del vocabolario resta verde.
5. **«Metti in lista ciò che manca»** (icona `IconShoppingCartPlus`, pulsante secondario accanto a «Cucina»): per ogni riga con `satisfied === false` una `POST /shopping-list` con l'ingrediente, in parallelo (`Promise.allSettled`; mai doppioni grazie a S18); `busy` mentre è in volo; nascosto quando tutte le righe sono soddisfatte. Avviso: «3 in lista» · «2 in lista · 1 c'era già» · «Era già tutto in lista.» · con guasti «2 in lista · 1 non è andata» con «Riprova», che rimanda solo le righe fallite. Poi si invalida la lista della spesa.
6. **«Cucina»** (icona `IconChefHat` e testo) è il pulsante principale **in fondo agli ingredienti**, prima del procedimento, con accanto «Metti in lista ciò che manca».
7. **Il foglio della cottura** usa `StockGauge` al posto dei tre pulsanti: parte dallo stato attuale della confezione (niente toccato = invariato); toccare di nuovo lo stato di partenza annulla la scelta; «Disponibile» si può scegliere (il backend lo accetta: `TransitionIn.to_status` è un `PantryStatus`); «Rimetti in lista» compare per quasi finito e finito, già spuntata per finito (regola di oggi). Il nome del radiogroup porta prodotto, marca e data come oggi (`itemLabel`).
8. **«Ho cucinato»**: l'esito passa dall'avviso unico (stesso testo di oggi, che comincia con «Segnato.»), e il fuoco va su «Cucina».
9. **«Apri l'originale»** alto 44 px, con `IconExternalLink`.
10. **«Salva nel ricettario»** (ultimo punto di T4): dopo il salvataggio dalla bozza (`AiDraftScreen`) e dalla modifica (`RecipeEditScreen`) l'avviso unico dice «Salvata.» prima di portare al dettaglio; via `state.saved`, `justSaved`/`savedRef` e la `<p role=status>` del dettaglio.

Scelte di questo piano, dove le dieci sopra non arrivavano (reversibili; Mattia le rivede):

11. **`StatusDot` non impara `satisfied`.** Il nome del pallino resta quello del vocabolario («quasi finito»); «non basta» è testo visibile accanto al nome, e chi ascolta lo sente perché è testo. Una prop in più non servirebbe al nome.
12. **Lo stepper**: l'etichetta «Porzioni» sta a sinistra, poi «−», il numero, «+» (via «Per … porzioni»: a porzioni ignote la frase non avrebbe un numero). Senza porzioni il numero è «—», **solo il «+» porta `unavailableReason`** — `Button` disegna il motivo sotto di sé, e con due pulsanti la stessa frase comparirebbe due volte in una riga — e il «−» è `disabled` come ai bordi. Ai bordi (1 e 50) resta `disabled`, come oggi (e l'e2e lo prova).
13. **«Metti in lista ciò che manca» sta sotto «Cucina», a tutta larghezza**, non sulla stessa riga: a 375 px i due testi con le icone non ci stanno insieme (≈370 px su 343).
14. **L'invio in lista non è una `useMutation`**, come l'«Annulla» della dispensa (`undoRemove` in `PantryScreen.tsx`): il «Riprova» vive nell'avviso, che è dell'app, e si può toccare anche dopo aver lasciato la ricetta. Il `raw_text` di ogni `POST` è il `ingredient_name` della riga (il nome canonico), con l'`ingredient_id`. Le altre frasi dell'avviso: «2 c'erano già», «2 non sono andate», e se non è andata nessuna e nessuna c'era già, «Non è andata: la lista è com'era.».
15. **Il fuoco torna su «Cucina» anche dopo «Annulla» del foglio**: il foglio si smonta col pulsante che aveva il fuoco, e altrimenti finirebbe sul `body`.
16. **`Button` impara `ref`** (in React 19 `ref` è una prop dei componenti funzione): serve a ridare il fuoco a «Cucina».
17. **Il tasto indietro è una pastiglia «‹ Ricette» con fondo `card`**, anche senza foto; la foto gli scivola sotto con un margine negativo (`-mt-[3.25rem]`), così il caso «foto che non carica» (`RecipeImage` non disegna niente) lo rimette al suo posto senza che lo schermo debba sapere se l'immagine è arrivata.
18. **Le icone accanto al titolo sono `ghost`**, anche «Elimina»: il rosso vuol dire «manca» e «non è andata» (spec §3.1). «Modifica» resta un collegamento (è una navigazione), disegnato con `buttonClasses("ghost", "icon")`; il gruppo si chiama «Azioni della ricetta».
19. **«Ho cucinato» con l'icona `IconCircleCheck`** (spec §3.3). «Annulla» e «Ho cucinato» del foglio passano a `Button` con `busy`, le tacche con `disabled` (che in `StockGauge` è già `aria-disabled`); «Cucina» mentre la dispensa carica ha `unavailableReason` «Carico la dispensa…» (la riga che oggi gli sta sotto); «Ripristina» di una ricetta eliminata passa a `Button` con `busy` e `IconRestore`.
20. **Un gruppo d'ingredienti vuoto non mostra la sua intestazione**, e le righe non hanno linee fra loro (spec §2).
21. **Test esistenti che cambiano forma perché il controllo non c'è più**: la prova e2e dei € passa a leggere il `CostMeter` del dettaglio e della scheda, e il `CostPicker` del modulo di modifica (colori e 40 px); la prova in jsdom «dopo porzioni e costo cambiati nel dettaglio» diventa «dopo porzioni cambiate nel dettaglio e un costo cambiato sul server» — la garanzia (il modulo nasce da una lettura fresca, mai dalla copia in cache) resta la stessa.

## Criteri di accettazione

- [ ] Con la foto, il tasto «Ricette» sta dentro il riquadro della foto, il punto al suo centro è suo, il suo fondo è `card` e «Ricette» ci sta sopra 4,5:1 in chiaro e in scuro; senza foto (o se non carica) sta sopra il titolo, nel flusso.
- [ ] Accanto al titolo un `toolbar` «Azioni della ricetta» con il collegamento «Modifica» (→ `/ricette/:id/modifica`) e il pulsante «Elimina» (→ `useArchiveRecipe().archive`), tutti e due da 44×44 px. Sotto il titolo categoria e `CostMeter`; nessun pulsante «Costo N su 5» nel dettaglio; `grep -rn "updateRecipeCost\|CostPicker" frontend/src/features/cooking frontend/src/features/recipes/api.ts` vuoto.
- [ ] Lo stepper c'è sempre; senza porzioni il «+» ha `aria-disabled="true"` e la descrizione «Porzioni non indicate: si cambiano da «Modifica».», scritta una volta.
- [ ] Ogni riga d'ingrediente ha il pallino col nome del vocabolario; un principale quasi finito e non soddisfatto dice «non basta»; un secondario quasi finito no. I pallini stanno sopra 3:1 sul loro fondo nei due temi.
- [ ] «Cucina» e «Metti in lista ciò che manca» stanno dopo gli ingredienti e prima di «Procedimento»; «Metti in lista…» manda una `POST /shopping-list` per ogni riga con `satisfied === false` e nessun'altra, è `busy` in volo, sparisce quando tutto è soddisfatto; l'avviso dice «N in lista · M c'era già · K non è andata» (o «Era già tutto in lista.»), e «Riprova» rimanda solo le fallite.
- [ ] Il foglio della cottura ha un `radiogroup` «Quanto resta di <itemLabel>» per confezione, che parte dallo stato della confezione; toccare lo stato di partenza annulla; «Disponibile» si manda; «Rimetti in lista» per quasi finito e finito, spuntata per finito.
- [ ] Dopo «Ho cucinato» l'avviso dice «Segnato. …» e il fuoco è su «Cucina»; dopo «Annulla» il fuoco è su «Cucina» e l'avviso è vuoto.
- [ ] Dopo «Salva nel ricettario» e «Salva le modifiche» l'avviso dice «Salvata.» e si è sul dettaglio; `grep -rn "justSaved\|savedRef" frontend/src` vuoto, e nessun `navigate` porta più `state: { saved: true }`.
- [ ] «Apri l'originale» è alto almeno 44 px.
- [ ] vitest, typecheck, lint, build, pytest e l'e2e intera verdi; `style.spec.ts` ha cinque prove nuove a 375×812.
- [ ] `docs/prossimi-passi.md` e `next-steps.md` aggiornati (Task 9).

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
PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Dalla radice di `<worktree>`:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -rn "updateRecipeCost\|justSaved\|savedRef\|deletedRecipe" frontend/src
grep -rn "CostPicker" frontend/src/features/cooking
```

Expected: i tre `grep` non stampano niente. E l'e2e intera con i comandi delle Global Constraints.

## Fuori scope

- Il modulo della ricetta, la coda d'import, `CategorySelect`, le maiuscole degli ingredienti a video, le parole («dataset», «backend»…): sono del Piano 4 (Consegna 6b). Qui `AiDraftScreen.tsx` e `RecipeEditScreen.tsx` cambiano solo nel loro `onSaved`.
- Il ricettario e `useArchiveRecipe` (Piano 2): si usano come sono.
- «N dosi su M non si riscalano» che non dice quali, il procedimento diviso in passi, i minuti (spec §5).
- Il backend: nessuna rotta, nessuno schema, nessuna migrazione. La `PATCH /recipes/{id}` col costo resta (la usa ancora l'e2e, e un client vecchio in cache).
- Il fuoco perso dal «−» quando arriva a 1 da tastiera (diventa `disabled` mentre ha il fuoco, come oggi): va in `next-steps.md` come idea (Task 9), non si cambia qui.
- La regola «Rimetti in lista già spuntata solo per finito» (`tbd` in `next-steps.md`): resta com'è.

## Margine di autonomia

- **Liberi**: i nomi di variabili locali, helper di test e funzioni interne non fissati nelle interfacce; l'ordine delle classi Tailwind; la formulazione dei commenti, purché dicano il perché.
- **Non liberi**: le parole a video, esattamente come in questo piano; i nomi accessibili; i nomi dei file e degli export che un task successivo consuma (`missingToList.ts` con `sendMissing`, `missingNotice`, `MissingOutcome`; `AddMissingButton`; `ServingsStepper` con `value: number | null`; la prop `ref` di `Button`).
- **Nessuna dipendenza nuova**, nessuna migrazione, nessun token di colore nuovo.
- **Un test di oggi si cambia solo per seguire un controllo ricostruito** (i tre pulsanti del foglio → le tacche; le pastiglie di testo → i pallini; il `CostPicker` del dettaglio → il `CostMeter`; la `<p role=status>` del dettaglio → l'avviso unico), mai per indebolirlo: dove un'asserzione su `aria-pressed` diventa un'asserzione su `aria-checked` resta altrettanto stretta. Le migrazioni ammesse sono elencate nei task; se ne serve un'altra, scrivila nel report con il perché.
- **Se il Piano 2 ha lasciato un test dell'eliminazione** (in `RecipeDetailActions.test.tsx` o `modifica-ricette.spec.ts`) che dipende dalla posizione di «Elimina» in fondo al dettaglio, si cambia solo quella premessa (Task 8, Step 4), non ciò che il test prova dell'avviso.
- Una decisione non coperta dal piano e non reversibile → si ferma quel task, si fa commit del lavoro parziale sul ramo, lo si segna `bloccato` in `next-steps.md` con la domanda precisa per Mattia, e si passa al task successivo. Una scelta reversibile e a basso impatto → la più conservativa, annotata nel report della notte (`docs/night-reports/<data>.md`).
- Un test che fallisce e non si risolve in modo ragionevole: niente test disattivati, niente asserzioni indebolite; `bloccato` con la diagnosi.

## Dipendenze

**Parte da `night/c4-ricette`** (Piano 2, Consegna 4, `docs/superpowers/plans/2026-09-30-ridisegno-ricette.md`), che a sua volta parte da `night/c6a-pulsanti` (Piano 1, Consegna 6a, `docs/superpowers/plans/2026-09-30-ridisegno-pulsanti-accesso-anagrafica.md`). I tre rami si uniscono in quest'ordine, e il Piano 4 (`night/c6b-modulo-coda-parole`) parte da questo. Dai piani precedenti servono:

- **dal Piano 1**: `Button` con `unavailableReason?: string` (`aria-disabled="true"`, clic e submit ignorati, il fuoco resta, un `<p>` col motivo sotto di sé collegato con `aria-describedby`) e `accessibleName?: string`. Qui si usa `unavailableReason` (lo stepper, «Cucina» mentre la dispensa carica); `accessibleName` non serve.
- **dal Piano 2**: `frontend/src/features/recipes/useArchiveRecipe.ts` con `useArchiveRecipe(): { archive(recipe: { id: string; title: string }): void; pending: boolean }` (archivia, toglie la riga dalla cache del ricettario, avviso «Eliminata: <titolo>» con «Annulla», porta a `/ricette`); il dettaglio lo usa già al posto di `navigate(..., { state: { deletedRecipe } })`. Qui il dettaglio si riscrive e continua a chiamarlo dall'icona «Elimina». Se il Piano 2 ha aggiunto `main_department` ai tipi `RecipeSummary`/`RecipeDetail`, i test di questo piano costruiscono le ricette per spread delle costanti già esistenti nei file di test (`{ ...DETAIL, … }`), quindi lo portano con sé.

La Consegna 5 in `next-steps.md` può stare in «Pronti per la notte» (`[pronto]`) o ancora in «Da approfondire» (`[tbd]`): il Task 9 la trova in tutti e due i casi.

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `frontend/src/components/ui/Button.tsx`, `Button.test.tsx` | 1 | la prop `ref` |
| `frontend/src/features/cooking/missingToList.ts` (nuovo) | 2 | `sendMissing`, `missingNotice`, `MissingOutcome` |
| `frontend/src/features/cooking/missingToList.test.ts` (nuovo) | 2 | test a tabella |
| `frontend/src/features/cooking/AddMissingButton.tsx` (nuovo) | 3 | «Metti in lista ciò che manca» |
| `frontend/src/features/cooking/AddMissingButton.test.tsx` (nuovo) | 3 | test |
| `frontend/src/features/cooking/ServingsStepper.tsx` | 4 | `value: number \| null`, `Button`, il motivo |
| `frontend/src/features/cooking/ServingsStepper.test.tsx` (nuovo) | 4 | test |
| `frontend/src/features/cooking/CookSheet.tsx`, `CookSheet.test.tsx` | 5 | `StockGauge`, `Button` con `busy` |
| `frontend/src/features/ai-draft/AiDraftScreen.tsx`, `AiDraftScreen.test.tsx` | 6 | «Salvata.» dall'avviso |
| `frontend/src/features/recipe-form/RecipeEditScreen.tsx`, `RecipeEditScreen.test.tsx` | 6 | «Salvata.» dall'avviso, via `state.saved` |
| `frontend/src/features/cooking/RecipeDetailScreen.tsx` | 7 | riscritto |
| `frontend/src/features/cooking/RecipeDetailScreen.test.tsx` | 7 | migrato e allargato |
| `frontend/src/features/cooking/RecipeDetailActions.test.tsx` | 7 | il `toolbar`; «Salvata» non è più del dettaglio |
| `frontend/src/features/recipes/api.ts` | 7 | via `updateRecipeCost` |
| `frontend/e2e/cooking.spec.ts`, `frontend/e2e/modifica-ricette.spec.ts` | 8 | le tacche; il pallino «manca» |
| `frontend/e2e/style.spec.ts` | 8 | la prova dei €, le tacche del foglio, cinque prove nuove |
| `docs/prossimi-passi.md`, `next-steps.md` | 9 | Consegna 5, T4 |

---

### Task 1: `Button` passa il `ref` al pulsante vero

**Files:**
- Modify: `frontend/src/components/ui/Button.tsx`
- Test: `frontend/src/components/ui/Button.test.tsx`

**Interfaces:**
- Produces: `Button` accetta `ref?: Ref<HTMLButtonElement>` e lo mette sul `<button>`. Il Task 7 lo usa per ridare il fuoco a «Cucina».

- [ ] **Step 1: Il test che fallisce**

In `frontend/src/components/ui/Button.test.tsx` aggiungi in cima, fra gli import:

```tsx
import { createRef } from "react";
```

e dentro `describe("Button", …)`, dopo il test «è type=button se non si dice altro: dentro un modulo non deve inviarlo», aggiungi:

```tsx
  it("il `ref` arriva al pulsante vero: chi deve ridargli il fuoco lo trova", () => {
    const ref = createRef<HTMLButtonElement>();
    render(<Button ref={ref}>Cucina</Button>);
    expect(ref.current).toBe(screen.getByRole("button", { name: "Cucina" }));
  });
```

- [ ] **Step 2: Vederlo fallire**

Run (da `frontend/`): `npx vitest run src/components/ui/Button.test.tsx`
Expected: FAIL sul test nuovo (`ref.current` è `null`).

- [ ] **Step 3: Il codice**

In `frontend/src/components/ui/Button.tsx`:
1. aggiungi `Ref` all'import dei tipi di `react` (oggi `import type { MouseEvent, ReactNode } from "react";` → `import type { MouseEvent, ReactNode, Ref } from "react";`; se il Piano 1 ha cambiato quella riga, aggiungi `Ref` a quella che c'è);
2. nel tipo `Common`, dopo `className?: string;`, aggiungi:
   ```ts
     /** Il pulsante vero, per chi deve ridargli il fuoco (il dettaglio della ricetta, quando
      * il foglio della cottura si chiude). In React 19 `ref` è una prop come le altre. */
     ref?: Ref<HTMLButtonElement>;
   ```
3. sull'elemento `<button` che il componente disegna, come primo attributo dopo `type={type}`, aggiungi `ref={props.ref}`.

Non cambiare altro del primitivo.

- [ ] **Step 4: Verde**

Run: `npx vitest run src/components/ui/Button.test.tsx && npm run typecheck && npm run lint`
Expected: tutto verde, un test in più.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/Button.tsx frontend/src/components/ui/Button.test.tsx
git commit -m "Button: il ref arriva al pulsante vero, per ridargli il fuoco"
```

---

### Task 2: Le funzioni di «Metti in lista ciò che manca»

**Files:**
- Create: `frontend/src/features/cooking/missingToList.ts`
- Test: `frontend/src/features/cooking/missingToList.test.ts`

**Interfaces:**
- Consumes: `addShoppingItem(rawText, ingredientId)` di `frontend/src/features/shopping-list/api.ts` (risponde `ShoppingItemAdded`, con `added` falso quando l'ingrediente era già da comprare: S18).
- Produces: `type MissingOutcome = { added: number; already: number; failed: RecipeIngredientLine[] }`; `sendMissing(lines): Promise<MissingOutcome>` (non rifiuta mai); `missingNotice(outcome): string`. Il Task 3 li usa.

- [ ] **Step 1: I test che falliscono**

Crea `frontend/src/features/cooking/missingToList.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { missingNotice, sendMissing, type MissingOutcome } from "./missingToList";
import type { RecipeIngredientLine } from "../../domain/types";

function riga(id: string, nome: string): RecipeIngredientLine {
  return {
    ingredient_id: id, ingredient_name: nome, role: "primary", quantity_text: null,
    quantity_display: null, quantity_scaled: false, note: null,
    availability: "missing", satisfied: false,
  };
}

const BASILICO = riga("i1", "basilico");
const POMODORO = riga("i2", "pomodoro");
const AGLIO = riga("i3", "aglio");

/** `POST /shopping-list` finta: lo stato della risposta si sceglie per ingrediente.
 * 201 è «entrata», 200 è «c'era già» (S18), dal 400 in su un guasto. */
function stubLista(risposte: Record<string, number>) {
  const spy = vi.fn((_url: unknown, init?: RequestInit) => {
    const { ingredient_id } = JSON.parse(String(init!.body)) as { ingredient_id: string };
    const status = risposte[ingredient_id];
    const corpo = status >= 400 ? { detail: "no" } : { id: `s-${ingredient_id}`, added: status === 201 };
    return Promise.resolve(new Response(JSON.stringify(corpo), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("missingNotice", () => {
  // Le frasi dell'avviso (decise il 2026-09-29, più le tre forme che il piano aggiunge:
  // i plurali e il caso in cui non è andata nessuna). Nessun participio che concorda
  // col nome di un ingrediente.
  it.each<[string, MissingOutcome, string]>([
    ["tutte nuove", { added: 3, already: 0, failed: [] }, "3 in lista"],
    ["una sola", { added: 1, already: 0, failed: [] }, "1 in lista"],
    ["una c'era già", { added: 2, already: 1, failed: [] }, "2 in lista · 1 c'era già"],
    ["due c'erano già", { added: 1, already: 2, failed: [] }, "1 in lista · 2 c'erano già"],
    ["c'era già tutto", { added: 0, already: 3, failed: [] }, "Era già tutto in lista."],
    ["un guasto", { added: 2, already: 0, failed: [BASILICO] }, "2 in lista · 1 non è andata"],
    [
      "tutto insieme",
      { added: 1, already: 1, failed: [BASILICO, POMODORO] },
      "1 in lista · 1 c'era già · 2 non sono andate",
    ],
    ["niente di nuovo, un guasto", { added: 0, already: 1, failed: [BASILICO] }, "1 c'era già · 1 non è andata"],
    ["solo guasti", { added: 0, already: 0, failed: [BASILICO, POMODORO] }, "Non è andata: la lista è com'era."],
  ])("%s", (_caso, esito, atteso) => {
    expect(missingNotice(esito)).toBe(atteso);
  });
});

describe("sendMissing", () => {
  it("una POST per riga, col nome e l'ingrediente, e conta chi è entrato e chi c'era già", async () => {
    const spy = stubLista({ i1: 201, i2: 200 });

    expect(await sendMissing([BASILICO, POMODORO])).toEqual({ added: 1, already: 1, failed: [] });
    const mandate = spy.mock.calls.map(([url, init]) => [
      String(url),
      init!.method,
      JSON.parse(String(init!.body)),
    ]);
    expect(mandate).toEqual([
      ["/api/v1/shopping-list", "POST", { raw_text: "basilico", ingredient_id: "i1" }],
      ["/api/v1/shopping-list", "POST", { raw_text: "pomodoro", ingredient_id: "i2" }],
    ]);
  });

  it("partono tutte insieme: una risposta lenta non ferma le altre", async () => {
    let rilascia = () => {};
    const lenta = new Promise<void>((resolve) => {
      rilascia = resolve;
    });
    const spy = vi.fn(async (_url: unknown, init?: RequestInit) => {
      const { ingredient_id } = JSON.parse(String(init!.body)) as { ingredient_id: string };
      if (ingredient_id === "i1") await lenta;
      return new Response(JSON.stringify({ id: "s", added: true }), { status: 201 });
    });
    vi.stubGlobal("fetch", spy);

    const inCorso = sendMissing([BASILICO, POMODORO, AGLIO]);
    // la prima è ancora per aria, e le altre due sono già partite
    await vi.waitFor(() => expect(spy).toHaveBeenCalledTimes(3));
    rilascia();
    expect(await inCorso).toEqual({ added: 3, already: 0, failed: [] });
  });

  it("una riga che non arriva finisce fra le fallite, e le altre contano lo stesso", async () => {
    stubLista({ i1: 201, i2: 500, i3: 200 });
    expect(await sendMissing([BASILICO, POMODORO, AGLIO])).toEqual({
      added: 1,
      already: 1,
      failed: [POMODORO],
    });
  });
});
```

- [ ] **Step 2: Vederli fallire**

Run (da `frontend/`): `npx vitest run src/features/cooking/missingToList.test.ts`
Expected: FAIL, il modulo `./missingToList` non esiste.

- [ ] **Step 3: Il codice**

Crea `frontend/src/features/cooking/missingToList.ts`:

```ts
import { addShoppingItem } from "../shopping-list/api";
import type { RecipeIngredientLine } from "../../domain/types";

/** Com'è andata «Metti in lista ciò che manca» (spec T3 §4.6): quante voci sono entrate
 * in lista, quante c'erano già — il server non scrive il doppione e risponde con la voce
 * che c'era, `added` falso (S18) — e quali righe non sono arrivate, da rimandare con
 * «Riprova». */
export type MissingOutcome = {
  added: number;
  already: number;
  failed: RecipeIngredientLine[];
};

/** Una `POST /shopping-list` per riga, tutte insieme. Quali righe mancano non si decide
 * qui: le passa chi chiama, filtrate su `satisfied`, che arriva dal server (la regola
 * primario/secondario vive nel backend). Il testo della voce è il nome dell'ingrediente,
 * e l'ingrediente va con lui: così la voce nasce agganciata, e un doppione non nasce.
 *
 * `allSettled` e non `all`: una riga che non arriva non deve far dimenticare quelle
 * arrivate, che in lista ci sono davvero. Per questo la promessa non rifiuta mai. */
export async function sendMissing(lines: RecipeIngredientLine[]): Promise<MissingOutcome> {
  const results = await Promise.allSettled(
    lines.map((line) => addShoppingItem(line.ingredient_name, line.ingredient_id))
  );
  const outcome: MissingOutcome = { added: 0, already: 0, failed: [] };
  results.forEach((result, index) => {
    if (result.status === "rejected") outcome.failed.push(lines[index]);
    else if (result.value.added) outcome.added += 1;
    else outcome.already += 1;
  });
  return outcome;
}

/** La frase dell'avviso. Numeri e non nomi: l'avviso è una riga sola, e i nomi sono
 * già a video, sulla ricetta. */
export function missingNotice({ added, already, failed }: MissingOutcome): string {
  if (failed.length === 0 && added === 0) return "Era già tutto in lista.";
  if (added === 0 && already === 0) return "Non è andata: la lista è com'era.";
  const parts: string[] = [];
  if (added > 0) parts.push(`${added} in lista`);
  if (already > 0) parts.push(already === 1 ? "1 c'era già" : `${already} c'erano già`);
  if (failed.length > 0) {
    parts.push(failed.length === 1 ? "1 non è andata" : `${failed.length} non sono andate`);
  }
  return parts.join(" · ");
}
```

- [ ] **Step 4: Verde**

Run: `npx vitest run src/features/cooking/missingToList.test.ts && npm run typecheck && npm run lint`
Expected: 12 test verdi (9 frasi, 3 invii).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/cooking/missingToList.ts frontend/src/features/cooking/missingToList.test.ts
git commit -m "dettaglio ricetta: le funzioni di «Metti in lista ciò che manca», in parallelo e con la frase dell'avviso"
```

---

### Task 3: Il pulsante «Metti in lista ciò che manca»

**Files:**
- Create: `frontend/src/features/cooking/AddMissingButton.tsx`
- Test: `frontend/src/features/cooking/AddMissingButton.test.tsx`

**Interfaces:**
- Consumes: `sendMissing`, `missingNotice` (Task 2); `Button` con `busy`; `useNotice` da `frontend/src/components/ui/noticeContext.ts`.
- Produces: `AddMissingButton({ lines }: { lines: RecipeIngredientLine[] })` — le righe **già filtrate** su `satisfied === false`; con zero righe non disegna niente. Il Task 7 lo mette sotto «Cucina».

- [ ] **Step 1: I test che falliscono**

Crea `frontend/src/features/cooking/AddMissingButton.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AddMissingButton } from "./AddMissingButton";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import type { RecipeIngredientLine } from "../../domain/types";

const NOME = "Metti in lista ciò che manca";

function riga(id: string, nome: string): RecipeIngredientLine {
  return {
    ingredient_id: id, ingredient_name: nome, role: "primary", quantity_text: null,
    quantity_display: null, quantity_scaled: false, note: null,
    availability: "missing", satisfied: false,
  };
}

const BASILICO = riga("i1", "basilico");
const POMODORO = riga("i2", "pomodoro");

// senza `NoticeProvider` l'avviso non avrebbe dove comparire
function renderButton(
  lines: RecipeIngredientLine[],
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
) {
  render(
    <QueryClientProvider client={client}>
      <NoticeProvider>
        <AddMissingButton lines={lines} />
      </NoticeProvider>
    </QueryClientProvider>
  );
  return client;
}

/** `POST /shopping-list` finta: per ogni ingrediente una coda di stati, consumata una
 * risposta alla volta (l'ultima resta). 201 entrata, 200 c'era già, dal 400 un guasto. */
function stubLista(code: Record<string, number[]>) {
  const spy = vi.fn((_url: unknown, init?: RequestInit) => {
    const { ingredient_id } = JSON.parse(String(init!.body)) as { ingredient_id: string };
    const coda = code[ingredient_id];
    const status = coda.length > 1 ? coda.shift()! : coda[0];
    const corpo = status >= 400 ? { detail: "no" } : { id: `s-${ingredient_id}`, added: status === 201 };
    return Promise.resolve(new Response(JSON.stringify(corpo), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function mandati(spy: ReturnType<typeof stubLista>) {
  return spy.mock.calls.map(([, init]) => JSON.parse(String(init!.body)).ingredient_id as string);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AddMissingButton", () => {
  it("manda le righe che riceve, e l'avviso dice com'è andata", async () => {
    const spy = stubLista({ i1: [201], i2: [200] });
    renderButton([BASILICO, POMODORO]);

    await userEvent.click(screen.getByRole("button", { name: NOME }));

    expect(await screen.findByText("1 in lista · 1 c'era già")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("1 in lista · 1 c'era già");
    expect(mandati(spy)).toEqual(["i1", "i2"]);
    // tutto arrivato: niente da riprovare
    expect(screen.queryByRole("button", { name: "Riprova" })).toBeNull();
  });

  it("in volo è spento tenendo il fuoco, e un secondo tocco non manda niente", async () => {
    let rilascia = () => {};
    const inVolo = new Promise<void>((resolve) => {
      rilascia = resolve;
    });
    const spy = vi.fn(async () => {
      await inVolo;
      return new Response(JSON.stringify({ id: "s", added: true }), { status: 201 });
    });
    vi.stubGlobal("fetch", spy);
    renderButton([BASILICO]);

    const pulsante = screen.getByRole("button", { name: NOME });
    await userEvent.click(pulsante);
    expect(pulsante).toHaveAttribute("aria-disabled", "true");
    expect(pulsante).not.toBeDisabled();
    expect(pulsante).toHaveFocus();
    await userEvent.click(pulsante);
    expect(spy).toHaveBeenCalledTimes(1);

    rilascia();
    expect(await screen.findByText("1 in lista")).toBeInTheDocument();
    // `busy` si spegne nel `finally`, un giro dopo l'avviso
    await vi.waitFor(() => expect(pulsante).not.toHaveAttribute("aria-disabled", "true"));
  });

  it("con dei guasti l'avviso offre «Riprova», che rimanda solo le righe fallite", async () => {
    const spy = stubLista({ i1: [201], i2: [500, 201] });
    renderButton([BASILICO, POMODORO]);

    await userEvent.click(screen.getByRole("button", { name: NOME }));
    expect(await screen.findByText("1 in lista · 1 non è andata")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Riprova" }));
    expect(await screen.findByText("1 in lista")).toBeInTheDocument();
    expect(mandati(spy)).toEqual(["i1", "i2", "i2"]);
  });

  it("dopo, la lista della spesa si rilegge", async () => {
    stubLista({ i1: [201] });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    client.setQueryData(["shopping-list"], []);
    renderButton([BASILICO], client);

    await userEvent.click(screen.getByRole("button", { name: NOME }));

    await vi.waitFor(() =>
      expect(client.getQueryState(["shopping-list"])?.isInvalidated).toBe(true)
    );
  });

  it("senza righe mancanti non c'è", () => {
    renderButton([]);
    expect(screen.queryByRole("button", { name: NOME })).toBeNull();
  });
});
```

- [ ] **Step 2: Vederli fallire**

Run: `npx vitest run src/features/cooking/AddMissingButton.test.tsx`
Expected: FAIL, il modulo `./AddMissingButton` non esiste.

- [ ] **Step 3: Il codice**

Crea `frontend/src/features/cooking/AddMissingButton.tsx`:

```tsx
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "../../components/ui/Button";
import { IconShoppingCartPlus } from "../../components/ui/icons";
import { useNotice } from "../../components/ui/noticeContext";
import { missingNotice, sendMissing } from "./missingToList";
import type { RecipeIngredientLine } from "../../domain/types";

/** «Metti in lista ciò che manca» (spec T3 §4.6): la freccia ricetta → lista, che prima
 * esisteva solo dopo aver cucinato. Riceve le righe già filtrate su `satisfied`, che
 * decide il server: questo pulsante non sa quale riga basti e quale no.
 *
 * Non una `useMutation`, come l'«Annulla» della dispensa (`undoRemove` in
 * `PantryScreen.tsx`): il «Riprova» vive nell'avviso, che è dell'app e non di questo
 * schermo, e si può toccare anche dopo aver lasciato la ricetta. `busy` e non
 * `disabled` mentre è in volo: il pulsante tiene il fuoco (regola del Piano 1). */
export function AddMissingButton({ lines }: { lines: RecipeIngredientLine[] }) {
  const notice = useNotice();
  const queryClient = useQueryClient();
  const [pending, setPending] = useState(false);

  function send(toSend: RecipeIngredientLine[]) {
    setPending(true);
    void sendMissing(toSend)
      .then((outcome) => {
        // la lista è cambiata anche se una riga non è arrivata: si rilegge comunque
        void queryClient.invalidateQueries({ queryKey: ["shopping-list"] });
        notice({
          text: missingNotice(outcome),
          action:
            outcome.failed.length > 0
              ? { label: "Riprova", onClick: () => send(outcome.failed) }
              : undefined,
        });
      })
      .finally(() => setPending(false));
  }

  if (lines.length === 0) return null;
  return (
    <Button
      variant="secondary"
      shape="block"
      icon={IconShoppingCartPlus}
      busy={pending}
      onClick={() => send(lines)}
    >
      Metti in lista ciò che manca
    </Button>
  );
}
```

- [ ] **Step 4: Verde**

Run: `npx vitest run src/features/cooking/AddMissingButton.test.tsx && npm run typecheck && npm run lint`
Expected: 5 test verdi, typecheck e lint puliti.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/cooking/AddMissingButton.tsx frontend/src/features/cooking/AddMissingButton.test.tsx
git commit -m "dettaglio ricetta: «Metti in lista ciò che manca», con l'avviso e «Riprova» per le sole righe fallite"
```

---

### Task 4: Lo stepper delle porzioni si vede sempre

**Files:**
- Modify: `frontend/src/features/cooking/ServingsStepper.tsx` (riscritto)
- Test: `frontend/src/features/cooking/ServingsStepper.test.tsx` (nuovo)

**Interfaces:**
- Consumes: `Button` con `icon`/`label`, `disabled` e `unavailableReason` (Piano 1).
- Produces: `ServingsStepper({ value, onChange }: { value: number | null; onChange: (next: number) => void })`. `null` = la ricetta non dichiara le porzioni. Il Task 7 lo usa.

- [ ] **Step 1: I test che falliscono**

Crea `frontend/src/features/cooking/ServingsStepper.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ServingsStepper } from "./ServingsStepper";

const MOTIVO = "Porzioni non indicate: si cambiano da «Modifica».";

describe("ServingsStepper", () => {
  it("con le porzioni, i due tasti cambiano il numero", async () => {
    const onChange = vi.fn();
    render(<ServingsStepper value={2} onChange={onChange} />);

    expect(screen.getByText("2")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Una porzione in più" }));
    await userEvent.click(screen.getByRole("button", { name: "Una porzione in meno" }));
    expect(onChange.mock.calls).toEqual([[3], [1]]);
  });

  it("ai bordi il tasto che uscirebbe dalla scala è spento", () => {
    const { rerender } = render(<ServingsStepper value={1} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Una porzione in meno" })).toBeDisabled();
    rerender(<ServingsStepper value={50} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: "Una porzione in più" })).toBeDisabled();
  });

  it("senza porzioni si vede lo stesso, e dice una volta sola perché non si usa", async () => {
    // dal giro di T3: lo stepper spariva senza dirlo, e non si capiva se mancasse
    // qualcosa o se la ricetta non si potesse riscalare
    const onChange = vi.fn();
    render(<ServingsStepper value={null} onChange={onChange} />);

    const piu = screen.getByRole("button", { name: "Una porzione in più" });
    expect(piu).toHaveAttribute("aria-disabled", "true");
    expect(piu).toHaveAccessibleDescription(MOTIVO);
    expect(screen.getAllByText(MOTIVO)).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Una porzione in meno" })).toBeDisabled();
    expect(screen.getByText("—")).toBeInTheDocument();

    await userEvent.click(piu);
    expect(onChange).not.toHaveBeenCalled();
  });

  it("i due tasti sono di sola icona, col nome intero, e bersagli da pollice", () => {
    render(<ServingsStepper value={2} onChange={() => {}} />);
    for (const name of ["Una porzione in meno", "Una porzione in più"]) {
      const tasto = screen.getByRole("button", { name });
      expect(tasto.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
      expect(tasto.className).toContain("size-11");
    }
  });
});
```

- [ ] **Step 2: Vederli fallire**

Run: `npx vitest run src/features/cooking/ServingsStepper.test.tsx`
Expected: FAIL (il terzo e il quarto test: oggi i tasti hanno un «−»/«+» di testo e `value` non accetta `null`).

- [ ] **Step 3: Il codice**

Sostituisci tutto `frontend/src/features/cooking/ServingsStepper.tsx` con:

```tsx
import { Button } from "../../components/ui/Button";
import { IconMinus, IconPlus } from "../../components/ui/icons";

// Il perché dello stepper fermo. Sta sul «+» soltanto: `Button` disegna il motivo sotto
// di sé, e con due pulsanti la stessa frase comparirebbe due volte in una riga.
const SERVINGS_UNKNOWN = "Porzioni non indicate: si cambiano da «Modifica».";

/** Per quante porzioni si vuole la ricetta.
 *
 * Si vede sempre (spec T3 §4.6): senza porzioni dichiarate non c'è una base da cui
 * riscalare, e invece di sparire — dal giro, «senza porzioni lo stepper sparisce senza
 * dirlo» — lo dice. Il «−» a porzioni ignote è spento come ai bordi: non c'è niente da
 * togliere. I due tasti sono bersagli da 44 px (`Button` di sola icona): questo si tocca
 * in cucina, con le mani occupate. */
export function ServingsStepper({
  value,
  onChange,
}: {
  value: number | null;
  onChange: (next: number) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <span className="text-sm text-ink-soft">Porzioni</span>
      <Button
        icon={IconMinus}
        label="Una porzione in meno"
        disabled={value === null || value <= 1}
        onClick={() => {
          if (value !== null) onChange(value - 1);
        }}
      />
      <span className="min-w-8 text-center font-medium" aria-live="polite">
        {value ?? "—"}
      </span>
      <Button
        icon={IconPlus}
        label="Una porzione in più"
        disabled={value !== null && value >= 50}
        unavailableReason={value === null ? SERVINGS_UNKNOWN : undefined}
        onClick={() => {
          if (value !== null) onChange(value + 1);
        }}
      />
    </div>
  );
}
```

Il chiamante di oggi (`RecipeDetailScreen.tsx`) passa sempre un numero, quindi compila ancora; il Task 7 gli fa passare `null`.

- [ ] **Step 4: Verde**

Run: `npx vitest run src/features/cooking/ && npm run typecheck && npm run lint`
Expected: i 4 test nuovi verdi, e verdi anche i test di oggi del dettaglio (i nomi «Una porzione in meno/in più» non sono cambiati).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/cooking/ServingsStepper.tsx frontend/src/features/cooking/ServingsStepper.test.tsx
git commit -m "dettaglio ricetta: lo stepper delle porzioni si vede sempre, e senza porzioni dice perché"
```

---

### Task 5: Il foglio della cottura con le tacche

**Files:**
- Modify: `frontend/src/features/cooking/CookSheet.tsx` (riscritto)
- Test: `frontend/src/features/cooking/CookSheet.test.tsx`

**Interfaces:**
- Consumes: `StockGauge({ status, onChange, itemName, disabled })` di `frontend/src/components/ui/StockGauge.tsx` (radiogroup «Quanto resta di <itemName>», tre `radio` chiamati «Finito», «Quasi finito», «Disponibile»; toccare lo stato mostrato non chiama `onChange`; `disabled` è `aria-disabled`).
- Produces: la stessa `CookSheet({ recipe, pantryItems, onDone })` di oggi. Il payload verso `POST /recipes/{id}/cook` non cambia forma.

- [ ] **Step 1: I test nuovi, che falliscono**

In `frontend/src/features/cooking/CookSheet.test.tsx`, dentro `describe("CookSheet", …)`, dopo il test «dichiarare quasi finito manda 'low' e non spunta il riacquisto», aggiungi:

```tsx
  it("le tacche partono da com'è la confezione: niente toccato è invariato", async () => {
    const spy = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ event_id: "e1", updated: 0, restocked: 0 }), { status: 201 }
    ));
    vi.stubGlobal("fetch", spy);

    renderSheet();
    const yogurt = screen.getByText("Total 0%").closest("li")!;
    const pesca = screen.getByText("Pesca").closest("li")!;
    expect(within(yogurt).getByRole("radio", { name: "Disponibile" })).toHaveAttribute("aria-checked", "true");
    expect(within(pesca).getByRole("radio", { name: "Quasi finito" })).toHaveAttribute("aria-checked", "true");
    // e nessuna domanda sul rientro finché non si tocca niente
    expect(screen.queryByRole("checkbox")).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Ho cucinato" }));
    expect(JSON.parse(spy.mock.calls[0][1].body).transitions).toEqual([]);
  });

  it("toccare di nuovo lo stato di partenza annulla la scelta", async () => {
    const spy = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ event_id: "e1", updated: 0, restocked: 0 }), { status: 201 }
    ));
    vi.stubGlobal("fetch", spy);

    renderSheet();
    const row = screen.getByText("Total 0%").closest("li")!;
    await userEvent.click(within(row).getByRole("radio", { name: "Finito" }));
    expect(within(row).getByRole("checkbox", { name: /Rimetti in lista/ })).toBeChecked();

    await userEvent.click(within(row).getByRole("radio", { name: "Disponibile" }));
    expect(within(row).getByRole("radio", { name: "Disponibile" })).toHaveAttribute("aria-checked", "true");
    expect(within(row).queryByRole("checkbox")).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Ho cucinato" }));
    expect(JSON.parse(spy.mock.calls[0][1].body).transitions).toEqual([]);
  });

  it("«Disponibile» si può scegliere: una confezione data per quasi finita che era ancora piena", async () => {
    const spy = vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ event_id: "e1", updated: 1, restocked: 0 }), { status: 201 }
    ));
    vi.stubGlobal("fetch", spy);

    renderSheet();
    const row = screen.getByText("Pesca").closest("li")!;
    await userEvent.click(within(row).getByRole("radio", { name: "Disponibile" }));
    // tornare disponibile non fa rientrare niente in lista: la domanda non c'è
    expect(within(row).queryByRole("checkbox")).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Ho cucinato" }));
    expect(JSON.parse(spy.mock.calls[0][1].body).transitions).toEqual([
      { pantry_item_id: "p3", to_status: "available", restock: false },
    ]);
  });

  it("mentre registra, tacche e pulsanti si spengono tenendo il fuoco", async () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>(() => {})));

    renderSheet();
    const fatto = screen.getByRole("button", { name: "Ho cucinato" });
    await userEvent.click(fatto);

    expect(fatto).toHaveAttribute("aria-disabled", "true");
    expect(fatto).toHaveFocus();
    expect(screen.getByRole("button", { name: "Annulla" })).toHaveAttribute("aria-disabled", "true");
    const row = screen.getByText("Total 0%").closest("li")!;
    const finito = within(row).getByRole("radio", { name: "Finito" });
    expect(finito).toHaveAttribute("aria-disabled", "true");
    await userEvent.click(finito);
    expect(finito).toHaveAttribute("aria-checked", "false");
  });
```

- [ ] **Step 2: Migrare i test di oggi al controllo nuovo**

Nello stesso file, e solo queste righe (il resto dei test resta com'è):

1. In «due confezioni identiche tranne la data d'ingresso restano distinguibili», le due righe
   `await userEvent.click(within(first).getByRole("button", { name: "Finito" }));` e `…within(second)…` → `getByRole("radio", { name: "Finito" })`.
2. In «dichiarare finito un prodotto propone il riacquisto, già spuntato», «invia le transizioni scelte e passa l'esito del backend a onDone», «una voce sparita dalla dispensa a foglio aperto non entra nel payload», «una cottura riuscita invalida dispensa, lista della spesa e ricette» e «si può togliere la spunta al riacquisto di una voce finita»: ogni `within(row).getByRole("button", { name: "Finito" })` → `within(row).getByRole("radio", { name: "Finito" })`.
3. In «dichiarare quasi finito manda 'low' e non spunta il riacquisto»: `within(row).getByRole("button", { name: "Quasi finito" })` → `within(row).getByRole("radio", { name: "Quasi finito" })`.
4. In «una voce comparsa a foglio aperto non rompe il foglio», sostituisci l'asserzione finale con:
   ```tsx
    // la confezione nuova parte da com'è, come le altre: «Disponibile»
    expect(within(row).getByRole("radio", { name: "Disponibile" })).toHaveAttribute(
      "aria-checked",
      "true"
    );
   ```
5. Il test «le tre scelte sono un gruppo con nome, con bersagli da pollice» diventa:
   ```tsx
  it("le tre tacche sono un gruppo con nome, con bersagli da pollice", async () => {
    // Le tacche della dispensa (StockGauge, spec T3 §4.4), da 44px (`size-11`): lo stesso
    // controllo per lo stesso giudizio. Il nome del gruppo porta prodotto e marca, come
    // prima: per chi legge con lo screen reader tre «Finito» senza confezione non
    // dicono nulla.
    renderSheet();
    const row = screen.getByText("Total 0%").closest("li")!;
    const group = within(row).getByRole("radiogroup");
    expect(group.getAttribute("aria-label")).toContain("Total 0%");
    expect(group.getAttribute("aria-label")).toContain("Fage");
    const tacche = within(group).getAllByRole("radio");
    expect(tacche).toHaveLength(3);
    for (const tacca of tacche) {
      expect(tacca).toHaveClass("size-11");
    }
  });
   ```
6. In «una cottura fallita lo dice, senza svuotare le scelte fatte», le due righe con `getByRole("button", { name: "Finito" })` → `getByRole("radio", { name: "Finito" })`, e l'asserzione finale `toHaveAttribute("aria-pressed", "true")` → `toHaveAttribute("aria-checked", "true")`.
7. Nel commento del test «ogni riga porta marca, nota e stato attuale, non il solo nome», la frase «Lo stato attuale serve anche a dare un referente a "Invariato".» diventa «Lo stato attuale dice anche da dove partono le tacche.».
8. In `frontend/src/features/cooking/RecipeDetailScreen.test.tsx` due test aprono il foglio e toccano «Finito» su «Pelati»: «una cottura riuscita dice quanto è tornato in lista, col numero del backend» e «dopo «Ho cucinato» l'esito viene in vista e prende il fuoco». In tutti e due, `within(row).getByRole("button", { name: "Finito" })` → `within(row).getByRole("radio", { name: "Finito" })`. Nient'altro di quel file cambia qui (lo riscrive il Task 7): così la suite resta verde a ogni commit.

- [ ] **Step 3: Vederli fallire**

Run: `npx vitest run src/features/cooking/CookSheet.test.tsx`
Expected: FAIL, i test che cercano `radio` e `radiogroup` (oggi sono pulsanti in un `group`).

- [ ] **Step 4: Il codice**

Sostituisci tutto `frontend/src/features/cooking/CookSheet.tsx` con:

```tsx
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { cookRecipe } from "../recipes/api";
import { STATUS_LABELS } from "../pantry/statusLabels";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { StockGauge } from "../../components/ui/StockGauge";
import { IconCircleCheck } from "../../components/ui/icons";
import type { CookResult, PantryItem, PantryStatus, RecipeDetail } from "../../domain/types";

type Choice = { status: PantryStatus | "unchanged"; restock: boolean };

// Una voce non toccata non è una transizione: è il valore di partenza di ogni riga
// e la risposta alla domanda che il foglio non fa.
const UNCHANGED: Choice = { status: "unchanged", restock: false };

function addedOn(item: PantryItem): string {
  return new Date(item.added_at).toLocaleDateString("it-IT");
}

// Tutto ciò che distingue una confezione da un'altra dello stesso ingrediente:
// prodotto, marca, nota, stato attuale e da quando è in dispensa. Serve sia scritto
// nella riga sia come nome accessibile dei controlli: senza, due sacchi di pasta
// senza codice a barre sono due righe identiche e la dichiarazione finisce su
// quello sbagliato — il vasetto vero resta "disponibile" e niente torna in lista.
function itemLabel(item: PantryItem): string {
  return [
    item.product_name ?? item.ingredient_name,
    item.product_brand,
    item.note,
    STATUS_LABELS[item.status],
    `in dispensa dal ${addedOn(item)}`,
  ]
    .filter(Boolean)
    .join(" · ");
}

export function CookSheet({
  recipe,
  pantryItems,
  onDone,
}: {
  recipe: RecipeDetail;
  pantryItems: PantryItem[];
  // l'esito arriva a chi ci sta sopra, che è l'unico a essere ancora montato dopo:
  // senza argomento quando si annulla, perché non c'è nessuna cottura da riferire
  onDone: (result?: CookResult) => void;
}) {
  // solo le voci di dispensa che appartengono a questa ricetta. La revisione opera
  // su vasetti concreti, non sull'ingrediente astratto: due vasetti di yogurt greco
  // sono due righe distinte, con due esiti distinti.
  //
  // Le voci già finite restano fuori: GET /pantry le restituisce finché non vengono
  // archiviate, e una confezione già finita non ha nulla da dichiarare dopo una
  // cottura — in mezzo a cinque "pasta" finite l'unico sacco vero diventa
  // impossibile da riconoscere. Si archiviano dalla dispensa, non da qui.
  const used = pantryItems.filter(
    (item) =>
      item.status !== "finished" &&
      recipe.ingredients.some((line) => line.ingredient_id === item.ingredient_id)
  );

  // niente istantanea al mount: le righe vengono da una prop viva (la query della
  // dispensa si aggiorna anche a foglio aperto) e una voce comparsa dopo non
  // troverebbe la sua scelta
  const [choices, setChoices] = useState<Record<string, Choice>>({});

  const queryClient = useQueryClient();
  const cook = useMutation({
    mutationFn: () =>
      cookRecipe(recipe.id, {
        // le porzioni per cui si è scalato, se si è scalato: è quel che si è
        // davvero cucinato. Il riporziona è «una vista» (spec §5.3) nel senso che
        // non si salva sulla ricetta — ma quante porzioni sono uscite dalla pentola
        // stasera è un fatto diverso, e `cooking_events` esiste senza consumatori
        // proprio perché la fase 3 ci trovi una storia vera su cui appoggiarsi.
        // Scrivere 2 dopo aver cucinato per 6 sarebbe invisibile oggi e sbagliato
        // per sempre.
        servings: recipe.scaled_to ?? recipe.servings ?? undefined,
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
      }),
    onSuccess: (result) => {
      // cucinare cambia sia la dispensa (gli stati appena dichiarati) sia la lista
      // della spesa (il riacquisto di ciò che è finito): senza invalidare entrambe
      // l'utente torna a schermate che non mostrano quel che è appena successo, e
      // questo è esattamente il cerchio che il task deve chiudere.
      queryClient.invalidateQueries({ queryKey: ["pantry"] });
      queryClient.invalidateQueries({ queryKey: ["shopping-list"] });
      // anche la ricetta appena cucinata va rinfrescata: la sua disponibilità per
      // ingrediente è calcolata sulla dispensa che abbiamo appena cambiato, e
      // senza questo l'utente torna al dettaglio e legge ancora lo stato vecchio.
      queryClient.invalidateQueries({ queryKey: ["recipe", recipe.id] });
      // e l'elenco ricette, perché missing/cookable di altre ricette dipendono
      // dalla stessa dispensa.
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
      // l'esito passa di sopra: chi ha dichiarato due vasetti finiti ha diritto di
      // sapere quanto è tornato in lista, e questo foglio sta per smontarsi
      onDone(result);
    },
  });

  // Le tacche partono da com'è la confezione (spec T3 §4.4, e decisione del 2026-09-29):
  // toccare lo stato di partenza vuol dire «come prima», cioè invariato, e annulla una
  // scelta fatta. «Disponibile» si può scegliere — una confezione data per quasi finita
  // che si scopre piena — e il backend lo accetta. Finito propone il riacquisto già
  // spuntato, quasi finito no (la regola di prima).
  function choose(item: PantryItem, status: PantryStatus) {
    setChoices((current) => ({
      ...current,
      [item.id]: status === item.status ? UNCHANGED : { status, restock: status === "finished" },
    }));
  }

  function setRestock(itemId: string, restock: boolean) {
    setChoices((current) => ({
      ...current,
      [itemId]: { ...(current[itemId] ?? UNCHANGED), restock },
    }));
  }

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-ink-soft">
        Tocca solo ciò che è cambiato. Ogni confezione si dichiara da sé.
      </p>

      {/* un foglio vuoto in silenzio si legge come un guasto: dire perché è vuoto
          costa una riga. Cucinare resta possibile: la cottura si registra comunque */}
      {used.length === 0 ? (
        <p className="text-sm text-ink-soft">
          Niente di questa ricetta è in dispensa: non c'è nulla da aggiornare.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {used.map((item) => {
            const choice = choices[item.id] ?? UNCHANGED;
            const label = itemLabel(item);
            return (
              <Card as="li" key={item.id} className="flex flex-col gap-1">
                <div className="flex items-center gap-2">
                  <div className="min-w-0 flex-1">
                    {/* la marca che hai comprato è più utile del nome generico */}
                    <p>
                      <span className="font-medium">{item.product_name ?? item.ingredient_name}</span>
                      {item.product_brand && (
                        <span className="ml-2 text-sm text-ink-faint">{item.product_brand}</span>
                      )}
                    </p>
                    {item.note && <p className="text-xs text-ink-soft">{item.note}</p>}
                    {/* lo stato di partenza dice da dove partono le tacche, e la data
                        separa il sacco di ieri da quello di stamattina */}
                    <p className="text-xs text-ink-soft">
                      {STATUS_LABELS[item.status]} · in dispensa dal {addedOn(item)}
                    </p>
                  </div>
                  {/* le stesse tacche della dispensa: lo stesso giudizio ha un
                      controllo solo (dal giro di T3). Il nome del gruppo porta tutto
                      ciò che distingue la confezione */}
                  <StockGauge
                    status={choice.status === "unchanged" ? item.status : choice.status}
                    onChange={(next) => choose(item, next)}
                    itemName={label}
                    disabled={cook.isPending}
                  />
                </div>
                {(choice.status === "low" || choice.status === "finished") && (
                  <label className="flex min-h-11 items-center gap-2.5 text-sm text-ink-soft">
                    <input
                      type="checkbox"
                      aria-label={`Rimetti in lista ${label}`}
                      checked={choice.restock}
                      onChange={(e) => setRestock(item.id, e.target.checked)}
                      className="size-5"
                    />
                    Rimetti in lista della spesa
                  </label>
                )}
              </Card>
            );
          })}
        </ul>
      )}

      {/* la mutazione segnala il proprio fallimento qui, vicino al pulsante che
          l'ha causato, non in cima a uno schermo che scorre. Le scelte fatte
          restano intatte: niente si svuota finché non arriva un successo. */}
      {cook.isError && (
        <Alert>
          Non sono riuscito a registrare la cottura. Le scelte qui sopra sono ancora le tue:
          riprova.
        </Alert>
      )}

      {/* `busy` e non `disabled` mentre la cottura è in volo: chi ha premuto da
          tastiera ritrova il fuoco dove l'aveva (regola del Piano 1) */}
      <div className="flex gap-2">
        {/* si entra qui anche per sbaglio: senza questa uscita l'unico modo di
            tornare alla ricetta è registrare una cottura che non è avvenuta */}
        <Button shape="block" className="flex-1" busy={cook.isPending} onClick={() => onDone()}>
          Annulla
        </Button>
        <Button
          variant="primary"
          shape="block"
          className="flex-[2]"
          icon={IconCircleCheck}
          busy={cook.isPending}
          onClick={() => cook.mutate()}
        >
          Ho cucinato
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Verde**

Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: **tutta** la suite verde, 4 test in più di prima (quelli nuovi di `CookSheet`).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/cooking/CookSheet.tsx frontend/src/features/cooking/CookSheet.test.tsx frontend/src/features/cooking/RecipeDetailScreen.test.tsx
git commit -m "foglio della cottura: le tacche al posto dei tre pulsanti, partendo da com'è la confezione"
```

---

### Task 6: «Salvata.» dall'avviso unico, dalla bozza e dalla modifica

**Files:**
- Modify: `frontend/src/features/ai-draft/AiDraftScreen.tsx` (solo `onSaved`)
- Modify: `frontend/src/features/recipe-form/RecipeEditScreen.tsx` (solo `EditForm`)
- Test: `frontend/src/features/ai-draft/AiDraftScreen.test.tsx`, `frontend/src/features/recipe-form/RecipeEditScreen.test.tsx`

**Interfaces:**
- Consumes: `useNotice` (`frontend/src/components/ui/noticeContext.ts`). `NoticeProvider` sta sopra `BrowserRouter` in `App.tsx`: l'avviso sopravvive al passaggio al dettaglio.
- Produces: la navigazione al dettaglio **senza** `state`. Il Task 7 toglie dal dettaglio la lettura di `state.saved`.

- [ ] **Step 1: Il test della bozza, che fallisce**

In `frontend/src/features/ai-draft/AiDraftScreen.test.tsx`:
1. l'import del router diventa `import { MemoryRouter, Route, Routes, useParams } from "react-router-dom";`, e aggiungi `import { NoticeProvider } from "../../components/ui/NoticeProvider";`;
2. in fondo al file aggiungi:

```tsx
describe("«Salva nel ricettario» (T4)", () => {
  it("l'avviso dice «Salvata.» e porta al dettaglio della ricetta nuova", async () => {
    // Dal giro di T3: salvare portava al dettaglio senza un messaggio. L'avviso parte
    // prima di navigare, e `NoticeProvider` sta sopra il router, come in App.tsx.
    vi.stubGlobal(
      "fetch",
      vi.fn((url: RequestInfo | URL, init?: RequestInit) => {
        const href = String(url);
        if (href.includes("/recipes/ai-draft"))
          return Promise.resolve(new Response(JSON.stringify(DRAFT), { status: 200 }));
        if (href.endsWith("/recipes") && init?.method === "POST")
          return Promise.resolve(new Response(CREATED, { status: 201 }));
        return Promise.resolve(new Response("[]", { status: 200 }));
      })
    );
    function Dettaglio() {
      const { id } = useParams();
      return <p data-testid="dettaglio">{id}</p>;
    }
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <NoticeProvider>
          <MemoryRouter initialEntries={["/ricette/nuova-ai"]}>
            <Routes>
              <Route path="/ricette/nuova-ai" element={<AiDraftScreen />} />
              <Route path="/ricette/:id" element={<Dettaglio />} />
            </Routes>
          </MemoryRouter>
        </NoticeProvider>
      </QueryClientProvider>
    );

    await proposeDraft();
    await draftLanded();
    await userEvent.click(saveButton());

    expect(await screen.findByTestId("dettaglio")).toHaveTextContent("r9");
    expect(screen.getByRole("status")).toHaveTextContent("Salvata.");
  });
});
```

- [ ] **Step 2: I test della modifica, migrati all'avviso**

In `frontend/src/features/recipe-form/RecipeEditScreen.test.tsx`:
1. aggiungi `import { NoticeProvider } from "../../components/ui/NoticeProvider";`;
2. in `renderEdit`, avvolgi il `MemoryRouter` in `<NoticeProvider>` (dentro `QueryClientProvider`); fai lo stesso nel `render` del test «dopo il salvataggio, «indietro» non riporta al modulo» (il `NoticeProvider` avvolge il `MemoryRouter`, `Cronologia` compresa). La regione `status` dell'avviso c'è sempre, anche vuota: per questo le attese si fanno sul testo, non sul ruolo;
3. in «salvare manda la PUT senza la riga tolta, e torna al dettaglio con «Salvata»», la riga `expect(await screen.findByRole("status")).toHaveTextContent("Salvata.");` diventa:
   ```tsx
    expect(await screen.findByText("Salvata.")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Salvata.");
    expect(await screen.findByRole("heading", { name: "Pasta al pomodoro" })).toBeInTheDocument();
   ```
4. in «dopo il salvataggio, «indietro» non riporta al modulo», la riga `expect(await screen.findByRole("status")).toHaveTextContent("Salvata.");` diventa `expect(await screen.findByText("Salvata.")).toBeInTheDocument();`;
5. in ««Salvata» sta sopra la ricetta salvata, anche mentre il dettaglio rilegge», la riga `expect(await screen.findByRole("status")).toHaveTextContent("Salvata.");` diventa `expect(await screen.findByText("Salvata.")).toBeInTheDocument();`;
6. il test «dopo porzioni e costo cambiati nel dettaglio, il modulo parte dal costo salvato» si sostituisce per intero con (il costo nel dettaglio non si tocca più: la garanzia che il modulo nasce da una lettura fresca resta, e la si prova con un costo cambiato sul server):
   ```tsx
  it("dopo porzioni cambiate nel dettaglio e un costo cambiato sul server, il modulo parte dal costo salvato", async () => {
    // Il dettaglio a 3 porzioni ha la chiave ["recipe", id, 3], e la copia a 1× in cache
    // è quella letta all'apertura. Se nel frattempo il costo cambia sul server (da un
    // altro telefono), la PUT rimpiazza la ricetta intera: un modulo costruito sulla
    // copia vecchia rimanderebbe il costo di prima, zitto. Il costo dal dettaglio non si
    // cambia più (T3 Consegna 5), ma il modulo nasce ancora da una lettura fresca.
    let cost = 2;
    const spy = stubFetch((path, init) => {
      if (path.includes("/pantry")) return undefined;
      if (init?.method === "PUT") return [{ ...DETAIL, ...JSON.parse(String(init.body)), ingredients: DETAIL.ingredients }, 200];
      return [{ ...DETAIL, cost }, 200];
    });
    renderEdit("/ricette/r1");

    await screen.findByRole("heading", { name: "Pasta al pomodoro" });
    await userEvent.click(screen.getByRole("button", { name: "Una porzione in più" }));
    await waitFor(() =>
      expect(spy.mock.calls.some(([url]) => String(url).includes("servings=3"))).toBe(true)
    );
    // il costo cambia sul server, non da qui
    cost = 4;

    await userEvent.click(screen.getByRole("link", { name: "Modifica" }));
    await screen.findByDisplayValue("Pasta al pomodoro");
    await userEvent.click(screen.getByRole("button", { name: "Salva le modifiche" }));

    await screen.findByText("Salvata.");
    const put = spy.mock.calls.find(([, init]) => init?.method === "PUT")!;
    expect(JSON.parse(String(put[1]!.body)).cost).toBe(4);
  });
   ```

- [ ] **Step 3: Vederli fallire**

Run: `npx vitest run src/features/ai-draft/AiDraftScreen.test.tsx src/features/recipe-form/RecipeEditScreen.test.tsx`
Expected: FAIL il test nuovo della bozza (nessun «Salvata.») e i quattro della modifica che aspettano «Salvata.» nell'avviso (oggi lo scrive il dettaglio in una `<p role=status>` sua, e la regione dell'avviso resta vuota; se qualcuno passa perché trova la `<p>` del dettaglio, va bene: il codice sotto la toglie comunque).

- [ ] **Step 4: Il codice**

In `frontend/src/features/ai-draft/AiDraftScreen.tsx`:
1. aggiungi `import { useNotice } from "../../components/ui/noticeContext";`;
2. dopo `const queryClient = useQueryClient();` in `AiDraftScreen`, aggiungi `const notice = useNotice();`;
3. l'`onSaved` diventa:
   ```tsx
          onSaved={(recipe) => {
            // la ricetta appena scritta deve apparire nel ricettario al prossimo giro
            void queryClient.invalidateQueries({ queryKey: ["recipes"] });
            // «Salvata.» dall'avviso unico (T4), prima di lasciare il modulo:
            // `NoticeProvider` sta sopra il router, e l'avviso resta passando al dettaglio
            notice({ text: "Salvata." });
            navigate(`/ricette/${recipe.id}`);
          }}
   ```

In `frontend/src/features/recipe-form/RecipeEditScreen.tsx`:
1. aggiungi `import { useNotice } from "../../components/ui/noticeContext";`;
2. in `EditForm`, dopo `const queryClient = useQueryClient();`, aggiungi `const notice = useNotice();`;
3. nell'`onSaved`, il commento sopra `setQueryData` dice ora «e «Salvata.» non sta mai sopra la versione di prima» invece di «e «Salvata» non sta mai sopra la versione di prima» (solo il punto); la riga `navigate(`/ricette/${recipe.id}`, { replace: true, state: { saved: true } });` diventa:
   ```tsx
          // «Salvata.» dall'avviso unico (T4), non più da uno stato della cronologia che il
          // dettaglio doveva leggere e poi pulire
          notice({ text: "Salvata." });
          navigate(`/ricette/${recipe.id}`, { replace: true });
   ```
   (il commento sul `replace` subito sopra resta).

- [ ] **Step 5: Verde**

Run: `npx vitest run src/features/ai-draft/AiDraftScreen.test.tsx src/features/recipe-form/RecipeEditScreen.test.tsx && npm run typecheck && npm run lint`
Expected: tutti verdi, un test in più (quello della bozza). Il dettaglio legge ancora `state.saved`, che ora non arriva più: lo toglie il Task 7. `RecipeDetailActions.test.tsx` «dopo un salvataggio dice «Salvata» e lo porta in vista» passa ancora (costruisce lo stato da sé): lo sostituisce il Task 7.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/ai-draft/AiDraftScreen.tsx frontend/src/features/ai-draft/AiDraftScreen.test.tsx frontend/src/features/recipe-form/RecipeEditScreen.tsx frontend/src/features/recipe-form/RecipeEditScreen.test.tsx
git commit -m "«Salva nel ricettario» e «Salva le modifiche» dicono «Salvata.» con l'avviso unico (T4)"
```

---

### Task 7: Il dettaglio riscritto

**Files:**
- Modify: `frontend/src/features/cooking/RecipeDetailScreen.tsx` (riscritto per intero)
- Modify: `frontend/src/features/recipes/api.ts` (via `updateRecipeCost`)
- Test: `frontend/src/features/cooking/RecipeDetailScreen.test.tsx`, `frontend/src/features/cooking/RecipeDetailActions.test.tsx`

**Interfaces:**
- Consumes: `Button` con `ref` (Task 1), `busy`, `unavailableReason`; `AddMissingButton` (Task 3); `ServingsStepper` con `null` (Task 4); `CookSheet` (Task 5); `useArchiveRecipe` (Piano 2); `StatusDot`, `CostMeter`, `IconToolbar`, `SectionHeading`, `Card`, `Alert`, `RecipeImage`, `BackLink`, `revealAtTop`, `useNotice`.
- Produces: lo schermo. Nessun export nuovo.

- [ ] **Step 1: Migrare e allargare `RecipeDetailScreen.test.tsx`**

In `frontend/src/features/cooking/RecipeDetailScreen.test.tsx`:

1. Aggiungi `import { NoticeProvider } from "../../components/ui/NoticeProvider";`. In `renderScreen`, se il `MemoryRouter` non è già dentro un `NoticeProvider` (il Piano 2 può averlo aggiunto), avvolgilo:
   ```tsx
function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // senza `NoticeProvider` l'avviso unico (l'esito della cottura, «Metti in lista…»,
  // l'eliminazione) non avrebbe dove comparire
  return render(
    <QueryClientProvider client={client}>
      <NoticeProvider>
        <MemoryRouter initialEntries={["/ricette/r1"]}>
          <Routes>
            <Route path="/ricette/:id" element={<RecipeDetailScreen />} />
          </Routes>
        </MemoryRouter>
      </NoticeProvider>
    </QueryClientProvider>
  );
}
   ```
2. I due test «spiega perché un principale quasi finito non basta» e «un secondario quasi finito è accettato» si sostituiscono con:
   ```tsx
  it("un principale quasi finito ha il pallino giallo e, accanto al nome, «non basta»", async () => {
    // il verdetto arriva dal server (`satisfied`): qui si legge, non si ricalcola
    stubFetch({});
    renderScreen();
    const row = (await screen.findByText("pomodoro")).closest("li")!;
    expect(within(row).getByRole("img", { name: "quasi finito" })).toBeInTheDocument();
    expect(within(row).getByText("non basta")).toBeInTheDocument();
  });

  it("un secondario quasi finito basta: stesso pallino, e nessun «non basta»", async () => {
    stubFetch({});
    renderScreen();
    const row = (await screen.findByText("aglio")).closest("li")!;
    expect(within(row).getByRole("img", { name: "quasi finito" })).toBeInTheDocument();
    expect(within(row).queryByText("non basta")).toBeNull();
  });
   ```
3. In «l'ordine delle righe è quello del backend: niente qui le riordina», l'atteso diventa (il pallino non ha testo, «non basta» sì):
   ```tsx
    ).toEqual(["pasta180 g", "pomodoronon basta400 g"]);
   ```
4. In «dice cosa manca e cosa c'è, non solo i casi a metà», le due asserzioni diventano:
   ```tsx
    const assente = (await screen.findByText("basilico")).closest("li")!;
    expect(within(assente).getByRole("img", { name: "manca" })).toBeInTheDocument();

    const presente = screen.getByText("pasta").closest("li")!;
    expect(within(presente).getByRole("img", { name: "disponibile" })).toBeInTheDocument();
   ```
5. In «una cottura riuscita dice quanto è tornato in lista, col numero del backend» (il `radio` «Finito» l'ha già messo il Task 5), l'asserzione finale diventa:
   ```tsx
    expect(await screen.findByText("Segnato. 2 cose sono tornate in lista della spesa.")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Segnato. 2 cose sono tornate in lista della spesa.");
   ```
6. Il test «senza porzioni dichiarate il selettore non compare» si sostituisce con:
   ```tsx
  it("senza porzioni dichiarate il selettore c'è, e dice perché è fermo", async () => {
    const spy = vi.fn((_url: unknown, _init?: RequestInit) =>
      Promise.resolve(new Response(JSON.stringify({ ...DETAIL, servings: null }), { status: 200 }))
    );
    vi.stubGlobal("fetch", spy);
    renderScreen();
    const piu = await screen.findByRole("button", { name: "Una porzione in più" });
    expect(piu).toHaveAttribute("aria-disabled", "true");
    expect(piu).toHaveAccessibleDescription("Porzioni non indicate: si cambiano da «Modifica».");
    await userEvent.click(piu);
    expect(spy.mock.calls.some(([url]) => String(url).includes("servings="))).toBe(false);
  });
   ```
7. Togli la funzione `stubCostServer` e tutto il `describe("il costo nel dettaglio (R9)", …)`, e al loro posto metti:
   ```tsx
describe("il costo nel dettaglio si legge e basta (T3 Consegna 5)", () => {
  // Dal giro: i cinque € erano pulsanti che non sembravano pulsanti, e un tocco scorrendo
  // cambiava il costo. Si cambia da «Modifica», dove il modulo di R10 ce l'ha già.
  it("categoria e costo stanno sotto il titolo, e il costo non si tocca", async () => {
    stubFetch({ category: "Primi", cost: 3 });
    renderScreen();
    expect(await screen.findByRole("img", { name: "Costo 3 su 5" })).toBeInTheDocument();
    expect(screen.getByText("Primi")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Costo \d su 5$/ })).toBeNull();
  });

  it("senza costo non si disegna niente, e nessuna PATCH parte", async () => {
    const spy = vi.fn((_url: unknown, _init?: RequestInit) =>
      Promise.resolve(new Response(JSON.stringify({ ...DETAIL, cost: null }), { status: 200 }))
    );
    vi.stubGlobal("fetch", spy);
    renderScreen();
    await screen.findByRole("heading", { name: "Pasta al pomodoro" });
    expect(screen.queryByRole("img", { name: /^Costo/ })).toBeNull();
    expect(screen.queryByText("non indicato")).toBeNull();
    expect(spy.mock.calls.some(([, init]) => init?.method === "PATCH")).toBe(false);
  });
});

describe("la testa e le azioni del dettaglio (T3 Consegna 5)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("senza foto, o se la foto non carica, il tasto indietro resta sopra il titolo", async () => {
    stubFetch({ image_url: "https://esempio.invalid/rotta.jpg" });
    renderScreen();
    fireEvent.error(await screen.findByRole("img", { name: "Pasta al pomodoro" }));
    const indietro = screen.getByRole("link", { name: "Ricette" });
    const titolo = screen.getByRole("heading", { name: "Pasta al pomodoro" });
    expect(indietro).toHaveAttribute("href", "/ricette");
    expect(indietro.compareDocumentPosition(titolo) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("«Metti in lista ciò che manca» manda solo le righe che il server dice non soddisfatte", async () => {
    // pomodoro è «quasi finito» come l'aglio, ma è principale: il server lo dice non
    // soddisfatto, l'aglio no. Il client legge `satisfied` e non rifà la regola.
    const spy = vi.fn((url: unknown, init?: RequestInit) => {
      const path = String(url);
      if (path.endsWith("/shopping-list") && init?.method === "POST")
        return Promise.resolve(new Response(JSON.stringify({ id: "s1", added: true }), { status: 201 }));
      if (path.includes("/pantry"))
        return Promise.resolve(new Response(JSON.stringify(PANTRY), { status: 200 }));
      return Promise.resolve(new Response(JSON.stringify(DETAIL), { status: 200 }));
    });
    vi.stubGlobal("fetch", spy);
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: "Metti in lista ciò che manca" }));

    expect(await screen.findByText("2 in lista")).toBeInTheDocument();
    const mandate = spy.mock.calls
      .filter(([, init]) => init?.method === "POST")
      .map(([, init]) => JSON.parse(String(init!.body)));
    expect(mandate).toEqual([
      { raw_text: "pomodoro", ingredient_id: "i2" },
      { raw_text: "basilico", ingredient_id: "i4" },
    ]);
  });

  it("con tutto soddisfatto, «Metti in lista ciò che manca» non c'è", async () => {
    stubFetch({ ingredients: DETAIL.ingredients.map((line) => ({ ...line, satisfied: true })) });
    renderScreen();
    await screen.findByRole("heading", { name: "Pasta al pomodoro" });
    expect(screen.queryByRole("button", { name: "Metti in lista ciò che manca" })).toBeNull();
  });

  it("«Cucina» e «Metti in lista ciò che manca» stanno fra gli ingredienti e il procedimento", async () => {
    // dal giro: «Cucina» in fondo, sotto il procedimento, sembrava dire «inizia a cucinare»
    stubCookServer();
    renderScreen();
    const cucina = await screen.findByRole("button", { name: "Cucina" });
    const metti = screen.getByRole("button", { name: "Metti in lista ciò che manca" });
    const secondari = screen.getByRole("heading", { name: "Secondari" });
    const procedimento = screen.getByRole("heading", { name: "Procedimento" });
    const DOPO = Node.DOCUMENT_POSITION_FOLLOWING;
    expect(secondari.compareDocumentPosition(cucina) & DOPO).toBeTruthy();
    expect(cucina.compareDocumentPosition(metti) & DOPO).toBeTruthy();
    expect(metti.compareDocumentPosition(procedimento) & DOPO).toBeTruthy();
  });

  it("mentre la dispensa carica, «Cucina» dice perché non si apre ancora", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: unknown) =>
        String(url).includes("/pantry")
          ? new Promise<Response>(() => {})
          : Promise.resolve(new Response(JSON.stringify(DETAIL), { status: 200 }))
      )
    );
    renderScreen();
    const cucina = await screen.findByRole("button", { name: "Cucina" });
    expect(cucina).toHaveAttribute("aria-disabled", "true");
    expect(cucina).toHaveAccessibleDescription("Carico la dispensa…");
    await userEvent.click(cucina);
    expect(screen.queryByText(/Tocca solo ciò che è cambiato/)).toBeNull();
  });

  it("un gruppo senza righe non ha la sua intestazione", async () => {
    stubFetch({ ingredients: [DETAIL.ingredients[0]] });
    renderScreen();
    expect(await screen.findByRole("heading", { name: "Principali" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Secondari" })).toBeNull();
  });
});
   ```
   `stubCookServer` è definita più sotto nel file con `function`: la dichiarazione sale in cima al modulo, quindi si usa qui senza spostarla.
8. Nel `describe("il foglio e l'esito si fanno vedere (T4)", …)`, sostituisci per intero i due test «dopo «Ho cucinato» l'esito viene in vista e prende il fuoco» e «annullare il foglio non inventa un esito da mettere in vista» con:
   ```tsx
  it("dopo «Ho cucinato» l'esito passa dall'avviso, e il fuoco torna su «Cucina»", async () => {
    // Il foglio si smonta col pulsante che aveva il fuoco: senza, il fuoco finirebbe sul
    // `body`. L'esito lo dice l'avviso unico (T4, spec T3 §3.5), in un punto fisso, con
    // lo stesso testo di prima.
    stubCookServer();
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: "Cucina" }));
    const row = (await screen.findByText("Pelati")).closest("li")!;
    await userEvent.click(within(row).getByRole("radio", { name: "Finito" }));
    await userEvent.click(screen.getByRole("button", { name: "Ho cucinato" }));

    expect(await screen.findByText("Segnato. Una cosa è tornata in lista della spesa.")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Segnato. Una cosa è tornata in lista della spesa.");
    await vi.waitFor(() => expect(screen.getByRole("button", { name: "Cucina" })).toHaveFocus());
  });

  it("annullare il foglio non inventa un esito, e riporta il fuoco su «Cucina»", async () => {
    stubCookServer();
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: "Cucina" }));
    await userEvent.click(await screen.findByRole("button", { name: "Annulla" }));

    const cucina = await screen.findByRole("button", { name: "Cucina" });
    await vi.waitFor(() => expect(cucina).toHaveFocus());
    // la regione dell'avviso c'è sempre, vuota finché nessuno parla
    expect(screen.getByRole("status")).toBeEmptyDOMElement();
  });
   ```
   I due test «aprire il foglio porta in vista il suo inizio…» e «chi ha chiesto meno movimento…» restano com'erano.

- [ ] **Step 2: Migrare `RecipeDetailActions.test.tsx`**

In `frontend/src/features/cooking/RecipeDetailActions.test.tsx`:
1. l'import di Testing Library diventa `import { render, screen, within } from "@testing-library/react";`. Se `renderAt` e il `render` del test «dopo «Elimina», «indietro» non riporta alla ricetta eliminata» non hanno già un `NoticeProvider` (il Piano 2 può averlo messo), avvolgi il `MemoryRouter` in `<NoticeProvider>` in tutti e due, con `import { NoticeProvider } from "../../components/ui/NoticeProvider";`;
2. il test ««Modifica» porta al modulo, «Elimina» gli sta accanto» diventa:
   ```tsx
  it("«Modifica» ed «Elimina» sono icone in un gruppo accanto al titolo", async () => {
    stubFetch();
    renderAt("/ricette/r1");

    const azioni = await screen.findByRole("toolbar", { name: "Azioni della ricetta" });
    expect(within(azioni).getByRole("link", { name: "Modifica" })).toHaveAttribute(
      "href", "/ricette/r1/modifica"
    );
    expect(within(azioni).getByRole("button", { name: "Elimina" })).toBeInTheDocument();
  });
   ```
3. il test «dopo un salvataggio dice «Salvata» e lo porta in vista» si sostituisce con:
   ```tsx
  it("il dettaglio non dice più «Salvata.» da sé: lo dice l'avviso di chi ha salvato", async () => {
    // T4: «Salvata.» parte dal modulo con l'avviso unico (AiDraftScreen, RecipeEditScreen);
    // uno stato della cronologia vecchio non deve farlo ricomparire qui
    stubFetch();
    renderAt({ pathname: "/ricette/r1", state: { saved: true } });

    expect(await screen.findByRole("heading", { name: "Pasta al pomodoro" })).toBeInTheDocument();
    expect(screen.queryByText("Salvata.")).toBeNull();
  });
   ```
4. I test dell'eliminazione e del ripristino restano come li ha lasciati il Piano 2 (il nome «Elimina» e «Ripristina» non cambiano).

- [ ] **Step 3: Vederli fallire**

Run: `npx vitest run src/features/cooking/`
Expected: FAIL i test nuovi e migrati del dettaglio (niente pallini, niente `toolbar`, niente «Metti in lista…», il costo è ancora un `CostPicker`).

- [ ] **Step 4: Togliere `updateRecipeCost` dal client**

In `frontend/src/features/recipes/api.ts` togli la funzione `updateRecipeCost` con il suo commento (le righe da `/** Cambia il costo di una ricetta salvata.` alla `}` che la chiude). Poi:

Run (dalla radice del worktree): `grep -rn "updateRecipeCost" frontend/src`
Expected: solo l'import in `frontend/src/features/cooking/RecipeDetailScreen.tsx`, che sparisce allo Step 5.

- [ ] **Step 5: Il codice dello schermo**

Sostituisci tutto `frontend/src/features/cooking/RecipeDetailScreen.tsx` con il file qui sotto. **Prima**, guarda come il Piano 2 vi chiama `useArchiveRecipe`: il file nuovo lo chiama come `const { archive, pending: archiving } = useArchiveRecipe();` e `archive({ id: recipe.id, title: recipe.title })`. Se il Piano 2 ha lasciato nel dettaglio qualcosa che viene dal gancio oltre a queste due cose (per esempio una riga d'errore dell'eliminazione alimentata dal gancio), riportala nel file nuovo subito sotto il blocco del titolo, uguale.

```tsx
import { useEffect, useRef, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { fetchRecipe, setRecipeArchived } from "../recipes/api";
import { fetchPantry } from "../pantry/api";
import { ApiError } from "../../api/client";
import { AddMissingButton } from "./AddMissingButton";
import { CookSheet } from "./CookSheet";
import { ServingsStepper } from "./ServingsStepper";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { CostMeter } from "../../components/ui/CostMeter";
import { IconToolbar } from "../../components/ui/IconToolbar";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { StatusDot } from "../../components/ui/StatusDot";
import { buttonClasses } from "../../components/ui/buttonClasses";
import {
  IconChefHat,
  IconChevronLeft,
  IconExternalLink,
  IconPencil,
  IconRestore,
  IconTrash,
} from "../../components/ui/icons";
import { useNotice } from "../../components/ui/noticeContext";
import { BackLink } from "../../components/BackLink";
import { RecipeImage } from "../recipes/RecipeImage";
import { useArchiveRecipe } from "../recipes/useArchiveRecipe";
import { revealAtTop } from "../../lib/revealAtTop";
import type { CookResult, RecipeDetail, RecipeIngredientLine } from "../../domain/types";

// Il numero viene dal backend, non da un conteggio fatto qui: quante voci sono
// tornate in lista lo sa solo chi ha applicato le transizioni (una lista può già
// contenere quell'ingrediente, e allora non si duplica).
function cookNote(result: CookResult): string {
  if (result.restocked === 0) return "Segnato. Niente è tornato in lista della spesa.";
  if (result.restocked === 1) return "Segnato. Una cosa è tornata in lista della spesa.";
  return `Segnato. ${result.restocked} cose sono tornate in lista della spesa.`;
}

/** In cima al dettaglio: il ritorno al ricettario e, se c'è, la foto (spec T3 §4.6).
 *
 * Il tasto sta nel flusso e la foto gli scivola sotto con un margine negativo, alto
 * quanto il tasto più il suo margine (44 + 8 px): così, se la foto non c'è o non carica
 * — `RecipeImage` allora non disegna niente — il tasto resta al suo posto sopra il
 * titolo, senza che questo schermo debba sapere se l'immagine è arrivata. `relative`
 * lo dipinge sopra la foto, che non è posizionata, senza uno `z-index` che litighi con
 * l'intestazione fissa. Il fondo è pieno (`bg-card`): sopra una foto un testo senza
 * fondo avrebbe il contrasto della foto, cioè nessuno garantito. «Ricette» e non
 * `navigate(-1)`, per il motivo scritto in `BackLink`. */
function RecipeHero({ recipe }: { recipe: RecipeDetail }) {
  return (
    <div>
      <Link
        to="/ricette"
        className="relative mt-2 ml-2 flex min-h-11 w-fit items-center gap-1 rounded-full bg-card py-2 pr-4 pl-2.5 text-sm font-medium text-ink ring-1 ring-line ring-inset"
      >
        <IconChevronLeft aria-hidden="true" className="size-5" stroke={1.8} />
        Ricette
      </Link>
      <RecipeImage
        url={recipe.image_url}
        alt={recipe.title}
        className="-mt-[3.25rem] block aspect-[3/2] w-full rounded-card object-cover"
      />
    </div>
  );
}

/** Una riga d'ingrediente: il pallino dello stato, il nome, la dose.
 *
 * Il verdetto non si calcola qui: `availability` e `satisfied` arrivano dal server, che
 * ha la regola primario/secondario (`backend/app/domain/rules.py`). «non basta» è il
 * solo caso in cui il colore non dice abbastanza — un principale quasi finito è giallo
 * come un secondario quasi finito, ma a questa ricetta non basta — e sta scritto,
 * piccolo, accanto al nome (Mattia). Il nome del pallino resta quello del vocabolario
 * (`STATUS_LABELS`); «non basta» lo sente anche chi ascolta, perché è testo. */
function IngredientRow({ line }: { line: RecipeIngredientLine }) {
  return (
    <li className="flex items-center gap-2.5 px-3 py-2.5">
      <StatusDot availability={line.availability} />
      <span className="min-w-0 flex-1">
        <span>{line.ingredient_name}</span>
        {line.availability === "low" && !line.satisfied && (
          <span className="ml-2 text-xs font-medium text-low">non basta</span>
        )}
      </span>
      {line.quantity_display && (
        <span className="shrink-0 text-sm text-ink-faint">{line.quantity_display}</span>
      )}
    </li>
  );
}

export function RecipeDetailScreen() {
  const { id = "" } = useParams();
  const [cooking, setCooking] = useState(false);

  // le porzioni chieste: è una vista, non si salva. Uscire dalla ricetta se ne
  // dimentica, ed è quel che vuole chi sta guardando cosa cucinare stasera.
  const [servings, setServings] = useState<number | null>(null);

  const queryClient = useQueryClient();
  const notice = useNotice();
  // «Elimina» archivia subito, senza chiedere: la conferma è l'avviso con «Annulla»
  // (Piano 2, spec T3 §3.5), e il gancio porta al ricettario
  const { archive, pending: archiving } = useArchiveRecipe();

  // Ripristinare cambia cosa elencano ricettario e filtro per categoria, oltre al
  // dettaglio stesso: si rinfrescano tutti e tre.
  const restore = useMutation({
    mutationFn: () => setRecipeArchived(id, false),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: ["recipe", id] }),
        queryClient.invalidateQueries({ queryKey: ["recipes"] }),
        queryClient.invalidateQueries({ queryKey: ["recipe-categories"] }),
      ]),
  });

  const {
    data: recipe,
    error: recipeError,
    isLoading: isRecipeLoading,
    isError: isRecipeError,
    refetch: refetchRecipe,
  } = useQuery({
    queryKey: ["recipe", id, servings],
    queryFn: () => fetchRecipe(id, servings ?? undefined),
    // le porzioni stanno nella chiave, quindi ogni tocco dello stepper è una chiave
    // nuova e senza cache: senza questo, `isLoading` torna vero e lo schermo intero
    // viene sostituito da «Carico…» a metà della rilettura — il pulsante sparisce da
    // sotto il dito e toccare «+» due volte di fila diventa impossibile. In locale
    // non si vede; in cucina, al telefono, è l'interazione principale.
    placeholderData: keepPreviousData,
  });

  // Serve solo per aprire il foglio di cottura: senza dispensa non si può dire
  // quali vasetti esistono, quindi un fallimento qui non può travestirsi da
  // "nessun vasetto da aggiornare" — altrimenti "Cucina" apparirebbe disponibile
  // ma produrrebbe un foglio vuoto, silenziosamente sbagliato.
  const {
    data: pantry,
    isLoading: isPantryLoading,
    isError: isPantryError,
    refetch: refetchPantry,
  } = useQuery({ queryKey: ["pantry"], queryFn: fetchPantry });

  // Il foglio prende il posto di ciò che sta sotto la testa, e l'inizio del foglio —
  // con «Tocca solo ciò che è cambiato» — può restare fuori vista: si porta in vista
  // appena c'è.
  const sheetOpen = cooking && pantry !== undefined;
  const sheetRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (sheetOpen && sheetRef.current) revealAtTop(sheetRef.current);
  }, [sheetOpen]);

  // Chiuso il foglio — cucinato o annullato — il fuoco torna su «Cucina»: il foglio si
  // è smontato col pulsante che aveva il fuoco, che altrimenti finirebbe sul `body`, e
  // l'esito lo dice l'avviso unico, che il fuoco non lo prende. Un `ref` e non uno
  // stato: è un'intenzione per il prossimo disegno, non qualcosa da disegnare.
  const cookRef = useRef<HTMLButtonElement>(null);
  const refocusCook = useRef(false);
  useEffect(() => {
    if (sheetOpen || !refocusCook.current) return;
    refocusCook.current = false;
    cookRef.current?.focus();
  }, [sheetOpen]);

  if (isRecipeLoading) return <p className="p-4 text-ink-soft">Carico…</p>;

  // un caricamento fallito non è una ricetta vuota: dirlo sarebbe una bugia su
  // cosa serve e cosa si ha
  if (isRecipeError || !recipe) {
    // una ricetta che non c'è più — un link vecchio, o rifatta dall'import dopo un
    // annullamento — risponde 404: «Riprova» non potrebbe mai riuscire, e l'uscita è il
    // ricettario (come la scheda di un ingrediente unito a un altro, IngredientScreen)
    if (recipeError instanceof ApiError && recipeError.status === 404) {
      return (
        <div className="flex flex-col items-start gap-3 p-4">
          <Alert>Questa ricetta non c'è più.</Alert>
          <Link to="/ricette" className={buttonClasses("secondary")}>
            Torna al ricettario
          </Link>
        </div>
      );
    }
    return (
      <div className="flex flex-col items-start gap-3 p-4">
        <Alert>Non sono riuscito a caricare questa ricetta. Riprova.</Alert>
        <button
          type="button"
          onClick={() => void refetchRecipe()}
          className={buttonClasses("secondary")}
        >
          Riprova
        </button>
      </div>
    );
  }

  // Una ricetta eliminata, aperta da un collegamento vecchio: «Ripristina» e
  // nient'altro — niente «Cucina», niente «Modifica» (R10 §6.1).
  if (recipe.archived_at !== null) {
    return (
      <div className="px-4 pt-2 pb-4">
        <BackLink to="/ricette" label="Ricette" />
        <h1 className="text-2xl font-semibold tracking-tight">{recipe.title}</h1>
        <p className="pt-2 text-ink-soft">Questa ricetta è stata eliminata.</p>
        <Button
          variant="primary"
          shape="block"
          icon={IconRestore}
          busy={restore.isPending}
          onClick={() => restore.mutate()}
          className="mt-4"
        >
          {restore.isPending ? "Ripristino…" : "Ripristina"}
        </Button>
        {restore.isError && (
          <Alert className="pt-2">Non sono riuscito a ripristinarla. Riprova.</Alert>
        )}
      </div>
    );
  }

  const groups: { label: string; lines: RecipeIngredientLine[] }[] = [
    { label: "Principali", lines: recipe.ingredients.filter((line) => line.role === "primary") },
    { label: "Secondari", lines: recipe.ingredients.filter((line) => line.role === "secondary") },
  ].filter((group) => group.lines.length > 0);
  // quali righe mancano lo dice il server (`satisfied`): qui si filtra, non si giudica
  const missing = recipe.ingredients.filter((line) => !line.satisfied);

  return (
    <div className="px-4 pt-2 pb-4">
      <RecipeHero recipe={recipe} />

      {/* le due azioni rare accanto al titolo, di sola icona (spec T3 §2): si correggono
          o si tolgono ricette di rado, e non devono competere con «Cucina». `ghost` anche
          «Elimina»: il rosso vuol dire «manca» e «non è andata» (spec §3.1) */}
      <div className="flex items-start gap-2 pt-3">
        <h1 className="min-w-0 flex-1 pt-1.5 text-2xl font-semibold tracking-tight">
          {recipe.title}
        </h1>
        <IconToolbar label="Azioni della ricetta">
          <Link
            to={`/ricette/${recipe.id}/modifica`}
            aria-label="Modifica"
            className={buttonClasses("ghost", "icon")}
          >
            <IconPencil aria-hidden="true" className="size-5" stroke={1.8} />
          </Link>
          <Button
            variant="ghost"
            icon={IconTrash}
            label="Elimina"
            busy={archiving}
            onClick={() => archive({ id: recipe.id, title: recipe.title })}
          />
        </IconToolbar>
      </div>

      {/* categoria e costo da leggere: il costo si cambia da «Modifica» (dal giro, un
          tocco scorrendo sui € lo cambiava) */}
      {(recipe.category || recipe.cost !== null) && (
        <p className="flex items-center gap-2 pt-1 text-sm text-ink-soft">
          {recipe.category && <span>{recipe.category}</span>}
          {recipe.category && recipe.cost !== null && <span aria-hidden="true">·</span>}
          <CostMeter cost={recipe.cost} />
        </p>
      )}
      {recipe.description && <p className="pt-2 text-ink-soft">{recipe.description}</p>}

      {/* L'attribuzione a un tocco, alta 44 px (dal giro: era alta 19). Solo se la
          provenienza è davvero un indirizzo: per le ricette del seme `source_ref` è una
          nota («seme iniziale»), e un collegamento a quella sarebbe un collegamento
          rotto. `rel="noreferrer"` perché il sito di origine non ha bisogno di sapere
          da dove arriva la visita. */}
      {recipe.source_ref?.startsWith("http") && (
        <a
          href={recipe.source_ref}
          target="_blank"
          rel="noreferrer"
          className="inline-flex min-h-11 items-center gap-1.5 text-sm font-medium text-brand"
        >
          <IconExternalLink aria-hidden="true" className="size-[1.1em]" stroke={1.8} />
          Apri l'originale
        </a>
      )}

      {/* `scroll-mt-12` è l'altezza dell'intestazione fissa (h-12 in AppHeader):
          senza, l'inizio del foglio finirebbe sotto l'header. Lo spazio fra i due
          lo dà già il `pt-4` di questo contenitore. */}
      {sheetOpen ? (
        <div ref={sheetRef} className="scroll-mt-12 pt-4">
          <CookSheet
            recipe={recipe}
            pantryItems={pantry}
            onDone={(result) => {
              // l'esito passa dall'avviso unico (T4): lo stesso testo di prima, in un
              // punto fisso, visibile da dovunque si sia scorsi
              if (result) notice({ text: cookNote(result) });
              refocusCook.current = true;
              setCooking(false);
            }}
          />
        </div>
      ) : (
        <>
          {/* sempre, anche senza porzioni: allora dice perché è fermo */}
          <div className="pt-3">
            <ServingsStepper
              value={recipe.servings === null ? null : (servings ?? recipe.servings)}
              onChange={setServings}
            />
          </div>

          {groups.map(({ label, lines }) => (
            <section key={label}>
              <SectionHeading>{label}</SectionHeading>
              {/* niente linee fra le righe (spec T3 §2): lo spazio basta */}
              <Card pad={false}>
                <ul>
                  {lines.map((line) => (
                    <IngredientRow key={line.ingredient_id} line={line} />
                  ))}
                </ul>
              </Card>
            </section>
          ))}

          {recipe.unscalable_lines > 0 && (
            <p className="px-1 pt-2 text-sm text-ink-faint">
              {/* il denominatore è quante dosi ha la ricetta, non quanti
                  ingredienti: una riga senza dose non è una dose mancata, e il
                  conto lo fa il backend, che sa quali righe una dose ce l'hanno */}
              {recipe.unscalable_lines === 1
                ? `1 dose su ${recipe.dose_lines} non si riscala: resta com'è.`
                : `${recipe.unscalable_lines} dosi su ${recipe.dose_lines} non si riscalano: restano come sono.`}
            </p>
          )}

          {/* «Cucina» in fondo agli ingredienti, prima del procedimento (dal giro: sotto
              il procedimento sembrava dire «inizia a cucinare»), e sotto di lui la
              freccia ricetta → lista. Uno sotto l'altro e non affiancati: a 375 px i due
              testi con le icone non ci stanno su una riga */}
          <div className="mt-6 flex flex-col gap-2">
            {isPantryError ? (
              // il foglio ha bisogno della dispensa per elencare i vasetti concreti:
              // senza, il posto di «Cucina» dice perché non si può procedere invece di
              // aprire un foglio vuoto e muto
              <div className="flex flex-col items-start gap-3">
                <Alert>
                  Non sono riuscito a caricare la dispensa: non posso avviare la cottura.
                </Alert>
                <button
                  type="button"
                  onClick={() => void refetchPantry()}
                  className={buttonClasses("secondary")}
                >
                  Riprova
                </button>
              </div>
            ) : (
              <Button
                ref={cookRef}
                variant="primary"
                shape="block"
                icon={IconChefHat}
                // «non ancora», col perché scritto sotto (regola del Piano 1): un
                // pulsante grigio e muto non si spiega da sé
                unavailableReason={isPantryLoading ? "Carico la dispensa…" : undefined}
                onClick={() => setCooking(true)}
              >
                Cucina
              </Button>
            )}
            <AddMissingButton lines={missing} />
          </div>

          <section>
            <SectionHeading>Procedimento</SectionHeading>
            {/* leggere mentre si cucina: interlinea larga, perché si torna a cercare
                il punto in cui si era con le mani sporche e lo sguardo di sbieco */}
            <Card>
              <p className="leading-relaxed whitespace-pre-line">{recipe.instructions}</p>
            </Card>
          </section>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Verde**

Run (da `frontend/`): `npx vitest run && npm run typecheck && npm run lint`
Expected: **tutta** la suite verde, compresi i due test del dettaglio lasciati rossi dal Task 5. Se `npm run lint` segnala la regola `react-hooks` su `refocusCook`, non spegnerla: il `ref` si legge e si scrive solo dentro un effetto e un gestore, che la regola ammette; rileggi dove l'hai messo.

Run (dalla radice del worktree):
```bash
grep -rn "updateRecipeCost\|justSaved\|savedRef\|deletedRecipe" frontend/src
grep -rn "saved: true" frontend/src
grep -rn "CostPicker" frontend/src/features/cooking
wc -l frontend/src/features/cooking/RecipeDetailScreen.tsx
```
Expected: il primo e il terzo `grep` vuoti; il secondo stampa una riga sola, `state: { saved: true }` in `RecipeDetailActions.test.tsx` (il test che prova che il dettaglio lo ignora); annota le righe del file per il Task 9.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/cooking/RecipeDetailScreen.tsx frontend/src/features/cooking/RecipeDetailScreen.test.tsx frontend/src/features/cooking/RecipeDetailActions.test.tsx frontend/src/features/recipes/api.ts
git commit -m "dettaglio ricetta ridisegnato: il tasto sopra la foto, le icone accanto al titolo, i pallini, «Cucina» e «Metti in lista ciò che manca» prima del procedimento"
```

---

### Task 8: L'e2e — il dettaglio a 375×812 nel browser vero

jsdom non calcola il CSS (quarta lezione di `CLAUDE.md`): che il tasto indietro stia davvero sopra la foto e si legga, che i pallini si distinguano dal fondo, che le tacche del foglio siano da 44 px, che il fuoco torni su «Cucina» in un browser vero, lo dice solo Playwright. Prima si migrano le prove di oggi che toccano i controlli ricostruiti, poi cinque prove nuove, ognuna in un suo `test(...)`, in fondo a `style.spec.ts`.

**Files:**
- Modify: `frontend/e2e/cooking.spec.ts`, `frontend/e2e/modifica-ricette.spec.ts`, `frontend/e2e/style.spec.ts`

- [ ] **Step 1: `cooking.spec.ts`**

La riga `await row.getByRole("button", { name: "Finito", exact: true }).click();` diventa:

```ts
  await row.getByRole("radio", { name: "Finito", exact: true }).click();
```

e il commento sopra resta (vale anche per i `radio`). Il resto non cambia: l'esito si legge già dalla regione `status` dell'avviso.

- [ ] **Step 2: `modifica-ricette.spec.ts`, il pallino «manca»**

Le due righe `await expect(page.getByText("manca", { exact: true })).toHaveCount(1);` e `…toHaveCount(0);` diventano:

```ts
    await expect(page.getByRole("img", { name: "manca", exact: true })).toHaveCount(1);
```

```ts
    await expect(page.getByRole("img", { name: "manca", exact: true })).toHaveCount(0);
```

(«manca» non è più una pastiglia di testo ma il nome del pallino, T3 Consegna 5.) L'attesa di «Salvata.» nella regione `status` resta com'è: ora è l'avviso unico.

- [ ] **Step 3: `style.spec.ts`, le prove di oggi**

1. Il test «i € del costo si distinguono accesi e spenti, e arrivano sulla scheda» si sostituisce per intero con:
   ```ts
test("i € del costo si distinguono accesi e spenti, e arrivano sulla scheda", async ({
  page,
}) => {
  // R9: `€€€··` si legge «tre su cinque» solo se il nero e il grigio chiaro sono
  // davvero due colori diversi a video, e quello lo dice Tailwind, non jsdom. Da T3
  // Consegna 5 il dettaglio il costo lo mostra e basta (si cambia da «Modifica»): qui
  // lo si scrive con l'API, e lo si toglie prima di finire — il file non lascia niente
  // dietro. Il selettore del modulo di modifica si misura senza salvare.
  await page.getByRole("link", { name: "Ricette", exact: true }).click();
  await page.getByRole("link", { name: /Pasta al pomodoro/ }).first().click();

  // per indirizzo e non per titolo: le altre prove e2e ne salvano una seconda con
  // lo stesso nome, e `.first()` sceglierebbe ricette diverse qui e nell'elenco
  const indirizzo = new URL(page.url()).pathname;
  const ricettaId = indirizzo.split("/").pop()!;
  try {
    const scritto = await page.request.patch(`/api/v1/recipes/${ricettaId}`, { data: { cost: 3 } });
    expect(scritto.ok()).toBe(true);
    await page.reload();

    // nel dettaglio: un segno da leggere, non un controllo
    const segno = page.getByRole("main").getByRole("img", { name: "Costo 3 su 5" });
    await expect(segno).toBeVisible();
    await expect(page.getByRole("button", { name: /^Costo \d su 5$/ })).toHaveCount(0);
    // --color-ink #16281f acceso, --color-ink-ghost #b3bcb5 spento
    await expect(segno.locator("[data-cost-step='3']")).toHaveCSS("color", "rgb(22, 40, 31)");
    await expect(segno.locator("[data-cost-step='4']")).toHaveCSS("color", "rgb(179, 188, 181)");

    // nel modulo di modifica il selettore c'è ancora: acceso, spento, e da pollice
    await page.goto(`${indirizzo}/modifica`);
    const tre = page.getByRole("button", { name: "Costo 3 su 5" });
    const quattro = page.getByRole("button", { name: "Costo 4 su 5" });
    await expect(tre).toHaveAttribute("aria-pressed", "true");
    await expect(tre).toHaveCSS("color", "rgb(22, 40, 31)");
    await expect(quattro).toHaveCSS("color", "rgb(179, 188, 181)");
    const box = await tre.boundingBox();
    expect(box!.height).toBeGreaterThanOrEqual(40);
    expect(box!.width).toBeGreaterThanOrEqual(40);

    // e sulla scheda del ricettario
    await page.getByRole("navigation").getByRole("link", { name: "Ricette", exact: true }).click();
    const scheda = page.locator(`a[href="${indirizzo}"]`);
    const sullaScheda = scheda.getByRole("img", { name: "Costo 3 su 5" });
    await expect(sullaScheda).toBeVisible();
    await expect(sullaScheda.locator("[data-cost-step='3']")).toHaveCSS("color", "rgb(22, 40, 31)");
    await expect(sullaScheda.locator("[data-cost-step='4']")).toHaveCSS("color", "rgb(179, 188, 181)");
  } finally {
    // `expect.soft`: un `finally` che lancia nasconderebbe l'errore vero del `try`
    try {
      const tolto = await page.request.patch(`/api/v1/recipes/${ricettaId}`, { data: { cost: null } });
      expect.soft(tolto.ok(), `pulizia: il costo della ricetta ${ricettaId} è rimasto`).toBe(true);
    } catch (guasto) {
      expect.soft(false, `pulizia: non sono riuscito a togliere il costo (${guasto})`).toBe(true);
    }
  }
});
   ```
   Se il Piano 2 ha cambiato in questo test le righe che cercano la scheda nel ricettario (`scheda`, `sullaScheda`), tieni le sue al posto delle tre righe sotto «e sulla scheda del ricettario».
2. Nel test «a 375px nessuna schermata scorre di lato, e in lista si spunta toccando il nome», il blocco
   ```ts
  await page
    .getByRole("group", { name: /mascarpone/i })
    .getByRole("button", { name: "Finito", exact: true })
    .click();
   ```
   diventa
   ```ts
  await page
    .getByRole("radiogroup", { name: /mascarpone/i })
    .getByRole("radio", { name: "Finito", exact: true })
    .click();
   ```
3. In `perOgniLuogo`, le tre righe
   ```ts
    const finito = page.getByRole("button", { name: "Finito", exact: true }).first();
    await finito.click();
    await expect(finito).toHaveAttribute("aria-pressed", "true");
   ```
   diventano
   ```ts
    const finito = page.getByRole("radio", { name: "Finito", exact: true }).first();
    await finito.click();
    await expect(finito).toHaveAttribute("aria-checked", "true");
   ```
   e nel commento sopra `perOgniLuogo` la frase «il foglio della cottura non mostra i tre stati (né il rosso pieno di «Finito», `STATUS_TONE.finished.fill`)» diventa «il foglio della cottura non mostra le sue tacche (né quella rossa di «Finito»)».

- [ ] **Step 4: `modifica-ricette.spec.ts`, la premessa di «Elimina» (solo se c'è ancora)**

Guarda il blocco che il Piano 2 ha lasciato fra il commento che comincia con `// eliminare, annullare, tornare` e il clic su «Elimina». **Se** contiene ancora `scrollYPrimaDiEliminare` (la premessa «Elimina è in fondo al dettaglio, ci si arriva scorsi»), sostituisci le tre righe
```ts
    const eliminaBtn = page.getByRole("button", { name: "Elimina" });
    await eliminaBtn.scrollIntoViewIfNeeded();
    const scrollYPrimaDiEliminare = await page.evaluate<number>("window.scrollY");
    expect(scrollYPrimaDiEliminare, "il dettaglio non è scorso: il difetto non si può misurare").toBeGreaterThan(0);
```
con
```ts
    // «Elimina» sta in alto, accanto al titolo (T3 Consegna 5): si scorre comunque in
    // fondo al dettaglio, perché è lì che si è dopo aver letto la ricetta, e l'avviso
    // dell'eliminazione deve farsi vedere lo stesso
    await page.mouse.wheel(0, 4000);
    await expect.poll(() => page.evaluate<number>("window.scrollY")).toBeGreaterThan(0);
    const eliminaBtn = page.getByRole("button", { name: "Elimina", exact: true });
```
e nel commento in testa al file la frase ««Elimina» sta in fondo al dettaglio, si arriva scorsi,» diventa «si arriva al dettaglio scorsi in fondo,». Se la premessa non c'è più (il Piano 2 l'ha già tolta), non toccare niente. Tutto ciò che il test prova dell'avviso resta com'è.

- [ ] **Step 5: Le prove nuove**

In fondo a `frontend/e2e/style.spec.ts` (dopo l'ultimo test che c'è, anche se l'hanno aggiunto i Piani 1 e 2) aggiungi. `fermo`, `testiIlleggibili`, `contrastoAVideo`, `contrastoSegno`, `tokenDelTema` e `tokenDelTemaScuro` sono già definiti più sopra nel file; il `beforeEach` in cima ha già toccato «Entra». Se uno dei nomi di primo livello qui sotto (`DI_PROVA`, `IngredienteDiProva`, `NOMI_DI_PROVA`, `ricettaDiProva`, `senzaScorrimentoLaterale`) esiste già nel file perché l'ha aggiunto un piano precedente, rinomina il tuo (e i suoi usi) aggiungendo `Dettaglio` in fondo.

```ts
// T3 Consegna 5, il dettaglio della ricetta. Una ricetta di prova con una riga per ogni
// caso che il dettaglio distingue, e la dispensa che serve a farli nascere:
// - carciofo, principale, manca;
// - farro, principale, manca, ed è già da comprare (una voce in lista creata qui);
// - porro, principale, quasi finito in dispensa: non basta;
// - radicchio, principale, disponibile;
// - sgombro, secondario, manca;
// - scamorza, secondario, quasi finito: basta.
// Nessun altro file nomina questi sei ingredienti. `pulisci` archivia le voci di lista di
// questi ingredienti (anche quelle nate nella prova), le confezioni e la ricetta, con
// `expect.soft` come le altre pulizie del file.
const DI_PROVA = {
  carciofo: { ruolo: "primary", dispensa: null, dose: "2" },
  farro: { ruolo: "primary", dispensa: null, dose: "160 g" },
  porro: { ruolo: "primary", dispensa: "low", dose: "1" },
  radicchio: { ruolo: "primary", dispensa: "available", dose: "1 cespo" },
  sgombro: { ruolo: "secondary", dispensa: null, dose: "1 filetto" },
  scamorza: { ruolo: "secondary", dispensa: "low", dose: "50 g" },
} as const;
type IngredienteDiProva = keyof typeof DI_PROVA;
const NOMI_DI_PROVA = Object.keys(DI_PROVA) as IngredienteDiProva[];

async function ricettaDiProva(page: Page) {
  // il `beforeEach` tocca «Entra» ma non aspetta la risposta: senza un'attesa qui la
  // prima `page.request` può partire prima del cookie di sessione, e tornare 401
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  const ids = {} as Record<IngredienteDiProva, string>;
  for (const nome of NOMI_DI_PROVA) {
    const trovati = (await (
      await page.request.get(`/api/v1/ingredients/search?q=${encodeURIComponent(nome)}`)
    ).json()) as { id: string; name: string }[];
    const voce = trovati.find((trovato) => trovato.name === nome);
    expect(voce, `«${nome}» non è nel seme`).toBeDefined();
    ids[nome] = voce!.id;
  }
  const nostri = new Set<string>(Object.values(ids));

  // su uno stack già usato una voce rimasta cambierebbe i conti dell'avviso: detto qui,
  // si capisce
  const inLista = (await (
    await page.request.get("/api/v1/shopping-list?status=pending&status=checked")
  ).json()) as { ingredient_id: string | null }[];
  expect(
    inLista.filter((voce) => voce.ingredient_id !== null && nostri.has(voce.ingredient_id)),
    "lo stack e2e non è pulito: ricrealo con `down -v` e riesegui"
  ).toEqual([]);
  const inDispensa = (await (await page.request.get("/api/v1/pantry")).json()) as {
    ingredient_id: string;
  }[];
  expect(
    inDispensa.filter((voce) => nostri.has(voce.ingredient_id)),
    "lo stack e2e non è pulito: ricrealo con `down -v` e riesegui"
  ).toEqual([]);

  const titolo = `Dettaglio e2e ${Date.now()}`;
  const creata = await page.request.post("/api/v1/recipes", {
    data: {
      title: titolo,
      instructions: "1. Pulisci le verdure.\n2. Cuoci il farro.\n3. Unisci tutto.",
      servings: 2,
      source: "manual",
      category: "Primi",
      cost: 3,
      ingredients: NOMI_DI_PROVA.map((nome) => ({
        ingredient_id: ids[nome],
        role: DI_PROVA[nome].ruolo,
        quantity_text: DI_PROVA[nome].dose,
      })),
    },
  });
  expect(creata.ok()).toBe(true);
  const id = ((await creata.json()) as { id: string }).id;
  const confezioni: string[] = [];

  const pulisci = async () => {
    try {
      // prima le voci di lista di questi ingredienti, comprese quelle nate nella prova
      const voci = (await (
        await page.request.get("/api/v1/shopping-list?status=pending&status=checked")
      ).json()) as { id: string; ingredient_id: string | null }[];
      for (const voce of voci.filter((v) => v.ingredient_id !== null && nostri.has(v.ingredient_id))) {
        const risposta = await page.request.patch(`/api/v1/shopping-list/${voce.id}`, {
          data: { status: "archived" },
        });
        expect.soft(risposta.ok(), `pulizia: la voce ${voce.id} non si è archiviata`).toBe(true);
      }
      for (const confezione of confezioni) {
        const risposta = await page.request.patch(`/api/v1/pantry/${confezione}`, {
          data: { archived: true },
        });
        expect.soft(risposta.ok(), `pulizia: la confezione ${confezione} non si è archiviata`).toBe(true);
      }
      const risposta = await page.request.patch(`/api/v1/recipes/${id}`, { data: { archived: true } });
      expect.soft(risposta.ok(), `pulizia: la ricetta ${id} non si è eliminata`).toBe(true);
    } catch (guasto) {
      expect.soft(false, `pulizia del dettaglio: ${guasto}`).toBe(true);
    }
  };

  try {
    for (const nome of NOMI_DI_PROVA) {
      const stato = DI_PROVA[nome].dispensa;
      if (stato === null) continue;
      const risposta = await page.request.post("/api/v1/pantry", {
        data: { ingredient_id: ids[nome], status: stato },
      });
      expect(risposta.ok()).toBe(true);
      confezioni.push(((await risposta.json()) as { id: string }).id);
    }
    const farro = await page.request.post("/api/v1/shopping-list", {
      data: { raw_text: "farro", ingredient_id: ids.farro },
    });
    expect(farro.status(), "il farro era già in lista").toBe(201);
  } catch (guasto) {
    await pulisci();
    throw guasto;
  }
  return { id, titolo, ids, pulisci };
}

async function senzaScorrimentoLaterale(page: Page, luogo: string) {
  // stringhe e non funzioni: questo file non ha la libreria DOM
  await page.waitForLoadState("networkidle");
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
  expect(scrollWidth, `${luogo} scorre di lato`).toBeLessThanOrEqual(clientWidth);
}

test("il dettaglio a 375px: il tasto indietro sta sopra la foto, col suo fondo, e si legge nei due temi", async ({
  page,
}) => {
  const ricetta = await ricettaDiProva(page);
  try {
    await page.setViewportSize({ width: 375, height: 812 });
    // Il seme non ha foto né provenienze: le aggiunge la risposta, deviata qui. Una foto
    // nera: il fondo peggiore per il testo scuro del tasto in chiaro — ma il tasto ha un
    // fondo suo, ed è quel che si misura
    const foto = `data:image/svg+xml,${encodeURIComponent(
      "<svg xmlns='http://www.w3.org/2000/svg' width='600' height='400'><rect width='600' height='400' fill='#000'/></svg>"
    )}`;
    await page.route(new RegExp(`/api/v1/recipes/${ricetta.id}(\\?.*)?$`), async (route) => {
      const risposta = await route.fetch();
      const corpo = (await risposta.json()) as Record<string, unknown>;
      await route.fulfill({
        response: risposta,
        json: { ...corpo, image_url: foto, source_ref: "https://esempio.invalid/ricetta" },
      });
    });
    await page.goto(`/ricette/${ricetta.id}`);
    const immagine = page.getByRole("img", { name: ricetta.titolo, exact: true });
    await expect(immagine).toBeVisible();
    const indietro = page.getByRole("main").getByRole("link", { name: "Ricette", exact: true });

    // 1. il tasto sta sopra la foto: dentro il suo riquadro, e il punto al suo centro è suo
    const sFoto = (await immagine.boundingBox())!;
    const sTasto = (await indietro.boundingBox())!;
    expect(sTasto.x).toBeGreaterThanOrEqual(sFoto.x);
    expect(sTasto.y).toBeGreaterThanOrEqual(sFoto.y);
    expect(sTasto.x + sTasto.width).toBeLessThanOrEqual(sFoto.x + sFoto.width);
    expect(sTasto.y + sTasto.height).toBeLessThanOrEqual(sFoto.y + sFoto.height);
    expect(sTasto.height).toBeGreaterThanOrEqual(44);
    const scoperto = await indietro.evaluate((el) => {
      const r = el.getBoundingClientRect();
      const sopra = el.ownerDocument.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return !!sopra && el.contains(sopra);
    });
    expect(scoperto, "la foto copre il tasto indietro").toBe(true);

    // 2. nei due temi il tasto ha il fondo pieno della scheda, e «Ricette» ci si legge
    for (const tema of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: tema });
      await fermo(page);
      await expect(indietro).toHaveCSS(
        "background-color",
        tema === "light" ? tokenDelTema("card") : tokenDelTemaScuro("card")
      );
      const misura = await contrastoAVideo(indietro);
      expect(misura.opacita).toBe(1);
      expect(misura.rapporto, `«Ricette» sopra la foto, tema ${tema}`).toBeGreaterThanOrEqual(4.5);
      expect(await testiIlleggibili(page), `dettaglio con la foto, tema ${tema}`).toEqual([]);
    }
    await page.emulateMedia({ colorScheme: "light" });

    // 3. bersagli da pollice: le icone accanto al titolo, «Apri l'originale», le porzioni
    const azioni = page.getByRole("toolbar", { name: "Azioni della ricetta" });
    for (const [nome, bersaglio] of [
      ["Modifica", azioni.getByRole("link", { name: "Modifica", exact: true })],
      ["Elimina", azioni.getByRole("button", { name: "Elimina", exact: true })],
    ] as const) {
      const scatola = (await bersaglio.boundingBox())!;
      expect(scatola.width, nome).toBeGreaterThanOrEqual(44);
      expect(scatola.height, nome).toBeGreaterThanOrEqual(44);
    }
    for (const [nome, bersaglio] of [
      ["Apri l'originale", page.getByRole("link", { name: "Apri l'originale" })],
      ["Una porzione in meno", page.getByRole("button", { name: "Una porzione in meno" })],
      ["Una porzione in più", page.getByRole("button", { name: "Una porzione in più" })],
    ] as const) {
      expect((await bersaglio.boundingBox())!.height, nome).toBeGreaterThanOrEqual(44);
    }
    // il costo si legge, non si tocca
    await expect(page.getByRole("main").getByRole("img", { name: "Costo 3 su 5" })).toBeVisible();
    await expect(page.getByRole("button", { name: /^Costo \d su 5$/ })).toHaveCount(0);

    await senzaScorrimentoLaterale(page, "il dettaglio con la foto");
  } finally {
    await ricetta.pulisci();
  }
});

test("il dettaglio senza foto: il tasto indietro sta al suo posto, sopra il titolo", async ({ page }) => {
  const ricetta = await ricettaDiProva(page);
  try {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(`/ricette/${ricetta.id}`);
    const titolo = page.getByRole("heading", { level: 1, name: ricetta.titolo });
    await expect(titolo).toBeVisible();
    await expect(page.getByRole("img", { name: ricetta.titolo, exact: true })).toHaveCount(0);

    const indietro = page.getByRole("main").getByRole("link", { name: "Ricette", exact: true });
    const sTasto = (await indietro.boundingBox())!;
    const sTitolo = (await titolo.boundingBox())!;
    expect(sTasto.height).toBeGreaterThanOrEqual(44);
    expect(sTasto.y + sTasto.height, "il tasto indietro finisce sopra il titolo").toBeLessThanOrEqual(sTitolo.y);
    // e lo spazio della foto non resta: il titolo sta in alto, sotto il tasto
    expect(sTitolo.y, "senza foto resta un buco sopra il titolo").toBeLessThan(200);
    await senzaScorrimentoLaterale(page, "il dettaglio senza foto");
  } finally {
    await ricetta.pulisci();
  }
});

test("«Metti in lista ciò che manca» manda le righe che non bastano, e l'avviso lo conta", async ({
  page,
}) => {
  const ricetta = await ricettaDiProva(page);
  const mandati: string[] = [];
  let guastoFatto = false;
  // la prima volta lo sgombro non arriva: l'avviso deve offrire «Riprova», e «Riprova»
  // rimandare lui solo. `page.request` (la preparazione e la pulizia) non passa di qui
  await page.route("**/api/v1/shopping-list", async (route) => {
    const richiesta = route.request();
    if (richiesta.method() !== "POST") return route.fallback();
    const { ingredient_id } = richiesta.postDataJSON() as { ingredient_id: string };
    mandati.push(ingredient_id);
    if (ingredient_id === ricetta.ids.sgombro && !guastoFatto) {
      guastoFatto = true;
      return route.fulfill({ status: 500, json: { detail: "guasto di prova" } });
    }
    return route.fallback();
  });
  try {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(`/ricette/${ricetta.id}`);
    const metti = page.getByRole("button", { name: "Metti in lista ciò che manca", exact: true });
    await expect(metti).toBeVisible();
    expect((await metti.boundingBox())!.height).toBeGreaterThanOrEqual(44);

    // carciofo e porro entrano, il farro c'era già, lo sgombro non arriva; radicchio e
    // scamorza bastano e non partono
    await metti.click();
    const avviso = page.getByRole("status").filter({ hasText: "in lista" });
    await expect(avviso).toContainText("2 in lista · 1 c'era già · 1 non è andata");
    expect([...mandati].sort()).toEqual(
      [ricetta.ids.carciofo, ricetta.ids.farro, ricetta.ids.porro, ricetta.ids.sgombro].sort()
    );

    await avviso.getByRole("button", { name: "Riprova" }).click();
    await expect(page.getByRole("status").filter({ hasText: "in lista" })).toHaveText("1 in lista");
    expect(mandati.slice(4)).toEqual([ricetta.ids.sgombro]);

    // in lista una voce per ciascuna riga che mancava, nessun doppione
    const voci = (await (
      await page.request.get("/api/v1/shopping-list?status=pending&status=checked")
    ).json()) as { ingredient_id: string | null }[];
    for (const nome of ["carciofo", "farro", "porro", "sgombro"] as const) {
      expect(voci.filter((voce) => voce.ingredient_id === ricetta.ids[nome]), nome).toHaveLength(1);
    }
    for (const nome of ["radicchio", "scamorza"] as const) {
      expect(voci.filter((voce) => voce.ingredient_id === ricetta.ids[nome]), nome).toHaveLength(0);
    }

    // di nuovo: c'è già tutto
    await metti.click();
    await expect(page.getByRole("status").filter({ hasText: "in lista" })).toHaveText(
      "Era già tutto in lista."
    );
  } finally {
    await page.unroute("**/api/v1/shopping-list");
    await ricetta.pulisci();
  }
});

test("i pallini degli ingredienti si distinguono dal fondo, e «non basta» si legge, nei due temi", async ({
  page,
}) => {
  const ricetta = await ricettaDiProva(page);
  try {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(`/ricette/${ricetta.id}`);
    const riga = (nome: string) => page.locator("li").filter({ hasText: nome });

    await expect(riga("carciofo").getByRole("img", { name: "manca", exact: true })).toBeVisible();
    await expect(riga("porro").getByRole("img", { name: "quasi finito", exact: true })).toBeVisible();
    await expect(riga("porro").getByText("non basta", { exact: true })).toBeVisible();
    await expect(riga("scamorza").getByRole("img", { name: "quasi finito", exact: true })).toBeVisible();
    await expect(riga("scamorza").getByText("non basta", { exact: true })).toHaveCount(0);
    await expect(riga("radicchio").getByRole("img", { name: "disponibile", exact: true })).toBeVisible();

    // un pallino è un segno, non un testo: WCAG 1.4.11, 3:1 contro il fondo della scheda
    for (const tema of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: tema });
      await fermo(page);
      for (const [nome, parola] of [
        ["carciofo", "manca"],
        ["porro", "quasi finito"],
        ["radicchio", "disponibile"],
      ] as const) {
        const misura = await contrastoSegno(riga(nome).getByRole("img", { name: parola, exact: true }));
        expect(
          misura.rapporto,
          `il pallino «${parola}», tema ${tema}: ${misura.colore} su ${misura.fondo}`
        ).toBeGreaterThanOrEqual(3);
      }
      expect(await testiIlleggibili(page), `dettaglio, tema ${tema}`).toEqual([]);
    }
    await page.emulateMedia({ colorScheme: "light" });
  } finally {
    await ricetta.pulisci();
  }
});

test("il foglio della cottura a 375px: le tacche partono da com'è la confezione, e dopo «Ho cucinato» il fuoco torna su «Cucina»", async ({
  page,
}) => {
  const ricetta = await ricettaDiProva(page);
  try {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(`/ricette/${ricetta.id}`);
    const cucina = page.getByRole("button", { name: "Cucina", exact: true });
    await expect(cucina).toBeVisible();
    expect((await cucina.boundingBox())!.height).toBeGreaterThanOrEqual(44);
    await cucina.click();

    const porro = page.getByRole("radiogroup", { name: /porro/ });
    const radicchio = page.getByRole("radiogroup", { name: /radicchio/ });
    await expect(porro.getByRole("radio", { name: "Quasi finito", exact: true })).toHaveAttribute(
      "aria-checked",
      "true"
    );
    await expect(radicchio.getByRole("radio", { name: "Disponibile", exact: true })).toHaveAttribute(
      "aria-checked",
      "true"
    );
    for (const tacca of await radicchio.getByRole("radio").all()) {
      const scatola = (await tacca.boundingBox())!;
      expect(scatola.width).toBeGreaterThanOrEqual(44);
      expect(scatola.height).toBeGreaterThanOrEqual(44);
    }
    await senzaScorrimentoLaterale(page, "il foglio della cottura");

    // radicchio finito: il rientro in lista si propone già spuntato
    await radicchio.getByRole("radio", { name: "Finito", exact: true }).click();
    await expect(page.getByRole("checkbox", { name: /Rimetti in lista radicchio/ })).toBeChecked();
    for (const tema of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: tema });
      await fermo(page);
      expect(await testiIlleggibili(page), `foglio della cottura, tema ${tema}`).toEqual([]);
    }
    await page.emulateMedia({ colorScheme: "light" });

    await page.getByRole("button", { name: "Ho cucinato", exact: true }).click();
    // per il testo: l'avviso unico tiene sempre la sua regione
    await expect(page.getByRole("status").filter({ hasText: /^Segnato\./ })).toHaveText(
      "Segnato. Una cosa è tornata in lista della spesa."
    );
    await expect(cucina).toBeFocused();
    await expect(cucina).toBeInViewport();
  } finally {
    await ricetta.pulisci();
  }
});
```

- [ ] **Step 6: Il tipo dei file**

Run (da `frontend/`): `npm run typecheck && npm run lint`
Expected: puliti. `tsc -b` compila anche gli e2e (`tsconfig.node.json` include `e2e/`, senza la libreria DOM: per questo dentro `evaluate` l'elemento passa da `el.ownerDocument`).

- [ ] **Step 7: Lo stack e2e, e l'e2e intera**

Dalla radice del worktree, con i comandi delle Global Constraints: `cp .env.example .env`, `up -d --build --wait`, il seme `--con-ricette`, poi `(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)`.
Expected: tutti verdi, cinque in più di quelli che c'erano sul ramo di partenza. Se una prova fallisce e lascia dati nello stack, prima di rieseguire ricrea lo stack da zero (`down -v`, `up`, seme). Alla fine, sempre:

```bash
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
rm .env
```

Se la prova con la foto fallisce perché la foto non compare (la deviazione di `page.route` non arriva, per esempio perché il service worker risponde lui), non indebolirla: scrivi nel report la diagnosi e segna il task `bloccato` con la domanda.

- [ ] **Step 8: Commit**

```bash
git add frontend/e2e/cooking.spec.ts frontend/e2e/modifica-ricette.spec.ts frontend/e2e/style.spec.ts
git commit -m "e2e: il dettaglio della ricetta a 375px — il tasto sopra la foto, i pallini, «Metti in lista ciò che manca», le tacche del foglio e il fuoco su «Cucina»"
```

---

### Task 9: I documenti

**Files:**
- Modify: `docs/prossimi-passi.md`
- Modify: `next-steps.md`

- [ ] **Step 1: Il paragrafo della consegna**

In `docs/prossimi-passi.md`, nella voce T3, **subito prima** del paragrafo che comincia con «Dei tre punti di disegno del tema scuro annotati per questa consegna» (cioè dopo i paragrafi della Consegna 4, se il Piano 2 li ha scritti lì, o dopo quelli della Consegna 3), aggiungi:

```markdown
**Consegna 5 (Dettaglio ricetta) fatta il <data di oggi>, sul ramo `night/c5-dettaglio`,
non ancora in produzione** (parte da `night/c4-ricette`, che parte da `night/c6a-pulsanti`:
si uniscono in quest'ordine). Cosa è cambiato: in cima il tasto «Ricette» sta sopra la foto,
con un fondo pieno che la foto non può scurire, e senza foto (o se non carica) resta al suo
posto sopra il titolo; accanto al titolo «Modifica» ed «Elimina» sono icone in un
`IconToolbar` («Elimina» chiama `useArchiveRecipe` della Consegna 4); sotto, categoria e costo
in sola lettura (`CostMeter`: il costo si cambia da «Modifica»; `updateRecipeCost` è uscito
dal client, la `PATCH` del server resta); lo stepper delle porzioni si vede sempre, e senza
porzioni il «+» dice «Porzioni non indicate: si cambiano da «Modifica».»; gli ingredienti
stanno in «Principali» e «Secondari» con lo `StatusDot` per riga, e un principale quasi
finito dice «non basta» accanto al nome; «Cucina» (con l'icona) è il pulsante principale in
fondo agli ingredienti, prima del procedimento, e sotto c'è il nuovo «Metti in lista ciò che
manca», che manda una `POST /shopping-list` per ogni riga che il server dice non soddisfatta
e riassume nell'avviso («2 in lista · 1 c'era già», «Era già tutto in lista.», con «Riprova»
per le sole righe fallite); il foglio della cottura ha le tacche di `StockGauge` al posto dei
tre pulsanti, e parte dallo stato della confezione (niente toccato è invariato, toccare di
nuovo lo stato di partenza annulla la scelta, «Disponibile» si può scegliere); «Ho cucinato»
dice l'esito con l'avviso e riporta il fuoco su «Cucina»; «Apri l'originale» è alto 44 px,
con la sua icona. «Salva nel ricettario» e «Salva le modifiche» dicono «Salvata.» con
l'avviso prima di portare al dettaglio (T4). `RecipeDetailScreen.tsx` ha ora <righe> righe
(431 prima delle Consegne 4 e 5); «Metti in lista…» sta in `AddMissingButton.tsx` e
`missingToList.ts`.

**Le scelte del piano che Mattia può voler rivedere:** «non basta» è testo accanto al nome e
`StatusDot` non ha imparato `satisfied`; lo stepper dice «Porzioni − 2 +» invece di «Per 2
porzioni», e a porzioni ignote il motivo sta sotto il «+» soltanto (il «−» è spento); «Metti
in lista ciò che manca» sta sotto «Cucina» a tutta larghezza, non accanto (a 375 px non ci
stanno insieme); le frasi «2 c'erano già», «2 non sono andate» e «Non è andata: la lista è
com'era.»; il fuoco torna su «Cucina» anche annullando il foglio; il tasto indietro è una
pastiglia «‹ Ricette» anche senza foto; «Elimina» è grigia come «Modifica», non rossa; un
gruppo d'ingredienti vuoto non ha l'intestazione.

**Da provare sul telefono:** il tasto «Ricette» sopra una foto vera, chiara e scura; lo
stepper di una ricetta senza porzioni; «Metti in lista ciò che manca» e l'avviso, poi la
Lista; le tacche del foglio col pollice, e «Ho cucinato» che riporta a «Cucina»; «Apri
l'originale»; «Salvata.» dopo aver scritto una ricetta e dopo averne modificata una.
```

Sostituisci `<data di oggi>` con la data vera e `<righe>` col numero misurato nel Task 7.

- [ ] **Step 2: T4 fatto, e le osservazioni del giro**

1. Il titolo `## T4. Le azioni grosse non danno una conferma che si veda **[FATTO IN PARTE 2026-09-27 — «Ho cucinato» e il foglio]**` diventa `## T4. Le azioni grosse non danno una conferma che si veda **[FATTO <data di oggi> — l'ultimo punto con la Consegna 5 di T3, non ancora in produzione]**`.
2. In fondo a T4, sostituisci la frase «**Resta aperto** «Salva nel ricettario», con lo stesso avviso che lo servirebbe.» con:
   ```markdown
   **«Salva nel ricettario» è fatto** (T3 Consegna 5, <data di oggi>): dalla bozza e dalla
   modifica l'avviso unico dice «Salvata.» prima di portare al dettaglio, che non legge più
   uno stato della cronologia. Con la stessa consegna l'esito di «Ho cucinato» è passato
   dalla riga in cima al dettaglio all'avviso, e il fuoco torna su «Cucina».
   ```
3. Nella sezione del giro, sotto «**Dettaglio ricetta** (oltre a R10 e T4)», segna ` *(T3 Consegna 5)*` in fondo a queste cinque voci: «**«Cucina» sta in fondo e sembra dire «inizia a cucinare».**», «**I mancanti non si mettono in lista dal dettaglio**…», «**I cinque € sono pulsanti che non sembrano pulsanti**…», «**«Apri l'originale» è alto 19 px.**», «**Senza porzioni lo stepper sparisce** senza dirlo.». Le prime due voci (dosi, procedimento) restano aperte.

- [ ] **Step 3: `next-steps.md`**

1. Aggiorna la riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte)_`.
2. Togli la riga della Consegna 5 da dove si trova («Pronti per la notte» o «Da approfondire»): è quella che comincia con `- [pronto] P1 · Consegna 5` o `- [tbd] P1 · Consegna 5, Dettaglio ricetta`.
3. Togli la riga `- [tbd] P2 · «Salva nel ricettario» senza avviso: …` (è chiusa da questa consegna).
4. In cima a «Fatti (recenti)» aggiungi:
   ```markdown
   - [fatto] <data di oggi> · T3 Consegna 5, Dettaglio ricetta: il tasto sopra la foto, «Modifica»/«Elimina» come icone, costo in sola lettura, stepper sempre visibile, `StatusDot` e «non basta», «Metti in lista ciò che manca», `StockGauge` nel foglio della cottura, «Apri l'originale» a 44 px; e «Salva nel ricettario» con l'avviso «Salvata.» (T4 chiuso) → branch night/c5-dettaglio (da revisionare)
   ```
5. In cima a «Da fare a mano (solo Mattia)» aggiungi:
   ```markdown
   - [tbd] P1 · Prove sul telefono del Dettaglio ricetta (Consegna 5): il tasto «Ricette» sopra una foto chiara e una scura, lo stepper senza porzioni, «Metti in lista ciò che manca» e l'avviso, le tacche del foglio col pollice e il fuoco su «Cucina», «Salvata.» dopo il salvataggio
   ```
6. In «Idee» aggiungi:
   ```markdown
   - [idea] P3 · Lo stepper delle porzioni spegne il «−» con `disabled` quando arriva a 1: premuto da tastiera, il fuoco finisce sul `body` (la stessa forma della ✕ di Lista); `unavailableReason` lo terrebbe, ma con una frase in più sotto lo stepper [T3 Consegna 5]
   ```
7. Se nella notte sono emerse cose da fare fuori da questo piano, aggiungile come `idea` o `tbd` nella sezione giusta, con la voce di `docs/prossimi-passi.md` fra parentesi quadre.

- [ ] **Step 4: Commit**

```bash
git add docs/prossimi-passi.md next-steps.md
git commit -m "docs: T3 Consegna 5, il dettaglio della ricetta; T4 chiuso con «Salva nel ricettario»"
```

---

### Task 10: La verifica finale

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

Expected: vitest tutto verde — **la linea di partenza annotata nella Preparazione più 31 test e 4 file**: 1 (`Button`) + 12 (`missingToList`, file nuovo) + 5 (`AddMissingButton`, file nuovo) + 4 (`ServingsStepper`, file nuovo) + 4 (`CookSheet`) + 1 (`AiDraftScreen`) + 4 (`RecipeDetailScreen`: 8 nuovi, 4 del costo tolti) + 0 (`RecipeEditScreen` e `RecipeDetailActions`, migrati) — con **3** file nuovi di test (`missingToList.test.ts`, `AddMissingButton.test.tsx`, `ServingsStepper.test.tsx`), quindi linea di partenza + 3 file; se il numero differisce, scrivi nel report da dove viene la differenza. Typecheck, lint e build puliti. `npx tsc -b --force` perché `node_modules` è condiviso col checkout principale e con lui il `tsbuildinfo`: `--force` compila davvero tutto invece di fidarsi di una build precedente.

- [ ] **Step 2: Il backend**

Da `<worktree>/backend`:

```bash
PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Expected: tutto verde, lo stesso numero del ramo di partenza (questo piano non tocca il backend).

- [ ] **Step 3: I grep**

Dalla radice del worktree:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -rn "updateRecipeCost\|justSaved\|savedRef\|deletedRecipe" frontend/src
grep -rn "CostPicker" frontend/src/features/cooking
grep -rn "aria-pressed" frontend/src/features/cooking
```

Expected: niente, quattro volte.

- [ ] **Step 4: L'e2e intera**

Con i comandi delle Global Constraints, su uno stack ricreato da zero (`down -v` prima dell'`up`, se ne era rimasto uno di questo ramo). Expected: tutti verdi. Poi `down -v` e `rm .env`, sempre.

- [ ] **Step 5: Un giro nel browser vero**

Con lo stack e2e ancora su (prima del `down -v` dello Step 4, o rialzato), apri `http://localhost:5174` a 375 px, in chiaro e in scuro, e guarda: una ricetta del seme (senza foto), il foglio della cottura aperto, «Metti in lista ciò che manca» e il suo avviso, lo stepper di una ricetta scritta senza porzioni (creala con `POST /api/v1/recipes` senza `servings`, ed eliminala dopo). Annota nel report ciò che un test non poteva vedere; un difetto trovato qui si corregge con un test prima, come negli altri task.

- [ ] **Step 6: Il report**

Nel report della notte, per questo piano: il ramo, i conti veri (vitest, pytest, e2e) con la linea di partenza, le righe di `RecipeDetailScreen.tsx`, le migrazioni di test fatte oltre a quelle elencate nei task (dovrebbero essere zero), se lo Step 4 del Task 8 è servito, e le decisioni prese in autonomia. Niente push, niente merge, niente deploy.
