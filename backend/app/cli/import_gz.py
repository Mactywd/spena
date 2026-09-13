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
    taken = 0
    skipped = 0
    consecutive_failures = 0
    stopped_early = False

    try:
        urls = await fetch_sitemap(client)
    except SourceUnavailable as exc:
        print(f"fonte dice di fermarsi: {exc}")
        print("Nessuna pagina presa oggi. Rilancia più tardi: costa nulla e riprende da dove era.")
        todo = []
        stopped_early = True
    else:
        already = await known_urls(session, GIALLOZAFFERANO)
        # `dict.fromkeys` scarta i duplicati mantenendo l'ordine di arrivo: una
        # sitemap con lo stesso `<loc>` due volte non deve far fallire `store_page`
        # con un `IntegrityError` che abortirebbe tutto il giro per un solo
        # indirizzo ripetuto.
        todo = list(dict.fromkeys(url for url in urls if url not in already))[:limit]

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

    # i termini si allineano sempre, anche dopo un giro fermato a metà: le pagine
    # prese devono comparire in coda, altrimenti il lavoro fatto non si vede
    await sync_terms(session, GIALLOZAFFERANO)

    # Poi l'AI decide quel che sa decidere, e solo allora si materializza: in
    # quest'ordine un comando solo riempie il ricettario. Senza chiave configurata
    # `LlmUnavailable` arriva qui e non oltre — le pagine restano salvate, i termini in
    # coda, e il comando esce pulito. È la regola «mai un vicolo cieco».
    decided = 0
    still_pending = 0
    waiting = await pending_terms(session, GIALLOZAFFERANO, limit=MAX_TERMS_PER_RUN)
    if waiting:
        try:
            outcome = await decide_terms(session, waiting, client=llm_client)
            decided = outcome.applied
            still_pending = outcome.still_pending
        except LlmUnavailable as exc:
            still_pending = len(waiting)
            print(f"riconoscimento non disponibile ({exc}): i termini restano in coda.")

    await materialize_ready(session, GIALLOZAFFERANO)
    return ImportRun(
        taken=taken, skipped=skipped, stopped_early=stopped_early,
        decided=decided, still_pending=still_pending,
    )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Scarica un lotto di ricette.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    arguments = parser.parse_args()

    async with SessionLocal() as session:
        async with build_client() as client:
            result = await run_import(session, limit=arguments.limit, client=client)
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


if __name__ == "__main__":
    asyncio.run(main())
