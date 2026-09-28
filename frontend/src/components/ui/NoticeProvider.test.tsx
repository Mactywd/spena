import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { NoticeProvider } from "./NoticeProvider";
import { NOTICE_MS, useNotice, type NoticeInput } from "./noticeContext";

function Trigger({ notice }: { notice: NoticeInput }) {
  const show = useNotice();
  return <button onClick={() => show(notice)}>mostra</button>;
}

describe("NoticeProvider", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("mostra l'avviso come stato, e se ne va dopo sei secondi", () => {
    render(
      <NoticeProvider>
        <Trigger notice={{ text: "4 in dispensa · 3 restano in lista" }} />
      </NoticeProvider>
    );
    fireEvent.click(screen.getByText("mostra"));
    expect(screen.getByRole("status")).toHaveTextContent("4 in dispensa · 3 restano in lista");
    act(() => vi.advanceTimersByTime(NOTICE_MS));
    expect(screen.queryByText("4 in dispensa · 3 restano in lista")).toBeNull();
  });

  it("l'azione esegue e chiude l'avviso", () => {
    const undo = vi.fn();
    render(
      <NoticeProvider>
        <Trigger notice={{ text: "Tolto: kiwi", action: { label: "Annulla", onClick: undo } }} />
      </NoticeProvider>
    );
    fireEvent.click(screen.getByText("mostra"));
    fireEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(undo).toHaveBeenCalledOnce();
    expect(screen.queryByText("Tolto: kiwi")).toBeNull();
  });

  it("un'azione che mostra un avviso nuovo lo lascia lì, non lo chiude", () => {
    // «Annulla» del doppione fa proprio questo: chiama `show` con un nuovo testo
    // prima di tornare. Un `setCurrent(null)` incondizionato dopo l'azione
    // cancellerebbe anche quello nuovo, perché React mette in coda entrambi gli
    // aggiornamenti dello stesso gestore
    function Chain() {
      const show = useNotice();
      return (
        <button
          onClick={() =>
            show({
              text: "primo",
              action: { label: "Annulla", onClick: () => show({ text: "secondo" }) },
            })
          }
        >
          mostra
        </button>
      );
    }
    render(
      <NoticeProvider>
        <Chain />
      </NoticeProvider>
    );
    fireEvent.click(screen.getByText("mostra"));
    fireEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(screen.getByText("secondo")).toBeInTheDocument();
  });

  it("un avviso nuovo prende il posto del vecchio e riparte da sei secondi", () => {
    function Two() {
      const show = useNotice();
      return (
        <>
          <button onClick={() => show({ text: "primo" })}>uno</button>
          <button onClick={() => show({ text: "secondo" })}>due</button>
        </>
      );
    }
    render(
      <NoticeProvider>
        <Two />
      </NoticeProvider>
    );
    fireEvent.click(screen.getByText("uno"));
    act(() => vi.advanceTimersByTime(NOTICE_MS - 1000));
    fireEvent.click(screen.getByText("due"));
    expect(screen.queryByText("primo")).toBeNull();
    act(() => vi.advanceTimersByTime(NOTICE_MS - 1000));
    expect(screen.getByText("secondo")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1000));
    expect(screen.queryByText("secondo")).toBeNull();
  });
});
