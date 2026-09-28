import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ShoppingEntryCard } from "./ShoppingEntryCard";
import type { ShoppingItem } from "../../domain/types";

function item(id: string, status: ShoppingItem["status"]): ShoppingItem {
  return {
    id, raw_text: id, ingredient_id: null, ingredient_name: null, ingredient_category: null,
    ingredient_kind: null, status, reason: "manual", created_at: "2026-09-28T10:00:00Z",
  };
}

function renderCard(items: ShoppingItem[] | undefined, failed = false) {
  return render(
    <MemoryRouter>
      <ShoppingEntryCard items={items} failed={failed} />
    </MemoryRouter>
  );
}

describe("ShoppingEntryCard", () => {
  it("porta a /sistema e conta quel che è nel carrello", () => {
    renderCard([item("a", "checked"), item("b", "pending"), item("c", "checked")]);
    const link = screen.getByRole("link", { name: /Sistema la spesa/ });
    expect(link.getAttribute("href")).toBe("/sistema");
    expect(screen.getByText("2 nel carrello")).toBeDefined();
  });

  it("resta anche con il carrello vuoto, e lo dice (D3)", () => {
    renderCard([item("b", "pending")]);
    expect(screen.getByText("Niente nel carrello, per ora")).toBeDefined();
  });

  it("finché la lista non è arrivata non dice niente del suo contenuto", () => {
    renderCard(undefined);
    expect(screen.getByText("Metti via quello che hai comprato")).toBeDefined();
  });

  it("a lista fallita non conta i dati vecchi, e la strada resta aperta", () => {
    renderCard([item("a", "checked")], true);
    expect(screen.getByText("Metti via quello che hai comprato")).toBeDefined();
    expect(screen.queryByText("1 nel carrello")).toBeNull();
    expect(screen.getByRole("link", { name: /Sistema la spesa/ })).toBeDefined();
  });
});
