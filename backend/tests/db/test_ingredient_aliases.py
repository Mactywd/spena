"""Le tre operazioni su cui poggiano il riconoscimento automatico e il suo annullamento.

`remember_alias` è ciò che fa valere una decisione per sempre, e anche fuori
dall'import: l'autocomplete della lista della spesa legge gli stessi alias.
`forget_alias` e `delete_ingredient_if_unused` sono la sua inversa, e la loro
prudenza è il motivo per cui annullare non può fare danni.
"""

import pytest
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.recipe import RecipeSource
from app.repositories.ingredients import (
    add_alias,
    create_ingredient,
    delete_ingredient_if_unused,
    forget_alias,
    remember_alias,
)
from app.repositories.products import create_product
from app.repositories.recipes import create_recipe


async def aliases(session, ingredient_id) -> list[str]:
    rows = await session.execute(
        select(IngredientAlias.alias).where(IngredientAlias.ingredient_id == ingredient_id)
    )
    return sorted(rows.scalars())


async def test_remember_alias_scrive_in_minuscolo_con_sorgente_import(db_session):
    pasta = await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    assert await remember_alias(db_session, pasta.id, "Rigatoni") is True
    assert await aliases(db_session, pasta.id) == ["rigatoni"]
    riga = (
        await db_session.execute(
            select(IngredientAlias).where(IngredientAlias.alias == "rigatoni")
        )
    ).scalar_one()
    assert riga.source == "import"


async def test_un_alias_gia_preso_da_un_altro_ingrediente_non_si_ruba(db_session):
    """Il vincolo del database è su `(ingredient_id, alias)`, non sull'alias.

    Lascerebbe passare lo stesso alias su due ingredienti diversi, cioè un
    autocomplete che dà due risposte a una domanda sola. Il legame fra termine e
    ingrediente vive su `import_terms`, quindi saltare la scrittura non perde niente.
    """
    pasta = await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    riso = await create_ingredient(
        db_session, name="riso", display_name="Riso", category=IngredientCategory.CEREALI
    )
    await add_alias(db_session, pasta.id, "rigatoni", source="import")

    assert await remember_alias(db_session, riso.id, "Rigatoni") is False
    assert await aliases(db_session, riso.id) == []


async def test_un_alias_piu_lungo_della_colonna_si_salta_invece_di_esplodere(db_session):
    """`import_terms.display_name` è `String(200)`, `alias` è `String(120)`.

    Un termine lunghissimo della fonte arriva qui legittimo, e senza il controllo
    l'insert è un errore del database in mezzo a una passata che ha già assegnato la
    decisione (e magari già creato l'ingrediente). Saltare l'alias non perde niente: il
    legame vive su `import_terms`, e si paga solo il fatto che quel termine non si
    riconoscerà da solo al prossimo giro.
    """
    pasta = await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    lunghissimo = "rigatoni " * 20
    assert len(lunghissimo.strip()) > 120

    assert await remember_alias(db_session, pasta.id, lunghissimo) is False
    assert await aliases(db_session, pasta.id) == []


async def test_forget_alias_cancella_solo_il_proprio_e_solo_quelli_dellimport(db_session):
    pasta = await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    await add_alias(db_session, pasta.id, "rigatoni", source="import")
    await add_alias(db_session, pasta.id, "maccheroni", source="seed")

    assert await forget_alias(db_session, pasta.id, "Rigatoni") is True
    # un alias del seme non è nostro: annullare una decisione dell'AI non deve poter
    # smontare l'anagrafica di partenza
    assert await forget_alias(db_session, pasta.id, "Maccheroni") is False
    assert await aliases(db_session, pasta.id) == ["maccheroni"]


async def test_un_ingrediente_senza_usi_si_cancella(db_session):
    speck = await create_ingredient(
        db_session, name="speck", display_name="Speck", category=IngredientCategory.CARNE
    )
    assert await delete_ingredient_if_unused(db_session, speck.id) is True
    assert await db_session.get(Ingredient, speck.id) is None


async def test_un_ingrediente_usato_da_una_ricetta_resta(db_session):
    speck = await create_ingredient(
        db_session, name="speck", display_name="Speck", category=IngredientCategory.CARNE
    )
    await create_recipe(
        db_session, title="Pasta allo speck", description=None, instructions="cuoci",
        servings=2, source=RecipeSource.DATASET, source_ref=None,
        ingredients=[(speck.id, "primary", None, None)], embedding=None,
    )
    assert await delete_ingredient_if_unused(db_session, speck.id) is False
    assert await db_session.get(Ingredient, speck.id) is not None


async def test_un_ingrediente_in_dispensa_resta(db_session):
    speck = await create_ingredient(
        db_session, name="speck", display_name="Speck", category=IngredientCategory.CARNE
    )
    db_session.add(PantryItem(ingredient_id=speck.id, status="available"))
    await db_session.flush()
    assert await delete_ingredient_if_unused(db_session, speck.id) is False


async def test_un_ingrediente_con_un_prodotto_resta(db_session):
    """Un prodotto senza articolo di dispensa trattiene comunque l'ingrediente.

    `pantry.py` non cancella mai un articolo, lo archivia (`archived_at`): un
    prodotto può quindi restare l'unico riferimento vivo molto dopo che l'ultimo
    articolo in dispensa è sparito. Costruito con `create_product`, il repository
    che l'app usa davvero, non con un `Product(...)` scritto a mano: altrimenti il
    test garantirebbe solo che il modello ha una colonna, non che il percorso reale
    viene controllato.
    """
    yogurt = await create_ingredient(
        db_session, name="yogurt greco", display_name="Yogurt greco",
        category=IngredientCategory.LATTICINI,
    )
    await create_product(
        db_session, ingredient_id=yogurt.id, name="Fage Total 0%", source="custom",
    )
    assert await delete_ingredient_if_unused(db_session, yogurt.id) is False
    assert await db_session.get(Ingredient, yogurt.id) is not None


async def test_i_suoi_alias_non_lo_trattengono(db_session):
    """Gli alias dell'import sono parte della decisione, non un uso indipendente.

    Se lo trattenessero, nessun ingrediente creato dall'AI sarebbe mai cancellabile:
    ogni decisione ne scrive uno.
    """
    speck = await create_ingredient(
        db_session, name="speck", display_name="Speck", category=IngredientCategory.CARNE
    )
    await add_alias(db_session, speck.id, "speck a cubetti", source="import")
    assert await delete_ingredient_if_unused(db_session, speck.id) is True
    assert await db_session.get(Ingredient, speck.id) is None
