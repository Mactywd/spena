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
    anthropic_api_key: str | None = None
    embedding_backend: str = "local"
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_endpoint: str = ""
    off_base_url: str = "https://world.openfoodfacts.org"
    off_timeout_seconds: float = 3.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
