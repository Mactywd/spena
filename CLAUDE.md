# Spena — Developer Notes

Shopping list, pantry tracking, and recipe suggestions for a single user. The v1
goal is one closed loop: write the list → unpack the shopping into the pantry →
cook a recipe → whatever ran out goes back on the list.

**Read these before touching anything:**

- `docs/superpowers/specs/2026-09-11-spena-design.md` — the design, in Italian. It
  is the authority on scope and on the two founding decisions below.
- `docs/superpowers/plans/2026-09-11-spena-v1.md` — the 24-task implementation
  plan, in Italian, test-first with exact file paths and code per step.

**Status: the plan has not been executed yet.** The repository holds only the spec
and the plan. When implementing, follow the plan task by task rather than
improvising a structure.

## The two decisions everything else follows from

**1. No quantities, anywhere.** The pantry does not know amounts, units, or expiry
dates. An ingredient is `available`, `low`, or `finished`. This is deliberate, not
an omission: it removes unit conversion and the daily upkeep that makes apps like
this get abandoned. `recipe_ingredients.quantity_text` is free text for display and
must never enter a calculation. The consequence is that nutrition cannot be derived
from stock levels, which is why nutrition tracking is phase 3 on its own track.

**2. Generic ingredient and specific product are different things.** `yogurt greco`
is an ingredient: the shopping list writes it, recipes require it, availability is
computed on it. `Fage Total 0%` with its barcode is a product: it is what actually
enters the pantry. Pantry items always carry an ingredient and optionally a product,
so loose apples and a branded yogurt coexist. Keep recipes pointing at ingredients
only; that is what keeps the recipe-to-pantry match a simple join while nutrition
stays accurate per brand.

## The rule that makes `low` useful

Every recipe ingredient is `primary` or `secondary`. A primary needs `available`;
a secondary accepts `available` or `low`. A nearly empty tomato can will not make
pasta al pomodoro, but it will make a soffritto. This lives as pure functions in
`backend/app/domain/rules.py` with no database access, and it is the first thing to
test, table-driven over every status and role combination.

Availability of an ingredient is the best status among its active pantry items.
Items that are `finished` or have `archived_at` set do not count.

## Stack and layout

```
backend/    FastAPI (Python 3.12), async SQLAlchemy, Alembic
frontend/   React 19 + Vite + TypeScript, mobile-first PWA, served by Nginx
db          Postgres 16 with pgvector and pg_trgm
```

All domain logic lives in the backend. The frontend asks whether a recipe is
cookable; it never works it out itself. That is what makes the planned Capacitor
port a wrapper rather than a rewrite.

Two external dependencies, each behind its own service with a narrow interface:
`OpenFoodFactsClient` for barcodes and `EmbeddingProvider` for semantic search.
Claude (`claude-sonnet-5`) is used only to draft recipes and to propose ingredient
matches. It never produces nutrient values.

## Conventions worth knowing

- **Never a dead end.** Every failure of an external dependency degrades to manual
  entry. Open Food Facts unreachable, barcode unknown, embedding model missing, an
  ingredient that resolves to nothing: all of these must leave the user able to
  continue, never facing an error page.
- **Tests run on real Postgres**, started through Compose. Not SQLite: the schema
  needs `vector` and `pg_trgm`. No network calls in the suite; Open Food Facts and
  Claude run against recorded fixtures.
- **e5 embeddings need their prefixes.** `query: ` for searches, `passage: ` for
  documents. Omitting them raises no error and silently degrades result quality.
- **Missing nutrients stay missing.** Never default an unknown nutrient to zero:
  zero is a claim, absence is the truth.
- Specs and plans are written in Italian, code and identifiers in English.

## Roadmap beyond v1

Phase 2 adds receipt scanning, nutrient estimation from a label photo, and bulk
import of an external recipe dataset. Phase 3 adds the food diary and
micronutrients. Phase 4 adds the suggestion engine. The `cooking_events` table
exists in v1 with no consumer precisely so phase 3 has a history to build on.
Details are in §4 of the spec.
