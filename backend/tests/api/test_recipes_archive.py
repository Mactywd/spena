"""Eliminare archivia, con la lapide (R10 §5): la ricetta resta, e si ripristina.

Non c'è una `DELETE`: la `PATCH` accetta `archived`, come la dispensa. Il dettaglio
risponde anche per una ricetta archiviata, così un collegamento vecchio non finisce in
un 404.
"""

from app.db.models.recipe import CookingEvent, Recipe, RecipeSource
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportState, RecipeImport
from app.repositories.recipes import create_recipe

CARBONARA = "https://ricette.giallozafferano.it/Spaghetti-alla-Carbonara.html"


async def _ricetta(db_session, *, source=RecipeSource.MANUAL, source_ref=None, cost=None) -> Recipe:
    return await create_recipe(
        db_session, title="Carbonara", description=None, instructions="Manteca.",
        servings=2, source=source, source_ref=source_ref, ingredients=[], embedding=None,
        cost=cost,
    )


async def _archivia(client, ricetta, archived: bool):
    return await client.patch(f"/api/v1/recipes/{ricetta.id}", json={"archived": archived})


async def _dettaglio(client, ricetta) -> dict:
    risposta = await client.get(f"/api/v1/recipes/{ricetta.id}")
    assert risposta.status_code == 200, risposta.text
    return risposta.json()


async def test_eliminare_scrive_la_data_e_il_dettaglio_risponde_ancora(logged_client, db_session):
    ricetta = await _ricetta(db_session)

    risposta = await _archivia(logged_client, ricetta, True)

    assert risposta.status_code == 200, risposta.text
    assert risposta.json()["archived_at"] is not None
    assert (await _dettaglio(logged_client, ricetta))["archived_at"] == risposta.json()["archived_at"]


async def test_ripristinare_toglie_la_data(logged_client, db_session):
    ricetta = await _ricetta(db_session)
    await _archivia(logged_client, ricetta, True)

    risposta = await _archivia(logged_client, ricetta, False)

    assert risposta.json()["archived_at"] is None
    assert (await _dettaglio(logged_client, ricetta))["archived_at"] is None


async def test_eliminare_due_volte_tiene_la_prima_data(logged_client, db_session):
    ricetta = await _ricetta(db_session)
    prima = (await _archivia(logged_client, ricetta, True)).json()["archived_at"]
    assert (await _archivia(logged_client, ricetta, True)).json()["archived_at"] == prima


async def test_eliminare_una_ricetta_importata_la_prende_in_carico_per_sempre(
    logged_client, db_session, dal_database
):
    ricetta = await _ricetta(db_session, source=RecipeSource.DATASET, source_ref=CARBONARA)
    pagina = RecipeImport(
        source=GIALLOZAFFERANO, url=CARBONARA, payload={"title": "Carbonara", "ingredients": []},
        state=ImportState.IMPORTED, recipe_id=ricetta.id,
    )
    db_session.add(pagina)
    await db_session.flush()
    assert (await _dettaglio(logged_client, ricetta))["owned_by_import"] is True

    await _archivia(logged_client, ricetta, True)
    assert (await dal_database(RecipeImport, pagina.id)).state == ImportState.ADOPTED

    # ripristinare non la rende di nuovo dell'import (spec §4: non torna mai indietro)
    await _archivia(logged_client, ricetta, False)
    assert (await dal_database(RecipeImport, pagina.id)).state == ImportState.ADOPTED
    assert (await _dettaglio(logged_client, ricetta))["owned_by_import"] is False


async def test_una_ricetta_scritta_qui_non_e_dell_import(logged_client, db_session):
    ricetta = await _ricetta(db_session)
    assert (await _dettaglio(logged_client, ricetta))["owned_by_import"] is False


async def test_le_cotture_restano_legate(logged_client, db_session, dal_database):
    ricetta = await _ricetta(db_session)
    evento = CookingEvent(recipe_id=ricetta.id, servings=2, snapshot={"transitions": [], "restocked": 0})
    db_session.add(evento)
    await db_session.flush()

    await _archivia(logged_client, ricetta, True)
    assert (await dal_database(CookingEvent, evento.id)).recipe_id == ricetta.id
    await _archivia(logged_client, ricetta, False)
    assert (await dal_database(CookingEvent, evento.id)).recipe_id == ricetta.id


async def test_il_costo_di_una_ricetta_eliminata_non_si_cambia(logged_client, db_session):
    ricetta = await _ricetta(db_session, cost=2)
    await _archivia(logged_client, ricetta, True)

    risposta = await logged_client.patch(f"/api/v1/recipes/{ricetta.id}", json={"cost": 4})

    assert risposta.status_code == 409
    assert "ripristinala" in risposta.json()["detail"]
    # una PATCH vuota resta innocua anche qui
    assert (await logged_client.patch(f"/api/v1/recipes/{ricetta.id}", json={})).status_code == 200


async def test_archived_vuole_un_booleano(logged_client, db_session):
    ricetta = await _ricetta(db_session)
    risposta = await logged_client.patch(f"/api/v1/recipes/{ricetta.id}", json={"archived": "sì"})
    assert risposta.status_code == 422
