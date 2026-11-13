import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChangeCard } from "./ChangeCard";
import { card, pantryItem, posts, renderWith, row, stubFetch } from "./testkit";

afterEach(() => vi.unstubAllGlobals());

const quiet = () => stubFetch((url) => (url.includes("/pantry") ? [[], 200] : [card(), 200]));

describe("ChangeCard", () => {
  it("ha le intestazioni e una riga con «Ora» e il select di «Diventa»", () => {
    quiet();
    renderWith(<ChangeCard card={card()} />);
    expect(screen.getByText("Voce")).toBeInTheDocument();
    expect(screen.getByText("Ora")).toBeInTheDocument();
    expect(screen.getByText("Diventa")).toBeInTheDocument();
    expect(screen.getByText("Ricotta")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Disponibile" })).toBeInTheDocument();
    expect(screen.getByLabelText("Diventa: Ricotta")).toHaveValue("finished");
    expect(screen.getByText("martedì 10 novembre · Cena")).toBeInTheDocument();
  });

  it("la riga «già in lista» ha la casella disattivata e non si toglie", async () => {
    quiet();
    renderWith(
      <ChangeCard
        card={card({
          rows: [row({ id: "r2", kind: "list", label: "latte", listed: true, checked: false, editable: false, from_status: null, to_status: null })],
        })}
      />
    );
    expect(screen.getByText("già in lista")).toBeInTheDocument();
    const box = screen.getByLabelText("Applica: latte");
    expect(box).toHaveAttribute("aria-disabled", "true");
    await userEvent.click(box);
    expect(box).not.toBeChecked();
  });

  it("«Applica» manda le correzioni locali e dice «Scheda applicata.»", async () => {
    const spy = stubFetch((url) => {
      if (url.includes("/apply")) return [card({ status: "applied" }), 200];
      return [[], 200];
    });
    renderWith(
      <ChangeCard
        card={card({
          rows: [row(), row({ id: "r2", label: "Parmigiano", from_status: "low", to_status: "finished" })],
        })}
      />
    );
    await userEvent.click(screen.getByLabelText("Applica: Parmigiano"));
    await userEvent.selectOptions(screen.getByLabelText("Diventa: Ricotta"), "low");
    expect(posts(spy)).toHaveLength(0); // niente parte prima di «Applica»
    await userEvent.click(screen.getByRole("button", { name: "Applica" }));
    expect(await screen.findByText("Scheda applicata.")).toBeInTheDocument();
    const [call] = posts(spy);
    expect(call.url).toBe("/api/v1/change-cards/c1/apply");
    expect(call.body.rows).toEqual([
      { id: "r1", checked: true, to_status: "low" },
      { id: "r2", checked: false, to_status: "finished" },
    ]);
    expect(await screen.findByText("Applicata.")).toBeInTheDocument();
  });

  it("«Applica» toccato due volte manda una richiesta sola", async () => {
    let release: () => void = () => {};
    const gate = new Promise<void>((r) => (release = r));
    const spy = vi.fn((url: unknown) => {
      if (String(url).includes("/apply"))
        return gate.then(() => new Response(JSON.stringify(card({ status: "applied" })), { status: 200 }));
      return Promise.resolve(new Response("[]", { status: 200 }));
    });
    vi.stubGlobal("fetch", spy);
    renderWith(<ChangeCard card={card()} />);
    const apply = screen.getByRole("button", { name: "Applica" });
    await userEvent.click(apply);
    await userEvent.click(apply);
    release();
    await screen.findByText("Applicata.");
    expect(posts(spy as never)).toHaveLength(1);
  });

  it("un 409 card_applied mostra la scheda applicata", async () => {
    stubFetch((url) =>
      url.includes("/apply")
        ? [{ code: "card_applied", detail: "La scheda era già applicata.", card: card({ status: "applied" }) }, 409]
        : [[], 200]
    );
    renderWith(<ChangeCard card={card()} />);
    await userEvent.click(screen.getByRole("button", { name: "Applica" }));
    expect(await screen.findByText("La scheda era già applicata.")).toBeInTheDocument();
    expect(screen.getByText("Applicata.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Applica" })).toBeNull();
  });

  it("un altro 409 mostra il suo detail", async () => {
    stubFetch((url) =>
      url.includes("/apply") ? [{ code: "discarded", detail: "La scheda è stata scartata.", card: null }, 409] : [[], 200]
    );
    renderWith(<ChangeCard card={card()} />);
    await userEvent.click(screen.getByRole("button", { name: "Applica" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("La scheda è stata scartata.");
  });

  it("«Scarta» manda discard e dice «Scheda scartata.»", async () => {
    const spy = stubFetch((url) => (url.includes("/discard") ? [card({ status: "discarded" }), 200] : [[], 200]));
    renderWith(<ChangeCard card={card()} />);
    await userEvent.click(screen.getByRole("button", { name: "Scarta" }));
    expect(await screen.findByText("Scheda scartata.")).toBeInTheDocument();
    expect(posts(spy)[0].url).toBe("/api/v1/change-cards/c1/discard");
    expect(screen.getByText("Scartata.")).toBeInTheDocument();
  });

  it("scheda vuota: la frase, e «Cerca in dispensa» aggiunge una riga", async () => {
    const spy = stubFetch((url) => {
      if (url.includes("/pantry")) return [[pantryItem("Parmigiano"), pantryItem("Latte", "p2")], 200];
      return [card({ rows: [row({ label: "Parmigiano" })] }), 200];
    });
    renderWith(<ChangeCard card={card({ rows: [] })} />);
    expect(
      screen.getByText("Nessuna voce: aggiungi quello che il pasto usa, o scarta la scheda.")
    ).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Cerca in dispensa"), "parm");
    const hit = await screen.findByRole("button", { name: "Parmigiano" });
    expect(screen.queryByText("Latte")).toBeNull();
    await userEvent.click(hit);
    await waitFor(() => expect(posts(spy)).toHaveLength(1));
    expect(posts(spy)[0]).toEqual({ url: "/api/v1/change-cards/c1/rows", body: { pantry_item_id: "p1" } });
  });

  it("«Aggiungi alla lista» manda il testo", async () => {
    const spy = quiet();
    renderWith(<ChangeCard card={card()} />);
    await userEvent.type(screen.getByLabelText("Aggiungi alla lista"), "basilico");
    await userEvent.click(screen.getByRole("button", { name: "Aggiungi" }));
    await waitFor(() => expect(posts(spy)).toHaveLength(1));
    expect(posts(spy)[0].body).toEqual({ raw_text: "basilico" });
  });

  it("una scheda applicata mostra «Applicata.», le note e nessun «Applica»", () => {
    quiet();
    renderWith(
      <ChangeCard
        card={card({
          status: "applied",
          rows: [row({ applied: true }), row({ id: "r2", label: "Pepe", applied: false, note: "La voce non c'era più." })],
        })}
      />
    );
    expect(screen.getByText("Applicata.")).toBeInTheDocument();
    expect(screen.getByText("La voce non c'era più.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Applica" })).toBeNull();
  });
});
