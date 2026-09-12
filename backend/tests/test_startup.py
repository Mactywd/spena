"""I controlli di configurazione all'avvio, provati attraverso l'avvio vero.

Perché un file a parte e perché `TestClient`: la fixture `client` della suite guida
l'applicazione con `ASGITransport`, che non esegue gli eventi di lifespan. Un test
che chiamasse direttamente la funzione di controllo dimostrerebbe solo che la
funzione funziona, non che sia agganciata all'avvio — ed è esattamente così che un
controllo scollegato passa inosservato. `with TestClient(app):` esegue il lifespan,
quindi qui si rompe davvero ciò che si dice di provare.
"""

import re

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import (
    InsecureSessionSecret,
    UnusablePasswordHash,
    hash_password,
)

# Come Compose tratta un valore di `.env` quando `env_file` non ha `format: raw`:
# ogni `$nome` è un riferimento a una variabile inesistente e sparisce. Il nome
# segue la regola delle shell, quindi inizia per lettera o underscore — per questo
# un segmento dell'hash che comincia con una cifra a volte sopravvive, e il numero
# di caratteri persi cambia con il sale, da un hash all'altro: il README racconta
# 97 caratteri arrivati come 62, una misurazione di questo test ne contava 82.
RIFERIMENTO_A_VARIABILE = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*")


def come_lo_tronca_compose(hashed: str) -> str:
    return RIFERIMENTO_A_VARIABILE.sub("", hashed)


def test_lavvio_rifiuta_un_segreto_di_sessione_inutilizzabile(monkeypatch):
    from app.main import app

    get_settings.cache_clear()
    monkeypatch.setenv("SESSION_SECRET", "")
    try:
        with pytest.raises(InsecureSessionSecret):
            with TestClient(app):
                pass
    finally:
        get_settings.cache_clear()


def test_lavvio_riesce_con_un_segreto_configurato(monkeypatch):
    """L'altra metà: il controllo deve lasciar partire un server configurato bene.

    Senza questa, un controllo che rifiuta sempre passerebbe il test di sopra.
    """
    from app.main import app

    get_settings.cache_clear()
    monkeypatch.setenv("SESSION_SECRET", "segreto-di-test")
    try:
        with TestClient(app) as booted:
            assert booted.get("/api/v1/health").status_code == 200
    finally:
        get_settings.cache_clear()


def test_lavvio_rifiuta_lhash_troncato_da_compose(monkeypatch):
    """Il caso vero, non un hash inventato: un hash valido tagliato come taglia Compose.

    È il guasto che questo cancello esiste per fermare, e in produzione non ha
    sintomi: `verify_password` non distingue un hash illeggibile da una password
    sbagliata, quindi senza questo controllo l'unica traccia sarebbe «password
    errata» per sempre.
    """
    from app.main import app

    troncato = come_lo_tronca_compose(hash_password("la-password-di-questo-test"))
    assert not troncato.startswith("$argon2id"), "il troncamento deve essere avvenuto"

    get_settings.cache_clear()
    monkeypatch.setenv("SESSION_SECRET", "segreto-di-test")
    monkeypatch.setenv("APP_PASSWORD_HASH", troncato)
    try:
        with pytest.raises(UnusablePasswordHash) as rifiuto:
            with TestClient(app):
                pass
        # Il messaggio è l'unica cosa che chi fa il deploy vedrà: deve nominare la
        # causa, non solo constatare che l'hash non va.
        assert "format: raw" in str(rifiuto.value)
    finally:
        get_settings.cache_clear()


def test_lavvio_riesce_con_un_hash_valido(monkeypatch):
    """L'altra metà del cancello: un hash buono deve passare.

    Senza questa, un controllo che rifiuta qualunque hash passerebbe il test di sopra
    e l'applicazione non partirebbe più nemmeno configurata bene.
    """
    from app.main import app

    get_settings.cache_clear()
    monkeypatch.setenv("SESSION_SECRET", "segreto-di-test")
    monkeypatch.setenv("APP_PASSWORD_HASH", hash_password("la-password-di-questo-test"))
    try:
        with TestClient(app) as booted:
            assert booted.get("/api/v1/health").status_code == 200
    finally:
        get_settings.cache_clear()


def test_lavvio_riesce_con_lhash_assente(monkeypatch):
    """Un `.env` non ancora riempito non è una configurazione rotta.

    Deliberato: qui il login risponde già 401 a chiunque e lo dice (vedi
    tests/api/test_auth.py::test_login_without_configured_password_is_401), quindi
    non c'è nessun vicolo cieco da fermare all'avvio. È anche il caso in cui si
    generano i due valori da mettere in `.env`, con `docker compose run`.
    """
    from app.main import app

    get_settings.cache_clear()
    monkeypatch.setenv("SESSION_SECRET", "segreto-di-test")
    monkeypatch.setenv("APP_PASSWORD_HASH", "")
    try:
        with TestClient(app) as booted:
            assert booted.get("/api/v1/health").status_code == 200
    finally:
        get_settings.cache_clear()
