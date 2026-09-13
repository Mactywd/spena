"""Le impostazioni di OpenRouter: i default e il fatto che l'ambiente li scavalchi.

`get_settings` è memoizzata con `lru_cache`: senza `cache_clear` un test che imposta
una variabile leggerebbe l'istanza costruita da un test precedente, e passerebbe o
fallirebbe in base all'ordine di esecuzione.
"""

from app.core.config import get_settings


def test_i_default_sono_quelli_della_spec():
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.openrouter_api_key is None
        assert settings.openrouter_model == "google/gemma-4-26b-a4b-it"
        assert settings.openrouter_base_url == "https://openrouter.ai/api/v1"
        assert settings.openrouter_app_title == "Spena Import Ricette"
        # vuota di proposito: il dominio dell'utente sta in .env, non nel codice
        assert settings.openrouter_app_url == ""
        assert settings.openrouter_provider_only == ""
        assert settings.llm_timeout_seconds == 60.0
        assert settings.llm_max_concurrency == 8
    finally:
        get_settings.cache_clear()


def test_lambiente_scavalca_i_default(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-5")
    monkeypatch.setenv("OPENROUTER_PROVIDER_ONLY", "darkbloom")
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "3")
    try:
        settings = get_settings()
        assert settings.openrouter_model == "anthropic/claude-sonnet-5"
        assert settings.openrouter_provider_only == "darkbloom"
        assert settings.llm_max_concurrency == 3
    finally:
        get_settings.cache_clear()


def test_anthropic_non_e_piu_unimpostazione():
    """La chiave di Anthropic esce da Settings, non resta come campo morto.

    Un campo che nessuno legge è peggio che assente: chi configura `.env` crede di
    aver acceso qualcosa.
    """
    get_settings.cache_clear()
    try:
        assert not hasattr(get_settings(), "anthropic_api_key")
    finally:
        get_settings.cache_clear()
