"""`ingredient_for_new_name`: dove finisce, salvando, un nome nuovo scritto nel modulo.

È la regola che `_resolve_lines` applica salvando e che `GET /ingredients/match` dice in
anticipo al passo del nome (piano 20): una funzione sola, perché l'avviso non dica una cosa
e il salvataggio ne faccia un'altra.
"""

from app.db.models.ingredient import IngredientCategory
from app.repositories.ingredients import add_alias, create_ingredient
from app.services.ingredient_match import ingredient_for_new_name


async def test_il_nome_canonico_si_collega_anche_scritto_diverso(db_session):
    pasta = await create_ingredient(db_session, "pasta", "Pasta", IngredientCategory.CEREALI)

    trovato = await ingredient_for_new_name(db_session, "  Pasta ")

    assert trovato is not None
    assert trovato.id == pasta.id


async def test_un_alias_porta_al_suo_ingrediente_anche_se_non_alimentare(db_session):
    detersivo = await create_ingredient(
        db_session, "detersivo per i piatti", "Detersivo per i piatti", IngredientCategory.CASA
    )
    await add_alias(db_session, detersivo.id, "sapone piatti", "manual")

    trovato = await ingredient_for_new_name(db_session, "Sapone piatti")

    assert trovato is not None
    assert trovato.id == detersivo.id
    assert trovato.kind == "non_food"


async def test_una_somiglianza_non_collega_salvando_nasce_un_ingrediente(db_session):
    await create_ingredient(
        db_session, "detersivo per i piatti", "Detersivo per i piatti", IngredientCategory.CASA
    )

    assert await ingredient_for_new_name(db_session, "detersivo") is None


async def test_un_nome_vuoto_non_collega_niente(db_session):
    assert await ingredient_for_new_name(db_session, "   ") is None
