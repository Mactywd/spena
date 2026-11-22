# Spena

Lista della spesa, dispensa e ricettario per una persona sola. La v1 chiude un
cerchio e uno solo:

> scrivi la lista → torni dalla spesa e la sistemi in dispensa → cucini una
> ricetta → ciò che è finito torna in lista da sé

Tutto il resto — diario dei pasti, nutrienti, suggerimenti — si innesta su questo
ciclo nelle fasi successive e non c'è dentro.

## La decisione da cui dipende tutto: niente quantità

La dispensa non conosce quantità né unità di misura. Un ingrediente sta in uno di
tre stati: `available`, `low`, `finished`. Non è una mancanza, è una scelta: toglie
le conversioni di unità e la manutenzione quotidiana che fa abbandonare le app di
questo tipo. Il prezzo è che i valori nutrizionali non si possono dedurre dalle
scorte, ed è il motivo per cui la nutrizione è in fase 3 su un binario suo.

Una data la conosce, dal 2026-09-21, ed è l'unica: la **scadenza** del singolo
elemento di dispensa, facoltativa. Non entra negli stati e non cambia la
disponibilità di niente — una cosa scaduta resta disponibile, la riga lo dice e chi
cucina sceglie. La regola si piega per una data e non per una quantità perché una
quantità va mantenuta e mente dal giorno che smetti, mentre una scadenza si scrive
una volta sola e non si tocca più.

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

E la password di accesso:

```bash
./scripts/imposta-password.sh docker-compose.yml
```

Lo script chiede la password due volte senza mostrarla, calcola l'hash nel container
con lo stesso argon2 che l'applicazione usa per verificarlo e lo scrive in
`password.env`: fuori da git, permessi 600, senza stamparlo. L'hash non va mai in
`.env`, perché Compose legge `.env` anche per sostituire i `${...}` dei file Compose,
dove `format: raw` non vale, e ogni `$` dell'hash diventava un avviso che ne stampava
un pezzo. Senza `password.env` l'app parte e l'accesso risponde 401.

Il comando del segreto funziona anche su un `.env` ancora a metà: `docker compose run
... python -c` sostituisce il comando del container, quindi l'applicazione non parte
e i controlli all'avvio non scattano. Per `docker compose up`, invece, il valore
deve essere già in `.env`.

Incolla il segreto in `.env` **senza apici**: `format: raw` non li toglie, quindi
arriverebbero dentro il container come parte del valore.

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
docker compose exec backend python -m app.cli.seed --con-ricette   # anagrafica e 26 ricette
```

Le migrazioni non sono un passo a mano: il backend esegue `alembic upgrade head`
all'avvio, prima di servire (spec §13), e se la migrazione fallisce il container
muore invece di rispondere contro uno schema vecchio. Il `--wait` serve al comando
dopo: senza, `up -d` torna appena il container è partito e la semina potrebbe
arrivare mentre le migrazioni sono ancora in corso.

L'app è su <http://localhost:5173>. Il seme è idempotente: rieseguirlo non duplica
niente.

**Nessun avviso previsto.** Se un comando `docker compose` stampa
`The "…" variable is not set`, in `.env` c'è un `$`: quel nome è un pezzo del valore,
e non va copiato da nessuna parte. Le righe si trovano senza mostrarne i valori con
`grep -n '\$' .env | cut -d= -f1`. Un hash va in `password.env`, con lo script.

## Portare ricette nel ricettario

```bash
docker compose exec backend python -m app.cli.import_gz --limit 200
```

Scarica un lotto di ricette da GialloZafferano: una pagina alla volta, con una pausa
di cortesia, e mai due volte lo stesso indirizzo. Rilanciarlo prende il lotto
successivo, quindi il ricettario si riempie a tappe e non in una notte.

Per tutto il catalogo (8.469 ricette nella sitemap al 2026-09-24) c'è `--tutto`: legge
la sitemap una volta e va a lotti da 50 fino in fondo, poi decide i termini rimasti.
Sono ore, quindi si lancia in background; il come, e cosa controllare prima e dopo,
sta in [`docs/import-gz-runbook.md`](docs/import-gz-runbook.md). Le 26 ricette di
semina, in produzione, si tolgono prima con
`python -m app.cli.drop_seed_recipes`, che senza `--conferma` elenca e basta.

Dopo lo scarico, gli ingredienti che l'anagrafica non riconosce li decide l'AI: uno per
uno, e quelli che non sa giudicare li lascia in coda. Le ricette entrano da sé, quindi
nel caso normale il ricettario si riempie senza altri passaggi — restano i due comandi
qui sotto, che il comando stesso ti nomina quando servono: `decide_units` se ha
depositato unità di misura nuove, `reindex` se tieni accesa la ricerca semantica.

Ci vuole `OPENROUTER_API_KEY` in `.env`. Senza, tutto continua a funzionare a mano: i
termini restano in coda e si decidono dalla riga in cima al ricettario, un tocco
ciascuno, come prima che questa funzione esistesse.

Quel che l'AI ha deciso si rivede da `/ricette/importa`, nell'elenco «Deciso dall'AI»:
ogni riga dice cosa ha fatto — collegato a un ingrediente, o ignorato — e si può
annullare. Non c'è un'etichetta «creato» a parte: nessun fatto scritto oggi permette
di distinguere un aggancio che ha usato un ingrediente già in anagrafica da uno che
l'ha creato, quindi entrambi si dicono «collegato». Annullare rimette il termine in
coda, cancella l'alias che aveva scritto, cancella l'ingrediente creato se nessun
altro lo usa, e rifà le ricette che ne erano nate. Se una di quelle ricette l'hai già
cucinata, chiede conferma prima: lo storico sopravvive ma perde il collegamento alla
ricetta.

Ogni decisione vale per sempre — diventa un alias dell'ingrediente, e la conosce anche
l'autocomplete della lista — quindi ogni giro costa meno del precedente: un termine già
deciso non torna mai al modello.

Per correggere l'anagrafica a lotti — un termine collegato all'ingrediente sbagliato,
due ingredienti che sono la stessa cosa, un reparto sbagliato — c'è un piano scritto in
`data/fixes/`, applicato da un comando che senza `--conferma` fa una prova completa e
non salva niente:

```bash
docker compose exec backend python -m app.cli.fix_registry /data/fixes/2026-09-27-anagrafica.json
docker compose exec backend python -m app.cli.fix_registry /data/fixes/2026-09-27-anagrafica.json --conferma
```

I passi (`decide`, `remap`, `merge`, `recategorize`, `rename`, `move_alias`) sono
descritti in testa a `backend/app/cli/fix_registry.py`. Usano lo stesso annullamento e
la stessa decisione a mano della schermata, quindi le ricette toccate si rifanno dalla
pagina scaricata; il costo scelto a mano sopravvive. Il piano applicato resta nel
repository come storia di cosa si è deciso: non si rilancia, se ne scrive uno nuovo.

Per sapere quale provider di OpenRouter serve il modello e a quanto:

```bash
docker compose exec backend python -m app.cli.llm_prices
```

### Le unità di misura delle dosi

Una ricetta importata porta con sé le parole con cui la fonte scrive le dosi —
«cucchiai», «spicchio», «costa» — e ogni parola nuova entra nel registro non decisa:
si mostra com'è arrivata, e il riporziona la scala lo stesso. Per farle scrivere bene
al singolare e al plurale:

```bash
docker compose exec backend python -m app.cli.decide_units
```

Chiede all'AI un lotto di parole per volta e applica solo le risposte che sa
verificare; l'ultima riga dice quante ne restano, e allora si rilancia. `import_gz` lo
nomina quando ne ha depositate di nuove. Senza, non si rompe niente: le dosi
riporzionate mostrano la parola grezza, che è brutto e non è sbagliato.

Una decisione storta si annulla con `--azzera <parola>`, e il giro dopo la ridecide —
ma se il modello rifà lo stesso errore, e capita, la si scrive a mano:

```bash
docker compose exec backend python -m app.cli.decide_units --imposta cucchiai cucchiaio cucchiai
```

La riga passa a `decided_by = "human"` e il comando non la ripesca più, finché non la
si azzera: altrimenti il giro dopo il modello rifarebbe l'errore appena corretto.

Una volta sola dopo la migrazione `0008`, e poi ogni volta che il parser delle dosi
migliora:

```bash
docker compose exec backend python -m app.cli.reparse_quantities
```

Rilegge `quantity_text` — che non si riscrive mai — e riempie le colonne che servono a
riporzionare. È rieseguibile per costruzione, e dice quante unità nuove ha depositato.

Una volta sola dopo la migrazione `0010`, per il costo delle ricette già importate:

```bash
docker compose exec backend python -m app.cli.reread_costs
```

Le pagine prese prima di R9 non avevano il costo, e l'HTML non si conserva: il comando
le riscarica una alla volta, con la stessa pausa dell'import, e scrive solo il costo,
solo dove manca. Un costo scelto a mano non si tocca; se la fonte chiede di smettere
si ferma, e rilanciato riprende da dove era. Le pagine importate da qui in avanti il
costo lo portano già.

### Le figure degli ingredienti in dispensa

Ogni riga della Dispensa ha a sinistra del nome la figura del suo ingrediente: un'emoji
di un elenco chiuso (fermo a Emoji 14.0, in `backend/app/domain/emoji.py`), o, dove non
ce n'è una, l'icona del reparto in grigio. Un ingrediente nasce senza figura; a deciderla
è l'AI, con un comando da lanciare a mano — una volta dopo la migrazione `0013`, e poi
quando si vuole dare una figura agli ingredienti nati dopo:

```bash
docker compose exec backend python -m app.cli.decide_emoji
```

Chiede all'AI cento nomi per volta, e scrive solo dove la figura non è ancora decisa e
solo un'emoji dell'elenco (o «nessuna», se nessuna va bene); una risposta che non sa
verificare la lascia da decidere. L'ultima riga dice quanti ingredienti restano, e allora
si rilancia; ma se quel numero non scende fra due lanci, quelli restano col ripiego del
reparto (o se ne sceglie la figura a mano in Anagrafica) e rilanciare ancora non serve.
Se l'AI non risponde, il comando lo dice con una riga «figure non disponibili (…)», col
perché fra parentesi: i lotti già decisi prima del guasto restano scritti (ogni lotto si
salva appena finito), e il guasto ferma solo quelli dopo. Se quella riga torna identica a
ogni lancio, il perché è lì. Senza `OPENROUTER_API_KEY` non si rompe niente: le righe
mostrano l'icona del reparto. Una figura sbagliata si corregge nella scheda dell'ingrediente in
Anagrafica, «Cambia figura»; una scelta fatta lì, «Nessuna» compresa, il comando non la
tocca più. In produzione, con `-f docker-compose.prod.yml` come ogni altro comando.

### I sostituti degli ingredienti

«Sostituisci», dentro una ricetta, legge una risposta salvata per ingrediente e contesto
(dolce o salato): uno o più sostituti, «si può omettere», «insostituibile». Le decide
l'AI, una voce per chiamata, e le scrive solo dove non c'è una risposta:

```bash
docker compose exec backend python -m app.cli.decide_substitutes --dry-run
docker compose exec backend python -m app.cli.decide_substitutes --limit 20
docker compose exec backend python -m app.cli.decide_substitutes
```

Il primo non chiama nessuno: dice quante voci mancano e, dopo un lancio vero, quanto
costerebbe il resto con la media pagata. Il secondo chiede le venti più usate e stampa
una riga per voce, da guardare prima del resto. L'ultima riga dice sempre quante voci
restano. Senza il comando non si rompe niente: una voce che manca si chiede all'AI la
prima volta che qualcuno tocca «Sostituisci». Le risposte si correggono in Anagrafica,
nella scheda dell'ingrediente, e per una ricetta sola dalla ricetta («Non va bene qui»);
una correzione a mano il comando non la tocca mai.

### I vettori della ricerca semantica

Se tieni accesa la ricerca semantica (`INSTALL_EMBEDDINGS=1`), dopo un import esegui:

```bash
docker compose exec backend python -m app.cli.reindex
```

Calcola i vettori delle ricette che non ne hanno. Senza, le ricette importate
restano cercabili solo per le parole che contengono, e rieseguire l'import non
rimedia: è idempotente e non torna su ciò che è già dentro.

### La fonte, e cosa vuol dire raccoglierla

Una nota che vale la pena sapere. Il `robots.txt` della fonte vieta esplicitamente i
crawler AI, e le sue condizioni d'uso con ogni probabilità vietano la raccolta
sistematica. Questo comando non è un crawler AI e si comporta di conseguenza, ma la
scelta di usarlo è di chi lo esegue: le ricette restano nel tuo database, non si
ridistribuiscono, e ognuna conserva l'indirizzo originale, che la schermata della
ricetta offre con «apri l'originale». La decisione e i suoi limiti stanno in §3 di
`docs/superpowers/specs/2026-09-12-import-ricette-design.md`.

## I valori nutrizionali degli ingredienti (CIQUAL)

I nutrienti medi di un ingrediente generico — `pomodoro`, non una marca — vengono dalla
tabella CIQUAL 2025 dell'Anses: Anses. 2025. Table de composition nutritionnelle des
aliments Ciqual (<https://doi.org/10.57745/RDMHWY>, licenza Etalab 2.0, che chiede di
citare la fonte). Il file è `data/ciqual/ciqual-2025.xlsx`; si carica, e si ricarica
quando esce un'edizione nuova:

```bash
docker compose exec backend python -m app.cli.load_ciqual --dry-run   # legge e conta, non scrive
docker compose exec backend python -m app.cli.load_ciqual
```

Un file che non torna — una colonna con un'unità diversa da quella attesa, una colonna
d'obbligo che manca — non scrive niente e dice quale colonna. Poi l'AI sceglie l'alimento
di ogni ingrediente alimentare che non ne ha uno, fra candidati trovati nella tabella:

```bash
docker compose exec backend python -m app.cli.s4_pilot             # prima: 30 casi con la risposta nota
docker compose exec backend python -m app.cli.decide_ciqual --limit 20
docker compose exec backend python -m app.cli.decide_ciqual
```

Il pilota non scrive niente sugli ingredienti: dice quanti casi l'AI azzecca, contro la
soglia del 90%, e quanto è costato. `decide_ciqual` scrive solo dove un ingrediente non ha
ancora una scelta, e l'ultima riga dice quanti ne restano. Una scelta si corregge nella
scheda dell'ingrediente in Anagrafica, «Valori nutrizionali»: «Cambia alimento» (si cerca
in francese, come la tabella, o per codice), «Nessun alimento adatto», o «Annulla la
scelta», che la ridà all'AI. Una scelta fatta lì il comando non la tocca. In produzione,
con `-f docker-compose.prod.yml` come ogni altro comando.

### I pesi delle dosi, e i nutrienti di una ricetta

Una ricetta dice dosi, non grammi. Le dosi in grammi o in litri si pesano da sé (i litri
con densità 1, salvo olio, miele, sciroppi e latte condensato); le altre — «1 spicchio»,
«2 cucchiai», «2» uova — hanno un peso per coppia ingrediente × unità canonica, che decide
l'AI:

```bash
docker compose exec backend python -m app.cli.decide_grams --limit 40
docker compose exec backend python -m app.cli.decide_grams
```

Scrive solo dove una coppia non ha ancora un peso; l'ultima riga dice quante ne restano.
Un peso si corregge nella scheda dell'ingrediente in Anagrafica, «Pesi per unità», e
«Annulla il peso» lo ridà all'AI. Il pilota (`s4_pilot`) prova anche venti pesi noti.
Nel dettaglio di una ricetta, in fondo, «Valori nutrizionali» somma le righe che hanno una
dose, un alimento CIQUAL e un peso, e dice quali restano fuori e perché («q.b.» fuori per
scelta). Gli stessi numeri escono da `GET /api/v1/recipes/{id}/nutrition`.

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
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest
```

Niente extra `ai`: il client dell'LLM parla HTTP con `httpx`, che è una dipendenza di
base, non un extra installato a parte come lo era `anthropic`.
`tests/test_image_dependencies.py` difende che resti così.

La suite non tocca la rete: Open Food Facts e l'LLM girano su fixture registrate, e
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

Il controllo dei tipi è un comando separato, e il nome che sembra ovvio è quello
sbagliato: `frontend/tsconfig.json` è in stile «solution», con `"files": []` e solo
riferimenti ai sotto-progetti, quindi `npx tsc --noEmit` legge quel file, non trova
niente da compilare ed esce con 0 — sempre, qualunque errore ci sia nel codice. Chi
lancia `tsc --noEmit` per controllare i tipi ottiene un verde che non significa
nulla. Il controllo che compila davvero i sotto-progetti è `tsc -b`, lo stesso che
lancia `npm run build` e ora anche `npm run typecheck`:

```bash
cd frontend && npm run typecheck
```

### Percorso end-to-end

Attraversa lista, dispensa, ricettario, cottura e rientro in lista con un browser
vero, contro l'app costruita e servita da Nginx. Nello stesso stack girano anche i
controlli di `e2e/style.spec.ts`, che sono lì per un motivo preciso: Tailwind genera
il CSS al momento della costruzione e jsdom non lo calcola, quindi lo stile è l'unica
parte dell'app che i test di Vitest non possono vedere. Quelli non vogliono uno stack
pulito: i pochi che scrivono (una voce di dispensa, un prodotto) la tolgono prima di
finire. Gira su uno stack Compose a parte,
`spena-e2e`, per due motivi: la password serve conosciuta (`.env.e2e` contiene
l'hash della parola `test`, e non protegge niente; `.env.e2e` è l'ultimo `env_file`,
quindi vince anche su un `password.env` presente) e lo stack va distrutto con i
volumi alla fine, cosa che non si può fare sul progetto di sviluppo senza perdere la
dispensa vera.

```bash
E2E="docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml"
$E2E up -d --build --wait
$E2E exec -T backend python -m app.cli.seed --con-ricette
(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
$E2E down -v
```

Il `-p spena-e2e` e il `-f docker-compose.e2e.yml` vanno ripetuti in ogni comando:
`down -v` sul progetto di default cancellerebbe il volume della dispensa vera.

Il percorso scrive in lista e in dispensa, quindi **vuole uno stack appena creato**:
rieseguirlo senza `down -v` lo fa fallire dicendo che lo stack non è pulito.

`e2e/import-review.spec.ts` semina le decisioni dell'AI da rivedere dentro il container
del backend (`backend/tests/e2e_import_review.py`, con il modello finto della suite), quindi
lancia da sé `docker compose exec` sul progetto `spena-e2e`: se il progetto ha un altro
nome, lo si passa in `E2E_PROJECT`. L'aiutante che gira è quello montato nel container del
backend, cioè quello della copia del repository da cui lo stack è stato avviato, non
necessariamente quella da cui si lancia Playwright. Parte solo dove c'è `SPENA_E2E=1`, che
sta in `.env.e2e`; lo stesso file lascia vuota `OPENROUTER_API_KEY`, così una chiamata al
modello che sfuggisse a uno stub finisce in un 503 e nel ripiego a mano, non in una spesa.

## Lo stile, e dove abita il colore

Tutti i colori, il raggio delle schede e il tipo di carattere stanno in un blocco
`@theme` in `frontend/src/index.css`. Tailwind ne fa delle classi (`--color-brand`
diventa `bg-brand`, `text-brand`, `border-brand`), e nessun file di schermata nomina
un colore grezzo: cercare `emerald` o `neutral-400` in `src/` non trova niente, ed è
così che va tenuto. Cambiare il verde dell'app è un lavoro da una riga, e il tema
scuro sta nello stesso file: ridefinisce le stesse variabili sotto
`@media (prefers-color-scheme: dark)`, e segue il telefono senza un interruttore.

I valori non sono scelti a occhio. Ogni colore che porta testo bianco sopra di sé sta
sopra 4.5:1 di contrasto, e `ink-faint` è il più chiaro che regge 4.5:1 sul fondo
della pagina: schiarirli è esattamente ciò che rende la lista illeggibile al sole,
cioè in corsia.

I campi di testo si vestono una volta sola, nel livello base dello stesso file, e non
schermata per schermata: sono otto moduli in sei cartelle e a mano si scollano. Il
selettore esclude i tipi che *non* sono campi di testo invece di elencare quelli che
lo sono, e non è pignoleria: `input[type="text"]` non seleziona un `<input>` senza
attributo `type`, che è come è scritta metà dei campi di quest'app.

Le primitive condivise stanno in `frontend/src/components/ui/`. Prima di scrivere la
quarta variante di un bottone, guarda lì.

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
rete esterna che deve esistere già. Il file la chiama `web`, che è il nome usato
dal server dove Spena gira; il nome giusto è quello che il *tuo* Traefik dichiara
in `providers.docker.network`, e sbagliarlo non produce nessun errore nei log del
sito — il dominio risponde 404 e basta, perché Traefik non vede il container.

```bash
docker network ls | grep web          # esiste già? allora non creare niente
docker network create web             # solo se manca
```

In `.env` servono, oltre alle variabili dell'avvio locale, `SPENA_HOST` con il nome
di host pubblicato e le `POSTGRES_*` (qui non hanno default: il Compose di
produzione non ne inventa uno).

La password si imposta, sul server, con `./scripts/imposta-password.sh
docker-compose.prod.yml`, sempre con il file di produzione, come ogni altro comando
lì. Poi il deploy di sempre la fa valere.

```bash
docker compose -f docker-compose.prod.yml up -d --build --wait --wait-timeout 120
docker compose -f docker-compose.prod.yml exec backend python -m app.cli.seed --solo-ingredienti
```

Il seme carica la sola anagrafica e non tocca le ricette: da R4 è il default, e
`--solo-ingredienti` resta accettato come sinonimo. Le ricette di semina servono solo
a sviluppo ed e2e (`--con-ricette`); in produzione si tolgono con
`python -m app.cli.drop_seed_recipes`, e un seme rilanciato non le rimette.

Il `--wait-timeout` serve al caso in cui una migrazione futura fallisca. Qui il
backend ha `restart: unless-stopped`: il container muore sulla migrazione, Docker lo
rianima, non diventa mai `healthy` e `--wait` senza scadenza aspetta per sempre senza
dire niente. Con la scadenza il comando torna con un errore dopo due minuti (oggi
l'avvio ne impiega pochi secondi: la 0007 è l'ultima migrazione e il database è
vuoto), e la causa vera si legge in un posto solo:

```bash
docker compose -f docker-compose.prod.yml logs backend
```

L'errore di Alembic è lì, ripetuto a ogni riavvio. Lo schema non resta a metà:
`alembic/env.py` avvolge tutte le revisioni in una sola transazione e Postgres ha DDL
transazionale, quindi la migrazione fallita è come se non fosse mai partita.

Anche qui le migrazioni girano all'avvio del backend, quindi con una migrazione nuova
basta rilanciare il deploy. Un `git pull` e un
`docker compose -f docker-compose.prod.yml up -d --build --wait` bastano. **Il `-f`
non è opzionale**: senza, Compose usa `docker-compose.yml`, i due file condividono il
nome di progetto `spena`, e lo stack di produzione viene sostituito da quello di
sviluppo — che non ha le etichette di Traefik. Il dominio smette di rispondere e non
lo scrive nessun log. Il seme invece resta a mano, perché non è un'operazione da
ripetere a ogni riavvio.

Il progetto Compose, in mancanza di `-p`, si chiama `spena` anche qui, cioè come
quello di sviluppo: sulla stessa macchina i due stack si contenderebbero gli stessi
nomi di container e lo stesso volume `spena_pgdata`. Su un server dedicato non
succede; se devi provare il Compose di produzione dove sviluppi, dagli un nome suo
con `-p spena-prod`.

HTTPS è necessario e non opzionale, per due motivi che si sommano: senza di esso la
fotocamera non parte, e il cookie di sessione viaggia con `Secure` — il Compose di
produzione impone `COOKIE_SECURE=true` al servizio backend — quindi su `http` il
browser non lo rimanderebbe e ogni chiamata dopo l'accesso risponderebbe 401.

### Cambiare la password

```bash
./scripts/imposta-password.sh docker-compose.prod.yml
docker compose -f docker-compose.prod.yml up -d --wait --force-recreate backend
```

I dispositivi già entrati restano dentro: il cookie è firmato con `SESSION_SECRET` e
non con la password. Per buttarli fuori tutti si cambia anche quella.

## Variabili d'ambiente

| Variabile | Default | Scopo |
|---|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | vedi `.env.example` | connessione al database |
| `SESSION_SECRET` | nessuno, obbligatorio | firma del cookie di sessione; vuota, il backend non parte |
| `APP_PASSWORD_HASH` | nessuno, obbligatorio | hash argon2 della password di accesso, **in `password.env`, mai in `.env`**, scritto da `scripts/imposta-password.sh`; illeggibile (troncato), il backend non parte |
| `COOKIE_SECURE` | `false` | `true` in produzione: il cookie solo su HTTPS |
| `OPENROUTER_API_KEY` | vuoto | stesura ricette con l'AI e decisione dei termini incerti nell'import |
| `OPENROUTER_MODEL` | `google/gemma-4-26b-a4b-it` | il modello; cambiarlo è come passare a uno più grosso (es. `anthropic/claude-sonnet-5`) |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | endpoint dell'API, sovrascrivibile nei test |
| `OPENROUTER_APP_TITLE` | `Spena Import Ricette` | header `X-Title`: per OpenRouter è solo il **nome visualizzato**, e da solo non attribuisce niente |
| `OPENROUTER_APP_URL` | vuoto | header `HTTP-Referer`, **la chiave con cui OpenRouter riconosce l'app**. Vuota, l'header si omette e i log mostrano «Unknown» qualunque titolo si mandi. Mettici il dominio dell'installazione |
| `OPENROUTER_PROVIDER_ONLY` | vuoto | vuoto: instradamento per prezzo scelto da OpenRouter. Valorizzata (es. `darkbloom`): pinni il provider a mano, e perdi la caduta automatica sul successivo |
| `LLM_TIMEOUT_SECONDS` | `60` | oltre il quale una chiamata al modello si considera persa |
| `LLM_MAX_CONCURRENCY` | `8` | quante domande in volo nel riconoscimento parallelo dei termini |
| `CLAUDE_CODE_OAUTH_TOKEN` | vuoto | la chat dei Pasti con Claude: il token del piano di Mattia, da `claude setup-token` (dura un anno), **solo nel `.env` del server**. Vuoto, la chat dice che Claude non è collegato e il resto dei Pasti funziona a mano |
| `CLAUDE_MODEL` | `claude-opus-5-5` | il modello dei Pasti, sul piano di Claude (non su OpenRouter) |
| `CLAUDE_REPLY_TIMEOUT_SECONDS` | `240` | il tempo massimo di una risposta della chat; oltre, il messaggio resta con l'avviso e «Riprova» |
| `EMBEDDING_BACKEND` | `local` | `local`, `http` oppure `fake`; `local` richiede `INSTALL_EMBEDDINGS=1` |
| `INSTALL_EMBEDDINGS` | `0` | argomento di build: a `1` l'immagine installa sentence-transformers |
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-small` | modello locale; cambiandolo va rimisurata `SEMANTIC_MAX_DISTANCE` (vedi sotto) |
| `EMBEDDING_ENDPOINT` | vuoto | solo con `EMBEDDING_BACKEND=http` |
| `OFF_BASE_URL` | api ufficiale di Open Food Facts | sovrascrivibile nei test |
| `OFF_TIMEOUT_SECONDS` | `3` | oltre il quale si degrada all'inserimento manuale |
| `SPENA_HOST` | nessuno | solo in produzione: host pubblicato da Traefik |

**Quanto costa ogni pezzo dell'app** non lo dicono i log di OpenRouter. Per loro
un'app è un indirizzo — `HTTP-Referer` è l'identificatore, `X-Title` ne cambia solo il
nome visualizzato — quindi mandare un titolo diverso per sezione non produrrebbe voci
di spesa separate, ma una sola app con il nome che sfarfalla. La divisione la tiene la
tabella `llm_calls`: una riga per chiamata, con la sezione che l'ha fatta e il costo
che OpenRouter dichiara in `usage.cost` nella risposta stessa. I fallimenti si
registrano come tali, perché un modello giù è spesa sprecata che si vuole vedere.

Nessuna di queste, mancando, porta a un vicolo cieco nell'interfaccia: senza
`OPENROUTER_API_KEY` la ricetta si scrive a mano e i termini dell'import si decidono
dalla coda, senza modello di embedding la ricerca resta quella testuale, con Open
Food Facts irraggiungibile il prodotto si crea a mano. È una regola di casa, non un
caso fortunato.

**Claude per i Pasti** si controlla dentro l'immagine che gira:
`docker compose -f docker-compose.prod.yml exec backend python -m app.cli.check_claude [--prova]`.
Senza argomenti non usa la rete: stampa la versione di `claude-agent-sdk`, la versione
del binario di Claude Code incluso e `token: presente` o `token: assente` (mai il
valore). Con `--prova` fa una sola chiamata minima e deve dire «prova: ok». La chat
spegne `ANTHROPIC_API_KEY` e `ANTHROPIC_AUTH_TOKEN` nell'ambiente del CLI, così usa
sempre il token del piano anche se il `.env` del server ha ancora la chiave;
`check_claude` avvisa se la chiave c'è (senza stamparla), e la prova vera resta
`--prova` con «prova: ok». Che il valore vuoto basti a spegnere la chiave è stato
verificato leggendo il codice dell'SDK e del CLI, non con una chiamata vera.

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
il seme è idempotente e non le riscrive. Per dargliene uno esegui

```bash
docker compose exec backend python -m app.cli.reindex
```

che calcola i vettori mancanti sul posto, senza toccare le ricette che ce l'hanno
già: non serve cancellare niente. Finché non lo esegui il ricettario continua a
mostrare la riga «Ricerca solo testuale»: `/recipes/search-mode` risponde
`semantic: true` solo se esiste almeno una ricetta con il vettore, quindi l'avviso
dice quel che cercare fa davvero e non quel che il fornitore saprebbe fare.

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
