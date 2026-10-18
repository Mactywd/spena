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
        icon={IconMinus}
        label="Una porzione in meno"
        disabled={below === null || below < MIN}
        onClick={() => {
          if (below !== null) onChange(below);
        }}
      />
      <span className="min-w-8 text-center font-medium" aria-live="polite">
        {approx !== null ? approxText(approx) : (value ?? "—")}
      </span>
      <Button
        icon={IconPlus}
        label="Una porzione in più"
        disabled={above !== null && above > MAX}
        unavailableReason={unknown ? SERVINGS_UNKNOWN : undefined}
        onClick={() => {
          if (above !== null) onChange(above);
        }}
      />
    </div>
  );
}
