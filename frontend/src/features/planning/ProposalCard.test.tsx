import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProposalCard } from "./ProposalCard";
import {
  FOLLOW_UP,
  planningChat,
  proposal,
  proposalRow,
  renderAt,
  requests,
  stubFetch,
} from "./testkit";
import type { Meal } from "../../domain/types";

const PLACE = "/api/v1/planning/proposals/p1/place";

const THREE_ROWS = proposal({
  rows: [
    proposalRow(),
    proposalRow({
      day: "2026-11-14", slot: "lunch", dish: "Pasta al pesto", sides: null, effect: "replace",
      occupant: { id: "m9", day: "2026-11-14", slot: "lunch", dish: "Pizza", recipe_id: null },
    }),
    proposalRow({
      day: "2026-11-14", slot: "dinner", dish: "Pasta e ceci", sides: null, effect: "officialize",
      occupant: { id: "m8", day: "2026-11-14", slot: "dinner", dish: "Pasta", recipe_id: null },
    }),
  ],
});

const PIZZA = {
  id: "m9", day: "2026-11-14", slot: "lunch", week: "2026-11-09", dish: "Pizza", sides: null,
  away: false, status: "official", unrecorded: false, recipe: null, leftover_of: null,
} as Meal;

afterEach(() => vi.unstubAllGlobals());

describe("la proposta", () => {
  it("una riga per posto: giorno, piatto, accompagnamenti e cosa fa al posto occupato", () => {
    stubFetch(() => [{}, 200]);
    renderAt(<ProposalCard proposal={THREE_ROWS} onPlaced={vi.fn()} />, "/pasti/pianifica");
    expect(screen.getByText("Proposta")).toBeInTheDocument();
    expect(screen.getByText("venerdì 13 novembre · Cena")).toBeInTheDocument();
    expect(screen.getByText("Frittata di spinaci")).toBeInTheDocument();
    expect(screen.getByText("insalata · pane")).toBeInTheDocument();
    expect(screen.getByText("sabato 14 novembre · Pranzo")).toBeInTheDocument();
    expect(screen.getByText("Al posto di «Pizza»")).toBeInTheDocument();
    expect(screen.getByText("La bozza «Pasta» diventa ufficiale")).toBeInTheDocument();
  });

  it("una bozza si intitola «Bozza per la spesa»", () => {
    stubFetch(() => [{}, 200]);
    renderAt(<ProposalCard proposal={proposal({ kind: "draft" })} onPlaced={vi.fn()} />, "/pasti/pianifica");
    expect(screen.getByText("Bozza per la spesa")).toBeInTheDocument();
    expect(screen.queryByText("Proposta")).not.toBeInTheDocument();
  });

  it("«Metti nella settimana» manda la proposta, avvisa e passa il seguito", async () => {
    const spy = stubFetch((url, init) =>
      url === PLACE && init?.method === "POST"
        ? [{ chat: planningChat(), meals: [], follow_up: FOLLOW_UP }, 200]
        : [{}, 200]
    );
    const onPlaced = vi.fn();
    renderAt(<ProposalCard proposal={proposal()} onPlaced={onPlaced} />, "/pasti/pianifica");
    await userEvent.click(screen.getByRole("button", { name: "Metti nella settimana" }));
    expect(await screen.findByText("Pasti messi nella settimana.")).toBeInTheDocument();
    expect(requests(spy, "POST", PLACE)).toEqual([{ replace: false }]);
    expect(onPlaced).toHaveBeenCalledWith(FOLLOW_UP);
  });

  it("i posti occupati chiedono la conferma, e «Sostituisci e metti» rimanda con replace", async () => {
    const spy = stubFetch((url, init) => {
      if (url !== PLACE) return [{}, 200];
      const body = JSON.parse(String(init?.body));
      return body.replace
        ? [{ chat: planningChat(), meals: [], follow_up: FOLLOW_UP }, 200]
        : [{ code: "slots_taken", detail: "posti occupati", chat: planningChat(), occupants: [PIZZA] }, 409];
    });
    const onPlaced = vi.fn();
    renderAt(<ProposalCard proposal={THREE_ROWS} onPlaced={onPlaced} />, "/pasti/pianifica");
    await userEvent.click(screen.getByRole("button", { name: "Metti nella settimana" }));
    expect(await screen.findByText("Questi posti sono occupati:")).toBeInTheDocument();
    expect(screen.getByText("sabato 14 novembre · Pranzo: «Pizza»")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Annulla" })).toBeInTheDocument();
    expect(onPlaced).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Sostituisci e metti" }));
    expect(await screen.findByText("Pasti messi nella settimana.")).toBeInTheDocument();
    expect(requests(spy, "POST", PLACE)).toEqual([{ replace: false }, { replace: true }]);
    expect(onPlaced).toHaveBeenCalledWith(FOLLOW_UP);
  });

  it("«Annulla» chiude la conferma senza mandare niente", async () => {
    const spy = stubFetch(() => [
      { code: "slots_taken", detail: "posti occupati", chat: planningChat(), occupants: [PIZZA] },
      409,
    ]);
    renderAt(<ProposalCard proposal={THREE_ROWS} onPlaced={vi.fn()} />, "/pasti/pianifica");
    await userEvent.click(screen.getByRole("button", { name: "Metti nella settimana" }));
    await userEvent.click(await screen.findByRole("button", { name: "Annulla" }));
    expect(screen.queryByText("Questi posti sono occupati:")).not.toBeInTheDocument();
    expect(requests(spy, "POST", PLACE)).toHaveLength(1);
  });

  it("toccato due volte, manda una richiesta sola", async () => {
    let release!: (response: Response) => void;
    const pending = new Promise<Response>((resolve) => {
      release = resolve;
    });
    const spy = stubFetch((url) => (url === PLACE ? pending : [{}, 200]));
    renderAt(<ProposalCard proposal={proposal()} onPlaced={vi.fn()} />, "/pasti/pianifica");
    const button = screen.getByRole("button", { name: "Metti nella settimana" });
    await userEvent.click(button);
    await userEvent.click(button);
    expect(button).toHaveAttribute("aria-disabled", "true");
    expect(requests(spy, "POST", PLACE)).toHaveLength(1);
    release(
      new Response(JSON.stringify({ chat: planningChat(), meals: [], follow_up: FOLLOW_UP }), { status: 200 })
    );
    expect(await screen.findByText("Pasti messi nella settimana.")).toBeInTheDocument();
    expect(requests(spy, "POST", PLACE)).toHaveLength(1);
  });

  it("già messa (409 `proposal_placed`), nessun errore", async () => {
    stubFetch(() => [
      { code: "proposal_placed", detail: "già messa", chat: planningChat() },
      409,
    ]);
    const onPlaced = vi.fn();
    renderAt(<ProposalCard proposal={proposal()} onPlaced={onPlaced} />, "/pasti/pianifica");
    await userEvent.click(screen.getByRole("button", { name: "Metti nella settimana" }));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Metti nella settimana" })).not.toHaveAttribute("aria-disabled")
    );
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(onPlaced).not.toHaveBeenCalled();
  });

  it("messa: «Messa nella settimana.» e nessun pulsante", () => {
    stubFetch(() => [{}, 200]);
    renderAt(<ProposalCard proposal={proposal({ status: "placed" })} onPlaced={vi.fn()} />, "/pasti/pianifica");
    const card = screen.getByText("Messa nella settimana.").closest("section")!;
    expect(within(card).queryByRole("button")).not.toBeInTheDocument();
  });

  it("sostituita: lo dice, e nessun pulsante", () => {
    stubFetch(() => [{}, 200]);
    renderAt(
      <ProposalCard proposal={proposal({ status: "superseded" })} onPlaced={vi.fn()} />,
      "/pasti/pianifica"
    );
    expect(screen.getByText("Sostituita da una proposta più nuova.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Metti nella settimana" })).not.toBeInTheDocument();
  });
});
