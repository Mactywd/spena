"""Vettori per la ricerca semantica, dietro un'interfaccia sostituibile.

I modelli della famiglia e5 sono addestrati con due prefissi distinti per le
interrogazioni e per i documenti. Ometterli non produce errori: produce
risultati peggiori, che è molto più difficile da notare.
"""

import asyncio
import hashlib
import json
import logging
import threading
from typing import Protocol

import httpx

from app.core.config import get_settings
from app.db.models.recipe import EMBEDDING_DIM

logger = logging.getLogger(__name__)


class EmbeddingUnavailable(Exception):
    """Il fornitore non è utilizzabile. La ricerca degrada al solo testo."""


# La spec §11 chiede che il degrado si veda («con avviso discreto») e finora non si
# vedeva da nessuna parte: il ricettario senza vettori è indistinguibile da uno sano,
# ed è questo che ha lasciato passare per tutto il branch un'immagine che non
# installava sentence-transformers. Il messaggio nomina la causa e dice come
# rimediare, perché è l'unica riga che chi fa il deploy leggerà.
SEMANTIC_OFF_HOWTO = (
    "ricerca semantica non disponibile (%s): il ricettario resta sulla sola ricerca "
    "testuale. È la degradazione prevista dalla spec §11, non un guasto. Per "
    "accenderla: INSTALL_EMBEDDINGS=1 in .env e `docker compose up -d --build`."
)

# Una volta per processo e non a ogni tentativo: un avviso per ricerca diventerebbe
# rumore, e il rumore non lo legge nessuno.
_degradation_logged = False


def log_degradation_once(reason: object) -> None:
    """Da chiamare in ogni punto che inghiotte EmbeddingUnavailable per degradare."""
    global _degradation_logged
    if _degradation_logged:
        return
    _degradation_logged = True
    logger.warning(SEMANTIC_OFF_HOWTO, reason)


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


# Lo stesso letterale `f"{title}. {description or ''}"` era ricopiato in linea in
# app/api/recipes.py, app/cli/seed.py, app/services/recipe_import/materialize.py e
# app/cli/reindex.py: quattro copie di una sola regola, con il rischio che una
# modifica futura (per esempio includere gli ingredienti nel testo) ne aggiorni tre
# e dimentichi la quarta. Vive qui perché questo modulo possiede già tutto ciò che il
# modello vede, prefissi compresi. Il corpo non cambia il testo prodotto finora: un
# testo diverso invaliderebbe in silenzio ogni vettore già salvato.
def recipe_document(title: str, description: str | None) -> str:
    """Il testo che una ricetta presenta al modello: titolo, punto, descrizione."""
    return f"{title}. {description or ''}"


class EmbeddingProvider(Protocol):
    async def embed_query(self, text: str) -> list[float]: ...

    async def embed_passages(self, texts: list[str]) -> list[list[float]]: ...


# Il modello caricato vive quanto il processo, indicizzato per nome. Non è una cache
# opportunistica: `get_embedding_provider()` costruisce un fornitore nuovo a ogni
# chiamata e `_model` è un attributo di istanza, quindi senza questo dizionario
# SentenceTransformer veniva ricostruito — e il modello riletto da disco — a ogni
# ricerca e a ogni ricetta salvata.
_LOADED_MODELS: dict[str, object] = {}

# Un solo caricamento alla volta, e chi arriva secondo non si mette in coda: degrada.
#
# Il primo caricamento scarica il modello (~500 MB) e dura minuti. Senza questo
# lucchetto due richieste vicine — il preriscaldamento all'ingresso nella scheda
# Ricette e la prima ricerca — ne fanno partire due in parallelo, ognuna con il suo
# download. Con un lucchetto bloccante, invece, ogni richiesta successiva terrebbe
# occupato un thread dell'esecutore per tutta la durata del download, e l'esecutore ha
# un numero di thread finito che serve anche ad altro. `blocking=False` è quindi la
# forma giusta: uno scarica, gli altri rispondono subito con la degradazione prevista
# dalla spec §11 e riprovano alla richiesta dopo.
_LOADING = threading.Lock()


class LocalEmbeddingProvider:
    """sentence-transformers dentro il container. Costo per query nullo."""

    def __init__(self, model_name: str | None = None) -> None:
        self._model_name = model_name or get_settings().embedding_model
        self._model = None

    def _load_model(self):
        if self._model is None:
            model = _LOADED_MODELS.get(self._model_name)
            if model is None:
                if not _LOADING.acquire(blocking=False):
                    raise EmbeddingUnavailable(
                        f"il modello {self._model_name} è in caricamento (al primo uso "
                        "viene scaricato): fino ad allora la ricerca resta testuale"
                    )
                try:
                    from sentence_transformers import SentenceTransformer

                    model = SentenceTransformer(self._model_name)
                    _LOADED_MODELS[self._model_name] = model
                finally:
                    _LOADING.release()
            self._model = model
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
    """Deterministico e istantaneo: i test non scaricano 500 MB di modello.

    Le distanze che produce sono riproducibili ma arbitrarie rispetto al contenuto —
    misurato sui passaggi del seme, 0,16–0,37 fra qualunque coppia, senza relazione
    con la pertinenza. Quindi non serve a calibrare né a provare
    SEMANTIC_MAX_DISTANCE: la soglia si prova con vettori espliciti, dove la distanza
    è aritmetica a vista (tests/api/test_recipes.py).
    """

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
