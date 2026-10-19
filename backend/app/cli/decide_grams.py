"""Fa pesare all'AI le dosi delle ricette che non sono in grammi né in litri (S4, fetta 2).

    python -m app.cli.decide_grams --limit 40   # le prime 40 coppie da pesare
    python -m app.cli.decide_grams              # tutte

Una coppia è un ingrediente con un'unità canonica («aglio» × «spicchio», «uova» ×
«pezzo»). Prima il pilota (`python -m app.cli.s4_pilot`). Scrive solo dove una coppia non
ha ancora un peso: un peso scritto in Anagrafica non si tocca. Un peso sbagliato si
corregge in Anagrafica, nella scheda dell'ingrediente, «Pesi per unità».
"""

import asyncio
import sys

from app.core.db import SessionLocal
from app.services.unit_grams import decide_grams

FLAG_LIMIT = "--limit"


async def main(argv: list[str]) -> int:
    limit: int | None = None
    if argv:
        if argv[0] != FLAG_LIMIT:
            print(f"argomento sconosciuto: {argv[0]}")
            return 2
        if len(argv) != 2 or not argv[1].isdigit() or int(argv[1]) < 1:
            print(f"uso: python -m app.cli.decide_grams [{FLAG_LIMIT} N], con N almeno 1")
            return 2
        limit = int(argv[1])

    async with SessionLocal() as session:
        esito = await decide_grams(session, limit=limit, after_batch=session.commit)
        await session.commit()

    if esito.unavailable is not None:
        print(
            f"pesi non disponibili ({esito.unavailable}): le dosi senza peso restano fuori "
            "dal conto dei nutrienti."
        )
    print(
        f"{esito.weighed} pesi scritti, {esito.none} senza un peso sensato, "
        f"{esito.refused} risposte rifiutate"
    )
    if esito.pending == 1:
        print("1 coppia resta da pesare: rilancia questo comando.")
    elif esito.pending:
        print(f"{esito.pending} coppie restano da pesare: rilancia questo comando.")
    else:
        print("nessuna coppia in attesa di un peso.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
