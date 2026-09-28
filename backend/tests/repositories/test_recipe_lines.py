"""L'unico punto che scrive `recipe_ingredients` (R10 §5).

La creazione e la modifica passano entrambe di qui: l'imbuto sul non alimentare e la
lettura delle quantità non hanno una seconda copia che una delle due strade potrebbe
dimenticare.
"""

from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import RecipeIngredient, RecipeSource
from app.repositories.recipes import (
    NonFoodInRecipe,
    create_recipe,
    get_recipe,
    recipe_categories,
    write_recipe_ingredients,
)


@pytest_asyncio.fixture
async def voci(db_session):
    voci = {
        "pasta": Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI),
        "aglio": Ingredient(name="aglio", display_name="Aglio", category=IngredientCategory.VERDURA),
        "sapone": Ingredient(name="sapone", display_name="Sapone", category=IngredientCategory.IGIENE),
    }
    db_session.add_all(voci.values())
    await db_session.flush()
    return voci


async def _aglio_e_olio(db_session, voci):
    return await create_recipe(
        db_session, title="Aglio e olio", description=None, instructions="Cuoci.",
        servings=2, source=RecipeSource.MANUAL, source_ref=None,
        ingredients=[
            (voci["pasta"].id, "primary", "320 g", None),
            (voci["aglio"].id, "secondary", "1 spicchio", None),
        ],
        embedding=None,
    )


async def _righe(db_session, recipe_id):
    rows = await db_session.execute(
        select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe_id)
    )
    return {row.ingredient_id: row for row in rows.scalars()}


async def test_riscrivere_toglie_le_righe_sparite_e_riscrive_le_altre(db_session, voci):
    ricetta = await _aglio_e_olio(db_session, voci)
    caricata = await get_recipe(db_session, ricetta.id)

    # la pasta resta ma cambia tutto, l'aglio se ne va: lo stesso ingrediente riscritto
    # è il caso che un flush unico romperebbe, inserendo prima di cancellare
    await write_recipe_ingredients(
        db_session, caricata, [(voci["pasta"].id, "secondary", "200 g", "al dente")]
    )
    await db_session.flush()

    righe = await _righe(db_session, ricetta.id)
    assert set(righe) == {voci["pasta"].id}
    pasta = righe[voci["pasta"].id]
    assert (pasta.role, pasta.quantity_text, pasta.note) == ("secondary", "200 g", "al dente")
    # la dose è passata dal parser, come alla creazione
    assert pasta.quantity_value == Decimal("200")


async def test_il_non_alimentare_e_rifiutato_prima_di_toccare_qualcosa(db_session, voci):
    ricetta = await _aglio_e_olio(db_session, voci)
    caricata = await get_recipe(db_session, ricetta.id)

    with pytest.raises(NonFoodInRecipe) as rifiuto:
        await write_recipe_ingredients(
            db_session, caricata,
            [(voci["pasta"].id, "primary", None, None), (voci["sapone"].id, "primary", None, None)],
        )

    assert rifiuto.value.display_name == "Sapone"
    assert set(await _righe(db_session, ricetta.id)) == {voci["pasta"].id, voci["aglio"].id}


async def test_la_categoria_si_scrive_creando(db_session, voci):
    ricetta = await create_recipe(
        db_session, title="Pasta in bianco", description=None, instructions="Cuoci.",
        servings=None, source=RecipeSource.MANUAL, source_ref=None,
        ingredients=[(voci["pasta"].id, "primary", None, None)], embedding=None,
        category="Primi piatti",
    )
    assert ricetta.category == "Primi piatti"


async def test_le_categorie_sono_quelle_presenti_una_volta_e_in_ordine(db_session, voci):
    for titolo, categoria in (("A", "Primi piatti"), ("B", "Dolci"), ("C", "Primi piatti"), ("D", None)):
        await create_recipe(
            db_session, title=titolo, description=None, instructions="x", servings=None,
            source=RecipeSource.MANUAL, source_ref=None, ingredients=[], embedding=None,
            category=categoria,
        )
    assert await recipe_categories(db_session) == ["Dolci", "Primi piatti"]
