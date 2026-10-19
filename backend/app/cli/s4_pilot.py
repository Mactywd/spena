"""Il pilota di S4: quanti casi con la risposta nota Gemma azzecca, e quanto costa.

    python -m app.cli.s4_pilot
    python -m app.cli.s4_pilot --casi <percorso.json>

Dopo `load_ciqual`, prima di `decide_ciqual` e `decide_grams`. Non scrive niente sugli ingredienti; le
chiamate si registrano in `llm_calls` come tutte. Se non passa, la spec di S4 al §9 dice
cosa servirebbe.
"""

import asyncio
import re
import sys
from pathlib import Path

from app.cli.decide_ciqual import EMPTY_TABLE
from app.core.db import SessionLocal
from app.domain.ciqual import CIQUAL_SOURCE
from app.repositories.ciqual import count_foods
from app.services.ai_spend import Spend
from app.services.s4_pilot import (
    PILOT_FILE,
    final_line,
    grams_report,
    load_cases,
    match_report,
    pilot_passed,
    run_grams_pilot,
    run_match_pilot,
    spend_line,
)

FLAG_CASES = "--casi"


async def main(argv: list[str]) -> int:
    path = PILOT_FILE
    if argv:
        if len(argv) != 2 or argv[0] != FLAG_CASES:
            print(f"uso: python -m app.cli.s4_pilot [{FLAG_CASES} percorso.json]")
            return 2
        path = Path(argv[1])
    try:
        cases = load_cases(path)
    except (OSError, ValueError, KeyError, TypeError, re.error) as exc:
        print(f"I casi del pilota non si leggono ({exc}).")
        return 1

    grams_outcomes = []
    async with SessionLocal() as session:
        if await count_foods(session) == 0:
            print(EMPTY_TABLE)
            return 1
        spend = Spend()
        outcomes, unavailable = await run_match_pilot(session, cases.matches, spend=spend)
        if unavailable is None and cases.grams:
            grams_outcomes, unavailable = await run_grams_pilot(session, cases.grams, spend=spend)
        await session.commit()  # le chiamate in `llm_calls`

    if unavailable is not None:
        print(f"il pilota non si è potuto fare: l'AI non ha risposto ({unavailable}).")
        print(spend_line(spend))
        return 1
    print(f"Pilota S4 su {CIQUAL_SOURCE}: {len(cases.matches)} abbinamenti, {len(cases.grams)} pesi.")
    for line in match_report(outcomes):
        print(line)
    if cases.grams:
        for line in grams_report(grams_outcomes):
            print(line)
    print(spend_line(spend))
    print(final_line(pilot_passed(outcomes, grams_outcomes)))
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
