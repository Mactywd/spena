"""L'AI che decide i sostituti di un ingrediente (R5), e la verifica della sua risposta.

Due strade, un solo modo di chiedere e di verificare:

- `decide_substitutions`, per `python -m app.cli.decide_substitutes`: tutte le voci
  scoperte (`pending_voices`), dalla più usata, a lotti di `SUBSTITUTE_BATCH` con le
  chiamate del lotto in parallelo, e `after_batch` (il commit) dopo ogni lotto;
- `decide_pair`, per «Sostituisci» su una voce che non ha ancora una risposta: una
  chiamata, sul momento.

Una chiamata per voce e non un lotto per chiamata, per la ragione scritta in testa a
`recipe_import/decide.py`: un modello piccolo che deve riecheggiare venti nomi in un
array si sfalda, e il degrado non si vede. L'anagrafica alimentare intera sta nel
prompt, perché un sostituto si sceglie solo lì (decisione 2 di Mattia): ~0,0004 $ a
chiamata, misurato su `term_decision`, che porta lo stesso elenco.

Una risposta che non si può verificare non si applica (decisione 2): un nome fuori
anagrafica o non alimentare, l'ingrediente stesso, un doppione, più di tre sostituti,
una nota troppo lunga, un esito che non torna. **Un solo difetto scarta la risposta
intera**: la voce resta scoperta, e il giro dopo la richiede. L'AI scrive solo dove non
c'è una risposta (`store_ai_answer`): una correzione a mano non si riscrive mai
(decisione 4).
"""

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

from anthropic import AsyncAnthropic
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.ingredient import Ingredient
from app.db.models.llm_call import LlmCall
from app.domain.rules import IngredientKind
from app.domain.substitutions import (
    SUBSTITUTE_NOTE_MAX,
    SUBSTITUTES_MAX,
    SubstitutionContext,
    SubstitutionVerdict,
    clean_note,
)
from app.repositories.llm_calls import record_llm_call
from app.repositories.substitutions import (
    Answer,
    Voice,
    general_row,
    is_answered,
    pending_voices,
    store_ai_answer,
)
from app.services.llm import (
    CLASSIFY,
    LLM_FAILURE_NOTICES,
    CallProfile,
    LlmCallSite,
    LlmFailureKind,
    LlmUnavailable,
    LlmUsage,
    complete_json,
    ensure_llm_configured,
    open_client,
)

# Venti voci per lotto: il commit dopo ogni lotto non butta il lavoro fatto se il quinto
# lotto si rompe, e venti chiamate insieme stanno sotto `LLM_MAX_CONCURRENCY` (8) a giri.
SUBSTITUTE_BATCH = 20
# Una risposta è al più tre nomi con tre note: un centinaio di token. Il resto è spazio
# per divagare, che lo schema non lascia usare.
SUBSTITUTE_MAX_TOKENS = 400

# Le parole dell'esito nella risposta del modello, in italiano come il prompt, verso il
# vocabolario del dominio
AI_VERDICTS: dict[str, SubstitutionVerdict] = {
    "sostituti": SubstitutionVerdict.SUBSTITUTES,
    "omettere": SubstitutionVerdict.OMIT,
    "insostituibile": SubstitutionVerdict.IRREPLACEABLE,
}

# «la ricetta è dolce / salata»: il contesto come lo legge il modello
CONTEXT_WORDS: dict[SubstitutionContext, str] = {
    SubstitutionContext.SAVORY: "salata",
    SubstitutionContext.SWEET: "dolce",
}

SUBSTITUTE_SYSTEM_PROMPT = """Sei un aiuto in cucina. Ricevi un ingrediente, se la ricetta in cui compare è dolce o salata, e l'elenco degli ingredienti alimentari di un'app di dispensa. Di' cosa può fare chi non ce l'ha in casa, scegliendo UN esito.

- "sostituti": da 1 a 3 ingredienti dell'elenco che lo sostituiscono bene in una ricetta di quel tipo, dal migliore, scritti identici a come compaiono nell'elenco. Per ognuno, in "nota", poche parole solo se servono per usarlo al suo posto ("metà dose", "sciolto in acqua"), altrimenti una stringa vuota.
- "omettere": nessun ingrediente dell'elenco lo sostituisce, ma il piatto riesce anche senza: una spezia, un'erba, una guarnizione.
- "insostituibile": senza di lui il piatto non si fa, come la farina nel pane.

Regole:
- Solo nomi dell'elenco, mai l'ingrediente stesso, mai lo stesso nome due volte.
- Con "omettere" e "insostituibile", "sostituti" è una lista vuota.
- Preferisci ingredienti comuni, che si trovano in una dispensa di casa.
- Non inserire valori nutrizionali, calorie o macronutrienti.
"""

# Vincolo dello strict mode: ogni proprietà in `required`, `additionalProperties` falso.
# Il numero dei sostituti non sta nello schema (`maxItems` non lo onorano tutti i
# provider): lo dice il prompt e lo controlla `verify_answer`.
SUBSTITUTE_SCHEMA = {
    "type": "object",
    "properties": {
        "esito": {"type": "string", "enum": list(AI_VERDICTS)},
        "sostituti": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"nome": {"type": "string"}, "nota": {"type": "string"}},
                "required": ["nome", "nota"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["esito", "sostituti"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class Rejected:
    """Una risposta che non si applica, e perché (il comando lo stampa)."""

    reason: str


def verify_answer(
    data: dict, ingredient_id: uuid.UUID, food: Mapping[str, uuid.UUID]
) -> Answer | Rejected:
    """La risposta del modello, verificata contro l'anagrafica alimentare (`food`).

    Uno schema rispettato non è una risposta verificata: si ricontrolla tutto qui.
    """
    raw_verdict = data.get("esito")
    verdict = AI_VERDICTS.get(raw_verdict) if isinstance(raw_verdict, str) else None
    if verdict is None:
        return Rejected("esito sconosciuto")
    raw = data.get("sostituti")
    if not isinstance(raw, list):
        return Rejected("«sostituti» non è una lista")
    if verdict is not SubstitutionVerdict.SUBSTITUTES:
        return Answer(verdict) if not raw else Rejected("sostituti con un esito che non ne vuole")
    if not raw:
        return Rejected("nessun sostituto")
    if len(raw) > SUBSTITUTES_MAX:
        return Rejected("più di tre sostituti")
    seen: set[uuid.UUID] = set()
    chosen: list[tuple[uuid.UUID, str | None]] = []
    for item in raw:
        if not isinstance(item, dict):
            return Rejected("un sostituto malformato")
        name = str(item.get("nome") or "").strip().casefold()
        substitute_id = food.get(name)
        if substitute_id is None:
            return Rejected(f"«{name}» non è un alimento dell'anagrafica")
        if substitute_id == ingredient_id:
            return Rejected("l'ingrediente stesso")
        if substitute_id in seen:
            return Rejected(f"«{name}» due volte")
        seen.add(substitute_id)
        raw_note = item.get("nota")
        note = clean_note(raw_note if isinstance(raw_note, str) else None)
        if note is not None and len(note) > SUBSTITUTE_NOTE_MAX:
            return Rejected(f"la nota di «{name}» è troppo lunga")
        chosen.append((substitute_id, note))
    return Answer(verdict, tuple(chosen))


async def load_food(session: AsyncSession) -> dict[str, uuid.UUID]:
    """Il cibo dell'anagrafica, nome in minuscolo → id, per nome: l'offerta al modello e
    il controllo della risposta sono lo stesso elenco, e non si possono scollare."""
    rows = await session.execute(
        select(Ingredient.id, Ingredient.name)
        .where(Ingredient.kind == IngredientKind.FOOD)
        .order_by(Ingredient.name)
    )
    return {name.casefold(): ingredient_id for ingredient_id, name in rows.all()}


def question(name: str, context: SubstitutionContext, food: Mapping[str, uuid.UUID]) -> str:
    own = name.casefold()
    return json.dumps(
        {
            "ingrediente": name,
            "ricetta": CONTEXT_WORDS[context],
            # senza l'ingrediente stesso: un nome in meno da non scegliere
            "anagrafica": [candidate for candidate in food if candidate != own],
        },
        ensure_ascii=False,
    )


async def _ask(
    name: str,
    ingredient_id: uuid.UUID,
    context: SubstitutionContext,
    food: Mapping[str, uuid.UUID],
    client: AsyncAnthropic,
    *,
    profile: CallProfile = CLASSIFY,
) -> tuple[Answer | Rejected, LlmUsage]:
    """Una voce, una chiamata. `LlmUnavailable` risale: chi chiama la registra."""
    esito = await complete_json(
        call_site=LlmCallSite.INGREDIENT_SUBSTITUTES,
        system=SUBSTITUTE_SYSTEM_PROMPT,
        user=question(name, context, food),
        schema=SUBSTITUTE_SCHEMA,
        max_tokens=SUBSTITUTE_MAX_TOKENS,
        profile=profile,
        client=client,
    )
    return verify_answer(esito.data, ingredient_id, food), esito.usage


def describe(outcome: Answer | Rejected, names: Mapping[uuid.UUID, str]) -> str:
    """Una risposta in una riga, per chi lancia il comando e guarda la qualità."""
    if isinstance(outcome, Rejected):
        return f"scartata ({outcome.reason})"
    if outcome.verdict is SubstitutionVerdict.OMIT:
        return "si può omettere"
    if outcome.verdict is SubstitutionVerdict.IRREPLACEABLE:
        return "insostituibile"
    return ", ".join(
        names.get(substitute_id, str(substitute_id)) + (f" ({note})" if note else "")
        for substitute_id, note in outcome.substitutes
    )


@dataclass(frozen=True)
class PairOutcome:
    stored: bool = False
    # l'AI non ha risposto, o ha risposto qualcosa che non si applica: a video la frase
    # del guasto (`notice`) sopra «Nessun suggerimento ancora», con la strada a mano
    failed: bool = False
    notice: str | None = None


async def decide_pair(
    session: AsyncSession,
    ingredient_id: uuid.UUID,
    context: SubstitutionContext,
    client: AsyncAnthropic | None = None,
    *,
    profile: CallProfile = CLASSIFY,
) -> PairOutcome:
    """La voce generale di un ingrediente in un contesto, chiesta sul momento se manca.

    Non chiama nessuno se la voce ha già una risposta, né senza chiave: una chiave che
    manca è la configurazione, non un guasto, e non si registra come spesa.
    """
    existing = await general_row(session, ingredient_id, context)
    if existing is not None and is_answered(existing):
        return PairOutcome()
    ingredient = await session.get(Ingredient, ingredient_id)
    if ingredient is None:
        raise LookupError(f"nessun ingrediente {ingredient_id}")
    try:
        ensure_llm_configured()
    except LlmUnavailable as exc:
        return PairOutcome(failed=True, notice=exc.notice)
    food = await load_food(session)
    owned = client is None
    api = client if client is not None else open_client()
    try:
        verified, usage = await _ask(
            ingredient.name, ingredient.id, context, food, api, profile=profile
        )
    except LlmUnavailable as exc:
        await record_llm_call(
            session, call_site=LlmCallSite.INGREDIENT_SUBSTITUTES, usage=exc.usage, ok=False
        )
        return PairOutcome(failed=True, notice=exc.notice)
    finally:
        if owned:
            await api.close()
    await record_llm_call(
        session, call_site=LlmCallSite.INGREDIENT_SUBSTITUTES, usage=usage, ok=True
    )
    if isinstance(verified, Rejected):
        return PairOutcome(failed=True, notice=LLM_FAILURE_NOTICES[LlmFailureKind.INVALID])
    return PairOutcome(stored=await store_ai_answer(session, ingredient.id, context, verified))


@dataclass(frozen=True)
class SubstitutionRun:
    """Quel che un lancio ha fatto, e quel che resta."""

    substitutes: int = 0  # voci salvate coi loro sostituti
    omit: int = 0  # voci salvate «si può omettere»
    irreplaceable: int = 0  # voci salvate «insostituibile»
    rejected: int = 0  # risposte che non si potevano verificare
    calls: int = 0
    # la somma dei costi calcolati dal listino; None se nessuna chiamata ne ha uno
    # (zero direbbe «gratis», ed è un'affermazione: la regola dei nutrienti)
    cost_usd: float | None = None
    # le voci ancora scoperte alla fine: senza, «0 salvate» vorrebbe dire insieme «niente
    # da fare» e «è andato tutto storto»
    pending: int = 0
    unavailable: str | None = None

    @property
    def stored(self) -> int:
        return self.substitutes + self.omit + self.irreplaceable


async def decide_substitutions(
    session: AsyncSession,
    client: AsyncAnthropic | None = None,
    limit: int | None = None,
    batch_size: int = SUBSTITUTE_BATCH,
    after_batch: Callable[[], Awaitable[None]] | None = None,
    report: Callable[[str], None] | None = None,
) -> SubstitutionRun:
    """Chiede all'AI le voci scoperte, dalla più usata, al più `limit`.

    Le domande di un lotto partono insieme sotto `LLM_MAX_CONCURRENCY`; le scritture si
    fanno dopo, in sequenza (il parallelo è sulla rete, non sul database). Dopo ogni lotto
    `after_batch` — il comando passa `session.commit`. Al primo lotto con un guasto
    dell'AI si ferma dopo averlo scritto: chiedere i lotti dopo sarebbe pagare per sapere
    che è ancora giù. `report` riceve una riga per voce («pollo (salato): tacchino»).
    """
    try:
        ensure_llm_configured()
    except LlmUnavailable as exc:
        # senza chiave non si apre niente e non si registra niente: è la configurazione
        return SubstitutionRun(pending=len(await pending_voices(session)), unavailable=str(exc))
    voices = await pending_voices(session)
    if limit is not None:
        voices = voices[:limit]
    if not voices:
        return SubstitutionRun(pending=len(await pending_voices(session)))
    food = await load_food(session)
    names = {ingredient_id: name for name, ingredient_id in food.items()}
    # `max(1, …)`: a 0 il semaforo non si aprirebbe mai (lo stesso motivo di decide.py)
    semaphore = asyncio.Semaphore(max(1, get_settings().llm_max_concurrency))
    stored = {verdict: 0 for verdict in SubstitutionVerdict}
    rejected = calls = 0
    cost: float | None = None
    unavailable: str | None = None
    # il primo guasto terminale del lancio: le domande che non sono ancora partite non
    # partono (credito finito, chiave revocata: lo stesso esito per ogni voce)
    halted: LlmUnavailable | None = None

    async def ask(voice: Voice, api: AsyncAnthropic):
        nonlocal halted
        async with semaphore:
            if halted is not None:
                # non è avvenuta nessuna chiamata: non si conta e non si registra
                return None, LlmUsage(), halted.detail, False
            try:
                verified, usage = await _ask(
                    voice.name, voice.ingredient_id, voice.context, food, api
                )
            except LlmUnavailable as exc:
                if exc.terminal and halted is None:
                    halted = exc
                return None, exc.usage, str(exc), True
            return verified, usage, None, True

    owned = client is None
    api = client if client is not None else open_client()
    try:
        for start in range(0, len(voices), batch_size):
            lot = voices[start : start + batch_size]
            answers = await asyncio.gather(*(ask(voice, api) for voice in lot))
            for voice, (verified, usage, error, called) in zip(lot, answers, strict=True):
                if called:
                    calls += 1
                    # la spesa si scrive comunque: una chiamata inutile costa come una buona
                    await record_llm_call(
                        session,
                        call_site=LlmCallSite.INGREDIENT_SUBSTITUTES,
                        usage=usage,
                        ok=error is None,
                    )
                if usage.cost_usd is not None:
                    cost = (cost or 0.0) + usage.cost_usd
                if error is not None:
                    unavailable = error
                    text = f"non decisa ({error})"
                elif isinstance(verified, Rejected):
                    rejected += 1
                    text = describe(verified, names)
                elif await store_ai_answer(session, voice.ingredient_id, voice.context, verified):
                    stored[verified.verdict] += 1
                    text = describe(verified, names)
                else:
                    text = "già decisa, lasciata com'era"
                if report is not None:
                    report(f"{voice.name} ({voice.context.value}): {text}")
            await session.flush()
            if after_batch is not None:
                await after_batch()
            if unavailable is not None:
                break
    finally:
        if owned:
            await api.close()

    return SubstitutionRun(
        substitutes=stored[SubstitutionVerdict.SUBSTITUTES],
        omit=stored[SubstitutionVerdict.OMIT],
        irreplaceable=stored[SubstitutionVerdict.IRREPLACEABLE],
        rejected=rejected,
        calls=calls,
        cost_usd=cost,
        pending=len(await pending_voices(session)),
        unavailable=unavailable,
    )


async def measured_cost(session: AsyncSession) -> tuple[int, float | None]:
    """Quante chiamate riuscite del modello di adesso hanno un costo, e la loro media: la
    stima del `--dry-run` si fa su quel che è stato pagato davvero. Le righe di un altro
    modello (Gemma, di prima) non stimano niente su Haiku."""
    count, average = (
        await session.execute(
            select(func.count(LlmCall.cost_usd), func.avg(LlmCall.cost_usd)).where(
                LlmCall.call_site == LlmCallSite.INGREDIENT_SUBSTITUTES.value,
                LlmCall.ok.is_(True),
                LlmCall.model == get_settings().llm_model,
            )
        )
    ).one()
    return count, (float(average) if average is not None else None)
