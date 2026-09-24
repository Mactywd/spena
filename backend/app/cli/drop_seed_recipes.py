"""Toglie le ricette di semina, e prima dice cosa toglierebbe (R4).

Eseguire nel container del backend:

    python -m app.cli.drop_seed_recipes             # elenca e basta
    python -m app.cli.drop_seed_recipes --conferma  # cancella

Una ricetta di semina è `source = 'dataset'` con `source_ref = 'seme iniziale'`, il
valore che `data/recipes_seed.json` scrive su tutte e 26. Le ricette importate portano
un indirizzo, quelle scritte a mano o con l'AI non sono `dataset`: nessuna delle due
può essere presa per sbaglio.

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
    """Quante ricette di semina ha tolto: zero senza `confirm`, che elenca e basta."""
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
            select(func.count())
            .select_from(CookingEvent)
            .where(CookingEvent.recipe_id.in_(ids))
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
