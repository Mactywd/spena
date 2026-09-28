import type { ReactNode } from "react";

/** La pastiglia: la forma una volta, il colore da chi la usa (un tono di STATUS_TONE o
 * di EXPIRY_TONE). */
export function Chip({ tone, children }: { tone: string; children: ReactNode }) {
  return <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-medium ${tone}`}>{children}</span>;
}
