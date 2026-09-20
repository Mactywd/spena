"""Chi decide come si scrive un'unità di misura.

Una chiamata sola per tutte le unità in attesa: sono una manciata di parole, non 40
stringhe da riecheggiare identiche come nei termini dell'import, quindi il lotto qui
non è il posto dove un MoE piccolo si sfalda. Sul tetto di 1$/giorno non si sente.
"""

import json
import logging
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.unit import UNIT_MAX_LENGTH, Unit
from app.repositories.llm_calls import record_llm_call
from app.repositories.units import apply_forms, undecided_units
from app.services.llm import (
    LlmCallSite,
    LlmUnavailable,
    LlmUsage,
    complete_json,
)

logger = logging.getLogger(__name__)

FORMS_MAX_TOKENS = 600

FORMS_SYSTEM_PROMPT = """Ricevi un elenco di parole italiane usate come unità di misura nelle dosi di una ricetta. Per ognuna rispondi con il singolare e il plurale.

Regole:
- "key" deve essere riscritta identica a come te l'ho passata.
- Per le sigle invariabili (g, kg, ml, l) singolare e plurale sono uguali alla sigla.
- Non aggiungere parole che non ti ho passato, e non toglierne.
"""

FORMS_SCHEMA = {
    "type": "object",
    "properties": {
        "units": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "singular": {"type": "string"},
                    "plural": {"type": "string"},
                },
                "required": ["key", "singular", "plural"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["units"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class Decided:
    applied: int
    refused: int


async def decide_unit_forms(
    session: AsyncSession, client: httpx.AsyncClient | None = None
) -> Decided:
    pending = await undecided_units(session)
    if not pending:
        return Decided(applied=0, refused=0)

    asked = {unit.key: unit for unit in pending}
    try:
        esito = await complete_json(
            call_site=LlmCallSite.UNIT_FORMS,
            system=FORMS_SYSTEM_PROMPT,
            user=json.dumps({"units": sorted(asked)}, ensure_ascii=False),
            schema=FORMS_SCHEMA,
            schema_name="forme_unita",
            max_tokens=FORMS_MAX_TOKENS,
            client=client,
        )
    except LlmUnavailable as exc:
        # mai un vicolo cieco: le unità restano non decise e si mostrano grezze
        logger.info("forme delle unità non decise: %s", exc)
        await record_llm_call(
            session, call_site=LlmCallSite.UNIT_FORMS, usage=LlmUsage(), ok=False
        )
        return Decided(applied=0, refused=0)

    await record_llm_call(
        session, call_site=LlmCallSite.UNIT_FORMS, usage=esito.usage, ok=True
    )

    applied = refused = 0
    for answer in esito.data.get("units") or []:
        unit = asked.get(answer.get("key"))
        singular = (answer.get("singular") or "").strip()
        plural = (answer.get("plural") or "").strip()
        # si applica solo quel che si può verificare: la chiave dev'essere una di
        # quelle chieste e le due forme non vuote ed entro il limite della colonna
        if unit is None or not singular or not plural:
            refused += 1
            continue
        if len(singular) > UNIT_MAX_LENGTH or len(plural) > UNIT_MAX_LENGTH:
            refused += 1
            continue
        await apply_forms(session, unit, singular, plural)
        applied += 1
    await session.flush()
    return Decided(applied=applied, refused=refused)
