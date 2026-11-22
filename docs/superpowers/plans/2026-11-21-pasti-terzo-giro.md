# Pasti con Claude: il terzo giro di correzioni — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** chiudere le idee dei Pasti rimaste in `next-steps.md` dopo i due piani del 2026-11-18 (gli avanzi fuori dalla finestra, le inverse del «fuori casa» e dei pasti passati, la lista che segue lo stato corretto in una scheda, il lucchetto sul pasto, la ricetta di un pasto eliminata dal ricettario, i ritocchi della settimana, del pasto e della pianificazione, la regola degli utensili nei prompt dei Pasti), con le quattro decisioni di Mattia del 2026-11-21.

**Architecture:** correzioni dentro i servizi che ci sono. Una regola pura nuova per la finestra dell'avanzo (`in_leftover_window`), usata dal modulo e dalla scrittura; un rifiuto nuovo con la sua via d'uscita per l'avanzo spostato, sul modello di `leftover_after`. Le righe di lista di una scheda ricordano da quali righe di dispensa vengono (colonna nuova, migrazione `0026`), e all'applicazione seguono lo stato corretto. Un `SELECT … FOR UPDATE` sul pasto in ogni scrittura della sua ricetta. Nel frontend: il modulo del pasto, il pasto, la settimana, la proposta della pianificazione, l'eliminazione dal ricettario.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Alembic, pytest su Postgres vero; React 19, TypeScript, Tailwind 4, TanStack Query, Vitest, Playwright. Nessuna chiamata a Claude.

**Spec:** `docs/superpowers/specs/2026-11-12-pasti-claude-design.md` (§4.2, §5.1, §5.2, §6.2, §8). La catena da cui parte: `docs/superpowers/plans/2026-11-18-pasti-chiave-api.md` (nonno) e `docs/superpowers/plans/2026-11-18-pasti-correzioni.md` (padre): **leggili tutti e due** prima di cominciare, perché questo piano cambia codice che loro hanno appena cambiato. Leggi `CLAUDE.md` del repo: le sette lezioni valgono tutte, la quinta («una correzione che chiude un buco non lascia un vicolo cieco») soprattutto.

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/pasti-terzo-giro`, ramo `night/pasti-terzo-giro`, creato da **`night/s4-candidati`** (che viene da `night/llm-haiku` ← `night/pasti-correzioni` ← `night/pasti-chiave-api` ← `master`). Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì, mai dalla radice del checkout principale, che non si tocca. **Nessun push, nessun merge, nessun deploy. Mai `git stash`. Niente letture o scritture sulla produzione, e mai il `.env` del checkout principale. Nessuna chiamata vera a Claude.**
- **Il piano è scritto contro `master` (4537139) più ciò che i due piani del 2026-11-18 dicono di produrre.** Leggi ogni file com'è sul ramo prima di cambiarlo: le righe citate sono indicative, le ancore sono le funzioni. **Se un nome sul ramo è diverso, vale il codice: usalo e scrivilo nel report.** In particolare:
  - dal piano della chiave API: `write_meal_recipe(..., expected: MealSnapshot | None = None)`, `STALE_WRITE_MESSAGE`, `TurnContext.seen`, `undoable_change_ids`, `change_is_undoable` (che passa da lì), `RecipeChange.created_ingredient_ids`, `undo_recipe_change`;
  - dal piano delle correzioni: `place_words`, `WEEKDAY_NAMES`, `SLOT_WORDS` (`app.domain.meals`), `MealRefusalCode.LEFTOVER_AFTER`, `MealRefusal.leftovers`, `update_meal(..., replace=False, detach_leftovers=False)`, `MealUpdate.detach_leftovers`, `_inverse_pantry_group`, `_list_still_needed`, `ChangeCardRow.source_row_ids`, `CardStatus.SUPERSEDED`, `_supersedes`; nel frontend la «domanda» di `MealForm` con il suo tipo (`slot_taken`, `leftover_after`) e `patchFrom` che porta `detach_leftovers`;
  - dal piano di `llm-haiku`: solo `backend/app/services/utensils.py` può essere cambiato da lui (la regola degli utensili per bozza e variante). Leggilo sul ramo: se ha già un modo per cambiare l'ultima frase della regola, usa quello per i Pasti (Task 10) invece di aggiungerne un altro.
  - Gli altri nomi, da `master`: `_check_leftover`, `_bad_leftover`, `MealRefusalCode.BAD_LEFTOVER`, `release_recipe`, `link_recipe`, `check_can_take_recipe`, `copy_recipe_to_meal`, `delete_meal`, `create_meal` (`app.services.meals`); `is_before`, `LEFTOVER_WINDOW_DAYS` (`app.domain.meals`); `leftover_candidates`, `get_meal`, `_select`, `_LOADS` (`app.repositories.meals`); `propose_card`, `apply_card`, `add_row`, `propose_inverse_card`, `_discard_proposed_inverses`, `InverseReason`, `_label` (`app.services.change_cards`); `adds_to_list` (`app.domain.change_cards`); `place_proposal`, `propose_meals`, `planning_to_reopen`, `planning_concluded`, `PlanningRefusalCode.PAST` (`app.services.planning`); `latest_planning` (`app.repositories.conversations`); `meal_out`, `_meals_out` (`app.api.meals`, `app.api.planning`); `today_in_pantry` (`app.domain.rules`); `day_name` (`app.services.claude.prompts`); `utensils_prompt_block`, `render_utensils_block`, `UTENSILS_PROMPT_RULE` (`app.services.utensils`); nel frontend `MealForm`, `MealScreen`, `WeekScreen`, `RecipeDetailView`, `useArchiveRecipe`, `PlanningScreen`, `ProposalCard`, `useChatSender`, `refusalOf`, `DishChat`, `Alert`.
- **Le due decisioni fondanti** restano intere: niente quantità in dispensa (le schede cambiano solo i tre stati), e le ricette puntano solo a ingredienti alimentari attraverso l'imbuto.
- **Mai un vicolo cieco.** Ogni rifiuto nuovo ha la sua strada a video: l'avanzo spostato ha «Sposta e stacca dal pasto d'origine»; la proposta con un giorno passato resta visibile con la frase che dice cosa fare; una ricetta del pasto «eliminata» dal ricettario ha «Annulla».
- **Il frontend non calcola logica di dominio**: quale avanzo esce dalla finestra, se un pasto è passato, se una riga di lista segue la dispensa, se una ricetta si toglie dal ricettario invece di archiviarsi, tutto nel backend. Il frontend sceglie solo che cosa mostrare di quello che riceve.
- **Colore e primitive**: solo token di `frontend/src/index.css`, **nessun token nuovo**; `grep -rn "emerald\|neutral-" frontend/src` resta vuoto; ogni testo sopra 4,5:1 nei due temi (misurato da `frontend/e2e/style.spec.ts`); primitive da `frontend/src/components/ui/`, `Button` e `Alert` non cambiano; bersagli alti almeno 44 px; a 375 px niente scorre di lato.
- Le parole a video e nei prompt sono in italiano e **si copiano esatte** da questo piano (fra «»; ‹…› è un valore). Gli identificatori in inglese, i commenti in italiano.
- **Il type check è `npm run typecheck`**, mai `tsc --noEmit`. Controlli del frontend, da `<worktree>/frontend`: `npx vitest run`, `npm run typecheck`, `npm run lint`, `npm run build`. Nei test dei componenti si usa `createTestQueryClient`.
- **Backend su Postgres vero**: `spena-db-1` (porta 5433), con il database di questo ramo, `spena_test_pasti_terzo_giro`. Mai `docker compose up` dal worktree, mai `-f docker-compose.prod.yml`. Si usa il `.venv` del checkout principale. Il comando di pytest, da `<worktree>/backend`:
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_pasti_terzo_giro \
    PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
- **e2e** sullo stack `spena-e2e`, con gli stessi comandi del piano padre (Global Constraints di `2026-11-18-pasti-correzioni.md`: `.env` da `.env.example` e cancellato alla fine, `-p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml` in ogni comando, il seme con le ricette e le due righe della fixture CIQUAL, `down -v` e `rm .env` sempre; se lo stack c'è e non l'hai alzato tu, aspetta che sparisca).
- **Nessuna dipendenza nuova.** **Una migrazione sola, la `0026`** (`backend/alembic/versions/0026_righe_lista_dalla_dispensa.py`, `revision = "0026"`, `down_revision` = la testa che `alembic heads` dà sul ramo nella Preparazione; attesa `0025`).
- **Il tempo non si legge dall'orologio nei servizi nuovi.** Le due regole che dipendono da «oggi» (la proposta con un giorno passato, l'inversa di un pasto passato) ricevono `today: date | None = None`, e `None` vuol dire «nessun controllo»: le passano le rotte con `today_in_pantry(...)`. Così i test di oggi, che usano date fisse di novembre 2026 ormai passate (`test_planning.py`, `test_double_tap.py`, `test_inverse_cards.py`, `api/test_change_cards.py`), non cambiano significato; i test nuovi passano `today` o usano le rotte con date relative a `today_in_pantry()`.
- **I test di oggi si cambiano solo dove il piano lo dice**: i test che fissano la frase vecchia di `bad_leftover` (Task 1); i test che spostano un avanzo con `update_meal` o con la `PATCH` e si aspettano `bad_leftover` (diventa `origin_out_of_reach`, Task 1); il confronto col blocco degli utensili in `test_meal_chat_turn.py` (Task 10). Nessun altro. Se cade altro, è un comportamento cambiato: si corregge il codice.

### Preparazione (una volta, prima del Task 1)

- [ ] **Il ramo di partenza e quello che deve avere.**
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify night/s4-candidati
  git ls-tree -r --name-only night/s4-candidati -- backend/alembic/versions | grep -E '002[3-6]_'
  git show night/s4-candidati:backend/app/services/meals.py | grep -c 'LEFTOVER_AFTER'
  git show night/s4-candidati:backend/app/services/meal_recipes.py | grep -c 'def undoable_change_ids'
  git show night/s4-candidati:backend/app/db/models/change_card.py | grep -c 'source_row_ids'
  ls .worktrees/pasti-terzo-giro 2>&1 | head -1
  ```
  Expected: un hash (**annotalo**: è `BASE` del Task 12); tre file, la `0023`, la `0024` e la `0025`, e nessuna `0026`; poi `1` o più, tre volte; `No such file or directory`. **Se il ramo non c'è, se manca una delle tre migrazioni o uno dei tre segni**, non creare niente: fermati e scrivi nel messaggio finale della notte quale piano della catena manca. Se un report della catena (`docs/night-reports/` sul ramo) dice un task `bloccato`, leggi quale: questo piano consuma S2 e S1 (Task 3 e 4 del padre), P1 (Task 7 del padre), C1 e C7 (Task 6 e 9 del nonno); se uno di questi è bloccato, fermati allo stesso modo. Se il worktree esiste già, fermati e scrivilo.
- [ ] **Il database dei test di questo ramo**:
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_pasti_terzo_giro WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_pasti_terzo_giro'
  ```
- [ ] `cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund`.
- [ ] **Il worktree**, con `node_modules` collegato e nessun `.env`:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/pasti-terzo-giro -b night/pasti-terzo-giro night/s4-candidati
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/pasti-terzo-giro/frontend/node_modules
  ```
- [ ] **La testa di Alembic**, da `<worktree>/backend`: `DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_pasti_terzo_giro PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" alembic heads`. Expected: una riga sola. **Annotala**: è il `down_revision` della `0026` (atteso `0025`). Due teste: fermati, va nel report.
- [ ] **La voce del backlog.** In `next-steps.md` la voce che cita questo piano (`2026-11-21-pasti-terzo-giro.md`) passa a `in corso`, con in coda ` → in corso su night/pasti-terzo-giro`. Commit: `git commit -m "next-steps: il terzo giro dei Pasti, in corso"`. Se la voce non c'è, aggiungila sotto «In corso» nello stile delle altre, con `[Parte IV]`.
- [ ] **La linea di partenza**: vitest e pytest dal worktree, tutto verde. **Annota** `N_file`, `N_vitest` e `N_pytest`. Se non è verde, fermati: va nel report.

---

## Obiettivo e contesto

La catena «Pasti con Claude» non è mai andata in produzione. I due piani del 2026-11-18 chiudono la chat (C1–C7) e la prima revisione della settimana e delle schede (S1–S3, P1–P4, U1–U2). Restano diciotto idee in «Da approfondire», verificate su `master` dalla fase giorno del 2026-11-21: due difetti veri sugli avanzi (la finestra dei 3 giorni che la scrittura non controlla, l'avanzo spostato che dà un rifiuto senza uscita), uno sulle schede (correggere «Finito» ↔ «Quasi finito» non sposta la riga della lista), una corsa fra la coda delle ricette e il salvataggio a mano, una ricetta del ricettario che, eliminata, lascia il suo pasto su una lapide, e una serie di ritocchi. Mattia ne ha decise quattro; le altre hanno una correzione sola che regge.

## Decisioni prese

Di Mattia (2026-11-21):

1. **Gli avanzi (idee 33 e 35).** Anche la scrittura controlla la finestra: un avanzo viene da un pasto cucinato **prima** del suo posto e **non più di 3 giorni** prima (`LEFTOVER_WINDOW_DAYS`). Un avanzo spostato fuori ordine o fuori finestra ha la stessa via d'uscita di S2: «Sposta e stacca dal pasto d'origine» (diventa un pasto a mano, con il suo piatto) oppure «Annulla». Spostare il pasto d'origine più di 3 giorni prima di un suo avanzo è coperto allargando il rifiuto `leftover_after` di S2, con la stessa uscita («Sposta e stacca l'avanzo»). Il legame **non** diventa modificabile da «Correggi».
2. **«Elimina» dal ricettario (idea 38).** Su una ricetta che ha un pasto, «Elimina» la toglie dal ricettario (`in_book` falso), con «Annulla», e il pasto la tiene. Resta vera l'invariante «una ricetta viva fuori dal ricettario ha sempre un pasto».
3. **Le inverse (idee 44 e 50).** Quando un pasto torna a casa, la sua scheda inversa del «fuori casa» ancora proposta si scarta da sola. Eliminare un pasto passato propone ancora l'inversa, ma con tutte le righe senza spunta e una nota.
4. **La lista che segue la dispensa (idea 49).** All'applicazione, una riga di lista che c'è solo per via di una riga di dispensa si salta quando quella riga non diventa più `finished`, e si aggiunge quando lo diventa. Resta la regola del barattolo avviato (solo `finished` porta in lista), e `add_item` resta l'unica regola contro i doppioni.

Del piano (Claude, delegate da Mattia: tecniche ed estetiche; Mattia le rivede nel report):

5. **I due rifiuti dell'avanzo nel dettaglio.** Il rifiuto nuovo ha il codice `origin_out_of_reach` (409) e la frase «Qui non può essere l'avanzo di «‹Lasagne›» (‹lunedì cena›): un avanzo viene dopo il suo pasto, entro 3 giorni.» (il posto con `place_words`: l'origine sta al massimo 3 giorni prima della posizione di adesso, quindi il giorno della settimana basta, come in S2). Con `detach_origin: true` nel corpo, lo spostamento riesce e il pasto perde `leftover_of_id`. Come S2, questo controllo viene **dopo** quello del posto occupato: prima la domanda del posto, poi quella dell'avanzo. Un avanzo che nello stesso cambio va fuori casa non chiede niente (il legame si toglie già). Per `create_meal` resta `bad_leftover`, con la frase nuova «Un avanzo viene da un pasto cucinato nei 3 giorni prima, che non sia a sua volta un avanzo.». `leftover_after` (S2) tiene frase, codice e campo `leftovers`; cambia solo quali avanzi conta: quelli per cui il posto nuovo dell'origine non è più nella finestra.
6. **Il lucchetto (idee 52 e 42).** `lock_meal` (`SELECT … FOR UPDATE` sulla riga del pasto) è la prima istruzione di `write_meal_recipe`, `link_recipe` e `undo_recipe_change`. Il controllo «scrive solo una ricetta nuova» dei giri della coda (`create_only`) passa dentro `write_meal_recipe`, sotto il lucchetto (`allowed_recipe_ids`); lo strumento non lo ripete. La rotta di «Annulla» prende il lucchetto **prima** di guardare se Claude sta rispondendo: con il lucchetto e l'istantanea di C1, l'idea 42 è chiusa.
7. **«Ricetta in preparazione» (idea 51).** Sotto la frase di oggi ci sono «Scrivi la ricetta» e «Scegli dal ricettario», con «Puoi anche scriverla tu: quella di Claude allora non arriva.». È vero grazie alla decisione 6: la coda non riscrive una ricetta che c'è già.
8. **La proposta con un giorno passato (idea 45).** «Metti nella settimana» la rifiuta con il codice di oggi `proposal_past` e «Questa proposta ha un giorno già passato (‹giovedì 12 novembre›): chiedi a Claude di rifarla.» (il primo giorno passato, con `day_name`). La proposta resta aperta e visibile, con la frase sotto.
9. **Un avviso solo (idea 46).** Quando la pianificazione o la chat del piatto dicono già, in testa, che Claude non è collegato, il rifiuto dell'invio con lo stesso testo non si ripete (`shownRefusal`).
10. **La conferma che sopravvive (idea 47).** Lo stato di «Metti nella settimana» (gli occupanti da confermare e l'errore) sta in `PlanningScreen`, per id della proposta, e non dentro `ProposalCard`: quando la risposta di Claude si salva e la proposta si ridisegna in un altro messaggio, la conferma resta.
11. **La ricetta dell'occupante (idea nuova, il seguito di S1).** La conferma «Questi posti sono occupati» dice, sotto ogni occupante con una ricetta fuori dal ricettario, «La sua ricetta non è nel ricettario: si elimina con il pasto.», come «Sostituisci» del modulo dopo S1. Stesso criterio: `recipe` c'è e `recipe.in_book` è falso.
12. **La conversazione vuota (idea 48).** `planning_to_reopen` salta le conversazioni senza messaggi quando cerca «la più recente»; una conversazione vuota si riapre solo se non c'è nient'altro da riaprire (così non se ne crea una nuova a ogni tocco).
13. **Ritocchi.** `/pasti?settimana=<non valida>`: lo stato d'errore ha anche «Torna a oggi» (idea 36). L'avviso della ricetta non arrivata ha il tono dell'AI, `Alert tone="degraded"` (idea 55). Ripristinare dalla lapide nella modalità pasto rinfresca anche `["meals"]` (idea 39). Un solo `meals_out` in `app.api.meals`, usato anche da `app.api.planning` (idea 53).
14. **Gli utensili nei Pasti (H4, lato Pasti).** L'ultima frase della regola dice dove dirlo: nella coda delle ricette «se senza quello strumento il piatto non si fa, scrivilo al primo passo del procedimento: della tua risposta resta solo la ricetta.»; nella chat del piatto «se senza quello strumento il piatto non si fa, dillo a Mattia nella risposta.». La bozza, la variante e la pianificazione restano come sono (bozza e variante sono del piano `llm-haiku`; `ai_recipes.py` non si tocca).
15. **La lista che segue la dispensa nel dettaglio.** Una riga di lista ricorda, in `from_pantry_row_ids`, le righe di dispensa della stessa scheda che l'hanno portata; è vuota se la riga sta in piedi da sola (chiesta da Claude, aggiunta a mano, o scritta prima della `0026`). All'applicazione, dopo le correzioni: una riga che ha origini e nessuna di esse ha più `to_status == finished` si salta, con «Non va in lista: nella scheda la voce non diventa più «Finito».»; una riga di dispensa spuntata che va a `finished`, la cui voce adesso non è `finished`, e per il cui ingrediente la scheda non ha nessuna riga di lista, ne aggiunge una (spuntata, con «In lista perché nella scheda la voce diventa «Finito».»), applicata con `add_item` come le altre. La spunta della riga di dispensa non entra nel salto (una riga di dispensa non spuntata con `finished` lascia la sua riga di lista com'è oggi): è la lettura letterale della decisione 4.
16. **Il pasto passato nel dettaglio.** Vale per l'eliminazione (`InverseReason.DELETED`) di un pasto con `day < today`; la sostituzione e il «fuori casa» di un pasto passato restano come oggi (rimettere ha senso: quel pasto non si è mangiato). La nota «Pasto già passato: rimettila solo se non l'hai mangiato.» va sulle righe che non ne hanno già una (`CHANGED_NOTE` e `IN_CART_NOTE` restano, più precise).
17. **38 nel dettaglio.** Lo decide il backend: `PATCH /recipes/{id}` con `archived: true` su una ricetta che ha un pasto e sta nel ricettario mette `in_book = False` e non archivia; su una che ha un pasto ed è già fuori dal ricettario risponde 409 «È la ricetta di un pasto: si elimina insieme al pasto.». A video, «Tolta dal ricettario: resta la ricetta di «‹Frittata›».», con «Annulla» che la rimette nel ricettario.

## Criteri di accettazione

- [ ] Nessun avanzo può stare prima del suo pasto o più di 3 giorni dopo, né per la scrittura né per il modulo; spostarlo fuori chiede, e «Sposta e stacca dal pasto d'origine» lo fa; spostare l'origine troppo indietro chiede con «Sposta e stacca l'avanzo».
- [ ] Tornando a casa, l'inversa del «fuori casa» non è più fra le schede da applicare; eliminando un pasto passato, l'inversa ha tutte le righe senza spunta, con la nota.
- [ ] In una scheda, «Finito» → «Quasi finito» non mette la voce in lista, «Quasi finito» → «Finito» la mette, e niente si duplica.
- [ ] La coda e un salvataggio a mano sullo stesso pasto non fanno mai due ricette; «Annulla» e la scrittura di Claude non si sovrappongono.
- [ ] «Elimina» dal ricettario su una ricetta di un pasto la toglie dal ricettario, con «Annulla»; il pasto la mostra ancora.
- [ ] La settimana non valida ha «Torna a oggi»; il pasto in preparazione ha i due pulsanti; l'avviso della ricetta ha il tono dell'AI; la pianificazione mostra un avviso solo, una proposta passata resta con la sua frase, la conferma dei posti sopravvive e dice della ricetta che si elimina.
- [ ] La `0026` sale e scende. Tutti i test di oggi passano, cambiati solo dove il piano lo dice. L'e2e intera è verde, con le prove nuove.

## Comandi di verifica

Da `<worktree>/backend`: il comando di pytest. Da `<worktree>/frontend`: `npx vitest run`, `npm run typecheck`, `npx tsc -b --force`, `npm run lint`, `npm run build`. Dalla radice di `<worktree>`:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -rn "_meals_out" backend/app
grep -rn "ctx.create_only" backend/app/services/claude/tools.py
git diff night/s4-candidati --stat -- backend/alembic/versions
git diff night/s4-candidati --stat -- backend/app/services/ai_recipes.py
```

Expected: il primo vuoto; il secondo vuoto (resta `meals_out`); il terzo una riga sola, quella che passa `allowed_recipe_ids` a `write_meal_recipe`; il quarto un file solo, `0026_righe_lista_dalla_dispensa.py`; l'ultimo vuoto. Poi l'e2e intera.

## Review Focus

1. **Due voci di dispensa dello stesso ingrediente** (due barattoli di passata), tutte e due «Finito» nella scheda, una corretta a «Quasi finito»: la riga della lista resta, perché l'altra la porta ancora (Task 4, `test_due_voci_dello_stesso_ingrediente_una_resta_finita`).
2. **Una riga di lista chiesta da Claude e portata anche da una voce finita**: correggere la voce a «Quasi finito» non la toglie, perché sta in piedi da sola (Task 4, `test_una_riga_chiesta_da_claude_resta_anche_se_la_voce_non_finisce`).
3. **La coda scrive mentre Mattia salva «Scrivi la ricetta»**: una ricetta sola legata al pasto, nessuna ricetta viva fuori dal ricettario senza pasto (Task 5, `test_la_coda_non_riscrive_una_ricetta_scritta_a_mano_nel_frattempo` e, in API, `test_scrivi_la_ricetta_dopo_la_coda_non_lascia_orfane`).
4. **Un avanzo spostato su un posto occupato e fuori dalla finestra**: prima «Sostituisci», poi «Sposta e stacca dal pasto d'origine», che manda `replace` e `detach_origin` insieme (Task 2, «il posto occupato e poi l'origine: due domande in fila»).
5. **«Elimina» dal ricettario, poi il pasto eliminato**: la ricetta, ormai fuori dal ricettario, si archivia col pasto, e nessuna ricetta viva resta senza pasto (Task 7, `test_tolta_dal_ricettario_si_archivia_col_pasto`).

## Fuori scope

- Le idee 41 (il token finto nella storia del commit `3df53ee`: lo decide Mattia al momento del push) e 54 (il tempo massimo della pianificazione: si aspettano i primi usi veri). L'idea 43 si toglie dal backlog: funziona come voluto (la chat si rilegge e mostra lo stato vero).
- La regola degli utensili per la bozza e la variante (`ai_recipes.py`, riga H4 di `next-steps.md`): piano `llm-haiku`.
- Rendere il legame dell'avanzo modificabile da «Correggi» (deciso da Mattia: no).
- Cambiare la finestra dell'avanzo (resta 3 giorni) o la regola del barattolo avviato.
- Mostrare prima dell'applicazione che una riga di lista verrà saltata o aggiunta: la scheda lo dice, applicata, con le note.
- Riproporre una scheda in avanti quando un pasto torna a casa dopo un'inversa applicata.

## Margine di autonomia

- **Liberi:** nomi locali, helper dei test, funzioni private non fissate qui, la disposizione delle domande e dei pulsanti dentro il sistema visivo di spena.
- **Fissi:** le frasi fra «» di questo piano; i codici `origin_out_of_reach`, `proposal_past`; i campi `detach_origin`, `allowed_recipe_ids`, `today`; la colonna `from_pantry_row_ids`; i nomi pubblici delle Interfaces.
- **Una decisione di comportamento non coperta e non reversibile**: si ferma quel task, si committa il lavoro parziale, la voce del backlog passa a `bloccato` con «attende: …» e la domanda precisa, e si va al task dopo se non dipende da quello. Una scelta reversibile e a basso impatto: la più conservativa, annotata nel report.
- Un test che fallisce e non si risolve: niente test disattivati, niente asserzioni indebolite. `bloccato` con la diagnosi.

## Dipendenze

- Task 2 consuma il Task 1. Task 6 e Task 9 sono il backend e il frontend della pianificazione: il 9 consuma il 6. Task 7 ha backend e frontend insieme. Task 8 (i due pulsanti in preparazione) va dopo il Task 5 (il lucchetto che li rende sicuri). Gli altri sono indipendenti; l'ordine dei numeri va bene.

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `backend/app/domain/meals.py`, `backend/app/repositories/meals.py`, `backend/app/services/meals.py`, `backend/app/api/refusals.py`, `backend/app/schemas/meal.py`, `backend/app/api/meals.py`, test | 1 | la finestra dell'avanzo, l'avanzo spostato |
| `frontend/src/features/meals/MealForm.tsx`, `frontend/src/features/meals/MealScreen.tsx`, `frontend/src/domain/types.ts`, test | 2 | «Sposta e stacca dal pasto d'origine» |
| `backend/app/services/change_cards.py`, `backend/app/services/meals.py`, `backend/app/api/meals.py`, test | 3 | il ritorno a casa, l'inversa di un pasto passato |
| `backend/alembic/versions/0026_righe_lista_dalla_dispensa.py` (nuovo), `backend/app/db/models/change_card.py`, `backend/app/services/change_cards.py`, `backend/tests/db/test_migration_0026.py` (nuovo), test | 4 | la lista che segue la dispensa |
| `backend/app/repositories/meals.py`, `backend/app/services/meals.py`, `backend/app/services/meal_recipes.py`, `backend/app/services/claude/tools.py`, `backend/app/api/meal_chat.py`, test | 5 | il lucchetto sul pasto |
| `backend/app/services/planning.py`, `backend/app/repositories/conversations.py`, `backend/app/api/planning.py`, `backend/app/api/meals.py`, test | 6 | la pianificazione nel backend |
| `backend/app/api/recipes.py`, `frontend/src/features/recipes/useArchiveRecipe.ts`, `frontend/src/features/recipes/api.ts`, `frontend/src/features/cooking/RecipeDetailScreen.tsx`, test | 7 | «Elimina» di una ricetta di un pasto, il ripristino |
| `frontend/src/features/meals/MealScreen.tsx`, `frontend/src/features/meals/WeekScreen.tsx`, test | 8 | il pasto e la settimana |
| `frontend/src/features/planning/PlanningScreen.tsx`, `frontend/src/features/planning/ProposalCard.tsx`, `frontend/src/features/meal-chat/useChatSender.ts`, `frontend/src/features/meal-chat/DishChat.tsx`, test | 9 | la pianificazione a video |
| `backend/app/services/utensils.py`, `backend/app/services/recipe_jobs.py`, `backend/app/services/meal_chat.py`, test | 10 | gli utensili nei prompt dei Pasti |
| `frontend/e2e/pasti.spec.ts`, `frontend/e2e/style.spec.ts` | 11 | nel browser vero |
| `docs/superpowers/specs/2026-11-12-pasti-claude-design.md`, `CLAUDE.md`, `next-steps.md`, `docs/night-reports/<data>.md` | 12 | documenti e report |

---

### Task 1: La finestra dell'avanzo nella scrittura, e l'avanzo spostato (idee 33, 35; backend)

**Files:**
- Modify: `backend/app/domain/meals.py`, `backend/app/repositories/meals.py` (`leftover_candidates`), `backend/app/services/meals.py` (`_bad_leftover`, `_check_leftover`, `MealRefusalCode`, `update_meal`), `backend/app/api/refusals.py` (`_MEAL_STATUS`), `backend/app/schemas/meal.py` (`MealUpdate`), `backend/app/api/meals.py` (la `PATCH`)
- Test: `backend/tests/domain/test_meals.py`, `backend/tests/services/test_meals.py`, `backend/tests/api/test_meals.py`

**Interfaces:**
- Produces: `def in_leftover_window(origin_day: date, origin_slot: MealSlot, day: date, slot: MealSlot) -> bool` in `app.domain.meals` = `is_before(origin_day, origin_slot, day, slot) and origin_day >= day - timedelta(days=LEFTOVER_WINDOW_DAYS)`. `MealRefusalCode.ORIGIN_OUT_OF_REACH = "origin_out_of_reach"` (409). `update_meal(session, meal, changes, *, replace=False, detach_leftovers=False, detach_origin=False)`. `MealUpdate.detach_origin: bool = False`, che come `replace` e `detach_leftovers` non è un cambio. Il corpo del rifiuto: `{"detail": …, "code": "origin_out_of_reach"}`.

- [ ] **Step 1: I test che falliscono.**
  - Dominio: `test_in_leftover_window`, parametrizzato, con l'avanzo a martedì pranzo: lunedì cena → vero; sabato pranzo (3 giorni prima) → vero; venerdì cena (4 giorni) → falso; martedì pranzo stesso posto → falso; martedì cena → falso.
  - Servizio, `test_meals.py`, con «Lasagne» lunedì cena e il suo avanzo martedì pranzo:
    - `test_un_avanzo_fuori_finestra_non_si_crea`: `create_meal(..., day=venerdì dopo, leftover_of_id=lasagne.id)` → `BAD_LEFTOVER` con «Un avanzo viene da un pasto cucinato nei 3 giorni prima, che non sia a sua volta un avanzo.».
    - `test_spostare_l_avanzo_prima_del_pasto_chiede`: `update_meal(avanzo, {"day": lunedì, "slot": "lunch"})` → `ORIGIN_OUT_OF_REACH`, «Qui non può essere l'avanzo di «Lasagne» (lunedì cena): un avanzo viene dopo il suo pasto, entro 3 giorni.», niente cambiato.
    - `test_spostare_l_avanzo_troppo_avanti_chiede`: avanzo a venerdì pranzo (4 giorni dopo) → lo stesso rifiuto.
    - `test_sposta_e_stacca_dal_pasto_d_origine`: lo stesso con `detach_origin=True` → il pasto è a venerdì, `leftover_of_id` vuoto, il piatto com'era.
    - `test_spostare_l_avanzo_dentro_la_finestra_non_chiede`: a mercoledì cena → riesce, ancora legato.
    - `test_il_posto_occupato_viene_prima_dell_origine`: avanzo spostato a lunedì pranzo, dove c'è «Pizza» → `SLOT_TAKEN`; con `replace=True` → `ORIGIN_OUT_OF_REACH`; con `replace=True, detach_origin=True` → riesce.
    - `test_l_avanzo_che_va_fuori_casa_non_chiede`: `{"day": venerdì, "away": True}` → riesce, staccato.
    - `test_spostare_l_origine_troppo_indietro_chiede` (S2 allargato): lasagne a venerdì cena della settimana prima (4 giorni prima di martedì) → `LEFTOVER_AFTER`, «Martedì pranzo è un suo avanzo.», `leftovers == 1`; con `detach_leftovers=True` riesce e l'avanzo è staccato. I test di S2 restano verdi senza cambiare (`test_spostare_prima_non_chiede_niente` sposta a domenica cena: 2 giorni, dentro la finestra).
  - API: `test_patch_dell_avanzo_fuori_finestra_e_409` (corpo `{"code": "origin_out_of_reach", "detail": …}`); `test_patch_con_detach_origin_sposta`.
  - **Cambi permessi**: i test che fissano la frase vecchia di `bad_leftover`, e quelli che spostano un avanzo con `update_meal` o la `PATCH` aspettandosi `bad_leftover` (cercali con `grep -rn "bad_leftover\|BAD_LEFTOVER\|cucinato prima" backend/tests`): la frase nuova, e `origin_out_of_reach` per gli spostamenti.
- [ ] **Step 2: Falliscono.** Expected: FAIL.
- [ ] **Step 3: Il codice.**
  - `leftover_candidates` tiene il filtro SQL di oggi e sostituisce il filtro in memoria con `in_leftover_window`: una regola sola per il modulo e la scrittura.
  - `_check_leftover` usa `in_leftover_window` al posto di `is_before`; `_bad_leftover` ha la frase nuova.
  - In `update_meal`, il controllo dell'avanzo spostato esce da dove sta oggi e va **dopo** il rifiuto del posto occupato: se il pasto si sposta, non va fuori casa e ha `leftover_of_id`, si legge l'origine; se l'origine non è valida per altri motivi (non c'è, è fuori casa, è un avanzo) resta `_bad_leftover()`; se è valida ma `not in_leftover_window(...)`, senza `detach_origin` il rifiuto nuovo (la frase con `origin.dish` e `place_words(origin.day, MealSlot(origin.slot))`), con `detach_origin` `meal.leftover_of_id = None` prima di scrivere il posto. Nel rifiuto `leftover_after` di S2, la condizione su ogni avanzo diventa `not in_leftover_window(day, slot, avanzo.day, MealSlot(avanzo.slot))`.
  - `_MEAL_STATUS[ORIGIN_OUT_OF_REACH] = 409`. La `PATCH` esclude `detach_origin` dai cambi e lo passa.
- [ ] **Step 4: Passano**, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `fix(pasti): la scrittura controlla la finestra dei 3 giorni dell'avanzo; un avanzo spostato fuori chiede, e «Sposta e stacca dal pasto d'origine» lo stacca`.

---

### Task 2: «Sposta e stacca dal pasto d'origine» nel modulo (idea 35; frontend)

**Files:**
- Modify: `frontend/src/features/meals/MealForm.tsx` (la domanda di S2 prende un terzo tipo), `frontend/src/features/meals/MealScreen.tsx` (`patchFrom`), `frontend/src/domain/types.ts` (`MealBody.detach_origin?: boolean`, `MealPatch.detach_origin?: boolean`)
- Test: `frontend/src/features/meals/MealForm.test.tsx`, `frontend/src/features/meals/MealScreen.test.tsx`

**Interfaces:**
- Consumes: il rifiuto `origin_out_of_reach` (Task 1).

- [ ] **Step 1: I test che falliscono.** In `MealForm.test.tsx`:
  - «l'avanzo fuori dalla finestra: la domanda e Sposta e stacca dal pasto d'origine»: `save` rifiuta con 409 `origin_out_of_reach` e il `detail` del Task 1 → si leggono la frase, «Sposta e stacca dal pasto d'origine» e un «Annulla» solo, e i pulsanti del modulo non ci sono (decisione 6 del padre); premuto il primo, `save` riceve lo stesso corpo con `detach_origin: true`; «Annulla» chiude la domanda e i pulsanti tornano.
  - «il posto occupato e poi l'origine: due domande in fila»: `slot_taken`, «Sostituisci», poi `origin_out_of_reach`; «Sposta e stacca dal pasto d'origine» manda `replace: true` e `detach_origin: true` insieme.
  - In `MealScreen.test.tsx`: «Correggi di un avanzo manda detach_origin»: `patchFrom` porta `detach_origin` quando il corpo lo ha e la patch ha un cambio.
- [ ] **Step 2: Falliscono.** `npx vitest run src/features/meals`. Expected: FAIL.
- [ ] **Step 3: Il codice.** Il tipo `origin_out_of_reach` accanto a `slot_taken` e `leftover_after`, con la frase dal `detail` (il frontend non la compone) e il corpo rifiutato da rimandare; cambiare giorno o pasto la chiude, come le altre.
- [ ] **Step 4: Passano**, poi `npx vitest run`, `npm run typecheck`, `npm run lint`. Expected: verdi, puliti.
- [ ] **Step 5: Commit** — `pasti: un avanzo spostato fuori dalla finestra chiede, con «Sposta e stacca dal pasto d'origine»`.

---

### Task 3: Il ritorno a casa e l'inversa di un pasto passato (idee 44, 50)

**Files:**
- Modify: `backend/app/services/change_cards.py` (`_discard_proposed_inverses` diventa pubblica, `propose_inverse_card`, costante nuova), `backend/app/services/meals.py` (`update_meal`, `delete_meal`), `backend/app/api/meals.py` (la `DELETE`)
- Test: `backend/tests/services/test_inverse_cards.py`, `backend/tests/services/test_meals.py`, `backend/tests/api/test_meals.py`

**Interfaces:**
- Produces: `async def discard_proposed_inverses(session, meal_id: str) -> None` (il corpo di oggi; `propose_inverse_card` la chiama per nome nuovo). `PAST_MEAL_NOTE = "Pasto già passato: rimettila solo se non l'hai mangiato."`. `propose_inverse_card(session, meal, reason, *, today: date | None = None)` e `delete_meal(session, meal, *, today: date | None = None, _reason=...)`: con `today` valorizzato, `reason == DELETED` e `meal.day < today`, ogni riga dell'inversa ha `checked = False`, e `note = PAST_MEAL_NOTE` se non ne aveva una. La `DELETE /meals/{id}` passa `today=today_in_pantry()`; le sostituzioni (`create_meal`/`update_meal` con `replace`) non lo passano.

- [ ] **Step 1: I test che falliscono.**
  - `test_meals.py`: `test_tornare_a_casa_scarta_l_inversa_del_fuori_casa` (pasto ufficiale con una scheda applicata; `{"away": True}` → un'inversa proposta; `{"away": False}` → quella inversa è `discarded` con `discarded_at`, e `open_cards_for_meals` non la dà più); `test_tornare_a_casa_senza_inversa_non_tocca_niente` (nessuna scheda cambia stato).
  - `test_inverse_cards.py`: `test_eliminare_un_pasto_passato_propone_l_inversa_senza_spunte` (pasto del 20 novembre, `delete_meal(..., today=date(2026, 11, 23))`: l'inversa c'è, tutte le righe `checked` falso, `note == PAST_MEAL_NOTE` sulle righe senza nota, `CHANGED_NOTE` resta su quella cambiata); `test_eliminare_un_pasto_di_oggi_spunta_come_sempre` (`today` = il giorno del pasto); `test_senza_oggi_l_inversa_e_quella_di_sempre` (`today=None`); `test_sostituire_un_pasto_passato_spunta_come_sempre` (decisione 16).
  - API: `test_delete_di_un_pasto_passato_propone_l_inversa_senza_spunte` (date relative: pasto a `today_in_pantry() - timedelta(days=2)`, scheda proposta e applicata con il servizio, `DELETE`, poi la scheda inversa letta con la sua rotta: righe non spuntate, con la nota).
- [ ] **Step 2: Falliscono.** Expected: FAIL.
- [ ] **Step 3: Il codice.** In `update_meal`, se `not away and meal.away`, `await discard_proposed_inverses(session, str(meal.id))`, con il commento: le inverse proposte di un pasto vivo sono quelle del «fuori casa» (decisione 3 di Mattia, 2026-11-21). In `propose_inverse_card`, dopo aver costruito le righe e prima di scriverle, il passaggio del pasto passato; la docstring aggiunge la regola e il perché (un pasto passato si è mangiato: rimettere di default sbaglierebbe).
- [ ] **Step 4: Passano**, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `fix(pasti): tornando a casa l'inversa del «fuori casa» si scarta; l'inversa di un pasto passato non ha spunte`.

---

### Task 4: La riga della lista segue lo stato corretto (idea 49)

**Files:**
- Create: `backend/alembic/versions/0026_righe_lista_dalla_dispensa.py`, `backend/tests/db/test_migration_0026.py`
- Modify: `backend/app/db/models/change_card.py` (`ChangeCardRow.from_pantry_row_ids`, la docstring), `backend/app/services/change_cards.py` (`propose_card`, `apply_card`, due costanti)
- Test: `backend/tests/services/test_change_cards.py`, `backend/tests/services/test_inverse_cards.py`

**Interfaces:**
- Produces: `change_card_rows.from_pantry_row_ids JSONB NOT NULL DEFAULT '[]'::jsonb` (gli id come stringhe, come `source_row_ids`); `ChangeCardRow.from_pantry_row_ids: Mapped[list[str]]`. `NO_LONGER_FINISHED_NOTE = "Non va in lista: nella scheda la voce non diventa più «Finito»."`, `NOW_FINISHED_NOTE = "In lista perché nella scheda la voce diventa «Finito»."`. La `downgrade` toglie la colonna.

- [ ] **Step 1: I test che falliscono.**
  - `test_migration_0026.py`, sul modello di `test_migration_0024.py`: `test_la_0026_sale_e_scende` (una riga scritta prima vale `[]`; `downgrade` alla testa annotata la toglie).
  - `test_change_cards.py`, con passata e panna in dispensa `available`:
    - `test_la_riga_della_lista_ricorda_da_dove_viene`: `propose_card` con passata → `finished` → la riga di lista ha `from_pantry_row_ids == [str(id della riga di dispensa)]`; con anche un `ListProposal` per la passata → `[]`; una `add_row` a mano → `[]`.
    - `test_correggere_finito_in_quasi_finito_non_mette_in_lista`: la stessa scheda applicata con l'override `low` sulla passata → nessuna voce attiva in lista per la passata, la riga di lista ha `applied` falso e `NO_LONGER_FINISHED_NOTE`, la passata è `low`.
    - `test_correggere_quasi_finito_in_finito_mette_in_lista`: panna → `low`, nessuna riga di lista; override `finished` → una voce attiva per la panna, e la scheda applicata ha una riga di lista nuova, ultima per posizione, `list_added` vero, `NOW_FINISHED_NOTE`, `from_pantry_row_ids` = la riga della panna.
    - `test_una_riga_chiesta_da_claude_resta_anche_se_la_voce_non_finisce` (Review Focus 2).
    - `test_due_voci_dello_stesso_ingrediente_una_resta_finita` (Review Focus 1): due voci di passata, tutte e due `finished`, una corretta a `low` → la passata è in lista una volta.
    - `test_la_riga_aggiunta_non_duplica_la_lista`: panna già da comprare in lista; override `finished` → la riga nuova c'è, `list_added` falso, e in lista la panna è una sola.
    - `test_una_voce_gia_finita_non_aggiunge_righe`: una riga di dispensa a mano su una voce già `finished`, lasciata `finished` → nessuna riga di lista nuova.
    - `test_una_riga_di_dispensa_non_spuntata_non_aggiunge_righe`: panna corretta a `finished` ma non spuntata → nessuna riga nuova.
  - `test_inverse_cards.py`: `test_l_inversa_toglie_la_riga_aggiunta_all_applicazione`: dopo il caso della panna, il pasto si elimina → l'inversa ha la riga che toglie la panna dalla lista.
- [ ] **Step 2: Falliscono.** Expected: FAIL.
- [ ] **Step 3: Migrazione e codice.**
  - `propose_card`: per ogni chiave della lista tiene le voci di dispensa che l'hanno portata e se un `ListProposal` l'ha chiesta; scrive prima le righe di dispensa, `flush`, poi quelle di lista con `from_pantry_row_ids` = gli id delle righe di quelle voci, oppure `[]` se una proposta l'ha chiesta.
  - `apply_card`, dopo le correzioni e prima del ciclo delle righe (dopo il blocco delle origini delle inverse): la decisione 15, in due passi. Primo, ogni riga `LIST` con `from_pantry_row_ids` non vuoto le cui righe d'origine (in questa scheda) non hanno più nessuna `to_status == finished` si segna da saltare: nel ciclo, se spuntata, `applied = False` e `NO_LONGER_FINISHED_NOTE`, senza `add_item`. Secondo, per ogni riga `PANTRY` spuntata con `to_status == finished`, la cui voce viva adesso non è `finished`, e senza nessuna riga `LIST` della scheda con lo stesso `ingredient_id`, una riga `LIST` nuova (`label=_label(item)`, `ingredient_id`, `meal_ids` della riga di dispensa, `checked` ed `editable` veri, `NOW_FINISHED_NOTE`, `from_pantry_row_ids=[str(id)]`, posizione dopo l'ultima), che il ciclo applica con `add_item` come le altre.
  - La docstring di `apply_card` e quella del modello dicono la regola e perché le righe di prima della `0026` (`[]`) stanno in piedi da sole come oggi.
- [ ] **Step 4: Passano**, con `tests/db/test_migration_0026.py tests/db/test_metadata_matches_migrations.py`, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `fix(pasti): nella scheda la riga della lista segue lo stato corretto della voce (0026)`.

---

### Task 5: Il lucchetto sul pasto (idee 52, 42)

**Files:**
- Modify: `backend/app/repositories/meals.py` (`lock_meal` nuova), `backend/app/services/meals.py` (`link_recipe`), `backend/app/services/meal_recipes.py` (`write_meal_recipe`, `undo_recipe_change`, due costanti), `backend/app/services/claude/tools.py` (`write_recipe`), `backend/app/api/meal_chat.py` (`undo_change`)
- Test: `backend/tests/db/test_meal_lock.py` (nuovo, due sessioni vere da `factory`), `backend/tests/services/test_meal_recipes.py`, `backend/tests/api/test_meals.py` o il file delle rotte delle ricette dei pasti

**Interfaces:**
- Produces: `async def lock_meal(session: AsyncSession, meal_id: uuid.UUID) -> Meal | None` in `app.repositories.meals`: `_select()` con `.with_for_update(of=Meal)`, stesse `_LOADS` e `populate_existing`. In `app.services.meal_recipes`: `CREATE_ONLY_MESSAGE = "Il pasto ha già una ricetta: non riscriverla."`, `MEAL_GONE_MESSAGE = "Il pasto non esiste più."`; `write_meal_recipe(..., expected=None, allowed_recipe_ids: frozenset[uuid.UUID | None] | None = None)`: la prima istruzione è `lock_meal` (pasto sparito → `RecipeWriteRefused(MEAL_GONE_MESSAGE)`); con `allowed_recipe_ids` valorizzato e `meal.recipe_id` fuori dall'insieme → `RecipeWriteRefused(CREATE_ONLY_MESSAGE)`, prima di ogni scrittura; poi i controlli di oggi (C1 compreso) sul pasto bloccato. Lo strumento `write_recipe` passa `allowed_recipe_ids=frozenset({None, *written})` quando `ctx.create_only` e non fa più il controllo da sé.

- [ ] **Step 1: I test che falliscono.** In `test_meal_lock.py`, con due sessioni dal `factory` (il modello è `test_double_tap.py`), un pasto ufficiale senza ricetta, e `asyncio.wait_for(..., 0.3)` per dire «aspetta»:
  - `test_lock_meal_aspetta_chi_lo_tiene`: A prende `lock_meal`; in B `lock_meal` scade; dopo il `commit` di A, B lo prende.
  - `test_la_coda_non_riscrive_una_ricetta_scritta_a_mano_nel_frattempo` (Review Focus 3): A prende il lucchetto, crea una ricetta e la lega con `link_recipe`; B lancia `write_meal_recipe(..., allowed_recipe_ids=frozenset({None}))` e aspetta; A committa; B solleva `RecipeWriteRefused(CREATE_ONLY_MESSAGE)`. Alla fine il pasto ha la ricetta di A, e nessuna ricetta viva fuori dal ricettario è senza pasto.
  - `test_scrivere_a_mano_dopo_la_coda_rifiuta`: B scrive con `write_meal_recipe` e committa; A, con il pasto letto prima, `link_recipe` → `MealRefusal(HAS_RECIPE)`.
  - `test_annulla_aspetta_la_scrittura`: una modifica annullabile; A prende il lucchetto e riscrive con `write_meal_recipe`; in B `undo_recipe_change` aspetta; A committa; B solleva `ChangeRefusal(STALE)`.
  - `test_due_annulla_insieme`: lo stesso annullamento in A e B → uno riesce, l'altro `ChangeRefusal(ALREADY_UNDONE)` (dopo il lucchetto la modifica si rilegge).
  - API: `test_scrivi_la_ricetta_dopo_la_coda_non_lascia_orfane`: il pasto riceve una ricetta da `write_meal_recipe` (come la coda) e si committa; poi `POST /api/v1/recipes` con `meal_id` → 409 `has_recipe`, e il numero di ricette non cambia. Se la rotta lasciasse la ricetta creata, il `rollback` va aggiunto lì.
  - Il test di oggi su «Il pasto ha già una ricetta: non riscriverla.» in `test_claude_planning_tools.py` resta verde senza cambiare.
- [ ] **Step 2: Falliscono.** Expected: FAIL.
- [ ] **Step 3: Il codice.** `link_recipe` prende `lock_meal(session, meal.id)` e fa `check_can_take_recipe` sul pasto bloccato (con `populate_existing` è lo stesso oggetto di chi chiama). `undo_recipe_change` prende `lock_meal(session, change.meal_id)` e poi `await session.refresh(change)`, prima di `change_is_undoable`. In `undo_change` (rotta), `lock_meal` prima del controllo `registry.running`, con il commento: dopo il lucchetto, un giro che parte adesso scrive solo dopo il nostro `commit`, e l'istantanea di C1 lo ferma. Ogni lucchetto ha sopra una riga che dice perché (idea 52: due ricette nello stesso istante, l'ultima vince e l'altra resta orfana).
- [ ] **Step 4: Passano**, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `fix(pasti): la ricetta di un pasto si scrive con il pasto bloccato (coda, salvataggio a mano, chat, «Annulla»)`.

---

### Task 6: La pianificazione nel backend (idee 45, 48, 53)

**Files:**
- Modify: `backend/app/services/planning.py` (`place_proposal`, `planning_to_reopen`), `backend/app/repositories/conversations.py` (`latest_planning`), `backend/app/api/planning.py` (`place`, via `_meals_out`), `backend/app/api/meals.py` (`_meals_out` → `meals_out`)
- Test: `backend/tests/services/test_planning.py`, `backend/tests/api/test_planning.py`

**Interfaces:**
- Produces: `place_proposal(session, proposal_id, *, replace, now, today: date | None = None)`: con `today`, dopo i controlli di stato e prima degli occupanti, se una riga ha `day < today` → `PlanningRefusal(PlanningRefusalCode.PAST, f"Questa proposta ha un giorno già passato ({day_name(primo)}): chiedi a Claude di rifarla.")`, niente scritto e la proposta resta `open`. La rotta passa `today=today_in_pantry(now)`. `latest_planning(session, *, with_messages: bool = False)`. `async def meals_out(session, meals: list[Meal], today: date, preparing: frozenset[uuid.UUID] = frozenset()) -> list[MealOut]` in `app.api.meals`, l'unica.

- [ ] **Step 1: I test che falliscono.**
  - `test_planning.py`: `test_una_proposta_con_un_giorno_passato_non_si_mette` (proposta di oggi per venerdì 13; `place_proposal(..., today=date(2026, 11, 14))` → `PAST`, «Questa proposta ha un giorno già passato (venerdì 13 novembre): chiedi a Claude di rifarla.», proposta ancora `open`, nessun pasto); `test_senza_oggi_non_si_controlla` (`today=None`: si mette come oggi).
  - `test_planning.py`, `planning_to_reopen` (decisione 12): `test_una_conversazione_vuota_non_nasconde_una_bozza_aperta` (A con una bozza messa ancora bozza, B più nuova senza messaggi → A); `test_una_conversazione_vuota_non_nasconde_una_aperta_piu_vecchia` (A con messaggi e nessuna proposta, B vuota → A); `test_la_conversazione_vuota_si_riapre_se_non_c_e_altro` (solo B → B; A conclusa e B vuota → B).
  - API: `test_place_di_una_proposta_passata_e_409` (proposta per domani scritta col servizio, poi spostata a ieri riscrivendo `rows`: 409, `code == "proposal_past"`, la frase, `chat` nella risposta con la proposta ancora aperta).
- [ ] **Step 2: Falliscono.** Expected: FAIL.
- [ ] **Step 3: Il codice.** `planning_to_reopen`: `newest = await latest_planning(session, with_messages=True)`; se c'è e non è conclusa, è lei; poi le bozze come oggi; se non trova niente, `await latest_planning(session)` se quella non ha messaggi, altrimenti `None`. `with_messages` filtra con un `EXISTS` su `ConversationMessage` dentro la query che porta il `limit`. `meals_out` prende il posto delle due `_meals_out`; `api/planning.py` lo importa e passa `today_in_pantry()`.
- [ ] **Step 4: Passano**, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `fix(pianificazione): una proposta con un giorno passato non si mette; una conversazione vuota non nasconde quella da riaprire; un solo meals_out`.

---

### Task 7: «Elimina» dal ricettario su una ricetta di un pasto, e il ripristino (idee 38, 39)

**Files:**
- Modify: `backend/app/api/recipes.py` (`update`, costante nuova), `frontend/src/features/recipes/useArchiveRecipe.ts`, `frontend/src/features/recipes/api.ts` (`setRecipeArchived` restituisce la ricetta, se oggi non lo fa), `frontend/src/features/cooking/RecipeDetailScreen.tsx` (`restore`)
- Test: il file delle rotte delle ricette che prova `archived` (cercalo con `grep -rln '"archived": True' backend/tests/api`), `frontend/src/features/recipes/useArchiveRecipe.test.tsx`, `frontend/src/features/cooking/RecipeDetailScreen.test.tsx`

**Interfaces:**
- Produces: `MEAL_RECIPE_KEPT = "È la ricetta di un pasto: si elimina insieme al pasto."`; nella `PATCH`, con `archived: true` e `meal_of_recipe(...)` non vuoto: nel ricettario → `in_book = False`, `archived_at` resta vuoto, 200 con la ricetta; fuori dal ricettario → 409 `MEAL_RECIPE_KEPT`, prima di scrivere. Senza pasto, come oggi.

- [ ] **Step 1: I test che falliscono.**
  - Backend: `test_eliminare_dal_ricettario_una_ricetta_di_un_pasto_la_toglie_dal_ricettario` (pasto con la ricetta salvata nel ricettario: `PATCH {"archived": true}` → 200, `archived_at` vuoto, `in_book` falso; il pasto ha ancora la ricetta); `test_eliminare_una_ricetta_di_un_pasto_fuori_dal_ricettario_e_409`; `test_tolta_dal_ricettario_si_archivia_col_pasto` (Review Focus 5: dopo, `DELETE` del pasto → la ricetta è archiviata). I test di oggi sull'eliminazione di una ricetta senza pasto restano verdi.
  - `useArchiveRecipe.test.tsx`: «una ricetta di un pasto si toglie dal ricettario, con Annulla»: la `PATCH` risponde con `archived_at: null`, `in_book: false`, `meal: {dish: "Frittata", …}` → l'avviso «Tolta dal ricettario: resta la ricetta di «Frittata».» con «Annulla»; premuto, parte `PATCH {"in_book": true}`; si rinfrescano anche `["meals"]`. Con `archived_at` valorizzato, l'avviso «Eliminata: ‹titolo›» di oggi.
  - `RecipeDetailScreen.test.tsx`: «ripristinare dalla lapide nel pasto rinfresca i pasti»: `RecipeDetailView` con `meal={{ mealId, readOnly: false }}` su una ricetta archiviata, «Ripristina» → `invalidateQueries` chiamato anche con `{ queryKey: ["meals"] }`.
- [ ] **Step 2: Falliscono.** Expected: FAIL.
- [ ] **Step 3: Il codice.** Nella `PATCH` il caso nuovo sta fra le decisioni prese «prima di scrivere qualunque cosa», con il commento: l'invariante «una ricetta viva fuori dal ricettario ha sempre un pasto» (decisione di Mattia del 2026-11-21). In `useArchiveRecipe`, la mutazione legge la ricetta restituita: `archived_at === null` vuol dire che il server l'ha tolta dal ricettario, e l'avviso è quello nuovo (con `meal?.dish`; senza pasto, «Tolta dal ricettario: resta la ricetta del suo pasto.»); il resto (via dalla cache del ricettario, ritorno a `/ricette`) come oggi. In `RecipeDetailView`, `restore` rinfresca anche `["meals"]`, come `setInBook`.
- [ ] **Step 4: Passano**, backend e frontend; `npm run typecheck && npm run lint`. Expected: PASS, puliti.
- [ ] **Step 5: Commit** — `fix(pasti): «Elimina» dal ricettario toglie dal ricettario la ricetta di un pasto, con «Annulla»; il ripristino dalla lapide rinfresca i pasti`.

---

### Task 8: Il pasto e la settimana (idee 51, 55, 36)

**Files:**
- Modify: `frontend/src/features/meals/MealScreen.tsx` (il ramo `recipe_state === "preparing"`, l'`Alert` di `recipe_notice`), `frontend/src/features/meals/WeekScreen.tsx` (lo stato d'errore)
- Test: `frontend/src/features/meals/MealScreen.test.tsx`, `frontend/src/features/meals/WeekScreen.test.tsx`

- [ ] **Step 1: I test che falliscono.**
  - `MealScreen.test.tsx`: «in preparazione si può scrivere la ricetta o sceglierla»: `recipe_state: "preparing"` → «Ricetta in preparazione: arriva fra poco.», «Puoi anche scriverla tu: quella di Claude allora non arriva.», e i collegamenti «Scrivi la ricetta» (`/pasti/<id>/ricetta/nuova`) e «Scegli dal ricettario» (`/pasti/<id>/ricetta/scegli`); nessun «Chiedi la ricetta a Claude». «l'avviso della ricetta non arrivata ha il tono dell'AI»: con `recipe_notice`, il suo elemento ha la classe di `tone="degraded"` (`text-low`) e non `text-danger`.
  - `WeekScreen.test.tsx`: «una settimana non valida offre Torna a oggi»: con `?settimana=abc` e la lettura che risponde 422 → «La settimana non si carica.», «Riprova», e il collegamento «Torna a oggi» verso `/pasti`; senza `settimana` nell'indirizzo, nell'errore non c'è.
- [ ] **Step 2: Falliscono.** `npx vitest run src/features/meals`. Expected: FAIL.
- [ ] **Step 3: Il codice.** Il ramo in preparazione disegna sotto la frase la seconda riga e i due collegamenti con `buttonClasses("secondary")`, come il ramo senza ricetta (una sola fila di pulsanti, che a 375 px va a capo). `Alert tone="degraded"` per `recipe_notice`. Nello stato d'errore di `WeekScreen`, quando `of !== null`, sotto `ErrorState` il collegamento «Torna a oggi» con le classi del «Torna a oggi» che c'è già.
- [ ] **Step 4: Passano**, poi `npx vitest run`, `npm run typecheck`, `npm run lint`. Expected: verdi.
- [ ] **Step 5: Commit** — `pasti: in preparazione si può scrivere la ricetta a mano; l'avviso della ricetta col tono dell'AI; «Torna a oggi» da una settimana che non si carica`.

---

### Task 9: La pianificazione a video (idee 46, 47, 45; la ricetta dell'occupante)

**Files:**
- Modify: `frontend/src/features/meal-chat/useChatSender.ts` (`shownRefusal` nuova), `frontend/src/features/planning/PlanningScreen.tsx`, `frontend/src/features/meal-chat/DishChat.tsx` (se mostra lo stesso doppione), `frontend/src/features/planning/ProposalCard.tsx`
- Test: `frontend/src/features/planning/PlanningScreen.test.tsx`, `frontend/src/features/planning/ProposalCard.test.tsx`, `frontend/src/features/meal-chat/DishChat.test.tsx`

**Interfaces:**
- Consumes: `proposal_past` con la frase (Task 6).
- Produces: `export function shownRefusal(refusal: Refusal | null, chat: { claude_ready: boolean; claude_notice: string | null } | undefined): Refusal | null` (null se il testo è quello che la schermata dice già in testa). `export type PlaceState = { occupants: Meal[] | null; error: string | null }`; `ProposalCard` riceve `state: PlaceState` e `onState: (next: PlaceState) => void` al posto dei due `useState`; `PlanningScreen` tiene `Record<string, PlaceState>` per id della proposta.

- [ ] **Step 1: I test che falliscono.**
  - `PlanningScreen.test.tsx`: «dopo un 503 l'avviso si legge una volta»: la vista con `claude_ready: false` e l'avviso, l'invio che risponde 503 con lo stesso testo → `getAllByText(<avviso>)` ha un elemento. «la conferma dei posti occupati resta quando la risposta si salva»: «Metti nella settimana» → 409 `slots_taken`; poi nella cache arriva una `PlanningChat` nuova in cui la stessa proposta sta in un messaggio con un altro id (quello salvato al posto di quello in arrivo) → «Questi posti sono occupati:» c'è ancora, e «Sostituisci e metti» manda `replace: true`.
  - `DishChat.test.tsx`: lo stesso «dopo un 503 l'avviso si legge una volta», se `DishChat` mostra il rifiuto dell'invio (se non lo mostra, il test dice che c'è un avviso solo e passa già: scrivilo nel report).
  - `ProposalCard.test.tsx`: «la conferma dice che la ricetta dell'occupante si elimina»: occupante con `recipe: {in_book: false, …}` → sotto la sua riga «La sua ricetta non è nel ricettario: si elimina con il pasto.»; con `in_book: true`, o senza ricetta, no. «una proposta con un giorno passato resta, con la frase»: 409 `proposal_past` → la frase del Task 6 sotto la scheda, le righe e «Metti nella settimana» ancora lì.
- [ ] **Step 2: Falliscono.** Expected: FAIL.
- [ ] **Step 3: Il codice**, come nelle Interfaces. `PlanningScreen` e `DishChat` disegnano `shownRefusal(sender.refusal, data)` al posto di `sender.refusal`. In `ProposalCard` `busy` e `inFlight` restano suoi (il `FOR UPDATE` di `place_proposal` ferma comunque un secondo tocco).
- [ ] **Step 4: Passano**, poi `npx vitest run`, `npm run typecheck`, `npm run lint`. Expected: verdi.
- [ ] **Step 5: Commit** — `pianificazione: un avviso solo dopo un 503; la conferma dei posti sopravvive al ridisegno e dice della ricetta che si elimina; la proposta passata resta con la sua frase`.

---

### Task 10: Gli utensili nei prompt dei Pasti (H4, lato Pasti)

**Files:**
- Modify: `backend/app/services/utensils.py`, `backend/app/services/recipe_jobs.py` (`_ask_claude`), `backend/app/services/meal_chat.py` (il prompt del piatto)
- Test: `backend/tests/services/test_claude_prompts.py`, `backend/tests/services/test_recipe_jobs.py`, `backend/tests/services/test_meal_chat_turn.py`

**Interfaces:**
- Produces (se il ramo non ha già un meccanismo suo, Global Constraints): in `app.services.utensils`, `UTENSILS_PROMPT_RULE_START = "Usa solo questi strumenti. Se la tecnica di sempre ne chiede uno che manca (la frusta per montare gli albumi, per esempio), scegli un'altra tecnica che si fa con quelli che ci sono; "`; `MISSING_TOOL_SAY = "se senza quello strumento il piatto non si fa, dillo."` (la frase di oggi); `MISSING_TOOL_IN_STEPS = "se senza quello strumento il piatto non si fa, scrivilo al primo passo del procedimento: della tua risposta resta solo la ricetta."`; `MISSING_TOOL_IN_REPLY = "se senza quello strumento il piatto non si fa, dillo a Mattia nella risposta."`; `UTENSILS_PROMPT_RULE = UTENSILS_PROMPT_RULE_START + MISSING_TOOL_SAY` (resta, uguale a oggi); `render_utensils_block(entries, *, missing_tool: str = MISSING_TOOL_SAY)` e `utensils_prompt_block(session, *, missing_tool: str = MISSING_TOOL_SAY)`. La coda passa `MISSING_TOOL_IN_STEPS`, la chat del piatto `MISSING_TOOL_IN_REPLY`; bozza, variante e pianificazione non passano niente.

- [ ] **Step 1: I test che falliscono.** `test_claude_prompts.py`: `test_la_regola_dice_dove_dirlo` (con `missing_tool=MISSING_TOOL_IN_STEPS` il blocco finisce con `UTENSILS_PROMPT_RULE_START + MISSING_TOOL_IN_STEPS`; senza, con `UTENSILS_PROMPT_RULE`). `test_recipe_jobs.py`: `test_la_coda_chiede_lo_strumento_nel_procedimento` (con un utensile, il prompt di sistema che il finto riceve finisce con `MISSING_TOOL_IN_STEPS`). `test_meal_chat_turn.py`: il test di oggi che confronta il prompt del piatto con `utensils_prompt_block(db_session)` lo chiama con `missing_tool=MISSING_TOOL_IN_REPLY` (è il cambio permesso). I test della bozza, della variante e della pianificazione restano verdi senza cambiare.
- [ ] **Step 2: Falliscono.** Expected: FAIL.
- [ ] **Step 3: Il codice**, come nelle Interfaces; la docstring del modulo dice perché la coda vuole la frase nel procedimento (nessuno legge la risposta del giro della coda).
- [ ] **Step 4: Passano**, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `pasti: la regola degli utensili dice dove dire lo strumento che manca (nel procedimento per la coda, nella risposta per la chat)`.

---

### Task 11: Nel browser vero, a 375 px, nei due temi

**Files:**
- Modify: `frontend/e2e/pasti.spec.ts` (prove in fondo), `frontend/e2e/style.spec.ts` (una prova **in fondo al file**)

- [ ] **Step 1: Le prove funzionali**, in fondo a `pasti.spec.ts` (375×812, accesso come nelle altre prove, posti lontani da quelli delle altre prove e del piano padre — fra 40 e 50 giorni da oggi —, piatti che cominciano per «e2e-terzo»; nel `finally` si eliminano i pasti creati):
  1. **«un avanzo spostato fuori dalla finestra chiede, e si stacca»**: con `page.request`, «e2e-terzo Lasagne» a cena fra 40 giorni e il suo avanzo a pranzo il giorno dopo. Su `/pasti/<avanzo>`, «Correggi», il giorno a +45, «Salva»: si legge la frase del Task 1, c'è un «Annulla» solo e «Sposta e stacca dal pasto d'origine». Premuto: la settimana di +45 ha il pasto, e la sua schermata non dice più «Avanzo di».
  2. **«Elimina dal ricettario la ricetta di un pasto la toglie dal ricettario»**: un pasto «e2e-terzo Frittata» con la sua ricetta (`POST /api/v1/recipes` con `meal_id`), salvata nel ricettario (`PATCH {"in_book": true}`). Su `/ricette/<id>`, «Elimina»: l'avviso «Tolta dal ricettario: resta la ricetta di «e2e-terzo Frittata».»; su `/pasti/<pasto>` la ricetta c'è, senza «Questa ricetta è stata eliminata.».
  3. **«una settimana non valida torna a oggi»**: `/pasti?settimana=abc` → «La settimana non si carica.»; «Torna a oggi» porta alla settimana di oggi.
- [ ] **Step 2: La prova di stile**, in fondo a `style.spec.ts`: **«la domanda dell'avanzo spostato e la settimana non valida, a 375 px nei due temi»**: lo stato della prova 1 prima di rispondere, poi `/pasti?settimana=abc`; per `"light"` e `"dark"`, `fermo`, `testiIlleggibili(page)` è `[]`, `scrollWidth <= clientWidth`, «Sposta e stacca dal pasto d'origine», «Annulla» e «Torna a oggi» visibili e alti almeno 44 px. Nel `finally`, i pasti si eliminano.
- [ ] **Step 3: Typecheck e lint**, `npm run typecheck && npm run lint`. Expected: puliti.
- [ ] **Step 4: L'e2e intera** su uno stack ricreato da zero. Expected: tutto verde, `N_e2e` + 4. **Annota** `N_e2e`. Poi `down -v` e `rm .env`, sempre. Un testo illeggibile si corregge con un altro token esistente, mai con uno nuovo; se nessuno basta, `bloccato` con la misura.
- [ ] **Step 5: Commit** — `pasti: nel browser vero — l'avanzo fuori finestra che chiede, «Elimina» che toglie dal ricettario, la settimana non valida; il contrasto nei due temi a 375 px`.

---

### Task 12: I documenti, la verifica finale e il report

**Files:**
- Modify: `docs/superpowers/specs/2026-11-12-pasti-claude-design.md`, `CLAUDE.md`, `next-steps.md`
- Create o modify: `docs/night-reports/<data di oggi>.md`

- [ ] **Step 1: La spec.** In §4.2, al punto dell'**avanzo**, aggiungi: «Un avanzo viene da un pasto cucinato prima del suo posto e non più di 3 giorni prima; spostarlo fuori si chiede, e «Sposta e stacca dal pasto d'origine» lo lascia come pasto a mano (deciso da Mattia il 2026-11-21).». Alla fine del paragrafo «Quando la ricetta di un pasto si salva nel ricettario…», aggiungi: ««Elimina» dal ricettario su una ricetta che ha un pasto la toglie dal ricettario, con «Annulla», e il pasto la tiene (deciso da Mattia il 2026-11-21).». In §5.2, dopo «mettere il pasto sostituisce il vecchio solo con una conferma.», aggiungi: «La conferma dice quali ricette fuori dal ricettario si eliminano con i pasti sostituiti; una proposta con un giorno già passato non si mette, e la scheda dice di chiederne una nuova.». In §6.2, al punto della scheda inversa, aggiungi: «Quando un pasto torna a casa, l'inversa del «fuori casa» ancora proposta si scarta; eliminando un pasto passato l'inversa arriva senza spunte, perché quel pasto si è mangiato. All'applicazione di una scheda, la riga della lista che c'è per una voce finita segue lo stato corretto di quella voce (decisi da Mattia il 2026-11-21).».
- [ ] **Step 2: `CLAUDE.md`.** Nel paragrafo «**A recipe written for a meal stays out of the recipe book**», dopo «restoring one without puts it back in the book.», aggiungi: «Deleting from the book a recipe that has a meal takes it out of the book instead, with «Annulla» (decided by Mattia on 2026-11-21): the invariant is kept by the `PATCH`, not by the screen.». Nel paragrafo «**Claude proposes, Mattia applies.**», dopo «only a row that becomes `finished` brings its list row along.», aggiungi: «That rule is applied to the card as corrected: a list row a pantry row brought (`from_pantry_row_ids`) is skipped when no such row becomes `finished` any more, and one is added when a corrected row does.». Dopo «Spec: … §5.2, §6.2.» dello stesso paragrafo, una frase: «Every write of a meal's recipe — the queue, the dish chat, a manual save, «Annulla» — takes the meal row first (`lock_meal`, `SELECT … FOR UPDATE`).».
- [ ] **Step 3: `next-steps.md`.**
  1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte: il terzo giro dei Pasti)_`.
  2. La voce di questo piano diventa `fatto <data di oggi>` con ` → branch night/pasti-terzo-giro (da revisionare)`, in cima a «Fatti (recenti)».
  3. Le righe `[idea]` che questo piano chiude passano a `fatto <data di oggi>`, ognuna con « — risolta col piano `2026-11-21-pasti-terzo-giro.md` → branch night/pasti-terzo-giro (da revisionare)», e vanno in «Fatti (recenti)». Cercale per il testo, non per numero di riga; sono quelle che cominciano per «Pasti:» o «Pasti con Claude:» e parlano di: la finestra di 3 giorni dell'avanzo; il legame dell'avanzo da «Correggi» (scrivi nella riga che il legame resta non modificabile, con «Sposta e stacca dal pasto d'origine»); `?settimana=<non valida>`; «Elimina» da `/ricette/:id` su una ricetta di un pasto; il ripristino dalla lapide; il controllo «Claude sta rispondendo» di «Annulla»; il ritorno a casa con l'inversa proposta; la proposta con il giorno passato; il doppio avviso dopo un 503; la conferma «Questi posti sono occupati» che si chiude; la conversazione vuota; «Finito» ↔ «Quasi finito» nella scheda; il pasto passato e l'inversa; «in preparazione» che nasconde i due pulsanti; la scrittura che non blocca il pasto; `_meals_out` doppio; il tono di `recipe_notice`. Se sul ramo c'è anche la riga della conferma di «Metti nella settimana» sui posti occupati (la può aver aggiunta la notte del padre), chiudila allo stesso modo; se non c'è, aggiungi direttamente in «Fatti (recenti)» una riga `fatto` per lei.
  4. La riga dell'idea 43 («una risposta che si interrompe dopo l'inizio non mostra un avviso…») si **toglie**: funziona come voluto. Scrivilo nel report. Le righe 41 (il token finto nel commit `3df53ee`) e 54 (il tempo massimo della pianificazione) restano come sono.
  5. La riga H4 sulla bozza e la variante («La regola del prompt finisce «se senza quello strumento il piatto non si fa, dillo»…»): se sul ramo è ancora aperta, aggiungi in coda « (il lato dei Pasti è fatto col piano `2026-11-21-pasti-terzo-giro.md`)», senza cambiarne lo stato.
  6. Quel che è emerso fuori da questo piano va come `idea` o `tbd`, con `[Parte IV]`.
- [ ] **Step 4: La verifica finale.** I «Comandi di verifica» con i loro attesi; vitest circa **`N_vitest` + 14**, pytest circa **`N_pytest` + 50**. Se i numeri differiscono, scrivi nel report da dove viene la differenza. L'e2e del Task 11 vale se dopo non è cambiato codice; se è cambiato, rifalla. Infine `docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_pasti_terzo_giro WITH (FORCE)'`.
- [ ] **Step 5: Il report**, `docs/night-reports/<data di oggi>.md` sul ramo (in fondo, se c'è già). Dentro: il ramo e `BASE`; i conti veri contro la Preparazione; la `0026` e il suo `down_revision`; i nomi della catena trovati diversi dal piano; le decisioni 5–17 che Mattia può voler rivedere, in particolare la spunta della riga di dispensa che non entra nel salto (15), l'inversa senza spunte solo per l'eliminazione e non per la sostituzione (16), il 409 su una ricetta di un pasto già fuori dal ricettario (17), la frase dell'avanzo fuori finestra (5); l'idea 43 tolta; lo stato del doppio avviso in `DishChat` (Task 9); la sezione «Dopo il deploy (solo Mattia)» qui sotto. Niente push, niente merge, niente deploy.
  ```bash
  git add CLAUDE.md docs/ next-steps.md
  git commit -m "docs: il terzo giro dei Pasti nella spec, in CLAUDE.md, in next-steps e nel report"
  ```

---

## Dopo il deploy (solo Mattia)

La notte non tocca la produzione. Questo ramo si unisce su `master` dopo tutta la catena (`night/pasti-chiave-api`, `night/pasti-correzioni`, `night/llm-haiku`, `night/s4-candidati`); il deploy è quello del piano della chiave API («Dopo il deploy» di `docs/superpowers/plans/2026-11-18-pasti-chiave-api.md`), con il `-f`, e la `0026` gira all'avvio insieme alle altre.

1. **Le scelte da rivedere**: le decisioni 15, 16 e 17 (il report le riassume). Ognuna si cambia in un punto solo.
2. **Sul telefono**: un avanzo spostato di cinque giorni chiede, con «Sposta e stacca dal pasto d'origine». Un pasto «Fuori casa» che torna a casa non lascia la scheda inversa fra quelle da applicare. In una scheda dei cambi, una voce corretta da «Finito» a «Quasi finito» non finisce in lista, e al contrario sì. Una ricetta di un pasto salvata nel ricettario, «Elimina» da Ricette: «Tolta dal ricettario», e il pasto la mostra ancora.
3. **Con la pianificazione vera**: mentre le ricette sono in preparazione, «Scrivi la ricetta» su uno dei pasti; la ricetta di Claude per quel pasto non arriva, e nessuna ricetta orfana compare nell'Anagrafica («(da un pasto)» senza pasto). Una proposta lasciata aperta fino al giorno dopo, poi «Metti nella settimana»: la frase chiede una proposta nuova.
