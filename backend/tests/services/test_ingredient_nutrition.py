"""Quale alimento CIQUAL dà i nutrienti a un ingrediente (S4, fetta 1): i tre stati, la
scelta a mano che vince sempre su quella dell'AI, l'annullamento, e la fusione."""

import uuid

import pytest
from sqlalchemy import select

from app.db.models.ingredient import Ingredient
from app.db.models.nutrition import IngredientNutrition
from app.domain.ciqual import CiqualRow
from app.repositories.ciqual import upsert_foods
from app.services import registry
from app.services.ingredient_nutrition import (
    NutritionRefusal,
    NutritionState,
    apply_ai_choice,
    choose_food,
    forget_choice,
    nutrition_of,
)


async def _mondo(db_session) -> dict[str, Ingredient]:
    await upsert_foods(
        db_session,
        [
            CiqualRow("90001", "Tomate, crue", "légumes", {"kcal": 18.0, "iron": 0.3}),
            CiqualRow("90002", "Tomate, concentré", "légumes", {"kcal": 77.0}),
        ],
    )
    voci = {
        "pomodoro": Ingredient(name="pomodoro", display_name="Pomodoro", category="verdura"),
        "pomodori": Ingredient(name="pomodori", display_name="Pomodori", category="verdura"),
        "detersivo": Ingredient(name="detersivo", display_name="Detersivo", category="casa"),
    }
    db_session.add_all(voci.values())
    await db_session.flush()
    return voci


async def _riga(db_session, ingrediente: Ingredient):
    return (
        await db_session.execute(
            select(IngredientNutrition.ciqual_code, IngredientNutrition.decided_by).where(
                IngredientNutrition.ingredient_id == ingrediente.id
            )
        )
    ).first()


async def test_un_alimento_nasce_da_decidere_e_un_non_alimentare_non_ne_ha(db_session):
    voci = await _mondo(db_session)

    assert (await nutrition_of(db_session, voci["pomodoro"].id)).state == NutritionState.UNDECIDED
    assert (await nutrition_of(db_session, voci["detersivo"].id)).state == NutritionState.NON_FOOD


async def test_la_scelta_a_mano_scrive_l_alimento(db_session):
    voci = await _mondo(db_session)

    vista = await choose_food(db_session, voci["pomodoro"].id, "90001")

    assert (vista.state, vista.decided_by) == (NutritionState.FOOD, "human")
    assert (vista.food.code, vista.food.nutrients) == ("90001", {"kcal": 18.0, "iron": 0.3})
    assert tuple(await _riga(db_session, voci["pomodoro"])) == ("90001", "human")


async def test_nessun_alimento_adatto_si_scrive_vuoto(db_session):
    voci = await _mondo(db_session)

    vista = await choose_food(db_session, voci["pomodoro"].id, None)

    assert (vista.state, vista.decided_by, vista.food) == (NutritionState.NONE, "human", None)
    assert tuple(await _riga(db_session, voci["pomodoro"])) == (None, "human")


async def test_una_scelta_a_mano_sostituisce_quella_dell_ai(db_session):
    voci = await _mondo(db_session)
    await apply_ai_choice(db_session, voci["pomodoro"].id, "90002")

    await choose_food(db_session, voci["pomodoro"].id, "90001")

    assert tuple(await _riga(db_session, voci["pomodoro"])) == ("90001", "human")


async def test_i_rifiuti_dicono_perche(db_session):
    voci = await _mondo(db_session)

    with pytest.raises(NutritionRefusal) as non_cibo:
        await choose_food(db_session, voci["detersivo"].id, "90001")
    assert non_cibo.value.code == "non_food"
    assert non_cibo.value.message == "«Detersivo» non è un alimento: non ha valori nutrizionali."

    with pytest.raises(NutritionRefusal) as sconosciuto:
        await choose_food(db_session, voci["pomodoro"].id, "12345")
    assert sconosciuto.value.code == "unknown_food"
    assert await _riga(db_session, voci["pomodoro"]) is None

    with pytest.raises(LookupError):
        await choose_food(db_session, uuid.uuid4(), "90001")


async def test_annullare_riporta_a_da_decidere(db_session):
    voci = await _mondo(db_session)
    await choose_food(db_session, voci["pomodoro"].id, "90001")

    vista = await forget_choice(db_session, voci["pomodoro"].id)

    assert vista.state == NutritionState.UNDECIDED
    assert await _riga(db_session, voci["pomodoro"]) is None


async def test_l_ai_scrive_solo_dove_non_c_e_niente(db_session):
    voci = await _mondo(db_session)
    await choose_food(db_session, voci["pomodoro"].id, "90001")

    assert await apply_ai_choice(db_session, voci["pomodoro"].id, "90002") is False
    assert await apply_ai_choice(db_session, voci["pomodori"].id, None) is True

    assert tuple(await _riga(db_session, voci["pomodoro"])) == ("90001", "human")
    assert tuple(await _riga(db_session, voci["pomodori"])) == (None, "ai")


async def test_la_fusione_perde_la_scelta_del_perdente_e_tiene_quella_del_vincitore(db_session):
    """Deciso da Mattia il 2026-10-13 (spec §12): il perdente si cancella, e la sua scelta
    con lui; il vincitore tiene la sua. Il giro dopo dell'AI non ha niente da rifare qui."""
    voci = await _mondo(db_session)
    await apply_ai_choice(db_session, voci["pomodori"].id, "90002")
    await choose_food(db_session, voci["pomodoro"].id, "90001")

    await registry.merge_ingredients(db_session, voci["pomodori"].id, voci["pomodoro"].id)

    assert await _riga(db_session, voci["pomodori"]) is None
    assert tuple(await _riga(db_session, voci["pomodoro"])) == ("90001", "human")
