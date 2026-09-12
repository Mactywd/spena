from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app.api import auth, cooking, ingredients, pantry, products, recipes, shopping
from app.core.config import get_settings
from app.core.security import (
    SECRET_HOWTO,
    InsecureSessionSecret,
    is_insecure_session_secret,
    require_session,
)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Un server con un segreto pubblico non deve sembrare sano.

    Il controllo in app/core/security.py scatta alla prima richiesta che tocca un
    cookie: fino a quel momento /health risponde 200 e il deploy sembra riuscito.
    Qui il processo muore all'avvio, dove chi ha fatto il deploy sta ancora
    guardando i log, con scritto come generare il segreto.
    """
    secret = get_settings().session_secret
    if is_insecure_session_secret(secret):
        raise InsecureSessionSecret(SECRET_HOWTO)
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
