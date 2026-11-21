"""«Sostituisci» nella ricetta (R5): la risposta di una riga, chiesta, corretta, tolta.

Per una riga vale la correzione della ricetta, se c'è, poi la voce generale del contesto
della ricetta. Ogni sostituto porta la sua disponibilità e se, in dispensa, soddisfa la
stessa regola della riga (`satisfied`, la metà della regola di R6 che R5 già calcola).
"""

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.llm_call import LlmCall
from app.db.models.pantry import PantryItem
from app.db.models.recipe import RecipeSource
from app.domain.substitutions import SubstitutionContext, SubstitutionVerdict
from app.repositories import substitutions as repo
from app.repositories.recipes import create_recipe
from app.repositories.substitutions import Answer
from llm_fakes import FakeLlm

SALATO = SubstitutionContext.SAVORY
DOLCE = SubstitutionContext.SWEET


@pytest.fixture
def con_chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def cucina(db_session):
    def voce(nome: str, reparto: str) -> Ingredient:
        return Ingredient(name=nome, display_name=nome.capitalize(), category=reparto)

    voci = {
        nome: voce(nome, IngredientCategory.CEREALI) for nome in ("pasta", "riso", "farro", "orzo")
    }
    db_session.add_all(voci.values())
    await db_session.flush()
    db_session.add_all([
        PantryItem(ingredient_id=voci["riso"].id, status="available"),
        PantryItem(ingredient_id=voci["farro"].id, status="low"),
    ])

    async def ricetta(titolo: str, ruolo: str):
        return await create_recipe(
            db_session, title=titolo, description=None, instructions="Cuoci.", servings=2,
            source=RecipeSource.MANUAL, source_ref=None,
            # senza categoria: una ricetta salata (Review Focus 5)
            ingredients=[(voci["pasta"].id, ruolo, "180 g", None)], embedding=None,
        )

    ricette = {
        "pasta": await ricetta("Pasta al pomodoro", "primary"),
        "minestra": await ricetta("Minestra", "secondary"),
    }
    return voci, ricette


def _url(ricetta, voce, coda: str = "") -> str:
    return f"/api/v1/recipes/{ricetta.id}/substitutes/{voce.id}{coda}"


async def test_senza_risposta_la_riga_lo_dice(logged_client, cucina):
    voci, ricette = cucina

    risposta = await logged_client.get(_url(ricette["pasta"], voci["pasta"]))

    assert risposta.status_code == 200
    assert risposta.json() == {
        "ingredient_id": str(voci["pasta"].id), "ingredient_name": "pasta", "context": "salato",
        "scope": None, "verdict": None, "decided_by": None, "substitutes": [], "ai_failed": False,
    }


async def test_la_voce_generale_dice_cosa_c_e_in_dispensa_secondo_la_riga(
    db_session, logged_client, cucina
):
    voci, ricette = cucina
    await repo.store_ai_answer(
        db_session, voci["pasta"].id, SALATO,
        Answer(SubstitutionVerdict.SUBSTITUTES, ((voci["riso"].id, "cottura più lunga"), (voci["farro"].id, None))),
    )

    principale = (await logged_client.get(_url(ricette["pasta"], voci["pasta"]))).json()
    secondaria = (await logged_client.get(_url(ricette["minestra"], voci["pasta"]))).json()

    assert (principale["scope"], principale["verdict"], principale["decided_by"]) == (
        "general", "substitutes", "ai",
    )
    assert principale["substitutes"] == [
        {"ingredient_id": str(voci["riso"].id), "name": "riso", "note": "cottura più lunga",
         "availability": "available", "satisfied": True},
        # quasi finito non basta a una riga principale…
        {"ingredient_id": str(voci["farro"].id), "name": "farro", "note": None,
         "availability": "low", "satisfied": False},
    ]
    # …e basta a una secondaria
    assert secondaria["substitutes"][1]["satisfied"] is True


async def test_la_correzione_della_ricetta_vince_sulla_voce_generale(db_session, logged_client, cucina):
    voci, ricette = cucina
    await repo.store_ai_answer(db_session, voci["pasta"].id, SALATO, Answer(SubstitutionVerdict.OMIT))
    await repo.write_override(
        db_session, ricette["pasta"].id, voci["pasta"].id, Answer(SubstitutionVerdict.IRREPLACEABLE)
    )

    corpo = (await logged_client.get(_url(ricette["pasta"], voci["pasta"]))).json()

    assert (corpo["scope"], corpo["verdict"], corpo["decided_by"]) == ("recipe", "irreplaceable", "human")
    altra = (await logged_client.get(_url(ricette["minestra"], voci["pasta"]))).json()
    assert (altra["scope"], altra["verdict"]) == ("general", "omit")


async def test_una_ricetta_che_diventa_dolce_legge_la_voce_dolce(db_session, logged_client, cucina):
    """Review Focus 1: cambiata la categoria con «Modifica», la voce è l'altra."""
    voci, ricette = cucina
    await repo.write_general(db_session, voci["pasta"].id, SALATO, Answer(SubstitutionVerdict.OMIT))
    await repo.write_general(
        db_session, voci["pasta"].id, DOLCE, Answer(SubstitutionVerdict.IRREPLACEABLE)
    )
    assert (await logged_client.get(_url(ricette["pasta"], voci["pasta"]))).json()["verdict"] == "omit"

    ricette["pasta"].category = "Dolci e Desserts"
    await db_session.flush()

    corpo = (await logged_client.get(_url(ricette["pasta"], voci["pasta"]))).json()
    assert (corpo["context"], corpo["verdict"]) == ("dolce", "irreplaceable")


async def test_una_ricetta_o_una_riga_che_non_ci_sono(logged_client, cucina):
    voci, ricette = cucina
    import uuid

    nessuna = await logged_client.get(f"/api/v1/recipes/{uuid.uuid4()}/substitutes/{voci['pasta'].id}")
    assert (nessuna.status_code, nessuna.json()["detail"]) == (404, "ricetta inesistente")
    fuori = await logged_client.get(_url(ricette["pasta"], voci["riso"]))
    assert (fuori.status_code, fuori.json()["detail"]) == (404, "Questo ingrediente non è nella ricetta.")


async def test_ask_salva_la_risposta_dell_ai(db_session, logged_client, cucina, con_chiave, monkeypatch):
    voci, ricette = cucina
    finto = FakeLlm({"esito": "sostituti", "sostituti": [{"nome": "riso", "nota": ""}]})
    monkeypatch.setattr("app.services.substitutions.open_client", lambda: finto)

    corpo = (await logged_client.post(_url(ricette["pasta"], voci["pasta"], "/ask"))).json()

    assert (corpo["scope"], corpo["verdict"], corpo["decided_by"], corpo["ai_failed"]) == (
        "general", "substitutes", "ai", False,
    )
    assert [s["name"] for s in corpo["substitutes"]] == ["riso"]
    assert len(finto.bodies) == 1
    chiamate = (await db_session.execute(select(LlmCall.call_site))).scalars().all()
    assert chiamate == ["ingredient_substitutes"]


async def test_ask_senza_ai_lascia_la_strada_a_mano(db_session, logged_client, cucina, monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    voci, ricette = cucina

    risposta = await logged_client.post(_url(ricette["pasta"], voci["pasta"], "/ask"))

    assert risposta.status_code == 200
    assert (risposta.json()["verdict"], risposta.json()["ai_failed"]) == (None, True)
    get_settings.cache_clear()


async def test_ask_con_una_risposta_non_chiama(db_session, logged_client, cucina, con_chiave, monkeypatch):
    voci, ricette = cucina
    await repo.store_ai_answer(db_session, voci["pasta"].id, SALATO, Answer(SubstitutionVerdict.OMIT))
    finto = FakeLlm()
    monkeypatch.setattr("app.services.substitutions.open_client", lambda: finto)

    corpo = (await logged_client.post(_url(ricette["pasta"], voci["pasta"], "/ask"))).json()

    assert (corpo["verdict"], corpo["ai_failed"]) == ("omit", False)
    assert finto.bodies == []


async def test_ask_richiede_una_voce_rimasta_senza_sostituti(
    db_session, logged_client, cucina, con_chiave, monkeypatch
):
    """Review Focus 2: l'unico sostituto è stato cancellato (un annullamento della coda)."""
    voci, ricette = cucina
    await repo.store_ai_answer(
        db_session, voci["pasta"].id, SALATO,
        Answer(SubstitutionVerdict.SUBSTITUTES, ((voci["orzo"].id, None),)),
    )
    await db_session.execute(delete(Ingredient).where(Ingredient.id == voci["orzo"].id))
    assert (await logged_client.get(_url(ricette["pasta"], voci["pasta"]))).json()["verdict"] is None

    monkeypatch.setattr(
        "app.services.substitutions.open_client",
        lambda: FakeLlm({"esito": "sostituti", "sostituti": [{"nome": "riso", "nota": ""}]}),
    )
    corpo = (await logged_client.post(_url(ricette["pasta"], voci["pasta"], "/ask"))).json()
    assert [s["name"] for s in corpo["substitutes"]] == ["riso"]


async def test_put_scrive_la_correzione_della_sola_ricetta(db_session, logged_client, cucina):
    voci, ricette = cucina

    risposta = await logged_client.put(
        _url(ricette["pasta"], voci["pasta"]),
        json={"verdict": "substitutes", "substitutes": [{"ingredient_id": str(voci["riso"].id), "note": " metà  dose "}]},
    )

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert (corpo["scope"], corpo["decided_by"]) == ("recipe", "human")
    assert corpo["substitutes"][0]["note"] == "metà dose"
    assert await repo.general_row(db_session, voci["pasta"].id, SALATO) is None


async def test_put_rifiuta_con_la_frase(logged_client, cucina):
    voci, ricette = cucina

    se_stesso = await logged_client.put(
        _url(ricette["pasta"], voci["pasta"]),
        json={"verdict": "substitutes", "substitutes": [{"ingredient_id": str(voci["pasta"].id)}]},
    )
    assert se_stesso.status_code == 422
    assert se_stesso.json()["detail"] == "«Pasta» non può sostituire sé stesso: scegli un altro ingrediente."
    sconosciuto = await logged_client.put(_url(ricette["pasta"], voci["pasta"]), json={"verdict": "forse"})
    assert sconosciuto.status_code == 422


async def test_delete_toglie_la_correzione_e_torna_la_generale(db_session, logged_client, cucina):
    voci, ricette = cucina
    await repo.write_general(db_session, voci["pasta"].id, SALATO, Answer(SubstitutionVerdict.OMIT))
    await repo.write_override(
        db_session, ricette["pasta"].id, voci["pasta"].id, Answer(SubstitutionVerdict.IRREPLACEABLE)
    )

    assert (await logged_client.delete(_url(ricette["pasta"], voci["pasta"]))).status_code == 204
    corpo = (await logged_client.get(_url(ricette["pasta"], voci["pasta"]))).json()
    assert (corpo["scope"], corpo["verdict"]) == ("general", "omit")
    # togliere quel che non c'è non è un errore
    assert (await logged_client.delete(_url(ricette["pasta"], voci["pasta"]))).status_code == 204
