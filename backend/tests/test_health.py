async def test_health_ok(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_required_extensions_present(db_session):
    from sqlalchemy import text

    result = await db_session.execute(
        text("SELECT extname FROM pg_extension WHERE extname IN ('vector', 'pg_trgm')")
    )
    assert set(result.scalars()) == {"vector", "pg_trgm"}
