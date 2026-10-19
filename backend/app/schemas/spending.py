"""La risposta di `GET /api/v1/llm-spending` (H1)."""

from datetime import date

from pydantic import BaseModel

from app.domain.spending import SpendingPeriod


class SectionSpendOut(BaseModel):
    call_site: str
    # il nome a video; per una sezione che il backend non conosce, `call_site` com'è
    label: str
    cost_usd: float
    # la quota del totale, 0–1
    share: float
    calls: int


class DaySpendOut(BaseModel):
    # il giorno di calendario a Roma
    day: date
    cost_usd: float


class SpendingOut(BaseModel):
    period: SpendingPeriod
    first_day: date
    last_day: date
    # la somma dei costi dichiarati da OpenRouter, in dollari
    total_usd: float
    calls: int
    # le chiamate senza un costo dichiarato (tutte le fallite, qualche riuscita): contate
    # qui, fuori dal totale
    unpriced_calls: int
    # dalla più cara
    sections: list[SectionSpendOut]
    # ogni giorno del periodo, in ordine; quelli senza spesa a 0
    days: list[DaySpendOut]
