"""Chi decide la figura di un ingrediente in Dispensa (S12).

Una volta, per gli ingredienti che non ce l'hanno: `python -m app.cli.decide_emoji`.
L'AI sceglie solo dentro l'elenco chiuso di `app/domain/emoji.py`, a lotti di
`EMOJI_BATCH` nomi. Una risposta che non si può verificare — un numero non chiesto o già
risposto, un nome che non è quello chiesto, un'emoji fuori elenco — non si applica, e la
colonna resta vuota: la riga mostra il ripiego del reparto, e il lancio dopo la richiede.

Scrive solo dove la colonna è `NULL`, e lo controlla nella stessa UPDATE che scrive: una
figura scelta a mano in Anagrafica, «Nessuna» compresa, non si tocca, nemmeno se è stata
scelta mentre il comando girava (bozza §3.A).

Niente `decided_by` e niente undo, a differenza delle decisioni dell'import: l'emoji non
lega niente a niente — non cambia una disponibilità né una ricetta — e sbagliata si
corregge in un tocco, in Anagrafica (bozza §3.A).

I nomi si numerano, e la risposta riporta numero e nome: in un lotto di cento un modello
piccolo può scivolare di una riga, e il nome accanto al numero è ciò che lo fa vedere.
Lo schema stretto restringe l'emoji all'elenco (`enum`); la verifica qui la ripete
comunque, perché uno schema rispettato non è una risposta verificata.
"""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingredient import Ingredient
from app.domain.emoji import INGREDIENT_EMOJI, NO_EMOJI, canonical_emoji
from app.repositories.llm_calls import record_llm_call
from app.services.llm import LlmCallSite, LlmUnavailable, LlmUsage, complete_json

# Cento nomi per chiamata (bozza §3.A: «a lotti di un centinaio di nomi»). Una risposta
# è `{"n": …, "nome": …, "emoji": …}` per nome, ~20 token: duemila per lotto, la metà
# del tetto qui sotto. Sui ~900 ingredienti di produzione sono nove chiamate, qualche
# decina di migliaia di token in tutto: molto sotto il tetto di 1 $/giorno.
EMOJI_BATCH = 100
EMOJI_MAX_TOKENS = 4000

# La parola con cui l'AI dice «nessuna figura dell'elenco va bene». Non è un'emoji, e
# `canonical_emoji` la rifiuta: si traduce in `NO_EMOJI` qui, e solo qui.
NONE_ANSWER = "nessuna"

EMOJI_SYSTEM_PROMPT = (
    "Ricevi un elenco numerato di voci della dispensa di casa: ingredienti e prodotti per "
    "la casa, ciascuno col suo reparto del supermercato. Per ognuna scegli l'emoji che la "
    "fa riconoscere a colpo d'occhio, solo fra queste:\n"
    + " ".join(INGREDIENT_EMOJI)
    + "\n\nRegole:\n"
    '- "n" e "nome" vanno riscritti identici a come te li ho passati.\n'
    "- Va bene un'emoji della stessa famiglia: 🧀 per un formaggio, 🐟 per un pesce, 🥩 "
    "per un taglio di carne.\n"
    f'- Se nessuna emoji dell\'elenco è quella cosa o una della sua famiglia, rispondi "{NONE_ANSWER}": '
    "meglio nessuna figura che una sbagliata.\n"
    "- Una risposta per ogni voce, nessuna in più."
)

EMOJI_SCHEMA = {
    "type": "object",
    "properties": {
        "emoji": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer"},
                    "nome": {"type": "string"},
                    "emoji": {"type": "string", "enum": [*INGREDIENT_EMOJI, NONE_ANSWER]},
                },
                "required": ["n", "nome", "emoji"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["emoji"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class EmojiRun:
    """Quel che un lancio ha fatto, e quel che resta."""

    applied: int = 0  # emoji scritte
    none: int = 0  # «nessuna» scritte
    refused: int = 0  # risposte che non si potevano verificare
    # gli ingredienti ancora `NULL` alla fine: i rifiutati, quelli dei lotti dopo un
    # guasto, tutti quando l'AI non risponde. Senza, «0 scritte» vorrebbe dire insieme
    # «niente da fare» e «è andato tutto storto» (la stessa ragione di `Decided.pending`
    # in `unit_forms.py`)
    pending: int = 0
    # il perché, se l'AI non ha risposto: il comando lo stampa
    unavailable: str | None = None


async def _pending(session: AsyncSession) -> int:
    return (
        await session.execute(
            select(func.count()).select_from(Ingredient).where(Ingredient.emoji.is_(None))
        )
    ).scalar_one()


async def decide_ingredient_emoji(
    session: AsyncSession,
    client: httpx.AsyncClient | None = None,
    batch_size: int = EMOJI_BATCH,
    after_batch: Callable[[], Awaitable[None]] | None = None,
) -> EmojiRun:
    """Chiede all'AI la figura di ogni ingrediente ancora `NULL`, una volta ciascuno.

    Non fa commit: lo fa `after_batch`, se c'è, dopo ogni lotto (il comando passa
    `session.commit`, così un guasto al quinto lotto non butta i primi quattro). Al primo
    guasto dell'AI si ferma: chiedere i lotti dopo sarebbe pagare per sapere che è
    ancora giù.
    """
    rows = (
        await session.execute(
            select(Ingredient.id, Ingredient.name, Ingredient.category)
            .where(Ingredient.emoji.is_(None))
            .order_by(Ingredient.name)
        )
    ).all()
    applied = none = refused = 0
    unavailable: str | None = None

    for start in range(0, len(rows), batch_size):
        asked = {n: row for n, row in enumerate(rows[start : start + batch_size], start=1)}
        question = {
            "ingredienti": [
                {"n": n, "nome": row.name, "reparto": row.category} for n, row in asked.items()
            ]
        }
        try:
            esito = await complete_json(
                call_site=LlmCallSite.INGREDIENT_EMOJI,
                system=EMOJI_SYSTEM_PROMPT,
                user=json.dumps(question, ensure_ascii=False),
                schema=EMOJI_SCHEMA,
                schema_name="figure_ingredienti",
                max_tokens=EMOJI_MAX_TOKENS,
                client=client,
            )
        except LlmUnavailable as exc:
            # mai un vicolo cieco: chi resta `NULL` mostra l'icona del reparto
            await record_llm_call(
                session, call_site=LlmCallSite.INGREDIENT_EMOJI, usage=LlmUsage(), ok=False
            )
            unavailable = str(exc)
            break
        await record_llm_call(
            session, call_site=LlmCallSite.INGREDIENT_EMOJI, usage=esito.usage, ok=True
        )

        answered: set[int] = set()
        for answer in esito.data.get("emoji") or []:
            n = answer.get("n")
            row = asked.get(n) if type(n) is int else None
            name = str(answer.get("nome") or "").strip().casefold()
            if row is None or n in answered or name != row.name.casefold():
                refused += 1
                continue
            answered.add(n)
            value = answer.get("emoji")
            if value == NONE_ANSWER:
                stored: str | None = NO_EMOJI
            else:
                stored = canonical_emoji(value) if isinstance(value, str) else None
            if stored is None:
                refused += 1
                continue
            written = await session.execute(
                update(Ingredient)
                .where(Ingredient.id == row.id, Ingredient.emoji.is_(None))
                .values(emoji=stored)
            )
            if written.rowcount == 1:
                if stored == NO_EMOJI:
                    none += 1
                else:
                    applied += 1
        await session.flush()
        if after_batch is not None:
            await after_batch()

    return EmojiRun(
        applied=applied,
        none=none,
        refused=refused,
        pending=await _pending(session),
        unavailable=unavailable,
    )
