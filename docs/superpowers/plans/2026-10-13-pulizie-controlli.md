# Pulizie: i controlli spenti e il fuoco — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** i controlli spenti fuori da `Button` smettono di sbiadire con l'`opacity` e seguono la regola del tema scuro (grigio per chi ha un fondo, `ink-faint` per chi è testo); le due caselle da 20 px diventano `Checkbox`; nessun controllo si spegne più col fuoco addosso (stepper, `IngredientPicker`, `InlineField`, «Salva prodotto»); `Button` definisce `disabled` insieme a `busy`/`unavailableReason` e mostra un segno d'attesa sui pulsanti di sola icona in volo; i `<button>` scritti a mano del modulo della ricetta diventano `Button`; il fuoco non cade più sulla pagina dopo l'annullamento di una decisione in coda né dopo una dispensa che non si ricarica.

**Architecture:** tutto nel frontend: nessuna rotta, nessuna migrazione, nessun token nuovo. `Button.tsx` cambia in due punti (chi vince fra le prop dello spento, l'icona in volo); i primitivi (`Checkbox`, `StockGauge`, `OptionList`, `CostPicker`) e `IngredientPicker` cambiano classi e `disabled` → `aria-disabled`/`readOnly`; `InlineField`, `CustomProductForm`, `RecipeForm` passano a `Button`; il fuoco si sposta a mano in tre punti (`ServingsStepper`, `RecipeDetailScreen`, `TermCard`), sempre e solo quando è caduto sulla pagina. Una prova strutturale in vitest (`disabledLook.test.ts`) tiene fuori ogni `disabled:opacity-…`; l'e2e misura gli spenti a video nei due temi.

**Tech Stack:** React 19, TypeScript, Tailwind 4.3 (token in `@theme`), TanStack Query 5, Vitest + Testing Library (jsdom; `node` per le prove che leggono i file), Playwright.

**Spec:** `docs/superpowers/specs/2026-10-13-pulizie-controlli-design.md` (tutta: il §2 dice quali voci di `next-steps.md` chiude, il §5 le scelte delegate). Regola dei pulsanti: `frontend/src/components/ui/Button.tsx` (JSDoc in testa). Regola dello spento: `docs/superpowers/plans/2026-10-08-tema-scuro-spenti.md`, «Decisioni prese».

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/pulizie-controlli` (`.worktrees/` è già in `.gitignore`), ramo `night/pulizie-controlli`, creato da **`night/r8-modifica-con-ai`** (la fine della catena: `night/r8-modifica-con-ai` ← `night/rimetti-in-lista` ← `night/s15-reparti-collassabili` ← `night/s14-cibo-casa` ← `night/tema-scuro-spenti` ← `night/s12-righe-dispensa` ← `night/s3-ingresso-diretto` ← `master`). Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì (o dalle sue `backend/` e `frontend/`), mai dalla radice del checkout principale. Il checkout principale non si tocca: se vi trovi modifiche non committate, sono dell'utente. **Nessun push, nessun merge, nessun deploy. Mai `git stash`.** Niente letture né scritture sulla produzione.
- **I file che anche i piani prima di questo toccano** — `frontend/src/features/pantry/PantryRow.tsx` (S12, rimetti in lista), `frontend/src/features/cooking/CookSheet.tsx` e il suo test (rimetti in lista, S12, S14), `frontend/src/features/cooking/RecipeDetailScreen.tsx` e il suo test (R8, S12, S14), `frontend/src/features/stocking/StockingScreen.test.tsx` (S3), `frontend/src/features/registry/IngredientScreen.test.tsx` e `ProductScreen.test.tsx` (S12), `frontend/src/components/ui/icons.ts` (S3, S12, S15), `frontend/src/theme.test.ts` (S12, tema scuro), `frontend/e2e/style.spec.ts` (tutti), `next-steps.md`, `docs/prossimi-passi.md`, il report della notte — **leggili com'è sul ramo prima di cambiarli**. Il piano descrive ogni modifica a questi file contro un'ancora riconoscibile — una funzione, un elemento JSX, un testo esatto — e mai contro numeri di riga, e aggiunge in blocchi propri senza toccare le righe degli altri piani. I file che solo questo piano tocca (`ServingsStepper.tsx`, `InlineField.tsx`) li dà interi: la Preparazione verifica che sul ramo siano come su `master`.
- **`Button`** (`frontend/src/components/ui/Button.tsx`). **La regola (di Mattia):** in volo → `busy`; «non ancora» → `unavailableReason` col perché; `disabled` nativo solo dove nessuno dei due vale. Questo piano la estende a ciò che non è `Button`: **un controllo che può avere il fuoco quando si spegne non si spegne con `disabled`** (si usa `aria-disabled` con la guardia del tocco, o `readOnly` per un campo). Nessun `<button>` nuovo scritto a mano; un pulsante di sola icona ha `label`.
- **Lo spento si vede senza `opacity`** (regola del tema scuro, estesa qui): chi ha un fondo pieno si spegne nel grigio (`disabled` / `on-disabled`), chi è solo testo scrive in `ink-faint`. Nessun `disabled:opacity-…` né `aria-disabled:opacity-…` in `frontend/src` (lo controlla `disabledLook.test.ts`, Task 4).
- Tutto il colore passa dai token di `frontend/src/index.css`. **Nessun token nuovo**: si usano `disabled`, `on-disabled`, `ink-faint`, `notch-off`, che il tema scuro ha già messo nei due temi. Nessuna schermata nomina un colore crudo: `grep -rn "emerald\|neutral-" frontend/src` resta vuoto. Ogni testo sta sopra 4,5:1, in chiaro e in scuro. Le icone si importano solo da `frontend/src/components/ui/icons.ts`.
- Ogni bersaglio resta almeno 44×44 px. A 375 px nessuna schermata scorre di lato.
- **Il fuoco si sposta a mano solo se è caduto sulla pagina** (`document.activeElement` è `null` o il `body`), con l'unica eccezione dello stepper, dove passa dal tasto premuto all'altro: chi ha toccato altro se lo tiene.
- **Mai un vicolo cieco.** Questo piano non spegne niente di nuovo e non toglie strade.
- Le parole a video **non cambiano**. Gli identificatori in inglese; i commenti in italiano come nel resto del codice, e dicono il perché.
- **Il type check è `npm run typecheck`** (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0 (settima lezione di `CLAUDE.md`).
- Controlli del frontend, da `<worktree>/frontend`: `npx vitest run` (non esiste `npm test`), `npm run typecheck`, `npm run lint`, `npm run build`.
- **Il backend non si tocca**: `git diff night/r8-modifica-con-ai -- backend` resta vuoto. La sua suite gira due volte (linea di partenza e verifica finale) per sapere che la catena è sana, su un **database suo**. Il server dei test è il container `spena-db-1` (porta 5433): se `docker ps --format '{{.Names}}'` non lo mostra, `docker start spena-db-1`. **Mai `docker compose up` dal worktree**, mai `-f docker-compose.prod.yml`. Nel worktree non c'è un `.venv`: si usa quello del checkout principale. Il comando, da `<worktree>/backend`:
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_controlli PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
- **Il database dei test è `spena_test_controlli`, non `spena_test`.** Il ramo eredita la `0013` di S12 e la `0014` di R8; la suite fa `alembic upgrade head` all'avvio, e su `spena_test` lo porterebbe alla `0014`, rompendo i piani che partono da `master` («Can't locate revision identified by '0014'»). Si crea nella Preparazione e si toglie alla fine della verifica finale:
  ```bash
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_controlli WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_controlli'
  # … i task …
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_controlli WITH (FORCE)'
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
  Il `-p spena-e2e` e il `-f docker-compose.e2e.yml` vanno in ogni comando: un `down -v` sul progetto di default cancellerebbe la dispensa vera. Una prova fallita lascia dati nello stack: prima di rieseguire, `down -v`, poi `up`, seme e prova. Se un piano della catena ha cambiato il comando del seme (leggi i loro report sul ramo, `docs/night-reports/`), usa il suo.
- Nessuna dipendenza nuova (`IconLoader2` è già in `@tabler/icons-react`, installato), nessuna migrazione, nessun cambio di configurazione globale.

### Preparazione (una volta, prima del Task 1)

- [ ] Il database dei test di questo ramo (prima di qualunque pytest):
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_controlli WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_controlli'
  ```
- [ ] Il ramo di partenza c'è, e porta la catena e ciò che questo piano consuma (i token e le classi dello spento del tema scuro, l'aiuto `tokenIn` dell'e2e):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify night/r8-modifica-con-ai
  for r in night/tema-scuro-spenti night/rimetti-in-lista; do git merge-base --is-ancestor $r night/r8-modifica-con-ai && echo "$r dentro"; done
  git ls-tree --name-only night/r8-modifica-con-ai backend/alembic/versions/ | grep -E '/00(13|14)'
  git show night/r8-modifica-con-ai:frontend/src/components/ui/buttonClasses.ts | grep -c "OFF_FILLED"
  git show night/r8-modifica-con-ai:frontend/src/index.css | grep -c -- "--color-on-disabled"
  git show night/r8-modifica-con-ai:frontend/e2e/style.spec.ts | grep -n "function tokenIn"
  ```
  Expected: un hash; «night/tema-scuro-spenti dentro» e «night/rimetti-in-lista dentro»; due file, la `0013` e la `0014`; un numero ≥ 1; `2`; una riga. Se `night/r8-modifica-con-ai` **non c'è**, **fermati**: la catena si è interrotta prima di questo piano, e nessun task parte. Il checkout principale non si tocca: la causa va nel report della notte (`docs/night-reports/<data>.md`) sull'ultimo ramo della catena che esiste, con la riga di questa voce segnata `bloccato` in `next-steps.md` di quel ramo («attende: il ramo `night/r8-modifica-con-ai`»), e la domanda per Mattia («la catena si è fermata a …: parto da lì?»). Se c'è ma manca uno degli altri segni (il tema scuro non è dentro, niente `OFF_FILLED`, niente `tokenIn`), fermati allo stesso modo: questo piano estende la regola del tema scuro e la misura con i suoi aiuti. Se R8 vi ha lasciato la sua voce `bloccato`, si parte lo stesso: il ramo è quello.
- [ ] Dal checkout principale, allinea `node_modules` al lockfile (non aggiunge dipendenze):
  ```bash
  cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund
  ```
- [ ] Crea il worktree e collega `node_modules` (e solo quello: **niente `.env`**):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/pulizie-controlli -b night/pulizie-controlli night/r8-modifica-con-ai
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/pulizie-controlli/frontend/node_modules
  ```
- [ ] Cosa hanno già cambiato i piani prima di questo nei file di questo piano:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/pulizie-controlli
  git diff --stat master -- \
    frontend/src/components/ui/Button.tsx frontend/src/components/ui/Checkbox.tsx \
    frontend/src/components/ui/StockGauge.tsx frontend/src/components/ui/OptionList.tsx \
    frontend/src/components/ui/CostPicker.tsx frontend/src/components/IngredientPicker.tsx \
    frontend/src/features/shopping-list/ListRow.tsx frontend/src/features/registry/InlineField.tsx \
    frontend/src/features/registry/MergePanel.tsx frontend/src/features/stocking/CustomProductForm.tsx \
    frontend/src/features/recipe-form/RecipeForm.tsx frontend/src/features/cooking/ServingsStepper.tsx \
    frontend/src/features/recipe-import/ImportQueueScreen.tsx frontend/src/features/recipe-import/TermCard.tsx \
    frontend/src/features/recipe-import/DecidedTermRow.tsx
  git diff --stat master -- \
    frontend/src/features/pantry/PantryRow.tsx frontend/src/features/cooking/CookSheet.tsx \
    frontend/src/features/cooking/RecipeDetailScreen.tsx frontend/src/components/ui/icons.ts \
    frontend/src/theme.test.ts frontend/e2e/style.spec.ts
  grep -rn "opacity" frontend/src --include=*.ts --include=*.tsx | grep -v "\.test\."
  ```
  Expected: il primo **vuoto** (se uno di quei file è cambiato, applica le modifiche di questo piano sopra la versione del ramo, blocco per blocco, invece di sovrascriverlo, e scrivilo nel report; per `ServingsStepper.tsx` e `InlineField.tsx`, che il piano dà interi, porta le modifiche dentro la versione del ramo). Il secondo non è vuoto (i piani della catena li hanno toccati): leggili per intero prima dei task che li cambiano. Il `grep` stampa i sette controlli della spec, §1 (`Checkbox.tsx`, `ListRow.tsx`, `StockGauge.tsx`, `PantryRow.tsx`, `CostPicker.tsx`, `IngredientPicker.tsx`, `OptionList.tsx`) e niente in `buttonClasses.ts`. Un `opacity` in un file in più è un controllo spento che un piano della catena ha aggiunto: portalo alla regola nel task del suo tipo (testo → `ink-faint`, fondo pieno → `on-disabled`/`disabled`) e scrivilo nel report.
- [ ] La voce in `next-steps.md` del ramo passa a `in corso`. Cercala con `grep -n "pulizie-controlli\|Pulizie: controlli spenti" next-steps.md` (di giorno è stata messa fra i «Pronti per la notte»): toglila da dove sta e mettila sotto `## In corso` (al posto di `_(niente)_`, se c'è; altrimenti in fondo alle righe già lì) come
  ```markdown
  - [in corso] P3 · Pulizie: i controlli spenti senza opacità e il fuoco che non cade — piano `docs/superpowers/plans/2026-10-13-pulizie-controlli.md` → branch night/pulizie-controlli [T3]
  ```
  Se non la trovi, aggiungi solo questa riga sotto `## In corso`. Commit:
  ```bash
  git add next-steps.md
  git commit -m "next-steps: pulizie dei controlli spenti, in corso"
  ```
- [ ] La linea di partenza, dal worktree:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/pulizie-controlli/frontend && npx vitest run 2>&1 | grep -E "Test Files|Tests "
  npx playwright test --list 2>/dev/null | tail -n 1
  cd ../backend && TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_controlli PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q 2>&1 | tail -n 1
  ```
  Expected: tutto verde. **Annota** file e test di vitest (`N_file`, `N_vitest`), il numero di prove e2e (`N_e2e`) e di pytest (`N_pytest`). Se una linea non è verde, fermati: non è un difetto di questo piano, e va scritto nel report.

---

## Review Focus

- **Un controllo che si spegne col fuoco addosso** (il selettore in volo, «Salva» di un campo del prodotto, lo stepper al bordo, «Salva prodotto»): chi usa la tastiera non deve ritrovarsi sul `body` — Task 3, 5, 6, 8 in jsdom; lo stepper in Chromium al Task 10, perché jsdom non toglie il fuoco a un `disabled`.
- **Lo spento a video nei due temi**: opacità 1 e il colore del token, non un'approssimazione — Task 10 (casella, tacche, scadenza), con le richieste trattenute.
- **Una richiesta in volo che fallisce**: il controllo torna acceso e il fuoco resta dov'era — Task 5 («fallito, il fuoco resta su «Salva»»), Task 8 («Riprova» in volo è `busy`).
- **Le letture della coda che tornano in un ordine qualsiasi dopo un annullamento**: il fuoco arriva lo stesso al nome del termine — Task 9 (l'effetto aspetta finché l'«Annulla» del termine ha ancora il fuoco).
- **Un tocco su un controllo spento** (un'opzione, la casella, «Salva» a campo vuoto, «Salva prodotto» senza nome) non fa niente — Task 2, 3, 5, 6.

## Obiettivo e contesto

Il tema scuro ha dato allo spento di `Button` un colore pieno, e ha lasciato fuori i controlli che `Button` non è: sette controlli si spengono ancora sbiadendo, e quattro (il campo e i suggerimenti del selettore, il «Salva» dei campi del prodotto, «Salva prodotto») si spengono con `disabled` nativo, che toglie il fuoco a chi lo usa da tastiera. Lo stepper delle porzioni fa lo stesso al bordo. Due schermate perdono il fuoco perché il controllo che l'aveva sparisce (la riga annullata in coda, «Cucina» sostituito dall'avviso). E `Button` non dice cosa succede se un chiamante gli passa insieme `disabled` e `unavailableReason`. Sono dodici voci `idea` piccole, raccolte qui perché si toccano: la regola è una.

## Decisioni prese

Di Mattia (non si rimettono in discussione):

1. **La regola dei pulsanti** (T3 Consegna 6a): in volo → `busy`; «non ancora» → `unavailableReason` col perché; `disabled` nativo solo dove nessuno dei due vale.
2. **Lo spento è un colore pieno, non un'`opacity`** (tema scuro, decisa il 2026-10-07): grigio `disabled`/`on-disabled` per i pieni, `ink-faint` per chi è testo.
3. **Le scelte estetiche e tecniche di queste pulizie sono delegate a Claude** (2026-10-13); solo il comportamento non ovvio va confermato. Qui non ce n'è.

Scelte di questo piano (**decise da Claude su delega di Mattia**, reversibili; la spec, §5):

4. **Fuori da `Button` la regola si legge così**: `Checkbox` spenta → spunta grigia (`aria-disabled:accent-ink-faint`); tacche spente → accese in `on-disabled`, spente in `notch-off` (la forma resta tre tacche, il livello si legge a 2,13:1 e 2,57:1); scadenza della riga, suggerimenti, campo del selettore → testo `ink-faint`.
5. **`CostPicker` perde la prop `disabled`**: nessun chiamante la passa.
6. **`IngredientPicker`** in volo: campo `readOnly` + `aria-disabled`, suggerimenti `aria-disabled` con il tocco ignorato dentro `OptionList`. La prop si chiama ancora `disabled` (quattro chiamanti, uno di S3).
7. **Le caselle da 20 px** (Lista, foglio della cottura) diventano `Checkbox`; le loro label passano a `gap-1`, e quella della Lista perde il `py-1.5`.
8. **Lo stepper**: il tasto al bordo resta `disabled`; prima che si spenga, se aveva il fuoco, il fuoco passa all'altro tasto. Niente motivo sotto.
9. **`InlineField`**: «Salva» è `Button` — `busy` in volo, `unavailableReason` «Il campo «<label>» non può restare vuoto.» se obbligatorio e vuoto, `disabled` se invariato; dopo un salvataggio riuscito il fuoco torna nel campo (se era su «Salva») **prima** che il pulsante si spenga; il campo in volo è `readOnly`.
10. **`CustomProductForm`**: «Salva prodotto» `Button` `type="submit"` con `busy` e `unavailableReason` «Scrivi il nome del prodotto per salvarlo.»; «Annulla» `Button` `ghost`.
11. **`Button`**: `busy` e `unavailableReason` vincono su `disabled` (niente `disabled` nativo se c'è uno dei due); un pulsante **di sola icona** in volo disegna `IconLoader2` con `motion-safe:animate-spin` al posto della sua icona.
12. **`RecipeForm`**: la ✕ è `Button` `ghost` con `IconX`; i ruoli sono `Button` con `aria-pressed`, `primary` lo scelto e `secondary` l'altro, forma `pill`; la riga della quantità è `flex-wrap`.
13. **Il fuoco dopo un annullamento** va al nome del termine nella sua scheda (`<p tabIndex={-1}>`); **dopo «Ho cucinato»** a «Cucina», o a «Riprova» se la dispensa non si ricarica (anche se l'errore arriva dopo). Sempre e solo se il fuoco è caduto sulla pagina.

## Criteri di accettazione

- [ ] `grep -rn "opacity" frontend/src --include=*.ts --include=*.tsx | grep -v "\.test\."` è vuoto; `disabledLook.test.ts` è verde.
- [ ] `Button` con `disabled` e `unavailableReason` (o `busy`) insieme: niente `disabled` nativo, `aria-disabled="true"`, il perché nella descrizione. Un pulsante di sola icona in volo mostra `IconLoader2` che gira, col nome di sempre; uno col testo tiene la sua icona.
- [ ] `Checkbox`, `StockGauge`, `OptionList`, il campo di `IngredientPicker`, la scadenza di `PantryRow` spenti hanno opacità 1 e i colori del §4 delle decisioni (jsdom per le classi, e2e per i colori a video nei due temi).
- [ ] Le caselle di `ListRow` e del foglio della cottura sono `Checkbox` (quadrato da 44 px).
- [ ] Nello stepper, da tastiera, arrivati a 1 il fuoco è sul «+», arrivati a 50 sul «−» (jsdom ed e2e).
- [ ] `IngredientPicker` in volo: campo e suggerimenti raggiungibili, non scrivono e non scelgono.
- [ ] `InlineField`: in volo `busy`; vuoto obbligatorio col perché e senza `disabled`; dopo il salvataggio il fuoco è nel campo; fallito, il fuoco resta su «Salva».
- [ ] «Salva prodotto» spento senza nome con `aria-disabled` e il perché; in volo `busy`.
- [ ] «Cambia» di `MergePanel` non sta dentro un `<p>`; in `RecipeForm` non resta nessun `<button` scritto a mano (`grep -n "<button" frontend/src/features/recipe-form/RecipeForm.tsx` vuoto).
- [ ] Annullata una decisione, il fuoco è sul nome del termine tornato in coda; dopo «Ho cucinato» con la dispensa che fallisce, su «Riprova».
- [ ] Nessuna parola a video cambiata; nessun test indebolito; i test cambiati sono solo quelli che controllavano proprio un `disabled` nativo che questo piano toglie (elencati nei task).
- [ ] vitest, typecheck, lint, build, pytest e l'e2e intera verdi.
- [ ] `next-steps.md` aggiornato (Task 11), il report della notte scritto (Task 12).

## Comandi di verifica

Da `<worktree>/frontend`: `npx vitest run`, `npm run typecheck`, `npm run lint`, `npm run build`. Dalla radice di `<worktree>`:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -rn "opacity" frontend/src --include=*.ts --include=*.tsx | grep -v "\.test\."
grep -n "<button" frontend/src/features/recipe-form/RecipeForm.tsx frontend/src/features/registry/InlineField.tsx frontend/src/features/stocking/CustomProductForm.tsx
git diff night/r8-modifica-con-ai -- backend
```

Expected: tutti vuoti. E l'e2e intera con i comandi delle Global Constraints.

## Fuori scope

- Altri campi spenti con `disabled` nativo in volo, non fra le voci: il campo di `RenameForm`, il `CategorySelect` di `CategoryForm`, il campo data di `PantryRow`. Il Task 11 li annota come idea.
- La versione di `ServingsStepper` di R2 (piano 8, da `master`): vedi «Dipendenze».
- Un aspetto proprio per `busy` sui pulsanti con testo.
- Gli altri `<button>` scritti a mano con `buttonClasses(...)` fuori da `InlineField`, `CustomProductForm` e `RecipeForm` (per esempio «Cambia reparto» e «Riprova» in `MergePanel`): si vedono già con lo spento del tema scuro, e nessuna voce li chiede.
- Il backend.

## Margine di autonomia

- **Liberi:** nomi di variabili locali e di aiuti dei test; l'ordine dei test in un file; l'ordine delle classi Tailwind in una stringa; i commenti, purché dicano il perché.
- **Fissi:** le parole a video (non cambiano); le classi dello spento del §4 delle decisioni; i nomi pubblici nuovi (`arriving`, `onArrived` di `TermCard`; `data-decided-term` di `DecidedTermRow`); le soglie dei test (3:1 e 2:1 delle tacche, 44 px).
- **Un test di oggi si cambia solo se controllava proprio il `disabled` nativo che questo piano toglie**, e lo si sostituisce con controlli almeno altrettanto stretti (`aria-disabled`, il perché, il tocco che non fa niente): sono elencati nei task. Se ne serve un altro, scrivilo nel report con il perché.
- **Una misura e2e che fallisce sul colore** (per esempio `accent-color` che il browser non riporta come `rgb(...)`): non cambiare token. Se è la forma della stringa, confronta i canali come fa `contrastoAVideo`; se è il colore, scrivi nel report cosa hai misurato, fai commit del lavoro, segna la voce `bloccato` con la domanda per Mattia, e vai al Task 11.
- **Una decisione non coperta e non reversibile** → si ferma quel task, si fa commit del lavoro parziale sul ramo, lo si segna `bloccato` in `next-steps.md` del ramo con la domanda precisa per Mattia, e si passa al task successivo. Una scelta reversibile e a basso impatto → la più conservativa, annotata nel report.
- Se un test fallisce e non si risolve in modo ragionevole: niente test disattivati, niente asserzioni indebolite; `bloccato` con la diagnosi.

## Dipendenze

**Parte da `night/r8-modifica-con-ai`**, la fine della catena: così al merge `PantryRow.tsx`, `CookSheet.tsx`, `RecipeDetailScreen.tsx`, `buttonClasses.ts` e i test della Dispensa e della cottura non hanno conflitti con i piani 1, 2, 3, 5, 6, 7 e 10. **Consuma** dal tema scuro (piano 3) i token `disabled`, `on-disabled` e le classi dello spento di `buttonClasses`, e in `style.spec.ts` gli aiuti `tokenIn`, `fermo`, `contrastoAVideo`.

**Al merge con i rami che partono da `master`**:
- **R2** (piano 8) dà `ServingsStepper.tsx` intero, col `disabled` al bordo e la prop `approx`. Questo piano aggiunge al file di `master` i due `ref` e la funzione `step` (Task 8). Al merge si tiene la versione di R2 e si portano dentro i `ref` e il passaggio del fuoco: nei due `onClick` di R2 `onChange(below)` diventa `step(below, minusRef, plusRef)` e `onChange(above)` diventa `step(above, plusRef, minusRef)`, con il bordo che `step` riconosce (`next <= MIN || next >= MAX`). R2 tocca anche `RecipeDetailScreen.tsx` e `CookSheet.tsx` (righe diverse da queste).
- **Le pagine scartate** (piano 9) toccano `ImportQueueScreen.tsx` e il suo test (una sezione nuova; qui lo stato `arriving` e due prop sulle `TermCard`), e `icons.ts`.
- **Il piano 14** (`pulizie-test`, da `master`) sostituisce in tutti i test di schermata il `new QueryClient(...)` con una fabbrica condivisa: i test nuovi di questo piano usano gli aiuti di montaggio dei loro file, e al merge passano alla fabbrica con loro.
- **Il piano 15** (`pulizie-parole`, da `master`) tocca `RecipeForm.tsx` (la nota «lo creo io salvando» e `attach`), `CookSheet.tsx` (il titolo della confezione) e `formModel.ts`: righe diverse da queste.

## Dopo il deploy (solo Mattia)

Niente: nessuna migrazione, nessun dato. Restano le prove sul telefono (il Task 11 le scrive in «Da fare a mano»).

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `frontend/src/components/ui/Button.tsx`, `Button.test.tsx`, `icons.ts` | 1 | chi vince fra le prop dello spento; il segno d'attesa; `IconLoader2` |
| `frontend/src/components/ui/Checkbox.tsx`, `Checkbox.test.tsx`, `StockGauge.tsx`, `StockGauge.test.tsx`, `OptionList.tsx`, `CostPicker.tsx`, `frontend/src/theme.test.ts` | 2 | lo spento dei primitivi |
| `frontend/src/components/IngredientPicker.tsx`, `IngredientPicker.test.tsx`, `frontend/src/features/pantry/PantryRow.tsx` | 3 | il selettore in volo; la scadenza spenta |
| `frontend/src/features/shopping-list/ListRow.tsx`, `ListRow.test.tsx`, `frontend/src/features/cooking/CookSheet.tsx`, `CookSheet.test.tsx`, `frontend/src/disabledLook.test.ts` (nuovo) | 4 | le caselle; la prova strutturale |
| `frontend/src/features/registry/InlineField.tsx`, `InlineField.test.tsx` (nuovo), `ProductScreen.test.tsx` | 5 | «Salva» dei campi del prodotto |
| `frontend/src/features/stocking/CustomProductForm.tsx`, `CustomProductForm.test.tsx`, `StockingScreen.test.tsx`, `frontend/src/features/registry/MergePanel.tsx`, `IngredientScreen.test.tsx` | 6 | «Salva prodotto»; il `<div>` di «Cambia» |
| `frontend/src/features/recipe-form/RecipeForm.tsx`, `RecipeForm.test.tsx` | 7 | la ✕ e i ruoli |
| `frontend/src/features/cooking/ServingsStepper.tsx`, `ServingsStepper.test.tsx`, `RecipeDetailScreen.tsx`, `RecipeDetailScreen.test.tsx` | 8 | il fuoco dello stepper e dopo la cottura |
| `frontend/src/features/recipe-import/ImportQueueScreen.tsx`, `TermCard.tsx`, `DecidedTermRow.tsx`, `ImportQueueScreen.test.tsx` | 9 | il fuoco dopo un annullamento |
| `frontend/e2e/style.spec.ts` | 10 | sei prove nuove |
| `next-steps.md` | 11 | i documenti |
| `docs/night-reports/<data>.md` | 12 | il report |

---

### Task 1: `Button` — chi vince fra le prop dello spento, e il segno d'attesa

**Files:**
- Modify: `frontend/src/components/ui/Button.tsx`
- Modify: `frontend/src/components/ui/icons.ts`
- Test: `frontend/src/components/ui/Button.test.tsx`

**Interfaces:**
- Produces: `Button` con le stesse prop di oggi. `disabled` vale solo se non ci sono `busy` né `unavailableReason`. Un pulsante di sola icona con `busy` disegna `IconLoader2` (classe `tabler-icon-loader-2`) con `motion-safe:animate-spin`. `icons.ts` esporta `IconLoader2`.

- [ ] **Step 1: I test**

In `frontend/src/components/ui/Button.test.tsx`, dentro `describe("Button", …)`, subito dopo il test `"disabled resta, per un'azione che adesso non si può proprio fare"`, aggiungi:

```tsx
  // Insieme, `busy` e `unavailableReason` vincono su `disabled` (idea della Consegna 6a,
  // pulizie del 2026-10-13): il `disabled` nativo toglierebbe il fuoco, e il perché non lo
  // sentirebbe più nessuno.
  it("con disabled e unavailableReason insieme vince il perché: niente disabled nativo, il motivo si sente", () => {
    const onClick = vi.fn();
    render(
      <Button disabled unavailableReason="Scrivi il nome." onClick={onClick}>
        Salva
      </Button>
    );
    const salva = screen.getByRole("button", { name: "Salva" });
    expect(salva).not.toBeDisabled();
    expect(salva).toHaveAttribute("aria-disabled", "true");
    expect(salva).toHaveAccessibleDescription("Scrivi il nome.");
    salva.focus();
    expect(salva).toHaveFocus();
    fireEvent.click(salva);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("con disabled e busy insieme vince busy: il fuoco resta", () => {
    render(
      <Button disabled busy>
        Salva
      </Button>
    );
    const salva = screen.getByRole("button", { name: "Salva" });
    expect(salva).not.toBeDisabled();
    expect(salva).toHaveAttribute("aria-disabled", "true");
    salva.focus();
    expect(salva).toHaveFocus();
  });

  // dal giro della Consegna 5: «Elimina» di sola icona non mostrava niente mentre
  // archiviava. Il segno d'attesa al posto dell'icona, e lo stesso nome
  it("di sola icona, in volo mostra il segno d'attesa al posto dell'icona, col nome di sempre", () => {
    const { rerender } = render(<Button icon={IconTrash} label="Elimina" />);
    const pulsante = screen.getByRole("button", { name: "Elimina" });
    expect(pulsante.querySelector("svg")!.getAttribute("class")).toContain("tabler-icon-trash");

    rerender(<Button icon={IconTrash} label="Elimina" busy />);
    const svg = screen.getByRole("button", { name: "Elimina" }).querySelector("svg")!;
    expect(svg.getAttribute("class")).toContain("tabler-icon-loader-2");
    // chi ha chiesto meno movimento lo vede fermo
    expect(svg.getAttribute("class")).toContain("motion-safe:animate-spin");
    expect(svg).toHaveAttribute("aria-hidden", "true");
    // è lo stesso pulsante: il fuoco non si perde
    expect(screen.getByRole("button", { name: "Elimina" })).toBe(pulsante);
  });

  it("con il testo, in volo tiene la sua icona: la parola la cambia già il chiamante", () => {
    render(
      <Button icon={IconPencil} busy>
        Modifica
      </Button>
    );
    const svg = screen.getByRole("button", { name: "Modifica" }).querySelector("svg")!;
    expect(svg.getAttribute("class")).toContain("tabler-icon-pencil");
    expect(svg.getAttribute("class")).not.toContain("animate-spin");
  });
```

(`IconTrash`, `IconPencil`, `fireEvent`, `vi` sono già importati in cima al file.)

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/components/ui/Button.test.tsx`
Expected: FAIL — i primi due con `expected element not to be disabled`, il terzo perché la classe è ancora `tabler-icon-trash`. Il quarto passa già (va bene: fissa ciò che non deve cambiare).

- [ ] **Step 3: `icons.ts`**

In `frontend/src/components/ui/icons.ts`, nel primo blocco `// ovunque` (`export { IconMenu2, IconChevronLeft, … } from "@tabler/icons-react";`), aggiungi `IconLoader2,` come ultimo nome prima della `}` (dopo `IconEyeOff,`, o dopo l'ultimo nome che il ramo vi ha messo). Sopra il blocco non serve un commento nuovo.

- [ ] **Step 4: `Button.tsx`**

In `frontend/src/components/ui/Button.tsx`:

1. L'import `import type { IconComponent } from "./icons";` diventa:
   ```tsx
   import { IconLoader2, type IconComponent } from "./icons";
   ```
2. Il JSDoc della prop `disabled`,
   ```tsx
     /** Un'azione che adesso non si può fare, dove non c'è niente da aspettare né da
      * spiegare. Il browser toglie il fuoco a un pulsante che diventa `disabled`: per «sto
      * già lavorando» c'è `busy`, per «non ancora» c'è `unavailableReason`. */
   ```
   diventa:
   ```tsx
     /** Un'azione che adesso non si può fare, dove non c'è niente da aspettare né da
      * spiegare. Il browser toglie il fuoco a un pulsante che diventa `disabled`: per «sto
      * già lavorando» c'è `busy`, per «non ancora» c'è `unavailableReason`.
      *
      * Insieme a `busy` o a `unavailableReason`, vincono loro: il pulsante non prende il
      * `disabled` nativo, resta raggiungibile e il perché si sente (pulizie del 2026-10-13). */
   ```
3. Subito dopo la riga `const inert = busy || reason !== null;` aggiungi:
   ```tsx
     // In volo, un pulsante di sola icona mostra un segno d'attesa al posto della sua icona:
     // «Elimina» non mostrava niente mentre archiviava (dal giro della Consegna 5), e prima
     // diceva «Elimino…». Uno con il testo no: lì il chiamante cambia già la parola.
     const ShownIcon = iconOnly && busy ? IconLoader2 : Icon;
   ```
4. Sul `<button …>`, `disabled={disabled}` diventa:
   ```tsx
           // `busy` e `unavailableReason` vincono su `disabled`: il nativo toglierebbe il fuoco
           disabled={inert ? undefined : disabled}
   ```
5. La riga
   ```tsx
           {Icon && <Icon aria-hidden="true" className={iconOnly ? "size-5" : "size-[1.1em]"} stroke={1.8} />}
   ```
   diventa:
   ```tsx
           {ShownIcon && (
             <ShownIcon
               aria-hidden="true"
               className={
                 iconOnly ? (busy ? "size-5 motion-safe:animate-spin" : "size-5") : "size-[1.1em]"
               }
               stroke={1.8}
             />
           )}
   ```

- [ ] **Step 5: Passano, e la classe esiste nel CSS compilato**

Run: `npx vitest run src/components/ui/Button.test.tsx`
Expected: PASS, 4 test in più.

Run: `npm run build && grep -o 'motion-safe\\:animate-spin[^{]*{[^}]*}' dist/assets/*.css | head -n 1`
Expected: una regola con `animation:` (dentro un `@media (prefers-reduced-motion:no-preference)`, che il `grep` può non mostrare). Se non stampa niente, Tailwind non ha trovato la classe: la stringa deve stare scritta per intero in `Button.tsx`.

- [ ] **Step 6: La suite e il tipo**

Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde, `N_vitest` + 4. Nessun altro test cambia: oggi nessun chiamante passa `disabled` insieme a `busy` o `unavailableReason` (`ServingsStepper` li passa sul «+» in due stati che non si toccano: `value === null` e `value >= 50`).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ui/Button.tsx frontend/src/components/ui/Button.test.tsx frontend/src/components/ui/icons.ts
git commit -m "feat(ui): Button fa vincere busy e unavailableReason su disabled, e in volo un pulsante di sola icona mostra il segno d'attesa"
```

---

### Task 2: Lo spento dei primitivi senza opacità

**Files:**
- Modify: `frontend/src/components/ui/Checkbox.tsx`, `frontend/src/components/ui/StockGauge.tsx`, `frontend/src/components/ui/OptionList.tsx`, `frontend/src/components/ui/CostPicker.tsx`
- Test: `frontend/src/components/ui/Checkbox.test.tsx`, `frontend/src/components/ui/StockGauge.test.tsx`, `frontend/src/theme.test.ts`

**Interfaces:**
- Produces: `Checkbox` come oggi, spenta con `aria-disabled:accent-ink-faint`; `StockGauge` come oggi, spenta con le tacche accese `bg-on-disabled`; `OptionList({ options, onPick, disabled?, fieldLabel? })` come oggi, ma spenta con `aria-disabled` e il tocco ignorato; `CostPicker({ value, onChange })` **senza** `disabled`. Il Task 3 usa `OptionList` spenta da `IngredientPicker`.

- [ ] **Step 1: I test**

1. In `frontend/src/components/ui/Checkbox.test.tsx`, dentro `describe("Checkbox", …)`, in fondo:
   ```tsx
     // spenta non sbiadisce (pulizie del 2026-10-13, la regola del tema scuro): la spunta
     // prende il grigio. Che il grigio arrivi a video lo misura e2e/style.spec.ts
     it("spenta non si sbiadisce: la spunta prende il grigio", () => {
       render(
         <label>
           <Checkbox aria-label="Spenta" defaultChecked aria-disabled="true" />
         </label>
       );
       const casella = screen.getByRole("checkbox", { name: "Spenta" });
       expect(casella.className).toContain("aria-disabled:accent-ink-faint");
       expect(casella.className).not.toMatch(/opacity/);
     });
   ```
2. In `frontend/src/components/ui/StockGauge.test.tsx`, dentro il `describe` del file, dopo il test `"spenta, un tocco non manda niente"`:
   ```tsx
     // Spenta (una scrittura in volo) non sbiadisce: le tacche accese diventano grigie
     // come un pulsante spento (`on-disabled`), le spente restano `notch-off`. La forma
     // resta tre tacche, e il livello si legge ancora (theme.test.ts, 2:1).
     it("spenta, le tacche accese sono grigie e le spente restano com'erano, senza opacità", () => {
       render(<StockGauge status="low" onChange={() => {}} itemName="Latte" disabled />);
       const gruppo = screen.getByRole("radiogroup");
       const accese = [...gruppo.querySelectorAll("[data-lit=true] > span")];
       const spente = [...gruppo.querySelectorAll("[data-lit=false] > span")];
       expect(accese).toHaveLength(2);
       expect(spente).toHaveLength(1);
       for (const tacca of accese) expect(tacca.className).toContain("bg-on-disabled");
       for (const tacca of spente) expect(tacca.className).toContain("bg-notch-off");
       for (const radio of screen.getAllByRole("radio")) expect(radio.className).not.toMatch(/opacity/);
     });

     it("accesa, le tacche hanno il colore dello stato", () => {
       render(<StockGauge status="low" onChange={() => {}} itemName="Latte" />);
       const accese = [...screen.getByRole("radiogroup").querySelectorAll("[data-lit=true] > span")];
       for (const tacca of accese) expect(tacca.className).toContain("bg-low");
     });
   ```
3. In `frontend/src/theme.test.ts` (leggilo com'è sul ramo: S12 e il tema scuro vi hanno aggiunto costanti e prove):
   - subito prima della riga `describe("i token del colore", () => {`, aggiungi:
     ```ts
     // La tacca accesa di `StockGauge` mentre una scrittura è in volo: grigia come un
     // pulsante spento (`on-disabled`), non sbiadita con l'opacità (pulizie del 2026-10-13).
     // Contro la scheda è un segno (3:1, WCAG 1.4.11); contro la tacca spenta (`notch-off`)
     // deve dire ancora il livello: 2:1, misurato 2,13 in chiaro e 2,57 in scuro.
     const OFF_GAUGE_PAIRS: [string, string, number][] = [
       ["on-disabled", "card", 3],
       ["on-disabled", "notch-off", 2],
     ];
     ```
   - dentro `describe("i token del colore", …)`, nel `for (const [mode, palette] of …)`, dopo l'ultimo `it.each(…)` che c'è sul ramo dentro quel `for`, aggiungi:
     ```ts
         it.each(OFF_GAUGE_PAIRS)(
           `in ${mode}, la tacca spenta accesa %s contro %s sta sopra %s:1`,
           (mark, background, min) => {
             expect(palette[mark], `--color-${mark} manca in ${mode}`).toBeDefined();
             expect(palette[background], `--color-${background} manca in ${mode}`).toBeDefined();
             expect(ratio(palette[mark], palette[background])).toBeGreaterThanOrEqual(min);
           }
         );
     ```

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/components/ui/Checkbox.test.tsx src/components/ui/StockGauge.test.tsx src/theme.test.ts`
Expected: FAIL — la casella ha ancora `aria-disabled:opacity-40`; le tacche accese spente hanno `bg-low`, e il pulsante `opacity`. «accesa, le tacche hanno il colore dello stato» passa già, e così le quattro prove di `theme.test.ts` (i token ci sono dal tema scuro: sono una dichiarazione, va bene).

- [ ] **Step 3: Le classi**

1. `frontend/src/components/ui/Checkbox.tsx`: alla fine del JSDoc, dopo `Il colore della spunta è il verde dell'app.`, aggiungi ` Spenta (\`aria-disabled\`) la spunta è grigia, \`ink-faint\`: lo spento non sbiadisce (la regola del tema scuro, estesa il 2026-10-13).`; e la `className` dell'`<input>`, `"size-6 accent-brand aria-disabled:opacity-40"`, diventa `"size-6 accent-brand aria-disabled:accent-ink-faint"`.
2. `frontend/src/components/ui/StockGauge.tsx`:
   - il commento che comincia con `// Spenta (una scrittura in volo) con \`aria-disabled\`` resta; subito dopo la funzione `choose` aggiungi:
     ```tsx
       // Spenta, non sbiadisce (la regola del tema scuro, estesa il 2026-10-13): le tacche
       // accese diventano grigie come un pulsante spento, le spente restano `notch-off`. La
       // forma resta tre tacche, e il livello si legge ancora (2:1, theme.test.ts).
       const litColor = disabled ? "bg-on-disabled" : LIT[status];
     ```
   - la `className` del `<button>`, `"flex size-11 items-center justify-center aria-disabled:opacity-40"`, diventa `"flex size-11 items-center justify-center"`;
   - la `className` dello `<span>` interno, `` `h-1.5 w-4 rounded-full ${lit ? LIT[status] : "bg-notch-off"}` ``, diventa `` `h-1.5 w-4 rounded-full ${lit ? litColor : "bg-notch-off"}` ``.
3. `frontend/src/components/ui/OptionList.tsx`, nel `<button>` di ogni opzione:
   - `disabled={disabled}` diventa:
     ```tsx
                 // `aria-disabled` e non `disabled`: un'opzione che si spegne col fuoco
                 // addosso lo perdeva (pulizie del 2026-10-13); il tocco si ignora qui
                 aria-disabled={disabled || undefined}
     ```
   - `onClick={() => onPick(ingredient)}` diventa `onClick={() => { if (!disabled) onPick(ingredient); }}`;
   - nella `className`, `disabled:opacity-50` diventa `aria-disabled:text-ink-faint`.
   - nel tipo delle prop, sopra `disabled?: boolean;` aggiungi il commento `/** Una scelta è in volo: le opzioni restano raggiungibili ma non scelgono. */`.
4. `frontend/src/components/ui/CostPicker.tsx`: togli `disabled = false,` dalla destrutturazione, `disabled?: boolean;` dal tipo, `disabled={disabled}` dal `<button>` e ` disabled:opacity-60` dalla `className` (resta `` `min-h-11 min-w-11 text-xl font-semibold ${ … }` ``). Nel JSDoc del componente, in coda, aggiungi: ` Non si spegne: nessuno schermo lo chiedeva, e lo spento che aveva sbiadiva (pulizie del 2026-10-13).`

- [ ] **Step 4: Passano**

Run: `npx vitest run src/components/ui/Checkbox.test.tsx src/components/ui/StockGauge.test.tsx src/theme.test.ts`
Expected: PASS.

- [ ] **Step 5: La suite e il tipo**

Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde, `N_vitest` + 4 (Task 1) + 7 (1 + 2 + 4). Se il typecheck segnala un chiamante di `CostPicker` con `disabled`, è un chiamante nuovo della catena: togli la prop da lì e scrivilo nel report. Se un test di oggi cliccava un'opzione di `OptionList` spenta aspettandosi `toBeDisabled()`, è uno dei test del Margine di autonomia: sostituisci con `aria-disabled` e il tocco che non sceglie.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ui/Checkbox.tsx frontend/src/components/ui/Checkbox.test.tsx frontend/src/components/ui/StockGauge.tsx frontend/src/components/ui/StockGauge.test.tsx frontend/src/components/ui/OptionList.tsx frontend/src/components/ui/CostPicker.tsx frontend/src/theme.test.ts
git commit -m "feat(ui): casella, tacche e suggerimenti spenti senza opacità — grigio e ink-faint come i pulsanti; CostPicker senza uno spento che nessuno usa"
```

---

### Task 3: Il selettore in volo, e la scadenza spenta

**Files:**
- Modify: `frontend/src/components/IngredientPicker.tsx`, `frontend/src/features/pantry/PantryRow.tsx`
- Test: `frontend/src/components/IngredientPicker.test.tsx`

**Interfaces:**
- Consumes: `OptionList` spenta con `aria-disabled` (Task 2).
- Produces: `IngredientPicker` con le stesse prop; `disabled` ora vuol dire «in volo»: campo `readOnly` + `aria-disabled`, opzioni `aria-disabled`.

- [ ] **Step 1: Il test**

In `frontend/src/components/IngredientPicker.test.tsx`, dentro il `describe` del file, subito dopo il test `"mentre la scelta di prima è in volo, «Aggiungi «…»» è spento ma tiene il fuoco, e non crea"`, aggiungi:

```tsx
  // Il campo e i suggerimenti si spegnevano con `disabled` mentre la scelta di prima era in
  // volo: il browser toglie il fuoco a un controllo che diventa `disabled`, e chi usa la
  // tastiera lo ritrovava sul `body` (T3 Consegna 2, pulizie del 2026-10-13)
  it("mentre la scelta è in volo, campo e suggerimenti sono spenti ma raggiungibili, e non scelgono", async () => {
    stubRoutedFetch(() => [[LATTE], 200]);
    const onPick = vi.fn();
    renderWithClient(
      <IngredientPicker label="Ingrediente" failureNote="x" onPick={onPick} initialTerm="lat" disabled />
    );

    const latte = await screen.findByRole("option", { name: "Latte" });
    expect(latte).toHaveAttribute("aria-disabled", "true");
    expect(latte).not.toBeDisabled();
    latte.focus();
    expect(latte).toHaveFocus();
    fireEvent.click(latte);
    expect(onPick).not.toHaveBeenCalled();

    const campo = screen.getByLabelText("Ingrediente");
    expect(campo).not.toBeDisabled();
    expect(campo).toHaveAttribute("aria-disabled", "true");
    expect(campo).toHaveAttribute("readonly");
    campo.focus();
    expect(campo).toHaveFocus();
    expect(campo).toHaveValue("lat");
  });
```

E nel test che lo precede (`"mentre la scelta di prima è in volo, «Aggiungi «…»» …"`), il commento
```tsx
    // `busy` e non `disabled` (Consegna 6a): il browser toglie il fuoco a un pulsante che
    // diventa `disabled`. Campo e suggerimenti restano spenti come prima (idea in
    // next-steps.md): cambia solo il pulsante
```
diventa:
```tsx
    // `busy` e non `disabled` (Consegna 6a): il browser toglie il fuoco a un pulsante che
    // diventa `disabled`. Campo e suggerimenti fanno lo stesso dal 2026-10-13 (il test dopo)
```

- [ ] **Step 2: Fallisce**

Run (da `<worktree>/frontend`): `npx vitest run src/components/IngredientPicker.test.tsx`
Expected: FAIL — il campo è `disabled` (`expected element not to be disabled`). Le opzioni passano già (Task 2).

- [ ] **Step 3: Il campo, e la scadenza**

1. In `frontend/src/components/IngredientPicker.tsx`:
   - il JSDoc della prop `disabled`, `/** Mentre la scrittura nata dalla scelta precedente è ancora in volo. */`, diventa:
     ```tsx
       /** Mentre la scrittura nata dalla scelta precedente è ancora in volo. Campo e
        * suggerimenti restano raggiungibili — si spengono con `aria-disabled`, il campo è
        * `readOnly` — perché un controllo che diventa `disabled` perde il fuoco; non si
        * scrive e non si sceglie (pulizie del 2026-10-13). */
     ```
   - nell'`<input>`, `disabled={disabled}` e `className="mt-1.5 disabled:opacity-50"` diventano:
     ```tsx
               readOnly={disabled}
               aria-disabled={disabled || undefined}
               className="mt-1.5 aria-disabled:text-ink-faint"
     ```
   - nel commento sopra il `Button` di «Aggiungi «…»», le due righe
     ```tsx
               // pulsante tiene il fuoco. Campo e suggerimenti restano spenti con `disabled`:
               // sono un'altra forma, annotata in next-steps.md
     ```
     diventano:
     ```tsx
               // pulsante tiene il fuoco, come il campo e i suggerimenti
     ```
2. In `frontend/src/features/pantry/PantryRow.tsx` (leggilo com'è sul ramo), nel `<button ref={expiryButton} …>` della scadenza, nella `className` sostituisci `aria-disabled:opacity-40` con `aria-disabled:text-ink-faint`, e al commento sopra `aria-disabled={busy || undefined}` (quello che finisce con `— finiva sul \`body\``) aggiungi in coda la riga `// Spento non sbiadisce: scrive in \`ink-faint\`, anche sopra il viola di una scadenza`.

- [ ] **Step 4: Passa, e la suite**

Run: `npx vitest run src/components/IngredientPicker.test.tsx && npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde, `N_vitest` + 4 + 7 + 1. I test dei chiamanti (`TermCard` nella coda, `AliasRow` e `ProductScreen` in Anagrafica, l'`IngredientChooser` di S3) restano verdi: nessuno controllava che il campo fosse `disabled`. Se uno lo faceva, è un test del Margine di autonomia.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/IngredientPicker.tsx frontend/src/components/IngredientPicker.test.tsx frontend/src/features/pantry/PantryRow.tsx
git commit -m "feat: il selettore in volo tiene il fuoco (readOnly e aria-disabled), e la scadenza spenta scrive in ink-faint"
```

---

### Task 4: Le caselle da 20 px diventano `Checkbox`, e la prova che l'opacità non torna

**Files:**
- Modify: `frontend/src/features/shopping-list/ListRow.tsx`, `frontend/src/features/cooking/CookSheet.tsx`
- Create: `frontend/src/disabledLook.test.ts`
- Test: `frontend/src/features/shopping-list/ListRow.test.tsx`, `frontend/src/features/cooking/CookSheet.test.tsx`

**Interfaces:**
- Consumes: `Checkbox` (Task 2).

- [ ] **Step 1: I test**

1. In `frontend/src/features/shopping-list/ListRow.test.tsx`, dentro `describe("ListRow", …)`, in fondo:
   ```tsx
     // era un quadratino da 20 px (T3 Consegna 6b): ora la casella di casa, col quadrato da
     // 44 intorno — il bersaglio è la label intera, ma il disegno si vede da 24
     it("la casella è quella di casa: il quadratino da 24 nel quadrato da 44", () => {
       renderRow();
       const casella = screen.getByRole("checkbox", { name: "yogurt greco" });
       expect(casella.className).toContain("size-6");
       expect(casella.parentElement!.className).toContain("size-11");
     });
   ```
2. In `frontend/src/features/cooking/CookSheet.test.tsx` (leggilo com'è sul ramo: il piano 7 vi ha aggiunto prove sulla casella), dentro `describe("CookSheet", …)`, dopo il test `"dichiarare finito un prodotto propone il riacquisto, già spuntato"`:
   ```tsx
     it("la casella «Rimetti in lista» è quella di casa, da 44 px", async () => {
       renderSheet();
       const row = screen.getByText("Total 0%").closest("li")!;
       await userEvent.click(within(row).getByRole("radio", { name: "Finito" }));
       const casella = within(row).getByRole("checkbox", { name: /Rimetti in lista/ });
       expect(casella.className).toContain("size-6");
       expect(casella.parentElement!.className).toContain("size-11");
     });
   ```
3. Crea `frontend/src/disabledLook.test.ts`:
   ```ts
   // @vitest-environment node
   //
   // Questo file non tocca il DOM: legge i sorgenti di `src`. In ambiente `node` per lo
   // stesso motivo di theme.test.ts (l'`URL` di jsdom ignora la base `file://`), e coi tipi
   // di Node chiesti qui, per questo file solo.
   /// <reference types="node" />
   import { readdirSync, readFileSync, statSync } from "node:fs";
   import { join } from "node:path";
   import { fileURLToPath } from "node:url";
   import { describe, expect, it } from "vitest";

   const SRC = fileURLToPath(new URL(".", import.meta.url));

   function sources(dir: string): string[] {
     return readdirSync(dir).flatMap((name) => {
       const path = join(dir, name);
       if (statSync(path).isDirectory()) return sources(path);
       return /\.(ts|tsx)$/.test(name) && !/\.test\./.test(name) ? [path] : [];
     });
   }

   // Lo spento non sbiadisce (tema scuro, 2026-10-07; esteso a tutti i controlli il
   // 2026-10-13): un'`opacity` compone colore e fondo con quel che c'è dietro, e in chiaro
   // portava il testo spento a 1,8:1. Un fondo pieno spento è il grigio `disabled`, un testo
   // spento è `ink-faint`. La prova guarda il sorgente e non il CSS: l'e2e salta il testo
   // sotto un'opacità, e un controllo nuovo che sbiadisce non lo vedrebbe nessuno.
   describe("lo spento", () => {
     it("nessun controllo si spegne con l'opacità", () => {
       const found: string[] = [];
       for (const file of sources(SRC)) {
         readFileSync(file, "utf8")
           .split("\n")
           .forEach((line, index) => {
             if (/(?:^|[\s"'`])(?:aria-)?disabled:opacity-/.test(line)) {
               found.push(`${file.slice(SRC.length)}:${index + 1}`);
             }
           });
       }
       expect(found).toEqual([]);
     });
   });
   ```

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/features/shopping-list/ListRow.test.tsx src/features/cooking/CookSheet.test.tsx src/disabledLook.test.ts`
Expected: FAIL — le due caselle sono `size-5` senza quadrato; `disabledLook` elenca `features/shopping-list/ListRow.tsx` (e nient'altro: i Task 1–3 hanno tolto gli altri). Se elenca altri file, sono `opacity` che un piano della catena ha aggiunto (vedi la Preparazione): portali alla regola qui.

- [ ] **Step 3: Le caselle**

1. In `frontend/src/features/shopping-list/ListRow.tsx`:
   - accanto agli altri import da `../../components/ui/`, aggiungi `import { Checkbox } from "../../components/ui/Checkbox";`;
   - la `<label className="flex min-h-11 min-w-0 flex-1 items-center gap-3 py-1.5">` diventa `<label className="flex min-h-11 min-w-0 flex-1 items-center gap-1">` (il quadrato da 44 di `Checkbox` dà già l'altezza e il respiro);
   - l'`<input type="checkbox" … className="size-5 shrink-0 accent-brand aria-disabled:opacity-40" />` diventa `Checkbox`, con le stesse prop e lo stesso commento sopra `aria-disabled`:
     ```tsx
               <Checkbox
                 aria-label={item.ingredient_name ?? item.raw_text}
                 checked={checked}
                 // `aria-disabled` e non `disabled`, come le tacche della dispensa: il browser
                 // toglie il fuoco a un controllo che diventa `disabled`, e chi spunta con la
                 // tastiera lo ritrovava sul `body` appena partiva la PATCH. La casella resta
                 // controllata: ignorato il cambio, React la ridisegna com'era
                 aria-disabled={busy || undefined}
                 onChange={() => {
                   if (!busy) onToggle();
                 }}
               />
     ```
   - nel commento S17 sopra la label, dopo `ed è alta almeno 44px.` aggiungi ` La casella è \`Checkbox\`, col quadrato da 44 (era un quadratino da 20, T3 Consegna 6b).`
2. In `frontend/src/features/cooking/CookSheet.tsx` (leggilo com'è sul ramo: il piano 7 ha cambiato la condizione sopra la casella, non la casella):
   - accanto agli altri import da `../../components/ui/`, aggiungi `import { Checkbox } from "../../components/ui/Checkbox";`;
   - la `<label className="flex min-h-11 items-center gap-2.5 text-sm text-ink-soft">` che contiene la casella «Rimetti in lista della spesa» diventa `<label className="flex min-h-11 items-center gap-1 text-sm text-ink-soft">`;
   - dentro, l'`<input type="checkbox" aria-label={\`Rimetti in lista ${label}\`} checked={choice.restock} onChange={(e) => setRestock(item.id, e.target.checked)} className="size-5" />` diventa:
     ```tsx
                         <Checkbox
                           aria-label={`Rimetti in lista ${label}`}
                           checked={choice.restock}
                           onChange={(e) => setRestock(item.id, e.target.checked)}
                         />
     ```
     (se sul ramo le prop della casella sono cambiate, tienile com'è sul ramo e cambia solo l'elemento e la `className`).

- [ ] **Step 4: Passano, e la suite**

Run: `npx vitest run src/features/shopping-list/ListRow.test.tsx src/features/cooking/CookSheet.test.tsx src/disabledLook.test.ts && npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde, `N_vitest` + 12 + 3, in `N_file` + 1 file. I test della Lista e della cottura che cercano la casella per ruolo e nome passano senza modifiche.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/shopping-list/ListRow.tsx frontend/src/features/shopping-list/ListRow.test.tsx frontend/src/features/cooking/CookSheet.tsx frontend/src/features/cooking/CookSheet.test.tsx frontend/src/disabledLook.test.ts
git commit -m "feat: le caselle della Lista e del foglio della cottura sono Checkbox da 44 px; una prova tiene fuori ogni spento con opacità"
```

---

### Task 5: «Salva» dei campi del prodotto (`InlineField`)

**Files:**
- Modify (file intero): `frontend/src/features/registry/InlineField.tsx`
- Create: `frontend/src/features/registry/InlineField.test.tsx`
- Test: `frontend/src/features/registry/ProductScreen.test.tsx`

**Interfaces:**
- Consumes: `Button` (Task 1: `unavailableReason` vince su `disabled`).
- Produces: `InlineField` con le stesse prop di oggi (`label`, `value`, `placeholder?`, `inputMode?`, `required?`, `onSave`, `describeError?`).

- [ ] **Step 1: I test**

1. Crea `frontend/src/features/registry/InlineField.test.tsx`:
   ```tsx
   import { useState } from "react";
   import { describe, expect, it, vi } from "vitest";
   import { render, screen, waitFor } from "@testing-library/react";
   import userEvent from "@testing-library/user-event";
   import { InlineField } from "./InlineField";

   /** Il campo con un valore salvato vero: `onSave` lo cambia, come la scheda riletta. */
   function Saved({ start = "Reggiano", fail = false }: { start?: string; fail?: boolean }) {
     const [value, setValue] = useState(start);
     return (
       <InlineField
         label="Nome"
         value={value}
         required
         onSave={async (next) => {
           if (fail) throw new Error("guasto");
           setValue(next);
         }}
       />
     );
   }

   describe("InlineField", () => {
     it("a riposo «Salva» è spento: non c'è niente da salvare", () => {
       render(<Saved />);
       expect(screen.getByRole("button", { name: "Salva nome" })).toBeDisabled();
     });

     it("in volo «Salva» tiene il fuoco, e il campo non si scrive ma resta raggiungibile", async () => {
       const onSave = vi.fn(() => new Promise<void>(() => {}));
       render(<InlineField label="Nome" value="Reggiano" onSave={onSave} />);
       const campo = screen.getByLabelText("Nome");
       await userEvent.type(campo, " 30 mesi");
       const salva = screen.getByRole("button", { name: "Salva nome" });
       salva.focus();
       await userEvent.keyboard("{Enter}");

       expect(onSave).toHaveBeenCalledWith("Reggiano 30 mesi");
       expect(salva).toHaveAttribute("aria-disabled", "true");
       expect(salva).not.toBeDisabled();
       expect(salva).toHaveFocus();
       expect(campo).toHaveAttribute("readonly");
       expect(campo).not.toBeDisabled();
     });

     // Dopo un salvataggio riuscito «Salva» si spegne perché invariato, con `disabled`, che
     // toglie il fuoco: il fuoco torna nel campo prima (pulizie del 2026-10-13)
     it("salvato, il fuoco torna nel campo, e «Salva» si spegne senza averlo", async () => {
       render(<Saved />);
       const campo = screen.getByLabelText("Nome");
       await userEvent.type(campo, " 30 mesi");
       const salva = screen.getByRole("button", { name: "Salva nome" });
       salva.focus();
       await userEvent.keyboard("{Enter}");

       await waitFor(() => expect(campo).toHaveFocus());
       expect(campo).toHaveValue("Reggiano 30 mesi");
       expect(salva).toBeDisabled();
     });

     it("fallito, il fuoco resta su «Salva» e l'errore si legge", async () => {
       render(<Saved fail />);
       await userEvent.type(screen.getByLabelText("Nome"), " 30 mesi");
       const salva = screen.getByRole("button", { name: "Salva nome" });
       salva.focus();
       await userEvent.keyboard("{Enter}");

       expect(
         await screen.findByText("Non sono riuscito a salvare. Quel che hai scritto è ancora qui: riprova.")
       ).toBeInTheDocument();
       expect(salva).toHaveFocus();
       expect(salva).not.toHaveAttribute("aria-disabled");
     });

     it("obbligatorio e vuoto, «Salva» dice perché, senza disabled nativo, e non salva", async () => {
       const onSave = vi.fn();
       render(<InlineField label="Nome" value="Reggiano" required onSave={onSave} />);
       await userEvent.clear(screen.getByLabelText("Nome"));
       const salva = screen.getByRole("button", { name: "Salva nome" });

       expect(salva).not.toBeDisabled();
       expect(salva).toHaveAttribute("aria-disabled", "true");
       expect(salva).toHaveAccessibleDescription("Il campo «Nome» non può restare vuoto.");
       await userEvent.click(salva);
       expect(onSave).not.toHaveBeenCalled();
     });
   });
   ```
2. In `frontend/src/features/registry/ProductScreen.test.tsx`, nel test `"il nome vuoto tiene «Salva nome» spento, e il motivo scritto sotto (F17)"`, la riga
   ```tsx
       expect(screen.getByRole("button", { name: "Salva nome" })).toBeDisabled();
   ```
   diventa (è il `disabled` nativo che questo piano toglie: la prova si fa più stretta, non più larga):
   ```tsx
       // «non ancora», col perché: spento con `aria-disabled`, raggiungibile (pulizie del 2026-10-13)
       const salvaNome = screen.getByRole("button", { name: "Salva nome" });
       expect(salvaNome).toHaveAttribute("aria-disabled", "true");
       expect(salvaNome).not.toBeDisabled();
       expect(salvaNome).toHaveAccessibleDescription("Il campo «Nome» non può restare vuoto.");
   ```
   La riga dopo (`expect(screen.getByText("Il campo «Nome» non può restare vuoto.")).toBeInTheDocument();`) e quelle sulla marca restano.

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/features/registry/InlineField.test.tsx src/features/registry/ProductScreen.test.tsx`
Expected: FAIL — in volo il pulsante è `disabled`; dopo il salvataggio il fuoco non è nel campo; vuoto il pulsante è `disabled` e senza descrizione. «a riposo» passa già.

- [ ] **Step 3: Il componente**

Sostituisci `frontend/src/features/registry/InlineField.tsx` con:

```tsx
import { useId, useRef, useState, type ReactNode } from "react";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";

/** Un campo modificabile in loco, con il suo «Salva» (spec §6.4).
 *
 * Un «Salva» per campo e non uno per la scheda: il nome, la marca e il codice sono tre
 * correzioni indipendenti, e un rifiuto su una non deve trattenere le altre. Se il
 * salvataggio fallisce il campo resta com'era scritto, e l'errore accanto (spec §7):
 * `describeError` lo dice a modo suo quando il rifiuto ha un'uscita da offrire.
 *
 * «Salva» segue la regola dei pulsanti (pulizie del 2026-10-13): in volo è `busy`; a
 * campo obbligatorio vuoto è «non ancora», col perché scritto sotto (`required`, F17: un
 * pulsante spento e muto non si spiega da sé); invariato è `disabled`, lo stato di ogni
 * campo a riposo, dove non c'è niente da spiegare. Un `disabled` toglie il fuoco a chi ce
 * l'ha: per questo, dopo un salvataggio riuscito, il fuoco torna nel campo prima che
 * «Salva» si spenga.
 *
 * L'errore si cancella anche battendo un tasto, non solo quando il valore salvato
 * cambia da fuori: `describeError` (ProductScreen la usa per il rifiuto del codice)
 * riceve la bozza *attuale*, e le sue uscite (le due uscite del rifiuto §7, «Sposta il
 * codice qui» e «Usalo lo stesso») agiscono su quel che le arriva. Senza cancellare
 * l'errore a ogni battuta, un rifiuto rimasto a video dopo che si è scritto un codice
 * diverso mostrerebbe ancora le sue uscite, che manderebbero il codice nuovo — mai
 * confermato — come se fosse quello rifiutato (rilievo della revisione finale S9). */
export function InlineField({
  label,
  value,
  placeholder,
  inputMode,
  required = false,
  onSave,
  describeError,
}: {
  label: string;
  value: string;
  placeholder?: string;
  inputMode?: "text" | "numeric";
  required?: boolean;
  onSave: (next: string) => Promise<unknown>;
  describeError?: (error: unknown, draft: string) => ReactNode;
}) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const saveRef = useRef<HTMLButtonElement>(null);
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  // Il valore salvato cambia da fuori — la scheda riletta dopo un salvataggio, o dopo
  // «Sposta il codice qui» — e il campo lo riprende, perdendo l'errore vecchio. Durante
  // il disegno e non in un effetto, come in PantryRow: un effetto mostrerebbe per un
  // disegno il valore vecchio.
  const [seen, setSeen] = useState(value);
  if (value !== seen) {
    setSeen(value);
    setDraft(value);
    setError(null);
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await onSave(draft.trim());
      // Riuscito: il valore salvato diventa quello scritto, e «Salva» sta per spegnersi
      // perché invariato. In volo era `busy` (il fuoco restava); spento con `disabled` lo
      // perderebbe, e chi usa la tastiera lo ritrovava sulla pagina. Se il fuoco era qui,
      // torna nel campo appena salvato prima che `saving` si spenga.
      if (document.activeElement === saveRef.current) inputRef.current?.focus();
    } catch (caught) {
      setError(caught);
    } finally {
      setSaving(false);
    }
  }

  const trimmed = draft.trim();
  const changed = trimmed !== value;
  const missing = required && trimmed === "";

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={inputId} className="text-sm font-medium text-ink-soft">
        {label}
      </label>
      {/* `flex-wrap` e `[&>p]:basis-full`: il perché di «Salva» è un `<p>` fratello del
          pulsante, che `Button` disegna sotto di sé, e va a capo sotto la riga invece di
          stringere il campo — come nello stepper delle porzioni */}
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 [&>p]:basis-full">
        <input
          id={inputId}
          ref={inputRef}
          value={draft}
          placeholder={placeholder}
          inputMode={inputMode}
          // in volo `readOnly` e non `disabled`: un campo che diventa `disabled` perde il fuoco
          readOnly={saving}
          onChange={(event) => {
            setDraft(event.target.value);
            setError(null);
          }}
          className="min-w-0 flex-1"
        />
        {/* `busy` e `unavailableReason` vincono su `disabled` (Button): in volo e a campo
            vuoto il fuoco resta qui */}
        <Button
          ref={saveRef}
          accessibleName={`Salva ${label.toLowerCase()}`}
          busy={saving}
          disabled={!changed}
          unavailableReason={missing ? `Il campo «${label}» non può restare vuoto.` : undefined}
          onClick={() => void save()}
          className="shrink-0"
        >
          Salva
        </Button>
      </div>
      {error !== null &&
        (describeError ? (
          describeError(error, trimmed)
        ) : (
          <Alert>Non sono riuscito a salvare. Quel che hai scritto è ancora qui: riprova.</Alert>
        ))}
    </div>
  );
}
```

- [ ] **Step 4: Passano, e la suite**

Run: `npx vitest run src/features/registry/InlineField.test.tsx src/features/registry/ProductScreen.test.tsx && npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde, `N_vitest` + 15 + 5, in `N_file` + 2 file. Gli altri test di `ProductScreen.test.tsx` («Salva marca» acceso a marca svuotata, il rifiuto del codice con le sue uscite, «Salva nome» dopo un errore) passano senza modifiche.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/registry/InlineField.tsx frontend/src/features/registry/InlineField.test.tsx frontend/src/features/registry/ProductScreen.test.tsx
git commit -m "feat(anagrafica): «Salva» dei campi del prodotto è Button — busy in volo, il perché a campo vuoto, e il fuoco torna nel campo dopo il salvataggio"
```

---

### Task 6: «Salva prodotto», e «Cambia» fuori dal `<p>`

**Files:**
- Modify: `frontend/src/features/stocking/CustomProductForm.tsx`, `frontend/src/features/registry/MergePanel.tsx`
- Test: `frontend/src/features/stocking/CustomProductForm.test.tsx`, `frontend/src/features/stocking/StockingScreen.test.tsx`, `frontend/src/features/registry/IngredientScreen.test.tsx`

**Interfaces:**
- Consumes: `Button` (Task 1).

- [ ] **Step 1: I test**

1. In `frontend/src/features/stocking/CustomProductForm.test.tsx`, nel test `"un suggerimento senza nome lascia il campo vuoto, e senza nome non si salva"` (è il `disabled` nativo che questo piano toglie):
   - le due righe `expect(save).toBeDisabled();` diventano ciascuna
     ```tsx
           expect(save).toHaveAttribute("aria-disabled", "true");
           expect(save).not.toBeDisabled();
     ```
   - subito dopo la prima delle due, aggiungi
     ```tsx
           expect(save).toHaveAccessibleDescription("Scrivi il nome del prodotto per salvarlo.");
     ```
   - `expect(save).toBeEnabled();` diventa `expect(save).not.toHaveAttribute("aria-disabled");`.
   - In fondo allo stesso `describe("il modulo dice cosa è successo, e non inventa il nome (S20)", …)` aggiungi:
     ```tsx
       it("senza nome, né il tocco né l'Invio nel campo mandano il prodotto", async () => {
         const spy = stubFetch();
         renderForm({ suggestion: { ...SUGGESTION, name: null }, barcode: "88990" });
         await userEvent.click(screen.getByRole("button", { name: "Salva prodotto" }));
         await userEvent.type(screen.getByLabelText("Marca"), "x{Enter}");
         expect(spy).not.toHaveBeenCalled();
       });

       it("in volo «Salva prodotto» è spento ma tiene il fuoco", async () => {
         vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
         renderForm({ suggestion: SUGGESTION, barcode: "88990" });
         const save = screen.getByRole("button", { name: "Salva prodotto" });
         save.focus();
         await userEvent.keyboard("{Enter}");
         await waitFor(() => expect(save).toHaveAttribute("aria-disabled", "true"));
         expect(save).not.toBeDisabled();
         expect(save).toHaveFocus();
       });
     ```
     (`stubFetch`, `renderForm`, `SUGGESTION` sono gli aiuti del file; aggiungi `waitFor` all'import da `@testing-library/react` se non c'è. Se `stubFetch` di questo file non restituisce la spia, usa al suo posto `const spy = vi.fn(); vi.stubGlobal("fetch", spy);` — basta sapere che non è stata chiamata.)
2. In `frontend/src/features/stocking/StockingScreen.test.tsx` (leggilo com'è sul ramo: S3 l'ha cambiato), nel test `"anche senza nome su Open Food Facts la domanda si fa, e il nome parte vuoto"`, la riga `expect(screen.getByRole("button", { name: "Salva prodotto" })).toBeDisabled();` diventa:
   ```tsx
         expect(screen.getByRole("button", { name: "Salva prodotto" })).toHaveAttribute("aria-disabled", "true");
   ```
   (Se S3 ha spostato o tolto quel test, cerca con `grep -n "Salva prodotto\" })).toBeDisabled" frontend/src -r` e cambia allo stesso modo ogni riga che trovi.)
3. In `frontend/src/features/registry/IngredientScreen.test.tsx`, subito dopo la riga `const cambia = screen.getByRole("button", { name: "Cambia" });`, aggiungi:
   ```tsx
       // un `Button` non sta dentro un `<p>`: il suo perché, se un giorno lo avrà, è un `<p>`
       expect(cambia.closest("p")).toBeNull();
   ```

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/features/stocking/CustomProductForm.test.tsx src/features/stocking/StockingScreen.test.tsx src/features/registry/IngredientScreen.test.tsx`
Expected: FAIL — «Salva prodotto» è `disabled` senza descrizione e non `aria-disabled`; «Cambia» sta dentro un `<p>`. «senza nome, né il tocco né l'Invio…» passa già (la guardia in `submit` c'è).

- [ ] **Step 3: Il codice**

1. In `frontend/src/features/stocking/CustomProductForm.tsx`:
   - l'import `import { buttonClasses } from "../../components/ui/buttonClasses";` diventa `import { Button } from "../../components/ui/Button";`;
   - il blocco
     ```tsx
           <div>
             <button type="submit" disabled={create.isPending || nameMissing}
                     className={buttonClasses("primary", "block")}>
               Salva prodotto
             </button>
             {/* un pulsante spento e muto non si spiega da sé */}
             {nameMissing && (
               <p className="pt-2 text-xs text-ink-soft">Scrivi il nome del prodotto per salvarlo.</p>
             )}
           </div>
     ```
     diventa:
     ```tsx
           <div>
             {/* La regola dei pulsanti (pulizie del 2026-10-13): in volo `busy`, senza nome
                 «non ancora» col perché, che `Button` scrive sotto di sé — un pulsante spento
                 e muto non si spiega da sé. Tutti e due con `aria-disabled`: il fuoco resta
                 qui, e anche l'Invio in un campo, che arriva al submit come un clic, si ferma */}
             <Button
               type="submit"
               variant="primary"
               shape="block"
               busy={create.isPending}
               unavailableReason={nameMissing ? "Scrivi il nome del prodotto per salvarlo." : undefined}
             >
               Salva prodotto
             </Button>
           </div>
     ```
   - il `<button type="button" onClick={onCancel} className={\`${buttonClasses("ghost")} self-start\`}>Annulla</button>` diventa:
     ```tsx
           <Button variant="ghost" onClick={onCancel} className="self-start">
             Annulla
           </Button>
     ```
   - il commento dentro `submit`, `// Invio nel campo invia il modulo anche col pulsante spento: la guardia sta qui`, diventa `// la guardia resta anche qui, oltre a quella di \`Button\`: il modulo non deve partire senza nome da nessuna strada`.
2. In `frontend/src/features/registry/MergePanel.tsx`, il contenitore di «Resta: «…»» e «Cambia»: `<p className="flex flex-wrap items-center gap-2 text-sm">` diventa `<div className="flex flex-wrap items-center gap-2 text-sm">`, e la sua chiusura `</p>` (quella subito dopo il `</Button>` di «Cambia») diventa `</div>`. Sopra il `<div>` aggiungi `{/* un \`<div>\` e non un \`<p>\`: un \`Button\` col suo perché porta un \`<p>\`, e un \`<p>\` dentro un \`<p>\` non esiste */}`.

- [ ] **Step 4: Passano, e la suite**

Run: `npx vitest run src/features/stocking src/features/registry && npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde, `N_vitest` + 20 + 2. Il lint segnala un import rimasto e non usato se `buttonClasses` serviva ancora altrove in `CustomProductForm.tsx`: non serve (i due `<button>` erano gli unici).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/stocking/CustomProductForm.tsx frontend/src/features/stocking/CustomProductForm.test.tsx frontend/src/features/stocking/StockingScreen.test.tsx frontend/src/features/registry/MergePanel.tsx frontend/src/features/registry/IngredientScreen.test.tsx
git commit -m "feat: «Salva prodotto» è Button col perché e busy; «Cambia» della fusione esce dal <p>"
```

---

### Task 7: La ✕ e i ruoli del modulo della ricetta

**Files:**
- Modify: `frontend/src/features/recipe-form/RecipeForm.tsx`
- Test: `frontend/src/features/recipe-form/RecipeForm.test.tsx`

**Interfaces:**
- Consumes: `Button`, `IconX`.

- [ ] **Step 1: Il test**

In `frontend/src/features/recipe-form/RecipeForm.test.tsx`, dopo il test `"una riga si toglie con la ✕, il ruolo si cambia, e la nota resta"`, aggiungi:

```tsx
  // erano due `<button>` scritti a mano, la ✕ con un SVG in linea (T3 Consegna 6b): ora
  // sono `Button`, coi 44 px, l'icona di casa e `aria-pressed` per i ruoli
  it("la ✕ e i ruoli sono pulsanti di casa: 44 px, l'icona X, aria-pressed", () => {
    stubCategories([[], 200]);
    renderForm(valuesFromRecipe(DETAIL));

    const togli = screen.getByRole("button", { name: "Togli pasta" });
    expect(togli.className).toContain("size-11");
    expect(togli.querySelector("svg")!.getAttribute("class")).toContain("tabler-icon-x");

    const ruoli = within(screen.getByRole("group", { name: "Ruolo di pasta" }));
    expect(ruoli.getByRole("button", { name: "principale" })).toHaveAttribute("aria-pressed", "true");
    expect(ruoli.getByRole("button", { name: "secondario" })).toHaveAttribute("aria-pressed", "false");
    for (const ruolo of ruoli.getAllByRole("button")) expect(ruolo.className).toContain("min-h-11");
  });
```

- [ ] **Step 2: Fallisce**

Run (da `<worktree>/frontend`): `npx vitest run src/features/recipe-form/RecipeForm.test.tsx`
Expected: FAIL — la ✕ ha un SVG senza classe Tabler.

- [ ] **Step 3: Il codice**

In `frontend/src/features/recipe-form/RecipeForm.tsx`:

1. Accanto agli altri import da `../../components/ui/`, aggiungi `import { IconX } from "../../components/ui/icons";`.
2. In `LineRow`, il commento `{/* la stessa X delle pastiglie del filtro, e per la stessa ragione il nome accessibile nomina la riga: su dodici righe «Togli» da solo non dice quale */}` e il `<button type="button" aria-label={\`Togli ${line.label}\`} onClick={onRemove} className="flex size-11 …">` con il suo `<svg>…</svg>` diventano:
   ```tsx
           {/* la ✕ di casa (`Button` di sola icona, 44 px), come in Lista e in Dispensa; il
               nome accessibile nomina la riga: su dodici righe «Togli» da solo non dice quale */}
           <Button variant="ghost" icon={IconX} label={`Togli ${line.label}`} onClick={onRemove} />
   ```
3. Il contenitore della quantità e dei ruoli, `<div className="flex items-end gap-2">`, diventa `<div className="flex flex-wrap items-end gap-2">` (se a 375 px quantità e ruoli non ci stanno, i ruoli vanno a capo invece di allargare la pagina).
4. Dentro il `role="group"` dei ruoli, il `<button key={role} …>{ROLE_LABELS[role]}</button>` col suo commento diventa:
   ```tsx
                 // `Button` con `aria-pressed`: quello scelto è il primario, l'altro il
                 // secondario col suo anello — un `bg-page` sul fondo della pagina era
                 // un'etichetta, non un bottone da toccare (dal giro)
                 <Button
                   key={role}
                   variant={line.role === role ? "primary" : "secondary"}
                   aria-pressed={line.role === role}
                   onClick={() => onUpdate({ role })}
                 >
                   {ROLE_LABELS[role]}
                 </Button>
   ```

- [ ] **Step 4: Passano, e la suite**

Run: `npx vitest run src/features/recipe-form && npx vitest run && npm run typecheck && npm run lint && grep -n "<button" src/features/recipe-form/RecipeForm.tsx`
Expected: tutto verde, `N_vitest` + 22 + 1; il `grep` vuoto. I test che toccano «Togli …» e i ruoli per nome (in `RecipeForm.test.tsx`, `AiDraftScreen.test.tsx`, `RecipeEditScreen.test.tsx` e quelli di R8) passano senza modifiche.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/recipe-form/RecipeForm.tsx frontend/src/features/recipe-form/RecipeForm.test.tsx
git commit -m "feat(ricette): la ✕ e i ruoli del modulo sono Button — IconX, aria-pressed, 44 px"
```

---

### Task 8: Il fuoco dello stepper, e dopo «Ho cucinato»

**Files:**
- Modify (file intero): `frontend/src/features/cooking/ServingsStepper.tsx`
- Modify: `frontend/src/features/cooking/RecipeDetailScreen.tsx`
- Test: `frontend/src/features/cooking/ServingsStepper.test.tsx`, `frontend/src/features/cooking/RecipeDetailScreen.test.tsx`

**Interfaces:**
- Produces: `ServingsStepper({ value, onChange })` come oggi.

- [ ] **Step 1: I test**

1. In `frontend/src/features/cooking/ServingsStepper.test.tsx`: in cima, aggiungi `import { useState } from "react";`; dopo la costante `MOTIVO` aggiungi
   ```tsx
   /** Lo stepper con le porzioni vere: ogni tocco le cambia, come nel dettaglio. */
   function Stepper({ start }: { start: number }) {
     const [value, setValue] = useState(start);
     return <ServingsStepper value={value} onChange={setValue} />;
   }
   ```
   e dentro `describe("ServingsStepper", …)`, in fondo:
   ```tsx
     // Il tasto arrivato al bordo si spegne con `disabled`, che toglie il fuoco: prima che
     // succeda il fuoco passa all'altro tasto (T3 Consegna 5, pulizie del 2026-10-13)
     it("arrivato a 1 dalla tastiera, il fuoco passa al «+»", async () => {
       render(<Stepper start={2} />);
       const meno = screen.getByRole("button", { name: "Una porzione in meno" });
       meno.focus();
       await userEvent.keyboard("{Enter}");
       expect(screen.getByText("1")).toBeInTheDocument();
       expect(meno).toBeDisabled();
       expect(screen.getByRole("button", { name: "Una porzione in più" })).toHaveFocus();
     });

     it("arrivato a 50, il fuoco passa al «−»", async () => {
       render(<Stepper start={49} />);
       const piu = screen.getByRole("button", { name: "Una porzione in più" });
       piu.focus();
       await userEvent.keyboard("{Enter}");
       expect(screen.getByText("50")).toBeInTheDocument();
       expect(piu).toBeDisabled();
       expect(screen.getByRole("button", { name: "Una porzione in meno" })).toHaveFocus();
     });

     it("lontano dai bordi il fuoco resta sul tasto premuto", async () => {
       render(<Stepper start={3} />);
       const meno = screen.getByRole("button", { name: "Una porzione in meno" });
       meno.focus();
       await userEvent.keyboard("{Enter}");
       expect(screen.getByText("2")).toBeInTheDocument();
       expect(meno).toHaveFocus();
     });
   ```
2. In `frontend/src/features/cooking/RecipeDetailScreen.test.tsx` (leggilo com'è sul ramo: R8, S12, S14 l'hanno cambiato), dentro `describe("il foglio e l'esito si fanno vedere (T4)", …)`, dopo il test `"dopo «Ho cucinato» l'esito passa dall'avviso, e il fuoco torna su «Cucina»"`, aggiungi:
   ```tsx
     it("se dopo «Ho cucinato» la dispensa non si ricarica, il fuoco va su «Riprova» al posto di «Cucina»", async () => {
       // «Cucina» lascia il posto all'avviso, e il fuoco cadeva sulla pagina (T3 Consegna 5)
       let letture = 0;
       vi.stubGlobal(
         "fetch",
         vi.fn((url: unknown) => {
           const path = String(url);
           if (path.includes("/cook")) {
             return Promise.resolve(
               new Response(JSON.stringify({ event_id: "e1", updated: 1, restocked: 1 }), { status: 201 })
             );
           }
           if (path.includes("/pantry")) {
             letture += 1;
             // la prima lettura apre il foglio; quella dopo la cottura fallisce
             return Promise.resolve(
               letture === 1
                 ? new Response(JSON.stringify(PANTRY), { status: 200 })
                 : new Response("", { status: 500 })
             );
           }
           return Promise.resolve(new Response(JSON.stringify(DETAIL), { status: 200 }));
         })
       );
       renderScreen();

       await userEvent.click(await screen.findByRole("button", { name: "Cucina" }));
       const row = (await screen.findByText("Pelati")).closest("li")!;
       await userEvent.click(within(row).getByRole("radio", { name: "Finito" }));
       await userEvent.click(screen.getByRole("button", { name: "Ho cucinato" }));

       const riprova = await screen.findByRole("button", { name: "Riprova" });
       await vi.waitFor(() => expect(riprova).toHaveFocus());
       expect(screen.queryByRole("button", { name: "Cucina" })).toBeNull();
     });
   ```
   (`renderScreen`, `PANTRY`, `DETAIL` sono quelli del file com'è sul ramo; se R8 ha cambiato il nome dell'aiuto di montaggio, usa quello che gli altri test di questo `describe` usano.)

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/features/cooking/ServingsStepper.test.tsx src/features/cooking/RecipeDetailScreen.test.tsx`
Expected: FAIL — nello stepper il fuoco resta sul tasto spento (jsdom non lo toglie, ma non lo sposta nessuno); nel dettaglio il fuoco non è su «Riprova». «lontano dai bordi» passa già.

- [ ] **Step 3: Lo stepper**

Sostituisci `frontend/src/features/cooking/ServingsStepper.tsx` con:

```tsx
import { useRef, type RefObject } from "react";
import { Button } from "../../components/ui/Button";
import { IconMinus, IconPlus } from "../../components/ui/icons";

// Il perché dello stepper fermo. Sta sul «+» soltanto: `Button` disegna il motivo sotto
// di sé, e con due pulsanti la stessa frase comparirebbe due volte in una riga.
const SERVINGS_UNKNOWN = "Porzioni non indicate: si cambiano da «Modifica».";

// la scala delle porzioni, la stessa del backend (`Query(ge=1, le=50)`)
const MIN = 1;
const MAX = 50;

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
  const minusRef = useRef<HTMLButtonElement>(null);
  const plusRef = useRef<HTMLButtonElement>(null);

  // Al bordo il tasto premuto si spegne con `disabled` (è fermo: non c'è un perché da
  // dire), e il browser toglie il fuoco a un pulsante che diventa `disabled` — chi usa la
  // tastiera lo ritrovava sul `body` (T3 Consegna 5). Prima che succeda, se il fuoco era
  // sul tasto premuto, passa all'altro, che a quel punto è acceso. Così niente frase in
  // più sotto lo stepper (pulizie del 2026-10-13).
  function step(
    next: number,
    pressed: RefObject<HTMLButtonElement | null>,
    other: RefObject<HTMLButtonElement | null>
  ) {
    if ((next <= MIN || next >= MAX) && document.activeElement === pressed.current) {
      other.current?.focus();
    }
    onChange(next);
  }

  return (
    // `[&>p]:basis-full`: il motivo del «+» (un `<p>` fratello del `<button>`, disegnato
    // da `Button`) è un figlio diretto di questa riga `flex flex-wrap`; senza questa
    // classe finirebbe a fianco dello stepper invece che a capo, sotto di lui (R-2).
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 [&>p]:basis-full">
      <span className="text-sm text-ink-soft">Porzioni</span>
      <Button
        ref={minusRef}
        icon={IconMinus}
        label="Una porzione in meno"
        disabled={value === null || value <= MIN}
        onClick={() => {
          if (value !== null) step(value - 1, minusRef, plusRef);
        }}
      />
      <span className="min-w-8 text-center font-medium" aria-live="polite">
        {value ?? "—"}
      </span>
      <Button
        ref={plusRef}
        icon={IconPlus}
        label="Una porzione in più"
        disabled={value !== null && value >= MAX}
        unavailableReason={value === null ? SERVINGS_UNKNOWN : undefined}
        onClick={() => {
          if (value !== null) step(value + 1, plusRef, minusRef);
        }}
      />
    </div>
  );
}
```

- [ ] **Step 4: Il dettaglio**

In `frontend/src/features/cooking/RecipeDetailScreen.tsx` (leggilo com'è sul ramo: R8 ha messo il dettaglio dentro un involucro con `key={id}` e ha aggiunto il pannello della variante):

1. Nella query della dispensa (`useQuery({ queryKey: ["pantry"], queryFn: fetchPantry })`), alla destrutturazione aggiungi `isFetching: isPantryFetching,` accanto a `isError: isPantryError,`.
2. Subito dopo `const cookRef = useRef<HTMLButtonElement>(null);` aggiungi `const retryPantryRef = useRef<HTMLButtonElement>(null);`.
3. L'effetto
   ```tsx
     useEffect(() => {
       if (sheetOpen || !refocusCook.current) return;
       refocusCook.current = false;
       cookRef.current?.focus();
     }, [sheetOpen]);
   ```
   diventa:
   ```tsx
     // Se la dispensa non si ricarica, al posto di «Cucina» c'è l'avviso con «Riprova», e il
     // fuoco va lì — anche se l'errore arriva dopo, a fuoco già tornato su «Cucina», che
     // sparendo lo lascia sul `body` (T3 Consegna 5). L'intenzione resta finché la rilettura
     // della dispensa non è finita. Solo se il fuoco è caduto sulla pagina: chi nel frattempo
     // ha toccato altro se lo tiene.
     useEffect(() => {
       if (sheetOpen || !refocusCook.current) return;
       const active = document.activeElement;
       if (active === null || active === document.body) {
         (isPantryError ? retryPantryRef.current : cookRef.current)?.focus();
       }
       if (!isPantryFetching) refocusCook.current = false;
     }, [sheetOpen, isPantryError, isPantryFetching]);
   ```
4. Nel ramo `isPantryError ? (…)` del posto di «Cucina», il pulsante
   ```tsx
                   <button
                     type="button"
                     onClick={() => void refetchPantry()}
                     className={buttonClasses("secondary")}
                   >
                     Riprova
                   </button>
   ```
   diventa:
   ```tsx
                   {/* `busy` mentre rilegge: il fuoco, che può essere arrivato qui dopo
                       «Ho cucinato», resta qui */}
                   <Button ref={retryPantryRef} busy={isPantryFetching} onClick={() => void refetchPantry()}>
                     Riprova
                   </Button>
   ```
   (`Button` è già importato nel file; `buttonClasses` resta, lo usano gli altri link e il «Riprova» della ricetta.)

- [ ] **Step 5: Passano, e la suite**

Run: `npx vitest run src/features/cooking && npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde, `N_vitest` + 23 + 4. I test di oggi «ai bordi il tasto che uscirebbe dalla scala è spento», «dopo «Ho cucinato» … il fuoco torna su «Cucina»» e «annullare il foglio … riporta il fuoco su «Cucina»» passano senza modifiche. Se il test del fuoco su «Cucina» ora fallisce, la condizione «fuoco caduto sulla pagina» non vale in jsdom dopo lo smontaggio del foglio: controlla che `document.activeElement` sia il `body` subito dopo il clic su «Ho cucinato» (jsdom lo rimette sul `body` quando l'elemento col fuoco esce dal DOM), e non indebolire la prova.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/cooking/ServingsStepper.tsx frontend/src/features/cooking/ServingsStepper.test.tsx frontend/src/features/cooking/RecipeDetailScreen.tsx frontend/src/features/cooking/RecipeDetailScreen.test.tsx
git commit -m "feat(cottura): lo stepper passa il fuoco all'altro tasto al bordo; dopo «Ho cucinato» con la dispensa che non torna il fuoco va su «Riprova»"
```

---

### Task 9: Il fuoco dopo l'annullamento di una decisione

**Files:**
- Modify: `frontend/src/features/recipe-import/ImportQueueScreen.tsx`, `frontend/src/features/recipe-import/TermCard.tsx`, `frontend/src/features/recipe-import/DecidedTermRow.tsx`
- Test: `frontend/src/features/recipe-import/ImportQueueScreen.test.tsx`

**Interfaces:**
- Produces: `TermCard` con due prop nuove, `arriving?: boolean` e `onArrived?: () => void`; il nome del termine è un `<p tabIndex={-1}>`. `DecidedTermRow` porta `data-decided-term={term.id}` sul suo `<li>`.

- [ ] **Step 1: Il test**

In `frontend/src/features/recipe-import/ImportQueueScreen.test.tsx`, dentro `describe("coda di revisione dell'import", …)`, dopo il test `"l'esito di un annullamento passa dall'avviso unico, non da una riga della pagina"`, aggiungi:

```tsx
  // La riga annullata sparisce col suo «Annulla», e il fuoco cadeva sulla pagina (T3
  // Consegna 6b): va al nome del termine, tornato in coda come scheda
  it("annullata una decisione, il fuoco va al nome del termine tornato in coda", async () => {
    const DECISO: ImportTerm = {
      id: "t5", display_name: "Speck", occurrences: 3, suggestion: null,
      waiting_titles: ["Pasta e speck"], decided_by: "ai", decided_action: "map",
      decided_name: "speck", decided_at: "2026-10-01T10:00:00Z",
    };
    const TORNATO: ImportTerm = {
      ...DECISO, decided_by: null, decided_action: null, decided_name: null, decided_at: null,
    };
    let annullato = false;
    vi.stubGlobal(
      "fetch",
      vi.fn((url: unknown, init?: RequestInit) => {
        const path = String(url);
        const method = init?.method ?? "GET";
        const rispondi = (body: unknown, status = 200) =>
          Promise.resolve(new Response(JSON.stringify(body), { status }));
        if (path.endsWith("/imports/terms/t5/undo") && method === "POST") {
          annullato = true;
          return rispondi({ recipes_requeued: 1, ingredient_deleted: false, remaining_terms: 3 });
        }
        if (path.includes("decided_by=ai")) return rispondi(annullato ? [] : [DECISO]);
        if (path.includes("decided_by=human")) return rispondi([]);
        if (path.includes("/imports/terms")) return rispondi(annullato ? [...TERMINI, TORNATO] : TERMINI);
        if (path.includes("/imports/status")) return rispondi(STATO_NORMALE);
        return rispondi({}, 404);
      })
    );
    renderScreen();

    const annulla = await screen.findByRole("button", { name: "Annulla la decisione su «Speck»" });
    annulla.focus();
    await userEvent.keyboard("{Enter}");

    await screen.findByRole("button", { name: "Ignora «Speck»" });
    await waitFor(() => {
      expect(document.activeElement?.tagName).toBe("P");
      expect(document.activeElement).toHaveTextContent("Speck");
    });
  });
```

(`TERMINI`, `STATO_NORMALE`, `renderScreen`, `ImportTerm`, `waitFor`, `userEvent` sono già nel file; se la forma di `ImportTerm` sul ramo ha campi in più, aggiungili a `DECISO` come nelle voci di `TERMINI`.)

- [ ] **Step 2: Fallisce**

Run (da `<worktree>/frontend`): `npx vitest run src/features/recipe-import/ImportQueueScreen.test.tsx`
Expected: FAIL — `document.activeElement` è il `BODY`.

- [ ] **Step 3: Il codice**

1. In `frontend/src/features/recipe-import/DecidedTermRow.tsx`, in `DecidedTermRow`, il `<li className="flex items-center justify-between gap-3 border-b border-line py-3 last:border-b-0">` prende `data-decided-term={term.id}` (prima di `className`), e sopra la riga `return (` aggiungi:
   ```tsx
     // `data-decided-term`: la scheda del termine tornato in coda aspetta che questa riga,
     // col fuoco sul suo «Annulla», se ne sia andata (TermCard)
   ```
2. In `frontend/src/features/recipe-import/TermCard.tsx`:
   - l'import `import { useState } from "react";` diventa `import { useEffect, useRef, useState } from "react";`;
   - alle prop, dopo `onDecide,` aggiungi `arriving = false,` e `onArrived,`; nel tipo, dopo `onDecide: (decision: Decision) => void;` aggiungi:
     ```tsx
       /** Il termine è appena tornato in coda da un annullamento: la scheda prende il fuoco
        * sul nome, se è caduto sulla pagina. */
       arriving?: boolean;
       /** Detto quando la scheda ha fatto quel che doveva col fuoco. */
       onArrived?: () => void;
     ```
   - subito dopo `const [newCategory, setNewCategory] = useState<string>("altro");` aggiungi:
     ```tsx
       // Annullata una decisione, la riga di «Decisioni recenti» sparisce col suo «Annulla»
       // e il termine torna qui: il fuoco cadeva sulla pagina (T3 Consegna 6b). Va al nome,
       // così chi ascolta sente quale termine è tornato e il Tab lo porta alle scelte. Solo
       // se è caduto: chi nel frattempo ha toccato altro se lo tiene. Se l'«Annulla» del
       // termine ha ancora il fuoco (la coda si è riletta prima delle decisioni recenti), si
       // aspetta il disegno dopo: per questo l'effetto gira a ogni disegno, e torna subito
       // indietro finché `arriving` è falso.
       const nameRef = useRef<HTMLParagraphElement>(null);
       useEffect(() => {
         if (!arriving) return;
         const active = document.activeElement;
         const row = active instanceof HTMLElement ? active.closest("[data-decided-term]") : null;
         if (row?.getAttribute("data-decided-term") === term.id) return;
         if (active === null || active === document.body) nameRef.current?.focus();
         onArrived?.();
       });
     ```
   - il nome, `<p className="font-medium">{term.display_name}</p>`, diventa:
     ```tsx
             <p
               ref={nameRef}
               tabIndex={-1}
               className="rounded-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
             >
               {term.display_name}
             </p>
     ```
3. In `frontend/src/features/recipe-import/ImportQueueScreen.tsx`:
   - subito dopo `const [undoError, setUndoError] = useState<string | null>(null);` aggiungi:
     ```tsx
       // il termine appena annullato, finché la sua scheda non ha preso il fuoco (TermCard)
       const [arriving, setArriving] = useState<string | null>(null);
     ```
   - nell'`undo` (`useMutation({ mutationFn: (termId: string) => undoTerm(termId), …`): in `onMutate`, dopo `setUndoError(null);` aggiungi `setArriving(null);`; `onSuccess: (result) => {` diventa `onSuccess: (result, termId) => {`, e dopo `setLastRun(null);` aggiungi `setArriving(termId);`;
   - su **ognuna** delle `TermCard` della schermata (quella del termine messo a fuoco, `key={\`${focused.id}-in-coda\`}`, e quelle dell'elenco, `key={term.id}`; più eventuali altre che il ramo abbia aggiunto) aggiungi, accanto a `onDecide`:
     ```tsx
                   arriving={arriving === focused.id}
                   onArrived={() => setArriving(null)}
     ```
     (con `term.id` al posto di `focused.id` nell'elenco).

- [ ] **Step 4: Passa, e la suite**

Run: `npx vitest run src/features/recipe-import && npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde, `N_vitest` + 27 + 1. Gli altri test della coda passano senza modifiche (nessuno guardava il fuoco dopo un annullamento).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/recipe-import/ImportQueueScreen.tsx frontend/src/features/recipe-import/TermCard.tsx frontend/src/features/recipe-import/DecidedTermRow.tsx frontend/src/features/recipe-import/ImportQueueScreen.test.tsx
git commit -m "feat(coda): annullata una decisione, il fuoco va al nome del termine tornato in coda"
```

---

### Task 10: Nel browser vero — gli spenti a video nei due temi, lo stepper e la casella da tastiera

jsdom non calcola il CSS: che `aria-disabled:accent-ink-faint` e `bg-on-disabled` arrivino a video, e che l'opacità sia davvero 1, lo dice solo il browser. E lo stepper: in Chromium un pulsante che diventa `disabled` perde il fuoco davvero.

**Files:**
- Modify: `frontend/e2e/style.spec.ts`

**Interfaces:**
- Consumes: `tokenIn(tema, nome)`, `fermo`, `ricettaDiProva` (nel file, dal tema scuro e dai piani prima); le classi dei Task 2–4; lo stepper del Task 8.

Leggi prima il file com'è sul ramo: quasi ogni piano della catena vi ha aggiunto prove in fondo. Le tue vanno dopo l'ultima, in un blocco proprio.

- [ ] **Step 1: Il JSDoc di `testiIlleggibili`**

Nel JSDoc di `testiIlleggibili`, la frase (scritta dal tema scuro) che dice che il testo sotto un'opacità si salta perché i controlli spenti fuori da `Button` si spengono ancora così: sostituisci la parentesi che nomina «i controlli spenti fuori da `Button`» con `(gli elementi velati: dal 2026-10-13 nessun controllo spento usa più l'opacità, e \`src/disabledLook.test.ts\` lo tiene)`. Fai lo stesso nel commento sopra `const SCHERMATE`, dove la parentesi dice `(i controlli spenti fuori da \`Button\`, gli elementi velati)`: diventa `(gli elementi velati)`. Nient'altro cambia nella funzione.

- [ ] **Step 2: Le prove nuove**

In fondo al file, dopo l'ultima prova che c'è sul ramo, aggiungi:

```ts
// --- Pulizie del 2026-10-13: i controlli spenti senza opacità, e il fuoco ---

/** Trattiene le richieste `metodo` verso `rotta` finché non si chiama la funzione che
 * restituisce: un controllo resta «in volo» per tutto il tempo che serve a misurarlo. */
async function trattieni(page: Page, rotta: string, metodo: string): Promise<() => void> {
  let rilascia!: () => void;
  const via = new Promise<void>((resolve) => (rilascia = resolve));
  await page.route(rotta, async (route) => {
    if (route.request().method() !== metodo) return route.continue();
    await via;
    return route.continue();
  });
  return rilascia;
}

/** Le proprietà calcolate che servono qui, così come il browser le dà. */
async function stileDi(elemento: Locator) {
  return elemento.evaluate((el) => {
    const s = el.ownerDocument.defaultView.getComputedStyle(el);
    return {
      opacita: s.opacity as string,
      colore: s.color as string,
      fondo: s.backgroundColor as string,
      accento: s.accentColor as string,
    };
  });
}

for (const tema of ["light", "dark"] as const) {
  test.describe(`controlli spenti senza opacità, tema ${tema === "light" ? "chiaro" : "scuro"}`, () => {
    test.use({ colorScheme: tema });

    test("in Lista la casella in volo è grigia e piena, nel suo quadrato da 44 px", async ({ page }) => {
      await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
      const creata = await page.request.post("/api/v1/shopping-list", {
        data: { raw_text: "prova casella spenta", ingredient_id: null },
      });
      expect(creata.ok()).toBe(true);
      const id = ((await creata.json()) as { id: string }).id;
      const rotta = `**/api/v1/shopping-list/${id}`;
      try {
        const rilascia = await trattieni(page, rotta, "PATCH");
        await page.goto("/lista");
        const casella = page.getByRole("checkbox", { name: "prova casella spenta" });
        const quadrato = (await casella.locator("xpath=..").boundingBox())!;
        expect(quadrato.width).toBeGreaterThanOrEqual(44);
        expect(quadrato.height).toBeGreaterThanOrEqual(44);

        const risposta = page.waitForResponse(
          (r) => r.request().method() === "PATCH" && r.url().includes(`/shopping-list/${id}`)
        );
        await casella.click();
        await expect(casella).toHaveAttribute("aria-disabled", "true");
        await fermo(page);
        const spenta = await stileDi(casella);
        expect(spenta.opacita).toBe("1");
        expect(spenta.accento).toBe(tokenIn(tema, "ink-faint"));

        rilascia();
        await risposta;
        await expect(casella).not.toHaveAttribute("aria-disabled", "true");
      } finally {
        await page.unroute(rotta);
        const pulizia = await page.request.patch(`/api/v1/shopping-list/${id}`, {
          data: { status: "archived" },
        });
        expect.soft(pulizia.ok(), `pulizia: la voce ${id} non si è archiviata`).toBe(true);
      }
    });

    test("in Dispensa le tacche e la scadenza in volo sono grigie, non sbiadite", async ({ page }) => {
      await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
      const trovati = (await (
        await page.request.get("/api/v1/ingredients/search?q=cavolfiore")
      ).json()) as { id: string; name: string }[];
      const cavolfiore = trovati.find((voce) => voce.name === "cavolfiore");
      expect(cavolfiore, "«cavolfiore» non è nel seme").toBeDefined();
      const creata = await page.request.post("/api/v1/pantry", {
        data: { ingredient_id: cavolfiore!.id, status: "available" },
      });
      expect(creata.ok()).toBe(true);
      const id = ((await creata.json()) as { id: string }).id;
      const rotta = `**/api/v1/pantry/${id}`;
      try {
        const rilascia = await trattieni(page, rotta, "PATCH");
        await page.goto("/dispensa");
        const tacche = page.getByRole("radiogroup", { name: /cavolfiore/ });
        await expect(tacche).toBeVisible();

        const risposta = page.waitForResponse(
          (r) => r.request().method() === "PATCH" && r.url().includes(`/pantry/${id}`)
        );
        await tacche.getByRole("radio", { name: "Quasi finito", exact: true }).click();
        await expect(tacche.getByRole("radio", { name: "Disponibile", exact: true })).toHaveAttribute(
          "aria-disabled",
          "true"
        );
        await fermo(page);
        for (const tacca of await tacche.getByRole("radio").all()) {
          expect((await stileDi(tacca)).opacita).toBe("1");
        }
        const accesa = tacche.locator("[data-lit=true] > span").first();
        expect((await stileDi(accesa)).fondo).toBe(tokenIn(tema, "on-disabled"));
        const scadenza = page.getByRole("button", { name: "+ scadenza per cavolfiore" });
        const spenta = await stileDi(scadenza);
        expect(spenta.opacita).toBe("1");
        expect(spenta.colore).toBe(tokenIn(tema, "ink-faint"));

        rilascia();
        await risposta;
        await expect(tacche.getByRole("radio", { name: "Disponibile", exact: true })).not.toHaveAttribute(
          "aria-disabled",
          "true"
        );
      } finally {
        await page.unroute(rotta);
        const pulizia = await page.request.patch(`/api/v1/pantry/${id}`, { data: { archived: true } });
        expect.soft(pulizia.ok(), `pulizia: la confezione ${id} non si è archiviata`).toBe(true);
      }
    });
  });
}

test("lo stepper delle porzioni da tastiera: arrivato a 1, il fuoco passa al «+»", async ({ page }) => {
  // in Chromium un pulsante che diventa `disabled` perde il fuoco davvero: jsdom no
  await page.getByRole("link", { name: "Ricette", exact: true }).click();
  await page.getByRole("link", { name: /Pasta al pomodoro/ }).first().click();
  const meno = page.getByRole("button", { name: "Una porzione in meno" });
  const piu = page.getByRole("button", { name: "Una porzione in più" });
  await expect(meno).toBeEnabled();
  await meno.focus();
  await page.keyboard.press("Enter");
  await expect(meno).toBeDisabled();
  await expect(piu).toBeFocused();
});

test("nel foglio della cottura la casella «Rimetti in lista» è un bersaglio da 44 px", async ({ page }) => {
  const ricetta = await ricettaDiProva(page);
  try {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(`/ricette/${ricetta.id}`);
    await page.getByRole("button", { name: "Cucina", exact: true }).click();
    const radicchio = page.getByRole("radiogroup", { name: /radicchio/ });
    await radicchio.getByRole("radio", { name: "Finito", exact: true }).click();
    const casella = page.getByRole("checkbox", { name: /Rimetti in lista radicchio/ });
    await expect(casella).toBeChecked();
    const quadrato = (await casella.locator("xpath=..").boundingBox())!;
    expect(quadrato.width).toBeGreaterThanOrEqual(44);
    expect(quadrato.height).toBeGreaterThanOrEqual(44);
    await page.getByRole("button", { name: "Annulla", exact: true }).click();
  } finally {
    await ricetta.pulisci();
  }
});
```

Se `ricettaDiProva` sul ramo ha cambiato nome o forma (un piano della catena può averla toccata), usa quella che usa la prova `"il foglio della cottura a 375px: …"`.

- [ ] **Step 3: Il tipo del file**

Run (da `<worktree>/frontend`): `npm run typecheck && npm run lint && npx playwright test --list 2>/dev/null | tail -n 1`
Expected: puliti; **`N_e2e` + 6**. (`tsc -b` compila anche gli e2e senza la libreria DOM: dentro `evaluate` l'elemento è `any` e si passa da `el.ownerDocument`, come nel resto del file.)

- [ ] **Step 4: Lo stack e2e, e l'e2e intera**

Dalla radice di `<worktree>`, con i comandi delle Global Constraints: `cp .env.example .env`, `up -d --build --wait`, il seme `--con-ricette`, poi `(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)`.

Expected: tutti verdi, `N_e2e` + 6. In particolare «in ogni luogo ogni testo sta sopra 4,5:1» resta verde nei due temi. Se `accento` arriva in una forma diversa da `rgb(r, g, b)` (per esempio `oklab(…)`), è la forma della stringa e non il colore: confronta i tre canali (`(s.match(/[\d.]+/g) ?? []).slice(0, 3)`) con quelli di `tokenIn`, e scrivilo nel report. Ogni altro fallimento si diagnostica: vedi il Margine di autonomia.

Se una prova fallisce e lascia dati nello stack, prima di rieseguire ricrea lo stack da zero. Alla fine, sempre:

```bash
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
rm .env
```

- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/style.spec.ts
git commit -m "e2e: casella, tacche e scadenza spente senza opacità nei due temi; lo stepper e la casella del foglio da tastiera e da pollice"
```

---

### Task 11: I documenti

**Files:**
- Modify: `next-steps.md`

Leggi prima il file com'è sul ramo: i piani della catena l'hanno aggiornato.

- [ ] **Step 1: Le idee chiuse escono**

In `next-steps.md`, sotto «### Idee», togli le dodici righe che cominciano con questi testi (cercale con `grep -n`; se una non c'è più, scrivilo nel report e vai avanti):

1. `- [idea] P3 · Annullando una decisione nella coda la riga sparisce e il fuoco cade sulla pagina`
2. `- [idea] P3 · La casella della Lista (\`ListRow.tsx\`) è ancora un quadratino da 20 px`
3. `- [idea] P3 · Lo stepper delle porzioni spegne il «−» con \`disabled\``
4. `- [idea] P3 · «Elimina» di sola icona non mostra niente mentre archivia`
5. `- [idea] P3 · Se il ricaricamento della dispensa dopo «Ho cucinato» fallisce`
6. `- [idea] P3 · \`IngredientPicker\` spegne campo e suggerimenti con \`disabled\``
7. `- [idea] P3 · \`InlineField.tsx\` (nome, marca e codice del prodotto) ha ancora \`<button disabled>\``
8. `- [idea] P3 · \`CustomProductForm.tsx\` («Salva prodotto») spegne ancora con \`disabled\``
9. `- [idea] P3 · \`Button\` con \`disabled\` e \`unavailableReason\` insieme non è definito`
10. `- [idea] P3 · In \`MergePanel.tsx\` «Cambia» è un \`Button\` dentro un \`<p class="flex">\``
11. `- [idea] P3 · In \`RecipeForm.tsx\` restano due \`<button>\` scritti a mano`
12. `- [idea] P3 · Altri controlli spenti fuori da \`Button\` usano ancora \`opacity\``

- [ ] **Step 2: Le voci nuove**

1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte)_` (se un piano prima di questo l'ha già scritta così stanotte, lasciala).
2. Togli la riga della voce da «In corso» (`grep -n "pulizie-controlli" next-steps.md`); se «In corso» resta vuota, rimetti `_(niente)_`.
3. In cima a «Fatti (recenti)» aggiungi:
   ```markdown
   - [fatto] <data di oggi> · Pulizie dei controlli spenti e del fuoco: casella, tacche, scadenza, suggerimenti e campo del selettore spenti senza opacità (grigio e `ink-faint`, la regola del tema scuro), con una prova che l'opacità non torni; le caselle della Lista e del foglio della cottura sono `Checkbox` da 44 px; il fuoco non cade più (stepper al bordo, selettore in volo, «Salva» dei campi del prodotto, «Salva prodotto», dopo un annullamento in coda, dopo una dispensa che non si ricarica); `Button` fa vincere `busy`/`unavailableReason` su `disabled` e disegna il segno d'attesa sui pulsanti di sola icona; la ✕ e i ruoli del modulo sono `Button`; «Cambia» fuori dal `<p>` [T3] → branch night/pulizie-controlli (da revisionare)
   ```
4. Sotto «### Idee», in fondo, aggiungi:
   ```markdown
   - [idea] P3 · Altri campi si spengono con `disabled` nativo mentre salvano, e perdono il fuoco: il campo del nome di `RenameForm`, il `CategorySelect` di `CategoryForm`, il campo data di `PantryRow` (lo stesso difetto delle pulizie del 2026-10-13, fuori dalle voci di allora) [T3]
   ```
   più, se la Preparazione o il Task 4 hanno trovato altri controlli con `opacity` o altri `disabled` col fuoco, una riga `idea` per ciascuno.
5. In «Da fare a mano (solo Mattia)», in fondo, aggiungi:
   ```markdown
   - [tbd] P3 · Prova sul telefono delle pulizie dei controlli: la casella della Lista grande sotto il pollice; le tacche e la casella grigie per un attimo mentre salvano, al sole, nei due temi; «Elimina» che gira mentre archivia. Nel browser l'e2e misura colori e opacità nei due temi, e il fuoco da tastiera [T3]
   ```
6. Se nella notte sono emerse altre cose da fare fuori da questo piano, aggiungile come `idea` o `tbd` nella sezione giusta.

Se un task si è chiuso `bloccato`, la voce resta in «Bloccati» con la domanda (Margine di autonomia), e la riga dei fatti dice cosa è fatto e cosa no; le idee che quel task chiudeva restano.

- [ ] **Step 3: Commit**

```bash
git add next-steps.md
git commit -m "docs: pulizie dei controlli spenti e del fuoco fatte (da revisionare) — dodici idee chiuse, una nuova"
```

---

### Task 12: La verifica finale, e il report

- [ ] **Step 1: Il frontend**

Da `<worktree>/frontend`:

```bash
npx vitest run
npm run typecheck
npx tsc -b --force
npm run lint
npm run build
```

Expected: vitest tutto verde — **`N_vitest` + 28** (4 + 7 + 1 + 3 + 5 + 2 + 1 + 4 + 1), in **`N_file` + 2** file (`disabledLook.test.ts`, `InlineField.test.tsx`); se il numero differisce, scrivi nel report da dove viene la differenza. Typecheck, lint e build puliti. `npx tsc -b --force` perché `node_modules` è condiviso col checkout principale, e con lui il `tsbuildinfo`.

- [ ] **Step 2: I grep**

Dalla radice del worktree, i quattro comandi di «Comandi di verifica». Expected: tutti vuoti.

- [ ] **Step 3: Il backend, e il suo database**

Da `<worktree>/backend`, il comando di pytest delle Global Constraints. Expected: verde, **`N_pytest`** (questo piano non tocca il backend). Poi:

```bash
docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_controlli WITH (FORCE)'
```

- [ ] **Step 4: L'e2e intera**

Con i comandi delle Global Constraints, su uno stack ricreato da zero. Expected: tutti verdi, `N_e2e` + 6. Poi `down -v` e `rm .env`, sempre.

- [ ] **Step 5: Il report**

Nel report della notte (`docs/night-reports/<data>.md`, sul ramo; se c'è già, scritto dai piani prima di questo, aggiungi una sezione tua in fondo, senza toccare le loro), per questo piano: il ramo e da dove parte; i conti veri (vitest, pytest, e2e) contro quelli della Preparazione; gli `opacity` o i `disabled` trovati oltre a quelli della spec; i test di oggi cambiati (devono essere solo quelli dei Task 5 e 6) e perché; le scelte che Mattia può voler rivedere — il grigio delle tacche e della casella in volo, il segno d'attesa che gira sulle icone in volo, il «Salva» dei campi del prodotto che resta `disabled` a riposo e il fuoco che torna nel campo, il fuoco sul nome del termine dopo un annullamento, i ruoli del modulo in `text-sm` —; e cosa fare al merge con R2 (lo stepper, vedi «Dipendenze»), col piano 9 e coi piani 14 e 15. Niente da fare dopo il deploy, se non le prove sul telefono. Niente push, niente merge, niente deploy.

```bash
git add docs/night-reports/
git commit -m "docs: report della notte, pulizie dei controlli spenti e del fuoco"
```
