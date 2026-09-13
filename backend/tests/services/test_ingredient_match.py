import pytest_asyncio
from llm_fakes import FakeLlm

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


async def test_il_nome_canonico_vince_su_un_alias_omonimo(db_session, anagrafica):
    """Se l'anagrafica arriva ad avere un ingrediente il cui nome coincide con
    l'alias di un altro (il duplicato lo permette: controlla solo
    `ingredients.name`, non gli alias esistenti), l'OR con `.limit(1)` e senza
    `ORDER BY` lascerebbe Postgres scegliere a caso fra i due. Qui «pomodori
    pelati» è insieme un alias di «pomodoro» (dalla fixture) e, dopo questa
    riga, il nome canonico di un secondo ingrediente: il nome canonico deve
    vincere sempre, non a caso una volta su due."""
    db_session.add(
        Ingredient(
            name="pomodori pelati", display_name="Pomodori pelati",
            category=IngredientCategory.VERDURA,
        )
    )
    await db_session.flush()

    match = await match_name(db_session, "Pomodori pelati")

    assert match.name == "pomodori pelati"
    assert match.certain is True


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
    from app.core.config import get_settings

    import app.services.ai_recipes as ai_recipes

    chiamate: list[str] = []
    originale = ai_recipes.match_name

    async def spia(session, raw_name):
        chiamate.append(raw_name)
        return await originale(session, raw_name)

    monkeypatch.setattr(ai_recipes, "match_name", spia)

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    try:
        finto = FakeLlm({
            "title": "Pasta al pomodoro",
            "description": "",
            "instructions": "Cuoci.",
            "servings": 2,
            "ingredients": [
                {"name": "pasta", "role": "primary", "quantity_text": "200 g",
                 "category": "cereali"}
            ],
        })
        await ai_recipes.draft_recipe(db_session, "qualcosa", client=finto)
    finally:
        get_settings.cache_clear()
    assert chiamate == ["pasta"]
