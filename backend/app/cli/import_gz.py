"""Scarico di ricette da GialloZafferano.

Eseguire dentro il container del backend, in uno dei due modi:

- `python -m app.cli.import_gz --limit 200`: un lotto, poi si ferma;
- `python -m app.cli.import_gz --tutto`: tutta la sitemap a lotti, poi i termini
  rimasti in coda (R4). Sono ore: si lancia in background, vedi
  `docs/import-gz-runbook.md`.

Rieseguibile: le pagine già presenti non si riscaricano, quindi rilanciarlo riprende
da dove era.

Sulla decisione di scaricare, e sul `robots.txt` della fonte che vieta
esplicitamente i crawler AI, vedi §3 dello spec. Questo comando non è quei crawler,
e si comporta di conseguenza: una pagina alla volta, con pausa, mai due volte la
stessa, e si ferma quando il sito chiede di smettere.
"""

import argparse
import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.db.models.recipe_import import GIALLOZAFFERANO
from app.db.models.unit import Unit
from app.repositories.imports import (
    counts,
    known_urls,
    pending_terms,
    store_page,
    store_unparsable,
)
from app.services.llm import LlmUnavailable
from app.services.recipe_import.decide import decide_terms
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

# Quanti giri di fila senza una sola decisione prima di smettere di chiedere all'AI:
# il credito finito (402), il modello giù e le risposte non verificabili si
# somigliano tutti, e distinguerli non serve — rilanciare più tardi riprende.
MAX_FRUITLESS_ROUNDS = 2

# Quanti termini l'AI giudica in un giro. Una chiamata a termine: il tetto è
# sull'attesa e sulla spesa di un singolo lancio, non sulla correttezza — i termini
# che restano fuori li prende il lancio successivo, o il bottone «Riprova con l'AI».
MAX_TERMS_PER_RUN = 60


@dataclass(frozen=True)
class ImportRun:
    taken: int
    skipped: int
    stopped_early: bool
    decided: int = 0
    still_pending: int = 0
    # le parole d'unità mai viste che la materializzazione ha depositato: nessuno le
    # decide da sé, e `main()` lo dice invece di lasciarle grezze per sempre
    new_units: int = 0


def _log(message: str) -> None:
    # `flush`: in background il log si legge mentre il comando gira, non alla fine
    print(message, flush=True)


@dataclass(frozen=True)
class _Taken:
    taken: int = 0
    skipped: int = 0
    stopped_early: bool = False
    # i rifiuti di fila con cui il lotto è finito: il lotto dopo parte da lì, perché
    # «due rifiuti di fila» non smette di valere al confine fra due lotti
    trailing_failures: int = 0


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
    # `dict.fromkeys` scarta i duplicati mantenendo l'ordine di arrivo: una
    # sitemap con lo stesso `<loc>` due volte non deve far fallire `store_page`
    # con un `IntegrityError` che abortirebbe tutto il giro per un solo
    # indirizzo ripetuto.
    return list(dict.fromkeys(url for url in urls if url not in already))


async def _take_pages(
    session: AsyncSession,
    client: httpx.AsyncClient,
    urls: list[str],
    sleep: Callable[[float], Awaitable[None]],
    consecutive_failures: int = 0,
) -> _Taken:
    """Scarica, analizza e salva queste pagine, una alla volta e con la pausa."""
    taken = 0
    skipped = 0
    stopped_early = False

    for url in urls:
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
            # committiamo a ogni pagina, non solo alla fine del lotto: un Ctrl-C, un
            # intoppo del database o qualunque eccezione imprevista a metà giro non
            # deve buttare via le pagine già scaricate con pazienza — sarebbero
            # ririchieste alla fonte al prossimo lancio, la cosa che la cortesia di
            # questo comando esiste per evitare.
            await session.commit()
            skipped += 1
            continue

        consecutive_failures = 0
        try:
            recipe = parse_recipe(html)
        except UnparsablePage as exc:
            await store_unparsable(
                session, source=GIALLOZAFFERANO, url=url, reason=exc.reason
            )
            await session.commit()
            skipped += 1
            continue

        await store_page(
            session, source=GIALLOZAFFERANO, url=url, payload=recipe.as_payload()
        )
        await session.commit()
        taken += 1

    return _Taken(
        taken=taken, skipped=skipped, stopped_early=stopped_early,
        trailing_failures=consecutive_failures,
    )


async def _settle(
    session: AsyncSession,
    llm_client: object | None,
    *,
    exclude: frozenset[uuid.UUID] = frozenset(),
    ask_ai: bool = True,
) -> _Settled:
    """Il lavoro dopo le pagine: allinea i termini, fa decidere l'AI, materializza."""
    # i termini si allineano sempre, anche dopo un giro fermato a metà: le pagine
    # prese devono comparire in coda, altrimenti il lavoro fatto non si vede
    await sync_terms(session, GIALLOZAFFERANO)

    # Poi l'AI decide quel che sa decidere, e solo allora si materializza: in
    # quest'ordine un comando solo riempie il ricettario. Senza chiave configurata
    # `LlmUnavailable` arriva qui e non oltre — le pagine restano salvate, i termini in
    # coda, e il comando esce pulito. È la regola «mai un vicolo cieco».
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

    # Contate attorno alla materializzazione, che è dove `create_recipe` deposita le
    # unità nuove. Non si decidono qui: quella è una chiamata AI in più dentro un
    # comando che ne fa già una sua, e il tetto di 1$/giorno non è nostro da spendere.
    # Si dice, come fa `reparse_quantities`, e chi lancia decide.
    before = await _count_units(session)
    await materialize_ready(session, GIALLOZAFFERANO)
    return _Settled(
        decided=decided,
        still_pending=still_pending,
        new_units=await _count_units(session) - before,
        asked=frozenset(term.id for term in waiting),
    )


async def run_import(
    session: AsyncSession,
    *,
    limit: int,
    client: httpx.AsyncClient,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    llm_client: object | None = None,
) -> ImportRun:
    """Prende fino a `limit` pagine nuove, le analizza e le salva.

    `sleep` è un parametro perché la suite non dorme e non tocca la rete: il test
    conta le pause invece di aspettarle.
    """
    urls = await _new_urls(session, client)
    pages = (
        _Taken(stopped_early=True)
        if urls is None
        else await _take_pages(session, client, urls[:limit], sleep)
    )
    settled = await _settle(session, llm_client)
    return ImportRun(
        taken=pages.taken, skipped=pages.skipped, stopped_early=pages.stopped_early,
        decided=settled.decided, still_pending=settled.still_pending,
        new_units=settled.new_units,
    )


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
    `MAX_FRUITLESS_ROUNDS` giri di fila smette di chiederle e il resto va avanti:
    rilanciare più tardi riprende dai termini in coda.
    """
    urls = await _new_urls(session, client)
    todo = urls or []
    taken = skipped = decided = new_units = still_pending = failures = fruitless = 0
    stopped_early = urls is None
    asked: set[uuid.UUID] = set()

    async def settle_and_report(label: str) -> _Settled:
        nonlocal decided, new_units, still_pending, fruitless
        settled = await _settle(
            session, llm_client, exclude=frozenset(asked),
            ask_ai=fruitless < MAX_FRUITLESS_ROUNDS,
        )
        await session.commit()
        asked.update(settled.asked)
        decided += settled.decided
        new_units += settled.new_units
        still_pending = settled.still_pending
        if settled.asked:
            fruitless = 0 if settled.decided else fruitless + 1
            if fruitless == MAX_FRUITLESS_ROUNDS:
                log(
                    f"l'AI non ha deciso niente per {MAX_FRUITLESS_ROUNDS} giri di fila "
                    "(credito finito, modello giù o risposte non verificabili): smetto di "
                    "chiederle. Le pagine vanno avanti; rilancia --tutto più tardi."
                )
        totals = await counts(session, GIALLOZAFFERANO)
        log(
            f"{datetime.now():%H:%M} {label} · termini decisi {decided}, "
            f"in coda {totals.pending_terms} · ricette {totals.imported}"
        )
        return settled

    for start in range(0, len(todo), chunk):
        pages = await _take_pages(
            session, client, todo[start : start + chunk], sleep, failures
        )
        taken += pages.taken
        skipped += pages.skipped
        failures = pages.trailing_failures
        await settle_and_report(
            f"pagine {min(start + chunk, len(todo))}/{len(todo)} "
            f"(prese {taken}, scartate {skipped})"
        )
        if pages.stopped_early:
            stopped_early = True
            break

    # finite le pagine, i termini rimasti: a giri, finché ce n'è di mai chiesti
    while not stopped_early and fruitless < MAX_FRUITLESS_ROUNDS:
        settled = await settle_and_report("solo termini")
        if not settled.asked:
            break

    return ImportRun(
        taken=taken, skipped=skipped, stopped_early=stopped_early,
        decided=decided, still_pending=still_pending, new_units=new_units,
    )


async def _count_units(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(Unit))).scalar_one()


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

    print(f"prese {result.taken} pagine, scartate {result.skipped}")
    print(
        f"ricettario: {totals.imported} importate, {totals.pending_recipes} in attesa, "
        f"{totals.skipped} scartate in tutto"
    )
    if result.decided:
        print(f"{result.decided} ingredienti riconosciuti da sé")
    if totals.pending_terms:
        print(
            f"{totals.pending_terms} ingredienti da abbinare a mano: aprili dal "
            "ricettario, alla riga in cima. Le ricette entrano da sé mentre decidi."
        )
    # La stessa riga di `reparse_quantities`: senza, le dosi delle ricette appena
    # importate mostrano la parola grezza per sempre, perché niente in questo comando
    # decide le unità e niente altro le guarda.
    if result.new_units:
        print(
            f"{result.new_units} unità di misura nuove: decidile con "
            "python -m app.cli.decide_units"
        )


if __name__ == "__main__":
    asyncio.run(main())
