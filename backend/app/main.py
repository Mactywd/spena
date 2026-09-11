from fastapi import Depends, FastAPI

from app.api import auth
from app.core.security import require_session

app = FastAPI(title="Spena", docs_url="/api/v1/docs", openapi_url="/api/v1/openapi.json")
app.include_router(auth.router)


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/ping-protected", dependencies=[Depends(require_session)])
async def ping_protected() -> dict[str, bool]:
    """Esiste per provare il gate. Resta, costa nulla e documenta il contratto."""
    return {"ok": True}
