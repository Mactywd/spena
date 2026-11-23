"""La rotta che fa decidere all'AI i termini rimasti in coda.

Non torna proposte da confermare: applica, e dice quante ricette ha sbloccato. È la
differenza fra la coda di prima — un modulo da compilare — e quella di adesso, che è
la revisione di un lavoro già fatto.

Le rotte di `/imports` sono dietro `require_session` (vedi
`test_senza_sessione_non_si_guarda_niente` in `test_imports.py`): qui si usa
`logged_client`, non `client`, per la stessa ragione di ogni altro test in questo
modulo.
"""

import asyncio
import json

import pytest
from sqlalchemy import select

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.repositories.ingredients import create_ingredient
from app.services.llm import (
    LLM_FAILURE_NOTICES,
    SYNC_PROFILE,
    LlmFailureKind,
    profile_worst_seconds,
)
from llm_fakes import FakeLlm, ScriptedLlm, errore_api, llm_map, user_of


@pytest.fixture(autouse=True)
def chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


async def test_la_rotta_applica_e_dice_cosa_resta(logged_client, db_session, monkeypatch):
    await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-rigatoni", display_name="Rigatoni",
        occurrences=3, decision=TermDecision.PENDING,
    )
    db_session.add(term)
    await db_session.flush()

    # il client finto si inietta sostituendo la funzione che apre quello vero: la
    # rotta non ha un parametro per passarlo, e non deve averlo — un parametro
    # iniettabile da HTTP sarebbe una via per far parlare il backend con un endpoint
    # scelto da chi chiama
    import app.services.recipe_import.decide as modulo

    monkeypatch.setattr(
        modulo, "open_client", lambda: ScriptedLlm({"Rigatoni": llm_map("pasta")})
    )

    response = await logged_client.post("/api/v1/imports/terms/decide", json={})
    assert response.status_code == 200
    corpo = response.json()
    assert corpo["applied"] == 1
    assert corpo["still_pending"] == 0
    assert corpo["remaining_terms"] == 0

    await db_session.refresh(term)
    assert term.decision == TermDecision.MAPPED
    assert term.decided_by == "ai"


async def test_senza_chiave_risponde_503_e_dice_che_la_coda_funziona(
    logged_client, db_session, monkeypatch
):
    from app.core.config import get_settings

    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-speck", display_name="Speck",
        occurrences=1, decision=TermDecision.PENDING,
    )
    db_session.add(term)
    await db_session.flush()

    get_settings.cache_clear()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    try:
        response = await logged_client.post("/api/v1/imports/terms/decide", json={})
        assert response.status_code == 503
        assert response.json() == {
            "code": "llm_not_configured",
            "detail": LLM_FAILURE_NOTICES[LlmFailureKind.NOT_CONFIGURED],
        }
    finally:
        get_settings.cache_clear()

    await db_session.refresh(term)
    assert term.decision == TermDecision.PENDING


async def test_il_credito_finito_alla_prima_domanda_risponde_503(
    logged_client, db_session, monkeypatch
):
    from app.db.models.llm_call import LlmCall

    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-speck", display_name="Speck",
        occurrences=1, decision=TermDecision.PENDING,
    )
    db_session.add(term)
    await db_session.flush()

    import app.services.recipe_import.decide as modulo

    monkeypatch.setattr(
        modulo, "open_client", lambda: FakeLlm(errore_api(402, "billing_error"))
    )

    response = await logged_client.post("/api/v1/imports/terms/decide", json={})

    assert response.status_code == 503
    assert response.json() == {
        "code": "llm_credit",
        "detail": LLM_FAILURE_NOTICES[LlmFailureKind.CREDIT],
    }
    # la riga di spesa è salvata nonostante il 503, e il termine è ancora in coda
    righe = (await db_session.execute(select(LlmCall))).scalars().all()
    assert [(r.call_site, r.ok) for r in righe] == [("term_decision", False)]
    await db_session.refresh(term)
    assert term.decision == TermDecision.PENDING


async def test_il_giro_fermato_a_meta_dice_perche(logged_client, db_session, monkeypatch):
    from app.core.config import get_settings

    await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    db_session.add_all([
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-rigatoni", display_name="Rigatoni",
            occurrences=3, decision=TermDecision.PENDING,
        ),
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-speck", display_name="Speck",
            occurrences=2, decision=TermDecision.PENDING,
        ),
    ])
    await db_session.flush()

    import app.services.recipe_import.decide as modulo

    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "1")
    get_settings.cache_clear()
    monkeypatch.setattr(
        modulo, "open_client",
        lambda: ScriptedLlm({
            "Rigatoni": llm_map("pasta"), "Speck": errore_api(402, "billing_error")
        }),
    )
    try:
        response = await logged_client.post("/api/v1/imports/terms/decide", json={})
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    corpo = response.json()
    assert corpo["applied"] == 1
    assert corpo["stopped_notice"] == LLM_FAILURE_NOTICES[LlmFailureKind.CREDIT]


async def test_un_giro_riuscito_non_ha_una_frase_di_stop(logged_client, db_session, monkeypatch):
    import app.services.recipe_import.decide as modulo

    await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    db_session.add(ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-rigatoni", display_name="Rigatoni",
        occurrences=3, decision=TermDecision.PENDING,
    ))
    await db_session.flush()
    monkeypatch.setattr(
        modulo, "open_client", lambda: ScriptedLlm({"Rigatoni": llm_map("pasta")})
    )

    response = await logged_client.post("/api/v1/imports/terms/decide", json={})

    assert response.status_code == 200
    assert response.json()["stopped_notice"] is None


async def test_senza_termini_in_coda_non_e_un_errore(logged_client):
    """Una coda vuota è il caso migliore, non un 404: la schermata non deve allarmare."""
    response = await logged_client.post("/api/v1/imports/terms/decide", json={})
    assert response.status_code == 200
    assert response.json()["applied"] == 0


async def test_term_ids_restringe_a_quei_termini(logged_client, db_session, monkeypatch):
    await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    uno = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-rigatoni", display_name="Rigatoni",
        occurrences=3, decision=TermDecision.PENDING,
    )
    due = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-penne", display_name="Penne",
        occurrences=2, decision=TermDecision.PENDING,
    )
    db_session.add_all([uno, due])
    await db_session.flush()

    import app.services.recipe_import.decide as modulo

    monkeypatch.setattr(
        modulo, "open_client", lambda: ScriptedLlm({"Rigatoni": llm_map("pasta")})
    )

    response = await logged_client.post(
        "/api/v1/imports/terms/decide", json={"term_ids": [str(uno.id)]}
    )
    assert response.status_code == 200
    await db_session.refresh(due)
    assert due.decision == TermDecision.PENDING


async def test_la_vecchia_rotta_delle_proposte_non_esiste_piu(client):
    """Una rotta morta che risponde 200 è peggio di una che non c'è.

    Il frontend non la chiama più; lasciarla in piedi significherebbe mantenere due
    modi di decidere, e uno dei due non sarebbe mai esercitato. Qui basta `client`
    senza login: una rotta assente risponde 404 dal router prima ancora che
    `require_session` entri in gioco.
    """
    response = await client.post(
        "/api/v1/imports/terms/proposals", json={"term_ids": []}
    )
    assert response.status_code == 404


async def test_lista_vuota_di_term_ids_e_un_no_op(logged_client, db_session, monkeypatch):
    """Una lista vuota `[]` non significa «tutto quanto in coda»: significa zero termini.

    La distinzione importa perché il payload può omettere `term_ids` (significa "tutti"),
    oppure passare una lista (significa "questi"). Una lista vuota deve essere un no-op:
    nessun termine viene deciso, nessuno è applicato, il database resta intatto.
    """
    await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )

    # Creiamo diversi termini PENDING nella coda
    terms = [
        ImportTerm(
            source=GIALLOZAFFERANO, term_key=f"k-pasta-{i}", display_name=f"Pasta {i}",
            occurrences=1, decision=TermDecision.PENDING,
        )
        for i in range(5)
    ]
    db_session.add_all(terms)
    await db_session.flush()

    # Fake LLM che mapperebbe tutti i termini se chiamato
    import app.services.recipe_import.decide as modulo

    monkeypatch.setattr(
        modulo, "open_client",
        lambda: ScriptedLlm({f"Pasta {i}": llm_map("pasta") for i in range(5)})
    )

    # Mandiamo term_ids vuoto: deve essere un no-op (zero termini decisi)
    response = await logged_client.post(
        "/api/v1/imports/terms/decide", json={"term_ids": []}
    )
    assert response.status_code == 200
    corpo = response.json()
    # Niente è stato deciso: la lista vuota significa "questi zero termini"
    assert corpo["applied"] == 0
    assert corpo["created"] == 0
    assert corpo["ignored"] == 0
    # still_pending è 0 perché abbiamo passato 0 termini a decide_terms
    # ma remaining_terms nel database è ancora 5 (non abbiamo toccato niente)
    assert corpo["still_pending"] == 0
    assert corpo["remaining_terms"] == 5

    # Nel database, tutti i termini restano PENDING
    for term in terms:
        await db_session.refresh(term)
        assert term.decision == TermDecision.PENDING


async def test_term_ids_non_decide_termini_da_altra_fonte(
    logged_client, db_session, monkeypatch
):
    """Un termine che appartiene a un'altra source non viene deciso nemmeno se
    passato esplicitamente in `term_ids`.

    La rotta deve filtrare per source come fa nel ramo senza `term_ids`.
    """
    # Creiamo un ingrediente per la verifica
    await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )

    # Creiamo un termine da GIALLOZAFFERANO (quello che vogliamo decidere)
    term_gz = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-rigatoni", display_name="Rigatoni",
        occurrences=1, decision=TermDecision.PENDING,
    )

    # Creiamo un termine da un'altra source
    altro_source = "altro-catalogo"
    term_altro = ImportTerm(
        source=altro_source, term_key="k-penne", display_name="Penne",
        occurrences=1, decision=TermDecision.PENDING,
    )
    db_session.add_all([term_gz, term_altro])
    await db_session.flush()

    # Fake LLM che sa decidere entrambi
    import app.services.recipe_import.decide as modulo

    monkeypatch.setattr(
        modulo, "open_client",
        lambda: ScriptedLlm({
            "Rigatoni": llm_map("pasta"),
            "Penne": llm_map("pasta"),
        })
    )

    # Proviamo a passare ENTRAMBI gli id: il filtro per source deve escludere
    # term_altro dalla query, per cui solo term_gz arriva a decide_terms
    response = await logged_client.post(
        "/api/v1/imports/terms/decide",
        json={"term_ids": [str(term_gz.id), str(term_altro.id)]}
    )
    assert response.status_code == 200
    corpo = response.json()
    # Solo il termine di GIALLOZAFFERANO è stato deciso (term_altro è stato filtrato)
    assert corpo["applied"] == 1
    assert corpo["created"] == 0
    assert corpo["ignored"] == 0
    # still_pending è 0 perché solo 1 termine è arrivato a decide_terms, ed è stato deciso
    assert corpo["still_pending"] == 0
    # remaining_terms conta solo i termini di GIALLOZAFFERANO, quindi è 0
    # (term_altro non è contato perché è di altra source)
    assert corpo["remaining_terms"] == 0

    # Nel database
    await db_session.refresh(term_gz)
    assert term_gz.decision == TermDecision.MAPPED  # questo è stato deciso

    await db_session.refresh(term_altro)
    assert term_altro.decision == TermDecision.PENDING  # questo NO, perché di altra source


async def test_term_ids_e_soggetto_allo_stesso_limite_del_ramo_senza(
    logged_client, db_session, monkeypatch
):
    """`term_ids` accetta fino a 200 id: senza un limite qui, un chiamante che ne
    manda tanti spende altrettante chiamate al modello a pagamento in una sola
    richiesta HTTP. Il ramo «tutti i pendenti» già si ferma a `MAX_TERMS_PER_CALL`;
    questo prova che il ramo per id fa lo stesso, e non uno dei due soli.
    """
    from app.api.imports import MAX_TERMS_PER_CALL

    await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    oltre_il_limite = MAX_TERMS_PER_CALL + 5
    termini = [
        ImportTerm(
            source=GIALLOZAFFERANO, term_key=f"k-{n}", display_name=f"Termine {n}",
            occurrences=1, decision=TermDecision.PENDING,
        )
        for n in range(oltre_il_limite)
    ]
    db_session.add_all(termini)
    await db_session.flush()

    import app.services.recipe_import.decide as modulo

    finto = ScriptedLlm({f"Termine {n}": llm_map("pasta") for n in range(oltre_il_limite)})
    monkeypatch.setattr(modulo, "open_client", lambda: finto)

    response = await logged_client.post(
        "/api/v1/imports/terms/decide",
        json={"term_ids": [str(t.id) for t in termini]},
    )
    assert response.status_code == 200
    corpo = response.json()
    # la chiamata al modello parte solo per i primi MAX_TERMS_PER_CALL, non per tutti
    # quelli passati in term_ids
    assert finto.calls == MAX_TERMS_PER_CALL
    assert corpo["applied"] == MAX_TERMS_PER_CALL
    # i restanti non sono nemmeno arrivati a `decide_terms`: contano ancora in coda
    assert corpo["remaining_terms"] == oltre_il_limite - MAX_TERMS_PER_CALL


class LentoLlm(ScriptedLlm):
    """Come `ScriptedLlm`, ma i termini `lenti` rispondono dopo un'attesa lunga.

    L'attesa è ben oltre la scadenza: se la scadenza non cancellasse la domanda, la
    prova durerebbe quanto l'attesa, e lo si vedrebbe.
    """

    def __init__(self, per_term: dict[str, object], lenti: set[str]) -> None:
        self._lenti = lenti
        super().__init__(per_term)

    async def answer(self, body: dict) -> object:
        if json.loads(user_of(body)).get("termine") in self._lenti:
            await asyncio.sleep(30)
        return await super().answer(body)


@pytest.fixture
def scadenza_corta(monkeypatch):
    """Alle domande resta un secondo: la scadenza della rotta meno il caso peggiore del
    profilo sincrono, la stessa sottrazione che fa la rotta."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    corta = profile_worst_seconds(SYNC_PROFILE, get_settings()) + 1.0
    monkeypatch.setenv("LLM_SYNC_DEADLINE_SECONDS", str(corta))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _termini(db_session, *nomi: str) -> list[ImportTerm]:
    # occorrenze decrescenti: la coda li chiede in quest'ordine, il primo da solo
    termini = [
        ImportTerm(
            source=GIALLOZAFFERANO, term_key=f"k-{nome.lower()}", display_name=nome,
            occurrences=10 - n, decision=TermDecision.PENDING,
        )
        for n, nome in enumerate(nomi)
    ]
    db_session.add_all(termini)
    return termini


async def test_la_scadenza_lascia_in_coda_chi_non_ha_risposto(
    logged_client, db_session, monkeypatch, scadenza_corta
):
    import app.services.recipe_import.decide as modulo

    await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    rigatoni, speck, guanciale = _termini(db_session, "Rigatoni", "Speck", "Guanciale")
    await db_session.flush()
    monkeypatch.setattr(
        modulo, "open_client",
        lambda: LentoLlm(
            {"Rigatoni": llm_map("pasta"), "Speck": llm_map("pasta"),
             "Guanciale": llm_map("pasta")},
            lenti={"Speck", "Guanciale"},
        ),
    )

    response = await logged_client.post("/api/v1/imports/terms/decide", json={})

    assert response.status_code == 200
    corpo = response.json()
    assert corpo["applied"] == 1
    assert corpo["still_pending"] == 2
    assert corpo["stopped_notice"] == (
        "L'AI ci ha messo troppo: 2 termini restano in coda. "
        "Decidili a mano qui sotto, o riprova."
    )
    for term in (rigatoni, speck, guanciale):
        await db_session.refresh(term)
    assert rigatoni.decision == TermDecision.MAPPED
    assert (speck.decision, guanciale.decision) == (TermDecision.PENDING, TermDecision.PENDING)
    assert (speck.ingredient_id, guanciale.ingredient_id) == (None, None)


async def test_la_frase_della_scadenza_conta_quel_che_resta_in_coda(
    logged_client, db_session, monkeypatch, scadenza_corta
):
    """Uno deciso, uno tagliato dalla scadenza, uno risposto ma non applicabile: in coda
    ne restano due, e la frase dice due (non uno, i soli scaduti)."""
    import app.services.recipe_import.decide as modulo

    await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    rigatoni, speck, guanciale = _termini(db_session, "Rigatoni", "Speck", "Guanciale")
    await db_session.flush()
    monkeypatch.setattr(
        modulo, "open_client",
        lambda: LentoLlm(
            {"Rigatoni": llm_map("pasta"), "Speck": llm_map("pasta"),
             "Guanciale": llm_map("ingrediente-che-non-esiste")},
            lenti={"Speck"},
        ),
    )

    response = await logged_client.post("/api/v1/imports/terms/decide", json={})

    assert response.status_code == 200
    corpo = response.json()
    assert corpo["applied"] == 1
    assert corpo["still_pending"] == 2
    assert corpo["stopped_notice"] == (
        "L'AI ci ha messo troppo: 2 termini restano in coda. "
        "Decidili a mano qui sotto, o riprova."
    )


async def test_la_scadenza_prima_di_ogni_risposta_non_e_un_503(
    logged_client, db_session, monkeypatch, scadenza_corta
):
    import app.services.recipe_import.decide as modulo

    await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    termini = _termini(db_session, "Rigatoni", "Speck")
    await db_session.flush()
    monkeypatch.setattr(
        modulo, "open_client",
        lambda: LentoLlm(
            {"Rigatoni": llm_map("pasta"), "Speck": llm_map("pasta")},
            lenti={"Rigatoni", "Speck"},
        ),
    )

    response = await logged_client.post("/api/v1/imports/terms/decide", json={})

    assert response.status_code == 200
    corpo = response.json()
    assert corpo["applied"] == 0
    assert corpo["still_pending"] == 2
    assert corpo["stopped_notice"] == (
        "L'AI ci ha messo troppo: 2 termini restano in coda. "
        "Decidili a mano qui sotto, o riprova."
    )
    for term in termini:
        await db_session.refresh(term)
        assert term.decision == TermDecision.PENDING


async def test_un_termine_solo_scaduto_ha_la_frase_al_singolare(
    logged_client, db_session, monkeypatch, scadenza_corta
):
    import app.services.recipe_import.decide as modulo

    _termini(db_session, "Speck")
    await db_session.flush()
    monkeypatch.setattr(
        modulo, "open_client",
        lambda: LentoLlm({"Speck": llm_map("pasta")}, lenti={"Speck"}),
    )

    response = await logged_client.post("/api/v1/imports/terms/decide", json={})

    assert response.status_code == 200
    assert response.json()["stopped_notice"] == (
        "L'AI ci ha messo troppo: 1 termine resta in coda. "
        "Decidilo a mano qui sotto, o riprova."
    )


async def test_la_rotta_usa_il_profilo_sincrono(logged_client, db_session, monkeypatch):
    """Le domande e il collasso: due `create` vicini fanno partire anche la chiamata
    del collasso, che deve stare nello stesso profilo."""
    import app.services.recipe_import.decide as modulo
    from llm_fakes import llm_create

    _termini(db_session, "Salmone", "Salmone selvaggio")
    await db_session.flush()
    finto = ScriptedLlm({
        "Salmone": llm_create("salmone", "Salmone", "pesce"),
        "Salmone selvaggio": llm_create("salmone selvaggio", "Salmone selvaggio", "pesce"),
    })
    monkeypatch.setattr(modulo, "open_client", lambda: finto)

    response = await logged_client.post("/api/v1/imports/terms/decide", json={})

    assert response.status_code == 200
    assert finto.calls == 3  # due domande e il collasso
    assert finto.options == [{"timeout": 45.0, "max_retries": 1}] * 3


async def test_la_scadenza_del_collasso_tiene_le_decisioni_separate(
    logged_client, db_session, monkeypatch
):
    """Le domande rispondono in tempo, il collasso no: allo scadere della rotta le
    proposte restano come sono arrivate, come quando il collasso fallisce, e la rotta
    risponde 200. Il caso peggiore del profilo si abbassa a mezzo secondo, così alle
    domande resta un secondo e al collasso il mezzo che manca a 1,5."""
    import app.api.imports as rotta
    import app.services.recipe_import.decide as modulo
    from app.core.config import get_settings
    from llm_fakes import llm_create

    class CollassoLento(ScriptedLlm):
        async def answer(self, body: dict) -> object:
            if "nuovi" in json.loads(user_of(body)):
                await asyncio.sleep(30)
            return await super().answer(body)

    import app.services.llm as llm_modulo

    monkeypatch.setattr(rotta, "profile_worst_seconds", lambda profile, settings: 0.5)
    # anche le impostazioni la leggono (rifiutano una scadenza sotto il caso peggiore)
    monkeypatch.setattr(llm_modulo, "profile_worst_seconds", lambda profile, settings: 0.5)
    monkeypatch.setenv("LLM_SYNC_DEADLINE_SECONDS", "1.5")
    get_settings.cache_clear()
    _termini(db_session, "Salmone", "Salmone selvaggio")
    await db_session.flush()
    finto = CollassoLento(
        {
            "Salmone": llm_create("salmone", "Salmone", "pesce"),
            "Salmone selvaggio": llm_create("salmone selvaggio", "Salmone selvaggio", "pesce"),
        },
        # se il collasso rispondesse, unirebbe i due nomi
        collapse={"groups": [{"canonical": "salmone", "merge": ["salmone selvaggio"]}]},
    )
    monkeypatch.setattr(modulo, "open_client", lambda: finto)

    response = await logged_client.post("/api/v1/imports/terms/decide", json={})

    assert response.status_code == 200
    corpo = response.json()
    assert (corpo["applied"], corpo["created"], corpo["still_pending"]) == (2, 2, 0)
    assert corpo["stopped_notice"] is None
    assert finto.calls == 3  # il collasso è partito, e si è cancellato
