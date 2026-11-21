# S4: i candidati sulla tabella vera e i pesi che non si fermano — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** la ricerca dei candidati CIQUAL smette di perdere l'alimento semplice dietro i piatti che lo contengono, il nome italiano non aggiunge più rumore, il pilota dice se un caso è mancato per la ricerca o per la scelta, e `decide_grams` non si ferma più per sempre su un lotto a cui l'AI risponde con un JSON rotto. Chiude le due voci P2 di S4 in «Da fare a mano» (il pilota al 69% e le 222 coppie ferme).

**Architecture:** in `find_candidates` (`backend/app/repositories/ciqual.py`), a parità di `word_similarity` vince il nome che comincia con la prima parola del termine, poi la `similarity` di tutto il nome, poi l'alfabeto, nella query di ogni parola e nell'unione. `match_names` (`backend/app/services/ciqual_match.py`) cerca col nome italiano solo quando le parole dell'AI non trovano niente, e restituisce per ogni nome cosa ha cercato e quanti candidati ha visto; il pilota e `decide_ciqual` lo stampano. `decide_grams` (`backend/app/services/unit_grams.py`) divide a metà un lotto la cui risposta non si legge, fino alla coppia sola, salta per quel giro la coppia che non si legge nemmeno da sola, e va avanti. Nessuna migrazione, nessun cambio al frontend o alle API.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, pytest su Postgres vero con `pg_trgm`; l'LLM è quello del ramo `night/llm-haiku` (Claude Haiku 5.5 con l'SDK di Anthropic, `complete_json` unico ingresso), mai chiamato in rete nei test.

**Spec:** `docs/superpowers/specs/2026-10-13-s4-nutrienti-ingrediente-design.md` (§4.10, §4.11, §4.18, §4.23; §4.10 e §4.23 cambiano con questo piano, Task 5). Il §9 («un modello più forte») lo aggiorna il piano `docs/superpowers/plans/2026-11-21-llm-haiku.md`: qui non si tocca. I piani da cui viene il codice sono `docs/superpowers/plans/2026-10-13-s4-ciqual.md` e `docs/superpowers/plans/2026-10-13-s4-grammi.md`. Leggi `CLAUDE.md` del repo prima di cominciare: la prima lezione (un test che costruisce il suo oggetto non prova quello della produzione) e la sesta (un filtro dietro un limite) sono il cuore di questo piano.

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/s4-candidati`, ramo `night/s4-candidati`, creato da **`night/llm-haiku`** (non da `master`). Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì, mai dalla radice del checkout principale, che non si tocca (le modifiche non committate che ci trovi sono dell'utente). **Nessun push, nessun merge, nessun deploy. Mai `git stash`. Niente letture o scritture sulla produzione, e mai un `.env`. Nessuna chiamata vera a un modello, niente rete.**
- **Il piano è scritto sul codice di `master`; il ramo di partenza è `night/llm-haiku`.** Quel ramo sostituisce il client di OpenRouter con Claude Haiku via SDK di Anthropic, tiene `complete_json` come unico ingresso, dà a `LlmUnavailable` un tipo (`kind`: i tipi terminali — chiave assente, autenticazione, credito — fermano i comandi; quelli di passaggio e la risposta troncata valgono per la singola richiesta) e registra l'uso anche delle chiamate fallite. **Leggi ogni file com'è sul ramo prima di cambiarlo**, e **usa i nomi che il ramo ha davvero** — il nome dell'enum dei tipi, i suoi valori, l'eventuale insieme o predicato dei tipi terminali, il finto dei test che sostituisce il client, la variabile della chiave nei fixture `chiave` — anche dove questo piano, scritto prima, ne cita altri (`LlmUnavailable`, `FakeLlm`, `OPENROUTER_API_KEY`, `finto.bodies`). Ogni nome diverso va nel report. Se il ramo ha già cambiato una funzione che questo piano tocca (per esempio il ciclo di `decide_grams` o di `match_names` sui guasti di passaggio), costruisci sopra quel che c'è e scrivi nel report cosa hai trovato.
- **Prima lezione di `CLAUDE.md`.** Le prove dell'ordine dei candidati chiamano `find_candidates`, la funzione che `match_names` usa in produzione, contro Postgres vero con `pg_trgm`; una di esse carica **la tabella vera** (`data/ciqual/ciqual-2025.xlsx`, già nel repository) con `read_ciqual` e `upsert_foods`, cioè lo stesso percorso di `load_ciqual`. Nessuna copia della query nei test.
- **Le soglie e le misure non si toccano**: `CANDIDATE_MIN_SIMILARITY = 0.3`, `SEARCH_MIN_SIMILARITY = 0.4`, `CANDIDATES = 15`, `MATCH_THRESHOLD = 0.9`, `GRAMS_THRESHOLD = 0.8`, `TERMS_BATCH`, `CHOICE_BATCH`, `GRAMS_BATCH`, i `*_MAX_TOKENS` (come sono sul ramo). `search_foods` (la ricerca di Anagrafica) non cambia.
- **Mai un vicolo cieco.** Un ingrediente senza candidati resta «nessun alimento adatto» come oggi (spec §4.13); una coppia saltata resta da pesare e si pesa a mano in Anagrafica, «Pesi per unità».
- **Backend su Postgres vero**: `spena-db-1` (porta 5433), con il database di questo ramo, `spena_test_s4_candidati`. Mai `docker compose up` dal worktree, mai `-f docker-compose.prod.yml`. Si usa il `.venv` del checkout principale. Il comando di pytest, da `<worktree>/backend`:
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_s4_candidati \
    PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
- **Nessuna dipendenza nuova, nessuna migrazione** (`git diff night/llm-haiku --stat -- backend/alembic/versions` resta vuoto), **nessun cambio al frontend** (`git diff night/llm-haiku --stat -- frontend` resta vuoto): per questo vitest ed e2e non servono.
- Le frasi stampate sono in italiano e **si copiano esatte** da questo piano (fra «»; ‹…› è un valore). Gli identificatori in inglese, i commenti in italiano.
- **I test di oggi si cambiano solo dove il piano lo dice**: le due righe di `match_report` per «uova» e «riso» in `test_il_rapporto_dice_soglia_casi_e_spesa` (Task 3); l'espressione del pomodoro dove un test la cita dal file del repository (Task 3); la frase di `final_line` se il Task 3 la cambia. Le asserzioni aggiunte a un test di oggi (`no_candidates` nel Task 2) non sono cambi. Il resto, se cade, è un comportamento cambiato: si corregge il codice.

### Preparazione (una volta, prima del Task 1)

- [ ] **Il ramo di partenza.**
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify night/llm-haiku
  git log -1 --format='%h %s' night/llm-haiku
  git show night/llm-haiku:next-steps.md | grep -n "2026-11-21-llm-haiku.md"
  ls .worktrees/s4-candidati 2>&1 | head -1
  ```
  Expected: un hash (**annotalo**: è `BASE` del Task 5); la voce di llm-haiku **`fatto … (da revisionare)`** sul suo ramo; `No such file or directory`. Se il ramo non c'è, o la sua voce non è `fatto` (è `in corso` o `bloccato`), fermati: la voce di questo piano passa a `bloccato` con «attende: night/llm-haiku finito», e lo scrivi nel messaggio finale della notte. Se il worktree esiste già, fermati e scrivilo.
- [ ] **Il database dei test di questo ramo**:
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_s4_candidati WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_s4_candidati'
  ```
- [ ] **Il worktree**, senza `.env`:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/s4-candidati -b night/s4-candidati night/llm-haiku
  ls .worktrees/s4-candidati/data/ciqual/ciqual-2025.xlsx
  ```
  Expected: il file c'è (è committato; md5 `0d9758ce23f3f13dd63a005bc1bb4f2c`).
- [ ] **I nomi del ramo.** Da `<worktree>/backend`, leggi `app/services/llm.py` (`LlmUnavailable`, il suo `kind`, i valori dell'enum, se c'è un insieme o un predicato dei terminali), `tests/llm_fakes.py` o il modulo che lo ha sostituito (come un test fa arrivare una risposta che non è JSON, una risposta troncata, un guasto terminale), e `app/services/unit_grams.py` (`decide_grams`: cosa fa oggi su un guasto). **Annota** i nomi: servono al Task 4 e al report. Se `import anthropic` fallisce nel `.venv` del checkout principale, il report di llm-haiku dice come la sua notte ha installato la dipendenza: fai lo stesso, con la stessa versione.
- [ ] **La testa di Alembic**, da `<worktree>/backend`: `DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_s4_candidati PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" alembic heads`. Expected: una riga sola (**annotala**; questo piano non ne aggiunge).
- [ ] **La voce del backlog.** In `next-steps.md` la voce che cita questo piano (`2026-11-21-s4-candidati.md`) passa a `in corso`, con in coda ` → in corso su night/s4-candidati`. Commit: `git commit -m "next-steps: i candidati di S4 sulla tabella vera e i pesi che non si fermano, in corso"`. Se la voce non c'è, aggiungila sotto «In corso» nello stile delle altre, con `[S4]`.
- [ ] **La linea di partenza**: pytest dal worktree, tutto verde. **Annota** `N_pytest`. Se non è verde, fermati: va nel report.

---

## Obiettivo e contesto

Il 2026-10-20 CIQUAL 2025 è stato caricato in produzione (3.484 alimenti) e il pilota `s4_pilot` ha dato 20 abbinamenti giusti su 29 (69%, soglia 90%); `decide_ciqual` non è partito. Lo stesso giorno `decide_grams` ha scritto 573 pesi e poi si è fermato: a ogni giro l'AI risponde allo stesso lotto con un JSON rotto («Expecting ':' delimiter»), e le 222 coppie restanti non si chiedono più.

La ricerca del 2026-11-21, sul file vero letto con `read_ciqual` e sulla query riprodotta in un database usa e getta, dice che il pilota non misurava il modello:

- **`word_similarity` vale 1,0 per ogni nome che contiene la parola.** Sulla tabella vera «riz» arriva a 1,0 con 43 nomi, «tomate» con 54, «sel» con 73, «pomme de terre» con 42. A parità, `find_candidates` ordina per nome (`order_by(score.desc(), CiqualFood.name_fr)`, e lo stesso nell'unione): «Amidon de riz», «Boisson au riz», «Riz au lait» passano prima di «Riz blanc, cru», e il riso crudo resta fuori dai 15. Su 24 gruppi di parole plausibili per i casi mancati, senza il nome italiano, **12 non hanno l'alimento atteso fra i candidati**; con il nuovo ordine **nessuno** (il peggiore è al posto 11: «saumon atlantique cru / filet de saumon»).
- **Il nome italiano fra le parole aggiunge rumore**: «sale» trova «Eau minérale Salvetat» (1,0), «Salers» (0,8), «Salade de riz au thon» (0,6); con il nome italiano «sel fin / sel de table» non porta nessun sale fra i 15, senza lo porta al posto 9. In nessuno dei 24 gruppi il nome italiano ha aiutato.
- **Il pomodoro era un caso sbagliato**: nella 2025 non c'è «Tomate, crue»; l'alimento generico è «Tomate sans précision, crue (aliment moyen)» (20385).
- **Il pollo**: l'AI ha scelto «Poulet blanc, viande et peau crues»; la tabella ha «Poulet, filet sans peau cru» (36017).
- **I pesi**: `GRAMS_BATCH = 40`; un `json.loads` che fallisce diventa `LlmUnavailable`, `decide_grams` fa `break`; `pending_pairs` restituisce le coppie sempre nello stesso ordine, e `--limit` prende le prime N, quindi niente scavalca il lotto rotto.

## Decisioni prese

Di Mattia (2026-11-21):

1. **Prima si corregge la ricerca dei candidati, poi si rifà il pilota**: l'ordine a parità di punteggio (prima il nome che comincia con la parola) e il nome italiano tolto dalle parole di ricerca, o tenuto solo come ripiego quando le parole dell'AI non trovano niente (la scelta fra le due è delegata a Claude: decisione 6).
2. **Il pomodoro** in `backend/app/data/s4_pilota.json` aspetta `^tomate (sans precision|ronde), crue`: l'alimento generico 20385 «Tomate sans précision, crue (aliment moyen)», o «Tomate ronde, crue».
3. **Il petto di pollo**: il pilota continua ad aspettare il filetto senza pelle (`^poulet, (filet|blanc)` non cambia), e il prompt della scelta aggiunge una riga sulla pelle e sulle ossa (decisione 9).
4. **Il «modello forte» del §9 di S4 è superato**: lo scrive il piano llm-haiku nella spec; questo piano non lo ripete.
5. **Il pilota si rifà una volta sola, sul server, dopo il deploy di Haiku**, da Mattia; poi `decide_ciqual` e `decide_grams` («Dopo il deploy»).

Del piano (Claude, tecniche; Mattia le rivede nel report):

6. **Il nome italiano resta solo come ripiego.** `match_names` cerca con le parole dell'AI; se non trovano nemmeno un candidato, cerca col nome italiano. Perché il ripiego e non la cancellazione: aggiunto sempre, il nome italiano porta rumore in una lista che ha già i candidati giusti (i 24 gruppi lo mostrano); da solo, quando la lista è vuota, non può peggiorare niente e recupera i nomi che CIQUAL scrive in italiano (ricotta, mascarpone, gorgonzola, bresaola, provolone, pecorino ci sono tutti) se le parole dell'AI mancano. Costa una query, solo in quel caso.
7. **L'ordine dei candidati**, per ogni parola e nell'unione: `word_similarity` decrescente, poi «il nome comincia con la prima parola del termine» (vero prima di falso), poi `similarity(termine, nome)` decrescente, poi il nome. Nell'unione ogni alimento tiene il massimo di ciascuna delle tre misure fra le parole che lo hanno trovato (è la forma misurata). La prima parola è la prima sequenza di lettere, cifre, apostrofi e trattini del termine in minuscolo («Riz, cru» → «riz», «huile d'olive» → «huile»); il confronto è `lower(name_fr) LIKE '<parola>%'`, senza `unaccent`, che vorrebbe una migrazione e che la misura non chiede (con e senza dà gli stessi posti sui 24 gruppi). `Candidate.score` resta la `word_similarity` migliore.
8. **Il pilota e `decide_ciqual` dicono perché un caso è mancato.** `match_names` restituisce, per ogni nome di cui le parole si sono verificate, le parole, quanti candidati ha visto la scelta e se venivano dal nome italiano (`Searched`). Il pilota distingue «nessun candidato» da «l'AI non ha scelto fra N candidati», e «parole non verificabili» da «scelta non verificabile»; ogni riga ✗ e – porta le parole. `decide_ciqual` conta a parte, dentro «senza un alimento adatto», quelli senza nemmeno un candidato.
9. **La riga del prompt della scelta**, dopo quella sullo stato: «- Carne e pesce: senza pelle né ossa, se il nome non dice altro (per esempio "petto di pollo" è "filet sans peau", non "viande et peau").». Il prompt delle parole non cambia.
10. **`decide_grams` divide un lotto che non si legge.** Un guasto **della risposta** — troncata, non JSON, non un oggetto, fuori schema: i tipi che il ramo llm-haiku dà a una risposta arrivata ma inutilizzabile — divide il lotto a metà (`mid = len // 2`, prima metà `[:mid]`) e richiede le due metà, fino alla coppia sola; una coppia che non si legge nemmeno da sola si **salta per questo giro**: resta da pesare, si conta e si nomina, e il giro va avanti. Ogni altro guasto si comporta come sul ramo: i terminali (chiave assente, autenticazione, credito) fermano subito il giro, anche a metà di una divisione, e quel che è già scritto resta; quelli di passaggio (rete, tempo, 5xx, limite di frequenza) fanno quello che il ramo fa (su `master`, fermarsi). Perché non dividere anche su un guasto di passaggio: non dice niente del lotto, e dividere in un'interruzione di rete moltiplicherebbe le chiamate per niente.
11. **Il freno.** Se di un lotto, dopo la divisione, **nessuna** coppia ha avuto una risposta leggibile (tutte saltate), il giro si ferma con «nessuna coppia del lotto ha avuto una risposta leggibile, nemmeno da sola: ‹ultimo errore›»: il guasto non è nel lotto, e continuare costerebbe fino a 79 chiamate per ogni lotto da 40.
12. **Il pilota dei pesi non cambia** (20 coppie, un lotto, si ferma al guasto: è un pilota).

## Criteri di accettazione

- [ ] Sulla tabella vera, per i 24 gruppi di parole della ricerca, `find_candidates(…, limit=CANDIDATES)` ha l'alimento atteso fra i candidati, e il test lo mostra rosso con l'ordine di oggi.
- [ ] Le parole dell'AI che trovano candidati non si mescolano al nome italiano; quelle che non trovano niente passano al nome italiano.
- [ ] Ogni espressione di `s4_pilota.json` trova almeno un alimento della tabella vera (nessun caso «da rivedere» sul file del 2025).
- [ ] Il rapporto del pilota distingue «nessun candidato» da «l'AI non ha scelto», e le parole non verificabili dalla scelta non verificabile, con le parole su ogni riga; `decide_ciqual` dice quanti sono rimasti senza nemmeno un candidato.
- [ ] Un lotto di pesi con una risposta rotta si divide e si pesa; una coppia rotta da sola si salta, si nomina, resta da pesare e un giro dopo si richiede; un guasto terminale ferma subito; un lotto illeggibile anche coppia per coppia ferma il giro.
- [ ] Nessuna migrazione, nessun file del frontend toccato, nessuna soglia cambiata. Tutti i test di oggi passano, cambiati solo dove il piano lo dice.
- [ ] Spec §4.10 e §4.23, `CLAUDE.md`, `README.md`, `next-steps.md` e il report di questa notte sono aggiornati.

## Comandi di verifica

Da `<worktree>/backend`: il comando di pytest. Dalla radice di `<worktree>`:

```bash
git diff night/llm-haiku --stat -- backend/alembic/versions frontend
grep -n "CANDIDATE_MIN_SIMILARITY = 0.3\|SEARCH_MIN_SIMILARITY = 0.4" backend/app/repositories/ciqual.py
grep -n "MATCH_THRESHOLD = 0.9\|GRAMS_THRESHOLD = 0.8" backend/app/services/s4_pilot.py
grep -n "\*terms\[item.name\], item.name" backend/app/services/ciqual_match.py
grep -n '"atteso": "^tomate' backend/app/data/s4_pilota.json
```

Expected: il primo vuoto; il secondo due righe; il terzo due righe; il quarto vuoto (il nome italiano non si aggiunge più alle parole: si cerca da solo, nel ripiego); l'ultimo una riga con `^tomate (sans precision|ronde), crue`.

## Review Focus

1. **Un termine che comincia con un articolo o un nome generico** («filet de saumon», «blanc de poulet»): la spinta del «comincia con» va alla famiglia sbagliata. L'alimento giusto deve restare fra i 15 lo stesso: i due gruppi sono nel test sulla tabella vera (Task 1, `test_la_tabella_vera_ha_l_alimento_fra_i_candidati`), al posto 11 e 9.
2. **I nomi con l'a capo** (889 dei 3.484, come «Sel blanc alimentaire, non iodé, non fluoré (marin,⏎ignigène ou gemme)»): `word_similarity`, `lower` e `LIKE` devono funzionare attraverso il `\n`. Il test sulla tabella vera li ha, e i dati di prova del Task 1 li copiano esatti.
3. **Parole dell'AI con maiuscole, virgole, parentesi o apostrofi** («Riz, cru», «(riz)», «huile d'olive»): la prima parola non deve diventare «riz,» o vuota (Task 1, `test_la_prima_parola_del_termine` e `test_maiuscole_e_punteggiatura_non_cambiano_l_ordine`).
4. **Una coppia che non si legge mai**, giro dopo giro (come potrebbe essere «aceto di mele × di»): ogni giro la salta, la nomina e va avanti, e il conto di quelle che restano la comprende (Task 4, `test_una_coppia_che_non_si_legge_da_sola_si_salta_e_il_giro_continua`).
5. **Il credito che finisce a metà di una divisione**: si ferma subito, quel che la prima metà ha scritto resta, nessuna chiamata dopo (Task 4, `test_un_guasto_terminale_durante_la_divisione_ferma_il_giro`).

## Fuori scope

- Il cambio di modello, il prompt delle parole, il client: piano `2026-11-21-llm-haiku.md`, da cui questo ramo parte. Il §9 della spec idem.
- Le soglie (0,3, 0,4, 90%, 80%), le misure dei lotti, i token massimi.
- `unaccent` o un indice trigram: vorrebbero una migrazione, e la misura non li chiede.
- La divisione dei lotti in `decide_ciqual` (che al primo guasto si ferma come `decide_grams` oggi) e lo stesso ordine in `search_foods` di Anagrafica: vanno come `idea` nel Task 5.
- Le tre correzioni in Anagrafica («aceto di mele» con l'unità «di», «acqua» un bicchiere 100 g, «alcol puro» senza unità 400 g): restano a Mattia, in «Da fare a mano».
- Gli altri casi del pilota: solo il pomodoro cambia.

## Margine di autonomia

- **Liberi:** nomi locali e privati non fissati qui, helper dei test, la forma della ricorsione o del ciclo che divide i lotti.
- **Fissi:** le frasi fra «»; l'ordine della decisione 7; il ripiego della decisione 6; la divisione e il freno delle decisioni 10–11; i nomi pubblici delle Interfacce prodotte; l'espressione del pomodoro.
- **I nomi del ramo `night/llm-haiku` vincono sul piano** (Global Constraints). Se il ramo non distingue una risposta rotta da un guasto di passaggio (un tipo solo per tutti e due), dividi su quel tipo e scrivilo nel report: il freno della decisione 11 tiene il costo limitato.
- **Una decisione di comportamento non coperta e non reversibile**: si ferma quel task, si committa il lavoro parziale, la voce del backlog passa a `bloccato` con «attende: …» e la domanda precisa, e si va al task dopo se non dipende da quello. Una scelta reversibile e a basso impatto: la più conservativa, annotata nel report.
- Un test che fallisce e non si risolve: niente test disattivati, niente asserzioni indebolite. `bloccato` con la diagnosi.

## Interfacce prodotte

- `find_candidates(session, terms, limit, min_similarity=CANDIDATE_MIN_SIMILARITY) -> list[Candidate]`: firma e `Candidate` invariati, ordine nuovo (decisione 7). `def _first_word(term: str) -> str` in `app.repositories.ciqual`.
- In `app.services.ciqual_match`: `@dataclass(frozen=True) class Searched: terms: tuple[str, ...]; candidates: int; by_italian_name: bool = False`; `MatchBatch.searched: dict[str, Searched]` (default vuoto); `CiqualRun.no_candidates: int = 0`; `CHOICE_SYSTEM_PROMPT` con la riga della decisione 9.
- In `app.services.s4_pilot`: `MatchOutcome.searched: Searched | None = None`.
- In `app.services.unit_grams`: `GramsRun.skipped: tuple[str, ...] = ()` (ogni voce `"‹ingrediente› × ‹unità›"`), `GramsRun.last_error: str | None = None`; `GRAMS_ALL_BROKEN = "nessuna coppia del lotto ha avuto una risposta leggibile, nemmeno da sola"`.

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `backend/app/repositories/ciqual.py`, `backend/tests/ciqual_veri.py` (nuovo), `backend/tests/repositories/test_ciqual_repository.py` | 1 | l'ordine dei candidati |
| `backend/app/services/ciqual_match.py`, `backend/app/cli/decide_ciqual.py`, `backend/tests/services/test_ciqual_match.py`, `backend/tests/test_decide_ciqual_cli.py` | 2 | il nome italiano come ripiego, cosa si è cercato, la pelle e le ossa |
| `backend/app/data/s4_pilota.json`, `backend/app/services/s4_pilot.py`, `backend/tests/services/test_s4_pilot.py` | 3 | il pomodoro e il rapporto che dice perché |
| `backend/app/services/unit_grams.py`, `backend/app/cli/decide_grams.py`, `backend/tests/services/test_unit_grams_ai.py`, `backend/tests/test_decide_grams_cli.py` | 4 | i lotti che si dividono |
| `docs/superpowers/specs/2026-10-13-s4-nutrienti-ingrediente-design.md`, `CLAUDE.md`, `README.md`, `next-steps.md`, `docs/night-reports/<data>.md` | 5 | documenti e report |

---

### Task 1: L'ordine dei candidati a parità di punteggio

**Files:**
- Create: `backend/tests/ciqual_veri.py`
- Modify: `backend/app/repositories/ciqual.py` (`find_candidates`, la docstring del modulo, `_first_word` nuova)
- Test: `backend/tests/repositories/test_ciqual_repository.py`

**Interfaces:**
- Produces: `ALIMENTI_VERI: list[CiqualRow]` e `async def tabella_vera(session) -> int` in `backend/tests/ciqual_veri.py` (si importa come `llm_fakes`: `from ciqual_veri import ALIMENTI_VERI, tabella_vera`); `_first_word`; l'ordine della decisione 7.

- [ ] **Step 1: I dati di prova.** `backend/tests/ciqual_veri.py`, con una docstring che dice: nomi, gruppi e codici veri di CIQUAL 2025 (l'a capo compreso, come lo legge `read_ciqual`), nutrienti vuoti; servono a riprodurre la parità di `word_similarity` che il pilota del 2026-10-20 ha incontrato sulla tabella vera, e che quattro righe inventate non fanno mai vedere. `tabella_vera` carica il file del repository con `read_ciqual(CANDIDATE_FILES[0])` (da `app.cli.load_ciqual`) e `upsert_foods`, e restituisce quanti alimenti ha scritto.
  ```python
  ALIMENTI_VERI = [
      CiqualRow("4041", "Aligot (purée de pomme de terre à la tomme fraîche),\npréemballé", "plats composés", {}),
      CiqualRow("96781", "Amidon de riz", "farines", {}),
      CiqualRow("37002", "Base de pizza (pâte et sauce à la tomate), crue", "aides culinaires", {}),
      CiqualRow("18904", "Boisson au riz, nature, préemballée", "boissons sans\nalcool", {}),
      CiqualRow("25559", "Brick à la pomme de terre, fait maison, cuit", "feuilletées et autres\nentrées", {}),
      CiqualRow("76039", "Eau minérale Salvetat, embouteillée, gazeuse,\nmoyennement minéralisée (La Salvetat, 34)", "eaux", {}),
      CiqualRow("9520", "Farine de riz", "farines", {}),
      CiqualRow("4090", "Fécule de pomme de terre", "farines", {}),
      CiqualRow("11082", "Fleur de sel, non iodée, non fluorée", "sels", {}),
      CiqualRow("20194", "Haricots blancs à la sauce tomate, appertisés", "plats composés", {}),
      CiqualRow("19590", "Mozzarella au lait de vache", "fromages et\nalternatives\nvégétales", {}),
      CiqualRow("25464", "Pizza au saumon, préemballée", "pizzas, tartes et\ncrêpes salées", {}),
      CiqualRow("4003", "Pomme de terre, bouillie/cuite à l'eau", "pommes de terre et\nautres tubercules", {}),
      CiqualRow("4008", "Pomme de terre, sans peau, crue", "pommes de terre et\nautres tubercules", {}),
      CiqualRow("39251", "Riz au lait, au caramel, rayon frais", "produits laitiers frais\net alternatives\nvégétales", {}),
      CiqualRow("9100", "Riz blanc, cru", "pâtes, riz et\ncéréales", {}),
      CiqualRow("9104", "Riz blanc, cuit, sans sel ajouté", "pâtes, riz et\ncéréales", {}),
      CiqualRow("26263", "Salade de riz au thon et légumes, avec sauce,\npréemballée", "salades composées\net crudités", {}),
      CiqualRow("12725", "Salers", "fromages et\nalternatives\nvégétales", {}),
      CiqualRow("26036", "Saumon, élevage, cru", "poissons crus", {}),
      CiqualRow("26229", "Saumon, grillé/poêlé", "poissons cuits", {}),
      CiqualRow("11017", "Sel blanc alimentaire, non iodé, non fluoré (marin,\nignigène ou gemme)", "sels", {}),
      CiqualRow("11083", "Sel marin gris, non iodé, non fluoré", "sels", {}),
      CiqualRow("25555", "Tarte au saumon, préemballée", "pizzas, tartes et\ncrêpes salées", {}),
      CiqualRow("26039", "Thon, au naturel, appertisé, égoutté", "produits à base de\npoissons et produits\nde la mer", {}),
      CiqualRow("26053", "Thon, cru", "poissons crus", {}),
      CiqualRow("20358", "Tomate, chair et peau, cuite (aliment moyen)", "légumes", {}),
      CiqualRow("20385", "Tomate sans précision, crue (aliment moyen)", "légumes", {}),
  ]
  ```
  Se `CiqualRow` sul ramo non accetta `{}` come nutrienti, usa `{"kcal": 1.0}`: i nutrienti non contano qui.
- [ ] **Step 2: I test che falliscono**, in `test_ciqual_repository.py`, tutti con `find_candidates` vera e `upsert_foods(db_session, ALIMENTI_VERI)` (i test di oggi con `ALIMENTI` restano):
  - `test_a_parita_vince_il_nome_che_comincia_con_la_parola`: `find_candidates(db_session, ["riz"], limit=3)` → codici `["9100", "9104", "39251"]` (oggi `["96781", "18904", "9520"]`).
  - `test_il_cibo_semplice_prima_dei_piatti_che_lo_contengono`, parametrizzato su `(parola, limit, codici attesi come insieme)`: `("saumon", 2, {"26036", "26229"})`, `("sel", 2, {"11083", "11017"})`, `("pomme de terre", 1, {"4008"})`, `("tomate", 2, {"20358", "20385"})`, `("thon", 2, {"26053", "26039"})`.
  - `test_le_parole_si_uniscono_con_lo_stesso_ordine`: `find_candidates(db_session, ["riz", "sel"], limit=3)` → `["9100", "9104", "39251"]`.
  - `test_maiuscole_e_punteggiatura_non_cambiano_l_ordine`: `["RIZ"]` con `limit=1` → `["9100"]`; `["Riz, cru"]` con `limit=3` → `["9100", "9104", "39251"]`.
  - `test_la_prima_parola_del_termine` (puro, senza database): `_first_word("Riz, cru") == "riz"`, `_first_word("pomme de terre") == "pomme"`, `_first_word("huile d'olive") == "huile"`, `_first_word("(riz)") == "riz"`, `_first_word("  Épinard cru") == "épinard"`, `_first_word("") == ""`.
  - `test_la_tabella_vera_ha_l_alimento_fra_i_candidati`: `await tabella_vera(db_session) == 3484`; poi per ogni `(espressione, parole)` di `GRUPPI_VERI`, `find_candidates(db_session, parole, limit=CANDIDATES)` (da `app.services.ciqual_match`) deve avere almeno un candidato con `re.search(espressione, normalize_name(c.name_fr))`. Il test raccoglie i gruppi mancati e fa `assert mancati == []`, così il messaggio li elenca tutti. Con l'ordine di oggi ne manca 12.
    ```python
    GRUPPI_VERI = [
        ("^riz.*cru", ["riz"]), ("^riz.*cru", ["riz blanc cru", "riz"]), ("^riz.*cru", ["riz cru", "riz blanc"]),
        ("^saumon", ["saumon"]), ("^saumon", ["saumon cru", "saumon frais"]),
        ("^saumon", ["saumon atlantique cru", "filet de saumon"]),
        ("^thon.*(appertise|conserve)", ["thon"]), ("^thon.*(appertise|conserve)", ["thon en conserve", "thon au naturel"]),
        ("^thon.*(appertise|conserve)", ["thon en boîte", "thon appertisé"]),
        ("^thon.*(appertise|conserve)", ["thon à l'huile", "thon"]),
        ("^lentille", ["lentilles"]), ("^lentille", ["lentilles sèches", "lentilles vertes"]), ("^miel", ["miel"]),
        ("^tomate (sans precision|ronde), crue", ["tomate crue", "tomate"]),
        ("^tomate (sans precision|ronde), crue", ["tomate"]),
        ("^pomme de terre.*crue", ["pomme de terre crue", "pomme de terre"]), ("^pomme de terre.*crue", ["pomme de terre"]),
        ("^sucre blanc", ["sucre"]), ("^sucre blanc", ["sucre blanc", "sucre en poudre"]),
        ("^sel (blanc|marin|gris)", ["sel"]), ("^sel (blanc|marin|gris)", ["sel fin", "sel de table"]),
        ("^sel (blanc|marin|gris)", ["sel marin", "sel"]),
        ("^poulet, filet sans peau cru", ["blanc de poulet", "filet de poulet cru"]),
        ("^poulet, filet sans peau cru", ["poulet filet cru", "poulet"]),
    ]
    ```
    Misurato il 2026-11-21 con questo stesso ordine su una copia della tabella: tutti i 24 trovati, il peggiore al posto 11.
- [ ] **Step 3: Falliscono.** Il comando di pytest con `tests/repositories/test_ciqual_repository.py`. Expected: FAIL su tutti i nuovi tranne `test_la_prima_parola_del_termine` (ImportError finché `_first_word` non c'è) e, nel test sulla tabella vera, 12 gruppi mancati.
- [ ] **Step 4: Il codice.**
  - `_first_word(term)`: `re.search(r"[\w'’-]+", term.lower())`, il gruppo o `""`.
  - In `find_candidates`, per ogni parola: `starts = func.lower(CiqualFood.name_fr).startswith(_first_word(term), autoescape=True)` e `closeness = func.similarity(term, CiqualFood.name_fr)` nella `select` con le loro etichette, `order_by(score.desc(), starts.desc(), closeness.desc(), CiqualFood.name_fr)`, `limit(limit)` come oggi. Nell'unione, per codice, il massimo di ciascuna delle tre misure; l'ordine finale `(-score, -starts, -closeness, name_fr)`; il taglio a `limit`. `Candidate` non cambia.
  - Docstring di `find_candidates` e del modulo: `word_similarity` vale 1 per ogni nome che contiene la parola (sulla tabella vera «riz» ne lega 43), e a parità l'ordine alfabetico lasciava fuori l'alimento semplice; per questo il nome che comincia con la parola, poi la somiglianza di tutto il nome. Niente `unaccent`: vorrebbe una migrazione, e sulla tabella vera non cambia i posti.
- [ ] **Step 5: Passano**, poi la suite intera. Expected: PASS. Il test sulla tabella vera dura qualche secondo (la lettura del file vero è sotto il secondo).
- [ ] **Step 6: Commit** — `fix(s4): a parità di somiglianza il candidato che comincia con la parola, provato sulla tabella CIQUAL vera`.

---

### Task 2: Il nome italiano come ripiego, cosa si è cercato, la pelle e le ossa

**Files:**
- Modify: `backend/app/services/ciqual_match.py` (`Searched` nuova, `MatchBatch`, `match_names`, `CiqualRun`, `decide_ciqual`, `CHOICE_SYSTEM_PROMPT`, la docstring del modulo), `backend/app/cli/decide_ciqual.py`
- Test: `backend/tests/services/test_ciqual_match.py`, `backend/tests/test_decide_ciqual_cli.py`

**Interfaces:**
- Consumes: `ALIMENTI_VERI` (Task 1).
- Produces: `Searched`, `MatchBatch.searched`, `CiqualRun.no_candidates` come nelle Interfacce prodotte. In `MatchBatch.searched` c'è ogni nome le cui parole si sono verificate (anche se poi la scelta è stata rifiutata o l'AI si è fermata prima di sceglierlo); un nome con le parole rifiutate non c'è.

- [ ] **Step 1: I test che falliscono**, nello stile dei vicini (il finto e il fixture `chiave` del ramo), con un `_mondo_vero(db_session, *voci)` che fa come `_mondo` ma carica `ALIMENTI_VERI`:
  - `test_il_nome_italiano_non_entra_fra_i_candidati`: «sale» (condimenti), parole `["sel"]`, scelta `"11083"`. I candidati della domanda di scelta sono, nell'ordine, `["11083", "11017", "11082", "9104"]`: né «Salers» (12725) né «Eau minérale Salvetat» (76039). Oggi ci sono tutti e due.
  - `test_senza_candidati_dalle_parole_si_cerca_col_nome_italiano`: «mozzarella» (latticini), parole `["zzzz qqqq"]`, scelta `"19590"`, con `match_names`: `decided["mozzarella"] == Matched(code="19590", candidates=1)`, i candidati della scelta sono `["19590"]`, e `searched["mozzarella"] == Searched(terms=("zzzz qqqq",), candidates=1, by_italian_name=True)`.
  - `test_match_names_dice_cosa_ha_cercato`: «riso» con `["riz"]` e scelta `null`; «miele» con le parole sotto il nome «mieli» (rifiutate). `searched["riso"] == Searched(("riz",), 7, False)` e `decided["riso"] == Matched(None, 7)`; `"miele" not in searched` e `"miele" not in decided`.
  - `test_un_candidato_mancato_si_conta_a_parte`: due ingredienti, «nduja» (carne) con `["zzzz qqqq"]` (niente, nemmeno col nome italiano) e «riso» con `["riz"]` e scelta `null`, con `decide_ciqual`: `(esito.none, esito.no_candidates, esito.matched) == (2, 1, 0)`, e le due righe scritte `(None, "ai")`.
  - In `test_senza_candidati_si_scrive_nessuno_senza_chiedere_la_scelta` (di oggi): si aggiunge `esito.no_candidates == 1` (è un'aggiunta, non un cambio).
  - `test_la_scelta_dice_senza_pelle_ne_ossa`: la riga della decisione 9 è in `CHOICE_SYSTEM_PROMPT` e nel prompt di sistema della richiesta di scelta che il finto ha registrato.
  - In `test_decide_ciqual_cli.py`, `test_dice_quanti_non_hanno_nemmeno_un_candidato`: con `decide_ciqual` sostituita (monkeypatch su `app.cli.decide_ciqual.decide_ciqual`) da una che torna `CiqualRun(matched=3, none=2, no_candidates=1, refused=0, pending=0, asked=5)`, l'uscita contiene «3 ingredienti abbinati, 2 senza un alimento adatto (1 senza nemmeno un candidato), 0 risposte rifiutate». Con `no_candidates=0` la riga resta quella di oggi (lo prova già `test_senza_chiave_dice_quanti_ne_restano_e_non_scrive`).
- [ ] **Step 2: Falliscono.** Expected: FAIL.
- [ ] **Step 3: Il codice.**
  - In `match_names`: `candidates = await find_candidates(session, terms[item.name], limit=CANDIDATES)`; se è vuota, `find_candidates(session, [item.name], limit=CANDIDATES)` e `by_italian_name=True` se questa trova qualcosa. `searched[item.name] = Searched(tuple(terms[item.name]), len(candidates), by_italian)` per ogni nome con le parole verificate, prima della scelta. `MatchBatch(decided, refused, unavailable, searched)` in tutti i ritorni, anche quelli del guasto.
  - In `decide_ciqual`: `code is None` e `candidates == 0` conta `none` **e** `no_candidates`; `code is None` con candidati conta solo `none`.
  - Nel CLI: dopo «‹none› senza un alimento adatto», se `no_candidates` è maggiore di zero, « (‹no_candidates› senza nemmeno un candidato)».
  - `CHOICE_SYSTEM_PROMPT`: la riga della decisione 9 sotto «Regole:», prima della riga su `"n"` e `"nome"`.
  - Docstring del modulo: il passo 2 dice «con quelle parole `pg_trgm` trova i candidati veri; il nome italiano si cerca solo se le parole non trovano niente (aggiunto sempre portava rumore: «sale» → «Salers»)».
- [ ] **Step 4: Passano**, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `fix(s4): il nome italiano solo quando le parole francesi non trovano niente; cosa si è cercato per ogni nome; carne e pesce senza pelle né ossa`.

---

### Task 3: Il pomodoro, e il rapporto del pilota che dice perché

**Files:**
- Modify: `backend/app/data/s4_pilota.json` (il caso «pomodoro»), `backend/app/services/s4_pilot.py` (`MatchOutcome`, `run_match_pilot`, `match_report`, e `final_line` se serve)
- Test: `backend/tests/services/test_s4_pilot.py`

**Interfaces:**
- Consumes: `Searched`, `MatchBatch.searched` (Task 2); `ALIMENTI_VERI` (Task 1).
- Produces: `MatchOutcome.searched`.

- [ ] **Step 1: I test che falliscono.**
  - `test_il_pomodoro_aspetta_il_pomodoro_crudo_generico` (puro): l'espressione del caso «pomodoro» di `load_cases()` è `^tomate (sans precision|ronde), crue`, e con `re.search` su `normalize_name(...)` trova «Tomate sans précision, crue (aliment moyen)» e «Tomate ronde, crue», non «Tomate, chair et peau, cuite (aliment moyen)», «Tomate cerise, crue», «Tomate verte, crue». (Gli accenti: `normalize_name` toglie «é», l'espressione dice «precision».)
  - `test_ogni_caso_trova_un_alimento_nella_tabella_vera` (senza database): `read_ciqual(CANDIDATE_FILES[0])`, i nomi normalizzati; ogni `atteso` non `None` di `load_cases()` ne trova almeno uno. Oggi fallisce sul pomodoro.
  - `test_il_rapporto_dice_perche`: `upsert_foods(db_session, ALIMENTI_VERI)`, `run_match_pilot` con cinque casi, in quest'ordine: `MatchCase("riso", "cereali", "^riz.*cru")`, `MatchCase("tonno in scatola", "pesce", "^thon.*appertise")`, `MatchCase("pomodoro", "verdura", "^tomate (sans precision|ronde), crue")`, `MatchCase("patata", "verdura", "^pomme de terre.*crue")`, `MatchCase("salmone", "pesce", "^saumon")`. Parole: `(1, "riso", ["riz"])`, `(2, "tonno in scatola", ["zzzz qqqq"])`, `(3, "pomodori", ["tomate"])` (rifiutata), `(4, "patata", ["pomme de terre"])`, `(5, "salmone", ["saumon"])`. Scelte, per i tre con candidati: `(1, "riso", None)`, `(2, "patata", "4003")`, `(3, "salmone", "9100")` (fuori dai candidati). `match_report(esiti)[1:]` è esattamente:
    ```
      ✗ «riso»: l'AI non ha scelto fra 7 candidati (parole: riz); atteso ^riz.*cru
      ✗ «tonno in scatola»: nessun candidato (le parole zzzz qqqq e il nome italiano non trovano alimenti); atteso ^thon.*appertise
      – «pomodoro»: le parole di ricerca dell'AI non si sono potute verificare
      ✗ «patata»: scelto «Pomme de terre, bouillie/cuite à l'eau» (4003) fra 5 candidati (parole: pomme de terre); atteso ^pomme de terre.*crue
      – «salmone»: la scelta dell'AI fra 7 candidati non si è potuta verificare (parole: saumon)
    ```
    Le parole di un caso si uniscono con « / ». Quando i candidati vengono dal nome italiano, la parentesi dice «(parole: ‹…›; candidati dal nome italiano)».
  - `test_il_rapporto_dice_soglia_casi_e_spesa` (di oggi), i due cambi permessi: l'esito di «uova» diventa `MatchOutcome(MatchCase("uova", "altro", "^oeuf"), Verdict.WRONG, searched=Searched(("oeuf cru",), 0))` con la riga «  ✗ «uova»: nessun candidato (le parole oeuf cru e il nome italiano non trovano alimenti); atteso ^oeuf»; quello di «riso» (`UNANSWERED`, senza `searched`) dà «  – «riso»: le parole di ricerca dell'AI non si sono potute verificare». Le altre righe non cambiano.
- [ ] **Step 2: Falliscono.** Expected: FAIL.
- [ ] **Step 3: Il codice.**
  - `s4_pilota.json`: `"atteso": "^tomate (sans precision|ronde), crue"` per «pomodoro»; nella `nota`, una frase: «Il pomodoro aspetta l'alimento generico: nella 2025 «Tomate, crue» non c'è (2026-11-21).».
  - `run_match_pilot`: ogni esito non «da rivedere» porta `searched=result.searched.get(case.ingredient)`.
  - `match_report`, le righe del Step 1. Un ✗ senza `searched` (solo negli esiti costruiti a mano: `run_match_pilot` lo dà a ogni caso deciso) stampa le righe di oggi («scelto «‹nome›» (‹codice›); atteso …», «nessun alimento scelto; atteso …»); un – senza `searched` vuol dire parole rifiutate, e dice che le parole non si sono potute verificare.
  - `final_line`: se sul ramo la frase del pilota che non passa parla ancora di un «modello più forte» o del §9, diventa «Il pilota non passa: non lanciare l'AI su tutto il catalogo. Le righe ✗ e – qui sopra dicono se è mancato il candidato o la scelta.»; se il ramo llm-haiku l'ha già cambiata, resta com'è. Il test che la fissa segue.
- [ ] **Step 4: Passano**, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `fix(s4): il pomodoro del pilota è il generico della 2025; il rapporto dice se è mancato il candidato o la scelta, con le parole`.

---

### Task 4: I lotti dei pesi che non si leggono si dividono

**Files:**
- Modify: `backend/app/services/unit_grams.py` (`GramsRun`, `decide_grams`, costante nuova), `backend/app/cli/decide_grams.py`
- Test: `backend/tests/services/test_unit_grams_ai.py`, `backend/tests/test_decide_grams_cli.py`

**Interfaces:**
- Consumes: `LlmUnavailable` e il suo tipo, come sono sul ramo (Preparazione).
- Produces: `GramsRun.skipped`, `GramsRun.last_error`, `GRAMS_ALL_BROKEN`; le decisioni 10–11.

- [ ] **Step 1: I test che falliscono**, con il `_mondo` di oggi (le tre coppie, nell'ordine di `pending_pairs`, con le etichette di `test_va_a_lotti_e_dopo_ogni_lotto_chiama_after_batch`: aglio × spicchio, olio di oliva × l'unità di quel test, uova × pezzo). `ROTTO` è una risposta che non si legge come JSON, fatta come il finto del ramo la fa (su `master`: la stringa `'{"pesi": [{"n": 1, "ingrediente" "aglio"'`); `TRONCO` una risposta troncata, come il ramo la riconosce.
  - `test_un_lotto_che_non_si_legge_si_divide_a_meta`: `batch_size=3`; risposte `ROTTO`, poi i pesi di aglio (una coppia), poi quelli di olio e uova (due). `(esito.weighed, esito.pending, esito.skipped) == (3, 0, ())`; le domande mandate hanno 3, 1 e 2 coppie; in `llm_calls` tre righe `unit_grams`, la prima con `ok` falso.
  - `test_una_risposta_troncata_si_divide_come_una_rotta`: lo stesso con `TRONCO` al posto di `ROTTO`.
  - `test_una_coppia_che_non_si_legge_da_sola_si_salta_e_il_giro_continua`: `batch_size=3`; `ROTTO`, `ROTTO` (aglio da solo), i pesi di olio e uova. `esito.weighed == 2`, `esito.skipped == ("aglio × spicchio",)`, `esito.pending == 1`, `esito.unavailable is None`, `esito.last_error` non vuoto. Un secondo `decide_grams` con un finto che risponde il peso di aglio chiede solo aglio e lo scrive: `pending == 0`.
  - `test_un_lotto_illeggibile_anche_coppia_per_coppia_ferma_il_giro`: `batch_size=2` (lotti: aglio e olio; uova); `ROTTO` tre volte. Tre chiamate sole (uova non si chiede), `esito.unavailable.startswith(GRAMS_ALL_BROKEN)`, `esito.skipped == ("aglio × spicchio", "olio di oliva × ‹unità›")`, `esito.pending == 3`.
  - `test_un_guasto_terminale_durante_la_divisione_ferma_il_giro`: `batch_size=3`; `ROTTO`, i pesi di aglio, poi un guasto terminale come il ramo lo costruisce nei suoi test (credito finito o chiave rifiutata). Tre chiamate, nessuna quarta; aglio scritto (`weighed == 1`), `pending == 2`, `esito.unavailable` non `None`, `skipped == ()`.
  - `test_l_ai_che_non_risponde_non_scrive_niente_e_si_registra` (di oggi, un guasto di rete): non cambia, e passa com'è sul ramo.
  - In `test_decide_grams_cli.py`, `test_nomina_le_coppie_saltate`: con `decide_grams` sostituita da una che torna `GramsRun(weighed=5, none=1, refused=0, pending=2, asked=8, skipped=("aceto di mele × di", "acqua × bicchiere"), last_error="Expecting ':' delimiter")`, l'uscita contiene, dopo la riga dei pesi scritti, «2 coppie saltate in questo giro, perché la risposta dell'AI non si leggeva nemmeno da sole (Expecting ':' delimiter): aceto di mele × di, acqua × bicchiere. Restano da pesare: un altro giro le richiede, o si pesano in Anagrafica, «Pesi per unità».», e l'ultima riga resta «2 coppie restano da pesare: rilancia questo comando.». Con una sola: «1 coppia saltata in questo giro, perché la risposta dell'AI non si leggeva nemmeno da sola (‹errore›): ‹coppia›. Resta da pesare: un altro giro la richiede, o si pesa in Anagrafica, «Pesi per unità».». Oltre le 20 coppie, le prime 20 e poi «, e altre ‹k›».
- [ ] **Step 2: Falliscono.** Expected: FAIL.
- [ ] **Step 3: Il codice.**
  - Un predicato privato in `unit_grams.py`, `_answer_unusable(exc: LlmUnavailable) -> bool`, vero solo per i tipi della risposta arrivata ma inutilizzabile (troncata, non JSON, non un oggetto, fuori schema), con i nomi del ramo e un commento che dice perché non i guasti di passaggio (decisione 10).
  - In `decide_grams`, ogni lotto passa da una funzione privata che chiede `ask_grams` sulle coppie, applica le risposte come oggi e, se `_answer_unusable`, si richiama sulle due metà; una coppia sola che fallisce così va in `skipped` come `f"{pair.ingredient_name} × {pair.unit_label}"` e il suo errore in `last_error`. Ogni altro `LlmUnavailable` risale: `decide_grams` lo tratta come fa il ramo (terminale: `unavailable` e fine del giro, senza le chiamate rimaste). Se di un lotto nessuna coppia ha avuto risposta e tutte sono saltate, `unavailable = f"{GRAMS_ALL_BROKEN}: {last_error}"` e il giro finisce. `after_batch` si chiama dopo ogni lotto intero, come oggi; il `flush` resta.
  - La docstring di `decide_grams` dice la divisione, il salto, il freno; il commento su `GRAMS_BATCH` aggiunge che un lotto che non si legge si divide (le misure non cambiano).
  - Il CLI stampa le righe del Step 1 fra quella dei pesi scritti e quella di quanto resta.
- [ ] **Step 4: Passano**, poi la suite intera. Expected: PASS.
- [ ] **Step 5: Commit** — `fix(s4): decide_grams divide a metà un lotto a cui l'AI risponde in modo illeggibile, salta la coppia rotta e va avanti`.

---

### Task 5: I documenti, la verifica finale e il report

**Files:**
- Modify: `docs/superpowers/specs/2026-10-13-s4-nutrienti-ingrediente-design.md`, `CLAUDE.md`, `README.md`, `next-steps.md`
- Create o modify: `docs/night-reports/<data di oggi>.md`

- [ ] **Step 1: La spec.** Sotto il titolo, una riga: «_2026-11-21: i candidati e i lotti dei pesi cambiano dopo il pilota sulla tabella vera; §4.10 e §4.23 aggiornati, vedi `docs/superpowers/plans/2026-11-21-s4-candidati.md`._» (se il ramo llm-haiku ha già messo una riga lì, questa va sotto la sua). La decisione 10 si riscrive così:
  ```
  10. **I candidati**: per ogni ingrediente, le parole dell'AI contro `ciqual_foods.name_fr` con
      `word_similarity` di `pg_trgm`; i 15 migliori sopra 0,3. `word_similarity` vale 1 per ogni
      nome che contiene la parola (sulla tabella vera «riz» ne lega 43: amido, bevanda, riso al
      latte), quindi a parità vince il nome che comincia con la prima parola, poi la
      `similarity` di tutto il nome, poi l'alfabeto. Il nome italiano si cerca solo se le parole
      dell'AI non trovano niente: aggiunto sempre portava rumore («sale» → «Salers», «Eau
      minérale Salvetat»). _Cambiato il 2026-11-21, dopo il pilota del 2026-10-20 (20 su 29):
      con l'ordine alfabetico, 12 di 24 gruppi di parole plausibili non avevano l'alimento fra i
      candidati; con questo, nessuno._
  ```
  In fondo alla decisione 23 (i lotti da 40): «Un lotto a cui l'AI risponde in modo illeggibile (troncato, JSON rotto) si divide a metà e si richiede, fino alla coppia sola; una coppia che non si legge nemmeno da sola si salta per quel giro, resta da pesare e il comando la nomina. Se nessuna coppia di un lotto si legge, il giro si ferma. (2026-11-21: prima si fermava al primo lotto rotto, e il lotto era sempre lo stesso.)». Nella decisione 18, dopo l'esempio `^tomate, crue`, una parentesi: «(nella 2025 quel nome non c'è: il caso del pomodoro aspetta `^tomate (sans precision|ronde), crue`)». Il §9 non si tocca.
- [ ] **Step 2: `CLAUDE.md`.** Una lezione nuova in fondo all'elenco delle lezioni, e il numero in «… things reviews here kept rediscovering» cresce di uno rispetto a com'è sul ramo:
  ```
  - **A similarity of 1.0 is a tie, not a match.** `word_similarity` in `pg_trgm` scores
    1.0 for every name that contains the word, so on the real CIQUAL table «riz» tied 43
    names — rice pudding, rice starch, rice drink — and the alphabetical tie-break left
    `Riz blanc, cru` outside the 15 candidates. The pilot read it as the model failing (20
    of 29); four invented fixture rows never tie, so no test could see it. `find_candidates`
    now breaks ties on the name starting with the term, then on whole-name `similarity`,
    and `tests/repositories/test_ciqual_repository.py` runs the search on the real file.
    When a ranking sorts on a score, ask how many rows reach the top score on the real data.
  ```
- [ ] **Step 3: `README.md`.** Nel paragrafo dopo i comandi di `s4_pilot`/`decide_ciqual`: «Il pilota dice, per ogni caso mancato, se la ricerca non ha trovato candidati o se l'AI non ha scelto, con le parole francesi che ha usato; `decide_ciqual` conta a parte gli ingredienti senza nemmeno un candidato.». Nel paragrafo dopo i comandi di `decide_grams`: «Se l'AI risponde a un lotto in modo illeggibile, il lotto si divide a metà fino alla coppia sola; una coppia che non si legge nemmeno da sola si salta per quel giro, e il comando la nomina: resta da pesare.».
- [ ] **Step 4: `next-steps.md`.**
  1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte: i candidati di S4 sulla tabella vera e i pesi che non si fermano)_`.
  2. La voce di questo piano diventa `fatto <data di oggi>` con ` → branch night/s4-candidati (da revisionare)`, e va in cima a «Fatti (recenti)».
  3. In «Da fare a mano (solo Mattia)», la voce «S4 fetta 1, il pilota degli abbinamenti non passa sulla tabella vera …» diventa `fatto <data di oggi>` («la ricerca dei candidati corretta su night/s4-candidati; il pilota si rifà sul server») e va in «Fatti (recenti)». La voce «S4 fetta 2, i pesi …» si riscrive tenendo solo quel che resta a Mattia: «[tbd] P2 · S4 fetta 2, da correggere in Anagrafica: «aceto di mele» con l'unità «di» (60 g: «di» non è un'unità, sfuggita a `clean_doses`), «acqua» un bicchiere 100 g (l'aceto 200), «alcol puro» senza unità 400 g [S4]». Al loro posto, una voce: «[tbd] P2 · S4 sul server, dopo il deploy di night/llm-haiku e night/s4-candidati: il pilota una volta (meno di 0,01 $), poi `decide_ciqual` e `decide_grams` fino a «nessun … in attesa», poi «Valori nutrizionali» su qualche ricetta vera e «Pesi per unità» sul telefono (comandi in «Dopo il deploy» di `docs/superpowers/plans/2026-11-21-s4-candidati.md`) [S4]».
  4. Due `idea` in «Idee», con `[S4]`: «`decide_ciqual` si ferma al primo guasto dell'AI, come faceva `decide_grams`: un lotto di nomi che dà sempre una risposta illeggibile bloccherebbe quelli dopo (l'ordine è per nome); la divisione a metà di `decide_grams` andrebbe bene anche lì» (solo se sul ramo `match_names` si ferma ancora al primo guasto); «La ricerca di Anagrafica («Cambia alimento», `search_foods`) ordina ancora alfabeticamente a parità di somiglianza: cercando «riz» il riso crudo non viene per primo».
  5. Quel che è emerso fuori da questo piano va come `idea` o `tbd`, con `[S4]`.
- [ ] **Step 5: La verifica finale.** I «Comandi di verifica» con i loro attesi; pytest circa **`N_pytest` + 25**. Se i numeri differiscono, scrivi nel report da dove viene la differenza. Infine `docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_s4_candidati WITH (FORCE)'`.
- [ ] **Step 6: Il report**, `docs/night-reports/<data di oggi>.md` sul ramo (in fondo, se c'è già). Dentro: il ramo e `BASE`; i conti veri contro la Preparazione; i nomi del ramo llm-haiku usati al posto di quelli del piano (il tipo di `LlmUnavailable`, i valori su cui `decide_grams` divide, il finto); cosa faceva `decide_grams` sul ramo prima di questo piano, se diverso da `master`; i gruppi della tabella vera con il loro posto (dal test, se lo stampa, o da una prova a parte sullo stesso database); le decisioni 6–11 che Mattia può voler rivedere, in particolare il nome italiano come ripiego e i guasti di passaggio che non dividono; la sezione «Dopo il deploy (solo Mattia)» qui sotto. Niente push, niente merge, niente deploy.
  ```bash
  git add CLAUDE.md README.md docs/ next-steps.md
  git commit -m "docs: i candidati di S4 e i lotti dei pesi nella spec, in CLAUDE.md e nel README; il report"
  ```

---

## Dopo il deploy (solo Mattia)

La notte non tocca la produzione. Questo ramo si unisce su `master` **dopo** `night/llm-haiku`, da cui parte; i due vanno in produzione insieme o in quest'ordine. I passi di «Dopo il deploy» del piano llm-haiku (la chiave, il controllo dell'LLM) vengono prima di questi.

1. **Il deploy di sempre, con il `-f`**: `docker compose -f docker-compose.prod.yml up -d --build --wait`. Nessuna migrazione da questo ramo.
2. **Il pilota, una volta sola**: `docker compose -f docker-compose.prod.yml exec backend python -m app.cli.s4_pilot`. Expected: 30 abbinamenti e 20 pesi, nessuna riga «?» (il pomodoro ora trova il suo alimento), «Abbinamenti: N giusti su 30» con N almeno 27 per passare, la spesa sotto 0,01 $. Se non passa, non si lancia niente: le righe ✗ e – dicono se è mancato il candidato o la scelta, con le parole usate; copiale nella voce di `next-steps.md`.
3. **Gli abbinamenti**, prima un lotto da guardare: `docker compose -f docker-compose.prod.yml exec backend python -m app.cli.decide_ciqual --limit 25`, qualche ingrediente in Anagrafica («Valori nutrizionali»), poi `docker compose -f docker-compose.prod.yml exec backend python -m app.cli.decide_ciqual`, da rilanciare finché l'ultima riga dice «nessun ingrediente alimentare in attesa.». Se dice «abbinamenti non disponibili (…)», il motivo è fra parentesi (credito, chiave): si sistema e si rilancia.
4. **I pesi**: `docker compose -f docker-compose.prod.yml exec backend python -m app.cli.decide_grams`, da rilanciare finché restano solo le coppie che il comando nomina come saltate. Quelle si pesano a mano in Anagrafica, «Pesi per unità»; con loro le tre correzioni della voce in «Da fare a mano» («aceto di mele» con «di», «acqua» un bicchiere, «alcol puro»).
5. **Le spese dell'AI**: le sezioni `ciqual_terms`, `ciqual_match` e `unit_grams` con il loro costo.
6. **Sul telefono**: «Valori nutrizionali» in fondo a qualche ricetta vera (quante righe restano fuori e perché), e «Pesi per unità» nella scheda di un ingrediente.
