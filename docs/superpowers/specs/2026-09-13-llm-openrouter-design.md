# Spena — Riconoscimento degli ingredienti con un LLM su OpenRouter (fase 2b)

**Data:** 2026-09-13
**Stato:** da approvare
**Spec madre:** `docs/superpowers/specs/2026-09-12-import-ricette-design.md`, §8.2 «Le proposte di Claude»
**Modello:** `google/gemma-4-26b-a4b-it` via OpenRouter, deciso dall'utente
**Emenda:** questa spec rovescia §8.2 della spec madre. Vedi §2.

## 1. Obiettivo

L'import porta le pagine dentro, ma una pagina diventa ricetta solo quando tutti i
suoi termini hanno una decisione. Oggi quelle decisioni le prende una persona, un
tocco per termine, e il modello serve solo a proporre — con una rotta che dal giorno
in cui è stata scritta risponde `503`, perché `ANTHROPIC_API_KEY` non è mai stata
configurata in nessun ambiente. Il primo lotto reale da 5 pagine ha prodotto «0
importate, 5 in attesa, 15 ingredienti da abbinare»: funzionante come progettato, e
fermo.

Questo lavoro fa due cose. Sostituisce Anthropic con OpenRouter, così che un modello
esista davvero. E cambia chi decide: **l'AI decide, la coda diventa la revisione.**

Criteri di riuscita, in ordine:

1. `python -m app.cli.import_gz --limit 50` porta le ricette nel ricettario senza
   nessun intervento, e quel che non ha saputo giudicare lo lascia in coda invece di
   indovinarlo.
2. Ogni decisione presa dall'AI è visibile e annullabile. Un errore non è un vicolo
   cieco.
3. L'anagrafica non si gonfia: `Rigatoni` resta un alias di `pasta`, e due nomi
   vicini creati nella stessa passata non diventano due ingredienti.
4. Senza chiave configurata tutto continua a funzionare a mano, come oggi.

## 2. La decisione che si rovescia

La spec madre, §8.2, dice: «Claude propone e non decide». Il codice la difende in tre
punti con commenti espliciti, e il motivo è buono — un abbinamento sbagliato in
silenzio avvelena la disponibilità di ogni ricetta che usa quell'ingrediente, e
l'alias che ne esce vale per sempre, anche fuori dall'import.

**Da qui in avanti l'AI decide.** La decisione è dell'utente, presa in chat il
2026-09-13, e va scritta con la sua contropartita, perché senza contropartita è solo
un rischio:

- ogni decisione presa dall'AI porta `decided_by = "ai"`, quindi è distinguibile da
  una umana e da una automatica;
- la coda `/ricette/importa` smette di essere un modulo da compilare e diventa
  **l'elenco di ciò che l'AI ha fatto**, con un verbo per disfarlo;
- una decisione non verificabile — un ingrediente che non esiste, una categoria
  inventata — non si applica: il termine resta in coda. Il modello può sbagliare, non
  può scrivere spazzatura.

Il principio che **non** cambia: la verifica di ogni risposta contro l'anagrafica
vera, che è già scritta in `propose_decisions` e che questo lavoro riusa intatta.

## 3. Il fornitore

### 3.1 Un client solo, e Anthropic esce

Nuovo file `backend/app/services/llm.py`, una funzione pubblica:

```python
async def complete_json(
    system: str, user: str, schema: dict, max_tokens: int, client: object | None = None
) -> dict
```

`POST {OPENROUTER_BASE_URL}/chat/completions` con `httpx`, che è già dipendenza di
base. Il pacchetto `anthropic`, l'extra `ai` e `ANTHROPIC_API_KEY` sono rimossi:
l'immagine del backend si alleggerisce di una dipendenza invece di guadagnarne una.

Non si costruisce un'interfaccia a due fornitori scelta da una variabile, sullo
stile di `EMBEDDING_BACKEND`. Il secondo percorso non girerebbe mai in produzione, e
sarebbe esattamente il difetto scritto in cima a CLAUDE.md: «un test che costruisce
il proprio oggetto non sta testando quello che la produzione usa». Il modello resta
configurabile (`OPENROUTER_MODEL`), e poiché OpenRouter fa da proxy anche a Claude,
tornare a un modello grosso è una riga di `.env` — non un secondo client.

`LlmUnavailable` sostituisce `AiUnavailable` (stessa semantica, nome onesto). I due
chiamanti la traducono già in «decidi a mano», e quel comportamento non cambia.

### 3.2 Scelta del provider

Misurato il 2026-09-13 su `GET /api/v1/models/google/gemma-4-26b-a4b-it/endpoints`,
undici provider, dollari per milione di token:

| Provider | input | output | cache read | structured outputs |
|---|---|---|---|---|
| **Darkbloom** | **0,042** | **0,22** | — | sì |
| DekaLLM | 0,060 | 0,33 | — | **no** |
| DeepInfra | 0,070 | 0,34 | — | sì |
| NextBit | 0,090 | 0,30 | 0,050 | sì |
| Cloudflare | 0,100 | 0,30 | — | **no** |
| Makora | 0,100 | 0,34 | 0,034 | **no** |
| Venice | 0,130 | 0,40 | 0,050 | sì |
| Parasail | 0,130 | 0,40 | 0,050 | sì |
| Novita | 0,130 | 0,40 | — | **no** |
| SiliconFlow | 0,140 | 0,40 | 0,050 | sì |
| Google | 0,150 | 0,60 | — | sì |

Nessuno di loro fa cache implicita.

Instradamento: `provider: {"sort": "price", "require_parameters": true}`.

`require_parameters` porta il peso: quattro provider su undici non supportano
`structured_outputs`, e **DekaLLM, che non li supporta, è il secondo più economico**.
Senza quel flag l'ordinamento per prezzo instrada verso un endpoint che non può
onorare lo schema.

Non si calcola il provider a mano, e la ragione è misurata, non stilistica:

- per default OpenRouter **non** prende il più economico — filtra chi ha avuto
  disservizi negli ultimi 30 secondi e poi sceglie pesando sull'inverso del quadrato
  del prezzo. `sort: "price"` spegne quel bilanciamento e ordina in modo stretto;
- con `allow_fallbacks` al suo default (`true`), un errore o un rate limit sul primo
  scende al secondo più economico da sé. È ciò che si perde pinnando
  `provider.only` sul vincitore di un calcolo proprio, su endpoint che stanno fra il
  99,2% e il 99,99% di uptime;
- **la cache non conviene su questo modello.** Il cache read più economico fra i
  provider che reggono lo structured output è 0,050 — più caro dei 0,042 che
  Darkbloom chiede per un token di input a prezzo pieno. L'unico cache read che
  batte Darkbloom (0,034, Makora) è su un provider senza structured output;
- la documentazione di OpenRouter **non dichiara** come `sort: "price"` pesi input
  contro output. Qui la lacuna non morde: fra i sette provider con structured
  output, Darkbloom è il più economico su entrambe le voci, quindi non c'è nessun
  compromesso da risolvere e qualunque formula dà lo stesso vincitore.

Quella lacuna è però il motivo di §11: il giorno in cui qualcuno apre a 0,03
sull'input e 0,50 sull'output, il compromesso esiste e va guardato.

### 3.3 Structured outputs

Ogni chiamata porta `response_format` con `type: "json_schema"` e `strict: true`.
Con lo schema stretto non serve nessuno scrostatore di blocchi ` ``` `: la risposta
è JSON o è un errore.

Vincolo dello strict mode da tenere a mente scrivendo gli schemi: **ogni proprietà
deve stare in `required`**, e `additionalProperties` deve essere `false`. I campi
che valgono solo per una delle azioni si dichiarano quindi nullable, non opzionali.

### 3.4 Attribuzione

Ogni richiesta porta:

```
Authorization: Bearer ${OPENROUTER_API_KEY}
HTTP-Referer: ${OPENROUTER_APP_URL}
X-Title: ${OPENROUTER_APP_TITLE}     # "Spena Import Ricette"
```

Sono opzionali per OpenRouter e obbligatori per noi: identificano l'app nelle
classifiche e nei consumi, ed è come si distingue questo traffico da qualunque altro
sulla stessa chiave.

## 4. Il riconoscimento: quattro passi

L'ordine di esecuzione, che non coincide con l'ordine in cui le sezioni qui sotto si
leggono — il fan-in si spiega prima perché è ciò che motiva il collasso:

1. **passo zero** (§4.1): il filtro deterministico, nessuna chiamata;
2. **fan-out** (§4.2): N chiamate in parallelo, nessuna scrittura;
3. **collasso** (§4.4): una chiamata sui soli `create`, nessuna scrittura;
4. **fan-in** (§4.3): le scritture, in sequenza.

### 4.1 Passo zero — il filtro deterministico, che esiste già

`sync_terms` passa ogni termine nuovo da `match_name`, che cerca la coincidenza
esatta sul nome canonico e poi sugli alias. Quando la trova decide da sé e segna
`decided_by = "auto"`: **nessuna chiamata al modello, costo zero.** Solo i termini
che restano `pending` arrivano all'AI.

Questo passo non si tocca. È anche ciò che rende il sistema più economico a ogni
passata: ogni alias scritto oggi è una chiamata che domani non si fa.

### 4.2 Fan-out — una chiamata per termine

`decide_terms(session, terms)` in `backend/app/services/recipe_import/terms.py`
manda **una chiamata per termine**, in parallelo con `asyncio.gather` sotto un
semaforo da `LLM_MAX_CONCURRENCY` (8).

Non è una scelta di costo: le chiamate parallele costano circa otto volte il lotto
unico (§12). È una scelta di accuratezza. `gemma-4-26b-a4b-it` ha 3,8 miliardi di
parametri attivi per token; chiedergli un array JSON di 40 elementi, ognuno dei
quali deve riecheggiare *identica* una delle 40 stringhe ricevute, è precisamente
dove un MoE piccolo si sfalda — e il degrado sarebbe invisibile, perché il codice
scarta in silenzio ogni elemento che non riconosce. Una domanda per termine è una
domanda a cui sa rispondere.

In più l'isolamento del guasto diventa gratuito: una chiamata che fallisce lascia
*quel* termine in coda, non il lotto.

Il prompt di sistema resta quello di `PROPOSAL_SYSTEM_PROMPT`, riscritto al
singolare. Il messaggio utente porta il termine, l'anagrafica intera (169
ingredienti, misurati 7,2 KB di JSON compatto) e le dodici categorie. Lo schema:

```json
{
  "type": "json_schema",
  "json_schema": {
    "name": "decisione_termine",
    "strict": true,
    "schema": {
      "type": "object",
      "properties": {
        "action":       {"type": "string", "enum": ["map", "create", "ignore"]},
        "ingredient":   {"type": ["string", "null"]},
        "name":         {"type": ["string", "null"]},
        "display_name": {"type": ["string", "null"]},
        "category":     {"type": ["string", "null"]}
      },
      "required": ["action", "ingredient", "name", "display_name", "category"],
      "additionalProperties": false
    }
  }
}
```

Le tre azioni e il loro significato non cambiano dalla spec madre §8.2: `map` verso
un nome canonico esistente, `create` con nome/nome visibile/categoria, `ignore` per
ciò che non si tiene in dispensa (l'acqua, il ghiaccio, l'acqua di cottura).
`ignore` resta: senza, quelle voci finiscono in anagrafica e da lì
nell'autocomplete della lista della spesa.

La verifica di ogni risposta è quella già scritta: `map` verso un ingrediente
inesistente si scarta; `category` fuori dall'enum si scarta; `create` di un nome che
l'anagrafica ha già si **converte** in `map`. Un termine la cui risposta non passa la
verifica resta `pending`.

### 4.3 Fan-in — le scritture in una passata sola

Le domande partono insieme, **le scritture si applicano dopo, in sequenza e in
ordine**, rifacendo `match_name` prima di ogni `create`.

Serve perché il parallelo apre un buco che il lotto unico non aveva: «Speck» e
«Speck a cubetti» tornano entrambi `create: speck`, e scritti in parallelo diventano
un doppione o una violazione del vincolo. Applicati in sequenza, il secondo trova
quello che il primo ha appena creato e diventa un `map` — usando la stessa
conversione `create`→`map` già presente nel codice.

Ogni decisione applicata scrive: `decision`, `ingredient_id`, `role_override`,
`decided_by = "ai"`, `decided_at`, e l'alias permanente.

### 4.4 La passata di collasso

Il fan-in prende i duplicati **identici**. Non vede i duplicati **vicini**:
`salmone` e `salmone selvaggio` sono due `create` diversi, ed è inutile avere
entrambi.

Prima che il fan-in scriva: si prendono i soli `create` sopravvissuti alla verifica,
per ognuno si cercano i vicini nell'anagrafica con `search_ingredients` (la ricerca
per trigrammi che il progetto usa già come primitiva di somiglianza), e si fa **una**
chiamata:

```json
{
  "type": "json_schema",
  "json_schema": {
    "name": "collasso_ingredienti",
    "strict": true,
    "schema": {
      "type": "object",
      "properties": {
        "groups": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "canonical": {"type": "string"},
              "merge":     {"type": "array", "items": {"type": "string"}}
            },
            "required": ["canonical", "merge"],
            "additionalProperties": false
          }
        }
      },
      "required": ["groups"],
      "additionalProperties": false
    }
  }
}
```

Copre due rischi in un colpo: nuovo contro nuovo (che nessuna delle chiamate
parallele poteva vedere) e nuovo contro esistente (che la chiamata singola avrebbe
dovuto prendere e a volte non prende). Input minuscolo, nessuna anagrafica da
rispedire, **zero chiamate quando non c'è nessun `create`**.

Il nome scartato **diventa un alias del canonico**. È ciò che rende la passata un
investimento e non una pulizia: la prossima volta che la fonte scrive «Salmone
selvaggio», il passo zero lo riconosce senza chiamare nessuno.

Guardrail: `canonical` deve essere uno dei nomi mandati o uno che esiste in
anagrafica, e ogni voce di `merge` deve essere uno dei nomi mandati. Altrimenti il
gruppo si scarta e i nomi restano separati. La direzione del fallimento è quella
giusta: **scartare un collasso lascia un ingrediente in più, applicarne uno
sbagliato lascia una distinzione in meno** — il primo si vede e si corregge, il
secondo è invisibile.

### 4.5 Dove gira

`python -m app.cli.import_gz` diventa: scarica → `sync_terms` → `decide_terms` →
`materialize_ready`. Un comando, e il ricettario si riempie.

`POST /api/v1/imports/terms/decide` **sostituisce** `POST /terms/proposals`. Stessa
funzione, verbo onesto: applica invece di proporre. Serve come «riprova con l'AI»
sui termini rimasti in coda dopo un guasto di rete. Corpo opzionale `term_ids`; senza,
tutti i `pending`.

Conseguenza nel frontend: la coda perde la query automatica delle proposte e tutto il
suo apparato — la cache `proposalsByTerm`, il `retry: false`, il `proposalsSettled`.
Non è pulizia opportunistica: quel codice esisteva per mostrare proposte non
applicate, e non ci sono più proposte non applicate.

## 5. La revisione

### 5.1 Due elenchi

`/ricette/importa` si divide.

**Da decidere** — i `pending`: quelli che l'AI non ha saputo giudicare, quelli la cui
risposta non ha passato la verifica, e tutti quanti se la chiave manca. La scheda di
oggi (`TermCard`), intatta. In testa, il bottone «Riprova con l'AI» di §4.5.

**Deciso dall'AI** — i `decided_by = "ai"`, i più recenti in cima, una riga l'uno:

```
Rigatoni           → pasta                Annulla
Speck              → creato, carne        Annulla
Acqua              → ignorato             Annulla
Salmone selvaggio  → salmone              Annulla
```

Un termine accorpato non ha bisogno di niente di speciale: **è un `map`, e si mostra
come un `map`**, perché è quello che è.

`GET /api/v1/imports/terms` guadagna `?decided_by=ai`. `TermOut` guadagna i campi che
descrivono la decisione presa (azione, nome dell'ingrediente, se creato).

### 5.2 L'annullamento

`POST /api/v1/imports/terms/{term_id}/undo`. Un verbo, non un editor: rimette il
mondo come era prima che l'AI toccasse, e poi si decide a mano con la scheda che
esiste già ed è già testata. Niente secondo percorso di decisione da scrivere e
mantenere.

Cinque effetti, in questo ordine:

1. il termine torna `pending`, con `ingredient_id`, `role_override`, `decided_by` e
   `decided_at` a `NULL`;
2. l'alias che quella decisione ha scritto viene rimosso — riconoscibile perché
   `ingredient_aliases.source = "import"` e `alias = display_name` in minuscolo;
3. se la decisione ha **creato** un ingrediente e nessun altro lo usa (nessun altro
   termine, nessuna `recipe_ingredients`, nessun articolo in dispensa, nessun alias
   oltre al suo), l'ingrediente si cancella; altrimenti resta, e la risposta lo dice;
4. le pagine che contengono quel termine e sono `imported` tornano `pending`, con la
   loro ricetta cancellata e `recipe_id` a `NULL`;
5. la risposta dice quante ricette sono tornate in coda.

Il controllo del punto 3 è anche ciò che rende l'annullamento di un collasso
gratuito: annullare «Salmone», se «salmone selvaggio» punta allo stesso ingrediente,
trova un altro termine che lo usa e non lo cancella.

Le ricette si rifanno da `payload`, che è ancora nel database esattamente per questo
(spec madre §6.1). Non serve nessuna chirurgia su `recipe_ingredients`.

Non c'è niente da preservare nelle ricette cancellate: **l'app non ha rotte per
modificare o cancellare una ricetta** (`recipes.py` ha `GET /search`,
`/search-mode`, `/categories`, `/{id}`, `POST ""`, `/ai-draft`, `/{id}/cook` — nessun
`PUT`, nessun `DELETE`). Il giorno in cui esisterà una modifica a mano, questo punto
va ripensato.

Il punto 4 distingue una ricetta che rifacciamo noi da una che l'utente ha
cancellato: la cancellazione dell'utente lascia `state = 'imported'` con `recipe_id`
nullo, questo passo scrive `state = 'pending'`. La regola del modello — «è lo stato,
non la presenza della chiave, a dire già importata una volta» — resta valida.

### 5.3 Lo storico di cottura

`cooking_events.recipe_id` è `ON DELETE SET NULL` e l'evento porta il suo `snapshot`
JSONB: cancellare la ricetta non distrugge lo storico, ma **gli stacca il
collegamento per sempre**. Quello storico esiste solo perché la fase 3 e la fase 4 ci
costruiscono sopra.

Quindi: se una delle ricette da rifare ha eventi di cottura, `undo` risponde `409`
con il numero, e la schermata dice «due di queste le hai già cucinate: rifacendole lo
storico resta ma perde il collegamento», con una conferma che rimanda la stessa
chiamata con `force: true`.

Rifiutare in silenzio sarebbe un vicolo cieco. Procedere in silenzio sarebbe una
perdita invisibile. È l'unico punto di tutta la feature in cui si chiede qualcosa.

## 6. La bozza AI

Lo schema del prompt di `draft_recipe` guadagna `category` per ogni ingrediente,
vincolata alle dodici categorie.

Quando `match_name` non aggancia niente, la riga della bozza porta la categoria
proposta e la scheda dice «lo creo io: speck, carne», con la categoria modificabile e
il selettore ancora disponibile se si preferisce collegarlo a qualcosa.

**L'ingrediente si crea al salvataggio, non alla stesura.** Una bozza scartata non
deve lasciare ingredienti dietro: l'anagrafica cresce solo con ciò che una ricetta
salvata usa davvero. `POST /api/v1/recipes` accetta, per una riga, `{name, category}`
al posto di `ingredient_id`, e crea l'ingrediente nella stessa transazione della
ricetta — che rende l'operazione atomica: nessun ingrediente orfano se il salvataggio
fallisce.

Nessuna passata di collasso qui: una bozza ha otto ingredienti e forse uno ignoto.
Quel che si riusa è `search_ingredients`: se si sta creando «salmone selvaggio»
mentre «salmone» esiste, compare come suggerimento grigio — il meccanismo del
`certain: false` che c'è già.

## 7. Modello dati: nessuna migrazione

`import_terms.decided_by` è già `String(20)` nullable, e `"ai"` ci sta accanto a
`"human"` e `"auto"`. `ingredient_aliases` ha già `source`, e `"import"` è già il
valore che l'import scrive. `recipe_imports.payload` c'è già.

**Questa feature non aggiunge nessuna colonna e nessun indice.** Se durante
l'implementazione nasce il bisogno di una migrazione, è il segnale che qualcosa si è
allontanato da questa spec: fermarsi e rileggere.

## 8. Config e ambiente

`backend/app/core/config.py`, campi nuovi su `Settings`:

| Variabile | Default | A cosa serve |
|---|---|---|
| `OPENROUTER_API_KEY` | `None` | senza, ogni chiamata degrada (§9) |
| `OPENROUTER_MODEL` | `google/gemma-4-26b-a4b-it` | cambiarlo è come si passa a un modello più grosso |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | |
| `OPENROUTER_APP_TITLE` | `Spena Import Ricette` | header `X-Title` |
| `OPENROUTER_APP_URL` | `""` | header `HTTP-Referer`; vuota, l'header si omette. In `.env` di produzione vale `https://spena.mattiagirellini.com` |
| `OPENROUTER_PROVIDER_ONLY` | `""` | vuoto: instradamento per prezzo. Valorizzato: `provider.only`, scavalco manuale |
| `LLM_TIMEOUT_SECONDS` | `60` | un MoE su un lotto è lento; i 3 secondi di Open Food Facts qui non bastano |
| `LLM_MAX_CONCURRENCY` | `8` | chiamate in volo nel fan-out |

`ANTHROPIC_API_KEY` esce da `Settings` e da `.env.example`.

`backend/pyproject.toml`: l'extra `ai` sparisce. `backend/Dockerfile`: il ramo che lo
installa sparisce. I due file Compose **non cambiano**: `env_file` in forma lunga con
`format: raw` porta già ogni variabile, e quella forma va lasciata com'è (il motivo è
in CLAUDE.md e in `tests/test_compose.py`).

Deploy: `git pull` e `docker compose -f docker-compose.prod.yml up -d --build`, con
il `-f` — e la ragione per cui va scritto esplicitamente sta in §15.

## 9. Senza chiave, tutto continua a funzionare

`LlmUnavailable` non è un guasto da propagare:

- `import_gz` la cattura, stampa la riga di oggi («N ingredienti da abbinare: aprili
  dal ricettario») e **non fallisce**. `materialize_ready` gira comunque;
- `POST /imports/terms/decide` risponde `503` con «decidi a mano, la coda funziona»,
  come fa oggi `/terms/proposals`;
- `POST /recipes/ai-draft` risponde `503` come oggi;
- la coda manuale, la scheda, l'annullamento e la materializzazione non passano dal
  modello e funzionano identici.

È la stessa regola di `EmbeddingProvider` e di `OpenFoodFactsClient`: mai un vicolo
cieco.

## 10. Test

Su Postgres vero via Compose, nessuna chiamata di rete, come tutta la suite.

**`llm.py`** — contro `respx`, già fra le dipendenze di `dev`: risposta valida;
corpo senza `choices`; `429`; timeout; `422` di schema rifiutato. E asserzioni sulla
**richiesta costruita**: `X-Title`, `HTTP-Referer`, `response_format.json_schema.strict`
a `true`, `provider.sort` a `"price"`, `provider.require_parameters` a `true`, e
`provider.only` presente solo quando `OPENROUTER_PROVIDER_ONLY` è valorizzata.

**`decide_terms`** — le tre azioni applicate; il termine la cui risposta non passa la
verifica resta `pending`; due `create` dello stesso nome producono un ingrediente e
due termini mappati; l'alias scritto; `decided_by = "ai"`; una chiamata che solleva
lascia in coda solo il suo termine.

**Il collasso** — `{"canonical": "salmone", "merge": ["salmone selvaggio"]}` produce
un ingrediente, un alias e due termini mappati; un canonico inventato fa scartare il
gruppo e restare due ingredienti; nessun `create` nel lotto significa zero chiamate.

**`undo`** — un test per ciascuno dei cinque effetti; l'ingrediente che resta perché
un altro termine lo usa; il `409` quando c'è uno storico di cottura, e il `force` che
procede.

**`import_gz`** — senza chiave esce con i termini in coda e codice di uscita zero.

**Immagine** — `tests/test_image_dependencies.py` va riscritto: l'extra `ai` e
`anthropic` non devono più comparire in `pyproject` né nel Dockerfile, e `httpx` deve
essere fra le dipendenze di base. Il test che eseguiva l'import vero di `anthropic`
viene sostituito da uno che **costruisce la richiesta vera** — è il punto di CLAUDE.md:
un percorso che nessun test attraversa è un percorso rotto che nessuno vede.

**`llm_prices`** — contro un `/endpoints` registrato: l'ordinamento è giusto, e i
provider senza `structured_outputs` sono esclusi.

**Frontend** — i due elenchi; la riga di ciò che l'AI ha deciso; l'annullamento e la
conferma dello storico; la bozza che mostra «lo creo io» con categoria modificabile.
Il type check è `npm run typecheck` e `npm run build`; **`tsc --noEmit` su questo
progetto esce sempre 0 e non prova niente** (CLAUDE.md).

## 11. Il CLI dei prezzi

`python -m app.cli.llm_prices` prende `/api/v1/models/{OPENROUTER_MODEL}/endpoints`,
stampa la tabella di §3.2 con i prezzi del momento, e calcola il costo di un lotto
vero sotto le due strategie (lotto unico e fan-out), segnando quali provider
`require_parameters` escluderebbe.

Non sta nel percorso caldo: è lo strumento con cui accorgersi del giorno in cui il
compromesso input/output di §3.2 comparirà davvero, e allora `OPENROUTER_PROVIDER_ONLY`
è lì per pinnare a mano.

## 12. Costi

Misurato: 169 ingredienti in anagrafica, 7,2 KB di JSON compatto, circa 2.400 token;
con il prompt di sistema, un prefisso di ~3.100 token per chiamata. Il termine sono
8 token. **Stimato**: ~35 token di output per termine.

Per i 15 termini in coda il 2026-09-13:

| strategia | costo |
|---|---|
| lotto unico, Darkbloom | $0,00026 |
| 15 chiamate parallele, Darkbloom | $0,0021 |
| 15 chiamate parallele, NextBit con cache read | $0,0027 |

Su tutto il catalogo GialloZafferano (~2.500 termini distinti stimati): 3 centesimi
con il lotto unico, 35 con il fan-out. Il fan-out costa circa otto volte, e otto
volte quasi niente è quasi niente: si sceglie per accuratezza (§4.2), non per prezzo.

## 13. Documenti da aggiornare

- **`CLAUDE.md`**: «Claude (`claude-sonnet-5`) è usato solo per abbozzare ricette e
  per proporre abbinamenti» diventa Gemma via OpenRouter; e la riga sull'import va
  estesa con «l'AI decide, la coda è la revisione». La frase «non produce mai valori
  nutrizionali» resta vera e resta.
- **Spec madre §8.2**: annotare che questa spec la rovescia, con la data.
- **`README.md`**: la sezione «Portare ricette nel ricettario» perde il passaggio
  manuale obbligatorio e guadagna la revisione; `.env.example` cambia.

## 14. Fuori scope, di proposito

- Un secondo fornitore dietro un'interfaccia (§3.1).
- Prompt caching (§3.2: misurato non conveniente su questo modello).
- Un editor delle decisioni: si annulla e si ridecide (§5.2).
- La passata di collasso sulla bozza AI (§6).
- Unione di due ingredienti già in anagrafica dal registro: è un lavoro suo, e
  questa feature non lo richiede perché `undo` copre il caso che lo genererebbe.
- Valori nutrizionali dal modello: vietato dalla spec madre e da CLAUDE.md, resta
  vietato.

## 15. Rischi noti

1. **Un modello da 3,8B attivi sbaglia più di Sonnet, e ora le sue decisioni si
   applicano.** Mitigazioni: la verifica contro l'anagrafica vera, il fan-out di
   §4.2, `decided_by = "ai"` e l'annullamento di §5.2. Resta il fatto che un
   abbinamento sbagliato che nessuno rilegge sopravvive.
2. **Un collasso sbagliato è invisibile.** «cipolla» e «cipollotto» sono nomi
   vicinissimi e ingredienti diversi. Il guardrail di §4.4 non lo previene: solo la
   revisione lo prende.
3. **La qualità del JSON dipende dal provider instradato.** `sort: "price"` cambia
   endpoint da sé, e due provider quantizzano lo stesso modello in modo diverso
   (`bf16`, `fp8`, `unknown`). Se la percentuale di risposte scartate diventa
   fastidiosa, `OPENROUTER_PROVIDER_ONLY` è la leva.
4. **Il deploy va fatto con `-f docker-compose.prod.yml`.** Un `docker compose up`
   senza `-f` sostituisce la produzione con lo stack di sviluppo: i due file
   condividono il nome di progetto `spena`, e quello di sviluppo non ha le etichette
   di Traefik. Il sintomo è un dominio che smette di rispondere senza un errore da
   nessuna parte — accaduto il 2026-09-13, diagnosi di mezz'ora.
5. **Il costo è per chiamata, non per lotto.** Un `--limit 500` con 300 termini nuovi
   fa 300 chiamate. Sono 4 centesimi, ma la forma della spesa è cambiata e vale
   saperlo.
