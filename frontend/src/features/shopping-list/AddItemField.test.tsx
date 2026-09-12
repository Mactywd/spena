import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AddItemField } from "./AddItemField";

const POMODORO = { id: "i1", name: "pomodoro", display_name: "Pomodoro", category: "verdura" };
const PORRO = { id: "i9", name: "porro", display_name: "Porro", category: "verdura" };

describe("AddItemField", () => {
  it("suggerisce ingredienti mentre si digita", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify([POMODORO]), { status: 200 })
    ));
    render(<AddItemField onAdd={vi.fn()} />);

    await userEvent.type(screen.getByLabelText("Aggiungi alla lista"), "pomo");
    expect(await screen.findByRole("option", { name: /Pomodoro/ })).toBeDefined();
  });

  it("scegliendo un suggerimento passa l'ingrediente risolto", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify([POMODORO]), { status: 200 })
    ));
    const onAdd = vi.fn();
    render(<AddItemField onAdd={onAdd} />);

    await userEvent.type(screen.getByLabelText("Aggiungi alla lista"), "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));

    expect(onAdd).toHaveBeenCalledWith("pomodoro", "i1");
  });

  it("accetta testo libero senza corrispondenze, perché non deve bloccare", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    const onAdd = vi.fn();
    render(<AddItemField onAdd={onAdd} />);

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

    render(<AddItemField onAdd={vi.fn()} />);
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
    render(<AddItemField onAdd={onAdd} />);

    const field = screen.getByLabelText("Aggiungi alla lista");
    await userEvent.type(field, "quella cosa verde{Enter}");

    expect(await screen.findByRole("alert")).toBeDefined();
    expect(field).toHaveValue("quella cosa verde");
  });

  it("un'aggiunta riuscita svuota il campo", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    render(<AddItemField onAdd={vi.fn().mockResolvedValue(undefined)} />);

    const field = screen.getByLabelText("Aggiungi alla lista");
    await userEvent.type(field, "quella cosa verde{Enter}");

    await waitFor(() => expect(field).toHaveValue(""));
  });

  it("offre un bersaglio visibile per il testo libero, non solo il tasto invio", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    const onAdd = vi.fn();
    render(<AddItemField onAdd={onAdd} />);

    await userEvent.type(screen.getByLabelText("Aggiungi alla lista"), "quella cosa verde");
    await userEvent.click(screen.getByRole("button", { name: "Aggiungi" }));

    expect(onAdd).toHaveBeenCalledWith("quella cosa verde", undefined);
  });
});
