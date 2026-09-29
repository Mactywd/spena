# T3 Consegna 4 — Il ricettario ridisegnato: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** portare il ricettario (`/ricette`) sulle primitive della Consegna 0: «Nuova» in alto a destra, la barra di ricerca con «Filtri» (col numero dei filtri accesi) che apre in linea un pannello con categoria, ingredienti, il numero dei risultati e «Azzera»; la scala «Cosa posso cucinare» sempre a video; i filtri ricordati finché l'app è aperta; righe compatte con una miniatura da 56 px che non è mai un rettangolo bianco; la scheda «Ingredienti da abbinare» solo a coda non vuota; `EmptyState` ed `ErrorState`; la lapide del ricettario che diventa l'avviso unico, con `useArchiveRecipe` (che il Piano 3 riusa).

**Architecture:** due cambi nel backend, scritti prima coi test su Postgres vero: `GET /recipes/search` manda l'intestazione `X-Total-Count`, contata **prima** del limite in tutti e due i rami (sesta lezione di `CLAUDE.md`), e `RecipeSummaryOut`/`RecipeOut` portano `main_department`, deciso da una funzione pura nuova di `app/domain/rules.py` sulla query che `_requirements_by_recipe` fa già. Nel frontend: `apiFetchWithHeaders` nel client; `searchRecipes` torna `{ recipes, total }`; i filtri (e il loro ricordo in `sessionStorage`) in `recipeFilters.ts`, funzioni pure testate a tabella; la riga in `RecipeRow.tsx` con la miniatura in `RecipeThumb.tsx` (al posto di `RecipeCard.tsx`); il pannello in `RecipeFiltersPanel.tsx`; l'eliminazione in `useArchiveRecipe.ts`, che il dettaglio chiama; `RecipeBookScreen.tsx` riscritto sopra di loro. Nessuna rotta nuova, nessuna migrazione, nessuna dipendenza.

**Tech Stack:** FastAPI, SQLAlchemy async, pytest su Postgres vero; React 19, TypeScript, Tailwind 4 (token in `@theme`), TanStack Query 5, react-router 7, Vitest + Testing Library (jsdom), Playwright.

**Spec:** `docs/superpowers/specs/2026-09-28-ridisegno-design.md`, §2, §3.5 e **§4.5**; le decisioni vincolanti della fase giorno del 2026-09-29 (seconda), «Piano 2 — Ricette (Consegna 4)» e «Interfacce condivise», riportate qui sotto in «Decisioni prese»; le osservazioni del giro sotto «**Ricette**» in `docs/prossimi-passi.md` (T3, esito del giro). Si leggono insieme a questo piano.

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/c4-ricette` (`.worktrees/` è già in `.gitignore`), ramo `night/c4-ricette`, creato da **`night/c6a-pulsanti`** (il ramo del Piano 1), non da `master`. Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì (o dalle sue `backend/` e `frontend/`), mai dalla radice del checkout principale. Il checkout principale non si tocca: se vi trovi modifiche non committate, sono dell'utente. **Nessun push, nessun merge, nessun deploy. Mai `git stash`.**
- **Backend su Postgres vero.** Il database di test è il container `spena-db-1` (porta 5433), da usare solo come database dei test: se `docker ps --format '{{.Names}}'` non lo mostra, `docker start spena-db-1`. **Mai `docker compose up` dal worktree** senza `-p spena-e2e`: il nome del progetto Compose viene dalla cartella, e ne nascerebbe un secondo Postgres che litiga sulla 5433. Nel worktree non c'è un `.venv`: si usa quello del checkout principale; `python -m` mette la cartella corrente in testa a `sys.path`, quindi si prova l'`app` del worktree. Il comando, sempre da `<worktree>/backend`:
  ```bash
  PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
  Se un test sembra ignorare una modifica, `python -c 'import app; print(app.__file__)'` da `<worktree>/backend` (con lo stesso `PATH`) deve stampare un percorso dentro il worktree. Nessuna chiamata di rete nella suite.
- **Frontend**, sempre da `<worktree>/frontend`: `npx vitest run` (non esiste `npm test`), `npm run lint`, `npm run typecheck`, `npm run build`. Il type check è `npm run typecheck` (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0 (settima lezione di `CLAUDE.md`). Aggiungere un campo obbligatorio a `RecipeSummary` rompe ogni oggetto letterale tipizzato che non lo porta: il Task 3 li elenca tutti, e solo `npm run typecheck` lo dice.
- **e2e** (Task 8 e Task 10) sullo stack `spena-e2e`, dalla radice del worktree. Serve un `.env`: **si copia da `.env.example`, che non ha segreti, solo per la prova, e si cancella dopo. Mai leggere né copiare il `.env` del checkout principale.** Prima di alzarlo, `docker ps --format '{{.Names}}' | grep spena-e2e`: se c'è e non l'hai alzato tu (un altro piano della notte), non toccarlo e aspetta che sparisca.
  ```bash
  cp .env.example .env
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed --con-ricette
  (cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
  rm .env
  ```
  Il `-p spena-e2e` e il `-f docker-compose.e2e.yml` vanno in ogni comando: un `down -v` sul progetto di default cancellerebbe la dispensa vera. Lo stack si alza **dal worktree**: il backend monta `./backend` su `/app`, ed è da lì che le prove del Task 8 lanciano `tests/e2e_ricettario.py`. Una prova fallita lascia dati nello stack: prima di rieseguire, `down -v`, `up`, seme.
- Tutto il colore passa dai token di `frontend/src/index.css`. Nessuna schermata nomina un colore crudo: `grep -rn "emerald\|neutral-" frontend/src` resta vuoto. Il testo su un fondo pieno usa il suo `on-*`. Ogni testo sta sopra 4,5:1, in chiaro e in scuro, e lo misura `frontend/e2e/style.spec.ts`.
- Le icone si importano solo da `frontend/src/components/ui/icons.ts` (ci sono già tutte: `IconPencilPlus`, `IconAdjustmentsHorizontal`, `IconSearch`, `IconX`, `IconClearAll`, `IconToolsKitchen2` e le icone dei reparti).
- Regola delle icone (spec §2): **più pulsanti in gruppo → solo icone; un pulsante da solo → icona e testo.** Ogni pulsante di sola icona ha il nome completo come `aria-label`.
- **Regola dei pulsanti spenti** (decisa da Mattia, costruita dal Piano 1): in volo → `busy`; «non ancora» → `unavailableReason`; `disabled` nativo solo dove nessuno dei due vale. Un pulsante con testo visibile e un nome più lungo usa `accessibleName`, e il nome comincia con il testo visibile.
- Ogni bersaglio nuovo è almeno 44×44 px. A 375 px il ricettario non scorre di lato.
- **Il frontend non calcola logica di dominio del backend.** «Hai tutto» risponde a `cookable`; i nomi di «Manca: …» sono `missing_names`; il reparto della miniatura è `main_department`; il numero dei risultati è `X-Total-Count`. Nessuno di questi si ricava nel client.
- **Mai un vicolo cieco.** Il vuoto dice perché e, con dei filtri accesi, offre «Azzera i filtri»; il guasto offre «Riprova»; un'eliminazione o un ripristino falliti offrono «Riprova» nell'avviso.
- Le parole a video sono in italiano e **si copiano esattamente come sono scritte qui**; gli identificatori in inglese; i commenti in italiano come nel resto del codice.
- Nessuna dipendenza nuova, nessuna migrazione (aggiungere un campo a una risposta, o un'intestazione, non lo è).

### Preparazione (una volta, prima del Task 1)

- [ ] Il ramo di partenza esiste ed è quello del Piano 1:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify night/c6a-pulsanti
  ```
  Se non esiste, **fermati**: questo piano parte dal lavoro del Piano 1. Segna la voce `bloccato` in `next-steps.md` sul ramo del Piano 1 (o nel report della notte) con «manca `night/c6a-pulsanti`».
- [ ] Dal checkout principale, allinea `node_modules` al lockfile (non aggiunge dipendenze: installa quelle di `package-lock.json`, come nei piani del 2026-09-29):
  ```bash
  cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund
  ```
- [ ] Crea il worktree dal ramo del Piano 1 e collega `node_modules` (e solo quello: **niente `.env`**):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/c4-ricette -b night/c4-ricette night/c6a-pulsanti
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/c4-ricette/frontend/node_modules
  ```
- [ ] Il contratto di `Button` del Piano 1 c'è:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/c4-ricette
  grep -n "unavailableReason\|accessibleName" frontend/src/components/ui/Button.tsx
  ```
  Expected: tutte e due le prop compaiono. Se `accessibleName` manca, fermati e segnala `bloccato` con «`Button` non ha `accessibleName` (Piano 1)»: il Task 7 lo usa.
- [ ] La linea di partenza, dal worktree:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/c4-ricette/frontend && npx vitest run 2>&1 | grep -E "Test Files|Tests "
  cd /home/mactyws/coding/ais/spena/.worktrees/c4-ricette/backend && PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q 2>&1 | tail -3
  ```
  Annota i due numeri nel report: **B** test vitest in **F** file, **P** test pytest. Devono essere tutti verdi; se no, fermati: non è un difetto di questo piano. Alla fine (Task 10) vitest sarà **B + 56** test in **F + 3** file, pytest **P + 13**.

---

## Obiettivo e contesto

Il ricettario è lo schermo che risponde a «cosa cucino stasera». Il giro di T3 l'ha trovato con i filtri che occupano tutta la prima schermata (la prima ricetta sotto la piega), la scala «Tutte / Ora / +1 / +2 / +3» senza un'etichetta visibile, i mancanti che si leggono come un sottotitolo, schede alte 386 px che mentre la foto carica mostrano un rettangolo bianco, la ricetta a mano che si scrive da «Scrivi con l'AI», la scheda «Ingredienti da abbinare» in cima anche a coda vuota, e il filtro per ingredienti che non conta i risultati né ha un «azzera». Questa consegna lo porta sulle primitive e chiude quelle osservazioni, senza toccare quel che il giro ha chiesto di non riprogettare via: la ricerca che non si traveste da ricettario vuoto quando fallisce, il vuoto che dice *perché* (le parole, la categoria, gli ingredienti, la soglia), la scala che manda `max_missing=0` per «Ora», l'ordine deciso dal backend, «Mostra altre» che non perde quel che è già a video quando fallisce.

## Decisioni prese

Prese di giorno (Mattia e il coordinatore della fase giorno, 2026-09-29): la notte non le riapre.

1. **«Nuova» in alto a destra** (`Screen action`), icona `IconPencilPlus`, porta al modulo di oggi (`/ricette/nuova-ai`, rotta invariata). «Scrivi con l'AI» smette di essere l'ingresso: l'AI resta raggiungibile con «Proponi» dentro il modulo.
2. **Barra di ricerca con accanto «Filtri»** (icona `IconAdjustmentsHorizontal`), col numero dei filtri attivi = categoria scelta (1) + ingredienti scelti. Filtri è un pannello **in linea** sotto la barra, apribile e richiudibile (`aria-expanded`), con dentro categoria e ingredienti, il numero dei risultati e «Azzera». **La scala resta fuori dal pannello**, sempre visibile, con l'etichetta visibile «Cosa posso cucinare»; non conta come filtro nel numero.
3. **Filtri ricordati finché l'app è aperta** (Mattia): testo cercato, categoria, ingredienti e gradino in `sessionStorage`, letto e scritto in try/catch; se non c'è, si parte vuoti. Tornando dal dettaglio si ritrovano.
4. **Numero dei risultati**: il backend manda l'intestazione `X-Total-Count` su `GET /recipes/search`, calcolata **prima** del limite, in tutti e due i rami (sfoglia e testo); il corpo resta una lista (compatibilità coi frontend vecchi in cache del service worker). Il client ha una funzione che legge anche l'intestazione.
5. **Righe compatte**: miniatura da 56 px (la foto; sotto, mentre carica o se manca, l'icona del reparto principale della ricetta su tinta da `departmentStyle`); titolo (al più due righe); «Hai tutto» se `cookable`, altrimenti «Manca: …» con al più tre nomi e poi «e un altro» / «e altri N»; sotto, categoria · costo (`CostMeter`) · minuti se ci sono. Via la provenienza («dataset») e la descrizione dalla riga.
6. **Reparto principale**: `main_department` (stringa o null) su `RecipeSummaryOut` e `RecipeOut`: il reparto più frequente fra le righe **principali**, a parità il primo in ordine alfabetico; calcolato nella query che `_requirements_by_recipe` fa già (nessuna query in più). Null → icona generica.
7. **La scheda «Ingredienti da abbinare» compare solo con `pending_terms > 0`** (il ☰ la raggiunge sempre); il commento «Sempre presente (D3)» di `SectionEntryCard` si aggiorna.
8. **Vuoto**: `EmptyState` che dice perché, con «Azzera i filtri» quando ce ne sono; **errore di caricamento**: `ErrorState` con «Riprova».
9. **La lapide diventa l'avviso**, con `useArchiveRecipe` — interfaccia condivisa, **da produrre esattamente così** (il Piano 3 ci conta): `frontend/src/features/recipes/useArchiveRecipe.ts` esporta `useArchiveRecipe(): { archive(recipe: { id: string; title: string }): void; pending: boolean }`; archivia (`setRecipeArchived(id, true)`), toglie la riga dalla cache del ricettario, alza l'avviso «Eliminata: <titolo>» con «Annulla» (che ripristina con `setRecipeArchived(id, false)`; se il ripristino fallisce, avviso con «Riprova», come in Dispensa), e porta a `/ricette`. Il dettaglio di oggi lo usa al posto di `navigate(..., { state: { deletedRecipe } })`; `state.deletedRecipe`, la lapide e il suo `revealAtTop` spariscono dal ricettario.
10. **e2e a 375×812**: la prima ricetta sta nella prima schermata; niente scorrimento laterale; miniatura e segnaposto; il pannello Filtri; il contrasto nei due temi. Il seme non ha foto né categorie: si seminano come fa `backend/tests/e2e_import_review.py` (dentro il container, con `SPENA_E2E=1`).
11. **`Button`** (Piano 1): si consumano `accessibleName` (e, dove servisse, `unavailableReason`) come il Piano 1 li ha costruiti.

Scelte di questo piano, dove le undici sopra non arrivavano (reversibili; Mattia le rivede):

12. **`main_department` è una funzione pura in `app/domain/rules.py`**, `main_department(lines: Iterable[tuple[IngredientRole, str]]) -> str | None`, testata a tabella, chiamata sia dalla ricerca (sulle righe che `_requirements_by_recipe` legge già, con in più `Ingredient.category`) sia dal dettaglio (`_to_out`, sulle righe già caricate). Una regola, due chiamanti: nessuna copia (prima lezione di `CLAUDE.md`).
13. **`search_recipes` torna `RecipeSearchPage(results, total)`.** Sul ramo senza parole il totale è un `COUNT` sulla stessa query filtrata di `_browse`, prima di `ORDER BY/OFFSET/LIMIT` (una query in più, solo lì). Sul ramo con le parole è il numero dei candidati che passano categoria, ingredienti e soglia, contato prima del taglio `[offset:offset+limit]`: la piscina `CANDIDATE_POOL` resta il limite già scritto e commentato in quel ramo, e il totale conta la risposta a quelle parole, non il ricettario. I test di oggi su `search_recipes` passano da un aiutante `_risultati` che chiama la funzione vera e legge `.results`.
    **Aggiunta del coordinatore della fase giorno (vincolante, sesta lezione di `CLAUDE.md`):** quando sul ramo con le parole la piscina era piena — i candidati prima dei filtri sono quanti `CANDIDATE_POOL` — il totale è solo un minimo. `RecipeSearchPage` porta anche `total_is_lower_bound: bool` (falso sul ramo senza parole, dove il `COUNT` è esatto); la rotta manda allora anche l'intestazione `X-Total-Count-Lower-Bound: 1`; il client la legge accanto a `X-Total-Count`, e l'etichetta dei risultati dice «almeno N ricette» invece di «N ricette». Un test del backend riempie la piscina (con `CANDIDATE_POOL` abbassato col `monkeypatch`) e controlla il segnale; un test della funzione dell'etichetta copre «almeno». Il controllore della notte lo porta nei dispatch dei Task 2, 3 e 4.
14. **Il client**: `apiFetchWithHeaders<T>(path, init)` in `api/client.ts` torna `{ data, headers }`, con gli stessi errori di `apiFetch` (le due passano da una sola `request`). `searchRecipes` torna `RecipePage = { recipes, total }`, con `total` `null` se l'intestazione manca o non è un intero. `nextPageOffset` decide «Mostra altre»: col totale, finché ne mancano; senza (un server di prima), la regola di oggi della pagina piena; una pagina vuota chiude sempre.
15. **I filtri ricordati** stanno sotto la chiave `spena.ricettario.filtri`, e si rileggono campo per campo: una scala che non è un gradino, un ingrediente scritto male, un doppione si scartano senza buttare il resto. **Aperto o chiuso, il pannello non si ricorda**: si riapre chiuso, e il numero su «Filtri» dice che ci sono filtri accesi.
16. **Il pannello resta montato quando è chiuso** (`hidden`): un ingrediente scritto a metà non si perde richiudendolo, e `aria-controls` di «Filtri» punta sempre a un elemento che c'è. `aria-expanded` il Piano 1 l'ha già dato a `Button`; qui **`Button` impara `aria-controls`** (un attributo passato così com'è). Il nome di «Filtri» è «Filtri», «Filtri, 1 attivo», «Filtri, N attivi»; il numero si vede anche, in una pastiglia `bg-brand text-on-brand`.
17. **«Azzera» toglie categoria e ingredienti** (quel che sta nel pannello e che il numero conta), non le parole né la scala, che sono sempre a video e si cambiano da lì. **Senza niente da azzerare, «Azzera» non c'è** (niente `unavailableReason`: non è un «non ancora», è un «non serve»). Icona `IconClearAll`, la stessa di «togli le spuntate» in Lista: vuol dire «togli tutto». «Azzera i filtri» del vuoto fa la stessa cosa.
18. **La miniatura è decorativa** (`alt=""`, e il contenitore `aria-hidden`): il titolo è già il nome del collegamento, e l'alt lo farebbe leggere due volte. L'icona sta sempre sotto la foto, quindi si vede mentre la foto carica e resta se la foto non carica (`RecipeImage` di oggi, riusato). **Senza reparto** l'icona è `IconToolsKitchen2` (quella della scheda Ricette) su ardesia: «altro» è un pacco, e una ricetta non è un pacco.
19. **«Manca: …» è in `text-finished`** (il token che la spec §3.1 dà a «ingrediente che manca»), «Hai tutto» in `text-brand`. Se una ricetta non cucinabile arrivasse senza nomi, la riga dice «Mancano N ingredienti» (o «Manca 1 ingrediente»), mai «Manca:» e niente.
20. **«Nuova»**: testo visibile «Nuova», nome accessibile «Nuova ricetta» (label-in-name), pulsante `secondary` (un collegamento con `buttonClasses`, perché è una navigazione).
21. **I vuoti che nominavano l'AI** ora nominano «Nuova»: «Nessuna ricetta con queste parole: provane altre, o scrivine una con «Nuova».» e «Il ricettario è vuoto: scrivi la prima ricetta con «Nuova».». Il titolo dell'`EmptyState` è «Nessuna ricetta»; il perché sta nel corpo, con le frasi di oggi. Il guasto: «Non sono riuscito a cercare nel ricettario.» con «Riprova».
22. **`useArchiveRecipe`**: un'eliminazione fallita non porta via dal dettaglio e alza l'avviso «Non sono riuscito a eliminarla: è ancora nel ricettario.» con «Riprova» (la frase di oggi, che il test di oggi cerca); un ripristino fallito, «Non sono riuscito a riportare «<titolo>» nel ricettario.» con «Riprova». Il doppio tocco lo ferma `busy` sul pulsante che chiama `archive`, non il gancio. L'«Elimina» del dettaglio diventa un `Button` `danger` con `busy` (il Piano 3 lo ridisegna).
23. **`RecipeCard` diventa `RecipeRow`** (è una riga, non più una scheda), e **`lib/undo.ts` se ne va**: `UNDO_MS` lo usava solo la lapide.
24. **L'aiutante e2e** è `backend/tests/e2e_ricettario.py` (`seed <etichetta>` / `clean`), col suo test di guardia come `test_e2e_import_review_guard.py`. Le foto puntano a `https://foto.e2e.invalid/…` e le serve `page.route` (una buona, una che si interrompe); nelle prove del ricettario il service worker è bloccato (`serviceWorkers: "block"`), così nessuna richiesta di immagine gli passa accanto.

## Criteri di accettazione

- [ ] `GET /api/v1/recipes/search` risponde con l'intestazione `X-Total-Count`: il numero delle ricette che rispondono alla domanda (parole, soglia, categoria, ingredienti), contato prima di `limit`/`offset`, sui due rami; il corpo resta una lista.
- [ ] `RecipeSummaryOut` e `RecipeOut` portano `main_department`: il reparto più frequente fra le righe principali, a parità il primo in ordine alfabetico, `null` senza principali; i secondari non contano.
- [ ] «Nuova» in alto a destra porta a `/ricette/nuova-ai`; nessun collegamento «Scrivi con l'AI» nel ricettario.
- [ ] «Filtri» sta sulla stessa riga del campo di ricerca, è almeno 44×44 px, ha `aria-expanded` e `aria-controls`, e dice il numero dei filtri accesi (categoria 1 + ingredienti) a video e nel nome; parole e scala non contano.
- [ ] Il pannello si apre in linea sotto la barra, contiene categoria, ingredienti, «N ricette» e «Azzera» (solo con qualcosa da azzerare); richiuso, i suoi campi non si vedono.
- [ ] La scala sta fuori dal pannello, sempre a video, con l'etichetta visibile «Cosa posso cucinare».
- [ ] Parole, gradino, categoria e ingredienti si ritrovano tornando da una ricetta (indietro, scheda Ricette, ricaricamento); con la memoria bloccata si parte vuoti e il ricettario funziona.
- [ ] Ogni riga: miniatura da 56×56 (foto, o icona del reparto principale sulla sua tinta — anche mentre la foto carica e se non carica), titolo su al più due righe, «Hai tutto» o «Manca: …» (tre nomi, poi «e un altro» / «e altri N»), sotto categoria · costo · minuti. Niente «dataset», niente descrizione.
- [ ] La scheda «Ingredienti da abbinare» c'è solo con `pending_terms > 0`.
- [ ] Il vuoto è un `EmptyState` col perché, e «Azzera i filtri» quando ce ne sono; il guasto un `ErrorState` con «Riprova» che riprova.
- [ ] «Elimina» nel dettaglio: la ricetta sparisce dal ricettario in cache, l'avviso dice «Eliminata: <titolo>» con «Annulla», si torna a `/ricette` (e «indietro» non riporta alla ricetta); «Annulla» la rimette; i guasti offrono «Riprova». `grep -rn "deletedRecipe\|Tombstone\|UNDO_MS" frontend/src` non stampa niente.
- [ ] A 375×812 la prima ricetta sta nella prima schermata, sopra la barra delle schede; il ricettario non scorre di lato; ogni testo sta sopra 4,5:1 nei due temi, col pannello aperto e nel vuoto.
- [ ] vitest (B + 56 in F + 3 file), typecheck, lint, build, pytest (P + 13) e l'e2e intera verdi.
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

Dalla radice del worktree:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -rn "deletedRecipe\|Tombstone\|UNDO_MS\|RecipeCard" frontend/src
```

Expected: i due `grep` non stampano niente. E l'e2e intera con i comandi delle Global Constraints.

## Fuori scope

- Il dettaglio della ricetta oltre all'«Elimina» che chiama `useArchiveRecipe` (Consegna 5, Piano 3): foto col tasto indietro, `IconToolbar` di Modifica/Elimina, `StatusDot`, «Metti in lista ciò che manca», `StockGauge` nel foglio, «Salvata.» nell'avviso.
- Il modulo della ricetta, R12, `CategorySelect`, la coda d'import, le parole a video fuori dal ricettario («dataset» altrove compreso): Consegna 6b, Piano 4.
- `IngredientPicker` (etichetta, segnaposto, `busy`): è del Piano 1; qui si usa com'è.
- Tecniche e preparazioni mescolate alle ricette, i minuti dai dati grezzi, il procedimento a passi, il layout da desktop (spec §5).
- Ricordare il pannello aperto; ricordare i filtri oltre la sessione (`localStorage`).
- La soglia `CANDIDATE_POOL` del ramo con le parole: il totale la dichiara, non la cambia.
- Le rotte: nessuna nuova; `/ricette/nuova-ai` resta com'è.

## Margine di autonomia

- **Liberi**: i nomi di variabili locali e aiutanti di test non fissati nelle interfacce; l'ordine delle classi Tailwind; i commenti, purché dicano il perché.
- **Non liberi**: le parole a video, **esattamente** come in questo piano; i nomi accessibili; i nomi dei file, delle funzioni e delle prop esportate che un task successivo o il Piano 3 consumano (`useArchiveRecipe` con la sua firma, `withoutRecipe`, `RecipePage`, `searchRecipes`, `nextPageOffset`, `totalFrom`, `apiFetchWithHeaders`, `RecipeFilters`, `loadFilters`, `saveFilters`, `activeFilterCount`, `filtersButtonName`, `resultsLabel`, `FILTERS_KEY`, `EMPTY_FILTERS`, `RecipeRow`, `RecipeThumb`, `RecipeFiltersPanel`, `main_department`, `RecipeSearchPage`); l'intestazione `X-Total-Count`.
- **Nessuna dipendenza nuova**, nessuna migrazione, nessun token di colore nuovo.
- **Un test di oggi si cambia solo per seguire un controllo che ha cambiato nome o posto** (elencati nei task: le frasi della riga, il pannello da aprire, la lapide diventata avviso, la scheda della coda), mai per indebolire un'asserzione. Se ne serve un'altra, scrivila nel report col perché.
- Una decisione non coperta e non reversibile → si ferma quel task, si fa commit del lavoro parziale sul ramo, lo si segna `bloccato` in `next-steps.md` con la domanda precisa, e si passa al task successivo che non ne dipende. Una scelta reversibile e a basso impatto → la più conservativa, annotata nel report della notte.
- Se un test fallisce e non si risolve in modo ragionevole: niente test disattivati, niente asserzioni indebolite; `bloccato` con la diagnosi.

## Dipendenze

- **Parte da `night/c6a-pulsanti`** (Piano 1, `docs/superpowers/plans/2026-09-30-ridisegno-pulsanti-accesso-anagrafica.md`), non da `master`: i quattro piani della notte vanno a catena, ognuno dal ramo del precedente, così la fusione non ha conflitti.
- **Dal Piano 1 serve** `Button` con `accessibleName?: string` (testo visibile + nome più lungo → `aria-label`) e `unavailableReason?: string`, più `busy` di prima; la Preparazione lo controlla. Il Piano 1 cambia anche `IngredientPicker` (segnaposto «Cerca un ingrediente», `busy`): qui non si tocca, e i test cercano il campo per etichetta («Contiene ingredienti»), che non cambia.
- **Il Piano 3** (`night/c5-dettaglio`, da questo ramo) consuma `useArchiveRecipe` esattamente con la firma della decisione 9: non rinominarla, non cambiarne il tipo.
- Le modifiche della fase giorno (i piani e `next-steps.md`) devono essere su `master` prima che la notte cominci, o il Task 9 lavorerà su un `next-steps.md` vecchio: la catena le porta, perché il Piano 1 parte da `master`.

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `backend/app/domain/rules.py` | 1 | `main_department` |
| `backend/tests/domain/test_rules.py` | 1 | la tabella (6 casi) |
| `backend/app/services/recipe_search.py` | 1, 2 | `RecipeRequirement.category`, `RecipeSearchResult.main_department`; `RecipeSearchPage`, il totale in `_browse` e nel ramo con le parole |
| `backend/app/schemas/recipe.py` | 1 | `main_department` su `RecipeOut` e `RecipeSummaryOut` |
| `backend/app/api/recipes.py` | 1, 2 | `main_department` nelle due risposte; `X-Total-Count` |
| `backend/tests/services/test_recipe_search.py` | 1, 2 | un test; l'aiutante `_risultati` e tre test del totale |
| `backend/tests/api/test_recipes.py` | 1, 2 | due test |
| `frontend/src/api/client.ts`, `client.test.ts` | 3 | `apiFetchWithHeaders` |
| `frontend/src/features/recipes/api.ts`, `api.test.ts` (nuovo) | 3 | `RecipePage`, `totalFrom`, `nextPageOffset`, `searchRecipes` |
| `frontend/src/domain/types.ts` | 3 | `RecipeSummary.main_department` |
| sette file di test con un `RecipeSummary`/`RecipeDetail` letterale | 3 | `main_department: null` |
| `frontend/src/features/recipes/RecipeBookScreen.tsx`, `.test.tsx` | 3, 7 | la forma della pagina; poi riscritto |
| `frontend/src/features/recipes/recipeFilters.ts`, `.test.ts` (nuovi) | 4 | filtri, conteggio, nomi, memoria |
| `frontend/src/features/recipes/RecipeThumb.tsx`, `.test.tsx` (nuovi) | 5 | la miniatura |
| `frontend/src/features/recipes/RecipeRow.tsx`, `.test.tsx` (nuovi) | 5 | la riga |
| `frontend/src/features/recipes/useArchiveRecipe.ts`, `.test.tsx` (nuovi) | 6 | eliminare con l'avviso |
| `frontend/src/features/cooking/RecipeDetailScreen.tsx`, `RecipeDetailActions.test.tsx` | 6 | «Elimina» col gancio |
| `frontend/e2e/modifica-ricette.spec.ts` | 6 | l'avviso al posto della lapide |
| `frontend/src/components/ui/Button.tsx`, `Button.test.tsx` | 7 | `aria-controls` (`aria-expanded` c'è dal Piano 1) |
| `frontend/src/features/recipes/MissingBudgetFilter.tsx`, `.test.tsx` | 7 | «Cosa posso cucinare» visibile |
| `frontend/src/features/recipes/RecipeFiltersPanel.tsx` (nuovo) | 7 | il pannello |
| `frontend/src/components/ui/SectionEntryCard.tsx` | 7 | il commento D3 |
| `frontend/src/features/recipes/RecipeCard.tsx`, `RecipeCard.test.tsx`, `RecipeBookScreen.lapide.test.tsx`, `frontend/src/lib/undo.ts` | 7 | tolti |
| `frontend/e2e/style.spec.ts`, `frontend/e2e/non-alimentari.spec.ts` | 7, 8 | «Filtri» prima del filtro; sei prove nuove |
| `backend/tests/e2e_ricettario.py`, `backend/tests/test_e2e_ricettario_guard.py` (nuovi) | 8 | semina e guardia |
| `docs/prossimi-passi.md`, `next-steps.md` | 9 | Consegna 4 |

---

### Task 1: Il reparto principale di una ricetta (`main_department`)

La miniatura di una ricetta senza foto mostra l'icona del suo reparto principale. Quale sia lo decide il server, con una regola sola: una funzione pura nel dominio, chiamata dalla ricerca e dal dettaglio.

**Files:**
- Modify: `backend/app/domain/rules.py` (una funzione nuova, dopo `is_cookable`)
- Modify: `backend/app/services/recipe_search.py` (`RecipeRequirement`, `RecipeSearchResult`, `_requirements_by_recipe`, `search_recipes`)
- Modify: `backend/app/schemas/recipe.py` (`RecipeOut`, `RecipeSummaryOut`)
- Modify: `backend/app/api/recipes.py` (`_to_out`, la rotta `search`)
- Test: `backend/tests/domain/test_rules.py`, `backend/tests/services/test_recipe_search.py`, `backend/tests/api/test_recipes.py`

**Interfaces:**
- Consumes: `IngredientRole` (`app/domain/rules.py`), `Ingredient.category` (colonna `String(20)`, un valore di `IngredientCategory`).
- Produces: `main_department(lines: Iterable[tuple[IngredientRole, str]]) -> str | None` in `app/domain/rules.py`; il campo `main_department: str | None` su `RecipeSearchResult`, `RecipeSummaryOut` e `RecipeOut`. Il Task 3 lo aggiunge al tipo `RecipeSummary` del frontend, il Task 5 lo legge.

- [ ] **Step 1: I test che falliscono**

In `backend/tests/domain/test_rules.py`, aggiungi `main_department,` all'elenco importato da `app.domain.rules`, fra `kind_for_category,` e `missing_count,`:

```python
    kind_for_category,
    main_department,
    missing_count,
```

e in fondo al file:

```python
# --- Il reparto principale di una ricetta (T3 Consegna 4) ---
# La miniatura del ricettario, quando la foto manca o non carica, mostra l'icona del
# reparto «principale»: il più frequente fra le righe principali, a parità il primo in
# ordine alfabetico. I secondari non contano: sale, olio e pepe stanno in mezzo
# ricettario, e contati farebbero di quasi ogni piatto un «condimenti».


@pytest.mark.parametrize(
    ("righe", "atteso"),
    [
        ([(PRIMARY, "verdura"), (PRIMARY, "verdura"), (PRIMARY, "pesce")], "verdura"),
        (
            [(PRIMARY, "pesce"), (SECONDARY, "spezie"), (SECONDARY, "spezie"),
             (SECONDARY, "condimenti")],
            "pesce",
        ),
        # a parità vince l'ordine alfabetico, qualunque sia l'ordine delle righe
        ([(PRIMARY, "pesce"), (PRIMARY, "carne")], "carne"),
        ([(PRIMARY, "carne"), (PRIMARY, "pesce")], "carne"),
        # senza principali non c'è un reparto da dire
        ([(SECONDARY, "spezie")], None),
        ([], None),
    ],
)
def test_il_reparto_principale_viene_dalle_righe_principali(righe, atteso):
    assert main_department(righe) == atteso
```

In `backend/tests/services/test_recipe_search.py`, in fondo:

```python
async def test_il_reparto_principale_arriva_coi_risultati(db_session):
    """Il reparto viaggia con le righe che `_requirements_by_recipe` legge già: nessuna
    query in più, e la regola è quella del dominio."""
    from app.db.models.ingredient import Ingredient, IngredientCategory
    from app.repositories.recipes import create_recipe
    from app.services.recipe_search import search_recipes

    zucchina = Ingredient(
        name="zucchina", display_name="Zucchina", category=IngredientCategory.VERDURA
    )
    carota = Ingredient(name="carota", display_name="Carota", category=IngredientCategory.VERDURA)
    branzino = Ingredient(
        name="branzino", display_name="Branzino", category=IngredientCategory.PESCE
    )
    sale = Ingredient(name="sale", display_name="Sale", category=IngredientCategory.SPEZIE)
    db_session.add_all([zucchina, carota, branzino, sale])
    await db_session.flush()
    await create_recipe(
        db_session, title="Verdure e pesce", description=None, instructions="Cuoci.",
        servings=2, source="manual", source_ref=None,
        ingredients=[
            (zucchina.id, "primary", None, None),
            (carota.id, "primary", None, None),
            (branzino.id, "primary", None, None),
            (sale.id, "secondary", None, None),
        ],
        embedding=None,
    )
    await create_recipe(
        db_session, title="Solo sale", description=None, instructions="Sala.",
        servings=1, source="manual", source_ref=None,
        ingredients=[(sale.id, "secondary", None, None)], embedding=None,
    )
    await db_session.flush()

    risultati = await search_recipes(db_session)

    assert {r.recipe.title: r.main_department for r in risultati} == {
        "Verdure e pesce": "verdura",
        "Solo sale": None,
    }
```

In `backend/tests/api/test_recipes.py`, in fondo:

```python
async def test_il_reparto_principale_arriva_nella_scheda_e_nel_dettaglio(logged_client, cucina):
    """Pasta (cereali) e pomodoro (verdura) sono i due principali, uno a testa: a parità
    vince l'ordine alfabetico. L'aglio è verdura ma secondario: se contasse, vincerebbe
    la verdura, ed è per questo che il caso è scelto così."""
    creata = await _create_recipe(logged_client, cucina)
    solo_aglio = await _create_recipe(
        logged_client, cucina, title="Aglio e basta", primary=(), secondary=("aglio",)
    )
    assert creata["main_department"] == "cereali"

    elenco = (await logged_client.get("/api/v1/recipes/search")).json()
    assert {r["title"]: r["main_department"] for r in elenco} == {
        "Pasta al pomodoro": "cereali",
        "Aglio e basta": None,
    }

    dettaglio = (await logged_client.get(f"/api/v1/recipes/{solo_aglio['id']}")).json()
    assert dettaglio["main_department"] is None
```

- [ ] **Step 2: Farli fallire**

Run (da `<worktree>/backend`): `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/domain/test_rules.py tests/services/test_recipe_search.py tests/api/test_recipes.py`
Expected: FAIL — `ImportError: cannot import name 'main_department'` per `test_rules.py`, `AttributeError: 'RecipeSearchResult' object has no attribute 'main_department'` e `KeyError: 'main_department'` per gli altri due.

- [ ] **Step 3: La regola, nel dominio**

In `backend/app/domain/rules.py`, cambia l'import in cima:

```python
import re
from collections.abc import Iterable
```

in:

```python
import re
from collections import Counter
from collections.abc import Iterable
```

e subito dopo la funzione `is_cookable` aggiungi:

```python
def main_department(lines: Iterable[tuple[IngredientRole, str]]) -> str | None:
    """Il reparto che fa da faccia a una ricetta nel ricettario (T3 Consegna 4): la
    miniatura ne mostra l'icona quando la foto manca o non carica.

    Il più frequente fra le righe principali; a parità, il primo in ordine alfabetico,
    così due richieste uguali danno la stessa icona. I secondari non contano: sale, olio
    e pepe stanno in mezzo ricettario, e contati farebbero di quasi ogni piatto un
    «condimenti». Senza righe principali non c'è un reparto da dire: `None`, e il client
    mostra un'icona generica.
    """
    counts = Counter(category for role, category in lines if role == IngredientRole.PRIMARY)
    if not counts:
        return None
    return min(counts, key=lambda category: (-counts[category], category))
```

- [ ] **Step 4: La ricerca**

In `backend/app/services/recipe_search.py`:

1. Nell'import da `app.domain.rules` aggiungi `main_department`:
   ```python
   from app.domain.rules import (
       Availability,
       IngredientRole,
       is_cookable,
       is_satisfied,
       main_department,
       missing_count,
   )
   ```
2. In `RecipeRequirement`, dopo `availability: Availability`, aggiungi:
   ```python
       # il reparto dell'ingrediente: il reparto principale della ricetta
       # (`main_department`) si decide da qui (T3 Consegna 4)
       category: str
   ```
3. In `RecipeSearchResult`, fra `missing_names: list[str]` e `score: float`, aggiungi:
   ```python
       main_department: str | None
   ```
4. In `_requirements_by_recipe`, la `select` diventa:
   ```python
       statement = (
           select(
               RecipeIngredient.recipe_id,
               RecipeIngredient.ingredient_id,
               RecipeIngredient.role,
               Ingredient.display_name,
               # il reparto viaggia con la riga: `main_department` si decide da qui,
               # senza una query in più
               Ingredient.category,
           )
           .join(Ingredient, Ingredient.id == RecipeIngredient.ingredient_id)
           .where(RecipeIngredient.recipe_id.in_(recipe_ids))
       )
   ```
   e il ciclo in fondo:
   ```python
       for recipe_id, ingredient_id, role, display_name, category in rows:
           have = availability.get(ingredient_id, Availability.MISSING)
           requirements[recipe_id].append(
               RecipeRequirement(display_name, IngredientRole(role), have, category)
           )
   ```
5. In `search_recipes`, dove si costruisce `RecipeSearchResult(...)`, dopo `missing_names=missing_names(reqs),` aggiungi:
   ```python
                   main_department=main_department((r.role, r.category) for r in reqs),
   ```

- [ ] **Step 5: Le risposte**

In `backend/app/schemas/recipe.py`, in `RecipeOut` subito dopo la riga `missing_names: list[str] = []`, e in `RecipeSummaryOut` subito dopo la sua riga `missing_names: list[str] = []`, aggiungi (uguale nei due):

```python
    # il reparto più frequente fra le righe principali (`main_department` in
    # app/domain/rules.py): la miniatura del ricettario ne mostra l'icona quando la foto
    # manca (T3 Consegna 4). `None` senza righe principali
    main_department: str | None = None
```

In `backend/app/api/recipes.py`:

1. Nell'import da `app.domain.rules` aggiungi `main_department`:
   ```python
   from app.domain.rules import (
       Availability,
       IngredientRole,
       is_cookable,
       is_satisfied,
       main_department,
       missing_count,
   )
   ```
2. In `_to_out`, nel `return RecipeOut(...)`, dopo `missing_names=sorted(missing_names),` aggiungi:
   ```python
           main_department=main_department(
               (IngredientRole(ri.role), ri.ingredient.category) for ri in recipe.ingredients
           ),
   ```
3. Nella rotta `search`, nel `RecipeSummaryOut(...)`, dopo `missing_names=r.missing_names,` aggiungi:
   ```python
               main_department=r.main_department,
   ```

- [ ] **Step 6: Farli passare**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/domain/test_rules.py tests/services/test_recipe_search.py tests/api/test_recipes.py`
Expected: PASS, i tre file interi.

- [ ] **Step 7: La suite intera**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q`
Expected: PASS; **P + 8**.

- [ ] **Step 8: Commit**

```bash
git add backend/app/domain/rules.py backend/app/services/recipe_search.py backend/app/schemas/recipe.py backend/app/api/recipes.py backend/tests/domain/test_rules.py backend/tests/services/test_recipe_search.py backend/tests/api/test_recipes.py
git commit -m "ricette: il reparto principale di una ricetta, deciso dalle righe principali"
```

---

### Task 2: Quante ricette rispondono, contate prima del limite (`X-Total-Count`)

Il pannello «Filtri» dice quante ricette rispondono. Contate dopo il limite sarebbero al più la misura della pagina: la sesta lezione di `CLAUDE.md`, stavolta sul conteggio. Il numero va nell'intestazione, e il corpo resta una lista: un frontend vecchio, servito dal service worker, continua a leggerla com'era.

**Files:**
- Modify: `backend/app/services/recipe_search.py` (`RecipeSearchPage`, `_browse`, `search_recipes`)
- Modify: `backend/app/api/recipes.py` (la rotta `search`)
- Test: `backend/tests/services/test_recipe_search.py`, `backend/tests/api/test_recipes.py`

**Interfaces:**
- Consumes: `search_recipes` e `RecipeSearchResult` del Task 1.
- Produces: `@dataclass class RecipeSearchPage: results: list[RecipeSearchResult]; total: int` in `app/services/recipe_search.py`; `search_recipes(...) -> RecipeSearchPage` (stessi argomenti di oggi); `_browse(...) -> tuple[list[uuid.UUID], int]`; l'intestazione `X-Total-Count` (un intero in cifre) su `GET /api/v1/recipes/search`. Il Task 3 la legge.

- [ ] **Step 1: I test di oggi passano da un aiutante**

`search_recipes` smetterà di tornare una lista. I test di oggi guardano ordine, filtri e pagine, cioè i risultati: passano da un aiutante che chiama la funzione vera e ne prende `.results`. Da `<worktree>/backend`:

```bash
sed -i 's/await search_recipes(/await _risultati(/g' tests/services/test_recipe_search.py
sed -i 's/^    from app.services.recipe_search import CANDIDATE_POOL, search_recipes$/    from app.services.recipe_search import CANDIDATE_POOL/; /^    from app.services.recipe_search import search_recipes$/d' tests/services/test_recipe_search.py
grep -n "search_recipes" tests/services/test_recipe_search.py
```

Expected: il `grep` non stampa niente (tutte le chiamate, anche quella del Task 1, sono diventate `_risultati`, e gli import locali di `search_recipes` sono spariti). Poi, in `tests/services/test_recipe_search.py`, subito dopo la riga `from app.services.recipe_search import reciprocal_rank_fusion` in cima, aggiungi:

```python


async def _risultati(session, *args, **kwargs):
    """Le ricette della pagina, senza il totale: i test di ordine, filtri e pagine
    guardano quelle. Chiama `search_recipes` vera; il totale ha i suoi test in fondo."""
    return (await recipe_search.search_recipes(session, *args, **kwargs)).results
```

- [ ] **Step 2: I test del totale**

In fondo a `tests/services/test_recipe_search.py`:

```python
# --- Il totale prima del limite (T3 Consegna 4) ---
# Il pannello «Filtri» dice quante ricette rispondono. Contato dopo il limite sarebbe al
# più la misura della pagina: la sesta lezione di CLAUDE.md, sul conteggio.


async def test_senza_parole_il_totale_conta_oltre_la_pagina(db_session):
    from app.db.models.recipe import Recipe

    for numero in range(35):
        db_session.add(Recipe(title=f"Minestra {numero:02d}", instructions="x", source="manual"))
    await db_session.flush()

    prima = await recipe_search.search_recipes(db_session, limit=30)
    seconda = await recipe_search.search_recipes(db_session, limit=30, offset=30)

    assert (len(prima.results), prima.total) == (30, 35)
    assert (len(seconda.results), seconda.total) == (5, 35)


async def test_il_totale_vede_gli_stessi_filtri_della_pagina(db_session):
    """Categoria, soglia e ingredienti stringono il totale come stringono la pagina: un
    totale su tutto il ricettario, sotto un filtro acceso, direbbe «36 ricette» di un
    elenco che ne ha 32."""
    from app.db.models.ingredient import Ingredient, IngredientCategory
    from app.db.models.pantry import PantryItem
    from app.repositories.recipes import create_recipe

    ho = Ingredient(name="riso", display_name="Riso", category=IngredientCategory.CEREALI)
    non_ho = Ingredient(
        name="zafferano", display_name="Zafferano", category=IngredientCategory.SPEZIE
    )
    db_session.add_all([ho, non_ho])
    await db_session.flush()
    db_session.add(PantryItem(ingredient_id=ho.id, status="available"))
    await db_session.flush()

    async def ricetta(titolo, ingrediente, categoria):
        creata = await create_recipe(
            db_session, title=titolo, description=None, instructions="Cuoci.",
            servings=2, source="manual", source_ref=None,
            ingredients=[(ingrediente.id, "primary", None, None)], embedding=None,
        )
        creata.category = categoria

    for numero in range(32):
        await ricetta(f"Riso {numero:02d}", ho, "Primi")
    for numero in range(3):
        await ricetta(f"Risotto {numero}", non_ho, "Primi")
    await ricetta("Budino di riso", ho, "Dolci")
    await db_session.flush()

    assert (await recipe_search.search_recipes(db_session, limit=30)).total == 36
    assert (await recipe_search.search_recipes(db_session, category="Primi", limit=30)).total == 35
    cucinabili = await recipe_search.search_recipes(
        db_session, category="Primi", max_missing=0, limit=30
    )
    assert (len(cucinabili.results), cucinabili.total) == (30, 32)
    per_ingrediente = await recipe_search.search_recipes(
        db_session, ingredient_ids=[non_ho.id], limit=30
    )
    assert per_ingrediente.total == 3


async def test_con_parole_il_totale_conta_i_candidati_prima_della_pagina(db_session):
    """Sul ramo con le parole il totale è la risposta a quelle parole — i candidati che
    passano i filtri — contata prima del taglio della pagina."""
    from app.db.models.recipe import Recipe

    for numero in range(5):
        db_session.add(Recipe(
            title=f"Zuppa {numero}", instructions="x", source="manual",
            category="Primi" if numero < 2 else None,
        ))
    db_session.add(Recipe(title="Arrosto", instructions="x", source="manual"))
    await db_session.flush()

    prima = await recipe_search.search_recipes(db_session, "zuppa", limit=3)
    dopo = await recipe_search.search_recipes(db_session, "zuppa", limit=3, offset=3)
    primi = await recipe_search.search_recipes(db_session, "zuppa", category="Primi", limit=1)

    assert (len(prima.results), prima.total) == (3, 5)
    assert (len(dopo.results), dopo.total) == (2, 5)
    assert (len(primi.results), primi.total) == (1, 2)
```

In fondo a `tests/api/test_recipes.py`:

```python
async def test_la_ricerca_dice_quante_ricette_ci_sono_prima_del_limite(logged_client, cucina):
    """`X-Total-Count` e non un campo nel corpo: il corpo resta una lista, e una copia
    vecchia del frontend nella cache del service worker continua a leggerla."""
    for titolo in ("Pasta al pomodoro", "Pasta al sugo", "Pasta in bianco"):
        await _create_recipe(logged_client, cucina, title=titolo)

    sfoglia = await logged_client.get("/api/v1/recipes/search?limit=2")
    assert sfoglia.status_code == 200
    assert len(sfoglia.json()) == 2
    assert sfoglia.headers["x-total-count"] == "3"

    cercata = await logged_client.get("/api/v1/recipes/search?q=pasta&limit=1")
    assert len(cercata.json()) == 1
    assert cercata.headers["x-total-count"] == "3"
```

- [ ] **Step 3: Farli fallire**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/services/test_recipe_search.py tests/api/test_recipes.py`
Expected: FAIL — tutti i test del file dei servizi che passano da `_risultati` falliscono con `AttributeError: 'list' object has no attribute 'results'` (è l'aiutante che anticipa il cambio), i tre nuovi con `AttributeError` su `.results`/`.total`, e quello dell'API con `KeyError: 'x-total-count'`. Gli altri test dell'API passano.

- [ ] **Step 4: La pagina e il totale nel servizio**

In `backend/app/services/recipe_search.py`:

1. Subito dopo la classe `RecipeSearchResult` aggiungi:
   ```python
   @dataclass
   class RecipeSearchPage:
       """Una pagina del ricettario e quante ricette rispondono in tutto (T3 Consegna 4).

       `total` si conta prima del limite, con gli stessi filtri della pagina: il numero
       che il pannello «Filtri» mostra è quello della domanda, non di quel che è arrivato
       finora — la sesta lezione di CLAUDE.md, applicata al conteggio.
       """

       results: list[RecipeSearchResult]
       total: int
   ```
2. In `_browse`, la firma:
   ```python
       limit: int,
       offset: int,
   ) -> list[uuid.UUID]:
   ```
   diventa:
   ```python
       limit: int,
       offset: int,
   ) -> tuple[list[uuid.UUID], int]:
   ```
   in fondo alla sua docstring, prima delle virgolette di chiusura, aggiungi il paragrafo:
   ```
       Torna anche quante ricette passano i filtri, contate prima della pagina.
   ```
   e la sua fine:
   ```python
       if max_missing is not None:
           statement = statement.having(missing <= max_missing)
       statement = (
           statement.order_by(missing, Recipe.title, Recipe.id).offset(offset).limit(limit)
       )
       return [row.id for row in (await session.execute(statement)).all()]
   ```
   diventa:
   ```python
       if max_missing is not None:
           statement = statement.having(missing <= max_missing)
       # Il totale sugli stessi filtri, prima di ordine e pagina (T3 Consegna 4): contato
       # dopo `limit` sarebbe al più la misura della pagina, cioè la sesta lezione di
       # CLAUDE.md sul conteggio. Una query in più, solo su questo ramo.
       total = await session.scalar(select(func.count()).select_from(statement.subquery()))
       statement = (
           statement.order_by(missing, Recipe.title, Recipe.id).offset(offset).limit(limit)
       )
       return [row.id for row in (await session.execute(statement)).all()], total or 0
   ```
3. In `search_recipes`, l'inizio:
   ```python
   ) -> list[RecipeSearchResult]:
       """`max_missing` è quante cose si è disposti a comprare; `None` è «tutte»."""
       if query and query.strip():
           semantic = await _semantic_ranking(session, query)
           textual = await _textual_ranking(session, query)
           fused = reciprocal_rank_fusion([semantic, textual])
           candidate_ids = list(fused)
       else:
           candidate_ids = await _browse(
               session, max_missing=max_missing, category=category,
               ingredient_ids=ingredient_ids, limit=limit, offset=offset,
           )
           fused = {recipe_id: 0.0 for recipe_id in candidate_ids}

       if not candidate_ids:
           return []
   ```
   diventa:
   ```python
   ) -> RecipeSearchPage:
       """`max_missing` è quante cose si è disposti a comprare; `None` è «tutte».

       Torna la pagina e quante ricette rispondono in tutto (`RecipeSearchPage`)."""
       # sul ramo con le parole il totale si conta in fondo, sui risultati filtrati
       browse_total = 0
       if query and query.strip():
           semantic = await _semantic_ranking(session, query)
           textual = await _textual_ranking(session, query)
           fused = reciprocal_rank_fusion([semantic, textual])
           candidate_ids = list(fused)
       else:
           candidate_ids, browse_total = await _browse(
               session, max_missing=max_missing, category=category,
               ingredient_ids=ingredient_ids, limit=limit, offset=offset,
           )
           fused = {recipe_id: 0.0 for recipe_id in candidate_ids}

       if not candidate_ids:
           # senza parole la pagina può essere vuota con un totale che non lo è (un
           # offset oltre la fine); con le parole, nessun candidato è nessuna ricetta
           return RecipeSearchPage([], browse_total)
   ```
   e la fine:
   ```python
       if query and query.strip():
           # prima ciò che puoi davvero cucinare, poi la pertinenza
           results.sort(key=lambda r: (r.missing, -r.score, r.recipe.title))
           return results[offset : offset + limit]
       # Senza parole ordine e pagina li ha già decisi `_browse`, in SQL, e `results`
       # segue quell'ordine. Il filtro sulla soglia qui sopra è una conferma, non un
       # secondo taglio: SQL e `missing_count` contano lo stesso numero, e
       # `test_la_soglia_in_sql_coincide_con_la_regola` lo difende.
       return results
   ```
   diventa:
   ```python
       if query and query.strip():
           # prima ciò che puoi davvero cucinare, poi la pertinenza
           results.sort(key=lambda r: (r.missing, -r.score, r.recipe.title))
           # Il totale prima della pagina: i candidati che hanno passato categoria,
           # ingredienti e soglia. Non è il ricettario intero — i candidati sono al più
           # CANDIDATE_POOL per graduatoria, il limite detto sopra `recipe_statement` — ma
           # è tutta la risposta a queste parole, cioè quel che la pagina sfoglia.
           return RecipeSearchPage(results[offset : offset + limit], len(results))
       # Senza parole ordine e pagina li ha già decisi `_browse`, in SQL, e `results`
       # segue quell'ordine. Il filtro sulla soglia qui sopra è una conferma, non un
       # secondo taglio: SQL e `missing_count` contano lo stesso numero, e
       # `test_la_soglia_in_sql_coincide_con_la_regola` lo difende. Per la stessa ragione
       # il totale di `_browse` vale anche per questi risultati.
       return RecipeSearchPage(results, browse_total)
   ```

- [ ] **Step 5: L'intestazione nella rotta**

In `backend/app/api/recipes.py`:

1. L'import di FastAPI diventa:
   ```python
   from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
   ```
2. Nella rotta `search`, aggiungi `response: Response,` come primo parametro:
   ```python
   @router.get("/search", response_model=list[RecipeSummaryOut])
   async def search(
       response: Response,
       q: str | None = None,
   ```
3. Nel corpo, `results = await search_recipes(` diventa `page = await search_recipes(`; subito dopo la chiamata (dopo la sua parentesi di chiusura) aggiungi:
   ```python
       # Quante ricette rispondono a questa domanda, prima del limite (T3 Consegna 4). In
       # un'intestazione e non nel corpo: il corpo resta una lista, e una copia vecchia del
       # frontend servita dal service worker continua a leggerla com'era.
       response.headers["X-Total-Count"] = str(page.total)
   ```
   e in fondo `for r in results` diventa `for r in page.results`.

Nginx inoltra `/api/` allo stesso dominio: l'intestazione arriva al browser senza `Access-Control-Expose-Headers`.

- [ ] **Step 6: Farli passare**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/services/test_recipe_search.py tests/api/test_recipes.py tests/services/test_semantic_degradation.py tests/api/test_recipes_archived_lists.py`
Expected: PASS, tutti i file.

- [ ] **Step 7: La suite intera**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q`
Expected: PASS; **P + 12**. `grep -rn "search_recipes(" backend/app` (dalla radice del worktree) stampa solo la definizione e la chiamata nella rotta.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/recipe_search.py backend/app/api/recipes.py backend/tests/services/test_recipe_search.py backend/tests/api/test_recipes.py
git commit -m "ricette: X-Total-Count, quante ricette rispondono contate prima del limite"
```

---

### Task 3: Il client legge il totale; `RecipeSummary` porta il reparto

**Files:**
- Modify: `frontend/src/api/client.ts` (una `request` comune, `apiFetchWithHeaders`)
- Test: `frontend/src/api/client.test.ts`
- Modify: `frontend/src/features/recipes/api.ts` (`RecipePage`, `totalFrom`, `nextPageOffset`, `searchRecipes`)
- Create: `frontend/src/features/recipes/api.test.ts`
- Modify: `frontend/src/domain/types.ts` (`RecipeSummary.main_department`)
- Modify: `frontend/src/features/recipes/RecipeBookScreen.tsx` (la forma della pagina, e basta)
- Modify: `frontend/src/features/recipes/RecipeBookScreen.test.tsx` (`stubRoutedFetch` con le intestazioni, due test)
- Modify (un campo, per seguire il tipo): `frontend/src/features/recipe-form/RecipeForm.test.tsx`, `frontend/src/features/recipe-form/formModel.test.ts`, `frontend/src/features/recipe-form/RecipeEditScreen.test.tsx`, `frontend/src/features/cooking/RecipeDetailScreen.test.tsx`, `frontend/src/features/cooking/RecipeDetailActions.test.tsx`, `frontend/src/features/cooking/CookSheet.test.tsx`, `frontend/src/features/recipes/RecipeCard.test.tsx`

**Interfaces:**
- Consumes: l'intestazione `X-Total-Count` e il campo `main_department` (Task 1 e 2).
- Produces:
  - `apiFetchWithHeaders<T>(path: string, init?: RequestInit): Promise<{ data: T; headers: Headers }>` in `api/client.ts`, con gli stessi errori di `apiFetch` (`UnauthorizedError` sul 401, `ApiError` con `status` e `body` sugli altri).
  - In `features/recipes/api.ts`: `interface RecipePage { recipes: RecipeSummary[]; total: number | null }`; `totalFrom(headers: Headers): number | null`; `nextPageOffset(lastPage: RecipePage, allPages: RecipePage[]): number | undefined`; `searchRecipes(...)` con gli argomenti di oggi, che torna `Promise<RecipePage>`.
  - `RecipeSummary.main_department: string | null` (e quindi anche su `RecipeDetail`, che la estende).
  - La cache `["recipes", …]` del ricettario tiene `InfiniteData<RecipePage>`: il Task 6 (`withoutRecipe`) ci conta.

- [ ] **Step 1: I test che falliscono**

In `frontend/src/api/client.test.ts`, l'import in cima diventa:

```ts
import { describe, expect, it, vi, beforeEach } from "vitest";
import { apiFetch, apiFetchWithHeaders, UnauthorizedError } from "./client";
```

e in fondo al file aggiungi:

```ts
describe("apiFetchWithHeaders", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("porta il corpo e le intestazioni della risposta", async () => {
    // il totale del ricettario viaggia in un'intestazione (T3 Consegna 4)
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify([{ id: "r1" }]), {
        status: 200,
        headers: { "X-Total-Count": "42" },
      })
    ));
    const { data, headers } = await apiFetchWithHeaders<{ id: string }[]>("/recipes/search");
    expect(data).toEqual([{ id: "r1" }]);
    expect(headers.get("X-Total-Count")).toBe("42");
  });

  it("gli errori sono quelli di apiFetch", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 401 })));
    await expect(apiFetchWithHeaders("/recipes/search")).rejects.toBeInstanceOf(UnauthorizedError);

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "giù" }), { status: 500 })
    ));
    await expect(apiFetchWithHeaders("/recipes/search")).rejects.toMatchObject({
      status: 500,
      message: "giù",
    });
  });
});
```

Crea `frontend/src/features/recipes/api.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { nextPageOffset, searchRecipes, totalFrom, type RecipePage } from "./api";
import type { RecipeSummary } from "../../domain/types";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("totalFrom", () => {
  // meglio nessun conteggio che uno inventato: quel che non è un intero non è un totale
  const casi: [string | null, number | null][] = [
    ["42", 42],
    ["0", 0],
    [null, null],
    ["-1", null],
    ["3.5", null],
    ["tante", null],
  ];
  it.each(casi)("«%s» → %s", (valore, atteso) => {
    const headers = new Headers(valore === null ? {} : { "X-Total-Count": valore });
    expect(totalFrom(headers)).toBe(atteso);
  });
});

describe("nextPageOffset", () => {
  function pagina(quante: number, total: number | null): RecipePage {
    return {
      recipes: Array.from({ length: quante }, (_, n) => ({ id: `r${n}` }) as RecipeSummary),
      total,
    };
  }

  const casi: [string, RecipePage[], number | undefined][] = [
    ["col totale, ne mancano ancora", [pagina(30, 45)], 30],
    ["col totale, una pagina piena che è anche l'ultima chiude", [pagina(30, 30)], undefined],
    ["col totale, la seconda pagina chiude il conto", [pagina(30, 34), pagina(4, 34)], undefined],
    ["senza totale, una pagina piena ne promette un'altra", [pagina(30, null)], 30],
    ["senza totale, una pagina corta è l'ultima", [pagina(12, null)], undefined],
    ["una pagina vuota chiude, qualunque cosa dica il totale", [pagina(30, 40), pagina(0, 40)], undefined],
  ];
  it.each(casi)("%s", (_caso, pagine, atteso) => {
    expect(nextPageOffset(pagine[pagine.length - 1], pagine)).toBe(atteso);
  });
});

describe("searchRecipes", () => {
  it("porta le ricette e il totale dell'intestazione", async () => {
    const spy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([{ id: "r1" }]), {
        status: 200,
        headers: { "X-Total-Count": "12" },
      })
    );
    vi.stubGlobal("fetch", spy);

    await expect(searchRecipes({ query: "pasta", offset: 30 })).resolves.toEqual({
      recipes: [{ id: "r1" }],
      total: 12,
    });
    expect(String(spy.mock.calls[0][0])).toBe(
      "/api/v1/recipes/search?q=pasta&limit=30&offset=30"
    );
  });
});
```

In `frontend/src/features/recipes/RecipeBookScreen.test.tsx`:

1. Sostituisci la funzione `stubRoutedFetch` intera (col suo commento) con:
   ```ts
   /** Quel che il finto server risponde a un percorso: il corpo, lo stato e, se servono,
    * le intestazioni (il totale del ricettario sta in `X-Total-Count`). */
   type Risposta = [unknown, number, Record<string, string>?];

   /** Un fetch che risponde in base al percorso: lo schermo fa tre chiamate — la
    * ricerca, il modo di ricerca e lo stato dell'import — e ognuna deve ricevere una
    * Response nuova, perché il corpo di una Response si legge una volta sola. */
   function stubRoutedFetch(route: (path: string) => Risposta) {
     const spy = vi.fn((url: unknown) => {
       const path = String(url);
       const [body, status, headers]: Risposta = path.includes("/imports/status")
         ? [NESSUN_IMPORT_IN_CORSO, 200]
         : route(path);
       return Promise.resolve(new Response(JSON.stringify(body), { status, headers }));
     });
     vi.stubGlobal("fetch", spy);
     return spy;
   }
   ```
2. Dentro `describe("«Mostra altre»", …)`, dopo il test «con meno di una pagina non la offre», aggiungi:
   ```ts
    // Col totale del server (T3 Consegna 4) «Mostra altre» sa se ne mancano: prima una
    // pagina piena che era anche l'ultima offriva un tocco che portava una pagina vuota.
    it("col totale del server, «Mostra altre» c'è finché non sono arrivate tutte", async () => {
      stubRoutedFetch((path) => {
        const [body, status] = paginato(path);
        return path.includes("/recipes/search?")
          ? [body, status, { "X-Total-Count": "34" }]
          : [body, status];
      });
      renderScreen();
      await screen.findByText("Ricetta 29");

      await userEvent.click(screen.getByRole("button", { name: "Mostra altre" }));

      expect(await screen.findByText("Ricetta 33")).toBeDefined();
      expect(screen.queryByRole("button", { name: "Mostra altre" })).toBeNull();
    });

    it("col totale del server, una pagina piena che è anche l'ultima non la offre", async () => {
      stubRoutedFetch((path) =>
        path.includes("/recipes/search?")
          ? [ricette(30), 200, { "X-Total-Count": "30" }]
          : paginato(path)
      );
      renderScreen();
      await screen.findByText("Ricetta 29");
      expect(screen.queryByRole("button", { name: "Mostra altre" })).toBeNull();
    });
   ```

- [ ] **Step 2: Farli fallire**

Run (da `<worktree>/frontend`): `npx vitest run src/api/client.test.ts src/features/recipes/api.test.ts src/features/recipes/RecipeBookScreen.test.tsx`
Expected: FAIL — `apiFetchWithHeaders`, `totalFrom`, `nextPageOffset` non esportati; nel ricettario il test «una pagina piena che è anche l'ultima» trova ancora «Mostra altre». Gli altri test del ricettario passano (l'intestazione in più non cambia niente).

- [ ] **Step 3: Il client**

Sostituisci in `frontend/src/api/client.ts` la funzione `apiFetch` (dalla riga `export async function apiFetch` alla fine del file) con:

```ts
/** La richiesta e i suoi errori, in un posto solo: `apiFetch` e `apiFetchWithHeaders`
 * ne leggono poi il corpo. Due copie di questi controlli si scollerebbero proprio sul
 * 401, che è quello che riporta all'accesso. */
async function request(path: string, init: RequestInit): Promise<Response> {
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    // il cookie di sessione è HttpOnly: va mandato dal browser, non da noi
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });

  if (response.status === 401) throw new UnauthorizedError();

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(detailToMessage(body?.detail, response.status), response.status, body);
  }
  return response;
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await request(path, init);
  if (response.status === 204) return null as T;
  return (await response.json()) as T;
}

/** Il corpo e le intestazioni, per chi legge nella risposta più del corpo: il totale del
 * ricettario sta in `X-Total-Count` (T3 Consegna 4), perché il corpo di
 * `GET /recipes/search` resta una lista per i frontend vecchi in cache. */
export async function apiFetchWithHeaders<T>(
  path: string,
  init: RequestInit = {}
): Promise<{ data: T; headers: Headers }> {
  const response = await request(path, init);
  const data = response.status === 204 ? (null as T) : ((await response.json()) as T);
  return { data, headers: response.headers };
}
```

- [ ] **Step 4: La pagina del ricettario**

In `frontend/src/features/recipes/api.ts`:

1. L'import in cima diventa:
   ```ts
   import { apiFetch, apiFetchWithHeaders } from "../../api/client";
   ```
2. Subito dopo la costante `RECIPE_PAGE_SIZE` aggiungi:
   ```ts
   /** Una pagina del ricettario e quante ricette rispondono in tutto, contate dal server
    * prima del limite (`X-Total-Count`, T3 Consegna 4). `total` è `null` quando il server
    * non lo dice: meglio nessun numero che uno inventato. */
   export interface RecipePage {
     recipes: RecipeSummary[];
     total: number | null;
   }

   /** Il totale dell'intestazione, o `null` se manca o non è un intero. */
   export function totalFrom(headers: Headers): number | null {
     const raw = headers.get("X-Total-Count");
     if (raw === null || !/^\d+$/.test(raw)) return null;
     return Number(raw);
   }

   /** Da dove parte la pagina dopo, o `undefined` se non ce n'è un'altra.
    *
    * L'offset è quante ricette sono arrivate, doppioni compresi: è il conto che il server
    * usa. Col totale si sa se ne mancano, e una pagina piena che è anche l'ultima non
    * offre più «Mostra altre» su una pagina vuota. Senza totale — un server di prima —
    * vale la regola di prima: una pagina piena fa pensare che ce ne sia un'altra. Una
    * pagina vuota chiude sempre: un totale che non torna non tiene aperto un «Mostra
    * altre» che non porta niente. */
   export function nextPageOffset(lastPage: RecipePage, allPages: RecipePage[]): number | undefined {
     if (lastPage.recipes.length === 0) return undefined;
     const loaded = allPages.reduce((count, page) => count + page.recipes.length, 0);
     if (lastPage.total !== null) return loaded < lastPage.total ? loaded : undefined;
     return lastPage.recipes.length === RECIPE_PAGE_SIZE ? loaded : undefined;
   }
   ```
3. In `searchRecipes`, la firma `} = {}) {` diventa `} = {}): Promise<RecipePage> {`, la funzione diventa `export async function searchRecipes({`, e l'ultima riga:
   ```ts
     return apiFetch<RecipeSummary[]>(`/recipes/search?${params.toString()}`);
   ```
   diventa:
   ```ts
     const { data, headers } = await apiFetchWithHeaders<RecipeSummary[]>(
       `/recipes/search?${params.toString()}`
     );
     return { recipes: data, total: totalFrom(headers) };
   ```

In `frontend/src/domain/types.ts`, in `RecipeSummary`, fra `cost: number | null;` e il commento di `archived_at`, aggiungi:

```ts
  /** Il reparto più frequente fra le righe principali, deciso dal server
   * (`main_department` in `backend/app/domain/rules.py`): la miniatura del ricettario ne
   * mostra l'icona quando la foto manca (T3 Consegna 4). `null` senza righe principali. */
  main_department: string | null;
```

- [ ] **Step 5: Il ricettario legge la pagina nuova**

In `frontend/src/features/recipes/RecipeBookScreen.tsx` (solo questo: lo schermo si riscrive nel Task 7):

1. L'import da `./api` diventa:
   ```ts
   import {
     fetchCategories,
     fetchSearchMode,
     nextPageOffset,
     searchRecipes,
     setRecipeArchived,
   } from "./api";
   ```
2. Le righe:
   ```ts
       // la pagina dopo parte da quante ne sono arrivate, doppioni compresi: è il conto
       // che il server usa per l'offset
       getNextPageParam: (lastPage, allPages) =>
         lastPage.length === RECIPE_PAGE_SIZE
           ? allPages.reduce((total, page) => total + page.length, 0)
           : undefined,
   ```
   diventano:
   ```ts
       // da dove parte la pagina dopo, e se ce n'è una: vedi `nextPageOffset` in api.ts
       getNextPageParam: (lastPage, allPages) => nextPageOffset(lastPage, allPages),
   ```
3. La riga `const recipes = uniqueById(data?.pages.flat() ?? []);` diventa:
   ```ts
     const recipes = uniqueById(data?.pages.flatMap((page) => page.recipes) ?? []);
   ```

- [ ] **Step 6: I letterali tipizzati seguono il tipo**

`main_department` è obbligatorio: ogni `RecipeSummary`/`RecipeDetail` scritto a mano nei test deve portarlo. Da `<worktree>/frontend`:

```bash
for f in src/features/recipe-form/RecipeForm.test.tsx src/features/recipe-form/formModel.test.ts \
         src/features/recipe-form/RecipeEditScreen.test.tsx src/features/cooking/RecipeDetailScreen.test.tsx \
         src/features/cooking/RecipeDetailActions.test.tsx src/features/cooking/CookSheet.test.tsx \
         src/features/recipes/RecipeCard.test.tsx; do
  sed -i '0,/archived_at: null,/s//archived_at: null, main_department: null,/' "$f"
  grep -c "main_department: null" "$f"
done
```

Expected: `1` sette volte (il primo `archived_at: null,` di ogni file è quello del letterale di partenza).

- [ ] **Step 7: Farli passare, e il tipo**

Run: `npx vitest run src/api/client.test.ts src/features/recipes/api.test.ts src/features/recipes/RecipeBookScreen.test.tsx`
Expected: PASS.

Run: `npm run typecheck && npm run lint`
Expected: puliti. Se `tsc -b` segnala un altro letterale senza `main_department` (un `TS2741`), aggiungi lì `main_department: null` accanto ad `archived_at` e scrivilo nel report: è un file che questo piano non ha contato.

- [ ] **Step 8: La suite intera**

Run: `npx vitest run`
Expected: PASS; **B + 17** test, **F + 1** file.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/api/client.test.ts frontend/src/features/recipes/api.ts frontend/src/features/recipes/api.test.ts frontend/src/domain/types.ts frontend/src/features/recipes/RecipeBookScreen.tsx frontend/src/features/recipes/RecipeBookScreen.test.tsx frontend/src/features/recipe-form/RecipeForm.test.tsx frontend/src/features/recipe-form/formModel.test.ts frontend/src/features/recipe-form/RecipeEditScreen.test.tsx frontend/src/features/cooking/RecipeDetailScreen.test.tsx frontend/src/features/cooking/RecipeDetailActions.test.tsx frontend/src/features/cooking/CookSheet.test.tsx frontend/src/features/recipes/RecipeCard.test.tsx
git commit -m "ricette: il client legge il totale del ricettario, e la ricetta porta il reparto principale"
```

---

### Task 4: I filtri del ricettario, contati, nominati e ricordati

Funzioni pure, testate a tabella, che lo schermo del Task 7 usa: quanti filtri sono accesi, come si chiama «Filtri», come si dice il numero dei risultati, e la memoria in `sessionStorage` (letta e scritta in try/catch, riletta campo per campo).

**Files:**
- Create: `frontend/src/features/recipes/recipeFilters.ts`
- Test: `frontend/src/features/recipes/recipeFilters.test.ts`

**Interfaces:**
- Consumes: `BUDGET_STEPS` da `./missingBudget`; il tipo `Ingredient`.
- Produces (tutto esportato da `recipeFilters.ts`):
  - `interface RecipeFilters { query: string; maxMissing: number | null; category: string; ingredients: Ingredient[] }`
  - `EMPTY_FILTERS: RecipeFilters`, `FILTERS_KEY = "spena.ricettario.filtri"`
  - `activeFilterCount(filters: Pick<RecipeFilters, "category" | "ingredients">): number`
  - `filtersButtonName(count: number): string`
  - `resultsLabel(total: number | null): string | null`
  - `loadFilters(store?: Storage | null): RecipeFilters`, `saveFilters(filters: RecipeFilters, store?: Storage | null): void` — senza `store` usano la `sessionStorage` del browser, se si riesce ad aprirla.

- [ ] **Step 1: I test che falliscono**

Crea `frontend/src/features/recipes/recipeFilters.test.ts`:

```ts
import { afterEach, describe, expect, it } from "vitest";
import {
  EMPTY_FILTERS,
  FILTERS_KEY,
  activeFilterCount,
  filtersButtonName,
  loadFilters,
  resultsLabel,
  saveFilters,
  type RecipeFilters,
} from "./recipeFilters";
import type { Ingredient } from "../../domain/types";

const POMODORO: Ingredient = {
  id: "i9", name: "pomodoro", display_name: "Pomodoro", category: "verdura", kind: "food",
};
const BASILICO: Ingredient = {
  id: "i7", name: "basilico", display_name: "Basilico", category: "verdura", kind: "food",
};

/** Una memoria di prova: la stessa interfaccia della `sessionStorage`, in una mappa. */
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

function memoria(): Storage {
  return new MemoriaFinta() as unknown as Storage;
}

const PIENI: RecipeFilters = {
  query: "pasta",
  // zero, non l'assenza di soglia: «Ora» deve tornare «Ora»
  maxMissing: 0,
  category: "Primi piatti",
  ingredients: [POMODORO, BASILICO],
};

afterEach(() => {
  sessionStorage.clear();
});

describe("activeFilterCount", () => {
  // la categoria conta uno, ogni ingrediente uno; parole e scala stanno fuori dal
  // pannello, sempre a video, e non contano
  const casi: [string, RecipeFilters, number][] = [
    ["niente", EMPTY_FILTERS, 0],
    ["la categoria", { ...EMPTY_FILTERS, category: "Primi piatti" }, 1],
    ["due ingredienti", { ...EMPTY_FILTERS, ingredients: [POMODORO, BASILICO] }, 2],
    [
      "categoria e due ingredienti",
      { ...EMPTY_FILTERS, category: "Dolci", ingredients: [POMODORO, BASILICO] },
      3,
    ],
    ["parole e scala non contano", { ...EMPTY_FILTERS, query: "pasta", maxMissing: 2 }, 0],
  ];
  it.each(casi)("%s", (_caso, filtri, atteso) => {
    expect(activeFilterCount(filtri)).toBe(atteso);
  });
});

describe("filtersButtonName", () => {
  const casi: [number, string][] = [
    [0, "Filtri"],
    [1, "Filtri, 1 attivo"],
    [3, "Filtri, 3 attivi"],
  ];
  it.each(casi)("%s → «%s»", (numero, atteso) => {
    // il nome comincia con la scritta a video (label-in-name)
    expect(filtersButtonName(numero)).toBe(atteso);
  });
});

describe("resultsLabel", () => {
  const casi: [number | null, string | null][] = [
    [null, null],
    [0, "Nessuna ricetta"],
    [1, "1 ricetta"],
    [42, "42 ricette"],
  ];
  it.each(casi)("%s → %s", (totale, atteso) => {
    expect(resultsLabel(totale)).toBe(atteso);
  });
});

describe("la memoria dei filtri", () => {
  it("salvati e riletti, i filtri tornano uguali", () => {
    const store = memoria();
    saveFilters(PIENI, store);
    expect(loadFilters(store)).toEqual(PIENI);
  });

  it("senza memoria, o con la memoria vuota, si parte vuoti", () => {
    expect(loadFilters(null)).toEqual(EMPTY_FILTERS);
    expect(loadFilters(memoria())).toEqual(EMPTY_FILTERS);
  });

  it("un contenuto che non è JSON, o non è un oggetto, non rompe niente", () => {
    const store = memoria();
    store.setItem(FILTERS_KEY, "{non è json");
    expect(loadFilters(store)).toEqual(EMPTY_FILTERS);
    store.setItem(FILTERS_KEY, "42");
    expect(loadFilters(store)).toEqual(EMPTY_FILTERS);
  });

  it("quel che non si riconosce si scarta pezzo per pezzo, e il resto resta", () => {
    const store = memoria();
    store.setItem(FILTERS_KEY, JSON.stringify({
      query: 42,
      // non è un gradino della scala
      maxMissing: 7,
      category: "Primi piatti",
      ingredients: [POMODORO, { id: "x" }, POMODORO, "basilico"],
    }));
    expect(loadFilters(store)).toEqual({
      query: "",
      maxMissing: null,
      category: "Primi piatti",
      ingredients: [POMODORO],
    });
  });

  it("una memoria che lancia, in lettura o in scrittura, non rompe niente", () => {
    // dati del sito bloccati, finestra privata, memoria piena
    const rotta = {
      getItem: () => {
        throw new Error("bloccata");
      },
      setItem: () => {
        throw new Error("piena");
      },
    } as unknown as Storage;
    expect(loadFilters(rotta)).toEqual(EMPTY_FILTERS);
    expect(() => saveFilters(PIENI, rotta)).not.toThrow();
  });

  it("di norma usa la sessionStorage del browser: vale finché l'app è aperta", () => {
    saveFilters(PIENI);
    expect(JSON.parse(sessionStorage.getItem(FILTERS_KEY)!)).toEqual(PIENI);
    expect(loadFilters()).toEqual(PIENI);
  });
});
```

- [ ] **Step 2: Farli fallire**

Run: `npx vitest run src/features/recipes/recipeFilters.test.ts`
Expected: FAIL — il modulo `./recipeFilters` non esiste.

- [ ] **Step 3: Il codice**

Crea `frontend/src/features/recipes/recipeFilters.ts`:

```ts
import type { Ingredient } from "../../domain/types";
import { BUDGET_STEPS } from "./missingBudget";

/** Quel che si è chiesto al ricettario: le parole, la scala, la categoria, gli
 * ingredienti. Gli ingredienti interi e non solo gli id: i nomi servono alle pastiglie
 * del pannello e al messaggio del vuoto, e una seconda chiamata per riaverli sarebbe un
 * giro in rete per qualcosa che l'utente ha appena toccato. */
export interface RecipeFilters {
  query: string;
  /** `null` è «Tutte»: l'assenza di soglia, non una soglia larghissima. */
  maxMissing: number | null;
  /** `""` è «Tutte». */
  category: string;
  ingredients: Ingredient[];
}

export const EMPTY_FILTERS: RecipeFilters = {
  query: "",
  maxMissing: null,
  category: "",
  ingredients: [],
};

/** Dove i filtri si ricordano finché l'app è aperta (Mattia, 2026-09-29): tornando da una
 * ricetta si ritrovano. `sessionStorage` e non `localStorage`: chiusa l'app, il
 * ricettario riparte intero, invece di aprirsi filtrato da una ricerca di tre giorni fa. */
export const FILTERS_KEY = "spena.ricettario.filtri";

/** Quanti filtri sono accesi, per il numero su «Filtri»: la categoria conta uno, ogni
 * ingrediente uno. Le parole e la scala stanno fuori dal pannello, sempre a video, e non
 * contano: il numero dice cosa c'è dentro il pannello chiuso. */
export function activeFilterCount(filters: Pick<RecipeFilters, "category" | "ingredients">): number {
  return (filters.category ? 1 : 0) + filters.ingredients.length;
}

/** Il nome di «Filtri» per chi ascolta: la scritta a video, e il numero detto a parole. Il
 * nome comincia con la scritta (label-in-name), così chi dà comandi a voce dice «Filtri». */
export function filtersButtonName(count: number): string {
  if (count === 0) return "Filtri";
  return count === 1 ? "Filtri, 1 attivo" : `Filtri, ${count} attivi`;
}

/** Quante ricette rispondono, a parole. `null` quando il server non lo dice: meglio nessun
 * numero che uno inventato. */
export function resultsLabel(total: number | null): string | null {
  if (total === null) return null;
  if (total === 0) return "Nessuna ricetta";
  return total === 1 ? "1 ricetta" : `${total} ricette`;
}

/** La `sessionStorage`, se si riesce ad aprirla: già leggerla può lanciare (dati del sito
 * bloccati), quindi anche l'accesso sta nel try. */
function sessionStore(): Storage | null {
  try {
    return globalThis.sessionStorage ?? null;
  } catch {
    return null;
  }
}

function isIngredient(value: unknown): value is Ingredient {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.id === "string" &&
    typeof v.name === "string" &&
    typeof v.display_name === "string" &&
    typeof v.category === "string" &&
    (v.kind === "food" || v.kind === "non_food")
  );
}

/** I filtri ricordati, o quelli vuoti. Quel che non si riconosce si scarta pezzo per pezzo
 * — una scala che non è un gradino, un ingrediente scritto male, un doppione — e il resto
 * resta: una memoria scritta da una versione di prima non deve azzerare tutto. */
export function loadFilters(store: Storage | null = sessionStore()): RecipeFilters {
  if (store === null) return EMPTY_FILTERS;
  let saved: unknown;
  try {
    saved = JSON.parse(store.getItem(FILTERS_KEY) ?? "null");
  } catch {
    return EMPTY_FILTERS;
  }
  if (typeof saved !== "object" || saved === null) return EMPTY_FILTERS;
  const s = saved as Record<string, unknown>;
  const steps = BUDGET_STEPS.map((step) => step.value);
  const ingredients = Array.isArray(s.ingredients) ? s.ingredients.filter(isIngredient) : [];
  return {
    query: typeof s.query === "string" ? s.query : "",
    maxMissing:
      typeof s.maxMissing === "number" && steps.includes(s.maxMissing) ? s.maxMissing : null,
    category: typeof s.category === "string" ? s.category : "",
    // due volte lo stesso non stringe niente: resta il primo
    ingredients: ingredients.filter(
      (ingredient, n) => ingredients.findIndex((other) => other.id === ingredient.id) === n
    ),
  };
}

/** Scrive i filtri. Se non si può (memoria piena o bloccata), valgono lo stesso finché lo
 * schermo è aperto: il ricordo è una comodità, non una condizione. */
export function saveFilters(
  filters: RecipeFilters,
  store: Storage | null = sessionStore()
): void {
  if (store === null) return;
  try {
    store.setItem(FILTERS_KEY, JSON.stringify(filters));
  } catch {
    // vedi sopra: niente da fare, e niente da dire
  }
}
```

- [ ] **Step 4: Farli passare**

Run: `npx vitest run src/features/recipes/recipeFilters.test.ts`
Expected: PASS, 18 test.

- [ ] **Step 5: La suite, il tipo e il lint**

Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: PASS; **B + 35** test, **F + 2** file; typecheck e lint puliti.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/recipes/recipeFilters.ts frontend/src/features/recipes/recipeFilters.test.ts
git commit -m "ricette: i filtri del ricettario, contati, nominati e ricordati finché l'app è aperta"
```

---

### Task 5: La riga compatta e la sua miniatura

**Files:**
- Create: `frontend/src/features/recipes/RecipeThumb.tsx`
- Test: `frontend/src/features/recipes/RecipeThumb.test.tsx`
- Create: `frontend/src/features/recipes/RecipeRow.tsx`
- Test: `frontend/src/features/recipes/RecipeRow.test.tsx`

Il ricettario non li usa ancora: il Task 7 li monta nello schermo riscritto, e toglie `RecipeCard`.

**Interfaces:**
- Consumes: `RecipeImage` (`./RecipeImage`, invariato: con `url` null o dopo un errore non rende niente), `departmentStyle` e `TINT_CLASSES` da `components/ui/departments`, `CostMeter`, `RecipeSummary.main_department` (Task 3).
- Produces: `RecipeThumb({ imageUrl: string | null; department: string | null })` — uno `span` con `data-recipe-thumb` e `data-dept` (il reparto, o `""`), 56×56, `aria-hidden`; `RecipeRow({ recipe: RecipeSummary })` — un `<li>` con un `<Link>` a `/ricette/<id>` il cui nome comincia col titolo. Il Task 7 e il Task 8 (l'e2e cerca `[data-recipe-thumb]`) contano su questi nomi.

- [ ] **Step 1: I test che falliscono**

Crea `frontend/src/features/recipes/RecipeThumb.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { fireEvent, render } from "@testing-library/react";
import { RecipeThumb } from "./RecipeThumb";

// Le classi qui sono la mappa reparto → icona e tinta, non la disposizione: che la
// miniatura sia davvero 56 px e che la tinta si veda lo misura il browser
// (`frontend/e2e/style.spec.ts`, «la miniatura»).
function miniatura(container: HTMLElement): HTMLElement {
  return container.querySelector<HTMLElement>("[data-recipe-thumb]")!;
}

describe("RecipeThumb", () => {
  it("senza foto mostra l'icona del reparto principale sulla sua tinta", () => {
    const { container } = render(<RecipeThumb imageUrl={null} department="pesce" />);
    const mini = miniatura(container);
    expect(mini).toHaveClass("bg-dept-blue");
    expect(mini).toHaveAttribute("data-dept", "pesce");
    expect(mini.querySelector("svg.tabler-icon-fish")).not.toBeNull();
    expect(mini.querySelector("img")).toBeNull();
  });

  it("con la foto l'icona resta sotto: mentre carica non c'è un rettangolo bianco", () => {
    const { container } = render(
      <RecipeThumb imageUrl="https://esempio.invalid/p.jpg" department="verdura" />
    );
    const mini = miniatura(container);
    expect(mini).toHaveClass("bg-dept-peach");
    expect(mini.querySelector("svg.tabler-icon-carrot")).not.toBeNull();
    const foto = mini.querySelector("img")!;
    expect(foto).toHaveAttribute("src", "https://esempio.invalid/p.jpg");
    // decorativa: il titolo è già il nome del collegamento, l'alt lo ripeterebbe
    expect(foto).toHaveAttribute("alt", "");
    expect(foto).toHaveAttribute("loading", "lazy");
  });

  it("una foto che non carica lascia l'icona, non un buco", () => {
    const { container } = render(
      <RecipeThumb imageUrl="https://esempio.invalid/rotta.jpg" department="verdura" />
    );
    fireEvent.error(miniatura(container).querySelector("img")!);
    expect(miniatura(container).querySelector("img")).toBeNull();
    expect(miniatura(container).querySelector("svg.tabler-icon-carrot")).not.toBeNull();
  });

  it("senza reparto, l'icona del ricettario su ardesia", () => {
    const { container } = render(<RecipeThumb imageUrl={null} department={null} />);
    const mini = miniatura(container);
    expect(mini).toHaveClass("bg-dept-slate");
    expect(mini).toHaveAttribute("data-dept", "");
    expect(mini.querySelector("svg.tabler-icon-tools-kitchen-2")).not.toBeNull();
  });
});
```

Crea `frontend/src/features/recipes/RecipeRow.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { RecipeRow } from "./RecipeRow";
import type { RecipeSummary } from "../../domain/types";

function ricetta(overrides: Partial<RecipeSummary> = {}): RecipeSummary {
  return {
    id: "r1", title: "Pasta al pomodoro", description: "Di sempre", source: "dataset",
    missing: 0, cookable: true, missing_names: [], image_url: null,
    prep_minutes: null, cook_minutes: null, category: null, cost: null,
    archived_at: null, main_department: null,
    ...overrides,
  };
}

function renderRow(recipe: RecipeSummary) {
  return render(
    <MemoryRouter>
      <ul>
        <RecipeRow recipe={recipe} />
      </ul>
    </MemoryRouter>
  );
}

describe("RecipeRow", () => {
  it("quando si può cucinare dice «Hai tutto», e nessun nome", () => {
    renderRow(ricetta());
    expect(screen.getByText("Hai tutto")).toBeVisible();
    expect(screen.queryByText(/Manca/)).toBeNull();
  });

  it("altrimenti dice «Manca:» coi nomi di quel che manca", () => {
    renderRow(ricetta({ missing: 2, cookable: false, missing_names: ["Basilico", "Pomodoro"] }));
    expect(screen.getByText("Manca: Basilico, Pomodoro")).toBeVisible();
  });

  it("esattamente al limite non taglia: tre nomi restano tre nomi", () => {
    renderRow(ricetta({
      missing: 3, cookable: false, missing_names: ["Acciughe", "Basilico", "Capperi"],
    }));
    expect(screen.getByText("Manca: Acciughe, Basilico, Capperi")).toBeVisible();
  });

  it("taglia gli elenchi lunghi invece di allungare la riga", () => {
    renderRow(ricetta({
      missing: 5, cookable: false,
      missing_names: ["Acciughe", "Basilico", "Capperi", "Olive", "Pomodoro"],
    }));
    expect(screen.getByText("Manca: Acciughe, Basilico, Capperi e altri 2")).toBeVisible();
  });

  it("al singolare dice «un altro»", () => {
    renderRow(ricetta({
      missing: 4, cookable: false,
      missing_names: ["Acciughe", "Basilico", "Capperi", "Olive"],
    }));
    expect(screen.getByText("Manca: Acciughe, Basilico, Capperi e un altro")).toBeVisible();
  });

  it("senza nomi dice quanti ne mancano, mai «Manca:» e niente", () => {
    renderRow(ricetta({ missing: 2, cookable: false }));
    expect(screen.getByText("Mancano 2 ingredienti")).toBeVisible();
  });

  it("sotto, categoria, costo e minuti", () => {
    renderRow(ricetta({ category: "Primi piatti", cost: 4, prep_minutes: 10, cook_minutes: 15 }));
    expect(screen.getByText("Primi piatti")).toBeVisible();
    expect(screen.getByRole("img", { name: "Costo 4 su 5" })).toBeInTheDocument();
    expect(screen.getByText("25 min")).toBeVisible();
  });

  it("senza costo non mostra cinque € grigi", () => {
    renderRow(ricetta({ cost: null }));
    expect(screen.queryByRole("img", { name: /Costo/ })).not.toBeInTheDocument();
    expect(screen.queryByText("€")).not.toBeInTheDocument();
  });

  it("senza categoria, costo né minuti la riga di sotto non c'è", () => {
    const { container } = renderRow(ricetta());
    expect(container.textContent).not.toContain("·");
  });

  it("non dice più la provenienza, né la descrizione", () => {
    renderRow(ricetta({ source: "dataset", description: "Di sempre" }));
    expect(screen.queryByText("dataset")).toBeNull();
    expect(screen.queryByText("Di sempre")).toBeNull();
  });

  it("tutta la riga porta alla ricetta, e il suo nome comincia dal titolo", () => {
    renderRow(ricetta());
    expect(screen.getByRole("link", { name: /^Pasta al pomodoro/ })).toHaveAttribute(
      "href", "/ricette/r1"
    );
  });

  it("la miniatura riceve la foto e il reparto principale", () => {
    const { container } = renderRow(
      ricetta({ image_url: "https://esempio.invalid/p.jpg", main_department: "verdura" })
    );
    const mini = container.querySelector("[data-recipe-thumb]");
    expect(mini).toHaveAttribute("data-dept", "verdura");
    expect(mini?.querySelector("img")).toHaveAttribute("src", "https://esempio.invalid/p.jpg");
  });
});
```

- [ ] **Step 2: Farli fallire**

Run: `npx vitest run src/features/recipes/RecipeThumb.test.tsx src/features/recipes/RecipeRow.test.tsx`
Expected: FAIL — i due moduli non esistono.

- [ ] **Step 3: La miniatura**

Crea `frontend/src/features/recipes/RecipeThumb.tsx`:

```tsx
import { RecipeImage } from "./RecipeImage";
import { departmentStyle, TINT_CLASSES } from "../../components/ui/departments";
import { IconToolsKitchen2 } from "../../components/ui/icons";

/** La miniatura di una riga del ricettario, 56 px (spec T3 §4.5).
 *
 * Sotto c'è sempre l'icona del reparto principale della ricetta sulla sua tinta — il
 * reparto lo decide il server, `main_department` — e sopra, se c'è, la foto. Così mentre
 * la foto carica, o se non carica, si vede l'icona: mai un rettangolo bianco (dal giro:
 * «mentre la foto carica mostrano un rettangolo bianco»). Senza reparto, l'icona del
 * ricettario su ardesia: «altro» è un pacco, e una ricetta non è un pacco.
 *
 * Tutta decorativa (`aria-hidden`, `alt=""`): il titolo è già il nome del collegamento,
 * e l'alt della foto lo farebbe leggere due volte. */
export function RecipeThumb({
  imageUrl,
  department,
}: {
  imageUrl: string | null;
  department: string | null;
}) {
  const { icon: Icon, tint } = department
    ? departmentStyle(department)
    : { icon: IconToolsKitchen2, tint: "slate" as const };
  return (
    <span
      data-recipe-thumb
      data-dept={department ?? ""}
      aria-hidden="true"
      className={`relative flex size-14 shrink-0 items-center justify-center overflow-hidden rounded-xl ${TINT_CLASSES[tint]}`}
    >
      <Icon className="size-6" stroke={1.8} />
      <RecipeImage url={imageUrl} alt="" className="absolute inset-0 size-full object-cover" />
    </span>
  );
}
```

- [ ] **Step 4: La riga**

Crea `frontend/src/features/recipes/RecipeRow.tsx`:

```tsx
import { Fragment, type ReactNode } from "react";
import { Link } from "react-router-dom";
import type { RecipeSummary } from "../../domain/types";
import { CostMeter } from "../../components/ui/CostMeter";
import { RecipeThumb } from "./RecipeThumb";

const MAX_NAMES = 3;

/** I mancanti, tagliati dove la riga smetterebbe di leggersi.
 *
 * Il taglio lo fa il client e non il server: è qui che si sa quanto spazio c'è, e il
 * server manda la lista intera. Con un gradino della scala acceso non si taglia mai — la
 * soglia arriva a tre — e si taglia solo su «Tutte», dove a una ricetta possono mancare
 * dodici cose e la riga diventerebbe più lunga del titolo.
 */
function missingNamesLabel(names: string[]): string {
  if (names.length <= MAX_NAMES) return names.join(", ");
  const altri = names.length - MAX_NAMES;
  return `${names.slice(0, MAX_NAMES).join(", ")} e ${altri === 1 ? "un altro" : `altri ${altri}`}`;
}

/** «Hai tutto», o «Manca: …» coi nomi (spec T3 §4.5; dal giro: i mancanti si leggevano
 * come un sottotitolo).
 *
 * Risponde a `cookable`, il verdetto del backend, e non a `missing === 0`: dedurre il
 * verdetto da un conteggio è il frontend che rifà un calcolo di dominio. I nomi vengono
 * dalla stessa regola del verdetto, quindi a una ricetta non cucinabile ne manca almeno
 * uno; se un giorno non fosse così, la riga dice il numero invece di «Manca:» e niente.
 */
function availabilityLabel(recipe: RecipeSummary): string {
  if (recipe.cookable) return "Hai tutto";
  if (recipe.missing_names.length > 0) return `Manca: ${missingNamesLabel(recipe.missing_names)}`;
  return recipe.missing === 1 ? "Manca 1 ingrediente" : `Mancano ${recipe.missing} ingredienti`;
}

/** Preparazione più cottura, quando almeno uno dei due c'è: «cucinabile ora» più «venti
 * minuti» è una risposta, «cucinabile ora» da solo è metà risposta. */
function totalMinutes(recipe: RecipeSummary): number | null {
  const total = (recipe.prep_minutes ?? 0) + (recipe.cook_minutes ?? 0);
  return total > 0 ? total : null;
}

/** Una riga del ricettario (spec T3 §4.5): miniatura, titolo su al più due righe, cosa
 * manca, e sotto categoria · costo · minuti. Righe compatte al posto delle schede con la
 * foto a tutta larghezza, alte 386 px (dal giro): la prima ricetta sale nella prima
 * schermata. Provenienza e descrizione non ci stanno più: la prima diceva «dataset» a chi
 * non sa cosa sia, la seconda la dice il dettaglio. */
export function RecipeRow({ recipe }: { recipe: RecipeSummary }) {
  const minutes = totalMinutes(recipe);
  // categoria · costo · minuti, ciascuno solo se c'è: un «·» davanti a niente è rumore
  const details: ReactNode[] = [];
  if (recipe.category) {
    details.push(
      <span key="category" className="min-w-0 truncate">
        {recipe.category}
      </span>
    );
  }
  if (recipe.cost !== null) details.push(<CostMeter key="cost" cost={recipe.cost} />);
  if (minutes !== null) {
    details.push(
      <span key="minutes" className="shrink-0">
        {minutes} min
      </span>
    );
  }
  return (
    <li>
      <Link to={`/ricette/${recipe.id}`} className="flex items-center gap-3 py-2">
        <RecipeThumb imageUrl={recipe.image_url} department={recipe.main_department} />
        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="line-clamp-2 font-medium">{recipe.title}</span>
          {/* verde «Hai tutto», rosso «Manca»: il rosso è quello che la spec §3.1 dà
              all'ingrediente che manca, lo stesso del pallino del dettaglio */}
          <span
            className={`text-sm font-medium ${recipe.cookable ? "text-brand" : "text-finished"}`}
          >
            {availabilityLabel(recipe)}
          </span>
          {details.length > 0 && (
            <span className="flex min-w-0 flex-wrap items-center gap-x-1.5 text-xs text-ink-faint">
              {details.map((detail, n) => (
                <Fragment key={n}>
                  {n > 0 && <span aria-hidden="true">·</span>}
                  {detail}
                </Fragment>
              ))}
            </span>
          )}
        </span>
      </Link>
    </li>
  );
}
```

- [ ] **Step 5: Farli passare**

Run: `npx vitest run src/features/recipes/RecipeThumb.test.tsx src/features/recipes/RecipeRow.test.tsx`
Expected: PASS, 4 + 12 test.

- [ ] **Step 6: La suite, il tipo e il lint**

Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: PASS; **B + 51** test, **F + 4** file; typecheck e lint puliti.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/recipes/RecipeThumb.tsx frontend/src/features/recipes/RecipeThumb.test.tsx frontend/src/features/recipes/RecipeRow.tsx frontend/src/features/recipes/RecipeRow.test.tsx
git commit -m "ricette: la riga compatta, con la miniatura che non è mai un rettangolo bianco"
```

---

### Task 6: Eliminare una ricetta con l'avviso (`useArchiveRecipe`)

La lapide del ricettario diventa l'avviso unico (spec §3.5: `Notice` «assorbe la lapide di dispensa e ricettario»). Il gancio è un'interfaccia condivisa: il Piano 3 ridisegna il dettaglio e continua a chiamare `useArchiveRecipe().archive`. **La firma è fissa.**

**Files:**
- Create: `frontend/src/features/recipes/useArchiveRecipe.ts`
- Test: `frontend/src/features/recipes/useArchiveRecipe.test.tsx`
- Modify: `frontend/src/features/cooking/RecipeDetailScreen.tsx` (l'`archive` di oggi, e il pulsante «Elimina»)
- Modify: `frontend/src/features/cooking/RecipeDetailActions.test.tsx` (tre test seguono l'avviso)
- Modify: `frontend/e2e/modifica-ricette.spec.ts` (l'avviso al posto della lapide)

La lapide nel ricettario (`deletedFrom`, `Tombstone`, `revealAtTop`) resta dov'è fino al Task 7, che riscrive lo schermo: da qui in poi nessuno le manda più `state.deletedRecipe`, quindi non compare più.

**Interfaces:**
- Consumes: `setRecipeArchived(id, archived)` e `RecipePage` (`./api`), `useNotice` (`components/ui/noticeContext`), `NoticeProvider` nei test.
- Produces:
  - `useArchiveRecipe(): { archive(recipe: { id: string; title: string }): void; pending: boolean }` — la firma della decisione 9, parola per parola.
  - `withoutRecipe(data: InfiniteData<RecipePage> | undefined, id: string): InfiniteData<RecipePage> | undefined`, esportata per i test.
  - Le parole a video: «Eliminata: <titolo>» con «Annulla»; «Non sono riuscito a riportare «<titolo>» nel ricettario.» con «Riprova»; «Non sono riuscito a eliminarla: è ancora nel ricettario.» con «Riprova».

- [ ] **Step 1: I test che falliscono**

Crea `frontend/src/features/recipes/useArchiveRecipe.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider, type InfiniteData } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { useArchiveRecipe, withoutRecipe } from "./useArchiveRecipe";
import type { RecipePage } from "./api";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import type { RecipeSummary } from "../../domain/types";

const CARBONARA: RecipeSummary = {
  id: "r-carb", title: "Carbonara", description: null, source: "manual", missing: 0,
  cookable: true, missing_names: [], image_url: null, prep_minutes: null, cook_minutes: null,
  category: null, cost: null, archived_at: null, main_department: null,
};
const AGLIO: RecipeSummary = { ...CARBONARA, id: "r-aglio", title: "Aglio e olio" };

// una voce del ricettario in cache, com'è la chiave di RecipeBookScreen
const CHIAVE = ["recipes", "", null, "", []];

function pagine(): InfiniteData<RecipePage> {
  return { pages: [{ recipes: [CARBONARA, AGLIO], total: 2 }], pageParams: [0] };
}

function nuovoClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

type Rotta = (path: string, init?: RequestInit) => [unknown, number];

function stubFetch(route: Rotta) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = route(String(url), init);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function patchMandate(spy: ReturnType<typeof stubFetch>) {
  return spy.mock.calls
    .filter(([, init]) => init?.method === "PATCH")
    .map(([url, init]) => [String(url), JSON.parse(String(init!.body))]);
}

/** Chi elimina: un pulsante, dove si trova, e se l'eliminazione è in volo. */
function Prova() {
  const { archive, pending } = useArchiveRecipe();
  const location = useLocation();
  return (
    <>
      <p data-testid="dove">{location.pathname}</p>
      <p data-testid="in-volo">{String(pending)}</p>
      <button type="button" onClick={() => archive({ id: CARBONARA.id, title: CARBONARA.title })}>
        elimina
      </button>
    </>
  );
}

// NoticeProvider sopra il router, come in App.tsx: l'avviso sopravvive al cambio di pagina
function renderProva(client = nuovoClient()) {
  return render(
    <QueryClientProvider client={client}>
      <NoticeProvider>
        <MemoryRouter initialEntries={["/ricette/r-carb"]}>
          <Routes>
            <Route path="*" element={<Prova />} />
          </Routes>
        </MemoryRouter>
      </NoticeProvider>
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useArchiveRecipe", () => {
  it("archivia, toglie la ricetta dal ricettario in cache, avvisa con «Annulla» e porta al ricettario", async () => {
    const spy = stubFetch(() => [{}, 200]);
    const client = nuovoClient();
    client.setQueryData(CHIAVE, pagine());
    renderProva(client);

    await userEvent.click(screen.getByRole("button", { name: "elimina" }));

    expect(await screen.findByText("Eliminata: Carbonara")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Annulla" })).toBeInTheDocument();
    expect(screen.getByTestId("dove")).toHaveTextContent(/^\/ricette$/);
    expect(patchMandate(spy)).toEqual([["/api/v1/recipes/r-carb", { archived: true }]]);
    // una pagina in cache non la mostra più, e il totale la conta una volta in meno
    expect(client.getQueryData<InfiniteData<RecipePage>>(CHIAVE)!.pages[0]).toEqual({
      recipes: [AGLIO],
      total: 1,
    });
  });

  it("«Annulla» la rimette nel ricettario", async () => {
    const spy = stubFetch(() => [{}, 200]);
    renderProva();

    await userEvent.click(screen.getByRole("button", { name: "elimina" }));
    await userEvent.click(await screen.findByRole("button", { name: "Annulla" }));

    await waitFor(() =>
      expect(patchMandate(spy)).toEqual([
        ["/api/v1/recipes/r-carb", { archived: true }],
        ["/api/v1/recipes/r-carb", { archived: false }],
      ])
    );
    expect(screen.queryByText("Eliminata: Carbonara")).toBeNull();
    expect(screen.queryByText(/Non sono riuscito/)).toBeNull();
  });

  it("un «Annulla» che fallisce lo dice, e «Riprova» ci riprova", async () => {
    let ripristini = 0;
    const spy = stubFetch((_path, init) => {
      const { archived } = JSON.parse(String(init!.body)) as { archived: boolean };
      if (archived) return [{}, 200];
      ripristini += 1;
      return ripristini === 1 ? [{ detail: "giù" }, 500] : [{}, 200];
    });
    renderProva();

    await userEvent.click(screen.getByRole("button", { name: "elimina" }));
    await userEvent.click(await screen.findByRole("button", { name: "Annulla" }));
    // la ricetta è eliminata davvero: perdere l'annulla qui sarebbe il vicolo cieco
    expect(
      await screen.findByText("Non sono riuscito a riportare «Carbonara» nel ricettario.")
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Riprova" }));

    await waitFor(() => expect(ripristini).toBe(2));
    await waitFor(() => expect(screen.queryByText(/Non sono riuscito a riportare/)).toBeNull());
    expect(patchMandate(spy)).toHaveLength(3);
  });

  it("un'eliminazione che fallisce lascia la ricetta dov'è, e «Riprova» ci riprova", async () => {
    let tentativi = 0;
    const spy = stubFetch(() => {
      tentativi += 1;
      return tentativi === 1 ? [{ detail: "giù" }, 500] : [{}, 200];
    });
    const client = nuovoClient();
    client.setQueryData(CHIAVE, pagine());
    renderProva(client);

    await userEvent.click(screen.getByRole("button", { name: "elimina" }));

    expect(
      await screen.findByText("Non sono riuscito a eliminarla: è ancora nel ricettario.")
    ).toBeInTheDocument();
    expect(screen.getByTestId("dove")).toHaveTextContent("/ricette/r-carb");
    expect(client.getQueryData<InfiniteData<RecipePage>>(CHIAVE)!.pages[0].recipes).toHaveLength(2);

    await userEvent.click(screen.getByRole("button", { name: "Riprova" }));

    expect(await screen.findByText("Eliminata: Carbonara")).toBeInTheDocument();
    expect(screen.getByTestId("dove")).toHaveTextContent(/^\/ricette$/);
    expect(patchMandate(spy)).toHaveLength(2);
  });

  it("mentre elimina è in volo, e poi non più", async () => {
    let rispondi: (risposta: Response) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>((resolve) => { rispondi = resolve; }))
    );
    renderProva();
    expect(screen.getByTestId("in-volo")).toHaveTextContent("false");

    await userEvent.click(screen.getByRole("button", { name: "elimina" }));
    await waitFor(() => expect(screen.getByTestId("in-volo")).toHaveTextContent("true"));

    rispondi(new Response(JSON.stringify({}), { status: 200 }));
    await waitFor(() => expect(screen.getByTestId("in-volo")).toHaveTextContent("false"));
  });
});

describe("withoutRecipe", () => {
  it("toglie la ricetta da ogni pagina, e il totale la conta una volta in meno", () => {
    const due: InfiniteData<RecipePage> = {
      pages: [
        { recipes: [CARBONARA, AGLIO], total: 3 },
        { recipes: [{ ...AGLIO, id: "r-altra" }], total: 3 },
      ],
      pageParams: [0, 2],
    };
    expect(withoutRecipe(due, "r-carb")).toEqual({
      pages: [
        { recipes: [AGLIO], total: 2 },
        { recipes: [{ ...AGLIO, id: "r-altra" }], total: 2 },
      ],
      pageParams: [0, 2],
    });
  });

  it("se la ricetta non c'è, le pagine restano le stesse", () => {
    const dati = pagine();
    expect(withoutRecipe(dati, "r-sconosciuta")).toBe(dati);
  });

  it("senza pagine, o senza totale, non inventa niente", () => {
    expect(withoutRecipe(undefined, "r-carb")).toBeUndefined();
    const senzaTotale: InfiniteData<RecipePage> = {
      pages: [{ recipes: [CARBONARA], total: null }],
      pageParams: [0],
    };
    expect(withoutRecipe(senzaTotale, "r-carb")!.pages[0]).toEqual({ recipes: [], total: null });
  });
});
```

In `frontend/src/features/cooking/RecipeDetailActions.test.tsx`:

1. Aggiungi l'import:
   ```tsx
   import { NoticeProvider } from "../../components/ui/NoticeProvider";
   ```
2. `renderAt` impara a mettere l'avviso sopra il router (come in `App.tsx`), solo a chi lo chiede: il test di «Salvata» cerca l'unica regione `status` della pagina, e la regione dell'avviso — che c'è sempre, anche vuota — ne farebbe due. Sostituisci la funzione con:
   ```tsx
   function renderAt(
     entry: string | { pathname: string; state: unknown },
     { notice = false }: { notice?: boolean } = {}
   ) {
     const client = new QueryClient({
       defaultOptions: { queries: { retry: defaultQueryRetryPredicate } },
     });
     const albero = (
       <MemoryRouter initialEntries={[entry]}>
         <Routes>
           <Route path="/ricette" element={<RecipeBookScreen />} />
           <Route
             path="/ricette/:id"
             element={
               <>
                 <RecipeDetailScreen />
                 <StatoDellaVoce />
               </>
             }
           />
         </Routes>
       </MemoryRouter>
     );
     return render(
       <QueryClientProvider client={client}>
         {notice ? <NoticeProvider>{albero}</NoticeProvider> : albero}
       </QueryClientProvider>
     );
   }
   ```
3. Il test `«Elimina» archivia subito e torna al ricettario con la lapide` diventa (la lapide è diventata l'avviso: si segue il controllo rifatto):
   ```tsx
     it("«Elimina» archivia subito e torna al ricettario con l'avviso", async () => {
       const spy = stubFetch((_path, init) =>
         init?.method === "PATCH" ? [{ ...DETAIL, archived_at: "2026-09-28T10:00:00Z" }, 200] : undefined
       );
       renderAt("/ricette/r1", { notice: true });

       await userEvent.click(await screen.findByRole("button", { name: "Elimina" }));

       expect(await screen.findByText("Eliminata: Pasta al pomodoro")).toBeInTheDocument();
       expect(screen.getByRole("button", { name: "Annulla" })).toBeInTheDocument();
       // si è tornati al ricettario
       expect(await screen.findByLabelText("Cerca nel ricettario")).toBeInTheDocument();
       expect(patchMandate(spy)).toEqual([["/api/v1/recipes/r1", { archived: true }]]);
     });
   ```
4. Nel test `dopo «Elimina», «indietro» non riporta alla ricetta eliminata`, avvolgi `<MemoryRouter …>…</MemoryRouter>` in `<NoticeProvider>…</NoticeProvider>` (dentro `QueryClientProvider`), e la riga:
   ```tsx
       expect(await screen.findByRole("status")).toHaveTextContent("Pasta al pomodoro eliminata");
   ```
   diventa:
   ```tsx
       expect(await screen.findByText("Eliminata: Pasta al pomodoro")).toBeInTheDocument();
   ```
5. Il test `un'eliminazione che fallisce lo dice, e la ricetta resta lì` diventa:
   ```tsx
     it("un'eliminazione che fallisce lo dice, e la ricetta resta lì", async () => {
       stubFetch((_path, init) => (init?.method === "PATCH" ? [{ detail: "no" }, 500] : undefined));
       renderAt("/ricette/r1", { notice: true });

       await userEvent.click(await screen.findByRole("button", { name: "Elimina" }));

       expect(await screen.findByText(/non sono riuscito a eliminarla/i)).toBeInTheDocument();
       // l'avviso offre di riprovare: la ricetta c'è ancora, e il gesto anche
       expect(screen.getByRole("button", { name: "Riprova" })).toBeInTheDocument();
       expect(screen.getByRole("heading", { name: "Pasta al pomodoro" })).toBeInTheDocument();
     });
   ```

- [ ] **Step 2: Farli fallire**

Run: `npx vitest run src/features/recipes/useArchiveRecipe.test.tsx src/features/cooking/RecipeDetailActions.test.tsx`
Expected: FAIL — `./useArchiveRecipe` non esiste; nel dettaglio i tre test aspettano un avviso che non arriva (la lapide di oggi non passa dall'avviso, e il guasto è un `Alert` senza «Riprova»).

- [ ] **Step 3: Il gancio**

Crea `frontend/src/features/recipes/useArchiveRecipe.ts`:

```ts
import { useMutation, useQueryClient, type InfiniteData } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { setRecipeArchived, type RecipePage } from "./api";
import { useNotice } from "../../components/ui/noticeContext";

type ArchivedRecipe = { id: string; title: string };

/** Le pagine del ricettario in cache senza una ricetta, col totale che la conta una volta
 * in meno. Tornano le stesse pagine, intatte, se la ricetta non c'era: niente
 * aggiornamento inutile per React. */
export function withoutRecipe(
  data: InfiniteData<RecipePage> | undefined,
  id: string
): InfiniteData<RecipePage> | undefined {
  if (!data || !data.pages.some((page) => page.recipes.some((recipe) => recipe.id === id))) {
    return data;
  }
  return {
    ...data,
    pages: data.pages.map((page) => ({
      recipes: page.recipes.filter((recipe) => recipe.id !== id),
      total: page.total === null ? null : Math.max(page.total - 1, 0),
    })),
  };
}

/** Eliminare una ricetta, dal dettaglio (T3 Consegna 4; spec §3.5, l'avviso che assorbe la
 * lapide del ricettario). Archivia, toglie la riga dal ricettario in cache, alza l'avviso
 * «Eliminata: <titolo>» con «Annulla», e porta al ricettario.
 *
 * Un gancio e non un pezzo del dettaglio perché il dettaglio si ridisegna (Consegna 5) e
 * deve continuare a eliminare nello stesso modo. Il doppio tocco lo ferma `busy` sul
 * pulsante che chiama `archive`: `pending` serve a quello. */
export function useArchiveRecipe(): {
  archive(recipe: { id: string; title: string }): void;
  pending: boolean;
} {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const notice = useNotice();

  // Eliminare e ripristinare cambiano cosa elencano il ricettario e il filtro per
  // categoria, oltre al dettaglio stesso: si rinfrescano tutti e tre.
  function refresh(id: string) {
    return Promise.all([
      queryClient.invalidateQueries({ queryKey: ["recipes"] }),
      queryClient.invalidateQueries({ queryKey: ["recipe-categories"] }),
      queryClient.invalidateQueries({ queryKey: ["recipe", id] }),
    ]);
  }

  // L'annulla vive nell'avviso, che è dell'app e non di chi ha eliminato: si tocca anche
  // quando il dettaglio non c'è più. Per questo non è una useMutation (legata al
  // componente) ma una chiamata col queryClient dell'app, come in Dispensa. Se fallisce,
  // un avviso nuovo lo dice e offre di riprovare: la ricetta è eliminata davvero, e
  // perdere l'annulla qui sarebbe il vicolo cieco.
  function restore(recipe: ArchivedRecipe): void {
    setRecipeArchived(recipe.id, false).then(
      () => refresh(recipe.id),
      () =>
        notice({
          text: `Non sono riuscito a riportare «${recipe.title}» nel ricettario.`,
          action: { label: "Riprova", onClick: () => restore(recipe) },
        })
    );
  }

  const mutation = useMutation({
    mutationFn: (recipe: ArchivedRecipe) => setRecipeArchived(recipe.id, true),
    onSuccess: (_archived, recipe) => {
      // prima di tornare al ricettario: una pagina in cache che la contiene ancora la
      // mostrerebbe per il tempo della rilettura, sotto l'avviso che la dice eliminata
      queryClient.setQueriesData<InfiniteData<RecipePage>>({ queryKey: ["recipes"] }, (data) =>
        withoutRecipe(data, recipe.id)
      );
      notice({
        text: `Eliminata: ${recipe.title}`,
        action: { label: "Annulla", onClick: () => restore(recipe) },
      });
      // `replace`: la ricetta eliminata lascia il posto al ricettario, e «indietro» non
      // ci riporta sopra
      navigate("/ricette", { replace: true });
      void refresh(recipe.id);
    },
    // la ricetta resta dov'è, e con lei il gesto: l'avviso offre di riprovare
    onError: (_error, recipe) =>
      notice({
        text: "Non sono riuscito a eliminarla: è ancora nel ricettario.",
        action: { label: "Riprova", onClick: () => archive(recipe) },
      }),
  });

  // Una dichiarazione col suo tipo, e non `mutation.mutate` scritto dentro le opzioni:
  // il «Riprova» qui sopra richiama la mutazione da dentro il suo stesso inizializzatore,
  // e senza un tipo dichiarato TypeScript non saprebbe dedurre quello di `mutation`
  // (TS7022). `mutate` è stabile: vale anche chiamata da un avviso di un render prima.
  function archive(recipe: ArchivedRecipe): void {
    mutation.mutate(recipe);
  }

  return { archive, pending: mutation.isPending };
}
```

- [ ] **Step 4: Il dettaglio lo usa**

In `frontend/src/features/cooking/RecipeDetailScreen.tsx`:

1. Aggiungi gli import (accanto a quelli di `../recipes/…` e `../../components/ui/…`):
   ```tsx
   import { useArchiveRecipe } from "../recipes/useArchiveRecipe";
   import { Button } from "../../components/ui/Button";
   ```
2. Sostituisci il blocco:
   ```tsx
     // «Elimina» archivia subito, senza chiedere: la conferma è la lapide con «Annulla»
     // nel ricettario, dove si torna (R10 §6.1). `replace`: la ricetta eliminata lascia il
     // posto al ricettario, e «indietro» non ci riporta sopra.
     const archive = useMutation({
       mutationFn: () => setRecipeArchived(id, true),
       onSuccess: (archived) => {
         void refreshAfterArchive();
         navigate("/ricette", {
           replace: true,
           state: { deletedRecipe: { id, title: archived.title } },
         });
       },
     });
   ```
   con:
   ```tsx
     // «Elimina» archivia subito, senza chiedere: la conferma è l'avviso con «Annulla», e
     // si torna al ricettario (T3 Consegna 4: l'avviso unico al posto della lapide). Tutto
     // questo sta in `useArchiveRecipe`, che il dettaglio ridisegnato riusa.
     const { archive, pending: archiving } = useArchiveRecipe();
   ```
3. Sostituisci il pulsante «Elimina» e l'`Alert` che lo segue:
   ```tsx
               <button
                 type="button"
                 onClick={() => archive.mutate()}
                 disabled={archive.isPending}
                 className={buttonClasses("danger")}
               >
                 {archive.isPending ? "Elimino…" : "Elimina"}
               </button>
             </div>
             {archive.isError && (
               <Alert className="pt-2">
                 Non sono riuscito a eliminarla: è ancora nel ricettario. Riprova.
               </Alert>
             )}
   ```
   con:
   ```tsx
               {/* `busy` e non `disabled`: in volo il pulsante tiene il fuoco, e il doppio
                   tocco non parte (regola dei pulsanti, Piano 1). Il guasto lo dice l'avviso,
                   con «Riprova» */}
               <Button
                 variant="danger"
                 busy={archiving}
                 onClick={() => archive({ id, title: recipe.title })}
               >
                 {archiving ? "Elimino…" : "Elimina"}
               </Button>
             </div>
   ```

`setRecipeArchived`, `useMutation`, `useNavigate` e `Alert` restano usati da `restore`, `setCost`, dal «Salvata» e dal guasto della dispensa: `npm run lint` dice se uno è rimasto senza uso.

- [ ] **Step 5: L'e2e segue l'avviso**

In `frontend/e2e/modifica-ricette.spec.ts`:

1. Nel commento in cima, le righe:
   ```
    * dettaglio, si arriva scorsi, e la lapide del ricettario deve farsi vedere in cima
    * (spec §6.1), non nascere sotto l'intestazione fissa. E il modulo di modifica a
   ```
   diventano:
   ```
    * dettaglio, si arriva scorsi, e l'esito — dal T3 Consegna 4 l'avviso unico, non più
    * la lapide in cima al ricettario (R10 §6.1) — deve farsi vedere, sopra la barra delle
    * schede. E il modulo di modifica a
   ```
2. Sostituisci il tratto da `// eliminare, annullare, tornare — «Elimina» è in fondo al dettaglio, quindi ci si` fino a `await expect(page.getByRole("link", { name: new RegExp(titolo) })).toBeVisible();` (compresi) con:
   ```ts
       // eliminare, annullare, tornare — «Elimina» è in fondo al dettaglio, quindi ci si
       // arriva scorsi. La lapide del ricettario nasceva lì sotto l'intestazione fissa
       // (misurato: la sua `getBoundingClientRect().top` a circa −7); l'avviso unico che
       // l'ha sostituita (T3 Consegna 4) è fisso in basso, e deve stare sopra la barra
       // delle schede, a video, da dovunque si arrivi.
       const eliminaBtn = page.getByRole("button", { name: "Elimina" });
       await eliminaBtn.scrollIntoViewIfNeeded();
       const scrollYPrimaDiEliminare = await page.evaluate<number>("window.scrollY");
       expect(scrollYPrimaDiEliminare, "il dettaglio non è scorso: il caso non si può misurare").toBeGreaterThan(0);

       await eliminaBtn.click();
       await expect(page).toHaveURL(/\/ricette$/);
       const avviso = page.getByRole("status").filter({ hasText: `Eliminata: ${titolo}` });
       await expect(avviso).toBeVisible();
       await expect(avviso).toBeInViewport();
       const schede = (await page.getByRole("navigation").boundingBox())!;
       const boxAvviso = (await avviso.boundingBox())!;
       expect(
         boxAvviso.y + boxAvviso.height,
         "l'avviso finisce sotto la barra delle schede"
       ).toBeLessThanOrEqual(schede.y);
       await avviso.getByRole("button", { name: "Annulla" }).click();
       await expect(avviso).toHaveCount(0);
       await page.getByLabel("Cerca nel ricettario").fill(titolo);
       await expect(page.getByRole("link", { name: new RegExp(titolo) })).toBeVisible();
   ```

L'e2e non si esegue qui: la prova il Task 8.

- [ ] **Step 6: Farli passare**

Run: `npx vitest run src/features/recipes/useArchiveRecipe.test.tsx src/features/cooking/RecipeDetailActions.test.tsx src/features/cooking/RecipeDetailScreen.test.tsx`
Expected: PASS.

- [ ] **Step 7: La suite, il tipo e il lint**

Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: PASS; **B + 59** test, **F + 5** file; typecheck e lint puliti (anche `e2e/modifica-ricette.spec.ts`, che `tsc -b` compila).

- [ ] **Step 8: Commit**

```bash
git add frontend/src/features/recipes/useArchiveRecipe.ts frontend/src/features/recipes/useArchiveRecipe.test.tsx frontend/src/features/cooking/RecipeDetailScreen.tsx frontend/src/features/cooking/RecipeDetailActions.test.tsx frontend/e2e/modifica-ricette.spec.ts
git commit -m "ricette: eliminare dal dettaglio passa dall'avviso unico, con useArchiveRecipe"
```

---

### Task 7: Lo schermo — «Nuova», la barra con «Filtri», il pannello, la memoria, le righe, il vuoto e il guasto

**Files:**
- Modify: `frontend/src/components/ui/Button.tsx`, `frontend/src/components/ui/Button.test.tsx` (`aria-controls`; `aria-expanded` c'è dal Piano 1)
- Modify: `frontend/src/features/recipes/MissingBudgetFilter.tsx`, `MissingBudgetFilter.test.tsx` («Cosa posso cucinare» visibile)
- Create: `frontend/src/features/recipes/RecipeFiltersPanel.tsx`
- Modify (riscritto): `frontend/src/features/recipes/RecipeBookScreen.tsx`
- Modify (riscritto): `frontend/src/features/recipes/RecipeBookScreen.test.tsx`
- Modify: `frontend/src/components/ui/SectionEntryCard.tsx` (il commento D3)
- Delete: `frontend/src/features/recipes/RecipeCard.tsx`, `frontend/src/features/recipes/RecipeCard.test.tsx`, `frontend/src/features/recipes/RecipeBookScreen.lapide.test.tsx`, `frontend/src/lib/undo.ts`
- Modify: `frontend/e2e/style.spec.ts` (la prova della pastiglia apre «Filtri»; un commento), `frontend/e2e/non-alimentari.spec.ts` (apre «Filtri»)

**Interfaces:**
- Consumes: `Button` con `accessibleName` e `busy` (Piano 1); `searchRecipes`, `nextPageOffset`, `RecipePage` (Task 3); tutto `recipeFilters.ts` (Task 4); `RecipeRow` (Task 5); `EmptyState`, `ErrorState`, `SectionEntryCard`, `Screen`, `IngredientPicker`.
- Produces: `Button` accetta anche `"aria-controls"?: string` (`"aria-expanded"` c'è dal Piano 1); `RecipeFiltersPanel` (props sotto); i nomi a video che il Task 8 cerca: il collegamento «Nuova ricetta», il pulsante «Filtri» (nome `/^Filtri/`), l'elenco `aria-label="Ricette trovate"`, il campo «Cerca nel ricettario», i campi «Categoria» e «Contiene ingredienti» nel pannello, il gruppo «Cosa posso cucinare», «Azzera», «Azzera i filtri».

**Cosa cambia nei test di oggi di `RecipeBookScreen.test.tsx`** (seguono un controllo rifatto, nessuno si indebolisce): «mostra la provenienza» diventa «la riga non dice la provenienza né la descrizione» (la decisione 5 la toglie); «manca 1 ingrediente» → «Manca: Pomodoro», «Puoi cucinarla ora» → «Hai tutto»; «Nessuna ricetta. Provane una scritta con l'AI.» → «Il ricettario è vuoto: scrivi la prima ricetta con «Nuova».» (l'AI non è più l'ingresso); la scheda della coda a coda vuota, o con lo stato che non arriva, non c'è più (decisione 7); «non riordina» legge l'ordine dagli indirizzi delle righe (il primo `span` della riga ora è la miniatura); foto e foto rotta si cercano dentro la riga (la foto è decorativa, `alt=""`); categoria e ingredienti si trovano dopo aver aperto «Filtri». I fixture `POMODORO` e `BASILICO` prendono `kind: "food"`, come la risposta vera: la memoria dei filtri scarta un ingrediente senza `kind`.

- [ ] **Step 1: I test del ricettario, riscritti**

Sostituisci **tutto** `frontend/src/features/recipes/RecipeBookScreen.test.tsx` con:

```tsx
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { RecipeBookScreen } from "./RecipeBookScreen";
import { UnauthorizedError } from "../../api/client";

// `kind` c'è perché c'è nella risposta vera, e perché i filtri ricordati scartano un
// ingrediente che non ce l'ha: senza, il test del ricordo mentirebbe
const POMODORO = { id: "i9", name: "pomodoro", display_name: "Pomodoro", category: "verdura", kind: "food" };
const BASILICO = { id: "i7", name: "basilico", display_name: "Basilico", category: "verdura", kind: "food" };

/** L'ultima richiesta di ricerca partita davvero: il filtro cambia la query, e
 * guardare la prima chiamata vorrebbe dire guardare lo schermo prima del gesto. */
function ultimaRicerca(fetchMock: { mock: { calls: unknown[][] } }): string {
  return fetchMock.mock.calls
    .map(([url]) => String(url))
    .filter((u) => u.includes("/recipes/search?"))
    .pop()!;
}

const RESULTS = [
  { id: "r1", title: "Pasta all'aglio", description: "Svelta", source: "dataset",
    missing: 0, cookable: true, missing_names: [], image_url: "https://example.com/aglio.jpg",
    prep_minutes: 10, cook_minutes: 15, category: "Primi piatti", cost: null,
    archived_at: null, main_department: "cereali" },
  { id: "r2", title: "Pasta al pomodoro", description: "Di sempre", source: "ai",
    missing: 1, cookable: false, missing_names: ["Pomodoro"], image_url: null,
    prep_minutes: null, cook_minutes: null, category: null, cost: null,
    archived_at: null, main_department: null },
];

/** Una riga di ricettario coi campi che la risposta vera porta tutti. */
function riga(id: string, title: string, extra: Record<string, unknown> = {}) {
  return { ...RESULTS[1], id, title, missing: 0, cookable: true, missing_names: [], ...extra };
}

function renderScreen(queryCache?: QueryCache) {
  const client = new QueryClient({
    queryCache,
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <RecipeBookScreen />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

// Nessun ingrediente in attesa: la scheda d'ingresso alla coda non c'è (T3 Consegna 4),
// e la coda resta raggiungibile dal ☰
const NESSUN_IMPORT_IN_CORSO = {
  fetched: 0, pending_recipes: 0, imported: 0, skipped: 0, pending_terms: 0,
};

/** Quel che il finto server risponde a un percorso: il corpo, lo stato e, se servono,
 * le intestazioni (il totale del ricettario sta in `X-Total-Count`). */
type Risposta = [unknown, number, Record<string, string>?];

/** Un fetch che risponde in base al percorso: lo schermo fa tre chiamate — la
 * ricerca, il modo di ricerca e lo stato dell'import — e ognuna deve ricevere una
 * Response nuova, perché il corpo di una Response si legge una volta sola. */
function stubRoutedFetch(route: (path: string) => Risposta) {
  const spy = vi.fn((url: unknown) => {
    const path = String(url);
    const [body, status, headers]: Risposta = path.includes("/imports/status")
      ? [NESSUN_IMPORT_IN_CORSO, 200]
      : route(path);
    return Promise.resolve(new Response(JSON.stringify(body), { status, headers }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

/** Apre il pannello «Filtri»: categoria e ingredienti stanno lì dentro. */
async function apriFiltri() {
  await userEvent.click(await screen.findByRole("button", { name: /^Filtri/ }));
}

// i filtri si ricordano in sessionStorage: ogni test parte e finisce senza
beforeEach(() => {
  sessionStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const CODA_CON_CATEGORIE = (path: string): Risposta => {
  if (path.includes("/recipes/categories")) return [["Primi piatti", "Dolci e Desserts"], 200];
  if (path.includes("/recipes/search-mode")) return [{ semantic: true }, 200];
  return [RESULTS, 200];
};

/** Come `CODA_CON_CATEGORIE`, e in più i suggerimenti degli ingredienti. */
const CON_POMODORO = (path: string): Risposta =>
  path.includes("/ingredients") ? [[POMODORO], 200] : CODA_CON_CATEGORIE(path);

describe("RecipeBookScreen", () => {
  it("la riga non dice la provenienza né la descrizione", async () => {
    // dal giro: «dataset» non dice niente a chi usa l'app, e la descrizione la dice il
    // dettaglio (T3 Consegna 4)
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();
    await screen.findByText("Pasta all'aglio");
    expect(screen.queryByText("dataset")).toBeNull();
    expect(screen.queryByText("AI")).toBeNull();
    expect(screen.queryByText("Svelta")).toBeNull();
  });

  it("dice cosa manca, senza nascondere la ricetta", async () => {
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();
    expect(await screen.findByText("Pasta al pomodoro")).toBeDefined();
    expect(screen.getByText("Manca: Pomodoro")).toBeDefined();
  });

  it("segnala le ricette che puoi cucinare adesso", async () => {
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();
    expect(await screen.findByText("Hai tutto")).toBeDefined();
  });

  it("la ricerca passa la query al backend", async () => {
    const spy = stubRoutedFetch(CODA_CON_CATEGORIE);

    renderScreen();
    await userEvent.type(await screen.findByLabelText("Cerca nel ricettario"), "pomodoro");

    await vi.waitFor(() =>
      expect(spy.mock.calls.some(([url]) => String(url).includes("q=pomodoro"))).toBe(true)
    );
  });

  it("la scala manda la soglia, e «Ora» manda zero", async () => {
    const spy = stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();
    await screen.findByText("Pasta all'aglio");

    await userEvent.click(
      screen.getByRole("radio", { name: "Solo quelle che puoi cucinare adesso." })
    );

    // `max_missing=0`, non l'assenza del parametro: «cucinabili ora» è la soglia più
    // stretta, e un `if (maxMissing)` la scambierebbe per «Tutte» mostrando tutto
    await waitFor(() => expect(ultimaRicerca(spy)).toContain("max_missing=0"));
    expect(ultimaRicerca(spy)).not.toContain("only_cookable");
  });

  it("un gradino più largo manda la sua soglia", async () => {
    const spy = stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();
    await screen.findByText("Pasta all'aglio");

    await userEvent.click(
      screen.getByRole("radio", { name: "Al massimo 2 ingredienti da comprare." })
    );

    await waitFor(() => expect(ultimaRicerca(spy)).toContain("max_missing=2"));
  });

  it("senza soglia non manda il parametro", async () => {
    const spy = stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();
    await screen.findByText("Pasta all'aglio");

    expect(ultimaRicerca(spy)).not.toContain("max_missing");
  });

  it("la scala ha un'etichetta visibile, «Cosa posso cucinare», anche a pannello chiuso", async () => {
    // dal giro: la scala «Tutte / Ora / +1 / +2 / +3» non aveva un'etichetta che si
    // vedesse; e resta fuori dal pannello dei filtri, sempre a video
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();
    expect(await screen.findByRole("group", { name: "Cosa posso cucinare" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Filtri" })).toHaveAttribute("aria-expanded", "false");
  });

  // Spec §11: «modello di embedding non caricato → la ricerca degrada a sola
  // ricerca testuale, con avviso discreto». Prima il degrado era invisibile: una
  // ricerca che trova solo le parole esatte ha lo stesso aspetto di una che capisce
  // il senso, e il difetto del Dockerfile che lo causava (C1) è stato invisibile
  // per tutto il branch proprio per questo.
  it("quando la ricerca è solo testuale lo dice, e non sembra un errore", async () => {
    stubRoutedFetch((path) => {
      if (path.includes("/search-mode")) return [{ semantic: false }, 200];
      if (path.includes("/recipes/categories")) return [[], 200];
      return [RESULTS, 200];
    });
    renderScreen();

    expect(await screen.findByText(/solo testuale/i)).toBeDefined();
    // una constatazione, non un guasto: nessun ruolo d'allarme, e le ricette ci sono
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByText("Pasta al pomodoro")).toBeDefined();
  });

  it("quando la ricerca è ibrida non dice niente", async () => {
    stubRoutedFetch((path) => {
      if (path.includes("/search-mode")) return [{ semantic: true }, 200];
      if (path.includes("/recipes/categories")) return [[], 200];
      return [RESULTS, 200];
    });
    renderScreen();

    await screen.findByText("Pasta al pomodoro");
    expect(screen.queryByText(/solo testuale/i)).toBeNull();
  });

  it("se il modo di ricerca non risponde non mostra un avviso rotto", async () => {
    // un avviso su una cosa che forse funziona è peggio del silenzio, e il
    // ricettario deve restare utilizzabile
    stubRoutedFetch((path) => {
      if (path.includes("/search-mode")) return [{ detail: "giù" }, 500];
      if (path.includes("/recipes/categories")) return [[], 200];
      return [RESULTS, 200];
    });
    renderScreen();

    await screen.findByText("Pasta al pomodoro");
    expect(screen.queryByText(/solo testuale/i)).toBeNull();
  });

  // R2. Prima della soglia di `recipe_search.py` la graduatoria semantica conteneva
  // tutto il ricettario per qualunque query, quindi una ricerca non tornava mai
  // vuota e questa frase non si vedeva mai. Adesso può: e «Nessuna ricetta» è un
  // verdetto sul ricettario mentre il fatto riguarda le parole scritte.
  it("una ricerca senza riscontri parla delle parole, non del ricettario", async () => {
    stubRoutedFetch((path) =>
      path.includes("/search-mode") ? [{ semantic: true }, 200] : [[], 200]
    );
    renderScreen();
    await userEvent.type(await screen.findByLabelText("Cerca nel ricettario"), "bulloni");

    expect(await screen.findByText(/Nessuna ricetta con queste parole/)).toBeDefined();
  });

  it("con il filtro acceso dice anche del filtro, che è l'altra cosa da togliere", async () => {
    stubRoutedFetch((path) =>
      path.includes("/search-mode") ? [{ semantic: true }, 200] : [[], 200]
    );
    renderScreen();
    await userEvent.click(
      await screen.findByRole("radio", { name: "Solo quelle che puoi cucinare adesso." })
    );
    await userEvent.type(screen.getByLabelText("Cerca nel ricettario"), "bulloni");

    // «fra quelle che puoi cucinare» appartiene solo al caso con entrambi: cercare
    // «togli il filtro» passerebbe anche sulla frase del solo filtro, che è quella
    // mostrata per i 180 ms del debounce, quando la query è ancora vuota
    expect(await screen.findByText(/fra quelle che puoi cucinare/)).toBeDefined();
  });

  it("col solo filtro acceso il vuoto parla della dispensa, non del ricettario", async () => {
    // dispensa vuota e filtro acceso: il ricettario è pieno, non c'è niente di
    // cucinabile. Senza questa frase il vuoto sembrerebbe colpa del ricettario, e
    // l'unica cosa da fare — togliere il filtro — non sarebbe nominata.
    stubRoutedFetch((path) =>
      path.includes("/search-mode") ? [{ semantic: true }, 200] : [[], 200]
    );
    renderScreen();
    await userEvent.click(
      await screen.findByRole("radio", { name: "Solo quelle che puoi cucinare adesso." })
    );

    expect(
      await screen.findByText(
        "Niente che puoi cucinare con quel che hai in dispensa: alza la soglia, o " +
          "scegli «Tutte» nella scala per vedere tutto il ricettario."
      )
    ).toBeDefined();
  });

  // Finding 1c della revisione finale: a un gradino di mezzo «alza la soglia» è
  // ancora un consiglio eseguibile, e deve comparire insieme a «Tutte».
  it("con un gradino di mezzo il vuoto offre sia di alzare la soglia sia «Tutte»", async () => {
    stubRoutedFetch((path) =>
      path.includes("/search-mode") ? [{ semantic: true }, 200] : [[], 200]
    );
    renderScreen();
    await userEvent.click(
      await screen.findByRole("radio", { name: "Al massimo 2 ingredienti da comprare." })
    );

    const messaggio = await screen.findByText(/Niente da cucinare comprando al massimo/);
    expect(messaggio.textContent).toMatch(/alza la soglia/);
    expect(messaggio.textContent).toMatch(/«Tutte» nella scala/);
  });

  // In cima alla scala non esiste un gradino più alto: «alza la soglia» sarebbe un
  // consiglio impossibile da seguire, non solo superfluo, ed è esattamente il tipo
  // di difetto che questo progetto tratta come tale invece che come una sfumatura.
  it("al gradino più alto il vuoto non consiglia di alzare la soglia, ma offre comunque una via d'uscita", async () => {
    stubRoutedFetch((path) =>
      path.includes("/search-mode") ? [{ semantic: true }, 200] : [[], 200]
    );
    renderScreen();
    await userEvent.click(
      await screen.findByRole("radio", { name: "Al massimo 3 ingredienti da comprare." })
    );

    const messaggio = await screen.findByText(/Niente da cucinare comprando al massimo/);
    expect(messaggio.textContent).not.toMatch(/alza la soglia/);
    expect(messaggio.textContent).toMatch(/«Tutte» nella scala/);
  });

  // Finding 1a: la casella «solo cucinabili» non esiste più, quindi il vuoto con
  // parole cercate più una soglia non può più dire «togli il filtro» — non c'è
  // nessun filtro da togliere, solo una scala da riportare a «Tutte».
  it("con parole cercate e una soglia il vuoto non parla più di un filtro da togliere", async () => {
    stubRoutedFetch((path) =>
      path.includes("/search-mode") ? [{ semantic: true }, 200] : [[], 200]
    );
    renderScreen();
    await userEvent.click(
      await screen.findByRole("radio", { name: "Al massimo 1 ingrediente da comprare." })
    );
    await userEvent.type(screen.getByLabelText("Cerca nel ricettario"), "bulloni");

    const messaggio = await screen.findByText(/Nessuna ricetta con queste parole/);
    expect(messaggio.textContent).not.toMatch(/togli il filtro/);
    expect(messaggio.textContent).toMatch(/«Tutte» nella scala/);
  });

  it("senza parole cercate il verdetto sul ricettario è quello giusto, e porta a «Nuova»", async () => {
    // l'unico caso in cui «il ricettario è vuoto» è vero: nessuna query, nessun filtro.
    // La via d'uscita è «Nuova» (T3 Consegna 4): l'AI non è più l'ingresso
    stubRoutedFetch((path) =>
      path.includes("/search-mode") ? [{ semantic: true }, 200] : [[], 200]
    );
    renderScreen();

    expect(
      await screen.findByText("Il ricettario è vuoto: scrivi la prima ricetta con «Nuova».")
    ).toBeDefined();
    expect(screen.getByRole("heading", { name: "Nessuna ricetta" })).toBeInTheDocument();
    // senza filtri accesi non c'è niente da azzerare
    expect(screen.queryByRole("button", { name: "Azzera i filtri" })).toBeNull();
  });

  // Pattern 2 delle istruzioni: una ricerca fallita deve dirlo, non sembrare un
  // ricettario vuoto. Una ricerca semantica senza risultati ha esattamente lo
  // stesso aspetto di una ricerca rotta, quindi qui la distinzione conta di più.
  it("una ricerca fallita lo dice, e non sembra un ricettario vuoto", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));
    renderScreen();

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/non sono riuscito/i);
    expect(screen.queryByText(/nessuna ricetta/i)).toBeNull();

    // il campo di ricerca resta utilizzabile: mai un vicolo cieco
    expect(screen.getByLabelText("Cerca nel ricettario")).not.toBeDisabled();
  });

  it("una ricerca fallita offre «Riprova», che riprova davvero", async () => {
    let giu = true;
    stubRoutedFetch((path) => {
      if (path.includes("/recipes/search?")) return giu ? [{ detail: "giù" }, 500] : [RESULTS, 200];
      return CODA_CON_CATEGORIE(path);
    });
    renderScreen();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Non sono riuscito a cercare nel ricettario."
    );
    giu = false;
    await userEvent.click(screen.getByRole("button", { name: "Riprova" }));

    expect(await screen.findByText("Pasta all'aglio")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  // Pattern 3: una risposta lenta e superata non deve sovrascrivere una risposta
  // più recente e già arrivata. Stesso tipo di guardia costata un MAJOR nel
  // Task 18 per AddItemField, qui sulla ricerca del ricettario. La ricerca
  // sul montaggio (query vuota) deve risolversi per conto suo, quindi le due
  // ricerche in gara si distinguono dall'URL, non dall'ordine di chiamata.
  it("una risposta lenta e superata non sovrascrive quella più recente", async () => {
    let releaseSlow: (response: Response) => void = () => {};
    let releaseFast: (response: Response) => void = () => {};
    const fetchMock = vi.fn((url: RequestInfo | URL) => {
      const href = String(url);
      if (href.includes("q=pollo")) {
        return new Promise<Response>((resolve) => { releaseSlow = resolve; });
      }
      if (href.includes("q=pesce")) {
        return new Promise<Response>((resolve) => { releaseFast = resolve; });
      }
      return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderScreen();
    const field = await screen.findByLabelText("Cerca nel ricettario");

    await userEvent.type(field, "pollo");
    await vi.waitFor(() =>
      expect(fetchMock.mock.calls.some(([u]) => String(u).includes("q=pollo"))).toBe(true)
    );

    await userEvent.clear(field);
    await userEvent.type(field, "pesce");
    await vi.waitFor(() =>
      expect(fetchMock.mock.calls.some(([u]) => String(u).includes("q=pesce"))).toBe(true)
    );

    // la rapida arriva prima...
    releaseFast(new Response(JSON.stringify([riga("rf", "Risotto al pesce")]), { status: 200 }));
    expect(await screen.findByText("Risotto al pesce")).toBeDefined();

    // ...e quella lenta, superata, arriva dopo: non deve cambiare nulla
    releaseSlow(new Response(JSON.stringify([riga("rs", "Pollo al forno")]), { status: 200 }));
    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(screen.getByText("Risotto al pesce")).toBeDefined();
    expect(screen.queryByText("Pollo al forno")).toBeNull();
  });

  it("una sessione scaduta durante la ricerca arriva alla QueryCache", async () => {
    // È il punto che App.tsx aggancia per riportare all'accesso. La prima versione
    // di questo schermo catturava il 401 in un .catch locale: l'utente leggeva
    // "ricerca fallita" e restava su uno schermo che non avrebbe mai più
    // funzionato, perché la sessione era finita e nessuno glielo diceva.
    const onError = vi.fn();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 401 })));

    renderScreen(new QueryCache({ onError }));

    await waitFor(() => expect(onError).toHaveBeenCalled());
    expect(onError.mock.calls[0][0]).toBeInstanceOf(UnauthorizedError);
  });

  it("«Nuova» in alto porta al modulo di sempre; l'AI non è più l'ingresso", async () => {
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();

    const nuova = await screen.findByRole("link", { name: "Nuova ricetta" });
    expect(nuova).toHaveAttribute("href", "/ricette/nuova-ai");
    // il nome accessibile comincia con la scritta a video (label-in-name)
    expect(nuova).toHaveTextContent("Nuova");
    expect(screen.queryByRole("link", { name: /Scrivi con l'AI/ })).toBeNull();
  });

  // Task 14, poi D3, poi T3 Consegna 4: la porta verso la coda c'è quando c'è davvero
  // qualcosa da decidere, col fondo ambra e il conteggio nella nota.
  it("quando ci sono ingredienti da abbinare, apre la porta verso la coda", async () => {
    const spy = vi.fn((url: unknown) => {
      const path = String(url);
      if (path.includes("/imports/status")) {
        return Promise.resolve(
          new Response(
            JSON.stringify(
              { fetched: 20, pending_recipes: 3, imported: 17, skipped: 0, pending_terms: 5 }
            ),
            { status: 200 }
          )
        );
      }
      if (path.includes("/recipes/categories")) {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify(RESULTS), { status: 200 }));
    });
    vi.stubGlobal("fetch", spy);
    renderScreen();

    await screen.findByText(/5 ingredienti,/);
    const link = screen.getByRole("link", { name: /Ingredienti da abbinare/ });
    expect(link).toHaveClass("bg-low-tint");
    expect(link).toHaveTextContent(/3 ricette in attesa/);
    expect(link).toHaveAttribute("href", "/ricette/importa");
  });

  // "1 ingredienti da abbinare, 1 ricette in attesa" era il testo con un solo
  // termine e una sola ricetta in attesa: entrambi i plurali sbagliati a uno, lo
  // stesso caso che TermCard.tsx già tratta correttamente riga per riga.
  it("con un solo ingrediente e una sola ricetta usa il singolare per entrambi", async () => {
    const spy = vi.fn((url: unknown) => {
      const path = String(url);
      if (path.includes("/imports/status")) {
        return Promise.resolve(
          new Response(
            JSON.stringify(
              { fetched: 1, pending_recipes: 1, imported: 0, skipped: 0, pending_terms: 1 }
            ),
            { status: 200 }
          )
        );
      }
      if (path.includes("/recipes/categories")) {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify(RESULTS), { status: 200 }));
    });
    vi.stubGlobal("fetch", spy);
    renderScreen();

    await screen.findByText("1 ingrediente, 1 ricetta in attesa");
    expect(screen.getByRole("link", { name: /Ingredienti da abbinare/ })).toHaveTextContent(
      "1 ingrediente, 1 ricetta in attesa"
    );
  });

  it("con la coda vuota la scheda non c'è: la coda si raggiunge dal ☰", async () => {
    // dal giro: la scheda stava in cima anche quando non c'era niente da decidere, e
    // spingeva la prima ricetta sotto la piega. La revisione delle decisioni già
    // prese resta raggiungibile da «Ingredienti da abbinare» nel ☰ (AppHeader)
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();

    await screen.findByText("Pasta al pomodoro");
    expect(screen.queryByRole("link", { name: /Ingredienti da abbinare/ })).toBeNull();
  });

  // «mai un vicolo cieco»: un conteggio che non arriva non si traveste da coda piena,
  // e il ricettario resta; la coda resta raggiungibile dal ☰
  it("se lo stato dell'import non arriva, la scheda non compare e il ricettario resta", async () => {
    const spy = vi.fn((url: unknown) => {
      const path = String(url);
      if (path.includes("/imports/status")) {
        return Promise.resolve(
          new Response(JSON.stringify({ detail: "giù" }), { status: 500 })
        );
      }
      if (path.includes("/recipes/categories")) {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify(RESULTS), { status: 200 }));
    });
    vi.stubGlobal("fetch", spy);
    renderScreen();

    await screen.findByText("Pasta al pomodoro"); // la ricerca è arrivata comunque
    expect(screen.queryByRole("link", { name: /Ingredienti da abbinare/ })).toBeNull();
  });

  it("non riordina: l'ordine è quello che decide il backend", async () => {
    // L'ordinamento nasce da `recipe_search.py`, che mette davanti ciò a cui manca
    // meno. Una ricetta non cucinabile prima di una cucinabile è quindi un ordine
    // legittimo, e il frontend non deve "aggiustarlo": la logica di dominio sta nel
    // backend, ed è quella separazione che rende la porta a Capacitor un involucro.
    // Dati scelti perché *qualunque* riordino lato client cambi l'ordine: per
    // titolo crescente, per mancanti crescenti o per cucinabili prima, Agnello
    // finirebbe davanti. I primi dati che avevo scelto si ordinavano già così da
    // soli, e il test passava anche con un .sort() aggiunto: non aveva denti.
    const backendOrder = [
      riga("z", "Zuppa", { missing: 2, cookable: false, missing_names: ["Farro", "Porri"] }),
      riga("a", "Agnello"),
    ];
    stubRoutedFetch((path) => (path.includes("/recipes/categories") ? [[], 200] : [backendOrder, 200]));
    renderScreen();

    await screen.findByText("Zuppa");
    // dagli indirizzi delle righe: il primo `span` di una riga ora è la miniatura
    const righe = within(screen.getByRole("list", { name: "Ricette trovate" })).getAllByRole("link");
    expect(righe.map((link) => link.getAttribute("href"))).toEqual(["/ricette/z", "/ricette/a"]);
  });

  it("la miniatura mostra la foto, e la riga il tempo totale", async () => {
    stubRoutedFetch(CODA_CON_CATEGORIE);
    const { container } = renderScreen();

    await screen.findByText("Pasta all'aglio");
    // la foto è decorativa (`alt=""`): il titolo è già il nome del collegamento
    const foto = container.querySelector('a[href="/ricette/r1"] img');
    expect(foto).toHaveAttribute("src", "https://example.com/aglio.jpg");
    expect(foto).toHaveAttribute("loading", "lazy");
    expect(screen.getByText("25 min")).toBeInTheDocument();
  });

  it("una ricetta senza foto e senza tempi non si rompe, e ha comunque la miniatura", async () => {
    stubRoutedFetch(CODA_CON_CATEGORIE);
    const { container } = renderScreen();

    expect(await screen.findByText("Pasta al pomodoro")).toBeInTheDocument();
    const senzaFoto = container.querySelector('a[href="/ricette/r2"]')!;
    expect(senzaFoto.querySelector("img")).toBeNull();
    expect(senzaFoto.querySelector("[data-recipe-thumb] svg")).not.toBeNull();
  });

  // Il caso normale, non un'eccezione (spec §6.3): l'immagine viene dal server di
  // origine e non è mai copiata, quindi un 404 dopo un rinominamento a monte, un
  // blocco sul Referer o solo poco segnale in corridoio la fanno fallire. Senza
  // questa gestione la riga mostrerebbe un riquadro vuoto al posto della foto.
  it("una foto che non carica non lascia un buco: resta l'icona del reparto", async () => {
    stubRoutedFetch(CODA_CON_CATEGORIE);
    const { container } = renderScreen();

    await screen.findByText("Pasta all'aglio");
    fireEvent.error(container.querySelector('a[href="/ricette/r1"] img')!);

    expect(container.querySelector('a[href="/ricette/r1"] img')).toBeNull();
    expect(container.querySelector('a[href="/ricette/r1"] [data-recipe-thumb] svg')).not.toBeNull();
    // il titolo resta una volta sola
    expect(screen.getAllByText("Pasta all'aglio")).toHaveLength(1);
  });

  it("i filtri stanno in un pannello chiuso, che «Filtri» apre e richiude", async () => {
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();

    const filtri = await screen.findByRole("button", { name: "Filtri" });
    expect(filtri).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByLabelText("Contiene ingredienti")).not.toBeVisible();

    await userEvent.click(filtri);
    expect(filtri).toHaveAttribute("aria-expanded", "true");
    const campo = screen.getByLabelText("Contiene ingredienti");
    expect(campo).toBeVisible();
    // `aria-controls` nomina il pannello che contiene davvero i filtri
    expect(document.getElementById(filtri.getAttribute("aria-controls")!)).toContainElement(campo);

    await userEvent.click(filtri);
    expect(filtri).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByLabelText("Contiene ingredienti")).not.toBeVisible();
  });

  it("«Filtri» conta categoria e ingredienti, non le parole né la scala", async () => {
    stubRoutedFetch(CON_POMODORO);
    renderScreen();

    await userEvent.type(await screen.findByLabelText("Cerca nel ricettario"), "pasta");
    await userEvent.click(
      screen.getByRole("radio", { name: "Solo quelle che puoi cucinare adesso." })
    );
    expect(screen.getByRole("button", { name: "Filtri" })).toBeInTheDocument();

    await apriFiltri();
    await userEvent.selectOptions(await screen.findByLabelText("Categoria"), "Primi piatti");
    expect(screen.getByRole("button", { name: "Filtri, 1 attivo" })).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Contiene ingredienti"), "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));
    // il numero si sente e si vede
    expect(screen.getByRole("button", { name: "Filtri, 2 attivi" })).toHaveTextContent("Filtri2");
  });

  it("il pannello dice quante ricette rispondono, col totale del server", async () => {
    stubRoutedFetch((path) =>
      path.includes("/recipes/search?")
        ? [RESULTS, 200, { "X-Total-Count": "42" }]
        : CODA_CON_CATEGORIE(path)
    );
    renderScreen();

    await apriFiltri();
    expect(await screen.findByText("42 ricette")).toBeVisible();
  });

  it("«Azzera» toglie categoria e ingredienti, e lascia parole e scala", async () => {
    const fetchMock = stubRoutedFetch(CON_POMODORO);
    renderScreen();

    await userEvent.type(await screen.findByLabelText("Cerca nel ricettario"), "pasta");
    await userEvent.click(
      screen.getByRole("radio", { name: "Al massimo 2 ingredienti da comprare." })
    );
    await apriFiltri();
    await userEvent.selectOptions(await screen.findByLabelText("Categoria"), "Primi piatti");
    await userEvent.type(screen.getByLabelText("Contiene ingredienti"), "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));

    await userEvent.click(screen.getByRole("button", { name: "Azzera" }));

    expect(screen.getByRole("button", { name: "Filtri" })).toBeInTheDocument();
    expect(screen.getByLabelText("Categoria")).toHaveValue("");
    expect(screen.queryByRole("button", { name: "Togli il filtro su Pomodoro" })).toBeNull();
    await waitFor(() => {
      const ultima = ultimaRicerca(fetchMock);
      expect(ultima).not.toContain("category=");
      expect(ultima).not.toContain("ingredient_id");
      expect(ultima).toContain("q=pasta");
      expect(ultima).toContain("max_missing=2");
    });
  });

  it("«Azzera» non c'è finché non c'è niente da azzerare", async () => {
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();

    await apriFiltri();
    await screen.findByLabelText("Categoria");
    expect(screen.queryByRole("button", { name: "Azzera" })).toBeNull();
  });

  it("i filtri si ricordano finché l'app è aperta: rimontato, lo schermo li ritrova", async () => {
    // tornando da una ricetta lo schermo rinasce (Mattia, 2026-09-29)
    const fetchMock = stubRoutedFetch(CON_POMODORO);
    const primo = renderScreen();

    await userEvent.type(await screen.findByLabelText("Cerca nel ricettario"), "pasta");
    await userEvent.click(
      screen.getByRole("radio", { name: "Al massimo 1 ingrediente da comprare." })
    );
    await apriFiltri();
    await userEvent.selectOptions(await screen.findByLabelText("Categoria"), "Primi piatti");
    await userEvent.type(screen.getByLabelText("Contiene ingredienti"), "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));
    await screen.findByRole("button", { name: "Filtri, 2 attivi" });
    primo.unmount();

    renderScreen();

    expect(await screen.findByLabelText("Cerca nel ricettario")).toHaveValue("pasta");
    expect(
      screen.getByRole("radio", { name: "Al massimo 1 ingrediente da comprare." })
    ).toBeChecked();
    expect(screen.getByRole("button", { name: "Filtri, 2 attivi" })).toBeInTheDocument();
    await waitFor(() => {
      const ultima = ultimaRicerca(fetchMock);
      expect(ultima).toContain("q=pasta");
      expect(ultima).toContain("max_missing=1");
      expect(ultima).toContain("category=Primi+piatti");
      expect(ultima).toContain(`ingredient_id=${POMODORO.id}`);
    });
  });

  it("se la memoria non si legge né si scrive, si parte vuoti e il ricettario funziona", async () => {
    // finestra privata, dati del sito bloccati: il ricordo è una comodità
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloccata");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloccata");
    });
    const fetchMock = stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();

    expect(await screen.findByText("Pasta all'aglio")).toBeInTheDocument();
    expect(screen.getByLabelText("Cerca nel ricettario")).toHaveValue("");
    await userEvent.type(screen.getByLabelText("Cerca nel ricettario"), "aglio");
    await waitFor(() => expect(ultimaRicerca(fetchMock)).toContain("q=aglio"));
  });

  it("il vuoto con dei filtri accesi offre «Azzera i filtri», che li toglie", async () => {
    const fetchMock = stubRoutedFetch((path) => {
      if (path.includes("/ingredients")) return [[POMODORO], 200];
      if (path.includes("/recipes/categories")) return [[], 200];
      if (path.includes("/recipes/search?")) {
        return [path.includes("ingredient_id") ? [] : RESULTS, 200];
      }
      return [{ semantic: true }, 200];
    });
    renderScreen();

    await apriFiltri();
    await userEvent.type(await screen.findByLabelText("Contiene ingredienti"), "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));
    expect(await screen.findByRole("heading", { name: "Nessuna ricetta" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Azzera i filtri" }));

    expect(await screen.findByText("Pasta all'aglio")).toBeInTheDocument();
    await waitFor(() => expect(ultimaRicerca(fetchMock)).not.toContain("ingredient_id"));
  });

  it("il filtro per categoria chiede al backend solo quella categoria", async () => {
    const spy = stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();

    await apriFiltri();
    await userEvent.selectOptions(
      await screen.findByLabelText("Categoria"),
      "Dolci e Desserts"
    );

    await waitFor(() =>
      expect(
        spy.mock.calls.some(([url]) =>
          String(url).includes("category=Dolci+e+Desserts")
        )
      ).toBe(true)
    );
  });

  it("senza categorie nel ricettario il filtro non compare", async () => {
    stubRoutedFetch((path) => {
      if (path.includes("/recipes/categories")) return [[], 200];
      return CODA_CON_CATEGORIE(path);
    });
    renderScreen();

    await screen.findByText("Pasta all'aglio");
    await apriFiltri();
    expect(screen.getByLabelText("Contiene ingredienti")).toBeVisible();
    expect(screen.queryByLabelText("Categoria")).not.toBeInTheDocument();
  });

  it("scegliere un ingrediente filtra il ricettario su di lui", async () => {
    const fetchMock = stubRoutedFetch((path) => {
      if (path.includes("/ingredients")) return [[POMODORO], 200];
      // altrimenti il fallback finirebbe anche sotto /recipes/categories, e il
      // <select> tenterebbe di renderizzare ricette come opzioni
      if (path.includes("/recipes/categories")) return [[], 200];
      return [RESULTS, 200];
    });
    renderScreen();

    await apriFiltri();
    await userEvent.type(await screen.findByLabelText("Contiene ingredienti"), "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));

    await waitFor(() => {
      const ultima = fetchMock.mock.calls.map(([url]) => String(url)).filter((u) => u.includes("/recipes/search")).pop();
      expect(ultima).toContain(`ingredient_id=${POMODORO.id}`);
    });
    expect(screen.getByRole("button", { name: "Togli il filtro su Pomodoro" })).toBeDefined();
  });

  it("togliere il filtro riporta il ricettario intero", async () => {
    const fetchMock = stubRoutedFetch((path) => {
      if (path.includes("/ingredients")) return [[POMODORO], 200];
      // altrimenti il fallback finirebbe anche sotto /recipes/categories, e il
      // <select> tenterebbe di renderizzare ricette come opzioni
      if (path.includes("/recipes/categories")) return [[], 200];
      return [RESULTS, 200];
    });
    renderScreen();

    await apriFiltri();
    await userEvent.type(await screen.findByLabelText("Contiene ingredienti"), "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Togli il filtro su Pomodoro" }));

    await waitFor(() => {
      const ultima = fetchMock.mock.calls.map(([url]) => String(url)).filter((u) => u.includes("/recipes/search")).pop();
      expect(ultima).not.toContain("ingredient_id");
    });
  });

  it("nessun risultato con un ingrediente dice che è il filtro, non il ricettario", async () => {
    // stesso errore corretto in b6ed1d9 dall'altro lato dell'app: «nessuna ricetta»
    // è un verdetto sul ricettario, e quasi sempre riguarda il filtro
    stubRoutedFetch((path) => {
      if (path.includes("/ingredients")) return [[POMODORO], 200];
      if (path.includes("/recipes/search")) return [[], 200];
      return [[], 200];
    });
    renderScreen();

    await apriFiltri();
    await userEvent.type(await screen.findByLabelText("Contiene ingredienti"), "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));

    expect(
      await screen.findByText(/Nessuna ricetta che contenga «Pomodoro»/)
    ).toBeDefined();
  });

  it("due ingredienti li chiede tutti e due, non solo l'ultimo scelto", async () => {
    // il parametro si ripete, e `set` al posto di `append` lascerebbe passare solo
    // l'ultimo: l'elenco a video sarebbe più largo di quello che il filtro promette,
    // e nessuno avrebbe modo di accorgersene se non contando le ricette
    const fetchMock = stubRoutedFetch((path) => {
      if (path.includes("/ingredients")) return [[POMODORO, BASILICO], 200];
      if (path.includes("/recipes/categories")) return [[], 200];
      return [RESULTS, 200];
    });
    renderScreen();

    await apriFiltri();
    const campo = await screen.findByLabelText("Contiene ingredienti");
    await userEvent.type(campo, "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));
    await userEvent.type(campo, "basi");
    await userEvent.click(await screen.findByRole("option", { name: /Basilico/ }));

    await waitFor(() => {
      const ultima = ultimaRicerca(fetchMock);
      expect(ultima).toContain(`ingredient_id=${POMODORO.id}`);
      expect(ultima).toContain(`ingredient_id=${BASILICO.id}`);
    });
  });

  it("togliere un ingrediente lascia in piedi gli altri", async () => {
    const fetchMock = stubRoutedFetch((path) => {
      if (path.includes("/ingredients")) return [[POMODORO, BASILICO], 200];
      if (path.includes("/recipes/categories")) return [[], 200];
      return [RESULTS, 200];
    });
    renderScreen();

    await apriFiltri();
    const campo = await screen.findByLabelText("Contiene ingredienti");
    await userEvent.type(campo, "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));
    await userEvent.type(campo, "basi");
    await userEvent.click(await screen.findByRole("option", { name: /Basilico/ }));
    await userEvent.click(screen.getByRole("button", { name: "Togli il filtro su Pomodoro" }));

    await waitFor(() => {
      const ultima = ultimaRicerca(fetchMock);
      expect(ultima).not.toContain(POMODORO.id);
      expect(ultima).toContain(`ingredient_id=${BASILICO.id}`);
    });
  });

  it("lo stesso ingrediente scelto due volte resta uno", async () => {
    // due volte lo stesso non stringe niente: sarebbe una pastiglia doppia da
    // togliere due volte, e una condizione ripetuta a vuoto nella query
    stubRoutedFetch((path) => {
      if (path.includes("/ingredients")) return [[POMODORO], 200];
      if (path.includes("/recipes/categories")) return [[], 200];
      return [RESULTS, 200];
    });
    renderScreen();

    await apriFiltri();
    const campo = await screen.findByLabelText("Contiene ingredienti");
    await userEvent.type(campo, "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));
    await userEvent.type(campo, "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));

    expect(screen.getAllByRole("button", { name: "Togli il filtro su Pomodoro" })).toHaveLength(1);
  });

  it("senza risultati nomina tutti gli ingredienti chiesti, e dice che stringono", async () => {
    stubRoutedFetch((path) => {
      if (path.includes("/ingredients")) return [[POMODORO, BASILICO], 200];
      if (path.includes("/recipes/search")) return [[], 200];
      return [[], 200];
    });
    renderScreen();

    await apriFiltri();
    const campo = await screen.findByLabelText("Contiene ingredienti");
    await userEvent.type(campo, "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));
    await userEvent.type(campo, "basi");
    await userEvent.click(await screen.findByRole("option", { name: /Basilico/ }));

    // entrambi nominati, e la via d'uscita è quella vera: togliere, non aggiungere
    expect(
      await screen.findByText(/Nessuna ricetta che contenga «Pomodoro» e «Basilico»/)
    ).toBeDefined();
    expect(screen.getByText(/togli un ingrediente/)).toBeDefined();
  });

  describe("«Mostra altre»", () => {
    function ricette(quante: number, da = 0) {
      return Array.from({ length: quante }, (_, n) => ({
        ...RESULTS[0], id: `r${da + n}`, title: `Ricetta ${da + n}`,
      }));
    }

    function paginato(path: string): Risposta {
      if (path.includes("/recipes/categories")) return [[], 200];
      if (path.includes("/recipes/search-mode")) return [{ semantic: true }, 200];
      const offset = Number(new URL(path, "http://x").searchParams.get("offset") ?? 0);
      // la seconda pagina ripete l'ultima della prima: è quel che fa un inserimento
      // sopra la pagina mentre l'import gira
      return offset === 0 ? [ricette(30), 200] : [ricette(5, 29), 200];
    }

    it("porta la pagina dopo, senza doppioni, e sparisce quando non ce ne sono altre", async () => {
      const fetchMock = stubRoutedFetch(paginato);
      renderScreen();
      await screen.findByText("Ricetta 29");

      await userEvent.click(screen.getByRole("button", { name: "Mostra altre" }));

      expect(await screen.findByText("Ricetta 33")).toBeDefined();
      expect(ultimaRicerca(fetchMock)).toContain("offset=30");
      expect(screen.getAllByText("Ricetta 29")).toHaveLength(1);
      expect(screen.queryByRole("button", { name: "Mostra altre" })).toBeNull();
    });

    it("chiede sempre la stessa misura di pagina che usa per decidere se ce n'è un'altra", async () => {
      const fetchMock = stubRoutedFetch(paginato);
      renderScreen();
      await screen.findByText("Ricetta 29");
      expect(ultimaRicerca(fetchMock)).toContain("limit=30");
    });

    it("con meno di una pagina non la offre", async () => {
      stubRoutedFetch(CODA_CON_CATEGORIE);
      renderScreen();
      await screen.findByText("Pasta all'aglio");
      expect(screen.queryByRole("button", { name: "Mostra altre" })).toBeNull();
    });

    // Col totale del server (T3 Consegna 4) «Mostra altre» sa se ne mancano: prima una
    // pagina piena che era anche l'ultima offriva un tocco che portava una pagina vuota.
    it("col totale del server, «Mostra altre» c'è finché non sono arrivate tutte", async () => {
      stubRoutedFetch((path) => {
        const [body, status] = paginato(path);
        return path.includes("/recipes/search?")
          ? [body, status, { "X-Total-Count": "34" }]
          : [body, status];
      });
      renderScreen();
      await screen.findByText("Ricetta 29");

      await userEvent.click(screen.getByRole("button", { name: "Mostra altre" }));

      expect(await screen.findByText("Ricetta 33")).toBeDefined();
      expect(screen.queryByRole("button", { name: "Mostra altre" })).toBeNull();
    });

    it("col totale del server, una pagina piena che è anche l'ultima non la offre", async () => {
      stubRoutedFetch((path) =>
        path.includes("/recipes/search?")
          ? [ricette(30), 200, { "X-Total-Count": "30" }]
          : paginato(path)
      );
      renderScreen();
      await screen.findByText("Ricetta 29");
      expect(screen.queryByRole("button", { name: "Mostra altre" })).toBeNull();
    });

    it("se la pagina dopo fallisce, le ricette restano e si può riprovare", async () => {
      stubRoutedFetch((path) => {
        if (path.includes("offset=30")) return [{ detail: "giù" }, 500];
        return paginato(path);
      });
      renderScreen();
      await screen.findByText("Ricetta 29");

      await userEvent.click(screen.getByRole("button", { name: "Mostra altre" }));

      expect(await screen.findByText("Non sono riuscito a caricarne altre.")).toBeDefined();
      expect(screen.getByText("Ricetta 0")).toBeDefined();
      expect(screen.queryByText(/Non sono riuscito a cercare/)).toBeNull();
      expect(screen.getByRole("button", { name: "Mostra altre" })).toBeDefined();
    });
  });
});
```

(54 test: i 43 di prima del task, più 11 nuovi — «la scala ha un'etichetta visibile», «Riprova» che riprova, «Nuova», il pannello che si apre e si richiude, il conto di «Filtri», il totale nel pannello, «Azzera», «Azzera» assente, il ricordo, la memoria rotta, «Azzera i filtri» nel vuoto.)

In `frontend/src/components/ui/Button.test.tsx`, dentro `describe("Button", …)`, dopo il test «è type=button se non si dice altro…», aggiungi:

```tsx
  it("chi apre un pannello dice se è aperto e quale apre", () => {
    // i «Filtri» del ricettario (T3 Consegna 4): il pannello è in linea, sotto la barra
    render(<Button aria-expanded={false} aria-controls="pannello">Filtri</Button>);
    const button = screen.getByRole("button", { name: "Filtri" });
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button).toHaveAttribute("aria-controls", "pannello");
  });
```

In `frontend/src/features/recipes/MissingBudgetFilter.test.tsx`, dentro `describe("MissingBudgetFilter", …)`, in fondo:

```tsx
  it("ha un'etichetta visibile: «Cosa posso cucinare»", () => {
    // dal giro: la scala non aveva un'etichetta che si vedesse, e «+2» da solo non è una
    // domanda. Che si veda davvero (non `sr-only`) lo misura anche l'e2e
    render(<MissingBudgetFilter value={null} onChange={vi.fn()} />);
    expect(screen.getByRole("group", { name: "Cosa posso cucinare" })).toBeInTheDocument();
    expect(screen.getByText("Cosa posso cucinare")).not.toHaveClass("sr-only");
  });
```

- [ ] **Step 2: Farli fallire**

Run: `npx vitest run src/features/recipes/RecipeBookScreen.test.tsx src/components/ui/Button.test.tsx src/features/recipes/MissingBudgetFilter.test.tsx`
Expected: FAIL — nel ricettario falliscono i test che cercano «Hai tutto», «Manca: Pomodoro», «Nuova ricetta», «Filtri», «Ricette trovate», la miniatura, «Cosa posso cucinare», «Azzera», l'`EmptyState` e l'`ErrorState` (e quelli sulla scheda della coda vuota, che oggi c'è). `Button` non passa `aria-controls`; la legenda di `MissingBudgetFilter` è «Quanto posso comprare» e `sr-only`.

- [ ] **Step 3: `Button` apre un pannello**

In `frontend/src/components/ui/Button.tsx` (com'è dopo il Piano 1, che ha già aggiunto `"aria-expanded"?: boolean` e `"aria-pressed"?: boolean` al tipo `Common` e li passa al `<button>`): manca solo `aria-controls`. Prima guarda, da `<worktree>/frontend`:

```bash
grep -n '"aria-expanded"\|"aria-controls"' src/components/ui/Button.tsx
```

1. Se `"aria-expanded"?: boolean;` **non** c'è nel tipo `Common` (il Piano 1 è cambiato), aggiungilo come sotto, insieme ad `aria-controls`; se c'è, aggiungi solo `aria-controls`. Nel tipo `Common`, subito dopo la riga `"aria-expanded"?: boolean;` (o, se manca, dopo `"aria-describedby"?: string;`):
   ```tsx
     /** Il pannello che questo pulsante apre e chiude (i «Filtri» del ricettario, T3
      * Consegna 4), accanto ad `aria-expanded`. Passa così com'è. */
     "aria-controls"?: string;
   ```
2. Nel `<button>` che il componente disegna, subito dopo la riga `aria-expanded={props["aria-expanded"]}` (o, se manca, accanto all'attributo `aria-describedby`, qualunque sia la sua espressione, aggiungendo anche quella riga), aggiungi:
   ```tsx
           aria-controls={props["aria-controls"]}
   ```
   Un attributo mai scritto due volte: se `grep` ne trova già uno, non ripeterlo.

- [ ] **Step 4: «Cosa posso cucinare», a video**

In `frontend/src/features/recipes/MissingBudgetFilter.tsx`, le righe:

```tsx
      {/* cinque radio senza gruppo, letti a voce, sono cinque scelte senza domanda */}
      <legend className="sr-only">Quanto posso comprare</legend>
```

diventano:

```tsx
      {/* cinque radio senza gruppo, letti a voce, sono cinque scelte senza domanda; e
          dal giro, la domanda si deve anche vedere (T3 Consegna 4) */}
      <legend className="pt-3 pb-1.5 text-sm font-medium text-ink-soft">Cosa posso cucinare</legend>
```

- [ ] **Step 5: Il pannello**

Crea `frontend/src/features/recipes/RecipeFiltersPanel.tsx`:

```tsx
import { IngredientPicker } from "../../components/IngredientPicker";
import { Button } from "../../components/ui/Button";
import { IconClearAll, IconX } from "../../components/ui/icons";
import type { Ingredient } from "../../domain/types";

/** Il pannello «Filtri» del ricettario (spec T3 §4.5): categoria e ingredienti, quante
 * ricette rispondono, e «Azzera». In linea sotto la barra e non un foglio sopra l'elenco:
 * aperto, si vede ancora cosa cambia sotto.
 *
 * Resta montato anche chiuso (`hidden`): un ingrediente scritto a metà non si perde
 * richiudendolo, e `aria-controls` di «Filtri» punta sempre a un elemento che c'è. La
 * scala non sta qui: è sempre a video, e non conta come filtro. */
export function RecipeFiltersPanel({
  id,
  open,
  categories,
  category,
  onCategory,
  ingredients,
  onPick,
  onRemove,
  count,
  onReset,
}: {
  id: string;
  open: boolean;
  /** le categorie presenti nel ricettario: un filtro che offre voci vuote porta a una
   * schermata vuota */
  categories: string[];
  category: string;
  onCategory: (category: string) => void;
  ingredients: Ingredient[];
  onPick: (ingredient: Ingredient) => void;
  onRemove: (id: string) => void;
  /** «N ricette», «Cerco…», o `null` quando non si sa */
  count: string | null;
  /** assente quando non c'è niente da azzerare: allora «Azzera» non c'è */
  onReset?: () => void;
}) {
  return (
    <div id={id} hidden={!open}>
      <div className="mt-2 flex flex-col gap-3 rounded-2xl bg-card p-3">
        {categories.length > 0 && (
          <label className="text-sm font-medium text-ink-soft">
            Categoria
            <select
              aria-label="Categoria"
              value={category}
              onChange={(e) => onCategory(e.target.value)}
              className="mt-1.5"
            >
              <option value="">Tutte</option>
              {categories.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
        )}

        {/* il campo resta a video anche con qualcosa già scelto: gli ingredienti si
            sommano, e un campo che sparisce al primo tocco direbbe il contrario */}
        <IngredientPicker
          label="Contiene ingredienti"
          failureNote="Puoi comunque cercare per parole qui sopra."
          kind="food"
          onPick={onPick}
        />

        {ingredients.length > 0 && (
          <ul className="flex flex-wrap items-center gap-2">
            {ingredients.map((chosen) => (
              <li
                key={chosen.id}
                className="flex items-center gap-1 rounded-card bg-brand-tint pr-1 pl-3"
              >
                <span className="min-w-0 truncate text-sm text-brand">{chosen.display_name}</span>
                {/* la stessa X con cui si toglie una voce dalla dispensa, e per la stessa
                    ragione il nome accessibile nomina l'ingrediente: su tre pastiglie
                    «Togli» ripetuto identico non dice quale si sta togliendo */}
                <button
                  type="button"
                  aria-label={`Togli il filtro su ${chosen.display_name}`}
                  onClick={() => onRemove(chosen.id)}
                  className="flex size-11 shrink-0 items-center justify-center rounded-full text-brand"
                >
                  <IconX aria-hidden="true" className="size-4" stroke={2} />
                </button>
              </li>
            ))}
          </ul>
        )}

        {(count !== null || onReset) && (
          <div className="flex min-h-11 items-center justify-between gap-3">
            <p className="text-sm text-ink-soft">{count}</p>
            {onReset && (
              <Button variant="ghost" icon={IconClearAll} onClick={onReset}>
                Azzera
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Lo schermo, riscritto**

Sostituisci **tutto** `frontend/src/features/recipes/RecipeBookScreen.tsx` con:

```tsx
import { useEffect, useId, useState } from "react";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { RecipeRow } from "./RecipeRow";
import { RecipeFiltersPanel } from "./RecipeFiltersPanel";
import { MissingBudgetFilter } from "./MissingBudgetFilter";
import { MAX_BUDGET } from "./missingBudget";
import { fetchCategories, fetchSearchMode, nextPageOffset, searchRecipes } from "./api";
import {
  activeFilterCount,
  filtersButtonName,
  loadFilters,
  resultsLabel,
  saveFilters,
  type RecipeFilters,
} from "./recipeFilters";
import { fetchImportStatus } from "../recipe-import/api";
import { useDebounced } from "../../hooks/useDebounced";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorState } from "../../components/ui/ErrorState";
import { Screen } from "../../components/ui/Screen";
import { SectionEntryCard } from "../../components/ui/SectionEntryCard";
import {
  IconAdjustmentsHorizontal,
  IconClearAll,
  IconPencilPlus,
  IconSearch,
} from "../../components/ui/icons";
import type { Ingredient } from "../../domain/types";

const DEBOUNCE_MS = 180;

/** «A», «B» e «C»: la virgola fra i primi e la «e» prima dell'ultimo, come si
 * scrive un elenco. Con «e» dappertutto tre ingredienti si leggono come una
 * filastrocca, e questo messaggio è già lungo di suo. */
function elenco(names: string[]): string {
  const quoted = names.map((name) => `«${name}»`);
  if (quoted.length <= 1) return quoted.join("");
  return `${quoted.slice(0, -1).join(", ")} e ${quoted[quoted.length - 1]}`;
}

/** Come si nomina la soglia dentro le frasi degli altri rami.
 *
 * Un posto solo: quattro rami che se la scrivono a mano si scollano al primo cambio
 * di parole, e il primo a scollarsi sarebbe quello che si legge meno spesso.
 */
function frammentoSoglia(maxMissing: number | null): string {
  if (maxMissing === null) return "";
  if (maxMissing === 0) return " fra quelle che puoi cucinare adesso";
  if (maxMissing === 1) return " fra quelle a cui manca al massimo 1 ingrediente";
  return ` fra quelle a cui mancano al massimo ${maxMissing} ingredienti`;
}

/** Perché non c'è niente da mostrare: le parole cercate e i filtri, un caso per ciascuno.
 *
 * «Nessuna ricetta» è un verdetto sul ricettario, e il ricettario del seme ne ha 26:
 * con la soglia semantica di `recipe_search.py` una risposta vuota è diventata
 * raggiungibile per la prima volta, e quasi sempre riguarda le parole cercate o il
 * filtro, non il ricettario. È lo stesso errore che b6ed1d9 ha corretto nel pannello
 * del catalogo («con queste parole», non «in catalogo»), dall'altro lato dell'app.
 * Dove la via d'uscita è scrivere una ricetta, la frase porta a «Nuova» (T3 Consegna 4):
 * l'AI non è più l'ingresso del modulo.
 */
function emptyMessage({
  query,
  maxMissing,
  category,
  ingredientNames,
}: {
  query: string;
  maxMissing: number | null;
  category: string;
  ingredientNames: string[];
}): string {
  const searched = query.trim() !== "";
  if (ingredientNames.length > 0) {
    return (
      `Nessuna ricetta che contenga ${elenco(ingredientNames)}` +
      `${searched ? " con queste parole" : ""}${category ? ` in «${category}»` : ""}` +
      `${frammentoSoglia(maxMissing)}: ` +
      // la via d'uscita è quella vera, e al plurale non è la stessa: ogni
      // ingrediente in più stringe, quindi si esce togliendone uno, non cambiandoli
      (ingredientNames.length === 1
        ? "togli il filtro, o provane un altro."
        : "togli un ingrediente — devono esserci tutti perché una ricetta compaia.")
    );
  }
  if (category) {
    const withSearchFragment = searched ? " con queste parole" : "";
    return (
      `Nessuna ricetta in «${category}»${withSearchFragment}${frammentoSoglia(maxMissing)}: ` +
      "scegli «Tutte» fra le categorie per vedere il resto del ricettario."
    );
  }
  if (searched && maxMissing !== null) {
    return (
      `Nessuna ricetta con queste parole${frammentoSoglia(maxMissing)}: ` +
      "scegli «Tutte» nella scala, o prova con altre parole."
    );
  }
  if (searched) {
    return "Nessuna ricetta con queste parole: provane altre, o scrivine una con «Nuova».";
  }
  if (maxMissing === 0) {
    return (
      "Niente che puoi cucinare con quel che hai in dispensa: alza la soglia, o " +
      "scegli «Tutte» nella scala per vedere tutto il ricettario."
    );
  }
  if (maxMissing !== null) {
    // in cima alla scala non c'è più una soglia da alzare: offrire quel
    // consiglio lì sarebbe impossibile da seguire, non solo inutile
    const wayOut =
      maxMissing === MAX_BUDGET
        ? "scegli «Tutte» nella scala per vedere tutto il ricettario."
        : "alza la soglia, o scegli «Tutte» nella scala per vedere tutto il ricettario.";
    return (
      `Niente da cucinare comprando al massimo ${maxMissing === 1 ? "1 cosa" : `${maxMissing} cose`}: ` +
      wayOut
    );
  }
  return "Il ricettario è vuoto: scrivi la prima ricetta con «Nuova».";
}

function uniqueById<T extends { id: string }>(items: T[]): T[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    if (seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  });
}

/** Il ricettario (T3 Consegna 4, spec §4.5): «Nuova» in alto, la barra di ricerca con
 * «Filtri» accanto, il pannello dei filtri in linea, la scala «Cosa posso cucinare»
 * sempre a video, e le righe compatte. */
export function RecipeBookScreen() {
  // I filtri nascono da quel che l'app ricorda (Mattia, 2026-09-29): tornando da una
  // ricetta lo schermo rinasce, e deve ritrovare parole, scala, categoria e
  // ingredienti. Ogni cambio si riscrive nella sessionStorage (`recipeFilters.ts`).
  const [filters, setFilters] = useState<RecipeFilters>(() => loadFilters());
  useEffect(() => {
    saveFilters(filters);
  }, [filters]);
  const { query, maxMissing, category, ingredients } = filters;
  const ingredientIds = ingredients.map((i) => i.id);
  const debouncedQuery = useDebounced(query, DEBOUNCE_MS);
  const activeCount = activeFilterCount(filters);

  const [panelOpen, setPanelOpen] = useState(false);
  const panelId = useId();

  function update(patch: Partial<RecipeFilters>) {
    setFilters((current) => ({ ...current, ...patch }));
  }

  // Scegliere due volte lo stesso non stringe niente: sarebbe una pastiglia doppia
  // da togliere due volte e una condizione ripetuta a vuoto nella query. Tornando
  // `current` immutato React non ridisegna e nessuna ricerca riparte.
  function addIngredient(picked: Ingredient) {
    setFilters((current) =>
      current.ingredients.some((i) => i.id === picked.id)
        ? current
        : { ...current, ingredients: [...current.ingredients, picked] }
    );
  }

  function removeIngredient(id: string) {
    setFilters((current) => ({
      ...current,
      ingredients: current.ingredients.filter((i) => i.id !== id),
    }));
  }

  // «Azzera» toglie quel che sta nel pannello, e che il numero su «Filtri» conta:
  // categoria e ingredienti. Parole e scala sono sempre a video, e si cambiano da lì.
  function resetFilters() {
    update({ category: "", ingredients: [] });
  }

  // Il termine sta dentro la chiave, e questo fa due cose che una ricerca scritta
  // a mano non fa. La sicurezza sull'ordine diventa strutturale: una risposta
  // superata atterra sotto la propria chiave e non può sovrascrivere risultati più
  // recenti, senza bisogno di guardarla. E l'errore passa dalla QueryCache che
  // App.tsx aggancia al 401: una sessione scaduta riporta all'accesso, invece di
  // diventare un "ricerca fallita" permanente su uno schermo che non funzionerà
  // mai più. La prima versione di questo schermo sbagliava esattamente lì.
  //
  // Una query a pagine (R4): 8.469 ricette non stanno in una. La chiave è la stessa
  // di prima, quindi gli `invalidateQueries({ queryKey: ["recipes"] })` sparsi
  // nell'app continuano a rinfrescarla; e `useArchiveRecipe` ci toglie una ricetta
  // eliminata sapendo che ogni pagina è una `RecipePage`.
  const {
    data,
    isLoading,
    isError,
    isFetchNextPageError,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
    refetch,
    isRefetching,
  } = useInfiniteQuery({
    queryKey: ["recipes", debouncedQuery, maxMissing, category, ingredientIds],
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      searchRecipes({
        query: debouncedQuery,
        maxMissing,
        category,
        ingredientIds,
        offset: pageParam,
      }),
    // da dove parte la pagina dopo, e se ce n'è una: vedi `nextPageOffset` in api.ts
    getNextPageParam: (lastPage, allPages) => nextPageOffset(lastPage, allPages),
  });
  // Un inserimento sopra la pagina (l'import che gira) sposta tutto in giù di uno:
  // l'offset fa vedere un doppione, mai un buco, e il doppione si scarta qui.
  const recipes = uniqueById(data?.pages.flatMap((page) => page.recipes) ?? []);
  // il totale più recente: quello dell'ultima pagina arrivata
  const total = data?.pages.at(-1)?.total ?? null;
  // l'errore di una pagina successiva non cancella quel che è già a video
  const searchFailed = isError && !isFetchNextPageError;

  // le categorie presenti, non tutte quelle possibili: un filtro che offre voci
  // vuote porta a una schermata vuota
  const { data: categories = [] } = useQuery({
    queryKey: ["recipe-categories"],
    queryFn: fetchCategories,
  });

  // Spec §11: quando il modello di embedding non si carica la ricerca resta solo
  // testuale, e va detto con un avviso discreto. Fuori dalla chiave ["recipes"],
  // che il salvataggio di una ricetta invalida: questo non cambia salvando una
  // ricetta, cambia solo quando il backend riparte. Se la rotta non risponde non si
  // mostra niente: un avviso rotto su una cosa che forse funziona è peggio del
  // silenzio.
  const { data: searchMode } = useQuery({
    queryKey: ["search-mode"],
    queryFn: fetchSearchMode,
    staleTime: Infinity,
  });

  // Fuori dalla chiave ["recipes"]: questa non cambia cercando, cambia quando si
  // decide un termine o si scarica un lotto. Se la rotta non risponde la scheda non
  // compare: la coda resta raggiungibile dal ☰.
  const { data: importStatus } = useQuery({
    queryKey: ["import-status"],
    queryFn: fetchImportStatus,
  });
  const pendingTerms = importStatus?.pending_terms ?? 0;

  return (
    <Screen
      title="Ricette"
      action={
        // «Nuova» apre il modulo di sempre (R10), da cui la bozza dell'AI si chiede con
        // «Proponi»: l'AI non è più l'ingresso (spec T3 §4.5). La rotta resta quella.
        // Il nome comincia con la scritta a video (label-in-name)
        <Link
          to="/ricette/nuova-ai"
          aria-label="Nuova ricetta"
          className={`${buttonClasses("secondary")} shrink-0`}
        >
          <IconPencilPlus aria-hidden="true" className="size-[1.1em]" stroke={1.8} />
          Nuova
        </Link>
      }
    >
      {/* solo con qualcosa da decidere (spec §4.5): a coda vuota, o con lo stato che non
          arriva, spingerebbe la prima ricetta sotto la piega per niente. La coda resta
          raggiungibile dal ☰, «Ingredienti da abbinare» */}
      {importStatus && pendingTerms > 0 && (
        <SectionEntryCard
          to="/ricette/importa"
          title="Ingredienti da abbinare"
          note={
            `${pendingTerms === 1 ? "1 ingrediente" : `${pendingTerms} ingredienti`}, ` +
            `${importStatus.pending_recipes === 1 ? "1 ricetta in attesa" : `${importStatus.pending_recipes} ricette in attesa`}`
          }
          pending
        />
      )}

      <div className="flex items-center gap-2">
        <div className="relative min-w-0 flex-1">
          <IconSearch
            aria-hidden="true"
            className="pointer-events-none absolute top-1/2 left-3 size-5 -translate-y-1/2 text-ink-faint"
          />
          <input
            id="recipe-search"
            aria-label="Cerca nel ricettario"
            value={query}
            onChange={(e) => update({ query: e.target.value })}
            placeholder="Cerca un piatto o un ingrediente"
            className="pl-10 text-base"
          />
        </div>
        {/* Un pulsante da solo: icona e testo (spec §2). Il numero dei filtri accesi si
            vede e si sente: nel nome, e in una pastiglia accanto alla scritta */}
        <Button
          icon={IconAdjustmentsHorizontal}
          accessibleName={filtersButtonName(activeCount)}
          aria-expanded={panelOpen}
          aria-controls={panelId}
          onClick={() => setPanelOpen((open) => !open)}
          className="shrink-0"
        >
          Filtri
          {activeCount > 0 && (
            <span className="min-w-5 rounded-full bg-brand px-1.5 text-center text-xs font-semibold text-on-brand">
              {activeCount}
            </span>
          )}
        </Button>
      </div>

      <RecipeFiltersPanel
        id={panelId}
        open={panelOpen}
        categories={categories}
        category={category}
        onCategory={(value) => update({ category: value })}
        ingredients={ingredients}
        onPick={addIngredient}
        onRemove={removeIngredient}
        count={isLoading ? "Cerco…" : searchFailed ? null : resultsLabel(total)}
        onReset={activeCount > 0 ? resetFilters : undefined}
      />

      {/* una constatazione, non un guasto: niente `role`, niente colore d'allarme.
          `=== false` e non `!searchMode?.semantic`, perché "non lo so ancora" e
          "non risponde" non sono "è degradata" */}
      {searchMode?.semantic === false && (
        <p className="pt-2 text-xs text-ink-faint">
          Ricerca solo testuale: trova le parole che scrivi, non i piatti simili.
        </p>
      )}

      <MissingBudgetFilter value={maxMissing} onChange={(value) => update({ maxMissing: value })} />

      {isLoading && <p className="pt-4 text-ink-soft">Cerco…</p>}

      {!isLoading && searchFailed && (
        <ErrorState
          message="Non sono riuscito a cercare nel ricettario."
          onRetry={() => void refetch()}
          retrying={isRefetching}
        />
      )}

      {!isLoading && !searchFailed && recipes.length === 0 && (
        <EmptyState
          title="Nessuna ricetta"
          body={emptyMessage({
            query: debouncedQuery,
            maxMissing,
            category,
            ingredientNames: ingredients.map((i) => i.display_name),
          })}
          action={
            activeCount > 0 ? (
              <Button icon={IconClearAll} onClick={resetFilters}>
                Azzera i filtri
              </Button>
            ) : undefined
          }
        />
      )}

      {!isLoading && !searchFailed && recipes.length > 0 && (
        <ul aria-label="Ricette trovate" className="flex flex-col rounded-2xl bg-card px-3 py-1">
          {recipes.map((recipe) => (
            <RecipeRow key={recipe.id} recipe={recipe} />
          ))}
        </ul>
      )}

      {!isLoading && !searchFailed && hasNextPage && (
        <div className="flex flex-col items-center gap-2 pt-3">
          {/* il bottone resta: riprovare è la via d'uscita, mai un vicolo cieco */}
          {isFetchNextPageError && <Alert>Non sono riuscito a caricarne altre.</Alert>}
          {/* `busy` e non `disabled`: in volo tiene il fuoco (regola dei pulsanti) */}
          <Button onClick={() => void fetchNextPage()} busy={isFetchingNextPage}>
            {isFetchingNextPage ? "Carico…" : "Mostra altre"}
          </Button>
        </div>
      )}
    </Screen>
  );
}
```

- [ ] **Step 7: Il commento di `SectionEntryCard`**

In `frontend/src/components/ui/SectionEntryCard.tsx`, il paragrafo:

```tsx
 * Sempre presente (D3 di docs/prossimi-passi.md). Sparire quando non c'è niente da
 * fare è ciò che rende una sottosezione irraggiungibile proprio quando la si vuole
 * visitare apposta — per sistemare una spesa che non si è spuntata, per rivedere
 * una decisione già presa.
```

diventa:

```tsx
 * Chi la usa decide quando c'è. In Lista e Dispensa, «Sistema la spesa» è sempre
 * presente (D3 di docs/prossimi-passi.md): sparire quando non c'è niente da fare la
 * renderebbe irraggiungibile proprio quando la si vuole visitare apposta, per sistemare
 * una spesa che non si è spuntata. Nel ricettario «Ingredienti da abbinare» compare solo
 * con la coda non vuota (T3 Consegna 4, spec §4.5): lì la sottosezione ha un'altra porta
 * che c'è sempre, la voce del ☰, e da lì si rivedono le decisioni già prese.
```

- [ ] **Step 8: Via quel che non serve più**

Da `<worktree>/frontend`:

```bash
git rm src/features/recipes/RecipeCard.tsx src/features/recipes/RecipeCard.test.tsx src/features/recipes/RecipeBookScreen.lapide.test.tsx src/lib/undo.ts
grep -rn "RecipeCard\|deletedRecipe\|Tombstone\|UNDO_MS\|lib/undo" src
```

Expected: il `grep` non stampa niente. (`RecipeCard.test.tsx` è sostituito da `RecipeRow.test.tsx`, che ne porta le prove; la lapide e i suoi test sono sostituiti dall'avviso e da `useArchiveRecipe.test.tsx`.)

- [ ] **Step 9: Le prove e2e che toccano il filtro aprono «Filtri»**

L'e2e si esegue nel Task 8; qui si cambiano le prove che cercano un campo ora nel pannello.

1. In `frontend/e2e/style.spec.ts`, nella prova «la X di una pastiglia del filtro è un bersaglio da pollice, e la pastiglia si vede», dopo `await page.getByRole("link", { name: "Ricette" }).click();` aggiungi:
   ```ts
     // categoria e ingredienti stanno nel pannello «Filtri» (T3 Consegna 4)
     await page.getByRole("button", { name: /^Filtri/ }).click();
   ```
2. Sempre in `frontend/e2e/style.spec.ts`, in `perOgniLuogo`, nel commento che comincia con `// il dettaglio: la prima scheda del ricettario.`, la parola `(RecipeCard)` diventa `(RecipeRow)`: `sed -i 's/(RecipeCard)/(RecipeRow)/' e2e/style.spec.ts` da `<worktree>/frontend`, poi `grep -n "RecipeCard" e2e/style.spec.ts` non stampa niente.
3. In `frontend/e2e/non-alimentari.spec.ts`, fra `await page.getByRole("link", { name: "Ricette", exact: true }).click();` e `const filtro = page.getByLabel("Contiene ingredienti");` aggiungi:
   ```ts
     // categoria e ingredienti stanno nel pannello «Filtri» (T3 Consegna 4)
     await page.getByRole("button", { name: /^Filtri/ }).click();
   ```

- [ ] **Step 10: Farli passare**

Run: `npx vitest run src/features/recipes src/components/ui src/features/cooking src/features/ai-draft`
Expected: PASS. (`AiDraftScreen.test.tsx` monta il ricettario insieme alla bozza, con risposte `{}` per categorie e stato dell'import: la scheda della coda non compare e il pannello non trova categorie, e il test resta verde.)

- [ ] **Step 11: La suite, il tipo, il lint, la build**

Run: `npx vitest run && npm run typecheck && npm run lint && npm run build`
Expected: PASS; **B + 56** test in **F + 3** file (rispetto al Task 6: +11 del ricettario, +1 di `Button`, +1 di `MissingBudgetFilter`, −7 di `RecipeCard.test.tsx`, −9 di `RecipeBookScreen.lapide.test.tsx`; due file in meno); typecheck, lint e build puliti. Poi `wc -l src/features/recipes/RecipeBookScreen.tsx` e annota il numero per il Task 9.

- [ ] **Step 12: Commit**

```bash
git add -A frontend/src/features/recipes frontend/src/components/ui/Button.tsx frontend/src/components/ui/Button.test.tsx frontend/src/components/ui/SectionEntryCard.tsx frontend/src/lib frontend/e2e/style.spec.ts frontend/e2e/non-alimentari.spec.ts
git commit -m "ricette: il ricettario ridisegnato — «Nuova», «Filtri» col pannello, la scala a video, i filtri ricordati, le righe compatte"
```

---

### Task 8: L'e2e — il ricettario a 375×812 nel browser vero

jsdom non calcola il CSS (quarta lezione di `CLAUDE.md`): che la prima ricetta stia nella prima schermata, che la pagina non scorra di lato, che la miniatura sia 56 px e mostri la tinta mentre la foto carica, che il pannello stia sotto la barra, che ogni testo si legga nei due temi, e che i filtri tornino davvero dopo un giro in una ricetta, lo dice solo un browser. Il seme non ha foto né categorie, e nessuna rotta le scrive: le semina un aiutante nel container del backend, come fa `backend/tests/e2e_import_review.py`.

**Files:**
- Create: `backend/tests/e2e_ricettario.py` (semina e pulizia; non è un test di pytest)
- Create: `backend/tests/test_e2e_ricettario_guard.py`
- Modify: `frontend/e2e/style.spec.ts` (un import in cima; in fondo, un blocco `describe` con sei prove)

**Interfaces:**
- Consumes: i nomi a video del Task 7 («Nuova ricetta», `/^Filtri/`, «Filtri, 1 attivo», «Filtri, 2 attivi», «Ricette trovate», «Cerca nel ricettario», «Categoria», «Contiene ingredienti», il gruppo «Cosa posso cucinare», «Azzera», «Azzera i filtri», «N ricette»); `[data-recipe-thumb]` e `data-dept` (Task 5); le funzioni già nel file `testiIlleggibili`, `fermo`, `tokenDelTema`.
- Produces: `python tests/e2e_ricettario.py seed <etichetta>` stampa in JSON `{"categoria", "conFoto", "senzaFoto", "fotoRotta", "ingrediente"}` (ogni ricetta come `{"id", "title"}`, `ingrediente` il `display_name` del branzino della semina); `clean` toglie tutto quel che il file ha scritto.

- [ ] **Step 1: La guardia dell'aiutante (test che fallisce)**

Crea `backend/tests/test_e2e_ricettario_guard.py`:

```python
"""L'aiutante delle prove e2e del ricettario non parte fuori dallo stack e2e.

`tests/e2e_ricettario.py` scrive e cancella ricette e ingredienti: lanciato nel container
di produzione, `clean` cancellerebbe davvero. Il contrassegno `SPENA_E2E=1` sta solo in
`.env.e2e`; qui si prova che senza, il file esce con errore prima di toccare `app` — cioè
prima di aprire una sessione. Un processo a parte, perché il controllo sta in cima al
modulo, al momento dell'import (come `test_e2e_import_review_guard.py`).
"""

import os
import subprocess
import sys
from pathlib import Path

AIUTANTE = Path(__file__).with_name("e2e_ricettario.py")


def test_senza_il_contrassegno_e2e_non_parte():
    env = {chiave: valore for chiave, valore in os.environ.items() if chiave != "SPENA_E2E"}

    esito = subprocess.run(
        [sys.executable, str(AIUTANTE), "clean"],
        env=env, capture_output=True, text=True, timeout=30,
    )

    assert esito.returncode != 0
    assert "SPENA_E2E=1" in esito.stderr
    assert esito.stdout == ""
```

Run (da `<worktree>/backend`): `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/test_e2e_ricettario_guard.py`
Expected: FAIL — il file `e2e_ricettario.py` non c'è (Python esce con errore, ma `stderr` dice «No such file», non `SPENA_E2E=1`).

- [ ] **Step 2: L'aiutante**

Crea `backend/tests/e2e_ricettario.py`:

```python
"""Semina e pulizia per le prove del ricettario in `frontend/e2e/style.spec.ts` (T3
Consegna 4). Non è un test di pytest.

Il seme dello stack e2e porta ricette senza foto e senza categoria, e nessuna rotta
scrive `image_url` o una categoria nuova (`_check_category` accetta solo quelle che il
ricettario ha già). Le prove della miniatura e del pannello «Filtri» ne hanno bisogno:
questo file scrive tre ricette con le loro righe dal repository vero (`create_recipe`),
e i quattro ingredienti che nominano. Le foto puntano a `https://foto.e2e.invalid/`, un
dominio che non esiste: le serve la prova con `page.route`, e nessuna richiesta esce.

Le tre ricette, tutte nella categoria `E2E ricettario <etichetta>` e con ingredienti che
la dispensa non ha:

- «con foto»: zucchina, carota e branzino principali → reparto `verdura`, mancano 3;
- «senza foto»: branzino principale, zucchina secondaria → reparto `pesce`, mancano 2;
- «foto rotta»: manzo principale → reparto `carne`, manca 1.

Si lancia dentro il container del backend, dove `./backend` è montato su `/app`:

    $E2E exec -T backend python tests/e2e_ricettario.py seed <etichetta>
    $E2E exec -T backend python tests/e2e_ricettario.py clean

`seed` stampa su stdout, in JSON, cosa ha scritto. `clean` toglie ricette e ingredienti
di questo file, anche quelli di un giro interrotto, e si può chiamare prima di seminare.

Scrive e cancella nel database, quindi **si rifiuta di partire fuori dallo stack e2e**:
vuole `SPENA_E2E=1`, che sta solo in `.env.e2e`.

Non si chiama `test_*.py` apposta: pytest non lo raccoglie.
"""

import os
import sys

if os.environ.get("SPENA_E2E") != "1":
    raise SystemExit(
        "e2e_ricettario.py scrive e cancella nel database: gira solo sullo stack "
        "spena-e2e, che porta SPENA_E2E=1 da .env.e2e. Qui manca, e non parto."
    )

import asyncio  # noqa: E402
import json  # noqa: E402

from sqlalchemy import select  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.db.models.ingredient import Ingredient, IngredientCategory  # noqa: E402
from app.db.models.recipe import Recipe  # noqa: E402
from app.repositories.ingredients import create_ingredient, delete_ingredient_if_unused  # noqa: E402
from app.repositories.recipes import create_recipe  # noqa: E402

TITLE_PREFIX = "Ricettario e2e"
# il segno nel nome di ogni ingrediente di questo file: la pulizia li ritrova da qui
NAME_MARK = "e2e-ricettario"
PHOTOS = "https://foto.e2e.invalid"


async def seed(tag: str) -> dict:
    category = f"E2E ricettario {tag}"
    async with SessionLocal() as session:
        made: dict[str, Ingredient] = {}
        for key, department in (
            ("zucchina", IngredientCategory.VERDURA),
            ("carota", IngredientCategory.VERDURA),
            ("branzino", IngredientCategory.PESCE),
            ("manzo", IngredientCategory.CARNE),
        ):
            made[key] = await create_ingredient(
                session,
                name=f"{key} {NAME_MARK} {tag}",
                display_name=f"{key.capitalize()} {NAME_MARK} {tag}",
                category=department,
            )

        async def recipe(title: str, lines: list[tuple[str, str]], image_url: str | None) -> Recipe:
            created = await create_recipe(
                session,
                title=f"{TITLE_PREFIX} {title} {tag}",
                description=None,
                instructions="1. Prova.",
                servings=2,
                source="manual",
                source_ref=None,
                ingredients=[(made[key].id, role, None, None) for key, role in lines],
                embedding=None,
                category=category,
            )
            created.image_url = image_url
            return created

        con_foto = await recipe(
            "con foto",
            [("zucchina", "primary"), ("carota", "primary"), ("branzino", "primary")],
            f"{PHOTOS}/{tag}/buona.png",
        )
        senza_foto = await recipe(
            "senza foto", [("branzino", "primary"), ("zucchina", "secondary")], None
        )
        foto_rotta = await recipe("foto rotta", [("manzo", "primary")], f"{PHOTOS}/{tag}/rotta.png")
        await session.commit()
        return {
            "categoria": category,
            "conFoto": {"id": str(con_foto.id), "title": con_foto.title},
            "senzaFoto": {"id": str(senza_foto.id), "title": senza_foto.title},
            "fotoRotta": {"id": str(foto_rotta.id), "title": foto_rotta.title},
            "ingrediente": made["branzino"].display_name,
        }


async def clean() -> dict:
    async with SessionLocal() as session:
        recipes = list(
            (
                await session.execute(select(Recipe).where(Recipe.title.like(f"{TITLE_PREFIX} %")))
            ).scalars()
        )
        # una cancellazione vera e non l'archivio: sono ricette di prova, e le righe se ne
        # vanno con loro (`cascade`), così gli ingredienti qui sotto tornano liberi
        for recipe in recipes:
            await session.delete(recipe)
        await session.flush()

        ids = list(
            (
                await session.execute(
                    select(Ingredient.id).where(Ingredient.name.like(f"%{NAME_MARK}%"))
                )
            ).scalars()
        )
        # `delete_ingredient_if_unused` e non una cancellazione cieca: se qualcosa li usa
        # ancora, lo si dice invece di rompere un vincolo
        kept = [str(i) for i in ids if not await delete_ingredient_if_unused(session, i)]
        await session.commit()
        return {"recipes": len(recipes), "ingredients": len(ids) - len(kept), "kept": kept}


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "seed" and len(sys.argv) == 3:
        print(json.dumps(asyncio.run(seed(sys.argv[2]))))
    elif command == "clean":
        print(json.dumps(asyncio.run(clean())))
    else:
        raise SystemExit("uso: e2e_ricettario.py seed <etichetta> | clean")


if __name__ == "__main__":
    main()
```

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/test_e2e_ricettario_guard.py`
Expected: PASS.

- [ ] **Step 3: Le sei prove**

In cima a `frontend/e2e/style.spec.ts`, prima della riga `import { readFileSync } from "node:fs";`, aggiungi:

```ts
import { execFileSync } from "node:child_process";
```

In fondo al file aggiungi (il `beforeEach` del file ha già premuto «Entra»; `testiIlleggibili`, `fermo` e `tokenDelTema` sono definiti più sopra nel file):

```ts
// --- T3 Consegna 4: il ricettario a 375×812 ---
//
// Il seme non ha foto né categorie, e nessuna rotta le scrive: le prove che ne hanno
// bisogno seminano tre ricette con `backend/tests/e2e_ricettario.py`, dentro il
// container del backend dello stack e2e (come `import-review.spec.ts`), e le tolgono nel
// `finally`. Le foto stanno su un dominio che non esiste: le serve `page.route`, la buona
// con un PNG vero e la rotta interrotta. Il service worker è bloccato in queste prove,
// così nessuna richiesta d'immagine gli passa accanto.

const RADICE = fileURLToPath(new URL("../..", import.meta.url));
// gli argomenti come elenco: un percorso o un nome di progetto con uno spazio non
// cambiano il comando
const COMPOSE_E2E = [
  "compose",
  "-p",
  process.env.E2E_PROJECT ?? "spena-e2e",
  "-f",
  "docker-compose.yml",
  "-f",
  "docker-compose.e2e.yml",
];

/** Lancia l'aiutante del ricettario nel container del backend e torna la sua ultima riga. */
function aiutanteRicettario(...args: string[]): string {
  const uscita = execFileSync(
    "docker",
    [...COMPOSE_E2E, "exec", "-T", "backend", "python", "tests/e2e_ricettario.py", ...args],
    { cwd: RADICE, encoding: "utf8" }
  );
  return uscita.trim().split("\n").pop() ?? "";
}

type RicettaSeminata = { id: string; title: string };
type RicettarioSeminato = {
  categoria: string;
  conFoto: RicettaSeminata;
  senzaFoto: RicettaSeminata;
  fotoRotta: RicettaSeminata;
  /** il nome a video del branzino della semina: sta in «con foto» e in «senza foto» */
  ingrediente: string;
};

// un PNG di 1×1: la «foto» che `page.route` serve al posto di un server vero
const PNG_1X1 = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
  "base64"
);

/** Semina le tre ricette e serve le loro foto: la buona dopo `trattieni` (se c'è), la
 * rotta mai. Prima di seminare, gli avanzi di un giro interrotto se ne vanno. */
async function seminaRicettario(page: Page, trattieni?: Promise<void>): Promise<RicettarioSeminato> {
  aiutanteRicettario("clean");
  const seminato = JSON.parse(aiutanteRicettario("seed", String(Date.now()))) as RicettarioSeminato;
  await page.route("https://foto.e2e.invalid/**", async (route) => {
    if (route.request().url().endsWith("/rotta.png")) return route.abort();
    if (trattieni) await trattieni;
    return route.fulfill({ contentType: "image/png", body: PNG_1X1 });
  });
  return seminato;
}

/** La pulizia, in un `finally`: `expect.soft` non lancia — un `finally` che lancia
 * nasconderebbe l'errore vero — ma segna la prova fallita, così una ricetta rimasta non
 * passa per un successo silenzioso. */
function pulisciRicettario() {
  try {
    aiutanteRicettario("clean");
  } catch (guasto) {
    expect.soft(false, `pulizia: non sono riuscito a togliere le ricette seminate (${guasto})`).toBe(true);
  }
}

/** Il collegamento di una riga del ricettario: il suo nome comincia col titolo. */
function rigaDi(page: Page, titolo: string): Locator {
  return page
    .getByRole("list", { name: "Ricette trovate" })
    .getByRole("link", { name: new RegExp(`^${titolo}`) });
}

/** Il ricettario col pannello aperto sulla categoria della semina: tre ricette, e solo loro. */
async function soloLaSemina(page: Page, seminato: RicettarioSeminato) {
  await page.goto("/ricette");
  await page.getByRole("button", { name: /^Filtri/ }).click();
  await page.getByLabel("Categoria").selectOption(seminato.categoria);
  await expect(page.getByText("3 ricette", { exact: true })).toBeVisible();
}

test.describe("il ricettario a 375px (T3 Consegna 4)", () => {
  test.use({ viewport: { width: 375, height: 812 }, serviceWorkers: "block" });

  // il `beforeEach` del file preme «Entra» e non aspetta la risposta: un `page.goto`
  // subito dopo interromperebbe l'accesso. Si aspetta la barra delle schede, che c'è
  // solo da dentro
  test.beforeEach(async ({ page }) => {
    await expect(page.getByRole("link", { name: "Ricette", exact: true })).toBeVisible();
  });

  test("la prima ricetta sta nella prima schermata, sopra la barra delle schede", async ({
    page,
  }) => {
    // dal giro: «i filtri occupano tutta la prima schermata: la prima ricetta è sotto la
    // piega». Con i filtri nel pannello chiuso, la prima riga si vede intera all'apertura
    await page.goto("/ricette");
    const prima = page.getByRole("list", { name: "Ricette trovate" }).getByRole("link").first();
    await expect(prima).toBeVisible();
    const riga = (await prima.boundingBox())!;
    const schede = (await page.getByRole("navigation").boundingBox())!;
    expect(riga.y, "la prima ricetta comincia fuori dalla finestra").toBeGreaterThanOrEqual(0);
    expect(riga.y + riga.height, "la prima ricetta va oltre la finestra").toBeLessThanOrEqual(812);
    expect(riga.y + riga.height, "la prima ricetta finisce sotto la barra delle schede").toBeLessThanOrEqual(
      schede.y
    );
    // «Nuova» e «Filtri»: bersagli da pollice
    for (const controllo of [
      page.getByRole("link", { name: "Nuova ricetta" }),
      page.getByRole("button", { name: /^Filtri/ }),
    ]) {
      const box = (await controllo.boundingBox())!;
      expect(box.height).toBeGreaterThanOrEqual(44);
      expect(box.width).toBeGreaterThanOrEqual(44);
    }
    // una prova a occhio per chi rivede: la cartella è quella dei risultati di Playwright
    await page.screenshot({ path: test.info().outputPath("ricettario-375.png") });
  });

  test("il ricettario non scorre di lato, nemmeno col pannello aperto e un ingrediente scelto", async ({
    page,
  }) => {
    // stringhe e non funzioni: questo file non ha la libreria DOM
    const nonScorreDiLato = async (quando: string) => {
      await page.waitForLoadState("networkidle");
      const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
      const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
      expect(scrollWidth, `il ricettario scorre di lato ${quando}`).toBeLessThanOrEqual(clientWidth);
    };
    await page.goto("/ricette");
    await expect(page.getByRole("list", { name: "Ricette trovate" })).toBeVisible();
    await nonScorreDiLato("a pannello chiuso");

    await page.getByRole("button", { name: /^Filtri/ }).click();
    await page.getByLabel("Contiene ingredienti").fill("pomodo");
    await page.getByRole("option", { name: /^Pomodoro\b/ }).click();
    await expect(page.getByRole("button", { name: "Togli il filtro su Pomodoro" })).toBeVisible();
    await nonScorreDiLato("col pannello aperto e un ingrediente scelto");
  });

  test("la miniatura: la foto, e sotto l'icona del reparto principale mentre carica o se manca", async ({
    page,
  }) => {
    // due `docker compose exec` oltre al browser: i 30 secondi di default non bastano su
    // una macchina carica
    test.setTimeout(120_000);
    // la foto buona si trattiene finché la prova non ha guardato la miniatura «mentre
    // carica»: dal giro, era un rettangolo bianco
    let rilascia: () => void = () => {};
    const trattenuta = new Promise<void>((resolve) => {
      rilascia = resolve;
    });
    try {
      const seminato = await seminaRicettario(page, trattenuta);
      await soloLaSemina(page, seminato);
      const mini = (titolo: string) => rigaDi(page, titolo).locator("[data-recipe-thumb]");

      for (const titolo of [seminato.conFoto.title, seminato.senzaFoto.title, seminato.fotoRotta.title]) {
        const box = (await mini(titolo).boundingBox())!;
        expect(box.width, titolo).toBeCloseTo(56, 0);
        expect(box.height, titolo).toBeCloseTo(56, 0);
      }

      // mentre la foto carica: sotto si vede già l'icona del reparto, sulla sua tinta
      const conFoto = mini(seminato.conFoto.title);
      await expect(conFoto).toHaveAttribute("data-dept", "verdura");
      await expect(conFoto.locator("svg.tabler-icon-carrot")).toBeVisible();
      await expect(conFoto).toHaveCSS("background-color", tokenDelTema("dept-peach"));
      rilascia();
      const foto = conFoto.locator("img");
      await expect
        .poll(() => foto.evaluate((el) => el.naturalWidth as number), { message: "la foto non arriva" })
        .toBeGreaterThan(0);
      await expect(foto).toBeVisible();

      // senza foto: l'icona del pesce, sul suo azzurro
      const senzaFoto = mini(seminato.senzaFoto.title);
      await expect(senzaFoto.locator("img")).toHaveCount(0);
      await expect(senzaFoto).toHaveAttribute("data-dept", "pesce");
      await expect(senzaFoto.locator("svg.tabler-icon-fish")).toBeVisible();
      await expect(senzaFoto).toHaveCSS("background-color", tokenDelTema("dept-blue"));

      // la foto che non carica se ne va, e resta l'icona della carne, sul suo rosa
      const fotoRotta = mini(seminato.fotoRotta.title);
      await expect(fotoRotta.locator("img")).toHaveCount(0);
      await expect(fotoRotta).toHaveAttribute("data-dept", "carne");
      await expect(fotoRotta.locator("svg.tabler-icon-meat")).toBeVisible();
      await expect(fotoRotta).toHaveCSS("background-color", tokenDelTema("dept-pink"));
    } finally {
      rilascia();
      pulisciRicettario();
    }
  });

  test("il pannello Filtri si apre sotto la barra, conta i risultati, e «Azzera» li toglie", async ({
    page,
  }) => {
    test.setTimeout(120_000);
    try {
      const seminato = await seminaRicettario(page);
      await page.goto("/ricette");
      const campo = page.getByLabel("Cerca nel ricettario");
      const filtri = page.getByRole("button", { name: /^Filtri/ });
      await expect(filtri).toHaveAttribute("aria-expanded", "false");
      await expect(page.getByLabel("Contiene ingredienti")).toBeHidden();

      // «Filtri» sta accanto al campo, sulla stessa riga
      const boxCampo = (await campo.boundingBox())!;
      const boxFiltri = (await filtri.boundingBox())!;
      expect(
        Math.abs(boxFiltri.y + boxFiltri.height / 2 - (boxCampo.y + boxCampo.height / 2)),
        "«Filtri» va a capo"
      ).toBeLessThan(2);
      expect(boxFiltri.x).toBeGreaterThanOrEqual(boxCampo.x + boxCampo.width - 1);

      await filtri.click();
      await expect(filtri).toHaveAttribute("aria-expanded", "true");
      const pannello = page.locator(`[id="${await filtri.getAttribute("aria-controls")}"]`);
      await expect(pannello.getByLabel("Contiene ingredienti")).toBeVisible();
      expect(
        (await pannello.boundingBox())!.y,
        "il pannello non sta sotto la barra"
      ).toBeGreaterThanOrEqual(boxCampo.y + boxCampo.height);

      // la scala resta fuori dal pannello, sempre a video, con un'etichetta che si vede
      // davvero: una legenda `sr-only` sarebbe «visibile» per Playwright ma alta un pixel
      await expect(page.getByRole("group", { name: "Cosa posso cucinare" })).toBeVisible();
      await expect(pannello.getByRole("group", { name: "Cosa posso cucinare" })).toHaveCount(0);
      const etichetta = (await page.getByText("Cosa posso cucinare", { exact: true }).boundingBox())!;
      expect(etichetta.height, "«Cosa posso cucinare» non si vede").toBeGreaterThan(10);

      await pannello.getByLabel("Categoria").selectOption(seminato.categoria);
      await expect(page.getByRole("button", { name: "Filtri, 1 attivo" })).toBeVisible();
      await expect(pannello.getByText("3 ricette", { exact: true })).toBeVisible();
      await expect(rigaDi(page, seminato.fotoRotta.title)).toBeVisible();

      await pannello.getByLabel("Contiene ingredienti").fill(seminato.ingrediente);
      await page.getByRole("option", { name: new RegExp(`^${seminato.ingrediente}`) }).click();
      await expect(page.getByRole("button", { name: "Filtri, 2 attivi" })).toBeVisible();
      await expect(pannello.getByText("2 ricette", { exact: true })).toBeVisible();
      await expect(rigaDi(page, seminato.fotoRotta.title)).toHaveCount(0);

      await pannello.getByRole("button", { name: "Azzera", exact: true }).click();
      await expect(page.getByRole("button", { name: "Filtri", exact: true })).toBeVisible();
      await expect(pannello.getByLabel("Categoria")).toHaveValue("");
      // il ricettario intero: le ricette del seme più le tre della semina
      await expect
        .poll(async () =>
          Number(((await pannello.getByText(/^\d+ ricette$/).textContent()) ?? "0").split(" ")[0])
        )
        .toBeGreaterThan(3);

      await filtri.click();
      await expect(filtri).toHaveAttribute("aria-expanded", "false");
      await expect(page.getByLabel("Contiene ingredienti")).toBeHidden();
    } finally {
      pulisciRicettario();
    }
  });

  test("il contrasto del ricettario nei due temi: righe vere, pannello aperto, e il vuoto", async ({
    page,
  }) => {
    test.setTimeout(120_000);
    try {
      const seminato = await seminaRicettario(page);
      await soloLaSemina(page, seminato);
      await page.getByLabel("Contiene ingredienti").fill(seminato.ingrediente);
      await page.getByRole("option", { name: new RegExp(`^${seminato.ingrediente}`) }).click();
      // il numero su «Filtri» (bianco su verde), la pastiglia dell'ingrediente, il conto,
      // «Azzera», «Manca: …» in rosso e la riga di sotto
      await expect(page.getByRole("button", { name: "Filtri, 2 attivi" })).toBeVisible();
      await expect(rigaDi(page, seminato.senzaFoto.title)).toBeVisible();
      for (const tema of ["light", "dark"] as const) {
        await page.emulateMedia({ colorScheme: tema });
        await fermo(page);
        expect(await testiIlleggibili(page), `ricettario col pannello, tema ${tema}`).toEqual([]);
      }

      // il vuoto, col suo perché e «Azzera i filtri»
      await page.emulateMedia({ colorScheme: "light" });
      await page.getByLabel("Cerca nel ricettario").fill("nessuna ricetta si chiama così");
      await expect(page.getByRole("button", { name: "Azzera i filtri" })).toBeVisible();
      for (const tema of ["light", "dark"] as const) {
        await page.emulateMedia({ colorScheme: tema });
        await fermo(page);
        expect(await testiIlleggibili(page), `ricettario vuoto coi filtri, tema ${tema}`).toEqual([]);
      }
      await page.emulateMedia({ colorScheme: "light" });
    } finally {
      pulisciRicettario();
    }
  });

  test("i filtri sopravvivono al giro in una ricetta: indietro, la scheda Ricette, e un ricaricamento", async ({
    page,
  }) => {
    test.setTimeout(120_000);
    try {
      const seminato = await seminaRicettario(page);
      await page.goto("/ricette");
      await page.getByLabel("Cerca nel ricettario").fill("ricettario e2e");
      await page.getByRole("button", { name: /^Filtri/ }).click();
      await page.getByLabel("Categoria").selectOption(seminato.categoria);
      const due = page.getByRole("radio", { name: "Al massimo 2 ingredienti da comprare." });
      // si tocca la pastiglia, non il radio `sr-only` (vedi la prova della scala più sopra)
      await page.locator("label").filter({ has: due }).locator("span").click();
      await expect(due).toBeChecked();
      // «+2»: alla «senza foto» ne mancano due, alla «foto rotta» uno, alla «con foto» tre
      await expect(rigaDi(page, seminato.senzaFoto.title)).toBeVisible();
      await expect(rigaDi(page, seminato.conFoto.title)).toHaveCount(0);

      const ritrovati = async (come: string) => {
        await expect(page.getByLabel("Cerca nel ricettario"), come).toHaveValue("ricettario e2e");
        await expect(due, come).toBeChecked();
        await expect(page.getByRole("button", { name: "Filtri, 1 attivo" }), come).toBeVisible();
        await expect(rigaDi(page, seminato.senzaFoto.title), come).toBeVisible();
        await expect(rigaDi(page, seminato.fotoRotta.title), come).toBeVisible();
        await expect(rigaDi(page, seminato.conFoto.title), come).toHaveCount(0);
      };

      await rigaDi(page, seminato.senzaFoto.title).click();
      await expect(page.getByRole("heading", { name: seminato.senzaFoto.title })).toBeVisible();
      await page.goBack();
      await ritrovati("tornando indietro");

      await rigaDi(page, seminato.fotoRotta.title).click();
      await expect(page.getByRole("heading", { name: seminato.fotoRotta.title })).toBeVisible();
      await page.getByRole("navigation").getByRole("link", { name: "Ricette", exact: true }).click();
      await ritrovati("dalla scheda Ricette");

      // l'app è ancora aperta: la sessionStorage della scheda resta
      await page.reload();
      await ritrovati("dopo un ricaricamento");
    } finally {
      pulisciRicettario();
    }
  });
});
```

- [ ] **Step 4: Il tipo del file**

Run (da `frontend/`): `npm run typecheck && npm run lint`
Expected: puliti. `tsc -b` compila anche gli e2e (`tsconfig.node.json` include `e2e/`, con i tipi di Node ma senza la libreria DOM: per questo dentro `evaluate` l'elemento non ha tipo, e `Buffer` e `execFileSync` compilano).

- [ ] **Step 5: Lo stack e2e, e l'e2e intera**

Dalla radice del worktree, con i comandi delle Global Constraints: `docker ps --format '{{.Names}}' | grep spena-e2e` (se c'è e non è tuo, aspetta), `cp .env.example .env`, `up -d --build --wait`, il seme `--con-ricette`, poi `(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)`.
Expected: tutti verdi, sei in più della suite di partenza. In particolare `modifica-ricette.spec.ts` (l'avviso «Eliminata: …» sopra la barra delle schede, e «Annulla»), `non-alimentari.spec.ts` e la prova della pastiglia di `style.spec.ts` (che aprono «Filtri»), e i giri dei due temi di `perOgniLuogo` su `/ricette`.

Se una prova si ferma sul `docker compose exec` dell'aiutante (`ENOENT`, o il container non trovato), controlla che lo stack sia stato alzato **dal worktree** e col nome `spena-e2e`: l'aiutante che gira è quello montato nel container. Se il contrasto segnala un testo del ricettario, correggi il colore nel componente (solo token di `index.css`) e non l'asserzione. Se una prova fallisce e lascia dati nello stack, ricrea lo stack da zero prima di rieseguire. Alla fine, sempre:

```bash
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
rm .env
```

- [ ] **Step 6: La suite del backend**

Run (da `<worktree>/backend`): `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q`
Expected: PASS; **P + 13** (`e2e_ricettario.py` non si chiama `test_*.py`: pytest non lo raccoglie).

- [ ] **Step 7: Commit**

```bash
git add backend/tests/e2e_ricettario.py backend/tests/test_e2e_ricettario_guard.py frontend/e2e/style.spec.ts
git commit -m "e2e: il ricettario a 375px — la prima ricetta in vista, la miniatura, il pannello Filtri, il contrasto e i filtri ricordati"
```

---

### Task 9: I documenti

**Files:**
- Modify: `docs/prossimi-passi.md`
- Modify: `next-steps.md`

- [ ] **Step 1: Il paragrafo della consegna**

In `docs/prossimi-passi.md`, nella voce T3, subito prima del paragrafo che comincia con «Dei tre punti di disegno del tema scuro annotati per questa consegna» (se il Piano 1 ci ha messo il suo paragrafo della Consegna 6a, questo va subito dopo il suo, così le consegne restano in ordine), aggiungi:

```markdown
**Consegna 4 (Ricette) fatta il <data di oggi>, sul ramo `night/c4-ricette` (da
`night/c6a-pulsanti`), non ancora in produzione.** Cosa è cambiato: «Nuova» in alto a
destra (la matita col +) apre il modulo di sempre, e «Scrivi con l'AI» non è più
l'ingresso — l'AI resta con «Proponi» dentro il modulo; accanto al campo di ricerca c'è
«Filtri», col numero dei filtri accesi (la categoria uno, ogni ingrediente uno), che apre in
linea un pannello con categoria, ingredienti, quante ricette rispondono e «Azzera»; la scala
sta fuori, sempre a video, con l'etichetta «Cosa posso cucinare»; parole, scala, categoria e
ingredienti si ricordano finché l'app è aperta (`sessionStorage`), così tornando da una
ricetta si ritrovano; le righe sono compatte, con una miniatura da 56 px — la foto, e sotto
l'icona del reparto principale sulla sua tinta, che si vede mentre la foto carica e resta se
non carica —, il titolo su al più due righe, «Hai tutto» o «Manca: …» (tre nomi, poi «e un
altro» / «e altri N»), e sotto categoria · costo · minuti; provenienza e descrizione non
stanno più sulla riga; la scheda «Ingredienti da abbinare» compare solo con la coda non
vuota (il ☰ la raggiunge sempre); il vuoto è un `EmptyState` che dice perché, con «Azzera i
filtri» quando ce ne sono, e il guasto un `ErrorState` con «Riprova»; la lapide del
ricettario è diventata l'avviso unico, «Eliminata: <titolo>» con «Annulla»
(`useArchiveRecipe`, che il dettaglio chiama e che la Consegna 5 riusa). Nel backend: `GET
/recipes/search` manda `X-Total-Count`, contato prima del limite in tutti e due i rami
(sesta lezione di `CLAUDE.md`; sul ramo con le parole è il numero dei candidati che passano
i filtri, dentro la piscina di `CANDIDATE_POOL`), e il corpo resta una lista;
`RecipeSummaryOut` e `RecipeOut` portano `main_department`, il reparto più frequente fra le
righe principali (a parità il primo in ordine alfabetico), da `main_department` in
`app/domain/rules.py`, sulla query che `_requirements_by_recipe` faceva già.
`RecipeBookScreen.tsx` è passato da 461 a <righe> righe: il pannello sta in
`RecipeFiltersPanel`, la riga in `RecipeRow` (al posto di `RecipeCard`), la miniatura in
`RecipeThumb`, i filtri e il loro ricordo in `recipeFilters.ts`.

**Le scelte del piano che Mattia può voler rivedere:** il pannello non si ricorda aperto; «Azzera»
toglie categoria e ingredienti ma non parole né scala, e non c'è quando non c'è niente da
azzerare; la miniatura senza reparto usa l'icona del ricettario su ardesia; «Manca: …» è
rosso (`finished`, il colore che la spec dà all'ingrediente che manca), «Hai tutto» verde;
«Nuova» è un pulsante secondario col nome «Nuova ricetta»; i vuoti che nominavano l'AI ora
portano a «Nuova»; un'eliminazione fallita resta sul dettaglio con l'avviso e «Riprova»;
«Mostra altre» usa il totale e non offre più una pagina vuota dopo una pagina piena che
era l'ultima.

**Da provare sul telefono:** la prima ricetta nella prima schermata; «Filtri» aperto e
richiuso col pollice, e il numero sopra; una ricetta aperta e poi «indietro» (i filtri ci
sono ancora); le miniature con la rete lenta del supermercato (l'icona sotto, mai un
bianco); «Elimina» dal dettaglio e «Annulla» nell'avviso.
```

Sostituisci `<data di oggi>` con la data vera (`date +%F`) e `<righe>` col numero misurato nel Task 7.

- [ ] **Step 2: Le osservazioni del giro**

Nella sezione del giro, sotto «**Ricette**», segna *(T3 Consegna 4)* in fondo a ognuna di queste sette voci: «**I filtri occupano tutta la prima schermata**», «**La scala «Tutte / Ora / +1 / +2 / +3» non ha un'etichetta visibile.**», «**I mancanti sulla scheda si leggono come un sottotitolo.**», «**Le schede sono alte 386 px**», «**La ricetta a mano si scrive da «Scrivi con l'AI».**», «**La scheda «Ingredienti da abbinare»**», «**Il filtro per ingredienti**». «**Tecniche e preparazioni di base**» e «**Alcune spaziature sono strette**» restano come sono.

- [ ] **Step 3: `next-steps.md`**

1. Aggiorna la riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte)_`.
2. Togli la riga della Consegna 4 da dove si trova: è quella che comincia con `- [tbd] P1 · Consegna 4, Ricette`, `- [pronto] P1 · Consegna 4` o `- [in corso] P1 · Consegna 4`.
3. In cima a «Fatti (recenti)» aggiungi:
   ```markdown
   - [fatto] <data di oggi> · T3 Consegna 4, Ricette: «Nuova», «Filtri» col numero e il pannello in linea, «Cosa posso cucinare» a video, i filtri ricordati finché l'app è aperta, righe compatte con la miniatura, l'avviso al posto della lapide (`useArchiveRecipe`); nel backend `X-Total-Count` e `main_department` → branch night/c4-ricette (da revisionare)
   ```
4. In cima a «Da fare a mano (solo Mattia)» aggiungi:
   ```markdown
   - [tbd] P1 · Prove sul telefono del Ricettario (Consegna 4): la prima ricetta in vista, «Filtri» col pollice, i filtri che restano tornando da una ricetta, le miniature con la rete lenta, «Elimina» e «Annulla»
   ```
5. Se nella notte sono emerse cose da fare fuori da questo piano, aggiungile come `idea` o `tbd` nella sezione giusta, con la voce di `docs/prossimi-passi.md` fra parentesi quadre.

- [ ] **Step 4: Commit**

```bash
git add docs/prossimi-passi.md next-steps.md
git commit -m "docs: T3 Consegna 4, il ricettario ridisegnato"
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

Expected: vitest tutto verde — **B + 56 test in F + 3 file**: +17 (Task 3: `client.test.ts` 2, `api.test.ts` 13, ricettario 2), +18 (`recipeFilters.test.ts`), +16 (`RecipeThumb.test.tsx` 4, `RecipeRow.test.tsx` 12), +8 (`useArchiveRecipe.test.tsx`), −3 (Task 7: ricettario +11, `Button` +1, `MissingBudgetFilter` +1, `RecipeCard.test.tsx` −7, `RecipeBookScreen.lapide.test.tsx` −9); file: cinque nuovi, due tolti. Se il numero differisce, scrivi nel report da dove viene la differenza. Typecheck, lint e build puliti. `npx tsc -b --force` perché `node_modules` è condiviso col checkout principale e con lui il `tsbuildinfo`: `--force` compila davvero tutto.

- [ ] **Step 2: Il backend**

Da `<worktree>/backend`:

```bash
PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Expected: tutto verde, **P + 13** (Task 1: 8; Task 2: 4; Task 8: 1).

- [ ] **Step 3: I grep**

Dalla radice del worktree:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -rn "deletedRecipe\|Tombstone\|UNDO_MS\|RecipeCard" frontend/src
grep -rn "Scrivi con l'AI" frontend/src/features/recipes
grep -n "export function useArchiveRecipe" frontend/src/features/recipes/useArchiveRecipe.ts
```

Expected: niente per i primi tre; il quarto stampa la riga della firma del gancio, com'è nella decisione 9 (il Piano 3 la consuma).

- [ ] **Step 4: L'e2e intera**

Con i comandi delle Global Constraints, su uno stack ricreato da zero (`down -v` prima dell'`up`, se ne era rimasto uno di questo ramo). Expected: tutti verdi. Poi `down -v` e `rm .env`, sempre.

- [ ] **Step 5: Il report**

Nel report della notte (`docs/night-reports/<data>.md`), per questo piano: il ramo (`night/c4-ricette`, da `night/c6a-pulsanti`), i conti veri (vitest, pytest, e2e), le righe di `RecipeBookScreen.tsx` prima e dopo, i test di oggi migrati oltre a quelli elencati nel Task 7 (dovrebbero essere zero), i letterali tipizzati trovati da `tsc -b` oltre ai sette del Task 3, e le decisioni prese in autonomia. Niente push, niente merge, niente deploy.
