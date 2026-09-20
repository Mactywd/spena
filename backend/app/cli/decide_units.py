"""Fa decidere all'AI singolare e plurale delle unità in attesa.

    python -m app.cli.decide_units
    python -m app.cli.decide_units --azzera cucchiai
    python -m app.cli.decide_units --imposta cucchiai cucchiaio cucchiai

Il secondo è l'undo: riporta una riga a non decisa, e la chiamata dopo la ridecide.
Il terzo serve a quel che l'undo non sa fare: se il modello sbaglia una parola in
modo ripetibile — misurato in produzione su «cucchiai», che dopo l'azzeramento è
tornato «cchiaio» — azzerare e rilanciare non porta da nessuna parte, e senza un
«invece è così» resterebbe solo una UPDATE a mano.
"""

import asyncio
import sys

from app.core.db import SessionLocal
from app.db.models.unit import UNIT_MAX_LENGTH
from app.repositories.units import reset_unit, set_unit_forms
from app.services.unit_forms import decide_unit_forms

FLAG_AZZERA = "--azzera"
FLAG_IMPOSTA = "--imposta"


async def main(argv: list[str]) -> int:
    # La guardia esce con codice diverso da zero, non solo stampando: un refuso in
    # uno script che controlla l'exit code non deve passare per un successo.
    if argv and argv[0] not in (FLAG_AZZERA, FLAG_IMPOSTA):
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
    if argv and argv[0] == FLAG_IMPOSTA:
        if len(argv) != 4:
            print(f"uso: {FLAG_IMPOSTA} <chiave> <singolare> <plurale>")
            return 2
        chiave, singolare, plurale = argv[1], argv[2], argv[3]
        # Gli stessi due rifiuti che `decide_unit_forms` applica alla risposta
        # dell'AI. Le colonne sono `String(UNIT_MAX_LENGTH)`: una parola più lunga
        # non darebbe un errore leggibile ma un troncamento di Postgres a metà
        # della scrittura, che è il difetto che questo ramo ha già chiuso una volta.
        if not singolare or not plurale:
            print("né il singolare né il plurale possono essere una parola vuota")
            return 2
        if len(singolare) > UNIT_MAX_LENGTH or len(plurale) > UNIT_MAX_LENGTH:
            print(f"singolare e plurale stanno in {UNIT_MAX_LENGTH} caratteri")
            return 2
        async with SessionLocal() as session:
            done = await set_unit_forms(session, chiave, singolare, plurale)
            await session.commit()
        if not done:
            print(f"nessuna unità con chiave «{chiave}»")
            return 1
        print(f"«{chiave}»: {singolare} / {plurale}, deciso a mano")
        return 0

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
