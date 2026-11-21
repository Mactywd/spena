# L'hash della password fuori da `.env`: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** l'hash argon2 della password d'accesso si sposta da `.env` a un file suo, `password.env`, fuori da git, letto come secondo `env_file` in forma lunga con `format: raw`. Così Compose smette di stampare a ogni comando avvisi con dei pezzi dell'hash. Un test sui file Compose impedisce di tornare indietro, e uno script scrive `password.env` senza mai mostrare l'hash.

**Architecture:** Compose legge `.env` due volte, e con due regole diverse. La prima è `env_file:`, dove `format: raw` consegna i `$` intatti. La seconda è la sostituzione dei `${...}` dentro i file Compose, che non conosce `format: raw`: lì ogni `$argon2id`, `$v` o `$m` dell'hash diventa una variabile mancante, e il suo nome finisce nell'avviso. La soluzione è quella di Training (commit `dfe92e6`, 2026-10-04): l'hash sta in `password.env`, una seconda voce di `env_file` (`format: raw`, `required: false`) dopo `.env`. Compose non usa quel file per la sostituzione. Lo scrive `scripts/imposta-password.sh <file compose>`: chiede la password due volte senza mostrarla, calcola l'hash nel container del backend e scrive il file con i permessi 600. Anche `Settings` legge `password.env` dopo `.env`, così fuori da Compose vale la stessa regola.

**Tech Stack:** Docker Compose ≥ 2.30 (in locale c'è la v5.7.1), bash, pydantic-settings, pytest, PyYAML (già fra gli extra `dev`).

**Spec:** non c'è una spec. L'autorità è la voce di `next-steps.md` che comincia con «Gli avvisi di `docker compose` sul server stampano pezzi dell'hash della password», decisa da Mattia («come Training»), insieme a questo piano. Il precedente da cui copiare è `/home/mactyws/coding/ais/training` al commit `dfe92e6`: `docker-compose.yml`, `backend/tests/test_compose.py`, `scripts/set-password.sh`, `.env.example`, `.gitignore`, `README.md`. **Si legge e basta.**

## Global Constraints

- **Dove si lavora.** Il worktree è `/home/mactyws/coding/ais/spena/.worktrees/hash-password` (`.worktrees/` è già in `.gitignore`), sul ramo `night/hash-password` creato da **`master`**. Nel piano `<worktree>` indica quel percorso. Ogni comando parte da lì, o dalla sua `backend/`. Il checkout principale non si tocca: se ci trovi modifiche non committate, sono dell'utente. **Nessun push, nessun merge, nessun deploy. Mai `git stash`. Nessuna lettura e nessuna scrittura sulla produzione, e nessun `ssh`.**
- **Nessun `.env` vero.** Non leggere e non copiare il `.env` né un `password.env` del checkout principale, di Training o di qualunque altro posto. Quando serve un `.env` (Task 4) **si copia da `.env.example`**, che non ha segreti, e alla fine si cancella. Il `password.env` del Task 4 lo scrive lo script con la password usa e getta `prova-della-notte`. Non stamparlo comunque mai (niente `cat password.env`): per controllarlo si usano `grep -c` e `stat`, come farà Mattia sul server.
- **Mai `docker compose config` senza `--quiet`.** Senza `--quiet` stampa l'ambiente risolto del backend, cioè l'hash. Con `--quiet` stampa solo gli avvisi e gli errori, ed è proprio quello che si vuole vedere.
- **La seconda lezione di `CLAUDE.md` resta intera.** Ogni `env_file` del backend, in tutti e tre i file Compose, è in forma lunga con `format: raw`. Mai la forma breve `env_file: .env`, nemmeno per la voce nuova.
- **La terza lezione di `CLAUDE.md`: il deploy è sempre `docker compose -f docker-compose.prod.yml up -d --build --wait`.** Lo script nuovo **non ha un file Compose di default**: il file si passa sempre come argomento, perché sul server un default su `docker-compose.yml` sarebbe proprio il trabocchetto di quella lezione.
- **Backend su Postgres vero, con un database dei test di questo ramo.** Il container è `spena-db-1` (porta 5433), e si usa solo come database dei test: se `docker ps --format '{{.Names}}'` non lo mostra, `docker start spena-db-1`. Questo ramo non aggiunge migrazioni, ma usa comunque **`spena_test_hash_password`**, creato nella Preparazione e tolto alla fine, così non si scontra con un'altra notte che usa `spena_test`. Nel worktree non c'è un `.venv`: si usa quello del checkout principale. `python -m` mette la cartella corrente in testa a `sys.path`, quindi si prova l'`app` del worktree. **Il comando di pytest** si lancia sempre da `<worktree>/backend`, con in coda i percorsi che il task indica:
  ```bash
  TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_hash_password \
    PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
  Se un test sembra ignorare una modifica, lancia `python -c 'import app; print(app.__file__)'` da `<worktree>/backend`, con lo stesso `PATH`: deve stampare un percorso dentro il worktree. La suite non fa chiamate di rete. I test dello script (Task 3) non chiamano Docker: usano un `docker` finto messo in testa al `PATH`.
- **Docker dal worktree, solo così.** Ci sono due progetti Compose, ognuno con il suo nome, e nessun altro. Il primo è **`spena-pw-notte`**, con soli `run --rm --no-deps` e `config --quiet`: non pubblica porte e non avvia Postgres. Il secondo è lo stack e2e **`spena-e2e`**. **Mai `docker compose up` sul progetto di default del worktree**, e mai un comando senza `-p` (tranne lo script, che riceve il nome da `COMPOSE_PROJECT_NAME`, vedi Task 4). Mai `-f docker-compose.prod.yml` con `up`, `run` o `down`: il file di produzione si usa solo con `config --quiet`.
- **e2e** sullo stack `spena-e2e`, dalla radice di `<worktree>`. Prima di alzarlo, `docker ps --format '{{.Names}}' | grep spena-e2e`: se c'è e non l'hai alzato tu (è di un'altra notte), non fare `down` e aspetta che sparisca. I comandi sono quelli del README, con il `-p spena-e2e` e il `-f docker-compose.e2e.yml` **in ogni comando**: un `down -v` sul progetto di default cancellerebbe la dispensa vera.
  ```bash
  E2E="docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml"
  $E2E up -d --build --wait
  $E2E exec -T backend python -m app.cli.seed --con-ricette
  (cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
  $E2E down -v
  ```
- Le parole sono in italiano: README, commenti, messaggi dello script, test. `CLAUDE.md` è in inglese. I commenti dicono il perché.
- Niente dipendenze nuove e niente migrazioni. Il frontend non cambia.

### Preparazione (una volta, prima del Task 1)

- [ ] Il ramo di partenza è `master`, e porta la voce del backlog. I file di questo piano sono ancora quelli su cui il piano è scritto (quando è stato scritto, `master` era `4537139`):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify master
  git show master:next-steps.md | grep -c "stampano pezzi dell'hash della password"
  git diff --stat 4537139 master -- docker-compose.yml docker-compose.prod.yml docker-compose.e2e.yml \
    .env.example .env.e2e .gitignore README.md CLAUDE.md backend/app/core/config.py \
    backend/app/core/security.py backend/tests/test_compose.py backend/tests/test_startup.py \
    backend/tests/api/test_auth.py
  ```
  Expected: un hash, poi `1`, poi un `diff --stat` **vuoto**. Se la voce manca, **fermati**: scrivilo nel report della notte (Task 5) e non partire. Se il `diff` non è vuoto, `master` è andato avanti su questi file: applica le modifiche del piano sopra la versione di `master`, ancora per ancora, e scrivilo nel report.
- [ ] Nessuno ha già cominciato:
  ```bash
  cd /home/mactyws/coding/ais/spena
  for f in scripts/imposta-password.sh backend/tests/test_imposta_password.py; do
    git cat-file -e master:$f 2>/dev/null && echo "c'è già: $f"; done
  git branch --list night/hash-password
  ```
  Expected: nessuna riga stampata. Se il file o il ramo esistono, **fermati**, scrivi nel report cosa hai trovato e non partire.
- [ ] Il database dei test di questo ramo, nuovo e vuoto (estensioni e migrazioni le crea `conftest.py` al primo pytest):
  ```bash
  docker ps --format '{{.Names}}' | grep -x spena-db-1 || docker start spena-db-1
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_hash_password WITH (FORCE)'
  docker exec spena-db-1 psql -U spena -d postgres -c 'CREATE DATABASE spena_test_hash_password'
  ```
- [ ] Allinea al lockfile `node_modules` del checkout principale (lo usa Playwright nel Task 4), poi crea il worktree e collegaci `node_modules`. Solo quello: **niente `.env`**.
  ```bash
  cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/hash-password -b night/hash-password master
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/hash-password/frontend/node_modules
  ```
- [ ] Nel `next-steps.md` del ramo la voce passa a `in corso`. Cercala con `grep -n "stampano pezzi dell'hash della password" next-steps.md` (di giorno può essere stata spostata in «Pronti per la notte») e cambia solo lo stato fra parentesi quadre. Poi committa:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/hash-password
  git add next-steps.md
  git commit -m "next-steps: hash della password in password.env, in corso"
  ```
- [ ] La linea di partenza: lancia il comando di pytest intero, `… python -m pytest -q 2>&1 | tail -n 1`. Expected: tutto verde. **Annota il numero**: è `N_pytest` del Task 5. Se non è verde, fermati: non è un difetto di questo piano, e va scritto nel report.

---

## Obiettivo e contesto

Il 2026-10-19 Mattia ha visto che sul server ogni comando `docker compose` stampava righe come `The "argon2id" variable is not set. Defaulting to a blank string.`, una per ogni pezzo dell'hash che comincia con `$`. Il README e `docs/prossimi-passi.md` le chiamano «cosmetiche». Non lo sono: i nomi delle «variabili» sono pezzi dell'hash, e finiscono nel terminale, nei log delle sessioni e in ogni copia-incolla di un deploy. L'hash arriva comunque intero al container, grazie a `format: raw`. A essere sbagliata è l'altra lettura di `.env`, quella che serve a sostituire i `${POSTGRES_USER}` e gli altri `${...}` dentro i file Compose, e lì `format: raw` non arriva.

Misurato il 2026-11-18, con Compose v5.7.1 e file finti:
- un `$argon2id$…` in `.env` produce gli avvisi, e `config --quiet` li stampa;
- lo stesso valore in un secondo `env_file` con `format: raw` non ne produce, e arriva al servizio intero;
- con `required: false`, se il secondo file manca, Compose non dà né avvisi né errori;
- con l'override e2e (`.env`, `.env.e2e`) sopra una base (`.env`, `password.env`), vince `.env.e2e`. Le liste di `env_file` si fondono, e quella dell'override va in coda.

## Decisioni prese

Di Mattia (la voce):

1. **La strada di Training.** L'hash sta in `password.env`, in un `env_file` in forma lunga con `format: raw`, e mai in `.env`. Un test sul compose lo difende. **Dopo il deploy Mattia cambia la password**, perché i pezzi di quella di oggi sono già usciti.

Di questo piano (Claude, su delega: scelte reversibili, da rivedere leggendo):

2. **La voce di `password.env` è `{path: password.env, format: raw, required: false}`, subito dopo quella di `.env`**, nei file `docker-compose.yml` e `docker-compose.prod.yml`. Con i valori ripetuti vince l'ultimo file, quindi l'hash di `password.env` batte una vecchia riga rimasta in `.env`. `required: false` è la scelta di Training, e qui ha tre motivi. Un clone nuovo parte senza `password.env`, e l'accesso risponde 401 come oggi con l'hash vuoto. Lo script stesso deve poter usare `docker compose run` prima che il file esista. Il ritorno indietro sul server (vedi «Dopo il deploy») è togliere il file, non riscriverlo.
3. **`docker-compose.e2e.yml` non aggiunge voci.** La sua lista si fonde con quella della base, e `.env.e2e` resta ultimo, quindi l'hash di «test» vince anche su un `password.env` dello sviluppatore. Cambiano solo i commenti, e un test lo tiene fermo (Task 1).
4. **Niente `password.env.example`.** Il file lo scrive solo lo script: un esempio inviterebbe a incollare l'hash a mano, che è il giro degli apici e dei copia-incolla da cui il README oggi deve mettere in guardia.
5. **Lo script è `scripts/imposta-password.sh <file compose>`**, sul modello di `scripts/set-password.sh` di Training, con tre differenze. Il file Compose è un argomento obbligatorio (terza lezione). Lo script **non riavvia niente**: dice il comando da lanciare, così sul server il deploy resta il passo esplicito di sempre. E **si rifiuta prima di chiamare Compose** se in `.env` c'è ancora un `APP_PASSWORD_HASH` non vuoto, perché quel `docker compose run` stamperebbe proprio gli avvisi che si vogliono togliere. Non tocca `.env`: la riga vecchia la toglie Mattia con il comando che lo script gli scrive.
6. **L'hash si calcola nel container**, con `--entrypoint python` (così non parte `alembic upgrade head` dell'entrypoint), `--no-deps` (non serve Postgres) e `-T`. La password passa sullo standard input, senza a capo finale, e non sulla riga di comando: così non finisce né nella cronologia della shell né in `ps`. La funzione è `app.core.security.hash_password`, la stessa che oggi indica il README.
7. **`Settings` legge `(.env, password.env)`**, in quest'ordine (`SETTINGS_ENV_FILES` in `app/core/config.py`). Dentro i container non cambia niente, perché lì non c'è nessuno dei due file e i valori arrivano da Compose. Fuori da Compose vale la stessa regola.
8. **Il messaggio di `UnusablePasswordHash` (`PASSWORD_HASH_HOWTO`) indica lo script e `password.env`**, al posto del comando `python -c` da incollare in `.env`.
9. **`.gitignore` aggiunge `password.env` e `password.env.*`.** Il secondo copre il file temporaneo dello script, se un'interruzione lo lascia lì. `.dockerignore` non cambia: i contesti di build sono `./backend` e `./frontend`, e `password.env` sta nella radice.
10. **In `docs/prossimi-passi.md`** si chiude la riga «I warning `"argon2id" variable is not set` … Non inseguirli» nella forma delle altre voci chiuse (Task 5). La voce di `next-steps.md` non ha un codice fra parentesi quadre, e non ne nasce uno nuovo.
11. **`SESSION_SECRET` non cambia insieme alla password** («Dopo il deploy», passo 10). **Confermata da Mattia il 2026-11-21.** Il cookie di sessione è firmato con il segreto, che non è mai uscito, e non con l'hash. Una sessione non si apre senza la password. I dispositivi già entrati restano dentro.

## Criteri di accettazione

- [ ] In `docker-compose.yml` e `docker-compose.prod.yml` il backend ha `env_file` = `.env` (raw), poi `password.env` (raw, `required: false`). In `docker-compose.e2e.yml` ogni voce è in forma lunga e raw, e l'ultima è `.env.e2e`. Un test lo difende per tutti e tre i file.
- [ ] `.env.example` non ha una riga `APP_PASSWORD_HASH=` né un `$` fuori dai commenti. `password.env` è ignorato da git. Un test difende entrambe le cose.
- [ ] `scripts/imposta-password.sh docker-compose.yml` scrive `password.env` con i permessi 600 e un hash argon2 che il backend, nel container, verifica con la password data. Non stampa né la password né l'hash. Si rifiuta (codice 1, senza chiamare Docker) se in `.env` c'è ancora l'hash, se le due password differiscono o sono vuote, e lascia com'era un `password.env` già esistente se il container non restituisce un hash.
- [ ] `docker compose -p spena-pw-notte -f docker-compose.yml config --quiet` non stampa niente, sia senza `password.env` sia con. Con un hash finto aggiunto a `.env`, stampa gli avvisi: il controllo vede il difetto che toglie.
- [ ] L'e2e intera passa con un `password.env` presente nel worktree (di un'altra password): lo stack e2e entra con «test».
- [ ] Tutti i test di oggi passano. L'unico cambiato è `test_lavvio_rifiuta_lhash_troncato_da_compose`, che guadagna due asserzioni sul messaggio.
- [ ] README, `CLAUDE.md`, `docs/prossimi-passi.md` e `next-steps.md` sono aggiornati, e il report della notte è scritto con la sezione «Dopo il deploy (solo Mattia)» (Task 5).

## Comandi di verifica

Il comando di pytest intero, da `<worktree>/backend`.

Dalla radice di `<worktree>`:

```bash
git diff master --name-only
git ls-files -s scripts/imposta-password.sh | cut -c1-6
grep -c '^APP_PASSWORD_HASH' .env.example
grep -rn "incollalo in .env\|hash_password('la-tua-password')\|Rumore previsto" README.md backend/app
```

Expected:
- il primo stampa esattamente `.env.e2e`, `.env.example`, `.gitignore`, `CLAUDE.md`, `README.md`, `backend/app/core/config.py`, `backend/app/core/security.py`, `backend/tests/api/test_auth.py`, `backend/tests/test_compose.py`, `backend/tests/test_imposta_password.py`, `backend/tests/test_startup.py`, `docker-compose.e2e.yml`, `docker-compose.prod.yml`, `docker-compose.yml`, `docs/night-reports/<data>.md`, `docs/prossimi-passi.md`, `next-steps.md`, `scripts/imposta-password.sh`;
- il secondo stampa `100755`;
- il terzo `0`;
- il quarto non stampa niente.

E le prove con Docker del Task 4.

## Review Focus

Questi sono i casi che la voce implica e che un test deve tenere fermi, i più probabili per primi. Ognuno è fissato nel task che possiede il codice:

1. **Sul server il `.env` ha ancora l'hash quando si lancia lo script.** È lo stato di partenza della produzione. Il `docker compose run` dello script stamperebbe i pezzi un'ultima volta. Lo script deve rifiutarsi prima di toccare Compose, e dire il comando per togliere la riga senza mostrarne il contenuto. Lo fissa il Task 3 (`test_con_lhash_ancora_in_env_si_rifiuta_prima_di_compose`), e lo prova dal vero il Task 4.
2. **Lo stack e2e su una macchina che ha un `password.env`**, come avrà da domani il checkout principale di Mattia. Deve vincere l'hash di «test», o l'e2e non entra più. Lo fissa il Task 1 (`test_nello_stack_e2e_lultimo_env_file_e_env_e2e`), e lo prova il Task 4 con l'e2e intera e un `password.env` presente.
3. **Nessun `password.env`**, in un clone nuovo o sul server prima del passo di Mattia. Compose non deve dare errori, e il backend deve partire con l'accesso a 401, come oggi con l'hash vuoto. Lo fissa il Task 1 (`required: false` in `test_lhash_arriva_da_password_env_dopo_env`), e lo prova il Task 4 (`config --quiet` senza il file).
4. **Una password battuta male, o un container che non risponde** (immagine assente, Compose che fallisce, un errore Python). `password.env` deve restare com'era, perché un hash rotto sul server chiude fuori. Lo fissa il Task 3 (`test_password_vuote_o_diverse_non_scrivono_niente`, `test_una_risposta_non_argon2_lascia_password_env_comera`).
5. **L'hash che riesce comunque a video**: nell'output dello script o nei comandi di controllo. Lo fissa il Task 3 (`test_non_stampa_ne_lhash_ne_la_password`). I controlli del Task 4 e di «Dopo il deploy» usano solo `grep -c`, `stat` e un `python -c` che stampa `True`/`False`.

## Fuori scope

- La produzione: nessun accesso, nessun deploy, e nessuna lettura del `.env` del server.
- I due file non tracciati sul server (`.env.bak` e un `imposta-password.sh` nella radice): restano della voce «Sul server: … decidere dei due file non tracciati» di «Da fare a mano». «Dopo il deploy» dice solo di non usare il secondo.
- Cambiare `SESSION_SECRET`, il gate a password o la durata della sessione.
- Il vecchio piano `docs/superpowers/plans/2026-09-11-spena-v1.md`, che porta ancora la forma breve e `APP_PASSWORD_HASH=` in `.env`: è storia, e non si riscrive.
- Il frontend.

## Margine di autonomia

- **Liberi:** i nomi di variabili locali e di helper di test; l'ordine dei test in un file; la formulazione dei commenti e dei paragrafi del README, purché contengano i fatti e i comandi scritti qui; il testo dei messaggi dello script, tranne le parole che i test cercano.
- **Fissi:** i nomi `password.env`, `scripts/imposta-password.sh`, `PASSWORD_ENV_FILE` e `SETTINGS_ENV_FILES`; la voce `{path: password.env, format: raw, required: false}` e la sua posizione dopo `.env`; l'argomento obbligatorio dello script e il suo rifiuto prima di Compose; i permessi 600; i nomi dei test.
- **Un test di oggi si cambia solo dove il piano lo dice** (`test_lavvio_rifiuta_lhash_troncato_da_compose`, Task 2). Se ne cade un altro, il piano non ha previsto quel comportamento: scrivilo nel report con il perché, senza indebolirlo.
- **Se Compose non si comporta come misurato in «Obiettivo e contesto»**, per esempio se nello stack e2e vince `password.env` o se un `password.env` mancante dà errore, **non inventare un altro schema**. Ferma il task, committa il lavoro parziale, segna la voce `bloccato` nel `next-steps.md` del ramo con quello che hai misurato (comando ed esito, mai valori di hash) e passa ai documenti.
- Una scelta reversibile e a basso impatto che il piano non copre: prendi la più conservativa e annotala nel report.

## Dipendenze

Il ramo **parte da `master`**, non consuma niente da altri piani e non ne produce per altri. Al merge può incontrare altri rami sullo stesso README (sezioni diverse) e su `next-steps.md`. Nessun altro ramo aperto tocca i file Compose.

### Interfacce prodotte

- `app.core.config`: `PASSWORD_ENV_FILE: Path = REPO_ROOT / "password.env"`, `SETTINGS_ENV_FILES: tuple[Path, Path] = (ENV_FILE, PASSWORD_ENV_FILE)`, `Settings.model_config["env_file"] = SETTINGS_ENV_FILES`. `ENV_FILE` resta com'è.
- `scripts/imposta-password.sh <file compose>`: il codice di uscita è 0 se ha scritto, 1 se si è rifiutato o è fallito, 2 per un uso sbagliato. Scrive solo `password.env`, nella radice del repo.

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `backend/tests/test_compose.py` | 1 | caricatore con `!override`, 8 test nuovi, docstring |
| `docker-compose.yml`, `docker-compose.prod.yml`, `docker-compose.e2e.yml` | 1 | la voce `password.env`; commenti |
| `.env.example`, `.env.e2e`, `.gitignore` | 1 | via `APP_PASSWORD_HASH=`; commento; `password.env`, `password.env.*` |
| `backend/app/core/config.py`, `backend/app/core/security.py` | 2 | `SETTINGS_ENV_FILES`; `PASSWORD_HASH_HOWTO` |
| `backend/tests/api/test_auth.py`, `backend/tests/test_startup.py` | 2 | 1 test nuovo; 2 asserzioni in più, docstring |
| `scripts/imposta-password.sh` (nuovo, eseguibile) | 3 | lo script |
| `backend/tests/test_imposta_password.py` (nuovo) | 3 | 11 test |
| `README.md`, `CLAUDE.md`, `docs/prossimi-passi.md`, `next-steps.md`, `docs/night-reports/<data>.md` | 5 | i documenti e il report |

---

### Task 1: Il contratto dei file Compose

**Files:**
- Modify: `backend/tests/test_compose.py`, `docker-compose.yml`, `docker-compose.prod.yml`, `docker-compose.e2e.yml`, `.env.example`, `.env.e2e`, `.gitignore`

**Interfaces:**
- Produces: la voce `password.env` negli `env_file` del backend, su cui contano lo script (Task 3) e le prove (Task 4).

- [ ] **Step 1: I test.** In `backend/tests/test_compose.py`, accanto alle costanti in testa, aggiungi un caricatore che accetti i tag di Compose. È il limite per cui oggi il docstring esclude `docker-compose.e2e.yml`. Aggiungi poi le costanti e i test qui sotto. I test di oggi restano tutti come sono, compreso `test_il_backend_legge_env_nella_forma_lunga_con_format_raw` sui due file.

```python
import subprocess

class ComposeLoader(yaml.SafeLoader):
    """`safe_load` più `!override` e `!reset`, che Compose usa negli override."""

def _tag_di_compose(loader, node):
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    return loader.construct_scalar(node)

for _tag in ("!override", "!reset"):
    ComposeLoader.add_constructor(_tag, _tag_di_compose)

def carica(nome_file: str) -> dict:
    return yaml.load((REPO_ROOT / nome_file).read_text(), Loader=ComposeLoader)

TUTTI_I_COMPOSE = COMPOSE_FILES + ("docker-compose.e2e.yml",)
ENV_EXAMPLE = REPO_ROOT / ".env.example"
VOCE_PASSWORD_ENV = {"path": "password.env", "format": "raw", "required": False}
```

| Test | Asserzioni |
|---|---|
| `test_ogni_env_file_del_backend_e_in_forma_lunga_con_format_raw` (parametrizzato su `TUTTI_I_COMPOSE`) | `env_file = carica(nome)["services"]["backend"]["env_file"]` è una lista non vuota; ogni voce è un `dict` con `voce.get("format") == "raw"`. Il messaggio nomina il file e la voce, e chiude con `PERCHE`. |
| `test_lhash_arriva_da_password_env_dopo_env` (parametrizzato su `COMPOSE_FILES`) | `percorsi = [v["path"] for v in env_file]`; `percorsi.count("password.env") == 1`; `VOCE_PASSWORD_ENV in env_file`; `percorsi.index(".env") < percorsi.index("password.env")`. Il messaggio spiega che `.env` serve anche a sostituire i `${...}`, che lì `format: raw` non vale, e che `required: false` lascia partire un clone senza il file. |
| `test_nello_stack_e2e_lultimo_env_file_e_env_e2e` | Per `docker-compose.e2e.yml`: `env_file[-1]["path"] == ".env.e2e"` e `"password.env" not in [v["path"] for v in env_file]`. Il messaggio spiega che Compose mette in coda le voci dell'override, quindi l'hash di «test» vince su un `password.env` dello sviluppatore. |
| `test_env_example_non_porta_lhash_ne_alcun_dollaro` | Righe di `.env.example` non vuote e che non cominciano (dopo `lstrip`) con `#`: nessuna comincia con `APP_PASSWORD_HASH`, e nessuna contiene `$`. Il messaggio spiega che `.env` si crea copiando questo file, e che ogni `$` lì dentro è un avviso di Compose a ogni comando. |
| `test_password_env_resta_fuori_da_git` | Per `nome` in `("password.env", "password.env.a1B2c3")`: `subprocess.run(["git", "check-ignore", "-q", nome], cwd=REPO_ROOT).returncode == 0`. |

Aggiorna il docstring del modulo: `docker-compose.e2e.yml` ora si legge con `ComposeLoader`, e c'è un paragrafo sul perché di `password.env` (la doppia lettura di `.env`, gli avvisi con i pezzi dell'hash, visti il 2026-10-19).

- [ ] **Step 2: Falliscono.** Lancia il comando di pytest con `tests/test_compose.py`. Expected: FAIL `test_lhash_arriva_da_password_env_dopo_env` (2), `test_env_example_non_porta_lhash_ne_alcun_dollaro` e `test_password_env_resta_fuori_da_git`. Passano già `test_ogni_env_file_…` (3) e `test_nello_stack_e2e_…`: difendono ciò che oggi è giusto e che la modifica non deve rompere.

- [ ] **Step 3: I file.**
  - `docker-compose.yml` e `docker-compose.prod.yml`, servizio `backend`: in `env_file`, dopo la voce di `.env`, aggiungi
    ```yaml
      - path: password.env
        format: raw
        required: false
    ```
    Nel commento sopra `env_file`, dopo il paragrafo su `format: raw` che resta, aggiungi in italiano che l'hash sta in `password.env` e mai in `.env`, perché Compose legge `.env` anche per sostituire i `${...}` di questo file. Lì `format: raw` non vale, e i `$` dell'hash diventavano avvisi con i suoi pezzi, a ogni comando (visto sul server il 2026-10-19). Aggiungi anche che `password.env` lo scrive `scripts/imposta-password.sh`, che sta dopo `.env` e quindi vince, e che `required: false` lascia partire un clone che non ce l'ha (l'accesso risponde 401).
  - `docker-compose.e2e.yml`: le voci non cambiano. Nel commento in testa, la frase «Aggiunge un secondo env_file: per le chiavi ripetute vince l'ultimo…» diventa: Compose mette in coda le voci di questo file a quelle della base (`.env`, `password.env`), quindi `.env.e2e` è l'ultimo, e il suo hash di «test» vince anche su un `password.env` dello sviluppatore.
  - `.env.example`: togli la riga `APP_PASSWORD_HASH=`. Al suo posto scrivi un commento, senza `$` fuori dai commenti: la password d'accesso non va qui, perché il suo hash sta in `password.env`, scritto da `scripts/imposta-password.sh docker-compose.yml` (README, «Avvio locale»); Compose legge questo file anche per sostituire i `${...}` dei file Compose, e i `$` dell'hash stamperebbero a ogni comando avvisi con dei suoi pezzi; senza `password.env` l'app parte e l'accesso risponde 401.
  - `.env.e2e`: solo il commento in testa. Dove dice che «il .env dello sviluppatore contiene l'hash della sua password vera», ora si dice `password.env`. Aggiungi una riga: questo file è letto solo come `env_file` e mai per la sostituzione dei `${...}`, quindi il suo hash non produce avvisi. La riga `APP_PASSWORD_HASH=…` resta identica.
  - `.gitignore`: aggiungi `password.env` e `password.env.*`.

- [ ] **Step 4: Passano.** Lancia il comando di pytest con `tests/test_compose.py tests/test_image_dependencies.py`. Expected: tutto PASS, cioè gli 8 test nuovi più quelli di oggi.

- [ ] **Step 5: Commit**
```bash
git add backend/tests/test_compose.py docker-compose.yml docker-compose.prod.yml docker-compose.e2e.yml .env.example .env.e2e .gitignore
git commit -m "fix: l'hash della password in password.env, non in .env, e un test sui file Compose"
```

---

### Task 2: Le impostazioni e il messaggio del troncamento

**Files:**
- Modify: `backend/app/core/config.py`, `backend/app/core/security.py`, `backend/tests/api/test_auth.py`, `backend/tests/test_startup.py`

**Interfaces:**
- Produces: `PASSWORD_ENV_FILE`, `SETTINGS_ENV_FILES` (vedi «Interfacce prodotte»).

- [ ] **Step 1: I test.**
  - In `tests/api/test_auth.py`, dopo `test_the_env_file_is_resolved_absolutely`:
    ```python
    def test_le_impostazioni_leggono_password_env_dopo_env(tmp_path, monkeypatch):
        from app.core.config import ENV_FILE, PASSWORD_ENV_FILE, REPO_ROOT, SETTINGS_ENV_FILES, Settings

        assert PASSWORD_ENV_FILE == REPO_ROOT / "password.env"
        assert SETTINGS_ENV_FILES == (ENV_FILE, PASSWORD_ENV_FILE)

        monkeypatch.delenv("APP_PASSWORD_HASH", raising=False)
        monkeypatch.delenv("SESSION_SECRET", raising=False)
        env = tmp_path / ".env"
        env.write_text("SESSION_SECRET=dal-env\nAPP_PASSWORD_HASH=vecchio\n")
        password_env = tmp_path / "password.env"
        password_env.write_text("APP_PASSWORD_HASH=$argon2id$v=19$nuovo\n")

        letto = Settings(_env_file=(env, password_env))
        assert letto.app_password_hash == "$argon2id$v=19$nuovo"   # vince il secondo, e i $ restano
        assert letto.session_secret == "dal-env"
        assert Settings(_env_file=(env, tmp_path / "manca.env")).app_password_hash == "vecchio"
    ```
    Nel docstring scrivi il perché: lo stesso ordine dei file Compose, e il secondo file che può mancare. La suite non legge i file veri, perché `conftest.py` spegne `env_file`: per questo la tupla di produzione si confronta con la costante, e il comportamento si prova su file in `tmp_path`.
  - In `tests/test_startup.py`, in `test_lavvio_rifiuta_lhash_troncato_da_compose`, dopo `assert "format: raw" in str(rifiuto.value)`, aggiungi:
    ```python
        assert "password.env" in str(rifiuto.value)
        assert "scripts/imposta-password.sh" in str(rifiuto.value)
    ```
    Nel docstring di `test_lavvio_riesce_con_lhash_assente`, «generano i due valori da mettere in `.env`» diventa «si genera il segreto da mettere in `.env` e si scrive `password.env` con lo script».

- [ ] **Step 2: Falliscono.** Lancia il comando di pytest con `tests/api/test_auth.py tests/test_startup.py`. Expected: FAIL il test nuovo (ImportError su `PASSWORD_ENV_FILE`) e `test_lavvio_rifiuta_lhash_troncato_da_compose` (su `"password.env"`).

- [ ] **Step 3: Il codice.**
  - `app/core/config.py`: sotto `ENV_FILE` metti `PASSWORD_ENV_FILE = REPO_ROOT / "password.env"` e `SETTINGS_ENV_FILES = (ENV_FILE, PASSWORD_ENV_FILE)`, e in `model_config` scrivi `env_file=SETTINGS_ENV_FILES`. Il commento dice che è lo stesso ordine dei file Compose, che vince il secondo e che può mancare.
  - `app/core/security.py`: `PASSWORD_HASH_HOWTO` dice nell'ordine la causa (i `$` e un `env_file` del backend nella forma breve, senza `format: raw`, oppure Compose precedente alla 2.30, misurato 62 caratteri su 97), il controllo (`docker compose version` e la forma degli `env_file` nel file Compose), e il rimedio: «rigenera l'hash con scripts/imposta-password.sh <file compose>, che lo scrive in password.env (mai in .env)». Togli il comando `python -c` e «incollalo in .env senza apici».

- [ ] **Step 4: Passano.** Lancia il comando di pytest con `tests/api/test_auth.py tests/test_startup.py`. Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add backend/app/core/config.py backend/app/core/security.py backend/tests/api/test_auth.py backend/tests/test_startup.py
git commit -m "fix: le impostazioni leggono password.env dopo .env; il messaggio del troncamento indica lo script"
```

---

### Task 3: Lo script che scrive `password.env`

**Files:**
- Create: `scripts/imposta-password.sh` (eseguibile), `backend/tests/test_imposta_password.py`

**Interfaces:**
- Consumes: la voce `password.env` del Task 1 (lo script scrive il file che Compose legge).
- Produces: `scripts/imposta-password.sh <file compose>` (vedi «Interfacce prodotte»).

- [ ] **Step 1: I test.** `backend/tests/test_imposta_password.py`. Il docstring dice il perché: si prova lo script vero, copiato in una radice finta in `tmp_path`, perché lo script fa `cd` nella cartella sopra la sua e non deve toccare la radice vera. Si prova con un `docker` finto in testa al `PATH`, che registra gli argomenti e lo standard input e risponde con un hash finto: la suite non chiama Docker, e il giro col container vero è il Task 4.

```python
REAL_SCRIPT = REPO_ROOT / "scripts" / "imposta-password.sh"
HASH_FINTO = "$argon2id$v=19$m=65536,t=3,p=4$c2FsZS1maW50bw$aGFzaC1maW50by1kZWxsYS1zdWl0ZQ"
FAKE_DOCKER = """#!/usr/bin/env bash
printf '%s\\n' "$@" > "$FAKE_DIR/args"
cat > "$FAKE_DIR/stdin"
printf '%s\\n' "$FAKE_OUTPUT"
exit "${FAKE_EXIT:-0}"
"""
```

- la fixture `radice(tmp_path)` crea `tmp_path/repo/scripts/imposta-password.sh` (con `shutil.copy2` dallo script vero, che conserva i permessi), dei `docker-compose.yml` e `docker-compose.prod.yml` vuoti e un `.env` con `SESSION_SECRET=x`. Crea anche `tmp_path/bin/docker` con `FAKE_DOCKER`, eseguibile, e restituisce `(repo, fake_dir)`;
- l'helper `lancia(radice, *args, stdin="segreta\nsegreta\n", output=HASH_FINTO, exit_code=0) -> subprocess.CompletedProcess` esegue `[repo/"scripts/imposta-password.sh", *args]` con `input=stdin`, `capture_output=True`, `text=True`, `cwd=tmp_path`. L'ambiente è quello del processo, più `PATH=<tmp>/bin:$PATH`, `FAKE_DIR`, `FAKE_OUTPUT` e `FAKE_EXIT`.

| Test | Asserzioni |
|---|---|
| `test_scrive_password_env_con_lhash_e_i_permessi_600` | `os.access(REAL_SCRIPT, os.X_OK)`; `lancia(…, "docker-compose.yml")` dà `returncode == 0`; `(repo/"password.env").read_text() == f"APP_PASSWORD_HASH={HASH_FINTO}\n"`; `stat.S_IMODE(...st_mode) == 0o600`; nessun file `password.env.*` resta in `repo`. |
| `test_lhash_si_calcola_nel_container_del_file_indicato` | Con `"docker-compose.prod.yml"`: le righe di `fake_dir/"args"` cominciano con `["compose", "-f", "docker-compose.prod.yml", "run", "--rm", "-T", "--no-deps", "--entrypoint", "python", "backend", "-c"]`, e il programma dopo `-c` contiene `hash_password` e `sys.stdin`; `(fake_dir/"stdin").read_text() == "segreta"` (senza a capo). |
| `test_non_stampa_ne_lhash_ne_la_password` | In `out = r.stdout + r.stderr`: `HASH_FINTO not in out`, `"c2FsZS1maW50bw" not in out` (il sale), `"segreta" not in out`; `"docker-compose.yml" in out` (il messaggio finale dice il comando di riavvio con il file passato). |
| `test_senza_il_file_compose_si_rifiuta_e_non_chiama_docker` (parametrizzato: nessun argomento; `"non-esiste.yml"`) | `returncode == 2`; `"Uso:" in r.stderr`; `not (fake_dir/"args").exists()`; `not (repo/"password.env").exists()`. |
| `test_con_lhash_ancora_in_env_si_rifiuta_prima_di_compose` | Con `.env` che contiene `f"APP_PASSWORD_HASH={HASH_FINTO}\n"`: `returncode == 1`; `not (fake_dir/"args").exists()`; `"APP_PASSWORD_HASH" in r.stderr`; `"sed -i '/^APP_PASSWORD_HASH=/d' .env" in r.stderr`; `HASH_FINTO not in r.stdout + r.stderr`; `not (repo/"password.env").exists()`. |
| `test_una_riga_vuota_in_env_non_ferma` | Con `.env` che contiene `APP_PASSWORD_HASH=\n` (il `.env` copiato dal vecchio `.env.example`): `returncode == 0` e `password.env` scritto. |
| `test_password_vuote_o_diverse_non_scrivono_niente` (parametrizzato: `"\n\n"`, `"una\naltra\n"`) | `returncode == 1`; `not (fake_dir/"args").exists()`; `not (repo/"password.env").exists()`. |
| `test_una_risposta_non_argon2_lascia_password_env_comera` (parametrizzato: `(output="Traceback (most recent call last):", exit_code=0)`, `(output="", exit_code=1)`) | Con un `password.env` preesistente `"APP_PASSWORD_HASH=quello-di-prima\n"`: `returncode == 1`; il file è ancora identico; nessun `password.env.*` resta in `repo`. |

- [ ] **Step 2: Falliscono.** Lancia il comando di pytest con `tests/test_imposta_password.py`. Expected: FAIL, perché lo script non esiste (`FileNotFoundError` nella fixture).

- [ ] **Step 3: Lo script.** `scripts/imposta-password.sh`, `#!/usr/bin/env bash` e `set -euo pipefail`. Il commento in testa dice a cosa serve, perché il file Compose è obbligatorio (la terza lezione di `CLAUDE.md`), perché l'hash va in `password.env` e non in `.env`, e i due usi:
  ```
  sul server:  ./scripts/imposta-password.sh docker-compose.prod.yml
  in locale:   ./scripts/imposta-password.sh docker-compose.yml
  ```
  Il comportamento, in quest'ordine:
  1. `cd "$(dirname "$0")/.."`.
  2. Serve esattamente un argomento, e deve essere un file che esiste. Altrimenti scrive su stderr `Uso: scripts/imposta-password.sh <file compose>` con i due esempi ed esce con 2.
  3. Se `.env` esiste e `grep -qE '^APP_PASSWORD_HASH=.+' .env`, scrive su stderr che in `.env` c'è ancora `APP_PASSWORD_HASH`, che Compose lo legge anche per sostituire i `${...}` e ne stampa dei pezzi negli avvisi, e che va tolto prima con `sed -i '/^APP_PASSWORD_HASH=/d' .env`. Poi esce con 1, **prima di qualunque comando `docker`** e senza mai stampare la riga.
  4. `IFS= read -rsp "Nuova password: " pw; echo >&2`, poi lo stesso con `"Ripetila: "` in `pw2`. Il prompt di `read -p` va su stderr solo davanti a un terminale. Se la password è vuota o le due differiscono, un messaggio su stderr ed esce con 1.
  5. Calcola l'hash dentro un `if !`, così un errore di Compose non fa uscire lo script senza il messaggio:
     ```bash
     PROGRAMMA='import sys
     from app.core.security import hash_password
     print(hash_password(sys.stdin.read()))'
     if ! hash=$(printf '%s' "$pw" | docker compose -f "$file" run --rm -T --no-deps --entrypoint python backend -c "$PROGRAMMA"); then
     ```
     Se fallisce, o se `"$hash"` non comincia con `$argon2id$` o contiene un a capo, scrive su stderr «il container non ha restituito un hash argon2: password.env non è stato toccato» ed esce con 1. Non stampa mai `$hash`.
  6. `umask 077`, `tmp=$(mktemp password.env.XXXXXX)`, `trap 'rm -f "$tmp"' EXIT`, `printf 'APP_PASSWORD_HASH=%s\n' "$hash" > "$tmp"`, `mv "$tmp" password.env`. La sostituzione è atomica: un `password.env` vecchio resta intero finché il nuovo non è pronto.
  7. Su stdout: password.env scritto, lo legge solo il proprietario, e vale dal prossimo avvio del backend con `docker compose -f "$file" up -d --wait --force-recreate backend`.

  `chmod +x scripts/imposta-password.sh`.

- [ ] **Step 4: Passano.** Lancia il comando di pytest con `tests/test_imposta_password.py`. Expected: 11 PASS. Poi `bash -n scripts/imposta-password.sh` (nessun output) e, se `shellcheck` è installato, `shellcheck scripts/imposta-password.sh` (nessun avviso; se non c'è, scrivilo nel report).

- [ ] **Step 5: Commit**
```bash
git add scripts/imposta-password.sh backend/tests/test_imposta_password.py
git ls-files -s scripts/imposta-password.sh | cut -c1-6   # 100755
git commit -m "feat: scripts/imposta-password.sh scrive l'hash in password.env senza mostrarlo"
```

---

### Task 4: Le prove con Docker vero

Nessun file nuovo da committare, se tutto va come atteso. Questo task prova sul Compose vero quel che i test non possono vedere: la sostituzione dei `${...}`, la fusione degli `env_file` e il container che calcola e verifica l'hash. Annota ogni esito per il report.

- [ ] **Step 1: Preparazione.** Dalla radice di `<worktree>`:
  ```bash
  cp .env.example .env
  test ! -e password.env && echo "nessun password.env"
  P="docker compose -p spena-pw-notte -f docker-compose.yml"
  $P config --quiet 2>&1; echo "rc=$?"
  docker compose -p spena-pw-notte -f docker-compose.prod.yml config --quiet 2>&1; echo "rc=$?"
  ```
  Expected: `nessun password.env`; il primo `config` stampa solo `rc=0`, quindi un `password.env` mancante non dà errori né avvisi (Review Focus 3). Il secondo stampa una sola riga di avviso, su `SPENA_HOST` (in `.env.example` è commentata), e `rc=0`: nessun altro nome di variabile.

- [ ] **Step 2: Il controllo vede il difetto.** È il controllo negativo, con un hash **finto**:
  ```bash
  printf 'APP_PASSWORD_HASH=%s\n' '$argon2id$v=19$m=65536,t=3,p=4$Y29udHJvbGxv$ZmludG8' >> .env
  $P config --quiet 2>&1 | grep -c 'variable is not set'
  printf 'x\nx\n' | COMPOSE_PROJECT_NAME=spena-pw-notte scripts/imposta-password.sh docker-compose.yml; echo "rc=$?"
  test ! -e password.env && echo "nessun password.env"
  cp .env.example .env
  ```
  Expected: un numero maggiore di 0, perché è il difetto di oggi; lo script si rifiuta con `rc=1` e dice il comando `sed`; `nessun password.env`.

- [ ] **Step 3: Lo script dal vero.** La prima volta costruisce l'immagine del backend del progetto `spena-pw-notte`.
  ```bash
  printf 'prova-della-notte\nprova-della-notte\n' | COMPOSE_PROJECT_NAME=spena-pw-notte scripts/imposta-password.sh docker-compose.yml; echo "rc=$?"
  stat -c %a password.env
  grep -c '^APP_PASSWORD_HASH=\$argon2id\$' password.env
  $P run --rm -T --no-deps --entrypoint python backend -c 'from app.core.config import get_settings; from app.core.security import verify_password; h = get_settings().app_password_hash; print(h.startswith("$argon2id$"), verify_password("prova-della-notte", h), verify_password("test", h))'
  $P config --quiet 2>&1; echo "rc=$?"
  ```
  Expected: il messaggio finale dello script e `rc=0`, senza l'hash a video; poi `600`, `1` e `True True False`, cioè l'hash arriva intero al container per la strada di `password.env`. L'ultimo comando stampa solo `rc=0`: l'hash in `password.env` non produce avvisi.

- [ ] **Step 4: L'e2e con un `password.env` presente** (Review Focus 2). Il `password.env` dello step 3 resta dov'è. L'e2e intera, con i comandi delle Global Constraints, su uno stack creato da zero. Expected: tutte verdi. Lo stack entra con «test» e non con `prova-della-notte`, perché `.env.e2e` è l'ultimo `env_file`. **Annota `N_e2e`.** Poi `$E2E down -v`, sempre.

- [ ] **Step 5: Pulizia.**
  ```bash
  $P down -v --rmi local
  rm .env password.env
  git status --short
  ```
  Expected: `git status` non stampa niente. Né `.env` né `password.env` compaiono, e non c'è niente da committare.

  Se uno degli esiti non è quello atteso, vale il «Margine di autonomia»: niente schemi nuovi. La voce diventa `bloccato`, con il comando e l'esito misurato.

---

### Task 5: I documenti, la verifica finale e il report

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `docs/prossimi-passi.md`, `next-steps.md`
- Create o modify: `docs/night-reports/<data di oggi>.md`

Prima di cambiarli, leggi i file come sono sul ramo. `<data di oggi>` è la data vera della notte.

- [ ] **Step 1: `README.md`.** Ogni modifica è ancorata al testo di oggi.
  1. **«Avvio locale».** Il blocco che comincia con «E l'hash della password di accesso, generato con lo stesso argon2…», con il suo `docker compose run … hash_password('la-tua-password')`, diventa il comando `./scripts/imposta-password.sh docker-compose.yml`, seguito da un paragrafo. Lo script chiede la password due volte senza mostrarla, calcola l'hash nel container con lo stesso argon2 che l'applicazione usa per verificarlo e lo scrive in `password.env`: fuori da git, permessi 600, senza stamparlo. L'hash non va mai in `.env`, perché Compose legge `.env` anche per sostituire i `${...}` dei file Compose, dove `format: raw` non vale, e ogni `$` dell'hash diventava un avviso che ne stampava un pezzo. Senza `password.env` l'app parte e l'accesso risponde 401. Il paragrafo «Questi due comandi funzionano anche su un `.env` ancora a metà…» ora parla del solo comando del segreto. Il paragrafo «Incolla i due valori in `.env` **senza apici**…» parla del solo segreto, e perde la frase sull'hash e gli apici, che lo script rende inutile.
  2. **«Rumore previsto».** Il paragrafo che comincia con «**Rumore previsto.**» si sostituisce con uno che comincia con «**Nessun avviso previsto.**». Se un comando `docker compose` stampa `The "…" variable is not set`, in `.env` c'è un `$`: quel nome è un pezzo del valore, e non va copiato da nessuna parte. Le righe si trovano senza mostrarne i valori con `grep -n '\$' .env | cut -d= -f1`. Un hash va in `password.env`, con lo script.
  3. **«Deploy».** Dopo il paragrafo «In `.env` servono, oltre alle variabili dell'avvio locale, `SPENA_HOST`…» aggiungi che la password si imposta, sul server, con `./scripts/imposta-password.sh docker-compose.prod.yml`, sempre con il file di produzione, come ogni altro comando lì. Poi il deploy di sempre la fa valere.
  4. **Una sottosezione nuova, «Cambiare la password»**, in fondo a «Deploy»:
     ```bash
     ./scripts/imposta-password.sh docker-compose.prod.yml
     docker compose -f docker-compose.prod.yml up -d --wait --force-recreate backend
     ```
     Aggiungi una frase: i dispositivi già entrati restano dentro, perché il cookie è firmato con `SESSION_SECRET` e non con la password; per buttarli fuori tutti si cambia anche quella.
  5. **Tabella delle variabili.** Nella riga di `APP_PASSWORD_HASH`, lo scopo diventa: «hash argon2 della password di accesso, **in `password.env`, mai in `.env`**, scritto da `scripts/imposta-password.sh`; illeggibile (troncato), il backend non parte».
  6. **«Percorso end-to-end».** Dopo «la password serve conosciuta (`.env.e2e` contiene l'hash della parola `test`, e non protegge niente)» aggiungi che `.env.e2e` è l'ultimo `env_file`, quindi vince anche su un `password.env` presente.

- [ ] **Step 2: `CLAUDE.md`.** La seconda lezione, quella che comincia con «**Compose interpolates `$` in `env_file` values in the short form.**», resta com'è fino a «Do not "simplify" it.». Lì dopo aggiungi:
  ```
  The hash itself lives in `password.env` (gitignored, mode 600, written by
  `scripts/imposta-password.sh <compose file>`), never in `.env`: Compose also reads
  `.env` to substitute the `${...}` inside the compose files, a step `format: raw`
  does not reach, so every `$` of the hash became a "variable is not set" warning
  that printed a piece of it, on every command (seen on the server 2026-10-19).
  `password.env` is the second long-form entry, `required: false`, after `.env`, so
  it wins; the e2e override's `.env.e2e` lands after both. The same test parses all
  three compose files, `.env.example` and `.gitignore` to keep it that way.
  ```

- [ ] **Step 3: `docs/prossimi-passi.md`.** La riga «**I warning `"argon2id" variable is not set`** sul server sono l'interpolazione `${VAR}` di Compose dentro lo YAML, cosmetici e preesistenti. Non inseguirli.» va barrata come le altre voci chiuse del file: `~~…~~ **Chiusa il <data di oggi>, sul ramo `night/hash-password`, non ancora in produzione**`. Poi una frase: non erano cosmetici, perché i nomi delle «variabili» erano pezzi dell'hash; ora l'hash sta in `password.env` (piano `docs/superpowers/plans/2026-11-18-hash-password.md`), e dopo il deploy Mattia cambia la password.

- [ ] **Step 4: `next-steps.md`.**
  1. La riga in testa diventa `_Ultimo aggiornamento: <data di oggi> (fase notte)_`.
  2. Togli la riga della voce, che dalla Preparazione è `in corso`, dovunque sia (`grep -n "stampano pezzi dell'hash della password" next-steps.md`).
  3. In cima a «Fatti (recenti)» aggiungi:
     ```markdown
     - [fatto] <data di oggi> · L'hash della password in `password.env` (secondo `env_file`, forma lunga, `format: raw`, `required: false`), mai in `.env`: Compose non stampa più avvisi con i suoi pezzi; `scripts/imposta-password.sh <file compose>` lo scrive senza mostrarlo, e un test sui tre file Compose, `.env.example` e `.gitignore` impedisce di tornare indietro → branch night/hash-password (da revisionare)
     ```
  4. In cima a «Da fare a mano (solo Mattia)» aggiungi:
     ```markdown
     - [tbd] P3 · Dopo il deploy di night/hash-password: spostare l'hash in `password.env` con una password nuova (i pezzi di quella di oggi sono usciti negli avvisi), con i passi di «Dopo il deploy (solo Mattia)» in `docs/superpowers/plans/2026-11-18-hash-password.md`; poi cancellare la copia `~/spena-env-prima-di-password-env`
     ```
  5. Se la notte ha fatto emergere altro fuori da questo piano, aggiungilo come `idea` o `tbd` nella sezione giusta.

- [ ] **Step 5: Commit dei documenti**
```bash
git add README.md CLAUDE.md docs/prossimi-passi.md next-steps.md
git commit -m "docs: l'hash della password in password.env, lo script e cosa fare sul server"
```

- [ ] **Step 6: La verifica finale.** Il comando di pytest intero, da `<worktree>/backend`. Expected: tutto verde, **`N_pytest` + 20** (8 del Task 1, 1 del Task 2, 11 del Task 3). Se il numero è diverso, scrivi nel report da dove viene la differenza. Dalla radice del worktree, i comandi di «Comandi di verifica». Expected: quello che dice quella sezione. Poi il database dei test di questo ramo non serve più:
  ```bash
  docker exec spena-db-1 psql -U spena -d postgres -c 'DROP DATABASE IF EXISTS spena_test_hash_password WITH (FORCE)'
  ```

- [ ] **Step 7: Il report.** Va in `docs/night-reports/<data di oggi>.md` sul ramo. Se il file c'è già aggiungi una sezione in fondo, altrimenti crealo con il titolo `# Notte del <data di oggi>`. Per questo piano scrivi:
  - il ramo e da dove parte;
  - i conti veri (pytest, e2e) contro quelli della Preparazione;
  - gli esiti dei cinque step del Task 4, comando per comando: i numeri e i `True`/`False`, **mai valori di hash**;
  - l'unico test di oggi cambiato;
  - le scelte del piano che Mattia può voler rivedere (decisioni 2–11, in particolare `required: false`, lo script che non riavvia; la 11 l'ha confermata Mattia il 2026-11-21);
  - se `shellcheck` c'era;
  - la sezione «Dopo il deploy (solo Mattia)» qui sotto, ricopiata intera.

  Niente push, niente merge, niente deploy.
  ```bash
  git add docs/night-reports/
  git commit -m "report: l'hash della password in password.env, la notte"
  ```

---

## Dopo il deploy (solo Mattia)

La notte non tocca la produzione. Questi passi vengono **dopo** che Mattia ha rivisto `night/hash-password`, l'ha unito su `master` e l'ha pushato. Si fanno tutti sul server, in una sessione interattiva, perché lo script chiede la password. Nessun comando qui stampa l'hash. Fino al passo 7 i container in esecuzione tengono l'ambiente con cui sono nati, quindi **la password vecchia continua a funzionare** e non si resta chiusi fuori.

1. Entra e aggiorna:
   ```bash
   ssh -t hetznerserver
   cd ~/sites/spena
   git pull --ff-only
   ```
   C'è un `imposta-password.sh` non tracciato **nella radice**: è un file d'altri tempi (voce «decidere dei due file non tracciati»), e non va usato. Quello giusto è `scripts/imposta-password.sh`.
2. Una copia del `.env` di oggi, fuori dal repository e leggibile solo da te. Serve per tornare indietro:
   ```bash
   cp -p .env ~/spena-env-prima-di-password-env && chmod 600 ~/spena-env-prima-di-password-env
   ```
3. Togli l'hash da `.env`, e controlla senza guardarlo:
   ```bash
   sed -i '/^APP_PASSWORD_HASH=/d' .env
   grep -c '^APP_PASSWORD_HASH=' .env
   ```
   Expected: `0`.
4. Nessun avviso rimasto:
   ```bash
   docker compose -f docker-compose.prod.yml config --quiet
   ```
   Expected: **nessuna riga**. Se stampa delle righe `variable is not set`, in `.env` c'è un altro valore con un `$`. Non copiare quelle righe da nessuna parte: trova il nome con `grep -n '\$' .env | cut -d= -f1`, che stampa solo il numero di riga e il nome, e portalo alla prossima sessione di giorno. Si può comunque andare avanti.
5. La password nuova, **diversa da quella di oggi**. Lo script la chiede due volte senza mostrarla e calcola l'hash nel container di produzione:
   ```bash
   ./scripts/imposta-password.sh docker-compose.prod.yml
   ```
   Se si rifiuta perché in `.env` c'è ancora `APP_PASSWORD_HASH`, il passo 3 non è andato: rifallo.
6. Controlla il file senza aprirlo:
   ```bash
   stat -c %a password.env
   grep -c '^APP_PASSWORD_HASH=\$argon2id\$' password.env
   ```
   Expected: `600` e `1`.
7. Il deploy di sempre (**il `-f docker-compose.prod.yml` non è opzionale**):
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build --wait --wait-timeout 120
   ```
   Poi conferma che il backend ha l'hash nuovo per la strada nuova, sempre senza stamparlo:
   ```bash
   docker compose -f docker-compose.prod.yml exec -T backend python -c 'from app.core.config import get_settings; h = get_settings().app_password_hash; print(h.startswith("$argon2id$"), len(h) > 90)'
   ```
   Expected: `True True`.
8. La prova d'accesso, **in una finestra privata** del browser (senza il cookie di sempre), in quest'ordine: prima la password vecchia, che deve rispondere «password errata»; poi, nella stessa finestra, quella nuova, che deve entrare. Il telefono e i browser già entrati restano dentro: è previsto (passo 10).
9. Se tutto è a posto, cancella la copia del passo 2, che contiene l'hash vecchio e gli altri segreti:
   ```bash
   rm ~/spena-env-prima-di-password-env
   ```
   I pezzi dell'hash vecchio sono stati stampati solo dal comando `docker compose`, nel terminale, e non dai container, quindi sul server non c'è nessun log da ripulire. Con la password cambiata non valgono più niente.
10. `SESSION_SECRET` resta com'è (decisione 11, confermata da Mattia il 2026-11-21). Se un giorno Mattia vuole buttare fuori tutti i dispositivi già entrati, deve generare un segreto nuovo e metterlo in `.env` al posto di quello vecchio, poi rilanciare `docker compose -f docker-compose.prod.yml up -d --wait --force-recreate backend`. Dopo, ogni dispositivo deve rientrare con la password nuova.

**Se l'accesso non va.** Si torna alla situazione di prima senza restare chiusi fuori:

- **Il deploy del passo 7 non diventa `healthy`.** Leggi la causa con `docker compose -f docker-compose.prod.yml logs backend | tail -n 40`. Se nomina `APP_PASSWORD_HASH`, l'hash è arrivato rotto: rifai il passo 5 e poi `docker compose -f docker-compose.prod.yml up -d --wait --force-recreate backend`. Se va ancora male, passa al ritorno indietro qui sotto.
- **Il deploy va, ma la password nuova non entra.** Rifai il passo 5, scrivendo la password con calma, poi `docker compose -f docker-compose.prod.yml up -d --wait --force-recreate backend` e il passo 8. Se non entra ancora, passa al ritorno indietro.
- **Il ritorno indietro.** Rimette il `.env` di prima, con l'hash vecchio, e toglie `password.env`. Il codice nuovo accetta l'assenza del file (`required: false`):
  ```bash
  cp -p ~/spena-env-prima-di-password-env .env
  mv password.env ~/spena-password-env-non-andato
  docker compose -f docker-compose.prod.yml up -d --wait --wait-timeout 120 --force-recreate backend
  ```
  La password vecchia torna a entrare, e gli avvisi tornano a stampare i pezzi dell'hash vecchio, che sono gli stessi già usciti. Porta alla prossima sessione di giorno cosa è successo (i messaggi dei comandi, non i valori), e cancella `~/spena-password-env-non-andato`.
