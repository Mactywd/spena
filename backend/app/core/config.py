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
    # L'LLM dell'import e dell'AI sulle ricette: Claude Haiku via l'API Messages di
    # Anthropic, con la stessa ANTHROPIC_API_KEY dei Pasti (deciso da Mattia il
    # 2026-11-21). Un client solo, in app/services/llm.py: un secondo fornitore dietro
    # un interruttore non girerebbe mai in produzione, ed è il difetto in cima a CLAUDE.md.
    # L'indirizzo dell'API non è un'impostazione: un campo `anthropic_base_url` leggerebbe
    # ANTHROPIC_BASE_URL dall'ambiente, che le shell degli agenti hanno.
    llm_model: str = "claude-haiku-5-5"
    # Per tentativo, e l'SDK ne fa fino a 1 + LLM_MAX_RETRIES (su 429, 5xx, 529 e rete). La
    # bozza e la variante hanno il loro: passano da Nginx, che aspetta 60 s.
    llm_timeout_seconds: float = 45.0
    llm_max_retries: int = 2
    llm_max_concurrency: int = 8
    # La chiave API di Anthropic: per i Pasti (chat, pianificazione, ricette dei pasti) e
    # per l'LLM dell'import con Claude Haiku. Vuota o assente: la chat dice che Claude non
    # è collegato, e l'import e l'AI sulle ricette continuano a mano.
    anthropic_api_key: str | None = None
    claude_model: str = "claude-opus-5-5"
    claude_reply_timeout_seconds: float = 240.0
    # Una cartella vuota come `cwd` dell'SDK: nessun CLAUDE.md di progetto è vicino.
    claude_workdir: str = "/tmp/spena-claude"
    embedding_backend: str = "local"
    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_endpoint: str = ""
    off_base_url: str = "https://world.openfoodfacts.org"
    off_timeout_seconds: float = 3.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
