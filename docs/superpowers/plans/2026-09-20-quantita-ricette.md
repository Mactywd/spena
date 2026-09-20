# Le quantità strutturate nelle ricette — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dare alle righe di ricetta una quantità strutturata accanto al testo libero,
e usarla per riporzionare una ricetta per numero di porzioni — senza toccare una riga
della dispensa.

**Architecture:** Un parser puro in `app/domain/quantities.py` ricava numero e unità da
`quantity_text` e viene chiamato dall'unico imbuto che scrive `recipe_ingredients`
(`create_recipe`). Le unità sconosciute si depositano in una tabella `units` che cresce
da sé; un comando separato chiede all'AI singolare e plurale, così nessuna chiamata di
rete entra in una transazione di scrittura. Il riporziona è un parametro di query sulla
rotta del dettaglio: il conto e la pluralizzazione stanno nel backend, il client mostra
e basta.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, Alembic, Postgres 16;
React 19 + TypeScript + Vite; Playwright per il browser vero.

**Spec:** `docs/superpowers/specs/2026-09-20-quantita-ricette-design.md`

## Global Constraints

- **La dispensa non cambia di una riga.** Niente quantità, niente unità, niente
  scadenze in `pantry_items`. Se un task sembra chiederlo, il task è sbagliato.
- **`quantity_text` non si riscrive mai** e non si perde mai: resta la verità mostrata
  a scala 1×, e la fonte da cui si riparsa per sempre.
- **`app/domain/` è puro**: nessun import di modelli, di sessioni, di `httpx`. Le
  funzioni di questo modulo non toccano il database né la rete.
- **La regola primario/secondario non si tocca.** `default_role` continua a leggere
  `q.b.` dalla stringa: «dose a piacere» e «non parsata» sono due domande diverse, e
  `abbondante` le separa.
- **Nessuna chiamata di rete dentro una scrittura.** Un'unità sconosciuta si deposita e
  si decide dopo.
- **`LlmCallSite` non ha default**: una sezione nuova si dichiara, o la torta delle
  spese guadagna un secchio muto.
- **La suite gira sull'host**, con Postgres su da Compose:
  `cd backend && .venv/bin/python -m pytest`. Per il frontend `npx vitest run`,
  `npm run typecheck`, `npm run build`. **`tsc --noEmit` non è il type check di questo
  progetto** (settima lezione di `CLAUDE.md`).
- **Deploy:** `docker compose -f docker-compose.prod.yml up -d --build --wait`. Il `-f`
  non è opzionale.

---

## Struttura dei file

**Creati**

| file | responsabilità |
|---|---|
| `backend/app/domain/quantities.py` | parsare, scalare e ridisegnare una dose. Puro. |
| `backend/app/db/models/unit.py` | la tabella `units` |
| `backend/alembic/versions/0008_quantita_ricette.py` | `units`, le due colonne, il vincolo |
| `backend/app/repositories/units.py` | `ensure_unit`, `undecided_units`, `apply_forms`, `reset_unit` |
| `backend/app/services/unit_forms.py` | la chiamata AI che decide singolare e plurale |
| `backend/app/cli/reparse_quantities.py` | riempie e riempie di nuovo le colonne |
| `backend/app/cli/decide_units.py` | fa decidere le unità in attesa |
| `frontend/src/features/cooking/ServingsStepper.tsx` | il selettore delle porzioni |

**Modificati**

| file | cosa |
|---|---|
| `backend/app/db/models/recipe.py` | due colonne su `RecipeIngredient`, il vincolo, la relazione `unit` |
| `backend/app/repositories/recipes.py` | `create_recipe` parsa e deposita |
| `backend/app/api/recipes.py` | `?servings=` sul dettaglio, `_to_out` che scala |
| `backend/app/schemas/recipe.py` | i campi nuovi in uscita |
| `backend/app/services/llm.py` | `LlmCallSite.UNIT_FORMS` |
| `frontend/src/domain/types.ts` | i campi nuovi |
| `frontend/src/features/recipes/api.ts` | `fetchRecipe(id, servings?)` |
| `frontend/src/features/cooking/RecipeDetailScreen.tsx` | il selettore, `quantity_display`, la riga della copertura |
| `frontend/e2e/style.spec.ts` | i bersagli da pollice del selettore |
| `CLAUDE.md`, spec madre §2, `docs/prossimi-passi.md` | gli emendamenti |

---

## Task 1: Il parser

**Files:**
- Create: `backend/app/domain/quantities.py`
- Test: `backend/tests/domain/test_quantities.py`

**Interfaces:**
- Consumes: niente.
- Produces: `parse_quantity(text: str | None) -> tuple[Decimal | None, str | None]`.

- [ ] **Step 1: Write the failing test**

Le dosi del test sono quelle vere del seme (`data/recipes_seed.json`, 52 distinte):
sono l'unico caso di prova che è anche un dato di produzione.

```python
# backend/tests/domain/test_quantities.py
from decimal import Decimal

import pytest

from app.domain.quantities import parse_quantity


@pytest.mark.parametrize(
    "text,expected",
    [
        # non parsabili: nessun numero in testa
        ("q.b.", (None, None)),
        ("abbondante", (None, None)),
        ("facoltativo", (None, None)),
        ("alcune foglie", (None, None)),
        (None, (None, None)),
        ("", (None, None)),
        # numero nudo: la fonte non ha scritto un'unità, e non la inventiamo
        ("1", (Decimal("1"), None)),
        ("10", (Decimal("10"), None)),
        ("1/2", (Decimal("0.5"), None)),
        # dose piena
        ("300 g", (Decimal("300"), "g")),
        ("80 ml", (Decimal("80"), "ml")),
        ("1 kg", (Decimal("1"), "kg")),
        ("3 cucchiai", (Decimal("3"), "cucchiai")),
        ("1 spicchio", (Decimal("1"), "spicchio")),
        ("8 fette", (Decimal("8"), "fette")),
        ("1/2 bicchiere", (Decimal("0.5"), "bicchiere")),
        # la prosa dopo l'unità si ignora: sta in quantity_text, che resta intatto
        ("1 litro di brodo", (Decimal("1"), "litro")),
        ("500 ml per la besciamella", (Decimal("500"), "ml")),
        ("1 confezione di sfoglie per lasagne", (Decimal("1"), "confezione")),
        ("1 scatola piccola", (Decimal("1"), "scatola")),
        # «2 medie» sono due zucchine medie: l'aggettivo diventa unità, ed è giusto
        # così — «4 medie» a ×2 si legge bene, e distinguere un aggettivo da
        # un'unità sarebbe analisi grammaticale dentro un parser di numeri
        ("2 medie", (Decimal("2"), "medie")),
        # le somme di merge_quantities: stessa unità si sommano...
        ("500 g + 50 g", (Decimal("550"), "g")),
        ("1 + 2", (Decimal("3"), None)),
        # ...unità diverse no: la somma di due cose diverse non è un numero
        ("500 g + 2 cucchiai", (None, None)),
        ("300 g + q.b.", (None, None)),
        # maiuscole e spazi non contano
        ("  300  G  ", (Decimal("300"), "g")),
    ],
)
def test_parse_quantity(text, expected):
    assert parse_quantity(text) == expected


def test_una_frazione_impossibile_non_solleva():
    """Una dose che non si capisce non è un errore: è una dose che non si scala."""
    assert parse_quantity("1/0 bicchiere") == (None, None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/domain/test_quantities.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.domain.quantities'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/domain/quantities.py
"""Le dosi delle ricette: leggerle, scalarle, riscriverle. Modulo puro.

La dispensa non conosce quantità e non ne conoscerà mai: questo modulo esiste per
le ricette e basta (decisione fondante 1, ristretta il 2026-09-17). `quantity_text`
resta la verità da mostrare; qui si ricava quel che serve per riporzionare, e
quando non si ricava non si inventa.
"""

import re
from dataclasses import dataclass
from decimal import Decimal, DivisionByZero, InvalidOperation

# tre decimali bastano a un terzo, e `Numeric` invece di `Float` perché un giorno
# queste righe si sommeranno per la nutrizione
PRECISION = Decimal("0.001")

# numero in testa (intero, decimale con virgola o punto, frazione), e subito dopo
# la parola dell'unità se c'è. Tutto quel che segue è prosa e non ci riguarda:
# «1 litro di brodo» è un litro, e «di brodo» sta già in quantity_text.
_DOSE = re.compile(
    r"^\s*(?:(?P<num>\d+)\s*/\s*(?P<den>\d+)|(?P<dec>\d+(?:[.,]\d+)?))"
    r"\s*(?P<unit>[^\W\d_]+)?",
    re.UNICODE,
)


@dataclass(frozen=True)
class UnitForms:
    """Come si scrive un'unità. `singular`/`plural` sono `None` finché nessuno
    ha deciso: allora si mostra `key`, cioè la parola come è arrivata."""

    key: str
    singular: str | None = None
    plural: str | None = None


def parse_quantity(text: str | None) -> tuple[Decimal | None, str | None]:
    """Il numero e la parola dell'unità dentro una dose scritta a mano.

    Torna `(None, None)` per tutto ciò che non comincia con un numero — «q.b.»,
    «abbondante», «facoltativo» — e non solleva mai: una dose che non si capisce
    non è un errore, è una dose che non si scala.
    """
    if not text:
        return (None, None)

    # `merge_quantities` unisce con « + » due dosi della stessa fonte finite sullo
    # stesso ingrediente («500 g + 50 g»). Sommare è giusto solo a unità uguale.
    pieces = [_parse_one(piece) for piece in text.split("+")]
    if any(value is None for value, _ in pieces):
        return (None, None)
    units = {unit for _, unit in pieces}
    if len(units) != 1:
        return (None, None)
    total = sum((value for value, _ in pieces), start=Decimal(0))
    return (total.quantize(PRECISION).normalize(), units.pop())


def _parse_one(piece: str) -> tuple[Decimal | None, str | None]:
    found = _DOSE.match(piece)
    if not found:
        return (None, None)
    try:
        if found["den"] is not None:
            value = (Decimal(found["num"]) / Decimal(found["den"])).quantize(PRECISION)
        else:
            value = Decimal(found["dec"].replace(",", "."))
    except (InvalidOperation, DivisionByZero, ZeroDivisionError):
        return (None, None)
    unit = found["unit"].lower() if found["unit"] else None
    return (value, unit)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/domain/test_quantities.py -v`
Expected: PASS, 25 casi

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/quantities.py backend/tests/domain/test_quantities.py
git commit -m "feat: il parser delle dosi, provato sulle 52 dosi vere del seme"
```

---

## Task 2: Scalare e ridisegnare

**Files:**
- Modify: `backend/app/domain/quantities.py`
- Test: `backend/tests/domain/test_quantities.py`

**Interfaces:**
- Consumes: `UnitForms`, `PRECISION` dal Task 1.
- Produces: `scale_quantity(value: Decimal, factor: Decimal) -> Decimal`,
  `render_quantity(value: Decimal, unit: UnitForms | None) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# in coda a backend/tests/domain/test_quantities.py
from app.domain.quantities import UnitForms, render_quantity, scale_quantity

CUCCHIAIO = UnitForms(key="cucchiai", singular="cucchiaio", plural="cucchiai")
GRAMMO = UnitForms(key="g", singular="g", plural="g")
NON_DECISA = UnitForms(key="costa")


@pytest.mark.parametrize(
    "value,factor,expected",
    [
        (Decimal("300"), Decimal("2"), Decimal("600")),
        (Decimal("300"), Decimal("0.5"), Decimal("150")),
        (Decimal("3"), Decimal("2") / Decimal("3"), Decimal("2")),
        (Decimal("1"), Decimal("0.5"), Decimal("0.5")),
    ],
)
def test_scale_quantity(value, factor, expected):
    assert scale_quantity(value, factor) == expected


@pytest.mark.parametrize(
    "value,unit,expected",
    [
        # il plurale si sceglie sul valore: singolare solo a 1 esatto
        (Decimal("1"), CUCCHIAIO, "1 cucchiaio"),
        (Decimal("6"), CUCCHIAIO, "6 cucchiai"),
        (Decimal("0.5"), CUCCHIAIO, "0,5 cucchiai"),
        # virgola decimale e zeri di coda tolti
        (Decimal("1.500"), CUCCHIAIO, "1,5 cucchiai"),
        (Decimal("550"), GRAMMO, "550 g"),
        # unità non ancora decisa: si mostra la parola come è arrivata, mai un errore
        (Decimal("2"), NON_DECISA, "2 costa"),
        # numero nudo: «1» di una cipolla è una cipolla, non «1 pezzo»
        (Decimal("2"), None, "2"),
    ],
)
def test_render_quantity(value, unit, expected):
    assert render_quantity(value, unit) == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/domain/test_quantities.py -k "scale or render" -v`
Expected: FAIL con `ImportError: cannot import name 'render_quantity'`

- [ ] **Step 3: Write minimal implementation**

```python
# in coda a backend/app/domain/quantities.py
from decimal import ROUND_HALF_UP


def scale_quantity(value: Decimal, factor: Decimal) -> Decimal:
    return (value * factor).quantize(PRECISION, rounding=ROUND_HALF_UP).normalize()


def render_quantity(value: Decimal, unit: UnitForms | None) -> str:
    """La dose riscritta dopo una scala. Non si usa a 1×: là si mostra
    `quantity_text`, che dice la verità meglio di quanto sappiamo riscriverla."""
    number = format(value.normalize(), "f").replace(".", ",")
    if unit is None:
        return number
    word = (unit.singular if value == 1 else unit.plural) or unit.key
    return f"{number} {word}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/domain/test_quantities.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/quantities.py backend/tests/domain/test_quantities.py
git commit -m "feat: scalare una dose e riscriverla con il plurale giusto"
```

---

## Task 3: Il modello e la migrazione

**Files:**
- Create: `backend/app/db/models/unit.py`
- Create: `backend/alembic/versions/0008_quantita_ricette.py`
- Modify: `backend/app/db/models/recipe.py:74-101` (`RecipeIngredient`)
- Test: `backend/tests/db/test_quantity_columns.py`

**Interfaces:**
- Consumes: niente.
- Produces: `Unit` (campi `key`, `singular`, `plural`, `decided_by`, `decided_at`,
  `canonical_id`); `RecipeIngredient.quantity_value`, `.quantity_unit_id`, `.unit`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/db/test_quantity_columns.py
"""I tre stati validi di una dose, e il quarto che il database rifiuta."""

from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe import Recipe, RecipeIngredient
from app.db.models.unit import Unit
from app.repositories.ingredients import create_ingredient


@pytest_asyncio.fixture
async def cucina(db_session):
    pasta = await create_ingredient(
        db_session, name="pasta", display_name="Pasta",
        category=IngredientCategory.CEREALI,
    )
    cipolla = await create_ingredient(
        db_session, name="cipolla", display_name="Cipolla",
        category=IngredientCategory.VERDURA,
    )
    sale = await create_ingredient(
        db_session, name="sale", display_name="Sale", category=IngredientCategory.SPEZIE,
    )
    return {"pasta": pasta, "cipolla": cipolla, "sale": sale}


async def test_unita_senza_numero_e_vietata(db_session, cucina):
    """La quarta combinazione non ha senso: un'unità senza un numero davanti non è
    una dose. Il vincolo sta nel database e non solo nel codice perché il riparsare
    e una futura migrazione scrivono queste colonne senza passare da create_recipe."""
    unit = Unit(key="g")
    db_session.add(unit)
    await db_session.flush()

    recipe = Recipe(title="vietata", instructions="i", source="dataset")
    recipe.ingredients.append(
        RecipeIngredient(
            ingredient_id=cucina["pasta"].id,
            role="primary",
            quantity_text="g",
            quantity_value=None,
            quantity_unit_id=unit.id,
        )
    )
    db_session.add(recipe)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_i_tre_stati_validi_si_scrivono(db_session, cucina):
    unit = Unit(key="g", singular="g", plural="g")
    db_session.add(unit)
    await db_session.flush()

    recipe = Recipe(title="valida", instructions="i", source="dataset")
    righe = [
        (cucina["sale"], None, None, "q.b."),            # non parsata
        (cucina["cipolla"], Decimal("1"), None, "1"),     # numero nudo
        (cucina["pasta"], Decimal("300"), unit.id, "300 g"),  # dose piena
    ]
    for ingredient, value, unit_id, text in righe:
        recipe.ingredients.append(
            RecipeIngredient(
                ingredient_id=ingredient.id, role="secondary", quantity_text=text,
                quantity_value=value, quantity_unit_id=unit_id,
            )
        )
    db_session.add(recipe)
    await db_session.flush()  # non solleva
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/db/test_quantity_columns.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.db.models.unit'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/db/models/unit.py
"""Il vocabolario delle dosi, che cresce da sé.

Non è un enum nel codice perché la fonte è un ricettario vero: ogni catalogo nuovo
porta parole che non avevamo previsto, e una parola non prevista non deve poter
bloccare una ricetta. Una riga senza `singular` è una parola incontrata e non ancora
decisa: si mostra così com'è arrivata, e il riporziona la scala lo stesso.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.db.models.base import TimestampMixin, UUIDMixin

UNIT_MAX_LENGTH = 30


class Unit(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "units"

    # la parola come è arrivata dal testo: è quel che si è visto, non quel che si
    # vorrebbe aver visto
    key: Mapped[str] = mapped_column(String(UNIT_MAX_LENGTH), unique=True)
    singular: Mapped[str | None] = mapped_column(String(UNIT_MAX_LENGTH), nullable=True)
    plural: Mapped[str | None] = mapped_column(String(UNIT_MAX_LENGTH), nullable=True)
    # "ai" o "human", come in ImportTerm: le due decisioni AI del progetto hanno la
    # stessa forma
    decided_by: Mapped[str | None] = mapped_column(String(20), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # «cucchiai» punta a «cucchiaio» quando l'AI dice che è il suo singolare e quella
    # chiave esiste già. Serve a S4: senza, il peso della coppia ingrediente×unità
    # andrebbe riempito due volte per la stessa unità, e la seconda divergerebbe.
    canonical_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units.id", ondelete="RESTRICT"), nullable=True
    )
```

In `backend/app/db/models/recipe.py`, dentro `RecipeIngredient`: aggiungi a
`__table_args__` il vincolo, e le due colonne più la relazione dopo `quantity_text`.

```python
# __table_args__ guadagna:
        CheckConstraint(
            "quantity_unit_id IS NULL OR quantity_value IS NOT NULL",
            name="ck_recipe_ingredient_unit_needs_value",
        ),

# dopo quantity_text:
    # `Numeric` e non `Float`: 0.1 + 0.2 deve fare 0.3 anche quando queste righe si
    # sommeranno per la nutrizione. Annullabili entrambe: vedi i tre stati nella spec.
    quantity_value: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    quantity_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units.id", ondelete="RESTRICT"), nullable=True
    )
    unit: Mapped["Unit | None"] = relationship(lazy="joined")
```

Gli import in cima a `recipe.py`: `from decimal import Decimal`,
`Numeric` da `sqlalchemy`, e `from app.db.models.unit import Unit`.

```python
# backend/alembic/versions/0008_quantita_ricette.py
"""le quantità strutturate nelle ricette

Revision ID: 0008
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"


def upgrade() -> None:
    op.create_table(
        "units",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(length=30), nullable=False, unique=True),
        sa.Column("singular", sa.String(length=30), nullable=True),
        sa.Column("plural", sa.String(length=30), nullable=True),
        sa.Column("decided_by", sa.String(length=20), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "canonical_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("units.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    # Nessun riempimento qui: lo fa `python -m app.cli.reparse_quantities`, perché il
    # parser migliorerà e migliorarlo non deve voler dire scrivere un'altra
    # migrazione. Stessa ragione per cui esiste `app.cli.reindex`.
    op.add_column(
        "recipe_ingredients", sa.Column("quantity_value", sa.Numeric(8, 3), nullable=True)
    )
    op.add_column(
        "recipe_ingredients",
        sa.Column(
            "quantity_unit_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("units.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_recipe_ingredient_unit_needs_value",
        "recipe_ingredients",
        "quantity_unit_id IS NULL OR quantity_value IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_recipe_ingredient_unit_needs_value", "recipe_ingredients", type_="check"
    )
    op.drop_column("recipe_ingredients", "quantity_unit_id")
    op.drop_column("recipe_ingredients", "quantity_value")
    op.drop_table("units")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/db/test_quantity_columns.py -v && .venv/bin/python -m pytest -q`
Expected: PASS, e tutta la suite verde (le ricette esistenti hanno le colonne a NULL,
che è uno stato valido)

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/models/unit.py backend/app/db/models/recipe.py \
  backend/alembic/versions/0008_quantita_ricette.py backend/tests/db/test_quantity_columns.py
git commit -m "feat: la tabella units e le due colonne sulla riga di ricetta"
```

---

## Task 4: L'imbuto riempie le colonne

**Files:**
- Create: `backend/app/repositories/units.py`
- Modify: `backend/app/repositories/recipes.py:25-75` (`create_recipe`)
- Test: `backend/tests/api/test_recipes_quantities.py`

**Interfaces:**
- Consumes: `parse_quantity` (Task 1), `Unit` (Task 3).
- Produces: `ensure_unit(session, key: str) -> Unit`; `create_recipe` riempie
  `quantity_value` e `quantity_unit_id` da sé, con la stessa firma di prima.

- [ ] **Step 1: Write the failing test**

Il test passa dall'imbuto vero e non costruisce la riga a mano: una riga costruita
dal test proverebbe una copia che non gira (prima lezione di `CLAUDE.md`).

```python
# backend/tests/api/test_recipes_quantities.py
"""Le colonne si riempiono passando dall'imbuto vero.

Costruire la riga a mano proverebbe una copia che non gira: è la prima lezione di
CLAUDE.md, e qui conta doppio, perché tutto il valore di questo lavoro sta nel fatto
che nessuno scrittore possa scordarsi di parsare.
"""

from decimal import Decimal

import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import IngredientCategory
from app.db.models.unit import Unit
from app.repositories.ingredients import create_ingredient
from app.repositories.recipes import create_recipe


@pytest_asyncio.fixture
async def cucina(db_session):
    pasta = await create_ingredient(
        db_session, name="pasta", display_name="Pasta",
        category=IngredientCategory.CEREALI,
    )
    cipolla = await create_ingredient(
        db_session, name="cipolla", display_name="Cipolla",
        category=IngredientCategory.VERDURA,
    )
    sale = await create_ingredient(
        db_session, name="sale", display_name="Sale", category=IngredientCategory.SPEZIE,
    )
    return {"pasta": pasta, "cipolla": cipolla, "sale": sale}


async def test_create_recipe_riempie_le_colonne(db_session, cucina):
    recipe = await create_recipe(
        db_session,
        title="prova", description=None, instructions="i", servings=4,
        source="dataset", source_ref=None,
        ingredients=[
            (cucina["pasta"].id, "primary", "300 g", None),
            (cucina["cipolla"].id, "primary", "1", None),
            (cucina["sale"].id, "secondary", "q.b.", None),
        ],
        embedding=None,
    )
    await db_session.flush()

    righe = {ri.ingredient_id: ri for ri in recipe.ingredients}
    assert righe[cucina["pasta"].id].quantity_value == Decimal("300")
    assert righe[cucina["pasta"].id].quantity_unit_id is not None
    # numero nudo: valore sì, unità no — non se ne inventa una che la fonte non ha
    assert righe[cucina["cipolla"].id].quantity_value == Decimal("1")
    assert righe[cucina["cipolla"].id].quantity_unit_id is None
    # non parsata
    assert righe[cucina["sale"].id].quantity_value is None
    assert righe[cucina["sale"].id].quantity_unit_id is None
    # e quantity_text non è stato toccato: resta la verità da mostrare
    assert righe[cucina["pasta"].id].quantity_text == "300 g"


async def test_una_unita_nuova_si_deposita_non_decisa(db_session, cucina):
    await create_recipe(
        db_session,
        title="prova2", description=None, instructions="i", servings=2,
        source="dataset", source_ref=None,
        ingredients=[(cucina["pasta"].id, "primary", "1 costa", None)],
        embedding=None,
    )
    await db_session.flush()

    unit = (
        await db_session.execute(select(Unit).where(Unit.key == "costa"))
    ).scalars().one()
    # nessuna chiamata di rete è partita: la decisione arriva dopo, da un comando
    assert unit.singular is None and unit.decided_by is None


async def test_la_stessa_unita_non_si_duplica(db_session, cucina):
    for title, nome in [("a", "pasta"), ("b", "cipolla")]:
        await create_recipe(
            db_session,
            title=title, description=None, instructions="i", servings=2,
            source="dataset", source_ref=None,
            ingredients=[(cucina[nome].id, "primary", "200 g", None)],
            embedding=None,
        )
    await db_session.flush()
    units = (
        await db_session.execute(select(Unit).where(Unit.key == "g"))
    ).scalars().all()
    assert len(units) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/api/test_recipes_quantities.py -v`
Expected: FAIL — `quantity_value` è `None` anche per «300 g»

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/repositories/units.py
"""Il registro delle unità: depositarle e rileggerle.

Sta in un repository e non nel dominio perché tocca il database; la regola di cosa
sia un'unità resta in `app/domain/quantities.py`, che non sa niente di sessioni.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.unit import Unit


async def ensure_unit(session: AsyncSession, key: str) -> Unit:
    """La riga di `key`, creandola non decisa se non c'è.

    Non chiama nessuno e non decide niente: depositare un'unità sconosciuta deve
    poter succedere dentro la transazione che scrive una ricetta, e una chiamata di
    rete lì dentro legherebbe una scrittura a un servizio esterno.
    """
    found = (
        await session.execute(select(Unit).where(Unit.key == key))
    ).scalars().first()
    if found is not None:
        return found
    unit = Unit(key=key)
    session.add(unit)
    await session.flush()
    return unit
```

In `create_recipe`, sostituisci il ciclo che costruisce le righe:

```python
    for ingredient_id, role, quantity_text, note in ingredients:
        # Il parser gira qui e non nei chiamanti: questo è già l'unico punto che
        # scrive recipe_ingredients, e chiedere a ogni chiamante di ricordarsene
        # significherebbe che il quinto — quello non ancora scritto — se ne
        # dimentica.
        value, unit_key = parse_quantity(quantity_text)
        unit = await ensure_unit(session, unit_key) if unit_key else None
        recipe.ingredients.append(
            RecipeIngredient(
                ingredient_id=ingredient_id,
                role=role,
                quantity_text=quantity_text,
                note=note,
                quantity_value=value,
                quantity_unit_id=unit.id if unit else None,
            )
        )
```

Import in cima: `from app.domain.quantities import parse_quantity` e
`from app.repositories.units import ensure_unit`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/api/test_recipes_quantities.py -v && .venv/bin/python -m pytest -q`
Expected: PASS, e tutta la suite verde

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/units.py backend/app/repositories/recipes.py \
  backend/tests/api/test_recipes_quantities.py
git commit -m "feat: create_recipe parsa la dose e deposita l'unità"
```

---

## Task 5: Il riporziona sull'API

**Files:**
- Modify: `backend/app/schemas/recipe.py:47-70`
- Modify: `backend/app/api/recipes.py:45-78` (`_to_out`) e `:134-143` (`detail`)
- Test: `backend/tests/api/test_recipes_riporziona.py`

**Interfaces:**
- Consumes: `scale_quantity`, `render_quantity`, `UnitForms` (Task 2); le colonne
  (Task 3-4).
- Produces: `GET /api/v1/recipes/{id}?servings=N`; `RecipeIngredientOut.quantity_display`,
  `.quantity_scaled`; `RecipeOut.scaled_to`, `.unscalable_lines`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/api/test_recipes_riporziona.py
"""Il riporziona per porzioni, visto dalla rotta che lo serve."""

import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import IngredientCategory
from app.db.models.unit import Unit
from app.repositories.ingredients import create_ingredient
from app.repositories.recipes import create_recipe


@pytest_asyncio.fixture
async def cucina(db_session):
    return {
        "pasta": await create_ingredient(
            db_session, name="pasta", display_name="Pasta",
            category=IngredientCategory.CEREALI,
        ),
        "cipolla": await create_ingredient(
            db_session, name="cipolla", display_name="Cipolla",
            category=IngredientCategory.VERDURA,
        ),
        "sale": await create_ingredient(
            db_session, name="sale", display_name="Sale",
            category=IngredientCategory.SPEZIE,
        ),
    }


async def _ricetta(db_session, cucina, servings):
    """Una ricetta con tutti e tre gli stati di dose: piena, numero nudo, non parsata."""
    recipe = await create_recipe(
        db_session,
        title="Mista", description=None, instructions="i", servings=servings,
        source="dataset", source_ref=None,
        ingredients=[
            (cucina["pasta"].id, "primary", "300 g", None),
            (cucina["cipolla"].id, "primary", "1", None),
            (cucina["sale"].id, "secondary", "q.b.", None),
        ],
        embedding=None,
    )
    # «g» decisa a mano: qui non gira nessun AI. Senza le forme il ridisegno
    # mostrerebbe la chiave, che per «g» è identica — e allora il test non direbbe
    # se le forme arrivano davvero a video.
    unit = (
        await db_session.execute(select(Unit).where(Unit.key == "g"))
    ).scalars().one()
    unit.singular, unit.plural, unit.decided_by = "g", "g", "human"
    await db_session.flush()
    return recipe.id


@pytest_asyncio.fixture
async def ricetta_mista(db_session, cucina):
    return await _ricetta(db_session, cucina, servings=4)


@pytest_asyncio.fixture
async def ricetta_senza_porzioni(db_session, cucina):
    return await _ricetta(db_session, cucina, servings=None)


async def test_senza_parametro_il_corpo_e_quello_di_sempre(logged_client, ricetta_mista):
    corpo = (await logged_client.get(f"/api/v1/recipes/{ricetta_mista}")).json()
    assert corpo["scaled_to"] is None
    assert corpo["unscalable_lines"] == 0
    for line in corpo["ingredients"]:
        assert line["quantity_display"] == line["quantity_text"]
        assert line["quantity_scaled"] is False


async def test_con_servings_le_dosi_parsate_scalano(logged_client, ricetta_mista):
    # la ricetta è per 4: chiederla per 2 dimezza
    corpo = (await logged_client.get(f"/api/v1/recipes/{ricetta_mista}?servings=2")).json()
    per_testo = {line["quantity_text"]: line for line in corpo["ingredients"]}

    assert per_testo["300 g"]["quantity_display"] == "150 g"
    assert per_testo["300 g"]["quantity_scaled"] is True
    # numero nudo: scala e resta nudo
    assert per_testo["1"]["quantity_display"] == "0,5"
    # non parsata: resta identica, ed è la risposta giusta
    assert per_testo["q.b."]["quantity_display"] == "q.b."
    assert per_testo["q.b."]["quantity_scaled"] is False

    assert corpo["scaled_to"] == 2
    assert corpo["unscalable_lines"] == 1


async def test_le_stesse_porzioni_sono_come_non_averle_chieste(logged_client, ricetta_mista):
    """A 1× il testo originale dice la verità meglio di quanto sappiamo riscriverla."""
    corpo = (await logged_client.get(f"/api/v1/recipes/{ricetta_mista}?servings=4")).json()
    assert corpo["scaled_to"] is None
    assert corpo["unscalable_lines"] == 0
    for line in corpo["ingredients"]:
        assert line["quantity_display"] == line["quantity_text"]


async def test_senza_porzioni_dichiarate_il_parametro_si_ignora(
    logged_client, ricetta_senza_porzioni
):
    corpo = (
        await logged_client.get(f"/api/v1/recipes/{ricetta_senza_porzioni}?servings=2")
    ).json()
    assert corpo["scaled_to"] is None
    for line in corpo["ingredients"]:
        assert line["quantity_display"] == line["quantity_text"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/api/test_recipes_riporziona.py -v`
Expected: FAIL con `KeyError: 'quantity_display'`

- [ ] **Step 3: Write minimal implementation**

In `backend/app/schemas/recipe.py`:

```python
class RecipeIngredientOut(BaseModel):
    ...
    # quel che va mostrato: a 1× è quantity_text, riscritto solo quando si riporziona
    quantity_display: str | None
    quantity_scaled: bool


class RecipeOut(BaseModel):
    ...
    scaled_to: int | None = None
    unscalable_lines: int = 0
```

In `backend/app/api/recipes.py`:

```python
async def _to_out(
    session: AsyncSession, recipe: Recipe, servings: int | None = None
) -> RecipeOut:
    ...
    # Il fattore sta qui e non nel client: la pluralizzazione e l'aritmetica sono
    # logica di dominio, ed è la riga di CLAUDE.md che tiene in piedi la porta a
    # Capacitor. In TypeScript vorrebbe dire spedire il registro delle unità al
    # client e tenere le stesse regole in due lingue.
    factor: Decimal | None = None
    if servings and recipe.servings:
        factor = Decimal(servings) / Decimal(recipe.servings)
        if factor == 1:
            factor = None  # chiedere le porzioni che ha già è come non chiedere niente

    unscalable = 0
    for ri in recipe.ingredients:
        ...
        if factor is not None and ri.quantity_value is not None:
            forms = (
                UnitForms(ri.unit.key, ri.unit.singular, ri.unit.plural)
                if ri.unit
                else None
            )
            display = render_quantity(scale_quantity(ri.quantity_value, factor), forms)
            scaled = True
        else:
            display = ri.quantity_text
            scaled = False
            if factor is not None:
                unscalable += 1
        lines.append(
            RecipeIngredientOut(
                ...,
                quantity_display=display,
                quantity_scaled=scaled,
            )
        )
    return RecipeOut(
        ...,
        scaled_to=servings if factor is not None else None,
        unscalable_lines=unscalable,
    )
```

E la rotta:

```python
@router.get("/{recipe_id}", response_model=RecipeOut)
async def detail(
    recipe_id: uuid.UUID,
    servings: int | None = Query(default=None, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
) -> RecipeOut:
    ...
    return await _to_out(session, recipe, servings=servings)
```

Import: `from decimal import Decimal`, `Query` da `fastapi`, e
`from app.domain.quantities import UnitForms, render_quantity, scale_quantity`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/api/ -v && .venv/bin/python -m pytest -q`
Expected: PASS. Se `tests/api/test_recipes.py` fallisce su un corpo senza i campi
nuovi, aggiorna quelle asserzioni: i campi ci sono sempre, e a 1× valgono
`quantity_text` e `False`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/recipe.py backend/app/api/recipes.py \
  backend/tests/api/test_recipes_riporziona.py
git commit -m "feat: GET /recipes/{id}?servings= riporziona, e dichiara cosa non scala"
```

---

## Task 6: Il comando che riempie, e che riempie di nuovo

**Files:**
- Create: `backend/app/cli/reparse_quantities.py`
- Test: `backend/tests/test_reparse_quantities_cli.py`

**Interfaces:**
- Consumes: `parse_quantity` (Task 1), `ensure_unit` (Task 4).
- Produces: `reparse(session) -> Reparsed(parsed: int, unparsed: int, new_units: int)`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_reparse_quantities_cli.py
"""Il comando che riempie le colonne, e che le riempie di nuovo."""

from decimal import Decimal

import pytest_asyncio
from sqlalchemy import select, update

from app.cli.reparse_quantities import reparse
from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe import RecipeIngredient
from app.repositories.ingredients import create_ingredient
from app.repositories.recipes import create_recipe


@pytest_asyncio.fixture
async def ricetta_mista(db_session):
    pasta = await create_ingredient(
        db_session, name="pasta", display_name="Pasta",
        category=IngredientCategory.CEREALI,
    )
    cipolla = await create_ingredient(
        db_session, name="cipolla", display_name="Cipolla",
        category=IngredientCategory.VERDURA,
    )
    sale = await create_ingredient(
        db_session, name="sale", display_name="Sale", category=IngredientCategory.SPEZIE,
    )
    await create_recipe(
        db_session,
        title="Mista", description=None, instructions="i", servings=4,
        source="dataset", source_ref=None,
        ingredients=[
            (pasta.id, "primary", "300 g", None),
            (cipolla.id, "primary", "1", None),
            (sale.id, "secondary", "q.b.", None),
        ],
        embedding=None,
    )
    await db_session.flush()


async def test_riempie_le_righe_svuotate(db_session, ricetta_mista):
    """Il caso della messa in produzione: la migrazione aggiunge le colonne vuote e
    questo comando le riempie rileggendo quantity_text, che non si perde mai."""
    await db_session.execute(
        update(RecipeIngredient).values(quantity_value=None, quantity_unit_id=None)
    )
    await db_session.flush()

    esito = await reparse(db_session)

    assert esito.parsed == 2 and esito.unparsed == 1
    righe = (await db_session.execute(select(RecipeIngredient))).scalars().all()
    per_testo = {ri.quantity_text: ri for ri in righe}
    assert per_testo["300 g"].quantity_value == Decimal("300")
    assert per_testo["300 g"].quantity_unit_id is not None
    assert per_testo["q.b."].quantity_value is None


async def test_e_rieseguibile(db_session, ricetta_mista):
    """Il parser migliorerà, e migliorarlo non deve voler dire una migrazione."""
    primo = await reparse(db_session)
    secondo = await reparse(db_session)
    assert (primo.parsed, primo.unparsed) == (secondo.parsed, secondo.unparsed)
    # la seconda passata non deposita niente: «g» c'è già
    assert secondo.new_units == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_reparse_quantities_cli.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.cli.reparse_quantities'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/cli/reparse_quantities.py
"""Riempie `quantity_value` e `quantity_unit_id` rileggendo `quantity_text`.

Eseguire con `python -m app.cli.reparse_quantities` dentro il container del backend,
una volta dopo la migrazione `0008` e ogni volta che il parser migliora.

Non è un passo dati dentro la migrazione proprio per questo: il primo catalogo vero
porterà forme di dose che 26 ricette non hanno, e migliorare il parser non deve voler
dire scriverne un'altra. È la stessa ragione per cui esiste `app.cli.reindex`.
"""

import asyncio
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.db.models.recipe import RecipeIngredient
from app.db.models.unit import Unit
from app.domain.quantities import parse_quantity
from app.repositories.units import ensure_unit

BATCH = 500


@dataclass(frozen=True)
class Reparsed:
    parsed: int
    unparsed: int
    new_units: int


async def reparse(session: AsyncSession) -> Reparsed:
    before = len((await session.execute(select(Unit.id))).scalars().all())
    parsed = unparsed = 0
    rows = (await session.execute(select(RecipeIngredient))).scalars().all()
    for row in rows:
        value, key = parse_quantity(row.quantity_text)
        unit = await ensure_unit(session, key) if key else None
        row.quantity_value = value
        row.quantity_unit_id = unit.id if unit else None
        if value is None:
            unparsed += 1
        else:
            parsed += 1
    await session.flush()
    after = len((await session.execute(select(Unit.id))).scalars().all())
    return Reparsed(parsed=parsed, unparsed=unparsed, new_units=after - before)


async def main() -> None:
    async with SessionLocal() as session:
        esito = await reparse(session)
        await session.commit()
    print(
        f"{esito.parsed} dosi parsate, {esito.unparsed} no, "
        f"{esito.new_units} unità nuove depositate"
    )
    if esito.new_units:
        print("decidile con: python -m app.cli.decide_units")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_reparse_quantities_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/cli/reparse_quantities.py backend/tests/test_reparse_quantities_cli.py
git commit -m "feat: reparse_quantities, rieseguibile perché il parser migliorerà"
```

---

## Task 7: L'AI decide singolare e plurale

**Files:**
- Modify: `backend/app/services/llm.py:25-37` (`LlmCallSite`)
- Modify: `backend/app/repositories/units.py` (`undecided_units`, `apply_forms`)
- Create: `backend/app/services/unit_forms.py`
- Test: `backend/tests/services/test_unit_forms.py`

**Interfaces:**
- Consumes: `complete_json`, `LlmUnavailable`, `LlmUsage`, `record_llm_call`.
- Produces: `decide_unit_forms(session, client=None) -> Decided(applied: int, refused: int)`
  in `services/unit_forms.py`; `undecided_units(session) -> list[Unit]` e
  `apply_forms(session, unit, singular, plural) -> None` in `repositories/units.py`
  (le query e le scritture del registro stanno nel repository, la chiamata nel servizio).

- [ ] **Step 1: Write the failing test**

Guarda `backend/tests/llm_fakes.py` e `backend/tests/services/test_decide_one.py` per
come questo progetto finge una risposta dell'LLM, e usa lo stesso meccanismo: non
introdurne uno nuovo.

```python
# backend/tests/services/test_unit_forms.py
"""Le forme delle unità decise dall'AI, e la verifica della sua risposta.

Come per i termini dell'import, la parte che conta è la verifica: una risposta che
non si può controllare non si applica, e la parola resta non decisa — cioè si
continua a mostrarla grezza, che è brutto e non è rotto.

Il finto sostituisce `httpx.AsyncClient`, non il client di OpenRouter: sotto prova
c'è `complete_json` per intero, header e corpo compresi.
"""

import pytest
from sqlalchemy import select

from app.db.models.unit import Unit
from app.services.unit_forms import decide_unit_forms
from llm_fakes import FakeLlm


@pytest.fixture(autouse=True)
def chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


async def _unita(db_session, *keys: str) -> None:
    db_session.add_all([Unit(key=key) for key in keys])
    await db_session.flush()


async def _riletta(db_session, key: str) -> Unit:
    return (
        await db_session.execute(select(Unit).where(Unit.key == key))
    ).scalars().one()


async def test_applica_le_forme_decise(db_session):
    await _unita(db_session, "cucchiai", "costa")
    finto = FakeLlm({"units": [
        {"key": "cucchiai", "singular": "cucchiaio", "plural": "cucchiai"},
        {"key": "costa", "singular": "costa", "plural": "coste"},
    ]})

    esito = await decide_unit_forms(db_session, client=finto)

    assert esito.applied == 2 and esito.refused == 0
    costa = await _riletta(db_session, "costa")
    assert (costa.singular, costa.plural) == ("costa", "coste")
    assert costa.decided_by == "ai" and costa.decided_at is not None


async def test_una_chiave_non_chiesta_non_si_applica(db_session):
    await _unita(db_session, "costa")
    finto = FakeLlm({"units": [
        {"key": "spicchio", "singular": "spicchio", "plural": "spicchi"},
    ]})

    esito = await decide_unit_forms(db_session, client=finto)

    assert esito.applied == 0 and esito.refused == 1
    assert (await _riletta(db_session, "costa")).decided_by is None
    # e non è comparsa una riga per una parola che nessuna ricetta ha mai scritto
    assert (
        await db_session.execute(select(Unit).where(Unit.key == "spicchio"))
    ).scalars().first() is None


async def test_una_forma_vuota_non_si_applica(db_session):
    await _unita(db_session, "costa")
    finto = FakeLlm({"units": [{"key": "costa", "singular": "", "plural": "coste"}]})

    esito = await decide_unit_forms(db_session, client=finto)

    assert esito.applied == 0 and esito.refused == 1
    assert (await _riletta(db_session, "costa")).decided_by is None


async def test_il_singolare_che_esiste_gia_non_duplica(db_session):
    """«cucchiai» punta a «cucchiaio»: serve a S4, che riempirà il peso della coppia
    ingrediente×unità una volta sola invece di due."""
    cucchiaio = Unit(
        key="cucchiaio", singular="cucchiaio", plural="cucchiai", decided_by="ai"
    )
    db_session.add_all([cucchiaio, Unit(key="cucchiai")])
    await db_session.flush()
    finto = FakeLlm({"units": [
        {"key": "cucchiai", "singular": "cucchiaio", "plural": "cucchiai"},
    ]})

    await decide_unit_forms(db_session, client=finto)

    riga = await _riletta(db_session, "cucchiai")
    assert riga.canonical_id == cucchiaio.id
    # le forme si scrivono comunque sulla riga: il dettaglio della ricetta le legge
    # dirette, senza seguire il puntatore a ogni lettura
    assert riga.singular == "cucchiaio"


async def test_ai_irraggiungibile_non_scrive_niente(db_session):
    """Per l'utente non è successo niente: il riporziona scala lo stesso e mostra la
    parola come è arrivata."""
    import httpx

    await _unita(db_session, "costa")
    finto = FakeLlm(httpx.ReadTimeout("lento"))

    esito = await decide_unit_forms(db_session, client=finto)

    assert esito.applied == 0
    assert (await _riletta(db_session, "costa")).decided_by is None


async def test_senza_unita_in_attesa_non_chiama_nessuno(db_session):
    """Il comando si può lanciare due volte di fila senza spendere due volte."""
    db_session.add(Unit(key="g", singular="g", plural="g", decided_by="ai"))
    await db_session.flush()
    finto = FakeLlm({"units": []})

    esito = await decide_unit_forms(db_session, client=finto)

    assert (esito.applied, esito.refused) == (0, 0)
    assert finto.bodies == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/services/test_unit_forms.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.services.unit_forms'`

- [ ] **Step 3: Write minimal implementation**

In `backend/app/services/llm.py`, dentro `LlmCallSite`:

```python
    UNIT_FORMS = "unit_forms"
```

In `backend/app/repositories/units.py` — le query e le scritture del registro
stanno qui, la chiamata al modello sta nel servizio:

```python
async def undecided_units(session: AsyncSession) -> list[Unit]:
    return list(
        (
            await session.execute(select(Unit).where(Unit.decided_by.is_(None)))
        ).scalars().all()
    )


async def apply_forms(
    session: AsyncSession, unit: Unit, singular: str, plural: str
) -> None:
    unit.singular = singular
    unit.plural = plural
    unit.decided_by = "ai"
    unit.decided_at = datetime.now(UTC)
    # «cucchiai» il cui singolare è «cucchiaio», che esiste già: ci punta, così S4
    # riempirà il peso di quell'unità una volta sola. Le forme restano scritte anche
    # sulla riga: il dettaglio della ricetta le legge dirette, senza seguire il
    # puntatore a ogni lettura.
    if singular != unit.key:
        canonical = (
            await session.execute(select(Unit).where(Unit.key == singular))
        ).scalars().first()
        if canonical is not None and canonical.id != unit.id:
            unit.canonical_id = canonical.id
```

Serve `from datetime import UTC, datetime` in cima a `repositories/units.py`.

```python
# backend/app/services/unit_forms.py
"""Chi decide come si scrive un'unità di misura.

Una chiamata sola per tutte le unità in attesa: sono una manciata di parole, non 40
stringhe da riecheggiare identiche come nei termini dell'import, quindi il lotto qui
non è il posto dove un MoE piccolo si sfalda. Sul tetto di 1$/giorno non si sente.
"""

import json
import logging
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.unit import UNIT_MAX_LENGTH, Unit
from app.repositories.llm_calls import record_llm_call
from app.repositories.units import apply_forms, undecided_units
from app.services.llm import (
    LlmCallSite,
    LlmUnavailable,
    LlmUsage,
    complete_json,
)

logger = logging.getLogger(__name__)

FORMS_MAX_TOKENS = 600

FORMS_SYSTEM_PROMPT = """Ricevi un elenco di parole italiane usate come unità di misura nelle dosi di una ricetta. Per ognuna rispondi con il singolare e il plurale.

Regole:
- "key" deve essere riscritta identica a come te l'ho passata.
- Per le sigle invariabili (g, kg, ml, l) singolare e plurale sono uguali alla sigla.
- Non aggiungere parole che non ti ho passato, e non toglierne.
"""

FORMS_SCHEMA = {
    "type": "object",
    "properties": {
        "units": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "singular": {"type": "string"},
                    "plural": {"type": "string"},
                },
                "required": ["key", "singular", "plural"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["units"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class Decided:
    applied: int
    refused: int


async def decide_unit_forms(
    session: AsyncSession, client: httpx.AsyncClient | None = None
) -> Decided:
    pending = await undecided_units(session)
    if not pending:
        return Decided(applied=0, refused=0)

    asked = {unit.key: unit for unit in pending}
    try:
        esito = await complete_json(
            call_site=LlmCallSite.UNIT_FORMS,
            system=FORMS_SYSTEM_PROMPT,
            user=json.dumps({"units": sorted(asked)}, ensure_ascii=False),
            schema=FORMS_SCHEMA,
            schema_name="forme_unita",
            max_tokens=FORMS_MAX_TOKENS,
            client=client,
        )
    except LlmUnavailable as exc:
        # mai un vicolo cieco: le unità restano non decise e si mostrano grezze
        logger.info("forme delle unità non decise: %s", exc)
        await record_llm_call(
            session, call_site=LlmCallSite.UNIT_FORMS, usage=LlmUsage(), ok=False
        )
        return Decided(applied=0, refused=0)

    await record_llm_call(
        session, call_site=LlmCallSite.UNIT_FORMS, usage=esito.usage, ok=True
    )

    applied = refused = 0
    for answer in esito.data.get("units") or []:
        unit = asked.get(answer.get("key"))
        singular = (answer.get("singular") or "").strip()
        plural = (answer.get("plural") or "").strip()
        # si applica solo quel che si può verificare: la chiave dev'essere una di
        # quelle chieste e le due forme non vuote ed entro il limite della colonna
        if unit is None or not singular or not plural:
            refused += 1
            continue
        if len(singular) > UNIT_MAX_LENGTH or len(plural) > UNIT_MAX_LENGTH:
            refused += 1
            continue
        await apply_forms(session, unit, singular, plural)
        applied += 1
    await session.flush()
    return Decided(applied=applied, refused=refused)


```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/services/test_unit_forms.py -v && .venv/bin/python -m pytest -q`
Expected: PASS. Se `tests/test_llm_spend_is_recorded.py` elenca le sezioni note,
aggiungici `UNIT_FORMS`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/unit_forms.py backend/app/services/llm.py \
  backend/app/repositories/units.py backend/tests/services/test_unit_forms.py
git commit -m "feat: l'AI decide singolare e plurale delle unità, e si verifica prima di applicare"
```

---

## Task 8: Il comando che le fa decidere

**Files:**
- Create: `backend/app/cli/decide_units.py`
- Modify: `backend/app/repositories/units.py` (`reset_unit`)
- Test: `backend/tests/test_decide_units_cli.py`

**Interfaces:**
- Consumes: `decide_unit_forms` (Task 7).
- Produces: comando `python -m app.cli.decide_units [--azzera <key>]`;
  `reset_unit(session, key) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_decide_units_cli.py
"""L'undo di una decisione dell'AI sulle unità."""

from sqlalchemy import select

from app.db.models.unit import Unit
from app.repositories.units import reset_unit


async def test_azzerare_riporta_una_unita_a_non_decisa(db_session):
    """L'undo di una decisione AI: la chiamata successiva la ridecide."""
    db_session.add(
        Unit(key="costa", singular="costa", plural="cost", decided_by="ai")
    )
    await db_session.flush()

    assert await reset_unit(db_session, "costa") is True

    costa = (await db_session.execute(select(Unit).where(Unit.key == "costa"))).scalars().one()
    assert costa.decided_by is None and costa.singular is None and costa.plural is None


async def test_azzerare_una_chiave_che_non_esiste_lo_dice(db_session):
    assert await reset_unit(db_session, "inesistente") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_decide_units_cli.py -v`
Expected: FAIL con `ImportError: cannot import name 'reset_unit'`

- [ ] **Step 3: Write minimal implementation**

In `backend/app/repositories/units.py`:

```python
async def reset_unit(session: AsyncSession, key: str) -> bool:
    """Riporta un'unità a non decisa. Torna `False` se quella chiave non c'è."""
    unit = (
        await session.execute(select(Unit).where(Unit.key == key))
    ).scalars().first()
    if unit is None:
        return False
    unit.singular = None
    unit.plural = None
    unit.decided_by = None
    unit.decided_at = None
    unit.canonical_id = None
    await session.flush()
    return True
```

```python
# backend/app/cli/decide_units.py
"""Fa decidere all'AI singolare e plurale delle unità in attesa.

    python -m app.cli.decide_units
    python -m app.cli.decide_units --azzera cucchiai

Il secondo è l'undo: riporta una riga a non decisa, e la chiamata dopo la ridecide.
"""

import asyncio
import sys

from app.core.db import SessionLocal
from app.repositories.units import reset_unit
from app.services.unit_forms import decide_unit_forms

FLAG_AZZERA = "--azzera"


async def main(argv: list[str]) -> int:
    # La guardia esce con codice diverso da zero, non solo stampando: un refuso in
    # uno script che controlla l'exit code non deve passare per un successo.
    if argv and argv[0] != FLAG_AZZERA:
        print(f"argomento sconosciuto: {argv[0]}")
        return 2
    if argv and argv[0] == FLAG_AZZERA:
        if len(argv) != 2:
            print(f"uso: {FLAG_AZZERA} <chiave>")
            return 2
        async with SessionLocal() as session:
            done = await reset_unit(session, argv[1])
            await session.commit()
        print("azzerata" if done else f"nessuna unità con chiave «{argv[1]}»")
        return 0 if done else 1

    async with SessionLocal() as session:
        esito = await decide_unit_forms(session)
        await session.commit()
    print(f"{esito.applied} unità decise, {esito.refused} risposte rifiutate")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_decide_units_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/cli/decide_units.py backend/app/repositories/units.py \
  backend/tests/test_decide_units_cli.py
git commit -m "feat: il comando che fa decidere le unità, con il suo undo"
```

---

## Task 9: Il selettore delle porzioni

**Files:**
- Modify: `frontend/src/domain/types.ts:82-97`
- Modify: `frontend/src/features/recipes/api.ts:41-43`
- Create: `frontend/src/features/cooking/ServingsStepper.tsx`
- Modify: `frontend/src/features/cooking/RecipeDetailScreen.tsx`
- Test: `frontend/src/features/cooking/RecipeDetailScreen.test.tsx`

**Interfaces:**
- Consumes: l'API del Task 5.
- Produces: `fetchRecipe(id: string, servings?: number)`; `<ServingsStepper value onChange />`.

- [ ] **Step 1: Write the failing test**

```tsx
// in coda a frontend/src/features/cooking/RecipeDetailScreen.test.tsx

/** Come `stubFetch`, ma la risposta dipende dall'indirizzo: qui servono due corpi
 * diversi — la ricetta com'è, e la ricetta riporzionata — e `mockImplementation` è
 * obbligatorio perché il corpo di una Response si legge una volta sola. */
function stubFetchByUrl(route: (url: string) => unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: unknown) =>
      Promise.resolve(new Response(JSON.stringify(route(String(url))), { status: 200 }))
    )
  );
}

// la stessa ricetta chiesta per 2 invece che per 4: è il server a decidere queste
// stringhe, e il client non le ricalcola — per questo il finto le detta
const DIMEZZATA = {
  ...DETAIL,
  scaled_to: 2,
  unscalable_lines: 2,
  ingredients: [
    { ...DETAIL.ingredients[0], quantity_display: "90 g", quantity_scaled: true },
    { ...DETAIL.ingredients[1], quantity_display: "200 g", quantity_scaled: true },
    { ...DETAIL.ingredients[2], quantity_display: null, quantity_scaled: false },
    { ...DETAIL.ingredients[3], quantity_display: null, quantity_scaled: false },
  ],
};

it("il selettore delle porzioni rilegge la ricetta e mostra quel che dice il server", async () => {
  // il client non fa aritmetica: chiede e mostra. È la riga di CLAUDE.md che tiene
  // in piedi la porta a Capacitor.
  const spy = vi.fn();
  stubFetchByUrl((url) => {
    spy(url);
    return url.includes("servings=1") ? DIMEZZATA : DETAIL;
  });

  renderScreen();
  expect(await screen.findByText("180 g")).toBeDefined();

  // DETAIL è per 2 porzioni: un tocco porta a 1
  await userEvent.click(screen.getByRole("button", { name: "Una porzione in meno" }));

  expect(await screen.findByText("90 g")).toBeDefined();
  // e la copertura si dichiara invece di far finta di niente
  expect(screen.getByText(/2 dosi su 4 non si riscalano/)).toBeDefined();
  expect(spy.mock.calls.some(([url]) => String(url).includes("servings=1"))).toBe(true);
});

it("senza porzioni dichiarate il selettore non compare", async () => {
  stubFetch({ servings: null });
  renderScreen();
  await screen.findByText("180 g");
  expect(screen.queryByRole("button", { name: /porzione in meno/ })).toBeNull();
});
```

> **Le fixture del file vanno aggiornate.** `DETAIL` non ha `quantity_display`,
> `quantity_scaled`, `scaled_to` né `unscalable_lines`: aggiungili alle sue quattro
> righe (a 1× `quantity_display` vale `quantity_text`, `quantity_scaled` è `false`,
> `scaled_to` è `null`, `unscalable_lines` è `0`). Lasciarli indietro fa fallire
> `npm run typecheck` con un `TS2739` — quello che `tsc --noEmit` non vede, settima
> lezione di `CLAUDE.md`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/features/cooking/RecipeDetailScreen.test.tsx`
Expected: FAIL — il pulsante «Una porzione in meno» non esiste

- [ ] **Step 3: Write minimal implementation**

```ts
// frontend/src/domain/types.ts — RecipeIngredientLine guadagna:
  quantity_display: string | null;
  quantity_scaled: boolean;
// RecipeDetail guadagna:
  scaled_to: number | null;
  unscalable_lines: number;
```

```ts
// frontend/src/features/recipes/api.ts
export function fetchRecipe(id: string, servings?: number) {
  const query = servings ? `?servings=${servings}` : "";
  return apiFetch<RecipeDetail>(`/recipes/${id}${query}`);
}
```

```tsx
// frontend/src/features/cooking/ServingsStepper.tsx
import { buttonClasses } from "../../components/ui/buttonClasses";

/** Per quante porzioni si vuole la ricetta.
 *
 * I due tasti portano la loro altezza da bersaglio da `buttonClasses` (min-h-11):
 * questo si tocca in cucina, con le mani occupate, e una freccia stretta si sbaglia.
 */
export function ServingsStepper({
  value,
  onChange,
}: {
  value: number;
  onChange: (next: number) => void;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-ink-soft">Per</span>
      <button
        type="button"
        aria-label="Una porzione in meno"
        disabled={value <= 1}
        onClick={() => onChange(value - 1)}
        className={`${buttonClasses("secondary")} w-11`}
      >
        −
      </button>
      <span className="min-w-8 text-center font-medium" aria-live="polite">
        {value}
      </span>
      <button
        type="button"
        aria-label="Una porzione in più"
        disabled={value >= 50}
        onClick={() => onChange(value + 1)}
        className={`${buttonClasses("secondary")} w-11`}
      >
        +
      </button>
      <span className="text-sm text-ink-soft">{value === 1 ? "porzione" : "porzioni"}</span>
    </div>
  );
}
```

In `RecipeDetailScreen.tsx`:

```tsx
  // le porzioni chieste: è una vista, non si salva. Uscire dalla ricetta se ne
  // dimentica, ed è quel che vuole chi sta guardando cosa cucinare stasera.
  const [servings, setServings] = useState<number | null>(null);

  const { data: recipe, ... } = useQuery({
    queryKey: ["recipe", id, servings],
    queryFn: () => fetchRecipe(id, servings ?? undefined),
  });
```

Il primo `servings` utile arriva dalla ricetta stessa: mostra lo stepper solo quando
`recipe.servings` non è nulla, con `value={servings ?? recipe.servings}`.

Nella riga dell'ingrediente, sostituisci `line.quantity_text` con
`line.quantity_display`. Sotto l'elenco dei gruppi:

```tsx
          {recipe.unscalable_lines > 0 && (
            <p className="px-1 pt-2 text-sm text-ink-faint">
              {recipe.unscalable_lines === 1
                ? `1 dose su ${totalLines} non si riscala: resta com'è.`
                : `${recipe.unscalable_lines} dosi su ${totalLines} non si riscalano: restano come sono.`}
            </p>
          )}
```

dove `totalLines` è `recipe.ingredients.length`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run && npm run typecheck && npm run build`
Expected: PASS su tutti e tre. **`tsc --noEmit` non conta** (settima lezione di
`CLAUDE.md`): `npm run typecheck` esegue `tsc -b`, che compila i project reference.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/domain/types.ts frontend/src/features/recipes/api.ts \
  frontend/src/features/cooking/ServingsStepper.tsx \
  frontend/src/features/cooking/RecipeDetailScreen.tsx \
  frontend/src/features/cooking/RecipeDetailScreen.test.tsx
git commit -m "feat: il selettore delle porzioni, che chiede al server e non calcola"
```

---

## Task 10: La verifica nel browser vero

**Files:**
- Modify: `frontend/e2e/style.spec.ts`

**Interfaces:**
- Consumes: il selettore del Task 9.
- Produces: niente che altri task usino.

- [ ] **Step 1: Write the failing test**

```ts
// in coda a frontend/e2e/style.spec.ts
test("i tasti delle porzioni sono bersagli da pollice, e il riporziona arriva a video", async ({
  page,
}) => {
  // jsdom non calcola il CSS: che due tasti da toccare in cucina siano davvero
  // grandi abbastanza non lo può dire nessun test in memoria (quarta lezione di
  // CLAUDE.md). E il giro completo prova anche che il server sta rispondendo
  // davvero al parametro, non che un nostro stub lo finge.
  await page.getByRole("link", { name: "Ricette", exact: true }).click();
  await page.getByRole("link", { name: /Pasta al pomodoro/ }).first().click();

  const meno = page.getByRole("button", { name: "Una porzione in meno" });
  const box = await meno.boundingBox();
  expect(box!.height).toBeGreaterThanOrEqual(40);
  expect(box!.width).toBeGreaterThanOrEqual(40);

  // «Pasta al pomodoro» nel seme è per 2 porzioni e ha dosi di tutti i tipi:
  // «180 g», «400 g», «1 spicchio», «2 cucchiai», «q.b.». Un tocco porta a 1, cioè
  // dimezza: «180 g» deve diventare «90 g», e «q.b.» deve restare «q.b.».
  const riga = page.locator("li", { hasText: "pasta" }).first();
  await expect(riga).toContainText("180 g");
  await meno.click();
  await expect(riga).toContainText("90 g");
  await expect(page.getByText("q.b.").first()).toBeVisible();
  // a 1 non si scende: il tasto si spegne invece di proporre zero porzioni
  await expect(meno).toBeDisabled();
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
E2E="docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml"
$E2E up -d --build --wait
$E2E exec -T backend python -m app.cli.seed
$E2E exec -T backend python -m app.cli.reparse_quantities
(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
```
Expected: il test nuovo fallisce se il selettore non è arrivato all'app costruita;
gli altri nove restano verdi.

- [ ] **Step 3: Guarda la schermata a 375px**

Non c'è codice da scrivere in questo passo: apri la ricetta a 375px, cambia le
porzioni, e controlla con gli occhi che le dosi ridisegnate non sfondino la riga e
che la frase della copertura non sembri un errore. Se qualcosa non torna, la
correzione è nel Task 9 e questo passo si ripete.

- [ ] **Step 4: Rerun, e pulisci lo stack**

```bash
(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
$E2E down -v
```
Expected: 10 controlli verdi. **`down -v` non è facoltativo**: un giro a mano sporca
la dispensa condivisa, e `cooking.spec.ts` pretende una lista vuota.

- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/style.spec.ts
git commit -m "test: i tasti delle porzioni sono bersagli da pollice, nel browser vero"
```

---

## Task 11: Gli emendamenti

**Files:**
- Modify: `CLAUDE.md` (decisione fondante 1 e il riquadro che annuncia questo lavoro)
- Modify: `docs/superpowers/specs/2026-09-11-spena-design.md` §2
- Modify: `docs/prossimi-passi.md` (D1, R2, Parte X)

**Interfaces:**
- Consumes: tutto quel che precede.
- Produces: niente codice.

- [ ] **Step 1: Emenda `CLAUDE.md`**

Il paragrafo «**1. No quantities, anywhere.**» dice oggi che `quantity_text` è testo
libero che **non deve mai entrare in un calcolo**, e il riquadro sotto annuncia questo
lavoro come «deciso ma non ancora costruito». Vanno riscritti insieme: il riquadro
sparisce, e il paragrafo diventa — la dispensa tiene la regola intera (niente
quantità, niente unità, niente scadenze, ed è lì che la regola ha comprato quel che
doveva comprare), le ricette hanno `quantity_value` e `quantity_unit_id` accanto a
`quantity_text`, che non viene mai riscritto. Nomina `app/domain/quantities.py` come
il posto dove sta la regola, e ricorda che `fill_percent` resta una posizione, non una
quantità.

- [ ] **Step 2: Emenda il §2 della spec madre**

`docs/superpowers/specs/2026-09-11-spena-design.md` §2 porta la stessa affermazione.
Stessa correzione, stesso giorno: una delle due lasciata indietro diventa la
documentazione che mente.

- [ ] **Step 3: Aggiorna `docs/prossimi-passi.md`**

- **D1** passa a «FATTO», con la data e il commit, e la riga sulla verifica in
  produzione — in quel file «FATTO» significa codice che gira su
  `spena.mattiagirellini.com`, non codice fermo in un ramo;
- **R2** resta aperta ma dimezzata: la metà per porzioni è fatta, restano l'ancoraggio
  su un ingrediente e la domanda se il riporziona si salvi;
- **Parte X** guadagna la voce dichiarata nella spec: non esiste una schermata per
  correggere un plurale sbagliato, si corregge da `python -m app.cli.decide_units
  --azzera <chiave>`;
- **S4** guadagna un rimando: il registro delle unità e l'attacco per il peso della
  coppia ingrediente×unità esistono già, e non serve una migrazione per riempirlo.

- [ ] **Step 4: Verifica che non sia rimasta una promessa vecchia**

```bash
grep -rn "mai entrare in un calcolo\|never enter a calculation" CLAUDE.md docs/
```
Expected: nessun risultato che parli delle ricette. Quel che resta deve parlare della
dispensa.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/
git commit -m "docs: la decisione fondante 1 si restringe alla dispensa"
```

---

## La messa in produzione

Dopo l'ultimo task, e non prima:

1. `git push origin master`
2. sul server: `cd ~/sites/spena && git pull --ff-only`
3. `docker compose -f docker-compose.prod.yml up -d --build --wait` — **il `-f` non è
   opzionale**, terza lezione di `CLAUDE.md`
4. la migrazione `0008` si applica all'avvio, come la `0007`
5. `docker compose -f docker-compose.prod.yml exec backend python -m app.cli.reparse_quantities`
6. `docker compose -f docker-compose.prod.yml exec backend python -m app.cli.decide_units`
7. verifica che il pacchetto servito sia quello nuovo confrontando il nome del bundle
   con quello della build locale — i container «healthy» lo sarebbero anche con il
   pacchetto di ieri
8. a mano, su una ricetta con dosi miste: «Pasta al pomodoro» ha `180 g`, `400 g`,
   `1 spicchio`, `2 cucchiai` e `q.b.` — dose piena, unità contabile e non parsata.
   Per il terzo stato, il numero nudo, serve un'altra ricetta: «Frittata di patate»
   e «Minestrone di verdure» ne hanno.

Fra il passo 4 e il passo 5 le ricette hanno le colonne vuote: il selettore c'è e
scala zero righe, dichiarando che nessuna dose si riscala. È brutto e non è rotto, e
dura il tempo di un comando.
