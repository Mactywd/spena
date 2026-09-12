"""Il degrado della ricerca semantica deve vedersi: spec §11, «con avviso discreto».

Finora non si vedeva da nessuna parte. `_semantic_ranking` restituiva `[]` e nessuno
ne sapeva niente, la risposta di /recipes/search non aveva un campo per dirlo, e il
seme inghiottiva l'eccezione per ricetta stampando solo i conteggi: un ricettario con
zero vettori era indistinguibile da uno sano. È il moltiplicatore del difetto
dell'immagine (C1) — con l'avviso lo si sarebbe visto al primo uso.

Tre cose difese qui: il log una volta per processo, la rotta che lo schermo Ricette
può leggere, e il conteggio del seme (quello sta in tests/test_seed.py).
"""

import logging

import pytest

from app.services import embeddings, recipe_search
from app.services.embeddings import EmbeddingUnavailable


@pytest.fixture
def avviso_da_dare(monkeypatch):
    """Riporta il flag a zero: «una volta per processo» vale anche per la suite."""
    monkeypatch.setattr(embeddings, "_degradation_logged", False)


@pytest.fixture
def embedding_rotto(monkeypatch):
    async def esplode(_: str) -> list[float]:
        raise EmbeddingUnavailable("sentence-transformers non installato")

    monkeypatch.setattr(recipe_search, "_embed_query", esplode)


async def test_il_primo_degrado_lo_dice_nei_log(
    db_session, avviso_da_dare, embedding_rotto, caplog
):
    with caplog.at_level(logging.WARNING):
        assert await recipe_search._semantic_ranking(db_session, "pomodoro") == []

    messaggi = [r.getMessage() for r in caplog.records]
    assert len(messaggi) == 1, f"atteso un avviso solo, trovati {messaggi!r}"
    # nomina la causa e dice come rimediare: è l'unica riga che chi fa il deploy legge
    assert "sentence-transformers non installato" in messaggi[0]
    assert "INSTALL_EMBEDDINGS=1" in messaggi[0]


async def test_il_secondo_degrado_non_ripete_lavviso(
    db_session, avviso_da_dare, embedding_rotto, caplog
):
    """Un avviso per ricerca sarebbe rumore, e il rumore non lo legge nessuno."""
    with caplog.at_level(logging.WARNING):
        await recipe_search._semantic_ranking(db_session, "pomodoro")
        await recipe_search._semantic_ranking(db_session, "pasta")
        await recipe_search._semantic_ranking(db_session, "riso")

    assert len([r for r in caplog.records if "ricerca semantica" in r.getMessage()]) == 1


async def test_la_rotta_dichiara_la_ricerca_testuale_quando_i_vettori_non_ci_sono(
    logged_client, avviso_da_dare, embedding_rotto
):
    response = await logged_client.get("/api/v1/recipes/search-mode")
    assert response.status_code == 200
    assert response.json() == {"semantic": False}


async def test_la_rotta_dichiara_la_ricerca_ibrida_quando_i_vettori_ci_sono(logged_client):
    """L'altra metà: una rotta che risponde sempre `false` avviserebbe a vuoto."""
    response = await logged_client.get("/api/v1/recipes/search-mode")
    assert response.status_code == 200
    assert response.json() == {"semantic": True}


async def test_la_rotta_del_modo_non_viene_confusa_con_un_id_di_ricetta(logged_client):
    """`/search-mode` prima di `/{recipe_id}`: invertirle darebbe un 422 sull'UUID."""
    assert (await logged_client.get("/api/v1/recipes/search-mode")).status_code == 200


async def test_la_rotta_del_modo_resta_dietro_la_sessione(client):
    assert (await client.get("/api/v1/recipes/search-mode")).status_code == 401
