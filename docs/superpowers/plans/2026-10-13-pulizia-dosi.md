# Pulizia delle dosi dell'import: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** le dosi che GialloZafferano scrive con gli a capo e le parole davanti («fredda ⏎ 330 ⏎ g», «36 mesi ⏎ 50 ⏎ g», «secco ⏎⏎ q.b.») diventano una dose pulita che si riscala, con le parole nella nota della riga; il parser legge ½ ¼ ¾ e «50 g + q.b.»; l'import pulisce all'ingresso; un comando con `--dry-run` pulisce le righe che ci sono, le rilegge e toglie dal registro `units` le parole che unità non sono; il dettaglio della ricetta mostra la nota sotto il nome.

**Architecture:** il dominio (`backend/app/domain/quantities.py`) impara le frazioni di un carattere e il pezzo «q.b.» in `parse_quantity`, e guadagna tre funzioni pure: `clean_dose` (separa nota e dose), `merge_notes` (unisce le note), `with_qb_tail` (rimette «+ q.b.» accanto a una dose riscalata). Le chiamano: `_to_out` del dettaglio (`with_qb_tail`), `materialize_ready` (pulisce dove il `payload` diventa ricetta), la fusione dell'anagrafica (unisce le note di due righe gemelle) e un comando nuovo, `python -m app.cli.clean_doses`, che legge tutte le righe a tuple, pulisce, rilegge con `parse_quantity` + `ensure_unit` come `reparse_quantities`, scrive con un `UPDATE` Core in blocco e toglie le unità orfane rispettando `canonical_id`. Nel frontend una riga in `IngredientRow`. Nessuna migrazione: `recipe_ingredients.note` c'è già.

**Tech Stack:** FastAPI 0.141, SQLAlchemy 2 async (Core per il comando), pytest su Postgres vero; React 19, TypeScript, Tailwind 4 (token in `@theme`), Vitest + Testing Library (jsdom), Playwright.

**Spec:** `docs/superpowers/specs/2026-10-13-pulizia-dosi-design.md` (scritta con questo piano: le decisioni di Mattia del 2026-10-13 al §2, quelle di Claude su delega al §3, il comportamento esatto al §4). Il ragionamento d'archivio è in `docs/prossimi-passi.md`, Parte X, le due voci che cominciano con «**Circa settanta dosi in produzione**» e «**Il rovescio della voce sopra**», e D1 per il parser. La riga di `next-steps.md` che questo piano chiude comincia con «Dosi dell'import con l'aggettivo davanti».

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/pulizia-dosi` (`.worktrees/` è già in `.gitignore`), ramo `night/pulizia-dosi`, creato da **`master`**: questo piano è il dodicesimo della notte ma non dipende dalla catena, e nessuno dei suoi file aspetta il lavoro degli altri. Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì (o dalle sue `backend/` e `frontend/`), mai dalla radice del checkout principale. Il checkout principale non si tocca: se vi trovi modifiche non committate, sono dell'utente. **Nessun push, nessun merge, nessun deploy. Mai `git stash`. Niente letture o scritture sulla produzione**: il comando che pulisce le righe vere si costruisce e si prova qui (sul database dei test e sullo stack e2e), e lo lancia Mattia (sezione «Dopo il deploy (solo Mattia)»).
- **I file che anche altri piani della notte toccano.** `backend/app/domain/quantities.py` e `backend/tests/domain/test_quantities.py` (R2, piano 8: aggiunge funzioni **in fondo** a `quantities.py` e cambia l'import in cima al test; questo piano aggiunge le sue **fra `_parse_one` e `scale_quantity`** e mette i test nuovi in un file nuovo, così i due rami non scrivono nello stesso punto); `backend/app/api/recipes.py` (R2 riscrive il calcolo di `display` in `_to_out`; R8, piano 10, aggiunge `derived_from`); `backend/app/services/recipe_import/materialize.py` (pagine scartate, piano 9: `explain_skip` e `NON_FOOD_PREFIX` nell'`except NonFoodInRecipe`; R8: `VARIANTS_KEY` e `_relink_variants`); `backend/app/services/registry.py` (S12, piano 2: `set_ingredient_emoji`); `frontend/src/features/cooking/RecipeDetailScreen.tsx` e il suo test (R2 riscrive `IngredientRow`; piani 7, 9 e 10 lo toccano); `frontend/e2e/style.spec.ts` (quasi tutti); `next-steps.md`, `docs/prossimi-passi.md`, il report della notte. Sul tuo ramo, che parte da `master`, sono come su `master`. Il piano descrive comunque ogni modifica a un file esistente contro un'ancora riconoscibile — una funzione, una riga di codice esatta, un elemento JSX — e mai contro numeri di riga: **leggi il file com'è sul ramo prima di cambiarlo**. Dove il piano dà un file intero è un file nuovo. Le prove nuove di `style.spec.ts` vanno **in fondo al file**; al merge, l'unione con quelle degli altri rami la fa la revisione.
- **Decisione fondante 1, ristretta qui da Mattia il 2026-10-13.** `quantity_text` resta la verità mostrata a 1×, e il verso resta uno solo (il testo alimenta le colonne); **una volta sola**, e solo sulle righe che hanno ancora la forma dell'import (almeno un a capo o una tabulazione), la pulizia lo riscrive: le parole davanti alla dose passano nella nota, gli spazi diventano uno. Una dose senza a capo né tabulazioni non si tocca **mai**, da nessuna strada. La dispensa e la lista non cambiano di una riga.
- **Il frontend non calcola logica di dominio.** La pulizia, la lettura delle frazioni, «+ q.b.» accanto alla dose riscalata stanno nel backend; il frontend mostra `quantity_display` e `note` come arrivano.
- **Mai un vicolo cieco.** Una dose che la pulizia non capisce resta una dose che non si riscala, mai un errore; un'unità che non si può togliere perché un'altra la usa come canonico resta, e il comando lo dice; il comando non si ferma per una riga cancellata nel frattempo da chi usa l'app.
- Tutto il colore passa dai token di `frontend/src/index.css`. **Nessun token nuovo.** Nessuna schermata nomina un colore crudo: `grep -rn "emerald\|neutral-" frontend/src` resta vuoto. Ogni testo sta sopra 4,5:1, in chiaro e in scuro, e lo misura `frontend/e2e/style.spec.ts`. Niente classi in conflitto sullo stesso elemento (due `text-*` di colore o due `px-*`). A 375 px nessuna schermata scorre di lato. `Button` non cambia, e questo piano non aggiunge pulsanti.
- Le parole a video e le righe stampate dal comando sono in italiano e **si copiano esattamente come sono scritte qui**; gli identificatori in inglese; i commenti in italiano come nel resto del codice.
- **Il type check è `npm run typecheck`** (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0 (settima lezione di `CLAUDE.md`).
- Controlli del frontend, da `<worktree>/frontend`: `npx vitest run` (non esiste `npm test`), `npm run typecheck`, `npm run lint`, `npm run build`.
- **Backend su Postgres vero.** Il database dei test è il container `spena-db-1` (porta 5433), da usare solo come database dei test: se `docker ps --format '{{.Names}}'` non lo mostra, `docker start spena-db-1`. **Mai `docker compose up` dal worktree** (il nome del progetto Compose viene dalla cartella: nascerebbe un secondo Postgres che litiga sulla 5433), mai `-f docker-compose.prod.yml`. Questo ramo parte da `master` e **non aggiunge migrazioni**: usa `spena_test`, il database dei rami che partono da `master`. Nel worktree non c'è un `.venv`: si usa quello del checkout principale; `python -m` mette la cartella corrente in testa a `sys.path`, quindi si prova l'`app` del worktree. Il comando, sempre da `<worktree>/backend` (dove un task dice «il comando di pytest» intende questo, con i percorsi che il task indica in coda):
  ```bash
  PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
  Se la Preparazione trova `spena_test` già portato oltre la `0012` da un altro ramo, ogni pytest di questo piano prende davanti `TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_pulizia` (vedi la Preparazione). Se un test sembra ignorare una modifica, `python -c 'import app; print(app.__file__)'` da `<worktree>/backend` (con lo stesso `PATH`) deve stampare un percorso dentro il worktree. Nessuna chiamata di rete nella suite.
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
- **Niente produzione, di notte.** Il comando `clean_doses` si prova sul database dei test (Task 5) e nel container del backend dello stack e2e (Task 7); in produzione lo lancia Mattia, dopo il deploy.
- Nessuna dipendenza nuova, nessuna migrazione, nessun cambio di configurazione globale.

### Preparazione (una volta, prima del Task 1)

- [ ] Il ramo di partenza è `master`, e i file di questo piano sono quelli su cui è scritto (`master` era `b9be6bf` quando il piano è stato scritto):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify master
  git diff --stat b9be6bf master -- \
    backend/app/domain/quantities.py backend/tests/domain/test_quantities.py \
    backend/app/api/recipes.py backend/app/services/recipe_import/materialize.py \
    backend/app/services/registry.py backend/app/db/models/recipe.py \
    backend/app/cli/reparse_quantities.py backend/app/repositories/units.py \
    frontend/src/features/cooking/RecipeDetailScreen.tsx \
    frontend/src/features/cooking/RecipeDetailScreen.test.tsx \
    frontend/e2e/style.spec.ts CLAUDE.md
  ls backend/app/cli/clean_doses.py backend/tests/test_clean_doses_cli.py \
    backend/tests/domain/test_quantities_pulizia.py backend/tests/api/test_recipes_dosi_pulite.py \
    backend/tests/services/test_materialize_dosi.py backend/tests/services/test_registry_merge_notes.py \
    frontend/e2e/dosi-pulite.spec.ts 2>&1 | grep -c "No such file"
  ```
  Expected: un hash; il `diff --stat` **vuoto**; `7` (i sette file nuovi non esistono ancora). Se il `diff` non è vuoto, `master` è andato avanti su questi file (per esempio Mattia ha unito R2): applica le modifiche del piano sopra la versione di `master`, ancora per ancora, e scrivilo nel report — in particolare, se `_to_out` in `api/recipes.py` ha più di un punto che chiama `render_quantity` su una riga (R2 ne aggiunge uno per la riga d'ancora), **ognuno** passa da `with_qb_tail` (Task 3). Se uno dei sette file nuovi esiste già, **fermati**: qualcuno ha già cominciato questa voce; scrivi nel report della notte (`docs/night-reports/<data>.md`, sul ramo `night/pulizia-dosi` appena creato) cosa hai trovato, segna la voce `bloccato` in `next-steps.md` di quel ramo con la domanda per Mattia, e non partire.
- [ ] Il database dei test:
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d spena_test -tAc 'SELECT version_num FROM alembic_version'
  ```
  Expected: `0012`. Se stampa altro (per esempio `0013`, lasciata da un ramo della catena che ha usato il database sbagliato), **non toccare `spena_test`**: crea il database di questo ramo e usalo per tutta la notte, mettendo `TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_pulizia` davanti a ogni comando di pytest di questo piano, e scrivilo nel report:
  ```bash
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_pulizia WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_pulizia'
  ```
  (in quel caso, alla fine del Task 9, `DROP DATABASE IF EXISTS spena_test_pulizia WITH (FORCE)`).
- [ ] Dal checkout principale, allinea `node_modules` al lockfile (non aggiunge dipendenze, installa quelle di `package-lock.json`):
  ```bash
  cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund
  ```
- [ ] Crea il worktree da `master` e collega `node_modules` (e solo quello: **niente `.env`**):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/pulizia-dosi -b night/pulizia-dosi master
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/pulizia-dosi/frontend/node_modules
  ```
- [ ] La voce in `next-steps.md` del ramo passa a `in corso` (cercala per testo, `grep -n "Dosi dell'import con l'aggettivo davanti" next-steps.md`: di giorno può essere stata spostata in «Pronti per la notte»; cambia solo lo stato fra parentesi quadre) e si committa:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/pulizia-dosi
  git add next-steps.md
  git commit -m "next-steps: pulizia delle dosi dell'import, in corso"
  ```
- [ ] La linea di partenza, dal worktree:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/pulizia-dosi/frontend && npx vitest run 2>&1 | grep -E "Test Files|Tests "
  cd ../backend && PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q 2>&1 | tail -n 1
  ```
  Expected: tutto verde. **Annota i numeri** (file e test di vitest, test di pytest): sono `N_file`, `N_vitest`, `N_pytest` del Task 9. Se una delle due linee non è verde, fermati: non è un difetto di questo piano, e va scritto nel report.

---

## Obiettivo e contesto

GialloZafferano scrive la dose dentro uno `<span>` pieno di a capo e tabulazioni, e l'import la conserva così: `"fredda\n\t\t\t330\n\t\t\tg"`. `parse_quantity` vuole il numero in testa, quindi le parole davanti fanno perdere la dose, e un numero nel nome («36 mesi ⏎ 50 ⏎ g») diventa la dose: 36 `mesi`, e al doppio delle porzioni «72 mesi». Quelle parole sono finite nel registro `units` come unità. Il parser non legge «½» né «10 g + q.b.».

**Misure sulla produzione del 2026-10-13** (sola lettura, fatte di giorno da Claude col via di Mattia; **la notte non le ripete**): 8.454 ricette, 83.343 righe; `quantity_value` vuoto su 32.067, di cui ~16.000 `q.b.`. Con a capo o tabulazioni: 61.137 righe (la più comune `"100\n\t\t\tg"`, 2.947). «Parole ⏎ numero ⏎ unità»: 9.767, tutte senza valore («da grattugiare» 510, «a temperatura ambiente» 461, «(da pulire)» 447, «(da grattugiare)» 392, «medie» 360, «freddo» 230…). «Numero nel nome ⏎ dose»: 202. Frazioni ½ ¼ ¾: ~1.042 senza valore. «+ q.b.»: ~3.547. «Parole ⏎⏎ q.b.»: qualche centinaio. `units`: 101 righe, 5 non usate; spurie fra le usate `mesi` 56, `da` 4, `per` 2, `intere` 2, `già`, `di`, `w`, `grande`, `lunghi`, `sodi`… `recipe_ingredients.note` è vuota su tutte le righe, e nessuna schermata la mostra.

## Decisioni prese

Di Mattia, il 2026-10-13:

1. **Le parole davanti alla dose vanno nella nota della riga** (`note`); `quantity_text` diventa la dose pulita («50 g») e si riscala. Lo stesso per «parole ⏎⏎ q.b.» (nota + «q.b.») e per il numero nel nome («36 mesi ⏎ 50 g» → nota «36 mesi», dose «50 g»).
2. **Entrano nella pulizia anche** le frazioni ½ ¼ ¾, che il parser legge («½ cucchiaino» = 0,5 cucchiaini; «1 + ½» = 1,5); «50 g + q.b.», dove i 50 g si riscalano e «+ q.b.» resta scritto accanto; le unità spurie, tolte dal registro `units` dopo la rilettura se nessuna riga le usa più (attenzione a `canonical_id` e alla FK `RESTRICT`).
3. **La pulizia tocca anche le ricette adottate** (R10), ma solo nelle righe che hanno ancora la forma dell'import: una riga scritta a mano senza quella forma non cambia.
4. **Gli spazi bianchi dell'import** (a capo, tabulazioni) diventano uno spazio nel testo pulito.

Di Claude, su delega di Mattia (tecniche o estetiche; il perché è nella spec, §3):

5. **La forma dell'import** è un testo con almeno un a capo (`\n`, `\r`) o una tabulazione. Una dose senza non si tocca mai.
6. **Nota e dose:** il testo si divide in righe sugli a capo (vuote escluse, spazi interni ridotti a uno); la dose comincia dall'**ultima** riga che comincia con una cifra, con ½ ¼ ¾ o con «q.b.»; quel che sta prima è la nota, se ha almeno una lettera (altrimenti è tutto dose). Una nota chiusa per intero fra parentesi le perde. Le dosi unite con « + » si puliscono pezzo per pezzo.
7. **Più note sulla stessa riga** si uniscono con «; », senza ripetersi, nei 300 caratteri della colonna; una nota già scritta resta davanti (`merge_notes`).
8. **«½ + ½» vale 1**; **«1 ½» e «1½» valgono 1,5**; «2 1/2» con la barra resta non letto, come oggi.
9. **«50 g + q.b.» riscalato si legge «100 g + q.b.»** (`with_qb_tail`): il numero si riscala, i pezzi «q.b.» del testo tornano accanto com'erano. Solo «q.b.» resta non letto.
10. **L'import pulisce in `materialize_ready`**, dove il `payload` diventa ricetta: il `payload` resta la copia di quel che è arrivato, e ogni ricetta rifatta da lì nasce pulita. **Il ruolo** si deduce dal testo come è arrivato, come prima: la pulizia non cambia ruoli. La fusione dell'anagrafica unisce anche le note delle due righe gemelle.
11. **Il comando `python -m app.cli.clean_doses`** legge tutte le righe (archiviate comprese), pulisce quelle nella forma dell'import, rilegge **tutte** le dosi con `parse_quantity` + `ensure_unit` (la lettura di `reparse_quantities`, in una passata sola e a tuple), scrive con un `UPDATE` Core in blocco, e toglie le unità orfane. `--dry-run` fa lo stesso lavoro e annulla la transazione alla fine. Rilanciato, non cambia niente.
12. **Le unità che si tolgono** sono quelle che avevano righe prima e non ne hanno dopo; una resta se è il canonico di un'unità che resta; fra quelle che se ne vanno, `canonical_id` si azzera prima della `DELETE`. Le unità **già senza righe prima** non si toccano: il comando le elenca, e Mattia decide al dry-run in produzione se toglierle (deciso da Mattia il 2026-10-13, sotto).
13. **La nota nel dettaglio:** sotto il nome dell'ingrediente, `text-xs text-ink-soft`, così com'è scritta.

Scelte interne di questo piano (Claude, su delega; reversibili):

14. **I test nuovi del backend in file nuovi** (`test_quantities_pulizia.py`, `test_recipes_dosi_pulite.py`, `test_materialize_dosi.py`, `test_registry_merge_notes.py`, `test_clean_doses_cli.py`): `test_quantities.py` si cambia solo dentro la tabella di `test_parse_quantity`, perché R2 cambia l'import in cima, e `test_materialize.py` lo cambiano i piani 9 e 10.
15. **`NOTE_MAX_CHARS = 300` nel dominio**, tenuto uguale alla colonna da un test (la colonna c'era prima, e il modello non la importa da qui).
16. **Il comando scrive con Core e non con l'ORM**: un `update(RecipeIngredient)` con una lista diventerebbe l'«ORM bulk update», che controlla quante righe ha toccato, e una riga cancellata nel frattempo da chi usa l'app farebbe fallire tutto.

**Le unità già senza righe prima della pulizia** (5 in produzione) — deciso da Mattia il 2026-10-13: il comando le elenca nella riga «Unità già senza righe prima, lasciate: …» e non le toglie; quali siano lo dice il dry-run in produzione, e lì Mattia decide se toglierle.

**La nota nel modulo di modifica** — deciso da Mattia il 2026-10-13: diventa un campo modificabile, in una voce a sé, il piano 20 (`modulo-nota-nome`). Oggi il modulo la porta con sé senza mostrarla (`formModel.ts`, `FormLine.note`), e dopo la pulizia saranno ~10.000 note. Questo piano **non cambia il modulo** e non aggiunge voci al backlog per questo: la voce del piano 20 c'è già.

## Criteri di accettazione

- [ ] `parse_quantity`: «½» → 0,5; «½ cucchiaino» → 0,5 `cucchiaino`; «1 ½ cucchiai», «1½», «1 + ½» → 1,5; «½ + ½» → 1; «300 g + q.b.» → 300 `g`; «q.b. + q.b.» e «abbondante + q.b.» → non letti; tutti i casi di oggi invariati tranne «300 g + q.b.».
- [ ] `clean_dose` sulla tabella della spec §4.1: «36 mesi ⏎ 50 ⏎ g» → «50 g» con nota «36 mesi»; «secco ⏎⏎ q.b.» → «q.b.» con nota «secco»; «freddo 50 g» invariato; una dose pulita non si pulisce di nuovo.
- [ ] `GET /api/v1/recipes/{id}?servings=4` su una ricetta per 2: «50 g + q.b.» → «100 g + q.b.», «½ cucchiaino» → «1 cucchiaino», «1 + ½» → «3»; la nota arriva in `note`.
- [ ] Una pagina dell'import con «setacciata ⏎ 500 ⏎ g» diventa una riga «500 g», nota «setacciata», 500 letti; due righe sullo stesso ingrediente uniscono dosi e note; il ruolo è quello di prima; il `payload` resta com'era. La fusione dell'anagrafica unisce le note.
- [ ] `clean_doses` sul mondo di prova: le righe dell'import pulite e rilette; nella ricetta adottata (e archiviata) cambia solo la riga con la forma dell'import, e la nota scritta resta davanti; i conti per forma; `mesi` tolta, `intera` tenuta come canonica di `intere`, `cchiaio` lasciata; due orfane che si puntano se ne vanno insieme; rilanciato non cambia niente; dopo di lui `reparse` non trova niente da cambiare.
- [ ] Nel dettaglio, la nota sotto il nome; nel browser vero, `clean_doses --dry-run` non salva e la scrittura sì, la dose pulita si riscala con «+ q.b.» accanto, la nota si legge nei due temi.
- [ ] Tutti i test di oggi passano; l'unico cambiato è il caso «300 g + q.b.» di `test_parse_quantity` (decisione 2 di Mattia), mai indebolito altro.
- [ ] `docs/prossimi-passi.md`, `CLAUDE.md`, la docstring di `RecipeIngredient` e `next-steps.md` aggiornati (Task 8).

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
```

Dalla radice di `<worktree>`:

```bash
grep -rn "emerald\|neutral-" frontend/src
git diff master --stat -- backend/alembic
```

Expected: i due comandi non stampano niente. E l'e2e intera con i comandi delle Global Constraints.

## Review Focus

I casi che la spec implica e che un test deve tenere fermi, i più probabili per primi; ognuno è fissato da un test nel task che possiede il codice:

1. **Una dose scritta a mano con l'aggettivo davanti** («freddo 50 g», senza a capo) deve restare com'è anche dentro una ricetta adottata che il comando attraversa — Task 2 (tabella) e Task 5 (`test_nella_ricetta_adottata_cambia_solo_la_riga_con_la_forma_dell_import`).
2. **Una ricetta archiviata** si può ripristinare: le sue righe si puliscono come le altre — Task 5 (la ricetta adottata del mondo di prova è archiviata).
3. **Un'unità orfana che è il canonico di una che resta**, e **due orfane che si puntano**: la FK `RESTRICT` non deve far fallire la transazione — Task 5 (`intera`, e `test_due_unita_orfane_che_si_puntano_se_ne_vanno_insieme`).
4. **La prova non salva niente**: `--dry-run` annulla tutto, unità depositate comprese — Task 7 (il comando vero nel container, prima `--dry-run` e il dettaglio invariato, poi la scrittura).
5. **«q.b.» prima della dose** («q.b. per spolverare + 50 g»): la dose si legge e il «q.b.» torna accanto alla dose riscalata, con le sue parole — Task 1 (`test_parse_quantity` e `test_with_qb_tail`).

## Fuori scope

- Mostrare o modificare la nota nel modulo: un campo modificabile, voce a sé (piano 20, `modulo-nota-nome`; deciso da Mattia il 2026-10-13).
- Le dosi scritte a mano senza la forma dell'import; il `payload` delle pagine dell'import; gli `snapshot` delle cotture passate.
- Le frazioni oltre ½ ¼ ¾ (⅓, ⅛…), «2 1/2» con la barra.
- Le forme (singolare e plurale) delle unità nuove: le decide `decide_units`, come sempre, e in produzione lo lancia Mattia.
- Il ruolo delle righe (decisione 10). La fusione dell'anagrafica che azzera il valore della riga gemella («500 g + 50 g» non si riscala più): è di prima, e resta.
- Tutto quel che fanno gli altri piani della notte.

## Margine di autonomia

- **Liberi:** i nomi di variabili locali, helper di test e funzioni private non fissati qui; l'ordine dei test dentro un file; l'ordine delle classi Tailwind; la formulazione dei commenti, purché dicano il perché.
- **Fissi:** le righe stampate dal comando, esattamente come sono scritte nel piano; i nomi pubblici che altri task usano (`VULGAR_FRACTIONS`, `NOTE_MAX_CHARS`, `DoseShape` e i suoi cinque valori, `CleanDose`, `clean_dose`, `merge_notes`, `with_qb_tail`, `clean_doses`, `Cleaned`, `Sample`, `report`, `main`, `SHAPE_LABELS`); il nome del comando e il flag `--dry-run`.
- **Nessuna dipendenza nuova**, nessuna migrazione, nessun token di colore nuovo.
- **Un test di oggi si cambia solo dove il piano lo dice** (il caso «300 g + q.b.»). Se un altro test di oggi cade, è un comportamento che il piano non ha previsto: scrivilo nel report con il perché, e non indebolirlo.
- **Una decisione di comportamento non coperta e non reversibile** → si ferma quel task, si fa commit del lavoro parziale sul ramo, lo si segna `bloccato` in `next-steps.md` del ramo con la domanda precisa per Mattia, e si passa al task successivo. Una scelta reversibile e a basso impatto → la più conservativa, annotata nel report della notte.
- Se un test fallisce e non si risolve in modo ragionevole: niente test disattivati, niente asserzioni indebolite; `bloccato` con la diagnosi.

## Dipendenze

**Parte da `master`.** Non consuma niente dagli altri piani della notte. Al merge incontra, sugli stessi file: **R2** (piano 8) in `quantities.py` (funzioni in fondo al file; qui fra `_parse_one` e `scale_quantity`), nell'import di `test_quantities.py`, in `_to_out` di `api/recipes.py` — dove **la riga d'ancora di R2 va passata anch'essa da `with_qb_tail`**, altrimenti una dose «50 g + q.b.» fissata come ancora si mostrerebbe «150 g» senza «+ q.b.» — e in `IngredientRow` di `RecipeDetailScreen.tsx` (R2 trasforma la dose in un pulsante; la nota di questo piano sta nel `<span>` del nome, che R2 non tocca); inoltre con R2 «½ cucchiaino» e «50 g + q.b.» diventano righe da cui si può riscalare. **Piani 9 e 10** in `materialize.py` (punti diversi di `materialize_ready`), **R8** anche in `_to_out`; **S12** in `registry.py` (una funzione nuova, lontana da `merge_ingredients`); tutti in `style.spec.ts`. Modifiche in punti diversi degli stessi file, che la revisione unisce.

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `backend/app/domain/quantities.py` | 1, 2 | `VULGAR_FRACTIONS`, `_DOSE` con le frazioni, `_QB`; `parse_quantity` salta i pezzi «q.b.»; `with_qb_tail`; `NOTE_MAX_CHARS`, `DoseShape`, `CleanDose`, `clean_dose`, `merge_notes` |
| `backend/tests/domain/test_quantities.py` | 1 | la tabella di `test_parse_quantity`: 1 caso cambiato, 14 nuovi |
| `backend/tests/domain/test_quantities_pulizia.py` (nuovo) | 1, 2 | 5 + 30 test |
| `backend/app/api/recipes.py`, `backend/tests/api/test_recipes_dosi_pulite.py` (nuovo) | 3 | `with_qb_tail` in `_to_out`; 3 test |
| `backend/app/services/recipe_import/materialize.py`, `backend/tests/services/test_materialize_dosi.py` (nuovo) | 4 | la pulizia nel collasso; 4 test |
| `backend/app/services/registry.py`, `backend/tests/services/test_registry_merge_notes.py` (nuovo) | 4 | le note nella fusione; 1 test |
| `backend/app/cli/clean_doses.py`, `backend/tests/test_clean_doses_cli.py` (nuovi) | 5 | il comando; 9 test |
| `frontend/src/features/cooking/RecipeDetailScreen.tsx`, `.test.tsx` | 6 | la nota in `IngredientRow`; 1 test |
| `frontend/e2e/dosi-pulite.spec.ts` (nuovo), `frontend/e2e/style.spec.ts` | 7 | 1 prova; 1 prova in fondo |
| `CLAUDE.md`, `backend/app/db/models/recipe.py` (docstring), `docs/prossimi-passi.md`, `next-steps.md` | 8 | i documenti |

---

### Task 1: Il parser legge le frazioni e «+ q.b.»

**Files:**
- Modify: `backend/app/domain/quantities.py` (`_DOSE`, `parse_quantity`, `_parse_one`, una funzione nuova `with_qb_tail` subito dopo `_parse_one`)
- Modify: `backend/tests/domain/test_quantities.py` (solo la tabella di `test_parse_quantity`)
- Create: `backend/tests/domain/test_quantities_pulizia.py`

**Interfaces:**
- Consumes: niente di nuovo.
- Produces, in `app.domain.quantities`: `VULGAR_FRACTIONS: dict[str, Decimal]` (`"½"`, `"¼"`, `"¾"`); `_FRACTION_CHARS: str`; `_QB: re.Pattern` (un pezzo che comincia con «q.b.», «qb», «Q. B.»…); `with_qb_tail(display: str, text: str | None) -> str`. `parse_quantity` ha la stessa firma.

- [ ] **Step 1: I test che falliscono**

In `backend/tests/domain/test_quantities.py`, dentro la tabella di `test_parse_quantity`, sostituisci la riga

```python
        ("300 g + q.b.", (None, None)),
```

con

```python
        # «q.b.» accanto a una dose non la rende illeggibile: i 300 g si riscalano, e il
        # «+ q.b.» lo rimette accanto `with_qb_tail` (Mattia, 2026-10-13)
        ("300 g + q.b.", (Decimal("300"), "g")),
        ("10 g + q.b.", (Decimal("10"), "g")),
        ("1 pizzico + q.b.", (Decimal("1"), "pizzico")),
        ("q.b. per spolverare + 50 g", (Decimal("50"), "g")),
        # solo «q.b.», o «q.b.» con quel che non si legge: niente da riscalare
        ("q.b. + q.b.", (None, None)),
        ("abbondante + q.b.", (None, None)),
```

e, subito dopo la riga `("2  1/2 tazze", (None, None)),` (l'ultima della tabella), aggiungi:

```python
        # le frazioni di un carattere solo, come le scrive GialloZafferano
        ("½", (Decimal("0.5"), None)),
        ("½ cucchiaino", (Decimal("0.5"), "cucchiaino")),
        ("¼ cucchiaino", (Decimal("0.25"), "cucchiaino")),
        ("¾ tazza", (Decimal("0.75"), "tazza")),
        # col numero intero davanti è una dose sola, e «½» non è mai un'unità
        ("1 ½ cucchiai", (Decimal("1.5"), "cucchiai")),
        ("1½", (Decimal("1.5"), None)),
        ("1 ½", (Decimal("1.5"), None)),
        # le somme di merge_quantities con le frazioni: «½ + ½» sono due metà dello
        # stesso limone, cioè uno
        ("1 + ½", (Decimal("1.5"), None)),
        ("½ + ½", (Decimal("1"), None)),
```

Crea `backend/tests/domain/test_quantities_pulizia.py`:

```python
"""La pulizia delle dosi dell'import, nel dominio (spec 2026-10-13-pulizia-dosi-design.md).

In un file suo e non in `test_quantities.py`: l'import in cima a quello lo cambia R2, e due
rami che scrivono nello stesso punto si scontrano al merge.
"""

import pytest

from app.domain.quantities import with_qb_tail


@pytest.mark.parametrize(
    "display,text,expected",
    [
        ("100 g", "50 g + q.b.", "100 g + q.b."),
        ("2 pizzichi", "1 pizzico + q.b.", "2 pizzichi + q.b."),
        # il «q.b.» torna con le sue parole, in fondo
        ("100 g", "q.b. per spolverare + 50 g", "100 g + q.b. per spolverare"),
        # senza «q.b.» la dose riscalata è quella e basta
        ("100 g", "50 g", "100 g"),
        ("100 g", None, "100 g"),
    ],
)
def test_with_qb_tail(display, text, expected):
    assert with_qb_tail(display, text) == expected
```

- [ ] **Step 2: Falliscono**

Run (da `<worktree>/backend`): `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/domain/test_quantities.py tests/domain/test_quantities_pulizia.py`
Expected: FAIL — `ImportError` su `with_qb_tail` nel file nuovo; in `test_quantities.py` cadono i casi con «q.b.» accanto a una dose e quelli con le frazioni (oggi «1 ½» dà `(1, "½")`: «½» è una lettera per `\w`). «q.b. + q.b.» e «abbondante + q.b.» passano già.

- [ ] **Step 3: Il parser**

In `backend/app/domain/quantities.py`:

1. Sostituisci il commento e la definizione di `_DOSE` (dal commento `# numero in testa (intero, decimale con virgola o punto, frazione), e subito dopo` fino alla `)` che chiude `re.compile`) con:

   ```python
   # Le frazioni scritte con un carattere solo, come le scrive GialloZafferano («½
   # cucchiaino»). Solo le tre misurate in produzione il 2026-10-13: un'altra resta una
   # dose che non si legge, che è il contratto di questo parser.
   VULGAR_FRACTIONS = {"½": Decimal("0.5"), "¼": Decimal("0.25"), "¾": Decimal("0.75")}
   _FRACTION_CHARS = "".join(VULGAR_FRACTIONS)

   # numero in testa (intero, decimale con virgola o punto, frazione con la barra, intero
   # seguito da ½ ¼ ¾, oppure ½ ¼ ¾ da soli), e subito dopo la parola dell'unità se c'è.
   # Tutto quel che segue è prosa e non ci riguarda: «1 litro di brodo» è un litro, e «di
   # brodo» sta già in quantity_text. ½ ¼ ¾ sono «lettere» per `\w`: senza escluderle
   # dall'unità, «1 ½» sarebbe un ½ come unità.
   _DOSE = re.compile(
       rf"^\s*(?:(?P<num>\d+)\s*/\s*(?P<den>\d+)"
       rf"|(?P<dec>\d+(?:[.,]\d+)?)(?:\s*(?P<mixed>[{_FRACTION_CHARS}]))?"
       rf"|(?P<vulgar>[{_FRACTION_CHARS}]))"
       rf"\s*(?P<unit>[^\W\d_{_FRACTION_CHARS}]+)?",
       re.UNICODE,
   )

   # Un pezzo «quanto basta»: «q.b.», «qb», «Q. B.», anche seguito da parole («q.b. per
   # spolverare»). Non si somma e non si scala: accanto a una dose, la dose resta leggibile.
   _QB = re.compile(r"^\s*q\s*\.?\s*b\b\.?", re.IGNORECASE)
   ```

2. In `parse_quantity`, sostituisci

   ```python
       # `merge_quantities` unisce con « + » due dosi della stessa fonte finite sullo
       # stesso ingrediente («500 g + 50 g»). Sommare è giusto solo a unità uguale.
       pieces = [_parse_one(piece) for piece in text.split("+")]
   ```

   con

   ```python
       # `merge_quantities` unisce con « + » due dosi della stessa fonte finite sullo
       # stesso ingrediente («500 g + 50 g»). Sommare è giusto solo a unità uguale.
       # Un pezzo «q.b.» non è una dose da sommare: «50 g + q.b.» sono 50 g che si
       # riscalano, e il «+ q.b.» lo rimette accanto `with_qb_tail` (Mattia, 2026-10-13).
       measured = [piece for piece in text.split("+") if not _QB.match(piece)]
       if not measured:
           return (None, None)
       pieces = [_parse_one(piece) for piece in measured]
   ```

   e nella docstring di `parse_quantity`, dopo il paragrafo che finisce con «è una dose che non si scala.», aggiungi:

   ```
       Un pezzo «q.b.» accanto a una dose non conta: «50 g + q.b.» sono 50 g. Le
       frazioni ½ ¼ ¾ si leggono, da sole («½ cucchiaino») e dopo un intero («1 ½»).
   ```

3. In `_parse_one`, sostituisci

   ```python
           if found["den"] is not None:
               value = (Decimal(found["num"]) / Decimal(found["den"])).quantize(PRECISION)
           else:
               value = Decimal(found["dec"].replace(",", "."))
   ```

   con

   ```python
           if found["den"] is not None:
               value = (Decimal(found["num"]) / Decimal(found["den"])).quantize(PRECISION)
           elif found["vulgar"] is not None:
               value = VULGAR_FRACTIONS[found["vulgar"]]
           else:
               value = Decimal(found["dec"].replace(",", "."))
               if found["mixed"] is not None:
                   value += VULGAR_FRACTIONS[found["mixed"]]
   ```

4. Subito dopo la fine di `_parse_one` (prima di `def scale_quantity`), aggiungi:

   ```python
   def with_qb_tail(display: str, text: str | None) -> str:
       """La dose riscalata, con accanto i pezzi «q.b.» che la riga scriveva.

       `parse_quantity` legge «50 g + q.b.» come 50 g; riscalata, la riga direbbe «100 g»
       e perderebbe il «q.b.». Mattia (2026-10-13): «+ q.b.» resta scritto accanto.
       """
       if not text:
           return display
       tails = [" ".join(piece.split()) for piece in text.split("+") if _QB.match(piece)]
       return " + ".join([display, *tails])
   ```

- [ ] **Step 4: Passano**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/domain/test_quantities.py tests/domain/test_quantities_pulizia.py tests/test_reparse_quantities_cli.py tests/api/test_recipes_quantities.py tests/api/test_recipes_riporziona.py`
Expected: PASS. Il parser lo usano anche `write_recipe_ingredients` e `reparse`: le loro prove devono restare verdi.

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/quantities.py backend/tests/domain/test_quantities.py backend/tests/domain/test_quantities_pulizia.py
git commit -m "dosi: il parser legge ½ ¼ ¾ e «50 g + q.b.»; with_qb_tail rimette il q.b. accanto alla dose riscalata"
```

---

### Task 2: La pulizia di una dose, pura

**Files:**
- Modify: `backend/app/domain/quantities.py` (dopo `with_qb_tail`, prima di `def scale_quantity`; un import in cima)
- Modify: `backend/tests/domain/test_quantities_pulizia.py`

**Interfaces:**
- Consumes: `_QB`, `_FRACTION_CHARS` (Task 1).
- Produces, in `app.domain.quantities`: `NOTE_MAX_CHARS = 300`; `class DoseShape(StrEnum)` con `UNCHANGED = "unchanged"`, `SPACES = "spaces"`, `WORDS_BEFORE = "words_before"`, `NUMBER_IN_NAME = "number_in_name"`, `NOTE_QB = "note_qb"`; `@dataclass(frozen=True) class CleanDose: quantity_text: str | None; note: str | None; shape: DoseShape`; `clean_dose(text: str | None) -> CleanDose`; `merge_notes(*notes: str | None) -> str | None`.

- [ ] **Step 1: I test che falliscono**

In `backend/tests/domain/test_quantities_pulizia.py`, l'import diventa:

```python
import pytest

from app.db.models.recipe import RecipeIngredient
from app.domain.quantities import (
    NOTE_MAX_CHARS,
    CleanDose,
    DoseShape,
    clean_dose,
    merge_notes,
    with_qb_tail,
)
```

e in fondo al file aggiungi:

```python
@pytest.mark.parametrize(
    "text,quantity,note,shape",
    [
        # senza a capo né tabulazioni non è la forma dell'import: non si tocca
        (None, None, None, DoseShape.UNCHANGED),
        ("300 g", "300 g", None, DoseShape.UNCHANGED),
        ("q.b.", "q.b.", None, DoseShape.UNCHANGED),
        # scritta a mano con l'aggettivo davanti: resta com'è (decisione 3 di Mattia)
        ("freddo 50 g", "freddo 50 g", None, DoseShape.UNCHANGED),
        # solo gli spazi dell'import: la forma più comune in produzione, 2.947 righe
        ("100\n\t\t\tg", "100 g", None, DoseShape.SPACES),
        ("½\n\t\t\tcucchiaino", "½ cucchiaino", None, DoseShape.SPACES),
        ("10\n\t\t\tg + q.b.", "10 g + q.b.", None, DoseShape.SPACES),
        ("1\n\t\t\tconfezione da 250 g", "1 confezione da 250 g", None, DoseShape.SPACES),
        # davanti solo numeri: è tutta dose, nessuna nota inventata
        ("2\n\t\t\t1/2\n\t\t\tcucchiai", "2 1/2 cucchiai", None, DoseShape.SPACES),
        # solo spazi bianchi: nessuna dose
        ("\n\t\t\t", None, None, DoseShape.SPACES),
        # le parole davanti alla dose vanno nella nota (decisione 1 di Mattia)
        ("fredda\n\t\t\t330\n\t\t\tg", "330 g", "fredda", DoseShape.WORDS_BEFORE),
        ("da grattugiare\n\t\t\t50\n\t\t\tg", "50 g", "da grattugiare", DoseShape.WORDS_BEFORE),
        (
            "a temperatura ambiente\n\t\t\t100\n\t\t\tg",
            "100 g",
            "a temperatura ambiente",
            DoseShape.WORDS_BEFORE,
        ),
        ("medie\n\t\t\t3", "3", "medie", DoseShape.WORDS_BEFORE),
        # le parentesi della fonte se ne vanno, anche con un numero dentro
        ("(da pulire)\n\t\t\t2\n\t\t\tcespi", "2 cespi", "da pulire", DoseShape.WORDS_BEFORE),
        ("(circa 2 medie)\n\t\t\t110\n\t\t\tg", "110 g", "circa 2 medie", DoseShape.WORDS_BEFORE),
        # con «+ q.b.» la nota resta del suo pezzo
        (
            "da grattugiare\n\t\t\t50\n\t\t\tg + q.b.",
            "50 g + q.b.",
            "da grattugiare",
            DoseShape.WORDS_BEFORE,
        ),
        # due pezzi uniti da merge_quantities con la stessa nota: una volta sola
        (
            "freddo\n\t\t\t100\n\t\t\tg + freddo\n\t\t\t50\n\t\t\tg",
            "100 g + 50 g",
            "freddo",
            DoseShape.WORDS_BEFORE,
        ),
        # il numero nel nome non è la dose (Parte X, «36 mesi»)
        ("36 mesi\n\t\t\t50\n\t\t\tg", "50 g", "36 mesi", DoseShape.NUMBER_IN_NAME),
        ("380/420 W\n\t\t\t410\n\t\t\tg", "410 g", "380/420 W", DoseShape.NUMBER_IN_NAME),
        # una nota e «q.b.»
        ("secco\n\n\t\t\tq.b.", "q.b.", "secco", DoseShape.NOTE_QB),
        ("per friggere\n\n\t\t\tq.b.", "q.b.", "per friggere", DoseShape.NOTE_QB),
    ],
)
def test_clean_dose(text, quantity, note, shape):
    assert clean_dose(text) == CleanDose(quantity, note, shape)


def test_una_dose_pulita_non_si_pulisce_di_nuovo():
    """Il comando si rilancia senza danni perché la dose pulita non ha più la forma
    dell'import: nessun a capo, nessuna tabulazione."""
    for text in [
        "36 mesi\n\t\t\t50\n\t\t\tg",
        "secco\n\n\t\t\tq.b.",
        "100\n\t\t\tg",
        "fredda\n\t\t\t330\n\t\t\tg + q.b.",
    ]:
        pulita = clean_dose(text).quantity_text
        assert clean_dose(pulita) == CleanDose(pulita, None, DoseShape.UNCHANGED)


@pytest.mark.parametrize(
    "notes,expected",
    [
        ((None, None), None),
        (("da grattugiare", None), "da grattugiare"),
        (("freddo", "freddo"), "freddo"),
        # la nota già scritta resta davanti
        (("mia", "da grattugiare"), "mia; da grattugiare"),
        (("  ", "a fette"), "a fette"),
    ],
)
def test_merge_notes(notes, expected):
    assert merge_notes(*notes) == expected


def test_merge_notes_sta_nella_colonna():
    assert len(merge_notes("a" * 200, "b" * 200)) == NOTE_MAX_CHARS


def test_note_max_chars_e_la_colonna():
    """La colonna c'era prima della costante, e il modello non la importa da qui: un test
    le tiene uguali, perché una nota più lunga farebbe fallire la scrittura di tutta la
    ricetta, non solo di quella riga."""
    assert RecipeIngredient.__table__.c.note.type.length == NOTE_MAX_CHARS
```

- [ ] **Step 2: Falliscono**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/domain/test_quantities_pulizia.py`
Expected: FAIL con `ImportError` su `NOTE_MAX_CHARS`.

- [ ] **Step 3: Il codice**

In `backend/app/domain/quantities.py`, fra gli import in cima aggiungi `from enum import StrEnum` (dopo `from decimal import …`). Subito dopo `with_qb_tail` (prima di `def scale_quantity`) aggiungi:

```python
# --- La pulizia delle dosi dell'import (spec 2026-10-13-pulizia-dosi-design.md) -------

# La lunghezza di `recipe_ingredients.note`. Il modello non la importa da qui (la colonna
# c'era prima): la tiene allineata `test_note_max_chars_e_la_colonna`.
NOTE_MAX_CHARS = 300

# Una dose «nella forma dell'import»: GialloZafferano la scrive con gli a capo e le
# tabulazioni del suo HTML («fredda\n\t\t\t330\n\t\t\tg»). Il campo del modulo è una riga
# sola, quindi una dose senza è scritta a mano, o è già pulita, e non si tocca: la
# decisione 3 di Mattia (2026-10-13) resa misurabile.
_IMPORT_WHITESPACE = re.compile(r"[\n\r\t]")
_STARTS_A_DOSE = re.compile(rf"^[\d{_FRACTION_CHARS}]")


class DoseShape(StrEnum):
    """Che cosa la pulizia ha trovato in una dose: il comando conta per forma."""

    UNCHANGED = "unchanged"  # non ha la forma dell'import: non si tocca
    SPACES = "spaces"  # solo a capo e tabulazioni
    WORDS_BEFORE = "words_before"  # parole davanti alla dose, ora nella nota
    NUMBER_IN_NAME = "number_in_name"  # «36 mesi ⏎ 50 ⏎ g»: la nota comincia con un numero
    NOTE_QB = "note_qb"  # «secco ⏎⏎ q.b.»: una nota e «q.b.»


@dataclass(frozen=True)
class CleanDose:
    quantity_text: str | None
    note: str | None
    shape: DoseShape


def clean_dose(text: str | None) -> CleanDose:
    """La dose dell'import ripulita: le parole davanti nella nota, gli spazi a uno.

    Non legge numeri e non sa di unità: separa e basta. Leggere resta di
    `parse_quantity`, che sulla dose pulita trova il numero in testa.
    """
    if text is None or not _IMPORT_WHITESPACE.search(text):
        return CleanDose(text, None, DoseShape.UNCHANGED)
    doses: list[str] = []
    notes: list[str] = []
    # le dosi unite da `merge_quantities` si puliscono pezzo per pezzo
    for piece in text.split("+"):
        dose, note = _split_note(piece)
        if dose:
            doses.append(dose)
        if note:
            notes.append(note)
    quantity = " + ".join(doses) or None
    return CleanDose(quantity, merge_notes(*notes), _shape(quantity, notes))


def _split_note(piece: str) -> tuple[str, str | None]:
    lines = [" ".join(line.split()) for line in piece.splitlines()]
    lines = [line for line in lines if line]
    starts = [
        index
        for index, line in enumerate(lines)
        if _STARTS_A_DOSE.match(line) or _QB.match(line)
    ]
    if not starts:
        return (" ".join(lines), None)
    # l'ultima riga che comincia come una dose: in «36 mesi ⏎ 50 ⏎ g» anche la prima
    # comincia con un numero, ma è il nome
    first = starts[-1]
    before = " ".join(lines[:first])
    if not any(char.isalpha() for char in before):
        # «2 ⏎ 1/2 ⏎ cucchiai»: davanti solo numeri, è tutta dose. Una nota fatta di
        # numeri sarebbe un'invenzione, e il parser dirà da sé che non la legge
        return (" ".join(lines), None)
    return (" ".join(lines[first:]), _unwrap(before))


def _unwrap(note: str) -> str:
    """«(da pulire)» → «da pulire»: in una nota le parentesi della fonte non servono."""
    if note.startswith("(") and note.endswith(")") and note.count("(") == note.count(")") == 1:
        return note[1:-1].strip()
    return note


def _shape(quantity: str | None, notes: list[str]) -> DoseShape:
    if not notes:
        return DoseShape.SPACES
    if any(note[:1].isdigit() for note in notes):
        return DoseShape.NUMBER_IN_NAME
    if quantity is not None and all(_QB.match(piece) for piece in quantity.split("+")):
        return DoseShape.NOTE_QB
    return DoseShape.WORDS_BEFORE


def merge_notes(*notes: str | None) -> str | None:
    """Più note sulla stessa riga diventano una: nell'ordine, senza ripetersi, con «; »
    fra l'una e l'altra, dentro i caratteri della colonna. La prima resta davanti: chi
    chiama ci mette la nota già scritta."""
    kept: list[str] = []
    for note in notes:
        cleaned = note.strip() if note else ""
        if cleaned and cleaned not in kept:
            kept.append(cleaned)
    return "; ".join(kept)[:NOTE_MAX_CHARS] or None
```

- [ ] **Step 4: Passano**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/domain/`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/quantities.py backend/tests/domain/test_quantities_pulizia.py
git commit -m "dosi: clean_dose separa la nota dalla dose dell'import, merge_notes unisce le note"
```

---

### Task 3: Il dettaglio riscalato tiene «+ q.b.» accanto

**Files:**
- Modify: `backend/app/api/recipes.py` (l'import da `app.domain.quantities`, `_to_out`)
- Create: `backend/tests/api/test_recipes_dosi_pulite.py`

**Interfaces:**
- Consumes: `with_qb_tail` (Task 1); il parser del Task 1.
- Produces: `quantity_display` di una riga riscalata con «+ q.b.» accanto. Nessun campo nuovo nella risposta.

- [ ] **Step 1: I test**

Crea `backend/tests/api/test_recipes_dosi_pulite.py`:

```python
"""Le dosi pulite viste dal dettaglio: «+ q.b.» resta accanto alla dose riscalata, le
frazioni si riscalano, la nota arriva com'è (spec 2026-10-13-pulizia-dosi-design.md)."""

import pytest_asyncio

from app.db.models.ingredient import IngredientCategory
from app.repositories.ingredients import create_ingredient
from app.repositories.recipes import create_recipe


@pytest_asyncio.fixture
async def ricetta(db_session):
    righe = []
    for nome, dose, nota in [
        ("parmigiano", "50 g + q.b.", "da grattugiare"),
        ("zucchero", "½ cucchiaino", None),
        ("limone", "1 + ½", None),
        ("sale", "q.b.", None),
    ]:
        ingrediente = await create_ingredient(
            db_session, name=nome, display_name=nome.capitalize(),
            category=IngredientCategory.CEREALI,
        )
        righe.append((ingrediente.id, "primary", dose, nota))
    recipe = await create_recipe(
        db_session,
        title="Prova", description=None, instructions="i", servings=2,
        source="manual", source_ref=None, ingredients=righe, embedding=None,
    )
    await db_session.flush()
    return recipe.id


def _per_nome(corpo: dict) -> dict:
    return {line["ingredient_name"]: line for line in corpo["ingredients"]}


async def test_a_1x_si_mostra_il_testo_e_la_nota(logged_client, ricetta):
    righe = _per_nome((await logged_client.get(f"/api/v1/recipes/{ricetta}")).json())
    assert righe["parmigiano"]["quantity_display"] == "50 g + q.b."
    assert righe["parmigiano"]["note"] == "da grattugiare"
    assert righe["zucchero"]["note"] is None


async def test_il_q_b_resta_accanto_alla_dose_riscalata(logged_client, ricetta):
    corpo = (await logged_client.get(f"/api/v1/recipes/{ricetta}?servings=4")).json()
    righe = _per_nome(corpo)
    assert righe["parmigiano"]["quantity_display"] == "100 g + q.b."
    assert righe["parmigiano"]["quantity_scaled"] is True
    # il solo «q.b.» resta com'è e si conta fra le dosi che non si riscalano
    assert righe["sale"]["quantity_display"] == "q.b."
    assert corpo["unscalable_lines"] == 1


async def test_le_frazioni_si_riscalano(logged_client, ricetta):
    righe = _per_nome((await logged_client.get(f"/api/v1/recipes/{ricetta}?servings=4")).json())
    # «cucchiaino» non è decisa (qui non gira nessun AI): si mostra la parola com'è
    assert righe["zucchero"]["quantity_display"] == "1 cucchiaino"
    assert righe["limone"]["quantity_display"] == "3"
```

- [ ] **Step 2: Il secondo fallisce**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/api/test_recipes_dosi_pulite.py`
Expected: `test_il_q_b_resta_accanto_alla_dose_riscalata` FAIL (`'100 g' != '100 g + q.b.'`); gli altri due passano già (il parser è del Task 1).

- [ ] **Step 3: Il codice**

In `backend/app/api/recipes.py`:

1. L'import `from app.domain.quantities import UnitForms, render_quantity, scale_quantity` diventa:
   ```python
   from app.domain.quantities import UnitForms, render_quantity, scale_quantity, with_qb_tail
   ```
2. In `_to_out`, la riga
   ```python
               display = render_quantity(scale_quantity(ri.quantity_value, factor), forms)
   ```
   diventa
   ```python
               # «50 g + q.b.» riscalata è «100 g + q.b.»: il q.b. resta scritto accanto
               display = with_qb_tail(
                   render_quantity(scale_quantity(ri.quantity_value, factor), forms),
                   ri.quantity_text,
               )
   ```
   Se `_to_out` sul ramo ha altri punti che scrivono una dose riscalata con `render_quantity` (non su `master`; vedi la Preparazione), passali tutti da `with_qb_tail` allo stesso modo.

- [ ] **Step 4: Passano**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/api/test_recipes_dosi_pulite.py tests/api/test_recipes_riporziona.py tests/api/test_recipes_quantities.py tests/api/test_recipes.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/recipes.py backend/tests/api/test_recipes_dosi_pulite.py
git commit -m "dosi: riscalata, «50 g + q.b.» si legge «100 g + q.b.»"
```

---

### Task 4: L'import pulisce all'ingresso, e la fusione unisce le note

**Files:**
- Modify: `backend/app/services/recipe_import/materialize.py` (gli import; in `materialize_ready` il collasso per ingrediente e la chiamata a `create_recipe`)
- Modify: `backend/app/services/registry.py` (gli import; in `merge_ingredients` il ramo della riga gemella)
- Create: `backend/tests/services/test_materialize_dosi.py`, `backend/tests/services/test_registry_merge_notes.py`

**Interfaces:**
- Consumes: `clean_dose`, `merge_notes` (Task 2); `parse_quantity` (Task 1), chiamato da `write_recipe_ingredients` come sempre.
- Produces: le ricette materializzate dall'import hanno `quantity_text` pulito e la nota; nessuna firma cambia.

- [ ] **Step 1: I test**

Crea `backend/tests/services/test_materialize_dosi.py`:

```python
"""L'import pulisce la dose dove il `payload` diventa ricetta (spec 2026-10-13, §3.10).

In un file suo: `test_materialize.py` lo cambiano altri piani della notte.
"""

from decimal import Decimal

import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import Recipe
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, RecipeImport, TermDecision
from app.domain.rules import IngredientRole
from app.repositories.imports import store_page
from app.repositories.recipes import get_recipe
from app.services.recipe_import.materialize import materialize_ready


@pytest_asyncio.fixture
async def farina(db_session):
    """La farina con due termini dell'import già decisi, come in `test_materialize.py`."""
    farina = Ingredient(
        name="farina", display_name="Farina", category=IngredientCategory.CEREALI
    )
    db_session.add(farina)
    await db_session.flush()
    db_session.add_all([
        ImportTerm(source=GIALLOZAFFERANO, term_key="farina-00", display_name="Farina 00",
                   occurrences=1, decision=TermDecision.MAPPED, ingredient_id=farina.id,
                   decided_by="human"),
        ImportTerm(source=GIALLOZAFFERANO, term_key="farina-0", display_name="Farina 0",
                   occurrences=1, decision=TermDecision.MAPPED, ingredient_id=farina.id,
                   decided_by="human"),
    ])
    await db_session.flush()
    return farina


async def _pagina(db_session, righe: list[tuple[str, str, str]]) -> None:
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/torta",
        payload={
            "title": "Torta", "description": None, "instructions": "Cuoci.", "servings": 4,
            "ingredients": [
                {"key": key, "name": name, "quantity_text": quantity}
                for key, name, quantity in righe
            ],
        },
    )
    await materialize_ready(db_session)


async def _unica_riga(db_session):
    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    dettaglio = await get_recipe(db_session, ricetta.id)
    assert len(dettaglio.ingredients) == 1
    return dettaglio.ingredients[0]


async def test_l_import_pulisce_la_dose_e_porta_le_parole_nella_nota(db_session, farina):
    await _pagina(db_session, [("farina-00", "Farina 00", "setacciata\n\t\t\t500\n\t\t\tg")])

    riga = await _unica_riga(db_session)
    assert (riga.quantity_text, riga.note) == ("500 g", "setacciata")
    assert riga.quantity_value == Decimal("500")


async def test_nel_collasso_le_dosi_si_uniscono_e_le_note_pure(db_session, farina):
    await _pagina(db_session, [
        ("farina-00", "Farina 00", "setacciata\n\t\t\t500\n\t\t\tg"),
        ("farina-0", "Farina 0", "per spolverare\n\n\t\t\tq.b."),
    ])

    riga = await _unica_riga(db_session)
    assert (riga.quantity_text, riga.note) == ("500 g + q.b.", "setacciata; per spolverare")
    # «+ q.b.» non toglie la dose: i 500 g si riscalano
    assert riga.quantity_value == Decimal("500")


async def test_il_ruolo_si_legge_dal_testo_come_e_arrivato(db_session, farina):
    """La pulizia non cambia ruoli (spec §3.10): «da setacciare ⏎⏎ q.b.» non comincia con
    «q.b.», quindi la farina resta principale come prima, anche se la dose pulita è «q.b.»."""
    await _pagina(db_session, [("farina-00", "Farina 00", "da setacciare\n\n\t\t\tq.b.")])

    riga = await _unica_riga(db_session)
    assert (riga.quantity_text, riga.note) == ("q.b.", "da setacciare")
    assert riga.role == IngredientRole.PRIMARY


async def test_il_payload_resta_come_e_arrivato(db_session, farina):
    """È la copia di quel che la pagina diceva: ogni ricetta rifatta da lì si ripulisce."""
    await _pagina(db_session, [("farina-00", "Farina 00", "setacciata\n\t\t\t500\n\t\t\tg")])

    pagina = (await db_session.execute(select(RecipeImport))).scalars().one()
    assert pagina.payload["ingredients"][0]["quantity_text"] == "setacciata\n\t\t\t500\n\t\t\tg"
```

Crea `backend/tests/services/test_registry_merge_notes.py`:

```python
"""Unendo due ingredienti, le due righe della stessa ricetta diventano una: anche le note.

Prima della pulizia delle dosi la nota era vuota ovunque e perderla non costava niente;
adesso porta «da grattugiare», «36 mesi».
"""

from sqlalchemy import select

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe import RecipeIngredient
from app.repositories.ingredients import create_ingredient
from app.repositories.recipes import create_recipe
from app.services.registry import merge_ingredients


async def test_unendo_due_righe_le_note_si_uniscono(db_session):
    vincitore = await create_ingredient(
        db_session, name="farina", display_name="Farina", category=IngredientCategory.CEREALI
    )
    perdente = await create_ingredient(
        db_session, name="farina 00", display_name="Farina 00",
        category=IngredientCategory.CEREALI,
    )
    ricetta = await create_recipe(
        db_session,
        title="Torta", description=None, instructions="i", servings=4,
        source="manual", source_ref=None,
        ingredients=[
            (vincitore.id, "primary", "500 g", "setacciata"),
            (perdente.id, "secondary", "50 g", "per spolverare"),
        ],
        embedding=None,
    )
    await db_session.flush()

    await merge_ingredients(db_session, perdente.id, vincitore.id)

    righe = (
        await db_session.execute(
            select(RecipeIngredient.quantity_text, RecipeIngredient.note).where(
                RecipeIngredient.recipe_id == ricetta.id
            )
        )
    ).all()
    assert [tuple(riga) for riga in righe] == [("500 g + 50 g", "setacciata; per spolverare")]
```

- [ ] **Step 2: Falliscono**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/services/test_materialize_dosi.py tests/services/test_registry_merge_notes.py`
Expected: FAIL i primi tre di `test_materialize_dosi.py` (il testo arriva com'è, la nota è `None`) e quello della fusione (la nota è solo «setacciata»); `test_il_payload_resta_come_e_arrivato` passa già.

- [ ] **Step 3: Il codice**

In `backend/app/services/recipe_import/materialize.py`:

1. Fra gli import, dopo `from app.db.models.recipe_import import …`, aggiungi:
   ```python
   from app.domain.quantities import clean_dose, merge_notes
   ```
2. In `materialize_ready`, il blocco del collasso (dal commento `# collasso per ingrediente, nell'ordine di prima comparsa` fino a `collapsed[key] = (role, quantity[:MAX_QUANTITY_CHARS] if quantity else None)` compreso) diventa:
   ```python
           # collasso per ingrediente, nell'ordine di prima comparsa
           collapsed: dict[uuid.UUID, tuple[IngredientRole, str | None, str | None]] = {}
           for line, term in zip(lines, decisions, strict=True):
               if term.decision == TermDecision.IGNORED:
                   continue
               arrived = line.get("quantity_text")
               # Il ruolo si legge dal testo come è arrivato, come prima della pulizia: la
               # pulizia non cambia ruoli (spec 2026-10-13, §3.10), così una ricetta rifatta
               # da qui è uguale a quella che il comando `clean_doses` ha ripulito sul posto.
               role = IngredientRole(
                   term.role_override
                   or default_role(categories.get(term.ingredient_id, "altro"), arrived)
               )
               # La dose pulita all'ingresso: le parole davanti nella nota, gli spazi
               # dell'HTML a uno (Mattia, 2026-10-13). Il `payload` resta com'è arrivato.
               cleaned = clean_dose(arrived)
               quantity, note = cleaned.quantity_text, cleaned.note
               key = term.ingredient_id
               if key in collapsed:
                   previous_role, previous_quantity, previous_note = collapsed[key]
                   collapsed[key] = (
                       stronger(previous_role, role),
                       merge_quantities(previous_quantity, quantity),
                       merge_notes(previous_note, note),
                   )
               else:
                   collapsed[key] = (
                       role,
                       quantity[:MAX_QUANTITY_CHARS] if quantity else None,
                       note,
                   )
   ```
3. Nella chiamata a `create_recipe`, l'argomento
   ```python
                   ingredients=[
                       (ingredient_id, role, quantity, None)
                       for ingredient_id, (role, quantity) in collapsed.items()
                   ],
   ```
   diventa
   ```python
                   ingredients=[
                       (ingredient_id, role, quantity, note)
                       for ingredient_id, (role, quantity, note) in collapsed.items()
                   ],
   ```

In `backend/app/services/registry.py`:

1. Dopo `from app.domain.barcodes import has_valid_check_digit` aggiungi:
   ```python
   from app.domain.quantities import merge_notes
   ```
2. In `merge_ingredients`, dopo la riga
   ```python
           twin.quantity_text = merge_quantities(twin.quantity_text, line.quantity_text)
   ```
   aggiungi
   ```python
           # le note delle due righe, come le dosi: da quando l'import le scrive («da
           # grattugiare», «36 mesi») perderne una vuol dire perdere com'è l'ingrediente
           twin.note = merge_notes(twin.note, line.note)
   ```

- [ ] **Step 4: Passano**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/services/`
Expected: PASS, compresi `test_materialize.py`, `test_registry_merge.py` e `test_undo.py` di oggi.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/recipe_import/materialize.py backend/app/services/registry.py backend/tests/services/test_materialize_dosi.py backend/tests/services/test_registry_merge_notes.py
git commit -m "dosi: l'import pulisce la dose quando la pagina diventa ricetta; la fusione unisce le note"
```

---

### Task 5: Il comando `clean_doses`

**Files:**
- Create: `backend/app/cli/clean_doses.py`
- Create: `backend/tests/test_clean_doses_cli.py`

**Interfaces:**
- Consumes: `clean_dose`, `merge_notes`, `DoseShape` (Task 2); `parse_quantity` (Task 1); `ensure_unit` (`app/repositories/units.py`, com'è).
- Produces, in `app.cli.clean_doses`: `SAMPLE_PER_SHAPE = 5`; `SHAPE_LABELS: dict[DoseShape, str]`; `@dataclass(frozen=True) class Sample(shape, before, after, note)`; `@dataclass class Cleaned` (campi sotto) con la proprietà `cleaned: int`; `async def clean_doses(session: AsyncSession) -> Cleaned` (non fa commit); `def report(outcome: Cleaned) -> str`; `async def main(argv: list[str] | None = None) -> int`.

- [ ] **Step 1: I test**

Crea `backend/tests/test_clean_doses_cli.py`:

```python
"""Il comando che pulisce le dosi già scritte, le rilegge e toglie le unità orfane.

Il mondo di prova ricalca le forme misurate in produzione il 2026-10-13. I valori delle
righe sono quelli che il parser di prima aveva lasciato: «½», «1 + ½» e «+ q.b.» non li
leggeva, «36 mesi» sì, e male.

Le righe si rileggono a colonne, non a oggetti: il comando scrive con Core, e gli oggetti
che la sessione tiene in memoria sono di prima del comando.
"""

import asyncio
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select, update

from app.cli.clean_doses import Cleaned, Sample, clean_doses, main, report
from app.cli.reparse_quantities import reparse
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import Recipe, RecipeIngredient
from app.db.models.unit import Unit
from app.domain.quantities import DoseShape
from app.repositories.ingredients import create_ingredient
from app.repositories.recipes import create_recipe


async def _unita(db_session, key: str) -> Unit:
    return (await db_session.execute(select(Unit).where(Unit.key == key))).scalars().one()


@pytest_asyncio.fixture
async def mondo(db_session):
    ing = {}
    for nome in [
        "parmigiano", "acqua", "burro", "sale", "zucchero", "limone", "olio", "uova",
        "pecorino", "pane",
    ]:
        ing[nome] = await create_ingredient(
            db_session, name=nome, display_name=nome.capitalize(),
            category=IngredientCategory.CEREALI,
        )
    importata = await create_recipe(
        db_session,
        title="Importata", description=None, instructions="i", servings=4,
        source="dataset", source_ref="https://esempio.invalid/importata",
        ingredients=[
            (ing["parmigiano"].id, "primary", "36 mesi\n\t\t\t50\n\t\t\tg", None),
            (ing["acqua"].id, "primary", "fredda\n\t\t\t330\n\t\t\tg", None),
            (ing["burro"].id, "primary", "100\n\t\t\tg", None),
            (ing["sale"].id, "secondary", "secco\n\n\t\t\tq.b.", None),
            (ing["zucchero"].id, "primary", "½\n\t\t\tcucchiaino", None),
            (ing["limone"].id, "primary", "1 + ½", None),
            (ing["olio"].id, "primary", "10\n\t\t\tg + q.b.", None),
            (ing["uova"].id, "primary", "1 intera\n\t\t\t60\n\t\t\tg", None),
        ],
        embedding=None,
    )
    # adottata (scritta a mano o modificata da Mattia) e archiviata: si può ripristinare,
    # quindi si pulisce come le altre, ma solo dove c'è ancora la forma dell'import
    adottata = await create_recipe(
        db_session,
        title="Adottata", description=None, instructions="i", servings=2,
        source="manual", source_ref=None,
        ingredients=[
            (ing["pecorino"].id, "primary", "da grattugiare\n\t\t\t30\n\t\t\tg", "mia"),
            (ing["burro"].id, "primary", "freddo 50 g", None),
            (ing["pane"].id, "primary", "2 intere", None),
        ],
        embedding=None,
    )
    await db_session.execute(
        update(Recipe).where(Recipe.id == adottata.id).values(archived_at=datetime.now(UTC))
    )
    # quel che il parser di prima non leggeva
    await db_session.execute(
        update(RecipeIngredient)
        .where(
            RecipeIngredient.quantity_text.in_(
                ["½\n\t\t\tcucchiaino", "1 + ½", "10\n\t\t\tg + q.b."]
            )
        )
        .values(quantity_value=None, quantity_unit_id=None)
    )
    # «intere» ha per singolare «intera», che esiste: ci punta, come fa decide_units
    (await _unita(db_session, "intere")).canonical_id = (await _unita(db_session, "intera")).id
    # un'unità già senza righe prima della pulizia: non è la pulizia ad averla lasciata sola
    db_session.add(Unit(key="cchiaio"))
    await db_session.flush()
    return {"importata": importata.id, "adottata": adottata.id}


async def _righe(db_session, recipe_id) -> dict[str, tuple]:
    """(testo, nota, valore, chiave dell'unità) per ingrediente, letti dal database."""
    risultato = await db_session.execute(
        select(
            Ingredient.name, RecipeIngredient.quantity_text, RecipeIngredient.note,
            RecipeIngredient.quantity_value, Unit.key,
        )
        .join(Ingredient, Ingredient.id == RecipeIngredient.ingredient_id)
        .outerjoin(Unit, Unit.id == RecipeIngredient.quantity_unit_id)
        .where(RecipeIngredient.recipe_id == recipe_id)
    )
    return {nome: (testo, nota, valore, chiave) for nome, testo, nota, valore, chiave in risultato.all()}


async def test_le_righe_dell_import_si_puliscono_e_si_rileggono(db_session, mondo):
    await clean_doses(db_session)

    righe = await _righe(db_session, mondo["importata"])
    assert righe["parmigiano"] == ("50 g", "36 mesi", Decimal("50"), "g")
    assert righe["acqua"] == ("330 g", "fredda", Decimal("330"), "g")
    assert righe["burro"] == ("100 g", None, Decimal("100"), "g")
    assert righe["sale"] == ("q.b.", "secco", None, None)
    assert righe["zucchero"] == ("½ cucchiaino", None, Decimal("0.5"), "cucchiaino")
    assert righe["limone"] == ("1 + ½", None, Decimal("1.5"), None)
    assert righe["olio"] == ("10 g + q.b.", None, Decimal("10"), "g")
    assert righe["uova"] == ("60 g", "1 intera", Decimal("60"), "g")


async def test_nella_ricetta_adottata_cambia_solo_la_riga_con_la_forma_dell_import(
    db_session, mondo
):
    await clean_doses(db_session)

    righe = await _righe(db_session, mondo["adottata"])
    # la nota scritta a mano resta davanti a quella che arriva dalla pulizia
    assert righe["pecorino"] == ("30 g", "mia; da grattugiare", Decimal("30"), "g")
    # scritte a mano, senza a capo: il testo non cambia, nemmeno con l'aggettivo davanti
    assert righe["burro"] == ("freddo 50 g", None, None, None)
    assert righe["pane"] == ("2 intere", None, Decimal("2"), "intere")


async def test_i_conti_per_forma_e_le_dosi_lette(db_session, mondo):
    esito = await clean_doses(db_session)

    assert esito.rows == 11
    assert esito.shapes == Counter({
        DoseShape.SPACES: 3,  # burro «100 g», zucchero, olio
        DoseShape.WORDS_BEFORE: 2,  # acqua, pecorino
        DoseShape.NUMBER_IN_NAME: 2,  # parmigiano, uova
        DoseShape.NOTE_QB: 1,  # sale
    })
    assert esito.cleaned == 8
    # prima: parmigiano (36 mesi), burro dell'import, uova (1 intera), pane
    assert esito.parsed_before == 4
    # dopo: tutte tranne sale («q.b.») e il burro scritto a mano
    assert esito.parsed_after == 9
    # lette prima e dopo, ma diverse: 36 mesi → 50 g, 1 intera → 60 g
    assert esito.changed_values == 2
    assert esito.new_units == []
    # il campione: una riga per forma, qui (il massimo è cinque)
    assert {campione.shape for campione in esito.sample} == set(esito.shapes)
    assert Sample(
        DoseShape.NUMBER_IN_NAME, "36 mesi\n\t\t\t50\n\t\t\tg", "50 g", "36 mesi"
    ) in esito.sample


async def test_le_unita_rimaste_senza_righe_se_ne_vanno_le_altre_restano(db_session, mondo):
    esito = await clean_doses(db_session)

    chiavi = set((await db_session.execute(select(Unit.key))).scalars())
    assert esito.removed_units == ["mesi"]
    assert "mesi" not in chiavi
    # «intera» non ha più righe, ma «intere» la usa ancora come suo singolare
    assert esito.kept_units == ["intera"]
    assert {"intera", "intere", "g", "cucchiaino"} <= chiavi
    # già senza righe prima: si elenca e resta
    assert "cchiaio" in esito.idle_units
    assert "cchiaio" in chiavi


async def test_due_unita_orfane_che_si_puntano_se_ne_vanno_insieme(db_session):
    """La FK di `canonical_id` è RESTRICT: fra due che se ne vanno, il puntatore si azzera
    prima, o la DELETE fallisce e con lei tutta la pulizia."""
    grana = await create_ingredient(
        db_session, name="grana", display_name="Grana", category=IngredientCategory.CEREALI
    )
    fontina = await create_ingredient(
        db_session, name="fontina", display_name="Fontina", category=IngredientCategory.CEREALI
    )
    await create_recipe(
        db_session,
        title="Formaggi", description=None, instructions="i", servings=2,
        source="dataset", source_ref=None,
        ingredients=[
            (grana.id, "primary", "24 mesi\n\t\t\t40\n\t\t\tg", None),
            (fontina.id, "primary", "1 mese\n\t\t\t30\n\t\t\tg", None),
        ],
        embedding=None,
    )
    (await _unita(db_session, "mesi")).canonical_id = (await _unita(db_session, "mese")).id
    await db_session.flush()

    esito = await clean_doses(db_session)

    assert esito.removed_units == ["mese", "mesi"]
    chiavi = set((await db_session.execute(select(Unit.key))).scalars())
    assert not {"mese", "mesi"} & chiavi


async def test_rilanciato_non_cambia_niente(db_session, mondo):
    await clean_doses(db_session)
    importata = await _righe(db_session, mondo["importata"])
    adottata = await _righe(db_session, mondo["adottata"])

    secondo = await clean_doses(db_session)

    assert secondo.cleaned == 0
    assert secondo.parsed_before == secondo.parsed_after == 9
    assert secondo.changed_values == 0
    assert (secondo.new_units, secondo.removed_units) == ([], [])
    assert await _righe(db_session, mondo["importata"]) == importata
    assert await _righe(db_session, mondo["adottata"]) == adottata


async def test_dopo_la_pulizia_reparse_quantities_legge_le_stesse_dosi(db_session, mondo):
    """La rilettura del comando è quella di `reparse_quantities`: l'altro comando, dopo di
    lui, non deve trovare niente da cambiare. Due strade che leggono le dosi devono
    leggerle uguali (prima lezione di CLAUDE.md)."""
    await clean_doses(db_session)
    importata = await _righe(db_session, mondo["importata"])
    adottata = await _righe(db_session, mondo["adottata"])

    # `reparse` legge oggetti ORM: quelli in memoria sono di prima del comando
    db_session.expunge_all()
    esito = await reparse(db_session)

    assert esito.new_units == 0
    assert await _righe(db_session, mondo["importata"]) == importata
    assert await _righe(db_session, mondo["adottata"]) == adottata


def test_il_resoconto_dice_i_conti_e_il_campione():
    esito = Cleaned(
        rows=11,
        shapes=Counter({DoseShape.NUMBER_IN_NAME: 1}),
        parsed_before=4,
        parsed_after=9,
        changed_values=2,
        removed_units=["mesi"],
        kept_units=["intera"],
        idle_units=["cchiaio"],
        sample=[Sample(DoseShape.NUMBER_IN_NAME, "36 mesi\n\t\t\t50\n\t\t\tg", "50 g", "36 mesi")],
    )

    assert report(esito).splitlines() == [
        "Righe lette: 11. Ripulite: 1.",
        "  solo a capo e tabulazioni: 0",
        "  parole davanti alla dose, ora nella nota: 0",
        "  numero nel nome, ora nella nota: 1",
        "  nota e q.b.: 0",
        "Dosi lette: 4 prima, 9 dopo; 2 lette diverse da prima.",
        "Unità nuove: nessuna.",
        "Unità tolte, nessuna riga le usa più: mesi.",
        "Unità senza righe tenute, perché canoniche di un'altra: intera.",
        "Unità già senza righe prima, lasciate: cchiaio.",
        "Campione:",
        "  [numero nel nome, ora nella nota] «36 mesi⏎50⏎g» → «50 g», nota «36 mesi»",
    ]


def test_un_argomento_sconosciuto_esce_senza_toccare_niente():
    """Un refuso («--conferma», il flag di fix_registry) non deve diventare una scrittura
    vera: argparse esce con 2 prima di aprire la sessione."""
    with pytest.raises(SystemExit) as uscita:
        asyncio.run(main(["--conferma"]))
    assert uscita.value.code == 2
```

- [ ] **Step 2: Falliscono**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/test_clean_doses_cli.py`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.cli.clean_doses'`.

- [ ] **Step 3: Il comando**

Crea `backend/app/cli/clean_doses.py`:

```python
"""Ripulisce le dosi scritte dall'import, le rilegge, e toglie le unità rimaste senza righe.

    python -m app.cli.clean_doses --dry-run
    python -m app.cli.clean_doses

Il primo fa tutto il lavoro e alla fine annulla la transazione: i numeri che stampa sono
quelli della scrittura vera, e un errore della scrittura vera esce già lì. Il secondo
salva, in una transazione sola. Rilanciato, non cambia niente: una dose pulita non ha più
la forma dell'import (spec `docs/superpowers/specs/2026-10-13-pulizia-dosi-design.md`).

Legge tutte le righe di `recipe_ingredients` — ricette importate, adottate, scritte a mano,
archiviate —, ma `clean_dose` cambia solo quelle che hanno ancora gli a capo e le
tabulazioni di GialloZafferano (decisione 3 di Mattia, 2026-10-13). La rilettura è quella
di `reparse_quantities` (`parse_quantity` più `ensure_unit`) in una passata sola e a tuple
invece che a oggetti: in produzione sono più di 83.000 righe.
"""

import argparse
import asyncio
import uuid
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import bindparam, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.db.models.recipe import RecipeIngredient
from app.db.models.unit import Unit
from app.domain.quantities import DoseShape, clean_dose, merge_notes, parse_quantity
from app.repositories.units import ensure_unit

SAMPLE_PER_SHAPE = 5

SHAPE_LABELS = {
    DoseShape.SPACES: "solo a capo e tabulazioni",
    DoseShape.WORDS_BEFORE: "parole davanti alla dose, ora nella nota",
    DoseShape.NUMBER_IN_NAME: "numero nel nome, ora nella nota",
    DoseShape.NOTE_QB: "nota e q.b.",
}

_LINES = RecipeIngredient.__table__
_UNITS = Unit.__table__

# Core e non ORM: un `update(RecipeIngredient)` con una lista diventerebbe l'«ORM bulk
# update», che controlla quante righe ha toccato, e una riga cancellata nel frattempo da
# chi usa l'app farebbe fallire tutto. I nomi dei parametri sono diversi da quelli delle
# colonne, come Core chiede.
_WRITE_LINE = (
    update(_LINES)
    .where(_LINES.c.id == bindparam("row_id"))
    .values(
        quantity_text=bindparam("new_text"),
        note=bindparam("new_note"),
        quantity_value=bindparam("new_value"),
        quantity_unit_id=bindparam("new_unit"),
    )
)


@dataclass(frozen=True)
class Sample:
    shape: DoseShape
    before: str | None
    after: str | None
    note: str | None


@dataclass
class Cleaned:
    rows: int = 0
    shapes: Counter[DoseShape] = field(default_factory=Counter)
    parsed_before: int = 0
    parsed_after: int = 0
    # lette sia prima sia dopo, ma con un valore o un'unità diversi: «36 mesi» → 50 g
    changed_values: int = 0
    new_units: list[str] = field(default_factory=list)
    removed_units: list[str] = field(default_factory=list)
    # senza righe dopo la pulizia, ma canoniche di un'unità che resta (FK RESTRICT)
    kept_units: list[str] = field(default_factory=list)
    # già senza righe prima: non è la pulizia ad averle lasciate sole, e non si toccano
    idle_units: list[str] = field(default_factory=list)
    sample: list[Sample] = field(default_factory=list)

    @property
    def cleaned(self) -> int:
        return sum(self.shapes.values())


async def clean_doses(session: AsyncSession) -> Cleaned:
    """Pulisce, rilegge e toglie le unità orfane. Non fa commit: decide chi chiama."""
    outcome = Cleaned()
    rows = (
        await session.execute(
            select(
                _LINES.c.id,
                _LINES.c.quantity_text,
                _LINES.c.note,
                _LINES.c.quantity_value,
                _LINES.c.quantity_unit_id,
            ).order_by(_LINES.c.id)
        )
    ).all()
    outcome.rows = len(rows)
    units = dict((await session.execute(select(_UNITS.c.key, _UNITS.c.id))).all())
    used_before = {row.quantity_unit_id for row in rows if row.quantity_unit_id is not None}

    writes = []
    for row in rows:
        cleaned = clean_dose(row.quantity_text)
        if cleaned.shape is DoseShape.UNCHANGED:
            text, note = row.quantity_text, row.note
        else:
            # la nota già scritta resta davanti: c'era prima della pulizia
            text, note = cleaned.quantity_text, merge_notes(row.note, cleaned.note)
            outcome.shapes[cleaned.shape] += 1
            if sum(1 for s in outcome.sample if s.shape is cleaned.shape) < SAMPLE_PER_SHAPE:
                outcome.sample.append(Sample(cleaned.shape, row.quantity_text, text, note))

        value, key = parse_quantity(text)
        unit_id = None
        if key is not None:
            if key not in units:
                units[key] = (await ensure_unit(session, key)).id
                outcome.new_units.append(key)
            unit_id = units[key]

        if row.quantity_value is not None:
            outcome.parsed_before += 1
        if value is not None:
            outcome.parsed_after += 1
            if row.quantity_value is not None and (value, unit_id) != (
                row.quantity_value,
                row.quantity_unit_id,
            ):
                outcome.changed_values += 1
        if (text, note, value, unit_id) != (
            row.quantity_text,
            row.note,
            row.quantity_value,
            row.quantity_unit_id,
        ):
            writes.append({
                "row_id": row.id,
                "new_text": text,
                "new_note": note,
                "new_value": value,
                "new_unit": unit_id,
            })

    if writes:
        await session.execute(_WRITE_LINE, writes)
    await _drop_orphaned_units(session, used_before, outcome)
    return outcome


async def _drop_orphaned_units(
    session: AsyncSession, used_before: set[uuid.UUID], outcome: Cleaned
) -> None:
    """Toglie le unità che la pulizia ha lasciato senza righe: le parole che stavano
    davanti alla dose («mesi», «da», «per»), finite nel registro come unità."""
    used_after = set(
        (
            await session.execute(
                select(_LINES.c.quantity_unit_id)
                .where(_LINES.c.quantity_unit_id.is_not(None))
                .distinct()
            )
        ).scalars()
    )
    registry = (
        await session.execute(select(_UNITS.c.id, _UNITS.c.key, _UNITS.c.canonical_id))
    ).all()
    keys = {unit.id: unit.key for unit in registry}
    orphaned = used_before - used_after
    deletable = set(orphaned)
    # Un'unità che resta e punta a una di queste la tiene in vita: la FK è RESTRICT. E
    # tenerla può tenerne un'altra, se a sua volta ci punta: si ripete finché niente cambia.
    while True:
        needed = {
            unit.canonical_id
            for unit in registry
            if unit.id not in deletable and unit.canonical_id in deletable
        }
        if not needed:
            break
        deletable -= needed
    if deletable:
        # fra quelle che se ne vanno, i puntatori prima: una che punta a un'altra della
        # stessa lista bloccherebbe la DELETE
        await session.execute(
            update(_UNITS).where(_UNITS.c.id.in_(deletable)).values(canonical_id=None)
        )
        await session.execute(delete(_UNITS).where(_UNITS.c.id.in_(deletable)))
    outcome.removed_units = sorted(keys[unit_id] for unit_id in deletable)
    outcome.kept_units = sorted(keys[unit_id] for unit_id in orphaned - deletable)
    outcome.idle_units = sorted(
        unit.key
        for unit in registry
        if unit.id not in used_before and unit.id not in used_after
    )


def _visible(text: str | None) -> str:
    """Una dose dell'import su una riga sola: l'a capo come ⏎, le tabulazioni via."""
    if text is None:
        return "(vuota)"
    return text.replace("\t", "").replace("\r", "").replace("\n", "⏎")


def _names(keys: list[str]) -> str:
    return ", ".join(keys) if keys else "nessuna"


def report(outcome: Cleaned) -> str:
    lines = [f"Righe lette: {outcome.rows}. Ripulite: {outcome.cleaned}."]
    for shape, label in SHAPE_LABELS.items():
        lines.append(f"  {label}: {outcome.shapes[shape]}")
    lines.append(
        f"Dosi lette: {outcome.parsed_before} prima, {outcome.parsed_after} dopo; "
        f"{outcome.changed_values} lette diverse da prima."
    )
    lines.append(f"Unità nuove: {_names(outcome.new_units)}.")
    lines.append(f"Unità tolte, nessuna riga le usa più: {_names(outcome.removed_units)}.")
    lines.append(
        f"Unità senza righe tenute, perché canoniche di un'altra: {_names(outcome.kept_units)}."
    )
    lines.append(f"Unità già senza righe prima, lasciate: {_names(outcome.idle_units)}.")
    if outcome.sample:
        lines.append("Campione:")
        for sample in outcome.sample:
            note = f", nota «{sample.note}»" if sample.note else ""
            lines.append(
                f"  [{SHAPE_LABELS[sample.shape]}] «{_visible(sample.before)}» → "
                f"«{_visible(sample.after)}»{note}"
            )
    return "\n".join(lines)


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ripulisce le dosi scritte dall'import, le rilegge, toglie le unità orfane."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="fa tutto, stampa i numeri e non salva niente"
    )
    arguments = parser.parse_args(argv)
    async with SessionLocal() as session:
        outcome = await clean_doses(session)
        print(report(outcome))
        if arguments.dry_run:
            await session.rollback()
            print("Era una prova, niente salvato: rilancia senza --dry-run per applicare.")
            return 0
        await session.commit()
    print("Salvato.")
    if outcome.new_units:
        print("Le unità nuove si decidono con: python -m app.cli.decide_units")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
```

- [ ] **Step 4: Passano**

Run: `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/test_clean_doses_cli.py tests/test_reparse_quantities_cli.py tests/test_decide_units_cli.py`
Expected: PASS. Se `test_dopo_la_pulizia_reparse_quantities_legge_le_stesse_dosi` fallisce, le due letture divergono: è un difetto del comando, non del test (la prima lezione di `CLAUDE.md`), e si corregge il comando.

- [ ] **Step 5: Commit**

```bash
git add backend/app/cli/clean_doses.py backend/tests/test_clean_doses_cli.py
git commit -m "dosi: python -m app.cli.clean_doses pulisce le righe esistenti, le rilegge e toglie le unità orfane, con --dry-run"
```

---

### Task 6: La nota nel dettaglio della ricetta

**Files:**
- Modify: `frontend/src/features/cooking/RecipeDetailScreen.tsx` (`IngredientRow`)
- Modify: `frontend/src/features/cooking/RecipeDetailScreen.test.tsx` (un `it` in fondo al `describe("RecipeDetailScreen", …)`)

Leggi i due file com'è sul ramo prima di cambiarli.

**Interfaces:**
- Consumes: `RecipeIngredientLine.note` (c'è già in `frontend/src/domain/types.ts` e nella risposta del backend).
- Produces: nessun tipo nuovo.

- [ ] **Step 1: Il test che fallisce**

In `RecipeDetailScreen.test.tsx`, in fondo al `describe("RecipeDetailScreen", …)` (prima della sua `});` di chiusura), aggiungi:

```tsx
  it("la nota della riga sta sotto il nome, e la dose resta a destra", async () => {
    // la nota nasce dalla pulizia delle dosi dell'import: «da grattugiare ⏎ 50 ⏎ g» è
    // diventata la dose «50 g» e la nota «da grattugiare» (spec 2026-10-13)
    stubFetch({
      ingredients: DETAIL.ingredients.map((line) =>
        line.ingredient_id === "i1" ? { ...line, note: "da grattugiare" } : line
      ),
    });
    renderScreen();
    const row = (await screen.findByText("Pasta")).closest("li")!;
    expect(within(row).getByText("da grattugiare")).toBeInTheDocument();
    expect(within(row).getByText("180 g")).toBeInTheDocument();
    // le righe senza nota non mostrano niente in più
    expect(screen.getAllByText("da grattugiare")).toHaveLength(1);
  });
```

- [ ] **Step 2: Fallisce**

Run (da `<worktree>/frontend`): `npx vitest run src/features/cooking/RecipeDetailScreen.test.tsx`
Expected: FAIL — `Unable to find an element with the text: da grattugiare`.

- [ ] **Step 3: Il codice**

In `RecipeDetailScreen.tsx`, dentro `IngredientRow`, nel `<span className="min-w-0 flex-1">`, dopo il blocco

```tsx
        {line.availability === "low" && !line.satisfied && (
          <span className="ml-2 text-xs font-medium text-low">non basta</span>
        )}
```

aggiungi

```tsx
        {/* la nota della riga: le parole che l'import scriveva davanti alla dose («da
            grattugiare», «36 mesi»), o quella scritta a mano. Sotto il nome e piccola:
            dice com'è l'ingrediente, non quanto — la dose resta a destra */}
        {line.note && (
          <span className="block break-words text-xs text-ink-soft">{line.note}</span>
        )}
```

- [ ] **Step 4: Passano, e i controlli**

Run (da `<worktree>/frontend`):
```bash
npx vitest run src/features/cooking/
npm run typecheck
npm run lint
```
Expected: PASS, typecheck e lint puliti.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/cooking/RecipeDetailScreen.tsx frontend/src/features/cooking/RecipeDetailScreen.test.tsx
git commit -m "dosi: nel dettaglio della ricetta la nota della riga sotto il nome"
```

---

### Task 7: Nel browser vero, col comando vero

**Files:**
- Create: `frontend/e2e/dosi-pulite.spec.ts`
- Modify: `frontend/e2e/style.spec.ts` (una prova in fondo al file)

Leggi `style.spec.ts` com'è sul ramo: le funzioni `testiIlleggibili` e `fermo` ci sono già (su `master`; cercale per nome), e il `beforeEach` in cima fa l'accesso.

**Interfaces:**
- Consumes: tutto quel che hanno fatto i Task 1–6, sull'app costruita e servita da Nginx, e `python -m app.cli.clean_doses` nel container `backend` dello stack `spena-e2e`.

- [ ] **Step 1: Le prove**

Crea `frontend/e2e/dosi-pulite.spec.ts`:

```ts
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

/**
 * La pulizia delle dosi dell'import nel browser vero, col comando vero nel container del
 * backend dello stack e2e (come `import-review.spec.ts` lancia i suoi aiutanti). Una
 * ricetta con le dosi nella forma di GialloZafferano — gli a capo e le tabulazioni —, la
 * prova che non salva niente, la scrittura, e il dettaglio che mostra la nota sotto il nome
 * e riscala la dose pulita. A 375×812, il telefono.
 *
 * Il comando passa su tutte le righe della base dello stack: quelle del seme non hanno la
 * forma dell'import, e non cambiano. La ricetta si crea con `page.request`, che condivide i
 * cookie della pagina, e si elimina nel `finally`.
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";
const RADICE = fileURLToPath(new URL("../..", import.meta.url));
// gli argomenti come elenco: un percorso o un nome di progetto con uno spazio non cambiano
// il comando
const COMPOSE_E2E = [
  "compose",
  "-p",
  process.env.E2E_PROJECT ?? "spena-e2e",
  "-f",
  "docker-compose.yml",
  "-f",
  "docker-compose.e2e.yml",
];

function pulisciDosi(...args: string[]): string {
  return execFileSync(
    "docker",
    [...COMPOSE_E2E, "exec", "-T", "backend", "python", "-m", "app.cli.clean_doses", ...args],
    { cwd: RADICE, encoding: "utf8" }
  );
}

async function entra(page: Page) {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  await page.getByLabel("Password", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();
}

async function ingrediente(page: Page, nome: string): Promise<string> {
  const risposta = await page.request.get(`/api/v1/ingredients/search?q=${encodeURIComponent(nome)}`);
  expect(risposta.ok()).toBe(true);
  const trovati = (await risposta.json()) as { id: string; name: string }[];
  const voce = trovati.find((trovato) => trovato.name === nome);
  expect(voce, `«${nome}» non è nel seme`).toBeDefined();
  return voce!.id;
}

function riga(page: Page, nome: string) {
  return page.getByRole("listitem").filter({ hasText: nome });
}

// stringhe e non funzioni: questo file lo compila tsconfig.node.json, senza la libreria DOM
async function nonScorreDiLato(page: Page, schermata: string) {
  await page.waitForLoadState("networkidle");
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
  expect(scrollWidth, `${schermata} scorre di lato`).toBeLessThanOrEqual(clientWidth);
}

test("le dosi dell'import si puliscono: la prova non salva, la scrittura sì, la nota sotto il nome e la dose che si riscala", async ({
  page,
}) => {
  await entra(page);
  const parmigiano = await ingrediente(page, "parmigiano");
  const farro = await ingrediente(page, "farro");
  const sale = await ingrediente(page, "sale");
  const burro = await ingrediente(page, "burro");
  const creata = await page.request.post("/api/v1/recipes", {
    data: {
      title: `Dosi dell'import e2e ${Date.now()}`,
      instructions: "Cuoci il farro, poi condisci.",
      servings: 2,
      source: "manual",
      ingredients: [
        { ingredient_id: parmigiano, role: "primary", quantity_text: "36 mesi\n\t\t\t50\n\t\t\tg" },
        { ingredient_id: farro, role: "primary", quantity_text: "(da sciacquare)\n\t\t\t160\n\t\t\tg" },
        { ingredient_id: sale, role: "secondary", quantity_text: "fino\n\n\t\t\tq.b." },
        { ingredient_id: burro, role: "primary", quantity_text: "10\n\t\t\tg + q.b." },
      ],
    },
  });
  expect(creata.ok()).toBe(true);
  const id = ((await creata.json()) as { id: string }).id;
  try {
    // la prova fa tutto il lavoro, lo racconta, e non salva niente
    const prova = pulisciDosi("--dry-run");
    expect(prova).toContain("«36 mesi⏎50⏎g» → «50 g», nota «36 mesi»");
    expect(prova).toContain("Era una prova, niente salvato");
    await page.goto(`/ricette/${id}`);
    await expect(riga(page, "parmigiano")).toContainText("50");
    await expect(page.getByText("36 mesi", { exact: true })).toHaveCount(0);

    // la scrittura vera: «mesi» non è più usata da nessuna riga, e se ne va
    const scritta = pulisciDosi();
    expect(scritta).toContain("Salvato.");
    expect(scritta).toMatch(/Unità tolte, nessuna riga le usa più: [^\n]*\bmesi\b/);

    await page.reload();
    await expect(riga(page, "parmigiano").getByText("36 mesi", { exact: true })).toBeVisible();
    await expect(riga(page, "parmigiano")).toContainText("50 g");
    await expect(riga(page, "farro").getByText("da sciacquare", { exact: true })).toBeVisible();
    await expect(riga(page, "farro")).toContainText("160 g");
    await expect(riga(page, "sale").getByText("fino", { exact: true })).toBeVisible();
    await expect(riga(page, "burro")).toContainText("10 g + q.b.");
    await nonScorreDiLato(page, "il dettaglio con le note");

    // da 2 a 3 porzioni: la dose pulita si riscala, «+ q.b.» resta accanto, «q.b.» com'è
    await page.getByRole("button", { name: "Una porzione in più" }).click();
    await expect(riga(page, "parmigiano")).toContainText("75 g");
    await expect(riga(page, "farro")).toContainText("240 g");
    await expect(riga(page, "burro")).toContainText("15 g + q.b.");
    await expect(riga(page, "sale")).toContainText("q.b.");

    // rilanciato, il comando non trova più niente da pulire
    expect(pulisciDosi("--dry-run")).toContain("Ripulite: 0.");
  } finally {
    const tolta = await page.request.patch(`/api/v1/recipes/${id}`, { data: { archived: true } });
    expect.soft(tolta.ok(), `pulizia: la ricetta ${id} non si è eliminata`).toBe(true);
  }
});
```

In fondo a `frontend/e2e/style.spec.ts` aggiungi:

```ts
test("la nota di una riga della ricetta si legge nei due temi", async ({ page }) => {
  // La nota nasce dalla pulizia delle dosi dell'import (spec 2026-10-13): il seme non ne
  // ha, quindi `perOgniLuogo` non la vede. Una ricetta con la nota, scritta con
  // `page.request`, e tolta alla fine.
  await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();
  const farro = (
    (await (await page.request.get("/api/v1/ingredients/search?q=farro")).json()) as {
      id: string;
      name: string;
    }[]
  ).find((voce) => voce.name === "farro");
  expect(farro, "«farro» non è nel seme").toBeDefined();
  const creata = await page.request.post("/api/v1/recipes", {
    data: {
      title: `Nota e2e ${Date.now()}`,
      instructions: "Cuoci.",
      servings: 2,
      source: "manual",
      ingredients: [
        { ingredient_id: farro!.id, role: "primary", quantity_text: "160 g", note: "da sciacquare" },
      ],
    },
  });
  expect(creata.ok()).toBe(true);
  const id = ((await creata.json()) as { id: string }).id;
  try {
    await page.goto(`/ricette/${id}`);
    await expect(page.getByText("da sciacquare", { exact: true })).toBeVisible();
    for (const tema of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: tema });
      await fermo(page);
      expect(await testiIlleggibili(page), `dettaglio con la nota, tema ${tema}`).toEqual([]);
    }
    await page.emulateMedia({ colorScheme: "light" });
  } finally {
    const tolta = await page.request.patch(`/api/v1/recipes/${id}`, { data: { archived: true } });
    expect.soft(tolta.ok(), `pulizia: la ricetta ${id} non si è eliminata`).toBe(true);
  }
});
```

- [ ] **Step 2: Typecheck e lint**

Run (da `<worktree>/frontend`): `npm run typecheck && npm run lint`
Expected: puliti (i file `e2e/` li compila `tsconfig.node.json`).

- [ ] **Step 3: L'e2e intera**

Con i comandi delle Global Constraints, dalla radice di `<worktree>`, su uno stack ricreato da zero (`down -v` prima dell'`up`, se ne era rimasto uno di questo ramo).
Expected: tutte verdi, le due nuove comprese. **Annota il numero** delle prove passate: è `N_e2e` del Task 9. Poi `down -v` e `rm .env`, sempre.

Se una prova nuova fallisce: guarda prima se il seme ha davvero «parmigiano», «farro», «sale», «burro» (`/api/v1/ingredients/search`); se la creazione della ricetta risponde 422, guarda se la rotta rifiuta gli a capo in `quantity_text` (non dovrebbe: `RecipeIngredientIn` ha solo `max_length=100`) e scrivilo nel report; se l'unità «g» nello stack si legge diversa (le forme non le decide nessun AI, lì: si mostra la chiave, «g»), adegua solo l'attesa del testo e scrivilo nel report. Se `pulisciDosi` non trova il container, controlla che lo stack si chiami `spena-e2e` (`docker ps`). Se fallisce `testiIlleggibili`, scrivi nel report quale testo e con che rapporto: **nessun token nuovo**; se il colpevole è la nota, il task si ferma `bloccato` con la misura.

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/dosi-pulite.spec.ts frontend/e2e/style.spec.ts
git commit -m "dosi: nel browser vero, il comando che pulisce (prima la prova), la nota sotto il nome, la dose che si riscala, il contrasto nei due temi"
```

---

### Task 8: I documenti

**Files:**
- Modify: `CLAUDE.md`
- Modify: `backend/app/db/models/recipe.py` (solo la docstring di `RecipeIngredient`)
- Modify: `docs/prossimi-passi.md` (Parte X, la voce che comincia con «**Il rovescio della voce sopra**»)
- Modify: `next-steps.md`

Leggi i file com'è sul ramo prima di cambiarli.

- [ ] **Step 1: `CLAUDE.md` e la docstring**

In `CLAUDE.md`, la frase

```
`quantity_text` stays the truth shown at 1× and is never rewritten; the structured
pair is what a rescale reads,
```

diventa

```
`quantity_text` stays the truth shown at 1× and is never rewritten — with one
exception, decided by Mattia on 2026-10-13: a dose still in the import's shape (a
newline or a tab in it, as GialloZafferano writes them) is cleaned once, its words
before the number moved to the line's `note` (`clean_dose`, run by the import and by
`python -m app.cli.clean_doses`); a dose without that shape is never touched. The structured
pair is what a rescale reads,
```

(il resto del paragrafo resta com'è).

In `backend/app/db/models/recipe.py`, nella docstring di `RecipeIngredient`, la frase

```
    `quantity_text` è la dose come l'ha scritta la fonte: non si riscrive mai e non
    si perde mai, ed è quel che si mostra a 1×.
```

diventa

```
    `quantity_text` è la dose come l'ha scritta la fonte: non si perde mai, ed è quel
    che si mostra a 1×. Si riscrive in un caso solo (Mattia, 2026-10-13): una dose
    ancora nella forma dell'import, con gli a capo di GialloZafferano, si pulisce una
    volta e le parole davanti al numero passano in `note` (`clean_dose`).
```

- [ ] **Step 2: `docs/prossimi-passi.md`**

In Parte X, in fondo alla voce che comincia con «**Il rovescio della voce sopra, visto con R4**» (dopo la frase che finisce con «finché qualcuno non le toglie.»), aggiungi, con lo stesso rientro della voce:

```markdown
  **Fatte tutte e due il <data di oggi>**, sul ramo `night/pulizia-dosi` (da revisionare),
  con le decisioni di Mattia del 2026-10-13 (spec
  `docs/superpowers/specs/2026-10-13-pulizia-dosi-design.md`). Le misure del 2026-10-13
  dicevano molto più di settanta e novanta: 9.767 righe con le parole davanti, 202 col
  numero nel nome, ~1.042 frazioni e ~3.547 «+ q.b.» non lette. Le parole davanti passano
  nella nota della riga, che l'import non aveva mai usato e che adesso il dettaglio mostra
  sotto il nome; il parser legge ½ ¼ ¾ e «50 g + q.b.» (riscalata «100 g + q.b.»);
  l'import pulisce dove il `payload` diventa ricetta; `python -m app.cli.clean_doses`
  (prima `--dry-run`) pulisce le righe che ci sono, anche delle ricette adottate ma solo
  dove resta la forma dell'import, le rilegge e toglie le unità rimaste senza righe. In
  produzione lo lancia Mattia dopo il deploy, con il backup prima: i comandi sono nel
  piano, «Dopo il deploy (solo Mattia)».
```

Sostituisci `<data di oggi>` con la data vera.

- [ ] **Step 3: `next-steps.md`**

1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte)_`.
2. Togli la riga della voce (`grep -n "Dosi dell'import con l'aggettivo davanti" next-steps.md`: `in corso` dalla Preparazione, dovunque sia). Se in «Pronti per la notte» era una voce numerata, lascia com'è la numerazione delle altre.
3. In cima a «Fatti (recenti)» aggiungi:
   ```markdown
   - [fatto] <data di oggi> · Pulizia delle dosi dell'import: le parole davanti alla dose e il numero nel nome nella nota (mostrata nel dettaglio sotto il nome), ½ ¼ ¾ e «50 g + q.b.» letti, l'import che pulisce all'ingresso, `python -m app.cli.clean_doses` con `--dry-run` per le righe esistenti e le unità spurie [Parte X] → branch night/pulizia-dosi (da revisionare)
   ```
4. In cima a «Da fare a mano (solo Mattia)» aggiungi:
   ```markdown
   - [tbd] P2 · Dopo il deploy della pulizia delle dosi: `clean_doses --dry-run` in produzione e il confronto coi numeri attesi, il backup del database, la scrittura, poi `decide_units` se ci sono unità nuove; i comandi esatti nel piano `docs/superpowers/plans/2026-10-13-pulizia-dosi.md`, «Dopo il deploy (solo Mattia)». Al dry-run, decidere se togliere le unità già senza righe prima della pulizia, che il comando elenca e lascia [Parte X]
   ```
5. Se nella notte sono emerse altre cose da fare fuori da questo piano, aggiungile come `idea` o `tbd` nella sezione giusta, con la voce di `docs/prossimi-passi.md` fra parentesi quadre.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md backend/app/db/models/recipe.py docs/prossimi-passi.md next-steps.md
git commit -m "docs: la pulizia delle dosi dell'import fatta sul ramo; quantity_text si riscrive una volta, solo nella forma dell'import"
```

---

### Task 9: La verifica finale e il report

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

Expected: vitest tutto verde — **`N_vitest` della Preparazione più 1**, in `N_file` file; se il numero differisce, scrivi nel report da dove viene la differenza. Typecheck, lint e build puliti. `npx tsc -b --force` perché `node_modules` è condiviso col checkout principale, e con lui il `tsbuildinfo`: `--force` compila davvero tutto.

- [ ] **Step 2: Il backend**

Da `<worktree>/backend` (con `TEST_DATABASE_URL` davanti se la Preparazione ha scelto `spena_test_pulizia`):

```bash
PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Expected: tutto verde, **`N_pytest` + 66** (14 + 5 del Task 1, 30 del Task 2, 3 del Task 3, 5 del Task 4, 9 del Task 5).

- [ ] **Step 3: I grep**

Dalla radice del worktree:

```bash
grep -rn "emerald\|neutral-" frontend/src
git diff master --stat -- backend/alembic
grep -n "with_qb_tail" backend/app/api/recipes.py | wc -l
```

Expected: i primi due vuoti (nessun colore crudo, nessuna migrazione); il terzo `2` (l'import e la chiamata in `_to_out`).

- [ ] **Step 4: L'e2e intera**

Con i comandi delle Global Constraints, su uno stack ricreato da zero. Expected: tutte verdi, `N_e2e` del Task 7. Poi `down -v` e `rm .env`, sempre. Se la Preparazione ha creato `spena_test_pulizia`: `docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_pulizia WITH (FORCE)'`.

- [ ] **Step 5: Il report**

Nel report della notte, `docs/night-reports/<data di oggi>.md` sul ramo: se il file c'è già sul ramo aggiungi una sezione in fondo, altrimenti crealo con un titolo `# Notte del <data di oggi>` (gli altri piani della notte scrivono lo stesso file sui loro rami: l'unione la fa la revisione). Per questo piano: il ramo e da dove parte (`master`); i conti veri (vitest, pytest, e2e) contro quelli della Preparazione; quale database dei test ha usato; i test di oggi cambiati (dovrebbe essere solo il caso «300 g + q.b.»); l'output di `clean_doses` sullo stack e2e (le due esecuzioni della prova), così Mattia vede la forma di quel che leggerà in produzione; le unità già senza righe che il comando elenca e lascia (in produzione le guarda Mattia al dry-run, deciso da Mattia il 2026-10-13); le scelte del piano che Mattia può voler rivedere: il ruolo dedotto dal testo arrivato, «½ + ½» = 1, «; » fra le note; i file che al merge incontrano altri rami della notte (`quantities.py`, `test_quantities.py`, `_to_out` e `IngredientRow` con R2 — e la riga d'ancora di R2 che deve passare da `with_qb_tail` —, `materialize.py` coi piani 9 e 10, `_to_out` con R8, `registry.py` con S12, `style.spec.ts` con tutti); e la sezione «Dopo il deploy (solo Mattia)» qui sotto, ricopiata. Niente push, niente merge, niente deploy.

```bash
git add docs/night-reports/
git commit -m "report: la pulizia delle dosi dell'import, la notte"
```

---

## Dopo il deploy (solo Mattia)

La notte non tocca la produzione. Quando Mattia avrà rivisto, unito e messo in produzione il ramo (il deploy di sempre, `docker compose -f docker-compose.prod.yml up -d --build --wait --wait-timeout 120`; nessuna migrazione), da quel momento le ricette **nuove** dell'import nascono pulite. Quelle che ci sono si puliscono così, in un momento in cui nessuno sta modificando ricette (il comando tiene una transazione sola su tutte le righe). **Il `-f docker-compose.prod.yml` non è opzionale** (CLAUDE.md: senza, lo stack di produzione viene sostituito da quello di sviluppo).

1. **La prova**, che fa tutto e non salva niente:
   ```bash
   ssh hetznerserver "cd ~/sites/spena && docker compose -f docker-compose.prod.yml exec -T backend python -m app.cli.clean_doses --dry-run"
   ```
   **I numeri attesi**, dalle misure del 2026-10-13 (un po' di più se nel frattempo sono entrate ricette nuove):
   - `Righe lette:` circa **83.343**; `Ripulite:` circa **61.137** (tutte le righe con a capo o tabulazioni);
   - `parole davanti alla dose, ora nella nota:` circa **9.800–10.500** (le 9.767 della misura, più quelle con un numero fra parentesi come «(circa 2 medie)» e quelle con una frazione dopo le parole);
   - `numero nel nome, ora nella nota:` **al massimo 202**; `nota e q.b.:` **qualche centinaio**; `solo a capo e tabulazioni:` il resto, circa **50.000–51.000**;
   - `Dosi lette:` **51.276 prima** (83.343 − 32.067), **circa 62.000–65.000 dopo** (le parole davanti, le frazioni, buona parte dei «+ q.b.»); restano non lette circa 18.000–21.000, quasi tutte `q.b.`; `lette diverse da prima:` circa **200–300** (il numero nel nome);
   - `Unità tolte:` una decina o qualche decina di parole che unità non sono — `mesi`, `da`, `per`, `già`, `di`, `w`, `grande`, `intere`, `lunghi`, `sodi`…; `Unità già senza righe prima, lasciate:` **5** nomi.

   **Non andare avanti** se `Dosi lette` dopo è **meno** di prima, se `Ripulite` è lontano da 61.000, se fra le unità tolte c'è un'unità vera (`g`, `ml`, `kg`, `cucchiaio`, `cucchiai`, `cucchiaino`, `spicchio`, `fette`…), o se il campione mostra una dose finita nella nota: è un difetto, e si torna di giorno con l'output.
2. **Il backup**, come nel runbook (`docs/import-gz-runbook.md`, §3):
   ```bash
   ssh hetznerserver "cd ~/sites/spena && docker compose -f docker-compose.prod.yml exec -T db sh -c 'pg_dump -U \"\$POSTGRES_USER\" \"\$POSTGRES_DB\"' | gzip > ~/spena-prima-della-pulizia-dosi-\$(date +%F).sql.gz && ls -lh ~/spena-prima-della-pulizia-dosi-*"
   ```
   Expected: un file di qualche decina di MB (il database era 72 MB dopo R4).
3. **La scrittura**:
   ```bash
   ssh hetznerserver "cd ~/sites/spena && docker compose -f docker-compose.prod.yml exec -T backend python -m app.cli.clean_doses"
   ```
   Expected: gli stessi numeri della prova, poi `Salvato.`. Rilanciando la prova (punto 1) deve dire `Ripulite: 0.` e nessuna unità tolta.
4. **Le unità nuove**, se l'ultima riga dice `Le unità nuove si decidono con: python -m app.cli.decide_units` (parole d'unità che prima stavano dietro un aggettivo e non erano mai state lette; ogni giro decide dodici parole, il costo è di frazioni di centesimo):
   ```bash
   ssh hetznerserver "cd ~/sites/spena && docker compose -f docker-compose.prod.yml exec -T backend python -m app.cli.decide_units"
   ```
   rilanciato finché non dice che non ce ne sono più in attesa.
5. **A video**: una ricetta con un formaggio stagionato («36 mesi» sotto il nome, «50 g» a destra) e una con «+ q.b.», riscalate con lo stepper.
6. **Le unità già senza righe prima della pulizia** (deciso da Mattia il 2026-10-13): la prova del punto 1 le elenca per nome nella riga «Unità già senza righe prima, lasciate: …», e il comando non le toglie. Lì Mattia decide se toglierle; se sì, è lavoro a parte, non di questo comando. La nota nel modulo la fa il piano 20 (`modulo-nota-nome`).

Se dopo la scrittura qualcosa non torna, il backup del punto 2 è la via indietro: va ripristinato a backend fermo, e non c'è ancora un runbook che lo descriva — si scrive di giorno, col dump davanti.
