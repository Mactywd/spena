"""Il pilota di S4: Gemma basta? (spec §4.18–4.19, decisione 3 di Mattia del 2026-10-13).

Chiede all'AI i casi di `backend/app/data/s4_pilota.json` con gli stessi servizi del lancio
vero (`match_names`), e li confronta con le risposte note. Non scrive niente sugli
ingredienti: registra solo le chiamate in `llm_calls`, come ogni chiamata.

Un abbinamento atteso è un'espressione regolare sul nome francese normalizzato, non un
codice: i codici del 2025 non li ha visti chi ha scritto i casi (spec §3). Per lo stesso
motivo un caso la cui espressione non trova **nessun** alimento nella tabella caricata è
«da rivedere»: non si chiede all'AI e non entra nel conto — è il caso, non l'AI, a essere
sbagliato. La soglia (90%) dice se si può lanciare su tutto il catalogo; non blocca
niente: decide Mattia.
"""

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.nutrition import CiqualFood
from app.domain.ciqual import normalize_name
from app.domain.recipe_nutrition import PIECE_LABEL
from app.services.ai_spend import Spend
from app.services.ciqual_match import NameToMatch, match_names
from app.services.llm import LlmUnavailable
from app.services.unit_grams import GRAMS_BATCH, PairQuestion, ask_grams

PILOT_FILE = Path(__file__).resolve().parent.parent / "data" / "s4_pilota.json"
MATCH_THRESHOLD = 0.9
GRAMS_THRESHOLD = 0.8


@dataclass(frozen=True)
class MatchCase:
    ingredient: str
    category: str
    # espressione regolare sul nome normalizzato; None = «nessun alimento adatto»
    expected: str | None


class Verdict(StrEnum):
    RIGHT = "right"
    WRONG = "wrong"
    UNANSWERED = "unanswered"
    REVIEW = "review"


@dataclass(frozen=True)
class MatchOutcome:
    case: MatchCase
    verdict: Verdict
    code: str | None = None
    name: str | None = None


@dataclass(frozen=True)
class GramsCase:
    ingredient: str
    # None = il pezzo
    unit: str | None
    low: Decimal
    high: Decimal


@dataclass(frozen=True)
class GramsOutcome:
    case: GramsCase
    verdict: Verdict
    grams: Decimal | None = None


@dataclass(frozen=True)
class PilotCases:
    matches: list[MatchCase]
    grams: list[GramsCase] = field(default_factory=list)


def load_cases(path: Path = PILOT_FILE) -> PilotCases:
    """I casi del file. Un'espressione rotta solleva `re.error` subito, non a metà giro."""
    data = json.loads(path.read_text(encoding="utf-8"))
    matches = []
    for item in data.get("abbinamenti", []):
        expected = item.get("atteso")
        if expected is not None:
            re.compile(expected)
        matches.append(MatchCase(str(item["ingrediente"]), str(item["reparto"]), expected))
    grams = []
    for item in data.get("pesi", []):
        low, high = Decimal(str(item["min"])), Decimal(str(item["max"]))
        if not Decimal("0") < low < high:
            raise ValueError(f"il peso di «{item['ingrediente']}» ha un intervallo vuoto")
        grams.append(GramsCase(str(item["ingrediente"]), item.get("unita"), low, high))
    return PilotCases(matches=matches, grams=grams)


async def run_match_pilot(
    session: AsyncSession,
    cases: Sequence[MatchCase],
    client: AsyncAnthropic | None = None,
    spend: Spend | None = None,
) -> tuple[list[MatchOutcome], str | None]:
    names = {
        code: name
        for code, name in (await session.execute(select(CiqualFood.code, CiqualFood.name_fr))).all()
    }
    plain = [normalize_name(name) for name in names.values()]
    to_review = {
        case.ingredient
        for case in cases
        if case.expected is not None and not any(re.search(case.expected, name) for name in plain)
    }
    asked = [NameToMatch(case.ingredient, case.category) for case in cases if case.ingredient not in to_review]
    result = await match_names(session, asked, client=client, spend=spend)

    outcomes = []
    for case in cases:
        if case.ingredient in to_review:
            outcomes.append(MatchOutcome(case, Verdict.REVIEW))
            continue
        matched = result.decided.get(case.ingredient)
        if matched is None:
            outcomes.append(MatchOutcome(case, Verdict.UNANSWERED))
            continue
        name = names.get(matched.code) if matched.code is not None else None
        if case.expected is None:
            right = matched.code is None
        else:
            right = name is not None and re.search(case.expected, normalize_name(name)) is not None
        outcomes.append(
            MatchOutcome(case, Verdict.RIGHT if right else Verdict.WRONG, matched.code, name)
        )
    return outcomes, result.unavailable


def score(outcomes: Sequence[MatchOutcome | GramsOutcome]) -> tuple[int, int]:
    """Giusti e contati: i casi da rivedere non contano."""
    counted = [outcome for outcome in outcomes if outcome.verdict != Verdict.REVIEW]
    return sum(outcome.verdict == Verdict.RIGHT for outcome in counted), len(counted)


def passes(right: int, counted: int, threshold: float) -> bool:
    return counted > 0 and right / counted >= threshold


def match_report(outcomes: Sequence[MatchOutcome]) -> list[str]:
    right, counted = score(outcomes)
    if counted == 0:
        lines = ["Abbinamenti: nessun caso da contare: i casi vanno rivisti."]
    else:
        verdict = "bastano" if passes(right, counted, MATCH_THRESHOLD) else "non bastano"
        lines = [
            f"Abbinamenti: {right} giusti su {counted} ({round(100 * right / counted)}%): "
            f"{verdict} (soglia {round(100 * MATCH_THRESHOLD)}%)."
        ]
    for outcome in outcomes:
        ingredient = outcome.case.ingredient
        expected = outcome.case.expected or "nessun alimento"
        if outcome.verdict == Verdict.WRONG and outcome.code is None:
            lines.append(f"  ✗ «{ingredient}»: nessun alimento scelto; atteso {expected}")
        elif outcome.verdict == Verdict.WRONG:
            lines.append(f"  ✗ «{ingredient}»: scelto «{outcome.name}» ({outcome.code}); atteso {expected}")
        elif outcome.verdict == Verdict.UNANSWERED:
            lines.append(f"  – «{ingredient}»: nessuna risposta verificabile dall'AI")
        elif outcome.verdict == Verdict.REVIEW:
            lines.append(
                f"  ? «{ingredient}»: nessun alimento della tabella corrisponde a {expected}: "
                "il caso va rivisto"
            )
    return lines


async def run_grams_pilot(
    session: AsyncSession,
    cases: Sequence[GramsCase],
    client: AsyncAnthropic | None = None,
    spend: Spend | None = None,
) -> tuple[list[GramsOutcome], str | None]:
    answers: dict[int, Decimal | None] = {}
    for start in range(0, len(cases), GRAMS_BATCH):
        chunk = cases[start : start + GRAMS_BATCH]
        try:
            got, _ = await ask_grams(
                session,
                [PairQuestion(case.ingredient, case.unit or PIECE_LABEL, None) for case in chunk],
                client=client,
                spend=spend,
            )
        except LlmUnavailable as exc:
            return [], str(exc)
        answers.update({start + index: grams for index, grams in got.items()})
    outcomes = []
    for index, case in enumerate(cases):
        if index not in answers:
            outcomes.append(GramsOutcome(case, Verdict.UNANSWERED))
            continue
        grams = answers[index]
        right = grams is not None and case.low <= grams <= case.high
        outcomes.append(GramsOutcome(case, Verdict.RIGHT if right else Verdict.WRONG, grams))
    return outcomes, None


def _number(value: Decimal) -> str:
    return format(value.normalize(), "f").replace(".", ",")


def grams_report(outcomes: Sequence[GramsOutcome]) -> list[str]:
    right, counted = score(outcomes)
    if counted == 0:
        return ["Pesi: nessun caso da contare."]
    verdict = "bastano" if passes(right, counted, GRAMS_THRESHOLD) else "non bastano"
    lines = [
        f"Pesi: {right} nell'intervallo su {counted} ({round(100 * right / counted)}%): "
        f"{verdict} (soglia {round(100 * GRAMS_THRESHOLD)}%)."
    ]
    for outcome in outcomes:
        case = outcome.case
        label = f"«{case.ingredient}», 1 {case.unit or PIECE_LABEL}"
        expected = f"{_number(case.low)}–{_number(case.high)} g"
        if outcome.verdict == Verdict.WRONG and outcome.grams is None:
            lines.append(f"  ✗ {label}: nessun peso; atteso {expected}")
        elif outcome.verdict == Verdict.WRONG:
            lines.append(f"  ✗ {label}: {_number(outcome.grams)} g; atteso {expected}")
        elif outcome.verdict == Verdict.UNANSWERED:
            lines.append(f"  – {label}: nessuna risposta verificabile dall'AI")
    return lines


def pilot_passed(
    matches: Sequence[MatchOutcome], grams: Sequence[GramsOutcome]
) -> bool:
    """Il pilota passa se passano gli abbinamenti e, se ci sono, i pesi."""
    passed = passes(*score(matches), MATCH_THRESHOLD)
    if grams:
        passed = passed and passes(*score(grams), GRAMS_THRESHOLD)
    return passed


def spend_line(spend: Spend) -> str:
    cost = f"{spend.cost_usd:.4f}".replace(".", ",")
    calls = "chiamata" if spend.calls == 1 else "chiamate"
    line = f"Spesa del pilota: {cost} $ in {spend.calls} {calls}"
    if spend.unpriced:
        line += f", {spend.unpriced} senza costo dichiarato"
    return line + "."


def final_line(passed: bool) -> str:
    if passed:
        return "Il pilota passa: si può lanciare l'AI su tutto il catalogo."
    return (
        "Il pilota non passa: prima del lancio su tutto il catalogo serve un modello più "
        "forte (spec di S4, §9)."
    )
