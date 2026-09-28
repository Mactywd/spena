import { createContext, useContext } from "react";

export type NoticeInput = { text: string; action?: { label: string; onClick: () => void } };

/** Quanto resta a video un avviso. Sei secondi, come la lapide di prima: abbastanza
 * per leggere e toccare «Annulla» con una mano sola. */
export const NOTICE_MS = 6000;

// Il contesto e il suo gancio stanno in un file senza componenti: accanto a
// NoticeProvider romperebbero il fast refresh (la stessa regola di statusLabels.ts).
export const NoticeContext = createContext<(notice: NoticeInput) => void>(() => {});

/** Mostra un avviso di conferma: in basso, sopra la barra delle schede, lo stesso in
 * tutta l'app (spec T3 §3.5, il resto di T4). */
export function useNotice(): (notice: NoticeInput) => void {
  return useContext(NoticeContext);
}
