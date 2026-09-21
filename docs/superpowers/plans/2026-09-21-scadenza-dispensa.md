# La scadenza in dispensa — piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** una data di scadenza facoltativa sull'elemento di dispensa, scritta
all'ingresso o dopo, che a sette giorni dalla scadenza colora una pastiglia sulla riga
— senza toccare lo stato, la disponibilità o la cucinabilità di niente.

**Architecture:** una colonna `DATE` annullabile su `pantry_items`; una funzione pura
in `app/domain/rules.py` che dice `soon` / `expired` / niente; il verdetto viaggia già
deciso dentro `PantryItemOut`, così il numero sette non arriva mai al TypeScript; due
superfici di scrittura (un campo dietro un tocco in «Sistema la spesa», la pastiglia
correggibile in dispensa) e un token di colore nuovo a due intensità.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, Postgres 16; React 19 + Vite +
TypeScript, Tailwind con `@theme`; pytest su Postgres vero, Vitest + jsdom, Playwright
sullo stack `spena-e2e`.

**Spec:** `docs/superpowers/specs/2026-09-21-scadenza-dispensa-design.md`

## Global Constraints

- **Lo stato resta la sola verità.** Niente di quel che segue entra in
  `status_for_fill`, in `availability_map` o in qualunque giudizio di cucinabilità.
  Una voce scaduta resta disponibile. (D5, §2 della spec.)
- **Il sette non attraversa il confine.** La soglia vive solo in Python; il frontend
  riceve `"soon"` / `"expired"` / `null` e non la ricalcola mai.
- **«Oggi» è `Europe/Rome`, non UTC.** Ogni conto sul giorno di calendario passa da
  `today_in_pantry`.
- **TDD, rosso prima.** Nessun codice di produzione senza un test che è già fallito.
- Il backend si prova da `backend/` con `.venv/bin/python -m pytest`; il frontend da
  `frontend/` con `npx vitest run` (da una sottodirectory Vitest dà un verde falso).
- **Il controllo dei tipi è `npm run typecheck`** (`tsc -b`), mai `tsc --noEmit`, che
  su questo progetto esce 0 sempre.
- Nessuna chiamata di rete nella suite.
- Tutto il colore sta nel blocco `@theme` di `frontend/src/index.css`. Nessuna
  schermata nomina un colore grezzo.
- Specifiche e commenti in italiano, identificatori in inglese.
- Commit frequenti, uno per task.

---

## Struttura dei file

**Backend**
- `backend/app/domain/rules.py` — *modifica*: `EXPIRY_SOON_DAYS`, `PANTRY_TZ`,
  `ExpiryState`, `expiry_state`, `today_in_pantry`. Resta puro: nessun accesso al
  database.
- `backend/app/db/models/pantry.py` — *modifica*: la colonna `expires_on`.
- `backend/alembic/versions/0009_scadenza_dispensa.py` — *crea*.
- `backend/app/repositories/pantry.py` — *modifica*: `set_expiry`, e `expires_on` fra
  i parametri di `add_pantry_item`.
- `backend/app/repositories/shopping.py` — *modifica*: `StockEntry.expires_on`, che
  `stock_items` inoltra.
- `backend/app/schemas/pantry.py` — *modifica*: `expires_on` e `expiry` in uscita,
  `expires_on` nella patch.
- `backend/app/schemas/shopping.py` — *modifica*: `StockEntryIn.expires_on`.
- `backend/app/api/pantry.py` — *modifica*: `_to_out` e il ramo nuovo della PATCH.
- `backend/app/api/shopping.py` — *modifica*: il campo passa da `StockEntryIn` a
  `StockEntry`.

**Frontend**
- `frontend/src/index.css` — *modifica*: i due token del colore.
- `frontend/src/features/pantry/expiryLabels.ts` — *crea*: le parole e i toni, in un
  file loro come `statusLabels.ts` (un export costante accanto a un componente rompe
  il fast refresh).
- `frontend/src/components/ui/ExpiryChip.tsx` — *crea*: la pastiglia, accanto a
  `StatusChip.tsx`.
- `frontend/src/domain/types.ts` — *modifica*: `PantryItem` prende `expires_on` e
  `expiry`.
- `frontend/src/features/pantry/api.ts` — *modifica*: `patchPantryItem` accetta la
  data, `null` compreso.
- `frontend/src/features/pantry/PantryRow.tsx` — *modifica*: pastiglia, «+ scadenza»,
  correzione.
- `frontend/src/features/pantry/PantryScreen.tsx` — *modifica*: la mutazione nuova.
- `frontend/src/features/stocking/StockingScreen.tsx` e `api.ts` — *modifica*: il
  campo dietro un tocco, e la data dentro le entries.

**Prove**
- `backend/tests/domain/test_rules.py`, `backend/tests/db/test_pantry_shopping_schema.py`,
  `backend/tests/api/test_pantry.py`, `backend/tests/api/test_shopping.py` — *modifica*.
- `frontend/src/components/ui/ExpiryChip.test.tsx` — *crea*.
- `frontend/src/features/pantry/PantryRow.test.tsx` (o `PantryScreen.test.tsx`),
  `frontend/src/features/stocking/StockingScreen.test.tsx` — *modifica*.
- `frontend/e2e/style.spec.ts` — *modifica*.

**Documenti** (Task 11): `CLAUDE.md`, `docs/superpowers/specs/2026-09-11-spena-design.md`,
`docs/prossimi-passi.md`.

---

### Task 1: La regola, pura

**Files:**
- Modify: `backend/app/domain/rules.py`
- Test: `backend/tests/domain/test_rules.py`

**Interfaces:**
- Consumes: niente.
- Produces: `EXPIRY_SOON_DAYS: int`, `PANTRY_TZ: ZoneInfo`,
  `ExpiryState(StrEnum)` con `SOON = "soon"` e `EXPIRED = "expired"`,
  `expiry_state(expires_on: date | None, today: date) -> ExpiryState | None`,
  `today_in_pantry(now: datetime | None = None) -> date`.

- [ ] **Step 1: Scrivi il test che fallisce**

In fondo a `backend/tests/domain/test_rules.py`:

```python
from datetime import UTC, date, datetime

import pytest

from app.domain.rules import (
    EXPIRY_SOON_DAYS,
    ExpiryState,
    expiry_state,
    today_in_pantry,
)

OGGI = date(2026, 9, 21)


@pytest.mark.parametrize(
    "expires_on, atteso",
    [
        (None, None),
        (date(2026, 12, 31), None),
        (date(2026, 9, 29), None),
        (date(2026, 9, 28), ExpiryState.SOON),
        (date(2026, 9, 22), ExpiryState.SOON),
        (date(2026, 9, 21), ExpiryState.SOON),
        (date(2026, 9, 20), ExpiryState.EXPIRED),
        (date(2025, 1, 1), ExpiryState.EXPIRED),
    ],
)
def test_il_segnale_della_scadenza(expires_on, atteso):
    """I due confini, dichiarati: a sette giorni esatti il segnale c'è già, e quel
    che scade oggi è ancora «sta per scadere» — si mangia oggi. «Scaduto» comincia
    il giorno dopo. Nessuna data è il caso normale e non produce niente."""
    assert expiry_state(expires_on, OGGI) is atteso


def test_la_soglia_e_sette_giorni():
    """Il numero è un valore di dominio, non una costante decorativa: se qualcuno lo
    cambia, deve essere una decisione e non un effetto collaterale."""
    assert EXPIRY_SOON_DAYS == 7


def test_il_giorno_della_dispensa_non_e_quello_di_utc():
    """Mezzanotte e mezza a Roma d'estate è ancora ieri in UTC. Con `date.today()`
    la pastiglia cambierebbe colore con un giorno di ritardo per due ore al giorno,
    e nessun test se ne accorgerebbe per le altre ventidue."""
    istante = datetime(2026, 7, 15, 23, 30, tzinfo=UTC)

    assert istante.date() == date(2026, 7, 15)
    assert today_in_pantry(istante) == date(2026, 7, 16)
```

- [ ] **Step 2: Guarda il rosso**

Run (da `backend/`): `.venv/bin/python -m pytest tests/domain/test_rules.py -v`
Expected: FAIL in raccolta — `ImportError: cannot import name 'ExpiryState'`.

- [ ] **Step 3: Il codice minimo**

In `backend/app/domain/rules.py`, dopo `status_for_fill` e il suo commento:

```python
# La scadenza: un segnale, non uno stato. Sta accanto a `status_for_fill` perché è
# lo stesso genere di cosa — un fatto che il client chiede invece di calcolare — ma
# non entra in quella funzione e non ne esce: una voce scaduta resta disponibile, e
# nessuna ricetta diventa non cucinabile di notte senza che nessuno abbia toccato
# niente. È la decisione D5 di docs/prossimi-passi.md.
EXPIRY_SOON_DAYS = 7

# Dove sta la dispensa. Tutto il resto del backend lavora in UTC ed è giusto così:
# sono istanti. Questo è un giorno di calendario, e un giorno in UTC non è il giorno
# di chi apre l'app a Milano a mezzanotte e mezza.
PANTRY_TZ = ZoneInfo("Europe/Rome")


class ExpiryState(StrEnum):
    SOON = "soon"
    EXPIRED = "expired"


def expiry_state(expires_on: date | None, today: date) -> ExpiryState | None:
    """Nessuna data → nessun segnale: è il caso normale e non deve costare niente.

    `today` entra come argomento invece di essere letto qui dentro: è quel che rende
    questa funzione provabile su date scritte a mano, e quel che impedisce
    all'orologio di entrare in un modulo puro.
    """
    if expires_on is None:
        return None
    if expires_on < today:
        return ExpiryState.EXPIRED
    if (expires_on - today).days <= EXPIRY_SOON_DAYS:
        return ExpiryState.SOON
    return None


def today_in_pantry(now: datetime | None = None) -> date:
    """Che giorno è, dove sta la dispensa."""
    return (now or datetime.now(UTC)).astimezone(PANTRY_TZ).date()
```

E in cima al file, agli import: `from datetime import UTC, date, datetime` e
`from zoneinfo import ZoneInfo`.

- [ ] **Step 4: Guarda il verde**

Run: `.venv/bin/python -m pytest tests/domain/test_rules.py -v`
Expected: PASS, tutti. Poi la suite del dominio intera:
`.venv/bin/python -m pytest tests/domain -q`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/rules.py backend/tests/domain/test_rules.py
git commit -m "feat: la regola della scadenza, e un giorno che non è quello di UTC"
```

---

### Task 2: La colonna

**Files:**
- Modify: `backend/app/db/models/pantry.py`
- Create: `backend/alembic/versions/0009_scadenza_dispensa.py`
- Test: `backend/tests/db/test_pantry_shopping_schema.py`

**Interfaces:**
- Consumes: niente del Task 1.
- Produces: `PantryItem.expires_on: Mapped[date | None]`, e la migrazione `0009` con
  `down_revision = "0008"`.

- [ ] **Step 1: Scrivi il test che fallisce**

In fondo a `backend/tests/db/test_pantry_shopping_schema.py`:

```python
async def test_una_voce_di_dispensa_puo_portare_una_scadenza(db_session):
    """Annullabile davvero, e una data già passata è legittima: capita di mettere in
    dispensa qualcosa che scade domani, o di scrivere la data il giorno dopo con il
    barattolo in mano. Un CHECK «non nel passato» sarebbe falso metà delle volte."""
    from datetime import date

    from app.db.models.ingredient import Ingredient, IngredientCategory
    from app.db.models.pantry import PantryItem
    from app.domain.rules import PantryStatus

    latte = Ingredient(name="latte", display_name="Latte",
                       category=IngredientCategory.LATTICINI)
    db_session.add(latte)
    await db_session.flush()

    senza = PantryItem(ingredient_id=latte.id, status=PantryStatus.AVAILABLE)
    scaduto = PantryItem(ingredient_id=latte.id, status=PantryStatus.AVAILABLE,
                         expires_on=date(2020, 1, 1))
    db_session.add_all([senza, scaduto])
    await db_session.flush()

    assert senza.expires_on is None
    assert scaduto.expires_on == date(2020, 1, 1)
```

- [ ] **Step 2: Guarda il rosso**

Run: `.venv/bin/python -m pytest tests/db/test_pantry_shopping_schema.py -v`
Expected: FAIL — `TypeError: 'expires_on' is an invalid keyword argument for PantryItem`.

- [ ] **Step 3: Il codice minimo**

In `backend/app/db/models/pantry.py`, dopo `note` e prima di `added_at`:

```python
    # La scadenza di *questo* barattolo, non dell'ingrediente e non del prodotto: la
    # dispensa può avere due vasetti dello stesso yogurt comprati a un mese di
    # distanza. `DATE` e non un timestamp, perché una scadenza è un giorno e non un
    # istante: trattarla come un istante infilerebbe un fuso orario in un dato che
    # non ne ha. NULL è il caso normale — chi non la scrive ha la dispensa di prima.
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
```

Aggiungi `Date` agli import di `sqlalchemy` e `date` a quelli di `datetime`.

Crea `backend/alembic/versions/0009_scadenza_dispensa.py`:

```python
"""la scadenza in dispensa

Revision ID: 0009
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"


def upgrade() -> None:
    # Nessun CHECK: una data nel passato è legittima (vedi il commento sul modello).
    op.add_column("pantry_items", sa.Column("expires_on", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("pantry_items", "expires_on")
```

- [ ] **Step 4: Guarda il verde, e la parità con la migrazione**

Run: `.venv/bin/python -m pytest tests/db -q`
Expected: PASS, **compreso `test_metadata_matches_migrations.py`** — è il test che si
accorge se il modello e la migrazione dicono cose diverse. Se fallisce lui, è la
migrazione a essere sbagliata, non il test.

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/models/pantry.py backend/alembic/versions/0009_scadenza_dispensa.py backend/tests/db/test_pantry_shopping_schema.py
git commit -m "feat: pantry_items porta una scadenza, annullabile e senza vincoli"
```

---

### Task 3: Scriverla e cancellarla, nel repository

**Files:**
- Modify: `backend/app/repositories/pantry.py`
- Test: `backend/tests/api/test_pantry.py`

**Interfaces:**
- Consumes: `PantryItem.expires_on` (Task 2).
- Produces: `set_expiry(session, item_id: uuid.UUID, expires_on: date | None) -> PantryItem`
  (solleva `KeyError` se la voce non c'è, come le sorelle), e
  `add_pantry_item(..., expires_on: date | None = None)`.

- [ ] **Step 1: Scrivi i test che falliscono**

In fondo a `backend/tests/api/test_pantry.py`:

```python
async def test_scrivere_e_cancellare_la_scadenza(db_session, dispensa):
    """`None` non è «non l'ho detto», è «cancellala»: chi ha battuto male una data
    deve poterla togliere, non solo cambiarla."""
    from datetime import date

    from app.repositories.pantry import set_expiry

    item = PantryItem(ingredient_id=dispensa["yogurt"].id, status=PantryStatus.AVAILABLE)
    db_session.add(item)
    await db_session.flush()

    await set_expiry(db_session, item.id, date(2026, 9, 28))
    assert item.expires_on == date(2026, 9, 28)

    await set_expiry(db_session, item.id, None)
    assert item.expires_on is None


async def test_la_scadenza_non_e_un_cambio_di_stato(db_session, dispensa):
    """`status_changed_at` risponde a «da quanto è in questo stato»: muoverlo qui
    direbbe che qualcosa è cambiato nella disponibilità, che è precisamente quel che
    D5 ha deciso non succeda."""
    from datetime import date

    from app.repositories.pantry import set_expiry

    item = PantryItem(ingredient_id=dispensa["yogurt"].id, status=PantryStatus.LOW)
    db_session.add(item)
    await db_session.flush()
    prima = item.status_changed_at

    await set_expiry(db_session, item.id, date(2026, 9, 28))

    assert item.status_changed_at == prima
    assert item.status == PantryStatus.LOW


async def test_scadenza_su_una_voce_inesistente(db_session):
    import uuid as _uuid
    from datetime import date

    import pytest as _pytest

    from app.repositories.pantry import set_expiry

    with _pytest.raises(KeyError):
        await set_expiry(db_session, _uuid.uuid4(), date(2026, 9, 28))


async def test_una_voce_entra_gia_con_la_sua_scadenza(db_session, dispensa):
    """La strada dell'ingresso: la data si scrive con il barattolo in mano, quindi
    `add_pantry_item` deve saperla accettare — è il punto unico da cui passano sia la
    scorta diretta sia la sistemazione della spesa."""
    from datetime import date

    from app.repositories.pantry import add_pantry_item

    item = await add_pantry_item(
        db_session, ingredient_id=dispensa["yogurt"].id, expires_on=date(2026, 10, 5)
    )

    assert item.expires_on == date(2026, 10, 5)
```

- [ ] **Step 2: Guarda il rosso**

Run: `.venv/bin/python -m pytest tests/api/test_pantry.py -v -k scadenza`
Expected: FAIL — `ImportError: cannot import name 'set_expiry'`.

- [ ] **Step 3: Il codice minimo**

In `backend/app/repositories/pantry.py`, accanto a `set_fill`:

```python
async def set_expiry(
    session: AsyncSession, item_id: uuid.UUID, expires_on: date | None
) -> PantryItem:
    """La scadenza di questa voce. `None` cancella la data: è una richiesta, non
    un'assenza di richiesta, ed è il motivo per cui la rotta guarda
    `model_fields_set` invece di `is not None`.

    Non tocca `status_changed_at`: la scadenza non è un cambio di stato, e il resto
    dell'app non deve vedere niente muoversi.
    """
    item = await session.get(PantryItem, item_id)
    if item is None:
        raise KeyError(item_id)
    item.expires_on = expires_on
    await session.flush()
    return item
```

E in `add_pantry_item`, il parametro nuovo fra `note` e la fine della firma:

```python
    expires_on: date | None = None,
```

passato al costruttore di `PantryItem` insieme agli altri. Aggiungi `date` agli
import del modulo.

- [ ] **Step 4: Guarda il verde**

Run: `.venv/bin/python -m pytest tests/api/test_pantry.py -q`
Expected: PASS, tutti.

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/pantry.py backend/tests/api/test_pantry.py
git commit -m "feat: set_expiry, e una voce che può entrare già con la sua data"
```

---

### Task 4: Il verdetto in uscita

**Files:**
- Modify: `backend/app/schemas/pantry.py`, `backend/app/api/pantry.py`
- Test: `backend/tests/api/test_pantry.py`

**Interfaces:**
- Consumes: `expiry_state`, `today_in_pantry`, `ExpiryState` (Task 1);
  `PantryItem.expires_on` (Task 2).
- Produces: `PantryItemOut.expires_on: date | None` e
  `PantryItemOut.expiry: ExpiryState | None`, riempiti in `_to_out`.

- [ ] **Step 1: Scrivi il test che fallisce**

```python
async def test_la_dispensa_manda_la_data_e_il_verdetto(logged_client, db_session, dispensa):
    """Due campi e non uno: la data serve a mostrarla e a riaprirla in correzione, il
    verdetto a colorarla. Con la sola data il browser dovrebbe rifare il conto dei
    sette giorni, che è esattamente quel che la spec §4 evita; con il solo verdetto si
    perderebbe quel che l'utente ha scritto."""
    from datetime import timedelta

    from app.domain.rules import today_in_pantry

    oggi = today_in_pantry()
    db_session.add_all([
        PantryItem(ingredient_id=dispensa["yogurt"].id, status=PantryStatus.AVAILABLE,
                   expires_on=oggi + timedelta(days=3)),
        PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.AVAILABLE,
                   expires_on=oggi - timedelta(days=1)),
        PantryItem(ingredient_id=dispensa["aglio"].id, status=PantryStatus.AVAILABLE),
    ])
    await db_session.flush()
    await db_session.commit()

    risposta = await logged_client.get("/api/v1/pantry")
    assert risposta.status_code == 200
    per_nome = {v["ingredient_name"]: v for v in risposta.json()}

    assert per_nome["yogurt greco"]["expiry"] == "soon"
    assert per_nome["yogurt greco"]["expires_on"] == (oggi + timedelta(days=3)).isoformat()
    assert per_nome["pomodoro"]["expiry"] == "expired"
    assert per_nome["aglio"]["expiry"] is None
    assert per_nome["aglio"]["expires_on"] is None


async def test_una_voce_scaduta_resta_disponibile(logged_client, db_session, dispensa):
    """Il cuore di D5. Se questo test diventa rosso, qualcuno ha fatto entrare la
    scadenza nel giudizio di disponibilità, e una ricetta ha smesso di essere
    cucinabile di notte senza che nessuno abbia toccato niente."""
    from datetime import timedelta

    from app.domain.rules import today_in_pantry

    db_session.add(
        PantryItem(ingredient_id=dispensa["yogurt"].id, status=PantryStatus.AVAILABLE,
                   expires_on=today_in_pantry() - timedelta(days=30))
    )
    await db_session.flush()
    await db_session.commit()

    risposta = await logged_client.get("/api/v1/pantry/availability")
    assert risposta.json()[str(dispensa["yogurt"].id)] == "available"
```

> Se il percorso di `availability` in questo file è scritto diversamente, copia la
> forma da `test_availability_endpoint_returns_a_map` invece di inventarne una.

- [ ] **Step 2: Guarda il rosso**

Run: `.venv/bin/python -m pytest tests/api/test_pantry.py -v -k "verdetto or scaduta"`
Expected: FAIL — `KeyError: 'expiry'` sul primo. Il secondo **deve passare già
adesso**: è un test di non-regressione, e passa perché nessuno ha ancora toccato la
disponibilità. Se fallisce, fermati: vuol dire che qualcosa nei task precedenti l'ha
già toccata.

- [ ] **Step 3: Il codice minimo**

In `backend/app/schemas/pantry.py`, dentro `PantryItemOut`, dopo `note`:

```python
    # La data com'è stata scritta, e il verdetto già preso. Il secondo esiste perché
    # la soglia dei sette giorni non deve attraversare il confine: il client chiede,
    # non calcola.
    expires_on: date | None
    expiry: ExpiryState | None
```

con `from datetime import date` e `from app.domain.rules import ExpiryState` fra gli
import. In `backend/app/api/pantry.py`, dentro `_to_out`:

```python
        expires_on=item.expires_on,
        expiry=expiry_state(item.expires_on, today_in_pantry()),
```

importando `expiry_state` e `today_in_pantry` da `app.domain.rules`.

- [ ] **Step 4: Guarda il verde**

Run: `.venv/bin/python -m pytest tests/api -q`
Expected: PASS. Qui si vede anche se qualche altro test costruiva un `PantryItemOut` a
mano: se ce n'è, aggiungerne i due campi fa parte di questo task.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/pantry.py backend/app/api/pantry.py backend/tests/api/test_pantry.py
git commit -m "feat: la dispensa manda la data e il verdetto, e la disponibilità non cambia"
```

---

### Task 5: Correggerla, dalla PATCH

**Files:**
- Modify: `backend/app/schemas/pantry.py`, `backend/app/api/pantry.py`
- Test: `backend/tests/api/test_pantry.py`

**Interfaces:**
- Consumes: `set_expiry` (Task 3), `PantryItemOut` (Task 4).
- Produces: `PantryItemPatch.expires_on: date | None = None`, e il ramo che la
  riconosce **per presenza** e non per valore.

- [ ] **Step 1: Scrivi i test che falliscono — il `null` per primo**

```python
async def test_patch_cancella_la_scadenza_con_null(logged_client, db_session, dispensa):
    """Il test che difende il difetto più probabile di tutto questo lavoro. Scritto
    con `payload.expires_on is not None`, il ramo sembra funzionare — scrive le date
    e non cancella mai niente — e un corpo `{"expires_on": null}` finisce nell'`else`,
    che risponde «niente da modificare». Cioè la cancellazione fallisce dicendo che
    non c'era niente da fare."""
    from datetime import date

    item = PantryItem(ingredient_id=dispensa["yogurt"].id, status=PantryStatus.AVAILABLE,
                      expires_on=date(2026, 9, 28))
    db_session.add(item)
    await db_session.flush()
    await db_session.commit()

    risposta = await logged_client.patch(f"/api/v1/pantry/{item.id}",
                                         json={"expires_on": None})

    assert risposta.status_code == 200
    assert risposta.json()["expires_on"] is None
    assert risposta.json()["expiry"] is None


async def test_patch_scrive_la_scadenza(logged_client, db_session, dispensa):
    item = PantryItem(ingredient_id=dispensa["yogurt"].id, status=PantryStatus.AVAILABLE)
    db_session.add(item)
    await db_session.flush()
    await db_session.commit()

    risposta = await logged_client.patch(f"/api/v1/pantry/{item.id}",
                                         json={"expires_on": "2026-09-28"})

    assert risposta.status_code == 200
    assert risposta.json()["expires_on"] == "2026-09-28"


async def test_patch_vuota_resta_un_400(logged_client, db_session, dispensa):
    """Il campo nuovo non deve trasformare «non hai chiesto niente» in un successo
    muto: un corpo `{}` non nomina `expires_on`, quindi non è una cancellazione."""
    item = PantryItem(ingredient_id=dispensa["yogurt"].id, status=PantryStatus.AVAILABLE)
    db_session.add(item)
    await db_session.flush()
    await db_session.commit()

    assert (await logged_client.patch(f"/api/v1/pantry/{item.id}", json={})).status_code == 400
```

- [ ] **Step 2: Guarda il rosso**

Run: `.venv/bin/python -m pytest tests/api/test_pantry.py -v -k patch`
Expected: FAIL — il primo e il secondo con 400 «niente da modificare»; il terzo passa
già.

- [ ] **Step 3: Il codice minimo**

In `PantryItemPatch`:

```python
    # `None` qui è una richiesta, non un'assenza: «cancella la scadenza». Per gli
    # altri campi l'annullabile bastava a distinguere le due cose (vedi `archived`);
    # per una data no, perché il valore nullo è esso stesso un comando. Chi legge
    # questo campo deve guardare `model_fields_set`.
    expires_on: date | None = None
```

In `backend/app/api/pantry.py`, ultimo ramo della catena, **prima** dell'`else`:

```python
        elif "expires_on" in payload.model_fields_set:
            # per presenza, non per valore: `{"expires_on": null}` è la cancellazione
            item = await set_expiry(session, item_id, payload.expires_on)
```

- [ ] **Step 4: Guarda il verde**

Run: `.venv/bin/python -m pytest tests/api/test_pantry.py -q`
Expected: PASS, tutti e tre, e nessuna regressione sugli altri rami della PATCH.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/pantry.py backend/app/api/pantry.py backend/tests/api/test_pantry.py
git commit -m "feat: la PATCH scrive e cancella la scadenza, e null vuol dire cancella"
```

---

### Task 6: La data che entra con la spesa

**Files:**
- Modify: `backend/app/schemas/shopping.py`, `backend/app/repositories/shopping.py`,
  `backend/app/api/shopping.py`
- Test: `backend/tests/api/test_shopping.py`

**Interfaces:**
- Consumes: `add_pantry_item(..., expires_on=...)` (Task 3).
- Produces: `StockEntryIn.expires_on: date | None = None` e
  `StockEntry.expires_on: date | None`, inoltrati da `stock_items`.

- [ ] **Step 1: Scrivi il test che fallisce**

In `backend/tests/api/test_shopping.py`, seguendo la forma dei test di `/stock` già lì
per costruire lista e ingredienti:

```python
async def test_la_sistemazione_porta_in_dispensa_anche_le_scadenze(
    logged_client, db_session, ingredienti
):
    """Una voce con la data e una senza, nella stessa richiesta: la scadenza è
    facoltativa per voce, non per sistemazione. Lo yogurt ha una scadenza vera e
    corta, le mele sfuse no — ed è il caso normale."""
    yogurt_item = ShoppingListItem(raw_text="yogurt greco",
                                   ingredient_id=ingredienti["yogurt"].id,
                                   status=ShoppingStatus.CHECKED,
                                   reason=ShoppingReason.MANUAL)
    mela_item = ShoppingListItem(raw_text="mele", ingredient_id=ingredienti["mela"].id,
                                 status=ShoppingStatus.CHECKED,
                                 reason=ShoppingReason.MANUAL)
    db_session.add_all([yogurt_item, mela_item])
    await db_session.flush()

    response = await logged_client.post("/api/v1/shopping-list/stock", json={"entries": [
        {"shopping_item_id": str(yogurt_item.id),
         "ingredient_id": str(ingredienti["yogurt"].id),
         "product_id": None, "expires_on": "2026-10-02"},
        # le mele sfuse entrano senza data, e non è un errore
        {"shopping_item_id": str(mela_item.id),
         "ingredient_id": str(ingredienti["mela"].id), "product_id": None},
    ]})
    assert response.status_code == 201

    voci = list((await db_session.execute(select(PantryItem))).scalars())
    per_ingrediente = {v.ingredient_id: v for v in voci}
    assert per_ingrediente[ingredienti["yogurt"].id].expires_on == date(2026, 10, 2)
    assert per_ingrediente[ingredienti["mela"].id].expires_on is None
```

`date` va aggiunta agli import del file se non c'è già; `select`, `PantryItem`,
`ShoppingListItem`, `ShoppingStatus` e `ShoppingReason` sono già importati là in cima,
e la fixture `ingredienti` è quella che usano gli altri test di `/stock`.

- [ ] **Step 2: Guarda il rosso**

Run: `.venv/bin/python -m pytest tests/api/test_shopping.py -v -k scadenze`
Expected: FAIL — la voce arriva in dispensa con `expires_on` a `None`, perché il campo
in più viene ignorato.

- [ ] **Step 3: Il codice minimo**

`StockEntryIn` prende `expires_on: date | None = None`; la dataclass `StockEntry`
prende `expires_on: date | None`; la costruzione in `backend/app/api/shopping.py` lo
copia; `stock_items` lo passa ad `add_pantry_item`:

```python
        item = await add_pantry_item(
            session, ingredient_id=entry.ingredient_id, product_id=entry.product_id,
            status=PantryStatus.AVAILABLE, expires_on=entry.expires_on,
        )
```

- [ ] **Step 4: Guarda il verde**

Run: `.venv/bin/python -m pytest tests/api -q`
Expected: PASS. Poi la suite backend intera: `.venv/bin/python -m pytest -q`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/shopping.py backend/app/repositories/shopping.py backend/app/api/shopping.py backend/tests/api/test_shopping.py
git commit -m "feat: la sistemazione della spesa porta in dispensa anche le scadenze"
```

---

### Task 7: Il colore e la pastiglia

**Files:**
- Modify: `frontend/src/index.css`, `frontend/src/domain/types.ts`
- Create: `frontend/src/features/pantry/expiryLabels.ts`,
  `frontend/src/components/ui/ExpiryChip.tsx`,
  `frontend/src/components/ui/ExpiryChip.test.tsx`

**Interfaces:**
- Consumes: i campi `expires_on` / `expiry` della rotta (Task 4).
- Produces: `PantryItem.expires_on: string | null` e
  `PantryItem.expiry: ExpiryState | null` con
  `type ExpiryState = "soon" | "expired"`;
  `formatExpiry(expires_on: string, expiry: ExpiryState | null): string`;
  `EXPIRY_TONE: Record<ExpiryState, string>`;
  `<ExpiryChip expiresOn={string} expiry={ExpiryState | null} />`.

- [ ] **Step 1: Scrivi il test che fallisce**

`frontend/src/components/ui/ExpiryChip.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ExpiryChip } from "./ExpiryChip";

describe("ExpiryChip", () => {
  it("dice quando scade, al futuro", () => {
    render(<ExpiryChip expiresOn="2026-09-28" expiry="soon" />);
    expect(screen.getByText("Scade il 28/09/2026")).toBeInTheDocument();
  });

  it("al passato cambia tempo verbale, non genere", () => {
    // «scaduto» e «scaduta» costringerebbero a scegliere fra «Fage Total 0%» e
    // «passata di pomodoro», e una delle due sarebbe sempre sbagliata. L'imperfetto
    // non concorda con niente.
    render(<ExpiryChip expiresOn="2026-09-20" expiry="expired" />);
    expect(screen.getByText("Scadeva il 20/09/2026")).toBeInTheDocument();
  });

  it("senza verdetto la data si legge comunque, in tinta neutra", () => {
    render(<ExpiryChip expiresOn="2026-12-31" expiry={null} />);
    expect(screen.getByText("Scade il 31/12/2026")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Guarda il rosso**

Run (da `frontend/`): `npx vitest run src/components/ui/ExpiryChip.test.tsx`
Expected: FAIL — il modulo `./ExpiryChip` non esiste.

- [ ] **Step 3: Il codice minimo**

In `frontend/src/index.css`, dentro `@theme`, dopo i token di `low`:

```css
  /* La scadenza ha un colore suo, e non è il giallo: la zona gialla del cursore vuol
     già dire «comincia a mancare» (LOW_MAX_FILL), e due fatti diversi sullo stesso
     colore non ne dicono più nessuno. Due intensità e non due colori: «sta per
     scadere» e «scaduto» sono lo stesso fatto a due distanze. */
  --color-expiry: #5b45a8;
  --color-expiry-tint: #efeaf9;
```

`frontend/src/features/pantry/expiryLabels.ts`:

```ts
import type { ExpiryState } from "../../domain/types";

/** La data come si legge, e il tempo verbale che porta la differenza. Nessuna delle
 * due forme concorda in genere: la riga può chiamarsi «Fage Total 0%» o «passata di
 * pomodoro», e un participio ne sbaglierebbe sempre una. */
export function formatExpiry(expiresOn: string, expiry: ExpiryState | null): string {
  const quando = new Date(expiresOn).toLocaleDateString("it-IT");
  return expiry === "expired" ? `Scadeva il ${quando}` : `Scade il ${quando}`;
}

/** Tinta leggera mentre si avvicina, piena da scaduta. Sta qui e non accanto al
 * componente per la ragione scritta in statusLabels.ts: un export costante accanto a
 * un componente rompe il fast refresh. */
export const EXPIRY_TONE: Record<ExpiryState, string> = {
  soon: "bg-expiry-tint text-expiry",
  expired: "bg-expiry text-white",
};
```

`frontend/src/components/ui/ExpiryChip.tsx`:

```tsx
import { EXPIRY_TONE, formatExpiry } from "../../features/pantry/expiryLabels";
import type { ExpiryState } from "../../domain/types";

/** La scadenza accanto allo stato, non al posto suo: due pastiglie dicono due fatti
 * diversi. Senza verdetto la data resta leggibile in tinta neutra — è
 * un'informazione, non un allarme, finché il server non dice altro. */
export function ExpiryChip({
  expiresOn,
  expiry,
}: {
  expiresOn: string;
  expiry: ExpiryState | null;
}) {
  const tono = expiry ? EXPIRY_TONE[expiry] : "bg-page text-ink-soft";
  return (
    <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-medium ${tono}`}>
      {formatExpiry(expiresOn, expiry)}
    </span>
  );
}
```

E in `frontend/src/domain/types.ts`, dentro `PantryItem` dopo `note`:

```ts
  /** La scadenza di questo barattolo, `null` se non è stata scritta. */
  expires_on: string | null;
  /** Il verdetto, già preso dal server: la soglia dei sette giorni non vive qui. */
  expiry: ExpiryState | null;
```

più `export type ExpiryState = "soon" | "expired";` accanto a `PantryStatus`.

- [ ] **Step 4: Guarda il verde, e i tipi**

Run: `npx vitest run src/components/ui/ExpiryChip.test.tsx`
Expected: PASS.
Run: `npm run typecheck`
Expected: rosso dove un `PantryItem` è costruito con il tipo dichiarato — aggiungere
i due campi lì fa parte di questo task.

**E poi, a mano, la parte che il controllo non vede.** Diversi fixture di questo
progetto sono letterali JSON senza tipo (`ITEMS` in `PantryScreen.test.tsx` è uno):
passano per `Response.json()`, quindi nessun `tsc` li guarda e restano indietro in
silenzio. È la settima lezione di `CLAUDE.md`, quella che ha fatto passare un oggetto
a cui mancavano quattro campi. Cerca con `grep -rn "fill_percent" frontend/src` i
posti dove una voce di dispensa è scritta a mano e allineali. Non usare
`tsc --noEmit`: su questo progetto esce 0 sempre.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/index.css frontend/src/domain/types.ts frontend/src/features/pantry/expiryLabels.ts frontend/src/components/ui/ExpiryChip.tsx frontend/src/components/ui/ExpiryChip.test.tsx
git commit -m "feat: la pastiglia della scadenza, con un colore suo a due intensità"
```

---

### Task 8: La riga di dispensa scrive e corregge

**Files:**
- Modify: `frontend/src/features/pantry/api.ts`,
  `frontend/src/features/pantry/PantryRow.tsx`,
  `frontend/src/features/pantry/PantryScreen.tsx`
- Test: `frontend/src/features/pantry/PantryScreen.test.tsx`

**Interfaces:**
- Consumes: `ExpiryChip` (Task 7), la PATCH (Task 5).
- Produces: `patchPantryItem(id, { expires_on?: string | null })`; `PantryRow` prende
  `onExpiry: (expiresOn: string | null) => Promise<PantryItem>`.

- [ ] **Step 1: Scrivi i test che falliscono**

In `PantryScreen.test.tsx`, con la forma già usata lì per le altre mutazioni:

**Prima di tutto**, `ITEMS` in cima al file prende i due campi nuovi su ogni voce:
`expires_on: null, expiry: null`, e una delle tre — la mela, `ITEMS[2]`, id `"p3"` —
li porta valorizzati: `expires_on: "2026-09-28", expiry: "soon"`. Quell'array è un
letterale JSON senza tipo, quindi **nessun controllo dei tipi si accorgerà se resta
indietro**: è la settima lezione di `CLAUDE.md`, ed è il motivo per cui questo passo
sta scritto qui invece che essere lasciato all'occhio.

```tsx
it("una voce con la scadenza la mostra sulla riga", async () => {
  stubRoutedFetch(() => [ITEMS, 200]);
  renderScreen();

  const riga = (await screen.findByText("mela")).closest("li")!;
  expect(within(riga).getByText("Scade il 28/09/2026")).toBeDefined();
});

it("una voce senza scadenza offre di scriverla", async () => {
  // il vuoto non deve costare niente, ma da qualche parte la strada deve esserci:
  // senza questo, chi ha saltato il momento dell'ingresso non può più scriverla —
  // ed è il vicolo cieco che la scelta del campo facoltativo voleva evitare
  stubRoutedFetch(() => [ITEMS, 200]);
  renderScreen();

  const riga = (await screen.findByText("Total 0%")).closest("li")!;
  expect(within(riga).getByRole("button", { name: /scadenza/i })).toBeDefined();
});

it("scrivere una data la manda al server, per la voce giusta", async () => {
  const fetchMock = stubRoutedFetch((_path, init) => {
    if (init?.method === "PATCH") return [{ ...ITEMS[0], expires_on: "2026-10-05" }, 200];
    return [ITEMS, 200];
  });
  renderScreen();

  const riga = (await screen.findByText("Total 0%")).closest("li")!;
  fireEvent.click(within(riga).getByRole("button", { name: /scadenza/i }));
  fireEvent.change(within(riga).getByLabelText(/scadenza/i), {
    target: { value: "2026-10-05" },
  });

  await waitFor(() => {
    const patch = fetchMock.mock.calls.find(
      ([, init]) => (init as RequestInit)?.method === "PATCH"
    );
    // ITEMS[0] ha id "p1": senza questa riga nessuna asserzione distinguerebbe
    // una PATCH mandata per la voce sbagliata
    expect(String(patch![0])).toContain("/pantry/p1");
    expect(JSON.parse(String((patch![1] as RequestInit).body))).toEqual({
      expires_on: "2026-10-05",
    });
  });
});

it("svuotare il campo manda null, che vuol dire cancellala", async () => {
  // e non `{}`: un corpo vuoto il backend lo rifiuta con 400 «niente da modificare»,
  // cioè la cancellazione fallirebbe dicendo che non c'era niente da fare
  const fetchMock = stubRoutedFetch((_path, init) => {
    if (init?.method === "PATCH") return [{ ...ITEMS[2], expires_on: null, expiry: null }, 200];
    return [ITEMS, 200];
  });
  renderScreen();

  const riga = (await screen.findByText("mela")).closest("li")!;
  fireEvent.click(within(riga).getByText("Scade il 28/09/2026"));
  fireEvent.change(within(riga).getByLabelText(/scadenza/i), { target: { value: "" } });

  await waitFor(() => {
    const patch = fetchMock.mock.calls.find(
      ([, init]) => (init as RequestInit)?.method === "PATCH"
    );
    expect(JSON.parse(String((patch![1] as RequestInit).body))).toEqual({ expires_on: null });
  });
});

it("una scrittura rifiutata lo dice, accanto alla voce giusta", async () => {
  // stesso principio del cursore: senza, la data torna da sé al valore del server e
  // l'utente resta convinto di averla scritta
  stubRoutedFetch((_path, init) => {
    if (init?.method === "PATCH") return [{ detail: "no" }, 500];
    return [ITEMS, 200];
  });
  renderScreen();

  const riga = (await screen.findByText("Total 0%")).closest("li")!;
  fireEvent.click(within(riga).getByRole("button", { name: /scadenza/i }));
  fireEvent.change(within(riga).getByLabelText(/scadenza/i), {
    target: { value: "2026-10-05" },
  });

  expect(await within(riga).findByRole("alert")).toHaveTextContent(/non sono riuscito/i);
  const altra = screen.getByText("Pesca").closest("li")!;
  expect(within(altra).queryByRole("alert")).toBeNull();
});
```

- [ ] **Step 2: Guarda il rosso**

Run: `npx vitest run src/features/pantry/PantryScreen.test.tsx`
Expected: FAIL — nessun pulsante «scadenza» nella riga.

- [ ] **Step 3: Il codice minimo**

`api.ts`: la firma di `patchPantryItem` accetta `expires_on?: string | null`.

`PantryRow.tsx`: uno stato locale `editingExpiry`; quando la data c'è, `ExpiryChip`
dentro un `<button>` che apre il campo; quando non c'è, un «+ scadenza» piccolo in
`text-ink-faint` nello stesso posto. Il campo è un `<input type="date">` con
un'etichetta vera («Scadenza di {itemLabel(item)}»), che al `change` chiama
`onExpiry(value || null)` e chiude. Gli errori riusano l'`Alert` già nella riga.

`PantryScreen.tsx`: una mutazione `expiry` sulla falsariga di `change`, con lo stesso
`onMutate: clearFailed` / `onSuccess: invalidate` / `onError: markFailed`, passata
come `onExpiry` a `PantryRow`.

- [ ] **Step 4: Guarda il verde**

Run: `npx vitest run` e `npm run typecheck`
Expected: PASS entrambi.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/pantry frontend/src/domain/types.ts
git commit -m "feat: la riga di dispensa mostra la scadenza, e la lascia correggere"
```

---

### Task 9: «Sistema la spesa» la chiede, dietro un tocco

**Files:**
- Modify: `frontend/src/features/stocking/api.ts`,
  `frontend/src/features/stocking/StockingScreen.tsx`
- Test: `frontend/src/features/stocking/StockingScreen.test.tsx`

**Interfaces:**
- Consumes: `POST /shopping-list/stock` con `expires_on` per entry (Task 6).
- Produces: `stockItems` con `expires_on: string | null` in ogni entry.

- [ ] **Step 1: Scrivi i test che falliscono**

```tsx
it("il campo della scadenza non c'è finché non lo si chiede", async () => {
  // dieci campi vuoti a video sono rumore permanente per chi la scadenza non la
  // scrive mai, e questo è già lo schermo più denso dell'app
  const user = userEvent.setup();
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(respond(CHECKED)));
  renderScreen();

  await screen.findByText("yogurt greco");
  expect(screen.queryByLabelText(/scadenza/i)).toBeNull();

  await user.click(screen.getAllByRole("button", { name: /scadenza/i })[0]);
  expect(screen.getByLabelText(/scadenza di yogurt greco/i)).toBeDefined();
});

it("la data scritta parte con la sistemazione, e le altre righe restano senza", async () => {
  const user = userEvent.setup();
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    if (String(url).includes("/stock")) return Promise.resolve(respond({ created: 2 }, 201));
    return Promise.resolve(respond(CHECKED));
  });
  vi.stubGlobal("fetch", spy);
  renderScreen();

  // entrambe le voci hanno già un ingrediente: si confermano sfuse
  for (const testo of ["yogurt greco", "mele"]) {
    const riga = (await screen.findByText(testo)).closest("li")!;
    await user.click(within(riga).getByRole("button", { name: /sfuso/i }));
  }
  const rigaYogurt = screen.getByText("yogurt greco").closest("li")!;
  await user.click(within(rigaYogurt).getByRole("button", { name: /scadenza/i }));
  fireEvent.change(within(rigaYogurt).getByLabelText(/scadenza di yogurt greco/i), {
    target: { value: "2026-10-02" },
  });
  await user.click(screen.getByRole("button", { name: /metti in dispensa/i }));

  await waitFor(() => {
    const stock = spy.mock.calls.find(([url]) => String(url).includes("/stock"));
    expect(JSON.parse(String((stock![1] as RequestInit).body)).entries).toEqual([
      expect.objectContaining({ shopping_item_id: "s1", expires_on: "2026-10-02" }),
      expect.objectContaining({ shopping_item_id: "s2", expires_on: null }),
    ]);
  });
});
```

`within`, `fireEvent` e `waitFor` vanno aggiunti all'import di
`@testing-library/react` in cima al file. Il pulsante di conferma si chiama «Metti in
dispensa» (`StockingScreen.tsx:605`, verificato) ed è disabilitato finché nessuna riga
è risolta — per questo il test conferma prima le due voci come sfuse.

- [ ] **Step 2: Guarda il rosso**

Run: `npx vitest run src/features/stocking/StockingScreen.test.tsx`
Expected: FAIL — nessun pulsante «scadenza».

- [ ] **Step 3: Il codice minimo**

Uno stato `const [expiry, setExpiry] = useState<Record<string, string>>({})` accanto a
`resolved`, e uno `openExpiryFor` per sapere quali righe hanno il campo aperto. Dentro
il `<li>`, sotto i pulsanti di risoluzione, un «+ scadenza» che apre un
`<input type="date">` etichettato con `item.raw_text`. Alla conferma,
`expires_on: expiry[item.id] ?? null` in ogni entry.

- [ ] **Step 4: Guarda il verde**

Run: `npx vitest run` e `npm run typecheck`
Expected: PASS entrambi.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/stocking
git commit -m "feat: la scadenza si scrive mentre sistemi la spesa, dietro un tocco"
```

---

### Task 10: Il browser vero

**Files:**
- Modify: `frontend/e2e/style.spec.ts`

**Interfaces:**
- Consumes: tutto il resto.
- Produces: un controllo che nessun test in jsdom può fare.

- [ ] **Step 1: Scrivi il controllo**

Nello stile del file (che fa già l'ingresso diretto in dispensa per avere una voce su
cui provare il cursore, e archivia quel che crea):

```ts
test("il campo data si vede, e la pastiglia della scadenza porta il suo colore", async ({
  page,
}) => {
  // La regola di base che veste i campi è una lista di esclusioni per selettore, e
  // `input[type="date"]` in quel foglio non compare mai. È già successo con
  // `input[type="text"]`: campi trasparenti su fondo grigio mentre 157 test in jsdom
  // passavano. Tailwind genera il CSS alla costruzione e jsdom non lo calcola.
  await page.getByRole("link", { name: "Dispensa" }).click();

  // stessa cautela del test sul cursore: una voce che nessun altro file nomina
  // («cipolla» è già di quel test, «pomodoro» di cooking.spec.ts), e archiviata in
  // fondo, perché la dispensa è stato condiviso e il database vive quanto lo stack
  await page.getByLabel("Aggiungi in dispensa").fill("carot");
  await page.getByRole("option", { name: /^Carota\b/ }).click();

  const riga = page.locator("li", { hasText: "carota" });
  await riga.getByRole("button", { name: /scadenza/i }).click();

  const campo = riga.getByLabel(/scadenza/i);
  await expect(campo).toBeVisible();
  // bianco sul fondo grigio, non trasparente: è il difetto che questo file esiste
  // per prendere
  await expect(campo).toHaveCSS("background-color", "rgb(255, 255, 255)");
  await expect(campo).toHaveCSS("border-top-width", "1px");
  // sotto i 16px iOS ingrandisce la pagina da solo quando il campo prende fuoco
  await expect(campo).toHaveCSS("font-size", "16px");

  // fra tre giorni: dentro la soglia, quindi il server deve rispondere «soon» e la
  // pastiglia prendere il token nuovo. La data si calcola qui e non si scrive a
  // mano, o il test scadrebbe da solo.
  const fraTreGiorni = new Date(Date.now() + 3 * 24 * 60 * 60 * 1000)
    .toISOString()
    .slice(0, 10);
  await campo.fill(fraTreGiorni);
  await campo.blur();

  // --color-expiry: #5b45a8. Se il token non arrivasse, la pastiglia resterebbe
  // del colore ereditato e direbbe quanto una scritta qualsiasi. Questo valore e
  // quello in index.css sono gli unici due posti dove il colore compare: se
  // l'occhio allo Step 3 lo fa cambiare, cambiano insieme.
  const pastiglia = riga.getByText(/^Scade il /);
  await expect(pastiglia).toHaveCSS("color", "rgb(91, 69, 168)");

  // la pulizia, come fa il test del cursore: senza, la dispensa cresce di una riga
  // a ogni esecuzione su uno stack riusato
  await riga.getByRole("button", { name: "Togli carota dalla dispensa" }).click();
  await expect(page.getByText("Tolta dalla dispensa")).toBeVisible();
});
```

«carota» è nel seme (`data/ingredients_seed.json`, verificato) e nessun altro file
di `e2e/` la nomina — gli altri lavorano su «pomodoro» e «cipolla». L'unica cosa da
far combaciare è l'etichetta del campo, che dev'essere la stessa scritta nel Task 8.

- [ ] **Step 2: Fallo girare**

```bash
E2E="docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml"
$E2E up -d --build --wait
$E2E exec -T backend python -m app.cli.seed
(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
$E2E down -v
```

Il `-p spena-e2e` e il `-f docker-compose.e2e.yml` vanno ripetuti in **ogni** comando:
un `down -v` sul progetto di default cancella il volume della dispensa vera.

- [ ] **Step 3: Guardalo con gli occhi, a 375px**

Nessun test dà questo giudizio: apri la dispensa a 375px con una voce che scade fra
tre giorni, una scaduta e una senza data. Tre domande, e sono quelle che decidono se
il colore scelto resta:

1. la pastiglia della scadenza si distingue **a colpo d'occhio** dal verde, dall'ambra
   di «quasi finito» e dal rosso della X?
2. le due pastiglie affiancate stanno sulla riga senza mandarla a capo male?
3. il «+ scadenza» sulle righe senza data è discreto abbastanza da non diventare
   rumore su venti righe?

Se la risposta a una delle tre è no, il valore da cambiare è il token in `index.css`
(e l'asserzione del colore in questo file, che è l'unico altro posto dove quel valore
compare). Riferisci cosa hai visto e cosa hai cambiato.

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/style.spec.ts frontend/src/index.css
git commit -m "test: la scadenza guardata in un browser vero, che è l'unico che la vede"
```

---

### Task 11: I documenti, insieme

**Files:**
- Modify: `CLAUDE.md`, `docs/superpowers/specs/2026-09-11-spena-design.md`,
  `docs/prossimi-passi.md`

**Interfaces:**
- Consumes: il lavoro in piedi.
- Produces: niente codice.

- [ ] **Step 1: La decisione fondante 1 in `CLAUDE.md`**

Smette di dire che la dispensa non conosce «date di scadenza». Dice: la dispensa
conosce una data di scadenza facoltativa per elemento, che **non entra in
`status_for_fill` né in nessun giudizio di disponibilità** — è un segnale sulla riga.
E dice il perché, che è l'argomento di D5: una quantità va *mantenuta* e mente il
giorno che smetti; una scadenza si scrive una volta sola e non si tocca più. `fill_percent`
è già il precedente citato lì accanto.

- [ ] **Step 2: Il §2 della spec madre**

`docs/superpowers/specs/2026-09-11-spena-design.md`, la stessa cosa e nello stesso
commit: è il documento d'origine, e due copie che divergono sono peggio di una sola
sbagliata.

- [ ] **Step 3: `docs/prossimi-passi.md`**

S7 da `[D]` a fatto con la data, e in Parte VIII l'ordine aggiornato. Scrivi quel che
si è **misurato** — cosa hai guardato a 375px, cosa hai cambiato del colore — non quel
che si è fatto.

- [ ] **Step 4: L'ultima suite, tutta**

```bash
cd backend && .venv/bin/python -m pytest -q
cd ../frontend && npx vitest run && npm run typecheck
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md docs/
git commit -m "docs: la dispensa conosce una scadenza, e la decisione fondante 1 lo dice"
```
