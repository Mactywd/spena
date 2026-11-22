"""Le ricette dei pasti ufficiali, scritte da Claude in coda (piano 6c, decisioni 15, 16, 17).

Quando i pasti diventano ufficiali (la messa nella settimana, o «Chiedi la ricetta a
Claude» su un pasto), spena chiede a Claude la ricetta di ognuno: un giro per pasto
(`generate_meal_recipe`), in una coda nel processo (`RecipeJobs`), perché uvicorn ha un
solo worker, come il registro dei giri della chat.

«Ricetta in preparazione» è vera solo se la coda ha davvero quel pasto (`live_ids`): un
pasto con `recipe_requested_at` che nessuna coda ha più (il container è ripartito) diventa,
alla prima lettura, un avviso scritto nel database (`settle_orphans`, decisione 16).
"""

import asyncio
import logging
import uuid
from collections import Counter
from collections.abc import Awaitable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.meal import Meal
from app.db.models.recipe_change import RecipeChange
from app.domain.meal_chat import (
    RECIPE_EFFORT,
    RECIPE_MAX_TURNS,
    FailureKind,
    can_chat,
    failure_notice,
)
from app.domain.meals import MealSlot
from app.domain.rules import today_in_pantry
from app.repositories.llm_calls import record_llm_call
from app.repositories.meals import get_meal
from app.services.claude.client import (
    ClaudeClient,
    ClaudeFailure,
    TurnFailed,
    TurnFinished,
    llm_usage,
)
from app.services.claude.prompts import DishContext, recipe_system_prompt, render_recipe_prompt
from app.services.claude.tools import TurnContext, recipe_tools
from app.services.llm import LlmCallSite
from app.services.meal_chat import chat_history
from app.services.utensils import UTENSILS_STEPS_RULE, utensils_prompt_block

logger = logging.getLogger(__name__)

INTERRUPTED_RECIPE_NOTICE = (
    "La ricetta non è arrivata: chiedila di nuovo a Claude o scrivila a mano."
)
NOT_WRITTEN_NOTICE = (
    "Claude ha risposto senza scrivere la ricetta: chiedila di nuovo o scrivila a mano."
)
# I guasti che valgono per tutti i pasti: chiamare Claude per il pasto dopo darebbe lo stesso
# guasto, quindi la coda si ferma (decisione 15).
TERMINAL_FAILURES = frozenset(
    {FailureKind.RATE_LIMIT, FailureKind.CREDIT, FailureKind.AUTH, FailureKind.NOT_CONFIGURED}
)


def wants_recipe(meal: Meal) -> bool:
    """Un pasto a cui Claude può scrivere la ricetta: ufficiale, a casa, non avanzo (le
    stesse condizioni della chat del piatto), e ancora senza ricetta."""
    return can_chat(meal) and meal.recipe_id is None


# --- un pasto ------------------------------------------------------------------------------


async def _no_change(change: RecipeChange) -> None:
    """Il giro della ricetta non ha una chat a cui mandare la modifica (C-R4)."""


@dataclass(frozen=True)
class _Outcome:
    failure: ClaudeFailure | None
    finished: TurnFinished | None


async def _ask_claude(
    session: AsyncSession,
    client: ClaudeClient,
    meal: Meal,
    conversation_id: uuid.UUID | None,
    timeout_seconds: float,
) -> _Outcome:
    now = datetime.now(UTC)
    lock = asyncio.Lock()
    ctx = TurnContext(
        session=session, lock=lock, today=today_in_pantry(now), meal_id=meal.id,
        conversation_id=None, turn_message_id=None, on_change=_no_change, create_only=True,
    )
    system_prompt = recipe_system_prompt(
        await utensils_prompt_block(session, rule=UTENSILS_STEPS_RULE)
    )
    history = (
        await chat_history(session, conversation_id) if conversation_id is not None else []
    )
    context = DishContext(
        today=ctx.today, day=meal.day, slot=MealSlot(meal.slot), dish=meal.dish,
        sides=meal.sides, recipe=None,
    )
    prompt = render_recipe_prompt(context, history)
    tools = recipe_tools(ctx)
    # Le letture sono finite: niente transazione aperta per tutto il tempo di Claude.
    await session.commit()

    stream = client.run(
        system_prompt=system_prompt, prompt=prompt, tools=tools,
        effort=RECIPE_EFFORT, max_turns=RECIPE_MAX_TURNS,
    )
    timer = asyncio.timeout(timeout_seconds)
    failure: ClaudeFailure | None = None
    finished: TurnFinished | None = None
    try:
        async with timer:
            async for event in stream:
                if isinstance(event, TurnFinished):
                    finished = event
                    break
                if isinstance(event, TurnFailed):
                    failure = event.failure
                    break
    except TimeoutError:
        if timer.expired():
            failure = ClaudeFailure(FailureKind.TIMEOUT, None, "tempo massimo")
        else:
            logger.exception("Il giro della ricetta del pasto %s è caduto", meal.id)
            failure = ClaudeFailure(FailureKind.UNAVAILABLE, None, "eccezione")
    except Exception:
        logger.exception("Il giro della ricetta del pasto %s è caduto", meal.id)
        failure = ClaudeFailure(FailureKind.UNAVAILABLE, None, "eccezione")
    finally:
        aclose = getattr(stream, "aclose", None)
        if aclose is not None:
            try:
                await aclose()
            except Exception:
                logger.exception("La chiusura dello stream di Claude è fallita")
    if failure is None and finished is None:
        failure = ClaudeFailure(FailureKind.INTERRUPTED, None, "il flusso è finito senza risultato")
    return _Outcome(failure, finished)


async def _settle_meal(
    session_factory: async_sessionmaker[AsyncSession],
    meal_id: uuid.UUID,
    outcome: _Outcome,
) -> None:
    """La fine del giro, in una sessione nuova: il pasto si rilegge per id (una scrittura
    annullata a metà dal tempo massimo lascia la sessione del giro con oggetti scaduti)."""
    now = datetime.now(UTC)
    async with session_factory() as session:
        meal = await get_meal(session, meal_id)
        if meal is not None:
            meal.recipe_requested_at = None
            if meal.recipe_id is not None or not can_chat(meal):
                meal.recipe_notice = None
            elif outcome.failure is not None and outcome.failure.kind != FailureKind.MAX_TURNS:
                meal.recipe_notice = failure_notice(
                    outcome.failure.kind, outcome.failure.resets_at, now
                )
            else:
                meal.recipe_notice = NOT_WRITTEN_NOTICE
        if outcome.finished is not None:
            await record_llm_call(
                session,
                call_site=LlmCallSite.MEAL_RECIPE,
                usage=llm_usage(outcome.finished.usage),
                ok=True,
            )
        elif outcome.failure is not None and outcome.failure.kind != FailureKind.NOT_CONFIGURED:
            await record_llm_call(
                session,
                call_site=LlmCallSite.MEAL_RECIPE,
                usage=llm_usage(outcome.failure.usage),
                ok=False,
            )
        await session.commit()


async def _generate(
    session_factory: async_sessionmaker[AsyncSession],
    client: ClaudeClient,
    meal_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    timeout_seconds: float,
) -> FailureKind | None:
    async with session_factory() as session:
        meal = await get_meal(session, meal_id)
        if meal is None:
            return None
        if not wants_recipe(meal):
            # già con una ricetta (scritta a mano nel frattempo), o non può averne una
            meal.recipe_requested_at = None
            if not can_chat(meal):
                meal.recipe_notice = None
            await session.commit()
            return None
        outcome = await _ask_claude(session, client, meal, conversation_id, timeout_seconds)
        # quello che `write_recipe` ha committato resta; una scrittura interrotta a metà no
        try:
            await session.rollback()
        except Exception:
            logger.exception("Il rollback del giro della ricetta del pasto %s è fallito", meal_id)
    await _settle_meal(session_factory, meal_id, outcome)
    return None if outcome.failure is None else outcome.failure.kind


async def give_up_meals(
    session_factory: async_sessionmaker[AsyncSession],
    meal_ids: Sequence[uuid.UUID],
    *,
    failure: FailureKind | None,
    like: uuid.UUID | None,
) -> None:
    """I pasti che la coda non farà più: niente più «in preparazione», e l'avviso del
    guasto che li ha fermati — quello scritto sul pasto `like` (con l'ora del limite), o
    l'avviso del guasto, o l'interruzione. Un pasto che ha già la ricetta non ha avviso."""
    if not meal_ids:
        return
    now = datetime.now(UTC)
    async with session_factory() as session:
        notice = None
        if like is not None:
            source = await get_meal(session, like)
            notice = source.recipe_notice if source is not None else None
        if notice is None:
            notice = (
                failure_notice(failure, None, now)
                if failure is not None
                else INTERRUPTED_RECIPE_NOTICE
            )
        for meal_id in meal_ids:
            meal = await get_meal(session, meal_id)
            if meal is None:
                continue
            meal.recipe_requested_at = None
            meal.recipe_notice = notice if wants_recipe(meal) else None
        await session.commit()


async def _write_crash(session_factory: async_sessionmaker[AsyncSession], meal_id: uuid.UUID) -> None:
    try:
        await give_up_meals(
            session_factory, [meal_id], failure=FailureKind.UNAVAILABLE, like=None
        )
    except Exception:
        logger.exception("Il pasto %s non ha ricevuto l'avviso", meal_id)


async def generate_meal_recipe(
    session_factory: async_sessionmaker[AsyncSession],
    client: ClaudeClient,
    *,
    meal_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    timeout_seconds: float,
) -> FailureKind | None:
    """Un giro: la ricetta di un pasto. Rilegge il pasto (sparito, non ufficiale, fuori
    casa, avanzo o già con una ricetta: non chiama Claude), gli manda il pasto e la
    conversazione in cui è stato deciso, con gli strumenti di lettura e `write_recipe` in
    sola creazione. Alla fine il pasto non è più «in preparazione»: ha la ricetta, o
    l'avviso del guasto, o `NOT_WRITTEN_NOTICE`. Torna il guasto, `None` se non ce n'è.
    Un'eccezione imprevista lascia il pasto usabile, con l'avviso «non risponde»."""
    try:
        return await _generate(
            session_factory, client, meal_id, conversation_id, timeout_seconds
        )
    except Exception:
        logger.exception("La ricetta del pasto %s è caduta", meal_id)
        await _write_crash(session_factory, meal_id)
        return FailureKind.UNAVAILABLE


# --- la coda -------------------------------------------------------------------------------


class RecipeRun(Protocol):
    """Quello che la coda fa per un pasto, e per quelli che non farà più."""

    def __call__(
        self, meal_id: uuid.UUID, conversation_id: uuid.UUID | None
    ) -> Awaitable[FailureKind | None]: ...

    async def give_up(
        self,
        meal_ids: Sequence[uuid.UUID],
        *,
        failure: FailureKind | None,
        like: uuid.UUID | None,
    ) -> None: ...


@dataclass(frozen=True)
class ClaudeRecipeRun:
    session_factory: async_sessionmaker[AsyncSession]
    client: ClaudeClient
    timeout_seconds: float

    async def __call__(
        self, meal_id: uuid.UUID, conversation_id: uuid.UUID | None
    ) -> FailureKind | None:
        return await generate_meal_recipe(
            self.session_factory, self.client, meal_id=meal_id,
            conversation_id=conversation_id, timeout_seconds=self.timeout_seconds,
        )

    async def give_up(
        self,
        meal_ids: Sequence[uuid.UUID],
        *,
        failure: FailureKind | None,
        like: uuid.UUID | None,
    ) -> None:
        await give_up_meals(self.session_factory, meal_ids, failure=failure, like=like)


def recipe_run(
    session_factory: async_sessionmaker[AsyncSession],
    client: ClaudeClient,
    *,
    timeout_seconds: float,
) -> ClaudeRecipeRun:
    """Il `run` di `RecipeJobs.enqueue`: i giri con questo client e queste sessioni."""
    return ClaudeRecipeRun(session_factory, client, timeout_seconds)


class RecipeJobs:
    """La coda delle ricette (decisione 15): **una coda alla volta, un pasto alla volta**.

    Ufficializzare sette pasti non lancia sette processi di Claude Code insieme: ogni giro
    è un processo dell'SDK con il suo consumo, e sette in parallelo
    arriverebbero al limite tutti insieme. Un `asyncio.Lock` fa girare una coda (un
    `enqueue`) alla volta; dentro, i pasti uno dopo l'altro.

    **Ogni pasto si committa da sé**: `write_recipe` committa la ricetta, e la fine del
    giro (niente più «in preparazione», o l'avviso) ha la sua transazione. Così
    un'interruzione a metà coda — il limite di frequenza, il container che riparte — lascia
    i pasti già fatti con la loro ricetta, e ognuno degli altri usabile, con l'avviso e
    «Chiedi la ricetta a Claude».

    **Cosa ferma la coda**: un guasto che vale per tutti (`TERMINAL_FAILURES`: il limite
    di frequenza, il credito, la chiave, Claude non collegato) scrive lo stesso avviso su
    ogni pasto rimasto, senza chiamare Claude, e chiude la coda. Un guasto del singolo (il tempo
    massimo, un errore) resta su quel pasto e la coda passa al pasto dopo.

    `live_ids` sono i pasti di tutte le code non finite, in attesa o in corso: un pasto ne
    esce solo dopo che il suo giro ha committato la fine, così una lettura non lo vede mai
    né «in preparazione» né orfano a torto.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._live: Counter[uuid.UUID] = Counter()
        self._tasks: set[asyncio.Task[None]] = set()

    def live_ids(self) -> frozenset[uuid.UUID]:
        return frozenset(meal_id for meal_id, n in self._live.items() if n > 0)

    def enqueue(
        self,
        meal_ids: Sequence[uuid.UUID],
        conversation_id: uuid.UUID | None,
        run: RecipeRun,
    ) -> None:
        """Mette i pasti in coda subito (`live_ids` li ha appena torna) e avvia la coda in
        un task suo, che non dipende dalla richiesta."""
        ids = list(dict.fromkeys(meal_ids))
        if not ids:
            return
        self._live.update(ids)
        task = asyncio.create_task(self._drain(ids, conversation_id, run))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def _release(self, meal_id: uuid.UUID) -> None:
        self._live[meal_id] -= 1
        if self._live[meal_id] <= 0:
            del self._live[meal_id]

    async def _drain(
        self, ids: list[uuid.UUID], conversation_id: uuid.UUID | None, run: RecipeRun
    ) -> None:
        pending = list(ids)
        try:
            async with self._lock:
                while pending:
                    meal_id = pending[0]
                    try:
                        failure = await run(meal_id, conversation_id)
                    except Exception:
                        logger.exception("La coda delle ricette è caduta sul pasto %s", meal_id)
                        failure = None
                        await self._give_up(run, [meal_id], FailureKind.UNAVAILABLE, None)
                    pending.pop(0)
                    self._release(meal_id)
                    if failure in TERMINAL_FAILURES:
                        await self._give_up(run, pending, failure, meal_id)
                        break
        finally:
            # i pasti rimasti (la coda fermata, o cancellata allo spegnimento) escono da
            # `live_ids`: se non hanno avuto l'avviso, la prossima lettura li trova orfani
            for meal_id in pending:
                self._release(meal_id)

    @staticmethod
    async def _give_up(
        run: RecipeRun,
        meal_ids: Sequence[uuid.UUID],
        failure: FailureKind | None,
        like: uuid.UUID | None,
    ) -> None:
        try:
            await run.give_up(meal_ids, failure=failure, like=like)
        except Exception:
            logger.exception("I pasti %s non hanno ricevuto l'avviso", list(meal_ids))

    async def wait_idle(self) -> None:
        """Aspetta che tutte le code finiscano (per i test e per lo spegnimento)."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)


_jobs = RecipeJobs()


def get_recipe_jobs() -> RecipeJobs:
    """La dipendenza FastAPI: la coda del processo."""
    return _jobs


# --- le preparazioni orfane ----------------------------------------------------------------


async def settle_orphans(
    session: AsyncSession, meals: Sequence[Meal], live: frozenset[uuid.UUID]
) -> bool:
    """Decisione 16: un pasto chiesto (`recipe_requested_at`) che nessuna coda viva ha più
    (il container è ripartito) non è «in preparazione»: diventa
    `INTERRUPTED_RECIPE_NOTICE`, scritto nel database. Chi chiama prende `live` **prima**
    di leggere i pasti, e fa `commit` se questa torna vero (ha scritto)."""
    wrote = False
    for meal in meals:
        if meal.recipe_requested_at is None or meal.id in live:
            continue
        meal.recipe_requested_at = None
        meal.recipe_notice = INTERRUPTED_RECIPE_NOTICE if wants_recipe(meal) else None
        wrote = True
    if wrote:
        await session.flush()
    return wrote

