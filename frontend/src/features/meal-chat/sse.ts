import type { ChatStreamEvent, DishChat } from "../../domain/types";

/** Un blocco SSE (le righe fra due `\n\n`) ridotto a un evento della chat, o a niente:
 * i commenti (`: ping`), i nomi sconosciuti e un `data` che non è JSON si saltano. */
function parseBlock<TChat>(block: string): ChatStreamEvent<TChat> | null {
  let name = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line === "" || line.startsWith(":")) continue;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    // dopo i due punti, uno spazio solo fa parte della sintassi, non del valore
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") name = value;
    else if (field === "data") data.push(value);
  }
  if (data.length === 0) return null;
  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(data.join("\n")) as Record<string, unknown>;
  } catch {
    return null;
  }
  switch (name) {
    case "start":
      return { name, message: payload.message } as ChatStreamEvent<TChat>;
    case "delta":
      return { name, text: payload.text } as ChatStreamEvent<TChat>;
    case "change":
      return { name, change: payload.change } as ChatStreamEvent<TChat>;
    case "proposal":
      return { name, proposal: payload.proposal } as ChatStreamEvent<TChat>;
    case "card":
      return { name, card: payload.card } as ChatStreamEvent<TChat>;
    case "done":
      return { name, chat: payload.chat } as ChatStreamEvent<TChat>;
    case "error":
      return { name, code: payload.code, notice: payload.notice, chat: payload.chat } as ChatStreamEvent<TChat>;
    default:
      return null;
  }
}

/** Legge una risposta `text/event-stream` fino in fondo, passando gli eventi in ordine.
 * I pezzi arrivano tagliati dove capita: si accumulano finché un `\n\n` chiude il blocco. */
export async function readSse<TChat = DishChat>(
  response: Response,
  onEvent: (event: ChatStreamEvent<TChat>) => void
): Promise<void> {
  if (!response.body) return;
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const flush = (final: boolean) => {
    buffer = buffer.replace(/\r\n/g, "\n");
    let end = buffer.indexOf("\n\n");
    while (end !== -1) {
      const event = parseBlock<TChat>(buffer.slice(0, end));
      buffer = buffer.slice(end + 2);
      if (event) onEvent(event);
      end = buffer.indexOf("\n\n");
    }
    if (final && buffer.trim() !== "") {
      const event = parseBlock<TChat>(buffer);
      buffer = "";
      if (event) onEvent(event);
    }
  };
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    flush(false);
  }
  buffer += decoder.decode();
  flush(true);
}
