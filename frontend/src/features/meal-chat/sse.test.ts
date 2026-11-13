import { describe, expect, it } from "vitest";
import { readSse } from "./sse";
import type { ChatStreamEvent } from "../../domain/types";

/** Una risposta in streaming che arriva a pezzi, tagliati dove capita. */
function streamed(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(body, { headers: { "Content-Type": "text/event-stream" } });
}

async function eventsOf(response: Response): Promise<ChatStreamEvent[]> {
  const seen: ChatStreamEvent[] = [];
  await readSse(response, (event) => seen.push(event));
  return seen;
}

describe("readSse", () => {
  it("rimette insieme gli eventi spezzati a metà riga, in ordine, saltando il `: ping`", async () => {
    const response = streamed([
      'event: delta\ndata: {"te',
      'xt": "Ciao"}\n\n: ping\n\nevent: del',
      'ta\ndata: {"text": " Mattia"}\n\n',
    ]);
    expect(await eventsOf(response)).toEqual([
      { name: "delta", text: "Ciao" },
      { name: "delta", text: " Mattia" },
    ]);
  });

  it("unisce un `data:` scritto su due righe", async () => {
    const response = streamed(['event: delta\ndata: {"text":\ndata:  "due righe"}\n\n']);
    expect(await eventsOf(response)).toEqual([{ name: "delta", text: "due righe" }]);
  });

  it("ignora un evento dal nome sconosciuto", async () => {
    const response = streamed([
      'event: mistero\ndata: {"text": "no"}\n\n',
      'event: delta\ndata: {"text": "sì"}\n\n',
    ]);
    expect(await eventsOf(response)).toEqual([{ name: "delta", text: "sì" }]);
  });

  it("legge `change`, `done` ed `error` con i loro dati", async () => {
    const change = { id: "c1", summary: "spinaci", created_recipe: false, undone: false, undoable: true };
    const chat = {
      meal_id: "m1", conversation_id: "k1", messages: [], replying: false, highlight: null,
      claude_ready: true, claude_notice: null,
    };
    const response = streamed([
      `event: change\ndata: ${JSON.stringify({ change })}\n\n`,
      `event: done\ndata: ${JSON.stringify({ chat })}\n\n`,
      `event: error\ndata: ${JSON.stringify({ code: "timeout", notice: "Tardi.", chat })}\n\n`,
    ]);
    expect(await eventsOf(response)).toEqual([
      { name: "change", change },
      { name: "done", chat },
      { name: "error", code: "timeout", notice: "Tardi.", chat },
    ]);
  });
});
