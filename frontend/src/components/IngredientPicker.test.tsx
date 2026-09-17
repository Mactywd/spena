import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { IngredientPicker } from "./IngredientPicker";

/** Un fetch che risponde in base al percorso: qui serve solo per registrare quale
 * rotta è stata chiamata, il corpo non conta. */
function stubRoutedFetch(route: (path: string, init?: RequestInit) => [unknown, number]) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = route(String(url), init);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function renderWithClient(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("IngredientPicker", () => {
  it("chiede al server solo il cibo quando glielo si dice, e lo mette nella chiave", async () => {
    // due montaggi nello stesso QueryClient, stessa parola cercata: senza il kind
    // nella chiave il secondo leggerebbe la risposta del primo, e il filtro
    // diventerebbe una decorazione
    const chiamate: string[] = [];
    stubRoutedFetch((path) => {
      chiamate.push(path);
      return [[], 200];
    });

    renderWithClient(
      <>
        <IngredientPicker label="Aggiungi in dispensa" failureNote="x" onPick={() => {}} />
        <IngredientPicker label="Contiene ingredienti" failureNote="x" kind="food" onPick={() => {}} />
      </>
    );
    fireEvent.change(screen.getByLabelText("Aggiungi in dispensa"), { target: { value: "deter" } });
    fireEvent.change(screen.getByLabelText("Contiene ingredienti"), { target: { value: "deter" } });

    await waitFor(() => expect(chiamate.length).toBe(2));
    expect(chiamate.some((c) => c.includes("kind=food"))).toBe(true);
    expect(chiamate.some((c) => !c.includes("kind="))).toBe(true);
  });
});
