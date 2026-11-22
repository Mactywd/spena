"""Perché una pagina è scartata, letto da quel che la pagina conserva (spec
docs/superpowers/specs/2026-10-09-scartate-in-coda-design.md §3.1).

Gli ultimi due test passano per la materializzazione vera: il motivo che
`explain_skip` rilegge deve essere quello che `materialize_ready` scrive, non una sua
copia scritta nel test (prima lezione di CLAUDE.md).
"""

import pytest

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportState, ImportTerm, TermDecision
from app.repositories.imports import store_page
from app.repositories.ingredients import create_ingredient
from app.services.recipe_import.materialize import (
    EMPTY_REASON,
    NON_FOOD_PREFIX,
    SkipCause,
    explain_skip,
    materialize_ready,
)

RIGHE = {"title": "Torta", "ingredients": [{"key": "k-farina", "name": "Farina 00"}]}


@pytest.mark.parametrize(
    ("payload", "reason"),
    [
        ({}, "nessuna riga dd.gz-ingredient nella pagina"),
        ({}, "la fonte ha risposto 404"),
        ({"title": "Torta", "ingredients": []}, None),
    ],
)
def test_una_pagina_senza_righe_e_illeggibile_e_non_si_rimette(payload, reason):
    """Senza righe non c'è niente da materializzare, e l'indirizzo non si riscarica:
    rimessa in coda tornerebbe scartata, e col motivo sbagliato («ogni ingrediente è
    stato ignorato»)."""
    spiegato = explain_skip(payload, reason)
    assert spiegato.cause == SkipCause.UNREADABLE
    assert spiegato.requeueable is False
    assert spiegato.non_food_name is None


def test_le_righe_tutte_ignorate():
    spiegato = explain_skip(RIGHE, EMPTY_REASON[:200])
    assert (spiegato.cause, spiegato.non_food_name, spiegato.requeueable) == (
        SkipCause.ALL_IGNORED, None, True,
    )


def test_una_riga_non_alimentare_porta_il_nome_della_voce():
    spiegato = explain_skip(RIGHE, f"{NON_FOOD_PREFIX}«Carta forno»")
    assert (spiegato.cause, spiegato.non_food_name, spiegato.requeueable) == (
        SkipCause.NON_FOOD, "Carta forno", True,
    )


def test_un_nome_tagliato_dal_limite_della_colonna_resta_quel_che_ce():
    """`skipped_reason` è String(200): un nome lunghissimo perde la chiusa »."""
    motivo = f"{NON_FOOD_PREFIX}«{'x' * 300}»"[:200]
    spiegato = explain_skip(RIGHE, motivo)
    assert spiegato.cause == SkipCause.NON_FOOD
    assert spiegato.non_food_name == "x" * (200 - len(NON_FOOD_PREFIX) - 1)


def test_un_motivo_sconosciuto_con_le_righe_si_rimette():
    spiegato = explain_skip(RIGHE, "un motivo scritto da una versione di prima")
    assert (spiegato.cause, spiegato.non_food_name, spiegato.requeueable) == (
        SkipCause.OTHER, None, True,
    )


async def test_il_motivo_non_alimentare_scritto_da_materialize_si_rilegge(db_session):
    panna = await create_ingredient(
        db_session, name="panna", display_name="Panna", category=IngredientCategory.CASA
    )
    db_session.add(ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-panna", display_name="Panna fresca",
        occurrences=1, decision=TermDecision.MAPPED, ingredient_id=panna.id,
        decided_by="human", created_ingredient=False,
    ))
    await db_session.flush()
    pagina = await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/torta",
        payload={"title": "Torta", "ingredients": [{"key": "k-panna", "name": "Panna fresca"}]},
    )

    await materialize_ready(db_session, GIALLOZAFFERANO)

    assert pagina.state == ImportState.SKIPPED
    spiegato = explain_skip(pagina.payload, pagina.skipped_reason)
    assert (spiegato.cause, spiegato.non_food_name) == (SkipCause.NON_FOOD, "Panna")


async def test_il_motivo_delle_righe_ignorate_scritto_da_materialize_si_rilegge(db_session):
    db_session.add(ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-acqua", display_name="Acqua",
        occurrences=1, decision=TermDecision.IGNORED, decided_by="human",
    ))
    await db_session.flush()
    pagina = await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio.invalid/acqua",
        payload={"title": "Acqua calda", "ingredients": [{"key": "k-acqua", "name": "Acqua"}]},
    )

    await materialize_ready(db_session, GIALLOZAFFERANO)

    assert pagina.state == ImportState.SKIPPED
    assert explain_skip(pagina.payload, pagina.skipped_reason).cause == SkipCause.ALL_IGNORED
