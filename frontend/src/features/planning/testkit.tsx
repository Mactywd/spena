import { vi } from "vitest";
import { render } from "@testing-library/react";
import { QueryClientProvider, type QueryClient } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import { createTestQueryClient } from "../../test/queryClient";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import type { ChatMessage, MealProposal, PlanningChat, ProposalRow } from "../../domain/types";

export function planningChat(extra: Partial<PlanningChat> = {}): PlanningChat {
  return {
    conversation_id: "k1", focus: null, messages: [], replying: false, concluded: false,
    claude_ready: true, claude_notice: null, ...extra,
  };
}

export function message(extra: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: "u1", role: "user", text: "Pianifichiamo la settimana", status: "sent", notice: null,
    created_at: "2026-11-13T10:00:00Z", changes: [], ...extra,
  };
}

export function proposalRow(extra: Partial<ProposalRow> = {}): ProposalRow {
  return {
    day: "2026-11-13", slot: "dinner", dish: "Frittata di spinaci", sides: "insalata · pane",
    effect: "new", occupant: null, meal_id: null, ...extra,
  };
}

export function proposal(extra: Partial<MealProposal> = {}): MealProposal {
  return {
    id: "p1", kind: "official", status: "open", rows: [proposalRow()],
    created_at: "2026-11-13T10:00:00Z", ...extra,
  };
}

export const FOLLOW_UP =
  "Ho messo nella settimana: venerdì 13 novembre · cena, Frittata di spinaci. Mandami la scheda dei cambi.";

/** Una risposta in streaming che il test scrive un evento alla volta. */
export function liveStream() {
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

type Reply = Response | Promise<Response> | [unknown, number];
export type Handler = (url: string, init?: RequestInit) => Reply;

export function stubFetch(handler: Handler) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const reply = handler(String(url), init);
    if (reply instanceof Response || reply instanceof Promise) return Promise.resolve(reply);
    const [body, status] = reply;
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

/** I corpi delle richieste con quel metodo e quell'indirizzo, in ordine. */
export function requests(spy: ReturnType<typeof stubFetch>, method: string, path: string) {
  return spy.mock.calls
    .filter(([url, init]) => ((init as RequestInit | undefined)?.method ?? "GET") === method && String(url) === path)
    .map(([, init]) => {
      const body = (init as RequestInit | undefined)?.body;
      return body ? JSON.parse(String(body)) : null;
    });
}

/** Gli indirizzi delle `POST`, in ordine. */
export function postUrls(spy: ReturnType<typeof stubFetch>) {
  return spy.mock.calls
    .filter(([, init]) => (init as RequestInit | undefined)?.method === "POST")
    .map(([url]) => String(url));
}

let router: ReturnType<typeof createMemoryRouter> | null = null;

/** L'indirizzo a cui è arrivata la schermata, con la query. */
export function where(): string {
  const location = router!.state.location;
  return `${location.pathname}${location.search}`;
}

export function renderAt(ui: ReactNode, path: string, client: QueryClient = createTestQueryClient()) {
  router = createMemoryRouter(
    [
      { path: "/pasti", element: <p>la settimana</p> },
      { path: "*", element: ui },
    ],
    { initialEntries: [path] }
  );
  render(
    <QueryClientProvider client={client}>
      <NoticeProvider>
        <RouterProvider router={router} />
      </NoticeProvider>
    </QueryClientProvider>
  );
  return client;
}
