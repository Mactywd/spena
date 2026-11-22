"""Nginx non trattiene la risposta di Claude: la chat dei piatti e quella della
pianificazione sono SSE, e senza `proxy_buffering off` arriverebbero tutte insieme alla
fine (Pasti, piano 3, Task 7; piano 6c, Task 9)."""

import re
from pathlib import Path

from app.core.config import Settings

NGINX = Path(__file__).resolve().parents[2] / "frontend" / "nginx.conf"


def test_nginx_non_trattiene_la_risposta_di_claude():
    # la location copre anche la pianificazione (piano 6c, Task 9): la regex è cambiata
    blocco = re.search(
        r"location ~ \^/api/v1/\(meals/\[\^/\]\+/chat\|planning/conversations/\[\^/\]\+\)"
        r"/messages\$ \{(?P<corpo>[^}]*)\}",
        NGINX.read_text(),
    )
    assert blocco, "manca la location delle chat in frontend/nginx.conf"
    corpo = blocco["corpo"]
    assert "proxy_buffering off;" in corpo
    assert "proxy_pass http://spena-backend:8000;" in corpo
    attesa = re.search(r"proxy_read_timeout (\d+)s;", corpo)
    assert attesa, "la location non alza proxy_read_timeout"
    assert int(attesa[1]) > Settings(_env_file=None).claude_reply_timeout_seconds


def test_nginx_non_trattiene_la_pianificazione():
    """La stessa `location` copre i due stream: la sua regex accetta il percorso dei
    messaggi della pianificazione e quello della chat del piatto, e nient'altro."""
    blocco = re.search(r"location ~ (?P<regex>\S+) \{(?P<corpo>[^}]*)\}", _stream_location())
    assert blocco
    regex = re.compile(blocco["regex"])
    uid = "0b0e7c1e-5d6f-4a9b-9c1d-2e3f4a5b6c7d"
    assert regex.match(f"/api/v1/planning/conversations/{uid}/messages")
    assert regex.match(f"/api/v1/meals/{uid}/chat/messages")
    assert not regex.match(f"/api/v1/planning/conversations/{uid}")
    assert not regex.match(f"/api/v1/planning/proposals/{uid}/place")
    assert not regex.match(f"/api/v1/meals/{uid}/chat")
    assert "proxy_buffering off;" in blocco["corpo"]


def _stream_location() -> str:
    """La `location` che ha `proxy_buffering off`: ce n'è una sola."""
    blocchi = [
        b for b in re.findall(r"location [^{]*\{[^}]*\}", NGINX.read_text())
        if "proxy_buffering off;" in b
    ]
    assert len(blocchi) == 1, blocchi
    return blocchi[0]
