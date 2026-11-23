"""La tabella CIQUAL nel database: scriverla, cercarla, trovarci i candidati (S4, fetta 1)."""

import re

import pytest
from ciqual_veri import ALIMENTI_VERI, tabella_vera
from sqlalchemy import select

from app.db.models.nutrition import CiqualFood
from app.domain.ciqual import CiqualRow, normalize_name
from app.repositories.ciqual import (
    _first_word,
    count_foods,
    count_missing_from,
    find_candidates,
    search_foods,
    upsert_foods,
)
from app.services.ciqual_match import CANDIDATES

ALIMENTI = [
    CiqualRow("90001", "Tomate, crue", "légumes", {"kcal": 18.0}),
    CiqualRow("90002", "Tomate, concentré", "légumes", {"kcal": 77.0}),
    CiqualRow("90007", "Basilic, frais", "herbes", {"kcal": 31.0}),
    CiqualRow("90011", "Riz blanc, cru", "pâtes, riz et céréales", {"kcal": 354.0}),
]


async def test_upsert_scrive_e_aggiorna_per_codice(db_session):
    assert await upsert_foods(db_session, ALIMENTI) == 4
    await upsert_foods(db_session, [CiqualRow("90001", "Tomate, crue (2027)", "légumes", {"kcal": 19.0})])

    assert await count_foods(db_session) == 4
    pomodoro = (
        await db_session.execute(
            select(CiqualFood).where(CiqualFood.code == "90001").execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert (pomodoro.name_fr, pomodoro.nutrients, pomodoro.version) == (
        "Tomate, crue (2027)", {"kcal": 19.0}, "2025",
    )


async def test_conta_gli_alimenti_che_il_file_non_ha_piu(db_session):
    await upsert_foods(db_session, ALIMENTI)

    assert await count_missing_from(db_session, {"90001", "90002"}) == 2
    assert await count_missing_from(db_session, {food.code for food in ALIMENTI}) == 0


async def test_i_candidati_vengono_dalla_somiglianza_col_nome_francese(db_session):
    await upsert_foods(db_session, ALIMENTI)

    candidati = await find_candidates(db_session, ["tomate crue"], limit=15)

    assert candidati[0].code == "90001"
    assert candidati[0].name_fr == "Tomate, crue" and candidati[0].group_fr == "légumes"
    assert "90011" not in {candidato.code for candidato in candidati}


async def test_i_candidati_di_piu_parole_si_uniscono_senza_doppioni_e_col_limite(db_session):
    await upsert_foods(db_session, ALIMENTI)

    tutti = await find_candidates(db_session, ["tomate crue", "riz blanc cru", "tomate"], limit=15)
    codici = [candidato.code for candidato in tutti]
    assert {"90001", "90011"} <= set(codici)
    assert len(codici) == len(set(codici))

    assert len(await find_candidates(db_session, ["tomate", "riz blanc"], limit=2)) == 2


async def test_sotto_la_soglia_nessun_candidato(db_session):
    await upsert_foods(db_session, ALIMENTI)

    assert await find_candidates(db_session, ["zzzz"], limit=15) == []


async def test_search_foods_per_codice_e_per_pezzo_di_nome(db_session):
    await upsert_foods(db_session, ALIMENTI)

    assert (await search_foods(db_session, "90007", limit=20))[0].name_fr == "Basilic, frais"
    trovati = await search_foods(db_session, "TOMATE", limit=20)
    assert {alimento.code for alimento in trovati[:2]} == {"90001", "90002"}


async def test_search_foods_non_usa_jolly(db_session):
    """«%» e «_» sono lettere, non jolly: altrimenti «%» elencherebbe tutta la tabella."""
    await upsert_foods(db_session, ALIMENTI)

    assert await search_foods(db_session, "%", limit=20) == []
    assert await search_foods(db_session, "_", limit=20) == []


async def test_search_foods_ignora_gli_accenti(db_session):
    await upsert_foods(
        db_session,
        [
            CiqualRow("90021", "Pâtes sèches, crues", "pâtes, riz et céréales", {"kcal": 350.0}),
            CiqualRow("90022", "Pâtes cuites", "pâtes, riz et céréales", {"kcal": 120.0}),
            *ALIMENTI,
        ],
    )

    assert (await search_foods(db_session, "pates seches", limit=20))[0].name_fr == "Pâtes sèches, crues"
    for scritto in ("PÂTES", "pâtes", "pates"):
        trovati = await search_foods(db_session, scritto, limit=20)
        assert {alimento.code for alimento in trovati[:2]} == {"90021", "90022"}
    assert await search_foods(db_session, "-", limit=20) == []
    assert await search_foods(db_session, "'", limit=20) == []


async def test_search_foods_a_parita_comincia_con_la_parola(db_session):
    await upsert_foods(db_session, ALIMENTI_VERI)

    assert (await search_foods(db_session, "riz", limit=20))[0].name_fr == "Riz blanc, cru"


async def test_search_foods_sulla_tabella_vera(db_session):
    assert await tabella_vera(db_session) == 3484

    riz = await search_foods(db_session, "riz", limit=20)
    assert all(a.name_fr.startswith("Riz") for a in riz[:5])
    assert "Riz blanc, cru" in [a.name_fr for a in riz[:3]]
    pates = await search_foods(db_session, "pates", limit=20)
    assert "Pâtes sèches, standard, crues" in [a.name_fr for a in pates[:3]]


def _codici(candidati):
    return [candidato.code for candidato in candidati]


async def test_a_parita_vince_il_nome_che_comincia_con_la_parola(db_session):
    """«riz» vale 1 con ogni nome che lo contiene: l'alfabeto metteva prima «Amidon de
    riz», «Boisson au riz», «Farine de riz», e il riso crudo restava fuori."""
    await upsert_foods(db_session, ALIMENTI_VERI)

    candidati = await find_candidates(db_session, ["riz"], limit=3)

    assert _codici(candidati) == ["9100", "9104", "39251"]


@pytest.mark.parametrize(
    ("parola", "limit", "attesi"),
    [
        ("saumon", 2, {"26036", "26229"}),
        ("sel", 2, {"11083", "11017"}),
        ("pomme de terre", 1, {"4008"}),
        ("tomate", 2, {"20358", "20385"}),
        ("thon", 2, {"26053", "26039"}),
    ],
)
async def test_il_cibo_semplice_prima_dei_piatti_che_lo_contengono(db_session, parola, limit, attesi):
    await upsert_foods(db_session, ALIMENTI_VERI)

    candidati = await find_candidates(db_session, [parola], limit=limit)

    assert set(_codici(candidati)) == attesi


async def test_le_parole_si_uniscono_con_lo_stesso_ordine(db_session):
    await upsert_foods(db_session, ALIMENTI_VERI)

    candidati = await find_candidates(db_session, ["riz", "sel"], limit=3)

    assert _codici(candidati) == ["9100", "9104", "39251"]


async def test_maiuscole_e_punteggiatura_non_cambiano_l_ordine(db_session):
    await upsert_foods(db_session, ALIMENTI_VERI)

    assert _codici(await find_candidates(db_session, ["RIZ"], limit=1)) == ["9100"]
    assert _codici(await find_candidates(db_session, ["Riz, cru"], limit=3)) == ["9100", "9104", "39251"]


def test_la_prima_parola_del_termine():
    assert _first_word("Riz, cru") == "riz"
    assert _first_word("pomme de terre") == "pomme"
    assert _first_word("huile d'olive") == "huile"
    assert _first_word("(riz)") == "riz"
    assert _first_word("  Épinard cru") == "épinard"
    assert _first_word("") == ""


# (espressione sul nome normalizzato, parole di ricerca): parole plausibili dell'AI per i
# casi che il pilota del 2026-10-20 ha mancato, e l'alimento che ciascun gruppo deve
# portare fra i candidati
GRUPPI_VERI = [
    ("^riz.*cru", ["riz"]), ("^riz.*cru", ["riz blanc cru", "riz"]), ("^riz.*cru", ["riz cru", "riz blanc"]),
    ("^saumon", ["saumon"]), ("^saumon", ["saumon cru", "saumon frais"]),
    ("^saumon", ["saumon atlantique cru", "filet de saumon"]),
    ("^thon.*(appertise|conserve)", ["thon"]), ("^thon.*(appertise|conserve)", ["thon en conserve", "thon au naturel"]),
    ("^thon.*(appertise|conserve)", ["thon en boîte", "thon appertisé"]),
    ("^thon.*(appertise|conserve)", ["thon à l'huile", "thon"]),
    ("^lentille", ["lentilles"]), ("^lentille", ["lentilles sèches", "lentilles vertes"]), ("^miel", ["miel"]),
    ("^tomate (sans precision|ronde), crue", ["tomate crue", "tomate"]),
    ("^tomate (sans precision|ronde), crue", ["tomate"]),
    ("^pomme de terre.*crue", ["pomme de terre crue", "pomme de terre"]), ("^pomme de terre.*crue", ["pomme de terre"]),
    ("^sucre blanc", ["sucre"]), ("^sucre blanc", ["sucre blanc", "sucre en poudre"]),
    ("^sel (blanc|marin|gris)", ["sel"]), ("^sel (blanc|marin|gris)", ["sel fin", "sel de table"]),
    ("^sel (blanc|marin|gris)", ["sel marin", "sel"]),
    ("^poulet, filet sans peau cru", ["blanc de poulet", "filet de poulet cru"]),
    ("^poulet, filet sans peau cru", ["poulet filet cru", "poulet"]),
]


async def test_la_tabella_vera_ha_l_alimento_fra_i_candidati(db_session):
    """Sulla tabella del 2025 intera, caricata per la strada di `load_ciqual`: ogni gruppo
    di parole porta il suo alimento fra i `CANDIDATES` che la scelta vede."""
    assert await tabella_vera(db_session) == 3484

    mancati = []
    for espressione, parole in GRUPPI_VERI:
        candidati = await find_candidates(db_session, parole, limit=CANDIDATES)
        if not any(re.search(espressione, normalize_name(c.name_fr)) for c in candidati):
            mancati.append((espressione, parole))

    assert mancati == []
