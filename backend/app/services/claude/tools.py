"""Gli strumenti di Claude dentro spena (spec 2026-11-12 §6): quattro di lettura e uno di
scrittura, sul server MCP `spena` che `client.build_options` costruisce.

Ogni handler tiene `ctx.lock` per tutto il tempo in cui usa `ctx.session`: gli strumenti di
sola lettura possono arrivare in parallelo, e una sessione async non regge due operazioni
insieme. Un errore di uno strumento è `{"content": [...], "is_error": True}`: Claude lo
legge e corregge, il giro non cade.
"""

import asyncio
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal

from claude_agent_sdk import SdkMcpTool, ToolAnnotations, tool
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe_change import RecipeChange
from app.domain.meal_chat import MAX_MEALS_RANGE_DAYS
from app.domain.meals import MealSlot
from app.domain.rules import (
    ExpiryState,
    IngredientKind,
    IngredientRole,
    PantryStatus,
    expiry_state,
    kind_for_category,
)
from app.repositories.ingredients import search_ingredients
from app.repositories.meals import get_meal, meals_between
from app.repositories.pantry import list_pantry
from app.repositories.shopping import list_items
from app.services.claude.client import SPENA_SERVER
from app.services.claude.prompts import SLOT_NAMES, day_name
from app.services.meal_recipes import (
    UNSET,
    DraftLine,
    MealRecipeDraft,
    RecipeWriteRefused,
    write_meal_recipe,
)
from app.services.meals import MealRefusal
from app.services.registry import ACTIVE_SHOPPING

__all__ = [
    "SPENA_SERVER",
    "TurnContext",
    "dish_tools",
    "read_tools",
    "write_recipe_tool",
]

SEARCH_LIMIT = 8
FOOD_DEPARTMENTS = [
    c.value for c in IngredientCategory if kind_for_category(c.value) == IngredientKind.FOOD
]
RANGE_ERROR = "Chiedi al massimo 28 giorni alla volta, con end non prima di start."
assert MAX_MEALS_RANGE_DAYS == 28


@dataclass
class TurnContext:
    session: AsyncSession
    lock: asyncio.Lock
    today: date
    meal_id: uuid.UUID | None
    conversation_id: uuid.UUID
    turn_message_id: uuid.UUID
    on_change: Callable[[RecipeChange], Awaitable[None]]


def _ok(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}]}


def _error(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "is_error": True}


def _short_date(day: date) -> str:
    return day_name(day).split(" ", 1)[1]  # «14 novembre»


_STATUS_WORDS = {
    PantryStatus.AVAILABLE.value: "c'è",
    PantryStatus.LOW.value: "quasi finito",
    PantryStatus.FINISHED.value: "finito",
}


# --- lettura -----------------------------------------------------------------------------


def read_tools(ctx: TurnContext) -> list[SdkMcpTool]:
    read_only = ToolAnnotations(readOnlyHint=True)

    @tool(
        "read_pantry",
        "Legge la dispensa di Mattia, per reparto: per ogni voce il nome, il prodotto se c'è, "
        "lo stato («c'è», «quasi finito», «finito») e la scadenza se c'è. Niente quantità: "
        "la dispensa non le conosce. È già al netto dei pasti pianificati.",
        {"type": "object", "properties": {}, "additionalProperties": False},
        annotations=read_only,
    )
    async def read_pantry(args: dict[str, Any]) -> dict[str, Any]:
        async with ctx.lock:
            items = await list_pantry(ctx.session)
        groups: dict[str, list[str]] = defaultdict(list)
        for item in items:
            ingredient = item.ingredient
            if kind_for_category(ingredient.category) != IngredientKind.FOOD:
                continue
            row = f"- {ingredient.display_name}"
            if item.product is not None:
                row += f" ({item.product.name})"
            row += f": {_STATUS_WORDS.get(item.status, item.status)}"
            if item.expires_on is not None:
                when = _short_date(item.expires_on)
                state = expiry_state(item.expires_on, ctx.today)
                if state == ExpiryState.EXPIRED:
                    row += f", scaduto il {when}"
                elif state == ExpiryState.SOON:
                    row += f", scade presto: il {when}"
                else:
                    row += f", scade il {when}"
            groups[ingredient.category].append(row)
        if not groups:
            return _ok("La dispensa è vuota.")
        blocks = []
        for category in IngredientCategory:
            if category.value in groups:
                blocks.append("\n".join([f"{category.value.capitalize()}:", *groups[category.value]]))
        return _ok("\n\n".join(blocks))

    @tool(
        "read_shopping_list",
        "Legge la lista della spesa: le voci attive, da comprare o già nel carrello.",
        {"type": "object", "properties": {}, "additionalProperties": False},
        annotations=read_only,
    )
    async def read_shopping_list(args: dict[str, Any]) -> dict[str, Any]:
        async with ctx.lock:
            items = await list_items(ctx.session, [s.value for s in ACTIVE_SHOPPING])
        if not items:
            return _ok("La lista della spesa è vuota.")
        rows = [
            f"- {i.raw_text} — {'nel carrello' if i.status == 'checked' else 'da comprare'}"
            for i in items
        ]
        return _ok("\n".join(rows))

    @tool(
        "read_meals",
        "Legge i pasti di un intervallo di date (start e end, AAAA-MM-GG, estremi compresi; "
        f"al massimo {MAX_MEALS_RANGE_DAYS} giorni): per ogni giorno pranzo e cena, con piatto, "
        "accompagnamenti, segni (fuori casa, bozza, avanzo) e la ricetta se c'è.",
        {
            "type": "object",
            "properties": {
                "start": {"type": "string", "description": "Primo giorno, AAAA-MM-GG."},
                "end": {"type": "string", "description": "Ultimo giorno, AAAA-MM-GG."},
            },
            "required": ["start", "end"],
            "additionalProperties": False,
        },
        annotations=read_only,
    )
    async def read_meals(args: dict[str, Any]) -> dict[str, Any]:
        try:
            start = date.fromisoformat(str(args.get("start")))
            end = date.fromisoformat(str(args.get("end")))
        except ValueError:
            return _error("Le date vanno scritte AAAA-MM-GG, per esempio 2026-11-10.")
        if end < start or (end - start).days + 1 > MAX_MEALS_RANGE_DAYS:
            return _error(RANGE_ERROR)
        async with ctx.lock:
            meals = await meals_between(ctx.session, start, end)
        found = {(m.day, m.slot): m for m in meals}
        blocks = []
        day = start
        while day <= end:
            rows = [day_name(day) + ":"]
            for slot in (MealSlot.LUNCH, MealSlot.DINNER):
                meal = found.get((day, slot.value))
                label = SLOT_NAMES[slot.value]
                if meal is None:
                    rows.append(f"{label}: (vuoto)")
                    continue
                rows.append(f"{label}: {_describe_meal(meal)}")
            blocks.append("\n".join(rows))
            day += timedelta(days=1)
        return _ok("\n\n".join(blocks))

    @tool(
        "search_ingredients",
        "Cerca nell'anagrafica degli ingredienti di Mattia (solo alimentari) per nome. "
        "Restituisce fino a 8 voci con il loro id e il reparto.",
        {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Il nome da cercare."}},
            "required": ["name"],
            "additionalProperties": False,
        },
        annotations=read_only,
    )
    async def search(args: dict[str, Any]) -> dict[str, Any]:
        name = str(args.get("name") or "")
        async with ctx.lock:
            found = await search_ingredients(
                ctx.session, name, limit=SEARCH_LIMIT, kind=IngredientKind.FOOD
            )
        if not found:
            return _ok("Nessun ingrediente con questo nome: usa name e department nella riga.")
        return _ok(
            "\n".join(f"- {i.display_name} · id {i.id} · reparto {i.category}" for i in found)
        )

    return [read_pantry, read_shopping_list, read_meals, search]


def _describe_meal(meal: Any) -> str:
    text = meal.dish
    if meal.sides:
        text += f", con {meal.sides}"
    marks = []
    if meal.away:
        marks.append("fuori casa")
    if meal.status == "draft":
        marks.append("bozza")
    if meal.leftover_of is not None:
        marks.append(f"avanzo di {meal.leftover_of.dish}")
    if marks:
        text += f" ({', '.join(marks)})"
    recipe = meal.recipe
    if recipe is not None:
        head = f"ricetta: {recipe.title}"
        if recipe.servings is not None:
            head += f", {recipe.servings} porz."
        rows = [text, head]
        for ri in sorted(recipe.ingredients, key=lambda r: r.ingredient.display_name.lower()):
            row = f"  - {ri.ingredient.display_name}"
            if ri.quantity_text:
                row += f": {ri.quantity_text}"
            if ri.note:
                row += f" ({ri.note})"
            rows.append(row)
        rows.append(f"  Procedimento: {recipe.instructions}")
        return "\n".join(rows)
    return text


# --- scrittura ---------------------------------------------------------------------------


class _LineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingredient_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    department: Literal[*FOOD_DEPARTMENTS] | None = None  # type: ignore[valid-type]
    role: Literal["primary", "secondary"]
    quantity: str | None = Field(default=None, max_length=100)
    note: str | None = Field(default=None, max_length=300)


class _WriteRecipeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    servings: int = Field(ge=1, le=50)
    description: str | None = None
    instructions: str = Field(min_length=1)
    ingredients: list[_LineIn] = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=200)
    dish: str | None = Field(default=None, min_length=1, max_length=200)
    sides: str | None = Field(default=None, max_length=200)


_LINE_SCHEMA = {
    "type": "object",
    "properties": {
        "ingredient_id": {
            "type": "string",
            "description": "L'id trovato con search_ingredients. Se lo dai, name e department no.",
        },
        "name": {"type": "string", "description": "Il nome, solo se l'ingrediente non è in anagrafica."},
        "department": {
            "type": "string",
            "enum": FOOD_DEPARTMENTS,
            "description": "Il reparto, obbligatorio con name.",
        },
        "role": {
            "type": "string",
            "enum": ["primary", "secondary"],
            "description": "primary se senza non si fa il piatto, secondary altrimenti.",
        },
        "quantity": {"type": "string", "description": "La dose come la scriveresti: «150 g», «2», «q.b.»."},
        "note": {"type": "string", "description": "Una nota breve, facoltativa."},
    },
    "required": ["role"],
    "additionalProperties": False,
}

_WRITE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Il titolo della ricetta (1–200 caratteri)."},
        "servings": {"type": "integer", "minimum": 1, "maximum": 50, "description": "Le porzioni."},
        "description": {"type": "string", "description": "Una riga di presentazione, facoltativa."},
        "instructions": {"type": "string", "description": "Il procedimento, a passi numerati."},
        "ingredients": {
            "type": "array",
            "minItems": 1,
            "items": _LINE_SCHEMA,
            "description": "Tutte le righe della ricetta, anche quelle che non cambiano.",
        },
        "summary": {
            "type": "string",
            "description": "La riga che Mattia legge sotto la risposta: cosa è cambiato (max 200).",
        },
        "dish": {"type": "string", "description": "Il nuovo nome del piatto nella settimana, solo se cambia."},
        "sides": {
            "type": "string",
            "description": "I nuovi accompagnamenti, solo se cambiano; stringa vuota per toglierli.",
        },
    },
    "required": ["title", "servings", "instructions", "ingredients", "summary"],
    "additionalProperties": False,
}


def _validation_message(exc: ValidationError) -> str:
    first = exc.errors()[0]
    field = ".".join(str(p) for p in first["loc"]) or "argomenti"
    return f"Argomenti non validi: {field}: {first['msg']}. Non è stato scritto niente."


def write_recipe_tool(ctx: TurnContext) -> SdkMcpTool:
    @tool(
        "write_recipe",
        "Scrive la ricetta del pasto di questa chat: la ricetta intera (titolo, porzioni, "
        "procedimento, tutte le righe), più summary, la riga che Mattia legge sotto la risposta. "
        "Facoltativi dish e sides, se il piatto cambia davvero. Il giorno e il pasto non si "
        "cambiano. Se rifiuta, non è stato scritto niente.",
        _WRITE_SCHEMA,
    )
    async def write_recipe(args: dict[str, Any]) -> dict[str, Any]:
        if ctx.meal_id is None:
            return _error("Questa chat non ha un pasto: non c'è una ricetta da scrivere.")
        try:
            data = _WriteRecipeIn.model_validate(args)
        except ValidationError as exc:
            return _error(_validation_message(exc))
        lines = tuple(
            DraftLine(
                ingredient_id=line.ingredient_id,
                name=line.name,
                category=IngredientCategory(line.department) if line.department else None,
                role=IngredientRole(line.role),
                quantity_text=line.quantity,
                note=line.note,
            )
            for line in data.ingredients
        )
        draft = MealRecipeDraft(
            title=data.title,
            description=data.description,
            instructions=data.instructions,
            servings=data.servings,
            lines=lines,
            summary=data.summary,
            dish=data.dish,
            sides=UNSET if "sides" not in data.model_fields_set else (data.sides or None),
        )
        async with ctx.lock:
            meal = await get_meal(ctx.session, ctx.meal_id)
            if meal is None:
                return _error("Il pasto non esiste più.")
            try:
                change = await write_meal_recipe(
                    ctx.session,
                    meal,
                    draft,
                    conversation_id=ctx.conversation_id,
                    turn_message_id=ctx.turn_message_id,
                )
            except (RecipeWriteRefused, MealRefusal) as exc:
                return _error(exc.message)
            await ctx.session.commit()
            await ctx.on_change(change)
        return _ok("Scritta. Mattia vede la ricetta aggiornata.")

    return write_recipe


def dish_tools(ctx: TurnContext) -> list[SdkMcpTool]:
    # il piano 4 (pianificazione) aggiunge qui i suoi strumenti
    return [*read_tools(ctx), write_recipe_tool(ctx)]
