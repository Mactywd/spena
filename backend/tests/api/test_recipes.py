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


def _vettore_a_distanza(distanza: float) -> list[float]:
    """Vettore unitario a `distanza` coseno da `_vettore_a_distanza(0)`.

    Vive nel piano dei primi due assi: `cosine_distance` fra due unitari è
    `1 - prodotto scalare`, quindi la distanza che il database calcolerà è quella
    scritta qui e il lettore può verificarla a mente.
    """
    from app.db.models.recipe import EMBEDDING_DIM

    coseno = 1.0 - distanza
    vettore = [0.0] * EMBEDDING_DIM
    vettore[0] = coseno
    vettore[1] = (1.0 - coseno**2) ** 0.5
    return vettore


@pytest_asyncio.fixture
async def due_ricette_a_distanza_nota(db_session):
    """Una ricetta vicina (0,10) e una lontana (0,30), intorno alla soglia di 0,17.

    I titoli non contengono la parola che le query useranno: così è la sola metà
    semantica a deciderne la sorte, e la metà testuale non maschera il risultato.
    """
    from app.repositories.recipes import create_recipe

    for titolo, distanza in (("Ricetta vicina", 0.10), ("Ricetta lontana", 0.30)):
        await create_recipe(
            db_session, title=titolo, description=None, instructions="Nulla.",
            servings=None, source="manual", source_ref=None, ingredients=[],
            embedding=_vettore_a_distanza(distanza),
        )
    await db_session.flush()


def _query_finta(monkeypatch, distanza_zero_da: float = 0.0):
    from app.services import recipe_search

    async def embed(_: str) -> list[float]:
        return _vettore_a_distanza(distanza_zero_da)

    monkeypatch.setattr(recipe_search, "_embed_query", embed)


async def test_la_soglia_semantica_tiene_i_vicini_e_scarta_il_resto(
    logged_client, due_ricette_a_distanza_nota, monkeypatch
):
    """La metà semantica deve trovare ciò che il testo non trova, ma non tutto.

    Query nel punto 0: la ricetta a 0,10 è dentro la soglia (0,17), quella a 0,30 no.
    La parola cercata non compare in nessun titolo, quindi l'unica via per entrare
    nei risultati è il vettore.
    """
    _query_finta(monkeypatch)
    body = (await logged_client.get("/api/v1/recipes/search?q=xyzzy")).json()
    assert [r["title"] for r in body] == ["Ricetta vicina"]


async def test_una_query_lontana_da_tutto_non_restituisce_niente(
    logged_client, due_ricette_a_distanza_nota, monkeypatch
):
    """Il difetto che la soglia esiste per chiudere: prima tornava il ricettario intero.

    Il vettore della query è ortogonale a entrambe le ricette (distanza 1,0) e la
    parola non compare da nessuna parte: la risposta onesta è nessun risultato, non
    il meno peggio.
    """
    from app.db.models.recipe import EMBEDDING_DIM
    from app.services import recipe_search

    ortogonale = [0.0] * EMBEDDING_DIM
    ortogonale[2] = 1.0

    async def embed(_: str) -> list[float]:
        return ortogonale

    monkeypatch.setattr(recipe_search, "_embed_query", embed)
    assert (await logged_client.get("/api/v1/recipes/search?q=xyzzy")).json() == []
