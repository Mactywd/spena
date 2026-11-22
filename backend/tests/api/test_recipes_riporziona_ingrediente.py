"""Il riporziona da una dose (R2, secondo modo), visto dalla rotta che lo serve."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import IngredientCategory
from app.db.models.unit import Unit
from app.repositories.ingredients import create_ingredient
from app.repositories.recipes import create_recipe

FRASE_FUORI_SCALA = (
    "Così la ricetta cambierebbe più di 50 volte: scrivi un numero fra 6 g e 15000 g."
)


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
    """Tre righe, tre stati di dose: piena («300 g»), numero nudo («1»), non parsata."""
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
    # «g» decisa a mano, come in test_recipes_riporziona.py: qui non gira nessun AI
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


async def _dettaglio(client, recipe_id, **params):
    return await client.get(f"/api/v1/recipes/{recipe_id}", params=params)


def _per_nome(corpo):
    return {line["ingredient_name"]: line for line in corpo["ingredients"]}


async def test_ogni_riga_dice_se_ci_si_puo_ancorare(logged_client, ricetta_mista):
    corpo = (await _dettaglio(logged_client, ricetta_mista)).json()
    righe = _per_nome(corpo)
    assert (righe["pasta"]["anchorable"], righe["pasta"]["anchor_unit"]) == (True, "g")
    # un numero nudo si riscala, e non ha un'unità da scrivere accanto al campo
    assert (righe["cipolla"]["anchorable"], righe["cipolla"]["anchor_unit"]) == (True, None)
    # «q.b.» non è una dose da cui partire
    assert (righe["sale"]["anchorable"], righe["sale"]["anchor_unit"]) == (False, None)
    assert corpo["anchor"] is None


async def test_da_una_dose_le_altre_seguono(logged_client, cucina, ricetta_mista):
    # la ricetta è per 4 con 300 g di pasta: 112,5 g sono 0,375 della ricetta
    risposta = await _dettaglio(
        logged_client, ricetta_mista, anchor=str(cucina["pasta"].id), amount="112.5"
    )
    assert risposta.status_code == 200
    corpo = risposta.json()
    righe = _per_nome(corpo)

    # la riga dell'ancora dice la dose scritta, non il suo ricalcolo
    assert righe["pasta"]["quantity_display"] == "112,5 g"
    assert righe["pasta"]["quantity_scaled"] is True
    assert righe["cipolla"]["quantity_display"] == "0,375"
    assert righe["cipolla"]["quantity_scaled"] is True
    # quel che non si capisce resta com'è, e si conta
    assert righe["sale"]["quantity_display"] == "q.b."
    assert righe["sale"]["quantity_scaled"] is False
    assert corpo["unscalable_lines"] == 1
    assert corpo["dose_lines"] == 3
    # la verità a 1× non si riscrive
    assert righe["pasta"]["quantity_text"] == "300 g"
    # il modo per porzioni non c'entra
    assert corpo["scaled_to"] is None
    assert corpo["anchor"] == {
        "ingredient_id": str(cucina["pasta"].id),
        "amount": "112.5",
        "equivalent_servings": 1.5,
    }


async def test_da_un_numero_nudo_si_riscala_lo_stesso(logged_client, cucina, ricetta_mista):
    corpo = (
        await _dettaglio(logged_client, ricetta_mista, anchor=str(cucina["cipolla"].id), amount="2")
    ).json()
    righe = _per_nome(corpo)
    assert righe["cipolla"]["quantity_display"] == "2"
    assert righe["pasta"]["quantity_display"] == "600 g"
    assert corpo["anchor"]["equivalent_servings"] == 8


async def test_la_dose_della_ricetta_e_come_non_chiedere_niente(
    logged_client, cucina, ricetta_mista
):
    """A 1× il testo originale dice la verità meglio di quanto sappiamo riscriverla."""
    corpo = (
        await _dettaglio(logged_client, ricetta_mista, anchor=str(cucina["pasta"].id), amount="300")
    ).json()
    for line in corpo["ingredients"]:
        assert line["quantity_display"] == line["quantity_text"]
        assert line["quantity_scaled"] is False
    assert corpo["unscalable_lines"] == 0
    # l'ancora resta: lo stepper dice «≈ 4», e «Torna alle dosi della ricetta» ha senso
    assert corpo["anchor"]["equivalent_servings"] == 4


async def test_senza_porzioni_si_riscala_lo_stesso(logged_client, cucina, ricetta_senza_porzioni):
    corpo = (
        await _dettaglio(
            logged_client, ricetta_senza_porzioni, anchor=str(cucina["pasta"].id), amount="150"
        )
    ).json()
    righe = _per_nome(corpo)
    assert righe["pasta"]["quantity_display"] == "150 g"
    assert righe["cipolla"]["quantity_display"] == "0,5"
    # senza porzioni nella ricetta non ci sono porzioni equivalenti da dire
    assert corpo["anchor"] == {
        "ingredient_id": str(cucina["pasta"].id),
        "amount": "150",
        "equivalent_servings": None,
    }


@pytest.mark.parametrize("amount", ["5.999", "15000.001"])
async def test_oltre_50_volte_un_422_che_dice_dove_stare(
    logged_client, cucina, ricetta_mista, amount
):
    risposta = await _dettaglio(
        logged_client, ricetta_mista, anchor=str(cucina["pasta"].id), amount=amount
    )
    assert risposta.status_code == 422
    assert risposta.json()["detail"] == FRASE_FUORI_SCALA


@pytest.mark.parametrize("amount,attesa", [("6", "6 g"), ("15000", "15000 g")])
async def test_gli_estremi_della_frase_si_accettano(
    logged_client, cucina, ricetta_mista, amount, attesa
):
    risposta = await _dettaglio(
        logged_client, ricetta_mista, anchor=str(cucina["pasta"].id), amount=amount
    )
    assert risposta.status_code == 200
    assert _per_nome(risposta.json())["pasta"]["quantity_display"] == attesa


async def test_un_ancora_che_la_ricetta_non_ha_si_ignora(logged_client, cucina, ricetta_mista):
    """Una ricetta modificata in un'altra scheda: la vista torna quella di tutti i giorni,
    come `servings` su una ricetta senza porzioni, invece di un errore."""
    for anchor in (str(cucina["sale"].id), str(uuid.uuid4())):
        corpo = (await _dettaglio(logged_client, ricetta_mista, anchor=anchor, amount="5")).json()
        assert corpo["anchor"] is None
        for line in corpo["ingredients"]:
            assert line["quantity_display"] == line["quantity_text"]


@pytest.mark.parametrize(
    "params",
    [
        {"anchor": "PASTA"},
        {"amount": "150"},
        {"anchor": "PASTA", "amount": "150", "servings": "2"},
    ],
)
async def test_i_parametri_vanno_insieme_e_un_modo_alla_volta(
    logged_client, cucina, ricetta_mista, params
):
    params = {k: (str(cucina["pasta"].id) if v == "PASTA" else v) for k, v in params.items()}
    assert (await _dettaglio(logged_client, ricetta_mista, **params)).status_code == 422


@pytest.mark.parametrize("amount", ["0", "-1", "1.2345", "abc", "10000000", "NaN"])
async def test_una_dose_che_non_e_un_numero_buono(logged_client, cucina, ricetta_mista, amount):
    risposta = await _dettaglio(
        logged_client, ricetta_mista, anchor=str(cucina["pasta"].id), amount=amount
    )
    assert risposta.status_code == 422
