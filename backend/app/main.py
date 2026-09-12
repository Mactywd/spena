from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app.api import auth, cooking, ingredients, pantry, products, recipes, shopping
from app.core.config import get_settings
from app.core.security import (
    PASSWORD_HASH_HOWTO,
    SECRET_HOWTO,
    InsecureSessionSecret,
    UnusablePasswordHash,
    is_insecure_session_secret,
    is_unusable_password_hash,
    require_session,
)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Un server mal configurato non deve sembrare sano.

    Il controllo sul segreto in app/core/security.py scatta alla prima richiesta che
    tocca un cookie: fino a quel momento /health risponde 200 e il deploy sembra
    riuscito. Qui il processo muore all'avvio, dove chi ha fatto il deploy sta ancora
    guardando i log, con scritto come rimediare.

    L'hash della password sta qui per un motivo peggiore: un APP_PASSWORD_HASH
    troncato (è quello che fa Compose ai `$` senza `format: raw`) non produce nessun
    sintomo diagnosticabile. `verify_password` risponde False come per una password
    sbagliata, quindi l'unico segnale è «password errata» per sempre, su un `.env`
    che a occhio sembra pieno. Un vicolo cieco di questo tipo va fermato dove si
    vede, cioè nei log dell'avvio.

    Un hash vuoto invece lascia partire: è il `.env` non ancora riempito, e il login
    risponde 401 dicendo il vero.
    """
    settings = get_settings()
    if is_insecure_session_secret(settings.session_secret):
        raise InsecureSessionSecret(SECRET_HOWTO)
    if is_unusable_password_hash(settings.app_password_hash):
        raise UnusablePasswordHash(PASSWORD_HASH_HOWTO)
    yield


app = FastAPI(
    title="Spena",
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)
app.include_router(auth.router)
app.include_router(ingredients.router)
app.include_router(products.router)
app.include_router(pantry.router)
app.include_router(shopping.router)
app.include_router(recipes.router)
app.include_router(cooking.router)


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/ping-protected", dependencies=[Depends(require_session)])
async def ping_protected() -> dict[str, bool]:
    """Esiste per provare il gate. Resta, costa nulla e documenta il contratto."""
    return {"ok": True}
