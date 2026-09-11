from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://spena:spena@localhost:5433/spena"
    session_secret: str = "dev-insecure-secret"
    app_password_hash: str = ""
    anthropic_api_key: str | None = None
    embedding_backend: str = "local"
    embedding_model: str = "intfloat/multilingual-e5-small"
    off_base_url: str = "https://world.openfoodfacts.org"
    off_timeout_seconds: float = 3.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
