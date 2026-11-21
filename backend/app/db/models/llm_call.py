"""Lo storico delle chiamate all'LLM, una riga per chiamata.

Esiste perché l'attribuzione di OpenRouter non risponde alla domanda che conta qui.
Per loro un'app è un indirizzo — `HTTP-Referer` è la chiave, e `X-Title` ne cambia
solo il nome visualizzato — quindi mandare un titolo diverso per sezione non
produrrebbe cinque voci di spesa, ma un'app sola con il nome che sfarfalla. La
divisione per sezione la teniamo noi.

Il costo, dal 2026-11-21, lo calcola spena: Anthropic dichiara i token e non il prezzo,
e `app/domain/llm_pricing.py` li moltiplica per il listino del modello, cache compresa.
Con OpenRouter era il contrario (il costo dichiarato in `usage.cost`, perché
l'instradamento per prezzo cambiava provider fra due chiamate), e le righe di prima
restano con quel costo. `cache_read_tokens` e `cache_write_tokens` sono qui perché ogni
costo si possa rifare dalla sua riga; `prompt_tokens` è tutto il prompt, cache compresa.
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

    # Tutti annullabili, e non per pigrizia: un modello che il listino non conosce non ha
    # costo, una richiesta rifiutata non porta `usage` affatto, e di una chiamata fallita
    # non sappiamo se ci è stata addebitata. Zero direbbe «gratis»,
    # che è un'affermazione; l'assenza è la verità. Stessa regola dei nutrienti.
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    generation_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    cache_read_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_write_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
