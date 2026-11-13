"""Le spese dell'AI (H1): i periodi, i giorni, la quota, i nomi delle sezioni.

Puro come `rules.py`: niente database e niente orologio. «Oggi» entra come argomento, ed è
`today_in_pantry()` di chi chiama: un giorno qui è un giorno di calendario a Roma, come la
scadenza, e non un giorno UTC — chi apre l'app a mezzanotte e mezza ha speso oggi.

Le cifre sono quelle che OpenRouter dichiara, in dollari (`llm_calls.cost_usd`). Una
chiamata senza costo dichiarato — tutte le fallite, e qualche riuscita — non vale zero:
zero direbbe «gratis», e l'assenza è la verità. La somma le salta, chi chiama le conta.
"""

from collections.abc import Mapping
from datetime import date, datetime, time, timedelta
from enum import StrEnum

from app.domain.rules import PANTRY_TZ


class SpendingPeriod(StrEnum):
    """I tre periodi della schermata, decisi da Mattia il 2026-10-09."""

    MONTH = "month"
    LAST_30_DAYS = "30d"
    ALL = "all"


LAST_DAYS = 30
# otto decimali: la somma di float lascia resti (0.30000000000000004) che non sono soldi
MONEY_DIGITS = 8
SHARE_DIGITS = 4

# Il nome a video di ogni sezione (`llm_calls.call_site`, cioè `LlmCallSite`). Chiavi
# stringa e non membri dell'enum: il database può contenere una sezione che il codice in
# esercizio non conosce (un ramo nuovo, una sezione tolta), e le ultime due arrivano
# stanotte da S12 e da R8 su altri rami. Una sezione assente da qui si mostra col suo
# valore com'è: brutta, ma vera e senza rompere niente.
CALL_SITE_LABELS: dict[str, str] = {
    "term_decision": "Abbinare gli ingredienti dell'import",
    "term_collapse": "Unire i doppioni dell'import",
    "unit_forms": "Forme delle unità",
    "recipe_draft": "Ricette scritte con l'AI",
    "recipe_variant": "Varianti con l'AI",
    "ingredient_emoji": "Figure della dispensa",
    "ingredient_substitutes": "Sostituti degli ingredienti",
    "ciqual_terms": "Cercare gli alimenti CIQUAL",
    "ciqual_match": "Abbinare gli ingredienti a CIQUAL",
    "unit_grams": "Pesare le dosi delle ricette",
    "meal_chat": "Chat dei piatti",
}

# Le sezioni che girano sul piano di Claude e non a consumo (decisione 20): le loro righe
# hanno token ma `cost_usd` NULL, e stanno fuori dal conto a consumo.
PLAN_CALL_SITES: frozenset[str] = frozenset({"meal_chat"})
PLAN_NOTE = "sul piano di Claude, non a consumo"


def call_site_label(call_site: str) -> str:
    return CALL_SITE_LABELS.get(call_site, call_site)


def period_days(
    period: SpendingPeriod, today: date, first_call: date | None
) -> tuple[date, date]:
    """Il primo e l'ultimo giorno del periodo, compresi; l'ultimo è sempre oggi.

    «Da sempre» parte dal giorno della prima chiamata registrata (in produzione il
    2026-09-17, quando è nato `llm_calls`), e senza chiamate è solo oggi. Una prima
    chiamata datata nel futuro (un orologio avanti) non sposta l'inizio dopo la fine.
    """
    if period is SpendingPeriod.MONTH:
        return today.replace(day=1), today
    if period is SpendingPeriod.LAST_30_DAYS:
        return today - timedelta(days=LAST_DAYS - 1), today
    if first_call is None:
        return today, today
    return min(first_call, today), today


def day_start(day: date) -> datetime:
    """La mezzanotte di quel giorno a Roma, come istante.

    La query confronta `created_at` (un istante) con `[day_start(primo),
    day_start(ultimo + 1))`: `ZoneInfo` sa quando l'ora cambia, quindi un giorno di 23 o
    25 ore resta un giorno.
    """
    return datetime.combine(day, time.min, tzinfo=PANTRY_TZ)


def daily_series(
    first: date, last: date, by_day: Mapping[date, float]
) -> list[tuple[date, float]]:
    """Ogni giorno del periodo con la sua spesa, quelli senza a zero.

    Qui lo zero è vero: è «nessuna chiamata con un costo quel giorno», non un costo
    sconosciuto messo a zero.
    """
    days = (last - first).days + 1
    series = []
    for offset in range(days):
        day = first + timedelta(days=offset)
        series.append((day, by_day.get(day, 0.0)))
    return series


def money(value: float) -> float:
    return round(value, MONEY_DIGITS)


def share(part: float, total: float) -> float:
    """La quota del totale, 0–1. Con un totale a zero non c'è niente da dividere."""
    if total <= 0:
        return 0.0
    rounded = round(part / total, SHARE_DIGITS)
    if part > 0 and rounded == 0:
        # Una sezione con qualche chiamata economica è pur sempre qualcosa: a 0 il
        # frontend non disegnerebbe la barra e direbbe «0%», cioè zero chiamate. La
        # quota minima rappresentabile lo fa dire «< 1%» con la barra minima.
        return 10**-SHARE_DIGITS
    return rounded
