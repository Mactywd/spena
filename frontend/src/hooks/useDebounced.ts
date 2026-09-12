import { useEffect, useState } from "react";

/** Ritarda il valore, così una ricerca non parte a ogni tasto premuto.
 *
 * Stava scritto identico in RecipeBookScreen e in AiDraftScreen; il terzo
 * schermo che ne ha avuto bisogno è AddItemField, e tre copie della stessa
 * attesa sono tre posti in cui il ritardo può divergere senza che nessuno lo
 * noti. Il valore dell'attesa resta di chi chiama: qui non c'è un default,
 * perché un default invisibile è il modo in cui tre schermi tornano a
 * comportarsi in tre modi diversi.
 */
export function useDebounced(value: string, ms: number): string {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return settled;
}
