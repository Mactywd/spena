"""La fusione di due ingredienti e i sostituti (R5): tutto passa al vincitore.

Dove il perdente è un sostituto va il vincitore, mai due volte nella stessa risposta e
mai come sostituto di sé stesso. Fra due voci generali dello stesso contesto vince quella
che risponde, poi quella scritta a mano, poi quella del vincitore. Le correzioni di
ricetta seguono la riga della ricetta. Una risposta «sostituti» rimasta vuota si toglie.
Sempre attraverso `merge_ingredients`, la funzione che le rotte e il comando chiamano.
"""

import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import RecipeSource
from app.db.models.substitution import IngredientSubstitution, SubstitutionOption
from app.repositories.recipes import create_recipe
from app.services.registry import merge_ingredients, preview_merge


@pytest_asyncio.fixture
async def voci(db_session):
    tutte = {
        nome: Ingredient(name=nome, display_name=nome.capitalize(), category=IngredientCategory.CARNE)
        for nome in ("pollo", "tacchino", "coniglio", "manzo", "agnello")
    }
    db_session.add_all(tutte.values())
    await db_session.flush()
    return {nome: voce.id for nome, voce in tutte.items()}


async def _risposta(db_session, voce, contesto=None, ricetta=None, verdetto="substitutes",
                    sostituti=(), decided_by="ai"):
    riga = IngredientSubstitution(
        ingredient_id=voce, context=contesto, recipe_id=ricetta, verdict=verdetto,
        decided_by=decided_by,
        options=[
            SubstitutionOption(substitute_id=sostituto, position=posto)
            for posto, sostituto in enumerate(sostituti)
        ],
    )
    db_session.add(riga)
    await db_session.flush()
    return riga


async def _risposte(db_session, voce) -> set[tuple]:
    righe = (
        await db_session.execute(
            select(IngredientSubstitution)
            .where(IngredientSubstitution.ingredient_id == voce)
            .options(
                selectinload(IngredientSubstitution.options).joinedload(SubstitutionOption.substitute)
            )
            .execution_options(populate_existing=True)
        )
    ).scalars().all()
    return {
        (
            riga.context, riga.recipe_id, riga.verdict, riga.decided_by,
            tuple(opzione.substitute.name for opzione in riga.options),
        )
        for riga in righe
    }


async def _ricetta(db_session, titolo: str, *voci_):
    return (
        await create_recipe(
            db_session, title=titolo, description=None, instructions="Cuoci.", servings=2,
            source=RecipeSource.MANUAL, source_ref=None,
            ingredients=[(voce, "primary", None, None) for voce in voci_], embedding=None,
        )
    ).id


async def test_la_voce_del_perdente_passa_al_vincitore_che_non_ne_ha(db_session, voci):
    await _risposta(db_session, voci["tacchino"], "salato", sostituti=[voci["coniglio"]])

    await merge_ingredients(db_session, voci["tacchino"], voci["pollo"])

    assert await _risposte(db_session, voci["pollo"]) == {
        ("salato", None, "substitutes", "ai", ("coniglio",)),
    }
    assert await _risposte(db_session, voci["tacchino"]) == set()


async def test_fra_due_voci_vince_la_mano(db_session, voci):
    await _risposta(db_session, voci["pollo"], "salato", sostituti=[voci["coniglio"]])
    await _risposta(db_session, voci["tacchino"], "salato", verdetto="omit", decided_by="human")
    await _risposta(db_session, voci["pollo"], "dolce", verdetto="irreplaceable", decided_by="human")
    await _risposta(db_session, voci["tacchino"], "dolce", verdetto="omit")

    await merge_ingredients(db_session, voci["tacchino"], voci["pollo"])

    assert await _risposte(db_session, voci["pollo"]) == {
        ("salato", None, "omit", "human", ()),
        ("dolce", None, "irreplaceable", "human", ()),
    }


async def test_a_parita_resta_la_voce_del_vincitore(db_session, voci):
    await _risposta(db_session, voci["pollo"], "salato", verdetto="omit")
    await _risposta(db_session, voci["tacchino"], "salato", verdetto="irreplaceable")

    await merge_ingredients(db_session, voci["tacchino"], voci["pollo"])

    assert await _risposte(db_session, voci["pollo"]) == {("salato", None, "omit", "ai", ())}


async def test_una_voce_che_risponde_batte_una_rimasta_vuota(db_session, voci):
    """La voce del vincitore, scritta a mano, ha perso il suo unico sostituto: non dice più
    niente, e quella dell'AI del perdente prende il suo posto."""
    await _risposta(db_session, voci["pollo"], "salato", sostituti=[voci["agnello"]], decided_by="human")
    await db_session.execute(delete(Ingredient).where(Ingredient.id == voci["agnello"]))
    await _risposta(db_session, voci["tacchino"], "salato", verdetto="omit")

    await merge_ingredients(db_session, voci["tacchino"], voci["pollo"])

    assert await _risposte(db_session, voci["pollo"]) == {("salato", None, "omit", "ai", ())}


async def test_dove_il_perdente_era_un_sostituto_c_e_il_vincitore(db_session, voci):
    await _risposta(db_session, voci["coniglio"], "salato", sostituti=[voci["tacchino"], voci["manzo"]])
    # il vincitore c'è già: il perdente non diventa un doppione
    await _risposta(db_session, voci["manzo"], "salato", sostituti=[voci["pollo"], voci["tacchino"]])
    # il vincitore non diventa sostituto di sé stesso, e la risposta rimasta vuota se ne va
    await _risposta(db_session, voci["pollo"], "salato", sostituti=[voci["tacchino"]])

    await merge_ingredients(db_session, voci["tacchino"], voci["pollo"])

    assert await _risposte(db_session, voci["coniglio"]) == {
        ("salato", None, "substitutes", "ai", ("pollo", "manzo")),
    }
    assert await _risposte(db_session, voci["manzo"]) == {
        ("salato", None, "substitutes", "ai", ("pollo",)),
    }
    assert await _risposte(db_session, voci["pollo"]) == set()


async def test_le_risposte_del_perdente_non_propongono_il_vincitore(db_session, voci):
    await _risposta(db_session, voci["tacchino"], "salato", sostituti=[voci["pollo"], voci["coniglio"]])
    await _risposta(db_session, voci["tacchino"], "dolce", sostituti=[voci["pollo"]])

    await merge_ingredients(db_session, voci["tacchino"], voci["pollo"])

    assert await _risposte(db_session, voci["pollo"]) == {
        ("salato", None, "substitutes", "ai", ("coniglio",)),
    }


async def test_una_correzione_di_ricetta_segue_la_riga(db_session, voci):
    spezzatino = await _ricetta(db_session, "Spezzatino", voci["tacchino"])
    misto = await _ricetta(db_session, "Misto", voci["pollo"], voci["tacchino"])
    await _risposta(db_session, voci["tacchino"], ricetta=spezzatino, verdetto="omit", decided_by="human")
    await _risposta(db_session, voci["pollo"], ricetta=misto, verdetto="irreplaceable", decided_by="human")
    await _risposta(db_session, voci["tacchino"], ricetta=misto, verdetto="omit", decided_by="human")

    await merge_ingredients(db_session, voci["tacchino"], voci["pollo"])

    assert await _risposte(db_session, voci["pollo"]) == {
        (None, spezzatino, "omit", "human", ()),
        (None, misto, "irreplaceable", "human", ()),
    }


async def test_l_anteprima_non_sposta_niente(db_session, voci):
    await _risposta(db_session, voci["tacchino"], "salato", verdetto="omit")
    await _risposta(db_session, voci["coniglio"], "salato", sostituti=[voci["tacchino"]])

    await preview_merge(db_session, voci["tacchino"], voci["pollo"])

    assert await _risposte(db_session, voci["tacchino"]) == {("salato", None, "omit", "ai", ())}
    assert await _risposte(db_session, voci["coniglio"]) == {
        ("salato", None, "substitutes", "ai", ("tacchino",)),
    }
    assert await _risposte(db_session, voci["pollo"]) == set()
