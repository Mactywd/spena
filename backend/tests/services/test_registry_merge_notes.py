"""Unendo due ingredienti, le due righe della stessa ricetta diventano una: anche le note.

Prima della pulizia delle dosi la nota era vuota ovunque e perderla non costava niente;
adesso porta «da grattugiare», «36 mesi».
"""

from sqlalchemy import select

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe import RecipeIngredient
from app.repositories.ingredients import create_ingredient
from app.repositories.recipes import create_recipe
from app.services.registry import merge_ingredients


async def test_unendo_due_righe_le_note_si_uniscono(db_session):
    vincitore = await create_ingredient(
        db_session, name="farina", display_name="Farina", category=IngredientCategory.CEREALI
    )
    perdente = await create_ingredient(
        db_session, name="farina 00", display_name="Farina 00",
        category=IngredientCategory.CEREALI,
    )
    ricetta = await create_recipe(
        db_session,
        title="Torta", description=None, instructions="i", servings=4,
        source="manual", source_ref=None,
        ingredients=[
            (vincitore.id, "primary", "500 g", "setacciata"),
            (perdente.id, "secondary", "50 g", "per spolverare"),
        ],
        embedding=None,
    )
    await db_session.flush()

    await merge_ingredients(db_session, perdente.id, vincitore.id)

    righe = (
        await db_session.execute(
            select(RecipeIngredient.quantity_text, RecipeIngredient.note).where(
                RecipeIngredient.recipe_id == ricetta.id
            )
        )
    ).all()
    assert [tuple(riga) for riga in righe] == [("500 g + 50 g", "setacciata; per spolverare")]
