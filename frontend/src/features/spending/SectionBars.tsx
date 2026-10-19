import { Card } from "../../components/ui/Card";
import { formatShare, formatUsd } from "./format";
import type { SectionSpend } from "./types";

/** «Per sezione» (H1): una riga per sezione, nell'ordine del server (dalla più cara), col
 * costo, la quota e una barra lunga quanto la quota.
 *
 * Un colore solo, `brand`: le sezioni si riconoscono dal nome scritto accanto, non da una
 * tinta — sei tinte su 375 px sarebbero una legenda da imparare. La traccia è
 * `brand-tint`: `brand` sta sopra 4,5:1 su di lei e sul bianco della scheda
 * (theme.test.ts), più del 3:1 che serve a un segno. SVG scritto a mano, come ogni grafico
 * dell'app: nessuna libreria. Il disegno è `aria-hidden`: il costo e la quota sono già
 * scritti nella riga. Una quota minuscola ha comunque un'unità su cento, perché accanto a
 * un «< 1%» una barra assente direbbe zero. */
export function SectionBars({ sections }: { sections: SectionSpend[] }) {
  return (
    <Card pad={false}>
      <ul aria-label="Spesa per sezione" className="divide-y divide-line">
        {sections.map((section) => (
          <li key={section.call_site} className="px-3 py-2.5">
            <div className="flex items-baseline gap-3">
              <span className="min-w-0 font-medium break-words">{section.label}</span>
              <span className="ml-auto shrink-0 text-sm text-ink-soft tabular-nums">
                {formatUsd(section.cost_usd)} · {formatShare(section.share)}
              </span>
            </div>
            <svg
              aria-hidden="true"
              viewBox="0 0 100 8"
              preserveAspectRatio="none"
              className="mt-1.5 block h-2 w-full"
            >
              <rect width="100" height="8" className="fill-brand-tint" />
              {section.share > 0 && (
                <rect
                  data-bar=""
                  width={Math.max(section.share * 100, 1)}
                  height="8"
                  className="fill-brand"
                />
              )}
            </svg>
          </li>
        ))}
      </ul>
    </Card>
  );
}
