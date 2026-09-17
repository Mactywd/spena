# I non alimentari in lista e in dispensa — design

**Data:** 2026-09-17
**Voci dei prossimi passi:** D4 (la decisione) e S5 (il lavoro)
**Documenti d'origine:** `docs/prossimi-passi.md` (D4, S5), `CLAUDE.md` (decisione
fondante 2), `docs/superpowers/specs/2026-09-11-spena-design.md` §2

---

## 1. Il problema

Detersivo e carta igienica si comprano insieme al cibo e devono stare nella stessa
lista. Oggi **una parte del giro funziona già**: scrivi «detersivo» nel campo della
lista e la voce entra come testo libero, senza ingrediente abbinato, e finisce nel
gruppo «senza reparto» in fondo.

Quello che non funziona è il resto del giro. Per portare quella voce **in dispensa**
serve un ingrediente in anagrafica, e l'unica strada che ce l'ha — la sistemazione
della spesa — lo crea d'ufficio nel reparto «altro». Da quel momento il detersivo
vive nel mondo del cibo: esce nell'autocomplete quando scrivi una ricetta, è
selezionabile nel filtro «Contiene ingredienti» del ricettario, il revisore
dell'import ci può mappare sopra un termine di GialloZafferano, e un domani la
nutrizione proverà a dargli dei valori.

Il lavoro non è «permettere i non alimentari»: è **separarli dal mondo del cibo senza
separarli dalla lista**.

## 2. Le tre decisioni prese

Prese durante il brainstorming del 2026-09-17, e vincolanti per quel che segue.

1. **Due assi, non uno.** Un campo `kind` (`food` | `non_food`) porta le regole, e
   `category` resta il reparto del supermercato, con valori nuovi riservati ai non
   alimentari. «Non è cibo» e «in che corsia sta» restano due domande separate, come
   sono nella realtà.
2. **Seme più scelta del reparto.** Un elenco di non alimentari entra nel seme, così
   l'autocomplete li trova dal primo giorno; e per tutto il resto, la sistemazione
   della spesa smette di creare l'ingrediente d'ufficio in «altro» e **chiede il
   reparto**. Il `kind` discende dal reparto: non lo si sceglie due volte.
3. **Un non alimentare può avere un prodotto, mai dei nutrienti.** Marca e codice a
   barre sì, come per il cibo. I quattro campi nutrizionali spariscono dal modulo, e
   `products.nutrients` resta NULL per sempre: assenza, non zero.

## 3. Il modello

### 3.1 La colonna `kind`

`ingredients` guadagna una colonna:

```python
kind: Mapped[str] = mapped_column(String(10), nullable=False)
```

con un `IngredientKind(StrEnum)` dichiarato in **`app/domain/rules.py`**, accanto a
`PantryStatus` e `IngredientRole`:

```python
class IngredientKind(StrEnum):
    FOOD = "food"
    NON_FOOD = "non_food"
```

Nel dominio e non accanto a `IngredientCategory` nel modello, benché sia la sua
proiezione: `rules.py` è un modulo puro che **dichiara** i propri enum e da cui
importano modelli, schemi e servizi; la direzione opposta farebbe dipendere il
dominio dalle tabelle. `IngredientCategory` resta dov'è — è una classificazione di
dati, non una regola — ed è per questo che `kind_for_category` prende una stringa.

`String(10)` e non un tipo enum di Postgres, per coerenza con `category`, che è già
una `String(20)`: i valori vivono in Python e il database conserva la stringa.

### 3.2 I due reparti nuovi

`IngredientCategory` guadagna due valori:

```python
    CASA = "casa"        # detersivi, spugne, sacchi, carta da cucina
    IGIENE = "igiene"    # carta igienica, sapone, dentifricio
```

**Nessuna migrazione di schema per questo**: `category` è una `String(20)`, non un
tipo enum del database, quindi i valori nuovi entrano senza toccare Postgres.

Fermo a due. `animali` e qualunque altro reparto sono un valore di enum e una riga di
partizione di distanza, e inventarli prima di sapere se servono è inventare.

### 3.3 `kind` non lo scrive il client: discende dal reparto

In `app/domain/rules.py`, accanto a `status_for_fill` e a `default_role`, una funzione
pura:

```python
# I reparti che non sono cibo. La partizione è dichiarata su questa metà e non
# sull'altra perché è la metà che cresce: un reparto alimentare nuovo è cibo per
# omissione, ed è la risposta giusta.
NON_FOOD_CATEGORIES = frozenset({"casa", "igiene"})


def kind_for_category(category: str) -> IngredientKind:
    """A quale mondo appartiene una voce, dedotto dalla sua corsia.

    Il reparto lo sceglie la persona; questo asse discende, e non si può quindi
    creare una riga che dice «igiene» e insieme «è cibo». Stessa forma di
    `status_for_fill`: là una posizione del cursore si proietta nei tre stati su
    cui ragiona il resto dell'app, qui una corsia del supermercato si proietta
    nell'asse su cui ragionano le guardie.
    """
    return IngredientKind.NON_FOOD if category in NON_FOOD_CATEGORIES else IngredientKind.FOOD
```

`NON_FOOD_CATEGORIES` è un insieme di **stringhe**, come `SECONDARY_CATEGORIES` due
funzioni più in là, e per la stessa ragione: questo modulo non importa i modelli
delle tabelle, quindi non può nominare i valori dell'enum. È il test della partizione
(prova 2 del §7) a tenerlo agganciato a `IngredientCategory`, esattamente come già succede per
le categorie secondarie.

**L'unico scrittore è `create_ingredient`** in `app/repositories/ingredients.py`:

```python
async def create_ingredient(
    session: AsyncSession, name: str, display_name: str, category: str
) -> Ingredient:
    ingredient = Ingredient(
        name=name.strip().lower(), display_name=display_name.strip(),
        category=category, kind=kind_for_category(category),
    )
```

La firma **non cambia** e `IngredientCreate` **non guadagna un campo**: nessun
chiamante, nemmeno l'API, può dichiarare il `kind` di una voce.

### 3.4 Perché memorizzare una colonna derivabile

Perché le guardie e i filtri sono SQL. `WHERE kind = 'food'` sta in un posto; la sua
alternativa è la partizione dei reparti ricopiata dentro ogni query che deve
escludere i non alimentari — cioè la sesta lezione di `CLAUDE.md` girata al
contrario, con il difetto che compare quando si aggiunge il terzo reparto e qualcuno
aggiorna tre query su quattro.

La colonna è una **proiezione**, non una seconda verità: la sorgente resta
`category`, e `kind_for_category` è l'unico posto che le mette in relazione.

## 4. Le guardie

Cinque, e vale la pena dire di ciascuna **dove** sta e **perché lì**.

### 4.1 Una ricetta non può puntare a un non alimentare

Sta dentro **`create_recipe`** (`app/repositories/recipes.py`), che è l'unico posto
del progetto che costruisce un `RecipeIngredient` e ha tre chiamanti: l'API delle
ricette, la materializzazione dell'import, il seme.

Il buco vero non è dove sembra. La strada «crea per nome» di `api/recipes.py` non
*creerebbe* mai un non alimentare, perché crea sempre con una categoria alimentare;
ma `match_name` può **agganciare un non alimentare esistente** — basta che una riga
di ricetta dica «sapone», e l'alias lo trova. Una guardia scritta nell'API lascerebbe
scoperti gli altri due chiamanti; nell'imbuto li copre tutti e tre.

```python
class NonFoodInRecipe(Exception):
    """Una riga di ricetta punta a una voce non alimentare.

    Porta il nome della voce perché il messaggio all'utente deve dire quale, non
    solo che ce n'è una.
    """

    def __init__(self, display_name: str) -> None:
        super().__init__(display_name)
        self.display_name = display_name
```

`create_recipe` verifica in una query sola — `SELECT display_name FROM ingredients
WHERE id IN (...) AND kind = 'non_food' LIMIT 1` — e solleva prima di scrivere
qualsiasi riga.

`app/api/recipes.py` la traduce in **422**:

> «Sapone per le mani» non è un alimento: una ricetta non può averlo fra gli
> ingredienti. Toglilo dalla riga, poi salva.

**L'eccezione deve urlare, non saltare la riga.** Se le guardie 4.3 e 4.4 tengono,
questa non è raggiungibile dalla materializzazione dell'import né dal seme: è
l'ultima linea, e una che si raggiunge solo perché una guardia a monte ha un buco.
Una materializzazione che saltasse in silenzio la riga produrrebbe una ricetta
mutilata che nessuno ha chiesto.

### 4.2 La nutrizione lo ignora

`CustomProductForm` (frontend) non mostra i quattro campi (`kcal`, `protein`,
`carbs`, `fat`) quando la voce è non alimentare, e non invia `nutrients`. La colonna
resta NULL: la convenzione «un nutriente assente resta assente, mai zero» è già
scritta e già rispettata nel modulo, e qui vale per tutti e quattro insieme.

Open Food Facts si interroga lo stesso (decisione 3): sui non alimentari trova di
rado, e quando non trova nulla la strada cade già oggi sull'inserimento a mano, che
qui è il caso normale.

### 4.3 L'AI dell'import non ne crea mai

`app/services/recipe_import/decide.py` costruisce oggi:

```python
CATEGORIES = frozenset(str(value) for value in IngredientCategory)
```

cioè l'enum intero, e lo usa in due punti: le `"categorie"` offerte al modello nel
prompt (riga 124) e la validazione della risposta (riga 213). Aggiungendo `casa` e
`igiene` all'enum, **senza toccare nulla** un termine di GialloZafferano potrebbe
essere classificato «igiene» e nascere come voce non alimentare.

Diventa:

```python
# Solo alimentari: questo modulo decide i termini di un ricettario, e una voce
# non alimentare qui sarebbe un ingrediente che nessuna ricetta potrà usare
# (vedi la guardia in create_recipe). L'elenco si restringe qui e non nel
# prompt, così l'offerta al modello e il controllo della risposta restano la
# stessa cosa: due elenchi si scollerebbero, e a scollarsi per prima sarebbe
# la validazione.
CATEGORIES = frozenset(
    str(value) for value in IngredientCategory
    if kind_for_category(str(value)) is IngredientKind.FOOD
)
```

Una risposta che propone una categoria fuori elenco è già rifiutata dal controllo
esistente alla riga 213, e **il termine resta in coda** — che è la regola della casa:
una risposta che non si può verificare non si applica.

### 4.4 La decisione umana della coda non ne aggancia mai

Nella coda dell'import il revisore può `map`pare un termine su **qualunque**
ingrediente esistente, «sapone» compreso, o `create`arne uno con **qualunque**
categoria dell'enum (`app/api/imports.py`, rotta della decisione).

La guardia 4.1 lo prenderebbe, ma **tardi e male**: la rotta chiama
`materialize_ready` nella stessa richiesta, e quel ciclo non protegge le singole
ricette — una sola riga non alimentare farebbe fallire la materializzazione di tutto
il lotto pronto, non solo della ricetta colpevole, dopo che la decisione è già stata
scritta. Un rifiuto a fine lotto è il vicolo cieco peggiore di tutti.

Quindi la rotta rifiuta **al momento della scelta**, con 422:

- `action="map"` verso una voce con `kind == non_food` →
  «Sapone per le mani» non è un alimento: un termine di ricetta non può collegarsi a
  una voce non alimentare. Scegline un'altra, oppure ignora il termine.
- `action="create"` con `category` in `NON_FOOD_CATEGORIES` →
  «Igiene» non è un reparto alimentare: un termine di ricetta non può creare una voce
  non alimentare.

Entrambi i messaggi lasciano una via d'uscita nominata, come vuole la convenzione
«mai un vicolo cieco»: qui l'uscita è *ignora il termine*, che è l'azione giusta per
un termine che non è cibo.

### 4.5 I selettori del mondo ricette non lo offrono

`search_ingredients` (`app/repositories/ingredients.py`) guadagna un parametro:

```python
async def search_ingredients(
    session: AsyncSession, query: str, limit: int = 10,
    kind: IngredientKind | None = None,
) -> list[Ingredient]:
```

`None` significa «tutti» e resta il comportamento di oggi. La rotta
`GET /api/v1/ingredients/search` guadagna `?kind=food`, e **lo passano solo i
chiamanti del mondo ricette**:

| chiamante | filtro | perché |
|---|---|---|
| lista della spesa (`AddItemField`) | nessuno | il detersivo si scrive in lista |
| sistemazione della spesa (`MatchIngredientField`) | nessuno | il detersivo entra in dispensa |
| dispensa (`IngredientPicker`, «Aggiungi in dispensa») | nessuno | idem |
| ricettario («Contiene ingredienti») | `food` | filtrare per «sapone» non darebbe mai niente |
| bozza AI (`IngredientPicker` delle righe) | `food` | la guardia 4.1 lo rifiuterebbe al salvataggio |
| coda dell'import (`TermCard`, «Collega a un altro ingrediente») | `food` | la guardia 4.4 lo rifiuterebbe alla decisione |

`CatalogSearchPanel`, nella stessa schermata, non compare nella tabella perché cerca
**prodotti** e non ingredienti: un prodotto non alimentare è legittimo (decisione 3)
e non va filtrato.

Questa **non è la guardia che tiene** — quella è la 4.1 — è quella che evita di far
sbattere l'utente contro un rifiuto evitabile.

## 5. L'interfaccia

### 5.1 Il seme dei non alimentari

Diciotto voci in coda a `data/ingredients_seed.json`, nella stessa forma delle 169
esistenti. Gli alias sono la parte che fa lavorare l'autocomplete e vanno scelti come
si scrive davvero sulla lista:

| name | display_name | category | aliases |
|---|---|---|---|
| carta igienica | Carta igienica | igiene | carta igenica, rotoloni |
| fazzoletti di carta | Fazzoletti di carta | igiene | fazzoletti, fazzolettini |
| sapone per le mani | Sapone per le mani | igiene | sapone, sapone liquido |
| bagnoschiuma | Bagnoschiuma | igiene | docciaschiuma |
| shampoo | Shampoo | igiene | — |
| dentifricio | Dentifricio | igiene | — |
| deodorante | Deodorante | igiene | — |
| detersivo per i piatti | Detersivo per i piatti | casa | detersivo piatti, sapone per i piatti |
| detersivo per la lavatrice | Detersivo per la lavatrice | casa | detersivo lavatrice, detersivo per il bucato |
| ammorbidente | Ammorbidente | casa | — |
| sgrassatore | Sgrassatore | casa | — |
| candeggina | Candeggina | casa | varechina |
| spugne per i piatti | Spugne per i piatti | casa | spugne, spugnette |
| sacchi per la spazzatura | Sacchi per la spazzatura | casa | sacchi spazzatura, sacchetti spazzatura |
| carta da cucina | Carta da cucina | casa | carta assorbente, scottex |
| pellicola trasparente | Pellicola trasparente | casa | pellicola |
| carta stagnola | Carta stagnola | casa | stagnola, carta alluminio |
| carta forno | Carta forno | casa | carta da forno |

«Detersivo» da solo **non è alias di nessuno dei due detersivi**, di proposito: sarebbe
una risposta sola a una domanda ambigua, e l'autocomplete li mostra comunque
entrambi digitando quella parola, perché la ricerca trigram lavora sul nome.

### 5.2 La scelta del reparto quando sistemi la spesa

In `MatchIngredientField` (`frontend/src/features/stocking/StockingScreen.tsx`) la
creazione di un ingrediente da testo libero usa oggi una costante:

```tsx
// il reparto di un ingrediente nato da un testo libero non lo sappiamo, e
// indovinarlo sarebbe una bugia: "altro" è il reparto che la lista mostra in
// fondo, insieme alle altre voci da chiarire
const UNKNOWN_CATEGORY = "altro";
```

Il commento aveva ragione, e la correzione non è indovinare meglio: è **chiedere**.
Il tasto «crea» diventa una scelta del reparto — un `<select>` con i reparti
alimentari e, in un `<optgroup>` staccato in fondo, **Casa** e **Igiene** — e poi la
creazione. Il valore iniziale resta `altro`, così chi non ha voglia di scegliere fa
esattamente quello che fa oggi con un tocco in più; e chi sta mettendo via il
detersivo trova il suo reparto senza aver mai sentito parlare di `kind`.

La domanda è **una sola**: il `kind` non compare da nessuna parte nell'interfaccia.

### 5.3 Lista e dispensa

Non cambiano di meccanica. I non alimentari si raggruppano sotto «casa» e «igiene»
come il resto si raggruppa sotto «verdura» e «latticini», hanno il loro cursore a tre
zone, e quando finiscono tornano in lista con la stessa domanda «Lo rimetto in
lista?» — compreso il giallo, dal 2026-09-17.

La dispensa ha già l'ingresso diretto (`IngredientPicker`, «Aggiungi in dispensa»):
dopo il seme trova il detersivo senza altro lavoro.

**Le parole non cambiano.** La nota D4 nei prossimi passi prevedeva di dire «voce»
invece di «ingrediente» nell'interfaccia. Verificato riga per riga: lista e dispensa
**non dicono mai «ingrediente» all'utente** — tutte le occorrenze visibili stanno nel
mondo delle ricette (bozza AI, coda dell'import, ricettario, foglio della cottura),
dove un non alimentare non arriva mai. Non c'è niente da rinominare, e questa parte
di D4 si chiude senza lavoro.

### 5.4 La conseguenza sul frontend: due elenchi, non uno

`frontend/src/domain/categories.ts` è oggi un elenco solo, e lo usa il `<select>`
della bozza AI per la categoria di un ingrediente **di ricetta**. Aggiungerci
`igiene` significherebbe offrirlo mentre scrivi una ricetta e creare una voce che la
guardia 4.1 rifiuterà un istante dopo.

Si spezza in due costanti esportate — `FOOD_CATEGORIES` e `NON_FOOD_CATEGORIES` —
nello stesso file, con i consumatori così:

- bozza AI: `FOOD_CATEGORIES`
- sistemazione della spesa: le due, con le non alimentari nel loro `<optgroup>`

Il presidio che tiene questo elenco allineato all'enum del backend **esiste già**:
`backend/tests/test_frontend_categories.py` confronta le stringhe del file con
`IngredientCategory`. Va esteso, o smette di dire qualcosa: l'unione delle due
costanti deve essere l'enum intero, e ciascuna metà deve corrispondere alla
partizione di `kind_for_category`. Il test legge oggi tutte le stringhe del file con
una sola espressione regolare; dovrà leggere i due array separatamente.

## 6. La migrazione

Alembic `0007`, una colonna sola:

```python
def upgrade() -> None:
    # server_default per riempire le righe che ci sono — in produzione al
    # 2026-09-17 sono 204, le 169 del seme più quelle create dalle decisioni
    # dell'import, tutte in reparti alimentari — e poi tolto subito: l'unico
    # scrittore deve tornare a essere create_ingredient, e una riga senza kind
    # deve fallire invece di diventare cibo in silenzio.
    op.add_column(
        "ingredients",
        sa.Column("kind", sa.String(length=10), nullable=False, server_default="food"),
    )
    op.alter_column("ingredients", "kind", server_default=None)


def downgrade() -> None:
    op.drop_column("ingredients", "kind")
```

I due reparti nuovi non compaiono qui: `category` è una `String(20)` e i valori
vivono in Python.

## 7. Le prove

Nell'ordine in cui si scrivono, e ciascuna con la modifica di produzione che la fa
fallire se non c'è — perché una prova che non sa dire cosa romperebbe non è una
prova.

**Dominio, per primo** (`backend/tests/domain/`, table-driven, senza database):

1. `kind_for_category` su **ogni** valore di `IngredientCategory`: i dodici
   alimentari danno `FOOD`, `casa` e `igiene` danno `NON_FOOD`.
2. La partizione è **totale**: ogni valore dell'enum sta di qua o di là, e
   `NON_FOOD_CATEGORIES` non contiene nomi che l'enum non ha. Fallisce il giorno in
   cui qualcuno aggiunge un reparto senza decidere da che parte sta — che è
   esattamente il presidio che già protegge `SECONDARY_CATEGORIES`.

**Repository:**

3. `create_ingredient` con `category="igiene"` scrive `kind="non_food"`; con
   `category="verdura"` scrive `kind="food"`. Fallisce se qualcuno toglie la
   derivazione.
4. La guardia dentro `create_recipe`: una ricetta con una riga non alimentare solleva
   `NonFoodInRecipe` e **non scrive niente** — né la ricetta né le righe. Rossa
   prima.

**API:**

5. `POST /api/v1/recipes` con un `ingredient_id` non alimentare → 422, e il messaggio
   nomina la voce.
6. **Il buco vero**: `POST /api/v1/recipes` con una riga che ha solo il *nome*
   «sapone», che l'alias del seme fa agganciare a una voce non alimentare → 422. È il
   caso che oggi passerebbe indisturbato, e quello per cui la guardia sta
   nell'imbuto e non nella rotta.
7. La decisione della coda: `map` su una voce non alimentare → 422; `create` con
   `category="casa"` → 422; e in entrambi i casi **il termine resta in coda** e
   nessuna ricetta viene materializzata.
8. `GET /api/v1/ingredients/search?kind=food` non restituisce il detersivo; senza
   parametro lo restituisce.

**Servizi:**

9. `decide.py`: l'insieme delle categorie offerte al modello e quello usato per
   validare la risposta **non contengono** `casa` e `igiene` — asserito
   sull'insieme vero usato dal codice, non su una copia scritta nel test.
10. Una risposta finta del modello che propone `category="igiene"` viene rifiutata e
    il termine resta in coda.

**Seme:**

11. Le diciotto voci nuove sono valide come le altre (il test
    `test_every_seed_category_is_a_known_one` le copre già una volta aggiunti i due
    reparti all'enum).
12. **Nuovo:** nessun alias del seme è ripetuto fra due voci. È l'invariante che
    `remember_alias` difende a runtime — «un alias già preso da un altro ingrediente
    non si ruba» — ma il seme scrive gli alias direttamente, senza passare di lì, e
    due voci che rispondono alla stessa parola sono un autocomplete che dà due
    risposte a una domanda sola. Vale per tutte le 187 voci, non solo per le nuove.

**Frontend (vitest):**

13. La sistemazione della spesa chiede il reparto prima di creare, e manda quello
    scelto.
14. `CustomProductForm` non mostra i quattro campi nutrizionali per una voce non
    alimentare, e li mostra per una alimentare.
15. Il selettore della dispensa offre il detersivo; quello del ricettario no.

**End-to-end (`frontend/e2e/`), uno solo:** detersivo scritto in lista, sistemato in
dispensa scegliendo il reparto, portato a zero col cursore, e rimesso in lista dalla
domanda. È il giro che questa funzione esiste per rendere possibile, e attraversa
backend e frontend insieme. Niente di nuovo in `style.spec.ts`: l'aspetto non cambia.

## 8. La messa in produzione

1. Deploy normale: `git pull --ff-only` e `docker compose -f docker-compose.prod.yml
   up -d --build --wait`. La migrazione `0007` parte all'avvio del backend come le
   altre.
2. Le diciotto voci arrivano **rieseguendo il seme**, che salta per nome quel che
   c'è già.

Il seme però ricarica anche le **ricette** mancanti per titolo: se nel frattempo ne
fosse stata cancellata una del seme, tornerebbe. Oggi non è successo, ma R4 prevede
proprio di cancellarle, quindi la trappola è a pochi mesi di distanza. Per questo
`app/cli/seed.py` guadagna un `--solo-ingredienti` che carica la sola anagrafica:
cinque righe, e il passo in produzione diventa esatto invece che «esatto se nessuno
ha cancellato niente».

## 9. Fuori ambito, e perché

- **Cambiare il `kind` di una voce esistente.** Non c'è oggi nessuna rotta che
  modifica un ingrediente, quindi il `kind` è immutabile per costruzione. Il giorno
  in cui una nascesse, dovrà rifiutare il passaggio a `non_food` per una voce già
  usata da una ricetta — altrimenti la guardia 4.1 diventa una promessa che vale solo
  al momento della scrittura. Sta scritto qui perché quel giorno si trovi.
- **Un reparto «animali».** Un valore di enum e una riga di partizione. Quando
  servirà.
- **La lista della spesa divisa in due schermate.** La decisione D4 dice
  esplicitamente il contrario: una lista sola, ed è metà del senso di questo lavoro.
- **I nutrienti dei non alimentari.** Mai. Non è una semplificazione temporanea: è la
  decisione 3.
- **S3 (parità dell'ingresso diretto in dispensa) e la scansione dello scontrino.**
  Sono un'altra voce, con una dipendenza che qui non tocchiamo.

## 10. Cosa va emendato quando questo lavora

- **`CLAUDE.md`, decisione fondante 2.** Oggi descrive l'anagrafica come un registro
  di ingredienti alimentari («`yogurt greco` è un ingrediente… le ricette lo
  richiedono»). Va aggiunto che l'anagrafica ospita anche voci non alimentari,
  separate da `kind`, che nessuna ricetta può nominare; e che la regola «le ricette
  puntano solo a ingredienti» resta intatta, perché è proprio quella che la guardia
  in `create_recipe` difende.
- **`docs/prossimi-passi.md`**: D4 e S5 diventano `[FATTO]` con la data, e la nota
  sulle parole («nell'interfaccia, dove serve, si dice "voce"») va corretta in
  «verificato: lista e dispensa non dicono mai "ingrediente", non c'era niente da
  rinominare».
- **La spec madre §2** non va toccata: parla delle quantità, non dei non alimentari.
