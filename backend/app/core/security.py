from argon2 import PasswordHasher, extract_parameters
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


PASSWORD_HASH_HOWTO = (
    "APP_PASSWORD_HASH c'è ma non è un hash argon2 leggibile. La causa più probabile "
    "è un troncamento: l'hash contiene dei `$` e Compose li interpreta come "
    "riferimenti a variabili se il servizio backend usa la forma breve "
    "`env_file: .env`, oppure se Compose è precedente alla 2.30 e non conosce "
    "`format: raw` (misurato: 62 caratteri su 97 arrivano al container). Controlla "
    "`docker compose version` e la forma di `env_file` in docker-compose.yml, poi "
    "rigenera l'hash con: docker compose run --rm backend python -c "
    "\"from app.core.security import hash_password; print(hash_password('la-tua-password'))\" "
    "e incollalo in .env senza apici."
)


class UnusablePasswordHash(RuntimeError):
    """APP_PASSWORD_HASH valorizzata ma illeggibile per argon2."""


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


def is_insecure_session_secret(secret: str) -> bool:
    """Il giudizio su un segreto, in un posto solo.

    Lo usano due controlli distinti: `_signer()`, che blocca la singola richiesta,
    e l'avvio dell'applicazione (app/main.py), che rifiuta di partire. Duplicare
    l'elenco dei segnaposto li farebbe divergere, e il controllo all'avvio
    diventerebbe più permissivo di quello che conta davvero.
    """
    return not secret or secret in PLACEHOLDER_SECRETS


def is_unusable_password_hash(hashed: str) -> bool:
    """Vero se l'hash configurato c'è ma argon2 non sa leggerlo.

    `extract_parameters` fa esattamente questa domanda — i parametri si estraggono
    solo da un hash ben formato — senza bisogno di una password da provare.

    Un hash vuoto non è illeggibile ma assente, e risponde False: è una macchina su
    cui il `.env` non è ancora stato riempito, non una configurazione rotta, e il
    login risponde già 401 a chiunque (vedi tests/api/test_auth.py).
    """
    if not hashed:
        return False
    try:
        extract_parameters(hashed)
    except InvalidHashError:
        return True
    return False


def _signer() -> TimestampSigner:
    """Unico punto che tocca il segreto, quindi unico punto dove va controllato.

    Sta qui e non nella rotta di login perché così il rifiuto copre sia l'emissione
    sia la verifica del cookie: un server mal configurato deve rompersi in modo
    rumoroso (500) invece di accettare cookie firmati con un segreto pubblico.
    Resta anche con il controllo all'avvio: le impostazioni si possono cambiare a
    processo vivo (i test lo fanno), e questo è l'ultimo cancello prima della firma.
    """
    secret = get_settings().session_secret
    if is_insecure_session_secret(secret):
        raise InsecureSessionSecret(SECRET_HOWTO)
    return TimestampSigner(secret)


def issue_session_cookie(response: Response) -> None:
    token = _signer().sign(b"spena").decode()
    response.set_cookie(
        SESSION_COOKIE, token, max_age=SESSION_MAX_AGE,
        httponly=True, samesite="lax", secure=get_settings().cookie_secure,
    )


def require_session(request: Request) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sessione assente")
    try:
        _signer().unsign(token, max_age=SESSION_MAX_AGE)
    except BadSignature as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sessione non valida") from exc
