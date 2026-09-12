import json

import pytest
import pytest_asyncio

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.services.ai_recipes import AiUnavailable
from app.services.recipe_import.terms import propose_decisions


class FakeClaude:
    """Sostituisce il client Anthropic: la suite non fa rete."""

    def __init__(self, payload: object) -> None:
        self._payload = payload
        self.messages = self

    async def create(self, **kwargs):
        self.last_kwargs = kwargs
        if isinstance(self._payload, Exception):
            raise self._payload

        class Block:
            text = self._payload if isinstance(self._payload, str) else json.dumps(self._payload)

        class Response:
            content = [Block()]

        return Response()


@pytest_asyncio.fixture
async def termini(db_session):
    db_session.add(
        Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
    )
    rigatoni = ImportTerm(
        source=GIALLOZAFFERANO, term_key="ricette-con-i-Rigatoni", display_name="Rigatoni",
        occurrences=12, decision=TermDecision.PENDING,
    )
    speck = ImportTerm(
        source=GIALLOZAFFERANO, term_key="ricette-con-lo-Speck", display_name="Speck",
        occurrences=4, decision=TermDecision.PENDING,
    )
    acqua = ImportTerm(
        source=GIALLOZAFFERANO, term_key="ricette-con-Acqua", display_name="Acqua",
        occurrences=7, decision=TermDecision.PENDING,
    )
    db_session.add_all([rigatoni, speck, acqua])
    await db_session.flush()
    return [rigatoni, speck, acqua]


async def test_le_tre_azioni_arrivano_tradotte(db_session, termini):
    risposta = {
        "proposals": [
            {"term": "Rigatoni", "action": "map", "ingredient": "pasta"},
            {"term": "Speck", "action": "create", "name": "speck",
             "display_name": "Speck", "category": "carne"},
            {"term": "Acqua", "action": "ignore"},
        ]
    }

    proposte = await propose_decisions(db_session, termini, client=FakeClaude(risposta))

    per_termine = {p.term_id: p for p in proposte}
    assert per_termine[termini[0].id].action == "map"
    assert per_termine[termini[0].id].ingredient_id is not None
    assert per_termine[termini[1].id].action == "create"
    assert per_termine[termini[1].id].category == "carne"
    assert per_termine[termini[2].id].action == "ignore"


async def test_un_ingrediente_che_non_esiste_non_e_una_proposta(db_session, termini):
    """Una proposta non verificabile è rumore: si scarta, non si mostra."""
    risposta = {
        "proposals": [{"term": "Rigatoni", "action": "map", "ingredient": "bucatini"}]
    }

    proposte = await propose_decisions(db_session, termini, client=FakeClaude(risposta))

    assert proposte == []


async def test_una_categoria_inventata_non_e_una_proposta(db_session, termini):
    risposta = {
        "proposals": [{"term": "Speck", "action": "create", "name": "speck",
                       "display_name": "Speck", "category": "salumeria"}]
    }

    proposte = await propose_decisions(db_session, termini, client=FakeClaude(risposta))

    assert proposte == []


async def test_un_termine_che_non_avevo_chiesto_si_scarta(db_session, termini):
    risposta = {"proposals": [{"term": "Zafferano", "action": "ignore"}]}

    proposte = await propose_decisions(db_session, termini, client=FakeClaude(risposta))

    assert proposte == []


async def test_una_risposta_che_non_e_json_si_dichiara(db_session, termini):
    with pytest.raises(AiUnavailable):
        await propose_decisions(db_session, termini, client=FakeClaude("mi dispiace, ecco:"))


async def test_senza_chiave_configurata_si_dichiara(db_session, termini, monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    try:
        with pytest.raises(AiUnavailable):
            await propose_decisions(db_session, termini)
    finally:
        get_settings.cache_clear()


async def test_si_chiedono_al_massimo_quaranta_termini_per_chiamata(db_session, termini):
    """Il prompt porta l'anagrafica intera: un lotto senza tetto la farebbe crescere
    fino a una chiamata che costa e che il modello tronca."""
    from app.services.recipe_import.terms import MAX_TERMS_PER_CALL

    finto = FakeClaude({"proposals": []})
    await propose_decisions(db_session, termini * 30, client=finto)

    inviati = finto.last_kwargs["messages"][0]["content"]
    assert inviati.count("Rigatoni") <= MAX_TERMS_PER_CALL


async def test_l_anagrafica_arriva_nel_prompt(db_session, termini):
    """Senza l'elenco dei nostri ingredienti il modello propone nomi che non esistono,
    e ogni proposta verrebbe scartata dalla verifica."""
    finto = FakeClaude({"proposals": []})
    await propose_decisions(db_session, termini, client=finto)

    assert "pasta" in finto.last_kwargs["system"] or "pasta" in str(
        finto.last_kwargs["messages"]
    )
