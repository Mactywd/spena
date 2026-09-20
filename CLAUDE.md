# Spena — Developer Notes

Shopping list, pantry tracking, and recipe suggestions for a single user. The v1
goal is one closed loop: write the list → unpack the shopping into the pantry →
cook a recipe → whatever ran out goes back on the list.

**Read these before touching anything:**

- `docs/superpowers/specs/2026-09-11-spena-design.md` — the design, in Italian. It
  is the authority on scope and on the two founding decisions below.
- `docs/superpowers/plans/2026-09-11-spena-v1.md` — the 24-task implementation
  plan, in Italian, test-first with exact file paths and code per step.

**Status: v1 is implemented.** All 24 tasks of the plan are done on branch
`v1-foundations`. The plan stays as the record of why the code looks the way it
does; the code is now the authority on what it does. `README.md` covers running,
testing and deploying.

Seven things reviews here kept rediscovering, written down so the next person does
not pay for them again:

- **A test that builds its own object is not testing the one production uses.**
  Three separate defects survived this way: a react-query client that retried
  forever (every screen test built its own with `retry: false`), two domain
  functions whose table-driven test guarded a copy nobody called, and an image
  missing `anthropic` while every AI test injected a fake client. Ask of any
  guarantee: is the thing under test the thing that runs?
- **Compose interpolates `$` in `env_file` values in the short form.** An argon2
  hash is full of `$`, so `env_file: .env` truncates `APP_PASSWORD_HASH` (measured:
  97 characters arrive as 62) and login then fails always. Both compose files use
  the long form with `format: raw`, which needs Compose 2.30 or newer, and a test
  parses them to keep it that way. Do not "simplify" it.
- **A `docker compose` without `-f` replaces production with the dev stack.** Both
  files share the project name `spena`, so `docker compose up -d` on the server
  swaps the prod containers for the dev ones — same volume, no data lost, and no
  Traefik labels, so the domain silently stops resolving to the app. Nothing logs
  an error anywhere: the PWA service worker keeps serving its cached shell while
  every API call fails, which looks exactly like a broken feature. Deploy is
  `docker compose -f docker-compose.prod.yml up -d --build --wait`, always.
- **A CSS selector is not a test surface, and no unit test will tell you.** The
  base-layer rule that styles every text field was first written
  `input[type="text"]`, which matches nothing when the element has no `type`
  attribute — half this app's fields. They rendered transparent and borderless on a
  grey page while all 157 jsdom tests passed, because Tailwind builds the CSS and
  jsdom does not compute it. Visual work is verified in a real browser;
  `frontend/e2e/style.spec.ts` now holds that ground.
- **"Never a dead end" is violated most often by a fix, not by an omission.**
  Adding the ingredient/product guard turned one mismatched barcode into a rejected
  whole shop with an unactionable "riprova". When you close a hole, ask what the new
  refusal leaves the user able to do.
- **A filter that works on the result cannot sit behind a limit.**
  `recipe_search.py` selected the 100 most recent recipes and then applied
  `only_cookable`: with 26 recipes that was the whole recipe book, with 500 it
  is a sample, and "what can I cook" would have answered by looking only at
  yesterday's recipes. No test could see it, because no test had more recipes
  than the candidate pool. When a job multiplies the data, look for the limits
  written when the data was small.
- **`tsc --noEmit` is not the project's type check.** `frontend/tsconfig.json` is
  solution-style — `{"files": [], "references": [...]}` — so `tsc --noEmit` reads
  it, finds zero files to compile, and exits 0 always, whatever errors sit in the
  code (measured: on a tree where `npx tsc -b --force` reports a `TS2739` in
  `CookSheet.test.tsx`, `npx tsc --noEmit` still exits 0). Every task on
  `import-ricette` ran `tsc --noEmit` as its type check, so an object literal left
  missing four fields added to `RecipeSummary` shipped past all of them; only
  `npm run build` (`tsc -b && vite build`, now also `npm run typecheck`) caught it,
  and only at the final browser-verification task. Ask of any green type check: did
  it compile project references, or find none to compile?

## The two decisions everything else follows from

**1. No quantities, in the pantry.** The pantry does not know amounts, units, or
expiry dates. An ingredient is `available`, `low`, or `finished`. This is
deliberate, not an omission: it removes unit conversion and the daily upkeep that
makes apps like this get abandoned. `pantry_items.fill_percent` (0–100, nullable)
is not an exception: it is a slider *position* — no unit, no expiry — read only by
`status_for_fill` to pick one of the three statuses, which stays the only truth the
rest of the app reasons on. The reasoning is in the note under D1 of
`docs/prossimi-passi.md`; read it before citing this column as a precedent.

The rule narrows to exactly that (decided 2026-09-17, built since): recipes — and
only recipes — carry structured quantities too. A recipe ingredient has
`quantity_value` and `quantity_unit_id` beside `quantity_text`, both nullable,
filled on a best-effort basis by the parser in `backend/app/domain/quantities.py`.
`quantity_text` stays the truth shown at 1× and is never rewritten; the structured
pair is what a rescale reads, and a line the parser could not fill — `q.b.` foremost
— simply does not scale, declared as such rather than guessed. **The pantry keeps
the rule whole**: no amounts, no units, no expiry there, which is where the rule
bought what it was meant to buy. Nutrition still cannot be derived from what a
recipe's quantities say, let alone from stock levels — that needs the grams-per-unit
work of S4 too — which is why nutrition tracking is phase 3 on its own track.

**2. Generic ingredient and specific product are different things.** `yogurt greco`
is an ingredient: the shopping list writes it, recipes require it, availability is
computed on it. `Fage Total 0%` with its barcode is a product: it is what actually
enters the pantry. Pantry items always carry an ingredient and optionally a product,
so loose apples and a branded yogurt coexist. Keep recipes pointing at ingredients
only; that is what keeps the recipe-to-pantry match a simple join while nutrition
stays accurate per brand.

> **Since 2026-09-17 the registry also holds non-food entries** — detergent, toilet
> paper — split off by `ingredients.kind` (`food` | `non_food`), which is never
> written by hand: it is derived from the department by `kind_for_category` in
> `backend/app/domain/rules.py`. They live in the same list and the same pantry,
> with the same three statuses. **The rule above is untouched**: recipes still
> point at ingredients only, and it is precisely that rule the funnel in
> `create_recipe` (`backend/app/repositories/recipes.py`) defends — a recipe
> cannot name a non-food entry. That funnel is the last line, not the only one:
> the AI's import decisions and the human review queue refuse a non-food term
> before it ever reaches a recipe, and the three ingredient pickers used by the
> recipe screens ask the registry for `kind=food` only. See
> `docs/superpowers/specs/2026-09-17-non-alimentari-design.md` for where each of
> these lives.

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
An LLM (`google/gemma-4-26b-a4b-it`, reached through OpenRouter via
`services/llm.py`) drafts recipes and decides the import's unknown ingredient
terms. It never produces nutrient values. There is one provider and one client
on purpose: a second implementation behind a config switch would never run in
production, which is the first defect listed above.

## Conventions worth knowing

- **Never a dead end.** Every failure of an external dependency degrades to manual
  entry. Open Food Facts unreachable, barcode unknown, embedding model missing, an
  ingredient that resolves to nothing: all of these must leave the user able to
  continue, never facing an error page.
- **Tests run on real Postgres**, started through Compose. Not SQLite: the schema
  needs `vector` and `pg_trgm`. No network calls in the suite; Open Food Facts and
  the LLM run against recorded fixtures.
- **e5 embeddings need their prefixes.** `query: ` for searches, `passage: ` for
  documents. Omitting them raises no error and silently degrades result quality.
- **Missing nutrients stay missing.** Never default an unknown nutrient to zero:
  zero is a claim, absence is the truth.
- **All colour lives in one `@theme` block** in `frontend/src/index.css`, as design
  tokens Tailwind turns into classes (`--color-brand` → `bg-brand`). No screen names
  a raw colour: grepping `src/` for `emerald` or `neutral-` must keep returning
  nothing. Shared primitives are in `frontend/src/components/ui/`; look there before
  writing a fourth button variant. Contrast is a constraint, not a preference —
  anything carrying white text is above 4.5:1, because this app is read in a
  supermarket aisle in daylight.
- Specs and plans are written in Italian, code and identifiers in English.
- **Import brings in recipes, not random new ingredients.** The source catalogue
  is finer than the ingredient registry: `Rigatoni` becomes an alias of `pasta`,
  decided once in `import_terms` and written into `ingredient_aliases`. There is
  no second mapping table, and a wrong decision is corrected from the ingredient
  registry. **The LLM decides these terms and the queue is the review**: every
  decision carries `decided_by = "ai"` and has an undo that puts the term, the
  alias, the created ingredient and the materialized recipes back. A response
  that cannot be verified against the real registry is never applied — the term
  stays in the queue. Specs are
  `docs/superpowers/specs/2026-09-12-import-ricette-design.md` and
  `docs/superpowers/specs/2026-09-13-llm-openrouter-design.md`; the second
  reverses §8.2 of the first.

## Roadmap beyond v1

Phase 2 was three things; bulk import of an external recipe dataset is done, so
what remains is receipt scanning and nutrient estimation from a label photo.
Phase 3 adds the food diary and micronutrients. Phase 4 adds the suggestion
engine. Two footings for phase 3 are already in place: the `cooking_events`
table exists with no consumer precisely so it has a history to build on, and
`products.nutrients` is already populated from Open Food Facts. Details are in
§4 of the spec.

**`docs/prossimi-passi.md` is the single list of what is open** — the manual
verification of v1 that no test can do, the small loose ends, and the phase
ordering. Read it before starting anything new, and keep it current: everything
in it existed only in one conversation before it was written down.
