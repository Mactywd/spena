"""Il corpo di un 503 quando l'AI non può rispondere: uno solo, per ogni guasto.

È la forma dei 503 dei Pasti (`app/api/meals.py`): `{"code", "detail"}`. Il `code` è
`llm_<tipo>` (il tipo del guasto, `LlmFailureKind`) e il `detail` è la frase da mostrare,
già scritta in italiano per chi non è uno sviluppatore. Il frontend legge questo e basta.

Il dettaglio tecnico (`str(exc)`: lo stato HTTP, il messaggio dell'API) resta nei log, dove
`llm.py` lo scrive; non esce mai nel corpo. Mai un vicolo cieco: chi riceve un 503 di
questa forma ha comunque la strada a mano (la coda, la ricetta, i sostituti).
"""

from fastapi.responses import JSONResponse

from app.services.llm import LlmUnavailable


def llm_refusal(exc: LlmUnavailable) -> JSONResponse:
    return JSONResponse(
        status_code=503, content={"code": f"llm_{exc.kind.value}", "detail": exc.notice}
    )
