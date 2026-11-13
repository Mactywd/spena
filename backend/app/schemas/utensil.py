"""Gli utensili di cucina, come li vede l'API (spec 2026-11-12 §4.4)."""

import uuid

from pydantic import BaseModel, ConfigDict, field_validator

from app.db.models.utensil import UTENSIL_NAME_MAX, UTENSIL_NOTE_MAX


def _one_line(value: str) -> str:
    # un testo incollato non deve portare righe nuove nel prompt dell'AI (decisione 6)
    return " ".join(value.split())


def _clean_name(value: str | None) -> str:
    if value is None:
        raise ValueError("il nome non può mancare")
    cleaned = _one_line(value)
    if not cleaned:
        raise ValueError("il nome non può essere vuoto")
    if len(cleaned) > UTENSIL_NAME_MAX:
        raise ValueError(f"il nome supera {UTENSIL_NAME_MAX} caratteri")
    return cleaned


def _clean_note(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = _one_line(value)
    if len(cleaned) > UTENSIL_NOTE_MAX:
        raise ValueError(f"la nota supera {UTENSIL_NOTE_MAX} caratteri")
    return cleaned or None


class UtensilIn(BaseModel):
    name: str
    note: str | None = None

    _name = field_validator("name", mode="after")(_clean_name)
    _note = field_validator("note", mode="after")(_clean_note)


class UtensilPatch(BaseModel):
    # presenza dei campi: la rotta guarda `model_fields_set`
    name: str | None = None
    note: str | None = None

    # i validatori girano solo sui campi passati; il tipo str lo controlla pydantic prima (123 -> 422)
    _name = field_validator("name", mode="after")(_clean_name)
    _note = field_validator("note", mode="after")(_clean_note)


class UtensilOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    note: str | None
