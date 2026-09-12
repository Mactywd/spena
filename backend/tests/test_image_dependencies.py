"""L'immagine deve installare ciò che le funzionalità della v1 richiedono.

Il difetto che questi test difendono è rimasto nascosto per tutto il branch, e vale
la pena scrivere perché. `backend/Dockerfile` faceva `pip install -e .`, che non
installa nessun extra: nell'unico deploy che questo progetto ha, `anthropic` non
esisteva, quindi lo schermo della stesura AI rispondeva «pacchetto anthropic non
installato» con qualunque chiave configurata. Nessun test della suite poteva
accorgersene, perché tutti i test di tests/services/test_ai_recipes.py iniettano un
client finto e l'unico che arriva a `_build_client` esce sulla chiave assente, prima
dell'`import anthropic`. L'istruzione di import non era eseguita da nessun test.

I tre test qui coprono due cose diverse, e nessuno dei due copre l'altra:

- la prima metà è un'asserzione sui file di build (Dockerfile e Compose), nello stile
  di tests/test_compose.py. È quella che ferma la regressione: gira sempre, anche
  dove gli extra non sono installati, e fallisce se qualcuno torna a `pip install -e .`.
- la seconda esegue davvero l'import e costruisce il client vero, cioè l'unico
  percorso che nessun test toccava. Si salta dove `anthropic` non c'è, perché il
  virtualenv dello sviluppatore può legittimamente non averlo (`pip install -e
  ".[dev]"`); il README installa `".[dev,ai]"` proprio per farlo girare.

Quello che nessun test di questa suite può dimostrare è che l'immagine *costruita*
contenga il pacchetto: la suite non gira dentro al container. Quella verifica è a
mano, e sta nel rapporto — `docker run --rm <immagine> python -c "import anthropic"`
più una chiamata vera a POST /api/v1/recipes/ai-draft nello stack e2e.
"""

import re
import tomllib
from importlib.util import find_spec
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "backend" / "Dockerfile"
PYPROJECT = REPO_ROOT / "backend" / "pyproject.toml"
COMPOSE_FILES = ("docker-compose.yml", "docker-compose.prod.yml")


def righe_unite(testo: str) -> str:
    """Il Dockerfile spezza il RUN su più righe: le continuazioni vanno ricucite."""
    return re.sub(r"\\\s*\n\s*", " ", testo)


def test_limmagine_installa_lextra_ai():
    contenuto = righe_unite(DOCKERFILE.read_text())
    installazioni = [r for r in contenuto.splitlines() if "pip install" in r]
    assert installazioni, f"{DOCKERFILE}: nessun `pip install`, questo test cerca male"

    assert any(".[ai]" in r or '".[ai]"' in r or "[ai," in r for r in installazioni), (
        f"{DOCKERFILE}: il pacchetto viene installato senza l'extra `ai`.\n"
        f"Trovato: {installazioni!r}\n"
        "`pip install -e .` non installa nessun extra: senza `ai` il pacchetto "
        "anthropic non esiste nell'immagine e POST /api/v1/recipes/ai-draft risponde "
        "sempre 503 «pacchetto anthropic non installato», con qualunque chiave."
    )


def test_lextra_ai_e_quello_che_porta_anthropic():
    """Le due metà devono restare d'accordo: l'extra giusto, col pacchetto giusto."""
    extra = tomllib.loads(PYPROJECT.read_text())["project"]["optional-dependencies"]
    assert any("anthropic" in dep for dep in extra["ai"]), (
        f"{PYPROJECT}: l'extra `ai` non dichiara anthropic ({extra['ai']!r}), "
        "quindi installarlo dal Dockerfile non servirebbe a niente"
    )


def test_lextra_embeddings_resta_opzionale_e_spento_per_default():
    """torch pesa GB: si accende da `.env`, e da un posto solo.

    Questo test difende la decisione in entrambe le direzioni — che l'interruttore
    esista e che il default sia spento — perché un'immagine che si porta torch dietro
    a sorpresa è l'altro modo di sbagliare.
    """
    contenuto = righe_unite(DOCKERFILE.read_text())
    assert "ARG INSTALL_EMBEDDINGS=0" in contenuto, (
        f"{DOCKERFILE}: manca `ARG INSTALL_EMBEDDINGS=0`, cioè l'interruttore "
        "dell'extra `embeddings` o il suo default spento"
    )
    assert "[embeddings]" in contenuto, (
        f"{DOCKERFILE}: nessun ramo installa l'extra `embeddings`, quindi "
        "INSTALL_EMBEDDINGS=1 non accenderebbe niente"
    )

    for nome_file in COMPOSE_FILES:
        servizio = yaml.safe_load((REPO_ROOT / nome_file).read_text())["services"]["backend"]
        args = servizio.get("build", {}).get("args", {})
        assert "INSTALL_EMBEDDINGS" in args, (
            f"{nome_file}: il servizio backend non passa INSTALL_EMBEDDINGS come "
            f"argomento di build (trovato {servizio.get('build')!r}). Senza, il valore "
            "scritto in `.env` non arriva all'immagine e l'interruttore non esiste."
        )


@pytest.mark.skipif(
    find_spec("anthropic") is None,
    reason="anthropic non installato: `pip install -e \".[dev,ai]\"` per far girare "
    "questo test, che è l'unico a eseguire l'import vero",
)
async def test_con_il_pacchetto_installato_il_client_vero_si_costruisce(monkeypatch):
    """L'unico test che esegue `import anthropic` dentro `_build_client`.

    Nessuna chiamata di rete: costruire `AsyncAnthropic` non parla con nessuno, e la
    chiave è finta di proposito. Ciò che si dimostra è che con una chiave configurata
    il percorso non finisce più in AiUnavailable per dipendenza mancante.
    """
    from app.core.config import get_settings
    from app.services.ai_recipes import AiUnavailable, _build_client

    get_settings.cache_clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chiave-finta-per-il-test")
    try:
        try:
            client = _build_client()
        except AiUnavailable as exc:  # pragma: no cover - è il difetto, non il caso sano
            pytest.fail(f"con anthropic installato _build_client non deve fallire: {exc}")
        assert type(client).__name__ == "AsyncAnthropic"
    finally:
        get_settings.cache_clear()
