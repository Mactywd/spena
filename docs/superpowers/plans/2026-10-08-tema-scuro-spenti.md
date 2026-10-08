# Tema scuro: il pulsante spento e il velo del ☰ — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** il pulsante spento — ogni variante, spento con `disabled`, `busy` o `unavailableReason` — smette di essere un'`opacity` 0,4 illeggibile (1,8:1 in chiaro, un verde torbido in scuro) e diventa un grigio pieno con la sua scritta sopra 4,5:1; il velo del ☰ spegne davvero la pagina anche in scuro (45% in chiaro, 60% in scuro) e il pannello se ne stacca con un bordo in scuro; l'e2e misura da qui in poi anche la scritta dei pulsanti spenti.

**Architecture:** tutto nel frontend, tutto nel CSS: nessuna rotta, nessuna migrazione, nessun cambio di comportamento. Tre token nuovi in `frontend/src/index.css` (`--color-disabled`, `--color-on-disabled`, `--color-panel-edge`) più una variabile non di colore (`--scrim-alpha`), con le loro coppie e la composizione del velo in `frontend/src/theme.test.ts`; `buttonClasses.ts` toglie l'`opacity` dalla `BASE` e dice per ogni variante come si spegne; `AppHeader.tsx` cambia due classi. `Button.tsx` non cambia. L'e2e (`frontend/e2e/style.spec.ts`) prova nel browser vero che le classi con prefisso vincono nel CSS compilato, che il velo ha l'alfa del tema e il pannello il suo bordo, e smette di saltare i pulsanti spenti nel controllo «ogni testo sopra 4,5:1».

**Tech Stack:** React 19, TypeScript, Tailwind 4.3 (token in `@theme`), Vitest (ambiente `node` per `theme.test.ts`, jsdom per il resto), Playwright.

**Spec:** `docs/superpowers/specs/2026-10-06-tema-scuro-bozza.md` (le decisioni sono al §7, tutte prese il 2026-10-07; il metodo di calcolo al §3; le misure ai §4–6). Spec madre: `docs/superpowers/specs/2026-09-28-ridisegno-design.md`, §3.1 (i colori: un blocco `@theme`, ogni coppia testo su fondo sopra 4,5:1) e §3.5 (`Button`). In `docs/prossimi-passi.md`, voce T3, i paragrafi «**Tre punti di disegno del tema scuro per la Consegna 1**» e «**Il secondo si chiude con la Consegna 1**».

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/tema-scuro-spenti` (`.worktrees/` è già in `.gitignore`), ramo `night/tema-scuro-spenti`, creato da **`night/s12-righe-dispensa`** (il ramo di S12, che parte da quello di S3, che parte da `master`). Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì (o dalla sua `frontend/`), mai dalla radice del checkout principale. Il checkout principale non si tocca: se vi trovi modifiche non committate, sono dell'utente. **Nessun push, nessun merge, nessun deploy. Mai `git stash`.**
- **I file che anche i piani prima di questo toccano** — `frontend/src/index.css` e `frontend/src/theme.test.ts` (S12), `frontend/e2e/style.spec.ts` (S3 e S12), `next-steps.md`, `docs/prossimi-passi.md` e il report della notte (tutti): **leggili com'è sul ramo prima di cambiarli**. Il piano descrive ogni modifica contro un'ancora riconoscibile — una costante, una funzione, un elemento JSX per nome, o un testo esatto — e non contro numeri di riga. Dove un piano prima di questo ha aggiunto token in `index.css` o righe in `theme.test.ts`, **aggiungi i tuoi senza toccare i loro**. I file che solo questo piano tocca (`buttonClasses.ts`, `Button.test.tsx`, `AppHeader.tsx`) li dà interi o con blocchi «sostituisci questo con questo»: la Preparazione verifica che sul ramo siano come su `master`.
- **`Button`** (`frontend/src/components/ui/Button.tsx`) **non cambia**. Ha già `busy` e `unavailableReason`, che spengono con `aria-disabled` (il fuoco resta), e `disabled` nativo. **La regola (di Mattia):** in volo → `busy`; «non ancora» → `unavailableReason`; `disabled` nativo solo dove nessuno dei due vale. Questo piano cambia **come si vede** lo spento, non quando un pulsante si spegne.
- Tutto il colore passa dai token di `frontend/src/index.css`. Nessuna schermata nomina un colore crudo: `grep -rn "emerald\|neutral-" frontend/src` resta vuoto. Il testo su un fondo pieno usa il suo `on-*` (qui: `text-on-disabled` su `bg-disabled`). Ogni testo sta sopra 4,5:1, in chiaro e in scuro. **I token nuovi sono esattamente tre — `disabled`, `on-disabled`, `panel-edge` — più la variabile `--scrim-alpha`, coi valori del §7 della bozza; nessun altro.** Ogni token nuovo sta nel blocco `@theme` **e** nel blocco scuro (`theme.test.ts` lo controlla).
- **jsdom non calcola il CSS** (quarta lezione di `CLAUDE.md`): che `aria-disabled:bg-disabled` vinca davvero su `bg-brand`, che `bg-scrim/(--scrim-alpha)` arrivi a video con l'alfa giusta, lo dice solo il browser vero. Per questo ogni task che cambia classi ha la sua prova nel CSS compilato (`npm run build` e un `grep` sul `.css` di `dist/`) e il Task 4 la misura a video.
- Ogni bersaglio resta almeno 44×44 px (`min-h-11` resta nella `BASE`). A 375 px nessuna schermata scorre di lato.
- **Mai un vicolo cieco**: questo piano non spegne niente di nuovo e non toglie strade; se una prova trova un pulsante che si spegne senza perché, non è di questo piano (si annota come idea).
- Le parole a video non cambiano. Gli identificatori in inglese; i commenti in italiano come nel resto del codice, e dicono il perché.
- **Il type check è `npm run typecheck`** (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0 (settima lezione di `CLAUDE.md`).
- Controlli del frontend, da `<worktree>/frontend`: `npx vitest run` (non esiste `npm test`), `npm run typecheck`, `npm run lint`, `npm run build`.
- **Il backend non si tocca** e la sua suite non serve a questo piano: `git diff night/s12-righe-dispensa -- backend` resta vuoto. Se mai servisse pytest, il comando è quello del piano modello (`TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_tema PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q` da `<worktree>/backend`, sul container `spena-db-1`), mai `docker compose up` dal worktree.
- **e2e** sullo stack `spena-e2e`, dalla radice di `<worktree>`. Serve un `.env`: **si copia da `.env.example`, che non ha segreti, solo per la prova, e si cancella alla fine. Mai leggere né copiare il `.env` del checkout principale.** Prima di alzarlo, `docker ps --format '{{.Names}}' | grep spena-e2e`: se c'è e non l'hai alzato tu (un altro piano della notte), non fare `down`, aspetta che sparisca.
  ```bash
  cp .env.example .env
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed --con-ricette
  (cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
  rm .env
  ```
  Il `-p spena-e2e` e il `-f docker-compose.e2e.yml` vanno in ogni comando: un `down -v` sul progetto di default cancellerebbe la dispensa vera. Mai `-f docker-compose.prod.yml`. Una prova fallita lascia dati nello stack: prima di rieseguire, `down -v`, poi `up`, seme e prova. Se il seme di S12 ha cambiato comando o argomenti (leggi il suo piano, `docs/superpowers/plans/` con `s12` o `righe-dispensa` nel nome, e il report della notte), usa il suo.
- Nessuna dipendenza nuova, nessuna migrazione, nessun cambio di configurazione globale.
- **Niente produzione**: nessuna lettura né scrittura. Questo piano non ha azioni sui dati (vedi «Dopo il deploy»).

- **Il database dei test è `spena_test_tema`, non `spena_test`** (deciso dall'orchestrazione della fase giorno del 2026-10-08). Questo ramo discende da `night/s12-righe-dispensa`, che aggiunge la migrazione `0013`, e la suite fa `alembic upgrade head` sul suo database all'avvio: girata su `spena_test` lo porterebbe alla `0013`, e il piano `suggerimenti-soglia`, che parte da `master` (ferma alla `0012`), troverebbe `alembic upgrade head` rotto («Can't locate revision identified by '0013'»). Per questo ogni comando di pytest di questo piano porta `TEST_DATABASE_URL` davanti, e il database si crea nella Preparazione e si toglie alla fine della verifica finale:
  ```bash
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_tema WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_tema'
  # … i task …
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_tema WITH (FORCE)'
  ```
  La creazione va fatta come primo passo della Preparazione, prima di qualunque pytest; il `DROP` come ultimo passo della verifica finale, dopo l'ultimo pytest.

### Preparazione (una volta, prima del Task 1)

- [ ] Il ramo di partenza c'è, e porta la catena:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify night/s12-righe-dispensa
  git log --oneline master..night/s12-righe-dispensa | tail -n 3
  git merge-base --is-ancestor night/s3-ingresso-diretto night/s12-righe-dispensa && echo "S3 dentro S12"
  ```
  Expected: un hash; dei commit (di S3 e di S12); «S3 dentro S12». Questo piano non consuma niente di S3 né di S12 (nessuna funzione, nessun componente): parte da lì solo perché la catena della notte è fissa e S14 parte da questo ramo. Se `night/s12-righe-dispensa` **non c'è**, **fermati**: la catena si è interrotta prima di questo piano, e nessun task di questo piano parte. Il checkout principale non si tocca: la causa va nel report della notte (`docs/night-reports/<data>.md`), sull'ultimo ramo della catena che esiste, con la riga di questa voce segnata `bloccato` in quel ramo e la domanda per Mattia («la catena si è fermata a …: parto da lì o da `master`?»). Se il ramo c'è ma S12 vi ha lasciato la sua voce `bloccato`, si parte lo stesso: il ramo è quello.
- [ ] Dal checkout principale, allinea `node_modules` al lockfile (non aggiunge dipendenze, installa quelle di `package-lock.json`):
  ```bash
  cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund
  ```
- [ ] Crea il worktree dal ramo di S12 e collega `node_modules` (e solo quello: **niente `.env`**):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/tema-scuro-spenti -b night/tema-scuro-spenti night/s12-righe-dispensa
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/tema-scuro-spenti/frontend/node_modules
  ```
- [ ] Cosa hanno già cambiato i piani prima di questo nei file di questo piano:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/tema-scuro-spenti
  git diff --stat master -- \
    frontend/src/components/ui/buttonClasses.ts \
    frontend/src/components/ui/Button.tsx \
    frontend/src/components/ui/Button.test.tsx \
    frontend/src/components/AppHeader.tsx
  git diff --stat master -- frontend/src/index.css frontend/src/theme.test.ts frontend/e2e/style.spec.ts
  ```
  Expected: il primo **vuoto** (il piano dà quei file come li vede su `master`; se uno è cambiato, applica le modifiche di questo piano sopra la versione del ramo, blocco per blocco, invece di sovrascriverlo, e scrivilo nel report). Il secondo può non essere vuoto (S12 aggiunge coppie in `theme.test.ts`, S3 e S12 prove in `style.spec.ts`): leggi quei file per intero prima dei Task 1 e 4.
- [ ] Nessun piano prima di questo ha messo un'`opacity` su un pulsante:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/tema-scuro-spenti
  grep -rn "opacity" frontend/src --include=*.ts --include=*.tsx | grep -v "\.test\."
  ```
  Expected: solo `buttonClasses.ts` (la `BASE`, che il Task 2 cambia) e i sette controlli fuori da `Button` che restano fuori scope — `Checkbox.tsx`, `ListRow.tsx`, `StockGauge.tsx`, `PantryRow.tsx`, `CostPicker.tsx`, `IngredientPicker.tsx`, `OptionList.tsx` (S12 può aver tolto o spostato quella di `PantryRow`). Se una riga nuova mette `opacity` sulle classi di un `Button` o di un elemento con `buttonClasses(...)` (per esempio `className="… aria-disabled:opacity-40"` accanto a un `Button`), toglila nel Task 2, perché lo spento di un pulsante è questa regola, e scrivilo nel report. Un controllo nuovo che non è un pulsante con `opacity` resta com'è e va nel report come candidato all'idea «Altri controlli spenti fuori da `Button`».
- [ ] La voce in `next-steps.md` del ramo passa a `in corso` (regola della notte di `plan-and-build`): trova la riga con `grep -n "Tema scuro: il pulsante primario spento" next-steps.md`, cambiane lo stato in `[in corso]`, spostala sotto «## In corso» (togliendo `_(niente)_` se c'è) e aggiungi in fondo `→ branch night/tema-scuro-spenti`. Commit:
  ```bash
  git add next-steps.md
  git commit -m "docs: tema scuro, pulsanti spenti e velo del ☰ in corso"
  ```
- [ ] La linea di partenza, dal worktree:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/tema-scuro-spenti/frontend && npx vitest run 2>&1 | grep -E "Test Files|Tests "
  npx playwright test --list 2>/dev/null | tail -n 1
  ```
  Expected: vitest tutto verde. **Annota** file e test di vitest (`N_file`, `N_vitest`) e il numero di prove e2e che `--list` stampa (`N_e2e`; non serve lo stack per elencarle). Dipendono da quel che S3 e S12 hanno aggiunto. Se vitest non è verde, fermati: non è un difetto di questo piano, e va scritto nel report.

---

## Obiettivo e contesto

Dal giro a occhio a 375 px della Consegna 1 erano rimasti aperti due punti di disegno del tema scuro. Il pulsante spento è fatto con `opacity` 0,4 nella `BASE` di `buttonClasses`, che compone fondo e scritta con quel che c'è dietro: in scuro il primario diventa un verde torbido con la scritta quasi nera, e — cosa che il giro non diceva — in chiaro va peggio, 1,84:1, un verde pallido con la scritta bianca che non si legge. Tutte e cinque le varianti spente stanno sotto 4,5:1 in tutti e due i temi, e nessun test lo vede, perché `testiIlleggibili` salta ogni testo dentro `[disabled]` o `[aria-disabled=true]`. Il velo del ☰ (`bg-scrim/40`) in scuro non ha dove scendere: la pagina velata sta a 1,05:1 da quella scoperta, e il pannello `card` si stacca dalle schede velate a 1,11:1. La bozza del 2026-10-06 ha misurato le opzioni; il 2026-10-07 sono state decise tutte. Questo piano le costruisce.

## Decisioni prese

Dalla bozza `docs/superpowers/specs/2026-10-06-tema-scuro-bozza.md`, §7, decise il 2026-10-07 (le prime due da Mattia, le altre da Claude su sua delega per le scelte estetiche):

1. **Il pulsante spento diventa grigio pieno** (opzione A): fondo `disabled`, scritta `on-disabled`, niente più `opacity`. Valori: `--color-disabled` `#d8dfdb` in chiaro, `#2a332d` in scuro; `--color-on-disabled` `#4e5a52` in chiaro, `#b4beb8` in scuro (gli stessi di `ink-soft`, con un nome suo per la regola «testo su fondo pieno usa il suo `on-*`»). Scritta su fondo 5,33:1 e 6,83:1; fondo contro `page` 1,22:1 e 1,45:1, contro `card` 1,36:1 e 1,30:1. **Deciso da Mattia.**
2. **La regola vale per tutte le varianti**, nella stessa consegna: `primary` e `warn` spenti con `bg-disabled text-on-disabled`; `secondary` (resta l'anello `line`), `ghost` e `danger` spenti con `text-ink-faint` — sotto i prefissi `disabled:` e `aria-disabled:`. **Deciso da Mattia.**
3. **`busy` resta uguale a spento**: anche il pulsante in volo diventa grigio per la durata della richiesta (`busy` spegne con `aria-disabled`, e `aria-disabled:` porta le stesse classi di `disabled:`). **Deciso da Claude su delega di Mattia.**
4. **I nomi** `disabled` / `on-disabled` (e non `brand-off`), perché lo stesso fondo serve anche a `warn`. **Deciso da Claude su delega di Mattia.**
5. **Il velo: 45% in chiaro e 60% in scuro, più un bordo `panel-edge` sul pannello** (V1 + V2). `--scrim-alpha` `45%` / `60%`, `--color-scrim` non cambia; `--color-panel-edge` `#ffffff` in chiaro (uguale a `card`: il bordo non si vede, il pannello si stacca col suo bianco, 3,35:1 e 3,09:1) e `#5a645e` in scuro (3,29:1 contro la pagina velata, 3,20:1 contro la scheda velata). `AppHeader.tsx`: `bg-scrim/40` → `bg-scrim/(--scrim-alpha)`, e `border-l border-panel-edge` sul pannello. **Deciso da Claude su delega di Mattia.**
6. **L'e2e smette di saltare i pulsanti spenti** nel controllo «ogni testo sopra 4,5:1»: `testiIlleggibili` non salta più `[disabled]` e `[aria-disabled=true]`; il salto per opacità resta, e copre i controlli fuori da `Button`. E una prova misura «Entra» a campo vuoto (`aria-disabled`, raggiungibile senza semina): opacità 1, fondo uguale al token `disabled` del tema, scritta ≥ 4,5:1, nei due temi; una prova misura nel ☰ l'alfa del velo e il bordo del pannello. **Deciso da Claude su delega di Mattia.**

Dalla bozza, §5 A e §6 V1/V2, i test: in `theme.test.ts` la coppia `["on-disabled", "disabled"]` in `PAIRS`; `disabled` contro `page` e `card` ≥ 1,2:1 (perché il pulsante non svanisca); e per ogni tema e per `page` e `card` velate, `max(ratio(card, velata), ratio(panel-edge, velata)) ≥ 3`, con la composizione `mix(scrim, sotto, alfa)` canale per canale in sRGB, arrotondata a 8 bit (§3).

Scelte di questo piano, dove la bozza non arrivava (tecniche, reversibili; **decise da Claude su delega di Mattia**):

7. **`--scrim-alpha: 45%` sta in un `:root` suo, scritto subito prima del blocco scuro**, e non nel `:root` di `--safe-bottom` che la bozza indicava. *Perché:* quel `:root` sta **dopo** il blocco `@media (prefers-color-scheme: dark)`, e due dichiarazioni con lo stesso selettore le decide l'ordine: da lì il 45% vincerebbe anche in scuro, e il 60% non arriverebbe mai a video. Un test di `theme.test.ts` fissa l'ordine; l'e2e lo misura.
8. **La sintassi del velo è `bg-scrim/(--scrim-alpha)`**: verificato il 2026-10-08 con il compilatore di Tailwind 4.3.3 del progetto, produce `background-color: color-mix(in oklab, var(--color-scrim) var(--scrim-alpha), transparent)`. Il ripiego della bozza (un valore arbitrario) non serve.
9. **Le classi dello spento si scrivono una volta**, in due costanti di `buttonClasses.ts` (`OFF_FILLED`, `OFF_TEXT`), con lo stesso elenco sotto `disabled:` e sotto `aria-disabled:`; le varianti le compongono. Tailwind le trova perché le stringhe stanno scritte per intero nel sorgente.
10. **Una prova e2e in più della bozza**: ogni variante di `buttonClasses`, spenta con `disabled` e con `aria-disabled`, su `page` e su una scheda `card`, misurata a video nei due temi — opacità 1 e scritta ≥ 4,5:1, e per `primary` e `warn` il grigio del tema. «Entra» prova un solo pulsante vero; questa prova le cinque varianti, che oggi nessuna schermata seminata mostra tutte spente.
11. **Anche i `<button>` scritti a mano con `buttonClasses(...)`** (`CustomProductForm`, `InlineField`, `RenameForm`, `MergePanel`, `ProductScreen` e gli altri) si spengono grigi: è la stessa `BASE`, e la bozza mette la regola lì. Nessuno di loro si tocca.

## Criteri di accettazione

- [ ] `buttonClasses(...)` non contiene `opacity` per nessuna variante; per ogni variante le classi sotto `disabled:` e sotto `aria-disabled:` sono le stesse; `primary` e `warn` spenti sono `bg-disabled text-on-disabled`, `secondary`, `ghost` e `danger` spenti `text-ink-faint`.
- [ ] In `index.css` ci sono `--color-disabled`, `--color-on-disabled`, `--color-panel-edge` nel blocco `@theme` e nel blocco scuro, coi valori delle Decisioni 1 e 5; `--scrim-alpha` è `45%` in un `:root` prima del blocco scuro e `60%` dentro il blocco scuro.
- [ ] `theme.test.ts`: `on-disabled` su `disabled` ≥ 4,5:1, `disabled` contro `page` e `card` ≥ 1,2:1, il pannello (o il suo bordo) ≥ 3:1 contro `page` e `card` velate, nei due temi; l'alfa chiara del velo sta prima del blocco scuro.
- [ ] Nel ☰ il velo ha `bg-scrim/(--scrim-alpha)` e il pannello `border-l border-panel-edge`; a video l'alfa del velo è quella del tema (0,45 e 0,6) e il bordo sinistro del pannello è largo 1 px, del colore `panel-edge` del tema (e2e).
- [ ] «Entra» a campo vuoto, nei due temi: opacità 1, fondo `disabled`, scritta `on-disabled`, ≥ 4,5:1 (e2e). Ogni variante spenta, in tutti e due i modi, su `page` e `card`: opacità 1 e ≥ 4,5:1 (e2e).
- [ ] `testiIlleggibili` non salta più `[disabled]` né `[aria-disabled=true]`, e «in ogni luogo ogni testo sta sopra 4,5:1» resta verde nei due temi.
- [ ] `Button.tsx` invariato; nessuna parola a video cambiata; nessun test indebolito; l'unico test cambiato è quello che controllava `opacity-40` in `Button.test.tsx`.
- [ ] vitest, typecheck, lint, build e l'e2e intera verdi; `style.spec.ts` ha sei prove nuove (tre per tema).
- [ ] `docs/prossimi-passi.md` e `next-steps.md` aggiornati (Task 5), il report della notte scritto (Task 6).

## Comandi di verifica

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
grep -n "opacity" frontend/src/components/ui/buttonClasses.ts
grep -rn "bg-scrim/40" frontend/src
git diff night/s12-righe-dispensa -- backend
```

Expected: tutti e quattro vuoti. E l'e2e intera con i comandi delle Global Constraints.

## Fuori scope

- **Gli altri controlli spenti con `opacity`, fuori da `Button`**: `Checkbox` e la casella di `ListRow` (`aria-disabled:opacity-40`), le tacche di `StockGauge` e il nome in `PantryRow` (`aria-disabled:opacity-40`), `CostPicker` (`disabled:opacity-60`), `IngredientPicker` e `OptionList` (`disabled:opacity-50`). La bozza li mette fuori (§8: «Hanno lo stesso difetto, misure da fare una per una; voce a parte»), e la voce `idea` in `next-steps.md` che li elenca resta com'è. L'e2e continua a saltarli (il salto per opacità resta).
- Un aspetto proprio per `busy` (per esempio il colore pieno con un'icona che gira): decisione 3, lavoro a parte.
- L'elevazione per luminosità (V3, un token `raised`) e ogni altra superficie sovrapposta.
- Il `background_color` del manifesto e la schermata d'avvio in scuro (nelle prove sul telefono della Consegna 0).
- L'avviso di conferma rovesciato (deciso da Mattia il 2026-09-29, spec T3 §3.5).
- `Button` con `disabled` e `unavailableReason` insieme, i `<button disabled>` di `InlineField` e `CustomProductForm`: idee già in `next-steps.md`, non toccate qui (si vedono grigi come ogni altro spento, per la scelta 11).
- Qualunque modifica al backend.

## Margine di autonomia

- **Liberi:** i nomi di variabili locali, helper di test e funzioni interne non fissati qui; l'ordine dei test dentro un file; l'ordine delle classi Tailwind dentro una stringa; la formulazione dei commenti, purché dicano il perché.
- **Fissi:** i valori dei token e dell'alfa (Decisioni 1 e 5); i nomi `--color-disabled`, `--color-on-disabled`, `--color-panel-edge`, `--scrim-alpha`; le classi per variante (Decisione 2); `data-menu-backdrop` (lo usano `AppHeader.test.tsx` e l'e2e); le soglie dei test (4,5:1, 1,2:1, 3:1).
- **Nessuna dipendenza nuova**, nessuna migrazione, nessun token oltre i tre.
- **Un test di oggi si cambia solo se controllava proprio l'`opacity` dello spento** (`Button.test.tsx`, «lo spento in volo si vede come lo spento vero, in ogni variante»), e lo si sostituisce con controlli più stretti, mai più larghi. Se ne serve un'altra migrazione, scrivila nel report con il perché.
- **Una prova del contrasto che fallisce dopo che `testiIlleggibili` misura gli spenti** (Task 4): è un pulsante spento che sta su un fondo che la bozza non ha misurato — per esempio `ink-faint` su `finished-tint`, che in chiaro sta a 4,47:1. **Non cambiare token e non rimettere il salto.** Scrivi nel report quale testo, su quale fondo, in quale tema e con quale rapporto, fai commit del lavoro sul ramo, segna la voce `bloccato` in `next-steps.md` del ramo con la domanda per Mattia («lo spento di `<variante>` su `<fondo>` sta a `<x>`:1: un colore apposta o un'altra variante per quel pulsante?»), e vai al Task 5. Un colore si decide di giorno.
- **Una decisione non coperta e non reversibile** → si ferma quel task, si fa commit del lavoro parziale sul ramo, lo si segna `bloccato` in `next-steps.md` del ramo con la domanda precisa per Mattia, e si passa al task successivo. Una scelta reversibile e a basso impatto → la più conservativa, annotata nel report della notte.
- Se un test fallisce e non si risolve in modo ragionevole: niente test disattivati, niente asserzioni indebolite; `bloccato` con la diagnosi.

## Dipendenze

**Parte da `night/s12-righe-dispensa`** (S12), che parte da `night/s3-ingresso-diretto` (S3), che parte da `master`: rami a catena, così al merge non ci sono conflitti in `index.css`, `theme.test.ts`, `style.spec.ts` e nei documenti. Da loro questo piano **non consuma niente**. Dopo questo piano partono S14 (`night/s14-cibo-casa`, da questo ramo) e S15: non consumano niente di qui, ma i loro pulsanti spenti saranno già grigi e misurati.

## Dopo il deploy (solo Mattia)

Niente: nessuna migrazione, nessun dato da toccare. Dopo il deploy restano solo le prove a occhio sul telefono (Task 5 le scrive in «Da fare a mano»).

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `frontend/src/index.css` | 1 | `--color-disabled`, `--color-on-disabled`, `--color-panel-edge` nei due blocchi; `--scrim-alpha` |
| `frontend/src/theme.test.ts` | 1 | la coppia dello spento, la forma ≥ 1,2:1, il velo e il suo ordine |
| `frontend/src/components/ui/buttonClasses.ts` | 2 | lo spento per variante, via l'`opacity` |
| `frontend/src/components/ui/Button.test.tsx` | 2 | un test sostituito da quattro |
| `frontend/src/components/AppHeader.tsx` | 3 | il velo per tema, il bordo del pannello |
| `frontend/e2e/style.spec.ts` | 4 | `testiIlleggibili` misura gli spenti; tre aiuti e sei prove in fondo |
| `docs/prossimi-passi.md`, `next-steps.md` | 5 | i documenti |
| `docs/night-reports/<data>.md` | 6 | il report |

---

### Task 1: I token dello spento e del velo, e i loro conti

**Files:**
- Modify: `frontend/src/theme.test.ts`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Produces: le classi Tailwind `bg-disabled`, `text-on-disabled`, `border-panel-edge` (dai token) e la variabile CSS `--scrim-alpha` (in `:root`, non un token), usate dai Task 2 e 3; in `theme.test.ts` le costanti `SHAPE_PAIRS`, `DARK_BLOCK` e le funzioni `mix(top, bottom, alpha)` e `scrimAlpha(block)`.

Leggi prima `frontend/src/theme.test.ts` e `frontend/src/index.css` com'è sul ramo: S12 può aver aggiunto coppie a `PAIRS` o `MARK_PAIRS` e token in `index.css`. Le tue aggiunte stanno accanto alle loro, senza toccarle.

- [ ] **Step 1: I test**

In `frontend/src/theme.test.ts`:

1. In fondo all'array `PAIRS`, dopo l'ultima riga che c'è sul ramo (su `master` è `["dept-sand-ink", "dept-sand"], ["dept-slate-ink", "dept-slate"],`), aggiungi:
   ```ts
   // il pulsante spento, di ogni variante con un fondo pieno (bozza del tema scuro, §5 A)
   ["on-disabled", "disabled"],
   ```
2. Subito dopo la dichiarazione di `MARK_PAIRS` (`const MARK_PAIRS: [string, string][] = [...];`, com'è sul ramo), aggiungi:
   ```ts
   // [fondo, fondo]: un controllo pieno che non deve sparire contro quel che ha intorno, ma
   // nemmeno dire «qui si tocca» come un segno a 3:1. È il grigio del pulsante spento: la
   // soglia di 1,2:1 è quella della bozza del tema scuro (2026-10-06, §5 A), che misura
   // 1,22–1,45:1 contro pagina e scheda.
   const SHAPE_PAIRS: [string, string][] = [
     ["disabled", "page"],
     ["disabled", "card"],
   ];

   // Il blocco scuro di index.css, come lo legge `dark` più sopra: serve anche al velo.
   const DARK_BLOCK = /@media \(prefers-color-scheme: dark\)\s*\{\s*:root\s*\{([\s\S]*?)\}\s*\}/;

   // L'alfa del velo del ☰ (`--scrim-alpha`, in percento) in un pezzo di index.css.
   function scrimAlpha(block: string): number | undefined {
     const percent = block.match(/--scrim-alpha:\s*(\d+(?:\.\d+)?)%\s*;/)?.[1];
     return percent === undefined ? undefined : Number(percent) / 100;
   }

   const lightScrim = scrimAlpha(css.replace(DARK_BLOCK, ""));
   const darkScrim = scrimAlpha(css.match(DARK_BLOCK)?.[1] ?? "");

   // Un colore con alfa sopra un fondo pieno, come lo compone il browser per il velo
   // (`color-mix(…, transparent)` è `scrim` con quell'alfa): in sRGB non lineare, canale per
   // canale, arrotondato a 8 bit — il metodo del §3 della bozza del tema scuro.
   function mix(top: string, bottom: string, alpha: number): string {
     const channel = (hex: string, i: number) => parseInt(hex.slice(i, i + 2), 16);
     return (
       "#" +
       [1, 3, 5]
         .map((i) => Math.round(alpha * channel(top, i) + (1 - alpha) * channel(bottom, i)))
         .map((v) => v.toString(16).padStart(2, "0"))
         .join("")
     );
   }
   ```
3. Dentro `describe("i token del colore", …)`, nel `for (const [mode, palette] of …)`, dopo l'`it.each(MARK_PAIRS)(…)` com'è sul ramo, aggiungi:
   ```ts
       it.each(SHAPE_PAIRS)(`in ${mode}, la forma %s su %s non sparisce: sopra 1,2:1`, (shape, background) => {
         expect(palette[shape], `--color-${shape} manca in ${mode}`).toBeDefined();
         expect(palette[background], `--color-${background} manca in ${mode}`).toBeDefined();
         expect(ratio(palette[shape], palette[background])).toBeGreaterThanOrEqual(1.2);
       });
   ```
4. In fondo al file, dopo la chiusura di `describe("i token del colore", …)`, aggiungi:
   ```ts
   // Il velo del ☰ (bozza del tema scuro, §6, V1 + V2): `scrim` con l'alfa del tema sopra
   // la pagina. In scuro la pagina è già quasi nera e il velo non ha dove scendere: il
   // pannello `card` resta a 1,2:1 da ciò che copre, e a staccarlo è il bordo `panel-edge`.
   // In chiaro il bordo vale quanto `card` e a staccarlo è il bianco del pannello. La
   // soglia è quella di un segno (3:1), per il pannello o per il suo bordo.
   describe("il velo del ☰", () => {
     it("l'alfa del velo è scritta per tutti e due i temi, fra 0 e 1", () => {
       for (const alpha of [lightScrim, darkScrim]) {
         expect(alpha).toBeDefined();
         expect(alpha!).toBeGreaterThan(0);
         expect(alpha!).toBeLessThan(1);
       }
     });

     it("l'alfa chiara sta prima del blocco scuro: dopo, a parità di `:root`, vincerebbe anche in scuro", () => {
       const lightAt = css.search(/--scrim-alpha:/);
       const darkBlockAt = css.search(/@media \(prefers-color-scheme: dark\)/);
       expect(lightAt).toBeGreaterThanOrEqual(0);
       expect(lightAt).toBeLessThan(darkBlockAt);
     });

     for (const [mode, palette, alpha] of [
       ["chiaro", light, lightScrim],
       ["scuro", dark, darkScrim],
     ] as const) {
       it.each(["page", "card"])(
         `in ${mode}, il pannello si stacca da %s velata: lui o il suo bordo sopra 3:1`,
         (under) => {
           expect(alpha, `--scrim-alpha manca in ${mode}`).toBeDefined();
           for (const token of ["card", "panel-edge", "scrim", under]) {
             expect(palette[token], `--color-${token} manca in ${mode}`).toBeDefined();
           }
           const veiled = mix(palette.scrim, palette[under], alpha!);
           expect(
             Math.max(ratio(palette.card, veiled), ratio(palette["panel-edge"], veiled))
           ).toBeGreaterThanOrEqual(3);
         }
       );
     }
   });
   ```

- [ ] **Step 2: Fallisce**

Run (da `<worktree>/frontend`): `npx vitest run src/theme.test.ts`
Expected: FAIL — `--color-on-disabled manca in chiaro` (e in scuro), `--color-disabled manca …`, `l'alfa del velo` con `expected undefined to be defined`, e i quattro del pannello per `--scrim-alpha manca`. Le prove di prima restano verdi.

- [ ] **Step 3: I token**

In `frontend/src/index.css`:

1. Nel blocco `@theme`, subito dopo `--color-scrim: #0b0f0d;` (e il suo commento sopra), aggiungi:
   ```css
     /* Il bordo sinistro del pannello del ☰. In scuro la pagina è già quasi nera, il velo
        non ha dove scendere, e il pannello `card` resta a 1,2:1 da ciò che copre: lo stacca
        un segno, non una superficie (bozza del tema scuro, 2026-10-06, §4.2) — 3,29:1 e
        3,20:1 contro la pagina e la scheda velate, theme.test.ts. In chiaro vale quanto
        `card` e non si vede: lì il pannello si stacca col suo bianco. Non è `notch-off`,
        che vuol dire «tacca spenta». */
     --color-panel-edge: #ffffff;
   ```
2. Nel blocco `@theme`, subito dopo `--color-on-brand: #ffffff;`, aggiungi:
   ```css

     /* Il pulsante spento, di ogni variante con un fondo pieno (bozza del tema scuro,
        2026-10-06, decisa il 2026-10-07): un grigio pieno e non un'`opacity`, che
        componeva fondo e scritta con quel che c'era dietro — il primario stava a 1,8:1 in
        chiaro, e in scuro era un verde torbido. Grigio perché «spento» è grigio in ogni
        app, come la tacca spenta: un verde attenuato direbbe ancora «azione principale».
        `on-disabled` vale quanto `ink-soft` ma ha un nome suo, perché il testo su un fondo
        pieno usa il suo `on-*`: se il fondo cambia, la scritta lo segue. 5,33:1 sul fondo,
        e il fondo non sparisce contro pagina e scheda (≥1,2:1, theme.test.ts). */
     --color-disabled: #d8dfdb;
     --color-on-disabled: #4e5a52;
   ```
3. Fra la chiusura del blocco `@theme` (la riga `}` che lo chiude) e il commento che comincia con `/* Il tema scuro: le stesse variabili, altri valori.`, aggiungi:
   ```css

   /* Quanto il velo del ☰ spegne la pagina: 45% in chiaro, 60% in scuro (nel blocco qui
      sotto). Non è un colore e non sta in `@theme`: `AppHeader` la legge con
      `bg-scrim/(--scrim-alpha)`. Sta qui, prima del blocco scuro, e non nel `:root` di
      `--safe-bottom` più in basso: a parità di selettore vince l'ultima dichiarazione, e
      da lì il 45% coprirebbe anche il 60% del tema scuro (theme.test.ts lo controlla). */
   :root {
     --scrim-alpha: 45%;
   }
   ```
4. Nel blocco scuro (`@media (prefers-color-scheme: dark) { :root { … } }`), subito dopo `--color-scrim: #000000;`, aggiungi:
   ```css
       --color-panel-edge: #5a645e;
       --scrim-alpha: 60%;
   ```
   e subito dopo `--color-on-brand: #06170e;`:
   ```css
       --color-disabled: #2a332d;
       --color-on-disabled: #b4beb8;
   ```

- [ ] **Step 4: Passa**

Run: `npx vitest run src/theme.test.ts`
Expected: PASS, **12 test in più** di prima in questo file: 2 (la coppia nei due temi) + 4 (la forma) + 6 (il velo: due generali e quattro del pannello). Se il velo in chiaro fallisce con 2,9:1 o 2,7:1, `--scrim-alpha` chiara non è stata letta come 45% (è ancora il 40% di oggi, o sta nel blocco sbagliato).

- [ ] **Step 5: La suite e il tipo**

Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde; vitest `N_vitest` + 12.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/index.css frontend/src/theme.test.ts
git commit -m "feat: i token del pulsante spento e del bordo del ☰, il velo per tema, e i loro conti in theme.test"
```

---

### Task 2: Il pulsante spento è grigio pieno, in ogni variante

**Files:**
- Modify: `frontend/src/components/ui/buttonClasses.ts`
- Test: `frontend/src/components/ui/Button.test.tsx`

**Interfaces:**
- Consumes: i token `disabled`, `on-disabled`, `ink-faint` (Task 1 e già esistenti).
- Produces: `buttonClasses(variant, shape)` con la stessa firma di oggi; ogni variante porta le sue classi dello spento sotto `disabled:` e `aria-disabled:`. Il Task 4 importa `buttonClasses` e il tipo `ButtonVariant` nell'e2e.

- [ ] **Step 1: I test**

In `frontend/src/components/ui/Button.test.tsx`, dentro `describe("buttonClasses", …)`, **sostituisci** il test

```ts
  it("lo spento in volo si vede come lo spento vero, in ogni variante", () => {
    for (const variant of variants) {
      const classes = buttonClasses(variant).split(/\s+/);
      expect(classes, variant).toContain("disabled:opacity-40");
      expect(classes, variant).toContain("aria-disabled:opacity-40");
    }
  });
```

con:

```ts
  // Lo spento è un colore pieno per tema e non un'`opacity` (bozza del tema scuro,
  // 2026-10-06, decisa il 2026-10-07): l'`opacity` 0,4 portava la scritta di ogni variante
  // sotto 4,5:1, in chiaro fino a 1,8:1. Qui si prova quali classi; che vincano davvero su
  // `bg-brand` nel CSS compilato lo misura e2e/style.spec.ts, perché jsdom non lo calcola.
  function offClasses(variant: ButtonVariant, prefix: "disabled:" | "aria-disabled:"): string[] {
    return buttonClasses(variant)
      .split(/\s+/)
      .filter((c) => c.startsWith(prefix))
      .map((c) => c.slice(prefix.length))
      .sort();
  }

  it("nessuna variante si spegne con l'opacità", () => {
    for (const variant of variants) {
      expect(buttonClasses(variant), variant).not.toMatch(/opacity/);
    }
  });

  it("lo spento in volo si vede come lo spento vero, in ogni variante", () => {
    for (const variant of variants) {
      expect(offClasses(variant, "disabled:").length, variant).toBeGreaterThan(0);
      expect(offClasses(variant, "aria-disabled:"), variant).toEqual(offClasses(variant, "disabled:"));
    }
  });

  it("primario e ambra spenti hanno il grigio pieno e la sua scritta", () => {
    for (const variant of ["primary", "warn"] as const) {
      expect(offClasses(variant, "disabled:"), variant).toEqual(["bg-disabled", "text-on-disabled"]);
    }
  });

  it("le varianti senza fondo pieno, spente, scrivono in ink-faint", () => {
    for (const variant of ["secondary", "ghost", "danger"] as const) {
      expect(offClasses(variant, "disabled:"), variant).toEqual(["text-ink-faint"]);
    }
  });
```

(`variants` e il tipo `ButtonVariant` ci sono già: il primo dentro lo stesso `describe`, il secondo nell'import in cima.)

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/frontend`): `npx vitest run src/components/ui/Button.test.tsx`
Expected: FAIL — «nessuna variante si spegne con l'opacità» (la `BASE` ha `opacity-40`), e gli altri tre perché le classi sotto `disabled:` sono `["opacity-40"]`.

- [ ] **Step 3: Le classi**

In `frontend/src/components/ui/buttonClasses.ts`, sostituisci il commento che comincia con `` // `aria-disabled:opacity-40` accanto a `disabled:opacity-40`: un pulsante in volo `` (le tre righe), la costante `BASE` e la costante `VARIANTS` con:

```ts
//
// Lo spento, per ogni variante e per i tre modi di spegnere — `disabled`, e in `Button`
// `busy` e `unavailableReason`, che spengono con `aria-disabled` per tenere il fuoco — è
// un colore pieno per tema, non un'`opacity`. L'`opacity` 0,4 componeva fondo e scritta
// con quel che c'era dietro, e portava ogni variante sotto 4,5:1: in chiaro il primario a
// 1,8:1, in scuro un verde torbido (bozza del tema scuro, 2026-10-06, decisa il
// 2026-10-07). Un fondo pieno spento diventa il grigio `disabled` con la sua scritta
// `on-disabled`, perché un verde o un'ambra attenuati direbbero ancora «azione
// principale» o «risolvi il problema»; chi non ha fondo scrive in `ink-faint`. Lo stesso
// elenco sotto `disabled:` e sotto `aria-disabled:`: un pulsante in volo deve sembrare
// spento come uno spento davvero. Le classi con prefisso vincono su `bg-brand` perché
// Tailwind scrive le varianti dopo le utilità semplici nel CSS compilato: lo misura
// e2e/style.spec.ts, non jsdom.
const BASE = "inline-flex min-h-11 items-center justify-center gap-2 font-medium transition-colors";

const OFF_FILLED =
  "disabled:bg-disabled disabled:text-on-disabled aria-disabled:bg-disabled aria-disabled:text-on-disabled";
const OFF_TEXT = "disabled:text-ink-faint aria-disabled:text-ink-faint";

const VARIANTS: Record<ButtonVariant, string> = {
  primary: `bg-brand text-on-brand ${OFF_FILLED}`,
  // spento resta l'anello `line`: è la forma del secondario, non il suo colore
  secondary: `bg-card text-ink ring-1 ring-line ring-inset ${OFF_TEXT}`,
  // ambra: lo stesso colore del problema che questo bottone risolve
  warn: `bg-low text-on-low ${OFF_FILLED}`,
  ghost: `text-ink-soft ${OFF_TEXT}`,
  danger: `text-danger ${OFF_TEXT}`,
};
```

Il commento di testa del file (da `// Le classi dei bottoni, non un componente:` fino a `// che in trenta posti dove dimenticarlo è gratis.`) resta com'è; il blocco nuovo comincia con la riga `//` che lo separa. `SHAPES` e `buttonClasses` non cambiano.

Se la Preparazione ha trovato un `opacity` messo da un piano precedente sulle classi di un `Button` o di un elemento con `buttonClasses(...)`, toglilo ora da lì (solo la classe `…:opacity-…`), e scrivilo nel report.

- [ ] **Step 4: Passano**

Run: `npx vitest run src/components/ui/Button.test.tsx`
Expected: PASS (il file ha 3 test in più: uno tolto, quattro aggiunti).

- [ ] **Step 5: Il CSS compilato le ha**

Run (da `<worktree>/frontend`):
```bash
npm run build
grep -o 'aria-disabled\\:bg-disabled[^{]*{[^}]*}' dist/assets/*.css
grep -o 'disabled\\:text-on-disabled:disabled[^{]*{[^}]*}' dist/assets/*.css
```
Expected: la prima stampa una regola con `[aria-disabled=true]` (con o senza virgolette) e `background-color:var(--color-disabled)`; la seconda una regola con `color:var(--color-on-disabled)` (il minificatore può aver unito più selettori in una regola: va bene). Se una delle due non stampa niente, Tailwind non ha trovato le classi nel sorgente: controlla che le stringhe di `OFF_FILLED` e `OFF_TEXT` siano scritte per intero. (Un `opacity` nel CSS compilato resta, ed è atteso: lo usano i controlli fuori scope.)

- [ ] **Step 6: La suite e il tipo**

Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde; vitest `N_vitest` + 15. Nessun altro test cambia: i test che cercano `bg-brand` su un pulsante (`ImportQueueScreen.test.tsx`, `AiDraftScreen.test.tsx`) lo trovano ancora, perché `bg-brand` resta fra le classi.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ui/buttonClasses.ts frontend/src/components/ui/Button.test.tsx
git commit -m "feat: il pulsante spento è grigio pieno in ogni variante, anche in volo; niente più opacity"
```

---

### Task 3: Il velo del ☰ per tema, e il bordo del pannello

**Files:**
- Modify: `frontend/src/components/AppHeader.tsx`

**Interfaces:**
- Consumes: `--scrim-alpha`, il token `panel-edge` (Task 1).
- Produces: il velo `[data-menu-backdrop]` con `bg-scrim/(--scrim-alpha)`; il pannello `role="dialog"` con `border-l border-panel-edge`. Il Task 4 li misura a video.

Nessun test in jsdom: le classi sono la sola cosa che jsdom vedrebbe, e una classe non è una superficie di prova (quarta lezione di `CLAUDE.md`). La prova è nel CSS compilato (Step 2) e a video (Task 4). `AppHeader.test.tsx` non cambia e deve restare verde (usa `[data-menu-backdrop]`, che resta).

- [ ] **Step 1: Le classi**

In `frontend/src/components/AppHeader.tsx`, nel portale del ☰:

1. Il commento sopra il velo, che oggi finisce con `` velo schiarirebbe la pagina invece di spegnerla */} ``, diventa:
   ```tsx
            {/* il tocco fuori chiude: il velo è un bersaglio, non una decorazione. Fuori
                dall'albero accessibile, perché per chi non lo vede la chiusura è Esc o
                «Chiudi il menu». `scrim` e non `ink`: in scuro `ink` è chiaro, e il
                velo schiarirebbe la pagina invece di spegnerla. L'alfa è del tema
                (`--scrim-alpha` in index.css, 45% e 60%): in scuro la pagina è già quasi
                nera, e al 40% di prima il velo non la spegneva */}
   ```
2. Sul `<div data-menu-backdrop="" …>`, `className="absolute inset-0 bg-scrim/40"` diventa:
   ```tsx
              className="absolute inset-0 bg-scrim/(--scrim-alpha)"
   ```
3. Sul pannello (`<div ref={panelRef} role="dialog" …>`), aggiungi `border-l border-panel-edge` alla sua `className`, che diventa:
   ```tsx
              className="absolute inset-y-0 right-0 flex w-72 max-w-[85vw] flex-col border-l border-panel-edge bg-card px-4 pt-1 pb-[calc(1rem+var(--safe-bottom))]"
   ```
   e sopra quel `<div>` aggiungi il commento:
   ```tsx
            {/* il bordo sinistro stacca il pannello dalla pagina velata in scuro, dove
                `card` contro il quasi nero resta a 1,2:1 (`panel-edge`, index.css); in
                chiaro vale quanto `card`, e non si vede */}
   ```

- [ ] **Step 2: Il CSS compilato le ha**

Run (da `<worktree>/frontend`):
```bash
npm run build
grep -o 'scrim-alpha[^;}]*' dist/assets/*.css
grep -o 'border-panel-edge[^{]*{[^}]*}' dist/assets/*.css
```
Expected: la prima stampa la definizione chiara (`scrim-alpha:45%`), quella scura (`scrim-alpha:60%`) e l'uso dentro un `color-mix(in oklab,var(--color-scrim) var(--scrim-alpha),transparent)` (gli spazi possono mancare: è minificato); la seconda una regola con `border-color:var(--color-panel-edge)`. Se l'uso non c'è, la sintassi non è stata riconosciuta: la classe nel sorgente deve essere esattamente `bg-scrim/(--scrim-alpha)`.

- [ ] **Step 3: La suite e il tipo**

Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: tutto verde, `N_vitest` + 15 (nessun test nuovo qui); `AppHeader.test.tsx` invariato e verde.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/AppHeader.tsx
git commit -m "feat: il velo del ☰ al 45% in chiaro e al 60% in scuro, e il pannello col bordo in scuro"
```

---

### Task 4: L'e2e — gli spenti misurati come ogni testo, «Entra», ogni variante e il ☰, nei due temi

jsdom non calcola il CSS: che `aria-disabled:bg-disabled` vinca su `bg-brand` nel CSS compilato, che il velo abbia davvero l'alfa del tema (la cascata del Task 1, scelta 7) e che il bordo arrivi al pannello lo dice solo il browser. **Nessuna prova scrive**: l'accesso esce buttando il cookie, le varianti sono pulsanti creati e tolti dentro la pagina, il ☰ si apre e basta.

**Files:**
- Modify: `frontend/e2e/style.spec.ts`

**Interfaces:**
- Consumes: `buttonClasses` e `ButtonVariant` (Task 2); i token `disabled`, `on-disabled`, `panel-edge` e `--scrim-alpha` in `index.css` (Task 1); `[data-menu-backdrop]` e il `role="dialog"` «Menu» (Task 3). Nel file ci sono già: `tokenDelTema`, `tokenDelTemaScuro`, `contrastoAVideo`, `fermo`, `testiIlleggibili`, `readFileSync`, `fileURLToPath`, `PASSWORD` e il `beforeEach` di testa che fa l'accesso.

Leggi prima il file com'è sul ramo: S3 e S12 vi hanno aggiunto prove in fondo. Le tue vanno dopo le loro, in un blocco proprio.

- [ ] **Step 1: `testiIlleggibili` misura gli spenti**

1. Nel corpo di `testiIlleggibili`, la riga
   ```ts
         if (el.closest("[aria-hidden=true], [disabled], [aria-disabled=true], .sr-only")) continue;
   ```
   diventa
   ```ts
         if (el.closest("[aria-hidden=true], .sr-only")) continue;
   ```
2. Nel suo JSDoc, la frase `Salta ciò che è nascosto, i controlli spenti (WCAG li esenta) e il testo dentro un \`aria-hidden\`.` diventa:
   ```ts
    * Salta ciò che è nascosto, il testo sotto un'opacità minore di 1 (i controlli spenti
    * fuori da `Button`, che si spengono ancora così) e il testo dentro un `aria-hidden`. I
    * pulsanti spenti si misurano come ogni altro testo: WCAG li esenta, la regola di casa
    * no, e dal tema scuro (bozza del 2026-10-06, decisione 6) hanno un colore pieno —
    * lasciarli fuori vorrebbe dire che il prossimo `opacity` torna senza che nessuno lo veda.
   ```
   (riscrivi le righe del JSDoc intorno perché il paragrafo resti leggibile; il resto del JSDoc non cambia).
3. Nel commento sopra `const SCHERMATE` la frase `Salta il testo sotto un antenato con \`opacity\` minore di 1 (i controlli spenti, gli elementi velati), dentro \`aria-hidden\`, \`disabled\` o \`.sr-only\`.` diventa `Salta il testo sotto un antenato con \`opacity\` minore di 1 (i controlli spenti fuori da \`Button\`, gli elementi velati), dentro \`aria-hidden\` o \`.sr-only\`; i pulsanti spenti li misura.`

- [ ] **Step 2: Le prove nuove**

1. In cima al file, l'import
   ```ts
   import { buttonClasses } from "../src/components/ui/buttonClasses.ts";
   ```
   diventa
   ```ts
   import { buttonClasses, type ButtonVariant } from "../src/components/ui/buttonClasses.ts";
   ```
   (se sul ramo quell'import ha già altri nomi, aggiungi solo `type ButtonVariant`).
2. In fondo al file, dopo l'ultima prova che c'è sul ramo, aggiungi:

```ts
// --- Tema scuro: i pulsanti spenti e il velo del ☰ (bozza del 2026-10-06, decisa il 2026-10-07) ---

/** Un token di `index.css` nel tema in prova, come `rgb(r, g, b)`. */
function tokenIn(tema: "light" | "dark", nome: string): string {
  return tema === "light" ? tokenDelTema(nome) : tokenDelTemaScuro(nome);
}

/** L'alfa del velo del ☰ scritta in `index.css` per il tema: `--scrim-alpha`, in un `:root`
 * prima del blocco scuro per il chiaro e dentro il blocco scuro per lo scuro. Letta dal
 * file come i token, per lo stesso motivo: se cambia lì, la prova misura il valore nuovo. */
function veloDelTema(tema: "light" | "dark"): number {
  const css = readFileSync(fileURLToPath(new URL("../src/index.css", import.meta.url)), "utf8");
  const bloccoScuro = /@media \(prefers-color-scheme: dark\)\s*\{\s*:root\s*\{([\s\S]*?)\}\s*\}/;
  const dove = tema === "light" ? css.replace(bloccoScuro, "") : (css.match(bloccoScuro)?.[1] ?? "");
  const percento = dove.match(/--scrim-alpha:\s*(\d+(?:\.\d+)?)%\s*;/)?.[1];
  expect(percento, `--scrim-alpha non è scritta per il tema ${tema} in index.css`).toBeDefined();
  return Number(percento) / 100;
}

/** L'alfa di un colore calcolato dal browser. Chromium rende un `color-mix(in oklab, …,
 * transparent)` come `oklab(L a b / α)` e non come `rgba()` (vedi `testiIlleggibili`): si
 * legge il numero dopo la barra, o il quarto di un `rgba()`. Un colore senza alfa è pieno. */
function alfaDi(colore: string): number {
  const dopoLaBarra = colore.match(/\/\s*([\d.]+)(%?)\s*\)$/);
  if (dopoLaBarra) return Number(dopoLaBarra[1]) / (dopoLaBarra[2] ? 100 : 1);
  const rgba = colore.match(/^rgba\([^,]+,[^,]+,[^,]+,\s*([\d.]+)\s*\)$/);
  return rgba ? Number(rgba[1]) : 1;
}

const VARIANTI: ButtonVariant[] = ["primary", "secondary", "warn", "ghost", "danger"];

for (const tema of ["light", "dark"] as const) {
  test.describe(`spenti e velo, tema ${tema === "light" ? "chiaro" : "scuro"}`, () => {
    test.use({ colorScheme: tema });

    test("«Entra» a campo vuoto è grigio pieno, senza opacità, e la sua scritta si legge", async ({
      page,
    }) => {
      // si esce come nella prova dell'accesso a 375px: aspettato l'accesso del
      // `beforeEach` (o il suo cookie arriverebbe dopo), via il cookie, e il primo 401
      // riporta all'accesso. «Entra» a campo vuoto è `aria-disabled` (`unavailableReason`)
      await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
      await page.context().clearCookies();
      await page.goto("/");
      const entra = page.getByRole("button", { name: "Entra", exact: true });
      await expect(entra).toHaveAttribute("aria-disabled", "true");
      await fermo(page);

      const misura = await contrastoAVideo(entra);
      test.info().annotations.push({
        type: "contrasto",
        description: `«Entra» spento in ${tema}: ${misura.colore} su ${misura.fondo}, ${misura.rapporto.toFixed(2)}:1`,
      });
      // senza opacità, e proprio il grigio del tema: è la prova che `aria-disabled:bg-…`
      // vince su `bg-brand` nel CSS compilato, che jsdom non vede
      expect(misura.opacita).toBe(1);
      expect(misura.fondo).toBe(tokenIn(tema, "disabled"));
      expect(misura.colore).toBe(tokenIn(tema, "on-disabled"));
      expect(misura.rapporto).toBeGreaterThanOrEqual(4.5);
    });

    test("ogni variante spenta, con `disabled` o `aria-disabled`, si legge sulla pagina e su una scheda", async ({
      page,
    }) => {
      // Nessuna schermata seminata mostra spente tutte e cinque le varianti: qui si
      // creano dei pulsanti con le classi vere di `buttonClasses`, come fa la prova del
      // pulsante quadrato, e si tolgono subito. Il CSS è quello compilato e servito.
      await expect(page.getByRole("link", { name: "Ricette", exact: true })).toBeVisible();
      const misure = await page.locator("body").evaluate(
        (body, varianti: { variante: string; classi: string }[]) => {
          const doc = body.ownerDocument;
          const view = doc.defaultView;
          const canali = (c: string) => (c.match(/[\d.]+/g) ?? []).map(Number);
          const lum = (c: string) => {
            const [r, g, b] = canali(c).map((v) => {
              const s = v / 255;
              return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
            });
            return 0.2126 * r + 0.7152 * g + 0.0722 * b;
          };
          const esiti: { dove: string; variante: string; opacita: string; fondo: string | null; colore: string; rapporto: number }[] = [];
          // "" è la pagina (il contenitore è trasparente, dietro c'è il `body`); `bg-card`
          // è una scheda, una classe che l'app usa e che quindi è nel CSS compilato
          for (const sotto of ["", "bg-card"]) {
            const contenitore = doc.createElement("div");
            contenitore.className = sotto;
            body.appendChild(contenitore);
            for (const { variante, classi } of varianti) {
              for (const modo of ["disabled", "aria-disabled"]) {
                const bottone = doc.createElement("button");
                bottone.className = classi;
                if (modo === "disabled") bottone.disabled = true;
                else bottone.setAttribute("aria-disabled", "true");
                bottone.textContent = "Prova";
                contenitore.appendChild(bottone);
                const stile = view.getComputedStyle(bottone);
                let fondo: string | null = null;
                for (let nodo = bottone; nodo && fondo === null; nodo = nodo.parentElement) {
                  const s = view.getComputedStyle(nodo);
                  if ((canali(s.backgroundColor)[3] ?? 1) > 0) fondo = s.backgroundColor;
                }
                const a = lum(stile.color);
                const b = lum(fondo ?? "rgb(255, 255, 255)");
                esiti.push({
                  dove: `${variante} ${modo} su ${sotto || "page"}`,
                  variante,
                  opacita: stile.opacity as string,
                  fondo,
                  colore: stile.color as string,
                  rapporto: (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05),
                });
                bottone.remove();
              }
            }
            contenitore.remove();
          }
          return esiti;
        },
        VARIANTI.map((variante) => ({ variante, classi: buttonClasses(variante) }))
      );

      expect(misure).toHaveLength(VARIANTI.length * 2 * 2);
      for (const m of misure) {
        expect(m.opacita, m.dove).toBe("1");
        expect(m.rapporto, `${m.dove}: ${m.colore} su ${m.fondo}`).toBeGreaterThanOrEqual(4.5);
      }
      // primario e ambra: il grigio pieno del tema, non un verde o un'ambra spenti
      for (const m of misure.filter((m) => m.variante === "primary" || m.variante === "warn")) {
        expect(m.fondo, m.dove).toBe(tokenIn(tema, "disabled"));
        expect(m.colore, m.dove).toBe(tokenIn(tema, "on-disabled"));
      }
    });

    test("il velo del ☰ ha l'alfa del tema, e il pannello il suo bordo", async ({ page }) => {
      // il `beforeEach` di testa preme «Entra» e non aspetta: prima la barra delle schede
      await expect(page.getByRole("link", { name: "Ricette", exact: true })).toBeVisible();
      await page.goto("/lista");
      await page.getByRole("button", { name: "Apri il menu" }).click();
      const pannello = page.getByRole("dialog", { name: "Menu" });
      await expect(pannello).toBeVisible();
      await fermo(page);

      // l'alfa e non la stringa: Chromium può dare `oklab(0 0 0 / 0.6)` invece di `rgba()`.
      // Se l'alfa chiara di index.css stesse dopo il blocco scuro, qui in scuro si
      // leggerebbe 0,45: è la prova della cascata (scelta 7 del piano)
      const velo = await page
        .locator("[data-menu-backdrop]")
        .evaluate((el) => el.ownerDocument.defaultView.getComputedStyle(el).backgroundColor as string);
      expect(alfaDi(velo), `il velo è ${velo}`).toBeCloseTo(veloDelTema(tema), 2);

      await expect(pannello).toHaveCSS("border-left-width", "1px");
      await expect(pannello).toHaveCSS("border-left-style", "solid");
      await expect(pannello).toHaveCSS("border-left-color", tokenIn(tema, "panel-edge"));
    });
  });
}
```

- [ ] **Step 3: Il tipo del file**

Run (da `<worktree>/frontend`): `npm run typecheck && npm run lint`
Expected: puliti. `tsc -b` compila anche gli e2e (`tsconfig.node.json`, senza la libreria DOM: per questo dentro `evaluate` l'elemento è `any` e si passa da `el.ownerDocument`, come nel resto del file). `npx playwright test --list 2>/dev/null | tail -n 1` stampa **`N_e2e` + 6**.

- [ ] **Step 4: Lo stack e2e, e l'e2e intera**

Dalla radice di `<worktree>`, con i comandi delle Global Constraints: `cp .env.example .env`, `up -d --build --wait`, il seme `--con-ricette`, poi `(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)`.

Expected: tutti verdi, `N_e2e` + 6. In particolare, nei due temi, «in ogni luogo ogni testo sta sopra 4,5:1» resta verde anche ora che misura i pulsanti spenti (fra gli altri «Entra» nell'accesso, il «Salva» spento di `InlineField` nella scheda del prodotto, il «−» dello stepper a una porzione se il dettaglio ne ha una).

Se «in ogni luogo ogni testo» trova un pulsante spento sotto 4,5:1: segui il «Margine di autonomia» (non cambiare token, non rimettere il salto; report e `bloccato` con la domanda). Se trova un testo spento che **non** è un pulsante e non ha opacità (un `<textarea disabled>`, un campo con contenuto), scrivilo nel report e segna la voce `bloccato` con la domanda «quel controllo come si spegne?»: non si decide di notte. Se fallisce la prova del velo in scuro con 0,45, l'alfa chiara è dopo il blocco scuro (Task 1, Step 3 punto 3). Ogni altro fallimento si diagnostica, non si migra.

Se una prova fallisce e lascia dati nello stack, prima di rieseguire ricrea lo stack da zero (`down -v`, `up`, seme). Alla fine, sempre:

```bash
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
rm .env
```

- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/style.spec.ts
git commit -m "e2e: i pulsanti spenti misurati come ogni testo; «Entra», ogni variante spenta e il velo del ☰ nei due temi"
```

---

### Task 5: I documenti

**Files:**
- Modify: `docs/prossimi-passi.md`
- Modify: `next-steps.md`

Leggi prima i due file com'è sul ramo: S3 e S12 li hanno aggiornati.

- [ ] **Step 1: Il paragrafo in `docs/prossimi-passi.md`**

Nella voce T3, trova il paragrafo che comincia con `**Il secondo si chiude con la Consegna 1** (2026-09-28)` e finisce con `restano aperti, e non toccano la Dispensa.` (`grep -n "Il secondo si chiude con la Consegna 1" docs/prossimi-passi.md`). Subito dopo quel paragrafo, aggiungi:

```markdown
**Il primo e il terzo si chiudono il <data di oggi>**, sul ramo `night/tema-scuro-spenti`,
non ancora in produzione (bozza `docs/superpowers/specs/2026-10-06-tema-scuro-bozza.md`,
decisa il 2026-10-07). Il pulsante spento non usa più `opacity`, che lo portava a 1,8:1 in
chiaro e a un verde torbido in scuro: `primary` e `warn` spenti hanno un grigio pieno
(`--color-disabled`, `#d8dfdb` / `#2a332d`) con la scritta `on-disabled` (5,33:1 e
6,83:1); `secondary`, `ghost` e `danger` spenti scrivono in `ink-faint`. Vale per
`disabled`, `busy` e `unavailableReason`, e per i `<button>` scritti a mano con
`buttonClasses`. Il velo del ☰ è al 45% in chiaro e al 60% in scuro (`--scrim-alpha`), e il
pannello ha un bordo sinistro `panel-edge` (`#5a645e` in scuro, invisibile in chiaro):
pannello o bordo stanno sopra 3:1 contro la pagina e le schede velate, nei due temi
(`theme.test.ts`). L'e2e misura ora anche la scritta dei pulsanti spenti, in ogni luogo;
restano saltati i testi sotto un'opacità, cioè gli altri controlli spenti fuori da
`Button` (voce a parte in `next-steps.md`).

**Le scelte che Mattia può voler rivedere:** il grigio dello spento anche per il pulsante
in volo (`busy`), per tutta la durata della richiesta; il bordo del ☰ solo in scuro.

**Da provare sul telefono:** il pulsante spento grigio al sole, accanto a un secondario
acceso, nei due temi; il ☰ in scuro, che la pagina si spenga e il pannello si stacchi.
```

Sostituisci `<data di oggi>` con la data vera.

- [ ] **Step 2: `next-steps.md`**

1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte)_` (se un piano prima di questo l'ha già scritta così stanotte, lasciala).
2. Togli la riga della voce dalla sezione dove sta (`grep -n "Tema scuro: il pulsante primario spento" next-steps.md`: la Preparazione l'ha messa in «In corso»); se «In corso» resta vuota, rimetti `_(niente)_`.
3. In cima a «Fatti (recenti)» aggiungi:
   ```markdown
   - [fatto] <data di oggi> · Tema scuro: il pulsante spento è grigio pieno (`disabled` / `on-disabled`) in ogni variante e in volo, niente più `opacity`; il velo del ☰ al 45% / 60% col bordo `panel-edge` in scuro; l'e2e misura anche i pulsanti spenti [T3 Consegna 1] → branch night/tema-scuro-spenti (da revisionare)
   ```
4. In «Da fare a mano (solo Mattia)», in fondo, aggiungi:
   ```markdown
   - [tbd] P3 · Prova sul telefono dei pulsanti spenti e del ☰ (tema scuro): il pulsante spento grigio si legge al sole e si capisce spento accanto a un secondario acceso, nei due temi; il ☰ in scuro spegne la pagina e si stacca col suo bordo. Nel browser l'e2e misura i contrasti nei due temi [T3 Consegna 1]
   ```
5. La voce `idea` che comincia con `- [idea] P3 · Altri controlli spenti fuori da \`Button\`` **non si tocca** (è fuori scope, e resta lei la strada). Se la Preparazione o il Task 4 hanno trovato un controllo spento con `opacity` che quella voce non elenca, aggiungi una riga `idea` nuova sotto di lei che lo nomina, con `[T3 Consegna 1]`, invece di riscriverla.
6. Se nella notte sono emerse altre cose da fare fuori da questo piano, aggiungile come `idea` o `tbd` nella sezione giusta, con la voce di `docs/prossimi-passi.md` fra parentesi quadre.

Se il Task 4 si è chiuso `bloccato`, i punti 2–3 non si fanno: la voce resta in «Bloccati» con la domanda (Margine di autonomia), e il paragrafo dello Step 1 dice cosa è fatto e cosa no.

- [ ] **Step 3: Commit**

```bash
git add docs/prossimi-passi.md next-steps.md
git commit -m "docs: tema scuro, il pulsante spento grigio e il velo del ☰ fatti (da revisionare)"
```

---

### Task 6: La verifica finale, e il report

Niente di nuovo da scrivere nel codice: si prova tutto, dal worktree, com'è sul ramo.

- [ ] **Step 1: Il frontend**

Da `<worktree>/frontend`:

```bash
npx vitest run
npm run typecheck
npx tsc -b --force
npm run lint
npm run build
```

Expected: vitest tutto verde — **`N_vitest` + 15** (12 del Task 1, 3 del Task 2), in **`N_file`** file (nessun file di test nuovo); se il numero differisce, scrivi nel report da dove viene la differenza. Typecheck, lint e build puliti. `npx tsc -b --force` perché `node_modules` è condiviso col checkout principale, e con lui il `tsbuildinfo`: `--force` compila davvero tutto.

- [ ] **Step 2: I grep**

Dalla radice del worktree:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -n "opacity" frontend/src/components/ui/buttonClasses.ts
grep -rn "bg-scrim/40" frontend/src
grep -rn "\[disabled\], \[aria-disabled=true\]" frontend/e2e
git diff night/s12-righe-dispensa -- backend frontend/src/components/ui/Button.tsx
grep -rn "opacity" frontend/src --include=*.ts --include=*.tsx | grep -v "\.test\."
```

Expected: vuoto, vuoto, vuoto, vuoto, vuoto; l'ultimo stampa solo i controlli fuori scope (`Checkbox.tsx`, `ListRow.tsx`, `StockGauge.tsx`, `PantryRow.tsx` se S12 non l'ha cambiato, `CostPicker.tsx`, `IngredientPicker.tsx`, `OptionList.tsx`).

- [ ] **Step 3: L'e2e intera**

Con i comandi delle Global Constraints, su uno stack ricreato da zero (`down -v` prima dell'`up`, se ne era rimasto uno di questo ramo). Expected: tutti verdi, `N_e2e` + 6. Poi `down -v` e `rm .env`, sempre.

- [ ] **Step 4: Il report**

Nel report della notte (`docs/night-reports/<data>.md`, sul ramo; se c'è già, scritto dai piani prima di questo, aggiungi una sezione tua in fondo, senza toccare le loro), per questo piano: il ramo e da dove parte; i conti veri (vitest, e2e) contro quelli della Preparazione; i rapporti misurati a video dalle annotazioni della prova «Entra» (`npx playwright test --reporter=list` le mostra, o il rapporto HTML); cosa ha trovato «in ogni luogo ogni testo» ora che misura gli spenti (niente, o cosa); gli `opacity` trovati nella Preparazione oltre ai sette noti; le decisioni prese in autonomia; **niente da fare dopo il deploy** se non le prove sul telefono. Niente push, niente merge, niente deploy.

```bash
git add docs/night-reports/
git commit -m "docs: report della notte, tema scuro: pulsanti spenti e velo del ☰"
```
