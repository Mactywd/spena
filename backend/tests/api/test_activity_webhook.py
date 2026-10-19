"""H2: il webhook di HC Webhook — la chiave, i limiti, e quel che si salva.

La rotta sta fuori dalla sessione: la apre solo la chiave in `X-Spena-Token`. Le chiavi qui
si scrivono nel database con `save_token`, come farà `POST /api/v1/activity/token` (Task 4).
I corpi seguono `docs/webhook.md` di HC Webhook (letto il 2026-10-13).
"""

import json
from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.core.webhook_token import new_token, token_hash
from app.db.models.activity import (
    ActivityExercise,
    ActivityStepsDay,
    ActivitySync,
    ActivityToken,
    ActivityWeight,
)
from app.domain.activity import NOT_JSON, NOT_OBJECT, STEPS_NOT_DAILY, TOO_BIG, WEBHOOK_MAX_BYTES
from app.repositories import activity as activity_repo
from app.repositories.activity import save_token

WEBHOOK = "/api/v1/activity/hc-webhook"
SAMSUNG = {
    "data_origin": "com.sec.android.app.shealth",
    "recording_method": "automatically_recorded",
}

CORPO = {
    "timestamp": "2026-10-12T12:00:00.500Z",
    # dalla 1.9.23 HC Webhook lo mette in ogni corpo
    "timezone": "Europe/Rome",
    "app_version": "2.4.0",
    "steps": [
        {"count": 4321, "start_time": "2026-10-11T22:00:00Z", "end_time": "2026-10-12T12:00:00.123Z"}
    ],
    "exercise": [
        {
            "type": "56",
            "start_time": "2026-10-12T06:00:00Z",
            "end_time": "2026-10-12T06:30:00Z",
            "duration_seconds": 1800,
            "distance_meters": 5200.0,
            "metadata": SAMSUNG,
        }
    ],
    "weight": [{"kilograms": 72.4, "time": "2026-10-12T05:30:00Z", "metadata": SAMSUNG}],
}


@pytest_asyncio.fixture
async def chiave(db_session) -> str:
    token = new_token()
    await save_token(db_session, token_hash(token), datetime(2026, 10, 12, 8, tzinfo=UTC))
    return token


async def conta(db_session, modello) -> int:
    return await db_session.scalar(select(func.count()).select_from(modello))


async def manda(client, chiave: str | None, corpo=CORPO):
    intestazioni = {} if chiave is None else {"X-Spena-Token": chiave}
    return await client.post(WEBHOOK, json=corpo, headers=intestazioni)


async def test_senza_chiave_401_vuoto_e_niente_scritto(client, chiave, db_session):
    risposta = await manda(client, None)

    assert (risposta.status_code, risposta.content) == (401, b"")
    assert await conta(db_session, ActivitySync) == 0
    assert await conta(db_session, ActivityStepsDay) == 0


@pytest.mark.parametrize("sbagliata", ["x" * 43, "corta", "inventata"])
async def test_una_chiave_sbagliata_e_lo_stesso_401(client, chiave, db_session, sbagliata):
    risposta = await manda(client, sbagliata)

    assert (risposta.status_code, risposta.content) == (401, b"")
    assert await conta(db_session, ActivitySync) == 0
    assert (await db_session.get(ActivityToken, 1)).last_used_at is None


async def test_senza_una_chiave_configurata_niente_passa(client, db_session):
    risposta = await manda(client, new_token())

    assert (risposta.status_code, risposta.content) == (401, b"")
    assert await conta(db_session, ActivitySync) == 0


async def test_la_sessione_dell_app_non_basta(logged_client, chiave):
    risposta = await manda(logged_client, None)

    assert risposta.status_code == 401


async def test_il_corpo_giusto_salva_passi_allenamenti_e_pesate(client, chiave, db_session):
    risposta = await manda(client, chiave)

    assert risposta.status_code == 200
    assert risposta.json() == {
        "test": False,
        "saved": {"steps_days": 1, "exercises": 1, "weights": 1},
        "ignored": [],
        "problems": [],
    }
    giorno = await db_session.get(ActivityStepsDay, date(2026, 10, 12))
    assert giorno.steps == 4321
    allenamento = await db_session.scalar(select(ActivityExercise))
    assert (
        allenamento.source,
        allenamento.exercise_type,
        allenamento.distance_m,
        allenamento.day,
    ) == ("com.sec.android.app.shealth", 56, 5200.0, date(2026, 10, 12))
    pesata = await db_session.scalar(select(ActivityWeight))
    assert (pesata.kilograms, pesata.day) == (72.4, date(2026, 10, 12))
    sync = await db_session.scalar(select(ActivitySync))
    assert (sync.status, sync.app_version, sync.steps_days, sync.exercises, sync.weights) == (
        "ok",
        "2.4.0",
        1,
        1,
        1,
    )
    assert sync.sent_at == datetime(2026, 10, 12, 12, 0, 0, 500000, tzinfo=UTC)
    assert sync.body_bytes > 0
    assert (await db_session.get(ActivityToken, 1)).last_used_at is not None


async def test_lo_stesso_corpo_due_volte_non_duplica_niente(client, chiave, db_session):
    for _ in range(2):
        assert (await manda(client, chiave)).status_code == 200

    assert await conta(db_session, ActivityStepsDay) == 1
    assert await conta(db_session, ActivityExercise) == 1
    assert await conta(db_session, ActivityWeight) == 1
    assert await conta(db_session, ActivitySync) == 2


async def test_il_totale_del_giorno_cresce_e_un_invio_vecchio_non_lo_abbassa(
    client, chiave, db_session
):
    def corpo(passi: int, fine: str) -> dict:
        return {"steps": [{"count": passi, "start_time": "2026-10-11T22:00:00Z", "end_time": fine}]}

    await manda(client, chiave, corpo(4321, "2026-10-12T12:00:00.123Z"))
    await manda(client, chiave, corpo(6500, "2026-10-12T15:00:00.456Z"))
    # un tentativo ripetuto dell'invio di prima arriva dopo: è un pezzo già contato
    await manda(client, chiave, corpo(4321, "2026-10-12T12:00:00.123Z"))

    giorno = await db_session.get(ActivityStepsDay, date(2026, 10, 12))
    await db_session.refresh(giorno)
    assert giorno.steps == 6500
    assert giorno.covered_to == datetime(2026, 10, 12, 15, 0, 0, 456000, tzinfo=UTC)


async def test_un_allenamento_rimandato_aggiorna_la_sua_riga(client, chiave, db_session):
    await manda(client, chiave)
    allungato = {
        "exercise": [
            {**CORPO["exercise"][0], "end_time": "2026-10-12T06:45:00Z", "title": "Giro lungo"}
        ]
    }

    await manda(client, chiave, allungato)

    righe = (await db_session.scalars(select(ActivityExercise))).all()
    assert len(righe) == 1
    await db_session.refresh(righe[0])
    assert (righe[0].ended_at, righe[0].title) == (
        datetime(2026, 10, 12, 6, 45, tzinfo=UTC),
        "Giro lungo",
    )


async def test_la_prova_di_hc_webhook_non_salva_niente(client, chiave, db_session):
    corpo = {**CORPO, "test": True, "heart_rate": [{"bpm": 70, "time": "2026-10-12T06:00:00Z"}]}

    risposta = await manda(client, chiave, corpo)

    assert risposta.status_code == 200
    assert risposta.json() == {
        "test": True,
        "saved": {"steps_days": 0, "exercises": 0, "weights": 0},
        "ignored": ["heart_rate"],
        "problems": [],
    }
    assert await conta(db_session, ActivityStepsDay) == 0
    assert await conta(db_session, ActivityExercise) == 0
    sync = await db_session.scalar(select(ActivitySync))
    assert (sync.status, sync.ignored_keys) == ("test", ["heart_rate"])


async def test_un_corpo_troppo_grosso_si_rifiuta_e_si_registra(client, chiave, db_session):
    grosso = json.dumps({**CORPO, "imbottitura": "x" * (WEBHOOK_MAX_BYTES + 1)})

    risposta = await client.post(
        WEBHOOK,
        content=grosso,
        headers={"X-Spena-Token": chiave, "Content-Type": "application/json"},
    )

    assert risposta.status_code == 413
    assert risposta.json() == {"detail": TOO_BIG}
    assert await conta(db_session, ActivityStepsDay) == 0
    sync = await db_session.scalar(select(ActivitySync))
    assert (sync.status, sync.problems) == ("rejected", [TOO_BIG])


async def test_una_lunghezza_dichiarata_assurda_non_e_un_500(client, chiave, db_session):
    # più di 4300 cifre: `int()` solleverebbe. L'intestazione si ignora e il corpo si legge
    # a pezzi come se non ci fosse.
    risposta = await client.post(
        WEBHOOK,
        content=json.dumps(CORPO),
        headers={"X-Spena-Token": chiave, "Content-Length": "9" * 5000},
    )

    assert risposta.status_code == 200
    assert await conta(db_session, ActivityStepsDay) == 1


async def test_anche_senza_lunghezza_dichiarata_il_corpo_si_ferma_al_limite(
    client, chiave, db_session
):
    async def a_pezzi():
        for _ in range(3):
            yield b"x" * (WEBHOOK_MAX_BYTES // 2)

    risposta = await client.post(WEBHOOK, content=a_pezzi(), headers={"X-Spena-Token": chiave})

    assert risposta.status_code == 413
    sync = await db_session.scalar(select(ActivitySync))
    assert sync.problems == [TOO_BIG]


@pytest.mark.parametrize(
    ("corpo", "problema"),
    [
        (b"non json", NOT_JSON),
        (b"\xff\xfe\x00", NOT_JSON),  # byte che non sono testo
        (b"[" * 100_000, NOT_JSON),  # annidato a fondo: in Python è un RecursionError
        (b"[1, 2]", NOT_OBJECT),
        (b'"una stringa"', NOT_OBJECT),
    ],
)
async def test_un_corpo_che_non_e_un_oggetto_json_e_400_registrato(
    client, chiave, db_session, corpo, problema
):
    risposta = await client.post(WEBHOOK, content=corpo, headers={"X-Spena-Token": chiave})

    assert risposta.status_code == 400
    assert risposta.json() == {"detail": problema}
    sync = await db_session.scalar(select(ActivitySync))
    assert (sync.status, sync.problems) == ("rejected", [problema])


async def test_voci_illeggibili_e_tipi_nuovi_non_fermano_il_resto(client, chiave, db_session):
    corpo = {
        **CORPO,
        "steps": [*CORPO["steps"], {"count": "tanti", "start_time": "x", "end_time": "y"}],
        "weight": "non un elenco",
        "tipo_del_futuro": [{"a": 1}],
    }

    risposta = await manda(client, chiave, corpo)

    assert risposta.status_code == 200
    corpo_risposta = risposta.json()
    assert corpo_risposta["saved"] == {"steps_days": 1, "exercises": 1, "weights": 0}
    assert corpo_risposta["ignored"] == ["tipo_del_futuro"]
    assert corpo_risposta["problems"] == [
        "Passi: 1 voce illeggibile, scartata.",
        "Pesate: non è un elenco, non letto.",
    ]
    sync = await db_session.scalar(select(ActivitySync))
    assert (sync.status, sync.ignored_keys, sync.problems) == (
        "ok",
        ["tipo_del_futuro"],
        corpo_risposta["problems"],
    )


async def test_i_passi_a_finestre_non_si_salvano_e_si_dice_perche(client, chiave, db_session):
    corpo = {
        "steps": [
            {"count": 120, "start_time": "2026-10-12T06:00:00Z", "end_time": "2026-10-12T06:15:00Z"}
        ]
    }

    risposta = await manda(client, chiave, corpo)

    assert risposta.json()["problems"] == [STEPS_NOT_DAILY]
    assert await conta(db_session, ActivityStepsDay) == 0


async def test_il_registro_tiene_solo_le_ultime_sincronizzazioni(
    client, chiave, db_session, monkeypatch
):
    monkeypatch.setattr(activity_repo, "SYNCS_KEPT", 3)

    for _ in range(5):
        assert (await manda(client, chiave, {"timestamp": "2026-10-12T12:00:00Z"})).status_code == 200

    assert await conta(db_session, ActivitySync) == 3


async def test_stringhe_che_postgres_non_scrive_non_fanno_un_500(client, chiave, db_session):
    # a mano, come testo JSON: gli escape `\u0000` e `\ud800` devono arrivare a `json.loads`
    # (con `json=` li manderebbe `json.dumps` già in forma di escape, ma qui il corpo si
    # legge byte per byte, come dal telefono)
    corpo = (
        b'{"app_version": "2.4.0\\u0000", "chiave\\u0000strana": [1],'
        b' "chiave\\ud800rotta": [2],'
        b' "steps": [{"count": 4321, "start_time": "2026-10-11T22:00:00Z",'
        b' "end_time": "2026-10-12T12:00:00Z"}],'
        b' "exercise": [{"type": "56", "start_time": "2026-10-12T06:00:00Z",'
        b' "end_time": "2026-10-12T06:30:00Z", "title": "Giro\\ud800",'
        b' "metadata": {"data_origin": "com.sec\\u0000.shealth"}}],'
        b' "weight": [{"kilograms": 72.4, "time": "2026-10-12T05:30:00Z"}]}'
    )

    risposta = await client.post(WEBHOOK, content=corpo, headers={"X-Spena-Token": chiave})

    assert risposta.status_code == 200
    assert risposta.json()["ignored"] == []
    giorno = await db_session.get(ActivityStepsDay, date(2026, 10, 12))
    assert giorno.steps == 4321
    pesata = await db_session.scalar(select(ActivityWeight))
    assert pesata.kilograms == 72.4
    sync = await db_session.scalar(select(ActivitySync))
    assert (sync.status, sync.app_version, sync.ignored_keys) == ("ok", None, [])
