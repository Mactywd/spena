"""Caricamento dei dati di semina. Idempotente: si può rieseguire senza danni.

Eseguire con `python -m app.cli.seed` dentro il container del backend.
"""

import asyncio
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.db.models.ingredient import Ingredient, IngredientAlias
from app.db.models.recipe import Recipe
from app.repositories.recipes import create_recipe
from app.services.embeddings import EmbeddingUnavailable, get_embedding_provider

DATA_DIR = Path(__file__).resolve().parents[3] / "data"


async def load_ingredients(session: AsyncSession, path: Path) -> int:
    entries = json.loads(path.read_text())
    existing = {
        name for name in (await session.execute(select(Ingredient.name))).scalars()
    }

    created = 0
    for entry in entries:
        if entry["name"] in existing:
            continue
        ingredient = Ingredient(
            name=entry["name"], display_name=entry["display_name"], category=entry["category"]
        )
        for alias in entry.get("aliases", []):
            ingredient.aliases.append(IngredientAlias(alias=alias.lower(), source="import"))
        session.add(ingredient)
        created += 1

    await session.flush()
    return created


async def load_recipes(session: AsyncSession, path: Path) -> int:
    entries = json.loads(path.read_text())
    by_name = {
        name: ingredient_id
        for ingredient_id, name in (
            await session.execute(select(Ingredient.id, Ingredient.name))
        ).all()
    }
    existing_titles = {
        title for title in (await session.execute(select(Recipe.title))).scalars()
    }

    provider = get_embedding_provider()
    created = 0
    for entry in entries:
        if entry["title"] in existing_titles:
            continue
        text = f"{entry['title']}. {entry.get('description', '')}"
        try:
            embedding = (await provider.embed_passages([text]))[0]
        except EmbeddingUnavailable:
            embedding = None

        await create_recipe(
            session,
            title=entry["title"], description=entry.get("description"),
            instructions=entry["instructions"], servings=entry.get("servings"),
            source=entry.get("source", "dataset"), source_ref=entry.get("source_ref"),
            ingredients=[
                (by_name[line["name"]], line["role"], line.get("quantity_text"), None)
                for line in entry["ingredients"]
            ],
            embedding=embedding,
        )
        created += 1

    await session.flush()
    return created


async def main() -> None:
    async with SessionLocal() as session:
        ingredients = await load_ingredients(session, DATA_DIR / "ingredients_seed.json")
        recipes = await load_recipes(session, DATA_DIR / "recipes_seed.json")
        await session.commit()
    print(f"caricati {ingredients} ingredienti e {recipes} ricette")


if __name__ == "__main__":
    asyncio.run(main())
