import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { PlanSections } from "./PlanSections";
import { callsText, formatTokens } from "./format";
import type { PlanSection } from "./types";

const SEZIONI: PlanSection[] = [
  {
    call_site: "meal_chat",
    label: "Chat dei piatti",
    calls: 3,
    tokens: 3600,
    note: "sul piano di Claude, non a consumo",
  },
];

describe("PlanSections", () => {
  it("il titolo «Claude», e per sezione il nome, chiamate e token, la nota", () => {
    render(<PlanSections sections={SEZIONI} />);

    expect(screen.getByText("Claude")).toBeInTheDocument();
    expect(screen.getByText("Chat dei piatti")).toBeInTheDocument();
    expect(screen.getByText(`${callsText(3)} · 3.600 token`)).toBeInTheDocument();
    expect(screen.getByText("sul piano di Claude, non a consumo")).toBeInTheDocument();
  });

  it("formatTokens usa il punto delle migliaia, sempre", () => {
    expect(formatTokens(0)).toBe("0");
    expect(formatTokens(999)).toBe("999");
    expect(formatTokens(3600)).toBe("3.600");
    expect(formatTokens(48300)).toBe("48.300");
    expect(formatTokens(1234567)).toBe("1.234.567");
  });
});
