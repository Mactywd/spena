"""Il registro dei giri della chat (decisione 11): nel processo, perché uvicorn ha un solo
worker, e **una sola risposta alla volta per conversazione**.

Il giro gira in un task suo, creato qui e tenuto finché non finisce, non nella richiesta
che l'ha avviato. Chi legge riceve gli eventi da una coda sua; se se ne va (il telefono si
blocca, Starlette cancella lo stream) toglie solo la sua coda, e il giro continua: la
risposta si trova riaprendo il piatto.
"""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable

from app.services.meal_chat import ChatEvent, Emit

logger = logging.getLogger(__name__)

_END = object()


class TurnBusy(RuntimeError):
    """La conversazione ha già un giro vivo: la rotta lo controlla prima (409)."""


class TurnRegistry:
    def __init__(self) -> None:
        self._tasks: dict[uuid.UUID, asyncio.Task[None]] = {}

    def running(self, conversation_id: uuid.UUID) -> bool:
        task = self._tasks.get(conversation_id)
        return task is not None and not task.done()

    def start(
        self, conversation_id: uuid.UUID, run: Callable[[Emit], Awaitable[None]]
    ) -> AsyncIterator[ChatEvent]:
        """Avvia il giro subito, anche se nessuno legge, e restituisce gli eventi per chi
        legge: l'iteratore finisce quando il giro finisce."""
        if self.running(conversation_id):
            raise TurnBusy(str(conversation_id))
        queue: asyncio.Queue[object] = asyncio.Queue()
        readers: set[asyncio.Queue[object]] = {queue}

        async def emit(event: ChatEvent) -> None:
            for reader in list(readers):
                reader.put_nowait(event)

        async def runner() -> None:
            try:
                await run(emit)
            except Exception:
                logger.exception("Il giro della conversazione %s è caduto", conversation_id)
            finally:
                for reader in list(readers):
                    reader.put_nowait(_END)
                if self._tasks.get(conversation_id) is asyncio.current_task():
                    del self._tasks[conversation_id]

        self._tasks[conversation_id] = asyncio.create_task(runner())
        return self._read(queue, readers)

    @staticmethod
    async def _read(
        queue: asyncio.Queue[object], readers: set[asyncio.Queue[object]]
    ) -> AsyncIterator[ChatEvent]:
        try:
            while True:
                item = await queue.get()
                if item is _END:
                    return
                assert isinstance(item, ChatEvent)
                yield item
        finally:
            # chi legge se ne va: si toglie solo la sua coda, il giro continua
            readers.discard(queue)

    async def wait(self, conversation_id: uuid.UUID) -> None:
        """Aspetta che il giro finisca (per i test e per lo spegnimento)."""
        task = self._tasks.get(conversation_id)
        if task is not None:
            await asyncio.wait({task})


_registry = TurnRegistry()


def get_turn_registry() -> TurnRegistry:
    """La dipendenza FastAPI: il registro del processo."""
    return _registry
