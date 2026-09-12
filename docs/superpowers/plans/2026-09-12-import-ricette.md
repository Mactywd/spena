# Import massivo di ricette — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** portare centinaia di ricette italiane nel ricettario, scaricandole da
GialloZafferano, senza che l'anagrafica degli ingredienti perda la granularità su
cui si calcola la disponibilità.

**Architecture:** quattro stadi rieseguibili. Un comando scarica le pagine e ne
salva la lettura strutturata in `recipe_imports`; ogni ingrediente distinto della
fonte diventa una riga di `import_terms`; una schermata dell'app decide i termini
con una proposta scritta da Claude; ogni decisione materializza le ricette che
l'aspettavano. La decisione su un termine vive in `ingredient_aliases`, che esiste
già: non c'è una seconda tabella di mappatura.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, Postgres 16, httpx,
beautifulsoup4 (nuova dipendenza), anthropic (`claude-sonnet-5`), React 19 +
TypeScript + Vite, Vitest, pytest su Postgres vero.

**Spec:** `docs/superpowers/specs/2026-09-12-import-ricette-design.md`

## Global Constraints

- **Niente quantità nei calcoli.** `quantity_text` è testo di sola visualizzazione.
- **Ingrediente generico ≠ prodotto specifico.** Le ricette puntano solo a ingredienti.
- **Mai un vicolo cieco.** Ogni guasto di una dipendenza esterna degrada a un
  percorso manuale dichiarato, mai a una schermata d'errore.
- **Nessuna rete nella suite.** Open Food Facts, Claude e GialloZafferano girano
  su fixture registrate o client finti.
- **I test girano su Postgres vero**, avviato da Compose (`vector` e `pg_trgm`).
- **Nessuna schermata nomina un colore.** Tutti i colori vengono dai token del
  blocco `@theme` di `frontend/src/index.css`; le primitive stanno in
  `frontend/src/components/ui/`.
- **Contrasto sopra 4.5:1** per qualunque cosa porti testo bianco.
- **Niente ridistribuzione** del contenuto della fonte: il repository è pubblico,
  quindi le fixture sono ridotte (vedi Task 5) e le ricette vivono solo nel
  database dell'utente.
- **Copy in italiano**, codice e identificatori in inglese. Le etichette esistenti
  non si cambiano: sono anche i nomi con cui si comanda l'app a voce.
- **Una sola implementazione per regola.** Se una logica esiste già altrove, si
  estrae e si chiama; non si copia. Il progetto ha già pagato tre difetti così.
- `ANTHROPIC_API_KEY` assente non è un errore: è una degradazione dichiarata.

## Come leggere i blocchi di codice

Diversi task mostrano codice da aggiungere **in coda** a un file che già esiste, e
quel codice a volte porta import nuovi. **Gli import vanno in testa al file**, con
gli altri, non nel punto in cui il blocco si incolla: `ruff` segnala `E402` e ha
ragione. Dove un blocco mostra `import httpx` o `from sqlalchemy import select`,
spostalo fra gli import esistenti e incolla solo il resto.

---

## Mappa dei file

**Backend, nuovi**

| File | Responsabilità |
|---|---|
| `backend/app/db/models/recipe_import.py` | i due modelli `RecipeImport` e `ImportTerm`, più gli enum dei loro stati |
| `backend/alembic/versions/0004_import_ricette.py` | le due tabelle e le quattro colonne nuove di `recipes` |
| `backend/app/services/ingredient_match.py` | `match_name`: nome grezzo → ingrediente, con la certezza. Unica implementazione |
| `backend/app/services/recipe_import/__init__.py` | pacchetto |
| `backend/app/services/recipe_import/giallozafferano.py` | scarico educato e parsing puro della pagina |
| `backend/app/services/recipe_import/terms.py` | registro dei termini, risoluzione automatica, proposte di Claude |
| `backend/app/services/recipe_import/materialize.py` | da pagina in attesa a `Recipe` vera |
| `backend/app/repositories/imports.py` | interrogazioni sulle due tabelle nuove |
| `backend/app/schemas/recipe_import.py` | schemi Pydantic delle rotte `/imports` |
| `backend/app/api/imports.py` | le quattro rotte |
| `backend/app/cli/import_gz.py` | il comando di scarico |
| `backend/app/cli/reindex.py` | il comando che calcola i vettori mancanti |

**Backend, modificati**

| File | Cosa cambia |
|---|---|
| `backend/app/db/models/recipe.py` | quattro colonne nullabili e l'indice su `category` |
| `backend/app/db/models/__init__.py` | importa i due modelli nuovi |
| `backend/app/domain/rules.py` | `default_role` |
| `backend/app/services/ai_recipes.py` | `_match` sparisce, chiama `match_name` |
| `backend/app/services/recipe_search.py` | filtro categoria e `only_cookable` oltre la piscina |
| `backend/app/api/recipes.py` | il filtro passa alla ricerca, le colonne nuove escono negli schemi |
| `backend/app/schemas/recipe.py` | `image_url`, `prep_minutes`, `cook_minutes`, `category` |
| `backend/app/main.py` | registra il router `imports` |
| `backend/pyproject.toml` | `beautifulsoup4` fra le dipendenze |
| `backend/tests/db/test_metadata_matches_migrations.py` | tre indici nuovi in `MIGRATED_INDEXES` |
| `backend/tests/test_image_dependencies.py` | l'immagine installa anche `beautifulsoup4` |

**Frontend, nuovi**

| File | Responsabilità |
|---|---|
| `frontend/src/features/recipe-import/api.ts` | le quattro chiamate |
| `frontend/src/features/recipe-import/ImportQueueScreen.tsx` | la coda di revisione |
| `frontend/src/features/recipe-import/TermCard.tsx` | una scheda, un termine, tre azioni |

**Frontend, modificati**

| File | Cosa cambia |
|---|---|
| `frontend/src/App.tsx` | rotta `/ricette/importa`, sopra `/ricette/:id` |
| `frontend/src/domain/types.ts` | i tipi dell'import e i quattro campi nuovi di `RecipeSummary` |
| `frontend/src/features/recipes/RecipeBookScreen.tsx` | riga d'ingresso alla coda, filtro per categoria |
| `frontend/src/features/recipes/RecipeCard.tsx` | foto e tempo |
| `frontend/src/features/cooking/RecipeDetailScreen.tsx` | «apri l'originale» |
| `README.md`, `CLAUDE.md` | i due comandi nuovi e le lezioni |

---

## Task 1: le due tabelle e le quattro colonne

**Files:**
- Create: `backend/app/db/models/recipe_import.py`
- Create: `backend/alembic/versions/0004_import_ricette.py`
- Modify: `backend/app/db/models/recipe.py`
- Modify: `backend/app/db/models/__init__.py`
- Modify: `backend/tests/db/test_metadata_matches_migrations.py`
- Test: `backend/tests/db/test_import_schema.py`

**Interfaces:**
- Produces: `RecipeImport`, `ImportTerm`, `ImportState`, `TermDecision`,
  `GIALLOZAFFERANO = "giallozafferano"` da `app.db.models.recipe_import`.
  `Recipe.image_url: str | None`, `Recipe.prep_minutes: int | None`,
  `Recipe.cook_minutes: int | None`, `Recipe.category: str | None`.

Lo spec chiama `key` la colonna del termine. Nel codice è `term_key`: `key` è un
attributo di `Table` in SQLAlchemy e un nome di colonna che lo rispecchia si legge
male in ogni traccia di errore.

- [ ] **Step 1: Scrivi i test dello schema**

`backend/tests/db/test_import_schema.py`:

```python
"""Lo schema dell'import difende da solo le tre cose che il codice non può.

Un termine «collegato» a niente, uno stato inventato e due volte la stessa pagina
sono difetti che arrivano silenziosi: il primo produce ricette con una riga in
meno, cioè una disponibilità calcolata su una ricetta che non è quella scritta.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, RecipeImport


def una_pagina(url: str = "https://ricette.giallozafferano.it/Tiramisu.html") -> RecipeImport:
    return RecipeImport(
        source=GIALLOZAFFERANO, url=url, payload={"title": "Tiramisù"}, state="pending"
    )


async def test_un_termine_collegato_deve_avere_un_ingrediente(db_session):
    db_session.add(
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="ricette-con-i-Rigatoni",
            display_name="Rigatoni", occurrences=3, decision="mapped",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_un_termine_ignorato_non_ha_bisogno_di_ingrediente(db_session):
    db_session.add(
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="ricette-con-Acqua",
            display_name="Acqua", occurrences=7, decision="ignored",
        )
    )
    await db_session.flush()


async def test_una_decisione_inventata_e_rifiutata(db_session):
    db_session.add(
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="ricette-con-il-Burro",
            display_name="Burro", occurrences=1, decision="quasi",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_un_ruolo_corretto_a_mano_puo_solo_essere_uno_dei_due(db_session):
    db_session.add(
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="ricette-con-l-Aglio",
            display_name="Aglio", occurrences=9, decision="pending",
            role_override="accessorio",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_la_stessa_pagina_non_entra_due_volte(db_session):
    db_session.add(una_pagina())
    await db_session.flush()
    db_session.add(una_pagina())
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_uno_stato_inventato_e_rifiutato(db_session):
    pagina = una_pagina("https://ricette.giallozafferano.it/Carbonara.html")
    pagina.state = "quasi-importata"
    db_session.add(pagina)
    with pytest.raises(IntegrityError):
        await db_session.flush()
```

- [ ] **Step 2: Verifica che i test falliscano**

Run: `cd backend && pytest tests/db/test_import_schema.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.db.models.recipe_import'`

- [ ] **Step 3: Scrivi i modelli**

`backend/app/db/models/recipe_import.py`:

```python
"""Le due tabelle dell'import: le pagine scaricate e il dizionario dei termini.

`recipe_imports` è l'area di sosta fra lo scarico e il ricettario, e resta dopo
come registro di ciò che si è preso. `import_terms` è il dizionario dal catalogo
della fonte al nostro: il catalogo di un sito di cucina è più fine di
un'anagrafica fatta per rispondere «ce l'ho in casa?», e colmare quella distanza
è l'unica parte di questo lavoro che non si può automatizzare.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.db.models.base import UUIDMixin

GIALLOZAFFERANO = "giallozafferano"


class ImportState(StrEnum):
    PENDING = "pending"
    IMPORTED = "imported"
    SKIPPED = "skipped"


class TermDecision(StrEnum):
    PENDING = "pending"
    MAPPED = "mapped"
    IGNORED = "ignored"


class RecipeImport(UUIDMixin, Base):
    """Una pagina scaricata, con la sua lettura strutturata.

    Non conserva l'HTML: sull'archivio intero sarebbe mezzo gigabyte, e analizzata
    la pagina non serve più. `payload` tiene anche i valori nutrizionali della
    fonte alla lettera, che nessuno usa oggi: è ciò che permetterà alla fase 3 di
    non riscaricare niente.
    """

    __tablename__ = "recipe_imports"
    __table_args__ = (
        UniqueConstraint("source", "url"),
        CheckConstraint(
            "state IN ('pending', 'imported', 'skipped')", name="ck_recipe_import_state"
        ),
        Index("ix_recipe_imports_state", "state"),
    )

    source: Mapped[str] = mapped_column(String(40))
    url: Mapped[str] = mapped_column(String(500))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    payload: Mapped[dict] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(20), default=ImportState.PENDING)
    skipped_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # SET NULL e non CASCADE: se l'utente cancella una ricetta importata, questa
    # riga deve sopravvivere con state='imported', altrimenti la materializzazione
    # successiva la ricrea e la cancellazione non è mai definitiva. È lo stato, non
    # la presenza della chiave, a dire «già importata una volta».
    recipe_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True
    )


class ImportTerm(UUIDMixin, Base):
    """Un ingrediente del catalogo della fonte, e cosa abbiamo deciso che sia.

    L'identità è la chiave del loro indirizzo, non il nome scritto: il nome cambia
    con un refuso corretto, l'indirizzo no.
    """

    __tablename__ = "import_terms"
    __table_args__ = (
        UniqueConstraint("source", "term_key"),
        CheckConstraint(
            "decision IN ('pending', 'mapped', 'ignored')", name="ck_import_term_decision"
        ),
        CheckConstraint(
            "role_override IS NULL OR role_override IN ('primary', 'secondary')",
            name="ck_import_term_role",
        ),
        # Il vincolo che conta: un termine «collegato» a niente produrrebbe ricette
        # con una riga in meno, e una disponibilità calcolata su una ricetta che non
        # è quella scritta.
        CheckConstraint(
            "decision <> 'mapped' OR ingredient_id IS NOT NULL",
            name="ck_import_term_mapped_has_ingredient",
        ),
        # la coda si legge per decisione e frequenza: è l'unico ordine in cui si
        # revisiona, perché decidere prima i termini frequenti sblocca più ricette
        Index("ix_import_terms_queue", "decision", "occurrences"),
    )

    source: Mapped[str] = mapped_column(String(40))
    term_key: Mapped[str] = mapped_column(String(200))
    display_name: Mapped[str] = mapped_column(String(200))
    # ricalcolato a ogni scarico, mai incrementato: un contatore incrementato
    # divergerebbe al primo ri-scarico, e un ordinamento della coda basato su un
    # numero sbagliato è un difetto che nessuno nota
    occurrences: Mapped[int] = mapped_column(Integer, default=0)
    decision: Mapped[str] = mapped_column(String(20), default=TermDecision.PENDING)
    ingredient_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=True
    )
    # la deduzione del ruolo sbaglia dove il buon senso culinario non segue la
    # categoria: l'aglio è verdura e quasi sempre secondario. Sta qui e non su
    # `ingredients` perché è una correzione alla deduzione dell'import, non una
    # proprietà dell'ingrediente.
    role_override: Mapped[str | None] = mapped_column(String(20), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(20), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

- [ ] **Step 4: Aggiungi le quattro colonne a `Recipe`**

In `backend/app/db/models/recipe.py`, dentro `__table_args__` di `Recipe` aggiungi
l'indice, e dopo `source_ref` le colonne:

```python
        Index("ix_recipes_category", "category"),
```

```python
    # Arrivano dall'import (spec §6.3) e restano nulle per le ricette scritte a mano
    # e per quelle dell'AI, che non le hanno e non le avranno.
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    prep_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cook_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # testo libero e non enum: la tassonomia è della fonte, e un enum costringerebbe
    # a una migrazione il giorno che aggiungono una voce
    category: Mapped[str | None] = mapped_column(String(60), nullable=True)
```

- [ ] **Step 5: Registra i modelli nuovi**

In `backend/app/db/models/__init__.py` aggiungi l'import e le due voci di `__all__`:

```python
from app.db.models.recipe_import import ImportTerm, RecipeImport
```

- [ ] **Step 6: Scrivi la migrazione**

`backend/alembic/versions/0004_import_ricette.py`:

```python
"""import ricette: pagine scaricate, dizionario dei termini, colonne nuove

Revision ID: 0004
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"


def upgrade() -> None:
    op.add_column("recipes", sa.Column("image_url", sa.String(500)))
    op.add_column("recipes", sa.Column("prep_minutes", sa.Integer))
    op.add_column("recipes", sa.Column("cook_minutes", sa.Integer))
    op.add_column("recipes", sa.Column("category", sa.String(60)))
    op.create_index("ix_recipes_category", "recipes", ["category"])

    op.create_table(
        "recipe_imports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
                  nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("skipped_reason", sa.String(200)),
        sa.Column("recipe_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("recipes.id", ondelete="SET NULL")),
        sa.UniqueConstraint("source", "url"),
        sa.CheckConstraint("state IN ('pending', 'imported', 'skipped')",
                           name="ck_recipe_import_state"),
    )
    op.create_index("ix_recipe_imports_state", "recipe_imports", ["state"])

    op.create_table(
        "import_terms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("term_key", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("occurrences", sa.Integer, nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("ingredient_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("ingredients.id", ondelete="RESTRICT")),
        sa.Column("role_override", sa.String(20)),
        sa.Column("decided_by", sa.String(20)),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("source", "term_key"),
        sa.CheckConstraint("decision IN ('pending', 'mapped', 'ignored')",
                           name="ck_import_term_decision"),
        sa.CheckConstraint("role_override IS NULL OR role_override IN ('primary', 'secondary')",
                           name="ck_import_term_role"),
        sa.CheckConstraint("decision <> 'mapped' OR ingredient_id IS NOT NULL",
                           name="ck_import_term_mapped_has_ingredient"),
    )
    op.create_index("ix_import_terms_queue", "import_terms", ["decision", "occurrences"])


def downgrade() -> None:
    op.drop_table("import_terms")
    op.drop_table("recipe_imports")
    op.drop_index("ix_recipes_category", table_name="recipes")
    for colonna in ("category", "cook_minutes", "prep_minutes", "image_url"):
        op.drop_column("recipes", colonna)
```

- [ ] **Step 7: Dichiara i tre indici nuovi**

In `backend/tests/db/test_metadata_matches_migrations.py`, dentro `MIGRATED_INDEXES`,
in ordine alfabetico:

```python
    "ix_import_terms_queue",
    "ix_recipe_imports_state",
    "ix_recipes_category",
```

Quel file contiene un test che fallisce se i modelli e lo schema divergono: è la
ragione per cui la migrazione va scritta a mano e identica ai modelli.

- [ ] **Step 8: Esegui i test**

Run: `cd backend && pytest tests/db -v`
Expected: PASS, compresi i tre test di `test_metadata_matches_migrations.py`. Se
`test_models_describe_the_migrated_schema` fallisce, la differenza che stampa dice
esattamente dove modello e migrazione non coincidono.

- [ ] **Step 9: Commit**

```bash
git add backend/app/db/models/recipe_import.py backend/app/db/models/recipe.py \
        backend/app/db/models/__init__.py backend/alembic/versions/0004_import_ricette.py \
        backend/tests/db/test_import_schema.py \
        backend/tests/db/test_metadata_matches_migrations.py
git commit -m "feat: le tabelle dell'import, e il vincolo che impedisce una ricetta incompleta"
```

---

## Task 2: la deduzione del ruolo

**Files:**
- Modify: `backend/app/domain/rules.py`
- Test: `backend/tests/domain/test_rules.py`

**Interfaces:**
- Produces: `default_role(category: str, quantity_text: str | None) -> IngredientRole`
  e `SECONDARY_CATEGORIES: frozenset[str]` da `app.domain.rules`.

Il ruolo è ciò che rende utile lo stato «quasi finito», e la fonte non ce lo dà. Si
deduce da due segnali che i dati hanno davvero: la dose «q.b.» e la categoria.

- [ ] **Step 1: Scrivi i test**

In coda a `backend/tests/domain/test_rules.py`:

```python
import pytest

from app.db.models.ingredient import IngredientCategory
from app.domain.rules import SECONDARY_CATEGORIES, IngredientRole, default_role


@pytest.mark.parametrize(
    "category, quantity, expected",
    [
        # la dose decide da sola: «q.b.» vuol dire che si aggiusta a piacere
        ("cereali", "q.b.", IngredientRole.SECONDARY),
        ("cereali", "qb", IngredientRole.SECONDARY),
        ("cereali", "q.b. (circa due cucchiai)", IngredientRole.SECONDARY),
        ("cereali", "a piacere", IngredientRole.SECONDARY),
        ("cereali", "quanto basta", IngredientRole.SECONDARY),
        # la categoria decide da sola: spezie e condimenti si riducono senza
        # snaturare il piatto, anche quando la dose è precisa
        ("spezie", "2 foglie", IngredientRole.SECONDARY),
        ("condimenti", "2 cucchiai", IngredientRole.SECONDARY),
        # tutto il resto con una dose vera è principale
        ("cereali", "320 g", IngredientRole.PRIMARY),
        ("carne", "80 g", IngredientRole.PRIMARY),
        ("latticini", "100 g", IngredientRole.PRIMARY),
        ("verdura", "1 spicchio", IngredientRole.PRIMARY),
        # dose assente non è dose «q.b.»: non si inventa un secondario
        ("verdura", None, IngredientRole.PRIMARY),
        ("verdura", "", IngredientRole.PRIMARY),
    ],
)
def test_default_role(category, quantity, expected):
    assert default_role(category, quantity) is expected


def test_ogni_categoria_e_decisa(category=None):
    """Nessuna categoria dell'anagrafica resta senza risposta."""
    for value in IngredientCategory:
        assert default_role(value, "100 g") in tuple(IngredientRole)


def test_le_categorie_secondarie_esistono_in_anagrafica():
    """`rules.py` è puro e non importa i modelli: le due stringhe potrebbero
    diventare nomi di categorie che non esistono più, e la deduzione smetterebbe
    di funzionare senza che nessun test se ne accorga."""
    assert SECONDARY_CATEGORIES <= {str(value) for value in IngredientCategory}
```

- [ ] **Step 2: Verifica che i test falliscano**

Run: `cd backend && pytest tests/domain/test_rules.py -v`
Expected: FAIL con `ImportError: cannot import name 'default_role'`

- [ ] **Step 3: Implementa**

In `backend/app/domain/rules.py`, dopo `import re` in testa al file e in coda al modulo:

```python
# Le categorie i cui ingredienti si riducono senza snaturare il piatto. Sono valori
# di IngredientCategory, scritti come stringhe perché questo modulo è puro e non
# importa i modelli; un test del dominio li confronta con l'enum per impedire
# che diventino nomi di categorie che non esistono più.
SECONDARY_CATEGORIES = frozenset({"spezie", "condimenti"})


def default_role(category: str, quantity_text: str | None) -> IngredientRole:
    """Il ruolo dedotto per una riga di ricetta importata.

    La fonte non dichiara i ruoli, e il ruolo è ciò che rende utile lo stato «quasi
    finito»: un pomodoro agli sgoccioli non fa una pasta al pomodoro ma fa un
    soffritto. Due segnali, entrambi presenti nei dati veri: una dose «quanto
    basta» dice che l'ingrediente si aggiusta a piacere, e spezie e condimenti lo
    sono per natura.

    Dove il buon senso culinario non segue la categoria — l'aglio è verdura e quasi
    sempre secondario — la correzione arriva da `ImportTerm.role_override`, deciso
    una volta sola dalla persona che revisiona il termine.
    """
    compact = re.sub(r"[\s.]+", "", (quantity_text or "").lower())
    if compact.startswith("qb") or compact in {"apiacere", "quantobasta"}:
        return IngredientRole.SECONDARY
    if category in SECONDARY_CATEGORIES:
        return IngredientRole.SECONDARY
    return IngredientRole.PRIMARY
```

- [ ] **Step 4: Esegui i test**

Run: `cd backend && pytest tests/domain -v`
Expected: PASS

- [ ] **Step 5: Prova di mutazione**

Cambia `compact.startswith("qb")` in `compact == "qb"` e riesegui: deve fallire il
solo caso `"q.b. (circa due cucchiai)"`. Rimetti come prima. Un test che non
sopravvive a questa prova non difende niente.

- [ ] **Step 6: Commit**

```bash
git add backend/app/domain/rules.py backend/tests/domain/test_rules.py
git commit -m "feat: il ruolo dedotto da dose e categoria, con la sua tavola di casi"
```

---

## Task 3: una sola funzione di aggancio

**Files:**
- Create: `backend/app/services/ingredient_match.py`
- Modify: `backend/app/services/ai_recipes.py`
- Test: `backend/tests/services/test_ingredient_match.py`

**Interfaces:**
- Consumes: `search_ingredients(session, query, limit)` da `app.repositories.ingredients`.
- Produces: `NameMatch(ingredient_id: uuid.UUID | None, name: str | None, certain: bool)`
  e `async def match_name(session, raw_name: str) -> NameMatch` da
  `app.services.ingredient_match`.

La logica «nome grezzo → ingrediente, e quanto mi fido» esiste già dentro
`ai_recipes._match`. Non va copiata: va estratta, e la stesura AI diventa un suo
chiamante. CLAUDE.md: un test che difende una copia che nessuno chiama non difende
niente, ed è già costato tre difetti a questo progetto.

Nell'estrazione la certezza si allarga a un fatto che oggi manca: anche la
coincidenza esatta con un **alias** è certa. Oggi `pomodori pelati`, che è un alias
esplicito di `pomodoro` nel seme, viene marcato incerto e chiede una conferma
inutile.

- [ ] **Step 1: Scrivi i test**

`backend/tests/services/test_ingredient_match.py`:

```python
import pytest_asyncio

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.services.ingredient_match import match_name


@pytest_asyncio.fixture
async def anagrafica(db_session):
    pomodoro = Ingredient(
        name="pomodoro", display_name="Pomodoro", category=IngredientCategory.VERDURA
    )
    pomodoro.aliases.append(IngredientAlias(alias="pomodori pelati", source="import"))
    db_session.add(pomodoro)
    db_session.add(
        Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
    )
    await db_session.flush()


async def test_il_nome_canonico_esatto_e_certo(db_session, anagrafica):
    match = await match_name(db_session, "Pomodoro")
    assert match.name == "pomodoro"
    assert match.certain is True


async def test_un_alias_esatto_e_certo(db_session, anagrafica):
    """Era il difetto dell'implementazione precedente: un alias scritto da noi
    veniva proposto come incerto, e chiedeva una conferma che non serve."""
    match = await match_name(db_session, "Pomodori pelati")
    assert match.name == "pomodoro"
    assert match.certain is True


async def test_una_somiglianza_si_propone_ma_resta_incerta(db_session, anagrafica):
    match = await match_name(db_session, "pomodorini")
    assert match.name == "pomodoro"
    assert match.certain is False


async def test_niente_di_somigliante_non_e_un_aggancio(db_session, anagrafica):
    match = await match_name(db_session, "bottarga di muggine")
    assert match.ingredient_id is None
    assert match.name is None
    assert match.certain is False


async def test_la_stesura_ai_usa_questa_funzione(db_session, anagrafica, monkeypatch):
    """Il punto di questo task: non deve esistere una seconda implementazione.

    Se `draft_recipe` tornasse a calcolarsi l'aggancio da sé, questo test resta
    verde mentre ogni garanzia qui sopra difende codice che nessuno chiama.
    """
    import app.services.ai_recipes as ai_recipes

    chiamate: list[str] = []
    originale = ai_recipes.match_name

    async def spia(session, raw_name):
        chiamate.append(raw_name)
        return await originale(session, raw_name)

    monkeypatch.setattr(ai_recipes, "match_name", spia)

    class FakeClaude:
        def __init__(self) -> None:
            self.messages = self

        async def create(self, **_kwargs):
            import json

            class Block:
                text = json.dumps(
                    {
                        "title": "Pasta al pomodoro",
                        "description": "",
                        "instructions": "Cuoci.",
                        "servings": 2,
                        "ingredients": [
                            {"name": "pasta", "role": "primary", "quantity_text": "200 g"}
                        ],
                    }
                )

            class Response:
                content = [Block()]

            return Response()

    await ai_recipes.draft_recipe(db_session, "qualcosa", client=FakeClaude())
    assert chiamate == ["pasta"]
```

- [ ] **Step 2: Verifica che i test falliscano**

Run: `cd backend && pytest tests/services/test_ingredient_match.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.services.ingredient_match'`

- [ ] **Step 3: Scrivi il modulo**

`backend/app/services/ingredient_match.py`:

```python
"""Nome grezzo → ingrediente dell'anagrafica, con quanto ci si fida.

Unica implementazione nell'applicazione. La usano la stesura AI, per agganciare gli
ingredienti che Claude propone, e l'import, per decidere da sé i termini che
coincidono con qualcosa che già conosciamo. Due copie di questa regola si
scollerebbero, e la prima a scollarsi sarebbe la definizione di «certo»: da lì
passa la differenza fra un aggancio applicato in silenzio e uno che chiede
conferma.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingredient import Ingredient, IngredientAlias
from app.repositories.ingredients import search_ingredients


@dataclass(frozen=True)
class NameMatch:
    ingredient_id: uuid.UUID | None
    name: str | None
    certain: bool


async def match_name(session: AsyncSession, raw_name: str) -> NameMatch:
    """La certezza richiede una coincidenza esatta, col nome canonico o con un alias.

    L'uguaglianza non è una proposta, è un fatto, e non ha bisogno di conferma.
    Tutto il resto si propone e si marca incerto, perché un ingrediente sbagliato
    in silenzio avvelena la disponibilità di tutte le ricette che lo usano.
    """
    normalized = raw_name.strip().lower()
    if not normalized:
        return NameMatch(None, None, False)

    # prima la coincidenza esatta, che non dipende dalla somiglianza trigram e non
    # può essere scavalcata da un candidato più "frequente"
    exact = (
        await session.execute(
            select(Ingredient)
            .outerjoin(IngredientAlias, IngredientAlias.ingredient_id == Ingredient.id)
            .where((Ingredient.name == normalized) | (IngredientAlias.alias == normalized))
            .limit(1)
        )
    ).unique().scalar_one_or_none()
    if exact is not None:
        return NameMatch(exact.id, exact.name, True)

    candidates = await search_ingredients(session, raw_name, limit=1)
    if not candidates:
        return NameMatch(None, None, False)
    best = candidates[0]
    return NameMatch(best.id, best.name, False)
```

- [ ] **Step 4: Fai chiamare la funzione alla stesura AI**

In `backend/app/services/ai_recipes.py`: cancella `_match` per intero, aggiungi
l'import `from app.services.ingredient_match import match_name`, e sostituisci la
riga che lo chiamava dentro `draft_recipe`:

```python
        match = await match_name(session, raw_name)
        ingredients.append(
            DraftIngredient(
                raw_name=raw_name, role=role,
                quantity_text=entry.get("quantity_text") or None,
                ingredient_id=match.ingredient_id, matched_name=match.name,
                confident=match.certain,
            )
        )
```

L'import di `search_ingredients` in `ai_recipes.py` resta solo se qualcos'altro lo
usa: se diventa inutilizzato, togli anche quello, o `ruff` lo segnala.

- [ ] **Step 5: Esegui tutta la suite dei servizi**

Run: `cd backend && pytest tests/services -v`
Expected: PASS. L'allargamento della certezza agli alias può far cadere
un'asserzione esistente in `tests/services/test_ai_recipes.py`: se un test dà per
incerto un nome che è un alias esatto, **il test va corretto**, perché l'alias
esatto è certo per decisione di questo task. Scrivi il perché nel commento del
test, non nel messaggio di commit.

- [ ] **Step 6: Prova di mutazione**

Togli il ramo della coincidenza esatta (lascia solo `search_ingredients`) e
riesegui: devono fallire `test_il_nome_canonico_esatto_e_certo` e
`test_un_alias_esatto_e_certo`, e nient'altro. Rimetti come prima.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/ingredient_match.py backend/app/services/ai_recipes.py \
        backend/tests/services/test_ingredient_match.py backend/tests/services/test_ai_recipes.py
git commit -m "refactor: un solo aggancio nome-ingrediente, e un alias esatto è certo"
```

---

## Task 4: la pulizia dei passaggi

**Files:**
- Create: `backend/app/services/recipe_import/__init__.py`
- Create: `backend/app/services/recipe_import/giallozafferano.py`
- Test: `backend/tests/services/test_giallozafferano_steps.py`

**Interfaces:**
- Produces, da `app.services.recipe_import.giallozafferano`:
  `normalize_steps(raw: object) -> list[str]`,
  `strip_photo_references(text: str) -> str`,
  `clean_instructions(raw: object) -> str`.

I passaggi della fonte contengono i rimandi numerici alle fotografie, come numeri
isolati prima della punteggiatura: «rosolare lo speck per circa 5 minuti 2 .». Una
ricetta si legge mentre si cucina, quindi vanno via. La regola è **stretta**: il
numero deve essere separato da spazi da entrambi i lati. «Dividi l'impasto in 4.»
non ha lo spazio prima del punto, e non deve cambiare.

- [ ] **Step 1: Scrivi i test**

`backend/tests/services/test_giallozafferano_steps.py`:

```python
import pytest

from app.services.recipe_import.giallozafferano import (
    clean_instructions,
    normalize_steps,
    strip_photo_references,
)


@pytest.mark.parametrize(
    "testo, atteso",
    [
        # i casi veri, copiati dalla forma che la fonte produce
        (
            "Lasciate rosolare lo speck per circa 5 minuti 2 .",
            "Lasciate rosolare lo speck per circa 5 minuti.",
        ),
        ("Riducetele a striscioline di circa 1 cm 1 .", "Riducetele a striscioline di circa 1 cm."),
        ("Di tanto in tanto mescolate 3", "Di tanto in tanto mescolate"),
        ("Unite il Parmigiano grattugiato 7 , poi mescolate.",
         "Unite il Parmigiano grattugiato, poi mescolate."),
        # più rimandi di fila
        ("Versate il latte e mescolate 6 7 .", "Versate il latte e mescolate."),
        # lo spazio insecabile che la fonte usa davvero
        ("Mettetelo da parte 4 .\xa0", "Mettetelo da parte."),
        # i casi che NON devono cambiare: è qui che una regola generosa fa danni
        ("Dividete l'impasto in 4.", "Dividete l'impasto in 4."),
        ("Cuocete per 10 minuti, poi scolate.", "Cuocete per 10 minuti, poi scolate."),
        ("Aggiungete 2 uova intere.", "Aggiungete 2 uova intere."),
        ("Infornate a 180 °C.", "Infornate a 180 °C."),
    ],
)
def test_strip_photo_references(testo, atteso):
    assert strip_photo_references(testo) == atteso


def test_normalize_steps_accetta_una_lista_di_stringhe():
    assert normalize_steps(["Primo.", "Secondo."]) == ["Primo.", "Secondo."]


def test_normalize_steps_accetta_gli_oggetti_howtostep():
    raw = [
        {"@type": "HowToStep", "text": "Primo."},
        {"@type": "HowToStep", "text": "Secondo."},
    ]
    assert normalize_steps(raw) == ["Primo.", "Secondo."]


def test_normalize_steps_accetta_una_stringa_sola():
    assert normalize_steps("Tutto in un paragrafo.") == ["Tutto in un paragrafo."]


def test_normalize_steps_su_niente_non_esplode():
    assert normalize_steps(None) == []
    assert normalize_steps([]) == []


def test_clean_instructions_unisce_i_passaggi_con_una_riga_vuota():
    raw = ["Scaldate l'olio 1 .", "Unite i pomodori 2 .", "   "]
    assert clean_instructions(raw) == "Scaldate l'olio.\n\nUnite i pomodori."
```

- [ ] **Step 2: Verifica che i test falliscano**

Run: `cd backend && pytest tests/services/test_giallozafferano_steps.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.services.recipe_import'`

- [ ] **Step 3: Crea il pacchetto e le tre funzioni**

`backend/app/services/recipe_import/__init__.py`: file vuoto.

`backend/app/services/recipe_import/giallozafferano.py` (prima parte del file; il
parsing arriva nel Task 5 e lo scarico nel Task 6):

```python
"""Lettura di una pagina di ricetta di GialloZafferano.

Il parsing è puro: prende il testo della pagina e non sa da dove arriva. È quel che
permetterà al futuro «incolla un link» di riusarlo senza modifiche.

Perché non serve nessun modello linguistico: la pagina porta un blocco
schema.org/Recipe, e nel corpo tiene il nome dell'ingrediente e la quantità in due
elementi separati, con un indirizzo stabile per ogni ingrediente del loro catalogo.
Il nome non va estratto da una stringa: è un elemento.
"""

import re

# Un rimando fotografico è un numero isolato da spazi su entrambi i lati, prima
# della punteggiatura o a fine paragrafo. Lo spazio a sinistra **e** a destra è ciò
# che distingue «per 5 minuti 2 .» da «dividete l'impasto in 4.»: la seconda è
# prosa, e una regola più generosa la mangerebbe.
PHOTO_REFERENCES_BEFORE_PUNCTUATION = re.compile(r"(?:\s\d{1,2})+\s+(?=[.,;:])")
PHOTO_REFERENCES_AT_END = re.compile(r"(?:\s\d{1,2})+\s*$")


def strip_photo_references(text: str) -> str:
    """Via i rimandi alle fotografie, che qui non ci sono."""
    cleaned = text.replace("\xa0", " ")
    cleaned = PHOTO_REFERENCES_BEFORE_PUNCTUATION.sub("", cleaned)
    cleaned = PHOTO_REFERENCES_AT_END.sub("", cleaned)
    return cleaned.strip()


def normalize_steps(raw: object) -> list[str]:
    """`recipeInstructions` arriva in tre forme, e tutte e tre sono nei dati veri.

    Lista di paragrafi, lista di oggetti `HowToStep` con il testo dentro, o una
    stringa sola. Una forma non gestita non solleverebbe niente: produrrebbe una
    ricetta senza procedimento, che è peggio.
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        steps: list[str] = []
        for entry in raw:
            if isinstance(entry, str):
                steps.append(entry)
            elif isinstance(entry, dict) and isinstance(entry.get("text"), str):
                steps.append(entry["text"])
        return steps
    return []


def clean_instructions(raw: object) -> str:
    """I passaggi ripuliti, uniti da una riga vuota."""
    steps = [strip_photo_references(step) for step in normalize_steps(raw)]
    return "\n\n".join(step for step in steps if step)
```

- [ ] **Step 4: Esegui i test**

Run: `cd backend && pytest tests/services/test_giallozafferano_steps.py -v`
Expected: PASS, 16 casi

- [ ] **Step 5: Prova di mutazione**

Cambia `\s+(?=[.,;:])` in `\s*(?=[.,;:])` e riesegui: deve fallire il solo caso
«Dividete l'impasto in 4.». È la prova che il test difende la strettezza della
regola, non solo il caso facile. Rimetti come prima.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/recipe_import backend/tests/services/test_giallozafferano_steps.py
git commit -m "feat: i passaggi senza i rimandi alle foto, con i casi che non devono cambiare"
```

---

## Task 5: il parser della pagina

**Files:**
- Modify: `backend/app/services/recipe_import/giallozafferano.py`
- Modify: `backend/pyproject.toml`
- Modify: `backend/tests/test_image_dependencies.py`
- Create: `backend/tests/fixtures/giallozafferano/semplice.html`
- Create: `backend/tests/fixtures/giallozafferano/gruppi.html`
- Create: `backend/tests/fixtures/giallozafferano/senza-jsonld.html`
- Test: `backend/tests/services/test_giallozafferano_parse.py`

**Interfaces:**
- Consumes: `clean_instructions` dal Task 4.
- Produces, da `app.services.recipe_import.giallozafferano`:
  `UnparsablePage(Exception)` con attributo `reason: str`,
  `ParsedIngredient(key: str, name: str, quantity_text: str | None)`,
  `ParsedRecipe` con i campi `title, description, instructions, servings, category,
  image_url, prep_minutes, cook_minutes, ingredients, nutrition` e il metodo
  `as_payload() -> dict`,
  `parse_recipe(html: str) -> ParsedRecipe`.

**Le fixture sono ridotte, e il perché va scritto dentro ognuna.** Il repository è
pubblico: salvare tre pagine intere ripubblicherebbe i loro articoli, che è ciò che
lo spec §3 promette di non fare. La struttura attorno alle parti che il parser legge
è conservata alla lettera; la prosa lunga è accorciata a una frase per passo,
tenendo i rimandi fotografici perché sono ciò che il pulitore deve togliere.

- [ ] **Step 1: Scrivi la fixture semplice**

`backend/tests/fixtures/giallozafferano/semplice.html`:

```html
<!-- Fixture ridotta da https://ricette.giallozafferano.it/Pasta-con-crema-di-Parmigiano-e-speck.html
     Il repository è pubblico: la struttura che il parser legge è conservata alla
     lettera, la prosa dei passaggi è accorciata a una frase ciascuno. Non è una
     pagina da ripubblicare, è lo scheletro che il parser deve sapere leggere. -->
<!DOCTYPE html>
<html lang="it">
<head>
<title>Pasta con crema di Parmigiano e speck</title>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Recipe",
  "name": "Pasta con crema di Parmigiano e speck",
  "description": "Un primo piatto cremoso e saporito, molto facile da preparare.",
  "recipeCategory": "Primi piatti",
  "recipeYield": 4,
  "prepTime": "PT10M",
  "cookTime": "PT15M",
  "totalTime": "PT25M",
  "image": "https://www.giallozafferano.it/images/0-0/pasta-crema-parmigiano.jpg",
  "recipeIngredient": ["Rigatoni 320 g", "Speck a fette 80 g"],
  "recipeInstructions": [
    "Riducete lo speck a striscioline di circa 1 cm 1 .",
    "Lasciate rosolare a fiamma viva per circa 5 minuti 2 .",
    "Versate il latte e unite il Parmigiano grattugiato 7 ."
  ],
  "nutrition": {
    "@type": "NutritionInformation",
    "calories": "464,4 kcal",
    "carbohydrateContent": "63,1 g",
    "fatContent": "10,7 g"
  }
}
</script>
<script type="application/ld+json">
{"@context": "https://schema.org", "@type": "Organization", "name": "GialloZafferano"}
</script>
</head>
<body>
<div class="gz-ingredients gz-outer">
  <div class="gz-head-ingredients"><h2 class="gz-title-section">INGREDIENTI</h2></div>
  <dl class="gz-list-ingredients">
    <dd class="gz-ingredient">
      <a href="/ricette-con-i-Rigatoni/" title="Ricette con i Rigatoni">Rigatoni</a>
      <span> 320 g </span>
    </dd>
    <dd class="gz-ingredient">
      <a href="/ricette-con-lo-Speck/" title="Ricette con lo Speck">Speck</a>
      <span> a fette 80 g </span>
    </dd>
    <dd class="gz-ingredient">
      <a href="/ricette-con-Pepe-nero/" title="Ricette con Pepe nero">Pepe nero</a>
      <span> q.b. </span>
    </dd>
  </dl>
</div>
</body>
</html>
```

- [ ] **Step 2: Scrivi la fixture con i gruppi**

`backend/tests/fixtures/giallozafferano/gruppi.html`:

```html
<!-- Fixture ridotta da https://ricette.giallozafferano.it/Torta-della-nonna.html
     (sulla riduzione, vedi il commento di semplice.html). Questa pagina porta le
     tre cose difficili che i dati veri hanno: gli ingredienti divisi in gruppi, lo
     stesso termine due volte nella stessa ricetta, e le entità HTML nelle dosi.
     Una riga è senza link di proposito: il loro catalogo non copre tutto. -->
<!DOCTYPE html>
<html lang="it">
<head>
<title>Torta della nonna</title>
<script type="application/ld+json">
[
  {
    "@context": "https://schema.org",
    "@type": "Recipe",
    "name": "Torta della nonna",
    "description": "Pasta frolla, crema e pinoli.",
    "recipeCategory": "Dolci e Desserts",
    "recipeYield": "10 porzioni",
    "prepTime": "PT40M",
    "cookTime": "PT60M",
    "image": {"@type": "ImageObject", "url": "https://www.giallozafferano.it/images/torta-della-nonna.jpg"},
    "recipeInstructions": [
      {"@type": "HowToStep", "text": "Lavorate la farina con il burro freddo 1 ."},
      {"@type": "HowToStep", "text": "Stendete la frolla nello stampo 5 ."}
    ],
    "nutrition": {"@type": "NutritionInformation", "calories": "583,4 kcal"}
  }
]
</script>
</head>
<body>
<div class="gz-ingredients gz-outer">
  <dl class="gz-list-ingredients">
    <dt class="gz-title-ingredients gz-uppercase">Per la pasta frolla</dt>
    <dd class="gz-ingredient">
      <a href="/ricette-con-la-Farina-00/" title="Ricette con la Farina 00">Farina 00</a>
      <span> 500 g </span>
    </dd>
    <dd class="gz-ingredient">
      <a href="/ricette-con-Zucchero-a-velo/" title="Ricette con Zucchero a velo">Zucchero a velo</a>
      <span> 150 g </span>
    </dd>
    <dd class="gz-ingredient">
      <a href="/ricette-con-Scorza-di-limone/" title="Ricette con Scorza di limone">Scorza di limone</a>
      <span> non trattato &frac12; </span>
    </dd>
    <dt class="gz-title-ingredients gz-uppercase">Per la crema</dt>
    <dd class="gz-ingredient">
      <a href="/ricette-con-Latte-intero/" title="Ricette con Latte intero">Latte intero</a>
      <span> 500 g </span>
    </dd>
    <dd class="gz-ingredient">
      <a href="/ricette-con-Zucchero-a-velo/" title="Ricette con Zucchero a velo">Zucchero a velo</a>
      <span> q.b. </span>
    </dd>
    <dd class="gz-ingredient">
      Amido di riso <span> 20 g </span>
    </dd>
  </dl>
</div>
</body>
</html>
```

- [ ] **Step 3: Scrivi la fixture senza dati strutturati**

`backend/tests/fixtures/giallozafferano/senza-jsonld.html`:

```html
<!-- Fixture costruita a mano: una pagina con l'elenco degli ingredienti ma senza
     il blocco schema.org/Recipe. Succede sulle pagine che non sono ricette, e sulle
     ricette vecchie. Deve finire in `skipped` con un motivo leggibile, non sparire. -->
<!DOCTYPE html>
<html lang="it">
<head><title>Una pagina che non è una ricetta</title></head>
<body>
<div class="gz-ingredients gz-outer">
  <dl class="gz-list-ingredients">
    <dd class="gz-ingredient">
      <a href="/ricette-con-il-Burro/" title="Ricette con il Burro">Burro</a>
      <span> 100 g </span>
    </dd>
  </dl>
</div>
</body>
</html>
```

- [ ] **Step 4: Scrivi i test del parser**

`backend/tests/services/test_giallozafferano_parse.py`:

```python
from pathlib import Path

import pytest

from app.services.recipe_import.giallozafferano import UnparsablePage, parse_recipe

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "giallozafferano"


def fixture(name: str) -> str:
    return (FIXTURES / f"{name}.html").read_text(encoding="utf-8")


def test_legge_i_campi_dal_blocco_strutturato():
    recipe = parse_recipe(fixture("semplice"))

    assert recipe.title == "Pasta con crema di Parmigiano e speck"
    assert recipe.description.startswith("Un primo piatto cremoso")
    assert recipe.servings == 4
    assert recipe.category == "Primi piatti"
    assert recipe.prep_minutes == 10
    assert recipe.cook_minutes == 15
    assert recipe.image_url.endswith("pasta-crema-parmigiano.jpg")


def test_i_rimandi_alle_foto_non_arrivano_nel_procedimento():
    recipe = parse_recipe(fixture("semplice"))

    assert " 1 ." not in recipe.instructions
    assert recipe.instructions.startswith("Riducetele a striscioline di circa 1 cm.")
    assert recipe.instructions.count("\n\n") == 2


def test_gli_ingredienti_arrivano_con_chiave_nome_e_dose():
    recipe = parse_recipe(fixture("semplice"))

    assert [i.key for i in recipe.ingredients] == [
        "ricette-con-i-Rigatoni",
        "ricette-con-lo-Speck",
        "ricette-con-Pepe-nero",
    ]
    assert [i.name for i in recipe.ingredients] == ["Rigatoni", "Speck", "Pepe nero"]
    assert [i.quantity_text for i in recipe.ingredients] == ["320 g", "a fette 80 g", "q.b."]


def test_i_valori_nutrizionali_si_conservano_alla_lettera():
    """Nessuno li usa oggi: sono ciò che permette alla fase 3 di non riscaricare."""
    recipe = parse_recipe(fixture("semplice"))

    assert recipe.nutrition["calories"] == "464,4 kcal"


def test_i_gruppi_non_perdono_righe_e_le_entita_si_decodificano():
    recipe = parse_recipe(fixture("gruppi"))

    assert len(recipe.ingredients) == 6
    scorza = next(i for i in recipe.ingredients if i.name == "Scorza di limone")
    assert scorza.quantity_text == "non trattato ½"


def test_lo_stesso_termine_puo_comparire_due_volte():
    """Il parser non collassa niente: è la materializzazione a farlo, perché è lei
    a conoscere l'ingrediente su cui le due righe finiscono."""
    recipe = parse_recipe(fixture("gruppi"))

    chiavi = [i.key for i in recipe.ingredients]
    assert chiavi.count("ricette-con-Zucchero-a-velo") == 2


def test_una_riga_senza_link_ha_comunque_una_chiave():
    recipe = parse_recipe(fixture("gruppi"))

    amido = next(i for i in recipe.ingredients if i.name == "Amido di riso")
    assert amido.key == "testo:amido di riso"
    assert amido.quantity_text == "20 g"


def test_le_porzioni_scritte_a_parole_si_leggono():
    assert parse_recipe(fixture("gruppi")).servings == 10


def test_il_blocco_dentro_una_lista_si_trova():
    """Il JSON-LD della fonte a volte è un oggetto, a volte una lista."""
    assert parse_recipe(fixture("gruppi")).title == "Torta della nonna"


def test_i_passaggi_a_oggetti_howtostep_si_leggono():
    instructions = parse_recipe(fixture("gruppi")).instructions

    assert instructions.startswith("Lavorate la farina con il burro freddo.")
    assert "Stendete la frolla nello stampo." in instructions


def test_una_pagina_senza_blocco_strutturato_dice_perche():
    with pytest.raises(UnparsablePage) as errore:
        parse_recipe(fixture("senza-jsonld"))

    assert "schema.org" in errore.value.reason


def test_una_pagina_senza_ingredienti_dice_perche():
    html = fixture("semplice").replace('class="gz-ingredient"', 'class="niente"')

    with pytest.raises(UnparsablePage) as errore:
        parse_recipe(html)

    assert "ingredient" in errore.value.reason


def test_il_payload_e_serializzabile_in_json():
    import json

    payload = parse_recipe(fixture("semplice")).as_payload()

    assert json.loads(json.dumps(payload))["ingredients"][0]["key"] == "ricette-con-i-Rigatoni"
```

- [ ] **Step 5: Verifica che i test falliscano**

Run: `cd backend && pytest tests/services/test_giallozafferano_parse.py -v`
Expected: FAIL con `ImportError: cannot import name 'UnparsablePage'`

- [ ] **Step 6: Aggiungi la dipendenza**

In `backend/pyproject.toml`, fra le `dependencies` del progetto (non fra gli extra:
il parser è codice di base, non una funzione opzionale), in ordine alfabetico:

```toml
  "beautifulsoup4>=4.12",
```

Senza `lxml`: è compilato, pesa, e qui il parser della libreria standard basta.
Installa in locale con `pip install -e ".[dev,ai]"` dentro `backend/`.

- [ ] **Step 7: Difendi la dipendenza nell'immagine**

In `backend/tests/test_image_dependencies.py`, in coda, un test nello stile degli altri:

```python
def test_beautifulsoup_e_una_dipendenza_di_base_e_non_un_extra():
    """Il parser dell'import non è una funzione opzionale.

    Messo fra gli extra finirebbe fuori dall'immagine esattamente come `anthropic`
    prima di questo file, e `python -m app.cli.import_gz` morirebbe su ImportError
    al primo uso in produzione, dove non c'è nessun test a dirlo.
    """
    progetto = tomllib.loads(PYPROJECT.read_text())["project"]
    assert any("beautifulsoup4" in dep for dep in progetto["dependencies"]), (
        f"{PYPROJECT}: beautifulsoup4 non è fra le dipendenze di base "
        f"({progetto['dependencies']!r}): il parser dell'import non parte."
    )
```

- [ ] **Step 8: Implementa il parser**

In coda a `backend/app/services/recipe_import/giallozafferano.py`:

```python
import html as html_entities
import json
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

MAX_QUANTITY_CHARS = 100  # il limite di recipe_ingredients.quantity_text
MIN_SERVINGS = 1
MAX_SERVINGS = 50  # i limiti che RecipeCreate già impone


class UnparsablePage(Exception):
    """La pagina non è una ricetta leggibile, e il motivo va conservato.

    Una pagina che sparisce in silenzio è un import di cui non si può dire niente:
    il motivo finisce in `recipe_imports.skipped_reason` e il riepilogo del comando
    li conta.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ParsedIngredient:
    key: str
    name: str
    quantity_text: str | None


@dataclass(frozen=True)
class ParsedRecipe:
    title: str
    description: str | None
    instructions: str
    servings: int | None
    category: str | None
    image_url: str | None
    prep_minutes: int | None
    cook_minutes: int | None
    ingredients: list[ParsedIngredient] = field(default_factory=list)
    nutrition: dict | None = None

    def as_payload(self) -> dict:
        """La forma che finisce in `recipe_imports.payload`, serializzabile in JSON."""
        return {
            "title": self.title,
            "description": self.description,
            "instructions": self.instructions,
            "servings": self.servings,
            "category": self.category,
            "image_url": self.image_url,
            "prep_minutes": self.prep_minutes,
            "cook_minutes": self.cook_minutes,
            "ingredients": [
                {"key": i.key, "name": i.name, "quantity_text": i.quantity_text}
                for i in self.ingredients
            ],
            "nutrition": self.nutrition,
        }


ISO_DURATION = re.compile(r"^P(?:(?P<days>\d+)D)?T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?")


def iso_minutes(value: object) -> int | None:
    """`PT1H30M` sono 90 minuti. Un formato che non riconosco è nessun minuto."""
    if not isinstance(value, str):
        return None
    found = ISO_DURATION.match(value.strip())
    if found is None:
        return None
    days = int(found.group("days") or 0)
    hours = int(found.group("hours") or 0)
    minutes = int(found.group("minutes") or 0)
    total = days * 24 * 60 + hours * 60 + minutes
    return total or None


def servings_from(value: object) -> int | None:
    """`4`, `"4"`, `"10 porzioni"`: il primo intero, se è un numero di porzioni sensato."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        candidate = value
    elif isinstance(value, list) and value:
        return servings_from(value[0])
    elif isinstance(value, str):
        found = re.search(r"\d+", value)
        if found is None:
            return None
        candidate = int(found.group())
    else:
        return None
    return candidate if MIN_SERVINGS <= candidate <= MAX_SERVINGS else None


def image_url_from(value: object) -> str | None:
    """`image` è una stringa, una lista, o un oggetto con `url`. Tutte e tre."""
    if isinstance(value, str):
        return value or None
    if isinstance(value, list):
        return image_url_from(value[0]) if value else None
    if isinstance(value, dict):
        return image_url_from(value.get("url"))
    return None


def recipe_jsonld(soup: BeautifulSoup) -> dict:
    """Il blocco schema.org/Recipe, cercato in tutte le forme che la fonte usa.

    Un oggetto solo, una lista di oggetti, o un `@graph`: saltarne una vorrebbe dire
    scartare pagine perfettamente leggibili.
    """
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        if isinstance(data, dict) and isinstance(data.get("@graph"), list):
            candidates = data["@graph"]
        for entry in candidates:
            if not isinstance(entry, dict):
                continue
            entry_type = entry.get("@type")
            types = entry_type if isinstance(entry_type, list) else [entry_type]
            if "Recipe" in types:
                return entry
    raise UnparsablePage("nessun blocco schema.org/Recipe nella pagina")


def term_key(href: str | None, name: str) -> str:
    """L'identità del termine è l'indirizzo del loro catalogo, non il nome scritto.

    Un refuso corretto cambia il nome e non l'indirizzo, e un dizionario costruito
    sui nomi perderebbe la decisione già presa. Le righe senza link — il catalogo
    non copre tutto — ricadono sul nome, marcate perché si veda che è un ripiego.
    """
    if href:
        return href.strip("/")
    return f"testo:{name.strip().lower()}"


def parse_ingredients(soup: BeautifulSoup) -> list[ParsedIngredient]:
    """Tutte le righe `dd.gz-ingredient`, nell'ordine, intestazioni dei gruppi ignorate.

    Non si collassa niente qui: lo stesso termine può comparire due volte nella
    stessa ricetta (la frolla e la crema vogliono entrambe lo zucchero a velo), e
    collassare richiede di sapere su quale ingrediente finiscono, che il parser non
    sa. Lo fa la materializzazione.
    """
    rows = soup.select("dd.gz-ingredient")
    if not rows:
        raise UnparsablePage("nessuna riga dd.gz-ingredient nella pagina")

    ingredients: list[ParsedIngredient] = []
    for row in rows:
        link = row.find("a")
        quantity_tag = row.find("span")
        quantity = quantity_tag.get_text(" ", strip=True) if quantity_tag else ""
        if quantity_tag is not None:
            quantity_tag.extract()
        name = link.get_text(" ", strip=True) if link else row.get_text(" ", strip=True)
        name = html_entities.unescape(name).strip()
        if not name:
            continue
        quantity = html_entities.unescape(quantity).strip()[:MAX_QUANTITY_CHARS]
        ingredients.append(
            ParsedIngredient(
                key=term_key(link.get("href") if link else None, name),
                name=name,
                quantity_text=quantity or None,
            )
        )
    if not ingredients:
        raise UnparsablePage("le righe degli ingredienti non hanno nomi leggibili")
    return ingredients


def parse_recipe(html: str) -> ParsedRecipe:
    """Il testo di una pagina → una ricetta leggibile, o `UnparsablePage` col perché.

    Funzione pura: nessuna rete, nessun database. È il nucleo verificabile di tutto
    l'import, ed è ciò che il futuro «incolla un link» riuserà così com'è.
    """
    soup = BeautifulSoup(html, "html.parser")
    data = recipe_jsonld(soup)

    title = str(data.get("name") or "").strip()
    if not title:
        raise UnparsablePage("la ricetta non ha un titolo")

    description = str(data.get("description") or "").strip() or None
    instructions = clean_instructions(data.get("recipeInstructions"))
    category = str(data.get("recipeCategory") or "").strip() or None

    return ParsedRecipe(
        title=title,
        description=description,
        instructions=instructions,
        servings=servings_from(data.get("recipeYield")),
        category=category,
        image_url=image_url_from(data.get("image")),
        prep_minutes=iso_minutes(data.get("prepTime")),
        cook_minutes=iso_minutes(data.get("cookTime")),
        ingredients=parse_ingredients(soup),
        nutrition=data.get("nutrition") if isinstance(data.get("nutrition"), dict) else None,
    )
```

Nota su `html_entities.unescape`: BeautifulSoup decodifica già le entità standard,
ma non tutte le fonti sono coerenti e la doppia decodifica di un testo già pulito è
a costo zero. `&frac12;` deve arrivare come `½`, e il test lo pretende.

- [ ] **Step 9: Esegui i test**

Run: `cd backend && pytest tests/services/test_giallozafferano_parse.py tests/test_image_dependencies.py -v`
Expected: PASS

- [ ] **Step 10: Prova di mutazione**

Nel parser, sostituisci `soup.select("dd.gz-ingredient")` con
`soup.select("dd.gz-ingredient a")` e riesegui: devono fallire i test che contano le
righe e quello delle dosi. Rimetti come prima. È la prova diretta della lezione di
CLAUDE.md sui selettori: un selettore plausibile e sbagliato non lo dice nessuno.

- [ ] **Step 11: Commit**

```bash
git add backend/app/services/recipe_import/giallozafferano.py backend/pyproject.toml \
        backend/tests/fixtures/giallozafferano backend/tests/services/test_giallozafferano_parse.py \
        backend/tests/test_image_dependencies.py
git commit -m "feat: il parser della pagina, su fixture ridotte e non ripubblicate"
```

---

## Task 6: lo scarico educato

**Files:**
- Modify: `backend/app/services/recipe_import/giallozafferano.py`
- Test: `backend/tests/services/test_giallozafferano_fetch.py`

**Interfaces:**
- Produces, da `app.services.recipe_import.giallozafferano`:
  `USER_AGENT: str`, `DELAY_SECONDS: float`, `RECIPE_SITEMAP: str`,
  `MAX_CONSECUTIVE_FAILURES: int`, `SourceUnavailable(Exception)`,
  `build_client() -> httpx.AsyncClient`,
  `async def fetch_sitemap(client) -> list[str]`,
  `async def fetch_page(client, url: str) -> str`.

Due guasti diversi, due eccezioni diverse, e la differenza conta. Un `404` su una
pagina è un problema di quella pagina: finisce in `skipped` e il giro continua. Un
`429` o un `500` è il sito che sta dicendo di smettere: ferma il giro, e le pagine
già prese restano salvate.

- [ ] **Step 1: Scrivi i test**

`backend/tests/services/test_giallozafferano_fetch.py`:

```python
import httpx
import pytest
import respx

from app.services.recipe_import.giallozafferano import (
    DELAY_SECONDS,
    MAX_CONSECUTIVE_FAILURES,
    RECIPE_SITEMAP,
    USER_AGENT,
    SourceUnavailable,
    UnparsablePage,
    build_client,
    fetch_page,
    fetch_sitemap,
)

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
 <url><loc>https://ricette.giallozafferano.it/Tiramisu.html</loc></url>
 <url><loc>https://ricette.giallozafferano.it/Carbonara.html</loc></url>
 <url><loc>https://ricette.giallozafferano.it/ricette-cat/Dolci/</loc></url>
</urlset>"""


@respx.mock
async def test_la_sitemap_da_solo_pagine_di_ricetta():
    respx.get(RECIPE_SITEMAP).mock(return_value=httpx.Response(200, text=SITEMAP))

    async with build_client() as client:
        urls = await fetch_sitemap(client)

    assert urls == [
        "https://ricette.giallozafferano.it/Tiramisu.html",
        "https://ricette.giallozafferano.it/Carbonara.html",
    ]


@respx.mock
async def test_la_richiesta_si_fa_riconoscere():
    """Lo User-Agent non è decorativo: è il modo di non presentarsi come un crawler
    anonimo a un sito che nel suo robots.txt vieta esplicitamente i crawler AI."""
    route = respx.get(RECIPE_SITEMAP).mock(return_value=httpx.Response(200, text=SITEMAP))

    async with build_client() as client:
        await fetch_sitemap(client)

    assert route.calls.last.request.headers["user-agent"] == USER_AGENT
    assert "archivio personale" in USER_AGENT


@respx.mock
async def test_una_pagina_si_legge():
    respx.get("https://ricette.giallozafferano.it/Tiramisu.html").mock(
        return_value=httpx.Response(200, text="<html>tiramisù</html>")
    )

    async with build_client() as client:
        html = await fetch_page(client, "https://ricette.giallozafferano.it/Tiramisu.html")

    assert "tiramisù" in html


@respx.mock
@pytest.mark.parametrize("status", [429, 500, 503])
async def test_il_sito_che_chiede_di_smettere_ferma_il_giro(status):
    respx.get("https://ricette.giallozafferano.it/Tiramisu.html").mock(
        return_value=httpx.Response(status)
    )

    async with build_client() as client:
        with pytest.raises(SourceUnavailable):
            await fetch_page(client, "https://ricette.giallozafferano.it/Tiramisu.html")


@respx.mock
async def test_una_pagina_che_non_esiste_e_un_problema_solo_suo():
    """404 non ferma niente: è questa pagina a essere andata, non il sito."""
    respx.get("https://ricette.giallozafferano.it/Spariita.html").mock(
        return_value=httpx.Response(404)
    )

    async with build_client() as client:
        with pytest.raises(UnparsablePage) as errore:
            await fetch_page(client, "https://ricette.giallozafferano.it/Spariita.html")

    assert "404" in errore.value.reason


@respx.mock
async def test_la_sitemap_irraggiungibile_e_un_guasto_della_fonte():
    respx.get(RECIPE_SITEMAP).mock(return_value=httpx.Response(503))

    async with build_client() as client:
        with pytest.raises(SourceUnavailable):
            await fetch_sitemap(client)


def test_le_costanti_di_cortesia_sono_quelle_dichiarate_nello_spec():
    assert DELAY_SECONDS >= 1.0
    assert MAX_CONSECUTIVE_FAILURES == 2
```

- [ ] **Step 2: Verifica che i test falliscano**

Run: `cd backend && pytest tests/services/test_giallozafferano_fetch.py -v`
Expected: FAIL con `ImportError: cannot import name 'SourceUnavailable'`

- [ ] **Step 3: Implementa**

In coda a `backend/app/services/recipe_import/giallozafferano.py`:

```python
import httpx

# Dichiarare cosa si è, su un sito che nel suo robots.txt vieta esplicitamente
# `Claude-Web` e `anthropic-ai`. Questo non è quei crawler, ed è giusto che si
# distingua anche nei loro log. Vedi §3 dello spec per la decisione.
USER_AGENT = (
    "SpenaPersonalArchive/1.0 (archivio personale di ricette, nessuna ridistribuzione)"
)
# Una pagina alla volta, con una pausa. Non è una configurazione: è la differenza
# fra leggere e rastrellare.
DELAY_SECONDS = 1.2
REQUEST_TIMEOUT = 20.0
MAX_CONSECUTIVE_FAILURES = 2

RECIPE_SITEMAP = "https://ricette.giallozafferano.it/sitemap/ricette.xml"

SITEMAP_LOCATION = re.compile(r"<loc>\s*(.*?)\s*</loc>", re.S)


class SourceUnavailable(Exception):
    """La fonte sta dicendo di smettere, o non risponde affatto.

    Distinta da `UnparsablePage` di proposito: questa ferma il giro, quella scarta
    una pagina e lascia continuare. Insistere contro un `429` è la cosa da non fare,
    e perdere il lavoro già fatto sarebbe inutile: le pagine prese sono già salvate.
    """


def build_client() -> httpx.AsyncClient:
    """Un client che si presenta, aspetta e segue i rinvii."""
    return httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
    )


async def fetch_sitemap(client: httpx.AsyncClient) -> list[str]:
    """Gli indirizzi delle pagine di ricetta, nell'ordine in cui la fonte li elenca.

    Si tengono solo gli indirizzi che finiscono in `.html`: la stessa sitemap elenca
    anche pagine di categoria, che non sono ricette e farebbero scartare una pagina
    su dieci per niente.
    """
    try:
        response = await client.get(RECIPE_SITEMAP)
    except httpx.HTTPError as exc:
        raise SourceUnavailable(f"sitemap irraggiungibile: {exc}") from exc
    if response.status_code != 200:
        raise SourceUnavailable(f"la sitemap ha risposto {response.status_code}")
    return [url for url in SITEMAP_LOCATION.findall(response.text) if url.endswith(".html")]


async def fetch_page(client: httpx.AsyncClient, url: str) -> str:
    """Il testo di una pagina.

    `429` e `5xx` sollevano `SourceUnavailable`, che ferma il giro. Qualunque altra
    risposta non buona solleva `UnparsablePage`, che scarta questa pagina e lascia
    andare avanti: una ricetta cancellata dal sito non è un guasto del sito.
    """
    try:
        response = await client.get(url)
    except httpx.HTTPError as exc:
        raise SourceUnavailable(f"{url} irraggiungibile: {exc}") from exc
    if response.status_code == 429 or response.status_code >= 500:
        raise SourceUnavailable(f"{url}: la fonte ha risposto {response.status_code}")
    if response.status_code != 200:
        raise UnparsablePage(f"la fonte ha risposto {response.status_code}")
    return response.text
```

- [ ] **Step 4: Esegui i test**

Run: `cd backend && pytest tests/services/test_giallozafferano_fetch.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/recipe_import/giallozafferano.py \
        backend/tests/services/test_giallozafferano_fetch.py
git commit -m "feat: scarico educato, e due guasti distinti: la pagina o la fonte"
```

---

## Task 7: il registro delle pagine e dei termini

**Files:**
- Create: `backend/app/repositories/imports.py`
- Create: `backend/app/services/recipe_import/terms.py`
- Test: `backend/tests/services/test_import_terms.py`

**Interfaces:**
- Consumes: `RecipeImport`, `ImportTerm`, `ImportState`, `TermDecision`,
  `GIALLOZAFFERANO` dal Task 1; `match_name` dal Task 3.
- Produces, da `app.repositories.imports`:
  `ImportCounts(fetched, pending_recipes, imported, skipped, pending_terms)`,
  `async def known_urls(session, source) -> set[str]`,
  `async def store_page(session, *, source, url, payload) -> RecipeImport`,
  `async def store_unparsable(session, *, source, url, reason) -> RecipeImport`,
  `async def pending_pages(session, source) -> list[RecipeImport]`,
  `async def counts(session, source) -> ImportCounts`,
  `async def pending_terms(session, source, limit) -> list[ImportTerm]`,
  `async def terms_by_key(session, source) -> dict[str, ImportTerm]`,
  `async def get_term(session, term_id) -> ImportTerm | None`,
  `async def waiting_titles(session, source, keys, per_term=3) -> dict[str, list[str]]`.
- Produces, da `app.services.recipe_import.terms`:
  `TermsSynced(created, auto_decided, pending)`,
  `async def sync_terms(session, source=GIALLOZAFFERANO) -> TermsSynced`.

`occurrences` conta **le pagine ancora in attesa** che usano quel termine, non tutte
le pagine mai scaricate. È il numero che serve a chi revisiona: «quante ricette
sblocca questa decisione». Cala da sé quando le ricette entrano, ed è anche la
ragione per cui si ricalcola invece di incrementarlo.

- [ ] **Step 1: Scrivi i test**

`backend/tests/services/test_import_terms.py`:

```python
import pytest_asyncio

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.recipe_import import GIALLOZAFFERANO, TermDecision
from app.repositories.imports import (
    counts,
    pending_terms,
    store_page,
    terms_by_key,
    waiting_titles,
)
from app.services.recipe_import.terms import sync_terms


def payload(title: str, ingredients: list[tuple[str, str, str]]) -> dict:
    """`ingredients` è una lista di (key, name, quantity_text)."""
    return {
        "title": title,
        "description": None,
        "instructions": "Cuoci.",
        "servings": 2,
        "category": "Primi piatti",
        "image_url": None,
        "prep_minutes": 5,
        "cook_minutes": 10,
        "ingredients": [
            {"key": key, "name": name, "quantity_text": quantity}
            for key, name, quantity in ingredients
        ],
        "nutrition": None,
    }


@pytest_asyncio.fixture
async def anagrafica(db_session):
    pasta = Ingredient(
        name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    pasta.aliases.append(IngredientAlias(alias="rigatoni", source="import"))
    db_session.add(pasta)
    db_session.add(
        Ingredient(name="speck", display_name="Speck", category=IngredientCategory.CARNE)
    )
    await db_session.flush()


async def test_ogni_termine_distinto_diventa_una_riga(db_session, anagrafica):
    await store_page(
        db_session, source=GIALLOZAFFERANO,
        url="https://ricette.giallozafferano.it/Uno.html",
        payload=payload("Uno", [
            ("ricette-con-i-Rigatoni", "Rigatoni", "320 g"),
            ("ricette-con-lo-Speck", "Speck", "80 g"),
        ]),
    )

    synced = await sync_terms(db_session)

    assert synced.created == 2


async def test_un_termine_che_coincide_con_un_nome_si_decide_da_se(db_session, anagrafica):
    await store_page(
        db_session, source=GIALLOZAFFERANO,
        url="https://ricette.giallozafferano.it/Uno.html",
        payload=payload("Uno", [("ricette-con-lo-Speck", "Speck", "80 g")]),
    )

    synced = await sync_terms(db_session)

    assert synced.auto_decided == 1
    term = (await pending_terms(db_session, GIALLOZAFFERANO, limit=10))
    assert term == [], "un termine certo non deve finire nella coda"


async def test_un_termine_che_coincide_con_un_alias_si_decide_da_se(db_session, anagrafica):
    """`Rigatoni` è un alias di `pasta`: l'uguaglianza è un fatto, non una proposta."""
    await store_page(
        db_session, source=GIALLOZAFFERANO,
        url="https://ricette.giallozafferano.it/Uno.html",
        payload=payload("Uno", [("ricette-con-i-Rigatoni", "Rigatoni", "320 g")]),
    )

    await sync_terms(db_session)

    term = (await terms_by_key(db_session, GIALLOZAFFERANO))["ricette-con-i-Rigatoni"]
    assert term.decision == TermDecision.MAPPED
    assert term.decided_by == "auto"


async def test_un_termine_sconosciuto_aspetta(db_session, anagrafica):
    await store_page(
        db_session, source=GIALLOZAFFERANO,
        url="https://ricette.giallozafferano.it/Uno.html",
        payload=payload("Uno", [("ricette-con-la-Bottarga", "Bottarga", "20 g")]),
    )

    synced = await sync_terms(db_session)

    assert synced.pending == 1
    coda = await pending_terms(db_session, GIALLOZAFFERANO, limit=10)
    assert [t.display_name for t in coda] == ["Bottarga"]


async def test_la_coda_e_ordinata_per_quante_ricette_sblocca(db_session, anagrafica):
    for numero in range(3):
        await store_page(
            db_session, source=GIALLOZAFFERANO,
            url=f"https://ricette.giallozafferano.it/Tre-{numero}.html",
            payload=payload(f"Tre {numero}", [("ricette-con-la-Bottarga", "Bottarga", "20 g")]),
        )
    await store_page(
        db_session, source=GIALLOZAFFERANO,
        url="https://ricette.giallozafferano.it/Uno.html",
        payload=payload("Uno", [("ricette-con-il-Nasello", "Nasello", "200 g")]),
    )

    await sync_terms(db_session)

    coda = await pending_terms(db_session, GIALLOZAFFERANO, limit=10)
    assert [(t.display_name, t.occurrences) for t in coda] == [("Bottarga", 3), ("Nasello", 1)]


async def test_il_conteggio_si_ricalcola_e_non_si_accumula(db_session, anagrafica):
    """Due sincronizzazioni non raddoppiano niente: è la ragione per cui
    `occurrences` si ricalcola invece di essere incrementato."""
    await store_page(
        db_session, source=GIALLOZAFFERANO,
        url="https://ricette.giallozafferano.it/Uno.html",
        payload=payload("Uno", [("ricette-con-la-Bottarga", "Bottarga", "20 g")]),
    )

    await sync_terms(db_session)
    seconda = await sync_terms(db_session)

    assert seconda.created == 0
    coda = await pending_terms(db_session, GIALLOZAFFERANO, limit=10)
    assert coda[0].occurrences == 1


async def test_lo_stesso_termine_due_volte_nella_stessa_ricetta_conta_una(db_session, anagrafica):
    """La frolla e la crema vogliono entrambe lo zucchero a velo, ma la ricetta in
    attesa è una: `occurrences` conta ricette, non righe."""
    await store_page(
        db_session, source=GIALLOZAFFERANO,
        url="https://ricette.giallozafferano.it/Torta.html",
        payload=payload("Torta", [
            ("ricette-con-Zucchero-a-velo", "Zucchero a velo", "150 g"),
            ("ricette-con-Zucchero-a-velo", "Zucchero a velo", "q.b."),
        ]),
    )

    await sync_terms(db_session)

    coda = await pending_terms(db_session, GIALLOZAFFERANO, limit=10)
    assert [(t.display_name, t.occurrences) for t in coda] == [("Zucchero a velo", 1)]


async def test_i_titoli_in_attesa_aiutano_a_decidere(db_session, anagrafica):
    """«Scorza di limone» si giudica diversamente in una torta e in un arrosto."""
    await store_page(
        db_session, source=GIALLOZAFFERANO,
        url="https://ricette.giallozafferano.it/Torta.html",
        payload=payload("Torta della nonna", [("ricette-con-Scorza", "Scorza di limone", "½")]),
    )
    await sync_terms(db_session)

    titoli = await waiting_titles(db_session, GIALLOZAFFERANO, ["ricette-con-Scorza"])

    assert titoli["ricette-con-Scorza"] == ["Torta della nonna"]


async def test_i_conteggi_dicono_dove_sta_l_import(db_session, anagrafica):
    await store_page(
        db_session, source=GIALLOZAFFERANO,
        url="https://ricette.giallozafferano.it/Uno.html",
        payload=payload("Uno", [("ricette-con-la-Bottarga", "Bottarga", "20 g")]),
    )
    await sync_terms(db_session)

    numeri = await counts(db_session, GIALLOZAFFERANO)

    assert numeri.fetched == 1
    assert numeri.pending_recipes == 1
    assert numeri.imported == 0
    assert numeri.skipped == 0
    assert numeri.pending_terms == 1
```

- [ ] **Step 2: Verifica che i test falliscano**

Run: `cd backend && pytest tests/services/test_import_terms.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.repositories.imports'`

- [ ] **Step 3: Scrivi il repository**

`backend/app/repositories/imports.py`:

```python
"""Interrogazioni sulle due tabelle dell'import.

Le pagine in attesa si leggono più volte per giro (sincronizzazione dei termini,
materializzazione, titoli in attesa): stanno tutte qui perché la stessa query
scritta tre volte si scolla tre volte.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.recipe_import import ImportState, ImportTerm, RecipeImport, TermDecision


@dataclass(frozen=True)
class ImportCounts:
    fetched: int
    pending_recipes: int
    imported: int
    skipped: int
    pending_terms: int


async def known_urls(session: AsyncSession, source: str) -> set[str]:
    """Gli indirizzi già presi. Non si riscarica mai una pagina due volte."""
    rows = await session.execute(
        select(RecipeImport.url).where(RecipeImport.source == source)
    )
    return set(rows.scalars())


async def store_page(
    session: AsyncSession, *, source: str, url: str, payload: dict
) -> RecipeImport:
    page = RecipeImport(
        source=source, url=url, payload=payload, state=ImportState.PENDING
    )
    session.add(page)
    await session.flush()
    return page


async def store_unparsable(
    session: AsyncSession, *, source: str, url: str, reason: str
) -> RecipeImport:
    """Una pagina illeggibile si conserva col suo motivo.

    Un import che perde in silenzio il tre per cento delle pagine è un import di cui
    non si può dire niente.
    """
    page = RecipeImport(
        source=source, url=url, payload={}, state=ImportState.SKIPPED,
        skipped_reason=reason[:200],
    )
    session.add(page)
    await session.flush()
    return page


async def pending_pages(session: AsyncSession, source: str) -> list[RecipeImport]:
    rows = await session.execute(
        select(RecipeImport)
        .where(RecipeImport.source == source, RecipeImport.state == ImportState.PENDING)
        .order_by(RecipeImport.fetched_at)
    )
    return list(rows.scalars())


async def counts(session: AsyncSession, source: str) -> ImportCounts:
    by_state = dict(
        (
            await session.execute(
                select(RecipeImport.state, func.count())
                .where(RecipeImport.source == source)
                .group_by(RecipeImport.state)
            )
        ).all()
    )
    waiting = (
        await session.execute(
            select(func.count())
            .select_from(ImportTerm)
            .where(ImportTerm.source == source, ImportTerm.decision == TermDecision.PENDING)
        )
    ).scalar_one()
    return ImportCounts(
        fetched=sum(by_state.values()),
        pending_recipes=by_state.get(ImportState.PENDING, 0),
        imported=by_state.get(ImportState.IMPORTED, 0),
        skipped=by_state.get(ImportState.SKIPPED, 0),
        pending_terms=waiting,
    )


async def pending_terms(
    session: AsyncSession, source: str, limit: int = 20
) -> list[ImportTerm]:
    """I termini da decidere, da quello che sblocca più ricette.

    È l'unico ordine in cui vale la pena revisionare: più della metà dei termini
    compare in una ricetta sola, e decidere prima i frequenti è ciò che fa vedere il
    ricettario crescere.
    """
    rows = await session.execute(
        select(ImportTerm)
        .where(ImportTerm.source == source, ImportTerm.decision == TermDecision.PENDING)
        .order_by(ImportTerm.occurrences.desc(), ImportTerm.display_name)
        .limit(limit)
    )
    return list(rows.scalars())


async def terms_by_key(session: AsyncSession, source: str) -> dict[str, ImportTerm]:
    rows = await session.execute(select(ImportTerm).where(ImportTerm.source == source))
    return {term.term_key: term for term in rows.scalars()}


async def get_term(session: AsyncSession, term_id: uuid.UUID) -> ImportTerm | None:
    return await session.get(ImportTerm, term_id)


async def waiting_titles(
    session: AsyncSession, source: str, keys: list[str], per_term: int = 3
) -> dict[str, list[str]]:
    """Qualche titolo in attesa per ogni termine chiesto.

    Serve a decidere: «Scorza di limone» si giudica diversamente in una torta e in
    un arrosto. Si scorre in Python sulle pagine in attesa, che sono le sole che
    contano e che calano a ogni decisione.
    """
    wanted = set(keys)
    titles: dict[str, list[str]] = {key: [] for key in keys}
    for page in await pending_pages(session, source):
        title = str(page.payload.get("title") or "")
        for line in page.payload.get("ingredients") or []:
            key = line.get("key")
            if key in wanted and len(titles[key]) < per_term and title not in titles[key]:
                titles[key].append(title)
    return titles
```

- [ ] **Step 4: Scrivi la sincronizzazione dei termini**

`backend/app/services/recipe_import/terms.py`:

```python
"""Il dizionario dal catalogo della fonte al nostro.

Il catalogo di un sito di cucina è più fine di un'anagrafica fatta per rispondere
«ce l'ho in casa?»: dove noi abbiamo `pasta`, loro hanno `Rigatoni`. Colmare quella
distanza è l'unica parte dell'import che non si automatizza, perché colmarla male
avvelena la disponibilità di tutte le ricette che usano quell'ingrediente.

Quel che si automatizza è l'uguaglianza: un termine che coincide con un nostro nome
canonico o con un alias già scritto si decide da sé. Non è una proposta, è un fatto.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.repositories.imports import pending_pages, terms_by_key
from app.services.ingredient_match import match_name


@dataclass(frozen=True)
class TermsSynced:
    created: int
    auto_decided: int
    pending: int


async def sync_terms(session: AsyncSession, source: str = GIALLOZAFFERANO) -> TermsSynced:
    """Allinea il dizionario alle pagine in attesa.

    `occurrences` conta le **ricette** in attesa che usano il termine, non le righe:
    la frolla e la crema vogliono entrambe lo zucchero a velo, ma la ricetta
    bloccata è una. Si ricalcola a ogni passaggio e non si incrementa mai: un
    contatore incrementato divergerebbe al primo ri-scarico, e un ordinamento della
    coda basato su un numero sbagliato è un difetto che nessuno nota.
    """
    occurrences: dict[str, int] = {}
    display_names: dict[str, str] = {}
    for page in await pending_pages(session, source):
        keys_here = set()
        for line in page.payload.get("ingredients") or []:
            key = line.get("key")
            if not key:
                continue
            keys_here.add(key)
            display_names.setdefault(key, str(line.get("name") or key)[:200])
        for key in keys_here:
            occurrences[key] = occurrences.get(key, 0) + 1

    existing = await terms_by_key(session, source)

    created = 0
    auto_decided = 0
    for key, count in occurrences.items():
        term = existing.get(key)
        if term is None:
            term = ImportTerm(
                source=source, term_key=key, display_name=display_names[key],
                occurrences=count, decision=TermDecision.PENDING,
            )
            session.add(term)
            existing[key] = term
            created += 1
            match = await match_name(session, term.display_name)
            if match.certain:
                term.decision = TermDecision.MAPPED
                term.ingredient_id = match.ingredient_id
                term.decided_by = "auto"
                term.decided_at = datetime.now(UTC)
                auto_decided += 1
        else:
            term.occurrences = count

    # un termine che non compare più in nessuna pagina in attesa non ha più ricette
    # da sbloccare: il suo conteggio va a zero, non resta al valore di ieri
    for key, term in existing.items():
        if key not in occurrences:
            term.occurrences = 0

    await session.flush()
    pending = sum(
        1 for term in existing.values() if term.decision == TermDecision.PENDING
    )
    return TermsSynced(created=created, auto_decided=auto_decided, pending=pending)
```

- [ ] **Step 5: Esegui i test**

Run: `cd backend && pytest tests/services/test_import_terms.py -v`
Expected: PASS

- [ ] **Step 6: Prova di mutazione**

In `sync_terms`, sostituisci `term.occurrences = count` con
`term.occurrences += count` e riesegui: deve fallire
`test_il_conteggio_si_ricalcola_e_non_si_accumula`, e solo quello. Rimetti come prima.

- [ ] **Step 7: Commit**

```bash
git add backend/app/repositories/imports.py backend/app/services/recipe_import/terms.py \
        backend/tests/services/test_import_terms.py
git commit -m "feat: il dizionario dei termini, ordinato per quante ricette sblocca"
```

---

## Task 8: la materializzazione

**Files:**
- Create: `backend/app/services/recipe_import/materialize.py`
- Test: `backend/tests/services/test_materialize.py`

**Interfaces:**
- Consumes: `pending_pages`, `terms_by_key` dal Task 7; `default_role` dal Task 2;
  `create_recipe(session, *, title, description, instructions, servings, source,
  source_ref, ingredients, embedding)` da `app.repositories.recipes`, dove
  `ingredients` è una lista di `(ingredient_id, role, quantity_text, note)`.
- Produces, da `app.services.recipe_import.materialize`:
  `Materialized(created: int, skipped: int)`,
  `async def materialize_ready(session, source=GIALLOZAFFERANO) -> Materialized`.

Tre regole non ovvie, e ognuna ha un test che la difende:

1. **Collasso dei duplicati.** `recipe_ingredients` ha `UNIQUE (recipe_id,
   ingredient_id)`: due righe che finiscono sullo stesso ingrediente farebbero
   fallire l'inserimento. Diventano una riga, con le quantità unite da ` + ` e il
   ruolo più forte, perché `primary` vince su `secondary`.
2. **I termini ignorati non producono righe** e non fanno scartare la ricetta.
3. **Una ricetta che resterebbe senza righe si scarta** con motivo: una ricetta
   senza ingredienti è sempre cucinabile, cioè la bugia peggiore che questo lavoro
   possa produrre.

- [ ] **Step 1: Scrivi i test**

`backend/tests/services/test_materialize.py`:

```python
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import Recipe
from app.db.models.recipe_import import (
    GIALLOZAFFERANO,
    ImportState,
    ImportTerm,
    RecipeImport,
    TermDecision,
)
from app.domain.rules import IngredientRole
from app.repositories.imports import store_page
from app.repositories.recipes import get_recipe
from app.services.recipe_import.materialize import materialize_ready


def payload(title: str, ingredients: list[tuple[str, str, str]]) -> dict:
    return {
        "title": title, "description": "Breve", "instructions": "Cuoci.",
        "servings": 4, "category": "Primi piatti",
        "image_url": "https://esempio/foto.jpg", "prep_minutes": 10, "cook_minutes": 15,
        "ingredients": [
            {"key": key, "name": name, "quantity_text": quantity}
            for key, name, quantity in ingredients
        ],
        "nutrition": {"calories": "464,4 kcal"},
    }


@pytest_asyncio.fixture
async def anagrafica(db_session):
    """Due ingredienti e i termini già decisi: questo task parte da lì."""
    farina = Ingredient(
        name="farina", display_name="Farina", category=IngredientCategory.CEREALI
    )
    sale = Ingredient(name="sale", display_name="Sale", category=IngredientCategory.SPEZIE)
    db_session.add_all([farina, sale])
    await db_session.flush()

    db_session.add_all([
        ImportTerm(source=GIALLOZAFFERANO, term_key="farina-00", display_name="Farina 00",
                   occurrences=1, decision=TermDecision.MAPPED, ingredient_id=farina.id,
                   decided_by="human"),
        ImportTerm(source=GIALLOZAFFERANO, term_key="farina-0", display_name="Farina 0",
                   occurrences=1, decision=TermDecision.MAPPED, ingredient_id=farina.id,
                   decided_by="human"),
        ImportTerm(source=GIALLOZAFFERANO, term_key="sale-fino", display_name="Sale fino",
                   occurrences=1, decision=TermDecision.MAPPED, ingredient_id=sale.id,
                   decided_by="human"),
        ImportTerm(source=GIALLOZAFFERANO, term_key="acqua", display_name="Acqua",
                   occurrences=1, decision=TermDecision.IGNORED, decided_by="human"),
        ImportTerm(source=GIALLOZAFFERANO, term_key="bottarga", display_name="Bottarga",
                   occurrences=1, decision=TermDecision.PENDING),
    ])
    await db_session.flush()
    return {"farina": farina, "sale": sale}


async def test_una_ricetta_coi_termini_decisi_entra(db_session, anagrafica):
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/pane.html",
        payload=payload("Pane", [("farina-00", "Farina 00", "500 g"),
                                 ("sale-fino", "Sale fino", "q.b.")]),
    )

    esito = await materialize_ready(db_session)

    assert (esito.created, esito.skipped) == (1, 0)
    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    assert ricetta.title == "Pane"
    assert ricetta.source == "dataset"
    assert ricetta.source_ref == "https://esempio/pane.html"
    assert ricetta.category == "Primi piatti"
    assert ricetta.prep_minutes == 10
    assert ricetta.cook_minutes == 15
    assert ricetta.image_url == "https://esempio/foto.jpg"


async def test_la_pagina_resta_legata_alla_ricetta_che_ha_prodotto(db_session, anagrafica):
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/pane.html",
        payload=payload("Pane", [("farina-00", "Farina 00", "500 g")]),
    )

    await materialize_ready(db_session)

    pagina = (await db_session.execute(select(RecipeImport))).scalars().one()
    assert pagina.state == ImportState.IMPORTED
    assert pagina.recipe_id is not None


async def test_il_ruolo_viene_dalla_regola(db_session, anagrafica):
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/pane.html",
        payload=payload("Pane", [("farina-00", "Farina 00", "500 g"),
                                 ("sale-fino", "Sale fino", "q.b.")]),
    )

    await materialize_ready(db_session)

    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    dettaglio = await get_recipe(db_session, ricetta.id)
    ruoli = {line.ingredient.name: line.role for line in dettaglio.ingredients}
    assert ruoli == {"farina": IngredientRole.PRIMARY, "sale": IngredientRole.SECONDARY}


async def test_il_ruolo_corretto_a_mano_vince_sulla_regola(db_session, anagrafica):
    termine = (
        await db_session.execute(
            select(ImportTerm).where(ImportTerm.term_key == "farina-00")
        )
    ).scalars().one()
    termine.role_override = IngredientRole.SECONDARY
    await db_session.flush()
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/pane.html",
        payload=payload("Pane", [("farina-00", "Farina 00", "500 g")]),
    )

    await materialize_ready(db_session)

    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    dettaglio = await get_recipe(db_session, ricetta.id)
    assert dettaglio.ingredients[0].role == IngredientRole.SECONDARY


async def test_due_righe_sullo_stesso_ingrediente_diventano_una(db_session, anagrafica):
    """Senza il collasso l'inserimento fallirebbe sul vincolo di unicità."""
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/torta.html",
        payload=payload("Torta", [("farina-00", "Farina 00", "500 g"),
                                  ("farina-0", "Farina 0", "50 g")]),
    )

    esito = await materialize_ready(db_session)

    assert esito.created == 1
    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    dettaglio = await get_recipe(db_session, ricetta.id)
    assert len(dettaglio.ingredients) == 1
    assert dettaglio.ingredients[0].quantity_text == "500 g + 50 g"


async def test_nel_collasso_il_ruolo_piu_forte_vince(db_session, anagrafica):
    """La farina per la frolla è principale anche se per la spolverata è «q.b.»."""
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/torta.html",
        payload=payload("Torta", [("farina-0", "Farina 0", "q.b."),
                                  ("farina-00", "Farina 00", "500 g")]),
    )

    await materialize_ready(db_session)

    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    dettaglio = await get_recipe(db_session, ricetta.id)
    assert dettaglio.ingredients[0].role == IngredientRole.PRIMARY


async def test_un_termine_ignorato_non_produce_una_riga(db_session, anagrafica):
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/pane.html",
        payload=payload("Pane", [("farina-00", "Farina 00", "500 g"),
                                 ("acqua", "Acqua", "300 g")]),
    )

    esito = await materialize_ready(db_session)

    assert esito.created == 1
    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    dettaglio = await get_recipe(db_session, ricetta.id)
    assert [line.ingredient.name for line in dettaglio.ingredients] == ["farina"]


async def test_una_ricetta_con_un_termine_ancora_da_decidere_aspetta(db_session, anagrafica):
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/bottarga.html",
        payload=payload("Spaghetti alla bottarga", [("farina-00", "Farina 00", "500 g"),
                                                    ("bottarga", "Bottarga", "20 g")]),
    )

    esito = await materialize_ready(db_session)

    assert (esito.created, esito.skipped) == (0, 0)
    pagina = (await db_session.execute(select(RecipeImport))).scalars().one()
    assert pagina.state == ImportState.PENDING


async def test_una_ricetta_che_resterebbe_vuota_si_scarta_col_motivo(db_session, anagrafica):
    """Una ricetta senza ingredienti è sempre cucinabile: è la bugia peggiore."""
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/acqua.html",
        payload=payload("Acqua bollente", [("acqua", "Acqua", "1 l")]),
    )

    esito = await materialize_ready(db_session)

    assert (esito.created, esito.skipped) == (0, 1)
    pagina = (await db_session.execute(select(RecipeImport))).scalars().one()
    assert pagina.state == ImportState.SKIPPED
    assert "senza" in pagina.skipped_reason
    assert (await db_session.execute(select(Recipe))).scalars().all() == []


async def test_una_ricetta_cancellata_non_viene_ricreata(db_session, anagrafica):
    """`recipe_id` va a NULL, ma lo stato resta `imported`: è lo stato a dire
    «questa pagina è già stata importata una volta»."""
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/pane.html",
        payload=payload("Pane", [("farina-00", "Farina 00", "500 g")]),
    )
    await materialize_ready(db_session)
    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    await db_session.delete(ricetta)
    await db_session.flush()

    esito = await materialize_ready(db_session)

    assert (esito.created, esito.skipped) == (0, 0)
    assert (await db_session.execute(select(Recipe))).scalars().all() == []


async def test_la_materializzazione_e_rieseguibile(db_session, anagrafica):
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/pane.html",
        payload=payload("Pane", [("farina-00", "Farina 00", "500 g")]),
    )

    await materialize_ready(db_session)
    seconda = await materialize_ready(db_session)

    assert (seconda.created, seconda.skipped) == (0, 0)
    assert len((await db_session.execute(select(Recipe))).scalars().all()) == 1
```

- [ ] **Step 2: Verifica che i test falliscano**

Run: `cd backend && pytest tests/services/test_materialize.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.services.recipe_import.materialize'`

- [ ] **Step 3: Implementa**

`backend/app/services/recipe_import/materialize.py`:

```python
"""Da pagina in attesa a ricetta vera.

Una pagina diventa ricetta solo quando **tutti** i suoi termini hanno una decisione.
L'alternativa — far entrare la ricetta con la riga non agganciata — richiederebbe di
dire alla cucinabilità cosa risponde su un ingrediente ignoto: «sì» è una bugia che
si scopre a metà cottura, «no» nasconde ricette fattibili. Aspettare è la sola
risposta onesta, ed è sopportabile perché la coda è ordinata per quante ricette
sblocca.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingredient import Ingredient
from app.db.models.recipe import RecipeSource
from app.db.models.recipe_import import (
    GIALLOZAFFERANO,
    ImportState,
    RecipeImport,
    TermDecision,
)
from app.domain.rules import IngredientRole, default_role
from app.repositories.imports import pending_pages, terms_by_key
from app.repositories.recipes import create_recipe
from app.services.embeddings import (
    EmbeddingUnavailable,
    get_embedding_provider,
    log_degradation_once,
)

MAX_QUANTITY_CHARS = 100  # il limite di recipe_ingredients.quantity_text
EMPTY_REASON = (
    "ogni ingrediente è stato ignorato: la ricetta resterebbe senza righe, "
    "e una ricetta senza ingredienti risulterebbe sempre cucinabile"
)


@dataclass(frozen=True)
class Materialized:
    created: int
    skipped: int


def merge_quantities(first: str | None, second: str | None) -> str | None:
    """Due dosi sullo stesso ingrediente diventano una stringa sola.

    Il gruppo di appartenenza («per la frolla», «per la crema») non entra nel nostro
    modello, quindi unire è il massimo di verità che si può conservare: si legge
    «500 g + 50 g», che è meno informativo dei due gruppi separati ma non è falso.
    """
    parts = [part for part in (first, second) if part]
    if not parts:
        return None
    return " + ".join(parts)[:MAX_QUANTITY_CHARS]


def stronger(first: IngredientRole, second: IngredientRole) -> IngredientRole:
    """`primary` vince: la farina della frolla serve anche se la spolverata è «q.b.»."""
    if IngredientRole.PRIMARY in (first, second):
        return IngredientRole.PRIMARY
    return IngredientRole.SECONDARY


async def materialize_ready(
    session: AsyncSession, source: str = GIALLOZAFFERANO
) -> Materialized:
    """Tutte le pagine in attesa i cui termini sono decisi diventano ricette."""
    terms = await terms_by_key(session, source)
    categories = dict(
        (await session.execute(select(Ingredient.id, Ingredient.category))).all()
    )
    provider = get_embedding_provider()

    created = 0
    skipped = 0
    for page in await pending_pages(session, source):
        lines = page.payload.get("ingredients") or []
        decisions = [terms.get(line.get("key")) for line in lines]
        if any(
            term is None or term.decision == TermDecision.PENDING for term in decisions
        ):
            continue  # aspetta: è la decisione presa nello spec §2

        # collasso per ingrediente, nell'ordine di prima comparsa
        collapsed: dict[str, tuple[IngredientRole, str | None]] = {}
        for line, term in zip(lines, decisions, strict=True):
            if term.decision == TermDecision.IGNORED:
                continue
            quantity = line.get("quantity_text")
            role = IngredientRole(
                term.role_override
                or default_role(categories.get(term.ingredient_id, "altro"), quantity)
            )
            key = str(term.ingredient_id)
            if key in collapsed:
                previous_role, previous_quantity = collapsed[key]
                collapsed[key] = (
                    stronger(previous_role, role),
                    merge_quantities(previous_quantity, quantity),
                )
            else:
                collapsed[key] = (role, quantity[:MAX_QUANTITY_CHARS] if quantity else None)

        if not collapsed:
            page.state = ImportState.SKIPPED
            page.skipped_reason = EMPTY_REASON[:200]
            skipped += 1
            continue

        text = f"{page.payload.get('title', '')}. {page.payload.get('description') or ''}"
        try:
            embedding = (await provider.embed_passages([text]))[0]
        except EmbeddingUnavailable as exc:
            # il vettore è un ornamento: la ricetta vale anche senza. `app.cli.reindex`
            # li calcola dopo, quando il modello c'è.
            embedding = None
            log_degradation_once(exc)

        recipe = await create_recipe(
            session,
            title=str(page.payload.get("title") or "Senza titolo")[:200],
            description=page.payload.get("description"),
            instructions=str(page.payload.get("instructions") or ""),
            servings=page.payload.get("servings"),
            source=RecipeSource.DATASET,
            source_ref=page.url,
            ingredients=[
                (ingredient_id, role, quantity, None)
                for ingredient_id, (role, quantity) in collapsed.items()
            ],
            embedding=embedding,
        )
        recipe.category = page.payload.get("category")
        recipe.image_url = page.payload.get("image_url")
        recipe.prep_minutes = page.payload.get("prep_minutes")
        recipe.cook_minutes = page.payload.get("cook_minutes")
        page.state = ImportState.IMPORTED
        page.recipe_id = recipe.id
        created += 1

    await session.flush()
    return Materialized(created=created, skipped=skipped)
```

Nota: `create_recipe` vuole `ingredient_id` come `uuid.UUID`, e le chiavi di
`collapsed` sono stringhe. Converti con `uuid.UUID(ingredient_id)` nella
comprensione, oppure usa direttamente `term.ingredient_id` come chiave del
dizionario: gli UUID sono hashabili, e questa è la versione da preferire. Se scegli
la seconda, togli `str(...)` e l'import di `uuid` non serve.

- [ ] **Step 4: Esegui i test**

Run: `cd backend && pytest tests/services/test_materialize.py -v`
Expected: PASS

- [ ] **Step 5: Prove di mutazione, tre**

1. Togli il collasso (inserisci una riga per ogni voce): deve fallire
   `test_due_righe_sullo_stesso_ingrediente_diventano_una` con un errore di vincolo.
2. Cambia `stronger` perché restituisca sempre `second`: deve fallire
   `test_nel_collasso_il_ruolo_piu_forte_vince`.
3. Togli il controllo `if not collapsed`: deve fallire
   `test_una_ricetta_che_resterebbe_vuota_si_scarta_col_motivo`.

Rimetti tutto come prima dopo ognuna.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/recipe_import/materialize.py \
        backend/tests/services/test_materialize.py
git commit -m "feat: le ricette entrano quando i loro termini sono decisi, duplicati collassati"
```

---

## Task 9: il comando di scarico

**Files:**
- Create: `backend/app/cli/import_gz.py`
- Test: `backend/tests/test_import_gz_cli.py`

**Interfaces:**
- Consumes: `build_client`, `fetch_sitemap`, `fetch_page`, `parse_recipe`,
  `UnparsablePage`, `SourceUnavailable`, `DELAY_SECONDS`, `MAX_CONSECUTIVE_FAILURES`
  dal Task 5 e 6; `known_urls`, `store_page`, `store_unparsable`, `counts` dal
  Task 7; `sync_terms` dal Task 7; `materialize_ready` dal Task 8.
- Produces, da `app.cli.import_gz`:
  `ImportRun(taken: int, skipped: int, stopped_early: bool)`,
  `async def run_import(session, *, limit, client, sleep=asyncio.sleep) -> ImportRun`,
  `async def main() -> None`.

La pausa è iniettabile e il client è un parametro: senza, il test del comando
dormirebbe davvero e parlerebbe con GialloZafferano, contro la regola di casa per cui
la suite non tocca la rete.

- [ ] **Step 1: Scrivi i test**

`backend/tests/test_import_gz_cli.py`:

```python
import httpx
import respx
from sqlalchemy import select

from app.cli.import_gz import run_import
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportState, RecipeImport
from app.services.recipe_import.giallozafferano import RECIPE_SITEMAP, build_client

PAGINA = """<html><head>
<script type="application/ld+json">
{"@type": "Recipe", "name": "TITOLO", "description": "Breve",
 "recipeYield": 2, "prepTime": "PT5M", "cookTime": "PT10M",
 "recipeCategory": "Primi piatti",
 "recipeInstructions": ["Cuoci 1 ."]}
</script></head><body>
<dl class="gz-list-ingredients">
<dd class="gz-ingredient"><a href="/ricette-con-la-Pasta/">Pasta</a><span> 320 g </span></dd>
</dl></body></html>"""

SITEMAP = """<?xml version="1.0"?><urlset>
 <url><loc>https://ricette.giallozafferano.it/Uno.html</loc></url>
 <url><loc>https://ricette.giallozafferano.it/Due.html</loc></url>
 <url><loc>https://ricette.giallozafferano.it/Tre.html</loc></url>
</urlset>"""


async def nessuna_pausa(_seconds: float) -> None:
    """La suite non dorme: la cortesia si verifica contando le chiamate."""


@respx.mock
async def test_scarica_fino_al_limite_e_non_oltre(db_session):
    respx.get(RECIPE_SITEMAP).mock(return_value=httpx.Response(200, text=SITEMAP))
    for nome in ("Uno", "Due", "Tre"):
        respx.get(f"https://ricette.giallozafferano.it/{nome}.html").mock(
            return_value=httpx.Response(200, text=PAGINA.replace("TITOLO", nome))
        )

    async with build_client() as client:
        esito = await run_import(db_session, limit=2, client=client, sleep=nessuna_pausa)

    assert esito.taken == 2
    pagine = (await db_session.execute(select(RecipeImport))).scalars().all()
    assert {p.url for p in pagine} == {
        "https://ricette.giallozafferano.it/Uno.html",
        "https://ricette.giallozafferano.it/Due.html",
    }


@respx.mock
async def test_aspetta_fra_una_pagina_e_l_altra(db_session):
    respx.get(RECIPE_SITEMAP).mock(return_value=httpx.Response(200, text=SITEMAP))
    for nome in ("Uno", "Due", "Tre"):
        respx.get(f"https://ricette.giallozafferano.it/{nome}.html").mock(
            return_value=httpx.Response(200, text=PAGINA.replace("TITOLO", nome))
        )
    pause: list[float] = []

    async def registra(seconds: float) -> None:
        pause.append(seconds)

    async with build_client() as client:
        await run_import(db_session, limit=3, client=client, sleep=registra)

    assert len(pause) == 3
    assert all(seconds >= 1.0 for seconds in pause)


@respx.mock
async def test_una_pagina_gia_presa_non_si_riscarica(db_session):
    respx.get(RECIPE_SITEMAP).mock(return_value=httpx.Response(200, text=SITEMAP))
    chiamate = respx.get("https://ricette.giallozafferano.it/Uno.html").mock(
        return_value=httpx.Response(200, text=PAGINA.replace("TITOLO", "Uno"))
    )
    respx.get("https://ricette.giallozafferano.it/Due.html").mock(
        return_value=httpx.Response(200, text=PAGINA.replace("TITOLO", "Due"))
    )

    async with build_client() as client:
        await run_import(db_session, limit=1, client=client, sleep=nessuna_pausa)
        await run_import(db_session, limit=1, client=client, sleep=nessuna_pausa)

    assert chiamate.call_count == 1


@respx.mock
async def test_una_pagina_illeggibile_si_conserva_col_motivo(db_session):
    respx.get(RECIPE_SITEMAP).mock(return_value=httpx.Response(200, text=SITEMAP))
    respx.get("https://ricette.giallozafferano.it/Uno.html").mock(
        return_value=httpx.Response(200, text="<html>niente dati strutturati</html>")
    )

    async with build_client() as client:
        esito = await run_import(db_session, limit=1, client=client, sleep=nessuna_pausa)

    assert esito.skipped == 1
    pagina = (await db_session.execute(select(RecipeImport))).scalars().one()
    assert pagina.state == ImportState.SKIPPED
    assert pagina.skipped_reason


@respx.mock
async def test_due_rifiuti_di_fila_fermano_il_giro(db_session):
    """Insistere contro un 429 è la cosa da non fare, e il lavoro fatto non si perde."""
    respx.get(RECIPE_SITEMAP).mock(return_value=httpx.Response(200, text=SITEMAP))
    respx.get("https://ricette.giallozafferano.it/Uno.html").mock(
        return_value=httpx.Response(200, text=PAGINA.replace("TITOLO", "Uno"))
    )
    respx.get("https://ricette.giallozafferano.it/Due.html").mock(
        return_value=httpx.Response(429)
    )
    terza = respx.get("https://ricette.giallozafferano.it/Tre.html").mock(
        return_value=httpx.Response(429)
    )

    async with build_client() as client:
        esito = await run_import(db_session, limit=3, client=client, sleep=nessuna_pausa)

    assert esito.stopped_early is True
    assert esito.taken == 1
    # la terza viene chiesta (è il secondo rifiuto, quello che fa scattare il freno)
    # e nessuna quarta: il giro si ferma lì
    assert terza.call_count == 1
    pagine = (await db_session.execute(select(RecipeImport))).scalars().all()
    assert [p.url for p in pagine] == ["https://ricette.giallozafferano.it/Uno.html"]


@respx.mock
async def test_lo_scarico_sincronizza_i_termini_e_materializza(db_session):
    """Un giro completo: con l'anagrafica che conosce già `pasta`, la ricetta entra
    senza nessuna revisione."""
    db_session.add(
        Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
    )
    await db_session.flush()
    respx.get(RECIPE_SITEMAP).mock(return_value=httpx.Response(200, text=SITEMAP))
    respx.get("https://ricette.giallozafferano.it/Uno.html").mock(
        return_value=httpx.Response(200, text=PAGINA.replace("TITOLO", "Uno"))
    )

    async with build_client() as client:
        await run_import(db_session, limit=1, client=client, sleep=nessuna_pausa)

    from app.db.models.recipe import Recipe

    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    assert ricetta.title == "Uno"
    assert ricetta.source_ref == "https://ricette.giallozafferano.it/Uno.html"
```

Le fixture di questo file sono solo `db_session`, che arriva da `conftest.py`.

- [ ] **Step 2: Verifica che i test falliscano**

Run: `cd backend && pytest tests/test_import_gz_cli.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.cli.import_gz'`

- [ ] **Step 3: Implementa**

`backend/app/cli/import_gz.py`:

```python
"""Scarico di un lotto di ricette da GialloZafferano.

Eseguire con `python -m app.cli.import_gz --limit 200` dentro il container del
backend. Rieseguibile: le pagine già presenti non si riscaricano, quindi rilanciarlo
prende il lotto successivo.

Sulla decisione di scaricare, e sul `robots.txt` della fonte che vieta
esplicitamente i crawler AI, vedi §3 dello spec. Questo comando non è quei crawler,
e si comporta di conseguenza: una pagina alla volta, con pausa, mai due volte la
stessa, e si ferma quando il sito chiede di smettere.
"""

import argparse
import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.db.models.recipe_import import GIALLOZAFFERANO
from app.repositories.imports import counts, known_urls, store_page, store_unparsable
from app.services.recipe_import.giallozafferano import (
    DELAY_SECONDS,
    MAX_CONSECUTIVE_FAILURES,
    SourceUnavailable,
    UnparsablePage,
    build_client,
    fetch_page,
    fetch_sitemap,
    parse_recipe,
)
from app.services.recipe_import.materialize import materialize_ready
from app.services.recipe_import.terms import sync_terms

DEFAULT_LIMIT = 50  # prudente di proposito: il lotto si rilancia, la cortesia no


@dataclass(frozen=True)
class ImportRun:
    taken: int
    skipped: int
    stopped_early: bool


async def run_import(
    session: AsyncSession,
    *,
    limit: int,
    client: httpx.AsyncClient,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> ImportRun:
    """Prende fino a `limit` pagine nuove, le analizza e le salva.

    `sleep` è un parametro perché la suite non dorme e non tocca la rete: il test
    conta le pause invece di aspettarle.
    """
    urls = await fetch_sitemap(client)
    already = await known_urls(session, GIALLOZAFFERANO)
    todo = [url for url in urls if url not in already][:limit]

    taken = 0
    skipped = 0
    consecutive_failures = 0
    stopped_early = False

    for url in todo:
        await sleep(DELAY_SECONDS)
        try:
            html = await fetch_page(client, url)
        except SourceUnavailable as exc:
            consecutive_failures += 1
            print(f"la fonte ha rifiutato {url}: {exc}")
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                stopped_early = True
                print(
                    f"{MAX_CONSECUTIVE_FAILURES} rifiuti di fila: mi fermo. "
                    "Le pagine già prese restano salvate, rilancia più tardi."
                )
                break
            continue
        except UnparsablePage as exc:
            consecutive_failures = 0
            await store_unparsable(
                session, source=GIALLOZAFFERANO, url=url, reason=exc.reason
            )
            skipped += 1
            continue

        consecutive_failures = 0
        try:
            recipe = parse_recipe(html)
        except UnparsablePage as exc:
            await store_unparsable(
                session, source=GIALLOZAFFERANO, url=url, reason=exc.reason
            )
            skipped += 1
            continue

        await store_page(
            session, source=GIALLOZAFFERANO, url=url, payload=recipe.as_payload()
        )
        taken += 1

    # i termini si allineano sempre, anche dopo un giro fermato a metà: le pagine
    # prese devono comparire in coda, altrimenti il lavoro fatto non si vede
    await sync_terms(session, GIALLOZAFFERANO)
    await materialize_ready(session, GIALLOZAFFERANO)
    return ImportRun(taken=taken, skipped=skipped, stopped_early=stopped_early)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Scarica un lotto di ricette.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    arguments = parser.parse_args()

    async with SessionLocal() as session:
        async with build_client() as client:
            esito = await run_import(session, limit=arguments.limit, client=client)
        numeri = await counts(session, GIALLOZAFFERANO)
        await session.commit()

    print(f"prese {esito.taken} pagine, scartate {esito.skipped}")
    print(
        f"ricettario: {numeri.imported} importate, {numeri.pending_recipes} in attesa, "
        f"{numeri.skipped} scartate in tutto"
    )
    if numeri.pending_terms:
        print(
            f"{numeri.pending_terms} ingredienti da abbinare: aprili dal ricettario, "
            "alla riga in cima. Le ricette entrano da sé mentre decidi."
        )


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Esegui i test**

Run: `cd backend && pytest tests/test_import_gz_cli.py -v`
Expected: PASS

- [ ] **Step 5: Prova di mutazione**

Togli `[:limit]` dalla costruzione di `todo` e riesegui: deve fallire
`test_scarica_fino_al_limite_e_non_oltre`. Poi togli il controllo su
`consecutive_failures` e riesegui: deve fallire
`test_due_rifiuti_di_fila_fermano_il_giro`. Rimetti tutto come prima.

- [ ] **Step 6: Commit**

```bash
git add backend/app/cli/import_gz.py backend/tests/test_import_gz_cli.py
git commit -m "feat: il comando di scarico, con la pausa iniettabile e il freno sui rifiuti"
```

---

## Task 10: il comando che calcola i vettori mancanti

**Files:**
- Create: `backend/app/cli/reindex.py`
- Test: `backend/tests/test_reindex_cli.py`

**Interfaces:**
- Produces, da `app.cli.reindex`:
  `async def reindex(session) -> int` (quanti vettori ha scritto),
  `async def main() -> None`.

Perché questo comando esiste, e perché sta in questo piano. L'immagine di produzione
è costruita con `INSTALL_EMBEDDINGS=0`, quindi ogni ricetta importata nasce senza
vettore, e il seme attuale si scusa in una riga di stampa dicendo che rieseguirlo non
rimedia. Con 26 ricette è un fastidio; con 500 è la ricerca semantica spenta per
sempre. Chiude anche il vicolo cieco che esisteva già.

- [ ] **Step 1: Scrivi i test**

`backend/tests/test_reindex_cli.py`:

```python
import pytest
from sqlalchemy import select

from app.cli.reindex import reindex
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import Recipe
from app.db.models.recipe import EMBEDDING_DIM
from app.repositories.recipes import create_recipe


async def una_ricetta(db_session, titolo: str, embedding: list[float] | None) -> Recipe:
    ingrediente = Ingredient(
        name=titolo.lower(), display_name=titolo, category=IngredientCategory.ALTRO
    )
    db_session.add(ingrediente)
    await db_session.flush()
    return await create_recipe(
        db_session, title=titolo, description="Breve", instructions="Cuoci.",
        servings=2, source="dataset", source_ref=None,
        ingredients=[(ingrediente.id, "primary", "1", None)], embedding=embedding,
    )


async def test_scrive_i_vettori_mancanti(db_session):
    await una_ricetta(db_session, "Senza", None)

    scritti = await reindex(db_session)

    assert scritti == 1
    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    assert ricetta.embedding is not None
    assert len(ricetta.embedding) == EMBEDDING_DIM


async def test_lascia_in_pace_i_vettori_che_ci_sono(db_session):
    presente = [0.5] * EMBEDDING_DIM
    await una_ricetta(db_session, "Con", presente)

    scritti = await reindex(db_session)

    assert scritti == 0
    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    assert list(ricetta.embedding) == pytest.approx(presente)


async def test_su_un_ricettario_gia_completo_non_fa_niente(db_session):
    assert await reindex(db_session) == 0


async def test_senza_modello_lo_dice_invece_di_tacere(db_session, monkeypatch):
    """Un comando che «riesce» scrivendo zero vettori è indistinguibile da uno che
    non serviva: la differenza va detta, ed è il motivo per cui l'eccezione risale."""
    from app.services.embeddings import EmbeddingUnavailable

    await una_ricetta(db_session, "Senza", None)

    class ProviderRotto:
        async def embed_passages(self, texts):
            raise EmbeddingUnavailable("modello non installato")

        async def embed_query(self, text):
            raise EmbeddingUnavailable("modello non installato")

    monkeypatch.setattr("app.cli.reindex.get_embedding_provider", lambda: ProviderRotto())

    with pytest.raises(EmbeddingUnavailable):
        await reindex(db_session)
```

- [ ] **Step 2: Verifica che i test falliscano**

Run: `cd backend && pytest tests/test_reindex_cli.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'app.cli.reindex'`

- [ ] **Step 3: Implementa**

`backend/app/cli/reindex.py`:

```python
"""Calcola i vettori delle ricette che non ne hanno.

Eseguire con `python -m app.cli.reindex` dentro il container del backend, dopo un
import, se si tiene accesa la ricerca semantica (`INSTALL_EMBEDDINGS=1`).

Esiste perché una ricetta salvata senza vettore non lo riceveva mai più: il seme è
idempotente e non torna sulle ricette già presenti, e l'import eredita la stessa
proprietà. Con 26 ricette era un fastidio, con 500 è la ricerca semantica spenta per
sempre.
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.db.models.recipe import Recipe
from app.services.embeddings import get_embedding_provider

# a lotti, perché un ricettario grande non deve entrare tutto in memoria insieme
BATCH = 64


async def reindex(session: AsyncSession) -> int:
    """Scrive i vettori mancanti e restituisce quanti.

    `EmbeddingUnavailable` risale al chiamante di proposito: un comando che
    «riesce» scrivendo zero vettori è indistinguibile da uno che non serviva, e la
    differenza è esattamente ciò che si vuole sapere.
    """
    provider = get_embedding_provider()
    written = 0
    while True:
        rows = await session.execute(
            select(Recipe).where(Recipe.embedding.is_(None)).limit(BATCH)
        )
        batch = list(rows.scalars())
        if not batch:
            return written
        texts = [f"{recipe.title}. {recipe.description or ''}" for recipe in batch]
        vectors = await provider.embed_passages(texts)
        for recipe, vector in zip(batch, vectors, strict=True):
            recipe.embedding = vector
        await session.flush()
        written += len(batch)


async def main() -> None:
    async with SessionLocal() as session:
        scritti = await reindex(session)
        await session.commit()
    if scritti:
        print(f"scritti {scritti} vettori: la ricerca semantica li vede adesso")
    else:
        print("nessun vettore da scrivere: tutte le ricette ne hanno già uno")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Esegui i test**

Run: `cd backend && pytest tests/test_reindex_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/cli/reindex.py backend/tests/test_reindex_cli.py
git commit -m "feat: i vettori mancanti si possono calcolare dopo, e il comando lo dice"
```

---

## Task 11: le proposte di Claude

**Files:**
- Modify: `backend/app/services/recipe_import/terms.py`
- Test: `backend/tests/services/test_term_proposals.py`

**Interfaces:**
- Consumes: `AiUnavailable` da `app.services.ai_recipes`; `ImportTerm` dal Task 1.
- Produces, da `app.services.recipe_import.terms`:
  `PROPOSAL_MODEL = "claude-sonnet-5"`, `MAX_TERMS_PER_CALL = 40`,
  `TermProposal(term_id: uuid.UUID, action: str, ingredient_id: uuid.UUID | None,
  name: str | None, display_name: str | None, category: str | None)`,
  `async def propose_decisions(session, terms, client=None) -> list[TermProposal]`.

Claude propone, non decide. Una proposta non si applica mai da sé, e una proposta non
verificabile si scarta invece di essere mostrata: un nome di ingrediente che non
esiste in anagrafica, o una categoria inventata, sono rumore travestito da dato.

Le `action` possibili sono `"map"`, `"create"` e `"ignore"`, le stesse tre della
decisione umana.

- [ ] **Step 1: Scrivi i test**

`backend/tests/services/test_term_proposals.py`:

```python
import json

import pytest
import pytest_asyncio

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.services.ai_recipes import AiUnavailable
from app.services.recipe_import.terms import propose_decisions


class FakeClaude:
    """Sostituisce il client Anthropic: la suite non fa rete."""

    def __init__(self, payload: object) -> None:
        self._payload = payload
        self.messages = self

    async def create(self, **kwargs):
        self.last_kwargs = kwargs
        if isinstance(self._payload, Exception):
            raise self._payload

        class Block:
            text = self._payload if isinstance(self._payload, str) else json.dumps(self._payload)

        class Response:
            content = [Block()]

        return Response()


@pytest_asyncio.fixture
async def termini(db_session):
    db_session.add(
        Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
    )
    rigatoni = ImportTerm(
        source=GIALLOZAFFERANO, term_key="ricette-con-i-Rigatoni", display_name="Rigatoni",
        occurrences=12, decision=TermDecision.PENDING,
    )
    speck = ImportTerm(
        source=GIALLOZAFFERANO, term_key="ricette-con-lo-Speck", display_name="Speck",
        occurrences=4, decision=TermDecision.PENDING,
    )
    acqua = ImportTerm(
        source=GIALLOZAFFERANO, term_key="ricette-con-Acqua", display_name="Acqua",
        occurrences=7, decision=TermDecision.PENDING,
    )
    db_session.add_all([rigatoni, speck, acqua])
    await db_session.flush()
    return [rigatoni, speck, acqua]


async def test_le_tre_azioni_arrivano_tradotte(db_session, termini):
    risposta = {
        "proposals": [
            {"term": "Rigatoni", "action": "map", "ingredient": "pasta"},
            {"term": "Speck", "action": "create", "name": "speck",
             "display_name": "Speck", "category": "carne"},
            {"term": "Acqua", "action": "ignore"},
        ]
    }

    proposte = await propose_decisions(db_session, termini, client=FakeClaude(risposta))

    per_termine = {p.term_id: p for p in proposte}
    assert per_termine[termini[0].id].action == "map"
    assert per_termine[termini[0].id].ingredient_id is not None
    assert per_termine[termini[1].id].action == "create"
    assert per_termine[termini[1].id].category == "carne"
    assert per_termine[termini[2].id].action == "ignore"


async def test_un_ingrediente_che_non_esiste_non_e_una_proposta(db_session, termini):
    """Una proposta non verificabile è rumore: si scarta, non si mostra."""
    risposta = {
        "proposals": [{"term": "Rigatoni", "action": "map", "ingredient": "bucatini"}]
    }

    proposte = await propose_decisions(db_session, termini, client=FakeClaude(risposta))

    assert proposte == []


async def test_una_categoria_inventata_non_e_una_proposta(db_session, termini):
    risposta = {
        "proposals": [{"term": "Speck", "action": "create", "name": "speck",
                       "display_name": "Speck", "category": "salumeria"}]
    }

    proposte = await propose_decisions(db_session, termini, client=FakeClaude(risposta))

    assert proposte == []


async def test_un_termine_che_non_avevo_chiesto_si_scarta(db_session, termini):
    risposta = {"proposals": [{"term": "Zafferano", "action": "ignore"}]}

    proposte = await propose_decisions(db_session, termini, client=FakeClaude(risposta))

    assert proposte == []


async def test_una_risposta_che_non_e_json_si_dichiara(db_session, termini):
    with pytest.raises(AiUnavailable):
        await propose_decisions(db_session, termini, client=FakeClaude("mi dispiace, ecco:"))


async def test_senza_chiave_configurata_si_dichiara(db_session, termini, monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    try:
        with pytest.raises(AiUnavailable):
            await propose_decisions(db_session, termini)
    finally:
        get_settings.cache_clear()


async def test_si_chiedono_al_massimo_quaranta_termini_per_chiamata(db_session, termini):
    """Il prompt porta l'anagrafica intera: un lotto senza tetto la farebbe crescere
    fino a una chiamata che costa e che il modello tronca."""
    from app.services.recipe_import.terms import MAX_TERMS_PER_CALL

    finto = FakeClaude({"proposals": []})
    await propose_decisions(db_session, termini * 30, client=finto)

    inviati = finto.last_kwargs["messages"][0]["content"]
    assert inviati.count("Rigatoni") <= MAX_TERMS_PER_CALL


async def test_l_anagrafica_arriva_nel_prompt(db_session, termini):
    """Senza l'elenco dei nostri ingredienti il modello propone nomi che non esistono,
    e ogni proposta verrebbe scartata dalla verifica."""
    finto = FakeClaude({"proposals": []})
    await propose_decisions(db_session, termini, client=finto)

    assert "pasta" in finto.last_kwargs["system"] or "pasta" in str(
        finto.last_kwargs["messages"]
    )
```

- [ ] **Step 2: Verifica che i test falliscano**

Run: `cd backend && pytest tests/services/test_term_proposals.py -v`
Expected: FAIL con `ImportError: cannot import name 'propose_decisions'`

- [ ] **Step 3: Implementa**

In coda a `backend/app/services/recipe_import/terms.py`:

```python
import json
import uuid

from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.services.ai_recipes import AiUnavailable, _build_client

PROPOSAL_MODEL = "claude-sonnet-5"
PROPOSAL_MAX_TOKENS = 3000
# il prompt porta l'anagrafica intera: un lotto senza tetto la farebbe crescere fino
# a una chiamata che costa e che il modello tronca a metà
MAX_TERMS_PER_CALL = 40

PROPOSAL_SYSTEM_PROMPT = """Sei un aiuto per mettere in ordine un'anagrafica di ingredienti. Rispondi SOLO con un oggetto JSON valido, senza testo attorno e senza blocchi di codice.

Ricevi una lista di nomi di ingredienti presi da un sito di cucina, e l'anagrafica di un'app di dispensa. Per ognuno dei nomi scegli UNA delle tre azioni:

- "map": è lo stesso ingrediente di uno che esiste già in anagrafica, scritto più in dettaglio. "Rigatoni" è pasta, "Latte intero" è latte.
- "create": è un ingrediente generico che l'anagrafica non ha. Dai il nome canonico in italiano minuscolo e singolare, il nome da mostrare, e la categoria.
- "ignore": non è qualcosa che si tiene in dispensa. L'acqua, il ghiaccio, l'acqua per la cottura.

Schema richiesto:
{
  "proposals": [
    {"term": "il nome ricevuto, identico", "action": "map", "ingredient": "nome canonico esistente"},
    {"term": "...", "action": "create", "name": "...", "display_name": "...", "category": "..."},
    {"term": "...", "action": "ignore"}
  ]
}

Regole:
- "ingredient" deve essere uno dei nomi canonici che ti passo, scritto identico.
- "category" deve essere una delle categorie che ti passo, scritta identica.
- Preferisci "map" quando l'ingrediente esiste già: un'anagrafica con venti formati di pasta non sa più dire cosa c'è in casa.
- Non inserire valori nutrizionali.
"""


@dataclass(frozen=True)
class TermProposal:
    term_id: uuid.UUID
    action: str
    ingredient_id: uuid.UUID | None = None
    name: str | None = None
    display_name: str | None = None
    category: str | None = None


async def propose_decisions(
    session: AsyncSession, terms: list[ImportTerm], client: object | None = None
) -> list[TermProposal]:
    """Una proposta per ogni termine che il modello riesce a giudicare.

    Claude propone e non decide: il risultato va mostrato e confermato. Una proposta
    che non si può verificare — un ingrediente che non esiste, una categoria
    inventata, un termine che non avevo chiesto — si scarta invece di essere
    mostrata: rumore travestito da dato è peggio di nessuna proposta.

    `AiUnavailable` non è un errore da nascondere né da far fallire la coda: chi
    chiama lo traduce in «decidi a mano», che è sempre possibile.
    """
    batch = terms[:MAX_TERMS_PER_CALL]
    if not batch:
        return []

    api = client if client is not None else _build_client()
    anagrafica = list(
        (
            await session.execute(
                select(Ingredient.id, Ingredient.name, Ingredient.category).order_by(
                    Ingredient.name
                )
            )
        ).all()
    )
    by_name = {name: ingredient_id for ingredient_id, name, _ in anagrafica}
    categories = {str(value) for value in IngredientCategory}

    question = json.dumps(
        {
            "termini": [term.display_name for term in batch],
            "anagrafica": [
                {"nome": name, "categoria": category} for _, name, category in anagrafica
            ],
            "categorie": sorted(categories),
        },
        ensure_ascii=False,
    )

    try:
        response = await api.messages.create(
            model=PROPOSAL_MODEL,
            max_tokens=PROPOSAL_MAX_TOKENS,
            system=PROPOSAL_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": question}],
        )
        payload = json.loads(response.content[0].text)
        raw = payload.get("proposals") if isinstance(payload, dict) else None
        if not isinstance(raw, list):
            raise AiUnavailable("la risposta non contiene una lista di proposte")
    except AiUnavailable:
        raise
    except Exception as exc:  # rete, quota, JSON malformato
        raise AiUnavailable(str(exc)) from exc

    by_display = {term.display_name: term for term in batch}
    proposals: list[TermProposal] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        term = by_display.get(str(entry.get("term", "")))
        if term is None:
            continue  # un termine che non avevo chiesto
        action = entry.get("action")
        if action == "ignore":
            proposals.append(TermProposal(term_id=term.id, action="ignore"))
        elif action == "map":
            ingredient_id = by_name.get(str(entry.get("ingredient", "")).strip().lower())
            if ingredient_id is None:
                continue  # un ingrediente che non esiste non è una proposta
            proposals.append(
                TermProposal(term_id=term.id, action="map", ingredient_id=ingredient_id)
            )
        elif action == "create":
            category = str(entry.get("category", "")).strip().lower()
            name = str(entry.get("name", "")).strip().lower()
            if category not in categories or not name:
                continue
            proposals.append(
                TermProposal(
                    term_id=term.id, action="create", name=name,
                    display_name=str(entry.get("display_name") or name).strip(),
                    category=category,
                )
            )
    return proposals
```

`_build_client` è privata in `ai_recipes.py` e qui la si riusa invece di duplicarla:
la costruzione del client è la stessa, compresa la traduzione di «chiave assente» e
«pacchetto non installato» in `AiUnavailable`. Se l'esecutore preferisce non
importare un nome privato, rinominala in `build_claude_client` in `ai_recipes.py` e
aggiorna i due chiamanti: è una sostituzione meccanica, non una decisione.

- [ ] **Step 4: Esegui i test**

Run: `cd backend && pytest tests/services/test_term_proposals.py -v`
Expected: PASS

- [ ] **Step 5: Prova di mutazione**

Togli il controllo `if ingredient_id is None: continue` e riesegui: deve fallire
`test_un_ingrediente_che_non_esiste_non_e_una_proposta`. Rimetti come prima.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/recipe_import/terms.py backend/tests/services/test_term_proposals.py
git commit -m "feat: Claude propone le decisioni sui termini, e le proposte non verificabili si scartano"
```

---

## Task 12: le rotte dell'import

**Files:**
- Create: `backend/app/schemas/recipe_import.py`
- Create: `backend/app/api/imports.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/api/test_imports.py`

**Interfaces:**
- Consumes: tutto il Task 7, `propose_decisions` dal Task 11, `materialize_ready`
  dal Task 8, `create_ingredient` e `add_alias` da `app.repositories.ingredients`.
- Produces: le quattro rotte sotto `/api/v1/imports`, tutte dietro `require_session`.

| Rotta | Risposta |
|---|---|
| `GET /status` | `{fetched, pending_recipes, imported, skipped, pending_terms}` |
| `GET /terms?limit=20` | `[{id, display_name, occurrences, suggestion, waiting_titles}]` |
| `POST /terms/proposals` | `{term_ids: [...]}` → `{proposals: [...]}`, `503` se Claude non risponde |
| `POST /terms/{id}/decision` | `{action, ...}` → `{unlocked, remaining_terms}` |

Collegare un termine scrive anche l'alias nell'anagrafica, **ma solo se quell'alias
non esiste già per nessun ingrediente**: il vincolo del database è su
`(ingredient_id, alias)` e lascerebbe passare lo stesso alias su due ingredienti,
cioè un autocomplete che dà due risposte a una domanda sola. Il legame fra termine e
ingrediente vive comunque su `import_terms`, quindi saltare l'alias non perde niente.

- [ ] **Step 1: Scrivi i test**

`backend/tests/api/test_imports.py`:

```python
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.recipe import Recipe
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.repositories.imports import store_page
from app.services.recipe_import.terms import sync_terms


def payload(title: str, ingredients: list[tuple[str, str, str]]) -> dict:
    return {
        "title": title, "description": "Breve", "instructions": "Cuoci.",
        "servings": 2, "category": "Primi piatti", "image_url": None,
        "prep_minutes": 5, "cook_minutes": 10,
        "ingredients": [
            {"key": key, "name": name, "quantity_text": quantity}
            for key, name, quantity in ingredients
        ],
        "nutrition": None,
    }


@pytest_asyncio.fixture
async def in_attesa(db_session):
    """Una ricetta scaricata che aspetta un solo termine sconosciuto."""
    db_session.add(
        Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
    )
    await db_session.flush()
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/bottarga.html",
        payload=payload("Spaghetti alla bottarga", [
            ("ricette-con-la-Pasta", "Pasta", "320 g"),
            ("ricette-con-la-Bottarga", "Bottarga", "20 g"),
        ]),
    )
    await sync_terms(db_session)


async def test_lo_stato_dice_dove_sta_l_import(logged_client, in_attesa):
    response = await logged_client.get("/api/v1/imports/status")

    assert response.status_code == 200
    assert response.json() == {
        "fetched": 1, "pending_recipes": 1, "imported": 0, "skipped": 0,
        "pending_terms": 1,
    }


async def test_senza_sessione_non_si_guarda_niente(client):
    assert (await client.get("/api/v1/imports/status")).status_code == 401


async def test_la_coda_porta_il_suggerimento_e_i_titoli_in_attesa(logged_client, in_attesa):
    response = await logged_client.get("/api/v1/imports/terms")

    assert response.status_code == 200
    coda = response.json()
    assert [voce["display_name"] for voce in coda] == ["Bottarga"]
    assert coda[0]["occurrences"] == 1
    assert coda[0]["waiting_titles"] == ["Spaghetti alla bottarga"]


async def test_collegare_un_termine_sblocca_le_ricette_e_lo_dice(
    logged_client, db_session, in_attesa
):
    pasta = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "pasta"))
    ).scalars().one()
    termine = (
        await db_session.execute(
            select(ImportTerm).where(ImportTerm.display_name == "Bottarga")
        )
    ).scalars().one()

    response = await logged_client.post(
        f"/api/v1/imports/terms/{termine.id}/decision",
        json={"action": "map", "ingredient_id": str(pasta.id)},
    )

    assert response.status_code == 200
    assert response.json() == {"unlocked": 1, "remaining_terms": 0}
    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    assert ricetta.title == "Spaghetti alla bottarga"


async def test_collegare_scrive_l_alias_in_anagrafica(logged_client, db_session, in_attesa):
    """È ciò che fa valere la decisione per sempre, e che insegna il nome anche
    all'autocomplete della lista della spesa."""
    pasta = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "pasta"))
    ).scalars().one()
    termine = (
        await db_session.execute(
            select(ImportTerm).where(ImportTerm.display_name == "Bottarga")
        )
    ).scalars().one()

    await logged_client.post(
        f"/api/v1/imports/terms/{termine.id}/decision",
        json={"action": "map", "ingredient_id": str(pasta.id)},
    )

    alias = (
        await db_session.execute(
            select(IngredientAlias).where(IngredientAlias.alias == "bottarga")
        )
    ).scalars().all()
    assert [a.ingredient_id for a in alias] == [pasta.id]
    assert alias[0].source == "import"


async def test_un_alias_che_esiste_gia_altrove_non_si_duplica(
    logged_client, db_session, in_attesa
):
    """Lo stesso alias su due ingredienti è un autocomplete con due risposte."""
    altro = Ingredient(
        name="muggine", display_name="Muggine", category=IngredientCategory.PESCE
    )
    altro.aliases.append(IngredientAlias(alias="bottarga", source="import"))
    db_session.add(altro)
    await db_session.flush()
    pasta = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "pasta"))
    ).scalars().one()
    termine = (
        await db_session.execute(
            select(ImportTerm).where(ImportTerm.display_name == "Bottarga")
        )
    ).scalars().one()

    response = await logged_client.post(
        f"/api/v1/imports/terms/{termine.id}/decision",
        json={"action": "map", "ingredient_id": str(pasta.id)},
    )

    assert response.status_code == 200
    alias = (
        await db_session.execute(
            select(IngredientAlias).where(IngredientAlias.alias == "bottarga")
        )
    ).scalars().all()
    assert [a.ingredient_id for a in alias] == [altro.id], "l'alias esistente resta dov'è"
    await db_session.refresh(termine)
    assert termine.ingredient_id == pasta.id, "la decisione vale comunque"


async def test_creare_un_ingrediente_nuovo_decide_il_termine(
    logged_client, db_session, in_attesa
):
    termine = (
        await db_session.execute(
            select(ImportTerm).where(ImportTerm.display_name == "Bottarga")
        )
    ).scalars().one()

    response = await logged_client.post(
        f"/api/v1/imports/terms/{termine.id}/decision",
        json={"action": "create", "name": "bottarga", "display_name": "Bottarga",
              "category": "pesce"},
    )

    assert response.status_code == 200
    nuovo = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "bottarga"))
    ).scalars().one()
    assert nuovo.category == "pesce"
    await db_session.refresh(termine)
    assert termine.ingredient_id == nuovo.id
    assert termine.decided_by == "human"


async def test_creare_un_nome_che_esiste_gia_dice_di_collegare(
    logged_client, db_session, in_attesa
):
    termine = (
        await db_session.execute(
            select(ImportTerm).where(ImportTerm.display_name == "Bottarga")
        )
    ).scalars().one()

    response = await logged_client.post(
        f"/api/v1/imports/terms/{termine.id}/decision",
        json={"action": "create", "name": "pasta", "display_name": "Pasta",
              "category": "cereali"},
    )

    assert response.status_code == 409
    assert "collega" in response.json()["detail"]


async def test_ignorare_un_termine_lo_toglie_dalla_coda(logged_client, db_session, in_attesa):
    termine = (
        await db_session.execute(
            select(ImportTerm).where(ImportTerm.display_name == "Bottarga")
        )
    ).scalars().one()

    response = await logged_client.post(
        f"/api/v1/imports/terms/{termine.id}/decision", json={"action": "ignore"}
    )

    assert response.status_code == 200
    assert response.json()["remaining_terms"] == 0
    await db_session.refresh(termine)
    assert termine.decision == TermDecision.IGNORED


async def test_un_termine_inesistente_e_un_404(logged_client, in_attesa):
    response = await logged_client.post(
        "/api/v1/imports/terms/00000000-0000-0000-0000-000000000000/decision",
        json={"action": "ignore"},
    )

    assert response.status_code == 404


async def test_collegare_a_un_ingrediente_inesistente_e_un_404(
    logged_client, db_session, in_attesa
):
    termine = (
        await db_session.execute(
            select(ImportTerm).where(ImportTerm.display_name == "Bottarga")
        )
    ).scalars().one()

    response = await logged_client.post(
        f"/api/v1/imports/terms/{termine.id}/decision",
        json={"action": "map",
              "ingredient_id": "00000000-0000-0000-0000-000000000000"},
    )

    assert response.status_code == 404


async def test_senza_claude_le_proposte_dicono_di_decidere_a_mano(
    logged_client, db_session, in_attesa, monkeypatch
):
    """La coda resta usabile: è la regola «mai un vicolo cieco»."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    termine = (
        await db_session.execute(
            select(ImportTerm).where(ImportTerm.display_name == "Bottarga")
        )
    ).scalars().one()
    try:
        response = await logged_client.post(
            "/api/v1/imports/terms/proposals", json={"term_ids": [str(termine.id)]}
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 503
    assert "a mano" in response.json()["detail"]
```

- [ ] **Step 2: Verifica che i test falliscano**

Run: `cd backend && pytest tests/api/test_imports.py -v`
Expected: FAIL con `404` su ogni rotta, perché il router non esiste ancora

- [ ] **Step 3: Scrivi gli schemi**

`backend/app/schemas/recipe_import.py`:

```python
import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.db.models.ingredient import IngredientCategory
from app.domain.rules import IngredientRole


class ImportStatusOut(BaseModel):
    fetched: int
    pending_recipes: int
    imported: int
    skipped: int
    pending_terms: int


class SuggestionOut(BaseModel):
    ingredient_id: uuid.UUID
    name: str
    certain: bool


class TermOut(BaseModel):
    id: uuid.UUID
    display_name: str
    occurrences: int
    suggestion: SuggestionOut | None
    # qualche titolo in attesa: «Scorza di limone» si giudica diversamente in una
    # torta e in un arrosto
    waiting_titles: list[str]


class ProposalsRequest(BaseModel):
    term_ids: list[uuid.UUID] = Field(min_length=1, max_length=40)


class ProposalOut(BaseModel):
    term_id: uuid.UUID
    action: Literal["map", "create", "ignore"]
    ingredient_id: uuid.UUID | None = None
    name: str | None = None
    display_name: str | None = None
    category: str | None = None


class ProposalsOut(BaseModel):
    proposals: list[ProposalOut]


class TermDecisionIn(BaseModel):
    """Le tre azioni in un solo corpo: l'API le distingue su `action`.

    Un corpo per azione avrebbe significato tre rotte per una decisione sola, e tre
    posti da cui far partire la materializzazione.
    """

    action: Literal["map", "create", "ignore"]
    ingredient_id: uuid.UUID | None = None
    name: str | None = Field(default=None, max_length=120)
    display_name: str | None = Field(default=None, max_length=120)
    category: IngredientCategory | None = None
    role_override: IngredientRole | None = None


class DecisionOut(BaseModel):
    unlocked: int
    remaining_terms: int
```

- [ ] **Step 4: Scrivi le rotte**

`backend/app/api/imports.py`:

```python
"""Le rotte della revisione dell'import.

Una sola decisione per chiamata, e ogni decisione materializza subito le ricette che
aspettavano quel termine: il numero che torna — «sbloccate dodici ricette» — è ciò
che rende la revisione un lavoro con un risultato visibile invece di un modulo da
compilare.

Le proposte di Claude stanno in una rotta separata dall'elenco di proposito: la coda
deve caricarsi subito, e un guasto del modello non deve poter svuotare una schermata
che funziona anche senza.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import require_session
from app.db.models.ingredient import Ingredient, IngredientAlias
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.repositories.imports import counts, get_term, pending_terms, waiting_titles
from app.repositories.ingredients import add_alias, create_ingredient
from app.schemas.recipe_import import (
    DecisionOut,
    ImportStatusOut,
    ProposalOut,
    ProposalsOut,
    ProposalsRequest,
    SuggestionOut,
    TermDecisionIn,
    TermOut,
)
from app.services.ai_recipes import AiUnavailable
from app.services.ingredient_match import match_name
from app.services.recipe_import.materialize import materialize_ready
from app.services.recipe_import.terms import propose_decisions

router = APIRouter(
    prefix="/api/v1/imports", tags=["imports"], dependencies=[Depends(require_session)]
)


@router.get("/status", response_model=ImportStatusOut)
async def read_status(session: AsyncSession = Depends(get_session)) -> ImportStatusOut:
    numbers = await counts(session, GIALLOZAFFERANO)
    return ImportStatusOut(**vars(numbers))


@router.get("/terms", response_model=list[TermOut])
async def read_terms(
    limit: int = Query(default=20, le=50),
    session: AsyncSession = Depends(get_session),
) -> list[TermOut]:
    terms = await pending_terms(session, GIALLOZAFFERANO, limit=limit)
    titles = await waiting_titles(
        session, GIALLOZAFFERANO, [term.term_key for term in terms]
    )

    out: list[TermOut] = []
    for term in terms:
        match = await match_name(session, term.display_name)
        suggestion = (
            SuggestionOut(
                ingredient_id=match.ingredient_id, name=match.name, certain=match.certain
            )
            if match.ingredient_id is not None and match.name is not None
            else None
        )
        out.append(
            TermOut(
                id=term.id, display_name=term.display_name, occurrences=term.occurrences,
                suggestion=suggestion, waiting_titles=titles.get(term.term_key, []),
            )
        )
    return out


@router.post("/terms/proposals", response_model=ProposalsOut)
async def read_proposals(
    payload: ProposalsRequest, session: AsyncSession = Depends(get_session)
) -> ProposalsOut:
    rows = await session.execute(
        select(ImportTerm).where(ImportTerm.id.in_(payload.term_ids))
    )
    terms = list(rows.scalars())
    if not terms:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "nessuno di questi termini esiste")

    try:
        proposals = await propose_decisions(session, terms)
    except AiUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"le proposte non sono disponibili ({exc}): decidi a mano, la coda funziona.",
        ) from exc
    return ProposalsOut(proposals=[ProposalOut(**vars(p)) for p in proposals])


@router.post("/terms/{term_id}/decision", response_model=DecisionOut)
async def decide(
    term_id: uuid.UUID,
    payload: TermDecisionIn,
    session: AsyncSession = Depends(get_session),
) -> DecisionOut:
    term = await get_term(session, term_id)
    if term is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "termine inesistente")

    if payload.action == "ignore":
        term.decision = TermDecision.IGNORED
        term.ingredient_id = None
    else:
        if payload.action == "map":
            if payload.ingredient_id is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "per collegare serve l'ingrediente",
                )
            ingredient = await session.get(Ingredient, payload.ingredient_id)
            if ingredient is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "ingrediente inesistente")
        else:
            if not payload.name or payload.category is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "per creare un ingrediente servono nome e categoria",
                )
            existing = (
                await session.execute(
                    select(Ingredient).where(Ingredient.name == payload.name.strip().lower())
                )
            ).scalars().first()
            if existing is not None:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"«{existing.name}» è già in anagrafica: collega il termine invece "
                    "di creare un doppione.",
                )
            ingredient = await create_ingredient(
                session, name=payload.name,
                display_name=payload.display_name or payload.name,
                category=payload.category,
            )

        term.decision = TermDecision.MAPPED
        term.ingredient_id = ingredient.id
        await _remember_alias(session, ingredient.id, term.display_name)

    term.role_override = payload.role_override
    term.decided_by = "human"
    term.decided_at = datetime.now(UTC)
    await session.flush()

    materialized = await materialize_ready(session, GIALLOZAFFERANO)
    numbers = await counts(session, GIALLOZAFFERANO)
    await session.commit()
    return DecisionOut(unlocked=materialized.created, remaining_terms=numbers.pending_terms)


async def _remember_alias(
    session: AsyncSession, ingredient_id: uuid.UUID, display_name: str
) -> None:
    """L'alias è ciò che fa valere la decisione per sempre, e anche fuori dall'import.

    Si scrive solo se quell'alias non esiste già per nessun ingrediente: il vincolo
    del database è su `(ingredient_id, alias)` e lascerebbe passare lo stesso alias
    su due ingredienti diversi, cioè un autocomplete che dà due risposte a una
    domanda sola. Il legame fra termine e ingrediente vive su `import_terms`, quindi
    saltarlo non perde la decisione.
    """
    alias = display_name.strip().lower()
    if not alias:
        return
    already = (
        await session.execute(
            select(IngredientAlias).where(IngredientAlias.alias == alias)
        )
    ).scalars().first()
    if already is not None:
        return
    await add_alias(session, ingredient_id, alias, source="import")
```

- [ ] **Step 5: Registra il router**

In `backend/app/main.py`, accanto agli altri `include_router`:

```python
from app.api import imports

app.include_router(imports.router)
```

Rispetta l'ordine e lo stile delle righe già presenti nel file.

- [ ] **Step 6: Esegui i test**

Run: `cd backend && pytest tests/api/test_imports.py -v`
Expected: PASS

- [ ] **Step 7: Prova di mutazione**

In `_remember_alias`, togli il controllo `if already is not None: return` e riesegui:
deve fallire `test_un_alias_che_esiste_gia_altrove_non_si_duplica`. Poi togli la
chiamata a `materialize_ready` dentro `decide` e riesegui: deve fallire
`test_collegare_un_termine_sblocca_le_ricette_e_lo_dice`. Rimetti tutto come prima.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/recipe_import.py backend/app/api/imports.py \
        backend/app/main.py backend/tests/api/test_imports.py
git commit -m "feat: le rotte della revisione, e una decisione che sblocca ricette subito"
```

---

## Task 13: il ricettario grande rompe due cose, e questa è la prima

**Files:**
- Modify: `backend/app/services/recipe_search.py`
- Modify: `backend/app/api/recipes.py`
- Modify: `backend/app/schemas/recipe.py`
- Test: `backend/tests/services/test_recipe_search.py`
- Test: `backend/tests/api/test_recipes.py`

**Interfaces:**
- Produces: `search_recipes(session, query=None, only_cookable=False, limit=30,
  category=None)`; `GET /api/v1/recipes/categories -> list[str]`;
  `RecipeSummaryOut` e `RecipeOut` con `image_url`, `prep_minutes`, `cook_minutes`,
  `category`.

`recipe_search.py` ha `CANDIDATE_POOL = 100` e, senza parole cercate, seleziona le
cento ricette più recenti. Con 26 ricette è tutto il ricettario; con cinquecento
diventa un campione, e `only_cookable` filtra **dentro** quel campione. Cioè
«mostrami solo ciò che posso cucinare» smetterebbe di guardare la maggior parte del
ricettario, proprio per effetto dell'import: la domanda centrale dell'app
risponderebbe male. Va riparato qui, perché è questo lavoro a romperlo.

- [ ] **Step 1: Scrivi il test che oggi non esiste**

In coda a `backend/tests/services/test_recipe_search.py`:

```python
async def test_solo_cucinabili_vede_oltre_la_piscina_dei_candidati(db_session):
    """Con più ricette della piscina, il filtro non deve guardare solo le recenti.

    È il difetto che l'import avrebbe introdotto: centinaia di ricette nuove spingono
    fuori dalle cento più recenti proprio quelle che si possono cucinare, e la
    domanda centrale dell'app risponde «niente».
    """
    from app.db.models.ingredient import Ingredient, IngredientCategory
    from app.db.models.pantry import PantryItem
    from app.repositories.recipes import create_recipe
    from app.services.recipe_search import CANDIDATE_POOL, search_recipes

    ho = Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
    non_ho = Ingredient(
        name="bottarga", display_name="Bottarga", category=IngredientCategory.PESCE
    )
    db_session.add_all([ho, non_ho])
    await db_session.flush()
    db_session.add(PantryItem(ingredient_id=ho.id, status="available"))
    await db_session.flush()

    # la cucinabile è la più vecchia: dopo di lei ne arrivano più della piscina
    await create_recipe(
        db_session, title="Pasta in bianco", description="Solo pasta",
        instructions="Cuoci.", servings=2, source="dataset", source_ref=None,
        ingredients=[(ho.id, "primary", "320 g", None)], embedding=None,
    )
    for numero in range(CANDIDATE_POOL + 5):
        await create_recipe(
            db_session, title=f"Bottarga {numero}", description="Non la hai",
            instructions="Cuoci.", servings=2, source="dataset", source_ref=None,
            ingredients=[(non_ho.id, "primary", "20 g", None)], embedding=None,
        )
    await db_session.flush()

    risultati = await search_recipes(db_session, only_cookable=True)

    assert [r.recipe.title for r in risultati] == ["Pasta in bianco"]


async def test_il_filtro_per_categoria_sceglie_in_sql(db_session):
    """Filtrare dopo il limite significherebbe filtrare dentro un campione."""
    from app.db.models.ingredient import Ingredient, IngredientCategory
    from app.repositories.recipes import create_recipe
    from app.services.recipe_search import CANDIDATE_POOL, search_recipes

    ingrediente = Ingredient(
        name="zucchero", display_name="Zucchero", category=IngredientCategory.DOLCI
    )
    db_session.add(ingrediente)
    await db_session.flush()

    dolce = await create_recipe(
        db_session, title="Tiramisù", description="Dolce", instructions="Monta.",
        servings=6, source="dataset", source_ref=None,
        ingredients=[(ingrediente.id, "primary", "100 g", None)], embedding=None,
    )
    dolce.category = "Dolci e Desserts"
    for numero in range(CANDIDATE_POOL + 5):
        primo = await create_recipe(
            db_session, title=f"Primo {numero}", description="Salato",
            instructions="Cuoci.", servings=2, source="dataset", source_ref=None,
            ingredients=[(ingrediente.id, "primary", "1 g", None)], embedding=None,
        )
        primo.category = "Primi piatti"
    await db_session.flush()

    risultati = await search_recipes(db_session, category="Dolci e Desserts")

    assert [r.recipe.title for r in risultati] == ["Tiramisù"]
```

- [ ] **Step 2: Verifica che i test falliscano**

Run: `cd backend && pytest tests/services/test_recipe_search.py -v`
Expected: FAIL. Il primo con una lista vuota, perché la ricetta cucinabile è fuori
dalle cento più recenti. Il secondo con `TypeError: search_recipes() got an
unexpected keyword argument 'category'`.

- [ ] **Step 3: Modifica `search_recipes`**

In `backend/app/services/recipe_search.py`, sostituisci la firma e il blocco dei
candidati:

```python
async def search_recipes(
    session: AsyncSession,
    query: str | None = None,
    only_cookable: bool = False,
    limit: int = 30,
    category: str | None = None,
) -> list[RecipeSearchResult]:
    if query and query.strip():
        semantic = await _semantic_ranking(session, query)
        textual = await _textual_ranking(session, query)
        fused = reciprocal_rank_fusion([semantic, textual])
        candidate_ids = list(fused)
    else:
        statement = select(Recipe.id).order_by(Recipe.created_at.desc())
        if category is not None:
            statement = statement.where(Recipe.category == category)
        # Senza `only_cookable` la piscina basta: è uno scorrimento, e cento ricette
        # recenti sono più di quante se ne guardino. Con `only_cookable` no: il
        # filtro lavora sul risultato, quindi limitare prima significa filtrare
        # dentro un campione, e «cosa posso cucinare» risponderebbe guardando solo
        # le ricette entrate ieri. Misurato: a cinquecento ricette la passata
        # completa non si distingue; oltre qualche migliaio va misurata di nuovo, e
        # se non regge la regola scende in SQL.
        if not only_cookable:
            statement = statement.limit(CANDIDATE_POOL)
        candidate_ids = list((await session.execute(statement)).scalars())
        fused = {recipe_id: 0.0 for recipe_id in candidate_ids}

    if not candidate_ids:
        return []

    requirements = await _requirements_by_recipe(session, candidate_ids)
    recipe_statement = select(Recipe).where(Recipe.id.in_(candidate_ids))
    if category is not None:
        # vale anche sul percorso con le parole cercate: lì i candidati arrivano dal
        # riordino, e far cadere fuori i fuori-categoria qui costa zero query
        recipe_statement = recipe_statement.where(Recipe.category == category)
    recipes = {
        r.id: r
        for r in (await session.execute(recipe_statement)).unique().scalars()
    }
```

Il resto della funzione resta com'è.

- [ ] **Step 4: Porta il filtro fino alla rotta**

In `backend/app/api/recipes.py`, nella rotta `search`, aggiungi il parametro e
passalo:

```python
async def search(
    q: str | None = None,
    only_cookable: bool = False,
    category: str | None = None,
    limit: int = Query(default=30, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[RecipeSummaryOut]:
    results = await search_recipes(session, q, only_cookable, limit, category=category)
```

E aggiungi la rotta delle categorie, **sopra** `/{recipe_id}` per lo stesso motivo
scritto nel commento di `search-mode`: la rotta col parametro mangerebbe la parola.

```python
@router.get("/categories", response_model=list[str])
async def categories(session: AsyncSession = Depends(get_session)) -> list[str]:
    """Le categorie presenti nel ricettario, per il filtro.

    Solo quelle che esistono davvero: un filtro che offre voci vuote è un filtro che
    porta a una schermata vuota.
    """
    rows = await session.execute(
        select(Recipe.category)
        .where(Recipe.category.is_not(None))
        .distinct()
        .order_by(Recipe.category)
    )
    return list(rows.scalars())
```

Poi porta i quattro campi nuovi nelle due risposte. Nella comprensione di `search`:

```python
        RecipeSummaryOut(
            id=r.recipe.id, title=r.recipe.title, description=r.recipe.description,
            source=r.recipe.source, missing=r.missing, cookable=r.cookable,
            image_url=r.recipe.image_url, prep_minutes=r.recipe.prep_minutes,
            cook_minutes=r.recipe.cook_minutes, category=r.recipe.category,
        )
```

E in `_to_out`, dentro la costruzione di `RecipeOut`:

```python
        image_url=recipe.image_url, prep_minutes=recipe.prep_minutes,
        cook_minutes=recipe.cook_minutes, category=recipe.category,
```

- [ ] **Step 5: Aggiungi i campi agli schemi**

In `backend/app/schemas/recipe.py`, dentro `RecipeSummaryOut`:

```python
    image_url: str | None = None
    prep_minutes: int | None = None
    cook_minutes: int | None = None
    category: str | None = None
```

`RecipeOut` estende `RecipeSummaryOut`? No: oggi sono due classi separate e
`RecipeOut` non eredita. Aggiungi le stesse quattro righe anche a `RecipeOut`, con
un commento che dice che sono le stesse: due elenchi uguali in due schemi sono
accettabili, una gerarchia introdotta per risparmiare quattro righe non lo è.

- [ ] **Step 6: Scrivi il test della rotta**

In coda a `backend/tests/api/test_recipes.py`:

```python
async def test_la_scheda_porta_foto_tempo_e_categoria(logged_client, db_session):
    from sqlalchemy import select

    from app.db.models.ingredient import Ingredient, IngredientCategory
    from app.db.models.recipe import Recipe
    from app.repositories.recipes import create_recipe

    ingrediente = Ingredient(
        name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    db_session.add(ingrediente)
    await db_session.flush()
    ricetta = await create_recipe(
        db_session, title="Pasta al pomodoro", description="Di sempre",
        instructions="Cuoci.", servings=2, source="dataset",
        source_ref="https://esempio/pasta.html",
        ingredients=[(ingrediente.id, "primary", "320 g", None)], embedding=None,
    )
    ricetta.image_url = "https://esempio/foto.jpg"
    ricetta.prep_minutes = 10
    ricetta.cook_minutes = 15
    ricetta.category = "Primi piatti"
    await db_session.flush()

    elenco = (await logged_client.get("/api/v1/recipes/search")).json()
    assert elenco[0]["image_url"] == "https://esempio/foto.jpg"
    assert elenco[0]["prep_minutes"] == 10
    assert elenco[0]["category"] == "Primi piatti"

    dettaglio = (await logged_client.get(f"/api/v1/recipes/{ricetta.id}")).json()
    assert dettaglio["cook_minutes"] == 15
    assert dettaglio["source_ref"] == "https://esempio/pasta.html"

    categorie = (await logged_client.get("/api/v1/recipes/categories")).json()
    assert categorie == ["Primi piatti"]

    filtrate = (
        await logged_client.get("/api/v1/recipes/search?category=Dolci")
    ).json()
    assert filtrate == []

    # la rotta delle categorie non deve essere letta come un id di ricetta
    assert (await logged_client.get("/api/v1/recipes/categories")).status_code == 200
```

- [ ] **Step 7: Esegui tutta la suite del backend**

Run: `cd backend && pytest -q`
Expected: PASS. Questo task tocca il modulo più delicato della v1: se cade un test
esistente di `test_recipe_search.py` o `test_semantic_degradation.py`, la modifica ha
cambiato un comportamento che qualcuno difendeva, e va capito quale prima di toccare
il test.

- [ ] **Step 8: Prova di mutazione**

Rimetti `statement = statement.limit(CANDIDATE_POOL)` senza condizione e riesegui:
deve fallire `test_solo_cucinabili_vede_oltre_la_piscina_dei_candidati`, e solo
quello. Rimetti come prima.

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/recipe_search.py backend/app/api/recipes.py \
        backend/app/schemas/recipe.py backend/tests/services/test_recipe_search.py \
        backend/tests/api/test_recipes.py
git commit -m "fix: con tante ricette «solo cucinabili» guardava solo le recenti"
```

---

## Task 14: la coda di revisione

**Files:**
- Create: `frontend/src/domain/categories.ts`
- Create: `frontend/src/features/recipe-import/api.ts`
- Create: `frontend/src/features/recipe-import/TermCard.tsx`
- Create: `frontend/src/features/recipe-import/ImportQueueScreen.tsx`
- Modify: `frontend/src/domain/types.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/features/recipes/RecipeBookScreen.tsx`
- Test: `frontend/src/features/recipe-import/ImportQueueScreen.test.tsx`
- Test: `backend/tests/test_frontend_categories.py`

**Interfaces:**
- Consumes: le quattro rotte del Task 12; `IngredientPicker` da
  `frontend/src/components/IngredientPicker`; le primitive di `components/ui/`.
- Produces: la rotta `/ricette/importa` e i tipi dell'import in `domain/types.ts`.

- [ ] **Step 1: Scrivi i tipi**

In `frontend/src/domain/types.ts`, in coda:

```ts
export interface ImportStatus {
  fetched: number;
  pending_recipes: number;
  imported: number;
  skipped: number;
  pending_terms: number;
}

export interface TermSuggestion {
  ingredient_id: string;
  name: string;
  certain: boolean;
}

export interface ImportTerm {
  id: string;
  display_name: string;
  /** Quante ricette scaricate aspettano questa decisione. Ordina la coda. */
  occurrences: number;
  suggestion: TermSuggestion | null;
  waiting_titles: string[];
}

export type TermAction = "map" | "create" | "ignore";

export interface TermProposal {
  term_id: string;
  action: TermAction;
  ingredient_id: string | null;
  name: string | null;
  display_name: string | null;
  category: string | null;
}

export interface TermDecisionResult {
  unlocked: number;
  remaining_terms: number;
}
```

E aggiungi a `RecipeSummary` i quattro campi che la rotta ora manda:

```ts
  image_url: string | null;
  prep_minutes: number | null;
  cook_minutes: number | null;
  category: string | null;
```

- [ ] **Step 2: Scrivi l'elenco delle categorie e il test che lo tiene allineato**

`frontend/src/domain/categories.ts`:

```ts
/** Le categorie dell'anagrafica, nell'ordine in cui si offrono.
 *
 * Sono i valori di `IngredientCategory` nel backend, ed è l'unico posto del
 * frontend che li nomina. Un valore inventato qui non sarebbe un errore visibile:
 * la creazione dell'ingrediente tornerebbe 422 dal backend, su una schermata che
 * fino a quel momento sembrava funzionare. `backend/tests/test_frontend_categories.py`
 * confronta i due elenchi per impedirlo.
 */
export const INGREDIENT_CATEGORIES = [
  "verdura",
  "frutta",
  "carne",
  "pesce",
  "latticini",
  "cereali",
  "legumi",
  "condimenti",
  "spezie",
  "bevande",
  "dolci",
  "altro",
] as const;
```

`backend/tests/test_frontend_categories.py`:

```python
"""Le categorie scritte nel frontend devono essere quelle che il backend accetta.

Una categoria inventata nel frontend non è un errore visibile: la creazione
dell'ingrediente tornerebbe 422 su una schermata che fino a quel momento sembrava
funzionare. Nello stile di tests/test_compose.py, che legge i file di build per
difendere una forma.
"""

import re
from pathlib import Path

from app.db.models.ingredient import IngredientCategory

REPO_ROOT = Path(__file__).resolve().parents[2]
CATEGORIES_TS = REPO_ROOT / "frontend" / "src" / "domain" / "categories.ts"


def test_il_frontend_offre_esattamente_le_categorie_del_backend():
    contenuto = CATEGORIES_TS.read_text()
    elencate = set(re.findall(r'"([a-z]+)"', contenuto))

    assert elencate == {str(value) for value in IngredientCategory}, (
        f"{CATEGORIES_TS}: l'elenco è {sorted(elencate)}, il backend accetta "
        f"{sorted(str(v) for v in IngredientCategory)}"
    )
```

- [ ] **Step 3: Scrivi le chiamate**

`frontend/src/features/recipe-import/api.ts`:

```ts
import { apiFetch } from "../../api/client";
import type {
  ImportStatus,
  ImportTerm,
  TermDecisionResult,
  TermProposal,
} from "../../domain/types";

export function fetchImportStatus() {
  return apiFetch<ImportStatus>("/imports/status");
}

export function fetchImportTerms() {
  return apiFetch<ImportTerm[]>("/imports/terms");
}

/** Le proposte di Claude, in una chiamata separata dall'elenco di proposito: la coda
 * deve caricarsi subito, e un guasto del modello non deve svuotare una schermata che
 * funziona anche senza. */
export function fetchTermProposals(termIds: string[]) {
  return apiFetch<{ proposals: TermProposal[] }>("/imports/terms/proposals", {
    method: "POST",
    body: JSON.stringify({ term_ids: termIds }),
  });
}

export function decideTerm(
  termId: string,
  body: {
    action: "map" | "create" | "ignore";
    ingredient_id?: string;
    name?: string;
    display_name?: string;
    category?: string;
    role_override?: "primary" | "secondary";
  }
) {
  return apiFetch<TermDecisionResult>(`/imports/terms/${termId}/decision`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
```

- [ ] **Step 4: Scrivi i test della schermata**

`frontend/src/features/recipe-import/ImportQueueScreen.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ImportQueueScreen } from "./ImportQueueScreen";

const TERMINI = [
  {
    id: "t1",
    display_name: "Rigatoni",
    occurrences: 12,
    suggestion: { ingredient_id: "i1", name: "pasta", certain: false },
    waiting_titles: ["Pasta alla norma", "Pasta al forno"],
  },
  {
    id: "t2",
    display_name: "Acqua",
    occurrences: 7,
    suggestion: null,
    waiting_titles: ["Pane casereccio"],
  },
];

const PROPOSTE = {
  proposals: [
    { term_id: "t1", action: "map", ingredient_id: "i1", name: null,
      display_name: null, category: null },
    { term_id: "t2", action: "ignore", ingredient_id: null, name: null,
      display_name: null, category: null },
  ],
};

function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ImportQueueScreen />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

/** Un fetch che risponde in base al percorso e al metodo: la schermata fa tre
 * chiamate diverse, e il corpo di una Response si legge una volta sola. */
function stubFetch(route: (path: string, method: string) => [unknown, number]) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = route(String(url), init?.method ?? "GET");
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

const CODA_NORMALE = (path: string, method: string): [unknown, number] => {
  if (path.includes("/imports/terms/proposals")) return [PROPOSTE, 200];
  if (path.includes("/imports/terms") && method === "POST")
    return [{ unlocked: 12, remaining_terms: 1 }, 200];
  if (path.includes("/imports/terms")) return [TERMINI, 200];
  if (path.includes("/imports/status"))
    return [
      { fetched: 20, pending_recipes: 19, imported: 1, skipped: 0, pending_terms: 2 },
      200,
    ];
  return [{}, 404];
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("coda di revisione dell'import", () => {
  it("mostra il termine, quante ricette aspettano e qualche titolo", async () => {
    stubFetch(CODA_NORMALE);
    renderScreen();

    expect(await screen.findByText("Rigatoni")).toBeInTheDocument();
    expect(screen.getByText(/12 ricette in attesa/)).toBeInTheDocument();
    expect(screen.getByText(/Pasta alla norma/)).toBeInTheDocument();
  });

  it("la proposta di Claude diventa un pulsante che dice cosa farà", async () => {
    stubFetch(CODA_NORMALE);
    renderScreen();

    expect(
      await screen.findByRole("button", { name: /Collega a pasta/i })
    ).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /^Ignora «Acqua»$/ })).toBeInTheDocument();
  });

  it("confermare la proposta manda la decisione e dice quante ricette ha sbloccato", async () => {
    const spy = stubFetch(CODA_NORMALE);
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: /Collega a pasta/i }));

    await waitFor(() => expect(screen.getByText(/Sbloccate 12 ricette/)).toBeInTheDocument());
    const decisione = spy.mock.calls.find(
      ([url, init]) =>
        String(url).includes("/imports/terms/t1/decision") &&
        (init as RequestInit | undefined)?.method === "POST"
    );
    expect(JSON.parse(String((decisione?.[1] as RequestInit).body))).toEqual({
      action: "map",
      ingredient_id: "i1",
    });
  });

  it("ignorare un termine lo manda come tale", async () => {
    const spy = stubFetch(CODA_NORMALE);
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: /^Ignora «Acqua»$/ }));

    await waitFor(() => {
      const inviata = spy.mock.calls.find(
        ([url, init]) =>
          String(url).includes("/imports/terms/t2/decision") &&
          (init as RequestInit | undefined)?.method === "POST"
      );
      expect(JSON.parse(String((inviata?.[1] as RequestInit).body))).toEqual({
        action: "ignore",
      });
    });
  });

  it("senza le proposte la coda funziona e lo dichiara", async () => {
    stubFetch((path, method) => {
      if (path.includes("/imports/terms/proposals")) return [{ detail: "no" }, 503];
      return CODA_NORMALE(path, method);
    });
    renderScreen();

    expect(await screen.findByText("Rigatoni")).toBeInTheDocument();
    expect(screen.getByText(/decidi a mano/i)).toBeInTheDocument();
    // il suggerimento testuale resta, ed è l'altra via per decidere in un tocco
    expect(await screen.findByRole("button", { name: /Collega a pasta/i })).toBeInTheDocument();
  });

  it("a coda vuota dice che non c'è niente da fare", async () => {
    stubFetch((path) => {
      if (path.includes("/imports/terms/proposals")) return [{ proposals: [] }, 200];
      if (path.includes("/imports/terms")) return [[], 200];
      return [
        { fetched: 20, pending_recipes: 0, imported: 20, skipped: 0, pending_terms: 0 },
        200,
      ];
    });
    renderScreen();

    expect(await screen.findByText(/Niente da abbinare/i)).toBeInTheDocument();
  });

  it("se la coda non risponde lo dice insieme a cosa resta possibile", async () => {
    stubFetch((path) => {
      if (path.includes("/imports/terms")) return [{ detail: "rotto" }, 500];
      return [{}, 500];
    });
    renderScreen();

    expect(await screen.findByRole("alert")).toHaveTextContent(/ricettario/i);
  });
});
```

- [ ] **Step 5: Verifica che i test falliscano**

Run: `cd frontend && npx vitest run src/features/recipe-import`
Expected: FAIL, il modulo `./ImportQueueScreen` non esiste

- [ ] **Step 6: Scrivi la scheda del termine**

`frontend/src/features/recipe-import/TermCard.tsx`:

```tsx
import { useState } from "react";
import { IngredientPicker } from "../../components/IngredientPicker";
import { Card } from "../../components/ui/Card";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { INGREDIENT_CATEGORIES } from "../../domain/categories";
import type { ImportTerm, TermProposal } from "../../domain/types";

export type Decision = {
  action: "map" | "create" | "ignore";
  ingredient_id?: string;
  name?: string;
  display_name?: string;
  category?: string;
  role_override?: "primary" | "secondary";
};

/** Cosa farà il pulsante, detto in parole.
 *
 * «Collega a pasta» e «Crea Speck in carne» sono frasi che si leggono e si
 * confermano; «Applica proposta» costringerebbe a fidarsi di qualcosa che non si
 * vede, che è esattamente ciò che la revisione esiste per evitare.
 */
function proposalLabel(proposal: TermProposal, term: ImportTerm): string | null {
  if (proposal.action === "map") return `Collega a ${proposal.name ?? "l'ingrediente"}`;
  if (proposal.action === "create")
    return `Crea «${proposal.display_name ?? proposal.name}» in ${proposal.category}`;
  return `Ignora «${term.display_name}»`;
}

export function TermCard({
  term,
  proposal,
  suggestionName,
  pending,
  onDecide,
}: {
  term: ImportTerm;
  /** La proposta di Claude, quando è arrivata. */
  proposal: TermProposal | null;
  /** Il nome dell'aggancio testuale: è la proposta di riserva, e c'è anche senza AI. */
  suggestionName: string | null;
  pending: boolean;
  onDecide: (decision: Decision) => void;
}) {
  const [alsoSecondary, setAlsoSecondary] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState(term.display_name.toLowerCase());
  const [newCategory, setNewCategory] = useState<string>("altro");

  const role = alsoSecondary ? ("secondary" as const) : undefined;

  // la proposta di Claude, se c'è; altrimenti l'aggancio testuale, che è sempre
  // meglio di nessun pulsante: un termine senza scorciatoia costa tre tocchi
  const shortcut: TermProposal | null =
    proposal ??
    (suggestionName !== null && term.suggestion !== null
      ? {
          term_id: term.id, action: "map", ingredient_id: term.suggestion.ingredient_id,
          name: suggestionName, display_name: null, category: null,
        }
      : null);

  return (
    <Card as="li" className="flex flex-col gap-3">
      <div>
        <p className="font-medium">{term.display_name}</p>
        <p className="text-xs text-ink-faint">
          {term.occurrences === 1 ? "1 ricetta in attesa" : `${term.occurrences} ricette in attesa`}
        </p>
        {term.waiting_titles.length > 0 && (
          // i titoli non sono decorazione: «Scorza di limone» si giudica
          // diversamente in una torta e in un arrosto
          <p className="pt-1 text-xs text-ink-soft">{term.waiting_titles.join(" · ")}</p>
        )}
      </div>

      {shortcut && (
        <button
          type="button"
          disabled={pending}
          onClick={() =>
            onDecide(
              shortcut.action === "map"
                ? { action: "map", ingredient_id: shortcut.ingredient_id!, role_override: role }
                : shortcut.action === "create"
                  ? {
                      action: "create", name: shortcut.name!,
                      display_name: shortcut.display_name ?? shortcut.name!,
                      category: shortcut.category!, role_override: role,
                    }
                  : { action: "ignore" }
            )
          }
          className={buttonClasses("primary", "block")}
        >
          {proposalLabel(shortcut, term)}
        </button>
      )}

      <IngredientPicker
        label="Collega a un altro ingrediente"
        failureNote="Puoi crearne uno nuovo qui sotto, o ignorare il termine."
        disabled={pending}
        onPick={(ingredient) =>
          onDecide({ action: "map", ingredient_id: ingredient.id, role_override: role })
        }
      />

      {!creating ? (
        <button
          type="button"
          disabled={pending}
          onClick={() => setCreating(true)}
          className={buttonClasses("secondary", "block")}
        >
          Crea un ingrediente nuovo
        </button>
      ) : (
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium text-ink-soft">
            Nome dell'ingrediente
            <input
              aria-label="Nome dell'ingrediente"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="mt-1.5"
            />
          </label>
          <label className="text-sm font-medium text-ink-soft">
            Categoria
            <select
              aria-label="Categoria"
              value={newCategory}
              onChange={(e) => setNewCategory(e.target.value)}
              className="mt-1.5"
            >
              {INGREDIENT_CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            disabled={pending || newName.trim() === ""}
            onClick={() =>
              onDecide({
                action: "create", name: newName.trim().toLowerCase(),
                display_name: term.display_name, category: newCategory,
                role_override: role,
              })
            }
            className={buttonClasses("primary", "block")}
          >
            Crea e collega
          </button>
        </div>
      )}

      {/* la correzione dell'aglio: un tocco in più, solo per le eccezioni */}
      <label className="flex min-h-11 items-center gap-2.5 text-sm text-ink-soft">
        <input
          type="checkbox"
          aria-label="Di solito è un ingrediente secondario"
          checked={alsoSecondary}
          onChange={(e) => setAlsoSecondary(e.target.checked)}
          className="size-5"
        />
        Di solito è secondario
      </label>

      <button
        type="button"
        disabled={pending}
        onClick={() => onDecide({ action: "ignore" })}
        className={buttonClasses("ghost", "block")}
      >
        Ignora «{term.display_name}»
      </button>
    </Card>
  );
}
```

- [ ] **Step 7: Scrivi la schermata**

`frontend/src/features/recipe-import/ImportQueueScreen.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert } from "../../components/ui/Alert";
import { Screen } from "../../components/ui/Screen";
import { decideTerm, fetchImportStatus, fetchImportTerms, fetchTermProposals } from "./api";
import { TermCard, type Decision } from "./TermCard";
import { useState } from "react";

/** La revisione dei termini dell'import.
 *
 * Una decisione per volta, e ogni decisione materializza subito le ricette che
 * aspettavano quel termine: il numero che torna è ciò che rende questa schermata un
 * lavoro con un risultato visibile invece di un modulo da compilare.
 */
export function ImportQueueScreen() {
  const queryClient = useQueryClient();
  const [lastUnlocked, setLastUnlocked] = useState<number | null>(null);

  const { data: terms = [], isLoading, isError } = useQuery({
    queryKey: ["import-terms"],
    queryFn: fetchImportTerms,
  });

  const { data: status } = useQuery({
    queryKey: ["import-status"],
    queryFn: fetchImportStatus,
  });

  // Le proposte arrivano in una query loro: se Claude non risponde la coda resta
  // usabile, e il guasto non può svuotare una schermata che funziona anche senza.
  const termIds = terms.map((term) => term.id);
  const { data: proposals, isError: proposalsFailed } = useQuery({
    queryKey: ["import-proposals", termIds.join(",")],
    queryFn: () => fetchTermProposals(termIds),
    enabled: termIds.length > 0,
    staleTime: Infinity,
  });

  const decide = useMutation({
    mutationFn: ({ termId, decision }: { termId: string; decision: Decision }) =>
      decideTerm(termId, decision),
    onSuccess: (result) => {
      setLastUnlocked(result.unlocked);
      // la coda e lo stato cambiano entrambi, e il ricettario è appena cresciuto:
      // senza questa riga l'utente torna a Ricette e non vede quel che ha sbloccato
      queryClient.invalidateQueries({ queryKey: ["import-terms"] });
      queryClient.invalidateQueries({ queryKey: ["import-status"] });
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
    },
  });

  const byTerm = new Map((proposals?.proposals ?? []).map((p) => [p.term_id, p]));

  return (
    <Screen title="Ingredienti da abbinare">
      <p className="text-sm text-ink-soft">
        Ogni nome deciso vale per sempre, e le ricette che lo aspettavano entrano nel
        ricettario da sé.
      </p>

      {status && status.pending_recipes > 0 && (
        <p className="pt-1 text-xs text-ink-faint">
          {status.pending_recipes} ricette scaricate aspettano, {status.imported} sono già dentro.
        </p>
      )}

      {lastUnlocked !== null && (
        <p className="pt-2 text-sm font-medium text-brand">
          {lastUnlocked === 0
            ? "Decisione registrata: nessuna ricetta era in attesa solo di questa."
            : `Sbloccate ${lastUnlocked} ricette.`}
        </p>
      )}

      {/* una constatazione, non un guasto: la coda funziona anche senza proposte */}
      {proposalsFailed && (
        <p className="pt-2 text-xs text-ink-faint">
          Le proposte non sono disponibili: decidi a mano, il suggerimento qui sotto
          viene dalla somiglianza dei nomi.
        </p>
      )}

      {decide.isError && (
        <Alert className="pt-2">
          Non sono riuscito a registrare la decisione. Niente è andato perso: riprova.
        </Alert>
      )}

      {isLoading && <p className="pt-4 text-ink-soft">Carico la coda…</p>}

      {!isLoading && isError && (
        <Alert className="pt-4">
          Non sono riuscito a leggere la coda. Il ricettario funziona comunque: le
          ricette già importate sono al loro posto.
        </Alert>
      )}

      {!isLoading && !isError && terms.length === 0 && (
        <p className="pt-4 text-ink-soft">
          Niente da abbinare. Ogni ingrediente delle ricette scaricate ha la sua
          decisione.
        </p>
      )}

      {terms.length > 0 && (
        <ul className="flex flex-col gap-2 pt-2">
          {terms.map((term) => (
            <TermCard
              key={term.id}
              term={term}
              proposal={byTerm.get(term.id) ?? null}
              suggestionName={term.suggestion?.name ?? null}
              pending={decide.isPending}
              onDecide={(decision) => decide.mutate({ termId: term.id, decision })}
            />
          ))}
        </ul>
      )}
    </Screen>
  );
}
```

- [ ] **Step 8: Aggiungi la rotta**

In `frontend/src/App.tsx`, accanto a `/ricette/nuova-ai` e **sopra**
`/ricette/:id`, per lo stesso motivo scritto nel commento già presente lì:

```tsx
            <Route path="/ricette/importa" element={<ImportQueueScreen />} />
```

con l'import in cima al file.

- [ ] **Step 9: Aggiungi la riga d'ingresso al ricettario**

In `frontend/src/features/recipes/RecipeBookScreen.tsx`, una query e una riga che
compare **solo** quando c'è qualcosa da fare:

```tsx
  // Fuori dalla chiave ["recipes"]: questa non cambia cercando, cambia quando si
  // decide un termine o si scarica un lotto. Se la rotta non risponde non si mostra
  // niente: una riga rotta su una cosa che forse funziona è peggio del silenzio.
  const { data: importStatus } = useQuery({
    queryKey: ["import-status"],
    queryFn: fetchImportStatus,
  });
```

```tsx
      {importStatus && importStatus.pending_terms > 0 && (
        <Link
          to="/ricette/importa"
          className="flex min-h-11 items-center justify-between rounded-card bg-low-tint px-3.5 py-3 text-sm text-low"
        >
          <span>
            {importStatus.pending_terms} ingredienti da abbinare,{" "}
            {importStatus.pending_recipes} ricette in attesa
          </span>
          <span aria-hidden="true">›</span>
        </Link>
      )}
```

L'ambra è il colore che in quest'app vuol dire «funziona, ma non del tutto», lo
stesso di «quasi finito»: è la cosa giusta per un lavoro da finire.

L'import in cima al file è
`import { fetchImportStatus } from "../recipe-import/api";`.

- [ ] **Step 10: Esegui i test**

Run: `cd frontend && npx vitest run`
Expected: PASS. Poi `cd backend && pytest tests/test_frontend_categories.py -v`.

Se cade un test esistente di `RecipeBookScreen.test.tsx`, è perché la schermata fa
una chiamata in più: lo stub del fetch di quel file va esteso con `/imports/status`,
non va indebolita l'asserzione.

- [ ] **Step 11: Controlla tipi e stile**

Run: `cd frontend && npx tsc --noEmit && npx eslint src`
Expected: nessun errore

- [ ] **Step 12: Commit**

```bash
git add frontend/src/domain frontend/src/features/recipe-import frontend/src/App.tsx \
        frontend/src/features/recipes/RecipeBookScreen.tsx \
        backend/tests/test_frontend_categories.py
git commit -m "feat: la coda di revisione, con la proposta di Claude da confermare in un tocco"
```

---

## Task 15: foto, tempo, categoria e l'originale

**Files:**
- Modify: `frontend/src/features/recipes/RecipeCard.tsx`
- Modify: `frontend/src/features/recipes/RecipeBookScreen.tsx`
- Modify: `frontend/src/features/recipes/api.ts`
- Modify: `frontend/src/features/cooking/RecipeDetailScreen.tsx`
- Test: `frontend/src/features/recipes/RecipeBookScreen.test.tsx`
- Test: `frontend/src/features/cooking/RecipeDetailScreen.test.tsx`

**Interfaces:**
- Consumes: i quattro campi nuovi di `RecipeSummary` dal Task 14; la rotta
  `GET /recipes/categories` e il parametro `category` dal Task 13.

Trecento ricette senza foto sono un elenco; con la foto sono un ricettario. E
«cucinabile ora» più «venti minuti» è una risposta, mentre «cucinabile ora» da solo è
metà risposta.

- [ ] **Step 1: Scrivi i test**

In coda a `frontend/src/features/recipes/RecipeBookScreen.test.tsx`, dentro il
`describe` esistente (e aggiungi `image_url`, `prep_minutes`, `cook_minutes` e
`category` alle due voci di `RESULTS`: `r1` con foto, tempi 10 e 15 e categoria
«Primi piatti»; `r2` con tutti e quattro a `null`):

```tsx
  it("mostra la foto e il tempo totale quando ci sono", async () => {
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();

    const foto = await screen.findByRole("img", { name: "Pasta all'aglio" });
    expect(foto).toHaveAttribute("loading", "lazy");
    expect(screen.getByText("25 min")).toBeInTheDocument();
  });

  it("una ricetta senza foto e senza tempi non si rompe", async () => {
    stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();

    expect(await screen.findByText("Pasta al pomodoro")).toBeInTheDocument();
    expect(screen.queryByRole("img", { name: "Pasta al pomodoro" })).not.toBeInTheDocument();
  });

  it("il filtro per categoria chiede al backend solo quella categoria", async () => {
    const spy = stubRoutedFetch(CODA_CON_CATEGORIE);
    renderScreen();

    await userEvent.selectOptions(
      await screen.findByLabelText("Categoria"),
      "Dolci e Desserts"
    );

    await waitFor(() =>
      expect(
        spy.mock.calls.some(([url]) =>
          String(url).includes("category=Dolci+e+Desserts")
        )
      ).toBe(true)
    );
  });

  it("senza categorie nel ricettario il filtro non compare", async () => {
    stubRoutedFetch((path) => {
      if (path.includes("/recipes/categories")) return [[], 200];
      return CODA_CON_CATEGORIE(path);
    });
    renderScreen();

    await screen.findByText("Pasta all'aglio");
    expect(screen.queryByLabelText("Categoria")).not.toBeInTheDocument();
  });
```

`CODA_CON_CATEGORIE` è la funzione di instradamento di questo file, estesa con le due
rotte nuove:

```tsx
const CODA_CON_CATEGORIE = (path: string): [unknown, number] => {
  if (path.includes("/recipes/categories")) return [["Primi piatti", "Dolci e Desserts"], 200];
  if (path.includes("/imports/status"))
    return [{ fetched: 0, pending_recipes: 0, imported: 0, skipped: 0, pending_terms: 0 }, 200];
  if (path.includes("/recipes/search-mode")) return [{ semantic: true }, 200];
  return [RESULTS, 200];
};
```

In coda a `frontend/src/features/cooking/RecipeDetailScreen.test.tsx`:

```tsx
/** Lo stesso dettaglio del file, con una provenienza diversa.
 *
 * `mockImplementation` e non `mockResolvedValue`: la schermata fa più di una
 * chiamata, e il corpo di una Response si legge una volta sola. */
function stubFetchWithSourceRef(sourceRef: string) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        new Response(JSON.stringify({ ...DETAIL, source: "dataset", source_ref: sourceRef }), {
          status: 200,
        })
      )
    )
  );
}

  it("offre l'originale quando la ricetta viene da un indirizzo", async () => {
    stubFetchWithSourceRef("https://ricette.giallozafferano.it/Tiramisu.html");
    renderScreen();

    const link = await screen.findByRole("link", { name: /originale/i });
    expect(link).toHaveAttribute("href", "https://ricette.giallozafferano.it/Tiramisu.html");
    expect(link).toHaveAttribute("rel", expect.stringContaining("noreferrer"));
  });

  it("non offre niente quando la provenienza non è un indirizzo", async () => {
    stubFetchWithSourceRef("seme iniziale");
    renderScreen();

    expect(await screen.findByText("Pasta al pomodoro")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /originale/i })).not.toBeInTheDocument();
  });
```

La funzione va fuori dal `describe`, accanto a `renderScreen`.

- [ ] **Step 2: Verifica che i test falliscano**

Run: `cd frontend && npx vitest run src/features/recipes src/features/cooking`
Expected: FAIL: nessuna immagine, nessun filtro, nessun collegamento

- [ ] **Step 3: Aggiungi foto e tempo alla scheda**

In `frontend/src/features/recipes/RecipeCard.tsx`, prima del titolo e dopo
l'etichetta della provenienza:

```tsx
/** Preparazione più cottura, quando almeno uno dei due c'è.
 *
 * È l'informazione che decide davvero cosa si cucina stasera: «cucinabile ora» più
 * «venti minuti» è una risposta, «cucinabile ora» da solo è metà risposta.
 */
function totalMinutes(recipe: RecipeSummary): number | null {
  const total = (recipe.prep_minutes ?? 0) + (recipe.cook_minutes ?? 0);
  return total > 0 ? total : null;
}
```

```tsx
        {recipe.image_url && (
          // loading="lazy" non è un dettaglio: duecento schede su un telefono sono
          // duecento immagini, e l'immagine arriva dal server di origine
          <img
            src={recipe.image_url}
            alt={recipe.title}
            loading="lazy"
            className="mb-2.5 aspect-[3/2] w-full rounded-lg object-cover"
          />
        )}
```

e, nella riga delle etichette in basso, accanto alla pastiglia della cucinabilità:

```tsx
          {totalMinutes(recipe) !== null && (
            <span className="text-xs text-ink-faint">{totalMinutes(recipe)} min</span>
          )}
```

Metti i due elementi dentro un contenitore `flex items-center gap-2` così la
pastiglia e il tempo stanno sulla stessa riga.

- [ ] **Step 4: Aggiungi il filtro al ricettario**

In `frontend/src/features/recipes/api.ts`:

```ts
export function fetchCategories() {
  return apiFetch<string[]>("/recipes/categories");
}
```

e `searchRecipes` prende la categoria:

```ts
export function searchRecipes(query: string, onlyCookable: boolean, category: string) {
  const params = new URLSearchParams();
  if (query.trim()) params.set("q", query.trim());
  if (onlyCookable) params.set("only_cookable", "true");
  if (category) params.set("category", category);
  return apiFetch<RecipeSummary[]>(`/recipes/search?${params.toString()}`);
}
```

In `RecipeBookScreen.tsx`: uno stato `category` che entra nella chiave della query,
la query delle categorie, e il `select` che compare solo se ce n'è almeno una.

```tsx
  const [category, setCategory] = useState("");

  const { data: recipes = [], isLoading, isError } = useQuery({
    queryKey: ["recipes", debouncedQuery, onlyCookable, category],
    queryFn: () => searchRecipes(debouncedQuery, onlyCookable, category),
  });

  // le categorie presenti, non tutte quelle possibili: un filtro che offre voci
  // vuote porta a una schermata vuota
  const { data: categories = [] } = useQuery({
    queryKey: ["recipe-categories"],
    queryFn: fetchCategories,
  });
```

```tsx
      {categories.length > 0 && (
        <label className="text-sm font-medium text-ink-soft">
          Categoria
          <select
            aria-label="Categoria"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="mt-1.5"
          >
            <option value="">Tutte</option>
            {categories.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
      )}
```

`emptyMessage` riceve un quarto caso. «Nessuna ricetta» con un filtro attivo è un
verdetto sul filtro, non sul ricettario, quindi il messaggio deve nominare la
categoria e dire cosa togliere. Il ramo nuovo va **prima** dei tre esistenti:

```tsx
function emptyMessage(query: string, onlyCookable: boolean, category: string): string {
  const searched = query.trim() !== "";
  if (category) {
    const conParole = searched ? " con queste parole" : "";
    const cucinabili = onlyCookable ? " fra quelle che puoi cucinare adesso" : "";
    return (
      `Nessuna ricetta in «${category}»${conParole}${cucinabili}: ` +
      "scegli «Tutte» per vedere il resto del ricettario."
    );
  }
  // i tre rami già scritti, invariati
```

e il punto di chiamata diventa `emptyMessage(debouncedQuery, onlyCookable, category)`.

- [ ] **Step 5: Aggiungi l'originale al dettaglio**

In `frontend/src/features/cooking/RecipeDetailScreen.tsx`, sotto il titolo:

```tsx
      {/* L'attribuzione a un tocco. Solo se la provenienza è davvero un indirizzo:
          per le ricette del seme `source_ref` è una nota («seme iniziale»), e un
          collegamento a quella sarebbe un collegamento rotto.
          `rel="noreferrer"` perché il sito di origine non ha bisogno di sapere da
          dove arriva la visita. */}
      {recipe.source_ref?.startsWith("http") && (
        <a
          href={recipe.source_ref}
          target="_blank"
          rel="noreferrer"
          className="text-sm font-medium text-brand"
        >
          Apri l'originale
        </a>
      )}
```

- [ ] **Step 6: Esegui i test**

Run: `cd frontend && npx vitest run && npx tsc --noEmit && npx eslint src`
Expected: PASS, nessun errore di tipo né di stile

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/recipes frontend/src/features/cooking
git commit -m "feat: il ricettario mostra foto, tempo e categoria, e sa dov'è l'originale"
```

---

## Task 16: la documentazione

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Documenta i due comandi nel README**

Accanto alla sezione della semina, questa, con lo stesso taglio delle altre:

```markdown
### Portare ricette nel ricettario

```bash
docker compose exec backend python -m app.cli.import_gz --limit 200
```

Scarica un lotto di ricette da GialloZafferano: una pagina alla volta, con una pausa
di cortesia, e mai due volte lo stesso indirizzo. Rilanciarlo prende il lotto
successivo, quindi il ricettario si riempie a tappe e non in una notte.

Dopo lo scarico, gli ingredienti che l'anagrafica non riconosce finiscono in una coda.
Ci si arriva dalla riga in cima al ricettario, che compare solo quando c'è qualcosa da
decidere. Ogni decisione vale per sempre — diventa un alias dell'ingrediente, e la
conosce anche l'autocomplete della lista — e fa entrare da sé le ricette che la
aspettavano.

Se tieni accesa la ricerca semantica (`INSTALL_EMBEDDINGS=1`), dopo un import esegui:

```bash
docker compose exec backend python -m app.cli.reindex
```

Calcola i vettori delle ricette che non ne hanno. Senza, le ricette importate
restano cercabili solo per le parole che contengono, e rieseguire l'import non
rimedia: è idempotente e non torna su ciò che è già dentro.

Una nota che vale la pena sapere. Il `robots.txt` della fonte vieta esplicitamente i
crawler AI, e le sue condizioni d'uso con ogni probabilità vietano la raccolta
sistematica. Questo comando non è un crawler AI e si comporta di conseguenza, ma la
scelta di usarlo è di chi lo esegue: le ricette restano nel tuo database, non si
ridistribuiscono, e ognuna conserva l'indirizzo originale, che la schermata della
ricetta offre con «apri l'originale». La decisione e i suoi limiti stanno in §3 di
`docs/superpowers/specs/2026-09-12-import-ricette-design.md`.
```

- [ ] **Step 2: Aggiungi la riga a `CLAUDE.md`**

Fra le lezioni, una voce nuova:

```markdown
- **Un filtro che lavora sul risultato non può stare dietro a un limite.**
  `recipe_search.py` selezionava le 100 ricette più recenti e poi applicava
  `only_cookable`: con 26 ricette era tutto il ricettario, con 500 è un campione, e
  «cosa posso cucinare» avrebbe risposto guardando solo le ricette di ieri. Nessun
  test poteva vederlo, perché nessun test aveva più ricette della piscina. Quando un
  lavoro moltiplica i dati, cerca i limiti scritti quando i dati erano pochi.
```

E fra le convenzioni:

```markdown
- **L'import porta ricette, non ingredienti nuovi a caso.** Il catalogo della fonte è
  più fine dell'anagrafica: `Rigatoni` diventa un alias di `pasta`, deciso una volta
  in `import_terms` e scritto in `ingredient_aliases`. Non esiste una seconda tabella
  di mappatura, e una decisione sbagliata si corregge dall'anagrafica. Lo spec è
  `docs/superpowers/specs/2026-09-12-import-ricette-design.md`.
```

- [ ] **Step 3: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: i due comandi dell'import, e la lezione del filtro dietro al limite"
```

---

## Task 17: verifica in un browser vero

**Files:** nessuno. Questo task non scrive codice: dimostra che quello scritto
funziona dove vive.

La lezione è in CLAUDE.md e il branch precedente l'ha pagata: 157 test in jsdom
passavano mentre metà dei campi di testo era invisibile, perché Tailwind costruisce il
CSS e jsdom non lo calcola. Una schermata nuova si guarda.

- [ ] **Step 1: Avvia lo stack e2e**

```bash
docker compose -f docker-compose.e2e.yml -p spena-e2e up -d --build --wait
```

È il solo stack su cui è permesso `down -v`. Non toccare i volumi del progetto
predefinito.

- [ ] **Step 2: Semina e porta dentro qualche pagina senza rete**

La suite non tocca la rete, e nemmeno questa verifica deve dipendere dal fatto che
GialloZafferano risponda. Si inseriscono due pagine a mano, con gli stessi payload
delle fixture:

```bash
docker compose -f docker-compose.e2e.yml -p spena-e2e exec backend python - <<'PY'
import asyncio
from app.core.db import SessionLocal
from app.db.models.recipe_import import GIALLOZAFFERANO
from app.repositories.imports import store_page
from app.services.recipe_import.terms import sync_terms
from app.services.recipe_import.materialize import materialize_ready

PAGINE = [
    ("https://ricette.giallozafferano.it/Pasta-speck.html", {
        "title": "Pasta con crema di Parmigiano e speck",
        "description": "Cremoso e veloce", "instructions": "Cuoci.\n\nManteca.",
        "servings": 4, "category": "Primi piatti",
        "image_url": "https://www.giallozafferano.it/images/0-0/pasta.jpg",
        "prep_minutes": 10, "cook_minutes": 15,
        "ingredients": [
            {"key": "ricette-con-i-Rigatoni", "name": "Rigatoni", "quantity_text": "320 g"},
            {"key": "ricette-con-lo-Speck", "name": "Speck", "quantity_text": "80 g"},
        ],
        "nutrition": {"calories": "464,4 kcal"},
    }),
    ("https://ricette.giallozafferano.it/Torta-nonna.html", {
        "title": "Torta della nonna", "description": "Frolla, crema e pinoli",
        "instructions": "Impasta.\n\nInforna.", "servings": 10,
        "category": "Dolci e Desserts", "image_url": None,
        "prep_minutes": 40, "cook_minutes": 60,
        "ingredients": [
            {"key": "ricette-con-la-Farina-00", "name": "Farina 00", "quantity_text": "500 g"},
            {"key": "ricette-con-i-Pinoli", "name": "Pinoli", "quantity_text": "40 g"},
        ],
        "nutrition": None,
    }),
]

async def main():
    async with SessionLocal() as session:
        for url, payload in PAGINE:
            await store_page(session, source=GIALLOZAFFERANO, url=url, payload=payload)
        print(await sync_terms(session))
        print(await materialize_ready(session))
        await session.commit()

asyncio.run(main())
PY
```

- [ ] **Step 2b: Esegui la suite Playwright esistente**

```bash
cd frontend && npx playwright test
```

Expected: i 5 test esistenti passano. Se `cooking.spec.ts` si lamenta che lo stack non
è pulito, è la sua guardia che funziona: i dati appena inseriti lo hanno sporcato.
Ricrea lo stack con `down -v` e riesegui **prima** di inserire i dati, poi rifai
l'inserimento e salta questo passo.

- [ ] **Step 3: Guarda le tre schermate a 375 pixel**

Apri l'app sulla porta dello stack e2e, in un browser vero, con la finestra a 375
pixel di larghezza. Accedi con la password dello stack e2e. Controlla, uno per uno:

1. **Ricettario.** La riga ambra in cima dice quanti ingredienti restano da abbinare.
   Le due ricette hanno la loro categoria nel filtro. La prima mostra la foto, la
   seconda no e non lascia un buco. Il tempo totale si legge accanto alla pastiglia.
2. **Coda.** Il nome del termine, quante ricette aspettano, i titoli. Se la chiave di
   Claude è configurata, la proposta è un pulsante che dice cosa farà; se non lo è,
   la riga grigia dice di decidere a mano e il suggerimento testuale resta. Il campo
   dell'anagrafica e il campo del nome nuovo **hanno fondo bianco e bordo**: è il
   difetto che i test in jsdom non vedono.
3. **Dettaglio di una ricetta importata.** «Apri l'originale» c'è e porta
   all'indirizzo giusto. Su una ricetta del seme non c'è.

Decidi un termine dal browser e controlla che la riga «sbloccate N ricette» compaia e
che il ricettario sia cresciuto tornando indietro.

- [ ] **Step 4: Riporta cosa hai visto**

Nel rapporto finale: cosa hai controllato, cosa hai visto, e gli eventuali difetti
trovati. Una verifica «fatta» senza dire cosa è apparso sullo schermo non è una
verifica.

- [ ] **Step 5: Smonta lo stack**

```bash
docker compose -f docker-compose.e2e.yml -p spena-e2e down -v
```

---

## Lista di controllo finale

Prima di considerare il piano finito:

- [ ] `cd backend && pytest -q` — tutto verde, compresi i test della v1
- [ ] `cd backend && ruff check app tests` — nessun avviso
- [ ] `cd frontend && npx vitest run` — tutto verde
- [ ] `cd frontend && npx tsc --noEmit && npx eslint src` — nessun errore
- [ ] `cd frontend && npm run build` — la costruzione riesce
- [ ] `git diff --stat master` — nessun file del backend toccato senza motivo, e
      nessuna modifica a `.env`
- [ ] `grep -rn "emerald\|neutral-\|slate-\|#[0-9a-f]\{6\}" frontend/src --include=*.tsx`
      — nessun colore crudo nelle schermate nuove
