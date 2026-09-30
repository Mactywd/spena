import { useId, type ReactNode } from "react";
import { departmentStyle, TINT_CLASSES } from "./departments";
import { capitalizeFirst } from "../../lib/text";

/** Un reparto: la scheda bianca con il quadratino colorato, il nome e il conteggio
 * (spec T3 §2, presa dalla direzione «Vivace»). Dentro, le righe non hanno linee fra
 * loro — deciso da Mattia: lo spazio basta a separarle, e la sezione resta un blocco
 * solo. Chi la usa passa righe che portano il proprio spazio verticale. */
export function Section({
  category,
  title,
  count,
  children,
}: {
  category: string | null;
  title?: string;
  count?: number;
  children: ReactNode;
}) {
  const headingId = useId();
  const { icon: Icon, tint } = departmentStyle(category);
  const name = title ?? (category ? capitalizeFirst(category) : "Senza reparto");
  return (
    <section aria-labelledby={headingId} className="overflow-hidden rounded-2xl bg-card">
      <div className="flex items-center gap-2.5 px-3 pt-3 pb-1.5">
        <span
          data-dept-badge
          aria-hidden="true"
          className={`flex size-7 shrink-0 items-center justify-center rounded-lg ${TINT_CLASSES[tint]}`}
        >
          <Icon className="size-4" stroke={1.8} />
        </span>
        <h2 id={headingId} className="flex-1 text-sm font-semibold">
          {name}
        </h2>
        {count !== undefined && <span className="text-xs text-ink-faint">{count}</span>}
      </div>
      <div className="px-3 pb-2">{children}</div>
    </section>
  );
}
