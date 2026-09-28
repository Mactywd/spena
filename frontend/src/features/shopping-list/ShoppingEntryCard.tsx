import { SectionEntryCard } from "../../components/ui/SectionEntryCard";
import { entryNote } from "./listView";
import type { ShoppingItem } from "../../domain/types";

/** L'ingresso a «Sistema la spesa», in cima a Lista e a Dispensa. Uno solo per i due
 * schermi: il giro l'ha trovato uguale nei due posti e da tenere così, e due copie della
 * stessa scheda si scollano da sole. Riceve la lista già chiesta dallo schermo — la
 * chiave `["shopping-list"]` è una sola, e la cache anche.
 *
 * `failed` vince sui dati: dopo un aggiornamento fallito React Query tiene quelli
 * vecchi, e contarli direbbe un carrello che forse non c'è più. */
export function ShoppingEntryCard({
  items,
  failed,
}: {
  items: ShoppingItem[] | undefined;
  failed: boolean;
}) {
  const inCart =
    failed || items === undefined ? null : items.filter((item) => item.status === "checked").length;
  return (
    <SectionEntryCard
      to="/sistema"
      title="Sistema la spesa"
      note={entryNote(inCart)}
      pending={inCart !== null && inCart > 0}
    />
  );
}
