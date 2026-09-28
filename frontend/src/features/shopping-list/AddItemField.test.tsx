import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AddItemField } from "./AddItemField";
import { UnauthorizedError } from "../../api/client";

const POMODORO = { id: "i1", name: "pomodoro", display_name: "Pomodoro", category: "verdura" };
const PORRO = { id: "i9", name: "porro", display_name: "Porro", category: "verdura" };

/** Un'aggiunta riuscita, come la risponde il backend: la voce è nuova (S18). */
const added = () => vi.fn().mockResolvedValue({ added: true });

/** La ricerca dei suggerimenti passa da react-query, quindi il campo vuole il suo
 * provider: è anche il punto del difetto che questo schermo aveva, perché un 401
 * che non arriva alla QueryCache non riporta all'accesso. */
function renderField(
  props: { onAdd: (rawText: string, ingredientId?: string) => Promise<{ added: boolean }> },
  queryCache?: QueryCache
) {
  const client = new QueryClient({
    queryCache,
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <AddItemField {...props} />
    </QueryClientProvider>
  );
}

describe("AddItemField", () => {
  it("suggerisce ingredienti mentre si digita", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify([POMODORO]), { status: 200 })
    ));
    renderField({ onAdd: added() });

    await userEvent.type(screen.getByLabelText("Aggiungi alla lista"), "pomo");
    expect(await screen.findByRole("option", { name: /Pomodoro/ })).toBeDefined();
  });

  it("l'elenco dei suggerimenti ha un nome, che dice di quale campo è", async () => {
    // ARIA vuole un nome per ogni listbox; diverso da quello del campo, o chi cerca il
    // campo per etichetta troverebbe due elementi
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify([POMODORO]), { status: 200 })
    ));
    renderField({ onAdd: added() });

    await userEvent.type(screen.getByLabelText("Aggiungi alla lista"), "pomo");
    expect(await screen.findByRole("listbox", { name: "Suggerimenti: Aggiungi alla lista" })).toBeDefined();
  });

  it("scegliendo un suggerimento passa l'ingrediente risolto", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify([POMODORO]), { status: 200 })
    ));
    const onAdd = added();
    renderField({ onAdd });

    await userEvent.type(screen.getByLabelText("Aggiungi alla lista"), "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));

    expect(onAdd).toHaveBeenCalledWith("pomodoro", "i1");
  });

  it("accetta testo libero senza corrispondenze, perché non deve bloccare", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    const onAdd = added();
    renderField({ onAdd });

    const field = screen.getByLabelText("Aggiungi alla lista");
    await userEvent.type(field, "quella cosa verde{Enter}");
    await waitFor(() => expect(onAdd).toHaveBeenCalledWith("quella cosa verde", undefined));
  });

  it("una ricerca lenta e superata non sovrascrive i suggerimenti freschi", async () => {
    // due ricerche in volo insieme: la prima, per "po", risponde dopo la seconda.
    // Senza guardia sull'ordine l'utente vede Porro e sceglie l'ingrediente sbagliato.
    let releaseStale: (response: Response) => void = () => {};
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(
        () => new Promise<Response>((resolve) => { releaseStale = resolve; })
      )
      .mockResolvedValue(new Response(JSON.stringify([POMODORO]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    renderField({ onAdd: added() });
    const field = screen.getByLabelText("Aggiungi alla lista");

    await userEvent.type(field, "po");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    await userEvent.type(field, "mo");
    expect(await screen.findByRole("option", { name: /Pomodoro/ })).toBeDefined();

    releaseStale(new Response(JSON.stringify([PORRO]), { status: 200 }));
    await waitFor(() => expect(screen.getByRole("option", { name: /Pomodoro/ })).toBeDefined());
    expect(screen.queryByRole("option", { name: /Porro/ })).toBeNull();
  });

  it("un'aggiunta fallita non perde il testo scritto", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    const onAdd = vi.fn().mockRejectedValue(new Error("il server non risponde"));
    renderField({ onAdd });

    const field = screen.getByLabelText("Aggiungi alla lista");
    await userEvent.type(field, "quella cosa verde{Enter}");

    expect(await screen.findByRole("alert")).toBeDefined();
    expect(field).toHaveValue("quella cosa verde");
  });

  it("un'aggiunta riuscita svuota il campo", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    renderField({ onAdd: added() });

    const field = screen.getByLabelText("Aggiungi alla lista");
    await userEvent.type(field, "quella cosa verde{Enter}");

    await waitFor(() => expect(field).toHaveValue(""));
  });

  // m10: era l'ultimo dei tre consumatori di `searchIngredients` a catturare
  // l'errore in un `.catch` locale. Un 401 non arrivava alla QueryCache che
  // App.tsx aggancia al ritorno all'accesso: la sessione scadeva e il campo
  // smetteva semplicemente di suggerire, senza dire perché.
  it("una sessione scaduta durante la ricerca arriva alla QueryCache", async () => {
    const onError = vi.fn();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 401 })));

    renderField({ onAdd: added() }, new QueryCache({ onError }));
    await userEvent.type(screen.getByLabelText("Aggiungi alla lista"), "pomo");

    await waitFor(() => expect(onError).toHaveBeenCalled());
    expect(onError.mock.calls[0][0]).toBeInstanceOf(UnauthorizedError);
  });

  it("una ricerca che non risponde non blocca il testo libero, e lo dice", async () => {
    // la decisione di casa: i suggerimenti sono un aiuto, non un pedaggio. Il
    // testo libero deve passare comunque, e il silenzio di prima era una rinuncia
    // invisibile
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));
    const onAdd = added();
    renderField({ onAdd });

    const field = screen.getByLabelText("Aggiungi alla lista");
    await userEvent.type(field, "quella cosa verde");
    expect(await screen.findByRole("status")).toHaveTextContent(/autocomplete non risponde/i);

    await userEvent.click(screen.getByRole("button", { name: "Aggiungi" }));
    expect(onAdd).toHaveBeenCalledWith("quella cosa verde", undefined);
  });

  // S18: il backend non doppia un ingrediente già da comprare e risponde con la
  // voce che c'era, `added` falso. Non è un errore: si dice come in dispensa
  it("se la voce era già in lista lo dice, senza allarmi, e svuota il campo", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    renderField({ onAdd: vi.fn().mockResolvedValue({ added: false }) });

    const field = screen.getByLabelText("Aggiungi alla lista");
    await userEvent.type(field, "latte{Enter}");

    expect(await screen.findByRole("status")).toHaveTextContent("Era già in lista.");
    expect(screen.queryByRole("alert")).toBeNull();
    expect(field).toHaveValue("");
  });

  it("l'avviso «era già in lista» se ne va appena si scrive altro", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    renderField({ onAdd: vi.fn().mockResolvedValue({ added: false }) });

    const field = screen.getByLabelText("Aggiungi alla lista");
    await userEvent.type(field, "latte{Enter}");
    await screen.findByText("Era già in lista.");

    await userEvent.type(field, "u");
    expect(screen.queryByText("Era già in lista.")).toBeNull();
  });

  it("una voce aggiunta davvero non dice niente", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    renderField({ onAdd: vi.fn().mockResolvedValue({ added: true }) });

    const field = screen.getByLabelText("Aggiungi alla lista");
    await userEvent.type(field, "latte{Enter}");

    await waitFor(() => expect(field).toHaveValue(""));
    expect(screen.queryByText("Era già in lista.")).toBeNull();
  });

  it("offre un bersaglio visibile per il testo libero, non solo il tasto invio", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    const onAdd = added();
    renderField({ onAdd });

    await userEvent.type(screen.getByLabelText("Aggiungi alla lista"), "quella cosa verde");
    await userEvent.click(screen.getByRole("button", { name: "Aggiungi" }));

    expect(onAdd).toHaveBeenCalledWith("quella cosa verde", undefined);
  });
});
