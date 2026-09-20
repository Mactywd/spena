import { buttonClasses } from "../../components/ui/buttonClasses";

/** Per quante porzioni si vuole la ricetta.
 *
 * I due tasti portano la loro altezza da bersaglio da `buttonClasses` (min-h-11):
 * questo si tocca in cucina, con le mani occupate, e una freccia stretta si sbaglia.
 */
export function ServingsStepper({
  value,
  onChange,
}: {
  value: number;
  onChange: (next: number) => void;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-ink-soft">Per</span>
      <button
        type="button"
        aria-label="Una porzione in meno"
        disabled={value <= 1}
        onClick={() => onChange(value - 1)}
        className={`${buttonClasses("secondary")} w-11`}
      >
        −
      </button>
      <span className="min-w-8 text-center font-medium" aria-live="polite">
        {value}
      </span>
      <button
        type="button"
        aria-label="Una porzione in più"
        disabled={value >= 50}
        onClick={() => onChange(value + 1)}
        className={`${buttonClasses("secondary")} w-11`}
      >
        +
      </button>
      <span className="text-sm text-ink-soft">{value === 1 ? "porzione" : "porzioni"}</span>
    </div>
  );
}
