# Spena — Design v1

Data: 2026-09-11
Stato: approvato in brainstorming, da tradurre in piano di implementazione

> **Nota d'emendamento, 2026-09-13.** Il fornitore dell'AI generativa non è più
> l'API di Anthropic: è OpenRouter, con `google/gemma-4-26b-a4b-it` come modello di
> default e `OPENROUTER_API_KEY` al posto di `ANTHROPIC_API_KEY`. Vedi
> `docs/superpowers/specs/2026-09-13-llm-openrouter-design.md`, §3. Il testo
> originale resta sotto com'era, a memoria di cosa si è progettato l'11 settembre; i
> passaggi superati sono segnalati dove compaiono. Quel che sopravvive intatto: i
> due punti in cui l'AI entra (stesura di una ricetta, riconoscimento degli
> ingredienti) e il fatto che non produce mai valori nutrizionali.

## 1. Obiettivo

Spena tiene insieme quattro cose che di solito vivono in app separate: la lista
della spesa, ciò che hai davvero in casa, ciò che puoi cucinarci e ciò che
mangi. La v1 chiude il primo ciclo completo:

> scrivi la lista → torni dalla spesa e i prodotti entrano in dispensa →
> cucini una ricetta → ciò che è finito torna in lista

Il tracking nutrizionale e il motore di suggerimenti si innestano su questo
ciclo nelle fasi successive e non fanno parte della v1.

Uso personale, un solo utente, deploy privato.

## 2. Decisione fondante: niente quantità in dispensa

> **Nota d'emendamento, 2026-09-20.** Quel che segue vale per la dispensa; da
> questa data non vale più per le ricette. `recipe_ingredients` porta
> `quantity_value` e `quantity_unit_id` accanto a `quantity_text`, entrambi
> annullabili e riempiti al meglio possibile dal parser di
> `backend/app/domain/quantities.py`: `quantity_text` resta la verità mostrata a
> 1× e non viene mai riscritta, la coppia strutturata è quel che il riporziona
> legge, e una riga che il parser non è riuscito a riempire — `q.b.` in testa —
> non si scala, dichiarandolo invece di fingere un numero. Vedi
> `docs/superpowers/specs/2026-09-20-quantita-ricette-design.md`. **La dispensa
> resta quella descritta sotto, intera**: niente quantità, niente unità, niente
> scadenze — è lì che questa decisione ha comprato quel che doveva comprare, e il
> costo restava lo stesso identico: i valori nutrizionali non si deducono dalle
> scorte.

La dispensa non conosce quantità, unità di misura o scadenze. Un ingrediente
sta in uno di tre stati:

| Stato | Significato |
|---|---|
| `available` | disponibile, utilizzabile per qualsiasi ruolo |
| `low` | quasi finito, utilizzabile solo in piccole dosi |
| `finished` | finito, non utilizzabile |

Questa scelta elimina conversioni di unità, decadimento delle scorte e la
manutenzione quotidiana che fa abbandonare le app di questo tipo. Il costo è
che i valori nutrizionali non possono essere dedotti dalle scorte: in fase 3
arriveranno dalle porzioni dichiarate nel diario dei pasti, su un binario
separato.

Le transizioni di stato avvengono in un solo punto: quando cucini.

## 3. Decisione fondante: ingrediente generico e prodotto specifico

Quattro sottosistemi parlano di ingredienti e devono parlare la stessa lingua.
La riconciliazione avviene su due livelli distinti.

**Ingrediente generico** — il concetto canonico, `yogurt greco`. È ciò che
scrivi nella lista della spesa, ciò che le ricette richiedono, ciò su cui si
calcola la disponibilità.

**Prodotto specifico** — la referenza reale, `Fage Total 0%`, con marca, codice
a barre e valori per cento grammi. È ciò che entra in dispensa quando torni dal
supermercato.

La dispensa contiene prodotti quando li conosce e ingredienti nudi quando non
servono, per esempio le mele sfuse. Le ricette chiedono solo ingredienti
generici. Il match ricetta-dispensa resta quindi una join semplice, mentre i
nutrienti restano precisi perché vengono letti dalla marca esatta acquistata.

## 4. Scope

### Dentro la v1

- Anagrafica ingredienti canonici con alias e autocomplete tollerante
- Catalogo prodotti, alimentato da Open Food Facts e da inserimento manuale
- Lista della spesa con inserimento libero, risoluzione a ingrediente,
  raggruppamento per categoria e spunta in negozio
- Schermo "sistema la spesa": da lista spuntata a dispensa
- Ingresso diretto in dispensa con lo stesso schermo
- Scansione del codice a barre da fotocamera del browser
- Dispensa a tre stati
- Ricettario unico con tre provenienze: dataset, manuale, AI. In v1 la
  provenienza `dataset` è popolata da un seme curato; l'import massivo di una
  raccolta esterna è in fase 2
- Ricerca ibrida semantica più testuale, riordinata per disponibilità
- Sezione di scrittura ricette con AI, con salvataggio nel ricettario
- Flusso "cucina": aggiornamento stati e rientro automatico in lista
- Registrazione dell'evento di cottura
- Gate di accesso a password unica

### Fuori dalla v1, rimandato per fase

**Fase 2 — ingressi avanzati**
- Scansione dello scontrino con riconoscimento testo e interpretazione AI
- Creazione prodotto custom fotografando l'etichetta, con estrazione AI dei
  valori nutrizionali
- Import massivo di un dataset di ricette con revisione dei match incerti

**Fase 3 — nutrizione**
- Diario dei pasti, alimentato dagli eventi di cottura e dall'inserimento
  in linguaggio naturale interpretato dall'AI
- Integrazione delle tabelle di composizione per i micronutrienti
- Obiettivi personali e cruscotto delle carenze

**Fase 4 — suggerimenti**
- Ranking delle ricette per disponibilità combinata a carenze nutrizionali
- Generazione AI mirata alle carenze
- Suggerimenti proattivi sulla lista della spesa

**Orizzonte** — porting mobile incapsulando il frontend in Capacitor, con
scanner e fotocamera nativi al posto di quelli del browser.

## 5. Architettura

Tre servizi in Docker Compose, dietro Traefik in produzione, come in
`goldenhour/contrade`.

```
frontend/   React 19 + Vite + TypeScript, PWA mobile-first, servito da Nginx
backend/    FastAPI (Python 3.12), SQLAlchemy async, Alembic
db/         Postgres 16 + pgvector + pg_trgm
```

Tutta la logica di dominio vive nel backend. Il frontend non decide se una
ricetta è cucinabile: lo chiede. Questo è ciò che rende il porting a Capacitor
un incapsulamento e non una riscrittura.

Due dipendenze esterne, ciascuna isolata dietro un servizio con interfaccia
propria, in modo che il resto del codice non le conosca:

- `OpenFoodFactsClient` — risoluzione dei codici a barre
- `EmbeddingProvider` — vettori per la ricerca semantica

### Embedding

Implementazione predefinita locale: `intfloat/multilingual-e5-small`,
384 dimensioni, esecuzione su CPU dentro il container del backend tramite
`sentence-transformers`. Costo per query nullo, nessuna dipendenza di rete,
qualità adeguata su titoli e descrizioni di ricette in italiano. Il prezzo è
circa 500 MB di immagine e qualche centinaio di millisecondi al primo
caricamento del modello.

`EmbeddingProvider` resta astratto, con una seconda implementazione basata su
API HTTP, così il cambio di fornitore è una variabile d'ambiente.

### AI generativa

> **Superato il 2026-09-13.** Non è più l'API di Anthropic: è OpenRouter, con
> `google/gemma-4-26b-a4b-it` come modello di default (sostituibile in
> `OPENROUTER_MODEL`, anche con un modello Anthropic dietro lo stesso proxy). Vedi
> `docs/superpowers/specs/2026-09-13-llm-openrouter-design.md`, §3.

Claude API, modello `claude-sonnet-5`, usata in due punti e solo lì:

1. Stesura di una ricetta nella sezione dedicata
2. Proposta dell'ingrediente canonico quando un nome nuovo non trova un match
   affidabile

Il modello non produce mai valori nutrizionali: quelli vengono da Open Food
Facts o, in fase 3, dalle tabelle di composizione.

## 6. Modello dati

Sette tabelle. Chiavi primarie UUID, timestamp `timestamptz`.

### `ingredients`

| Campo | Tipo | Note |
|---|---|---|
| `id` | uuid | PK |
| `name` | text | canonico, minuscolo, univoco |
| `display_name` | text | forma leggibile |
| `category` | text | reparto: verdura, frutta, carne, pesce, latticini, cereali, legumi, condimenti, spezie, bevande, dolci, altro |
| `composition_ref` | text null | riferimento alle tabelle di composizione, popolato in fase 3 |
| `created_at`, `updated_at` | timestamptz | |

`category` guida il raggruppamento della lista nella vista da supermercato.

### `ingredient_aliases`

| Campo | Tipo | Note |
|---|---|---|
| `id` | uuid | PK |
| `ingredient_id` | uuid | FK `ingredients`, on delete cascade |
| `alias` | text | |
| `source` | text | `manual`, `import`, `ai`, `openfoodfacts` |

Univoco su `(ingredient_id, alias)`. Indice GIN trigram su `alias` e su
`ingredients.name` per l'autocomplete tollerante agli errori di battitura.

### `products`

| Campo | Tipo | Note |
|---|---|---|
| `id` | uuid | PK |
| `ingredient_id` | uuid | FK `ingredients`, obbligatorio |
| `name` | text | |
| `brand` | text null | |
| `barcode` | text null | univoco quando presente |
| `source` | text | `openfoodfacts`, `custom` |
| `source_payload` | jsonb null | risposta grezza, per rielaborazioni future |
| `nutrients` | jsonb null | per 100 g |
| `image_url` | text null | |
| `created_at`, `updated_at` | timestamptz | |

`ingredient_id` è obbligatorio per tenere pulite le query di disponibilità. Il
principio "mai un vicolo cieco" è preservato nell'interfaccia: se nessun
ingrediente canonico corrisponde, un solo tocco ne crea uno nuovo dal nome del
prodotto.

`nutrients` contiene, quando disponibili: `kcal`, `protein`, `carbs`, `sugars`,
`fat`, `saturated_fat`, `fiber`, `salt`. I micronutrienti vengono conservati se
presenti ma non sono usati in v1.

### `pantry_items`

| Campo | Tipo | Note |
|---|---|---|
| `id` | uuid | PK |
| `ingredient_id` | uuid | FK, obbligatorio |
| `product_id` | uuid null | FK, presente solo se il prodotto è noto |
| `status` | text | `available`, `low`, `finished` |
| `note` | text null | |
| `added_at` | timestamptz | |
| `status_changed_at` | timestamptz | |
| `archived_at` | timestamptz null | esclude la voce dai calcoli |

Più voci possono riferirsi allo stesso ingrediente: due yogurt di marche
diverse sono due voci. La disponibilità di un ingrediente è il migliore fra gli
stati delle sue voci non archiviate.

### `shopping_list_items`

| Campo | Tipo | Note |
|---|---|---|
| `id` | uuid | PK |
| `raw_text` | text | ciò che hai scritto |
| `ingredient_id` | uuid null | risolto quando possibile |
| `status` | text | `pending`, `checked`, `done`, `archived` |
| `reason` | text | `manual`, `finished_while_cooking`, `low_while_cooking` |
| `created_at`, `checked_at`, `done_at` | timestamptz | |

Qui `ingredient_id` è deliberatamente opzionale: mentre scrivi la lista non
devi essere interrotto. `pending` è da comprare, `checked` è nel carrello,
`done` è sistemato in dispensa.

### `recipes`

| Campo | Tipo | Note |
|---|---|---|
| `id` | uuid | PK |
| `title` | text | |
| `description` | text null | |
| `instructions` | text | markdown |
| `servings` | int null | |
| `source` | text | `dataset`, `manual`, `ai` |
| `source_ref` | text null | url, id del dataset o modello usato |
| `embedding` | vector(384) null | |
| `search_tsv` | tsvector | generato, configurazione `italian` |
| `created_at`, `updated_at` | timestamptz | |

Indice HNSW su `embedding`, indice GIN su `search_tsv`.

### `recipe_ingredients`

| Campo | Tipo | Note |
|---|---|---|
| `id` | uuid | PK |
| `recipe_id` | uuid | FK, on delete cascade |
| `ingredient_id` | uuid | FK |
| `role` | text | `primary`, `secondary` |
| `quantity_text` | text null | solo visualizzazione, mai usato in logica |
| `note` | text null | |

Univoco su `(recipe_id, ingredient_id)`.

### `cooking_events`

| Campo | Tipo | Note |
|---|---|---|
| `id` | uuid | PK |
| `recipe_id` | uuid null | FK; in v1 sempre valorizzato, il nullo è previsto per la cottura a braccio della fase 3 |
| `cooked_at` | timestamptz | |
| `servings` | int null | |
| `snapshot` | jsonb | ingredienti coinvolti e transizioni di stato applicate |

Non serve alla v1. Esiste perché la fase 3 costruisce il diario nutrizionale su
questo storico e la fase 4 ci impara sopra cosa cucini davvero. Registrarlo
adesso costa una tabella e nessuna complessità.

## 7. Regole di dominio

Sono il cuore del sistema e vivono in un unico modulo puro, senza accesso al
database, per poter essere testate a tabella.

### Disponibilità di un ingrediente

```
disponibilità(ingrediente) =
    available  se esiste una voce attiva con status = available
    low        altrimenti, se esiste una voce attiva con status = low
    missing    altrimenti
```

Le voci con `status = finished` o `archived_at` valorizzato non contano.

### Soddisfazione di un ingrediente di ricetta

```
soddisfatto(ingrediente_ricetta) =
    ruolo = primary    → disponibilità = available
    ruolo = secondary  → disponibilità ∈ { available, low }
```

Questa è la traduzione diretta della regola: un pomodoro quasi finito non ti fa
una pasta al pomodoro, ma ti fa un soffritto.

### Cucinabilità di una ricetta

```
mancanti(ricetta) = numero di ingredienti non soddisfatti
cucinabile(ricetta) = mancanti(ricetta) = 0
```

`mancanti` è anche il criterio di riordinamento dei risultati di ricerca.

## 8. Flussi

### 8.1 Lista della spesa

Campo di testo unico con autocomplete su `ingredients.name` e
`ingredient_aliases.alias`, ordinato per uso recente e frequenza. Un testo che
non trova corrispondenza entra comunque, con `ingredient_id` nullo.

La vista si raggruppa per `category` così da seguire il giro dei reparti. Ogni
voce si spunta passando a `checked`.

### 8.2 Sistema la spesa

È lo schermo centrale dell'app. Mostra le voci in stato `checked` e per
ciascuna offre tre strade:

1. **Codice a barre** — la fotocamera legge il codice, il backend cerca prima
   nel catalogo locale e poi su Open Food Facts, e propone il prodotto.
2. **Ricerca a catalogo** — ricerca per nome con affinamento progressivo: da
   `yogurt greco` a `yogurt greco carrefour pesca` finché non compare la
   referenza giusta.
3. **Voce generica** — conferma senza prodotto, per gli sfusi.

Ogni conferma crea una `pantry_items` in stato `available` e porta la voce di
lista a `done`.

Se il codice a barre è ignoto a Open Food Facts, si crea un prodotto `custom`
inserendo nome, marca e macro a mano. In fase 2 la stessa schermata accetterà
una foto dell'etichetta.

### 8.3 Ingresso diretto in dispensa

Stesso schermo di 8.2, punto di ingresso diverso, senza voci di lista da
consumare.

### 8.4 Cucinare

Il dettaglio ricetta mostra ogni ingrediente con il suo stato di disponibilità
e il suo ruolo. Il pulsante "cucina" apre una revisione degli ingredienti
utilizzati: per ognuno scegli fra invariato, quasi finito e finito. Il valore
predefinito è invariato, così tocchi solo ciò che cambia davvero.

La revisione opera sulle voci di dispensa concrete e non sugli ingredienti
astratti. Se un ingrediente ha una sola voce attiva, viene mostrata quella. Se
ne ha più di una, per esempio due yogurt di marche diverse, vengono elencate
tutte e dichiari lo stato di ciascuna, perché aver finito un vasetto non
significa aver finito l'altro.

Alla conferma, in una sola transazione:

- gli stati delle voci di dispensa vengono aggiornati
- gli ingredienti dichiarati `finished` generano voci di lista con
  `reason = finished_while_cooking`, preselezionate ma deselezionabili
- gli ingredienti passati a `low` possono opzionalmente generare voci con
  `reason = low_while_cooking`, non preselezionate
- viene scritto un `cooking_events`

### 8.5 Ricettario e ricerca

Le tre provenienze vivono in un elenco unico, ciascuna con il badge della
sorgente. La ricerca è ibrida:

1. La query va in parallelo alla ricerca vettoriale su `embedding` e alla
   ricerca testuale su `search_tsv`
2. I due insiemi si fondono con Reciprocal Rank Fusion
3. Il punteggio finale viene corretto da `mancanti(ricetta)`, che riordina ma
   non filtra

Una ricetta a cui manca un solo ingrediente resta visibile, perché è
un'informazione utile. Esiste un filtro esplicito per le sole ricette
cucinabili ora.

### 8.6 Scrittura AI

Sezione dedicata: descrivi cosa vuoi, il modello propone una ricetta
strutturata con ingredienti e ruoli già separati. Puoi modificarla e salvarla
nel ricettario con `source = ai`. Al salvataggio gli ingredienti vengono
agganciati all'anagrafica, chiedendo conferma solo dove il match è incerto.

## 9. API

Prefisso `/api/v1`. Tutte le rotte sono dietro il gate di sessione tranne
`/health` e `/auth/login`.

| Metodo | Rotta | Scopo |
|---|---|---|
| `GET` | `/ingredients/search?q=` | autocomplete su nomi e alias |
| `POST` | `/ingredients` | crea ingrediente canonico |
| `POST` | `/ingredients/{id}/aliases` | aggiunge alias |
| `GET` | `/products/barcode/{code}` | catalogo locale, poi Open Food Facts |
| `GET` | `/products/search?q=` | ricerca a catalogo |
| `POST` | `/products` | prodotto custom |
| `GET` | `/pantry` | dispensa, raggruppata per categoria |
| `POST` | `/pantry` | inserisce una voce |
| `PATCH` | `/pantry/{id}` | cambia stato o archivia |
| `GET` | `/pantry/availability` | mappa ingrediente → disponibilità |
| `GET` | `/shopping-list` | lista corrente |
| `POST` | `/shopping-list` | aggiunge voce da testo libero |
| `PATCH` | `/shopping-list/{id}` | spunta, risolve l'ingrediente, archivia |
| `POST` | `/shopping-list/stock` | trasforma voci spuntate in voci di dispensa |
| `GET` | `/recipes/search?q=&only_cookable=` | ricerca ibrida |
| `GET` | `/recipes/{id}` | dettaglio con disponibilità calcolata |
| `POST` | `/recipes` | salva ricetta, qualunque provenienza |
| `POST` | `/recipes/{id}/cook` | applica transizioni e rigenera la lista |
| `POST` | `/recipes/ai-draft` | genera una bozza, non salva |
| `POST` | `/auth/login`, `/auth/logout` | sessione |

## 10. Frontend

React 19, Vite, TypeScript. Mobile-first: il layout è progettato sul telefono e
il desktop è una versione allargata, mai il contrario. PWA installabile con
`vite-plugin-pwa`.

Navigazione a tre schede in basso: **Lista**, **Dispensa**, **Ricette**. Lo
schermo "sistema la spesa" si apre dalla Lista e a schermo intero, perché è un
compito con un inizio e una fine. La scrittura AI vive dentro la scheda
Ricette, come modalità di creazione accanto all'inserimento manuale.

Stato server gestito con TanStack Query. Nessuna logica di dominio duplicata
lato client.

Scansione del codice a barre: `BarcodeDetector` nativo quando il browser lo
espone, altrimenti `@zxing/browser` come riserva. Richiede HTTPS, quindi lo
sviluppo locale usa un certificato self-signed per poter provare con il
telefono.

## 11. Gestione errori

Il principio è uno solo: **nessun percorso di inserimento può finire in un
muro**.

| Guasto | Comportamento |
|---|---|
| Open Food Facts irraggiungibile o lento | timeout breve, si passa all'inserimento manuale del prodotto |
| Codice a barre sconosciuto | schermata di creazione prodotto custom precompilata col codice |
| Modello di embedding non caricato | la ricerca degrada a sola ricerca testuale, con avviso discreto |
| Ingrediente non risolto | la voce resta salvata con `ingredient_id` nullo, senza bloccare |
| Claude API non disponibile | la sezione AI segnala il guasto, il resto dell'app non ne risente |

## 12. Testing

Sviluppo guidato dai test, test scritti prima del codice.

**Priorità uno**: il modulo delle regole di dominio del capitolo 7, testato a
tabella su tutte le combinazioni di stato e ruolo, incluso il caso di più voci
di dispensa per lo stesso ingrediente. È puro, non tocca il database, e regge
tutto il resto.

**Backend**: `pytest` con `pytest-asyncio`, su un Postgres vero avviato in
Compose, mai SQLite, perché servono `pgvector` e `pg_trgm`. Ogni test in una
transazione con rollback.

**Client Open Food Facts**: test su risposte registrate, nessuna chiamata di
rete nella suite. Le fixture includono un prodotto completo, uno con nutrienti
mancanti e un codice sconosciuto.

**Transazione di cottura**: test di integrazione che verifica atomicità,
ovvero stati aggiornati, voci di lista create ed evento registrato, oppure
nulla.

**Frontend**: Vitest sulla logica di presentazione e sui form. Un solo percorso
end-to-end con Playwright, quello del cucinare, perché è il flusso che tocca
tutte le tabelle.

## 13. Deploy e configurazione

`docker-compose.yml` per lo sviluppo, con Postgres, backend e frontend. In
produzione, Traefik davanti, come in `goldenhour/contrade`. Le migrazioni
Alembic girano all'avvio del backend.

Accesso: password unica confrontata con un hash, che emette un cookie di
sessione HttpOnly a lunga scadenza. Non è multiutente, serve solo a non tenere
l'app aperta in chiaro su internet.

| Variabile | Default | Scopo |
|---|---|---|
| `POSTGRES_*` | vedi `.env.example` | connessione al database |
| `SESSION_SECRET` | nessuno, obbligatorio | firma del cookie di sessione |
| `APP_PASSWORD_HASH` | nessuno, obbligatorio | hash della password di accesso |
| `ANTHROPIC_API_KEY` | vuoto | sezione di scrittura AI e matching incerto — **superato il 2026-09-13**: è `OPENROUTER_API_KEY`, vedi `docs/superpowers/specs/2026-09-13-llm-openrouter-design.md`, §8 |
| `EMBEDDING_BACKEND` | `local` | `local` oppure `http` |
| `EMBEDDING_MODEL` | `intfloat/multilingual-e5-small` | modello locale |
| `OFF_BASE_URL` | api ufficiale | sovrascrivibile nei test |
| `OFF_TIMEOUT_SECONDS` | `3` | oltre il quale si degrada al manuale |

### Struttura del repository

```
backend/
  app/
    api/          rotte REST
    core/         config, sicurezza, sessione
    db/           modelli SQLAlchemy, migrazioni Alembic
    domain/       regole pure: disponibilità, cucinabilità
    services/     openfoodfacts, embeddings, ricerca, matching, ai
  tests/
frontend/
  src/
    features/     shopping-list, pantry, recipes, cooking, ai-draft
    components/   elementi condivisi
    api/          client REST tipizzato
data/
  ingredients_seed.json    anagrafica iniziale
  recipes_seed.json        semina ricette
docs/superpowers/specs/
docker-compose.yml
```

## 14. Rischi noti

**Popolamento iniziale dell'anagrafica.** Un'app vuota non è utile. La v1 parte
con un seme curato di ingredienti canonici italiani con le categorie da
supermercato, sufficiente a coprire la spesa ordinaria. Non è un lavoro
rimandabile: senza di esso l'autocomplete non ha nulla da suggerire.

**Semina del ricettario.** Per lo stesso motivo servono alcune decine di
ricette dal primo giorno. La v1 usa un seme piccolo e curato. L'import massivo
di un dataset esterno, con la normalizzazione degli ingredienti e la revisione
dei match incerti, è esplicitamente in fase 2, per non far dipendere la v1
dalla ricerca del dataset perfetto.

**Ruolo principale o secondario nei dati importati.** Le ricette scritte a mano
e quelle generate dall'AI dichiarano il ruolo. Un dataset esterno quasi
certamente no. Alla fase 2 servirà una regola di assegnazione predefinita, per
esempio secondario per spezie e condimenti e principale per tutto il resto, con
revisione manuale. In v1 il problema non si pone.

**Copertura italiana di Open Food Facts.** Buona sui prodotti della grande
distribuzione, incompleta sui marchi regionali e sui discount. Il prodotto
custom è la valvola di sfogo, ed è il motivo per cui non è rimandabile alla
fase 2 insieme alla stima da foto.
