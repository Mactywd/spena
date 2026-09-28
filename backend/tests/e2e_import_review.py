"""Semina e pulizia per `frontend/e2e/import-review.spec.ts`. Non è un test di pytest.

La revisione della coda si prova nel browser vero solo se ci sono decisioni prese
dall'AI da rivedere, e lo stack e2e non ne ha: il seme porta anagrafica e ricette, non
termini dell'import. Questo file le fa nascere **dal codice vero** — `decide_terms`, la
stessa funzione che risponde al bottone «Riprova con l'AI» — e l'unica cosa finta è il
modello: `ScriptedLlm` di `llm_fakes.py`, lo stesso finto della suite, che sostituisce
`httpx.AsyncClient` e lascia girare per intero `complete_json`, la verifica contro
l'anagrafica, l'alias e il `decided_by = "ai"`. Nessuna chiamata di rete: la chiave qui
sotto è finta di proposito (sullo stack e2e quella vera è comunque vuota, vedi
`.env.e2e`), così nemmeno un errore di questo file potrebbe spendere qualcosa.

Si lancia dentro il container del backend, dove `./backend` è montato su `/app`:

    $E2E exec -T backend python tests/e2e_import_review.py seed <etichetta>
    $E2E exec -T backend python tests/e2e_import_review.py clean

`seed` stampa su stdout, in JSON, i due termini decisi. `clean` rimette tutto com'era:
annulla con `undo_decision` — il codice vero dell'annulla — ogni decisione ancora in
piedi, cancella i termini e gli ingredienti di questo file e le righe di spesa finte.
Pulisce anche quel che ha lasciato un giro interrotto, quindi si può rieseguire, e si
può chiamare anche prima di seminare.

Scrive e cancella nel database, quindi **si rifiuta di partire fuori dallo stack e2e**:
vuole `SPENA_E2E=1`, che sta solo in `.env.e2e`.

Non si chiama `test_*.py` apposta: pytest non lo raccoglie.
"""

import os
import sys

if os.environ.get("SPENA_E2E") != "1":
    raise SystemExit(
        "e2e_import_review.py scrive e cancella nel database: gira solo sullo stack "
        "spena-e2e, che porta SPENA_E2E=1 da .env.e2e. Qui manca, e non parto."
    )

# prima di qualunque import di `app`: `get_settings` è in cache al primo uso
os.environ["OPENROUTER_API_KEY"] = "chiave-finta-e2e"

import asyncio  # noqa: E402
import json  # noqa: E402

from sqlalchemy import delete, select  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.db.models.ingredient import Ingredient, IngredientCategory  # noqa: E402
from app.db.models.llm_call import LlmCall  # noqa: E402
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision  # noqa: E402
from app.repositories.ingredients import create_ingredient, delete_ingredient_if_unused  # noqa: E402
from app.services.recipe_import.decide import decide_terms  # noqa: E402
from app.services.recipe_import.undo import undo_decision  # noqa: E402
from llm_fakes import ScriptedLlm, llm_create, llm_map  # noqa: E402

KEY_PREFIX = "e2e-import-review-"
# Il segno che porta nel nome ogni ingrediente di questo file, quello su cui si collega
# il termine lungo e quello che l'AI finta crea: la pulizia li ritrova da qui.
NAME_MARK = "e2e-revisione"
# l'`id` che i finti di `llm_fakes` mettono in ogni risposta: è così che la pulizia
# riconosce le righe di spesa che la semina ha scritto, e solo quelle
FAKE_GENERATION_ID = "gen-finta"


async def seed(tag: str) -> dict:
    # Il nome lungo è il caso della prova a 375px: 88 caratteri con l'etichetta di 13
    # cifre che passa la prova (`Date.now()`), un nome da catalogo vero di quelli che la
    # fonte scrive.
    long_name = (
        "Mezze maniche rigate trafilate al bronzo di grano duro 100% italiano "
        f"(e2e {tag})"
    )
    # Il corto nasce come ingrediente nuovo: annullarlo deve dire che l'ingrediente
    # creato è stato eliminato, che è la frase che quel gesto esiste per dire.
    new_name = f"Speck {NAME_MARK} {tag}"
    async with SessionLocal() as session:
        # Il termine lungo si collega a un ingrediente che nasce qui, non a uno del seme.
        # Nato quando annullare un `map` poteva cancellare l'ingrediente d'arrivo se
        # nient'altro lo usava; il difetto è chiuso (migrazione 0011: un aggancio porta
        # `created_ingredient` falso e l'annullamento non lo cancella più), e l'ingrediente
        # proprio resta perché la prova non tocchi niente del seme: lo toglie `clean`.
        target = await create_ingredient(
            session,
            name=f"pasta {NAME_MARK} {tag}",
            display_name=f"Pasta {NAME_MARK} {tag}",
            category=IngredientCategory.CEREALI,
        )
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
            long_name: llm_map(target.name),
            new_name: llm_create(new_name.lower(), new_name, "carne"),
        })
        esito = await decide_terms(session, [long_term, new_term], client=finto)
        if esito.applied != 2 or long_term.decided_by != "ai" or new_term.decided_by != "ai":
            raise SystemExit(f"la semina non ha deciso i due termini: {esito}")
        await session.commit()
        return {
            "long": {"id": str(long_term.id), "name": long_name, "target": target.name},
            "created": {"id": str(new_term.id), "name": new_name},
        }


async def clean() -> dict:
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
        await session.flush()

        # Gli ingredienti di questo file, qualunque cosa l'annulla ne abbia fatto: quello
        # creato dall'AI finta di solito se n'è già andato, quello d'arrivo del `map` no.
        # `delete_ingredient_if_unused` e non una cancellazione cieca: se qualcosa li usa
        # ancora, lo si dice invece di rompere un vincolo.
        ids = list(
            (
                await session.execute(
                    select(Ingredient.id).where(Ingredient.name.like(f"%{NAME_MARK}%"))
                )
            ).scalars()
        )
        kept = [str(i) for i in ids if not await delete_ingredient_if_unused(session, i)]

        await session.execute(delete(LlmCall).where(LlmCall.generation_id == FAKE_GENERATION_ID))
        await session.commit()
        return {"terms": len(terms), "ingredients": len(ids) - len(kept), "kept": kept}


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "seed" and len(sys.argv) == 3:
        print(json.dumps(asyncio.run(seed(sys.argv[2]))))
    elif command == "clean":
        print(json.dumps(asyncio.run(clean())))
    else:
        raise SystemExit("uso: e2e_import_review.py seed <etichetta> | clean")


if __name__ == "__main__":
    main()
