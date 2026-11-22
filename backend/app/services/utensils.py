"""Gli utensili di cucina nei prompt dell'AI.

Il blocco va nei prompt delle ricette scritte dall'AI: la bozza, la variante e, nel
piano 3, la chat dei pasti. Con l'elenco vuoto non c'è blocco (`None`): un elenco vuoto
vuol dire «nessun vincolo» (spec 2026-11-12 §7) e non «nessuno strumento», e dirlo al
modello gli farebbe scrivere ricette senza fornelli. L'elenco si legge a ogni chiamata,
così una correzione fatta un minuto fa vale subito.
"""

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.utensils import list_utensils

UTENSILS_PROMPT_INTRO = "Gli strumenti che ci sono in cucina sono solo questi:"
UTENSILS_PROMPT_RULE = (
    "Usa solo questi strumenti. Se la tecnica di sempre ne chiede uno che manca (la frusta "
    "per montare gli albumi, per esempio), scegli un'altra tecnica che si fa con quelli che "
    "ci sono; se senza quello strumento il piatto non si fa, dillo."
)
# La bozza e la variante rispondono con uno schema stretto: «dillo» lì ha un posto solo,
# la descrizione. Senza `rule` chiama solo la pianificazione; la chat del piatto e la coda
# passano le loro (`UTENSILS_REPLY_RULE`, `UTENSILS_STEPS_RULE`).
UTENSILS_JSON_RULE = (
    "Usa solo questi strumenti. Se la tecnica di sempre ne chiede uno che manca (la frusta "
    "per montare gli albumi, per esempio), scegli un'altra tecnica che si fa con quelli che "
    "ci sono; se senza quello strumento il piatto non si fa, dillo nella descrizione."
)
# I Pasti dicono lo strumento che manca dove la risposta lo porta davvero. Nella coda delle
# ricette nessuno legge la risposta del giro: resta solo la ricetta, quindi la frase va nel
# procedimento. Nella chat del piatto la risposta la legge Mattia.
_RULE_START = UTENSILS_PROMPT_RULE[: -len("dillo.")]
UTENSILS_STEPS_RULE = (
    _RULE_START
    + "scrivilo al primo passo del procedimento: della tua risposta resta solo la ricetta."
)
UTENSILS_REPLY_RULE = _RULE_START + "dillo a Mattia nella risposta."


def render_utensils_block(
    entries: Sequence[tuple[str, str | None]], *, rule: str = UTENSILS_PROMPT_RULE
) -> str | None:
    """Il blocco di prompt per `entries` (nome, nota), nell'ordine ricevuto."""
    if not entries:
        return None
    righe = [f"- {name} ({note})" if note else f"- {name}" for name, note in entries]
    return "\n".join([UTENSILS_PROMPT_INTRO, *righe, rule])


async def utensils_prompt_block(
    session: AsyncSession, *, rule: str = UTENSILS_PROMPT_RULE
) -> str | None:
    utensils = await list_utensils(session)
    return render_utensils_block([(u.name, u.note) for u in utensils], rule=rule)
