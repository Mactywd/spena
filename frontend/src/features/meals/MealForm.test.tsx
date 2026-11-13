import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MealForm } from "./MealForm";
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
});
