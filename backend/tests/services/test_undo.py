"""Annullare una decisione: rimettere il mondo come era, e non un editor.

Un verbo solo. Dopo l'annullamento il termine è in coda e si decide a mano con la
scheda che esiste già ed è già testata — niente secondo percorso di decisione da
scrivere e mantenere.

Le ricette si rifanno da `payload`, che è ancora nel database esattamente per questo
(spec madre §6.1): non serve nessuna chirurgia su `recipe_ingredients`.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.recipe import CookingEvent, Recipe, RecipeSource
from app.db.models.recipe_import import (
    GIALLOZAFFERANO,
    ImportState,
    ImportTerm,
    RecipeImport,
    TermDecision,
)
from app.repositories.ingredients import create_ingredient, remember_alias
from app.repositories.recipes import create_recipe
from app.services.recipe_import.undo import CookedRecipesAffected, undo_decision


@pytest_asyncio.fixture
async def deciso(db_session):
    """Un termine deciso dall'AI, con l'ingrediente creato, l'alias e la ricetta."""
    speck = await create_ingredient(
        db_session, name="speck", display_name="Speck", category=IngredientCategory.CARNE
    )
    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-speck", display_name="Speck",
        occurrences=1, decision=TermDecision.MAPPED, ingredient_id=speck.id,
        decided_by="ai", role_override="secondary",
    )
    db_session.add(term)
    await db_session.flush()
    await remember_alias(db_session, speck.id, "Speck")

    recipe = await create_recipe(
        db_session, title="Pasta allo speck", description=None, instructions="cuoci",
        servings=2, source=RecipeSource.DATASET, source_ref="https://esempio.invalid/1",
        ingredients=[(speck.id, "primary", "100 g", None)], embedding=None,
    )
    page = RecipeImport(
        source=GIALLOZAFFERANO, url="https://esempio.invalid/1",
        payload={"title": "Pasta allo speck", "ingredients": [{"key": "k-speck", "name": "Speck"}]},
        state=ImportState.IMPORTED, recipe_id=recipe.id,
    )
    db_session.add(page)
    await db_session.flush()
    return term, speck, recipe, page


async def test_il_termine_torna_in_coda_pulito(db_session, deciso):
    term, _, _, _ = deciso
    await undo_decision(db_session, term)
    assert term.decision == TermDecision.PENDING
    assert term.ingredient_id is None
    assert term.decided_by is None
    assert term.decided_at is None
    assert term.role_override is None


async def test_lalias_scritto_dalla_decisione_si_cancella(db_session, deciso):
    term, speck, _, _ = deciso
    await undo_decision(db_session, term)
    trovati = (
        await db_session.execute(
            select(IngredientAlias).where(IngredientAlias.alias == "speck")
        )
    ).scalars().all()
    assert trovati == []


async def test_lingrediente_creato_e_non_piu_usato_si_cancella(db_session, deciso):
    term, speck, _, _ = deciso
    esito = await undo_decision(db_session, term)
    assert esito.ingredient_deleted is True
    assert await db_session.get(Ingredient, speck.id) is None


async def test_la_ricetta_torna_in_coda_e_la_pagina_torna_pending(db_session, deciso):
    term, _, recipe, page = deciso
    esito = await undo_decision(db_session, term)

    assert esito.recipes_requeued == 1
    assert await db_session.get(Recipe, recipe.id) is None
    await db_session.refresh(page)
    assert page.state == ImportState.PENDING
    assert page.recipe_id is None


async def test_un_ingrediente_che_un_altro_termine_usa_resta(db_session, deciso):
    """È questo controllo che rende gratuito l'annullamento di un collasso.

    Se «Speck a cubetti» era stato accorpato sullo stesso ingrediente, annullare
    «Speck» trova l'altro termine e non cancella niente.
    """
    term, speck, _, _ = deciso
    altro = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-speck-cubetti", display_name="Speck a cubetti",
        occurrences=1, decision=TermDecision.MAPPED, ingredient_id=speck.id, decided_by="ai",
    )
    db_session.add(altro)
    await db_session.flush()

    esito = await undo_decision(db_session, term)
    assert esito.ingredient_deleted is False
    assert await db_session.get(Ingredient, speck.id) is not None


async def test_una_ricetta_gia_cucinata_blocca_finche_non_si_insiste(db_session, deciso):
    """L'unico punto di tutta la feature in cui si chiede qualcosa.

    `cooking_events.recipe_id` è ON DELETE SET NULL: lo storico sopravvive col suo
    snapshot, ma perde il collegamento alla ricetta, per sempre. Quello storico esiste
    solo perché la fase 3 e la fase 4 ci costruiscono sopra. Rifiutare in silenzio
    sarebbe un vicolo cieco, procedere in silenzio una perdita invisibile.
    """
    term, _, recipe, _ = deciso
    db_session.add(CookingEvent(recipe_id=recipe.id, servings=2, snapshot={}))
    await db_session.flush()

    with pytest.raises(CookedRecipesAffected) as errore:
        await undo_decision(db_session, term)
    assert errore.value.count == 1

    # niente è stato toccato: un'eccezione a metà lavoro sarebbe peggio del rifiuto
    assert term.decision == TermDecision.MAPPED
    assert await db_session.get(Recipe, recipe.id) is not None


async def test_con_force_si_procede_e_lo_storico_resta_orfano(db_session, deciso):
    term, _, recipe, _ = deciso
    evento = CookingEvent(recipe_id=recipe.id, servings=2, snapshot={"titolo": "Pasta allo speck"})
    db_session.add(evento)
    await db_session.flush()

    esito = await undo_decision(db_session, term, force=True)

    assert esito.recipes_requeued == 1
    assert await db_session.get(Recipe, recipe.id) is None
    await db_session.refresh(evento)
    assert evento.recipe_id is None
    # lo snapshot è ciò che sopravvive, ed è il motivo per cui questo è accettabile
    assert evento.snapshot == {"titolo": "Pasta allo speck"}


async def test_annullare_un_termine_ignorato_funziona(db_session):
    """Un `ignore` non ha ingrediente né alias: l'annullamento deve reggerlo comunque."""
    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-acqua", display_name="Acqua",
        occurrences=2, decision=TermDecision.IGNORED, ingredient_id=None, decided_by="ai",
    )
    db_session.add(term)
    await db_session.flush()

    esito = await undo_decision(db_session, term)
    assert term.decision == TermDecision.PENDING
    assert esito.ingredient_deleted is False
    assert esito.alias_forgotten is False


async def test_una_pagina_cancellata_dallutente_non_si_resuscita(db_session, deciso):
    """`state='imported'` con `recipe_id` nullo è una cancellazione dell'utente.

    La regola del modello — «è lo stato, non la presenza della chiave, a dire già
    importata una volta» — dice che quella pagina non deve tornare. Rimetterla a
    `pending` la farebbe ricreare, e la cancellazione non sarebbe mai definitiva.
    """
    term, _, recipe, page = deciso
    await db_session.delete(recipe)
    await db_session.flush()
    await db_session.refresh(page)
    assert page.state == ImportState.IMPORTED and page.recipe_id is None

    esito = await undo_decision(db_session, term)
    assert esito.recipes_requeued == 0
    await db_session.refresh(page)
    assert page.state == ImportState.IMPORTED
