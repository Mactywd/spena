import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AddItemField } from "./AddItemField";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import { UnauthorizedError } from "../../api/client";

const POMODORO = { id: "i1", name: "pomodoro", display_name: "Pomodoro", category: "verdura" };
const PORRO = { id: "i9", name: "porro", display_name: "Porro", category: "verdura" };

/** Un'aggiunta riuscita, come la risponde il backend: la voce è nuova (S18). */
const added = () => vi.fn().mockResolvedValue({ added: true });

/** La ricerca dei suggerimenti passa da react-query, quindi il campo vuole il suo
 * provider: un 401 che non arriva alla QueryCache non riporta all'accesso. E
 * «Era già in lista.» esce dall'avviso unico: senza `NoticeProvider` non avrebbe dove
 * comparire. */
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
      <NoticeProvider>
        <AddItemField {...props} />
      </NoticeProvider>
    </QueryClientProvider>
  );
}

describe("AddItemField", () => {
  it("il campo dice cosa scriverci, e il + ha il suo nome", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    renderField({ onAdd: added() });
    expect(screen.getByLabelText("Aggiungi alla lista").getAttribute("placeholder")).toBe("Cosa manca?");
    expect(screen.getByRole("button", { name: "Aggiungi" })).toBeDefined();
  });

  it("suggerisce ingredienti mentre si digita", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify([POMODORO]), { status: 200 })
    ));
    renderField({ onAdd: added() });

    await userEvent.type(screen.getByLabelText("Aggiungi alla lista"), "pomo");
    expect(await screen.findByRole("option", { name: /Pomodoro/ })).toBeDefined();
  });

  it("l'elenco dei suggerimenti ha un nome, che dice di quale campo è", async () => {
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

  it("accetta testo libero con l'Invio, perché non deve bloccare", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    const onAdd = added();
    renderField({ onAdd });

    await userEvent.type(screen.getByLabelText("Aggiungi alla lista"), "quella cosa verde{Enter}");
    await waitFor(() => expect(onAdd).toHaveBeenCalledWith("quella cosa verde", undefined));
  });

  it("e col +: da telefono il tasto invio della tastiera non si vede", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    const onAdd = added();
    renderField({ onAdd });

    await userEvent.type(screen.getByLabelText("Aggiungi alla lista"), "  quella cosa verde  ");
    await userEvent.click(screen.getByRole("button", { name: "Aggiungi" }));
    expect(onAdd).toHaveBeenCalledWith("quella cosa verde", undefined);
  });

  it("il + a campo vuoto non aggiunge niente e porta nel campo", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    const onAdd = added();
    renderField({ onAdd });

    await userEvent.click(screen.getByRole("button", { name: "Aggiungi" }));
    expect(onAdd).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(screen.getByLabelText("Aggiungi alla lista"));
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

  it("un'aggiunta riuscita svuota il campo, e non dice niente", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    renderField({ onAdd: added() });

    const field = screen.getByLabelText("Aggiungi alla lista");
    await userEvent.type(field, "latte{Enter}");

    await waitFor(() => expect(field).toHaveValue(""));
    expect(screen.queryByText("Era già in lista.")).toBeNull();
  });

  // m10: un 401 durante la ricerca deve arrivare alla QueryCache che App.tsx aggancia
  // al ritorno all'accesso, non morire in un `.catch` locale
  it("una sessione scaduta durante la ricerca arriva alla QueryCache", async () => {
    const onError = vi.fn();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 401 })));

    renderField({ onAdd: added() }, new QueryCache({ onError }));
    await userEvent.type(screen.getByLabelText("Aggiungi alla lista"), "pomo");

    await waitFor(() => expect(onError).toHaveBeenCalled());
    expect(onError.mock.calls[0][0]).toBeInstanceOf(UnauthorizedError);
  });

  it("una ricerca che non risponde non blocca il testo libero, e lo dice", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));
    const onAdd = added();
    renderField({ onAdd });

    await userEvent.type(screen.getByLabelText("Aggiungi alla lista"), "quella cosa verde");
    // per testo e non per ruolo: la regione `status` dell'avviso unico c'è sempre
    expect(await screen.findByText(/autocomplete non risponde/i)).toBeDefined();

    await userEvent.click(screen.getByRole("button", { name: "Aggiungi" }));
    expect(onAdd).toHaveBeenCalledWith("quella cosa verde", undefined);
  });

  // S18: il backend non doppia un ingrediente già da comprare e risponde con la voce
  // che c'era, `added` falso. Non è un errore: lo dice l'avviso unico, con le stesse
  // parole della dispensa quando rimette in lista
  it("se la voce era già in lista lo dice nell'avviso, senza allarmi, e svuota il campo", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    renderField({ onAdd: vi.fn().mockResolvedValue({ added: false }) });

    const field = screen.getByLabelText("Aggiungi alla lista");
    await userEvent.type(field, "latte{Enter}");

    const status = await screen.findByRole("status");
    await waitFor(() => expect(status).toHaveTextContent("Era già in lista."));
    expect(screen.queryByRole("alert")).toBeNull();
    expect(field).toHaveValue("");
  });
});
