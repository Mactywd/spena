import { afterEach, describe, expect, it, vi } from "vitest";
import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PlanningScreen } from "./PlanningScreen";
import { planningChatKey } from "./api";
import type { Meal } from "../../domain/types";
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
const NOT_CONFIGURED = "Claude non è collegato: manca la chiave API sul server.";
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

  it("Continua manda il messaggio fisso sulla pianificazione", async () => {
    const stream = liveStream();
    const spy = stubFetch((_url, init) =>
      init?.method === "POST"
        ? stream.response
        : [
            planningChat({
              messages: [
                message({ id: "a1", role: "assistant", text: "Ecco.", notice: "Claude si è fermato.", can_continue: true }),
              ],
            }),
            200,
          ]
    );
    renderAt(<PlanningScreen />, "/pasti/pianifica?conversazione=k1");
    await userEvent.click(await screen.findByRole("button", { name: "Continua" }));
    await waitFor(() =>
      expect(requests(spy, "POST", `${CONVERSATIONS}/k1/messages`)).toEqual([
        { text: "Continua da dove ti sei fermato." },
      ])
    );
    stream.close();
  });

  it("messa mentre Claude scrive: il seguito parte da solo dopo `done`, e il campo resta com'è", async () => {
    const first = liveStream();
    const second = liveStream();
    const streams = [first, second];
    const spy = stubFetch((url, init) => {
      if (url.endsWith("/place")) return [{ chat: planningChat(), meals: [], follow_up: FOLLOW_UP }, 200];
      if (init?.method === "POST" && url.endsWith("/messages")) return streams.shift()!.response;
      return [planningChat(), 200];
    });
    renderAt(<PlanningScreen />, "/pasti/pianifica?conversazione=k1");
    const field = await screen.findByRole("textbox", { name: "Messaggio per Claude" });
    await userEvent.type(field, "Cosa ceno stasera?");
    await userEvent.click(screen.getByRole("button", { name: "Invia" }));
    first.send("start", { message: message({ status: "pending", text: "Cosa ceno stasera?" }) });
    first.send("proposal", { proposal: proposal() });
    await userEvent.click(await screen.findByRole("button", { name: "Metti nella settimana" }));
    await userEvent.type(field, "e domani?");
    // finché il giro è in volo, nessun secondo messaggio
    await screen.findByText("Pasti messi nella settimana.");
    expect(requests(spy, "POST", `${CONVERSATIONS}/k1/messages`)).toEqual([{ text: "Cosa ceno stasera?" }]);
    first.send("done", { chat: planningChat() });
    first.close();
    await waitFor(() =>
      expect(requests(spy, "POST", `${CONVERSATIONS}/k1/messages`)).toEqual([
        { text: "Cosa ceno stasera?" },
        { text: FOLLOW_UP },
      ])
    );
    expect(field).toHaveValue("e domani?");
    second.close();
  });

  it("il seguito rifiutato non si perde e non tocca il testo scritto", async () => {
    const first = liveStream();
    let messages = 0;
    stubFetch((url, init) => {
      if (url.endsWith("/place")) return [{ chat: planningChat(), meals: [], follow_up: FOLLOW_UP }, 200];
      if (init?.method === "POST" && url.endsWith("/messages")) {
        messages += 1;
        return messages === 1
          ? first.response
          : [{ code: "claude_not_configured", detail: NOT_CONFIGURED }, 503];
      }
      return [planningChat(), 200];
    });
    renderAt(<PlanningScreen />, "/pasti/pianifica?conversazione=k1");
    const field = await screen.findByRole("textbox", { name: "Messaggio per Claude" });
    await userEvent.type(field, "Cosa ceno stasera?");
    await userEvent.click(screen.getByRole("button", { name: "Invia" }));
    first.send("start", { message: message({ status: "pending", text: "Cosa ceno stasera?" }) });
    first.send("proposal", { proposal: proposal() });
    await userEvent.click(await screen.findByRole("button", { name: "Metti nella settimana" }));
    await userEvent.type(field, "e domani?");
    first.send("done", { chat: planningChat() });
    first.close();
    expect(await screen.findByText(NOT_CONFIGURED)).toBeInTheDocument();
    await waitFor(() => expect(field).toHaveValue(`e domani?\n\n${FOLLOW_UP}`));
  });

  it("mentre Claude risponde «Nuova» dice perché non si può ancora", async () => {
    const stream = liveStream();
    const spy = stubFetch((url, init) =>
      init?.method === "POST" && url.endsWith("/messages") ? stream.response : [planningChat(), 200]
    );
    renderAt(<PlanningScreen />, "/pasti/pianifica?conversazione=k1");
    await userEvent.type(await screen.findByRole("textbox", { name: "Messaggio per Claude" }), "Ciao");
    await userEvent.click(screen.getByRole("button", { name: "Invia" }));
    const nuova = screen.getByRole("button", { name: "Nuova" });
    await waitFor(() => expect(nuova).toHaveAttribute("aria-disabled", "true"));
    expect(nuova.hasAttribute("disabled")).toBe(false);
    expect(nuova).toHaveAccessibleDescription("Aspetta che Claude finisca di rispondere.");
    await userEvent.click(nuova);
    expect(requests(spy, "POST", CONVERSATIONS)).toEqual([]);
    stream.send("done", { chat: planningChat() });
    stream.close();
    await waitFor(() => expect(nuova).not.toHaveAttribute("aria-disabled"));
    expect(screen.queryByText("Aspetta che Claude finisca di rispondere.")).not.toBeInTheDocument();
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

  it("dopo un 503 l'avviso si legge una volta", async () => {
    stubFetch((url, init) =>
      init?.method === "POST" && url.endsWith("/messages")
        ? [{ code: "claude_not_configured", detail: NOT_CONFIGURED }, 503]
        : [planningChat({ claude_ready: false, claude_notice: NOT_CONFIGURED }), 200]
    );
    renderAt(<PlanningScreen />, "/pasti/pianifica?conversazione=k1");
    const field = await screen.findByRole("textbox", { name: "Messaggio per Claude" });
    await userEvent.type(field, "Cosa ceno?");
    await userEvent.click(screen.getByRole("button", { name: "Invia" }));
    await waitFor(() => expect(field).toHaveValue("Cosa ceno?"));
    expect(screen.getAllByText(NOT_CONFIGURED)).toHaveLength(1);
  });

  it("senza Claude, un rifiuto con un altro testo si legge comunque", async () => {
    const OTHER = "Claude sta già rispondendo in un'altra conversazione.";
    stubFetch((url, init) =>
      init?.method === "POST" && url.endsWith("/messages")
        ? [{ code: "claude_busy", detail: OTHER }, 409]
        : [planningChat({ claude_ready: false, claude_notice: NOT_CONFIGURED }), 200]
    );
    renderAt(<PlanningScreen />, "/pasti/pianifica?conversazione=k1");
    const field = await screen.findByRole("textbox", { name: "Messaggio per Claude" });
    await userEvent.type(field, "Cosa ceno?");
    await userEvent.click(screen.getByRole("button", { name: "Invia" }));
    expect(await screen.findByText(OTHER)).toBeInTheDocument();
    expect(screen.getAllByText(NOT_CONFIGURED)).toHaveLength(1);
  });

  it("la conferma dei posti occupati resta quando la risposta si salva", async () => {
    const reply = (id: string) =>
      planningChat({
        messages: [
          message(),
          message({ id, role: "assistant", text: "Ecco la proposta.", proposals: [proposal()] }),
        ],
      });
    const PIZZA = {
      id: "m9", day: "2026-11-14", slot: "lunch", week: "2026-11-09", dish: "Pizza", sides: null,
      away: false, status: "official", unrecorded: false, recipe: null, leftover_of: null,
    } as Meal;
    const PLACE = "/api/v1/planning/proposals/p1/place";
    let saved = "a1";
    const spy = stubFetch((url, init) => {
      if (url === PLACE) {
        return JSON.parse(String(init?.body)).replace
          ? [{ chat: reply("a2"), meals: [], follow_up: FOLLOW_UP }, 200]
          : [{ code: "slots_taken", detail: "posti occupati", chat: reply("a1"), occupants: [PIZZA] }, 409];
      }
      return [reply(saved), 200];
    });
    const client = renderAt(<PlanningScreen />, "/pasti/pianifica?conversazione=k1");
    await userEvent.click(await screen.findByRole("button", { name: "Metti nella settimana" }));
    expect(await screen.findByText("Questi posti sono occupati:")).toBeInTheDocument();
    // la risposta salvata porta la proposta in un messaggio con un altro id: il `<li>` ha
    // un'altra chiave e la scheda si rimonta. react-query avvisa gli osservatori con un
    // setTimeout(0), quindi il ridisegno arriva dopo `act`: si aspetta il pulsante nuovo.
    saved = "a2";
    const before = screen.getByRole("button", { name: "Sostituisci e metti" });
    act(() => client.setQueryData(planningChatKey("k1"), reply("a2")));
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Sostituisci e metti" })).not.toBe(before)
    );
    expect(before.isConnected).toBe(false);
    expect(screen.getByText("Questi posti sono occupati:")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Sostituisci e metti" }));
    await waitFor(() => expect(requests(spy, "POST", PLACE)).toEqual([{ replace: false }, { replace: true }]));
  });
});
