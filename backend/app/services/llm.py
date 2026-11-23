"""Una chiamata all'LLM, via l'API Messages di Anthropic, che torna JSON o solleva.

Un fornitore solo e un client solo, costruito in un posto solo (`client_options`): i
test sostituiscono il trasporto HTTP e nient'altro, così l'SDK che costruisce la
richiesta e legge la risposta è lo stesso della produzione (la prima lezione di
CLAUDE.md). L'indirizzo e la chiave sono espliciti: l'SDK altrimenti li cercherebbe
nell'ambiente (ANTHROPIC_BASE_URL, ANTHROPIC_AUTH_TOKEN, un profilo su disco).

Questo file non sa niente di ricette, di ingredienti e di import: prende un prompt e
uno schema, torna un dizionario e quel che è costato.
"""

import json
import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from anthropic import (
    APIConnectionError,
    APIError,
    APIStatusError,
    AsyncAnthropic,
    AuthenticationError,
    DefaultAsyncHttpxClient,
    PermissionDeniedError,
    RateLimitError,
)
from anthropic.types import Message

from app.core.config import Settings, get_settings
from app.domain.llm_pricing import cost_usd

logger = logging.getLogger(__name__)

# L'indirizzo dell'API è una costante, non un'impostazione: un campo letto dall'ambiente
# prenderebbe l'ANTHROPIC_BASE_URL delle shell degli agenti (vedi app/core/config.py).
API_BASE_URL = "https://api.anthropic.com"


class LlmCallSite(StrEnum):
    """Da dove parte la chiamata: è la fetta della torta delle spese.

    Sta qui e non fra i modelli perché è vocabolario del client, non dello schema, e
    `llm.py` non deve conoscere il database. `complete_json` lo pretende **senza
    default**: una sezione nuova che dimenticasse di dichiararsi finirebbe zitta in un
    secchio chiamato «altro», ed è così che un tracciamento smette di servire.
    """

    TERM_DECISION = "term_decision"
    TERM_COLLAPSE = "term_collapse"
    RECIPE_DRAFT = "recipe_draft"
    UNIT_FORMS = "unit_forms"
    INGREDIENT_EMOJI = "ingredient_emoji"
    # R8: «Modifica con AI», la variante di una ricetta che esiste
    RECIPE_VARIANT = "recipe_variant"
    INGREDIENT_SUBSTITUTES = "ingredient_substitutes"
    CIQUAL_TERMS = "ciqual_terms"
    CIQUAL_MATCH = "ciqual_match"
    UNIT_GRAMS = "unit_grams"
    # la chat dei piatti (Pasti): su Claude via Agent SDK con la chiave API, a consumo; il
    # costo lo registra il giro, non questo client
    MEAL_CHAT = "meal_chat"
    # la pianificazione con Claude e le ricette scritte dopo l'ufficializzazione: stessa
    # chiave, a consumo, costo registrato dal giro e dalla coda delle ricette
    MEAL_PLANNING = "meal_planning"
    MEAL_RECIPE = "meal_recipe"


@dataclass(frozen=True)
class LlmUsage:
    """Quanto è costata una chiamata, secondo i token che Anthropic dichiara, e il
    listino di `llm_pricing`.

    Ogni campo è annullabile perché ogni campo può davvero mancare: una chiamata che
    non è arrivata a una risposta non ha token, e un modello senza listino non ha un
    costo. Un costo sconosciuto resta sconosciuto — metterci zero sarebbe
    un'affermazione, e l'assenza è la verità (vedi CLAUDE.md sui nutrienti: è la stessa
    regola).
    """

    generation_id: str | None = None
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cost_usd: float | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None


@dataclass(frozen=True)
class LlmResult:
    """La risposta e quel che è costata, insieme.

    Stanno insieme perché il consumo arriva nello stesso corpo della risposta, secondo
    i token che Anthropic dichiara, e il listino di `llm_pricing` ne fa il costo:
    buttarlo via è stato il difetto che ha reso «Unknown» ogni voce di spesa per mesi.
    """

    data: dict[str, Any]
    usage: LlmUsage
    call_site: LlmCallSite


class LlmFailureKind(StrEnum):
    """Il tipo di un guasto: dice se rifare la domanda subito servirebbe (spec §5)."""

    NOT_CONFIGURED = "not_configured"
    AUTH = "auth"
    CREDIT = "credit"
    RATE_LIMIT = "rate_limit"
    REJECTED = "rejected"
    TRANSIENT = "transient"
    TRUNCATED = "truncated"
    REFUSAL = "refusal"
    INVALID = "invalid"


# Terminale: rifare la domanda subito darebbe lo stesso esito per ogni voce.
TERMINAL_LLM_FAILURES = frozenset(
    {
        LlmFailureKind.NOT_CONFIGURED,
        LlmFailureKind.AUTH,
        LlmFailureKind.CREDIT,
        LlmFailureKind.RATE_LIMIT,
        LlmFailureKind.REJECTED,
    }
)

# Le frasi da schermo, scritte una volta sola (spec §5). Nessuna nomina una variabile o
# un codice HTTP: il dettaglio tecnico va fra parentesi nel testo dell'eccezione.
LLM_FAILURE_NOTICES: dict[LlmFailureKind, str] = {
    LlmFailureKind.NOT_CONFIGURED: "L'AI non è collegata: manca la chiave API sul server.",
    LlmFailureKind.AUTH: (
        "L'AI non risponde: la chiave API non vale più (sbagliata o revocata). "
        "Va sostituita nel .env del server."
    ),
    LlmFailureKind.CREDIT: (
        "L'AI non risponde: il credito della chiave API è finito. "
        "Va ricaricato nella console di Anthropic."
    ),
    LlmFailureKind.RATE_LIMIT: (
        "L'AI non risponde: hai raggiunto il limite di frequenza della chiave API, "
        "riprova fra poco."
    ),
    LlmFailureKind.REJECTED: (
        "L'AI non risponde: Anthropic ha rifiutato la richiesta (modello o schema non "
        "accettati). Il dettaglio è nei log del backend."
    ),
    LlmFailureKind.TRANSIENT: "L'AI non risponde in questo momento: riprova fra poco.",
    LlmFailureKind.TRUNCATED: "La risposta dell'AI si è interrotta prima della fine: riprova.",
    LlmFailureKind.REFUSAL: "L'AI ha rifiutato di rispondere a questa richiesta.",
    LlmFailureKind.INVALID: "La risposta dell'AI non si può usare: riprova.",
}


class LlmUnavailable(Exception):
    """Modello non raggiungibile o risposta inutilizzabile, con il suo tipo.

    Non è un errore da propagare: chi chiama la traduce in «decidi a mano», che è
    sempre possibile. Vedi la regola «mai un vicolo cieco» in CLAUDE.md. `usage` è
    l'uso della risposta, quando una risposta c'è stata (tagliata, rifiutata,
    inutilizzabile): quei token sono stati pagati.
    """

    def __init__(
        self,
        detail: str,
        *,
        kind: LlmFailureKind = LlmFailureKind.INVALID,
        usage: LlmUsage | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.kind = kind
        self.usage = usage if usage is not None else LlmUsage()

    def __str__(self) -> str:
        return self.detail

    @property
    def terminal(self) -> bool:
        return self.kind in TERMINAL_LLM_FAILURES

    @property
    def notice(self) -> str:
        return LLM_FAILURE_NOTICES[self.kind]


@dataclass(frozen=True)
class CallProfile:
    """Come pensa una chiamata, e quanto può aspettare.

    `timeout_seconds` e `max_retries` a `None` sono quelli delle impostazioni.
    """

    thinking: bool
    effort: str
    timeout_seconds: float | None = None
    max_retries: int | None = None


# Le classificazioni: niente ragionamento, sforzo basso.
CLASSIFY = CallProfile(thinking=False, effort="low")

# Le rotte sincrone passano da Nginx: un solo ritentativo, così una chiamata sta nei
# 90,5 s del caso peggiore (2 x 45 + 0,5, `profile_worst_seconds`).
SYNC_PROFILE = CallProfile(thinking=False, effort="low", timeout_seconds=45.0, max_retries=1)


def profile_worst_seconds(profile: CallProfile, settings: Settings) -> float:
    """Il caso peggiore di una chiamata: (ritentativi + 1) x tempo, piu le pause dell'SDK.

    Con `None` nel profilo legge le impostazioni, come `complete_json`. Le pause sono
    `min(0,5 x 2^n, 8)` per ogni ritentativo; un `retry-after` del server non ha tetto.
    """
    timeout = profile.timeout_seconds if profile.timeout_seconds is not None else settings.llm_timeout_seconds
    retries = profile.max_retries if profile.max_retries is not None else settings.llm_max_retries
    pauses = sum(min(0.5 * 2**n, 8.0) for n in range(retries))
    return (retries + 1) * timeout + pauses


def llm_configured() -> bool:
    return bool(get_settings().anthropic_api_key)


def ensure_llm_configured() -> None:
    """Prima della rete: senza chiave non si apre niente e non si spreca un giro."""
    if not llm_configured():
        raise LlmUnavailable(
            "ANTHROPIC_API_KEY non configurata", kind=LlmFailureKind.NOT_CONFIGURED
        )


def client_options(*, http_client: DefaultAsyncHttpxClient | None = None) -> dict[str, Any]:
    """Le opzioni del client: l'unico posto che le costruisce, in produzione e nei finti.

    `api_key` e `base_url` espliciti: con un argomento di credenziale l'SDK non legge
    ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN né un profilo su disco, e con l'indirizzo
    non legge ANTHROPIC_BASE_URL.
    """
    settings = get_settings()
    options: dict[str, Any] = {
        "api_key": settings.anthropic_api_key,
        "base_url": API_BASE_URL,
        "timeout": settings.llm_timeout_seconds,
        "max_retries": settings.llm_max_retries,
    }
    if http_client is not None:
        options["http_client"] = http_client
    return options


def open_client() -> AsyncAnthropic:
    """Un client, per chi fa più chiamate di seguito. Si chiude con `await api.close()`."""
    ensure_llm_configured()
    return AsyncAnthropic(**client_options())


def request_params(
    *,
    system: str,
    user: str,
    schema: dict[str, Any],
    max_tokens: int,
    profile: CallProfile,
    cache_system: bool,
) -> dict[str, Any]:
    """Il corpo della richiesta, puro: lo schema stretto è ciò che rende inutile
    qualunque scrostatore di blocchi di codice."""
    system_block: dict[str, Any] = {"type": "text", "text": system}
    if cache_system:
        system_block["cache_control"] = {"type": "ephemeral"}
    return {
        "model": get_settings().llm_model,
        "max_tokens": max_tokens,
        "system": [system_block],
        "messages": [{"role": "user", "content": user}],
        "thinking": {"type": "adaptive"} if profile.thinking else {"type": "disabled"},
        "output_config": {
            "effort": profile.effort,
            "format": {"type": "json_schema", "schema": schema},
        },
    }


def read_usage(message: Message, *, model: str) -> LlmUsage:
    """Il consumo dichiarato nella risposta, e il costo dal listino del modello chiesto.

    Il listino è di quel che si chiede (`model`), non del nome che la risposta riporta.
    Un campo della cache che l'SDK lascia `None` resta `None`; conta zero solo nella
    somma dei token in ingresso.
    """
    usage = message.usage
    cache_read = usage.cache_read_input_tokens
    cache_write = usage.cache_creation_input_tokens
    return LlmUsage(
        generation_id=message.id,
        model=message.model,
        prompt_tokens=usage.input_tokens + (cache_read or 0) + (cache_write or 0),
        completion_tokens=usage.output_tokens,
        cost_usd=cost_usd(
            model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=cache_read or 0,
            cache_write_tokens=cache_write or 0,
        ),
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
    )


def _failure(
    kind: LlmFailureKind, technical: str, usage: LlmUsage | None = None
) -> LlmUnavailable:
    detail = f"{LLM_FAILURE_NOTICES[kind]} ({technical})"
    logger.warning("LLM non disponibile, %s: %s", kind.value, technical)
    return LlmUnavailable(detail, kind=kind, usage=usage)


def _is_credit(exc: APIStatusError) -> bool:
    if exc.status_code == 402 or getattr(exc, "type", None) == "billing_error":
        return True
    if exc.status_code != 400:
        return False
    message = f"{getattr(exc, 'api_message', None) or ''} {exc.message}"
    return "credit balance" in message.lower()


def _status_failure(exc: APIStatusError) -> LlmUnavailable:
    """Il tipo di una risposta d'errore, nell'ordine della spec: il primo che vale vince.

    408 e 409, che l'SDK ritenta, dopo i tentativi cadono fra i `REJECTED` come ogni
    altro 4xx (deciso con il piano).
    """
    technical = f"HTTP {exc.status_code} {getattr(exc, 'type', None) or ''}".rstrip()
    if isinstance(exc, (AuthenticationError, PermissionDeniedError)):
        return _failure(LlmFailureKind.AUTH, technical)
    if _is_credit(exc):
        return _failure(LlmFailureKind.CREDIT, technical)
    if isinstance(exc, RateLimitError):
        return _failure(LlmFailureKind.RATE_LIMIT, technical)
    if exc.status_code >= 500:
        return _failure(LlmFailureKind.TRANSIENT, technical)
    return _failure(LlmFailureKind.REJECTED, technical)


def _network_detail(exc: APIConnectionError) -> str:
    """Il nome della classe del guasto di rete (`ReadTimeout`, `ConnectError`), e il suo
    messaggio se ne ha uno: nei log dice dove si è rotto, ed è di httpx, mai la chiave."""
    cause = exc.__cause__ or exc
    text = str(cause)[:200]
    return f"{type(cause).__name__}: {text}" if text else type(cause).__name__


def _is_message(message: object) -> bool:
    """Un `Message` che si può leggere. Un 200 che non lo è — una pagina HTML di un
    proxy, un corpo estraneo — l'SDK lo torna com'è (una `str`, o un `Message` coi campi
    vuoti), e leggerlo solleverebbe un `AttributeError` che nessun chiamante prende."""
    if not isinstance(message, Message):
        return False
    usage = getattr(message, "usage", None)
    return (
        isinstance(getattr(message, "content", None), list)
        and usage is not None
        and isinstance(getattr(usage, "input_tokens", None), int)
        and isinstance(getattr(usage, "output_tokens", None), int)
    )


def _parse(message: Message, usage: LlmUsage) -> dict[str, Any]:
    """Il dizionario della risposta, o il guasto con l'uso che la risposta aveva.

    Un `stop_reason` che la tabella non nomina (`model_context_window_exceeded`, …)
    non ha un tipo suo: la risposta si legge, e se non è JSON intero è `INVALID`.
    """
    if message.stop_reason == "max_tokens":
        raise _failure(LlmFailureKind.TRUNCATED, "stop_reason max_tokens", usage)
    if message.stop_reason == "refusal":
        raise _failure(LlmFailureKind.REFUSAL, "stop_reason refusal", usage)
    # con il ragionamento acceso il primo blocco è `thinking`: si legge quello di testo
    text = next((block.text for block in message.content if block.type == "text"), None)
    if text is None:
        raise _failure(LlmFailureKind.INVALID, "nessun blocco di testo", usage)
    try:
        parsed = json.loads(text)
    except ValueError:
        raise _failure(LlmFailureKind.INVALID, "JSON non valido", usage) from None
    if not isinstance(parsed, dict):
        raise _failure(LlmFailureKind.INVALID, "non un oggetto", usage)
    return parsed


async def complete_json(
    *,
    call_site: LlmCallSite,
    system: str,
    user: str,
    schema: dict[str, Any],
    max_tokens: int,
    profile: CallProfile = CLASSIFY,
    cache_system: bool = False,
    client: AsyncAnthropic | None = None,
) -> LlmResult:
    """Una risposta JSON conforme a `schema`, o `LlmUnavailable` con il suo tipo.

    Vincolo degli output strutturati da rispettare negli schemi che si passano qui —
    ogni proprietà deve stare in `required` e `additionalProperties` deve essere
    `false` — quindi i campi che valgono per una sola azione si dichiarano nullable,
    non opzionali.

    `client` si passa quando il chiamante ne ha già uno aperto: il riconoscimento
    parallelo fa N chiamate insieme, e aprire N connessioni separate sarebbe uno
    spreco che il semaforo non compensa. I tentativi su 429, 5xx e rete sono dell'SDK.
    """
    ensure_llm_configured()  # prima della rete: senza chiave non si apre niente
    params = request_params(
        system=system,
        user=user,
        schema=schema,
        max_tokens=max_tokens,
        profile=profile,
        cache_system=cache_system,
    )
    options: dict[str, Any] = {}
    if profile.timeout_seconds is not None:
        options["timeout"] = profile.timeout_seconds
    if profile.max_retries is not None:
        options["max_retries"] = profile.max_retries

    owned = client is None
    api = client if client is not None else open_client()
    try:
        try:
            message = await api.with_options(**options).messages.create(**params)
        except APIStatusError as exc:
            raise _status_failure(exc) from exc
        except APIConnectionError as exc:  # APITimeoutError compreso
            raise _failure(LlmFailureKind.TRANSIENT, _network_detail(exc)) from exc
        except APIError as exc:  # gli altri errori dell'SDK, come la validazione
            raise _failure(LlmFailureKind.INVALID, type(exc).__name__) from exc
        if not _is_message(message):
            raise _failure(LlmFailureKind.INVALID, "risposta non riconosciuta")
        usage = read_usage(message, model=params["model"])
        return LlmResult(data=_parse(message, usage), usage=usage, call_site=call_site)
    finally:
        if owned:
            await api.close()
