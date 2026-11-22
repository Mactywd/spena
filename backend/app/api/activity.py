"""L'attività da Health Connect (H2).

Due router con lo stesso prefisso. `webhook_router` porta l'unica rotta dell'app fuori
dalla sessione che scrive: la apre la chiave in `X-Spena-Token`, perché HC Webhook non ha
il cookie. `router` porta quelle della schermata, dietro la sessione come tutte.
"""

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import require_session
from app.domain.activity import (
    NOT_JSON,
    NOT_OBJECT,
    TOKEN_HEADER,
    TOO_BIG,
    WEBHOOK_MAX_BYTES,
    parse_payload,
)
from app.schemas.activity import ActivityOut, TokenOut
from app.services.activity import (
    activity_summary,
    authenticate_webhook,
    receive_payload,
    regenerate_token,
    reject_payload,
)

router = APIRouter(
    prefix="/api/v1/activity", tags=["activity"], dependencies=[Depends(require_session)]
)
webhook_router = APIRouter(prefix="/api/v1/activity", tags=["activity"])


def _declared_size(request: Request) -> int | None:
    """La lunghezza dichiarata, o `None` se manca o non è un numero credibile.

    Solo cifre ASCII e al massimo dieci: oltre le 4300 cifre `int()` solleva, e sarebbe un
    500 su un'intestazione. `None` vuol dire «non lo so»: la lettura a pezzi si ferma
    comunque al limite.
    """
    declared = request.headers.get("content-length", "")
    if declared.isascii() and declared.isdigit() and len(declared) <= 10:
        return int(declared)
    return None


async def _read_capped(request: Request) -> bytes | None:
    """Il corpo, o `None` se supera `WEBHOOK_MAX_BYTES`.

    Letto a pezzi e fermato al limite: una lunghezza dichiarata si può non dichiarare
    (`Transfer-Encoding: chunked`), e leggere tutto per poi misurarlo vorrebbe dire tenere
    in memoria quel che si voleva rifiutare.
    """
    declared = _declared_size(request)
    if declared is not None and declared > WEBHOOK_MAX_BYTES:
        return None
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > WEBHOOK_MAX_BYTES:
            return None
    return bytes(body)


async def _rejected(
    session: AsyncSession, problem: str, body_bytes: int, now: datetime, code: int
) -> JSONResponse:
    await reject_payload(session, problem, body_bytes, now)
    await session.commit()
    return JSONResponse({"detail": problem}, status_code=code)


@webhook_router.post("/hc-webhook", include_in_schema=False)
async def hc_webhook(request: Request, session: AsyncSession = Depends(get_session)) -> Response:
    # Il rifiuto è silenzioso e uguale per tutti (spec H2 §3.1): niente corpo, niente
    # scritture, nessun indizio su cosa mancava. Prima della chiave non si legge il corpo.
    token = await authenticate_webhook(session, request.headers.get(TOKEN_HEADER))
    if token is None:
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    now = datetime.now(UTC)
    token.last_used_at = now
    body = await _read_capped(request)
    if body is None:
        declared = _declared_size(request)
        size = WEBHOOK_MAX_BYTES + 1 if declared is None else declared
        return await _rejected(
            session, TOO_BIG, min(size, 2**31 - 1), now, status.HTTP_413_CONTENT_TOO_LARGE
        )
    try:
        data = json.loads(body)
    except (ValueError, RecursionError):
        # ValueError copre anche i byte che non sono UTF-8 e gli interi di migliaia di
        # cifre; RecursionError un JSON annidato a fondo. Nessuno dei due è un 500.
        return await _rejected(session, NOT_JSON, len(body), now, status.HTTP_400_BAD_REQUEST)
    if not isinstance(data, dict):
        return await _rejected(session, NOT_OBJECT, len(body), now, status.HTTP_400_BAD_REQUEST)

    result = await receive_payload(session, parse_payload(data), len(body), now)
    await session.commit()
    return JSONResponse(result)


@router.get("", response_model=ActivityOut)
async def get_activity(session: AsyncSession = Depends(get_session)) -> ActivityOut:
    return await activity_summary(session, datetime.now(UTC))


@router.post("/token", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
async def create_token(session: AsyncSession = Depends(get_session)) -> TokenOut:
    # crea o rigenera: la chiave di prima smette di valere con questo commit
    token = await regenerate_token(session, datetime.now(UTC))
    await session.commit()
    return TokenOut(token=token, header=TOKEN_HEADER)
