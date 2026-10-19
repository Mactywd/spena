import { describe, expect, it } from "vitest";
import { sourceRef } from "./sourceRef";

describe("sourceRef", () => {
  it("un prompt corto passa com'è, dopo «prompt: »", () => {
    expect(sourceRef("senza basilico")).toBe("prompt: senza basilico");
  });

  it("un prompt lungo si accorcia a 500 caratteri, e l'ultimo è «…»", () => {
    const ref = sourceRef("a".repeat(1000));
    expect(ref).toHaveLength(500);
    expect(ref.startsWith("prompt: aaa")).toBe(true);
    expect(ref.endsWith("…")).toBe(true);
  });
});
