"""L'import pulisce la dose dove il `payload` diventa ricetta (spec 2026-10-13, §3.10).

In un file suo: `test_materialize.py` lo cambiano altri piani della notte.
"""

from decimal import Decimal

import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import Recipe
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, RecipeImport, TermDecision
from app.domain.rules import IngredientRole
from app.repositories.imports import store_page
from app.repositories.recipes import get_recipe
from app.services.recipe_import.materialize import materialize_ready


@pytest_asyncio.fixture
async def farina(db_session):
    """La farina con due termini dell'import già decisi, come in `test_materialize.py`."""
    farina = Ingredient(
        name="farina", display_name="Farina", category=IngredientCategory.CEREALI
    )
    db_session.add(farina)
    await db_session.flush()
    db_session.add_all([
        ImportTerm(source=GIALLOZAFFERANO, term_key="farina-00", display_name="Farina 00",
                   occurrences=1, decision=TermDecision.MAPPED, ingredient_id=farina.id,
                   decided_by="human"),
        ImportTerm(source=GIALLOZAFFERANO, term_key="farina-0", display_name="Farina 0",
                   occurrences=1, decision=TermDecision.MAPPED, ingredient_id=farina.id,
                   decided_by="human"),
    ])
    await db_session.flush()
    return farina


async def _pagina(db_session, righe: list[tuple[str, str, str]]) -> None:
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/torta",
        payload={
            "title": "Torta", "description": None, "instructions": "Cuoci.", "servings": 4,
            "ingredients": [
                {"key": key, "name": name, "quantity_text": quantity}
                for key, name, quantity in righe
            ],
        },
    )
    await materialize_ready(db_session)


async def _unica_riga(db_session):
    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    dettaglio = await get_recipe(db_session, ricetta.id)
    assert len(dettaglio.ingredients) == 1
    return dettaglio.ingredients[0]


async def test_l_import_pulisce_la_dose_e_porta_le_parole_nella_nota(db_session, farina):
    await _pagina(db_session, [("farina-00", "Farina 00", "setacciata\n\t\t\t500\n\t\t\tg")])

    riga = await _unica_riga(db_session)
    assert (riga.quantity_text, riga.note) == ("500 g", "setacciata")
    assert riga.quantity_value == Decimal("500")


async def test_nel_collasso_le_dosi_si_uniscono_e_le_note_pure(db_session, farina):
    await _pagina(db_session, [
        ("farina-00", "Farina 00", "setacciata\n\t\t\t500\n\t\t\tg"),
        ("farina-0", "Farina 0", "per spolverare\n\n\t\t\tq.b."),
    ])

    riga = await _unica_riga(db_session)
    assert (riga.quantity_text, riga.note) == ("500 g + q.b.", "setacciata; per spolverare")
    # «+ q.b.» non toglie la dose: i 500 g si riscalano
    assert riga.quantity_value == Decimal("500")


async def test_il_ruolo_si_legge_dal_testo_come_e_arrivato(db_session, farina):
    """La pulizia non cambia ruoli (spec §3.10): «da setacciare ⏎⏎ q.b.» non comincia con
    «q.b.», quindi la farina resta principale come prima, anche se la dose pulita è «q.b.»."""
    await _pagina(db_session, [("farina-00", "Farina 00", "da setacciare\n\n\t\t\tq.b.")])

    riga = await _unica_riga(db_session)
    assert (riga.quantity_text, riga.note) == ("q.b.", "da setacciare")
    assert riga.role == IngredientRole.PRIMARY


async def test_il_payload_resta_come_e_arrivato(db_session, farina):
    """È la copia di quel che la pagina diceva: ogni ricetta rifatta da lì si ripulisce."""
    await _pagina(db_session, [("farina-00", "Farina 00", "setacciata\n\t\t\t500\n\t\t\tg")])

    pagina = (await db_session.execute(select(RecipeImport))).scalars().one()
    assert pagina.payload["ingredients"][0]["quantity_text"] == "setacciata\n\t\t\t500\n\t\t\tg"
