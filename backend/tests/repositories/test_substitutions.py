"""Le risposte di «Sostituisci» (R5): leggerle, scriverle, controllarle.

Due ambiti in una tabella — la voce generale (ingrediente × contesto) e la correzione di
una ricetta —, e una regola che li lega: per una riga vale la correzione, se c'è, poi la
voce generale. Una risposta «sostituti» rimasta senza sostituti visibili non vale niente.
"""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import RecipeSource
from app.db.models.substitution import IngredientSubstitution
from app.domain.substitutions import DecidedBy, SubstitutionContext, SubstitutionVerdict
from app.repositories import substitutions as repo
from app.repositories.recipes import create_recipe
from app.repositories.substitutions import Answer, SubstitutionRefused

SALATO = SubstitutionContext.SAVORY
DOLCE = SubstitutionContext.SWEET


@pytest_asyncio.fixture
async def voci(db_session):
    def voce(nome: str, reparto: str) -> Ingredient:
        return Ingredient(name=nome, display_name=nome.capitalize(), category=reparto)

    tutte = {
        "pollo": voce("pollo", IngredientCategory.CARNE),
        "tacchino": voce("tacchino", IngredientCategory.CARNE),
        "coniglio": voce("coniglio", IngredientCategory.CARNE),
        "burro": voce("burro", IngredientCategory.LATTICINI),
        "margarina": voce("margarina", IngredientCategory.CONDIMENTI),
        "detersivo": voce("detersivo", IngredientCategory.CASA),
    }
    db_session.add_all(tutte.values())
    await db_session.flush()
    return tutte


@pytest_asyncio.fixture
async def ricetta(db_session, voci):
    return await create_recipe(
        db_session, title="Pollo arrosto", description=None, instructions="Cuoci.",
        servings=2, source=RecipeSource.MANUAL, source_ref=None,
        ingredients=[(voci["pollo"].id, "primary", "1", None)], embedding=None,
    )


def sostituti(*voci_: Ingredient) -> Answer:
    return Answer(SubstitutionVerdict.SUBSTITUTES, tuple((voce.id, None) for voce in voci_))


def nomi(riga: IngredientSubstitution | None) -> list[str]:
    assert riga is not None
    return [opzione.substitute.name for opzione in repo.visible_options(riga)]


# --- controllare una risposta scritta a mano ---------------------------------------


async def test_una_risposta_giusta_esce_con_le_note_pulite(db_session, voci):
    risposta = await repo.checked_answer(
        db_session, voci["pollo"].id, SubstitutionVerdict.SUBSTITUTES,
        [(voci["tacchino"].id, "  metà   dose "), (voci["coniglio"].id, "   ")],
    )
    assert risposta == Answer(
        SubstitutionVerdict.SUBSTITUTES,
        ((voci["tacchino"].id, "metà dose"), (voci["coniglio"].id, None)),
    )


async def test_omettere_e_insostituibile_non_hanno_sostituti(db_session, voci):
    for esito in (SubstitutionVerdict.OMIT, SubstitutionVerdict.IRREPLACEABLE):
        assert await repo.checked_answer(db_session, voci["pollo"].id, esito, []) == Answer(esito)


async def test_i_rifiuti_dicono_cosa_fare(db_session, voci):
    pollo = voci["pollo"].id

    async def rifiuto(esito, scelti) -> str:
        with pytest.raises(SubstitutionRefused) as preso:
            await repo.checked_answer(db_session, pollo, esito, scelti)
        return preso.value.message

    S = SubstitutionVerdict.SUBSTITUTES
    assert await rifiuto(S, []) == "Scegli almeno un ingrediente da usare al suo posto."
    assert await rifiuto(SubstitutionVerdict.OMIT, [(voci["tacchino"].id, None)]) == (
        "Chi si omette o è insostituibile non ha sostituti: toglili, poi salva."
    )
    quattro = [(voci[n].id, None) for n in ("tacchino", "coniglio", "burro", "margarina")]
    assert await rifiuto(S, quattro) == "Al massimo tre sostituti: togline uno, poi salva."
    assert await rifiuto(S, [(uuid.uuid4(), None)]) == (
        "Uno dei sostituti scelti non è più in anagrafica: toglilo e scegline un altro."
    )
    assert await rifiuto(S, [(pollo, None)]) == (
        "«Pollo» non può sostituire sé stesso: scegli un altro ingrediente."
    )
    assert await rifiuto(S, [(voci["detersivo"].id, None)]) == (
        "«Detersivo» non è un alimento: non può sostituire un ingrediente."
    )
    assert await rifiuto(S, [(voci["tacchino"].id, None), (voci["tacchino"].id, "a fette")]) == (
        "«Tacchino» è scelto due volte: tienilo una volta sola."
    )
    assert await rifiuto(S, [(voci["tacchino"].id, "x" * 61)]) == (
        "La nota per «Tacchino» è troppo lunga: bastano poche parole, al massimo 60 caratteri."
    )


async def test_una_nota_di_sessanta_caratteri_basta(db_session, voci):
    risposta = await repo.checked_answer(
        db_session, voci["pollo"].id, SubstitutionVerdict.SUBSTITUTES,
        [(voci["tacchino"].id, "x" * 60)],
    )
    assert risposta.substitutes == ((voci["tacchino"].id, "x" * 60),)


# --- scrivere e leggere ---------------------------------------------------------------


async def test_la_voce_scritta_a_mano_sostituisce_quella_dell_ai(db_session, voci):
    pollo = voci["pollo"].id
    assert await repo.store_ai_answer(db_session, pollo, SALATO, sostituti(voci["tacchino"]))
    await repo.write_general(
        db_session, pollo, SALATO, sostituti(voci["coniglio"], voci["tacchino"])
    )

    riga = await repo.general_row(db_session, pollo, SALATO)
    assert riga is not None and riga.decided_by == DecidedBy.HUMAN
    assert nomi(riga) == ["coniglio", "tacchino"]  # nell'ordine dato
    tutte = (await db_session.execute(select(IngredientSubstitution))).scalars().all()
    assert len(tutte) == 1


async def test_i_due_contesti_sono_due_voci(db_session, voci):
    pollo = voci["pollo"].id
    await repo.write_general(db_session, pollo, SALATO, Answer(SubstitutionVerdict.OMIT))
    await repo.write_general(db_session, pollo, DOLCE, Answer(SubstitutionVerdict.IRREPLACEABLE))
    assert (await repo.general_row(db_session, pollo, SALATO)).verdict == "omit"
    assert (await repo.general_row(db_session, pollo, DOLCE)).verdict == "irreplaceable"


async def test_la_correzione_della_ricetta_vince_e_tolta_torna_la_generale(
    db_session, voci, ricetta
):
    pollo = voci["pollo"].id
    await repo.write_general(db_session, pollo, SALATO, sostituti(voci["tacchino"]))
    await repo.write_override(db_session, ricetta.id, pollo, Answer(SubstitutionVerdict.OMIT))

    vale = await repo.effective_row(db_session, ricetta.id, pollo, SALATO)
    assert vale is not None
    assert (vale.recipe_id, vale.context, vale.verdict, vale.decided_by) == (
        ricetta.id, None, "omit", "human",
    )

    assert await repo.delete_override(db_session, ricetta.id, pollo) is True
    assert nomi(await repo.effective_row(db_session, ricetta.id, pollo, SALATO)) == ["tacchino"]
    assert await repo.delete_override(db_session, ricetta.id, pollo) is False


async def test_una_nuova_correzione_prende_il_posto_della_vecchia(db_session, voci, ricetta):
    pollo = voci["pollo"].id
    await repo.write_override(db_session, ricetta.id, pollo, Answer(SubstitutionVerdict.OMIT))
    await repo.write_override(db_session, ricetta.id, pollo, sostituti(voci["coniglio"]))
    assert nomi(await repo.recipe_row(db_session, ricetta.id, pollo)) == ["coniglio"]


async def test_senza_risposte_non_vale_niente(db_session, voci, ricetta):
    assert await repo.effective_row(db_session, ricetta.id, voci["pollo"].id, SALATO) is None


async def test_un_sostituto_cancellato_lascia_la_voce_senza_risposta(db_session, voci, ricetta):
    """L'annullamento di una decisione della coda cancella l'ingrediente che l'AI aveva
    proposto: la risposta resta, vuota, e vale come nessuna (Review Focus 2)."""
    pollo = voci["pollo"].id
    await repo.store_ai_answer(db_session, pollo, SALATO, sostituti(voci["tacchino"]))
    await db_session.execute(delete(Ingredient).where(Ingredient.id == voci["tacchino"].id))

    riga = await repo.general_row(db_session, pollo, SALATO)
    assert riga is not None and repo.is_answered(riga) is False
    assert await repo.effective_row(db_session, ricetta.id, pollo, SALATO) is None


async def test_un_sostituto_diventato_non_alimentare_non_si_vede(db_session, voci):
    pollo = voci["pollo"].id
    await repo.store_ai_answer(
        db_session, pollo, SALATO, sostituti(voci["tacchino"], voci["coniglio"])
    )
    voci["tacchino"].category = IngredientCategory.CASA
    await db_session.flush()
    assert nomi(await repo.general_row(db_session, pollo, SALATO)) == ["coniglio"]


async def test_omettere_risponde_anche_senza_sostituti(db_session, voci):
    await repo.store_ai_answer(db_session, voci["pollo"].id, SALATO, Answer(SubstitutionVerdict.OMIT))
    riga = await repo.general_row(db_session, voci["pollo"].id, SALATO)
    assert repo.is_answered(riga) is True


# --- l'AI scrive solo dove non c'è una risposta ----------------------------------------


async def test_l_ai_scrive_dove_non_c_e_niente(db_session, voci):
    pollo = voci["pollo"].id
    assert await repo.store_ai_answer(db_session, pollo, SALATO, sostituti(voci["tacchino"])) is True
    riga = await repo.general_row(db_session, pollo, SALATO)
    assert riga.decided_by == DecidedBy.AI and nomi(riga) == ["tacchino"]


async def test_l_ai_non_tocca_una_risposta_che_c_e(db_session, voci):
    pollo = voci["pollo"].id
    await repo.write_general(db_session, pollo, SALATO, Answer(SubstitutionVerdict.IRREPLACEABLE))
    assert await repo.store_ai_answer(db_session, pollo, SALATO, sostituti(voci["tacchino"])) is False
    await repo.store_ai_answer(db_session, pollo, DOLCE, sostituti(voci["tacchino"]))
    assert await repo.store_ai_answer(db_session, pollo, DOLCE, sostituti(voci["coniglio"])) is False

    assert (await repo.general_row(db_session, pollo, SALATO)).verdict == "irreplaceable"
    assert nomi(await repo.general_row(db_session, pollo, DOLCE)) == ["tacchino"]


async def test_l_ai_rimpiazza_una_risposta_rimasta_vuota(db_session, voci):
    pollo = voci["pollo"].id
    await repo.write_general(db_session, pollo, SALATO, sostituti(voci["tacchino"]))
    await db_session.execute(delete(Ingredient).where(Ingredient.id == voci["tacchino"].id))

    assert await repo.store_ai_answer(db_session, pollo, SALATO, sostituti(voci["coniglio"])) is True
    riga = await repo.general_row(db_session, pollo, SALATO)
    assert riga.decided_by == DecidedBy.AI and nomi(riga) == ["coniglio"]


async def test_l_ai_non_scavalca_chi_scrive_fra_il_controllo_e_la_scrittura(
    db_session, voci, monkeypatch
):
    """La scrittura stessa controlla (`ON CONFLICT DO NOTHING`): se fra la lettura e
    l'`INSERT` una persona ha scritto, vince la persona."""
    pollo = voci["pollo"].id
    await repo.write_general(db_session, pollo, SALATO, Answer(SubstitutionVerdict.OMIT))

    async def non_vede_niente(*_args):
        return None

    monkeypatch.setattr(repo, "general_row", non_vede_niente)
    assert await repo.store_ai_answer(db_session, pollo, SALATO, sostituti(voci["tacchino"])) is False
    monkeypatch.undo()
    riga = await repo.general_row(db_session, pollo, SALATO)
    assert (riga.verdict, riga.decided_by) == ("omit", "human")
