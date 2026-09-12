"""Il controllo del segreto all'avvio, provato attraverso l'avvio vero.

Perché un file a parte e perché `TestClient`: la fixture `client` della suite guida
l'applicazione con `ASGITransport`, che non esegue gli eventi di lifespan. Un test
che chiamasse direttamente la funzione di controllo dimostrerebbe solo che la
funzione funziona, non che sia agganciata all'avvio — ed è esattamente così che un
controllo scollegato passa inosservato. `with TestClient(app):` esegue il lifespan,
quindi qui si rompe davvero ciò che si dice di provare.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import InsecureSessionSecret


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
