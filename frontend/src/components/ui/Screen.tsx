import type { ReactNode } from "react";
import { BackLink } from "../BackLink";

// L'intestazione di ogni schermata, in un posto solo. Quindici schermate che ripetono
// la stessa minestra di classi divergono da sole: basta un `pt-5` diventato `pt-4` e
// il titolo salta passando da una scheda all'altra.
export function Screen({
  title,
  subtitle,
  action,
  back,
  children,
}: {
  title: string;
  subtitle?: ReactNode;
  /** un bottone o un link in alto a destra, all'altezza del titolo */
  action?: ReactNode;
  /** dove si torna, per le sottosezioni. Le sezioni primarie non lo passano: da
   * loro non si torna, ci si sposta con la barra in basso. */
  back?: { to: string; label: string };
  children: ReactNode;
}) {
  return (
    // con il ritorno lo spazio sopra è già occupato dal collegamento, che porta la
    // sua altezza da bersaglio: `pt-5` in più staccherebbe il titolo dal resto
    <div className={`px-4 pb-4 ${back ? "pt-2" : "pt-5"}`}>
      {back && <BackLink to={back.to} label={back.label} />}
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
