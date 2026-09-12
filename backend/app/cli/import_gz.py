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
