# Due correzioni del frontend: la nota che resta dopo «Annulla» nell'ingresso diretto, e il test che cade sotto carico — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** dopo «Annulla» nell'avviso «In dispensa: …», rileggere lo stesso codice nella serie non dice più «L'hai appena messo in dispensa…». E `useArchiveRecipe.test.tsx` smette di cadere a caso quando la macchina è occupata.

**Architecture:**
- **La nota.** `DirectEntry` ricorda la voce entrata, non solo il prodotto. `PantryScreen`, quando un «Annulla» riesce, le dice quale voce è uscita, e la nota guarda se la voce ricordata è fra quelle.
- **Il test.** Si prova prima l'ipotesi: l'avviso dura 6 s di orologio vero (`NOTICE_MS`), e sotto carico i passi di una prova fra la comparsa dell'avviso e il tocco su «Annulla» o «Riprova» possono superarli. Se l'ipotesi tiene, le prove che toccano un pulsante dell'avviso montano `NoticeProvider` con una durata lunga, che il provider impara a ricevere (`durationMs`). La durata vera resta provata da `NoticeProvider.test.tsx`.

**Tech Stack:** React 19, TanStack Query 5, Vitest + Testing Library. Solo frontend.

**Spec:** le idee P2 di `next-steps.md` «Dopo «Annulla» nell'avviso «In dispensa: …»…» [S3] e «`useArchiveRecipe.test.tsx` fallisce un test…» [Parte X]. Il report `docs/night-reports/2026-10-18.md` («Test instabili»).

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/frontend-annulla-e-test`, ramo `night/frontend-annulla-e-test`, creato da `master`. Nel piano `<worktree>` è quel percorso. **Nessun push, nessun merge, nessun deploy. Mai `git stash`.**
- **Il carico sulla macchina**: al massimo 6 thread e 8 GB (Mattia, 2026-11-22). Ogni corsa più grande di un file gira dentro `systemd-run --user --scope -p MemoryMax=8G -p CPUQuota=600% …`, mai due suite intere insieme; vitest con `--maxWorkers=4` (in una prova di carico, il file ripetuto con `--maxWorkers=1` e la suite accanto con `--maxWorkers=4`).
- **Mai indebolire una prova**: niente `retry`, niente `it.skip`, niente asserzioni tolte, niente attese globali più lunghe (`asyncUtilTimeout` resta 4000, `testTimeout` resta 15 000).
- **La durata vera dell'avviso non cambia** (`NOTICE_MS = 6000`), e il default di `durationMs` è `NOTICE_MS`. L'app non passa mai `durationMs`: `grep -rn "durationMs" frontend/src --include=*.tsx | grep -v test` dà solo `NoticeProvider.tsx`.
- **Il type check è `npm run typecheck`**, mai `tsc --noEmit`. Controlli, da `<worktree>/frontend`: `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`. Nei test dei componenti si usa `createTestQueryClient`.
- Nessuna parola a video nuova, nessun token di colore nuovo, nessuna dipendenza nuova. Il backend non si tocca.

## Review Focus

1. **«Annulla» che fallisce** (l'avviso «Non sono riuscito a togliere … dalla dispensa.» con «Riprova»): la voce è ancora in dispensa, e la nota resta. Task 1.
2. **Due confezioni dello stesso prodotto di fila, poi «Annulla» della seconda**: la nota sparisce, perché la voce ricordata è l'ultima. Che la prima sia ancora in dispensa è vero, ma la serie ricorda solo l'ultima. Task 1.
3. **«Annulla» toccato dopo aver chiuso il pannello**: niente cambia nel pannello chiuso, e riaprendolo la serie riparte da zero come oggi. Task 1.
4. **Le altre prove che toccano un pulsante dell'avviso dopo un'attesa** (nel ricettario, in dispensa, in lista): hanno lo stesso rischio. Task 2 le elenca e le corregge allo stesso modo.
5. **`NoticeProvider` con una durata diversa** si comporta come con quella vera, solo più lungo: lo prova un test del provider. Task 2.

### Preparazione (una volta, prima del Task 1)

- [ ] Il worktree, con `node_modules` collegato:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/frontend-annulla-e-test -b night/frontend-annulla-e-test master
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/frontend-annulla-e-test/frontend/node_modules
  ```
- [ ] Le due voci di `next-steps.md` che citano questo piano passano a `in corso` (` → in corso su night/frontend-annulla-e-test`), e si committa: `next-steps: la nota dopo Annulla e il test sotto carico, in corso`.
- [ ] La linea di partenza: `npx vitest run --maxWorkers=4` dal worktree, tutto verde. **Annota** i numeri.

---

## Decisioni prese

1. **La nota guarda la voce, non solo il prodotto** (Claude, su delega: è un difetto, e la frase non cambia). `DirectEntry` tiene `lastEntered: { itemId: string; productId: string | null } | null`. `justEntered` vale quando il prodotto della scheda è quello ricordato **e** la voce ricordata non è fra quelle annullate.
2. **Chi sa che l'annullamento è riuscito è `PantryScreen`** (`undoEntry`). Tiene un insieme `undoneEntryIds`, gli aggiunge l'id quando il `PATCH archived` riesce, e lo passa a `DirectEntry` come prop `undoneItemIds: ReadonlySet<string>`. Un annullamento fallito non aggiunge niente.
3. **Il test: prima la prova dell'ipotesi, poi la correzione.** La prova non serve un carico: si abbassa la durata. Con `vi.mock` di `../../components/ui/noticeContext`, `NOTICE_MS` a 200 ms, in una copia temporanea del file (che non si committa): le prove che toccano «Annulla» o «Riprova» dopo un'attesa devono cadere nello stesso modo dei rapporti (il pulsante non si trova). Se cadono, l'ipotesi tiene. Se non cadono, l'ipotesi è sbagliata: **fermati**, scrivi nel report cosa hai visto, e lascia la voce `bloccato` con la diagnosi.
4. **La correzione è `durationMs`** su `NoticeProvider` (`durationMs?: number`, default `NOTICE_MS`), usata dalle prove che toccano un pulsante dell'avviso, con un valore che nessuna prova raggiunge (`60_000`). Le prove che misurano la durata usano i finti timer, come oggi in `NoticeProvider.test.tsx`.

## Margine di autonomia

- Liberi: i nomi interni, il nome dell'helper delle prove se ne serve uno (per esempio `renderWithNotice`, nel posto dove stanno gli altri helper delle prove).
- Fissi: `durationMs`, il suo default, `undoneItemIds`.
- **Fermati** nei casi della decisione 3.

---

### Task 1: la nota sparisce con l'annullamento

**Files:**
- Modify: `frontend/src/features/pantry/DirectEntry.tsx` (`lastProductId` diventa `lastEntered`, la prop `undoneItemIds`, `justEntered`)
- Modify: `frontend/src/features/pantry/PantryScreen.tsx` (`undoEntry`, lo stato `undoneEntryIds`, la prop a `DirectEntry`)
- Test: `frontend/src/features/pantry/DirectEntry.test.tsx`, `frontend/src/features/pantry/PantryScreen.test.tsx`

**Interfaces:**
- Produces: `DirectEntry` riceve `undoneItemIds: ReadonlySet<string>`. Nella `submit` della serie, la `onSuccess` della mutazione riceve la voce creata e ne ricorda `id` e prodotto.

- [ ] **Step 1: I test che falliscono.**
  - In `DirectEntry.test.tsx`, «dopo un annullamento la nota sparisce»: entra una confezione a catalogo nella serie; lo stesso codice riletto mostra «L'hai appena messo in dispensa: se è un'altra confezione, mettila pure.»; poi, ridisegnato con `undoneItemIds` che contiene l'id della voce, la stessa scheda non la mostra più.
  - In `PantryScreen.test.tsx`, «Annulla nell'avviso toglie la nota della serie»: il giro intero con il `PATCH {archived: true}` finto che riesce. E «un Annulla fallito la lascia»: con il `PATCH` che fallisce, la nota resta.
- [ ] **Step 2: Falliscono**: `npx vitest run --maxWorkers=1 src/features/pantry/DirectEntry.test.tsx src/features/pantry/PantryScreen.test.tsx`.
- [ ] **Step 3: Il codice**, secondo le decisioni 1 e 2.
- [ ] **Step 4: Passano**, poi `npx vitest run --maxWorkers=4 src/features/pantry`.
- [ ] **Step 5: Commit**: `dispensa: dopo «Annulla» la serie non dice più «L'hai appena messo»`.

### Task 2: le prove che toccano l'avviso non dipendono dai 6 secondi

**Files:**
- Modify: `frontend/src/components/ui/NoticeProvider.tsx` (`durationMs`)
- Modify: `frontend/src/features/recipes/useArchiveRecipe.test.tsx`, e le altre prove trovate allo Step 1
- Test: `frontend/src/components/ui/NoticeProvider.test.tsx`

**Interfaces:**
- Produces: `NoticeProvider({ children, durationMs = NOTICE_MS })`.

- [ ] **Step 1: La prova dell'ipotesi** (decisione 3). Copia `useArchiveRecipe.test.tsx` in un file temporaneo accanto, con in cima il `vi.mock` che mette `NOTICE_MS` a 200, e fallo girare da solo (`--maxWorkers=1`). Annota quali prove cadono e con quale errore, poi **cancella la copia**. Elenca le altre prove che toccano un pulsante dell'avviso dopo un'attesa (`grep -rln "NoticeProvider" frontend/src --include=*.test.tsx`, poi quelle che fanno `click` su «Annulla» o «Riprova» dentro l'avviso). Va tutto nel report.
- [ ] **Step 2: Il test del provider che fallisce**: «con una durata sua, l'avviso resta fino a quella»: con i finti timer, `durationMs={10_000}`, a `NOTICE_MS` l'avviso c'è ancora e a 10 000 non più.
- [ ] **Step 3: Fallisce**: `npx vitest run --maxWorkers=1 src/components/ui/NoticeProvider.test.tsx`.
- [ ] **Step 4: Il codice.** `durationMs` nel provider. Le prove dello Step 1 montano il provider con `durationMs={60_000}` (un commento nel file, una volta, dice perché). Ripeti la copia temporanea dello Step 1 col `vi.mock`: ora nessuna prova cade. Cancella la copia.
- [ ] **Step 5: La prova di carico**, una volta, dentro il limite: in un `systemd-run --user --scope -p MemoryMax=8G -p CPUQuota=600%`, la suite intera con `--maxWorkers=4` e accanto, otto volte, `useArchiveRecipe.test.tsx` con `--maxWorkers=1`. Annota l'esito nel report. Il 2026-11-22, con questo limite, il giorno non l'aveva fatto cadere: l'esito verde non prova la correzione, la prova è lo Step 4.
- [ ] **Step 6: Passano**, poi i controlli interi: `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- [ ] **Step 7: Commit**: `prove: l'avviso non sparisce sotto le dita di una prova lenta`.

### Task 3: il backlog

- [ ] Le due voci passano a `fatto <data>` in «Fatti (recenti)», con ` → branch night/frontend-annulla-e-test (da revisionare)`. Se il Task 2 si è fermato alla decisione 3, la voce del test resta `bloccato` con la diagnosi. Commit: `next-steps: la nota dopo Annulla e il test sotto carico`.

## Fuori scope

- Gli altri test instabili del report del 2026-10-18 (la Lista per reparto, `IngredientScreen`) che non toccano un pulsante dell'avviso: se lo Step 1 del Task 2 li vede cadere, vanno nel report come idea.
- Gli altri esiti silenziosi dell'ingresso diretto (idea P3 a parte).

## Comandi di verifica

- Da `<worktree>/frontend`: `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- `grep -rn "durationMs" frontend/src --include=*.tsx | grep -v test` dà solo `NoticeProvider.tsx`.
- `git -C <worktree> status --short` non mostra copie temporanee dei test.
