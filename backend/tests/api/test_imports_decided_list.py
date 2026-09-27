"""L'elenco «Decisioni recenti»: cosa è stato deciso, in una riga per termine.

Un termine accorpato non ha niente di speciale: è un `map`, e si mostra come un `map`,
perché è quello che è. Nessuna colonna nuova in tutta la feature.
"""

from datetime import UTC, datetime

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.repositories.ingredients import create_ingredient


async def test_lelenco_predefinito_resta_quello_dei_termini_in_coda(logged_client, db_session):
    """Il contratto di oggi non cambia: la coda manuale è la stessa di prima."""
    db_session.add(
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-boh", display_name="Boh",
            occurrences=1, decision=TermDecision.PENDING,
        )
    )
    await db_session.flush()

    response = await logged_client.get("/api/v1/imports/terms")
    assert response.status_code == 200
    nomi = [t["display_name"] for t in response.json()]
    assert nomi == ["Boh"]


async def test_decided_by_ai_torna_solo_le_decisioni_dellai(logged_client, db_session):
    pasta = await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    db_session.add_all([
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-rigatoni", display_name="Rigatoni",
            occurrences=3, decision=TermDecision.MAPPED, ingredient_id=pasta.id,
            decided_by="ai",
        ),
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-penne", display_name="Penne",
            occurrences=2, decision=TermDecision.MAPPED, ingredient_id=pasta.id,
            decided_by="human",
        ),
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-farfalle", display_name="Farfalle",
            occurrences=1, decision=TermDecision.MAPPED, ingredient_id=pasta.id,
            decided_by="auto",
        ),
    ])
    await db_session.flush()

    response = await logged_client.get("/api/v1/imports/terms?decided_by=ai")
    assert response.status_code == 200
    voci = response.json()
    assert [v["display_name"] for v in voci] == ["Rigatoni"]
    assert voci[0]["decided_action"] == "map"
    assert voci[0]["decided_name"] == "pasta"
    assert voci[0]["decided_by"] == "ai"


async def test_un_termine_ignorato_si_riconosce_dallazione(logged_client, db_session):
    db_session.add(
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-acqua", display_name="Acqua",
            occurrences=2, decision=TermDecision.IGNORED, ingredient_id=None,
            decided_by="ai",
        )
    )
    await db_session.flush()

    voci = (await logged_client.get("/api/v1/imports/terms?decided_by=ai")).json()
    assert voci[0]["decided_action"] == "ignored"
    assert voci[0]["decided_name"] is None


async def test_un_decided_by_sconosciuto_e_un_422_non_un_elenco_vuoto(logged_client):
    """Un filtro scritto male che risponde «niente» è indistinguibile da «niente c'è»."""
    response = await logged_client.get("/api/v1/imports/terms?decided_by=nessuno")
    assert response.status_code == 422


async def test_decided_by_human_torna_le_decisioni_a_mano_con_la_loro_data(
    logged_client, db_session
):
    """R11: l'elenco delle decisioni recenti mette insieme AI e mano, e le ordina per
    data. La data deve quindi viaggiare nella risposta: senza, la schermata non ha
    niente su cui fondere i due elenchi."""
    pasta = await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    prima = datetime(2026, 9, 20, 10, 0, tzinfo=UTC)
    dopo = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)
    db_session.add_all([
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-penne", display_name="Penne",
            occurrences=2, decision=TermDecision.MAPPED, ingredient_id=pasta.id,
            decided_by="human", decided_at=prima,
        ),
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-sedani", display_name="Sedani",
            occurrences=1, decision=TermDecision.MAPPED, ingredient_id=pasta.id,
            decided_by="human", decided_at=dopo,
        ),
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-rigatoni", display_name="Rigatoni",
            occurrences=3, decision=TermDecision.MAPPED, ingredient_id=pasta.id,
            decided_by="ai", decided_at=dopo,
        ),
    ])
    await db_session.flush()

    response = await logged_client.get("/api/v1/imports/terms?decided_by=human")
    assert response.status_code == 200
    voci = response.json()
    assert [v["display_name"] for v in voci] == ["Sedani", "Penne"]
    assert all(v["decided_by"] == "human" for v in voci)
    assert datetime.fromisoformat(voci[0]["decided_at"]) == dopo
    assert datetime.fromisoformat(voci[1]["decided_at"]) == prima


async def test_la_coda_da_decidere_non_ha_data_di_decisione(logged_client, db_session):
    db_session.add(
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-boh", display_name="Boh",
            occurrences=1, decision=TermDecision.PENDING,
        )
    )
    await db_session.flush()

    voci = (await logged_client.get("/api/v1/imports/terms")).json()
    assert voci[0]["decided_at"] is None
