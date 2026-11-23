"""Le due rotte dell'AI che aspettano la risposta hanno una location di Nginx sopra la
loro scadenza: senza, Nginx le taglierebbe a 60 s con un 504."""

import re
from pathlib import Path

from app.core.config import Settings

NGINX = Path(__file__).resolve().parents[2] / "frontend" / "nginx.conf"


def _blocco():
    blocco = re.search(
        r"location ~ (?P<regex>\^/api/v1/\(imports/terms/decide\|[^\s]+) \{(?P<corpo>[^}]*)\}",
        NGINX.read_text(),
    )
    assert blocco, "manca la location delle rotte sincrone dell'AI in frontend/nginx.conf"
    return blocco


def test_la_location_sta_sopra_la_scadenza():
    corpo = _blocco()["corpo"]
    scadenza = Settings(_env_file=None).llm_sync_deadline_seconds
    for direttiva in ("proxy_read_timeout", "proxy_send_timeout"):
        tempo = re.search(rf"{direttiva} (\d+)s;", corpo)
        assert tempo, f"manca {direttiva}"
        assert int(tempo[1]) > scadenza
    assert "proxy_pass http://spena-backend:8000;" in corpo


def test_la_regex_prende_le_due_rotte_e_non_la_decisione_a_mano():
    regex = re.compile(_blocco()["regex"])
    uid = "0b0e7c1e-5d6f-4a9b-9c1d-2e3f4a5b6c7d"
    assert regex.match("/api/v1/imports/terms/decide")
    assert regex.match(f"/api/v1/recipes/{uid}/substitutes/{uid}/ask")
    assert not regex.match(f"/api/v1/imports/terms/{uid}/decision")
    assert not regex.match(f"/api/v1/recipes/{uid}/substitutes")
