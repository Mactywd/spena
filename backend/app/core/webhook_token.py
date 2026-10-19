"""La chiave del webhook di HC Webhook (H2): creata qui, conservata come impronta.

Non è la sessione dell'app: HC Webhook non ha il cookie, e una chiave sua si rigenera
senza toccare la password. 32 byte casuali (43 caratteri) non si indovinano: per questo
l'impronta è un SHA-256 semplice, e non un hash lento come quello della password, che una
persona sceglie e qualcuno può indovinare.
"""

import hashlib
import hmac
import secrets
import string

TOKEN_BYTES = 32
# `token_urlsafe(32)`: 32 byte in base64 per URL, senza `=`
TOKEN_LENGTH = 43
_ALPHABET = frozenset(string.ascii_letters + string.digits + "-_")
# Senza una chiave configurata si confronta lo stesso, con questa: il tempo della risposta
# non deve dire se una chiave c'è.
_NO_TOKEN_HASH = hashlib.sha256(b"spena: nessuna chiave configurata").hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def looks_like_token(candidate: str) -> bool:
    """La forma di una chiave: si controlla prima di toccare il database."""
    return len(candidate) == TOKEN_LENGTH and set(candidate) <= _ALPHABET


def token_matches(candidate: str, stored_hash: str | None) -> bool:
    """Il confronto a tempo costante fra le impronte (`hmac.compare_digest`)."""
    expected = stored_hash if stored_hash is not None else _NO_TOKEN_HASH
    same = hmac.compare_digest(token_hash(candidate), expected)
    return same and stored_hash is not None
