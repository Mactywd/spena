import type { ReactNode } from "react";

/** Più pulsanti in gruppo: la metà «solo icone» della regola (spec T3 §2). Il gruppo
 * ha un nome suo, così chi usa uno screen reader sa di che cosa sono le icone prima
 * di sentirle una per una. */
export function IconToolbar({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div role="toolbar" aria-label={label} className="flex items-center gap-1">
      {children}
    </div>
  );
}
