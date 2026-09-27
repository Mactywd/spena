"""Semina e pulizia per `frontend/e2e/import-review.spec.ts`. Non è un test di pytest.

La revisione della coda si prova nel browser vero solo se ci sono decisioni prese
dall'AI da rivedere, e lo stack e2e non ne ha: il seme porta anagrafica e ricette, non
termini dell'import. Questo file le fa nascere **dal codice vero** — `decide_terms`, la
stessa funzione che risponde al bottone «Riprova con l'AI» — e l'unica cosa finta è il
modello: `ScriptedLlm` di `llm_fakes.py`, lo stesso finto della suite, che sostituisce
`httpx.AsyncClient` e lascia girare per intero `complete_json`, la verifica contro
l'anagrafica, l'alias e il `decided_by = "ai"`. Nessuna chiamata di rete: la chiave qui
sotto è finta di proposito, così nemmeno un errore di questo file potrebbe spendere
qualcosa con quella vera che il `.env` dello stack porta con sé.

Si lancia dentro il container del backend, dove `./backend` è montato su `/app`:

    $E2E exec -T backend python tests/e2e_import_review.py seed <etichetta>
    $E2E exec -T backend python tests/e2e_import_review.py clean

`seed` stampa su stdout, in JSON, i due termini decisi. `clean` rimette tutto com'era
passando da `undo_decision` — il codice vero dell'annulla, che toglie alias e
ingrediente creato — e poi cancella i termini: pulisce ogni termine con la chiave di
questo file, anche quelli lasciati da un giro interrotto, quindi si può rieseguire.

Non si chiama `test_*.py` apposta: pytest non lo raccoglie.
"""

import os

# prima di qualunque import di `app`: `get_settings` è in cache al primo uso
os.environ["OPENROUTER_API_KEY"] = "chiave-finta-e2e"

import asyncio  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402

from sqlalchemy import delete, select  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.db.models.llm_call import LlmCall  # noqa: E402
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision  # noqa: E402
from app.services.recipe_import.decide import decide_terms  # noqa: E402
from app.services.recipe_import.undo import undo_decision  # noqa: E402
from llm_fakes import ScriptedLlm, llm_create, llm_map  # noqa: E402

KEY_PREFIX = "e2e-import-review-"
# l'`id` che i finti di `llm_fakes` mettono in ogni risposta: è così che la pulizia
# riconosce le righe di spesa che la semina ha scritto, e solo quelle
FAKE_GENERATION_ID = "gen-finta"


async def seed(tag: str) -> dict:
    # Il nome lungo è il caso della prova a 375px: 90 caratteri, un nome da catalogo
    # vero di quelli che la fonte scrive. Si collega a «pasta», che il seme ha.
    long_name = (
        "Mezze maniche rigate trafilate al bronzo di grano duro 100% italiano "
        f"(e2e {tag})"
    )
    # Il corto nasce come ingrediente nuovo: annullarlo deve dire che l'ingrediente
    # creato è stato eliminato, che è la frase che quel gesto esiste per dire.
    new_name = f"Speck e2e {tag}"
    async with SessionLocal() as session:
        long_term = ImportTerm(
            source=GIALLOZAFFERANO, term_key=f"{KEY_PREFIX}{tag}-lungo",
            display_name=long_name, occurrences=1, decision=TermDecision.PENDING,
        )
        new_term = ImportTerm(
            source=GIALLOZAFFERANO, term_key=f"{KEY_PREFIX}{tag}-nuovo",
            display_name=new_name, occurrences=1, decision=TermDecision.PENDING,
        )
        session.add_all([long_term, new_term])
        await session.flush()

        finto = ScriptedLlm({
            long_name: llm_map("pasta"),
            new_name: llm_create(new_name.lower(), new_name, "carne"),
        })
        esito = await decide_terms(session, [long_term, new_term], client=finto)
        if esito.applied != 2 or long_term.decided_by != "ai" or new_term.decided_by != "ai":
            raise SystemExit(f"la semina non ha deciso i due termini: {esito}")
        await session.commit()
        return {
            "long": {"id": str(long_term.id), "name": long_name},
            "created": {"id": str(new_term.id), "name": new_name},
        }


async def clean() -> int:
    async with SessionLocal() as session:
        terms = list(
            (
                await session.execute(
                    select(ImportTerm).where(ImportTerm.term_key.like(f"{KEY_PREFIX}%"))
                )
            ).scalars()
        )
        for term in terms:
            if term.decision != TermDecision.PENDING:
                await undo_decision(session, term)
            await session.delete(term)
        await session.execute(delete(LlmCall).where(LlmCall.generation_id == FAKE_GENERATION_ID))
        await session.commit()
        return len(terms)


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "seed" and len(sys.argv) == 3:
        print(json.dumps(asyncio.run(seed(sys.argv[2]))))
    elif command == "clean":
        print(json.dumps({"removed": asyncio.run(clean())}))
    else:
        raise SystemExit("uso: e2e_import_review.py seed <etichetta> | clean")


if __name__ == "__main__":
    main()
