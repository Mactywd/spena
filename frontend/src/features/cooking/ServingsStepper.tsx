import { useRef, type RefObject } from "react";
import { Button } from "../../components/ui/Button";
import { IconMinus, IconPlus } from "../../components/ui/icons";

// Il perché dello stepper fermo. Sta sul «+» soltanto: `Button` disegna il motivo sotto
// di sé, e con due pulsanti la stessa frase comparirebbe due volte in una riga.
const SERVINGS_UNKNOWN = "Porzioni non indicate: si cambiano da «Modifica».";

// la scala delle porzioni, la stessa del backend (`Query(ge=1, le=50)`)
const MIN = 1;
const MAX = 50;

/** Per quante porzioni si vuole la ricetta.
 *
 * Si vede sempre (spec T3 §4.6): senza porzioni dichiarate non c'è una base da cui
 * riscalare, e invece di sparire — dal giro, «senza porzioni lo stepper sparisce senza
 * dirlo» — lo dice. Il «−» a porzioni ignote è spento come ai bordi: non c'è niente da
 * togliere. I due tasti sono bersagli da 44 px (`Button` di sola icona): questo si tocca
 * in cucina, con le mani occupate. */
export function ServingsStepper({
  value,
  onChange,
}: {
  value: number | null;
  onChange: (next: number) => void;
}) {
  const minusRef = useRef<HTMLButtonElement>(null);
  const plusRef = useRef<HTMLButtonElement>(null);

  // Al bordo il tasto premuto si spegne con `disabled` (è fermo: non c'è un perché da
  // dire), e il browser toglie il fuoco a un pulsante che diventa `disabled` — chi usa la
  // tastiera lo ritrovava sul `body` (T3 Consegna 5). Prima che succeda, se il fuoco era
  // sul tasto premuto, passa all'altro, che a quel punto è acceso. Così niente frase in
  // più sotto lo stepper (pulizie del 2026-10-13).
  function step(
    next: number,
    pressed: RefObject<HTMLButtonElement | null>,
    other: RefObject<HTMLButtonElement | null>
  ) {
    if ((next <= MIN || next >= MAX) && document.activeElement === pressed.current) {
      other.current?.focus();
    }
    onChange(next);
  }

  return (
    // `[&>p]:basis-full`: il motivo del «+» (un `<p>` fratello del `<button>`, disegnato
    // da `Button`) è un figlio diretto di questa riga `flex flex-wrap`; senza questa
    // classe finirebbe a fianco dello stepper invece che a capo, sotto di lui (R-2).
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 [&>p]:basis-full">
      <span className="text-sm text-ink-soft">Porzioni</span>
      <Button
        ref={minusRef}
        icon={IconMinus}
        label="Una porzione in meno"
        disabled={value === null || value <= MIN}
        onClick={() => {
          if (value !== null) step(value - 1, minusRef, plusRef);
        }}
      />
      <span className="min-w-8 text-center font-medium" aria-live="polite">
        {value ?? "—"}
      </span>
      <Button
        ref={plusRef}
        icon={IconPlus}
        label="Una porzione in più"
        disabled={value !== null && value >= MAX}
        unavailableReason={value === null ? SERVINGS_UNKNOWN : undefined}
        onClick={() => {
          if (value !== null) step(value + 1, plusRef, minusRef);
        }}
      />
    </div>
  );
}
