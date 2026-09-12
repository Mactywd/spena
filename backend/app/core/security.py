from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import HTTPException, Request, Response, status
from itsdangerous import BadSignature, TimestampSigner

from app.core.config import get_settings

SESSION_COOKIE = "spena_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 365  # un anno: è la tua app, non un portale bancario
_hasher = PasswordHasher()

# Segreti pubblicati: il primo è il vecchio default del codice, il secondo il
# segnaposto di .env.example. Entrambi stanno in git, quindi chiunque li legge può
# firmarsi un cookie valido.
PLACEHOLDER_SECRETS = frozenset({
    "dev-insecure-secret",
    "cambiami-con-stringa-casuale-lunga",
})

SECRET_HOWTO = (
    "SESSION_SECRET non è configurata (o è rimasta al valore di esempio). "
    "Generane una con: "
    "python -c \"import secrets; print(secrets.token_urlsafe(48))\""
)


class InsecureSessionSecret(RuntimeError):
    """SESSION_SECRET assente o lasciata a un segnaposto pubblico."""


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except (VerificationError, InvalidHashError):
        # VerificationError (e VerifyMismatchError, sua sottoclasse) copre la password
        # sbagliata; InvalidHashError arriva invece da un hash malformato (es. un
        # APP_PASSWORD_HASH troncato da un copia-incolla sbagliato nel .env) ed eredita
        # da ValueError, non da VerificationError, quindi va elencata a parte.
        return False


def _signer() -> TimestampSigner:
    """Unico punto che tocca il segreto, quindi unico punto dove va controllato.

    Sta qui e non nella rotta di login perché così il rifiuto copre sia l'emissione
    sia la verifica del cookie: un server mal configurato deve rompersi in modo
    rumoroso (500) invece di accettare cookie firmati con un segreto pubblico.
    """
    secret = get_settings().session_secret
    if not secret or secret in PLACEHOLDER_SECRETS:
        raise InsecureSessionSecret(SECRET_HOWTO)
    return TimestampSigner(secret)


def issue_session_cookie(response: Response) -> None:
    token = _signer().sign(b"spena").decode()
    response.set_cookie(
        SESSION_COOKIE, token, max_age=SESSION_MAX_AGE,
        httponly=True, samesite="lax", secure=False,
    )


def require_session(request: Request) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sessione assente")
    try:
        _signer().unsign(token, max_age=SESSION_MAX_AGE)
    except BadSignature as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sessione non valida") from exc
