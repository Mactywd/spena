# R7 — al massimo *n* ingredienti mancanti: piano di implementazione

> **Per chi lavora con gli agenti:** SOTTO-SKILL RICHIESTA: usare
> `superpowers:subagent-driven-development` (consigliata) o
> `superpowers:executing-plans` per eseguire questo piano un task alla volta. I passi
> usano le caselle (`- [ ]`) per tenere il conto.

**Obiettivo:** sostituire la casella «Solo quelle che posso cucinare» con una scala a
cinque gradini — Tutte, Ora, +1, +2, +3 — che filtra il ricettario per quanti
ingredienti si è disposti a comprare, ed elencare nella scheda quali sono.

**Architettura:** la soglia è una generalizzazione della regola che c'è già:
`is_cookable` diventa `within_budget(reqs, 0)` in `app/domain/rules.py`, e il servizio
di ricerca filtra su `missing <= max_missing`. Il punto delicato è uno solo: essendo un
filtro che lavora sul risultato, `max_missing` deve togliere il `limit(CANDIDATE_POOL)`
esattamente come fa oggi `only_cookable`. Il frontend manda `max_missing` e non calcola
niente.

**Stack:** FastAPI + SQLAlchemy async + Postgres 16 dietro, React 19 + Vite +
TypeScript + Tailwind v4 davanti, pytest e Vitest per i test, Playwright per lo stile.

**Spec:** `docs/superpowers/specs/2026-09-21-ricette-mancanti-design.md`

## Vincoli globali

- **La suite gira sull'host, non in Docker.** Backend: `docker compose up -d db` una
  volta, poi `cd backend && .venv/bin/python -m pytest`. Frontend: `cd frontend && npx
  vitest run`.
- **`tsc --noEmit` non è il type check di questo progetto** (settima lezione di
  `CLAUDE.md`): `frontend/tsconfig.json` è solution-style e non compila niente. Usare
  `npm run typecheck` e `npm run build`.
- **Nessun colore nuovo.** Tutto il colore vive nel blocco `@theme` di
  `frontend/src/index.css`; R7 usa i token che ci sono. Nessuna schermata nomina un
  colore grezzo: `grep -rn "emerald\|neutral-" frontend/src` deve continuare a non
  trovare niente.
- **Nessuna migrazione.** R7 non tocca lo schema del database.
- **Identificatori in inglese, commenti e nomi dei test in italiano**, come nei file
  che si toccano.
- **Mai un vicolo cieco.** Ogni stato dell'elenco vuoto deve dire come uscirne.
- **Niente rete nei test.**

---

### Task 1: `within_budget` nel dominio

**File:**
- Modificare: `backend/app/domain/rules.py:66-70` (`missing_count` e `is_cookable`)
- Test: `backend/tests/domain/test_rules.py`

**Interfacce:**
- Consuma: `missing_count(requirements)`, `is_satisfied(role, availability)`, già presenti.
- Produce: `within_budget(requirements: Iterable[tuple[IngredientRole, Availability]], budget: int) -> bool`,
  importabile da `app.domain.rules`. `is_cookable` conserva firma e comportamento.

- [ ] **Passo 1: scrivere i test che falliscono**

In `backend/tests/domain/test_rules.py`, aggiungere `within_budget` alla riga di import
da `app.domain.rules` e in fondo alla sezione delle regole (dopo
`test_recipe_without_ingredients_is_cookable`, riga 77 circa) aggiungere:

```python
@pytest.mark.parametrize(
    "requirements,budget,expected",
    [
        ([], 0, True),
        ([(PRIMARY, Availability.AVAILABLE)], 0, True),
        ([(PRIMARY, Availability.MISSING)], 0, False),
        ([(PRIMARY, Availability.MISSING)], 1, True),
        # un principale quasi finito manca davvero: la soglia si applica dopo la
        # regola del ruolo, non al posto suo
        ([(PRIMARY, Availability.LOW)], 0, False),
        ([(PRIMARY, Availability.LOW)], 1, True),
        # un secondario quasi finito non manca, quindi non consuma soglia
        ([(SECONDARY, Availability.LOW)], 0, True),
        ([(SECONDARY, Availability.MISSING)], 0, False),
        ([(SECONDARY, Availability.MISSING)], 1, True),
        ([(PRIMARY, Availability.MISSING), (PRIMARY, Availability.LOW)], 1, False),
        ([(PRIMARY, Availability.MISSING), (PRIMARY, Availability.LOW)], 2, True),
        ([(PRIMARY, Availability.MISSING)] * 3, 2, False),
        ([(PRIMARY, Availability.MISSING)] * 3, 3, True),
    ],
)
def test_la_soglia_conta_solo_quel_che_manca_davvero(requirements, budget, expected):
    assert within_budget(requirements, budget) is expected


@pytest.mark.parametrize(
    "requirements",
    [
        [],
        [(PRIMARY, Availability.AVAILABLE)],
        [(PRIMARY, Availability.LOW)],
        [(SECONDARY, Availability.LOW)],
        [(PRIMARY, Availability.MISSING), (SECONDARY, Availability.MISSING)],
    ],
)
def test_cucinabile_e_la_soglia_a_zero(requirements):
    """Non è una coincidenza da controllare a occhio: è la definizione.

    Se un giorno le due risposte divergessero, vorrebbe dire che «cucinabile» è
    tornata a essere una seconda regola scritta altrove — che è il difetto che
    questo lavoro toglie di mezzo.
    """
    assert is_cookable(requirements) is within_budget(requirements, 0)
```

- [ ] **Passo 2: lanciarli e vederli fallire**

```bash
cd backend && .venv/bin/python -m pytest tests/domain/test_rules.py -v
```

Atteso: errore di importazione — `cannot import name 'within_budget' from 'app.domain.rules'`.

- [ ] **Passo 3: scrivere l'implementazione minima**

In `backend/app/domain/rules.py`, sostituire il corpo di `is_cookable` e inserire
`within_budget` prima di lei (subito dopo `missing_count`):

```python
def within_budget(
    requirements: Iterable[tuple[IngredientRole, Availability]], budget: int
) -> bool:
    """Se quel che manca sta dentro quante cose si è disposti a comprare.

    La soglia si applica *dopo* la regola del ruolo, non al posto suo: «al massimo
    due mancanti» vuol dire due cose da comprare davvero, non due righe gialle — un
    secondario quasi finito non manca e non consuma soglia.
    """
    return missing_count(requirements) <= budget


def is_cookable(requirements: Iterable[tuple[IngredientRole, Availability]]) -> bool:
    """Il caso `budget = 0`, e scritto così di proposito.

    «Cucinabile» resta una parola sola in tutta l'app: il giorno in cui la regola di
    `is_satisfied` cambiasse, la risposta al filtro e la risposta alla scheda non
    potrebbero divergere, perché sono la stessa funzione.
    """
    return within_budget(requirements, 0)
```

- [ ] **Passo 4: lanciarli e vederli passare**

```bash
cd backend && .venv/bin/python -m pytest tests/domain/test_rules.py -v
```

Atteso: tutti verdi, compresi i test preesistenti su `missing_count` e `is_cookable`.

- [ ] **Passo 5: commit**

```bash
git add backend/app/domain/rules.py backend/tests/domain/test_rules.py
git commit -m "feat: la cucinabilità diventa il gradino zero di una soglia"
```

---

### Task 2: i nomi di quel che manca, nel servizio di ricerca

**File:**
- Modificare: `backend/app/services/recipe_search.py` (`RecipeSearchResult`,
  `_requirements_by_recipe`, la costruzione dei risultati in fondo a `search_recipes`)
- Test: `backend/tests/services/test_recipe_search.py`

**Interfacce:**
- Consuma: `is_satisfied`, `missing_count`, `is_cookable` da `app.domain.rules`;
  `availability_map` da `app.repositories.pantry`.
- Produce: `RecipeRequirement(name: str, role: IngredientRole, availability: Availability)`
  (dataclass congelata), `missing_names(requirements: Iterable[RecipeRequirement]) -> list[str]`,
  e il campo `RecipeSearchResult.missing_names: list[str]`.

- [ ] **Passo 1: scrivere il test che fallisce**

In fondo a `backend/tests/services/test_recipe_search.py`:

```python
async def test_i_mancanti_si_chiamano_per_nome_e_in_ordine(db_session):
    """Il conteggio dice quante cose mancano, non quali.

    Con la soglia ferma a zero bastava il numero; oltre lo zero la domanda diventa
    «vale la pena comprarle?», e a quella un numero non risponde.

    Il secondario quasi finito non compare: non manca (regola primario/secondario), e
    se comparisse la scheda direbbe di comprare una cosa che c'è.
    """
    from app.db.models.ingredient import Ingredient, IngredientCategory
    from app.db.models.pantry import PantryItem
    from app.repositories.recipes import create_recipe
    from app.services.recipe_search import search_recipes

    pasta = Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
    aglio = Ingredient(name="aglio", display_name="Aglio", category=IngredientCategory.VERDURA)
    bottarga = Ingredient(
        name="bottarga", display_name="Bottarga", category=IngredientCategory.PESCE
    )
    zafferano = Ingredient(
        name="zafferano", display_name="Zafferano", category=IngredientCategory.SPEZIE
    )
    db_session.add_all([pasta, aglio, bottarga, zafferano])
    await db_session.flush()
    db_session.add_all([
        PantryItem(ingredient_id=pasta.id, status="available"),
        PantryItem(ingredient_id=aglio.id, status="low"),
    ])
    await db_session.flush()

    await create_recipe(
        db_session, title="Pasta della domenica", description="Con quel che non ho",
        instructions="Cuoci.", servings=2, source="dataset", source_ref=None,
        ingredients=[
            (pasta.id, "primary", "320 g", None),
            (aglio.id, "secondary", "1 spicchio", None),
            (zafferano.id, "primary", "1 bustina", None),
            (bottarga.id, "primary", "20 g", None),
        ],
        embedding=None,
    )
    await db_session.flush()

    risultati = await search_recipes(db_session)

    assert len(risultati) == 1
    assert risultati[0].missing == 2
    # alfabetico: `recipe_ingredients` non ha una colonna di posizione, e senza un
    # criterio esplicito due letture identiche potrebbero elencarli in ordine diverso
    assert risultati[0].missing_names == ["Bottarga", "Zafferano"]
```

- [ ] **Passo 2: lanciarlo e vederlo fallire**

```bash
docker compose up -d db
cd backend && .venv/bin/python -m pytest tests/services/test_recipe_search.py::test_i_mancanti_si_chiamano_per_nome_e_in_ordine -v
```

Atteso: `AttributeError: 'RecipeSearchResult' object has no attribute 'missing_names'`.

- [ ] **Passo 3: scrivere l'implementazione**

In `backend/app/services/recipe_search.py`:

a) allargare gli import in cima al file:

```python
from collections.abc import Iterable

from app.db.models.ingredient import Ingredient
from app.db.models.recipe import Recipe, RecipeIngredient
from app.domain.rules import (
    Availability,
    IngredientRole,
    is_cookable,
    is_satisfied,
    missing_count,
)
```

b) accanto a `RecipeSearchResult`, che guadagna un campo:

```python
@dataclass(frozen=True)
class RecipeRequirement:
    """Una riga di ricetta ridotta a quel che serve per giudicarla.

    Il nome sta qui dentro e non si va a ripescare dopo: chi manca lo decide
    `is_satisfied` riga per riga, e per dirlo la riga deve sapere come si chiama.
    """

    name: str
    role: IngredientRole
    availability: Availability


@dataclass
class RecipeSearchResult:
    recipe: Recipe
    missing: int
    cookable: bool
    missing_names: list[str]
    score: float


def _pairs(
    requirements: Iterable[RecipeRequirement],
) -> list[tuple[IngredientRole, Availability]]:
    """Le coppie che `rules.py` sa leggere.

    Il dominio è puro e non conosce questa dataclass: la conversione sta qui, in un
    posto solo, invece di far entrare un tipo del servizio dentro il modulo delle
    regole.
    """
    return [(r.role, r.availability) for r in requirements]


def missing_names(requirements: Iterable[RecipeRequirement]) -> list[str]:
    """I nomi di quel che manca, in ordine alfabetico.

    L'ordine non è un vezzo: `recipe_ingredients` non ha una colonna di posizione,
    quindi senza un criterio esplicito due richieste identiche elencherebbero gli
    stessi mancanti in ordine diverso. È lo spareggio di `Recipe.id.desc()` sulla
    piscina dei candidati, applicato a una lista.

    Il giudizio su cosa manchi è `is_satisfied`, la stessa funzione della rotta di
    dettaglio: non esiste un secondo parere su cosa sia mancante.
    """
    return sorted(r.name for r in requirements if not is_satisfied(r.role, r.availability))
```

c) `_requirements_by_recipe` restituisce le dataclass, con una join invece di una
seconda query:

```python
async def _requirements_by_recipe(
    session: AsyncSession, recipe_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[RecipeRequirement]]:
    """Per ogni ricetta, le righe su cui decidono le regole.

    Si ferma qui di proposito: il conteggio dei mancanti e il verdetto di
    cucinabilità sono le funzioni di app/domain/rules.py, non una somma ricopiata
    in questo modulo. Ricalcolarle in linea è la ragione per cui il test a tabella
    difendeva una copia che non girava.
    """
    requirements: dict[uuid.UUID, list[RecipeRequirement]] = {
        recipe_id: [] for recipe_id in recipe_ids
    }
    if not recipe_ids:
        return requirements
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
    rows = (await session.execute(statement)).all()

    availability = await availability_map(session, [row[1] for row in rows])
    for recipe_id, ingredient_id, role, display_name in rows:
        have = availability.get(ingredient_id, Availability.MISSING)
        requirements[recipe_id].append(
            RecipeRequirement(display_name, IngredientRole(role), have)
        )
    return requirements
```

d) in fondo a `search_recipes`, la costruzione dei risultati diventa un ciclo — la
comprensione avrebbe convertito le stesse righe in coppie tre volte:

```python
    results: list[RecipeSearchResult] = []
    for recipe_id in candidate_ids:
        if recipe_id not in recipes:
            continue
        reqs = requirements.get(recipe_id, [])
        pairs = _pairs(reqs)
        results.append(
            RecipeSearchResult(
                recipe=recipes[recipe_id],
                missing=missing_count(pairs),
                cookable=is_cookable(pairs),
                missing_names=missing_names(reqs),
                score=fused.get(recipe_id, 0.0),
            )
        )
```

- [ ] **Passo 4: lanciare tutti i test del servizio**

```bash
cd backend && .venv/bin/python -m pytest tests/services/test_recipe_search.py -v
```

Atteso: verde, compresi i quattro test preesistenti sulla piscina dei candidati.

- [ ] **Passo 5: commit**

```bash
git add backend/app/services/recipe_search.py backend/tests/services/test_recipe_search.py
git commit -m "feat: la ricerca sa anche come si chiama quel che manca"
```

---

### Task 3: `max_missing` nel servizio, e il limite che lo insidia

**File:**
- Modificare: `backend/app/services/recipe_search.py` (firma di `search_recipes`, la
  condizione sul `limit`, il filtro finale, i due commenti lunghi)
- Test: `backend/tests/services/test_recipe_search.py`

**Interfacce:**
- Consuma: `RecipeRequirement`, `missing_names`, `_pairs` dal Task 2.
- Produce: `search_recipes(session, query=None, max_missing=None, limit=30, category=None, ingredient_ids=None)`.
  `only_cookable` **sparisce dal servizio**: il sinonimo vive nella rotta (Task 4).

- [ ] **Passo 1: aggiornare la chiamata del test che esiste, e scrivere il gemello**

In `backend/tests/services/test_recipe_search.py:70`, dentro
`test_solo_cucinabili_vede_oltre_la_piscina_dei_candidati`, la chiamata passa al
parametro nuovo (il test chiama il servizio, non la rotta, e il servizio non conosce
più il sinonimo):

```python
    risultati = await search_recipes(db_session, max_missing=0)
```

Poi, subito sotto quel test, il suo gemello:

```python
async def test_una_soglia_oltre_lo_zero_vede_oltre_la_piscina(db_session):
    """Il gemello del test qui sopra, per una soglia diversa da zero.

    I due insieme chiudono la condizione da entrambi i lati, ed è il punto di tutto
    il lavoro: scritta `if not max_missing` la soglia zero ricadrebbe sotto il limite
    e lo direbbe il test di sopra; scritta `if max_missing == 0` ci cadrebbe la
    soglia uno, e lo dice solo questo.

    Le ricette di scarto ne hanno due di mancanti, non una: devono restare fuori dal
    filtro e non solo in fondo all'ordine.
    """
    from datetime import UTC, datetime, timedelta

    from app.db.models.ingredient import Ingredient, IngredientCategory
    from app.db.models.pantry import PantryItem
    from app.repositories.recipes import create_recipe
    from app.services.recipe_search import CANDIDATE_POOL, search_recipes

    ho = Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
    non_ho = Ingredient(
        name="bottarga", display_name="Bottarga", category=IngredientCategory.PESCE
    )
    nemmeno = Ingredient(
        name="zafferano", display_name="Zafferano", category=IngredientCategory.SPEZIE
    )
    db_session.add_all([ho, non_ho, nemmeno])
    await db_session.flush()
    db_session.add(PantryItem(ingredient_id=ho.id, status="available"))
    await db_session.flush()

    # stessa costruzione del test di sopra: `created_at` assegnato a mano, e quella
    # che ci interessa indiscutibilmente la più vecchia di tutte
    adesso = datetime.now(UTC)
    quasi = await create_recipe(
        db_session, title="Pasta con la bottarga", description="Ne manca una",
        instructions="Cuoci.", servings=2, source="dataset", source_ref=None,
        ingredients=[(ho.id, "primary", "320 g", None), (non_ho.id, "primary", "20 g", None)],
        embedding=None,
    )
    quasi.created_at = adesso - timedelta(seconds=CANDIDATE_POOL + 10)
    for numero in range(CANDIDATE_POOL + 5):
        scarto = await create_recipe(
            db_session, title=f"Introvabile {numero}", description="Ne mancano due",
            instructions="Cuoci.", servings=2, source="dataset", source_ref=None,
            ingredients=[
                (non_ho.id, "primary", "20 g", None),
                (nemmeno.id, "primary", "1 bustina", None),
            ],
            embedding=None,
        )
        scarto.created_at = adesso + timedelta(seconds=numero)
    await db_session.flush()

    risultati = await search_recipes(db_session, max_missing=1)

    assert [r.recipe.title for r in risultati] == ["Pasta con la bottarga"]
```

- [ ] **Passo 2: lanciarli e vederli fallire**

```bash
cd backend && .venv/bin/python -m pytest tests/services/test_recipe_search.py -v -k piscina
```

Atteso: entrambi falliscono con `TypeError: search_recipes() got an unexpected keyword
argument 'max_missing'`.

- [ ] **Passo 3: scrivere l'implementazione**

In `backend/app/services/recipe_search.py`, la firma:

```python
async def search_recipes(
    session: AsyncSession,
    query: str | None = None,
    max_missing: int | None = None,
    limit: int = 30,
    category: str | None = None,
    ingredient_ids: list[uuid.UUID] | None = None,
) -> list[RecipeSearchResult]:
    """`max_missing` è quante cose si è disposti a comprare; `None` è «tutte»."""
```

La condizione sul limite, al posto del blocco `if not only_cookable:`, con il commento
riscritto perché adesso parla di una soglia e non di una casella:

```python
        # Senza soglia la piscina basta: è uno scorrimento, e cento ricette recenti
        # sono più di quante se ne guardino. Con una soglia no — zero compreso: il
        # filtro lavora sul risultato, quindi limitare prima significa filtrare dentro
        # un campione, e «cosa posso cucinare se compro due cose» risponderebbe
        # guardando solo le ricette entrate ieri. `is None` e non la verità: `0` è una
        # soglia, la più stretta, e `if not max_missing` la tratterebbe come la sua
        # assenza. Misurato: a cinquecento ricette la passata completa non si
        # distingue; oltre qualche migliaio va misurata di nuovo, e se non regge la
        # regola scende in SQL.
        if max_missing is None:
            statement = statement.limit(CANDIDATE_POOL)
```

E il filtro finale, al posto di `if only_cookable:`:

```python
    if max_missing is not None:
        # `r.missing` l'ha già contato `missing_count`: questo confronto legge la
        # regola, non la ricopia
        results = [r for r in results if r.missing <= max_missing]
```

Infine, nel commento lungo dentro il ramo con le parole cercate (quello che comincia
con «Qui sta il limite, scritto dove esiste»), aggiungere in fondo:

```python
        # Dal 2026-09-21 lo stesso vale per la soglia dei mancanti: su questo ramo
        # «a cui manca al massimo una cosa» vuol dire «fra le ricette che parlano di
        # queste parole», non «in tutto il ricettario». È la stessa scelta, con lo
        # stesso motivo e lo stesso punto da rimisurare.
```

- [ ] **Passo 4: lanciare tutta la suite del servizio e delle rotte**

```bash
cd backend && .venv/bin/python -m pytest tests/services/test_recipe_search.py tests/api/test_recipes.py -v
```

Atteso: i test del servizio verdi. `tests/api/test_recipes.py` **fallisce** su
`test_only_cookable_filter_hides_the_rest` e sugli altri che passano da `/search`,
perché la rotta passa ancora `only_cookable` posizionalmente: lo chiude il Task 4.
Annotare il fallimento e proseguire.

- [ ] **Passo 5: commit**

```bash
git add backend/app/services/recipe_search.py backend/tests/services/test_recipe_search.py
git commit -m "feat: la ricerca filtra per soglia di mancanti, e la soglia toglie il limite"
```

---

### Task 4: la rotta, il sinonimo, e `missing_names` nelle due risposte

**File:**
- Modificare: `backend/app/api/recipes.py` (la rotta `/search` alla riga 124 circa, e
  `_to_out` alla riga 46 circa)
- Modificare: `backend/app/schemas/recipe.py:60-96` (`RecipeOut` e `RecipeSummaryOut`)
- Test: `backend/tests/api/test_recipes.py`

**Interfacce:**
- Consuma: `search_recipes(..., max_missing=...)` dal Task 3; `is_satisfied` (già
  importata in `api/recipes.py`).
- Produce: il parametro `max_missing` su `GET /api/v1/recipes/search`, il campo
  `missing_names: list[str]` su `RecipeSummaryOut` e su `RecipeOut`.

- [ ] **Passo 1: scrivere i test che falliscono**

In `backend/tests/api/test_recipes.py`, subito dopo
`test_only_cookable_filter_hides_the_rest` (riga 109 circa), che **resta com'è** ed è
adesso il test del sinonimo:

```python
async def test_la_soglia_lascia_passare_chi_manca_di_poco(logged_client, db_session, cucina):
    """«Tanto devo andare a fare la spesa»: con una cosa da comprare l'elenco cambia."""
    await _create_recipe(logged_client, cucina, title="Pasta al pomodoro")
    await _create_recipe(logged_client, cucina, title="Pasta all'aglio",
                         primary=("pasta",), secondary=("aglio",))
    db_session.add_all([
        PantryItem(ingredient_id=cucina["pasta"].id, status=PantryStatus.AVAILABLE),
        PantryItem(ingredient_id=cucina["aglio"].id, status=PantryStatus.AVAILABLE),
    ])
    await db_session.flush()

    body = (await logged_client.get("/api/v1/recipes/search?max_missing=1")).json()

    # «Pasta al pomodoro» ha il pomodoro primario e non in dispensa: ne manca una
    assert [r["title"] for r in body] == ["Pasta all'aglio", "Pasta al pomodoro"]


async def test_la_soglia_esplicita_ha_la_precedenza_sul_sinonimo(
    logged_client, db_session, cucina
):
    """Una copia vecchia dello schermo manda `only_cookable`; una nuova manda
    entrambi solo per sbaglio. Se succede, vince quello che la persona ha scelto.
    """
    await _create_recipe(logged_client, cucina, title="Pasta al pomodoro")
    db_session.add(PantryItem(ingredient_id=cucina["pasta"].id, status=PantryStatus.AVAILABLE))
    await db_session.flush()

    body = (
        await logged_client.get("/api/v1/recipes/search?only_cookable=true&max_missing=1")
    ).json()

    assert [r["title"] for r in body] == ["Pasta al pomodoro"]


async def test_la_scheda_elenca_i_mancanti(logged_client, db_session, cucina):
    await _create_recipe(logged_client, cucina, title="Pasta al pomodoro")
    db_session.add(PantryItem(ingredient_id=cucina["pasta"].id, status=PantryStatus.AVAILABLE))
    await db_session.flush()

    body = (await logged_client.get("/api/v1/recipes/search")).json()

    # l'aglio è secondario e non in dispensa: manca anche lui. Il pomodoro è primario
    assert body[0]["missing_names"] == ["Aglio", "Pomodoro"]


async def test_anche_il_dettaglio_dichiara_i_mancanti(logged_client, db_session, cucina):
    """Ridondante sul dettaglio — le righe portano già `satisfied` — e mandato lo
    stesso: nel frontend `RecipeDetail extends RecipeSummary`, quindi un campo che
    solo una delle due rotte manda è una forma che mente.
    """
    creata = await _create_recipe(logged_client, cucina, title="Pasta al pomodoro")
    db_session.add(PantryItem(ingredient_id=cucina["pasta"].id, status=PantryStatus.AVAILABLE))
    await db_session.flush()

    body = (await logged_client.get(f"/api/v1/recipes/{creata['id']}")).json()

    assert body["missing_names"] == ["Aglio", "Pomodoro"]
```

- [ ] **Passo 2: lanciarli e vederli fallire**

```bash
cd backend && .venv/bin/python -m pytest tests/api/test_recipes.py -v
```

Atteso: i quattro nuovi falliscono (`KeyError: 'missing_names'`, e la soglia ignorata),
e i preesistenti falliscono ancora per il `TypeError` lasciato aperto dal Task 3.

- [ ] **Passo 3: scrivere l'implementazione**

a) in `backend/app/schemas/recipe.py`, aggiungere a **`RecipeOut`** (dopo `cookable`,
riga 70) e a **`RecipeSummaryOut`** (dopo `cookable`, riga 91) la stessa riga:

```python
    # I nomi di quel che manca, in ordine alfabetico. Su RecipeOut è ridondante — le
    # righe portano già `availability` e `satisfied`, e nessuna schermata lo legge —
    # ed è voluto: nel frontend `RecipeDetail extends RecipeSummary`, quindi un campo
    # che solo la scheda riassuntiva manda renderebbe obbligatorio sul dettaglio
    # qualcosa che il dettaglio non manda, e `tsc` lo direbbe solo a `npm run build`.
    missing_names: list[str] = []
```

b) in `backend/app/api/recipes.py`, dentro `_to_out`, raccogliere i nomi nello stesso
ciclo che costruisce le righe. Subito prima del ciclo:

```python
    missing_names: list[str] = []
```

dentro il ciclo, dopo `requirements.append((role, have))`:

```python
        if not is_satisfied(role, have):
            missing_names.append(ri.ingredient.display_name)
```

e nella `RecipeOut(...)` finale, accanto a `missing=` e `cookable=`:

```python
        missing_names=sorted(missing_names),
```

c) la rotta `/search`:

```python
@router.get("/search", response_model=list[RecipeSummaryOut])
async def search(
    q: str | None = None,
    # quante cose si è disposti a comprare; assente vuol dire «tutto il ricettario»
    max_missing: int | None = Query(default=None, ge=0),
    # Sinonimo di `max_missing=0`, e non un residuo da togliere alla prossima
    # occasione. Il service worker della PWA può servire per giorni una copia vecchia
    # dello schermo, che manda ancora questo parametro: ignorarlo significherebbe
    # mostrarle il ricettario intero sotto l'etichetta di un filtro che sembra acceso
    # — lo stesso guasto silenzioso che il commento su `ingredient_id` qui sotto
    # esiste per evitare.
    only_cookable: bool = False,
    category: str | None = None,
    ingredient_id: list[uuid.UUID] = Query(default=[]),
    limit: int = Query(default=30, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[RecipeSummaryOut]:
    # esplicito batte sinonimo: se arrivano entrambi vince quello che la persona ha scelto
    budget = max_missing if max_missing is not None else (0 if only_cookable else None)
    results = await search_recipes(
        session,
        q,
        # per nome, non per posizione: il terzo argomento posizionale era un `bool` e
        # adesso è un `int | None`, e in Python `True == 1` — un `only_cookable`
        # rimasto posizionale diventerebbe in silenzio «al massimo un mancante»
        max_missing=budget,
        limit=limit,
        category=category,
        ingredient_ids=ingredient_id,
    )
    return [
        RecipeSummaryOut(
            id=r.recipe.id, title=r.recipe.title, description=r.recipe.description,
            source=r.recipe.source, missing=r.missing, cookable=r.cookable,
            missing_names=r.missing_names,
            image_url=r.recipe.image_url, prep_minutes=r.recipe.prep_minutes,
            cook_minutes=r.recipe.cook_minutes, category=r.recipe.category,
        )
        for r in results
    ]
```

- [ ] **Passo 4: lanciare tutta la suite del backend**

```bash
cd backend && .venv/bin/python -m pytest
```

Atteso: tutto verde. Se `tests/api/test_recipes.py::test_la_scheda_elenca_i_mancanti`
riporta un ordine diverso, è `sorted` dimenticato in `_to_out` o in `missing_names`.

- [ ] **Passo 5: commit**

```bash
git add backend/app/api/recipes.py backend/app/schemas/recipe.py backend/tests/api/test_recipes.py
git commit -m "feat: /search prende una soglia, e le due rotte dicono cosa manca"
```

---

### Task 5: il tipo e la chiamata, nel frontend

**File:**
- Modificare: `frontend/src/domain/types.ts:69-80` (`RecipeSummary`)
- Modificare: `frontend/src/features/recipes/api.ts:7-25` (`searchRecipes`)
- Modificare: `frontend/src/features/recipes/RecipeBookScreen.test.tsx`,
  `frontend/src/features/cooking/RecipeDetailScreen.test.tsx`,
  `frontend/src/features/cooking/CookSheet.test.tsx` (gli oggetti costruiti a mano)

**Interfacce:**
- Consuma: il campo `missing_names` che la rotta manda (Task 4).
- Produce: `RecipeSummary.missing_names: string[]` e
  `searchRecipes({ query?, maxMissing?, category?, ingredientIds? })`, dove
  `maxMissing?: number | null`.

- [ ] **Passo 1: cambiare il tipo, e lasciare che sia il type check a fallire**

Qui il test che fallisce è il compilatore: `RecipeDetail extends RecipeSummary`, quindi
un campo obbligatorio in più fa cadere ogni oggetto costruito a mano nei test. È la
settima lezione di `CLAUDE.md` usata al contrario — e va usata con il comando giusto,
perché `tsc --noEmit` direbbe zero errori comunque.

In `frontend/src/domain/types.ts`, dentro `RecipeSummary`, dopo `cookable`:

```ts
  /** I nomi di quel che manca, in ordine alfabetico, decisi dal server. Il client
   * non li ricava da `ingredients`: chi manca lo dice la regola primario/secondario,
   * che vive nel backend. */
  missing_names: string[];
```

- [ ] **Passo 2: lanciare il type check e vederlo fallire**

```bash
cd frontend && npm run typecheck
```

Atteso: una serie di `TS2739`/`TS2345` che nominano i file e le righe degli oggetti
costruiti a mano. Annotare l'elenco: è la lista della spesa del passo dopo.

- [ ] **Passo 3: cambiare la chiamata e riparare gli oggetti**

a) in `frontend/src/features/recipes/api.ts`:

```ts
export function searchRecipes({
  query = "",
  maxMissing = null,
  category = "",
  ingredientIds = [],
}: {
  query?: string;
  /** Quante cose si è disposti a comprare. `null` è «tutte»: non una soglia
   * altissima, ma l'assenza di soglia — il server le distingue, perché una soglia
   * qualunque gli fa guardare tutto il ricettario invece dei cento più recenti. */
  maxMissing?: number | null;
  category?: string;
  ingredientIds?: string[];
} = {}) {
  const params = new URLSearchParams();
  if (query.trim()) params.set("q", query.trim());
  // `!== null` e non la verità: `0` è la soglia più stretta, non la sua assenza
  if (maxMissing !== null) params.set("max_missing", String(maxMissing));
  if (category) params.set("category", category);
  for (const id of ingredientIds) params.append("ingredient_id", id);
  return apiFetch<RecipeSummary[]>(`/recipes/search?${params.toString()}`);
}
```

b) in ognuno dei file che il passo 2 ha nominato, aggiungere `missing_names` agli
oggetti costruiti a mano, con il valore che il test descrive davvero — `[]` quando la
ricetta è cucinabile, i nomi quando non lo è. Nel `RESULTS` di
`RecipeBookScreen.test.tsx`:

```ts
const RESULTS = [
  { id: "r1", title: "Pasta all'aglio", description: "Svelta", source: "dataset",
    missing: 0, cookable: true, missing_names: [], image_url: "https://example.com/aglio.jpg",
    prep_minutes: 10, cook_minutes: 15, category: "Primi piatti" },
  { id: "r2", title: "Pasta al pomodoro", description: "Di sempre", source: "ai",
    missing: 1, cookable: false, missing_names: ["Pomodoro"], image_url: null,
    prep_minutes: null, cook_minutes: null, category: null },
];
```

- [ ] **Passo 4: type check e test verdi**

```bash
cd frontend && npm run typecheck && npx vitest run
```

Atteso: zero errori di tipo. `RecipeBookScreen.test.tsx` fallisce ancora sul test che
si aspetta `only_cookable=true` nell'URL: lo chiude il Task 7. Annotare e proseguire.

- [ ] **Passo 5: commit**

```bash
git add frontend/src/domain/types.ts frontend/src/features/recipes/api.ts frontend/src/features/recipes/RecipeBookScreen.test.tsx frontend/src/features/cooking/RecipeDetailScreen.test.tsx frontend/src/features/cooking/CookSheet.test.tsx
git commit -m "feat: il ricettario chiede una soglia e riceve i nomi dei mancanti"
```

---

### Task 6: `MissingBudgetFilter`, la scala

**File:**
- Creare: `frontend/src/features/recipes/MissingBudgetFilter.tsx`
- Creare: `frontend/src/features/recipes/MissingBudgetFilter.test.tsx`

**Interfacce:**
- Consuma: `buttonClasses(variant, shape)` da `frontend/src/components/ui/buttonClasses.ts`.
- Produce: `<MissingBudgetFilter value={number | null} onChange={(value: number | null) => void} />`.
  I gradini restano una costante privata del modulo: nessun altro file li nomina, e un
  export che non serve è una superficie in più da tenere ferma.

- [ ] **Passo 1: scrivere i test che falliscono**

`frontend/src/features/recipes/MissingBudgetFilter.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MissingBudgetFilter } from "./MissingBudgetFilter";

describe("MissingBudgetFilter", () => {
  it("segna il gradino scelto e spiega a parole cosa si sta guardando", () => {
    render(<MissingBudgetFilter value={2} onChange={vi.fn()} />);

    expect(
      screen.getByRole("radio", { name: "Al massimo 2 ingredienti da comprare." })
    ).toBeChecked();
    // «+2» da solo non dice niente: è la riga sotto a dire cosa si sta guardando
    expect(screen.getByText("Al massimo 2 ingredienti da comprare.")).toBeVisible();
  });

  it("parte da «Tutte» quando non c'è soglia", () => {
    render(<MissingBudgetFilter value={null} onChange={vi.fn()} />);
    expect(screen.getByRole("radio", { name: "Tutto il ricettario." })).toBeChecked();
  });

  it("comunica la soglia scelta", async () => {
    const onChange = vi.fn();
    render(<MissingBudgetFilter value={null} onChange={onChange} />);

    await userEvent.click(
      screen.getByRole("radio", { name: "Al massimo 1 ingrediente da comprare." })
    );

    expect(onChange).toHaveBeenCalledWith(1);
  });

  it("«Ora» è zero, non l'assenza di soglia", async () => {
    // il caso che un `if (maxMissing)` sbaglierebbe in silenzio, da qui fino alla query
    const onChange = vi.fn();
    render(<MissingBudgetFilter value={null} onChange={onChange} />);

    await userEvent.click(
      screen.getByRole("radio", { name: "Solo quelle che puoi cucinare adesso." })
    );

    expect(onChange).toHaveBeenCalledWith(0);
  });

  it("«Tutte» torna a nessuna soglia", async () => {
    const onChange = vi.fn();
    render(<MissingBudgetFilter value={0} onChange={onChange} />);

    await userEvent.click(screen.getByRole("radio", { name: "Tutto il ricettario." }));

    expect(onChange).toHaveBeenCalledWith(null);
  });
});
```

- [ ] **Passo 2: lanciarli e vederli fallire**

```bash
cd frontend && npx vitest run src/features/recipes/MissingBudgetFilter.test.tsx
```

Atteso: `Failed to resolve import "./MissingBudgetFilter"`.

- [ ] **Passo 3: scrivere il componente**

`frontend/src/features/recipes/MissingBudgetFilter.tsx`:

```tsx
import { buttonClasses } from "../../components/ui/buttonClasses";

/** I gradini della scala, nell'ordine in cui si leggono.
 *
 * `null` è «Tutte»: non una soglia altissima ma l'assenza di soglia, e il server le
 * distingue — una soglia qualunque gli fa guardare tutto il ricettario invece dei
 * cento più recenti. Oltre i tre mancanti un filtro sui mancanti non filtra più
 * niente, ed è per questo che la scala finisce lì.
 */
const BUDGET_STEPS: { value: number | null; pill: string; caption: string }[] = [
  { value: null, pill: "Tutte", caption: "Tutto il ricettario." },
  { value: 0, pill: "Ora", caption: "Solo quelle che puoi cucinare adesso." },
  { value: 1, pill: "+1", caption: "Al massimo 1 ingrediente da comprare." },
  { value: 2, pill: "+2", caption: "Al massimo 2 ingredienti da comprare." },
  { value: 3, pill: "+3", caption: "Al massimo 3 ingredienti da comprare." },
];

export function MissingBudgetFilter({
  value,
  onChange,
}: {
  value: number | null;
  onChange: (value: number | null) => void;
}) {
  const scelto = BUDGET_STEPS.find((step) => step.value === value) ?? BUDGET_STEPS[0];
  return (
    <fieldset>
      {/* cinque radio senza gruppo, letti a voce, sono cinque scelte senza domanda */}
      <legend className="sr-only">Quanto posso comprare</legend>
      <div className="flex flex-wrap gap-2">
        {BUDGET_STEPS.map((step) => {
          const checked = step.value === value;
          return (
            <label key={step.pill}>
              {/* Un radio vero, nascosto. La selezione singola e la navigazione da
                  tastiera sono del browser invece che nostre, e il test lo trova come
                  radio senza sapere niente di come è disegnato. Il nome accessibile è
                  la frase intera: «+2» letto a voce non è una scelta. */}
              <input
                type="radio"
                name="missing-budget"
                className="peer sr-only"
                checked={checked}
                onChange={() => onChange(step.value)}
                aria-label={step.caption}
              />
              <span
                className={`${buttonClasses(checked ? "primary" : "secondary", "pill")} peer-focus-visible:ring-2 peer-focus-visible:ring-brand peer-focus-visible:ring-offset-2`}
              >
                {step.pill}
              </span>
            </label>
          );
        })}
      </div>
      <p className="pt-1.5 text-xs text-ink-faint">{scelto.caption}</p>
    </fieldset>
  );
}
```

- [ ] **Passo 4: lanciarli e vederli passare**

```bash
cd frontend && npx vitest run src/features/recipes/MissingBudgetFilter.test.tsx && npm run typecheck
```

Atteso: cinque test verdi, zero errori di tipo.

- [ ] **Passo 5: commit**

```bash
git add frontend/src/features/recipes/MissingBudgetFilter.tsx frontend/src/features/recipes/MissingBudgetFilter.test.tsx
git commit -m "feat: la scala dei mancanti, cinque gradini e una frase"
```

---

### Task 7: lo schermo — via la casella, dentro la scala

**File:**
- Modificare: `frontend/src/features/recipes/RecipeBookScreen.tsx` (stato, chiave della
  query, il blocco della casella alle righe 193-201, `emptyMessage` alle righe 34-79)
- Modificare: `frontend/src/features/recipes/RecipeBookScreen.test.tsx`

**Interfacce:**
- Consuma: `MissingBudgetFilter` (Task 6), `searchRecipes({ maxMissing })` (Task 5).
- Produce: niente per altri task.

- [ ] **Passo 1: riscrivere il test che c'è e aggiungerne due**

In `frontend/src/features/recipes/RecipeBookScreen.test.tsx`, il test che oggi si
aspetta `only_cookable=true` (riga 114 circa) diventa:

```tsx
  it("la scala manda la soglia, e «Ora» manda zero", async () => {
    const spy = stubRoutedFetch(() => [RESULTS, 200]);
    renderScreen();
    await screen.findByText("Pasta all'aglio");

    await userEvent.click(
      screen.getByRole("radio", { name: "Solo quelle che puoi cucinare adesso." })
    );

    // `max_missing=0`, non l'assenza del parametro: «cucinabili ora» è la soglia più
    // stretta, e un `if (maxMissing)` la scambierebbe per «Tutte» mostrando tutto
    await waitFor(() => expect(ultimaRicerca(spy)).toContain("max_missing=0"));
    expect(ultimaRicerca(spy)).not.toContain("only_cookable");
  });

  it("un gradino più largo manda la sua soglia", async () => {
    const spy = stubRoutedFetch(() => [RESULTS, 200]);
    renderScreen();
    await screen.findByText("Pasta all'aglio");

    await userEvent.click(
      screen.getByRole("radio", { name: "Al massimo 2 ingredienti da comprare." })
    );

    await waitFor(() => expect(ultimaRicerca(spy)).toContain("max_missing=2"));
  });

  it("senza soglia non manda il parametro", async () => {
    const spy = stubRoutedFetch(() => [RESULTS, 200]);
    renderScreen();
    await screen.findByText("Pasta all'aglio");

    expect(ultimaRicerca(spy)).not.toContain("max_missing");
  });
```

E, sempre in quel file, il test dell'elenco vuoto che nomina la casella va aggiornato
alla frase nuova — cercare `puoi cucinare adesso` e allineare l'attesa a:

```
Niente che puoi cucinare con quel che hai in dispensa: alza la soglia, o scegli «Tutte» per vedere tutto il ricettario.
```

- [ ] **Passo 2: lanciarli e vederli fallire**

```bash
cd frontend && npx vitest run src/features/recipes/RecipeBookScreen.test.tsx
```

Atteso: i test nuovi falliscono perché il radio non esiste
(`Unable to find an accessible element with the role "radio"`).

- [ ] **Passo 3: cablare lo schermo**

In `frontend/src/features/recipes/RecipeBookScreen.tsx`:

a) importare il componente accanto agli altri import di `./`:

```tsx
import { MissingBudgetFilter } from "./MissingBudgetFilter";
```

b) lo stato, al posto di `const [onlyCookable, setOnlyCookable] = useState(false)`:

```tsx
  // `null` è «Tutte»: l'assenza di soglia, non una soglia larghissima
  const [maxMissing, setMaxMissing] = useState<number | null>(null);
```

c) la chiave e la chiamata della query:

```tsx
  const { data: recipes = [], isLoading, isError } = useQuery({
    queryKey: ["recipes", debouncedQuery, maxMissing, category, ingredientIds],
    queryFn: () =>
      searchRecipes({
        query: debouncedQuery,
        maxMissing,
        category,
        ingredientIds,
      }),
  });
```

d) al posto del blocco `<label>` con la casella (righe 193-201):

```tsx
      <MissingBudgetFilter value={maxMissing} onChange={setMaxMissing} />
```

e) in `emptyMessage`, il parametro `onlyCookable: boolean` diventa
`maxMissing: number | null`, e il frammento che quattro rami ripetono si calcola in un
posto solo:

```tsx
/** Come si nomina la soglia dentro le frasi degli altri rami.
 *
 * Un posto solo: quattro rami che se la scrivono a mano si scollano al primo cambio
 * di parole, e il primo a scollarsi sarebbe quello che si legge meno spesso.
 */
function frammentoSoglia(maxMissing: number | null): string {
  if (maxMissing === null) return "";
  if (maxMissing === 0) return " fra quelle che puoi cucinare adesso";
  if (maxMissing === 1) return " fra quelle a cui manca al massimo 1 ingrediente";
  return ` fra quelle a cui mancano al massimo ${maxMissing} ingredienti`;
}
```

dentro `emptyMessage`, ogni `${onlyCookable ? " fra quelle che puoi cucinare adesso" : ""}`
diventa `${frammentoSoglia(maxMissing)}`, e i due rami finali in cui la soglia è
l'unico filtro acceso diventano:

```tsx
  if (maxMissing === 0) {
    return (
      "Niente che puoi cucinare con quel che hai in dispensa: alza la soglia, o " +
      "scegli «Tutte» per vedere tutto il ricettario."
    );
  }
  if (maxMissing !== null) {
    return (
      `Niente da cucinare comprando al massimo ${maxMissing === 1 ? "1 cosa" : `${maxMissing} cose`}: ` +
      "alza la soglia, o scegli «Tutte» per vedere tutto il ricettario."
    );
  }
```

f) la chiamata a `emptyMessage` in fondo allo schermo passa `maxMissing` al posto di
`onlyCookable`.

- [ ] **Passo 4: test e type check**

```bash
cd frontend && npx vitest run && npm run typecheck && npm run build
```

Atteso: tutto verde. `npm run build` è l'unico che compila davvero i riferimenti di
progetto: non saltarlo.

- [ ] **Passo 5: commit**

```bash
git add frontend/src/features/recipes/RecipeBookScreen.tsx frontend/src/features/recipes/RecipeBookScreen.test.tsx
git commit -m "feat: il ricettario filtra per soglia, e la casella sparisce"
```

---

### Task 8: la scheda elenca i mancanti

**File:**
- Modificare: `frontend/src/features/recipes/RecipeCard.tsx`
- Creare: `frontend/src/features/recipes/RecipeCard.test.tsx`

**Interfacce:**
- Consuma: `RecipeSummary.missing_names` (Task 5).
- Produce: niente per altri task.

- [ ] **Passo 1: scrivere i test che falliscono**

`frontend/src/features/recipes/RecipeCard.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { RecipeCard } from "./RecipeCard";
import type { RecipeSummary } from "../../domain/types";

function ricetta(overrides: Partial<RecipeSummary> = {}): RecipeSummary {
  return {
    id: "r1", title: "Pasta al pomodoro", description: "Di sempre", source: "dataset",
    missing: 0, cookable: true, missing_names: [], image_url: null,
    prep_minutes: null, cook_minutes: null, category: null,
    ...overrides,
  };
}

function renderCard(recipe: RecipeSummary) {
  return render(
    <MemoryRouter>
      <ul>
        <RecipeCard recipe={recipe} />
      </ul>
    </MemoryRouter>
  );
}

describe("RecipeCard", () => {
  it("elenca quel che manca", () => {
    renderCard(ricetta({ missing: 2, cookable: false, missing_names: ["Basilico", "Pomodoro"] }));
    expect(screen.getByText("Basilico, Pomodoro")).toBeVisible();
  });

  it("non dice niente quando non manca niente", () => {
    renderCard(ricetta());
    expect(screen.getByText("Puoi cucinarla ora")).toBeVisible();
    expect(screen.queryByText(/,/)).toBeNull();
  });

  it("taglia gli elenchi lunghi invece di allungare la riga", () => {
    renderCard(
      ricetta({
        missing: 5, cookable: false,
        missing_names: ["Acciughe", "Basilico", "Capperi", "Olive", "Pomodoro"],
      })
    );
    expect(screen.getByText("Acciughe, Basilico, Capperi e altri 2")).toBeVisible();
  });

  it("al singolare dice «un altro»", () => {
    renderCard(
      ricetta({
        missing: 4, cookable: false,
        missing_names: ["Acciughe", "Basilico", "Capperi", "Olive"],
      })
    );
    expect(screen.getByText("Acciughe, Basilico, Capperi e un altro")).toBeVisible();
  });
});
```

- [ ] **Passo 2: lanciarli e vederli fallire**

```bash
cd frontend && npx vitest run src/features/recipes/RecipeCard.test.tsx
```

Atteso: `Unable to find an element with the text: Basilico, Pomodoro`.

- [ ] **Passo 3: scrivere l'implementazione**

In `frontend/src/features/recipes/RecipeCard.tsx`, accanto a `missingLabel`:

```tsx
const MAX_NAMES = 3;

/** I mancanti, tagliati dove la riga smetterebbe di leggersi.
 *
 * Il taglio lo fa il client e non il server: è qui che si sa quanto spazio c'è, e il
 * server manda la lista intera. Con un gradino della scala acceso non si taglia mai —
 * la soglia arriva a tre — e si taglia solo su «Tutte», dove a una ricetta possono
 * mancare dodici cose e la riga diventerebbe più lunga del titolo.
 */
function missingNamesLabel(names: string[]): string {
  if (names.length <= MAX_NAMES) return names.join(", ");
  const altri = names.length - MAX_NAMES;
  return `${names.slice(0, MAX_NAMES).join(", ")} e ${altri === 1 ? "un altro" : `altri ${altri}`}`;
}
```

e, subito sotto il `<div>` che contiene la pastiglia e i minuti:

```tsx
        {/* i nomi e basta: «mancano» l'ha appena detto la pastiglia qui sopra */}
        {recipe.missing_names.length > 0 && (
          <p className="pt-1 text-xs text-ink-faint">
            {missingNamesLabel(recipe.missing_names)}
          </p>
        )}
```

- [ ] **Passo 4: test, tipi, costruzione**

```bash
cd frontend && npx vitest run && npm run typecheck && npm run build
```

Atteso: tutto verde.

- [ ] **Passo 5: commit**

```bash
git add frontend/src/features/recipes/RecipeCard.tsx frontend/src/features/recipes/RecipeCard.test.tsx
git commit -m "feat: la scheda dice quali ingredienti mancano, non solo quanti"
```

---

### Task 9: la prova nel browser, e i documenti

**File:**
- Modificare: `frontend/e2e/style.spec.ts`
- Modificare: `docs/prossimi-passi.md` (R7 in Parte III, e la riga di R6)
- Modificare: `README.md` se nomina la casella del ricettario

**Interfacce:**
- Consuma: la scala costruita nei Task 6 e 7.
- Produce: niente.

- [ ] **Passo 1: scrivere il controllo end-to-end**

La quarta lezione di `CLAUDE.md`: la pastiglia scelta si distingue da quelle non
scelte solo per il CSS, e jsdom non lo calcola. In fondo a
`frontend/e2e/style.spec.ts`, e con `type Locator` aggiunto all'import di
`@playwright/test`:

```ts
test("il gradino scelto della scala si distingue, e si legge", async ({ page }) => {
  await page.getByRole("link", { name: "Ricette", exact: true }).click();

  const tutte = page.getByRole("radio", { name: "Tutto il ricettario." });
  const uno = page.getByRole("radio", { name: "Al massimo 1 ingrediente da comprare." });
  await expect(tutte).toBeChecked();

  // il radio è `sr-only`: la pastiglia che si vede è lo `span` dentro la sua label,
  // come per la X del filtro qui sopra si parte dal controllo e si sale
  const pastigliaDi = (radio: Locator) => page.locator("label").filter({ has: radio }).locator("span");

  const fondoSpento = await pastigliaDi(uno).evaluate(
    (el) => getComputedStyle(el).backgroundColor
  );
  await uno.click();
  await expect(uno).toBeChecked();

  // --color-brand: #14804f. Se il gradino scelto non cambiasse fondo, la scala
  // direbbe cinque volte la stessa cosa e nessun test in jsdom se ne accorgerebbe
  const fondoAcceso = await pastigliaDi(uno).evaluate(
    (el) => getComputedStyle(el).backgroundColor
  );
  expect(fondoAcceso).not.toBe(fondoSpento);
  expect(fondoAcceso).toBe("rgb(20, 128, 79)");

  // il contrasto misurato dal browser, non calcolato a mente: questa app si legge
  // in corsia alla luce del giorno
  const rapporto = await pastigliaDi(uno).evaluate((el) => {
    const luminanza = (colore: string) => {
      const [r, g, b] = colore.match(/\d+(\.\d+)?/g)!.slice(0, 3).map(Number);
      const canale = (v: number) => {
        const s = v / 255;
        return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
      };
      return 0.2126 * canale(r) + 0.7152 * canale(g) + 0.0722 * canale(b);
    };
    const stile = getComputedStyle(el);
    const a = luminanza(stile.color);
    const b = luminanza(stile.backgroundColor);
    return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  });
  expect(rapporto).toBeGreaterThanOrEqual(4.5);
});
```

- [ ] **Passo 2: lanciarlo sullo stack e2e**

```bash
E2E="docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml"
$E2E up -d --build --wait
$E2E exec -T backend python -m app.cli.seed
(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
$E2E down -v
```

Atteso: tutti i controlli verdi, il nuovo compreso.

- [ ] **Passo 3: guardare lo schermo davvero**

Con lo stack e2e ancora in piedi (o quello di sviluppo), aprire il ricettario a 375px e
controllare tre cose che nessun test dice:

1. i cinque gradini stanno su una riga o vanno a capo in modo leggibile, senza
   traboccare;
2. scegliendo «+2» la frase sotto cambia e l'elenco si allarga;
3. una scheda con due mancanti mostra i nomi sotto la pastiglia, e il titolo resta
   leggibile.

- [ ] **Passo 4: aggiornare i documenti**

In `docs/prossimi-passi.md`:

a) l'intestazione di R7 diventa
`## R7. Cerca ricette con al massimo *n* ingredienti mancanti **[FATTO 2026-09-21]**`,
con sotto due righe su com'è finita: la casella «Solo quelle che posso cucinare» è
diventata il gradino zero di una scala a cinque, la scheda elenca i mancanti, e il
filtro toglie il limite della piscina per qualunque soglia;

b) sotto R6, una riga: «"cucinabile" adesso è un gradino di una scala, non una
casella: quando R6 arriverà, "cucinabile con sostituti" va pensata come una seconda
scala o come un interruttore accanto a questa, non come una casella in più»;

c) aggiornare la data e la riga di apertura del file, come fa ogni lavoro che entra.

Poi:

```bash
grep -rn "posso cucinare" README.md
```

Se la casella è nominata, allineare la frase alla scala.

- [ ] **Passo 5: la verifica completa, e il commit**

```bash
docker compose up -d db
cd backend && .venv/bin/python -m pytest
cd ../frontend && npx vitest run && npm run typecheck && npm run build
```

Atteso: tutto verde, in tutti e quattro i comandi. Nessuna affermazione di «fatto»
prima di aver visto questi output.

```bash
git add frontend/e2e/style.spec.ts docs/prossimi-passi.md README.md
git commit -m "docs: R7 è in piedi, e la scala si vede anche in un browser vero"
```
