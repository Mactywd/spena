import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider, focusManager, onlineManager } from "@tanstack/react-query";
import { createTestQueryClient } from "../../test/queryClient";
import { SubstitutePanel } from "./SubstitutePanel";
import type { LineSubstitution } from "./types";

const LINE = "/api/v1/recipes/r1/substitutes/i-pasta";
const GENERALE: LineSubstitution = {
  ingredient_id: "i-pasta", ingredient_name: "pasta", context: "salato", scope: "general",
  verdict: "substitutes", decided_by: "ai", ai_failed: false,
  substitutes: [
    { ingredient_id: "i-riso", name: "riso", note: "cottura più lunga", availability: "available", satisfied: true },
    { ingredient_id: "i-farro", name: "farro", note: null, availability: "low", satisfied: false },
  ],
};
const VUOTA: LineSubstitution = { ...GENERALE, scope: null, verdict: null, decided_by: null, substitutes: [] };
const CORRETTA: LineSubstitution = {
  ...GENERALE, scope: "recipe", decided_by: "human", verdict: "irreplaceable", substitutes: [],
};

type FetchRoute = (path: string, method: string, init?: RequestInit) => [unknown, number];

function stubRoutedFetch(route: FetchRoute) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const [body, status] = route(String(url), init?.method ?? "GET", init);
    return Promise.resolve(
      status === 204 ? new Response(null, { status }) : new Response(JSON.stringify(body), { status })
    );
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

function callsTo(spy: ReturnType<typeof stubRoutedFetch>, method: string, path: string) {
  return spy.mock.calls.filter(
    ([url, init]) => String(url) === path && ((init as RequestInit | undefined)?.method ?? "GET") === method
  );
}

function renderPanel() {
  const client = createTestQueryClient();
  render(
    <QueryClientProvider client={client}>
      <SubstitutePanel recipeId="r1" ingredientId="i-pasta" ingredientName="pasta" />
    </QueryClientProvider>
  );
  return client;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SubstitutePanel", () => {
  it("dice la voce generale dell'AI, con quel che c'è in dispensa", async () => {
    const spy = stubRoutedFetch(() => [GENERALE, 200]);
    renderPanel();
    expect(await screen.findByText("Al posto di pasta:")).toBeInTheDocument();
    expect(screen.getByText("Riso")).toBeInTheDocument();
    expect(screen.getByText("· cottura più lunga")).toBeInTheDocument();
    expect(screen.getByText("ce l'hai")).toBeInTheDocument();
    expect(screen.getByText("non basta")).toBeInTheDocument();
    expect(screen.getByText("Suggerito dall'AI per i piatti salati.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Non va bene qui" })).toBeInTheDocument();
    expect(callsTo(spy, "POST", `${LINE}/ask`)).toHaveLength(0);
  });

  it("senza una risposta la chiede, e mentre aspetta lo dice", async () => {
    stubRoutedFetch((_path, method) => [method === "POST" ? GENERALE : VUOTA, 200]);
    renderPanel();
    expect(screen.getByRole("status")).toHaveTextContent("Cerco cosa usare al posto di pasta…");
    expect(await screen.findByText("Suggerito dall'AI per i piatti salati.")).toBeInTheDocument();
  });

  it("se l'AI non risponde lascia «Riprova» e «Scrivi tu»", async () => {
    const spy = stubRoutedFetch((_path, method) => [method === "POST" ? { ...VUOTA, ai_failed: true } : VUOTA, 200]);
    renderPanel();
    expect(await screen.findByText("Nessun suggerimento ancora.")).toBeInTheDocument();
    expect(callsTo(spy, "POST", `${LINE}/ask`)).toHaveLength(1);

    await userEvent.click(screen.getByRole("button", { name: "Riprova" }));
    await waitFor(() => expect(callsTo(spy, "POST", `${LINE}/ask`)).toHaveLength(2));

    await userEvent.click(screen.getByRole("button", { name: "Scrivi tu" }));
    expect(screen.getByRole("group", { name: "Al posto di pasta, in questa ricetta:" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Un altro ingrediente" })).toBeChecked();
  });

  it("senza una risposta non richiama l'AI da sola: né al fuoco, né alla rete, né dopo un guasto", async () => {
    // il client di produzione ritenta; il pannello deve spegnerlo lui, non il client del test
    let guasto = false;
    const spy = stubRoutedFetch((_path, method) =>
      method === "POST" ? (guasto ? [{ detail: "boom" }, 500] : [{ ...VUOTA, ai_failed: true }, 200]) : [VUOTA, 200]
    );
    renderPanel();
    expect(await screen.findByText("Nessun suggerimento ancora.")).toBeInTheDocument();
    expect(callsTo(spy, "POST", `${LINE}/ask`)).toHaveLength(1);

    try {
      focusManager.setFocused(false);
      focusManager.setFocused(true);
      onlineManager.setOnline(false);
      onlineManager.setOnline(true);
      await new Promise((resolve) => setTimeout(resolve, 50));
      expect(callsTo(spy, "POST", `${LINE}/ask`)).toHaveLength(1);
      expect(callsTo(spy, "GET", LINE)).toHaveLength(1);
    } finally {
      focusManager.setFocused(undefined);
      onlineManager.setOnline(true);
    }

    // un 5xx dell'AI non si ritenta da solo: una sola chiamata, poi «Riprova»
    guasto = true;
    await userEvent.click(screen.getByRole("button", { name: "Riprova" }));
    expect(await screen.findByText("Non sono riuscito a leggere i sostituti.")).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(callsTo(spy, "POST", `${LINE}/ask`)).toHaveLength(2);
  });

  it("un rilancio in background fallito non porta via il modulo aperto", async () => {
    let guasto = false;
    stubRoutedFetch((_path, method) => (guasto && method === "GET" ? [{ detail: "boom" }, 500] : [GENERALE, 200]));
    const client = renderPanel();
    await userEvent.click(await screen.findByRole("button", { name: "Non va bene qui" }));
    const nota = screen.getByRole("textbox", { name: "Nota per riso" });
    await userEvent.type(nota, " molto");

    guasto = true;
    await client.invalidateQueries({ queryKey: ["substitution"] });
    await waitFor(() => expect(client.getQueryState(["substitution", "r1", "i-pasta"])?.status).toBe("error"));
    expect(screen.getByRole("textbox", { name: "Nota per riso" })).toHaveValue("cottura più lunga molto");
    expect(screen.queryByText("Non sono riuscito a leggere i sostituti.")).not.toBeInTheDocument();
  });

  it("«si può omettere» è una frase", async () => {
    stubRoutedFetch(() => [{ ...GENERALE, verdict: "omit", substitutes: [] }, 200]);
    renderPanel();
    expect(await screen.findByText("Si può omettere: il piatto riesce anche senza pasta.")).toBeInTheDocument();
  });

  it("«insostituibile» è una frase", async () => {
    stubRoutedFetch(() => [{ ...GENERALE, verdict: "irreplaceable", substitutes: [] }, 200]);
    renderPanel();
    expect(await screen.findByText("Insostituibile: senza pasta il piatto non si fa.")).toBeInTheDocument();
  });

  it("«Non va bene qui» salva una correzione per questa ricetta", async () => {
    const spy = stubRoutedFetch((_path, method) => [method === "PUT" ? CORRETTA : GENERALE, 200]);
    renderPanel();
    await userEvent.click(await screen.findByRole("button", { name: "Non va bene qui" }));
    expect(screen.getByRole("textbox", { name: "Nota per riso" })).toHaveValue("cottura più lunga");
    await userEvent.click(screen.getByRole("radio", { name: "Insostituibile" }));
    await userEvent.click(screen.getByRole("button", { name: "Salva per questa ricetta" }));

    expect(await screen.findByText("Insostituibile: senza pasta il piatto non si fa.")).toBeInTheDocument();
    expect(screen.getByText("Scelto a mano per questa ricetta.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Torna al suggerimento generale" })).toBeInTheDocument();
    // chiuso il modulo, il fuoco torna al pulsante che apre il modulo
    expect(screen.getByRole("button", { name: "Cambia" })).toHaveFocus();
    const [put] = callsTo(spy, "PUT", LINE);
    expect(JSON.parse(String((put[1] as RequestInit).body))).toEqual({ verdict: "irreplaceable", substitutes: [] });
  });

  it("«Torna al suggerimento generale» toglie la correzione e rilegge", async () => {
    let corretta = true;
    const spy = stubRoutedFetch((_path, method) => {
      if (method === "DELETE") {
        corretta = false;
        return [null, 204];
      }
      return [corretta ? CORRETTA : GENERALE, 200];
    });
    renderPanel();
    await userEvent.click(await screen.findByRole("button", { name: "Torna al suggerimento generale" }));
    expect(await screen.findByText("Suggerito dall'AI per i piatti salati.")).toBeInTheDocument();
    expect(callsTo(spy, "DELETE", LINE)).toHaveLength(1);
  });

  it("una riga che non c'è più lo dice, senza «Riprova»", async () => {
    stubRoutedFetch(() => [{ detail: "Questo ingrediente non è nella ricetta." }, 404]);
    renderPanel();
    expect(
      await screen.findByText("Questo ingrediente non è più nella ricetta: ricarica la pagina.")
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Riprova" })).toBeNull();
  });

  it("un guasto del server lascia «Riprova»", async () => {
    stubRoutedFetch(() => [{ detail: "x" }, 500]);
    renderPanel();
    expect(await screen.findByText("Non sono riuscito a leggere i sostituti.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Riprova" })).toBeInTheDocument();
  });
});
