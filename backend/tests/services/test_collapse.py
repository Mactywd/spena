"""Il collasso dei nomi vicini, che è il buco che il parallelo apre.

Il fan-in prende i duplicati identici («speck» due volte). Non vede i vicini:
«salmone» e «salmone selvaggio» sono due `create` diversi, e nessuna delle chiamate
parallele poteva vedere l'altra. Questa passata li unisce, e il nome scartato diventa
un alias del canonico — che è ciò che la rende un investimento e non una pulizia: la
prossima volta il filtro deterministico lo riconosce senza chiamare nessuno.
"""

import uuid

import pytest
import pytest_asyncio

from app.db.models.ingredient import IngredientCategory
from app.repositories.ingredients import create_ingredient
from app.services.recipe_import.decide import (
    TermDecisionProposal,
    collapse_creates,
    load_registry,
)
from llm_fakes import FakeLlm


@pytest.fixture(autouse=True)
def chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def anagrafica(db_session):
    await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    return await load_registry(db_session)


def crea(nome: str, categoria: str = "pesce", display_name: str | None = None) -> TermDecisionProposal:
    return TermDecisionProposal(
        term_id=uuid.uuid4(), action="create", name=nome,
        display_name=display_name if display_name is not None else nome.capitalize(),
        category=categoria,
    )


async def test_due_nomi_vicini_diventano_uno_e_laltro_un_alias(db_session, anagrafica):
    salmone, selvaggio = crea("salmone"), crea("salmone selvaggio")
    finto = FakeLlm({"groups": [{"canonical": "salmone", "merge": ["salmone selvaggio"]}]})

    risultato, _ = await collapse_creates(
        db_session, [salmone, selvaggio], anagrafica, client=finto
    )

    creazioni = [p for p in risultato if p.action == "create"]
    assert [p.name for p in creazioni] == ["salmone"]
    # il secondo non spariste: resta una proposta, e chiede di essere agganciato al
    # canonico. L'alias lo scrive il fan-in, non questa passata: qui non si scrive.
    accorpati = [p for p in risultato if p.action == "merge"]
    assert len(accorpati) == 1
    assert accorpati[0].term_id == selvaggio.term_id
    assert accorpati[0].name == "salmone"


async def test_il_merge_porta_etichetta_e_categoria_del_vincitore_non_del_perdente(
    db_session, anagrafica
):
    """Nessun test qui sopra distingue l'etichetta del vincitore da quella del
    perdente: condividevano `category="pesce"` e nessuno guardava `display_name`.
    Scambiare vincitore e perdente nel codice di produzione passava comunque tutti
    e sette i test. Qui vincitore e perdente hanno nome ed etichetta diversi apposta,
    così un errore nella direzione della copia si vede.
    """
    salmone = crea("salmone", categoria="pesce", display_name="Salmone")
    selvaggio = crea(
        "salmone selvaggio", categoria="pesce fresco", display_name="Salmone selvaggio"
    )
    finto = FakeLlm({"groups": [{"canonical": "salmone", "merge": ["salmone selvaggio"]}]})

    risultato, _ = await collapse_creates(
        db_session, [salmone, selvaggio], anagrafica, client=finto
    )

    accorpato = next(p for p in risultato if p.action == "merge")
    assert accorpato.display_name == "Salmone"
    assert accorpato.category == "pesce"


async def test_il_merge_su_canonico_gia_in_anagrafica_usa_il_nome_capitalizzato(
    db_session, anagrafica
):
    """Quando il canonico è già in anagrafica non ha una proposta propria nel lotto:
    l'etichetta ricade sul nome canonico capitalizzato, mai su quella del perdente.
    """
    fresca = crea("pasta fresca", categoria="cereali", display_name="Pasta fresca")
    finto = FakeLlm({"groups": [{"canonical": "pasta", "merge": ["pasta fresca"]}]})

    risultato, _ = await collapse_creates(db_session, [fresca], anagrafica, client=finto)

    accorpato = next(p for p in risultato if p.action == "merge")
    assert accorpato.display_name == "Pasta"
    assert accorpato.category == "cereali"


async def test_un_canonico_che_nessuno_ha_proposto_fa_scartare_il_gruppo(db_session, anagrafica):
    """La direzione del fallimento è quella giusta.

    Scartare un collasso lascia un ingrediente in più — si vede e si corregge.
    Applicarne uno sbagliato lascia una distinzione in meno, ed è invisibile.
    """
    salmone, selvaggio = crea("salmone"), crea("salmone selvaggio")
    finto = FakeLlm({"groups": [{"canonical": "pesce", "merge": ["salmone", "salmone selvaggio"]}]})

    risultato, _ = await collapse_creates(
        db_session, [salmone, selvaggio], anagrafica, client=finto
    )
    assert sorted(p.name for p in risultato if p.action == "create") == [
        "salmone", "salmone selvaggio"
    ]
    assert not [p for p in risultato if p.action == "merge"]


async def test_un_nome_da_accorpare_che_nessuno_ha_proposto_si_ignora(db_session, anagrafica):
    salmone = crea("salmone")
    finto = FakeLlm({"groups": [{"canonical": "salmone", "merge": ["tonno"]}]})

    risultato, _ = await collapse_creates(db_session, [salmone], anagrafica, client=finto)
    assert [p.name for p in risultato if p.action == "create"] == ["salmone"]
    assert not [p for p in risultato if p.action == "merge"]


async def test_un_canonico_che_esiste_gia_in_anagrafica_e_valido(db_session, anagrafica):
    """Nuovo contro esistente: il caso che la chiamata singola avrebbe dovuto prendere.

    «Pasta fresca» proposto come `create` mentre «pasta» esiste: qui si recupera, e
    diventa un aggancio all'ingrediente vero invece di un quindicesimo cereale.
    """
    fresca = crea("pasta fresca", categoria="cereali")
    finto = FakeLlm({"groups": [{"canonical": "pasta", "merge": ["pasta fresca"]}]})

    risultato, _ = await collapse_creates(db_session, [fresca], anagrafica, client=finto)
    assert not [p for p in risultato if p.action == "create"]
    accorpato = next(p for p in risultato if p.action == "merge")
    assert accorpato.ingredient_id == anagrafica.by_name["pasta"]
    assert accorpato.name == "pasta"


async def test_senza_create_non_si_chiama_nessuno(db_session, anagrafica):
    """Zero costo nel caso comune: un lotto di soli `map` non fa nessuna domanda."""
    solo_map = TermDecisionProposal(
        term_id=uuid.uuid4(), action="map",
        ingredient_id=anagrafica.by_name["pasta"], name="pasta",
    )
    finto = FakeLlm()
    risultato, _ = await collapse_creates(db_session, [solo_map], anagrafica, client=finto)
    assert risultato == [solo_map]
    assert finto.bodies == []


async def test_un_solo_create_non_si_chiama_nessuno(db_session, anagrafica):
    """Un nome solo non ha nessuno con cui collassare fra i nuovi.

    Il confronto con l'anagrafica esistente lo ha già fatto `decide_one`, con tutta
    l'anagrafica nel prompt: rifarlo qui su un nome solo è una chiamata che non può
    scoprire niente di nuovo.
    """
    finto = FakeLlm()
    risultato, _ = await collapse_creates(db_session, [crea("speck", "carne")], anagrafica, client=finto)
    assert [p.name for p in risultato] == ["speck"]
    assert finto.bodies == []


async def test_due_termini_con_lo_stesso_nome_da_creare_sopravvivono_entrambi(
    db_session, anagrafica
):
    """«Salmone selvaggio» e «Filetto di salmone selvaggio» riducono allo stesso
    `create name="salmone selvaggio"`: due termini diversi, un solo nome. Se quel
    nome perde in un gruppo di collasso e `merged` è indicizzato per nome, le due
    proposte finiscono sostituite dallo stesso oggetto — un `term_id` sparisce dal
    risultato e l'altro compare due volte, e la scrittura del passo successivo
    applicherebbe — e conterebbe — la stessa decisione due volte per un solo termine.
    Indicizzare per `term_id` toglie la collisione: entrambi restano, una volta sola
    ciascuno.
    """
    salmone = crea("salmone")
    selvaggio_a = crea("salmone selvaggio")  # da "Salmone selvaggio"
    selvaggio_b = crea("salmone selvaggio")  # da "Filetto di salmone selvaggio"
    finto = FakeLlm({"groups": [{"canonical": "salmone", "merge": ["salmone selvaggio"]}]})

    risultato, _ = await collapse_creates(
        db_session, [salmone, selvaggio_a, selvaggio_b], anagrafica, client=finto
    )

    term_ids_risultato = [p.term_id for p in risultato]
    assert term_ids_risultato.count(selvaggio_a.term_id) == 1
    assert term_ids_risultato.count(selvaggio_b.term_id) == 1
    assert selvaggio_a.term_id in term_ids_risultato
    assert selvaggio_b.term_id in term_ids_risultato

    accorpati = {p.term_id: p for p in risultato if p.action == "merge"}
    assert set(accorpati) == {selvaggio_a.term_id, selvaggio_b.term_id}
    assert all(p.name == "salmone" for p in accorpati.values())


async def test_un_guasto_del_modello_non_perde_le_proposte(db_session, anagrafica):
    """Il collasso è un miglioramento, non un requisito: se cade, si applica il resto.

    Far fallire tutto il lotto perché la passata di rifinitura non ha risposto
    significherebbe buscare N decisioni buone per una chiamata in meno.
    """
    import httpx

    salmone, selvaggio = crea("salmone"), crea("salmone selvaggio")
    finto = FakeLlm(httpx.ReadTimeout("lento"))

    risultato, _ = await collapse_creates(
        db_session, [salmone, selvaggio], anagrafica, client=finto
    )
    assert sorted(p.name for p in risultato if p.action == "create") == [
        "salmone", "salmone selvaggio"
    ]
