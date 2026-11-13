import { afterEach, describe, expect, it, vi } from "vitest";
import { act, screen } from "@testing-library/react";
import { PendingCards } from "./PendingCards";
import { card, renderWith, stubFetch } from "./testkit";

afterEach(() => vi.unstubAllGlobals());

describe("PendingCards", () => {
  it("elenca le schede con il collegamento «Apri»", async () => {
    stubFetch(() => [[card(), card({ id: "c2", title: "Altra scheda" })], 200]);
    renderWith(<PendingCards />);
    expect(await screen.findByText("Schede dei cambi da applicare")).toBeInTheDocument();
    const links = screen.getAllByRole("link", { name: "Apri" });
    expect(links.map((l) => l.getAttribute("href"))).toEqual(["/pasti/cambi/c1", "/pasti/cambi/c2"]);
  });

  it("senza schede non mostra niente", async () => {
    const spy = stubFetch(() => [[], 200]);
    renderWith(<PendingCards />);
    await vi.waitFor(() => expect(spy).toHaveBeenCalled());
    await act(async () => {
      await new Promise((r) => setTimeout(r, 20));
    });
    expect(screen.queryByText("Schede dei cambi da applicare")).toBeNull();
    expect(screen.queryByRole("link")).toBeNull();
  });
});
