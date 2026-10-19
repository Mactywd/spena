"""Le dosi pulite viste dal dettaglio: «+ q.b.» resta accanto alla dose riscalata, le
frazioni si riscalano, la nota arriva com'è (spec 2026-10-13-pulizia-dosi-design.md)."""

import pytest_asyncio

from app.db.models.ingredient import IngredientCategory
from app.repositories.ingredients import create_ingredient
from app.repositories.recipes import create_recipe


@pytest_asyncio.fixture
async def ricetta(db_session):
    righe = []
    for nome, dose, nota in [
        ("parmigiano", "50 g + q.b.", "da grattugiare"),
        ("zucchero", "½ cucchiaino", None),
        ("limone", "1 + ½", None),
        ("sale", "q.b.", None),
    ]:
        ingrediente = await create_ingredient(
            db_session, name=nome, display_name=nome.capitalize(),
            category=IngredientCategory.CEREALI,
        )
        righe.append((ingrediente.id, "primary", dose, nota))
    recipe = await create_recipe(
        db_session,
        title="Prova", description=None, instructions="i", servings=2,
        source="manual", source_ref=None, ingredients=righe, embedding=None,
    )
    await db_session.flush()
    return recipe.id


def _per_nome(corpo: dict) -> dict:
    return {line["ingredient_name"]: line for line in corpo["ingredients"]}


async def test_a_1x_si_mostra_il_testo_e_la_nota(logged_client, ricetta):
    righe = _per_nome((await logged_client.get(f"/api/v1/recipes/{ricetta}")).json())
    assert righe["parmigiano"]["quantity_display"] == "50 g + q.b."
    assert righe["parmigiano"]["note"] == "da grattugiare"
    assert righe["zucchero"]["note"] is None


async def test_il_q_b_resta_accanto_alla_dose_riscalata(logged_client, ricetta):
    corpo = (await logged_client.get(f"/api/v1/recipes/{ricetta}?servings=4")).json()
    righe = _per_nome(corpo)
    assert righe["parmigiano"]["quantity_display"] == "100 g + q.b."
    assert righe["parmigiano"]["quantity_scaled"] is True
    # il solo «q.b.» resta com'è e si conta fra le dosi che non si riscalano
    assert righe["sale"]["quantity_display"] == "q.b."
    assert corpo["unscalable_lines"] == 1


async def test_le_frazioni_si_riscalano(logged_client, ricetta):
    righe = _per_nome((await logged_client.get(f"/api/v1/recipes/{ricetta}?servings=4")).json())
    # «cucchiaino» non è decisa (qui non gira nessun AI): si mostra la parola com'è
    assert righe["zucchero"]["quantity_display"] == "1 cucchiaino"
    assert righe["limone"]["quantity_display"] == "3"


async def test_il_q_b_resta_accanto_anche_alla_dose_fissata(logged_client, ricetta):
    # R2 con la pulizia delle dosi (rilascio 2026-10-19): la riga dell'ancora mostra la dose
    # scritta e non il suo ricalcolo, ma il «+ q.b.» le resta accanto come alle altre
    righe = _per_nome((await logged_client.get(f"/api/v1/recipes/{ricetta}")).json())
    parmigiano = righe["parmigiano"]
    assert parmigiano["anchorable"] is True
    corpo = (
        await logged_client.get(
            f"/api/v1/recipes/{ricetta}",
            params={"anchor": parmigiano["ingredient_id"], "amount": "100"},
        )
    ).json()
    righe = _per_nome(corpo)
    assert corpo["anchor"]["amount"] == "100"
    assert righe["parmigiano"]["quantity_display"] == "100 g + q.b."
    assert righe["limone"]["quantity_display"] == "3"
