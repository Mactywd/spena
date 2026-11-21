"""Semina e pulizia per le prove della chat del piatto in `frontend/e2e/`. Non è un test
di pytest.

Lo stack e2e non ha la chiave API di Claude: la chat vera risponde 503 (spec §9). Lo stato con
una modifica di Claude e il suo «Annulla», e quello di un messaggio rimasto senza risposta
per il limite di frequenza, non si raggiungono senza Claude: li scrive questo file, passando
dai servizi veri (`create_meal`, `write_meal_recipe`, il repository delle conversazioni),
così lo stato seminato è uno stato che il codice sa produrre. Nessuna rete.

Due pasti, su posti lontani da quelli delle altre prove (la cena fra 20 giorni e il
pranzo fra 21, nel giorno di Roma), col piatto che comincia per «e2e-chat»:

- A, «e2e-chat Frittata di spinaci»: la ricetta (uova 2, spinaci 200 g, parmigiano 30 g),
  poi un messaggio di Mattia sugli spinaci surgelati, una seconda scrittura legata a quel
  giro (spinaci 150 g, «congelati, senza scongelare») e la risposta di Claude;
- B, «e2e-chat Pasta al pesto»: un messaggio di Mattia fallito, con l'avviso del limite.

Si lancia dentro il container del backend, dove `./backend` è montato su `/app`:

    $E2E exec -T backend python tests/e2e_chat.py seed    # stampa {"meal_change", "meal_failed"}
    $E2E exec -T backend python tests/e2e_chat.py clean

`clean` si può chiamare prima di seminare: toglie anche gli avanzi di un giro interrotto.
Scrive e cancella nel database, quindi **si rifiuta di partire fuori dallo stack e2e**:
vuole `SPENA_E2E=1`, che sta solo in `.env.e2e`.

Non si chiama `test_*.py` apposta: pytest non lo raccoglie.
"""

import os
import sys

if os.environ.get("SPENA_E2E") != "1":
    raise SystemExit(
        "e2e_chat.py scrive e cancella nel database: gira solo sullo stack "
        "spena-e2e, che porta SPENA_E2E=1 da .env.e2e. Qui manca, e non parto."
    )

import asyncio  # noqa: E402
import json  # noqa: E402
from datetime import UTC, datetime, timedelta  # noqa: E402

from sqlalchemy import delete, select  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.db.models.conversation import (  # noqa: E402
    ConversationMessage,
    MessageRole,
    MessageStatus,
)
from app.db.models.ingredient import Ingredient  # noqa: E402
from app.db.models.meal import Meal  # noqa: E402
from app.db.models.recipe import Recipe  # noqa: E402
from app.domain.meal_chat import FailureKind, failure_notice  # noqa: E402
from app.domain.meals import MealSlot  # noqa: E402
from app.domain.rules import IngredientRole, today_in_pantry  # noqa: E402
from app.repositories.conversations import get_or_create_dish_conversation  # noqa: E402
from app.services.meal_recipes import DraftLine, MealRecipeDraft, write_meal_recipe  # noqa: E402
from app.services.meals import create_meal  # noqa: E402

MARK = "e2e-chat"
DISH_A = f"{MARK} Frittata di spinaci"
DISH_B = f"{MARK} Pasta al pesto"


async def _ingredient(session, name: str) -> Ingredient:
    found = (
        await session.execute(select(Ingredient).where(Ingredient.name == name))
    ).scalar_one_or_none()
    if found is None:
        raise SystemExit(f"manca l'ingrediente «{name}» del seme: serve `app.cli.seed`.")
    return found


def _line(ingredient: Ingredient, quantity: str, note: str | None = None) -> DraftLine:
    return DraftLine(
        ingredient_id=ingredient.id, name=None, category=None,
        role=IngredientRole.PRIMARY, quantity_text=quantity, note=note,
    )


def _draft(lines: tuple[DraftLine, ...], summary: str) -> MealRecipeDraft:
    return MealRecipeDraft(
        title=DISH_A,
        description=None,
        instructions="Sbatti le uova, aggiungi gli spinaci e il parmigiano, cuoci in padella.",
        servings=2,
        lines=lines,
        summary=summary,
    )


async def seed() -> dict:
    await clean()
    now = datetime.now(UTC)
    today = today_in_pantry(now)
    async with SessionLocal() as session:
        uova = await _ingredient(session, "uova")
        spinaci = await _ingredient(session, "spinaci")
        parmigiano = await _ingredient(session, "parmigiano")

        meal_a = await create_meal(
            session, day=today + timedelta(days=20), slot=MealSlot.DINNER, dish=DISH_A
        )
        await write_meal_recipe(
            session,
            meal_a,
            _draft(
                (_line(uova, "2"), _line(spinaci, "200 g"), _line(parmigiano, "30 g")),
                "ricetta scritta",
            ),
        )
        conversation = await get_or_create_dish_conversation(session, meal_a.id)
        asked = ConversationMessage(
            conversation_id=conversation.id,
            role=MessageRole.USER.value,
            text="Ho gli spinaci congelati nella busta da 1 kg: quanti ne prendo?",
            status=MessageStatus.SENT.value,
            created_at=now - timedelta(minutes=5),
        )
        session.add(asked)
        await session.flush()
        await write_meal_recipe(
            session,
            meal_a,
            _draft(
                (
                    _line(uova, "2"),
                    _line(spinaci, "150 g", "congelati, senza scongelare"),
                    _line(parmigiano, "30 g"),
                ),
                "spinaci congelati, padella unica",
            ),
            conversation_id=conversation.id,
            turn_message_id=asked.id,
        )
        session.add(
            ConversationMessage(
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT.value,
                text="Ne bastano 150 g, e non serve scongelarli: vanno in padella così come sono.",
                status=MessageStatus.SENT.value,
                reply_to_id=asked.id,
                created_at=now - timedelta(minutes=4),
            )
        )

        meal_b = await create_meal(
            session, day=today + timedelta(days=21), slot=MealSlot.LUNCH, dish=DISH_B
        )
        conversation_b = await get_or_create_dish_conversation(session, meal_b.id)
        resets_at = now + timedelta(hours=3)
        session.add(
            ConversationMessage(
                conversation_id=conversation_b.id,
                role=MessageRole.USER.value,
                text="Come lo rendo più cremoso?",
                status=MessageStatus.FAILED.value,
                failure=FailureKind.RATE_LIMIT.value,
                notice=failure_notice(FailureKind.RATE_LIMIT, resets_at, now),
                created_at=now - timedelta(minutes=2),
            )
        )
        await session.commit()
        return {"meal_change": str(meal_a.id), "meal_failed": str(meal_b.id)}


async def clean() -> dict:
    async with SessionLocal() as session:
        meals = await session.execute(delete(Meal).where(Meal.dish.like(f"{MARK}%")))
        recipes = await session.execute(delete(Recipe).where(Recipe.title.like(f"{MARK}%")))
        await session.commit()
    return {"meals": meals.rowcount, "recipes": recipes.rowcount}


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "seed" and len(sys.argv) == 2:
        print(json.dumps(asyncio.run(seed())))
    elif command == "clean" and len(sys.argv) == 2:
        print(json.dumps(asyncio.run(clean())))
    else:
        raise SystemExit("uso: e2e_chat.py seed | clean")


if __name__ == "__main__":
    main()
