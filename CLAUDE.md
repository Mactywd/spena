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

Eight things reviews here kept rediscovering, written down so the next person does
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
  The hash itself lives in `password.env` (gitignored, mode 600, written by
  `scripts/imposta-password.sh <compose file>`), never in `.env`: Compose also reads
  `.env` to substitute the `${...}` inside the compose files, a step `format: raw`
  does not reach, so every `$` of the hash became a "variable is not set" warning
  that printed a piece of it, on every command (seen on the server 2026-10-19).
  `password.env` is the second long-form entry, `required: false`, after `.env`, so
  it wins; the e2e override's `.env.e2e` lands after both. The same test parses all
  three compose files, `.env.example` and `.gitignore` to keep it that way. Never run
  `docker compose config` without `--quiet`: it prints the backend's resolved
  environment, which is the hash.
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
- **A similarity of 1.0 is a tie, not a match.** `word_similarity` in `pg_trgm` scores
  1.0 for every name that contains the word, so on the real CIQUAL table «riz» tied 43
  names — rice pudding, rice starch, rice drink — and the alphabetical tie-break left
  `Riz blanc, cru` outside the 15 candidates. The pilot read it as the model failing (20
  of 29); four invented fixture rows never tie, so no test could see it. `find_candidates`
  now breaks ties on the name starting with the term, then on whole-name `similarity`,
  and `tests/repositories/test_ciqual_repository.py` runs the search on the real file.
  When a ranking sorts on a score, ask how many rows reach the top score on the real data.

## The two decisions everything else follows from

**1. No quantities, in the pantry.** The pantry does not know amounts or units. An
ingredient is `available`, `low`, or `finished`. This is deliberate, not an omission:
it removes unit conversion and the daily upkeep that makes apps like this get
abandoned. `pantry_items.fill_percent` (0–100, nullable) is not an exception: it was
a slider *position* — no unit, nothing to convert — and since T3's first screen
(2026-09-28) no client writes it any more: the pantry's three notches send `status`
directly, and `set_status` clears the column. It stays in the schema, nullable, with
its CHECK and its place in `PantryItemOut`; the `PATCH` path that wrote it
(`set_fill`) was removed on 2026-09-29, so nothing writes it now, and a `PATCH`
carrying only `fill_percent` is answered 400. `status_for_fill` stays in `rules.py`
with its tests and no production caller. The
three statuses stay the only truth the rest of the app reasons on. The reasoning is
in the note under D1 of `docs/prossimi-passi.md`; read it before citing this column
as a precedent.

The rule narrows to exactly that (decided 2026-09-17, built since): recipes — and
only recipes — carry structured quantities too. A recipe ingredient has
`quantity_value` and `quantity_unit_id` beside `quantity_text`, both nullable,
filled on a best-effort basis by the parser in `backend/app/domain/quantities.py`.
`quantity_text` stays the truth shown at 1× and is never rewritten — with one
exception, decided by Mattia on 2026-10-13: a dose still in the import's shape (a
newline or a tab in it, as GialloZafferano writes them) is cleaned once, its words
before the number moved to the line's `note` (`clean_dose`, run by the import and by
`python -m app.cli.clean_doses`); a dose without that shape is never touched. The structured
pair is what a rescale reads, and a line the parser could not fill — `q.b.` foremost
— simply does not scale, declared as such rather than guessed. **The pantry keeps
the rule whole on amounts**: no quantities and no units there, which is where the rule
bought what it was meant to buy. Nutrition still cannot be derived from what a
recipe's quantities say, let alone from stock levels — that needs the grams-per-unit
work of S4 too — which is why nutrition tracking is phase 3 on its own track.

The pantry does carry one date, and it is the only other bend (decided 2026-09-20 as
D5, built 2026-09-21): `pantry_items.expires_on`, a nullable `DATE` on the pantry item
— *that* jar expires, not `yogurt greco` and not `Fage Total 0%` — with no CHECK
constraint, because a date already in the past is legitimate: people write it the day
after, with the jar in hand. It does not enter `status_for_fill`, it never reaches
`availability_map`, and no cookability judgement reads it: an expired item stays
available and recipes count it exactly as the day before, so nothing becomes
uncookable overnight with nobody having touched anything. It is a signal on the row
and nothing else. The verdict travels already decided inside `PantryItemOut` as
`expiry` (`"soon"` / `"expired"` / `null`), from `expiry_state` in
`backend/app/domain/rules.py` — beside `status_for_fill` and deliberately outside it,
with `EXPIRY_SOON_DAYS = 7`, and with *today* read in `Europe/Rome` through
`PANTRY_TZ` and not in UTC, because a UTC calendar day is not the day of someone
opening the app in Milan at half past midnight. So the number 7 never crosses into the
TypeScript.

Why the rule bends for a date and not for an amount is the whole argument, and it is
D5's: **a quantity has to be maintained and starts lying the day you stop; an expiry
is written once and never touched again.** Leave it empty and you have exactly the
pantry you had before. The column stands beside `fill_percent` above and for the same
reason: present, nullable, and no precedent for amounts, because the three statuses
remain the only truth the rest of the app reasons on. Spec:
`docs/superpowers/specs/2026-09-21-scadenza-dispensa-design.md`.

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
> `write_recipe_ingredients` (`backend/app/repositories/recipes.py`) defends — the
> single writer of recipe lines, which both `create_recipe` and the recipe edit
> (R10) go through — a recipe cannot name a non-food entry. That funnel is the
> last line, not the only one: the AI's import decisions and the human review
> queue refuse a non-food term
> before it ever reaches a recipe, the three ingredient pickers used by the
> recipe screens ask the registry for `kind=food` only, and the form's new-name
> step asks `GET /ingredients/match` as the name is typed — the same
> `ingredient_for_new_name` the save calls — and refuses a non-food there, with
> a way out. See
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
An LLM, Claude Haiku (`claude-haiku-5-5`, `LLM_MODEL`), reached through the Anthropic
Messages API with the official `anthropic` SDK in `services/llm.py`, decides the
import's unknown ingredient terms and the questions of units, figures, substitutes,
CIQUAL matches and grams, and drafts recipes and their variants. It never produces
nutrient values. There is one client on purpose, and its options are built in one
place (`client_options`), with the key from the settings and the API address written
in the code, never read from the environment: tests replace only its HTTP transport
(`httpx2.MockTransport`; the fakes also make `copy`/`with_options` return themselves, recording the options), so the SDK that builds the request and parses the response
under test is the one production runs. Anthropic reports tokens, not prices: spena
computes the cost from the tokens and the price list in
`backend/app/domain/llm_pricing.py`, cache reads and writes included, and keeps the
cache tokens in `llm_calls` so every cost can be redone from its row. A failure carries
a kind (`LlmFailureKind`): no key, a revoked key, credit run out, the rate limit or a
rejected request stop a fan-out at the first one; in the term decisions the others
leave only that item in the queue, while the batch commands stop at the first failure
of any kind — except `decide_grams`, which splits a batch whose answer cannot be read
(truncated or invalid) down to a single pair, skips a pair that cannot be read even
alone, and stops only when every pair of a batch of more than one was skipped. A second implementation behind a config switch would never run in
production, which is the first defect listed above.

The drafts and the variants (R8) are told which utensils the kitchen has: the list
Mattia keeps in «Utensili», from the hamburger (`utensils` table, `/api/v1/utensils`),
goes at the end of their system prompt through `utensils_prompt_block` in
`backend/app/services/utensils.py`, read at every call. An empty list means no
constraint, not no tools: the prompt is then exactly the one of before. Imported
recipes are never checked against it. Spec: `docs/superpowers/specs/2026-11-12-pasti-claude-design.md`, §4.4 and §8.

**Two paths to Claude, on purpose, on one key.** The meal chat, the planning and the
meals' recipes run on Claude Opus (`claude-opus-5-5`) through the Claude Agent SDK for
Python (`claude-agent-sdk`, pinned, with its bundled Claude Code binary), authenticated
with Mattia's Anthropic API key, `ANTHROPIC_API_KEY`, kept only in the server's `.env`
(decided by Mattia on 2026-11-18; since 2026-11-21 the same key serves the import's
LLM, with a spend limit in the Anthropic console: a large import draws on the meals'
credit too). The SDK gets `CLAUDE_CODE_OAUTH_TOKEN` and `ANTHROPIC_AUTH_TOKEN` empty, so
a subscription token left in the environment can never take over. This is not what the
one-provider rule above forbids: that rule is against two implementations behind a
switch, one of which never runs. Here there are two paths with two jobs, both
Anthropic's and both running in production — the Messages API with Haiku for the
import, drafts and variants; the Agent SDK with Opus for the meals. The SDK is driven
with every built-in tool off (`tools=[]`), no settings or `CLAUDE.md` loaded
(`setting_sources=[]`), `permission_mode="dontAsk"`, no session transcripts on disk
(`--no-session-persistence`, proven on the bundled binary by
`tests/test_claude_binary.py`), and spena's own tools as an in-process MCP server
(`backend/app/services/claude/`). Its calls go into `llm_calls` as `meal_chat`,
`meal_planning` and `meal_recipe` with their tokens and the cost Claude Code reports
(`ResultMessage.total_cost_usd`, an estimate from its price list), failed turns
included, and «Spese dell'AI» counts them like any other section. Claude writes a
meal's recipe only through `write_meal_recipe` (`backend/app/services/meal_recipes.py`),
which goes through the `write_recipe_ingredients` funnel, inside a savepoint, refuses
when the meal changed since Claude saw it, and stores the version before for «Annulla».
Tests never run the SDK against the network: `get_claude_client` is injected, the fake
calls the very tool objects production builds, and the production client is tested
against the SDK's real message types. Spec:
`docs/superpowers/specs/2026-11-12-pasti-claude-design.md` §3, §6, §7, §9.

## Conventions worth knowing

- **Never a dead end.** Every failure of an external dependency degrades to manual
  entry. Open Food Facts unreachable, barcode unknown, embedding model missing, an
  ingredient that resolves to nothing: all of these must leave the user able to
  continue, never facing an error page.
- **Tests run on real Postgres**, started through Compose. Not SQLite: the schema
  needs `vector` and `pg_trgm`. No network calls in the suite; Open Food Facts runs
  against recorded fixtures, and the LLM against Messages-shaped responses through a
  mock transport.
- **e5 embeddings need their prefixes.** `query: ` for searches, `passage: ` for
  documents. Omitting them raises no error and silently degrades result quality.
- **Missing nutrients stay missing.** Never default an unknown nutrient to zero:
  zero is a claim, absence is the truth.
- **All colour lives in one `@theme` block** in `frontend/src/index.css`, as design
  tokens Tailwind turns into classes (`--color-brand` → `bg-brand`). The dark theme
  redefines the same variables under `@media (prefers-color-scheme: dark)` in the
  same file, so no screen knows which theme it is in. Text on a solid fill uses the
  matching `on-*` token (`text-on-brand`), never `text-white`: in the dark theme the
  fills get lighter. `src/theme.test.ts` checks every text/background pair in both
  themes; `e2e/style.spec.ts` measures every visible text in both themes on every
  route, the open cook sheet and the ☰ menu — in the state the seed and the test
  leave them (the import queue empty, no AI draft), so a state no test opens is
  not measured. No
  screen names a raw colour: grepping `src/` for `emerald` or `neutral-` must keep
  returning nothing. Shared primitives are in `frontend/src/components/ui/`; look
  there before writing a fourth button variant. Contrast is a constraint, not a
  preference — every text on its background is above 4.5:1, because this app is
  read in a supermarket aisle in daylight.
- Specs and plans are written in Italian, code and identifiers in English.
- **Import brings in recipes, not random new ingredients.** The source catalogue
  is finer than the ingredient registry: `Rigatoni` becomes an alias of `pasta`,
  decided once in `import_terms` and written into `ingredient_aliases`. There is
  no second mapping table, and a wrong decision is corrected from the ingredient
  registry — since S9 a place in the app, «Anagrafica» from the hamburger
  (`frontend/src/features/registry/`), over the single service
  `backend/app/services/registry.py` that `app.cli.fix_registry` also calls. The
  exception is an alias that is half of a queue decision (`source = "import"` with
  its term still in `import_terms`): that one is corrected from the queue, where R11
  shows manual decisions too, so the queue and the registry never disagree.
  **The LLM decides these terms and the queue is the review**: every decision
  carries a `decided_by` — `"ai"` from the LLM, `"human"` for R11's manual
  decisions and for a term a merge re-decides on the winner — and has an undo
  that puts the term, the alias and the materialized recipes back. The undo
  removes the ingredient only when the term owns its deletion
  (`import_terms.created_ingredient`) and nothing else uses it. The decision that
  created the ingredient owns it; when its undo cannot delete because other terms
  still map there, ownership passes to one of them (`_hand_over_creation`), so the
  last undo removes it. A `map` onto an ingredient that already existed never
  deletes it, and decisions from before 2026-09-28 carry `NULL` there and never
  delete either.
  Undo never refuses over recipes already cooked: the ids of their cooking events wait
  in the page's `payload` under `cooking_event_ids`, and `materialize_ready` puts them
  back on the rebuilt recipe (S9 §5.2).

  **A recipe the user edits or deletes is theirs** (R10): the first save of an edit, or
  the deletion, moves its import page to `adopted` in the same transaction, and nothing
  in the import rebuilds it again — undo counts it and leaves it, `materialize_ready` and
  a resync never see it, a merge moves its lines in place, `reread_costs` skips it.
  Deleting archives (`recipes.archived_at`, restored from the tombstone or an old link),
  and every recipe listing excludes archived recipes inside the query that carries the
  limit — except the registry's usage lists (`recipes_using`, `ingredient_usage`), which
  include them on purpose and mark them «(eliminata)»: a correction that a recipe line
  forbids (turning an ingredient non-food) must still see them, or a restored recipe
  would come back with a non-food line. Spec:
  `docs/superpowers/specs/2026-09-27-modifica-ricette-design.md`.

  **A recipe written for a meal stays out of the recipe book** (`recipes.in_book`
  false, decided by Mattia on 2026-11-12) until «Salva nel ricettario». Every book
  listing and search — browse, the cookable count, text and semantic search, the
  categories, the substitution engine's voices — excludes it inside the query that
  carries the limit, through the one expression `in_the_book()` beside the column, the
  same rule as archived recipes; the registry's usage lists include it and mark it
  «(da un pasto)», for the reason they include archived ones, and `reindex` gives it a
  vector for the day it is saved. A meal owns its recipe one to one
  (`meals.recipe_id` is unique): picking from the book makes a copy, and deleting a
  meal archives its recipe unless it is in the book. A live recipe out of the book
  always has a meal: «Togli dal ricettario» refuses one without, and restoring one
  without puts it back in the book. Deleting from the book a recipe that has a meal
  takes it out of the book instead, with «Annulla» (decided by Mattia on 2026-11-21):
  the invariant is kept by the `PATCH`, not by the screen. Spec:
  `docs/superpowers/specs/2026-11-12-pasti-claude-design.md` §4.

  **Claude proposes, Mattia applies.** No Claude tool writes the pantry or the shopping
  list: the meal planning and the dish chat send a change card (`propose_changes`), one
  row per pantry item and per ingredient to buy, with the state it becomes, and Mattia
  ticks, corrects and applies it (`backend/app/services/change_cards.py`). Applying is
  one transaction that locks the card first, through `set_status` and `add_item` — the
  one rule against duplicates in the list — and keeps the state each item had before.
  That is what makes the inverse possible without quantities: when an official meal is
  deleted, replaced or goes «fuori casa», spena itself proposes the inverse card, never
  restoring what another meal still uses or what was bought again; what changed since is
  proposed unticked, with a note, for Mattia to decide.
  A `low` sauce is a started jar: only a row that becomes `finished` brings its list row
  along. That rule is applied to the card as corrected: a list row a pantry row brought
  (`from_pantry_row_ids`) is skipped when no such row becomes `finished` any more, and
  one is added when a corrected row does. Planned meals arrive from a proposal card
  («Metti nella settimana»); their
  recipes are written afterwards by an in-process queue, one meal at a time, each in its
  own transaction, so a plan limit halfway leaves every meal usable by hand. Spec:
  `docs/superpowers/specs/2026-11-12-pasti-claude-design.md` §5.2, §6.2.
  Every write of a meal's recipe that races with the queue — the queue, the dish chat,
  the manual save, «Annulla» — takes the meal row first (`lock_meal`,
  `SELECT … FOR UPDATE`); the edit (`PUT /recipes/{id}`) and the recipe's `PATCH` do not
  yet. A recipe written by hand while Claude's arrives is not lost: the form offers to
  save it in the recipe book.

  A response that cannot be verified against the real registry is never applied — the
  term stays in the queue. Specs are
  `docs/superpowers/specs/2026-09-12-import-ricette-design.md` and
  `docs/superpowers/specs/2026-09-13-llm-openrouter-design.md`; the second
  reverses §8.2 of the first, and is itself superseded for the provider by
  `docs/superpowers/specs/2026-11-21-llm-haiku-design.md`.

## Roadmap beyond v1

Phase 2 was three things; bulk import of an external recipe dataset is done, so
what remains is receipt scanning and nutrient estimation from a label photo.
Phase 3 adds the food diary and micronutrients. Phase 4 adds the suggestion
engine. Two footings for phase 3 are already in place: the `cooking_events`
table exists with no consumer precisely so it has a history to build on, and
`products.nutrients` is already populated from Open Food Facts. Details are in
§4 of the spec.

**`next-steps.md`, at the root, is the single list of what is open** (since
2026-09-29): one line per item with its state — `idea`, `tbd`, `pronto`,
`in corso`, `fatto`, `bloccato` — for a day/night cycle. By day, items are
clarified with Mattia and get a plan in `docs/superpowers/plans/`; only a plan
with no open TBD makes an item `pronto`. By night, `pronto` plans are built
autonomously on `night/<slug>` branches, with a report in `docs/night-reports/`:
no merge, push or deploy without Mattia. `docs/prossimi-passi.md` stays as the
archive of the reasoning — each line of `next-steps.md` points to its section
there ([S3], [Parte X]). Read both before starting anything new, and keep
`next-steps.md` current: anything noticed in passing goes in as `idea` or `tbd`
instead of being done out of scope.
