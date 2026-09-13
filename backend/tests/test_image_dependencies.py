"""L'immagine deve installare ciò che le funzionalità della v1 richiedono.

Il difetto che questi test difendono è rimasto nascosto per tutto il branch, e vale
la pena scrivere perché. `backend/Dockerfile` faceva `pip install -e .`, che non
installa nessun extra: nell'unico deploy che questo progetto ha, `anthropic` non
esisteva, quindi lo schermo della stesura AI rispondeva «pacchetto anthropic non
installato» con qualunque chiave configurata. Nessun test della suite poteva
accorgersene, perché tutti i test di tests/services/test_ai_recipes.py iniettano un
client finto e l'unico che arriva a `_build_client` esce sulla chiave assente, prima
dell'`import anthropic`. L'istruzione di import non era eseguita da nessun test.

I test qui sono asserzioni sui file di build (Dockerfile e Compose), nello stile
di tests/test_compose.py. Girano sempre, anche dove gli extra non sono installati, e
falliscono se qualcuno torna a `pip install -e .`.

Task 13 ha ritirato il ponte Anthropic (`_build_client`, `AiUnavailable`): la stesura
AI adesso usa OpenRouter via `httpx`, che è una dipendenza di base. Il vecchio test
che eseguiva `_build_client()` non ha più un soggetto e se ne è andato con lui. La
garanzia che `test_limmagine_installa_lextra_ai` continua a offrire non è più
specifica per la stesura AI, ma per le funzionalità che vivono in quell'extra in
generale.

Quello che nessun test di questa suite può dimostrare è che l'immagine *costruita*
contenga i pacchetti degli extra: la suite non gira dentro al container. Quella
verifica è a mano, e sta nel rapporto.
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


def test_limmagine_installa_lextra_ai():
    contenuto = righe_unite(DOCKERFILE.read_text())
    installazioni = [r for r in contenuto.splitlines() if "pip install" in r]
    assert installazioni, f"{DOCKERFILE}: nessun `pip install`, questo test cerca male"

    assert any(".[ai]" in r or '".[ai]"' in r or "[ai," in r for r in installazioni), (
        f"{DOCKERFILE}: il pacchetto viene installato senza l'extra `ai`.\n"
        f"Trovato: {installazioni!r}\n"
        "`pip install -e .` non installa nessun extra: senza `ai` mancano dipendenze "
        "opzionali dall'immagine. Fino a task 13, la stesura AI usava il pacchetto "
        "`anthropic` e richiedeva questo extra; adesso usa OpenRouter via `httpx` "
        "(dipendenza di base), ma altri servizi potrebbero dipendere da pacchetti "
        "negli extra opzionali."
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


def test_beautifulsoup_e_una_dipendenza_di_base_e_non_un_extra():
    """Il parser dell'import non è una funzione opzionale.

    Messo fra gli extra finirebbe fuori dall'immagine esattamente come `anthropic`
    prima di questo file, e `python -m app.cli.import_gz` morirebbe su ImportError
    al primo uso in produzione, dove non c'è nessun test a dirlo.
    """
    progetto = tomllib.loads(PYPROJECT.read_text())["project"]
    assert any("beautifulsoup4" in dep for dep in progetto["dependencies"]), (
        f"{PYPROJECT}: beautifulsoup4 non è fra le dipendenze di base "
        f"({progetto['dependencies']!r}): il parser dell'import non parte."
    )
