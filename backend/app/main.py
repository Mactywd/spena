from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse

from app.api import auth, cooking, imports, ingredients, pantry, products, recipes, shopping
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


# Documentazione spenta qui e riaccesa sotto, dietro al gate. La spec §9 ammette
# fuori dalla sessione solo /health e /auth/login, e questa app esiste «solo per non
# tenere l'app aperta in chiaro su internet» (spec §13): Swagger e lo schema OpenAPI
# non espongono dati — ogni rotta che descrivono risponde 401 — ma pubblicherebbero
# l'intera superficie a chiunque trovi l'host. Si tengono perché al proprietario
# servono per leggere un contratto mentre ha un dubbio, e nel browser il cookie di
# sessione ce l'ha già: gratis per lui, niente per gli altri.
app = FastAPI(
    title="Spena",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)
app.include_router(auth.router)
app.include_router(ingredients.router)
app.include_router(products.router)
app.include_router(pantry.router)
app.include_router(shopping.router)
app.include_router(recipes.router)
app.include_router(cooking.router)
app.include_router(imports.router)


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get(
    "/api/v1/openapi.json", include_in_schema=False, dependencies=[Depends(require_session)]
)
async def openapi_schema() -> JSONResponse:
    return JSONResponse(app.openapi())


@app.get("/api/v1/docs", include_in_schema=False, dependencies=[Depends(require_session)])
async def swagger_ui() -> HTMLResponse:
    return get_swagger_ui_html(openapi_url="/api/v1/openapi.json", title="Spena")
