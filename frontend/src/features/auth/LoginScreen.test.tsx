import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LoginScreen } from "./LoginScreen";

describe("LoginScreen", () => {
  it("chiama onSuccess dopo un accesso riuscito", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    const onSuccess = vi.fn();
    render(<LoginScreen onSuccess={onSuccess} />);

    await userEvent.type(screen.getByLabelText("Password"), "apriti sesamo");
    await userEvent.click(screen.getByRole("button", { name: "Entra" }));

    expect(onSuccess).toHaveBeenCalled();
  });

  it("distingue un server irraggiungibile da una password sbagliata", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    render(<LoginScreen onSuccess={vi.fn()} />);

    await userEvent.type(screen.getByLabelText("Password"), "qualunque");
    await userEvent.click(screen.getByRole("button", { name: "Entra" }));

    expect(await screen.findByText(/Impossibile contattare il server/)).toBeDefined();
  });

  it("mostra un messaggio leggibile quando la password è sbagliata", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 401 })));
    render(<LoginScreen onSuccess={vi.fn()} />);

    await userEvent.type(screen.getByLabelText("Password"), "sbagliata");
    await userEvent.click(screen.getByRole("button", { name: "Entra" }));

    expect(await screen.findByText("Password errata")).toBeDefined();
  });

  // Consegna 6a (spec T3 §4.7): l'accesso dal giro non dava il fuoco al campo, lasciava
  // «Password errata» a video mentre si riscriveva, e non c'era modo di vedere la password
  it("il campo prende il fuoco all'apertura", () => {
    vi.stubGlobal("fetch", vi.fn());
    render(<LoginScreen onSuccess={vi.fn()} />);
    expect(screen.getByLabelText("Password")).toHaveFocus();
  });

  it("a campo vuoto «Entra» non ancora: dice perché, e né il tocco né l'Invio mandano niente", async () => {
    const spy = vi.fn();
    vi.stubGlobal("fetch", spy);
    render(<LoginScreen onSuccess={vi.fn()} />);
    const entra = screen.getByRole("button", { name: "Entra" });
    // `unavailableReason` e non `disabled`: resta raggiungibile, e il perché si legge
    expect(entra).toHaveAttribute("aria-disabled", "true");
    expect(entra.hasAttribute("disabled")).toBe(false);
    expect(entra).toHaveAccessibleDescription("Scrivi la password per entrare.");
    await userEvent.type(screen.getByLabelText("Password"), "{Enter}");
    await userEvent.click(entra);
    expect(spy).not.toHaveBeenCalled();

    await userEvent.type(screen.getByLabelText("Password"), "a");
    expect(entra).not.toHaveAttribute("aria-disabled");
    expect(screen.queryByText("Scrivi la password per entrare.")).toBeNull();
  });

  it("in volo «Entra» è spento ma tiene il fuoco, e non parte un secondo accesso", async () => {
    let risolvi: ((response: Response) => void) | null = null;
    const pendente = new Promise<Response>((resolve) => {
      risolvi = resolve;
    });
    const spy = vi.fn(() => pendente);
    vi.stubGlobal("fetch", spy);
    const onSuccess = vi.fn();
    render(<LoginScreen onSuccess={onSuccess} />);

    await userEvent.type(screen.getByLabelText("Password"), "apriti sesamo");
    const entra = screen.getByRole("button", { name: "Entra" });
    await userEvent.click(entra);
    await waitFor(() => expect(entra).toHaveAttribute("aria-disabled", "true"));
    expect(entra.hasAttribute("disabled")).toBe(false);
    expect(entra).toHaveFocus();
    await userEvent.click(entra);
    expect(spy).toHaveBeenCalledTimes(1);

    risolvi!(new Response(null, { status: 204 }));
    await waitFor(() => expect(onSuccess).toHaveBeenCalledOnce());
  });

  it("«Password errata» se ne va appena si riscrive", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 401 })));
    render(<LoginScreen onSuccess={vi.fn()} />);
    const campo = screen.getByLabelText("Password");
    await userEvent.type(campo, "sbagliata");
    await userEvent.click(screen.getByRole("button", { name: "Entra" }));
    expect(await screen.findByText("Password errata")).toBeDefined();

    await userEvent.type(campo, "x");
    expect(screen.queryByText("Password errata")).toBeNull();
  });

  it("«Mostra password» mostra e rinasconde la password, col nome fisso e aria-pressed", async () => {
    const spy = vi.fn();
    vi.stubGlobal("fetch", spy);
    render(<LoginScreen onSuccess={vi.fn()} />);
    const campo = screen.getByLabelText("Password");
    expect(campo).toHaveAttribute("type", "password");

    const mostra = screen.getByRole("button", { name: "Mostra password" });
    // un pulsante di sola icona: il nome sta nell'`aria-label`
    expect(mostra.textContent).toBe("");
    expect(mostra).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(mostra);
    expect(campo).toHaveAttribute("type", "text");
    // lo stesso pulsante, lo stesso nome, premuto, col fuoco ancora lì
    expect(screen.getByRole("button", { name: "Mostra password" })).toBe(mostra);
    expect(mostra).toHaveAttribute("aria-pressed", "true");
    expect(mostra).toHaveFocus();

    await userEvent.click(mostra);
    expect(campo).toHaveAttribute("type", "password");
    // e non è un submit: l'occhio non manda la password
    expect(spy).not.toHaveBeenCalled();
  });
});
