import { useId } from "react";
import type { Ingredient } from "../../domain/types";

// L'elenco dei suggerimenti dell'anagrafica. Ne esistevano due copie identiche — nel
// campo della lista e nel selettore di ingredienti — e due copie della stessa cosa si
// scollano: la prima differenza che compare è sempre la misura del bersaglio.
export function OptionList({
  options,
  onPick,
  disabled = false,
  fieldLabel,
}: {
  options: Ingredient[];
  onPick: (ingredient: Ingredient) => void;
  disabled?: boolean;
  /** L'etichetta del campo che l'elenco completa. ARIA vuole un nome per ogni listbox;
   * il nome non è l'etichetta nuda, perché chi cerca il campo per etichetta (uno
   * screen reader, un test) troverebbe due elementi con lo stesso nome. */
  fieldLabel?: string;
}) {
  const baseId = useId();
  return (
    // un listbox contiene opzioni e basta: niente `<ul>/<li>` in mezzo, che uno screen
    // reader leggerebbe come un elenco di voci e non come una scelta (dal giro di T3)
    <div
      role="listbox"
      aria-label={fieldLabel ? `Suggerimenti: ${fieldLabel}` : undefined}
      className="flex flex-col overflow-hidden rounded-card bg-card"
    >
      {options.map((ingredient) => {
        const categoryId = `${baseId}-${ingredient.id}`;
        return (
          <button
            key={ingredient.id}
            type="button"
            role="option"
            aria-selected={false}
            aria-label={ingredient.display_name}
            aria-describedby={categoryId}
            disabled={disabled}
            onClick={() => onPick(ingredient)}
            className="flex min-h-12 w-full items-baseline gap-3 px-3 py-2.5 text-left text-sm disabled:opacity-50"
          >
            <span className="truncate">{ingredient.display_name}</span>
            {/* la categoria serve a distinguere due omonimi, non a essere letta
                sempre: in fondo alla riga, e per chi ascolta è una descrizione, non
                un pezzo del nome */}
            <span id={categoryId} className="ml-auto shrink-0 text-xs text-ink-faint">
              {ingredient.category}
            </span>
          </button>
        );
      })}
    </div>
  );
}
