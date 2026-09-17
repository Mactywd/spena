"""Caricamento dei dati di semina. Idempotente: si può rieseguire senza danni.

Eseguire con `python -m app.cli.seed` dentro il container del backend.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.db.models.ingredient import Ingredient, IngredientAlias
from app.db.models.recipe import Recipe
from app.repositories.recipes import create_recipe
from app.services.embeddings import (
    EmbeddingUnavailable,
    get_embedding_provider,
    log_degradation_once,
    recipe_document,
)

# I file del seme stanno in data/ nella radice del repository (layout della spec),
# che è fuori dal contesto di build dell'immagine del backend: dentro il container
# arrivano come bind mount su /data (vedi docker-compose.yml). Fuori dal container,
# invece, si trovano risalendo da questo file. Vanno provati entrambi: misurato,
# senza questa ricerca `docker compose exec backend python -m app.cli.seed` — la
# semina documentata dal piano — moriva con FileNotFoundError, cioè la v1 non era
# seminabile dove gira.
# Il montaggio bersaglia /data e non /app/data perché in sviluppo /app è a sua volta
# un bind di ./backend, e un montaggio annidato fa creare a Docker il punto di
# innesto sull'host: un backend/data vuoto e di proprietà di root.
CANDIDATE_DATA_DIRS = (
    Path(__file__).resolve().parents[3] / "data",
    Path("/data"),
)

INGREDIENTS_FILE = "ingredients_seed.json"
RECIPES_FILE = "recipes_seed.json"

HOWTO_MISSING_DATA = (
    f"Non trovo i file del seme ({INGREDIENTS_FILE}, {RECIPES_FILE}). "
    "Dentro Docker la cartella data/ del repository va montata su /data "
    "(`./data:/data:ro`): controlla il volume del servizio backend in "
    "docker-compose.yml. "
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


class RecipesLoaded(NamedTuple):
    """Quante ricette sono entrate, e quante senza vettore.

    Il secondo numero esiste perché un ricettario seminato con zero vettori era
    indistinguibile da uno sano: il seme inghiotte EmbeddingUnavailable per ricetta
    (giustamente, la ricetta vale anche senza vettore) e stampava solo i conteggi.
    Vederlo al momento della semina è il momento in cui costa meno accorgersene.
    """

    created: int
    without_embedding: int


async def load_recipes(session: AsyncSession, path: Path) -> RecipesLoaded:
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
    without_embedding = 0
    for entry in entries:
        if entry["title"] in existing_titles:
            continue
        text = recipe_document(entry["title"], entry.get("description", ""))
        try:
            embedding = (await provider.embed_passages([text]))[0]
        except EmbeddingUnavailable as exc:
            embedding = None
            without_embedding += 1
            log_degradation_once(exc)

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
    return RecipesLoaded(created=created, without_embedding=without_embedding)


FLAG_SOLO_INGREDIENTI = "--solo-ingredienti"


async def main() -> None:
    # `--solo-ingredienti` per la messa in produzione di un'anagrafica allargata:
    # il seme è idempotente e salta per titolo anche le ricette, ma «salta quelle
    # che ci sono» non è «non ne rimette»: una ricetta del seme cancellata a mano
    # tornerebbe. R4 prevede proprio di cancellarle, quindi la trappola è vicina.
    #
    # Un argomento che comincia per `--` e non è questo flag viene rifiutato: un
    # refuso come `--solo-ingredient` altrimenti passerebbe inosservato come «nessun
    # flag», il seme farebbe la passata piena, e niente distinguerebbe «capito» da
    # «ignorato» — esattamente la trappola che il flag doveva evitare.
    sconosciuti = [
        arg for arg in sys.argv[1:] if arg.startswith("--") and arg != FLAG_SOLO_INGREDIENTI
    ]
    if sconosciuti:
        print(
            f"argomento sconosciuto: {sconosciuti[0]}. Valore valido: {FLAG_SOLO_INGREDIENTI}"
        )
        return
    solo_ingredienti = FLAG_SOLO_INGREDIENTI in sys.argv
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


if __name__ == "__main__":
    asyncio.run(main())
