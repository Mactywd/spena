import { Button } from "../../components/ui/Button";
import { IconMinus, IconPlus } from "../../components/ui/icons";

// Il perché dello stepper fermo. Sta sul «+» soltanto: `Button` disegna il motivo sotto
// di sé, e con due pulsanti la stessa frase comparirebbe due volte in una riga.
const SERVINGS_UNKNOWN = "Porzioni non indicate: si cambiano da «Modifica».";

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
  return (
    // `[&>p]:basis-full`: il motivo del «+» (un `<p>` fratello del `<button>`, disegnato
    // da `Button`) è un figlio diretto di questa riga `flex flex-wrap`; senza questa
    // classe finirebbe a fianco dello stepper invece che a capo, sotto di lui (R-2).
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 [&>p]:basis-full">
      <span className="text-sm text-ink-soft">Porzioni</span>
      <Button
        icon={IconMinus}
        label="Una porzione in meno"
        disabled={value === null || value <= 1}
        onClick={() => {
          if (value !== null) onChange(value - 1);
        }}
      />
      <span className="min-w-8 text-center font-medium" aria-live="polite">
        {value ?? "—"}
      </span>
      <Button
        icon={IconPlus}
        label="Una porzione in più"
        disabled={value !== null && value >= 50}
        unavailableReason={value === null ? SERVINGS_UNKNOWN : undefined}
        onClick={() => {
          if (value !== null) onChange(value + 1);
        }}
      />
    </div>
  );
}
