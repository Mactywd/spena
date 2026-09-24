"""Rilegge il costo delle ricette già importate da GialloZafferano.

Eseguire con `python -m app.cli.reread_costs` dentro il container del backend, una
volta dopo la migrazione `0010`. Le pagine prese prima di R9 non avevano il costo
nel `payload`, e l'HTML non si conserva: l'unico modo di saperlo è richiederle.

Scrive **solo** il costo, e solo dove manca: un costo scelto a mano non si
sovrascrive, e rilanciare il comando dopo un'interruzione riprende da dove era.
Stessa cortesia di `app.cli.import_gz`: una pagina alla volta, con pausa, e ci si
ferma quando la fonte chiede di smettere.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.db.models.recipe import Recipe, RecipeSource
from app.db.models.recipe_import import RecipeImport
from app.services.recipe_import.giallozafferano import (
    DELAY_SECONDS,
    MAX_CONSECUTIVE_FAILURES,
    SourceUnavailable,
    UnparsablePage,
    build_client,
    cost_from_page,
    fetch_page,
)

# Nessun `.limit()`, come in `reparse_quantities`: la tabella è piccola per
# contratto finché i volumi non cambiano, e il comando si rilancia.


@dataclass(frozen=True)
class Reread:
    found: int  # costo trovato e scritto
    without: int  # pagina letta, ma senza un costo riconoscibile
    gone: int  # pagina che la fonte non ha più
    stopped_early: bool


async def reread_costs(
    session: AsyncSession,
    *,
    client: httpx.AsyncClient,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> Reread:
    recipes = (
        await session.execute(
            select(Recipe)
            .where(
                Recipe.source == RecipeSource.DATASET,
                Recipe.cost.is_(None),
                # le ricette del seme hanno una nota qui, non un indirizzo
                Recipe.source_ref.like("http%"),
            )
            .order_by(Recipe.source_ref)
        )
    ).scalars().all()

    found = without = gone = 0
    consecutive_failures = 0
    stopped_early = False
    for recipe in recipes:
        await sleep(DELAY_SECONDS)
        try:
            html = await fetch_page(client, recipe.source_ref)
        except SourceUnavailable as exc:
            consecutive_failures += 1
            print(f"la fonte ha rifiutato {recipe.source_ref}: {exc}")
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                stopped_early = True
                break
            continue
        except UnparsablePage:
            consecutive_failures = 0
            gone += 1
            continue
        consecutive_failures = 0

        # Il costo e basta, non `parse_recipe`: una pagina il cui JSON-LD nel frattempo
        # è cambiato non deve impedire di leggere una riga che sta altrove.
        cost = cost_from_page(BeautifulSoup(html, "html.parser"))
        if cost is None:
            without += 1
            continue

        recipe.cost = cost
        page = (
            await session.execute(select(RecipeImport).where(RecipeImport.recipe_id == recipe.id))
        ).scalars().first()
        if page is not None:
            # un dizionario nuovo e non una modifica sul posto: SQLAlchemy non vede
            # le mutazioni dentro un JSONB, e il payload resterebbe com'era
            page.payload = {**page.payload, "cost": cost}
        # a ogni pagina, come l'import: un'interruzione non butta via quel che la
        # fonte ha già servito
        await session.commit()
        found += 1

    return Reread(found=found, without=without, gone=gone, stopped_early=stopped_early)


async def main() -> None:
    async with SessionLocal() as session:
        async with build_client() as client:
            esito = await reread_costs(session, client=client)
        await session.commit()
    print(
        f"{esito.found} costi scritti, {esito.without} pagine senza costo, "
        f"{esito.gone} pagine sparite dalla fonte"
    )
    if esito.stopped_early:
        print(
            f"{MAX_CONSECUTIVE_FAILURES} rifiuti di fila: mi sono fermato. "
            "Rilancia più tardi, riprende da dove era."
        )


if __name__ == "__main__":
    asyncio.run(main())
