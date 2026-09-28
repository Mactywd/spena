import { useRef, type KeyboardEvent } from "react";
import { STATUS_LABELS } from "../../features/pantry/statusLabels";
import type { PantryStatus } from "../../domain/types";

// Da sinistra a destra, dal meno al più. Il livello arriva fino alla tacca toccata
// (spec T3 §4.4): si tocca dove si vuole che arrivi.
const ORDER: PantryStatus[] = ["finished", "low", "available"];
const LIT: Record<PantryStatus, string> = {
  finished: "bg-finished",
  low: "bg-low",
  available: "bg-brand",
};

/** Le tre tacche: quanto resta di una voce, e il controllo che lo cambia (spec T3
 * §4.4, al posto del cursore). Sono tre pulsanti e non un `range`: un tocco che
 * diventa uno scorrimento il browser non lo trasforma in un clic, quindi scorrere
 * partendo da qui non cambia mai uno stato — il difetto di S13 non ha dove nascere.
 * Ogni tacca è un bersaglio da 44px; il disegno è una barretta. */
export function StockGauge({
  status,
  onChange,
  itemName,
  disabled = false,
}: {
  status: PantryStatus;
  onChange: (status: PantryStatus) => void;
  itemName: string;
  disabled?: boolean;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const level = ORDER.indexOf(status);

  function choose(next: PantryStatus) {
    if (next !== status) onChange(next);
  }

  function onKeyDown(event: KeyboardEvent) {
    const step = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1 }[event.key];
    if (step === undefined) return;
    event.preventDefault();
    const index = Math.min(ORDER.length - 1, Math.max(0, level + step));
    choose(ORDER[index]);
    refs.current[index]?.focus();
  }

  return (
    <div role="radiogroup" aria-label={`Quanto resta di ${itemName}`} className="flex shrink-0">
      {ORDER.map((option, index) => {
        const lit = index <= level;
        return (
          <button
            key={option}
            ref={(el) => {
              refs.current[index] = el;
            }}
            type="button"
            role="radio"
            aria-checked={option === status}
            aria-label={STATUS_LABELS[option]}
            tabIndex={option === status ? 0 : -1}
            disabled={disabled}
            data-lit={lit}
            onClick={() => choose(option)}
            onKeyDown={onKeyDown}
            className="flex size-11 items-center justify-center disabled:opacity-40"
          >
            <span className={`h-1.5 w-4 rounded-full ${lit ? LIT[status] : "bg-notch-off"}`} />
          </button>
        );
      })}
    </div>
  );
}
