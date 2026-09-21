import { buttonClasses } from "../../components/ui/buttonClasses";

/** I gradini della scala, nell'ordine in cui si leggono.
 *
 * `null` è «Tutte»: non una soglia altissima ma l'assenza di soglia, e il server le
 * distingue — una soglia qualunque gli fa guardare tutto il ricettario invece dei
 * cento più recenti. Oltre i tre mancanti un filtro sui mancanti non filtra più
 * niente, ed è per questo che la scala finisce lì.
 */
const BUDGET_STEPS: { value: number | null; pill: string; caption: string }[] = [
  { value: null, pill: "Tutte", caption: "Tutto il ricettario." },
  { value: 0, pill: "Ora", caption: "Solo quelle che puoi cucinare adesso." },
  { value: 1, pill: "+1", caption: "Al massimo 1 ingrediente da comprare." },
  { value: 2, pill: "+2", caption: "Al massimo 2 ingredienti da comprare." },
  { value: 3, pill: "+3", caption: "Al massimo 3 ingredienti da comprare." },
];

/** L'ultimo gradino della scala.
 *
 * Lo schermo lo chiede per non dire «alza la soglia» a chi è già in cima: un
 * consiglio impossibile non è un vicolo cieco, ma è la prima frase che si legge
 * quando lo schermo è vuoto, ed è la peggiore da sprecare.
 */
export const MAX_BUDGET = BUDGET_STEPS[BUDGET_STEPS.length - 1].value ?? 0;

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
