import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { IngredientChooser } from "./IngredientChooser";
import type { Ingredient } from "../../domain/types";

const CECI_NERI: Ingredient = {
  id: "i4", name: "ceci neri", display_name: "ceci neri", category: "legumi", kind: "food",
};

/** Un fetch che risponde in base a percorso e metodo. */
function stubRoutedFetch(route: (path: string, init?: RequestInit) => [unknown, number]) {
  const spy = vi.fn((input: unknown, init?: RequestInit) => {
    const [body, status] = route(String(input), init);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function renderChooser(busy = false) {
  const onChosen = vi.fn();
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <IngredientChooser
        label="Cosa hai comprato?"
        failureNote="Puoi comunque aggiungerlo."
        initialTerm="ceci neri"
        onChosen={onChosen}
        busy={busy}
        before={<p>prima</p>}
        after={<button type="button">dopo</button>}
      />
    </QueryClientProvider>
  );
  return { onChosen };
}

describe("IngredientChooser", () => {
  it("quel che sta prima e dopo il selettore c'è solo mentre si sceglie, e l'ingrediente creato è la scelta", async () => {
    stubRoutedFetch((path, init) =>
      path.endsWith("/ingredients") && init?.method === "POST" ? [CECI_NERI, 201] : [[], 200]
    );
    const { onChosen } = renderChooser();
    expect(screen.getByText("prima")).toBeDefined();
    expect(screen.getByRole("button", { name: "dopo" })).toBeDefined();

    // l'anagrafica non ha «ceci neri»: si crea qui, col nome da correggere
    await userEvent.click(await screen.findByRole("button", { name: "Aggiungi «ceci neri»" }));
    expect(screen.getByLabelText("Come si chiama in generale?")).toHaveValue("ceci neri");
    expect(screen.queryByText("prima")).toBeNull();
    expect(screen.queryByRole("button", { name: "dopo" })).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Crea l'ingrediente" }));
    await vi.waitFor(() => expect(onChosen).toHaveBeenCalledWith(CECI_NERI));
  });

  it("mentre la scelta di prima è in volo, il campo è spento", () => {
    stubRoutedFetch(() => [[], 200]);
    renderChooser(true);
    // spento senza `disabled`, che toglierebbe il fuoco (pulizie del 2026-10-13)
    const campo = screen.getByRole("textbox", { name: "Cosa hai comprato?" });
    expect(campo).toHaveAttribute("aria-disabled", "true");
    expect(campo).toHaveAttribute("readonly");
    expect(campo).not.toBeDisabled();
  });
});
