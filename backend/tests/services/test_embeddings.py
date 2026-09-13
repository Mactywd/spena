import json

import httpx
import pytest
import respx

from app.db.models.recipe import EMBEDDING_DIM
from app.services.embeddings import (
    EmbeddingUnavailable,
    FakeEmbeddingProvider,
    HttpEmbeddingProvider,
    LocalEmbeddingProvider,
    decorate_passage,
    decorate_query,
    get_embedding_provider,
    recipe_document,
)

ENDPOINT = "http://embedding-service/embed"


async def test_fake_provider_returns_vectors_of_the_right_size():
    provider = FakeEmbeddingProvider()
    vector = await provider.embed_query("pasta al pomodoro")
    assert len(vector) == EMBEDDING_DIM


async def test_fake_provider_is_deterministic():
    provider = FakeEmbeddingProvider()
    assert await provider.embed_query("pasta") == await provider.embed_query("pasta")
    assert await provider.embed_query("pasta") != await provider.embed_query("riso")


async def test_fake_provider_embeds_many_passages():
    vectors = await FakeEmbeddingProvider().embed_passages(["pasta", "riso", "pane"])
    assert len(vectors) == 3
    assert all(len(v) == EMBEDDING_DIM for v in vectors)


def test_i_prefissi_e5_sono_quelli_che_il_modello_si_aspetta():
    """Ometterli non dà errore, degrada solo la qualità: va vincolato qui.

    Ora c'è una copia sola (app/services/embeddings.py) e la fissa questo test; i tre
    test che seguono verificano che ciascun fornitore la usi davvero, perché un
    fornitore che riscrivesse le stringhe in linea passerebbe comunque da qui.
    """
    assert decorate_query("pasta") == "query: pasta"
    assert decorate_passage("pasta") == "passage: pasta"


async def test_il_fornitore_locale_consegna_al_modello_il_testo_con_i_prefissi(monkeypatch):
    class ModelloFinto:
        def __init__(self) -> None:
            self.visti: list[str] = []

        def encode(self, texts, normalize_embeddings=True):
            self.visti.extend(texts)
            return [[0.0] * EMBEDDING_DIM for _ in texts]

    provider = LocalEmbeddingProvider(model_name="modello-finto")
    modello = ModelloFinto()
    monkeypatch.setattr(provider, "_load_model", lambda: modello)

    await provider.embed_query("pasta")
    await provider.embed_passages(["riso", "pane"])
    assert modello.visti == ["query: pasta", "passage: riso", "passage: pane"]


@respx.mock
async def test_il_fornitore_http_manda_i_prefissi_nel_corpo():
    """È il fornitore che si usa quando l'extra locale resta fuori dall'immagine.

    Era la copia non difesa delle tre, cioè quella che sarebbe finita in produzione.
    """
    rotta = respx.post(ENDPOINT).mock(
        return_value=httpx.Response(200, json={"embeddings": [[0.0] * EMBEDDING_DIM]})
    )
    provider = HttpEmbeddingProvider(endpoint=ENDPOINT)

    await provider.embed_query("pasta")
    assert json.loads(rotta.calls.last.request.content)["inputs"] == ["query: pasta"]

    await provider.embed_passages(["riso"])
    assert json.loads(rotta.calls.last.request.content)["inputs"] == ["passage: riso"]


async def test_il_fornitore_finto_distingue_interrogazione_e_documento():
    """Senza i prefissi i due vettori sarebbero identici e la differenza invisibile."""
    provider = FakeEmbeddingProvider()
    assert await provider.embed_query("pasta") != (await provider.embed_passages(["pasta"]))[0]


async def test_missing_dependency_raises_embedding_unavailable(monkeypatch):
    """Senza sentence-transformers la ricerca deve degradare, non schiantarsi."""
    provider = LocalEmbeddingProvider(model_name="modello-inesistente-xyz")
    monkeypatch.setattr(provider, "_load_model", lambda: (_ for _ in ()).throw(ImportError("no")))
    with pytest.raises(EmbeddingUnavailable):
        await provider.embed_query("pasta")


def test_recipe_document_unisce_titolo_e_descrizione():
    """Era ricopiato in linea in quattro punti; ora lo fissa un test solo."""
    assert recipe_document("Pasta al pomodoro", "Un classico") == (
        "Pasta al pomodoro. Un classico"
    )


def test_recipe_document_senza_descrizione_non_scrive_none():
    """`None` diventa stringa vuota, non la parola "None" nel testo per il modello."""
    assert recipe_document("Pasta al pomodoro", None) == "Pasta al pomodoro. "


def test_factory_honours_the_configured_backend(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("EMBEDDING_BACKEND", "fake")
    assert isinstance(get_embedding_provider(), FakeEmbeddingProvider)
    get_settings.cache_clear()
    monkeypatch.setenv("EMBEDDING_BACKEND", "local")
    assert isinstance(get_embedding_provider(), LocalEmbeddingProvider)
    get_settings.cache_clear()


@respx.mock
async def test_malformed_json_body_raises_embedding_unavailable():
    """Un 200 con body non-JSON è quello che torna da un captive portal o da un proxy
    configurato male. Deve degradare, mai diventare errore."""
    respx.post(ENDPOINT).mock(
        return_value=httpx.Response(
            200, text="<html>Captive Portal</html>", headers={"content-type": "text/html"}
        )
    )
    provider = HttpEmbeddingProvider(endpoint=ENDPOINT)
    with pytest.raises(EmbeddingUnavailable):
        await provider.embed_query("pasta")


async def test_il_modello_locale_si_carica_una_volta_per_processo(monkeypatch):
    """`get_embedding_provider()` restituisce un fornitore nuovo a ogni chiamata.

    Senza una cache condivisa, ogni ricerca e ogni ricetta salvata ricostruirebbero
    SentenceTransformer, cioè rileggerebbero da disco mezzo gigabyte di modello. Il
    test finge il pacchetto invece di installarlo: conta le costruzioni, che è ciò
    che si vuole vincolare.
    """
    import sys
    import types

    from app.services import embeddings

    costruzioni: list[str] = []

    class SentenceTransformerFinto:
        def __init__(self, nome: str) -> None:
            costruzioni.append(nome)

        def encode(self, texts, normalize_embeddings=True):
            return [[0.0] * EMBEDDING_DIM for _ in texts]

    modulo = types.ModuleType("sentence_transformers")
    modulo.SentenceTransformer = SentenceTransformerFinto
    monkeypatch.setitem(sys.modules, "sentence_transformers", modulo)
    monkeypatch.setattr(embeddings, "_LOADED_MODELS", {})

    await LocalEmbeddingProvider(model_name="modello-finto").embed_query("pasta")
    await LocalEmbeddingProvider(model_name="modello-finto").embed_query("riso")
    assert costruzioni == ["modello-finto"]
