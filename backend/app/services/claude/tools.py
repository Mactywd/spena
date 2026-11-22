"""Gli strumenti di Claude dentro spena (spec 2026-11-12 §6): quattro di lettura, la scrittura
della ricetta e le due proposte (`propose_meals`, `propose_changes`: Claude propone, Mattia
applica), sul server MCP `spena` che `client.build_options` costruisce.

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
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.change_card import ChangeCard
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.planning import MealProposal, ProposalKind
from app.db.models.recipe_change import RecipeChange
from app.domain.meal_chat import MAX_MEALS_RANGE_DAYS
from app.domain.meals import MealSlot
from app.domain.recipe_changes import MealSnapshot, snapshot_from_json
from app.domain.rules import (
    ExpiryState,
    IngredientKind,
    IngredientRole,
    PantryStatus,
    expiry_state,
    kind_for_category,
)
from app.repositories.ingredients import search_ingredients
from app.repositories.meals import get_meal, meal_at, meals_between
from app.repositories.pantry import list_pantry
from app.repositories.shopping import list_items
from app.services.change_cards import (
    CardRefusal,
    CardRefusalCode,
    ListProposal,
    PantryProposal,
    propose_card,
)
from app.services.claude.client import SPENA_SERVER
from app.services.claude.prompts import SLOT_NAMES, day_name
from app.services.meal_recipes import (
    MEAL_GONE_MESSAGE,
    UNSET,
    DraftLine,
    MealRecipeDraft,
    RecipeWriteRefused,
    meal_snapshot,
    write_meal_recipe,
)
from app.services.ingredient_match import exact_ingredient
from app.services.meals import MealRefusal
from app.services.planning import PlanningRefusal, ProposedMeal, propose_meals
from app.services.registry import ACTIVE_SHOPPING

__all__ = [
    "SPENA_SERVER",
    "TurnContext",
    "dish_tools",
    "planning_tools",
    "propose_changes_tool",
    "propose_meals_tool",
    "read_tools",
    "recipe_tools",
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
    conversation_id: uuid.UUID | None
    turn_message_id: uuid.UUID | None
    on_change: Callable[[RecipeChange], Awaitable[None]]
    # i giri delle ricette non hanno un messaggio né schede da mostrare: None = niente
    on_proposal: Callable[[MealProposal], Awaitable[None]] | None = None
    on_card: Callable[[ChangeCard], Awaitable[None]] | None = None
    # il giro scrive una ricetta nuova: non ne riscrive una che c'era già (decisione 15)
    create_only: bool = False
    # il pasto com'è nel prompt del giro del piatto: `write_recipe` scrive solo se è ancora
    # questo (una correzione a mano nel frattempo non si perde). None = nessun controllo
    seen: MealSnapshot | None = None


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


async def _end_read(ctx: TurnContext) -> None:
    """Chiude la transazione che la lettura ha aperto, perché la sessione non resti «idle in
    transaction» mentre Claude pensa. Un `commit` e non un `rollback`: il rollback scade gli
    oggetti caricati, il commit no (`expire_on_commit=False`); e non c'è mai niente in
    sospeso, perché le scritture si committano da sé."""
    await ctx.session.commit()


def read_tools(ctx: TurnContext) -> list[SdkMcpTool]:
    read_only = ToolAnnotations(readOnlyHint=True)

    @tool(
        "read_pantry",
        "Legge la dispensa di Mattia, per reparto: per ogni voce il nome, il prodotto se c'è, "
        "lo stato («c'è», «quasi finito», «finito»), la scadenza se c'è e l'id, che serve a "
        "propose_changes. Niente quantità: "
        "la dispensa non le conosce. È già al netto dei pasti pianificati.",
        {"type": "object", "properties": {}, "additionalProperties": False},
        annotations=read_only,
    )
    async def read_pantry(args: dict[str, Any]) -> dict[str, Any]:
        async with ctx.lock:
            items = await list_pantry(ctx.session)
            await _end_read(ctx)
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
            row += f" · id {item.id}"
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
            await _end_read(ctx)
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
            # rileggere il pasto di questa chat è vederlo com'è adesso
            if ctx.seen is not None:
                mine = next((m for m in meals if m.id == ctx.meal_id), None)
                if mine is not None:
                    ctx.seen = await meal_snapshot(ctx.session, mine)
            await _end_read(ctx)
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
            await _end_read(ctx)
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
    recipe = None if meal.away else meal.recipe  # fuori casa la ricetta è nascosta
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
    written: set[uuid.UUID] = set()  # le ricette create da questo giro

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
                await ctx.session.commit()
                return _error(MEAL_GONE_MESSAGE)
            # «solo una ricetta nuova» si controlla dentro `write_meal_recipe`, col pasto
            # bloccato: qui la lettura è senza lucchetto e una ricetta a mano può arrivare dopo
            allowed = frozenset({None, *written}) if ctx.create_only else None
            try:
                change = await write_meal_recipe(
                    ctx.session,
                    meal,
                    draft,
                    conversation_id=ctx.conversation_id,
                    turn_message_id=ctx.turn_message_id,
                    expected=ctx.seen,
                    allowed_recipe_ids=allowed,
                )
            except (RecipeWriteRefused, MealRefusal) as exc:
                # La lettura ha aperto una transazione: chiuderla (come `_end_read`), o la connessione resta
                # «idle in transaction» finché Claude pensa.
                await ctx.session.commit()
                return _error(exc.message)
            if ctx.seen is not None:
                ctx.seen = snapshot_from_json(change.after)
            if meal.recipe_id is not None:
                written.add(meal.recipe_id)
            await ctx.session.commit()
            await ctx.on_change(change)
        return _ok("Scritta. Mattia vede la ricetta aggiornata.")

    return write_recipe


# --- proposte ------------------------------------------------------------------------------


class _PlaceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day: date
    slot: Literal["lunch", "dinner"]


class _MealIn(_PlaceIn):
    dish: str = Field(min_length=1, max_length=200)
    sides: str | None = Field(default=None, max_length=200)

    @field_validator("dish")
    @classmethod
    def _dish_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("il piatto è vuoto")
        return value


class _ProposeMealsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["official", "draft"]
    meals: list[_MealIn] = Field(min_length=1, max_length=14)


class _PantryRowIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pantry_item_id: uuid.UUID
    to: Literal["available", "low", "finished"]
    meals: list[_PlaceIn] | None = Field(default=None, min_length=1, max_length=14)


class _ShoppingRowIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingredient_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=120)
    meals: list[_PlaceIn] | None = Field(default=None, min_length=1, max_length=14)

    @model_validator(mode="after")
    def _one_way_to_say_it(self) -> "_ShoppingRowIn":
        if self.ingredient_id is None and not (self.name or "").strip():
            raise ValueError("serve ingredient_id oppure name")
        return self


class _ProposeChangesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meals: list[_PlaceIn] | None = Field(default=None, min_length=1, max_length=14)
    pantry: list[_PantryRowIn] = Field(default_factory=list, max_length=40)
    shopping: list[_ShoppingRowIn] = Field(default_factory=list, max_length=40)

    @model_validator(mode="after")
    def _not_empty(self) -> "_ProposeChangesIn":
        if not self.pantry and not self.shopping:
            raise ValueError("la scheda non ha voci: serve almeno una riga in pantry o shopping")
        return self


_PLACE_PROPERTIES = {
    "day": {"type": "string", "description": "Il giorno, AAAA-MM-GG."},
    "slot": {"type": "string", "enum": ["lunch", "dinner"], "description": "Pranzo o cena."},
}
_PLACE_SCHEMA = {
    "type": "object",
    "properties": _PLACE_PROPERTIES,
    "required": ["day", "slot"],
    "additionalProperties": False,
}


def _places_schema(description: str) -> dict[str, Any]:
    return {
        "type": "array",
        "minItems": 1,
        "maxItems": 14,
        "items": _PLACE_SCHEMA,
        "description": description,
    }


_PROPOSE_MEALS_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {
            "type": "string",
            "enum": ["official", "draft"],
            "description": "official per pasti con quello che c'è o per ufficializzare una bozza, "
            "draft per la bozza prima della spesa.",
        },
        "meals": {
            "type": "array",
            "minItems": 1,
            "maxItems": 14,
            "items": {
                "type": "object",
                "properties": {
                    **_PLACE_PROPERTIES,
                    "dish": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 200,
                        "pattern": "\\S",
                        "description": "Il nome breve del piatto, come si legge nella settimana.",
                    },
                    "sides": {
                        "type": "string",
                        "maxLength": 200,
                        "description": "Gli accompagnamenti, scritti corti; facoltativi.",
                    },
                },
                "required": ["day", "slot", "dish"],
                "additionalProperties": False,
            },
            "description": "I pasti proposti, posto per posto, da oggi in avanti.",
        },
    },
    "required": ["kind", "meals"],
    "additionalProperties": False,
}

_PROPOSE_CHANGES_SCHEMA = {
    "type": "object",
    "properties": {
        "meals": _places_schema(
            "I posti dei pasti a cui la scheda si riferisce, già nella settimana. Nella chat di "
            "un piatto, se manca, è il pasto del piatto."
        ),
        "pantry": {
            "type": "array",
            "maxItems": 40,
            "items": {
                "type": "object",
                "properties": {
                    "pantry_item_id": {"type": "string", "description": "L'id letto con read_pantry."},
                    "to": {
                        "type": "string",
                        "enum": ["available", "low", "finished"],
                        "description": "Lo stato che la voce diventa.",
                    },
                    "meals": _places_schema("Per quali pasti serve, se non tutti quelli della scheda."),
                },
                "required": ["pantry_item_id", "to"],
                "additionalProperties": False,
            },
            "description": "Le voci della dispensa che cambiano stato.",
        },
        "shopping": {
            "type": "array",
            "maxItems": 40,
            "items": {
                "type": "object",
                "properties": {
                    "ingredient_id": {
                        "type": "string",
                        "description": "L'id trovato con search_ingredients.",
                    },
                    "name": {
                        "type": "string",
                        "description": "Il nome esatto di un ingrediente in anagrafica, al posto dell'id.",
                    },
                    "meals": _places_schema("Per quali pasti serve, se non tutti quelli della scheda."),
                },
                "additionalProperties": False,
            },
            "description": "Le cose da comprare che mancano e non sono già in lista.",
        },
    },
    "additionalProperties": False,
}


def _place_text(day: date, slot: str) -> str:
    return f"{day_name(day)} · {SLOT_NAMES[slot]}"


def propose_meals_tool(ctx: TurnContext) -> SdkMcpTool:
    @tool(
        "propose_meals",
        "Propone a Mattia i pasti della settimana: kind (official o draft) e i pasti, ognuno con "
        "giorno, pranzo o cena, piatto e accompagnamenti. Mattia vede una scheda e la mette nella "
        "settimana con un tocco. Una proposta nuova sostituisce quella precedente: mandala intera. "
        "Se rifiuta, non è stato salvato niente.",
        _PROPOSE_MEALS_SCHEMA,
    )
    async def propose(args: dict[str, Any]) -> dict[str, Any]:
        if ctx.conversation_id is None:
            return _error("Questa chat non è una pianificazione: non si possono proporre pasti.")
        try:
            data = _ProposeMealsIn.model_validate(args)
        except ValidationError as exc:
            return _error(_validation_message(exc))
        meals = [
            ProposedMeal(day=m.day, slot=MealSlot(m.slot), dish=m.dish, sides=m.sides)
            for m in data.meals
        ]
        async with ctx.lock:
            try:
                proposal = await propose_meals(
                    ctx.session,
                    conversation_id=ctx.conversation_id,
                    turn_message_id=ctx.turn_message_id,
                    kind=ProposalKind(data.kind),
                    meals=meals,
                    today=ctx.today,
                )
            except PlanningRefusal as exc:
                await ctx.session.commit()
                return _error(exc.message)
            await ctx.session.commit()
            if ctx.on_proposal is not None:
                await ctx.on_proposal(proposal)
        return _ok(
            "Proposta mandata: Mattia la vede come scheda e la mette nella settimana con un tocco."
        )

    return propose


class _Refused(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


async def _meals_at(session: AsyncSession, places: list[_PlaceIn]) -> list[Any]:
    found = []
    for place in places:
        meal = await meal_at(session, place.day, MealSlot(place.slot))
        if meal is None:
            raise _Refused(
                f"Nessun pasto in {_place_text(place.day, place.slot)}: "
                "la scheda è per pasti già nella settimana."
            )
        found.append(meal)
    return found


def _food_or_refuse(ingredient: Ingredient) -> None:
    if ingredient.kind != IngredientKind.FOOD.value:
        raise _Refused(f"{ingredient.display_name} non è un alimento: non va nella scheda.")


async def _build_card_inputs(
    ctx: TurnContext, data: _ProposeChangesIn
) -> tuple[list[Any], list[PantryProposal], list[ListProposal]]:
    session = ctx.session
    if data.meals is not None:
        meals = await _meals_at(session, data.meals)
    elif ctx.meal_id is not None:
        meal = await get_meal(session, ctx.meal_id)
        if meal is None:
            raise _Refused("Il pasto non esiste più.")
        meals = [meal]
    else:
        raise _Refused("Dì per quali pasti è la scheda: manca meals.")
    card_ids = {m.id for m in meals}

    async def row_meal_ids(places: list[_PlaceIn] | None) -> tuple[uuid.UUID, ...]:
        if places is None:
            return ()
        row_meals = await _meals_at(session, places)
        for place, meal in zip(places, row_meals, strict=True):
            if meal.id not in card_ids:
                raise _Refused(
                    f"{_place_text(place.day, place.slot)} non è fra i pasti della scheda."
                )
        return tuple(m.id for m in row_meals)

    pantry: list[PantryProposal] = []
    for row in data.pantry:
        item = await session.get(PantryItem, row.pantry_item_id)
        if item is None or item.archived_at is not None:
            raise _Refused(f"La voce {row.pantry_item_id} non è in dispensa: rileggi con read_pantry.")
        ingredient = await session.get(Ingredient, item.ingredient_id)
        assert ingredient is not None
        _food_or_refuse(ingredient)
        pantry.append(
            PantryProposal(
                item.id, PantryStatus(row.to), await row_meal_ids(row.meals)
            )
        )

    shopping: list[ListProposal] = []
    for row in data.shopping:
        if row.ingredient_id is not None:
            found = await session.get(Ingredient, row.ingredient_id)
            if found is None:
                raise _Refused(
                    f"{row.ingredient_id} non è nell'anagrafica: cercalo con search_ingredients."
                )
        else:
            name = (row.name or "").strip()
            found = await exact_ingredient(session, name)
            if found is None:
                raise _Refused(f"{name} non è nell'anagrafica: cercalo con search_ingredients.")
        _food_or_refuse(found)
        shopping.append(
            ListProposal(found.id, found.display_name, await row_meal_ids(row.meals))
        )
    return meals, pantry, shopping


def propose_changes_tool(ctx: TurnContext) -> SdkMcpTool:
    @tool(
        "propose_changes",
        "Propone a Mattia la scheda dei cambi per uno o più pasti: le voci della dispensa (con il "
        "loro id e lo stato che diventano) e le cose da comprare. Non scrive mai in dispensa né in "
        "lista: Mattia rivede la scheda e la applica lui. Nella chat di un piatto, senza meals la "
        "scheda è per il pasto del piatto. Se rifiuta, non è stato salvato niente.",
        _PROPOSE_CHANGES_SCHEMA,
    )
    async def propose(args: dict[str, Any]) -> dict[str, Any]:
        try:
            data = _ProposeChangesIn.model_validate(args)
        except ValidationError as exc:
            return _error(_validation_message(exc))
        async with ctx.lock:
            try:
                meals, pantry, shopping = await _build_card_inputs(ctx, data)
                card = await propose_card(
                    ctx.session,
                    meals=meals,
                    pantry=pantry,
                    shopping=shopping,
                    conversation_id=ctx.conversation_id,
                    turn_message_id=ctx.turn_message_id,
                )
            except _Refused as exc:
                await ctx.session.commit()
                return _error(exc.message)
            except CardRefusal as exc:
                await ctx.session.commit()
                if exc.code == CardRefusalCode.LIST_ONLY:
                    return _error(
                        "Per una bozza la scheda ha solo le cose da comprare: la dispensa si "
                        "aggiorna quando i pasti diventano ufficiali."
                    )
                return _error(exc.message)
            await ctx.session.commit()
            if ctx.on_card is not None:
                await ctx.on_card(card)
        return _ok("Scheda mandata: Mattia la rivede e la applica.")

    return propose


def dish_tools(ctx: TurnContext) -> list[SdkMcpTool]:
    # la scheda dei cambi è propose_changes: la ricetta si scrive, dispensa e lista si propongono
    return [*read_tools(ctx), write_recipe_tool(ctx), propose_changes_tool(ctx)]


def planning_tools(ctx: TurnContext) -> list[SdkMcpTool]:
    return [*read_tools(ctx), propose_meals_tool(ctx), propose_changes_tool(ctx)]


def recipe_tools(ctx: TurnContext) -> list[SdkMcpTool]:
    return [*read_tools(ctx), write_recipe_tool(ctx)]
