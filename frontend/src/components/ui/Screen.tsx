import type { ReactNode } from "react";

// L'intestazione di ogni schermata, in un posto solo. Quindici schermate che ripetono
// la stessa minestra di classi divergono da sole: basta un `pt-5` diventato `pt-4` e
// il titolo salta passando da una scheda all'altra.
export function Screen({
  title,
  subtitle,
  action,
  children,
}: {
  title: string;
  subtitle?: ReactNode;
  /** un bottone o un link in alto a destra, all'altezza del titolo */
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="px-4 pt-5 pb-4">
      <div className="flex items-start justify-between gap-3 pb-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          {subtitle && <p className="pt-0.5 text-sm text-ink-soft">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}
