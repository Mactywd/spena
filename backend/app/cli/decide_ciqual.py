"""Fa abbinare all'AI gli ingredienti alimentari alla tabella CIQUAL (S4, fetta 1).

    python -m app.cli.decide_ciqual --limit 20   # i primi 20 da decidere, per nome
    python -m app.cli.decide_ciqual              # tutti

Prima la tabella (`python -m app.cli.load_ciqual`) e il pilota (`python -m
app.cli.s4_pilot`). Scrive solo dove un ingrediente non ha ancora una scelta: una scelta
fatta in Anagrafica, «Nessun alimento adatto» compreso, non si tocca. Una scelta sbagliata
si corregge in Anagrafica, nella scheda dell'ingrediente («Cambia alimento», o «Annulla
la scelta» per ridarla all'AI).
"""

import asyncio
import sys

from app.core.db import SessionLocal
from app.repositories.ciqual import count_foods
from app.services.ciqual_match import decide_ciqual

FLAG_LIMIT = "--limit"
EMPTY_TABLE = "La tabella CIQUAL è vuota: prima python -m app.cli.load_ciqual."


async def main(argv: list[str]) -> int:
    limit: int | None = None
    if argv:
        if argv[0] != FLAG_LIMIT:
            print(f"argomento sconosciuto: {argv[0]}")
            return 2
        if len(argv) != 2 or not argv[1].isdigit() or int(argv[1]) < 1:
            print(f"uso: python -m app.cli.decide_ciqual [{FLAG_LIMIT} N], con N almeno 1")
            return 2
        limit = int(argv[1])

    async with SessionLocal() as session:
        if await count_foods(session) == 0:
            print(EMPTY_TABLE)
            return 1
        esito = await decide_ciqual(session, limit=limit, after_batch=session.commit)
        await session.commit()

    if esito.unavailable is not None:
        # Si stampa, non si logga: `app/` non configura nessun logging (la stessa scelta
        # di `unit_forms.py` e `decide_emoji`).
        print(
            f"abbinamenti non disponibili ({esito.unavailable}): gli ingredienti restano da "
            "decidere, senza valori nutrizionali."
        )
    without = f" ({esito.no_candidates} senza nemmeno un candidato)" if esito.no_candidates else ""
    print(
        f"{esito.matched} ingredienti abbinati, {esito.none} senza un alimento adatto{without}, "
        f"{esito.refused} risposte rifiutate"
    )
    # L'ultima riga dice sempre quanto resta: chi lancia in produzione legge quella.
    if esito.pending == 1:
        print("1 ingrediente alimentare resta da decidere: rilancia questo comando.")
    elif esito.pending:
        print(f"{esito.pending} ingredienti alimentari restano da decidere: rilancia questo comando.")
    else:
        print("nessun ingrediente alimentare in attesa.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
