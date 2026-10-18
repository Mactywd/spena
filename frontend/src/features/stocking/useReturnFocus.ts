import { useEffect, type RefObject } from "react";
import type { FocusTarget } from "./stockingView";

/** Rimette il fuoco al pulsante giusto di una riga che rinasce.
 *
 * La vista cambia forma aprendo e chiudendo un pannello, e la riga rinasce: il pulsante
 * che aveva il fuoco non c'è più. Lo schermo dice dove rimetterlo; `Button` non passa
 * `ref` a chi lo avvolge, quindi lo si cerca per l'attributo dello span che lo avvolge
 * (`data-trigger` nella riga di una voce, `data-package-trigger` in quella di una
 * confezione: la seconda sta dentro la prima, e i due non devono trovarsi a vicenda).
 * Solo se il fuoco è caduto sulla pagina: è sempre così quando il pulsante che lo aveva
 * è sparito, e una richiesta arrivata in ritardo (la rilettura dopo un abbinamento) non
 * lo toglie a chi è già andato altrove. */
export function useReturnFocus(
  container: RefObject<HTMLElement | null>,
  target: FocusTarget | null,
  onDone: () => void,
  attribute = "data-trigger"
) {
  useEffect(() => {
    if (!target || !container.current) return;
    const lost = document.activeElement === null || document.activeElement === document.body;
    if (lost) {
      container.current.querySelector<HTMLElement>(`[${attribute}="${target}"] button`)?.focus();
    }
    onDone();
  }, [container, target, onDone, attribute]);
}
