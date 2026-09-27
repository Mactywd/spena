# L'anagrafica (S9) — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Obiettivo:** un errore di registrazione smette di restare per sempre: dall'app un
prodotto si rinomina, cambia marca, si sposta sotto un altro ingrediente con la sua
dispensa, perde o cambia il codice, si elimina; un ingrediente si rinomina, cambia
reparto, cede un alias, si unisce a un doppione con un'anteprima che è la fusione stessa.

**Architettura:** un servizio solo, `backend/app/services/registry.py`, prende la
logica che oggi vive in `app/cli/fix_registry.py` (che diventa un guscio) e aggiunge
le correzioni sui prodotti; non fa mai commit, e l'anteprima della fusione è la stessa
funzione dentro un SAVEPOINT annullato. Le cotture non si perdono più quando una
ricetta importata si rifà: i loro id aspettano nel `payload` della pagina e tornano
sulla ricetta nuova, così `CookedRecipesAffected` e il suo `force` spariscono. Sopra,
nove rotte con 409 che portano l'ostacolo, e tre schermate raggiunte dall'hamburger e
dal nome della riga di dispensa.

**Stack:** FastAPI, SQLAlchemy async, Postgres 16 (pgvector, pg_trgm); React 19 +
Vite + TypeScript, TanStack Query 5, React Router 7, Tailwind 4 con `@theme`; pytest
su Postgres vero, Vitest + jsdom + Testing Library, Playwright sullo stack `spena-e2e`.

**Spec:** `docs/superpowers/specs/2026-09-27-anagrafica-design.md`

## Vincoli globali

- **Testi per l'utente in italiano**, e in italiano anche commenti e docstring;
  identificatori in inglese.
- **Il colore vive solo nei token** del blocco `@theme` di `frontend/src/index.css`
  (`text-brand`, `text-danger`, `text-low`, `bg-card`, `bg-ink/40`, `divide-line`…).
  Nessuna schermata nomina un colore grezzo: `grep -rnE "emerald|neutral-|#[0-9a-f]{6}" frontend/src --include=*.tsx`
  resta vuoto.
- **I primitivi stanno in `frontend/src/components/ui/`** (`Screen`, `Card`, `Alert`,
  `SectionHeading`, `buttonClasses`, `OptionList`) e in `frontend/src/components/`
  (`IngredientPicker`, `BackLink`): si guardano prima di scrivere un bottone.
- **Il type check è `npm run typecheck`** (`tsc -b`). Mai `tsc --noEmit`, che su
  questo progetto esce 0 sempre (settima lezione di `CLAUDE.md`).
- **Backend su Postgres vero:** `docker compose up -d db`, poi
  `cd backend && PATH="$PWD/.venv/bin:$PATH" python -m pytest` (il `PATH` serve ai test
  che lanciano `alembic`). Nessuna chiamata di rete nella suite.
- **Frontend**, sempre da `frontend/`: `npx vitest run`, `npm run lint`,
  `npm run typecheck`, `npm run build`.
- **e2e sullo stack `spena-e2e`** (Parte IX di `docs/prossimi-passi.md`), con `-p
  spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml` in **ogni** comando:
  ```bash
  E2E="docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml"
  $E2E up -d --build --wait
  $E2E exec -T backend python -m app.cli.seed --con-ricette
  (cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
  $E2E down -v
  ```
- **Un JSONB si riassegna, non si muta:** `page.payload = {...}`, mai
  `page.payload["x"] = …` né `.pop()`. SQLAlchemy non vede le mutazioni dentro un JSONB.
- **`backend/tests/test_fix_registry_cli.py` non si modifica:** passa com'è, prima e
  dopo lo spostamento sul servizio (spec §9.2, §10).
- **Nessuna funzione del servizio fa commit.** Chi chiama decide.
- **Bersagli di almeno 44 px** (`min-h-11`, `size-11`, o `buttonClasses`, che li porta).
- **Mai un vicolo cieco:** ogni rifiuto offre il passo dopo (spec §7).
- **I test dei componenti usano il predicato di retry vero**
  (`defaultQueryRetryPredicate` da `frontend/src/lib/queryRetry.ts`), non
  `retry: false` (prima lezione di `CLAUDE.md`).
- **TDD:** nessun codice di produzione senza un test che è già fallito.
- **Commit in italiano**, uno per task, che finiscono con
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Distribuzione sempre** `docker compose -f docker-compose.prod.yml up -d --build --wait`,
  e solo dopo il via esplicito di Mattia in chat. Mai un `docker compose` senza `-f`
  sul server (terza lezione di `CLAUDE.md`).
- **Niente dati di produzione in git:** il repository è pubblico.

---

## Struttura dei file

**Backend**
- `backend/app/services/registry.py` — *crea*: il servizio unico delle correzioni.
  `RefusalCode`, `RegistryRefusal`, `RecipeRef`, `RecipesInUse`, `MergeCounts`;
  `recipes_using`, `queue_terms_by_alias`, `rename_ingredient`,
  `recategorize_ingredient`, `move_alias`, `delete_alias`, `merge_ingredients`,
  `preview_merge`, `update_product`, `move_product`, `set_barcode`, `delete_product`.
- `backend/app/repositories/ingredients.py` — *modifica*: `remember_alias` prende
  `source` (default `"import"`); `IngredientUsage` e `ingredient_usage` per la scheda.
- `backend/app/services/recipe_import/materialize.py` — *modifica*:
  `COOKING_EVENTS_KEY`, la ri-legatura delle cotture, `Materialized.relinked`.
- `backend/app/services/recipe_import/undo.py` — *modifica*: via `CookedRecipesAffected`
  e `force`; gli id delle cotture nel `payload`; la docstring.
- `backend/app/schemas/recipe_import.py`, `backend/app/api/imports.py` — *modifica*:
  via `UndoRequest` e il ramo 409 delle cotture.
- `backend/app/cli/fix_registry.py` — *modifica*: guscio sul servizio.
- `backend/app/api/refusals.py` — *crea*: `refusal_response`, il 409 dell'anagrafica
  in un posto solo.
- `backend/app/schemas/ingredient.py`, `backend/app/api/ingredients.py` — *modifica*:
  la scheda, la PATCH, la fusione, gli alias.
- `backend/app/schemas/product.py`, `backend/app/api/products.py` — *modifica*: la
  scheda, la PATCH, la DELETE.

**Prove backend**
- `backend/tests/conftest.py` — *modifica*: la fixture `dal_database`.
- `backend/tests/services/test_registry.py` — *crea* (Task 1, 2, 7).
- `backend/tests/services/test_registry_merge.py` — *crea* (Task 5, 6).
- `backend/tests/services/test_undo.py`, `backend/tests/api/test_imports_undo.py` —
  *modifica* (Task 3).
- `backend/tests/test_fix_registry_is_a_shell.py` — *crea* (Task 8).
- `backend/tests/api/test_registry_ingredients.py` — *crea* (Task 9).
- `backend/tests/api/test_registry_products.py` — *crea* (Task 10).
- `backend/tests/test_fix_registry_cli.py` — **non si tocca**.

**Frontend**
- `frontend/src/features/recipe-import/api.ts`, `ImportQueueScreen.tsx`,
  `ImportQueueScreen.test.tsx` — *modifica* (Task 4).
- `frontend/src/components/AppHeader.tsx`, `AppHeader.test.tsx` — *modifica*: il ☰ e il
  pannello (Task 13).
- `frontend/src/App.tsx` — *modifica*: le tre rotte nuove (Task 14, 15, 19).
- `frontend/src/domain/types.ts` — *modifica*: le forme della scheda, della fusione e
  dei rifiuti.
- `frontend/src/features/registry/api.ts` — *crea*: le chiamate, `registryRefusal`,
  `refreshAfterCorrection`.
- `frontend/src/features/registry/origin.ts` — *crea*: da dove si è arrivati, e dove si
  torna (`?da=dispensa`).
- `frontend/src/features/registry/wording.ts` (+ `wording.test.ts`) — *crea*: le frasi
  che dipendono da numeri (uso, anteprima, esito, spostamento).
- `frontend/src/features/registry/RegistryScreen.tsx` (+ test) — *crea*: `/anagrafica`.
- `frontend/src/features/registry/IngredientScreen.tsx` (+ test) — *crea*: la scheda
  dell'ingrediente.
- `frontend/src/features/registry/AliasRow.tsx`, `CategoryForm.tsx`, `MergePanel.tsx`,
  `RenameForm.tsx` — *crea*: i pezzi della scheda dell'ingrediente, provati attraverso
  la scheda.
- `frontend/src/features/registry/ProductScreen.tsx` (+ test), `InlineField.tsx` —
  *crea*: la scheda del prodotto e il campo con «Salva».
- `frontend/src/features/pantry/PantryRow.tsx`, `PantryScreen.test.tsx` — *modifica*:
  il nome diventa un link (Task 21).
- `frontend/e2e/anagrafica.spec.ts` — *crea* (Task 22).

**Documenti:** `CLAUDE.md` (Task 3, Task 23), `docs/prossimi-passi.md` (Task 12, 13,
23), la docstring di `undo.py` (Task 3).

---

# Consegna 1 — backend

Si distribuisce da sola (Task 12): le rotte nuove esistono senza schermate, e la coda
smette di chiedere conferma per le cotture.

### Task 1: Il servizio — rinominare e cambiare reparto

**File:**
- Create: `backend/app/services/registry.py`
- Modify: `backend/app/repositories/ingredients.py` (`remember_alias`, righe 119–152)
- Test: `backend/tests/services/test_registry.py`

**Interfacce:**
- Consuma: `canonical_name`, `find_by_name`, `remember_alias`
  (`app/repositories/ingredients.py`); `kind_for_category`, `IngredientKind`
  (`app/domain/rules.py`); `create_recipe` nei test.
- Produce:
  - `remember_alias(session, ingredient_id, display_name, *, source: str = "import") -> bool`
  - `MANUAL_ALIAS_SOURCE = "manual"`, `RECIPES_SHOWN = 20`
  - `class RefusalCode(StrEnum)` con `SAME_INGREDIENT`, `EMPTY_NAME`, `NAME_TAKEN`,
    `UNKNOWN_CATEGORY`, `NON_FOOD_IN_RECIPES`, `KIND_MISMATCH`, `IMPORT_ALIAS`,
    `DECISION_REFUSED`, `STILL_USED`, `BARCODE_TAKEN`, `BAD_CHECKSUM` (valori in
    minuscolo, uguali al nome)
  - `class RegistryRefusal(Exception)` con `.code: RefusalCode`, `.message: str`,
    `.obstacle: object | None`
  - `@dataclass(frozen=True) RecipeRef(id: uuid.UUID, title: str)`,
    `@dataclass(frozen=True) RecipesInUse(count: int, recipes: tuple[RecipeRef, ...])`
  - `async recipes_using(session, ingredient_id) -> RecipesInUse`
  - `async rename_ingredient(session, ingredient_id, *, name: str | None = None, display_name: str | None = None) -> Ingredient`
  - `async recategorize_ingredient(session, ingredient_id, category: str) -> Ingredient`
  - un id inesistente solleva `LookupError`.

- [ ] **Step 0: il ramo**

```bash
git checkout master && git pull --ff-only
git checkout -b anagrafica
docker compose up -d db
(cd backend && PATH="$PWD/.venv/bin:$PATH" python -m pytest -q)
```
Expected: tutto verde. Annota il numero di test: è la linea di partenza.

- [ ] **Step 1: scrivi il test che fallisce**

Crea `backend/tests/services/test_registry.py`:

```python
"""Il servizio unico dell'anagrafica (S9 §3): una prova per funzione e una per rifiuto.

Su Postgres vero, come tutto: le guardie leggono le righe di ricetta e gli alias con
query, e un finto database proverebbe una copia di quelle query.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.recipe import RecipeSource
from app.domain.rules import IngredientKind
from app.repositories.recipes import create_recipe
from app.services.registry import (
    RecipeRef,
    RefusalCode,
    RegistryRefusal,
    recategorize_ingredient,
    rename_ingredient,
)


@pytest_asyncio.fixture
async def anagrafica(db_session):
    def voce(name: str, display: str, category: str) -> Ingredient:
        return Ingredient(name=name, display_name=display, category=category)

    voci = {
        "pomodoro": voce("pomodoro", "Pomodoro", IngredientCategory.VERDURA),
        "pomodori": voce("pomodori", "Pomodori", IngredientCategory.VERDURA),
        "burro": voce("burro", "Burro", IngredientCategory.LATTICINI),
        "parmigiano": voce("parmigiano", "Parmigiano", IngredientCategory.LATTICINI),
        "salvia": voce("salvia", "Salvia", IngredientCategory.SPEZIE),
    }
    db_session.add_all(voci.values())
    await db_session.flush()
    return voci


async def _alias(db_session, ingredient_id) -> dict[str, str]:
    """Gli alias di un ingrediente, con la loro fonte."""
    rows = await db_session.execute(
        select(IngredientAlias.alias, IngredientAlias.source).where(
            IngredientAlias.ingredient_id == ingredient_id
        )
    )
    return dict(rows.all())


async def test_rinominare_scrive_i_due_nomi_e_il_vecchio_resta_come_alias(db_session, anagrafica):
    pomodori = anagrafica["pomodori"]

    await rename_ingredient(db_session, pomodori.id, name="Pomodorini", display_name="Pomodorini")

    assert pomodori.name == "pomodorini"
    assert pomodori.display_name == "Pomodorini"
    # «manual» e non «import»: il vecchio nome non è la metà di nessuna decisione della
    # coda, e marcato «import» diventerebbe un alias che l'anagrafica non può toccare
    assert await _alias(db_session, pomodori.id) == {"pomodori": "manual"}


async def test_un_nome_gia_preso_rifiuta_e_porta_l_omonimo(db_session, anagrafica):
    """Il rifiuto porta l'ingrediente che ha già quel nome: lo schermo ne fa «Uniscili»."""
    with pytest.raises(RegistryRefusal) as rifiuto:
        await rename_ingredient(db_session, anagrafica["pomodori"].id, name=" Pomodoro ")

    assert rifiuto.value.code == RefusalCode.NAME_TAKEN
    assert rifiuto.value.obstacle is anagrafica["pomodoro"]
    assert "già in anagrafica" in rifiuto.value.message
    assert anagrafica["pomodori"].name == "pomodori"


async def test_un_nome_vuoto_rifiuta_senza_toccare_niente(db_session, anagrafica):
    """Il controllo viene prima di ogni scrittura: un rifiuto a metà lascerebbe il nome
    nuovo con il nome a video vecchio."""
    with pytest.raises(RegistryRefusal) as rifiuto:
        await rename_ingredient(
            db_session, anagrafica["pomodori"].id, name="Pomodorini", display_name="   "
        )

    assert rifiuto.value.code == RefusalCode.EMPTY_NAME
    assert anagrafica["pomodori"].name == "pomodori"


async def test_rinominare_un_ingrediente_che_non_c_e(db_session):
    with pytest.raises(LookupError):
        await rename_ingredient(db_session, uuid.uuid4(), name="qualcosa")


async def test_cambiare_reparto_ricalcola_il_tipo(db_session, anagrafica):
    salvia = anagrafica["salvia"]

    await recategorize_ingredient(db_session, salvia.id, "casa")

    assert salvia.category == "casa"
    # `kind` non si scrive: lo deriva il `@validates` del modello dal reparto
    assert salvia.kind == IngredientKind.NON_FOOD


async def test_il_non_alimentare_con_ricette_rifiuta_e_le_elenca(db_session, anagrafica):
    burro = anagrafica["burro"]
    risotto = await create_recipe(
        db_session, title="Risotto al burro", description=None, instructions="Manteca.",
        servings=2, source=RecipeSource.AI, source_ref=None,
        ingredients=[(burro.id, "primary", "50 g", None)], embedding=None,
    )

    with pytest.raises(RegistryRefusal) as rifiuto:
        await recategorize_ingredient(db_session, burro.id, "casa")

    assert rifiuto.value.code == RefusalCode.NON_FOOD_IN_RECIPES
    assert rifiuto.value.obstacle.count == 1
    assert rifiuto.value.obstacle.recipes == (RecipeRef(id=risotto.id, title="Risotto al burro"),)
    assert "non può diventare non alimentare" in rifiuto.value.message
    assert burro.category == "latticini"


async def test_un_reparto_sconosciuto_rifiuta(db_session, anagrafica):
    with pytest.raises(RegistryRefusal) as rifiuto:
        await recategorize_ingredient(db_session, anagrafica["salvia"].id, "bagno")
    assert rifiuto.value.code == RefusalCode.UNKNOWN_CATEGORY
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `cd backend && PATH="$PWD/.venv/bin:$PATH" python -m pytest tests/services/test_registry.py -v`
Expected: FAIL in raccolta — `ModuleNotFoundError: No module named 'app.services.registry'`.

- [ ] **Step 3: implementazione minima**

In `backend/app/repositories/ingredients.py`, la firma e l'ultima riga di
`remember_alias`, più un paragrafo in fondo alla sua docstring:

```python
async def remember_alias(
    session: AsyncSession, ingredient_id: uuid.UUID, display_name: str,
    *, source: str = "import",
) -> bool:
```

```python
    `source` resta `"import"` per i chiamanti di sempre, che sono decisioni della coda.
    Le correzioni dell'anagrafica (`app/services/registry.py`) scrivono `"manual"`: il
    vecchio nome di un ingrediente rinominato non è la metà di nessuna decisione, e
    marcato «import» sarebbe un alias che l'anagrafica rifiuta di toccare e che la
    coda non sa di avere.
    """
```

```python
    await add_alias(session, ingredient_id, cleaned, source=source)
    return True
```

Crea `backend/app/services/registry.py`:

```python
"""Le correzioni dell'anagrafica, in un posto solo (S9).

Due porte le chiamano: le schede dell'anagrafica (`app/api/ingredients.py`,
`app/api/products.py`) e il comando `app.cli.fix_registry`, che corregge a lotti da un
piano scritto. La logica stava nel comando; è stata spostata qui e non ricopiata,
perché una guardia provata su una copia non protegge l'originale (prima lezione di
CLAUDE.md).

Ogni funzione prende la sessione e argomenti tipizzati, e **non fa commit**: chi chiama
decide. È questo che permette all'anteprima della fusione di essere la fusione stessa,
dentro un SAVEPOINT annullato, e al comando di provare un piano intero senza salvarlo.

Un rifiuto è un `RegistryRefusal`: un codice, un messaggio in italiano da mostrare e,
dove serve, l'oggetto che fa da ostacolo — l'omonimo, il prodotto che ha già il codice,
le ricette che usano l'ingrediente. Lo schermo ne ricava il passo dopo invece di un
errore (spec §7). Un id che non esiste è un `LookupError`, come nei repository.
"""

import uuid
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.recipe import Recipe, RecipeIngredient
from app.domain.rules import IngredientKind, kind_for_category
from app.repositories.ingredients import canonical_name, find_by_name, remember_alias

# La fonte degli alias che nascono da una correzione a mano. Non sono la metà di una
# decisione della coda, quindi l'anagrafica li può spostare e togliere.
MANUAL_ALIAS_SOURCE = "manual"

# Quante ricette porta con sé il rifiuto «non alimentare con ricette»: abbastanza per
# riconoscerle, non tutte — «sale» è in migliaia di ricette, e il conto le dice.
RECIPES_SHOWN = 20


class RefusalCode(StrEnum):
    SAME_INGREDIENT = "same_ingredient"
    EMPTY_NAME = "empty_name"
    NAME_TAKEN = "name_taken"
    UNKNOWN_CATEGORY = "unknown_category"
    NON_FOOD_IN_RECIPES = "non_food_in_recipes"
    KIND_MISMATCH = "kind_mismatch"
    IMPORT_ALIAS = "import_alias"
    DECISION_REFUSED = "decision_refused"
    STILL_USED = "still_used"
    BARCODE_TAKEN = "barcode_taken"
    BAD_CHECKSUM = "bad_checksum"


class RegistryRefusal(Exception):
    """Una correzione che non si può applicare così com'è, detta con il suo perché."""

    def __init__(
        self, code: RefusalCode, message: str, obstacle: object | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.obstacle = obstacle


@dataclass(frozen=True)
class RecipeRef:
    id: uuid.UUID
    title: str


@dataclass(frozen=True)
class RecipesInUse:
    count: int
    recipes: tuple[RecipeRef, ...]


async def _ingredient(session: AsyncSession, ingredient_id: uuid.UUID) -> Ingredient:
    ingredient = await session.get(Ingredient, ingredient_id)
    if ingredient is None:
        raise LookupError(f"nessun ingrediente {ingredient_id}")
    return ingredient


async def recipes_using(session: AsyncSession, ingredient_id: uuid.UUID) -> RecipesInUse:
    """Quante ricette usano l'ingrediente, e le prime `RECIPES_SHOWN` per titolo.

    Il conto è una query sua e non la lunghezza dell'elenco: l'elenco è tagliato, il
    conto no (sesta lezione di CLAUDE.md, un limite davanti a quel che si conta).
    """
    count = (
        await session.execute(
            select(func.count())
            .select_from(RecipeIngredient)
            .where(RecipeIngredient.ingredient_id == ingredient_id)
        )
    ).scalar_one()
    rows = await session.execute(
        select(Recipe.id, Recipe.title)
        .join(RecipeIngredient, RecipeIngredient.recipe_id == Recipe.id)
        .where(RecipeIngredient.ingredient_id == ingredient_id)
        .order_by(Recipe.title, Recipe.id)
        .limit(RECIPES_SHOWN)
    )
    return RecipesInUse(
        count=count, recipes=tuple(RecipeRef(id=row.id, title=row.title) for row in rows)
    )


async def rename_ingredient(
    session: AsyncSession,
    ingredient_id: uuid.UUID,
    *,
    name: str | None = None,
    display_name: str | None = None,
) -> Ingredient:
    """Il nome canonico e il nome a video. Il vecchio nome resta come alias, così chi
    lo scrive in lista trova ancora l'ingrediente.

    Tutti i controlli vengono prima di ogni scrittura: un rifiuto a metà lascerebbe
    un ingrediente col nome nuovo e il nome a video vecchio.
    """
    ingredient = await _ingredient(session, ingredient_id)
    new_name = canonical_name(name) if name is not None else None
    new_display = display_name.strip() if display_name is not None else None
    if new_name == "" or new_display == "":
        raise RegistryRefusal(RefusalCode.EMPTY_NAME, "Il nome non può essere vuoto.")
    if new_name is not None and new_name != ingredient.name:
        taken = await find_by_name(session, new_name)
        if taken is not None:
            raise RegistryRefusal(
                RefusalCode.NAME_TAKEN,
                f"«{new_name}» è già in anagrafica: uniscili invece di rinominare.",
                taken,
            )

    old_name = ingredient.name
    if new_name is not None and new_name != ingredient.name:
        # l'alias uguale al nome nuovo diventerebbe un doppione del nome
        await session.execute(
            delete(IngredientAlias).where(
                IngredientAlias.ingredient_id == ingredient.id,
                IngredientAlias.alias == new_name,
            )
        )
        ingredient.name = new_name
    if new_display is not None:
        ingredient.display_name = new_display
    await session.flush()
    if old_name != ingredient.name:
        await remember_alias(session, ingredient.id, old_name, source=MANUAL_ALIAS_SOURCE)
    return ingredient


async def recategorize_ingredient(
    session: AsyncSession, ingredient_id: uuid.UUID, category: str
) -> Ingredient:
    """Il reparto, e con lui `kind`, che il `@validates` del modello deriva.

    Un ingrediente che una ricetta usa non diventa non alimentare: le ricette puntano
    solo al cibo (decisione fondante 2), e il rifiuto porta le ricette perché lo
    schermo le elenchi, ciascuna col suo link.
    """
    ingredient = await _ingredient(session, ingredient_id)
    if category not in {c.value for c in IngredientCategory}:
        raise RegistryRefusal(RefusalCode.UNKNOWN_CATEGORY, f"reparto sconosciuto: «{category}»")
    if kind_for_category(category) == IngredientKind.NON_FOOD:
        in_use = await recipes_using(session, ingredient.id)
        if in_use.count:
            recipes = "1 ricetta" if in_use.count == 1 else f"{in_use.count} ricette"
            raise RegistryRefusal(
                RefusalCode.NON_FOOD_IN_RECIPES,
                f"«{ingredient.display_name}» è in {recipes}: non può diventare non "
                "alimentare finché una ricetta lo usa.",
                in_use,
            )
    ingredient.category = str(category)
    await session.flush()
    return ingredient
```

- [ ] **Step 4: eseguilo e verifica che passi**

Run: `cd backend && PATH="$PWD/.venv/bin:$PATH" python -m pytest tests/services/test_registry.py tests/api/test_ingredients.py tests/services -q`
Expected: PASS, tutti (le decisioni dell'import che chiamano `remember_alias` senza
`source` continuano a scrivere `"import"`).

- [ ] **Step 5: commit**

```bash
git add backend/app/services/registry.py backend/app/repositories/ingredients.py backend/tests/services/test_registry.py
git commit -m "$(cat <<'EOF'
anagrafica: il servizio unico, con rinomina e cambio di reparto

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Il servizio — gli alias

**File:**
- Modify: `backend/app/services/registry.py`
- Test: `backend/tests/services/test_registry.py`

**Interfacce:**
- Consuma: `_ingredient`, `RegistryRefusal`, `RefusalCode`, `MANUAL_ALIAS_SOURCE`
  (Task 1); `add_alias`, `remember_alias`.
- Produce:
  - `async queue_terms_by_alias(session, ingredient_id) -> dict[str, ImportTerm]`
    (chiave: `display_name.strip().lower()`, la stessa normalizzazione di `remember_alias`)
  - `async move_alias(session, alias_id, target_id) -> IngredientAlias | None`
  - `async delete_alias(session, alias_id) -> None`
  - rifiuto `IMPORT_ALIAS` con `obstacle` = l'`ImportTerm`; `LookupError` per un alias
    inesistente.

- [ ] **Step 1: scrivi il test che fallisce**

In `backend/tests/services/test_registry.py`, agli import:

```python
from datetime import UTC, datetime

from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.repositories.ingredients import add_alias, remember_alias
from app.services.registry import delete_alias, move_alias, queue_terms_by_alias
```

(le ultime tre vanno nell'import esistente da `app.services.registry`, in ordine
alfabetico). In fondo al file:

```python
@pytest_asyncio.fixture
async def deciso(db_session, anagrafica):
    """Un termine della coda deciso su «pomodori», con il suo alias «import».

    Lo spazio in coda al nome è voluto: `remember_alias` normalizza, e la guardia deve
    riconoscere l'alias con la stessa normalizzazione, non con una sua.
    """
    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-pelati", display_name="Pomodori pelati ",
        occurrences=1, decision=TermDecision.MAPPED, ingredient_id=anagrafica["pomodori"].id,
        decided_by="ai", decided_at=datetime.now(UTC),
    )
    db_session.add(term)
    await db_session.flush()
    await remember_alias(db_session, term.ingredient_id, term.display_name)
    alias = (
        await db_session.execute(
            select(IngredientAlias).where(IngredientAlias.alias == "pomodori pelati")
        )
    ).scalar_one()
    return term, alias


async def test_un_alias_scritto_a_mano_si_sposta(db_session, anagrafica):
    pomodori, pomodoro = anagrafica["pomodori"], anagrafica["pomodoro"]
    alias = await add_alias(db_session, pomodori.id, "pomodoro ciliegino", source="manual")

    spostato = await move_alias(db_session, alias.id, pomodoro.id)

    assert spostato is not None
    assert spostato.ingredient_id == pomodoro.id
    assert spostato.source == "manual"
    assert await _alias(db_session, pomodori.id) == {}


async def test_un_alias_uguale_al_nome_di_arrivo_sparisce(db_session, anagrafica):
    """Un alias uguale al nome è un doppione del nome: spostarlo lì vuol dire toglierlo."""
    alias = await add_alias(db_session, anagrafica["pomodori"].id, "pomodoro", source="seed")

    assert await move_alias(db_session, alias.id, anagrafica["pomodoro"].id) is None
    rimasti = (
        await db_session.execute(select(IngredientAlias).where(IngredientAlias.alias == "pomodoro"))
    ).scalars().all()
    assert rimasti == []


async def test_un_alias_della_coda_non_si_tocca_e_porta_il_termine(db_session, anagrafica, deciso):
    """Spostarlo da qui lascerebbe la coda a dire una cosa e l'anagrafica un'altra."""
    term, alias = deciso

    with pytest.raises(RegistryRefusal) as spostamento:
        await move_alias(db_session, alias.id, anagrafica["pomodoro"].id)
    with pytest.raises(RegistryRefusal) as rimozione:
        await delete_alias(db_session, alias.id)

    assert spostamento.value.code == RefusalCode.IMPORT_ALIAS
    assert spostamento.value.obstacle is term
    assert "nella coda" in spostamento.value.message
    assert rimozione.value.code == RefusalCode.IMPORT_ALIAS
    assert await _alias(db_session, anagrafica["pomodori"].id) == {"pomodori pelati": "import"}


async def test_un_alias_import_senza_termine_si_corregge_da_qui(db_session, anagrafica):
    """Il vecchio nome scritto da un `merge` o da un `rename` della CLI prima di S9 porta
    `source="import"` ma non è la metà di nessuna decisione: rifiutarlo sarebbe un
    vicolo cieco, perché nella coda non c'è niente da correggere."""
    alias = await add_alias(
        db_session, anagrafica["pomodori"].id, "pomodoro san marzano", source="import"
    )

    await delete_alias(db_session, alias.id)

    assert await _alias(db_session, anagrafica["pomodori"].id) == {}


async def test_i_termini_della_coda_per_alias(db_session, anagrafica, deciso):
    term, _ = deciso
    assert await queue_terms_by_alias(db_session, anagrafica["pomodori"].id) == {
        "pomodori pelati": term
    }


async def test_un_alias_che_non_c_e(db_session):
    with pytest.raises(LookupError):
        await delete_alias(db_session, uuid.uuid4())
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `cd backend && PATH="$PWD/.venv/bin:$PATH" python -m pytest tests/services/test_registry.py -v`
Expected: FAIL in raccolta — `ImportError: cannot import name 'delete_alias' from 'app.services.registry'`.

- [ ] **Step 3: implementazione minima**

In `backend/app/services/registry.py`, agli import:

```python
from app.db.models.recipe_import import ImportTerm
```

In fondo al modulo:

```python
async def queue_terms_by_alias(
    session: AsyncSession, ingredient_id: uuid.UUID
) -> dict[str, ImportTerm]:
    """I termini della coda decisi su questo ingrediente, per l'alias che hanno scritto.

    La chiave è normalizzata come in `remember_alias` (strip e minuscole), in Python e
    non in SQL: è la stessa operazione che ha scritto l'alias, quindi le due non
    possono dare risposte diverse sullo stesso nome.
    """
    rows = await session.execute(
        select(ImportTerm).where(ImportTerm.ingredient_id == ingredient_id)
    )
    return {term.display_name.strip().lower(): term for term in rows.scalars()}


async def _alias(session: AsyncSession, alias_id: uuid.UUID) -> IngredientAlias:
    alias = await session.get(IngredientAlias, alias_id)
    if alias is None:
        raise LookupError(f"nessun alias {alias_id}")
    return alias


async def _refuse_import_alias(session: AsyncSession, alias: IngredientAlias) -> None:
    """Un alias `import` che ha il suo termine nella coda è la metà di una decisione.

    Spostarlo da qui lascerebbe la coda a dire una cosa e l'anagrafica un'altra: si
    corregge dalla coda, dove R11 mostra anche le decisioni prese a mano. Un alias
    `import` *senza* termine — il vecchio nome scritto da un `merge` o da un `rename`
    della CLI prima di S9 — non è la metà di niente, e si corregge da qui: rifiutarlo
    sarebbe un vicolo cieco, perché nella coda non c'è niente da correggere.
    """
    if alias.source != "import":
        return
    term = (await queue_terms_by_alias(session, alias.ingredient_id)).get(alias.alias)
    if term is not None:
        raise RegistryRefusal(
            RefusalCode.IMPORT_ALIAS,
            f"«{alias.alias}» viene dalla decisione su «{term.display_name.strip()}» nella "
            "coda: si corregge da lì, così la coda e l'anagrafica dicono la stessa cosa.",
            term,
        )


async def move_alias(
    session: AsyncSession, alias_id: uuid.UUID, target_id: uuid.UUID
) -> IngredientAlias | None:
    """L'alias passa a `target_id`. Torna la riga che ora lo porta su quell'ingrediente,
    oppure `None`: se l'alias era il nome stesso dell'ingrediente d'arrivo (un alias
    uguale al nome è un doppione, e sparisce) o se un terzo ingrediente lo porta già.

    `remember_alias` e non un inserimento diretto: è la regola che impedisce lo stesso
    alias su due ingredienti, cioè un autocomplete con due risposte.
    """
    alias = await _alias(session, alias_id)
    target = await _ingredient(session, target_id)
    await _refuse_import_alias(session, alias)
    text = alias.alias
    await session.delete(alias)
    await session.flush()
    if text != target.name:
        await remember_alias(session, target.id, text, source=MANUAL_ALIAS_SOURCE)
    return (
        await session.execute(
            select(IngredientAlias).where(
                IngredientAlias.ingredient_id == target.id, IngredientAlias.alias == text
            )
        )
    ).scalars().first()


async def delete_alias(session: AsyncSession, alias_id: uuid.UUID) -> None:
    """Toglie un alias che non è la metà di una decisione della coda."""
    alias = await _alias(session, alias_id)
    await _refuse_import_alias(session, alias)
    await session.delete(alias)
    await session.flush()
```

- [ ] **Step 4: eseguilo e verifica che passi**

Run: `cd backend && PATH="$PWD/.venv/bin:$PATH" python -m pytest tests/services/test_registry.py -v`
Expected: PASS, tutti.

- [ ] **Step 5: commit**

```bash
git add backend/app/services/registry.py backend/tests/services/test_registry.py
git commit -m "$(cat <<'EOF'
anagrafica: gli alias si spostano e si tolgono, tranne quelli che sono metà della coda

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---
### Task 3: Le cotture si ri-legano, e l'annullamento smette di rifiutare

**File:**
- Modify: `backend/app/services/recipe_import/materialize.py` (import; `Materialized`,
  righe 37–40; il ciclo di `materialize_ready`, righe 63–159)
- Modify: `backend/app/services/recipe_import/undo.py` (docstring del modulo, righe
  1–17; `CookedRecipesAffected`, righe 38–47; `undo_decision`, righe 79–143)
- Modify: `backend/app/schemas/recipe_import.py` (via `UndoRequest`, righe 91–98)
- Modify: `backend/app/api/imports.py` (import, righe 33–54; la rotta `undo`, righe 246–284)
- Modify: `backend/app/cli/fix_registry.py` (import di riga 69; `_undo`, righe 158–165)
- Modify: `backend/tests/conftest.py` (la fixture `dal_database`)
- Modify: `CLAUDE.md` (la sezione sull'import)
- Test: `backend/tests/services/test_undo.py`, `backend/tests/api/test_imports_undo.py`

**Interfacce:**
- Consuma: niente dei Task 1–2.
- Produce:
  - `COOKING_EVENTS_KEY = "cooking_event_ids"` in `app/services/recipe_import/materialize.py`
  - `Materialized(created: int, skipped: int, relinked: int)`
  - `undo_decision(session, term) -> Undone` (senza `force`; non solleva più per le cotture)
  - `CookedRecipesAffected` e `UndoRequest` non esistono più
  - fixture `dal_database(model, key)` in `backend/tests/conftest.py`: rilegge una riga da
    una sessione nuova sulla stessa connessione.

- [ ] **Step 1: scrivi il test che fallisce**

In `backend/tests/conftest.py`, in fondo:

```python
@pytest_asyncio.fixture
async def dal_database(db_session):
    """Rilegge una riga da una sessione nuova, sulla stessa connessione del test.

    Vede il database e non la memoria di `db_session`: un JSONB mutato invece che
    riassegnato sembra giusto nell'identity map e non arriva mai al database, e solo
    una lettura da fuori se ne accorge (spec S9 §10). La sessione nuova si unisce alla
    transazione del test senza savepoint, e chiuderla non annulla niente.
    """

    async def leggi(model, key):
        await db_session.flush()
        fresca = AsyncSession(bind=db_session.bind, expire_on_commit=False)
        try:
            return await fresca.get(model, key)
        finally:
            await fresca.close()

    return leggi
```

In `backend/tests/services/test_undo.py`:
- togli `import pytest` (riga 13): serviva solo al test che se ne va;
- la riga 28 diventa `from app.services.recipe_import.undo import undo_decision`, e
  sotto aggiungi
  ```python
  from app.services.recipe_import.manual import ManualDecision, decide_by_hand
  from app.services.recipe_import.materialize import materialize_ready
  ```
- **sostituisci** i due test `test_una_ricetta_gia_cucinata_blocca_finche_non_si_insiste`
  e `test_con_force_si_procede_e_lo_storico_resta_orfano` (righe 119–153) con:

```python
async def test_una_ricetta_gia_cucinata_non_blocca_e_la_cottura_aspetta_nella_pagina(
    db_session, deciso, dal_database
):
    """Fino a S9 qui c'era un rifiuto, e un `force` per superarlo: cancellando la
    ricetta `cooking_events.recipe_id` diventava NULL per sempre. Ora gli id delle
    cotture passano nel `payload` della pagina prima della cancellazione.

    La pagina si rilegge da una sessione nuova: un `payload` mutato invece che
    riassegnato sembrerebbe giusto nella memoria di `db_session` e non arriverebbe mai
    al database (spec §10). Scritto così, questo test lo vede.
    """
    term, _, recipe, page = deciso
    evento = CookingEvent(recipe_id=recipe.id, servings=2, snapshot={"titolo": "Pasta allo speck"})
    db_session.add(evento)
    await db_session.flush()
    evento_id, page_id = evento.id, page.id

    esito = await undo_decision(db_session, term)

    assert esito.recipes_requeued == 1
    pagina = await dal_database(RecipeImport, page_id)
    assert pagina.payload["cooking_event_ids"] == [str(evento_id)]
    assert pagina.payload["title"] == "Pasta allo speck"
    cottura = await dal_database(CookingEvent, evento_id)
    # senza ricetta per ora, e con il suo snapshot: la ritrova quando la pagina torna
    assert cottura.recipe_id is None
    assert cottura.snapshot == {"titolo": "Pasta allo speck"}


async def test_la_cottura_ritrova_la_ricetta_quando_la_pagina_torna(db_session, deciso, dal_database):
    """La pagina lasciata in coda tiene gli id finché il termine non ha di nuovo una
    decisione; allora torna ricetta, e la cottura con lei (spec §5.2 e §9.3)."""
    term, _, recipe, page = deciso
    evento = CookingEvent(recipe_id=recipe.id, servings=2, snapshot={})
    db_session.add(evento)
    await db_session.flush()
    evento_id, page_id = evento.id, page.id

    await undo_decision(db_session, term)
    # il termine è in coda: la pagina aspetta, e la cottura con lei
    assert (await materialize_ready(db_session, GIALLOZAFFERANO)).created == 0

    pancetta = await create_ingredient(
        db_session, name="pancetta", display_name="Pancetta", category=IngredientCategory.CARNE
    )
    await decide_by_hand(db_session, term, ManualDecision(action="map", ingredient_id=pancetta.id))
    esito = await materialize_ready(db_session, GIALLOZAFFERANO)

    assert esito.created == 1
    assert esito.relinked == 1
    pagina = await dal_database(RecipeImport, page_id)
    cottura = await dal_database(CookingEvent, evento_id)
    assert pagina.recipe_id is not None
    assert cottura.recipe_id == pagina.recipe_id
    assert "cooking_event_ids" not in pagina.payload
```

In `backend/tests/api/test_imports_undo.py`:
- la prima riga della docstring diventa `"""La rotta dell'annullamento, che dalla S9 non chiede più conferma.`
- **sostituisci** `test_una_ricetta_cucinata_risponde_409_col_numero` e
  `test_con_force_procede` (righe 66–90) con:

```python
async def test_una_ricetta_cucinata_non_blocca_piu_l_annullamento(logged_client, db_session):
    """Fino a S9 qui c'era un 409 che chiedeva conferma. Le cotture ora si ri-legano
    (spec §5.2): l'annullamento non scollega più niente, e non c'è niente da
    confermare."""
    term, recipe = await prepara(db_session)
    db_session.add(CookingEvent(recipe_id=recipe.id, servings=2, snapshot={}))
    await db_session.flush()

    response = await logged_client.post(f"/api/v1/imports/terms/{term.id}/undo", json={})

    assert response.status_code == 200
    assert response.json()["recipes_requeued"] == 1
    await db_session.refresh(term)
    assert term.decision == TermDecision.PENDING


async def test_un_corpo_con_force_di_una_pwa_vecchia_non_rompe_niente(logged_client, db_session):
    """Una PWA con la cache di prima manda ancora `{"force": ...}`: la rotta lo ignora."""
    term, _ = await prepara(db_session)

    response = await logged_client.post(
        f"/api/v1/imports/terms/{term.id}/undo", json={"force": True}
    )

    assert response.status_code == 200
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `cd backend && PATH="$PWD/.venv/bin:$PATH" python -m pytest tests/services/test_undo.py tests/api/test_imports_undo.py -v`
Expected: FAIL —
`test_una_ricetta_gia_cucinata_non_blocca_e_la_cottura_aspetta_nella_pagina` con
`CookedRecipesAffected`, `test_la_cottura_ritrova_la_ricetta_quando_la_pagina_torna` con
`CookedRecipesAffected`, `test_una_ricetta_cucinata_non_blocca_piu_l_annullamento` con
`assert 409 == 200`.

- [ ] **Step 3: implementazione minima**

**`materialize.py`.** Gli import diventano:

```python
import uuid
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingredient import Ingredient
from app.db.models.recipe import CookingEvent, RecipeSource
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportState, RecipeImport, TermDecision
```

(il resto degli import resta com'è). Dopo `EMPTY_REASON`:

```python
# La chiave del `payload` dove `undo_decision` lascia gli id delle cotture della ricetta
# che ha cancellato. La ricetta rifatta da questa pagina le riprende (S9 §5.2).
COOKING_EVENTS_KEY = "cooking_event_ids"
```

`Materialized` diventa:

```python
@dataclass(frozen=True)
class Materialized:
    created: int
    skipped: int
    # le cotture che hanno ritrovato la loro ricetta in questo giro
    relinked: int
```

Prima di `materialize_ready`:

```python
async def _relink_cooking_events(
    session: AsyncSession, page: RecipeImport, recipe_id: uuid.UUID
) -> int:
    """Rimette sulla ricetta rifatta le cotture che aspettavano nel `payload`.

    `recipe_id IS NULL` nella condizione: una cottura che nel frattempo qualcuno ha
    legato ad altro non si ruba. La chiave si toglie riassegnando il dizionario —
    SQLAlchemy non vede le mutazioni dentro un JSONB, e una `pop` sparirebbe al flush
    senza un errore.
    """
    waiting = page.payload.get(COOKING_EVENTS_KEY)
    if not waiting:
        return 0
    result = await session.execute(
        update(CookingEvent)
        .where(
            CookingEvent.id.in_([uuid.UUID(str(value)) for value in waiting]),
            CookingEvent.recipe_id.is_(None),
        )
        .values(recipe_id=recipe_id)
    )
    page.payload = {key: value for key, value in page.payload.items() if key != COOKING_EVENTS_KEY}
    return result.rowcount or 0
```

In `materialize_ready`: accanto a `created = 0` e `skipped = 0` aggiungi `relinked = 0`;
dopo `page.recipe_id = recipe.id` e `created += 1` aggiungi

```python
        relinked += await _relink_cooking_events(session, page, recipe.id)
```

e l'ultima riga diventa `return Materialized(created=created, skipped=skipped, relinked=relinked)`.

**`undo.py`.** Il terzo paragrafo della docstring del modulo («Nelle ricette cancellate
c'è una cosa sola da preservare…») diventa:

```
Nelle ricette cancellate ci sono due cose da preservare, e passano entrambe nel
`payload` prima della cancellazione. Il costo, l'unico campo che l'applicazione lascia
modificare a mano (R9). E le cotture: `cooking_events.recipe_id` è ON DELETE SET NULL,
quindi cancellare la ricetta scollegherebbe lo storico per sempre. Fino a S9 questo
file rifiutava con `CookedRecipesAffected` e chiedeva conferma; ora scrive gli id delle
cotture alla chiave `cooking_event_ids` (`COOKING_EVENTS_KEY`), e `materialize_ready`
li rimette sulla ricetta rifatta. Una pagina che resta in coda tiene gli id finché non
torna ricetta: la cottura è senza ricetta per quel tempo, e la ritrova dopo. Il giorno
in cui una ricetta importata potrà essere modificata in altro (R10), questo file va
ripensato.
```

Togli la classe `CookedRecipesAffected` (righe 38–47). Agli import aggiungi
`from app.services.recipe_import.materialize import COOKING_EVENTS_KEY`. `undo_decision`
diventa:

```python
async def undo_decision(session: AsyncSession, term: ImportTerm) -> Undone:
    """Rimette il mondo come era prima che quella decisione fosse presa.

    Quattro effetti, in quest'ordine: le pagine e le ricette, l'alias, l'ingrediente, il
    termine. Nessuno rifiuta: le ricette già cucinate si rifanno come le altre, perché
    le loro cotture aspettano nel `payload` (vedi la docstring del modulo).
    """
    pages = await _imported_pages_with(session, term)

    # le ricette si rifanno da payload: cancellarle è il modo corretto, non una
    # scorciatoia
    requeued = 0
    for page in pages:
        recipe = await session.get(Recipe, page.recipe_id)
        if recipe is not None:
            payload = dict(page.payload)
            # Il costo si sceglie anche a mano dal dettaglio (R9): è l'unica modifica
            # che una ricetta importata può ricevere, e rifacendola da `payload` si
            # perderebbe. Scritto nel `payload`, `materialize_ready` lo rilegge da lì.
            if recipe.cost != cost_in_scale(payload.get("cost")):
                payload["cost"] = recipe.cost
            cooked = [
                str(event_id)
                for event_id in (
                    await session.execute(
                        select(CookingEvent.id).where(CookingEvent.recipe_id == recipe.id)
                    )
                ).scalars()
            ]
            if cooked:
                payload[COOKING_EVENTS_KEY] = sorted(
                    {*payload.get(COOKING_EVENTS_KEY, []), *cooked}
                )
            # Riassegnato e non mutato: SQLAlchemy non vede le mutazioni in un JSONB.
            if payload != page.payload:
                page.payload = payload
            await session.delete(recipe)
        page.state = ImportState.PENDING
        page.recipe_id = None
        requeued += 1
```

Da `ingredient_id: uuid.UUID | None = term.ingredient_id` in giù la funzione resta
com'è.

**`schemas/recipe_import.py`.** Togli la classe `UndoRequest` (righe 91–98).

**`api/imports.py`.** Togli `UndoRequest` dall'import di `app.schemas.recipe_import`;
l'import di riga 54 diventa `from app.services.recipe_import.undo import undo_decision`.
La rotta diventa:

```python
@router.post("/terms/{term_id}/undo", response_model=UndoOut)
async def undo(
    term_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> UndoOut:
    """Rimette un termine deciso in coda, e con lui il mondo che quella decisione ha mosso.

    Non è un editor: dopo questo, il termine si decide a mano con la scheda di sempre.
    Non chiede conferma per le ricette già cucinate: le loro cotture aspettano nel
    `payload` della pagina e tornano sulla ricetta rifatta (S9 §5.2). Un corpo con
    `force`, mandato da una PWA con la cache di prima, si ignora.
    """
    term = await get_term(session, term_id)
    if term is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "termine inesistente")
    if term.decision == TermDecision.PENDING:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"«{term.display_name}» è già in coda: non c'è nessuna decisione da disfare.",
        )

    undone = await undo_decision(session, term)
    numbers = await counts(session, GIALLOZAFFERANO)
    await session.commit()
    return UndoOut(
        recipes_requeued=undone.recipes_requeued,
        ingredient_deleted=undone.ingredient_deleted,
        remaining_terms=numbers.pending_terms,
    )
```

**`cli/fix_registry.py`.** L'import di riga 69 diventa
`from app.services.recipe_import.undo import undo_decision`, e `_undo`:

```python
async def _undo(session: AsyncSession, term: ImportTerm) -> int:
    return (await undo_decision(session, term)).recipes_requeued
```

**`CLAUDE.md`**, nella voce «Import brings in recipes, not random new ingredients.»:
dopo la frase che finisce con «…the created ingredient and the materialized recipes
back.» aggiungi:

```
Undo never refuses over recipes already cooked: the ids of their cooking events wait
in the page's `payload` under `cooking_event_ids`, and `materialize_ready` puts them
back on the rebuilt recipe (S9 §5.2).
```

- [ ] **Step 4: eseguilo e verifica che passi**

Run:
```bash
(cd backend && PATH="$PWD/.venv/bin:$PATH" python -m pytest tests/services/test_undo.py tests/api/test_imports_undo.py tests/test_fix_registry_cli.py tests/api/test_imports.py tests/api/test_imports_decide.py -v)
grep -rn "CookedRecipesAffected\|UndoRequest" backend/app backend/tests
```
Expected: PASS, tutti; il `grep` trova una riga sola, la docstring di `undo.py` che
racconta perché la classe non c'è più.

- [ ] **Step 5: commit**

```bash
git add backend/app/services/recipe_import/materialize.py backend/app/services/recipe_import/undo.py backend/app/schemas/recipe_import.py backend/app/api/imports.py backend/app/cli/fix_registry.py backend/tests/conftest.py backend/tests/services/test_undo.py backend/tests/api/test_imports_undo.py CLAUDE.md
git commit -m "$(cat <<'EOF'
import: le cotture aspettano nella pagina e tornano sulla ricetta rifatta

L'annullamento non rifiuta più per le ricette già cucinate: via
CookedRecipesAffected e il force di UndoRequest.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: La coda smette di chiedere conferma

**File:**
- Modify: `frontend/src/features/recipe-import/api.ts` (`undoTerm`, righe 38–45)
- Modify: `frontend/src/features/recipe-import/ImportQueueScreen.tsx` (docstring di
  `undoErrorMessage` e `undoResultMessage`; `undoConfirm`; la mutazione `undo`; il
  dialogo)
- Test: `frontend/src/features/recipe-import/ImportQueueScreen.test.tsx`

**Interfacce:**
- Consuma: la rotta del Task 3, che non chiede più conferma.
- Produce: `undoTerm(termId: string): Promise<UndoResult>` (senza `force`, senza corpo).

- [ ] **Step 1: scrivi il test che fallisce**

In `ImportQueueScreen.test.tsx` **togli** i tre test «un 409 sull'annullamento chiede
conferma invece di fallire», «confermare l'annullamento dopo il 409 lo rimanda con
`force`» e «un 409 sull'annullamento che torna anche dopo `force` è un rifiuto: il
dialogo si chiude», e al loro posto scrivi:

```tsx
  it("un 409 sull'annullamento è un rifiuto detto col suo motivo, non una domanda", async () => {
    // Dalla S9 il backend non chiede più conferma per le ricette già cucinate: le
    // cotture si ri-legano alla ricetta rifatta. L'unico 409 che resta è il termine
    // già in coda, e lì non c'è niente da confermare.
    renderQueue({
      pending: [],
      decided: [
        {
          id: "t9", display_name: "Rigatoni", occurrences: 3, suggestion: null,
          waiting_titles: [], decided_by: "ai", decided_action: "map",
          decided_name: "pasta", decided_at: "2026-09-20T10:00:00Z",
        },
      ],
      undoStatus: 409,
      undoDetail: "«Rigatoni» è già in coda: non c'è nessuna decisione da disfare.",
    });

    await userEvent.click(
      await screen.findByRole("button", { name: /annulla la decisione su «Rigatoni»/i })
    );

    expect(
      await screen.findByText(/«Rigatoni» è già in coda: non c'è nessuna decisione da disfare\./)
    ).toBeInTheDocument();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /rifai comunque/i })).not.toBeInTheDocument();
  });

  it("l'annullamento non manda più `force`", async () => {
    const spy = renderQueue({
      pending: [],
      decided: [
        {
          id: "t9", display_name: "Rigatoni", occurrences: 3, suggestion: null,
          waiting_titles: [], decided_by: "ai", decided_action: "map",
          decided_name: "pasta", decided_at: "2026-09-20T10:00:00Z",
        },
      ],
      undoStatus: 200,
    });

    await userEvent.click(
      await screen.findByRole("button", { name: /annulla la decisione su «Rigatoni»/i })
    );

    await waitFor(() => {
      const undo = spy.mock.calls.find(
        ([url, init]) =>
          String(url).includes("/undo") && (init as RequestInit | undefined)?.method === "POST"
      );
      expect(undo).toBeDefined();
      expect((undo![1] as RequestInit).body).toBeUndefined();
    });
  });
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `cd frontend && npx vitest run src/features/recipe-import/ImportQueueScreen.test.tsx`
Expected: FAIL — il primo test trova l'`alertdialog` (il 409 apre ancora il dialogo), il
secondo trova il corpo `{"force":false}` invece di `undefined`.

- [ ] **Step 3: implementazione minima**

`api.ts`, `undoTerm` diventa:

```ts
/** Rimette un termine deciso in coda, e con lui le ricette che ne erano nate. Non
 * chiede conferma: dalla S9 le cotture delle ricette rifatte non si perdono,
 * aspettano nella pagina e tornano sulla ricetta nuova. */
export function undoTerm(termId: string) {
  return apiFetch<UndoResult>(`/imports/terms/${termId}/undo`, { method: "POST" });
}
```

`ImportQueueScreen.tsx`:
- la docstring di `undoErrorMessage` diventa:
  ```ts
  /** Il messaggio da mostrare quando annullare una decisione fallisce.
   *
   * Dalla S9 non c'è più un 409 che chiede conferma: le cotture delle ricette rifatte
   * si ri-legano, quindi annullare non scollega niente. Da qui passano i rifiuti veri —
   * il 409 del termine già in coda, che nel suo `detail` dice perché — e i guasti. È un
   * 4xx come quello di `decisionErrorMessage`: stessa forma, stesso motivo per
   * mostrarlo verbatim.
   */
  ```
- nella docstring di `undoResultMessage`, la frase «dall'unica conferma distruttiva di
  questa funzione ("Rifai comunque")» diventa «dall'unico gesto distruttivo di questa
  schermata»;
- togli lo stato `undoConfirm` (le tre righe `const [undoConfirm, setUndoConfirm] = …`);
- la mutazione `undo` diventa:
  ```ts
  const undo = useMutation({
    mutationFn: (termId: string) => undoTerm(termId),
    onMutate: () => {
      // un nuovo tentativo non deve restare sull'errore del precedente: senza
      // questo, annullare un secondo termine con successo lascerebbe in vista
      // l'alert del primo tentativo fallito
      setUndoError(null);
    },
    onSuccess: (result) => {
      setLastUndo({
        recipesRequeued: result.recipes_requeued,
        ingredientDeleted: result.ingredient_deleted,
      });
      setLastRun(null);
      queryClient.invalidateQueries({ queryKey: ["import-terms"] });
      queryClient.invalidateQueries({ queryKey: ["import-status"] });
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
    },
    // ogni esito diverso dal successo è un rifiuto vero, e si vede
    onError: (error) => setUndoError(undoErrorMessage(error)),
  });
  ```
- in `DecidedTermRow`, `onUndo={() => undo.mutate(term.id)}`;
- togli tutto il blocco `{undoConfirm && ( <div role="alertdialog" …> … </div> )}` in
  fondo alla schermata.

- [ ] **Step 4: eseguilo e verifica che passi**

Run: `cd frontend && npx vitest run src/features/recipe-import && npm run lint && npm run typecheck`
Expected: PASS; lint e typecheck puliti (nessun `undoConfirm` né `force` rimasto:
`grep -rn "force\|undoConfirm\|Rifai comunque" src/features/recipe-import` restituisce
solo i test appena scritti).

- [ ] **Step 5: commit**

```bash
git add frontend/src/features/recipe-import/api.ts frontend/src/features/recipe-import/ImportQueueScreen.tsx frontend/src/features/recipe-import/ImportQueueScreen.test.tsx
git commit -m "$(cat <<'EOF'
coda: annullare non chiede più conferma per le ricette già cucinate

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: La fusione, nel servizio

**File:**
- Modify: `backend/app/services/registry.py`
- Test: `backend/tests/services/test_registry_merge.py`

**Interfacce:**
- Consuma: `_ingredient`, `RegistryRefusal`, `RefusalCode`, `MANUAL_ALIAS_SOURCE`
  (Task 1); `COOKING_EVENTS_KEY`, `Materialized.relinked` (Task 3); `undo_decision`,
  `decide_by_hand`, `ManualDecision`, `DecisionRefused`, `materialize_ready`,
  `merge_quantities`, `stronger`, `delete_ingredient_if_unused`, `remember_alias`.
- Produce:
  - `@dataclass(frozen=True) MergeCounts(loser_name: str, winner_name: str, recipes_rebuilt: int, recipe_lines_moved: int, pantry_items: int, shopping_items: int, products: int, aliases: int, cooking_events_relinked: int)`
  - `async merge_ingredients(session, loser_id, winner_id) -> MergeCounts`
  - rifiuti `SAME_INGREDIENT`, `KIND_MISMATCH` (con `obstacle` = il vincitore),
    `DECISION_REFUSED`, `STILL_USED`.

- [ ] **Step 1: scrivi il test che fallisce**

Crea `backend/tests/services/test_registry_merge.py`:

```python
"""La fusione di due ingredienti (S9 §5): tutto quel che punta al perdente passa al
vincitore, le ricette dell'import si rifanno, e le cotture ritrovano la ricetta.

Il mondo di prova ha un pezzo per ogni tabella che la fusione tocca: due pagine
dell'import (una con le due righe che diventano una), una ricetta scritta dall'AI, un
elemento di dispensa, una voce di lista, un prodotto, un alias scritto a mano.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.db.models.recipe import CookingEvent, RecipeIngredient, RecipeSource
from app.db.models.recipe_import import (
    GIALLOZAFFERANO,
    ImportState,
    ImportTerm,
    RecipeImport,
    TermDecision,
)
from app.db.models.shopping import ShoppingListItem, ShoppingReason, ShoppingStatus
from app.domain.rules import PantryStatus
from app.repositories.imports import store_page
from app.repositories.ingredients import add_alias, remember_alias
from app.repositories.recipes import create_recipe
from app.services.recipe_import.materialize import materialize_ready
from app.services.registry import (
    MergeCounts,
    RefusalCode,
    RegistryRefusal,
    merge_ingredients,
)

SUGO = "https://esempio.invalid/sugo"
BRUSCHETTA = "https://esempio.invalid/bruschetta"
PAGINE = {
    SUGO: ("Sugo semplice", [("k-pomodori", "Pomodori", "400 g"), ("k-basilico", "Basilico", "q.b.")]),
    BRUSCHETTA: ("Bruschetta", [("k-pomodori", "Pomodori", "2"), ("k-pomodoro", "Pomodoro", "1")]),
}


def _payload(title: str, righe: list[tuple[str, str, str]]) -> dict:
    return {
        "title": title, "description": None, "instructions": "Cuoci.", "servings": 2,
        "ingredients": [
            {"key": key, "name": name, "quantity_text": quantity} for key, name, quantity in righe
        ],
    }


@pytest_asyncio.fixture
async def mondo(db_session):
    def voce(name: str, display: str, category: str) -> Ingredient:
        return Ingredient(name=name, display_name=display, category=category)

    voci = {
        "pomodoro": voce("pomodoro", "Pomodoro", IngredientCategory.VERDURA),
        "pomodori": voce("pomodori", "Pomodori", IngredientCategory.VERDURA),
        "basilico": voce("basilico", "Basilico", IngredientCategory.SPEZIE),
        "detersivo": voce("detersivo", "Detersivo", IngredientCategory.CASA),
    }
    db_session.add_all(voci.values())
    await db_session.flush()

    def termine(key: str, display: str, voce_: str) -> ImportTerm:
        return ImportTerm(
            source=GIALLOZAFFERANO, term_key=key, display_name=display, occurrences=1,
            decision=TermDecision.MAPPED, ingredient_id=voci[voce_].id, decided_by="ai",
            decided_at=datetime.now(UTC),
        )

    termini = [
        termine("k-pomodori", "Pomodori", "pomodori"),
        termine("k-pomodoro", "Pomodoro", "pomodoro"),
        termine("k-basilico", "Basilico", "basilico"),
    ]
    db_session.add_all(termini)
    await db_session.flush()
    for term in termini:
        await remember_alias(db_session, term.ingredient_id, term.display_name)

    for url, (title, righe) in PAGINE.items():
        await store_page(db_session, source=GIALLOZAFFERANO, url=url, payload=_payload(title, righe))
    await materialize_ready(db_session, GIALLOZAFFERANO)

    await add_alias(db_session, voci["pomodori"].id, "pomodorini", source="manual")
    scritta = await create_recipe(
        db_session, title="Insalata dell'AI", description=None, instructions="Taglia.",
        servings=1, source=RecipeSource.AI, source_ref=None,
        ingredients=[(voci["pomodori"].id, "primary", "3", None)], embedding=None,
    )
    db_session.add(PantryItem(ingredient_id=voci["pomodori"].id, status=PantryStatus.AVAILABLE))
    db_session.add(ShoppingListItem(
        raw_text="pomodori", ingredient_id=voci["pomodori"].id,
        status=ShoppingStatus.PENDING, reason=ShoppingReason.MANUAL,
    ))
    db_session.add(Product(ingredient_id=voci["pomodori"].id, name="Pelati Cirio", source="custom"))
    await db_session.flush()
    return {**voci, "scritta": scritta}


async def _pagina(db_session, url: str) -> RecipeImport:
    return (
        await db_session.execute(select(RecipeImport).where(RecipeImport.url == url))
    ).scalar_one()


async def _righe(db_session, url: str) -> dict[str, str | None]:
    """Le righe della ricetta nata da quella pagina: ingrediente → dose."""
    page = await _pagina(db_session, url)
    assert page.state == ImportState.IMPORTED, page.state
    rows = await db_session.execute(
        select(Ingredient.name, RecipeIngredient.quantity_text)
        .join(Ingredient, Ingredient.id == RecipeIngredient.ingredient_id)
        .where(RecipeIngredient.recipe_id == page.recipe_id)
    )
    return dict(rows.all())


async def _chi_ha_l_alias(db_session, alias: str) -> list[str]:
    rows = await db_session.execute(
        select(Ingredient.name)
        .join(IngredientAlias, IngredientAlias.ingredient_id == Ingredient.id)
        .where(IngredientAlias.alias == alias)
    )
    return list(rows.scalars())


async def test_unire_porta_tutto_sul_vincitore_e_lo_conta(db_session, mondo):
    perdente, vincitore = mondo["pomodori"].id, mondo["pomodoro"].id

    conti = await merge_ingredients(db_session, perdente, vincitore)

    assert conti == MergeCounts(
        loser_name="pomodori", winner_name="pomodoro",
        recipes_rebuilt=2, recipe_lines_moved=1, pantry_items=1, shopping_items=1,
        products=1, aliases=2, cooking_events_relinked=0,
    )
    assert await db_session.get(Ingredient, perdente) is None
    assert "pomodoro" in await _righe(db_session, SUGO)
    # le due righe della bruschetta diventano una, come nella materializzazione
    assert await _righe(db_session, BRUSCHETTA) == {"pomodoro": "2 + 1"}
    # chi scrive ancora «pomodori» o «pomodorini» nella lista trova il pomodoro
    assert await _chi_ha_l_alias(db_session, "pomodori") == ["pomodoro"]
    assert await _chi_ha_l_alias(db_session, "pomodorini") == ["pomodoro"]
    lista = (await db_session.execute(select(ShoppingListItem))).scalar_one()
    assert lista.ingredient_id == vincitore
    scritta = (
        await db_session.execute(
            select(RecipeIngredient.ingredient_id).where(
                RecipeIngredient.recipe_id == mondo["scritta"].id
            )
        )
    ).scalars().all()
    assert scritta == [vincitore]


async def test_le_cotture_della_ricetta_rifatta_si_ri_legano(db_session, mondo, dal_database):
    """Il caso per cui la fusione è sicura da offrire a un tocco (spec §5.2, §9.3): una
    ricetta importata già cucinata si rifà, e la cottura punta alla ricetta nuova."""
    pagina = await _pagina(db_session, SUGO)
    evento = CookingEvent(recipe_id=pagina.recipe_id, servings=2, snapshot={"title": "Sugo semplice"})
    db_session.add(evento)
    await db_session.flush()
    evento_id, pagina_id, ricetta_vecchia = evento.id, pagina.id, pagina.recipe_id

    conti = await merge_ingredients(db_session, mondo["pomodori"].id, mondo["pomodoro"].id)

    assert conti.cooking_events_relinked == 1
    pagina = await dal_database(RecipeImport, pagina_id)
    cottura = await dal_database(CookingEvent, evento_id)
    assert pagina.recipe_id not in (None, ricetta_vecchia)
    assert cottura.recipe_id == pagina.recipe_id
    assert "cooking_event_ids" not in pagina.payload


async def test_un_alimento_e_una_voce_non_alimentare_non_si_uniscono(db_session, mondo):
    """Non è un vicolo cieco: il messaggio dice il passo (spec §5.3)."""
    with pytest.raises(RegistryRefusal) as rifiuto:
        await merge_ingredients(db_session, mondo["pomodori"].id, mondo["detersivo"].id)

    assert rifiuto.value.code == RefusalCode.KIND_MISMATCH
    assert rifiuto.value.obstacle is mondo["detersivo"]
    assert (
        "Prima porta «Pomodori» nello stesso reparto di «Detersivo», poi uniscili."
        in rifiuto.value.message
    )
    assert await db_session.get(Ingredient, mondo["pomodori"].id) is not None


async def test_un_ingrediente_non_si_unisce_a_se_stesso(db_session, mondo):
    with pytest.raises(RegistryRefusal) as rifiuto:
        await merge_ingredients(db_session, mondo["pomodoro"].id, mondo["pomodoro"].id)
    assert rifiuto.value.code == RefusalCode.SAME_INGREDIENT
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `cd backend && PATH="$PWD/.venv/bin:$PATH" python -m pytest tests/services/test_registry_merge.py -v`
Expected: FAIL in raccolta — `ImportError: cannot import name 'MergeCounts' from 'app.services.registry'`.

- [ ] **Step 3: implementazione minima**

In `backend/app/services/registry.py` il blocco degli import diventa:

```python
import uuid
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.db.models.recipe import Recipe, RecipeIngredient
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm
from app.db.models.shopping import ShoppingListItem
from app.domain.rules import IngredientKind, IngredientRole, kind_for_category
from app.repositories.ingredients import (
    canonical_name,
    delete_ingredient_if_unused,
    find_by_name,
    remember_alias,
)
from app.services.recipe_import.manual import DecisionRefused, ManualDecision, decide_by_hand
from app.services.recipe_import.materialize import (
    materialize_ready,
    merge_quantities,
    stronger,
)
from app.services.recipe_import.undo import undo_decision
```

Dopo `RecipesInUse`:

```python
@dataclass(frozen=True)
class MergeCounts:
    """Quel che una fusione ha mosso (spec §5.1). Gli stessi numeri escono
    dall'anteprima, perché l'anteprima è questa stessa fusione annullata."""

    loser_name: str
    winner_name: str
    recipes_rebuilt: int  # ricette dell'import rifatte dal loro `payload`
    recipe_lines_moved: int  # righe di ricette non importate, spostate sul vincitore
    pantry_items: int
    shopping_items: int
    products: int
    aliases: int  # alias che il vincitore guadagna, nome del perdente compreso
    cooking_events_relinked: int
```

In fondo al modulo:

```python
async def _repoint(
    session: AsyncSession, model: type, loser_id: uuid.UUID, winner_id: uuid.UUID
) -> int:
    result = await session.execute(
        update(model).where(model.ingredient_id == loser_id).values(ingredient_id=winner_id)
    )
    return result.rowcount or 0


async def _alias_count(session: AsyncSession, ingredient_id: uuid.UUID) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(IngredientAlias)
            .where(IngredientAlias.ingredient_id == ingredient_id)
        )
    ).scalar_one()


async def merge_ingredients(
    session: AsyncSession, loser_id: uuid.UUID, winner_id: uuid.UUID
) -> MergeCounts:
    """Tutto quel che punta al perdente passa al vincitore, e il perdente sparisce.

    Termini dell'import, dispensa, lista, prodotti, righe di ricetta, alias: i termini
    si annullano e si ridecidono sul vincitore, così le loro ricette si rifanno dal
    `payload` invece di una chirurgia su `recipe_ingredients`; le righe delle ricette
    scritte a mano o dall'AI si spostano. Il nome del perdente resta come alias del
    vincitore: chi lo scrive nella lista trova ancora qualcosa. Le pagine rimesse in
    attesa tornano ricette qui dentro, e le loro cotture con loro (§5.2).

    È l'unica correzione che non si annulla: per questo `preview_merge` la esegue
    tutta dentro un SAVEPOINT prima di chiedere conferma.
    """
    loser = await _ingredient(session, loser_id)
    winner = await _ingredient(session, winner_id)
    if loser.id == winner.id:
        raise RegistryRefusal(
            RefusalCode.SAME_INGREDIENT,
            f"«{loser.display_name}» non si unisce a sé stesso: scegli un altro ingrediente.",
        )
    if loser.kind != winner.kind:
        raise RegistryRefusal(
            RefusalCode.KIND_MISMATCH,
            f"«{loser.display_name}» e «{winner.display_name}» stanno in due metà diverse "
            "dell'anagrafica: un alimento e una voce non alimentare non si uniscono. "
            f"Prima porta «{loser.display_name}» nello stesso reparto di "
            f"«{winner.display_name}», poi uniscili.",
            winner,
        )
    loser_name, winner_name = loser.name, winner.name
    # I nomi si fotografano prima: l'annullamento dell'ultimo termine può cancellare
    # l'ingrediente, e i suoi alias con lui. Gli alias con una query e non con
    # `loser.aliases`: `session.get` restituisce l'oggetto che la sessione ha già, e se
    # quella collezione non è mai stata caricata leggerla è un caricamento pigro — in
    # una sessione async, un MissingGreenlet. La CLI non lo vedeva perché trovava
    # l'ingrediente con una `select`, che la carica.
    alias_names = list(
        (
            await session.execute(
                select(IngredientAlias.alias).where(IngredientAlias.ingredient_id == loser.id)
            )
        ).scalars()
    )
    names = [loser.name, loser.display_name, *alias_names]
    aliases_before = await _alias_count(session, winner.id)

    terms = list(
        (await session.execute(select(ImportTerm).where(ImportTerm.ingredient_id == loser_id))).scalars()
    )
    for term in terms:
        role = term.role_override
        await undo_decision(session, term)
        try:
            await decide_by_hand(
                session, term,
                ManualDecision(action="map", ingredient_id=winner.id, role_override=role),
            )
        except DecisionRefused as exc:
            raise RegistryRefusal(
                RefusalCode.DECISION_REFUSED, f"«{term.display_name}»: {exc.message}"
            ) from exc

    pantry_items = await _repoint(session, PantryItem, loser_id, winner.id)
    shopping_items = await _repoint(session, ShoppingListItem, loser_id, winner.id)
    products = await _repoint(session, Product, loser_id, winner.id)

    # Le righe rimaste sono di ricette che non vengono dall'import (scritte a mano o
    # con l'AI): quelle non si rifanno da un payload, si spostano. Se la ricetta ha
    # già una riga del vincitore, le due diventano una come nella materializzazione.
    lines = list(
        (
            await session.execute(
                select(RecipeIngredient).where(RecipeIngredient.ingredient_id == loser_id)
            )
        ).scalars()
    )
    for line in lines:
        twin = (
            await session.execute(
                select(RecipeIngredient).where(
                    RecipeIngredient.recipe_id == line.recipe_id,
                    RecipeIngredient.ingredient_id == winner.id,
                )
            )
        ).scalars().first()
        if twin is None:
            line.ingredient_id = winner.id
            continue
        twin.role = stronger(IngredientRole(twin.role), IngredientRole(line.role))
        twin.quantity_text = merge_quantities(twin.quantity_text, line.quantity_text)
        # «500 g + 50 g» non è una dose che il riporziona sappia leggere: la riga
        # smette di scalare, che è onesto, invece di scalare solo metà.
        twin.quantity_value = None
        twin.quantity_unit_id = None
        await session.delete(line)
    await session.flush()

    await session.execute(delete(IngredientAlias).where(IngredientAlias.ingredient_id == loser_id))
    await session.flush()
    survivor = await session.get(Ingredient, loser_id)
    if survivor is not None:
        # la collezione in memoria ricorda ancora gli alias appena cancellati
        await session.refresh(survivor)
        if not await delete_ingredient_if_unused(session, loser_id):
            raise RegistryRefusal(
                RefusalCode.STILL_USED,
                f"«{loser_name}» è ancora usato dopo l'unione: niente è stato salvato.",
            )
    for name in names:
        if canonical_name(name) != winner_name:
            await remember_alias(session, winner.id, name, source=MANUAL_ALIAS_SOURCE)
    await session.flush()

    materialized = await materialize_ready(session, GIALLOZAFFERANO)
    return MergeCounts(
        loser_name=loser_name,
        winner_name=winner_name,
        recipes_rebuilt=materialized.created,
        recipe_lines_moved=len(lines),
        pantry_items=pantry_items,
        shopping_items=shopping_items,
        products=products,
        aliases=await _alias_count(session, winner.id) - aliases_before,
        cooking_events_relinked=materialized.relinked,
    )
```

- [ ] **Step 4: eseguilo e verifica che passi**

Run: `cd backend && PATH="$PWD/.venv/bin:$PATH" python -m pytest tests/services/test_registry_merge.py tests/services/test_registry.py -v`
Expected: PASS, tutti.

- [ ] **Step 5: commit**

```bash
git add backend/app/services/registry.py backend/tests/services/test_registry_merge.py
git commit -m "$(cat <<'EOF'
anagrafica: la fusione nel servizio, con le cotture che ritrovano la ricetta

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: L'anteprima è la fusione

**File:**
- Modify: `backend/app/services/registry.py`
- Test: `backend/tests/services/test_registry_merge.py`

**Interfacce:**
- Consuma: `merge_ingredients`, `MergeCounts` (Task 5).
- Produce: `async preview_merge(session, loser_id, winner_id) -> MergeCounts`. Dopo la
  chiamata gli oggetti toccati nella sessione sono scaduti: chi chiama rilegge per id.

- [ ] **Step 1: scrivi il test che fallisce**

In `test_registry_merge.py`, agli import: `from app.core.db import Base`, e
`preview_merge` nell'import da `app.services.registry`. In fondo al file:

```python
# Le tabelle che la fusione tocca (spec §5), più `units`: la rimaterializzazione passa
# da `create_recipe`, che può crearne una. `embedding` e `search_tsv` restano fuori dal
# confronto: un vettore non si confronta con `==`, e la seconda è calcolata dalle altre.
TABELLE_TOCCATE = (
    "ingredients", "ingredient_aliases", "import_terms", "recipe_imports", "recipes",
    "recipe_ingredients", "units", "pantry_items", "shopping_list_items", "products",
    "cooking_events",
)
NON_CONFRONTABILI = {"embedding", "search_tsv"}


async def _fotografia(db_session) -> dict[str, list[str]]:
    """Il contenuto di ogni tabella toccata, riga per riga. I conteggi da soli non
    vedrebbero un UPDATE: un elemento di dispensa spostato e rimesso a posto a metà ha
    lo stesso conteggio di uno mai toccato."""
    foto: dict[str, list[str]] = {}
    for nome in TABELLE_TOCCATE:
        tabella = Base.metadata.tables[nome]
        colonne = [c for c in tabella.c if c.name not in NON_CONFRONTABILI]
        righe = (await db_session.execute(select(*colonne))).all()
        foto[nome] = sorted(repr(tuple(riga)) for riga in righe)
    return foto


async def test_l_anteprima_non_scrive_niente_e_dice_i_numeri_della_fusione(db_session, mondo):
    """Spec §5.1 e §9.4: dopo l'anteprima il database è identico — confrontato riga per
    riga, non sul valore di ritorno — e la fusione vera fatta subito dopo dà gli stessi
    numeri. Gli id si prendono prima: dopo il rollback del SAVEPOINT gli oggetti toccati
    sono scaduti, e leggerne un attributo in una sessione async è un MissingGreenlet."""
    pagina = await _pagina(db_session, SUGO)
    db_session.add(CookingEvent(recipe_id=pagina.recipe_id, servings=2, snapshot={}))
    await db_session.flush()
    perdente, vincitore = mondo["pomodori"].id, mondo["pomodoro"].id

    prima = await _fotografia(db_session)
    anteprima = await preview_merge(db_session, perdente, vincitore)
    dopo = await _fotografia(db_session)

    assert dopo == prima
    vera = await merge_ingredients(db_session, perdente, vincitore)
    assert anteprima == vera
    assert vera.cooking_events_relinked == 1


async def test_un_anteprima_rifiutata_non_lascia_niente(db_session, mondo):
    perdente, vincitore = mondo["pomodori"].id, mondo["detersivo"].id
    prima = await _fotografia(db_session)

    with pytest.raises(RegistryRefusal) as rifiuto:
        await preview_merge(db_session, perdente, vincitore)

    assert rifiuto.value.code == RefusalCode.KIND_MISMATCH
    assert await _fotografia(db_session) == prima
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `cd backend && PATH="$PWD/.venv/bin:$PATH" python -m pytest tests/services/test_registry_merge.py -v`
Expected: FAIL in raccolta — `ImportError: cannot import name 'preview_merge'`.

- [ ] **Step 3: implementazione minima**

In fondo a `backend/app/services/registry.py`:

```python
async def preview_merge(
    session: AsyncSession, loser_id: uuid.UUID, winner_id: uuid.UUID
) -> MergeCounts:
    """L'anteprima della fusione è la fusione stessa, dentro un SAVEPOINT annullato.

    Nessuna seconda funzione che stima: i numeri sono quelli dell'operazione, per
    costruzione (spec §5.1). Una stima scritta a parte sarebbe giusta finché i dati sono
    pochi — la lezione di `recipe_search.py` al contrario. Le ricette si rimaterializzano
    anche qui, embedding compresi: sono poche per fusione, ed è il prezzo della garanzia.

    Dopo il rollback del SAVEPOINT gli oggetti che la fusione ha toccato sono scaduti.
    Chi chiama non li rilegge di sfuggita (in una sessione async un attributo scaduto
    letto senza `await` è un MissingGreenlet): le rotte rispondono coi conteggi, che sono
    valori, e i test rileggono per id.
    """
    savepoint = await session.begin_nested()
    try:
        return await merge_ingredients(session, loser_id, winner_id)
    finally:
        await savepoint.rollback()
```

- [ ] **Step 4: eseguilo e verifica che passi**

Run: `cd backend && PATH="$PWD/.venv/bin:$PATH" python -m pytest tests/services/test_registry_merge.py -v`
Expected: PASS. Se la fusione vera dopo l'anteprima alza `MissingGreenlet`, c'è un
attributo scaduto letto senza `await` dentro `merge_ingredients`: la cura è rileggere
l'oggetto con `await session.get(...)` o `await session.refresh(...)`, non togliere il
SAVEPOINT.

- [ ] **Step 5: commit**

```bash
git add backend/app/services/registry.py backend/tests/services/test_registry_merge.py
git commit -m "$(cat <<'EOF'
anagrafica: l'anteprima della fusione è la fusione dentro un SAVEPOINT annullato

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: I prodotti, nel servizio

**File:**
- Modify: `backend/app/services/registry.py`
- Test: `backend/tests/services/test_registry.py`

**Interfacce:**
- Consuma: `_ingredient`, `RegistryRefusal`, `RefusalCode` (Task 1); `find_by_barcode`
  (`app/repositories/products.py`); `has_valid_check_digit` (`app/domain/barcodes.py`).
- Produce:
  - `async update_product(session, product_id, *, name: str | None = None, brand: str | None = None) -> Product`
    (`brand=""` toglie la marca, `None` la lascia)
  - `async move_product(session, product_id, ingredient_id) -> int` (quanti elementi
    **attivi** si sono spostati; si spostano tutti)
  - `async set_barcode(session, product_id, barcode: str | None, *, take: bool = False, accept_bad_checksum: bool = False) -> Product`
  - `async delete_product(session, product_id) -> int` (elementi attivi rimasti sfusi)
  - rifiuti `EMPTY_NAME`, `BARCODE_TAKEN` (con `obstacle` = il prodotto che ha il
    codice), `BAD_CHECKSUM`.

- [ ] **Step 1: scrivi il test che fallisce**

In `backend/tests/services/test_registry.py`, agli import:

```python
from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.domain.rules import IngredientKind, PantryStatus
```

(la seconda sostituisce l'import di `IngredientKind` che c'è già) e, nell'import da
`app.services.registry`, `delete_product`, `move_product`, `set_barcode`,
`update_product`. In fondo al file:

```python
@pytest_asyncio.fixture
async def scaffale(db_session, anagrafica):
    """Il caso del parmigiano (spec §1): un prodotto sotto «burro», con un elemento di
    dispensa attivo e uno archiviato, e un secondo prodotto che ha già un codice."""
    reggiano = Product(
        ingredient_id=anagrafica["burro"].id, name="Parmigiano Reggiano 24 mesi",
        brand="Latteria", barcode="8009876543217", source="custom",
    )
    grana = Product(
        ingredient_id=anagrafica["parmigiano"].id, name="Grana Padano 200 g",
        barcode="8001234567897", source="custom",
    )
    db_session.add_all([reggiano, grana])
    await db_session.flush()
    attivo = PantryItem(
        ingredient_id=anagrafica["burro"].id, product_id=reggiano.id,
        status=PantryStatus.AVAILABLE,
    )
    archiviato = PantryItem(
        ingredient_id=anagrafica["burro"].id, product_id=reggiano.id,
        status=PantryStatus.FINISHED, archived_at=datetime.now(UTC),
    )
    db_session.add_all([attivo, archiviato])
    await db_session.flush()
    return {"reggiano": reggiano, "grana": grana, "attivo": attivo, "archiviato": archiviato}


async def test_spostare_un_prodotto_porta_con_se_tutta_la_sua_dispensa(db_session, anagrafica, scaffale):
    """Anche gli archiviati: `add_pantry_item` rifiuta la coppia ingrediente–prodotto
    incoerente, e un archiviato rimasto sotto «burro» tornerebbe in dispensa incoerente
    al primo annulla."""
    parmigiano = anagrafica["parmigiano"]

    attivi = await move_product(db_session, scaffale["reggiano"].id, parmigiano.id)

    assert attivi == 1
    assert scaffale["reggiano"].ingredient_id == parmigiano.id
    for voce in (scaffale["attivo"], scaffale["archiviato"]):
        await db_session.refresh(voce)
        assert voce.ingredient_id == parmigiano.id


async def test_nome_e_marca_si_correggono_e_la_marca_si_toglie(db_session, scaffale):
    reggiano = scaffale["reggiano"]

    await update_product(db_session, reggiano.id, name=" Parmigiano Reggiano 30 mesi ", brand="")

    assert reggiano.name == "Parmigiano Reggiano 30 mesi"
    assert reggiano.brand is None
    with pytest.raises(RegistryRefusal) as rifiuto:
        await update_product(db_session, reggiano.id, name="  ")
    assert rifiuto.value.code == RefusalCode.EMPTY_NAME


async def test_togliere_il_codice(db_session, scaffale):
    await set_barcode(db_session, scaffale["reggiano"].id, None)
    assert scaffale["reggiano"].barcode is None


async def test_un_codice_gia_preso_rifiuta_e_porta_chi_lo_ha(db_session, scaffale):
    with pytest.raises(RegistryRefusal) as rifiuto:
        await set_barcode(db_session, scaffale["reggiano"].id, "8001234567897")

    assert rifiuto.value.code == RefusalCode.BARCODE_TAKEN
    assert rifiuto.value.obstacle is scaffale["grana"]
    assert scaffale["reggiano"].barcode == "8009876543217"


async def test_prendere_il_codice_lo_toglie_all_altro(db_session, scaffale):
    await set_barcode(db_session, scaffale["reggiano"].id, "8001234567897", take=True)

    assert scaffale["reggiano"].barcode == "8001234567897"
    assert scaffale["grana"].barcode is None


async def test_un_codice_che_non_torna_avvisa_e_si_usa_lo_stesso(db_session, scaffale):
    """S20: l'avviso e «Usalo lo stesso», mai un rifiuto che non si supera — i codici
    interni dei negozi esistono."""
    with pytest.raises(RegistryRefusal) as rifiuto:
        await set_barcode(db_session, scaffale["reggiano"].id, "8001234567890")
    assert rifiuto.value.code == RefusalCode.BAD_CHECKSUM

    await set_barcode(
        db_session, scaffale["reggiano"].id, "8001234567890", accept_bad_checksum=True
    )
    assert scaffale["reggiano"].barcode == "8001234567890"


async def test_eliminare_un_prodotto_lascia_la_dispensa_sfusa(db_session, anagrafica, scaffale):
    sfusi = await delete_product(db_session, scaffale["reggiano"].id)

    assert sfusi == 1
    assert await db_session.get(Product, scaffale["reggiano"].id) is None
    for voce in (scaffale["attivo"], scaffale["archiviato"]):
        await db_session.refresh(voce)
        assert voce.product_id is None
        assert voce.ingredient_id == anagrafica["burro"].id
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `cd backend && PATH="$PWD/.venv/bin:$PATH" python -m pytest tests/services/test_registry.py -v`
Expected: FAIL in raccolta — `ImportError: cannot import name 'delete_product'`.

- [ ] **Step 3: implementazione minima**

In `backend/app/services/registry.py`, agli import:

```python
from app.domain.barcodes import has_valid_check_digit
from app.repositories.products import find_by_barcode
```

In fondo al modulo:

```python
async def _product(session: AsyncSession, product_id: uuid.UUID) -> Product:
    product = await session.get(Product, product_id)
    if product is None:
        raise LookupError(f"nessun prodotto {product_id}")
    return product


async def update_product(
    session: AsyncSession,
    product_id: uuid.UUID,
    *,
    name: str | None = None,
    brand: str | None = None,
) -> Product:
    """Nome e marca. `brand=""` toglie la marca; `None` la lascia com'è."""
    product = await _product(session, product_id)
    if name is not None:
        cleaned = name.strip()
        if not cleaned:
            raise RegistryRefusal(RefusalCode.EMPTY_NAME, "Il nome non può essere vuoto.")
        product.name = cleaned
    if brand is not None:
        product.brand = brand.strip() or None
    await session.flush()
    return product


async def move_product(
    session: AsyncSession, product_id: uuid.UUID, ingredient_id: uuid.UUID
) -> int:
    """Il prodotto passa sotto un altro ingrediente, e **tutti** i suoi elementi di
    dispensa con lui, attivi e archiviati: `add_pantry_item` rifiuta la coppia
    ingrediente–prodotto incoerente, e un archiviato lasciato indietro tornerebbe
    incoerente al primo annulla. Torna quanti degli attivi si sono spostati: sono quelli
    che chi guarda la dispensa vede.

    Nessun filtro sul `kind`: in anagrafica si corregge anche il non alimentare.
    """
    product = await _product(session, product_id)
    target = await _ingredient(session, ingredient_id)
    active = (
        await session.execute(
            select(func.count())
            .select_from(PantryItem)
            .where(PantryItem.product_id == product.id, PantryItem.archived_at.is_(None))
        )
    ).scalar_one()
    product.ingredient_id = target.id
    await session.execute(
        update(PantryItem).where(PantryItem.product_id == product.id).values(ingredient_id=target.id)
    )
    await session.flush()
    return active


async def set_barcode(
    session: AsyncSession,
    product_id: uuid.UUID,
    barcode: str | None,
    *,
    take: bool = False,
    accept_bad_checksum: bool = False,
) -> Product:
    """Il codice a barre, o nessun codice.

    Un codice che è già di un altro prodotto si rifiuta portando quel prodotto, e con
    `take=True` gli si toglie: spostarlo è una decisione di chi ha la confezione in
    mano, non un effetto collaterale. Un codice che la cifra di controllo non conferma
    si rifiuta finché non si dice `accept_bad_checksum=True` — l'avviso e «Usalo lo
    stesso» di S20, mai un rifiuto che non si supera. Chi prende un codice già in
    catalogo non passa dal controllo: qualcuno l'ha già confermato con la confezione in
    mano, come in «Sistema la spesa».
    """
    product = await _product(session, product_id)
    code = (barcode or "").strip()
    if not code:
        product.barcode = None
        await session.flush()
        return product
    if code == product.barcode:
        return product
    holder = await find_by_barcode(session, code)
    if holder is not None and holder.id != product.id:
        if not take:
            raise RegistryRefusal(
                RefusalCode.BARCODE_TAKEN, f"Il codice è di «{holder.name}».", holder
            )
        holder.barcode = None
        # il vincolo di unicità deve vedere il vuoto prima del codice nuovo
        await session.flush()
    elif not accept_bad_checksum and not has_valid_check_digit(code):
        raise RegistryRefusal(
            RefusalCode.BAD_CHECKSUM,
            "Il codice non torna con la sua cifra di controllo: controlla le cifre. "
            "Se è un codice del negozio, usalo lo stesso.",
        )
    product.barcode = code
    await session.flush()
    return product


async def delete_product(session: AsyncSession, product_id: uuid.UUID) -> int:
    """Cancella il prodotto. Gli elementi di dispensa restano, sfusi.

    `pantry_items.product_id` è già ON DELETE SET NULL; l'UPDATE esplicito prima del
    DELETE tiene d'accordo anche gli oggetti che la sessione ha in memoria. Torna quanti
    elementi attivi restano sfusi: è quel che la conferma ha promesso.
    """
    product = await _product(session, product_id)
    loose = (
        await session.execute(
            select(func.count())
            .select_from(PantryItem)
            .where(PantryItem.product_id == product.id, PantryItem.archived_at.is_(None))
        )
    ).scalar_one()
    await session.execute(
        update(PantryItem).where(PantryItem.product_id == product.id).values(product_id=None)
    )
    await session.delete(product)
    await session.flush()
    return loose
```

- [ ] **Step 4: eseguilo e verifica che passi**

Run: `cd backend && PATH="$PWD/.venv/bin:$PATH" python -m pytest tests/services -q`
Expected: PASS, tutti.

- [ ] **Step 5: commit**

```bash
git add backend/app/services/registry.py backend/tests/services/test_registry.py
git commit -m "$(cat <<'EOF'
anagrafica: i prodotti si rinominano, si spostano con la loro dispensa, cambiano codice

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: La CLI diventa un guscio

**File:**
- Modify: `backend/app/cli/fix_registry.py` (tutto il file: docstring, import, `merge`,
  `recategorize`, `rename`, `move_alias`, `apply_plan`)
- Test: `backend/tests/test_fix_registry_is_a_shell.py` (nuovo);
  `backend/tests/test_fix_registry_cli.py` **si esegue e non si tocca**

**Interfacce:**
- Consuma: `registry.merge_ingredients`, `registry.recategorize_ingredient`,
  `registry.rename_ingredient`, `registry.move_alias`, `RegistryRefusal`, `MergeCounts`
  (Task 1, 2, 5).
- Produce: `apply_plan`, `OPERATIONS`, `PlanError`, `Outcome` con la stessa forma di
  prima; `Outcome.rebuilt` ora somma anche le ricette rifatte dentro ogni `merge`.

- [ ] **Step 1: scrivi il test che fallisce**

Crea `backend/tests/test_fix_registry_is_a_shell.py`:

```python
"""La CLI dell'anagrafica è un guscio sul servizio (S9 §3).

`test_fix_registry_cli.py` prova che il comando fa ancora quel che faceva, e non si
tocca. Questo prova che lo fa chiamando `app/services/registry.py` e non una sua copia
delle guardie: la prima lezione di CLAUDE.md — se la copia restasse, lo schermo e il
comando avrebbero due guardie, e la prima a scollarsi sarebbe quella sul non alimentare.
"""

import inspect

from app.cli import fix_registry


def test_le_correzioni_passano_dal_servizio():
    sorgente = inspect.getsource(fix_registry)

    assert "from app.services import registry" in sorgente
    for copia in (
        "kind_for_category",
        "delete_ingredient_if_unused",
        "merge_quantities",
        "remember_alias",
    ):
        assert copia not in sorgente, f"fix_registry ha ancora la sua copia: {copia}"
```

- [ ] **Step 2: eseguilo e verifica che fallisca, e che i test della CLI siano verdi prima**

Run:
```bash
(cd backend && PATH="$PWD/.venv/bin:$PATH" python -m pytest tests/test_fix_registry_is_a_shell.py -v)
(cd backend && PATH="$PWD/.venv/bin:$PATH" python -m pytest tests/test_fix_registry_cli.py -v)
git diff --stat master -- backend/tests/test_fix_registry_cli.py
```
Expected: il primo FAIL — `AssertionError: ... from app.services import registry`; il
secondo PASS, 13 test (è la fotografia del «prima»); il `git diff` vuoto.

- [ ] **Step 3: implementazione minima**

Sostituisci `backend/app/cli/fix_registry.py` con:

```python
"""Corregge l'anagrafica degli ingredienti a lotti, da un piano scritto.

Eseguire nel container del backend, dove la cartella `data/` del repository è montata
in `/data`:

    python -m app.cli.fix_registry /data/fixes/<piano>.json             # prova e dice
    python -m app.cli.fix_registry /data/fixes/<piano>.json --conferma  # applica

Senza `--conferma` il piano gira davvero, dentro una transazione che alla fine si
annulla: la prova incontra gli stessi rifiuti dell'applicazione, compresa la
materializzazione delle ricette, e non una loro imitazione. Con `--conferma` la stessa
transazione si salva, e un solo passo rifiutato non salva niente.

Nato il 2026-09-27, dopo l'import completo (R4): la revisione dell'anagrafica ha
trovato alias sbagliati («lampascioni» sotto «lampone disidratato»), doppioni che
davano falsi «manca» (la piadina in dispensa, la piadella nelle ricette) e reparti
sbagliati. Il piano è un file e non un elenco di UPDATE per due ragioni: resta nel
repository come storia di cosa si è deciso, e ogni passo usa gli stessi percorsi già
testati dell'import — l'annullamento di una decisione e la decisione a mano — invece
di una chirurgia su `recipe_ingredients`.

Da S9 le correzioni dell'anagrafica — `merge`, `recategorize`, `rename`, `move_alias` —
stanno in `app/services/registry.py`, lo stesso servizio che chiamano le schede
dell'anagrafica nell'app. Questo comando traduce il passo in argomenti, chiama il
servizio e trasforma il suo rifiuto (`RegistryRefusal`) in `PlanError`. `decide` e
`remap` restano qui: sono decisioni della coda, non anagrafica.

Il piano è una lista di passi JSON, applicati in ordine:

    {"op": "decide", "term": "Fegato di vitello", "create": {"name": "fegato di vitello",
     "category": "carne"}}
    {"op": "decide", "term": "Noce di manzo", "map": "fettina di manzo"}
    {"op": "decide", "term": "Liquore", "map": "liquore", "role": "secondary"}
    {"op": "remap", "term": "Lampascioni", "map": "lampascione"}
    {"op": "merge", "from": "piadella", "into": "piadina"}
    {"op": "recategorize", "ingredient": "eglefino", "category": "pesce"}
    {"op": "rename", "ingredient": "tormini", "name": "tomino", "display_name": "Tomini"}
    {"op": "move_alias", "alias": "piadina", "to": "piadina"}

`decide` vale per un termine in coda, `remap` per uno già deciso: prima lo annulla,
rimettendo in attesa le pagine delle sue ricette, poi lo decide. `merge` sposta tutto
quel che puntava a `from` — termini, dispensa, lista, prodotti, righe di ricetta,
alias — su `into`, e poi cancella `from`; il suo nome resta come alias di `into`,
così chi lo scrive nella lista trova ancora qualcosa. Le pagine rimesse in attesa da
un `merge` tornano ricette dentro il passo stesso, con le loro cotture; quelle di
`remap` e `decide` una volta sola, alla fine.
"""

import argparse
import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.db.models.ingredient import Ingredient, IngredientAlias
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.domain.rules import IngredientRole
from app.repositories.imports import counts
from app.services import registry
from app.services.recipe_import.manual import DecisionRefused, ManualDecision, decide_by_hand
from app.services.recipe_import.materialize import materialize_ready
from app.services.recipe_import.undo import undo_decision
from app.services.registry import RegistryRefusal

Log = Callable[[str], None]


class PlanError(Exception):
    """Un passo del piano non si può applicare: niente del piano viene salvato."""


@dataclass
class Outcome:
    steps: int = 0
    requeued: int = 0
    rebuilt: int = 0
    skipped: int = 0
    pending_terms: int = 0
```

Le funzioni `_ingredient`, `_term`, `_decision`, `_apply_decision`, `_undo` (quella del
Task 3), `decide` e `remap` restano **identiche** a come sono ora. Sotto `remap`:

```python
async def merge(session: AsyncSession, step: dict, outcome: Outcome) -> str:
    loser = await _ingredient(session, step["from"])
    winner = await _ingredient(session, step["into"])
    try:
        merged = await registry.merge_ingredients(session, loser.id, winner.id)
    except RegistryRefusal as exc:
        raise PlanError(exc.message) from exc
    outcome.rebuilt += merged.recipes_rebuilt
    return (
        f"{step['from']} → {merged.winner_name}: {merged.recipes_rebuilt} ricette rifatte, "
        f"{merged.recipe_lines_moved} righe fuori dall'import, "
        f"{merged.pantry_items + merged.shopping_items + merged.products} fra dispensa, "
        f"lista e prodotti, {merged.cooking_events_relinked} cotture ri-legate"
    )


async def recategorize(session: AsyncSession, step: dict, outcome: Outcome) -> str:
    ingredient = await _ingredient(session, step["ingredient"])
    before = ingredient.category
    try:
        await registry.recategorize_ingredient(session, ingredient.id, step["category"])
    except RegistryRefusal as exc:
        raise PlanError(exc.message) from exc
    return f"{ingredient.name}: {before} → {ingredient.category}"


async def rename(session: AsyncSession, step: dict, outcome: Outcome) -> str:
    ingredient = await _ingredient(session, step["ingredient"])
    old_name, old_display = ingredient.name, ingredient.display_name
    try:
        await registry.rename_ingredient(
            session, ingredient.id,
            name=step.get("name"), display_name=step.get("display_name"),
        )
    except RegistryRefusal as exc:
        raise PlanError(exc.message) from exc
    return f"{old_name} ({old_display}) → {ingredient.name} ({ingredient.display_name})"


async def move_alias(session: AsyncSession, step: dict, outcome: Outcome) -> str:
    alias = step["alias"].strip().lower()
    target = await _ingredient(session, step["to"])
    query = select(IngredientAlias).where(IngredientAlias.alias == alias)
    if "from" in step:
        query = query.where(
            IngredientAlias.ingredient_id == (await _ingredient(session, step["from"])).id
        )
    rows = list((await session.execute(query)).scalars())
    if not rows:
        raise PlanError(f"nessun alias «{alias}» da spostare")
    for row in rows:
        try:
            await registry.move_alias(session, row.id, target.id)
        except RegistryRefusal as exc:
            raise PlanError(exc.message) from exc
    return f"alias «{alias}» → {target.name}"
```

`OPERATIONS` resta identico. In `apply_plan` l'assegnazione dopo `materialize_ready`
diventa una somma, perché ogni `merge` ha già rifatto le sue:

```python
    materialized = await materialize_ready(session, GIALLOZAFFERANO)
    outcome.rebuilt += materialized.created
```

`main` resta identico.

- [ ] **Step 4: eseguilo e verifica che passi**

Run:
```bash
(cd backend && PATH="$PWD/.venv/bin:$PATH" python -m pytest tests/test_fix_registry_is_a_shell.py tests/test_fix_registry_cli.py tests/services -v)
git diff --stat master -- backend/tests/test_fix_registry_cli.py
```
Expected: PASS, tutti — gli stessi 13 test della CLI dello Step 2, **senza** modifiche
(il `git diff` resta vuoto). Se uno di quei 13 fallisce, si corregge il servizio o il
guscio, mai il test (spec §10).

- [ ] **Step 5: commit**

```bash
git add backend/app/cli/fix_registry.py backend/tests/test_fix_registry_is_a_shell.py
git commit -m "$(cat <<'EOF'
anagrafica: fix_registry diventa un guscio sul servizio, i suoi test non si toccano

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: Le rotte dell'ingrediente

**File:**
- Create: `backend/app/api/refusals.py`
- Modify: `backend/app/schemas/ingredient.py` (in fondo)
- Modify: `backend/app/repositories/ingredients.py` (`IngredientUsage`, `ingredient_usage`)
- Modify: `backend/app/api/ingredients.py` (import; rotte nuove in fondo, dopo `create_alias`)
- Test: `backend/tests/api/test_registry_ingredients.py`

**Interfacce:**
- Consuma: tutto il servizio (Task 1, 2, 5, 6).
- Produce:
  - schemi `AliasOut(id, alias, source, decided_in_queue: bool)`,
    `ProductBriefOut(id, name, brand, barcode)`, `IngredientUsageOut(recipes, pantry, shopping)`,
    `IngredientDetailOut(IngredientOut + aliases, products, usage)`,
    `IngredientPatch(name?, category?)`, `MergeIn(into, dry_run=False)`,
    `MergeOut(dry_run, loser_name, winner_id, winner_name, recipes_rebuilt, recipe_lines_moved, pantry_items, shopping_items, products, aliases, cooking_events_relinked)`,
    `AliasMoveIn(ingredient_id)`, `AliasMovedOut(alias: AliasOut | None, ingredient: IngredientOut)`
  - `refusal_response(exc: RegistryRefusal) -> JSONResponse` (409:
    `{"detail", "code", ...ostacolo}`; ostacolo `existing` per ingrediente e prodotto,
    `recipes` + `recipe_count` per le ricette, `term` per il termine della coda)
  - `IngredientUsage(recipes, pantry, shopping)`, `async ingredient_usage(session, ingredient_id)`
  - rotte: `GET /api/v1/ingredients/{id}`, `PATCH /api/v1/ingredients/{id}`,
    `POST /api/v1/ingredients/{id}/merge`,
    `PATCH /api/v1/ingredients/{id}/aliases/{alias_id}`,
    `DELETE /api/v1/ingredients/{id}/aliases/{alias_id}` (204).

- [ ] **Step 1: scrivi il test che fallisce**

Crea `backend/tests/api/test_registry_ingredients.py`:

```python
"""Le rotte dell'anagrafica sull'ingrediente (S9 §4): la scheda, e i 409 con i loro
ostacoli accanto.

Il mondo di prova si salva con `commit`: una rotta che rifiuta fa `rollback`, e con
`join_transaction_mode="create_savepoint"` quel rollback porterebbe via quel che il
test avesse solo scritto con `flush`. Si restituiscono id e non oggetti, per lo stesso
motivo: dopo un rollback gli oggetti sono scaduti.
"""

import uuid
from datetime import UTC, datetime

import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.db.models.recipe import RecipeSource
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.db.models.shopping import ShoppingListItem, ShoppingReason, ShoppingStatus
from app.domain.rules import PantryStatus
from app.repositories.ingredients import add_alias, remember_alias
from app.repositories.recipes import create_recipe

BASE = "/api/v1/ingredients"


@pytest_asyncio.fixture
async def anagrafica(db_session):
    def voce(name: str, display: str, category: str) -> Ingredient:
        return Ingredient(name=name, display_name=display, category=category)

    pomodoro = voce("pomodoro", "Pomodoro", IngredientCategory.VERDURA)
    pomodori = voce("pomodori", "Pomodori", IngredientCategory.VERDURA)
    burro = voce("burro", "Burro", IngredientCategory.LATTICINI)
    detersivo = voce("detersivo", "Detersivo", IngredientCategory.CASA)
    db_session.add_all([pomodoro, pomodori, burro, detersivo])
    await db_session.flush()

    manuale = await add_alias(db_session, pomodori.id, "pomodorini", source="manual")
    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-pelati", display_name="Pomodori pelati",
        occurrences=1, decision=TermDecision.MAPPED, ingredient_id=pomodori.id,
        decided_by="ai", decided_at=datetime.now(UTC),
    )
    db_session.add(term)
    await db_session.flush()
    await remember_alias(db_session, pomodori.id, "Pomodori pelati")
    risotto = await create_recipe(
        db_session, title="Risotto al burro", description=None, instructions="Manteca.",
        servings=2, source=RecipeSource.AI, source_ref=None,
        ingredients=[(burro.id, "primary", "50 g", None)], embedding=None,
    )
    db_session.add(PantryItem(ingredient_id=pomodori.id, status=PantryStatus.AVAILABLE))
    db_session.add(ShoppingListItem(
        raw_text="pomodori", ingredient_id=pomodori.id,
        status=ShoppingStatus.PENDING, reason=ShoppingReason.MANUAL,
    ))
    db_session.add(Product(
        ingredient_id=pomodori.id, name="Pelati Cirio", brand="Cirio",
        barcode="8004567890120", source="custom",
    ))
    await db_session.flush()
    pelati = (
        await db_session.execute(
            select(IngredientAlias.id).where(IngredientAlias.alias == "pomodori pelati")
        )
    ).scalar_one()
    ids = {
        "pomodoro": pomodoro.id, "pomodori": pomodori.id, "burro": burro.id,
        "detersivo": detersivo.id, "manuale": manuale.id, "pelati": pelati,
        "term": term.id, "risotto": risotto.id,
    }
    await db_session.commit()
    return ids


def _alias_per_nome(corpo: dict) -> dict[str, dict]:
    """Per nome e non per posizione: l'ordine dipende dalla collazione del database."""
    return {alias["alias"]: alias for alias in corpo["aliases"]}


async def test_la_scheda_dice_alias_prodotti_e_uso(logged_client, anagrafica):
    risposta = await logged_client.get(f"{BASE}/{anagrafica['pomodori']}")

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert (corpo["name"], corpo["category"], corpo["kind"]) == ("pomodori", "verdura", "food")
    alias = _alias_per_nome(corpo)
    assert alias["pomodori pelati"]["source"] == "import"
    assert alias["pomodori pelati"]["decided_in_queue"] is True
    assert alias["pomodorini"]["decided_in_queue"] is False
    assert [(p["name"], p["brand"], p["barcode"]) for p in corpo["products"]] == [
        ("Pelati Cirio", "Cirio", "8004567890120")
    ]
    assert corpo["usage"] == {"recipes": 0, "pantry": 1, "shopping": 1}


async def test_un_ingrediente_che_non_c_e_e_un_404(logged_client):
    assert (await logged_client.get(f"{BASE}/{uuid.uuid4()}")).status_code == 404


async def test_un_nome_gia_preso_e_un_409_con_l_omonimo(logged_client, anagrafica):
    risposta = await logged_client.patch(f"{BASE}/{anagrafica['pomodori']}", json={"name": "Pomodoro"})

    assert risposta.status_code == 409
    corpo = risposta.json()
    assert corpo["code"] == "name_taken"
    assert "già in anagrafica" in corpo["detail"]
    assert corpo["existing"]["id"] == str(anagrafica["pomodoro"])
    assert corpo["existing"]["display_name"] == "Pomodoro"


async def test_rinominare_scrive_i_nomi_e_tiene_il_vecchio_come_alias(logged_client, anagrafica):
    risposta = await logged_client.patch(
        f"{BASE}/{anagrafica['pomodori']}", json={"name": "Pomodori rossi"}
    )

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert (corpo["name"], corpo["display_name"]) == ("pomodori rossi", "Pomodori rossi")
    assert _alias_per_nome(corpo)["pomodori"]["source"] == "manual"


async def test_il_non_alimentare_con_ricette_e_un_409_che_le_elenca(logged_client, anagrafica):
    risposta = await logged_client.patch(f"{BASE}/{anagrafica['burro']}", json={"category": "casa"})

    assert risposta.status_code == 409
    corpo = risposta.json()
    assert corpo["code"] == "non_food_in_recipes"
    assert corpo["recipe_count"] == 1
    assert corpo["recipes"] == [{"id": str(anagrafica["risotto"]), "title": "Risotto al burro"}]
    assert (await logged_client.get(f"{BASE}/{anagrafica['burro']}")).json()["category"] == "latticini"


async def test_un_corpo_vuoto_e_un_400(logged_client, anagrafica):
    risposta = await logged_client.patch(f"{BASE}/{anagrafica['pomodori']}", json={})
    assert risposta.status_code == 400


async def test_l_anteprima_non_cambia_niente_e_la_fusione_dice_gli_stessi_numeri(
    logged_client, anagrafica
):
    url = f"{BASE}/{anagrafica['pomodori']}/merge"

    prova = await logged_client.post(url, json={"into": str(anagrafica["pomodoro"]), "dry_run": True})
    assert prova.status_code == 200
    assert prova.json()["dry_run"] is True
    assert (await logged_client.get(f"{BASE}/{anagrafica['pomodori']}")).status_code == 200

    vera = await logged_client.post(url, json={"into": str(anagrafica["pomodoro"])})
    assert vera.status_code == 200
    assert vera.json() == {**prova.json(), "dry_run": False}
    assert vera.json()["pantry_items"] == 1
    assert vera.json()["winner_id"] == str(anagrafica["pomodoro"])
    assert (await logged_client.get(f"{BASE}/{anagrafica['pomodori']}")).status_code == 404
    vincitore = (await logged_client.get(f"{BASE}/{anagrafica['pomodoro']}")).json()
    assert {"pomodori", "pomodorini", "pomodori pelati"} <= set(_alias_per_nome(vincitore))


async def test_un_alimento_e_una_voce_non_alimentare_sono_un_409_kind_mismatch(logged_client, anagrafica):
    risposta = await logged_client.post(
        f"{BASE}/{anagrafica['pomodori']}/merge",
        json={"into": str(anagrafica["detersivo"]), "dry_run": True},
    )

    assert risposta.status_code == 409
    corpo = risposta.json()
    assert corpo["code"] == "kind_mismatch"
    assert corpo["existing"]["id"] == str(anagrafica["detersivo"])
    assert "poi uniscili" in corpo["detail"]


async def test_un_alias_scritto_a_mano_si_sposta(logged_client, anagrafica):
    risposta = await logged_client.patch(
        f"{BASE}/{anagrafica['pomodori']}/aliases/{anagrafica['manuale']}",
        json={"ingredient_id": str(anagrafica["pomodoro"])},
    )

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert corpo["alias"]["alias"] == "pomodorini"
    assert corpo["ingredient"]["id"] == str(anagrafica["pomodoro"])


async def test_un_alias_della_coda_e_un_409_che_porta_il_termine(logged_client, anagrafica):
    url = f"{BASE}/{anagrafica['pomodori']}/aliases/{anagrafica['pelati']}"

    spostamento = await logged_client.patch(url, json={"ingredient_id": str(anagrafica["pomodoro"])})
    rimozione = await logged_client.delete(url)

    for risposta in (spostamento, rimozione):
        assert risposta.status_code == 409
        assert risposta.json()["code"] == "import_alias"
        assert risposta.json()["term"] == {
            "id": str(anagrafica["term"]), "display_name": "Pomodori pelati",
        }


async def test_togliere_un_alias_scritto_a_mano(logged_client, anagrafica):
    risposta = await logged_client.delete(
        f"{BASE}/{anagrafica['pomodori']}/aliases/{anagrafica['manuale']}"
    )

    assert risposta.status_code == 204
    scheda = (await logged_client.get(f"{BASE}/{anagrafica['pomodori']}")).json()
    assert "pomodorini" not in _alias_per_nome(scheda)


async def test_un_alias_di_un_altro_ingrediente_e_un_404(logged_client, anagrafica):
    risposta = await logged_client.delete(
        f"{BASE}/{anagrafica['pomodoro']}/aliases/{anagrafica['manuale']}"
    )
    assert risposta.status_code == 404
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `cd backend && PATH="$PWD/.venv/bin:$PATH" python -m pytest tests/api/test_registry_ingredients.py -v`
Expected: FAIL — `test_la_scheda_dice_alias_prodotti_e_uso` con `assert 405 == 200`
(la rotta `GET /{id}` non esiste), le PATCH con 405, le rotte degli alias con 404/405.

- [ ] **Step 3: implementazione minima**

In fondo a `backend/app/schemas/ingredient.py`:

```python
class AliasOut(BaseModel):
    id: uuid.UUID
    alias: str
    source: str
    # vero se l'alias è la metà di una decisione della coda: si corregge da lì (§4)
    decided_in_queue: bool


class ProductBriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    brand: str | None
    barcode: str | None


class IngredientUsageOut(BaseModel):
    recipes: int
    pantry: int
    shopping: int


class IngredientDetailOut(IngredientOut):
    """La scheda dell'ingrediente: cos'è, i suoi alias, i suoi prodotti, e dove è
    usato — così il peso di una correzione si vede prima di farla (spec §6.3)."""

    aliases: list[AliasOut]
    products: list[ProductBriefOut]
    usage: IngredientUsageOut


class IngredientPatch(BaseModel):
    """`name` scrive il nome canonico e il nome a video insieme: nell'app si rinomina
    una cosa sola. Il nome a video da solo resta della CLI."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: IngredientCategory | None = None


class MergeIn(BaseModel):
    into: uuid.UUID
    dry_run: bool = False


class MergeOut(BaseModel):
    dry_run: bool
    loser_name: str
    winner_id: uuid.UUID
    winner_name: str
    recipes_rebuilt: int
    recipe_lines_moved: int
    pantry_items: int
    shopping_items: int
    products: int
    aliases: int
    cooking_events_relinked: int


class AliasMoveIn(BaseModel):
    ingredient_id: uuid.UUID


class AliasMovedOut(BaseModel):
    # `None` se l'alias era il nome stesso dell'ingrediente d'arrivo, e quindi è sparito
    alias: AliasOut | None
    ingredient: IngredientOut
```

In `backend/app/repositories/ingredients.py`, agli import `from dataclasses import dataclass`
e `from app.db.models.shopping import ShoppingListItem, ShoppingStatus` (sostituisce
l'import di `ShoppingListItem` che c'è già); in fondo al modulo:

```python
@dataclass(frozen=True)
class IngredientUsage:
    recipes: int
    pantry: int
    shopping: int


async def ingredient_usage(session: AsyncSession, ingredient_id: uuid.UUID) -> IngredientUsage:
    """Dove è usato un ingrediente: righe di ricetta, elementi attivi in dispensa, voci
    ancora da comprare o nel carrello. Il peso di una correzione, detto prima di farla
    (spec §6.3)."""
    from app.db.models.pantry import PantryItem
    from app.db.models.recipe import RecipeIngredient

    async def count(statement) -> int:
        return (await session.execute(statement)).scalar_one()

    return IngredientUsage(
        recipes=await count(
            select(func.count())
            .select_from(RecipeIngredient)
            .where(RecipeIngredient.ingredient_id == ingredient_id)
        ),
        pantry=await count(
            select(func.count())
            .select_from(PantryItem)
            .where(PantryItem.ingredient_id == ingredient_id, PantryItem.archived_at.is_(None))
        ),
        shopping=await count(
            select(func.count())
            .select_from(ShoppingListItem)
            .where(
                ShoppingListItem.ingredient_id == ingredient_id,
                ShoppingListItem.status.in_([ShoppingStatus.PENDING, ShoppingStatus.CHECKED]),
            )
        ),
    )
```

Crea `backend/app/api/refusals.py`:

```python
"""I rifiuti dell'anagrafica in HTTP: un 409 con il motivo e l'ostacolo accanto.

La forma è quella che `POST /ingredients` usa da S19 — `detail` con il messaggio, e
l'oggetto d'ostacolo in `existing` — più `code`, che dice allo schermo quale passo
offrire (spec §7). Un posto solo perché le rotte dell'ingrediente e del prodotto devono
dire lo stesso rifiuto nello stesso modo.
"""

from fastapi import status
from fastapi.responses import JSONResponse

from app.db.models.ingredient import Ingredient
from app.db.models.product import Product
from app.db.models.recipe_import import ImportTerm
from app.schemas.ingredient import IngredientOut, ProductBriefOut
from app.services.registry import RecipesInUse, RegistryRefusal


def refusal_response(exc: RegistryRefusal) -> JSONResponse:
    """Da chiamare **prima** del rollback: dopo, l'ostacolo è un oggetto scaduto, e
    leggerlo in una sessione async è un MissingGreenlet."""
    content: dict[str, object] = {"detail": exc.message, "code": exc.code.value}
    obstacle = exc.obstacle
    if isinstance(obstacle, Ingredient):
        content["existing"] = IngredientOut.model_validate(obstacle).model_dump(mode="json")
    elif isinstance(obstacle, Product):
        content["existing"] = ProductBriefOut.model_validate(obstacle).model_dump(mode="json")
    elif isinstance(obstacle, RecipesInUse):
        content["recipe_count"] = obstacle.count
        content["recipes"] = [
            {"id": str(recipe.id), "title": recipe.title} for recipe in obstacle.recipes
        ]
    elif isinstance(obstacle, ImportTerm):
        content["term"] = {"id": str(obstacle.id), "display_name": obstacle.display_name.strip()}
    return JSONResponse(content, status_code=status.HTTP_409_CONFLICT)
```

In `backend/app/api/ingredients.py` gli import diventano:

```python
import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.refusals import refusal_response
from app.core.db import get_session, is_missing_reference, is_unique_violation
from app.core.security import require_session
from app.db.models.ingredient import Ingredient, IngredientAlias
from app.db.models.product import Product
from app.domain.rules import IngredientKind
from app.repositories.ingredients import (
    add_alias,
    create_ingredient,
    find_by_name,
    ingredient_usage,
    search_ingredients,
)
from app.schemas.ingredient import (
    AliasCreate,
    AliasMovedOut,
    AliasMoveIn,
    AliasOut,
    IngredientCreate,
    IngredientDetailOut,
    IngredientOut,
    IngredientPatch,
    IngredientUsageOut,
    MergeIn,
    MergeOut,
    ProductBriefOut,
)
from app.services import registry
from app.services.registry import RegistryRefusal
```

In fondo al modulo (dopo `create_alias`: le rotte con `{ingredient_id}` stanno dopo
`/search`, che altrimenti verrebbe letto come un id):

```python
_CONFLICT = {status.HTTP_409_CONFLICT: {
    "description": "rifiuto dell'anagrafica: `code`, `detail` e l'ostacolo accanto",
}}


async def _aliases_out(session: AsyncSession, ingredient_id: uuid.UUID) -> list[AliasOut]:
    rows = list(
        (
            await session.execute(
                select(IngredientAlias)
                .where(IngredientAlias.ingredient_id == ingredient_id)
                .order_by(IngredientAlias.alias)
            )
        ).scalars()
    )
    in_queue = await registry.queue_terms_by_alias(session, ingredient_id)
    return [
        AliasOut(
            id=alias.id, alias=alias.alias, source=alias.source,
            decided_in_queue=alias.source == "import" and alias.alias in in_queue,
        )
        for alias in rows
    ]


async def _detail(session: AsyncSession, ingredient_id: uuid.UUID) -> IngredientDetailOut:
    ingredient = await session.get(Ingredient, ingredient_id)
    if ingredient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ingrediente inesistente")
    products = list(
        (
            await session.execute(
                select(Product)
                .where(Product.ingredient_id == ingredient_id)
                .order_by(Product.name, Product.id)
            )
        ).scalars()
    )
    usage = await ingredient_usage(session, ingredient_id)
    return IngredientDetailOut(
        **IngredientOut.model_validate(ingredient).model_dump(),
        aliases=await _aliases_out(session, ingredient_id),
        products=[ProductBriefOut.model_validate(product) for product in products],
        usage=IngredientUsageOut(**asdict(usage)),
    )


@router.get("/{ingredient_id}", response_model=IngredientDetailOut)
async def read_one(
    ingredient_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> IngredientDetailOut:
    return await _detail(session, ingredient_id)


@router.patch("/{ingredient_id}", response_model=IngredientDetailOut, responses=_CONFLICT)
async def update(
    ingredient_id: uuid.UUID, payload: IngredientPatch,
    session: AsyncSession = Depends(get_session),
) -> IngredientDetailOut | JSONResponse:
    if payload.name is None and payload.category is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "niente da cambiare")
    try:
        if payload.name is not None:
            await registry.rename_ingredient(
                session, ingredient_id, name=payload.name, display_name=payload.name
            )
        if payload.category is not None:
            await registry.recategorize_ingredient(session, ingredient_id, payload.category)
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ingrediente inesistente") from exc
    except RegistryRefusal as exc:
        response = refusal_response(exc)
        await session.rollback()
        return response
    await session.commit()
    return await _detail(session, ingredient_id)


@router.post("/{ingredient_id}/merge", response_model=MergeOut, responses=_CONFLICT)
async def merge(
    ingredient_id: uuid.UUID, payload: MergeIn,
    session: AsyncSession = Depends(get_session),
) -> MergeOut | JSONResponse:
    """`dry_run` esegue la stessa fusione dentro un SAVEPOINT annullato (§5.1): i numeri
    dell'anteprima sono quelli dell'operazione, per costruzione."""
    try:
        if payload.dry_run:
            merged = await registry.preview_merge(session, ingredient_id, payload.into)
        else:
            merged = await registry.merge_ingredients(session, ingredient_id, payload.into)
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ingrediente inesistente") from exc
    except RegistryRefusal as exc:
        response = refusal_response(exc)
        await session.rollback()
        return response
    if payload.dry_run:
        await session.rollback()
    else:
        await session.commit()
    return MergeOut(dry_run=payload.dry_run, winner_id=payload.into, **asdict(merged))


async def _own_alias(
    session: AsyncSession, ingredient_id: uuid.UUID, alias_id: uuid.UUID
) -> IngredientAlias:
    alias = await session.get(IngredientAlias, alias_id)
    if alias is None or alias.ingredient_id != ingredient_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alias inesistente")
    return alias


@router.patch(
    "/{ingredient_id}/aliases/{alias_id}", response_model=AliasMovedOut, responses=_CONFLICT
)
async def move_one_alias(
    ingredient_id: uuid.UUID, alias_id: uuid.UUID, payload: AliasMoveIn,
    session: AsyncSession = Depends(get_session),
) -> AliasMovedOut | JSONResponse:
    await _own_alias(session, ingredient_id, alias_id)
    try:
        moved = await registry.move_alias(session, alias_id, payload.ingredient_id)
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ingrediente inesistente") from exc
    except RegistryRefusal as exc:
        response = refusal_response(exc)
        await session.rollback()
        return response
    target = await session.get(Ingredient, payload.ingredient_id)
    in_queue = await registry.queue_terms_by_alias(session, payload.ingredient_id)
    out = AliasMovedOut(
        alias=AliasOut(
            id=moved.id, alias=moved.alias, source=moved.source,
            decided_in_queue=moved.source == "import" and moved.alias in in_queue,
        ) if moved is not None else None,
        ingredient=IngredientOut.model_validate(target),
    )
    await session.commit()
    return out


@router.delete(
    "/{ingredient_id}/aliases/{alias_id}", status_code=status.HTTP_204_NO_CONTENT,
    response_model=None, responses=_CONFLICT,
)
async def remove_alias(
    ingredient_id: uuid.UUID, alias_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    await _own_alias(session, ingredient_id, alias_id)
    try:
        await registry.delete_alias(session, alias_id)
    except RegistryRefusal as exc:
        response = refusal_response(exc)
        await session.rollback()
        return response
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 4: eseguilo e verifica che passi**

Run: `cd backend && PATH="$PWD/.venv/bin:$PATH" python -m pytest tests/api/test_registry_ingredients.py tests/api/test_ingredients.py -v`
Expected: PASS, tutti (i test di `POST /ingredients` e di `/search` di prima compresi).

- [ ] **Step 5: commit**

```bash
git add backend/app/api/refusals.py backend/app/schemas/ingredient.py backend/app/repositories/ingredients.py backend/app/api/ingredients.py backend/tests/api/test_registry_ingredients.py
git commit -m "$(cat <<'EOF'
anagrafica: le rotte dell'ingrediente, con i 409 che portano l'ostacolo

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: Le rotte del prodotto

**File:**
- Modify: `backend/app/schemas/product.py` (in fondo)
- Modify: `backend/app/api/products.py` (import; rotte nuove in fondo, dopo `create`)
- Test: `backend/tests/api/test_registry_products.py`

**Interfacce:**
- Consuma: `update_product`, `move_product`, `set_barcode`, `delete_product` (Task 7);
  `refusal_response` (Task 9); `has_valid_check_digit`.
- Produce:
  - schemi `IngredientRefOut(id, name, display_name)`,
    `ProductPantryItemOut(id, status, expires_on)`,
    `ProductDetailOut(id, name, brand, barcode, valid_checksum: bool | None, ingredient: IngredientRefOut, pantry_items: list[ProductPantryItemOut])`,
    `ProductPatch(name?, brand?, ingredient_id?, barcode?, take_barcode=False, accept_bad_checksum=False)`,
    `ProductDeletedOut(loose_pantry_items: int)`
  - rotte: `GET /api/v1/products/{id}`, `PATCH /api/v1/products/{id}` (i campi letti da
    `model_fields_set`: `brand: null` toglie la marca, `barcode: null` toglie il codice),
    `DELETE /api/v1/products/{id}` → 200 `{"loose_pantry_items": n}`.

- [ ] **Step 1: scrivi il test che fallisce**

Crea `backend/tests/api/test_registry_products.py`:

```python
"""Le rotte dell'anagrafica sul prodotto (S9 §4, §6.4): il caso del parmigiano sotto
«burro», e i due rifiuti del codice a barre con la loro uscita.

Come in `test_registry_ingredients.py`, il mondo si salva con `commit` e si passano id.
"""

import uuid
from datetime import UTC, datetime

import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.domain.rules import PantryStatus

BASE = "/api/v1/products"


@pytest_asyncio.fixture
async def scaffale(db_session):
    burro = Ingredient(name="burro", display_name="Burro", category=IngredientCategory.LATTICINI)
    parmigiano = Ingredient(
        name="parmigiano", display_name="Parmigiano", category=IngredientCategory.LATTICINI
    )
    db_session.add_all([burro, parmigiano])
    await db_session.flush()
    reggiano = Product(
        ingredient_id=burro.id, name="Parmigiano Reggiano 24 mesi", brand="Latteria",
        barcode="8009876543217", source="custom",
    )
    grana = Product(
        ingredient_id=parmigiano.id, name="Grana Padano 200 g", barcode="8001234567897",
        source="custom",
    )
    db_session.add_all([reggiano, grana])
    await db_session.flush()
    attivo = PantryItem(ingredient_id=burro.id, product_id=reggiano.id, status=PantryStatus.AVAILABLE)
    archiviato = PantryItem(
        ingredient_id=burro.id, product_id=reggiano.id, status=PantryStatus.FINISHED,
        archived_at=datetime.now(UTC),
    )
    db_session.add_all([attivo, archiviato])
    await db_session.flush()
    ids = {
        "burro": burro.id, "parmigiano": parmigiano.id, "reggiano": reggiano.id,
        "grana": grana.id, "attivo": attivo.id, "archiviato": archiviato.id,
    }
    await db_session.commit()
    return ids


async def _voce(db_session, item_id) -> PantryItem:
    return (
        await db_session.execute(
            select(PantryItem).where(PantryItem.id == item_id).execution_options(populate_existing=True)
        )
    ).scalar_one()


async def test_la_scheda_dice_ingrediente_codice_e_dispensa_attiva(logged_client, scaffale):
    risposta = await logged_client.get(f"{BASE}/{scaffale['reggiano']}")

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert (corpo["name"], corpo["brand"], corpo["barcode"]) == (
        "Parmigiano Reggiano 24 mesi", "Latteria", "8009876543217",
    )
    assert corpo["valid_checksum"] is True
    assert corpo["ingredient"] == {
        "id": str(scaffale["burro"]), "name": "burro", "display_name": "Burro",
    }
    # l'archiviato non è in dispensa: la scheda mostra quel che si vede
    assert [voce["id"] for voce in corpo["pantry_items"]] == [str(scaffale["attivo"])]


async def test_un_prodotto_che_non_c_e_e_un_404(logged_client):
    assert (await logged_client.get(f"{BASE}/{uuid.uuid4()}")).status_code == 404


async def test_spostarlo_porta_con_se_tutta_la_dispensa(logged_client, db_session, scaffale):
    risposta = await logged_client.patch(
        f"{BASE}/{scaffale['reggiano']}", json={"ingredient_id": str(scaffale["parmigiano"])}
    )

    assert risposta.status_code == 200
    assert risposta.json()["ingredient"]["display_name"] == "Parmigiano"
    assert len(risposta.json()["pantry_items"]) == 1
    for voce in ("attivo", "archiviato"):
        assert (await _voce(db_session, scaffale[voce])).ingredient_id == scaffale["parmigiano"]


async def test_un_codice_gia_preso_e_un_409_e_si_puo_prendere(logged_client, scaffale):
    url = f"{BASE}/{scaffale['reggiano']}"

    rifiuto = await logged_client.patch(url, json={"barcode": "8001234567897"})
    assert rifiuto.status_code == 409
    assert rifiuto.json()["code"] == "barcode_taken"
    assert rifiuto.json()["existing"]["name"] == "Grana Padano 200 g"

    presa = await logged_client.patch(url, json={"barcode": "8001234567897", "take_barcode": True})
    assert presa.status_code == 200
    assert presa.json()["barcode"] == "8001234567897"
    grana = (await logged_client.get(f"{BASE}/{scaffale['grana']}")).json()
    assert grana["barcode"] is None


async def test_un_codice_che_non_torna_e_un_avviso_che_si_supera(logged_client, scaffale):
    url = f"{BASE}/{scaffale['reggiano']}"

    avviso = await logged_client.patch(url, json={"barcode": "8001234567890"})
    assert avviso.status_code == 409
    assert avviso.json()["code"] == "bad_checksum"

    usato = await logged_client.patch(
        url, json={"barcode": "8001234567890", "accept_bad_checksum": True}
    )
    assert usato.status_code == 200
    assert usato.json()["barcode"] == "8001234567890"
    assert usato.json()["valid_checksum"] is False


async def test_null_toglie_il_codice_e_la_marca(logged_client, scaffale):
    risposta = await logged_client.patch(
        f"{BASE}/{scaffale['reggiano']}", json={"barcode": None, "brand": None}
    )

    assert risposta.status_code == 200
    assert risposta.json()["barcode"] is None
    assert risposta.json()["valid_checksum"] is None
    assert risposta.json()["brand"] is None


async def test_il_nome_si_corregge(logged_client, scaffale):
    risposta = await logged_client.patch(
        f"{BASE}/{scaffale['reggiano']}", json={"name": "Parmigiano Reggiano 30 mesi"}
    )
    assert risposta.status_code == 200
    assert risposta.json()["name"] == "Parmigiano Reggiano 30 mesi"


async def test_un_corpo_vuoto_e_un_400(logged_client, scaffale):
    assert (await logged_client.patch(f"{BASE}/{scaffale['reggiano']}", json={})).status_code == 400


async def test_eliminarlo_lascia_la_dispensa_sfusa_e_lo_dice(logged_client, db_session, scaffale):
    risposta = await logged_client.delete(f"{BASE}/{scaffale['reggiano']}")

    assert risposta.status_code == 200
    assert risposta.json() == {"loose_pantry_items": 1}
    assert (await logged_client.get(f"{BASE}/{scaffale['reggiano']}")).status_code == 404
    for voce in ("attivo", "archiviato"):
        riletta = await _voce(db_session, scaffale[voce])
        assert riletta.product_id is None
        assert riletta.ingredient_id == scaffale["burro"]
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `cd backend && PATH="$PWD/.venv/bin:$PATH" python -m pytest tests/api/test_registry_products.py -v`
Expected: FAIL — la GET e la DELETE con `405`, la PATCH con `405`.

- [ ] **Step 3: implementazione minima**

In fondo a `backend/app/schemas/product.py` (agli import `from datetime import date`):

```python
class IngredientRefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    display_name: str


class ProductPantryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    expires_on: date | None


class ProductDetailOut(BaseModel):
    """La scheda del prodotto (spec §6.4): la scheda dell'elemento di dispensa è questa,
    e l'ingrediente sta qui come link."""

    id: uuid.UUID
    name: str
    brand: str | None
    barcode: str | None
    # il verdetto di `has_valid_check_digit`, detto e mai applicato; `None` senza codice
    valid_checksum: bool | None
    ingredient: IngredientRefOut
    # solo gli attivi: sono quelli che chi guarda la dispensa vede
    pantry_items: list[ProductPantryItemOut]


class ProductPatch(BaseModel):
    """Ogni campo si legge da `model_fields_set`: `brand: null` e `barcode: null` sono
    richieste («toglila», «toglilo»), non assenze.

    `take_barcode` prende il codice a chi l'ha già; `accept_bad_checksum` lo usa anche se
    la cifra di controllo non torna. Sono le due uscite dei due rifiuti del codice
    (spec §7).
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    brand: str | None = Field(default=None, max_length=120)
    ingredient_id: uuid.UUID | None = None
    barcode: str | None = Field(default=None, max_length=20)
    take_barcode: bool = False
    accept_bad_checksum: bool = False


class ProductDeletedOut(BaseModel):
    """Quanti elementi di dispensa attivi sono rimasti, sfusi: è quel che la conferma
    aveva promesso."""

    loose_pantry_items: int
```

In `backend/app/api/products.py` gli import diventano:

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.refusals import refusal_response
from app.core.db import get_session, is_missing_reference, is_unique_violation
from app.core.security import require_session
from app.db.models.ingredient import Ingredient
from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.domain.barcodes import has_valid_check_digit
from app.repositories.products import create_product, find_by_barcode, search_products
from app.schemas.product import (
    BarcodeLookupOut,
    IngredientRefOut,
    ProductCreate,
    ProductDeletedOut,
    ProductDetailOut,
    ProductOut,
    ProductPantryItemOut,
    ProductPatch,
    ProductSuggestion,
)
from app.services import registry
from app.services.openfoodfacts import OffUnavailable, OpenFoodFactsClient
from app.services.registry import RegistryRefusal
```

In fondo al modulo (dopo `create`: `/barcode/{barcode}` e `/search` restano prima):

```python
_CONFLICT = {status.HTTP_409_CONFLICT: {
    "description": "rifiuto dell'anagrafica: `code`, `detail` e l'ostacolo accanto",
}}


async def _detail(session: AsyncSession, product_id: uuid.UUID) -> ProductDetailOut:
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "prodotto inesistente")
    ingredient = await session.get(Ingredient, product.ingredient_id)
    items = list(
        (
            await session.execute(
                select(PantryItem)
                .where(PantryItem.product_id == product_id, PantryItem.archived_at.is_(None))
                .order_by(PantryItem.added_at, PantryItem.id)
            )
        ).scalars()
    )
    return ProductDetailOut(
        id=product.id,
        name=product.name,
        brand=product.brand,
        barcode=product.barcode,
        valid_checksum=has_valid_check_digit(product.barcode) if product.barcode else None,
        ingredient=IngredientRefOut.model_validate(ingredient),
        pantry_items=[ProductPantryItemOut.model_validate(item) for item in items],
    )


@router.get("/{product_id}", response_model=ProductDetailOut)
async def read_one(
    product_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> ProductDetailOut:
    return await _detail(session, product_id)


@router.patch("/{product_id}", response_model=ProductDetailOut, responses=_CONFLICT)
async def update(
    product_id: uuid.UUID, payload: ProductPatch,
    session: AsyncSession = Depends(get_session),
) -> ProductDetailOut | JSONResponse:
    fields = payload.model_fields_set - {"take_barcode", "accept_bad_checksum"}
    if not fields:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "niente da cambiare")
    try:
        if "name" in fields or "brand" in fields:
            await registry.update_product(
                session, product_id,
                name=payload.name if "name" in fields else None,
                # `null` è «togli la marca», che per il servizio è la stringa vuota
                brand=(payload.brand or "") if "brand" in fields else None,
            )
        if "ingredient_id" in fields and payload.ingredient_id is not None:
            await registry.move_product(session, product_id, payload.ingredient_id)
        if "barcode" in fields:
            await registry.set_barcode(
                session, product_id, payload.barcode,
                take=payload.take_barcode, accept_bad_checksum=payload.accept_bad_checksum,
            )
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "prodotto o ingrediente inesistente"
        ) from exc
    except RegistryRefusal as exc:
        response = refusal_response(exc)
        await session.rollback()
        return response
    await session.commit()
    return await _detail(session, product_id)


@router.delete("/{product_id}", response_model=ProductDeletedOut)
async def remove(
    product_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> ProductDeletedOut:
    """200 e non 204: la risposta dice quanti elementi di dispensa sono rimasti sfusi, e
    un 204 non ha corpo."""
    try:
        loose = await registry.delete_product(session, product_id)
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "prodotto inesistente") from exc
    await session.commit()
    return ProductDeletedOut(loose_pantry_items=loose)
```

- [ ] **Step 4: eseguilo e verifica che passi**

Run: `cd backend && PATH="$PWD/.venv/bin:$PATH" python -m pytest tests/api/test_registry_products.py tests/api/test_products.py -v`
Expected: PASS, tutti (i test di prima su `/barcode/{barcode}` e `/search` compresi).

- [ ] **Step 5: commit**

```bash
git add backend/app/schemas/product.py backend/app/api/products.py backend/tests/api/test_registry_products.py
git commit -m "$(cat <<'EOF'
anagrafica: le rotte del prodotto, col codice preso o usato lo stesso

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: La prova su una copia della produzione — **serve il via esplicito di Mattia**

> **Legge dati di produzione.** Questo task non parte senza un «sì» di Mattia in chat,
> chiesto dicendo cosa si scarica (un `pg_dump` del database di produzione, nella
> cartella scratchpad della sessione, fuori dal repository), dove va (lo stack
> `spena-e2e`, distrutto alla fine) e che niente di quel che si vede entra in git — il
> repository è pubblico. Senza il via, il Task 12 non distribuisce la fusione.

Spec §9, ultimo paragrafo: prima di distribuire la fusione, una fusione vera su dati
veri (8.136 ricette), anteprima e poi esecuzione, con i conteggi confrontati. Sta qui,
prima della distribuzione della Consegna 1, perché è la Consegna 1 a portare la fusione
in produzione.

**File:** nessuno nel repository. Tutto vive in `$SCRATCHPAD`, la cartella scratchpad
della sessione che esegue (mai dentro il repository).

**Interfacce:**
- Consuma: `registry.preview_merge`, `registry.merge_ingredients` (Task 5, 6), la rotta
  `POST /api/v1/ingredients/{id}/merge` (Task 9).
- Produce: i tempi e l'esito dei confronti, scritti nel Task 12 in
  `docs/prossimi-passi.md` — tempi e «uguale / diverso», non nomi né conteggi della
  dispensa.

- [ ] **Step 1: la copia**

```bash
SCRATCHPAD="<cartella scratchpad della sessione>"   # es. /tmp/claude-…/scratchpad
ssh hetznerserver 'cd ~/sites/spena && docker compose -f docker-compose.prod.yml exec -T db sh -c "pg_dump -U \$POSTGRES_USER -Fc \$POSTGRES_DB"' > "$SCRATCHPAD/prod.dump"
ls -lh "$SCRATCHPAD/prod.dump"
```
Expected: un file di qualche decina di MB. `-T` non è decorativo: con un TTY il dump
binario arriverebbe corrotto.

- [ ] **Step 2: lo stack e2e con dentro la copia**

```bash
E2E="docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml"
$E2E up -d --build --wait
$E2E stop backend
$E2E exec -T db sh -c 'dropdb -U "$POSTGRES_USER" "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
$E2E exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges' < "$SCRATCHPAD/prod.dump"
$E2E up -d --wait
$E2E exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT count(*) FROM recipes"'
```
Expected: il conteggio delle ricette è quello della produzione (8.136 al 2026-09-24,
più quelle entrate dopo). Avvisi di `pg_restore` su `COMMENT ON EXTENSION` sono
attesi; un errore su una tabella no — in quel caso ci si ferma e si riferisce.
L'immagine del backend è costruita da questo ramo: il backend all'avvio applica
`alembic upgrade head`, che non ha niente da fare (S9 non aggiunge migrazioni).

- [ ] **Step 3: la coppia da fondere**

La prova più dura è la più grande: il perdente è l'alimento con più occorrenze nei
termini dell'import, il vincitore un altro alimento dello stesso reparto. Il senso
culinario della coppia non conta — lo stack si distrugge alla fine; conta che la
fusione tocchi quante più ricette possibile.

```bash
read PERDENTE VINCITORE < <($E2E exec -T backend python - <<'PY'
import asyncio

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.db.models.ingredient import Ingredient
from app.db.models.recipe_import import ImportTerm


async def main() -> None:
    async with SessionLocal() as s:
        loser = (
            await s.execute(
                select(Ingredient)
                .join(ImportTerm, ImportTerm.ingredient_id == Ingredient.id)
                .where(Ingredient.kind == "food")
                .group_by(Ingredient.id)
                .order_by(func.sum(ImportTerm.occurrences).desc())
                .limit(1)
            )
        ).scalar_one()
        winner = (
            await s.execute(
                select(Ingredient)
                .where(
                    Ingredient.kind == "food",
                    Ingredient.category == loser.category,
                    Ingredient.id != loser.id,
                )
                .order_by(Ingredient.name)
                .limit(1)
            )
        ).scalar_one()
        print(loser.id, winner.id)


asyncio.run(main())
PY
)
echo "$PERDENTE $VINCITORE"
```

- [ ] **Step 4: l'anteprima attraverso la rotta, con il tempo**

Nginx inoltra `/api/` al backend con il `proxy_read_timeout` di default, 60 s: se
l'anteprima della fusione più grande ci mette di più, dallo schermo non arriverebbe
mai. Questo passo lo misura dalla stessa strada del browser.

```bash
curl -s -c "$SCRATCHPAD/cookie" -H 'Content-Type: application/json' \
  -d '{"password":"test"}' http://localhost:5174/api/v1/auth/login -o /dev/null -w "%{http_code}\n"
curl -s -b "$SCRATCHPAD/cookie" -H 'Content-Type: application/json' \
  -d "{\"into\":\"$VINCITORE\",\"dry_run\":true}" \
  "http://localhost:5174/api/v1/ingredients/$PERDENTE/merge" \
  -o "$SCRATCHPAD/anteprima.json" -w "%{http_code} %{time_total}s\n"
```
Expected: `204` per l'accesso; `200` e un tempo per l'anteprima. Un `504` è un
risultato, non un guasto della prova: si annota, e si decide con Mattia prima di
distribuire.

- [ ] **Step 5: anteprima, database identico, fusione, numeri uguali**

```bash
$E2E exec -T backend python - "$PERDENTE" "$VINCITORE" <<'PY'
import asyncio
import sys
import time
import uuid

from sqlalchemy import text

from app.core.db import SessionLocal
from app.services.registry import merge_ingredients, preview_merge

TABELLE = (
    "ingredients", "ingredient_aliases", "import_terms", "recipe_imports", "recipes",
    "recipe_ingredients", "units", "pantry_items", "shopping_list_items", "products",
    "cooking_events",
)


async def impronta(s) -> dict[str, tuple[int, str]]:
    """Conteggio e md5 di ogni riga, tabella per tabella: un UPDATE che il conteggio
    non vedrebbe cambia l'impronta."""
    out = {}
    for tabella in TABELLE:
        riga = (
            await s.execute(
                text(
                    f"SELECT count(*), md5(coalesce(string_agg(t::text, '|' ORDER BY t::text), '')) "
                    f"FROM {tabella} t"
                )
            )
        ).one()
        out[tabella] = (riga[0], riga[1])
    return out


async def orfane(s) -> int:
    return (
        await s.execute(text("SELECT count(*) FROM cooking_events WHERE recipe_id IS NULL"))
    ).scalar_one()


async def main(loser: uuid.UUID, winner: uuid.UUID) -> None:
    async with SessionLocal() as s:
        prima, orfane_prima = await impronta(s), await orfane(s)

        t0 = time.monotonic()
        anteprima = await preview_merge(s, loser, winner)
        print(f"anteprima in {time.monotonic() - t0:.1f}s")
        assert await impronta(s) == prima, "l'anteprima ha scritto"
        print("database identico dopo l'anteprima: sì")

        t0 = time.monotonic()
        vera = await merge_ingredients(s, loser, winner)
        await s.commit()
        print(f"fusione in {time.monotonic() - t0:.1f}s")
        assert vera == anteprima, f"numeri diversi:\n{anteprima}\n{vera}"
        print("anteprima e fusione dicono gli stessi numeri: sì")
        assert await orfane(s) == orfane_prima, "una cottura ha perso la sua ricetta"
        print("nessuna cottura senza ricetta in più: sì")
        print(f"ricette rifatte: {vera.recipes_rebuilt}, cotture ri-legate: {vera.cooking_events_relinked}")


asyncio.run(main(uuid.UUID(sys.argv[1]), uuid.UUID(sys.argv[2])))
PY
```
Expected: tre «sì» e i tempi. Un'asserzione che fallisce ferma il Task 12: si
riferisce a Mattia con l'output, e si corregge prima di distribuire.

- [ ] **Step 6: via tutto**

```bash
$E2E down -v
rm -f "$SCRATCHPAD/prod.dump" "$SCRATCHPAD/anteprima.json" "$SCRATCHPAD/cookie"
git status --short
```
Expected: `git status` pulito — niente di questa prova è entrato nel repository.
Nessun commit in questo task.

---

### Task 12: Consegna 1 — verifica e distribuzione — **la distribuzione vuole il via di Mattia**

**File:**
- Modify: `docs/prossimi-passi.md` (la voce S9 e l'intestazione)

**Interfacce:**
- Consuma: tutto il lavoro dei Task 1–11.
- Produce: il backend di S9 in produzione, e la coda che non chiede più conferma.

- [ ] **Step 1: le suite intere**

```bash
(cd backend && PATH="$PWD/.venv/bin:$PATH" python -m pytest -q)
(cd frontend && npx vitest run && npm run lint && npm run typecheck && npm run build)
git diff --stat master -- backend/tests/test_fix_registry_cli.py
```
Expected: tutto verde; il numero dei test backend è quello dello Step 0 del Task 1
più i nuovi; il `git diff` sul file dei test della CLI è vuoto.

- [ ] **Step 2: l'e2e, su uno stack pulito**

```bash
E2E="docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml"
$E2E up -d --build --wait
$E2E exec -T backend python -m app.cli.seed --con-ricette
(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
$E2E down -v
```
Expected: verde, tutti i file che esistono (la Consegna 1 non ne aggiunge).

- [ ] **Step 3: il documento**

In `docs/prossimi-passi.md`, sotto il titolo di S9, un paragrafo nuovo:

```
**Consegna 1 (backend) fatta il <data>:** il servizio `app/services/registry.py`, le
rotte della scheda di ingrediente e prodotto, la fusione con l'anteprima nel SAVEPOINT,
le cotture che si ri-legano (via `CookedRecipesAffected`: la coda non chiede più
conferma). `fix_registry` è un guscio sul servizio, con i suoi test invariati. La prova
su una copia della produzione: anteprima in <s> s dalla rotta, <s> s dal servizio;
fusione in <s> s; database identico dopo l'anteprima, stessi numeri, nessuna cottura
persa. Le schermate sono la Consegna 2.
```

con i valori misurati nel Task 11 (tempi ed esiti, niente nomi né conteggi della
dispensa). Commit:

```bash
git add docs/prossimi-passi.md
git commit -m "$(cat <<'EOF'
docs: S9, la prima consegna e la prova sulla copia della produzione

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: la distribuzione — solo col via di Mattia in chat**

Si chiede dicendo cosa va in produzione (il backend di S9 e la coda senza conferma) e
che il Task 11 è passato. Poi:

```bash
git checkout master && git merge --ff-only anagrafica && git push origin master
ssh hetznerserver 'cd ~/sites/spena && git pull --ff-only && docker compose -f docker-compose.prod.yml up -d --build --wait'
(cd frontend && npm run build) && ls frontend/dist/assets | grep -E '^index-.*\.js$'
curl -s https://spena.mattiagirellini.com/ | grep -o 'assets/index-[^"]*'
curl -s https://spena.mattiagirellini.com/api/v1/health
git checkout anagrafica
```
Expected: il nome del pacchetto servito è quello della build locale (un `git pull`
senza ricostruire non distribuisce niente, Parte XI); `/health` risponde. Mai un
`docker compose` senza `-f docker-compose.prod.yml` sul server.

---

# Consegna 2 — schermate

Si distribuisce da sola (Task 23), sopra la Consegna 1 già in produzione.

### Task 13: L'hamburger

**File:**
- Modify: `frontend/src/components/AppHeader.tsx` (tutto il componente; `Mark` resta com'è)
- Modify: `docs/prossimi-passi.md` (T1, e la riga «Resta aperto solo l'hamburger di T1»)
- Test: `frontend/src/components/AppHeader.test.tsx`

**Interfacce:**
- Consuma: niente dei task precedenti.
- Produce: nell'intestazione il pulsante «Apri il menu» (`aria-haspopup="dialog"`,
  `aria-expanded`) e, aperto, un `role="dialog"` di nome «Menu» con «Chiudi il menu» e
  tre link: «Sistema la spesa» → `/sistema`, «Ingredienti da abbinare» →
  `/ricette/importa`, «Anagrafica» → `/anagrafica`. Il velo porta `data-menu-backdrop`.

- [ ] **Step 1: scrivi il test che fallisce**

In `AppHeader.test.tsx` gli import diventano:

```tsx
import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AppHeader } from "./AppHeader";
```

e dentro `describe("AppHeader", …)`, dopo i tre test che ci sono:

```tsx
  it("il ☰ apre un dialogo con l'indice, e ogni voce porta al suo posto", async () => {
    renderHeader();
    const apri = screen.getByRole("button", { name: "Apri il menu" });
    expect(apri).toHaveAttribute("aria-expanded", "false");

    await userEvent.click(apri);

    const menu = screen.getByRole("dialog", { name: "Menu" });
    expect(apri).toHaveAttribute("aria-expanded", "true");
    expect(within(menu).getByRole("link", { name: "Sistema la spesa" })).toHaveAttribute("href", "/sistema");
    expect(within(menu).getByRole("link", { name: "Ingredienti da abbinare" })).toHaveAttribute(
      "href", "/ricette/importa"
    );
    expect(within(menu).getByRole("link", { name: "Anagrafica" })).toHaveAttribute("href", "/anagrafica");
  });

  it("aperto, il fuoco entra nel pannello; Esc lo chiude e il fuoco torna al ☰", async () => {
    renderHeader();
    const apri = screen.getByRole("button", { name: "Apri il menu" });

    await userEvent.click(apri);
    expect(screen.getByRole("button", { name: "Chiudi il menu" })).toHaveFocus();

    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(apri).toHaveFocus();
  });

  it("il fuoco resta dentro: dopo l'ultima voce si torna alla prima, e al contrario", async () => {
    renderHeader();
    await userEvent.click(screen.getByRole("button", { name: "Apri il menu" }));
    const ultima = screen.getByRole("link", { name: "Anagrafica" });
    const prima = screen.getByRole("button", { name: "Chiudi il menu" });

    ultima.focus();
    await userEvent.tab();
    expect(prima).toHaveFocus();

    await userEvent.tab({ shift: true });
    expect(ultima).toHaveFocus();
  });

  it("il tocco fuori dal pannello lo chiude, e il fuoco torna al ☰", async () => {
    const { container } = renderHeader();
    const apri = screen.getByRole("button", { name: "Apri il menu" });
    await userEvent.click(apri);

    await userEvent.click(container.querySelector("[data-menu-backdrop]")!);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(apri).toHaveFocus();
  });

  it("scelta una voce, il pannello si chiude", async () => {
    renderHeader();
    await userEvent.click(screen.getByRole("button", { name: "Apri il menu" }));

    await userEvent.click(screen.getByRole("link", { name: "Anagrafica" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `cd frontend && npx vitest run src/components/AppHeader.test.tsx`
Expected: FAIL — `Unable to find an accessible element with the role "button" and name "Apri il menu"`
nei cinque test nuovi; i tre di prima passano.

- [ ] **Step 3: implementazione minima**

In `AppHeader.tsx`, l'import in cima diventa
`import { useCallback, useEffect, useRef, useState } from "react";` più quello di `Link`
che c'è già. Dopo `Mark`:

```tsx
// Le tre righe del menu e la croce, disegnate a mano come il segno e per lo stesso
// motivo: una libreria di icone per due segni peserebbe sul primo avvio più di quanto
// valga.
function MenuIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className="size-6"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
    >
      <path d="M4 7h16M4 12h16M4 17h16" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className="size-5"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
    >
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  );
}

// L'indice completo (D3, T1): le sezioni che la barra in basso non porta. Pasti,
// Spese, Profilo e Connettori si aggiungeranno qui quando esisteranno.
const INDEX = [
  { to: "/sistema", label: "Sistema la spesa" },
  { to: "/ricette/importa", label: "Ingredienti da abbinare" },
  { to: "/anagrafica", label: "Anagrafica" },
];

const FOCUSABLE = "a[href], button:not([disabled])";
```

La docstring di `AppHeader` perde il paragrafo «A destra non c'è niente, ed è una
scelta…» e prende al suo posto:

```
 * A destra il ☰ dell'indice completo (T1): apre un pannello con le sezioni che la
 * barra in basso non porta. È arrivato con la prima sezione secondaria vera,
 * l'anagrafica (S9), come D3 aveva deciso. Il pannello è un dialogo: il fuoco ci entra
 * e non ne esce col tabulatore, Esc e il tocco sul velo lo chiudono, e il fuoco torna
 * al ☰ — chi naviga da tastiera o con la voce resta dov'era.
```

Il corpo del componente:

```tsx
export function AppHeader() {
  const [open, setOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const close = useCallback(() => {
    setOpen(false);
    toggleRef.current?.focus();
  }, []);

  useEffect(() => {
    if (!open) return;
    panelRef.current?.querySelector<HTMLElement>(FOCUSABLE)?.focus();

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
        return;
      }
      const panel = panelRef.current;
      if (event.key !== "Tab" || !panel) return;
      const targets = Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (targets.length === 0) return;
      const first = targets[0];
      const last = targets[targets.length - 1];
      if (!panel.contains(document.activeElement)) {
        event.preventDefault();
        first.focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, close]);

  return (
    <header role="banner" className="sticky top-0 z-10 h-12 border-b border-line bg-card">
      {/* l'altezza sta sull'header, non su questo div: il bordo dell'header è nella
          sua stessa scatola (box-sizing: border-box, dal preflight di Tailwind), e
          49px (48 + 1 di bordo) contro i 48 che `main` riserva con
          `calc(100dvh-3rem)` sono la differenza verticale che frontend/e2e/style.spec.ts
          ora controlla e che qui misurava un pixel di scorrimento in più */}
      <div className="mx-auto flex h-full max-w-md items-center justify-between px-4">
        <Link
          to="/"
          className="flex min-h-11 items-center gap-2 font-semibold tracking-tight text-brand"
        >
          <Mark />
          Spena
        </Link>
        <button
          ref={toggleRef}
          type="button"
          aria-label="Apri il menu"
          aria-haspopup="dialog"
          aria-expanded={open}
          onClick={() => setOpen(true)}
          className="-mr-2 flex size-11 items-center justify-center rounded-full text-ink-soft"
        >
          <MenuIcon />
        </button>
      </div>

      {open && (
        <div className="fixed inset-0 z-30">
          {/* il tocco fuori chiude: il velo è un bersaglio, non una decorazione. Fuori
              dall'albero accessibile, perché per chi non lo vede la chiusura è Esc o
              «Chiudi il menu» */}
          <div
            data-menu-backdrop=""
            aria-hidden="true"
            onClick={close}
            className="absolute inset-0 bg-ink/40"
          />
          <div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-label="Menu"
            className="absolute inset-y-0 right-0 flex w-72 max-w-[85vw] flex-col bg-card px-4 pt-1 pb-[calc(1rem+var(--safe-bottom))]"
          >
            <div className="flex min-h-11 items-center justify-between">
              <span className="font-semibold tracking-tight">Menu</span>
              <button
                type="button"
                aria-label="Chiudi il menu"
                onClick={close}
                className="-mr-2 flex size-11 items-center justify-center rounded-full text-ink-soft"
              >
                <CloseIcon />
              </button>
            </div>
            <nav aria-label="Indice">
              <ul className="divide-y divide-line">
                {INDEX.map((entry) => (
                  <li key={entry.to}>
                    {/* scelta una voce si chiude e basta: la navigazione porta altrove,
                        e rendere il fuoco al ☰ lo toglierebbe alla pagina nuova */}
                    <Link
                      to={entry.to}
                      onClick={() => setOpen(false)}
                      className="flex min-h-12 items-center text-base font-medium text-ink"
                    >
                      {entry.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          </div>
        </div>
      )}
    </header>
  );
}
```

In `docs/prossimi-passi.md`:
- il titolo `## T1. Navigazione **[FATTO IN PARTE 2026-09-17]**` diventa
  `## T1. Navigazione **[FATTO — l'hamburger con S9, 2026-09-27]**`;
- il paragrafo che comincia con «**Resta aperto l'hamburger**, e non è una
  dimenticanza…» diventa:
  ```
  **L'hamburger c'è** (S9): un ☰ in `AppHeader.tsx` apre un pannello laterale, un
  dialogo accessibile col fuoco intrappolato, che Esc e il tocco fuori chiudono. Dentro:
  «Sistema la spesa», «Ingredienti da abbinare», «Anagrafica». Pasti, Spese, Profilo e
  Connettori si aggiungeranno lì quando esisteranno.
  ```
- nella Parte VIII, la frase «**Resta aperto** solo l'hamburger di T1» diventa «T1 è
  chiusa: l'hamburger è arrivato con S9».

- [ ] **Step 4: eseguilo e verifica che passi**

Run: `cd frontend && npx vitest run src/components src/App.test.tsx && npm run lint && npm run typecheck`
Expected: PASS, tutti; `App.test.tsx` monta l'intestazione vera e non deve accorgersi
del ☰.

- [ ] **Step 5: commit**

```bash
git add frontend/src/components/AppHeader.tsx frontend/src/components/AppHeader.test.tsx docs/prossimi-passi.md
git commit -m "$(cat <<'EOF'
intestazione: l'hamburger, un dialogo con l'indice completo (T1)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 14: La pagina «Anagrafica»

**File:**
- Create: `frontend/src/features/registry/RegistryScreen.tsx`
- Modify: `frontend/src/App.tsx` (import e una `Route`)
- Test: `frontend/src/features/registry/RegistryScreen.test.tsx`

**Interfacce:**
- Consuma: `searchIngredients` (`features/shopping-list/api.ts`), `searchProducts`
  (`features/stocking/api.ts`), le chiavi `["ingredients", q, "tutti"]` e
  `["products", q]` che `IngredientPicker` e `CatalogSearchPanel` già usano.
- Produce: `RegistryScreen` su `/anagrafica`; un campo «Cerca in anagrafica»; i risultati
  come link a `/anagrafica/ingrediente/{id}` e `/anagrafica/prodotto/{id}`.

- [ ] **Step 1: scrivi il test che fallisce**

Crea `frontend/src/features/registry/RegistryScreen.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { RegistryScreen } from "./RegistryScreen";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import type { Ingredient, Product } from "../../domain/types";

const BURRO: Ingredient = {
  id: "i-burro", name: "burro", display_name: "Burro", category: "latticini", kind: "food",
};
const REGGIANO: Product = {
  id: "p-reggiano", ingredient_id: "i-burro", name: "Parmigiano Reggiano 24 mesi",
  brand: "Latteria", barcode: "8009876543217", source: "custom", nutrients: null, image_url: null,
};

function stubRoutedFetch(route: (path: string) => [unknown, number]) {
  const spy = vi.fn((url: unknown) => {
    const [body, status] = route(String(url));
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

// Il predicato vero di App.tsx, non un `retry: false` di comodo (prima lezione di
// CLAUDE.md): con risposte riuscite non cambia niente.
function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: defaultQueryRetryPredicate } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <RegistryScreen />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RegistryScreen", () => {
  it("senza testo spiega cosa si trova qui, e non chiede niente al server", () => {
    const spy = stubRoutedFetch(() => [[], 200]);
    renderScreen();

    expect(screen.getByRole("heading", { name: "Anagrafica" })).toBeInTheDocument();
    expect(screen.getByText(/anche quel che in dispensa non c'è/)).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
  });

  it("cerca nelle due anagrafiche e mostra due gruppi, ogni risultato con la sua scheda", async () => {
    const spy = stubRoutedFetch((path) => {
      if (path.includes("/ingredients/search")) return [[BURRO], 200];
      if (path.includes("/products/search")) return [[REGGIANO], 200];
      return [{}, 404];
    });
    renderScreen();

    await userEvent.type(screen.getByLabelText("Cerca in anagrafica"), "parmig");

    expect(await screen.findByRole("link", { name: /Burro/ })).toHaveAttribute(
      "href", "/anagrafica/ingrediente/i-burro"
    );
    expect(await screen.findByRole("link", { name: /Parmigiano Reggiano 24 mesi/ })).toHaveAttribute(
      "href", "/anagrafica/prodotto/p-reggiano"
    );
    expect(screen.getByRole("heading", { name: "Ingredienti" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Prodotti" })).toBeInTheDocument();
    // l'anagrafica corregge anche il non alimentare: la ricerca non filtra il `kind`
    await waitFor(() =>
      expect(spy.mock.calls.some(([url]) => String(url).includes("/ingredients/search"))).toBe(true)
    );
    expect(spy.mock.calls.some(([url]) => String(url).includes("kind="))).toBe(false);
  });

  it("un gruppo vuoto lo dice, e l'altro resta", async () => {
    stubRoutedFetch((path) => {
      if (path.includes("/ingredients/search")) return [[], 200];
      if (path.includes("/products/search")) return [[REGGIANO], 200];
      return [{}, 404];
    });
    renderScreen();

    await userEvent.type(screen.getByLabelText("Cerca in anagrafica"), "reggiano");

    expect(await screen.findByText("Nessun ingrediente con questo nome.")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /Parmigiano Reggiano 24 mesi/ })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `cd frontend && npx vitest run src/features/registry/RegistryScreen.test.tsx`
Expected: FAIL — `Failed to resolve import "./RegistryScreen"`.

- [ ] **Step 3: implementazione minima**

Crea `frontend/src/features/registry/RegistryScreen.tsx`:

```tsx
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { searchIngredients } from "../shopping-list/api";
import { searchProducts } from "../stocking/api";
import { useDebounced } from "../../hooks/useDebounced";
import { Alert } from "../../components/ui/Alert";
import { Card } from "../../components/ui/Card";
import { Screen } from "../../components/ui/Screen";
import { SectionHeading } from "../../components/ui/SectionHeading";

const DEBOUNCE_MS = 180;

type ResultItem = { key: string; to: string; title: string; note: string | null };

function Results({
  status,
  items,
  empty,
  failed,
}: {
  status: "pending" | "error" | "success";
  items: ResultItem[];
  empty: string;
  failed: string;
}) {
  if (status === "error") return <Alert>{failed}</Alert>;
  if (status === "pending") return <p className="px-1 text-sm text-ink-soft">Cerco…</p>;
  if (items.length === 0) return <p className="px-1 text-sm text-ink-soft">{empty}</p>;
  return (
    <Card pad={false}>
      <ul className="divide-y divide-line">
        {items.map((item) => (
          <li key={item.key}>
            <Link to={item.to} className="flex min-h-12 items-baseline gap-3 px-3 py-2.5">
              <span className="min-w-0 truncate font-medium">{item.title}</span>
              {item.note && (
                <span className="ml-auto shrink-0 text-xs text-ink-faint">{item.note}</span>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** «Anagrafica» (spec S9 §6.2): la porta per quel che in dispensa non c'è.
 *
 * Un campo, le due ricerche che esistono già, due gruppi. Nessun filtro sul `kind`: in
 * anagrafica si corregge anche il detersivo. Senza tasto indietro: ci si arriva
 * dall'hamburger, da qualunque schermata, e non ha una sezione madre.
 */
export function RegistryScreen() {
  const [term, setTerm] = useState("");
  const debounced = useDebounced(term, DEBOUNCE_MS).trim();
  const ready = debounced.length >= 2;
  // sul testo corrente e non su quello ritardato: svuotando il campo i gruppi
  // spariscono subito, come l'elenco di IngredientPicker
  const showing = term.trim().length >= 2;

  // le stesse chiavi di IngredientPicker e di CatalogSearchPanel: è la stessa domanda
  // allo stesso server, e una seconda chiave per la stessa risposta la chiederebbe due
  // volte
  const ingredients = useQuery({
    queryKey: ["ingredients", debounced, "tutti"],
    queryFn: () => searchIngredients(debounced),
    enabled: ready,
  });
  const products = useQuery({
    queryKey: ["products", debounced],
    queryFn: () => searchProducts(debounced),
    enabled: ready,
  });

  return (
    <Screen
      title="Anagrafica"
      subtitle="Ingredienti e prodotti, per correggere quel che è stato registrato male."
    >
      <label className="block text-sm font-medium text-ink-soft">
        Cerca
        <input
          aria-label="Cerca in anagrafica"
          value={term}
          onChange={(event) => setTerm(event.target.value)}
          placeholder="pomodoro, Fage…"
          className="mt-1.5"
        />
      </label>

      {!showing && (
        <p className="pt-3 text-sm text-ink-soft">
          Qui c'è ogni ingrediente e ogni prodotto registrato, anche quel che in dispensa
          non c'è. Aprilo per rinominarlo, cambiargli reparto, spostarlo sotto un altro
          ingrediente o unire un doppione.
        </p>
      )}

      {showing && (
        <>
          <SectionHeading>Ingredienti</SectionHeading>
          <Results
            status={ingredients.status}
            items={(ingredients.data ?? []).map((ingredient) => ({
              key: ingredient.id,
              to: `/anagrafica/ingrediente/${ingredient.id}`,
              title: ingredient.display_name,
              note: ingredient.category,
            }))}
            empty="Nessun ingrediente con questo nome."
            failed="La ricerca degli ingredienti non risponde. Riprova tra poco: niente è cambiato."
          />
          <SectionHeading>Prodotti</SectionHeading>
          <Results
            status={products.status}
            items={(products.data ?? []).map((product) => ({
              key: product.id,
              to: `/anagrafica/prodotto/${product.id}`,
              title: product.name,
              note: product.brand,
            }))}
            empty="Nessun prodotto con questo nome."
            failed="La ricerca dei prodotti non risponde. Riprova tra poco: niente è cambiato."
          />
        </>
      )}
    </Screen>
  );
}
```

In `frontend/src/App.tsx`: `import { RegistryScreen } from "./features/registry/RegistryScreen";`
e, dopo la rotta `/ricette/:id`:

```tsx
            <Route path="/anagrafica" element={<RegistryScreen />} />
```

- [ ] **Step 4: eseguilo e verifica che passi**

Run: `cd frontend && npx vitest run src/features/registry src/App.test.tsx && npm run lint && npm run typecheck`
Expected: PASS.

- [ ] **Step 5: commit**

```bash
git add frontend/src/features/registry/RegistryScreen.tsx frontend/src/features/registry/RegistryScreen.test.tsx frontend/src/App.tsx
git commit -m "$(cat <<'EOF'
anagrafica: la pagina di ricerca, ingredienti e prodotti in due gruppi

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 15: La scheda dell'ingrediente — cos'è, alias, prodotti

**File:**
- Modify: `frontend/src/domain/types.ts` (in fondo)
- Create: `frontend/src/features/registry/api.ts`
- Create: `frontend/src/features/registry/origin.ts`
- Create: `frontend/src/features/registry/wording.ts`, `wording.test.ts`
- Create: `frontend/src/features/registry/AliasRow.tsx`
- Create: `frontend/src/features/registry/IngredientScreen.tsx`
- Modify: `frontend/src/App.tsx` (import e una `Route`)
- Test: `frontend/src/features/registry/IngredientScreen.test.tsx`

**Interfacce:**
- Consuma: le rotte del Task 9; `IngredientPicker`, `Screen`, `Card`, `Alert`,
  `SectionHeading`, `buttonClasses`.
- Produce:
  - tipi `AliasEntry`, `ProductBrief`, `IngredientUsage`, `IngredientDetail`,
    `MergeCounts`, `AliasMoved`, `RegistryRefusal` (unione discriminata su `code`)
  - `fetchIngredientDetail(id)`, `patchIngredient(id, { name?, category? })`,
    `mergeIngredient(id, into, dryRun)`, `moveAlias(ingredientId, aliasId, targetId)`,
    `deleteAlias(ingredientId, aliasId)`, `registryRefusal(error): RegistryRefusal | null`,
    `refreshAfterCorrection(client, refetch = true)`
  - `type Origin = "dispensa" | null`, `originFrom(da)`, `backFrom(origin)`,
    `ingredientPath(id, origin)`, `productPath(id, origin)`
  - `usageText(usage: IngredientUsage): string`
  - chiave di query della scheda: `["registry", "ingredient", id]`
  - `IngredientScreen` su `/anagrafica/ingrediente/:id`.

- [ ] **Step 1: scrivi il test che fallisce**

Crea `frontend/src/features/registry/wording.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { usageText } from "./wording";

describe("usageText", () => {
  it("dice dove è usato un ingrediente, come l'esempio della spec", () => {
    expect(usageText({ recipes: 42, pantry: 1, shopping: 1 })).toBe(
      "in 42 ricette · 1 in dispensa · in lista"
    );
  });

  it("al singolare, e senza le parti che non ci sono", () => {
    expect(usageText({ recipes: 1, pantry: 0, shopping: 0 })).toBe("in 1 ricetta");
    expect(usageText({ recipes: 0, pantry: 2, shopping: 0 })).toBe("in nessuna ricetta · 2 in dispensa");
  });
});
```

Crea `frontend/src/features/registry/IngredientScreen.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { IngredientScreen } from "./IngredientScreen";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import type { Ingredient, IngredientDetail } from "../../domain/types";

const POMODORI: IngredientDetail = {
  id: "i-pomodori", name: "pomodori", display_name: "Pomodori", category: "verdura", kind: "food",
  aliases: [
    { id: "a-pelati", alias: "pomodori pelati", source: "import", decided_in_queue: true },
    { id: "a-pomodorini", alias: "pomodorini", source: "manual", decided_in_queue: false },
  ],
  products: [{ id: "p-cirio", name: "Pelati Cirio", brand: "Cirio", barcode: "8004567890120" }],
  usage: { recipes: 42, pantry: 1, shopping: 1 },
};
const POMODORO: Ingredient = {
  id: "i-pomodoro", name: "pomodoro", display_name: "Pomodoro", category: "verdura", kind: "food",
};

type FetchRoute = (path: string, init?: RequestInit) => [unknown, number];

function stubRoutedFetch(route: FetchRoute) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = route(String(url), init);
    // un 204 non ha corpo, e `new Response` rifiuta di costruirne uno che ce l'ha
    return Promise.resolve(
      status === 204 ? new Response(null, { status }) : new Response(JSON.stringify(body), { status })
    );
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function callsTo(spy: ReturnType<typeof stubRoutedFetch>, method: string, suffix: string) {
  return spy.mock.calls.filter(
    ([url, init]) =>
      String(url).endsWith(suffix) && ((init as RequestInit | undefined)?.method ?? "GET") === method
  );
}

function Where() {
  const location = useLocation();
  return <p>dove: {location.pathname + location.search}</p>;
}

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: defaultQueryRetryPredicate } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/anagrafica/ingrediente/:id" element={<IngredientScreen />} />
          <Route path="*" element={<Where />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

/** Le risposte di sempre: la scheda di «pomodori», e la ricerca che trova «pomodoro». */
function base(path: string): [unknown, number] | null {
  if (path.includes("/ingredients/search")) return [[POMODORO], 200];
  if (path.endsWith("/ingredients/i-pomodori")) return [POMODORI, 200];
  return null;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("IngredientScreen", () => {
  it("dice cos'è e dove è usato, prima di ogni correzione", async () => {
    stubRoutedFetch((path) => base(path) ?? [{}, 404]);
    renderAt("/anagrafica/ingrediente/i-pomodori");

    expect(await screen.findByRole("heading", { name: "Pomodori" })).toBeInTheDocument();
    expect(screen.getByText("verdura · in 42 ricette · 1 in dispensa · in lista")).toBeInTheDocument();
  });

  it("un alias della coda porta alla coda; uno scritto a mano si sposta e si toglie", async () => {
    stubRoutedFetch((path) => base(path) ?? [{}, 404]);
    renderAt("/anagrafica/ingrediente/i-pomodori");

    expect(await screen.findByRole("link", { name: "Deciso nella coda" })).toHaveAttribute(
      "href", "/ricette/importa"
    );
    expect(screen.getByRole("button", { name: "Sposta l'alias «pomodorini»" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Togli l'alias «pomodorini»" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Sposta l'alias «pomodori pelati»" })).toBeNull();
  });

  it("«Togli» manda la DELETE dell'alias", async () => {
    const spy = stubRoutedFetch((path, init) => {
      if (init?.method === "DELETE") return [null, 204];
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Togli l'alias «pomodorini»" }));

    await waitFor(() =>
      expect(callsTo(spy, "DELETE", "/ingredients/i-pomodori/aliases/a-pomodorini")).toHaveLength(1)
    );
  });

  it("«Sposta» chiede l'ingrediente, senza filtro sul tipo, e manda la PATCH", async () => {
    const spy = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") {
        return [{ alias: { ...POMODORI.aliases[1] }, ingredient: POMODORO }, 200];
      }
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Sposta l'alias «pomodorini»" }));
    await userEvent.type(screen.getByLabelText("Sposta «pomodorini» sotto"), "pomod");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));

    await waitFor(() =>
      expect(callsTo(spy, "PATCH", "/ingredients/i-pomodori/aliases/a-pomodorini")).toHaveLength(1)
    );
    const [, init] = callsTo(spy, "PATCH", "/ingredients/i-pomodori/aliases/a-pomodorini")[0];
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({ ingredient_id: "i-pomodoro" });
    expect(spy.mock.calls.some(([url]) => String(url).includes("kind="))).toBe(false);
  });

  it("un alias della coda rifiutato dice perché, e porta alla coda", async () => {
    stubRoutedFetch((path, init) => {
      if (init?.method === "DELETE") {
        return [{
          code: "import_alias",
          detail: "«pomodorini» viene dalla decisione su «Pomodorini» nella coda: si corregge da lì.",
          term: { id: "t1", display_name: "Pomodorini" },
        }, 409];
      }
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Togli l'alias «pomodorini»" }));

    expect(await screen.findByText(/si corregge da lì/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Vai alla coda" })).toHaveAttribute("href", "/ricette/importa");
  });

  it("dalla dispensa: i prodotti portano alla loro scheda e l'origine li segue", async () => {
    stubRoutedFetch((path) => base(path) ?? [{}, 404]);
    renderAt("/anagrafica/ingrediente/i-pomodori?da=dispensa");

    expect(await screen.findByRole("link", { name: /Pelati Cirio/ })).toHaveAttribute(
      "href", "/anagrafica/prodotto/p-cirio?da=dispensa"
    );
    expect(screen.getByRole("link", { name: "Dispensa" })).toHaveAttribute("href", "/dispensa");
  });

  it("senza origine si torna all'anagrafica", async () => {
    stubRoutedFetch((path) => base(path) ?? [{}, 404]);
    renderAt("/anagrafica/ingrediente/i-pomodori");

    expect(await screen.findByRole("link", { name: "Anagrafica" })).toHaveAttribute("href", "/anagrafica");
    expect(screen.getByRole("link", { name: /Pelati Cirio/ })).toHaveAttribute(
      "href", "/anagrafica/prodotto/p-cirio"
    );
  });

  it(
    "un ingrediente che non c'è più lo dice, invece di un «riprova» che non può riuscire",
    async () => {
      // il 404 si ritenta due volte col predicato vero (Parte X): da qui il tempo lungo
      stubRoutedFetch(() => [{ detail: "ingrediente inesistente" }, 404]);
      renderAt("/anagrafica/ingrediente/i-sparito");

      expect(
        await screen.findByText(/Questo ingrediente non c'è più/, undefined, { timeout: 8000 })
      ).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Riprova" })).toBeNull();
    },
    10000
  );
});
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `cd frontend && npx vitest run src/features/registry`
Expected: FAIL — `Failed to resolve import "./wording"` e `"./IngredientScreen"`.

- [ ] **Step 3: implementazione minima**

In fondo a `frontend/src/domain/types.ts`:

```ts
// L'anagrafica (S9): la scheda dell'ingrediente, la fusione, i rifiuti.
export interface AliasEntry {
  id: string;
  alias: string;
  source: string;
  /** Vero se l'alias è la metà di una decisione della coda: si corregge da lì. */
  decided_in_queue: boolean;
}

export interface ProductBrief {
  id: string;
  name: string;
  brand: string | null;
  barcode: string | null;
}

export interface IngredientUsage {
  recipes: number;
  pantry: number;
  shopping: number;
}

export interface IngredientDetail extends Ingredient {
  aliases: AliasEntry[];
  products: ProductBrief[];
  usage: IngredientUsage;
}

/** Quel che una fusione muove. Gli stessi numeri escono dall'anteprima, che è la
 * fusione stessa annullata (spec S9 §5.1). */
export interface MergeCounts {
  dry_run: boolean;
  loser_name: string;
  winner_id: string;
  winner_name: string;
  recipes_rebuilt: number;
  recipe_lines_moved: number;
  pantry_items: number;
  shopping_items: number;
  products: number;
  aliases: number;
  cooking_events_relinked: number;
}

export interface AliasMoved {
  /** `null` se l'alias era il nome stesso dell'ingrediente d'arrivo, e quindi è sparito. */
  alias: AliasEntry | null;
  ingredient: Ingredient;
}

/** Il corpo di un 409 dell'anagrafica. `code` dice quale passo offrire (spec S9 §7),
 * l'ostacolo accanto dice con chi. */
export type RegistryRefusal =
  | { code: "name_taken" | "kind_mismatch"; detail: string; existing?: Ingredient }
  | {
      code: "non_food_in_recipes";
      detail: string;
      recipe_count: number;
      recipes: { id: string; title: string }[];
    }
  | { code: "import_alias"; detail: string; term: { id: string; display_name: string } }
  | { code: "barcode_taken"; detail: string; existing: ProductBrief }
  | {
      code:
        | "same_ingredient"
        | "empty_name"
        | "unknown_category"
        | "decision_refused"
        | "still_used"
        | "bad_checksum";
      detail: string;
    };
```

Crea `frontend/src/features/registry/api.ts`:

```ts
import type { QueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "../../api/client";
import type {
  AliasMoved,
  IngredientDetail,
  MergeCounts,
  RegistryRefusal,
} from "../../domain/types";

export function fetchIngredientDetail(id: string) {
  return apiFetch<IngredientDetail>(`/ingredients/${id}`);
}

/** `name` rinomina (nome e nome a video insieme), `category` cambia reparto. */
export function patchIngredient(id: string, body: { name?: string; category?: string }) {
  return apiFetch<IngredientDetail>(`/ingredients/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

/** Con `dryRun` è l'anteprima: la stessa fusione, annullata dal server (spec §5.1). */
export function mergeIngredient(id: string, into: string, dryRun: boolean) {
  return apiFetch<MergeCounts>(`/ingredients/${id}/merge`, {
    method: "POST",
    body: JSON.stringify({ into, dry_run: dryRun }),
  });
}

export function moveAlias(ingredientId: string, aliasId: string, targetId: string) {
  return apiFetch<AliasMoved>(`/ingredients/${ingredientId}/aliases/${aliasId}`, {
    method: "PATCH",
    body: JSON.stringify({ ingredient_id: targetId }),
  });
}

export function deleteAlias(ingredientId: string, aliasId: string) {
  return apiFetch<null>(`/ingredients/${ingredientId}/aliases/${aliasId}`, { method: "DELETE" });
}

/** Il rifiuto dell'anagrafica dentro un errore, o `null` se l'errore è un altro.
 *
 * È il `code` a dire che è un rifiuto: un 409 senza `code` (il termine già in coda, per
 * dire) resta un errore qualsiasi, e lo schermo lo tratta come tale. */
export function registryRefusal(error: unknown): RegistryRefusal | null {
  if (!(error instanceof ApiError) || error.status !== 409) return null;
  const body = error.body as { code?: unknown } | null;
  return body !== null && typeof body.code === "string" ? (body as RegistryRefusal) : null;
}

// Quel che una correzione dell'anagrafica può cambiare a video: la scheda stessa, le
// ricerche, la dispensa, la lista, il ricettario e il dettaglio di una ricetta, e le
// decisioni della coda (una fusione le ridecide sul vincitore).
const TOUCHED = [
  "registry", "ingredients", "products", "pantry", "shopping-list", "recipes", "recipe",
  "import-terms",
] as const;

/** Dopo una correzione, tutto quel che potrebbe mostrarla è vecchio.
 *
 * Con `refetch = false` si segna vecchio senza rileggere: serve a chi sta per lasciare
 * la schermata (una fusione, un'eliminazione), perché rileggere subito vorrebbe dire
 * chiedere al server una scheda che non esiste più. La schermata dopo rilegge da sé. */
export function refreshAfterCorrection(client: QueryClient, refetch = true) {
  return Promise.all(
    TOUCHED.map((key) =>
      client.invalidateQueries({ queryKey: [key], refetchType: refetch ? "active" : "none" })
    )
  );
}
```

Crea `frontend/src/features/registry/origin.ts`:

```ts
/** Da dove si è aperta una scheda dell'anagrafica, e quindi dove porta il tasto
 * indietro.
 *
 * Le schede si raggiungono da due posti — la dispensa e la pagina «Anagrafica» — e
 * `Screen` vuole una destinazione dichiarata, non `navigate(-1)` (T1). Chi apre la
 * scheda lo scrive nell'indirizzo: `?da=dispensa` torna alla dispensa, senza si torna
 * all'anagrafica. Il parametro segue la navigazione fra le schede, così dal prodotto
 * all'ingrediente e ritorno il tasto indietro porta ancora dove si era partiti. */
export type Origin = "dispensa" | null;

export function originFrom(da: string | null): Origin {
  return da === "dispensa" ? "dispensa" : null;
}

export function backFrom(origin: Origin): { to: string; label: string } {
  return origin === "dispensa"
    ? { to: "/dispensa", label: "Dispensa" }
    : { to: "/anagrafica", label: "Anagrafica" };
}

function withOrigin(path: string, origin: Origin): string {
  return origin === "dispensa" ? `${path}?da=dispensa` : path;
}

export function ingredientPath(id: string, origin: Origin): string {
  return withOrigin(`/anagrafica/ingrediente/${id}`, origin);
}

export function productPath(id: string, origin: Origin): string {
  return withOrigin(`/anagrafica/prodotto/${id}`, origin);
}
```

Crea `frontend/src/features/registry/wording.ts`:

```ts
import type { IngredientUsage } from "../../domain/types";

/** Dove è usato un ingrediente, in una riga: «in 42 ricette · 1 in dispensa · in lista».
 * Il peso di una correzione, detto prima di farla (spec §6.3). */
export function usageText(usage: IngredientUsage): string {
  const parts = [
    usage.recipes === 0
      ? "in nessuna ricetta"
      : usage.recipes === 1
        ? "in 1 ricetta"
        : `in ${usage.recipes} ricette`,
  ];
  if (usage.pantry > 0) parts.push(`${usage.pantry} in dispensa`);
  if (usage.shopping > 0) parts.push("in lista");
  return parts.join(" · ");
}
```

Crea `frontend/src/features/registry/AliasRow.tsx`:

```tsx
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { IngredientPicker } from "../../components/IngredientPicker";
import { Alert } from "../../components/ui/Alert";
import { buttonClasses } from "../../components/ui/buttonClasses";
import type { AliasEntry, Ingredient } from "../../domain/types";
import { deleteAlias, moveAlias, refreshAfterCorrection, registryRefusal } from "./api";

/** Un alias della scheda. Quelli che sono la metà di una decisione della coda non si
 * toccano da qui: dicono «Deciso nella coda» e portano lì (spec §4). Gli altri si
 * spostano sotto un altro ingrediente o si tolgono. */
export function AliasRow({ ingredientId, alias }: { ingredientId: string; alias: AliasEntry }) {
  const queryClient = useQueryClient();
  const [moving, setMoving] = useState(false);
  const move = useMutation({
    mutationFn: (target: Ingredient) => moveAlias(ingredientId, alias.id, target.id),
    onSuccess: () => refreshAfterCorrection(queryClient),
  });
  const remove = useMutation({
    mutationFn: () => deleteAlias(ingredientId, alias.id),
    onSuccess: () => refreshAfterCorrection(queryClient),
  });
  const busy = move.isPending || remove.isPending;
  const failed = move.error ?? remove.error;
  const refusal = registryRefusal(failed);

  return (
    <li className="flex flex-col gap-2 py-1">
      <div className="flex min-h-11 items-center justify-between gap-2">
        <span className="min-w-0 truncate">{alias.alias}</span>
        {alias.decided_in_queue ? (
          <Link
            to="/ricette/importa"
            className="inline-flex min-h-11 shrink-0 items-center text-sm font-medium text-brand"
          >
            Deciso nella coda
          </Link>
        ) : (
          <span className="flex shrink-0 gap-1">
            <button
              type="button"
              disabled={busy}
              aria-expanded={moving}
              aria-label={`Sposta l'alias «${alias.alias}»`}
              onClick={() => setMoving((open) => !open)}
              className={buttonClasses("ghost")}
            >
              Sposta
            </button>
            <button
              type="button"
              disabled={busy}
              aria-label={`Togli l'alias «${alias.alias}»`}
              onClick={() => remove.mutate()}
              className={buttonClasses("danger")}
            >
              Togli
            </button>
          </span>
        )}
      </div>
      {moving && (
        <IngredientPicker
          label={`Sposta «${alias.alias}» sotto`}
          failureNote="L'alias resta dov'è: riprova tra poco."
          disabled={busy}
          onPick={(target) => {
            setMoving(false);
            move.mutate(target);
          }}
        />
      )}
      {refusal?.code === "import_alias" && (
        <Alert>
          {refusal.detail}{" "}
          <Link to="/ricette/importa" className="font-medium text-brand">
            Vai alla coda
          </Link>
        </Alert>
      )}
      {refusal !== null && refusal.code !== "import_alias" && <Alert>{refusal.detail}</Alert>}
      {failed && refusal === null && (
        <Alert>Non sono riuscito a correggere l'alias. È ancora qui: riprova.</Alert>
      )}
    </li>
  );
}
```

Crea `frontend/src/features/registry/IngredientScreen.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { Alert } from "../../components/ui/Alert";
import { Card } from "../../components/ui/Card";
import { Screen } from "../../components/ui/Screen";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { AliasRow } from "./AliasRow";
import { fetchIngredientDetail } from "./api";
import { backFrom, originFrom, productPath } from "./origin";
import { usageText } from "./wording";

/** La scheda dell'ingrediente (spec S9 §6.3).
 *
 * `key` sull'id: passando da una scheda all'altra — la fusione porta al vincitore, un
 * link porta a un altro ingrediente — React Router riusa lo stesso componente, e senza
 * la chiave la scheda nuova erediterebbe il pannello aperto della precedente. */
export function IngredientScreen() {
  const { id = "" } = useParams();
  return <IngredientCard key={id} id={id} />;
}

/** Prima dice cos'è e dove è usato — il peso di una correzione si vede prima di farla —
 * poi gli alias e i prodotti. Le correzioni stanno sopra, e vengono dal servizio unico
 * dell'anagrafica: lo schermo le chiede e mostra il rifiuto con il suo passo dopo. */
function IngredientCard({ id }: { id: string }) {
  const [params] = useSearchParams();
  const origin = originFrom(params.get("da"));
  const back = backFrom(origin);

  const {
    data: ingredient,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["registry", "ingredient", id],
    queryFn: () => fetchIngredientDetail(id),
  });

  if (isLoading) {
    return (
      <Screen title="Ingrediente" back={back}>
        <p className="text-ink-soft">Carico…</p>
      </Screen>
    );
  }

  if (isError || !ingredient) {
    // un ingrediente unito a un altro sparisce: un link vecchio porta qui, e «riprova»
    // non potrebbe mai riuscire
    const gone = error instanceof ApiError && error.status === 404;
    return (
      <Screen title="Ingrediente" back={back}>
        <Alert>
          {gone
            ? "Questo ingrediente non c'è più: forse è stato unito a un altro. Cercalo in anagrafica."
            : "Non sono riuscito a leggere questo ingrediente."}
        </Alert>
        {!gone && (
          <button
            type="button"
            onClick={() => void refetch()}
            className={`${buttonClasses("secondary")} mt-3`}
          >
            Riprova
          </button>
        )}
      </Screen>
    );
  }

  return (
    <Screen
      title={ingredient.display_name}
      subtitle={`${ingredient.category} · ${usageText(ingredient.usage)}`}
      back={back}
    >
      <SectionHeading>Alias</SectionHeading>
      {ingredient.aliases.length === 0 ? (
        <p className="px-1 text-sm text-ink-soft">Nessun alias: si trova solo col suo nome.</p>
      ) : (
        <Card pad={false}>
          <ul className="divide-y divide-line px-3">
            {ingredient.aliases.map((alias) => (
              <AliasRow key={alias.id} ingredientId={ingredient.id} alias={alias} />
            ))}
          </ul>
        </Card>
      )}

      <SectionHeading>Prodotti</SectionHeading>
      {ingredient.products.length === 0 ? (
        <p className="px-1 text-sm text-ink-soft">Nessun prodotto sotto questo ingrediente.</p>
      ) : (
        <Card pad={false}>
          <ul className="divide-y divide-line">
            {ingredient.products.map((product) => (
              <li key={product.id}>
                <Link
                  to={productPath(product.id, origin)}
                  className="flex min-h-12 items-baseline gap-2 px-3 py-2.5"
                >
                  <span className="min-w-0 truncate font-medium">{product.name}</span>
                  {product.brand && (
                    <span className="ml-auto shrink-0 text-sm text-ink-faint">{product.brand}</span>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </Screen>
  );
}
```

In `frontend/src/App.tsx`: `import { IngredientScreen } from "./features/registry/IngredientScreen";`
e, dopo la rotta `/anagrafica`:

```tsx
            <Route path="/anagrafica/ingrediente/:id" element={<IngredientScreen />} />
```

- [ ] **Step 4: eseguilo e verifica che passi**

Run: `cd frontend && npx vitest run src/features/registry && npm run lint && npm run typecheck`
Expected: PASS.

- [ ] **Step 5: commit**

```bash
git add frontend/src/domain/types.ts frontend/src/features/registry frontend/src/App.tsx
git commit -m "$(cat <<'EOF'
anagrafica: la scheda dell'ingrediente, con alias e prodotti

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 16: Cambia reparto

**File:**
- Create: `frontend/src/features/registry/CategoryForm.tsx`
- Modify: `frontend/src/features/registry/IngredientScreen.tsx`
- Test: `frontend/src/features/registry/IngredientScreen.test.tsx`

**Interfacce:**
- Consuma: `patchIngredient`, `refreshAfterCorrection`, `registryRefusal` (Task 15);
  `FOOD_CATEGORIES`, `NON_FOOD_CATEGORIES` (`frontend/src/domain/categories.ts`).
- Produce: `CategoryForm({ ingredient: IngredientDetail, onDone: () => void })`; in
  `IngredientCard` lo stato `panel: Panel | null` con `type Panel = { kind: "category" }`
  e la fila delle azioni con «Cambia reparto».

- [ ] **Step 1: scrivi il test che fallisce**

In `IngredientScreen.test.tsx`, dentro `describe("IngredientScreen", …)`, in fondo:

```tsx
  it("«Cambia reparto» manda il reparto scelto, e si richiude", async () => {
    const spy = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") return [{ ...POMODORI, category: "legumi" }, 200];
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Cambia reparto" }));
    await userEvent.selectOptions(screen.getByLabelText("Reparto"), "legumi");
    await userEvent.click(screen.getByRole("button", { name: "Salva il reparto" }));

    await waitFor(() => expect(callsTo(spy, "PATCH", "/ingredients/i-pomodori")).toHaveLength(1));
    const [, init] = callsTo(spy, "PATCH", "/ingredients/i-pomodori")[0];
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({ category: "legumi" });
    await waitFor(() => expect(screen.queryByLabelText("Reparto")).toBeNull());
  });

  it("il rifiuto per le ricette le elenca, ciascuna col suo link", async () => {
    stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") {
        return [{
          code: "non_food_in_recipes",
          detail:
            "«Pomodori» è in 42 ricette: non può diventare non alimentare finché una ricetta lo usa.",
          recipe_count: 42,
          recipes: [{ id: "r1", title: "Sugo semplice" }],
        }, 409];
      }
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Cambia reparto" }));
    await userEvent.selectOptions(screen.getByLabelText("Reparto"), "casa");
    await userEvent.click(screen.getByRole("button", { name: "Salva il reparto" }));

    expect(await screen.findByText(/non può diventare non alimentare/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sugo semplice" })).toHaveAttribute("href", "/ricette/r1");
    expect(screen.getByText("e altre 41.")).toBeInTheDocument();
    // il reparto scelto resta scelto: si corregge, non si riscrive da capo
    expect(screen.getByLabelText("Reparto")).toHaveValue("casa");
  });
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `cd frontend && npx vitest run src/features/registry/IngredientScreen.test.tsx`
Expected: FAIL — `Unable to find an accessible element with the role "button" and name "Cambia reparto"`.

- [ ] **Step 3: implementazione minima**

Crea `frontend/src/features/registry/CategoryForm.tsx`:

```tsx
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Alert } from "../../components/ui/Alert";
import { Card } from "../../components/ui/Card";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { FOOD_CATEGORIES, NON_FOOD_CATEGORIES } from "../../domain/categories";
import type { IngredientDetail } from "../../domain/types";
import { patchIngredient, refreshAfterCorrection, registryRefusal } from "./api";

/** «Cambia reparto» (spec §6.3). Tutti i reparti, i non alimentari compresi: in
 * anagrafica si corregge anche il detersivo creato in «latticini». Il rifiuto per le
 * ricette le elenca, ciascuna col suo link — è da lì che si toglie l'ingrediente, se
 * davvero non è cibo (spec §7). */
export function CategoryForm({
  ingredient,
  onDone,
}: {
  ingredient: IngredientDetail;
  onDone: () => void;
}) {
  const queryClient = useQueryClient();
  const [category, setCategory] = useState(ingredient.category);
  const save = useMutation({
    mutationFn: (next: string) => patchIngredient(ingredient.id, { category: next }),
    onSuccess: async () => {
      await refreshAfterCorrection(queryClient);
      onDone();
    },
  });
  const refusal = registryRefusal(save.error);

  return (
    <Card as="section" className="mt-2 flex flex-col gap-3">
      <label className="text-sm font-medium text-ink-soft">
        Reparto
        <select
          value={category}
          onChange={(event) => setCategory(event.target.value)}
          disabled={save.isPending}
          className="mt-1.5"
        >
          {FOOD_CATEGORIES.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
          {/* staccati, come in «Sistema la spesa»: non sono un reparto in più, sono la
              metà dell'anagrafica che le ricette non vedono */}
          <optgroup label="Non alimentari">
            {NON_FOOD_CATEGORIES.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </optgroup>
        </select>
      </label>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={save.isPending || category === ingredient.category}
          onClick={() => save.mutate(category)}
          className={buttonClasses("primary")}
        >
          Salva il reparto
        </button>
        <button type="button" onClick={onDone} className={buttonClasses("ghost")}>
          Lascia com'è
        </button>
      </div>
      {refusal?.code === "non_food_in_recipes" && (
        <div role="alert" className="flex flex-col gap-1 text-sm">
          <p className="text-danger">{refusal.detail}</p>
          <ul>
            {refusal.recipes.map((recipe) => (
              <li key={recipe.id}>
                <Link
                  to={`/ricette/${recipe.id}`}
                  className="inline-flex min-h-11 items-center font-medium text-brand"
                >
                  {recipe.title}
                </Link>
              </li>
            ))}
          </ul>
          {refusal.recipe_count > refusal.recipes.length && (
            <p className="text-ink-soft">e altre {refusal.recipe_count - refusal.recipes.length}.</p>
          )}
        </div>
      )}
      {refusal !== null && refusal.code !== "non_food_in_recipes" && <Alert>{refusal.detail}</Alert>}
      {save.isError && refusal === null && (
        <Alert>
          Non sono riuscito a cambiare il reparto. È ancora «{ingredient.category}»: riprova.
        </Alert>
      )}
    </Card>
  );
}
```

In `frontend/src/features/registry/IngredientScreen.tsx`:
- in cima, `import { useState } from "react";`, e dopo l'import di `AliasRow`
  `import { CategoryForm } from "./CategoryForm";`;
- sopra `IngredientCard`: `type Panel = { kind: "category" };`
- in `IngredientCard`, subito dopo la chiamata a `useQuery` (prima di `if (isLoading)`):
  ```tsx
  // un pannello solo alla volta: due moduli aperti su una scheda del telefono
  // spingerebbero l'altro fuori schermo
  const [panel, setPanel] = useState<Panel | null>(null);
  ```
- nel `return` finale, subito prima di `<SectionHeading>Alias</SectionHeading>`:
  ```tsx
      <div className="flex flex-wrap gap-2 pb-1">
        <button
          type="button"
          onClick={() => setPanel({ kind: "category" })}
          className={buttonClasses("secondary")}
        >
          Cambia reparto
        </button>
      </div>
      {panel?.kind === "category" && (
        <CategoryForm ingredient={ingredient} onDone={() => setPanel(null)} />
      )}
  ```

- [ ] **Step 4: eseguilo e verifica che passi**

Run: `cd frontend && npx vitest run src/features/registry && npm run lint && npm run typecheck`
Expected: PASS.

- [ ] **Step 5: commit**

```bash
git add frontend/src/features/registry/CategoryForm.tsx frontend/src/features/registry/IngredientScreen.tsx frontend/src/features/registry/IngredientScreen.test.tsx
git commit -m "$(cat <<'EOF'
anagrafica: cambiare reparto, e il rifiuto che elenca le ricette

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 17: Unisci, con l'anteprima

**File:**
- Create: `frontend/src/features/registry/MergePanel.tsx`
- Modify: `frontend/src/features/registry/wording.ts`, `wording.test.ts`
- Modify: `frontend/src/features/registry/IngredientScreen.tsx`
- Test: `frontend/src/features/registry/IngredientScreen.test.tsx`

**Interfacce:**
- Consuma: `mergeIngredient`, `refreshAfterCorrection`, `registryRefusal`,
  `ingredientPath`, `Origin` (Task 15); `CategoryForm` e `Panel` (Task 16);
  `defaultQueryRetryPredicate`.
- Produce:
  - `mergePreviewText(counts: MergeCounts): string`, `mergeDoneText(counts: MergeCounts): string`
  - `MergePanel({ ingredient, initialWinner: Ingredient | null, origin: Origin, onClose, onChangeCategory })`
  - chiave dell'anteprima: `["registry", "merge-preview", ingredientId, winnerId]`
  - `type Panel = { kind: "category" } | { kind: "merge"; winner: Ingredient | null }`
  - dopo «Unisci», `navigate(ingredientPath(winner_id, origin), { state: { merged: counts } })`.

- [ ] **Step 1: scrivi il test che fallisce**

In `wording.test.ts` l'import diventa
`import { mergeDoneText, mergePreviewText, usageText } from "./wording";`, più
`import type { MergeCounts } from "../../domain/types";`. In fondo:

```ts
const CONTI: MergeCounts = {
  dry_run: true, loser_name: "pomodori", winner_id: "i-pomodoro", winner_name: "pomodoro",
  recipes_rebuilt: 2, recipe_lines_moved: 1, pantry_items: 1, shopping_items: 0,
  products: 0, aliases: 2, cooking_events_relinked: 0,
};

describe("mergePreviewText", () => {
  it("è la frase della spec, parola per parola", () => {
    expect(mergePreviewText(CONTI)).toBe(
      "Si spostano 3 ricette, 1 elemento di dispensa, 2 alias. «pomodori» diventa un alias di «pomodoro». Non si annulla."
    );
  });

  it("al singolare, e con niente da spostare", () => {
    const una = { ...CONTI, recipes_rebuilt: 0, recipe_lines_moved: 1, pantry_items: 0, aliases: 0 };
    expect(mergePreviewText(una)).toBe(
      "Si sposta 1 ricetta. «pomodori» diventa un alias di «pomodoro». Non si annulla."
    );
    const niente = { ...una, recipe_lines_moved: 0 };
    expect(mergePreviewText(niente)).toBe(
      "Non si sposta niente. «pomodori» diventa un alias di «pomodoro». Non si annulla."
    );
  });

  it("dice le cotture che si ri-legano: chi fonde lo vuole sapere (spec §5.2)", () => {
    expect(mergePreviewText({ ...CONTI, cooking_events_relinked: 2 })).toContain(
      "2 cotture già registrate ritrovano la loro ricetta."
    );
  });
});

describe("mergeDoneText", () => {
  it("dice l'esito sulla scheda del vincitore", () => {
    expect(mergeDoneText({ ...CONTI, dry_run: false })).toBe(
      "Uniti: «pomodori» ora è un alias di «pomodoro». Spostati qui: 3 ricette, 1 elemento di dispensa, 2 alias."
    );
  });
});
```

In `IngredientScreen.test.tsx`: `within` nell'import da `@testing-library/react`,
`MergeCounts` nell'import dei tipi. Dopo `POMODORO`:

```tsx
const POMODORO_SCHEDA: IngredientDetail = {
  ...POMODORO, aliases: [], products: [], usage: { recipes: 3, pantry: 1, shopping: 0 },
};
const DETERSIVO: Ingredient = {
  id: "i-detersivo", name: "detersivo", display_name: "Detersivo", category: "casa", kind: "non_food",
};
const ANTEPRIMA: MergeCounts = {
  dry_run: true, loser_name: "pomodori", winner_id: "i-pomodoro", winner_name: "pomodoro",
  recipes_rebuilt: 2, recipe_lines_moved: 1, pantry_items: 1, shopping_items: 0, products: 0,
  aliases: 2, cooking_events_relinked: 0,
};
```

e in fondo al `describe`:

```tsx
  it("l'anteprima dice cosa si sposta, e «Unisci» porta al vincitore con l'esito in vista", async () => {
    const spy = stubRoutedFetch((path, init) => {
      if (path.endsWith("/ingredients/i-pomodori/merge")) {
        const { dry_run } = JSON.parse(String(init?.body));
        return [{ ...ANTEPRIMA, dry_run }, 200];
      }
      if (path.endsWith("/ingredients/i-pomodoro")) return [POMODORO_SCHEDA, 200];
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Unisci a un altro…" }));
    await userEvent.type(screen.getByLabelText("Unisci a"), "pomod");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));

    expect(
      await screen.findByText(
        "Si spostano 3 ricette, 1 elemento di dispensa, 2 alias. «pomodori» diventa un alias di «pomodoro». Non si annulla."
      )
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Unisci" }));

    expect(await screen.findByRole("heading", { name: "Pomodoro" })).toBeInTheDocument();
    expect(screen.getByText(/Uniti: «pomodori» ora è un alias di «pomodoro»\./)).toBeInTheDocument();
    const corpi = callsTo(spy, "POST", "/ingredients/i-pomodori/merge").map(([, init]) =>
      JSON.parse(String((init as RequestInit).body))
    );
    expect(corpi).toEqual([
      { into: "i-pomodoro", dry_run: true },
      { into: "i-pomodoro", dry_run: false },
    ]);
  });

  it("tra un alimento e una voce non alimentare offre il cambio di reparto", async () => {
    stubRoutedFetch((path) => {
      if (path.endsWith("/ingredients/i-pomodori/merge")) {
        return [{
          code: "kind_mismatch",
          detail:
            "«Pomodori» e «Detersivo» stanno in due metà diverse dell'anagrafica: un alimento e una voce non alimentare non si uniscono. Prima porta «Pomodori» nello stesso reparto di «Detersivo», poi uniscili.",
          existing: DETERSIVO,
        }, 409];
      }
      if (path.includes("/ingredients/search")) return [[DETERSIVO], 200];
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Unisci a un altro…" }));
    await userEvent.type(screen.getByLabelText("Unisci a"), "deter");
    await userEvent.click(await screen.findByRole("option", { name: /Detersivo/ }));

    const avviso = await screen.findByRole("alert");
    expect(avviso).toHaveTextContent("poi uniscili");
    await userEvent.click(within(avviso).getByRole("button", { name: "Cambia reparto" }));
    expect(screen.getByLabelText("Reparto")).toBeInTheDocument();
  });
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `cd frontend && npx vitest run src/features/registry`
Expected: FAIL — `wording.test.ts` con `mergePreviewText is not a function` (o l'import
che non si risolve), e `Unable to find … name "Unisci a un altro…"`.

- [ ] **Step 3: implementazione minima**

In `wording.ts`, l'import dei tipi diventa
`import type { IngredientUsage, MergeCounts } from "../../domain/types";`, e in fondo:

```ts
type Part = { n: number; one: string; many: string };

/** Quel che una fusione sposta, nell'ordine in cui interessa: prima le ricette, per
 * ultimi gli alias. Una parte a zero non si dice. */
function movedParts(counts: MergeCounts): Part[] {
  return [
    { n: counts.recipes_rebuilt + counts.recipe_lines_moved, one: "ricetta", many: "ricette" },
    { n: counts.pantry_items, one: "elemento di dispensa", many: "elementi di dispensa" },
    { n: counts.shopping_items, one: "voce di lista", many: "voci di lista" },
    { n: counts.products, one: "prodotto", many: "prodotti" },
    { n: counts.aliases, one: "alias", many: "alias" },
  ].filter((part) => part.n > 0);
}

function listed(parts: Part[]): string {
  return parts.map((part) => `${part.n} ${part.n === 1 ? part.one : part.many}`).join(", ");
}

/** L'anteprima della fusione (spec §6.3): «Si spostano 3 ricette, 1 elemento di
 * dispensa, 2 alias. «pomodori» diventa un alias di «pomodoro». Non si annulla.» Le
 * cotture si dicono quando ci sono, perché chi fonde lo vuole sapere (§5.2). */
export function mergePreviewText(counts: MergeCounts): string {
  const parts = movedParts(counts);
  const verb = parts.length === 1 && parts[0].n === 1 ? "Si sposta" : "Si spostano";
  const moved = parts.length === 0 ? "Non si sposta niente." : `${verb} ${listed(parts)}.`;
  const n = counts.cooking_events_relinked;
  const cooked =
    n === 0
      ? ""
      : n === 1
        ? "1 cottura già registrata ritrova la sua ricetta."
        : `${n} cotture già registrate ritrovano la loro ricetta.`;
  return [
    moved,
    `«${counts.loser_name}» diventa un alias di «${counts.winner_name}».`,
    cooked,
    "Non si annulla.",
  ]
    .filter((sentence) => sentence !== "")
    .join(" ");
}

/** L'esito, in vista sulla scheda del vincitore dopo la fusione. */
export function mergeDoneText(counts: MergeCounts): string {
  const parts = movedParts(counts);
  return [
    `Uniti: «${counts.loser_name}» ora è un alias di «${counts.winner_name}».`,
    parts.length === 0 ? "" : `Spostati qui: ${listed(parts)}.`,
  ]
    .filter((sentence) => sentence !== "")
    .join(" ");
}
```

Crea `frontend/src/features/registry/MergePanel.tsx`:

```tsx
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { IngredientPicker } from "../../components/IngredientPicker";
import { Alert } from "../../components/ui/Alert";
import { Card } from "../../components/ui/Card";
import { buttonClasses } from "../../components/ui/buttonClasses";
import type { Ingredient, IngredientDetail } from "../../domain/types";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import { mergeIngredient, refreshAfterCorrection, registryRefusal } from "./api";
import { ingredientPath, type Origin } from "./origin";
import { mergePreviewText } from "./wording";

/** «Unisci a un altro…» (spec §6.3): la scelta del vincitore, l'anteprima, «Unisci».
 *
 * L'anteprima è una query e non una mutazione: è il dato di una coppia (perdente,
 * vincitore), e il server la calcola eseguendo la fusione vera dentro un SAVEPOINT che
 * annulla (§5.1). `gcTime: 0` perché un'anteprima vecchia, riletta dopo un'altra
 * correzione, direbbe numeri che non valgono più. Un rifiuto non si ritenta: è una
 * risposta, non un guasto. */
export function MergePanel({
  ingredient,
  initialWinner,
  origin,
  onClose,
  onChangeCategory,
}: {
  ingredient: IngredientDetail;
  /** già scelto quando si arriva da «Uniscili» della rinomina */
  initialWinner: Ingredient | null;
  origin: Origin;
  onClose: () => void;
  /** l'uscita del rifiuto `kind_mismatch`: il cambio di reparto (spec §7) */
  onChangeCategory: () => void;
}) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [winner, setWinner] = useState<Ingredient | null>(initialWinner);

  const preview = useQuery({
    queryKey: ["registry", "merge-preview", ingredient.id, winner?.id ?? null],
    queryFn: () =>
      winner
        ? mergeIngredient(ingredient.id, winner.id, true)
        : Promise.reject(new Error("nessun ingrediente scelto")),
    enabled: winner !== null,
    gcTime: 0,
    retry: (count, error) => registryRefusal(error) === null && defaultQueryRetryPredicate(count, error),
  });

  const merge = useMutation({
    mutationFn: (into: string) => mergeIngredient(ingredient.id, into, false),
    onSuccess: (counts) => {
      // Prima si segna tutto come vecchio senza rileggere, poi si va: rileggere subito
      // chiederebbe al server la scheda del perdente, che non esiste più. La scheda del
      // vincitore, montata dopo, rilegge da sé.
      void refreshAfterCorrection(queryClient, false);
      navigate(ingredientPath(counts.winner_id, origin), { state: { merged: counts } });
    },
  });

  const counts = preview.data;
  const refusal = registryRefusal(preview.error) ?? registryRefusal(merge.error);

  return (
    <Card as="section" className="mt-2 flex flex-col gap-3">
      <h2 className="font-medium">Unisci «{ingredient.display_name}» a un altro ingrediente</h2>

      {winner === null ? (
        <IngredientPicker
          label="Unisci a"
          failureNote="Il doppione resta com'è: riprova tra poco."
          onPick={setWinner}
        />
      ) : (
        <p className="flex flex-wrap items-center gap-2 text-sm">
          <span>
            Resta: <span className="font-medium">«{winner.display_name}»</span>
          </span>
          <button type="button" onClick={() => setWinner(null)} className={buttonClasses("ghost")}>
            Cambia
          </button>
        </p>
      )}

      {winner !== null && preview.isPending && (
        <p className="text-sm text-ink-soft">Calcolo cosa si sposta…</p>
      )}

      {counts && (
        <>
          <p className="text-sm">{mergePreviewText(counts)}</p>
          <button
            type="button"
            disabled={merge.isPending}
            onClick={() => merge.mutate(counts.winner_id)}
            className={buttonClasses("warn", "block")}
          >
            {merge.isPending ? "Unisco…" : "Unisci"}
          </button>
        </>
      )}

      {refusal?.code === "kind_mismatch" && (
        <div role="alert" className="flex flex-col gap-2 text-sm">
          <p className="text-danger">{refusal.detail}</p>
          <button type="button" onClick={onChangeCategory} className={buttonClasses("secondary")}>
            Cambia reparto
          </button>
        </div>
      )}
      {refusal !== null && refusal.code !== "kind_mismatch" && <Alert>{refusal.detail}</Alert>}
      {refusal === null && preview.isError && (
        <div role="alert" className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-danger">Non sono riuscito a calcolare l'anteprima.</span>
          <button type="button" onClick={() => void preview.refetch()} className={buttonClasses("secondary")}>
            Riprova
          </button>
        </div>
      )}
      {refusal === null && merge.isError && (
        <Alert>Non sono riuscito a unirli. Niente è cambiato: riprova.</Alert>
      )}

      <button type="button" onClick={onClose} className={buttonClasses("ghost")}>
        Lascia com'è
      </button>
    </Card>
  );
}
```

In `IngredientScreen.tsx`:
- l'import da `react-router-dom` diventa
  `import { Link, useLocation, useParams, useSearchParams } from "react-router-dom";`;
  aggiungi `import { MergePanel } from "./MergePanel";`,
  `import type { Ingredient, MergeCounts } from "../../domain/types";`, e l'import da
  `./wording` diventa `import { mergeDoneText, usageText } from "./wording";`;
- `type Panel` diventa
  `type Panel = { kind: "category" } | { kind: "merge"; winner: Ingredient | null };`
- in `IngredientCard`, subito dopo `const [panel, setPanel] = …`:
  ```tsx
  // l'esito di una fusione arriva con la navigazione, dalla scheda del perdente che non
  // c'è più: è qui, sulla scheda del vincitore, che si dice (spec §6.3)
  const location = useLocation();
  const merged = (location.state as { merged?: MergeCounts } | null)?.merged ?? null;
  ```
- nel `return` finale, come primo figlio di `<Screen>`:
  ```tsx
      {merged && (
        <p role="status" className="pb-2 text-sm font-medium text-brand">
          {mergeDoneText(merged)}
        </p>
      )}
  ```
- nella fila delle azioni, dopo «Cambia reparto»:
  ```tsx
        <button
          type="button"
          onClick={() => setPanel({ kind: "merge", winner: null })}
          className={buttonClasses("secondary")}
        >
          Unisci a un altro…
        </button>
  ```
- dopo il blocco `{panel?.kind === "category" && ( … )}`:
  ```tsx
      {panel?.kind === "merge" && (
        <MergePanel
          key={panel.winner?.id ?? "da-scegliere"}
          ingredient={ingredient}
          initialWinner={panel.winner}
          origin={origin}
          onClose={() => setPanel(null)}
          onChangeCategory={() => setPanel({ kind: "category" })}
        />
      )}
  ```

- [ ] **Step 4: eseguilo e verifica che passi**

Run: `cd frontend && npx vitest run src/features/registry && npm run lint && npm run typecheck`
Expected: PASS.

- [ ] **Step 5: commit**

```bash
git add frontend/src/features/registry
git commit -m "$(cat <<'EOF'
anagrafica: unire due ingredienti, con l'anteprima che è la fusione stessa

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 18: Rinomina

**File:**
- Create: `frontend/src/features/registry/RenameForm.tsx`
- Modify: `frontend/src/features/registry/IngredientScreen.tsx`
- Test: `frontend/src/features/registry/IngredientScreen.test.tsx`

**Interfacce:**
- Consuma: `patchIngredient`, `refreshAfterCorrection`, `registryRefusal` (Task 15);
  `MergePanel` e `Panel` (Task 17).
- Produce: `RenameForm({ ingredient, onDone, onMergeWith: (existing: Ingredient) => void })`;
  `type Panel` guadagna `{ kind: "rename" }`.

- [ ] **Step 1: scrivi il test che fallisce**

In fondo al `describe` di `IngredientScreen.test.tsx`:

```tsx
  it("«Rinomina» manda il nome nuovo e si richiude", async () => {
    const spy = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") {
        return [{ ...POMODORI, name: "pomodori rossi", display_name: "Pomodori rossi" }, 200];
      }
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Rinomina" }));
    const campo = screen.getByLabelText("Nuovo nome");
    await userEvent.clear(campo);
    await userEvent.type(campo, "Pomodori rossi");
    await userEvent.click(screen.getByRole("button", { name: "Salva il nome" }));

    await waitFor(() => expect(callsTo(spy, "PATCH", "/ingredients/i-pomodori")).toHaveLength(1));
    const [, init] = callsTo(spy, "PATCH", "/ingredients/i-pomodori")[0];
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({ name: "Pomodori rossi" });
    await waitFor(() => expect(screen.queryByLabelText("Nuovo nome")).toBeNull());
  });

  it("un nome già preso offre «Uniscili», e porta alla fusione con quel vincitore già scelto", async () => {
    const spy = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") {
        return [{
          code: "name_taken",
          detail: "«pomodoro» è già in anagrafica: uniscili invece di rinominare.",
          existing: POMODORO,
        }, 409];
      }
      if (path.endsWith("/ingredients/i-pomodori/merge")) return [ANTEPRIMA, 200];
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/ingrediente/i-pomodori");

    await userEvent.click(await screen.findByRole("button", { name: "Rinomina" }));
    const campo = screen.getByLabelText("Nuovo nome");
    await userEvent.clear(campo);
    await userEvent.type(campo, "Pomodoro");
    await userEvent.click(screen.getByRole("button", { name: "Salva il nome" }));

    expect(await screen.findByText("C'è già «Pomodoro». Uniscili?")).toBeInTheDocument();
    // il nome scritto resta nel campo: si corregge, non si riscrive (spec §7)
    expect(screen.getByLabelText("Nuovo nome")).toHaveValue("Pomodoro");
    await userEvent.click(screen.getByRole("button", { name: "Uniscili" }));

    expect(await screen.findByText(/«pomodori» diventa un alias di «pomodoro»/)).toBeInTheDocument();
    const [, init] = callsTo(spy, "POST", "/ingredients/i-pomodori/merge")[0];
    expect(JSON.parse(String((init as RequestInit).body))).toEqual({
      into: "i-pomodoro", dry_run: true,
    });
  });
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `cd frontend && npx vitest run src/features/registry/IngredientScreen.test.tsx`
Expected: FAIL — `Unable to find an accessible element with the role "button" and name "Rinomina"`.

- [ ] **Step 3: implementazione minima**

Crea `frontend/src/features/registry/RenameForm.tsx`:

```tsx
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Alert } from "../../components/ui/Alert";
import { Card } from "../../components/ui/Card";
import { buttonClasses } from "../../components/ui/buttonClasses";
import type { Ingredient, IngredientDetail } from "../../domain/types";
import { patchIngredient, refreshAfterCorrection, registryRefusal } from "./api";

/** «Rinomina» (spec §6.3). Un nome già preso non è un errore da riprovare: è un
 * doppione, e il rifiuto porta l'omonimo perché «Uniscili» apra la fusione con quel
 * vincitore già scelto (spec §7). Il nome scritto resta nel campo in ogni caso. */
export function RenameForm({
  ingredient,
  onDone,
  onMergeWith,
}: {
  ingredient: IngredientDetail;
  onDone: () => void;
  onMergeWith: (existing: Ingredient) => void;
}) {
  const queryClient = useQueryClient();
  const [name, setName] = useState(ingredient.display_name);
  const save = useMutation({
    mutationFn: (next: string) => patchIngredient(ingredient.id, { name: next }),
    onSuccess: async () => {
      await refreshAfterCorrection(queryClient);
      onDone();
    },
  });
  const refusal = registryRefusal(save.error);
  const existing = refusal?.code === "name_taken" ? (refusal.existing ?? null) : null;
  const cleaned = name.trim();

  return (
    <Card as="section" className="mt-2 flex flex-col gap-3">
      <label className="text-sm font-medium text-ink-soft">
        Nuovo nome
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          disabled={save.isPending}
          className="mt-1.5"
        />
      </label>
      <p className="text-xs text-ink-faint">
        Il nome di prima resta come alias: chi lo scrive in lista ritrova questo ingrediente.
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={save.isPending || cleaned === "" || cleaned === ingredient.display_name}
          onClick={() => save.mutate(cleaned)}
          className={buttonClasses("primary")}
        >
          Salva il nome
        </button>
        <button type="button" onClick={onDone} className={buttonClasses("ghost")}>
          Lascia com'è
        </button>
      </div>
      {existing && (
        <div role="alert" className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-danger">C'è già «{existing.display_name}». Uniscili?</span>
          <button
            type="button"
            onClick={() => onMergeWith(existing)}
            className={buttonClasses("warn")}
          >
            Uniscili
          </button>
        </div>
      )}
      {refusal !== null && existing === null && <Alert>{refusal.detail}</Alert>}
      {save.isError && refusal === null && (
        <Alert>Non sono riuscito a rinominarlo. Il nome che hai scritto è ancora qui: riprova.</Alert>
      )}
    </Card>
  );
}
```

In `IngredientScreen.tsx`:
- aggiungi `import { RenameForm } from "./RenameForm";`;
- `type Panel` diventa
  ```tsx
  type Panel =
    | { kind: "rename" }
    | { kind: "category" }
    | { kind: "merge"; winner: Ingredient | null };
  ```
- nella fila delle azioni, **prima** di «Cambia reparto»:
  ```tsx
        <button
          type="button"
          onClick={() => setPanel({ kind: "rename" })}
          className={buttonClasses("secondary")}
        >
          Rinomina
        </button>
  ```
- subito prima del blocco `{panel?.kind === "category" && ( … )}`:
  ```tsx
      {panel?.kind === "rename" && (
        <RenameForm
          ingredient={ingredient}
          onDone={() => setPanel(null)}
          onMergeWith={(existing) => setPanel({ kind: "merge", winner: existing })}
        />
      )}
  ```

- [ ] **Step 4: eseguilo e verifica che passi**

Run: `cd frontend && npx vitest run src/features/registry && npm run lint && npm run typecheck`
Expected: PASS.

- [ ] **Step 5: commit**

```bash
git add frontend/src/features/registry/RenameForm.tsx frontend/src/features/registry/IngredientScreen.tsx frontend/src/features/registry/IngredientScreen.test.tsx
git commit -m "$(cat <<'EOF'
anagrafica: rinominare, e il nome già preso che porta alla fusione

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 19: La scheda del prodotto — nome, marca, ingrediente

**File:**
- Modify: `frontend/src/domain/types.ts` (in fondo), `frontend/src/features/registry/api.ts`
  (in fondo), `frontend/src/features/registry/wording.ts`, `wording.test.ts`
- Create: `frontend/src/features/registry/InlineField.tsx`
- Create: `frontend/src/features/registry/ProductScreen.tsx`
- Modify: `frontend/src/App.tsx` (import e una `Route`)
- Test: `frontend/src/features/registry/ProductScreen.test.tsx`

**Interfacce:**
- Consuma: le rotte del Task 10; `refreshAfterCorrection`, `originFrom`, `backFrom`,
  `ingredientPath` (Task 15); `IngredientPicker`.
- Produce:
  - tipo `ProductDetail`; `type ProductPatchBody`; `fetchProductDetail(id)`,
    `patchProduct(id, body)`, `deleteProduct(id)`
  - `movedText(product: ProductDetail): string`, `pantryText(n: number): string`
  - `InlineField({ label, value, placeholder?, inputMode?, onSave, describeError? })`: il
    pulsante si chiama `Salva <label in minuscolo>`
  - chiave di query della scheda: `["registry", "product", id]`
  - `ProductScreen` su `/anagrafica/prodotto/:id`.

- [ ] **Step 1: scrivi il test che fallisce**

In `wording.test.ts` l'import diventa
`import { mergeDoneText, mergePreviewText, movedText, pantryText, usageText } from "./wording";`
e quello dei tipi `import type { MergeCounts, ProductDetail } from "../../domain/types";`.
In fondo:

```ts
describe("movedText", () => {
  const SPOSTATO: ProductDetail = {
    id: "p1", name: "Parmigiano Reggiano 24 mesi", brand: null, barcode: null,
    valid_checksum: null, ingredient: { id: "i1", name: "parmigiano", display_name: "Parmigiano" },
    pantry_items: [{ id: "v1", status: "available", expires_on: null }],
  };

  it("dice sotto cosa è andato, e con quanti elementi di dispensa (spec §6.4)", () => {
    expect(movedText(SPOSTATO)).toBe("Spostato sotto «Parmigiano», con 1 elemento di dispensa.");
    expect(movedText({ ...SPOSTATO, pantry_items: [] })).toBe("Spostato sotto «Parmigiano».");
  });

  it("conta gli elementi in dispensa", () => {
    expect(pantryText(0)).toBe("Nessun elemento in dispensa.");
    expect(pantryText(2)).toBe("2 elementi in dispensa.");
  });
});
```

Crea `frontend/src/features/registry/ProductScreen.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { ProductScreen } from "./ProductScreen";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import type { Ingredient, ProductDetail } from "../../domain/types";

const REGGIANO: ProductDetail = {
  id: "p-reggiano", name: "Parmigiano Reggiano 24 mesi", brand: "Latteria",
  barcode: "8009876543217", valid_checksum: true,
  ingredient: { id: "i-burro", name: "burro", display_name: "Burro" },
  pantry_items: [{ id: "v1", status: "available", expires_on: null }],
};
const PARMIGIANO: Ingredient = {
  id: "i-parmigiano", name: "parmigiano", display_name: "Parmigiano", category: "latticini", kind: "food",
};

type FetchRoute = (path: string, init?: RequestInit) => [unknown, number];

function stubRoutedFetch(route: FetchRoute) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = route(String(url), init);
    return Promise.resolve(
      status === 204 ? new Response(null, { status }) : new Response(JSON.stringify(body), { status })
    );
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function bodiesOf(spy: ReturnType<typeof stubRoutedFetch>, method: string) {
  return spy.mock.calls
    .filter(([, init]) => (init as RequestInit | undefined)?.method === method)
    .map(([, init]) => JSON.parse(String((init as RequestInit).body ?? "null")));
}

function Where() {
  const location = useLocation();
  return <p>dove: {location.pathname + location.search}</p>;
}

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: defaultQueryRetryPredicate } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/anagrafica/prodotto/:id" element={<ProductScreen />} />
          <Route path="*" element={<Where />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function base(path: string): [unknown, number] | null {
  if (path.includes("/ingredients/search")) return [[PARMIGIANO], 200];
  if (path.endsWith("/products/p-reggiano")) return [REGGIANO, 200];
  return null;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ProductScreen", () => {
  it("nome e marca si salvano ciascuno col suo «Salva»; la marca vuota si toglie", async () => {
    const spy = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") return [REGGIANO, 200];
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/prodotto/p-reggiano");

    const nome = await screen.findByLabelText("Nome");
    await userEvent.clear(nome);
    await userEvent.type(nome, "Parmigiano Reggiano 30 mesi");
    await userEvent.click(screen.getByRole("button", { name: "Salva nome" }));
    await waitFor(() => expect(bodiesOf(spy, "PATCH")).toHaveLength(1));

    await userEvent.clear(screen.getByLabelText("Marca"));
    await userEvent.click(screen.getByRole("button", { name: "Salva marca" }));

    await waitFor(() =>
      expect(bodiesOf(spy, "PATCH")).toEqual([
        { name: "Parmigiano Reggiano 30 mesi" },
        { brand: null },
      ])
    );
  });

  it("un salvataggio fallito lascia il campo com'era scritto, e l'errore accanto", async () => {
    stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") return [{ detail: "rotto" }, 500];
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/prodotto/p-reggiano");

    const nome = await screen.findByLabelText("Nome");
    await userEvent.clear(nome);
    await userEvent.type(nome, "Parmigiano Reggiano 30 mesi");
    await userEvent.click(screen.getByRole("button", { name: "Salva nome" }));

    expect(
      await screen.findByText("Non sono riuscito a salvare. Quel che hai scritto è ancora qui: riprova.")
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Nome")).toHaveValue("Parmigiano Reggiano 30 mesi");
  });

  it("«Spostalo»: la scelta dell'ingrediente, senza filtro sul tipo, e il fatto detto dopo", async () => {
    const spostato: ProductDetail = {
      ...REGGIANO,
      ingredient: { id: "i-parmigiano", name: "parmigiano", display_name: "Parmigiano" },
    };
    const spy = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") return [spostato, 200];
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/prodotto/p-reggiano");

    expect(await screen.findByText("È sotto l'ingrediente sbagliato?")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Spostalo" }));
    await userEvent.type(screen.getByLabelText("Sposta sotto"), "parmig");
    await userEvent.click(await screen.findByRole("option", { name: /Parmigiano/ }));

    expect(
      await screen.findByText("Spostato sotto «Parmigiano», con 1 elemento di dispensa.")
    ).toBeInTheDocument();
    expect(bodiesOf(spy, "PATCH")).toEqual([{ ingredient_id: "i-parmigiano" }]);
    expect(spy.mock.calls.some(([url]) => String(url).includes("kind="))).toBe(false);
  });

  it("dalla dispensa: l'ingrediente è un link alla sua scheda, e l'origine segue", async () => {
    stubRoutedFetch((path) => base(path) ?? [{}, 404]);
    renderAt("/anagrafica/prodotto/p-reggiano?da=dispensa");

    expect(await screen.findByRole("heading", { name: "Parmigiano Reggiano 24 mesi" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Burro" })).toHaveAttribute(
      "href", "/anagrafica/ingrediente/i-burro?da=dispensa"
    );
    expect(screen.getByRole("link", { name: "Dispensa" })).toHaveAttribute("href", "/dispensa");
    expect(screen.getByText("1 elemento in dispensa.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `cd frontend && npx vitest run src/features/registry`
Expected: FAIL — `Failed to resolve import "./ProductScreen"`, e in `wording.test.ts`
`movedText` non esportato.

- [ ] **Step 3: implementazione minima**

In fondo a `frontend/src/domain/types.ts`:

```ts
/** La scheda del prodotto (spec S9 §6.4): è anche la scheda dell'elemento di dispensa. */
export interface ProductDetail {
  id: string;
  name: string;
  brand: string | null;
  barcode: string | null;
  /** Se la cifra di controllo torna, detto dal server; `null` senza codice. */
  valid_checksum: boolean | null;
  ingredient: { id: string; name: string; display_name: string };
  /** Solo gli attivi: quelli che chi guarda la dispensa vede. */
  pantry_items: { id: string; status: PantryStatus; expires_on: string | null }[];
}
```

In `frontend/src/features/registry/api.ts`, `ProductDetail` nell'import dei tipi, e in
fondo:

```ts
/** Il corpo della PATCH del prodotto. `brand: null` toglie la marca, `barcode: null`
 * toglie il codice: il server legge i campi presenti, non quelli valorizzati. */
export type ProductPatchBody = {
  name?: string;
  brand?: string | null;
  ingredient_id?: string;
  barcode?: string | null;
  /** prende il codice al prodotto che l'ha già: l'uscita di `barcode_taken` */
  take_barcode?: boolean;
  /** usa il codice anche se la cifra di controllo non torna: l'uscita di `bad_checksum` */
  accept_bad_checksum?: boolean;
};

export function fetchProductDetail(id: string) {
  return apiFetch<ProductDetail>(`/products/${id}`);
}

export function patchProduct(id: string, body: ProductPatchBody) {
  return apiFetch<ProductDetail>(`/products/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export function deleteProduct(id: string) {
  return apiFetch<{ loose_pantry_items: number }>(`/products/${id}`, { method: "DELETE" });
}
```

In `wording.ts`, l'import dei tipi diventa
`import type { IngredientUsage, MergeCounts, ProductDetail } from "../../domain/types";`,
e in fondo:

```ts
function pantryItems(n: number): string {
  return n === 1 ? "1 elemento" : `${n} elementi`;
}

/** Dopo lo spostamento (spec §6.4): «Spostato sotto «parmigiano», con 1 elemento di
 * dispensa». Il conto è quello degli attivi che il server rimanda, cioè quelli che la
 * dispensa mostra. */
export function movedText(product: ProductDetail): string {
  const n = product.pantry_items.length;
  const where = `Spostato sotto «${product.ingredient.display_name}»`;
  return n === 0 ? `${where}.` : `${where}, con ${pantryItems(n)} di dispensa.`;
}

export function pantryText(n: number): string {
  return n === 0 ? "Nessun elemento in dispensa." : `${pantryItems(n)} in dispensa.`;
}
```

Crea `frontend/src/features/registry/InlineField.tsx`:

```tsx
import { useId, useState, type ReactNode } from "react";
import { Alert } from "../../components/ui/Alert";
import { buttonClasses } from "../../components/ui/buttonClasses";

/** Un campo modificabile in loco, con il suo «Salva» (spec §6.4).
 *
 * Un «Salva» per campo e non uno per la scheda: il nome, la marca e il codice sono tre
 * correzioni indipendenti, e un rifiuto su una non deve trattenere le altre. Se il
 * salvataggio fallisce il campo resta com'era scritto, e l'errore accanto (spec §7):
 * `describeError` lo dice a modo suo quando il rifiuto ha un'uscita da offrire. */
export function InlineField({
  label,
  value,
  placeholder,
  inputMode,
  onSave,
  describeError,
}: {
  label: string;
  value: string;
  placeholder?: string;
  inputMode?: "text" | "numeric";
  onSave: (next: string) => Promise<unknown>;
  describeError?: (error: unknown, draft: string) => ReactNode;
}) {
  const inputId = useId();
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  // Il valore salvato cambia da fuori — la scheda riletta dopo un salvataggio, o dopo
  // «Sposta il codice qui» — e il campo lo riprende, perdendo l'errore vecchio. Durante
  // il disegno e non in un effetto, come in PantryRow: un effetto mostrerebbe per un
  // disegno il valore vecchio.
  const [seen, setSeen] = useState(value);
  if (value !== seen) {
    setSeen(value);
    setDraft(value);
    setError(null);
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await onSave(draft.trim());
    } catch (caught) {
      setError(caught);
    } finally {
      setSaving(false);
    }
  }

  const changed = draft.trim() !== value;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={inputId} className="text-sm font-medium text-ink-soft">
        {label}
      </label>
      <div className="flex items-center gap-2">
        <input
          id={inputId}
          value={draft}
          placeholder={placeholder}
          inputMode={inputMode}
          disabled={saving}
          onChange={(event) => setDraft(event.target.value)}
          className="min-w-0 flex-1"
        />
        <button
          type="button"
          aria-label={`Salva ${label.toLowerCase()}`}
          disabled={!changed || saving}
          onClick={() => void save()}
          className={`${buttonClasses("secondary")} shrink-0`}
        >
          Salva
        </button>
      </div>
      {error !== null &&
        (describeError ? (
          describeError(error, draft.trim())
        ) : (
          <Alert>Non sono riuscito a salvare. Quel che hai scritto è ancora qui: riprova.</Alert>
        ))}
    </div>
  );
}
```

Crea `frontend/src/features/registry/ProductScreen.tsx`:

```tsx
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { IngredientPicker } from "../../components/IngredientPicker";
import { Alert } from "../../components/ui/Alert";
import { Card } from "../../components/ui/Card";
import { Screen } from "../../components/ui/Screen";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { buttonClasses } from "../../components/ui/buttonClasses";
import type { Ingredient } from "../../domain/types";
import { InlineField } from "./InlineField";
import {
  fetchProductDetail,
  patchProduct,
  refreshAfterCorrection,
  type ProductPatchBody,
} from "./api";
import { backFrom, ingredientPath, originFrom } from "./origin";
import { movedText, pantryText } from "./wording";

/** La scheda del prodotto (spec S9 §6.4). È anche la scheda dell'elemento di dispensa:
 * dalla riga della dispensa si arriva qui, e l'ingrediente sta come link. Il caso del
 * parmigiano sotto «burro» sono due tocchi e una scelta.
 *
 * `key` sull'id, per la stessa ragione della scheda dell'ingrediente. */
export function ProductScreen() {
  const { id = "" } = useParams();
  return <ProductCard key={id} id={id} />;
}

function ProductCard({ id }: { id: string }) {
  const [params] = useSearchParams();
  const origin = originFrom(params.get("da"));
  const back = backFrom(origin);
  const queryClient = useQueryClient();
  const [moving, setMoving] = useState(false);
  const [movedNote, setMovedNote] = useState<string | null>(null);

  const {
    data: product,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["registry", "product", id],
    queryFn: () => fetchProductDetail(id),
  });
  const patch = useMutation({
    mutationFn: (body: ProductPatchBody) => patchProduct(id, body),
    onSuccess: () => refreshAfterCorrection(queryClient),
  });
  const move = useMutation({
    mutationFn: (target: Ingredient) => patchProduct(id, { ingredient_id: target.id }),
    onSuccess: async (updated) => {
      setMoving(false);
      setMovedNote(movedText(updated));
      await refreshAfterCorrection(queryClient);
    },
  });

  if (isLoading) {
    return (
      <Screen title="Prodotto" back={back}>
        <p className="text-ink-soft">Carico…</p>
      </Screen>
    );
  }

  if (isError || !product) {
    const gone = error instanceof ApiError && error.status === 404;
    return (
      <Screen title="Prodotto" back={back}>
        <Alert>
          {gone
            ? "Questo prodotto non c'è più. Gli elementi di dispensa che lo avevano sono rimasti, sfusi."
            : "Non sono riuscito a leggere questo prodotto."}
        </Alert>
        {!gone && (
          <button
            type="button"
            onClick={() => void refetch()}
            className={`${buttonClasses("secondary")} mt-3`}
          >
            Riprova
          </button>
        )}
      </Screen>
    );
  }

  return (
    <Screen title={product.name} subtitle={product.brand ?? undefined} back={back}>
      {movedNote && (
        <p role="status" className="pb-2 text-sm font-medium text-brand">
          {movedNote}
        </p>
      )}

      <Card className="flex flex-col gap-3">
        <InlineField
          label="Nome"
          value={product.name}
          onSave={(next) => patch.mutateAsync({ name: next })}
        />
        <InlineField
          label="Marca"
          value={product.brand ?? ""}
          placeholder="Nessuna marca"
          onSave={(next) => patch.mutateAsync({ brand: next === "" ? null : next })}
        />
      </Card>

      <SectionHeading>Ingrediente</SectionHeading>
      <Card className="flex flex-col gap-2">
        <Link
          to={ingredientPath(product.ingredient.id, origin)}
          className="inline-flex min-h-11 items-center font-medium text-brand"
        >
          {product.ingredient.display_name}
        </Link>
        <div className="flex flex-wrap items-center gap-2 text-sm text-ink-soft">
          <span>È sotto l'ingrediente sbagliato?</span>
          <button
            type="button"
            aria-expanded={moving}
            onClick={() => setMoving((open) => !open)}
            className={buttonClasses("secondary")}
          >
            Spostalo
          </button>
        </div>
        {/* senza filtro sul `kind`: in anagrafica si corregge anche il non alimentare */}
        {moving && (
          <IngredientPicker
            label="Sposta sotto"
            failureNote="Il prodotto resta dov'è: riprova tra poco."
            disabled={move.isPending}
            onPick={(target) => move.mutate(target)}
          />
        )}
        {move.isError && (
          <Alert>
            Non sono riuscito a spostarlo: è ancora sotto «{product.ingredient.display_name}». Riprova.
          </Alert>
        )}
        <p className="text-xs text-ink-faint">{pantryText(product.pantry_items.length)}</p>
      </Card>
    </Screen>
  );
}
```

In `frontend/src/App.tsx`: `import { ProductScreen } from "./features/registry/ProductScreen";`
e, dopo la rotta dell'ingrediente:

```tsx
            <Route path="/anagrafica/prodotto/:id" element={<ProductScreen />} />
```

- [ ] **Step 4: eseguilo e verifica che passi**

Run: `cd frontend && npx vitest run src/features/registry && npm run lint && npm run typecheck`
Expected: PASS.

- [ ] **Step 5: commit**

```bash
git add frontend/src/domain/types.ts frontend/src/features/registry frontend/src/App.tsx
git commit -m "$(cat <<'EOF'
anagrafica: la scheda del prodotto, e lo spostamento sotto l'ingrediente giusto

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 20: Il codice a barre e l'eliminazione

**File:**
- Modify: `frontend/src/features/registry/ProductScreen.tsx`
- Test: `frontend/src/features/registry/ProductScreen.test.tsx`

**Interfacce:**
- Consuma: `patchProduct`, `deleteProduct`, `registryRefusal`, `refreshAfterCorrection`
  (Task 15, 19); `InlineField` con `describeError` (Task 19).
- Produce: in `ProductCard` le mutazioni `barcodeAction` e `remove`, lo stato
  `confirmingDelete`, la sezione «Codice a barre» e «Elimina il prodotto».

- [ ] **Step 1: scrivi il test che fallisce**

In fondo al `describe` di `ProductScreen.test.tsx`:

```tsx
  it("un codice già di un altro prodotto offre di spostarlo qui", async () => {
    let tentativi = 0;
    const spy = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") {
        tentativi += 1;
        if (tentativi === 1) {
          return [{
            code: "barcode_taken",
            detail: "Il codice è di «Grana Padano 200 g».",
            existing: { id: "p-grana", name: "Grana Padano 200 g", brand: null, barcode: "8001234567897" },
          }, 409];
        }
        return [{ ...REGGIANO, barcode: "8001234567897" }, 200];
      }
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/prodotto/p-reggiano");

    const codice = await screen.findByLabelText("Codice");
    await userEvent.clear(codice);
    await userEvent.type(codice, "8001234567897");
    await userEvent.click(screen.getByRole("button", { name: "Salva codice" }));

    expect(await screen.findByText("Il codice è di «Grana Padano 200 g». Spostalo qui?")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Sposta il codice qui" }));

    await waitFor(() =>
      expect(bodiesOf(spy, "PATCH")).toEqual([
        { barcode: "8001234567897" },
        { barcode: "8001234567897", take_barcode: true },
      ])
    );
  });

  it("un codice che non torna avvisa, e «Usalo lo stesso» lo manda", async () => {
    let tentativi = 0;
    const spy = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") {
        tentativi += 1;
        if (tentativi === 1) {
          return [{
            code: "bad_checksum",
            detail:
              "Il codice non torna con la sua cifra di controllo: controlla le cifre. Se è un codice del negozio, usalo lo stesso.",
          }, 409];
        }
        return [{ ...REGGIANO, barcode: "8001234567890", valid_checksum: false }, 200];
      }
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/prodotto/p-reggiano");

    const codice = await screen.findByLabelText("Codice");
    await userEvent.clear(codice);
    await userEvent.type(codice, "8001234567890");
    await userEvent.click(screen.getByRole("button", { name: "Salva codice" }));

    expect(await screen.findByText(/controlla le cifre/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Usalo lo stesso" }));

    await waitFor(() =>
      expect(bodiesOf(spy, "PATCH")).toEqual([
        { barcode: "8001234567890" },
        { barcode: "8001234567890", accept_bad_checksum: true },
      ])
    );
  });

  it("«Togli il codice» manda il codice vuoto", async () => {
    const spy = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") return [{ ...REGGIANO, barcode: null, valid_checksum: null }, 200];
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/prodotto/p-reggiano");

    await userEvent.click(await screen.findByRole("button", { name: "Togli il codice" }));

    await waitFor(() => expect(bodiesOf(spy, "PATCH")).toEqual([{ barcode: null }]));
  });

  it("eliminare chiede conferma, dice cosa resta, e torna da dove si è venuti", async () => {
    const spy = stubRoutedFetch((path, init) => {
      if (init?.method === "DELETE") return [{ loose_pantry_items: 1 }, 200];
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/prodotto/p-reggiano?da=dispensa");

    await userEvent.click(await screen.findByRole("button", { name: "Elimina il prodotto" }));
    expect(
      screen.getByText("Gli elementi in dispensa restano, come «Burro» sfuso.")
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Elimina" }));

    expect(await screen.findByText("dove: /dispensa")).toBeInTheDocument();
    expect(
      spy.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === "DELETE")
    ).toHaveLength(1);
  });
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `cd frontend && npx vitest run src/features/registry/ProductScreen.test.tsx`
Expected: FAIL — `Unable to find a label with the text of: Codice` e
`… name "Elimina il prodotto"`.

- [ ] **Step 3: implementazione minima**

In `ProductScreen.tsx`:
- l'import da `react-router-dom` diventa
  `import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";`;
- l'import da `./api` diventa:
  ```tsx
  import {
    deleteProduct,
    fetchProductDetail,
    patchProduct,
    refreshAfterCorrection,
    registryRefusal,
    type ProductPatchBody,
  } from "./api";
  ```
- in `ProductCard`, subito dopo la mutazione `move`:
  ```tsx
  const navigate = useNavigate();
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  // le due uscite dei rifiuti del codice, e «Togli il codice»: una mutazione sua, così
  // un suo guasto si dice senza confondersi con quello del campo
  const barcodeAction = useMutation({
    mutationFn: (body: ProductPatchBody) => patchProduct(id, body),
    onSuccess: () => refreshAfterCorrection(queryClient),
  });
  const remove = useMutation({
    mutationFn: () => deleteProduct(id),
    onSuccess: () => {
      // si va via: segnare vecchio senza rileggere, perché questa scheda non c'è più
      void refreshAfterCorrection(queryClient, false);
      navigate(back.to);
    },
  });

  /** Il rifiuto del codice con la sua uscita (spec §7): un codice già usato si sposta
   * qui, un codice che non torna si usa lo stesso. */
  function barcodeRefusal(failure: unknown, draft: string) {
    const refusal = registryRefusal(failure);
    if (refusal?.code === "barcode_taken") {
      return (
        <div role="alert" className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-danger">Il codice è di «{refusal.existing.name}». Spostalo qui?</span>
          <button
            type="button"
            disabled={barcodeAction.isPending}
            onClick={() => barcodeAction.mutate({ barcode: draft, take_barcode: true })}
            className={buttonClasses("warn")}
          >
            Sposta il codice qui
          </button>
        </div>
      );
    }
    if (refusal?.code === "bad_checksum") {
      return (
        // ambra e non rosso: non è un rifiuto, è un avviso (S20)
        <div role="alert" className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-low">{refusal.detail}</span>
          <button
            type="button"
            disabled={barcodeAction.isPending}
            onClick={() => barcodeAction.mutate({ barcode: draft, accept_bad_checksum: true })}
            className={buttonClasses("secondary")}
          >
            Usalo lo stesso
          </button>
        </div>
      );
    }
    return (
      <Alert>
        {refusal
          ? refusal.detail
          : "Non sono riuscito a salvare il codice. Quel che hai scritto è ancora qui: riprova."}
      </Alert>
    );
  }
  ```
- nel `return` finale, subito dopo la prima `<Card>` (quella con Nome e Marca):
  ```tsx
      <SectionHeading>Codice a barre</SectionHeading>
      <Card className="flex flex-col gap-2">
        <InlineField
          label="Codice"
          value={product.barcode ?? ""}
          placeholder="Nessun codice"
          inputMode="numeric"
          onSave={(next) => patch.mutateAsync({ barcode: next === "" ? null : next })}
          describeError={barcodeRefusal}
        />
        {product.valid_checksum === false && (
          <p className="text-xs text-ink-faint">
            La cifra di controllo di questo codice non torna: può essere un codice del negozio.
          </p>
        )}
        {product.barcode && (
          <button
            type="button"
            disabled={barcodeAction.isPending}
            onClick={() => barcodeAction.mutate({ barcode: null })}
            className={`${buttonClasses("ghost")} self-start`}
          >
            Togli il codice
          </button>
        )}
        {barcodeAction.isError && (
          <Alert>Non sono riuscito a cambiare il codice. È ancora quello di prima: riprova.</Alert>
        )}
      </Card>
  ```
- in fondo al `return`, dopo la `<Card>` dell'ingrediente e prima di `</Screen>`:
  ```tsx
      <div className="pt-6">
        {!confirmingDelete ? (
          <button
            type="button"
            onClick={() => setConfirmingDelete(true)}
            className={buttonClasses("danger")}
          >
            Elimina il prodotto
          </button>
        ) : (
          <div
            role="alertdialog"
            aria-label="Conferma l'eliminazione"
            className="flex flex-col gap-2 rounded-card bg-card p-3"
          >
            <p className="text-sm">
              Gli elementi in dispensa restano, come «{product.ingredient.display_name}» sfuso.
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                disabled={remove.isPending}
                onClick={() => remove.mutate()}
                className={buttonClasses("danger")}
              >
                Elimina
              </button>
              <button
                type="button"
                onClick={() => setConfirmingDelete(false)}
                className={buttonClasses("ghost")}
              >
                Lascia
              </button>
            </div>
            {remove.isError && <Alert>Non sono riuscito a eliminarlo. È ancora qui: riprova.</Alert>}
          </div>
        )}
      </div>
  ```

- [ ] **Step 4: eseguilo e verifica che passi**

Run: `cd frontend && npx vitest run src/features/registry && npm run lint && npm run typecheck`
Expected: PASS.

- [ ] **Step 5: commit**

```bash
git add frontend/src/features/registry/ProductScreen.tsx frontend/src/features/registry/ProductScreen.test.tsx
git commit -m "$(cat <<'EOF'
anagrafica: il codice si toglie, si prende, si usa lo stesso; il prodotto si elimina

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 21: Dalla dispensa alla scheda

**File:**
- Modify: `frontend/src/features/pantry/PantryRow.tsx` (import; il blocco del nome,
  righe 160–171)
- Test: `frontend/src/features/pantry/PantryScreen.test.tsx`

**Interfacce:**
- Consuma: `ingredientPath`, `productPath` (Task 15); le schede dei Task 15 e 19.
- Produce: sulla riga della dispensa, il nome (con la marca) è un link di almeno 44 px a
  `/anagrafica/prodotto/{product_id}?da=dispensa`, o a
  `/anagrafica/ingrediente/{ingredient_id}?da=dispensa` per uno sfuso.

- [ ] **Step 1: scrivi il test che fallisce**

In fondo al `describe("PantryScreen", …)` di `PantryScreen.test.tsx`:

```tsx
  it("il nome porta alla scheda: del prodotto se c'è, dell'ingrediente se è sfuso", async () => {
    // S9 §6.5: nessuna terza schermata. La scheda dell'elemento è quella del prodotto,
    // e `?da=dispensa` dice al tasto indietro dove tornare
    stubRoutedFetch(() => [ITEMS, 200]);
    renderScreen();

    expect(await screen.findByRole("link", { name: /Total 0%/ })).toHaveAttribute(
      "href", "/anagrafica/prodotto/pr1?da=dispensa"
    );
    expect(screen.getByRole("link", { name: "mela" })).toHaveAttribute(
      "href", "/anagrafica/ingrediente/i2?da=dispensa"
    );
  });

  it("il tocco è sul nome e non sulla riga: il cursore non sta dentro il link", async () => {
    // il cursore resta un bersaglio solo suo, e S13 resta chiusa
    stubRoutedFetch(() => [ITEMS, 200]);
    renderScreen();

    const nome = await screen.findByRole("link", { name: "mela" });
    const cursore = screen.getByRole("slider", { name: "Quanto ne resta di mela" });
    expect(nome.contains(cursore)).toBe(false);
    expect(nome.querySelector("button")).toBeNull();
  });
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `cd frontend && npx vitest run src/features/pantry/PantryScreen.test.tsx`
Expected: FAIL — `Unable to find an accessible element with the role "link" and name `/Total 0%/``.

- [ ] **Step 3: implementazione minima**

In `PantryRow.tsx`, agli import:

```tsx
import { Link } from "react-router-dom";
import { ingredientPath, productPath } from "../registry/origin";
```

Sotto `itemLabel`:

```tsx
/** Dove porta il nome: alla scheda del prodotto se la voce ne ha uno, a quella
 * dell'ingrediente se è sfusa (spec S9 §6.5). Nessuna terza schermata: la scheda
 * dell'elemento è la scheda del prodotto, e l'ingrediente sta lì come link. */
function registryPath(item: PantryItem): string {
  return item.product_id
    ? productPath(item.product_id, "dispensa")
    : ingredientPath(item.ingredient_id, "dispensa");
}
```

Il blocco `<div className="min-w-0"> … </div>` del nome diventa:

```tsx
        <div className="min-w-0">
          {/* Il nome porta alla scheda: è lì che si corregge una voce registrata male
              (S9). Il tocco è sul nome e non sulla riga, così il cursore sotto resta un
              bersaglio solo suo e S13 resta chiusa.

              Il bersaglio è alto 44px: `min-h-11`, cioè 10px di padding per parte
              attorno a una riga di 24px. Il margine negativo uguale lo ritoglie dal
              flusso, e la riga resta alta com'era. I 10px che sporgono sotto sono
              esattamente il `gap-2.5` che separa questa riga dal cursore: il bordo
              basso del link tocca quello alto del cursore senza coprirlo — la stessa
              misura del «+ scadenza» qui sotto. `block` e non `flex`: in un flex lo
              spazio fra nome e marca sparirebbe, e con lui la separazione a video. */}
          <Link
            to={registryPath(item)}
            className="-my-2.5 block min-h-11 py-2.5 underline decoration-line underline-offset-4"
          >
            {/* la marca che hai comprato è più utile del nome generico */}
            <span className="font-medium">{itemLabel(item)}</span>
            {/* lo spazio è scritto a mano perché `ml-2` è un margine, non del testo:
                senza, il nome accessibile della riga si legge «Total 0%Fage» */}
            {item.product_brand && (
              <>
                {" "}
                <span className="text-sm text-ink-faint">{item.product_brand}</span>
              </>
            )}
          </Link>
        </div>
```

- [ ] **Step 4: eseguilo e verifica che passi**

Run: `cd frontend && npx vitest run src/features/pantry && npm run lint && npm run typecheck`
Expected: PASS, compresi i test di prima («nome e marca restano due parole», «per gli
sfusi mostra il nome dell'ingrediente»).

- [ ] **Step 5: commit**

```bash
git add frontend/src/features/pantry/PantryRow.tsx frontend/src/features/pantry/PantryScreen.test.tsx
git commit -m "$(cat <<'EOF'
dispensa: il nome della riga porta alla scheda del prodotto o dell'ingrediente (S9)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 22: Il browser vero — il parmigiano, e i 375 px

**File:**
- Create: `frontend/e2e/anagrafica.spec.ts`

**Interfacce:**
- Consuma: tutto il resto; le rotte `GET /api/v1/ingredients/search`,
  `POST /api/v1/products`, `POST /api/v1/pantry`, `GET /api/v1/pantry`,
  `DELETE /api/v1/products/{id}` attraverso `page.request`, che condivide i cookie della
  pagina.
- Produce: il caso del parmigiano per intero (spec §9.7) e il controllo di
  `scrollWidth` a 375 px sulle tre pagine nuove e sul pannello dell'hamburger.

- [ ] **Step 1: scrivi il test**

Crea `frontend/e2e/anagrafica.spec.ts`:

```ts
import { expect, test, type Page } from "@playwright/test";

/**
 * Il caso che ha fatto nascere S9, per intero e nel browser vero: un parmigiano
 * registrato sotto «burro» si sposta dalla dispensa in due tocchi e una scelta.
 *
 * Il prodotto e l'elemento di dispensa si creano con `page.request`, che condivide i
 * cookie della pagina: il seme non ha prodotti, e costruirli dalla sistemazione della
 * spesa allungherebbe la prova senza provare niente di S9. Il nome porta l'ora, perché
 * il catalogo vive quanto lo stack; in fondo la voce si toglie e il prodotto si
 * elimina, così il file non lascia niente dietro di sé. Nessun altro file di `e2e/`
 * nomina il burro o il parmigiano.
 *
 * `scrollWidth` lo calcola il browser dal CSS che Tailwind ha costruito: jsdom non lo
 * vede, quindi il controllo dei 375 px sta qui (come in `style.spec.ts`).
 */
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

async function ingrediente(page: Page, nome: string): Promise<{ id: string; name: string }> {
  const risposta = await page.request.get(`/api/v1/ingredients/search?q=${encodeURIComponent(nome)}`);
  expect(risposta.ok()).toBe(true);
  const trovati = (await risposta.json()) as { id: string; name: string }[];
  const voce = trovati.find((trovato) => trovato.name === nome);
  expect(voce, `«${nome}» non è nel seme`).toBeDefined();
  return voce!;
}

// stringhe e non funzioni: questo file lo compila tsconfig.node.json, senza la libreria DOM
async function nonScorreDiLato(page: Page, schermata: string) {
  await page.waitForLoadState("networkidle");
  const scrollWidth = await page.evaluate<number>("document.documentElement.scrollWidth");
  const clientWidth = await page.evaluate<number>("document.documentElement.clientWidth");
  expect(scrollWidth, `${schermata} scorre di lato`).toBeLessThanOrEqual(clientWidth);
}

test("il parmigiano sotto «burro» si sposta dalla dispensa, e a 375px niente scorre di lato", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();

  // lo stato di partenza: un prodotto sotto l'ingrediente sbagliato, in dispensa
  const burro = await ingrediente(page, "burro");
  const nome = `Parmigiano Reggiano e2e ${Date.now()}`;
  const creato = await page.request.post("/api/v1/products", {
    data: { ingredient_id: burro.id, name: nome },
  });
  expect(creato.ok()).toBe(true);
  const { id: prodottoId } = (await creato.json()) as { id: string };
  const inDispensa = await page.request.post("/api/v1/pantry", {
    data: { ingredient_id: burro.id, product_id: prodottoId },
  });
  expect(inDispensa.ok()).toBe(true);
  const { id: voceId } = (await inDispensa.json()) as { id: string };

  // tocco 1: il nome nella riga della dispensa, un bersaglio da pollice
  await page.getByRole("link", { name: "Dispensa", exact: true }).click();
  const link = page.getByRole("link", { name: nome });
  await expect(link).toBeVisible();
  const box = await link.boundingBox();
  expect(box!.height).toBeGreaterThanOrEqual(44);
  await link.click();
  await expect(page).toHaveURL(new RegExp(`/anagrafica/prodotto/${prodottoId}\\?da=dispensa$`));
  await expect(page.getByRole("link", { name: "Burro", exact: true })).toBeVisible();

  // tocco 2 e la scelta
  await page.getByRole("button", { name: "Spostalo" }).click();
  await page.getByLabel("Sposta sotto").fill("parmig");
  await page.getByRole("option", { name: /^Parmigiano\b/ }).click();
  await expect(
    page.getByText("Spostato sotto «Parmigiano», con 1 elemento di dispensa.")
  ).toBeVisible();
  await expect(page.getByRole("link", { name: "Parmigiano", exact: true })).toBeVisible();

  // la riga della dispensa mostra il nome del prodotto, non l'ingrediente: che ora stia
  // sotto «parmigiano» lo dice la risposta che la dispensa legge
  await page.getByRole("main").getByRole("link", { name: "Dispensa" }).click();
  await expect(page.getByRole("link", { name: nome })).toBeVisible();
  const dispensa = (await (await page.request.get("/api/v1/pantry")).json()) as {
    id: string;
    ingredient_name: string;
  }[];
  expect(dispensa.find((voce) => voce.id === voceId)?.ingredient_name).toBe("parmigiano");

  // a 375px: le tre pagine nuove e il pannello dell'hamburger
  await page.setViewportSize({ width: 375, height: 812 });
  const parmigiano = await ingrediente(page, "parmigiano");

  await page.goto(`/anagrafica/prodotto/${prodottoId}?da=dispensa`);
  await expect(page.getByRole("heading", { name: nome })).toBeVisible();
  await page.screenshot({ path: test.info().outputPath("prodotto-375.png"), fullPage: true });
  await nonScorreDiLato(page, "la scheda del prodotto");

  await page.goto(`/anagrafica/ingrediente/${parmigiano.id}`);
  await expect(page.getByRole("heading", { name: "Parmigiano" })).toBeVisible();
  // il prodotto dal nome lungo sta nell'elenco della scheda: è il caso che allarga
  await expect(page.getByRole("link", { name: new RegExp(nome) })).toBeVisible();
  await page.screenshot({ path: test.info().outputPath("ingrediente-375.png"), fullPage: true });
  await nonScorreDiLato(page, "la scheda dell'ingrediente");

  await page.goto("/anagrafica");
  await page.getByLabel("Cerca in anagrafica").fill("parmigiano");
  await expect(page.getByRole("heading", { name: "Prodotti" })).toBeVisible();
  await expect(page.getByRole("link", { name: new RegExp(nome) })).toBeVisible();
  await page.screenshot({ path: test.info().outputPath("anagrafica-375.png"), fullPage: true });
  await nonScorreDiLato(page, "l'anagrafica");

  await page.getByRole("button", { name: "Apri il menu" }).click();
  await expect(page.getByRole("dialog", { name: "Menu" })).toBeVisible();
  await page.screenshot({ path: test.info().outputPath("menu-375.png") });
  await nonScorreDiLato(page, "il pannello dell'hamburger");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Menu" })).toHaveCount(0);

  // la pulizia: la voce esce dalla dispensa, il prodotto dal catalogo
  await page.goto("/dispensa");
  await page.getByRole("button", { name: `Togli ${nome} dalla dispensa` }).click();
  await expect(page.getByText("Tolta dalla dispensa")).toBeVisible();
  expect((await page.request.delete(`/api/v1/products/${prodottoId}`)).ok()).toBe(true);
});
```

- [ ] **Step 2: eseguilo sullo stack e2e**

```bash
E2E="docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml"
$E2E up -d --build --wait
$E2E exec -T backend python -m app.cli.seed --con-ricette
(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
$E2E down -v
```
Expected: verde, questo file e tutti quelli che c'erano. Se `anagrafica.spec.ts` viene
prima di `cooking.spec.ts` in ordine alfabetico e `cooking` si lamenta di uno stack non
pulito, è questo file ad aver lasciato qualcosa: la pulizia in fondo va corretta, non la
guardia di `cooking`.

- [ ] **Step 3: guardalo con gli occhi**

Apri i quattro screenshot in `frontend/test-results/` (git li ignora) e rispondi a
tre domande, che nessun test dà:
1. la fila «Rinomina · Cambia reparto · Unisci a un altro…» va a capo pulita a 375px,
   senza un pulsante tagliato?
2. nella scheda del prodotto, «Salva» accanto a ogni campo lascia al campo abbastanza
   larghezza per un codice a 13 cifre leggibile?
3. il velo dell'hamburger si distingue dal pannello, e il pannello non copre l'intera
   larghezza (resta una striscia di velo da toccare per chiudere)?

Se una risposta è no, si corregge la classe nel componente e si rilancia lo Step 2.
Riferisci cosa hai visto e cosa hai cambiato.

- [ ] **Step 4: commit**

```bash
git add frontend/e2e/anagrafica.spec.ts
git commit -m "$(cat <<'EOF'
test: il parmigiano sotto «burro» nel browser vero, e l'anagrafica a 375px

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

(più i componenti toccati allo Step 3, se ce ne sono).

---

### Task 23: Consegna 2 — verifica, documenti, distribuzione — **la distribuzione vuole il via di Mattia**

**File:**
- Modify: `docs/prossimi-passi.md` (S9, l'intestazione del file)
- Modify: `CLAUDE.md` (la voce sull'import)

**Interfacce:**
- Consuma: tutto.
- Produce: S9 chiusa, in produzione, e i documenti che dicono il vero.

- [ ] **Step 1: le suite intere**

```bash
(cd backend && PATH="$PWD/.venv/bin:$PATH" python -m pytest -q)
(cd frontend && npx vitest run && npm run lint && npm run typecheck && npm run build)
grep -rnE "emerald|neutral-" frontend/src && echo "COLORE GREZZO" || echo "token soltanto"
git diff --stat master -- backend/tests/test_fix_registry_cli.py
```
Expected: tutto verde; «token soltanto»; il `git diff` vuoto.

- [ ] **Step 2: l'e2e su uno stack pulito**

```bash
E2E="docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml"
$E2E up -d --build --wait
$E2E exec -T backend python -m app.cli.seed --con-ricette
(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
$E2E down -v
```
Expected: verde.

- [ ] **Step 3: il giro a mano a 375px**

Sullo stack e2e ricreato e seminato come allo Step 2 (e distrutto dopo), nel browser a
375px con il tocco emulato: apri l'hamburger, «Anagrafica», cerca «pomodoro», apri la
scheda, prova «Rinomina» con «Pomodoro» (il rifiuto e «Uniscili»), chiudi; «Unisci a
un altro…» con un ingrediente non alimentare (il rifiuto e «Cambia reparto»). Nessun
vicolo cieco, nessuno scorrimento di lato. Riferisci cosa hai visto.

- [ ] **Step 4: i documenti**

`docs/prossimi-passi.md`:
- il titolo di S9 diventa
  `## S9. Correggere quel che è stato registrato male **[FATTO 2026-09-27 — spec: docs/superpowers/specs/2026-09-27-anagrafica-design.md]**`;
- il paragrafo che comincia con «**TBD**: dove vive la correzione.» diventa:
  ```
  **Deciso e costruito** (spec del 2026-09-27): dalla riga della dispensa — il nome è un
  link alla scheda del prodotto, o dell'ingrediente se lo sfuso — e da «Anagrafica»
  nell'hamburger per quel che in dispensa non c'è. Un servizio solo,
  `app/services/registry.py`, per l'app e per `fix_registry`.
  ```
- il paragrafo «**Il caso concreto resta sbagliato in produzione**…» si toglie: il
  parmigiano è stato sistemato a mano, e ora si sistemerebbe dall'app;
- in cima al file, una riga nuova nell'«Aggiornato il…»: S9 fatta, con l'hamburger (T1
  chiusa) e l'annullamento della coda che non chiede più conferma;
- in Parte X, una voce nuova:
  ```
  - **«Deciso nella coda» porta a una coda che può non mostrare quella decisione.** La
    scheda dell'ingrediente (S9) rimanda alla coda per gli alias che sono la metà di una
    decisione, ma «Decisioni recenti» mostra solo le 50 più recenti per autore: una
    decisione vecchia non si trova. Serve un filtro per termine nella coda
    (`/ricette/importa?termine=<id>`), o l'annulla direttamente dalla scheda. Dal piano
    di S9, verificato sul codice.
  ```

`CLAUDE.md`, nella voce «Import brings in recipes, not random new ingredients.»: la
frase «and a wrong decision is corrected from the ingredient registry.» diventa:

```
and a wrong decision is corrected from the ingredient registry — since S9 a place in
the app, «Anagrafica» from the hamburger (`frontend/src/features/registry/`), over the
single service `backend/app/services/registry.py` that `app.cli.fix_registry` also
calls. The exception is an alias that is half of a queue decision (`source = "import"`
with its term still in `import_terms`): that one is corrected from the queue, where
R11 shows manual decisions too, so the queue and the registry never disagree.
```

Commit:

```bash
git add docs/prossimi-passi.md CLAUDE.md
git commit -m "$(cat <<'EOF'
docs: S9 fatta, l'anagrafica ha un posto nell'app

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 5: la distribuzione — solo col via di Mattia in chat**

Si chiede dicendo cosa va in produzione (l'hamburger, l'anagrafica, il nome della
dispensa che porta alla scheda). Poi:

```bash
git checkout master && git merge --ff-only anagrafica && git push origin master
ssh hetznerserver 'cd ~/sites/spena && git pull --ff-only && docker compose -f docker-compose.prod.yml up -d --build --wait'
(cd frontend && npm run build) && ls frontend/dist/assets | grep -E '^index-.*\.js$'
curl -s https://spena.mattiagirellini.com/ | grep -o 'assets/index-[^"]*'
curl -s https://spena.mattiagirellini.com/api/v1/health
```
Expected: il pacchetto servito è quello della build locale; `/health` risponde. La PWA
installata sul telefono prende il pacchetto nuovo alla riapertura successiva: la prova
sul telefono vero (il ☰ col pollice, il nome della riga senza toccare il cursore) la fa
Mattia, e si annota in S9 quando l'ha fatta.

---

## Note per chi rivede

Discrepanze fra la spec e il codice, e scelte fatte dove la spec non decideva.

1. **`UndoIn` non esiste: è `UndoRequest`** (`backend/app/schemas/recipe_import.py`).
   Il piano la toglie del tutto e la rotta non prende più un corpo; un corpo con
   `force` mandato da una PWA con la cache vecchia si ignora, e un test lo prova
   (Task 3).
2. **`DELETE /products/{id}` risponde 200, non 204.** La spec §4 chiede «204, con il
   numero di elementi di dispensa rimasti sfusi», ma un 204 non ha corpo. Il piano
   risponde `200 {"loose_pantry_items": n}`. La DELETE dell'alias resta 204.
3. **`remember_alias` scriveva sempre `source="import"`**, anche per il vecchio nome di
   un `rename` e per i nomi del perdente in un `merge` della CLI. Il piano le dà un
   argomento `source` (default `"import"`, così i chiamanti di sempre non cambiano) e il
   servizio scrive `"manual"`. Di conseguenza la guardia `import_alias` è definita come
   «`source == "import"` **e** un termine della coda che normalizzato dà quell'alias»:
   gli alias `import` scritti dalla CLI prima di S9 non hanno termine, e rifiutarli
   sarebbe un vicolo cieco (nella coda non c'è niente da correggere).
4. **La CLI prende la guardia `import_alias` anche per `move_alias`.** Prima spostava
   qualunque alias; ora un alias che è la metà di una decisione si rifiuta con un
   messaggio che rimanda alla coda (per un piano, `remap`). I test esistenti non se ne
   accorgono («piadina ripiena» non ha termine). È un cambiamento di comportamento
   voluto: la stessa guardia in due porte.
5. **Il `merge` della CLI ora rimaterializza dentro il passo**, perché lo fa il servizio
   (i conteggi della fusione — ricette rifatte, cotture ri-legate — esistono solo così).
   `apply_plan` somma (`outcome.rebuilt += …`) invece di assegnare, e la riga finale del
   log conta tutto. I messaggi dei rifiuti della CLI ora vengono dal servizio, scritti
   perché le espressioni regolari dei test invariati continuino a trovarli («non
   alimentare», «non può diventare non alimentare», «già in anagrafica»).
6. **`recipes_rebuilt` conta quel che `materialize_ready` crea in quella chiamata**, che
   rifà *ogni* pagina pronta della fonte, non solo quelle della fusione. In pratica non
   ce ne sono in attesa (ogni decisione materializza subito), ma se ci fossero finirebbero
   nel conto. Stessa cosa per l'anteprima, che resta comunque uguale alla fusione.
7. **Il codice che non torna: 409 `bad_checksum` finché non si dice
   `accept_bad_checksum: true`.** «Mai un rifiuto» della spec §4 è letto come «mai un
   rifiuto che non si supera»: il server non può mostrare un avviso prima di salvare
   senza un giro in più, quindi il primo salvataggio torna l'avviso e «Usalo lo stesso»
   rimanda con la conferma. Chi *prende* un codice già in catalogo non passa dal
   controllo, come in «Sistema la spesa». La scheda porta `valid_checksum` per dirlo
   anche su un codice già salvato.
8. **«La dispensa lo mostra sotto «parmigiano»» (spec §9.7) non si vede sulla riga**, che
   mostra il nome del prodotto e non l'ingrediente. L'e2e lo prova con il link
   all'ingrediente sulla scheda del prodotto e con `ingredient_name` di `GET /pantry`.
9. **«Deciso nella coda» porta a `/ricette/importa`, ma la coda mostra solo le 50
   decisioni più recenti per autore.** Un alias di una decisione vecchia porta a una
   coda dove quella decisione non si vede. Fuori da questa spec (§8, R11): il Task 23 lo
   scrive in Parte X di `docs/prossimi-passi.md` come voce aperta.
10. **La prova sulla copia della produzione sta prima della distribuzione della Consegna
    1 (Task 11), non in fondo al piano**: la spec §9 la vuole «prima di distribuire la
    fusione», e la fusione va in produzione con la Consegna 1.
11. **`aliases` in `MergeCounts` è la differenza** fra gli alias del vincitore dopo e
    prima: comprende quelli riscritti dalla ridecisione dei termini e il nome del
    perdente.
12. **Codici di rifiuto oltre a quelli della spec:** `same_ingredient`, `empty_name`,
    `unknown_category`, `decision_refused`, `still_used`, `bad_checksum`.
13. **Il rifiuto `non_food_in_recipes` porta le prime 20 ricette per titolo e il conto
    totale** (`RECIPES_SHOWN`): «sale» è in migliaia di ricette.
14. **`PATCH /ingredients/{id}` con `name` scrive nome canonico e nome a video insieme**;
    il nome a video da solo resta della CLI. La spec §4 elenca solo `name?` e `category?`.
15. **I test delle rotte salvano il mondo con `commit`**: le rotte che rifiutano fanno
    `rollback`, e con `join_transaction_mode="create_savepoint"` porterebbero via i dati
    scritti solo con `flush`. Per la stessa ragione passano id e non oggetti. Il servizio
    ha la stessa cautela dopo il SAVEPOINT dell'anteprima: gli oggetti toccati sono
    scaduti, e la rotta risponde coi conteggi.
16. **`move_product` sposta anche gli elementi archiviati** (spec §3: «tutti»), e torna
    il numero degli attivi, che è quello che la scheda dice. `delete_product` fa un
    `UPDATE product_id = NULL` esplicito prima del `DELETE`, anche se la chiave esterna
    lo farebbe: tiene d'accordo gli oggetti in memoria.
17. **`/anagrafica` non ha tasto indietro**: ci si arriva dall'hamburger, da qualunque
    schermata, e non ha una sezione madre. Le due schede sì, dichiarato da `?da=`.
18. **Le schede sono avvolte in un componente con `key={id}`**: dopo una fusione React
    Router riusa lo stesso componente per la scheda del vincitore, e senza la chiave il
    pannello della fusione resterebbe aperto sul vincitore.
