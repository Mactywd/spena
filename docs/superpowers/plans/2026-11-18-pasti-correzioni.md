# Pasti con Claude: le correzioni della settimana, delle schede e degli utensili — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** chiudere i rilievi della revisione del 2026-11-18 sui pasti (S1–S3), sulle schede dei cambi (P1–P4) e sugli utensili (U1–U2), con le decisioni di Mattia su S1, S2 e P3.

**Architecture:** correzioni puntuali dentro i servizi che ci sono. «Fuori casa» nasconde la ricetta invece di staccarla (via il vincolo `ck_meal_away_no_recipe`); spostare un pasto prima dei suoi avanzi è un rifiuto nuovo con una via d'uscita; la scheda inversa ragiona per voce e non per riga, e non toglie dalla lista ciò che serve a un altro pasto; una scheda nuova di Claude mette da parte le vecchie non applicate (stato nuovo `superseded`). Nel frontend: il modulo del pasto, il pasto fuori casa, la ricetta in sola lettura, la scheda, gli utensili. Una migrazione, la `0024`.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Alembic, pytest su Postgres vero; React 19, TypeScript, Tailwind 4, TanStack Query, Vitest, Playwright. Nessuna chiamata a Claude.

**Spec:** `docs/superpowers/specs/2026-11-12-pasti-claude-design.md` (§4.1, §4.2, §5.1, §6.2, §5.4). I rilievi e le decisioni sono riportati qui sotto; la catena da cui parte è descritta in `docs/superpowers/plans/2026-11-12-pasti-settimana.md`, `docs/superpowers/plans/2026-11-12-pasti-pianificazione.md`, `docs/superpowers/plans/2026-11-12-utensili.md` e nel report `docs/night-reports/2026-11-13.md`. Leggi `CLAUDE.md` del repo prima di cominciare.

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/pasti-correzioni`, ramo `night/pasti-correzioni`, creato da **`night/pasti-chiave-api`** (piano `docs/superpowers/plans/2026-11-18-pasti-chiave-api.md`). Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì, mai dalla radice del checkout principale, che non si tocca. **Nessun push, nessun merge, nessun deploy. Mai `git stash`. Niente letture o scritture sulla produzione, e mai il `.env` del checkout principale. Nessuna chiamata vera a Claude.**
- **Leggi ogni file com'è sul ramo prima di cambiarlo.** Le righe citate dai rilievi sono indicative; il piano descrive le modifiche contro ancore riconoscibili. Dove il piano dà un elenco di firme per un file che non c'è, è un file nuovo.
- **I nomi della catena si usano così come sono**: `update_meal`, `create_meal`, `delete_meal`, `release_recipe`, `link_recipe`, `refuse_if_no_recipe_here`, `check_can_take_recipe`, `_unlink_leftovers_of`, `_check_leftover`, `MealRefusal`, `MealRefusalCode` (`app.services.meals`); `is_before` (`app.domain.meals`); `meal_out` (`app.api.meals`); `meal_refusal_response`, `_MEAL_STATUS` (`app.api.refusals`); `MealUpdate` (`app.schemas.meal`); `propose_card`, `propose_inverse_card`, `_still_used_elsewhere`, `_inverse_pantry_row`, `_inverse_list_row`, `apply_card`, `CardStatus`, `REVERSED_NOTE`, `CHANGED_NOTE` (`app.services.change_cards`, `app.db.models.change_card`); `planning_concluded` (`app.services.planning`); `card_line`, `_CARD_STATES` (`app.services.meal_chat`); `_describe_meal`, `GIORNI`, `SLOT_NAMES` (`app.services.claude.tools`, `app.services.claude.prompts`); nel frontend `MealForm`, `MealScreen`, `patchFrom`, `RecipeDetailView`, `IngredientRow`, `AddMissingButton`, `ChangeCard`, `UtensilRow`, `UtensilsScreen`, i tipi `Meal`, `MealBody`, `MealPatch`. **Se un nome sul ramo è diverso**, vale il codice: usalo e scrivilo nel report.
- **Le due decisioni fondanti** restano intere: niente quantità in dispensa (le schede cambiano solo i tre stati), e le ricette puntano solo a ingredienti alimentari attraverso l'imbuto.
- **Mai un vicolo cieco.** Ogni rifiuto nuovo ha la sua via d'uscita a video (S2: «Sposta e stacca l'avanzo»). Una correzione che chiude un buco non deve lasciare Mattia davanti a un «no» senza strada (quinta lezione di `CLAUDE.md`).
- **Il frontend non calcola logica di dominio**: quale avanzo verrebbe prima del suo pasto, le frasi dei rifiuti, lo stato di una scheda, tutto nel backend. Il frontend sceglie solo che cosa mostrare di quello che riceve.
- **Colore e primitive**: solo token di `frontend/src/index.css`, **nessun token nuovo**; `grep -rn "emerald\|neutral-" frontend/src` resta vuoto; ogni testo sopra 4,5:1 nei due temi (misurato da `frontend/e2e/style.spec.ts`); primitive da `frontend/src/components/ui/`, `Button` non cambia; bersagli alti almeno 44 px; a 375 px niente scorre di lato.
- Le parole a video sono in italiano e **si copiano esatte** da questo piano (fra «»; ‹…› è un valore). Gli identificatori in inglese, i commenti in italiano.
- **Il type check è `npm run typecheck`**, mai `tsc --noEmit`. Controlli del frontend, da `<worktree>/frontend`: `npx vitest run`, `npm run typecheck`, `npm run lint`, `npm run build`. Nei test dei componenti si usa `createTestQueryClient`.
- **Backend su Postgres vero**: `spena-db-1` (porta 5433), con il database di questo ramo, `spena_test_pasti_correzioni`. Mai `docker compose up` dal worktree, mai `-f docker-compose.prod.yml`. Si usa il `.venv` del checkout principale. Il comando di pytest, da `<worktree>/backend`:
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_pasti_correzioni \
    PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
- **e2e** sullo stack `spena-e2e` (il `.env` copiato da `.env.example` e cancellato alla fine; `-p spena-e2e` e `-f docker-compose.e2e.yml` in ogni comando; se lo stack c'è e non l'hai alzato tu, aspetta che sparisca), con le due righe della fixture CIQUAL:
  ```bash
  cp .env.example .env
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed --con-ricette
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python tests/ciqual_fixture.py /tmp/ciqual-e2e.xlsx
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.load_ciqual /tmp/ciqual-e2e.xlsx
  (cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
  rm .env
  ```
- **Nessuna dipendenza nuova.** **Una migrazione sola, la `0024`** (`backend/alembic/versions/0024_pasti_correzioni.py`, `down_revision = "0023"`).
- **I test di oggi si cambiano solo dove il piano lo dice**: `test_fuori_casa_toglie_la_ricetta_e_l_avanzo` (Task 2), il caso `fuori_casa_con_ricetta` di `test_migration_0020.py` (Task 1), le etichette «Nota» dell'aggiunta in `UtensilsScreen.test.tsx` e nel `aggiungi` di `frontend/e2e/utensili.spec.ts` (Task 10). Nessun altro.

### Preparazione (una volta, prima del Task 1)

- [ ] **Il ramo di partenza.** Il piano della chiave API deve aver lasciato `night/pasti-chiave-api` con la sua migrazione:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify night/pasti-chiave-api
  git ls-tree -r --name-only night/pasti-chiave-api -- backend/alembic/versions | grep 0023
  git show night/pasti-chiave-api:backend/app/domain/meal_chat.py | grep -c 'RATE_LIMIT = "rate_limit"'
  ls .worktrees/pasti-correzioni 2>&1 | head -1
  ```
  Expected: un hash (**annotalo**: è `BASE` del Task 12); `…/0023_modifiche_ingredienti.py`; `1`; `No such file or directory`. **Se il ramo non esiste o non ha la `0023`**, non creare niente: fermati e scrivi nel messaggio finale della notte che questo piano non è partito perché manca quello della chiave API. Se il report di quel ramo (`docs/night-reports/` sul ramo) dice un task `bloccato`, leggi quale: questo piano non consuma niente del Task 2 (trascrizioni) né del Task 10 (e2e), e può partire lo stesso; per ogni altro task bloccato, fermati allo stesso modo. Se il worktree esiste già, fermati e scrivilo.
- [ ] **Il database dei test di questo ramo**:
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_pasti_correzioni WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_pasti_correzioni'
  ```
- [ ] `cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund`.
- [ ] **Il worktree**, con `node_modules` collegato e nessun `.env`:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/pasti-correzioni -b night/pasti-correzioni night/pasti-chiave-api
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/pasti-correzioni/frontend/node_modules
  ```
- [ ] **La testa di Alembic**, da `<worktree>/backend`: `DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_pasti_correzioni PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" alembic heads`. Expected: una riga sola, `0023 (head)`.
- [ ] **La voce del backlog.** In `next-steps.md` la voce che cita questo piano (`2026-11-18-pasti-correzioni.md`) passa a `in corso`, con in coda ` → in corso su night/pasti-correzioni`. Commit: `git commit -m "next-steps: le correzioni dei Pasti, in corso"`. Se la voce non c'è, aggiungila sotto «In corso» nello stile delle altre, con `[Parte IV]`.
- [ ] **La linea di partenza**: vitest e pytest dal worktree, tutto verde. **Annota** `N_file`, `N_vitest` e `N_pytest`. Se non è verde, fermati: va nel report.

---

## Obiettivo e contesto

La catena «Pasti con Claude» è su `master` e non è mai andata in produzione. La revisione del 2026-11-18 ha trovato, oltre ai difetti della chat (piano della chiave API), nove difetti fra la settimana, le schede dei cambi e gli utensili. Tre li ha decisi Mattia; gli altri hanno una correzione sola che regge.

## Decisioni prese

Di Mattia (2026-11-18):

1. **S1 — la ricetta resta.** «Fuori casa» nasconde la ricetta del pasto senza staccarla; togliendo la spunta, torna. «Sostituisci» (il posto occupato) chiede prima, come già fa l'eliminazione del pasto: se l'occupante ha una ricetta fuori dal ricettario, l'avviso lo dice («La sua ricetta non è nel ricettario: si elimina con il pasto.»).
2. **S2 — si chiede.** Spostare un pasto in un posto che non viene più prima di un suo avanzo è rifiutato con «‹Martedì pranzo› è un suo avanzo.», e il modulo offre «Sposta e stacca l'avanzo» (l'avanzo diventa un pasto a mano, con il suo piatto) oppure «Annulla».
3. **P3 — la nuova sostituisce.** Una scheda dei cambi nuova di Claude per lo stesso pasto mette da parte quelle non ancora applicate, come già fanno le proposte dei pasti (decisione 12 del piano della pianificazione).

Del piano (Claude, sui rilievi; Mattia le rivede nel report):

4. **S1 nel dettaglio.** Il vincolo `ck_meal_away_no_recipe` se ne va (migrazione `0024`): un pasto fuori casa può tenere la sua ricetta. Restano: nessuna ricetta **nuova** a un pasto fuori casa (`refuse_if_no_recipe_here`), niente chat (`can_chat`), niente coda delle ricette; il legame d'avanzo si toglie come oggi, e gli avanzi che venivano da lui restano soli come oggi; la scheda inversa del «fuori casa» si propone come oggi. Claude, leggendo i pasti, vede un pasto fuori casa senza ricetta (`_describe_meal`). Eliminare un pasto fuori casa archivia la sua ricetta nascosta, e l'avviso di «Elimina» lo dice come per gli altri.
5. **S2 nel dettaglio.** Il rifiuto ha il codice `leftover_after` (409) e porta, oltre alla frase, `leftovers: <quanti>`; con `detach_leftovers: true` nel corpo, lo spostamento stacca **solo** gli avanzi che verrebbero prima o nello stesso posto, e gli altri restano legati. Un pasto che nello stesso cambio va fuori casa non chiede niente (i suoi avanzi si staccano già). La frase usa il giorno della settimana e il pasto («Martedì pranzo»): un avanzo sta al massimo 3 giorni dopo il suo pasto, quindi il giorno della settimana basta. Con due avanzi: «Martedì pranzo e mercoledì cena sono suoi avanzi.», e il pulsante dice «Sposta e stacca gli avanzi».
6. **Le due domande del modulo** (il posto occupato e l'avanzo) nascondono, finché sono aperte, i pulsanti del modulo («Salva»/«Annulla»): così non ci sono mai due «Annulla» affiancati (chiude l'idea del backlog che lo segnala). Scelta estetica.
7. **S3.** La ricetta in sola lettura di un avanzo non ha «Sostituisci» su nessuna riga (né il pannello dei sostituti) e non ha «Metti in lista ciò che manca». Lo stepper delle porzioni e il tocco sulla dose restano: cambiano solo la vista e non scrivono niente.
8. **P1 — l'inversa per voce.** Le righe di dispensa d'origine di un pasto si raggruppano per voce (`pantry_item_id`). Lo stato a cui rimettere è il `before_status` della riga **più vecchia** (l'effetto netto del pasto); se la voce è già così, nessuna riga. La riga è spuntata se la voce è ancora nello stato che le ha dato la riga **più recente**; se no non è spuntata, con `CHANGED_NOTE`. Se una qualunque riga del gruppo serve ancora a un altro pasto ufficiale e non fuori casa, il gruppo si salta. La riga inversa ricorda **tutte** le sue righe d'origine (colonna nuova `change_card_rows.source_row_ids`); applicata, le segna tutte `reversed_at`, e si salta con `REVERSED_NOTE` se una qualunque è già rimessa.
9. **P2 — la lista che serve a un altro pasto.** Una riga di lista d'origine non si toglie se un'altra scheda in avanti, proposta o applicata, ha una riga di lista per lo stesso ingrediente al servizio di un altro pasto ufficiale e non fuori casa (anche se quella riga era «Già in lista.» e non è mai stata applicata).
10. **P3 nel dettaglio.** Lo stato nuovo è `superseded` («sostituita»), con `discarded_at` come momento in cui è stata messa da parte. Lo applica solo `propose_card` (le schede di Claude), alle schede **in avanti, ancora proposte**, comprese quelle create a mano con la scheda vuota. **Cosa vuol dire «lo stesso pasto» per una scheda di più pasti (confermato da Mattia il 2026-11-21):** si mette da parte una scheda vecchia solo se **tutti** i suoi pasti sono fra quelli della nuova (`set(vecchia.meal_ids) <= set(nuova.meal_ids)`). Così la scheda nuova della settimana mette da parte quella vecchia della settimana e quelle dei singoli piatti, mentre una scheda del solo piatto di martedì non mette da parte quella della settimana intera. La regola sta tutta in `_supersedes(old_meal_ids, new_meal_ids) -> bool` (Task 9): cambiarla è una riga. Le inverse non si toccano mai. A video: «Sostituita da una scheda più nuova.», senza «Applica»; nella cronologia di Claude, «sostituita».
11. **P4.** `link_recipe` e `release_recipe` azzerano `recipe_notice`: un avviso vecchio della coda non ricompare quando il pasto torna senza ricetta.
12. **U1, U2.** Aprendo «Correggi» il fuoco va su «Nome»; chiudendo la correzione (salvata o annullata) torna su «Correggi» di quella riga (chiude l'idea del backlog sul fuoco che resta sul corpo). Il campo della nota dell'aggiunta si chiama «Nota del nuovo utensile».

## Criteri di accettazione

- [ ] Un pasto con ricetta che va fuori casa la tiene, nascosta; tornando a casa la ricetta e la chat ci sono di nuovo. «Sostituisci» dice prima che la ricetta dell'occupante si elimina, se non è nel ricettario.
- [ ] Spostare «Lasagne» dopo il suo avanzo chiede, e «Sposta e stacca l'avanzo» lo fa; nessuna settimana mostra più un avanzo prima del suo pasto.
- [ ] La ricetta di un avanzo non scrive niente: nessun «Sostituisci», nessun «Metti in lista ciò che manca».
- [ ] La scheda inversa di un pasto con due schede applicate sulla stessa voce propone l'effetto netto; non toglie dalla lista ciò che serve a un altro pasto; una scheda nuova di Claude mette da parte le vecchie non applicate dei suoi pasti, e la pianificazione si conclude.
- [ ] Un avviso vecchio della ricetta non ricompare dopo un «Scrivi la ricetta» e un'eliminazione della ricetta.
- [ ] Il fuoco e le etichette degli utensili come in U1 e U2.
- [ ] La `0024` sale e scende. Tutti i test di oggi passano, cambiati solo dove il piano lo dice. L'e2e intera è verde, con le prove nuove.

## Comandi di verifica

Da `<worktree>/backend`: il comando di pytest. Da `<worktree>/frontend`: `npx vitest run`, `npm run typecheck`, `npx tsc -b --force`, `npm run lint`, `npm run build`. Dalla radice di `<worktree>`:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -rn "ck_meal_away_no_recipe" backend/app
git diff night/pasti-chiave-api --stat -- backend/alembic/versions
```

Expected: il primo vuoto; il secondo vuoto (il nome resta solo nella `0020` e nella `0024`, fuori da `backend/app`); l'ultimo un file solo, `0024_pasti_correzioni.py`. Poi l'e2e intera con i comandi delle Global Constraints.

## Review Focus

1. **Un pasto fuori casa con ricetta nascosta, poi eliminato dalla settimana**: la ricetta si archivia e l'avviso di «Elimina» lo dice prima (Task 2, `test_eliminare_un_pasto_fuori_casa_archivia_la_ricetta_nascosta`; Task 4, il test di `MealScreen`).
2. **Lo spostamento che cade sia su un posto occupato sia prima di un avanzo**: prima la domanda del posto, poi, con «Sostituisci», quella dell'avanzo; «Sposta e stacca l'avanzo» manda anche `replace` (Task 4, `«il posto occupato e poi l'avanzo: due domande in fila»`).
3. **Un'inversa applicata col «fuori casa», poi il pasto torna a casa e si elimina**: la seconda inversa non ripropone le righe già rimesse (Task 7, `test_l_inversa_del_fuori_casa_applicata_non_si_ripropone_all_eliminazione`).
4. **Una scheda vecchia con righe aggiunte a mano, messa da parte da una nuova di Claude**: le righe restano leggibili nella scheda «Sostituita da una scheda più nuova.», e niente si applica (Task 9, `test_una_scheda_messa_da_parte_non_si_applica`).
5. **Lo stato vecchio `discarded` nella conclusione della pianificazione**: una conversazione la cui scheda è stata messa da parte da una scheda nuova poi applicata si conclude (Task 9, `test_la_pianificazione_si_conclude_dopo_una_scheda_sostituita`).

## Fuori scope

- La chat, la chiave API e i rilievi C1–C7: piano `docs/superpowers/plans/2026-11-18-pasti-chiave-api.md`.
- Le altre idee dei Pasti in `next-steps.md`, in particolare: la scheda inversa del «fuori casa» che resta proposta quando il pasto torna a casa (con S1 la ricetta torna, ma la scheda resta da scartare a mano); la finestra di 3 giorni dell'avanzo che la scrittura non ricontrolla; il legame dell'avanzo che non si cambia da «Correggi»; «Metti nella settimana» che sostituisce un posto occupato senza dire della ricetta dell'occupante (la conferma della pianificazione, diversa da «Sostituisci» del modulo).
- Cambiare la finestra dell'avanzo, la regola della scheda inversa sulle liste (solo ciò che la scheda aveva aggiunto davvero), i prompt.

## Margine di autonomia

- **Liberi:** nomi locali, helper dei test, funzioni private non fissate qui; la disposizione delle domande del modulo (dentro il sistema visivo di spena, con `Alert tone="note"` come oggi).
- **Fissi:** le frasi fra «» di questo piano; i codici `leftover_after` e `superseded`; il campo `detach_leftovers`; la colonna `source_row_ids`; i nomi pubblici delle Interfaces.
- **Una decisione di comportamento non coperta e non reversibile**: si ferma quel task, si committa il lavoro parziale, la voce del backlog passa a `bloccato` con «attende: …» e la domanda precisa, e si va al task dopo se non dipende da quello. Una scelta reversibile e a basso impatto: la più conservativa, annotata nel report.
- Un test che fallisce e non si risolve: niente test disattivati, niente asserzioni indebolite. `bloccato` con la diagnosi.

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `backend/alembic/versions/0024_pasti_correzioni.py` (nuovo), `backend/app/db/models/meal.py`, `backend/app/db/models/change_card.py`, `backend/tests/db/test_migration_0024.py` (nuovo), `backend/tests/db/test_migration_0020.py` | 1 | lo schema |
| `backend/app/services/meals.py`, `backend/app/services/claude/tools.py`, `backend/tests/services/test_meals.py`, `backend/tests/api/test_meals.py`, `backend/tests/services/test_claude_tools.py` | 2 | S1 nel backend |
| `backend/app/domain/meals.py`, `backend/app/services/meals.py`, `backend/app/services/claude/prompts.py`, `backend/app/api/refusals.py`, `backend/app/api/meals.py`, `backend/app/schemas/meal.py`, test | 3 | S2 nel backend |
| `frontend/src/features/meals/MealForm.tsx`, `frontend/src/features/meals/MealScreen.tsx`, `frontend/src/domain/types.ts`, test | 4 | il modulo del pasto e il pasto fuori casa |
| `frontend/src/features/cooking/RecipeDetailScreen.tsx`, test | 5 | S3 |
| `backend/app/services/meals.py`, test | 6 | P4 |
| `backend/app/services/change_cards.py`, `backend/tests/services/test_inverse_cards.py` | 7, 8 | P1, P2 |
| `backend/app/services/change_cards.py`, `backend/app/services/meal_chat.py`, `backend/app/schemas/change_card.py`, `frontend/src/features/change-cards/ChangeCard.tsx`, `frontend/src/domain/types.ts`, test | 9 | P3 |
| `frontend/src/features/utensils/UtensilRow.tsx`, `frontend/src/features/utensils/UtensilsScreen.tsx`, `UtensilsScreen.test.tsx`, `frontend/e2e/utensili.spec.ts` | 10 | U1, U2 |
| `frontend/e2e/pasti.spec.ts`, `frontend/e2e/style.spec.ts` | 11 | nel browser vero |
| `docs/superpowers/specs/2026-11-12-pasti-claude-design.md`, `next-steps.md`, `docs/night-reports/<data>.md` | 12 | documenti e report |

---

### Task 1: Lo schema — la ricetta del pasto fuori casa, la scheda sostituita, le origini dell'inversa

**Files:**
- Create: `backend/alembic/versions/0024_pasti_correzioni.py`, `backend/tests/db/test_migration_0024.py`
- Modify: `backend/app/db/models/meal.py` (via il `CheckConstraint` `ck_meal_away_no_recipe`), `backend/app/db/models/change_card.py` (`CardStatus.SUPERSEDED = "superseded"`, il vincolo dello stato, `ChangeCardRow.source_row_ids`, la docstring del modulo), `backend/tests/db/test_migration_0020.py` (il caso `fuori_casa_con_ricetta` esce dal parametrizzato: dopo la `0024` è permesso, e lo prova il test nuovo)

**Interfaces:**
- Produces: `meals` senza `ck_meal_away_no_recipe`; `ck_card_status` = `status IN ('proposed', 'applied', 'discarded', 'superseded')`; `change_card_rows.source_row_ids JSONB NOT NULL DEFAULT '[]'::jsonb` (gli id come stringhe, come `meal_ids`); `ChangeCardRow.source_row_ids: Mapped[list[str]]`. La `downgrade` rimette il vincolo dei pasti dopo aver staccato le ricette dei pasti fuori casa (`UPDATE meals SET recipe_id = NULL WHERE away`), riporta a `discarded` le schede `superseded` e toglie la colonna.

- [ ] **Step 1: Il test che fallisce.** `test_migration_0024.py`, sul modello di `test_migration_0022.py` (un database suo, Alembic in un sottoprocesso): `test_la_0024_sale_e_scende`; `test_un_pasto_fuori_casa_puo_tenere_la_ricetta` (dopo `upgrade head` l'`INSERT` di un pasto `away` con `recipe_id` riesce); `test_una_scheda_puo_essere_sostituita` (`status='superseded'` riesce, `status='lost'` fallisce); `test_le_origini_dell_inversa_hanno_un_default` (una riga scritta senza `source_row_ids` vale `[]`); `test_la_0024_scende_staccando_le_ricette_fuori_casa` (un pasto fuori casa con ricetta e una scheda `superseded`, poi `downgrade 0023`: il pasto non ha più la ricetta, la scheda è `discarded`).
- [ ] **Step 2: Fallisce.** Expected: FAIL.
- [ ] **Step 3: Migrazione e modelli.** La docstring di `change_card.py` dice il nuovo stato: «proposed → applied | discarded | superseded (messa da parte da una scheda nuova di Claude per gli stessi pasti)».
- [ ] **Step 4: Passa, e lo schema coincide coi modelli.** Il comando di pytest con `tests/db/test_migration_0024.py tests/db/test_migration_0020.py tests/db/test_metadata_matches_migrations.py`, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `feat(pasti): un pasto fuori casa può tenere la ricetta, una scheda può essere sostituita, un'inversa ricorda tutte le sue origini (0024)`.

---

### Task 2: «Fuori casa» nasconde la ricetta, non la stacca (S1)

**Files:**
- Modify: `backend/app/services/meals.py` (`update_meal`, il ramo `if away and not meal.away`), `backend/app/services/claude/tools.py` (`_describe_meal`)
- Test: `backend/tests/services/test_meals.py`, `backend/tests/api/test_meals.py`, `backend/tests/services/test_claude_tools.py`

- [ ] **Step 1: I test che falliscono.**
  - `test_meals.py`: `test_fuori_casa_toglie_la_ricetta_e_l_avanzo` diventa `test_fuori_casa_tiene_la_ricetta_e_toglie_l_avanzo` (dopo `update_meal(origin, {"away": True})`: `recipe_id` è quello di prima, la copia **non** è archiviata, l'avanzo non è più legato); `test_tornare_a_casa_rimette_la_ricetta` (poi `{"away": False}`: stessa ricetta, `can_chat` vero); `test_eliminare_un_pasto_fuori_casa_archivia_la_ricetta_nascosta`; `test_un_pasto_fuori_casa_non_riceve_una_ricetta_nuova` (senza ricetta e fuori casa: `check_can_take_recipe` solleva `NO_RECIPE_HERE` come oggi); `test_fuori_casa_propone_ancora_l_inversa` (con una scheda applicata, l'inversa del «fuori casa» nasce come oggi).
  - `tests/api/test_meals.py`: `test_un_pasto_fuori_casa_ha_la_ricetta_nel_pasto` (`GET /meals/<id>` di un pasto fuori casa con ricetta: `away` vero, `recipe` valorizzato, `can_chat` falso, `can_ask_recipe` falso).
  - Strumenti: `test_read_meals_non_mostra_la_ricetta_di_un_pasto_fuori_casa` (il testo ha «(fuori casa)» e non «ricetta:»).
- [ ] **Step 2: Falliscono.** Expected: FAIL.
- [ ] **Step 3: Il codice.** In `update_meal` il ramo del «fuori casa» tiene `propose_inverse_card`, `meal.leftover_of_id = None` e `_unlink_leftovers_of`, e perde `release_recipe`; il commento dice la decisione di Mattia del 2026-11-18 (la ricetta resta, nascosta). In `_describe_meal` la ricetta si descrive solo se `not meal.away`.
- [ ] **Step 4: Passano**, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `fix(pasti): «Fuori casa» nasconde la ricetta del pasto invece di archiviarla; tornando a casa torna`.

---

### Task 3: Spostare un pasto prima dei suoi avanzi chiede (S2, backend)

**Files:**
- Modify: `backend/app/domain/meals.py` (`WEEKDAY_NAMES`, `SLOT_WORDS`, `place_words`), `backend/app/services/claude/prompts.py` (`GIORNI` e `SLOT_NAMES` si prendono da `app.domain.meals`: una copia sola), `backend/app/services/meals.py` (`MealRefusalCode.LEFTOVER_AFTER`, `update_meal`), `backend/app/api/refusals.py` (`_MEAL_STATUS`, `meal_refusal_response`), `backend/app/schemas/meal.py` (`MealUpdate`), `backend/app/api/meals.py` (la `PATCH`)
- Test: `backend/tests/domain/test_meals.py`, `backend/tests/services/test_meals.py`, `backend/tests/api/test_meals.py`

**Interfaces:**
- Produces: in `app.domain.meals`, `WEEKDAY_NAMES = ("lunedì", …, "domenica")`, `SLOT_WORDS = {"lunch": "pranzo", "dinner": "cena"}`, `def place_words(day: date, slot: MealSlot) -> str` («martedì pranzo»). `MealRefusalCode.LEFTOVER_AFTER = "leftover_after"` (409); `MealRefusal` con l'attributo nuovo `leftovers: int = 0`. `update_meal(session, meal, changes, *, replace=False, detach_leftovers=False)`. `MealUpdate.detach_leftovers: bool = False`, che come `replace` non è un cambio. Il corpo del rifiuto: `{"detail": …, "code": "leftover_after", "leftovers": n}`.

- [ ] **Step 1: I test che falliscono.**
  - Dominio: `test_place_words` («martedì pranzo» per un martedì a pranzo, «domenica cena»).
  - `test_meals.py` (servizio), con «Lasagne» lunedì cena e il suo avanzo martedì pranzo:
    - `test_spostare_il_pasto_dopo_il_suo_avanzo_chiede`: `update_meal(lasagne, {"day": mercoledì})` → `MealRefusal` con codice `LEFTOVER_AFTER`, frase «Martedì pranzo è un suo avanzo.», `leftovers == 1`, e niente è cambiato.
    - `test_con_due_avanzi_la_frase_li_dice_tutti`: avanzi martedì pranzo e martedì cena, origine spostata a mercoledì → «Martedì pranzo e martedì cena sono suoi avanzi.», `leftovers == 2`.
    - `test_sposta_e_stacca_l_avanzo`: con `detach_leftovers=True` il pasto si sposta, l'avanzo di martedì è un pasto a mano con il suo piatto («Lasagne» o com'era scritto) e `leftover_of_id` vuoto.
    - `test_stacca_solo_gli_avanzi_che_verrebbero_prima`: avanzi martedì pranzo e giovedì pranzo, origine spostata a mercoledì cena con `detach_leftovers=True` → martedì staccato, giovedì ancora legato.
    - `test_spostare_prima_non_chiede_niente`: origine spostata a domenica cena della settimana prima (sempre prima dell'avanzo) → riesce senza domande.
    - `test_spostare_e_andare_fuori_casa_insieme_non_chiede`: `{"day": mercoledì, "away": True}` → riesce, gli avanzi staccati come oggi.
  - `tests/api/test_meals.py`: `test_patch_dopo_l_avanzo_e_409_con_quanti` (corpo `{"code": "leftover_after", "detail": "Martedì pranzo è un suo avanzo.", "leftovers": 1}`); `test_patch_con_detach_leftovers_sposta` (200, e il pasto avanzo è staccato).
- [ ] **Step 2: Falliscono.** Expected: FAIL.
- [ ] **Step 3: Il codice.** In `update_meal`, fra i rifiuti prima di scrivere e **dopo** quello del posto occupato: se il pasto si sposta e non va fuori casa, si leggono gli avanzi che puntano a lui e si tengono quelli per cui `not is_before(day, slot, avanzo.day, MealSlot(avanzo.slot))`; se ce ne sono e `detach_leftovers` è falso, il rifiuto, con la frase costruita da `place_words` (prima lettera maiuscola; «X è un suo avanzo.» per uno, «X e Y sono suoi avanzi.» per due, «X, Y e Z sono suoi avanzi.» per tre o più, in ordine di posto). Con `detach_leftovers`, dopo la sostituzione dell'occupante e prima di scrivere il posto nuovo, quegli avanzi hanno `leftover_of_id = None`. La `PATCH` esclude `detach_leftovers` dai cambi e lo passa. `meal_refusal_response` aggiunge `leftovers` per questo codice.
- [ ] **Step 4: Passano**, poi la suite intera. Expected: PASS (i prompt non cambiano: `GIORNI` e `SLOT_NAMES` hanno gli stessi valori).
- [ ] **Step 5: Commit** — `fix(pasti): spostare un pasto prima dei suoi avanzi chiede, e «Sposta e stacca l'avanzo» li stacca`.

---

### Task 4: Il modulo del pasto e il pasto fuori casa (S1, S2 nel frontend)

**Files:**
- Modify: `frontend/src/features/meals/MealForm.tsx`, `frontend/src/features/meals/MealScreen.tsx` (`patchFrom`, il ramo `m.away`, la condizione di `RecipeDetailView`), `frontend/src/domain/types.ts` (`MealBody.detach_leftovers?: boolean`, `MealPatch.detach_leftovers?: boolean`)
- Test: `frontend/src/features/meals/MealForm.test.tsx`, `frontend/src/features/meals/MealScreen.test.tsx`

**Interfaces:**
- Consumes: il rifiuto `leftover_after` con `leftovers` (Task 3); il rifiuto `slot_taken` con `occupant` (`MealOut`, com'è oggi).

- [ ] **Step 1: I test che falliscono.**
  - `MealForm.test.tsx`:
    - «il posto occupato da un pasto con la ricetta fuori dal ricettario lo dice prima di Sostituisci»: `save` rifiuta con 409 `slot_taken` e `occupant.recipe = {in_book: false, …}` → si leggono «C'è già «Pizza» in questo posto.» e «La sua ricetta non è nel ricettario: si elimina con il pasto.», poi «Sostituisci» e «Annulla». Con `in_book: true`, o senza ricetta, la seconda frase non c'è.
    - «l'avanzo che verrebbe prima: la domanda e Sposta e stacca l'avanzo»: 409 `leftover_after`, `detail` «Martedì pranzo è un suo avanzo.», `leftovers: 1` → la frase, «Sposta e stacca l'avanzo» e «Annulla»; premuto il primo, `save` riceve lo stesso corpo con `detach_leftovers: true`. Con `leftovers: 2` il pulsante dice «Sposta e stacca gli avanzi».
    - «il posto occupato e poi l'avanzo: due domande in fila»: il primo invio dà `slot_taken`, «Sostituisci» dà `leftover_after`, «Sposta e stacca l'avanzo» manda `replace: true` e `detach_leftovers: true` insieme.
    - «con una domanda aperta i pulsanti del modulo non ci sono»: con la domanda di uno dei due casi aperta, il pulsante d'invio del modulo e il suo «Annulla» non ci sono, e c'è un «Annulla» solo; «Annulla» della domanda la chiude e i pulsanti tornano.
  - `MealScreen.test.tsx`: «un pasto fuori casa con la ricetta la tiene da parte»: `away: true` e `recipe` valorizzato → si legge «Fuori casa: non c'è niente da cucinare. La ricetta resta da parte: togliendo «Fuori casa» torna.», e non c'è la ricetta; «Elimina» di quel pasto dice «La sua ricetta non è nel ricettario: si elimina con il pasto.» (se `in_book` è falso). Senza ricetta resta la frase di oggi.
- [ ] **Step 2: Falliscono.** `npx vitest run src/features/meals`. Expected: FAIL.
- [ ] **Step 3: Il codice.** In `MealForm` lo stato `taken` diventa una domanda con il suo tipo (`slot_taken` con la frase dell'occupante e se la sua ricetta si elimina; `leftover_after` con la frase e quanti), sempre con il corpo rifiutato da rimandare; cambiare giorno o pasto la chiude, come oggi. La frase «La sua ricetta non è nel ricettario: si elimina con il pasto.» si mostra quando `occupant.recipe` c'è e `occupant.recipe.in_book` è falso (lo stesso criterio di `MealScreen` per «Elimina»). In `MealScreen`, `patchFrom` porta anche `detach_leftovers` quando il corpo lo ha e la patch ha un cambio; la ricetta si mostra solo se `!m.away`.
- [ ] **Step 4: Passano**, poi `npx vitest run`, `npm run typecheck`, `npm run lint`. Expected: verdi, puliti.
- [ ] **Step 5: Commit** — `pasti: «Sostituisci» dice prima della ricetta che si elimina; spostare prima di un avanzo chiede; il pasto fuori casa tiene la ricetta da parte`.

---

### Task 5: La ricetta di un avanzo è davvero in sola lettura (S3)

**Files:**
- Modify: `frontend/src/features/cooking/RecipeDetailScreen.tsx` (`IngredientRow` con la prop nuova `readOnly: boolean`; il punto dove si disegna `AddMissingButton`)
- Test: `frontend/src/features/cooking/RecipeDetailScreen.test.tsx`

- [ ] **Step 1: I test che falliscono.** «la ricetta di un avanzo non ha Sostituisci né Metti in lista»: `RecipeDetailView` con `meal={{ mealId, readOnly: true }}` e una ricetta con un ingrediente mancante → nessun pulsante «Sostituisci ‹ingrediente›», nessun «Metti in lista ciò che manca»; lo stepper delle porzioni c'è. Con `readOnly: false`, i pulsanti ci sono come oggi.
- [ ] **Step 2: Fallisce.** Expected: FAIL.
- [ ] **Step 3: Il codice.** `IngredientRow` riceve `readOnly`; con `readOnly` non disegna il pulsante «Sostituisci» né il `SubstitutePanel`. `AddMissingButton` si disegna solo se `!meal?.readOnly`. Il commento cita la spec §4.2 («in sola lettura e senza chat»).
- [ ] **Step 4: Passa**, poi `npx vitest run`, `npm run typecheck`, `npm run lint`. Expected: verdi.
- [ ] **Step 5: Commit** — `pasti: la ricetta di un avanzo non scrive niente (via «Sostituisci» e «Metti in lista ciò che manca»)`.

---

### Task 6: Un avviso vecchio della ricetta non ricompare (P4)

**Files:**
- Modify: `backend/app/services/meals.py` (`link_recipe`, `release_recipe`)
- Test: `backend/tests/services/test_meals.py`, `backend/tests/api/test_meals.py`

- [ ] **Step 1: I test che falliscono.** `test_dare_una_ricetta_azzera_l_avviso` (un pasto con `recipe_notice` = l'avviso del limite di frequenza; `link_recipe` → `recipe_notice is None`); `test_staccare_la_ricetta_azzera_l_avviso` (idem con `release_recipe`); e in API `test_l_avviso_vecchio_non_ricompare` (pasto con l'avviso, «Scrivi la ricetta» con `POST /api/v1/recipes` e `meal_id`, poi eliminazione della ricetta da `/ricette/:id`, poi `GET` del pasto: `recipe_state == "none"` e `recipe_notice` vuoto).
- [ ] **Step 2: Falliscono.** Expected: FAIL.
- [ ] **Step 3: Il codice.** `meal.recipe_notice = None` in tutte e due le funzioni, prima del `flush`.
- [ ] **Step 4: Passano**, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `fix(pasti): dare o staccare una ricetta azzera l'avviso della ricetta non arrivata`.

---

### Task 7: L'inversa ragiona per voce (P1)

**Files:**
- Modify: `backend/app/services/change_cards.py` (`propose_inverse_card`, `_inverse_pantry_row`, `apply_card`)
- Test: `backend/tests/services/test_inverse_cards.py`

**Interfaces:**
- Produces: `async def _inverse_pantry_group(session, sources: Sequence[ChangeCardRow]) -> dict[str, object] | None` al posto di `_inverse_pantry_row` (le righe d'origine di una voce, dalla più recente alla più vecchia, come le dà la query di oggi); la riga inversa ha `source_row_id` = la riga più vecchia e `source_row_ids` = tutte, come stringhe. Le righe di lista restano una per una (`source_row_ids = [source_row_id]`).

- [ ] **Step 1: I test che falliscono** (con il `mondo` dei test di oggi):
  - `test_due_schede_dello_stesso_pasto_che_si_annullano_sulla_voce`: il caso del rilievo. Scheda 1 applicata: spinaci disponibile → finito. Scheda 2 applicata: spinaci finito → disponibile, zucchine disponibile → finito. Eliminato il pasto: l'inversa **non ha** una riga per gli spinaci, e ha «zucchine → Disponibile» spuntata.
  - `test_due_schede_sulla_stessa_voce_rimettono_lo_stato_di_partenza`: scheda 1 spinaci disponibile → quasi finito, scheda 2 quasi finito → finito. Inversa: «spinaci → Disponibile», spuntata.
  - `test_una_voce_toccata_dopo_l_ultima_scheda_non_si_spunta`: come sopra, poi spinaci messi a mano a «Quasi finito» → la riga c'è, «→ Disponibile», non spuntata, con `CHANGED_NOTE`.
  - `test_applicare_l_inversa_segna_tutte_le_origini`: applicata l'inversa del secondo caso, le due righe d'origine hanno `reversed_at`.
  - `test_l_inversa_del_fuori_casa_applicata_non_si_ripropone_all_eliminazione`: due schede sugli spinaci, «fuori casa» → inversa applicata; poi il pasto torna a casa e si elimina: nessuna riga per gli spinaci.
  - `test_un_gruppo_che_serve_a_un_altro_pasto_si_salta`: la scheda 1 serve ai pasti A e B, la 2 al solo A; eliminato A (B ufficiale, a casa): nessuna riga per la voce.
  - I test di oggi di `test_inverse_cards.py` restano verdi senza cambiare.
- [ ] **Step 2: Falliscono.** Expected: FAIL (il primo propone «spinaci → Finito» spuntato).
- [ ] **Step 3: Il codice.** In `propose_inverse_card`, le righe d'origine di dispensa si raggruppano per `pantry_item_id` mantenendo l'ordine della query (dalla scheda applicata più di recente); per gruppo: si salta se una riga serve ancora a un altro pasto (la regola di oggi, riga per riga, sul gruppo intero), poi `_inverse_pantry_group` come nella decisione 8. In `apply_card`, gli id da bloccare `FOR UPDATE` sono l'unione di `source_row_id` e `source_row_ids` di tutte le righe, in ordine di id; una riga si salta con `REVERSED_NOTE` se una qualunque delle sue origini ha `reversed_at`; applicata, le segna tutte. Una riga inversa scritta prima della `0024` (`source_row_ids` vuoto) si comporta come oggi, col solo `source_row_id`. La docstring di `propose_inverse_card` dice la regola per voce.
- [ ] **Step 4: Passano**, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `fix(pasti): la scheda inversa rimette l'effetto netto del pasto su ogni voce, non riga per riga`.

---

### Task 8: L'inversa non toglie dalla lista ciò che serve a un altro pasto (P2)

**Files:**
- Modify: `backend/app/services/change_cards.py` (la regola «serve ancora a un altro pasto» per le righe di lista)
- Test: `backend/tests/services/test_inverse_cards.py`

**Interfaces:**
- Produces: `async def _list_still_needed(session, source: ChangeCardRow, meal_id: str) -> bool`: vero se la regola di oggi lo dice (un altro pasto della riga) **oppure** se esiste una riga di lista con lo stesso `ingredient_id` (non nullo) in un'altra scheda in avanti con stato `proposed` o `applied`, i cui `meal_ids` comprendono un pasto diverso da `meal_id`, ufficiale e non fuori casa. Le righe di dispensa continuano con la regola di oggi (Task 7).

- [ ] **Step 1: I test che falliscono.**
  - `test_l_inversa_non_toglie_dalla_lista_cio_che_serve_a_un_altro_pasto`, parametrizzato sulla scheda di B proposta o applicata: la scheda del pasto A mette «merluzzo» in lista (applicata, `list_added`); la scheda del pasto B, ufficiale, ha merluzzo «Già in lista.», non spuntato. Eliminato A: l'inversa non ha la riga «merluzzo → via dalla lista» (e se era l'unica riga, l'inversa non nasce).
  - `test_una_scheda_scartata_non_tiene_la_voce_in_lista`: la scheda di B è scartata → l'inversa toglie il merluzzo come oggi.
  - `test_un_pasto_bozza_non_tiene_la_voce_in_lista`: B è una bozza → come oggi.
- [ ] **Step 2: Falliscono.** Expected: FAIL.
- [ ] **Step 3: Il codice.** In `propose_inverse_card` le righe di lista usano `_list_still_needed`; la docstring della funzione, al punto «serve ancora a un altro pasto», aggiunge le schede degli altri pasti.
- [ ] **Step 4: Passano**, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `fix(pasti): la scheda inversa non toglie dalla lista una voce che serve a un altro pasto`.

---

### Task 9: Una scheda nuova di Claude mette da parte le vecchie (P3)

**Files:**
- Modify: `backend/app/services/change_cards.py` (`propose_card`, `_supersedes` nuova), `backend/app/services/meal_chat.py` (`_CARD_STATES`), `backend/app/schemas/change_card.py` (lo stato), `frontend/src/features/change-cards/ChangeCard.tsx`, `frontend/src/domain/types.ts`
- Test: `backend/tests/services/test_change_cards.py`, `backend/tests/services/test_planning.py`, `frontend/src/features/change-cards/ChangeCard.test.tsx`

**Interfaces:**
- Produces: `def _supersedes(old_meal_ids: Sequence[str], new_meal_ids: Sequence[str]) -> bool` — **la regola della decisione 10** (confermata da Mattia il 2026-11-21): `bool(old_meal_ids) and set(old_meal_ids) <= set(new_meal_ids)`. In `propose_card`, dopo aver creato la scheda nuova, ogni scheda `forward` e `proposed` diversa da lei per cui `_supersedes` è vero passa a `superseded`, con `discarded_at = now`. Lo schema della scheda ammette `"superseded"`; `_CARD_STATES["superseded"] = "sostituita"`.

- [ ] **Step 1: I test che falliscono.**
  - `test_change_cards.py`: `test_una_scheda_nuova_mette_da_parte_quella_vecchia_dello_stesso_pasto` (due `propose_card` per il pasto A: la prima è `superseded` con `discarded_at`, la seconda `proposed`); `test_la_scheda_della_settimana_mette_da_parte_quelle_dei_piatti` (vecchie {A} e {A,B}, nuova {A,B,C}: tutte e due messe da parte); `test_la_scheda_di_un_piatto_non_mette_da_parte_quella_della_settimana` (vecchia {A,B,C}, nuova {A}: la vecchia resta `proposed`); `test_non_tocca_le_applicate_ne_le_inverse`; `test_mette_da_parte_anche_una_scheda_compilata_a_mano` (una `create_empty_card` per A con una riga aggiunta: `superseded`); `test_una_scheda_messa_da_parte_non_si_applica` (`apply_card` → il rifiuto di oggi per le schede non proposte; le sue righe restano leggibili con `get_card`); `test_supersedes` (la funzione, sui tre casi).
  - `test_planning.py`: `test_la_pianificazione_si_conclude_dopo_una_scheda_sostituita` (proposta messa, scheda 1 proposta, scheda 2 per gli stessi pasti applicata → `planning_concluded` vero; prima di applicare la 2, falso).
  - `ChangeCard.test.tsx`: «una scheda sostituita lo dice, e non si applica»: `status: "superseded"` → «Sostituita da una scheda più nuova.», nessun «Applica».
- [ ] **Step 2: Falliscono.** Expected: FAIL.
- [ ] **Step 3: Il codice**, come nelle Interfaces. Nel frontend `status` ammette `"superseded"` e `ChangeCard` mostra la frase accanto ad «Applicata.» e «Scartata.». La regola di `_supersedes` ha sopra un commento: «"Lo stesso pasto" per una scheda di più pasti: tutti i suoi pasti sono nella nuova (Mattia, 2026-11-21; piano 2026-11-18-pasti-correzioni, decisione 10).».
- [ ] **Step 4: Passano**, backend e frontend; `npm run typecheck && npm run lint`. Expected: PASS, puliti.
- [ ] **Step 5: Commit** — `fix(pasti): una scheda nuova di Claude mette da parte le vecchie non applicate degli stessi pasti`.

---

### Task 10: Il fuoco e le etichette degli utensili (U1, U2)

**Files:**
- Modify: `frontend/src/features/utensils/UtensilRow.tsx`, `frontend/src/features/utensils/UtensilsScreen.tsx`, `frontend/e2e/utensili.spec.ts` (in `aggiungi`, `getByLabel("Nota", { exact: true })` diventa `getByLabel("Nota del nuovo utensile", { exact: true })`)
- Test: `frontend/src/features/utensils/UtensilsScreen.test.tsx`

- [ ] **Step 1: I test che falliscono.**
  - «Correggi porta il fuoco su Nome»: premuto «Correggi «Frusta»», il campo «Nome» della riga ha il fuoco.
  - «chiudere la correzione riporta il fuoco su Correggi»: dopo «Annulla», e dopo un «Salva» riuscito, il fuoco è su «Correggi «‹nome›»» di quella riga.
  - «con una riga in correzione c'è un campo Nota solo»: `getAllByLabelText("Nota", { exact: true })` ha un elemento, e c'è «Nota del nuovo utensile».
  - I due test di oggi che scrivono la nota dell'aggiunta (`getByLabelText("Nota")`) usano «Nota del nuovo utensile»: è il cambio permesso.
- [ ] **Step 2: Falliscono.** Expected: FAIL.
- [ ] **Step 3: Il codice.** In `UtensilsScreen` l'etichetta del campo della nota dell'aggiunta è «Nota del nuovo utensile». In `UtensilRow`, un `ref` sul campo «Nome» che prende il fuoco quando la correzione si apre, e un `ref` su «Correggi» che lo riprende quando si chiude (un effetto sul passaggio di `editing` da vero a falso; non al primo montaggio).
- [ ] **Step 4: Passano**, poi `npx vitest run`, `npm run typecheck`, `npm run lint`. Expected: verdi.
- [ ] **Step 5: Commit** — `utensili: il fuoco su «Nome» aprendo «Correggi» e di nuovo su «Correggi» chiudendo; «Nota del nuovo utensile»`.

---

### Task 11: Nel browser vero, a 375 px, nei due temi

**Files:**
- Modify: `frontend/e2e/pasti.spec.ts` (prove in fondo), `frontend/e2e/style.spec.ts` (una prova **in fondo al file**)

- [ ] **Step 1: Le prove funzionali**, in fondo a `pasti.spec.ts` (375×812, accesso come nelle altre prove, posti lontani da quelli delle altre prove, piatti che cominciano per «e2e-corr»; nel `finally` si eliminano i pasti creati):
  1. **«spostare un pasto dopo il suo avanzo chiede, e lo stacca»**: con `page.request`, «e2e-corr Lasagne» a cena fra 30 giorni e il suo avanzo a pranzo il giorno dopo. Su `/pasti/<lasagne>`, «Correggi», il giorno a +32, «Salva»: si legge «‹Giorno› pranzo è un suo avanzo.», c'è un «Annulla» solo, e «Sposta e stacca l'avanzo». Premuto: la settimana di +32 ha «e2e-corr Lasagne», e il pasto del giorno +31 non dice più «Avanzo di».
  2. **«fuori casa tiene la ricetta da parte»**: un pasto ufficiale «e2e-corr Frittata» con la sua ricetta (`POST /api/v1/recipes` con `meal_id`). Spuntato «Fuori casa» e salvato: si legge «Fuori casa: non c'è niente da cucinare. La ricetta resta da parte: togliendo «Fuori casa» torna.». Tolta la spunta: la ricetta c'è di nuovo, e c'è «Chat con Claude» (con l'avviso che la chiave manca: lo stack e2e non l'ha).
  3. **«Sostituisci dice della ricetta dell'occupante»**: su un posto occupato da un pasto con ricetta fuori dal ricettario, un pasto nuovo sullo stesso posto mostra «La sua ricetta non è nel ricettario: si elimina con il pasto.» prima di «Sostituisci».
- [ ] **Step 2: La prova di stile**, in fondo a `style.spec.ts`: **«la domanda dell'avanzo a 375 px, nei due temi»**: lo stato della prova 1 prima di rispondere; per `"light"` e `"dark"`, `fermo`, `testiIlleggibili(page)` è `[]`, `scrollWidth <= clientWidth`, «Sposta e stacca l'avanzo» e «Annulla» visibili e alti almeno 44 px. Nel `finally`, i pasti si eliminano.
- [ ] **Step 3: Typecheck e lint**, `npm run typecheck && npm run lint`. Expected: puliti.
- [ ] **Step 4: L'e2e intera** su uno stack ricreato da zero, con i comandi delle Global Constraints. Expected: tutto verde, `N_e2e` + 4. **Annota** `N_e2e`. Poi `down -v` e `rm .env`, sempre. Un testo illeggibile si corregge con un altro token esistente, mai con uno nuovo; se nessuno basta, `bloccato` con la misura.
- [ ] **Step 5: Commit** — `pasti: nel browser vero — l'avanzo che chiede, il fuori casa con la ricetta da parte, «Sostituisci» che avvisa; il contrasto nei due temi a 375 px`.

---

### Task 12: I documenti, la verifica finale e il report

**Files:**
- Modify: `docs/superpowers/specs/2026-11-12-pasti-claude-design.md`, `next-steps.md`
- Create o modify: `docs/night-reports/<data di oggi>.md`

- [ ] **Step 1: La spec.** In §4.1, al punto **fuori casa**, aggiungi: «Un pasto che va fuori casa tiene la sua ricetta, nascosta: togliendo il segno torna (deciso da Mattia il 2026-11-18).». In §4.2, al punto dell'**avanzo**, aggiungi: «Spostare un pasto dopo un suo avanzo si chiede: «Sposta e stacca l'avanzo» lo lascia come pasto a mano (deciso da Mattia il 2026-11-18).». In §6.2, al punto della scheda inversa, aggiungi: «La scheda inversa ragiona per voce (l'effetto netto delle schede del pasto) e non toglie dalla lista ciò che serve a un altro pasto. Una scheda nuova di Claude per gli stessi pasti mette da parte quelle non ancora applicate (deciso da Mattia il 2026-11-18).».
- [ ] **Step 2: `next-steps.md`.**
  1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte: le correzioni dei Pasti)_`.
  2. La voce di questo piano diventa `fatto <data di oggi>` con ` → branch night/pasti-correzioni (da revisionare)`, in cima a «Fatti (recenti)».
  3. Le righe `[idea]` che questo piano chiude passano a `fatto <data di oggi>`, ognuna con « — risolta col piano `2026-11-18-pasti-correzioni.md` → branch night/pasti-correzioni (da revisionare)», e vanno in «Fatti (recenti)» (cercale per il testo, non per numero di riga):
     - «Pasti: spostare un pasto d'origine dopo il suo avanzo lascia l'avanzo legato a un pasto successivo» (S2);
     - «Pasti: «Fuori casa» e «Sostituisci» archiviano in silenzio una ricetta fuori dal ricettario (avvisa solo «Elimina»)» (S1);
     - «Pasti: la ricetta in sola lettura di un avanzo mostra ancora «Metti in lista ciò che manca», lo stepper delle porzioni e i sostituti» (S3; lo stepper resta di proposito, decisione 7: scrivilo nella riga);
     - «Pasti: due «Annulla» affiancati nell'avviso del posto occupato (quello del modulo e quello dell'avviso)» (decisione 6);
     - «Chiudendo il modulo di correzione di un utensile il fuoco resta sul corpo della pagina; farlo tornare su «Correggi»» (U1).
  4. Nessuna voce nuova per la regola di P3: Mattia l'ha confermata il 2026-11-21 (decisione 10).
  5. Quel che è emerso fuori da questo piano va come `idea` o `tbd`, con `[Parte IV]`.
- [ ] **Step 3: La verifica finale.** I «Comandi di verifica» con i loro attesi; vitest circa **`N_vitest` + 12**, pytest circa **`N_pytest` + 45**. Se i numeri differiscono, scrivi nel report da dove viene la differenza. L'e2e del Task 11 vale se dopo non è cambiato codice; se è cambiato, rifalla. Infine `docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_pasti_correzioni WITH (FORCE)'`.
- [ ] **Step 4: Il report**, `docs/night-reports/<data di oggi>.md` sul ramo (in fondo, se c'è già: la notte del piano della chiave API scrive nello stesso file). Dentro: il ramo e `BASE`; i conti veri contro la Preparazione; la `0024`; le decisioni 4–12 che Mattia può voler rivedere, la regola di P3 (decisione 10, confermata il 2026-11-21), poi la ricetta nascosta del pasto fuori casa, i due avanzi, lo stepper che resta nella sola lettura; le idee vicine lasciate fuori (la scheda inversa del «fuori casa» che resta proposta al ritorno a casa; la conferma di «Metti nella settimana» sui posti occupati); la sezione «Dopo il deploy (solo Mattia)» qui sotto. Niente push, niente merge, niente deploy.
  ```bash
  git add docs/ next-steps.md
  git commit -m "docs: le correzioni dei Pasti nella spec, in next-steps e nel report"
  ```

---

## Dopo il deploy (solo Mattia)

La notte non tocca la produzione. Questo ramo si unisce su `master` dopo `night/pasti-chiave-api`; il deploy è quello del piano della chiave API («Dopo il deploy» di `docs/superpowers/plans/2026-11-18-pasti-chiave-api.md`), e la `0024` gira all'avvio insieme alle altre.

1. **La regola di P3**: leggi la decisione 10 e conferma, o di' l'altra regola (basta cambiare `_supersedes`).
2. **Sul telefono**: una cena con la sua ricetta va «Fuori casa» e torna; la ricetta torna con la chat. Un pasto spostato dopo il suo avanzo chiede, con un «Annulla» solo. La ricetta di un avanzo non ha «Sostituisci» né «Metti in lista ciò che manca». In «Utensili», «Correggi» apre la tastiera sul nome.
3. **Le schede**: nella pianificazione, chiedi a Claude di rifare la scheda dei cambi; quella vecchia dice «Sostituita da una scheda più nuova.» e «Pianifica con Claude» non riapre più quella conversazione dopo aver applicato la nuova.
