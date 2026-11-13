import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatThread } from "./ChatThread";
import type { ChatMessage, RecipeChange } from "../../domain/types";

function message(extra: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: "u1", role: "user", text: "Fallo con gli spinaci congelati", status: "sent", notice: null,
    created_at: "2026-11-13T19:00:00Z", changes: [], ...extra,
  };
}

function change(extra: Partial<RecipeChange> = {}): RecipeChange {
  return {
    id: "c1", summary: "spinaci congelati, padella unica", created_recipe: false,
    undone: false, undoable: true, ...extra,
  };
}

function renderThread(messages: ChatMessage[]) {
  const onUndo = vi.fn();
  const onRetry = vi.fn();
  render(<ChatThread messages={messages} streaming={null} onUndo={onUndo} onRetry={onRetry} />);
  return { onUndo, onRetry };
}

describe("ChatThread", () => {
  it("mostra i due messaggi e la modifica con «Annulla», che passa l'id", async () => {
    const { onUndo } = renderThread([
      message(),
      message({ id: "a1", role: "assistant", text: "Fatto: tutto in una padella.", changes: [change()] }),
    ]);
    expect(screen.getByText("Fallo con gli spinaci congelati")).toBeInTheDocument();
    expect(screen.getByText("Fatto: tutto in una padella.")).toBeInTheDocument();
    expect(screen.getByText("Ricetta aggiornata: spinaci congelati, padella unica")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(onUndo).toHaveBeenCalledWith("c1");
  });

  it("una modifica annullata lo dice, e non ha «Annulla»", () => {
    renderThread([
      message({
        id: "a1", role: "assistant", text: "Fatto.",
        changes: [change({ undone: true, undoable: false })],
      }),
    ]);
    expect(
      screen.getByText("Ricetta aggiornata: spinaci congelati, padella unica — annullata")
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Annulla" })).not.toBeInTheDocument();
  });

  it("una ricetta scritta da zero dice «Ricetta scritta»", () => {
    renderThread([
      message({
        id: "a1", role: "assistant", text: "Ecco la ricetta.",
        changes: [change({ created_recipe: true, summary: "pollo al limone in padella" })],
      }),
    ]);
    expect(screen.getByText("Ricetta scritta: pollo al limone in padella")).toBeInTheDocument();
  });

  it("un messaggio non risposto ha il suo avviso e «Riprova»", async () => {
    const failed = message({
      status: "failed",
      notice: "Claude non risponde: hai raggiunto il limite del piano, riprova dopo le 18:40",
    });
    const { onRetry } = renderThread([failed]);
    expect(
      screen.getByText("Claude non risponde: hai raggiunto il limite del piano, riprova dopo le 18:40")
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Riprova" }));
    expect(onRetry).toHaveBeenCalledWith(failed);
  });
});
