"""L'attività da Health Connect (H2): leggere il corpo di HC Webhook, senza database.

HC Webhook (https://github.com/mcnaveen/health-connect-webhook) legge Health Connect sul
telefono e manda a un indirizzo un oggetto JSON: `timestamp` e `app_version` sempre, poi
un elenco per ogni tipo che ha qualcosa di nuovo. Spena ne usa tre — `steps`, `exercise`,
`weight` (decisione di Mattia del 2026-10-13) — e degli altri registra solo il nome. Il
formato è quello di `docs/webhook.md` del progetto, letto il 2026-10-13; l'app può
aggiungere tipi e campi a ogni versione, e qui nessuna voce inattesa fa cadere le altre:
`parse_payload` non solleva mai, salva quel che capisce e dice in italiano cosa ha scartato.

Puro come `rules.py`: niente database, niente orologio. I giorni sono giorni di Roma
(`PANTRY_TZ`), come la scadenza.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.domain.rules import PANTRY_TZ

# L'intestazione che porta la chiave (spec H2 §3.1): un nome solo da incollare, senza il
# «Bearer » da scrivere a mano sul telefono.
TOKEN_HEADER = "X-Spena-Token"
# Oltre, il corpo si rifiuta. Spena coi suoi tre tipi riceve pochi kB; 2 MB servono a chi
# lascia attivi tutti i 31 tipi. Nginx ne lascia passare 4 (frontend/nginx.conf), così il
# rifiuto lo dà il backend, e si vede in «Attività».
WEBHOOK_MAX_BYTES = 2 * 1024 * 1024

# `timezone` e `deleted` sono involucro di HC Webhook dalla 1.9.23, non tipi di dato: il
# primo è in ogni corpo (anche nella prova), il secondo elenca i record cancellati in Health
# Connect. Non si possono spegnere nell'app, quindi non vanno mai tra le chiavi ignorate,
# che invitano a toglierle dal webhook.
ENVELOPE_KEYS = frozenset({"timestamp", "app_version", "test", "timezone", "deleted"})
USED_KEYS = frozenset({"steps", "exercise", "weight"})

MAX_RECORDS = 5000
MAX_DAY_STEPS = 200_000
# un giorno con il cambio dell'ora dura 25 ore; 26 lascia un margine al fuso del telefono
MAX_STEPS_SPAN = timedelta(hours=26)
# le finestre di HC Webhook sono di 1, 5 o 15 minuti; sotto l'ora, al minuto tondo, è una
# finestra e non un totale del giorno (vedi `_is_daily_total`)
BUCKET_SPAN = timedelta(minutes=60)
MAX_EXERCISE_SPAN = timedelta(hours=48)
MAX_EXERCISE_STEPS = 200_000
MAX_DISTANCE_M = 1_000_000.0
MIN_KG = 2.0
MAX_KG = 400.0
MAX_EXERCISE_TYPE = 10_000
MAX_SOURCE = 120
MAX_TITLE = 200
MAX_APP_VERSION = 40
MAX_KEY = 40
MAX_IGNORED_KEYS = 50
MAX_INSTANT_TEXT = 40

STEPS_LABEL = "Passi"
EXERCISES_LABEL = "Allenamenti"
WEIGHTS_LABEL = "Pesate"

STEPS_NOT_DAILY = (
    "Passi non salvati: arrivano a intervalli e non come totale del giorno. In HC Webhook, "
    "alla voce «Risoluzione passi», scegli «Giornaliero»."
)
TOO_BIG = (
    "Rifiutato: il corpo supera i 2 MB. Nel webhook di Spena, in HC Webhook, lascia solo "
    "Passi, Sessioni di esercizio e Peso."
)
NOT_JSON = "Rifiutato: il corpo non è JSON."
NOT_OBJECT = "Rifiutato: il corpo è JSON, ma non un oggetto."


def rome_day(instant: datetime) -> date:
    """Il giorno di calendario a Roma di un istante."""
    return instant.astimezone(PANTRY_TZ).date()


def rome_clock(instant: datetime) -> str:
    """L'ora a Roma, «18:05»: il frontend non sa di fusi."""
    return instant.astimezone(PANTRY_TZ).strftime("%H:%M")


@dataclass(frozen=True)
class StepsDay:
    """Il totale dei passi di un giorno di Roma, con l'intervallo che copre."""

    day: date
    steps: int
    covered_from: datetime
    covered_to: datetime


@dataclass(frozen=True)
class Exercise:
    # il `data_origin` di Health Connect, `""` se manca
    source: str
    started_at: datetime
    ended_at: datetime
    # la costante di Health Connect (56 è la corsa), `None` se illeggibile
    exercise_type: int | None
    title: str | None
    distance_m: float | None
    steps: int | None

    @property
    def day(self) -> date:
        return rome_day(self.started_at)


@dataclass(frozen=True)
class Weight:
    source: str
    measured_at: datetime
    kilograms: float

    @property
    def day(self) -> date:
        return rome_day(self.measured_at)


@dataclass(frozen=True)
class ParsedPayload:
    is_test: bool
    app_version: str | None
    sent_at: datetime | None
    steps_days: list[StepsDay]
    exercises: list[Exercise]
    weights: list[Weight]
    # i nomi delle chiavi del corpo che Spena non usa, ordinati
    ignored_keys: list[str]
    # in italiano, nell'ordine passi, allenamenti, pesate: si mostrano così in «Attività»
    problems: list[str]


def parse_instant(value: object) -> datetime | None:
    """Un istante ISO-8601 col fuso (`Instant.toString()`, fino ai nanosecondi), o `None`.

    Senza fuso non si sa quando; prima del 2000 o dopo il 2100 è un orologio sbagliato.
    """
    if not isinstance(value, str) or len(value) > MAX_INSTANT_TEXT:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None or not 2000 <= parsed.year <= 2100:
        return None
    return parsed


def _int(value: object) -> int | None:
    # `True` è un `int` per Python, e un conteggio per nessuno
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    return None


def _float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    try:
        number = float(value)
    except OverflowError:
        # un intero di quattrocento cifre: JSON lo permette, un float no
        return None
    return number if math.isfinite(number) else None


def _storable(text: str) -> bool:
    """Vero se Postgres può scrivere il testo nelle colonne di testo e nei JSONB.

    Rifiuta `\\u0000` e rifiuta una metà di coppia surrogata (`"\\ud800"`, che `json.loads`
    accetta): scritti nel database sarebbero un 500, e un corpo inatteso non lo dà mai.
    Ogni stringa del corpo che può arrivare al database passa di qui.
    """
    if "\x00" in text:
        return False
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _text(value: object, limit: int) -> str | None:
    # una stringa che Postgres non può salvare, per Spena, è come se mancasse
    if not isinstance(value, str) or not _storable(value):
        return None
    text = value.strip()
    return text[:limit] if text else None


def _records(raw: object, label: str, problems: list[str]) -> list[object]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        problems.append(f"{label}: non è un elenco, non letto.")
        return []
    if len(raw) > MAX_RECORDS:
        problems.append(f"{label}: {len(raw)} voci, lette le prime {MAX_RECORDS}.")
        return raw[:MAX_RECORDS]
    return raw


def _unreadable(label: str, count: int, problems: list[str]) -> None:
    if count == 1:
        problems.append(f"{label}: 1 voce illeggibile, scartata.")
    elif count > 1:
        problems.append(f"{label}: {count} voci illeggibili, scartate.")


def _source(record: Mapping) -> str:
    metadata = record.get("metadata")
    if not isinstance(metadata, Mapping):
        return ""
    return _text(metadata.get("data_origin"), MAX_SOURCE) or ""


def merge_steps_day(stored: StepsDay | None, incoming: StepsDay) -> StepsDay:
    """Il totale di un giorno, fra quello tenuto e uno nuovo dello stesso giorno: mai la somma.

    Un totale che copre almeno l'intervallo tenuto lo sostituisce, anche se più basso: è lo
    stesso giorno visto più tardi, o corretto. Uno che ci sta dentro è un pezzo già contato
    (un invio vecchio arrivato dopo). Due pezzi che si sovrappongono solo in parte — succede
    dopo un buco di più di un giorno fra due sincronizzazioni — sono due stime per difetto
    dello stesso giorno: resta la più alta, perché sommarle conterebbe due volte le ore in
    comune.
    """
    if stored is None:
        return incoming
    if incoming.covered_from <= stored.covered_from and incoming.covered_to >= stored.covered_to:
        return incoming
    if incoming.covered_from >= stored.covered_from and incoming.covered_to <= stored.covered_to:
        return stored
    return incoming if incoming.steps > stored.steps else stored


def _steps_reading(record: object) -> StepsDay | None:
    if not isinstance(record, Mapping):
        return None
    start = parse_instant(record.get("start_time"))
    end = parse_instant(record.get("end_time"))
    count = _int(record.get("count"))
    if start is None or end is None or count is None:
        return None
    if not start < end <= start + MAX_STEPS_SPAN or not 0 <= count <= MAX_DAY_STEPS:
        return None
    return StepsDay(day=rome_day(start), steps=count, covered_from=start, covered_to=end)


def _is_daily_total(record: object, reading: StepsDay) -> bool:
    """Vero se il record è un totale del giorno, la forma «Giornaliero» di HC Webhook.

    È l'unica calcolata con la lettura aggregata di Health Connect, che toglie i doppioni
    fra le app (spec H2 §3.2). «Completo» porta `metadata`, un record per app e intervallo;
    le finestre di 1, 5 o 15 minuti cominciano e finiscono al minuto tondo. Un totale del
    giorno o dura un giorno intero o finisce «adesso», coi millesimi.
    """
    if isinstance(record, Mapping) and "metadata" in record:
        return False
    on_the_minute = all(
        instant.second == 0 and instant.microsecond == 0
        for instant in (reading.covered_from, reading.covered_to)
    )
    return not (on_the_minute and reading.covered_to - reading.covered_from <= BUCKET_SPAN)


def _steps(raw: object, problems: list[str]) -> list[StepsDay]:
    by_day: dict[date, StepsDay] = {}
    unreadable = 0
    not_daily = 0
    for record in _records(raw, STEPS_LABEL, problems):
        reading = _steps_reading(record)
        if reading is None:
            unreadable += 1
            continue
        if not _is_daily_total(record, reading):
            not_daily += 1
            continue
        by_day[reading.day] = merge_steps_day(by_day.get(reading.day), reading)
    _unreadable(STEPS_LABEL, unreadable, problems)
    if not_daily:
        problems.append(STEPS_NOT_DAILY)
    return sorted(by_day.values(), key=lambda reading: reading.day)


def _exercise_type(value: object) -> int | None:
    # HC Webhook manda la costante come stringa («56»); un intero va bene lo stesso
    if isinstance(value, str):
        text = value.strip()
        number = int(text) if text.isascii() and text.isdigit() and len(text) <= 5 else None
    else:
        number = _int(value)
    return number if number is not None and 0 <= number <= MAX_EXERCISE_TYPE else None


def _exercise(record: object) -> Exercise | None:
    if not isinstance(record, Mapping):
        return None
    start = parse_instant(record.get("start_time"))
    end = parse_instant(record.get("end_time"))
    # durata zero sì: certi orologi scrivono sessioni così
    if start is None or end is None or not start <= end <= start + MAX_EXERCISE_SPAN:
        return None
    distance = _float(record.get("distance_meters"))
    if distance is not None and not 0 <= distance <= MAX_DISTANCE_M:
        distance = None
    steps = _int(record.get("steps"))
    if steps is not None and not 0 <= steps <= MAX_EXERCISE_STEPS:
        steps = None
    return Exercise(
        source=_source(record),
        started_at=start,
        ended_at=end,
        exercise_type=_exercise_type(record.get("type")),
        title=_text(record.get("title"), MAX_TITLE),
        distance_m=distance,
        steps=steps,
    )


def _exercises(raw: object, problems: list[str]) -> list[Exercise]:
    # lo stesso allenamento due volte nello stesso corpo: vale l'ultimo
    found: dict[tuple[str, datetime], Exercise] = {}
    unreadable = 0
    for record in _records(raw, EXERCISES_LABEL, problems):
        exercise = _exercise(record)
        if exercise is None:
            unreadable += 1
            continue
        found[(exercise.source, exercise.started_at)] = exercise
    _unreadable(EXERCISES_LABEL, unreadable, problems)
    return sorted(found.values(), key=lambda exercise: (exercise.started_at, exercise.source))


def _weight(record: object) -> Weight | None:
    if not isinstance(record, Mapping):
        return None
    measured_at = parse_instant(record.get("time"))
    kilograms = _float(record.get("kilograms"))
    if measured_at is None or kilograms is None or not MIN_KG <= kilograms <= MAX_KG:
        return None
    return Weight(source=_source(record), measured_at=measured_at, kilograms=kilograms)


def _weights(raw: object, problems: list[str]) -> list[Weight]:
    found: dict[tuple[str, datetime], Weight] = {}
    unreadable = 0
    for record in _records(raw, WEIGHTS_LABEL, problems):
        weight = _weight(record)
        if weight is None:
            unreadable += 1
            continue
        found[(weight.source, weight.measured_at)] = weight
    _unreadable(WEIGHTS_LABEL, unreadable, problems)
    return sorted(found.values(), key=lambda weight: (weight.measured_at, weight.source))


def parse_payload(body: Mapping[str, object]) -> ParsedPayload:
    """Quel che Spena capisce di un corpo di HC Webhook. Non solleva mai."""
    problems: list[str] = []
    steps_days = _steps(body.get("steps"), problems)
    exercises = _exercises(body.get("exercise"), problems)
    weights = _weights(body.get("weight"), problems)
    ignored = sorted(
        {
            str(key)[:MAX_KEY]
            for key in body
            if key not in ENVELOPE_KEYS | USED_KEYS and _storable(str(key))
        }
    )
    return ParsedPayload(
        # solo `true`: la prova di HC Webhook lo scrive così, e una stringa «true» no
        is_test=body.get("test") is True,
        app_version=_text(body.get("app_version"), MAX_APP_VERSION),
        sent_at=parse_instant(body.get("timestamp")),
        steps_days=steps_days,
        exercises=exercises,
        weights=weights,
        ignored_keys=ignored[:MAX_IGNORED_KEYS],
        problems=problems,
    )


# I nomi a video degli allenamenti, per costante di Health Connect
# (androidx.health.connect.client.records.ExerciseSessionRecord, letta il 2026-10-13).
EXERCISE_LABELS: dict[int, str] = {
    0: "Allenamento",
    2: "Badminton",
    4: "Baseball",
    5: "Pallacanestro",
    8: "Bicicletta",
    9: "Cyclette",
    10: "Boot camp",
    11: "Pugilato",
    13: "Calistenia",
    14: "Cricket",
    16: "Ballo",
    25: "Ellittica",
    26: "Lezione di gruppo",
    27: "Scherma",
    28: "Football americano",
    29: "Football australiano",
    31: "Frisbee",
    32: "Golf",
    33: "Respirazione guidata",
    34: "Ginnastica",
    35: "Pallamano",
    36: "Allenamento a intervalli",
    37: "Escursionismo",
    38: "Hockey su ghiaccio",
    39: "Pattinaggio su ghiaccio",
    44: "Arti marziali",
    46: "Canoa e kayak",
    47: "Parapendio",
    48: "Pilates",
    50: "Racquetball",
    51: "Arrampicata",
    52: "Hockey su rotelle",
    53: "Canottaggio",
    54: "Vogatore",
    55: "Rugby",
    56: "Corsa",
    57: "Tapis roulant",
    58: "Vela",
    59: "Immersione",
    60: "Pattinaggio",
    61: "Sci",
    62: "Snowboard",
    63: "Ciaspole",
    64: "Calcio",
    65: "Softball",
    66: "Squash",
    68: "Scale",
    69: "Stepper",
    70: "Allenamento di forza",
    71: "Stretching",
    72: "Surf",
    73: "Nuoto in acque libere",
    74: "Nuoto in piscina",
    75: "Ping pong",
    76: "Tennis",
    78: "Pallavolo",
    79: "Camminata",
    80: "Pallanuoto",
    81: "Sollevamento pesi",
    82: "Sedia a rotelle",
    83: "Yoga",
}
DEFAULT_EXERCISE_LABEL = "Allenamento"


def exercise_label(exercise_type: int | None) -> str:
    if exercise_type is None:
        return DEFAULT_EXERCISE_LABEL
    return EXERCISE_LABELS.get(exercise_type, DEFAULT_EXERCISE_LABEL)


SOURCE_LABELS: dict[str, str] = {
    "com.sec.android.app.shealth": "Samsung Health",
    "com.google.android.apps.fitness": "Google Fit",
    "com.google.android.apps.healthdata": "Health Connect",
    "com.strava": "Strava",
    "com.fitbit.FitbitMobile": "Fitbit",
}
UNKNOWN_SOURCE_LABEL = "origine non indicata"


def source_label(source: str) -> str:
    if not source:
        return UNKNOWN_SOURCE_LABEL
    return SOURCE_LABELS.get(source, source)


# I tipi di HC Webhook che Spena non usa, col loro nome per la riga «Arrivati e non usati».
HC_TYPE_LABELS: dict[str, str] = {
    "sleep": "sonno",
    "heart_rate": "frequenza cardiaca",
    "heart_rate_variability": "variabilità del battito",
    "distance": "distanza",
    "active_calories": "calorie attive",
    "total_calories": "calorie totali",
    "height": "altezza",
    "blood_pressure": "pressione",
    "blood_glucose": "glicemia",
    "oxygen_saturation": "ossigenazione",
    "body_temperature": "temperatura corporea",
    "skin_temperature": "temperatura della pelle",
    "respiratory_rate": "frequenza respiratoria",
    "resting_heart_rate": "battito a riposo",
    "hydration": "idratazione",
    "nutrition": "alimentazione",
    "basal_metabolic_rate": "metabolismo basale",
    "body_fat": "massa grassa",
    "lean_body_mass": "massa magra",
    "body_water_mass": "acqua corporea",
    "vo2_max": "VO₂ max",
    "bone_mass": "massa ossea",
    "menstruation_flow": "flusso mestruale",
    "menstruation_period": "ciclo mestruale",
    "intermenstrual_bleeding": "perdite intermestruali",
    "ovulation_test": "test di ovulazione",
    "cervical_mucus": "muco cervicale",
    "sexual_activity": "attività sessuale",
    "basal_body_temperature": "temperatura basale",
}


def hc_type_label(key: str) -> str:
    return HC_TYPE_LABELS.get(key, key)
