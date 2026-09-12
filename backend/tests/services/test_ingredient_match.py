import pytest_asyncio

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.services.ingredient_match import match_name


@pytest_asyncio.fixture
async def anagrafica(db_session):
    pomodoro = Ingredient(
        name="pomodoro", display_name="Pomodoro", category=IngredientCategory.VERDURA
    )
    pomodoro.aliases.append(IngredientAlias(alias="pomodori pelati", source="import"))
    db_session.add(pomodoro)
    db_session.add(
        Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
    )
    await db_session.flush()


async def test_il_nome_canonico_esatto_e_certo(db_session, anagrafica):
    match = await match_name(db_session, "Pomodoro")
    assert match.name == "pomodoro"
    assert match.certain is True


async def test_un_alias_esatto_e_certo(db_session, anagrafica):
    """Era il difetto dell'implementazione precedente: un alias scritto da noi
    veniva proposto come incerto, e chiedeva una conferma che non serve."""
    match = await match_name(db_session, "Pomodori pelati")
    assert match.name == "pomodoro"
    assert match.certain is True


async def test_una_somiglianza_si_propone_ma_resta_incerta(db_session, anagrafica):
    match = await match_name(db_session, "pomodorini")
    assert match.name == "pomodoro"
    assert match.certain is False


async def test_niente_di_somigliante_non_e_un_aggancio(db_session, anagrafica):
    match = await match_name(db_session, "bottarga di muggine")
    assert match.ingredient_id is None
    assert match.name is None
    assert match.certain is False


async def test_la_stesura_ai_usa_questa_funzione(db_session, anagrafica, monkeypatch):
    """Il punto di questo task: non deve esistere una seconda implementazione.

    Se `draft_recipe` tornasse a calcolarsi l'aggancio da sé, questo test resta
    verde mentre ogni garanzia qui sopra difende codice che nessuno chiama.
    """
    import app.services.ai_recipes as ai_recipes

    chiamate: list[str] = []
    originale = ai_recipes.match_name

    async def spia(session, raw_name):
        chiamate.append(raw_name)
        return await originale(session, raw_name)

    monkeypatch.setattr(ai_recipes, "match_name", spia)

    class FakeClaude:
        def __init__(self) -> None:
            self.messages = self

        async def create(self, **_kwargs):
            import json

            class Block:
                text = json.dumps(
                    {
                        "title": "Pasta al pomodoro",
                        "description": "",
                        "instructions": "Cuoci.",
                        "servings": 2,
                        "ingredients": [
                            {"name": "pasta", "role": "primary", "quantity_text": "200 g"}
                        ],
                    }
                )

            class Response:
                content = [Block()]

            return Response()

    await ai_recipes.draft_recipe(db_session, "qualcosa", client=FakeClaude())
    assert chiamate == ["pasta"]
