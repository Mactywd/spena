import { COST_STEPS, costLabel } from "../../domain/cost";

/** Il costo di una ricetta, da leggere: cinque €, pieni fino al gradino (R9).
 *
 * Il grigio da solo non dice niente a uno screen reader, quindi il gradino sta anche
 * nell'etichetta. Senza costo non si disegna niente: cinque € tutti grigi direbbero
 * «meno di uno», e una ricetta senza costo non è una ricetta economica. */
export function CostMeter({ cost }: { cost: number | null }) {
  if (cost === null) return null;
  return (
    <span role="img" aria-label={costLabel(cost)} className="inline-flex text-xs font-semibold">
      {COST_STEPS.map((step) => (
        <span
          key={step}
          aria-hidden="true"
          data-cost-step={step}
          data-on={step <= cost}
          className={step <= cost ? "text-ink" : "text-ink-ghost"}
        >
          €
        </span>
      ))}
    </span>
  );
}
