import { vi } from "vitest";
import { render } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import { createTestQueryClient } from "../../test/queryClient";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import type { ChangeCard, ChangeRow, PantryItem } from "../../domain/types";

export function row(extra: Partial<ChangeRow> = {}): ChangeRow {
  return {
    id: "r1", kind: "pantry", label: "Ricotta", from_status: "available", to_status: "finished",
    listed: false, checked: true, editable: true, note: null, applied: null, ...extra,
  };
}

export function card(extra: Partial<ChangeCard> = {}): ChangeCard {
  return {
    id: "c1", kind: "forward", status: "proposed", list_only: false,
    title: "Cambi per la cena di martedì", meals: [
      { id: "m1", day: "2026-11-10", slot: "dinner", dish: "Lasagne", recipe_id: null },
    ],
    rows: [row()], created_at: "2026-11-10T10:00:00Z", applied_at: null, ...extra,
  };
}

export function pantryItem(name: string, id = "p1"): PantryItem {
  return { id, ingredient_name: name, product_name: null, status: "available" } as PantryItem;
}

export type Handler = (url: string, init?: RequestInit) => [unknown, number];

export function stubFetch(handler: Handler) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = handler(String(url), init);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

export function posts(spy: ReturnType<typeof stubFetch>) {
  return spy.mock.calls
    .filter(([, init]) => (init as RequestInit | undefined)?.method === "POST")
    .map(([url, init]) => ({
      url: String(url),
      body: (init as RequestInit).body ? JSON.parse(String((init as RequestInit).body)) : null,
    }));
}

export function renderWith(ui: ReactNode, path = "/") {
  return render(
    <QueryClientProvider client={createTestQueryClient()}>
      <NoticeProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/pasti" element={<p>la settimana</p>} />
            <Route path="/pasti/cambi/:id" element={ui} />
            <Route path="*" element={ui} />
          </Routes>
        </MemoryRouter>
      </NoticeProvider>
    </QueryClientProvider>
  );
}
