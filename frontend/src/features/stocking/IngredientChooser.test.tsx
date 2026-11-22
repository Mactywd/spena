import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { createTestQueryClient } from "../../test/queryClient";
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

function renderChooser(busy = false, trim?: boolean) {
  const onChosen = vi.fn();
  const client = createTestQueryClient();
  const { unmount } = render(
    <QueryClientProvider client={client}>
      <IngredientChooser
        label="Cosa hai comprato?"
        failureNote="Puoi comunque aggiungerlo."
        initialTerm="ceci neri"
        onChosen={onChosen}
        busy={busy}
        trim={trim}
        before={<p>prima</p>}
        after={<button type="button">dopo</button>}
      />
    </QueryClientProvider>
  );
  return { onChosen, unmount };
}

describe("IngredientChooser", () => {
  it("cerca col taglio, salvo trim={false}", async () => {
    const spy = stubRoutedFetch(() => [[], 200]);
    const trims = () =>
      spy.mock.calls
        .map(([url]) => new URL(String(url), "http://localhost"))
        .filter((u) => u.pathname.endsWith("/ingredients/search"))
        .map((u) => u.searchParams.get("trim"));

    const first = renderChooser();
    await vi.waitFor(() => expect(trims()).toEqual([null]));
    first.unmount();

    renderChooser(false, false);
    await vi.waitFor(() => expect(trims()).toEqual([null, "false"]));
  });

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
