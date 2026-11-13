"""Il finto di Claude per i test dei giri e delle rotte. Niente SDK vero, niente rete.

`UseTool` chiama il `handler` dello strumento **con quel nome fra i `tools` ricevuti**:
sono gli stessi oggetti che il codice di produzione costruisce, così un test che passa dal
finto prova gli strumenti veri e non una copia. Il client di produzione si prova a parte
(`tests/services/test_claude_client.py`).
"""

import asyncio
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from claude_agent_sdk import SdkMcpTool

from app.domain.meal_chat import FailureKind
from app.services.claude.client import (
    ClaudeClient,
    ClaudeEvent,
    ClaudeFailure,
    ClaudeUsage,
    Effort,
    TextDelta,
    TurnFailed,
    TurnFinished,
)


@dataclass
class Say:
    text: str


@dataclass
class UseTool:
    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class Finish:
    input_tokens: int | None = 100
    output_tokens: int | None = 20


@dataclass
class Fail:
    kind: FailureKind
    resets_at: datetime | None = None


class Hang:
    """Aspetta per sempre: serve al tempo massimo."""


Step = Say | UseTool | Finish | Fail | Hang


class FakeClaude(ClaudeClient):
    def __init__(self, script: Sequence[Step]):
        self.script = list(script)
        self.calls: list[dict[str, Any]] = []
        self.tool_results: list[dict[str, Any]] = []

    async def run(
        self,
        *,
        system_prompt: str,
        prompt: str,
        tools: Sequence[SdkMcpTool],
        effort: Effort,
        max_turns: int,
    ) -> AsyncIterator[ClaudeEvent]:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "prompt": prompt,
                "tool_names": [t.name for t in tools],
                "effort": effort,
                "max_turns": max_turns,
            }
        )
        by_name = {t.name: t for t in tools}
        said: list[str] = []
        for step in self.script:
            if isinstance(step, Say):
                said.append(step.text)
                for i in range(0, len(step.text), 5):
                    yield TextDelta(step.text[i : i + 5])
            elif isinstance(step, UseTool):
                self.tool_results.append(await by_name[step.name].handler(step.args))
            elif isinstance(step, Finish):
                yield TurnFinished(
                    "\n\n".join(said),
                    ClaudeUsage(
                        model="claude-opus-5-5",
                        session_id="sessione-finta",
                        input_tokens=step.input_tokens,
                        output_tokens=step.output_tokens,
                    ),
                )
                return
            elif isinstance(step, Fail):
                yield TurnFailed(ClaudeFailure(step.kind, step.resets_at, "finto"))
                return
            elif isinstance(step, Hang):
                await asyncio.Event().wait()
