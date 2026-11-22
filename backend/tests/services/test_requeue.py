"""Rimettere in coda una pagina scartata (spec
docs/superpowers/specs/2026-10-09-scartate-in-coda-design.md).

Le pagine si scartano col codice vero (`materialize_ready`), non scrivendo lo stato a
mano: il motivo che la rimessa rilegge è quello che la produzione scrive. La correzione
della causa si fa come la fa l'anagrafica: il reparto cambia, e `kind` lo segue dal
validatore del modello.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe import CookingEvent, Recipe
from app.db.models.recipe_import import (
    GIALLOZAFFERANO,
    ImportState,
    ImportTerm,
    RecipeImport,
    TermDecision,
)
from app.repositories.imports import store_page, store_unparsable
from app.repositories.ingredients import create_ingredient, remember_alias
from app.services.recipe_import.materialize import SkipCause, materialize_ready
from app.services.recipe_import.requeue import NotRequeueable, RequeueRefusal, requeue_page
from app.services.recipe_import.undo import undo_decision


def pagina(title: str, righe: list[tuple[str, str]]) -> dict:
    return {
        "title": title, "instructions": "Cuoci.", "servings": 4,
        "ingredients": [
            {"key": key, "name": name, "quantity_text": "100 g"} for key, name in righe
        ],
    }


@pytest_asyncio.fixture
async def scartate(db_session):
    """Due pagine scartate dal codice vero. «Torta alla panna» ha una riga su «Panna»,
    finita per sbaglio fra i prodotti per la casa: `create_recipe` la rifiuta. «Acqua
    calda» ha una riga sola, ignorata: resterebbe una ricetta senza ingredienti."""
    farina = await create_ingredient(
        db_session, name="farina", display_name="Farina", category=IngredientCategory.CEREALI
    )
    panna = await create_ingredient(
        db_session, name="panna", display_name="Panna", category=IngredientCategory.CASA
    )
    termini = {
        "farina": ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-farina", display_name="Farina 00",
            occurrences=1, decision=TermDecision.MAPPED, ingredient_id=farina.id,
            decided_by="human", created_ingredient=False,
        ),
        "panna": ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-panna", display_name="Panna fresca",
            occurrences=1, decision=TermDecision.MAPPED, ingredient_id=panna.id,
            decided_by="human", created_ingredient=False,
        ),
        "acqua": ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-acqua", display_name="Acqua",
            occurrences=1, decision=TermDecision.IGNORED, decided_by="human",
        ),
    }
    db_session.add_all(termini.values())
    await db_session.flush()
    torta = await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/torta",
        payload=pagina("Torta alla panna", [("k-farina", "Farina 00"), ("k-panna", "Panna fresca")]),
    )
    acqua = await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/acqua",
        payload=pagina("Acqua calda", [("k-acqua", "Acqua")]),
    )
    await materialize_ready(db_session, GIALLOZAFFERANO)
    assert (torta.state, acqua.state) == (ImportState.SKIPPED, ImportState.SKIPPED)
    return {"torta": torta, "acqua": acqua, "farina": farina, "panna": panna, "termini": termini}


async def test_con_la_causa_corretta_la_pagina_entra_nel_ricettario(db_session, scartate):
    torta = scartate["torta"]
    scartate["panna"].category = IngredientCategory.LATTICINI  # la correzione
    await db_session.flush()

    esito = await requeue_page(db_session, torta)

    assert esito.outcome == "imported"
    assert torta.state == ImportState.IMPORTED
    assert torta.skipped_reason is None
    assert torta.recipe_id is not None
    assert esito.recipe_id == torta.recipe_id
    assert esito.cooking_relinked == 0
    ricetta = await db_session.get(Recipe, torta.recipe_id)
    assert ricetta.title == "Torta alla panna"


async def test_le_cotture_che_aspettano_ritrovano_la_ricetta(db_session, scartate, dal_database):
    """Gli id che `undo_decision` lascia nel `payload` (S9 §5.2) tornano sulla ricetta
    rifatta: è `materialize_ready` a rilegarli, e la rimessa lo dice."""
    torta = scartate["torta"]
    evento = CookingEvent(recipe_id=None, servings=2, snapshot={"titolo": "Torta alla panna"})
    db_session.add(evento)
    await db_session.flush()
    torta.payload = {**torta.payload, "cooking_event_ids": [str(evento.id)]}
    scartate["panna"].category = IngredientCategory.LATTICINI
    await db_session.flush()
    evento_id, page_id = evento.id, torta.id

    esito = await requeue_page(db_session, torta)

    assert esito.cooking_relinked == 1
    assert (await dal_database(CookingEvent, evento_id)).recipe_id == torta.recipe_id
    assert "cooking_event_ids" not in (await dal_database(RecipeImport, page_id)).payload


async def test_senza_correggere_torna_scartata_col_suo_motivo(db_session, scartate):
    torta = scartate["torta"]

    esito = await requeue_page(db_session, torta)

    assert esito.outcome == "skipped"
    assert (esito.skip.cause, esito.skip.non_food_name) == (SkipCause.NON_FOOD, "Panna")
    assert torta.state == ImportState.SKIPPED
    assert torta.skipped_reason == "riga non alimentare: «Panna»"
    assert (await db_session.execute(select(Recipe))).scalars().all() == []


async def test_le_righe_ancora_tutte_ignorate_la_riscartano(db_session, scartate):
    esito = await requeue_page(db_session, scartate["acqua"])

    assert esito.outcome == "skipped"
    assert esito.skip.cause == SkipCause.ALL_IGNORED
    assert scartate["acqua"].state == ImportState.SKIPPED


async def test_con_un_termine_tornato_in_coda_aspetta_e_dice_quale(db_session, scartate):
    """La decisione «ignora» annullata nel frattempo: la pagina non è pronta, resta in
    coda, e la coda conta una ricetta in attesa di quel termine."""
    acqua, termine = scartate["acqua"], scartate["termini"]["acqua"]
    await undo_decision(db_session, termine)
    assert termine.occurrences == 0  # nessuna pagina in attesa lo usava

    esito = await requeue_page(db_session, acqua)

    assert esito.outcome == "waiting"
    assert esito.waiting_terms == ["Acqua"]
    assert acqua.state == ImportState.PENDING
    assert termine.occurrences == 1


async def test_un_termine_sparito_che_coincide_con_lanagrafica_rinasce_deciso(
    db_session, scartate
):
    """Il primo `sync_terms` della rimessa. Senza, `materialize_ready` lascerebbe la
    pagina ad aspettare un termine che non esiste, e il termine rinato dopo, deciso da
    sé, non la materializzerebbe fino alla prossima decisione qualunque."""
    torta, farina = scartate["torta"], scartate["farina"]
    scartate["panna"].category = IngredientCategory.LATTICINI
    await remember_alias(db_session, farina.id, "Farina 00")
    await db_session.delete(scartate["termini"]["farina"])
    await db_session.flush()

    esito = await requeue_page(db_session, torta)

    assert esito.outcome == "imported"
    rinato = (
        await db_session.execute(select(ImportTerm).where(ImportTerm.term_key == "k-farina"))
    ).scalars().one()
    assert (rinato.decision, rinato.decided_by, rinato.ingredient_id) == (
        TermDecision.MAPPED, "auto", farina.id,
    )


async def test_una_pagina_illeggibile_non_si_rimette(db_session):
    vuota = await store_unparsable(
        db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/vuota",
        reason="nessuna riga dd.gz-ingredient nella pagina",
    )

    with pytest.raises(NotRequeueable) as rifiuto:
        await requeue_page(db_session, vuota)

    assert rifiuto.value.refusal == RequeueRefusal.UNREADABLE
    assert vuota.state == ImportState.SKIPPED
    assert vuota.skipped_reason == "nessuna riga dd.gz-ingredient nella pagina"


async def test_una_pagina_che_non_e_scartata_non_si_rimette(db_session):
    in_attesa = await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/attesa",
        payload=pagina("Pane", [("k-lievito", "Lievito madre")]),
    )

    with pytest.raises(NotRequeueable) as rifiuto:
        await requeue_page(db_session, in_attesa)

    assert rifiuto.value.refusal == RequeueRefusal.NOT_SKIPPED
    assert in_attesa.state == ImportState.PENDING
