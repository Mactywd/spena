"""Le spese dell'AI (H1): il totale del periodo, per sezione e giorno per giorno."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import require_session
from app.domain.rules import today_in_pantry
from app.domain.spending import SpendingPeriod
from app.schemas.spending import SpendingOut
from app.services.spending import spending_report

router = APIRouter(
    prefix="/api/v1/llm-spending", tags=["spending"], dependencies=[Depends(require_session)]
)


@router.get("", response_model=SpendingOut)
async def get_spending(
    period: SpendingPeriod = SpendingPeriod.MONTH,
    session: AsyncSession = Depends(get_session),
) -> SpendingOut:
    # «oggi» a Roma, come la scadenza: è il giorno di chi guarda, non quello di UTC
    return await spending_report(session, period, today_in_pantry())
