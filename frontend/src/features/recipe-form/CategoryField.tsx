import { useId, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchCategories } from "../recipes/api";
import { Alert } from "../../components/ui/Alert";
import { buttonClasses } from "../../components/ui/buttonClasses";

/** La categoria della ricetta: una di quelle che il ricettario ha già, o nessuna.
 *
 * Senza testo libero, per non creare «Primi» e «primi» (R10 §6.2): il backend rifiuta
 * comunque un nome che non conosce. Una scelta che si apre, e non una `<select>`: la
 * categoria è il campo che si tocca meno, l'elenco si legge solo quando serve (con il
 * suo «Carico…» e il suo errore), mentre una `<select>` nativa sul telefono apre la sua
 * lista subito, prima che le voci siano arrivate (deviazione 11). La chiave è quella del
 * filtro del ricettario, quindi quasi sempre la risposta è già in cache.
 *
 * «Categoria» è l'etichetta vera del gruppo e dell'elenco (`aria-labelledby`): un
 * `<label>` non sa nominare una coppia bottone-elenco.
 */
export function CategoryField({
  value,
  onChange,
}: {
  value: string | null;
  onChange: (category: string | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const labelId = useId();
  const listId = useId();
  const { data: categories = [], isLoading, isError } = useQuery({
    queryKey: ["recipe-categories"],
    queryFn: fetchCategories,
    enabled: open,
  });

  function choose(category: string | null) {
    onChange(category);
    setOpen(false);
  }

  return (
    <div role="group" aria-labelledby={labelId} className="text-sm">
      <span id={labelId}>Categoria</span>
      <div className="flex min-h-11 items-center justify-between gap-2">
        <span className={value === null ? "text-ink-faint" : ""}>{value ?? "nessuna"}</span>
        <button
          type="button"
          aria-label={open ? "Chiudi la scelta della categoria" : "Cambia la categoria"}
          aria-expanded={open}
          aria-controls={listId}
          onClick={() => setOpen((current) => !current)}
          className={buttonClasses("ghost")}
        >
          {open ? "Chiudi" : "Cambia"}
        </button>
      </div>
      {open && isLoading && <p className="text-ink-soft">Carico le categorie…</p>}
      {/* mai un vicolo cieco: senza elenco la ricetta si salva con la categoria che ha */}
      {open && isError && (
        <Alert tone="note">
          Non riesco a leggere le categorie: la ricetta si salva anche senza, e la scegli dopo.
        </Alert>
      )}
      {open && !isLoading && !isError && (
        <ul
          id={listId}
          role="listbox"
          aria-labelledby={labelId}
          className="divide-y divide-line overflow-hidden rounded-card bg-card"
        >
          {[null, ...categories].map((category) => (
            // `presentation`: dentro un listbox contano solo le opzioni, e un `listitem`
            // in mezzo romperebbe l'albero che uno screen reader si aspetta
            <li key={category ?? ""} role="presentation">
              <button
                type="button"
                role="option"
                aria-selected={category === value}
                onClick={() => choose(category)}
                className="flex min-h-11 w-full items-center px-3 text-left"
              >
                {category ?? "Nessuna"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
