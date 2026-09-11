from fastapi import FastAPI

app = FastAPI(title="Spena", docs_url="/api/v1/docs", openapi_url="/api/v1/openapi.json")


@app.get("/api/v1/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
