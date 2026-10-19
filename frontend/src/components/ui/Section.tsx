import { useId, type ReactNode } from "react";
import { departmentStyle, TINT_CLASSES } from "./departments";
import { IconChevronDown, IconChevronRight } from "./icons";
import { capitalizeFirst } from "../../lib/text";

/** Un reparto: la scheda bianca con il quadratino colorato, il nome e il conteggio
 * (spec T3 §2, presa dalla direzione «Vivace»). Dentro, le righe non hanno linee fra
 * loro — deciso da Mattia: lo spazio basta a separarle, e la sezione resta un blocco
 * solo. Chi la usa passa righe che portano il proprio spazio verticale.
 *
 * Con `onToggle` il titolo diventa il pulsante che apre e chiude il reparto (spec S15
 * §2): tutto il titolo — quadratino, nome, numero, chevron — dentro l'`h2`, con
 * `aria-expanded` e `aria-controls`, lo schema ARIA dell'accordion. Chiuso, il contenuto
 * ha `hidden`: le sue tacche e le sue ✕ escono anche dall'ordine del Tab. `closedNote` è
 * quel che il titolo chiuso dice oltre al numero; lo scrive chi usa la sezione, perché la
 * sezione non sa cosa sia una voce. Nessuna animazione: a 375 px un'altezza che si apre
 * sposta il resto sotto il dito. Senza `onToggle` è la sezione di sempre: la Lista e
 * Sistema la spesa non si chiudono (spec S15 §7). */
export function Section({
  category,
  title,
  count,
  collapsed = false,
  onToggle,
  closedNote,
  children,
}: {
  category: string | null;
  title?: string;
  count?: number;
  collapsed?: boolean;
  onToggle?: () => void;
  closedNote?: ReactNode;
  children: ReactNode;
}) {
  const headingId = useId();
  const contentId = useId();
  const { icon: Icon, tint } = departmentStyle(category);
  const name = title ?? (category ? capitalizeFirst(category) : "Senza reparto");
  const badge = (
    <span
      data-dept-badge
      aria-hidden="true"
      className={`flex size-7 shrink-0 items-center justify-center rounded-lg ${TINT_CLASSES[tint]}`}
    >
      <Icon className="size-4" stroke={1.8} />
    </span>
  );

  if (onToggle === undefined) {
    return (
      <section aria-labelledby={headingId} className="overflow-hidden rounded-2xl bg-card">
        <div className="flex items-center gap-2.5 px-3 pt-3 pb-1.5">
          {badge}
          <h2 id={headingId} className="flex-1 text-sm font-semibold">
            {name}
          </h2>
          {count !== undefined && <span className="text-xs text-ink-faint">{count}</span>}
        </div>
        <div className="px-3 pb-2">{children}</div>
      </section>
    );
  }

  const Chevron = collapsed ? IconChevronRight : IconChevronDown;
  const note = collapsed && closedNote ? closedNote : null;
  return (
    // la regione si chiama col solo nome del reparto («Latticini»), aperta e chiusa: il
    // pulsante, e con lui l'`h2`, si chiama col titolo intero («Latticini 2 · 1 finito»)
    <section aria-labelledby={headingId} className="overflow-hidden rounded-2xl bg-card">
      <h2 className="text-sm font-semibold">
        <button
          type="button"
          aria-expanded={!collapsed}
          aria-controls={contentId}
          onClick={onToggle}
          // il contorno del fuoco sta dentro: la sezione ha `overflow-hidden`, e quello di
          // base, 2 px fuori, verrebbe tagliato sui tre lati
          className={`flex min-h-11 w-full items-center gap-2.5 px-3 text-left focus-visible:-outline-offset-2 ${
            collapsed ? "py-3" : "pt-3 pb-1.5"
          }`}
        >
          {badge}
          {/* il numero, e chiuso la nota, a destra del nome; quando non ci stanno vanno a
              capo sotto il nome, piccoli (spec S15 §2). Lo spazio fra i due `span` non si
              vede in un contenitore flex, ma tiene separate le parole nel nome accessibile */}
          <span className="flex min-w-0 flex-1 flex-wrap items-baseline justify-between gap-x-2">
            <span id={headingId}>{name}</span>{" "}
            <span className="text-xs font-normal text-ink-faint">
              {count !== undefined && <span>{count}</span>}
              {count !== undefined && note !== null && " · "}
              {note}
            </span>
          </span>
          <Chevron aria-hidden="true" className="size-5 shrink-0 text-ink-faint" stroke={1.8} />
        </button>
      </h2>
      <div id={contentId} hidden={collapsed} className="px-3 pb-2">
        {children}
      </div>
    </section>
  );
}
