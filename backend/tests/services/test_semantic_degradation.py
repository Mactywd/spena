"""Il degrado della ricerca semantica deve vedersi: spec §11, «con avviso discreto».

Finora non si vedeva da nessuna parte. `_semantic_ranking` restituiva `[]` e nessuno
ne sapeva niente, la risposta di /recipes/search non aveva un campo per dirlo, e il
seme inghiottiva l'eccezione per ricetta stampando solo i conteggi: un ricettario con
zero vettori era indistinguibile da uno sano. È il moltiplicatore del difetto
dell'immagine (C1) — con l'avviso lo si sarebbe visto al primo uso.

Difeso qui: il log una volta per processo e la rotta che lo schermo Ricette legge,
con tutte e tre le condizioni che la rendono vera (fornitore, soglia valida per il
modello configurato, almeno un vettore nel ricettario), più le due scadenze che
tengono il primo uso fuori dal «resta appeso»: il limite sul calcolo del vettore e il
caricamento del modello che non si mette in coda. Il conteggio del seme sta in
tests/test_seed.py.
"""

import asyncio
import logging

import pytest
import pytest_asyncio

from app.core.config import get_settings
from app.services import embeddings, recipe_search
from app.services.embeddings import EmbeddingUnavailable


@pytest.fixture
def avviso_da_dare(monkeypatch):
    """Riporta il flag a zero: «una volta per processo» vale anche per la suite."""
    monkeypatch.setattr(embeddings, "_degradation_logged", False)


@pytest.fixture
def modello_sbagliato_da_dire(monkeypatch):
    """Lo stesso azzeramento per l'avviso del modello che non c'entra con la soglia."""
    monkeypatch.setattr(recipe_search, "_model_mismatch_logged", False)


@pytest_asyncio.fixture
async def una_ricetta_con_vettore(db_session):
    """Il ricettario ha almeno un vettore: la terza condizione di R4.

    Senza, la rotta non può rispondere `semantic: true` nemmeno con un fornitore
    perfetto, ed è proprio il punto.
    """
    from app.db.models.recipe import EMBEDDING_DIM
    from app.repositories.recipes import create_recipe

    await create_recipe(
        db_session, title="Ricetta con vettore", description=None, instructions="Nulla.",
        servings=None, source="manual", source_ref=None, ingredients=[],
        embedding=[0.1] * EMBEDDING_DIM,
    )
    await db_session.flush()


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


async def test_la_rotta_dichiara_la_ricerca_ibrida_quando_i_vettori_ci_sono(
    logged_client, una_ricetta_con_vettore
):
    """L'altra metà: una rotta che risponde sempre `false` avviserebbe a vuoto."""
    response = await logged_client.get("/api/v1/recipes/search-mode")
    assert response.status_code == 200
    assert response.json() == {"semantic": True}


async def test_la_rotta_dichiara_la_ricerca_testuale_se_nessuna_ricetta_ha_un_vettore(
    logged_client,
):
    """R4: il fornitore funziona, il ricettario non ha vettori, cercare non li usa.

    È il percorso che il README descrive: accendere INSTALL_EMBEDDINGS=1 *dopo* aver
    seminato lascia le 26 ricette del seme con `embedding` a NULL, perché il seme è
    idempotente e non le riscrive. Finché la rotta guardava solo il fornitore,
    l'avviso spariva dallo schermo mentre la metà semantica restava vuota su tutto il
    ricettario: un segnale che promette una ricerca che non c'è.
    """
    assert (await logged_client.get("/api/v1/recipes/search-mode")).json() == {
        "semantic": False
    }


async def test_un_modello_diverso_da_quello_misurato_spegne_la_meta_semantica(
    db_session, monkeypatch, modello_sbagliato_da_dire, caplog
):
    """R3: la soglia vale per il modello su cui è misurata, e per nessun altro.

    Applicarla comunque è una supposizione che sbaglia in silenzio: su una scala più
    larga la graduatoria semantica è sempre vuota mentre /recipes/search-mode dice
    `semantic: true`, perché il vettore si calcola benissimo. Qui si rinuncia, e lo
    si dice — con dentro il nome del modello e le due strade per tornare indietro.
    """
    monkeypatch.setenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-large")
    get_settings.cache_clear()
    try:
        with caplog.at_level(logging.WARNING):
            assert await recipe_search._semantic_ranking(db_session, "pomodoro") == []
    finally:
        get_settings.cache_clear()

    (messaggio,) = [r.getMessage() for r in caplog.records]
    assert "intfloat/multilingual-e5-large" in messaggio
    assert "0.17" in messaggio
    assert "rimisura la soglia" in messaggio


async def test_con_un_modello_diverso_la_rotta_non_promette_la_ricerca_ibrida(
    logged_client, una_ricetta_con_vettore, monkeypatch, modello_sbagliato_da_dire
):
    """L'altra faccia di R3: il segnale deve dire quel che la ricerca fa davvero."""
    monkeypatch.setenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-large")
    get_settings.cache_clear()
    try:
        risposta = await logged_client.get("/api/v1/recipes/search-mode")
    finally:
        get_settings.cache_clear()
    assert risposta.json() == {"semantic": False}


async def test_un_vettore_che_non_arriva_in_tempo_degrada_invece_di_far_aspettare(
    db_session, avviso_da_dare, monkeypatch, caplog
):
    """R6: il primo calcolo scarica il modello, e dietro c'è un Nginx che chiude a 60 s.

    Senza un limite, il solo ingresso nella scheda Ricette resta appeso e finisce in
    «Non sono riuscito a cercare nel ricettario», che è un guasto apparente mentre il
    download procede. Con il limite la risposta arriva subito, testuale.
    """
    async def non_arriva_mai(_: str) -> list[float]:
        await asyncio.sleep(30)
        raise AssertionError("non deve arrivare fin qui")

    monkeypatch.setattr(recipe_search, "_embed_query", non_arriva_mai)
    monkeypatch.setattr(recipe_search, "EMBED_TIMEOUT_SECONDS", 0.05)

    with caplog.at_level(logging.WARNING):
        assert await recipe_search._semantic_ranking(db_session, "pomodoro") == []

    assert "si sta ancora scaricando" in "".join(r.getMessage() for r in caplog.records)


def test_un_secondo_caricamento_non_si_mette_in_coda_dietro_al_download():
    """R6, l'altra metà: chi arriva mentre il modello si scarica degrada subito.

    Con un lucchetto bloccante ogni richiesta successiva terrebbe occupato un thread
    dell'esecutore per tutti i minuti del download. Qui il lucchetto è preso da fuori,
    come lo terrebbe il thread che sta scaricando, e il fornitore risponde invece di
    aspettare. Gira sul codice di produzione: `_load_model` è quello che `_encode`
    chiama dentro `asyncio.to_thread`.
    """
    fornitore = embeddings.LocalEmbeddingProvider("un/modello-che-non-esiste")
    assert embeddings._LOADING.acquire(blocking=False)
    try:
        with pytest.raises(EmbeddingUnavailable, match="in caricamento"):
            fornitore._load_model()
    finally:
        embeddings._LOADING.release()


async def test_la_rotta_del_modo_non_viene_confusa_con_un_id_di_ricetta(logged_client):
    """`/search-mode` prima di `/{recipe_id}`: invertirle darebbe un 422 sull'UUID."""
    assert (await logged_client.get("/api/v1/recipes/search-mode")).status_code == 200


async def test_la_rotta_del_modo_resta_dietro_la_sessione(client):
    assert (await client.get("/api/v1/recipes/search-mode")).status_code == 401
