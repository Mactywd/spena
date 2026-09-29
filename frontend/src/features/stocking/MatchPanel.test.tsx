import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MatchPanel } from "./MatchPanel";
import type { Ingredient, ShoppingItem } from "../../domain/types";

const ITEM: ShoppingItem = {
  id: "s3", raw_text: "cera per pavimenti", ingredient_id: null, ingredient_name: null,
  ingredient_category: null, ingredient_kind: null, status: "checked", reason: "manual",
  created_at: "2026-09-29T10:00:00Z",
};
const PERA: Ingredient = { id: "i7", name: "pera", display_name: "Pera", category: "frutta", kind: "food" };
const CERA: Ingredient = { id: "i9", name: "cera", display_name: "cera", category: "casa", kind: "non_food" };

type Route = (path: string, init?: RequestInit) => [unknown, number];

/** Un fetch che risponde in base a percorso e metodo, e tiene le chiamate. */
function stubRoutedFetch(route: Route) {
  const spy = vi.fn((input: unknown, init?: RequestInit) => {
    const [body, status] = route(String(input), init);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

const creations = (spy: ReturnType<typeof stubRoutedFetch>) =>
  spy.mock.calls
    .filter(([url, init]) => String(url).endsWith("/ingredients") && init?.method === "POST")
    .map(([, init]) => JSON.parse(String(init?.body)));

function renderPanel() {
  const onMatched = vi.fn();
  const onCancel = vi.fn();
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MatchPanel item={ITEM} onMatched={onMatched} onCancel={onCancel} />
    </QueryClientProvider>
  );
  return { onMatched, onCancel };
}

const FIELD = { name: "Abbina un ingrediente per cera per pavimenti" };
const OFFER = { name: "Aggiungi «cera per pavimenti»" };

describe("MatchPanel", () => {
  it("cerca subito il testo della voce, col fuoco nel campo", async () => {
    stubRoutedFetch(() => [[PERA], 200]);
    renderPanel();
    const field = screen.getByRole("textbox", FIELD);
    expect(field).toHaveValue("cera per pavimenti");
    expect(document.activeElement).toBe(field);
    expect(await screen.findByRole("option", { name: "Pera" })).toBeDefined();
  });

  it("scegliere un suggerimento abbina quello", async () => {
    stubRoutedFetch(() => [[PERA], 200]);
    const { onMatched } = renderPanel();
    await userEvent.click(await screen.findByRole("option", { name: "Pera" }));
    expect(onMatched).toHaveBeenCalledWith(PERA);
  });

  // S6: «cera per pavimenti» pescava sette suggerimenti, `Pera` in testa, e l'unica
  // porta che crea un ingrediente spariva dietro di loro
  it("offre di crearlo anche quando la ricerca trova qualcosa, col nome da correggere", async () => {
    stubRoutedFetch(() => [[PERA], 200]);
    renderPanel();
    await screen.findByRole("option", { name: "Pera" });
    await userEvent.click(screen.getByRole("button", OFFER));
    expect(screen.getByLabelText("Come si chiama in generale?")).toHaveValue("cera per pavimenti");
  });

  it("crea col nome corretto e il reparto scelto, e abbina l'ingrediente nuovo", async () => {
    const spy = stubRoutedFetch((_path, init) => (init?.method === "POST" ? [CERA, 201] : [[], 200]));
    const { onMatched } = renderPanel();
    await userEvent.click(await screen.findByRole("button", OFFER));
    const name = screen.getByLabelText("Come si chiama in generale?");
    await userEvent.clear(name);
    await userEvent.type(name, "cera");
    await userEvent.selectOptions(screen.getByLabelText("Reparto"), "casa");
    await userEvent.click(screen.getByRole("button", { name: "Crea l'ingrediente" }));
    await waitFor(() => expect(onMatched).toHaveBeenCalledWith(CERA));
    // `name` e `display_name` sono lo stesso testo: normalizzare è del backend
    expect(creations(spy)).toEqual([{ name: "cera", display_name: "cera", category: "casa" }]);
  });

  it("un ingrediente che c'è già si aggancia, senza errore (S19)", async () => {
    stubRoutedFetch((_path, init) =>
      init?.method === "POST"
        ? [{ detail: "ingrediente già presente", existing: CERA }, 409]
        : [[], 200]
    );
    const { onMatched } = renderPanel();
    await userEvent.click(await screen.findByRole("button", OFFER));
    await userEvent.click(screen.getByRole("button", { name: "Crea l'ingrediente" }));
    await waitFor(() => expect(onMatched).toHaveBeenCalledWith(CERA));
    expect(screen.queryByText(/Non sono riuscito a creare/)).toBeNull();
  });

  it("un altro fallimento lo dice, e il nome scritto resta", async () => {
    stubRoutedFetch((_path, init) => (init?.method === "POST" ? [{ detail: "giù" }, 500] : [[], 200]));
    const { onMatched } = renderPanel();
    await userEvent.click(await screen.findByRole("button", OFFER));
    const name = screen.getByLabelText("Come si chiama in generale?");
    await userEvent.clear(name);
    await userEvent.type(name, "cera");
    await userEvent.click(screen.getByRole("button", { name: "Crea l'ingrediente" }));
    expect(await screen.findByText(/Non sono riuscito a creare l'ingrediente/)).toBeDefined();
    expect(name).toHaveValue("cera");
    expect(onMatched).not.toHaveBeenCalled();
  });

  it("«Annulla» nella creazione torna alla ricerca; nella ricerca chiude il pannello", async () => {
    stubRoutedFetch(() => [[], 200]);
    const { onCancel } = renderPanel();
    await userEvent.click(await screen.findByRole("button", OFFER));
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(screen.getByRole("textbox", FIELD)).toBeDefined();
    expect(onCancel).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(onCancel).toHaveBeenCalled();
  });

  // «Annulla» durante la creazione in volo: l'ingrediente può nascere lo stesso sul
  // server, ma la voce non ci si abbina — l'utente ha tolto quella scelta
  it("«Annulla» mentre la creazione è in volo non abbina l'ingrediente", async () => {
    let answer: (response: Response) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn((_input: unknown, init?: RequestInit) =>
        init?.method === "POST"
          ? new Promise<Response>((resolve) => {
              answer = resolve;
            })
          : Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))
      )
    );
    const { onMatched } = renderPanel();
    await userEvent.click(await screen.findByRole("button", OFFER));
    await userEvent.click(screen.getByRole("button", { name: "Crea l'ingrediente" }));
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(screen.getByRole("textbox", FIELD)).toBeDefined();
    answer(new Response(JSON.stringify(CERA), { status: 201 }));
    // lascia al POST il tempo di arrivare in fondo, onSuccess compreso
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(onMatched).not.toHaveBeenCalled();
  });

  it("una ricerca che non risponde lo dice, e lascia crearlo lo stesso (S6)", async () => {
    stubRoutedFetch(() => [{ detail: "giù" }, 500]);
    renderPanel();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "La ricerca degli ingredienti non risponde."
    );
    expect(screen.getByRole("button", OFFER)).toBeDefined();
  });
});
