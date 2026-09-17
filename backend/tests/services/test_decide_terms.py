"""Il fan-out, il fan-in, e la proprietà che il parallelo mette a rischio.

Il test che conta più di tutti è `test_due_create_dello_stesso_nome...`: è il buco che
si apre passando da un lotto unico a N chiamate parallele, e la sua chiusura — le
scritture in sequenza, con `match_name` rifatto prima di ogni `create` — è la ragione
per cui il fan-in esiste.
"""

import asyncio

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.repositories.ingredients import create_ingredient
from app.services.ingredient_match import match_name
from app.services.recipe_import.decide import decide_terms
from app.db.models.llm_call import LlmCall
from app.services.llm import LlmCallSite
from llm_fakes import COSTO_FINTO, LLM_IGNORE, ScriptedLlm, llm_create, llm_map


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


class CountingLlm:
    """`ScriptedLlm` che misura quante chiamate sono in volo nello stesso istante.

    Serve perché `ScriptedLlm.post` non ha nessun punto di attesa: torna senza mai
    cedere il controllo, quindi con lui il fan-out si comporta come un ciclo
    sequenziale e togliere il semaforo — o il `gather` — non farebbe fallire niente.
    Qui `post` dorme, così le chiamate si sovrappongono davvero: `max_in_flight` dice
    se il parallelo c'è, e se il semaforo lo tiene entro il limite.
    """

    def __init__(self, per_term: dict[str, object], pausa: float = 0.02) -> None:
        self._inner = ScriptedLlm(per_term)
        self._pausa = pausa
        self.in_flight = 0
        self.max_in_flight = 0

    async def post(self, url, json: dict, headers):  # noqa: A002
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(self._pausa)
            return await self._inner.post(url, json=json, headers=headers)
        finally:
            self.in_flight -= 1

    async def aclose(self):
        return None

    @property
    def calls(self) -> int:
        return self._inner.calls


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


async def test_una_somiglianza_non_certa_non_aggancia_il_create(db_session, base):
    """Guardia sulla riga 455: `match.certain` non è ridondante col solo `ingredient_id`.

    "pomodorini" è solo un vicino per trigram di "pomodoro" (lo si verifica qui sotto
    con la stessa funzione, non lo si assume): il `create` proposto dal modello deve
    diventare davvero un nuovo ingrediente, non agganciarsi in silenzio al vicino più
    simile. È lo stesso difetto che rese «Pinoli» un alias permanente di «pisello»:
    una somiglianza presentata come un fatto.
    """
    pomodoro = await create_ingredient(
        db_session, name="pomodoro", display_name="Pomodoro", category=IngredientCategory.VERDURA
    )
    verifica = await match_name(db_session, "pomodorini")
    assert verifica.certain is False
    assert verifica.ingredient_id == pomodoro.id  # è comunque il vicino più simile

    (termine_pomodorini,) = await aggiungi(db_session, termine("Pomodorini", "k-pomodorini"))
    finto = ScriptedLlm({"Pomodorini": llm_create("pomodorini", "Pomodorini", "verdura")})

    esito = await decide_terms(db_session, [termine_pomodorini], client=finto)

    assert esito.created == 1
    assert termine_pomodorini.ingredient_id != pomodoro.id
    nuovo = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "pomodorini"))
    ).scalar_one()
    assert termine_pomodorini.ingredient_id == nuovo.id


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


def test_le_categorie_offerte_allai_sono_solo_alimentari():
    """Asserito sull'insieme vero, quello che il modulo usa davvero.

    Una copia scritta qui passerebbe anche il giorno in cui la produzione
    smettesse di filtrare: è la prima lezione di CLAUDE.md, un test che guarda
    un oggetto che nessuno chiama.
    """
    from app.services.recipe_import.decide import CATEGORIES

    assert "casa" not in CATEGORIES
    assert "igiene" not in CATEGORIES
    assert "verdura" in CATEGORIES


async def test_una_categoria_non_alimentare_proposta_dallai_resta_in_coda(db_session, base):
    """«igiene» è un reparto vero, e qui sta la differenza con il test qui sopra.

    Là la risposta è rifiutata perché «salumi» non esiste; qui è rifiutata perché
    non è cibo. Finché `CATEGORIES` conteneva l'enum intero questa sarebbe stata
    una decisione **applicata**, con una voce non alimentare nata da un ricettario
    e nessuno ad accorgersene.
    """
    (sapone,) = await aggiungi(db_session, termine("Sapone", "k-sapone"))
    finto = ScriptedLlm({"Sapone": llm_create("sapone", "Sapone", "igiene")})

    esito = await decide_terms(db_session, [sapone], client=finto)

    assert esito.applied == 0
    assert esito.still_pending == 1
    assert sapone.decision == TermDecision.PENDING
    assert sapone.decided_by is None
    creati = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "sapone"))
    ).scalars().all()
    assert creati == [], "nessuna voce non alimentare deve nascere da un ricettario"


async def test_una_mappatura_su_una_voce_non_alimentare_resta_in_coda(db_session, base):
    """Il ramo `map` non aveva questa guardia: bastava che l'anagrafica avesse già una
    voce non alimentare per farcela mappare sopra, senza passare da nessuna delle
    verifiche di categoria che valgono per `create` (vedi il test qui sopra sulla
    stessa cosa per `create`). Come là, si rifiuta come ogni altra risposta non
    verificabile: il termine resta `pending` e non nasce nessun alias.
    """
    sapone = await create_ingredient(
        db_session, name="sapone", display_name="Sapone", category=IngredientCategory.IGIENE
    )
    (detersivo,) = await aggiungi(db_session, termine("Detersivo per piatti", "k-detersivo"))
    finto = ScriptedLlm({"Detersivo per piatti": llm_map("sapone")})

    esito = await decide_terms(db_session, [detersivo], client=finto)

    assert esito.applied == 0
    assert esito.still_pending == 1
    assert detersivo.decision == TermDecision.PENDING
    assert detersivo.decided_by is None
    assert detersivo.ingredient_id is None
    alias = (
        await db_session.execute(
            select(IngredientAlias).where(IngredientAlias.ingredient_id == sapone.id)
        )
    ).scalars().all()
    assert alias == []


async def test_un_create_che_risolve_su_un_alias_non_alimentare_resta_in_coda(db_session, base):
    """Rotta B del finding round 1: `create` non passa mai da `_mapped_proposal`.

    La categoria dichiarata dall'AI è alimentare e il nome non è in
    `registry.by_name` (costruito solo su `Ingredient.name`), quindi
    `_verified_proposal` lo lascia passare come `create` vero — proprio perché il
    suo nome non è nell'anagrafica sotto quella forma. Solo al fan-in, `match_name`
    lo risolve sull'**alias** di una voce non alimentare, cosa che `by_name` non
    può vedere. Senza una guardia lì, il termine diventerebbe `MAPPED` per sempre
    su «detersivo» e ci scriverebbe pure un alias nuovo — esattamente lo scenario
    concreto del finding.
    """
    from app.repositories.ingredients import add_alias

    detersivo = await create_ingredient(
        db_session, name="detersivo", display_name="Detersivo", category=IngredientCategory.IGIENE
    )
    await add_alias(db_session, detersivo.id, "detersivo piatti", source="seed")
    (termine_detersivo,) = await aggiungi(
        db_session, termine("Detersivo per i piatti", "k-detersivo-piatti")
    )
    finto = ScriptedLlm({
        "Detersivo per i piatti": llm_create("detersivo piatti", "Detersivo piatti", "condimenti")
    })

    esito = await decide_terms(db_session, [termine_detersivo], client=finto)

    assert esito.applied == 0
    assert esito.created == 0
    assert esito.still_pending == 1
    assert termine_detersivo.decision == TermDecision.PENDING
    assert termine_detersivo.decided_by is None
    assert termine_detersivo.ingredient_id is None
    creati = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "detersivo piatti"))
    ).scalars().all()
    assert creati == [], "nessuna voce non alimentare deve nascere da un ricettario"
    alias = (
        await db_session.execute(
            select(IngredientAlias.alias).where(IngredientAlias.ingredient_id == detersivo.id)
        )
    ).scalars().all()
    assert alias == ["detersivo piatti"], "nessun alias nuovo deve aggiungersi"


async def test_un_merge_del_collasso_su_una_voce_non_alimentare_resta_in_coda(db_session, base):
    """Rotta A del finding round 1: il `merge` che nasce nel collasso.

    `collapse_creates` prende `existing_id = registry.by_name.get(canonical)` e lo
    mette in una proposta `merge` senza nessun controllo di kind: `search_ingredients`,
    che trova i vicini, non filtra per kind, e al modello del collasso arrivano solo i
    nomi, mai la categoria. Un `create` proposto per «detersivo per piatti», con
    «detersivo» (non alimentare) come vicino di trigrammi, può quindi collassare sullo
    stesso ingrediente non alimentare — scavalcando `_mapped_proposal`, che il `merge`
    non attraversa mai. La stessa guardia al fan-in, a valle di entrambe le rotte, lo
    chiude comunque.
    """
    detersivo = await create_ingredient(
        db_session, name="detersivo", display_name="Detersivo", category=IngredientCategory.IGIENE
    )
    (termine_detersivo,) = await aggiungi(
        db_session, termine("Detersivo per piatti", "k-detersivo-piatti")
    )
    finto = ScriptedLlm(
        {
            "Detersivo per piatti": llm_create(
                "detersivo per piatti", "Detersivo per piatti", "condimenti"
            )
        },
        collapse={"groups": [{"canonical": "detersivo", "merge": ["detersivo per piatti"]}]},
    )

    esito = await decide_terms(db_session, [termine_detersivo], client=finto)

    assert esito.applied == 0
    assert esito.created == 0
    assert esito.still_pending == 1
    assert termine_detersivo.decision == TermDecision.PENDING
    assert termine_detersivo.decided_by is None
    assert termine_detersivo.ingredient_id is None
    alias = (
        await db_session.execute(
            select(IngredientAlias).where(IngredientAlias.ingredient_id == detersivo.id)
        )
    ).scalars().all()
    assert alias == [], "nessun alias nuovo deve nascere sulla voce non alimentare"


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


async def test_un_guasto_su_un_termine_non_tocca_gli_altri(db_session, base, caplog):
    """L'isolamento del guasto, che è l'altro regalo del fan-out.

    Con un lotto unico una chiamata caduta perdeva tutte le decisioni del lotto.
    """
    import logging

    import httpx

    rigatoni, speck = await aggiungi(
        db_session, termine("Rigatoni", "k-rigatoni"), termine("Speck", "k-speck")
    )
    finto = ScriptedLlm({
        "Rigatoni": llm_map("pasta"),
        "Speck": httpx.ReadTimeout("lento"),
    })

    with caplog.at_level(logging.WARNING):
        esito = await decide_terms(db_session, [rigatoni, speck], client=finto)

    assert esito.applied == 1
    assert esito.still_pending == 1
    assert rigatoni.decision == TermDecision.MAPPED
    assert speck.decision == TermDecision.PENDING
    # senza questo avviso `applied=0, still_pending=N` non dice da nessuna parte
    # perché: un modello giù per ogni termine sarebbe indistinguibile da un difetto
    # nostro, e la ragione starebbe solo nel corpo HTTP che nessuno rilegge
    messaggi = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("Speck" in m and "non deciso" in m for m in messaggi)


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


async def test_una_decisione_azzera_il_ruolo_forzato(db_session, base):
    """`role_override` è nell'elenco della spec §4.3, e il Task 10 lo riporta a `NULL`.

    L'AI non propone ruoli, quindi il valore giusto è `None`. Scriverlo e non solo
    lasciarlo stare è ciò che rende i due elenchi — quello che scrive e quello che
    annulla — la stessa lista, senza una differenza da spiegare.
    """
    rigatoni, acqua = await aggiungi(
        db_session, termine("Rigatoni", "k-rigatoni"), termine("Acqua", "k-acqua")
    )
    rigatoni.role_override = "primary"
    acqua.role_override = "secondary"
    await db_session.flush()

    finto = ScriptedLlm({"Rigatoni": llm_map("pasta"), "Acqua": LLM_IGNORE})
    esito = await decide_terms(db_session, [rigatoni, acqua], client=finto)

    assert esito.applied == 2
    assert rigatoni.role_override is None
    assert acqua.role_override is None


async def test_un_errore_inatteso_su_un_termine_non_perde_le_altre_decisioni(
    db_session, base, monkeypatch, caplog
):
    """Il `gather` non deve poter buttare il lotto per un errore che non è di rete.

    `complete_json` traduce tutto ciò che è rete o parsing in `LlmUnavailable`, che
    `ask` assorbe; il corpo di `decide_one` dopo la chiamata, e la costruzione della
    domanda, non sono coperti da niente. Senza `return_exceptions=True` un errore lì
    risalirebbe dal `gather` e porterebbe via anche le decisioni già verificate degli
    altri termini — chiudendo il client condiviso con le chiamate ancora in volo.
    """
    import logging

    from app.services.recipe_import import decide as modulo

    vero = modulo.decide_one

    async def a_volte_scoppia(session, term, registry, client=None):
        if term.display_name == "Speck":
            raise RuntimeError("un difetto nostro, non un guasto del modello")
        return await vero(session, term, registry, client=client)

    monkeypatch.setattr(modulo, "decide_one", a_volte_scoppia)

    rigatoni, speck = await aggiungi(
        db_session, termine("Rigatoni", "k-rigatoni"), termine("Speck", "k-speck")
    )
    finto = ScriptedLlm({"Rigatoni": llm_map("pasta")})

    with caplog.at_level(logging.ERROR):
        esito = await decide_terms(db_session, [rigatoni, speck], client=finto)

    assert esito.applied == 1
    assert esito.still_pending == 1
    assert rigatoni.decision == TermDecision.MAPPED
    assert speck.decision == TermDecision.PENDING
    assert speck.decided_by is None
    # un difetto nostro non deve produrre lo stesso silenzio di un modello giù:
    # qui ci vuole il livello error e la traccia, non solo un avviso
    (record,) = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert "Speck" in record.getMessage()
    assert record.exc_info is not None
    assert record.exc_info[1].args == ("un difetto nostro, non un guasto del modello",)


async def test_una_concorrenza_a_zero_non_appende_limport(db_session, base, monkeypatch):
    """`LLM_MAX_CONCURRENCY=0` sarebbe un semaforo che non si apre mai.

    Si scrive in `.env`, quindi ci arriva un operatore e non un test. Un import appeso
    per sempre non ha né timeout né errore: è il guasto che non si presenta. Degrada a
    una domanda per volta. Il `wait_for` è lì perché senza di lui un ritorno di questo
    difetto farebbe restare appesa la suite, non fallire un test.
    """
    from app.core.config import get_settings

    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "0")
    get_settings.cache_clear()

    rigatoni, acqua = await aggiungi(
        db_session, termine("Rigatoni", "k-rigatoni"), termine("Acqua", "k-acqua")
    )
    finto = ScriptedLlm({"Rigatoni": llm_map("pasta"), "Acqua": LLM_IGNORE})

    esito = await asyncio.wait_for(
        decide_terms(db_session, [rigatoni, acqua], client=finto), timeout=5
    )

    assert esito.applied == 2
    assert finto.calls == 2


async def test_le_domande_partono_insieme_e_il_semaforo_le_tiene(db_session, base, monkeypatch):
    """La proprietà su cui poggia tutto il disegno: le domande vanno in parallelo.

    È la ragione per cui si fa una chiamata per termine invece di un lotto unico (vedi
    la docstring del modulo), e nessun altro test la vede: con un finto che non attende
    mai, un ciclo sequenziale e il `gather` sono indistinguibili. Le due assert sono le
    due metà della stessa proprietà — più di una chiamata insieme, e non più di quante
    il semaforo permette.
    """
    from app.core.config import get_settings

    limite = 2
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", str(limite))
    get_settings.cache_clear()

    termini = await aggiungi(
        db_session, *(termine(f"Pasta formato {n}", f"k-{n}") for n in range(6))
    )
    finto = CountingLlm({f"Pasta formato {n}": llm_map("pasta") for n in range(6)})

    esito = await decide_terms(db_session, list(termini), client=finto)

    assert esito.applied == 6
    assert finto.calls == 6
    # in parallelo davvero: un ciclo sequenziale misurerebbe 1
    assert finto.max_in_flight > 1
    # e non oltre il limite: senza semaforo misurerebbe 6
    assert finto.max_in_flight <= limite


async def test_ogni_domanda_allai_finisce_nello_storico_delle_spese(db_session, base):
    """Una riga per chiamata, nessuna esclusa.

    È l'asserzione che conta: non «ci sono delle righe», ma «tante quante le domande
    fatte». Registrarne una su due darebbe una torta delle spese che sembra giusta e
    sottostima, che è peggio di non averla.
    """
    rigatoni, speck = await aggiungi(
        db_session, termine("Rigatoni", "k-rigatoni"), termine("Speck", "k-speck")
    )
    finto = ScriptedLlm({
        "Rigatoni": llm_map("pasta"),
        "Speck": llm_create("speck", "Speck", "carne"),
    })

    await decide_terms(db_session, [rigatoni, speck], client=finto)

    righe = (await db_session.execute(select(LlmCall))).scalars().all()
    assert len(righe) == finto.calls
    assert {r.call_site for r in righe} <= {
        LlmCallSite.TERM_DECISION, LlmCallSite.TERM_COLLAPSE
    }
    assert LlmCallSite.TERM_DECISION in {r.call_site for r in righe}
    assert all(r.ok for r in righe)
    assert sum(r.cost_usd for r in righe) == pytest.approx(finto.calls * COSTO_FINTO)
