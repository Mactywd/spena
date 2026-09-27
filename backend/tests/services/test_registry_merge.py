"""La fusione di due ingredienti (S9 §5): tutto quel che punta al perdente passa al
vincitore, le ricette dell'import si rifanno, e le cotture ritrovano la ricetta.

Il mondo di prova ha un pezzo per ogni tabella che la fusione tocca: due pagine
dell'import (una con le due righe che diventano una), una ricetta scritta dall'AI, un
elemento di dispensa, una voce di lista, un prodotto, un alias scritto a mano.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.db.models.recipe import CookingEvent, RecipeIngredient, RecipeSource
from app.db.models.recipe_import import (
    GIALLOZAFFERANO,
    ImportState,
    ImportTerm,
    RecipeImport,
    TermDecision,
)
from app.db.models.shopping import ShoppingListItem, ShoppingReason, ShoppingStatus
from app.domain.rules import PantryStatus
from app.repositories.imports import store_page
from app.repositories.ingredients import add_alias, remember_alias
from app.repositories.recipes import create_recipe
from app.services.recipe_import.materialize import materialize_ready
from app.services.registry import (
    MergeCounts,
    RefusalCode,
    RegistryRefusal,
    merge_ingredients,
)

SUGO = "https://esempio.invalid/sugo"
BRUSCHETTA = "https://esempio.invalid/bruschetta"
PAGINE = {
    SUGO: ("Sugo semplice", [("k-pomodori", "Pomodori", "400 g"), ("k-basilico", "Basilico", "q.b.")]),
    BRUSCHETTA: ("Bruschetta", [("k-pomodori", "Pomodori", "2"), ("k-pomodoro", "Pomodoro", "1")]),
}


def _payload(title: str, righe: list[tuple[str, str, str]]) -> dict:
    return {
        "title": title, "description": None, "instructions": "Cuoci.", "servings": 2,
        "ingredients": [
            {"key": key, "name": name, "quantity_text": quantity} for key, name, quantity in righe
        ],
    }


@pytest_asyncio.fixture
async def mondo(db_session):
    def voce(name: str, display: str, category: str) -> Ingredient:
        return Ingredient(name=name, display_name=display, category=category)

    voci = {
        "pomodoro": voce("pomodoro", "Pomodoro", IngredientCategory.VERDURA),
        "pomodori": voce("pomodori", "Pomodori", IngredientCategory.VERDURA),
        "basilico": voce("basilico", "Basilico", IngredientCategory.SPEZIE),
        "detersivo": voce("detersivo", "Detersivo", IngredientCategory.CASA),
    }
    db_session.add_all(voci.values())
    await db_session.flush()

    def termine(key: str, display: str, voce_: str) -> ImportTerm:
        return ImportTerm(
            source=GIALLOZAFFERANO, term_key=key, display_name=display, occurrences=1,
            decision=TermDecision.MAPPED, ingredient_id=voci[voce_].id, decided_by="ai",
            decided_at=datetime.now(UTC),
        )

    termini = [
        termine("k-pomodori", "Pomodori", "pomodori"),
        termine("k-pomodoro", "Pomodoro", "pomodoro"),
        termine("k-basilico", "Basilico", "basilico"),
    ]
    db_session.add_all(termini)
    await db_session.flush()
    for term in termini:
        await remember_alias(db_session, term.ingredient_id, term.display_name)

    for url, (title, righe) in PAGINE.items():
        await store_page(db_session, source=GIALLOZAFFERANO, url=url, payload=_payload(title, righe))
    await materialize_ready(db_session, GIALLOZAFFERANO)

    await add_alias(db_session, voci["pomodori"].id, "pomodorini", source="manual")
    scritta = await create_recipe(
        db_session, title="Insalata dell'AI", description=None, instructions="Taglia.",
        servings=1, source=RecipeSource.AI, source_ref=None,
        ingredients=[(voci["pomodori"].id, "primary", "3", None)], embedding=None,
    )
    db_session.add(PantryItem(ingredient_id=voci["pomodori"].id, status=PantryStatus.AVAILABLE))
    db_session.add(ShoppingListItem(
        raw_text="pomodori", ingredient_id=voci["pomodori"].id,
        status=ShoppingStatus.PENDING, reason=ShoppingReason.MANUAL,
    ))
    db_session.add(Product(ingredient_id=voci["pomodori"].id, name="Pelati Cirio", source="custom"))
    await db_session.flush()
    return {**voci, "scritta": scritta}


async def _pagina(db_session, url: str) -> RecipeImport:
    return (
        await db_session.execute(select(RecipeImport).where(RecipeImport.url == url))
    ).scalar_one()


async def _righe(db_session, url: str) -> dict[str, str | None]:
    """Le righe della ricetta nata da quella pagina: ingrediente → dose."""
    page = await _pagina(db_session, url)
    assert page.state == ImportState.IMPORTED, page.state
    rows = await db_session.execute(
        select(Ingredient.name, RecipeIngredient.quantity_text)
        .join(Ingredient, Ingredient.id == RecipeIngredient.ingredient_id)
        .where(RecipeIngredient.recipe_id == page.recipe_id)
    )
    return dict(rows.all())


async def _chi_ha_l_alias(db_session, alias: str) -> list[str]:
    rows = await db_session.execute(
        select(Ingredient.name)
        .join(IngredientAlias, IngredientAlias.ingredient_id == Ingredient.id)
        .where(IngredientAlias.alias == alias)
    )
    return list(rows.scalars())


async def test_unire_porta_tutto_sul_vincitore_e_lo_conta(db_session, mondo):
    perdente, vincitore = mondo["pomodori"].id, mondo["pomodoro"].id

    conti = await merge_ingredients(db_session, perdente, vincitore)

    assert conti == MergeCounts(
        loser_name="pomodori", winner_name="pomodoro",
        recipes_rebuilt=2, recipe_lines_moved=1, pantry_items=1, shopping_items=1,
        products=1, aliases=2, cooking_events_relinked=0,
    )
    assert await db_session.get(Ingredient, perdente) is None
    assert "pomodoro" in await _righe(db_session, SUGO)
    # le due righe della bruschetta diventano una, come nella materializzazione
    assert await _righe(db_session, BRUSCHETTA) == {"pomodoro": "2 + 1"}
    # chi scrive ancora «pomodori» o «pomodorini» nella lista trova il pomodoro
    assert await _chi_ha_l_alias(db_session, "pomodori") == ["pomodoro"]
    assert await _chi_ha_l_alias(db_session, "pomodorini") == ["pomodoro"]
    lista = (await db_session.execute(select(ShoppingListItem))).scalar_one()
    assert lista.ingredient_id == vincitore
    scritta = (
        await db_session.execute(
            select(RecipeIngredient.ingredient_id).where(
                RecipeIngredient.recipe_id == mondo["scritta"].id
            )
        )
    ).scalars().all()
    assert scritta == [vincitore]


async def test_le_cotture_della_ricetta_rifatta_si_ri_legano(db_session, mondo, dal_database):
    """Il caso per cui la fusione è sicura da offrire a un tocco (spec §5.2, §9.3): una
    ricetta importata già cucinata si rifà, e la cottura punta alla ricetta nuova."""
    pagina = await _pagina(db_session, SUGO)
    evento = CookingEvent(recipe_id=pagina.recipe_id, servings=2, snapshot={"title": "Sugo semplice"})
    db_session.add(evento)
    await db_session.flush()
    evento_id, pagina_id, ricetta_vecchia = evento.id, pagina.id, pagina.recipe_id

    conti = await merge_ingredients(db_session, mondo["pomodori"].id, mondo["pomodoro"].id)

    assert conti.cooking_events_relinked == 1
    pagina = await dal_database(RecipeImport, pagina_id)
    cottura = await dal_database(CookingEvent, evento_id)
    assert pagina.recipe_id not in (None, ricetta_vecchia)
    assert cottura.recipe_id == pagina.recipe_id
    assert "cooking_event_ids" not in pagina.payload


async def test_un_alimento_e_una_voce_non_alimentare_non_si_uniscono(db_session, mondo):
    """Non è un vicolo cieco: il messaggio dice il passo (spec §5.3)."""
    with pytest.raises(RegistryRefusal) as rifiuto:
        await merge_ingredients(db_session, mondo["pomodori"].id, mondo["detersivo"].id)

    assert rifiuto.value.code == RefusalCode.KIND_MISMATCH
    assert rifiuto.value.obstacle is mondo["detersivo"]
    assert (
        "Prima porta «Pomodori» nello stesso reparto di «Detersivo», poi uniscili."
        in rifiuto.value.message
    )
    assert await db_session.get(Ingredient, mondo["pomodori"].id) is not None


async def test_un_ingrediente_non_si_unisce_a_se_stesso(db_session, mondo):
    with pytest.raises(RegistryRefusal) as rifiuto:
        await merge_ingredients(db_session, mondo["pomodoro"].id, mondo["pomodoro"].id)
    assert rifiuto.value.code == RefusalCode.SAME_INGREDIENT
