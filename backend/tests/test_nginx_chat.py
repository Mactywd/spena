"""Nginx non trattiene la risposta di Claude: la chat dei piatti è SSE, e senza
`proxy_buffering off` arriverebbe tutta insieme alla fine (Pasti, piano 3, Task 7)."""

import re
from pathlib import Path

from app.core.config import Settings

NGINX = Path(__file__).resolve().parents[2] / "frontend" / "nginx.conf"


def test_nginx_non_trattiene_la_risposta_di_claude():
    blocco = re.search(
        r"location ~ \^/api/v1/meals/\[\^/\]\+/chat/messages\$ \{(?P<corpo>[^}]*)\}",
        NGINX.read_text(),
    )
    assert blocco, "manca la location della chat dei piatti in frontend/nginx.conf"
    corpo = blocco["corpo"]
    assert "proxy_buffering off;" in corpo
    assert "proxy_pass http://backend:8000;" in corpo
    attesa = re.search(r"proxy_read_timeout (\d+)s;", corpo)
    assert attesa, "la location non alza proxy_read_timeout"
    assert int(attesa[1]) > Settings(_env_file=None).claude_reply_timeout_seconds
