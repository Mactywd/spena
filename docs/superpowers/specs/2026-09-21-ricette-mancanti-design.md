# Cerca ricette con al massimo *n* ingredienti mancanti — design

**Data:** 2026-09-21
**Voce dei prossimi passi:** R7
**Documenti d'origine:** `docs/prossimi-passi.md` (R7, e la sesta lezione citata lì),
`CLAUDE.md` (la regola che rende utile `low`, prima e sesta lezione),
`docs/superpowers/specs/2026-09-11-spena-design.md` §7

---

## 1. Il problema

Il ricettario di oggi conosce due risposte alla domanda «cosa cucino»: tutto, oppure
solo quel che si può cucinare adesso. In mezzo non c'è niente, e in mezzo stanno i due
casi veri.

Il primo: **tanto devo andare a fare la spesa**. Se accetto di comprare tre cose, il
ricettario si allarga moltissimo — e oggi per scoprirlo devo togliere il filtro e
guardare a occhio un elenco in cui le ricette a cui manca tutto stanno accanto a
quelle a cui manca il prezzemolo.

Il secondo: lo **svuotafrigo**. Parto da quel che devo consumare, e allargo di poco.

Il dato per rispondere c'è già: `RecipeSearchResult` porta `missing` per ogni ricetta
e l'elenco è già ordinato per mancanti crescenti. Quel che manca è un modo di dire
«fermati a *n*», e la casella «Solo quelle che posso cucinare» è già quel controllo
bloccato su zero.

## 2. Le cinque decisioni prese

Prese durante il brainstorming del 2026-09-21, e vincolanti per quel che segue.

1. **Un controllo solo, e la casella sparisce.** «Cucinabile» è «zero mancanti»: due
   controlli che dicono la stessa cosa con due nomi diversi possono contraddirsi, e
   uno dei due sarebbe sempre quello sbagliato da guardare. La casella diventa il
   gradino zero di una scala.
2. **La scheda del ricettario elenca i mancanti.** Con la soglia a zero il conteggio
   bastava; con la soglia a due la domanda diventa «vale la pena comprarli?», e un
   numero non ci risponde. I nomi sì.
3. **Lo svuotafrigo è la combinazione dei filtri, non una modalità.** Si scelgono gli
   avanzi in «Contiene ingredienti» e si alza la soglia. L'AND del filtro per
   ingrediente resta com'è stato deciso il 2026-09-17.
4. **La scala è fissa a cinque gradini** — Tutte, Ora, +1, +2, +3 — perché oltre i tre
   mancanti un filtro sui mancanti non filtra più niente.
5. **`only_cookable` resta accettato dall'API** come sinonimo di `max_missing=0`.

## 3. La regola sta nel dominio, e generalizza quella che c'è

`app/domain/rules.py` ha già il conteggio e il verdetto, e il secondo è il primo
confrontato con zero. R7 non aggiunge una regola: allarga quella soglia da fissa a
parametrica.

```python
def within_budget(
    requirements: Iterable[tuple[IngredientRole, Availability]], budget: int
) -> bool:
    """Se quel che manca sta dentro quanto si è disposti a comprare.

    `is_cookable` è il caso `budget = 0` e resta scritto così: «cucinabile» è una
    parola sola in tutta l'app, e il giorno in cui la regola di `is_satisfied`
    cambiasse, le due risposte non potrebbero divergere perché sono la stessa
    funzione.
    """
    return missing_count(requirements) <= budget


def is_cookable(requirements: Iterable[tuple[IngredientRole, Availability]]) -> bool:
    return within_budget(requirements, 0)
```

Il ruolo continua a decidere cosa conta come mancante: un principale «quasi finito»
manca, un secondario «quasi finito» no. La soglia si applica **dopo** quella regola,
non al posto suo — «al massimo due mancanti» vuol dire due cose da comprare davvero,
non due righe gialle.

**L'alternativa scartata: il conteggio in SQL.** Reggerebbe il catalogo intero dopo
R4, ma richiederebbe una seconda scrittura di `is_satisfied` come espressione SQL,
che nessun test del dominio esercita — la prima lezione di `CLAUDE.md`, presa
apposta. Il punto di rimisura è già dichiarato nel commento di `recipe_search.py`
(«oltre qualche migliaio va misurata di nuovo, e se non regge la regola scende in
SQL»): R7 lo eredita senza spostarlo, e con il vincolo attivo delle ~100 ricette non
lo tocca nemmeno da lontano.

## 4. Il servizio, e la trappola del limite

`search_recipes` perde `only_cookable` e prende `max_missing: int | None`. `None` vuol
dire «Tutte».

```python
async def search_recipes(
    session: AsyncSession,
    query: str | None = None,
    max_missing: int | None = None,
    limit: int = 30,
    category: str | None = None,
    ingredient_ids: list[uuid.UUID] | None = None,
) -> list[RecipeSearchResult]:
```

e in fondo, al posto del filtro su `cookable`:

```python
if max_missing is not None:
    results = [r for r in results if r.missing <= max_missing]
```

`r.missing` è già calcolato da `missing_count`: il confronto non ricopia nessuna
regola, la legge.

### 4.1 Il limite, che è il punto di tutto il lavoro

Sul ramo senza parole cercate, oggi, `only_cookable` **toglie** il
`limit(CANDIDATE_POOL)`, con un commento che spiega perché. `max_missing` è lo stesso
filtro con un'altra soglia, quindi la condizione diventa:

```python
# Vale per qualunque soglia, zero compreso: il filtro lavora sul risultato, quindi
# limitare prima significa filtrare dentro un campione, e «cosa posso cucinare se
# compro due cose» risponderebbe guardando solo le cento ricette entrate ieri.
if max_missing is None:
    statement = statement.limit(CANDIDATE_POOL)
```

Il commento lungo che sta lì oggi si aggiorna per nominare la soglia invece della
cucinabilità, e resta dov'è.

Sul ramo **con** parole cercate il limite resta, e resta il limite dichiarato nel
commento che c'è già accanto al filtro per ingrediente: fra le ricette che parlano di
quelle parole, quelle a cui manca poco. Non è la sesta lezione — lì il filtro era
l'unico criterio e la piscina un taglio arbitrario; qui le parole cercate *sono* un
ordinamento, e la domanda è sul risultato della ricerca. Ma è una scelta, non un
fatto provato, e adesso vale per un filtro in più: va scritta nel commento.

### 4.2 L'ordinamento non cambia

`results.sort(key=lambda r: (r.missing, -r.score, r.recipe.title))` è già quel che
serve: con la soglia a 3, le cucinabili restano in cima da sole, poi quelle a cui
manca una cosa, e così via. Lo svuotafrigo ottiene gratis l'ordine che vuole.

### 4.3 I nomi dei mancanti

`_requirements_by_recipe` oggi butta via l'identità dell'ingrediente e tiene solo la
coppia `(ruolo, disponibilità)`. Per elencare i mancanti deve portarsi dietro il
nome, con una join invece di una seconda query:

```python
statement = (
    select(
        RecipeIngredient.recipe_id,
        RecipeIngredient.ingredient_id,
        RecipeIngredient.role,
        Ingredient.display_name,
    )
    .join(Ingredient, Ingredient.id == RecipeIngredient.ingredient_id)
    .where(RecipeIngredient.recipe_id.in_(recipe_ids))
)
```

e restituisce `dict[uuid.UUID, list[RecipeRequirement]]`, con

```python
@dataclass(frozen=True)
class RecipeRequirement:
    name: str
    role: IngredientRole
    availability: Availability
```

Le funzioni del dominio continuano a ricevere coppie — `[(r.role, r.availability) for
r in reqs]` — perché `rules.py` è puro e non conosce questa dataclass. Chi manca lo
decide `is_satisfied`, la stessa funzione che usa la rotta di dettaglio, riga per
riga: non esiste un secondo giudizio su cosa sia mancante.

**I nomi si ordinano alfabeticamente.** `recipe_ingredients` non ha una colonna di
posizione, quindi senza un criterio esplicito due richieste identiche potrebbero
elencare gli stessi mancanti in ordine diverso — è la lezione del `Recipe.id.desc()`
come spareggio, applicata a una lista invece che a una piscina.

`RecipeSearchResult` guadagna `missing_names: list[str]`.

## 5. La rotta e lo schema

```python
@router.get("/search", response_model=list[RecipeSummaryOut])
async def search(
    q: str | None = None,
    max_missing: int | None = Query(default=None, ge=0),
    # Sinonimo di `max_missing=0`, e non un residuo da togliere alla prossima
    # occasione. Il service worker della PWA può servire per giorni una copia
    # vecchia dello schermo, che manda ancora questo parametro: ignorarlo
    # significherebbe mostrarle il ricettario intero sotto l'etichetta di un filtro
    # che sembra acceso — lo stesso guasto silenzioso che il commento su
    # `ingredient_id` qui sotto esiste per evitare. `max_missing` ha la precedenza:
    # se arrivano entrambi, vince quello esplicito.
    only_cookable: bool = False,
    ...
):
    budget = max_missing if max_missing is not None else (0 if only_cookable else None)
```

La chiamata al servizio passa la soglia **per nome**, `max_missing=budget`. Il terzo
argomento posizionale era un `bool` e diventa un `int | None`: in Python `True == 1`,
quindi un `only_cookable` rimasto in una chiamata posizionale diventerebbe
silenziosamente «al massimo un mancante» invece di «cucinabili», e nessun tipo lo
fermerebbe.

Nessun tetto superiore su `max_missing` lato API: il tetto è la scala a schermo, e un
valore più alto scritto a mano è una domanda legittima a cui il servizio sa
rispondere. `ge=0` perché una soglia negativa non vuol dire niente.

### 5.1 `missing_names` va su tutte e due le risposte

`RecipeSummaryOut` guadagna `missing_names: list[str] = []`, e **anche `RecipeOut`**,
che oggi non eredita da lei.

La ragione è nel frontend: `RecipeDetail extends RecipeSummary`. Un campo aggiunto
solo alla scheda riassuntiva diventerebbe obbligatorio anche sul dettaglio, che non
lo manderebbe — e `tsc` lo direbbe solo a `npm run build`, cioè la settima lezione di
`CLAUDE.md` rifatta con lo stesso identico tipo. Mandarlo da entrambe le rotte tiene
una forma sola. Sul dettaglio è ridondante — le righe portano già `availability` e
`satisfied`, e nessuna schermata lo legge — e va scritto nel commento che è così di
proposito.

In `_to_out` costa due righe: il ciclo che costruisce `requirements` ha già
`ri.ingredient.display_name` e il verdetto `is_satisfied` sotto mano.

Nessuna migrazione: R7 non tocca lo schema del database.

## 6. L'interfaccia

### 6.1 La scala

Un componente nuovo, `frontend/src/features/recipes/MissingBudgetFilter.tsx`. **Non**
in `components/ui/`: serve in un posto solo, e se un giorno nasce una seconda scala si
sposta allora.

Cinque gradini, in una fila che entra in 375px:

| Pastiglia | `maxMissing` | La riga sotto |
|---|---|---|
| Tutte | `null` | «Tutto il ricettario.» |
| Ora | `0` | «Solo quelle che puoi cucinare adesso.» |
| +1 | `1` | «Al massimo 1 ingrediente da comprare.» |
| +2 | `2` | «Al massimo 2 ingredienti da comprare.» |
| +3 | `3` | «Al massimo 3 ingredienti da comprare.» |

«+1» da solo non dice niente: è la riga sotto a dire cosa si sta guardando, e cambia
con la scelta.

**Radio veri, non bottoni con `aria-checked`.** Ogni gradino è un `<input
type="radio">` in classe `sr-only` dentro la sua `<label>`, e la pastiglia è lo `span`
accanto, colorato con `peer-checked:`. Si ottengono gratis la selezione singola, la
navigazione da tastiera e il nome accessibile; e i test trovano
`getByRole("radio", { name: "Al massimo 2 ingredienti da comprare" })` senza sapere
niente di come è disegnato. Il gruppo sta in un `<fieldset>` con una `<legend>`
`sr-only` — «Quanto posso comprare» — perché cinque radio senza gruppo, letti a voce,
sono cinque scelte senza domanda.

Solo token esistenti: la pastiglia scelta è `bg-brand` con testo bianco, come il resto
dell'app. R7 non chiede nessun colore nuovo.

Il valore di partenza è `null`, cioè quel che il ricettario mostra oggi aprendosi.

### 6.2 Quel che sparisce, e quel che cambia intorno

La casella «Solo quelle che posso cucinare» viene tolta, e con lei lo stato
`onlyCookable` dello schermo. La chiave di react-query diventa `["recipes",
debouncedQuery, maxMissing, category, ingredientIds]`.

`searchRecipes` in `api.ts` cambia il parametro per nome — `maxMissing?: number |
null` al posto di `onlyCookable` — e lo scrive solo quando non è `null`.

`emptyMessage` **non** guadagna un quarto asse combinatorio. Oggi `onlyCookable`
compare in ogni ramo come frammento fisso («fra quelle che puoi cucinare adesso»):
basta sostituire quel frammento con uno che sa dire anche «fra quelle a cui manca al
massimo 1 ingrediente», e i rami restano quattro. Il ramo in cui la soglia è l'unico
filtro acceso dice la via d'uscita giusta, che è alzarla:

> «Niente che tu possa cucinare comprando al massimo 2 cose: alza la soglia, o scegli
> «Tutte» per vedere il resto del ricettario.»

### 6.3 La scheda

`RecipeCard` tiene la pastiglia com'è — «Puoi cucinarla ora» continua a rispondere a
`cookable` e non a `missing === 0`, per la ragione scritta nel suo commento — e sotto,
quando `missing_names` non è vuoto, una riga `text-xs text-ink-faint` con i nomi
separati da virgola. Niente «mancano» ripetuto: la pastiglia lo ha appena detto.

Al massimo tre nomi, poi «e altri N». Con il filtro acceso non si tronca mai — la
soglia è al massimo 3 — e si tronca solo su «Tutte», dove una ricetta può mancarne
dodici e la riga diventerebbe più lunga del titolo. Il taglio lo fa il client, che è
dove si sa quanto spazio c'è; il server manda la lista intera.

## 7. Le prove

**a. Un ricettario più grande della piscina, per una soglia diversa da zero.** Il
caso zero è già difeso: `test_solo_cucinabili_vede_oltre_la_piscina_dei_candidati`
semina `CANDIDATE_POOL + 6` ricette con la cucinabile indiscutibilmente la più
vecchia, e pretende di vederla. Quel test resta, e diventa il test del gradino
«Ora»: cambia solo la chiamata, perché interroga il servizio e non la rotta, e il
sinonimo `only_cookable` vive nella rotta.

Quel che manca è il suo gemello per una soglia maggiore di zero: stessa semina, ma la
ricetta più vecchia ha **un solo** ingrediente mancante e si chiede `max_missing=1`.
I due test insieme chiudono la condizione da entrambi i lati, ed è il punto: scritta
`if not max_missing` invece di `if max_missing is None`, la soglia zero ricadrebbe
sotto il limite e il test che esiste lo direbbe; scritta `if max_missing == 0`, sarebbe
la soglia 1 a caderci, e solo il test nuovo lo direbbe.

Il vincolo delle ~100 ricette riguarda la produzione e il suo storage, non una
transazione di prova che si annulla.

**b. La tabella del dominio, allargata ai budget.** `within_budget` su ogni
combinazione di ruolo e disponibilità per budget 0, 1, 2, 3 — e l'identità
`is_cookable(reqs) == within_budget(reqs, 0)` asserita, non data per buona.

**c. Il sinonimo e la precedenza.** `only_cookable=true` da solo filtra come
`max_missing=0`; con `max_missing=2` insieme, vince il 2.

**d. I nomi.** Una ricetta con due mancanti e un secondario «quasi finito» che non
manca: `missing_names` ne contiene due, non tre, e in ordine alfabetico.

**e. Lo schermo.** Scegliere «+2» manda `max_missing=2`; il gradino «Ora» manda
`max_missing=0` e non `only_cookable`; la scheda elenca i nomi e tronca al quarto.

**f. In un browser vero, una riga sola.** La quarta lezione: la pastiglia scelta si
distingue da quelle non scelte solo per il CSS, e jsdom non lo calcola. Una
asserzione in `frontend/e2e/style.spec.ts` — il gradino scelto ha un fondo diverso
dagli altri, e il suo testo sta sopra 4.5:1 su quel fondo. Non apre la Parte IX dei
prossimi passi: è una riga dentro il file che già esiste.

## 8. Fuori ambito, e perché

- **Un tasto «aggiungi i mancanti alla lista».** Chiuderebbe il giro sul caso «tanto
  devo fare la spesa», ed è la cosa più tentante qui dentro. È una funzione sua: tocca
  la Lista, i duplicati con quel che c'è già, e l'annulla. R7 elenca i mancanti; non
  li compra.
- **Ordinare per quanti avanzi una ricetta consuma.** Sarebbe un terzo criterio
  accanto a RRF e al conteggio dei mancanti. Lo svuotafrigo è servito
  dall'ordinamento che c'è.
- **AND/OR sul filtro per ingrediente.** Riaprirebbe una decisione del 2026-09-17 che
  ha una ragione scritta.
- **Il conteggio dei mancanti in SQL.** Vedi §3.
- **L'`retry: false` degli undici test di schermata.** Difetto vero e preesistente,
  con una voce sua in `prossimi-passi.md`. I test nuovi di questo lavoro non lo
  allargano: usano il client di produzione.

## 9. Cosa va aggiornato quando questo lavora

- **`docs/prossimi-passi.md`**: R7 da `[D]` a fatto, con la data; e la riga di R6
  («filtra per cucinabili con sostituti») va riletta, perché adesso «cucinabile» è un
  gradino di una scala e non una casella.
- **`README.md`** se nomina la casella del ricettario.
- Niente da emendare in `CLAUDE.md` né nella spec madre: R7 non tocca nessuna delle
  due decisioni fondanti, e la regola primario/secondario resta esattamente dov'è.
