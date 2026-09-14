from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Il .env vive nella radice del repository, non in backend/. Un percorso relativo
# verrebbe risolto rispetto alla directory da cui parte il processo: fuori da
# Compose (pytest, uvicorn lanciato da backend/) il file non verrebbe trovato e
# ogni impostazione cadrebbe sul proprio default senza dirlo.
REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = REPO_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    database_url: str = "postgresql+asyncpg://spena:spena@localhost:5433/spena"
    # nessun default utilizzabile: un segreto scritto in questo repository è
    # pubblico, e firmarci un cookie equivale a non avere password (vedi
    # app/core/security.py, che rifiuta i valori segnaposto)
    session_secret: str = ""
    app_password_hash: str = ""
    # Il cookie di sessione viaggia con `Secure` solo dove esiste HTTPS. Il default
    # è False perché in sviluppo si serve anche su http://localhost, e un cookie
    # `Secure` lì non verrebbe mai mandato: l'accesso riuscirebbe e ogni chiamata
    # successiva risponderebbe 401, senza dire perché. In produzione vale true
    # (docker-compose.prod.yml lo impone al servizio).
    cookie_secure: bool = False
    # OpenRouter è l'unico fornitore di LLM dell'applicazione. Un secondo fornitore
    # dietro un'interfaccia scelta da una variabile (come EMBEDDING_BACKEND) non
    # girerebbe mai in produzione, e sarebbe il difetto in cima a CLAUDE.md. Quel che
    # resta configurabile è il modello: OpenRouter fa da proxy anche a Claude, quindi
    # passare a un modello grosso è questa riga, non un secondo client.
    openrouter_api_key: str | None = None
    openrouter_model: str = "google/gemma-4-26b-a4b-it"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # Identificano l'app nelle classifiche e nei consumi di OpenRouter. Il titolo ha
    # un default perché è una costante del progetto; l'indirizzo no, perché è il
    # dominio di chi installa e nel codice non ci sta.
    openrouter_app_title: str = "Spena Import Ricette"
    openrouter_app_url: str = ""
    # Vuota: instradamento per prezzo fra i provider che sanno onorare lo schema.
    # Valorizzata (lista separata da virgole): scavalco manuale, e si perde il
    # failover automatico. Vedi `python -m app.cli.llm_prices`.
    openrouter_provider_only: str = ""
    # 60 e non i 3 di Open Food Facts: un MoE su una domanda con l'anagrafica intera
    # dentro è lento, e un timeout troppo corto si presenta come «decidi a mano».
    llm_timeout_seconds: float = 60.0
    llm_max_concurrency: int = 8
    embedding_backend: str = "local"
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_endpoint: str = ""
    off_base_url: str = "https://world.openfoodfacts.org"
    off_timeout_seconds: float = 3.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
