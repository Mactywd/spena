import json

import pytest
import pytest_asyncio

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.services.ai_recipes import AiUnavailable, draft_recipe


class FakeClaude:
    """Sostituisce il client Anthropic: la suite non fa rete."""

    def __init__(self, payload: dict | Exception) -> None:
        self._payload = payload
        self.messages = self

    async def create(self, **_kwargs):
        if isinstance(self._payload, Exception):
            raise self._payload

        class Block:
            text = json.dumps(self._payload)

        class Response:
            content = [Block()]

        return Response()


DRAFT = {
    "title": "Pasta al pomodoro",
    "description": "Veloce e di sempre",
    "instructions": "Cuoci la pasta. Scalda il sugo. Unisci.",
    "servings": 2,
    "ingredients": [
        {"name": "pasta", "role": "primary", "quantity_text": "200 g"},
        {"name": "pomodoro", "role": "primary", "quantity_text": "400 g"},
        {"name": "basilico fresco tritato", "role": "secondary", "quantity_text": "q.b."},
        {"name": "zafferano di Navelli", "role": "secondary", "quantity_text": "1 bustina"},
    ],
}


@pytest_asyncio.fixture
async def anagrafica(db_session):
    for name, category in [
        ("pasta", IngredientCategory.CEREALI),
        ("pomodoro", IngredientCategory.VERDURA),
        ("basilico", IngredientCategory.SPEZIE),
    ]:
        db_session.add(Ingredient(name=name, display_name=name.capitalize(), category=category))
    await db_session.flush()


async def test_draft_returns_structured_ingredients_with_roles(db_session, anagrafica):
    draft = await draft_recipe(db_session, "qualcosa di veloce", client=FakeClaude(DRAFT))

    assert draft.title == "Pasta al pomodoro"
    assert draft.servings == 2
    roles = {i.raw_name: i.role for i in draft.ingredients}
    assert roles["pasta"] == "primary"
    assert roles["basilico fresco tritato"] == "secondary"


async def test_known_ingredients_are_matched_confidently(db_session, anagrafica):
    draft = await draft_recipe(db_session, "x", client=FakeClaude(DRAFT))
    pasta = next(i for i in draft.ingredients if i.raw_name == "pasta")
    assert pasta.ingredient_id is not None
    assert pasta.matched_name == "pasta"
    assert pasta.confident is True


async def test_a_near_match_is_proposed_but_flagged_uncertain(db_session, anagrafica):
    """"basilico fresco tritato" somiglia a "basilico", ma la conferma spetta a te."""
    draft = await draft_recipe(db_session, "x", client=FakeClaude(DRAFT))
    basilico = next(i for i in draft.ingredients if i.raw_name == "basilico fresco tritato")
    assert basilico.matched_name == "basilico"
    assert basilico.confident is False


async def test_an_unknown_ingredient_has_no_match(db_session, anagrafica):
    draft = await draft_recipe(db_session, "x", client=FakeClaude(DRAFT))
    zafferano = next(i for i in draft.ingredients if i.raw_name == "zafferano di Navelli")
    assert zafferano.ingredient_id is None
    assert zafferano.confident is False


async def test_api_failure_raises_ai_unavailable(db_session, anagrafica):
    with pytest.raises(AiUnavailable):
        await draft_recipe(db_session, "x", client=FakeClaude(RuntimeError("429")))


async def test_malformed_json_raises_ai_unavailable(db_session, anagrafica):
    class Garbage(FakeClaude):
        async def create(self, **_kwargs):
            class Block:
                text = "non sono JSON"

            class Response:
                content = [Block()]

            return Response()

    with pytest.raises(AiUnavailable):
        await draft_recipe(db_session, "x", client=Garbage({}))


async def test_response_that_is_not_a_dict_raises_ai_unavailable(
    db_session, anagrafica
):
    """La risposta al top level deve essere un oggetto JSON."""
    with pytest.raises(AiUnavailable):
        await draft_recipe(db_session, "x", client=FakeClaude([1, 2, 3]))


async def test_ingredients_entries_that_are_not_dicts_raise_ai_unavailable(
    db_session, anagrafica
):
    """Gli ingredienti devono essere oggetti, non stringhe."""
    bad_draft = {
        "title": "Ricetta rotta",
        "description": "Descrizione",
        "instructions": "Passi",
        "servings": 2,
        "ingredients": ["pasta", "pomodoro"],
    }
    with pytest.raises(AiUnavailable):
        await draft_recipe(db_session, "x", client=FakeClaude(bad_draft))


async def test_missing_api_key_raises_ai_unavailable(db_session, anagrafica, monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(AiUnavailable):
        await draft_recipe(db_session, "x")
    get_settings.cache_clear()
