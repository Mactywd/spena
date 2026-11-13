import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { createTestQueryClient } from "../../test/queryClient";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import { UtensilsScreen } from "./UtensilsScreen";
import type { Utensil } from "../../domain/types";

const PADELLA: Utensil = { id: "u1", name: "padella antiaderente", note: "da 24 cm" };
const FRUSTA: Utensil = { id: "u2", name: "frusta elettrica", note: null };

type Call = { method: string; path: string; body: unknown };
type Route = (method: string, path: string) => [unknown, number] | undefined;

// guarda metodo e percorso, e registra ogni chiamata col suo corpo
function stubRoutedFetch(route: Route) {
  const calls: Call[] = [];
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    const path = String(url);
    calls.push({ method, path, body: init?.body ? JSON.parse(String(init.body)) : null });
    const [body, status] = route(method, path) ?? [{}, 404];
    return Promise.resolve(
      status === 204 ? new Response(null, { status }) : new Response(JSON.stringify(body), { status })
    );
  });
  vi.stubGlobal("fetch", spy);
  return calls;
}

function renderScreen() {
  const client = createTestQueryClient();
  return render(
    <QueryClientProvider client={client}>
      <NoticeProvider>
        <MemoryRouter>
          <UtensilsScreen />
        </MemoryRouter>
      </NoticeProvider>
    </QueryClientProvider>
  );
}

const LIST = "/api/v1/utensils";
const gets = (calls: Call[]) => calls.filter((c) => c.method === "GET" && c.path === LIST).length;

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("UtensilsScreen", () => {
  it("vuota, dice cosa serve con le parole della spec", async () => {
    stubRoutedFetch((m) => (m === "GET" ? [[], 200] : undefined));
    renderScreen();

    expect(
      await screen.findByText(
        "Scrivi gli strumenti che hai in cucina: le ricette scritte dall'AI useranno solo quelli"
      )
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Utensili" })).toBeInTheDocument();
  });

  it("elenca gli utensili, con la nota sotto il nome", async () => {
    stubRoutedFetch((m) => (m === "GET" ? [[FRUSTA, PADELLA], 200] : undefined));
    renderScreen();

    const items = await screen.findAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(within(items[1]).getByText("da 24 cm")).toBeInTheDocument();
    expect(screen.queryByText(/Scrivi gli strumenti/)).not.toBeInTheDocument();
  });

  it("«Aggiungi» manda nome e nota, svuota i campi e rilegge l'elenco", async () => {
    const calls = stubRoutedFetch((m) =>
      m === "GET" ? [[], 200] : m === "POST" ? [{ id: "u3", name: "x", note: null }, 201] : undefined
    );
    renderScreen();
    await screen.findByText(/Scrivi gli strumenti/);

    await userEvent.type(screen.getByLabelText("Nuovo utensile"), "frusta elettrica");
    await userEvent.type(screen.getByLabelText("Nota"), "a due fruste");
    await userEvent.click(screen.getByRole("button", { name: "Aggiungi" }));

    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    const post = calls.find((c) => c.method === "POST")!;
    expect(post.path).toBe(LIST);
    expect(post.body).toEqual({ name: "frusta elettrica", note: "a due fruste" });
    await waitFor(() => expect(screen.getByLabelText("Nuovo utensile")).toHaveValue(""));
    expect(screen.getByLabelText("Nota")).toHaveValue("");
    expect(screen.getByLabelText("Nuovo utensile")).toHaveFocus();
    await waitFor(() => expect(gets(calls)).toBe(2));
    expect(calls.findIndex((c) => c.method === "POST")).toBeLessThan(calls.length - 1);
  });

  it("«Aggiungi» col nome vuoto dice perché, e non manda niente", async () => {
    const calls = stubRoutedFetch((m) => (m === "GET" ? [[], 200] : undefined));
    renderScreen();
    await screen.findByText(/Scrivi gli strumenti/);

    await userEvent.type(screen.getByLabelText("Nuovo utensile"), "   ");
    const button = screen.getByRole("button", { name: "Aggiungi" });
    await userEvent.click(button);

    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByText("Scrivi il nome dell'utensile.")).toBeInTheDocument();
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });

  it("un'aggiunta fallita lascia quel che si è scritto, con l'errore", async () => {
    stubRoutedFetch((m) => (m === "GET" ? [[], 200] : m === "POST" ? [{}, 500] : undefined));
    renderScreen();
    await screen.findByText(/Scrivi gli strumenti/);

    await userEvent.type(screen.getByLabelText("Nuovo utensile"), "frusta elettrica");
    await userEvent.click(screen.getByRole("button", { name: "Aggiungi" }));

    expect(
      await screen.findByText("L'utensile non è stato aggiunto: riprova tra poco.")
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Nuovo utensile")).toHaveValue("frusta elettrica");
  });

  it("«Correggi» apre i campi pieni, e «Salva» manda la correzione", async () => {
    const calls = stubRoutedFetch((m) =>
      m === "GET" ? [[PADELLA], 200] : m === "PATCH" ? [{ ...PADELLA, note: "da 28 cm" }, 200] : undefined
    );
    renderScreen();

    await userEvent.click(
      await screen.findByRole("button", { name: "Correggi «padella antiaderente»" })
    );
    const row = screen.getByRole("listitem");
    expect(within(row).getByLabelText("Nome")).toHaveValue("padella antiaderente");
    const noteField = within(row).getByLabelText("Nota");
    expect(noteField).toHaveValue("da 24 cm");

    await userEvent.clear(noteField);
    await userEvent.type(noteField, "da 28 cm");
    await userEvent.click(within(row).getByRole("button", { name: "Salva" }));

    await waitFor(() => expect(calls.some((c) => c.method === "PATCH")).toBe(true));
    const patch = calls.find((c) => c.method === "PATCH")!;
    expect(patch.path).toBe(`${LIST}/u1`);
    expect(patch.body).toEqual({ name: "padella antiaderente", note: "da 28 cm" });
    await waitFor(() => expect(screen.queryByLabelText("Nome")).not.toBeInTheDocument());
  });

  it("una correzione su un utensile sparito lo dice con un avviso e rilegge l'elenco", async () => {
    let patched = false;
    const calls = stubRoutedFetch((m) => {
      if (m === "PATCH") {
        patched = true;
        return [{ detail: "non trovato" }, 404];
      }
      return m === "GET" ? [patched ? [] : [PADELLA], 200] : undefined;
    });
    renderScreen();

    await userEvent.click(
      await screen.findByRole("button", { name: "Correggi «padella antiaderente»" })
    );
    await userEvent.click(screen.getByRole("button", { name: "Salva" }));

    // la riga sparisce con l'elenco riletto: il testo sta nell'avviso, che resta
    expect(await screen.findByText("Questo utensile non c'è più.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole("listitem")).not.toBeInTheDocument());
    expect(screen.getByText("Questo utensile non c'è più.")).toBeInTheDocument();
    const patchAt = calls.findIndex((c) => c.method === "PATCH");
    expect(calls.slice(patchAt + 1).some((c) => c.method === "GET" && c.path === LIST)).toBe(true);
  });

  it("«Togli» toglie, e «Annulla» lo rimette com'era", async () => {
    const calls = stubRoutedFetch((m) =>
      m === "GET" ? [[PADELLA], 200] : m === "DELETE" ? [null, 204] : m === "POST" ? [PADELLA, 201] : undefined
    );
    renderScreen();

    await userEvent.click(
      await screen.findByRole("button", { name: "Togli «padella antiaderente»" })
    );

    await waitFor(() => expect(calls.some((c) => c.method === "DELETE")).toBe(true));
    expect(calls.find((c) => c.method === "DELETE")!.path).toBe(`${LIST}/u1`);
    expect(await screen.findByText("Tolto «padella antiaderente».")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    const post = calls.find((c) => c.method === "POST")!;
    expect(post.path).toBe(LIST);
    expect(post.body).toEqual({ name: "padella antiaderente", note: "da 24 cm" });
  });

  it("se l'elenco non si carica, offre «Riprova»", async () => {
    stubRoutedFetch((m) => (m === "GET" ? [{}, 500] : undefined));
    renderScreen();

    expect(await screen.findByText("Gli utensili non si caricano.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Riprova" })).toBeInTheDocument();
  });
});
