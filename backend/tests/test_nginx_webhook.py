"""Nginx lascia arrivare al backend i corpi del webhook di H2 oltre il limite del backend.

Il limite di default di Nginx è 1 MB, e un suo 413 non arriva mai al backend: HC Webhook
lo scriverebbe nel suo registro, e in «Attività» non si vedrebbe niente. Con 4 MB sulla
sola rotta del webhook il rifiuto oltre i 2 MB lo dà il backend, che lo registra e lo
mostra (spec H2 §3.1, 4). Un `location` tolto «per pulizia» lo riporterebbe muto.
"""

import re
from pathlib import Path

from app.domain.activity import WEBHOOK_MAX_BYTES

NGINX = Path(__file__).resolve().parents[2] / "frontend" / "nginx.conf"


def test_nginx_porta_al_backend_i_corpi_oltre_il_limite_del_webhook():
    blocco = re.search(
        r"location = /api/v1/activity/hc-webhook \{(?P<corpo>[^}]*)\}", NGINX.read_text()
    )
    assert blocco, "manca la location del webhook in frontend/nginx.conf"
    misura = re.search(r"client_max_body_size (\d+)m;", blocco["corpo"])
    assert misura, "la location del webhook non alza client_max_body_size"
    assert int(misura[1]) * 1024 * 1024 > WEBHOOK_MAX_BYTES
    assert "proxy_pass http://backend:8000;" in blocco["corpo"]
