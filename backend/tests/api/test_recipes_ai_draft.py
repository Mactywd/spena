"""La rotta della bozza AI consegna `non_food` di ogni riga.

Il servizio lo calcola (tests/services/test_ai_recipes.py); qui si guarda che la rotta non lo
perda: un campo che manca in `DraftIngredientOut` Pydantic lo scarterebbe senza dire niente.
"""

from app.domain.rules import IngredientRole


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
