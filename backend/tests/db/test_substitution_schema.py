"""I vincoli delle risposte di «Sostituisci» (R5), nel database.

Le regole che contano stanno nello schema e non solo nel codice che scrive: una voce
generale per ingrediente e contesto, una correzione per ricetta e ingrediente, una
correzione sempre scritta a mano, un sostituto una volta sola per risposta. Alembic non
confronta i predicati degli indici parziali (vedi `test_metadata_matches_migrations.py`):
per questo qui si provano col comportamento, inserendo i doppioni.
"""

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError

from app.core.db import Base
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import Recipe, RecipeSource
from app.db.models.substitution import IngredientSubstitution, SubstitutionOption
from app.repositories.recipes import create_recipe

INDICI = {"uq_substitution_general", "uq_substitution_recipe", "ix_substitution_options_substitute"}


@pytest_asyncio.fixture
async def voci(db_session):
    tutte = {
        nome: Ingredient(name=nome, display_name=nome.capitalize(), category=IngredientCategory.CARNE)
        for nome in ("pollo", "tacchino", "coniglio")
    }
    db_session.add_all(tutte.values())
    await db_session.flush()
    return tutte


async def _ricetta(db_session, titolo: str) -> Recipe:
    return await create_recipe(
        db_session, title=titolo, description=None, instructions="Cuoci.", servings=2,
        source=RecipeSource.MANUAL, source_ref=None, ingredients=[], embedding=None,
    )


async def _rifiutata(db_session, *righe) -> None:
    """Le righe, in un SAVEPOINT suo: il rifiuto non lascia la sessione rotta."""
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add_all(righe)
            await db_session.flush()


async def _accettata(db_session, *righe) -> None:
    async with db_session.begin_nested():
        db_session.add_all(righe)
        await db_session.flush()


def _generale(voce, contesto="salato", **altro) -> IngredientSubstitution:
    return IngredientSubstitution(
        ingredient_id=voce.id, context=contesto, verdict=altro.get("verdict", "omit"),
        decided_by=altro.get("decided_by", "ai"),
    )


def _correzione(voce, ricetta, **altro) -> IngredientSubstitution:
    return IngredientSubstitution(
        ingredient_id=voce.id, recipe_id=ricetta.id, verdict=altro.get("verdict", "omit"),
        decided_by=altro.get("decided_by", "human"),
    )


async def test_una_voce_generale_per_ingrediente_e_contesto(db_session, voci):
    await _accettata(db_session, _generale(voci["pollo"], "salato"))
    await _rifiutata(db_session, _generale(voci["pollo"], "salato", decided_by="human"))
    # l'altro contesto, e la correzione di una ricetta, stanno accanto
    ricetta = await _ricetta(db_session, "Pollo arrosto")
    await _accettata(db_session, _generale(voci["pollo"], "dolce"))
    await _accettata(db_session, _correzione(voci["pollo"], ricetta))


async def test_una_correzione_per_ricetta_e_ingrediente(db_session, voci):
    prima = await _ricetta(db_session, "Pollo arrosto")
    seconda = await _ricetta(db_session, "Pollo al curry")
    await _accettata(db_session, _correzione(voci["pollo"], prima))
    await _rifiutata(db_session, _correzione(voci["pollo"], prima, verdict="irreplaceable"))
    await _accettata(db_session, _correzione(voci["pollo"], seconda))


async def test_una_riga_e_o_generale_o_di_una_ricetta(db_session, voci):
    ricetta = await _ricetta(db_session, "Pollo arrosto")
    entrambi = IngredientSubstitution(
        ingredient_id=voci["pollo"].id, context="salato", recipe_id=ricetta.id,
        verdict="omit", decided_by="human",
    )
    nessuno = IngredientSubstitution(ingredient_id=voci["pollo"].id, verdict="omit", decided_by="human")
    await _rifiutata(db_session, entrambi)
    await _rifiutata(db_session, nessuno)


async def test_una_correzione_di_ricetta_e_sempre_a_mano(db_session, voci):
    ricetta = await _ricetta(db_session, "Pollo arrosto")
    await _rifiutata(db_session, _correzione(voci["pollo"], ricetta, decided_by="ai"))


async def test_esiti_contesti_e_autori_sono_quelli_del_dominio(db_session, voci):
    await _rifiutata(db_session, _generale(voci["pollo"], "salato", verdict="forse"))
    await _rifiutata(db_session, _generale(voci["pollo"], "speziato"))
    await _rifiutata(db_session, _generale(voci["pollo"], "salato", decided_by="auto"))


async def test_un_sostituto_una_volta_sola_per_risposta(db_session, voci):
    risposta = _generale(voci["pollo"], verdict="substitutes")
    await _accettata(db_session, risposta)
    await _accettata(
        db_session,
        SubstitutionOption(substitution_id=risposta.id, substitute_id=voci["tacchino"].id, position=0),
    )
    await _rifiutata(
        db_session,
        SubstitutionOption(substitution_id=risposta.id, substitute_id=voci["tacchino"].id, position=1),
    )


async def test_un_ingrediente_o_una_ricetta_che_spariscono_si_portano_via_le_loro_righe(
    db_session, voci
):
    ricetta = await _ricetta(db_session, "Pollo arrosto")
    risposta = _generale(voci["pollo"], verdict="substitutes")
    correzione = _correzione(voci["coniglio"], ricetta)
    await _accettata(db_session, risposta, correzione)
    await _accettata(
        db_session,
        SubstitutionOption(substitution_id=risposta.id, substitute_id=voci["tacchino"].id, position=0),
    )

    await db_session.execute(delete(Ingredient).where(Ingredient.id == voci["tacchino"].id))
    await db_session.execute(delete(Recipe).where(Recipe.id == ricetta.id))

    sostituti = (await db_session.execute(select(SubstitutionOption.id))).all()
    righe = (await db_session.execute(select(IngredientSubstitution.id))).scalars().all()
    assert sostituti == []
    assert righe == [risposta.id]


async def test_i_tre_indici_sono_dichiarati_e_ci_sono(db_session):
    dichiarati = {index.name for table in Base.metadata.tables.values() for index in table.indexes}
    assert INDICI <= dichiarati
    nel_database = await db_session.execute(
        text("SELECT indexname FROM pg_indexes WHERE schemaname = current_schema()")
    )
    assert INDICI <= {riga.indexname for riga in nel_database}
