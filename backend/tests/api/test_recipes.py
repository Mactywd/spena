import pytest_asyncio

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.pantry import PantryItem
from app.domain.rules import PantryStatus


@pytest_asyncio.fixture
async def cucina(db_session):
    pomodoro = Ingredient(name="pomodoro", display_name="Pomodoro",
                          category=IngredientCategory.VERDURA)
    pasta = Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
    aglio = Ingredient(name="aglio", display_name="Aglio", category=IngredientCategory.VERDURA)
    db_session.add_all([pomodoro, pasta, aglio])
    await db_session.flush()
    return {"pomodoro": pomodoro, "pasta": pasta, "aglio": aglio}


async def _create_recipe(client, cucina, title="Pasta al pomodoro", primary=("pasta", "pomodoro"),
                         secondary=("aglio",)):
    ingredients = [
        {"ingredient_id": str(cucina[name].id), "role": "primary", "quantity_text": "q.b."}
        for name in primary
    ] + [
        {"ingredient_id": str(cucina[name].id), "role": "secondary"} for name in secondary
    ]
    response = await client.post("/api/v1/recipes", json={
        "title": title, "description": "Il piatto di sempre",
        "instructions": "Cuoci la pasta, scalda il sugo.", "servings": 2,
        "source": "manual", "ingredients": ingredients,
    })
    assert response.status_code == 201
    return response.json()


async def test_create_recipe_stores_roles_and_quantity_text(logged_client, cucina):
    body = await _create_recipe(logged_client, cucina)
    roles = {i["ingredient_name"]: i["role"] for i in body["ingredients"]}
    assert roles == {"pasta": "primary", "pomodoro": "primary", "aglio": "secondary"}
    quantities = {i["ingredient_name"]: i["quantity_text"] for i in body["ingredients"]}
    assert quantities["pasta"] == "q.b."


async def test_detail_reports_availability_and_cookability(logged_client, db_session, cucina):
    created = await _create_recipe(logged_client, cucina)
    db_session.add_all([
        PantryItem(ingredient_id=cucina["pasta"].id, status=PantryStatus.AVAILABLE),
        PantryItem(ingredient_id=cucina["pomodoro"].id, status=PantryStatus.LOW),
        PantryItem(ingredient_id=cucina["aglio"].id, status=PantryStatus.LOW),
    ])
    await db_session.flush()

    body = (await logged_client.get(f"/api/v1/recipes/{created['id']}")).json()
    by_name = {i["ingredient_name"]: i for i in body["ingredients"]}
    # il pomodoro è principale e quasi finito: non basta
    assert by_name["pomodoro"]["availability"] == "low"
    assert by_name["pomodoro"]["satisfied"] is False
    # l'aglio è secondario e quasi finito: basta
    assert by_name["aglio"]["satisfied"] is True
    assert body["missing"] == 1
    assert body["cookable"] is False


async def test_recipe_becomes_cookable_when_the_primary_is_full(logged_client, db_session, cucina):
    created = await _create_recipe(logged_client, cucina)
    db_session.add_all([
        PantryItem(ingredient_id=cucina["pasta"].id, status=PantryStatus.AVAILABLE),
        PantryItem(ingredient_id=cucina["pomodoro"].id, status=PantryStatus.AVAILABLE),
        PantryItem(ingredient_id=cucina["aglio"].id, status=PantryStatus.LOW),
    ])
    await db_session.flush()
    body = (await logged_client.get(f"/api/v1/recipes/{created['id']}")).json()
    assert body["cookable"] is True
    assert body["missing"] == 0


async def test_search_ranks_closer_recipes_first(logged_client, db_session, cucina):
    """Con tutto in dispensa nulla manca, così l'ordine dipende solo dalla pertinenza."""
    await _create_recipe(logged_client, cucina, title="Pasta al pomodoro")
    await _create_recipe(logged_client, cucina, title="Aglio olio e peperoncino",
                         primary=("pasta",), secondary=("aglio",))
    db_session.add_all([
        PantryItem(ingredient_id=cucina[name].id, status=PantryStatus.AVAILABLE)
        for name in ("pasta", "pomodoro", "aglio")
    ])
    await db_session.flush()

    body = (await logged_client.get("/api/v1/recipes/search?q=pomodoro")).json()
    assert body[0]["title"] == "Pasta al pomodoro"


async def test_search_reorders_by_what_is_missing_without_hiding(logged_client, db_session, cucina):
    """Una ricetta a cui manca un ingrediente resta visibile, solo più in basso."""
    await _create_recipe(logged_client, cucina, title="Pasta al pomodoro")
    await _create_recipe(logged_client, cucina, title="Pasta all'aglio",
                         primary=("pasta",), secondary=("aglio",))
    db_session.add_all([
        PantryItem(ingredient_id=cucina["pasta"].id, status=PantryStatus.AVAILABLE),
        PantryItem(ingredient_id=cucina["aglio"].id, status=PantryStatus.AVAILABLE),
    ])
    await db_session.flush()

    body = (await logged_client.get("/api/v1/recipes/search?q=pasta")).json()
    titles = [r["title"] for r in body]
    assert titles[0] == "Pasta all'aglio"
    assert "Pasta al pomodoro" in titles


async def test_only_cookable_filter_hides_the_rest(logged_client, db_session, cucina):
    await _create_recipe(logged_client, cucina, title="Pasta al pomodoro")
    await _create_recipe(logged_client, cucina, title="Pasta all'aglio",
                         primary=("pasta",), secondary=("aglio",))
    db_session.add_all([
        PantryItem(ingredient_id=cucina["pasta"].id, status=PantryStatus.AVAILABLE),
        PantryItem(ingredient_id=cucina["aglio"].id, status=PantryStatus.AVAILABLE),
    ])
    await db_session.flush()

    body = (await logged_client.get("/api/v1/recipes/search?only_cookable=true")).json()
    assert [r["title"] for r in body] == ["Pasta all'aglio"]


async def test_search_without_a_query_lists_the_whole_book(logged_client, cucina):
    await _create_recipe(logged_client, cucina, title="Pasta al pomodoro")
    body = (await logged_client.get("/api/v1/recipes/search")).json()
    assert len(body) == 1
    assert body[0]["source"] == "manual"


async def test_search_survives_an_unavailable_embedding_provider(
    logged_client, cucina, monkeypatch
):
    """Senza vettori la ricerca degrada al solo testo, non restituisce un errore."""
    from app.services import recipe_search

    async def broken(_: str) -> list[float]:
        from app.services.embeddings import EmbeddingUnavailable

        raise EmbeddingUnavailable("modello assente")

    await _create_recipe(logged_client, cucina, title="Pasta al pomodoro")
    monkeypatch.setattr(recipe_search, "_embed_query", broken)
    response = await logged_client.get("/api/v1/recipes/search?q=pomodoro")
    assert response.status_code == 200
    assert response.json()[0]["title"] == "Pasta al pomodoro"


async def test_creating_with_a_dangling_ingredient_is_404_not_500(logged_client):
    import uuid

    response = await logged_client.post("/api/v1/recipes", json={
        "title": "Ricetta fantasma", "instructions": "Nulla.", "source": "manual",
        "ingredients": [{"ingredient_id": str(uuid.uuid4()), "role": "primary"}],
    })
    assert response.status_code == 404
    assert "inesistente" in response.json()["detail"]


async def test_repeating_an_ingredient_in_a_recipe_is_409_not_500(logged_client, cucina):
    """Lo stesso ingrediente due volte è un conflitto, non un riferimento mancante."""
    response = await logged_client.post("/api/v1/recipes", json={
        "title": "Pasta e pasta", "instructions": "Nulla.", "source": "manual",
        "ingredients": [
            {"ingredient_id": str(cucina["pasta"].id), "role": "primary"},
            {"ingredient_id": str(cucina["pasta"].id), "role": "secondary"},
        ],
    })
    assert response.status_code == 409


async def test_search_applies_the_role_rule_to_low_items(logged_client, db_session, cucina):
    """La regola dei ruoli vale anche in ricerca, non solo nel dettaglio.

    Un principale quasi finito non è soddisfatto, un secondario quasi finito sì:
    con pasta piena, pomodoro (principale) e aglio (secondario) agli sgoccioli,
    manca esattamente una cosa. Un calcolo cieco al ruolo direbbe due.
    """
    await _create_recipe(logged_client, cucina, title="Pasta al pomodoro")
    db_session.add_all([
        PantryItem(ingredient_id=cucina["pasta"].id, status=PantryStatus.AVAILABLE),
        PantryItem(ingredient_id=cucina["pomodoro"].id, status=PantryStatus.LOW),
        PantryItem(ingredient_id=cucina["aglio"].id, status=PantryStatus.LOW),
    ])
    await db_session.flush()

    body = (await logged_client.get("/api/v1/recipes/search?q=pomodoro")).json()
    assert [r["title"] for r in body] == ["Pasta al pomodoro"]
    assert body[0]["missing"] == 1
    assert body[0]["cookable"] is False


async def test_search_is_cookable_with_only_secondaries_low(logged_client, db_session, cucina):
    """Tutti i principali pieni e il solo secondario agli sgoccioli: si cucina."""
    await _create_recipe(logged_client, cucina, title="Pasta al pomodoro")
    db_session.add_all([
        PantryItem(ingredient_id=cucina["pasta"].id, status=PantryStatus.AVAILABLE),
        PantryItem(ingredient_id=cucina["pomodoro"].id, status=PantryStatus.AVAILABLE),
        PantryItem(ingredient_id=cucina["aglio"].id, status=PantryStatus.LOW),
    ])
    await db_session.flush()

    body = (await logged_client.get("/api/v1/recipes/search?q=pomodoro")).json()
    assert body[0]["missing"] == 0
    assert body[0]["cookable"] is True
