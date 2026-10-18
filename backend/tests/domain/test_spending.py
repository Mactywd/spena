"""Le spese dell'AI (H1), la parte pura: i periodi, i giorni di Roma, la quota, i nomi.

Un giorno qui è un giorno di calendario a Roma, come la scadenza (`PANTRY_TZ`): chi apre
l'app a mezzanotte e mezza ha speso «oggi», anche se in UTC è ancora ieri. Le funzioni
prendono «oggi» come argomento, e per questo si provano su date scritte a mano.
"""

from datetime import UTC, date, datetime

import pytest

from app.domain.spending import (
    CALL_SITE_LABELS,
    SpendingPeriod,
    call_site_label,
    daily_series,
    day_start,
    money,
    period_days,
    share,
)
from app.services.llm import LlmCallSite

OGGI = date(2026, 10, 13)


@pytest.mark.parametrize(
    ("oggi", "primo"),
    [(date(2026, 10, 13), date(2026, 10, 1)), (date(2026, 10, 1), date(2026, 10, 1))],
)
def test_il_mese_va_dal_primo_a_oggi(oggi, primo):
    assert period_days(SpendingPeriod.MONTH, oggi, None) == (primo, oggi)


def test_gli_ultimi_30_giorni_finiscono_oggi_e_sono_trenta():
    primo, ultimo = period_days(SpendingPeriod.LAST_30_DAYS, OGGI, None)
    assert (primo, ultimo) == (date(2026, 9, 14), OGGI)
    assert (ultimo - primo).days + 1 == 30


def test_da_sempre_parte_dal_giorno_della_prima_chiamata():
    assert period_days(SpendingPeriod.ALL, OGGI, date(2026, 9, 17)) == (date(2026, 9, 17), OGGI)


def test_da_sempre_senza_chiamate_e_solo_oggi():
    assert period_days(SpendingPeriod.ALL, OGGI, None) == (OGGI, OGGI)


def test_da_sempre_con_una_chiamata_datata_domani_parte_da_oggi():
    """Un orologio avanti non deve dare un periodo che finisce prima di cominciare."""
    assert period_days(SpendingPeriod.ALL, OGGI, date(2026, 10, 14)) == (OGGI, OGGI)


@pytest.mark.parametrize(
    ("giorno", "istante"),
    [
        # ora legale: Roma è a UTC+2
        (date(2026, 10, 1), datetime(2026, 9, 30, 22, 0, tzinfo=UTC)),
        # il giorno dopo il ritorno all'ora solare (25 ottobre): UTC+1
        (date(2026, 10, 26), datetime(2026, 10, 25, 23, 0, tzinfo=UTC)),
        # il giorno del passaggio all'ora legale comincia ancora in ora solare
        (date(2026, 3, 29), datetime(2026, 3, 28, 23, 0, tzinfo=UTC)),
    ],
)
def test_un_giorno_comincia_a_mezzanotte_a_roma(giorno, istante):
    assert day_start(giorno) == istante


def test_i_giorni_senza_spesa_valgono_zero():
    serie = daily_series(
        date(2026, 9, 29),
        date(2026, 10, 2),
        # un giorno fuori dal periodo non entra
        {date(2026, 9, 30): 0.5, date(2026, 10, 5): 9.0},
    )
    assert serie == [
        (date(2026, 9, 29), 0.0),
        (date(2026, 9, 30), 0.5),
        (date(2026, 10, 1), 0.0),
        (date(2026, 10, 2), 0.0),
    ]


@pytest.mark.parametrize(
    ("parte", "totale", "quota"), [(0.004, 0.025, 0.16), (0.0, 0.025, 0.0), (0.01, 0.0, 0.0)]
)
def test_la_quota_del_totale(parte, totale, quota):
    assert share(parte, totale) == quota


def test_le_somme_di_float_non_arrivano_a_video_coi_loro_resti():
    assert money(0.1 + 0.2) == 0.3
    assert money(0.000123456789) == 0.00012346


def test_ogni_sezione_del_client_llm_ha_un_nome_a_video():
    """La settima sezione non deve arrivare a video come `snake_case`.

    `LlmCallSite` vuole la sezione senza default proprio perché un tracciamento che
    finisce in «altro» smette di servire; un nome a video che manca sarebbe la stessa
    cosa, un piano più in là.
    """
    senza = [site.value for site in LlmCallSite if call_site_label(site.value) == site.value]
    assert not senza, (
        f"{senza}: sezioni di LlmCallSite senza un nome in CALL_SITE_LABELS "
        "(backend/app/domain/spending.py)"
    )


@pytest.mark.parametrize(
    ("call_site", "nome"),
    [("ingredient_emoji", "Figure della dispensa"), ("recipe_variant", "Varianti con l'AI")],
)
def test_le_sezioni_che_arrivano_stanotte_hanno_gia_il_nome(call_site, nome):
    """S12 e R8 aggiungono le loro sezioni su altri rami: il nome c'è già, così al merge
    nessuna delle due passa per una sezione sconosciuta."""
    assert CALL_SITE_LABELS[call_site] == nome


def test_una_sezione_sconosciuta_si_mostra_col_suo_nome():
    assert call_site_label("sezione_di_un_altro_ramo") == "sezione_di_un_altro_ramo"
