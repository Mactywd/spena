"""L'immagine deve contenere ciò che le funzionalità richiedono, senza extra sulla strada.

La storia che questo file ricorda: `anthropic` era un extra (`.[ai]`), il Dockerfile
faceva `pip install -e .`, e nell'unico deploy del progetto il pacchetto non esisteva —
quindi la stesura AI rispondeva «pacchetto non installato» con qualunque chiave. Nessun
test poteva accorgersene, perché tutti iniettavano un client finto e l'unico che
arrivava alla costruzione vera usciva sulla chiave assente, prima dell'import.

Poi l'LLM passò da OpenRouter, via `httpx`, e `anthropic` uscì del tutto. Ora è tornato,
perché l'import parla con Claude Haiku attraverso l'API Messages: ma il contrario della
prima volta, come **dipendenza di base fissata con `==`**, mai un extra. È quello che
questo file difende, insieme a `httpx`, che resta di base per Open Food Facts e per lo
scarico delle ricette.

I finti della suite sono il client vero dell'SDK con il trasporto HTTP sostituito
(`tests/llm_fakes.py`): ogni test dell'AI importa `anthropic` e costruisce il client con
le opzioni di produzione, quindi un SDK mancante farebbe cadere la suite, non solo
l'immagine. Questo file resta sulla superficie di dipendenza dell'immagine.
"""

import re
import tomllib
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPO_ROOT / "backend" / "Dockerfile"
PYPROJECT = REPO_ROOT / "backend" / "pyproject.toml"
COMPOSE_FILES = ("docker-compose.yml", "docker-compose.prod.yml")


def righe_unite(testo: str) -> str:
    """Il Dockerfile spezza il RUN su più righe: le continuazioni vanno ricucite."""
    return re.sub(r"\\\s*\n\s*", " ", testo)


def test_httpx_e_una_dipendenza_di_base_e_non_un_extra():
    """Open Food Facts e lo scarico di GialloZafferano ci girano sopra: messo fra gli
    extra ripeterebbe la storia di `anthropic`, e morirebbero su ImportError in
    produzione."""
    progetto = tomllib.loads(PYPROJECT.read_text())["project"]
    assert any("httpx" in dep for dep in progetto["dependencies"]), (
        f"{PYPROJECT}: httpx non è fra le dipendenze di base ({progetto['dependencies']!r}): "
        "Open Food Facts e lo scarico delle ricette non partono."
    )


def test_anthropic_e_una_dipendenza_di_base_fissata():
    """Il client dell'LLM dell'import: di base, perché da extra mancò dall'immagine, e
    fissato, perché una ricostruzione non cambi l'SDK senza che nessuno lo decida."""
    progetto = tomllib.loads(PYPROJECT.read_text())["project"]
    assert any(dep.startswith("anthropic==") for dep in progetto["dependencies"]), (
        f"{PYPROJECT}: manca `anthropic==…` fra le dipendenze di base "
        f"({progetto['dependencies']!r}): l'LLM dell'import non parte."
    )
    extra = progetto.get("optional-dependencies", {})
    for nome, voci in extra.items():
        assert not any("anthropic" in voce for voce in voci), (
            f"{PYPROJECT}: l'extra `{nome}` nomina `anthropic` ({voci!r}): sta fra le "
            "dipendenze di base, e solo lì."
        )
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


def test_claude_agent_sdk_e_una_dipendenza_di_base_fissata():
    """Il binario di Claude Code segue la versione del pacchetto: con un `>=` ogni
    ricostruzione dell'immagine cambierebbe Claude Code senza che nessuno lo decida."""
    progetto = tomllib.loads(PYPROJECT.read_text())["project"]
    assert "claude-agent-sdk==0.2.180" in progetto["dependencies"], (
        f"{PYPROJECT}: manca `claude-agent-sdk==0.2.180` fra le dipendenze di base "
        f"({progetto['dependencies']!r})"
    )


def test_il_dockerfile_non_installa_node():
    """L'SDK porta il binario da sé: Node nell'immagine sarebbe peso senza ragione."""
    for riga in DOCKERFILE.read_text().splitlines():
        for parola in ("nodejs", "npm", "@anthropic-ai"):
            assert parola not in riga, f"{DOCKERFILE}: la riga {riga!r} nomina {parola}"
