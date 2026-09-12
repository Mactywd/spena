import pytest_asyncio

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.shopping import ShoppingListItem, ShoppingReason, ShoppingStatus
from app.repositories.ingredients import search_ingredients


@pytest_asyncio.fixture
async def catalogo(db_session):
    pomodoro = Ingredient(name="pomodoro", display_name="Pomodoro",
                          category=IngredientCategory.VERDURA)
    pomodoro.aliases.append(IngredientAlias(alias="pomodori pelati", source="import"))
    yogurt = Ingredient(name="yogurt greco", display_name="Yogurt greco",
                        category=IngredientCategory.LATTICINI)
    prezzemolo = Ingredient(name="prezzemolo", display_name="Prezzemolo",
                            category=IngredientCategory.SPEZIE)
    db_session.add_all([pomodoro, yogurt, prezzemolo])
    await db_session.flush()
    return {"pomodoro": pomodoro, "yogurt": yogurt, "prezzemolo": prezzemolo}


async def test_search_finds_by_exact_prefix(db_session, catalogo):
    results = await search_ingredients(db_session, "pomo")
    assert [i.name for i in results][0] == "pomodoro"


async def test_search_forgives_a_typo(db_session, catalogo):
    results = await search_ingredients(db_session, "yogrut greco")
    assert "yogurt greco" in [i.name for i in results]


async def test_search_matches_on_aliases(db_session, catalogo):
    results = await search_ingredients(db_session, "pelati")
    assert [i.name for i in results][0] == "pomodoro"


async def test_search_returns_each_ingredient_once(db_session, catalogo):
    """Un match sia sul nome sia su un alias non deve duplicare la riga."""
    catalogo["pomodoro"].aliases.append(IngredientAlias(alias="pomodoro rosso", source="manual"))
    await db_session.flush()
    results = await search_ingredients(db_session, "pomodoro")
    names = [i.name for i in results]
    assert names.count("pomodoro") == 1


async def test_frequently_bought_ingredients_rank_first(db_session, catalogo):
    """A pari somiglianza vince ciò che compri davvero."""
    for _ in range(5):
        db_session.add(ShoppingListItem(
            raw_text="prezzemolo", ingredient_id=catalogo["prezzemolo"].id,
            status=ShoppingStatus.DONE, reason=ShoppingReason.MANUAL,
        ))
    await db_session.flush()
    results = await search_ingredients(db_session, "p")
    assert results[0].name == "prezzemolo"


async def test_fuzzy_match_ranks_by_similarity_not_frequency(db_session):
    """Su una query lunga con refuso, la somiglianza vince sulla frequenza d'acquisto.

    Né 'pomodoro' né 'pomodorini' sono prefissi di 'pomodorr' (entrambi i LIKE sono
    falsi), quindi il confronto ricade sulla sola trigram similarity: 'pomodoro' è
    più simile (0.636) di 'pomodorini' (0.538). Comprare 'pomodorini' cinque volte
    non deve ribaltare l'ordine: la frequenza è un criterio secondario, non primario,
    quando il match non è un prefisso esatto.
    """
    pomodoro = Ingredient(name="pomodoro", display_name="Pomodoro",
                          category=IngredientCategory.VERDURA)
    pomodorini = Ingredient(name="pomodorini", display_name="Pomodorini",
                            category=IngredientCategory.VERDURA)
    db_session.add_all([pomodoro, pomodorini])
    await db_session.flush()

    for _ in range(5):
        db_session.add(ShoppingListItem(
            raw_text="pomodorini", ingredient_id=pomodorini.id,
            status=ShoppingStatus.DONE, reason=ShoppingReason.MANUAL,
        ))
    await db_session.flush()

    results = await search_ingredients(db_session, "pomodorr")
    assert results[0].name == "pomodoro"


async def test_search_endpoint_requires_a_session(client):
    assert (await client.get("/api/v1/ingredients/search?q=pomo")).status_code == 401


async def test_create_ingredient_and_alias_via_api(logged_client, db_session):
    created = await logged_client.post("/api/v1/ingredients", json={
        "name": "basilico", "display_name": "Basilico", "category": "spezie",
    })
    assert created.status_code == 201
    ingredient_id = created.json()["id"]

    aliased = await logged_client.post(
        f"/api/v1/ingredients/{ingredient_id}/aliases",
        json={"alias": "basilico genovese", "source": "manual"},
    )
    assert aliased.status_code == 201

    found = await logged_client.get("/api/v1/ingredients/search?q=genovese")
    assert found.json()[0]["name"] == "basilico"


async def test_duplicate_ingredient_name_returns_409(logged_client):
    body = {"name": "basilico", "display_name": "Basilico", "category": "spezie"}
    assert (await logged_client.post("/api/v1/ingredients", json=body)).status_code == 201
    assert (await logged_client.post("/api/v1/ingredients", json=body)).status_code == 409


async def test_alias_on_a_missing_ingredient_is_404_not_409(logged_client):
    """Un ingrediente inesistente non è un alias duplicato: dirlo bene importa."""
    import uuid

    response = await logged_client.post(
        f"/api/v1/ingredients/{uuid.uuid4()}/aliases",
        json={"alias": "basilico genovese", "source": "manual"},
    )
    assert response.status_code == 404
    assert "ingrediente" in response.json()["detail"]


async def test_duplicate_alias_is_still_409(logged_client):
    created = await logged_client.post("/api/v1/ingredients", json={
        "name": "basilico", "display_name": "Basilico", "category": "spezie",
    })
    ingredient_id = created.json()["id"]
    body = {"alias": "basilico genovese", "source": "manual"}
    url = f"/api/v1/ingredients/{ingredient_id}/aliases"
    assert (await logged_client.post(url, json=body)).status_code == 201
    conflict = await logged_client.post(url, json=body)
    assert conflict.status_code == 409
    assert "alias" in conflict.json()["detail"]
