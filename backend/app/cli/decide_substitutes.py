"""Fa decidere all'AI i sostituti degli ingredienti che non li hanno (R5).

    python -m app.cli.decide_substitutes --dry-run
    python -m app.cli.decide_substitutes --limit 20
    python -m app.cli.decide_substitutes

Una «voce» è un ingrediente in un contesto (dolce o salato) in cui compare in una
ricetta. Il comando chiede all'AI le voci che non hanno una risposta, dalla più usata,
una chiamata per voce, a lotti con un commit dopo ognuno: interrotto, rilanciato riprende
da quel che manca. Scrive solo dove non c'è una risposta: una correzione fatta in
Anagrafica non si tocca. Una voce che nessuno ha chiesto si calcola anche da sola, la
prima volta che qualcuno tocca «Sostituisci» su quell'ingrediente.

`--dry-run` non chiama nessuno e non scrive: dice quante voci mancano, quali chiederebbe,
e — dopo un primo lancio vero — quanto costerebbe, con la media di quel che è stato
pagato. `--limit N` chiede al più N voci: la prima volta `--limit 20`, per guardare le
risposte (una riga stampata per voce) e il costo prima del resto.
"""

import asyncio
import sys

from app.core.db import SessionLocal
from app.domain.substitutions import SubstitutionContext
from app.repositories.substitutions import pending_voices
from app.services.substitutions import decide_substitutions, measured_cost

FLAG_DRY_RUN = "--dry-run"
FLAG_LIMIT = "--limit"
# quante voci elenca il `--dry-run`: il resto si conta
SHOWN = 20


def parse(argv: list[str]) -> tuple[bool, int | None] | str:
    """`(dry_run, limit)`, o il messaggio d'errore da stampare."""
    dry_run = False
    limit: int | None = None
    position = 0
    while position < len(argv):
        arg = argv[position]
        if arg == FLAG_DRY_RUN:
            dry_run = True
            position += 1
            continue
        if arg == FLAG_LIMIT:
            value = argv[position + 1] if position + 1 < len(argv) else ""
            if not value.isdigit() or int(value) < 1:
                return f"uso: {FLAG_LIMIT} <un numero maggiore di zero>"
            limit = int(value)
            position += 2
            continue
        return f"argomento sconosciuto: {arg}"
    return dry_run, limit


def _voices(count: int) -> str:
    return "1 voce" if count == 1 else f"{count} voci"


def _recipes(count: int) -> str:
    return "1 ricetta" if count == 1 else f"{count} ricette"


def _pending_line(count: int) -> str:
    # L'ultima riga dice sempre quanto resta, come `decide_units`: chi mette in produzione
    # legge proprio quella per sapere se deve rilanciare.
    if count == 1:
        return "1 voce resta da decidere: rilancia questo comando."
    if count:
        return f"{count} voci restano da decidere: rilancia questo comando."
    return "nessuna voce in attesa."


async def _dry_run(session, limit: int | None) -> None:
    voices = await pending_voices(session)
    if not voices:
        print("nessuna voce in attesa.")
        return
    savory = sum(1 for voice in voices if voice.context is SubstitutionContext.SAVORY)
    print(
        f"{_voices(len(voices))} senza sostituti: {savory} nei piatti salati, "
        f"{len(voices) - savory} nei dolci."
    )
    asked = voices[:limit] if limit is not None else voices
    print(f"ne chiederei {len(asked)}, dalle più usate:")
    for voice in asked[:SHOWN]:
        print(f"- {voice.name} ({voice.context.value}, {_recipes(voice.recipes)})")
    if len(asked) > SHOWN:
        print(f"… e altre {len(asked) - SHOWN}.")
    calls, average = await measured_cost(session)
    if average is None:
        print(f"nessun costo misurato ancora: lancia con {FLAG_LIMIT} 20 per misurarlo.")
    else:
        print(
            f"costo medio misurato: {average:.5f} $ a voce su {calls} chiamate; "
            f"stima per {len(asked)}: {average * len(asked):.4f} $."
        )


async def main(argv: list[str]) -> int:
    parsed = parse(argv)
    # Un codice d'uscita diverso da zero, non solo la stampa: un refuso in uno script che
    # controlla l'exit code non deve passare per un successo.
    if isinstance(parsed, str):
        print(parsed)
        return 2
    dry_run, limit = parsed

    async with SessionLocal() as session:
        if dry_run:
            await _dry_run(session, limit)
            return 0
        # Si stampa, non si logga: `app/` non configura nessun logging, e sotto `python -m`
        # una riga a `logger.info` non esce da nessuna parte (la scelta di `decide_units`).
        esito = await decide_substitutions(
            session, limit=limit, after_batch=session.commit, report=print
        )
        await session.commit()

    if esito.unavailable is not None:
        print(
            f"sostituti non disponibili ({esito.unavailable}): chi tocca «Sostituisci» trova "
            "«Nessun suggerimento ancora» e la strada a mano."
        )
    saved = "1 voce salvata" if esito.stored == 1 else f"{esito.stored} voci salvate"
    print(
        f"{saved} ({esito.substitutes} con sostituti, {esito.omit} da omettere, "
        f"{esito.irreplaceable} insostituibili), {esito.rejected} risposte scartate."
    )
    if esito.calls:
        spent = "costo non dichiarato" if esito.cost_usd is None else f"{esito.cost_usd:.5f} $"
        calls = "1 chiamata" if esito.calls == 1 else f"{esito.calls} chiamate"
        print(f"spesa di questo lancio: {spent} in {calls}.")
    print(_pending_line(esito.pending))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
