"""Le figure degli ingredienti decise dall'AI (S12), e la verifica della sua risposta.

Come per le unità e i termini dell'import, la parte che conta è la verifica: una
risposta che non si può controllare non si applica, e l'ingrediente resta senza figura
— cioè col ripiego del reparto, che è meno bello e non è sbagliato.

Il finto sostituisce `httpx.AsyncClient`, non il client di OpenRouter: sotto prova c'è
`complete_json` per intero, header e corpo compresi.
"""

import json

import httpx
import pytest
from sqlalchemy import select, update

from app.db.models.ingredient import Ingredient
from app.db.models.llm_call import LlmCall
from app.domain.emoji import INGREDIENT_EMOJI, NO_EMOJI
from app.services.ingredient_emoji import EmojiRun, decide_ingredient_emoji
from llm_fakes import FakeLlm


@pytest.fixture(autouse=True)
def chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


async def _voci(db_session, *voci: tuple[str, str, str | None]) -> dict[str, Ingredient]:
    """(nome, reparto, emoji) → l'ingrediente, già nel database."""
    creati = {
        nome: Ingredient(name=nome, display_name=nome.capitalize(), category=reparto, emoji=emoji)
        for nome, reparto, emoji in voci
    }
    db_session.add_all(creati.values())
    await db_session.flush()
    return creati


async def _figura(db_session, ingrediente: Ingredient) -> str | None:
    """Dal database, non dall'oggetto in memoria."""
    return (
        await db_session.execute(select(Ingredient.emoji).where(Ingredient.id == ingrediente.id))
    ).scalar_one()


def _risposta(*righe: tuple[int, str, str]) -> dict:
    return {"emoji": [{"n": n, "nome": nome, "emoji": emoji} for n, nome, emoji in righe]}


def _domanda(corpo: dict) -> list[dict]:
    return json.loads(corpo["messages"][1]["content"])["ingredienti"]


async def test_applica_le_figure_dell_elenco(db_session):
    voci = await _voci(db_session, ("carota", "verdura", None), ("mozzarella", "latticini", None))
    finto = FakeLlm(_risposta((1, "carota", "🥕"), (2, "mozzarella", "🧀")))

    esito = await decide_ingredient_emoji(db_session, client=finto)

    assert esito == EmojiRun(applied=2, none=0, refused=0, pending=0, unavailable=None)
    assert await _figura(db_session, voci["carota"]) == "🥕"
    assert await _figura(db_session, voci["mozzarella"]) == "🧀"


async def test_nessuna_si_scrive_e_non_si_richiede(db_session):
    """«nessuna» è una risposta dell'elenco, non un rifiuto: l'ingrediente è deciso, e
    il lancio dopo non lo chiede di nuovo (decisione 22 del piano)."""
    voci = await _voci(db_session, ("sedano", "verdura", None))
    finto = FakeLlm(_risposta((1, "sedano", "nessuna")))

    esito = await decide_ingredient_emoji(db_session, client=finto)

    assert (esito.none, esito.applied, esito.pending) == (1, 0, 0)
    assert await _figura(db_session, voci["sedano"]) == NO_EMOJI


async def test_una_figura_fuori_elenco_non_si_applica(db_session):
    """Lo zenzero di Emoji 15.0 è la prima figura che un modello proporrebbe, ed è
    proprio quella che un telefono vecchio mostra come un quadratino vuoto."""
    voci = await _voci(db_session, ("zenzero", "spezie", None))
    finto = FakeLlm(_risposta((1, "zenzero", "\U0001FADA")))

    esito = await decide_ingredient_emoji(db_session, client=finto)

    assert (esito.refused, esito.applied, esito.pending) == (1, 0, 1)
    assert await _figura(db_session, voci["zenzero"]) is None


async def test_un_numero_non_chiesto_un_nome_che_non_torna_e_un_doppione_non_si_applicano(
    db_session,
):
    """In un lotto di cento un modello piccolo sbaglia riga: il nome accanto al numero
    è quel che lo fa vedere. E di due risposte per lo stesso numero vale la prima."""
    voci = await _voci(db_session, ("carota", "verdura", None), ("sedano", "verdura", None))
    finto = FakeLlm(_risposta(
        (7, "carota", "🥕"),       # 7 non è stato chiesto
        (2, "carota", "🥕"),       # il 2 è il sedano
        (1, "Carota ", "🥕"),      # giusto: maiuscole e spazi ai lati non contano
        (1, "carota", "🥦"),       # doppione del primo
    ))

    esito = await decide_ingredient_emoji(db_session, client=finto)

    assert (esito.applied, esito.refused, esito.pending) == (1, 3, 1)
    assert await _figura(db_session, voci["carota"]) == "🥕"
    assert await _figura(db_session, voci["sedano"]) is None


async def test_una_risposta_che_non_e_un_oggetto_si_conta_rifiutata_e_il_giro_prosegue(
    db_session,
):
    """Un elemento che è una stringa o un numero non ha `.get`: prima faceva cadere il
    comando con un `AttributeError`, e la chiamata già pagata non finiva in `llm_calls`."""
    voci = await _voci(db_session, ("carota", "verdura", None), ("sedano", "verdura", None))
    finto = FakeLlm({"emoji": [
        "carota",                                       # una stringa al posto dell'oggetto
        7,                                              # un numero
        {"n": 1, "nome": "carota", "emoji": "🥕"},      # questa è valida
    ]})

    esito = await decide_ingredient_emoji(db_session, client=finto)

    assert (esito.applied, esito.refused, esito.pending) == (1, 2, 1)
    assert esito.unavailable is None
    assert await _figura(db_session, voci["carota"]) == "🥕"
    assert await _figura(db_session, voci["sedano"]) is None
    chiamate = (await db_session.execute(select(LlmCall.ok))).scalars().all()
    assert chiamate == [True]


async def test_senza_selettore_di_variante_si_scrive_la_forma_dell_elenco(db_session):
    voci = await _voci(db_session, ("peperoncino", "spezie", None))
    finto = FakeLlm(_risposta((1, "peperoncino", "\U0001F336")))

    await decide_ingredient_emoji(db_session, client=finto)

    assert await _figura(db_session, voci["peperoncino"]) == "\U0001F336️"


async def test_chi_ha_gia_una_figura_o_nessuna_non_si_chiede(db_session):
    """L'AI scrive solo dove la colonna è vuota: una figura scelta a mano, «Nessuna»
    compresa, non torna al modello. E se non c'è niente da chiedere, non si chiama."""
    voci = await _voci(
        db_session,
        ("carota", "verdura", None),
        ("melanzana", "verdura", "🍆"),
        ("sedano", "verdura", NO_EMOJI),
    )
    finto = FakeLlm(_risposta((1, "carota", "🥕")))

    await decide_ingredient_emoji(db_session, client=finto)

    assert [voce["nome"] for voce in _domanda(finto.bodies[0])] == ["carota"]
    assert await _figura(db_session, voci["melanzana"]) == "🍆"
    assert await _figura(db_session, voci["sedano"]) == NO_EMOJI

    di_nuovo = FakeLlm()
    esito = await decide_ingredient_emoji(db_session, client=di_nuovo)
    assert di_nuovo.bodies == []
    assert esito == EmojiRun()


class _LlmMentreUnaManoCorregge(FakeLlm):
    """Prima di rispondere, qualcuno sceglie una figura in Anagrafica."""

    def __init__(self, mano, *payloads: object) -> None:
        super().__init__(*payloads)
        self._mano = mano

    async def post(self, url, json, headers):  # noqa: A002
        await self._mano()
        return await super().post(url, json, headers)


async def test_una_scelta_a_mano_fatta_mentre_l_ai_risponde_non_si_riscrive(db_session):
    """Il comando può girare minuti; la scelta fatta nel frattempo vince, perché la
    UPDATE che scrive controlla che la colonna sia ancora vuota."""
    voci = await _voci(db_session, ("carota", "verdura", None))

    async def mano():
        await db_session.execute(
            update(Ingredient).where(Ingredient.id == voci["carota"].id).values(emoji="🥦")
        )

    finto = _LlmMentreUnaManoCorregge(mano, _risposta((1, "carota", "🥕")))

    esito = await decide_ingredient_emoji(db_session, client=finto)

    assert esito.applied == 0
    assert await _figura(db_session, voci["carota"]) == "🥦"


async def test_va_a_lotti_e_dopo_ogni_lotto_chiama_after_batch(db_session):
    """Il comando fa commit dopo ogni lotto: un guasto al quinto non butta i primi
    quattro. Ogni lotto numera da 1."""
    await _voci(
        db_session,
        ("aglio", "verdura", None), ("banana", "frutta", None), ("carota", "verdura", None),
    )
    finto = FakeLlm(
        _risposta((1, "aglio", "🧄"), (2, "banana", "🍌")),
        _risposta((1, "carota", "🥕")),
    )
    giri: list[int] = []

    async def dopo():
        giri.append(len(finto.bodies))

    esito = await decide_ingredient_emoji(db_session, client=finto, batch_size=2, after_batch=dopo)

    assert (esito.applied, esito.pending) == (3, 0)
    assert giri == [1, 2]
    assert [[(v["n"], v["nome"]) for v in _domanda(corpo)] for corpo in finto.bodies] == [
        [(1, "aglio"), (2, "banana")],
        [(1, "carota")],
    ]


async def test_l_ai_che_non_risponde_non_scrive_niente_e_lo_dice(db_session):
    voci = await _voci(db_session, ("carota", "verdura", None))
    finto = FakeLlm(httpx.ConnectError("rete giù"))

    esito = await decide_ingredient_emoji(db_session, client=finto)

    assert (esito.applied, esito.pending) == (0, 1)
    assert esito.unavailable is not None and "rete giù" in esito.unavailable
    assert await _figura(db_session, voci["carota"]) is None


async def test_il_primo_guasto_ferma_il_giro(db_session):
    """Dopo un guasto i lotti dopo non si chiedono: sarebbe pagare per sapere che è
    ancora giù. Quel che è già scritto resta."""
    voci = await _voci(
        db_session,
        ("aglio", "verdura", None), ("banana", "frutta", None), ("carota", "verdura", None),
    )
    finto = FakeLlm(_risposta((1, "aglio", "🧄")), httpx.ConnectError("rete giù"))

    esito = await decide_ingredient_emoji(db_session, client=finto, batch_size=1)

    assert len(finto.bodies) == 2
    assert (esito.applied, esito.pending) == (1, 2)
    assert esito.unavailable is not None
    assert await _figura(db_session, voci["aglio"]) == "🧄"


async def test_ogni_chiamata_registra_la_spesa(db_session):
    """Anche quella fallita, come le altre sezioni: una chiamata che non entra in
    `llm_calls` non compare mai nel conto."""
    await _voci(db_session, ("aglio", "verdura", None), ("banana", "frutta", None))
    finto = FakeLlm(_risposta((1, "aglio", "🧄")), httpx.ConnectError("rete giù"))

    await decide_ingredient_emoji(db_session, client=finto, batch_size=1)

    righe = (
        await db_session.execute(select(LlmCall).where(LlmCall.call_site == "ingredient_emoji"))
    ).scalars().all()
    assert sorted(riga.ok for riga in righe) == [False, True]


async def test_la_domanda_porta_numero_nome_e_reparto_e_l_elenco_chiuso(db_session):
    await _voci(db_session, ("carota", "verdura", None))
    finto = FakeLlm(_risposta((1, "carota", "🥕")))

    await decide_ingredient_emoji(db_session, client=finto)

    corpo = finto.bodies[0]
    assert _domanda(corpo) == [{"n": 1, "nome": "carota", "reparto": "verdura"}]
    assert "🥕" in corpo["messages"][0]["content"]
    assert "nessuna" in corpo["messages"][0]["content"]
    schema = corpo["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["emoji"]["items"]["properties"]["emoji"]["enum"] == [
        *INGREDIENT_EMOJI, "nessuna",
    ]
