import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusChip } from "./StatusChip";
import { STATUS_LABELS, STATUS_TONE } from "../../features/pantry/statusLabels";
import type { PantryStatus } from "../../domain/types";

// La mappa dei colori può essere giusta mentre il controllo che la gente tocca non
// la usa: è il difetto che su questo ramo è sopravvissuto tre volte (v. CLAUDE.md,
// prima lezione). Prima questo legame lo provava solo StatusToggle.test.tsx, che
// Task 9 ha cancellato con il resto del componente. `StatusChip` è ora l'unico
// posto in dispensa dove lo stato si vede, e va provato passando dal componente
// vero, non interrogando la mappa da sola.
describe("StatusChip", () => {
  it.each<PantryStatus>(["available", "low", "finished"])(
    "mostra la tinta e la parola di STATUS_TONE/STATUS_LABELS per %s",
    (status) => {
      render(<StatusChip status={status} />);
      const chip = screen.getByText(STATUS_LABELS[status]);
      for (const className of STATUS_TONE[status].tint.split(" ")) {
        expect(chip).toHaveClass(className);
      }
    }
  );
});
