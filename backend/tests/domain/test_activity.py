"""H2, la parte pura: leggere il corpo di HC Webhook e tenere un totale dei passi al giorno.

I corpi qui sono scritti a mano sul formato di `docs/webhook.md` di HC Webhook (letto il
2026-10-13). Gli istanti sono in UTC come li manda l'app; i giorni sono quelli di Roma.
"""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.domain import activity
from app.domain.activity import (
    STEPS_NOT_DAILY,
    Exercise,
    StepsDay,
    Weight,
    exercise_label,
    hc_type_label,
    merge_steps_day,
    parse_instant,
    parse_payload,
    rome_clock,
    rome_day,
    source_label,
)

SAMSUNG = {
    "data_origin": "com.sec.android.app.shealth",
    "recording_method": "automatically_recorded",
}


def utc(*parti: int) -> datetime:
    return datetime(*parti, tzinfo=UTC)


def passi(conta, inizio: str, fine: str, **altro) -> dict:
    return {"count": conta, "start_time": inizio, "end_time": fine, **altro}


@pytest.mark.parametrize(
    ("testo", "istante"),
    [
        ("2026-10-12T07:30:00Z", utc(2026, 10, 12, 7, 30)),
        ("2026-10-12T07:30:00.123Z", utc(2026, 10, 12, 7, 30, 0, 123000)),
        # `Instant.toString()` di Android arriva ai nanosecondi: Python ne tiene sei
        ("2026-10-12T07:30:00.123456789Z", utc(2026, 10, 12, 7, 30, 0, 123456)),
        ("2026-10-12T09:30:00+02:00", utc(2026, 10, 12, 7, 30)),
    ],
)
def test_un_istante_di_hc_webhook_si_legge(testo, istante):
    assert parse_instant(testo) == istante


@pytest.mark.parametrize(
    "valore",
    [
        None,
        1760254200,
        "",
        "ieri",
        "2026-10-12T07:30:00",  # senza fuso: non si sa quando
        "1970-01-01T00:00:00Z",  # prima del 2000: un orologio a zero, non un dato
        "2026-10-12T07:30:00Z" + " " * 30,  # troppo lungo per essere un istante
    ],
)
def test_un_istante_illeggibile_non_si_legge(valore):
    assert parse_instant(valore) is None


@pytest.mark.parametrize(
    ("istante", "giorno"),
    [
        (utc(2026, 10, 12, 22, 30), date(2026, 10, 13)),  # 00:30 a Roma, ora legale
        (utc(2026, 10, 12, 21, 30), date(2026, 10, 12)),  # 23:30 a Roma
        (utc(2026, 1, 15, 23, 30), date(2026, 1, 16)),  # 00:30 a Roma, ora solare
    ],
)
def test_il_giorno_e_quello_di_roma(istante, giorno):
    assert rome_day(istante) == giorno


def test_l_ora_e_quella_di_roma():
    assert rome_clock(utc(2026, 10, 12, 16, 5)) == "18:05"


GIORNO = date(2026, 10, 12)
MEZZANOTTE = utc(2026, 10, 11, 22)  # la mezzanotte del 12 a Roma
ORE_8 = MEZZANOTTE + timedelta(hours=8)
ORE_14 = MEZZANOTTE + timedelta(hours=14)
FINE = MEZZANOTTE + timedelta(days=1)


def totale(conta: int, dalle: datetime, alle: datetime) -> StepsDay:
    return StepsDay(day=GIORNO, steps=conta, covered_from=dalle, covered_to=alle)


@pytest.mark.parametrize(
    ("tenuto", "arrivato", "atteso"),
    [
        # niente di tenuto: si tiene quel che arriva
        (None, totale(800, MEZZANOTTE, ORE_8), totale(800, MEZZANOTTE, ORE_8)),
        # dalla mezzanotte a più tardi: copre di più, sostituisce
        (
            totale(800, MEZZANOTTE, ORE_8),
            totale(5000, MEZZANOTTE, ORE_14),
            totale(5000, MEZZANOTTE, ORE_14),
        ),
        # lo stesso intervallo, più basso: è una correzione, sostituisce
        (
            totale(5000, MEZZANOTTE, ORE_14),
            totale(4800, MEZZANOTTE, ORE_14),
            totale(4800, MEZZANOTTE, ORE_14),
        ),
        # un pezzo già contato (arriva tardi un invio vecchio): si ignora
        (
            totale(9000, MEZZANOTTE, FINE),
            totale(5000, MEZZANOTTE, ORE_14),
            totale(9000, MEZZANOTTE, FINE),
        ),
        # dopo un buco di più di un giorno: due pezzi sovrapposti, resta il più alto
        (totale(5000, MEZZANOTTE, ORE_14), totale(7000, ORE_8, FINE), totale(7000, ORE_8, FINE)),
        (
            totale(5000, MEZZANOTTE, ORE_14),
            totale(3000, ORE_8, FINE),
            totale(5000, MEZZANOTTE, ORE_14),
        ),
    ],
)
def test_un_giorno_ha_un_totale_solo_mai_una_somma(tenuto, arrivato, atteso):
    assert merge_steps_day(tenuto, arrivato) == atteso


def test_i_passi_giornalieri_si_leggono_un_giorno_per_uno():
    corpo = {
        "timestamp": "2026-10-12T12:00:00.500Z",
        "app_version": "2.4.0",
        "steps": [
            # il giorno prima, intero: dalla mezzanotte alla mezzanotte di Roma
            passi(9876, "2026-10-10T22:00:00Z", "2026-10-11T22:00:00Z"),
            # oggi, da mezzanotte ad adesso: la fine porta i millesimi
            passi(4321, "2026-10-11T22:00:00Z", "2026-10-12T12:00:00.123Z"),
        ],
    }

    letto = parse_payload(corpo)

    assert letto.problems == []
    assert [(giorno.day, giorno.steps) for giorno in letto.steps_days] == [
        (date(2026, 10, 11), 9876),
        (date(2026, 10, 12), 4321),
    ]
    assert letto.app_version == "2.4.0"
    assert letto.sent_at == utc(2026, 10, 12, 12, 0, 0, 500000)
    assert letto.is_test is False


def test_i_passi_a_finestre_di_minuti_non_si_salvano():
    """«15 min» somma gli intervalli grezzi di tutte le app: i doppioni di telefono e
    orologio tornerebbero. Si dice come rimediare, e non si salva niente."""
    corpo = {
        "steps": [
            passi(120, "2026-10-12T06:00:00Z", "2026-10-12T06:15:00Z"),
            passi(340, "2026-10-12T06:15:00Z", "2026-10-12T06:30:00Z"),
        ]
    }

    letto = parse_payload(corpo)

    assert letto.steps_days == []
    assert letto.problems == [STEPS_NOT_DAILY]


def test_i_passi_grezzi_con_l_origine_non_si_salvano():
    corpo = {
        "steps": [
            passi(4321, "2026-10-11T22:00:00Z", "2026-10-12T12:00:00.123Z", metadata=SAMSUNG)
        ]
    }

    letto = parse_payload(corpo)

    assert letto.steps_days == []
    assert letto.problems == [STEPS_NOT_DAILY]


def test_due_totali_dello_stesso_giorno_nello_stesso_corpo_non_si_sommano():
    corpo = {
        "steps": [
            passi(5000, "2026-10-11T22:00:00Z", "2026-10-12T12:00:00.100Z"),
            passi(7000, "2026-10-12T06:00:00.200Z", "2026-10-12T22:00:00Z"),
        ]
    }

    letto = parse_payload(corpo)

    assert [(giorno.day, giorno.steps) for giorno in letto.steps_days] == [
        (date(2026, 10, 12), 7000)
    ]


def test_le_voci_illeggibili_si_scartano_e_si_contano_le_altre_restano():
    corpo = {
        "steps": [
            passi(4321, "2026-10-11T22:00:00Z", "2026-10-12T12:00:00.123Z"),
            passi("tanti", "2026-10-10T22:00:00Z", "2026-10-11T22:00:00Z"),
            passi(True, "2026-10-09T22:00:00Z", "2026-10-10T22:00:00Z"),
            passi(-1, "2026-10-08T22:00:00Z", "2026-10-09T22:00:00Z"),
            # finisce prima di cominciare
            passi(100, "2026-10-08T22:00:00Z", "2026-10-07T22:00:00Z"),
            "non un oggetto",
        ]
    }

    letto = parse_payload(corpo)

    assert [giorno.steps for giorno in letto.steps_days] == [4321]
    assert letto.problems == ["Passi: 5 voci illeggibili, scartate."]


def test_una_voce_illeggibile_si_dice_al_singolare():
    corpo = {"weight": [{"kilograms": 72.4, "time": "2026-10-12T05:30:00Z"}, {"kilograms": 72.4}]}

    letto = parse_payload(corpo)

    assert len(letto.weights) == 1
    assert letto.problems == ["Pesate: 1 voce illeggibile, scartata."]


def test_un_tipo_che_non_e_un_elenco_si_salta():
    corpo = {
        "exercise": {"type": "56"},
        "weight": [{"kilograms": 72.4, "time": "2026-10-12T05:30:00Z"}],
    }

    letto = parse_payload(corpo)

    assert letto.exercises == []
    assert len(letto.weights) == 1
    assert letto.problems == ["Allenamenti: non è un elenco, non letto."]


def test_oltre_le_voci_massime_si_leggono_le_prime(monkeypatch):
    monkeypatch.setattr(activity, "MAX_RECORDS", 3)
    pesate = [{"kilograms": 70 + i, "time": f"2026-10-0{i + 1}T05:30:00Z"} for i in range(5)]

    letto = parse_payload({"weight": pesate})

    assert [pesata.kilograms for pesata in letto.weights] == [70.0, 71.0, 72.0]
    assert letto.problems == ["Pesate: 5 voci, lette le prime 3."]


def test_un_allenamento_si_legge_con_tutto_quel_che_porta():
    corpo = {
        "exercise": [
            {
                "type": "56",
                "title": "Giro del parco",
                "start_time": "2026-10-12T16:00:00Z",
                "end_time": "2026-10-12T16:32:00Z",
                "duration_seconds": 1920,
                "distance_meters": 5100.5,
                "steps": 5400,
                "avg_cadence_spm": 168.2,
                "metadata": SAMSUNG,
            }
        ]
    }

    letto = parse_payload(corpo)

    assert letto.problems == []
    assert letto.exercises == [
        Exercise(
            source="com.sec.android.app.shealth",
            started_at=utc(2026, 10, 12, 16),
            ended_at=utc(2026, 10, 12, 16, 32),
            exercise_type=56,
            title="Giro del parco",
            distance_m=5100.5,
            steps=5400,
        )
    ]
    assert letto.exercises[0].day == date(2026, 10, 12)


def test_un_allenamento_con_campi_nuovi_o_mancanti_si_salva_lo_stesso():
    corpo = {
        "exercise": [
            {
                "type": "EXERCISE_TYPE_DEL_FUTURO",
                # durata zero: certi orologi lo fanno
                "start_time": "2026-10-12T16:00:00Z",
                "end_time": "2026-10-12T16:00:00Z",
                "distance_meters": "lontano",
                "steps": -3,
                "campo_nuovo": {"a": 1},
            }
        ]
    }

    letto = parse_payload(corpo)

    assert letto.problems == []
    (allenamento,) = letto.exercises
    assert (allenamento.source, allenamento.exercise_type, allenamento.title) == ("", None, None)
    assert (allenamento.distance_m, allenamento.steps) == (None, None)


def test_un_allenamento_senza_tempi_sensati_si_scarta():
    corpo = {
        "exercise": [
            {"type": "56", "start_time": "2026-10-12T16:00:00Z", "end_time": "2026-10-12T15:00:00Z"},
            # più di 48 ore
            {"type": "56", "start_time": "2026-10-10T16:00:00Z", "end_time": "2026-10-12T17:00:00Z"},
            {"type": "56", "start_time": "2026-10-12T16:00:00Z"},
        ]
    }

    letto = parse_payload(corpo)

    assert letto.exercises == []
    assert letto.problems == ["Allenamenti: 3 voci illeggibili, scartate."]


def test_lo_stesso_allenamento_due_volte_nello_stesso_corpo_e_uno():
    voce = {
        "type": "79",
        "start_time": "2026-10-12T16:00:00Z",
        "end_time": "2026-10-12T16:20:00Z",
        "metadata": SAMSUNG,
    }
    piu_lungo = {**voce, "end_time": "2026-10-12T16:25:00Z"}

    letto = parse_payload({"exercise": [voce, piu_lungo]})

    assert [allenamento.ended_at for allenamento in letto.exercises] == [utc(2026, 10, 12, 16, 25)]


def test_le_pesate_si_leggono_e_quelle_impossibili_si_scartano():
    corpo = {
        "weight": [
            {"kilograms": 72.4, "time": "2026-10-12T05:30:00Z", "metadata": SAMSUNG},
            {"kilograms": 1.0, "time": "2026-10-11T05:30:00Z"},
            {"kilograms": 500, "time": "2026-10-10T05:30:00Z"},
        ]
    }

    letto = parse_payload(corpo)

    assert letto.weights == [
        Weight(
            source="com.sec.android.app.shealth",
            measured_at=utc(2026, 10, 12, 5, 30),
            kilograms=72.4,
        )
    ]
    assert letto.weights[0].day == date(2026, 10, 12)
    assert letto.problems == ["Pesate: 2 voci illeggibili, scartate."]


def test_i_tipi_che_spena_non_usa_si_registrano_solo_per_nome():
    corpo = {
        "timestamp": "2026-10-12T12:00:00Z",
        "app_version": "2.4.0",
        "test": False,
        "sleep": [{"session_end_time": "2026-10-12T05:00:00Z"}],
        "heart_rate": [{"bpm": 70, "time": "2026-10-12T06:00:00Z"}],
        "x" * 60: [1],
    }

    letto = parse_payload(corpo)

    assert letto.ignored_keys == ["heart_rate", "sleep", "x" * 40]
    assert letto.problems == []


@pytest.mark.parametrize(
    ("valore", "prova"), [(True, True), ("true", False), (1, False), (None, False)]
)
def test_la_prova_di_hc_webhook_e_solo_test_true(valore, prova):
    assert parse_payload({"test": valore}).is_test is prova


def test_versione_e_istante_del_corpo_sono_facoltativi():
    letto = parse_payload({"timestamp": "ieri", "app_version": "v" * 100})

    assert letto.sent_at is None
    assert letto.app_version == "v" * 40
    assert letto.problems == []


def test_un_corpo_vuoto_va_bene():
    letto = parse_payload({})

    assert (letto.steps_days, letto.exercises, letto.weights) == ([], [], [])
    assert (letto.ignored_keys, letto.problems) == ([], [])


def test_numeri_impossibili_non_rompono_niente():
    corpo = {
        "steps": [
            passi(10**30, "2026-10-11T22:00:00Z", "2026-10-12T12:00:00.1Z"),
            passi(float("inf"), "2026-10-10T22:00:00Z", "2026-10-11T22:00:00Z"),
        ],
        "exercise": [
            {
                "type": 10**20,
                "start_time": "2026-10-12T16:00:00Z",
                "end_time": "2026-10-12T16:20:00Z",
                "distance_meters": 10**400,
            }
        ],
        "weight": [
            {"kilograms": float("nan"), "time": "2026-10-12T05:30:00Z"},
            {"kilograms": 10**400, "time": "2026-10-12T05:31:00Z"},
        ],
    }

    letto = parse_payload(corpo)

    assert (letto.steps_days, letto.weights) == ([], [])
    assert [(a.exercise_type, a.distance_m) for a in letto.exercises] == [(None, None)]
    assert letto.problems == [
        "Passi: 2 voci illeggibili, scartate.",
        "Pesate: 2 voci illeggibili, scartate.",
    ]


@pytest.mark.parametrize(
    ("tipo", "nome"),
    [
        (56, "Corsa"),
        (79, "Camminata"),
        (70, "Allenamento di forza"),
        (None, "Allenamento"),
        (9999, "Allenamento"),
    ],
)
def test_il_nome_di_un_allenamento(tipo, nome):
    assert exercise_label(tipo) == nome


@pytest.mark.parametrize(
    ("origine", "nome"),
    [
        ("com.sec.android.app.shealth", "Samsung Health"),
        ("", "origine non indicata"),
        ("com.esempio.app", "com.esempio.app"),
    ],
)
def test_il_nome_di_un_app(origine, nome):
    assert source_label(origine) == nome


@pytest.mark.parametrize(
    ("chiave", "nome"),
    [("heart_rate", "frequenza cardiaca"), ("tipo_del_futuro", "tipo_del_futuro")],
)
def test_il_nome_di_un_tipo_non_usato(chiave, nome):
    assert hc_type_label(chiave) == nome


# Postgres rifiuta `\u0000` nei testi e nei JSONB, e rifiuta anche una metà di coppia
# surrogata (`"\ud800"`, che `json.loads` accetta): scritta nel database sarebbe un 500, e
# un corpo inatteso non deve darlo mai. Una stringa così, per Spena, è come se mancasse.
@pytest.mark.parametrize("cattiva", ["\x00", "a\x00b", "\ud800", "ab\ud800cd"])
def test_i_testi_che_postgres_non_puo_salvare_si_trattano_come_assenti(cattiva):
    corpo = {
        "app_version": cattiva,
        "exercise": [
            {
                "type": "56",
                "title": cattiva,
                "start_time": "2026-10-12T16:00:00Z",
                "end_time": "2026-10-12T16:32:00Z",
                "metadata": {"data_origin": cattiva},
            }
        ],
        "weight": [{"kilograms": 72.4, "time": "2026-10-12T05:30:00Z", "metadata": SAMSUNG}],
        "heart_rate": [],
        cattiva: [1],
    }

    letto = parse_payload(corpo)

    assert letto.app_version is None
    (allenamento,) = letto.exercises
    assert (allenamento.source, allenamento.title) == ("", None)
    assert allenamento.exercise_type == 56
    assert [pesata.kilograms for pesata in letto.weights] == [72.4]
    assert letto.ignored_keys == ["heart_rate"]
    assert letto.problems == []
