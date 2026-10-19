import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import { CopyField } from "./CopyField";

const INDIRIZZO = "https://spena.example/api/v1/activity/hc-webhook";

// Gli appunti del browser, finti. Il click diretto di user-event (`userEvent.click`, senza
// `setup()`) non installa i suoi: quel che c'è qui è quel che vede il componente.
function appunti(valore: unknown) {
  Object.defineProperty(window.navigator, "clipboard", { value: valore, configurable: true });
}

afterEach(() => {
  appunti(undefined);
});

function renderField() {
  return render(
    <NoticeProvider>
      <CopyField label="Indirizzo" value={INDIRIZZO} />
    </NoticeProvider>
  );
}

describe("CopyField", () => {
  it("mostra il testo in un campo di sola lettura, col suo nome", () => {
    renderField();

    const campo = screen.getByLabelText("Indirizzo");
    expect(campo).toHaveValue(INDIRIZZO);
    expect(campo).toHaveAttribute("readonly");
  });

  it("«Copia» scrive negli appunti e lo dice", async () => {
    const writeText = vi.fn(() => Promise.resolve());
    appunti({ writeText });
    renderField();

    await userEvent.click(screen.getByRole("button", { name: "Copia: Indirizzo" }));

    expect(writeText).toHaveBeenCalledWith(INDIRIZZO);
    expect(await screen.findByText("Copiato.")).toBeInTheDocument();
  });

  it("se il telefono non lascia copiare, seleziona il testo e dice come fare a mano", async () => {
    appunti({ writeText: () => Promise.reject(new Error("negato")) });
    renderField();

    await userEvent.click(screen.getByRole("button", { name: "Copia: Indirizzo" }));

    expect(
      await screen.findByText("Non riesco a copiare: tieni premuto sul testo e copialo a mano.")
    ).toBeInTheDocument();
    const campo = screen.getByLabelText<HTMLInputElement>("Indirizzo");
    expect(campo).toHaveFocus();
    expect([campo.selectionStart, campo.selectionEnd]).toEqual([0, INDIRIZZO.length]);
  });

  it("senza appunti del tutto (fuori da HTTPS) è lo stesso", async () => {
    appunti(undefined);
    renderField();

    await userEvent.click(screen.getByRole("button", { name: "Copia: Indirizzo" }));

    expect(
      await screen.findByText("Non riesco a copiare: tieni premuto sul testo e copialo a mano.")
    ).toBeInTheDocument();
  });
});
