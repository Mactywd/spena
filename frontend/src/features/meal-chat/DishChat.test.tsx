import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider, useQuery, type QueryClient } from "@tanstack/react-query";
import { apiFetch } from "../../api/client";
import { createTestQueryClient } from "../../test/queryClient";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import { DishChat } from "./DishChat";
import { card } from "../change-cards/testkit";
import type { ChatMessage, DishChat as DishChatData, Meal } from "../../domain/types";

const NOT_CONFIGURED = "Claude non è collegato: manca il token del piano sul server.";
const PLAN_LIMIT = "Claude non risponde: hai raggiunto il limite del piano, riprova dopo le 18:40";

function chat(extra: Partial<DishChatData> = {}): DishChatData {
  return {
    meal_id: "m1", conversation_id: "k1", messages: [], replying: false, highlight: null,
    claude_ready: true, claude_notice: null, ...extra,
  };
}

function message(extra: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: "u1", role: "user", text: "Fallo con gli spinaci", status: "sent", notice: null,
    created_at: "2026-11-13T19:00:00Z", changes: [], ...extra,
  };
}

const CHANGE = {
  id: "c1", summary: "spinaci congelati, padella unica", created_recipe: false,
  undone: false, undoable: true,
};

/** Una risposta in streaming che il test scrive un evento alla volta. */
function liveStream() {
  const encoder = new TextEncoder();
  let controller!: ReadableStreamDefaultController<Uint8Array>;
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      controller = c;
    },
  });
  return {
    response: new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } }),
    send(name: string, data: unknown) {
      controller.enqueue(encoder.encode(`event: ${name}\ndata: ${JSON.stringify(data)}\n\n`));
    },
    close() {
      controller.close();
    },
  };
}

type Reply = Response | [unknown, number];
type Handler = (url: string, init?: RequestInit) => Reply;

function stubFetch(handler: Handler) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const reply = handler(String(url), init);
    if (reply instanceof Response) return Promise.resolve(reply);
    const [body, status] = reply;
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function requests(spy: ReturnType<typeof stubFetch>, method: string, path: string) {
  return spy.mock.calls
    .filter(([url, init]) => ((init as RequestInit | undefined)?.method ?? "GET") === method && String(url) === path)
    .map(([, init]) => {
      const body = (init as RequestInit | undefined)?.body;
      return body ? JSON.parse(String(body)) : null;
    });
}

/** La ricetta del pasto com'è letta dal dettaglio, con la sua chiave. */
function RecipeProbe() {
  useQuery({ queryKey: ["recipe", "r1", null], queryFn: () => apiFetch("/recipes/r1") });
  return null;
}

function renderChat({ hasRecipe = true, client = createTestQueryClient() } = {}) {
  render(
    <QueryClientProvider client={client}>
      <NoticeProvider>
        <RecipeProbe />
        <DishChat mealId="m1" hasRecipe={hasRecipe} />
      </NoticeProvider>
    </QueryClientProvider>
  );
  return client;
}

function withMeal(client: QueryClient) {
  const meal = { id: "m1", recipe: { id: "r1", title: "Pollo", in_book: false } } as Meal;
  client.setQueryData(["meals", "meal", "m1"], meal);
  return client;
}

afterEach(() => vi.unstubAllGlobals());

describe("la chat del piatto", () => {
  it("vuota, con la ricetta, spiega che la ricetta si aggiorna qui sopra", async () => {
    stubFetch(() => [chat(), 200]);
    renderChat();
    expect(screen.getByRole("heading", { name: "Chat con Claude" })).toBeInTheDocument();
    expect(
      await screen.findByText("Chiedi a Claude di cambiare la ricetta: la vedi aggiornata qui sopra.")
    ).toBeInTheDocument();
  });

  it("vuota, senza ricetta, invita a farla scrivere", async () => {
    stubFetch(() => [chat(), 200]);
    renderChat({ hasRecipe: false });
    expect(
      await screen.findByText("Chiedi a Claude di scrivere la ricetta di questo piatto.")
    ).toBeInTheDocument();
  });

  it("«Invia» manda il testo, il fumetto compare, i `delta` compongono la risposta e `done` la chiude", async () => {
    const stream = liveStream();
    const spy = stubFetch((_url, init) =>
      init?.method === "POST" ? stream.response : [chat(), 200]
    );
    renderChat();
    const field = await screen.findByRole("textbox", { name: "Messaggio per Claude" });
    // campo vuoto = «non ancora»: aria-disabled col perché, mai `disabled` nativo
    const invia = screen.getByRole("button", { name: "Invia" });
    expect(invia).toHaveAttribute("aria-disabled", "true");
    expect(invia.hasAttribute("disabled")).toBe(false);
    expect(invia).toHaveAccessibleDescription("Scrivi prima il messaggio.");
    expect(screen.getByText("Scrivi prima il messaggio.")).toBeInTheDocument();
    await userEvent.type(field, "Fallo con gli spinaci");
    await userEvent.click(screen.getByRole("button", { name: "Invia" }));

    expect(requests(spy, "POST", "/api/v1/meals/m1/chat/messages")).toEqual([
      { text: "Fallo con gli spinaci" },
    ]);
    expect(field).toHaveValue("");
    const user = message({ status: "pending" });
    stream.send("start", { message: user });
    expect(await screen.findByText("Fallo con gli spinaci")).toBeInTheDocument();
    stream.send("delta", { text: "Uso gli spinaci" });
    stream.send("delta", { text: " congelati." });
    expect(await screen.findByText("Uso gli spinaci congelati.")).toBeInTheDocument();
    expect(screen.getByText("Claude sta scrivendo…")).toBeInTheDocument();

    const answer = message({ id: "a1", role: "assistant", text: "Uso gli spinaci congelati." });
    stream.send("done", { chat: chat({ messages: [{ ...user, status: "sent" }, answer] }) });
    stream.close();
    await waitFor(() => expect(screen.queryByText("Claude sta scrivendo…")).not.toBeInTheDocument());
    expect(screen.getByText("Uso gli spinaci congelati.")).toBeInTheDocument();
    expect(screen.getByText("Fallo con gli spinaci")).toBeInTheDocument();
  });

  it("un `change` fa rileggere la ricetta del pasto", async () => {
    const stream = liveStream();
    const spy = stubFetch((url, init) => {
      if (init?.method === "POST") return stream.response;
      if (url.endsWith("/recipes/r1")) return [{ id: "r1" }, 200];
      return [chat(), 200];
    });
    renderChat({ client: withMeal(createTestQueryClient()) });
    await waitFor(() => expect(requests(spy, "GET", "/api/v1/recipes/r1")).toHaveLength(1));
    await userEvent.type(await screen.findByRole("textbox", { name: "Messaggio per Claude" }), "spinaci");
    await userEvent.click(screen.getByRole("button", { name: "Invia" }));
    stream.send("start", { message: message({ status: "pending", text: "spinaci" }) });
    stream.send("change", { change: CHANGE });
    await waitFor(() => expect(requests(spy, "GET", "/api/v1/recipes/r1")).toHaveLength(2));
    stream.close();
  });

  it("mentre Claude risponde «Invia» è `busy`: aria-disabled, niente `disabled` nativo, e non rimanda", async () => {
    const stream = liveStream();
    const spy = stubFetch((_url, init) =>
      init?.method === "POST" ? stream.response : [chat(), 200]
    );
    renderChat();
    const field = await screen.findByRole("textbox", { name: "Messaggio per Claude" });
    await userEvent.type(field, "uno");
    await userEvent.click(screen.getByRole("button", { name: "Invia" }));
    await waitFor(() => expect(requests(spy, "POST", "/api/v1/meals/m1/chat/messages")).toHaveLength(1));
    await userEvent.type(field, "due");
    const invia = screen.getByRole("button", { name: "Invia" });
    expect(invia).toHaveAttribute("aria-disabled", "true");
    expect(invia.hasAttribute("disabled")).toBe(false);
    await userEvent.click(invia);
    expect(requests(spy, "POST", "/api/v1/meals/m1/chat/messages")).toHaveLength(1);
    stream.close();
  });

  it("un 503 lascia il testo nel campo e dice perché", async () => {
    stubFetch((_url, init) =>
      init?.method === "POST"
        ? [{ code: "claude_not_configured", detail: NOT_CONFIGURED }, 503]
        : [chat(), 200]
    );
    renderChat();
    const field = await screen.findByRole("textbox", { name: "Messaggio per Claude" });
    await userEvent.type(field, "Fallo con gli spinaci");
    await userEvent.click(screen.getByRole("button", { name: "Invia" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(NOT_CONFIGURED);
    expect(field).toHaveValue("Fallo con gli spinaci");
  });

  it("un 409 «claude_busy» lascia il testo nel campo e dice perché", async () => {
    stubFetch((_url, init) =>
      init?.method === "POST"
        ? [{ code: "claude_busy", detail: "Claude sta ancora rispondendo." }, 409]
        : [chat(), 200]
    );
    renderChat();
    const field = await screen.findByRole("textbox", { name: "Messaggio per Claude" });
    await userEvent.type(field, "ancora");
    await userEvent.click(screen.getByRole("button", { name: "Invia" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Claude sta ancora rispondendo.");
    expect(field).toHaveValue("ancora");
  });

  it("un `error` mette l'avviso sotto il messaggio, e «Riprova» lo rimanda con `retry_of`", async () => {
    const first = liveStream();
    const second = liveStream();
    const streams = [first, second];
    const spy = stubFetch((_url, init) =>
      init?.method === "POST" ? streams.shift()!.response : [chat(), 200]
    );
    renderChat();
    await userEvent.type(await screen.findByRole("textbox", { name: "Messaggio per Claude" }), "Fallo con gli spinaci");
    await userEvent.click(screen.getByRole("button", { name: "Invia" }));
    const user = message({ status: "pending" });
    first.send("start", { message: user });
    first.send("error", {
      code: "plan_limit",
      notice: PLAN_LIMIT,
      chat: chat({ messages: [{ ...user, status: "failed", notice: PLAN_LIMIT }] }),
    });
    first.close();
    expect(await screen.findByText(PLAN_LIMIT)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Riprova" }));
    expect(requests(spy, "POST", "/api/v1/meals/m1/chat/messages")).toEqual([
      { text: "Fallo con gli spinaci" },
      { text: "Fallo con gli spinaci", retry_of: "u1" },
    ]);
    second.close();
  });

  it("un `error` con `chat: null` non svuota la chat: la rilegge, e il messaggio fallito resta con «Riprova»", async () => {
    const stream = liveStream();
    const user = message({ status: "pending" });
    const failed = chat({ messages: [{ ...user, status: "failed", notice: PLAN_LIMIT }] });
    let gets = 0;
    const spy = stubFetch((_url, init) => {
      if (init?.method === "POST") return stream.response;
      gets += 1;
      return [gets === 1 ? chat() : failed, 200];
    });
    renderChat();
    await userEvent.type(await screen.findByRole("textbox", { name: "Messaggio per Claude" }), "Fallo con gli spinaci");
    await userEvent.click(screen.getByRole("button", { name: "Invia" }));
    stream.send("start", { message: user });
    stream.send("error", { code: "unavailable", notice: PLAN_LIMIT, chat: null });
    stream.close();
    await waitFor(() => expect(requests(spy, "GET", "/api/v1/meals/m1/chat")).toHaveLength(2));
    expect(await screen.findByText(PLAN_LIMIT)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Riprova" })).toBeInTheDocument();
  });

  it("«Annulla» manda l'annullamento e conferma «Modifica annullata.»", async () => {
    const answer = message({ id: "a1", role: "assistant", text: "Fatto.", changes: [CHANGE] });
    const spy = stubFetch((_url, init) =>
      init?.method === "POST"
        ? [chat({ messages: [message(), { ...answer, changes: [{ ...CHANGE, undone: true, undoable: false }] }] }), 200]
        : [chat({ messages: [message(), answer] }), 200]
    );
    renderChat();
    await userEvent.click(await screen.findByRole("button", { name: "Annulla" }));
    expect(await screen.findByText("Modifica annullata.")).toBeInTheDocument();
    expect(requests(spy, "POST", "/api/v1/meals/m1/chat/changes/c1/undo")).toHaveLength(1);
    expect(
      screen.getByText("Ricetta aggiornata: spinaci congelati, padella unica — annullata")
    ).toBeInTheDocument();
  });

  it("un «Annulla» rifiutato mostra il perché", async () => {
    const answer = message({ id: "a1", role: "assistant", text: "Fatto.", changes: [CHANGE] });
    stubFetch((_url, init) =>
      init?.method === "POST"
        ? [{ code: "change_stale", detail: "La ricetta è cambiata dopo questa modifica." }, 409]
        : [chat({ messages: [message(), answer] }), 200]
    );
    renderChat();
    await userEvent.click(await screen.findByRole("button", { name: "Annulla" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "La ricetta è cambiata dopo questa modifica."
    );
  });

  it("senza Claude, l'avviso in testa c'è prima di scrivere", async () => {
    stubFetch(() => [chat({ claude_ready: false, claude_notice: NOT_CONFIGURED }), 200]);
    renderChat();
    expect(await screen.findByRole("alert")).toHaveTextContent(NOT_CONFIGURED);
  });

  it("uno stream finito senza `done` né `error` fa rileggere la chat, e non resta «sta scrivendo»", async () => {
    const stream = liveStream();
    const spy = stubFetch((_url, init) => (init?.method === "POST" ? stream.response : [chat(), 200]));
    renderChat();
    await userEvent.type(await screen.findByRole("textbox", { name: "Messaggio per Claude" }), "ciao");
    await userEvent.click(screen.getByRole("button", { name: "Invia" }));
    stream.send("start", { message: message({ status: "pending", text: "ciao" }) });
    stream.send("delta", { text: "Ci" });
    expect(await screen.findByText("Claude sta scrivendo…")).toBeInTheDocument();
    stream.close();
    await waitFor(() => expect(requests(spy, "GET", "/api/v1/meals/m1/chat")).toHaveLength(2));
    await waitFor(() => expect(screen.queryByText("Claude sta scrivendo…")).not.toBeInTheDocument());
  });

  it("una scheda dei cambi arriva sotto il fumetto, con «Applica»", async () => {
    const answer = message({ id: "a1", role: "assistant", text: "Ecco i cambi.", cards: [card()] });
    stubFetch((url) => (url.includes("/pantry") ? [[], 200] : [chat({ messages: [answer] }), 200]));
    renderChat();
    expect(await screen.findByText("Ecco i cambi.")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Applica" })).toBeInTheDocument();
  });
});
