import json

import pytest
import pytest_asyncio
from llm_fakes import FakeLlm, system_of, user_of

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import RecipeSource
from app.repositories.recipes import create_recipe, get_recipe
from app.repositories.utensils import create_utensil
from app.services.ai_recipes import (
    SYSTEM_PROMPT,
    VARIANT_SYSTEM_PROMPT,
    draft_recipe,
    draft_variant,
)
from app.services.utensils import (
    UTENSILS_PROMPT_RULE,
    render_utensils_block,
    utensils_prompt_block,
)


@pytest.fixture(autouse=True)
def chiave(monkeypatch):
    """Senza chiave `build_headers` fallisce prima di arrivare al finto."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


BOZZA = {
    "title": "Frittata", "description": None, "instructions": "1. Sbatti le uova.",
    "servings": 1, "cost": 1, "ingredients": [],
}

ATTESO = (
    "Gli strumenti che ci sono in cucina sono solo questi:\n"
    "- frusta elettrica\n"
    "- padella antiaderente (da 24 cm)\n"
    + UTENSILS_PROMPT_RULE
)


@pytest_asyncio.fixture
async def ricetta(db_session):
    uova = Ingredient(name="uova", display_name="Uova", category=IngredientCategory.ALTRO)
    db_session.add(uova)
    await db_session.flush()
    creata = await create_recipe(
        db_session, title="Frittata", description=None, instructions="1. Sbatti le uova.",
        servings=1, source=RecipeSource.MANUAL, source_ref=None,
        ingredients=[(uova.id, "primary", "2", None)], embedding=None,
    )
    return await get_recipe(db_session, creata.id)


async def _due_utensili(session):
    # aggiunti al contrario: l'ordine del blocco è quello dell'elenco, non dell'inserimento
    await create_utensil(session, name="padella antiaderente", note="da 24 cm")
    await create_utensil(session, name="frusta elettrica", note=None)


async def test_senza_utensili_nessun_blocco(db_session):
    assert render_utensils_block([]) is None
    assert await utensils_prompt_block(db_session) is None


def test_il_blocco_elenca_gli_utensili_con_la_nota():
    assert render_utensils_block(
        [("frusta elettrica", None), ("padella antiaderente", "da 24 cm")]
    ) == ATTESO


async def test_il_blocco_dal_database_segue_l_ordine_dell_elenco(db_session):
    await _due_utensili(db_session)
    assert await utensils_prompt_block(db_session) == ATTESO


async def test_la_bozza_dice_all_ai_gli_utensili(db_session):
    await _due_utensili(db_session)
    finto = FakeLlm(BOZZA)
    await draft_recipe(db_session, "una frittata", client=finto)
    sistema = system_of(finto.bodies[0])
    assert sistema == SYSTEM_PROMPT + "\n" + ATTESO + "\n"
    # la richiesta resta com'è: gli utensili non la cambiano
    assert user_of(finto.bodies[0]) == "una frittata"


async def test_la_bozza_senza_utensili_ha_il_prompt_di_sempre(db_session):
    finto = FakeLlm(BOZZA)
    await draft_recipe(db_session, "una frittata", client=finto)
    assert system_of(finto.bodies[0]) == SYSTEM_PROMPT


async def test_la_variante_dice_all_ai_gli_utensili(db_session, ricetta):
    await _due_utensili(db_session)
    finto = FakeLlm(BOZZA)
    await draft_variant(db_session, ricetta, "senza forno", client=finto)
    assert system_of(finto.bodies[0]) == VARIANT_SYSTEM_PROMPT + "\n" + ATTESO + "\n"
    assert json.loads(user_of(finto.bodies[0]))["richiesta"] == "senza forno"


async def test_la_variante_senza_utensili_ha_il_prompt_di_sempre(db_session, ricetta):
    finto = FakeLlm(BOZZA)
    await draft_variant(db_session, ricetta, "senza forno", client=finto)
    assert system_of(finto.bodies[0]) == VARIANT_SYSTEM_PROMPT
