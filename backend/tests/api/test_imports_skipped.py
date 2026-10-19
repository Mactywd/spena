"""Le pagine scartate dell'import: l'elenco col perché, e la rimessa in coda (spec
docs/superpowers/specs/2026-10-09-scartate-in-coda-design.md).

Le rotte di `/imports` sono dietro `require_session` (vedi
`test_senza_sessione_non_si_guarda_niente` in `test_imports.py`): qui si usa
`logged_client`, tranne nell'ultimo test.
"""

import uuid

import pytest_asyncio

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportState, ImportTerm, TermDecision
from app.repositories.imports import store_page, store_unparsable
from app.repositories.ingredients import create_ingredient
from app.services.recipe_import.materialize import materialize_ready

ELENCO = "/api/v1/imports/pages/skipped"


def pagina(title: str, righe: list[tuple[str, str]]) -> dict:
    return {
        "title": title, "instructions": "Cuoci.", "servings": 4,
        "ingredients": [
            {"key": key, "name": name, "quantity_text": "100 g"} for key, name in righe
        ],
    }


@pytest_asyncio.fixture
async def scarico(db_session):
    """Cinque pagine: tre scartate — una illeggibile, una con la riga tutta ignorata, una
    con una riga non alimentare — una in attesa e una importata."""
    farina = await create_ingredient(
        db_session, name="farina", display_name="Farina", category=IngredientCategory.CEREALI
    )
    panna = await create_ingredient(
        db_session, name="panna", display_name="Panna", category=IngredientCategory.CASA
    )
    db_session.add_all([
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-farina", display_name="Farina 00",
            occurrences=1, decision=TermDecision.MAPPED, ingredient_id=farina.id,
            decided_by="human", created_ingredient=False,
        ),
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-panna", display_name="Panna fresca",
            occurrences=1, decision=TermDecision.MAPPED, ingredient_id=panna.id,
            decided_by="human", created_ingredient=False,
        ),
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-acqua", display_name="Acqua",
            occurrences=1, decision=TermDecision.IGNORED, decided_by="human",
        ),
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-lievito", display_name="Lievito madre",
            occurrences=1, decision=TermDecision.PENDING,
        ),
    ])
    await db_session.flush()
    pagine = {
        "vuota": await store_unparsable(
            db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/vuota",
            reason="nessuna riga dd.gz-ingredient nella pagina",
        ),
        "torta": await store_page(
            db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/torta",
            payload=pagina("Torta alla panna", [("k-farina", "Farina 00"), ("k-panna", "Panna fresca")]),
        ),
        "acqua": await store_page(
            db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/acqua",
            payload=pagina("Acqua calda", [("k-acqua", "Acqua")]),
        ),
        "pane": await store_page(
            db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/pane",
            payload=pagina("Pane", [("k-farina", "Farina 00")]),
        ),
        "focaccia": await store_page(
            db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/focaccia",
            payload=pagina("Focaccia", [("k-farina", "Farina 00"), ("k-lievito", "Lievito madre")]),
        ),
    }
    await materialize_ready(db_session, GIALLOZAFFERANO)
    assert [pagine[n].state for n in ("vuota", "torta", "acqua", "pane", "focaccia")] == [
        ImportState.SKIPPED, ImportState.SKIPPED, ImportState.SKIPPED,
        ImportState.IMPORTED, ImportState.PENDING,
    ]
    return {**pagine, "panna": panna}


async def test_lelenco_dice_per_ogni_scartata_il_perche(logged_client, scarico):
    risposta = await logged_client.get(ELENCO)

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert corpo["total"] == 3
    per_indirizzo = {voce["url"]: voce for voce in corpo["pages"]}
    assert set(per_indirizzo) == {
        "https://esempio.invalid/vuota", "https://esempio.invalid/torta",
        "https://esempio.invalid/acqua",
    }
    assert per_indirizzo["https://esempio.invalid/vuota"] == {
        "id": str(scarico["vuota"].id), "url": "https://esempio.invalid/vuota", "title": None,
        "cause": "unreadable", "non_food_name": None, "requeueable": False,
        "waiting_cooking_events": 0,
    }
    torta = per_indirizzo["https://esempio.invalid/torta"]
    assert (torta["title"], torta["cause"], torta["non_food_name"], torta["requeueable"]) == (
        "Torta alla panna", "non_food", "Panna", True,
    )
    acqua = per_indirizzo["https://esempio.invalid/acqua"]
    assert (acqua["title"], acqua["cause"], acqua["non_food_name"], acqua["requeueable"]) == (
        "Acqua calda", "all_ignored", None, True,
    )


async def test_le_cotture_che_aspettano_si_contano(logged_client, db_session, scarico):
    torta = scarico["torta"]
    torta.payload = {**torta.payload, "cooking_event_ids": [str(uuid.uuid4()), str(uuid.uuid4())]}
    await db_session.flush()

    corpo = (await logged_client.get(ELENCO)).json()

    assert {voce["url"]: voce["waiting_cooking_events"] for voce in corpo["pages"]}[
        "https://esempio.invalid/torta"
    ] == 2


async def test_lelenco_si_sfoglia_senza_doppioni(logged_client, scarico):
    prima = (await logged_client.get(f"{ELENCO}?limit=2&offset=0")).json()
    seconda = (await logged_client.get(f"{ELENCO}?limit=2&offset=2")).json()

    assert (prima["total"], seconda["total"]) == (3, 3)
    assert (len(prima["pages"]), len(seconda["pages"])) == (2, 1)
    assert len({voce["id"] for voce in prima["pages"] + seconda["pages"]}) == 3


async def test_un_limite_fuori_misura_si_rifiuta(logged_client, scarico):
    for query in ("limit=0", "limit=101", "offset=-1"):
        assert (await logged_client.get(f"{ELENCO}?{query}")).status_code == 422, query


async def test_rimessa_dopo_la_correzione_entra_nel_ricettario(logged_client, db_session, scarico):
    scarico["panna"].category = IngredientCategory.LATTICINI
    await db_session.flush()

    risposta = await logged_client.post(f"/api/v1/imports/pages/{scarico['torta'].id}/requeue")

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert (corpo["outcome"], corpo["title"], corpo["url"]) == (
        "imported", "Torta alla panna", "https://esempio.invalid/torta",
    )
    assert (corpo["cooking_relinked"], corpo["cause"], corpo["non_food_name"], corpo["waiting_terms"]) == (
        0, None, None, [],
    )
    ricetta = await logged_client.get(f"/api/v1/recipes/{corpo['recipe_id']}")
    assert ricetta.status_code == 200
    assert ricetta.json()["title"] == "Torta alla panna"
    assert (await logged_client.get("/api/v1/imports/status")).json()["skipped"] == 2


async def test_rimessa_senza_correggere_torna_scartata_e_dice_perche(logged_client, scarico):
    risposta = await logged_client.post(f"/api/v1/imports/pages/{scarico['torta'].id}/requeue")

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert (corpo["outcome"], corpo["cause"], corpo["non_food_name"], corpo["recipe_id"]) == (
        "skipped", "non_food", "Panna", None,
    )
    assert (await logged_client.get("/api/v1/imports/status")).json()["skipped"] == 3


async def test_una_pagina_illeggibile_si_rifiuta_col_perche(logged_client, scarico):
    risposta = await logged_client.post(f"/api/v1/imports/pages/{scarico['vuota'].id}/requeue")

    assert risposta.status_code == 409
    assert "non aveva una ricetta leggibile" in risposta.json()["detail"]


async def test_una_pagina_non_scartata_si_rifiuta(logged_client, scarico):
    risposta = await logged_client.post(f"/api/v1/imports/pages/{scarico['focaccia'].id}/requeue")

    assert risposta.status_code == 409
    assert "non è più scartata" in risposta.json()["detail"]


async def test_una_pagina_che_non_ce(logged_client, scarico):
    risposta = await logged_client.post(f"/api/v1/imports/pages/{uuid.uuid4()}/requeue")

    assert risposta.status_code == 404


async def test_senza_sessione_non_si_guarda_e_non_si_rimette_niente(client):
    assert (await client.get(ELENCO)).status_code == 401
    assert (await client.post(f"/api/v1/imports/pages/{uuid.uuid4()}/requeue")).status_code == 401
