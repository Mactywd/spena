import { Button } from "../../components/ui/Button";
import { IconListCheck, IconShoppingCartPlus } from "../../components/ui/icons";
import { STATUS_LABELS, offersRestock, type RestockStatus } from "./statusLabels";
import type { PantryStatus } from "../../domain/types";

// La parola dello stato nel suo colore, come le tacche accese: rosso per finito, ambra
// per quasi finito. `text-finished` e `text-low` su `card` sono già misurati in
// `theme.test.ts`, e il tema scuro li ridefinisce.
const WORD_TONE: Record<RestockStatus, string> = {
  low: "text-low",
  finished: "text-finished",
};

/** La riga del rientro in lista, sotto una voce gialla o rossa della Dispensa: la parola
 * dello stato e, a destra, «In lista» — o «Già in lista» se l'ingrediente ha già una voce
 * aperta in lista (dal giro di T3: «la domanda del rientro compare anche per ciò che è
 * già in lista»). Su una voce disponibile non disegna niente.
 *
 * Era dentro `PantryRow`, per il solo rosso; dal 2026-10-09 vale anche per il giallo
 * (Mattia: «anche quasi finito, ovunque») ed è uscita in un file suo, il taglio che la
 * nota di Parte X su `PantryRow.tsx` indicava. Sta sotto la scadenza, a tutta larghezza,
 * e non sulla riga della scadenza: lì un pulsante stringerebbe il campo data quando è
 * aperto. Il tocco non cambia lo stato della voce: la rotta del rientro scrive solo in
 * lista. */
export function RestockLine({
  status,
  listed,
  busy,
  onRestock,
}: {
  status: PantryStatus;
  listed: boolean;
  busy: boolean;
  onRestock: () => void;
}) {
  if (!offersRestock(status)) return null;
  return (
    // «Lo rimetto in lista? Sì / No» aveva bersagli da 35px e non tornava più se
    // ignorato: è un pulsante che resta finché serve, e ignorarlo è il «No»
    <div className="flex items-center justify-between gap-2 pb-2">
      <span className={`text-sm font-medium ${WORD_TONE[status]}`}>{STATUS_LABELS[status]}</span>
      {listed ? (
        <span className="flex items-center gap-1 text-sm text-ink-soft">
          <IconListCheck aria-hidden="true" className="size-4" stroke={1.8} />
          Già in lista
        </span>
      ) : (
        <Button icon={IconShoppingCartPlus} onClick={onRestock} busy={busy}>
          In lista
        </Button>
      )}
    </div>
  );
}
