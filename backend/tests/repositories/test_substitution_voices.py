"""Le voci di «Sostituisci» (R5): un ingrediente per ogni contesto in cui compare.

La doppia voce solo dove serve (decisione 1 di Mattia): il burro dei biscotti e quello
del pollo al burro sono due voci, lo zucchero dei biscotti una sola. Le ricette eliminate
non contano.
"""

from datetime import UTC, datetime

import pytest_asyncio
from sqlalchemy import delete

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import RecipeSource
from app.domain.substitutions import SubstitutionContext, SubstitutionVerdict
from app.repositories import substitutions as repo
from app.repositories.recipes import create_recipe
from app.repositories.substitutions import Answer

SALATO = SubstitutionContext.SAVORY
DOLCE = SubstitutionContext.SWEET


@pytest_asyncio.fixture
async def cucina(db_session):
    def voce(nome: str, reparto: str) -> Ingredient:
        return Ingredient(name=nome, display_name=nome.capitalize(), category=reparto)

    voci = {
        "pollo": voce("pollo", IngredientCategory.CARNE),
        "burro": voce("burro", IngredientCategory.LATTICINI),
        "zucchero": voce("zucchero", IngredientCategory.DOLCI),
        "miele": voce("miele", IngredientCategory.DOLCI),
    }
    db_session.add_all(voci.values())
    await db_session.flush()

    async def ricetta(titolo: str, categoria: str | None, *nomi: str):
        return await create_recipe(
            db_session, title=titolo, description=None, instructions="Cuoci.", servings=2,
            source=RecipeSource.MANUAL, source_ref=None,
            ingredients=[(voci[nome].id, "primary", None, None) for nome in nomi],
            embedding=None, category=categoria,
        )

    ricette = {
        "pollo al burro": await ricetta("Pollo al burro", "Secondi piatti", "pollo", "burro"),
        "biscotti": await ricetta("Biscotti", "Dolci e Desserts", "burro", "zucchero"),
        "torta": await ricetta("Torta", "Dolci", "burro", "zucchero"),
        # senza categoria è salata (Review Focus 5)
        "pollo lesso": await ricetta("Pollo lesso", None, "pollo"),
    }
    vecchia = await ricetta("Pollo vecchio", "Secondi piatti", "pollo")
    vecchia.archived_at = datetime.now(UTC)
    await db_session.flush()
    return voci, ricette


def _voci(elenco) -> list[tuple[str, str, int]]:
    return [(voce.name, voce.context.value, voce.recipes) for voce in elenco]


async def test_una_voce_per_ogni_contesto_in_cui_compare_dalla_piu_usata(db_session, cucina):
    assert _voci(await repo.pending_voices(db_session)) == [
        ("burro", "dolce", 2),
        ("pollo", "salato", 2),  # la ricetta eliminata non conta
        ("zucchero", "dolce", 2),
        ("burro", "salato", 1),
    ]


async def test_una_voce_con_una_risposta_non_manca_piu(db_session, cucina):
    voci, _ = cucina
    await repo.write_general(db_session, voci["pollo"].id, SALATO, Answer(SubstitutionVerdict.OMIT))
    await repo.store_ai_answer(
        db_session, voci["burro"].id, DOLCE, Answer(SubstitutionVerdict.IRREPLACEABLE)
    )
    assert _voci(await repo.pending_voices(db_session)) == [
        ("zucchero", "dolce", 2),
        ("burro", "salato", 1),
    ]


async def test_una_voce_rimasta_senza_sostituti_torna_a_mancare(db_session, cucina):
    voci, _ = cucina
    await repo.store_ai_answer(
        db_session, voci["burro"].id, DOLCE,
        Answer(SubstitutionVerdict.SUBSTITUTES, ((voci["miele"].id, None),)),
    )
    assert ("burro", "dolce", 2) not in _voci(await repo.pending_voices(db_session))

    await db_session.execute(delete(Ingredient).where(Ingredient.id == voci["miele"].id))
    assert ("burro", "dolce", 2) in _voci(await repo.pending_voices(db_session))


async def test_la_scheda_di_un_ingrediente_ha_i_suoi_contesti(db_session, cucina):
    voci, ricette = cucina
    burro = voci["burro"].id
    await repo.write_general(db_session, burro, DOLCE, Answer(SubstitutionVerdict.OMIT))
    await repo.write_override(
        db_session, ricette["pollo al burro"].id, burro, Answer(SubstitutionVerdict.IRREPLACEABLE)
    )

    scheda = await repo.ingredient_view(db_session, burro)

    assert [(c.context.value, c.recipes) for c in scheda.contexts] == [("salato", 1), ("dolce", 2)]
    assert scheda.contexts[0].row is None
    assert scheda.contexts[1].row is not None and scheda.contexts[1].row.verdict == "omit"
    assert scheda.recipe_overrides == 1


async def test_una_voce_senza_ricette_resta_nella_scheda(db_session, cucina):
    """La voce dolce del pollo, scritta a mano, anche se nessun dolce usa il pollo."""
    voci, _ = cucina
    pollo = voci["pollo"].id
    await repo.write_general(db_session, pollo, DOLCE, Answer(SubstitutionVerdict.IRREPLACEABLE))

    scheda = await repo.ingredient_view(db_session, pollo)
    assert [(c.context.value, c.recipes) for c in scheda.contexts] == [("salato", 2), ("dolce", 0)]


async def test_un_ingrediente_in_nessuna_ricetta_non_ha_contesti(db_session, cucina):
    voci, _ = cucina
    scheda = await repo.ingredient_view(db_session, voci["miele"].id)
    assert scheda.contexts == () and scheda.recipe_overrides == 0
