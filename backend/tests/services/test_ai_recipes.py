import pytest
import pytest_asyncio
from llm_fakes import FakeLlm

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.services.ai_recipes import draft_recipe
from app.services.llm import LlmUnavailable


@pytest.fixture(autouse=True)
def chiave(monkeypatch):
    """La suite non legge `.env` (vedi conftest.py): senza questo, ogni chiamata a
    `draft_recipe` con un client finto fallirebbe comunque su chiave assente, prima
    ancora di raggiungere il finto — `build_headers` gira sempre, client o no."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


DRAFT = {
    "title": "Pasta al pomodoro",
    "description": "Veloce e di sempre",
    "instructions": "Cuoci la pasta. Scalda il sugo. Unisci.",
    "servings": 2,
    "ingredients": [
        {"name": "pasta", "role": "primary", "quantity_text": "200 g", "category": "cereali"},
        {"name": "pomodoro", "role": "primary", "quantity_text": "400 g", "category": "verdura"},
        {
            "name": "basilico fresco tritato", "role": "secondary", "quantity_text": "q.b.",
            "category": "spezie",
        },
        {
            "name": "zafferano di Navelli", "role": "secondary", "quantity_text": "1 bustina",
            "category": "spezie",
        },
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
    draft = await draft_recipe(db_session, "qualcosa di veloce", client=FakeLlm(DRAFT))

    assert draft.title == "Pasta al pomodoro"
    assert draft.servings == 2
    roles = {i.raw_name: i.role for i in draft.ingredients}
    assert roles["pasta"] == "primary"
    assert roles["basilico fresco tritato"] == "secondary"


async def test_known_ingredients_are_matched_confidently(db_session, anagrafica):
    draft = await draft_recipe(db_session, "x", client=FakeLlm(DRAFT))
    pasta = next(i for i in draft.ingredients if i.raw_name == "pasta")
    assert pasta.ingredient_id is not None
    assert pasta.matched_name == "pasta"
    assert pasta.confident is True


async def test_a_near_match_is_proposed_but_flagged_uncertain(db_session, anagrafica):
    """"basilico fresco tritato" somiglia a "basilico", ma la conferma spetta a te."""
    draft = await draft_recipe(db_session, "x", client=FakeLlm(DRAFT))
    basilico = next(i for i in draft.ingredients if i.raw_name == "basilico fresco tritato")
    assert basilico.matched_name == "basilico"
    assert basilico.confident is False


async def test_an_unknown_ingredient_has_no_match(db_session, anagrafica):
    draft = await draft_recipe(db_session, "x", client=FakeLlm(DRAFT))
    zafferano = next(i for i in draft.ingredients if i.raw_name == "zafferano di Navelli")
    assert zafferano.ingredient_id is None
    assert zafferano.confident is False


async def test_api_failure_raises_llm_unavailable(db_session, anagrafica):
    with pytest.raises(LlmUnavailable):
        await draft_recipe(db_session, "x", client=FakeLlm(RuntimeError("429")))


async def test_malformed_json_raises_llm_unavailable(db_session, anagrafica):
    with pytest.raises(LlmUnavailable):
        await draft_recipe(db_session, "x", client=FakeLlm("non sono JSON"))


async def test_response_that_is_not_a_dict_raises_llm_unavailable(
    db_session, anagrafica
):
    """La risposta al top level deve essere un oggetto JSON."""
    with pytest.raises(LlmUnavailable):
        await draft_recipe(db_session, "x", client=FakeLlm([1, 2, 3]))


async def test_ingredients_entries_that_are_not_dicts_are_skipped(
    db_session, anagrafica
):
    """Gli ingredienti che non sono oggetti si scartano, non bloccano la bozza."""
    bad_draft = {
        "title": "Ricetta rotta",
        "description": "Descrizione",
        "instructions": "Passi",
        "servings": 2,
        "ingredients": ["pasta", "pomodoro"],
    }
    draft = await draft_recipe(db_session, "x", client=FakeLlm(bad_draft))
    assert draft.ingredients == []


async def test_missing_api_key_raises_llm_unavailable(db_session, anagrafica, monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(LlmUnavailable):
        await draft_recipe(db_session, "x")
    get_settings.cache_clear()


async def test_un_ingrediente_ignoto_porta_la_categoria_proposta(db_session, monkeypatch):
    """Serve alla bozza per dire «lo creo io: speck, carne» invece di un campo vuoto.

    La categoria arriva nella stessa risposta: una seconda chiamata per chiederla
    costerebbe il doppio e potrebbe contraddire la prima.
    """
    from app.core.config import get_settings
    from app.services.ai_recipes import draft_recipe

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    try:
        finto = FakeLlm({
            "title": "Pasta allo speck",
            "description": "veloce",
            "instructions": "1. cuoci",
            "servings": 2,
            "ingredients": [
                {"name": "speck", "role": "primary", "quantity_text": "100 g",
                 "category": "carne"}
            ],
        })
        draft = await draft_recipe(db_session, "pasta allo speck", client=finto)
        riga = draft.ingredients[0]
        assert riga.ingredient_id is None  # l'anagrafica non ce l'ha
        assert riga.proposed_category == "carne"
    finally:
        get_settings.cache_clear()


async def test_una_categoria_inventata_non_si_propone(db_session, monkeypatch):
    """Meglio un campo da riempire che una categoria che il salvataggio rifiuterebbe."""
    from app.core.config import get_settings
    from app.services.ai_recipes import draft_recipe

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    try:
        finto = FakeLlm({
            "title": "X", "description": None, "instructions": "1. cuoci", "servings": 2,
            "ingredients": [
                {"name": "speck", "role": "primary", "quantity_text": None,
                 "category": "salumi"}
            ],
        })
        draft = await draft_recipe(db_session, "x", client=finto)
        assert draft.ingredients[0].proposed_category is None
    finally:
        get_settings.cache_clear()


async def test_ingrediente_noto_non_propone_categoria_anche_se_valida(db_session, anagrafica):
    """Se l'anagrafica ha già l'ingrediente, non proponiamo una categoria neanche se il
    modello ne ha data una valida: la categoria è già scelta da un essere umano,
    e proporla da questa schermata inviterebbe a cambiarla, il che è una violazione
    del controllo accessi. Questo test prova che il mezzo della guardia
    (match.ingredient_id is None) è indispensabile, non è mai bypassato dal mezzo
    della categoria valida."""
    draft = await draft_recipe(
        db_session,
        "pasta fredda",
        client=FakeLlm({
            "title": "Pasta fredda",
            "description": "Estate",
            "instructions": "1. cuoci",
            "servings": 2,
            "ingredients": [
                # Il modello propone "pasta" (che esiste già) con una categoria
                # completamente diversa dalla realtà ("carne" invece di "cereali").
                # Il test verifica che la categoria proposta viene ignorata perché
                # match.ingredient_id is not None.
                {"name": "pasta", "role": "primary", "quantity_text": "200 g",
                 "category": "carne"}
            ],
        })
    )
    pasta = draft.ingredients[0]
    assert pasta.ingredient_id is not None  # esiste in anagrafica
    assert pasta.matched_name == "pasta"
    assert pasta.proposed_category is None  # non si propone nulla
