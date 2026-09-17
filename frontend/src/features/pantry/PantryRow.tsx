import { StatusToggle } from "./StatusToggle";
import { Alert } from "../../components/ui/Alert";
import type { PantryItem, PantryStatus } from "../../domain/types";

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
 * il messaggio compare dentro la lapide (non ha più senso accanto a `StatusToggle`,
 * che qui non c'è), e la lapide non scade da sola — solo un altro annulla, riuscito
 * stavolta, la può togliere.
 */
export function PantryRow({
  item,
  busy,
  removed,
  failed,
  onStatus,
  onRemove,
  onUndo,
}: {
  item: PantryItem;
  busy: boolean;
  removed: boolean;
  failed: boolean;
  onStatus: (status: PantryStatus) => void;
  onRemove: () => void;
  onUndo: () => void;
}) {
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
      <StatusToggle value={item.status} disabled={busy} onChange={onStatus} />
      {failed && <Alert>Non sono riuscito a salvare la modifica. Riprova.</Alert>}
    </li>
  );
}
