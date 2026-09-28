import type { ReactNode } from "react";

/** La pastiglia: la forma una volta, il colore (sfondo e testo) da chi la usa. Dal T3
 * Consegna 1 la dispensa non ne mostra più — lo stato sta nelle tacche di
 * StockGauge, la scadenza nel testo della riga — e al 2026-09-28 nessuno schermo la
 * importa. */
export function Chip({ tone, children }: { tone: string; children: ReactNode }) {
  return <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-medium ${tone}`}>{children}</span>;
}
