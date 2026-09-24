import { COST_STEPS, costLabel } from "../../domain/cost";

/** Il costo di una ricetta, da scegliere: gli stessi cinque € di `CostMeter`, come
 * bottoni. Si tocca il terzo e la ricetta è da tre; si ritocca quello scelto e il
 * costo torna non indicato — l'unico modo di dire «non lo so» dopo averlo detto. */
export function CostPicker({
  value,
  onChange,
  disabled = false,
}: {
  value: number | null;
  onChange: (cost: number | null) => void;
  disabled?: boolean;
}) {
  return (
    <div role="group" aria-label="Costo" className="flex">
      {COST_STEPS.map((step) => (
        <button
          key={step}
          type="button"
          aria-label={costLabel(step)}
          aria-pressed={step === value}
          data-cost-step={step}
          data-on={value !== null && step <= value}
          disabled={disabled}
          onClick={() => onChange(step === value ? null : step)}
          // bersaglio da pollice, 44px, anche se il segno è piccolo
          className={`min-h-11 min-w-11 text-xl font-semibold disabled:opacity-60 ${
            value !== null && step <= value ? "text-ink" : "text-ink-ghost"
          }`}
        >
          €
        </button>
      ))}
    </div>
  );
}
