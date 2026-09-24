# R4 — Import completo: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendere il ricettario capace di reggere le 8.469 ricette di GialloZafferano, e
dare all'import un comando che svuota la sitemap da solo. Il lancio vero resta a un
runbook.

**Architecture:** Il seme smette di caricare ricette per default, e un comando nuovo
toglie quelle di semina dalla produzione. `import_gz --tutto` riusa le funzioni
interne di `run_import`, estratte, a lotti di 50, con i termini già chiesti esclusi.
Nel ramo senza ricerca, la soglia dei mancanti scende in SQL come appartenenza a
insiemi che `rules.py` ha già deciso, e ordine e paginazione con lei. Il frontend
pagina con `useInfiniteQuery` e un «Mostra altre».

**Tech Stack:** FastAPI, SQLAlchemy async, Postgres 16, pytest + respx; React 19,
TanStack Query 5, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-24-import-completo-design.md`

## Global Constraints

- Test su Postgres vero: `docker compose up -d db`, poi da `backend/`
  `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m pytest` (il PATH serve ai test che
  lanciano `alembic` come sottoprocesso).
- Frontend: `npx vitest run`, `npm run typecheck` (mai `tsc --noEmit`).
- Testi per l'utente e commenti in italiano, identificatori in inglese.
- Mai un vicolo cieco: ogni errore nuovo lascia una strada per continuare.
- La regola primario/secondario vive solo in `backend/app/domain/rules.py`.
- Nessuna chiamata di rete nei test: respx per la fonte, `llm_fakes` per l'LLM.
- Niente esecuzione in produzione: deploy, cancellazione e import sono nel runbook.

---

### Task 1: Il seme carica le ricette solo se glielo si chiede

**Files:**
- Modify: `backend/app/cli/seed.py` (`main`, costanti dei flag)
- Test: `backend/tests/test_seed.py`
- Modify: `README.md` (avvio locale ed e2e), `docs/prossimi-passi.md` (Parte IX)

**Interfaces:**
- Produces: `FLAG_CON_RICETTE = "--con-ricette"`; `seed.main()` solleva
  `SystemExit(1)` su un flag sconosciuto o contraddittorio.

- [ ] **Step 1: I test.** In `tests/test_seed.py` si sostituiscono i tre test di `main`
  con questi (stesso `_SessioneDiTest` già nel file):

```python
async def _main_con(argv, db_session, monkeypatch):
    from app.cli import seed as modulo_seme

    monkeypatch.setattr(modulo_seme, "SessionLocal", lambda: _SessioneDiTest(db_session))
    monkeypatch.setattr(sys, "argv", ["app.cli.seed", *argv])
    await modulo_seme.main()
    ingredients = list((await db_session.execute(select(Ingredient))).scalars())
    recipes = list((await db_session.execute(select(Recipe))).scalars())
    return ingredients, recipes


async def test_main_senza_flag_carica_solo_l_anagrafica(db_session, monkeypatch):
    """Da R4 il default è quello sicuro in produzione: rilanciare il seme non fa
    tornare le ricette di semina cancellate."""
    ingredients, recipes = await _main_con([], db_session, monkeypatch)
    assert len(ingredients) > 0
    assert recipes == []


async def test_main_con_solo_ingredienti_resta_accettato(db_session, monkeypatch):
    ingredients, recipes = await _main_con(["--solo-ingredienti"], db_session, monkeypatch)
    assert len(ingredients) > 0
    assert recipes == []


async def test_main_con_ricette_carica_anche_le_ricette(db_session, monkeypatch):
    """Sviluppo ed e2e le vogliono: si chiedono per nome."""
    ingredients, recipes = await _main_con(["--con-ricette"], db_session, monkeypatch)
    assert len(ingredients) > 0
    assert len(recipes) > 0


@pytest.mark.parametrize(
    "argv", [["--solo-ingredient"], ["--con-ricette", "--solo-ingredienti"]]
)
async def test_main_rifiuta_un_flag_sbagliato_con_codice_1(db_session, monkeypatch, capsys, argv):
    """Un refuso prima usciva con 0: uno script che guarda il codice d'uscita non
    se ne accorgeva (Parte X). E non si tocca niente."""
    with pytest.raises(SystemExit) as uscita:
        await _main_con(argv, db_session, monkeypatch)
    assert uscita.value.code == 1
    assert "--con-ricette" in capsys.readouterr().out
    assert list((await db_session.execute(select(Ingredient))).scalars()) == []
```

- [ ] **Step 2:** `pytest tests/test_seed.py -q` → falliscono i nuovi (il default
  carica ancora le ricette, `--con-ricette` è sconosciuto).

- [ ] **Step 3: `main`.** In `app/cli/seed.py` si sostituiscono `FLAG_SOLO_INGREDIENTI`
  e l'inizio di `main()` fino a `solo_ingredienti = …` compreso:

```python
FLAG_CON_RICETTE = "--con-ricette"
# Il default da R4, quindi non serve più: resta accettato perché è scritto nel README
# e nelle mani di chi ha fatto i deploy precedenti.
FLAG_SOLO_INGREDIENTI = "--solo-ingredienti"
FLAGS = (FLAG_CON_RICETTE, FLAG_SOLO_INGREDIENTI)


async def main() -> None:
    # Da R4 il seme carica le ricette solo con `--con-ricette`: in produzione le
    # ricette di semina si cancellano (`app.cli.drop_seed_recipes`), e un seme
    # rilanciato senza pensarci non deve rimetterle. Sviluppo ed e2e le chiedono.
    #
    # Un argomento che comincia per `--` e non è uno dei flag viene rifiutato con
    # codice 1: un refuso passato per «nessun flag» farebbe una passata diversa da
    # quella chiesta, e uno script che guarda il codice d'uscita deve vederlo.
    sconosciuti = [arg for arg in sys.argv[1:] if arg.startswith("--") and arg not in FLAGS]
    if sconosciuti:
        print(f"argomento sconosciuto: {sconosciuti[0]}. Valori validi: {', '.join(FLAGS)}")
        raise SystemExit(1)
    if FLAG_CON_RICETTE in sys.argv and FLAG_SOLO_INGREDIENTI in sys.argv:
        print(f"{FLAG_CON_RICETTE} e {FLAG_SOLO_INGREDIENTI} si contraddicono: scegline uno.")
        raise SystemExit(1)
    solo_ingredienti = FLAG_CON_RICETTE not in sys.argv
```

  Il resto di `main()` resta com'è.

- [ ] **Step 4:** `pytest tests/test_seed.py -q` → verde. Poi tutta la suite: qualunque
  altro test che chiami `main()` senza flag aspettandosi ricette va aggiornato a
  `--con-ricette`.

- [ ] **Step 5: i comandi documentati.** `README.md`: nell'avvio locale
  `python -m app.cli.seed --con-ricette   # 187 ingredienti, 26 ricette`; nel blocco
  e2e `$E2E exec -T backend python -m app.cli.seed --con-ricette`; il blocco di
  produzione resta `seed --solo-ingredienti`, con una riga che dice che da R4 è anche
  il default. Stessa correzione nel blocco e2e di `docs/prossimi-passi.md`, Parte IX.

- [ ] **Step 6: Commit** `R4: il seme carica le ricette solo con --con-ricette`.

### Task 2: `drop_seed_recipes`

**Files:**
- Create: `backend/app/cli/drop_seed_recipes.py`
- Test: `backend/tests/test_drop_seed_recipes_cli.py`

**Interfaces:**
- Produces: `SEED_SOURCE_REF = "seme iniziale"`;
  `async def drop_seed_recipes(session, *, confirm: bool, log=print) -> int`, cioè il
  numero di ricette cancellate (0 senza `confirm`).

- [ ] **Step 1: I test.**

```python
from sqlalchemy import select

from app.cli.drop_seed_recipes import SEED_SOURCE_REF, drop_seed_recipes
from app.db.models.recipe import CookingEvent, Recipe


def _ricetta(titolo: str, source: str, source_ref: str | None) -> Recipe:
    return Recipe(title=titolo, instructions="Cuoci.", source=source, source_ref=source_ref)


async def _prepara(db_session):
    seme = _ricetta("Pasta al pomodoro", "dataset", SEED_SOURCE_REF)
    importata = _ricetta("Amatriciana", "dataset", "https://ricette.giallozafferano.it/A.html")
    scritta = _ricetta("Bozza", "ai", None)
    db_session.add_all([seme, importata, scritta])
    await db_session.flush()
    db_session.add(CookingEvent(recipe_id=seme.id, snapshot={"title": seme.title}))
    await db_session.flush()
    return seme, importata, scritta


async def _titoli(db_session) -> set[str]:
    return set((await db_session.execute(select(Recipe.title))).scalars())


async def test_senza_conferma_dice_cosa_toglierebbe_e_non_tocca_niente(db_session):
    await _prepara(db_session)
    righe: list[str] = []

    cancellate = await drop_seed_recipes(db_session, confirm=False, log=righe.append)

    assert cancellate == 0
    assert await _titoli(db_session) == {"Pasta al pomodoro", "Amatriciana", "Bozza"}
    testo = "\n".join(righe)
    assert "Pasta al pomodoro" in testo
    assert "1 cottura" in testo
    assert "--conferma" in testo


async def test_con_conferma_toglie_solo_quelle_di_semina(db_session):
    seme, *_ = await _prepara(db_session)

    cancellate = await drop_seed_recipes(db_session, confirm=True, log=lambda _: None)

    assert cancellate == 1
    assert await _titoli(db_session) == {"Amatriciana", "Bozza"}
    evento = (await db_session.execute(select(CookingEvent))).scalar_one()
    # la cottura resta nello storico, con la sua fotografia, senza ricetta
    await db_session.refresh(evento)
    assert evento.recipe_id is None
    assert evento.snapshot == {"title": "Pasta al pomodoro"}


async def test_rilanciarlo_non_trova_piu_niente(db_session):
    await _prepara(db_session)
    await drop_seed_recipes(db_session, confirm=True, log=lambda _: None)

    assert await drop_seed_recipes(db_session, confirm=True, log=lambda _: None) == 0
```

- [ ] **Step 2:** `pytest tests/test_drop_seed_recipes_cli.py -q` → errore di import.

- [ ] **Step 3: Il comando.**

```python
"""Toglie le ricette di semina, e prima dice cosa toglierebbe (R4).

Eseguire nel container del backend:

    python -m app.cli.drop_seed_recipes             # elenca e basta
    python -m app.cli.drop_seed_recipes --conferma  # cancella

Una ricetta di semina è `source = 'dataset'` con `source_ref = 'seme iniziale'`,
il valore che `data/recipes_seed.json` scrive su tutte e 26. Le ricette importate
portano un indirizzo, quelle scritte a mano o con l'AI non sono `dataset`: nessuna
delle due può essere presa per sbaglio.

Le righe della ricetta se ne vanno con lei (`ON DELETE CASCADE`). Le cotture no:
`cooking_events.recipe_id` è `ON DELETE SET NULL`, quindi la cottura resta nello
storico, con la sua fotografia della ricetta, e perde solo il collegamento.
"""

import argparse
import asyncio
from collections.abc import Callable

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.db.models.recipe import CookingEvent, Recipe, RecipeSource

SEED_SOURCE_REF = "seme iniziale"


async def drop_seed_recipes(
    session: AsyncSession, *, confirm: bool, log: Callable[[str], None] = print
) -> int:
    recipes = list(
        (
            await session.execute(
                select(Recipe)
                .where(
                    Recipe.source == RecipeSource.DATASET,
                    Recipe.source_ref == SEED_SOURCE_REF,
                )
                .order_by(Recipe.title)
            )
        ).scalars()
    )
    if not recipes:
        log("Nessuna ricetta di semina: niente da togliere.")
        return 0

    ids = [recipe.id for recipe in recipes]
    cooked = (
        await session.execute(
            select(func.count()).select_from(CookingEvent).where(CookingEvent.recipe_id.in_(ids))
        )
    ).scalar_one()
    for recipe in recipes:
        log(f"  {recipe.title}")
    parola = "cottura" if cooked == 1 else "cotture"
    log(
        f"{len(recipes)} ricette di semina; {cooked} {parola} resteranno nello storico "
        "senza ricetta collegata."
    )
    if not confirm:
        log("Niente cancellato: rilancia con --conferma per toglierle.")
        return 0

    await session.execute(delete(Recipe).where(Recipe.id.in_(ids)))
    log(f"Tolte {len(recipes)} ricette di semina.")
    return len(recipes)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Toglie le ricette di semina.")
    parser.add_argument("--conferma", action="store_true", help="cancella davvero")
    arguments = parser.parse_args()
    async with SessionLocal() as session:
        await drop_seed_recipes(session, confirm=arguments.conferma)
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4:** `pytest tests/test_drop_seed_recipes_cli.py -q` → verde.
- [ ] **Step 5: Commit** `R4: drop_seed_recipes, che prima elenca e cancella solo con --conferma`.

### Task 3: `pending_terms` sa escludere

**Files:**
- Modify: `backend/app/repositories/imports.py:97-112`
- Test: `backend/tests/repositories/test_imports_repository.py` (o il file che già
  prova `pending_terms`: `grep -rln pending_terms backend/tests`)

**Interfaces:**
- Produces: `pending_terms(session, source, limit=20, exclude: Collection[uuid.UUID] = ())`.

- [ ] **Step 1: Il test.**

```python
async def test_pending_terms_salta_quelli_esclusi(db_session):
    from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
    from app.repositories.imports import pending_terms

    frequente = ImportTerm(source=GIALLOZAFFERANO, term_key="a", display_name="A",
                           occurrences=9, decision=TermDecision.PENDING)
    raro = ImportTerm(source=GIALLOZAFFERANO, term_key="b", display_name="B",
                      occurrences=1, decision=TermDecision.PENDING)
    db_session.add_all([frequente, raro])
    await db_session.flush()

    assert [t.term_key for t in await pending_terms(db_session, GIALLOZAFFERANO, limit=1)] == ["a"]
    assert [
        t.term_key
        for t in await pending_terms(db_session, GIALLOZAFFERANO, limit=1, exclude={frequente.id})
    ] == ["b"]
```

- [ ] **Step 2:** fallisce (`exclude` sconosciuto).
- [ ] **Step 3:**

```python
async def pending_terms(
    session: AsyncSession,
    source: str,
    limit: int = 20,
    exclude: Collection[uuid.UUID] = (),
) -> list[ImportTerm]:
    """I termini da decidere, da quello che sblocca più ricette.

    È l'unico ordine in cui vale la pena revisionare: più della metà dei termini
    compare in una ricetta sola, e decidere prima i frequenti è ciò che fa vedere il
    ricettario crescere.

    `exclude` serve a `import_gz --tutto`: un termine a cui l'AI ha già risposto
    qualcosa di non verificabile resta in coda e resta primo per frequenza, e senza
    esclusione ogni giro rifarebbe le stesse domande mentre il resto della coda non
    verrebbe mai chiesto.
    """
    statement = select(ImportTerm).where(
        ImportTerm.source == source, ImportTerm.decision == TermDecision.PENDING
    )
    if exclude:
        statement = statement.where(ImportTerm.id.not_in(list(exclude)))
    rows = await session.execute(
        statement.order_by(ImportTerm.occurrences.desc(), ImportTerm.display_name).limit(limit)
    )
    return list(rows.scalars())
```

  (import di `Collection` da `collections.abc` e di `uuid` se mancano.)
- [ ] **Step 4:** verde.
- [ ] **Step 5: Commit** `R4: pending_terms sa escludere i termini già chiesti`.

### Task 4: `import_gz --tutto`

**Files:**
- Modify: `backend/app/cli/import_gz.py`
- Test: `backend/tests/test_import_gz_cli.py` (in coda al file)

**Interfaces:**
- Consumes: `pending_terms(..., exclude=...)` (Task 3).
- Produces: `async def run_all(session, *, client, sleep=asyncio.sleep,
  llm_client=None, chunk=DEFAULT_LIMIT, log=_log) -> ImportRun`;
  `MAX_FRUITLESS_ROUNDS = 2`; `main()` con `--tutto`.

- [ ] **Step 1: I test.**

```python
SITEMAP_TRE_PAGINE_DIVERSE = SITEMAP  # Uno, Due, Tre


@respx.mock
async def test_tutto_svuota_la_sitemap_leggendola_una_volta(db_session):
    sitemap = respx.get(RECIPE_SITEMAP).mock(return_value=httpx.Response(200, text=SITEMAP))
    for nome in ("Uno", "Due", "Tre"):
        respx.get(f"https://ricette.giallozafferano.it/{nome}.html").mock(
            return_value=httpx.Response(200, text=PAGINA.replace("TITOLO", nome))
        )
    righe: list[str] = []

    async with build_client() as client:
        esito = await import_gz.run_all(
            db_session, client=client, sleep=nessuna_pausa, chunk=2, log=righe.append
        )

    assert esito.taken == 3
    assert sitemap.call_count == 1
    # una riga di avanzamento per lotto: 2 + 1
    assert sum("pagine" in riga for riga in righe) == 2


@respx.mock
async def test_tutto_non_richiede_un_termine_gia_chiesto(db_session, monkeypatch):
    """Il primo per frequenza ha una risposta non verificabile: senza esclusione
    ogni giro richiederebbe lui e il secondo non verrebbe mai chiesto."""
    from app.core.config import get_settings
    from app.db.models.recipe_import import ImportTerm, TermDecision

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    monkeypatch.setattr(import_gz, "MAX_TERMS_PER_RUN", 1)
    try:
        db_session.add(
            Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
        )
        await db_session.flush()
        client = fonte_finta_con_una_ricetta()
        llm = ScriptedLlm(
            # "rigatoni" → un ingrediente che non esiste: non verificabile, resta in coda
            {"Rigatoni": llm_map("non-esiste"), "Speck": llm_create("speck", "Speck", "carne")}
        )
        esito = await import_gz.run_all(
            db_session, client=client, sleep=nessuna_pausa, llm_client=llm,
            log=lambda _: None,
        )

        speck = (
            await db_session.execute(select(ImportTerm).where(ImportTerm.display_name == "Speck"))
        ).scalar_one()
        assert speck.decision != TermDecision.PENDING
        assert esito.decided == 1
    finally:
        get_settings.cache_clear()


@respx.mock
async def test_tutto_senza_chiave_finisce_e_lascia_i_termini_in_coda(db_session, monkeypatch):
    from app.core.config import get_settings
    from app.db.models.recipe_import import ImportTerm, TermDecision

    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    try:
        client = fonte_finta_con_una_ricetta()
        esito = await import_gz.run_all(
            db_session, client=client, sleep=nessuna_pausa, log=lambda _: None
        )
        assert esito.taken == 1
        in_coda = (
            await db_session.execute(
                select(ImportTerm).where(ImportTerm.decision == TermDecision.PENDING)
            )
        ).scalars().all()
        assert in_coda != []
    finally:
        get_settings.cache_clear()


async def test_tutto_e_limit_insieme_sono_un_errore(monkeypatch):
    import sys

    monkeypatch.setattr(sys, "argv", ["app.cli.import_gz", "--tutto", "--limit", "5"])
    with pytest.raises(SystemExit) as uscita:
        await import_gz.main()
    assert uscita.value.code == 2
```

  Nota sul secondo test: con `MAX_TERMS_PER_RUN = 1` e l'esclusione, il primo giro
  chiede Rigatoni (più frequente o primo per nome a parità: entrambi compaiono in una
  ricetta, e l'ordine a parità è per `display_name`, «Rigatoni» < «Speck»), il secondo
  chiede Speck. Senza esclusione il secondo giro richiederebbe Rigatoni.

- [ ] **Step 2:** falliscono (`run_all` non esiste).

- [ ] **Step 3: Le funzioni interne.** In `import_gz.py`, il corpo di `run_import` si
  divide in tre funzioni, e `run_import` le compone. Il codice del ciclo sulle pagine
  e dei suoi messaggi si **sposta**, non si riscrive:

```python
import uuid
from datetime import datetime

# Quanti giri di fila senza una sola decisione prima di smettere di chiedere: il
# credito finito (402), il modello giù e le risposte non verificabili si
# somigliano tutti, e distinguerli non serve — rilanciare più tardi riprende.
MAX_FRUITLESS_ROUNDS = 2


def _log(message: str) -> None:
    # `flush`: in background il log si legge mentre il comando gira, non alla fine
    print(message, flush=True)


@dataclass(frozen=True)
class _Taken:
    taken: int = 0
    skipped: int = 0
    stopped_early: bool = False


@dataclass(frozen=True)
class _Settled:
    decided: int = 0
    still_pending: int = 0
    new_units: int = 0
    asked: frozenset[uuid.UUID] = frozenset()


async def _new_urls(session: AsyncSession, client: httpx.AsyncClient) -> list[str] | None:
    """Gli indirizzi della sitemap non ancora presi, o `None` se la fonte dice di no."""
    try:
        urls = await fetch_sitemap(client)
    except SourceUnavailable as exc:
        print(f"fonte dice di fermarsi: {exc}")
        print("Nessuna pagina presa oggi. Rilancia più tardi: costa nulla e riprende da dove era.")
        return None
    already = await known_urls(session, GIALLOZAFFERANO)
    # (il commento esistente su `dict.fromkeys` si sposta qui)
    return list(dict.fromkeys(url for url in urls if url not in already))


async def _take_pages(
    session: AsyncSession,
    client: httpx.AsyncClient,
    urls: list[str],
    sleep: Callable[[float], Awaitable[None]],
) -> _Taken:
    # il ciclo `for url in todo:` di oggi, invariato, su `urls`, con i suoi
    # contatori locali; alla fine:
    return _Taken(taken=taken, skipped=skipped, stopped_early=stopped_early)


async def _settle(
    session: AsyncSession,
    llm_client: object | None,
    *,
    exclude: frozenset[uuid.UUID] = frozenset(),
    ask_ai: bool = True,
) -> _Settled:
    """Allinea i termini, fa decidere l'AI, materializza: il lavoro dopo le pagine."""
    # i termini si allineano sempre, anche dopo un giro fermato a metà: le pagine
    # prese devono comparire in coda, altrimenti il lavoro fatto non si vede
    await sync_terms(session, GIALLOZAFFERANO)

    # (il commento esistente su «Poi l'AI decide…»)
    decided = 0
    still_pending = 0
    waiting = (
        await pending_terms(
            session, GIALLOZAFFERANO, limit=MAX_TERMS_PER_RUN, exclude=exclude
        )
        if ask_ai
        else []
    )
    if waiting:
        try:
            outcome = await decide_terms(session, waiting, client=llm_client)
            decided = outcome.applied
            still_pending = outcome.still_pending
        except LlmUnavailable as exc:
            still_pending = len(waiting)
            print(f"riconoscimento non disponibile ({exc}): i termini restano in coda.")

    # (il commento esistente sulle unità)
    before = await _count_units(session)
    await materialize_ready(session, GIALLOZAFFERANO)
    return _Settled(
        decided=decided,
        still_pending=still_pending,
        new_units=await _count_units(session) - before,
        asked=frozenset(term.id for term in waiting),
    )


async def run_import(session, *, limit, client, sleep=asyncio.sleep, llm_client=None) -> ImportRun:
    """(docstring di oggi)"""
    urls = await _new_urls(session, client)
    pages = _Taken(stopped_early=True) if urls is None else await _take_pages(
        session, client, urls[:limit], sleep
    )
    settled = await _settle(session, llm_client)
    return ImportRun(
        taken=pages.taken, skipped=pages.skipped, stopped_early=pages.stopped_early,
        decided=settled.decided, still_pending=settled.still_pending,
        new_units=settled.new_units,
    )
```

- [ ] **Step 4:** tutta `tests/test_import_gz_cli.py` tranne i test nuovi → verde. Il
  refactor non deve cambiare niente di osservabile.

- [ ] **Step 5: `run_all`.**

```python
async def run_all(
    session: AsyncSession,
    *,
    client: httpx.AsyncClient,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    llm_client: object | None = None,
    chunk: int = DEFAULT_LIMIT,
    log: Callable[[str], None] = _log,
) -> ImportRun:
    """Tutta la sitemap, a lotti, poi i termini rimasti (R4).

    La sitemap si legge una volta sola. Dopo ogni lotto si allinea, si decide e si
    materializza, e si committa: il ricettario cresce mentre il comando gira, e un
    comando interrotto ha perso al massimo il lotto in corso. Un termine chiesto in
    questo giro non si richiede in questo giro. Quando l'AI non decide niente per
    `MAX_FRUITLESS_ROUNDS` giri di fila smette di chiederle, e il resto va avanti:
    rilanciare più tardi riprende dai termini in coda.
    """
    urls = await _new_urls(session, client)
    todo = urls or []
    taken = skipped = decided = new_units = still_pending = 0
    stopped_early = urls is None
    asked: set[uuid.UUID] = set()
    fruitless = 0

    async def settle_and_report(label: str) -> _Settled:
        nonlocal decided, new_units, still_pending, fruitless
        ask_ai = fruitless < MAX_FRUITLESS_ROUNDS
        settled = await _settle(session, llm_client, exclude=frozenset(asked), ask_ai=ask_ai)
        await session.commit()
        asked.update(settled.asked)
        decided += settled.decided
        new_units += settled.new_units
        still_pending = settled.still_pending
        if settled.asked:
            fruitless = 0 if settled.decided else fruitless + 1
            if fruitless == MAX_FRUITLESS_ROUNDS:
                log("l'AI non decide più niente: smetto di chiederle. Rilancia più tardi.")
        totals = await counts(session, GIALLOZAFFERANO)
        log(
            f"{datetime.now():%H:%M} {label} · termini decisi {decided}, "
            f"in coda {totals.pending_terms} · ricette {totals.imported}"
        )
        return settled

    for start in range(0, len(todo), chunk):
        pages = await _take_pages(session, client, todo[start : start + chunk], sleep)
        taken += pages.taken
        skipped += pages.skipped
        await settle_and_report(
            f"pagine {min(start + chunk, len(todo))}/{len(todo)} "
            f"(prese {taken}, scartate {skipped})"
        )
        if pages.stopped_early:
            stopped_early = True
            break

    while not stopped_early and fruitless < MAX_FRUITLESS_ROUNDS:
        settled = await settle_and_report("solo termini")
        if not settled.asked:
            break

    return ImportRun(
        taken=taken, skipped=skipped, stopped_early=stopped_early,
        decided=decided, still_pending=still_pending, new_units=new_units,
    )
```

  Una riga di avanzamento per lotto contiene «pagine»; quelle della fase termini
  dicono «solo termini». Il test 1 conta le prime.

- [ ] **Step 6: `main`.**

```python
async def main() -> None:
    parser = argparse.ArgumentParser(description="Scarica ricette da GialloZafferano.")
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument("--limit", type=int, default=None)
    modo.add_argument(
        "--tutto", action="store_true",
        help="tutta la sitemap a lotti, poi i termini in coda (R4)",
    )
    arguments = parser.parse_args()

    async with SessionLocal() as session:
        async with build_client() as client:
            if arguments.tutto:
                result = await run_all(session, client=client)
            else:
                result = await run_import(
                    session, limit=arguments.limit or DEFAULT_LIMIT, client=client
                )
        totals = await counts(session, GIALLOZAFFERANO)
        await session.commit()
    # (le stampe di riepilogo di oggi, invariate)
```

- [ ] **Step 7:** `pytest tests/test_import_gz_cli.py -q` → verde. Il docstring del
  modulo nomina `--tutto` accanto a `--limit`.

- [ ] **Step 8: Commit** `R4: import_gz --tutto svuota la sitemap a lotti`.

### Task 5: La soglia in SQL, il ricettario intero, l'offset

**Files:**
- Modify: `backend/app/services/recipe_search.py` (`_requirements_by_recipe`,
  `search_recipes`, nuove `_unmet_line` e `_browse`)
- Modify: `backend/app/api/recipes.py` (parametro `offset`)
- Test: `backend/tests/services/test_recipe_search.py`, `backend/tests/api/test_recipes.py`

**Interfaces:**
- Produces: `search_recipes(..., offset: int = 0)`; `GET /recipes/search?offset=N`.

- [ ] **Step 1: I test di servizio.**

```python
async def test_la_soglia_in_sql_coincide_con_la_regola(db_session):
    """Ogni combinazione di ruolo e stato in dispensa: le ricette che il filtro SQL
    lascia passare con soglia 0 sono esattamente quelle che `rules.py` dice
    cucinabili. Se un giorno la regola cambiasse, il filtro non potrebbe restare
    indietro in silenzio."""
    from app.db.models.ingredient import Ingredient, IngredientCategory
    from app.db.models.pantry import PantryItem
    from app.db.models.recipe import Recipe, RecipeIngredient
    from app.domain.rules import (
        Availability, IngredientRole, PantryStatus, availability_of, is_satisfied,
    )
    from app.services.recipe_search import search_recipes

    stati = {"assente": [], "disponibile": [PantryStatus.AVAILABLE],
             "quasi": [PantryStatus.LOW], "finito": [PantryStatus.FINISHED]}
    attese: dict[str, bool] = {}
    for nome, statuses in stati.items():
        ingrediente = Ingredient(name=f"ing {nome}", display_name=nome,
                                 category=IngredientCategory.VERDURA)
        db_session.add(ingrediente)
        await db_session.flush()
        for status in statuses:
            db_session.add(PantryItem(ingredient_id=ingrediente.id, status=status))
        disponibilita = availability_of(statuses) if statuses else Availability.MISSING
        for ruolo in IngredientRole:
            titolo = f"{nome} {ruolo.value}"
            ricetta = Recipe(title=titolo, instructions="x", source="manual")
            db_session.add(ricetta)
            await db_session.flush()
            db_session.add(RecipeIngredient(recipe_id=ricetta.id,
                                            ingredient_id=ingrediente.id, role=ruolo.value))
            attese[titolo] = is_satisfied(ruolo, disponibilita)
    await db_session.flush()

    cucinabili = await search_recipes(db_session, max_missing=0, limit=100)

    assert {r.recipe.title for r in cucinabili} == {t for t, ok in attese.items() if ok}
    assert all(r.missing == 0 and r.cookable for r in cucinabili)


async def test_senza_parole_il_ricettario_si_sfoglia_tutto(db_session):
    """Prima il ramo senza ricerca guardava le 100 più recenti: la pagina dopo la
    centesima era vuota. Ora ogni ricetta si raggiunge, una volta sola."""
    from app.db.models.recipe import Recipe
    from app.services.recipe_search import search_recipes

    for numero in range(130):
        db_session.add(Recipe(title=f"Ricetta {numero:03d}", instructions="x", source="manual"))
    await db_session.flush()

    visti: list[str] = []
    for offset in range(0, 150, 30):
        pagina = await search_recipes(db_session, limit=30, offset=offset)
        visti += [r.recipe.title for r in pagina]

    assert len(visti) == 130
    assert len(set(visti)) == 130
    assert visti == sorted(visti)  # stessi mancanti (zero righe): poi il titolo


async def test_con_parole_l_offset_scorre_i_candidati(db_session):
    from app.db.models.recipe import Recipe
    from app.services.recipe_search import search_recipes

    for numero in range(5):
        db_session.add(Recipe(title=f"Zuppa {numero}", instructions="x", source="manual"))
    await db_session.flush()

    prima = await search_recipes(db_session, "zuppa", limit=3)
    dopo = await search_recipes(db_session, "zuppa", limit=3, offset=3)

    assert len(prima) == 3 and len(dopo) == 2
    assert not {r.recipe.id for r in prima} & {r.recipe.id for r in dopo}
```

  Test d'API in `tests/api/test_recipes.py`, con il client autenticato che i test
  vicini usano: due ricette, `GET /api/v1/recipes/search?limit=1&offset=1` → una sola
  ricetta, diversa da quella di `offset=0`; `offset=-1` → 422.

- [ ] **Step 2:** falliscono (`offset` sconosciuto; il ricettario si ferma a 100).

- [ ] **Step 3: `_requirements_by_recipe`**: la chiamata diventa
  `availability_map(session, list({row[1] for row in rows}))`, con un commento: un id
  per riga, duplicati compresi, sfondava i 32.767 parametri di asyncpg già intorno alle
  3.300 ricette (misurato il 2026-09-24).

- [ ] **Step 4: Il conteggio in SQL.**

```python
from sqlalchemy import and_, false, or_, true


def _unmet_line(availability: dict[uuid.UUID, Availability]):
    """La condizione SQL «questa riga manca», senza ricopiare la regola.

    `is_satisfied` decide, ruolo per ruolo, quali ingredienti della dispensa lo
    soddisfano; SQL chiede solo se l'ingrediente della riga sta in quell'insieme.
    Gli insiemi hanno al più la dimensione della dispensa, quindi i parametri restano
    pochi qualunque sia il ricettario. Un ingrediente fuori dalla dispensa è
    `MISSING`: se un giorno un ruolo si accontentasse anche di quello, la condizione
    si rovescia invece di mentire.
    """
    per_role = []
    for role in IngredientRole:
        if is_satisfied(role, Availability.MISSING):
            bad = [i for i, have in availability.items() if not is_satisfied(role, have)]
            unmet = RecipeIngredient.ingredient_id.in_(bad) if bad else false()
        else:
            good = [i for i, have in availability.items() if is_satisfied(role, have)]
            unmet = RecipeIngredient.ingredient_id.not_in(good) if good else true()
        per_role.append(and_(RecipeIngredient.role == role.value, unmet))
    return or_(*per_role)


async def _browse(
    session: AsyncSession,
    *,
    max_missing: int | None,
    category: str | None,
    ingredient_ids: list[uuid.UUID] | None,
    limit: int,
    offset: int,
) -> list[uuid.UUID]:
    """Il ricettario intero senza parole cercate: filtrato, ordinato e paginato in SQL.

    Sostituisce la piscina delle cento più recenti. Con 8.500 ricette la passata in
    Python costava un secondo per categoria e, sul ricettario intero, un errore
    (misurato il 2026-09-24): la sesta lezione di CLAUDE.md, arrivata. L'ordine è lo
    stesso che la pagina mostrava già — prima ciò che puoi cucinare, poi il titolo —
    ma adesso vale su tutto il ricettario, non su un campione.
    """
    availability = await availability_map(session)
    missing = func.count(RecipeIngredient.id).filter(_unmet_line(availability)).label("missing")
    statement = (
        select(Recipe.id, missing)
        .outerjoin(RecipeIngredient, RecipeIngredient.recipe_id == Recipe.id)
        .group_by(Recipe.id)
    )
    if category is not None:
        statement = statement.where(Recipe.category == category)
    if ingredient_ids:
        statement = _containing_all(statement, ingredient_ids)
    if max_missing is not None:
        statement = statement.having(missing <= max_missing)
    statement = statement.order_by(missing, Recipe.title, Recipe.id).offset(offset).limit(limit)
    return [row.id for row in (await session.execute(statement)).all()]
```

- [ ] **Step 5: `search_recipes`.** Firma con `offset: int = 0`. Il ramo `else` (senza
  parole) diventa:

```python
    else:
        candidate_ids = await _browse(
            session, max_missing=max_missing, category=category,
            ingredient_ids=ingredient_ids, limit=limit, offset=offset,
        )
        fused = {recipe_id: 0.0 for recipe_id in candidate_ids}
```

  Il resto della funzione resta, con due ritocchi: il filtro `max_missing` in Python
  resta (sul ramo senza parole è una conferma: SQL e regola sono lo stesso numero, e
  il test del passo 1 lo difende), e l'ordinamento finale e il taglio diventano:

```python
    if query and query.strip():
        # prima ciò che puoi davvero cucinare, poi la pertinenza
        results.sort(key=lambda r: (r.missing, -r.score, r.recipe.title))
        return results[offset : offset + limit]
    # senza parole l'ordine e la pagina li ha già decisi `_browse`, in SQL
    return results
```

  Su quel ramo `results` segue l'ordine di `candidate_ids`, cioè quello di SQL. Il
  commento sulla piscina (quello che nomina `created_at` e `Recipe.id.desc()`) se ne va
  con il codice che spiegava; resta quello del ramo con le parole.

- [ ] **Step 6: L'API.** In `search`: `offset: int = Query(default=0, ge=0)` e
  `offset=offset` nella chiamata.

- [ ] **Step 7:** tutti i test di ricerca e ricettario → verdi. I test sulla piscina
  (`test_solo_cucinabili_vede_oltre_la_piscina_dei_candidati` e vicini) devono restare
  verdi senza modifiche: dicevano esattamente questo.

- [ ] **Step 8: Commit** `R4: la soglia dei mancanti in SQL, il ricettario intero e l'offset`.

### Task 6: «Mostra altre»

**Files:**
- Modify: `frontend/src/features/recipes/api.ts`, `frontend/src/features/recipes/RecipeBookScreen.tsx`
- Test: `frontend/src/features/recipes/RecipeBookScreen.test.tsx`

**Interfaces:**
- Consumes: `GET /recipes/search?offset=N&limit=30` (Task 5).
- Produces: `RECIPE_PAGE_SIZE = 30`; `searchRecipes({..., offset})`.

- [ ] **Step 1: I test** (in coda al `describe`, con `stubRoutedFetch` del file):

```tsx
function ricette(quante: number, da = 0) {
  return Array.from({ length: quante }, (_, n) => ({
    ...RESULTS[0], id: `r${da + n}`, title: `Ricetta ${da + n}`,
  }));
}

function paginato(path: string): [unknown, number] {
  if (path.includes("/recipes/categories")) return [[], 200];
  if (path.includes("/recipes/search-mode")) return [{ semantic: true }, 200];
  const offset = Number(new URL(path, "http://x").searchParams.get("offset") ?? 0);
  // la seconda pagina ripete l'ultima della prima: un inserimento durante l'import
  return offset === 0 ? [ricette(30), 200] : [ricette(5, 29), 200];
}

it("«Mostra altre» porta la pagina dopo, senza doppioni", async () => {
  const fetchMock = stubRoutedFetch(paginato);
  renderScreen();
  await screen.findByText("Ricetta 29");

  await userEvent.click(screen.getByRole("button", { name: "Mostra altre" }));

  expect(await screen.findByText("Ricetta 33")).toBeDefined();
  expect(ultimaRicerca(fetchMock)).toContain("offset=30");
  expect(screen.getAllByText("Ricetta 29")).toHaveLength(1);
  // l'ultima pagina non era piena: non ce ne sono altre
  expect(screen.queryByRole("button", { name: "Mostra altre" })).toBeNull();
});

it("con meno di una pagina non offre «Mostra altre»", async () => {
  stubRoutedFetch(CODA_CON_CATEGORIE);
  renderScreen();
  await screen.findByText("Pasta all'aglio");
  expect(screen.queryByRole("button", { name: "Mostra altre" })).toBeNull();
});

it("se la pagina dopo fallisce, le ricette restano e si può riprovare", async () => {
  stubRoutedFetch((path) => {
    if (path.includes("offset=30")) return [{ detail: "giù" }, 500];
    return paginato(path);
  });
  renderScreen();
  await screen.findByText("Ricetta 29");

  await userEvent.click(screen.getByRole("button", { name: "Mostra altre" }));

  expect(await screen.findByText("Non sono riuscito a caricarne altre.")).toBeDefined();
  expect(screen.getByText("Ricetta 0")).toBeDefined();
  expect(screen.getByRole("button", { name: "Mostra altre" })).toBeDefined();
});
```

- [ ] **Step 2:** `npx vitest run src/features/recipes/RecipeBookScreen.test.tsx` →
  falliscono.

- [ ] **Step 3: `api.ts`.**

```ts
/** Quante ricette per pagina. Si manda sempre, così il numero sta in un posto solo e
 * «l'ultima pagina era piena» si confronta con quel che si è chiesto davvero. */
export const RECIPE_PAGE_SIZE = 30;
```

  `searchRecipes` guadagna `offset = 0` fra i parametri con nome, e prima del `return`:

```ts
  params.set("limit", String(RECIPE_PAGE_SIZE));
  if (offset > 0) params.set("offset", String(offset));
```

- [ ] **Step 4: `RecipeBookScreen.tsx`.** `useQuery` della ricerca diventa:

```tsx
  const {
    data,
    isLoading,
    isError,
    isFetchNextPageError,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ["recipes", debouncedQuery, maxMissing, category, ingredientIds],
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      searchRecipes({ query: debouncedQuery, maxMissing, category, ingredientIds, offset: pageParam }),
    // la pagina dopo parte da quante ne sono arrivate, doppioni compresi: è il conto
    // che il server usa per l'offset
    getNextPageParam: (lastPage, allPages) =>
      lastPage.length === RECIPE_PAGE_SIZE
        ? allPages.reduce((total, page) => total + page.length, 0)
        : undefined,
  });
  // Un inserimento sopra la pagina (l'import che gira) sposta tutto in giù di uno:
  // l'offset fa vedere un doppione, mai un buco, e il doppione si scarta qui.
  const recipes = uniqueById(data?.pages.flat() ?? []);
  // l'errore di una pagina successiva non cancella quel che è già a video
  const searchFailed = isError && !isFetchNextPageError;
```

  con, sopra il componente:

```tsx
function uniqueById<T extends { id: string }>(items: T[]): T[] {
  const seen = new Set<string>();
  return items.filter((item) => (seen.has(item.id) ? false : (seen.add(item.id), true)));
}
```

  Nel JSX, `isError` diventa `searchFailed` nelle tre condizioni, e dopo la `<ul>`:

```tsx
      {!isLoading && !searchFailed && hasNextPage && (
        <div className="flex flex-col items-center gap-2 pt-3">
          {isFetchNextPageError && (
            <Alert>Non sono riuscito a caricarne altre.</Alert>
          )}
          <button
            type="button"
            onClick={() => void fetchNextPage()}
            disabled={isFetchingNextPage}
            className={buttonClasses("secondary")}
          >
            {isFetchingNextPage ? "Carico…" : "Mostra altre"}
          </button>
        </div>
      )}
```

  Import: `useInfiniteQuery` al posto di `useQuery` solo se `useQuery` non serve più
  (serve: categorie, modo di ricerca, stato dell'import), `RECIPE_PAGE_SIZE` da `./api`,
  `buttonClasses` da `../../components/ui/buttonClasses`.

- [ ] **Step 5:** test verdi, poi `npx vitest run` intera e `npm run typecheck`.
- [ ] **Step 6: Commit** `R4: «Mostra altre» nel ricettario`.

### Task 7: Misura, runbook, documenti

**Files:**
- Create: `docs/import-gz-runbook.md`
- Modify: `docs/prossimi-passi.md` (R4, Parte X, Parte XI), `README.md` (i due comandi nuovi)

- [ ] **Step 1: Rimisurare** con lo script usa e getta del brainstorming (8.500
  ricette sintetiche nel database `spena_bench`): tutti i casi senza errori, e i tempi
  scritti nel runbook e in `prossimi-passi.md`. Se un caso supera 300 ms si guarda il
  piano di esecuzione (`EXPLAIN ANALYZE`) prima di andare avanti.
- [ ] **Step 2: Il runbook** (sezione per sezione): cosa c'è da sapere, prerequisiti,
  deploy e verifica del pacchetto, limite di credito su OpenRouter, cancellazione delle
  ricette di semina (prima senza `--conferma`), lancio in background con `nohup` e
  log, come si segue, cosa fare se si ferma, dopo (unità, coda, controlli, misura in
  produzione), cosa aggiornare in `prossimi-passi.md` a lavoro fatto.
- [ ] **Step 3:** `prossimi-passi.md`: R4 «[COSTRUITA 2026-09-24, da eseguire]» con il
  rimando al runbook; la voce di Parte X sul flag del seme che esce con 0 si chiude.
- [ ] **Step 4:** suite complete (backend, jsdom, typecheck) e commit
  `R4: il runbook dell'import completo`.
