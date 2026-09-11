import httpx
import pytest
import respx

from app.db.models.recipe import EMBEDDING_DIM
from app.services.embeddings import (
    EmbeddingUnavailable,
    FakeEmbeddingProvider,
    HttpEmbeddingProvider,
    LocalEmbeddingProvider,
    get_embedding_provider,
)


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


def test_local_provider_applies_the_e5_prefixes():
    """Ometterli non dà errore, degrada solo la qualità: va vincolato qui."""
    assert LocalEmbeddingProvider._decorate_query("pasta") == "query: pasta"
    assert LocalEmbeddingProvider._decorate_passage("pasta") == "passage: pasta"


async def test_missing_dependency_raises_embedding_unavailable(monkeypatch):
    """Senza sentence-transformers la ricerca deve degradare, non schiantarsi."""
    provider = LocalEmbeddingProvider(model_name="modello-inesistente-xyz")
    monkeypatch.setattr(provider, "_load_model", lambda: (_ for _ in ()).throw(ImportError("no")))
    with pytest.raises(EmbeddingUnavailable):
        await provider.embed_query("pasta")


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
    respx.post("http://embedding-service/embed").mock(
        return_value=httpx.Response(
            200, text="<html>Captive Portal</html>", headers={"content-type": "text/html"}
        )
    )
    provider = HttpEmbeddingProvider(endpoint="http://embedding-service/embed")
    with pytest.raises(EmbeddingUnavailable):
        await provider.embed_query("pasta")
