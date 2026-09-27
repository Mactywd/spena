"""La rotta dell'annullamento, che dalla S9 non chiede più conferma.

Le rotte di `/imports` sono dietro `require_session` (vedi
`test_senza_sessione_non_si_guarda_niente` in `test_imports.py`): qui si usa
`logged_client`, non `client`, per la stessa ragione di ogni altro test in questo
modulo.
"""

from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import CookingEvent, RecipeSource
from app.db.models.recipe_import import (
    GIALLOZAFFERANO,
    ImportState,
    ImportTerm,
    RecipeImport,
    TermDecision,
)
from app.repositories.imports import store_page
from app.repositories.ingredients import create_ingredient, remember_alias
from app.repositories.recipes import create_recipe
from app.services.recipe_import.terms import sync_terms


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


async def test_una_ricetta_cucinata_non_blocca_piu_l_annullamento(logged_client, db_session):
    """Fino a S9 qui c'era un 409 che chiedeva conferma. Le cotture ora si ri-legano
    (spec §5.2): l'annullamento non scollega più niente, e non c'è niente da
    confermare."""
    term, recipe = await prepara(db_session)
    db_session.add(CookingEvent(recipe_id=recipe.id, servings=2, snapshot={}))
    await db_session.flush()

    response = await logged_client.post(f"/api/v1/imports/terms/{term.id}/undo", json={})

    assert response.status_code == 200
    assert response.json()["recipes_requeued"] == 1
    await db_session.refresh(term)
    assert term.decision == TermDecision.PENDING


async def test_un_corpo_con_force_di_una_pwa_vecchia_non_rompe_niente(logged_client, db_session):
    """Una PWA con la cache di prima manda ancora `{"force": ...}`: la rotta lo ignora."""
    term, _ = await prepara(db_session)

    response = await logged_client.post(
        f"/api/v1/imports/terms/{term.id}/undo", json={"force": True}
    )

    assert response.status_code == 200


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


async def test_una_decisione_presa_a_mano_si_annulla_come_quella_dellai(
    logged_client, db_session
):
    """R11: l'annulla non guarda chi ha deciso. Il giro intero passa dalle rotte —
    decisione a mano che crea l'ingrediente, elenco `decided_by=human`, annulla — perché
    è quello il percorso che la schermata fa, e un termine costruito a mano nel test
    non direbbe se la decisione vera lascia qualcosa che l'annulla non sa disfare."""
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/bottarga",
        payload={
            "title": "Crostini alla bottarga", "description": "Breve",
            "instructions": "Cuoci.", "servings": 2, "category": "Antipasti",
            "image_url": None, "prep_minutes": 5, "cook_minutes": 5,
            "ingredients": [
                {"key": "k-bottarga", "name": "Bottarga", "quantity_text": "20 g"}
            ],
            "nutrition": None,
        },
    )
    await sync_terms(db_session)
    term = (
        await db_session.execute(select(ImportTerm).where(ImportTerm.term_key == "k-bottarga"))
    ).scalars().one()

    decisa = await logged_client.post(
        f"/api/v1/imports/terms/{term.id}/decision",
        json={"action": "create", "name": "bottarga", "display_name": "Bottarga",
              "category": "pesce"},
    )
    assert decisa.status_code == 200
    assert decisa.json()["unlocked"] == 1

    elenco = (await logged_client.get("/api/v1/imports/terms?decided_by=human")).json()
    assert [v["id"] for v in elenco] == [str(term.id)]

    response = await logged_client.post(f"/api/v1/imports/terms/{term.id}/undo", json={})
    assert response.status_code == 200
    corpo = response.json()
    assert corpo["recipes_requeued"] == 1
    assert corpo["ingredient_deleted"] is True

    await db_session.refresh(term)
    assert term.decision == TermDecision.PENDING
    assert term.decided_by is None
    assert (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "bottarga"))
    ).scalars().first() is None
    assert (await logged_client.get("/api/v1/imports/terms?decided_by=human")).json() == []
