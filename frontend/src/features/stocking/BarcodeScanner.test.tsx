import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { BarcodeScanner } from "./BarcodeScanner";
import { isBarcodeScanningSupported } from "./barcodeSupport";

afterEach(() => vi.unstubAllGlobals());

describe("BarcodeScanner", () => {
  it("riconosce il supporto nativo quando il browser lo espone", () => {
    vi.stubGlobal("BarcodeDetector", class {});
    expect(isBarcodeScanningSupported()).toBe(true);
  });

  it("resta utilizzabile senza supporto nativo, grazie alla riserva", () => {
    vi.unstubAllGlobals();
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
    vi.stubGlobal("BarcodeDetector", class {
      detect() {
        return Promise.resolve([]);
      }
    });
    const stopTrack = vi.fn();
    const getUserMedia = vi.fn().mockResolvedValue({
      getTracks: () => [{ stop: stopTrack }],
    });
    vi.stubGlobal("navigator", { mediaDevices: { getUserMedia } });

    const { unmount } = render(<BarcodeScanner onDetected={vi.fn()} onCancel={vi.fn()} />);
    await vi.waitFor(() => expect(getUserMedia).toHaveBeenCalled());
    unmount();

    expect(stopTrack).toHaveBeenCalled();
  });
});
