# Modificare ed eliminare una ricetta salvata (R10) — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Obiettivo:** una ricetta salvata smette di restare com'è per sempre: ogni ricetta, anche
importata, si modifica con lo stesso modulo di «Scrivi una ricetta» e si elimina con la
lapide e «Annulla»; e l'import non riscrive mai quel che si è toccato.

**Architettura:** una migrazione (`0011`) aggiunge `recipes.archived_at` e lo stato
`adopted` delle pagine d'import. La scrittura delle righe di ricetta resta in un punto
solo, `write_recipe_ingredients` in `app/repositories/recipes.py`, che `create_recipe`
e la nuova `PUT /recipes/{id}` chiamano entrambe; la `PATCH` guadagna `archived`. Il
primo salvataggio di una modifica, o l'eliminazione, passa la pagina a `adopted` nella
stessa transazione, e il resto dell'import (annullamento, materializzazione, fusione,
risincronizzazione) la lascia stare perché lavora solo su `imported` o `pending`. Ogni
elenco di ricette esclude le archiviate **prima** di qualunque limite. Nel frontend il
modulo di `AiDraftScreen` diventa `RecipeForm`, controllato dal genitore, usato da
«Scrivi una ricetta» e dalla nuova `/ricette/:id/modifica`; il dettaglio porta
«Modifica» ed «Elimina», e il ricettario la lapide.

**Stack:** FastAPI, SQLAlchemy async, Alembic, Postgres 16 (pgvector, pg_trgm); React 19
+ Vite + TypeScript, TanStack Query 5, React Router 7, Tailwind 4 con `@theme`; pytest su
Postgres vero, Vitest + jsdom + Testing Library, Playwright sullo stack `spena-e2e`.

**Spec:** `docs/superpowers/specs/2026-09-27-modifica-ricette-design.md` (la gemella,
`docs/superpowers/specs/2026-09-27-anagrafica-design.md`, è già costruita e in
produzione: il ri-legamento delle cotture e `merge_ingredients` esistono).

## Vincoli globali

- **Dove si lavora:** il worktree `/home/mactyws/coding/ais/spena/.claude/worktrees/r10-ricette`,
  ramo `r10-ricette`. Ogni comando parte da lì (o dalle sue `backend/` e `frontend/`),
  mai dalla radice del repository principale. `frontend/node_modules` e `.env` sono
  collegamenti simbolici al repository principale, ed è voluto.
- **Backend su Postgres vero**, dal database `spena_test_r10` che esiste già. Il
  comando, sempre da `<worktree>/backend`:
  ```bash
  PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_r10 python -m pytest -q
  ```
  Nel piano lo si abbrevia in `$PYTEST`; per comodità, in ogni shell:
  ```bash
  export PYTEST='env PATH=/home/mactyws/coding/ais/spena/backend/.venv/bin:'"$PATH"' TEST_DATABASE_URL=postgresql+asyncpg://spena:spena@localhost:5433/spena_test_r10 python -m pytest'
  ```
  e poi `$PYTEST -q tests/…`. Dove la shell non conserva le variabili fra un comando e
  l'altro (un agente), `$PYTEST` va scritto per intero. Il `PATH` serve ai test che
  lanciano `alembic`. Il venv è quello del repository principale, che vi ha installato
  `spena-backend` in modo modificabile: `python -m` mette la cartella corrente in testa a
  `sys.path` (e `alembic.ini` ha `prepend_sys_path = .`), quindi si prova l'`app` del
  worktree. Se un test sembra ignorare una modifica, `python -c 'import app; print(app.__file__)'`
  da `backend/` deve stampare un percorso dentro il worktree. Nessuna chiamata di rete
  nella suite. Il database parte con `docker compose up -d db` (dalla
  radice del worktree) se `docker ps` non mostra `spena-db-1`.
- **Frontend**, sempre da `<worktree>/frontend`: `npx vitest run` (il progetto **non
  ha** uno script `npm test`), `npm run lint`, `npm run typecheck`, `npm run build`.
- **Il type check è `npm run typecheck`** (`tsc -b`). Mai `tsc --noEmit`, che su questo
  progetto esce 0 sempre (settima lezione di `CLAUDE.md`). `RecipeSummary` e
  `RecipeDetail` guadagnano campi: i letterali dei test si rompono, e lo vede solo
  `tsc -b` (spec §9).
- **Testi per l'utente in italiano**, e in italiano anche commenti e docstring;
  identificatori in inglese.
- **Il colore vive solo nei token** del blocco `@theme` di `frontend/src/index.css`
  (`text-brand`, `text-danger`, `text-low`, `text-ink-soft`, `bg-card`, `bg-brand-tint`…).
  `grep -rnE "emerald|neutral-|#[0-9a-f]{6}" frontend/src --include=*.tsx` resta vuoto.
- **I primitivi stanno in `frontend/src/components/ui/`** (`Screen`, `Card`, `Alert`,
  `SectionHeading`, `buttonClasses`, `CostPicker`) e in `frontend/src/components/`
  (`IngredientPicker`, `BackLink`): si guardano prima di scrivere un bottone.
- **Bersagli di almeno 44 px** (`min-h-11`, `size-11`, o `buttonClasses`, che li porta).
- **Mai un vicolo cieco:** ogni rifiuto dice il passo dopo; una lapide il cui annulla
  fallisce resta, con l'errore dentro.
- **I test nuovi dei componenti usano il predicato di retry vero**
  (`defaultQueryRetryPredicate` da `frontend/src/lib/queryRetry.ts`), non
  `retry: false` (prima lezione di `CLAUDE.md`). Dove un ramo d'errore passa dai due
  tentativi, `findBy…` prende `{ timeout: 8000 }` e il test `10000`, come in
  `IngredientScreen.test.tsx`.
- **Un filtro sul risultato non sta dietro un limite** (sesta lezione di `CLAUDE.md`):
  l'esclusione delle archiviate va nella query che ha il `.limit()`, non dopo.
- **I test esistenti di «Scrivi una ricetta»** (`AiDraftScreen.test.tsx`) restano verdi
  **senza modifiche**, salvo i quattro selettori che cambiano per la ✕ al posto della
  spunta, elencati uno per uno nel Task 9 (spec §9).
- **Un JSONB si riassegna, non si muta** (`page.payload = {...}`).
- **Nessuna funzione di repository o di servizio fa commit.** Le rotte decidono.
- **TDD:** nessun codice di produzione senza un test che è già fallito.
- **Commit in italiano**, uno per task, che finiscono con
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Nessun accesso alla produzione, nessun deploy.** Il piano finisce con il ramo verde;
  la distribuzione la decide Mattia dopo.
- **Niente dati di produzione in git:** il repository è pubblico.

---

## Deviazioni dalla spec

Decise scrivendo il piano, dove la spec è ambigua o il codice la contraddice. Ognuna è
richiamata nel task che la costruisce.

1. **Il filtro «costo» di `_browse` non esiste.** La spec §5 elenca fra i filtri dello
   sfoglio «cucinabili, per ingrediente, mancanti al più *n*, costo»; ma R9 ha deciso
   «nessun filtro né ordinamento per costo», e `_browse` in `recipe_search.py` filtra
   per soglia di mancanti, categoria e ingredienti. Il Task 6 prova i filtri che ci
   sono: cucinabili, per ingrediente, mancanti al più 1, **categoria**, e lo sfoglio
   senza filtri con la sua pagina.
2. **`match_name` non sta in `create_recipe`.** La spec §5 dice che le righe della PUT
   passano «dalla stessa strada di `create_recipe`: stessa risoluzione dei nomi con
   `match_name`, stesso imbuto, stessa lettura delle quantità». Nel codice la
   risoluzione dei nomi vive nella rotta `POST /recipes`, e imbuto e quantità in
   `create_recipe`. Il piano estrae quindi **due** pezzi condivisi: `_resolve_lines`
   nella rotta (nomi, e creazione dell'ingrediente mancante) e
   `write_recipe_ingredients` nel repository (imbuto `NonFoodInRecipe`,
   `parse_quantity`, scrittura). Quest'ultimo resta *l'unico punto che scrive le righe*.
3. **La categoria entra anche nella `POST`.** `RecipeCreate` oggi non ha `category`, e
   la spec §6.2 vuole che il modulo la scelga. `RecipeCreate` e la PUT la accettano; la
   rotta rifiuta con 422 un nome che non è già fra le categorie del ricettario. La spec
   dice «senza testo libero» per il modulo: il controllo nel backend è l'ultima linea,
   come l'imbuto per il non alimentare.
4. **Il dettaglio dice se l'import rifà ancora la ricetta.** La riga «È una ricetta
   importata: salvando diventa tua…» (spec §6.2) è vera solo se la pagina è ancora
   `imported`: su una ricetta già presa in carico «diventa tua» sarebbe falso. La spec
   non dice come lo schermo lo sappia: `RecipeOut` guadagna `owned_by_import: bool`.
5. **«Se il termine aveva creato un ingrediente» non si può sapere.** Spec §4: la coda
   deve dire che l'ingrediente resta perché una ricetta tua lo usa. Ma `import_terms`
   non registra se la decisione ha creato l'ingrediente o ne ha usato uno esistente
   (`_decided_action` in `api/imports.py` spiega perché nessuna deduzione regge).
   L'annullamento restituisce quindi `ingredient_kept_for_adopted` — l'ingrediente non è
   stato cancellato **e** una ricetta presa in carico lo usa — e la coda lo dice con una
   frase vera in entrambi i casi: «L'ingrediente resta in anagrafica: lo usa una ricetta
   tua.»
6. **L'anagrafica continua a contare le ricette archiviate.** `recipes_using` (la guardia
   sul non alimentare) e `ingredient_usage` (la scheda dell'ingrediente) non escludono
   le archiviate: le loro righe esistono ancora, e una ricetta ripristinata non deve
   tornare con una riga che punta a un non alimentare. «Tutto quel che elenca ricette»
   (spec §5) si legge come l'elenco del §5 stesso: il ricettario, le categorie,
   `reindex`.
7. **`reread_costs` salta le pagine prese in carico.** La spec §4 elenca annullamento,
   materializzazione, fusione e risincronizzazione; `app.cli.reread_costs` è un quinto
   percorso dell'import che scrive sulle ricette (il costo dove manca). Una ricetta resa
   tua con il costo tolto a mano se lo vedrebbe riscrivere. Una condizione in più, con
   il suo test (Task 7).
8. **Il costo di una ricetta archiviata non si cambia.** La spec dice che una ricetta
   archiviata non si modifica con la PUT (409). La PATCH del costo fa lo stesso: 409 con
   la stessa frase. Una PATCH del costo **non** prende in carico la pagina: il costo era
   già al sicuro nel `payload` (R9) e la spec §4 nomina solo modifica ed eliminazione.
9. **La migrazione si prova su un database suo, e scendendo perde l'adozione.** Il test
   dell'`upgrade` e del `downgrade` crea e distrugge un database apposta: far scendere
   quello della suite toglierebbe `archived_at` sotto i piedi agli altri test. Il
   `downgrade` riporta `adopted` a `imported` prima di rimettere il vecchio `CHECK`
   (altrimenti fallirebbe): è una perdita dichiarata nel commento della migrazione.
10. **La spunta resta solo sugli agganci incerti.** Spec §6.2: «una riga si toglie con
    una ✕, e non togliendo la spunta». Ogni riga ha la sua ✕; la casella «Includi …»
    resta **solo** sulla riga dell'AI con un aggancio incerto, dove non vuol dire
    «togli» ma «confermo che è questo» — ed è quel che due test esistenti provano, con
    le stesse etichette.
11. **Le categorie del modulo si leggono quando si apre la scelta, non al montaggio.**
    Leggerle al montaggio consumerebbe la prima delle risposte in sequenza
    (`mockResolvedValueOnce`) con cui i test esistenti di «Scrivi una ricetta» fingono
    la bozza, e li romperebbe: la spec §9 lo vieta. Aprire la scelta la carica; la chiave
    è la stessa `["recipe-categories"]` del ricettario, quindi quasi sempre è già in cache.
12. **Il nome si scrive una volta** (spec §6.2) mostrando la nota dell'aggancio solo
    quando dice qualcosa di diverso dall'etichetta: aggancio incerto, niente in
    anagrafica, o un nome agganciato diverso da quello scritto («basilico fresco» →
    «basilico»).

---

## Struttura dei file

**Backend**
- `backend/alembic/versions/0011_modifica_ricette.py` — *crea*: `archived_at` e `adopted`.
- `backend/app/db/models/recipe.py` — *modifica*: `Recipe.archived_at`.
- `backend/app/db/models/recipe_import.py` — *modifica*: `ImportState.ADOPTED`, il `CHECK`.
- `backend/app/repositories/recipes.py` — *modifica*: `IngredientLine`,
  `write_recipe_ingredients`, `recipe_categories`; `create_recipe` prende `category`.
- `backend/app/repositories/imports.py` — *modifica*: `adopt_import_page`, `owned_by_import`.
- `backend/app/schemas/recipe.py` — *modifica*: `RecipeFields`, `RecipeCreate`,
  `RecipeReplace`, `RecipeUpdate.archived`, `archived_at` e `owned_by_import` in uscita.
- `backend/app/api/recipes.py` — *modifica*: `_resolve_lines`, `_check_category`,
  `_embedding_for`, `_writing_recipe`, la PUT, la PATCH con `archived`.
- `backend/app/services/recipe_search.py` — *modifica*: le tre query escludono le archiviate.
- `backend/app/cli/reindex.py` — *modifica*: salta le archiviate.
- `backend/app/services/recipe_import/undo.py` — *modifica*: conta le pagine `adopted`;
  la docstring (Task 15).
- `backend/app/schemas/recipe_import.py`, `backend/app/api/imports.py` — *modifica*:
  `UndoOut` porta i due fatti nuovi.
- `backend/app/cli/reread_costs.py` — *modifica*: salta le pagine `adopted`.

**Prove backend**
- `backend/tests/db/test_migration_0011.py` — *crea* (Task 1).
- `backend/tests/db/test_import_schema.py` — *modifica* (Task 1).
- `backend/tests/repositories/__init__.py`, `backend/tests/repositories/test_recipe_lines.py`
  — *crea* (Task 2).
- `backend/tests/api/test_recipes_category.py` — *crea* (Task 3).
- `backend/tests/api/test_recipes_edit.py` — *crea* (Task 4).
- `backend/tests/api/test_recipes_archive.py` — *crea* (Task 5).
- `backend/tests/api/test_recipes_archived_lists.py` — *crea* (Task 6).
- `backend/tests/api/test_recipes_adoption.py` — *crea* (Task 7).
- `backend/tests/test_reread_costs_cli.py` — *modifica* (Task 7).

**Frontend**
- `frontend/src/domain/types.ts` — *modifica*: `archived_at`, `owned_by_import`,
  `RecipeBody`, `RecipeIngredientBody`, i due campi di `UndoResult`.
- `frontend/src/features/recipes/api.ts` — *modifica*: `createRecipe` tipizzata,
  `updateRecipe`, `setRecipeArchived`.
- `frontend/src/features/recipe-form/formModel.ts` (+ `formModel.test.ts`) — *crea*: le
  righe, i valori, la validazione, il corpo da mandare. Funzioni pure.
- `frontend/src/features/recipe-form/RecipeForm.tsx` (+ `RecipeForm.test.tsx`) — *crea*.
- `frontend/src/features/recipe-form/CategoryField.tsx` — *crea*: la scelta della
  categoria, provata attraverso `RecipeForm`.
- `frontend/src/features/recipe-form/RecipeEditScreen.tsx` (+ test) — *crea*.
- `frontend/src/features/ai-draft/AiDraftScreen.tsx` — *modifica*: usa `RecipeForm`.
- `frontend/src/features/ai-draft/AiDraftScreen.test.tsx` — *modifica*: solo i quattro
  selettori del Task 9.
- `frontend/src/lib/undo.ts` — *crea*: `UNDO_MS`, condiviso da dispensa e ricettario.
- `frontend/src/features/pantry/PantryScreen.tsx` — *modifica*: importa `UNDO_MS`.
- `frontend/src/features/recipes/RecipeBookScreen.tsx` (+ `RecipeBookScreen.lapide.test.tsx`)
  — *modifica*: la lapide.
- `frontend/src/features/cooking/RecipeDetailScreen.tsx` (+ `RecipeDetailActions.test.tsx`)
  — *modifica*: «Modifica», «Elimina», «Salvata», la ricetta archiviata.
- `frontend/src/App.tsx` — *modifica*: la rotta `/ricette/:id/modifica`.
- `frontend/src/features/recipe-import/ImportQueueScreen.tsx` (+ test) — *modifica*.
- I letterali `RecipeDetail`/`RecipeSummary` dei test esistenti
  (`CookSheet.test.tsx`, `RecipeDetailScreen.test.tsx`, `RecipeCard.test.tsx`) —
  *modifica*: un campo in più, niente altro.
- `frontend/e2e/modifica-ricette.spec.ts` — *crea* (Task 14).

**Documenti** (Task 15): `docs/prossimi-passi.md`, `CLAUDE.md`, la docstring di
`backend/app/services/recipe_import/undo.py`.

---

# Consegna 1 — backend

Le rotte nuove esistono senza schermate, e l'import smette di rifare le ricette prese in
carico. Si chiude con la suite intera verde (fine del Task 7); non si distribuisce da
sola — la distribuzione la decide Mattia.

### Task 1: La migrazione `0011` e i modelli

**File:**
- Create: `backend/alembic/versions/0011_modifica_ricette.py`
- Modify: `backend/app/db/models/recipe.py` (classe `Recipe`, dopo `cost`)
- Modify: `backend/app/db/models/recipe_import.py` (`ImportState`, `RecipeImport.__table_args__`)
- Test: `backend/tests/db/test_migration_0011.py`, `backend/tests/db/test_import_schema.py`

**Interfacce:**
- Consuma: niente.
- Produce:
  - `Recipe.archived_at: Mapped[datetime | None]` (`TIMESTAMPTZ`, annullabile)
  - `ImportState.ADOPTED = "adopted"`
  - revisione Alembic `"0011"`, `down_revision = "0010"` (l'ultima esistente è davvero
    la `0010_costo_ricette.py`: il numero della spec è giusto)

- [ ] **Step 0: il punto di partenza**

```bash
cd /home/mactyws/coding/ais/spena/.claude/worktrees/r10-ricette
git status && git log --oneline -1   # r10-ricette, pulito, f390231 o successivo
docker ps --format '{{.Names}}' | grep -q spena-db-1 || docker compose up -d db
cd backend && $PYTEST -q
```
Expected: tutto verde. Annota il numero di test: è la linea di partenza.

- [ ] **Step 1: scrivi i test che falliscono**

Crea `backend/tests/db/test_migration_0011.py`:

```python
"""La migrazione 0011 sale e scende (R10 §8.1).

Su un database suo, creato e distrutto qui: far scendere quello della suite
toglierebbe `archived_at` sotto i piedi a ogni altro test, e un fallimento a metà lo
lascerebbe lì. Alembic gira in un sottoprocesso, come nella fixture `engine` di
conftest: il suo template async chiama `asyncio.run`, che dentro un loop già in corsa
esplode.
"""

import os
import subprocess

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://spena:spena@localhost:5433/spena_test"
)
SERVER, _, TEST_DB = TEST_DATABASE_URL.rpartition("/")
SCRATCH_DB = f"{TEST_DB}_migrazione"

ARCHIVED_AT = (
    "SELECT data_type FROM information_schema.columns "
    "WHERE table_name = 'recipes' AND column_name = 'archived_at'"
)


def alembic(url: str, *args: str) -> None:
    subprocess.run(["alembic", *args], check=True, env={**os.environ, "DATABASE_URL": url})


@pytest_asyncio.fixture
async def scratch_url():
    admin = create_async_engine(f"{SERVER}/postgres", isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)'))
        await conn.execute(text(f'CREATE DATABASE "{SCRATCH_DB}"'))
    try:
        yield f"{SERVER}/{SCRATCH_DB}"
    finally:
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)'))
        await admin.dispose()


async def _scalar(url: str, sql: str):
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            return (await conn.execute(text(sql))).scalar()
    finally:
        await engine.dispose()


async def _pagina(url: str, indirizzo: str, stato: str) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO recipe_imports (id, source, url, payload, state) "
                    "VALUES (gen_random_uuid(), 'giallozafferano', :url, '{}'::jsonb, :state)"
                ),
                {"url": indirizzo, "state": stato},
            )
    finally:
        await engine.dispose()


async def test_la_0011_sale_scende_e_risale(scratch_url):
    alembic(scratch_url, "upgrade", "0011")
    assert await _scalar(scratch_url, ARCHIVED_AT) == "timestamp with time zone"
    await _pagina(scratch_url, "https://esempio.invalid/presa", "adopted")
    with pytest.raises(IntegrityError):
        await _pagina(scratch_url, "https://esempio.invalid/inventata", "quasi")

    alembic(scratch_url, "downgrade", "0010")
    assert await _scalar(scratch_url, ARCHIVED_AT) is None
    # scendendo, la presa in carico si perde: la pagina torna «imported», e il vecchio
    # CHECK non rifiuta niente di quel che c'è
    assert (
        await _scalar(
            scratch_url,
            "SELECT state FROM recipe_imports WHERE url = 'https://esempio.invalid/presa'",
        )
        == "imported"
    )
    with pytest.raises(IntegrityError):
        await _pagina(scratch_url, "https://esempio.invalid/dopo", "adopted")

    alembic(scratch_url, "upgrade", "head")
    assert await _scalar(scratch_url, ARCHIVED_AT) == "timestamp with time zone"
```

In `backend/tests/db/test_import_schema.py`, in fondo:

```python
async def test_una_pagina_presa_in_carico_e_uno_stato_valido(db_session):
    """R10: la pagina di una ricetta modificata o eliminata a mano è `adopted`."""
    from app.db.models.recipe_import import ImportState

    pagina = una_pagina("https://ricette.giallozafferano.it/Carbonara.html")
    pagina.state = ImportState.ADOPTED
    db_session.add(pagina)
    await db_session.flush()


async def test_una_ricetta_ha_la_data_di_eliminazione_vuota_finche_c_e(db_session):
    from app.db.models.recipe import Recipe, RecipeSource

    ricetta = Recipe(title="Carbonara", instructions="x", source=RecipeSource.MANUAL)
    db_session.add(ricetta)
    await db_session.flush()
    assert ricetta.archived_at is None
```

- [ ] **Step 2: eseguili e verifica che falliscano**

Run: `cd backend && $PYTEST -q tests/db/test_migration_0011.py tests/db/test_import_schema.py`
Expected: FAIL — `alembic upgrade 0011` esce con «Can't locate revision identified by
'0011'»; `AttributeError: ADOPTED` e `AttributeError: 'Recipe' object has no attribute
'archived_at'` negli altri due.

- [ ] **Step 3: implementazione minima**

Crea `backend/alembic/versions/0011_modifica_ricette.py`:

```python
"""modificare ed eliminare una ricetta salvata (R10)

Revision ID: 0011
"""
import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"


def upgrade() -> None:
    # Presente vuol dire eliminata, come `pantry_items.archived_at`. Nessun indice: ogni
    # elenco di ricette filtra `IS NULL` su qualche migliaio di righe.
    op.add_column("recipes", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint("ck_recipe_import_state", "recipe_imports", type_="check")
    op.create_check_constraint(
        "ck_recipe_import_state",
        "recipe_imports",
        "state IN ('pending', 'imported', 'skipped', 'adopted')",
    )


def downgrade() -> None:
    # Scendere perde quel che R10 ha scritto, e va detto: una pagina presa in carico
    # torna `imported` (il vecchio CHECK non conosce altro), quindi l'import potrà di
    # nuovo rifare quella ricetta; e le ricette eliminate ricompaiono, perché la colonna
    # che le nascondeva se ne va.
    op.execute("UPDATE recipe_imports SET state = 'imported' WHERE state = 'adopted'")
    op.drop_constraint("ck_recipe_import_state", "recipe_imports", type_="check")
    op.create_check_constraint(
        "ck_recipe_import_state", "recipe_imports", "state IN ('pending', 'imported', 'skipped')"
    )
    op.drop_column("recipes", "archived_at")
```

In `backend/app/db/models/recipe.py`, nella classe `Recipe`, subito dopo la riga di `cost`:

```python
    # Presente vuol dire eliminata (R10), come `pantry_items.archived_at`: la riga resta,
    # con le sue righe e le sue cotture, e si ripristina togliendo la data. Ogni elenco
    # di ricette la esclude; il dettaglio no, perché un collegamento vecchio non deve
    # finire in un 404.
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

In `backend/app/db/models/recipe_import.py`:

```python
class ImportState(StrEnum):
    PENDING = "pending"
    IMPORTED = "imported"
    SKIPPED = "skipped"
    # Presa in carico (R10): la ricetta è stata modificata o eliminata a mano. L'import
    # non la rifà più — l'annullamento e la materializzazione lavorano su `imported` e
    # `pending` — e non si torna indietro, nemmeno ripristinandola.
    ADOPTED = "adopted"
```

e nel `CheckConstraint` di `RecipeImport`:

```python
        CheckConstraint(
            "state IN ('pending', 'imported', 'skipped', 'adopted')",
            name="ck_recipe_import_state",
        ),
```

- [ ] **Step 4: eseguili e verifica che passino, poi la suite**

Run: `cd backend && $PYTEST -q tests/db`
Expected: PASS, compreso `test_metadata_matches_migrations.py` (modello e migrazione
dicono la stessa colonna).

Run: `cd backend && $PYTEST -q`
Expected: tutto verde, linea di partenza + 3.

- [ ] **Step 5: commit**

```bash
git add backend/alembic/versions/0011_modifica_ricette.py backend/app/db/models/recipe.py backend/app/db/models/recipe_import.py backend/tests/db/test_migration_0011.py backend/tests/db/test_import_schema.py
git commit -m "$(cat <<'EOF'
ricette: la migrazione 0011, con la data di eliminazione e la pagina presa in carico

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Il punto unico delle righe, e l'elenco delle categorie

**File:**
- Modify: `backend/app/repositories/recipes.py` (tutto il modulo)
- Modify: `backend/app/api/recipes.py` (la rotta `categories`, righe 192–205)
- Create: `backend/tests/repositories/__init__.py` (vuoto)
- Test: `backend/tests/repositories/test_recipe_lines.py`

**Interfacce:**
- Consuma: `Recipe.archived_at` (Task 1) — non ancora filtrato qui: il filtro arriva
  nel Task 6, con i suoi test.
- Produce:
  - `IngredientLine = tuple[uuid.UUID, str, str | None, str | None]` — (ingredient_id,
    role, quantity_text, note)
  - `async write_recipe_ingredients(session, recipe: Recipe, ingredients: list[IngredientLine]) -> None`
    — solleva `NonFoodInRecipe` prima di ogni scrittura; sulla ricetta persistente
    la collezione `recipe.ingredients` deve essere già caricata (`get_recipe` lo fa).
  - `create_recipe(..., cost: int | None = None, category: str | None = None) -> Recipe`
  - `async recipe_categories(session) -> list[str]`

- [ ] **Step 1: scrivi il test che fallisce**

Crea `backend/tests/repositories/__init__.py` vuoto e
`backend/tests/repositories/test_recipe_lines.py`:

```python
"""L'unico punto che scrive `recipe_ingredients` (R10 §5).

La creazione e la modifica passano entrambe di qui: l'imbuto sul non alimentare e la
lettura delle quantità non hanno una seconda copia che una delle due strade potrebbe
dimenticare.
"""

from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import RecipeIngredient, RecipeSource
from app.repositories.recipes import (
    NonFoodInRecipe,
    create_recipe,
    get_recipe,
    recipe_categories,
    write_recipe_ingredients,
)


@pytest_asyncio.fixture
async def voci(db_session):
    voci = {
        "pasta": Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI),
        "aglio": Ingredient(name="aglio", display_name="Aglio", category=IngredientCategory.VERDURA),
        "sapone": Ingredient(name="sapone", display_name="Sapone", category=IngredientCategory.IGIENE),
    }
    db_session.add_all(voci.values())
    await db_session.flush()
    return voci


async def _aglio_e_olio(db_session, voci):
    return await create_recipe(
        db_session, title="Aglio e olio", description=None, instructions="Cuoci.",
        servings=2, source=RecipeSource.MANUAL, source_ref=None,
        ingredients=[
            (voci["pasta"].id, "primary", "320 g", None),
            (voci["aglio"].id, "secondary", "1 spicchio", None),
        ],
        embedding=None,
    )


async def _righe(db_session, recipe_id):
    rows = await db_session.execute(
        select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe_id)
    )
    return {row.ingredient_id: row for row in rows.scalars()}


async def test_riscrivere_toglie_le_righe_sparite_e_riscrive_le_altre(db_session, voci):
    ricetta = await _aglio_e_olio(db_session, voci)
    caricata = await get_recipe(db_session, ricetta.id)

    # la pasta resta ma cambia tutto, l'aglio se ne va: lo stesso ingrediente riscritto
    # è il caso che un flush unico romperebbe, inserendo prima di cancellare
    await write_recipe_ingredients(
        db_session, caricata, [(voci["pasta"].id, "secondary", "200 g", "al dente")]
    )
    await db_session.flush()

    righe = await _righe(db_session, ricetta.id)
    assert set(righe) == {voci["pasta"].id}
    pasta = righe[voci["pasta"].id]
    assert (pasta.role, pasta.quantity_text, pasta.note) == ("secondary", "200 g", "al dente")
    # la dose è passata dal parser, come alla creazione
    assert pasta.quantity_value == Decimal("200")


async def test_il_non_alimentare_e_rifiutato_prima_di_toccare_qualcosa(db_session, voci):
    ricetta = await _aglio_e_olio(db_session, voci)
    caricata = await get_recipe(db_session, ricetta.id)

    with pytest.raises(NonFoodInRecipe) as rifiuto:
        await write_recipe_ingredients(
            db_session, caricata,
            [(voci["pasta"].id, "primary", None, None), (voci["sapone"].id, "primary", None, None)],
        )

    assert rifiuto.value.display_name == "Sapone"
    assert set(await _righe(db_session, ricetta.id)) == {voci["pasta"].id, voci["aglio"].id}


async def test_la_categoria_si_scrive_creando(db_session, voci):
    ricetta = await create_recipe(
        db_session, title="Pasta in bianco", description=None, instructions="Cuoci.",
        servings=None, source=RecipeSource.MANUAL, source_ref=None,
        ingredients=[(voci["pasta"].id, "primary", None, None)], embedding=None,
        category="Primi piatti",
    )
    assert ricetta.category == "Primi piatti"


async def test_le_categorie_sono_quelle_presenti_una_volta_e_in_ordine(db_session, voci):
    for titolo, categoria in (("A", "Primi piatti"), ("B", "Dolci"), ("C", "Primi piatti"), ("D", None)):
        await create_recipe(
            db_session, title=titolo, description=None, instructions="x", servings=None,
            source=RecipeSource.MANUAL, source_ref=None, ingredients=[], embedding=None,
            category=categoria,
        )
    assert await recipe_categories(db_session) == ["Dolci", "Primi piatti"]
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `cd backend && $PYTEST -q tests/repositories/test_recipe_lines.py`
Expected: FAIL in raccolta — `ImportError: cannot import name 'recipe_categories'`.

- [ ] **Step 3: implementazione minima**

Riscrivi `backend/app/repositories/recipes.py` così (`NonFoodInRecipe` e `get_recipe`
sono quelle di prima, parola per parola):

```python
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.ingredient import Ingredient
from app.db.models.recipe import Recipe, RecipeIngredient
from app.domain.quantities import parse_quantity
from app.domain.rules import IngredientKind
from app.repositories.units import ensure_unit

# Una riga di ricetta come la scrivono i chiamanti: (ingredient_id, role,
# quantity_text, note). Una tupla e non un modello perché è la forma che la
# materializzazione, il seme e i test passano da sempre a `create_recipe`.
IngredientLine = tuple[uuid.UUID, str, str | None, str | None]


class NonFoodInRecipe(Exception):
    """Una riga di ricetta punta a una voce non alimentare.

    Porta il nome visibile della voce perché il messaggio all'utente deve dire
    **quale**: su una ricetta di dodici righe, «una voce non alimentare» non è
    un'indicazione, è un indovinello.
    """

    def __init__(self, display_name: str) -> None:
        super().__init__(display_name)
        self.display_name = display_name


async def _refuse_non_food(session: AsyncSession, ingredients: list[IngredientLine]) -> None:
    # Una query sola per tutta la ricetta, e sul `kind` invece che sulla lista dei
    # reparti: la partizione vive in un posto solo (`kind_for_category`), e qui si
    # legge il suo risultato.
    #
    # Solleva, e non salta la riga: se le guardie a monte tengono — la decisione
    # della coda, l'AI dell'import, i selettori `kind=food` del modulo — questa non è
    # raggiungibile. È l'ultima linea, e ci si arriva solo perché qualcosa più in alto
    # ha un buco; una riga saltata in silenzio produrrebbe una ricetta mutilata che
    # nessuno ha chiesto.
    if not ingredients:
        return
    non_food = (
        await session.execute(
            select(Ingredient.display_name)
            .where(
                Ingredient.id.in_({line[0] for line in ingredients}),
                Ingredient.kind == IngredientKind.NON_FOOD,
            )
            .limit(1)
        )
    ).scalars().first()
    if non_food is not None:
        raise NonFoodInRecipe(non_food)


async def write_recipe_ingredients(
    session: AsyncSession, recipe: Recipe, ingredients: list[IngredientLine]
) -> None:
    """L'unico punto che scrive `recipe_ingredients`, alla creazione e alla modifica.

    Sostituisce le righe: quelle che non ci sono più si cancellano, le altre si
    riscrivono (R10 §5). Il controllo sul non alimentare viene prima di ogni
    scrittura, così un rifiuto lascia la ricetta esattamente com'era.

    Su una ricetta già salvata la collezione `recipe.ingredients` dev'essere caricata
    (`get_recipe` la carica): leggerla pigra in una sessione async è un MissingGreenlet.
    """
    await _refuse_non_food(session, ingredients)
    if recipe.ingredients:
        # le vecchie righe se ne vanno con un flush loro, prima che arrivino le nuove:
        # in un flush unico SQLAlchemy inserisce prima di cancellare, e lo stesso
        # ingrediente riscritto violerebbe l'unicità (recipe_id, ingredient_id)
        recipe.ingredients.clear()
        await session.flush()
    for ingredient_id, role, quantity_text, note in ingredients:
        # Il parser gira qui e non nei chiamanti: questo è l'unico punto che scrive
        # recipe_ingredients, e chiedere a ogni chiamante di ricordarsene
        # significherebbe che il prossimo — quello non ancora scritto — se ne
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


async def create_recipe(
    session: AsyncSession,
    *,
    title: str,
    description: str | None,
    instructions: str,
    servings: int | None,
    source: str,
    source_ref: str | None,
    ingredients: list[IngredientLine],
    embedding: list[float] | None,
    cost: int | None = None,
    category: str | None = None,
) -> Recipe:
    recipe = Recipe(
        title=title, description=description, instructions=instructions, servings=servings,
        source=source, source_ref=source_ref, embedding=embedding, cost=cost,
        category=category,
    )
    await write_recipe_ingredients(session, recipe, ingredients)
    session.add(recipe)
    await session.flush()
    return recipe


async def get_recipe(session: AsyncSession, recipe_id: uuid.UUID) -> Recipe | None:
    statement = (
        select(Recipe)
        .options(selectinload(Recipe.ingredients).joinedload(RecipeIngredient.ingredient))
        .where(Recipe.id == recipe_id)
    )
    return (await session.execute(statement)).unique().scalar_one_or_none()


async def recipe_categories(session: AsyncSession) -> list[str]:
    """Le categorie presenti nel ricettario, una volta ciascuna e in ordine.

    Un posto solo per due domande: il filtro del ricettario (`GET /recipes/categories`)
    e il controllo sulla categoria scelta nel modulo (R10). Solo quelle che esistono
    davvero: un filtro che offre voci vuote porta a una schermata vuota.
    """
    rows = await session.execute(
        select(Recipe.category)
        .where(Recipe.category.is_not(None))
        .distinct()
        .order_by(Recipe.category)
    )
    return list(rows.scalars())
```

In `backend/app/api/recipes.py`, la rotta `categories` diventa:

```python
@router.get("/categories", response_model=list[str])
async def categories(session: AsyncSession = Depends(get_session)) -> list[str]:
    """Le categorie presenti nel ricettario, per il filtro (vedi `recipe_categories`)."""
    return await recipe_categories(session)
```

con `recipe_categories` aggiunto all'import da `app.repositories.recipes`, e via la riga
`from sqlalchemy import select`: la rotta delle categorie era l'unica a usarla. `Recipe`
resta importato (lo usa `_to_out`).

- [ ] **Step 4: eseguilo e verifica che passi, poi la suite**

Run: `cd backend && $PYTEST -q tests/repositories tests/api/test_recipes.py tests/services/test_materialize.py`
Expected: PASS.

Run: `cd backend && $PYTEST -q`
Expected: tutto verde — la materializzazione, il seme e i test che chiamano
`create_recipe` passano senza modifiche.

- [ ] **Step 5: commit**

```bash
git add backend/app/repositories/recipes.py backend/app/api/recipes.py backend/tests/repositories
git commit -m "$(cat <<'EOF'
ricette: le righe si scrivono in un punto solo, per creare e per modificare

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: La categoria nella creazione, e i nomi risolti in un punto solo

Deviazioni 2 e 3.

**File:**
- Modify: `backend/app/schemas/recipe.py` (`RecipeCreate`, righe 37–45)
- Modify: `backend/app/api/recipes.py` (la rotta `create`, righe 234–299)
- Test: `backend/tests/api/test_recipes_category.py`

**Interfacce:**
- Consuma: `create_recipe(..., category=)`, `recipe_categories`, `IngredientLine` (Task 2).
- Produce:
  - `class RecipeFields(BaseModel)` con `title`, `description`, `category: str | None`
    (max 60), `instructions`, `servings`, `ingredients`, `cost`
  - `class RecipeCreate(RecipeFields)` con `source`, `source_ref`
  - in `app/api/recipes.py`:
    `async _resolve_lines(session, lines: list[RecipeIngredientIn]) -> list[IngredientLine]`,
    `async _check_category(session, category: str | None, *, current: str | None = None) -> None`
    (422 se sconosciuta), `async _embedding_for(title: str, description: str | None) -> list[float] | None`,
    `_writing_recipe(session)` — un `asynccontextmanager` che traduce `NonFoodInRecipe`
    in 422 e `IntegrityError` in 404/409, dopo il rollback.

- [ ] **Step 1: scrivi il test che fallisce**

Crea `backend/tests/api/test_recipes_category.py`:

```python
"""Una ricetta scritta qui esce filtrando per categoria (R10 §6.2, giro di T3).

La categoria si sceglie fra quelle già nel ricettario, o nessuna: senza testo libero,
per non creare «Primi» e «primi». Il modulo non offre altro; la rotta è l'ultima linea.
"""

import pytest_asyncio
from sqlalchemy import func, select

from app.db.models.recipe import Recipe, RecipeSource
from app.repositories.recipes import create_recipe


@pytest_asyncio.fixture
async def primi(db_session):
    """Una categoria che il ricettario ha già, portata da una ricetta importata."""
    await create_recipe(
        db_session, title="Pasta e fagioli", description=None, instructions="Cuoci.",
        servings=2, source=RecipeSource.DATASET, source_ref=None, ingredients=[],
        embedding=None, category="Primi piatti",
    )
    await db_session.flush()


def _corpo(**extra):
    return {"title": "Pasta e ceci", "instructions": "Cuoci.", "source": "manual", **extra}


async def test_una_categoria_esistente_si_scrive_e_si_ritrova_filtrando(logged_client, primi):
    creata = await logged_client.post("/api/v1/recipes", json=_corpo(category="Primi piatti"))

    assert creata.status_code == 201, creata.text
    assert creata.json()["category"] == "Primi piatti"
    trovate = (
        await logged_client.get("/api/v1/recipes/search?category=Primi%20piatti")
    ).json()
    assert "Pasta e ceci" in [r["title"] for r in trovate]


async def test_una_categoria_che_il_ricettario_non_ha_e_un_422(logged_client, db_session, primi):
    risposta = await logged_client.post("/api/v1/recipes", json=_corpo(category="primi"))

    assert risposta.status_code == 422
    assert "scegline una dall'elenco" in risposta.json()["detail"]
    quante = await db_session.scalar(
        select(func.count()).select_from(Recipe).where(Recipe.title == "Pasta e ceci")
    )
    assert quante == 0


async def test_senza_categoria_resta_senza(logged_client):
    creata = await logged_client.post("/api/v1/recipes", json=_corpo())
    assert creata.status_code == 201
    assert creata.json()["category"] is None
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `cd backend && $PYTEST -q tests/api/test_recipes_category.py`
Expected: FAIL — il primo con `category` `None` invece di `"Primi piatti"` (il campo non
esiste e Pydantic lo ignora), il secondo con 201 invece di 422.

- [ ] **Step 3: implementazione minima**

In `backend/app/schemas/recipe.py`, `RecipeCreate` diventa due classi:

```python
class RecipeFields(BaseModel):
    """Quel che si scrive di una ricetta, alla creazione e alla modifica (R10 §5)."""

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    # Una delle categorie già nel ricettario, o nessuna. Il modulo la sceglie da
    # `GET /recipes/categories` e la rotta rifiuta un nome che non c'è: con il testo
    # libero «Primi» e «primi» diventerebbero due voci del filtro.
    category: str | None = Field(default=None, max_length=60)
    instructions: str = Field(min_length=1)
    servings: int | None = Field(default=None, ge=1, le=50)
    ingredients: list[RecipeIngredientIn] = Field(default_factory=list)
    cost: int | None = Field(default=None, ge=COST_MIN, le=COST_MAX)


class RecipeCreate(RecipeFields):
    source: RecipeSource
    source_ref: str | None = Field(default=None, max_length=500)
```

In `backend/app/api/recipes.py`, agli import:

```python
from contextlib import asynccontextmanager
```

e da `app.repositories.recipes` importa anche `IngredientLine`. Sopra la rotta `create`
aggiungi i quattro aiuti:

```python
async def _resolve_lines(
    session: AsyncSession, lines: list[RecipeIngredientIn]
) -> list[IngredientLine]:
    """Da righe del modulo a righe da scrivere: la stessa strada per creare e modificare.

    Le righe che nominano un ingrediente non ancora in anagrafica lo creano qui,
    dentro la stessa transazione della ricetta: se il salvataggio fallisce non resta
    nessun ingrediente orfano. In sequenza e non in parallelo, per lo stesso motivo del
    fan-in dell'import: due righe con lo stesso nome nuovo devono diventare un
    ingrediente, non un doppione.
    """
    resolved: list[IngredientLine] = []
    for line in lines:
        ingredient_id = line.ingredient_id
        if ingredient_id is None:
            # `match_name` e non una ricerca sul solo nome canonico: se la bozza dice
            # «pomodori» e l'anagrafica ha «pomodoro» con quell'alias, collegarsi è
            # giusto e creare sarebbe un duplicato travestito
            match = await match_name(session, line.name or "")
            if match.certain and match.ingredient_id is not None:
                ingredient_id = match.ingredient_id
            else:
                created = await create_ingredient(
                    session, name=line.name or "",
                    display_name=(line.name or "").capitalize(),
                    category=line.category or "altro",
                )
                ingredient_id = created.id
        resolved.append((ingredient_id, line.role, line.quantity_text, line.note))
    return resolved


async def _check_category(
    session: AsyncSession, category: str | None, *, current: str | None = None
) -> None:
    """Una categoria che il ricettario ha già, o nessuna (R10, deviazione 3).

    `current` è quella che la ricetta ha già: tenerla non si rifiuta mai.
    """
    if category is None or category == current:
        return
    if category not in await recipe_categories(session):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"«{category}» non è una categoria del ricettario: scegline una dall'elenco, "
            "o nessuna.",
        )


async def _embedding_for(title: str, description: str | None) -> list[float] | None:
    """L'embedding è un ornamento: se il modello non c'è, la ricetta si salva comunque,
    con il vettore a `NULL`, e `app.cli.reindex` lo ritrova (riempie solo i `NULL`)."""
    try:
        return (await get_embedding_provider().embed_passages([recipe_document(title, description)]))[0]
    except EmbeddingUnavailable as exc:
        log_degradation_once(exc)
        return None


@asynccontextmanager
async def _writing_recipe(session: AsyncSession):
    """Gli errori di una scrittura di ricetta, uguali per la creazione e la modifica."""
    try:
        yield
    except NonFoodInRecipe as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"«{exc.display_name}» non è un alimento: una ricetta non può averlo fra "
            "gli ingredienti. Toglilo dalla riga, poi salva.",
        ) from exc
    except IntegrityError as exc:
        await session.rollback()
        if is_missing_reference(exc):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "ingrediente inesistente") from exc
        # solo un duplicato è un "ripetuto": qualunque altra violazione è un difetto
        # nostro e deve restare visibile come 500, come in shopping.py e pantry.py
        if not is_unique_violation(exc):
            raise
        raise HTTPException(
            status.HTTP_409_CONFLICT, "ingrediente ripetuto nella ricetta"
        ) from exc
```

e la rotta `create` diventa:

```python
@router.post("", response_model=RecipeOut, status_code=status.HTTP_201_CREATED)
async def create(
    payload: RecipeCreate, session: AsyncSession = Depends(get_session)
) -> RecipeOut:
    await _check_category(session, payload.category)
    embedding = await _embedding_for(payload.title, payload.description)
    async with _writing_recipe(session):
        recipe = await create_recipe(
            session, title=payload.title, description=payload.description,
            instructions=payload.instructions, servings=payload.servings,
            source=payload.source, source_ref=payload.source_ref,
            ingredients=await _resolve_lines(session, payload.ingredients),
            embedding=embedding,
            cost=payload.cost,
            category=payload.category,
        )
        await session.commit()
    stored = await get_recipe(session, recipe.id)
    return await _to_out(session, stored)
```

(`RecipeIngredientIn` va aggiunto all'import da `app.schemas.recipe`.)

- [ ] **Step 4: eseguilo e verifica che passi, poi le rotte delle ricette**

Run: `cd backend && $PYTEST -q tests/api/test_recipes_category.py tests/api/test_recipes.py tests/api/test_recipes_create_ingredient.py tests/api/test_recipes_cost.py tests/api/test_recipes_quantities.py`
Expected: PASS — i test della creazione non cambiano.

- [ ] **Step 5: commit**

```bash
git add backend/app/schemas/recipe.py backend/app/api/recipes.py backend/tests/api/test_recipes_category.py
git commit -m "$(cat <<'EOF'
ricette: la categoria si sceglie creando, fra quelle del ricettario

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---
### Task 4: `PUT /recipes/{id}`

Spec §5 e §8.2.

**File:**
- Modify: `backend/app/schemas/recipe.py` (dopo `RecipeCreate`)
- Modify: `backend/app/repositories/imports.py` (in fondo)
- Modify: `backend/app/api/recipes.py` (una rotta nuova, dopo `update`)
- Test: `backend/tests/api/test_recipes_edit.py`

**Interfacce:**
- Consuma: `RecipeFields`, `_resolve_lines`, `_check_category`, `_embedding_for`,
  `_writing_recipe` (Task 3); `write_recipe_ingredients`, `get_recipe` (Task 2);
  `ImportState.ADOPTED`, `Recipe.archived_at` (Task 1).
- Produce:
  - `class RecipeReplace(RecipeFields)` — nessun campo in più; `source` e `source_ref`
    mandati comunque si ignorano (Pydantic scarta i campi non dichiarati).
  - `async adopt_import_page(session, recipe_id: uuid.UUID) -> bool` in
    `app/repositories/imports.py`
  - `RECIPE_ARCHIVED = "Questa ricetta è stata eliminata: ripristinala prima di modificarla."`
    in `app/api/recipes.py` (il frontend riconosce il 409 da «eliminata», Task 9)
  - `PUT /api/v1/recipes/{recipe_id}` → `RecipeOut`; 404 ricetta o ingrediente
    inesistente, 409 riga doppia o ricetta archiviata, 422 non alimentare o categoria
    sconosciuta.

- [ ] **Step 1: scrivi il test che fallisce**

Crea `backend/tests/api/test_recipes_edit.py`:

```python
"""`PUT /recipes/{id}`: la ricetta intera, righe comprese (R10 §5, §8.2).

Le righe passano dalla stessa strada della creazione: `_resolve_lines` per i nomi,
`write_recipe_ingredients` per l'imbuto e le quantità. Una ricetta importata che si
modifica diventa tua: la sua pagina passa ad `adopted` nella stessa transazione.
"""

import uuid
from datetime import UTC, datetime

import pytest_asyncio
from sqlalchemy import select

from app.cli.reindex import reindex
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.recipe import Recipe, RecipeIngredient, RecipeSource
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportState, RecipeImport
from app.domain.rules import PantryStatus
from app.repositories.recipes import create_recipe

SPAGHETTI = "https://ricette.giallozafferano.it/Spaghetti-al-pomodoro.html"


@pytest_asyncio.fixture
async def cucina(db_session):
    def voce(name: str, category: str) -> Ingredient:
        return Ingredient(name=name, display_name=name.capitalize(), category=category)

    voci = {
        "pasta": voce("pasta", IngredientCategory.CEREALI),
        "pomodoro": voce("pomodoro", IngredientCategory.VERDURA),
        "aglio": voce("aglio", IngredientCategory.VERDURA),
        "sapone": voce("sapone per le mani", IngredientCategory.IGIENE),
    }
    db_session.add_all(voci.values())
    await db_session.flush()
    return voci


@pytest_asyncio.fixture
async def importata(db_session, cucina):
    """Una ricetta dell'import, con la sua pagina ancora `imported`."""
    ricetta = await create_recipe(
        db_session, title="Spaghetti al pomodoro", description=None, instructions="Cuoci.",
        servings=4, source=RecipeSource.DATASET, source_ref=SPAGHETTI,
        ingredients=[
            (cucina["pasta"].id, "primary", "320 g", None),
            (cucina["pomodoro"].id, "primary", "400 g", None),
        ],
        embedding=None, category="Primi piatti",
    )
    pagina = RecipeImport(
        source=GIALLOZAFFERANO, url=SPAGHETTI,
        payload={"title": "Spaghetti al pomodoro", "ingredients": []},
        state=ImportState.IMPORTED, recipe_id=ricetta.id,
    )
    db_session.add(pagina)
    await db_session.flush()
    return ricetta, pagina


def _riga(voce, role="primary", quantity=None):
    return {"ingredient_id": str(voce.id), "role": role, "quantity_text": quantity}


def _corpo(cucina, **extra):
    corpo = {
        "title": "Pasta al pomodoro", "description": "Di sempre", "category": None,
        "instructions": "Cuoci.", "servings": 2, "cost": None,
        "ingredients": [
            _riga(cucina["pasta"], quantity="320 g"),
            _riga(cucina["pomodoro"], quantity="400 g"),
            _riga(cucina["aglio"], "secondary"),
        ],
    }
    corpo.update(extra)
    return corpo


async def _scritta(client, cucina) -> dict:
    risposta = await client.post("/api/v1/recipes", json={**_corpo(cucina), "source": "manual"})
    assert risposta.status_code == 201, risposta.text
    return risposta.json()


async def _modifica(client, recipe_id, corpo):
    return await client.put(f"/api/v1/recipes/{recipe_id}", json=corpo)


async def _nomi(client, recipe_id) -> set[str]:
    dettaglio = (await client.get(f"/api/v1/recipes/{recipe_id}")).json()
    return {riga["ingredient_name"] for riga in dettaglio["ingredients"]}


async def _vettore(dal_database, recipe_id) -> list[float] | None:
    ricetta = await dal_database(Recipe, uuid.UUID(str(recipe_id)))
    return None if ricetta.embedding is None else [float(x) for x in ricetta.embedding]


async def test_una_ricetta_scritta_a_mano_si_modifica_tutta(logged_client, cucina):
    ricetta = await _scritta(logged_client, cucina)

    risposta = await _modifica(logged_client, ricetta["id"], _corpo(
        cucina, title="Pasta aglio e pomodoro", description="Più veloce",
        instructions="Soffriggi, poi cuoci.", servings=4, cost=2,
        ingredients=[
            _riga(cucina["pasta"], "primary", "200 g"),
            _riga(cucina["aglio"], "primary", "2 spicchi"),
            _riga(cucina["pomodoro"], "secondary"),
        ],
    ))

    assert risposta.status_code == 200, risposta.text
    corpo = risposta.json()
    assert (corpo["title"], corpo["description"], corpo["instructions"]) == (
        "Pasta aglio e pomodoro", "Più veloce", "Soffriggi, poi cuoci.",
    )
    assert (corpo["servings"], corpo["cost"]) == (4, 2)
    assert {r["ingredient_name"]: (r["role"], r["quantity_text"]) for r in corpo["ingredients"]} == {
        "pasta": ("primary", "200 g"),
        "aglio": ("primary", "2 spicchi"),
        "pomodoro": ("secondary", None),
    }
    # la provenienza non si tocca
    assert (corpo["source"], corpo["source_ref"]) == ("manual", None)
    dettaglio = (await logged_client.get(f"/api/v1/recipes/{ricetta['id']}")).json()
    assert dettaglio["title"] == "Pasta aglio e pomodoro"


async def test_una_riga_tolta_se_ne_va_e_la_ricetta_diventa_cucinabile(
    logged_client, db_session, cucina
):
    ricetta = await _scritta(logged_client, cucina)
    db_session.add_all([
        PantryItem(ingredient_id=cucina["pasta"].id, status=PantryStatus.AVAILABLE),
        PantryItem(ingredient_id=cucina["aglio"].id, status=PantryStatus.AVAILABLE),
    ])
    await db_session.flush()
    prima = (await logged_client.get(f"/api/v1/recipes/{ricetta['id']}")).json()
    assert prima["cookable"] is False  # manca il pomodoro

    risposta = await _modifica(logged_client, ricetta["id"], _corpo(
        cucina, ingredients=[_riga(cucina["pasta"], quantity="320 g"), _riga(cucina["aglio"], "secondary")],
    ))

    assert risposta.json()["cookable"] is True
    righe = (
        await db_session.execute(
            select(RecipeIngredient.ingredient_id).where(
                RecipeIngredient.recipe_id == uuid.UUID(ricetta["id"])
            )
        )
    ).scalars().all()
    assert set(righe) == {cucina["pasta"].id, cucina["aglio"].id}


async def test_una_ricetta_importata_modificata_diventa_tua(
    logged_client, dal_database, cucina, importata
):
    ricetta, pagina = importata

    risposta = await _modifica(
        logged_client, ricetta.id, _corpo(cucina, title="I miei spaghetti", category="Primi piatti")
    )

    assert risposta.status_code == 200, risposta.text
    # «tua» non è la provenienza: resta `dataset`, con il suo indirizzo
    assert (risposta.json()["source"], risposta.json()["source_ref"]) == ("dataset", SPAGHETTI)
    assert (await dal_database(RecipeImport, pagina.id)).state == ImportState.ADOPTED


async def test_il_non_alimentare_e_rifiutato_e_la_ricetta_resta_com_era(logged_client, cucina):
    ricetta = await _scritta(logged_client, cucina)

    risposta = await _modifica(logged_client, ricetta["id"], _corpo(
        cucina, title="Altro titolo",
        ingredients=[_riga(cucina["pasta"]), _riga(cucina["sapone"])],
    ))

    assert risposta.status_code == 422
    assert "Sapone per le mani" in risposta.json()["detail"]
    dettaglio = (await logged_client.get(f"/api/v1/recipes/{ricetta['id']}")).json()
    assert dettaglio["title"] == "Pasta al pomodoro"
    assert await _nomi(logged_client, ricetta["id"]) == {"pasta", "pomodoro", "aglio"}


async def test_senza_modello_un_titolo_nuovo_lascia_l_embedding_a_null(
    logged_client, db_session, dal_database, cucina, monkeypatch
):
    from app.services.embeddings import EmbeddingUnavailable

    ricetta = await _scritta(logged_client, cucina)
    assert await _vettore(dal_database, ricetta["id"]) is not None

    class ProviderRotto:
        async def embed_passages(self, texts):
            raise EmbeddingUnavailable("modello non installato")

        async def embed_query(self, text):
            raise EmbeddingUnavailable("modello non installato")

    monkeypatch.setattr("app.api.recipes.get_embedding_provider", lambda: ProviderRotto())

    risposta = await _modifica(logged_client, ricetta["id"], _corpo(cucina, title="Titolo nuovo"))

    assert risposta.status_code == 200, risposta.text
    # un vettore del titolo vecchio sarebbe una bugia sulla ricetta nuova: meglio nessuno
    assert await _vettore(dal_database, ricetta["id"]) is None
    # e il comando che riempie i vettori mancanti la ritrova
    assert await reindex(db_session) == 1


async def test_un_titolo_nuovo_ricalcola_l_embedding_e_il_resto_no(
    logged_client, dal_database, cucina
):
    ricetta = await _scritta(logged_client, cucina)
    prima = await _vettore(dal_database, ricetta["id"])

    await _modifica(logged_client, ricetta["id"], _corpo(cucina, instructions="Solo questo cambia."))
    assert await _vettore(dal_database, ricetta["id"]) == prima

    await _modifica(logged_client, ricetta["id"], _corpo(cucina, title="Titolo nuovo"))
    assert await _vettore(dal_database, ricetta["id"]) != prima


async def test_una_ricetta_eliminata_non_si_modifica(logged_client, db_session, cucina):
    ricetta = await _scritta(logged_client, cucina)
    salvata = await db_session.get(Recipe, uuid.UUID(ricetta["id"]))
    salvata.archived_at = datetime.now(UTC)
    await db_session.flush()

    risposta = await _modifica(logged_client, ricetta["id"], _corpo(cucina, title="Non passa"))

    assert risposta.status_code == 409
    assert "ripristinala" in risposta.json()["detail"]


async def test_un_ingrediente_sparito_e_un_404_e_una_riga_doppia_un_409(logged_client, cucina):
    ricetta = await _scritta(logged_client, cucina)

    fantasma = {"ingredient_id": str(uuid.uuid4()), "role": "primary"}
    assert (await _modifica(logged_client, ricetta["id"], _corpo(cucina, ingredients=[fantasma]))).status_code == 404
    doppia = [_riga(cucina["pasta"]), _riga(cucina["pasta"], "secondary")]
    assert (await _modifica(logged_client, ricetta["id"], _corpo(cucina, ingredients=doppia))).status_code == 409

    # nessuno dei due ha lasciato la ricetta a metà
    assert await _nomi(logged_client, ricetta["id"]) == {"pasta", "pomodoro", "aglio"}


async def test_una_ricetta_che_non_c_e_e_un_404(logged_client, cucina):
    assert (await _modifica(logged_client, uuid.uuid4(), _corpo(cucina))).status_code == 404


async def test_la_provenienza_mandata_si_ignora(logged_client, cucina):
    ricetta = await _scritta(logged_client, cucina)

    risposta = await _modifica(
        logged_client, ricetta["id"], {**_corpo(cucina), "source": "ai", "source_ref": "prompt: altro"}
    )

    assert (risposta.json()["source"], risposta.json()["source_ref"]) == ("manual", None)


async def test_una_riga_per_nome_si_aggancia_come_alla_creazione(logged_client, db_session, cucina):
    """`match_name`, come nella POST: «pomodori» è un alias di «pomodoro», e crearne
    un secondo sarebbe un duplicato travestito."""
    from app.repositories.ingredients import add_alias

    await add_alias(db_session, cucina["pomodoro"].id, "pomodori", source="seed")
    ricetta = await _scritta(logged_client, cucina)

    risposta = await _modifica(logged_client, ricetta["id"], _corpo(cucina, ingredients=[
        _riga(cucina["pasta"]),
        {"name": "pomodori", "category": "verdura", "role": "primary"},
    ]))

    assert risposta.status_code == 200, risposta.text
    assert {r["ingredient_id"] for r in risposta.json()["ingredients"]} == {
        str(cucina["pasta"].id), str(cucina["pomodoro"].id),
    }


async def test_la_categoria_che_ha_gia_si_tiene_e_una_inventata_no(logged_client, cucina, importata):
    ricetta, _ = importata
    assert (await _modifica(logged_client, ricetta.id, _corpo(cucina, category="Primi piatti"))).status_code == 200
    assert (await _modifica(logged_client, ricetta.id, _corpo(cucina, category="Secondi inventati"))).status_code == 422
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `cd backend && $PYTEST -q tests/api/test_recipes_edit.py`
Expected: FAIL — ogni `PUT` risponde 405 (Method Not Allowed).

- [ ] **Step 3: implementazione minima**

In `backend/app/schemas/recipe.py`, dopo `RecipeCreate`:

```python
class RecipeReplace(RecipeFields):
    """La ricetta intera, per `PUT /recipes/{id}` (R10 §5).

    Tutto quel che ha `RecipeCreate` tranne la provenienza, che non si cambia: una
    ricetta importata e poi modificata resta `dataset`, con il suo `source_ref`. Un
    `source` mandato comunque si ignora, come ogni campo che il modello non dichiara.
    """
```

In `backend/app/repositories/imports.py`, in fondo:

```python
async def adopt_import_page(session: AsyncSession, recipe_id: uuid.UUID) -> bool:
    """La pagina da cui la ricetta è nata passa ad `adopted`, se è ancora `imported`.

    Si chiama nella stessa transazione del primo salvataggio di una modifica e
    dell'eliminazione (R10 §4). Non torna mai indietro: una pagina già `adopted` resta
    tale, e ripristinare la ricetta non la rende di nuovo dell'import. Vero se l'ha
    cambiata adesso.
    """
    page = (
        await session.execute(select(RecipeImport).where(RecipeImport.recipe_id == recipe_id))
    ).scalars().first()
    if page is None or page.state != ImportState.IMPORTED:
        return False
    page.state = ImportState.ADOPTED
    await session.flush()
    return True
```

In `backend/app/api/recipes.py`: agli import aggiungi `RecipeReplace` (da
`app.schemas.recipe`), `write_recipe_ingredients` (da `app.repositories.recipes`) e
`from app.repositories.imports import adopt_import_page`; sotto il `router`:

```python
RECIPE_ARCHIVED = "Questa ricetta è stata eliminata: ripristinala prima di modificarla."
```

e, dopo la rotta `update`:

```python
@router.put("/{recipe_id}", response_model=RecipeOut)
async def replace(
    recipe_id: uuid.UUID, payload: RecipeReplace, session: AsyncSession = Depends(get_session)
) -> RecipeOut:
    """La ricetta intera, righe comprese (R10 §5).

    Le righe passano dalla stessa strada della creazione: stessi nomi risolti
    (`_resolve_lines`), stesso imbuto e stesse quantità (`write_recipe_ingredients`),
    stessi errori (`_writing_recipe`). Se la ricetta viene dall'import e la sua pagina è
    ancora `imported`, passa ad `adopted` in questa transazione: da qui l'import non la
    rifà più.
    """
    recipe = await get_recipe(session, recipe_id)
    if recipe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ricetta inesistente")
    if recipe.archived_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, RECIPE_ARCHIVED)
    await _check_category(session, payload.category, current=recipe.category)
    # il vettore nasce da titolo e descrizione: solo se cambiano va rifatto, e senza
    # modello va a NULL — un vettore del testo vecchio mentirebbe sulla ricetta nuova
    new_text = (payload.title, payload.description) != (recipe.title, recipe.description)
    embedding = await _embedding_for(payload.title, payload.description) if new_text else None
    async with _writing_recipe(session):
        await write_recipe_ingredients(
            session, recipe, await _resolve_lines(session, payload.ingredients)
        )
        recipe.title = payload.title
        recipe.description = payload.description
        recipe.category = payload.category
        recipe.instructions = payload.instructions
        recipe.servings = payload.servings
        recipe.cost = payload.cost
        if new_text:
            recipe.embedding = embedding
        await adopt_import_page(session, recipe.id)
        await session.commit()
    # Le righe appena scritte non hanno l'ingrediente caricato: si rilegge la ricetta
    # intera invece di scoprirlo con un caricamento pigro, che in una sessione async è un
    # MissingGreenlet.
    session.expire(recipe)
    stored = await get_recipe(session, recipe_id)
    return await _to_out(session, stored)
```

- [ ] **Step 4: eseguilo e verifica che passi, poi le rotte delle ricette**

Run: `cd backend && $PYTEST -q tests/api/test_recipes_edit.py tests/api/test_recipes.py tests/api/test_recipes_category.py tests/api/test_recipes_cost.py`
Expected: PASS.

- [ ] **Step 5: commit**

```bash
git add backend/app/schemas/recipe.py backend/app/repositories/imports.py backend/app/api/recipes.py backend/tests/api/test_recipes_edit.py
git commit -m "$(cat <<'EOF'
ricette: PUT modifica la ricetta intera, e una ricetta importata diventa tua

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Eliminare e ripristinare: la `PATCH` con `archived`, e il dettaglio che lo dice

Spec §5 e §8.4 (le cotture restano legate); deviazioni 4 e 8.

**File:**
- Modify: `backend/app/schemas/recipe.py` (`RecipeUpdate`, `RecipeOut`, `RecipeSummaryOut`)
- Modify: `backend/app/repositories/imports.py` (in fondo)
- Modify: `backend/app/api/recipes.py` (`_to_out`, `search`, `update`)
- Test: `backend/tests/api/test_recipes_archive.py`

**Interfacce:**
- Consuma: `adopt_import_page`, `RECIPE_ARCHIVED` (Task 4).
- Produce:
  - `RecipeUpdate.archived: bool | None` (strict); la `PATCH` accetta `{"archived": true|false}`
  - `RecipeOut.archived_at: datetime | None`, `RecipeOut.owned_by_import: bool`,
    `RecipeSummaryOut.archived_at: datetime | None`
  - `async owned_by_import(session, recipe_id: uuid.UUID) -> bool` in
    `app/repositories/imports.py`

- [ ] **Step 1: scrivi il test che fallisce**

Crea `backend/tests/api/test_recipes_archive.py`:

```python
"""Eliminare archivia, con la lapide (R10 §5): la ricetta resta, e si ripristina.

Non c'è una `DELETE`: la `PATCH` accetta `archived`, come la dispensa. Il dettaglio
risponde anche per una ricetta archiviata, così un collegamento vecchio non finisce in
un 404.
"""

from app.db.models.recipe import CookingEvent, Recipe, RecipeSource
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportState, RecipeImport
from app.repositories.recipes import create_recipe

CARBONARA = "https://ricette.giallozafferano.it/Spaghetti-alla-Carbonara.html"


async def _ricetta(db_session, *, source=RecipeSource.MANUAL, source_ref=None, cost=None) -> Recipe:
    return await create_recipe(
        db_session, title="Carbonara", description=None, instructions="Manteca.",
        servings=2, source=source, source_ref=source_ref, ingredients=[], embedding=None,
        cost=cost,
    )


async def _archivia(client, ricetta, archived: bool):
    return await client.patch(f"/api/v1/recipes/{ricetta.id}", json={"archived": archived})


async def _dettaglio(client, ricetta) -> dict:
    risposta = await client.get(f"/api/v1/recipes/{ricetta.id}")
    assert risposta.status_code == 200, risposta.text
    return risposta.json()


async def test_eliminare_scrive_la_data_e_il_dettaglio_risponde_ancora(logged_client, db_session):
    ricetta = await _ricetta(db_session)

    risposta = await _archivia(logged_client, ricetta, True)

    assert risposta.status_code == 200, risposta.text
    assert risposta.json()["archived_at"] is not None
    assert (await _dettaglio(logged_client, ricetta))["archived_at"] == risposta.json()["archived_at"]


async def test_ripristinare_toglie_la_data(logged_client, db_session):
    ricetta = await _ricetta(db_session)
    await _archivia(logged_client, ricetta, True)

    risposta = await _archivia(logged_client, ricetta, False)

    assert risposta.json()["archived_at"] is None
    assert (await _dettaglio(logged_client, ricetta))["archived_at"] is None


async def test_eliminare_due_volte_tiene_la_prima_data(logged_client, db_session):
    ricetta = await _ricetta(db_session)
    prima = (await _archivia(logged_client, ricetta, True)).json()["archived_at"]
    assert (await _archivia(logged_client, ricetta, True)).json()["archived_at"] == prima


async def test_eliminare_una_ricetta_importata_la_prende_in_carico_per_sempre(
    logged_client, db_session, dal_database
):
    ricetta = await _ricetta(db_session, source=RecipeSource.DATASET, source_ref=CARBONARA)
    pagina = RecipeImport(
        source=GIALLOZAFFERANO, url=CARBONARA, payload={"title": "Carbonara", "ingredients": []},
        state=ImportState.IMPORTED, recipe_id=ricetta.id,
    )
    db_session.add(pagina)
    await db_session.flush()
    assert (await _dettaglio(logged_client, ricetta))["owned_by_import"] is True

    await _archivia(logged_client, ricetta, True)
    assert (await dal_database(RecipeImport, pagina.id)).state == ImportState.ADOPTED

    # ripristinare non la rende di nuovo dell'import (spec §4: non torna mai indietro)
    await _archivia(logged_client, ricetta, False)
    assert (await dal_database(RecipeImport, pagina.id)).state == ImportState.ADOPTED
    assert (await _dettaglio(logged_client, ricetta))["owned_by_import"] is False


async def test_una_ricetta_scritta_qui_non_e_dell_import(logged_client, db_session):
    ricetta = await _ricetta(db_session)
    assert (await _dettaglio(logged_client, ricetta))["owned_by_import"] is False


async def test_le_cotture_restano_legate(logged_client, db_session, dal_database):
    ricetta = await _ricetta(db_session)
    evento = CookingEvent(recipe_id=ricetta.id, servings=2, snapshot={"transitions": [], "restocked": 0})
    db_session.add(evento)
    await db_session.flush()

    await _archivia(logged_client, ricetta, True)
    assert (await dal_database(CookingEvent, evento.id)).recipe_id == ricetta.id
    await _archivia(logged_client, ricetta, False)
    assert (await dal_database(CookingEvent, evento.id)).recipe_id == ricetta.id


async def test_il_costo_di_una_ricetta_eliminata_non_si_cambia(logged_client, db_session):
    ricetta = await _ricetta(db_session, cost=2)
    await _archivia(logged_client, ricetta, True)

    risposta = await logged_client.patch(f"/api/v1/recipes/{ricetta.id}", json={"cost": 4})

    assert risposta.status_code == 409
    assert "ripristinala" in risposta.json()["detail"]
    # una PATCH vuota resta innocua anche qui
    assert (await logged_client.patch(f"/api/v1/recipes/{ricetta.id}", json={})).status_code == 200


async def test_archived_vuole_un_booleano(logged_client, db_session):
    ricetta = await _ricetta(db_session)
    risposta = await logged_client.patch(f"/api/v1/recipes/{ricetta.id}", json={"archived": "sì"})
    assert risposta.status_code == 422
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `cd backend && $PYTEST -q tests/api/test_recipes_archive.py`
Expected: FAIL — `KeyError: 'archived_at'` e `KeyError: 'owned_by_import'` nelle
risposte (i campi non esistono), e l'ultimo con 200 invece di 422: senza il campo
`archived` Pydantic ignora `"sì"`.

- [ ] **Step 3: implementazione minima**

In `backend/app/schemas/recipe.py` aggiungi `from datetime import datetime` e:

```python
class RecipeUpdate(BaseModel):
    """Quel che si cambia di una ricetta con un tocco: il costo, e l'eliminazione.

    Un campo assente non si tocca, `null` lo azzera: per questo la rotta legge
    `model_fields_set` e non il valore. `strict` perché `2.5` o `"3"` non sono un
    gradino, e arrotondarli sarebbe decidere al posto di chi ha toccato.

    `archived` elimina (`true`) e ripristina (`false`), come nella dispensa (R10 §5):
    non c'è una `DELETE`. Annullabile, perché «non l'ho detto» e «ripristina» sono due
    richieste diverse.
    """

    cost: int | None = Field(default=None, ge=COST_MIN, le=COST_MAX, strict=True)
    archived: bool | None = Field(default=None, strict=True)
```

In `RecipeOut`, dopo `dose_lines`:

```python
    # presente vuol dire eliminata (R10): il dettaglio risponde lo stesso, perché un
    # collegamento vecchio porti a «Ripristina» e non a un 404
    archived_at: datetime | None = None
    # vero finché una pagina dell'import la rifà: modificarla la rende tua, e lo schermo
    # di modifica lo dice prima del salvataggio (R10 §6.2)
    owned_by_import: bool = False
```

In `RecipeSummaryOut`, dopo `cost`:

```python
    # negli elenchi è sempre `None`, perché le archiviate ne sono escluse; c'è perché nel
    # frontend `RecipeDetail extends RecipeSummary`, come `missing_names` qui sopra
    archived_at: datetime | None = None
```

In `backend/app/repositories/imports.py`, in fondo:

```python
async def owned_by_import(session: AsyncSession, recipe_id: uuid.UUID) -> bool:
    """Vero se una pagina dell'import rifà ancora questa ricetta: è `imported`, non
    presa in carico (R10 §4)."""
    found = await session.scalar(
        select(RecipeImport.id)
        .where(RecipeImport.recipe_id == recipe_id, RecipeImport.state == ImportState.IMPORTED)
        .limit(1)
    )
    return found is not None
```

In `backend/app/api/recipes.py`: `from datetime import UTC, datetime` e
`owned_by_import` accanto ad `adopt_import_page` negli import. In `_to_out`, fra gli
argomenti di `RecipeOut(...)`:

```python
        archived_at=recipe.archived_at,
        owned_by_import=await owned_by_import(session, recipe.id),
```

nella rotta `search`, fra gli argomenti di `RecipeSummaryOut(...)`:

```python
            archived_at=r.recipe.archived_at,
```

e la rotta `update` diventa:

```python
@router.patch("/{recipe_id}", response_model=RecipeOut)
async def update(
    recipe_id: uuid.UUID, payload: RecipeUpdate, session: AsyncSession = Depends(get_session)
) -> RecipeOut:
    """Cambia quel che `RecipeUpdate` dichiara, e solo i campi mandati davvero.

    `archived` elimina e ripristina (R10 §5). Eliminare prende in carico la pagina
    d'import, come il primo salvataggio di una modifica; ripristinare no, e la pagina
    resta `adopted`. Il costo di una ricetta eliminata non si cambia, come il resto: il
    409 lo dice prima di toccare qualunque cosa.
    """
    recipe = await get_recipe(session, recipe_id)
    if recipe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ricetta inesistente")
    archived_after = (
        recipe.archived_at is not None if payload.archived is None else payload.archived
    )
    if "cost" in payload.model_fields_set and archived_after:
        raise HTTPException(status.HTTP_409_CONFLICT, RECIPE_ARCHIVED)
    if payload.archived is True:
        # la prima data resta: eliminare due volte non sposta l'eliminazione
        if recipe.archived_at is None:
            recipe.archived_at = datetime.now(UTC)
        await adopt_import_page(session, recipe.id)
    elif payload.archived is False:
        recipe.archived_at = None
    if "cost" in payload.model_fields_set:
        recipe.cost = payload.cost
    await session.commit()
    return await _to_out(session, recipe)
```

- [ ] **Step 4: eseguilo e verifica che passi, poi la suite**

Run: `cd backend && $PYTEST -q tests/api/test_recipes_archive.py tests/api/test_recipes_cost.py`
Expected: PASS — i test del costo di R9 non cambiano.

Run: `cd backend && $PYTEST -q`
Expected: tutto verde.

- [ ] **Step 5: commit**

```bash
git add backend/app/schemas/recipe.py backend/app/repositories/imports.py backend/app/api/recipes.py backend/tests/api/test_recipes_archive.py
git commit -m "$(cat <<'EOF'
ricette: eliminare archivia, ripristinare riporta, e il dettaglio risponde lo stesso

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Tutto quel che elenca ricette esclude le archiviate

Spec §5 (l'elenco da coprire) e §8.4; deviazioni 1 e 6.

**File:**
- Modify: `backend/app/services/recipe_search.py` (`_semantic_ranking`, `_textual_ranking`, `_browse`)
- Modify: `backend/app/repositories/recipes.py` (`recipe_categories`)
- Modify: `backend/app/cli/reindex.py` (`reindex`)
- Test: `backend/tests/api/test_recipes_archived_lists.py`

**Interfacce:**
- Consuma: la `PATCH` con `archived` (Task 5).
- Produce: nessuna firma nuova. Le tre query del ricettario, `recipe_categories` e
  `reindex` filtrano `Recipe.archived_at IS NULL` **nella stessa query che porta il
  limite**. `recipes_using` e `ingredient_usage` dell'anagrafica restano come sono
  (deviazione 6): non si toccano, e nessun test qui li riguarda.

- [ ] **Step 1: scrivi il test che fallisce**

Crea `backend/tests/api/test_recipes_archived_lists.py`:

```python
"""Tutto quel che elenca ricette esclude le archiviate (R10 §5, §8.4).

Un test per voce, perché una voce dimenticata è il modo più facile di mostrare una
ricetta eliminata (spec §9). Ognuno elimina e ripristina passando dalla rotta vera.

Tre test in più mettono l'esclusione davanti al limite: più ricette archiviate che
posti nella piscina dei candidati (o nella pagina), tutte davanti alla viva
nell'ordine. Un filtro applicato dopo il `.limit()` perderebbe la viva: la sesta
lezione di CLAUDE.md.

Lo sfoglio non ha un filtro per costo (R9 ha deciso di non averne): i filtri provati
sono quelli che `_browse` ha davvero (deviazione 1 del piano).
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.cli.reindex import reindex
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.recipe import EMBEDDING_DIM, Recipe, RecipeSource
from app.domain.rules import PantryStatus
from app.repositories.recipes import create_recipe
from app.services.recipe_search import CANDIDATE_POOL


async def _ricetta(db_session, titolo, righe=(), *, embedding=None, category=None) -> Recipe:
    return await create_recipe(
        db_session, title=titolo, description=None, instructions="Cuoci.", servings=2,
        source=RecipeSource.MANUAL, source_ref=None, ingredients=list(righe),
        embedding=embedding, category=category,
    )


def _archiviata_da_sempre(ricetta: Recipe) -> None:
    """Per i mondi di cento ricette la data si scrive direttamente: cento PATCH non
    proverebbero niente di più. Le prove per voce passano dalla rotta."""
    ricetta.archived_at = datetime.now(UTC)


async def _archivia(client, ricetta, archived=True):
    risposta = await client.patch(f"/api/v1/recipes/{ricetta.id}", json={"archived": archived})
    assert risposta.status_code == 200, risposta.text


async def _titoli(client, query="") -> set[str]:
    risposta = await client.get(f"/api/v1/recipes/search?{query}")
    assert risposta.status_code == 200, risposta.text
    return {r["title"] for r in risposta.json()}


def _vettore_a_distanza(distanza: float) -> list[float]:
    """Unitario, nel piano dei primi due assi, a `distanza` coseno dal punto 0: la
    distanza che il database calcolerà si verifica a mente. È la stessa costruzione di
    `tests/api/test_recipes.py`, ricopiata perché i file di test non si importano fra
    loro."""
    coseno = 1.0 - distanza
    vettore = [0.0] * EMBEDDING_DIM
    vettore[0] = coseno
    vettore[1] = (1.0 - coseno**2) ** 0.5
    return vettore


@pytest.fixture
def query_nel_punto_zero(monkeypatch):
    from app.services import recipe_search

    async def embed(_: str) -> list[float]:
        return _vettore_a_distanza(0.0)

    monkeypatch.setattr(recipe_search, "_embed_query", embed)


@pytest_asyncio.fixture
async def ricettario(db_session):
    """Due ricette che ogni filtro dello sfoglio trova: cucinabili, con la pasta, a cui
    manca al più una cosa, e in «Primi piatti». Una delle due si eliminerà."""
    pasta = Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
    db_session.add(pasta)
    await db_session.flush()
    db_session.add(PantryItem(ingredient_id=pasta.id, status=PantryStatus.AVAILABLE))
    riga = [(pasta.id, "primary", "320 g", None)]
    await _ricetta(db_session, "Pasta in bianco", riga, category="Primi piatti")
    eliminata = await _ricetta(db_session, "Pasta al burro", riga, category="Primi piatti")
    await db_session.flush()
    return pasta, eliminata


FILTRI = {
    "senza filtri": lambda pasta: "",
    "cucinabili": lambda pasta: "max_missing=0",
    "per ingrediente": lambda pasta: f"ingredient_id={pasta.id}",
    "mancanti al più uno": lambda pasta: "max_missing=1",
    "categoria": lambda pasta: "category=Primi%20piatti",
}


@pytest.mark.parametrize("filtro", list(FILTRI))
async def test_lo_sfoglio_esclude_le_eliminate_e_le_ritrova_ripristinate(
    logged_client, ricettario, filtro
):
    pasta, eliminata = ricettario
    query = FILTRI[filtro](pasta)
    entrambe = {"Pasta in bianco", "Pasta al burro"}
    assert await _titoli(logged_client, query) == entrambe

    await _archivia(logged_client, eliminata)
    assert await _titoli(logged_client, query) == {"Pasta in bianco"}

    await _archivia(logged_client, eliminata, archived=False)
    assert await _titoli(logged_client, query) == entrambe


async def test_lo_sfoglio_esclude_le_eliminate_prima_della_pagina(logged_client, db_session):
    for numero in range(35):
        _archiviata_da_sempre(await _ricetta(db_session, f"Anguria {numero:02d}"))
    await _ricetta(db_session, "Zucca al forno")
    await db_session.flush()

    # la pagina è di 30 e l'ordine, a parità di mancanti, è per titolo: le 35
    # archiviate starebbero tutte davanti alla viva
    assert await _titoli(logged_client, "limit=30") == {"Zucca al forno"}


async def test_la_ricerca_testuale_esclude_le_eliminate(logged_client, db_session):
    await _ricetta(db_session, "Zuppa di pane")
    eliminata = await _ricetta(db_session, "Zuppa di ceci")
    await db_session.flush()
    entrambe = {"Zuppa di pane", "Zuppa di ceci"}
    # senza vettori: le trova solo la metà testuale
    assert await _titoli(logged_client, "q=zuppa") == entrambe

    await _archivia(logged_client, eliminata)
    assert await _titoli(logged_client, "q=zuppa") == {"Zuppa di pane"}

    await _archivia(logged_client, eliminata, archived=False)
    assert await _titoli(logged_client, "q=zuppa") == entrambe


async def test_la_ricerca_testuale_esclude_le_eliminate_prima_della_piscina(
    logged_client, db_session
):
    for numero in range(CANDIDATE_POOL + 5):
        _archiviata_da_sempre(await _ricetta(db_session, f"Zuppa zuppa zuppa {numero}"))
    await _ricetta(db_session, "Zuppa di pane")
    await db_session.flush()

    # le archiviate dicono «zuppa» tre volte, e `ts_rank` le metterebbe tutte davanti
    assert await _titoli(logged_client, "q=zuppa") == {"Zuppa di pane"}


async def test_la_ricerca_semantica_esclude_le_eliminate(
    logged_client, db_session, query_nel_punto_zero
):
    await _ricetta(db_session, "Ricetta vicina", embedding=_vettore_a_distanza(0.10))
    eliminata = await _ricetta(db_session, "Ricetta vicinissima", embedding=_vettore_a_distanza(0.05))
    await db_session.flush()
    entrambe = {"Ricetta vicina", "Ricetta vicinissima"}
    # «xyzzy» non compare in nessun titolo: le trova solo la metà semantica
    assert await _titoli(logged_client, "q=xyzzy") == entrambe

    await _archivia(logged_client, eliminata)
    assert await _titoli(logged_client, "q=xyzzy") == {"Ricetta vicina"}

    await _archivia(logged_client, eliminata, archived=False)
    assert await _titoli(logged_client, "q=xyzzy") == entrambe


async def test_la_ricerca_semantica_esclude_le_eliminate_prima_della_piscina(
    logged_client, db_session, query_nel_punto_zero
):
    for numero in range(CANDIDATE_POOL + 5):
        _archiviata_da_sempre(
            await _ricetta(db_session, f"Vicinissima {numero}", embedding=_vettore_a_distanza(0.05))
        )
    await _ricetta(db_session, "Ricetta vicina", embedding=_vettore_a_distanza(0.10))
    await db_session.flush()
    # L'indice HNSW è approssimato: se il pianificatore lo usa, un filtro nella stessa
    # query vede solo i primi `ef_search` vicini (40 di default). Alzarlo al massimo
    # prova la cosa che questo test prova — dove sta il filtro rispetto al limite — e
    # non la precisione dell'indice.
    await db_session.execute(text("SET LOCAL hnsw.ef_search = 1000"))

    assert await _titoli(logged_client, "q=xyzzy") == {"Ricetta vicina"}


async def test_le_categorie_non_contano_le_eliminate(logged_client, db_session):
    await _ricetta(db_session, "Pasta e fagioli", category="Primi piatti")
    dolce = await _ricetta(db_session, "Tiramisù", category="Dolci")
    await db_session.flush()

    async def categorie():
        return (await logged_client.get("/api/v1/recipes/categories")).json()

    assert await categorie() == ["Dolci", "Primi piatti"]
    await _archivia(logged_client, dolce)
    assert await categorie() == ["Primi piatti"]
    await _archivia(logged_client, dolce, archived=False)
    assert await categorie() == ["Dolci", "Primi piatti"]


async def test_reindex_salta_le_eliminate_e_le_ritrova_ripristinate(logged_client, db_session):
    ricetta = await _ricetta(db_session, "Senza vettore")
    await db_session.flush()

    await _archivia(logged_client, ricetta)
    assert await reindex(db_session) == 0

    await _archivia(logged_client, ricetta, archived=False)
    assert await reindex(db_session) == 1
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `cd backend && $PYTEST -q tests/api/test_recipes_archived_lists.py`
Expected: FAIL — ogni prova trova ancora la ricetta archiviata (`{'Pasta in bianco',
'Pasta al burro'} != {'Pasta in bianco'}`), le categorie contano ancora «Dolci»,
`reindex` restituisce 1 invece di 0, e le tre prove della piscina non trovano la viva.

- [ ] **Step 3: implementazione minima**

In `backend/app/services/recipe_search.py`:

`_semantic_ranking`, la `where`:

```python
        .where(
            Recipe.embedding.is_not(None),
            # dentro la query che ha il limite, non dopo: altrimenti cento archiviate
            # vicine riempirebbero la piscina (R10, sesta lezione di CLAUDE.md)
            Recipe.archived_at.is_(None),
            distance <= SEMANTIC_MAX_DISTANCE,
        )
```

`_textual_ranking`, la `where`:

```python
        .where(Recipe.search_tsv.op("@@")(ts_query), Recipe.archived_at.is_(None))
```

`_browse`, lo `statement` iniziale:

```python
    statement = (
        select(Recipe.id, missing)
        .outerjoin(line, line.recipe_id == Recipe.id)
        # prima della pagina, come ogni altro filtro dello sfoglio (R10)
        .where(Recipe.archived_at.is_(None))
        .group_by(Recipe.id)
    )
```

In `backend/app/repositories/recipes.py`, `recipe_categories`:

```python
    rows = await session.execute(
        select(Recipe.category)
        .where(Recipe.category.is_not(None), Recipe.archived_at.is_(None))
        .distinct()
        .order_by(Recipe.category)
    )
```

e nella docstring una riga: «Le ricette eliminate non contano: una categoria che
resta solo su quelle porterebbe a un filtro vuoto (R10).»

In `backend/app/cli/reindex.py`, la query del lotto:

```python
        rows = await session.execute(
            select(Recipe)
            # un'eliminata non si cerca, e il vettore lo riceve se torna (R10)
            .where(Recipe.embedding.is_(None), Recipe.archived_at.is_(None))
            .limit(BATCH)
        )
```

- [ ] **Step 4: eseguilo e verifica che passi, poi la ricerca**

Run: `cd backend && $PYTEST -q tests/api/test_recipes_archived_lists.py tests/services/test_recipe_search.py tests/api/test_recipes.py tests/services/test_semantic_degradation.py tests/test_reindex_cli.py`
Expected: PASS.

- [ ] **Step 5: commit**

```bash
git add backend/app/services/recipe_search.py backend/app/repositories/recipes.py backend/app/cli/reindex.py backend/tests/api/test_recipes_archived_lists.py
git commit -m "$(cat <<'EOF'
ricette: le eliminate escono da ricerca, sfoglio, categorie e reindex, prima di ogni limite

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: La presa in carico contro l'import

Spec §4 e §8.3; deviazioni 5 e 7.

**File:**
- Modify: `backend/app/services/recipe_import/undo.py` (`Undone`, `_imported_pages_with`, `undo_decision`)
- Modify: `backend/app/schemas/recipe_import.py` (`UndoOut`, righe 91–94)
- Modify: `backend/app/api/imports.py` (la rotta `undo`, righe 245–273)
- Modify: `backend/app/cli/reread_costs.py` (la query di `reread_costs`)
- Test: `backend/tests/api/test_recipes_adoption.py`, `backend/tests/test_reread_costs_cli.py`

**Interfacce:**
- Consuma: la `PUT` (Task 4), `ImportState.ADOPTED` (Task 1); `merge_ingredients(session, loser_id, winner_id) -> MergeCounts`
  e `materialize_ready`, invariati.
- Produce:
  - `Undone.adopted_untouched: int`, `Undone.ingredient_kept_for_adopted: bool`
  - `UndoOut.adopted_untouched: int = 0`, `UndoOut.ingredient_kept_for_adopted: bool = False`
  - `_pages_with(session, term, state: ImportState) -> list[RecipeImport]` (sostituisce
    `_imported_pages_with`)

**Tre prove su cinque passano già** dopo il Task 4, ed è il punto: la spec §4 dice che
fusione, materializzazione e risincronizzazione lasciano stare una pagina `adopted`
«senza codice nuovo». Qui lo provano; guidano codice solo l'annullamento e
`reread_costs`.

- [ ] **Step 1: scrivi i test che falliscono**

Crea `backend/tests/api/test_recipes_adoption.py`:

```python
"""La presa in carico contro l'import (R10 §4, §8.3).

Due pagine dell'import con gli stessi due termini: la carbonara diventa tua con una
PUT, come la rende tua l'app; l'amatriciana resta dell'import. Ogni percorso che rifà
le ricette deve toccare la seconda e lasciare la prima.
"""

from datetime import UTC, datetime

import pytest_asyncio
from sqlalchemy import func, select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import Recipe
from app.db.models.recipe_import import (
    GIALLOZAFFERANO,
    ImportState,
    ImportTerm,
    RecipeImport,
    TermDecision,
)
from app.repositories.imports import known_urls, store_page
from app.repositories.ingredients import remember_alias
from app.services.recipe_import.materialize import materialize_ready
from app.services.registry import merge_ingredients

CARBONARA = "https://ricette.giallozafferano.it/Spaghetti-alla-Carbonara.html"
AMATRICIANA = "https://ricette.giallozafferano.it/Bucatini-all-Amatriciana.html"


def _payload(titolo: str) -> dict:
    return {
        "title": titolo, "description": None, "instructions": "Cuoci.", "servings": 4,
        "ingredients": [
            {"key": "k-spaghetti", "name": "Spaghetti", "quantity_text": "320 g"},
            {"key": "k-guanciale", "name": "Guanciale", "quantity_text": "150 g"},
        ],
    }


@pytest_asyncio.fixture
async def mondo(db_session):
    def voce(name: str, category: str) -> Ingredient:
        return Ingredient(name=name, display_name=name.capitalize(), category=category)

    voci = {
        "pasta": voce("pasta", IngredientCategory.CEREALI),
        "guanciale": voce("guanciale", IngredientCategory.CARNE),
        "pancetta": voce("pancetta", IngredientCategory.CARNE),
    }
    db_session.add_all(voci.values())
    await db_session.flush()

    def termine(key: str, display: str, voce_: str) -> ImportTerm:
        return ImportTerm(
            source=GIALLOZAFFERANO, term_key=key, display_name=display, occurrences=2,
            decision=TermDecision.MAPPED, ingredient_id=voci[voce_].id, decided_by="ai",
            decided_at=datetime.now(UTC),
        )

    termini = {
        "spaghetti": termine("k-spaghetti", "Spaghetti", "pasta"),
        "t-guanciale": termine("k-guanciale", "Guanciale", "guanciale"),
    }
    db_session.add_all(termini.values())
    await db_session.flush()
    for term in termini.values():
        await remember_alias(db_session, term.ingredient_id, term.display_name)
    for url, titolo in ((CARBONARA, "Spaghetti alla carbonara"), (AMATRICIANA, "Bucatini all'amatriciana")):
        await store_page(db_session, source=GIALLOZAFFERANO, url=url, payload=_payload(titolo))
    await materialize_ready(db_session, GIALLOZAFFERANO)
    return {**voci, **termini}


async def _pagina(db_session, url: str) -> RecipeImport:
    return (
        await db_session.execute(select(RecipeImport).where(RecipeImport.url == url))
    ).scalar_one()


async def _adotta(client, db_session, url: str, titolo: str) -> str:
    """Rende tua la ricetta di quella pagina come la rende tua l'app: con una PUT."""
    pagina = await _pagina(db_session, url)
    dettaglio = (await client.get(f"/api/v1/recipes/{pagina.recipe_id}")).json()
    corpo = {
        "title": titolo, "description": dettaglio["description"],
        "category": dettaglio["category"], "instructions": dettaglio["instructions"],
        "servings": dettaglio["servings"], "cost": dettaglio["cost"],
        "ingredients": [
            {"ingredient_id": r["ingredient_id"], "role": r["role"],
             "quantity_text": r["quantity_text"], "note": r["note"]}
            for r in dettaglio["ingredients"]
        ],
    }
    risposta = await client.put(f"/api/v1/recipes/{pagina.recipe_id}", json=corpo)
    assert risposta.status_code == 200, risposta.text
    return dettaglio["id"]


async def _ricetta(client, recipe_id: str) -> dict:
    return (await client.get(f"/api/v1/recipes/{recipe_id}")).json()


async def test_annullare_il_termine_lascia_intatta_la_ricetta_tua_e_la_conta(
    logged_client, db_session, mondo
):
    mia = await _adotta(logged_client, db_session, CARBONARA, "La mia carbonara")

    risposta = await logged_client.post(f"/api/v1/imports/terms/{mondo['t-guanciale'].id}/undo")

    assert risposta.status_code == 200, risposta.text
    esito = risposta.json()
    assert esito["recipes_requeued"] == 1  # l'amatriciana, ancora dell'import
    assert esito["adopted_untouched"] == 1  # la carbonara, tua
    assert esito["ingredient_deleted"] is False
    assert esito["ingredient_kept_for_adopted"] is True
    ricetta = await _ricetta(logged_client, mia)
    assert ricetta["title"] == "La mia carbonara"
    assert {r["ingredient_name"] for r in ricetta["ingredients"]} == {"pasta", "guanciale"}
    assert (await _pagina(db_session, CARBONARA)).state == ImportState.ADOPTED
    assert (await _pagina(db_session, AMATRICIANA)).state == ImportState.PENDING


async def test_rideciso_il_termine_l_import_rifa_solo_la_sua(logged_client, db_session, mondo):
    mia = await _adotta(logged_client, db_session, CARBONARA, "La mia carbonara")
    termine = mondo["t-guanciale"]
    await logged_client.post(f"/api/v1/imports/terms/{termine.id}/undo")

    risposta = await logged_client.post(
        f"/api/v1/imports/terms/{termine.id}/decision",
        json={"action": "map", "ingredient_id": str(mondo["pancetta"].id)},
    )

    assert risposta.status_code == 200, risposta.text
    assert risposta.json()["unlocked"] == 1  # l'amatriciana torna, con la pancetta
    quante = await db_session.scalar(
        select(func.count()).select_from(Recipe).where(Recipe.source_ref == CARBONARA)
    )
    assert quante == 1  # la carbonara resta una, la tua
    ricetta = await _ricetta(logged_client, mia)
    assert {r["ingredient_name"] for r in ricetta["ingredients"]} == {"pasta", "guanciale"}


async def test_una_fusione_sposta_in_loco_la_riga_della_ricetta_tua(
    logged_client, db_session, mondo
):
    mia = await _adotta(logged_client, db_session, CARBONARA, "La mia carbonara")

    conti = await merge_ingredients(db_session, mondo["guanciale"].id, mondo["pancetta"].id)
    await db_session.flush()

    assert conti.recipe_lines_moved == 1  # la tua, spostata dov'è
    assert conti.recipes_rebuilt == 1  # l'amatriciana, rifatta dal payload
    ricetta = await _ricetta(logged_client, mia)
    assert ricetta["title"] == "La mia carbonara"
    assert {r["ingredient_name"] for r in ricetta["ingredients"]} == {"pasta", "pancetta"}


async def test_materialize_ready_non_tocca_la_pagina_presa_in_carico(
    logged_client, db_session, mondo
):
    mia = await _adotta(logged_client, db_session, CARBONARA, "La mia carbonara")

    esito = await materialize_ready(db_session, GIALLOZAFFERANO)

    assert esito.created == 0
    pagina = await _pagina(db_session, CARBONARA)
    assert (pagina.state, str(pagina.recipe_id)) == (ImportState.ADOPTED, mia)


async def test_la_risincronizzazione_salta_l_indirizzo_della_ricetta_tua(
    logged_client, db_session, mondo
):
    """`_new_urls` di `import_gz` scarta ogni indirizzo che `known_urls` conosce."""
    await _adotta(logged_client, db_session, CARBONARA, "La mia carbonara")
    assert CARBONARA in await known_urls(db_session, GIALLOZAFFERANO)
```

In `backend/tests/test_reread_costs_cli.py`, in fondo (`pagina(costo)` è la funzione
del file che costruisce l'HTML, quindi la riga d'import si chiama `riga_import`):

```python
@respx.mock
async def test_una_ricetta_presa_in_carico_non_si_rilegge(db_session):
    """R10: modificata o eliminata a mano, la ricetta è tua, e un costo tolto a mano
    resta tolto."""
    recipe = await ricetta(db_session, "Carbonara-mia")
    riga_import = (await db_session.execute(select(RecipeImport))).scalars().one()
    riga_import.state = ImportState.ADOPTED
    await db_session.flush()
    rotta = respx.get(f"{BASE}/Carbonara-mia.html").mock(
        return_value=httpx.Response(200, text=pagina("Basso"))
    )
    async with build_client() as client:
        esito = await reread_costs(db_session, client=client, sleep=Pause())

    assert esito.found == 0
    assert not rotta.called
    await db_session.refresh(recipe)
    assert recipe.cost is None
```

- [ ] **Step 2: eseguili e verifica quali falliscono**

Run: `cd backend && $PYTEST -q tests/api/test_recipes_adoption.py tests/test_reread_costs_cli.py`
Expected: FAIL due — `KeyError: 'adopted_untouched'` nel primo test, e
`assert not rotta.called` in quello di `reread_costs`. Gli altri quattro della presa in
carico PASSANO già (vedi sopra): se uno di loro fallisce, fermati — vuol dire che un
percorso dell'import rifà le ricette `adopted`, e la spec §4 va riletta prima di
scrivere codice.

- [ ] **Step 3: implementazione minima**

In `backend/app/services/recipe_import/undo.py`, agli import:

```python
from app.db.models.recipe import CookingEvent, Recipe, RecipeIngredient
```

`Undone`:

```python
@dataclass(frozen=True)
class Undone:
    recipes_requeued: int
    ingredient_deleted: bool
    alias_forgotten: bool
    # le ricette prese in carico che contengono il termine: l'annullamento non le tocca,
    # e la coda lo dice (R10 §4)
    adopted_untouched: int
    # l'ingrediente del termine non è stato cancellato e una di quelle ricette lo usa:
    # resta per lei. Non dice se la decisione l'aveva creato — nessun fatto scritto lo
    # distingue (vedi `_decided_action` in api/imports.py)
    ingredient_kept_for_adopted: bool
```

`_imported_pages_with` diventa `_pages_with`, con lo stato come argomento. La docstring
cambia la prima riga, tiene i due paragrafi di prima e ne guadagna uno in fondo:

```python
async def _pages_with(
    session: AsyncSession, term: ImportTerm, state: ImportState
) -> list[RecipeImport]:
    """Le pagine in quello stato, con una ricetta, che contengono questo termine.

    Contenimento JSONB e non una scansione in Python: le pagine importate crescono con
    il ricettario, e caricarle tutte per leggerne una chiave sarebbe la stessa scelta
    che CLAUDE.md segnala su `recipe_search.py` — un limite scritto quando i dati erano
    pochi. Nessun indice nuovo (la feature non aggiunge migrazioni): resta una
    scansione, ma dentro il database e senza materializzare le righe, su
    un'operazione che si fa a mano e di rado.

    `recipe_id IS NOT NULL` distingue una pagina da rifare da una la cui ricetta
    l'utente ha cancellato: quella resta `imported`, perché è lo stato e non la
    presenza della chiave a dire «già importata una volta» (modello `RecipeImport`).

    `imported` sono quelle da rifare; `adopted` quelle prese in carico (R10), che non si
    toccano e si contano soltanto.
    """
    rows = await session.execute(
        select(RecipeImport).where(
            RecipeImport.source == term.source,
            RecipeImport.state == state,
            RecipeImport.recipe_id.is_not(None),
            RecipeImport.payload["ingredients"].op("@>")(
                func.jsonb_build_array(func.jsonb_build_object("key", term.term_key))
            ),
        )
    )
    return list(rows.scalars())
```

In `undo_decision`: la prima riga diventa

```python
    pages = await _pages_with(session, term, ImportState.IMPORTED)
    adopted = await _pages_with(session, term, ImportState.ADOPTED)
```

e dopo il blocco che chiama `delete_ingredient_if_unused`, prima dell'ultimo `flush`:

```python
    kept_for_adopted = False
    if ingredient_id is not None and not ingredient_deleted and adopted:
        # l'ingrediente è rimasto: lo dice solo se è una ricetta tua a tenerlo
        kept_for_adopted = (
            await session.scalar(
                select(RecipeIngredient.id)
                .where(
                    RecipeIngredient.ingredient_id == ingredient_id,
                    RecipeIngredient.recipe_id.in_([page.recipe_id for page in adopted]),
                )
                .limit(1)
            )
        ) is not None
```

e il `return`:

```python
    return Undone(
        recipes_requeued=requeued,
        ingredient_deleted=ingredient_deleted,
        alias_forgotten=alias_forgotten,
        adopted_untouched=len(adopted),
        ingredient_kept_for_adopted=kept_for_adopted,
    )
```

(La docstring del modulo si riscrive nel Task 15, con gli altri emendamenti.)

In `backend/app/schemas/recipe_import.py`:

```python
class UndoOut(BaseModel):
    recipes_requeued: int
    ingredient_deleted: bool
    remaining_terms: int
    # R10: le ricette tue che contengono il termine, lasciate come sono
    adopted_untouched: int = 0
    ingredient_kept_for_adopted: bool = False
```

In `backend/app/api/imports.py`, nel `return UndoOut(...)` della rotta `undo`:

```python
        adopted_untouched=undone.adopted_untouched,
        ingredient_kept_for_adopted=undone.ingredient_kept_for_adopted,
```

In `backend/app/cli/reread_costs.py`: `from app.db.models.recipe_import import ImportState, RecipeImport`,
e nella `where` della query di `reread_costs`, dopo la condizione su `source_ref`:

```python
                # una ricetta presa in carico è tua (R10): un costo tolto a mano resta
                # tolto, e l'import non riscrive quel che hai toccato
                ~select(RecipeImport.id)
                .where(
                    RecipeImport.recipe_id == Recipe.id,
                    RecipeImport.state == ImportState.ADOPTED,
                )
                .exists(),
```

- [ ] **Step 4: eseguili e verifica che passino, poi la suite intera**

Run: `cd backend && $PYTEST -q tests/api/test_recipes_adoption.py tests/test_reread_costs_cli.py tests/services/test_undo.py tests/api/test_imports_undo.py tests/services/test_registry_merge.py`
Expected: PASS.

Run: `cd backend && $PYTEST -q`
Expected: tutto verde. **Fine della Consegna 1**: annota il numero di test.

- [ ] **Step 5: commit**

```bash
git add backend/app/services/recipe_import/undo.py backend/app/schemas/recipe_import.py backend/app/api/imports.py backend/app/cli/reread_costs.py backend/tests/api/test_recipes_adoption.py backend/tests/test_reread_costs_cli.py
git commit -m "$(cat <<'EOF'
import: le ricette prese in carico non si rifanno, e l'annullamento le conta

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

# Consegna 2 — le schermate

Da qui in poi i comandi partono da `<worktree>/frontend`, salvo dove detto.

### Task 8: I tipi, le chiamate e il modello del modulo

Spec §6.2 e §9 (i tipi); deviazione 12.

**File:**
- Modify: `frontend/src/domain/types.ts` (`RecipeSummary`, `RecipeDetail`, `UndoResult`; due tipi nuovi)
- Modify: `frontend/src/features/recipes/api.ts` (`createRecipe`; due funzioni nuove)
- Modify: `frontend/src/features/cooking/CookSheet.test.tsx`, `frontend/src/features/cooking/RecipeDetailScreen.test.tsx`,
  `frontend/src/features/recipes/RecipeCard.test.tsx` — solo i letterali tipizzati
- Create: `frontend/src/features/recipe-form/formModel.ts`
- Test: `frontend/src/features/recipe-form/formModel.test.ts`

**Interfacce:**
- Consuma: la forma di `RecipeOut`, `RecipeSummaryOut`, `UndoOut` dei Task 5 e 7.
- Produce:
  - `RecipeSummary.archived_at: string | null`, `RecipeDetail.owned_by_import: boolean`,
    `UndoResult.adopted_untouched: number`, `UndoResult.ingredient_kept_for_adopted: boolean`
  - `interface RecipeIngredientBody { ingredient_id?: string; name?: string; category?: string | null; role: IngredientRole; quantity_text: string | null; note?: string }`
  - `interface RecipeBody { title; description: string | null; category: string | null; instructions; servings: number | null; cost: number | null; ingredients: RecipeIngredientBody[] }`
  - `createRecipe(body: RecipeBody & { source: RecipeSource; source_ref: string | null }): Promise<RecipeDetail>`
  - `updateRecipe(id: string, body: RecipeBody): Promise<RecipeDetail>` (PUT)
  - `setRecipeArchived(id: string, archived: boolean): Promise<RecipeDetail>` (PATCH)
  - da `formModel.ts`: `TITLE_MAX`, `QUANTITY_MAX`, `interface FormLine`,
    `interface RecipeFormValues`, `EMPTY_FORM`, `lineFromDraft(line, index)`,
    `lineFromIngredient(ingredient)`, `lineFromRecipe(line)`, `valuesFromRecipe(recipe)`,
    `applyDraft(values, draft)`, `savableLines(lines)`, `matchNote(line)`,
    `showsMatch(line)`, `validationProblem(values): string | null`,
    `recipeBody(values): RecipeBody`

- [ ] **Step 1: scrivi il test che fallisce**

Crea `frontend/src/features/recipe-form/formModel.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { DraftIngredient, Ingredient, RecipeDetail, RecipeDraft } from "../../domain/types";
import {
  EMPTY_FORM,
  applyDraft,
  lineFromDraft,
  lineFromIngredient,
  recipeBody,
  showsMatch,
  validationProblem,
  valuesFromRecipe,
} from "./formModel";

const DETAIL: RecipeDetail = {
  id: "r1", title: "Pasta al pomodoro", description: null, source: "dataset",
  missing: 0, cookable: true, missing_names: [], image_url: null, prep_minutes: null,
  cook_minutes: null, category: "Primi piatti", cost: 2, archived_at: null,
  instructions: "Cuoci.", servings: 4, source_ref: "https://esempio.invalid/pasta",
  scaled_to: null, unscalable_lines: 0, dose_lines: 1, owned_by_import: true,
  ingredients: [
    { ingredient_id: "i1", ingredient_name: "pasta", role: "primary", quantity_text: "320 g",
      quantity_display: "320 g", quantity_scaled: false, note: "al dente",
      availability: "available", satisfied: true },
    { ingredient_id: "i2", ingredient_name: "basilico", role: "secondary", quantity_text: null,
      quantity_display: null, quantity_scaled: false, note: null,
      availability: "missing", satisfied: false },
  ],
};

const ZAFFERANO: Ingredient = {
  id: "i9", name: "zafferano", display_name: "Zafferano", category: "spezie", kind: "food",
};

function bozza(overrides: Partial<DraftIngredient>): DraftIngredient {
  return {
    raw_name: "pasta", role: "primary", quantity_text: "180 g", ingredient_id: "i1",
    matched_name: "pasta", confident: true, proposed_category: null, ...overrides,
  };
}

describe("il modulo riempito da una ricetta salvata", () => {
  it("riprende i campi, la dose scritta e la nota", () => {
    const values = valuesFromRecipe(DETAIL);

    expect(values).toMatchObject({
      title: "Pasta al pomodoro", description: "", category: "Primi piatti",
      servingsText: "4", cost: 2, instructions: "Cuoci.",
    });
    expect(values.lines.map((l) => [l.label, l.role, l.quantityText, l.note, l.included])).toEqual([
      ["pasta", "primary", "320 g", "al dente", true],
      ["basilico", "secondary", "", null, true],
    ]);
  });

  it("la dose è quella scritta, non quella riscalata", () => {
    const riscalata: RecipeDetail = {
      ...DETAIL,
      ingredients: [{ ...DETAIL.ingredients[0], quantity_display: "640 g", quantity_scaled: true }],
    };
    expect(valuesFromRecipe(riscalata).lines[0].quantityText).toBe("320 g");
  });

  it("salvato senza toccare niente, torna identico, con la nota solo dove c'è", () => {
    expect(recipeBody(valuesFromRecipe(DETAIL))).toEqual({
      title: "Pasta al pomodoro", description: null, category: "Primi piatti",
      instructions: "Cuoci.", servings: 4, cost: 2,
      ingredients: [
        { ingredient_id: "i1", role: "primary", quantity_text: "320 g", note: "al dente" },
        { ingredient_id: "i2", role: "secondary", quantity_text: null },
      ],
    });
  });
});

describe("la bozza dell'AI", () => {
  const DRAFT: RecipeDraft = {
    title: "Bozza", description: "Svelta", instructions: "1. Cuoci.", servings: 2, cost: 3,
    ingredients: [bozza({})],
  };

  it("sostituisce le righe del modello e lascia quelle scelte da te, e la categoria", () => {
    const prima = {
      ...EMPTY_FORM,
      category: "Primi piatti",
      lines: [lineFromDraft(bozza({ raw_name: "vecchia" }), 0), lineFromIngredient(ZAFFERANO)],
    };

    const dopo = applyDraft(prima, DRAFT);

    expect(dopo.lines.map((l) => l.label)).toEqual(["pasta", "Zafferano"]);
    expect(dopo).toMatchObject({
      title: "Bozza", description: "Svelta", servingsText: "2", cost: 3, category: "Primi piatti",
    });
  });

  it("un aggancio incerto non confermato non parte; una riga da creare parte con nome e categoria", () => {
    const values = {
      ...EMPTY_FORM, title: "x", instructions: "y",
      lines: [
        lineFromDraft(bozza({ raw_name: "basilico fresco", ingredient_id: "i2", matched_name: "basilico", confident: false }), 0),
        lineFromDraft(bozza({ raw_name: "Speck", quantity_text: "", ingredient_id: null, matched_name: null, confident: false, proposed_category: "carne" }), 1),
      ],
    };

    expect(recipeBody(values).ingredients).toEqual([
      { name: "speck", category: "carne", role: "primary", quantity_text: null },
    ]);
  });
});

describe("prima di mandare", () => {
  it("dice cosa manca o cosa è fuori scala", () => {
    expect(validationProblem(EMPTY_FORM)).toMatch(/servono un titolo e un procedimento/i);
    expect(validationProblem({ ...EMPTY_FORM, title: "x", instructions: "y", servingsText: "0" })).toMatch(/tra 1 e 50/);
    expect(validationProblem({ ...EMPTY_FORM, title: "x", instructions: "y" })).toBeNull();
  });
});

describe("il nome si scrive una volta", () => {
  it("la nota dell'aggancio compare solo se dice qualcosa di diverso", () => {
    expect(showsMatch(lineFromIngredient(ZAFFERANO))).toBe(false);
    expect(showsMatch(valuesFromRecipe(DETAIL).lines[0])).toBe(false);
    expect(showsMatch(lineFromDraft(bozza({}), 0))).toBe(false);
    expect(showsMatch(lineFromDraft(bozza({ raw_name: "basilico fresco", matched_name: "basilico" }), 0))).toBe(true);
    expect(showsMatch(lineFromDraft(bozza({ confident: false }), 0))).toBe(true);
    expect(showsMatch(lineFromDraft(bozza({ ingredient_id: null, matched_name: null }), 0))).toBe(true);
  });
});
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `npx vitest run src/features/recipe-form/formModel.test.ts`
Expected: FAIL — `Failed to resolve import "./formModel"`.

- [ ] **Step 3: implementazione minima**

In `frontend/src/domain/types.ts`:

- in `RecipeSummary`, dopo `cost`:

```ts
  /** Quando è stata eliminata, in ISO 8601 (R10). Negli elenchi è sempre `null`: il
   * server esclude le eliminate. Il dettaglio la manda, perché un collegamento vecchio
   * porti a «Ripristina» e non a un errore. */
  archived_at: string | null;
```

- in `RecipeDetail`, dopo `dose_lines`:

```ts
  /** Vero finché una pagina dell'import rifà questa ricetta: salvare una modifica la
   * rende tua, e l'import non la riscrive più (R10 §4). Lo decide il server. */
  owned_by_import: boolean;
```

- in `UndoResult`, dopo `remaining_terms`:

```ts
  /** R10: le ricette tue (modificate o eliminate) che contengono il termine, lasciate
   * come sono. */
  adopted_untouched: number;
  /** L'ingrediente del termine resta perché una di quelle ricette lo usa. */
  ingredient_kept_for_adopted: boolean;
```

- dopo `RecipeDetail`, due tipi nuovi:

```ts
/** Una riga come la si scrive: un ingrediente esistente, oppure nome e categoria con
 * cui crearlo salvando (`RecipeIngredientIn` nel backend). `note` si manda solo se c'è. */
export interface RecipeIngredientBody {
  ingredient_id?: string;
  name?: string;
  category?: string | null;
  role: IngredientRole;
  quantity_text: string | null;
  note?: string;
}

/** Quel che si scrive di una ricetta, alla creazione e alla modifica (`RecipeFields`
 * nel backend). La provenienza la aggiunge solo la creazione. */
export interface RecipeBody {
  title: string;
  description: string | null;
  category: string | null;
  instructions: string;
  servings: number | null;
  cost: number | null;
  ingredients: RecipeIngredientBody[];
}
```

In `frontend/src/features/recipes/api.ts`, l'import dei tipi diventa
`import type { CookResult, RecipeBody, RecipeDetail, RecipeDraft, RecipeSource, RecipeSummary } from "../../domain/types";`,
`createRecipe` si tipizza e arrivano le due chiamate nuove:

```ts
export function createRecipe(body: RecipeBody & { source: RecipeSource; source_ref: string | null }) {
  return apiFetch<RecipeDetail>("/recipes", { method: "POST", body: JSON.stringify(body) });
}

/** La ricetta intera, righe comprese (R10). La provenienza non si manda: non si cambia. */
export function updateRecipe(id: string, body: RecipeBody) {
  return apiFetch<RecipeDetail>(`/recipes/${id}`, { method: "PUT", body: JSON.stringify(body) });
}

/** Elimina (`true`) o ripristina (`false`): non c'è una `DELETE`, come in dispensa. */
export function setRecipeArchived(id: string, archived: boolean) {
  return apiFetch<RecipeDetail>(`/recipes/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ archived }),
  });
}
```

Crea `frontend/src/features/recipe-form/formModel.ts`:

```ts
import type {
  DraftIngredient,
  Ingredient,
  IngredientRole,
  RecipeBody,
  RecipeDetail,
  RecipeDraft,
  RecipeIngredientBody,
  RecipeIngredientLine,
} from "../../domain/types";

// I limiti che `RecipeFields` applica nel backend. Stanno qui per far correggere un
// campo *prima* della chiamata, non per decidere qualcosa: l'autorità resta il
// backend, e un 422 che arriva comunque viene detto per quello che è.
export const TITLE_MAX = 200;
export const QUANTITY_MAX = 100;
const SERVINGS_MIN = 1;
const SERVINGS_MAX = 50;

/** Una riga di ingrediente del modulo. Le righe della bozza, quelle scelte a mano e
 * quelle di una ricetta già salvata convivono nella stessa lista: cambia solo chi ha
 * proposto l'aggancio, e quello che il backend ha detto di quell'aggancio. */
export interface FormLine {
  key: string;
  label: string;
  ingredientId: string | null;
  matchedName: string | null;
  // vero solo per una riga della bozza che il backend ha marcato `confident: false`.
  // Non lo ricalcoliamo: lo riportiamo.
  uncertain: boolean;
  /** Vero per le righe che non vengono dal modello: scelte a mano, o già nella ricetta
   * salvata. Una bozza nuova le lascia dove sono. */
  manual: boolean;
  role: IngredientRole;
  quantityText: string;
  /** Falso solo per un aggancio incerto non ancora confermato. Le altre righe non si
   * escludono: si tolgono con la ✕ (R10 §6.2). */
  included: boolean;
  // `null` quando la riga è agganciata o quando il modello non ha detto niente di
  // utilizzabile. Valorizzato è la ragione per cui una riga senza aggancio può
  // comunque salvarsi: il modello ha detto cos'è e in che reparto.
  proposedCategory: string | null;
  /** La nota della riga salvata, portata com'è: il modulo non la mostra e non la
   * cambia, ma una modifica non deve perderla. */
  note: string | null;
}

export interface RecipeFormValues {
  title: string;
  description: string;
  category: string | null;
  // stringa, non numero: un campo vuoto vuole dire "non lo so", e non deve diventare
  // uno zero o un 4 inventato da noi
  servingsText: string;
  // `null` è «non indicato»: una ricetta scritta a mano parte senza costo
  cost: number | null;
  instructions: string;
  lines: FormLine[];
}

export const EMPTY_FORM: RecipeFormValues = {
  title: "",
  description: "",
  category: null,
  servingsText: "",
  cost: null,
  instructions: "",
  lines: [],
};

export function lineFromDraft(line: DraftIngredient, index: number): FormLine {
  const attached = line.ingredient_id !== null;
  const uncertain = attached && !line.confident;
  return {
    // l'indice, non il solo nome: niente vieta al modello di proporre due volte lo
    // stesso `raw_name`, e due righe con la stessa chiave si muoverebbero insieme —
    // oltre a far scartare una riga a React senza dire niente
    key: `draft:${index}:${line.raw_name}`,
    label: line.raw_name,
    ingredientId: line.ingredient_id,
    matchedName: line.matched_name,
    uncertain,
    manual: false,
    role: line.role,
    quantityText: line.quantity_text ?? "",
    // Un aggancio incerto parte ESCLUSO. Partire incluso lo farebbe entrare nel
    // ricettario senza che nessuno l'abbia guardato, ed è esattamente l'accettazione
    // in silenzio che la seconda decisione di progetto vieta: un ingrediente sbagliato
    // avvelena la disponibilità di ogni ricetta che lo usa.
    included: !uncertain,
    proposedCategory: attached ? null : line.proposed_category ?? null,
    note: null,
  };
}

export function lineFromIngredient(ingredient: Ingredient): FormLine {
  return {
    key: `manual:${ingredient.id}`,
    label: ingredient.display_name,
    ingredientId: ingredient.id,
    matchedName: ingredient.name,
    uncertain: false,
    manual: true,
    // "principale" è il default prudente: un principale esige disponibilità piena,
    // quindi al massimo fa sembrare la ricetta meno cucinabile di quanto sia — mai il
    // contrario. Il ruolo resta cambiabile sulla riga.
    role: "primary",
    quantityText: "",
    included: true,
    proposedCategory: null,
    note: null,
  };
}

export function lineFromRecipe(line: RecipeIngredientLine): FormLine {
  return {
    key: `recipe:${line.ingredient_id}`,
    label: line.ingredient_name,
    ingredientId: line.ingredient_id,
    matchedName: line.ingredient_name,
    uncertain: false,
    manual: true,
    role: line.role,
    // la dose scritta, mai quella riscalata: il modulo modifica la ricetta a 1×
    quantityText: line.quantity_text ?? "",
    included: true,
    proposedCategory: null,
    note: line.note,
  };
}

export function valuesFromRecipe(recipe: RecipeDetail): RecipeFormValues {
  return {
    title: recipe.title,
    description: recipe.description ?? "",
    category: recipe.category,
    servingsText: recipe.servings === null ? "" : String(recipe.servings),
    cost: recipe.cost,
    instructions: recipe.instructions,
    lines: recipe.ingredients.map(lineFromRecipe),
  };
}

/** Una bozza nuova sostituisce le proposte del modello, non il lavoro di chi scrive:
 * le righe scelte a mano restano, e la categoria anche (la bozza non ne propone). */
export function applyDraft(values: RecipeFormValues, draft: RecipeDraft): RecipeFormValues {
  return {
    ...values,
    title: draft.title,
    description: draft.description ?? "",
    instructions: draft.instructions,
    servingsText: String(draft.servings ?? ""),
    cost: draft.cost,
    lines: [...draft.ingredients.map(lineFromDraft), ...values.lines.filter((line) => line.manual)],
  };
}

/** Le righe che partono salvando: agganciate, o con nome e categoria per crearle. */
export function savableLines(lines: FormLine[]): FormLine[] {
  return lines.filter(
    (line) => line.included && (line.ingredientId !== null || line.proposedCategory !== null)
  );
}

export function matchNote(line: FormLine): string {
  if (line.ingredientId === null) {
    if (line.proposedCategory !== null) return `${line.label}: da creare salvando`;
    return `${line.label} non in anagrafica, sarà escluso`;
  }
  if (line.uncertain) return `${line.matchedName}, da confermare`;
  return line.matchedName ?? line.label;
}

/** Se la nota dell'aggancio dice qualcosa che l'etichetta non dice già. Una riga
 * scelta a mano o salvata porta lo stesso nome due volte (giro di T3): lì si tace. */
export function showsMatch(line: FormLine): boolean {
  if (line.ingredientId === null || line.uncertain) return true;
  return (line.matchedName ?? "").toLowerCase() !== line.label.toLowerCase();
}

/** Quello che il backend rifiuterebbe con un 422, detto qui in modo che si possa
 * correggere invece di riprovare a mandare gli stessi dati. `null` quando non c'è
 * niente da sistemare. */
export function validationProblem(values: RecipeFormValues): string | null {
  if (values.title.trim() === "" || values.instructions.trim() === "")
    return "Servono un titolo e un procedimento per salvare.";
  if (values.title.trim().length > TITLE_MAX)
    return `Il titolo è troppo lungo: massimo ${TITLE_MAX} caratteri.`;

  const servings = values.servingsText.trim();
  if (servings !== "" && !/^\d+$/.test(servings))
    return `Le porzioni vanno scritte come numero intero da ${SERVINGS_MIN} a ${SERVINGS_MAX}, oppure lasciate vuote.`;
  if (servings !== "" && (Number(servings) < SERVINGS_MIN || Number(servings) > SERVINGS_MAX))
    return `Le porzioni devono stare tra ${SERVINGS_MIN} e ${SERVINGS_MAX}. Lascia il campo vuoto se non lo sai: vuoto è meglio di inventato.`;

  const tooLong = savableLines(values.lines).find(
    (line) => line.quantityText.trim().length > QUANTITY_MAX
  );
  if (tooLong)
    return `La quantità di «${tooLong.label}» è troppo lunga: massimo ${QUANTITY_MAX} caratteri.`;

  return null;
}

function lineBody(line: FormLine): RecipeIngredientBody {
  // `quantity_text` è testo da mostrare, mai un numero da calcolare: passa verbatim, e
  // vuoto resta vuoto invece di diventare ""
  const quantity_text = line.quantityText.trim() === "" ? null : line.quantityText;
  // la nota solo se c'è: una chiave `note: null` in più cambierebbe il corpo che
  // «Scrivi una ricetta» ha sempre mandato
  const note = line.note ? { note: line.note } : {};
  return line.ingredientId !== null
    ? { ingredient_id: line.ingredientId, role: line.role, quantity_text, ...note }
    : {
        name: line.label.trim().toLowerCase(),
        category: line.proposedCategory,
        role: line.role,
        quantity_text,
        ...note,
      };
}

export function recipeBody(values: RecipeFormValues): RecipeBody {
  const servings = values.servingsText.trim();
  const description = values.description.trim();
  return {
    title: values.title.trim(),
    description: description === "" ? null : description,
    category: values.category,
    instructions: values.instructions,
    servings: servings === "" ? null : Number(servings),
    cost: values.cost,
    ingredients: savableLines(values.lines).map(lineBody),
  };
}
```

Poi i letterali tipizzati che `tsc -b` ora rifiuta, un campo ciascuno e nient'altro:
- `frontend/src/features/cooking/CookSheet.test.tsx`, `RECIPE`: `archived_at: null,` e
  `owned_by_import: false,`
- `frontend/src/features/cooking/RecipeDetailScreen.test.tsx`, `DETAIL`: gli stessi due
- `frontend/src/features/recipes/RecipeCard.test.tsx`, `ricetta()`: `archived_at: null,`

Se `npm run typecheck` ne trova altri, stessa correzione: un campo, niente altro.

- [ ] **Step 4: eseguilo e verifica che passi, poi il type check**

Run: `npx vitest run src/features/recipe-form/formModel.test.ts`
Expected: PASS.

Run: `npm run typecheck`
Expected: esce 0 dopo una correzione che `tsc` chiede di sicuro: `AiDraftScreen.tsx` passa
ancora a `createRecipe({...})` un oggetto senza `category`, che `RecipeBody` vuole.
Aggiungi lì `category: null,` accanto a `description`: il Task 9 riscrive comunque
quella chiamata.

- [ ] **Step 5: commit**

```bash
git add src/domain/types.ts src/features/recipes/api.ts src/features/recipe-form src/features/cooking/CookSheet.test.tsx src/features/cooking/RecipeDetailScreen.test.tsx src/features/recipes/RecipeCard.test.tsx src/features/ai-draft/AiDraftScreen.tsx
git commit -m "$(cat <<'EOF'
ricette: i tipi della modifica e il modello del modulo, in funzioni pure

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: `RecipeForm`, e «Scrivi una ricetta» che lo usa

Spec §6.2 e §9; deviazioni 10, 11 e 12.

**File:**
- Create: `frontend/src/features/recipe-form/RecipeForm.tsx`
- Create: `frontend/src/features/recipe-form/CategoryField.tsx`
- Modify: `frontend/src/features/ai-draft/AiDraftScreen.tsx` (riscritta)
- Modify: `frontend/src/features/ai-draft/AiDraftScreen.test.tsx` — **solo** i quattro test
  elencati allo Step 3
- Test: `frontend/src/features/recipe-form/RecipeForm.test.tsx`

**Interfacce:**
- Consuma: tutto `formModel.ts` (Task 8), `createRecipe`, `fetchCategories`, `RecipeBody`.
- Produce:
  - `RecipeForm({ values, onChange, save, onSaved, submitLabel })` con
    `values: RecipeFormValues`, `onChange: Dispatch<SetStateAction<RecipeFormValues>>`,
    `save: (body: RecipeBody) => Promise<RecipeDetail>`,
    `onSaved: (recipe: RecipeDetail) => void`, `submitLabel: string`
  - `CategoryField({ value, onChange })`, `value: string | null`
  - nomi accessibili che i task dopo usano: «Titolo», «Descrizione», «Porzioni»,
    «Procedimento», «Quantità per X», il gruppo «Ruolo di X» con «principale» e
    «secondario», la ✕ «Togli X», la casella «Includi X» (solo sugli agganci incerti),
    «Cambia la categoria», l'elenco «Categorie» con le opzioni e «Nessuna».

- [ ] **Step 1: scrivi il test che fallisce**

Crea `frontend/src/features/recipe-form/RecipeForm.test.tsx`:

```tsx
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { RecipeForm } from "./RecipeForm";
import { lineFromDraft, valuesFromRecipe, type RecipeFormValues } from "./formModel";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import type { RecipeBody, RecipeDetail } from "../../domain/types";

const DETAIL: RecipeDetail = {
  id: "r1", title: "Pasta al pomodoro", description: "Di sempre", source: "manual",
  missing: 0, cookable: true, missing_names: [], image_url: null, prep_minutes: null,
  cook_minutes: null, category: "Primi piatti", cost: null, archived_at: null,
  instructions: "Cuoci.", servings: 2, source_ref: null, scaled_to: null,
  unscalable_lines: 0, dose_lines: 1, owned_by_import: false,
  ingredients: [
    { ingredient_id: "i1", ingredient_name: "pasta", role: "primary", quantity_text: "320 g",
      quantity_display: "320 g", quantity_scaled: false, note: "al dente",
      availability: "available", satisfied: true },
    { ingredient_id: "i2", ingredient_name: "basilico", role: "secondary", quantity_text: null,
      quantity_display: null, quantity_scaled: false, note: null,
      availability: "missing", satisfied: false },
  ],
};

/** Il modulo è controllato: chi lo usa tiene i valori, come fanno le due schermate. */
function Genitore({
  initial,
  save,
}: {
  initial: RecipeFormValues;
  save: (body: RecipeBody) => Promise<RecipeDetail>;
}) {
  const [values, setValues] = useState(initial);
  return (
    <RecipeForm
      values={values}
      onChange={setValues}
      save={save}
      onSaved={() => {}}
      submitLabel="Salva le modifiche"
    />
  );
}

function renderForm(initial: RecipeFormValues) {
  // quel che torna non conta qui: `onSaved` è vuoto, e il corpo mandato lo legge il test
  const save = vi.fn((_body: RecipeBody) => Promise.resolve(DETAIL));
  const client = new QueryClient({
    defaultOptions: { queries: { retry: defaultQueryRetryPredicate } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <Genitore initial={initial} save={save} />
      </MemoryRouter>
    </QueryClientProvider>
  );
  return save;
}

function stubCategories([body, status]: [unknown, number]) {
  const spy = vi.fn((url: unknown) =>
    Promise.resolve(
      String(url).includes("/recipes/categories")
        ? new Response(JSON.stringify(body), { status })
        : new Response("[]", { status: 200 })
    )
  );
  vi.stubGlobal("fetch", spy);
  return spy;
}

function categorieChieste(spy: ReturnType<typeof stubCategories>) {
  return spy.mock.calls.filter(([url]) => String(url).includes("/recipes/categories")).length;
}

async function salva() {
  await userEvent.click(screen.getByRole("button", { name: "Salva le modifiche" }));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RecipeForm riempito da una ricetta", () => {
  it("parte dai suoi valori, descrizione e categoria comprese", () => {
    stubCategories([[], 200]);
    renderForm(valuesFromRecipe(DETAIL));

    expect(screen.getByLabelText("Titolo")).toHaveValue("Pasta al pomodoro");
    expect(screen.getByLabelText("Descrizione")).toHaveValue("Di sempre");
    expect(screen.getByText("Primi piatti")).toBeInTheDocument();
    expect(screen.getByLabelText("Quantità per pasta")).toHaveValue("320 g");
  });

  it("una riga si toglie con la ✕, il ruolo si cambia, e la nota resta", async () => {
    stubCategories([[], 200]);
    const save = renderForm(valuesFromRecipe(DETAIL));

    await userEvent.click(screen.getByRole("button", { name: "Togli basilico" }));
    await userEvent.click(
      within(screen.getByRole("group", { name: "Ruolo di pasta" })).getByRole("button", {
        name: "secondario",
      })
    );
    await salva();

    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({
        ingredients: [{ ingredient_id: "i1", role: "secondary", quantity_text: "320 g", note: "al dente" }],
      })
    );
  });

  it("il nome di una riga si legge una volta sola", () => {
    stubCategories([[], 200]);
    renderForm(valuesFromRecipe(DETAIL));
    expect(screen.getAllByText("pasta")).toHaveLength(1);
  });

  it("il ruolo si cambia anche su una riga proposta dall'AI", async () => {
    stubCategories([[], 200]);
    const save = renderForm({
      ...valuesFromRecipe(DETAIL),
      lines: [
        lineFromDraft(
          { raw_name: "pasta", role: "primary", quantity_text: "180 g", ingredient_id: "i1",
            matched_name: "pasta", confident: true, proposed_category: null },
          0
        ),
      ],
    });

    await userEvent.click(
      within(screen.getByRole("group", { name: "Ruolo di pasta" })).getByRole("button", {
        name: "secondario",
      })
    );
    await salva();

    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({
        ingredients: [{ ingredient_id: "i1", role: "secondary", quantity_text: "180 g" }],
      })
    );
  });
});

describe("la categoria", () => {
  it("si legge solo aprendo la scelta, e si sceglie o si toglie", async () => {
    const spy = stubCategories([["Dolci", "Primi piatti"], 200]);
    const save = renderForm(valuesFromRecipe(DETAIL));
    expect(categorieChieste(spy)).toBe(0);

    await userEvent.click(screen.getByRole("button", { name: "Cambia la categoria" }));
    await userEvent.click(await screen.findByRole("option", { name: "Dolci" }));
    expect(screen.getByText("Dolci")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Cambia la categoria" }));
    await userEvent.click(await screen.findByRole("option", { name: "Nessuna" }));
    await salva();

    expect(save).toHaveBeenCalledWith(expect.objectContaining({ category: null }));
  });

  it(
    "se le categorie non arrivano lo dice, e la ricetta si salva lo stesso",
    async () => {
      // un 500 si ritenta due volte col predicato vero: da qui il tempo lungo
      stubCategories([{ detail: "giù" }, 500]);
      const save = renderForm(valuesFromRecipe(DETAIL));

      await userEvent.click(screen.getByRole("button", { name: "Cambia la categoria" }));
      expect(
        await screen.findByText(/la ricetta si salva anche senza/i, undefined, { timeout: 8000 })
      ).toBeInTheDocument();
      await salva();

      expect(save).toHaveBeenCalledWith(expect.objectContaining({ category: "Primi piatti" }));
    },
    10000
  );
});
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `npx vitest run src/features/recipe-form/RecipeForm.test.tsx`
Expected: FAIL — `Failed to resolve import "./RecipeForm"`.

- [ ] **Step 3: implementazione minima**

Crea `frontend/src/features/recipe-form/CategoryField.tsx`:

```tsx
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchCategories } from "../recipes/api";
import { Alert } from "../../components/ui/Alert";
import { buttonClasses } from "../../components/ui/buttonClasses";

/** La categoria della ricetta: una di quelle che il ricettario ha già, o nessuna.
 *
 * Senza testo libero, per non creare «Primi» e «primi» (R10 §6.2): il backend rifiuta
 * comunque un nome che non conosce. L'elenco si legge quando si apre la scelta, non al
 * montaggio: il modulo è sempre in pagina in «Scrivi una ricetta», e una chiamata in
 * più all'apertura cambierebbe l'ordine delle risposte su cui quella schermata e i suoi
 * test contano. La chiave è quella del filtro del ricettario, quindi quasi sempre la
 * risposta è già in cache.
 */
export function CategoryField({
  value,
  onChange,
}: {
  value: string | null;
  onChange: (category: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const { data: categories = [], isLoading, isError } = useQuery({
    queryKey: ["recipe-categories"],
    queryFn: fetchCategories,
    enabled: open,
  });

  function choose(category: string | null) {
    onChange(category);
    setOpen(false);
  }

  return (
    <div className="text-sm">
      Categoria
      <div className="flex min-h-11 items-center justify-between gap-2">
        <span className={value === null ? "text-ink-faint" : ""}>{value ?? "nessuna"}</span>
        <button
          type="button"
          aria-label={open ? "Chiudi la scelta della categoria" : "Cambia la categoria"}
          aria-expanded={open}
          onClick={() => setOpen((current) => !current)}
          className={buttonClasses("ghost")}
        >
          {open ? "Chiudi" : "Cambia"}
        </button>
      </div>
      {open && isLoading && <p className="text-ink-soft">Carico le categorie…</p>}
      {/* mai un vicolo cieco: senza elenco la ricetta si salva con la categoria che ha */}
      {open && isError && (
        <Alert tone="note">
          Non riesco a leggere le categorie: la ricetta si salva anche senza, e la scegli dopo.
        </Alert>
      )}
      {open && !isLoading && !isError && (
        <ul
          role="listbox"
          aria-label="Categorie"
          className="divide-y divide-line overflow-hidden rounded-card bg-card"
        >
          {[null, ...categories].map((category) => (
            <li key={category ?? ""}>
              <button
                type="button"
                role="option"
                aria-selected={category === value}
                onClick={() => choose(category)}
                className="flex min-h-11 w-full items-center px-3 text-left"
              >
                {category ?? "Nessuna"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

Crea `frontend/src/features/recipe-form/RecipeForm.tsx`:

```tsx
import type { Dispatch, SetStateAction } from "react";
import { useMutation } from "@tanstack/react-query";
import { ApiError } from "../../api/client";
import { IngredientPicker } from "../../components/IngredientPicker";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { CostPicker } from "../../components/ui/CostPicker";
import { FOOD_CATEGORIES } from "../../domain/categories";
import type { Ingredient, IngredientRole, RecipeBody, RecipeDetail } from "../../domain/types";
import { CategoryField } from "./CategoryField";
import {
  QUANTITY_MAX,
  TITLE_MAX,
  lineFromIngredient,
  matchNote,
  recipeBody,
  savableLines,
  showsMatch,
  validationProblem,
  type FormLine,
  type RecipeFormValues,
} from "./formModel";

const ROLE_LABELS: Record<IngredientRole, string> = {
  primary: "principale",
  secondary: "secondario",
};

/** Un salvataggio rifiutato per validazione non è un guasto passeggero: mandare di
 * nuovo gli stessi byte darà lo stesso esito, e dire "riprova" sarebbe un vicolo cieco
 * travestito da invito. Il messaggio lo distingue per stato.
 *
 * Il `detail` di un 422 di FastAPI può essere una lista di oggetti, non una frase:
 * non si mostra grezzo. Il 409 di una ricetta eliminata nel frattempo porta invece
 * già la frase giusta, con l'uscita dentro (R10). */
function saveProblem(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 422)
      return "Il backend ha rifiutato la ricetta: qualcosa nei campi qui sopra non va. Correggilo — rimandarla identica darà lo stesso esito.";
    if (error.status === 409 && error.message.includes("eliminata")) return error.message;
    if (error.status === 409)
      return "Due righe puntano allo stesso ingrediente. Togline una con la ✕, poi salva.";
    if (error.status === 404)
      return "Un ingrediente agganciato non esiste più. Togli quella riga con la ✕, poi salva.";
  }
  return "Non sono riuscito a salvare la ricetta. Niente è andato perso: riprova.";
}

function LineRow({
  line,
  onUpdate,
  onRemove,
}: {
  line: FormLine;
  onUpdate: (change: Partial<FormLine>) => void;
  onRemove: () => void;
}) {
  // la stessa condizione di `savableLines`: una riga entra nel salvataggio se è
  // agganciata o se porta nome e categoria con cui crearla, ed è lì che ha dose e ruolo
  const savableShape = line.ingredientId !== null || line.proposedCategory !== null;
  return (
    <li className="flex flex-col gap-2 py-2 text-sm">
      <div className="flex items-center justify-between gap-2">
        <label className="flex min-h-11 min-w-0 flex-1 items-center gap-3">
          {/* La casella c'è solo dove l'AI ha un'ipotesi da confermare: lì vuol dire
              «è questo», non «tienila». Le righe si tolgono con la ✕ (R10 §6.2). */}
          {line.uncertain && (
            <input
              type="checkbox"
              aria-label={`Includi ${line.label}`}
              checked={line.included}
              onChange={() => onUpdate({ included: !line.included })}
              className="size-5 shrink-0"
            />
          )}
          <span className="min-w-0 break-words">{line.label}</span>
        </label>
        {showsMatch(line) && (
          <span className="max-w-[45%] text-right text-xs">
            {line.ingredientId === null || line.uncertain ? (
              <em className="text-low">{matchNote(line)}</em>
            ) : (
              <span className="text-brand">{matchNote(line)}</span>
            )}
          </span>
        )}
        {/* la stessa X delle pastiglie del filtro, e per la stessa ragione il nome
            accessibile nomina la riga: su dodici righe «Togli» da solo non dice quale */}
        <button
          type="button"
          aria-label={`Togli ${line.label}`}
          onClick={onRemove}
          className="flex size-11 shrink-0 items-center justify-center rounded-full text-ink-soft"
        >
          <svg
            viewBox="0 0 24 24"
            aria-hidden="true"
            className="size-4"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          >
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </div>

      {/* perché la casella parte vuota: senza questa frase "da confermare" sembra un
          avviso, non una cosa da fare */}
      {line.uncertain && (
        <p className="text-xs text-low">
          Parte escluso, perché l'aggancio è solo un'ipotesi: spunta la casella se è quello
          giusto.
        </p>
      )}

      {line.ingredientId === null && line.proposedCategory !== null && (
        <div className="flex flex-col gap-1">
          <p className="text-xs text-ink-soft">Non è in anagrafica: lo creo io salvando.</p>
          <label className="text-xs font-medium text-ink-soft">
            Categoria
            <select
              aria-label={`Categoria per «${line.label}»`}
              value={line.proposedCategory ?? "altro"}
              onChange={(e) => onUpdate({ proposedCategory: e.target.value })}
              className="mt-1"
            >
              {FOOD_CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      {savableShape && (
        <div className="flex items-end gap-2">
          <label className="flex-1 text-xs text-ink-soft">
            Quantità
            <input
              aria-label={`Quantità per ${line.label}`}
              value={line.quantityText}
              onChange={(e) => onUpdate({ quantityText: e.target.value })}
              maxLength={QUANTITY_MAX}
              placeholder="q.b."
              className="mt-1.5 text-ink"
            />
          </label>
          {/* su ogni riga, anche su quelle proposte dall'AI: è il ruolo che decide se
              la ricetta è cucinabile (giro di T3) */}
          <div className="flex gap-1" role="group" aria-label={`Ruolo di ${line.label}`}>
            {(["primary", "secondary"] as IngredientRole[]).map((role) => (
              <button
                key={role}
                type="button"
                onClick={() => onUpdate({ role })}
                aria-pressed={line.role === role}
                className={`min-h-11 rounded-full px-3 py-2 text-xs font-medium ${
                  line.role === role ? "bg-brand text-white" : "bg-page text-ink-soft"
                }`}
              >
                {ROLE_LABELS[role]}
              </button>
            ))}
          </div>
        </div>
      )}
    </li>
  );
}

/** Il modulo di una ricetta, per scriverla e per modificarla (R10 §6.2).
 *
 * Controllato: i valori li tiene chi lo usa. «Scrivi una ricetta» ci versa dentro la
 * bozza dell'AI senza perdere le righe scelte a mano; la modifica lo riempie una volta
 * dalla ricetta salvata. Il salvataggio è la funzione che riceve — `POST` o `PUT` — e
 * il modulo ne mostra l'esito accanto al pulsante.
 */
export function RecipeForm({
  values,
  onChange,
  save,
  onSaved,
  submitLabel,
}: {
  values: RecipeFormValues;
  onChange: Dispatch<SetStateAction<RecipeFormValues>>;
  save: (body: RecipeBody) => Promise<RecipeDetail>;
  onSaved: (recipe: RecipeDetail) => void;
  submitLabel: string;
}) {
  const savable = savableLines(values.lines);
  const problem = validationProblem(values);
  const submit = useMutation({
    mutationFn: () => save(recipeBody(values)),
    onSuccess: onSaved,
  });

  function set(change: Partial<RecipeFormValues>) {
    onChange((prev) => ({ ...prev, ...change }));
  }

  function updateLine(key: string, change: Partial<FormLine>) {
    onChange((prev) => ({
      ...prev,
      lines: prev.lines.map((line) => (line.key === key ? { ...line, ...change } : line)),
    }));
  }

  function removeLine(key: string) {
    onChange((prev) => ({ ...prev, lines: prev.lines.filter((line) => line.key !== key) }));
  }

  function attach(ingredient: Ingredient) {
    onChange((prev) => {
      // due righe sullo stesso ingrediente sono un 409 del backend, e non vorrebbero
      // dire niente: se c'è già, la si include e basta — che è anche il modo di
      // confermare un aggancio incerto scegliendolo di persona
      if (prev.lines.some((line) => line.ingredientId === ingredient.id))
        return {
          ...prev,
          lines: prev.lines.map((line) =>
            line.ingredientId === ingredient.id ? { ...line, included: true } : line
          ),
        };
      return { ...prev, lines: [...prev.lines, lineFromIngredient(ingredient)] };
    });
  }

  return (
    <div className="flex flex-col gap-3">
      <label className="text-sm">
        Titolo
        <input
          value={values.title}
          onChange={(e) => set({ title: e.target.value })}
          maxLength={TITLE_MAX}
          className="mt-1.5"
        />
      </label>

      <label className="text-sm">
        Descrizione
        <textarea
          value={values.description}
          onChange={(e) => set({ description: e.target.value })}
          rows={2}
          placeholder="Facoltativa: una riga che la presenta"
          className="mt-1.5"
        />
      </label>

      <CategoryField value={values.category} onChange={(category) => set({ category })} />

      <label className="text-sm">
        Porzioni
        <input
          aria-label="Porzioni"
          value={values.servingsText}
          onChange={(e) => set({ servingsText: e.target.value })}
          inputMode="numeric"
          placeholder="Lascia vuoto se non lo sai"
          className="mt-1.5"
        />
      </label>

      <div className="text-sm">
        Costo
        <div className="flex items-center gap-2">
          <CostPicker value={values.cost} onChange={(cost) => set({ cost })} />
          {values.cost === null && <span className="text-ink-faint">non indicato</span>}
        </div>
      </div>

      <div>
        <h2 className="text-xs uppercase tracking-wide text-ink-faint">Ingredienti</h2>
        <ul className="divide-y divide-line">
          {values.lines.map((line) => (
            <LineRow
              key={line.key}
              line={line}
              onUpdate={(change) => updateLine(line.key, change)}
              onRemove={() => removeLine(line.key)}
            />
          ))}
        </ul>

        <IngredientPicker
          label="Aggiungi un ingrediente"
          failureNote="Puoi salvare la ricetta comunque, anche senza ingredienti agganciati."
          kind="food"
          onPick={attach}
        />
      </div>

      <label className="text-sm">
        Procedimento
        <textarea
          value={values.instructions}
          onChange={(e) => set({ instructions: e.target.value })}
          rows={8}
          className="mt-1.5"
        />
      </label>

      {/* una ricetta senza agganci si salva — è comunque la ricetta che l'utente
          voleva — ma va detto cosa ci rimette, prima del salvataggio e non dopo */}
      {savable.length === 0 && (
        <p role="status" className="text-sm text-low">
          Nessun ingrediente agganciato: la ricetta si salva comunque, ma il ricettario non
          potrà dire se puoi cucinarla.
        </p>
      )}

      {/* il motivo sta accanto al pulsante che sta disabilitando: un pulsante spento e
          muto è un vicolo cieco quanto un errore senza spiegazione */}
      {problem && <p className="text-sm text-low">{problem}</p>}

      <button
        type="button"
        onClick={() => submit.mutate()}
        disabled={submit.isPending || problem !== null}
        className={buttonClasses("primary", "block")}
      >
        {submit.isPending ? "Salvo…" : submitLabel}
      </button>

      {/* l'errore sta accanto al pulsante che ha fallito: tutti i campi restano qui,
          pronti per un altro tentativo */}
      {submit.isError && (
        <p role="alert" className="text-sm text-danger">
          {saveProblem(submit.error)}
        </p>
      )}
    </div>
  );
}
```

Riscrivi `frontend/src/features/ai-draft/AiDraftScreen.tsx`:

```tsx
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { createRecipe, draftRecipe } from "../recipes/api";
import { BackLink } from "../../components/BackLink";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { RecipeForm } from "../recipe-form/RecipeForm";
import { EMPTY_FORM, applyDraft, type RecipeFormValues } from "../recipe-form/formModel";
import type { RecipeDraft } from "../../domain/types";

const SOURCE_REF_MAX = 500;

/** `source_ref` sta in 500 caratteri, il prompt può arrivarne a 1000: la
 * provenienza si accorcia, il testo scritto no — quello resta nel suo campo.
 * Senza questo, un prompt lungo faceva rifiutare il salvataggio con un 422. */
function sourceRef(prompt: string): string {
  const ref = `prompt: ${prompt}`;
  return ref.length <= SOURCE_REF_MAX ? ref : `${ref.slice(0, SOURCE_REF_MAX - 1)}…`;
}

// Lo schermo che tiene insieme la dipendenza meno affidabile dell'app e la via
// d'uscita da tutti i suoi guasti. L'AI può non rispondere, rispondere con qualcosa di
// inutilizzabile, o proporre un ingrediente che in anagrafica non esiste: nessuno di
// questi casi può diventare una pagina d'errore.
//
// Per questo il modulo della ricetta è SEMPRE in pagina, non dietro un `draft` né
// dietro un `propose.isError`. Tre ragioni, in ordine di peso:
//  1. `createRecipe` ha qui l'unico punto di chiamata del frontend: se il modulo vive
//     dentro una condizione, scrivere una ricetta a mano è una cosa che l'app non sa
//     fare finché quella condizione non è vera.
//  2. Una via d'uscita che si apre solo dopo un guasto si rompe insieme al guasto:
//     basta sbagliare la condizione e il vicolo cieco torna. Un modulo senza condizioni
//     non ha nessun flag da sbagliare.
//  3. Chiedere all'AI diventa un aiuto sul modulo — precompila i campi — invece di
//     essere il cancello da cui passare per averlo.
//
// Il modulo è `RecipeForm` (R10), lo stesso della modifica: qui sopra resta la
// richiesta all'AI, e la bozza lo riempie con `applyDraft`.
export function AiDraftScreen() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [prompt, setPrompt] = useState("");
  const [draft, setDraft] = useState<RecipeDraft | null>(null);
  const [values, setValues] = useState<RecipeFormValues>(EMPTY_FORM);

  const propose = useMutation({
    mutationFn: () => draftRecipe(prompt),
    onSuccess: (result) => {
      setDraft(result);
      setValues((prev) => applyDraft(prev, result));
    },
  });

  return (
    <div className="flex flex-col gap-4 px-4 pt-2 pb-4">
      <BackLink to="/ricette" label="Ricette" />
      <h1 className="text-2xl font-semibold tracking-tight">Scrivi una ricetta</h1>

      <div className="flex flex-col gap-2">
        <label htmlFor="prompt" className="text-sm text-ink-soft">Cosa vuoi cucinare</label>
        <textarea
          id="prompt"
          aria-label="Cosa vuoi cucinare"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={3}
          placeholder="Qualcosa di veloce con quello che ho"
        />
        <button
          type="button"
          onClick={() => propose.mutate()}
          disabled={prompt.trim().length < 3 || propose.isPending}
          className={buttonClasses("primary", "block")}
        >
          {propose.isPending ? "Propongo…" : "Proponi"}
        </button>
        <p className="text-xs text-ink-soft">
          Chiedere all'AI è facoltativo: precompila il modulo qui sotto, che funziona anche da
          solo.
        </p>

        {/* il testo scritto resta qui sopra qualunque sia l'esito, e il modulo
            qui sotto c'era già prima: il guasto non toglie niente */}
        {propose.isError && (
          <p role="alert" className="text-sm text-low">
            La stesura AI non è disponibile. Il modulo qui sotto resta tuo: scrivi la ricetta a
            mano e salvala.
          </p>
        )}
      </div>

      <div className="border-t border-line pt-4">
        <RecipeForm
          values={values}
          onChange={setValues}
          save={(body) =>
            createRecipe({
              ...body,
              // la provenienza dice il vero: senza bozza questa ricetta l'ha scritta
              // una persona, e spacciarla per "ai" sarebbe una bugia nello storico
              source: draft ? "ai" : "manual",
              source_ref: draft ? sourceRef(prompt) : null,
            })
          }
          onSaved={(recipe) => {
            // la ricetta appena scritta deve apparire nel ricettario al prossimo giro
            void queryClient.invalidateQueries({ queryKey: ["recipes"] });
            navigate(`/ricette/${recipe.id}`);
          }}
          submitLabel="Salva nel ricettario"
        />
      </div>
    </div>
  );
}
```

In `frontend/src/features/ai-draft/AiDraftScreen.test.tsx` cambiano **quattro test, e
solo i selettori che la ✕ cambia** (spec §9). Nessun'altra riga del file si tocca:

1. «due righe di bozza con lo stesso nome restano due righe indipendenti» — dalla riga
   `const boxes = …` alla fine del test:

```tsx
    // R10: una riga si toglie con la ✕, non togliendo la spunta (spec §6.2)
    const crocette = screen.getAllByRole("button", { name: "Togli pomodoro" });
    expect(crocette).toHaveLength(2);

    await userEvent.click(crocette[0]);
    expect(screen.getAllByRole("button", { name: "Togli pomodoro" })).toHaveLength(1);
    expect(screen.getByLabelText("Quantità per pomodoro")).toHaveValue("2 cucchiai");
```

2. «un aggancio incerto parte escluso, e la riga dice perché» — la riga
   `expect(screen.getByLabelText(/includi pasta/i)).toBeChecked();` diventa:

```tsx
    // un aggancio sicuro non ha casella da spuntare: è dentro, e si toglie con la ✕
    expect(screen.queryByLabelText(/includi pasta/i)).toBeNull();
    expect(screen.getByRole("button", { name: "Togli pasta" })).toBeInTheDocument();
```

3. «anche un aggancio sicuro si può togliere, e una ricetta senza agganci lo dichiara» —
   la riga `await userEvent.click(await screen.findByLabelText(/includi pasta/i));`
   diventa:

```tsx
    await userEvent.click(await screen.findByRole("button", { name: "Togli pasta" }));
```

4. «un ingrediente da creare si esclude con la sua casella, e resta fuori dal corpo
   salvato» — il titolo diventa «un ingrediente da creare si toglie con la sua ✕, e resta
   fuori dal corpo salvato», e le quattro righe da `const casella = …` a
   `expect(casella).not.toBeChecked();` diventano:

```tsx
    await userEvent.click(await screen.findByRole("button", { name: "Togli speck" }));
    expect(screen.queryByLabelText("Quantità per speck")).toBeNull();
```

(Il commento sopra il quarto test parla della «casella»: aggiungici in fondo una riga,
`// R10: la casella è diventata la ✕; l'assert resta sul corpo della POST.`)

- [ ] **Step 4: eseguili e verifica che passino**

Run: `npx vitest run src/features/recipe-form src/features/ai-draft`
Expected: PASS — i test di «Scrivi una ricetta» compresi, con i soli quattro selettori
cambiati. Se ne fallisce un altro, è `RecipeForm` a essere sbagliato, non il test.

Run: `npm run lint && npm run typecheck`
Expected: puliti.

- [ ] **Step 5: commit**

```bash
git add src/features/recipe-form src/features/ai-draft
git commit -m "$(cat <<'EOF'
ricette: il modulo diventa RecipeForm, con descrizione, categoria, ruolo e la ✕

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: La lapide nel ricettario

Spec §6.1.

**File:**
- Create: `frontend/src/lib/undo.ts`
- Modify: `frontend/src/features/pantry/PantryScreen.tsx` (righe 14–16: `UNDO_MS` importato)
- Modify: `frontend/src/features/recipes/RecipeBookScreen.tsx`
- Test: `frontend/src/features/recipes/RecipeBookScreen.lapide.test.tsx`

**Interfacce:**
- Consuma: `setRecipeArchived` (Task 8).
- Produce:
  - `UNDO_MS = 6000` da `frontend/src/lib/undo.ts`
  - lo stato di navigazione che il ricettario legge:
    `{ deletedRecipe: { id: string; title: string } }` — il dettaglio lo manda nel Task 11
  - la lapide è un `role="status"` con «<titolo> eliminata» e il bottone «Annulla»

- [ ] **Step 1: scrivi il test che fallisce**

Crea `frontend/src/features/recipes/RecipeBookScreen.lapide.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { RecipeBookScreen } from "./RecipeBookScreen";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";

const CARBONARA = {
  id: "r-carb", title: "Carbonara", description: null, source: "manual", missing: 0,
  cookable: true, missing_names: [], image_url: null, prep_minutes: null, cook_minutes: null,
  category: null, cost: null, archived_at: null,
};
const AGLIO = { ...CARBONARA, id: "r-aglio", title: "Aglio e olio" };
const ELIMINATA = { deletedRecipe: { id: "r-carb", title: "Carbonara" } };

type Rotta = (path: string, init?: RequestInit) => [unknown, number];

/** Le chiamate che lo schermo fa sempre hanno una risposta fissa; la ricerca e la
 * PATCH le decide il test. */
function stubFetch(route: Rotta) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const path = String(url);
    const [body, status]: [unknown, number] = path.includes("/imports/status")
      ? [{ fetched: 0, pending_recipes: 0, imported: 0, skipped: 0, pending_terms: 0 }, 200]
      : path.includes("/recipes/categories")
        ? [[], 200]
        : path.includes("/recipes/search-mode")
          ? [{ semantic: true }, 200]
          : route(path, init);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

/** Quel che la cronologia ricorda di questa voce: la lapide non deve restarci. */
function StatoDellaVoce() {
  const location = useLocation();
  return <p data-testid="stato">{JSON.stringify(location.state)}</p>;
}

function renderBook(state: unknown = ELIMINATA) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: defaultQueryRetryPredicate } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[{ pathname: "/ricette", state }]}>
        <Routes>
          <Route
            path="/ricette"
            element={
              <>
                <RecipeBookScreen />
                <StatoDellaVoce />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function patchMandate(spy: ReturnType<typeof stubFetch>) {
  return spy.mock.calls
    .filter(([, init]) => init?.method === "PATCH")
    .map(([url, init]) => [String(url), JSON.parse(String(init!.body))]);
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("la lapide del ricettario (R10 §6.1)", () => {
  it("arriva con la navigazione e dice quale ricetta, anche se la ricerca la manda ancora", async () => {
    stubFetch(() => [[CARBONARA, AGLIO], 200]);
    renderBook();

    expect(await screen.findByRole("status")).toHaveTextContent("Carbonara eliminata");
    expect(await screen.findByText("Aglio e olio")).toBeInTheDocument();
    // una risposta vecchia della ricerca non la fa ricomparire sotto la sua lapide
    expect(screen.queryByRole("link", { name: /Carbonara/ })).toBeNull();
  });

  it("la cronologia la dimentica subito: un «indietro» non la resusciterebbe", async () => {
    stubFetch(() => [[AGLIO], 200]);
    renderBook();

    await screen.findByRole("status");
    await waitFor(() => expect(screen.getByTestId("stato")).toHaveTextContent("null"));
    expect(screen.getByRole("status")).toHaveTextContent("Carbonara eliminata");
  });

  it("«Annulla» la riporta nel ricettario, e la lapide se ne va", async () => {
    let eliminata = true;
    const spy = stubFetch((_path, init) => {
      if (init?.method === "PATCH") {
        eliminata = false;
        return [CARBONARA, 200];
      }
      return [eliminata ? [AGLIO] : [CARBONARA, AGLIO], 200];
    });
    renderBook();

    await userEvent.click(await screen.findByRole("button", { name: "Annulla" }));

    await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
    expect(await screen.findByText("Carbonara")).toBeInTheDocument();
    expect(patchMandate(spy)).toEqual([["/api/v1/recipes/r-carb", { archived: false }]]);
  });

  it("passati i secondi dell'annulla la lapide se ne va", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    stubFetch(() => [[AGLIO], 200]);
    renderBook();

    expect(await screen.findByRole("status")).toBeInTheDocument();
    await vi.advanceTimersByTimeAsync(6000);

    await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
  });

  it("un annulla che fallisce lascia la lapide con l'errore, ferma, e si riprova", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const utente = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    let tentativi = 0;
    stubFetch((_path, init) => {
      if (init?.method === "PATCH") {
        tentativi += 1;
        return tentativi === 1 ? [{ detail: "no" }, 500] : [CARBONARA, 200];
      }
      return [[AGLIO], 200];
    });
    renderBook();

    await utente.click(await screen.findByRole("button", { name: "Annulla" }));
    expect(await screen.findByText(/non sono riuscito a riportarla/i)).toBeInTheDocument();

    // il timer si è spento con l'errore: la lapide non scade mentre lo mostra
    await vi.advanceTimersByTimeAsync(6000);
    expect(screen.getByRole("status")).toHaveTextContent("Carbonara eliminata");

    await utente.click(screen.getByRole("button", { name: "Annulla" }));
    await waitFor(() => expect(screen.queryByRole("status")).toBeNull());
  });

  it("senza una ricetta eliminata non c'è lapide", async () => {
    stubFetch(() => [[AGLIO], 200]);
    renderBook(null);

    await screen.findByText("Aglio e olio");
    expect(screen.queryByRole("status")).toBeNull();
  });
});
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `npx vitest run src/features/recipes/RecipeBookScreen.lapide.test.tsx`
Expected: FAIL — `Unable to find role="status"` nei primi cinque; l'ultimo passa già.

- [ ] **Step 3: implementazione minima**

Crea `frontend/src/lib/undo.ts`:

```ts
// Quanto dura l'annulla di una lapide, in dispensa e nel ricettario. Sei secondi: il
// tempo di accorgersi di aver sbagliato riga senza che lo schermo resti mezzo finto per
// mezzo minuto. Uno solo per l'app: due lapidi con due durate non si imparano.
export const UNDO_MS = 6000;
```

In `frontend/src/features/pantry/PantryScreen.tsx`, le righe 14–16 (il commento e
`const UNDO_MS = 6000;`) diventano l'import `import { UNDO_MS } from "../../lib/undo";`
accanto agli altri.

In `frontend/src/features/recipes/RecipeBookScreen.tsx`:

- gli import in testa diventano:

```tsx
import { useEffect, useState } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { RecipeCard } from "./RecipeCard";
import { MissingBudgetFilter } from "./MissingBudgetFilter";
import { MAX_BUDGET } from "./missingBudget";
import {
  RECIPE_PAGE_SIZE,
  fetchCategories,
  fetchSearchMode,
  searchRecipes,
  setRecipeArchived,
} from "./api";
import { fetchImportStatus } from "../recipe-import/api";
import { useDebounced } from "../../hooks/useDebounced";
import { UNDO_MS } from "../../lib/undo";
```

  (il resto degli import invariato)

- sopra `export function RecipeBookScreen()`:

```tsx
interface DeletedRecipe {
  id: string;
  title: string;
}

/** La lapide: la ricetta appena eliminata, e a che punto è il suo annulla. */
type Tombstone = DeletedRecipe & { phase: "waiting" | "restoring" | "failed" };

/** La ricetta che il dettaglio ha appena eliminato, se la navigazione la porta (R10
 * §6.1): il segnale passa con lo stato della navigazione, non con la cache. */
function deletedFrom(state: unknown): DeletedRecipe | null {
  return (state as { deletedRecipe?: DeletedRecipe } | null)?.deletedRecipe ?? null;
}
```

- in testa al corpo di `RecipeBookScreen`, prima di `const [query, setQuery]`:

```tsx
  const location = useLocation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  // La lapide nasce dallo stato della navigazione e vive qui, non lì: la voce della
  // cronologia si pulisce appena letta (sotto), così un «indietro» dal prossimo
  // dettaglio non resuscita una lapide già scaduta con un «Annulla» ancora premibile.
  const incoming = deletedFrom(location.state);
  const [tombstone, setTombstone] = useState<Tombstone | null>(() =>
    incoming ? { ...incoming, phase: "waiting" } : null
  );
  const incomingId = incoming?.id;
  useEffect(() => {
    if (incomingId === undefined) return;
    navigate(location.pathname, { replace: true, state: null });
  }, [incomingId, navigate, location.pathname]);

  // sei secondi, come in dispensa; non mentre l'annulla è in volo né dopo che è
  // fallito — una lapide che scade mostrando un errore toglie l'unico modo di riprovare
  useEffect(() => {
    if (tombstone?.phase !== "waiting") return;
    const timer = setTimeout(() => setTombstone(null), UNDO_MS);
    return () => clearTimeout(timer);
  }, [tombstone]);

  const restore = useMutation({
    mutationFn: (id: string) => setRecipeArchived(id, false),
    onMutate: () => setTombstone((current) => current && { ...current, phase: "restoring" }),
    onSuccess: (_data, id) => {
      setTombstone(null);
      void queryClient.invalidateQueries({ queryKey: ["recipes"] });
      void queryClient.invalidateQueries({ queryKey: ["recipe-categories"] });
      void queryClient.invalidateQueries({ queryKey: ["recipe", id] });
    },
    // la lapide RESTA, con l'errore dentro: la ricetta è eliminata davvero, e senza la
    // lapide non ci sarebbe più un modo di riportarla (mai un vicolo cieco)
    onError: () => setTombstone((current) => current && { ...current, phase: "failed" }),
  });
```

- dopo `const recipes = uniqueById(data?.pages.flat() ?? []);`:

```tsx
  // una risposta arrivata prima dell'eliminazione la manda ancora: sotto la sua lapide
  // non deve comparire
  const visible = tombstone ? recipes.filter((recipe) => recipe.id !== tombstone.id) : recipes;
```

  e nel JSX `recipes.length === 0` → `visible.length === 0`, `recipes.length > 0` →
  `visible.length > 0`, `recipes.map(` → `visible.map(`.

- primo figlio di `<Screen …>`, prima di `<SectionEntryCard`:

```tsx
      {tombstone && (
        <div role="status" className="mb-3 flex flex-col gap-2 rounded-card bg-card p-3">
          <div className="flex min-h-11 items-center justify-between gap-3">
            <span className="min-w-0 truncate text-ink-soft">
              <span className="font-medium text-ink">{tombstone.title}</span> eliminata
            </span>
            <button
              type="button"
              disabled={tombstone.phase === "restoring"}
              onClick={() => restore.mutate(tombstone.id)}
              className="min-h-11 shrink-0 px-2 text-sm font-medium text-brand disabled:opacity-40"
            >
              Annulla
            </button>
          </div>
          {tombstone.phase === "failed" && (
            <Alert>Non sono riuscito a riportarla nel ricettario. Riprova.</Alert>
          )}
        </div>
      )}
```

- [ ] **Step 4: eseguilo e verifica che passi, poi ricettario e dispensa**

Run: `npx vitest run src/features/recipes src/features/pantry src/features/ai-draft`
Expected: PASS — i test esistenti del ricettario e della dispensa non cambiano.

- [ ] **Step 5: commit**

```bash
git add src/lib/undo.ts src/features/pantry/PantryScreen.tsx src/features/recipes/RecipeBookScreen.tsx src/features/recipes/RecipeBookScreen.lapide.test.tsx
git commit -m "$(cat <<'EOF'
ricettario: la lapide della ricetta eliminata, con «Annulla» per sei secondi

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: Il dettaglio: «Modifica», «Elimina», «Salvata», e la ricetta eliminata

Spec §6.1 e §6.2 («al termine si torna al dettaglio con “Salvata” in vista»).

**File:**
- Modify: `frontend/src/features/cooking/RecipeDetailScreen.tsx`
- Test: `frontend/src/features/cooking/RecipeDetailActions.test.tsx`

**Interfacce:**
- Consuma: `setRecipeArchived` (Task 8), la lapide del ricettario (Task 10).
- Produce:
  - «Modifica»: un link a `/ricette/:id/modifica` (la rotta arriva nel Task 12)
  - «Elimina» manda `PATCH {archived: true}` e naviga a `/ricette` con
    `{ deletedRecipe: { id, title } }`
  - lo stato di navigazione `{ saved: true }` fa mostrare «Salvata.» (`role="status"`) in
    cima e lo porta in vista — lo manda la modifica nel Task 12
  - con `archived_at` valorizzato: titolo, «Questa ricetta è stata eliminata.» e
    «Ripristina», nient'altro

- [ ] **Step 1: scrivi il test che fallisce**

Crea `frontend/src/features/cooking/RecipeDetailActions.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { RecipeDetailScreen } from "./RecipeDetailScreen";
import { RecipeBookScreen } from "../recipes/RecipeBookScreen";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import type { RecipeDetail } from "../../domain/types";

const DETAIL: RecipeDetail = {
  id: "r1", title: "Pasta al pomodoro", description: null, source: "manual",
  missing: 0, cookable: true, missing_names: [], image_url: null, prep_minutes: null,
  cook_minutes: null, category: null, cost: null, archived_at: null,
  instructions: "Cuoci.", servings: 2, source_ref: null, scaled_to: null,
  unscalable_lines: 0, dose_lines: 1, owned_by_import: false,
  ingredients: [
    { ingredient_id: "i1", ingredient_name: "pasta", role: "primary", quantity_text: "180 g",
      quantity_display: "180 g", quantity_scaled: false, note: null,
      availability: "available", satisfied: true },
  ],
};

type Rotta = (path: string, init?: RequestInit) => [unknown, number] | undefined;

/** Il test decide le risposte che gli interessano; le altre chiamate dei due schermi
 * hanno una risposta fissa. */
function stubFetch(route: Rotta = () => undefined) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const path = String(url);
    const [body, status] = route(path, init) ??
      (path.includes("/pantry")
        ? [[], 200]
        : path.includes("/imports/status")
          ? [{ fetched: 0, pending_recipes: 0, imported: 0, skipped: 0, pending_terms: 0 }, 200]
          : path.includes("/recipes/categories") || path.includes("/recipes/search?")
            ? [[], 200]
            : path.includes("/recipes/search-mode")
              ? [{ semantic: true }, 200]
              : [DETAIL, 200]);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function renderAt(entry: string | { pathname: string; state: unknown }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: defaultQueryRetryPredicate } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/ricette" element={<RecipeBookScreen />} />
          <Route path="/ricette/:id" element={<RecipeDetailScreen />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function patchMandate(spy: ReturnType<typeof stubFetch>) {
  return spy.mock.calls
    .filter(([, init]) => init?.method === "PATCH")
    .map(([url, init]) => [String(url), JSON.parse(String(init!.body))]);
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("le azioni del dettaglio (R10 §6.1)", () => {
  it("«Modifica» porta al modulo, «Elimina» gli sta accanto", async () => {
    stubFetch();
    renderAt("/ricette/r1");

    expect(await screen.findByRole("link", { name: "Modifica" })).toHaveAttribute(
      "href", "/ricette/r1/modifica"
    );
    expect(screen.getByRole("button", { name: "Elimina" })).toBeInTheDocument();
  });

  it("«Elimina» archivia subito e torna al ricettario con la lapide", async () => {
    const spy = stubFetch((_path, init) =>
      init?.method === "PATCH" ? [{ ...DETAIL, archived_at: "2026-09-28T10:00:00Z" }, 200] : undefined
    );
    renderAt("/ricette/r1");

    await userEvent.click(await screen.findByRole("button", { name: "Elimina" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Pasta al pomodoro eliminata");
    expect(patchMandate(spy)).toEqual([["/api/v1/recipes/r1", { archived: true }]]);
  });

  it("un'eliminazione che fallisce lo dice, e la ricetta resta lì", async () => {
    stubFetch((_path, init) => (init?.method === "PATCH" ? [{ detail: "no" }, 500] : undefined));
    renderAt("/ricette/r1");

    await userEvent.click(await screen.findByRole("button", { name: "Elimina" }));

    expect(await screen.findByText(/non sono riuscito a eliminarla/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Pasta al pomodoro" })).toBeInTheDocument();
  });

  it("una ricetta eliminata aperta da un collegamento offre «Ripristina» e nient'altro", async () => {
    let eliminata = true;
    const spy = stubFetch((path, init) => {
      if (init?.method === "PATCH") {
        eliminata = false;
        return [DETAIL, 200];
      }
      if (path.endsWith("/recipes/r1"))
        return [{ ...DETAIL, archived_at: eliminata ? "2026-09-28T10:00:00Z" : null }, 200];
      return undefined;
    });
    renderAt("/ricette/r1");

    expect(await screen.findByText("Questa ricetta è stata eliminata.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cucina" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Modifica" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Elimina" })).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Ripristina" }));

    expect(await screen.findByRole("button", { name: "Cucina" })).toBeInTheDocument();
    expect(patchMandate(spy)).toEqual([["/api/v1/recipes/r1", { archived: false }]]);
  });

  it("dopo un salvataggio dice «Salvata» e lo porta in vista", async () => {
    const scroll = vi.spyOn(Element.prototype, "scrollIntoView");
    stubFetch();
    renderAt({ pathname: "/ricette/r1", state: { saved: true } });

    const esito = await screen.findByRole("status");
    expect(esito).toHaveTextContent("Salvata.");
    await vi.waitFor(() => expect(scroll.mock.contexts).toContain(esito));
  });
});
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `npx vitest run src/features/cooking/RecipeDetailActions.test.tsx`
Expected: FAIL — `Unable to find an accessible element with the role "link" and name
"Modifica"`, e così gli altri.

- [ ] **Step 3: implementazione minima**

In `frontend/src/features/cooking/RecipeDetailScreen.tsx`:

- import: `import { Link, useLocation, useNavigate, useParams } from "react-router-dom";`
  e `import { fetchRecipe, setRecipeArchived, updateRecipeCost } from "../recipes/api";`

- dopo `const queryClient = useQueryClient();`:

```tsx
  const navigate = useNavigate();
  // «Salvata» arriva con la navigazione dalla modifica (R10 §6.2), come l'esito di una
  // fusione arriva alla scheda del vincitore
  const location = useLocation();
  const justSaved = (location.state as { saved?: boolean } | null)?.saved === true;

  // Eliminare e ripristinare cambiano cosa elencano ricettario e filtro per categoria,
  // oltre al dettaglio stesso: si rinfrescano tutti e tre.
  const refreshAfterArchive = () =>
    Promise.all([
      queryClient.invalidateQueries({ queryKey: ["recipe", id] }),
      queryClient.invalidateQueries({ queryKey: ["recipes"] }),
      queryClient.invalidateQueries({ queryKey: ["recipe-categories"] }),
    ]);

  // «Elimina» archivia subito, senza chiedere: la conferma è la lapide con «Annulla»
  // nel ricettario, dove si torna (R10 §6.1)
  const archive = useMutation({
    mutationFn: () => setRecipeArchived(id, true),
    onSuccess: (archived) => {
      void refreshAfterArchive();
      navigate("/ricette", { state: { deletedRecipe: { id, title: archived.title } } });
    },
  });

  const restore = useMutation({
    mutationFn: () => setRecipeArchived(id, false),
    onSuccess: () => refreshAfterArchive(),
  });
```

- dopo l'effetto di `outcomeRef` (e prima di `if (isRecipeLoading)`):

```tsx
  // «Salvata» in vista: si arriva dal pulsante in fondo al modulo, e la pagina nuova non
  // riparte dall'alto da sola
  const savedRef = useRef<HTMLParagraphElement>(null);
  const hasRecipe = recipe !== undefined;
  useEffect(() => {
    if (justSaved && hasRecipe && savedRef.current) revealAtTop(savedRef.current);
  }, [justSaved, hasRecipe]);
```

- dopo il blocco `if (isRecipeError || !recipe) { … }`:

```tsx
  // Una ricetta eliminata, aperta da un collegamento vecchio: «Ripristina» e
  // nient'altro — niente «Cucina», niente «Modifica» (R10 §6.1).
  if (recipe.archived_at !== null) {
    return (
      <div className="px-4 pt-2 pb-4">
        <BackLink to="/ricette" label="Ricette" />
        <h1 className="text-2xl font-semibold tracking-tight">{recipe.title}</h1>
        <p className="pt-2 text-ink-soft">Questa ricetta è stata eliminata.</p>
        <button
          type="button"
          onClick={() => restore.mutate()}
          disabled={restore.isPending}
          className={`${buttonClasses("primary", "block")} mt-4`}
        >
          {restore.isPending ? "Ripristino…" : "Ripristina"}
        </button>
        {restore.isError && (
          <Alert className="pt-2">Non sono riuscito a ripristinarla. Riprova.</Alert>
        )}
      </div>
    );
  }
```

- nel `return` principale, subito dopo `<BackLink to="/ricette" label="Ricette" />`:

```tsx
      {justSaved && (
        // `scroll-mt-16`: l'intestazione fissa (h-12) più un respiro, come l'esito
        // della cottura; `tabIndex={-1}` per il fuoco dato dal codice, non dal Tab
        <p
          ref={savedRef}
          role="status"
          tabIndex={-1}
          className="mb-3 scroll-mt-16 rounded-card bg-brand-tint px-3 py-2.5 text-sm text-brand"
        >
          Salvata.
        </p>
      )}
```

- dentro il frammento del ramo senza foglio, dopo il blocco
  `{isPantryError ? ( … ) : ( … )}` di «Cucina»:

```tsx
          {/* due azioni secondarie sotto «Cucina» (R10 §6.1): si correggono o si
              tolgono ricette di rado, e non devono competere con il gesto principale */}
          <div className="mt-3 flex flex-wrap gap-2">
            <Link to={`/ricette/${id}/modifica`} className={buttonClasses("secondary")}>
              Modifica
            </Link>
            <button
              type="button"
              onClick={() => archive.mutate()}
              disabled={archive.isPending}
              className={buttonClasses("danger")}
            >
              {archive.isPending ? "Elimino…" : "Elimina"}
            </button>
          </div>
          {archive.isError && (
            <Alert className="pt-2">
              Non sono riuscito a eliminarla: è ancora nel ricettario. Riprova.
            </Alert>
          )}
```

- [ ] **Step 4: eseguilo e verifica che passi, poi i test del dettaglio**

Run: `npx vitest run src/features/cooking src/features/recipes`
Expected: PASS — `RecipeDetailScreen.test.tsx` e `CookSheet.test.tsx` invariati (salvo il
campo del Task 8).

- [ ] **Step 5: commit**

```bash
git add src/features/cooking/RecipeDetailScreen.tsx src/features/cooking/RecipeDetailActions.test.tsx
git commit -m "$(cat <<'EOF'
dettaglio: «Modifica» ed «Elimina», «Salvata», e la ricetta eliminata che si ripristina

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: La schermata di modifica

Spec §6.2; deviazione 4.

**File:**
- Create: `frontend/src/features/recipe-form/RecipeEditScreen.tsx`
- Modify: `frontend/src/App.tsx` (una rotta)
- Test: `frontend/src/features/recipe-form/RecipeEditScreen.test.tsx`

**Interfacce:**
- Consuma: `RecipeForm`, `valuesFromRecipe` (Task 8–9); `fetchRecipe`, `updateRecipe`;
  lo stato `{ saved: true }` del dettaglio (Task 11).
- Produce: la rotta `/ricette/:id/modifica` → `RecipeEditScreen`; il pulsante
  «Salva le modifiche» (l'e2e del Task 14 lo usa).

- [ ] **Step 1: scrivi il test che fallisce**

Crea `frontend/src/features/recipe-form/RecipeEditScreen.test.tsx`:

```tsx
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { RecipeEditScreen } from "./RecipeEditScreen";
import { RecipeDetailScreen } from "../cooking/RecipeDetailScreen";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import type { RecipeDetail } from "../../domain/types";

const DETAIL: RecipeDetail = {
  id: "r1", title: "Pasta al pomodoro", description: null, source: "manual",
  missing: 1, cookable: false, missing_names: ["Basilico"], image_url: null,
  prep_minutes: null, cook_minutes: null, category: null, cost: null, archived_at: null,
  instructions: "Cuoci.", servings: 2, source_ref: null, scaled_to: null,
  unscalable_lines: 0, dose_lines: 1, owned_by_import: false,
  ingredients: [
    { ingredient_id: "i1", ingredient_name: "pasta", role: "primary", quantity_text: "180 g",
      quantity_display: "180 g", quantity_scaled: false, note: null,
      availability: "available", satisfied: true },
    { ingredient_id: "i2", ingredient_name: "basilico", role: "primary", quantity_text: null,
      quantity_display: null, quantity_scaled: false, note: null,
      availability: "missing", satisfied: false },
  ],
};

type Rotta = (path: string, init?: RequestInit) => [unknown, number] | undefined;

function stubFetch(route: Rotta = () => undefined) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const path = String(url);
    const [body, status] =
      route(path, init) ?? (path.includes("/pantry") ? [[], 200] : [DETAIL, 200]);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function renderEdit() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: defaultQueryRetryPredicate } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/ricette/r1/modifica"]}>
        <Routes>
          <Route path="/ricette/:id/modifica" element={<RecipeEditScreen />} />
          <Route path="/ricette/:id" element={<RecipeDetailScreen />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("la modifica di una ricetta (R10 §6.2)", () => {
  it("parte dalla ricetta, e una importata dice cosa succede salvando", async () => {
    stubFetch(() => [{ ...DETAIL, owned_by_import: true }, 200]);
    renderEdit();

    expect(await screen.findByDisplayValue("Pasta al pomodoro")).toBeInTheDocument();
    expect(screen.getByText(/salvando diventa tua, e l'import non la riscriverà più/i)).toBeInTheDocument();
  });

  it("una ricetta scritta qui non porta l'avviso", async () => {
    stubFetch();
    renderEdit();

    await screen.findByDisplayValue("Pasta al pomodoro");
    expect(screen.queryByText(/salvando diventa tua/i)).toBeNull();
  });

  it("salvare manda la PUT senza la riga tolta, e torna al dettaglio con «Salvata»", async () => {
    let salvata = DETAIL;
    const spy = stubFetch((path, init) => {
      if (init?.method === "PUT") {
        salvata = { ...DETAIL, missing: 0, cookable: true, missing_names: [], ingredients: [DETAIL.ingredients[0]] };
        return [salvata, 200];
      }
      if (path.endsWith("/recipes/r1")) return [salvata, 200];
      return undefined;
    });
    renderEdit();

    await screen.findByDisplayValue("Pasta al pomodoro");
    await userEvent.click(screen.getByRole("button", { name: "Togli basilico" }));
    await userEvent.click(screen.getByRole("button", { name: "Salva le modifiche" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Salvata.");
    const put = spy.mock.calls.find(([, init]) => init?.method === "PUT")!;
    expect(String(put[0])).toBe("/api/v1/recipes/r1");
    const corpo = JSON.parse(String(put[1]!.body));
    expect(corpo.ingredients).toEqual([{ ingredient_id: "i1", role: "primary", quantity_text: "180 g" }]);
    // la provenienza non si manda: non si cambia
    expect(corpo.source).toBeUndefined();
  });

  it("una ricetta eliminata non si modifica: dice dove ripristinarla", async () => {
    stubFetch(() => [{ ...DETAIL, archived_at: "2026-09-28T10:00:00Z" }, 200]);
    renderEdit();

    expect(await screen.findByText(/ripristinala dalla sua pagina/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Vai alla ricetta" })).toHaveAttribute("href", "/ricette/r1");
    expect(screen.queryByRole("button", { name: "Salva le modifiche" })).toBeNull();
  });

  it("se nel frattempo è stata eliminata, il rifiuto lo dice con le sue parole", async () => {
    stubFetch((_path, init) =>
      init?.method === "PUT"
        ? [{ detail: "Questa ricetta è stata eliminata: ripristinala prima di modificarla." }, 409]
        : undefined
    );
    renderEdit();

    await screen.findByDisplayValue("Pasta al pomodoro");
    await userEvent.click(screen.getByRole("button", { name: "Salva le modifiche" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Questa ricetta è stata eliminata: ripristinala prima di modificarla."
    );
  });
});
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `npx vitest run src/features/recipe-form/RecipeEditScreen.test.tsx`
Expected: FAIL — `Failed to resolve import "./RecipeEditScreen"`.

- [ ] **Step 3: implementazione minima**

Crea `frontend/src/features/recipe-form/RecipeEditScreen.tsx`:

```tsx
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { fetchRecipe, updateRecipe } from "../recipes/api";
import { Alert } from "../../components/ui/Alert";
import { Screen } from "../../components/ui/Screen";
import { buttonClasses } from "../../components/ui/buttonClasses";
import { RecipeForm } from "./RecipeForm";
import { valuesFromRecipe } from "./formModel";
import type { RecipeDetail } from "../../domain/types";

const TITLE = "Modifica la ricetta";

function EditForm({ recipe }: { recipe: RecipeDetail }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  // Una volta sola, dalla ricetta caricata: una rilettura in background mentre si
  // scrive (il fuoco che torna alla finestra) non deve cancellare il lavoro.
  const [values, setValues] = useState(() => valuesFromRecipe(recipe));

  return (
    <>
      {recipe.owned_by_import && (
        <p className="pb-3 text-sm text-ink-soft">
          È una ricetta importata: salvando diventa tua, e l'import non la riscriverà più.
        </p>
      )}
      <RecipeForm
        values={values}
        onChange={setValues}
        save={(body) => updateRecipe(recipe.id, body)}
        onSaved={() => {
          void queryClient.invalidateQueries({ queryKey: ["recipe", recipe.id] });
          void queryClient.invalidateQueries({ queryKey: ["recipes"] });
          void queryClient.invalidateQueries({ queryKey: ["recipe-categories"] });
          navigate(`/ricette/${recipe.id}`, { state: { saved: true } });
        }}
        submitLabel="Salva le modifiche"
      />
    </>
  );
}

/** `/ricette/:id/modifica`: `RecipeForm` riempito dalla ricetta, salvato con la PUT
 * (R10 §6.2). La chiave della query è quella del dettaglio a 1×, quindi arrivando da lì
 * la ricetta è già in cache. */
export function RecipeEditScreen() {
  const { id = "" } = useParams();
  const back = { to: `/ricette/${id}`, label: "Ricetta" };
  const { data: recipe, isLoading, isError, refetch } = useQuery({
    queryKey: ["recipe", id, null],
    queryFn: () => fetchRecipe(id),
  });

  if (isLoading) {
    return (
      <Screen title={TITLE} back={back}>
        <p className="text-ink-soft">Carico…</p>
      </Screen>
    );
  }

  if (isError || !recipe) {
    return (
      <Screen title={TITLE} back={back}>
        <Alert>Non sono riuscito a caricare questa ricetta.</Alert>
        <button
          type="button"
          onClick={() => void refetch()}
          className={`${buttonClasses("secondary")} mt-3`}
        >
          Riprova
        </button>
      </Screen>
    );
  }

  // una ricetta eliminata non si modifica (il backend risponderebbe 409): lo schermo
  // dice dove sta l'uscita invece di offrire un modulo che non può salvare
  if (recipe.archived_at !== null) {
    return (
      <Screen title={TITLE} back={back}>
        <p className="text-ink-soft">
          Questa ricetta è stata eliminata: ripristinala dalla sua pagina, poi modificala.
        </p>
        <Link to={`/ricette/${id}`} className={`${buttonClasses("secondary")} mt-3`}>
          Vai alla ricetta
        </Link>
      </Screen>
    );
  }

  return (
    <Screen title={TITLE} back={back}>
      <EditForm recipe={recipe} />
    </Screen>
  );
}
```

In `frontend/src/App.tsx`: `import { RecipeEditScreen } from "./features/recipe-form/RecipeEditScreen";`
e, subito dopo `<Route path="/ricette/:id" element={<RecipeDetailScreen />} />`:

```tsx
            <Route path="/ricette/:id/modifica" element={<RecipeEditScreen />} />
```

- [ ] **Step 4: eseguilo e verifica che passi, poi tutto il frontend**

Run: `npx vitest run src/features/recipe-form`
Expected: PASS.

Run: `npx vitest run && npm run lint && npm run typecheck`
Expected: tutto verde, lint e tipi puliti.

- [ ] **Step 5: commit**

```bash
git add src/features/recipe-form/RecipeEditScreen.tsx src/features/recipe-form/RecipeEditScreen.test.tsx src/App.tsx
git commit -m "$(cat <<'EOF'
ricette: la schermata di modifica, con l'avviso per le ricette importate

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 13: La coda dice quali ricette tue l'annullamento non ha toccato

Spec §4 («la coda lo dice»); deviazione 5.

**File:**
- Modify: `frontend/src/features/recipe-import/ImportQueueScreen.tsx` (`undoResultMessage`, lo stato `lastUndo`, `undo.onSuccess`)
- Test: `frontend/src/features/recipe-import/ImportQueueScreen.test.tsx`

**Interfacce:**
- Consuma: `UndoResult.adopted_untouched`, `UndoResult.ingredient_kept_for_adopted` (Task 8).
- Produce: nessuna.

- [ ] **Step 1: scrivi il test che fallisce**

In `frontend/src/features/recipe-import/ImportQueueScreen.test.tsx`:

- in `CodaOptions`, dopo `undoDetail?: string;`: `undoResult?: unknown;`
- in `renderQueue`, il ritorno riuscito dell'annullamento diventa:

```tsx
      return [
        options.undoResult ?? { recipes_requeued: 0, ingredient_deleted: false, remaining_terms: 0 },
        200,
      ];
```

- subito dopo il test «un annullamento riuscito dice quante ricette sono tornate in coda»:

```tsx
  it("un annullamento dice quali ricette tue non ha toccato, e perché l'ingrediente resta", async () => {
    renderQueue({
      pending: [],
      decided: [
        {
          id: "t9", display_name: "Guanciale", occurrences: 2, suggestion: null,
          waiting_titles: [], decided_by: "ai", decided_action: "map",
          decided_name: "guanciale", decided_at: "2026-09-20T10:00:00Z",
        },
      ],
      undoResult: {
        recipes_requeued: 1, ingredient_deleted: false, remaining_terms: 1,
        adopted_untouched: 1, ingredient_kept_for_adopted: true,
      },
    });

    await userEvent.click(
      await screen.findByRole("button", { name: /annulla la decisione su «Guanciale»/i })
    );

    expect(
      await screen.findByText(
        "1 ricetta è tornata in coda. 1 ricetta tua non è stata toccata. L'ingrediente resta in anagrafica: lo usa una ricetta tua."
      )
    ).toBeInTheDocument();
  });
```

- [ ] **Step 2: eseguilo e verifica che fallisca**

Run: `npx vitest run src/features/recipe-import/ImportQueueScreen.test.tsx`
Expected: FAIL — trovato solo «1 ricetta è tornata in coda.».

- [ ] **Step 3: implementazione minima**

In `frontend/src/features/recipe-import/ImportQueueScreen.tsx`, `undoResultMessage`
diventa:

```tsx
/** L'esito di un annullamento riuscito: quante ricette sono tornate in coda, quante
 * ricette tue non ha toccato (R10), e che fine ha fatto l'ingrediente. È l'unica cosa
 * che dice cosa ha mosso l'unico gesto distruttivo di questa schermata: senza dirlo
 * qui, si scopre solo tornando nell'anagrafica o nel ricettario.
 *
 * «Resta perché lo usa una ricetta tua» è vero sia che la decisione l'avesse creato
 * sia che l'avesse trovato: nessun fatto scritto distingue le due storie (vedi
 * `_decided_action` in backend/app/api/imports.py), e la frase non ci prova. */
function undoResultMessage({
  recipesRequeued,
  ingredientDeleted,
  adoptedUntouched,
  ingredientKeptForAdopted,
}: UndoSummary): string {
  const recipesPart =
    recipesRequeued === 0
      ? "Nessuna ricetta è tornata in coda."
      : recipesRequeued === 1
        ? "1 ricetta è tornata in coda."
        : `${recipesRequeued} ricette sono tornate in coda.`;
  const adoptedPart =
    adoptedUntouched === 0
      ? ""
      : adoptedUntouched === 1
        ? " 1 ricetta tua non è stata toccata."
        : ` ${adoptedUntouched} ricette tue non sono state toccate.`;
  const ingredientPart = ingredientDeleted
    ? " L'ingrediente che questa decisione aveva creato è stato eliminato, perché nessun'altra cosa lo usava."
    : ingredientKeptForAdopted
      ? " L'ingrediente resta in anagrafica: lo usa una ricetta tua."
      : "";
  return `${recipesPart}${adoptedPart}${ingredientPart}`;
}
```

con, sopra la funzione:

```tsx
interface UndoSummary {
  recipesRequeued: number;
  ingredientDeleted: boolean;
  adoptedUntouched: number;
  ingredientKeptForAdopted: boolean;
}
```

Lo stato `lastUndo` diventa `useState<UndoSummary | null>(null)`, e in `undo.onSuccess`:

```tsx
      setLastUndo({
        recipesRequeued: result.recipes_requeued,
        ingredientDeleted: result.ingredient_deleted,
        // `?? 0` e `?? false`: una risposta di un backend di prima di R10 non li porta,
        // e un `undefined` finirebbe scritto nella frase
        adoptedUntouched: result.adopted_untouched ?? 0,
        ingredientKeptForAdopted: result.ingredient_kept_for_adopted ?? false,
      });
```

- [ ] **Step 4: eseguilo e verifica che passi**

Run: `npx vitest run src/features/recipe-import`
Expected: PASS, compreso «Nessuna ricetta è tornata in coda.» del test di prima, che
confronta la frase intera.

- [ ] **Step 5: commit**

```bash
git add src/features/recipe-import/ImportQueueScreen.tsx src/features/recipe-import/ImportQueueScreen.test.tsx
git commit -m "$(cat <<'EOF'
coda: l'annullamento dice quali ricette tue non ha toccato

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 14: La prova nel browser vero

Spec §8.6.

**File:**
- Create: `frontend/e2e/modifica-ricette.spec.ts`

**Interfacce:**
- Consuma: tutto quel che precede; il seme `--con-ricette` per gli ingredienti
  `cetriolo` e `anguria`, che nessun altro file di `e2e/` nomina.
- Produce: nessuna.

- [ ] **Step 1: scrivi la prova**

Crea `frontend/e2e/modifica-ricette.spec.ts`:

```ts
import { expect, test, type Page } from "@playwright/test";

/**
 * R10 nel browser vero (spec §8.6): una ricetta si modifica togliendo l'unico
 * ingrediente che manca, e diventa cucinabile; si elimina, si annulla, torna. E il
 * modulo di modifica a 375 px non scorre di lato: `scrollWidth` lo calcola il browser
 * dal CSS che Tailwind ha costruito, jsdom non lo vede.
 *
 * La ricetta e la voce di dispensa si creano con `page.request`, che condivide i
 * cookie della pagina; il titolo porta l'ora, perché il ricettario vive quanto lo
 * stack. In fondo la voce si toglie e la ricetta si elimina — non esiste una
 * cancellazione vera, ed è il punto di R10 — dentro un `finally`, così un'asserzione
 * fallita a metà non lascia la dispensa sporca per le prove dopo.
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

test("una ricetta si modifica e diventa cucinabile, si elimina e torna; a 375px il modulo non scorre di lato", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();
  await expect(page.getByLabel("Aggiungi alla lista")).toBeVisible();

  const cetriolo = await ingrediente(page, "cetriolo");
  const anguria = await ingrediente(page, "anguria");
  const titolo = `Insalata e2e ${Date.now()}`;
  const creata = await page.request.post("/api/v1/recipes", {
    data: {
      title: titolo, instructions: "Taglia e condisci.", servings: 2, source: "manual",
      ingredients: [
        { ingredient_id: cetriolo.id, role: "primary", quantity_text: "1" },
        { ingredient_id: anguria.id, role: "primary", quantity_text: "1 fetta" },
      ],
    },
  });
  expect(creata.ok()).toBe(true);
  const { id: ricettaId } = (await creata.json()) as { id: string };
  let voceId: string | undefined;

  try {
    const inDispensa = await page.request.post("/api/v1/pantry", {
      data: { ingredient_id: cetriolo.id, status: "available" },
    });
    expect(inDispensa.ok()).toBe(true);
    voceId = (await inDispensa.json()).id as string;

    // manca l'anguria, e solo lei
    await page.goto(`/ricette/${ricettaId}`);
    await expect(page.getByRole("heading", { name: titolo })).toBeVisible();
    await expect(page.getByText("manca", { exact: true })).toHaveCount(1);

    // la modifica: via l'anguria, e la ricetta diventa cucinabile
    await page.getByRole("link", { name: "Modifica" }).click();
    await expect(page).toHaveURL(new RegExp(`/ricette/${ricettaId}/modifica$`));
    await page.getByRole("button", { name: "Togli anguria" }).click();
    await page.getByRole("button", { name: "Salva le modifiche" }).click();

    await expect(page).toHaveURL(new RegExp(`/ricette/${ricettaId}$`));
    await expect(page.getByRole("status").filter({ hasText: "Salvata." })).toBeVisible();
    await expect(page.getByText("manca", { exact: true })).toHaveCount(0);
    const dettaglio = (await (await page.request.get(`/api/v1/recipes/${ricettaId}`)).json()) as {
      cookable: boolean;
    };
    expect(dettaglio.cookable).toBe(true);

    // eliminare, annullare, tornare
    await page.getByRole("button", { name: "Elimina" }).click();
    await expect(page).toHaveURL(/\/ricette$/);
    const lapide = page.getByRole("status").filter({ hasText: `${titolo} eliminata` });
    await expect(lapide).toBeVisible();
    await lapide.getByRole("button", { name: "Annulla" }).click();
    await expect(lapide).toHaveCount(0);
    await page.getByLabel("Cerca nel ricettario").fill(titolo);
    await expect(page.getByRole("link", { name: new RegExp(titolo) })).toBeVisible();

    // a 375px, il modulo di modifica
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(`/ricette/${ricettaId}/modifica`);
    await expect(page.getByRole("button", { name: "Salva le modifiche" })).toBeVisible();
    await page.screenshot({ path: test.info().outputPath("modifica-375.png"), fullPage: true });
    await nonScorreDiLato(page, "il modulo di modifica");
  } finally {
    if (voceId) await page.request.patch(`/api/v1/pantry/${voceId}`, { data: { archived: true } });
    await page.request.patch(`/api/v1/recipes/${ricettaId}`, { data: { archived: true } });
  }
});
```

- [ ] **Step 2: eseguila sullo stack e2e**

Prima di alzare lo stack: **un altro ramo può usare lo stesso progetto `spena-e2e`.**

```bash
docker ps --format '{{.Names}}' | grep spena-e2e
```

Se stampa qualcosa, lo stack è di qualcun altro: **non** fare `down`, aspetta che sparisca
(riprova ogni qualche minuto) e solo allora prosegui. Poi, dalla radice del worktree:

```bash
E2E="docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml"
$E2E up -d --build --wait
$E2E exec -T backend python -m app.cli.seed --con-ricette
(cd frontend && E2E_BASE_URL=http://localhost:5174 npx playwright test e2e/modifica-ricette.spec.ts)
```

Expected: 1 passed. La password dello stack è «test». Lo stack resta su per il Task 16;
se ti fermi qui, `$E2E down -v`.

Se la prova fallisce su un selettore, guarda lo screenshot in `frontend/test-results/`
prima di cambiare la prova: un bottone che non c'è è un difetto dello schermo, non del
test.

- [ ] **Step 3: commit**

```bash
git add frontend/e2e/modifica-ricette.spec.ts
git commit -m "$(cat <<'EOF'
e2e: modificare, eliminare e ripristinare una ricetta, e il modulo a 375px

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 15: Gli emendamenti

Spec §10, da fare insieme. Solo documenti e una docstring: nessun test nuovo, ma la suite
deve restare verde (la docstring sta in un modulo che la suite importa).

**File:**
- Modify: `docs/prossimi-passi.md` (la testata, la sezione R10, tre righe di T3)
- Modify: `CLAUDE.md` (la sezione sul non alimentare e quella sull'import)
- Modify: `backend/app/services/recipe_import/undo.py` (docstring del modulo, un commento)

**Interfacce:** nessuna.

- [ ] **Step 1: `docs/prossimi-passi.md`**

La prima riga dopo il titolo, «Aggiornato il 2026-09-27, cinque volte. La quinta:»,
diventa:

```markdown
Aggiornato il 2026-09-28: **R10 è fatta** — una ricetta salvata si modifica e si elimina,
con la lapide; non ancora in produzione. Prima, il 2026-09-27, cinque volte. La quinta:
```

La sezione R10, dal titolo fino alla riga prima di `## R11.`, diventa:

```markdown
## R10. Una ricetta salvata non si corregge né si cancella **[FATTO 2026-09-28 — spec: `docs/superpowers/specs/2026-09-27-modifica-ricette-design.md`, piano: `docs/superpowers/plans/2026-09-28-modifica-ricette.md`; non ancora in produzione]**
Una ricetta scritta a mano o dalla bozza AI restava per sempre com'era: un refuso nel
titolo, un ingrediente dimenticato, una ricetta di prova. È lo stesso principio di S9,
applicato alle ricette. Non c'era una `DELETE`, e la `PATCH /recipes/{id}` cambiava solo
`cost`.

**Com'è fatto.** Ogni ricetta si modifica, anche importata, con lo stesso modulo di
«Scrivi una ricetta» (`RecipeForm`, in `frontend/src/features/recipe-form/`), da
«Modifica» in fondo al dettaglio, con `PUT /recipes/{id}`. «Elimina» archivia
(`recipes.archived_at`, migrazione `0011`) e torna al ricettario con la lapide e
«Annulla» per sei secondi; una ricetta eliminata aperta da un collegamento vecchio dice
«Questa ricetta è stata eliminata» e offre «Ripristina». Il primo salvataggio di una
modifica, o l'eliminazione, passa la pagina d'import ad `adopted` nella stessa
transazione, e non torna indietro: l'annullamento di una decisione la lascia e la conta
(«1 ricetta tua non è stata toccata»), la materializzazione e la risincronizzazione non
la vedono, una fusione ne sposta le righe in loco, `reread_costs` la salta. Ogni elenco
di ricette — ricerca testuale e semantica, sfoglio con i suoi filtri, categorie,
`reindex` — esclude le eliminate dentro la query che ha il limite. Il modulo chiude anche
tre note del giro di T3: descrizione e categoria (scelta fra quelle del ricettario), il
ruolo su ogni riga, la ✕ al posto della spunta.

**Le deviazioni dalla spec** sono dodici, scritte in testa al piano con il loro perché.
Le tre che si vedono: la categoria si sceglie anche creando, e il backend rifiuta con 422
un nome che il ricettario non ha; il dettaglio manda `owned_by_import`, perché l'avviso
«salvando diventa tua» sia vero solo quando lo è; l'anagrafica continua a contare le
ricette eliminate, perché una ricetta ripristinata non torni con una riga non alimentare.

**Resta aperto:**
- `POST /recipes/{id}/cook` non rifiuta una ricetta eliminata: il dettaglio non offre
  «Cucina», ma una PWA con la cache vecchia potrebbe ancora mandarla.
- `counts().imported`, cioè «N sono già dentro» nella coda, non conta le pagine `adopted`.
- La ricerca semantica esclude le eliminate nella query che ha il limite, ma l'indice
  HNSW è approssimato: con molte eliminate vicine alla domanda, la query può vedere meno
  di `CANDIDATE_POOL` candidati (`hnsw.ef_search`, 40 di default). Oggi non conta — in
  produzione gli embedding non ci sono — e il test lo neutralizza alzando `ef_search`.
- La distribuzione, con la migrazione `0011` all'avvio, la decide Mattia.
```

Sotto «**Scrivi una ricetta**» dell'esito del giro di T3, in fondo a tre righe, dopo il
punto finale, ` *(Fatto con R10.)*`:
- «**Il ruolo delle righe proposte dall'AI non si cambia**, …»
- «**Mancano categoria e descrizione**, …»
- «**Le righe a mano si tolgono solo togliendo la spunta**, …»

- [ ] **Step 2: `CLAUDE.md`**

Nel riquadro «Since 2026-09-17 the registry also holds non-food entries», la frase
«it is precisely that rule the funnel in `create_recipe` (`backend/app/repositories/recipes.py`)
defends» diventa:

```markdown
it is precisely that rule the funnel in `write_recipe_ingredients`
(`backend/app/repositories/recipes.py`) defends — the single writer of recipe lines,
which both `create_recipe` and the recipe edit (R10) go through
```

Nella voce «Import brings in recipes, not random new ingredients», dopo la frase che
finisce con «back on the rebuilt recipe (S9 §5.2).» e prima di «A response that cannot
be verified…», inserisci:

```markdown
  **A recipe the user edits or deletes is theirs** (R10): the first save of an edit, or
  the deletion, moves its import page to `adopted` in the same transaction, and nothing
  in the import rebuilds it again — undo counts it and leaves it, `materialize_ready` and
  a resync never see it, a merge moves its lines in place, `reread_costs` skips it.
  Deleting archives (`recipes.archived_at`, restored from the tombstone or an old link),
  and every recipe listing excludes archived recipes inside the query that carries the
  limit. Spec: `docs/superpowers/specs/2026-09-27-modifica-ricette-design.md`.
```

- [ ] **Step 3: la docstring di `backend/app/services/recipe_import/undo.py`**

Nel terzo paragrafo della docstring del modulo, «Il costo, l'unico campo che
l'applicazione lascia modificare a mano (R9).» diventa «Il costo, l'unico campo che si
cambia senza prendere in carico la ricetta (R9, R10).», e l'ultima frase, «Il giorno in
cui una ricetta importata potrà essere modificata in altro (R10), questo file va
ripensato.», si toglie. Dopo quel paragrafo, prima delle virgolette di chiusura, un
paragrafo nuovo:

```python
Ripensato con R10, quando le ricette importate sono diventate modificabili. Una ricetta
che l'utente modifica o elimina non è più dell'import: la sua pagina passa ad `adopted`
nella stessa transazione, e qui si selezionano solo le pagine `imported`. Una pagina
`adopted` non si cancella e non torna in coda: rifarla dal `payload` cancellerebbe il
lavoro di chi l'ha corretta, ed è per questo che la presa in carico esiste. Le si conta
soltanto (`adopted_untouched`), perché la coda dica che l'annullamento non le ha
toccate; e se l'ingrediente del termine resta perché una di loro lo usa ancora
(`delete_ingredient_if_unused` lo lascia), lo si dice (`ingredient_kept_for_adopted`).
Le loro righe restano sull'ingrediente di prima: spostarle è una modifica della ricetta,
o una fusione in anagrafica, che le sposta in loco.
```

Nel corpo di `undo_decision`, il commento sopra la copia del costo nel `payload`
(«Il costo si sceglie anche a mano dal dettaglio (R9): è l'unica modifica che una
ricetta importata può ricevere, e rifacendola da `payload` si perderebbe. …») diventa:

```python
            # Il costo si sceglie anche dal dettaglio (R9), ed è l'unica modifica che non
            # prende in carico la ricetta (R10): rifacendola da `payload` si perderebbe.
            # Scritto nel `payload`, `materialize_ready` lo rilegge da lì.
```

- [ ] **Step 4: la suite resta verde**

Run: `cd backend && $PYTEST -q tests/services/test_undo.py tests/api/test_imports_undo.py`
Expected: PASS.

- [ ] **Step 5: commit**

```bash
git add docs/prossimi-passi.md CLAUDE.md backend/app/services/recipe_import/undo.py
git commit -m "$(cat <<'EOF'
docs: R10 fatta, la presa in carico in CLAUDE.md, e undo.py ripensato

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 16: La verifica finale

Niente codice nuovo: tutto quel che il ramo promette, eseguito dall'inizio alla fine.
Se un passo fallisce, si torna al task che lo riguarda; qui non si corregge niente.

**File:** nessuno (salvo una riga in `docs/prossimi-passi.md` allo Step 6).

- [ ] **Step 1: il backend intero**

Run: `cd backend && $PYTEST -q`
Expected: tutto verde. Il numero di test è la linea di partenza del Task 1 più i nuovi
(circa 60; annota il numero esatto).

- [ ] **Step 2: il frontend**

Da `frontend/`:

```bash
npm run lint
npm run typecheck
npx vitest run
npm run build
```

Expected: lint e tipi puliti (`typecheck` è `tsc -b`: mai `tsc --noEmit`), vitest tutto
verde, build riuscita. E il colore resta nei token:

```bash
grep -rnE "emerald|neutral-|#[0-9a-f]{6}" src --include=*.tsx
```

Expected: nessuna riga.

- [ ] **Step 3: che i test di «Scrivi una ricetta» siano cambiati solo dove dovevano**

```bash
git diff f390231 -- frontend/src/features/ai-draft/AiDraftScreen.test.tsx
```

Expected: solo i quattro punti del Task 9 (e il commento aggiunto al quarto). Qualunque
altra riga cambiata è un test ammorbidito per far passare il codice: si torna al Task 9.

- [ ] **Step 4: la prova nel browser vero**

**Prima di tutto, `docker ps --format '{{.Names}}' | grep spena-e2e`**: se lo stack c'è e
non l'hai alzato tu (Task 14), è di un altro ramo — non fare `down`, aspetta che sparisca.
Poi, dalla radice del worktree:

```bash
E2E="docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml"
$E2E up -d --build --wait
$E2E exec -T backend python -m app.cli.seed --con-ricette
(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
$E2E down -v
```

Expected: tutte le prove di `e2e/` passano (quelle di prima più `modifica-ricette.spec.ts`).
La password dello stack è «test». Lo stack si alza da questo worktree, quindi costruisce
questo ramo.

- [ ] **Step 5: guarda lo screenshot**

Apri `frontend/test-results/*/modifica-375.png`: a 375 px il modulo di modifica deve
avere le righe con la ✕ dentro lo schermo, il ruolo leggibile, il pulsante «Salva le
modifiche» a tutta larghezza. `scrollWidth` prova che niente scorre di lato, non che si
legga bene: questo lo vede un occhio.

- [ ] **Step 6: annota e chiudi**

In `docs/prossimi-passi.md`, in fondo alla sezione R10, una riga con i numeri veri:

```markdown
**Verificato il 2026-09-28 sul ramo `r10-ricette`:** backend N, vitest M, e2e K/K, lint,
typecheck e build puliti. Non ancora distribuito.
```

(con N, M, K letti dagli Step 1, 2 e 4), e il commit:

```bash
git add docs/prossimi-passi.md
git commit -m "$(cat <<'EOF'
docs: R10, la verifica finale del ramo

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
EOF
)"
```

Nessun deploy, nessun `docker compose -f docker-compose.prod.yml`: la distribuzione la
decide Mattia.
