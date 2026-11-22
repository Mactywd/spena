"""Fa decidere all'AI la figura degli ingredienti che non ce l'hanno (S12).

    python -m app.cli.decide_emoji

Una volta dopo il deploy di S12, e poi quando si vuole: gli ingredienti nati dopo (a
mano, dall'import, dalla coda) nascono senza figura e mostrano l'icona del reparto finché
questo comando non gira (bozza S12 §5.4). Scrive solo dove la colonna è vuota: una
figura scelta in Anagrafica, «Nessuna» compresa, non si tocca. Non ha opzioni, a
differenza di `decide_units`: una figura sbagliata si corregge in Anagrafica, nella
scheda dell'ingrediente («Cambia figura»).
"""

import asyncio
import sys

from app.core.db import SessionLocal
from app.services.ingredient_emoji import decide_ingredient_emoji


async def main(argv: list[str]) -> int:
    # La guardia esce con codice diverso da zero, non solo stampando: un refuso in uno
    # script che controlla l'exit code non deve passare per un successo.
    if argv:
        print(f"argomento sconosciuto: {argv[0]}")
        return 2

    async with SessionLocal() as session:
        esito = await decide_ingredient_emoji(session, after_batch=session.commit)
        await session.commit()

    if esito.unavailable is not None:
        # Si stampa, non si logga: `app/` non configura nessun logging, e sotto
        # `python -m` una riga a `logger.info` non esce da nessuna parte (la stessa
        # scelta di `unit_forms.py` e `import_gz.py`).
        print(
            f"figure non disponibili ({esito.unavailable}): gli ingredienti senza figura "
            "mostrano l'icona del reparto."
        )
    print(
        f"{esito.applied} figure scritte, {esito.none} ingredienti senza una figura adatta, "
        f"{esito.refused} risposte rifiutate"
    )
    # L'ultima riga dice sempre quanto resta, come `decide_units`: chi mette in
    # produzione legge proprio quella per sapere se deve rilanciare.
    if esito.pending == 1:
        print("1 ingrediente resta da decidere: rilancia questo comando.")
    elif esito.pending:
        print(f"{esito.pending} ingredienti restano da decidere: rilancia questo comando.")
    else:
        print("nessun ingrediente in attesa.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
