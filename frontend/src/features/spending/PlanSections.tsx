import { Card } from "../../components/ui/Card";
import { SectionHeading } from "../../components/ui/SectionHeading";
import { callsText, formatTokens } from "./format";
import type { PlanSection } from "./types";

/** «Claude»: le chiamate sul piano di Claude (la chat dei piatti), contate a parte perché
 * non hanno un costo: chiamate e token, e la nota che dice perché non sono nel totale. */
export function PlanSections({ sections }: { sections: PlanSection[] }) {
  return (
    <>
      <SectionHeading>Claude</SectionHeading>
      <Card pad={false}>
        <ul aria-label="Chiamate sul piano di Claude" className="divide-y divide-line">
          {sections.map((section) => (
            <li key={section.call_site} className="px-3 py-2.5">
              <div className="flex items-baseline gap-3">
                <span className="min-w-0 font-medium break-words">{section.label}</span>
                <span className="ml-auto shrink-0 text-sm text-ink-soft tabular-nums">
                  {callsText(section.calls)} · {formatTokens(section.tokens)} token
                </span>
              </div>
              <p className="pt-0.5 text-sm text-ink-soft">{section.note}</p>
            </li>
          ))}
        </ul>
      </Card>
    </>
  );
}
