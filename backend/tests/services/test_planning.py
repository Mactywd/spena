"""Le proposte di pasti e «Metti nella settimana» (piano 6c, Task 5, decisioni 12, 13, 26,
28): una proposta nuova sostituisce l'aperta, le bozze si ufficializzano senza conferma,
un posto occupato si sostituisce solo con la conferma, e una proposta si mette una volta
sola. Oggi è giovedì 12 novembre 2026 (il 13 è venerdì, il 14 sabato)."""

from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.change_card import ChangeCard
from app.db.models.conversation import ConversationMessage
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.meal import Meal
from app.db.models.pantry import PantryItem
from app.db.models.planning import ProposalKind
from app.db.models.recipe import RecipeSource
from app.db.models.recipe_change import RecipeChange
from app.domain.meals import MealSlot, MealStatus
from app.domain.rules import PantryStatus
from app.repositories.conversations import (
    cards_of,
    create_planning,
    latest_planning,
    move_turn_products,
    proposals_of,
    set_focus,
)
from app.repositories.meals import get_meal, meal_at
from app.repositories.recipes import create_recipe
from app.services.change_cards import (
    ListProposal,
    PantryProposal,
    apply_card,
    propose_card,
)
from app.services.meals import create_meal, update_meal
from app.services.planning import (
    PlanningRefusal,
    PlanningRefusalCode,
    ProposedMeal,
    conversation_for_meal,
    place_proposal,
    planning_concluded,
    propose_meals,
    row_occupants,
)

TODAY = date(2026, 11, 12)
VEN = date(2026, 11, 13)
SAB = date(2026, 11, 14)
L, D = MealSlot.LUNCH, MealSlot.DINNER
OFFICIAL, DRAFT = ProposalKind.OFFICIAL, ProposalKind.DRAFT


def now() -> datetime:
    return datetime.now(UTC)


@pytest_asyncio.fixture
async def chat(db_session):
    conversation = await create_planning(db_session)
    message = ConversationMessage(
        conversation_id=conversation.id, role="user", text="Cosa mangio?",
        created_at=now(),
    )
    db_session.add(message)
    await db_session.flush()
    return conversation, message


async def proponi(db_session, chat, kind, *meals):
    conversation, message = chat
    return await propose_meals(
        db_session, conversation_id=conversation.id, turn_message_id=message.id,
        kind=kind, meals=list(meals), today=TODAY,
    )


async def test_una_proposta_nuova_sostituisce_quella_aperta(db_session, chat):
    prima = await proponi(db_session, chat, OFFICIAL, ProposedMeal(VEN, D, "Frittata", None))
    seconda = await proponi(db_session, chat, OFFICIAL, ProposedMeal(VEN, D, "Orata", "Pane"))

    await db_session.refresh(prima)
    assert prima.status == "superseded"
    assert seconda.status == "open"
    assert seconda.rows == [
        {"day": "2026-11-13", "slot": "dinner", "dish": "Orata", "sides": "Pane", "meal_id": None}
    ]
    assert [p.id for p in await proposals_of(db_session, chat[0].id)] == [prima.id, seconda.id]


async def test_niente_passato_niente_doppioni(db_session, chat):
    with pytest.raises(PlanningRefusal) as passato:
        await proponi(db_session, chat, OFFICIAL, ProposedMeal(date(2026, 11, 11), D, "X", None))
    assert passato.value.code == PlanningRefusalCode.PAST
    assert passato.value.message == (
        "Non si pianifica nel passato: mercoledì 11 novembre è prima di oggi."
    )

    with pytest.raises(PlanningRefusal) as doppio:
        await proponi(
            db_session, chat, OFFICIAL,
            ProposedMeal(VEN, D, "Frittata", None), ProposedMeal(VEN, D, "Orata", None),
        )
    assert doppio.value.code == PlanningRefusalCode.DUPLICATE_SLOT
    assert doppio.value.message == "Due pasti nello stesso posto: venerdì 13 novembre · cena."
    assert await proposals_of(db_session, chat[0].id) == []


async def test_mettere_su_posti_vuoti(db_session, chat):
    proposta = await proponi(
        db_session, chat, OFFICIAL,
        ProposedMeal(VEN, D, "Frittata di spinaci", "Pane · mela"),
        ProposedMeal(SAB, L, "Pasta al pesto", None),
    )
    assert [effect for _, _, effect in await row_occupants(db_session, proposta)] == [
        "new", "new",
    ]
    istante = now()
    placement = await place_proposal(db_session, proposta.id, replace=False, now=istante)

    cena = await meal_at(db_session, VEN, D)
    pranzo = await meal_at(db_session, SAB, L)
    assert (cena.dish, cena.sides, cena.status) == ("Frittata di spinaci", "Pane · mela", "official")
    assert (pranzo.dish, pranzo.sides, pranzo.status) == ("Pasta al pesto", None, "official")
    for meal in (cena, pranzo):
        assert meal.recipe_requested_at == istante
        assert meal.recipe_notice is None
    assert [m.id for m in placement.meals] == [cena.id, pranzo.id]
    assert placement.proposal.status == "placed"
    assert placement.proposal.placed_at == istante
    assert [r["meal_id"] for r in placement.proposal.rows] == [str(cena.id), str(pranzo.id)]
    assert placement.follow_up == (
        "Ho messo nella settimana: venerdì 13 novembre · cena, Frittata di spinaci; "
        "sabato 14 novembre · pranzo, Pasta al pesto. Mandami la scheda dei cambi."
    )
    assert await conversation_for_meal(db_session, cena.id) == chat[0].id


async def test_una_bozza_si_mette_come_bozza(db_session, chat):
    proposta = await proponi(db_session, chat, DRAFT, ProposedMeal(VEN, D, "Lasagne", None))
    placement = await place_proposal(db_session, proposta.id, replace=False, now=now())

    (meal,) = placement.meals
    assert meal.status == "draft"
    assert meal.recipe_requested_at is None
    assert placement.follow_up == (
        "Ho messo nella settimana come bozza: venerdì 13 novembre · cena, Lasagne. "
        "Mandami le cose da mettere in lista."
    )


async def test_l_ufficializzazione_aggiorna_la_bozza_senza_conferma(db_session, chat):
    bozza = await create_meal(
        db_session, day=VEN, slot=D, dish="Merluzzo", sides="Pane", status=MealStatus.DRAFT
    )
    proposta = await proponi(
        db_session, chat, OFFICIAL, ProposedMeal(VEN, D, "Salmone al forno", "Patate")
    )
    ((_, occupante, effetto),) = await row_occupants(db_session, proposta)
    assert (occupante.id, effetto) == (bozza.id, "officialize")

    placement = await place_proposal(db_session, proposta.id, replace=False, now=now())

    meal = await get_meal(db_session, bozza.id)
    assert meal is not None
    assert (meal.status, meal.dish, meal.sides) == ("official", "Salmone al forno", "Patate")
    assert meal.recipe_requested_at is not None
    assert [m.id for m in placement.meals] == [bozza.id]
    assert placement.proposal.rows[0]["meal_id"] == str(bozza.id)


async def test_un_posto_occupato_chiede_la_conferma_e_non_scrive_niente(db_session, chat):
    ricotta = Ingredient(
        name="ricotta", display_name="Ricotta", category=IngredientCategory.LATTICINI
    )
    db_session.add(ricotta)
    await db_session.flush()
    voce = PantryItem(ingredient_id=ricotta.id, status=PantryStatus.AVAILABLE)
    db_session.add(voce)
    await db_session.flush()
    occupante = await create_meal(db_session, day=VEN, slot=D, dish="Pasta alla ricotta")
    scheda = await propose_card(
        db_session, meals=[occupante],
        pantry=[PantryProposal(voce.id, PantryStatus.FINISHED)], shopping=[],
    )
    await apply_card(db_session, scheda.id, [])

    # il pranzo del 13, vuoto, viene prima del posto occupato: scrivere riga per riga lo
    # metterebbe nella settimana prima del rifiuto
    proposta = await proponi(
        db_session, chat, OFFICIAL,
        ProposedMeal(VEN, D, "Orata", None), ProposedMeal(SAB, L, "Risotto", None),
        ProposedMeal(VEN, L, "Insalata di farro", None),
    )
    assert [e for _, _, e in await row_occupants(db_session, proposta)] == [
        "new", "replace", "new",
    ]

    with pytest.raises(PlanningRefusal) as rifiuto:
        await place_proposal(db_session, proposta.id, replace=False, now=now())
    assert rifiuto.value.code == PlanningRefusalCode.SLOTS_TAKEN
    assert rifiuto.value.message == "Alcuni posti sono occupati."
    assert [m.id for m in rifiuto.value.occupants] == [occupante.id]
    assert await meal_at(db_session, SAB, L) is None
    assert await meal_at(db_session, VEN, L) is None
    await db_session.refresh(proposta)
    assert proposta.status == "open"
    assert (await meal_at(db_session, VEN, D)).id == occupante.id

    placement = await place_proposal(db_session, proposta.id, replace=True, now=now())
    assert await db_session.get(Meal, occupante.id) is None
    nuovo = await meal_at(db_session, VEN, D)
    assert (nuovo.dish, nuovo.status) == ("Orata", "official")
    assert await meal_at(db_session, SAB, L) is not None
    assert placement.proposal.status == "placed"
    inverse = (
        await db_session.execute(select(ChangeCard).where(ChangeCard.kind == "inverse"))
    ).scalars().all()
    assert len(inverse) == 1


async def test_mettere_due_volte(db_session, chat):
    vecchia = await proponi(db_session, chat, OFFICIAL, ProposedMeal(VEN, D, "Frittata", None))
    proposta = await proponi(db_session, chat, OFFICIAL, ProposedMeal(VEN, D, "Orata", None))
    await place_proposal(db_session, proposta.id, replace=False, now=now())

    with pytest.raises(PlanningRefusal) as messa:
        await place_proposal(db_session, proposta.id, replace=True, now=now())
    assert messa.value.code == PlanningRefusalCode.PLACED
    assert messa.value.message == "Questa proposta è già nella settimana."

    with pytest.raises(PlanningRefusal) as superata:
        await place_proposal(db_session, vecchia.id, replace=True, now=now())
    assert superata.value.code == PlanningRefusalCode.SUPERSEDED
    assert superata.value.message == "C'è una proposta più nuova: usa quella."
    assert (await meal_at(db_session, VEN, D)).dish == "Orata"


async def test_conclusa(db_session, chat):
    conversation, _ = chat
    pesto = Ingredient(name="pesto", display_name="Pesto", category=IngredientCategory.CONDIMENTI)
    db_session.add(pesto)
    await db_session.flush()
    assert await planning_concluded(db_session, conversation, TODAY) is False

    # il giro con quello che c'è: messa ufficiale, poi la sua scheda applicata
    proposta = await proponi(db_session, chat, OFFICIAL, ProposedMeal(VEN, D, "Orata", None))
    assert await planning_concluded(db_session, conversation, TODAY) is False
    (orata,) = (await place_proposal(db_session, proposta.id, replace=False, now=now())).meals
    assert await planning_concluded(db_session, conversation, TODAY) is False
    scheda = await propose_card(
        db_session, meals=[orata], pantry=[], shopping=[ListProposal(pesto.id, "Pesto")],
        conversation_id=conversation.id,
    )
    assert await planning_concluded(db_session, conversation, TODAY) is False
    await apply_card(db_session, scheda.id, [])
    assert await planning_concluded(db_session, conversation, TODAY) is True

    # il giro prima della spesa: la bozza tiene aperta la conversazione
    bozza_proposta = await proponi(db_session, chat, DRAFT, ProposedMeal(SAB, L, "Lasagne", None))
    (bozza,) = (
        await place_proposal(db_session, bozza_proposta.id, replace=False, now=now())
    ).meals
    lista = await propose_card(
        db_session, meals=[bozza], pantry=[], shopping=[ListProposal(None, "Besciamella")],
        conversation_id=conversation.id,
    )
    await apply_card(db_session, lista.id, [])
    assert await planning_concluded(db_session, conversation, TODAY) is False

    ufficiale = await proponi(db_session, chat, OFFICIAL, ProposedMeal(SAB, L, "Lasagne", None))
    (lasagne,) = (await place_proposal(db_session, ufficiale.id, replace=False, now=now())).meals
    assert lasagne.id == bozza.id and lasagne.status == "official"
    assert await planning_concluded(db_session, conversation, TODAY) is False
    sua = await propose_card(
        db_session, meals=[lasagne], pantry=[], shopping=[ListProposal(pesto.id, "Pesto")],
        conversation_id=conversation.id,
    )
    await apply_card(db_session, sua.id, [])
    assert await planning_concluded(db_session, conversation, TODAY) is True


async def test_la_bozza_ufficializzata_a_mano_conclude(db_session, chat):
    """La bozza resa ufficiale da «Rendi ufficiale» non tiene più aperta la conversazione:
    basta la scheda applicata dopo la messa."""
    conversation, _ = chat
    proposta = await proponi(db_session, chat, DRAFT, ProposedMeal(SAB, L, "Lasagne", None))
    (bozza,) = (await place_proposal(db_session, proposta.id, replace=False, now=now())).meals
    lista = await propose_card(
        db_session, meals=[bozza], pantry=[], shopping=[ListProposal(None, "Besciamella")],
        conversation_id=conversation.id,
    )
    await apply_card(db_session, lista.id, [])
    assert await planning_concluded(db_session, conversation, TODAY) is False
    # una bozza nel passato non tiene aperto niente
    assert await planning_concluded(db_session, conversation, SAB + timedelta(days=1)) is True
    await update_meal(db_session, bozza, {"status": "official"})
    assert await planning_concluded(db_session, conversation, TODAY) is True


async def test_move_turn_products(db_session, chat):
    conversation, x = chat
    y = ConversationMessage(
        conversation_id=conversation.id, role="user", text="Riprova",
        created_at=now() + timedelta(seconds=1),
    )
    db_session.add(y)
    await db_session.flush()
    proposta = await proponi(db_session, chat, OFFICIAL, ProposedMeal(VEN, D, "Orata", None))
    (meal,) = (await place_proposal(db_session, proposta.id, replace=False, now=now())).meals
    scheda = await propose_card(
        db_session, meals=[meal], pantry=[], shopping=[ListProposal(None, "Limoni")],
        conversation_id=conversation.id, turn_message_id=x.id,
    )
    recipe = await create_recipe(
        db_session, title="Orata", description=None, instructions="", servings=2,
        source=RecipeSource.MANUAL, source_ref=None, ingredients=[], embedding=None,
    )
    change = RecipeChange(
        meal_id=meal.id, recipe_id=recipe.id, conversation_id=conversation.id,
        turn_message_id=x.id, created_recipe=True, summary="Ricetta scritta",
        before={}, after={}, changed={},
    )
    db_session.add(change)
    await db_session.flush()

    await move_turn_products(db_session, from_message_id=x.id, to_message_id=y.id)

    await db_session.refresh(proposta)
    await db_session.refresh(change)
    assert proposta.turn_message_id == y.id
    assert change.turn_message_id == y.id
    (card,) = await cards_of(db_session, conversation.id)
    assert card.id == scheda.id and card.turn_message_id == y.id
    assert card.rows[0].label == "Limoni"


async def test_le_conversazioni_di_pianificazione(db_session):
    assert await latest_planning(db_session) is None
    prima = await create_planning(db_session)
    seconda = await create_planning(db_session, focus=(VEN, D))
    assert (seconda.focus_day, seconda.focus_slot) == (VEN, "dinner")
    assert (await latest_planning(db_session)).id == seconda.id
    await set_focus(db_session, prima, (SAB, L))
    assert (prima.focus_day, prima.focus_slot) == (SAB, "lunch")
    await set_focus(db_session, prima, None)
    assert (prima.focus_day, prima.focus_slot) == (None, None)
