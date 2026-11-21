"""Il client di Claude sull'Agent SDK per Python (`claude-agent-sdk==0.2.180`).

Le scelte vengono dalle pagine dell'SDK lette il 2026-11-12: agent-sdk/python (le opzioni
e i tipi), custom-tools (gli strumenti nel processo con `create_sdk_mcp_server`),
permissions (`dontAsk`: ogni altra chiamata è negata, non chiesta), claude-code-features
(`setting_sources=[]`, `strict_mcp_config`), streaming-output (`include_partial_messages`
e i `StreamEvent`), sessions (ogni giro è una `query()` nuova: la cronologia sta in spena, e le
sessioni non si scrivono nemmeno su disco: `--no-session-persistence`).

`query` è importata nel modulo proprio perché i test la sostituiscano qui. Il tempo
massimo non sta qui ma nel giro (Task 6).
"""

import contextlib
import os
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKError,
    RateLimitEvent,
    ResultError,
    ResultMessage,
    SdkMcpTool,
    StreamEvent,
    TextBlock,
    create_sdk_mcp_server,
    query,
)

from app.core.config import get_settings
from app.domain.meal_chat import FailureKind
from app.services.llm import LlmUsage

SPENA_SERVER = "spena"

Effort = Literal["low", "medium", "high", "xhigh", "max"]


@dataclass(frozen=True)
class ClaudeUsage:
    model: str | None
    session_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float | None = None


@dataclass(frozen=True)
class ClaudeFailure:
    kind: FailureKind
    resets_at: datetime | None = None
    detail: str = ""
    usage: ClaudeUsage | None = None
    partial_text: str = ""


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class TurnFinished:
    text: str
    usage: ClaudeUsage


@dataclass(frozen=True)
class TurnFailed:
    failure: ClaudeFailure


ClaudeEvent = TextDelta | TurnFinished | TurnFailed


class ClaudeClient(Protocol):
    def run(
        self,
        *,
        system_prompt: str,
        prompt: str,
        tools: Sequence[SdkMcpTool],
        effort: Effort,
        max_turns: int,
    ) -> AsyncIterator[ClaudeEvent]: ...


def llm_usage(usage: ClaudeUsage | None) -> LlmUsage:
    """L'uso dichiarato dall'SDK nella forma che `llm_calls` registra."""
    if usage is None:
        return LlmUsage()
    return LlmUsage(
        generation_id=usage.session_id,
        model=usage.model,
        prompt_tokens=usage.input_tokens,
        completion_tokens=usage.output_tokens,
        cost_usd=usage.cost_usd,
    )


def claude_configured() -> bool:
    """La chiave API c'è e non è vuota (`.env.example` la lascia vuota)."""
    return bool(get_settings().anthropic_api_key)


def build_options(
    *,
    system_prompt: str,
    tools: Sequence[SdkMcpTool],
    effort: Effort,
    max_turns: int,
) -> ClaudeAgentOptions:
    settings = get_settings()
    workdir = settings.claude_workdir
    os.makedirs(workdir, exist_ok=True)
    return ClaudeAgentOptions(
        model=settings.claude_model,
        system_prompt=system_prompt,
        tools=[],
        mcp_servers={
            SPENA_SERVER: create_sdk_mcp_server(name=SPENA_SERVER, version="1", tools=list(tools))
        },
        allowed_tools=[f"mcp__{SPENA_SERVER}__{t.name}" for t in tools],
        permission_mode="dontAsk",
        setting_sources=[],
        strict_mcp_config=True,
        include_partial_messages=True,
        effort=effort,
        max_turns=max_turns,
        cwd=workdir,
        # Senza, il CLI scrive la trascrizione di ogni giro (prompt di sistema, dispensa,
        # pasti, chiamate degli strumenti) sotto `~/.claude/projects/` nel container.
        # `CLAUDE_CODE_SKIP_PROMPT_HISTORY` ferma la cronologia dei prompt (sul binario
        # 2.1.321 ferma anche la trascrizione, ma non è il suo scopo e non ci si regge).
        # Verificato sul binario: `tests/test_claude_binary.py`.
        extra_args={"no-session-persistence": None},
        env={
            "ANTHROPIC_API_KEY": settings.anthropic_api_key or "",
            # L'SDK passa al CLI `{**os.environ, **env}`: un token del piano rimasto
            # nell'ambiente del server prenderebbe il posto della chiave senza che niente
            # lo mostri. Vuoti, il CLI li legge come assenti.
            "CLAUDE_CODE_OAUTH_TOKEN": "",
            "ANTHROPIC_AUTH_TOKEN": "",
            "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
            "ENABLE_TOOL_SEARCH": "false",
            "CLAUDE_CODE_SKIP_PROMPT_HISTORY": "1",
        },
    )


@dataclass
class TurnState:
    """Quello che `translate` ricorda da un messaggio all'altro dello stesso giro."""

    texts: list[str] = field(default_factory=list)
    model: str | None = None
    resets_at: datetime | None = None
    failure: ClaudeFailure | None = None


def _classify_status(status: int | None) -> FailureKind:
    if status in (401, 403):
        return FailureKind.AUTH
    if status == 402:
        return FailureKind.CREDIT
    if status == 429:
        return FailureKind.RATE_LIMIT
    return FailureKind.UNAVAILABLE


def _mark(state: TurnState, kind: FailureKind, detail: str = "") -> None:
    # il primo guasto visto vale, salvo che un limite di frequenza ne precisi l'ora dopo
    if state.failure is None:
        state.failure = ClaudeFailure(kind, state.resets_at, detail)


def _sum_input(usage: dict[str, Any]) -> int | None:
    parts = [
        usage.get(k)
        for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    ]
    present = [p for p in parts if isinstance(p, int)]
    return sum(present) if present else None


def translate(message: object, state: TurnState) -> list[ClaudeEvent]:
    """Un messaggio dell'SDK → zero o più eventi nostri."""
    if isinstance(message, StreamEvent):
        event = message.event
        delta = event.get("delta") if isinstance(event, dict) else None
        if (
            isinstance(event, dict)
            and event.get("type") == "content_block_delta"
            and isinstance(delta, dict)
            and delta.get("type") == "text_delta"
            and isinstance(delta.get("text"), str)
        ):
            return [TextDelta(delta["text"])]
        return []

    if isinstance(message, AssistantMessage):
        state.model = message.model or state.model
        text = "".join(b.text for b in message.content if isinstance(b, TextBlock))
        if text:
            state.texts.append(text)
        if message.error is not None:
            if message.error == "rate_limit":
                kind = FailureKind.RATE_LIMIT
            elif message.error == "billing_error":
                kind = FailureKind.CREDIT
            elif message.error == "authentication_failed":
                kind = FailureKind.AUTH
            else:
                kind = FailureKind.UNAVAILABLE
            _mark(state, kind, str(message.error))
        return []

    if isinstance(message, RateLimitEvent):
        info = message.rate_limit_info
        if info.status == "rejected":
            if info.resets_at is not None:
                state.resets_at = datetime.fromtimestamp(info.resets_at, UTC)
            state.failure = ClaudeFailure(FailureKind.RATE_LIMIT, state.resets_at, "rejected")
        return []

    if isinstance(message, ResultMessage):
        raw = message.usage or {}
        output = raw.get("output_tokens")
        cost = message.total_cost_usd
        usage = ClaudeUsage(
            model=state.model,
            session_id=message.session_id,
            input_tokens=_sum_input(raw),
            output_tokens=output if isinstance(output, int) else None,
            cost_usd=float(cost) if isinstance(cost, int | float) else None,
        )
        text = "\n\n".join(state.texts)
        if not message.is_error and message.subtype == "success":
            return [TurnFinished(text, usage)]
        if message.subtype == "error_max_turns":
            kind = FailureKind.MAX_TURNS
        else:
            kind = _classify_status(message.api_error_status)
        _mark(state, kind, message.result or message.subtype)
        assert state.failure is not None
        # un guasto già visto nel giro tiene il suo tipo, ma l'uso e il testo detto fin
        # qui arrivano dal risultato: ogni giro registra quello che l'SDK dichiara
        state.failure = replace(state.failure, usage=usage, partial_text=text)
        return [TurnFailed(state.failure)]

    return []


class SdkClaudeClient:
    """Il client di produzione: una `query()` nuova a ogni giro."""

    async def run(
        self,
        *,
        system_prompt: str,
        prompt: str,
        tools: Sequence[SdkMcpTool],
        effort: Effort,
        max_turns: int,
    ) -> AsyncIterator[ClaudeEvent]:
        if not claude_configured():
            yield TurnFailed(ClaudeFailure(FailureKind.NOT_CONFIGURED))
            return
        state = TurnState()
        ended = False
        try:
            options = build_options(
                system_prompt=system_prompt, tools=tools, effort=effort, max_turns=max_turns
            )
            # `aclosing`: un `async for` non chiude il generatore interno quando chi legge
            # esce (PEP 533). Senza, la `query()` dell'SDK, e il processo del CLI, si
            # chiuderebbero al garbage collector, in un altro task.
            async with contextlib.aclosing(query(prompt=prompt, options=options)) as messages:
                async for message in messages:
                    for event in translate(message, state):
                        if isinstance(event, TurnFinished | TurnFailed):
                            ended = True
                        yield event
        except ResultError as exc:
            if not ended:
                kind = state.failure.kind if state.failure else _classify_status(exc.api_error_status)
                yield TurnFailed(
                    state.failure or ClaudeFailure(kind, state.resets_at, str(exc))
                )
            return
        except ClaudeSDKError as exc:
            if not ended:
                yield TurnFailed(state.failure or ClaudeFailure(FailureKind.UNAVAILABLE, None, str(exc)))
            return
        if not ended:
            # il flusso è finito senza un risultato: la risposta si è interrotta
            yield TurnFailed(
                state.failure or ClaudeFailure(FailureKind.INTERRUPTED, None, "nessun risultato")
            )


def get_claude_client() -> ClaudeClient:
    """La dipendenza FastAPI. Il 503 «non collegato» sta nella rotta (Task 7)."""
    return SdkClaudeClient()
