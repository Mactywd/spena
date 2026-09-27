"""Annullare una decisione: rimettere il mondo come era, e non un editor.

Un verbo solo. Dopo l'annullamento il termine è in coda e si decide a mano con la
scheda che esiste già ed è già testata — niente secondo percorso di decisione da
scrivere e mantenere.

Le ricette si rifanno da `payload`, che è ancora nel database esattamente per questo
(spec madre §6.1): non serve nessuna chirurgia su `recipe_ingredients`.
"""

from datetime import UTC, datetime

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
from app.db.models.pantry import PantryItem
from app.domain.rules import PantryStatus
from app.repositories.ingredients import create_ingredient, remember_alias
from app.repositories.recipes import create_recipe
from app.services.recipe_import.undo import undo_decision
from app.services.recipe_import.manual import ManualDecision, decide_by_hand
from app.services.recipe_import.materialize import materialize_ready
from app.services.registry import merge_ingredients


@pytest_asyncio.fixture
async def deciso(db_session):
    """Un termine deciso dall'AI, con l'ingrediente creato, l'alias e la ricetta."""
    speck = await create_ingredient(
        db_session, name="speck", display_name="Speck", category=IngredientCategory.CARNE
    )
    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-speck", display_name="Speck",
        occurrences=1, decision=TermDecision.MAPPED, ingredient_id=speck.id,
        decided_by="ai", decided_at=datetime.now(UTC), role_override="secondary",
        created_ingredient=True,
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


async def test_lingrediente_creato_dalla_decisione_e_non_piu_usato_si_cancella(
    db_session, deciso
):
    term, speck, _, _ = deciso
    esito = await undo_decision(db_session, term)
    assert esito.ingredient_deleted is True
    assert await db_session.get(Ingredient, speck.id) is None
    assert term.created_ingredient is None


async def test_una_decisione_di_prima_del_flag_non_cancella_lingrediente(db_session, deciso):
    """Le decisioni prese prima del 2026-09-28 hanno `created_ingredient` NULL: non si
    sa se hanno creato l'ingrediente o ne hanno agganciato uno che c'era, e nel dubbio
    l'ingrediente resta — cancellare quello che c'era è il difetto peggiore."""
    term, speck, _, _ = deciso
    term.created_ingredient = None
    await db_session.flush()

    esito = await undo_decision(db_session, term)

    assert esito.ingredient_deleted is False
    assert await db_session.get(Ingredient, speck.id) is not None


async def test_annullare_un_aggancio_non_cancella_lingrediente_che_cera_gia(db_session):
    """«Rigatoni» agganciato a «pasta», che c'era da prima e che niente altro usa:
    annullare toglie l'alias «rigatoni» e rimette il termine in coda, ma «pasta»
    resta. Prima la cancellava, e la coda diceva «L'ingrediente che questa decisione
    aveva creato è stato eliminato», che era falso.
    """
    pasta = await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-rigatoni", display_name="Rigatoni",
        occurrences=1, decision=TermDecision.MAPPED, ingredient_id=pasta.id,
        decided_by="ai", decided_at=datetime.now(UTC), created_ingredient=False,
    )
    db_session.add(term)
    await db_session.flush()
    await remember_alias(db_session, pasta.id, "Rigatoni")
    pasta_id = pasta.id

    esito = await undo_decision(db_session, term)

    assert esito.ingredient_deleted is False
    assert esito.alias_forgotten is True
    db_session.expunge_all()
    assert await db_session.get(Ingredient, pasta_id) is not None
    alias = (
        await db_session.execute(select(IngredientAlias).where(IngredientAlias.alias == "rigatoni"))
    ).scalars().all()
    assert alias == []


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


async def test_una_ricetta_gia_cucinata_non_blocca_e_la_cottura_aspetta_nella_pagina(
    db_session, deciso, dal_database
):
    """Fino a S9 qui c'era un rifiuto, e un `force` per superarlo: cancellando la
    ricetta `cooking_events.recipe_id` diventava NULL per sempre. Ora gli id delle
    cotture passano nel `payload` della pagina prima della cancellazione.

    La pagina si rilegge da una sessione nuova: un `payload` mutato invece che
    riassegnato sembrerebbe giusto nella memoria di `db_session` e non arriverebbe mai
    al database (spec §10). Scritto così, questo test lo vede.
    """
    term, _, recipe, page = deciso
    evento = CookingEvent(recipe_id=recipe.id, servings=2, snapshot={"titolo": "Pasta allo speck"})
    db_session.add(evento)
    await db_session.flush()
    evento_id, page_id = evento.id, page.id

    esito = await undo_decision(db_session, term)

    assert esito.recipes_requeued == 1
    pagina = await dal_database(RecipeImport, page_id)
    assert pagina.payload["cooking_event_ids"] == [str(evento_id)]
    assert pagina.payload["title"] == "Pasta allo speck"
    cottura = await dal_database(CookingEvent, evento_id)
    # senza ricetta per ora, e con il suo snapshot: la ritrova quando la pagina torna
    assert cottura.recipe_id is None
    assert cottura.snapshot == {"titolo": "Pasta allo speck"}


async def test_la_cottura_ritrova_la_ricetta_quando_la_pagina_torna(db_session, deciso, dal_database):
    """La pagina lasciata in coda tiene gli id finché il termine non ha di nuovo una
    decisione; allora torna ricetta, e la cottura con lei (spec §5.2 e §9.3)."""
    term, _, recipe, page = deciso
    evento = CookingEvent(recipe_id=recipe.id, servings=2, snapshot={})
    db_session.add(evento)
    await db_session.flush()
    evento_id, page_id = evento.id, page.id

    await undo_decision(db_session, term)
    # il termine è in coda: la pagina aspetta, e la cottura con lei
    assert (await materialize_ready(db_session, GIALLOZAFFERANO)).created == 0

    pancetta = await create_ingredient(
        db_session, name="pancetta", display_name="Pancetta", category=IngredientCategory.CARNE
    )
    await decide_by_hand(db_session, term, ManualDecision(action="map", ingredient_id=pancetta.id))
    esito = await materialize_ready(db_session, GIALLOZAFFERANO)

    assert esito.created == 1
    assert esito.relinked == 1
    pagina = await dal_database(RecipeImport, page_id)
    cottura = await dal_database(CookingEvent, evento_id)
    assert pagina.recipe_id is not None
    assert cottura.recipe_id == pagina.recipe_id
    assert "cooking_event_ids" not in pagina.payload


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


async def _scarta_con_ignora(db_session, term):
    """Ogni riga ignorata: la ricetta resterebbe vuota, e la pagina finisce SKIPPED."""
    await decide_by_hand(db_session, term, ManualDecision(action="ignore"))


async def _scarta_con_non_alimentare(db_session, term):
    """La riga punta a una voce diventata non alimentare mentre la pagina aspettava:
    `create_recipe` rifiuta, e la pagina finisce SKIPPED col nome della voce. Il
    reparto si scrive diretto, perché `recategorize_ingredient` quel buco lo chiude."""
    sapone = await create_ingredient(
        db_session, name="sapone", display_name="Sapone", category=IngredientCategory.CARNE
    )
    await decide_by_hand(db_session, term, ManualDecision(action="map", ingredient_id=sapone.id))
    sapone.category = IngredientCategory.CASA
    await db_session.flush()


@pytest.mark.parametrize("scarta", [_scarta_con_ignora, _scarta_con_non_alimentare])
async def test_una_pagina_che_finisce_scartata_tiene_gli_id_delle_cotture(
    db_session, deciso, dal_database, scarta
):
    """Nota della revisione del Task 3 di S9: una pagina rimessa in coda da un
    annullamento può finire SKIPPED invece che ricetta. Non c'è una ricetta a cui
    rilegare le cotture, e non se ne inventa una: gli id restano nel `payload`, letto
    dal database e non dalla memoria di `db_session`, e le cotture restano senza
    ricetta ma col loro snapshot.
    """
    term, _, recipe, page = deciso
    evento = CookingEvent(recipe_id=recipe.id, servings=2, snapshot={"titolo": "Pasta allo speck"})
    db_session.add(evento)
    await db_session.flush()
    evento_id, page_id = evento.id, page.id

    await undo_decision(db_session, term)
    await scarta(db_session, term)
    esito = await materialize_ready(db_session, GIALLOZAFFERANO)

    assert (esito.created, esito.skipped, esito.relinked) == (0, 1, 0)
    pagina = await dal_database(RecipeImport, page_id)
    assert pagina.state == ImportState.SKIPPED
    assert pagina.payload["cooking_event_ids"] == [str(evento_id)]
    cottura = await dal_database(CookingEvent, evento_id)
    assert cottura.recipe_id is None
    assert cottura.snapshot == {"titolo": "Pasta allo speck"}


async def test_una_pagina_scartata_rimessa_in_attesa_ritrova_le_cotture(
    db_session, deciso, dal_database
):
    """Una pagina SKIPPED non torna in attesa da nessuna strada dell'app: né
    annullando un'altra decisione (`undo_decision` rimette in coda solo le pagine
    `imported` con la loro ricetta), né da un comando. Il giorno in cui una strada
    così esisterà, o se la si rimette a `pending` a mano nel database, la
    materializzazione vera rilega le cotture che il `payload` ha tenuto.
    """
    term, _, recipe, page = deciso
    evento = CookingEvent(recipe_id=recipe.id, servings=2, snapshot={})
    db_session.add(evento)
    await db_session.flush()
    evento_id, page_id = evento.id, page.id

    await undo_decision(db_session, term)
    await _scarta_con_ignora(db_session, term)
    await materialize_ready(db_session, GIALLOZAFFERANO)

    # annullare il termine ignorato non riporta indietro la pagina scartata
    esito = await undo_decision(db_session, term)
    assert esito.recipes_requeued == 0
    assert (await dal_database(RecipeImport, page_id)).state == ImportState.SKIPPED

    pancetta = await create_ingredient(
        db_session, name="pancetta", display_name="Pancetta", category=IngredientCategory.CARNE
    )
    await decide_by_hand(db_session, term, ManualDecision(action="map", ingredient_id=pancetta.id))
    await db_session.refresh(page)
    page.state = ImportState.PENDING
    page.skipped_reason = None
    await db_session.flush()
    esito = await materialize_ready(db_session, GIALLOZAFFERANO)

    assert (esito.created, esito.relinked) == (1, 1)
    pagina = await dal_database(RecipeImport, page_id)
    cottura = await dal_database(CookingEvent, evento_id)
    assert pagina.state == ImportState.IMPORTED
    assert cottura.recipe_id == pagina.recipe_id
    assert "cooking_event_ids" not in pagina.payload


async def test_una_creazione_a_mano_annullata_cancella_lingrediente_se_non_lo_usa_nessuno(
    db_session,
):
    """R11: la decisione a mano che crea scrive il fatto come quella dell'AI. Creato e
    poi usato in dispensa, l'ingrediente resta: il flag dice «creato qui», non «si
    cancella comunque»."""
    usato, libero = (
        ImportTerm(
            source=GIALLOZAFFERANO, term_key=f"k-{nome}", display_name=nome.capitalize(),
            occurrences=1, decision=TermDecision.PENDING,
        )
        for nome in ("bottarga", "colatura")
    )
    db_session.add_all([usato, libero])
    await db_session.flush()
    bottarga = await decide_by_hand(db_session, usato, ManualDecision(
        action="create", name="bottarga", display_name="Bottarga", category=IngredientCategory.PESCE,
    ))
    colatura = await decide_by_hand(db_session, libero, ManualDecision(
        action="create", name="colatura", display_name="Colatura", category=IngredientCategory.PESCE,
    ))
    assert (usato.created_ingredient, libero.created_ingredient) == (True, True)
    db_session.add(PantryItem(ingredient_id=bottarga.id, status=PantryStatus.AVAILABLE))
    await db_session.flush()
    bottarga_id, colatura_id = bottarga.id, colatura.id

    assert (await undo_decision(db_session, usato)).ingredient_deleted is False
    assert (await undo_decision(db_session, libero)).ingredient_deleted is True
    assert await db_session.get(Ingredient, bottarga_id) is not None
    assert await db_session.get(Ingredient, colatura_id) is None


async def test_un_aggancio_a_mano_scrive_che_non_ha_creato(db_session):
    pasta = await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-penne", display_name="Penne",
        occurrences=1, decision=TermDecision.PENDING,
    )
    db_session.add(term)
    await db_session.flush()

    await decide_by_hand(db_session, term, ManualDecision(action="map", ingredient_id=pasta.id))
    assert term.created_ingredient is False
    esito = await undo_decision(db_session, term)

    assert esito.ingredient_deleted is False
    assert await db_session.get(Ingredient, pasta.id) is not None


async def test_un_termine_rideciso_dalla_fusione_non_cancella_il_vincitore(db_session):
    """«Pomodorini» ha creato il suo ingrediente; la fusione lo unisce a «pomodoro», che
    c'era da prima, e ridecide il termine sul vincitore: da lì il termine non ha creato
    niente, e annullarlo lascia «pomodoro» dov'è."""
    pomodoro = await create_ingredient(
        db_session, name="pomodoro", display_name="Pomodoro", category=IngredientCategory.VERDURA
    )
    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-pomodorini", display_name="Pomodorini",
        occurrences=1, decision=TermDecision.PENDING,
    )
    db_session.add(term)
    await db_session.flush()
    pomodorini = await decide_by_hand(db_session, term, ManualDecision(
        action="create", name="pomodorini", display_name="Pomodorini",
        category=IngredientCategory.VERDURA,
    ))
    assert term.created_ingredient is True

    await merge_ingredients(db_session, pomodorini.id, pomodoro.id)
    await db_session.refresh(term)
    assert (term.ingredient_id, term.created_ingredient) == (pomodoro.id, False)

    esito = await undo_decision(db_session, term)

    assert esito.ingredient_deleted is False
    assert await db_session.get(Ingredient, pomodoro.id) is not None


async def test_una_creazione_dellai_annullata_cancella_lingrediente(db_session, monkeypatch):
    """Il giro vero dell'AI: `decide_terms` crea «speck» e aggancia «Rigatoni» a
    «pasta». Annullate tutte e due, lo speck sparisce e la pasta resta."""
    from app.core.config import get_settings
    from app.services.recipe_import.decide import decide_terms
    from llm_fakes import ScriptedLlm, llm_create, llm_map

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    try:
        pasta = await create_ingredient(
            db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
        )
        rigatoni, speck = (
            ImportTerm(
                source=GIALLOZAFFERANO, term_key=f"k-{nome.lower()}", display_name=nome,
                occurrences=1, decision=TermDecision.PENDING,
            )
            for nome in ("Rigatoni", "Speck")
        )
        db_session.add_all([rigatoni, speck])
        await db_session.flush()
        finto = ScriptedLlm({
            "Rigatoni": llm_map("pasta"),
            "Speck": llm_create("speck", "Speck", "carne"),
        })

        await decide_terms(db_session, [rigatoni, speck], client=finto)
    finally:
        get_settings.cache_clear()

    assert (rigatoni.created_ingredient, speck.created_ingredient) == (False, True)
    speck_id = speck.ingredient_id
    assert (await undo_decision(db_session, rigatoni)).ingredient_deleted is False
    assert (await undo_decision(db_session, speck)).ingredient_deleted is True
    assert await db_session.get(Ingredient, pasta.id) is not None
    assert await db_session.get(Ingredient, speck_id) is None


async def _creato_e_agganciato(db_session):
    """«Speck» crea l'ingrediente, «Speck a cubetti» ci si aggancia dopo: due termini
    sullo stesso ingrediente, uno solo con `created_ingredient=True` — come il collasso
    di `decide.py` o due `create` dello stesso nome nella stessa passata."""
    creatore, agganciato = (
        ImportTerm(
            source=GIALLOZAFFERANO, term_key=key, display_name=nome,
            occurrences=1, decision=TermDecision.PENDING,
        )
        for key, nome in (("k-speck", "Speck"), ("k-speck-cubetti", "Speck a cubetti"))
    )
    db_session.add_all([creatore, agganciato])
    await db_session.flush()
    speck = await decide_by_hand(db_session, creatore, ManualDecision(
        action="create", name="speck", display_name="Speck", category=IngredientCategory.CARNE,
    ))
    await decide_by_hand(
        db_session, agganciato, ManualDecision(action="map", ingredient_id=speck.id)
    )
    return creatore, agganciato, speck.id


@pytest.mark.parametrize("creatore_prima", [True, False])
async def test_lingrediente_creato_si_cancella_in_qualunque_ordine_si_annulli(
    db_session, creatore_prima
):
    """Revisione del ramo: annullando prima il creatore, la cancellazione era rifiutata
    (l'altro termine lo usa ancora) e il flag spariva con lui; poi l'altro, `False`,
    non cancellava mai. Ora il creatore rifiutato passa il flag a chi resta."""
    creatore, agganciato, speck_id = await _creato_e_agganciato(db_session)
    primo, secondo = (creatore, agganciato) if creatore_prima else (agganciato, creatore)

    assert (await undo_decision(db_session, primo)).ingredient_deleted is False
    assert await db_session.get(Ingredient, speck_id) is not None
    assert (await undo_decision(db_session, secondo)).ingredient_deleted is True
    assert await db_session.get(Ingredient, speck_id) is None


async def test_il_flag_passato_non_cancella_un_ingrediente_ancora_in_dispensa(db_session):
    creatore, agganciato, speck_id = await _creato_e_agganciato(db_session)
    db_session.add(PantryItem(ingredient_id=speck_id, status=PantryStatus.AVAILABLE))
    await db_session.flush()

    await undo_decision(db_session, creatore)
    assert agganciato.created_ingredient is True
    esito = await undo_decision(db_session, agganciato)

    assert esito.ingredient_deleted is False
    assert await db_session.get(Ingredient, speck_id) is not None
