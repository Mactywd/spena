"""Semina e pulizia per le prove della pianificazione in `frontend/e2e/`. Non è un test di
pytest.

Lo stack e2e non ha la chiave API di Claude: la chat vera risponde 503 (spec §9). Le proposte e
le schede dei cambi nascono solo quando Claude chiama i suoi strumenti, e senza Claude non
si raggiungono: le scrive questo file, passando dai servizi veri (`create_planning`,
`propose_meals`, `create_meal`, `propose_card`, `stock_one`, `give_up_meals`), così lo stato
seminato è uno stato che il codice sa produrre. Nessuna rete.

Su posti lontani da quelli delle altre prove (dal giorno +30 al +33, nel giorno di Roma),
con piatti, ingredienti e voci di dispensa il cui nome comincia per «e2e-plan»:

- in dispensa «e2e-plan ricotta» e «e2e-plan parmigiano», tutte e due disponibili;
- una conversazione di pianificazione: Mattia chiede, Claude propone un pasto **ufficiale**
  per la cena del giorno +32; poi Mattia chiede una bozza per la spesa, e Claude propone
  una **bozza** per il pranzo e la cena del giorno +30. La bozza è aperta, la proposta
  ufficiale `superseded`: una proposta nuova sostituisce quelle aperte della stessa
  conversazione (decisione 12), e due proposte aperte insieme sono uno stato che il codice
  non produce;
- un pasto ufficiale alla cena del giorno +33, senza ricetta e con l'avviso del limite del
  piano (`give_up_meals`, come la coda delle ricette quando il limite la ferma), e una
  scheda dei cambi **proposta** per lui: ricotta → «Finito», parmigiano → «Quasi finito», e
  la ricotta in lista (ci va da sé, perché finisce: decisione 19).

Si lancia dentro il container del backend, dove `./backend` è montato su `/app`:

    $E2E exec -T backend python tests/e2e_planning.py seed
    # stampa {"conversation", "proposal_draft", "proposal_official", "card", "meal"}
    $E2E exec -T backend python tests/e2e_planning.py interrupted
    # stampa {"meal"}: un pasto «e2e-plan» col messaggio di Mattia e la risposta interrotta
    $E2E exec -T backend python tests/e2e_planning.py clean

`clean` si può chiamare prima di seminare: toglie anche gli avanzi di un giro interrotto, e
quello che le prove hanno fatto (i pasti messi nella settimana, la scheda inversa, la scheda
vuota di «Rendi ufficiale», le voci aggiunte in lista). Scrive e cancella nel database,
quindi **si rifiuta di partire fuori dallo stack e2e**: vuole `SPENA_E2E=1`, che sta solo
in `.env.e2e`.

Non si chiama `test_*.py` apposta: pytest non lo raccoglie.
"""

import os
import sys

if os.environ.get("SPENA_E2E") != "1":
    raise SystemExit(
        "e2e_planning.py scrive e cancella nel database: gira solo sullo stack "
        "spena-e2e, che porta SPENA_E2E=1 da .env.e2e. Qui manca, e non parto."
    )

import asyncio  # noqa: E402
import json  # noqa: E402
from datetime import UTC, date, datetime, timedelta  # noqa: E402

from sqlalchemy import Text, and_, cast, delete, or_, select  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.db.models.change_card import ChangeCard, ChangeCardRow  # noqa: E402
from app.db.models.conversation import (  # noqa: E402
    Conversation,
    ConversationMessage,
    MessageRole,
    MessageStatus,
)
from app.db.models.ingredient import Ingredient, IngredientCategory  # noqa: E402
from app.db.models.meal import Meal  # noqa: E402
from app.db.models.pantry import PantryItem  # noqa: E402
from app.db.models.planning import MealProposal, ProposalKind  # noqa: E402
from app.db.models.recipe import Recipe  # noqa: E402
from app.db.models.shopping import ShoppingListItem  # noqa: E402
from app.domain.meal_chat import FailureKind, failure_notice  # noqa: E402
from app.domain.meals import MealSlot  # noqa: E402
from app.domain.rules import PantryStatus, today_in_pantry  # noqa: E402
from app.repositories.conversations import (  # noqa: E402
    create_planning,
    get_or_create_dish_conversation,
)
from app.repositories.ingredients import create_ingredient, delete_ingredient_if_unused  # noqa: E402
from app.repositories.pantry import stock_one  # noqa: E402
from app.services.change_cards import PantryProposal, propose_card  # noqa: E402
from app.services.meals import create_meal  # noqa: E402
from app.services.planning import ProposedMeal, propose_meals  # noqa: E402
from app.services.recipe_jobs import give_up_meals  # noqa: E402

MARK = "e2e-plan"
RICOTTA = f"{MARK} ricotta"
PARMIGIANO = f"{MARK} parmigiano"
DRAFT_LUNCH = f"{MARK} Insalata di farro e ceci"
DRAFT_DINNER = f"{MARK} Merluzzo al forno"
OFFICIAL_DISH = f"{MARK} Pasta ricotta e spinaci"
CARD_DISH = f"{MARK} Pasta ricotta e parmigiano"
INTERRUPTED_DISH = f"{MARK} Riso e zucchine"


def _seeded_places(today: date) -> list[tuple[date, MealSlot]]:
    """I posti della semina: la bozza (+30, pranzo e cena), la proposta ufficiale (+32, cena)
    e il pasto con la scheda (+33, cena)."""
    return [
        (today + timedelta(days=30), MealSlot.LUNCH),
        (today + timedelta(days=30), MealSlot.DINNER),
        (today + timedelta(days=32), MealSlot.DINNER),
        (today + timedelta(days=33), MealSlot.DINNER),
        (today + timedelta(days=34), MealSlot.DINNER),
    ]


def _message(conversation_id, role: MessageRole, text: str, at: datetime, reply_to=None):
    # `created_at` scritto qui: nella stessa transazione `now()` è lo stesso istante per
    # tutti, e l'ordine dei messaggi si perderebbe
    return ConversationMessage(
        conversation_id=conversation_id,
        role=role.value,
        text=text,
        status=MessageStatus.SENT.value,
        reply_to_id=reply_to,
        created_at=at,
    )


async def seed() -> dict:
    await clean()
    now = datetime.now(UTC)
    today = today_in_pantry(now)
    async with SessionLocal() as session:
        ricotta = await create_ingredient(
            session, name=RICOTTA, display_name=RICOTTA, category=IngredientCategory.LATTICINI
        )
        parmigiano = await create_ingredient(
            session, name=PARMIGIANO, display_name=PARMIGIANO,
            category=IngredientCategory.LATTICINI,
        )
        ricotta_item = await stock_one(
            session, ingredient_id=ricotta.id, product_id=None, expires_on=None, barcode=None
        )
        parmigiano_item = await stock_one(
            session, ingredient_id=parmigiano.id, product_id=None, expires_on=None, barcode=None
        )

        conversation = await create_planning(session)
        asked = _message(
            conversation.id, MessageRole.USER,
            "Cosa mi proponi con quello che c'è in casa?", now - timedelta(minutes=10),
        )
        session.add(asked)
        await session.flush()
        official = await propose_meals(
            session,
            conversation_id=conversation.id,
            turn_message_id=asked.id,
            kind=ProposalKind.OFFICIAL,
            meals=[
                ProposedMeal(
                    day=today + timedelta(days=32), slot=MealSlot.DINNER,
                    dish=OFFICIAL_DISH, sides="insalata verde",
                ),
            ],
            today=today,
        )
        session.add(_message(
            conversation.id, MessageRole.ASSISTANT,
            "La ricotta è aperta da qualche giorno: la finirei con una pasta e gli spinaci.",
            now - timedelta(minutes=9), reply_to=asked.id,
        ))
        later = _message(
            conversation.id, MessageRole.USER,
            "Facciamo prima una bozza per la spesa: pranzo e cena dello stesso giorno.",
            now - timedelta(minutes=6),
        )
        session.add(later)
        await session.flush()
        draft = await propose_meals(
            session,
            conversation_id=conversation.id,
            turn_message_id=later.id,
            kind=ProposalKind.DRAFT,
            meals=[
                ProposedMeal(
                    day=today + timedelta(days=30), slot=MealSlot.LUNCH,
                    dish=DRAFT_LUNCH, sides="pane · una mela",
                ),
                ProposedMeal(
                    day=today + timedelta(days=30), slot=MealSlot.DINNER,
                    dish=DRAFT_DINNER, sides="patate al forno",
                ),
            ],
            today=today,
        )
        session.add(_message(
            conversation.id, MessageRole.ASSISTANT,
            "Ecco la bozza: il farro a pranzo, il pesce la sera. Mettila nella settimana e ti "
            "dico cosa scrivere in lista.",
            now - timedelta(minutes=5), reply_to=later.id,
        ))

        meal = await create_meal(
            session, day=today + timedelta(days=33), slot=MealSlot.DINNER, dish=CARD_DISH,
            sides="insalata",
        )
        card = await propose_card(
            session,
            meals=[meal],
            pantry=[
                PantryProposal(pantry_item_id=ricotta_item.id, to_status=PantryStatus.FINISHED),
                PantryProposal(pantry_item_id=parmigiano_item.id, to_status=PantryStatus.LOW),
            ],
            shopping=[],
        )
        result = {
            "conversation": str(conversation.id),
            "proposal_draft": str(draft.id),
            "proposal_official": str(official.id),
            "card": str(card.id),
            "meal": str(meal.id),
        }
        meal_id = meal.id
        await session.commit()

    # l'avviso del limite di frequenza sul pasto senza ricetta, scritto come lo scrive la coda
    # delle ricette quando il limite la ferma
    await give_up_meals(SessionLocal, [meal_id], failure=FailureKind.RATE_LIMIT, like=None)
    return result


async def interrupted() -> dict:
    """Un pasto «e2e-plan» (giorno +34, cena) con la chat del piatto che finisce su una
    risposta interrotta: le due righe che scrive `_reply` quando i passaggi sono finiti."""
    await clean()
    now = datetime.now(UTC)
    today = today_in_pantry(now)
    async with SessionLocal() as session:
        meal = await create_meal(
            session, day=today + timedelta(days=34), slot=MealSlot.DINNER,
            dish=INTERRUPTED_DISH,
        )
        conversation = await get_or_create_dish_conversation(session, meal.id)
        asked = _message(
            conversation.id, MessageRole.USER,
            "Riscrivimi la ricetta con le zucchine e il riso integrale.",
            now - timedelta(minutes=3),
        )
        session.add(asked)
        await session.flush()
        answer = _message(
            conversation.id, MessageRole.ASSISTANT,
            "Ho cominciato dal riso: prima lo tosto, poi aggiungo le zucchine.",
            now - timedelta(minutes=2), reply_to=asked.id,
        )
        answer.notice = failure_notice(FailureKind.MAX_TURNS, None, now)
        session.add(answer)
        result = {"meal": str(meal.id)}
        await session.commit()
    return result


async def clean() -> dict:
    today = today_in_pantry(datetime.now(UTC))
    async with SessionLocal() as session:
        ingredient_ids = list(
            (
                await session.execute(
                    select(Ingredient.id).where(Ingredient.name.like(f"{MARK}%"))
                )
            ).scalars()
        )
        conversation_ids = list(
            (
                await session.execute(
                    select(MealProposal.conversation_id)
                    .where(cast(MealProposal.rows, Text).like(f"%{MARK}%"))
                    .distinct()
                )
            ).scalars()
        )
        # le schede seminate e quelle nate dalle prove (l'inversa, la vuota di «Rendi
        # ufficiale»): il titolo porta il piatto, le righe gli ingredienti
        card_rows = select(ChangeCardRow.card_id).where(
            or_(
                ChangeCardRow.ingredient_id.in_(ingredient_ids),
                ChangeCardRow.label.like(f"{MARK}%"),
            )
        )
        cards = await session.execute(
            delete(ChangeCard).where(
                or_(
                    ChangeCard.title.like(f"%{MARK}%"),
                    ChangeCard.conversation_id.in_(conversation_ids),
                    ChangeCard.id.in_(card_rows),
                )
            )
        )
        places = [
            and_(Meal.day == day, Meal.slot == slot.value)
            for day, slot in _seeded_places(today)
        ]
        meals = await session.execute(
            delete(Meal).where(or_(Meal.dish.like(f"{MARK}%"), *places))
        )
        recipes = await session.execute(delete(Recipe).where(Recipe.title.like(f"{MARK}%")))
        conversations = await session.execute(
            delete(Conversation).where(Conversation.id.in_(conversation_ids))
        )
        shopping = await session.execute(
            delete(ShoppingListItem).where(
                or_(
                    ShoppingListItem.ingredient_id.in_(ingredient_ids),
                    ShoppingListItem.raw_text.like(f"{MARK}%"),
                )
            )
        )
        pantry = await session.execute(
            delete(PantryItem).where(PantryItem.ingredient_id.in_(ingredient_ids))
        )
        ingredients = 0
        for ingredient_id in ingredient_ids:
            if await delete_ingredient_if_unused(session, ingredient_id):
                ingredients += 1
        await session.commit()
    return {
        "cards": cards.rowcount,
        "meals": meals.rowcount,
        "recipes": recipes.rowcount,
        "conversations": conversations.rowcount,
        "shopping": shopping.rowcount,
        "pantry": pantry.rowcount,
        "ingredients": ingredients,
    }


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "seed" and len(sys.argv) == 2:
        print(json.dumps(asyncio.run(seed())))
    elif command == "interrupted" and len(sys.argv) == 2:
        print(json.dumps(asyncio.run(interrupted())))
    elif command == "clean" and len(sys.argv) == 2:
        print(json.dumps(asyncio.run(clean())))
    else:
        raise SystemExit("uso: e2e_planning.py seed | interrupted | clean")


if __name__ == "__main__":
    main()
