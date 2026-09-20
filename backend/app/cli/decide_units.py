"""Fa decidere all'AI singolare e plurale delle unità in attesa.

    python -m app.cli.decide_units
    python -m app.cli.decide_units --azzera cucchiai

Il secondo è l'undo: riporta una riga a non decisa, e la chiamata dopo la ridecide.
"""

import asyncio
import sys

from app.core.db import SessionLocal
from app.repositories.units import reset_unit
from app.services.unit_forms import decide_unit_forms

FLAG_AZZERA = "--azzera"


async def main(argv: list[str]) -> int:
    # La guardia esce con codice diverso da zero, non solo stampando: un refuso in
    # uno script che controlla l'exit code non deve passare per un successo.
    if argv and argv[0] != FLAG_AZZERA:
        print(f"argomento sconosciuto: {argv[0]}")
        return 2
    if argv and argv[0] == FLAG_AZZERA:
        if len(argv) != 2:
            print(f"uso: {FLAG_AZZERA} <chiave>")
            return 2
        async with SessionLocal() as session:
            done = await reset_unit(session, argv[1])
            await session.commit()
        print("azzerata" if done else f"nessuna unità con chiave «{argv[1]}»")
        return 0 if done else 1

    async with SessionLocal() as session:
        esito = await decide_unit_forms(session)
        await session.commit()
    print(f"{esito.applied} unità decise, {esito.refused} risposte rifiutate")
    # L'ultima riga dice sempre quanto resta, come `import_gz` con i suoi termini:
    # «0 decise» da solo non distingue «non c'era niente da fare» da «l'AI non ha
    # risposto», e chi mette in produzione legge proprio quella riga per sapere se
    # deve rilanciare.
    if esito.pending == 1:
        print("1 parola resta da decidere: rilancia questo comando.")
    elif esito.pending:
        print(f"{esito.pending} parole restano da decidere: rilancia questo comando.")
    else:
        print("nessuna parola in attesa.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
