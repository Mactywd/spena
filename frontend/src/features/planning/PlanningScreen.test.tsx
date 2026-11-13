import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PlanningScreen } from "./PlanningScreen";
import {
  FOLLOW_UP,
  liveStream,
  message,
  planningChat,
  postUrls,
  proposal,
  renderAt,
  requests,
  stubFetch,
  where,
} from "./testkit";

const CURRENT = "/api/v1/planning/current";
const CONVERSATIONS = "/api/v1/planning/conversations";
const NOT_CONFIGURED = "Claude non è collegato: manca il token del piano sul server.";
const EMPTY = "Dimmi come vuoi pianificare: con quello che c'è in casa, o una bozza prima della spesa.";

afterEach(() => vi.unstubAllGlobals());

describe("Pianifica con Claude", () => {
  it("senza conversazione: la frase vuota, e «Invia» prima crea la conversazione e poi manda", async () => {
    const stream = liveStream();
    const spy = stubFetch((url, init) => {
      if (url === CURRENT) return [planningChat({ conversation_id: null }), 200];
      if (url === CONVERSATIONS && init?.method === "POST") return [planningChat(), 201];
      if (url === `${CONVERSATIONS}/k1/messages`) return stream.response;
      return [planningChat(), 200];
    });
    renderAt(<PlanningScreen />, "/pasti/pianifica");
    expect(screen.getByRole("heading", { name: "Pianifica con Claude" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Pasti/ })).toHaveAttribute("href", "/pasti");
    expect(await screen.findByText(EMPTY)).toBeInTheDocument();
    await userEvent.type(
      screen.getByRole("textbox", { name: "Messaggio per Claude" }),
      "Pianifichiamo la settimana"
    );
    await userEvent.click(screen.getByRole("button", { name: "Invia" }));
    await waitFor(() =>
      expect(requests(spy, "POST", `${CONVERSATIONS}/k1/messages`)).toEqual([
        { text: "Pianifichiamo la settimana" },
      ])
    );
    expect(postUrls(spy)).toEqual([CONVERSATIONS, `${CONVERSATIONS}/k1/messages`]);
    expect(where()).toBe("/pasti/pianifica?conversazione=k1");
    stream.close();
  });

  it("dal posto vuoto: crea la conversazione col posto, lo mostra e precompila il campo", async () => {
    const focused = planningChat({ focus: { day: "2026-11-13", slot: "dinner" } });
    const spy = stubFetch((url, init) => {
      if (url === CURRENT) return [planningChat({ conversation_id: null }), 200];
      if (url === CONVERSATIONS && init?.method === "POST") return [focused, 201];
      return [focused, 200];
    });
    renderAt(<PlanningScreen />, "/pasti/pianifica?giorno=2026-11-13&posto=dinner");
    expect(await screen.findByText("Per: venerdì 13 novembre · Cena")).toBeInTheDocument();
    expect(requests(spy, "POST", CONVERSATIONS)).toEqual([
      { focus: { day: "2026-11-13", slot: "dinner" } },
    ]);
    expect(screen.getByRole("textbox", { name: "Messaggio per Claude" })).toHaveValue(
      "Cosa mi proponi per venerdì 13 novembre a cena?"
    );
    expect(screen.getByRole("button", { name: "Togli il posto" })).toBeInTheDocument();
    await waitFor(() => expect(where()).toBe("/pasti/pianifica?conversazione=k1"));
  });

  it("dal posto vuoto con una conversazione aperta: la punta lì", async () => {
    const focused = planningChat({ focus: { day: "2026-11-13", slot: "lunch" } });
    let patched = false;
    const spy = stubFetch((url, init) => {
      if (url === CURRENT) return [planningChat(), 200];
      if (url === `${CONVERSATIONS}/k1` && init?.method === "PATCH") {
        patched = true;
        return [focused, 200];
      }
      return [patched ? focused : planningChat(), 200];
    });
    renderAt(<PlanningScreen />, "/pasti/pianifica?giorno=2026-11-13&posto=lunch");
    expect(await screen.findByText("Per: venerdì 13 novembre · Pranzo")).toBeInTheDocument();
    expect(requests(spy, "PATCH", `${CONVERSATIONS}/k1`)).toEqual([
      { focus: { day: "2026-11-13", slot: "lunch" } },
    ]);
    expect(requests(spy, "POST", CONVERSATIONS)).toEqual([]);
    expect(screen.getByRole("textbox", { name: "Messaggio per Claude" })).toHaveValue(
      "Cosa mi proponi per venerdì 13 novembre a pranzo?"
    );
  });

  it("«Togli il posto» toglie il posto", async () => {
    const focused = planningChat({ focus: { day: "2026-11-13", slot: "dinner" } });
    const spy = stubFetch((_url, init) =>
      init?.method === "PATCH" ? [planningChat(), 200] : [focused, 200]
    );
    renderAt(<PlanningScreen />, "/pasti/pianifica?conversazione=k1");
    await userEvent.click(await screen.findByRole("button", { name: "Togli il posto" }));
    await waitFor(() => expect(screen.queryByText(/^Per: /)).not.toBeInTheDocument());
    expect(requests(spy, "PATCH", `${CONVERSATIONS}/k1`)).toEqual([{ focus: null }]);
  });

  it("una proposta nello stream compare sotto il fumetto prima di `done`", async () => {
    const stream = liveStream();
    stubFetch((url, init) =>
      init?.method === "POST" && url.endsWith("/messages") ? stream.response : [planningChat(), 200]
    );
    renderAt(<PlanningScreen />, "/pasti/pianifica?conversazione=k1");
    await userEvent.type(
      await screen.findByRole("textbox", { name: "Messaggio per Claude" }),
      "Cosa ceno stasera?"
    );
    await userEvent.click(screen.getByRole("button", { name: "Invia" }));
    stream.send("start", { message: message({ status: "pending", text: "Cosa ceno stasera?" }) });
    stream.send("delta", { text: "Ti propongo una frittata." });
    stream.send("proposal", { proposal: proposal() });
    expect(await screen.findByText("Proposta")).toBeInTheDocument();
    expect(screen.getByText("Claude sta scrivendo…")).toBeInTheDocument();
    const reply = screen.getByText("Ti propongo una frittata.").closest("li")!;
    expect(within(reply).getByRole("button", { name: "Metti nella settimana" })).toBeInTheDocument();
    stream.close();
  });

  it("dopo «Metti nella settimana» il seguito parte subito come messaggio", async () => {
    const stream = liveStream();
    const withProposal = planningChat({
      messages: [
        message(),
        message({ id: "a1", role: "assistant", text: "Ecco la proposta.", proposals: [proposal()] }),
      ],
    });
    const spy = stubFetch((url, init) => {
      if (url.endsWith("/place")) return [{ chat: withProposal, meals: [], follow_up: FOLLOW_UP }, 200];
      if (init?.method === "POST" && url.endsWith("/messages")) return stream.response;
      return [withProposal, 200];
    });
    renderAt(<PlanningScreen />, "/pasti/pianifica?conversazione=k1");
    await userEvent.click(await screen.findByRole("button", { name: "Metti nella settimana" }));
    await waitFor(() =>
      expect(requests(spy, "POST", `${CONVERSATIONS}/k1/messages`)).toEqual([{ text: FOLLOW_UP }])
    );
    expect(requests(spy, "POST", "/api/v1/planning/proposals/p1/place")).toEqual([{ replace: false }]);
    stream.close();
  });

  it("messa mentre Claude scrive: il seguito aspetta nel campo, nessun secondo giro", async () => {
    const stream = liveStream();
    const spy = stubFetch((url, init) => {
      if (url.endsWith("/place")) return [{ chat: planningChat(), meals: [], follow_up: FOLLOW_UP }, 200];
      if (init?.method === "POST" && url.endsWith("/messages")) return stream.response;
      return [planningChat(), 200];
    });
    renderAt(<PlanningScreen />, "/pasti/pianifica?conversazione=k1");
    const field = await screen.findByRole("textbox", { name: "Messaggio per Claude" });
    await userEvent.type(field, "Cosa ceno stasera?");
    await userEvent.click(screen.getByRole("button", { name: "Invia" }));
    stream.send("start", { message: message({ status: "pending", text: "Cosa ceno stasera?" }) });
    stream.send("proposal", { proposal: proposal() });
    await userEvent.click(await screen.findByRole("button", { name: "Metti nella settimana" }));
    await waitFor(() => expect(field).toHaveValue(FOLLOW_UP));
    expect(requests(spy, "POST", `${CONVERSATIONS}/k1/messages`)).toHaveLength(1);
    stream.close();
  });

  it("«Nuova» crea una conversazione e l'indirizzo passa a lei", async () => {
    const spy = stubFetch((url, init) => {
      if (url === CONVERSATIONS && init?.method === "POST") return [planningChat({ conversation_id: "k2" }), 201];
      if (url === `${CONVERSATIONS}/k2`) return [planningChat({ conversation_id: "k2" }), 200];
      return [planningChat({ messages: [message()] }), 200];
    });
    renderAt(<PlanningScreen />, "/pasti/pianifica?conversazione=k1");
    expect(await screen.findByText("Pianifichiamo la settimana")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Nuova" }));
    await waitFor(() => expect(where()).toBe("/pasti/pianifica?conversazione=k2"));
    expect(requests(spy, "POST", CONVERSATIONS)).toEqual([{ focus: null }]);
    expect(await screen.findByText(EMPTY)).toBeInTheDocument();
  });

  it("un 503 dice perché e lascia il testo nel campo", async () => {
    stubFetch((url, init) =>
      init?.method === "POST" && url.endsWith("/messages")
        ? [{ code: "claude_not_configured", detail: NOT_CONFIGURED }, 503]
        : [planningChat(), 200]
    );
    renderAt(<PlanningScreen />, "/pasti/pianifica?conversazione=k1");
    const field = await screen.findByRole("textbox", { name: "Messaggio per Claude" });
    await userEvent.type(field, "Cosa ceno?");
    await userEvent.click(screen.getByRole("button", { name: "Invia" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(NOT_CONFIGURED);
    expect(field).toHaveValue("Cosa ceno?");
  });

  it("senza Claude, l'avviso del server in testa", async () => {
    stubFetch(() => [planningChat({ claude_ready: false, claude_notice: NOT_CONFIGURED }), 200]);
    renderAt(<PlanningScreen />, "/pasti/pianifica?conversazione=k1");
    expect(await screen.findByRole("alert")).toHaveTextContent(NOT_CONFIGURED);
  });
});
