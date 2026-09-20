"""Il riporziona per porzioni, visto dalla rotta che lo serve."""

import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import IngredientCategory
from app.db.models.unit import Unit
from app.repositories.ingredients import create_ingredient
from app.repositories.recipes import create_recipe


@pytest_asyncio.fixture
async def cucina(db_session):
    return {
        "pasta": await create_ingredient(
            db_session, name="pasta", display_name="Pasta",
            category=IngredientCategory.CEREALI,
        ),
        "cipolla": await create_ingredient(
            db_session, name="cipolla", display_name="Cipolla",
            category=IngredientCategory.VERDURA,
        ),
        "sale": await create_ingredient(
            db_session, name="sale", display_name="Sale",
            category=IngredientCategory.SPEZIE,
        ),
    }


async def _ricetta(db_session, cucina, servings):
    """Una ricetta con tutti e tre gli stati di dose: piena, numero nudo, non parsata."""
    recipe = await create_recipe(
        db_session,
        title="Mista", description=None, instructions="i", servings=servings,
        source="dataset", source_ref=None,
        ingredients=[
            (cucina["pasta"].id, "primary", "300 g", None),
            (cucina["cipolla"].id, "primary", "1", None),
            (cucina["sale"].id, "secondary", "q.b.", None),
        ],
        embedding=None,
    )
    # «g» decisa a mano: qui non gira nessun AI. Senza le forme il ridisegno
    # mostrerebbe la chiave, che per «g» è identica — e allora il test non direbbe
    # se le forme arrivano davvero a video.
    unit = (
        await db_session.execute(select(Unit).where(Unit.key == "g"))
    ).scalars().one()
    unit.singular, unit.plural, unit.decided_by = "g", "g", "human"
    await db_session.flush()
    return recipe.id


@pytest_asyncio.fixture
async def ricetta_mista(db_session, cucina):
    return await _ricetta(db_session, cucina, servings=4)


@pytest_asyncio.fixture
async def ricetta_senza_porzioni(db_session, cucina):
    return await _ricetta(db_session, cucina, servings=None)


async def test_senza_parametro_il_corpo_e_quello_di_sempre(logged_client, ricetta_mista):
    corpo = (await logged_client.get(f"/api/v1/recipes/{ricetta_mista}")).json()
    assert corpo["scaled_to"] is None
    assert corpo["unscalable_lines"] == 0
    for line in corpo["ingredients"]:
        assert line["quantity_display"] == line["quantity_text"]
        assert line["quantity_scaled"] is False


async def test_con_servings_le_dosi_parsate_scalano(logged_client, ricetta_mista):
    # la ricetta è per 4: chiederla per 2 dimezza
    corpo = (await logged_client.get(f"/api/v1/recipes/{ricetta_mista}?servings=2")).json()
    per_testo = {line["quantity_text"]: line for line in corpo["ingredients"]}

    assert per_testo["300 g"]["quantity_display"] == "150 g"
    assert per_testo["300 g"]["quantity_scaled"] is True
    # numero nudo: scala e resta nudo
    assert per_testo["1"]["quantity_display"] == "0,5"
    # non parsata: resta identica, ed è la risposta giusta
    assert per_testo["q.b."]["quantity_display"] == "q.b."
    assert per_testo["q.b."]["quantity_scaled"] is False

    assert corpo["scaled_to"] == 2
    assert corpo["unscalable_lines"] == 1
    # tutte e tre le righe hanno una dose scritta: qui denominatore e numero di
    # ingredienti coincidono per caso, ed è proprio il caso che nascondeva il difetto
    assert corpo["dose_lines"] == 3


async def test_le_stesse_porzioni_sono_come_non_averle_chieste(logged_client, ricetta_mista):
    """A 1× il testo originale dice la verità meglio di quanto sappiamo riscriverla."""
    corpo = (await logged_client.get(f"/api/v1/recipes/{ricetta_mista}?servings=4")).json()
    assert corpo["scaled_to"] is None
    assert corpo["unscalable_lines"] == 0
    for line in corpo["ingredients"]:
        assert line["quantity_display"] == line["quantity_text"]


async def test_una_riga_senza_dose_non_e_una_dose_che_non_si_riscala(
    logged_client, db_session, cucina
):
    """Il denominatore sono le dosi, non gli ingredienti.

    `materialize.py`, la stesura AI e l'inserimento a mano producono tutti righe con
    `quantity_text` nullo. Contarle fra quelle «che non si riscalano» manderebbe
    l'utente a cercare dosi che nella ricetta non ci sono — e la spec §5.4 promette
    su questa riga la stessa onestà dei nutrienti mancanti: l'assenza si dichiara,
    non si gonfia.
    """
    recipe = await create_recipe(
        db_session,
        title="Con una riga muta", description=None, instructions="i", servings=4,
        source="dataset", source_ref=None,
        ingredients=[
            (cucina["pasta"].id, "primary", "300 g", None),
            (cucina["cipolla"].id, "primary", "q.b.", None),
            (cucina["sale"].id, "secondary", None, None),
        ],
        embedding=None,
    )
    await db_session.flush()

    corpo = (await logged_client.get(f"/api/v1/recipes/{recipe.id}?servings=2")).json()

    # tre ingredienti, due dosi: una scalata e una no
    assert len(corpo["ingredients"]) == 3
    assert corpo["dose_lines"] == 2
    assert corpo["unscalable_lines"] == 1


async def test_senza_porzioni_dichiarate_il_parametro_si_ignora(
    logged_client, ricetta_senza_porzioni
):
    corpo = (
        await logged_client.get(f"/api/v1/recipes/{ricetta_senza_porzioni}?servings=2")
    ).json()
    assert corpo["scaled_to"] is None
    for line in corpo["ingredients"]:
        assert line["quantity_display"] == line["quantity_text"]
