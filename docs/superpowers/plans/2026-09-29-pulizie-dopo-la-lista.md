# Pulizie dopo la Lista — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** chiudere sette code rimaste aperte dopo la T3 Consegna 2: il doppione che un «Annulla» rapido può ancora rimettere in lista, la ✕ che spegnendosi butta il fuoco sulla pagina, l'elenco dei suggerimenti senza altezza massima, la pulizia e2e vecchia che avvisa soltanto, la via `set_fill` rimasta senza chiamanti, il 404 ritentato che finisce in un «Riprova» inutile, e `occurrences` che dopo un annullamento dice «1 ricetta in attesa» sopra due titoli.

**Architecture:** sette interventi piccoli e indipendenti, ognuno col suo test prima del codice. Nel backend: un controllo in `patch_item` (409 quando una voce archiviata tornerebbe in lista accanto a un'altra dello stesso ingrediente); la rotta `PATCH /pantry/{id}` perde il ramo `fill_percent` e `set_fill` sparisce; il conteggio delle ricette in attesa per termine esce da `sync_terms` in una funzione (`count_pending_keys`) che anche `undo_decision` chiama. Nel frontend: `Button` impara `busy` (spento con `aria-disabled`, tocco ignorato dentro il primitivo); `OptionList` scorre da sé; `defaultQueryRetryPredicate` non ritenta il 404; dettaglio e modifica della ricetta dicono «Questa ricetta non c'è più.». Nessuna rotta nuova, nessuna migrazione, nessuna dipendenza.

**Tech Stack:** FastAPI, SQLAlchemy async, pytest su Postgres vero; React 19, TypeScript, Tailwind 4 (token in `@theme`), TanStack Query 5, react-router 7, Vitest + Testing Library (jsdom), Playwright.

**Spec:** nessuna, di proposito: sono code piccole e già decise. Le voci vengono da `docs/prossimi-passi.md`:
- T3, paragrafo «**Consegna 2 (Lista) fatta il 2026-09-28**…» e il paragrafo che segue, «**Restano aperti, da questa consegna:**» (i punti 1, 2, 3 e 4 qui sotto);
- Parte X, «**Un 404 viene ritentato e poi offre «Riprova».**» (punto 6);
- T3, «Esito del giro» → «**Ingredienti da abbinare**», la voce «**«1 ricetta in attesa»** compare con due ricette elencate sotto» (punto 7);
- D1, la «**Nota 2026-09-17.**» su `pantry_items.fill_percent` (punto 5).

Le decisioni sono state prese nella fase giorno del 2026-09-29 e sono scritte sotto, in «Decisioni prese». Questo piano le rende eseguibili.

## Global Constraints

- **Dove si lavora.** Un worktree sul ramo `night/pulizie-dopo-la-lista`, dal `master` attuale. Dalla radice del checkout principale:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/pulizie-dopo-la-lista -b night/pulizie-dopo-la-lista master
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/pulizie-dopo-la-lista/frontend/node_modules
  (cd .worktrees/pulizie-dopo-la-lista/frontend && npm install --no-audit --no-fund && npx vitest run 2>&1 | grep -E "Test Files|Tests ")
  ```
  Il `npm install` allinea i `node_modules` condivisi al `package-lock.json` (nessuna dipendenza nuova): il 2026-09-29 erano vecchi e 24 file di test non partivano. Deve stampare 51 file e 663 test verdi; se no, fermati prima del Task 1.
  Nel piano `<worktree>` è `/home/mactyws/coding/ais/spena/.worktrees/pulizie-dopo-la-lista`. Ogni comando parte da lì (o dalle sue `backend/` e `frontend/`), mai dalla radice del checkout principale. Il checkout principale non si tocca: se vi trovi modifiche non committate, sono dell'utente.
- **Backend su Postgres vero.** Il container `spena-db-1` si usa solo come database dei test. Se `docker ps --format '{{.Names}}'` non lo mostra, lo si avvia dal checkout principale: `cd /home/mactyws/coding/ais/spena && docker compose up -d db` (mai `up` senza `db`, mai `-f docker-compose.prod.yml`). Nel worktree non c'è un `.venv`: si usa quello del checkout principale, che vi ha installato `spena-backend` in modo modificabile; `python -m` mette la cartella corrente in testa a `sys.path` (e `alembic.ini` ha `prepend_sys_path = .`), quindi si prova l'`app` del worktree. Il comando, sempre da `<worktree>/backend`:
  ```bash
  PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
  Nel piano lo si scrive **`$PYTEST`**; dove la shell non conserva le variabili fra un comando e l'altro, va scritto per intero. Il `PATH` serve ai test che lanciano `alembic`. Se un test sembra ignorare una modifica, `python -c 'import app; print(app.__file__)'` da `<worktree>/backend` deve stampare un percorso dentro il worktree. Nessuna chiamata di rete nella suite.
- **Frontend**, sempre da `<worktree>/frontend`: `npx vitest run` (non esiste `npm test`), `npm run lint`, `npm run typecheck`, `npm run build`. Il type check è `npm run typecheck` (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0 (`CLAUDE.md`, settima lezione).
- **e2e** (Task 8 e Task 10), dalla radice di `<worktree>`. Serve un `.env`: si copia da `.env.example`, che non ha segreti, solo per la prova, e si cancella alla fine. **Mai leggere né copiare il `.env` del checkout principale.**
  ```bash
  cp .env.example .env
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed --con-ricette
  (cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
  rm .env
  ```
  Il `-p spena-e2e` e il `-f docker-compose.e2e.yml` vanno in ogni comando: un `down -v` sul progetto di default cancellerebbe la dispensa vera. Una prova fallita lascia dati nello stack: prima di rieseguire si ricrea da zero (`down -v`, poi `up`, poi il seme). Prima di alzarlo, `docker ps --format '{{.Names}}' | grep spena-e2e`: se c'è e non l'hai alzato tu (un altro piano della notte), non fare `down`, aspetta che sparisca.
- **La linea di partenza**, misurata il 2026-09-29: vitest **663** test verdi in 51 file (prima di contare, `node_modules` va allineato al `package-lock`: con quelli vecchi 24 file non partono e il conto sembra 320). Il backend non è stato misurato: esegui `$PYTEST` una volta prima del Task 1 e annota il numero. Ogni task finisce con la sua suite verde; il conto cresce, non cala.
- Tutto il colore passa dai token di `frontend/src/index.css`: `grep -rn "emerald\|neutral-" frontend/src` resta vuoto. Ogni bersaglio resta almeno 44×44 px.
- **Un controllo che si spegne mentre ha il fuoco usa `aria-disabled` e una guardia nel gestore**, mai `disabled`: il browser toglie il fuoco a un controllo che diventa `disabled`, e chi usa la tastiera lo ritrova sul `body`. È la regola delle tacche (`StockGauge.tsx`), della casella della lista e della scadenza in dispensa; questo piano la porta dentro `Button`.
- **Mai un vicolo cieco.** Ogni rifiuto nuovo (il 409 della lista, il 404 della ricetta) dice cosa è successo e lascia una strada: «Era già in lista.» con la voce che c'è, «Torna al ricettario».
- Le parole a video sono in italiano e **si copiano esattamente come sono scritte qui**; gli identificatori in inglese; i commenti in italiano come nel resto del codice.
- Nessuna dipendenza nuova, nessuna migrazione. Niente push, merge, deploy: il lavoro finisce sul ramo, verificato.

---

## Obiettivo e contesto

La Consegna 2 del ridisegno (la Lista) è in produzione dal 2026-09-28, e il suo giro finale ha lasciato quattro punti scritti in «Restano aperti». Accanto, tre code piccole già decise aspettavano un piano: il 404 ritentato (Parte X), il conteggio sbagliato della coda d'import dopo un annullamento (dal giro di T3), e la via `PATCH` di `fill_percent` che dalla Consegna 1 nessuno chiama (D1). Sono tutte piccole, tutte indipendenti, e ognuna o fa mentire l'app («1 ricetta in attesa» sopra due titoli, «Riprova» dove riprovare non può riuscire) o lascia un difetto che si vede solo usandola (un doppione in lista, il fuoco perso, un elenco che esce dallo schermo con la tastiera aperta). Una via di scrittura senza chiamanti è una porta che nessuno sorveglia: si toglie finché è piccola.

## Decisioni prese

1. **Il doppione sull'«Annulla» si ferma nel server.** Quando una `PATCH /api/v1/shopping-list/{id}` porta una voce **archiviata** a `pending` o `checked`, e un'altra voce attiva (`pending` o `checked`) ha lo stesso `ingredient_id` non nullo, il server risponde **409** con `detail` «l'ingrediente è già in lista» e non cambia niente. L'ingrediente guardato è quello che la voce avrebbe *dopo* la PATCH (se la stessa richiesta porta un `ingredient_id`, conta quello). Una voce senza ingrediente non è mai un doppione (è la regola di S18: senza ingrediente non c'è un'identità). Le altre PATCH restano com'erano: spuntare, togliere la spunta, abbinare. *Perché:* la cache del client non sa, fra la POST della barra e il refetch, che la stessa cosa è tornata in lista; il server lo sa sempre. *Nel client* `undoRemove` tiene il controllo sulla cache come via veloce, e su un `ApiError` con `status === 409` mostra l'avviso che esiste già, «Era già in lista.», e rilegge la lista; il suo avviso di guasto con «Riprova» resta per ogni altro errore (un 409 riprovato rifallirebbe).
2. **`Button` ha `busy`.** `busy` rende `aria-disabled="true"` (non `disabled`), si vede con `aria-disabled:opacity-40` (in `buttonClasses`, accanto a `disabled:opacity-40`), e dentro `Button` il tocco si ignora — anche l'invio del modulo, per un `type="submit"` — così nessun chiamante può dimenticare la guardia. `disabled` resta, per un'azione che adesso non si può proprio fare. Passano a `busy` i chiamanti che spengono un `Button` mentre una richiesta è in volo: la ✕ di `ListRow.tsx`, il «Riprova» di `ErrorState.tsx` e — scelta di questo piano, perché hanno lo stesso difetto e la stessa causa — la ✕ e «In lista» di `PantryRow.tsx`. `IngredientPicker.tsx` resta com'è (spegne insieme campo, suggerimenti e pulsante: è un'altra forma, va in `next-steps.md` come idea).
3. **`OptionList` si tiene lo scorrimento.** `max-h-[min(18rem,45dvh)] overflow-y-auto overscroll-contain`, con gli angoli arrotondati di prima. Ne beneficiano i due chiamanti, la barra della Lista (`AddItemField.tsx`) e `IngredientPicker.tsx`. *Perché* `45dvh`: con la tastiera aperta la finestra si accorcia, e `dvh` segue la finestra vera; `18rem` è il tetto su uno schermo alto. Lo prova l'e2e a 375×812 e a 375×450 (un telefono con la tastiera aperta), con i suggerimenti forniti da `page.route`.
4. **La pulizia e2e vecchia fa fallire la prova.** I due blocchi di `frontend/e2e/style.spec.ts` che oggi fanno `try { … } catch { console.warn }` prendono la forma della prova più recente: la risposta si controlla con `expect.soft(risposta.ok(), …)`, e nel `catch` `expect.soft(false, …)`. `expect.soft` non lancia (un `finally` che lancia nasconderebbe l'errore vero del `try`) ma segna la prova fallita.
5. **`set_fill` si toglie.** Via il ramo `elif payload.fill_percent is not None` della rotta `PATCH /api/v1/pantry/{id}`, via `set_fill` da `app/repositories/pantry.py`, via il campo `fill_percent` da `PantryItemPatch`. Lo schema non vieta i campi in più (nessun `extra="forbid"`), quindi un `fill_percent` mandato si ignora: da solo la richiesta non ha niente da modificare e risponde **400** «niente da modificare», insieme a `status` vale solo lo stato. Un test fissa questo comportamento al posto di quelli che provavano la via tolta. **Restano** la colonna, il suo CHECK, il campo in `PantryItemOut`, e `set_status` che la azzera. `status_for_fill` resta in `app/domain/rules.py` con i suoi test anche senza chiamanti in produzione, perché `CLAUDE.md` la cita; lo si scrive nel suo commento e nei documenti. *Perché* non la colonna: le voci toccate prima del 2026-09-28 l'hanno ancora piena, e toglierla è una migrazione che questo piano non fa.
6. **Un 404 non si ritenta.** `defaultQueryRetryPredicate` non ritenta un `ApiError` con `status` 404 né 401 (`UnauthorizedError` è un `ApiError` con 401); il resto si ritenta come prima, due volte. Il dettaglio (`RecipeDetailScreen.tsx`) e la modifica (`RecipeEditScreen.tsx`) seguono lo schema di `IngredientScreen.tsx` e `ProductScreen.tsx`: `const gone = error instanceof ApiError && error.status === 404`; se `gone`, «Questa ricetta non c'è più.» e un collegamento «Torna al ricettario» a `/ricette`, niente «Riprova». Il ramo `archived_at` di `RecipeEditScreen` resta com'è. Nella modifica, a ricetta sparita, anche il ritorno in alto porta al ricettario (tornare alla ricetta sparita sarebbe un giro a vuoto). *Test:* una tabella sul predicato vero, e una prova sul `QueryClient` vero dell'app (`App.test.tsx`), perché i test di schermata si costruiscono il client con `retry: false` (prima lezione di `CLAUDE.md`). Conseguenza: `frontend/e2e/error-branch.spec.ts` provava la politica dei ritentativi deviando la lista su un 404; con questa decisione un 404 non si ritenta più e quella prova non vedrebbe niente. La deviazione passa a un 405 del server vero (`GET /api/v1/auth/login`, rotta che accetta solo `POST`).
7. **`undo_decision` riconta `occurrences`.** Il conteggio delle ricette in attesa per termine esce da `sync_terms` in `count_pending_keys(pages)`, che tutte e due chiamano; `undo_decision`, dopo aver rimesso le pagine in coda e nella stessa transazione, riconta **solo il termine annullato**. `UndoOut` non cambia. *Perché* una funzione sola: due conteggi scritti due volte divergono, ed è la prima lezione di `CLAUDE.md` (un test che guarda una copia che nessuno chiama).

## Criteri di accettazione

- `PATCH /api/v1/shopping-list/{id}` da `archived` a `pending` o `checked`, con un'altra voce `pending`/`checked` dello stesso ingrediente, risponde 409 «l'ingrediente è già in lista» e lascia la voce archiviata; con un ingrediente mandato nella stessa richiesta conta quello. Voci libere, voci senza doppioni, e ogni altra PATCH: come prima.
- In Lista, un «Annulla» che riceve quel 409 mostra «Era già in lista.», non «Non sono riuscito a rimettere … in lista.» e non «Riprova».
- `Button` con `busy`: `aria-disabled="true"`, nessun attributo `disabled`, il tocco non chiama `onClick` e non invia il modulo, il fuoco resta. La ✕ della Lista, la ✕ e «In lista» della Dispensa e il «Riprova» di `ErrorState` usano `busy`. Nel browser, dopo una ✕ fallita premuta da tastiera, il fuoco è ancora sulla ✕.
- Con dodici suggerimenti, a 375×812 e a 375×450, l'elenco sotto la barra della Lista scorre da sé e il suo fondo sta dentro la finestra.
- In `frontend/e2e/style.spec.ts` non resta nessun `console.warn`; le due pulizie vecchie usano `expect.soft`.
- `PATCH /api/v1/pantry/{id}` con solo `fill_percent` risponde 400 e non cambia niente; con `fill_percent` e `status` scrive lo stato e lascia `fill_percent` vuoto. `set_fill` non esiste più (`grep -rn "set_fill" backend/app` vuoto). La colonna, il CHECK, `PantryItemOut.fill_percent` e `status_for_fill` restano.
- `defaultQueryRetryPredicate` non ritenta 401 e 404, ritenta il resto al più due volte. Una ricetta sparita (404) mostra subito «Questa ricetta non c'è più.» con «Torna al ricettario» → `/ricette`, nel dettaglio e nella modifica; ogni altro errore mostra ancora «Riprova».
- Dopo `undo_decision`, `import_terms.occurrences` del termine annullato è il numero di ricette in attesa che lo nominano (la riproduzione del giro: 2).
- Documenti aggiornati: `docs/prossimi-passi.md`, `next-steps.md`, `CLAUDE.md` (Task 9).
- Tutti i comandi di verifica qui sotto passano.

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
grep -rn "emerald\|neutral-" src   # deve restare vuoto
```
Dalla radice di `<worktree>`, l'e2e intera (la sequenza completa è nei Global Constraints):
```bash
cp .env.example .env
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed --con-ricette
(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
rm .env
```

## Fuori scope

- Tutto ciò che appartiene alle Consegne 3–6 del ridisegno (Sistema la spesa, Ricette, Dettaglio ricetta, il resto): nessun ritocco di disegno a quelle schermate, nemmeno dove questo piano ci passa (il dettaglio della ricetta cambia solo nel ramo d'errore).
- Togliere la colonna `fill_percent`, il suo CHECK o il campo in `PantryItemOut`; togliere `status_for_fill` o `LOW_MAX_FILL`.
- Cambiare `UndoOut`, o ricontare `occurrences` di termini diversi da quello annullato.
- Gli stati d'errore delle altre schermate (ricettario, dispensa, lista, sistemazione, coda d'import): cambia solo il predicato comune, non i loro messaggi. Il `retry` locale di `ImportQueueScreen.tsx` (righe ~196-200, che esclude già il 404) resta com'è: ora è ridondante, ma è corretto e non si tocca.
- `IngredientPicker.tsx` e il suo `disabled` (vedi la decisione 2): si annota in `next-steps.md`, non si cambia.
- Le pulizie di `frontend/e2e/anagrafica.spec.ts` e `frontend/e2e/import-review.spec.ts` che avvisano con `console.warn`: la decisione 4 riguarda solo `style.spec.ts`.
- La soglia dei suggerimenti «sempre dieci righe» (altra voce di `next-steps.md`, ancora `tbd`).

## Margine di autonomia

- **Libero:** i nomi di variabili locali, helper di test e funzioni interne; l'ordine dei test dentro un file; la formulazione dei commenti.
- **Fisso:** le parole a video, esattamente come sono scritte nel piano («Era già in lista.», «Questa ricetta non c'è più.», «Torna al ricettario», «l'ingrediente è già in lista»); i nomi pubblici che altri task usano (`AlreadyListed`, `busy`, `count_pending_keys`, `PendingKeys`); le classi `max-h-[min(18rem,45dvh)] overflow-y-auto overscroll-contain`.
- **Nessuna dipendenza nuova**, nessuna migrazione, nessun cambio di configurazione globale.
- **Un test esistente può cambiare solo per seguire un'API rinominata o tolta** (`disabled` → `busy`, la via `set_fill`), mai per indebolirlo: dove un'asserzione su `disabled` diventa un'asserzione su `aria-disabled`, la si mantiene altrettanto stretta, e dove prima un clic era impossibile si prova che il clic non fa niente.
- **Una decisione non coperta da questo piano e non reversibile** → si ferma quel task, si fa commit del lavoro parziale sul ramo, lo si segna `bloccato` in `next-steps.md` con la domanda precisa, e si passa al task successivo. Una scelta reversibile e a basso impatto → la più conservativa, annotata nel report della notte.
- Se un test fallisce e non si risolve in modo ragionevole: niente test disattivati, niente asserzioni indebolite; `bloccato` con la diagnosi.

## Dipendenze

Nessuna. Il piano è indipendente da quello della Consegna 3 (Sistema la spesa), ma tutti e due toccano `frontend/e2e/style.spec.ts` (e forse `Button`): le aggiunte e2e di questo piano stanno in blocchi `test(...)` propri, in fondo al file, così la fusione dei due rami resta un'unione di blocchi. Se la Consegna 3 arriva prima su `master` e aggiunge chiamanti di `Button` con `disabled` mentre una richiesta è in volo, passarli a `busy` è compito suo, non di questo ramo.

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `backend/app/repositories/shopping.py` | 1 | `AlreadyListed`, il controllo in `patch_item` |
| `backend/app/api/shopping.py` | 1 | 409 su `AlreadyListed` |
| `backend/tests/api/test_shopping.py` | 1 | cinque test (otto casi) |
| `frontend/src/features/shopping-list/ShoppingListScreen.tsx` | 2 | `undoRemove` sul 409 |
| `frontend/src/features/shopping-list/ShoppingListScreen.test.tsx` | 2, 3 | un test; due asserzioni `toBeDisabled` → `aria-disabled` |
| `frontend/src/components/ui/buttonClasses.ts` | 3 | `aria-disabled:opacity-40` |
| `frontend/src/components/ui/Button.tsx` | 3 | `busy` |
| `frontend/src/components/ui/Button.test.tsx` | 3 | test di `busy` |
| `frontend/src/components/ui/ErrorState.tsx`, `States.test.tsx` | 3 | `busy={retrying}` |
| `frontend/src/features/shopping-list/ListRow.tsx`, `ListRow.test.tsx` | 3 | la ✕ con `busy` |
| `frontend/src/features/pantry/PantryRow.tsx`, `PantryRow.test.tsx`, `PantryScreen.test.tsx` | 3 | ✕ e «In lista» con `busy` |
| `backend/app/api/pantry.py`, `backend/app/repositories/pantry.py`, `backend/app/schemas/pantry.py` | 4 | via `set_fill` |
| `backend/app/domain/rules.py`, `backend/app/db/models/pantry.py` | 4 | commenti su `status_for_fill` e sulla colonna |
| `backend/tests/api/test_pantry.py` | 4 | i test della via tolta → un test del comportamento nuovo |
| `frontend/src/lib/queryRetry.ts`, `frontend/src/lib/queryRetry.test.ts` (nuovo) | 5 | il 404 non si ritenta |
| `frontend/src/App.test.tsx` | 5 | la ricetta sparita sul client vero |
| `frontend/src/features/cooking/RecipeDetailScreen.tsx`, `.test.tsx` | 5 | «Questa ricetta non c'è più.» |
| `frontend/src/features/recipe-form/RecipeEditScreen.tsx`, `.test.tsx` | 5 | idem |
| `frontend/e2e/error-branch.spec.ts` | 5 | la deviazione su un 405 |
| `backend/app/services/recipe_import/terms.py` | 6 | `count_pending_keys` |
| `backend/app/services/recipe_import/undo.py` | 6 | il riconteggio |
| `backend/tests/services/test_undo.py` | 6 | due test |
| `frontend/src/components/ui/OptionList.tsx` | 7 | altezza massima e scorrimento |
| `frontend/e2e/style.spec.ts` | 8 | due pulizie; due test nuovi |
| `docs/prossimi-passi.md`, `next-steps.md`, `CLAUDE.md` | 9 | i documenti |

---

### Task 1: Il 409 sul ritorno di una voce tolta (backend)

**Files:**
- Modify: `backend/app/repositories/shopping.py` (`patch_item`, e una classe nuova sopra)
- Modify: `backend/app/api/shopping.py` (la rotta `patch`)
- Test: `backend/tests/api/test_shopping.py`

**Interfaces:**
- Consumes: `active_item_for(session, ingredient_id)` (stesso file, già usata da `add_item` per S18).
- Produces: `class AlreadyListed(Exception)` in `app/repositories/shopping.py`, con attributo `existing: ShoppingListItem`; `patch_item` la solleva prima di ogni scrittura. La rotta risponde `409` con `detail` «l'ingrediente è già in lista». Il Task 2 si appoggia a questo 409.

- [ ] **Step 1: Scrivere i test che falliscono**

In cima a `backend/tests/api/test_shopping.py` aggiungi `import pytest` sopra `import pytest_asyncio` (oggi il file importa solo `pytest_asyncio`):

```python
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import select
```

In fondo al file, dopo `test_il_testo_libero_non_si_confronta_col_testo_libero`, aggiungi:

```python
# --- L'«Annulla» della ✕ non rimette un doppione (T3 Consegna 2, «Restano aperti») ---
# La ✕ archivia la voce, e «Annulla» la rimanda a `pending` o `checked` con la PATCH di
# sempre. Nei secondi dell'avviso la stessa cosa può essere tornata in lista dalla barra:
# il client lo guarda nella sua cache, ma fra la POST e il refetch la cache non lo sa
# ancora. La difesa vera è qui: rimettere una voce tolta il cui ingrediente è già da
# comprare o nel carrello in un'altra voce è un 409, e non cambia niente.


def _voce(
    ingrediente: Ingredient | None, stato: ShoppingStatus, testo: str = "latte"
) -> ShoppingListItem:
    return ShoppingListItem(
        raw_text=testo,
        ingredient_id=ingrediente.id if ingrediente is not None else None,
        status=stato,
        reason=ShoppingReason.MANUAL,
    )


@pytest.mark.parametrize("gia_in_lista", [ShoppingStatus.PENDING, ShoppingStatus.CHECKED])
@pytest.mark.parametrize("verso", ["pending", "checked"])
async def test_rimettere_una_voce_tolta_gia_in_lista_e_409_e_non_cambia_niente(
    logged_client, db_session, dal_database, anagrafica_s18, gia_in_lista, verso
):
    tolta = _voce(anagrafica_s18["latte"], ShoppingStatus.ARCHIVED)
    riscritta = _voce(anagrafica_s18["latte"], gia_in_lista, testo="latte intero")
    db_session.add_all([tolta, riscritta])
    await db_session.flush()

    risposta = await logged_client.patch(
        f"/api/v1/shopping-list/{tolta.id}", json={"status": verso}
    )

    assert risposta.status_code == 409
    assert risposta.json()["detail"] == "l'ingrediente è già in lista"
    assert (await dal_database(ShoppingListItem, tolta.id)).status == "archived"
    assert (await dal_database(ShoppingListItem, riscritta.id)).status == gia_in_lista


async def test_l_ingrediente_mandato_insieme_conta_come_quello_della_voce(
    logged_client, db_session, dal_database, anagrafica_s18
):
    """Una PATCH che abbina e rimette nello stesso colpo guarda l'ingrediente che la
    voce avrebbe dopo, non quello che aveva: altrimenti il doppione passerebbe
    dall'abbinamento."""
    tolta = _voce(None, ShoppingStatus.ARCHIVED, testo="latt")
    db_session.add_all([tolta, _voce(anagrafica_s18["latte"], ShoppingStatus.PENDING)])
    await db_session.flush()

    risposta = await logged_client.patch(f"/api/v1/shopping-list/{tolta.id}", json={
        "status": "pending", "ingredient_id": str(anagrafica_s18["latte"].id),
    })

    assert risposta.status_code == 409
    salvata = await dal_database(ShoppingListItem, tolta.id)
    assert salvata.status == "archived"
    assert salvata.ingredient_id is None


async def test_rimettere_una_voce_tolta_senza_doppioni_riesce(
    logged_client, db_session, anagrafica_s18
):
    """Una voce già sistemata in dispensa o un'altra tolta non sono «in lista»:
    l'«Annulla» di sempre rimette la voce com'era."""
    tolta = _voce(anagrafica_s18["latte"], ShoppingStatus.ARCHIVED)
    db_session.add_all([
        tolta,
        _voce(anagrafica_s18["latte"], ShoppingStatus.DONE),
        _voce(anagrafica_s18["latte"], ShoppingStatus.ARCHIVED),
    ])
    await db_session.flush()

    risposta = await logged_client.patch(
        f"/api/v1/shopping-list/{tolta.id}", json={"status": "checked"}
    )

    assert risposta.status_code == 200
    assert risposta.json()["status"] == "checked"


async def test_una_voce_libera_tolta_torna_sempre(logged_client, db_session):
    """Senza ingrediente non c'è un'identità su cui dire «è la stessa cosa» (S18): due
    voci libere con lo stesso testo restano due, anche passando dall'«Annulla»."""
    tolta = _voce(None, ShoppingStatus.ARCHIVED, testo="quella cosa verde")
    db_session.add_all([tolta, _voce(None, ShoppingStatus.PENDING, testo="quella cosa verde")])
    await db_session.flush()

    risposta = await logged_client.patch(
        f"/api/v1/shopping-list/{tolta.id}", json={"status": "pending"}
    )

    assert risposta.status_code == 200
    assert risposta.json()["status"] == "pending"


async def test_solo_il_ritorno_da_archiviata_e_controllato(
    logged_client, db_session, anagrafica_s18
):
    """Spuntare, togliere la spunta e riaprire una voce sistemata restano come prima,
    anche con due voci dello stesso ingrediente già in lista (una storia di prima di
    S18): il controllo è dell'«Annulla», non di ogni PATCH."""
    prima = _voce(anagrafica_s18["latte"], ShoppingStatus.PENDING)
    seconda = _voce(anagrafica_s18["latte"], ShoppingStatus.PENDING, testo="latte intero")
    sistemata = _voce(anagrafica_s18["latte"], ShoppingStatus.DONE, testo="latte uht")
    db_session.add_all([prima, seconda, sistemata])
    await db_session.flush()

    spunta = await logged_client.patch(
        f"/api/v1/shopping-list/{prima.id}", json={"status": "checked"}
    )
    assert spunta.status_code == 200
    togli_spunta = await logged_client.patch(
        f"/api/v1/shopping-list/{prima.id}", json={"status": "pending"}
    )
    assert togli_spunta.status_code == 200
    riapri = await logged_client.patch(
        f"/api/v1/shopping-list/{sistemata.id}", json={"status": "pending"}
    )
    assert riapri.status_code == 200
```

- [ ] **Step 2: Farli fallire**

Run (da `<worktree>/backend`): `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/api/test_shopping.py`
Expected: FAIL nei cinque casi che aspettano 409 (i quattro di `test_rimettere_una_voce_tolta_gia_in_lista_e_409_e_non_cambia_niente` e `test_l_ingrediente_mandato_insieme_conta_come_quello_della_voce`), con `assert 200 == 409`. Gli altri tre test nuovi passano già: fissano quel che non deve cambiare.

- [ ] **Step 3: Scrivere il codice**

In `backend/app/repositories/shopping.py`, subito sopra `async def patch_item(`, aggiungi:

```python
class AlreadyListed(Exception):
    """Rimettere in lista una voce tolta farebbe un doppione: il suo ingrediente è già
    da comprare, o nel carrello, in un'altra voce (T3 Consegna 2, l'«Annulla» della ✕).

    `existing` è quella voce: la stessa che S18 restituisce alla POST con `added`
    falso.
    """

    def __init__(self, existing: ShoppingListItem):
        self.existing = existing
        super().__init__(f"l'ingrediente {existing.ingredient_id} è già in lista")
```

e sostituisci l'inizio di `patch_item`:

```python
    item = await session.get(ShoppingListItem, item_id)
    if item is None:
        raise KeyError(item_id)
    if ingredient_id is not None:
        item.ingredient_id = ingredient_id
```

con:

```python
    item = await session.get(ShoppingListItem, item_id)
    if item is None:
        raise KeyError(item_id)
    # L'«Annulla» della ✕ riporta una voce archiviata in lista. Se nel frattempo la
    # stessa cosa ci è tornata dalla barra, rimetterla farebbe il doppione che S18 esiste
    # per evitare. Il controllo sta qui e non nel client, che lo guarda nella sua cache:
    # fra la POST della barra e il refetch la cache non lo sa ancora. Conta l'ingrediente
    # che la voce avrebbe dopo questa PATCH, e si guarda prima di scrivere niente. Una
    # voce libera non è mai un doppione: senza ingrediente non c'è un'identità (S18).
    # Le altre PATCH non si toccano: il controllo è del ritorno da `archived`.
    target_ingredient = ingredient_id if ingredient_id is not None else item.ingredient_id
    if (
        item.status == ShoppingStatus.ARCHIVED
        and status in (ShoppingStatus.PENDING, ShoppingStatus.CHECKED)
        and target_ingredient is not None
    ):
        existing = await active_item_for(session, target_ingredient)
        if existing is not None:
            raise AlreadyListed(existing)
    if ingredient_id is not None:
        item.ingredient_id = ingredient_id
```

(`active_item_for` guarda solo `pending` e `checked`: la voce stessa, archiviata, non può risultare.)

In `backend/app/api/shopping.py` cambia l'import:

```python
from app.repositories.shopping import StockEntry, add_item, list_items, patch_item, stock_items
```

in:

```python
from app.repositories.shopping import (
    AlreadyListed,
    StockEntry,
    add_item,
    list_items,
    patch_item,
    stock_items,
)
```

e nella rotta `patch`, fra `except KeyError …` e `except IntegrityError …`, aggiungi:

```python
    except AlreadyListed as exc:
        # sollevata prima di ogni scrittura: non c'è niente da annullare. Un 409 e non un
        # 200 con la voce che c'era (come la POST di S18): chi ha chiesto di rimettere
        # *questa* voce deve sapere che non è tornata
        raise HTTPException(status.HTTP_409_CONFLICT, "l'ingrediente è già in lista") from exc
```

- [ ] **Step 4: Farli passare**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/api/test_shopping.py`
Expected: PASS, tutto il file.

- [ ] **Step 5: La suite intera**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q`
Expected: PASS; il conto è quello di partenza più 8.

- [ ] **Step 6: Commit**

```bash
git add backend/app/repositories/shopping.py backend/app/api/shopping.py backend/tests/api/test_shopping.py
git commit -m "lista: rimettere una voce tolta accanto a una dello stesso ingrediente è un 409"
```

---

### Task 2: «Annulla» sul 409 dice «Era già in lista.»

**Files:**
- Modify: `frontend/src/features/shopping-list/ShoppingListScreen.tsx` (`undoRemove`)
- Test: `frontend/src/features/shopping-list/ShoppingListScreen.test.tsx`

**Interfaces:**
- Consumes: il 409 del Task 1; `ApiError` da `frontend/src/api/client.ts` (ha `status`).
- Produces: nessuna API nuova.

- [ ] **Step 1: Scrivere il test che fallisce**

In `frontend/src/features/shopping-list/ShoppingListScreen.test.tsx`, subito dopo il test «se nel frattempo la stessa cosa è tornata in lista, «Annulla» non fa il doppione», aggiungi:

```tsx
  it("se la cache non lo sa ma il server sì, «Annulla» dice «Era già in lista.» e non offre «Riprova»", async () => {
    // La POST della barra e il refetch si sono incrociati: la cache non ha ancora la voce
    // riscritta, quindi la PATCH parte, e il server risponde 409 (la difesa vera). Non è
    // un guasto: riprovare rifallirebbe
    let patches = 0;
    const spy = stubRoutedFetch((_path, init) => {
      if (init?.method !== "PATCH") return [patches === 0 ? ITEMS : ITEMS.filter((i) => i.id !== "s1"), 200];
      patches += 1;
      return patches === 1 ? [ITEMS[1], 200] : [{ detail: "l'ingrediente è già in lista" }, 409];
    });
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Togli pomodoro dalla lista" }));
    await screen.findByText("Tolto dalla lista: pomodoro");
    fireEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(await screen.findByText("Era già in lista.")).toBeDefined();
    expect(screen.queryByText("Non sono riuscito a rimettere pomodoro in lista.")).toBeNull();
    expect(screen.queryByRole("button", { name: "Riprova" })).toBeNull();
    expect(patchesOf(spy)).toEqual([
      ["/shopping-list/s1", { status: "archived" }],
      ["/shopping-list/s1", { status: "pending" }],
    ]);
  });
```

- [ ] **Step 2: Farlo fallire**

Run (da `<worktree>/frontend`): `npx vitest run src/features/shopping-list/ShoppingListScreen.test.tsx`
Expected: FAIL nel test nuovo: `findByText("Era già in lista.")` non trova niente, perché compare «Non sono riuscito a rimettere pomodoro in lista.».

- [ ] **Step 3: Scrivere il codice**

In `frontend/src/features/shopping-list/ShoppingListScreen.tsx` aggiungi l'import, dopo quello di `./api`:

```tsx
import { ApiError } from "../../api/client";
```

e sostituisci tutta la funzione `undoRemove` con:

```tsx
  function undoRemove(item: ShoppingItem) {
    // nei 6 secondi dell'avviso la stessa cosa può essere stata riscritta dalla barra:
    // rimettere anche questa farebbe il doppione che S18 esiste per evitare. La cache è
    // la via veloce, non la difesa: fra la POST della barra e il refetch non lo sa
    // ancora, e allora risponde il server, con un 409 (sotto)
    const current = queryClient.getQueryData<ShoppingItem[]>(LIST_KEY) ?? [];
    const relisted =
      item.ingredient_id !== null &&
      current.some((other) => other.id !== item.id && other.ingredient_id === item.ingredient_id);
    if (relisted) {
      notice({ text: "Era già in lista." });
      return;
    }
    patchShoppingItem(item.id, { status: item.status }).then(
      () => queryClient.invalidateQueries({ queryKey: LIST_KEY }),
      (error: unknown) => {
        // la stessa notizia della barra, non un guasto: niente «Riprova», che
        // rifallirebbe. Si rilegge la lista, così la voce che c'è si vede
        if (error instanceof ApiError && error.status === 409) {
          notice({ text: "Era già in lista." });
          void queryClient.invalidateQueries({ queryKey: LIST_KEY });
          return;
        }
        // la voce è archiviata davvero: perderla qui sarebbe il vicolo cieco
        notice({
          text: `Non sono riuscito a rimettere ${item.raw_text} in lista.`,
          action: { label: "Riprova", onClick: () => undoRemove(item) },
        });
      }
    );
  }
```

Il commento sopra la funzione («L'annulla vive nell'avviso…») resta com'è.

- [ ] **Step 4: Farlo passare**

Run: `npx vitest run src/features/shopping-list/ShoppingListScreen.test.tsx`
Expected: PASS, tutto il file (il test «un «Annulla» fallito lo dice, e offre di riprovare», su un 500, passa ancora: è il ramo che resta).

- [ ] **Step 5: Le verifiche del frontend**

Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde, vitest 664 test.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/shopping-list/ShoppingListScreen.tsx frontend/src/features/shopping-list/ShoppingListScreen.test.tsx
git commit -m "lista: «Annulla» su un 409 dice «Era già in lista.» invece di offrire «Riprova»"
```

---

### Task 3: `Button` con `busy`, e i pulsanti che si spengono in volo

**Files:**
- Modify: `frontend/src/components/ui/buttonClasses.ts` (`BASE`)
- Modify: `frontend/src/components/ui/Button.tsx`
- Test: `frontend/src/components/ui/Button.test.tsx`
- Modify: `frontend/src/components/ui/ErrorState.tsx`; Test: `frontend/src/components/ui/States.test.tsx`
- Modify: `frontend/src/features/shopping-list/ListRow.tsx`; Test: `frontend/src/features/shopping-list/ListRow.test.tsx`, `frontend/src/features/shopping-list/ShoppingListScreen.test.tsx`
- Modify: `frontend/src/features/pantry/PantryRow.tsx`; Test: `frontend/src/features/pantry/PantryRow.test.tsx`, `frontend/src/features/pantry/PantryScreen.test.tsx`

**Interfaces:**
- Produces: `Button` accetta `busy?: boolean` (in `Common`, quindi in tutte e due le forme, con testo e di sola icona). `busy` → `aria-disabled="true"`, niente `disabled`; il clic non chiama `onClick` e, su un `type="submit"`, non invia il modulo. `disabled` resta invariato.

- [ ] **Step 1: I chiamanti di oggi**

Run (da `<worktree>/frontend`): `grep -rn -A8 "<Button" src --include=*.tsx | grep -v "\.test\." | grep "disabled"`
Expected, cinque righe: `ListRow.tsx` (~68), `PantryRow.tsx` (~132 e ~200), `IngredientPicker.tsx` (~126), `ErrorState.tsx` (~23). Le prime quattro, meno `IngredientPicker`, passano a `busy` in questo task; `IngredientPicker` resta (Fuori scope). Se l'elenco è diverso (un altro ramo fuso nel frattempo), migra solo quelle in cui `disabled` vuol dire «una richiesta partita da qui è in volo», e annotalo nel report.

- [ ] **Step 2: Scrivere i test di `Button` che falliscono**

In `frontend/src/components/ui/Button.test.tsx`, dentro il `describe("Button", …)` e dopo il test «compila solo se l'unione icona+etichetta è rispettata…», aggiungi:

```tsx
  // `busy` (T3 Consegna 2, «Restano aperti»): una richiesta partita da qui è in volo. Il
  // browser toglie il fuoco a un pulsante che diventa `disabled`, e chi usa la tastiera
  // lo ritrovava sul `body` dopo una ✕ fallita. jsdom non toglie il fuoco a un pulsante
  // che si spegne, ma rifiuta di darlo a uno già `disabled`: è questo che i test sotto
  // misurano. Il fuoco perso vero lo misura l'e2e (`style.spec.ts`).
  it("in volo è spento con aria-disabled, non con disabled, e un tocco non fa niente", () => {
    const onClick = vi.fn();
    render(<Button icon={IconTrash} label="Elimina" onClick={onClick} busy />);
    const button = screen.getByRole("button", { name: "Elimina" });
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button.hasAttribute("disabled")).toBe(false);
    fireEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("in volo resta raggiungibile dal fuoco", () => {
    render(<Button busy>Riprova</Button>);
    const button = screen.getByRole("button", { name: "Riprova" });
    button.focus();
    expect(button).toHaveFocus();
  });

  it("finito il volo torna a rispondere, e il fuoco non si è mosso", () => {
    const onClick = vi.fn();
    const { rerender } = render(<Button onClick={onClick} busy>Riprova</Button>);
    const button = screen.getByRole("button", { name: "Riprova" });
    button.focus();
    rerender(<Button onClick={onClick}>Riprova</Button>);
    expect(button).toHaveFocus();
    expect(button).not.toHaveAttribute("aria-disabled");
    fireEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("un submit in volo non invia il modulo", () => {
    const onSubmit = vi.fn((event: { preventDefault: () => void }) => event.preventDefault());
    render(
      <form onSubmit={onSubmit}>
        <Button type="submit" busy>
          Salva
        </Button>
      </form>
    );
    fireEvent.click(screen.getByRole("button", { name: "Salva" }));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("disabled resta, per un'azione che adesso non si può proprio fare", () => {
    render(<Button disabled>Salva</Button>);
    expect(screen.getByRole("button", { name: "Salva" })).toBeDisabled();
  });
```

e dentro il `describe("buttonClasses", …)`, dopo il test «il quadrato è un bersaglio da pollice…», aggiungi:

```tsx
  it("lo spento in volo si vede come lo spento vero, in ogni variante", () => {
    for (const variant of variants) {
      const classes = buttonClasses(variant).split(/\s+/);
      expect(classes, variant).toContain("disabled:opacity-40");
      expect(classes, variant).toContain("aria-disabled:opacity-40");
    }
  });
```

- [ ] **Step 3: Farli fallire**

Run: `npx vitest run src/components/ui/Button.test.tsx`
Expected: FAIL. `npm run typecheck` fallirebbe anche lui (`busy` non esiste su `Button`), ma vitest non controlla i tipi: falliscono i test su `aria-disabled`, sul tocco ignorato, sul submit e su `aria-disabled:opacity-40`; «in volo resta raggiungibile dal fuoco» e «disabled resta» possono già passare.

- [ ] **Step 4: Scrivere `busy`**

In `frontend/src/components/ui/buttonClasses.ts` sostituisci la riga di `BASE`:

```ts
const BASE = "inline-flex min-h-11 items-center justify-center gap-2 font-medium transition-colors disabled:opacity-40";
```

con:

```ts
// `aria-disabled:opacity-40` accanto a `disabled:opacity-40`: un pulsante in volo
// (`busy` in Button) si spegne con `aria-disabled` per tenere il fuoco, e deve
// sembrare spento come uno spento davvero
const BASE =
  "inline-flex min-h-11 items-center justify-center gap-2 font-medium transition-colors disabled:opacity-40 aria-disabled:opacity-40";
```

Sostituisci `frontend/src/components/ui/Button.tsx` per intero con:

```tsx
import type { MouseEvent, ReactNode } from "react";
import { buttonClasses, type ButtonShape, type ButtonVariant } from "./buttonClasses";
import type { IconComponent } from "./icons";

type Common = {
  variant?: ButtonVariant;
  shape?: ButtonShape;
  type?: "button" | "submit";
  onClick?: () => void;
  /** Un'azione che adesso non si può fare (un modulo incompleto). Il browser toglie il
   * fuoco a un pulsante che diventa `disabled`: per «sto già lavorando» c'è `busy`. */
  disabled?: boolean;
  /** Una richiesta partita da qui è in volo (T3 Consegna 2). Il pulsante si spegne con
   * `aria-disabled` e non con `disabled`, così tiene il fuoco: dopo una ✕ fallita chi
   * naviga da tastiera lo ritrovava sul `body`. Il tocco si ignora qui dentro, e non in
   * ogni chiamante, perché nessuno possa dimenticare la guardia — come fanno a mano le
   * tacche (`StockGauge`) e la casella della lista. */
  busy?: boolean;
  className?: string;
  "aria-describedby"?: string;
};

// Le due forme della regola delle icone (spec T3 §2), e nessuna terza: un pulsante di
// sola icona senza `label` non compila, perché un pulsante muto per uno screen reader
// è un pulsante che non c'è.
type WithText = Common & { children: ReactNode; icon?: IconComponent; label?: never };
type IconOnly = Common & { icon: IconComponent; label: string; children?: never };

export function Button(props: WithText | IconOnly) {
  const {
    variant = "secondary",
    type = "button",
    onClick,
    disabled,
    busy = false,
    className = "",
  } = props;
  const Icon = props.icon;
  const iconOnly = props.label !== undefined;
  const shape = props.shape ?? (iconOnly ? "icon" : "pill");

  function handleClick(event: MouseEvent<HTMLButtonElement>) {
    if (busy) {
      // anche l'invio del modulo: un submit in volo non deve partire una seconda volta
      event.preventDefault();
      return;
    }
    onClick?.();
  }

  return (
    <button
      type={type}
      onClick={handleClick}
      disabled={disabled}
      aria-disabled={busy || undefined}
      aria-label={iconOnly ? props.label : undefined}
      aria-describedby={props["aria-describedby"]}
      className={`${buttonClasses(variant, shape)} ${className}`}
    >
      {Icon && <Icon aria-hidden="true" className={iconOnly ? "size-5" : "size-[1.1em]"} stroke={1.8} />}
      {props.children}
    </button>
  );
}
```

- [ ] **Step 5: Farli passare**

Run: `npx vitest run src/components/ui/Button.test.tsx`
Expected: PASS, tutto il file.

- [ ] **Step 6: I test dei chiamanti, prima del codice**

`frontend/src/components/ui/States.test.tsx` — sostituisci il test:

```tsx
  it("mentre riprova il pulsante non si ripete", () => {
    render(<ErrorState message="x" onRetry={() => {}} retrying />);
    expect(screen.getByRole("button", { name: "Riprovo…" })).toBeDisabled();
  });
```

con:

```tsx
  it("mentre riprova il pulsante non si ripete, e tiene il fuoco", () => {
    const onRetry = vi.fn();
    render(<ErrorState message="x" onRetry={onRetry} retrying />);
    const button = screen.getByRole("button", { name: "Riprovo…" });
    // `aria-disabled` e non `disabled` (Button, `busy`): chi ha premuto «Riprova» da
    // tastiera non deve ritrovarsi il fuoco sulla pagina
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(button.hasAttribute("disabled")).toBe(false);
    fireEvent.click(button);
    expect(onRetry).not.toHaveBeenCalled();
  });
```

`frontend/src/features/shopping-list/ListRow.test.tsx` — nel test «mentre una scrittura è in volo la casella è spenta ma tiene il fuoco», sostituisci le tre righe finali:

```tsx
    const remove = screen.getByRole("button", { name: "Togli Total 0% dalla lista" });
    expect(remove.hasAttribute("disabled")).toBe(true);
    fireEvent.click(remove);
    expect(onRemove).not.toHaveBeenCalled();
```

con:

```tsx
    const remove = screen.getByRole("button", { name: "Togli Total 0% dalla lista" });
    expect(remove.hasAttribute("disabled")).toBe(false);
    expect(remove).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(remove);
    expect(onRemove).not.toHaveBeenCalled();
```

e subito dopo quel test aggiungi:

```tsx
  it("in volo anche la ✕ resta raggiungibile dal fuoco (T3 Consegna 2)", () => {
    // con `disabled` il browser toglieva il fuoco alla ✕ appena partiva la PATCH, e dopo
    // una ✕ fallita chi usa la tastiera lo ritrovava sulla pagina
    renderRow({}, { busy: true });
    const remove = screen.getByRole("button", { name: "Togli Total 0% dalla lista" });
    remove.focus();
    expect(remove).toHaveFocus();
  });
```

`frontend/src/features/shopping-list/ShoppingListScreen.test.tsx` — due asserzioni.

Nel test «la riga resta bloccata finché il riordino dopo la ✕ non è arrivato (regressione)», sostituisci:

```tsx
    expect(screen.getByRole("button", { name: "Togli pomodoro dalla lista" })).toBeDisabled();
    fireEvent.click(box);
    expect(spy.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(1);
    releaseGet(
```

con:

```tsx
    const remove = screen.getByRole("button", { name: "Togli pomodoro dalla lista" });
    expect(remove).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(box);
    fireEvent.click(remove);
    expect(spy.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(1);
    releaseGet(
```

(l'ultima riga, `releaseGet(`, resta com'è: serve solo a trovare il punto).

Nel test «mentre una scrittura è in volo, la stessa voce non ne parte una seconda», sostituisci:

```tsx
    fireEvent.click(box);
    expect(screen.getByRole("button", { name: "Togli pomodoro dalla lista" })).toBeDisabled();
    expect(spy.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(1);
```

con:

```tsx
    fireEvent.click(box);
    const remove = screen.getByRole("button", { name: "Togli pomodoro dalla lista" });
    expect(remove).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(remove);
    expect(spy.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(1);
```

`frontend/src/features/pantry/PantryRow.test.tsx` — nel test «mentre una scrittura è in volo i controlli sono spenti», sostituisci:

```tsx
    expect(screen.getByRole("button", { name: "In lista" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "Togli Total 0% dalla dispensa" }).hasAttribute("disabled")).toBe(true);
```

con:

```tsx
    // ✕ e «In lista» come le tacche: `aria-disabled` (Button, `busy`), e il tocco non parte
    for (const name of ["In lista", "Togli Total 0% dalla dispensa"]) {
      const button = screen.getByRole("button", { name });
      expect(button.hasAttribute("disabled")).toBe(false);
      expect(button).toHaveAttribute("aria-disabled", "true");
    }
    fireEvent.click(screen.getByRole("button", { name: "In lista" }));
    expect(onRestock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Togli Total 0% dalla dispensa" }));
    expect(onRemove).not.toHaveBeenCalled();
```

e nella prima riga del test sostituisci `const { onStatus } = renderRow({ status: "finished" }, { busy: true });` con `const { onStatus, onRestock, onRemove } = renderRow({ status: "finished" }, { busy: true });` (`renderRow` restituisce già tutti i gestori).

`frontend/src/features/pantry/PantryScreen.test.tsx` — tre asserzioni:
- intorno alla riga 105 e alla riga 469, sostituisci ciascuna delle due righe
  ```tsx
      expect(within(row).getByRole("button", { name: "Togli Total 0% dalla dispensa" })).toBeDisabled();
  ```
  con
  ```tsx
      expect(within(row).getByRole("button", { name: "Togli Total 0% dalla dispensa" })).toHaveAttribute("aria-disabled", "true");
  ```
- intorno alla riga 524 (test «un rientro in lista che fallisce lo dice nella riga, e «In lista» resta per riprovare»), sostituisci
  ```tsx
      expect(within(row).getByRole("button", { name: "In lista" })).not.toBeDisabled();
  ```
  con
  ```tsx
      // `not.toBeDisabled` passerebbe sempre, ora che il pulsante si spegne con
      // `aria-disabled`: si guarda l'attributo che conta
      expect(within(row).getByRole("button", { name: "In lista" })).not.toHaveAttribute("aria-disabled");
  ```

- [ ] **Step 7: Farli fallire**

Run: `npx vitest run src/components/ui/States.test.tsx src/features/shopping-list src/features/pantry`
Expected: FAIL su `aria-disabled` in `States.test.tsx`, `ListRow.test.tsx`, `ShoppingListScreen.test.tsx`, `PantryRow.test.tsx`, `PantryScreen.test.tsx` (i chiamanti passano ancora `disabled`), e su «in volo anche la ✕ resta raggiungibile dal fuoco».

- [ ] **Step 8: Migrare i chiamanti**

`frontend/src/components/ui/ErrorState.tsx` — sostituisci:

```tsx
      <Button icon={IconRefresh} onClick={onRetry} disabled={retrying}>
```

con:

```tsx
      {/* `busy` e non `disabled`: chi ha premuto «Riprova» da tastiera tiene il fuoco */}
      <Button icon={IconRefresh} onClick={onRetry} busy={retrying}>
```

`frontend/src/features/shopping-list/ListRow.tsx` — sostituisci:

```tsx
        <Button
          variant="ghost"
          icon={IconX}
          label={`Togli ${item.raw_text} dalla lista`}
          onClick={onRemove}
          disabled={busy}
        />
```

con:

```tsx
        {/* `busy` come la casella: con `disabled` il browser toglieva il fuoco alla ✕
            appena partiva la PATCH, e dopo una ✕ fallita lo si ritrovava sulla pagina */}
        <Button
          variant="ghost"
          icon={IconX}
          label={`Togli ${item.raw_text} dalla lista`}
          onClick={onRemove}
          busy={busy}
        />
```

`frontend/src/features/pantry/PantryRow.tsx` — sostituisci:

```tsx
        <Button
          variant="ghost"
          icon={IconX}
          label={`Togli ${label} dalla dispensa`}
          onClick={onRemove}
          disabled={busy}
        />
```

con:

```tsx
        <Button
          variant="ghost"
          icon={IconX}
          label={`Togli ${label} dalla dispensa`}
          onClick={onRemove}
          busy={busy}
        />
```

e sostituisci:

```tsx
            <Button icon={IconShoppingCartPlus} onClick={onRestock} disabled={busy}>
```

con:

```tsx
            <Button icon={IconShoppingCartPlus} onClick={onRestock} busy={busy}>
```

- [ ] **Step 9: Farli passare**

Run: `npx vitest run src/components/ui src/features/shopping-list src/features/pantry`
Expected: PASS.

- [ ] **Step 10: Le verifiche del frontend**

Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde; vitest 671 test (664 del Task 2, più 6 in `Button.test.tsx` e 1 in `ListRow.test.tsx`). Se il Task 2 non è ancora fatto, 670.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/components/ui/buttonClasses.ts frontend/src/components/ui/Button.tsx frontend/src/components/ui/Button.test.tsx frontend/src/components/ui/ErrorState.tsx frontend/src/components/ui/States.test.tsx frontend/src/features/shopping-list/ListRow.tsx frontend/src/features/shopping-list/ListRow.test.tsx frontend/src/features/shopping-list/ShoppingListScreen.test.tsx frontend/src/features/pantry/PantryRow.tsx frontend/src/features/pantry/PantryRow.test.tsx frontend/src/features/pantry/PantryScreen.test.tsx
git commit -m "ui: Button con busy, spento con aria-disabled; la ✕, «In lista» e «Riprova» tengono il fuoco"
```

---

### Task 4: Via `set_fill`

**Files:**
- Modify: `backend/app/api/pantry.py` (import e rotta `patch`)
- Modify: `backend/app/repositories/pantry.py` (`set_fill` via, import di `status_for_fill` via)
- Modify: `backend/app/schemas/pantry.py` (`PantryItemPatch.fill_percent` via)
- Modify: `backend/app/domain/rules.py` (solo il commento sopra `LOW_MAX_FILL`)
- Modify: `backend/app/db/models/pantry.py` (solo il commento sopra `fill_percent`)
- Test: `backend/tests/api/test_pantry.py`

**Interfaces:**
- Produces: `PATCH /api/v1/pantry/{id}` non accetta più `fill_percent`: il campo si ignora (lo schema non vieta i campi in più). `PantryItemOut.fill_percent` resta.

- [ ] **Step 1: Sostituire i test della via tolta con quello del comportamento nuovo**

In `backend/tests/api/test_pantry.py`:

1. Cancella per intero `test_la_posizione_arriva_con_lo_stato_gia_ricavato` (col suo `@pytest.mark.parametrize("posizione, stato_atteso", …)` sopra) e `test_una_posizione_fuori_scala_e_422`: provavano la via che questo task toglie.
2. Al loro posto aggiungi:

```python
async def test_la_posizione_non_si_scrive_piu(logged_client, db_session, dal_database, dispensa):
    """`set_fill` è stata tolta il 2026-09-29: dalla T3 Consegna 1 le tacche mandano lo
    stato, e una via di scrittura senza chiamanti è una porta che nessuno sorveglia (D1
    in docs/prossimi-passi.md). `PantryItemPatch` non vieta i campi in più, quindi
    `fill_percent` si ignora: da solo non resta niente da modificare, insieme allo stato
    vale solo lo stato. La colonna resta, e la risposta la porta ancora."""
    item = PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.AVAILABLE)
    db_session.add(item)
    await db_session.flush()

    sola = await logged_client.patch(f"/api/v1/pantry/{item.id}", json={"fill_percent": 10})
    assert sola.status_code == 400
    assert sola.json()["detail"] == "niente da modificare"
    assert (await dal_database(PantryItem, item.id)).status == "available"

    insieme = await logged_client.patch(
        f"/api/v1/pantry/{item.id}", json={"fill_percent": 10, "status": "low"}
    )
    assert insieme.status_code == 200
    assert insieme.json()["status"] == "low"
    assert insieme.json()["fill_percent"] is None
    assert (await dal_database(PantryItem, item.id)).fill_percent is None
```

3. In `test_cambiare_lo_stato_a_mano_azzera_la_posizione` la posizione non si può più scrivere con l'API: la si scrive nel database, come fa già `tests/api/test_cooking.py`. Sostituisci:

```python
    item = PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.AVAILABLE)
    db_session.add(item)
    await db_session.flush()
    await logged_client.patch(f"/api/v1/pantry/{item.id}", json={"fill_percent": 80})
```

con:

```python
    # una voce toccata prima del 2026-09-28 ha ancora la colonna piena
    item = PantryItem(
        ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.AVAILABLE, fill_percent=80
    )
    db_session.add(item)
    await db_session.flush()
```

Il resto del test (la PATCH con `status: finished` e le due asserzioni) resta com'è.

- [ ] **Step 2: Farlo fallire**

Run (da `<worktree>/backend`): `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/api/test_pantry.py`
Expected: FAIL in `test_la_posizione_non_si_scrive_piu`: `assert 200 == 400` (la via c'è ancora).

- [ ] **Step 3: Togliere la via**

`backend/app/api/pantry.py` — dall'import da `app.repositories.pantry` togli la riga `    set_fill,`. Nella rotta `patch` togli per intero il ramo:

```python
        elif payload.fill_percent is not None:
            # prima dello stato: in una richiesta che porta entrambi lo stato è una
            # conseguenza della posizione, non una seconda opinione. Nessun client la
            # manda più dal 2026-09-28 (T3 Consegna 1: le tacche mandano `status`),
            # e questa via resta senza chiamanti — vedi D1 in docs/prossimi-passi.md
            item = await set_fill(session, item_id, payload.fill_percent)
```

così che dopo il ramo `if payload.archived is not None:` venga subito `elif payload.status is not None:`.

`backend/app/repositories/pantry.py` — cancella per intero la funzione `set_fill` (da `async def set_fill(` fino al suo `return item`, con le due righe vuote che la separano dalla successiva), e nell'import in cima sostituisci:

```python
from app.domain.rules import Availability, PantryStatus, availability_of, status_for_fill
```

con:

```python
from app.domain.rules import Availability, PantryStatus, availability_of
```

`backend/app/schemas/pantry.py` — in `PantryItemPatch` cancella:

```python
    # dove il dito ha lasciato il cursore. Lo stato non si manda: lo ricava il
    # dominio, ed è l'unico modo perché i due non possano contraddirsi
    fill_percent: int | None = Field(default=None, ge=0, le=100)
```

e sopra la classe `PantryItemPatch` aggiungi il commento:

```python
# Niente `fill_percent`: dal 2026-09-29 non si scrive più (D1 in docs/prossimi-passi.md).
# Il modello non vieta i campi in più, quindi chi lo mandasse lo vedrebbe ignorato: da
# solo la rotta risponde 400 «niente da modificare».
```

(`Field` resta importato: lo usa `PantryItemCreate`.)

`backend/app/domain/rules.py` — sostituisci il commento sopra `LOW_MAX_FILL`:

```python
# La soglia di `status_for_fill`: fin qui è «quasi finito», oltre è «disponibile».
# 30 e non 50: la zona bassa deve dire «comincia a mancare», non «siamo a metà».
# Dal T3 Consegna 1 (2026-09-28) nessun client scrive più `fill_percent` — le tre
# tacche della dispensa mandano lo stato direttamente — ma la via `PATCH` che lo
# accetta (`set_fill`) resta nel backend, e questa soglia resta la sua unica lettura.
```

con:

```python
# La soglia di `status_for_fill`: fin qui è «quasi finito», oltre è «disponibile».
# 30 e non 50: la zona bassa deve dire «comincia a mancare», non «siamo a metà».
# Dal T3 Consegna 1 (2026-09-28) nessun client scrive più `fill_percent` — le tre
# tacche della dispensa mandano lo stato direttamente — e dal 2026-09-29 non c'è più
# nemmeno la via `PATCH` che lo accettava (`set_fill`, D1 in docs/prossimi-passi.md).
# `status_for_fill` non ha quindi chiamanti in produzione. Resta, coi suoi test,
# perché CLAUDE.md la cita come la regola che teneva d'accordo posizione e stato, e
# perché le voci toccate prima del 2026-09-28 hanno ancora la colonna piena.
```

(il paragrafo che segue, «È una soglia display con una conseguenza…», resta com'è).

`backend/app/db/models/pantry.py` — sostituisci il commento sopra `fill_percent`:

```python
    # Dove sta il cursore a tre zone, 0–100. È un'indicazione a occhio — utile in
    # negozio, e per seguire qualcosa che si consuma senza mai finire — non una
    # quantità: niente unità, niente conversioni, nessun conto la usa. Lo stato qui
    # sopra resta la verità, e `status_for_fill` è ciò che li tiene d'accordo.
    # NULL per chi non l'ha mai mosso.
```

con:

```python
    # Dove stava il cursore a tre zone, 0–100. Era un'indicazione a occhio, non una
    # quantità: niente unità, niente conversioni, nessun conto la usa. Lo stato qui
    # sopra resta la verità. Dal 2026-09-28 le tacche mandano lo stato e `set_status`
    # azzera la colonna; dal 2026-09-29 nessuna rotta la scrive più (D1 in
    # docs/prossimi-passi.md). Resta per le voci toccate prima, e per `PantryItemOut`.
    # NULL per chi non l'ha mai mosso.
```

- [ ] **Step 4: Farlo passare, e controllare che la via sia sparita**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/api/test_pantry.py tests/api/test_cooking.py tests/domain/test_rules.py tests/db/test_pantry_shopping_schema.py`
Expected: PASS.

Run (da `<worktree>`): `grep -rn "set_fill" backend/app backend/tests`
Expected: nessuna riga.

- [ ] **Step 5: La suite intera**

Run (da `<worktree>/backend`): `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q`
Expected: PASS; il conto è quello del Task 1 meno 5 (cinque casi parametrizzati e il test del 422 tolti, uno aggiunto).

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/pantry.py backend/app/repositories/pantry.py backend/app/schemas/pantry.py backend/app/domain/rules.py backend/app/db/models/pantry.py backend/tests/api/test_pantry.py
git commit -m "dispensa: via set_fill e la PATCH di fill_percent, senza chiamanti dalla Consegna 1"
```

---

### Task 5: Un 404 non si ritenta, e la ricetta sparita lo dice

**Files:**
- Modify: `frontend/src/lib/queryRetry.ts`
- Create: `frontend/src/lib/queryRetry.test.ts`
- Test: `frontend/src/App.test.tsx`
- Modify: `frontend/src/features/cooking/RecipeDetailScreen.tsx`; Test: `frontend/src/features/cooking/RecipeDetailScreen.test.tsx`
- Modify: `frontend/src/features/recipe-form/RecipeEditScreen.tsx`; Test: `frontend/src/features/recipe-form/RecipeEditScreen.test.tsx`
- Modify: `frontend/e2e/error-branch.spec.ts`

**Interfaces:**
- Produces: `defaultQueryRetryPredicate(count, error)` → falso per un `ApiError` con `status` 401 o 404, altrimenti `count < 2`.

- [ ] **Step 1: I test del predicato, prima del codice**

Crea `frontend/src/lib/queryRetry.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { ApiError, UnauthorizedError } from "../api/client";
import { defaultQueryRetryPredicate } from "./queryRetry";

// Il predicato vero, quello che App.tsx dà al suo QueryClient: i test di schermata si
// costruiscono il client con `retry: false` e non lo vedono mai (prima lezione di
// CLAUDE.md). `count` è il numero di tentativi già falliti oltre al primo.
describe("defaultQueryRetryPredicate", () => {
  it.each([
    ["un 500", new ApiError("errore 500", 500)],
    ["un 502 di Nginx", new ApiError("errore 502", 502)],
    ["un 409", new ApiError("conflitto", 409)],
    ["una rete che non risponde", new TypeError("Failed to fetch")],
  ])("%s si ritenta, due volte e non di più", (_nome, error) => {
    expect(defaultQueryRetryPredicate(0, error)).toBe(true);
    expect(defaultQueryRetryPredicate(1, error)).toBe(true);
    expect(defaultQueryRetryPredicate(2, error)).toBe(false);
  });

  it.each([
    ["un 401 (la sessione è scaduta)", new UnauthorizedError()],
    ["un 404 (la cosa chiesta non c'è)", new ApiError("ricetta inesistente", 404)],
  ])("%s non si ritenta mai", (_nome, error) => {
    expect(defaultQueryRetryPredicate(0, error)).toBe(false);
  });
});
```

- [ ] **Step 2: Farlo fallire**

Run (da `<worktree>/frontend`): `npx vitest run src/lib/queryRetry.test.ts`
Expected: FAIL solo nel caso «un 404 (la cosa chiesta non c'è) non si ritenta mai» (`expected true to be false`).

- [ ] **Step 3: Il predicato**

Sostituisci `frontend/src/lib/queryRetry.ts` per intero con:

```ts
import { ApiError } from "../api/client";

// Due risposte non si ritentano. Un 401: la sessione è scaduta e il rimbalzo al login
// è già partito (`UnauthorizedError` è un `ApiError` con 401). Un 404: la cosa chiesta
// non c'è, e chiederla di nuovo non la fa comparire — ritentarlo teneva lo schermo su
// «Carico…» per tre secondi, per poi offrire un «Riprova» che non poteva riuscire
// (Parte X di docs/prossimi-passi.md). Tutto il resto si ritenta, ma un numero finito
// di volte: un predicato che ignora il conteggio ritenta per sempre, `isError` non
// diventa mai vero e ogni ramo d'errore dell'app resta irraggiungibile — lo schermo
// resta su "Carico…" senza dire niente, che è il vicolo cieco che le regole di casa
// vietano.
const NOT_RETRIED = new Set([401, 404]);

export const defaultQueryRetryPredicate = (count: number, error: unknown) =>
  count < 2 && !(error instanceof ApiError && NOT_RETRIED.has(error.status));
```

Run: `npx vitest run src/lib/queryRetry.test.ts`
Expected: PASS, 6 test.

- [ ] **Step 4: I test delle due schermate e del client vero, prima del codice**

`frontend/src/App.test.tsx` — in fondo al `describe("App", …)`, dopo il test «un indirizzo che non esiste dice «Pagina non trovata» e porta alla lista», aggiungi:

```tsx
  it("una ricetta che non c'è più lo dice subito, senza ritentare, e riporta al ricettario", async () => {
    // Sul QueryClient vero dell'app, come la prova sul 500 qui sopra: gli schermi si
    // provano con `retry: false`, e un 404 ritentato non lo vedrebbero mai. Qui sì: con
    // i ritentativi il messaggio arriverebbe dopo le attese di 1 s e 2 s, fuori dal
    // secondo che `findBy` aspetta
    const fetchMock = vi.fn((url: string) =>
      Promise.resolve(
        String(url).includes("/recipes/r-sparita")
          ? new Response(JSON.stringify({ detail: "ricetta inesistente" }), { status: 404 })
          : new Response("[]", { status: 200 })
      )
    );
    vi.stubGlobal("fetch", fetchMock);
    window.history.pushState({}, "", "/ricette/r-sparita");

    render(<App />);

    expect(await screen.findByText("Questa ricetta non c'è più.")).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.filter(([url]) => String(url).includes("/recipes/r-sparita"))
    ).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Torna al ricettario" })).toHaveAttribute("href", "/ricette");
    expect(screen.queryByRole("button", { name: "Riprova" })).toBeNull();
  });
```

`frontend/src/features/cooking/RecipeDetailScreen.test.tsx` — dopo il test «un fallimento nel caricare la ricetta lo dice, non resta a caricare per sempre», aggiungi:

```tsx
  it("una ricetta che non c'è più lo dice, e riporta al ricettario invece di offrire «Riprova»", async () => {
    // un link vecchio, o una ricetta rifatta dall'import: riprovare non potrebbe riuscire
    vi.stubGlobal(
      "fetch",
      vi.fn((url: unknown) =>
        Promise.resolve(
          String(url).includes("/pantry")
            ? new Response("[]", { status: 200 })
            : new Response(JSON.stringify({ detail: "ricetta inesistente" }), { status: 404 })
        )
      )
    );
    renderScreen();
    expect(await screen.findByRole("alert")).toHaveTextContent("Questa ricetta non c'è più.");
    expect(screen.getByRole("link", { name: "Torna al ricettario" })).toHaveAttribute("href", "/ricette");
    expect(screen.queryByRole("button", { name: "Riprova" })).toBeNull();
  });

  it("un errore che non è un 404 offre ancora «Riprova»", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 500 })));
    renderScreen();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Non sono riuscito a caricare questa ricetta. Riprova."
    );
    expect(screen.getByRole("button", { name: "Riprova" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Torna al ricettario" })).toBeNull();
  });
```

`frontend/src/features/recipe-form/RecipeEditScreen.test.tsx` — dopo il test «con una copia in cache e la rilettura fallita, dice l'errore e non costruisce il modulo sulla copia», aggiungi:

```tsx
  it("una ricetta che non c'è più lo dice subito, e riporta al ricettario", async () => {
    stubFetch((path) =>
      path.includes("/recipes/r1") ? [{ detail: "ricetta inesistente" }, 404] : undefined
    );
    // `renderEdit` usa il predicato vero dell'app: un 404 ritentato arriverebbe dopo 3 s,
    // fuori dal secondo che `findBy` aspetta
    renderEdit();

    expect(await screen.findByText("Questa ricetta non c'è più.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Torna al ricettario" })).toHaveAttribute("href", "/ricette");
    expect(screen.queryByRole("button", { name: "Riprova" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Salva le modifiche" })).toBeNull();
    // e anche il ritorno in alto porta al ricettario, non alla ricetta che non c'è
    expect(screen.getByRole("link", { name: "Ricette" })).toHaveAttribute("href", "/ricette");
    expect(screen.queryByRole("link", { name: "Ricetta" })).toBeNull();
  });
```

- [ ] **Step 5: Farli fallire**

Run: `npx vitest run src/App.test.tsx src/features/cooking/RecipeDetailScreen.test.tsx src/features/recipe-form/RecipeEditScreen.test.tsx`
Expected: FAIL nei tre test sul 404 (`Unable to find an element with the text: Questa ricetta non c'è più.`). «un errore che non è un 404 offre ancora «Riprova»» passa già.

- [ ] **Step 6: Le due schermate**

`frontend/src/features/cooking/RecipeDetailScreen.tsx`:

Aggiungi l'import, dopo quello di `../pantry/api`:

```tsx
import { ApiError } from "../../api/client";
```

Nella `useQuery` della ricetta aggiungi `error: recipeError` alla destrutturazione:

```tsx
  const {
    data: recipe,
    error: recipeError,
    isLoading: isRecipeLoading,
    isError: isRecipeError,
    refetch: refetchRecipe,
  } = useQuery({
```

e sostituisci il blocco:

```tsx
  // un caricamento fallito non è una ricetta vuota: dirlo sarebbe una bugia su
  // cosa serve e cosa si ha
  if (isRecipeError || !recipe) {
    return (
```

con:

```tsx
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
```

(il `return (` che segue, con «Non sono riuscito a caricare questa ricetta. Riprova.» e il pulsante, resta com'è).

`frontend/src/features/recipe-form/RecipeEditScreen.tsx`:

Aggiungi l'import, dopo quello di `../recipes/api`:

```tsx
import { ApiError } from "../../api/client";
```

Sostituisci:

```tsx
  const { data: recipe, isError, isFetchedAfterMount, refetch } = useQuery({
```

con:

```tsx
  const { data: recipe, error, isError, isFetchedAfterMount, refetch } = useQuery({
```

e sostituisci il blocco:

```tsx
  if (isError || !recipe) {
    return (
      <Screen title={TITLE} back={back}>
        <Alert>Non sono riuscito a caricare questa ricetta.</Alert>
```

con:

```tsx
  // una ricetta che non c'è più risponde 404: niente «Riprova», che non potrebbe
  // riuscire, e anche il ritorno in alto porta al ricettario — tornare alla ricetta
  // sparita sarebbe un giro a vuoto
  if (error instanceof ApiError && error.status === 404) {
    return (
      <Screen title={TITLE} back={{ to: "/ricette", label: "Ricette" }}>
        <Alert>Questa ricetta non c'è più.</Alert>
        <Link to="/ricette" className={`${buttonClasses("secondary")} mt-3`}>
          Torna al ricettario
        </Link>
      </Screen>
    );
  }

  if (isError || !recipe) {
    return (
      <Screen title={TITLE} back={back}>
        <Alert>Non sono riuscito a caricare questa ricetta.</Alert>
```

(il resto di quel ramo, il ramo `archived_at` e il modulo restano com'erano). Il ramo del 404 sta dopo il `if (!isFetchedAfterMount)` e prima di quello dell'errore generico.

- [ ] **Step 7: Farli passare**

Run: `npx vitest run src/lib src/App.test.tsx src/features/cooking src/features/recipe-form src/features/registry src/features/recipe-import`
Expected: PASS (le ultime due cartelle usano il predicato vero, con i loro 404: devono restare verdi).

- [ ] **Step 8: La prova e2e del ramo d'errore**

`frontend/e2e/error-branch.spec.ts` deviava la lista su un 404 per provare che i ritentativi finiscono; ora un 404 non si ritenta e la prova non vedrebbe più la politica. Sostituisci:

```ts
  // Un 404 dal backend, non un 401: il 401 è una sessione scaduta e riporta
  // all'accesso per disegno, mentre qualunque altro errore è il caso che deve
  // diventare un messaggio. La deviazione resta attiva anche sui ritentativi.
  await page.route("**/api/v1/shopping-list?**", (route) =>
    route.continue({ url: new URL("/api/v1/rotta-che-non-esiste", page.url()).toString() })
  );
```

con:

```ts
  // Un errore del backend che non è né un 401 né un 404. Il 401 è una sessione scaduta
  // e riporta all'accesso per disegno; il 404 dal 2026-09-29 non si ritenta più (la
  // cosa chiesta non c'è, e richiederla non la fa comparire), quindi con quello questa
  // prova non vedrebbe la politica dei ritentativi. Un GET su una rotta che accetta solo
  // POST dà un 405 dal server vero, senza bisogno della sessione. La deviazione resta
  // attiva anche sui ritentativi.
  await page.route("**/api/v1/shopping-list?**", (route) =>
    route.continue({ url: new URL("/api/v1/auth/login", page.url()).toString() })
  );
```

Il resto del file resta com'è: la stima dei 10 s vale per ogni errore ritentato. Questa prova gira nel Task 8.

- [ ] **Step 9: Le verifiche del frontend**

Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde; 10 test in più di prima di questo task (6 del predicato, 1 in `App.test.tsx`, 2 nel dettaglio, 1 nella modifica).

- [ ] **Step 10: Commit**

```bash
git add frontend/src/lib/queryRetry.ts frontend/src/lib/queryRetry.test.ts frontend/src/App.test.tsx frontend/src/features/cooking/RecipeDetailScreen.tsx frontend/src/features/cooking/RecipeDetailScreen.test.tsx frontend/src/features/recipe-form/RecipeEditScreen.tsx frontend/src/features/recipe-form/RecipeEditScreen.test.tsx frontend/e2e/error-branch.spec.ts
git commit -m "query: un 404 non si ritenta; una ricetta sparita dice «Questa ricetta non c'è più.»"
```

---

### Task 6: `occurrences` dopo l'annullamento

**Files:**
- Modify: `backend/app/services/recipe_import/terms.py` (`count_pending_keys`, `PendingKeys`; `sync_terms` li usa)
- Modify: `backend/app/services/recipe_import/undo.py` (`undo_decision`)
- Test: `backend/tests/services/test_undo.py`

**Interfaces:**
- Produces: in `app/services/recipe_import/terms.py`:
  - `@dataclass(frozen=True) class PendingKeys` con `occurrences: dict[str, int]` (ricette in attesa per chiave) e `display_names: dict[str, str]` (il primo nome letto per chiave, tagliato a 200 caratteri);
  - `def count_pending_keys(pages: Iterable[RecipeImport]) -> PendingKeys`, pura.
- `undo_decision` e `Undone` non cambiano firma.

- [ ] **Step 1: Scrivere i test che falliscono**

In fondo a `backend/tests/services/test_undo.py` aggiungi:

```python
# --- `occurrences` dopo l'annullamento (T3, esito del giro, «1 ricetta in attesa») ---


async def test_dopo_lannullamento_occurrences_conta_le_ricette_in_attesa(
    db_session, deciso, dal_database
):
    """La riproduzione del giro: «Ics» deciso, una seconda ricetta con «Ics» scaricata e
    importata dopo (il conto resta 1, perché al secondo scarico la prima era già
    dentro), poi annulla — e la coda diceva «1 ricetta in attesa» sopra due titoli.
    `occurrences` si ricalcolava solo a ogni scarico (`sync_terms`)."""
    term, speck, _, _ = deciso
    seconda = await create_recipe(
        db_session, title="Pasta Q", description=None, instructions="cuoci",
        servings=2, source=RecipeSource.DATASET, source_ref="https://esempio.invalid/2",
        ingredients=[(speck.id, "primary", "80 g", None)], embedding=None,
    )
    db_session.add(RecipeImport(
        source=GIALLOZAFFERANO, url="https://esempio.invalid/2",
        payload={"title": "Pasta Q", "ingredients": [{"key": "k-speck", "name": "Speck"}]},
        state=ImportState.IMPORTED, recipe_id=seconda.id,
    ))
    await db_session.flush()
    assert term.occurrences == 1

    esito = await undo_decision(db_session, term)

    assert esito.recipes_requeued == 2
    assert (await dal_database(ImportTerm, term.id)).occurrences == 2


async def test_il_riconteggio_guarda_solo_le_pagine_in_attesa_che_nominano_il_termine(
    db_session, deciso, dal_database
):
    """Una pagina già in attesa per un altro termine conta anche per questo; una presa
    in carico (R10) no, e nemmeno una in attesa che il termine non lo nomina."""
    term, _, _, _ = deciso
    db_session.add_all([
        RecipeImport(
            source=GIALLOZAFFERANO, url="https://esempio.invalid/attesa",
            payload={"title": "Speck e bottarga", "ingredients": [
                {"key": "k-speck", "name": "Speck"},
                {"key": "k-bottarga", "name": "Bottarga"},
            ]},
            state=ImportState.PENDING,
        ),
        RecipeImport(
            source=GIALLOZAFFERANO, url="https://esempio.invalid/altro",
            payload={"title": "Solo bottarga",
                     "ingredients": [{"key": "k-bottarga", "name": "Bottarga"}]},
            state=ImportState.PENDING,
        ),
        RecipeImport(
            source=GIALLOZAFFERANO, url="https://esempio.invalid/tua",
            payload={"title": "Speck mio", "ingredients": [{"key": "k-speck", "name": "Speck"}]},
            state=ImportState.ADOPTED,
        ),
    ])
    await db_session.flush()

    await undo_decision(db_session, term)

    # la pagina del fixture, rimessa in coda, più quella che aspettava già
    assert (await dal_database(ImportTerm, term.id)).occurrences == 2
```

(Tutti i nomi usati — `create_recipe`, `RecipeSource`, `RecipeImport`, `ImportState`, `ImportTerm`, `GIALLOZAFFERANO` — sono già importati in cima al file; `dal_database` è in `tests/conftest.py`.)

- [ ] **Step 2: Farli fallire**

Run (da `<worktree>/backend`): `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/services/test_undo.py`
Expected: FAIL nei due test nuovi, `assert 1 == 2` (il conto resta quello del fixture).

- [ ] **Step 3: La funzione comune**

In `backend/app/services/recipe_import/terms.py`:

Sostituisci gli import:

```python
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
```

con:

```python
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, RecipeImport, TermDecision
```

Subito dopo la classe `TermsSynced` aggiungi:

```python
@dataclass(frozen=True)
class PendingKeys:
    """Quel che le pagine in attesa dicono dei loro termini."""

    # le ricette in attesa per chiave: una ricetta conta una volta, anche se nomina il
    # termine in due righe
    occurrences: dict[str, int]
    # il primo nome letto per ogni chiave, già tagliato alla colonna
    display_names: dict[str, str]


def count_pending_keys(pages: Iterable[RecipeImport]) -> PendingKeys:
    """`occurrences` conta le **ricette** in attesa che usano il termine, non le righe:
    la frolla e la crema vogliono entrambe lo zucchero a velo, ma la ricetta bloccata è
    una. Una funzione sola per `sync_terms` e per `undo_decision`: due conteggi scritti
    due volte divergono, e la coda direbbe numeri diversi a seconda di chi l'ha
    toccata per ultimo.
    """
    occurrences: dict[str, int] = {}
    display_names: dict[str, str] = {}
    for page in pages:
        keys_here = set()
        for line in page.payload.get("ingredients") or []:
            key = line.get("key")
            if not key:
                continue
            keys_here.add(key)
            display_names.setdefault(key, str(line.get("name") or key)[:200])
        for key in keys_here:
            occurrences[key] = occurrences.get(key, 0) + 1
    return PendingKeys(occurrences=occurrences, display_names=display_names)
```

In `sync_terms` sostituisci la docstring e il conteggio:

```python
    """Allinea il dizionario alle pagine in attesa.

    `occurrences` conta le **ricette** in attesa che usano il termine, non le righe:
    la frolla e la crema vogliono entrambe lo zucchero a velo, ma la ricetta
    bloccata è una. Si ricalcola a ogni passaggio e non si incrementa mai: un
    contatore incrementato divergerebbe al primo ri-scarico, e un ordinamento della
    coda basato su un numero sbagliato è un difetto che nessuno nota.
    """
    occurrences: dict[str, int] = {}
    display_names: dict[str, str] = {}
    for page in await pending_pages(session, source):
        keys_here = set()
        for line in page.payload.get("ingredients") or []:
            key = line.get("key")
            if not key:
                continue
            keys_here.add(key)
            display_names.setdefault(key, str(line.get("name") or key)[:200])
        for key in keys_here:
            occurrences[key] = occurrences.get(key, 0) + 1
```

con:

```python
    """Allinea il dizionario alle pagine in attesa.

    `occurrences` (vedi `count_pending_keys`) si ricalcola a ogni passaggio e non si
    incrementa mai: un contatore incrementato divergerebbe al primo ri-scarico, e un
    ordinamento della coda basato su un numero sbagliato è un difetto che nessuno nota.
    L'altro posto che lo ricalcola è `undo_decision`, per il termine annullato.
    """
    counted = count_pending_keys(await pending_pages(session, source))
    occurrences = counted.occurrences
    display_names = counted.display_names
```

Il resto di `sync_terms` resta com'è.

- [ ] **Step 4: Il riconteggio nell'annullamento**

In `backend/app/services/recipe_import/undo.py` aggiungi gli import, dopo `from app.domain.rules import cost_in_scale`:

```python
from app.repositories.imports import pending_pages
```

e dopo `from app.services.recipe_import.materialize import COOKING_EVENTS_KEY`:

```python
from app.services.recipe_import.terms import count_pending_keys
```

In `undo_decision`, subito dopo il blocco

```python
    term.decision = TermDecision.PENDING
    term.ingredient_id = None
    term.role_override = None
    term.decided_by = None
    term.decided_at = None
    term.created_ingredient = None
    await session.flush()
```

aggiungi:

```python

    # `occurrences` si ricalcolava solo a ogni scarico (`sync_terms`): le pagine appena
    # rimesse in coda restavano fuori dal conto, e la coda diceva «1 ricetta in attesa»
    # sopra due titoli (T3, esito del giro). Si riconta il termine annullato, e solo
    # lui, con la funzione di `sync_terms`, dopo il `flush` che ha scritto le pagine
    # tornate `pending`. Gli altri termini di quelle pagine si riallineano al prossimo
    # scarico, come prima.
    counted = count_pending_keys(await pending_pages(session, term.source))
    term.occurrences = counted.occurrences.get(term.term_key, 0)
```

Il `await session.flush()` in fondo alla funzione scrive il valore. Aggiorna anche la docstring di `undo_decision` all'ordine vero del codice, sostituendo:

```python
    Quattro effetti, in quest'ordine: le pagine e le ricette, l'alias, l'ingrediente
    (solo se il termine ne possiede la cancellazione, `created_ingredient`), il termine. Nessuno rifiuta: le ricette già
    cucinate si rifanno come le altre, perché le loro cotture aspettano nel `payload`
    (vedi la docstring del modulo).
```

con:

```python
    Quattro effetti, in quest'ordine: le pagine e le ricette, il termine (col suo
    `occurrences` ricontato), l'alias, l'ingrediente (solo se il termine ne possiede la
    cancellazione, `created_ingredient`). Nessuno rifiuta: le ricette già cucinate si
    rifanno come le altre, perché le loro cotture aspettano nel `payload` (vedi la
    docstring del modulo).
```

- [ ] **Step 5: Farli passare**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/services/test_undo.py tests/services/test_import_terms.py tests/api/test_imports_undo.py tests/services/test_registry_merge.py`
Expected: PASS (i test di `sync_terms` in `test_import_terms.py` provano ora `count_pending_keys` attraverso il suo chiamante vero).

- [ ] **Step 6: La suite intera**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q`
Expected: PASS; il conto del Task 4 più 2.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/recipe_import/terms.py backend/app/services/recipe_import/undo.py backend/tests/services/test_undo.py
git commit -m "import: l'annullamento riconta le ricette in attesa del termine, con la funzione di sync_terms"
```

---

### Task 7: L'elenco dei suggerimenti scorre da sé

**Files:**
- Modify: `frontend/src/components/ui/OptionList.tsx`

La prova è nel browser (Task 8): jsdom non calcola il CSS (quarta lezione di `CLAUDE.md`), e una classe presente in un test di unità non dice niente di un elenco che esce dallo schermo.

- [ ] **Step 1: L'altezza massima**

In `frontend/src/components/ui/OptionList.tsx` sostituisci:

```tsx
    <div
      role="listbox"
      aria-label={fieldLabel ? `Suggerimenti: ${fieldLabel}` : undefined}
      className="flex flex-col overflow-hidden rounded-card bg-card"
    >
```

con:

```tsx
    // L'elenco scorre da sé, alto al più 18rem o il 45% della finestra *dinamica*: sotto
    // la barra appiccicata della lista, su uno schermo basso con la tastiera aperta, gli
    // ultimi suggerimenti chiedevano di scorrere la pagina (T3 Consegna 2, «Restano
    // aperti»). `dvh` segue la finestra vera, che la tastiera accorcia; `overscroll-contain`
    // tiene lo scorrimento dentro l'elenco quando arriva in fondo. `overflow-y-auto` taglia
    // gli angoli come faceva `overflow-hidden`
    <div
      role="listbox"
      aria-label={fieldLabel ? `Suggerimenti: ${fieldLabel}` : undefined}
      className="flex max-h-[min(18rem,45dvh)] flex-col overflow-y-auto overscroll-contain rounded-card bg-card"
    >
```

- [ ] **Step 2: I due chiamanti non si rompono**

Run (da `<worktree>/frontend`): `npx vitest run src/features/shopping-list src/components && npm run typecheck && npm run lint && npm run build`
Expected: tutto verde. Poi, sul CSS costruito: `grep -c "45dvh" dist/assets/*.css` stampa almeno un 1 (la classe arbitraria è stata generata; si cerca solo `45dvh` perché il minificatore può riscrivere il resto della funzione). Se stampa 0, Tailwind non ha riconosciuto la classe: controlla che nel sorgente non ci siano spazi dentro le parentesi quadre.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ui/OptionList.tsx
git commit -m "ui: i suggerimenti scorrono nel loro elenco, alto al più min(18rem, 45dvh)"
```

---

### Task 8: L'e2e — i suggerimenti, il fuoco dopo una ✕ fallita, le pulizie che fanno fallire

**Files:**
- Modify: `frontend/e2e/style.spec.ts` (import; due blocchi di pulizia; due test nuovi in fondo)

Lo stack e2e prova anche `frontend/e2e/error-branch.spec.ts`, cambiato nel Task 5.

- [ ] **Step 1: L'import del tipo**

In cima a `frontend/e2e/style.spec.ts` sostituisci:

```ts
import type { RecipeDraft } from "../src/domain/types.ts";
```

con:

```ts
import type { Ingredient, RecipeDraft } from "../src/domain/types.ts";
```

- [ ] **Step 2: La prima pulizia vecchia (la voce di farina di `perOgniLuogo`)**

Sostituisci:

```ts
  } finally {
    // prima che i cookie spariscano (in fondo a questa funzione, per la schermata
    // d'accesso): dopo, una PATCH autenticata non arriverebbe da nessuna parte e la
    // voce resterebbe, crescendo la dispensa a ogni esecuzione su uno stack riusato
    try {
      await page.request.patch(`/api/v1/pantry/${riempimentoId}`, { data: { archived: true } });
    } catch (guasto) {
      console.warn(`pulizia: non sono riuscito ad archiviare la voce ${riempimentoId}`, guasto);
    }
  }
```

con:

```ts
  } finally {
    // prima che i cookie spariscano (in fondo a questa funzione, per la schermata
    // d'accesso): dopo, una PATCH autenticata non arriverebbe da nessuna parte e la
    // voce resterebbe, crescendo la dispensa a ogni esecuzione su uno stack riusato.
    // `expect.soft` e non un'asserzione: un `finally` che lancia nasconderebbe l'errore
    // vero del `try`, ma la prova risulta comunque fallita, così una voce rimasta non
    // passa per un successo silenzioso (come la pulizia della barra della lista, in
    // fondo al file)
    try {
      const risposta = await page.request.patch(`/api/v1/pantry/${riempimentoId}`, {
        data: { archived: true },
      });
      expect.soft(risposta.ok(), `pulizia: la voce ${riempimentoId} non si è archiviata`).toBe(true);
    } catch (guasto) {
      expect
        .soft(false, `pulizia: non sono riuscito ad archiviare la voce ${riempimentoId} (${guasto})`)
        .toBe(true);
    }
  }
```

- [ ] **Step 3: La seconda pulizia vecchia (voce e prodotto)**

Sostituisci:

```ts
  } finally {
    // best-effort e senza asserzioni, come in `anagrafica.spec.ts`: un `finally` che
    // solleva nasconderebbe l'errore vero del `try`. Prima la voce, poi il prodotto
    if (voceId) {
      try {
        await page.request.patch(`/api/v1/pantry/${voceId}`, { data: { archived: true } });
      } catch (guasto) {
        console.warn(`pulizia: non sono riuscito ad archiviare la voce ${voceId}`, guasto);
      }
    }
    try {
      await page.request.delete(`/api/v1/products/${prodottoId}`);
    } catch (guasto) {
      console.warn(`pulizia: non sono riuscito a eliminare il prodotto ${prodottoId}`, guasto);
    }
  }
```

con:

```ts
  } finally {
    // Un `finally` che lancia nasconderebbe l'errore vero del `try`: ogni passo resta un
    // `expect.soft`, che non lancia e non salta il passo dopo, ma segna la prova fallita
    // — una voce o un prodotto rimasti non passano per un successo silenzioso. Prima la
    // voce, poi il prodotto
    if (voceId) {
      try {
        const risposta = await page.request.patch(`/api/v1/pantry/${voceId}`, {
          data: { archived: true },
        });
        expect.soft(risposta.ok(), `pulizia: la voce ${voceId} non si è archiviata`).toBe(true);
      } catch (guasto) {
        expect
          .soft(false, `pulizia: non sono riuscito ad archiviare la voce ${voceId} (${guasto})`)
          .toBe(true);
      }
    }
    try {
      const risposta = await page.request.delete(`/api/v1/products/${prodottoId}`);
      expect.soft(risposta.ok(), `pulizia: il prodotto ${prodottoId} non si è eliminato`).toBe(true);
    } catch (guasto) {
      expect
        .soft(false, `pulizia: non sono riuscito a eliminare il prodotto ${prodottoId} (${guasto})`)
        .toBe(true);
    }
  }
```

(`DELETE /api/v1/products/{id}` risponde 200 con il conto delle voci rimaste sfuse: `ok()` è vero.)

Run (da `<worktree>`): `grep -n "console.warn" frontend/e2e/style.spec.ts`
Expected: nessuna riga.

- [ ] **Step 4: I due test nuovi**

In fondo a `frontend/e2e/style.spec.ts`, dopo l'ultimo test («la barra della lista resta sotto l'intestazione scorrendo, e la ✕ offre «Annulla»»), aggiungi due blocchi `test(...)` a sé:

```ts
test("i suggerimenti sotto la barra della lista scorrono nel loro elenco, dentro la finestra", async ({
  page,
}) => {
  // T3 Consegna 2, «Restano aperti»: l'elenco non aveva un'altezza massima, e su uno
  // schermo basso con la tastiera aperta gli ultimi suggerimenti chiedevano di scorrere
  // la pagina. Dodici suggerimenti li dà `page.route`: l'anagrafica del seme non ne ha
  // dodici che somiglino alla stessa parola, e lo schermo, il componente e il CSS sono
  // quelli veri. Niente si scrive, quindi niente da pulire.
  //
  // il `beforeEach` tocca «Entra» ma non aspetta la risposta: senza quest'attesa la
  // navigazione qui sotto può partire prima che il cookie di sessione sia scritto
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  const suggerimenti = Array.from({ length: 12 }, (_, i) => ({
    id: `00000000-0000-4000-8000-${String(i + 1).padStart(12, "0")}`,
    name: `prova suggerimento ${i + 1}`,
    display_name: `Prova suggerimento ${i + 1}`,
    category: "altro",
    kind: "food" as const,
  })) satisfies Ingredient[];
  await page.route("**/api/v1/ingredients/search?**", (route) =>
    route.fulfill({ json: suggerimenti })
  );

  // 375×812 è un telefono con la tastiera chiusa; 375×450 uno con la tastiera aperta,
  // che accorcia la finestra: `45dvh` deve seguirla
  for (const altezza of [812, 450]) {
    await page.setViewportSize({ width: 375, height: altezza });
    await page.goto("/lista");
    await page.getByLabel("Aggiungi alla lista", { exact: true }).fill("prova");
    const elenco = page.getByRole("listbox", { name: "Suggerimenti: Aggiungi alla lista" });
    await expect(elenco.getByRole("option")).toHaveCount(12);

    const scatola = await elenco.boundingBox();
    expect(
      scatola!.y + scatola!.height,
      `a 375×${altezza} l'elenco dei suggerimenti esce dalla finestra`
    ).toBeLessThanOrEqual(altezza);
    expect(
      await elenco.evaluate((el) => el.scrollHeight - el.clientHeight),
      `a 375×${altezza} l'elenco non scorre da sé`
    ).toBeGreaterThan(0);

    // l'ultimo si raggiunge scorrendo l'elenco
    await elenco.hover();
    await page.mouse.wheel(0, 2000);
    await expect.poll(() => elenco.evaluate((el) => el.scrollTop)).toBeGreaterThan(0);
    await expect(elenco.getByRole("option", { name: "Prova suggerimento 12" })).toBeInViewport();
  }
});

test("dopo una ✕ fallita in lista il fuoco resta sulla ✕", async ({ page }) => {
  // T3 Consegna 2, «Restano aperti»: la ✕ si spegneva con `disabled` mentre la PATCH era
  // in volo, e il browser toglie il fuoco a un pulsante che diventa `disabled` — chi
  // usa la tastiera lo ritrovava sulla pagina. jsdom non lo fa, quindi lo vede solo un
  // browser. La PATCH la fa fallire `page.route`, dopo un'attesa che lascia vedere la ✕
  // in volo; la voce la crea l'API e la toglie il `finally` (`page.request` non passa
  // da `page.route`).
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  const creata = await page.request.post("/api/v1/shopping-list", {
    data: { raw_text: "prova fuoco", ingredient_id: null },
  });
  expect(creata.ok()).toBe(true);
  const id = ((await creata.json()) as { id: string }).id;
  const rotta = `**/api/v1/shopping-list/${id}`;
  try {
    await page.route(rotta, async (route) => {
      if (route.request().method() !== "PATCH") return route.continue();
      await new Promise((resolve) => setTimeout(resolve, 1000));
      return route.fulfill({ status: 500, json: { detail: "guasto di prova" } });
    });
    await page.goto("/lista");
    const togli = page.getByRole("button", { name: "Togli prova fuoco dalla lista" });
    await togli.focus();
    await page.keyboard.press("Enter");

    // in volo: spenta, ma col fuoco
    await expect(togli).toHaveAttribute("aria-disabled", "true");
    await expect(togli).toBeFocused();
    // fallita: il messaggio nella riga, la ✕ di nuovo attiva, e il fuoco ancora lì
    const riga = page.getByRole("listitem").filter({ has: togli });
    await expect(riga.getByRole("alert")).toBeVisible();
    await expect(togli).not.toHaveAttribute("aria-disabled", "true");
    await expect(togli).toBeFocused();
  } finally {
    await page.unroute(rotta);
    try {
      const risposta = await page.request.patch(`/api/v1/shopping-list/${id}`, {
        data: { status: "archived" },
      });
      expect.soft(risposta.ok(), `pulizia: la voce ${id} non si è archiviata`).toBe(true);
    } catch (guasto) {
      expect.soft(false, `pulizia: non sono riuscito ad archiviare la voce ${id} (${guasto})`).toBe(true);
    }
  }
});
```

- [ ] **Step 5: Il type check dell'e2e**

`frontend/e2e` lo compila `tsconfig.node.json`, che `npm run typecheck` include.

Run (da `<worktree>/frontend`): `npm run typecheck && npm run lint`
Expected: tutto verde.

- [ ] **Step 6: Lo stack e2e, e l'e2e intera**

Dalla radice di `<worktree>` (prima: `docker ps --format '{{.Names}}' | grep spena-e2e` — se c'è uno stack di un altro ramo, aspetta che sparisca):

```bash
cp .env.example .env
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed --con-ricette
(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
```

Expected: tutti i test passano, due più di prima (i due nuovi di `style.spec.ts`), compreso `error-branch.spec.ts` con la deviazione sul 405. Se un test fallisce e lascia dati nello stack, prima di rieseguire ricrea lo stack da zero (`down -v`, `up`, seme). Se fallisce una delle due pulizie convertite con un messaggio `pulizia: …`, non è un difetto della conversione: è una pulizia che falliva già in silenzio — diagnostica la rotta (una PATCH o una DELETE che non risponde `ok`) e annotalo nel report; non tornare al `console.warn`.

Poi, sempre dalla radice di `<worktree>`:

```bash
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
rm .env
```

- [ ] **Step 7: Commit**

```bash
git add frontend/e2e/style.spec.ts
git commit -m "e2e: i suggerimenti scorrono dentro la finestra, la ✕ fallita tiene il fuoco, le pulizie vecchie fanno fallire"
```

---

### Task 9: I documenti

**Files:**
- Modify: `docs/prossimi-passi.md`
- Modify: `next-steps.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: `docs/prossimi-passi.md`, i quattro punti di «Restano aperti»**

Nella voce T3, subito dopo il paragrafo che comincia con «**Restano aperti, da questa consegna:**» (e finisce con «…a differenza di quella più recente per la barra della lista.»), aggiungi il paragrafo:

```markdown
**Chiusi tutti e quattro il 2026-09-29**, sul ramo `night/pulizie-dopo-la-lista` (piano
`docs/superpowers/plans/2026-09-29-pulizie-dopo-la-lista.md`), non ancora in produzione.
Il doppione: la `PATCH` che riporta una voce archiviata a `pending` o `checked` risponde
409 («l'ingrediente è già in lista») se lo stesso ingrediente è già da comprare o nel
carrello in un'altra voce, e non cambia niente; «Annulla» su quel 409 dice «Era già in
lista.», e la cache del client resta la via veloce. La ✕: `Button` ha `busy`, che spegne
con `aria-disabled` e ignora il tocco dentro il primitivo; lo usano la ✕ della lista, la ✕ e
«In lista» della dispensa e il «Riprova» di `ErrorState`, e `disabled` resta per ciò che
non si può proprio fare. `IngredientPicker` spegne ancora campo e suggerimenti con
`disabled` mentre la scelta è in volo: è in `next-steps.md` come idea. I suggerimenti:
`OptionList` scorre da sé, alto al più `min(18rem, 45dvh)`, per la barra della lista e
per `IngredientPicker`; l'e2e lo misura a 375×812 e a 375×450. La pulizia e2e vecchia di
`style.spec.ts` usa ora `expect.soft` come la nuova.
```

- [ ] **Step 2: `docs/prossimi-passi.md`, Parte X e il giro**

In Parte X, in fondo alla voce «**Un 404 viene ritentato e poi offre «Riprova».**» (dopo «Dal giro di T3, verificato sul codice.»), aggiungi:

```markdown
  *(Fatto il 2026-09-29, ramo `night/pulizie-dopo-la-lista`: `defaultQueryRetryPredicate`
  non ritenta né il 401 né il 404, e dettaglio e modifica della ricetta dicono «Questa
  ricetta non c'è più.» con «Torna al ricettario». La prova e2e del ramo d'errore
  (`error-branch.spec.ts`) ora devia la lista su un 405, perché su un 404 non vedrebbe
  più i ritentativi.)*
```

Nella voce T3, sezione «Esito del giro», sotto «**Ingredienti da abbinare**», in fondo alla voce «**«1 ricetta in attesa»** compare con due ricette elencate sotto.» (dopo «Il rimedio è ricontare le pagine in attesa del termine dentro `undo_decision`.»), aggiungi:

```markdown
  *(Fatto il 2026-09-29, ramo `night/pulizie-dopo-la-lista`: `undo_decision` riconta il
  termine annullato con `count_pending_keys`, la stessa funzione di `sync_terms`.)*
```

- [ ] **Step 3: `docs/prossimi-passi.md`, la nota di D1**

Nella «**Nota 2026-09-17.**» sotto D1, sostituisci le ultime due righe:

```markdown
> nessuno scrive più la colonna. La via `PATCH` di `fill_percent` resta nel backend
> senza chiamanti, ed è una voce piccola da togliere quando si tocca `api/pantry.py`.
```

con:

```markdown
> nessuno scrive più la colonna. Dal 2026-09-29 (ramo `night/pulizie-dopo-la-lista`)
> non c'è più nemmeno la via `PATCH` che la accettava: `set_fill` è tolta, e un
> `fill_percent` mandato si ignora (da solo la rotta risponde 400, «niente da
> modificare»). La colonna resta, annullabile, col suo CHECK e in `PantryItemOut`, e
> `set_status` la azzera; toglierla è una migrazione, e le voci toccate prima del
> 2026-09-28 l'hanno ancora piena. `status_for_fill` resta in `app/domain/rules.py` coi
> suoi test, senza chiamanti in produzione, perché `CLAUDE.md` la cita.
```

- [ ] **Step 4: `CLAUDE.md`**

Nel paragrafo «**1. No quantities, in the pantry.**», sostituisci:

```markdown
directly, and `set_status` clears the column. It stays in the schema, nullable, with
its `PATCH` path (`set_fill`) still accepted by the API and used by nobody. The
three statuses stay the only truth the rest of the app reasons on.
```

con:

```markdown
directly, and `set_status` clears the column. It stays in the schema, nullable, with
its CHECK and its place in `PantryItemOut`; the `PATCH` path that wrote it
(`set_fill`) was removed on 2026-09-29, so nothing writes it now, and a `PATCH`
carrying only `fill_percent` is answered 400. `status_for_fill` stays in `rules.py`
with its tests and no production caller. The
three statuses stay the only truth the rest of the app reasons on.
```

- [ ] **Step 5: `next-steps.md`**

1. La riga in testa diventa `_Ultimo aggiornamento: 2026-09-29 (fase notte)_`.
2. Da «### Code della Consegna 2 e pulizie» togli queste sette righe (resta solo quella dei suggerimenti «sempre dieci righe»):
   - «Il doppione sull'«Annulla» della ✕ in Lista…»
   - «La ✕ di Lista usa ancora `disabled`…»
   - «I suggerimenti sotto la barra appiccicata della Lista non hanno un'altezza massima…»
   - «La vecchia pulizia e2e di `style.spec.ts`…»
   - «Togliere `set_fill` e la sua `PATCH` dal backend…»
   - «Un 404 viene ritentato e poi offre «Riprova»…»
   - ««1 ricetta in attesa» con due ricette sotto…»
3. In cima a «## Fatti (recenti)» aggiungi:
   ```markdown
   - [fatto] 2026-09-29 · Pulizie dopo la Lista: il 409 sull'«Annulla» che farebbe un doppione, `Button` con `busy` (la ✕ tiene il fuoco), i suggerimenti che scorrono da sé, le pulizie e2e che fanno fallire, via `set_fill`, il 404 non ritentato con «Questa ricetta non c'è più.», `occurrences` ricontato dopo l'annullamento → branch night/pulizie-dopo-la-lista (da revisionare)
   ```
4. In «### Idee» aggiungi:
   ```markdown
   - [idea] P3 · `IngredientPicker` spegne campo, suggerimenti e «Aggiungi «…»» con `disabled` mentre la scelta è in volo: lo stesso fuoco perso della ✕ di Lista, in una forma diversa (tre controlli insieme) [T3 Consegna 2]
   ```
5. In «## Da fare a mano (solo Mattia)» aggiungi:
   ```markdown
   - [tbd] P3 · Prova sul telefono delle pulizie: con la tastiera aperta i suggerimenti della barra della Lista scorrono nel loro elenco, e l'ultimo si raggiunge senza scorrere la pagina
   ```

Se la fase notte ha già spostato le voci (ad esempio marcandole `in corso`), porta comunque lo stato finale a quello scritto qui.

- [ ] **Step 6: Commit**

```bash
git add docs/prossimi-passi.md next-steps.md CLAUDE.md
git commit -m "docs: le pulizie dopo la Lista, chiuse"
```

---

### Task 10: La verifica finale

Tutto insieme, sul ramo finito, perché ogni task ha provato solo il suo pezzo.

- [ ] **Step 1: Il backend**

Run (da `<worktree>/backend`): `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q`
Expected: PASS; il conto di partenza + 8 − 5 + 2.

- [ ] **Step 2: Il frontend**

Run (da `<worktree>/frontend`):

```bash
npx vitest run
npm run typecheck
npm run lint
npm run build
grep -rn "emerald\|neutral-" src
```

Expected: vitest verde con 681 test (663 + 1 + 7 + 10); typecheck, lint e build verdi; il `grep` non stampa niente.

- [ ] **Step 3: I controlli a occhio sul codice**

Run (da `<worktree>`):

```bash
grep -rn "set_fill" backend/app backend/tests
grep -n "console.warn" frontend/e2e/style.spec.ts
grep -rn -A8 "<Button" frontend/src --include=*.tsx | grep -v "\.test\." | grep "disabled"
```

Expected: le prime due non stampano niente; la terza stampa solo la riga di `IngredientPicker.tsx` (Fuori scope).

- [ ] **Step 4: L'e2e intera, su uno stack nuovo**

Dalla radice di `<worktree>`, la sequenza dei Global Constraints:

```bash
cp .env.example .env
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed --con-ricette
(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
rm .env
```

Expected: tutti i test passano. `ls .env` alla fine risponde che il file non c'è.

- [ ] **Step 5: Lo stato del ramo**

Run: `git status --short && git log --oneline master..HEAD`
Expected: nessuna modifica in sospeso; nove commit (Task 1–9). Niente push, niente merge: il ramo resta da revisionare.
