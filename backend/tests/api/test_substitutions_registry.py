"""I sostituti nella scheda di un ingrediente (R5): i contesti, la voce dell'AI da
rivedere, la voce scritta a mano, le correzioni delle ricette."""

import uuid

import pytest_asyncio

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import RecipeSource
from app.domain.substitutions import SubstitutionContext, SubstitutionVerdict
from app.repositories import substitutions as repo
from app.repositories.recipes import create_recipe
from app.repositories.substitutions import Answer

SALATO = SubstitutionContext.SAVORY


@pytest_asyncio.fixture
async def burro(db_session):
    def voce(nome: str, reparto: str) -> Ingredient:
        return Ingredient(name=nome, display_name=nome.capitalize(), category=reparto)

    voci = {
        "burro": voce("burro", IngredientCategory.LATTICINI),
        "margarina": voce("margarina", IngredientCategory.CONDIMENTI),
        "detersivo": voce("detersivo", IngredientCategory.CASA),
    }
    db_session.add_all(voci.values())
    await db_session.flush()
    ricette = []
    for titolo, categoria in (("Pollo al burro", "Secondi piatti"), ("Biscotti", "Dolci"), ("Torta", "Dolci")):
        ricette.append(
            await create_recipe(
                db_session, title=titolo, description=None, instructions="Cuoci.", servings=2,
                source=RecipeSource.MANUAL, source_ref=None,
                ingredients=[(voci["burro"].id, "primary", None, None)], embedding=None,
                category=categoria,
            )
        )
    return voci, ricette


async def test_la_scheda_ha_un_contesto_per_dove_compare(db_session, logged_client, burro):
    voci, ricette = burro
    await repo.store_ai_answer(
        db_session, voci["burro"].id, SALATO,
        Answer(SubstitutionVerdict.SUBSTITUTES, ((voci["margarina"].id, "metà dose"),)),
    )
    await repo.write_override(
        db_session, ricette[1].id, voci["burro"].id, Answer(SubstitutionVerdict.OMIT)
    )

    risposta = await logged_client.get(f"/api/v1/ingredients/{voci['burro'].id}/substitutes")

    assert risposta.status_code == 200
    assert risposta.json() == {
        "ingredient_id": str(voci["burro"].id),
        "recipe_overrides": 1,
        "contexts": [
            {"context": "salato", "recipes": 1, "verdict": "substitutes", "decided_by": "ai",
             "substitutes": [{"ingredient_id": str(voci["margarina"].id), "name": "margarina", "note": "metà dose"}]},
            {"context": "dolce", "recipes": 2, "verdict": None, "decided_by": None, "substitutes": []},
        ],
    }


async def test_va_bene_cosi_fa_la_voce_scritta_a_mano(db_session, logged_client, burro):
    voci, _ = burro
    await repo.store_ai_answer(db_session, voci["burro"].id, SALATO, Answer(SubstitutionVerdict.OMIT))

    risposta = await logged_client.put(
        f"/api/v1/ingredients/{voci['burro'].id}/substitutes/salato",
        json={"verdict": "omit", "substitutes": []},
    )

    assert risposta.status_code == 200
    salato = risposta.json()["contexts"][0]
    assert (salato["context"], salato["verdict"], salato["decided_by"]) == ("salato", "omit", "human")


async def test_la_voce_dolce_si_scrive_dove_non_c_era(logged_client, burro):
    voci, _ = burro

    risposta = await logged_client.put(
        f"/api/v1/ingredients/{voci['burro'].id}/substitutes/dolce",
        json={"verdict": "substitutes", "substitutes": [{"ingredient_id": str(voci["margarina"].id), "note": None}]},
    )

    dolce = risposta.json()["contexts"][1]
    assert (dolce["context"], dolce["decided_by"], [s["name"] for s in dolce["substitutes"]]) == (
        "dolce", "human", ["margarina"],
    )


async def test_i_rifiuti(logged_client, burro):
    voci, _ = burro
    base = f"/api/v1/ingredients/{voci['burro'].id}/substitutes"

    assert (await logged_client.put(f"{base}/speziato", json={"verdict": "omit"})).status_code == 422
    se_stesso = await logged_client.put(
        f"{base}/salato",
        json={"verdict": "substitutes", "substitutes": [{"ingredient_id": str(voci["burro"].id)}]},
    )
    assert (se_stesso.status_code, se_stesso.json()["detail"]) == (
        422, "«Burro» non può sostituire sé stesso: scegli un altro ingrediente.",
    )
    detersivo = await logged_client.put(
        f"/api/v1/ingredients/{voci['detersivo'].id}/substitutes/salato", json={"verdict": "omit"}
    )
    assert (detersivo.status_code, detersivo.json()["detail"]) == (
        422, "«Detersivo» non è un alimento: non ha sostituti.",
    )
    for metodo, corpo in (("get", None), ("put", {"verdict": "omit"})):
        url = f"/api/v1/ingredients/{uuid.uuid4()}/substitutes" + ("/salato" if metodo == "put" else "")
        risposta = await getattr(logged_client, metodo)(url, **({"json": corpo} if corpo else {}))
        assert (risposta.status_code, risposta.json()["detail"]) == (404, "ingrediente inesistente")


async def test_un_non_alimentare_non_ha_contesti(logged_client, burro):
    voci, _ = burro
    corpo = (await logged_client.get(f"/api/v1/ingredients/{voci['detersivo'].id}/substitutes")).json()
    assert (corpo["contexts"], corpo["recipe_overrides"]) == ([], 0)
