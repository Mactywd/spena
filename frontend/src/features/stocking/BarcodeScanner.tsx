import { useEffect, useRef, useState } from "react";
import { BrowserMultiFormatReader } from "@zxing/browser";

export function BarcodeScanner({
  onDetected,
  onCancel,
}: {
  onDetected: (code: string) => void;
  onCancel: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stopped = false;
    // Il flusso della fotocamera è nostro (lo apriamo noi con getUserMedia) e va
    // chiuso noi in ogni caso. `reader.decodeFromVideoElement` di zxing restituisce
    // dei controls il cui stop() ferma solo il ciclo di lettura interno (un
    // setTimeout che rilegge il canvas) e non tocca lo stream: verificato leggendo
    // BrowserCodeReader.scan in @zxing/browser, che non chiama mai stop sui track.
    // Fidarsi solo di quello lascerebbe la fotocamera accesa dopo aver lasciato lo
    // schermo. Per questo il flusso si tiene qui e si ferma sempre a parte.
    let stream: MediaStream | null = null;
    let stopDecoding: (() => void) | null = null;

    async function start() {
      try {
        const NativeDetector = (globalThis as { BarcodeDetector?: new (options: unknown) => {
          detect: (source: HTMLVideoElement) => Promise<{ rawValue: string }[]>;
        } }).BarcodeDetector;

        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "environment" },
        });
        if (stopped || !videoRef.current) return;
        videoRef.current.srcObject = stream;
        await videoRef.current.play();

        if (NativeDetector) {
          const detector = new NativeDetector({ formats: ["ean_13", "ean_8", "upc_a", "upc_e"] });
          const tick = async () => {
            if (stopped || !videoRef.current) return;
            const found = await detector.detect(videoRef.current).catch(() => []);
            if (found.length > 0) return onDetected(found[0].rawValue);
            requestAnimationFrame(tick);
          };
          tick();
        } else {
          const reader = new BrowserMultiFormatReader();
          const controls = await reader.decodeFromVideoElement(videoRef.current, (result) => {
            if (result) onDetected(result.getText());
          });
          stopDecoding = () => controls.stop();
        }
      } catch {
        // fotocamera negata o non disponibile: si degrada, non si blocca
        setError("Fotocamera non disponibile. Puoi inserire il prodotto a mano.");
      }
    }

    start();
    return () => {
      stopped = true;
      stopDecoding?.();
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, [onDetected]);

  return (
    <div className="flex flex-col gap-3">
      {error ? (
        <p role="alert" className="text-sm text-amber-700">{error}</p>
      ) : (
        <video ref={videoRef} className="w-full rounded-lg bg-black" muted playsInline />
      )}
      <button type="button" onClick={onCancel} className="text-sm text-neutral-500">
        Annulla
      </button>
    </div>
  );
}
