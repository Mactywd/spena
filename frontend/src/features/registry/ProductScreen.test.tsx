import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { ProductScreen } from "./ProductScreen";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import type { Ingredient, ProductDetail } from "../../domain/types";

const REGGIANO: ProductDetail = {
  id: "p-reggiano", name: "Parmigiano Reggiano 24 mesi", brand: "Latteria",
  barcode: "8009876543217", valid_checksum: true,
  ingredient: { id: "i-burro", name: "burro", display_name: "Burro" },
  pantry_items: [{ id: "v1", status: "available", expires_on: null }],
};
const PARMIGIANO: Ingredient = {
  id: "i-parmigiano", name: "parmigiano", display_name: "Parmigiano", category: "latticini", kind: "food",
};

type FetchRoute = (path: string, init?: RequestInit) => [unknown, number];

function stubRoutedFetch(route: FetchRoute) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = route(String(url), init);
    return Promise.resolve(
      status === 204 ? new Response(null, { status }) : new Response(JSON.stringify(body), { status })
    );
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function bodiesOf(spy: ReturnType<typeof stubRoutedFetch>, method: string) {
  return spy.mock.calls
    .filter(([, init]) => (init as RequestInit | undefined)?.method === method)
    .map(([, init]) => JSON.parse(String((init as RequestInit).body ?? "null")));
}

function Where() {
  const location = useLocation();
  return <p>dove: {location.pathname + location.search}</p>;
}

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: defaultQueryRetryPredicate } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/anagrafica/prodotto/:id" element={<ProductScreen />} />
          <Route path="*" element={<Where />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function base(path: string): [unknown, number] | null {
  if (path.includes("/ingredients/search")) return [[PARMIGIANO], 200];
  if (path.endsWith("/products/p-reggiano")) return [REGGIANO, 200];
  return null;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ProductScreen", () => {
  it("nome e marca si salvano ciascuno col suo «Salva»; la marca vuota si toglie", async () => {
    const spy = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") return [REGGIANO, 200];
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/prodotto/p-reggiano");

    const nome = await screen.findByLabelText("Nome");
    await userEvent.clear(nome);
    await userEvent.type(nome, "Parmigiano Reggiano 30 mesi");
    await userEvent.click(screen.getByRole("button", { name: "Salva nome" }));
    await waitFor(() => expect(bodiesOf(spy, "PATCH")).toHaveLength(1));

    await userEvent.clear(screen.getByLabelText("Marca"));
    await userEvent.click(screen.getByRole("button", { name: "Salva marca" }));

    await waitFor(() =>
      expect(bodiesOf(spy, "PATCH")).toEqual([
        { name: "Parmigiano Reggiano 30 mesi" },
        { brand: null },
      ])
    );
  });

  it("un salvataggio fallito lascia il campo com'era scritto, e l'errore accanto", async () => {
    stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") return [{ detail: "rotto" }, 500];
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/prodotto/p-reggiano");

    const nome = await screen.findByLabelText("Nome");
    await userEvent.clear(nome);
    await userEvent.type(nome, "Parmigiano Reggiano 30 mesi");
    await userEvent.click(screen.getByRole("button", { name: "Salva nome" }));

    expect(
      await screen.findByText("Non sono riuscito a salvare. Quel che hai scritto è ancora qui: riprova.")
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Nome")).toHaveValue("Parmigiano Reggiano 30 mesi");
  });

  it("il nome vuoto tiene «Salva nome» spento, e il motivo scritto sotto (F17)", async () => {
    stubRoutedFetch((path) => base(path) ?? [{}, 404]);
    renderAt("/anagrafica/prodotto/p-reggiano");

    const nome = await screen.findByLabelText("Nome");
    await userEvent.clear(nome);

    expect(screen.getByRole("button", { name: "Salva nome" })).toBeDisabled();
    expect(screen.getByText("Il campo «Nome» non può restare vuoto.")).toBeInTheDocument();

    // la marca, invece, si può svuotare: non è obbligatoria (F17)
    await userEvent.clear(screen.getByLabelText("Marca"));
    expect(screen.getByRole("button", { name: "Salva marca" })).not.toBeDisabled();
  });

  it("«Spostalo»: la scelta dell'ingrediente, senza filtro sul tipo, e il fatto detto dopo", async () => {
    const spostato: ProductDetail = {
      ...REGGIANO,
      ingredient: { id: "i-parmigiano", name: "parmigiano", display_name: "Parmigiano" },
    };
    const spy = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") return [spostato, 200];
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/prodotto/p-reggiano");

    // «Spostalo» sta nel gruppo di icone accanto al titolo (Consegna 6a), senza più la
    // domanda che lo introduceva
    expect(await screen.findByRole("toolbar", { name: "Correzioni del prodotto" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Spostalo" }));
    await userEvent.type(screen.getByLabelText("Sposta sotto"), "parmig");
    await userEvent.click(await screen.findByRole("option", { name: /Parmigiano/ }));

    expect(
      await screen.findByText("Spostato sotto «Parmigiano», con 1 elemento di dispensa.")
    ).toBeInTheDocument();
    expect(bodiesOf(spy, "PATCH")).toEqual([{ ingredient_id: "i-parmigiano" }]);
    expect(spy.mock.calls.some(([url]) => String(url).includes("kind="))).toBe(false);
  });

  it("dalla dispensa: l'ingrediente è un link alla sua scheda, e l'origine segue", async () => {
    stubRoutedFetch((path) => base(path) ?? [{}, 404]);
    renderAt("/anagrafica/prodotto/p-reggiano?da=dispensa");

    expect(await screen.findByRole("heading", { name: "Parmigiano Reggiano 24 mesi" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Burro" })).toHaveAttribute(
      "href", "/anagrafica/ingrediente/i-burro?da=dispensa"
    );
    expect(screen.getByRole("link", { name: "Dispensa" })).toHaveAttribute("href", "/dispensa");
    expect(screen.getByText("1 elemento in dispensa.")).toBeInTheDocument();
  });

  it("un codice già di un altro prodotto offre di spostarlo qui", async () => {
    let tentativi = 0;
    const spy = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") {
        tentativi += 1;
        if (tentativi === 1) {
          return [{
            code: "barcode_taken",
            detail: "Il codice è di «Grana Padano 200 g».",
            existing: { id: "p-grana", name: "Grana Padano 200 g", brand: null, barcode: "8001234567897" },
          }, 409];
        }
        return [{ ...REGGIANO, barcode: "8001234567897" }, 200];
      }
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/prodotto/p-reggiano");

    const codice = await screen.findByLabelText("Codice");
    await userEvent.clear(codice);
    await userEvent.type(codice, "8001234567897");
    await userEvent.click(screen.getByRole("button", { name: "Salva codice" }));

    expect(await screen.findByText("Il codice è di «Grana Padano 200 g». Spostalo qui?")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Sposta il codice qui" }));

    await waitFor(() =>
      expect(bodiesOf(spy, "PATCH")).toEqual([
        { barcode: "8001234567897" },
        { barcode: "8001234567897", take_barcode: true },
      ])
    );
  });

  it("un codice che non torna avvisa, e «Usalo lo stesso» lo manda", async () => {
    let tentativi = 0;
    const spy = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") {
        tentativi += 1;
        if (tentativi === 1) {
          return [{
            code: "bad_checksum",
            detail:
              "Il codice non torna con la sua cifra di controllo: controlla le cifre. Se è un codice del negozio, usalo lo stesso.",
          }, 409];
        }
        return [{ ...REGGIANO, barcode: "8001234567890", valid_checksum: false }, 200];
      }
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/prodotto/p-reggiano");

    const codice = await screen.findByLabelText("Codice");
    await userEvent.clear(codice);
    await userEvent.type(codice, "8001234567890");
    await userEvent.click(screen.getByRole("button", { name: "Salva codice" }));

    expect(await screen.findByText(/controlla le cifre/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Usalo lo stesso" }));

    await waitFor(() =>
      expect(bodiesOf(spy, "PATCH")).toEqual([
        { barcode: "8001234567890" },
        { barcode: "8001234567890", accept_bad_checksum: true },
      ])
    );
  });

  it("modificare il campo dopo un rifiuto barcode_taken toglie il pulsante, e salvare manda la bozza nuova senza spostamento", async () => {
    // il difetto: le uscite del rifiuto agivano sulla bozza attuale del campo, non sul
    // codice rifiutato. Chi cambia idea e scrive un altro codice, senza premere «Salva»,
    // non deve poter far scattare uno spostamento sul valore nuovo mai confermato
    let tentativi = 0;
    const spy = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") {
        tentativi += 1;
        if (tentativi === 1) {
          return [{
            code: "barcode_taken",
            detail: "Il codice è di «Grana Padano 200 g».",
            existing: { id: "p-grana", name: "Grana Padano 200 g", brand: null, barcode: "8001234567897" },
          }, 409];
        }
        return [{ ...REGGIANO, barcode: "9990000000000" }, 200];
      }
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/prodotto/p-reggiano");

    const codice = await screen.findByLabelText("Codice");
    await userEvent.clear(codice);
    await userEvent.type(codice, "8001234567897");
    await userEvent.click(screen.getByRole("button", { name: "Salva codice" }));
    expect(await screen.findByText("Il codice è di «Grana Padano 200 g». Spostalo qui?")).toBeInTheDocument();

    // si cambia idea, senza premere «Salva»
    await userEvent.clear(codice);
    await userEvent.type(codice, "9990000000000");

    expect(screen.queryByRole("button", { name: "Sposta il codice qui" })).not.toBeInTheDocument();
    expect(screen.queryByText(/Spostalo qui\?/)).not.toBeInTheDocument();

    // e se ora si salva, va il valore scritto adesso, senza `take_barcode`
    await userEvent.click(screen.getByRole("button", { name: "Salva codice" }));
    await waitFor(() =>
      expect(bodiesOf(spy, "PATCH")).toEqual([
        { barcode: "8001234567897" },
        { barcode: "9990000000000" },
      ])
    );
  });

  it("uno spostamento del codice che fallisce dice cos'è andato storto, non un generico «ancora quello di prima»", async () => {
    let tentativi = 0;
    stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") {
        tentativi += 1;
        if (tentativi === 1) {
          return [{
            code: "barcode_taken",
            detail: "Il codice è di «Grana Padano 200 g».",
            existing: { id: "p-grana", name: "Grana Padano 200 g", brand: null, barcode: "8001234567897" },
          }, 409];
        }
        return [{ detail: "boom" }, 500];
      }
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/prodotto/p-reggiano");

    const codice = await screen.findByLabelText("Codice");
    await userEvent.clear(codice);
    await userEvent.type(codice, "8001234567897");
    await userEvent.click(screen.getByRole("button", { name: "Salva codice" }));
    await userEvent.click(await screen.findByRole("button", { name: "Sposta il codice qui" }));

    expect(
      await screen.findByText("Non sono riuscito a spostare il codice qui. Riprova.")
    ).toBeInTheDocument();
    expect(screen.queryByText(/ancora quello di prima/)).not.toBeInTheDocument();
  });

  it("«Togli il codice» manda il codice vuoto", async () => {
    const spy = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") return [{ ...REGGIANO, barcode: null, valid_checksum: null }, 200];
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/prodotto/p-reggiano");

    await userEvent.click(await screen.findByRole("button", { name: "Togli il codice" }));

    await waitFor(() => expect(bodiesOf(spy, "PATCH")).toEqual([{ barcode: null }]));
  });

  it("eliminare chiede conferma, dice cosa resta, e torna da dove si è venuti", async () => {
    const spy = stubRoutedFetch((path, init) => {
      if (init?.method === "DELETE") return [{ loose_pantry_items: 1 }, 200];
      return base(path) ?? [{}, 404];
    });
    renderAt("/anagrafica/prodotto/p-reggiano?da=dispensa");

    await userEvent.click(await screen.findByRole("button", { name: "Elimina il prodotto" }));
    expect(
      screen.getByText("Gli elementi in dispensa restano, come «Burro» sfuso.")
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Elimina" }));

    expect(await screen.findByText("dove: /dispensa")).toBeInTheDocument();
    expect(
      spy.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === "DELETE")
    ).toHaveLength(1);
  });

  it("le correzioni sono un gruppo di icone accanto al titolo, coi nomi di sempre", async () => {
    stubRoutedFetch((path) => base(path) ?? [{}, 404]);
    renderAt("/anagrafica/prodotto/p-reggiano");

    const toolbar = await screen.findByRole("toolbar", { name: "Correzioni del prodotto" });
    expect(toolbar.parentElement).toContainElement(
      screen.getByRole("heading", { level: 1, name: "Parmigiano Reggiano 24 mesi" })
    );
    const buttons = within(toolbar).getAllByRole("button");
    expect(buttons.map((button) => button.getAttribute("aria-label"))).toEqual([
      "Spostalo",
      "Togli il codice",
    ]);
    for (const button of buttons) {
      expect(button.textContent).toBe("");
      expect(button.querySelector('svg[aria-hidden="true"]')).not.toBeNull();
    }
    // «Spostalo» apre e chiude la scelta dell'ingrediente, e lo dice
    expect(buttons[0]).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(buttons[0]);
    expect(buttons[0]).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByLabelText("Sposta sotto")).toBeInTheDocument();
  });

  it("senza codice, nel gruppo non c'è «Togli il codice»", async () => {
    stubRoutedFetch((path) =>
      path.endsWith("/products/p-reggiano")
        ? [{ ...REGGIANO, barcode: null, valid_checksum: null }, 200]
        : (base(path) ?? [{}, 404])
    );
    renderAt("/anagrafica/prodotto/p-reggiano");

    const toolbar = await screen.findByRole("toolbar", { name: "Correzioni del prodotto" });
    expect(within(toolbar).getAllByRole("button").map((button) => button.getAttribute("aria-label"))).toEqual([
      "Spostalo",
    ]);
  });

  it("mentre il codice si toglie, «Togli il codice» resta spento col fuoco, e non riparte", async () => {
    let risolvi: ((response: Response) => void) | null = null;
    const pendente = new Promise<Response>((resolve) => {
      risolvi = resolve;
    });
    const spy = vi.fn((url: unknown, init?: RequestInit) => {
      if (init?.method === "PATCH") return pendente;
      const [body, status] = base(String(url)) ?? [{}, 404];
      return Promise.resolve(new Response(JSON.stringify(body), { status }));
    });
    vi.stubGlobal("fetch", spy);
    renderAt("/anagrafica/prodotto/p-reggiano");

    const togli = await screen.findByRole("button", { name: "Togli il codice" });
    await userEvent.click(togli);
    // `busy` e non `disabled` (Consegna 6a)
    await waitFor(() => expect(togli).toHaveAttribute("aria-disabled", "true"));
    expect(togli.hasAttribute("disabled")).toBe(false);
    expect(togli).toHaveFocus();
    await userEvent.click(togli);
    expect(spy.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(1);

    risolvi!(
      new Response(JSON.stringify({ ...REGGIANO, barcode: null, valid_checksum: null }), { status: 200 })
    );
  });
});
