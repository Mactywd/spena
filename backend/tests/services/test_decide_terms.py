"""Il fan-out, il fan-in, e la proprietà che il parallelo mette a rischio.

Il test che conta più di tutti è `test_due_create_dello_stesso_nome...`: è il buco che
si apre passando da un lotto unico a N chiamate parallele, e la sua chiusura — le
scritture in sequenza, con `match_name` rifatto prima di ogni `create` — è la ragione
per cui il fan-in esiste.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.repositories.ingredients import create_ingredient
from app.services.recipe_import.decide import decide_terms
from llm_fakes import LLM_IGNORE, ScriptedLlm, llm_create, llm_map


@pytest.fixture(autouse=True)
def chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def base(db_session):
    await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )


def termine(nome: str, chiave: str, quante: int = 3) -> ImportTerm:
    return ImportTerm(
        source=GIALLOZAFFERANO, term_key=chiave, display_name=nome,
        occurrences=quante, decision=TermDecision.PENDING,
    )


async def aggiungi(db_session, *termini: ImportTerm) -> list[ImportTerm]:
    db_session.add_all(termini)
    await db_session.flush()
    return list(termini)


async def test_le_tre_azioni_si_applicano(db_session, base):
    rigatoni, speck, acqua = await aggiungi(
        db_session,
        termine("Rigatoni", "k-rigatoni"),
        termine("Speck", "k-speck"),
        termine("Acqua", "k-acqua"),
    )
    finto = ScriptedLlm({
        "Rigatoni": llm_map("pasta"),
        "Speck": llm_create("speck", "Speck", "carne"),
        "Acqua": LLM_IGNORE,
    })

    esito = await decide_terms(db_session, [rigatoni, speck, acqua], client=finto)

    assert esito.applied == 3
    assert esito.created == 1
    assert esito.ignored == 1
    assert esito.still_pending == 0

    assert rigatoni.decision == TermDecision.MAPPED
    assert rigatoni.decided_by == "ai"
    assert rigatoni.decided_at is not None
    assert speck.decision == TermDecision.MAPPED
    assert acqua.decision == TermDecision.IGNORED
    assert acqua.ingredient_id is None

    creato = await db_session.get(Ingredient, speck.ingredient_id)
    assert (creato.name, creato.display_name, creato.category) == ("speck", "Speck", "carne")


async def test_ogni_decisione_scrive_lalias_permanente(db_session, base):
    (rigatoni,) = await aggiungi(db_session, termine("Rigatoni", "k-rigatoni"))
    finto = ScriptedLlm({"Rigatoni": llm_map("pasta")})

    await decide_terms(db_session, [rigatoni], client=finto)

    alias = (
        await db_session.execute(
            select(IngredientAlias).where(IngredientAlias.alias == "rigatoni")
        )
    ).scalar_one()
    assert alias.ingredient_id == rigatoni.ingredient_id
    assert alias.source == "import"


async def test_un_termine_ignorato_non_scrive_nessun_alias(db_session, base):
    """Un alias su un termine ignorato non punterebbe a niente, e resterebbe."""
    (acqua,) = await aggiungi(db_session, termine("Acqua", "k-acqua"))
    await decide_terms(db_session, [acqua], client=ScriptedLlm({"Acqua": LLM_IGNORE}))

    trovati = (
        await db_session.execute(
            select(IngredientAlias).where(IngredientAlias.alias == "acqua")
        )
    ).scalars().all()
    assert trovati == []


async def test_due_create_dello_stesso_nome_fanno_un_ingrediente_e_due_termini(db_session, base):
    """Il buco che il parallelo apre, e la sua chiusura.

    Scritte in parallelo, queste due proposte sarebbero un doppione o una violazione
    del vincolo di unicità. Applicate in sequenza con `match_name` rifatto prima di
    ogni `create`, la seconda trova quello che la prima ha appena creato.
    """
    speck, cubetti = await aggiungi(
        db_session, termine("Speck", "k-speck"), termine("Speck a cubetti", "k-speck-cubetti")
    )
    finto = ScriptedLlm({
        "Speck": llm_create("speck", "Speck", "carne"),
        "Speck a cubetti": llm_create("speck", "Speck a cubetti", "carne"),
    })

    esito = await decide_terms(db_session, [speck, cubetti], client=finto)

    assert esito.created == 1
    assert speck.ingredient_id == cubetti.ingredient_id
    quanti = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "speck"))
    ).scalars().all()
    assert len(quanti) == 1
    # entrambi i termini portano il loro alias, che è ciò che li farà riconoscere
    # senza chiamare nessuno al prossimo giro
    alias = (
        await db_session.execute(
            select(IngredientAlias.alias).where(
                IngredientAlias.ingredient_id == speck.ingredient_id
            )
        )
    ).scalars().all()
    assert sorted(alias) == ["speck", "speck a cubetti"]


async def test_un_create_che_e_gia_un_alias_diventa_una_mappatura(db_session, base):
    """La ragione per cui `match_name` si rifà qui, e non basta il registro.

    `decide_one` confronta un nome nuovo solo con `ingredients.name`: un nome che
    l'anagrafica ha già come **alias** le arriva ancora sotto forma di `create`.
    `match_name` interroga nomi canonici e alias, e lo riporta al `map` che doveva
    essere — senza creare un secondo ingrediente che l'autocomplete mostrerebbe
    accanto al primo.
    """
    from app.repositories.ingredients import add_alias

    pasta = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "pasta"))
    ).scalar_one()
    await add_alias(db_session, pasta.id, "rigatoni", source="seed")

    (termine_rigatoni,) = await aggiungi(db_session, termine("Rigatoni giganti", "k-rigatoni-g"))
    finto = ScriptedLlm({"Rigatoni giganti": llm_create("rigatoni", "Rigatoni", "cereali")})

    esito = await decide_terms(db_session, [termine_rigatoni], client=finto)

    assert esito.created == 0
    assert esito.applied == 1
    assert termine_rigatoni.ingredient_id == pasta.id
    nomi = (await db_session.execute(select(Ingredient.name))).scalars().all()
    assert nomi == ["pasta"]


async def test_un_collasso_produce_un_ingrediente_e_due_termini(db_session, base):
    salmone, selvaggio = await aggiungi(
        db_session, termine("Salmone", "k-salmone"), termine("Salmone selvaggio", "k-salmone-s")
    )
    finto = ScriptedLlm(
        {
            "Salmone": llm_create("salmone", "Salmone", "pesce"),
            "Salmone selvaggio": llm_create("salmone selvaggio", "Salmone selvaggio", "pesce"),
        },
        collapse={"groups": [{"canonical": "salmone", "merge": ["salmone selvaggio"]}]},
    )

    esito = await decide_terms(db_session, [salmone, selvaggio], client=finto)

    assert esito.created == 1
    assert salmone.ingredient_id == selvaggio.ingredient_id
    nomi = (
        await db_session.execute(select(Ingredient.name).where(Ingredient.category == "pesce"))
    ).scalars().all()
    assert nomi == ["salmone"]
    # il nome perdente non si butta: diventa l'alias che lo farà riconoscere da solo
    alias = (
        await db_session.execute(
            select(IngredientAlias.alias).where(
                IngredientAlias.ingredient_id == salmone.ingredient_id
            )
        )
    ).scalars().all()
    assert "salmone selvaggio" in alias


async def test_una_risposta_non_verificabile_lascia_il_termine_in_coda(db_session, base):
    rigatoni, speck = await aggiungi(
        db_session, termine("Rigatoni", "k-rigatoni"), termine("Speck", "k-speck")
    )
    finto = ScriptedLlm({
        "Rigatoni": llm_map("pasta"),
        "Speck": llm_create("speck", "Speck", "salumi"),  # categoria inventata
    })

    esito = await decide_terms(db_session, [rigatoni, speck], client=finto)

    assert esito.applied == 1
    assert esito.still_pending == 1
    assert rigatoni.decision == TermDecision.MAPPED
    assert speck.decision == TermDecision.PENDING
    assert speck.decided_by is None


async def test_un_nome_piu_lungo_della_colonna_resta_in_coda(db_session, base):
    """`ingredients.name` è `String(120)`: oltre, l'insert è un errore, non una decisione.

    Niente a monte lo rifiuta — `decide_one` guarda che il nome non sia vuoto e che la
    categoria sia una delle dodici, e si ferma lì. Arrivato all'insert diventerebbe un
    errore del database in mezzo alla passata che scrive, cioè il contrario di «questo
    termine resta in coda».
    """
    lungo = (
        "ragu di carne di manzo macinata grossa con cipolla carota sedano e vino rosso "
        "lasciato sobbollire per tre ore in una pentola di coccio"
    )
    assert len(lungo) > 120
    (ragu,) = await aggiungi(db_session, termine("Ragù lunghissimo", "k-ragu"))
    finto = ScriptedLlm({"Ragù lunghissimo": llm_create(lungo, "Ragù", "carne")})

    esito = await decide_terms(db_session, [ragu], client=finto)

    assert esito.applied == 0
    assert esito.created == 0
    assert esito.still_pending == 1
    assert ragu.decision == TermDecision.PENDING
    assert ragu.decided_by is None
    nomi = (await db_session.execute(select(Ingredient.name))).scalars().all()
    assert nomi == ["pasta"]


async def test_un_termine_troppo_lungo_per_un_alias_si_decide_comunque(db_session, base):
    """`import_terms.display_name` è `String(200)`, `ingredient_aliases.alias` è `String(120)`.

    La decisione vive su `import_terms` e saltare l'alias non la perde (vedi
    `remember_alias`); scriverlo sarebbe un errore del database a metà della passata.
    """
    nome = "rigatoni " * 20
    assert len(nome.strip()) > 120
    (lungo,) = await aggiungi(db_session, termine(nome.strip(), "k-lungo"))
    finto = ScriptedLlm({nome.strip(): llm_map("pasta")})

    esito = await decide_terms(db_session, [lungo], client=finto)

    assert esito.applied == 1
    assert lungo.decision == TermDecision.MAPPED
    assert lungo.ingredient_id is not None
    alias = (await db_session.execute(select(IngredientAlias.alias))).scalars().all()
    assert alias == []


async def test_un_guasto_su_un_termine_non_tocca_gli_altri(db_session, base):
    """L'isolamento del guasto, che è l'altro regalo del fan-out.

    Con un lotto unico una chiamata caduta perdeva tutte le decisioni del lotto.
    """
    import httpx

    rigatoni, speck = await aggiungi(
        db_session, termine("Rigatoni", "k-rigatoni"), termine("Speck", "k-speck")
    )
    finto = ScriptedLlm({
        "Rigatoni": llm_map("pasta"),
        "Speck": httpx.ReadTimeout("lento"),
    })

    esito = await decide_terms(db_session, [rigatoni, speck], client=finto)

    assert esito.applied == 1
    assert esito.still_pending == 1
    assert rigatoni.decision == TermDecision.MAPPED
    assert speck.decision == TermDecision.PENDING


async def test_una_lista_vuota_non_chiama_nessuno(db_session, base):
    finto = ScriptedLlm({})
    esito = await decide_terms(db_session, [], client=finto)
    assert esito == type(esito)(applied=0, created=0, ignored=0, still_pending=0)
    assert finto.calls == 0


async def test_senza_chiave_solleva_invece_di_decidere_a_caso(db_session, base, monkeypatch):
    from app.core.config import get_settings
    from app.services.llm import LlmUnavailable

    (rigatoni,) = await aggiungi(db_session, termine("Rigatoni", "k-rigatoni"))
    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    try:
        with pytest.raises(LlmUnavailable):
            await decide_terms(db_session, [rigatoni])
    finally:
        get_settings.cache_clear()
    assert rigatoni.decision == TermDecision.PENDING
