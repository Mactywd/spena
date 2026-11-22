import { describe, expect, it, vi, type Mock } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { type ComponentProps } from "react";
import { PackageRow } from "./PackageRow";

type Props = ComponentProps<typeof PackageRow>;

function renderPackage(over: Partial<Props> = {}) {
  const props: Props = {
    name: "mele", index: 2, resolution: undefined, expiry: undefined, onExpiry: vi.fn(),
    returnFocusTo: null, onFocusReturned: vi.fn(), onOpen: vi.fn(), onLoose: vi.fn(),
    onChange: vi.fn(), onRemove: vi.fn(), ...over,
  };
  render(<PackageRow {...props} />);
  // le prop sono tutte `vi.fn()` (salvo ciò che il caso passa): il tipo lo dice, per `.mock`
  return props as Props & { onOpen: Mock; onLoose: Mock; onChange: Mock; onRemove: Mock };
}

describe("PackageRow", () => {
  it("da scegliere: le tre strade col numero della confezione nel nome, e ognuna fa la sua", async () => {
    const { onOpen, onLoose } = renderPackage();
    expect(screen.getByText("Confezione 2")).toBeDefined();
    const toolbar = screen.getByRole("toolbar", { name: "Come entra in dispensa: mele, confezione 2" });
    await userEvent.click(within(toolbar).getByRole("button", { name: "Codice a barre per mele, confezione 2" }));
    await userEvent.click(within(toolbar).getByRole("button", { name: "Cerca a catalogo per mele, confezione 2" }));
    await userEvent.click(within(toolbar).getByRole("button", { name: "Sfuso, senza marca: mele, confezione 2" }));
    expect(onOpen.mock.calls).toEqual([["scanner"], ["catalog"]]);
    expect(onLoose).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "+ scadenza per mele, confezione 2" })).toBeDefined();
  });

  it("scelta: dice a cosa, «Cambia» la disfa, e la ✕ toglie la confezione", async () => {
    const { onChange, onRemove } = renderPackage({ resolution: { kind: "loose" } });
    expect(screen.getByText("Sfuso")).toBeDefined();
    expect(screen.queryByRole("toolbar")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Cambia la scelta per mele, confezione 2" }));
    await userEvent.click(screen.getByRole("button", { name: "Togli la confezione 2 di mele" }));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onRemove).toHaveBeenCalledTimes(1);
  });

  it("il fuoco torna alla sua icona, non a quella della voce che la contiene", () => {
    const onFocusReturned = vi.fn();
    render(
      <div>
        <span data-trigger="scanner" className="contents">
          <button type="button">della voce</button>
        </span>
        <PackageRow
          name="mele" index={2} resolution={undefined} expiry={undefined} onExpiry={vi.fn()}
          returnFocusTo="scanner" onFocusReturned={onFocusReturned} onOpen={vi.fn()}
          onLoose={vi.fn()} onChange={vi.fn()} onRemove={vi.fn()}
        />
      </div>
    );
    expect(document.activeElement).toBe(
      screen.getByRole("button", { name: "Codice a barre per mele, confezione 2" })
    );
    expect(onFocusReturned).toHaveBeenCalled();
  });
});
