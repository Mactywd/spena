import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
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
});
