"""Lo storico delle chiamate all'LLM, una riga per chiamata.

Esiste perché l'attribuzione di OpenRouter non risponde alla domanda che conta qui.
Per loro un'app è un indirizzo — `HTTP-Referer` è la chiave, e `X-Title` ne cambia
solo il nome visualizzato — quindi mandare un titolo diverso per sezione non
produrrebbe cinque voci di spesa, ma un'app sola con il nome che sfarfalla. La
divisione per sezione la teniamo noi.

Il costo non è stimato: è quello che OpenRouter dichiara in `usage.cost` a ogni
risposta. Stimarlo da token e listino sbaglierebbe, perché i provider hanno prezzi
diversi, la cache ha una voce sua, e l'instradamento per prezzo può cambiare provider
fra due chiamate consecutive.
"""

from datetime import datetime

from sqlalchemy import DateTime, Boolean, Float, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.db.models.base import UUIDMixin


class LlmCall(UUIDMixin, Base):
    __tablename__ = "llm_calls"
    __table_args__ = (
        # La domanda vera è sempre «in questo periodo, quanto per sezione»: l'indice
        # segue quell'ordine e non l'inverso.
        Index("ix_llm_calls_created_at_call_site", "created_at", "call_site"),
    )

    call_site: Mapped[str] = mapped_column(String(40), nullable=False)
    ok: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # Tutti annullabili, e non per pigrizia: `cost` è dichiarato nullable da
    # OpenRouter stesso, una richiesta rifiutata non porta `usage` affatto, e di una
    # chiamata fallita non sappiamo se ci è stata addebitata. Zero direbbe «gratis»,
    # che è un'affermazione; l'assenza è la verità. Stessa regola dei nutrienti.
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    generation_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
