import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";

const ITEMS = [
  { id: "s1", raw_text: "pomodoro", ingredient_id: "i1", ingredient_name: "pomodoro",
    ingredient_category: "verdura", status: "pending", reason: "manual",
    created_at: "2026-09-11T10:00:00Z" },
];

describe("App", () => {
  it("riporta alla schermata di accesso quando una mutazione riceve un 401", async () => {
    // la lista carica normalmente, ma spuntare una voce (una mutazione, non una query)
    // trova la sessione scaduta: anche la MutationCache deve riportare al login.
    const fetchMock = vi.fn((_url: string, init?: RequestInit) => {
      if (init?.method === "PATCH") {
        return Promise.resolve(new Response("", { status: 401 }));
      }
      return Promise.resolve(new Response(JSON.stringify(ITEMS), { status: 200 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    const checkbox = await screen.findByRole("checkbox", { name: /pomodoro/ });
    await userEvent.click(checkbox);

    expect(await screen.findByRole("button", { name: "Entra" })).toBeDefined();
  });
});
