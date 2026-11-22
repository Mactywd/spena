"""Semina e pulizia per le prove delle spese dell'AI (H1) in `frontend/e2e/`. Non è un test
di pytest.

Lo stack e2e non ha spese: `.env.e2e` lascia vuota la chiave API, e una chiamata
che sfugge a uno stub si ferma su `LlmUnavailable` (al più una riga fallita, col costo
NULL). Le prove della schermata vogliono cifre vere: questo file scrive in `llm_calls` delle
righe col loro costo, nessuna rete, e le toglie. Le riconosce dal `generation_id`, che
comincia con `e2e-spese-` (anche quella fallita, che in esercizio non l'avrebbe).

Le righe, negli ultimi 30 giorni 0,025 $:

- oggi: `recipe_draft` 0,012 e 0,008, una `recipe_draft` fallita senza costo, e
  `e2e_sconosciuta` 0,001 — una sezione che il backend non conosce, da mostrare grezza;
- tre giorni fa: `term_decision` 0,004.

Si lancia dentro il container del backend, dove `./backend` è montato su `/app`:

    $E2E exec -T backend python tests/e2e_spese.py seed
    $E2E exec -T backend python tests/e2e_spese.py clean

`clean` si può chiamare prima di seminare: toglie anche gli avanzi di un giro interrotto.

Scrive e cancella nel database, quindi **si rifiuta di partire fuori dallo stack e2e**:
vuole `SPENA_E2E=1`, che sta solo in `.env.e2e`.

Non si chiama `test_*.py` apposta: pytest non lo raccoglie.
"""

import os
import sys

if os.environ.get("SPENA_E2E") != "1":
    raise SystemExit(
        "e2e_spese.py scrive e cancella nel database: gira solo sullo stack "
        "spena-e2e, che porta SPENA_E2E=1 da .env.e2e. Qui manca, e non parto."
    )

import asyncio  # noqa: E402
import json  # noqa: E402
from datetime import UTC, datetime, timedelta  # noqa: E402

from sqlalchemy import delete  # noqa: E402

from app.core.db import SessionLocal  # noqa: E402
from app.db.models.llm_call import LlmCall  # noqa: E402

MARK = "e2e-spese-"

# (sezione, riuscita, costo, giorni fa)
ROWS = [
    ("recipe_draft", True, 0.012, 0),
    ("recipe_draft", True, 0.008, 0),
    ("recipe_draft", False, None, 0),
    ("e2e_sconosciuta", True, 0.001, 0),
    ("term_decision", True, 0.004, 3),
]


async def seed() -> dict:
    now = datetime.now(UTC)
    async with SessionLocal() as session:
        for index, (call_site, ok, cost, days_ago) in enumerate(ROWS):
            session.add(
                LlmCall(
                    call_site=call_site,
                    ok=ok,
                    model="e2e/finto",
                    generation_id=f"{MARK}{index}",
                    cost_usd=cost,
                    created_at=now - timedelta(days=days_ago),
                )
            )
        await session.commit()
    return {"rows": len(ROWS)}


async def clean() -> dict:
    async with SessionLocal() as session:
        result = await session.execute(
            delete(LlmCall).where(LlmCall.generation_id.like(f"{MARK}%"))
        )
        await session.commit()
    return {"rows": result.rowcount}


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "seed" and len(sys.argv) == 2:
        print(json.dumps(asyncio.run(seed())))
    elif command == "clean" and len(sys.argv) == 2:
        print(json.dumps(asyncio.run(clean())))
    else:
        raise SystemExit("uso: e2e_spese.py seed | clean")


if __name__ == "__main__":
    main()
