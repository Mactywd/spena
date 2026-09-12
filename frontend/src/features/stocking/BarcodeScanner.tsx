import { useEffect, useRef, useState } from "react";
import { BrowserMultiFormatReader } from "@zxing/browser";
import { buttonClasses } from "../../components/ui/buttonClasses";

export function BarcodeScanner({
  onDetected,
  onCancel,
}: {
  onDetected: (code: string) => void;
  onCancel: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState<string | null>(null);
  // il rilascio dell'effetto in corso, raggiungibile da fuori dall'effetto: il
  // pulsante Annulla spegne la fotocamera da sé, senza dipendere dal fatto che
  // il chiamante smonti davvero questo componente
  const releaseRef = useRef<() => void>(() => {});

  useEffect(() => {
    // Il flusso della fotocamera è nostro (lo apriamo noi con getUserMedia) e va
    // chiuso noi in ogni caso. `reader.decodeFromVideoElement` di zxing restituisce
    // dei controls il cui stop() ferma solo il ciclo di lettura interno (un
    // setTimeout che rilegge il canvas) e non tocca lo stream: verificato leggendo
    // BrowserCodeReader.scan in @zxing/browser, che non chiama mai stop sui track.
    // Fidarsi solo di quello lascerebbe la fotocamera accesa dopo aver lasciato lo
    // schermo. Per questo il flusso si tiene qui e si ferma sempre a parte.
    let stopped = false;
    let stream: MediaStream | null = null;
    let stopDecoding: (() => void) | null = null;

    // L'unica uscita: smontaggio, codice letto, Annulla, errore dopo
    // l'acquisizione, effetto che riparte. Passa tutto da qui, è idempotente, e
    // `stopped` fa da guardia perché una risoluzione in ritardo ci ripassi.
    function release() {
      stopped = true;
      stopDecoding?.();
      stopDecoding = null;
      stream?.getTracks().forEach((track) => track.stop());
      stream = null;
    }

    releaseRef.current = release;

    function detected(code: string) {
      // letto il codice la fotocamera non serve più: il lookup che segue può
      // durare, e tenerla accesa nel frattempo è la stessa fuga più corta
      release();
      onDetected(code);
    }

    async function start() {
      try {
        const NativeDetector = (globalThis as { BarcodeDetector?: new (options: unknown) => {
          detect: (source: HTMLVideoElement) => Promise<{ rawValue: string }[]>;
        } }).BarcodeDetector;

        // assegnato prima di ogni altra cosa: il permesso può arrivare dopo che la
        // pulizia è già girata (il prompt dura secondi, e si lascia lo schermo
        // mentre è aperto), e allora è `release()` qui sotto a fermare i track che
        // nessun altro vedrebbe più
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "environment" },
        });
        if (stopped || !videoRef.current) return release();
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        if (stopped || !videoRef.current) return release();

        if (NativeDetector) {
          const detector = new NativeDetector({ formats: ["ean_13", "ean_8", "upc_a", "upc_e"] });
          const tick = async () => {
            if (stopped || !videoRef.current) return;
            const found = await detector.detect(videoRef.current).catch(() => []);
            if (stopped) return;
            if (found.length > 0) return detected(found[0].rawValue);
            requestAnimationFrame(tick);
          };
          tick();
        } else {
          const reader = new BrowserMultiFormatReader();
          const controls = await reader.decodeFromVideoElement(videoRef.current, (result) => {
            if (result && !stopped) detected(result.getText());
          });
          stopDecoding = () => controls.stop();
          // la pulizia può essere girata durante quell'await: allora questi
          // controls sono già orfani e vanno fermati subito
          if (stopped) release();
        }
      } catch {
        // fotocamera negata, non disponibile, o play() rifiutata dalle politiche
        // di autoplay quando lo stream è già acceso: si degrada, non si blocca, e
        // quel che era già stato acquisito si spegne
        const wasReleased = stopped;
        release();
        if (!wasReleased) setError("Fotocamera non disponibile. Puoi inserire il prodotto a mano.");
      }
    }

    start();
    return release;
  }, [onDetected]);

  return (
    <div className="flex flex-col gap-3">
      {error ? (
        <p role="alert" className="text-sm text-low">{error}</p>
      ) : (
        <video ref={videoRef} className="w-full rounded-card bg-black" muted playsInline />
      )}
      <button
        type="button"
        onClick={() => {
          releaseRef.current();
          onCancel();
        }}
        className={buttonClasses("ghost")}
      >
        Annulla
      </button>
    </div>
  );
}
