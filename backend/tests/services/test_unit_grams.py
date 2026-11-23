"""Le coppie ingrediente × unità che le ricette usano, e i loro pesi (S4, fetta 2).

Le ricette di prova si scrivono con `create_recipe`, che legge le dosi col parser vero e
deposita le unità come fa l'import: «spicchi» è un'unità a sé finché, come farebbe
`decide_units`, non punta a «spicchio».
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.models.ingredient import Ingredient
from app.db.models.nutrition import IngredientUnitGrams
from app.db.models.recipe import RecipeSource
from app.db.models.unit import Unit
from app.repositories.recipes import create_recipe
from app.repositories.units import apply_forms, ensure_unit, set_unit_forms
from app.services import registry
from app.services.ingredient_nutrition import NutritionRefusal
from app.services.unit_grams import (
    Weight,
    apply_ai_grams,
    clear_grams,
    count_pending_pairs,
    pending_pairs,
    realign_weights,
    set_grams,
    used_pairs,
    weights_of,
)


async def _mondo(db_session) -> dict[str, Ingredient]:
    voci = {
        nome: Ingredient(name=nome, display_name=nome.capitalize(), category=reparto)
        for nome, reparto in [
            ("aglio", "verdura"), ("uova", "altro"), ("olio di oliva", "condimenti"),
            ("pasta", "cereali"), ("basilico", "spezie"), ("detersivo", "casa"),
        ]
    }
    db_session.add_all(voci.values())
    await db_session.flush()

    async def ricetta(titolo, righe):
        await create_recipe(
            db_session, title=titolo, description=None, instructions="Si cucina.", servings=2,
            source=RecipeSource.MANUAL, source_ref=None, embedding=None,
            ingredients=[(voci[nome].id, ruolo, dose, None) for nome, ruolo, dose in righe],
        )

    await ricetta("Prima", [
        ("aglio", "secondary", "1 spicchio"), ("uova", "primary", "2"),
        ("olio di oliva", "secondary", "2 cucchiai"), ("pasta", "primary", "180 g"),
        ("basilico", "secondary", "q.b."),
    ])
    await ricetta("Seconda", [
        ("aglio", "secondary", "2 spicchi"), ("uova", "primary", "1 pezzo"),
        ("olio di oliva", "secondary", "1 l"),
    ])
    # «spicchi» punta a «spicchio», come farebbe `decide_units`
    await set_unit_forms(db_session, "spicchi", "spicchio", "spicchi")
    return voci


async def _unita(db_session, chiave: str) -> uuid.UUID:
    return (await db_session.execute(select(Unit.id).where(Unit.key == chiave))).scalar_one()


async def test_used_pairs_salta_massa_volume_e_q_b(db_session):
    await _mondo(db_session)

    coppie = await used_pairs(db_session)

    # 180 g e 1 l si pesano da sé; «q.b.» non ha una dose: nessuna coppia
    assert [(c.ingredient_name, c.unit_label) for c in coppie] == [
        ("aglio", "spicchio"), ("olio di oliva", "cucchiai"), ("uova", "pezzo"),
    ]


async def test_used_pairs_unisce_le_unita_canoniche_e_i_pezzi(db_session):
    voci = await _mondo(db_session)
    spicchio = await _unita(db_session, "spicchio")

    aglio = await used_pairs(db_session, voci["aglio"].id)
    uova = await used_pairs(db_session, voci["uova"].id)

    # «1 spicchio» e «2 spicchi»: una coppia sola, sull'unità canonica
    assert [(c.unit_id, c.example) for c in aglio] == [(spicchio, "1 spicchio")]
    # «2» e «1 pezzo»: una coppia sola, il pezzo
    assert [(c.unit_id, c.unit_label) for c in uova] == [(None, "pezzo")]


async def test_weights_of_dice_lo_stato_di_ogni_coppia(db_session):
    voci = await _mondo(db_session)
    spicchio = await _unita(db_session, "spicchio")
    cucchiai = await _unita(db_session, "cucchiai")
    testa = (await ensure_unit(db_session, "testa")).id
    await apply_ai_grams(db_session, voci["aglio"].id, spicchio, Decimal("5"))
    # un peso deciso per un'unità che le ricette non usano più resta, e si vede
    await apply_ai_grams(db_session, voci["aglio"].id, testa, Decimal("40"))
    await apply_ai_grams(db_session, voci["olio di oliva"].id, cucchiai, None)

    assert await weights_of(db_session, voci["aglio"].id) == [
        Weight(str(spicchio), "spicchio", Decimal("5.00"), "decided", "ai"),
        Weight(str(testa), "testa", Decimal("40.00"), "decided", "ai"),
    ]
    assert await weights_of(db_session, voci["olio di oliva"].id) == [
        Weight(str(cucchiai), "cucchiai", None, "none", "ai"),
    ]
    assert await weights_of(db_session, voci["uova"].id) == [
        Weight("pezzo", "pezzo", None, "undecided", None),
    ]


async def test_il_peso_a_mano_vince_e_va_sull_unita_canonica(db_session):
    voci = await _mondo(db_session)
    spicchio = await _unita(db_session, "spicchio")
    spicchi = await _unita(db_session, "spicchi")
    await apply_ai_grams(db_session, voci["aglio"].id, spicchio, Decimal("5"))

    pesi = await set_grams(db_session, voci["aglio"].id, spicchi, Decimal("6"))

    assert pesi == [Weight(str(spicchio), "spicchio", Decimal("6.00"), "decided", "human")]
    assert await apply_ai_grams(db_session, voci["aglio"].id, spicchio, Decimal("7")) is False


async def test_i_rifiuti_dicono_perche(db_session):
    voci = await _mondo(db_session)
    grammi = await _unita(db_session, "g")
    spicchio = await _unita(db_session, "spicchio")

    with pytest.raises(NutritionRefusal) as misurata:
        await set_grams(db_session, voci["pasta"].id, grammi, Decimal("1"))
    assert misurata.value.code == "measured_unit"
    assert misurata.value.message == "«g» è un'unità di peso o di volume: i grammi si contano da sé."

    with pytest.raises(NutritionRefusal) as non_cibo:
        await set_grams(db_session, voci["detersivo"].id, None, Decimal("10"))
    assert non_cibo.value.code == "non_food"

    for sbagliato in (Decimal("6000"), Decimal("0"), Decimal("-1"), Decimal("0.001"), Decimal("NaN"), Decimal("1E+30")):
        with pytest.raises(NutritionRefusal) as fuori:
            await set_grams(db_session, voci["aglio"].id, spicchio, sbagliato)
        assert fuori.value.code == "bad_grams"
        assert fuori.value.message == "Un peso va da più di 0 a 5000 g: controlla il numero."

    with pytest.raises(LookupError):
        await set_grams(db_session, uuid.uuid4(), spicchio, Decimal("5"))
    with pytest.raises(LookupError):
        await set_grams(db_session, voci["aglio"].id, uuid.uuid4(), Decimal("5"))


async def test_annullare_riporta_a_da_decidere(db_session):
    voci = await _mondo(db_session)
    await set_grams(db_session, voci["uova"].id, None, Decimal("50"))

    pesi = await clear_grams(db_session, voci["uova"].id, None)

    assert pesi == [Weight("pezzo", "pezzo", None, "undecided", None)]


async def test_l_ai_scrive_solo_dove_non_c_e_niente(db_session):
    voci = await _mondo(db_session)
    await set_grams(db_session, voci["uova"].id, None, Decimal("50"))

    assert await apply_ai_grams(db_session, voci["uova"].id, None, Decimal("60")) is False
    assert await apply_ai_grams(db_session, voci["uova"].id, None, None) is False
    righe = (await db_session.execute(select(IngredientUnitGrams.grams, IngredientUnitGrams.decided_by))).all()
    assert [tuple(riga) for riga in righe] == [(Decimal("50.00"), "human")]


async def test_le_coppie_da_pesare_sono_quelle_senza_un_peso(db_session):
    voci = await _mondo(db_session)
    await apply_ai_grams(db_session, voci["uova"].id, None, Decimal("50"))

    assert [(c.ingredient_name, c.unit_label) for c in await pending_pairs(db_session)] == [
        ("aglio", "spicchio"), ("olio di oliva", "cucchiai"),
    ]
    assert len(await pending_pairs(db_session, limit=1)) == 1
    assert await count_pending_pairs(db_session) == 2


async def test_la_fusione_perde_i_pesi_del_perdente(db_session):
    """Deciso da Mattia il 2026-10-13 (spec §12): il vincitore tiene i suoi."""
    voci = await _mondo(db_session)
    uovo = Ingredient(name="uovo", display_name="Uovo", category="altro")
    db_session.add(uovo)
    await db_session.flush()
    await apply_ai_grams(db_session, uovo.id, None, Decimal("55"))
    await set_grams(db_session, voci["uova"].id, None, Decimal("50"))

    await registry.merge_ingredients(db_session, uovo.id, voci["uova"].id)

    righe = (
        await db_session.execute(select(IngredientUnitGrams.ingredient_id, IngredientUnitGrams.grams))
    ).all()
    assert [tuple(riga) for riga in righe] == [(voci["uova"].id, Decimal("50.00"))]


async def _forma_su(db_session, canonica: str, sing: str | None = None):
    """«cucchiai» riceve la canonica `canonica`, dopo che l'olio ha già un peso su «cucchiai»."""
    voci = await _mondo(db_session)
    cucchiai = await ensure_unit(db_session, "cucchiai")
    canon = await ensure_unit(db_session, canonica)
    return voci, cucchiai, canon


async def _riga(db_session, ingrediente, unit_id, grammi, chi):
    db_session.add(IngredientUnitGrams(
        ingredient_id=ingrediente.id, unit_id=unit_id, grams=Decimal(grammi), decided_by=chi,
    ))
    await db_session.flush()


async def _righe(db_session, ingrediente):
    return list((await db_session.execute(
        select(IngredientUnitGrams).where(IngredientUnitGrams.ingredient_id == ingrediente.id)
    )).scalars())


async def test_il_peso_passa_alla_canonica_quando_l_unita_la_riceve(db_session):
    voci, cucchiai, cucchiaio = await _forma_su(db_session, "cucchiaio")
    olio = voci["olio di oliva"]
    await _riga(db_session, olio, cucchiai.id, "12", "ai")
    prima = (await _righe(db_session, olio))[0]
    decisa = prima.decided_at
    await apply_forms(db_session, cucchiai, "cucchiaio", "cucchiai")

    esito = await realign_weights(db_session, [cucchiai.id])

    righe = await _righe(db_session, olio)
    assert [(r.unit_id, r.grams, r.decided_by, r.decided_at) for r in righe] == [
        (cucchiaio.id, Decimal("12.00"), "ai", decisa)
    ]
    assert (esito.moved, esito.merged, esito.dropped, esito.total) == (1, 0, 0, 1)
    assert [(p.ingredient_name, p.unit_label) for p in await pending_pairs(db_session)
            if p.ingredient_name == "olio di oliva"] == []


@pytest.mark.parametrize(
    ("sulla_forma", "sulla_canonica", "resta"),
    [("human", "ai", "forma"), ("ai", "human", "canonica"), ("ai", "ai", "canonica"),
     ("human", "human", "canonica")],
)
async def test_fondendo_vince_il_peso_a_mano(db_session, sulla_forma, sulla_canonica, resta):
    voci, cucchiai, cucchiaio = await _forma_su(db_session, "cucchiaio")
    olio = voci["olio di oliva"]
    await _riga(db_session, olio, cucchiai.id, "10", sulla_forma)
    await _riga(db_session, olio, cucchiaio.id, "20", sulla_canonica)
    await apply_forms(db_session, cucchiai, "cucchiaio", "cucchiai")

    esito = await realign_weights(db_session, [cucchiai.id])

    righe = await _righe(db_session, olio)
    atteso = (Decimal("10.00"), sulla_forma) if resta == "forma" else (Decimal("20.00"), sulla_canonica)
    assert [(r.unit_id, r.grams, r.decided_by) for r in righe] == [(cucchiaio.id, *atteso)]
    assert esito.merged == 1 and esito.moved == 0


async def test_un_peso_su_un_unita_diventata_di_massa_si_toglie(db_session):
    voci, cucchiai, _ = await _forma_su(db_session, "grammo")
    olio = voci["olio di oliva"]
    await _riga(db_session, olio, cucchiai.id, "10", "ai")
    await apply_forms(db_session, cucchiai, "grammo", "cucchiai")

    esito = await realign_weights(db_session, [cucchiai.id])

    assert await _righe(db_session, olio) == []
    assert esito.dropped == 1


async def test_un_peso_su_un_unita_diventata_pezzo_va_sul_pezzo(db_session):
    voci, cucchiai, _ = await _forma_su(db_session, "pezzo")
    olio = voci["olio di oliva"]
    await _riga(db_session, olio, cucchiai.id, "10", "human")
    await apply_forms(db_session, cucchiai, "pezzo", "cucchiai")

    esito = await realign_weights(db_session, [cucchiai.id])

    assert [(r.unit_id, r.grams, r.decided_by) for r in await _righe(db_session, olio)] == [
        (None, Decimal("10.00"), "human")
    ]
    assert esito.moved == 1


async def test_senza_unita_ricontrolla_tutto_e_non_tocca_le_righe_a_posto(db_session):
    voci, cucchiai, cucchiaio = await _forma_su(db_session, "cucchiaio")
    olio = voci["olio di oliva"]
    await _riga(db_session, olio, cucchiaio.id, "20", "ai")
    await _riga(db_session, voci["uova"], None, "50", "ai")

    assert (await realign_weights(db_session)).total == 0
