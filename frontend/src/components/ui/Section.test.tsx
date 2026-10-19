import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { Section } from "./Section";

describe("Section", () => {
  it("è una regione col nome del reparto, e dice quante righe porta", () => {
    render(
      <Section category="latticini" count={3}>
        <p>Latte</p>
      </Section>
    );
    const region = screen.getByRole("region", { name: "Latticini" });
    expect(region).toHaveTextContent("3");
    expect(region).toHaveTextContent("Latte");
  });

  it("il quadratino porta la tinta del reparto", () => {
    render(<Section category="latticini">x</Section>);
    const badge = screen.getByRole("region", { name: "Latticini" }).querySelector("[data-dept-badge]");
    expect(badge?.className).toContain("bg-dept-blue");
  });

  it("senza reparto si chiama «Senza reparto», e un titolo dato vince", () => {
    render(
      <>
        <Section category={null}>a</Section>
        <Section category="altro" title="Da abbinare">b</Section>
      </>
    );
    expect(screen.getByRole("region", { name: "Senza reparto" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Da abbinare" })).toBeInTheDocument();
  });

  it("dentro la sezione le righe non hanno linee di separazione", () => {
    render(<Section category="frutta">x</Section>);
    const region = screen.getByRole("region", { name: "Frutta" });
    expect(region.innerHTML).not.toContain("divide-");
  });

  // --- S15: il titolo che apre e chiude ---

  it("senza `onToggle` è la sezione di sempre: nessun pulsante, l'`h2` col solo nome", () => {
    render(
      <Section category="latticini" count={3}>
        <p>Latte</p>
      </Section>
    );
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByRole("heading", { level: 2, name: "Latticini" })).toBeInTheDocument();
  });

  it("con `onToggle` il titolo intero è un pulsante dentro l'`h2`, che controlla il contenuto", () => {
    const onToggle = vi.fn();
    render(
      <Section category="latticini" count={3} onToggle={onToggle}>
        <p>Latte</p>
      </Section>
    );
    const heading = screen.getByRole("heading", { level: 2 });
    const button = within(heading).getByRole("button");
    // quadratino, nome, numero e chevron: tutto dentro il pulsante
    expect(button).toHaveAccessibleName(/^Latticini\s+3$/);
    expect(button.querySelector("[data-dept-badge]")).not.toBeNull();
    expect(button.querySelector(".tabler-icon-chevron-down")).not.toBeNull();
    // `Array.from`: la libreria del progetto è `DOM` senza `DOM.Iterable`, e un `NodeList`
    // non si scorre con `for…of`
    for (const svg of Array.from(button.querySelectorAll("svg"))) {
      expect(svg.closest("[aria-hidden=true]")).not.toBeNull();
    }
    expect(button).toHaveAttribute("aria-expanded", "true");
    const content = document.getElementById(button.getAttribute("aria-controls")!);
    expect(content).toHaveTextContent("Latte");
    expect(content).not.toHaveAttribute("hidden");
    fireEvent.click(button);
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("chiusa: il contenuto ha `hidden`, la regione tiene il nome del reparto, il titolo porta la nota", () => {
    render(
      <Section category="latticini" count={3} collapsed onToggle={() => {}} closedNote="1 finito">
        <p>Latte</p>
      </Section>
    );
    // il nome della regione è il solo reparto: chi la cerca per nome la trova chiusa e aperta
    const region = screen.getByRole("region", { name: "Latticini" });
    const button = within(region).getByRole("button");
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(button).toHaveAccessibleName(/^Latticini\s+3\s+·\s+1 finito$/);
    expect(button.querySelector(".tabler-icon-chevron-right")).not.toBeNull();
    expect(document.getElementById(button.getAttribute("aria-controls")!)).toHaveAttribute("hidden");
    // fuori dalla pagina accessibile, quindi anche dall'ordine del Tab
    expect(screen.queryByText("Latte")).not.toBeVisible();
  });

  it("aperta, la nota non c'è: le righe sono lì sotto", () => {
    render(
      <Section category="latticini" count={3} collapsed={false} onToggle={() => {}} closedNote="1 finito">
        <p>Latte</p>
      </Section>
    );
    expect(screen.queryByText("1 finito")).toBeNull();
    expect(screen.getByRole("button")).toHaveAccessibleName(/^Latticini\s+3$/);
  });
});
