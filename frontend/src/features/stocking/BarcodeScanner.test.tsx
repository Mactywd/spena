import { describe, expect, it, vi, afterEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { BarcodeScanner } from "./BarcodeScanner";
import { isBarcodeScanningSupported } from "./barcodeSupport";

// La strada zxing (ogni browser senza lettore nativo: Safari, Firefox) va
// esercitata come quella nativa. Il lettore vero carica WebAssembly e non
// decodifica niente in jsdom: qui conta solo che i suoi controls vengano
// fermati e che lo stream venga rilasciato comunque.
const zxing = vi.hoisted(() => ({ decode: vi.fn(), stopDecoding: vi.fn() }));

vi.mock("@zxing/browser", () => ({
  BrowserMultiFormatReader: class {
    decodeFromVideoElement(
      _video: HTMLVideoElement,
      callback: (result: { getText: () => string } | undefined) => void
    ) {
      zxing.decode(callback);
      return Promise.resolve({ stop: zxing.stopDecoding });
    }
  },
}));

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  zxing.decode.mockClear();
  zxing.stopDecoding.mockClear();
});

/** Uno stream finto che sa solo dire se i suoi track sono stati fermati. */
function fakeStream() {
  const stop = vi.fn();
  return { stop, stream: { getTracks: () => [{ stop }] } as unknown as MediaStream };
}

function stubCamera(stream: MediaStream) {
  const getUserMedia = vi.fn().mockResolvedValue(stream);
  vi.stubGlobal("navigator", { mediaDevices: { getUserMedia } });
  return getUserMedia;
}

function stubNativeDetector(codes: string[]) {
  vi.stubGlobal(
    "BarcodeDetector",
    class {
      detect() {
        return Promise.resolve(codes.map((rawValue) => ({ rawValue })));
      }
    }
  );
}

describe("BarcodeScanner", () => {
  // `isBarcodeScanningSupported` restituisce una costante: niente può distinguere
  // un browser dall'altro, quindi un solo test è tutto quel che può dire.
  it("dichiara la lettura possibile su ogni browser, grazie alla riserva zxing", () => {
    expect(isBarcodeScanningSupported()).toBe(true);
  });

  it("spiega cosa fare se la fotocamera viene negata", async () => {
    vi.stubGlobal("navigator", {
      mediaDevices: { getUserMedia: vi.fn().mockRejectedValue(new Error("NotAllowedError")) },
    });
    render(<BarcodeScanner onDetected={vi.fn()} onCancel={vi.fn()} />);
    expect(await screen.findByText(/inserire il prodotto a mano/i)).toBeDefined();
  });

  it("rilascia la fotocamera quando lo schermo viene smontato", async () => {
    // la fuga da controllare: se lo stop dello stream manca nella pulizia
    // dell'effetto, la fotocamera del telefono resta accesa dopo aver lasciato
    // lo schermo. `controls.stop()` di zxing ferma solo il ciclo di lettura,
    // non lo stream, quindi questo test non può fidarsi solo di quello.
    stubNativeDetector([]);
    const { stop, stream } = fakeStream();
    const getUserMedia = stubCamera(stream);

    const { unmount } = render(<BarcodeScanner onDetected={vi.fn()} onCancel={vi.fn()} />);
    await vi.waitFor(() => expect(getUserMedia).toHaveBeenCalled());
    unmount();

    expect(stop).toHaveBeenCalled();
  });

  it("rilascia la fotocamera anche sulla strada zxing, senza lettore nativo", async () => {
    // nessun BarcodeDetector stubbato: è la strada di Safari e Firefox
    const { stop, stream } = fakeStream();
    stubCamera(stream);

    const { unmount } = render(<BarcodeScanner onDetected={vi.fn()} onCancel={vi.fn()} />);
    await vi.waitFor(() => expect(zxing.decode).toHaveBeenCalled());
    unmount();

    expect(stop).toHaveBeenCalled();
    expect(zxing.stopDecoding).toHaveBeenCalled();
  });

  it("rilascia lo stream anche se lo schermo si smonta mentre il permesso è in sospeso", async () => {
    // il prompt dei permessi dura secondi: smontare in quella finestra faceva
    // girare la pulizia con `stream` ancora nullo, e nessuno fermava più i track
    // dello stream che arrivava dopo
    const { stop, stream } = fakeStream();
    let grant: (value: MediaStream) => void = () => {};
    const getUserMedia = vi.fn(
      () =>
        new Promise<MediaStream>((resolve) => {
          grant = resolve;
        })
    );
    vi.stubGlobal("navigator", { mediaDevices: { getUserMedia } });

    const { unmount } = render(<BarcodeScanner onDetected={vi.fn()} onCancel={vi.fn()} />);
    await vi.waitFor(() => expect(getUserMedia).toHaveBeenCalled());
    unmount();
    grant(stream);

    await vi.waitFor(() => expect(stop).toHaveBeenCalled());
  });

  it("spegne la fotocamera appena un codice è stato letto", async () => {
    // letto il codice, la fotocamera non serve più: tenerla accesa per tutta la
    // durata del lookup è la stessa fuga, solo più corta
    stubNativeDetector(["52010"]);
    const { stop, stream } = fakeStream();
    stubCamera(stream);
    const onDetected = vi.fn();

    render(<BarcodeScanner onDetected={onDetected} onCancel={vi.fn()} />);

    await vi.waitFor(() => expect(onDetected).toHaveBeenCalledWith("52010"));
    expect(stop).toHaveBeenCalled();
  });

  it("spegne la fotocamera quando si annulla, senza attendere lo smontaggio", async () => {
    stubNativeDetector([]);
    const { stop, stream } = fakeStream();
    const getUserMedia = stubCamera(stream);
    const onCancel = vi.fn();

    render(<BarcodeScanner onDetected={vi.fn()} onCancel={onCancel} />);
    await vi.waitFor(() => expect(getUserMedia).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: "Annulla" }));

    expect(onCancel).toHaveBeenCalled();
    await vi.waitFor(() => expect(stop).toHaveBeenCalled());
  });

  it("rilascia lo stream se qualcosa fallisce dopo averlo ottenuto", async () => {
    // `play()` può essere rifiutata dalle politiche di autoplay: l'errore arriva
    // quando la fotocamera è già accesa, e degradare al manuale senza spegnerla
    // lascerebbe la spia del telefono accesa su uno schermo che dice "non
    // disponibile"
    stubNativeDetector([]);
    const { stop, stream } = fakeStream();
    stubCamera(stream);
    vi.spyOn(HTMLMediaElement.prototype, "play").mockRejectedValue(new Error("NotAllowedError"));

    render(<BarcodeScanner onDetected={vi.fn()} onCancel={vi.fn()} />);

    expect(await screen.findByText(/inserire il prodotto a mano/i)).toBeDefined();
    expect(stop).toHaveBeenCalled();
  });

  it("non lascia aperto il primo stream se l'effetto riparte", async () => {
    // un re-render che cambia l'identità di `onDetected` fa ripartire l'effetto:
    // il secondo getUserMedia non deve accumularsi sul primo
    stubNativeDetector([]);
    const first = fakeStream();
    const second = fakeStream();
    const getUserMedia = vi
      .fn()
      .mockResolvedValueOnce(first.stream)
      .mockResolvedValueOnce(second.stream);
    vi.stubGlobal("navigator", { mediaDevices: { getUserMedia } });

    const { rerender } = render(<BarcodeScanner onDetected={vi.fn()} onCancel={vi.fn()} />);
    await vi.waitFor(() => expect(getUserMedia).toHaveBeenCalledTimes(1));
    rerender(<BarcodeScanner onDetected={vi.fn()} onCancel={vi.fn()} />);

    await vi.waitFor(() => expect(getUserMedia).toHaveBeenCalledTimes(2));
    await vi.waitFor(() => expect(first.stop).toHaveBeenCalled());
    expect(second.stop).not.toHaveBeenCalled();
  });
});
