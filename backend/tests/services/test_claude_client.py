"""Il client di produzione di Claude, con i tipi veri dell'SDK e `query` sostituita."""

from datetime import UTC, datetime

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    CLINotFoundError,
    RateLimitEvent,
    RateLimitInfo,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    TextBlock,
    tool,
)

from app.core.config import get_settings
from app.domain.meal_chat import FailureKind
from app.services.claude import client as client_module
from app.services.claude.client import (
    ClaudeUsage,
    SdkClaudeClient,
    TextDelta,
    TurnFailed,
    TurnFinished,
    build_options,
    claude_configured,
    get_claude_client,
    llm_usage,
)
from app.services.llm import LlmUsage

CHIAVE_FINTA = "chiave-finta-per-i-test"


@pytest.fixture(autouse=True)
def _chiave(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", CHIAVE_FINTA)
    monkeypatch.setenv("CLAUDE_WORKDIR", str(tmp_path / "lavoro"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@tool("ping", "Risponde pong", {})
async def _ping(args):
    return {"content": [{"type": "text", "text": "pong"}]}


def _delta(text: str) -> StreamEvent:
    return StreamEvent(
        uuid="u",
        session_id="s1",
        event={
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": text},
        },
    )


def _assistant(text: str, error=None) -> AssistantMessage:
    return AssistantMessage(content=[TextBlock(text=text)], model="claude-opus-5-5", error=error)


def _result(**kw) -> ResultMessage:
    base = dict(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=False,
        num_turns=1,
        session_id="s1",
    )
    base.update(kw)
    return ResultMessage(**base)


def _fake_query(monkeypatch, messages=(), raises=None):
    calls: list[dict] = []

    async def fake(*, prompt, options):
        calls.append({"prompt": prompt, "options": options})
        for m in messages:
            yield m
        if raises is not None:
            raise raises

    monkeypatch.setattr(client_module, "query", fake)
    return calls


async def _run():
    return [
        e
        async for e in SdkClaudeClient().run(
            system_prompt="sono io", prompt="ciao", tools=[], effort="medium", max_turns=12
        )
    ]


async def test_le_opzioni_di_produzione(monkeypatch):
    calls = _fake_query(monkeypatch, [_result(usage={})])
    events = [
        e
        async for e in SdkClaudeClient().run(
            system_prompt="sono io", prompt="ciao", tools=[_ping], effort="medium", max_turns=12
        )
    ]
    assert len(events) == 1
    assert calls[0]["prompt"] == "ciao"
    o = calls[0]["options"]
    assert o.model == "claude-opus-5-5"
    assert o.system_prompt == "sono io"
    assert o.tools == []
    assert list(o.mcp_servers) == ["spena"]
    assert o.allowed_tools == ["mcp__spena__ping"]
    assert o.permission_mode == "dontAsk"
    assert o.setting_sources == []
    assert o.strict_mcp_config is True
    assert o.include_partial_messages is True
    assert o.effort == "medium"
    assert o.max_turns == 12
    assert str(o.cwd).endswith("lavoro")
    assert o.extra_args == {"no-session-persistence": None}
    assert o.env == {
        "ANTHROPIC_API_KEY": CHIAVE_FINTA,
        "CLAUDE_CODE_OAUTH_TOKEN": "",
        "ANTHROPIC_AUTH_TOKEN": "",
        "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
        "ENABLE_TOOL_SEARCH": "false",
        "CLAUDE_CODE_SKIP_PROMPT_HISTORY": "1",
    }
    # la cartella di lavoro viene creata
    import os

    assert os.path.isdir(o.cwd)


def test_un_token_nell_ambiente_non_prende_il_posto_della_chiave(monkeypatch):
    """L'SDK passa al CLI `{**os.environ, **options.env}`: un token del piano rimasto
    nell'ambiente prenderebbe il posto della chiave senza che niente lo mostri. Si spegne
    con una stringa vuota, che il CLI legge come assente."""
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "finto-token-per-il-test")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "finto-auth-per-il-test")
    o = build_options(system_prompt="x", tools=[_ping], effort="low", max_turns=1)
    assert o.env["CLAUDE_CODE_OAUTH_TOKEN"] == ""
    assert o.env["ANTHROPIC_AUTH_TOKEN"] == ""
    assert o.env["ANTHROPIC_API_KEY"] == CHIAVE_FINTA


def test_build_options_e_quello_che_gira():
    o = build_options(system_prompt="x", tools=[_ping], effort="low", max_turns=1)
    assert o.effort == "low" and o.max_turns == 1


async def test_lo_streaming_diventa_testo_e_fine(monkeypatch):
    _fake_query(
        monkeypatch,
        [
            SystemMessage(subtype="init", data={}),
            _delta("Cia"),
            _delta("o!"),
            _assistant("Ciao!"),
            _result(
                usage={"input_tokens": 10, "cache_read_input_tokens": 90, "output_tokens": 7}
            ),
        ],
    )
    events = await _run()
    assert [type(e) for e in events] == [TextDelta, TextDelta, TurnFinished]
    assert events[0].text == "Cia"
    fine = events[2]
    assert fine.text == "Ciao!"
    assert fine.usage == ClaudeUsage(
        model="claude-opus-5-5",
        session_id="s1",
        input_tokens=100,
        output_tokens=7,
        cost_usd=None,
    )


async def test_piu_messaggi_si_separano_con_una_riga_vuota(monkeypatch):
    _fake_query(monkeypatch, [_assistant("Uno"), _assistant("Due"), _result(usage={})])
    fine = (await _run())[-1]
    assert fine.text == "Uno\n\nDue"
    # i valori assenti restano None, non 0
    assert fine.usage.input_tokens is None and fine.usage.output_tokens is None


async def test_il_limite_di_frequenza_porta_l_ora(monkeypatch):
    t = datetime(2026, 11, 12, 17, 40, tzinfo=UTC)
    _fake_query(
        monkeypatch,
        [
            RateLimitEvent(
                rate_limit_info=RateLimitInfo(status="rejected", resets_at=int(t.timestamp())),
                uuid="u",
                session_id="s1",
            ),
            _result(is_error=True),
        ],
    )
    events = await _run()
    assert len(events) == 1 and isinstance(events[0], TurnFailed)
    assert events[0].failure.kind == FailureKind.RATE_LIMIT
    assert events[0].failure.resets_at == t


async def test_un_limite_permesso_non_e_un_guasto(monkeypatch):
    _fake_query(
        monkeypatch,
        [
            RateLimitEvent(
                rate_limit_info=RateLimitInfo(status="allowed_warning", resets_at=1),
                uuid="u",
                session_id="s1",
            ),
            _result(usage={}),
        ],
    )
    assert isinstance((await _run())[-1], TurnFinished)


@pytest.mark.parametrize(
    ("messages", "raises", "kind"),
    [
        ([_assistant("", error="authentication_failed"), _result(is_error=True)], None, "auth"),
        ([_assistant("", error="billing_error"), _result(is_error=True)], None, "credit"),
        ([_assistant("", error="rate_limit"), _result(is_error=True)], None, "rate_limit"),
        ([_assistant("", error="server_error"), _result(is_error=True)], None, "unavailable"),
        ([_result(is_error=True, api_error_status=429)], None, "rate_limit"),
        ([_result(is_error=True, api_error_status=402)], None, "credit"),
        ([_result(is_error=True, api_error_status=401)], None, "auth"),
        ([_result(is_error=True, api_error_status=403)], None, "auth"),
        ([_result(is_error=True, api_error_status=529)], None, "unavailable"),
        ([_result(is_error=True, subtype="error_max_turns")], None, "max_turns"),
        ([], CLINotFoundError("manca"), "unavailable"),
    ],
)
async def test_i_guasti(monkeypatch, messages, raises, kind):
    _fake_query(monkeypatch, messages, raises)
    events = await _run()
    falliti = [e for e in events if isinstance(e, TurnFailed)]
    assert len(falliti) == 1 and events[-1] is falliti[0]
    assert falliti[0].failure.kind == FailureKind(kind)
    assert not any(isinstance(e, TurnFinished) for e in events)


async def test_un_errore_dopo_il_risultato_non_duplica_il_guasto(monkeypatch):
    from claude_agent_sdk import ResultError

    _fake_query(
        monkeypatch,
        [_result(is_error=True, api_error_status=429)],
        ResultError("esce 1", data={"api_error_status": 429}),
    )
    events = await _run()
    assert len(events) == 1 and events[0].failure.kind == FailureKind.RATE_LIMIT


async def test_result_error_si_classifica_per_stato(monkeypatch):
    from claude_agent_sdk import ResultError

    _fake_query(monkeypatch, [], ResultError("esce 1", data={"api_error_status": 401}))
    assert (await _run())[0].failure.kind == FailureKind.AUTH


@pytest.mark.parametrize("valore", [None, ""])
async def test_senza_chiave_non_parte_niente(monkeypatch, valore):
    if valore is None:
        monkeypatch.delenv("ANTHROPIC_API_KEY")
    else:
        monkeypatch.setenv("ANTHROPIC_API_KEY", valore)
    get_settings.cache_clear()
    calls = _fake_query(monkeypatch, [_result(usage={})])
    assert not claude_configured()
    events = await _run()
    assert calls == []
    assert len(events) == 1 and events[0].failure.kind == FailureKind.NOT_CONFIGURED


def test_con_la_chiave_e_configurato():
    assert claude_configured()


def test_get_claude_client_e_quello_di_produzione():
    assert isinstance(get_claude_client(), SdkClaudeClient)


def test_prova_senza_chiave_dice_che_non_e_collegato(monkeypatch, capsys):
    from app.cli import check_claude

    monkeypatch.delenv("ANTHROPIC_API_KEY")
    get_settings.cache_clear()
    check_claude.main(["--prova"])
    assert "prova: Claude non è collegato" in capsys.readouterr().out


def test_prova_con_un_giro_riuscito(monkeypatch, capsys):
    from app.cli import check_claude

    _fake_query(monkeypatch, [_assistant("ok"), _result(usage={})])
    assert check_claude.main(["--prova"]) == 0
    assert "prova: ok" in capsys.readouterr().out


async def test_chi_smette_di_leggere_chiude_subito_la_query_dell_sdk(monkeypatch):
    """Il giro esce dal flusso al primo `TurnFinished` (o al tempo massimo) e chiude il
    nostro generatore: la `query()` dell'SDK, e con lei il processo del CLI, si chiude
    subito, nel task del giro, non quando passa il garbage collector."""
    closed: list[bool] = []

    async def fake(*, prompt, options):
        try:
            yield _delta("ciao")
            yield _result(usage={})
            yield _delta("dopo")
        finally:
            closed.append(True)

    monkeypatch.setattr(client_module, "query", fake)
    stream = SdkClaudeClient().run(
        system_prompt="x", prompt="ciao", tools=[], effort="low", max_turns=1
    )
    async for event in stream:
        if isinstance(event, TurnFinished):
            break
    await stream.aclose()

    assert closed == [True]


async def test_la_fine_porta_il_costo(monkeypatch):
    _fake_query(
        monkeypatch,
        [_assistant("Ciao!"), _result(total_cost_usd=0.0421, usage={"output_tokens": 7})],
    )
    fine = (await _run())[-1]
    assert isinstance(fine, TurnFinished) and fine.usage.cost_usd == 0.0421


async def test_troppi_passaggi_tengono_il_testo(monkeypatch):
    _fake_query(
        monkeypatch,
        [
            _assistant("Ecco la ricetta."),
            _result(
                subtype="error_max_turns",
                is_error=True,
                total_cost_usd=0.31,
                usage={"input_tokens": 900, "output_tokens": 300},
            ),
        ],
    )
    events = await _run()
    failure = events[-1].failure
    assert isinstance(events[-1], TurnFailed) and failure.kind == FailureKind.MAX_TURNS
    assert failure.partial_text == "Ecco la ricetta."
    assert failure.usage.cost_usd == 0.31 and failure.usage.input_tokens == 900


async def test_un_guasto_con_il_risultato_porta_l_uso(monkeypatch):
    _fake_query(
        monkeypatch,
        [_result(is_error=True, api_error_status=500, total_cost_usd=0.002, usage={})],
    )
    failure = (await _run())[-1].failure
    assert failure.kind == FailureKind.UNAVAILABLE and failure.usage.cost_usd == 0.002


async def test_un_guasto_gia_visto_tiene_il_tipo_e_prende_l_uso(monkeypatch):
    """Un 429 arriva di solito prima come `AssistantMessage.error`, poi come risultato: il
    tipo resta quello, ma il costo e i token del risultato non si perdono."""
    _fake_query(
        monkeypatch,
        [
            _assistant("Cominciavo", error="rate_limit"),
            _result(
                is_error=True,
                total_cost_usd=0.07,
                usage={"input_tokens": 50, "output_tokens": 5},
            ),
        ],
    )
    failure = (await _run())[-1].failure
    assert failure.kind == FailureKind.RATE_LIMIT
    assert failure.usage.cost_usd == 0.07 and failure.usage.output_tokens == 5
    assert failure.partial_text == "Cominciavo"


def test_llm_usage():
    assert llm_usage(None) == LlmUsage()
    pieno = ClaudeUsage(
        model="claude-opus-5-5", session_id="s1", input_tokens=10, output_tokens=2, cost_usd=0.5
    )
    assert llm_usage(pieno) == LlmUsage(
        generation_id="s1",
        model="claude-opus-5-5",
        prompt_tokens=10,
        completion_tokens=2,
        cost_usd=0.5,
    )
