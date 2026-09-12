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

# I file del seme stanno in data/ nella radice del repository (layout della spec),
# che è fuori dal contesto di build dell'immagine del backend: dentro il container
# arrivano come bind mount su /app/data (vedi docker-compose.yml). Fuori dal
# container, invece, si trovano risalendo da questo file. Vanno provati entrambi:
# misurato, senza questo `docker compose exec backend python -m app.cli.seed` —
# la semina documentata dal piano — moriva con FileNotFoundError su «/data», cioè
# la v1 non era seminabile dove gira.
CANDIDATE_DATA_DIRS = (
    Path(__file__).resolve().parents[3] / "data",
    Path("/app/data"),
)

INGREDIENTS_FILE = "ingredients_seed.json"
RECIPES_FILE = "recipes_seed.json"

HOWTO_MISSING_DATA = (
    f"Non trovo i file del seme ({INGREDIENTS_FILE}, {RECIPES_FILE}). "
    "Dentro Docker la cartella data/ del repository va montata su /app/data: "
    "controlla il volume del servizio backend in docker-compose.yml. "
    "Fuori da Docker, esegui dalla copia del repository che contiene data/."
)


def find_data_dir(candidates: tuple[Path, ...] = CANDIDATE_DATA_DIRS) -> Path:
    """La prima cartella candidata che contiene davvero il seme.

    Fallisce dicendo come rimediare: un seme assente non deve trasformarsi in un
    traceback da cui non si capisce che manca un volume.
    """
    for candidate in candidates:
        if (candidate / INGREDIENTS_FILE).is_file():
            return candidate
    raise FileNotFoundError(HOWTO_MISSING_DATA)


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
    data_dir = find_data_dir()
    async with SessionLocal() as session:
        ingredients = await load_ingredients(session, data_dir / INGREDIENTS_FILE)
        recipes = await load_recipes(session, data_dir / RECIPES_FILE)
        await session.commit()
    print(f"caricati {ingredients} ingredienti e {recipes} ricette")


if __name__ == "__main__":
    asyncio.run(main())
