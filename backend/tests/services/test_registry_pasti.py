"""L'Anagrafica conta e segna le ricette dei pasti (spec 2026-11-12 §4.2)."""

import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import RecipeIngredient, RecipeSource
from app.repositories.ingredients import ingredient_usage
from app.repositories.recipes import create_recipe
from app.services.registry import merge_ingredients, recipes_using


async def _voce(db_session, nome: str, reparto=IngredientCategory.VERDURA) -> Ingredient:
    voce = Ingredient(name=nome, display_name=nome.capitalize(), category=reparto)
    db_session.add(voce)
    await db_session.flush()
    return voce


async def _ricetta(db_session, titolo, voce, *, fuori: bool):
    return await create_recipe(
        db_session, title=titolo, description=None, instructions="Cuoci.", servings=2,
        source=RecipeSource.MANUAL, source_ref=None,
        ingredients=[(voce.id, "primary", "2", None)], embedding=None, in_book=not fuori,
    )


@pytest_asyncio.fixture
async def zucchine(db_session):
    voce = await _voce(db_session, "zucchine")
    dentro = await _ricetta(db_session, "Zucchine in padella", voce, fuori=False)
    fuori = await _ricetta(db_session, "Zucchine del pasto", voce, fuori=True)
    await db_session.flush()
    return voce, dentro, fuori


async def test_recipes_using_conta_e_segna_le_ricette_dei_pasti(db_session, zucchine):
    voce, dentro, fuori = zucchine

    uso = await recipes_using(db_session, voce.id)

    assert uso.count == 2
    segni = {ricetta.id: ricetta.from_meal for ricetta in uso.recipes}
    assert segni == {dentro.id: False, fuori.id: True}


async def test_ingredient_usage_conta_le_righe_delle_ricette_dei_pasti(db_session, zucchine):
    voce, _, _ = zucchine

    assert (await ingredient_usage(db_session, voce.id)).recipes == 2


async def test_la_fusione_sposta_anche_le_righe_delle_ricette_dei_pasti(db_session):
    perdente = await _voce(db_session, "zucchina")
    vincitore = await _voce(db_session, "zucchine")
    fuori = await _ricetta(db_session, "Zucchina del pasto", perdente, fuori=True)
    await db_session.flush()

    await merge_ingredients(db_session, perdente.id, vincitore.id)

    ingredienti = (
        await db_session.execute(
            select(RecipeIngredient.ingredient_id).where(RecipeIngredient.recipe_id == fuori.id)
        )
    ).scalars().all()
    assert ingredienti == [vincitore.id]


async def test_il_rifiuto_del_non_alimentare_nomina_la_ricetta_del_pasto(
    logged_client, db_session
):
    """Una ricetta di un pasto usa ancora l'ingrediente: il rifiuto la nomina e la segna
    (`from_meal`), perché chi non la vede nel ricettario capisca da dove viene il blocco."""
    voce = await _voce(db_session, "burro", IngredientCategory.LATTICINI)
    fuori = await _ricetta(db_session, "Burro del pasto", voce, fuori=True)
    await db_session.flush()

    risposta = await logged_client.patch(
        f"/api/v1/ingredients/{voce.id}", json={"category": "casa"}
    )

    assert risposta.status_code == 409
    corpo = risposta.json()
    assert corpo["code"] == "non_food_in_recipes"
    assert corpo["recipes"] == [
        {"id": str(fuori.id), "title": "Burro del pasto", "archived": False, "from_meal": True}
    ]
