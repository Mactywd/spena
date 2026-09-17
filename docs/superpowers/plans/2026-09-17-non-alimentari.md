# I non alimentari in lista e in dispensa — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** far entrare detersivo e carta igienica nella lista e nella dispensa, senza
che diventino ingredienti di ricetta.

**Architecture:** un campo `kind` (`food` | `non_food`) sull'anagrafica, che **non si
scrive a mano**: discende dal reparto scelto tramite una funzione pura del dominio,
come `status_for_fill` fa discendere lo stato dalla posizione del cursore. Cinque
guardie impediscono a una voce non alimentare di entrare nel mondo delle ricette, e
quella che tiene sta nell'unico imbuto che costruisce le righe di una ricetta.

**Tech Stack:** FastAPI + SQLAlchemy async + Alembic (Python 3.12), React 19 + Vite +
TypeScript, Postgres 16, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-17-non-alimentari-design.md`

## Global Constraints

- **Specs e commenti in italiano, identificatori in inglese.** È la convenzione di
  `CLAUDE.md` e vale per ogni file toccato qui.
- **I test girano su Postgres vero**, avviato da Compose: `docker compose -f
  docker-compose.yml up -d db`, poi `cd backend && .venv/bin/python -m pytest -q`.
  Mai SQLite: lo schema richiede `vector` e `pg_trgm`.
- **`tsc --noEmit` non è il type check di questo progetto** (settima lezione di
  `CLAUDE.md`: `frontend/tsconfig.json` è solution-style e `--noEmit` esce 0 sempre).
  Il type check è `npm run typecheck` (`tsc -b`) **e** `npm run build`.
- **Frontend:** da `frontend/`, `npx vitest run`.
- **e2e solo sul progetto `spena-e2e`**, mai sul progetto di default:
  `docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d
  --build --wait`, poi `... exec -T backend python -m app.cli.seed`, poi da
  `frontend/`: `E2E_BASE_URL=http://localhost:5174 npm run e2e`, e alla fine
  `docker compose -p spena-e2e ... down -v`. **`down -v` su qualunque altro progetto
  cancella i volumi di sviluppo.**
- **Mai scrivere in `.env`**, né in locale né sul server.
- **Il colore vive solo nei token di `frontend/src/index.css`**: nessuno schermo
  nomina un colore grezzo. I bersagli da toccare sono ≥ 44px.
- **Ogni commit finisce con** `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
- **Il ramo non è distribuibile a metà.** Il Task 2 aggiunge `casa` e `igiene`
  all'enum, e da quel momento fino al Task 3 l'AI dell'import potrebbe classificare
  un termine di GialloZafferano come «igiene». Il Task 3 chiude la finestra: non
  distribuire nulla prima che sia verde.
- **`kind` non compare mai nell'interfaccia.** L'utente sceglie un reparto; l'asse
  discende. Nessuna schermata nomina «alimentare» o «non alimentare» come scelta.

---

## Struttura dei file

**Backend — dominio e modello**
- `app/domain/rules.py` — dichiara `IngredientKind`, `NON_FOOD_CATEGORIES`,
  `kind_for_category`. Modulo puro: nessun import dei modelli.
- `app/db/models/ingredient.py` — la colonna `kind` e i due reparti nuovi.
- `alembic/versions/0007_non_alimentari.py` — la colonna, con backfill e default tolto.

**Backend — scrittura e guardie**
- `app/repositories/ingredients.py` — `create_ingredient` deriva il kind (unico
  scrittore); `search_ingredients` guadagna il filtro.
- `app/repositories/recipes.py` — `NonFoodInRecipe` e la guardia nell'imbuto.
- `app/api/recipes.py` — traduzione in 422.
- `app/api/imports.py` — la decisione della coda rifiuta presto.
- `app/api/ingredients.py` — `?kind=` sulla ricerca.
- `app/services/recipe_import/decide.py` — le categorie offerte all'AI.
- `app/schemas/ingredient.py`, `app/schemas/shopping.py` — il server dice il kind.

**Backend — dati**
- `data/ingredients_seed.json` — 18 voci non alimentari.
- `app/cli/seed.py` — `--solo-ingredienti`.

**Frontend**
- `src/domain/categories.ts` — due costanti al posto di una.
- `src/domain/types.ts` — `kind` su `Ingredient`, `ingredient_kind` su `ShoppingItem`.
- `src/components/IngredientPicker.tsx` — prop `kind`, e la chiave di cache che lo include.
- `src/features/shopping-list/api.ts` — `searchIngredients(query, kind?)`.
- `src/features/recipes/RecipeBookScreen.tsx`, `src/features/ai-draft/AiDraftScreen.tsx`,
  `src/features/recipe-import/TermCard.tsx` — i tre selettori che chiedono solo cibo.
- `src/features/stocking/StockingScreen.tsx` — la scelta del reparto.
- `src/features/stocking/CustomProductForm.tsx` — niente nutrienti per un non alimentare.
- `e2e/non-alimentari.spec.ts` — il giro del detersivo.

**Documenti**
- `CLAUDE.md` (decisione fondante 2), `docs/prossimi-passi.md` (D4, S5).

---

### Task 1: Il dominio — `kind_for_category`

**Files:**
- Modify: `backend/app/domain/rules.py`
- Test: `backend/tests/domain/test_rules.py`

**Interfaces:**
- Consumes: niente.
- Produces: `IngredientKind` (StrEnum: `FOOD = "food"`, `NON_FOOD = "non_food"`),
  `NON_FOOD_CATEGORIES: frozenset[str]`, `kind_for_category(category: str) ->
  IngredientKind`. Tutti importabili da `app.domain.rules`.

Il modulo è puro e **dichiara** i propri enum (come già fa per `PantryStatus` e
`IngredientRole`); modelli, schemi e servizi importano da lui. La direzione opposta
farebbe dipendere il dominio dalle tabelle.

- [ ] **Step 1: Scrivi il test che fallisce**

In coda a `backend/tests/domain/test_rules.py`:

```python
def test_kind_for_category_su_ogni_reparto():
    """Ogni valore dell'enum, non un campione: è la mappa che decide le guardie.

    Scritta per esteso e non come «tutto quel che non è in NON_FOOD_CATEGORIES»,
    che sarebbe la stessa frase della produzione ricopiata nel test — e un test
    che ripete l'implementazione non può vederla sbagliata.
    """
    atteso = {
        IngredientCategory.VERDURA: IngredientKind.FOOD,
        IngredientCategory.FRUTTA: IngredientKind.FOOD,
        IngredientCategory.CARNE: IngredientKind.FOOD,
        IngredientCategory.PESCE: IngredientKind.FOOD,
        IngredientCategory.LATTICINI: IngredientKind.FOOD,
        IngredientCategory.CEREALI: IngredientKind.FOOD,
        IngredientCategory.LEGUMI: IngredientKind.FOOD,
        IngredientCategory.CONDIMENTI: IngredientKind.FOOD,
        IngredientCategory.SPEZIE: IngredientKind.FOOD,
        IngredientCategory.BEVANDE: IngredientKind.FOOD,
        IngredientCategory.DOLCI: IngredientKind.FOOD,
        IngredientCategory.ALTRO: IngredientKind.FOOD,
        IngredientCategory.CASA: IngredientKind.NON_FOOD,
        IngredientCategory.IGIENE: IngredientKind.NON_FOOD,
    }

    assert set(atteso) == set(IngredientCategory), (
        "un reparto nuovo è nato senza che nessuno decidesse da che parte sta"
    )
    for categoria, kind in atteso.items():
        assert kind_for_category(str(categoria)) is kind, categoria


def test_i_reparti_non_alimentari_esistono_davvero():
    """Come per SECONDARY_CATEGORIES: un nome scritto male qui non è un errore
    visibile, è una guardia che smette di scattare in silenzio."""
    assert NON_FOOD_CATEGORIES <= {str(value) for value in IngredientCategory}
```

E aggiungi `IngredientKind`, `NON_FOOD_CATEGORIES` e `kind_for_category` all'import
da `app.domain.rules` in cima al file (l'elenco è già in ordine alfabetico: `IngredientKind`
va dopo `IngredientRole`, `NON_FOOD_CATEGORIES` dopo `LOW_MAX_FILL`, `kind_for_category`
fra `is_satisfied` e `missing_count`).

- [ ] **Step 2: Esegui il test e guardalo fallire**

```bash
cd backend && .venv/bin/python -m pytest tests/domain/test_rules.py -q
```

Atteso: **ImportError** su `IngredientKind` da `app.domain.rules`. Non un fallimento
di asserzione: il modulo non ha ancora niente.

- [ ] **Step 3: Scrivi il dominio**

In `backend/app/domain/rules.py`, subito dopo `class IngredientRole(StrEnum)`:

```python
class IngredientKind(StrEnum):
    """Se una voce dell'anagrafica è cibo o no.

    Non lo sceglie nessuno a mano: discende dal reparto, e l'unico posto che lo
    calcola è `kind_for_category` qui sotto.
    """

    FOOD = "food"
    NON_FOOD = "non_food"
```

e, accanto a `SECONDARY_CATEGORIES` (che sta poco sopra `default_role`):

```python
# I reparti che non sono cibo. La partizione è dichiarata su questa metà e non
# sull'altra perché è la metà che cresce: un reparto alimentare nuovo è cibo per
# omissione, ed è la risposta giusta. Stringhe e non valori dell'enum, come
# SECONDARY_CATEGORIES qui sotto e per la stessa ragione: questo modulo è puro e
# non importa i modelli delle tabelle.
NON_FOOD_CATEGORIES = frozenset({"casa", "igiene"})


def kind_for_category(category: str) -> IngredientKind:
    """A quale mondo appartiene una voce, dedotto dalla sua corsia.

    Il reparto lo sceglie la persona; questo asse discende, e non c'è quindi modo
    di creare una riga che dica insieme «igiene» e «è cibo». Stessa forma di
    `status_for_fill`: là una posizione del cursore si proietta nei tre stati su
    cui ragiona il resto dell'app, qui una corsia del supermercato si proietta
    nell'asse su cui ragionano le guardie delle ricette.
    """
    if category in NON_FOOD_CATEGORIES:
        return IngredientKind.NON_FOOD
    return IngredientKind.FOOD
```

- [ ] **Step 4: Esegui il test e guardalo passare**

```bash
cd backend && .venv/bin/python -m pytest tests/domain/test_rules.py -q
```

Atteso: **fallisce ancora**, ma per un motivo nuovo — `IngredientCategory.CASA` non
esiste. È il Task 2 a crearlo. Verifica che il fallimento sia `AttributeError: CASA`
e non altro, poi passa allo Step 5: il dominio è scritto e il test resta rosso su una
dipendenza dichiarata, non su un difetto.

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/rules.py backend/tests/domain/test_rules.py
git commit -m "$(cat <<'EOF'
feat: il dominio sa se una voce è cibo, e lo deduce dal reparto

`kind_for_category` è una proiezione, non una seconda verità: la sorgente
resta la categoria, come `status_for_fill` proietta la posizione del cursore
nei tre stati. Il test resta rosso finché l'enum non ha i due reparti nuovi.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: I due reparti, nell'enum e nelle due metà del frontend

**Files:**
- Modify: `backend/app/db/models/ingredient.py`
- Modify: `frontend/src/domain/categories.ts`
- Modify: `backend/tests/test_frontend_categories.py`
- Modify: `backend/tests/domain/test_rules.py` (la mappa dei ruoli)
- Modify: `frontend/src/features/ai-draft/AiDraftScreen.tsx` (l'import cambia nome)

**Interfaces:**
- Consumes: `kind_for_category` e `NON_FOOD_CATEGORIES` dal Task 1.
- Produces: `IngredientCategory.CASA = "casa"` e `IngredientCategory.IGIENE =
  "igiene"`; nel frontend `FOOD_CATEGORIES` e `NON_FOOD_CATEGORIES`, entrambe
  `readonly string[]`, esportate da `frontend/src/domain/categories.ts` — la costante
  `INGREDIENT_CATEGORIES` **sparisce**.

**Attenzione — due test esistenti cadono appena l'enum cresce, e vanno sistemati in
questo stesso task:**
1. `backend/tests/test_frontend_categories.py` confronta l'elenco del frontend con
   l'enum: finché `categories.ts` non ha i due reparti, fallisce.
2. `backend/tests/domain/test_rules.py::test_default_role_per_categoria` (riga ~124)
   asserisce che la mappa categoria→ruolo copra **tutti** i valori dell'enum.

- [ ] **Step 1: Aggiungi i due reparti all'enum**

In `backend/app/db/models/ingredient.py`, in coda a `IngredientCategory`:

```python
    DOLCI = "dolci"
    ALTRO = "altro"
    # I due reparti non alimentari. Stanno nello stesso enum e non in uno separato
    # perché sono corsie di supermercato come le altre, e la lista li raggruppa
    # allo stesso modo; a separarli è `kind_for_category` nel dominio, che è
    # l'unica cosa che le guardie leggono.
    CASA = "casa"
    IGIENE = "igiene"
```

- [ ] **Step 2: Esegui i test e guarda cadere i tre**

```bash
cd backend && .venv/bin/python -m pytest tests/domain/test_rules.py tests/test_frontend_categories.py -q
```

Atteso: **tre fallimenti** — `test_kind_for_category_su_ogni_reparto` ora passa
(il Task 1 è completo), `test_default_role_per_categoria` fallisce sull'uguaglianza
degli insiemi, `test_il_frontend_offre_esattamente_le_categorie_del_backend`
fallisce perché il frontend ne elenca dodici.

- [ ] **Step 3: Aggiungi le due righe alla mappa dei ruoli**

In `backend/tests/domain/test_rules.py`, dentro il dizionario di
`test_default_role_per_categoria`, dopo `IngredientCategory.ALTRO`:

```python
        # Non ci arrivano mai: nessuna riga di ricetta può nominare una voce non
        # alimentare (la guardia sta in create_recipe). Stanno qui perché la mappa
        # è totale per costruzione, e perché se un giorno ci arrivassero il ruolo
        # che otterrebbero è questo.
        IngredientCategory.CASA: IngredientRole.PRIMARY,
        IngredientCategory.IGIENE: IngredientRole.PRIMARY,
```

- [ ] **Step 4: Spezza in due l'elenco del frontend**

Sostituisci l'intero contenuto di `frontend/src/domain/categories.ts`:

```ts
/** I reparti dell'anagrafica, nell'ordine in cui si offrono.
 *
 * Sono i valori di `IngredientCategory` nel backend, ed è l'unico posto del
 * frontend che li nomina. Un valore inventato qui non sarebbe un errore visibile:
 * la creazione dell'ingrediente tornerebbe 422 dal backend, su una schermata che
 * fino a quel momento sembrava funzionare. `backend/tests/test_frontend_categories.py`
 * confronta i due elenchi per impedirlo.
 *
 * Sono **due** e non uno perché i reparti non alimentari non vanno offerti
 * dappertutto: chi scrive una ricetta non deve poter mettere un ingrediente in
 * «igiene», perché la guardia del backend rifiuterebbe il salvataggio un istante
 * dopo. Quale metà usare lo decide lo schermo, non questo file.
 */
export const FOOD_CATEGORIES = [
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

export const NON_FOOD_CATEGORIES = ["casa", "igiene"] as const;
```

In `frontend/src/features/ai-draft/AiDraftScreen.tsx` cambia l'import e l'uso:

```tsx
import { FOOD_CATEGORIES } from "../../domain/categories";
```

```tsx
                        {FOOD_CATEGORIES.map((category) => (
```

- [ ] **Step 5: Estendi il presidio che tiene allineati i due lati**

Sostituisci il corpo del test in `backend/tests/test_frontend_categories.py`
(lasciando il docstring del modulo com'è) con:

```python
import re
from pathlib import Path

from app.db.models.ingredient import IngredientCategory
from app.domain.rules import IngredientKind, kind_for_category

REPO_ROOT = Path(__file__).resolve().parents[2]
CATEGORIES_TS = REPO_ROOT / "frontend" / "src" / "domain" / "categories.ts"


def _elenco(nome: str) -> set[str]:
    """Le stringhe di una delle due costanti del file.

    Una regex sola su tutto il file non basta più: con due elenchi direbbe solo
    che l'unione è giusta, e lascerebbe passare «igiene» finito fra gli
    alimentari — cioè proprio il difetto che questo file esiste per impedire.
    """
    contenuto = CATEGORIES_TS.read_text()
    blocco = re.search(rf"export const {nome} = \[(.*?)\]", contenuto, re.DOTALL)
    assert blocco is not None, f"{CATEGORIES_TS}: manca la costante {nome}"
    return set(re.findall(r'"([a-z_]+)"', blocco.group(1)))


def test_il_frontend_offre_esattamente_le_categorie_del_backend():
    tutte = _elenco("FOOD_CATEGORIES") | _elenco("NON_FOOD_CATEGORIES")

    assert tutte == {str(value) for value in IngredientCategory}, (
        f"{CATEGORIES_TS}: l'elenco è {sorted(tutte)}, il backend accetta "
        f"{sorted(str(v) for v in IngredientCategory)}"
    )


def test_le_due_meta_del_frontend_seguono_la_partizione_del_dominio():
    """Non basta che l'unione torni: un reparto nella metà sbagliata verrebbe
    offerto mentre si scrive una ricetta, e il salvataggio lo rifiuterebbe."""
    for nome, atteso in (
        ("FOOD_CATEGORIES", IngredientKind.FOOD),
        ("NON_FOOD_CATEGORIES", IngredientKind.NON_FOOD),
    ):
        for categoria in _elenco(nome):
            assert kind_for_category(categoria) is atteso, f"{nome}: {categoria}"
```

- [ ] **Step 6: Esegui tutto e guardalo verde**

```bash
cd backend && .venv/bin/python -m pytest -q
cd frontend && npx vitest run && npm run typecheck && npm run build
```

Atteso: backend verde; frontend verde (`AiDraftScreen.test.tsx` usa l'elenco tramite
lo schermo, non la costante, quindi non cambia).

- [ ] **Step 7: Commit**

```bash
git add backend/app/db/models/ingredient.py backend/tests/domain/test_rules.py \
  backend/tests/test_frontend_categories.py frontend/src/domain/categories.ts \
  frontend/src/features/ai-draft/AiDraftScreen.tsx
git commit -m "$(cat <<'EOF'
feat: casa e igiene sono reparti, e il frontend li tiene separati dal cibo

L'enum cresce di due valori — niente migrazione, `category` è una String(20)
e non un tipo del database. Nel frontend l'elenco si spezza in due, perché
offrire «igiene» mentre si scrive una ricetta creerebbe una voce che il
salvataggio rifiuta un istante dopo; il presidio che confronta i due lati
ora controlla anche che ciascuna metà stia dalla parte giusta.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: L'AI dell'import non propone i non alimentari

**Files:**
- Modify: `backend/app/services/recipe_import/decide.py:76`
- Test: `backend/tests/services/test_decide_terms.py`

**Interfaces:**
- Consumes: `kind_for_category`, `IngredientKind` (Task 1); `IngredientCategory.CASA`
  e `.IGIENE` (Task 2).
- Produces: `CATEGORIES` in `decide.py` resta un `frozenset[str]`, ma contiene solo i
  reparti alimentari.

**Perché adesso e non dopo:** il Task 2 ha appena allargato l'enum, e `CATEGORIES` è
costruito dall'enum intero. In questo momento l'AI dell'import può classificare un
termine di GialloZafferano come «igiene». Questo task chiude la finestra.

- [ ] **Step 1: Scrivi il test che fallisce**

In coda a `backend/tests/services/test_decide_terms.py`:

```python
def test_le_categorie_offerte_allai_sono_solo_alimentari():
    """Asserito sull'insieme vero, quello che il modulo usa davvero.

    Una copia scritta qui passerebbe anche il giorno in cui la produzione
    smettesse di filtrare: è la prima lezione di CLAUDE.md, un test che guarda
    un oggetto che nessuno chiama.
    """
    from app.services.recipe_import.decide import CATEGORIES

    assert "casa" not in CATEGORIES
    assert "igiene" not in CATEGORIES
    assert "verdura" in CATEGORIES
```


E, subito sotto, il test che guarda il comportamento e non solo la costante. Ricalca
`test_una_risposta_non_verificabile_lascia_il_termine_in_coda`, che sta già in questo
file e usa le stesse finte (`ScriptedLlm`, `llm_create`) e le stesse fixture
(`base`, `aggiungi`, `termine`):

```python
async def test_una_categoria_non_alimentare_proposta_dallai_resta_in_coda(db_session, base):
    """«igiene» è un reparto vero, e qui sta la differenza con il test qui sopra.

    Là la risposta è rifiutata perché «salumi» non esiste; qui è rifiutata perché
    non è cibo. Finché `CATEGORIES` conteneva l'enum intero questa sarebbe stata
    una decisione **applicata**, con una voce non alimentare nata da un ricettario
    e nessuno ad accorgersene.
    """
    (sapone,) = await aggiungi(db_session, termine("Sapone", "k-sapone"))
    finto = ScriptedLlm({"Sapone": llm_create("sapone", "Sapone", "igiene")})

    esito = await decide_terms(db_session, [sapone], client=finto)

    assert esito.applied == 0
    assert esito.still_pending == 1
    assert sapone.decision == TermDecision.PENDING
    assert sapone.decided_by is None
    creati = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "sapone"))
    ).scalars().all()
    assert creati == [], "nessuna voce non alimentare deve nascere da un ricettario"
```

- [ ] **Step 2: Esegui il test e guardalo fallire**

```bash
cd backend && .venv/bin/python -m pytest tests/services/test_decide_terms.py -q
```

Atteso: `assert "casa" not in CATEGORIES` fallisce — l'insieme li contiene entrambi.

- [ ] **Step 3: Restringi l'insieme**

In `backend/app/services/recipe_import/decide.py`, sostituisci la riga 76:

```python
# Solo alimentari: questo modulo decide i termini di un ricettario, e una voce non
# alimentare qui sarebbe un ingrediente che nessuna ricetta potrà mai usare (la
# guardia sta in create_recipe). L'elenco si restringe qui, dove è già costruito,
# e non nel prompt: la stessa costante è insieme l'offerta al modello (riga 124) e
# il controllo della risposta (riga 213), e due elenchi separati si scollerebbero —
# a scollarsi per prima sarebbe la validazione, cioè la metà che protegge.
CATEGORIES = frozenset(
    str(value)
    for value in IngredientCategory
    if kind_for_category(str(value)) is IngredientKind.FOOD
)
```

e aggiungi l'import in cima al file, accanto a quelli del dominio già presenti:

```python
from app.domain.rules import IngredientKind, kind_for_category
```

- [ ] **Step 4: Esegui i test e guardali passare**

```bash
cd backend && .venv/bin/python -m pytest tests/services/ -q
```

Atteso: verde, compresi i test esistenti sulle decisioni dell'AI.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/recipe_import/decide.py backend/tests/services/test_decide_terms.py
git commit -m "$(cat <<'EOF'
fix: l'AI dell'import non può più classificare un termine come non alimentare

CATEGORIES è insieme l'offerta al modello e il controllo della risposta:
restringerlo dove è costruito chiude entrambe le metà con una riga sola, e
tenerne due elenchi separati avrebbe scollato per prima la validazione.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: La colonna `kind`, e l'unico che la scrive

**Files:**
- Modify: `backend/app/db/models/ingredient.py`
- Create: `backend/alembic/versions/0007_non_alimentari.py`
- Modify: `backend/app/repositories/ingredients.py:77-84`
- Test: `backend/tests/db/test_ingredient_schema.py`

**Interfaces:**
- Consumes: `kind_for_category`, `IngredientKind` (Task 1); i due reparti (Task 2).
- Produces: `Ingredient.kind` (`str`, non nullable); `create_ingredient` continua ad
  avere la firma `(session, name, display_name, category)` — **nessun parametro
  nuovo**, il kind non si passa.

- [ ] **Step 1: Scrivi il test che fallisce**

In coda a `backend/tests/db/test_ingredient_schema.py`:

```python
async def test_create_ingredient_deduce_il_kind_dal_reparto(db_session):
    """Il kind non è un parametro: chi crea sceglie il reparto e basta.

    Fallisce se qualcuno aggiunge un argomento `kind` alla firma, che è il modo
    in cui una riga «igiene ma è cibo» potrebbe nascere.
    """
    from app.domain.rules import IngredientKind
    from app.repositories.ingredients import create_ingredient

    cibo = await create_ingredient(db_session, "zucchina", "Zucchina", "verdura")
    non_cibo = await create_ingredient(db_session, "candeggina", "Candeggina", "casa")

    assert cibo.kind == IngredientKind.FOOD
    assert non_cibo.kind == IngredientKind.NON_FOOD
```

- [ ] **Step 2: Esegui il test e guardalo fallire**

```bash
docker compose -f docker-compose.yml up -d db
cd backend && .venv/bin/python -m pytest tests/db/test_ingredient_schema.py -q
```

Atteso: `AttributeError` o `TypeError` su `kind` — la colonna non esiste.

- [ ] **Step 3: Aggiungi la colonna al modello**

In `backend/app/db/models/ingredient.py`, dentro `class Ingredient`, subito dopo
`category`:

```python
    # Se questa voce è cibo. Derivata da `category` e mai scritta a mano: l'unico
    # posto che la calcola è `kind_for_category` nel dominio, e l'unico che la
    # scrive è `create_ingredient`. Memorizzata invece che calcolata a ogni lettura
    # perché le guardie e i filtri sono SQL: `WHERE kind = 'food'` sta in un posto,
    # mentre la partizione dei reparti ricopiata in ogni query si scollerebbe al
    # terzo reparto.
    kind: Mapped[str] = mapped_column(String(10))
```

- [ ] **Step 4: Scrivi la migrazione**

Crea `backend/alembic/versions/0007_non_alimentari.py`:

```python
"""se una voce dell'anagrafica è cibo o no

Revision ID: 0007
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"


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

- [ ] **Step 5: Fai derivare il kind a chi crea**

In `backend/app/repositories/ingredients.py`, sostituisci `create_ingredient`:

```python
async def create_ingredient(
    session: AsyncSession, name: str, display_name: str, category: str
) -> Ingredient:
    """L'unico scrittore di `kind`, che non è un parametro ma una conseguenza.

    La firma non prende il kind di proposito: nessun chiamante — nemmeno l'API —
    deve poter dichiarare che una voce in «igiene» è cibo.
    """
    ingredient = Ingredient(
        name=name.strip().lower(), display_name=display_name.strip(),
        category=category, kind=kind_for_category(category),
    )
    session.add(ingredient)
    await session.flush()
    return ingredient
```

e aggiungi in cima al file:

```python
from app.domain.rules import kind_for_category
```

- [ ] **Step 6: Esegui i test e guardali passare**

```bash
cd backend && .venv/bin/python -m pytest -q
```

Atteso: verde, compreso `tests/db/test_metadata_matches_migrations.py`, che confronta
i modelli con la catena delle migrazioni e fallirebbe se la colonna stesse solo da
una parte.

- [ ] **Step 7: Commit**

```bash
git add backend/app/db/models/ingredient.py backend/alembic/versions/0007_non_alimentari.py \
  backend/app/repositories/ingredients.py backend/tests/db/test_ingredient_schema.py
git commit -m "$(cat <<'EOF'
feat: l'anagrafica sa se una voce è cibo, e non glielo dice il chiamante

La colonna nasce con un default per riempire le righe che ci sono e lo perde
subito: l'unico scrittore torna a essere create_ingredient, e una riga senza
kind fallisce invece di diventare cibo in silenzio.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: La guardia nell'imbuto — una ricetta non nomina un non alimentare

**Files:**
- Modify: `backend/app/repositories/recipes.py:10-35`
- Modify: `backend/app/api/recipes.py:161-195`
- Test: `backend/tests/db/test_recipe_schema.py`, `backend/tests/api/test_recipes.py`,
  `backend/tests/api/test_recipes_create_ingredient.py`

**Interfaces:**
- Consumes: `IngredientKind` (Task 1), `Ingredient.kind` (Task 4).
- Produces: `NonFoodInRecipe(Exception)` con attributo `display_name: str`,
  esportata da `app.repositories.recipes`. La firma di `create_recipe` non cambia.

**Perché qui e non nella rotta:** `create_recipe` è l'**unico** posto del progetto che
costruisce un `RecipeIngredient`, e ha tre chiamanti — `app/api/recipes.py`,
`app/services/recipe_import/materialize.py`, `app/cli/seed.py`. Una guardia nella rotta
ne coprirebbe uno solo. E il buco vero non è la creazione per nome (che crea sempre con
una categoria alimentare) ma `match_name`, che un «sapone» scritto in una riga di
ricetta lo **aggancia** alla voce non alimentare esistente tramite il suo alias.

- [ ] **Step 1: Scrivi i tre test che falliscono**

In coda a `backend/tests/db/test_recipe_schema.py`:

```python
async def test_una_ricetta_non_puo_nominare_una_voce_non_alimentare(db_session):
    """La guardia sta nell'imbuto, quindi vale anche per il seme e per l'import.

    E non scrive niente: se sollevasse dopo aver aggiunto la ricetta, resterebbe
    un titolo senza ingredienti a seconda di dove il chiamante fa il commit.
    """
    import pytest
    from sqlalchemy import select

    from app.db.models.recipe import Recipe
    from app.repositories.ingredients import create_ingredient
    from app.repositories.recipes import NonFoodInRecipe, create_recipe

    sapone = await create_ingredient(db_session, "sapone", "Sapone", "igiene")

    with pytest.raises(NonFoodInRecipe) as caduta:
        await create_recipe(
            db_session,
            title="Pasta al sapone", description=None, instructions="1. no",
            servings=2, source="manual", source_ref=None,
            ingredients=[(sapone.id, "primary", None, None)],
            embedding=None,
        )

    assert caduta.value.display_name == "Sapone"
    rimaste = (
        await db_session.execute(select(Recipe).where(Recipe.title == "Pasta al sapone"))
    ).scalars().all()
    assert rimaste == []
```

In coda a `backend/tests/api/test_recipes.py`:

```python
async def test_salvare_una_ricetta_con_una_voce_non_alimentare_e_un_422(
    logged_client, db_session
):
    from app.repositories.ingredients import create_ingredient

    sapone = await create_ingredient(db_session, "sapone", "Sapone", "igiene")
    await db_session.commit()

    response = await logged_client.post("/api/v1/recipes", json={
        "title": "Pasta al sapone", "instructions": "1. no", "servings": 2,
        "source": "manual",
        "ingredients": [{"ingredient_id": str(sapone.id), "role": "primary"}],
    })

    assert response.status_code == 422
    # il messaggio nomina la voce: su una ricetta di dodici righe «una voce non
    # alimentare» non dice quale togliere
    assert "Sapone" in response.json()["detail"]
```

In coda a `backend/tests/api/test_recipes_create_ingredient.py`:

```python
async def test_un_nome_che_e_alias_di_una_voce_non_alimentare_non_passa(
    logged_client, db_session
):
    """Il buco vero, e il motivo per cui la guardia sta nell'imbuto.

    Questa riga non *crea* niente — la creazione per nome usa sempre una categoria
    alimentare — ma `match_name` la aggancia alla voce non alimentare tramite il
    suo alias, e senza la guardia la ricetta si salverebbe.
    """
    from app.repositories.ingredients import add_alias, create_ingredient

    sapone = await create_ingredient(
        db_session, name="sapone per le mani", display_name="Sapone per le mani",
        category="igiene",
    )
    await add_alias(db_session, sapone.id, "sapone", source="seed")
    await db_session.commit()

    response = await logged_client.post("/api/v1/recipes", json={
        "title": "Pasta al sapone", "instructions": "1. no", "servings": 2,
        "source": "ai",
        "ingredients": [{"name": "sapone", "category": "condimenti", "role": "primary"}],
    })

    assert response.status_code == 422
    assert "Sapone per le mani" in response.json()["detail"]
```

- [ ] **Step 2: Esegui i test e guardali fallire**

```bash
docker compose -f docker-compose.yml up -d db
cd backend && .venv/bin/python -m pytest tests/db/test_recipe_schema.py tests/api/test_recipes.py tests/api/test_recipes_create_ingredient.py -q
```

Atteso: il primo fallisce con `ImportError` su `NonFoodInRecipe`; gli altri due
falliscono con **201 invece di 422** — cioè la ricetta si salva. Guarda bene il terzo:
è il difetto che questo lavoro esiste per chiudere, e vederlo passare adesso è la
prova che il test ha qualcosa da dire.

- [ ] **Step 3: Scrivi la guardia nell'imbuto**

In `backend/app/repositories/recipes.py`, in cima ai import:

```python
from app.db.models.ingredient import Ingredient
from app.domain.rules import IngredientKind
```

Subito prima di `create_recipe`:

```python
class NonFoodInRecipe(Exception):
    """Una riga di ricetta punta a una voce non alimentare.

    Porta il nome visibile della voce perché il messaggio all'utente deve dire
    **quale**: su una ricetta di dodici righe, «una voce non alimentare» non è
    un'indicazione, è un indovinello.
    """

    def __init__(self, display_name: str) -> None:
        super().__init__(display_name)
        self.display_name = display_name
```

E in testa al corpo di `create_recipe`, prima che `recipe` esista:

```python
    # Prima di scrivere qualunque cosa. Una query sola per tutta la ricetta, e sul
    # `kind` invece che sulla lista dei reparti: la partizione vive in un posto
    # solo (`kind_for_category`), e qui si legge il suo risultato.
    #
    # Solleva, e non salta la riga: se le guardie a monte tengono — la decisione
    # della coda e l'AI dell'import — questa non è raggiungibile né dalla
    # materializzazione né dal seme. È l'ultima linea, e ci si arriva solo perché
    # qualcosa più in alto ha un buco; una materializzazione che saltasse la riga
    # in silenzio produrrebbe una ricetta mutilata che nessuno ha chiesto.
    if ingredients:
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
```

- [ ] **Step 4: Traduci in 422 nella rotta**

In `backend/app/api/recipes.py`, aggiungi `NonFoodInRecipe` all'import da
`app.repositories.recipes` e, nel blocco `try` del salvataggio, **prima** di
`except IntegrityError`:

```python
    except NonFoodInRecipe as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"«{exc.display_name}» non è un alimento: una ricetta non può averlo fra "
            "gli ingredienti. Toglilo dalla riga, poi salva.",
        ) from exc
```

- [ ] **Step 5: Esegui tutto e guardalo passare**

```bash
cd backend && .venv/bin/python -m pytest -q
```

Atteso: verde, 483 + i nuovi.

- [ ] **Step 6: Commit**

```bash
git add backend/app/repositories/recipes.py backend/app/api/recipes.py \
  backend/tests/db/test_recipe_schema.py backend/tests/api/test_recipes.py \
  backend/tests/api/test_recipes_create_ingredient.py
git commit -m "$(cat <<'EOF'
feat: una ricetta non può nominare una voce non alimentare

La guardia sta in create_recipe e non nella rotta: è l'unico posto che
costruisce una riga di ricetta, e ha tre chiamanti. Il buco vero non era la
creazione per nome — che crea sempre alimentare — ma `match_name`, che un
«sapone» scritto in una riga lo aggancia alla voce non alimentare via alias.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: La coda dell'import rifiuta al momento della scelta

**Files:**
- Modify: `backend/app/api/imports.py:205-240`
- Test: `backend/tests/api/test_imports.py`

**Interfaces:**
- Consumes: `NON_FOOD_CATEGORIES`, `IngredientKind` (Task 1); `Ingredient.kind` (Task 4).
- Produces: niente di nuovo; due rifiuti 422 in più sulla rotta della decisione.

**Perché presto e non alla materializzazione:** la rotta chiama `materialize_ready`
nella **stessa richiesta**, e quel ciclo non protegge le singole ricette — una riga
non alimentare farebbe fallire la materializzazione di **tutto il lotto pronto**, non
solo della ricetta colpevole, dopo che la decisione è già stata scritta.

- [ ] **Step 1: Scrivi i due test che falliscono**

In coda a `backend/tests/api/test_imports.py`, che è dove vivono i test della
**decisione umana** (`test_imports_decide.py` è la rotta di massa dell'AI, un'altra
cosa). Usa la fixture `in_attesa` già presente, che mette in coda il termine
«Bottarga», e la rotta `POST /api/v1/imports/terms/{id}/decision`:

```python
async def test_collegare_un_termine_a_una_voce_non_alimentare_e_un_422(
    logged_client, db_session, in_attesa
):
    from app.repositories.ingredients import create_ingredient

    sapone = await create_ingredient(db_session, "sapone", "Sapone", "igiene")
    termine = (
        await db_session.execute(
            select(ImportTerm).where(ImportTerm.display_name == "Bottarga")
        )
    ).scalars().one()

    response = await logged_client.post(
        f"/api/v1/imports/terms/{termine.id}/decision",
        json={"action": "map", "ingredient_id": str(sapone.id)},
    )

    assert response.status_code == 422
    assert "Sapone" in response.json()["detail"]
    await db_session.refresh(termine)
    assert termine.decision == TermDecision.PENDING


async def test_creare_una_voce_non_alimentare_da_un_termine_e_un_422(
    logged_client, db_session, in_attesa
):
    termine = (
        await db_session.execute(
            select(ImportTerm).where(ImportTerm.display_name == "Bottarga")
        )
    ).scalars().one()

    response = await logged_client.post(
        f"/api/v1/imports/terms/{termine.id}/decision",
        json={"action": "create", "name": "sapone", "display_name": "Sapone",
              "category": "igiene"},
    )

    assert response.status_code == 422
    creati = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "sapone"))
    ).scalars().all()
    assert creati == []
    await db_session.refresh(termine)
    assert termine.decision == TermDecision.PENDING
```

`select`, `Ingredient`, `ImportTerm` e `TermDecision` sono già importati in cima a
quel file.

- [ ] **Step 2: Esegui i test e guardali fallire**

```bash
cd backend && .venv/bin/python -m pytest tests/api/test_imports.py -q
```

Atteso: entrambi falliscono con **200** — la decisione viene accettata.

- [ ] **Step 3: Rifiuta alla scelta**

In `backend/app/api/imports.py`, nel ramo `action == "map"`, subito dopo il controllo
`if ingredient is None`:

```python
            # Presto, e non alla materializzazione: questa rotta chiama
            # materialize_ready nella stessa richiesta, e quel ciclo non protegge
            # le singole ricette — una riga non alimentare farebbe fallire tutto
            # il lotto pronto, non solo la ricetta colpevole, con la decisione già
            # scritta. Un rifiuto a fine lotto è il vicolo cieco peggiore.
            if ingredient.kind == IngredientKind.NON_FOOD:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"«{ingredient.display_name}» non è un alimento: un termine di "
                    "ricetta non può collegarsi a una voce non alimentare. "
                    "Scegline un'altra, oppure ignora il termine.",
                )
```

e nel ramo `create`, subito dopo il controllo su `name` e `category`:

```python
            if payload.category in NON_FOOD_CATEGORIES:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"«{payload.category}» non è un reparto alimentare: un termine "
                    "di ricetta non può creare una voce non alimentare. "
                    "Scegli un altro reparto, oppure ignora il termine.",
                )
```

Aggiungi in cima al file:

```python
from app.domain.rules import NON_FOOD_CATEGORIES, IngredientKind
```

Entrambi i messaggi nominano una via d'uscita — *ignora il termine* — perché per un
termine che non è cibo quella è l'azione giusta, e un rifiuto senza uscita è un
vicolo cieco (convenzione di `CLAUDE.md`).

- [ ] **Step 4: Esegui i test e guardali passare**

```bash
cd backend && .venv/bin/python -m pytest tests/api/ -q
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/imports.py backend/tests/api/test_imports.py
git commit -m "$(cat <<'EOF'
fix: la coda dell'import rifiuta il non alimentare quando lo scegli, non a fine lotto

La rotta materializza nella stessa richiesta e il ciclo non protegge le
singole ricette: senza questo, un termine collegato a «sapone» avrebbe fatto
fallire la materializzazione di tutto il lotto pronto, con la decisione già
scritta. Entrambi i rifiuti nominano l'uscita: ignora il termine.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Il server dice il kind, e sa filtrarci

**Files:**
- Modify: `backend/app/repositories/ingredients.py:11-75`
- Modify: `backend/app/api/ingredients.py:18-24`
- Modify: `backend/app/schemas/ingredient.py`
- Modify: `backend/app/schemas/shopping.py`, `backend/app/api/shopping.py:24-35`
- Test: `backend/tests/api/test_ingredients.py`, `backend/tests/api/test_shopping.py`

**Interfaces:**
- Consumes: `IngredientKind` (Task 1), `Ingredient.kind` (Task 4).
- Produces: `search_ingredients(session, query, limit=10, kind: IngredientKind | None
  = None)`; `GET /api/v1/ingredients/search?q=…&kind=food`; `IngredientOut.kind: str`;
  `ShoppingItemOut.ingredient_kind: str | None`.

`kind=None` significa «tutti» ed è il comportamento di oggi: il filtro è **esplicito
in chi lo vuole**, perché un default che esclude silenziosamente è il modo in cui la
lista della spesa smetterebbe di suggerire il detersivo senza che nessun test lo veda.

- [ ] **Step 1: Scrivi i test che falliscono**

In coda a `backend/tests/api/test_ingredients.py`:

```python
async def test_la_ricerca_filtra_per_kind_solo_se_glielo_chiedi(logged_client, db_session):
    """Senza parametro si vede tutto: è la lista della spesa, dove il detersivo
    deve comparire. Con `kind=food` no: è il ricettario."""
    from app.repositories.ingredients import create_ingredient

    await create_ingredient(db_session, "detersivo per i piatti", "Detersivo per i piatti", "casa")
    await create_ingredient(db_session, "detersivo alimentare finto", "Dado", "condimenti")
    await db_session.commit()

    tutti = (await logged_client.get("/api/v1/ingredients/search?q=deter")).json()
    assert "Detersivo per i piatti" in [i["display_name"] for i in tutti]

    solo_cibo = (await logged_client.get("/api/v1/ingredients/search?q=deter&kind=food")).json()
    assert "Detersivo per i piatti" not in [i["display_name"] for i in solo_cibo]


async def test_la_ricerca_dice_il_kind_di_ogni_voce(logged_client, db_session):
    """Il frontend non lo calcola: lo legge. La partizione dei reparti vive nel
    backend, e ricopiarla nel client sarebbe la seconda copia che si scolla."""
    from app.repositories.ingredients import create_ingredient

    await create_ingredient(db_session, "candeggina", "Candeggina", "casa")
    await db_session.commit()

    trovati = (await logged_client.get("/api/v1/ingredients/search?q=cande")).json()
    assert trovati[0]["kind"] == "non_food"
```

In coda a `backend/tests/api/test_shopping.py`:

```python
async def test_una_voce_di_lista_porta_il_kind_del_suo_ingrediente(logged_client, db_session):
    """Serve alla sistemazione della spesa, che deve sapere se nascondere i campi
    dei nutrienti — e deve saperlo senza ricalcolare la partizione nel client."""
    from app.repositories.ingredients import create_ingredient

    candeggina = await create_ingredient(db_session, "candeggina", "Candeggina", "casa")
    await db_session.commit()

    await logged_client.post(
        "/api/v1/shopping-list",
        json={"raw_text": "candeggina", "ingredient_id": str(candeggina.id)},
    )
    voci = (await logged_client.get("/api/v1/shopping-list")).json()

    assert voci[0]["ingredient_kind"] == "non_food"
```

- [ ] **Step 2: Esegui i test e guardali fallire**

```bash
cd backend && .venv/bin/python -m pytest tests/api/test_ingredients.py tests/api/test_shopping.py -q
```

Atteso: `KeyError: 'kind'` e `KeyError: 'ingredient_kind'`, e il filtro ignorato.

- [ ] **Step 3: Filtra nel repository**

In `backend/app/repositories/ingredients.py`, cambia la firma e aggiungi il `where`
dopo la costruzione di `statement` (prima di `.limit(limit)` — il modo più semplice è
aggiungere il filtro alla `select(Ingredient)` iniziale):

```python
async def search_ingredients(
    session: AsyncSession, query: str, limit: int = 10,
    kind: IngredientKind | None = None,
) -> list[Ingredient]:
```

e, dentro, subito dopo `statement = (...)`:

```python
    # `None` vuol dire «tutti», ed è il comportamento di sempre: il filtro lo
    # chiede chi lo vuole. Un default che esclude sarebbe il modo in cui la lista
    # della spesa smette di suggerire il detersivo senza che nessun test lo veda.
    if kind is not None:
        statement = statement.where(Ingredient.kind == kind)
```

Aggiungi l'import `from app.domain.rules import IngredientKind, kind_for_category`
(la seconda c'è già dal Task 4).

- [ ] **Step 4: Apri il parametro sulla rotta e di' il kind negli schemi**

In `backend/app/api/ingredients.py`:

```python
@router.get("/search", response_model=list[IngredientOut])
async def search(
    q: str = Query(min_length=1), limit: int = Query(default=10, le=50),
    kind: IngredientKind | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[IngredientOut]:
    found = await search_ingredients(session, q, limit, kind=kind)
    return [IngredientOut.model_validate(i) for i in found]
```

con `from app.domain.rules import IngredientKind` in cima.

In `backend/app/schemas/ingredient.py`, dentro `IngredientOut`, dopo `category`:

```python
    # detto dal server e non calcolato dal client: la partizione dei reparti vive
    # in `kind_for_category`, e una seconda copia nel frontend si scollerebbe
    kind: str
```

In `backend/app/schemas/shopping.py`, dentro `ShoppingItemOut`, dopo
`ingredient_category`:

```python
    ingredient_kind: str | None
```

e in `backend/app/api/shopping.py`, dentro `_to_out`, dopo `ingredient_category`:

```python
        ingredient_kind=item.ingredient.kind if item.ingredient else None,
```

- [ ] **Step 5: Esegui tutto e guardalo passare**

```bash
cd backend && .venv/bin/python -m pytest -q
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/repositories/ingredients.py backend/app/api/ingredients.py \
  backend/app/schemas/ingredient.py backend/app/schemas/shopping.py \
  backend/app/api/shopping.py backend/tests/api/test_ingredients.py \
  backend/tests/api/test_shopping.py
git commit -m "$(cat <<'EOF'
feat: la ricerca sa filtrare per kind, e ogni voce dice il suo

Il filtro è esplicito in chi lo vuole: `None` resta «tutti», perché un
default che esclude è il modo in cui la lista della spesa smetterebbe di
suggerire il detersivo senza che nessun test lo veda.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Il seme delle diciotto voci, e `--solo-ingredienti`

**Files:**
- Modify: `data/ingredients_seed.json`
- Modify: `backend/app/cli/seed.py:142-158`
- Test: `backend/tests/test_seed.py`

**Interfaces:**
- Consumes: i due reparti (Task 2), la derivazione del kind (Task 4).
- Produces: 187 voci nel seme; `python -m app.cli.seed --solo-ingredienti`.

- [ ] **Step 1: Scrivi il test che fallisce**

In coda a `backend/tests/test_seed.py`:

```python
def test_il_seme_porta_i_non_alimentari():
    from app.domain.rules import NON_FOOD_CATEGORIES

    voci = json.loads((DATA / "ingredients_seed.json").read_text())
    non_alimentari = [v for v in voci if v["category"] in NON_FOOD_CATEGORIES]

    assert len(non_alimentari) >= 18
    nomi = {v["name"] for v in non_alimentari}
    assert {"detersivo per i piatti", "carta igienica", "sacchi per la spazzatura"} <= nomi


def test_nessun_alias_del_seme_e_ripetuto_fra_due_voci():
    """L'invariante che `remember_alias` difende a runtime — «un alias già preso da
    un altro ingrediente non si ruba» — ma il seme scrive gli alias direttamente,
    senza passare di lì. Due voci che rispondono alla stessa parola sono un
    autocomplete che dà due risposte a una domanda sola.
    """
    import collections

    voci = json.loads((DATA / "ingredients_seed.json").read_text())
    conteggio = collections.Counter(
        alias for voce in voci for alias in voce.get("aliases", [])
    )
    ripetuti = {alias: n for alias, n in conteggio.items() if n > 1}

    assert ripetuti == {}, f"alias su più voci: {ripetuti}"
```

`DATA` (la cartella `data/` del repository) e l'import di `json` sono già in cima a
`backend/tests/test_seed.py`.

- [ ] **Step 2: Esegui i test e guardali fallire**

```bash
cd backend && .venv/bin/python -m pytest tests/test_seed.py -q
```

Atteso: il primo fallisce (`0 >= 18`); il secondo dovrebbe **già passare** sulle 169
voci esistenti — se fallisce, hai trovato un difetto vero nell'anagrafica del seme:
segnalalo e correggi l'alias duplicato prima di andare avanti.

- [ ] **Step 3: Aggiungi le diciotto voci**

In coda all'array di `data/ingredients_seed.json` (prima della `]` finale, con la
virgola sull'ultima voce esistente):

```json
  { "name": "carta igienica", "display_name": "Carta igienica", "category": "igiene",
    "aliases": ["carta igenica", "rotoloni"] },
  { "name": "fazzoletti di carta", "display_name": "Fazzoletti di carta", "category": "igiene",
    "aliases": ["fazzoletti", "fazzolettini"] },
  { "name": "sapone per le mani", "display_name": "Sapone per le mani", "category": "igiene",
    "aliases": ["sapone", "sapone liquido"] },
  { "name": "bagnoschiuma", "display_name": "Bagnoschiuma", "category": "igiene",
    "aliases": ["docciaschiuma"] },
  { "name": "shampoo", "display_name": "Shampoo", "category": "igiene", "aliases": [] },
  { "name": "dentifricio", "display_name": "Dentifricio", "category": "igiene", "aliases": [] },
  { "name": "deodorante", "display_name": "Deodorante", "category": "igiene", "aliases": [] },
  { "name": "detersivo per i piatti", "display_name": "Detersivo per i piatti", "category": "casa",
    "aliases": ["detersivo piatti", "sapone per i piatti"] },
  { "name": "detersivo per la lavatrice", "display_name": "Detersivo per la lavatrice",
    "category": "casa", "aliases": ["detersivo lavatrice", "detersivo per il bucato"] },
  { "name": "ammorbidente", "display_name": "Ammorbidente", "category": "casa", "aliases": [] },
  { "name": "sgrassatore", "display_name": "Sgrassatore", "category": "casa", "aliases": [] },
  { "name": "candeggina", "display_name": "Candeggina", "category": "casa",
    "aliases": ["varechina"] },
  { "name": "spugne per i piatti", "display_name": "Spugne per i piatti", "category": "casa",
    "aliases": ["spugne", "spugnette"] },
  { "name": "sacchi per la spazzatura", "display_name": "Sacchi per la spazzatura",
    "category": "casa", "aliases": ["sacchi spazzatura", "sacchetti spazzatura"] },
  { "name": "carta da cucina", "display_name": "Carta da cucina", "category": "casa",
    "aliases": ["carta assorbente", "scottex"] },
  { "name": "pellicola trasparente", "display_name": "Pellicola trasparente", "category": "casa",
    "aliases": ["pellicola"] },
  { "name": "carta stagnola", "display_name": "Carta stagnola", "category": "casa",
    "aliases": ["stagnola", "carta alluminio"] },
  { "name": "carta forno", "display_name": "Carta forno", "category": "casa",
    "aliases": ["carta da forno"] }
```

«Detersivo» da solo **non è alias di nessuno dei due detersivi**, di proposito:
sarebbe una risposta sola a una domanda ambigua. L'autocomplete li mostra comunque
entrambi digitando quella parola, perché la ricerca trigram lavora anche sul nome.

- [ ] **Step 4: Aggiungi `--solo-ingredienti`**

In `backend/app/cli/seed.py`, sostituisci `main`:

```python
async def main() -> None:
    # `--solo-ingredienti` per la messa in produzione di un'anagrafica allargata:
    # il seme è idempotente e salta per titolo anche le ricette, ma «salta quelle
    # che ci sono» non è «non ne rimette»: una ricetta del seme cancellata a mano
    # tornerebbe. R4 prevede proprio di cancellarle, quindi la trappola è vicina.
    solo_ingredienti = "--solo-ingredienti" in sys.argv
    data_dir = find_data_dir()
    async with SessionLocal() as session:
        ingredients = await load_ingredients(session, data_dir / INGREDIENTS_FILE)
        if solo_ingredienti:
            await session.commit()
            print(f"caricati {ingredients} ingredienti (ricette non toccate)")
            return
        recipes = await load_recipes(session, data_dir / RECIPES_FILE)
        await session.commit()
    print(f"caricati {ingredients} ingredienti e {recipes.created} ricette")
    if recipes.without_embedding:
        # senza questa riga un ricettario senza vettori sembra identico a uno sano
        print(
            f"{recipes.without_embedding} ricette salvate senza vettore: la ricerca "
            "resta solo testuale. Vedi l'avviso qui sopra per accendere la semantica; "
            "queste ricette non riceveranno il vettore rieseguendo il seme, che è "
            "idempotente."
        )
```

con `import sys` in cima al file.

- [ ] **Step 5: Esegui i test e guardali passare**

```bash
cd backend && .venv/bin/python -m pytest -q
```

Atteso: verde. `test_every_seed_category_is_a_known_one` copre già i due reparti nuovi
(l'enum li conosce dal Task 2).

- [ ] **Step 6: Commit**

```bash
git add data/ingredients_seed.json backend/app/cli/seed.py backend/tests/test_seed.py
git commit -m "$(cat <<'EOF'
feat: diciotto non alimentari nel seme, e un seme che sa caricare solo l'anagrafica

«Detersivo» da solo non è alias di nessuno dei due: sarebbe una risposta sola
a una domanda ambigua, e la ricerca trigram li mostra comunque entrambi.
Il nuovo test sugli alias ripetuti difende sul file l'invariante che
`remember_alias` difende a runtime, e che il seme aggirava scrivendo diretto.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: I tre selettori del mondo ricette chiedono solo cibo

**Files:**
- Modify: `frontend/src/domain/types.ts`
- Modify: `frontend/src/features/shopping-list/api.ts:27-29`
- Modify: `frontend/src/components/IngredientPicker.tsx`
- Modify: `frontend/src/features/recipes/RecipeBookScreen.tsx:224-228`
- Modify: `frontend/src/features/ai-draft/AiDraftScreen.tsx:447`
- Modify: `frontend/src/features/recipe-import/TermCard.tsx:83`
- Test: `frontend/src/components/IngredientPicker.test.tsx` (nuovo)

**Interfaces:**
- Consumes: `?kind=food` sulla rotta e `kind` su `IngredientOut` (Task 7).
- Produces: `searchIngredients(query: string, kind?: "food")`; prop opzionale
  `kind?: "food"` su `IngredientPicker`.

**Attenzione alla chiave di cache.** `IngredientPicker` e `AddItemField` usano
entrambi `queryKey: ["ingredients", termine]`. Senza il `kind` nella chiave, la
risposta filtrata e quella non filtrata **si sovrascrivono a vicenda** in react-query:
la dispensa smetterebbe di vedere il detersivo solo perché il ricettario ha cercato
la stessa parola un momento prima. È un difetto che nessun test di un componente solo
può vedere.

- [ ] **Step 1: Scrivi il test che fallisce**

Crea `frontend/src/components/IngredientPicker.test.tsx`. **`stubRoutedFetch` non è
un helper condiviso**: ogni file di test ne definisce uno suo (tre copie oggi, in
`PantryScreen.test.tsx`, `RecipeBookScreen.test.tsx`, `StockingScreen.test.tsx`).
Copia quello di `frontend/src/features/pantry/PantryScreen.test.tsx:25` insieme al
modo in cui quel file costruisce il `QueryClient` e monta i componenti — e usa **un
solo** `QueryClient` per i due selettori, perché è la cache condivisa la cosa sotto
esame:

```tsx
it("chiede al server solo il cibo quando glielo si dice, e lo mette nella chiave", async () => {
  // due montaggi nello stesso QueryClient, stessa parola cercata: senza il kind
  // nella chiave il secondo leggerebbe la risposta del primo, e il filtro
  // diventerebbe una decorazione
  const chiamate: string[] = [];
  stubRoutedFetch((path) => {
    chiamate.push(path);
    return [[], 200];
  });

  render(
    <>
      <IngredientPicker label="Aggiungi in dispensa" failureNote="x" onPick={() => {}} />
      <IngredientPicker label="Contiene ingredienti" failureNote="x" kind="food" onPick={() => {}} />
    </>
  );
  fireEvent.change(screen.getByLabelText("Aggiungi in dispensa"), { target: { value: "deter" } });
  fireEvent.change(screen.getByLabelText("Contiene ingredienti"), { target: { value: "deter" } });

  await waitFor(() => expect(chiamate.length).toBe(2));
  expect(chiamate.some((c) => c.includes("kind=food"))).toBe(true);
  expect(chiamate.some((c) => !c.includes("kind="))).toBe(true);
});
```

- [ ] **Step 2: Esegui il test e guardalo fallire**

```bash
cd frontend && npx vitest run src/components/IngredientPicker.test.tsx
```

Atteso: una sola chiamata invece di due (le due richieste condividono la chiave), e
nessuna con `kind=food`.

- [ ] **Step 3: Porta il kind fino alla rotta**

`frontend/src/domain/types.ts`, dentro `Ingredient` dopo `category`:

```ts
  /** Se questa voce è cibo. Lo dice il server: la partizione dei reparti vive in
   * `kind_for_category`, nel dominio del backend. */
  kind: "food" | "non_food";
```

e dentro `ShoppingItem` dopo `ingredient_category`:

```ts
  ingredient_kind: "food" | "non_food" | null;
```

`frontend/src/features/shopping-list/api.ts`:

```ts
export function searchIngredients(query: string, kind?: "food") {
  const params = new URLSearchParams({ q: query });
  // solo chi vuole il filtro lo manda: senza parametro il server risponde tutto,
  // che è quel che vogliono la lista, la sistemazione e la dispensa
  if (kind) params.set("kind", kind);
  return apiFetch<Ingredient[]>(`/ingredients/search?${params}`);
}
```

`frontend/src/components/IngredientPicker.tsx` — aggiungi la prop e mettila **nella
chiave**:

```tsx
  /** Restringe i suggerimenti al cibo. Lo passano i tre selettori del mondo
   * ricette, dove una voce non alimentare verrebbe rifiutata al salvataggio. */
  kind,
```

```tsx
  kind?: "food";
```

```tsx
  const { data: found = [], isError } = useQuery({
    // il kind sta nella chiave: senza, la risposta filtrata e quella non filtrata
    // si sovrascriverebbero a vicenda sulla stessa parola cercata, e la dispensa
    // smetterebbe di vedere il detersivo perché il ricettario ha cercato prima
    queryKey: ["ingredients", debounced, kind ?? "tutti"],
    queryFn: () => searchIngredients(debounced, kind),
    enabled: ready,
  });
```

- [ ] **Step 4: Passa `kind="food"` nei tre selettori del mondo ricette**

`RecipeBookScreen.tsx`:

```tsx
      <IngredientPicker
        label="Contiene ingredienti"
        failureNote="Puoi comunque cercare per parole qui sopra."
        kind="food"
        onPick={addIngredient}
      />
```

`AiDraftScreen.tsx` e `TermCard.tsx`: aggiungi `kind="food"` all'elenco delle prop
del loro `<IngredientPicker>`, senza toccare il resto.

- [ ] **Step 5: Esegui tutto e guardalo passare**

```bash
cd frontend && npx vitest run && npm run typecheck && npm run build
```

Atteso: verde. Il type check è `tsc -b`: `tsc --noEmit` **non** è il type check di
questo progetto (settima lezione di `CLAUDE.md`).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/domain/types.ts frontend/src/features/shopping-list/api.ts \
  frontend/src/components/IngredientPicker.tsx frontend/src/components/IngredientPicker.test.tsx \
  frontend/src/features/recipes/RecipeBookScreen.tsx \
  frontend/src/features/ai-draft/AiDraftScreen.tsx \
  frontend/src/features/recipe-import/TermCard.tsx
git commit -m "$(cat <<'EOF'
feat: i selettori del mondo ricette non offrono i non alimentari

Il kind sta nella chiave di react-query, non solo nella richiesta: senza,
la risposta filtrata e quella non filtrata si sovrascrivono sulla stessa
parola, e la dispensa smette di vedere il detersivo perché il ricettario ha
cercato un momento prima. Nessun test di un componente solo lo vedrebbe.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: La scelta del reparto quando sistemi la spesa

**Files:**
- Modify: `frontend/src/features/stocking/StockingScreen.tsx:16-150`
- Test: `frontend/src/features/stocking/StockingScreen.test.tsx`

**Interfaces:**
- Consumes: `FOOD_CATEGORIES`, `NON_FOOD_CATEGORIES` (Task 2).
- Produces: niente per gli altri task.

- [ ] **Step 1: Scrivi il test che fallisce**

In coda a `frontend/src/features/stocking/StockingScreen.test.tsx`, ricalcando la
forma dei test già presenti (gli stub delle rotte e il rendering dello schermo):

Il test da scrivere è il gemello di quello già presente in fondo al file — «se
nessun ingrediente corrisponde lo dice, e lascia crearlo» — e usa lo stesso stub, la
stessa voce spaiata `UNMATCHED` e lo stesso `postBody`:

```tsx
  it("il reparto di una voce nuova si sceglie, e fra i reparti c'è anche il non alimentare", async () => {
    const spy = stubRoutedFetch((path, init) => {
      if (path.includes("/ingredients/search")) return [[]];
      if (path.endsWith("/ingredients") && init?.method === "POST") return [STRANGE, 201];
      return [UNMATCHED];
    });

    renderScreen();
    await screen.findByText("cosa strana");

    const reparto = await screen.findByLabelText("Reparto");
    // il non alimentare è offerto: è l'unico modo perché un detersivo entri in
    // dispensa senza passare per «altro», che è il reparto delle cose da chiarire
    expect(
      [...(reparto as HTMLSelectElement).options].map((o) => o.value)
    ).toContain("casa");

    await userEvent.selectOptions(reparto, "casa");
    await userEvent.click(screen.getByRole("button", { name: /Crea l'ingrediente/i }));

    expect(postBody(spy, "/ingredients")).toEqual({
      name: "cosa strana",
      display_name: "cosa strana",
      category: "casa",
    });
  });
```

**E cambia il test vicino invece di lasciarlo in piedi.** «Se nessun ingrediente
corrisponde lo dice, e lascia crearlo» asserisce oggi `category: "altro"` **e** la
frase «finisce nel reparto «altro»». Da questo task la creazione non è più d'ufficio:
quel test descrive un comportamento che non esiste più. Aggiornalo alla frase nuova
(Step 3) e lascialo asserire `category: "altro"` **senza** toccare il `<select>` —
diventa così la prova che il valore di partenza è ancora «altro», cioè che chi non
vuole scegliere fa esattamente quel che faceva prima.

- [ ] **Step 2: Esegui il test e guardalo fallire**

```bash
cd frontend && npx vitest run src/features/stocking/StockingScreen.test.tsx
```

Atteso: `findByLabelText("Reparto")` non trova niente.

- [ ] **Step 3: Sostituisci la costante con una scelta**

In `frontend/src/features/stocking/StockingScreen.tsx`, togli:

```tsx
const UNKNOWN_CATEGORY = "altro";
```

e dentro `MatchIngredientField` aggiungi uno stato e il campo. Il valore iniziale
resta `"altro"`, così chi non vuole scegliere fa quel che fa oggi con un tocco in più:

```tsx
  // Il reparto non si indovina più: si chiede. Il commento che stava qui diceva
  // «indovinarlo sarebbe una bugia», e aveva ragione — la correzione non è
  // indovinare meglio. Parte da «altro», che è dove finiva d'ufficio: chi non ha
  // niente da dire fa esattamente quello che faceva prima.
  const [category, setCategory] = useState<string>("altro");
```

```tsx
  const create = useMutation({
    mutationFn: (text: string) =>
      createIngredient({ name: text, display_name: text, category }),
    onSuccess: onMatched,
  });
```

e, appena sopra il tasto «Crea l'ingrediente», il campo:

```tsx
      <label className="text-sm">
        Reparto
        <select
          aria-label="Reparto"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="mt-1.5"
        >
          {FOOD_CATEGORIES.map((name) => (
            <option key={name} value={name}>{name}</option>
          ))}
          {/* staccati, perché sono un'altra cosa: non è un reparto in più del
              supermercato, è la metà dell'anagrafica che le ricette non vedono */}
          <optgroup label="Non alimentari">
            {NON_FOOD_CATEGORIES.map((name) => (
              <option key={name} value={name}>{name}</option>
            ))}
          </optgroup>
        </select>
      </label>
```

con `import { FOOD_CATEGORIES, NON_FOOD_CATEGORIES } from "../../domain/categories";`
in cima.

Aggiorna anche la frase che prometteva il reparto d'ufficio:

```tsx
        <p className="text-sm text-low">
          Nessun ingrediente corrisponde. Puoi crearlo adesso: scegli il reparto e la
          voce diventa sistemabile.
        </p>
```

- [ ] **Step 4: Esegui tutto e guardalo passare**

```bash
cd frontend && npx vitest run && npm run typecheck && npm run build
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/stocking/StockingScreen.tsx \
  frontend/src/features/stocking/StockingScreen.test.tsx
git commit -m "$(cat <<'EOF'
feat: il reparto di una voce nuova si chiede, non si indovina

Il commento che stava qui diceva che indovinarlo sarebbe una bugia, e aveva
ragione: la correzione non era indovinare meglio. Parte da «altro», dove
finiva d'ufficio, e i due reparti non alimentari stanno in un gruppo a parte
— non sono una corsia in più, sono la metà che le ricette non vedono.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: Niente campi nutrizionali per un non alimentare

**Files:**
- Modify: `frontend/src/features/stocking/CustomProductForm.tsx`
- Modify: `frontend/src/features/stocking/StockingScreen.tsx` (il punto di chiamata)
- Test: `frontend/src/features/stocking/CustomProductForm.test.tsx`

**Interfaces:**
- Consumes: `ShoppingItem.ingredient_kind` e `Ingredient.kind` (Task 7, Task 9).
- Produces: prop `isNonFood?: boolean` su `CustomProductForm`.

- [ ] **Step 1: Scrivi il test che fallisce**

In coda a `frontend/src/features/stocking/CustomProductForm.test.tsx`:

```tsx
it("per un non alimentare non chiede i nutrienti, e non ne manda", async () => {
  // quattro campi senza senso su un detersivo, e un `nutrients: {}` che sarebbe
  // un'affermazione su valori che non esistono
  const inviati: unknown[] = [];
  stubRoutedFetch((_path, init) => {
    inviati.push(JSON.parse(String(init?.body)));
    return [{ id: "p1", ingredient_id: "i1", name: "Dash", brand: null, barcode: null,
              source: "custom", nutrients: null, image_url: null }, 201];
  });

  render(
    <CustomProductForm
      ingredientId="i1" itemLabel="detersivo" isNonFood
      onCreated={() => {}} onCancel={() => {}}
    />
  );

  expect(screen.queryByLabelText("Calorie per 100 g")).toBeNull();
  fireEvent.change(screen.getByLabelText("Nome"), { target: { value: "Dash" } });
  fireEvent.click(screen.getByRole("button", { name: "Salva prodotto" }));

  await waitFor(() => expect(inviati.length).toBe(1));
  expect((inviati[0] as { nutrients?: unknown }).nutrients).toBeUndefined();
});
```

Le etichette sono quelle vere del componente: il campo si chiama «Nome» e il tasto
di invio «Salva prodotto».

- [ ] **Step 2: Esegui il test e guardalo fallire**

```bash
cd frontend && npx vitest run src/features/stocking/CustomProductForm.test.tsx
```

Atteso: `isNonFood` non esiste come prop (errore di tipo), e i quattro campi ci sono.

- [ ] **Step 3: Nascondi i campi e non mandare la mappa**

In `CustomProductForm`, aggiungi la prop:

```tsx
  /** Un detersivo non ha calorie: i quattro campi non si mostrano e `nutrients`
   * resta assente. Assente, non a zero — zero sarebbe un'affermazione. */
  isNonFood = false,
```

```tsx
  isNonFood?: boolean;
```

Avvolgi il blocco `{FIELDS.map(...)}` (e il riepilogo `carried`, che parla degli
stessi valori) in `{!isNonFood && ( ... )}`, e nella mutazione:

```tsx
        nutrients: isNonFood || Object.keys(parsed).length === 0 ? undefined : parsed,
```

In `StockingScreen.tsx`, accanto a `effectiveIngredientId`, aggiungi il gemello e
passalo al modulo:

```tsx
  // lo stesso ragionamento di effectiveIngredientId: la voce può avere il suo
  // ingrediente dalla lista, oppure averlo appena abbinato qui dentro
  function effectiveKind(item: ShoppingItem): "food" | "non_food" | null {
    return item.ingredient_kind ?? matchedIngredient[item.id]?.kind ?? null;
  }
```

```tsx
            isNonFood={effectiveKind(creatingFor.item) === "non_food"}
```

- [ ] **Step 4: Esegui tutto e guardalo passare**

```bash
cd frontend && npx vitest run && npm run typecheck && npm run build
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/stocking/CustomProductForm.tsx \
  frontend/src/features/stocking/CustomProductForm.test.tsx \
  frontend/src/features/stocking/StockingScreen.tsx
git commit -m "$(cat <<'EOF'
feat: un detersivo può avere una marca, non delle calorie

I quattro campi spariscono e `nutrients` resta assente: assente e non a
zero, perché zero sarebbe un'affermazione su valori che non esistono.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: L'e2e — il giro del detersivo

**Files:**
- Create: `frontend/e2e/non-alimentari.spec.ts`

**Interfaces:**
- Consumes: tutto quel che precede.
- Produces: niente.

**La regola di questa suite: ogni file pulisce dietro di sé.** Il database vive
quanto lo stack e i file girano in sequenza (`workers: 1`), ma **l'ordine non è una
garanzia** — `style.spec.ts` lo dice per esteso nel suo commento in testa, e archivia
la voce che si aggiunge proprio per questo. `cooking.spec.ts` comincia asserendo che
la lista sia vuota: un file che le lascia dentro un detersivo lo farebbe fallire con
un errore che non dice perché. Quindi due regole, ed entrambe vanno rispettate:
**usa un ingrediente che nessun altro file nomina** («detersivo per i piatti»: gli
altri lavorano su pomodoro e cipolla) e **togli quel che hai messo**, dalla lista e
dalla dispensa, prima di finire.

- [ ] **Step 1: Scrivi la prova**

Crea `frontend/e2e/non-alimentari.spec.ts`:

```ts
import { test, expect } from "@playwright/test";

// Il giro che questa funzione esiste per rendere possibile, sull'app costruita e
// servita da Nginx contro il backend vero: il detersivo entra in lista, va in
// dispensa, finisce, e torna in lista. Gira dopo cooking.spec.ts (workers: 1,
// ordine alfabetico), che pretende una lista vuota: il nome del file non è
// decorativo.
const PASSWORD = process.env.E2E_PASSWORD ?? "test";

test("un detersivo fa il giro: lista, dispensa, e ritorno in lista", async ({ page }) => {
  await page.goto("/");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Entra", exact: true }).click();

  // 1. lo scelgo dall'autocomplete: c'è perché il seme lo porta
  await page.getByLabel("Aggiungi alla lista").fill("detersivo per i p");
  await page.getByRole("option", { name: /Detersivo per i piatti/ }).click();
  const voce = page.getByRole("checkbox", { name: "detersivo per i piatti" });
  await expect(voce).toBeVisible();

  // 2. lo spunto e lo sistemo in dispensa come sfuso
  await voce.click();
  await expect(voce).toBeChecked();
  await page.getByRole("link", { name: "Sistema la spesa" }).click();
  await page.getByRole("button", { name: /Sfuso.*detersivo per i piatti/i }).click();
  await page.getByRole("button", { name: "Metti in dispensa", exact: true }).click();

  // 3. in dispensa sta nel suo reparto, non fra il cibo
  await page.getByRole("link", { name: "Dispensa" }).click();
  await expect(page.getByText("casa")).toBeVisible();

  // 4. lo porto a zero e la domanda del rientro arriva
  const cursore = page.getByRole("slider", { name: "Quanto ne resta di detersivo per i piatti" });
  await cursore.fill("0");
  await cursore.dispatchEvent("pointerup");
  await expect(page.getByText("Lo rimetto in lista?")).toBeVisible();
  await page.getByRole("button", { name: "Sì" }).click();
  await expect(page.getByText("Rimesso in lista.")).toBeVisible();

  // 5. nel ricettario invece non esiste: il filtro per ingrediente non lo offre
  await page.getByRole("link", { name: "Ricette" }).click();
  await page.getByLabel("Contiene ingredienti").fill("detersivo");
  await expect(page.getByRole("option", { name: /Detersivo/ })).toHaveCount(0);

  // 6. la pulizia, che non è un contorno: la dispensa e la lista sono stato
  // condiviso con gli altri file, e cooking.spec.ts pretende una lista vuota.
  // La X archivia davvero sul server — la lapide che resta a video è solo la
  // finestra dell'annulla.
  await page.getByRole("link", { name: "Dispensa" }).click();
  await page
    .getByRole("button", { name: "Togli detersivo per i piatti dalla dispensa" })
    .click();
  await expect(page.getByText("Tolta dalla dispensa")).toBeVisible();

  await page.getByRole("link", { name: "Lista" }).click();
  await page
    .getByRole("button", { name: "Togli detersivo per i piatti dalla lista" })
    .click();
  await expect(page.getByText("Lista vuota. Scrivi cosa ti serve.")).toBeVisible();
});
```

I nomi dei tasti sono quelli veri: `cooking.spec.ts` fa lo stesso percorso con il
pomodoro e usa esattamente queste due chiamate. L'ultima asserzione — «Lista vuota» —
è anche la prova che la pulizia è completa: se avanzasse qualcosa, fallirebbe qui
invece che dentro `cooking.spec.ts` alla corsa successiva.

- [ ] **Step 2: Esegui gli e2e su uno stack pulito**

```bash
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed
cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e
```

Atteso: **tutti verdi**, il nuovo compreso. Se `cooking.spec.ts` si lamenta che «lo
stack e2e non è pulito», ricrealo con `down -v` **sul solo progetto `spena-e2e`** e
riesegui: è il suo modo documentato di dire che il database porta lo stato di una
corsa precedente.

- [ ] **Step 3: Smonta lo stack e2e**

```bash
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
```

**`-p spena-e2e` non è opzionale:** senza, `down -v` cancella i volumi dello sviluppo.

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/non-alimentari.spec.ts
git commit -m "$(cat <<'EOF'
test: il giro del detersivo, in un browser vero

Lista, dispensa nel suo reparto, rientro in lista da finito, e assenza dal
filtro per ingrediente del ricettario. Poi la pulizia, come fa style.spec.ts:
il database vive quanto lo stack e cooking.spec.ts pretende una lista vuota,
quindi un file che lascia qualcosa dietro rompe un altro file.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 13: I documenti fondanti

**Files:**
- Modify: `CLAUDE.md` (decisione fondante 2)
- Modify: `docs/prossimi-passi.md` (D4, S5, e la nota sulle parole)

**Interfaces:** nessuna.

- [ ] **Step 1: Emenda la decisione fondante 2 di `CLAUDE.md`**

In coda al paragrafo «**2. Generic ingredient and specific product are different
things.**», aggiungi:

```markdown
> **Since 2026-09-17 the registry also holds non-food entries** — detergent, toilet
> paper — split off by `ingredients.kind` (`food` | `non_food`), which is never
> written by hand: it is derived from the department by `kind_for_category` in
> `domain/rules.py`. They live in the same list and the same pantry, with the same
> three statuses. **The rule above is untouched**: recipes still point at
> ingredients only, and it is precisely that rule the guard in `create_recipe`
> defends — a recipe cannot name a non-food entry, and four earlier guards make
> sure it never gets the chance. See
> `docs/superpowers/specs/2026-09-17-non-alimentari-design.md`.
```

- [ ] **Step 2: Chiudi D4 e S5 nei prossimi passi**

In `docs/prossimi-passi.md`:
- l'intestazione di **D4** diventa `## D4. Il non alimentare **[FATTO <data>]**`, e
  la proposta va riscritta al passato: due assi (`kind` derivato dal reparto), i due
  reparti `casa` e `igiene`, le cinque guardie e dove stanno.
- l'intestazione di **S5** diventa `## S5. Non alimentari in lista e dispensa
  **[FATTO <data>]**`, con il rimando alla spec.
- la frase «La parola "ingrediente" resta nel codice; nell'interfaccia, dove serve, si
  dice "voce"» va **corretta**, non cancellata: verificato riga per riga, lista e
  dispensa non dicono mai «ingrediente» all'utente — tutte le occorrenze visibili
  stanno nel mondo delle ricette — quindi non c'era niente da rinominare.
- in **Parte VIII (ordine consigliato)**, togli D4/S5 dal blocco strutturale: restano
  S4 e D1 applicata.

- [ ] **Step 3: Verifica finale su tutto**

```bash
docker compose -f docker-compose.yml up -d db
cd backend && .venv/bin/python -m pytest -q
cd frontend && npx vitest run && npm run typecheck && npm run build
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md docs/prossimi-passi.md
git commit -m "$(cat <<'EOF'
docs: l'anagrafica ospita anche il non alimentare, e le ricette no

CLAUDE.md dice ora che il registro è diviso da `kind`, e che la regola «le
ricette puntano solo a ingredienti» è intatta: è proprio quella che la
guardia in create_recipe difende. D4 e S5 sono chiuse.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Messa in produzione (dopo che il ramo è verde e rivisto)

1. `git pull --ff-only` sul server, in `~/sites/spena`.
2. `docker compose -f docker-compose.prod.yml up -d --build --wait` — **il `-f` non è
   opzionale** (terza lezione di `CLAUDE.md`). La migrazione `0007` parte all'avvio
   del backend.
3. Le diciotto voci arrivano con
   `docker compose -f docker-compose.prod.yml exec -T backend python -m app.cli.seed --solo-ingredienti`.
   La forma con `--solo-ingredienti` è quella giusta: il seme intero rimetterebbe
   anche le ricette del seme eventualmente cancellate.
