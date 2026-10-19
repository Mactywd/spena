"""La tabella CIQUAL nel database: scriverla, cercarla, trovarci i candidati (S4, fetta 1)."""

from sqlalchemy import select

from app.db.models.nutrition import CiqualFood
from app.domain.ciqual import CiqualRow
from app.repositories.ciqual import (
    count_foods,
    count_missing_from,
    find_candidates,
    search_foods,
    upsert_foods,
)

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
