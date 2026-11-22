"""La rotta della bozza AI consegna `non_food` di ogni riga.

Il servizio lo calcola (tests/services/test_ai_recipes.py); qui si guarda che la rotta non lo
perda: un campo che manca in `DraftIngredientOut` Pydantic lo scarterebbe senza dire niente.
"""

import pytest

from app.domain.rules import IngredientRole
from app.services.llm import LLM_FAILURE_NOTICES, LlmFailureKind
from llm_fakes import FakeLlm, errore_api, messaggio


async def test_la_rotta_della_bozza_consegna_non_food(logged_client, monkeypatch):
    import app.api.recipes as rotte
    from app.services.ai_recipes import DraftIngredient, RecipeDraft

    async def bozza_finta(_session, _prompt):
        return RecipeDraft(
            title="Torta", description=None, instructions="1. cuoci", servings=2,
            ingredients=[
                DraftIngredient(
                    raw_name="carta forno", role=IngredientRole.SECONDARY,
                    quantity_text="1 foglio", ingredient_id=None, matched_name=None,
                    confident=False, non_food=True,
                ),
                DraftIngredient(
                    raw_name="farina", role=IngredientRole.PRIMARY, quantity_text="200 g",
                    ingredient_id=None, matched_name=None, confident=False,
                    proposed_category="cereali",
                ),
            ],
        )

    monkeypatch.setattr(rotte, "draft_recipe", bozza_finta)
    response = await logged_client.post("/api/v1/recipes/ai-draft", json={"prompt": "torta"})
    assert response.status_code == 200
    assert [riga["non_food"] for riga in response.json()["ingredients"]] == [True, False]


@pytest.mark.parametrize(
    ("risposta", "tipo"),
    [
        (errore_api(401, "authentication_error"), LlmFailureKind.AUTH),
        (errore_api(402, "billing_error"), LlmFailureKind.CREDIT),
        (errore_api(429, "rate_limit_error"), LlmFailureKind.RATE_LIMIT),
        (errore_api(400, "invalid_request_error"), LlmFailureKind.REJECTED),
        (errore_api(529, "overloaded_error"), LlmFailureKind.TRANSIENT),
        (messaggio("{", stop_reason="max_tokens"), LlmFailureKind.TRUNCATED),
        (messaggio("", stop_reason="refusal"), LlmFailureKind.REFUSAL),
        (messaggio("non è json"), LlmFailureKind.INVALID),
        (None, LlmFailureKind.NOT_CONFIGURED),
    ],
)
async def test_la_stesura_dice_il_motivo(logged_client, monkeypatch, risposta, tipo):
    """Il servizio vero, col trasporto finto: il 503 porta `llm_<tipo>` e la sua frase."""
    import app.services.llm as llm
    from app.core.config import get_settings

    get_settings.cache_clear()
    if risposta is None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    else:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "chiave-finta")
        monkeypatch.setattr(llm, "open_client", lambda: FakeLlm(risposta))
    try:
        response = await logged_client.post("/api/v1/recipes/ai-draft", json={"prompt": "torta"})
    finally:
        get_settings.cache_clear()

    assert response.status_code == 503
    assert response.json() == {"code": f"llm_{tipo.value}", "detail": LLM_FAILURE_NOTICES[tipo]}
