"""La rotta che fa decidere all'AI i termini rimasti in coda.

Non torna proposte da confermare: applica, e dice quante ricette ha sbloccato. È la
differenza fra la coda di prima — un modulo da compilare — e quella di adesso, che è
la revisione di un lavoro già fatto.

Le rotte di `/imports` sono dietro `require_session` (vedi
`test_senza_sessione_non_si_guarda_niente` in `test_imports.py`): qui si usa
`logged_client`, non `client`, per la stessa ragione di ogni altro test in questo
modulo.
"""

import pytest
from sqlalchemy import select

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.repositories.ingredients import create_ingredient
from llm_fakes import ScriptedLlm, llm_map


@pytest.fixture(autouse=True)
def chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


async def test_la_rotta_applica_e_dice_cosa_resta(logged_client, db_session, monkeypatch):
    await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-rigatoni", display_name="Rigatoni",
        occurrences=3, decision=TermDecision.PENDING,
    )
    db_session.add(term)
    await db_session.flush()

    # il client finto si inietta sostituendo la funzione che apre quello vero: la
    # rotta non ha un parametro per passarlo, e non deve averlo — un parametro
    # iniettabile da HTTP sarebbe una via per far parlare il backend con un endpoint
    # scelto da chi chiama
    import app.services.recipe_import.decide as modulo

    monkeypatch.setattr(
        modulo, "open_client", lambda: ScriptedLlm({"Rigatoni": llm_map("pasta")})
    )

    response = await logged_client.post("/api/v1/imports/terms/decide", json={})
    assert response.status_code == 200
    corpo = response.json()
    assert corpo["applied"] == 1
    assert corpo["still_pending"] == 0
    assert corpo["remaining_terms"] == 0

    await db_session.refresh(term)
    assert term.decision == TermDecision.MAPPED
    assert term.decided_by == "ai"


async def test_senza_chiave_risponde_503_e_dice_che_la_coda_funziona(
    logged_client, db_session, monkeypatch
):
    from app.core.config import get_settings

    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-speck", display_name="Speck",
        occurrences=1, decision=TermDecision.PENDING,
    )
    db_session.add(term)
    await db_session.flush()

    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    try:
        response = await logged_client.post("/api/v1/imports/terms/decide", json={})
        assert response.status_code == 503
        assert "a mano" in response.json()["detail"]
    finally:
        get_settings.cache_clear()

    await db_session.refresh(term)
    assert term.decision == TermDecision.PENDING


async def test_senza_termini_in_coda_non_e_un_errore(logged_client):
    """Una coda vuota è il caso migliore, non un 404: la schermata non deve allarmare."""
    response = await logged_client.post("/api/v1/imports/terms/decide", json={})
    assert response.status_code == 200
    assert response.json()["applied"] == 0


async def test_term_ids_restringe_a_quei_termini(logged_client, db_session, monkeypatch):
    await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    uno = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-rigatoni", display_name="Rigatoni",
        occurrences=3, decision=TermDecision.PENDING,
    )
    due = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-penne", display_name="Penne",
        occurrences=2, decision=TermDecision.PENDING,
    )
    db_session.add_all([uno, due])
    await db_session.flush()

    import app.services.recipe_import.decide as modulo

    monkeypatch.setattr(
        modulo, "open_client", lambda: ScriptedLlm({"Rigatoni": llm_map("pasta")})
    )

    response = await logged_client.post(
        "/api/v1/imports/terms/decide", json={"term_ids": [str(uno.id)]}
    )
    assert response.status_code == 200
    await db_session.refresh(due)
    assert due.decision == TermDecision.PENDING


async def test_la_vecchia_rotta_delle_proposte_non_esiste_piu(client):
    """Una rotta morta che risponde 200 è peggio di una che non c'è.

    Il frontend non la chiama più; lasciarla in piedi significherebbe mantenere due
    modi di decidere, e uno dei due non sarebbe mai esercitato. Qui basta `client`
    senza login: una rotta assente risponde 404 dal router prima ancora che
    `require_session` entri in gioco.
    """
    response = await client.post(
        "/api/v1/imports/terms/proposals", json={"term_ids": []}
    )
    assert response.status_code == 404
