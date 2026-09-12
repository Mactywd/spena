import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
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
});
