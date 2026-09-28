"""Un termine della coda, per id: quello a cui portano i rifiuti dell'anagrafica.

«Decisioni recenti» mostra le ultime 50 dell'AI e le ultime 50 a mano, e mai quelle
`auto`: un termine deciso tempo fa non ci sta più, e un rifiuto che dicesse «annullalo
in coda» porterebbe a una schermata dove non c'è (revisione finale di S9). Questa rotta
lo legge comunque, nella stessa forma dell'elenco: deciso come in «Decisioni recenti»,
in attesa come nella coda.
"""

import uuid

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe_import import (
    GIALLOZAFFERANO,
    ImportState,
    ImportTerm,
    RecipeImport,
    TermDecision,
)
from app.repositories.ingredients import create_ingredient


async def test_un_termine_deciso_torna_nella_forma_delle_decisioni(logged_client, db_session):
    pasta = await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-rigatoni", display_name="Rigatoni",
        occurrences=3, decision=TermDecision.MAPPED, ingredient_id=pasta.id, decided_by="auto",
    )
    db_session.add(term)
    await db_session.flush()

    response = await logged_client.get(f"/api/v1/imports/terms/{term.id}")

    assert response.status_code == 200
    voce = response.json()
    assert (voce["id"], voce["display_name"]) == (str(term.id), "Rigatoni")
    assert (voce["decided_action"], voce["decided_name"], voce["decided_by"]) == (
        "map", "pasta", "auto",
    )
    # decisa prima che il fatto si scrivesse: non si sa se l'ha creata
    assert voce["created_ingredient"] is None


async def test_un_termine_deciso_dice_se_ha_creato_lingrediente(logged_client, db_session):
    speck = await create_ingredient(
        db_session, name="speck", display_name="Speck", category=IngredientCategory.CARNE
    )
    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-speck", display_name="Speck", occurrences=1,
        decision=TermDecision.MAPPED, ingredient_id=speck.id, decided_by="ai",
        created_ingredient=True,
    )
    db_session.add(term)
    await db_session.flush()

    voce = (await logged_client.get(f"/api/v1/imports/terms/{term.id}")).json()
    assert voce["created_ingredient"] is True
    elenco = (await logged_client.get("/api/v1/imports/terms?decided_by=ai")).json()
    assert [v["created_ingredient"] for v in elenco] == [True]


async def test_un_termine_in_attesa_torna_nella_forma_della_coda(logged_client, db_session):
    await create_ingredient(
        db_session, name="basilico", display_name="Basilico", category=IngredientCategory.SPEZIE
    )
    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-basilico", display_name="Basilico",
        occurrences=1, decision=TermDecision.PENDING,
    )
    db_session.add_all([
        term,
        RecipeImport(
            source=GIALLOZAFFERANO, url="https://esempio.invalid/pesto", state=ImportState.PENDING,
            payload={"title": "Pesto", "ingredients": [{"key": "k-basilico"}]},
        ),
    ])
    await db_session.flush()

    voce = (await logged_client.get(f"/api/v1/imports/terms/{term.id}")).json()

    assert voce["decided_action"] is None
    assert voce["waiting_titles"] == ["Pesto"]
    assert voce["suggestion"]["name"] == "basilico"


async def test_un_termine_che_non_ce_e_un_404(logged_client):
    response = await logged_client.get(f"/api/v1/imports/terms/{uuid.uuid4()}")
    assert response.status_code == 404
