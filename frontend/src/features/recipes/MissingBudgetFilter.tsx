import { buttonClasses } from "../../components/ui/buttonClasses";
import { BUDGET_STEPS } from "./missingBudget";

export function MissingBudgetFilter({
  value,
  onChange,
}: {
  value: number | null;
  onChange: (value: number | null) => void;
}) {
  const scelto = BUDGET_STEPS.find((step) => step.value === value) ?? BUDGET_STEPS[0];
  return (
    <fieldset>
      {/* cinque radio senza gruppo, letti a voce, sono cinque scelte senza domanda */}
      <legend className="sr-only">Quanto posso comprare</legend>
      <div className="flex flex-wrap gap-2">
        {BUDGET_STEPS.map((step) => {
          const checked = step.value === value;
          return (
            <label key={step.pill}>
              {/* Un radio vero, nascosto. La selezione singola e la navigazione da
                  tastiera sono del browser invece che nostre, e il test lo trova come
                  radio senza sapere niente di come è disegnato. Il nome accessibile è
                  la frase intera: «+2» letto a voce non è una scelta. */}
              <input
                type="radio"
                name="missing-budget"
                className="peer sr-only"
                checked={checked}
                onChange={() => onChange(step.value)}
                aria-label={step.caption}
              />
              <span
                className={`${buttonClasses(checked ? "primary" : "secondary", "pill")} peer-focus-visible:ring-2 peer-focus-visible:ring-brand peer-focus-visible:ring-offset-2`}
              >
                {step.pill}
              </span>
            </label>
          );
        })}
      </div>
      <p className="pt-1.5 pb-2 text-xs text-ink-faint">{scelto.caption}</p>
    </fieldset>
  );
}
