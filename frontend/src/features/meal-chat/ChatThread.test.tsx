import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
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
  it("`renderExtras` mette il suo contenuto sotto il messaggio giusto; senza, niente cambia", () => {
    const messages = [
      message(),
      message({ id: "a1", role: "assistant", text: "Ecco la proposta." }),
    ];
    const { rerender } = render(
      <ChatThread
        messages={messages}
        streaming={null}
        onUndo={vi.fn()}
        onRetry={vi.fn()}
        renderExtras={(m) => (m.id === "a1" ? <p>la scheda di a1</p> : null)}
      />
    );
    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(within(items[1]).getByText("la scheda di a1")).toBeInTheDocument();
    expect(within(items[0]).queryByText("la scheda di a1")).not.toBeInTheDocument();
    // la scheda sta sotto il fumetto, non sopra
    const bubble = within(items[1]).getByText("Ecco la proposta.");
    const extra = within(items[1]).getByText("la scheda di a1");
    expect(bubble.compareDocumentPosition(extra) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    rerender(<ChatThread messages={messages} streaming={null} onUndo={vi.fn()} onRetry={vi.fn()} />);
    expect(screen.queryByText("la scheda di a1")).not.toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });
});
