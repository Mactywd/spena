"""L'AI pesa le coppie ingrediente × unità (S4, fetta 2), e la verifica delle sue risposte.

Come per le altre decisioni dell'AI, una risposta che non si può controllare non si
applica: un numero non chiesto o già risposto, un ingrediente o un'unità che non tornano,
un peso fuori misura. «nessun peso» (`null`) si scrive, e non si richiede (deciso da
Mattia il 2026-10-13).
"""

import json
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import select

from app.db.models.ingredient import Ingredient
from app.db.models.llm_call import LlmCall
from app.db.models.nutrition import IngredientUnitGrams
from app.db.models.recipe import RecipeSource
from app.repositories.recipes import create_recipe
from app.services.unit_grams import GramsRun, decide_grams, set_grams
from llm_fakes import FakeLlm, schema_of, system_of, user_of


@pytest.fixture(autouse=True)
def chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


async def _mondo(db_session) -> dict[str, Ingredient]:
    voci = {
        nome: Ingredient(name=nome, display_name=nome.capitalize(), category=reparto)
        for nome, reparto in [("aglio", "verdura"), ("olio di oliva", "condimenti"), ("uova", "altro")]
    }
    db_session.add_all(voci.values())
    await db_session.flush()
    await create_recipe(
        db_session, title="Prova", description=None, instructions="Si cucina.", servings=2,
        source=RecipeSource.MANUAL, source_ref=None, embedding=None,
        ingredients=[
            (voci["aglio"].id, "secondary", "1 spicchio", None),
            (voci["olio di oliva"].id, "secondary", "2 cucchiai", None),
            (voci["uova"].id, "primary", "2", None),
        ],
    )
    return voci


def _pesi(*righe):
    return {
        "pesi": [
            {"n": n, "ingrediente": ingrediente, "unita": unita, "grammi": grammi}
            for n, ingrediente, unita, grammi in righe
        ]
    }


async def _scritti(db_session):
    return sorted(
        (riga.grams, riga.decided_by)
        for riga in (await db_session.execute(select(IngredientUnitGrams))).scalars()
    )


async def test_pesa_e_scrive(db_session):
    await _mondo(db_session)
    finto = FakeLlm(_pesi((1, "aglio", "spicchio", 5), (2, "olio di oliva", "cucchiai", 12.5), (3, "uova", "pezzo", 50)))

    esito = await decide_grams(db_session, client=finto)

    assert esito == GramsRun(weighed=3, none=0, refused=0, pending=0, unavailable=None, asked=3)
    assert await _scritti(db_session) == [
        (Decimal("5.00"), "ai"), (Decimal("12.50"), "ai"), (Decimal("50.00"), "ai"),
    ]


async def test_la_domanda_porta_numero_ingrediente_unita_ed_esempio(db_session):
    await _mondo(db_session)
    finto = FakeLlm(_pesi((1, "aglio", "spicchio", 5)))

    await decide_grams(db_session, client=finto, limit=1)

    corpo = finto.bodies[0]
    assert json.loads(user_of(corpo)) == {
        "coppie": [{"n": 1, "ingrediente": "aglio", "unita": "spicchio", "esempio": "1 spicchio"}]
    }
    assert "parte che si mangia" in system_of(corpo)
    schema = schema_of(corpo)
    assert schema["properties"]["pesi"]["items"]["properties"]["grammi"] == {
        "anyOf": [{"type": "number"}, {"type": "null"}]
    }


async def test_nessun_peso_si_scrive_e_non_si_richiede(db_session):
    await _mondo(db_session)
    finto = FakeLlm(_pesi((1, "aglio", "spicchio", None), (2, "olio di oliva", "cucchiai", None), (3, "uova", "pezzo", None)))

    esito = await decide_grams(db_session, client=finto)

    assert (esito.none, esito.weighed, esito.pending) == (3, 0, 0)
    assert await _scritti(db_session) == [(None, "ai")] * 3


async def test_un_peso_fuori_misura_non_si_applica(db_session):
    await _mondo(db_session)
    finto = FakeLlm(_pesi((1, "aglio", "spicchio", 0), (2, "olio di oliva", "cucchiai", 6000), (3, "uova", "pezzo", "50")))

    esito = await decide_grams(db_session, client=finto)

    assert (esito.refused, esito.weighed, esito.pending) == (3, 0, 3)
    assert await _scritti(db_session) == []


async def test_un_peso_enorme_si_rifiuta_senza_fermare_il_giro(db_session):
    await _mondo(db_session)
    finto = FakeLlm(
        '{"pesi": [{"n": 1, "ingrediente": "aglio", "unita": "spicchio", "grammi": 1e30},'
        ' {"n": 2, "ingrediente": "olio di oliva", "unita": "cucchiai", "grammi": 1'
        + "0" * 400
        + "},"
        ' {"n": 3, "ingrediente": "uova", "unita": "pezzo", "grammi": 50}]}'
    )

    esito = await decide_grams(db_session, client=finto)

    assert (esito.refused, esito.weighed, esito.pending) == (2, 1, 2)
    assert await _scritti(db_session) == [(Decimal("50.00"), "ai")]


async def test_un_numero_un_ingrediente_o_un_unita_che_non_tornano_non_si_applicano(db_session):
    await _mondo(db_session)
    finto = FakeLlm(
        _pesi(
            (7, "aglio", "spicchio", 5),  # 7 non è stato chiesto
            (1, "aglio", "spicchi", 5),  # l'unità chiesta è «spicchio»
            (1, "Aglio ", "spicchio", 5),  # giusto: maiuscole e spazi ai lati non contano
            (1, "aglio", "spicchio", 6),  # doppione
        )
    )

    esito = await decide_grams(db_session, client=finto)

    assert (esito.weighed, esito.refused, esito.pending) == (1, 3, 2)


class _LlmMentreUnaManoCorregge(FakeLlm):
    def __init__(self, mano, *payloads: object) -> None:
        super().__init__(*payloads)
        self._mano = mano

    async def answer(self, body: dict) -> object:
        await self._mano()
        return await super().answer(body)


async def test_un_peso_a_mano_scritto_mentre_l_ai_risponde_non_si_riscrive(db_session):
    voci = await _mondo(db_session)

    async def mano():
        await set_grams(db_session, voci["uova"].id, None, Decimal("55"))

    finto = _LlmMentreUnaManoCorregge(mano, _pesi((1, "aglio", "spicchio", 5), (2, "olio di oliva", "cucchiai", 12), (3, "uova", "pezzo", 50)))

    esito = await decide_grams(db_session, client=finto)

    assert esito.weighed == 2
    assert (Decimal("55.00"), "human") in await _scritti(db_session)


async def test_va_a_lotti_e_dopo_ogni_lotto_chiama_after_batch(db_session):
    await _mondo(db_session)
    finto = FakeLlm(
        _pesi((1, "aglio", "spicchio", 5), (2, "olio di oliva", "cucchiai", 12)),
        _pesi((1, "uova", "pezzo", 50)),
    )
    giri: list[int] = []

    async def dopo():
        giri.append(len(finto.bodies))

    esito = await decide_grams(db_session, client=finto, batch_size=2, after_batch=dopo)

    assert giri == [1, 2]
    assert (esito.weighed, esito.pending) == (3, 0)


async def test_l_ai_che_non_risponde_non_scrive_niente_e_si_registra(db_session):
    await _mondo(db_session)

    esito = await decide_grams(db_session, client=FakeLlm(httpx.ConnectError("rete giù")))

    assert (esito.weighed, esito.pending, esito.asked) == (0, 3, 3)
    assert esito.unavailable is not None and "rete giù" in esito.unavailable
    righe = (await db_session.execute(select(LlmCall.call_site, LlmCall.ok))).all()
    assert [tuple(riga) for riga in righe] == [("unit_grams", False)]


async def test_limit_chiede_solo_le_prime_coppie(db_session):
    await _mondo(db_session)
    finto = FakeLlm(_pesi((1, "aglio", "spicchio", 5)))

    esito = await decide_grams(db_session, client=finto, limit=1)

    assert (esito.asked, esito.weighed, esito.pending) == (1, 1, 2)
