# Spena — Import massivo di ricette (fase 2)

**Data:** 2026-09-12
**Stato:** approvato in chat, da pianificare
**Spec madre:** `docs/superpowers/specs/2026-09-11-spena-design.md`, §4 «Fase 2 — ingressi avanzati»
**Fonte del primo import:** GialloZafferano (`ricette.giallozafferano.it`), deciso dall'utente

## 1. Obiettivo

Il ricettario contiene 26 ricette, seminate a mano. La domanda su cui è costruita
tutta la dispensa — «cosa posso cucinare adesso» — con 26 ricette ha quasi sempre
la stessa risposta, e il cerchio della v1 gira a vuoto sul lato della cucina.

Questo lavoro porta nel ricettario centinaia di ricette italiane vere, con foto,
tempi e categoria, **senza che l'anagrafica degli ingredienti perda la granularità
che rende affidabile il calcolo di disponibilità**. La seconda metà di quella frase
è il vero problema da risolvere; la prima è un parser di venti righe.

Criteri di riuscita, in ordine:

1. Nessuna ricetta importata dichiara `cookable` ciò che non è cucinabile. Una
   bugia qui si scopre a metà cottura, ed è il modo più rapido per far abbandonare
   l'app.
2. Dopo un lotto da 200 ricette il ricettario le contiene tutte, o dice per ognuna
   che manca cosa e perché.
3. Nel caso comune la revisione di un termine è un tocco: la proposta è giusta e
   si conferma. Si può interrompere in qualsiasi momento senza perdere nulla.
4. L'anagrafica cresce in modo coerente: `pasta` resta `pasta`, e `Rigatoni`
   diventa un suo alias, non un quindicesimo cereale.

## 2. La decisione che governa tutto: il catalogo della fonte è più fine del nostro

Misurato su 30 ricette prese a caso dalla loro sitemap:

| Misura | Valore |
|---|---|
| ricette nella sitemap `ricette.xml` | 8449 |
| righe ingrediente lette | 346 |
| righe per ricetta (media) | 11,5 |
| termini ingrediente distinti | 143 |
| termini visti una volta sola | 80 |

Dove la nostra anagrafica ha `pasta`, la loro ha `Rigatoni`, `Penne`, `Spaghetti`.
Dove noi abbiamo `formaggio grattugiato`, loro hanno `Parmigiano Reggiano DOP` e
`Grana Padano DOP`. Dove noi abbiamo `latte`, loro hanno `Latte intero`.

Questa differenza non è un difetto dei loro dati: è la distanza fra un catalogo
editoriale e un'anagrafica fatta per rispondere «ce l'ho in casa?». E non si può
colmare automaticamente, perché colmarla male avvelena la disponibilità di tutte
le ricette che usano quell'ingrediente — cioè rompe esattamente la cosa per cui
stiamo importando.

Più della metà dei termini compare una volta sola, quindi la coda **non si
esaurisce da sé** crescendo il corpus: cresce con esso, più lentamente.

**La decisione presa:** ogni termine distinto della fonte è una decisione umana,
presa una volta sola e riusata per sempre. Una ricetta che contiene un termine non
ancora deciso resta scaricata e fuori dal ricettario, finché quel termine non ha
una decisione. Le alternative scartate, con il motivo:

- *Creare automaticamente un ingrediente per ogni termine sconosciuto.* Riempie il
  ricettario in un pomeriggio e rompe la dispensa: avere `pasta` in casa non
  renderebbe cucinabile una ricetta che chiede `Rigatoni`. Si perde la funzione
  mentre si guadagna il contenuto.
- *Far entrare la ricetta con la riga non agganciata come testo libero.* Richiede di
  rendere opzionale `recipe_ingredients.ingredient_id` e di decidere cosa risponde
  la cucinabilità su una riga ignota. Dire «sì» è la bugia del criterio 1; dire «no»
  nasconde ricette fattibili. Entrambe peggio dell'attesa.

**Ciò che rende sopportabile l'attesa** è che la coda è ordinata per frequenza,
che ogni riga arriva con una proposta già scritta, e che decidere un termine
smaterializza subito le ricette che lo aspettavano. La revisione non è un modulo
da compilare: è una serie di conferme con un risultato visibile a ogni tocco.

**Dove vive la decisione presa:** in `ingredient_aliases`, che esiste già. Collegare
il termine `Rigatoni` all'ingrediente `pasta` scrive l'alias `rigatoni` con
`source='import'`. L'alias si scrive **solo se quell'alias non esiste già per
nessun ingrediente**: il vincolo del database è su `(ingredient_id, alias)` e
lascerebbe passare lo stesso alias su due ingredienti diversi, cioè un autocomplete
che dà due risposte a una domanda sola. Il legame fra termine e ingrediente vive
comunque su `import_terms`, quindi saltare l'alias non perde la decisione. Da quel momento lo conosce anche l'autocomplete della lista
della spesa, e il prossimo lotto lo risolve da sé senza chiedere niente. Il
dizionario dell'import e l'anagrafica dell'app sono la stessa cosa: non esiste
una seconda tabella di mappatura.

## 3. Nota su `robots.txt` e sul diritto d'autore

Va scritto perché chi legge questo codice fra sei mesi ha il diritto di saperlo.

Il `robots.txt` di `ricette.giallozafferano.it` consente a un agente generico di
leggere le pagine delle ricette, e pubblica le sitemap per farlo. Contiene però
anche queste righe:

```
User-agent: Claude-Web
Disallow: /

User-agent: anthropic-ai
Disallow: /
```

Il sito vieta esplicitamente i crawler AI. Uno script personale che archivia
ricette scelte dal proprietario dell'app non è quei crawler, ma la distanza fra
«leggo una ricetta» e «scarico l'archivio» è precisamente quella che quelle righe
dichiarano di non volere. Le condizioni d'uso del sito con ogni probabilità
vietano la raccolta sistematica, e il testo dei procedimenti è materiale protetto.

La scelta di procedere è dell'utente, consapevole, ed è stata presa in chat. Il
progetto la rispetta nei modi che restano:

- si scarica **una pagina alla volta**, con pausa di cortesia, mai in parallelo;
- non si riscarica mai un indirizzo già preso;
- nessuna identità di crawler AI: lo `User-Agent` dice cosa è, un archivio personale;
- **niente ridistribuzione.** Le ricette vivono nel database dell'utente. Questo
  include le fixture dei test: il repository è pubblico, quindi le fixture **non**
  sono pagine intere salvate così come sono (vedi §12).
- ogni ricetta conserva l'indirizzo originale in `source_ref`, e la schermata della
  ricetta offre «apri l'originale»: l'attribuzione è sempre a un tocco.

## 4. Cosa offre la pagina di origine

Verificato su pagine vere, non dedotto.

**Un blocco `application/ld+json` con `@type: Recipe`**, che porta `name`,
`description`, `recipeInstructions` (lista di paragrafi), `recipeYield`,
`prepTime`/`cookTime`/`totalTime` in durata ISO 8601, `recipeCategory`, `image`,
`keywords` e `nutrition` con i valori calcolati da loro.

**Nel corpo della pagina, il nome e la quantità dell'ingrediente sono già due
elementi separati**, dentro `dl.gz-list-ingredients`:

```html
<dd class="gz-ingredient">
  <a href="/ricette-con-i-Rigatoni/" title="Ricette con i Rigatoni">Rigatoni</a>
  <span> 320 g </span>
</dd>
```

Questo è il fatto che rende inutile qualunque modello nel parsing: il nome non va
estratto da una stringa, è un elemento, e l'`href` è una chiave stabile per il
termine, indipendente da come è scritto il nome. Le dosi restano testo libero, come
vuole la decisione fondante sulle quantità.

**Gli ingredienti possono essere divisi in gruppi**, con intestazioni
`dt.gz-title-ingredients` tipo «Per la pasta frolla». Il parser prende tutti i `dd`
nell'ordine e ignora le intestazioni, e questo ha una conseguenza che va gestita:
**lo stesso termine può comparire due volte nella stessa ricetta** (misurato sulla
torta della nonna: `Zucchero a velo` e `Scorza di limone` due volte ciascuno).
Vedi §8, collasso dei duplicati.

Il testo dei passaggi contiene i rimandi numerici alle fotografie, come numeri
isolati prima della punteggiatura: «rosolare lo speck a fiamma viva per circa 5
minuti 2 .». Vanno ripuliti, perché una ricetta si legge mentre si cucina.

Le entità HTML compaiono nelle quantità (`&frac12;`) e vanno decodificate.

## 5. Architettura: quattro stadi, ognuno rieseguibile

```
sitemap ──► [1 scarico] ──► recipe_imports (pending)
                                  │
                                  ├──► [2 termini] ──► import_terms (pending|mapped|ignored)
                                  │                         │
                                  │                   [3 revisione] ◄── proposte di Claude
                                  │                         │
                                  └──► [4 materializzazione] ◄┘ ──► recipes + recipe_ingredients
```

Ogni stadio è idempotente, come il seme di oggi: rieseguirlo non duplica nulla.

**1. Scarico** — `python -m app.cli.import_gz --limit N` dentro il container del
backend. Legge la sitemap, scarta gli indirizzi già presenti in `recipe_imports`,
ne prende N nell'ordine della sitemap, scarica ognuno con la pausa, lo analizza e
ne salva la **lettura normalizzata** in `payload`. Non salva l'HTML: sull'archivio
intero sarebbe mezzo gigabyte, e una volta analizzata la pagina non serve più. Alla
fine ricalcola i conteggi di `import_terms` e stampa un riepilogo: quante prese,
quante scartate e perché, quanti termini nuovi aspettano una decisione.

**2. Termini** — ogni ingrediente distinto diventa una riga di `import_terms`,
identificata dall'`href` e non dal nome. Alla creazione si tenta la risoluzione
automatica: se il nome normalizzato **coincide esattamente** con un nostro nome
canonico o con un alias esistente, il termine è deciso con `decided_by='auto'`.
Tutto il resto resta `pending`. L'uguaglianza non è una proposta: è un fatto, e
non ha bisogno di conferma.

**3. Revisione** — una schermata dentro il ricettario (§10). I termini `pending`
arrivano dal più frequente al più raro. Per ognuno, tre azioni possibili: collega a
un ingrediente esistente, crea un ingrediente nuovo con la sua categoria, ignora.
Claude pre-compila la proposta; l'utente conferma o corregge. **La proposta non si
applica mai da sé**: è il principio della spec madre, Claude propone e non decide.

**4. Materializzazione** — dopo ogni decisione, ogni riga `pending` di
`recipe_imports` i cui termini sono tutti decisi diventa una `Recipe` vera, con le
sue `recipe_ingredients` e il vettore se disponibile. La risposta dice quante
ricette ha sbloccato la decisione, e la schermata lo mostra.

## 6. Modello dati

### 6.1 `recipe_imports` (nuova)

Una riga per pagina scaricata. È l'area di sosta, e resta dopo l'import come
registro di ciò che si è preso.

| Colonna | Tipo | Note |
|---|---|---|
| `id` | uuid | chiave |
| `source` | varchar(40) | `giallozafferano` |
| `url` | varchar(500) | unico con `source` |
| `fetched_at` | timestamptz | default `now()` |
| `payload` | jsonb | la lettura normalizzata, §6.4 |
| `state` | varchar(20) | `pending` \| `imported` \| `skipped` |
| `skipped_reason` | varchar(200) | valorizzato solo se `skipped` |
| `recipe_id` | uuid null | FK `recipes(id)`, `ON DELETE SET NULL` |

Vincoli: `UNIQUE (source, url)`, check su `state`, indice su `state`.

`ON DELETE SET NULL` e non `CASCADE`: se l'utente cancella una ricetta importata,
la riga dell'import deve **sopravvivere con `state='imported'`**, altrimenti la
materializzazione successiva la ricrea e la cancellazione non è mai definitiva.
Lo stato, non la presenza della chiave, è ciò che dice «questa pagina è già stata
importata una volta».

Una pagina senza dati strutturati utilizzabili non sparisce: si salva con
`state='skipped'` e il motivo in chiaro. Un import silenzioso che perde il 3% delle
pagine è un import di cui non si può dire niente.

### 6.2 `import_terms` (nuova)

Una riga per ingrediente del catalogo della fonte. È il dizionario.

| Colonna | Tipo | Note |
|---|---|---|
| `id` | uuid | chiave |
| `source` | varchar(40) | `giallozafferano` |
| `key` | varchar(200) | unico con `source`; lo slug dell'`href` |
| `display_name` | varchar(200) | `Rigatoni`, come lo scrivono loro |
| `occurrences` | int | quante righe ingrediente lo usano |
| `decision` | varchar(20) | `pending` \| `mapped` \| `ignored` |
| `ingredient_id` | uuid null | FK `ingredients(id)`, `ON DELETE RESTRICT` |
| `role_override` | varchar(20) null | `primary` \| `secondary`, §9 |
| `decided_by` | varchar(20) null | `auto` \| `human` |
| `decided_at` | timestamptz null | |

Vincoli: `UNIQUE (source, key)`, indice su `(decision, occurrences DESC)`, check su
`decision` e su `role_override`, e un check che dice la cosa importante:

```sql
CHECK (decision <> 'mapped' OR ingredient_id IS NOT NULL)
```

Senza, un termine «collegato» a niente produce ricette con una riga in meno, cioè
una disponibilità calcolata su una ricetta che non è quella scritta.

`occurrences` **si ricalcola a ogni scarico** con una passata sui payload, non si
incrementa. Un contatore incrementato divergerebbe al primo ri-scarico, e un
ordinamento della coda basato su un numero sbagliato è un difetto che nessuno nota.

### 6.3 `recipes`: quattro colonne nuove

| Colonna | Tipo | Note |
|---|---|---|
| `image_url` | varchar(500) null | caricata dal server di origine, non copiata |
| `prep_minutes` | int null | da `prepTime` |
| `cook_minutes` | int null | da `cookTime` |
| `category` | varchar(60) null | `Primi piatti`, come la scrive la fonte |

`category` è testo libero e non un enum: la tassonomia è loro, e un enum
costringerebbe a una migrazione il giorno che aggiungono una voce. Indice su
`category` per il filtro del ricettario.

Tutte nullabili, perché le 26 ricette del seme e quelle scritte con l'AI non le
hanno, e continueranno a non averle.

### 6.4 La forma di `payload`

```json
{
  "title": "Pasta con crema di Parmigiano e speck",
  "description": "...",
  "instructions": "passaggi uniti e ripuliti",
  "servings": 4,
  "category": "Primi piatti",
  "image_url": "https://...",
  "prep_minutes": 10,
  "cook_minutes": 15,
  "ingredients": [
    {"key": "ricette-con-i-Rigatoni", "name": "Rigatoni", "quantity_text": "320 g"}
  ],
  "nutrition": { "...": "copiato alla lettera dal JSON-LD" }
}
```

`nutrition` si conserva e non si usa: la fase 3 leggerà da qui senza riscaricare
niente, e la regola «i nutrienti assenti restano assenti» vale anche per questi,
che non entrano in nessun calcolo oggi.

## 7. Il parser

`backend/app/services/recipe_import/giallozafferano.py`

- `RECIPE_SITEMAP` — `https://ricette.giallozafferano.it/sitemap/ricette.xml`
- `async def fetch_sitemap(client) -> list[str]`
- `def parse_recipe(html: str) -> ParsedRecipe` — **funzione pura sul testo della
  pagina, nessuna rete.** È il nucleo verificabile.
- `def clean_instructions(steps) -> str` — funzione pura.

`parse_recipe` solleva `UnparsablePage(reason)` quando la pagina non è
utilizzabile, e il motivo finisce in `skipped_reason`. Casi: nessun blocco JSON-LD
di tipo `Recipe`, nessun `dd.gz-ingredient`, titolo vuoto.

Dettagli che il parser deve gestire perché sono nei dati veri:

- Il JSON-LD può essere un oggetto, una lista, o avere un `@graph`: si cerca in
  tutti e tre il membro con `@type == "Recipe"`.
- `recipeInstructions` arriva come lista di stringhe, lista di oggetti `HowToStep`
  con `text`, o stringa singola. Tutte e tre.
- `recipeYield` può essere intero o stringa (`"4"`, `"4 persone"`, `"10"`): si
  prende il primo intero, e si tiene solo se sta fra 1 e 50, che sono i limiti dello
  schema esistente.
- `prepTime`/`cookTime` sono durate ISO 8601 (`PT10M`, `PT1H30M`): in minuti.
- Le entità HTML si decodificano, nei nomi e nelle quantità.
- Il `key` del termine è lo slug dell'`href`, senza le barre. Se la riga non ha
  link — possibile, il catalogo non copre tutto — il `key` è `testo:` più il nome
  normalizzato, così il termine esiste comunque e la ricetta non si perde.
- `quantity_text` è troncato a 100 caratteri, che è il limite della colonna.

La pulizia dei rimandi fotografici è una regola stretta, non generosa: si rimuove
un numero di una o due cifre **solo** quando è isolato da spazi e seguito
immediatamente da punto, virgola o fine del paragrafo. Così «striscioline di circa
1 cm 1 .» diventa «striscioline di circa 1 cm.» e «cuoci 15 minuti» resta intatto.
Tavola di casi nei test, compresi i casi che **non** devono cambiare.

Per l'analisi dell'HTML si aggiunge `beautifulsoup4` alle dipendenze, usato con il
parser della libreria standard. Senza `lxml`: è compilato e pesa, e qui non serve.
Un parser a espressioni regolari su `dd class="gz-ingredient"` funzionerebbe oggi
e si romperebbe al primo attributo aggiunto.

## 8. Risoluzione dei termini e materializzazione

### 8.1 Una sola funzione di aggancio, due chiamanti

La logica «nome grezzo → ingrediente, e quanto mi fido» **esiste già**, dentro
`app/services/ai_recipes.py::_match`. Non va copiata: va estratta in
`app/services/ingredient_match.py` come `match_name(session, raw) -> NameMatch`, e
la stesura AI diventa un suo chiamante. La lezione è scritta in CLAUDE.md e il
progetto l'ha già pagata tre volte: un test che difende una copia che nessuno
chiama non difende niente.

Nell'estrazione la certezza si allarga a un fatto che oggi manca: **anche la
coincidenza esatta con un alias è certa**, non solo quella con il nome canonico.
Oggi `_match` marca incerto `pomodori pelati` che è un alias esplicito di
`pomodoro`, e chiede una conferma che non serve.

### 8.2 Le proposte di Claude

`app/services/recipe_import/terms.py::propose_decisions(session, terms)`

Una chiamata per lotto di termini (massimo 40), modello `claude-sonnet-5`. Riceve i
nomi dei termini e l'elenco dei nostri ingredienti canonici con la loro categoria.
Risponde, per ogni termine, una fra:

- `{"action": "map", "ingredient": "pasta"}` — è lo stesso ingrediente, scritto più
  in dettaglio
- `{"action": "create", "name": "speck", "display_name": "Speck", "category": "carne"}`
  — è un ingrediente generico che non abbiamo
- `{"action": "ignore"}` — non è un ingrediente da tenere in dispensa (acqua,
  ghiaccio, acqua per la cottura)

Le categorie ammesse sono le dodici di `IngredientCategory`, e una risposta fuori
da quell'insieme si scarta come se la proposta non ci fosse. Un nome di ingrediente
che non esiste nell'anagrafica in una `map` si scarta allo stesso modo: una proposta
non verificata è rumore, non un dato.

`AiUnavailable` non è un errore della schermata. La coda funziona comunque, con la
proposta debole che viene dalla somiglianza testuale, e lo dichiara in una riga.
È la regola «mai un vicolo cieco» della spec madre.

### 8.3 Materializzazione

`app/services/recipe_import/materialize.py::materialize_ready(session) -> int`

Prende le righe `pending` di `recipe_imports` i cui termini sono tutti decisi e
crea la ricetta con `create_recipe`, cioè con la stessa funzione che usa
`POST /recipes`. Passa per `source='dataset'` e `source_ref=<url>`.

Tre regole non ovvie:

1. **Collasso dei duplicati.** Lo stesso termine può comparire due volte nella
   stessa ricetta, e due termini diversi possono essere collegati allo stesso
   ingrediente. `recipe_ingredients` ha `UNIQUE (recipe_id, ingredient_id)`, quindi
   senza collasso l'inserimento fallisce. Le righe che finiscono sullo stesso
   ingrediente diventano **una** riga: le quantità si uniscono con ` + ` e si
   troncano a 100 caratteri, e il ruolo è il più forte dei due, perché `primary`
   vince su `secondary` (una ricetta che usa la farina per la frolla e per la crema
   ha bisogno della farina).
2. **I termini ignorati non producono righe**, e non fanno scartare la ricetta.
   Ignorare è una scelta umana: l'acqua non entra in dispensa.
3. **Una ricetta senza nemmeno una riga superstite si scarta** con motivo, invece
   di entrare vuota. Una ricetta senza ingredienti è sempre cucinabile, che è la
   bugia del criterio 1 nella sua forma peggiore.

Il vettore si calcola come già fa il seme, sullo stesso testo (`titolo. descrizione`),
e la sua assenza non blocca niente.

Ri-decidere un termine già deciso è permesso, ed è il modo di correggere un errore.
Vale però solo per le ricette non ancora materializzate: quelle già entrate non si
riscrivono. Una mappatura sbagliata già usata si corregge dall'anagrafica, togliendo
l'alias e sistemando le ricette dal ricettario.

## 9. Primario o secondario

Il ruolo è la cosa che rende utile lo stato `low` (CLAUDE.md), e la fonte non ce lo
dà. Si deduce da due segnali che i dati hanno davvero, in `app/domain/rules.py`:

```python
def default_role(category: str, quantity_text: str | None) -> IngredientRole
```

`secondary` se la quantità è «q.b.» (o «qb», «a piacere») **oppure** se la categoria
dell'ingrediente è `spezie` o `condimenti`. `primary` in tutti gli altri casi.
Funzione pura, tavola di casi su tutte e dodici le categorie.

La regola sbaglia dove il buon senso culinario non segue la categoria: l'aglio è
`verdura` e quasi sempre secondario. Per questo la decisione del termine porta un
`role_override` facoltativo: un controllo in più sulla schermata che l'utente sta
già guardando, da toccare solo per le eccezioni. Quando c'è, vince sulla regola.

L'override sta su `import_terms` e non su `ingredients`, perché è una correzione
alla deduzione dell'import, non una proprietà dell'ingrediente. Le ricette scritte
a mano e quelle dell'AI continuano a dichiarare il ruolo per riga, come oggi.

## 10. API e frontend

### 10.1 Rotte, sotto `/api/v1/imports`, dietro `require_session`

| Rotta | Risposta |
|---|---|
| `GET /status` | `{fetched, pending_recipes, imported, skipped, pending_terms}` |
| `GET /terms?limit=20` | i termini `pending`, dal più frequente: `{id, display_name, occurrences, suggestion, waiting_titles}` |
| `POST /terms/proposals` | corpo `{term_ids: [...]}` → `{proposals: [...]}`; `503` se Claude non risponde |
| `POST /terms/{id}/decision` | corpo `{action, ...}` → `{unlocked, remaining_terms}` |

`suggestion` è l'aggancio testuale (`{ingredient_id, name, certain}`) oppure nullo.
`waiting_titles` sono al massimo tre titoli di ricette in attesa di quel termine:
servono a decidere, perché «Scorza di limone» si giudica diversamente in una torta
e in un arrosto.

Le tre forme del corpo di `decision`:

```
{"action": "map",    "ingredient_id": "...",  "role_override": null}
{"action": "create", "name": "speck", "display_name": "Speck", "category": "carne", "role_override": null}
{"action": "ignore"}
```

`404` su termine o ingrediente inesistente; `409` su `create` con un nome già in
anagrafica, col messaggio che dice di collegare invece di creare. Le proposte
stanno in una rotta separata dall'elenco di proposito: la coda deve caricarsi
subito, e il fallimento di Claude non deve poter svuotare una schermata che
funziona anche senza.

### 10.2 Schermate

- **Ingresso:** una riga in cima al ricettario, visibile **solo** se
  `pending_terms > 0`: «23 ingredienti da abbinare, 61 ricette in attesa». Porta a
  `/ricette/importa`. Quando la coda è vuota non c'è niente da vedere e la riga
  non c'è.
- **`features/recipe-import/ImportQueueScreen.tsx`:** un termine per scheda, con il
  nome come lo scrive la fonte, quante ricette lo aspettano, i titoli di esempio, e
  la proposta già selezionata. Tre azioni, e per «collega» si riusa
  `IngredientPicker`, che esiste. Dopo ogni decisione una riga di esito:
  «sbloccate 12 ricette». La coda si ricarica e il primo termine è già pronto.
- **Ricettario:** la scheda della ricetta mostra la foto (con `loading="lazy"`,
  perché duecento schede su un telefono sono duecento immagini) e il tempo totale.
  Sopra l'elenco, un filtro per categoria, alimentato dalle categorie presenti.
- **Dettaglio della ricetta:** «apri l'originale» quando `source_ref` è un
  indirizzo. È l'attribuzione, e si applica anche alle 26 ricette del seme, dove
  `source_ref` non è un link e quindi il collegamento non appare.

Tutto con i token e le primitive di `components/ui/`, come da CLAUDE.md: nessuna
schermata nomina un colore.

## 11. Il ricettario grande rompe due cose che oggi funzionano

Vanno riparate qui, perché è questo lavoro a farle emergere. È il principio
«chiudere un buco ne apre un altro» scritto in CLAUDE.md.

**1. La piscina dei candidati.** `recipe_search.py` ha `CANDIDATE_POOL = 100`, e
senza query seleziona le 100 ricette più recenti. Con 26 ricette è tutto il
ricettario; con 500 diventa un campione, e `only_cookable` filtra **dentro** quel
campione. Cioè «mostrami solo ciò che posso cucinare» smetterebbe di guardare la
maggior parte del ricettario: la domanda centrale dell'app risponderebbe male
proprio per effetto dell'import.

Rimedio: nel percorso senza query, il filtro di categoria e la selezione vanno in
SQL prima del limite, e quando `only_cookable` è vero i requisiti si calcolano su
tutte le ricette candidate invece che sulle prime cento. Una sola interrogazione
raggruppata; a cinquecento ricette è gratis, oltre qualche migliaio va misurata di
nuovo e, se non regge, la regola scende in SQL. Il test copre il caso con più
ricette della piscina, che oggi non esiste in nessun test.

**2. Le ricette senza vettore.** L'immagine di produzione è costruita con
`INSTALL_EMBEDDINGS=0`, quindi ogni ricetta importata nasce senza vettore, e il
seme attuale si scusa in una riga di stampa dicendo che rieseguirlo non rimedia.
Con 26 ricette è un fastidio; con 500 è la ricerca semantica spenta per sempre.

Rimedio: `python -m app.cli.reindex`, che calcola i vettori mancanti e dice quanti
ne ha scritti. Chiude il vicolo cieco esistente, non solo quello nuovo. Il README
dice che va eseguito dopo un import se si tiene la ricerca semantica accesa.

## 12. Educazione nello scarico

In `app/services/recipe_import/giallozafferano.py`, come costanti con il loro
perché accanto:

- `USER_AGENT` che dichiara cosa è: un archivio personale, nessuna ridistribuzione.
- `DELAY_SECONDS = 1.2` fra una pagina e l'altra. Sequenziale, una connessione.
- Mai due volte lo stesso indirizzo: il controllo è su `recipe_imports.url`.
- Due risposte consecutive `429` o `5xx` fermano il giro, che riporta quante pagine
  ha preso. Insistere contro un sito che sta dicendo di smettere è la cosa da non
  fare, e perdere il lavoro già fatto è inutile: le pagine prese sono già salvate.
- `--limit` ha un valore di default prudente (50) e la sitemap si scarica una volta
  per giro.

## 13. Verifica

Nessuna rete nella suite, come vuole la spec madre. Fixture registrate in
`backend/tests/fixtures/giallozafferano/`.

**Le fixture sono ridotte, e il perché sta scritto dentro ognuna.** Il repository è
pubblico: salvare tre pagine intere significherebbe ripubblicare i loro articoli,
che è esattamente ciò che §3 promette di non fare. Quindi la struttura attorno alle
parti che il parser legge è conservata alla lettera — il blocco JSON-LD, il `dl`
degli ingredienti, le intestazioni dei gruppi — e la prosa lunga dei passaggi è
accorciata a una frase per passo, mantenendo i rimandi fotografici perché sono ciò
che il pulitore deve togliere. Tre fixture:

1. una ricetta semplice, ingredienti senza gruppi;
2. una con i gruppi, lo stesso termine due volte e le entità HTML;
3. una pagina senza JSON-LD utilizzabile.

Cosa difende ogni test:

| Oggetto | Garanzia |
|---|---|
| `parse_recipe` | titolo, dosi, tempi, categoria, foto, termini con chiave e quantità, dalle fixture vere |
| `parse_recipe` | le tre forme di `recipeInstructions`, e `recipeYield` intero o stringa |
| `parse_recipe` | una pagina inutilizzabile solleva `UnparsablePage` con un motivo leggibile |
| `clean_instructions` | tavola di casi, compresi quelli che **non** devono cambiare |
| `match_name` | nome esatto e alias esatto sono certi; somiglianza è incerta; niente è niente |
| `default_role` | tavola su tutte e dodici le categorie, per entrambe le forme di quantità |
| registro dei termini | un termine nuovo che coincide con un alias nasce già deciso |
| `occurrences` | ricalcolato, non incrementato: due scarichi della stessa pagina non lo raddoppiano |
| decisione `map` | scrive l'alias, materializza le ricette pronte, riporta quante |
| decisione `ignore` | la ricetta entra senza quella riga, e non si scarta |
| materializzazione | collasso dei duplicati: una riga per ingrediente, ruolo più forte, quantità unite |
| materializzazione | una ricetta che resterebbe senza righe si scarta con motivo |
| materializzazione | una ricetta cancellata dall'utente non viene ricreata |
| vincolo di `import_terms` | `mapped` senza ingrediente è rifiutato dal database |
| ricerca | con più ricette della piscina, `only_cookable` le vede tutte |
| `reindex` | scrive i vettori mancanti e lascia in pace quelli presenti |
| coda (frontend) | un termine mostra proposta, ricette in attesa e tre azioni |
| coda (frontend) | Claude non disponibile: la coda funziona e lo dichiara |
| ricettario (frontend) | foto, tempo e filtro per categoria; una ricetta senza foto non si rompe |

I test girano su Postgres vero, avviato da Compose, come tutto il resto.

## 14. Fuori scope, di proposito

- **«Incolla un link».** È il passo successivo dichiarato dall'utente, e riuserà
  `parse_recipe` senza modifiche: il parser non sa da dove arriva l'HTML.
- **Scaricare le fotografie.** Significherebbe copiarsi in casa le loro immagini.
  Si carica l'indirizzo.
- **Colonne per i valori nutrizionali.** La fase 3 li leggerà da `payload`.
- **Riaggiornare una ricetta già importata** quando la pagina cambia.
- **Altre fonti.** La tabella ha la colonna `source` perché il secondo sito non
  deve costare una migrazione, ma il secondo adattatore non si scrive adesso.

## 15. Rischi noti

- **Il loro HTML cambia e il parser si ferma.** Probabile entro un anno. Si scopre
  subito, perché le pagine finiscono in `skipped` con un motivo e il riepilogo le
  conta. Non è silenzioso, ed è tutto ciò che serve.
- **La coda non si esaurisce.** 80 termini su 143 compaiono una volta sola: lotti
  grandi portano molte decisioni rare. È accettato come costo noto, e mitigato
  dall'ordine per frequenza: si può smettere di revisionare in qualsiasi momento e
  le ricette già sbloccate restano.
- **Una mappatura sbagliata avvelena in silenzio.** Collegare `Scorza di limone` a
  `limone` rende cucinabili ricette che chiedono la scorza di un limone non
  trattato. È il rischio che giustifica l'intera coda di revisione, e non si elimina:
  si rende visibile e correggibile.
- **Tocca il cuore della ricerca.** Il §11 modifica `recipe_search.py`, che è il
  modulo più delicato della v1. La difesa è un test che oggi non esiste: più
  ricette della piscina dei candidati.
