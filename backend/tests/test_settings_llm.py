"""Le impostazioni dell'LLM: i default e il fatto che l'ambiente li scavalchi.

`get_settings` è memoizzata con `lru_cache`: senza `cache_clear` un test che imposta
una variabile leggerebbe l'istanza costruita da un test precedente, e passerebbe o
fallirebbe in base all'ordine di esecuzione.
"""

from app.core.config import get_settings
from app.domain.llm_pricing import PRICES


def test_i_default():
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.llm_model == "claude-haiku-5-5"
        assert settings.llm_timeout_seconds == 45.0
        assert settings.llm_max_retries == 2
        assert settings.llm_max_concurrency == 8
        # OpenRouter non c'è più: nessuna impostazione ne porta il nome
        assert not [nome for nome in dir(settings) if nome.startswith("openrouter")]
    finally:
        get_settings.cache_clear()


def test_lambiente_scavalca_i_default(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("LLM_MODEL", "claude-sonnet-5")
    monkeypatch.setenv("LLM_MAX_RETRIES", "0")
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "3")
    try:
        settings = get_settings()
        assert settings.llm_model == "claude-sonnet-5"
        assert settings.llm_max_retries == 0
        assert settings.llm_max_concurrency == 3
    finally:
        get_settings.cache_clear()


def test_il_modello_di_default_ha_un_prezzo():
    """Un modello senza listino registrerebbe ogni chiamata a costo sconosciuto."""
    get_settings.cache_clear()
    try:
        assert get_settings().llm_model in PRICES
    finally:
        get_settings.cache_clear()


def test_nessuna_impostazione_legge_anthropic_base_url(monkeypatch):
    """Le shell degli agenti hanno ANTHROPIC_BASE_URL: un campo che la leggesse
    manderebbe le chiamate dell'import dove dice l'ambiente, non ad Anthropic."""
    get_settings.cache_clear()
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:9")
    try:
        valori = get_settings().model_dump().values()
        assert "http://127.0.0.1:9" not in [str(v) for v in valori]
    finally:
        get_settings.cache_clear()
