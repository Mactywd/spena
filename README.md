# Spena

Lista della spesa, dispensa e ricettario per una persona sola. La v1 chiude un
cerchio e uno solo:

> scrivi la lista → torni dalla spesa e la sistemi in dispensa → cucini una
> ricetta → ciò che è finito torna in lista da sé

Tutto il resto — diario dei pasti, nutrienti, suggerimenti — si innesta su questo
ciclo nelle fasi successive e non c'è dentro.

## La decisione da cui dipende tutto: niente quantità

La dispensa non conosce quantità, unità di misura né scadenze. Un ingrediente sta
in uno di tre stati: `available`, `low`, `finished`. Non è una mancanza, è una
scelta: toglie le conversioni di unità e la manutenzione quotidiana che fa
abbandonare le app di questo tipo. Il prezzo è che i valori nutrizionali non si
possono dedurre dalle scorte, ed è il motivo per cui la nutrizione è in fase 3 su
un binario suo.

Il `low` serve a qualcosa grazie a una seconda regola: ogni ingrediente di una
ricetta è `primary` o `secondary`. Un primario vuole `available`, un secondario si
accontenta di `low`. Un barattolo di pelati quasi vuoto non fa una pasta al
pomodoro ma fa un soffritto.

Le due decisioni, per esteso e con le loro conseguenze, sono in
[`docs/superpowers/specs/2026-09-11-spena-design.md`](docs/superpowers/specs/2026-09-11-spena-design.md),
che resta l'autorità su scopo e perimetro.

## Cosa serve

- **Docker con Compose 2.30 o successivo.** Non è una preferenza: i file Compose
  usano la forma lunga di `env_file` con `format: raw`, introdotta in 2.30. Con una
  versione precedente l'hash argon2 della password viene interpretato da Compose —
  i `$` diventano riferimenti a variabili — e arriva al container troncato: misurato,
  97 caratteri su 62, e l'accesso non funziona mai. Verifica con
  `docker compose version`.
- **Node 22 o successivo**, solo per far girare i test del frontend da fuori Docker.

## Avvio locale

```bash
cp .env.example .env
```

Poi riempi le due variabili obbligatorie. Entrambe si generano con il Python del
container, perché «Cosa serve» non promette un Python sull'host. Il segreto di
sessione:

```bash
docker compose run --rm --build backend \
  python -c "import secrets; print(secrets.token_urlsafe(48))"
```

E l'hash della password di accesso, generato con lo stesso argon2 che l'applicazione
usa per verificarlo:

```bash
docker compose run --rm --build backend \
  python -c "from app.core.security import hash_password; print(hash_password('la-tua-password'))"
```

Questi due comandi funzionano anche su un `.env` ancora a metà: `docker compose run
... python -c` sostituisce il comando del container, quindi l'applicazione non parte
e i controlli all'avvio non scattano. Per `docker compose up`, invece, i due valori
devono essere già in `.env`.

Incolla i due valori in `.env` **senza apici**. L'hash contiene dei `$` e sembra
naturale proteggerlo con degli apici singoli: non farlo. `format: raw` non li
toglie, quindi arriverebbero dentro il container come parte dell'hash e la verifica
fallirebbe sempre.

Se `SESSION_SECRET` resta vuota — o al valore di esempio — il backend **rifiuta di
partire**, e lo dice nei log con il comando per generarne una. È deliberato: un
server che firma i cookie con un segreto pubblicato su git non deve sembrare sano.

Lo stesso se `APP_PASSWORD_HASH` c'è ma non è un hash argon2 leggibile, che è come
arriva un hash troncato dai `$`: il backend rifiuta di partire nominando la causa
probabile e il comando per rigenerarlo. Senza quel rifiuto l'unico sintomo sarebbe
«password errata» per qualunque password, su un `.env` che a occhio sembra pieno.
Vuota invece lascia partire: è il `.env` non ancora riempito, e l'accesso risponde
401 dicendo il vero.

Poi:

```bash
docker compose up -d --build --wait
docker compose exec backend python -m app.cli.seed   # 169 ingredienti, 26 ricette
```

Le migrazioni non sono un passo a mano: il backend esegue `alembic upgrade head`
all'avvio, prima di servire (spec §13), e se la migrazione fallisce il container
muore invece di rispondere contro uno schema vecchio. Il `--wait` serve al comando
dopo: senza, `up -d` torna appena il container è partito e la semina potrebbe
arrivare mentre le migrazioni sono ancora in corso.

L'app è su <http://localhost:5173>. Il seme è idempotente: rieseguirlo non duplica
niente.

**Rumore previsto.** Ogni comando `docker compose` stampa avvisi come
`The "argon2id" variable is not set. Defaulting to a blank string.` Sono cosmetici:
vengono dalla lettura del `.env` che Compose fa per sostituire i `${...}` dentro al
file Compose stesso, che è una cosa diversa da `env_file:` e non accetta
`format: raw`. Verificato: dentro al container `APP_PASSWORD_HASH` è lungo 97
caratteri, cioè intero.

## Test

Tre suite separate. Ognuna va lanciata dalla sua directory.

### Backend

Gira su Postgres vero, non su SQLite: lo schema ha bisogno di `vector` e di
`pg_trgm`. Il database di test va creato una volta sola:

```bash
docker compose up -d db
docker compose exec -T db psql -U spena -c "CREATE DATABASE spena_test"
```

Poi, **da `backend/`**, un ambiente virtuale con le dipendenze di sviluppo — la
suite gira sull'host, non dentro al container, perché deve poter importare
`app.core.config` e spegnere la lettura del `.env`:

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -e ".[dev,ai]"
.venv/bin/python -m pytest
```

`ai` oltre a `dev` perché un test solo esegue l'`import anthropic` vero
(`tests/test_image_dependencies.py`), e senza il pacchetto si salta: è il percorso
che nessun test toccava quando l'immagine non installava l'extra, e saltarlo
significa non difenderlo.

La suite non tocca la rete: Open Food Facts e Claude girano su fixture registrate, e
non legge il tuo `.env` (vedi il commento in `backend/tests/conftest.py`).

### Frontend

La prima volta servono le dipendenze, e per il percorso end-to-end anche il browser
che Playwright si scarica a parte (i test di Vitest non ne hanno bisogno):

```bash
cd frontend && npm install
npx playwright install chromium
```

Poi, **da `frontend/`**, e l'avvertenza non è pedanteria: lanciato da una
sottodirectory, Vitest riporta «No test files found» e passa, cioè dà un verde
falso.

```bash
cd frontend && npx vitest run
```

### Percorso end-to-end

Attraversa lista, dispensa, ricettario, cottura e rientro in lista con un browser
vero, contro l'app costruita e servita da Nginx. Gira su uno stack Compose a parte,
`spena-e2e`, per due motivi: la password serve conosciuta (`.env.e2e` contiene
l'hash della parola `test`, e non protegge niente) e lo stack va distrutto con i
volumi alla fine, cosa che non si può fare sul progetto di sviluppo senza perdere la
dispensa vera.

```bash
E2E="docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml"
$E2E up -d --build --wait
$E2E exec -T backend python -m app.cli.seed
(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
$E2E down -v
```

Il `-p spena-e2e` e il `-f docker-compose.e2e.yml` vanno ripetuti in ogni comando:
`down -v` sul progetto di default cancellerebbe il volume della dispensa vera.

Il percorso scrive in lista e in dispensa, quindi **vuole uno stack appena creato**:
rieseguirlo senza `down -v` lo fa fallire dicendo che lo stack non è pulito.

## Provare la fotocamera dal telefono

Lo scanner di codici a barre ha bisogno di `getUserMedia`, che il browser concede
solo in un contesto sicuro: HTTPS o `localhost`. Da telefono serve quindi HTTPS, ed
è per questo che il server di sviluppo ha un certificato autofirmato.

```bash
cd frontend && npm run dev -- --host
```

Vite stampa l'indirizzo sulla rete locale (`https://192.168.x.x:5173`). Aprilo dal
telefono e accetta il certificato: è autofirmato, il browser avvisa, è normale. Il
backend deve girare in parallelo (`docker compose up -d`), il proxy di Vite inoltra
`/api` a <http://localhost:8000>.

> **Questo percorso non è mai stato eseguito.** Non c'era un telefono durante lo
> sviluppo: `getUserMedia`, la lettura di un codice a barre reale e il permesso della
> fotocamera su un dispositivo vero non sono stati provati nemmeno una volta. I test
> coprono il componente dello scanner in jsdom, con la fotocamera finta, e il
> percorso end-to-end usa l'inserimento manuale del codice. La verifica resta da
> fare, e sono questi quattro passaggi:
>
> 1. Scrivi tre cose in lista, una con un errore di battitura, e controlla che
>    l'autocomplete la riconosca.
> 2. Spunta tutto e sistema la spesa scansionando almeno un codice a barre reale.
> 3. Apri una ricetta e controlla che gli stati degli ingredienti corrispondano a
>    ciò che hai in casa.
> 4. Cucina, dichiara finita una cosa, e verifica che sia tornata in lista da sé.
>
> Se questi quattro passaggi filano, la v1 è completa.

## Deploy in produzione

`docker-compose.prod.yml` pubblica un solo servizio, il frontend: Nginx inoltra
`/api/` al backend, che quindi non ha porte esposte. Davanti c'è Traefik, su una
rete esterna che deve esistere già:

```bash
docker network create traefik-public   # solo la prima volta
```

In `.env` servono, oltre alle variabili dell'avvio locale, `SPENA_HOST` con il nome
di host pubblicato e le `POSTGRES_*` (qui non hanno default: il Compose di
produzione non ne inventa uno).

```bash
docker compose -f docker-compose.prod.yml up -d --build --wait --wait-timeout 120
docker compose -f docker-compose.prod.yml exec backend python -m app.cli.seed
```

Il `--wait-timeout` serve al caso in cui una migrazione futura fallisca. Qui il
backend ha `restart: unless-stopped`: il container muore sulla migrazione, Docker lo
rianima, non diventa mai `healthy` e `--wait` senza scadenza aspetta per sempre senza
dire niente. Con la scadenza il comando torna con un errore dopo due minuti (oggi
l'avvio ne impiega pochi secondi: la 0003 è l'ultima migrazione e il database è
vuoto), e la causa vera si legge in un posto solo:

```bash
docker compose -f docker-compose.prod.yml logs backend
```

L'errore di Alembic è lì, ripetuto a ogni riavvio. Lo schema non resta a metà:
`alembic/env.py` avvolge tutte le revisioni in una sola transazione e Postgres ha DDL
transazionale, quindi la migrazione fallita è come se non fosse mai partita.

Anche qui le migrazioni girano all'avvio del backend, quindi un `git pull` con una
migrazione nuova e un `up -d --build` bastano: non c'è un comando da ricordarsi. Il
seme invece resta a mano, perché non è un'operazione da ripetere a ogni riavvio.

Il progetto Compose, in mancanza di `-p`, si chiama `spena` anche qui, cioè come
quello di sviluppo: sulla stessa macchina i due stack si contenderebbero gli stessi
nomi di container e lo stesso volume `spena_pgdata`. Su un server dedicato non
succede; se devi provare il Compose di produzione dove sviluppi, dagli un nome suo
con `-p spena-prod`.

HTTPS è necessario e non opzionale, per due motivi che si sommano: senza di esso la
fotocamera non parte, e il cookie di sessione viaggia con `Secure` — il Compose di
produzione impone `COOKIE_SECURE=true` al servizio backend — quindi su `http` il
browser non lo rimanderebbe e ogni chiamata dopo l'accesso risponderebbe 401.

## Variabili d'ambiente

| Variabile | Default | Scopo |
|---|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | vedi `.env.example` | connessione al database |
| `SESSION_SECRET` | nessuno, obbligatorio | firma del cookie di sessione; vuota, il backend non parte |
| `APP_PASSWORD_HASH` | nessuno, obbligatorio | hash argon2 della password di accesso; illeggibile (troncato), il backend non parte |
| `COOKIE_SECURE` | `false` | `true` in produzione: il cookie solo su HTTPS |
| `ANTHROPIC_API_KEY` | vuoto | stesura ricette con l'AI e abbinamenti incerti |
| `EMBEDDING_BACKEND` | `local` | `local`, `http` oppure `fake`; `local` richiede `INSTALL_EMBEDDINGS=1` |
| `INSTALL_EMBEDDINGS` | `0` | argomento di build: a `1` l'immagine installa sentence-transformers |
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-small` | modello locale; cambiandolo va rimisurata `SEMANTIC_MAX_DISTANCE` (vedi sotto) |
| `EMBEDDING_ENDPOINT` | vuoto | solo con `EMBEDDING_BACKEND=http` |
| `OFF_BASE_URL` | api ufficiale di Open Food Facts | sovrascrivibile nei test |
| `OFF_TIMEOUT_SECONDS` | `3` | oltre il quale si degrada all'inserimento manuale |
| `SPENA_HOST` | nessuno | solo in produzione: host pubblicato da Traefik |

Nessuna di queste, mancando, porta a un vicolo cieco nell'interfaccia: senza chiave
Anthropic la ricetta si scrive a mano, senza modello di embedding la ricerca resta
quella testuale, con Open Food Facts irraggiungibile il prodotto si crea a mano. È
una regola di casa, non un caso fortunato.

### La ricerca semantica è facoltativa, e per default è spenta

`INSTALL_EMBEDDINGS` è un argomento di build, non una variabile d'ambiente: va
scritto in `.env` come le altre, ma ha effetto solo ricostruendo l'immagine
(`docker compose up -d --build`). Entrambi i file Compose lo leggono da lì, quindi è
un posto solo.

| | `INSTALL_EMBEDDINGS=0` (default) | `INSTALL_EMBEDDINGS=1` |
|---|---|---|
| immagine del backend | 233 MB | qualche GB: sentence-transformers trascina torch |
| prima ricerca | immediata | il modello (circa 500 MB) si scarica al primo uso, una volta sola: sta nel volume `hfcache` e sopravvive a `up -d --build` |
| ricerca nel ricettario | solo testuale, su `pg_trgm` e `search_tsv` | ibrida, vettoriale più testuale come nella spec §8.5 |
| ricette salvate | `embedding` a NULL | con il vettore |

Cosa si perde davvero con `0`: la ricerca trova solo ciò che contiene le parole che
hai scritto. «qualcosa di veloce con le uova» non trova la frittata, e «pomodoro»
non trova «Pasta al sugo». Tutto il resto dell'app funziona identico, ed è la
degradazione che la spec §11 prevede — non un guasto. Il backend lo scrive nei log
al primo tentativo di calcolare un vettore, una volta per processo:

```
semantic search non disponibile: ... — la ricerca resta solo testuale.
Per accenderla: INSTALL_EMBEDDINGS=1 in .env e `docker compose up -d --build`.
```

Se accendi `1` *dopo* aver seminato, le 26 ricette del seme restano senza vettore:
il seme è idempotente e non le riscrive. Per rifarle, cancella il volume del
database e risemina — oppure accetta che solo le ricette nuove siano cercabili
anche per somiglianza. Nel frattempo il ricettario continua a mostrare la riga
«Ricerca solo testuale»: `/recipes/search-mode` risponde `semantic: true` solo se
esiste almeno una ricetta con il vettore, quindi l'avviso dice quel che cercare fa
davvero e non quel che il fornitore saprebbe fare.

**Il primo ingresso in Ricette dopo una ricostruzione.** È quello che fa partire il
download: lo schermo interroga `/recipes/search-mode`, che calcola un vettore di
prova. Finché il modello non è scaricato la ricerca resta testuale — il backend
risponde entro cinque secondi invece di far aspettare — e lo dice con la riga grigia;
qualche minuto dopo, ricaricando, la ricerca è ibrida. Non è un guasto e non serve
fare niente.

**Se cambi `EMBEDDING_MODEL`** va rimisurata `SEMANTIC_MAX_DISTANCE` in
`backend/app/services/recipe_search.py`: la scala delle distanze è una proprietà del
modello, e quella soglia è misurata su `intfloat/multilingual-e5-small`. Finché non è
rimisurata il backend rinuncia alla metà semantica invece di applicare a un modello
nuovo un numero che vale per un altro — lo scrive nei log, una volta per processo, e
`/recipes/search-mode` risponde `semantic: false`, cioè il ricettario te lo dice.

Con `INSTALL_EMBEDDINGS=0` tieni `EMBEDDING_BACKEND=local` così com'è: è la
configurazione che si accende da sola il giorno in cui ricostruisci con `1`.
L'alternativa è `http` con un `EMBEDDING_ENDPOINT` tuo, che dà la ricerca semantica
senza torch dentro all'immagine.

## Oltre la v1

Le fasi 2 (scontrino, nutrienti da foto dell'etichetta, import massivo di ricette),
3 (diario dei pasti e micronutrienti) e 4 (motore di suggerimenti) sono descritte
nel §4 della
[spec di design](docs/superpowers/specs/2026-09-11-spena-design.md). La tabella
`cooking_events` esiste già in v1 senza nessun consumatore proprio perché la fase 3
abbia una storia su cui appoggiarsi.
