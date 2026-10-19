import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { SkippedPages } from "./SkippedPages";
import { defaultQueryRetryPredicate } from "../../lib/queryRetry";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import type { RequeueResult, SkippedPage } from "../../domain/types";

const ILLEGGIBILE: SkippedPage = {
  id: "p-vuota",
  url: "https://esempio.invalid/vuota.html",
  title: null,
  cause: "unreadable",
  non_food_name: null,
  requeueable: false,
  waiting_cooking_events: 0,
};
const TORTA: SkippedPage = {
  id: "p-torta",
  url: "https://esempio.invalid/torta.html",
  title: "Torta alla panna",
  cause: "non_food",
  non_food_name: "Panna",
  requeueable: true,
  waiting_cooking_events: 2,
};
const ACQUA: SkippedPage = {
  id: "p-acqua",
  url: "https://esempio.invalid/acqua.html",
  title: "Acqua calda",
  cause: "all_ignored",
  non_food_name: null,
  requeueable: true,
  waiting_cooking_events: 0,
};
const ENTRATA: RequeueResult = {
  outcome: "imported",
  title: "Torta alla panna",
  url: TORTA.url,
  recipe_id: "r-torta",
  cooking_relinked: 2,
  cause: null,
  non_food_name: null,
  waiting_terms: [],
};

// Il predicato vero di App.tsx, non un `retry: false` di comodo (CLAUDE.md, prima
// lezione). `retryDelay: 0` solo dove si prova un errore: i tentativi restano tre.
function clientVero(retryDelay?: number) {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: defaultQueryRetryPredicate,
        ...(retryDelay === undefined ? {} : { retryDelay }),
      },
    },
  });
}

function renderSkipped(count = 3, client = clientVero()) {
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/ricette/importa"]}>
        <NoticeProvider>
          <Routes>
            <Route path="/ricette/importa" element={<SkippedPages count={count} />} />
            <Route path="/ricette/:id" element={<p>La ricetta aperta</p>} />
          </Routes>
        </NoticeProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

type Risposta = [unknown, number] | "in volo";

/** Un fetch che risponde in base al percorso e al metodo; «in volo» non risponde mai. */
function stubFetch(route: (path: string, method: string) => Risposta) {
  const spy = vi.fn((url: unknown, init?: RequestInit) => {
    const risposta = route(String(url), init?.method ?? "GET");
    if (risposta === "in volo") return new Promise<Response>(() => {});
    const [body, status] = risposta;
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

/** L'elenco delle tre pagine in una volta, e la rimessa come la si chiede. */
function stubElenco(rimessa: Risposta = [ENTRATA, 200]) {
  return stubFetch((path, method) => {
    if (path.includes("/requeue") && method === "POST") return rimessa;
    if (path.includes("/imports/pages/skipped"))
      return [{ total: 3, pages: [ILLEGGIBILE, TORTA, ACQUA] }, 200];
    return [{}, 404];
  });
}

async function apri() {
  await userEvent.click(screen.getByRole("button", { name: "Scartate (3)" }));
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SkippedPages", () => {
  it("è chiusa di partenza, col numero, e non chiede l'elenco finché non si apre", () => {
    const spy = stubElenco();
    renderSkipped();
    const titolo = screen.getByRole("button", { name: "Scartate (3)" });
    expect(titolo).toHaveAttribute("aria-expanded", "false");
    expect(titolo.closest("h2")).not.toBeNull();
    expect(screen.queryByRole("list")).toBeNull();
    expect(spy).not.toHaveBeenCalled();
  });

  it("con nessuna pagina scartata non c'è", () => {
    stubElenco();
    const { container } = renderSkipped(0);
    expect(container.querySelector("section")).toBeNull();
    expect(screen.queryByRole("button", { name: /^Scartate/ })).toBeNull();
  });

  it("aperta, dice per ogni pagina il nome, il perché e cosa si può fare", async () => {
    stubElenco();
    renderSkipped();
    await apri();
    expect(screen.getByRole("button", { name: "Scartate (3)" })).toHaveAttribute(
      "aria-expanded",
      "true"
    );
    const righe = await screen.findAllByRole("listitem");
    expect(righe).toHaveLength(3);
    const [vuota, torta, acqua] = righe;

    // senza titolo, l'indirizzo; e al posto di «Rimetti in coda», la pagina da aprire
    expect(within(vuota).getByText(ILLEGGIBILE.url)).toBeInTheDocument();
    expect(
      within(vuota).getByText(
        "Sul sito la pagina non aveva una ricetta leggibile: rimetterla in coda non cambierebbe niente."
      )
    ).toBeInTheDocument();
    expect(within(vuota).queryByRole("button")).toBeNull();
    const pagina = within(vuota).getByRole("link", {
      name: `Apri la pagina «${ILLEGGIBILE.url}»`,
    });
    expect(pagina).toHaveAttribute("href", ILLEGGIBILE.url);
    expect(pagina).toHaveAttribute("target", "_blank");

    // il titolo, il perché in parole con la strada, le cotture che aspettano
    expect(within(torta).getByText("Torta alla panna")).toBeInTheDocument();
    expect(
      within(torta).getByText(/^Fra gli ingredienti c'è «Panna», che non è un alimento\./)
    ).toBeInTheDocument();
    expect(
      within(torta).getByText("2 cotture registrate aspettano questa ricetta.")
    ).toBeInTheDocument();
    expect(
      within(torta).getByRole("button", { name: "Rimetti in coda «Torta alla panna»" })
    ).toBeInTheDocument();
    expect(within(acqua).getByText(/^Tutti i suoi ingredienti sono ignorati/)).toBeInTheDocument();
    expect(within(acqua).queryByText(/cottur/)).toBeNull();

    // nessun codice, nessun motivo tecnico
    expect(screen.queryByText(/non_food|all_ignored|unreadable|dd\.gz/)).toBeNull();
  });

  it("rimessa e entrata: l'avviso lo dice, e «Apri» porta alla ricetta", async () => {
    const spy = stubElenco([ENTRATA, 200]);
    renderSkipped();
    await apri();
    await userEvent.click(
      await screen.findByRole("button", { name: "Rimetti in coda «Torta alla panna»" })
    );
    expect(spy).toHaveBeenCalledWith(
      "/api/v1/imports/pages/p-torta/requeue",
      expect.objectContaining({ method: "POST" })
    );
    const avviso = screen.getByRole("status");
    await waitFor(() =>
      expect(avviso).toHaveTextContent(
        "«Torta alla panna» è entrata nel ricettario. Ha ritrovato 2 cotture."
      )
    );
    await userEvent.click(within(avviso).getByRole("button", { name: "Apri" }));
    expect(await screen.findByText("La ricetta aperta")).toBeInTheDocument();
  });

  it("rimessa e ancora scartata: l'avviso dice perché, senza «Apri», e la riga resta", async () => {
    stubElenco([
      {
        ...ENTRATA,
        outcome: "skipped",
        recipe_id: null,
        cooking_relinked: 0,
        cause: "non_food",
        non_food_name: "Panna",
      },
      200,
    ]);
    renderSkipped();
    await apri();
    await userEvent.click(
      await screen.findByRole("button", { name: "Rimetti in coda «Torta alla panna»" })
    );
    const avviso = screen.getByRole("status");
    await waitFor(() =>
      expect(avviso).toHaveTextContent(
        "«Torta alla panna» è ancora scartata: «Panna» non è un alimento."
      )
    );
    expect(within(avviso).queryByRole("button", { name: "Apri" })).toBeNull();
    expect(
      screen.getByRole("button", { name: "Rimetti in coda «Torta alla panna»" })
    ).toBeInTheDocument();
  });

  it.each([
    [
      409,
      { detail: "Questa pagina non è più scartata: l'elenco era vecchio." },
      "Questa pagina non è più scartata: l'elenco era vecchio.",
    ],
    [500, { detail: "errore" }, "Non sono riuscito a rimetterla in coda. Niente è andato perso: riprova."],
  ])("un rifiuto %i si legge nella sezione", async (stato, corpo, frase) => {
    stubElenco([corpo, stato]);
    renderSkipped();
    await apri();
    await userEvent.click(
      await screen.findByRole("button", { name: "Rimetti in coda «Torta alla panna»" })
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(frase);
  });

  it("un 409 dice che l'elenco era vecchio: lo si rilegge, e la riga stantia se ne va", async () => {
    let tolta = false;
    const spy = stubFetch((path, method) => {
      if (path.includes("/requeue") && method === "POST") {
        tolta = true;
        return [{ detail: "Questa pagina non è più scartata: l'elenco era vecchio." }, 409];
      }
      if (path.includes("/imports/pages/skipped"))
        return [{ total: 2, pages: tolta ? [ACQUA] : [TORTA, ACQUA] }, 200];
      return [{}, 404];
    });
    const elencoChiesto = () =>
      spy.mock.calls.filter(([url]) => String(url).includes("/imports/pages/skipped")).length;
    renderSkipped();
    await apri();
    await userEvent.click(
      await screen.findByRole("button", { name: "Rimetti in coda «Torta alla panna»" })
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Questa pagina non è più scartata: l'elenco era vecchio."
    );
    // l'elenco è stato riletto (due richieste) e la riga che non c'è più è sparita
    await waitFor(() => expect(elencoChiesto()).toBe(2));
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Rimetti in coda «Torta alla panna»" })).toBeNull()
    );
    // il messaggio del 409 resta, parola per parola
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Questa pagina non è più scartata: l'elenco era vecchio."
    );
  });

  it("un guasto (500) non rilegge l'elenco", async () => {
    const spy = stubElenco([{ detail: "errore" }, 500]);
    renderSkipped();
    await apri();
    await userEvent.click(
      await screen.findByRole("button", { name: "Rimetti in coda «Torta alla panna»" })
    );
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(
      spy.mock.calls.filter(([url]) => String(url).includes("/imports/pages/skipped"))
    ).toHaveLength(1);
  });

  it("«Mostra altre» porta le pagine che mancano, e poi sparisce", async () => {
    const spy = stubFetch((path) => {
      if (path.includes("offset=2")) return [{ total: 3, pages: [ACQUA] }, 200];
      if (path.includes("/imports/pages/skipped"))
        return [{ total: 3, pages: [ILLEGGIBILE, TORTA] }, 200];
      return [{}, 404];
    });
    renderSkipped();
    await apri();
    expect(await screen.findAllByRole("listitem")).toHaveLength(2);
    expect(spy).toHaveBeenCalledWith(
      "/api/v1/imports/pages/skipped?limit=50&offset=0",
      expect.anything()
    );
    await userEvent.click(screen.getByRole("button", { name: "Mostra altre" }));
    await waitFor(() => expect(screen.getAllByRole("listitem")).toHaveLength(3));
    expect(screen.queryByRole("button", { name: "Mostra altre" })).toBeNull();
  });

  it("se l'elenco non arriva lo dice, e «Riprova» lo richiede", async () => {
    let tentativi = 0;
    stubFetch((path) => {
      if (path.includes("/imports/pages/skipped")) {
        tentativi += 1;
        // i tre tentativi del predicato falliscono; quello di «Riprova» no
        return tentativi <= 3 ? [{ detail: "guasto" }, 500] : [{ total: 3, pages: [TORTA] }, 200];
      }
      return [{}, 404];
    });
    renderSkipped(3, clientVero(0));
    await apri();
    expect(
      await screen.findByText("Non sono riuscito a leggere le pagine scartate.")
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Riprova" }));
    expect(await screen.findByText("Torta alla panna")).toBeInTheDocument();
  });

  it("mentre una rimessa è in volo, «Rimetti in coda» è spento e tiene il fuoco", async () => {
    stubElenco("in volo");
    renderSkipped();
    await apri();
    const tasto = await screen.findByRole("button", { name: "Rimetti in coda «Torta alla panna»" });
    await userEvent.click(tasto);
    await waitFor(() => expect(tasto).toHaveAttribute("aria-disabled", "true"));
    expect(tasto).toHaveFocus();
  });
});
