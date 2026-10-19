"""H2: «Attività» — cosa è arrivato da Health Connect, e la chiave del webhook.

Il riepilogo si prova sul servizio con «adesso» scritto a mano (il 13 ottobre 2026 alle
12:00 UTC, le 14:00 a Roma); le rotte con l'orologio vero, dove il risultato non dipende
da che ora è.
"""

from datetime import UTC, date, datetime, time, timedelta

import pytest

from app.db.models.activity import ActivityExercise, ActivityStepsDay, ActivityWeight
from app.domain.activity import rome_day
from app.domain.rules import PANTRY_TZ, today_in_pantry
from app.repositories.activity import record_sync
from app.services.activity import activity_summary

ADESSO = datetime(2026, 10, 13, 12, tzinfo=UTC)
OGGI = date(2026, 10, 13)
SAMSUNG = "com.sec.android.app.shealth"
WEBHOOK = "/api/v1/activity/hc-webhook"


def utc(*parti: int) -> datetime:
    return datetime(*parti, tzinfo=UTC)


def passi_del_giorno(giorno: date, passi: int) -> ActivityStepsDay:
    inizio = datetime.combine(giorno, time.min, tzinfo=PANTRY_TZ)
    return ActivityStepsDay(
        day=giorno, steps=passi, covered_from=inizio, covered_to=inizio + timedelta(hours=10)
    )


def allenamento(inizio: datetime, minuti: int, tipo: int | None = 56, **altro) -> ActivityExercise:
    return ActivityExercise(
        source=SAMSUNG,
        started_at=inizio,
        ended_at=inizio + timedelta(minutes=minuti),
        day=rome_day(inizio),
        exercise_type=tipo,
        **altro,
    )


def pesata(istante: datetime, chili: float) -> ActivityWeight:
    return ActivityWeight(source=SAMSUNG, measured_at=istante, day=rome_day(istante), kilograms=chili)


async def test_le_rotte_della_schermata_vogliono_la_sessione(client):
    assert (await client.get("/api/v1/activity")).status_code == 401
    assert (await client.post("/api/v1/activity/token")).status_code == 401


async def test_mai_sincronizzato(db_session):
    riepilogo = await activity_summary(db_session, ADESSO)

    assert riepilogo.today == OGGI
    assert riepilogo.last_sync is None
    assert [giorno.day for giorno in riepilogo.steps_days] == [
        OGGI - timedelta(days=giorni) for giorni in range(7)
    ]
    assert all(giorno.steps is None for giorno in riepilogo.steps_days)
    assert (riepilogo.exercises, riepilogo.weights) == ([], [])
    assert riepilogo.connection.has_token is False
    assert riepilogo.connection.created_day is None


async def test_i_passi_degli_ultimi_sette_giorni_oggi_per_primo(db_session):
    db_session.add_all(
        [
            passi_del_giorno(OGGI, 4321),
            passi_del_giorno(OGGI - timedelta(days=2), 9876),
            # otto giorni fa: fuori
            passi_del_giorno(OGGI - timedelta(days=7), 5555),
        ]
    )
    await db_session.flush()

    riepilogo = await activity_summary(db_session, ADESSO)

    assert [giorno.steps for giorno in riepilogo.steps_days] == [
        4321, None, 9876, None, None, None, None
    ]


async def test_gli_allenamenti_degli_ultimi_sette_giorni_dal_piu_recente(db_session):
    db_session.add_all(
        [
            allenamento(utc(2026, 10, 10, 7), 45, tipo=None),
            allenamento(
                utc(2026, 10, 13, 16), 32, title="Giro del parco", distance_m=5100.0, steps=5400
            ),
            # nove giorni fa: fuori
            allenamento(utc(2026, 10, 4, 7), 30),
        ]
    )
    await db_session.flush()

    riepilogo = await activity_summary(db_session, ADESSO)

    assert [e.model_dump() for e in riepilogo.exercises] == [
        {
            "day": OGGI,
            "time": "18:00",
            "label": "Corsa",
            "title": "Giro del parco",
            "minutes": 32,
            "distance_km": 5.1,
            "source": "Samsung Health",
        },
        {
            "day": date(2026, 10, 10),
            "time": "09:00",
            "label": "Allenamento",
            "title": None,
            "minutes": 45,
            "distance_km": None,
            "source": "Samsung Health",
        },
    ]


async def test_una_distanza_che_arrotonda_a_zero_non_e_zero_virgola_zero_km(db_session):
    db_session.add(allenamento(utc(2026, 10, 13, 7), 20, distance_m=30.0))
    await db_session.flush()

    riepilogo = await activity_summary(db_session, ADESSO)

    assert [e.distance_km for e in riepilogo.exercises] == [None]


async def test_le_ultime_cinque_pesate(db_session):
    db_session.add_all(
        [pesata(utc(2026, 10, giorno, 5, 30), 70 + giorno / 10) for giorno in range(1, 7)]
    )
    await db_session.flush()

    riepilogo = await activity_summary(db_session, ADESSO)

    assert [(p.day, p.time, p.kilograms) for p in riepilogo.weights] == [
        (date(2026, 10, 6), "07:30", 70.6),
        (date(2026, 10, 5), "07:30", 70.5),
        (date(2026, 10, 4), "07:30", 70.4),
        (date(2026, 10, 3), "07:30", 70.3),
        (date(2026, 10, 2), "07:30", 70.2),
    ]


@pytest.mark.parametrize(("ore_fa", "vecchia"), [(1, False), (25, True)])
async def test_l_ultima_sincronizzazione_coi_nomi_e_se_e_vecchia(db_session, ore_fa, vecchia):
    await record_sync(
        db_session,
        status="ok",
        received_at=ADESSO - timedelta(hours=ore_fa + 48),
        body_bytes=10,
    )
    await record_sync(
        db_session,
        status="ok",
        received_at=ADESSO - timedelta(hours=ore_fa),
        body_bytes=812,
        steps_days=1,
        exercises=2,
        weights=0,
        ignored_keys=["heart_rate", "tipo_del_futuro"],
        problems=["Pesate: 1 voce illeggibile, scartata."],
    )

    sync = (await activity_summary(db_session, ADESSO)).last_sync

    assert sync is not None
    assert (sync.day, sync.status, sync.stale) == (
        rome_day(ADESSO - timedelta(hours=ore_fa)),
        "ok",
        vecchia,
    )
    assert (sync.steps_days, sync.exercises, sync.weights) == (1, 2, 0)
    assert sync.ignored == ["frequenza cardiaca", "tipo_del_futuro"]
    assert sync.problems == ["Pesate: 1 voce illeggibile, scartata."]


async def test_la_chiave_si_crea_si_usa_e_si_rigenera(logged_client):
    creata = await logged_client.post("/api/v1/activity/token")
    assert creata.status_code == 201
    prima = creata.json()
    assert prima["header"] == "X-Spena-Token"
    assert len(prima["token"]) == 43

    collegamento = (await logged_client.get("/api/v1/activity")).json()["connection"]
    assert collegamento["has_token"] is True
    assert collegamento["created_day"] == today_in_pantry().isoformat()
    assert collegamento["last_used_day"] is None

    usata = await logged_client.post(WEBHOOK, json={}, headers={"X-Spena-Token": prima["token"]})
    assert usata.status_code == 200
    collegamento = (await logged_client.get("/api/v1/activity")).json()["connection"]
    assert collegamento["last_used_day"] == today_in_pantry().isoformat()

    seconda = (await logged_client.post("/api/v1/activity/token")).json()
    assert seconda["token"] != prima["token"]
    vecchia = await logged_client.post(WEBHOOK, json={}, headers={"X-Spena-Token": prima["token"]})
    assert vecchia.status_code == 401
    nuova = await logged_client.post(WEBHOOK, json={}, headers={"X-Spena-Token": seconda["token"]})
    assert nuova.status_code == 200


async def test_la_chiave_non_si_rilegge_dal_riepilogo(logged_client):
    chiave = (await logged_client.post("/api/v1/activity/token")).json()["token"]

    risposta = await logged_client.get("/api/v1/activity")

    assert chiave not in risposta.text


async def test_la_rotta_risponde_coi_giorni_di_roma(logged_client):
    corpo = (await logged_client.get("/api/v1/activity")).json()

    assert corpo["today"] == today_in_pantry().isoformat()
    assert len(corpo["steps_days"]) == 7
    assert corpo["last_sync"] is None
