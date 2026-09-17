import { useEffect, useState } from "react";
import { FillSlider } from "./FillSlider";
import { fillForStatus } from "./fillZones";
import { Alert } from "../../components/ui/Alert";
import { StatusChip } from "../../components/ui/StatusChip";
import type { PantryItem, RestockResult } from "../../domain/types";

/** Il nome con cui l'utente chiama questa voce: la marca se c'è, l'ingrediente
 * altrimenti. Entra anche nel nome accessibile della X, perché «Togli dalla
 * dispensa» ripetuto identico su trenta righe non dice quale riga si sta togliendo. */
export function itemLabel(item: PantryItem): string {
  return item.product_name ?? item.ingredient_name;
}

/** Una riga della dispensa.
 *
 * `removed` è la lapide: la riga resta dov'era, con l'annulla dentro, per i secondi
 * in cui il gesto si può disfare. Sparisce da sé quando lo schermo ricarica. Se
 * `failed` è vero mentre la lapide è a video, è l'annulla stesso che ha fallito:
 * il messaggio compare dentro la lapide (non ha più senso accanto al cursore, che
 * qui non c'è), e la lapide non scade da sola — solo un altro annulla, riuscito
 * stavolta, la può togliere.
 */
export function PantryRow({
  item,
  busy,
  removed,
  failed,
  onFill,
  onRemove,
  onUndo,
  onRestock,
}: {
  item: PantryItem;
  busy: boolean;
  removed: boolean;
  failed: boolean;
  onFill: (percent: number) => Promise<PantryItem>;
  onRemove: () => void;
  onUndo: () => void;
  onRestock: () => Promise<RestockResult>;
}) {
  // la domanda vive qui e non nello schermo: riguarda questa riga, e fuori di qui
  // sarebbe un avviso in cima a una dispensa lunga, cioè fuori schermo
  const [asking, setAsking] = useState(false);
  const [restocked, setRestocked] = useState<RestockResult | null>(null);
  // mai un vicolo cieco: se il rientro in lista fallisce, la domanda torna a
  // video (non resta chiusa su un errore muto) e «Sì» è di nuovo un modo di riprovare
  const [restockFailed, setRestockFailed] = useState(false);

  // la riga non si smonta quando diventa una lapide (stessa chiave, stesso
  // fiber): senza questo, la domanda risposta prima dell'archiviazione resta
  // accesa in memoria e, al ritorno dall'annulla, si ripresenta da sola senza
  // nessun gesto nuovo dell'utente. Il difetto è fra due rami della stessa riga,
  // non fra due righe: si azzera qui, seguendo `removed`, in entrambe le direzioni.
  useEffect(() => {
    setAsking(false);
    setRestocked(null);
    setRestockFailed(false);
  }, [removed]);

  async function fill(percent: number) {
    setRestocked(null);
    setRestockFailed(false);
    try {
      const updated = await onFill(percent);
      // Quali stati chiedono lo dice il server, non una soglia ricopiata qui.
      // Chiede anche il giallo, e non solo lo zero: «quasi finito» è il momento in
      // cui ricomprare è ancora in tempo, mentre allo zero te ne accorgi in cucina.
      // I due stati sono scritti per esteso invece di «diverso da disponibile»:
      // se un giorno ne nascesse un quarto, questa riga deve smettere di compilare
      // e non decidere da sé che anche quello vuole la domanda.
      setAsking(updated.status === "finished" || updated.status === "low");
    } catch {
      // il guasto lo mostra già lo schermo, accanto a questa riga
      setAsking(false);
    }
  }

  async function askRestock() {
    // la domanda resta a video finché la richiesta è in volo (non si chiude
    // subito, di ottimismo): è quello che permette a `busy` di disabilitare
    // «Sì»/«No» sul serio, allo stesso modo in cui il resto del file disabilita
    // il proprio controllo durante una mutazione, invece di farlo sparire prima
    setRestockFailed(false);
    try {
      const result = await onRestock();
      setAsking(false);
      setRestocked(result);
    } catch {
      setRestocked(null);
      setRestockFailed(true);
    }
  }

  if (removed) {
    return (
      <li className="flex flex-col gap-2 p-3" role="status">
        <div className="flex min-h-11 items-center justify-between gap-3">
          <span className="min-w-0 truncate text-ink-soft">
            <span className="font-medium text-ink">{itemLabel(item)}</span> Tolta dalla dispensa
          </span>
          <button
            type="button"
            disabled={busy}
            onClick={onUndo}
            className="min-h-11 shrink-0 px-2 text-sm font-medium text-brand disabled:opacity-40"
          >
            Annulla
          </button>
        </div>
        {failed && <Alert>Non sono riuscito a salvare la modifica. Riprova.</Alert>}
      </li>
    );
  }

  return (
    <li className="flex flex-col gap-2.5 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {/* la marca che hai comprato è più utile del nome generico */}
          <span className="font-medium">{itemLabel(item)}</span>
          {/* lo spazio è scritto a mano perché `ml-2` è un margine, non del testo:
              senza, il nome accessibile della riga si legge «Total 0%Fage» */}
          {item.product_brand && (
            <>
              {" "}
              <span className="text-sm text-ink-faint">{item.product_brand}</span>
            </>
          )}
        </div>
        {/* una X, non più un link testuale. Il nome accessibile resta una frase
            intera e nomina la voce: è anche il nome con cui si comanda a voce
            questo bersaglio, e «Togli dalla dispensa» su trenta righe è ambiguo */}
        <button
          type="button"
          disabled={busy}
          onClick={onRemove}
          aria-label={`Togli ${itemLabel(item)} dalla dispensa`}
          className="-mt-1 -mr-1 flex size-11 shrink-0 items-center justify-center rounded-full text-danger disabled:opacity-40"
        >
          <svg
            viewBox="0 0 24 24"
            aria-hidden="true"
            className="size-5"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          >
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </div>
      <FillSlider
        value={item.fill_percent ?? fillForStatus(item.status)}
        label={itemLabel(item)}
        disabled={busy}
        onCommit={fill}
      />
      {/* la verità sullo stato la dice il server, e questa pastiglia è l'unica cosa
          nella riga a dirla: il cursore, da solo, è un'indicazione a occhio */}
      <StatusChip status={item.status} />
      {failed && <Alert>Non sono riuscito a salvare la modifica. Riprova.</Alert>}

      {asking && (
        <div className="flex items-center justify-between gap-2 rounded-card bg-page px-3 py-2">
          <span className="text-sm text-ink-soft">Lo rimetto in lista?</span>
          <span className="flex shrink-0 gap-1">
            <button
              type="button"
              disabled={busy}
              onClick={askRestock}
              className="min-h-11 rounded-full px-3 text-sm font-medium text-brand disabled:opacity-40"
            >
              Sì
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => setAsking(false)}
              className="min-h-11 rounded-full px-3 text-sm font-medium text-ink-soft disabled:opacity-40"
            >
              No
            </button>
          </span>
        </div>
      )}

      {restockFailed && <Alert>Non sono riuscito a rimettere la voce in lista. Riprova.</Alert>}

      {restocked && (
        <p role="status" className="text-sm text-ink-soft">
          {restocked.added ? "Rimesso in lista." : "Era già in lista."}
        </p>
      )}
    </li>
  );
}
