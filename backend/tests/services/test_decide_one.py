"""Una domanda sola al modello, e la verifica della sua risposta.

La verifica è la parte che conta: da qui passa la differenza fra «il modello può
sbagliare» e «il modello può scrivere spazzatura». Una risposta non verificabile non
diventa una proposta — torna `None`, e il termine resta in coda.
"""

import json

import pytest
import pytest_asyncio

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.repositories.ingredients import create_ingredient
from app.services.llm import LlmUnavailable
from app.services.recipe_import.decide import decide_one, load_registry
from llm_fakes import FakeLlm


@pytest.fixture(autouse=True)
def chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def anagrafica(db_session):
    await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    return await load_registry(db_session)


def termine(nome: str, chiave: str) -> ImportTerm:
    return ImportTerm(
        source=GIALLOZAFFERANO, term_key=chiave, display_name=nome,
        occurrences=3, decision=TermDecision.PENDING,
    )


async def test_map_verso_un_ingrediente_esistente(db_session, anagrafica):
    term = termine("Rigatoni", "ricette-con-i-Rigatoni")
    db_session.add(term)
    await db_session.flush()

    finto = FakeLlm({"action": "map", "ingredient": "pasta", "name": None,
                     "display_name": None, "category": None})
    proposta = await decide_one(db_session, term, anagrafica, client=finto)

    assert proposta is not None
    assert proposta.action == "map"
    assert proposta.ingredient_id == anagrafica.by_name["pasta"]
    # il nome canonico viaggia con la proposta: è la sola fonte di un testo leggibile
    # che la revisione può mostrare senza fidarsi di un id cieco
    assert proposta.name == "pasta"


async def test_create_con_categoria_valida(db_session, anagrafica):
    term = termine("Speck", "ricette-con-lo-Speck")
    db_session.add(term)
    await db_session.flush()

    finto = FakeLlm({"action": "create", "ingredient": None, "name": "speck",
                     "display_name": "Speck", "category": "carne"})
    proposta = await decide_one(db_session, term, anagrafica, client=finto)

    assert proposta is not None
    assert (proposta.action, proposta.name, proposta.category) == ("create", "speck", "carne")


async def test_ignore(db_session, anagrafica):
    term = termine("Acqua", "ricette-con-Acqua")
    db_session.add(term)
    await db_session.flush()

    finto = FakeLlm({"action": "ignore", "ingredient": None, "name": None,
                     "display_name": None, "category": None})
    proposta = await decide_one(db_session, term, anagrafica, client=finto)
    assert proposta is not None and proposta.action == "ignore"


async def test_un_map_verso_un_ingrediente_inesistente_non_e_una_proposta(db_session, anagrafica):
    term = termine("Rigatoni", "ricette-con-i-Rigatoni")
    db_session.add(term)
    await db_session.flush()

    finto = FakeLlm({"action": "map", "ingredient": "pasta integrale di kamut",
                     "name": None, "display_name": None, "category": None})
    assert await decide_one(db_session, term, anagrafica, client=finto) is None


async def test_una_categoria_inventata_non_e_una_proposta(db_session, anagrafica):
    term = termine("Speck", "ricette-con-lo-Speck")
    db_session.add(term)
    await db_session.flush()

    finto = FakeLlm({"action": "create", "ingredient": None, "name": "speck",
                     "display_name": "Speck", "category": "salumi"})
    assert await decide_one(db_session, term, anagrafica, client=finto) is None


async def test_un_create_di_un_nome_che_esiste_diventa_un_map(db_session, anagrafica):
    """Lo stesso caso che per `map` si scarterebbe, e qui si converte.

    Un `create` di «pasta» non si può applicare: il 409 lo rifiuterebbe a ogni tocco.
    Ma l'ingrediente esiste, quindi la carta verificata non è il `create` sbagliato: è
    il `map` che il modello avrebbe dovuto scegliere, e id e nome li abbiamo già dalla
    stessa ricerca che verifica un `map` vero.
    """
    term = termine("Rigatoni", "ricette-con-i-Rigatoni")
    db_session.add(term)
    await db_session.flush()

    finto = FakeLlm({"action": "create", "ingredient": None, "name": "pasta",
                     "display_name": "Pasta", "category": "cereali"})
    proposta = await decide_one(db_session, term, anagrafica, client=finto)

    assert proposta is not None
    assert proposta.action == "map"
    assert proposta.ingredient_id == anagrafica.by_name["pasta"]


async def test_unazione_sconosciuta_non_e_una_proposta(db_session, anagrafica):
    term = termine("Speck", "ricette-con-lo-Speck")
    db_session.add(term)
    await db_session.flush()

    finto = FakeLlm({"action": "forse", "ingredient": None, "name": None,
                     "display_name": None, "category": None})
    assert await decide_one(db_session, term, anagrafica, client=finto) is None


async def test_un_guasto_del_modello_risale(db_session, anagrafica):
    """`decide_one` non inghiotte `LlmUnavailable`: chi orchestra decide cosa farne.

    Il fan-out la cattura per termine (un guasto lascia in coda solo il suo termine);
    il CLI la cattura per il lotto. Inghiottirla qui renderebbe indistinguibile «il
    modello è giù» da «il modello ha risposto una cosa inutilizzabile».
    """
    term = termine("Speck", "ricette-con-lo-Speck")
    db_session.add(term)
    await db_session.flush()

    import httpx

    finto = FakeLlm(httpx.ReadTimeout("lento"))
    with pytest.raises(LlmUnavailable):
        await decide_one(db_session, term, anagrafica, client=finto)


async def test_la_domanda_porta_il_termine_lanagrafica_e_le_categorie(db_session, anagrafica):
    term = termine("Rigatoni", "ricette-con-i-Rigatoni")
    db_session.add(term)
    await db_session.flush()

    finto = FakeLlm({"action": "ignore", "ingredient": None, "name": None,
                     "display_name": None, "category": None})
    await decide_one(db_session, term, anagrafica, client=finto)

    corpo = finto.bodies[0]
    domanda = json.loads(corpo["messages"][1]["content"])
    assert domanda["termine"] == "Rigatoni"
    assert {"nome": "pasta", "categoria": "cereali"} in domanda["anagrafica"]
    assert "carne" in domanda["categorie"]
    # una domanda sola, non un array: è la scelta di §4.2 della spec
    assert isinstance(domanda["termine"], str)
