import uuid
from datetime import UTC, date, datetime

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.planning import MealProposal
from app.db.models.recipe import Recipe, RecipeIngredient
from app.domain.meal_chat import INTERRUPTED_HISTORY_LINE
from app.domain.meals import MealSlot
from app.services.claude.prompts import (
    COMMON_PROMPT,
    CHANGES_RULE,
    DISH_PROMPT,
    PLANNING_PROMPT,
    RECIPE_PROMPT,
    PlanningContext,
    DishContext,
    HistoryItem,
    dish_system_prompt,
    planning_system_prompt,
    recipe_system_prompt,
    render_planning_prompt,
    render_recipe_prompt,
    render_turn_prompt,
)
from app.services.utensils import (
    UTENSILS_PROMPT_RULE,
    UTENSILS_REPLY_RULE,
    UTENSILS_STEPS_RULE,
    render_utensils_block,
)


def test_il_prompt_del_piatto_senza_utensili():
    assert dish_system_prompt(None) == COMMON_PROMPT + "\n\n" + DISH_PROMPT + "\n\n" + CHANGES_RULE


def test_il_prompt_della_pianificazione():
    assert planning_system_prompt(None) == (
        COMMON_PROMPT + "\n\n" + PLANNING_PROMPT + "\n\n" + CHANGES_RULE
    )
    block = render_utensils_block([("frusta elettrica", None)])
    assert planning_system_prompt(block).endswith("\n\n" + block)


def test_il_prompt_della_ricetta():
    assert recipe_system_prompt(None) == COMMON_PROMPT + "\n\n" + RECIPE_PROMPT
    block = render_utensils_block([("frusta elettrica", None)])
    assert recipe_system_prompt(block) == COMMON_PROMPT + "\n\n" + RECIPE_PROMPT + "\n\n" + block


def test_la_ricetta_non_si_ferma_alla_scheda_gia_applicata():
    # I-2 della revisione del piano 4, deciso da Mattia il 2026-11-18: la scheda dei
    # cambi applicata prima della coda segna «Finito» proprio gli ingredienti del pasto.
    assert "scrivi comunque la ricetta del piatto deciso con quegli ingredienti" in RECIPE_PROMPT


def test_i_prompt_dicono_le_regole_degli_stati():
    for frase in (
        "diventa finito",
        "resta com'è",
        "appena aperto diventa quasi finito",
        "è avviato: non va in lista",
    ):
        assert frase in CHANGES_RULE
    for frase in (
        "mai nel passato",
        "5 g al giorno",
        "perché aiuta l'equilibrio",
        "propose_meals",
        "draft per la bozza",
    ):
        assert frase in PLANNING_PROMPT


def test_il_prompt_del_piatto_con_gli_utensili():
    block = render_utensils_block([("frusta elettrica", None)])
    prompt = dish_system_prompt(block)
    assert prompt.endswith(block)
    assert prompt.startswith(COMMON_PROMPT)


def test_il_prompt_dice_le_regole_della_skill():
    prompt = dish_system_prompt(None)
    for frase in (
        "già al netto dei pasti pianificati",
        "vasetto avviato",
        "5 g al giorno",
        "1 porzione",
        "Il ricettario di spena non lo leggi",
        "Il giorno e il pasto non li cambi tu",
    ):
        assert frase in prompt


def _recipe():
    spinaci = Ingredient(
        id=uuid.uuid4(), name="spinaci", display_name="Spinaci", category=IngredientCategory.VERDURA
    )
    uova = Ingredient(
        id=uuid.uuid4(), name="uova", display_name="Uova", category=IngredientCategory.LATTICINI
    )
    recipe = Recipe(
        title="Frittata di spinaci", description=None, instructions="1. Sbatti.\n2. Cuoci.",
        servings=1, source="ai",
    )
    recipe.ingredients = [
        RecipeIngredient(
            ingredient_id=spinaci.id, ingredient=spinaci, role="primary",
            quantity_text="150 g", note="congelati",
        ),
        RecipeIngredient(
            ingredient_id=uova.id, ingredient=uova, role="primary", quantity_text="2", note=None
        ),
    ]
    return recipe, spinaci, uova


def test_render_turn_prompt():
    recipe, spinaci, uova = _recipe()
    ctx = DishContext(
        today=date(2026, 11, 12), day=date(2026, 11, 10), slot=MealSlot.DINNER,
        dish="Frittata", sides="insalata", recipe=recipe,
    )
    history = [
        HistoryItem("user", "Metti più verdura", ()),
        HistoryItem("assistant", "Fatto.", ("Ricetta aggiornata: più spinaci — annullata",)),
    ]
    text = render_turn_prompt(ctx, history, "E se non ho le uova?")
    assert "Oggi: giovedì 12 novembre 2026" in text
    assert "martedì 10 novembre, cena" in text
    assert "Frittata" in text and "insalata" in text
    assert f"ingredient_id {spinaci.id}" in text and "150 g" in text
    assert f"ingredient_id {uova.id}" in text
    assert "1. Sbatti." in text
    assert text.index("Metti più verdura") < text.index("Ricetta aggiornata: più spinaci — annullata")
    assert text.index("annullata") < text.index("E se non ho le uova?")
    assert text.rstrip().endswith("E se non ho le uova?")

    senza = DishContext(
        today=date(2026, 11, 12), day=date(2026, 11, 10), slot=MealSlot.DINNER,
        dish="Frittata", sides=None, recipe=None,
    )
    assert "Il pasto non ha ancora una ricetta." in render_turn_prompt(senza, [], "ciao")


def test_render_planning_prompt():
    proposal = MealProposal(
        kind="official",
        rows=[
            {"day": "2026-11-13", "slot": "dinner", "dish": "Orata al forno", "sides": "patate"},
            {"day": "2026-11-14", "slot": "lunch", "dish": "Pasta al pesto", "sides": None},
        ],
    )
    context = PlanningContext(
        now=datetime(2026, 11, 12, 17, 40, tzinfo=UTC),
        focus=(date(2026, 11, 13), MealSlot.DINNER),
        open_proposal=proposal,
    )
    history = [
        HistoryItem("user", "Cosa mangio domani?", ()),
        HistoryItem(
            "assistant", "Ecco.",
            ("Proposta: Orata al forno — messa nella settimana",),
        ),
    ]
    text = render_planning_prompt(context, history, "Va bene")
    assert "Adesso: giovedì 12 novembre 2026, 18:40" in text
    assert "venerdì 13 novembre, cena" in text
    assert "Orata al forno, con patate" in text and "Pasta al pesto" in text
    assert "Proposta: Orata al forno — messa nella settimana" in text
    assert text.endswith("Va bene")


def test_render_planning_prompt_senza_posto_ne_proposta():
    context = PlanningContext(
        now=datetime(2026, 11, 12, 17, 40, tzinfo=UTC), focus=None, open_proposal=None
    )
    text = render_planning_prompt(context, [], "Ciao")
    assert "nessuna proposta" in text and "partito da" not in text


def test_render_recipe_prompt():
    ctx = DishContext(
        today=date(2026, 11, 12), day=date(2026, 11, 14), slot=MealSlot.LUNCH,
        dish="Pasta al pesto", sides=None, recipe=None,
    )
    history = [HistoryItem("user", "Pesto di basilico", ())]
    text = render_recipe_prompt(ctx, history)
    assert "sabato 14 novembre, pranzo" in text and "Pasta al pesto" in text
    assert "Pesto di basilico" in text


def test_la_cronologia_dice_la_risposta_interrotta():
    ctx = DishContext(
        today=date(2026, 11, 12), day=date(2026, 11, 14), slot=MealSlot.LUNCH,
        dish="Pasta al pesto", sides=None, recipe=None,
    )
    planning = PlanningContext(
        now=datetime(2026, 11, 12, 17, 40, tzinfo=UTC), focus=None, open_proposal=None
    )

    def history(interrupted):
        return [
            HistoryItem("user", "Cambia gli spinaci"),
            HistoryItem(
                "assistant", "Ho cambiato", ("Ricetta aggiornata: spinaci",),
                interrupted=interrupted,
            ),
        ]

    for render in (
        lambda h: render_turn_prompt(ctx, h, "ok"),
        lambda h: render_planning_prompt(planning, h, "ok"),
        lambda h: render_recipe_prompt(ctx, h),
    ):
        text = render(history(True))
        expected = "\n".join(
            ["Claude: Ho cambiato", "Ricetta aggiornata: spinaci", INTERRUPTED_HISTORY_LINE]
        )
        assert expected in text
        assert INTERRUPTED_HISTORY_LINE not in render(history(False))


def test_la_regola_dice_dove_dirlo():
    inizio = UTENSILS_PROMPT_RULE[: -len("dillo.")]
    nei_passi = render_utensils_block([("padella", None)], rule=UTENSILS_STEPS_RULE)
    assert nei_passi is not None and nei_passi.endswith(
        inizio
        + "scrivilo al primo passo del procedimento: della tua risposta resta solo la ricetta."
    )
    nella_risposta = render_utensils_block([("padella", None)], rule=UTENSILS_REPLY_RULE)
    assert nella_risposta is not None and nella_risposta.endswith(
        inizio + "dillo a Mattia nella risposta."
    )
    senza = render_utensils_block([("padella", None)])
    assert senza is not None and senza.endswith(UTENSILS_PROMPT_RULE)
