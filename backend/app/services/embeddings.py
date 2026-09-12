"""Vettori per la ricerca semantica, dietro un'interfaccia sostituibile.

I modelli della famiglia e5 sono addestrati con due prefissi distinti per le
interrogazioni e per i documenti. Ometterli non produce errori: produce
risultati peggiori, che è molto più difficile da notare.
"""

import asyncio
import hashlib
import json
from typing import Protocol

import httpx

from app.core.config import get_settings
from app.db.models.recipe import EMBEDDING_DIM


class EmbeddingUnavailable(Exception):
    """Il fornitore non è utilizzabile. La ricerca degrada al solo testo."""


# I due prefissi vivono qui e solo qui. Erano ricopiati in linea da tre fornitori su
# tre, con un test che ne fissava uno: e il fornitore non difeso era proprio quello
# (HTTP) che si usa quando l'extra `embeddings` resta fuori dall'immagine. Ometterli
# non solleva nessun errore, peggiora solo i risultati.
QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "


def decorate_query(text: str) -> str:
    return f"{QUERY_PREFIX}{text}"


def decorate_passage(text: str) -> str:
    return f"{PASSAGE_PREFIX}{text}"


class EmbeddingProvider(Protocol):
    async def embed_query(self, text: str) -> list[float]: ...

    async def embed_passages(self, texts: list[str]) -> list[list[float]]: ...


class LocalEmbeddingProvider:
    """sentence-transformers dentro il container. Costo per query nullo."""

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or get_settings().embedding_model
        self._model = None

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
        return self._model

    async def _encode(self, texts: list[str]) -> list[list[float]]:
        def run() -> list[list[float]]:
            model = self._load_model()
            return [list(map(float, row)) for row in model.encode(texts, normalize_embeddings=True)]

        try:
            return await asyncio.to_thread(run)
        except Exception as exc:  # modello assente, dipendenza mancante, OOM
            raise EmbeddingUnavailable(str(exc)) from exc

    async def embed_query(self, text: str) -> list[float]:
        return (await self._encode([decorate_query(text)]))[0]

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return await self._encode([decorate_passage(t) for t in texts])


class HttpEmbeddingProvider:
    """Fornitore remoto, per quando si vuole un'immagine leggera."""

    def __init__(self, endpoint: str, timeout: float = 10.0) -> None:
        self._endpoint = endpoint
        self._timeout = timeout

    async def _post(self, inputs: list[str]) -> list[list[float]]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as http:
                response = await http.post(self._endpoint, json={"inputs": inputs})
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EmbeddingUnavailable(str(exc)) from exc
        try:
            return response.json()["embeddings"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise EmbeddingUnavailable(f"Risposta non valida dal fornitore: {exc}") from exc

    async def embed_query(self, text: str) -> list[float]:
        return (await self._post([decorate_query(text)]))[0]

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return await self._post([decorate_passage(t) for t in texts])


class FakeEmbeddingProvider:
    """Deterministico e istantaneo: i test non scaricano 500 MB di modello."""

    def _vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode()).digest()
        # ripete il digest fino a coprire la dimensione richiesta
        raw = digest * (EMBEDDING_DIM // len(digest) + 1)
        values = [b / 255.0 for b in raw[:EMBEDDING_DIM]]
        norm = sum(v * v for v in values) ** 0.5 or 1.0
        return [v / norm for v in values]

    async def embed_query(self, text: str) -> list[float]:
        return self._vector(decorate_query(text))

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(decorate_passage(t)) for t in texts]


def get_embedding_provider() -> EmbeddingProvider:
    backend = get_settings().embedding_backend
    if backend == "fake":
        return FakeEmbeddingProvider()
    if backend == "http":
        return HttpEmbeddingProvider(endpoint=get_settings().embedding_endpoint)
    return LocalEmbeddingProvider()
