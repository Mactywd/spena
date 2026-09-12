import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AddItemField } from "./AddItemField";

const POMODORO = { id: "i1", name: "pomodoro", display_name: "Pomodoro", category: "verdura" };

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
});
