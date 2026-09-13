import json
import uuid

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
    # il nome canonico deve arrivare con la proposta: senza di esso il pulsante non
    # può dire a cosa collega, e chiede di confermare qualcosa che non si vede
    assert per_termine[termini[0].id].name == "pasta"
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


async def test_una_voce_non_a_dizionario_si_scarta(db_session, termini):
    """Una voce che non è nemmeno un oggetto non si può verificare: si scarta, e non
    deve costare le proposte buone dello stesso lotto."""
    risposta = {
        "proposals": [
            "Rigatoni",
            {"term": "Speck", "action": "ignore"},
        ]
    }

    proposte = await propose_decisions(db_session, termini, client=FakeClaude(risposta))

    per_termine = {p.term_id: p for p in proposte}
    assert termini[0].id not in per_termine
    assert per_termine[termini[1].id].action == "ignore"


async def test_un_azione_non_riconosciuta_si_scarta(db_session, termini):
    """Un'azione fuori dalle tre previste non produce niente per quel termine, ma
    non deve bloccare le proposte buone dello stesso lotto."""
    risposta = {
        "proposals": [
            {"term": "Rigatoni", "action": "boh"},
            {"term": "Speck", "action": "ignore"},
        ]
    }

    proposte = await propose_decisions(db_session, termini, client=FakeClaude(risposta))

    per_termine = {p.term_id: p for p in proposte}
    assert termini[0].id not in per_termine
    assert per_termine[termini[1].id].action == "ignore"


async def test_un_nome_vuoto_in_create_non_e_una_proposta(db_session, termini):
    """Un nome vuoto non è un nome canonico: la create si scarta, ma le altre
    proposte dello stesso lotto restano."""
    risposta = {
        "proposals": [
            {"term": "Speck", "action": "create", "name": "", "display_name": "Speck",
             "category": "carne"},
            {"term": "Acqua", "action": "ignore"},
        ]
    }

    proposte = await propose_decisions(db_session, termini, client=FakeClaude(risposta))

    per_termine = {p.term_id: p for p in proposte}
    assert termini[1].id not in per_termine
    assert per_termine[termini[2].id].action == "ignore"


async def test_una_create_su_un_nome_gia_in_anagrafica_diventa_un_map(db_session, termini):
    """Claude che risponde "create" con un nome che l'anagrafica ha già (il caso di
    "Rigatoni" -> "pasta" proposto come create invece di map) non deve produrre una
    proposta non verificata: l'ingrediente esiste, quindi la proposta verificata è il
    map che Claude avrebbe dovuto scegliere, con l'id e il nome canonico già noti."""
    risposta = {
        "proposals": [
            {"term": "Rigatoni", "action": "create", "name": "pasta",
             "display_name": "Pasta", "category": "cereali"},
        ]
    }

    proposte = await propose_decisions(db_session, termini, client=FakeClaude(risposta))

    per_termine = {p.term_id: p for p in proposte}
    assert per_termine[termini[0].id].action == "map"
    assert per_termine[termini[0].id].ingredient_id is not None
    assert per_termine[termini[0].id].name == "pasta"


async def test_una_risposta_che_non_e_json_si_dichiara(db_session, termini):
    with pytest.raises(AiUnavailable):
        await propose_decisions(db_session, termini, client=FakeClaude("mi dispiace, ecco:"))


async def test_un_json_valido_senza_proposals_si_dichiara(db_session, termini):
    """Un JSON ben formato ma senza 'proposals' è altrettanto inverificabile di un
    JSON rotto: si dichiara, non si interpreta alla meglio."""
    with pytest.raises(AiUnavailable):
        await propose_decisions(db_session, termini, client=FakeClaude({"termini": []}))


async def test_un_proposals_che_non_e_una_lista_si_dichiara(db_session, termini):
    """Anche quando 'proposals' c'è ma non è una lista, la forma è sbagliata allo
    stesso modo: si dichiara, non si interpreta alla meglio."""
    with pytest.raises(AiUnavailable):
        await propose_decisions(
            db_session, termini, client=FakeClaude({"proposals": "non è una lista"})
        )


async def test_senza_chiave_configurata_si_dichiara(db_session, termini, monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    try:
        with pytest.raises(AiUnavailable):
            await propose_decisions(db_session, termini)
    finally:
        get_settings.cache_clear()


async def test_si_chiedono_al_massimo_quaranta_termini_per_chiamata(db_session):
    """Il prompt porta l'anagrafica intera: un lotto senza tetto la farebbe crescere
    fino a una chiamata che costa e che il modello tronca.

    Il tetto va misurato sul numero di termini effettivamente inviati, non su
    quante volte ricorre un nome: con nomi tutti diversi un lotto senza tetto (90)
    supera chiaramente il tetto (40), mentre un lotto tagliato non lo supera mai —
    l'asserzione distingue davvero i due casi.
    """
    from app.services.recipe_import.terms import MAX_TERMS_PER_CALL

    lotto = [
        ImportTerm(
            id=uuid.uuid4(), source=GIALLOZAFFERANO, term_key=f"ricetta-{i}",
            display_name=f"Ingrediente{i}", occurrences=1, decision=TermDecision.PENDING,
        )
        for i in range(90)
    ]

    finto = FakeClaude({"proposals": []})
    await propose_decisions(db_session, lotto, client=finto)

    inviati = json.loads(finto.last_kwargs["messages"][0]["content"])["termini"]
    assert len(inviati) <= MAX_TERMS_PER_CALL


async def test_l_anagrafica_arriva_nel_prompt(db_session, termini):
    """Senza l'elenco dei nostri ingredienti il modello propone nomi che non esistono,
    e ogni proposta verrebbe scartata dalla verifica."""
    finto = FakeClaude({"proposals": []})
    await propose_decisions(db_session, termini, client=finto)

    assert "pasta" in finto.last_kwargs["system"] or "pasta" in str(
        finto.last_kwargs["messages"]
    )
