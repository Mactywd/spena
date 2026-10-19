"""Le risposte di «Attività» (H2): `GET /api/v1/activity` e `POST /api/v1/activity/token`.

Tutto quel che è dominio arriva già deciso: i giorni e le ore di Roma, i nomi a video, se
la sincronizzazione è vecchia. Il frontend scrive «Oggi», i numeri all'italiana, e disegna.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel


class SyncOut(BaseModel):
    # il giorno e l'ora di Roma in cui è arrivata
    day: date
    time: str
    status: Literal["ok", "test", "rejected"]
    # più di 24 ore fa: in «Attività» compare l'avviso sulla batteria
    stale: bool
    steps_days: int
    exercises: int
    weights: int
    # i nomi a video dei tipi arrivati e non usati
    ignored: list[str]
    problems: list[str]


class StepsDayOut(BaseModel):
    day: date
    # `None`: nessun totale arrivato per quel giorno, che non è zero passi
    steps: int | None


class ExerciseOut(BaseModel):
    day: date
    time: str
    label: str
    title: str | None
    minutes: int
    distance_km: float | None
    # il nome a video dell'app che l'ha scritto
    source: str


class WeightOut(BaseModel):
    day: date
    time: str
    kilograms: float


class ConnectionOut(BaseModel):
    has_token: bool
    created_day: date | None
    created_time: str | None
    last_used_day: date | None
    last_used_time: str | None


class ActivityOut(BaseModel):
    today: date
    last_sync: SyncOut | None
    # gli ultimi 7 giorni di Roma, oggi per primo
    steps_days: list[StepsDayOut]
    # degli ultimi 7 giorni, dal più recente, al più 20
    exercises: list[ExerciseOut]
    # le ultime 5, dalla più recente
    weights: list[WeightOut]
    connection: ConnectionOut


class TokenOut(BaseModel):
    # si vede solo qui, una volta: il database ne tiene l'impronta
    token: str
    header: str
