import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { RegistryScreen } from "./RegistryScreen";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import type { Ingredient, Product } from "../../domain/types";

const BURRO: Ingredient = {
  id: "i-burro", name: "burro", display_name: "Burro", category: "latticini", kind: "food",
};
const REGGIANO: Product = {
  id: "p-reggiano", ingredient_id: "i-burro", ingredient_name: "burro",
  name: "Parmigiano Reggiano 24 mesi",
  brand: "Latteria", barcode: "8009876543217", source: "custom", nutrients: null, image_url: null,
};

function stubRoutedFetch(route: (path: string) => [unknown, number]) {
  const spy = vi.fn((url: unknown) => {
    const [body, status] = route(String(url));
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

// Il predicato vero di App.tsx, non un `retry: false` di comodo (prima lezione di
// CLAUDE.md): con risposte riuscite non cambia niente.
function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: defaultQueryRetryPredicate } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <RegistryScreen />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("RegistryScreen", () => {
  it("senza testo spiega cosa si trova qui, e non chiede niente al server", () => {
    const spy = stubRoutedFetch(() => [[], 200]);
    renderScreen();

    expect(screen.getByRole("heading", { name: "Anagrafica" })).toBeInTheDocument();
    expect(screen.getByText(/anche quel che in dispensa non c'è/)).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
  });

  it("cerca nelle due anagrafiche e mostra due gruppi, ogni risultato con la sua scheda", async () => {
    const spy = stubRoutedFetch((path) => {
      if (path.includes("/ingredients/search")) return [[BURRO], 200];
      if (path.includes("/products/search")) return [[REGGIANO], 200];
      return [{}, 404];
    });
    renderScreen();

    await userEvent.type(screen.getByLabelText("Cerca in anagrafica"), "parmig");

    expect(await screen.findByRole("link", { name: /Burro/ })).toHaveAttribute(
      "href", "/anagrafica/ingrediente/i-burro"
    );
    expect(await screen.findByRole("link", { name: /Parmigiano Reggiano 24 mesi/ })).toHaveAttribute(
      "href", "/anagrafica/prodotto/p-reggiano"
    );
    expect(screen.getByRole("heading", { name: "Ingredienti" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Prodotti" })).toBeInTheDocument();
    // l'anagrafica corregge anche il non alimentare: la ricerca non filtra il `kind`
    await waitFor(() =>
      expect(spy.mock.calls.some(([url]) => String(url).includes("/ingredients/search"))).toBe(true)
    );
    expect(spy.mock.calls.some(([url]) => String(url).includes("kind="))).toBe(false);
  });

  it("un gruppo vuoto lo dice, e l'altro resta", async () => {
    stubRoutedFetch((path) => {
      if (path.includes("/ingredients/search")) return [[], 200];
      if (path.includes("/products/search")) return [[REGGIANO], 200];
      return [{}, 404];
    });
    renderScreen();

    await userEvent.type(screen.getByLabelText("Cerca in anagrafica"), "reggiano");

    expect(await screen.findByText("Nessun ingrediente con questo nome.")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /Parmigiano Reggiano 24 mesi/ })).toBeInTheDocument();
  });
});
