"""Chi decide come si scrive un'unità di misura.

Una chiamata sola per il lotto di unità in attesa: sono una manciata di parole, non 40
stringhe da riecheggiare identiche come nei termini dell'import, quindi il lotto qui
non è il posto dove un MoE piccolo si sfalda. Sul tetto di 1$/giorno non si sente.

Un lotto, però, e non tutte: vedi `MAX_UNITS_PER_RUN`. Quel che resta fuori lo prende
il giro dopo, e il comando lo dice.
"""

import json
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

FORMS_MAX_TOKENS = 600

# Quante unità entrano in un giro. Il tetto dei token è su una risposta sola, quindi
# senza questo il limite vero sarebbe «quante parole nuove ha portato l'ultimo
# catalogo»: il seme ne produce 22, e una risposta plausibile per quelle 22 misura
# ~1400 caratteri, cioè già 450-500 token dei 600. Un import solo la supera, e oltre
# il tetto `complete_json` riceve un JSON tagliato, solleva `LlmUnavailable` e non
# applica niente — identicamente a ogni rilancio.
#
# Dodici perché il conto torna anche nel caso pessimo: un elemento della risposta è
# `{"key": …, "singular": …, "plural": …}` con tre parole lunghe al massimo quanto la
# colonna (30 caratteri), cioè ~125 caratteri, ~45 token. 12 × 45 = 540 < 600 anche
# se ogni parola fosse mostruosa; sui dati veri (~22 token a elemento) sono ~270, meno
# della metà. Quel che resta fuori lo prende il giro dopo, come per i termini
# dell'import: il tetto è sull'attesa di un singolo lancio, non sulla correttezza.
MAX_UNITS_PER_RUN = 12

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
    # quante parole restano non decise dopo questo giro: quelle lasciate fuori dal
    # tetto, quelle rifiutate, e tutte quante quando l'AI non risponde. Senza,
    # «0 unità decise» significa insieme «non c'era niente da fare» e «è andato
    # tutto storto», che è il difetto che questo campo chiude.
    pending: int = 0


async def decide_unit_forms(
    session: AsyncSession, client: httpx.AsyncClient | None = None
) -> Decided:
    undecided = await undecided_units(session)
    if not undecided:
        return Decided(applied=0, refused=0, pending=0)

    asked = {unit.key: unit for unit in undecided[:MAX_UNITS_PER_RUN]}
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
        # mai un vicolo cieco: le unità restano non decise e si mostrano grezze.
        # Si stampa, non si logga: `app/` non configura nessun logging, quindi sotto
        # `python -m` una riga a `logger.info` non esce da nessuna parte e il comando
        # diventa indistinguibile da uno che non aveva niente da fare. È la stessa
        # scelta di `import_gz.py` quando il riconoscimento non è disponibile.
        print(f"forme delle unità non disponibili ({exc}): restano come sono arrivate.")
        await record_llm_call(
            session, call_site=LlmCallSite.UNIT_FORMS, usage=LlmUsage(), ok=False
        )
        return Decided(applied=0, refused=0, pending=len(undecided))

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
    return Decided(applied=applied, refused=refused, pending=len(undecided) - applied)
