import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MealForm } from "./MealForm";
import { ApiError } from "../../api/client";
import type { Meal, MealBody } from "../../domain/types";

const INITIAL: MealBody = {
  day: "2026-11-10", slot: "dinner", dish: "", sides: null, away: false, leftover_of_id: null,
};

function candidate(id: string, dish: string, day: string, slot: Meal["slot"]): Meal {
  return {
    id, day, slot, week: "2026-11-09", dish, sides: null, away: false,
    status: "official", unrecorded: false, recipe: null, leftover_of: null,
  };
}

function renderForm(props: Partial<Parameters<typeof MealForm>[0]> = {}) {
  const save = vi.fn().mockResolvedValue(undefined);
  render(
    <MealForm
      initial={INITIAL}
      slotEditable={false}
      leftoverChoices={[]}
      submitLabel="Salva"
      save={save}
      onSaved={() => {}}
      {...props}
    />
  );
  return save;
}

describe("il modulo del pasto", () => {
  it("con il piatto vuoto dice «Scrivi il piatto.» e non manda niente", async () => {
    const save = renderForm();
    await userEvent.click(screen.getByRole("button", { name: "Salva" }));
    expect(screen.getByText("Scrivi il piatto.")).toBeInTheDocument();
    expect(save).not.toHaveBeenCalled();
  });

  it("manda gli accompagnamenti vuoti come null", async () => {
    const save = renderForm();
    await userEvent.type(screen.getByLabelText("Piatto"), "Frittata");
    await userEvent.click(screen.getByRole("button", { name: "Salva" }));
    await waitFor(() => expect(save).toHaveBeenCalled());
    expect(save).toHaveBeenCalledWith({
      day: "2026-11-10", slot: "dinner", dish: "Frittata", sides: null, away: false,
      leftover_of_id: null,
    });
  });

  it("offre «Avanzo di» con «Nessuno» e un pasto per voce, e ne manda l'id", async () => {
    const save = renderForm({
      leftoverChoices: [
        candidate("a", "Pollo arrosto", "2026-11-09", "dinner"),
        candidate("b", "Lasagne", "2026-11-10", "lunch"),
      ],
    });
    const select = screen.getByLabelText("Avanzo di");
    const labels = Array.from(select.querySelectorAll("option")).map((o) => o.textContent);
    expect(labels).toEqual([
      "Nessuno",
      "Pollo arrosto (lunedì 9 novembre, cena)",
      "Lasagne (martedì 10 novembre, pranzo)",
    ]);
    await userEvent.type(screen.getByLabelText("Piatto"), "Pollo di ieri");
    await userEvent.selectOptions(select, "a");
    await userEvent.click(screen.getByRole("button", { name: "Salva" }));
    await waitFor(() => expect(save).toHaveBeenCalled());
    expect(save.mock.calls[0][0]).toMatchObject({ leftover_of_id: "a" });
  });

  it("senza `slotEditable` non c'è né giorno né pasto", () => {
    renderForm();
    expect(screen.queryByLabelText("Giorno")).toBeNull();
    expect(screen.queryByLabelText("Pasto")).toBeNull();
  });
  describe("le domande del posto", () => {
    const SAVED_BODY = {
      day: "2026-11-10", slot: "dinner", dish: "Frittata", sides: null, away: false,
      leftover_of_id: null,
    };
    const occupant = (recipe: { id: string; title: string; in_book: boolean } | null) => ({
      ...candidate("o", "Pizza", "2026-11-10", "dinner"), recipe,
    });
    const taken = (recipe: { id: string; title: string; in_book: boolean } | null) =>
      new ApiError("C'è già «Pizza» in questo posto.", 409, {
        code: "slot_taken", occupant: occupant(recipe),
      });
    const leftoverAfter = (leftovers: number) =>
      new ApiError(
        leftovers === 1 ? "Martedì pranzo è un suo avanzo." : "Martedì pranzo e mercoledì cena sono suoi avanzi.",
        409,
        { code: "leftover_after", leftovers }
      );
    async function fill() {
      await userEvent.type(screen.getByLabelText("Piatto"), "Frittata");
      await userEvent.click(screen.getByRole("button", { name: "Salva" }));
    }

    it("il posto occupato da un pasto con la ricetta fuori dal ricettario lo dice prima di Sostituisci", async () => {
      const save = vi.fn().mockRejectedValue(taken({ id: "r", title: "Pizza", in_book: false }));
      renderForm({ save, onCancel: () => {} });
      await fill();
      expect(await screen.findByText("C'è già «Pizza» in questo posto.")).toBeInTheDocument();
      expect(
        screen.getByText("La sua ricetta non è nel ricettario: si elimina con il pasto.")
      ).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Sostituisci" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Annulla" })).toBeInTheDocument();
    });

    it("con la ricetta nel ricettario, o senza ricetta, la seconda frase non c'è", async () => {
      for (const recipe of [{ id: "r", title: "Pizza", in_book: true }, null]) {
        const save = vi.fn().mockRejectedValue(taken(recipe));
        const { unmount } = render(
          <MealForm initial={INITIAL} slotEditable={false} leftoverChoices={[]}
            submitLabel="Salva" save={save} onSaved={() => {}} />
        );
        await fill();
        expect(await screen.findByText("C'è già «Pizza» in questo posto.")).toBeInTheDocument();
        expect(screen.queryByText(/non è nel ricettario/)).toBeNull();
        unmount();
      }
    });

    it("un slot_taken senza occupante non rompe niente", async () => {
      const save = vi.fn().mockRejectedValue(
        new ApiError("C'è già «Pizza» in questo posto.", 409, { code: "slot_taken" })
      );
      renderForm({ save });
      await fill();
      expect(await screen.findByText("C'è già «Pizza» in questo posto.")).toBeInTheDocument();
      expect(screen.queryByText(/non è nel ricettario/)).toBeNull();
      expect(screen.getByRole("button", { name: "Sostituisci" })).toBeInTheDocument();
    });

    it("l'avanzo che verrebbe prima: la domanda e Sposta e stacca l'avanzo", async () => {
      const save = vi.fn().mockRejectedValueOnce(leftoverAfter(1)).mockResolvedValue(undefined);
      renderForm({ save });
      await fill();
      expect(await screen.findByText("Martedì pranzo è un suo avanzo.")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Annulla" })).toBeInTheDocument();
      await userEvent.click(screen.getByRole("button", { name: "Sposta e stacca l'avanzo" }));
      await waitFor(() => expect(save).toHaveBeenCalledTimes(2));
      expect(save).toHaveBeenLastCalledWith({ ...SAVED_BODY, detach_leftovers: true });
    });

    it("con più avanzi il pulsante dice «Sposta e stacca gli avanzi»", async () => {
      const save = vi.fn().mockRejectedValue(leftoverAfter(2));
      renderForm({ save });
      await fill();
      expect(
        await screen.findByText("Martedì pranzo e mercoledì cena sono suoi avanzi.")
      ).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Sposta e stacca gli avanzi" })).toBeInTheDocument();
    });

    it("il posto occupato e poi l'avanzo: due domande in fila", async () => {
      const save = vi
        .fn()
        .mockRejectedValueOnce(taken(null))
        .mockRejectedValueOnce(leftoverAfter(1))
        .mockResolvedValue(undefined);
      renderForm({ save });
      await fill();
      await userEvent.click(await screen.findByRole("button", { name: "Sostituisci" }));
      await userEvent.click(await screen.findByRole("button", { name: "Sposta e stacca l'avanzo" }));
      await waitFor(() => expect(save).toHaveBeenCalledTimes(3));
      expect(save).toHaveBeenLastCalledWith({ ...SAVED_BODY, replace: true, detach_leftovers: true });
    });

    it("con una domanda aperta i pulsanti del modulo non ci sono", async () => {
      const save = vi.fn().mockRejectedValue(leftoverAfter(1));
      renderForm({ save, onCancel: () => {} });
      await fill();
      await screen.findByText("Martedì pranzo è un suo avanzo.");
      expect(screen.queryByRole("button", { name: "Salva" })).toBeNull();
      expect(screen.getAllByRole("button", { name: "Annulla" })).toHaveLength(1);
      await userEvent.click(screen.getByRole("button", { name: "Annulla" }));
      expect(screen.queryByText("Martedì pranzo è un suo avanzo.")).toBeNull();
      expect(screen.getByRole("button", { name: "Salva" })).toBeInTheDocument();
      expect(screen.getAllByRole("button", { name: "Annulla" })).toHaveLength(1);
    });
  });
});
