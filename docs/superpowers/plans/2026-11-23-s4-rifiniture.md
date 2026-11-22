# S4, rifiniture: le vitamine E e A da CIQUAL, «Cambia alimento» senza accenti e con lo spareggio, «< 0,01», i pesi che seguono l'unità canonica — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** quattro difetti piccoli dei nutrienti (S4):
- la vitamina E arriva per 2329 alimenti invece di 595, e la vitamina A entra (1922 alimenti);
- «Cambia alimento» trova «Pâtes» scrivendo «pates», e cercando «riz» mette il riso prima dell'amido di riso;
- un valore sotto la cifra mostrata si legge «< 0,01 mg», non «0 mg»;
- un peso deciso su un'unità che poi riceve la sua canonica passa alla coppia canonica, invece di restare orfano e far richiedere quella coppia.

**Architecture:**
- **Le vitamine.** Nel file del 2025 «Vitamine E» e «Alpha-tocophérol (vitamine E)» non hanno mai un valore sulla stessa riga (misurato il 2026-11-23: 595 e 1734 alimenti, 0 in comune). `domain/ciqual.py` impara un ripiego per chiave: se la colonna principale non ha un valore, legge la seconda. La vitamina A legge «Activité vitaminique A, équivalents rétinol», che CIQUAL dà già in equivalenti: nessuna somma da fare. I valori si leggono da `ciqual_foods` con una join (spec S4, decisione 5), quindi rilanciare `load_ciqual` aggiorna ogni ingrediente già abbinato.
- **La ricerca.** `search_foods` confronta il nome **piegato**, cioè in minuscolo, senza accenti e con gli spazi ridotti, con la stessa piega del testo cercato. È la `translate()` con `FOLD_FROM`/`FOLD_TO` che `repositories/ingredients.py` usa già (`_folded`). A parità di punteggio spareggia come `find_candidates`: prima il nome che comincia con la prima parola, poi la `similarity` di tutto il nome, poi il nome.
- **«< 0,01».** `formatNutrient` (frontend) scrive «< ‹la cifra più piccola›» quando un valore non zero, arrotondato alle cifre che mostra, darebbe zero.
- **I pesi.** Una funzione sola in `services/unit_grams.py` (l'unico che scrive `ingredient_unit_grams`) rimette ogni riga sulla coppia che `resolve_pair_unit` darebbe oggi. Lo chiama chi dà una canonica a un'unità (`decide_unit_forms`, `decide_units imposta`), e `decide_grams` prima di cercare le coppie da pesare.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 async, Postgres 16 con `pg_trgm`, pytest su Postgres vero; React 19, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-13-s4-nutrienti-ingrediente-design.md` (§4.3 i nutrienti letti, decisione 5 la join, decisione 14 «Cambia alimento», §4.21–4.23 i pesi sull'unità canonica). Le voci di `next-steps.md` [S4]: «Le vitamine E e A da CIQUAL…», «La ricerca in CIQUAL dell'Anagrafica («Cambia alimento», `search_foods`)…», «In «Valori nutrizionali» un valore sotto 0,005…», «Un peso deciso su una unità che poi diventa canonica…». Lo spareggio viene da `find_candidates`, ottava lezione di `CLAUDE.md`.

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/s4-rifiniture`, ramo `night/s4-rifiniture`, creato da `master`. Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì. **Nessun push, nessun merge, nessun deploy. Mai `git stash`. Niente letture o scritture sulla produzione, e mai il `.env` del checkout principale. `load_ciqual` non si lancia mai fuori dai test e dallo stack e2e**: ricaricare la produzione è un passo di Mattia (Task 5).
- **Una cucitura sola con gli altri piani della notte.** `2026-11-23-anagrafica-revisioni.md` (ramo `night/anagrafica-revisioni`) aggiunge `inherit_grams` a `services/unit_grams.py`: funzioni diverse dello stesso file, la seconda che arriva su `master` si cuce al merge, e il report lo dice. Per il resto nessuno tocca `domain/ciqual.py`, `repositories/ciqual.py`, `services/unit_grams.py` (salvo quella funzione), `services/unit_forms.py`, `cli/decide_units.py`, `cli/decide_grams.py` o `frontend/src/lib/nutrients.ts`. `2026-11-23-pulizie.md` aggiunge la migrazione `0027`: questo piano **non ne scrive**.
- **`find_candidates` non cambia.** È la ricerca dei candidati per l'AI. La piega degli accenti lì cambierebbe le risposte del pilota (`tests/services/test_s4_pilot.py`), e resta fuori scope.
- **Mancante resta mancante** (`CLAUDE.md`). Il ripiego legge la seconda colonna solo se la prima è **vuota**. Una cella illeggibile nella prima si conta illeggibile come oggi, e non si sostituisce. La vitamina A non si calcola mai da retinolo e beta-carotene.
- **Prima lezione di `CLAUDE.md`: l'oggetto provato è quello che gira.** Le prove della ricerca passano da `search_foods`, anche sulla tabella vera (`tabella_vera` di `tests/ciqual_veri.py`). Quelle delle vitamine leggono il file vero con `read_ciqual`. Quelle dei pesi passano da `decide_grams`, `decide_unit_forms` e dal comando `decide_units`.
- Le parole a video e quelle stampate dai comandi **si copiano esatte** da questo piano (fra «»). Gli identificatori in inglese, i commenti in italiano.
- **Il type check è `npm run typecheck`**, mai `tsc --noEmit`. Controlli del frontend, da `<worktree>/frontend`: `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- **Il carico sulla macchina**: al massimo 6 thread e 8 GB (Mattia, 2026-11-22). Le suite intere girano dentro `systemd-run --user --scope -p MemoryMax=8G -p CPUQuota=600% …`, mai due insieme. Vitest gira con `--maxWorkers=4`, pytest senza parallelismo.
- **Backend su Postgres vero**: `spena-db-1` (porta 5433), con il database `spena_test_s4_rifiniture`. Mai `docker compose up` dal worktree. Si usa il `.venv` del checkout principale. Il comando di pytest, da `<worktree>/backend`:
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_s4_rifiniture \
    PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
- **e2e** sullo stack `spena-e2e`, con i comandi delle Global Constraints di `docs/superpowers/plans/2026-11-18-suggerimenti-elenco-intero.md`: il `.env` da `.env.example`, cancellato alla fine; `-p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml` in ogni comando; il seme con le ricette e le due righe della fixture CIQUAL; `down -v` e `rm .env` sempre. Se lo stack c'è e non l'hai alzato tu, aspetta che sparisca.
- Nessuna dipendenza nuova, **nessuna migrazione, nessuna estensione nuova** (`unaccent` c'è nell'immagine, ma vorrebbe una migrazione: vedi decisione 4).

## Review Focus

1. **Il ripiego non inventa**: una riga con «Vitamine E» vuota e «Alpha-tocophérol» piena prende la seconda; con la prima illeggibile, la vitamina E resta assente e conta fra le illeggibili; con le due vuote, assente. Task 1.
2. **Il file vero** dà 2329 alimenti con la vitamina E e 1922 con la A, e nessuna colonna in un'unità sbagliata. Task 1.
3. **«riz» sulla tabella vera**: le prime righe cominciano con «Riz», e «Riz blanc, cru» è fra le prime tre. «pates» trova «Pâtes sèches, standard, crues». Il codice esatto resta primo, e `%` e `_` restano lettere. Task 2.
4. **Un valore zero dichiarato** («traces», 0) resta «0 mg». Solo un valore non zero che l'arrotondamento farebbe zero diventa «< 0,01 mg». Task 3.
5. **Due pesi sulla stessa coppia dopo lo spostamento**: vince quello a mano su quello dell'AI; a parità, resta quello della canonica. Nessun `IntegrityError` dal vincolo `uq_ingredient_unit_grams`. Task 4.

### Preparazione (una volta, prima del Task 1)

- [ ] Il worktree, con `node_modules` collegato e nessun `.env`:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/s4-rifiniture -b night/s4-rifiniture master
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/s4-rifiniture/frontend/node_modules
  ```
- [ ] Il database dei test:
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_s4_rifiniture WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_s4_rifiniture'
  ```
- [ ] Le quattro voci di `next-steps.md` che citano questo piano passano a `in corso` (` → in corso su night/s4-rifiniture`), e si committa: `next-steps: le rifiniture di S4, in corso`.
- [ ] La linea di partenza: pytest e vitest dal worktree, tutto verde. **Annota** i numeri. Se non è verde, fermati e scrivilo nel report.

---

## Decisioni prese

1. **La vitamina E: «Vitamine E», e «Alpha-tocophérol (vitamine E)» dove la prima è vuota** (Claude, su delega).
   - Le due colonne sono disgiunte nel file del 2025, quindi leggere «la seconda dove manca la prima» dà gli stessi valori di leggerle tutte e due, e nessun valore di oggi cambia: i 595 restano quelli.
   - La principale resta «Vitamine E» (oggi letta): se un'edizione futura le riempisse tutte e due, vince il totale, che è quel che l'etichetta chiama «Vitamina E».
   - Le due sono in mg, come il vocabolario.
2. **La vitamina A: «Activité vitaminique A, équivalents rétinol (µg/100 g)»** (Claude, su delega). Il motivo che la teneva fuori (spec §4.3: «la somma in equivalenti è un calcolo che non si fa senza dirlo») non vale per questa colonna: il calcolo lo fa CIQUAL e lo dice nel nome. Retinolo (2584) e beta-carotene (2050) restano non usati. Dove l'attività manca, la vitamina A manca: niente ripiego sul retinolo, che sarebbe un'altra grandezza.
3. **Il ripiego è una mappa a parte**, `CIQUAL_FALLBACKS: dict[str, tuple[str, ...]]`, e non un secondo nome in `CIQUAL_NAMES` (Claude, su delega). Un secondo nome in `CIQUAL_NAMES` vuol dire «lo stesso costituente scritto in un altro modo»: `map_columns` ne prende una colonna sola, la prima. Il ripiego invece è un'altra colonna, letta riga per riga. La sua unità si controlla come quella della principale: un ripiego nell'unità sbagliata rifiuta il file. Le colonne di ripiego non stanno fra le `unused`.
4. **La piega degli accenti è la `translate()` che c'è già, non `unaccent`** (Claude, su delega).
   - `unaccent` è nell'immagine (`pg_available_extensions`), ma vorrebbe un `CREATE EXTENSION` in una migrazione, e la notte ne ha già una in un altro ramo.
   - Misurato il 2026-11-23: dopo `lower()`, ogni lettera non ASCII dei 3484 nomi del file è in `FOLD_FROM` (é à è â ê ô û î ï ç ë). Restano fuori «…», «°» e uno spazio non separabile, che non sono lettere.
   - `lower()` piega anche «É» e «Â» perché i database sono `en_US.utf8` (verificato sul container dei test; la produzione usa la stessa immagine).
   - La piega è la stessa dei suggerimenti: apostrofi e trattini diventano spazi, e gli spazi, a capo compresi (i nomi del file vanno a capo), si riducono a uno, dopo la `translate()`.
5. **L'ordine di `search_foods`**: il codice esatto; poi la `word_similarity` piegata; poi il nome che comincia con la prima parola piegata (`_first_word`, che c'è già); poi la `similarity` piegata di tutto il nome; poi il nome. Il filtro resta quello di oggi (codice esatto, pezzo di nome, `word_similarity` ≥ `SEARCH_MIN_SIMILARITY`), sui due lati piegati.
6. **«< ‹cifra›» per ogni unità, anche le kcal** (Claude, su delega: è come si scrive un numero). Le cifre restano quelle di oggi: 0 per le kcal, 2 sotto l'unità, 1 sopra. Quando un valore maggiore di zero si scriverebbe «0», si scrive «< 0,01 mg», «< 0,01 µg», o «< 1 kcal». È la forma che «Spese dell'AI» usa già («< 0,0001 $»).
7. **Dove va un peso che non sta sulla sua coppia** (Claude, su delega). La coppia giusta di una riga è quella che `resolve_pair_unit` dà alla sua unità oggi:
   - la canonica;
   - il pezzo (`unit_id` NULL) se la canonica è un pezzo;
   - nessuna, se la canonica è di massa o di volume.

   Una riga fuori posto:
   - se la coppia giusta è libera, **si sposta**, con i suoi grammi, `decided_by` e `decided_at`;
   - se è occupata, **si fonde**: resta il peso a mano rispetto a quello dell'AI (la regola del modulo: «il peso a mano vince sempre»), e a parità quello che c'era già sulla canonica, perché è quello che le ricette sulla canonica usavano;
   - se non c'è coppia (massa o volume), **si toglie**: i grammi si contano da sé.
8. **I pesi orfani di oggi si sistemano da sé** al primo `decide_grams` dopo il deploy, che riallinea prima di cercare le coppie da pesare, e lo dice. Non serve una migrazione di dati, e nessuna chiamata all'AI parte per una coppia che il riallineamento ha già coperto.

## Margine di autonomia

- Liberi: i nomi interni e dei test, i nomi dei campi del risultato del riallineamento (suggeriti `moved`, `merged`, `dropped`), le parole dei commenti.
- Fissi: `CIQUAL_FALLBACKS`, le colonne scelte, l'ordine della decisione 5, le parole stampate fra «», le regole della decisione 7.
- **Fermati** (voce `bloccato` nel report) se il file vero ha una riga con «Vitamine E» **e** «Alpha-tocophérol» tutte e due piene: la decisione 1 è stata presa sull'assenza di questa riga.

---

### Task 1: le vitamine E e A

**Files:**
- Modify: `backend/app/domain/ciqual.py` (`CIQUAL_NAMES["vitamin_a"]`, `CIQUAL_FALLBACKS`, `ColumnMap.fallbacks`, `map_columns`, `food_from_row`, il commento sopra `CIQUAL_NAMES`)
- Test: `backend/tests/domain/test_ciqual.py`, `backend/tests/services/test_ciqual_file.py`, `backend/tests/domain/test_nutrients.py`
- Modify: la spec S4, §4.3: una riga datata che dice che la A entra dall'attività in equivalenti e la E col ripiego

**Interfaces:**
- Produces:
  - `CIQUAL_NAMES["vitamin_a"] = ("activite vitaminique a, equivalents retinol",)`;
  - `CIQUAL_FALLBACKS = {"vitamin_e": ("alpha-tocopherol (vitamine e)",)}`;
  - `ColumnMap.fallbacks: dict[str, int]` (chiave → indice della colonna di ripiego). È presente solo se il file ha anche la principale; se il file ha solo il ripiego, il ripiego diventa la colonna della chiave.
  - `food_from_row` legge il ripiego solo quando `parse_teneur` della principale dà `None`.
  - `CiqualFile` e `load_ciqual` non cambiano firma: `with_value["vitamin_e"]` conta gli alimenti che hanno l'una o l'altra.

- [ ] **Step 1: I test che falliscono.**
  - `test_map_columns_riconosce_le_intestazioni_vere_del_2025` resta, con in più `colonne.nutrients["vitamin_a"] == 62` e `colonne.fallbacks == {"vitamin_e": 68}` (gli indici di `INTESTAZIONE_2025`: controllali nella lista), e «Alpha-tocophérol» non è fra le `unused`.
  - `test_i_nomi_coprono_il_vocabolario_tranne_cinque` diventa `…_tranne_quattro`: `{"biotin", "fluoride", "chromium", "molybdenum"}`, con la docstring nuova. Anche i nomi di `CIQUAL_FALLBACKS` sono già normalizzati.
  - `test_il_ripiego_della_vitamina_e`, tabellare su `food_from_row`, con un'intestazione corta (codice, nome, le quattro d'obbligo, «Alpha-tocophérol (vitamine E) (mg/100 g)», «Vitamine E (mg/100 g)»):

    | «Vitamine E» | «Alpha-tocophérol» | vitamina E | illeggibili |
    |---|---|---|---|
    | «0,5» | vuota | 0,5 | — |
    | vuota | «1,2» | 1,2 | — |
    | «-» | «< 0,2» | 0,1 | — |
    | «n.d.» | «1,2» | assente | `vitamin_e` |
    | vuota | vuota | assente | — |
  - `test_un_ripiego_nell_unita_sbagliata_rifiuta_il_file`: «Alpha-tocophérol (vitamine E) (µg/100 g)» → `CiqualFormatError` che nomina la colonna.
  - `test_solo_il_ripiego_vale_come_colonna`: senza «Vitamine E», la colonna di `vitamin_e` è quella di «Alpha-tocophérol», e `vitamin_e` non è fra le `absent`.
  - In `test_ciqual_file.py`, `test_la_tabella_vera_ha_le_vitamine_e_e_a`: `read_ciqual(CANDIDATE_FILES[0])`, `with_value["vitamin_e"] == 2329`, `with_value["vitamin_a"] == 1922`, nessuna illeggibile per le due. I numeri sono stati misurati sulle righe con un codice. Se `read_ciqual` dà un numero diverso, controlla che la differenza siano righe doppie o senza nome (`duplicate_codes`, `skipped_rows`), usa il suo numero e scrivilo nel report.
  - In `test_nutrients.py`, `test_vocabulary_holds_fields_not_collected_yet` usa `biotin` al posto di `vitamin_a`: la A ora una fonte ce l'ha.
- [ ] **Step 2: Falliscono** (il comando di pytest con i tre file).
- [ ] **Step 3: Il codice.** In `map_columns` i nomi del ripiego si cercano come quelli principali, con lo stesso controllo dell'unità. Il commento sopra `CIQUAL_NAMES` cambia la frase sulla vitamina A con le decisioni 1 e 2, in due righe.
- [ ] **Step 4: Passano**, con `tests/domain/test_ciqual.py`, `tests/services/test_ciqual_file.py`, `tests/test_load_ciqual_cli.py`, `tests/api/test_nutrition.py`, `tests/services/test_recipe_nutrition_service.py`. Poi la suite intera.
- [ ] **Step 5: Commit**: `ciqual: la vitamina E col ripiego sull'alfa-tocoferolo, la A dall'attività in equivalenti`.

### Task 2: «Cambia alimento» senza accenti, e lo spareggio

**Files:**
- Modify: `backend/app/repositories/ciqual.py` (`search_foods`, un `_folded_name()` accanto)
- Test: `backend/tests/repositories/test_ciqual_repository.py`

**Interfaces:**
- Consumes: `FOLD_FROM`, `FOLD_TO`, `fold_for_match` da `app.domain.suggestions`; `_first_word`, che c'è già.
- Produces: `search_foods(session, query: str, limit: int) -> list[CiqualFood]`, stessa firma. L'espressione piegata è `regexp_replace(translate(lower(name_fr), FOLD_FROM, FOLD_TO), '\s+', ' ', 'g')`. Il testo cercato si piega con `fold_for_match(text.lower())`. Il codice esatto si confronta col testo com'è, senza piega.

- [ ] **Step 1: I test che falliscono.**
  - `test_search_foods_ignora_gli_accenti` (fixture): «pates seches» → il primo è «Pâtes sèches, crues»; «PÂTES» e «pâtes» trovano tutti e due gli alimenti «Pâtes …».
  - `test_search_foods_a_parita_comincia_con_la_parola`, con `ALIMENTI_VERI` (`upsert_foods`): «riz» → il primo è «Riz blanc, cru» (oggi è «Amidon de riz», per l'ordine alfabetico).
  - `test_search_foods_sulla_tabella_vera` (`tabella_vera`): con `limit=20`,
    - «riz»: le prime cinque cominciano con «Riz», e «Riz blanc, cru» è fra le prime tre;
    - «pates»: «Pâtes sèches, standard, crues» è fra le prime tre.
  - I due test di oggi (`…per_codice_e_per_pezzo_di_nome`, `…non_usa_jolly`) restano come sono.
- [ ] **Step 2: Falliscono** (il comando di pytest con quel file).
- [ ] **Step 3: Il codice**, con l'ordine della decisione 5. Un testo che dopo la piega è vuoto («-», «'») risponde `[]`, come oggi una stringa vuota. La docstring di `search_foods` dice la piega, perché `translate()` e non `unaccent` (decisione 4, in una riga), e lo spareggio, citando la docstring di `find_candidates`.
- [ ] **Step 4: Passano**, con tutto il file e `tests/api/test_nutrition.py` (la rotta della ricerca). Poi la suite intera.
- [ ] **Step 5: Commit**: `anagrafica: «Cambia alimento» ignora gli accenti e a parità mette prima il nome che comincia con la parola`.

### Task 3: «< 0,01» invece di «0»

**Files:**
- Modify: `frontend/src/lib/nutrients.ts` (`formatNutrient` e la sua docstring)
- Test: `frontend/src/lib/nutrients.test.ts`

- [ ] **Step 1: I test che falliscono**, nella tabella di oggi:
  - `[0.003, "mg", "< 0,01 mg"]`, `[0.0049, "µg", "< 0,01 µg"]`, `[0.3, "kcal", "< 1 kcal"]`;
  - quelli che non cambiano: `[0.005, "mg", "0,01 mg"]`, `[0, "mg", "0 mg"]`, `[0.25, "g", "0,25 g"]`.
- [ ] **Step 2: Falliscono**: `npx vitest run --maxWorkers=4 src/lib/nutrients.test.ts`.
- [ ] **Step 3: Il codice.** Se `value > 0` e il numero scritto con quelle cifre è zero, si scrive «< » e la cifra più piccola (`10 ** -digits`), scritta con lo stesso `toLocaleString`. Il resto non cambia. `UnitWeights` usa la stessa funzione per i grammi, che sono sempre almeno 0,01 (`Numeric(8, 2)`, `> 0`): lì non cambia niente.
- [ ] **Step 4: Passano**, poi i controlli interi del frontend.
- [ ] **Step 5: Commit**: `nutrienti: un valore sotto la cifra mostrata si legge «< 0,01», non zero`.

### Task 4: i pesi seguono l'unità canonica

**Files:**
- Modify: `backend/app/services/unit_grams.py` (`realign_weights`, `Realigned`; `decide_grams` lo chiama per primo; `GramsRun.realigned`; la docstring del modulo)
- Modify: `backend/app/services/unit_forms.py` (`decide_unit_forms`, dopo il ciclo, con gli id delle unità applicate)
- Modify: `backend/app/cli/decide_units.py` (dopo `set_unit_forms`), `backend/app/cli/decide_grams.py` (la riga stampata)
- Test: `backend/tests/services/test_unit_grams.py` (gli helper `_mondo`, `_unita`), `backend/tests/services/test_unit_forms.py`, `backend/tests/test_decide_units_cli.py`, il file dei test di `decide_grams` (`grep -rl "decide_grams" backend/tests`)

**Interfaces:**
- Produces: `async def realign_weights(session: AsyncSession, unit_ids: Collection[uuid.UUID] | None = None) -> Realigned`. Prende le righe con `unit_id` non NULL (di quelle unità, o di tutte) che non stanno sulla coppia di `resolve_pair_unit`, e le sposta, le fonde o le toglie secondo la decisione 7. Fa `flush`, non `commit`.
- Produces: `@dataclass(frozen=True) class Realigned: moved: int; merged: int; dropped: int`, con `total` = la somma.
- `decide_grams` lo chiama prima di `pending_pairs`, e `GramsRun.realigned: int` porta il totale.
- Il comando `decide_grams` stampa, se è più di zero, «‹n› pesi spostati sull'unità canonica.» (con 1: «1 peso spostato sull'unità canonica.»).

- [ ] **Step 1: I test che falliscono.** «cucchiaio» è decisa; «cucchiai» non lo è ancora; l'olio ha un peso dell'AI su «cucchiai».
  - `test_il_peso_passa_alla_canonica_quando_l_unita_la_riceve`: `apply_forms(cucchiai, "cucchiaio", "cucchiai")`, poi `realign_weights(session, [cucchiai.id])`. La riga è su «cucchiaio», con i grammi, `decided_by` e `decided_at` di prima; `moved == 1`; `pending_pairs` non ha la coppia (olio, cucchiaio).
  - `test_fondendo_vince_il_peso_a_mano`, tabellare su chi ha deciso la riga della forma e quella della canonica:

    | sulla forma | sulla canonica | resta |
    |---|---|---|
    | a mano | AI | quella a mano, sulla canonica |
    | AI | a mano | quella della canonica |
    | AI | AI | quella della canonica |
    | a mano | a mano | quella della canonica |

    Ogni volta una riga sola per la coppia, e `merged == 1`.
  - `test_un_peso_su_un_unita_diventata_di_massa_si_toglie`: la canonica è «grammo» (o un'altra di massa secondo `classify_unit`); la riga sparisce, `dropped == 1`.
  - `test_un_peso_su_un_unita_diventata_pezzo_va_sul_pezzo`: la canonica si classifica pezzo; la riga va su `unit_id` NULL.
  - `test_decide_grams_riallinea_prima_di_chiedere`: l'orfano c'è già (l'unità ha `canonical_id` e la riga è sulla forma). Il client finto dell'AI fallisce il test se viene chiamato. `decide_grams` non lo chiama, e `realigned == 1`.
  - In `test_unit_forms.py`: `decide_unit_forms`, con la risposta finta che dà a «cucchiai» il singolare «cucchiaio», sposta il peso.
  - In `test_decide_units_cli.py`: `imposta cucchiai cucchiaio cucchiai` sposta il peso.
  - Il comando `decide_grams` con un orfano stampa «1 peso spostato sull'unità canonica.».
- [ ] **Step 2: Falliscono** (il comando di pytest con quei file).
- [ ] **Step 3: Il codice.**
  - `realign_weights` legge le righe candidate con le loro unità, calcola la coppia giusta con `resolve_pair_unit` una volta per unità, e per ogni riga fuori posto cerca la riga sulla coppia giusta (stesso ingrediente). Poi sposta (`UPDATE … SET unit_id`), fonde (aggiorna la riga che resta, se vince la forma, e cancella l'altra) o toglie.
  - La docstring del modulo dice che questo è il terzo modo in cui il modulo scrive, e perché. Quella del modello `IngredientUnitGrams` («Sempre sull'unità canonica») aggiunge chi tiene vera la frase quando un'unità riceve la canonica dopo.
- [ ] **Step 4: Passano**, con tutti i file del Task, `tests/services/test_unit_grams_ai.py`, `tests/services/test_s4_pilot_grams.py`, `tests/api/test_nutrition_weights.py`. Poi la suite intera.
- [ ] **Step 5: Commit**: `pesi: una unità che riceve la canonica le porta i suoi pesi`.

### Task 5: e2e, la verifica, il backlog

- [ ] **Step 1: e2e intera**, con i comandi delle Global Constraints, dentro il limite di carico.
- [ ] **Step 2: Nel browser**, sullo stack e2e prima del `down`, a 375 px, in Anagrafica:
  - «Cambia alimento» su un ingrediente, cercando «pates»: compaiono gli alimenti «Pâtes …» della fixture;
  - i «Valori nutrizionali» di un ingrediente abbinato si leggono, nei due temi.

  Uno screenshot della ricerca va nel report.
- [ ] **Step 3: Il backlog.** Le quattro voci passano a `fatto <data>` in «Fatti (recenti)», con ` → branch night/s4-rifiniture (da revisionare)`. In «Da fare a mano (solo Mattia)» si aggiungono due righe [S4]:
  - «Dopo il deploy di `night/s4-rifiniture`: `docker compose -f docker-compose.prod.yml exec backend python -m app.cli.load_ciqual --dry-run` (attese circa 2329 righe di vitamina E e 1922 di vitamina A), poi lo stesso senza `--dry-run`. I valori si leggono con una join: ogni ingrediente già abbinato li vede subito.»
  - «I pesi rimasti sulla forma di un'unità si spostano al primo `decide_grams` dopo il deploy, che lo dice («‹n› pesi spostati sull'unità canonica.»): niente da fare a parte, basta guardare la riga.»

  Commit: `next-steps: le rifiniture di S4, fatto`.

## Fuori scope

- La piega degli accenti in `find_candidates`, che cambierebbe le domande all'AI e il pilota: è un'idea a parte, da misurare.
- La vitamina A dal retinolo dove manca l'attività, e la vitamina D2/D3 (la D resta la colonna totale di oggi).
- Ricaricare CIQUAL in produzione: è il passo di Mattia scritto nel Task 5.
- I pesi di un'unità che perde la canonica (`reset_unit`, la pulizia delle dosi): restano sulla canonica, che è ancora un'unità vera.

## Comandi di verifica

- Backend: il comando di pytest delle Global Constraints, tutto verde, con i test nuovi.
- Frontend, da `<worktree>/frontend`: `npx vitest run --maxWorkers=4`, `npm run typecheck`, `npm run lint`, `npm run build`.
- e2e: la suite intera, verde.
- `git -C <worktree> diff master --stat` tocca solo i file dei task, più `next-steps.md`, la spec S4 e il report. Nessun file in `backend/alembic/versions/`.
