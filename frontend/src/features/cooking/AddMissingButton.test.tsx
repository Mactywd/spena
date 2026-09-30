import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AddMissingButton } from "./AddMissingButton";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import type { RecipeIngredientLine } from "../../domain/types";

const NOME = "Metti in lista ciò che manca";

function riga(id: string, nome: string): RecipeIngredientLine {
  return {
    ingredient_id: id, ingredient_name: nome, role: "primary", quantity_text: null,
    quantity_display: null, quantity_scaled: false, note: null,
    availability: "missing", satisfied: false,
  };
}

const BASILICO = riga("i1", "basilico");
const POMODORO = riga("i2", "pomodoro");

// senza `NoticeProvider` l'avviso non avrebbe dove comparire
function renderButton(
  lines: RecipeIngredientLine[],
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
) {
  render(
    <QueryClientProvider client={client}>
      <NoticeProvider>
        <AddMissingButton lines={lines} />
      </NoticeProvider>
    </QueryClientProvider>
  );
  return client;
}

/** `POST /shopping-list` finta: per ogni ingrediente una coda di stati, consumata una
 * risposta alla volta (l'ultima resta). 201 entrata, 200 c'era già, dal 400 un guasto. */
function stubLista(code: Record<string, number[]>) {
  const spy = vi.fn((_url: unknown, init?: RequestInit) => {
    const { ingredient_id } = JSON.parse(String(init!.body)) as { ingredient_id: string };
    const coda = code[ingredient_id];
    const status = coda.length > 1 ? coda.shift()! : coda[0];
    const corpo = status >= 400 ? { detail: "no" } : { id: `s-${ingredient_id}`, added: status === 201 };
    return Promise.resolve(new Response(JSON.stringify(corpo), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function mandati(spy: ReturnType<typeof stubLista>) {
  return spy.mock.calls.map(([, init]) => JSON.parse(String(init!.body)).ingredient_id as string);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AddMissingButton", () => {
  it("manda le righe che riceve, e l'avviso dice com'è andata", async () => {
    const spy = stubLista({ i1: [201], i2: [200] });
    renderButton([BASILICO, POMODORO]);

    await userEvent.click(screen.getByRole("button", { name: NOME }));

    expect(await screen.findByText("1 in lista · 1 c'era già")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("1 in lista · 1 c'era già");
    expect(mandati(spy)).toEqual(["i1", "i2"]);
    // tutto arrivato: niente da riprovare
    expect(screen.queryByRole("button", { name: "Riprova" })).toBeNull();
  });

  it("in volo è spento tenendo il fuoco, e un secondo tocco non manda niente", async () => {
    let rilascia = () => {};
    const inVolo = new Promise<void>((resolve) => {
      rilascia = resolve;
    });
    const spy = vi.fn(async () => {
      await inVolo;
      return new Response(JSON.stringify({ id: "s", added: true }), { status: 201 });
    });
    vi.stubGlobal("fetch", spy);
    renderButton([BASILICO]);

    const pulsante = screen.getByRole("button", { name: NOME });
    await userEvent.click(pulsante);
    expect(pulsante).toHaveAttribute("aria-disabled", "true");
    expect(pulsante).not.toBeDisabled();
    expect(pulsante).toHaveFocus();
    await userEvent.click(pulsante);
    expect(spy).toHaveBeenCalledTimes(1);

    rilascia();
    expect(await screen.findByText("1 in lista")).toBeInTheDocument();
    // `busy` si spegne nel `finally`, un giro dopo l'avviso
    await vi.waitFor(() => expect(pulsante).not.toHaveAttribute("aria-disabled", "true"));
  });

  it("con dei guasti l'avviso offre «Riprova», che rimanda solo le righe fallite", async () => {
    const spy = stubLista({ i1: [201], i2: [500, 201] });
    renderButton([BASILICO, POMODORO]);

    await userEvent.click(screen.getByRole("button", { name: NOME }));
    expect(await screen.findByText("1 in lista · 1 non è andata")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Riprova" }));
    expect(await screen.findByText("1 in lista")).toBeInTheDocument();
    expect(mandati(spy)).toEqual(["i1", "i2", "i2"]);
  });

  it("dopo, la lista della spesa si rilegge", async () => {
    stubLista({ i1: [201] });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    client.setQueryData(["shopping-list"], []);
    renderButton([BASILICO], client);

    await userEvent.click(screen.getByRole("button", { name: NOME }));

    await vi.waitFor(() =>
      expect(client.getQueryState(["shopping-list"])?.isInvalidated).toBe(true)
    );
  });

  it("senza righe mancanti non c'è", () => {
    renderButton([]);
    expect(screen.queryByRole("button", { name: NOME })).toBeNull();
  });
});
