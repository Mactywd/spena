import { Button } from "./Button";
import { IconAlertCircle, IconRefresh } from "./icons";

/** L'errore di caricamento, uno per tutta l'app (spec T3 §3.5: il giro ne ha contate
 * cinque forme, due senza un modo di riprovare). Dice cosa non è andato — chi lo usa
 * scrive anche se il dato è ancora lì — e offre sempre «Riprova»: «riprova più tardi»
 * senza un pulsante chiede di ricaricare a mano, ed è un vicolo cieco. */
export function ErrorState({
  message,
  onRetry,
  retrying = false,
}: {
  message: string;
  onRetry: () => void;
  retrying?: boolean;
}) {
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-2xl bg-card p-4">
      <p className="flex items-start gap-2 text-sm text-danger">
        <IconAlertCircle aria-hidden="true" className="mt-0.5 size-5 shrink-0" stroke={1.8} />
        {message}
      </p>
      {/* `busy` e non `disabled`: chi ha premuto «Riprova» da tastiera tiene il fuoco */}
      <Button icon={IconRefresh} onClick={onRetry} busy={retrying}>
        {retrying ? "Riprovo…" : "Riprova"}
      </Button>
    </div>
  );
}
