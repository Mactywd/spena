"""L'immagine deve contenere ciò che le funzionalità richiedono, senza extra sulla strada.

La storia che questo file ricorda: `anthropic` era un extra (`.[ai]`), il Dockerfile
faceva `pip install -e .`, e nell'unico deploy del progetto il pacchetto non esisteva —
quindi la stesura AI rispondeva «pacchetto non installato» con qualunque chiave. Nessun
test poteva accorgersene, perché tutti iniettavano un client finto e l'unico che
arrivava alla costruzione vera usciva sulla chiave assente, prima dell'import.

Da OpenRouter quel difetto è strutturalmente impossibile: il client parla HTTP con
`httpx`, che è una **dipendenza di base**. Quel che resta da difendere è che rimanga
tale, e che `anthropic` non rientri.

La seconda metà di questo file prova la costruzione della richiesta vera. È l'erede del
test che eseguiva `import anthropic`: la lezione di CLAUDE.md — un percorso che nessun
test attraversa è un percorso rotto che nessuno vede — vale per la richiesta esattamente
come valeva per l'import.
"""

import json
import re
import tomllib
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


def test_httpx_e_una_dipendenza_di_base_e_non_un_extra():
    """Il client del modello ci gira sopra: messo fra gli extra ripeterebbe la storia
    di `anthropic`, e ogni chiamata all'LLM morirebbe su ImportError in produzione."""
    progetto = tomllib.loads(PYPROJECT.read_text())["project"]
    assert any("httpx" in dep for dep in progetto["dependencies"]), (
        f"{PYPROJECT}: httpx non è fra le dipendenze di base ({progetto['dependencies']!r}): "
        "il client di OpenRouter non parte."
    )


def test_anthropic_non_e_piu_una_dipendenza_di_nessun_tipo():
    contenuto = PYPROJECT.read_text()
    assert "anthropic" not in contenuto, (
        f"{PYPROJECT}: `anthropic` è tornata. Il fornitore è OpenRouter, e un secondo "
        "client che nessuno esercita è il difetto in cima a CLAUDE.md."
    )
    extra = tomllib.loads(contenuto)["project"].get("optional-dependencies", {})
    assert "ai" not in extra, f"{PYPROJECT}: l'extra `ai` è tornato ({extra.keys()!r})"


def test_il_dockerfile_non_installa_nessun_extra_ai():
    contenuto = righe_unite(DOCKERFILE.read_text())
    installazioni = [r for r in contenuto.splitlines() if "pip install" in r]
    assert installazioni, f"{DOCKERFILE}: nessun `pip install`, questo test cerca male"
    assert not any("[ai" in r for r in installazioni), (
        f"{DOCKERFILE}: installa ancora un extra `ai` ({installazioni!r}), che non esiste più"
    )


def test_lextra_embeddings_resta_opzionale_e_spento_per_default():
    """torch pesa GB: si accende da `.env`, e da un posto solo.

    Difeso in entrambe le direzioni — che l'interruttore esista e che il default sia
    spento — perché un'immagine che si porta torch dietro a sorpresa è l'altro modo di
    sbagliare.
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
            f"{nome_file}: il servizio backend non passa INSTALL_EMBEDDINGS come argomento "
            f"di build (trovato {servizio.get('build')!r}). Senza, il valore scritto in "
            "`.env` non arriva all'immagine e l'interruttore non esiste."
        )


def test_beautifulsoup_e_una_dipendenza_di_base_e_non_un_extra():
    """Il parser dell'import non è una funzione opzionale."""
    progetto = tomllib.loads(PYPROJECT.read_text())["project"]
    assert any("beautifulsoup4" in dep for dep in progetto["dependencies"]), (
        f"{PYPROJECT}: beautifulsoup4 non è fra le dipendenze di base "
        f"({progetto['dependencies']!r}): il parser dell'import non parte."
    )


async def test_la_richiesta_vera_si_costruisce_per_intero(monkeypatch):
    """L'erede del test che eseguiva `import anthropic`: nessun finto, nessuna rete.

    Costruisce il corpo e gli header che `complete_json` manderebbe, chiamando le
    funzioni vere. È l'unico test che attraversa `build_headers` e
    `build_provider_preferences` insieme al corpo, ed è il posto in cui un errore di
    battitura su `X-Title` o su `require_parameters` si vede.
    """
    import httpx
    import respx

    from app.core.config import get_settings
    from app.services.llm import build_headers, build_provider_preferences, complete_json

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta-per-il-test")
    monkeypatch.setenv("OPENROUTER_APP_URL", "https://esempio.invalid")
    try:
        assert build_headers()["X-Title"] == "Spena Import Ricette"
        assert build_provider_preferences() == {"sort": "price", "require_parameters": True}

        async with respx.mock:
            route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
                return_value=httpx.Response(
                    200, json={"choices": [{"message": {"content": '{"ok": true}'}}]}
                )
            )
            await complete_json(
                system="s", user="u",
                schema={
                    "type": "object", "properties": {"ok": {"type": "boolean"}},
                    "required": ["ok"], "additionalProperties": False,
                },
                schema_name="prova", max_tokens=10,
            )
        corpo = json.loads(route.calls.last.request.content)
        assert corpo["model"] == "google/gemma-4-26b-a4b-it"
        assert corpo["response_format"]["json_schema"]["strict"] is True
    finally:
        get_settings.cache_clear()
