import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { IconX } from "../../components/ui/icons";
import type { ShoppingItem } from "../../domain/types";

// Parziale e tipizzato sull'unione: "manual" non ha nota perché non c'è niente da
// spiegare, e il giorno in cui il backend aggiunge un motivo il compilatore lo dice.
const REASON_HINT: Partial<Record<ShoppingItem["reason"], string>> = {
  finished_while_cooking: "rientrata perché finita cucinando",
  low_while_cooking: "rientrata perché quasi finita cucinando",
};

/** Una voce della lista (spec T3 §4.2): la casella con il testo scritto, la nota del
 * rientro se c'è, e la ✕ a destra. Senza linee fra le righe: le separa la sezione. */
export function ListRow({
  item,
  busy,
  failed,
  onToggle,
  onRemove,
}: {
  item: ShoppingItem;
  busy: boolean;
  failed: boolean;
  onToggle: () => void;
  onRemove: () => void;
}) {
  const checked = item.status === "checked";
  const hint = REASON_HINT[item.reason];
  return (
    <li>
      <div className="flex items-center gap-1">
        {/* S17: in corsia spuntare è il gesto che si fa di più, e il pollice tocca la
            parola, non il quadratino accanto. La label prende casella, nome e nota, ed è
            alta almeno 44px. L'`aria-label` della casella vince sul testo della label: il
            nome accessibile è l'ingrediente abbinato, non «Total 0% rientrata perché…».
            La ✕ sta fuori, bersaglio suo: dentro, un tocco per togliere spunterebbe anche */}
        <label className="flex min-h-11 min-w-0 flex-1 items-center gap-3 py-1.5">
          <input
            type="checkbox"
            aria-label={item.ingredient_name ?? item.raw_text}
            checked={checked}
            // `aria-disabled` e non `disabled`, come le tacche della dispensa: il browser
            // toglie il fuoco a un controllo che diventa `disabled`, e chi spunta con la
            // tastiera lo ritrovava sul `body` appena partiva la PATCH. La casella resta
            // controllata: ignorato il cambio, React la ridisegna com'era
            aria-disabled={busy || undefined}
            onChange={() => {
              if (!busy) onToggle();
            }}
            className="size-5 shrink-0 accent-brand aria-disabled:opacity-40"
          />
          {/* S16: `min-w-0` lascia stringere la colonna sotto la sua parola più lunga, e
              `break-words` spezza un nome che non ci sta: a 375px la riga spingeva la
              pagina di lato */}
          <span className="flex min-w-0 flex-1 flex-col break-words">
            <span className={checked ? "text-ink-faint line-through" : ""}>{item.raw_text}</span>
            {/* visibile, non un tooltip: da telefono non esiste il passaggio del mouse,
                e il motivo per cui una voce è rientrata va letto */}
            {hint && <span className="text-xs text-low">{hint}</span>}
          </span>
        </label>
        {/* `busy` come la casella: con `disabled` il browser toglieva il fuoco alla ✕
            appena partiva la PATCH, e dopo una ✕ fallita lo si ritrovava sulla pagina */}
        <Button
          variant="ghost"
          icon={IconX}
          label={`Togli ${item.raw_text} dalla lista`}
          onClick={onRemove}
          busy={busy}
        />
      </div>
      {failed && (
        <Alert className="pb-2">
          Non sono riuscito a salvare la modifica. La voce è ancora qui: riprova.
        </Alert>
      )}
    </li>
  );
}
