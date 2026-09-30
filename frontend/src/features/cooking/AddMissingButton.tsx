import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "../../components/ui/Button";
import { IconShoppingCartPlus } from "../../components/ui/icons";
import { useNotice } from "../../components/ui/noticeContext";
import { missingNotice, sendMissing } from "./missingToList";
import type { RecipeIngredientLine } from "../../domain/types";

/** «Metti in lista ciò che manca» (spec T3 §4.6): la freccia ricetta → lista, che prima
 * esisteva solo dopo aver cucinato. Riceve le righe già filtrate su `satisfied`, che
 * decide il server: questo pulsante non sa quale riga basti e quale no.
 *
 * Non una `useMutation`, come l'«Annulla» della dispensa (`undoRemove` in
 * `PantryScreen.tsx`): il «Riprova» vive nell'avviso, che è dell'app e non di questo
 * schermo, e si può toccare anche dopo aver lasciato la ricetta. `busy` e non
 * `disabled` mentre è in volo: il pulsante tiene il fuoco (regola del Piano 1). */
export function AddMissingButton({ lines }: { lines: RecipeIngredientLine[] }) {
  const notice = useNotice();
  const queryClient = useQueryClient();
  const [pending, setPending] = useState(false);

  function send(toSend: RecipeIngredientLine[]) {
    setPending(true);
    void sendMissing(toSend)
      .then((outcome) => {
        // la lista è cambiata anche se una riga non è arrivata: si rilegge comunque
        void queryClient.invalidateQueries({ queryKey: ["shopping-list"] });
        notice({
          text: missingNotice(outcome),
          action:
            outcome.failed.length > 0
              ? { label: "Riprova", onClick: () => send(outcome.failed) }
              : undefined,
        });
      })
      .finally(() => setPending(false));
  }

  if (lines.length === 0) return null;
  return (
    <Button
      variant="secondary"
      shape="block"
      icon={IconShoppingCartPlus}
      busy={pending}
      onClick={() => send(lines)}
    >
      Metti in lista ciò che manca
    </Button>
  );
}
