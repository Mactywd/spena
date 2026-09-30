import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Alert } from "./Alert";

describe("Alert", () => {
  it.each([
    ["error", "text-danger"],
    ["note", "text-ink-soft"],
    ["degraded", "text-low"],
  ] as const)("il tono %s è un alert in %s", (tone, classe) => {
    render(<Alert tone={tone}>Qualcosa</Alert>);
    expect(screen.getByRole("alert")).toHaveClass(classe);
  });
});
