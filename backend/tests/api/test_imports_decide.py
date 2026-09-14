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


async def test_lista_vuota_di_term_ids_e_un_no_op(logged_client, db_session, monkeypatch):
    """Una lista vuota `[]` non significa «tutto quanto in coda»: significa zero termini.

    La distinzione importa perché il payload può omettere `term_ids` (significa "tutti"),
    oppure passare una lista (significa "questi"). Una lista vuota deve essere un no-op:
    nessun termine viene deciso, nessuno è applicato, il database resta intatto.
    """
    await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )

    # Creiamo diversi termini PENDING nella coda
    terms = [
        ImportTerm(
            source=GIALLOZAFFERANO, term_key=f"k-pasta-{i}", display_name=f"Pasta {i}",
            occurrences=1, decision=TermDecision.PENDING,
        )
        for i in range(5)
    ]
    db_session.add_all(terms)
    await db_session.flush()

    # Fake LLM che mapperebbe tutti i termini se chiamato
    import app.services.recipe_import.decide as modulo

    monkeypatch.setattr(
        modulo, "open_client",
        lambda: ScriptedLlm({f"Pasta {i}": llm_map("pasta") for i in range(5)})
    )

    # Mandiamo term_ids vuoto: deve essere un no-op (zero termini decisi)
    response = await logged_client.post(
        "/api/v1/imports/terms/decide", json={"term_ids": []}
    )
    assert response.status_code == 200
    corpo = response.json()
    # Niente è stato deciso: la lista vuota significa "questi zero termini"
    assert corpo["applied"] == 0
    assert corpo["created"] == 0
    assert corpo["ignored"] == 0
    # still_pending è 0 perché abbiamo passato 0 termini a decide_terms
    # ma remaining_terms nel database è ancora 5 (non abbiamo toccato niente)
    assert corpo["still_pending"] == 0
    assert corpo["remaining_terms"] == 5

    # Nel database, tutti i termini restano PENDING
    for term in terms:
        await db_session.refresh(term)
        assert term.decision == TermDecision.PENDING


async def test_term_ids_non_decide_termini_da_altra_fonte(
    logged_client, db_session, monkeypatch
):
    """Un termine che appartiene a un'altra source non viene deciso nemmeno se
    passato esplicitamente in `term_ids`.

    La rotta deve filtrare per source come fa nel ramo senza `term_ids`.
    """
    # Creiamo un ingrediente per la verifica
    await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )

    # Creiamo un termine da GIALLOZAFFERANO (quello che vogliamo decidere)
    term_gz = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-rigatoni", display_name="Rigatoni",
        occurrences=1, decision=TermDecision.PENDING,
    )

    # Creiamo un termine da un'altra source
    altro_source = "altro-catalogo"
    term_altro = ImportTerm(
        source=altro_source, term_key="k-penne", display_name="Penne",
        occurrences=1, decision=TermDecision.PENDING,
    )
    db_session.add_all([term_gz, term_altro])
    await db_session.flush()

    # Fake LLM che sa decidere entrambi
    import app.services.recipe_import.decide as modulo

    monkeypatch.setattr(
        modulo, "open_client",
        lambda: ScriptedLlm({
            "Rigatoni": llm_map("pasta"),
            "Penne": llm_map("pasta"),
        })
    )

    # Proviamo a passare ENTRAMBI gli id: il filtro per source deve escludere
    # term_altro dalla query, per cui solo term_gz arriva a decide_terms
    response = await logged_client.post(
        "/api/v1/imports/terms/decide",
        json={"term_ids": [str(term_gz.id), str(term_altro.id)]}
    )
    assert response.status_code == 200
    corpo = response.json()
    # Solo il termine di GIALLOZAFFERANO è stato deciso (term_altro è stato filtrato)
    assert corpo["applied"] == 1
    assert corpo["created"] == 0
    assert corpo["ignored"] == 0
    # still_pending è 0 perché solo 1 termine è arrivato a decide_terms, ed è stato deciso
    assert corpo["still_pending"] == 0
    # remaining_terms conta solo i termini di GIALLOZAFFERANO, quindi è 0
    # (term_altro non è contato perché è di altra source)
    assert corpo["remaining_terms"] == 0

    # Nel database
    await db_session.refresh(term_gz)
    assert term_gz.decision == TermDecision.MAPPED  # questo è stato deciso

    await db_session.refresh(term_altro)
    assert term_altro.decision == TermDecision.PENDING  # questo NO, perché di altra source


async def test_term_ids_e_soggetto_allo_stesso_limite_del_ramo_senza(
    logged_client, db_session, monkeypatch
):
    """`term_ids` accetta fino a 200 id: senza un limite qui, un chiamante che ne
    manda tanti spende altrettante chiamate al modello a pagamento in una sola
    richiesta HTTP. Il ramo «tutti i pendenti» già si ferma a `MAX_TERMS_PER_CALL`;
    questo prova che il ramo per id fa lo stesso, e non uno dei due soli.
    """
    from app.api.imports import MAX_TERMS_PER_CALL

    await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    oltre_il_limite = MAX_TERMS_PER_CALL + 5
    termini = [
        ImportTerm(
            source=GIALLOZAFFERANO, term_key=f"k-{n}", display_name=f"Termine {n}",
            occurrences=1, decision=TermDecision.PENDING,
        )
        for n in range(oltre_il_limite)
    ]
    db_session.add_all(termini)
    await db_session.flush()

    import app.services.recipe_import.decide as modulo

    finto = ScriptedLlm({f"Termine {n}": llm_map("pasta") for n in range(oltre_il_limite)})
    monkeypatch.setattr(modulo, "open_client", lambda: finto)

    response = await logged_client.post(
        "/api/v1/imports/terms/decide",
        json={"term_ids": [str(t.id) for t in termini]},
    )
    assert response.status_code == 200
    corpo = response.json()
    # la chiamata al modello parte solo per i primi MAX_TERMS_PER_CALL, non per tutti
    # quelli passati in term_ids
    assert finto.calls == MAX_TERMS_PER_CALL
    assert corpo["applied"] == MAX_TERMS_PER_CALL
    # i restanti non sono nemmeno arrivati a `decide_terms`: contano ancora in coda
    assert corpo["remaining_terms"] == oltre_il_limite - MAX_TERMS_PER_CALL
