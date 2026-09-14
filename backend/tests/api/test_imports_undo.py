"""La rotta dell'annullamento, e il 409 che chiede conferma sullo storico.

Le rotte di `/imports` sono dietro `require_session` (vedi
`test_senza_sessione_non_si_guarda_niente` in `test_imports.py`): qui si usa
`logged_client`, non `client`, per la stessa ragione di ogni altro test in questo
modulo.
"""

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe import CookingEvent, RecipeSource
from app.db.models.recipe_import import (
    GIALLOZAFFERANO,
    ImportState,
    ImportTerm,
    RecipeImport,
    TermDecision,
)
from app.repositories.ingredients import create_ingredient, remember_alias
from app.repositories.recipes import create_recipe


async def prepara(db_session):
    speck = await create_ingredient(
        db_session, name="speck", display_name="Speck", category=IngredientCategory.CARNE
    )
    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-speck", display_name="Speck",
        occurrences=1, decision=TermDecision.MAPPED, ingredient_id=speck.id, decided_by="ai",
    )
    db_session.add(term)
    await db_session.flush()
    await remember_alias(db_session, speck.id, "Speck")
    recipe = await create_recipe(
        db_session, title="Pasta allo speck", description=None, instructions="cuoci",
        servings=2, source=RecipeSource.DATASET, source_ref="https://esempio.invalid/1",
        ingredients=[(speck.id, "primary", None, None)], embedding=None,
    )
    db_session.add(
        RecipeImport(
            source=GIALLOZAFFERANO, url="https://esempio.invalid/1",
            payload={"title": "Pasta allo speck", "ingredients": [{"key": "k-speck"}]},
            state=ImportState.IMPORTED, recipe_id=recipe.id,
        )
    )
    await db_session.flush()
    return term, recipe


async def test_annulla_e_dice_quante_ricette_sono_tornate_in_coda(logged_client, db_session):
    term, _ = await prepara(db_session)
    response = await logged_client.post(f"/api/v1/imports/terms/{term.id}/undo", json={})
    assert response.status_code == 200
    corpo = response.json()
    assert corpo["recipes_requeued"] == 1
    assert corpo["ingredient_deleted"] is True
    assert corpo["remaining_terms"] == 1

    await db_session.refresh(term)
    assert term.decision == TermDecision.PENDING


async def test_una_ricetta_cucinata_risponde_409_col_numero(logged_client, db_session):
    term, recipe = await prepara(db_session)
    db_session.add(CookingEvent(recipe_id=recipe.id, servings=2, snapshot={}))
    await db_session.flush()

    response = await logged_client.post(f"/api/v1/imports/terms/{term.id}/undo", json={})
    assert response.status_code == 409
    # il numero deve stare nel messaggio: è ciò che la schermata mostra
    assert "1" in response.json()["detail"]

    await db_session.refresh(term)
    assert term.decision == TermDecision.MAPPED


async def test_con_force_procede(logged_client, db_session):
    term, recipe = await prepara(db_session)
    db_session.add(CookingEvent(recipe_id=recipe.id, servings=2, snapshot={}))
    await db_session.flush()

    response = await logged_client.post(
        f"/api/v1/imports/terms/{term.id}/undo", json={"force": True}
    )
    assert response.status_code == 200
    await db_session.refresh(term)
    assert term.decision == TermDecision.PENDING


async def test_un_termine_inesistente_risponde_404(logged_client):
    response = await logged_client.post(
        "/api/v1/imports/terms/00000000-0000-0000-0000-000000000000/undo", json={}
    )
    assert response.status_code == 404


async def test_un_termine_ancora_in_coda_non_si_annulla(logged_client, db_session):
    """Non c'è niente da disfare, e un 200 farebbe credere il contrario."""
    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-boh", display_name="Boh",
        occurrences=1, decision=TermDecision.PENDING,
    )
    db_session.add(term)
    await db_session.flush()

    response = await logged_client.post(f"/api/v1/imports/terms/{term.id}/undo", json={})
    assert response.status_code == 409
    assert "già in coda" in response.json()["detail"]
