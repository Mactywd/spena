"""Il motore dei sostituti non conta le ricette dei pasti (spec 2026-11-12 §4.2)."""

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import RecipeSource
from app.domain.substitutions import SubstitutionContext
from app.repositories import substitutions as repo
from app.repositories.recipes import create_recipe


async def _ingrediente(db_session, nome: str) -> Ingredient:
    voce = Ingredient(name=nome, display_name=nome.capitalize(), category=IngredientCategory.CARNE)
    db_session.add(voce)
    await db_session.flush()
    return voce


async def _ricetta(db_session, titolo, voce, *, fuori: bool):
    return await create_recipe(
        db_session, title=titolo, description=None, instructions="Cuoci.", servings=2,
        source=RecipeSource.MANUAL, source_ref=None,
        ingredients=[(voce.id, "primary", None, None)], embedding=None,
        category="Secondi piatti", in_book=not fuori,
    )


async def test_un_ingrediente_solo_in_una_ricetta_di_un_pasto_non_e_una_voce(db_session):
    pollo = await _ingrediente(db_session, "pollo")
    await _ricetta(db_session, "Pollo del pasto", pollo, fuori=True)
    await db_session.flush()

    voci = await repo.pending_voices(db_session)
    assert pollo.id not in {voce.ingredient_id for voce in voci}


async def test_la_scheda_dell_ingrediente_non_conta_le_ricette_dei_pasti(db_session):
    pollo = await _ingrediente(db_session, "pollo")
    await _ricetta(db_session, "Pollo arrosto", pollo, fuori=False)
    await _ricetta(db_session, "Pollo del pasto", pollo, fuori=True)
    await db_session.flush()

    vista = await repo.ingredient_view(db_session, pollo.id)
    salato = [c for c in vista.contexts if c.context == SubstitutionContext.SAVORY]
    assert [c.recipes for c in salato] == [1]
