import httpx
import pytest
import pytest_asyncio
from llm_fakes import FakeLlm

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.services.ai_recipes import (
    DRAFT_SCHEMA,
    SYSTEM_PROMPT,
    VARIANT_MAX_TOKENS,
    VARIANT_SYSTEM_PROMPT,
    draft_recipe,
    draft_variant,
)
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
    "cost": 1,
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


async def test_una_voce_non_alimentare_non_si_aggancia_alla_bozza(db_session, monkeypatch):
    """Finding 3 della revisione finale: senza questa guardia la riga tornerebbe
    già agganciata e `confident: true`, e `POST /recipes` la rifiuterebbe con un
    422. Meglio una riga non agganciata: l'utente la risolve dal selettore, che
    dal Task 9 offre solo cibo, o la toglie."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    try:
        db_session.add(
            Ingredient(name="carta forno", display_name="Carta forno",
                       category=IngredientCategory.CASA)
        )
        await db_session.flush()

        finto = FakeLlm({
            "title": "Torta", "description": None, "instructions": "1. cuoci",
            "servings": 2,
            "ingredients": [
                {"name": "carta forno", "role": "secondary", "quantity_text": "1 foglio",
                 "category": "casa"}
            ],
        })
        draft = await draft_recipe(db_session, "torta", client=finto)
        riga = draft.ingredients[0]
        assert riga.ingredient_id is None
        assert riga.confident is False
    finally:
        get_settings.cache_clear()


async def test_una_voce_alimentare_continua_ad_agganciarsi_alla_bozza(db_session, anagrafica):
    """Il gemello alimentare del test sopra: la guardia deve guardare il reparto,
    non spegnere l'aggancio in generale."""
    draft = await draft_recipe(db_session, "x", client=FakeLlm(DRAFT))
    pasta = next(i for i in draft.ingredients if i.raw_name == "pasta")
    assert pasta.ingredient_id is not None
    assert pasta.confident is True


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


async def test_una_bozza_chiesta_e_buttata_resta_comunque_nelle_spese(db_session):
    """La chiamata è pagata che la ricetta si salvi o no.

    Questa rotta propone e non scrive, quindi la sua sessione non la committa nessuno:
    senza una commit esplicita la riga della spesa sparirebbe. Ed è proprio il consumo
    più facile da fare per sbaglio — dieci bozze chieste e nessuna tenuta — cioè quello
    che una torta delle spese esiste per mostrare.
    """
    from sqlalchemy import select

    from app.db.models.llm_call import LlmCall
    from app.services.llm import LlmCallSite
    from llm_fakes import COSTO_FINTO, FakeLlm

    finto = FakeLlm({
        "title": "Pasta al pomodoro", "description": None, "instructions": "Cuoci.",
        "servings": 2, "ingredients": [],
    })
    await draft_recipe(db_session, "pasta veloce", client=finto)

    # Prima di qualunque interrogazione: una `select` farebbe scattare l'autoflush e
    # renderebbe visibile anche una riga solo aggiunta e mai committata — cioè una
    # riga che in produzione andrebbe persa, perché questa rotta non salva e nessuno
    # committa la sua sessione. `session.new` vuoto è la prova che l'unità di lavoro
    # è stata chiusa e non soltanto preparata. Misurato: senza questa riga, togliere
    # la commit dal codice lascia il test verde.
    assert not db_session.new, "la spesa è solo in sospeso: senza commit andrebbe persa"

    riga = (await db_session.execute(select(LlmCall))).scalar_one()
    assert riga.call_site == LlmCallSite.RECIPE_DRAFT
    assert riga.ok is True
    assert riga.cost_usd == pytest.approx(COSTO_FINTO)


async def test_un_modello_giu_durante_la_stesura_e_spesa_registrata_come_fallita(db_session):
    """Un guasto va nello storico, altrimenti i giri che pagano e non concludono sono
    invisibili proprio nello strumento che dovrebbe scoprirli."""
    from sqlalchemy import select

    from app.db.models.llm_call import LlmCall
    from llm_fakes import FakeLlm

    finto = FakeLlm(httpx.ReadTimeout("troppo lento"))
    with pytest.raises(LlmUnavailable):
        await draft_recipe(db_session, "pasta veloce", client=finto)

    assert not db_session.new, "la spesa è solo in sospeso: senza commit andrebbe persa"

    riga = (await db_session.execute(select(LlmCall))).scalar_one()
    assert riga.ok is False
    assert riga.cost_usd is None


async def test_la_bozza_propone_un_costo(db_session, anagrafica):
    draft = await draft_recipe(db_session, "qualcosa di veloce", client=FakeLlm(DRAFT))
    assert draft.cost == 1


@pytest.mark.parametrize("cost", [0, 7, "3", 2.5, True, None])
async def test_un_costo_fuori_scala_diventa_nessun_costo(db_session, anagrafica, cost):
    """Un campo vuoto nel modulo è meglio di un gradino inventato o arrotondato."""
    draft = await draft_recipe(
        db_session, "qualcosa di veloce", client=FakeLlm({**DRAFT, "cost": cost})
    )
    assert draft.cost is None


async def test_una_risposta_senza_costo_resta_una_bozza(db_session, anagrafica):
    senza = {k: v for k, v in DRAFT.items() if k != "cost"}
    draft = await draft_recipe(db_session, "qualcosa di veloce", client=FakeLlm(senza))
    assert draft.cost is None
    assert draft.title == "Pasta al pomodoro"


def test_lo_schema_chiede_il_costo():
    from app.services.ai_recipes import DRAFT_SCHEMA, SYSTEM_PROMPT

    assert "cost" in DRAFT_SCHEMA["required"]
    assert DRAFT_SCHEMA["properties"]["cost"] == {"type": ["integer", "null"]}
    assert '"cost"' in SYSTEM_PROMPT


# ---- R8: la variante di una ricetta che esiste ----

VARIANTE = {
    "title": "Pasta al pomodoro senza basilico",
    "description": "Di sempre, senza erbe",
    "instructions": "1. Cuoci la pasta.\n2. Scalda il sugo con un pizzico di zucchero.",
    "servings": 2,
    "cost": 1,
    "ingredients": [
        {"name": "pasta", "role": "primary", "quantity_text": "180 g", "category": "cereali"},
        {"name": "pomodoro", "role": "primary", "quantity_text": "350 g", "category": "verdura"},
        {"name": "zucchero", "role": "secondary", "quantity_text": "1 pizzico", "category": "dolci"},
    ],
}


@pytest_asyncio.fixture
async def originale(db_session, anagrafica):
    from sqlalchemy import select

    from app.db.models.recipe import RecipeSource
    from app.repositories.recipes import create_recipe, get_recipe

    ids = {i.name: i.id for i in (await db_session.execute(select(Ingredient))).scalars()}
    ricetta = await create_recipe(
        db_session, title="Pasta al pomodoro", description="Di sempre",
        instructions="1. Cuoci la pasta.\n2. Scalda il sugo.", servings=2,
        source=RecipeSource.MANUAL, source_ref=None,
        ingredients=[
            (ids["pasta"], "primary", "180 g", None),
            (ids["pomodoro"], "primary", "300 g", None),
            (ids["basilico"], "secondary", "q.b.", None),
        ],
        embedding=None, cost=1,
    )
    return await get_recipe(db_session, ricetta.id)


async def test_la_variante_manda_all_ai_la_ricetta_e_la_richiesta(db_session, originale):
    """La domanda è la ricetta com'è salvata, coi nomi canonici dell'anagrafica — così le
    righe che la variante tiene si riagganciano con certezza — e la richiesta."""
    import json

    finto = FakeLlm(VARIANTE)
    await draft_variant(db_session, originale, "senza basilico", client=finto)

    corpo = finto.bodies[0]
    assert corpo["messages"][0]["content"] == VARIANT_SYSTEM_PROMPT
    # le regole della bozza valgono anche qui: la variante le estende, non le riscrive
    assert VARIANT_SYSTEM_PROMPT.startswith(SYSTEM_PROMPT)
    assert corpo["max_tokens"] == VARIANT_MAX_TOKENS == 4000
    # lo schema è quello della bozza: il modulo legge la stessa forma
    assert corpo["response_format"]["json_schema"]["schema"] == DRAFT_SCHEMA
    domanda = json.loads(corpo["messages"][1]["content"])
    assert domanda["richiesta"] == "senza basilico"
    ricetta = domanda["ricetta"]
    assert ricetta["title"] == "Pasta al pomodoro"
    assert ricetta["description"] == "Di sempre"
    assert ricetta["instructions"] == "1. Cuoci la pasta.\n2. Scalda il sugo."
    assert ricetta["servings"] == 2
    assert ricetta["cost"] == 1
    assert sorted(
        (r["name"], r["role"], r["quantity_text"], r["category"]) for r in ricetta["ingredients"]
    ) == [
        ("basilico", "secondary", "q.b.", "spezie"),
        ("pasta", "primary", "180 g", "cereali"),
        ("pomodoro", "primary", "300 g", "verdura"),
    ]


async def test_le_righe_tenute_si_riagganciano_e_le_nuove_si_propongono(db_session, originale):
    draft = await draft_variant(db_session, originale, "senza basilico", client=FakeLlm(VARIANTE))

    assert draft.title == "Pasta al pomodoro senza basilico"
    assert draft.cost == 1
    righe = {i.raw_name: i for i in draft.ingredients}
    assert righe["pasta"].ingredient_id is not None
    assert righe["pasta"].confident is True
    assert righe["pomodoro"].quantity_text == "350 g"
    # uno nuovo che l'anagrafica non ha: si propone col reparto, «da creare salvando»
    assert righe["zucchero"].ingredient_id is None
    assert righe["zucchero"].proposed_category == "dolci"


async def test_la_variante_non_introduce_un_non_alimentare(db_session, originale):
    """Né agganciato (la carta forno c'è, ma è di casa) né da creare (il detersivo non
    c'è, e il suo reparto non è del cibo): tutti e due tornano senza aggancio e senza
    reparto, cioè «non in anagrafica, sarà escluso», e non partono salvando."""
    db_session.add(
        Ingredient(name="carta forno", display_name="Carta forno", category=IngredientCategory.CASA)
    )
    await db_session.flush()
    risposta = {**VARIANTE, "ingredients": [
        *VARIANTE["ingredients"],
        {"name": "carta forno", "role": "secondary", "quantity_text": "1 foglio", "category": "casa"},
        {"name": "detersivo per piatti", "role": "secondary", "quantity_text": "1 goccia",
         "category": "casa"},
    ]}

    draft = await draft_variant(db_session, originale, "in forno", client=FakeLlm(risposta))

    righe = {i.raw_name: i for i in draft.ingredients}
    for nome in ("carta forno", "detersivo per piatti"):
        assert righe[nome].ingredient_id is None, nome
        assert righe[nome].proposed_category is None, nome


async def test_la_spesa_della_variante_ha_la_sua_sezione(db_session, originale):
    from sqlalchemy import select

    from app.db.models.llm_call import LlmCall
    from app.services.llm import LlmCallSite
    from llm_fakes import COSTO_FINTO

    await draft_variant(db_session, originale, "senza basilico", client=FakeLlm(VARIANTE))

    # committata: una variante chiesta e buttata è pagata lo stesso (vedi `_record_spend`)
    assert not db_session.new, "la spesa è solo in sospeso: senza commit andrebbe persa"
    riga = (await db_session.execute(select(LlmCall))).scalar_one()
    assert riga.call_site == LlmCallSite.RECIPE_VARIANT == "recipe_variant"
    assert riga.ok is True
    assert riga.cost_usd == pytest.approx(COSTO_FINTO)


async def test_un_modello_giu_durante_la_variante_e_spesa_fallita(db_session, originale):
    from sqlalchemy import select

    from app.db.models.llm_call import LlmCall
    from app.services.llm import LlmCallSite

    with pytest.raises(LlmUnavailable):
        await draft_variant(
            db_session, originale, "senza basilico",
            client=FakeLlm(httpx.ReadTimeout("troppo lento")),
        )

    assert not db_session.new, "la spesa è solo in sospeso: senza commit andrebbe persa"
    riga = (await db_session.execute(select(LlmCall))).scalar_one()
    assert riga.call_site == LlmCallSite.RECIPE_VARIANT
    assert riga.ok is False
    assert riga.cost_usd is None
