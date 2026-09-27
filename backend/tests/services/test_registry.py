"""Il servizio unico dell'anagrafica (S9 §3): una prova per funzione e una per rifiuto.

Su Postgres vero, come tutto: le guardie leggono le righe di ricetta e gli alias con
query, e un finto database proverebbe una copia di quelle query.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.recipe import RecipeSource
from app.domain.rules import IngredientKind
from app.repositories.recipes import create_recipe
from app.services.registry import (
    RecipeRef,
    RefusalCode,
    RegistryRefusal,
    recategorize_ingredient,
    rename_ingredient,
)


@pytest_asyncio.fixture
async def anagrafica(db_session):
    def voce(name: str, display: str, category: str) -> Ingredient:
        return Ingredient(name=name, display_name=display, category=category)

    voci = {
        "pomodoro": voce("pomodoro", "Pomodoro", IngredientCategory.VERDURA),
        "pomodori": voce("pomodori", "Pomodori", IngredientCategory.VERDURA),
        "burro": voce("burro", "Burro", IngredientCategory.LATTICINI),
        "parmigiano": voce("parmigiano", "Parmigiano", IngredientCategory.LATTICINI),
        "salvia": voce("salvia", "Salvia", IngredientCategory.SPEZIE),
    }
    db_session.add_all(voci.values())
    await db_session.flush()
    return voci


async def _alias(db_session, ingredient_id) -> dict[str, str]:
    """Gli alias di un ingrediente, con la loro fonte."""
    rows = await db_session.execute(
        select(IngredientAlias.alias, IngredientAlias.source).where(
            IngredientAlias.ingredient_id == ingredient_id
        )
    )
    return dict(rows.all())


async def test_rinominare_scrive_i_due_nomi_e_il_vecchio_resta_come_alias(db_session, anagrafica):
    pomodori = anagrafica["pomodori"]

    await rename_ingredient(db_session, pomodori.id, name="Pomodorini", display_name="Pomodorini")

    assert pomodori.name == "pomodorini"
    assert pomodori.display_name == "Pomodorini"
    # «manual» e non «import»: il vecchio nome non è la metà di nessuna decisione della
    # coda, e marcato «import» diventerebbe un alias che l'anagrafica non può toccare
    assert await _alias(db_session, pomodori.id) == {"pomodori": "manual"}


async def test_un_nome_gia_preso_rifiuta_e_porta_l_omonimo(db_session, anagrafica):
    """Il rifiuto porta l'ingrediente che ha già quel nome: lo schermo ne fa «Uniscili»."""
    with pytest.raises(RegistryRefusal) as rifiuto:
        await rename_ingredient(db_session, anagrafica["pomodori"].id, name=" Pomodoro ")

    assert rifiuto.value.code == RefusalCode.NAME_TAKEN
    assert rifiuto.value.obstacle is anagrafica["pomodoro"]
    assert "già in anagrafica" in rifiuto.value.message
    assert anagrafica["pomodori"].name == "pomodori"


async def test_un_nome_vuoto_rifiuta_senza_toccare_niente(db_session, anagrafica):
    """Il controllo viene prima di ogni scrittura: un rifiuto a metà lascerebbe il nome
    nuovo con il nome a video vecchio."""
    with pytest.raises(RegistryRefusal) as rifiuto:
        await rename_ingredient(
            db_session, anagrafica["pomodori"].id, name="Pomodorini", display_name="   "
        )

    assert rifiuto.value.code == RefusalCode.EMPTY_NAME
    assert anagrafica["pomodori"].name == "pomodori"


async def test_rinominare_un_ingrediente_che_non_c_e(db_session):
    with pytest.raises(LookupError):
        await rename_ingredient(db_session, uuid.uuid4(), name="qualcosa")


async def test_cambiare_reparto_ricalcola_il_tipo(db_session, anagrafica):
    salvia = anagrafica["salvia"]

    await recategorize_ingredient(db_session, salvia.id, "casa")

    assert salvia.category == "casa"
    # `kind` non si scrive: lo deriva il `@validates` del modello dal reparto
    assert salvia.kind == IngredientKind.NON_FOOD


async def test_il_non_alimentare_con_ricette_rifiuta_e_le_elenca(db_session, anagrafica):
    burro = anagrafica["burro"]
    risotto = await create_recipe(
        db_session, title="Risotto al burro", description=None, instructions="Manteca.",
        servings=2, source=RecipeSource.AI, source_ref=None,
        ingredients=[(burro.id, "primary", "50 g", None)], embedding=None,
    )

    with pytest.raises(RegistryRefusal) as rifiuto:
        await recategorize_ingredient(db_session, burro.id, "casa")

    assert rifiuto.value.code == RefusalCode.NON_FOOD_IN_RECIPES
    assert rifiuto.value.obstacle.count == 1
    assert rifiuto.value.obstacle.recipes == (RecipeRef(id=risotto.id, title="Risotto al burro"),)
    assert "non può diventare non alimentare" in rifiuto.value.message
    assert burro.category == "latticini"


async def test_un_reparto_sconosciuto_rifiuta(db_session, anagrafica):
    with pytest.raises(RegistryRefusal) as rifiuto:
        await recategorize_ingredient(db_session, anagrafica["salvia"].id, "bagno")
    assert rifiuto.value.code == RefusalCode.UNKNOWN_CATEGORY
