import { useRef, type RefObject } from "react";
import { Button } from "../../components/ui/Button";
import { IconMinus, IconPlus } from "../../components/ui/icons";

// Il perché dello stepper fermo. Sta sul «+» soltanto: `Button` disegna il motivo sotto
// di sé, e con due pulsanti la stessa frase comparirebbe due volte in una riga.
const SERVINGS_UNKNOWN = "Porzioni non indicate: si cambiano da «Modifica».";

// la scala delle porzioni, la stessa del backend (`Query(ge=1, le=50)`)
const MIN = 1;
const MAX = 50;

/** «≈ 1,5»: le porzioni che fa una dose fissata, col numero già arrotondato dal server.
 * Qui si mette solo la virgola. */
function approxText(approx: number): string {
  return `≈ ${approx.toLocaleString("it-IT", { maximumFractionDigits: 2 })}`;
}

/** Per quante porzioni si vuole la ricetta.
 *
 * Si vede sempre (spec T3 §4.6): senza porzioni dichiarate non c'è una base da cui
 * riscalare, e invece di sparire — dal giro, «senza porzioni lo stepper sparisce senza
 * dirlo» — lo dice. Il «−» a porzioni ignote è spento come ai bordi: non c'è niente da
 * togliere. I due tasti sono bersagli da 44 px (`Button` di sola icona): questo si tocca
 * in cucina, con le mani occupate.
 *
 * Con una dose fissata su una riga (R2, secondo modo) `approx` porta le porzioni che quella
 * dose fa, e lo stepper le dice al posto del numero: «≈ 1,5». Toccarlo torna alle porzioni
 * intere (un modo alla volta, Mattia): − all'intero più grande sotto, + al più piccolo
 * sopra — da ≈ 1,5 a 1 e a 2, da ≈ 2 a 1 e a 3 —, dentro 1–50. */
export function ServingsStepper({
  value,
  approx = null,
  onChange,
}: {
  value: number | null;
  approx?: number | null;
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

  const below =
    approx !== null ? Math.min(Math.ceil(approx) - 1, MAX) : value !== null ? value - 1 : null;
  const above =
    approx !== null ? Math.max(Math.floor(approx) + 1, MIN) : value !== null ? value + 1 : null;
  const unknown = value === null && approx === null;

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
        disabled={below === null || below < MIN}
        onClick={() => {
          if (below !== null) step(below, minusRef, plusRef);
        }}
      />
      <span className="min-w-8 text-center font-medium" aria-live="polite">
        {approx !== null ? approxText(approx) : (value ?? "—")}
      </span>
      <Button
        ref={plusRef}
        icon={IconPlus}
        label="Una porzione in più"
        disabled={above !== null && above > MAX}
        unavailableReason={unknown ? SERVINGS_UNKNOWN : undefined}
        onClick={() => {
          if (above !== null) step(above, plusRef, minusRef);
        }}
      />
    </div>
  );
}
